"""Occurrence-preserving DAG projection and exact labeled graph correspondence."""

import copy
from collections import Counter

from trusted_synthesis.canonical_json import canonical_json_bytes
from trusted_synthesis.domains.finance.qa_vnext.protocol import record, require

from .judgments import verify_review
from .plan import VERSION


def key(value):
    return canonical_json_bytes(value).decode()


def expression(tree):
    """Only the explicitly supported multiply commutation, not polynomial identity."""
    if isinstance(tree, str):
        return tree
    args = [expression(t) for t in tree["args"]]
    if tree["op"] in {"multiply", "add"}:
        args.sort(key=key)
    return {"op": tree["op"], "args": args}


def project(session, review):
    verify_review(session, review)
    if any(r["status"] != "REVIEWED" for r in review["annotations"]):
        return record(
            "finqa_numeric_projection",
            version=VERSION,
            label=session["row"]["label"],
            status="UNDETERMINED",
            reason="unresolved_public_commitment",
            graph=None,
            raw_and_validity_retained=True,
        )
    try:
        return _project(session, review)
    except (Unsupported, KeyError, TypeError) as error:
        return record(
            "finqa_numeric_projection",
            version=VERSION,
            label=session["row"]["label"],
            status="UNDETERMINED",
            reason=str(error),
            graph=None,
            raw_and_validity_retained=True,
        )


class Unsupported(ValueError):
    pass


def _project(session, review):
    turns = session["turns"]
    annotations = {r["submission"]: r for r in review["annotations"]}
    context = turns[0]["request"]["context"]
    graph = {
        "binding": {
            "version": VERSION,
            "task_id": context["task_id"],
            "source_digest": context["source_digest"],
            "protocol_id": turns[0]["request"]["protocol_id"],
        },
        "nodes": {},
        "edges": [],
    }
    nodes, edges = graph["nodes"], graph["edges"]
    for ref in turns[0]["request"]["protocol"]["constants"]:
        nodes[ref] = {"kind": "constant", "id": ref, "exact_value": ref.split(":", 1)[1]}
    for source in context["numeric_catalog"]:
        nodes[source["id"]] = {
            "kind": "source",
            "catalog": source,
            "fragment": context["related_source_fragments"][source["segment"]],
        }
    claims, observations, evidence, actual_inputs = {}, {}, {}, {}
    temporal_units, barriers, previous_operations, consumed_updates = [], [], {}, set()
    final_claim, final_id = None, None

    def edge(source, target, role):
        edges.append([source, target, role])

    for position, turn in enumerate(turns):
        event = turn["event"]
        model, index = event["model_submission"], event["submission_count"]
        if model is None:
            try:
                import json

                model = json.loads(turn["raw"])
                if not isinstance(model, dict) or model.get("kind") != "action":
                    raise Unsupported("uninterpreted_unadmitted_submission")
            except (ValueError, TypeError):
                raise Unsupported("uninterpreted_unadmitted_submission") from None
        node_id = f"action:{index}"
        if model["kind"] == "update":
            if index not in consumed_updates:
                raise Unsupported("unpaired_or_interleaved_update")
            continue
        if model["kind"] == "action":
            operation = model["operation"]
            if (
                operation not in {"read", "add", "multiply", "subtract", "divide"}
                or model["parameters"]
            ):
                raise Unsupported("outside_finite_operation_domain")
            annotation = annotations[index]
            label = {
                "kind": "action_resolution" if event["admitted"] else "unadmitted_action",
                "operation": operation,
                "parameters": model["parameters"],
                "public_commitments": sorted(annotation["public_commitments"]),
            }
            nodes[node_id] = label
            actual_inputs[node_id] = []
            evidence[node_id] = {
                "action_submission": index,
                "transition_id": event["id"],
                "raw_sha256": event["raw_sha256"],
                "actual_inputs": model["inputs"],
                "judgment_review_id": review["id"],
                "admitted": event["admitted"],
                "accepted_claim_id": None,
                "update_submission": None,
            }
            for slot, ref in enumerate(model["inputs"]):
                if ref in claims:
                    producer, representation = claims[ref], "accepted_claim"
                elif ref in nodes and nodes[ref]["kind"] == "constant":
                    producer, representation = ref, "constant"
                elif ref in nodes and nodes[ref]["kind"] == "source":
                    producer, representation = ref, "raw_source"
                else:
                    raise Unsupported("unbound_input")
                port = (
                    "factor"
                    if operation == "multiply"
                    else "term"
                    if operation == "add"
                    else f"input:{slot}"
                )
                edge(producer, node_id, port + ":" + representation)
                if representation == "accepted_claim":
                    actual_inputs[node_id].append(producer)
            for prior in annotation["explicit_prior_accepted_actions"]:
                parent = f"action:{prior}"
                if parent not in claims.values():
                    raise Unsupported("unbound_public_accepted_knowledge")
                edge(parent, node_id, "public_prior_knowledge")
            temporal_units.append(node_id)
            if event["admitted"]:
                obs = event["observation"]
                if position + 1 >= len(turns):
                    raise Unsupported("unresolved_observation")
                update_event = turns[position + 1]["event"]
                update = update_event["model_submission"]
                if not (
                    update_event["admitted"]
                    and update["kind"] == "update"
                    and update["observation"] == obs["id"]
                ):
                    raise Unsupported("unpaired_or_interleaved_update")
                consumed_updates.add(update_event["submission_count"])
                label["disposition"] = update["disposition"]
                label["output"] = {
                    "exact_value": obs["exact_value"],
                    "expression": expression(obs["expression"]),
                    "lineage": obs["lineage"],
                }
                evidence[node_id].update(
                    observation_id=obs["id"],
                    update_submission=update_event["submission_count"],
                    update_transition_id=update_event["id"],
                    disposition=update["disposition"],
                )
                observations[obs["id"]] = node_id
                if update["disposition"] == "accept":
                    claim = update_event["claim"]
                    require(claim["observation_id"] == obs["id"], "projection.claim_occurrence")
                    claims[claim["id"]] = node_id
                    evidence[node_id]["accepted_claim_id"] = claim["id"]
                elif update["disposition"] == "reject":
                    require(update_event["claim"] is None, "projection.reject_no_claim")
                    barriers.append(node_id)
                else:
                    raise Unsupported("unknown_disposition")
                inputs = list(model["inputs"])
                if operation in {"multiply", "add"}:
                    inputs.sort()
                signature = key([operation, inputs, model["parameters"]])
                if signature in previous_operations:
                    edge(previous_operations[signature], node_id, "duplicate_predecessor")
                    evidence[node_id]["duplicate_of"] = previous_operations[signature]
                previous_operations[signature] = node_id
            else:
                require(
                    event["observation"] is None and event["claim"] is None,
                    "projection.unadmitted_not_executed",
                )
                label["error"] = event["error"]
                evidence[node_id]["error"] = event["error"]
                barriers.append(node_id)
        elif model["kind"] == "final" and event["admitted"]:
            if model["answer_claim"] not in claims:
                raise Unsupported("unbound_final_claim")
            final_id, final_claim = f"final:{index}", model["answer_claim"]
            nodes[final_id] = {
                "kind": "final",
                "result": model["result"],
                "citations": sorted(model["citations"]),
            }
            edge(claims[final_claim], final_id, "answer_claim")
            for previous in temporal_units:
                edge(previous, final_id, "before_terminal")
            evidence[final_id] = {
                "submission": index,
                "answer_claim_id": final_claim,
                "transition_id": event["id"],
            }
        else:
            raise Unsupported("unsupported_submission")
    used_constants = {e[0] for e in edges if e[0].startswith("constant:")}
    for ref in list(nodes):
        if nodes[ref]["kind"] == "constant" and ref not in used_constants:
            del nodes[ref]
    require(final_id is not None, "projection.original_valid_final")
    for barrier in barriers:
        ordinal = temporal_units.index(barrier)
        for prior in temporal_units[:ordinal]:
            edge(prior, barrier, "adjustment_order")
        for after in temporal_units[ordinal + 1 :]:
            edge(barrier, after, "adjustment_order")
    # Deduplicate identical order edges only; multiplicity of input edges is preserved.
    ordering = {tuple(e) for e in edges if e[2] == "adjustment_order"}
    graph["edges"] = sorted(
        [e for e in edges if e[2] != "adjustment_order"] + [list(e) for e in ordering]
    )
    ancestry = set()

    def visit(node):
        if node in ancestry:
            return
        ancestry.add(node)
        for parent in actual_inputs[node]:
            visit(parent)

    visit(claims[final_claim])
    require(
        {evidence[n]["accepted_claim_id"] for n in ancestry}
        == set(session["audit"]["recovery_trace"]["valid_final_actual_claim_ancestry"]),
        "projection.saved_actual_ancestry",
    )
    support = {"binding": graph["binding"], "nodes": {}, "edges": []}
    selected = ancestry | {final_id}
    for source, target, role in graph["edges"]:
        if target in selected and (
            role.startswith(("input:", "factor:", "term:")) or role == "answer_claim"
        ):
            support["edges"].append([source, target, role])
            selected.add(source)
    for node in selected:
        label = copy.deepcopy(nodes[node])
        label.pop("public_commitments", None)
        support["nodes"][node] = label
    for node in temporal_units:
        evidence[node]["in_actual_final_ancestry"] = node in ancestry
    covered = []
    for item in evidence.values():
        covered.append(item.get("action_submission", item.get("submission")))
        if item.get("update_submission") is not None:
            covered.append(item["update_submission"])
    require(sorted(covered) == list(range(1, len(turns) + 1)), "projection.every_submission_once")
    return record(
        "finqa_numeric_projection",
        version=VERSION,
        label=session["row"]["label"],
        status="MAPPED",
        graph=graph,
        support_graph=support,
        evidence=evidence,
        original_interaction_count=len(turns),
        covered_original_submissions=sorted(covered),
        retained_unadmitted=len([n for n in nodes.values() if n["kind"] == "unadmitted_action"]),
        actual_operations=len(actual_inputs)
        - len([n for n in nodes.values() if n["kind"] == "unadmitted_action"]),
        final_support_operations=len(ancestry),
        retained_actual_off_support=[
            n
            for n in temporal_units
            if nodes[n]["kind"] == "action_resolution" and n not in ancestry
        ],
        all_occurrences_retained=True,
        validity_recomputed=False,
    )


def compare(left, right):
    """Complete finite search; an explicit bijection, not equality of graph hashes."""
    if left["binding"] != right["binding"]:
        return {
            "relation": "OUT_OF_DOMAIN",
            "reason": "different_source_or_protocol",
            "mapping": None,
        }
    ln, rn = left["nodes"], right["nodes"]
    lc, rc = Counter(key(v) for v in ln.values()), Counter(key(v) for v in rn.values())
    if lc != rc:
        return {
            "relation": "DIFFERENT",
            "reason": "labeled_node_multiplicity",
            "left_only": dict(lc - rc),
            "right_only": dict(rc - lc),
            "mapping": None,
        }
    le, re = Counter(map(tuple, left["edges"])), Counter(map(tuple, right["edges"]))

    def incident(edges, node, outgoing):
        return Counter(
            (role, count) for (a, b, role), count in edges.items() if (a if outgoing else b) == node
        )

    candidates = {
        a: [
            b
            for b in rn
            if ln[a] == rn[b]
            and incident(le, a, True) == incident(re, b, True)
            and incident(le, a, False) == incident(re, b, False)
        ]
        for a in ln
    }
    order = sorted(ln, key=lambda a: (len(candidates[a]), a))
    mapping, used = {}, set()

    def between(edges, a, b):
        return Counter({role: count for (x, y, role), count in edges.items() if x == a and y == b})

    def search(position):
        if position == len(order):
            return Counter((mapping[a], mapping[b], role) for a, b, role in left["edges"]) == re
        a = order[position]
        for b in candidates[a]:
            if b in used or between(le, a, a) != between(re, b, b):
                continue
            if any(
                between(le, a, x) != between(re, b, y) or between(le, x, a) != between(re, y, b)
                for x, y in mapping.items()
            ):
                continue
            mapping[a] = b
            used.add(b)
            if search(position + 1):
                return True
            del mapping[a]
            used.remove(b)
        return False

    matched = search(0)
    return {
        "relation": "EQUIVALENT" if matched else "DIFFERENT",
        "reason": "exact_labeled_occurrence_bijection" if matched else "no_labeled_graph_bijection",
        "mapping": dict(mapping) if matched else None,
        "edge_multiset_checked": matched,
    }
