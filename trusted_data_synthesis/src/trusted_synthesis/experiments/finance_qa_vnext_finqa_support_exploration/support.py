"""Source-bound actual-consumption probes, distinct from graph classes or rewards."""

from trusted_synthesis.domains.finance.qa_vnext.protocol import record

from .plan import VERSION
from .projection import expression


def support_graph(session):
    """Actual accepted ancestors, computable even when public interpretation is unknown."""
    audit, request = session["audit"], session["turns"][0]["request"]
    context = request["context"]
    used = {
        r["accepted_claim_id"]: r
        for r in audit["recovery_trace"]["operations"]
        if r["consumed_by_valid_final"]
    }
    nodes, edges = {}, []
    facts = {f["id"]: f for f in context["numeric_catalog"]}
    for row in used.values():
        nid = f"action:{row['submission']}"
        nodes[nid] = {
            "kind": "action_resolution",
            "operation": row["operation"],
            "parameters": {},
            "disposition": "accept",
            "output": {
                "exact_value": row["exact_value"],
                "expression": expression(row["expression"]),
                "lineage": row["lineage"],
            },
        }
        for slot, ref in enumerate(row["inputs"]):
            if ref in used:
                parent, kind = f"action:{used[ref]['submission']}", "accepted_claim"
            elif ref.startswith("constant:"):
                parent, kind = ref, "constant"
                nodes[ref] = {"kind": "constant", "id": ref, "exact_value": ref.split(":", 1)[1]}
            else:
                parent, kind = ref, "raw_source"
                fact = facts[ref]
                nodes[ref] = {
                    "kind": "source",
                    "catalog": fact,
                    "fragment": context["related_source_fragments"][fact["segment"]],
                }
            port = (
                "factor"
                if row["operation"] == "multiply"
                else "term"
                if row["operation"] == "add"
                else f"input:{slot}"
            )
            edges.append([parent, nid, port + ":" + kind])
    final = session["turns"][-1]["event"]
    model = final["model_submission"]
    fid = f"final:{final['submission_count']}"
    nodes[fid] = {
        "kind": "final",
        "result": model["result"],
        "citations": sorted(model["citations"]),
    }
    edges.append([f"action:{used[model['answer_claim']]['submission']}", fid, "answer_claim"])
    return {
        "binding": {
            "version": VERSION,
            "task_id": context["task_id"],
            "source_digest": context["source_digest"],
            "protocol_id": request["protocol_id"],
        },
        "nodes": nodes,
        "edges": edges,
    }


def witnesses(audit):
    operations = audit["recovery_trace"]["operations"]
    used = {r["accepted_claim_id"]: r for r in operations if r["consumed_by_valid_final"]}

    def matching(name, operation):
        return {
            cid
            for cid, row in used.items()
            if name in row["method_probe_matches"] and row["operation"] == operation
        }

    def ancestors(cid):
        found = {cid}
        for parent in used[cid]["input_claim_ids"]:
            found |= ancestors(parent)
        return found

    published = [f for f in audit["recovery_trace"]["final_attempts"] if f["admitted"]]
    answer = published[-1]["answer_claim_id"] if published else None

    def publication_cut(cid):
        if audit["task_key"] == "J2":
            return cid == answer
        if answer not in used:
            return False
        root = used[answer]
        if root["operation"] != "multiply" or "constant:100" not in root["inputs"]:
            return False
        if len(root["input_claim_ids"]) != 1:
            return False
        ratio = used[root["input_claim_ids"][0]]
        return (
            ratio["operation"] == "divide"
            and len(ratio["input_claim_ids"]) == 2
            and ratio["input_claim_ids"][0] == cid
            and ratio["input_claim_ids"][1] in matching("net_base", "add")
        )

    def pair(label, left_name, right_name, branch_op, combine_op, required=None):
        left, right = matching(left_name, branch_op), matching(right_name, branch_op)
        found = []
        for cid, row in used.items():
            if (
                row["operation"] != combine_op
                or len(row["input_claim_ids"]) != 2
                or not publication_cut(cid)
            ):
                continue
            choices = [row["input_claim_ids"]]
            if combine_op == "add":
                choices.append(list(reversed(row["input_claim_ids"])))
            for a, b in choices:
                if a not in left or b not in right:
                    continue
                if required and not all(
                    ancestors(x) & matching(probe, "subtract")
                    for x, probe in zip((a, b), required, strict=True)
                ):
                    continue
                found.append(
                    {
                        "combine_submission": row["submission"],
                        "combine_claim_id": cid,
                        "left_claim_id": a,
                        "right_claim_id": b,
                        "left_submission": used[a]["submission"],
                        "right_submission": used[b]["submission"],
                        "all_in_actual_valid_final_ancestry": True,
                        "actual_publication_cut_verified": True,
                    }
                )
        return {"name": label, "witnesses": found, "established": bool(found)}

    if audit["task_key"] == "J2":
        routes = [
            pair("annual_totals", "annual_new", "annual_base", "multiply", "subtract"),
            pair(
                "quantity_base_price_plus_price_new_quantity",
                "quantity_effect_base_price",
                "price_effect_new_quantity",
                "multiply",
                "add",
                ("quantity_change", "price_change"),
            ),
            pair(
                "quantity_new_price_plus_price_base_quantity",
                "quantity_effect_new_price",
                "price_effect_base_quantity",
                "multiply",
                "add",
                ("quantity_change", "price_change"),
            ),
        ]
    else:
        routes = [
            pair("annual_net_costs", "net_new", "net_base", "add", "subtract"),
            pair("signed_component_changes", "cost_change", "signed_tax_change", "subtract", "add"),
        ]
    return record(
        "support_route_witnesses",
        label=audit["label"],
        task_key=audit["task_key"],
        exploration_stratum=audit["exploration_stratum"],
        complete_valid=audit["complete_valid"],
        routes=routes,
        exhaustive_taxonomy=False,
        is_behavior_class_assignment=False,
        unused_or_rejected_intermediates_excluded=True,
        economic_contribution=None,
    )
