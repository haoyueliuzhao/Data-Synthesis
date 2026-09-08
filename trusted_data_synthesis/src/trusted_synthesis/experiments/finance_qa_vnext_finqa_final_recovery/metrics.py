"""Posthoc E1 recovery measurements; never consulted by the model or admission."""

import json
from collections import Counter

from trusted_synthesis.domains.finance.qa_vnext.protocol import require
from trusted_synthesis.experiments.finance_qa_vnext_finqa_difficulty.semantics import (
    equivalent,
    lineage,
)
from trusted_synthesis.experiments.finance_qa_vnext_finqa_reference_diagnostic.metrics import (
    aggregate_observations,
)

from .runtime import TARGET_ERROR


def recovery_trace(events, requests, result, task):
    require(task["key"] == "E1", "recovery.only_E1")
    target = task["target"]
    # Posthoc source-symbolic probes include both conversion directions, a normalized
    # ratio, and the full percent. They do not prescribe action order or input IDs.
    numerator, converted_denominator = target["args"][0]["args"]
    scale = converted_denominator["args"][1]
    probes = {
        "denominator_in_numerator_scale": converted_denominator,
        "numerator_in_denominator_scale": {"op": "multiply", "args": [numerator, scale]},
        "normalized_ratio": target["args"][0],
        "complete_percent_target": target,
    }

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
                "scale_alignment_probes": [
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
    aligned = [r for r in operations if r["scale_alignment_probes"]]
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
        "scale_aligned_operations": aligned,
        "fresh_aligned_accepted_consumed_operations": fresh,
        "fresh_dependency_recovery_witness": bool(
            first_trigger is not None and result["terminal"] and fresh
        ),
        "valid_final_actual_claim_ancestry": sorted(ancestry),
        "operations": operations,
        "final_attempts": finals,
        "probes_are_posthoc_not_action_admission": True,
        "reason_text_is_not_recovery_evidence": True,
    }


def aggregate(rows):
    """Keep full registered denominator, and separately the actually observed triggers."""
    audited = all("recovery_trace" in r for r in rows)
    usage_keys = sorted({key for r in rows for key in r.get("usage", {})})
    triggers = [r for r in rows if r.get("recovery_trace", {}).get("triggered")]
    return {
        "denominator": len(rows),
        "complete_valid": sum(r["complete_valid"] for r in rows),
        "statuses": dict(Counter(r["status"] for r in rows)),
        "triggered_sessions": len(triggers) if audited else None,
        "complete_recoveries": sum(r["complete_valid"] for r in triggers) if audited else None,
        "fresh_dependency_recovery_witnesses": sum(
            r["recovery_trace"]["fresh_dependency_recovery_witness"] for r in triggers
        )
        if audited
        else None,
        "recovery_not_applicable": len(rows) - len(triggers) if audited else None,
        "repeat_target_rejections": sum(
            r["recovery_trace"]["repeat_target_rejections_after_first"] for r in triggers
        )
        if audited
        else None,
        **{
            field: sum(r[field] for r in rows) if all(field in r for r in rows) else None
            for field in ("actions", "submissions", "provider_attempts", "review_http_exposures")
        },
        "usage": {
            key: {
                "total": sum(r["usage"][key]["total"] for r in rows)
                if all(r.get("usage", {}).get(key, {}).get("total") is not None for r in rows)
                else None,
                "observed_subtotal": sum(
                    r.get("usage", {}).get(key, {}).get("observed_subtotal", 0) for r in rows
                ),
                "unknown_attempts": sum(
                    r.get("usage", {}).get(key, {}).get("unknown_attempts", 0) for r in rows
                ),
                "missing_session_audits": sum(key not in r.get("usage", {}) for r in rows),
            }
            for key in usage_keys
        },
        "observations": aggregate_observations(
            [e for r in rows for e in r["observation_diagnostics"]["events"]]
        )
        if all("observation_diagnostics" in r for r in rows)
        else None,
    }
