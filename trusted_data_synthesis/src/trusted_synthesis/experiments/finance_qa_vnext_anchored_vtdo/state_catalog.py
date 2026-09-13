"""Evidence-bound finite semantic DAG states over an unchanged material kernel.

Exact canonicalization is bounded, never a hash heuristic for graph equivalence.
If its search budget is exhausted the original package remains pending. The
runtime mapper preserves all observed visibility edges rather than guessing
that an unreferenced earlier observation could not affect a later decision.
"""

import ast
import copy
import json
from collections import Counter, defaultdict
from fractions import Fraction
from pathlib import Path

from ..finance_qa_vnext_basis_student.kernel import validate_row
from ..finance_qa_vnext_catalog_bridge import worker
from ..finance_qa_vnext_eval_readiness import materials, training_runtime
from .protocol import checked_record, encode, record, require, sha

MAX_NODES = 128
MAX_SEARCH_NODES = 100000


def policy():
    return record(
        "state_mapper_policy",
        version="explicit_runtime_semantic_DAG.v1",
        graph_domain="finite labelled DAG; exact canonical individualization/refinement",
        max_graph_nodes=MAX_NODES,
        max_canonical_search_nodes=MAX_SEARCH_NODES,
        id_renaming_changes_state=False,
        unordered_independent_graph_operations_change_state=False,
        operation_roles="AST operand positions and explicit result_id variable bindings",
        actual_sources_and_periods=(
            "complete original public source objects and exact read locators"
        ),
        visibility="all actual prior tool observations retained as visible-before edges",
        unknown_free_text_dependency_inference=False,
        cycles="reject",
        runtime_domain=(
            "replayed successful read_source/calculate and closed structured first Final"
        ),
        unsupported_event_or_unprovable_relation="retain original package as PENDING_REVIEW",
        actual_methods_never_merged=True,
        old_signatures_rewritten=False,
        old_financial_admission=(
            "inherited content-bound qualification, not independently re-certified"
        ),
        train_pending="block entire new train-kernel admission; do not drop packages",
        heldout_pending="record separately; never enter train state counts or weights",
        initial_state_mass="dual n_train/16; control n_train/8",
        coverage_prior="r=pi0",
    )


class CanonicalizationLimit(ValueError):
    pass


def _graph(graph):
    require(
        isinstance(graph, dict) and set(graph) == {"label", "nodes", "edges"}, "dag.closed_graph"
    )
    require(
        isinstance(graph["nodes"], list) and 0 < len(graph["nodes"]) <= MAX_NODES, "dag.node_bound"
    )
    require(
        all(
            set(node) == {"id", "label"} and isinstance(node["id"], str) and node["id"]
            for node in graph["nodes"]
        ),
        "dag.closed_labelled_nodes",
    )
    ids = [node["id"] for node in graph["nodes"]]
    require(len(set(ids)) == len(ids), "dag.unique_reference_keys")
    indices = {identifier: index for index, identifier in enumerate(ids)}
    labels = [copy.deepcopy(node["label"]) for node in graph["nodes"]]
    edges = []
    require(isinstance(graph["edges"], list), "dag.edge_list")
    for edge in graph["edges"]:
        require(
            set(edge) == {"from", "to", "role"}
            and edge["from"] in indices
            and edge["to"] in indices
            and isinstance(edge["role"], str)
            and edge["role"],
            "dag.closed_bound_role_edge",
        )
        edges.append((indices[edge["from"]], indices[edge["to"]], edge["role"]))
    require(len(set(edges)) == len(edges), "dag.no_duplicate_edges")
    indegrees = Counter(target for _, target, _ in edges)
    followers = defaultdict(list)
    for source, target, _ in edges:
        followers[source].append(target)
    queue = [index for index in range(len(ids)) if not indegrees[index]]
    seen = 0
    while queue:
        current = queue.pop()
        seen += 1
        for target in followers[current]:
            indegrees[target] -= 1
            if indegrees[target] == 0:
                queue.append(target)
    require(seen == len(ids), "dag.cycle_rejected")
    encode(graph["label"])
    return ids, labels, edges


def canonicalize_dag(graph, *, max_search_nodes=MAX_SEARCH_NODES):
    """An exact canonical graph, or an explicit failure; no probabilistic merging."""
    require(
        type(max_search_nodes) is int and 0 < max_search_nodes <= MAX_SEARCH_NODES,
        "dag.search_budget",
    )
    ids, labels, edges = _graph(graph)
    n = len(ids)
    incoming, outgoing = defaultdict(list), defaultdict(list)
    for source, target, role in edges:
        incoming[target].append((source, role))
        outgoing[source].append((target, role))

    def partition(signatures):
        unique = {value: index for index, value in enumerate(sorted(set(signatures)))}
        return tuple(unique[value] for value in signatures)

    initial = partition([encode(label) for label in labels])

    def refine(colors):
        while True:
            signatures = [
                encode(
                    [
                        colors[index],
                        sorted((role, colors[other]) for other, role in incoming[index]),
                        sorted((role, colors[other]) for other, role in outgoing[index]),
                    ]
                )
                for index in range(n)
            ]
            changed = partition(signatures)
            if len(set(changed)) == len(set(colors)):
                return changed
            colors = changed

    explored, best, best_mapping = 0, None, None

    def search(colors):
        nonlocal explored, best, best_mapping
        explored += 1
        if explored > max_search_nodes:
            raise CanonicalizationLimit("dag.exact_search_budget_exhausted")
        colors = refine(colors)
        cells = defaultdict(list)
        for index, color in enumerate(colors):
            cells[color].append(index)
        ambiguous = [(color, nodes) for color, nodes in sorted(cells.items()) if len(nodes) > 1]
        if ambiguous:
            for individual in ambiguous[0][1]:
                branch = list(colors)
                branch[individual] = max(colors) + 1
                search(tuple(branch))
            return
        order = sorted(range(n), key=lambda index: colors[index])
        renamed = {index: position for position, index in enumerate(order)}
        normalized = {
            "label": graph["label"],
            "nodes": [labels[index] for index in order],
            "edges": sorted(
                [[renamed[source], renamed[target], role] for source, target, role in edges]
            ),
        }
        encoded = encode(normalized)
        if best is None or encoded < best:
            best, best_mapping = encoded, {ids[index]: renamed[index] for index in range(n)}

    search(initial)
    canonical = json.loads(best)
    return record(
        "canonical_semantic_DAG",
        canonical_graph=canonical,
        state_id="behavior_state:" + sha(best),
        original_to_canonical=best_mapping,
        exact=True,
        explored_search_nodes=explored,
    )


def isomorphic(left, right):
    return canonicalize_dag(left)["canonical_graph"] == canonicalize_dag(right)["canonical_graph"]


def _expression(expression, variables):
    require(isinstance(expression, str) and len(expression) <= 8192, "mapper.expression_bound")
    tree = ast.parse(expression, mode="eval")

    def visit(node):
        if isinstance(node, ast.Constant) and type(node.value) in {int, float}:
            return ["literal", str(Fraction(str(node.value)))]
        if isinstance(node, ast.Name):
            require(node.id in variables, "mapper.expression_declared_input_role")
            return ["input_role", node.id]
        if isinstance(node, ast.BinOp) and type(node.op) in {
            ast.Add,
            ast.Sub,
            ast.Mult,
            ast.Div,
            ast.Pow,
        }:
            return [type(node.op).__name__, visit(node.left), visit(node.right)]
        if isinstance(node, ast.UnaryOp) and type(node.op) in {ast.UAdd, ast.USub}:
            return [type(node.op).__name__, visit(node.operand)]
        if isinstance(node, (ast.List, ast.Tuple)):
            return [type(node).__name__, *[visit(child) for child in node.elts]]
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            require(
                node.func.id in {"sum", "avg", "min", "max", "abs"} and not node.keywords,
                "mapper.finite_numeric_function",
            )
            return ["call", node.func.id, *[visit(child) for child in node.args]]
        raise ValueError("mapper.unsupported_expression_node")

    return visit(tree.body)


def project_session(session, qualification):
    """Derive only facts present in replayed original public records and certificates."""
    old_signature = qualification.get("full_signature")
    provenance = {
        "original_session_id": session.get("id"),
        "original_qualification_id": qualification.get("id"),
        "original_full_class_id": qualification.get("full_class"),
        "original_signature_id": old_signature.get("id")
        if isinstance(old_signature, dict)
        else None,
        "original_signature_sha256": sha(encode(old_signature))
        if old_signature is not None
        else None,
        "mapper_policy_id": policy()["id"],
        "original_raw_turns_sha256": sha(encode(session.get("turns", []))),
    }
    try:
        training_runtime.replay(session)
        materials.checked_record(qualification, "training_assessment")
        require(
            qualification["session_id"] == session["id"]
            and qualification["financial_valid"]
            and qualification["representation_eligible"]
            and qualification["authentic_Teacher_origin_verified"]
            and qualification["full_mapping_status"] == "MAPPED",
            "mapper.original_admitted_qualification",
        )
        method = qualification["actual_method"]
        require(method in {"endpoint", "movement", "control"}, "mapper.exact_actual_method")
        require(
            isinstance(old_signature, dict) and old_signature["id"] == qualification["full_class"],
            "mapper.original_signature_reference",
        )
        expected = worker.record(
            "finite_complete_signature",
            **{
                key: value
                for key, value in old_signature.items()
                if key not in {"id", "schema_version"}
            },
        )
        require(old_signature == expected, "mapper.original_signature_identity")
        require(
            old_signature["task_id"] == session["identity"]["task_id"]
            and old_signature["actual_method"] == method,
            "mapper.original_signature_task_method",
        )
        public = worker.public_document(session["public_messages"], session["identity"])
        sources = {source["source_id"]: source for source in public["sources"]}
        graph = {
            "label": {
                "task_id": session["identity"]["task_id"],
                "actual_method": method,
                "visibility_contract": "all actual prior observations preserved",
            },
            "nodes": [
                {
                    "id": "initial",
                    "label": {
                        "kind": "initial_visible_information",
                        "actual_initial_messages_sha256": sha(encode(session["initial_messages"])),
                    },
                }
            ],
            "edges": [],
        }
        seen, evidence, final_identifier = [], [], None
        signature_events = {event["result_id"]: event for event in old_signature["events"]}
        for turn, event in zip(session["turns"], session["events"], strict=True):
            require(event["protocol_error"] is None, "mapper.unproved_format_recovery")
            choice = worker.strict_json(turn["raw_response"])
            if event["final"]:
                require(
                    set(choice) == {"final"}
                    and isinstance(choice["final"], dict)
                    and set(choice["final"]) == {"value", "unit", "result_id"},
                    "mapper.closed_structured_Final_only",
                )
                final = choice["final"]
                require(final["result_id"] in seen, "mapper.actual_Final_support_reference")
                node_id, final_identifier = "final", final["result_id"]
                label = {
                    "kind": "Final",
                    "value": str(Fraction(str(final["value"]))),
                    "unit": final["unit"],
                }
                graph["edges"].append(
                    {"from": final_identifier, "to": node_id, "role": "Final_support"}
                )
            else:
                require(
                    set(choice) == {"tool", "arguments"}
                    and event["tool_call"] is not None
                    and event["tool_call"]["status"] == "ok",
                    "mapper.successful_closed_tool_only",
                )
                tool, args = event["tool_call"], choice["arguments"]
                node_id = tool["call_id"]
                require(
                    node_id not in seen and node_id in signature_events,
                    "mapper.original_tool_reference",
                )
                certified = signature_events[node_id]
                require(
                    certified.get("kind") == tool["tool"]
                    and certified.get("unit") == tool["result"]["unit"]
                    and certified.get("source_locator") == tool["result"].get("source_locator")
                    and certified.get("used_result_ids")
                    == tool["result"].get("used_result_ids", []),
                    "mapper.original_executed_signature_edges",
                )
                require(
                    certified.get("role")
                    in {
                        "final_support",
                        "source_exploration",
                        "redundant_target_recomputation",
                        "alternative_basis_target_cross_check",
                        "explicitly_revised_calculation",
                    },
                    "mapper.unproved_execution_role",
                )
                if tool["tool"] == "read_source":
                    require(
                        set(args) <= {"source_id", "cells", "unit"}, "mapper.closed_source_read"
                    )
                    source = sources[args["source_id"]]
                    label = {
                        "kind": "read_source",
                        "source": {
                            key: value for key, value in source.items() if key != "original_rows"
                        },
                        "complete_original_source_object_sha256": sha(encode(source)),
                        "original_locator": tool["result"]["source_locator"],
                        "conversion": tool["result"]["conversion"],
                    }
                elif tool["tool"] == "calculate":
                    require(
                        set(args) <= {"expression", "variables", "unit", "revises_result_id"},
                        "mapper.no_unproved_calculation_declarations",
                    )
                    variables = args.get("variables", {})
                    require(isinstance(variables, dict), "mapper.explicit_variables")
                    literals = {}
                    for role, value in variables.items():
                        if isinstance(value, dict):
                            require(
                                set(value) == {"result_id"} and value["result_id"] in seen,
                                "mapper.explicit_prior_input_reference",
                            )
                            graph["edges"].append(
                                {"from": value["result_id"], "to": node_id, "role": "input:" + role}
                            )
                        else:
                            require(
                                type(value) in {str, int, float}, "mapper.finite_scalar_literal"
                            )
                            literals[role] = str(Fraction(str(value)))
                    label = {
                        "kind": "calculate",
                        "expression": _expression(args["expression"], variables),
                        "literals": literals,
                        "unit": tool["result"]["unit"],
                        "exact_value": tool["result"]["exact_value"],
                        "conversion": tool["result"]["conversion"],
                    }
                    revision = args.get("revises_result_id")
                    if revision is not None:
                        require(revision in seen, "mapper.prior_explicit_revision")
                        graph["edges"].append(
                            {"from": revision, "to": node_id, "role": "explicit_revision"}
                        )
                else:
                    raise ValueError("mapper.unsupported_tool")
                label["inherited_executed_role"] = certified["role"]
            graph["nodes"].append({"id": node_id, "label": label})
            graph["edges"].append({"from": "initial", "to": node_id, "role": "initial_visibility"})
            graph["edges"].extend(
                {"from": earlier, "to": node_id, "role": "observed_before_decision"}
                for earlier in seen
            )
            evidence.append(
                {
                    "node_id": node_id,
                    "response_index": turn["response_index"],
                    "raw_response_sha256": turn["raw_response_sha256"],
                    "actual_input_messages_sha256": sha(encode(turn["input_messages"])),
                }
            )
            seen.append(node_id)
        require(
            final_identifier is not None and session["terminal"] == "first_final",
            "mapper.first_Final_required",
        )
        require(
            old_signature["first_final_result_id"] == final_identifier,
            "mapper.same_original_Final_support",
        )
        require(
            set(signature_events) == set(seen) - {"final"}, "mapper.all_executed_nodes_retained"
        )
        for check in old_signature.get("target_cross_checks", []):
            require(
                check["result_id"] in signature_events
                and check["first_final_result_id"] == final_identifier,
                "mapper.inherited_executed_verification_reference",
            )
            graph["edges"].append(
                {
                    "from": check["result_id"],
                    "to": "final",
                    "role": "inherited_check:" + check["kind"],
                }
            )
        canonical = canonicalize_dag(graph)
        return record(
            "original_package_state_mapping",
            **provenance,
            status="MAPPED",
            reasons=[],
            state_id=canonical["state_id"],
            actual_method=method,
            semantic_DAG=graph,
            canonical_graph=canonical["canonical_graph"],
            node_evidence=evidence,
            original_to_canonical=canonical["original_to_canonical"],
            old_financial_qualification_inherited_not_rerun=True,
        )
    except (ValueError, TypeError, KeyError, SyntaxError, IndexError, RecursionError) as error:
        return record(
            "original_package_state_mapping",
            **provenance,
            status="PENDING_REVIEW",
            reasons=[str(error)],
            state_id=None,
            actual_method=qualification.get("actual_method"),
            original_package_must_not_be_removed=True,
        )


def validate_original_manifest(manifest):
    materials.checked_record(manifest, "fixed_AB_material_manifest")
    require(
        manifest["status"] == "FIXED_AB_MATERIALS_READY"
        and manifest["collection_complete"] is True,
        "state_catalog.original_materials_admitted",
    )
    selected = {
        row["task_id"]: row["group"] for row in manifest["population_selection"]["selected"]
    }
    require(
        len(selected) == len(manifest["population_selection"]["selected"]),
        "state_catalog.unique_tasks",
    )
    groups = defaultdict(list)
    seen = set()
    for item in manifest["packages"]:
        require(
            item["id"] not in seen
            and item["task_id"] in selected
            and item["group"] == selected[item["task_id"]]
            and item["pool"] in {"A", "B"},
            "state_catalog.original_unique_pool_task_packages",
        )
        seen.add(item["id"])
        require(
            item["actual_method"]
            in (("control",) if item["group"] == "control" else ("endpoint", "movement")),
            "state_catalog.actual_method_not_guidance",
        )
        groups[item["pool"], item["task_id"], item["actual_method"]].append(item)
    expected = {
        (pool, task, method)
        for task, group in selected.items()
        for pool in ("A", "B")
        for method in (("control",) if group == "control" else ("endpoint", "movement"))
    }
    require(set(groups) == expected, "state_catalog.complete_original_AB_strata")
    for values in groups.values():
        require(
            len(values) == 10
            and [row["within_stratum_index"] for row in values] == list(range(10))
            and [row["role"] for row in values] == ["train"] * 8 + ["heldout"] * 2,
            "state_catalog.original_ordered_eight_plus_two",
        )
    return selected


def build_catalog(manifest, evidence_by_package):
    """Pure builder over explicitly loaded originals; missing evidence remains pending.

    Each evidence entry contains encoded_package, raw_package, session,
    qualification, and optional immutable file references. Callers must load the
    originals from their already admitted parent manifests, not live collection.
    """
    selected = validate_original_manifest(manifest)
    require(
        set(evidence_by_package) <= {row["id"] for row in manifest["packages"]},
        "state_catalog.no_foreign_evidence",
    )
    mappings, states = [], {}
    for descriptor in manifest["packages"]:
        item = {
            "package_id": descriptor["id"],
            "pool": descriptor["pool"],
            "task_id": descriptor["task_id"],
            "actual_method": descriptor["actual_method"],
            "role": descriptor["role"],
            "descriptor": copy.deepcopy(descriptor),
        }
        try:
            evidence = evidence_by_package[descriptor["id"]]
            encoded, raw, session, qualification = [
                evidence[key]
                for key in ("encoded_package", "raw_package", "session", "qualification")
            ]
            materials.checked_record(encoded, "encoded_original_package")
            require(
                encoded["id"] == descriptor["id"]
                and sha(encode(encoded)) == descriptor["sha256"]
                and encoded["raw_package_id"] == raw["id"],
                "state_catalog.original_encoded_raw_binding",
            )
            require(
                encoded["consumable"] is True
                and encoded["maximum_sequence_length"] == 24576
                and encoded["tokenizer_binding_id"] == manifest["tokenizer_binding"]["id"]
                and all(
                    encoded[key] == descriptor[key]
                    for key in ("task_id", "pool", "actual_method", "whole_package_target_tokens")
                )
                and [row["candidate_id"] for row in encoded["rows"]]
                == [row["id"] for row in raw["candidates"]]
                and sum(validate_row(row)["target_token_count"] for row in encoded["rows"])
                == encoded["whole_package_target_tokens"],
                "state_catalog.all_original_rows_and_lengths",
            )
            registered = {
                "session_id": descriptor["registered_session_id"],
                "task_id": descriptor["task_id"],
                "pool": descriptor["pool"],
            }
            require(
                materials.raw_package(session, qualification, registered) == raw,
                "state_catalog.whole_original_raw_package_identity",
            )
            require(
                raw["actual_method"] == descriptor["actual_method"]
                and raw["task_id"] == descriptor["task_id"]
                and raw["pool"] == descriptor["pool"],
                "state_catalog.original_pool_task_method_join",
            )
            mapping = project_session(session, qualification)
            item.update(
                mapping=mapping,
                state_id=mapping["state_id"],
                status=mapping["status"],
                original_rows_sha256=sha(encode(encoded["rows"])),
                whole_package_target_tokens=encoded["whole_package_target_tokens"],
                original_file_references=copy.deepcopy(evidence.get("references", [])),
            )
            if mapping["status"] == "MAPPED":
                states[mapping["state_id"]] = mapping["canonical_graph"]
        except (ValueError, KeyError, TypeError, IndexError) as error:
            item.update(
                state_id=None,
                status="PENDING_REVIEW",
                reasons=[str(error)],
                original_package_must_not_be_removed=True,
            )
        mappings.append(item)
    supports = []
    for pool in ("A", "B"):
        for task, group in selected.items():
            records = [
                row
                for row in mappings
                if row["pool"] == pool and row["task_id"] == task and row["role"] == "train"
            ]
            by_state = defaultdict(list)
            for item in records:
                if item["status"] == "MAPPED":
                    by_state[item["state_id"]].append(item)
            denominator = 8 if group == "control" else 16
            support = []
            for state_id, items in sorted(by_state.items()):
                require(
                    len({row["actual_method"] for row in items}) == 1,
                    "state_catalog.no_actual_method_merge",
                )
                support.append(
                    {
                        "state_id": state_id,
                        "actual_method": items[0]["actual_method"],
                        "n_train": len(items),
                        "pi0": str(Fraction(len(items), denominator)),
                        "r": str(Fraction(len(items), denominator)),
                        "train_package_ids": [row["package_id"] for row in items],
                    }
                )
            supports.append(
                {
                    "pool": pool,
                    "task_id": task,
                    "group": group,
                    "states": support,
                    "train_pending": sum(row["status"] != "MAPPED" for row in records),
                }
            )
    pending_train = sum(row["status"] != "MAPPED" and row["role"] == "train" for row in mappings)
    return record(
        "behavior_state_catalog",
        mapper_policy_id=policy()["id"],
        original_material_manifest_id=manifest["id"],
        original_material_sha256=sha(encode(manifest)),
        original_package_descriptors=copy.deepcopy(manifest["packages"]),
        package_mappings=mappings,
        task_support=supports,
        canonical_states=states,
        status="READY_STATE_TRAIN_SUPPORT" if not pending_train else "PENDING_TRAIN_STATE_MAPPING",
        train_pending_count=pending_train,
        heldout_pending_count=sum(
            row["status"] != "MAPPED" and row["role"] == "heldout" for row in mappings
        ),
        heldout_mapping_required_for_train=False,
        original_package_count=len(mappings),
        dropped_original_packages=0,
        old_signatures_modified=False,
        prior_is_initial_pushforward=True,
        real_Qwen_training_performed=False,
    )


def validate_state_support(catalog):
    checked_record(catalog, "behavior_state_catalog")
    descriptors = catalog["original_package_descriptors"]
    mappings = catalog["package_mappings"]
    require(
        len(descriptors) == len(mappings) == catalog["original_package_count"],
        "state_catalog.exact_original_mapping_denominator",
    )
    for descriptor, mapping in zip(descriptors, mappings, strict=True):
        require(
            mapping["package_id"] == descriptor["id"]
            and mapping["descriptor"] == descriptor
            and all(
                mapping[key] == descriptor[key]
                for key in ("task_id", "pool", "role", "actual_method")
            ),
            "state_catalog.no_package_metadata_substitution",
        )
    expected_keys = {(row["pool"], row["task_id"]) for row in descriptors}
    require(
        len(catalog["task_support"]) == len(expected_keys)
        and {(row["pool"], row["task_id"]) for row in catalog["task_support"]} == expected_keys,
        "state_catalog.exact_pool_task_supports",
    )
    for support in catalog["task_support"]:
        train = [
            row
            for row in mappings
            if row["pool"] == support["pool"]
            and row["task_id"] == support["task_id"]
            and row["role"] == "train"
        ]
        denominator = 8 if support["group"] == "control" else 16
        require(
            len(train) == denominator
            and support["train_pending"] == sum(row["status"] != "MAPPED" for row in train),
            "state_catalog.original_training_count_with_pending_retained",
        )
        counts = Counter(row["state_id"] for row in train if row["status"] == "MAPPED")
        require(
            len(support["states"]) == len(counts)
            and {row["state_id"] for row in support["states"]} == set(counts),
            "state_catalog.no_heldout_or_unsupported_train_state",
        )
        for state in support["states"]:
            members = [
                row
                for row in train
                if row["status"] == "MAPPED" and row["state_id"] == state["state_id"]
            ]
            require(
                state["n_train"] == counts[state["state_id"]]
                and Fraction(state["pi0"])
                == Fraction(state["r"])
                == Fraction(len(members), denominator)
                and state["train_package_ids"] == [row["package_id"] for row in members]
                and all(row["actual_method"] == state["actual_method"] for row in members),
                "state_catalog.exact_initial_pushforward_not_method_merge",
            )
    pending = sum(row["status"] != "MAPPED" and row["role"] == "train" for row in mappings)
    require(
        catalog["train_pending_count"] == pending
        and catalog["status"]
        == ("PENDING_TRAIN_STATE_MAPPING" if pending else "READY_STATE_TRAIN_SUPPORT"),
        "state_catalog.no_forced_unknown_train_admission",
    )
    return catalog


def build_from_parents(root, material_parent, collection_parent):
    """Explicit future input boundary: read complete sealed original parents only.

    This loader is not called during synthetic development. It reads the exact
    selected 8+2 originals, not any prefix of a running collection. A broken
    parent/member hash is an input-integrity error, never an excuse to omit a
    heldout or training package. Semantic uncertainty is retained by the mapper.
    """
    root = Path(root).resolve()
    manifest = material_parent.read("material_manifest.json")
    validate_original_manifest(manifest)
    collected = collection_parent.read("report.json")
    materials.checked_record(collected, "fixed_collection_report")
    require(
        collected["status"] == "COMPLETE_FIXED_COLLECTION"
        and collected["collection_complete"] is True
        and manifest["collection_id"] == collected["id"]
        and manifest["all_original_registered_denominators"]
        == collected["registered_session_count"],
        "state_catalog.closed_original_collection_and_material_parent",
    )
    evidence = {}
    for descriptor in manifest["packages"]:
        path = root / descriptor["path"]
        require(
            path.is_relative_to(material_parent.directory),
            "state_catalog.original_material_parent_member",
        )
        encoded_member = str(path.relative_to(material_parent.directory))
        raw_member = str(Path(encoded_member).with_name("raw_package.json"))
        session_prefix = "sessions/" + descriptor["registered_session_id"] + "/"
        encoded = material_parent.read(encoded_member)
        raw = material_parent.read(raw_member)
        session = collection_parent.read(session_prefix + "session.json")
        qualification = collection_parent.read(session_prefix + "qualification.json")
        references = []
        for parent, member, role in [
            (material_parent, encoded_member, "original_encoded_package"),
            (material_parent, raw_member, "original_raw_package"),
            (collection_parent, session_prefix + "session.json", "original_session"),
            (collection_parent, session_prefix + "qualification.json", "original_qualification"),
        ]:
            references.append(
                {
                    "role": role,
                    "parent_manifest_id": parent.manifest["id"],
                    "parent_directory": parent.relative,
                    "member": member,
                    **parent.members[member],
                }
            )
        evidence[descriptor["id"]] = {
            "encoded_package": encoded,
            "raw_package": raw,
            "session": session,
            "qualification": qualification,
            "references": references,
        }
    catalog = build_catalog(manifest, evidence)
    validate_catalog(catalog, manifest, require_ready=False)
    material_parent.check_manifest()
    collection_parent.check_manifest()
    return catalog


def validate_catalog(catalog, manifest, *, require_ready=True):
    checked_record(catalog, "behavior_state_catalog")
    validate_original_manifest(manifest)
    validate_state_support(catalog)
    require(
        catalog["original_material_manifest_id"] == manifest["id"]
        and catalog["original_material_sha256"] == sha(encode(manifest))
        and catalog["original_package_descriptors"] == manifest["packages"]
        and [row["package_id"] for row in catalog["package_mappings"]]
        == [row["id"] for row in manifest["packages"]],
        "state_catalog.no_deleted_changed_or_reordered_original_packages",
    )
    require(
        catalog["mapper_policy_id"] == policy()["id"] and catalog["dropped_original_packages"] == 0,
        "state_catalog.frozen_mapper_no_drops",
    )
    if require_ready:
        require(
            catalog["status"] == "READY_STATE_TRAIN_SUPPORT"
            and catalog["train_pending_count"] == 0
            and all(
                row["status"] == "MAPPED"
                for row in catalog["package_mappings"]
                if row["role"] == "train"
            ),
            "state_catalog.every_original_training_package_mapped",
        )
    for row in catalog["package_mappings"]:
        if row["status"] == "MAPPED":
            mapping = row["mapping"]
            checked_record(mapping, "original_package_state_mapping")
            canonical = canonicalize_dag(mapping["semantic_DAG"])
            require(
                canonical["state_id"] == row["state_id"] == mapping["state_id"]
                and canonical["canonical_graph"] == catalog["canonical_states"][row["state_id"]]
                and mapping["actual_method"] == row["actual_method"],
                "state_catalog.actual_semantic_state_identity",
            )
    return catalog
