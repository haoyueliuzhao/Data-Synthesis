"""Task-specific, read-only method probes and executed Claim dependency accounting."""

import json

from trusted_synthesis.domains.finance.qa_vnext.protocol import require
from trusted_synthesis.experiments.finance_qa_vnext_finqa_difficulty.semantics import (
    equivalent,
    lineage,
)
from trusted_synthesis.experiments.finance_qa_vnext_finqa_final_recovery.runtime import TARGET_ERROR

from .plan import probes as method_probes


def recovery_trace(events, requests, result, task):
    require(task["key"] in {"J1", "J2"}, "binding_metrics.two_registered_tasks")
    target = task["target"]
    probes = method_probes(task)

    def eq(a, b):
        return equivalent(a, b, task["facts"], task["relations"])

    def canonical(tree):
        return json.dumps(tree, sort_keys=True, separators=(",", ":"))

    operations, finals, observations, claim_graph = [], [], {}, {}
    prior_trees, known_bad, trigger_indices = [], [], []
    first_trigger, final_claim = None, None
    for event, request in zip(events, requests, strict=True):
        model = event["model_submission"] or {}
        index = event["submission_count"]
        after_trigger = first_trigger is not None and index > first_trigger
        claims = {c["id"]: c for c in request["state"]["claims"]}
        if model.get("kind") == "action":
            obs = event["observation"] if event["admitted"] else None
            tree = obs["expression"] if obs else None
            row = {
                "submission": index,
                "after_first_target_rejection": after_trigger,
                "admitted": event["admitted"],
                "error": event["error"],
                "operation": model["operation"],
                "inputs": model["inputs"],
                "reason": model["reason"],
                "subgoal": model["subgoal"],
                "observation_id": obs["id"] if obs else None,
                "expression": tree,
                "exact_value": obs["exact_value"] if obs else None,
                "value": obs["value"] if obs else None,
                "lineage": obs["lineage"] if obs else None,
                "input_claim_ids": [ref for ref in model["inputs"] if ref in claims],
                "new_expanded_expression": bool(obs)
                and all(canonical(tree) != canonical(t) for t in prior_trees),
                "new_symbolic_expression": bool(obs) and not any(eq(tree, t) for t in prior_trees),
                "related_source_lineage": bool(obs) and bool(lineage(tree) & lineage(target)),
                "method_probe_matches": [
                    key for key, probe in probes.items() if obs and eq(tree, probe)
                ],
                "resolution": "unresolved" if obs else "no_observation",
                "accepted_claim_id": None,
                "resolved_at_submission": None,
                "consumed_by_valid_final": False,
            }
            operations.append(row)
            if obs:
                observations[obs["id"]] = row
                prior_trees.append(tree)
        elif model.get("kind") == "update" and event["admitted"]:
            row = observations[model["observation"]]
            row["resolution"] = model["disposition"]
            row["resolved_at_submission"] = index
            if event["claim"]:
                claim_id = event["claim"]["id"]
                row["accepted_claim_id"] = claim_id
                claim_graph[claim_id] = row["input_claim_ids"]
        elif model.get("kind") == "final":
            claim = claims.get(model["answer_claim"])
            tree = claim["expression"] if claim else None
            row = {
                "submission": index,
                "after_first_target_rejection": after_trigger,
                "raw_submission": model,
                "admitted": event["admitted"],
                "error": event["error"],
                "answer_claim_id": model["answer_claim"],
                "expression": tree,
                "exact_value": claim["exact_value"] if claim else None,
                "reuses_previously_target_rejected_claim": any(
                    b["answer_claim_id"] == model["answer_claim"] for b in known_bad
                ),
                "reuses_previously_target_rejected_expanded_expression": bool(claim)
                and any(canonical(tree) == canonical(b["expression"]) for b in known_bad),
                "reuses_previously_target_rejected_symbolic_expression": bool(claim)
                and any(eq(tree, b["expression"]) for b in known_bad),
            }
            finals.append(row)
            if event["error"] == TARGET_ERROR:
                require(claim is not None, "recovery.target_rejected_claim_exists")
                trigger_indices.append(index)
                if first_trigger is None:
                    first_trigger = index
                known_bad.append(row)
            if event["admitted"]:
                final_claim = model["answer_claim"]
    ancestry = set()

    def visit(claim_id):
        if claim_id in ancestry:
            return
        require(claim_id in claim_graph, "recovery.executed_claim_graph")
        ancestry.add(claim_id)
        for dependency in claim_graph[claim_id]:
            visit(dependency)

    if final_claim:
        visit(final_claim)
    for row in operations:
        row["consumed_by_valid_final"] = row["accepted_claim_id"] in ancestry
    post = [r for r in operations if r["after_first_target_rejection"]]
    aligned = [r for r in operations if r["method_probe_matches"]]
    fresh = [
        r
        for r in aligned
        if r["after_first_target_rejection"]
        and r["new_symbolic_expression"]
        and r["consumed_by_valid_final"]
    ]

    def first(rows):
        return rows[0]["submission"] if rows else None

    return {
        "triggered": first_trigger is not None,
        "recovery_status": "NOT_APPLICABLE"
        if first_trigger is None
        else "COMPLETE_RECOVERY"
        if result["terminal"]
        else "NOT_COMPLETED",
        "first_target_rejection_submission": first_trigger,
        "first_target_rejection": known_bad[0] if known_bad else None,
        "target_rejection_submissions": trigger_indices,
        "repeat_target_rejections_after_first": max(0, len(trigger_indices) - 1),
        "first_post_trigger_action_proposal": first(post),
        "first_post_trigger_executed_operation": first([r for r in post if r["admitted"]]),
        "first_new_related_executed_operation": first(
            [
                r
                for r in post
                if r["admitted"] and r["new_symbolic_expression"] and r["related_source_lineage"]
            ]
        ),
        "post_trigger_model_submissions": len(
            [
                e
                for e in events
                if first_trigger is not None and e["submission_count"] > first_trigger
            ]
        ),
        "old_bad_claim_reuse_submissions": [
            r["submission"] for r in finals if r["reuses_previously_target_rejected_claim"]
        ],
        "bad_expression_reuse_submissions": [
            r["submission"]
            for r in finals
            if r["reuses_previously_target_rejected_symbolic_expression"]
        ],
        "method_matched_operations": aligned,
        "fresh_method_accepted_consumed_operations": fresh,
        "fresh_dependency_recovery_witness": bool(
            first_trigger is not None and result["terminal"] and fresh
        ),
        "valid_final_actual_claim_ancestry": sorted(ancestry),
        "operations": operations,
        "final_attempts": finals,
        "probes_are_posthoc_not_action_admission": True,
        "reason_text_is_not_recovery_evidence": True,
    }
