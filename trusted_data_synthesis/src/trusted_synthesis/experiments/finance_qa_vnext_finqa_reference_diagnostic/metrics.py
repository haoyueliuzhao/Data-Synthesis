"""Read-only event measures: legal reject counts, absent decisions never disappear."""

from collections import Counter

from trusted_synthesis.domains.finance.qa_vnext.protocol import require
from trusted_synthesis.experiments.finance_qa_vnext_finqa_difficulty.reference_revision import (
    REFERENCE_RULE,
)
from trusted_synthesis.experiments.finance_qa_vnext_finqa_difficulty.semantics import equivalent

REFERENCE_ERROR = "lifecycle.observation_binding"
FOCUS = {
    "E1": "scale_alignment",
    "M3": "period_set",
    "J1": "after_tax_definition",
    "J2": "period_input_pairing",
}


def verify_public_reference(request):
    prop = request["response_schemas"]["update"]["properties"]["observation"]
    require(prop["description"] == REFERENCE_RULE, "audit.v21_description")
    require(request["rules"]["update_reference"] == REFERENCE_RULE, "audit.v21_rule")
    pending = request["state"]["pending_observation"]
    require(
        prop.get("const") == (pending["id"] if pending else None),
        "audit.v21_exact_pending_const",
    )


def aggregate_observations(rows):
    counts = Counter()
    for row in rows:
        counts["total_observations"] += 1
        if row["first_decision"] is None:
            counts["no_following_submission"] += 1
        else:
            counts["with_first_decision"] += 1
            counts[row["first_decision"]["classification"]] += 1
        counts["reference_rejections"] += len(row["reference_rejection_submissions"])
        counts["resolved_" + row["resolution"]] += 1
        counts["budget_exhausted_on_pending"] += row["budget_exhausted_on_pending"]
    for key in (
        "total_observations",
        "with_first_decision",
        "no_following_submission",
        "first_legal_accept",
        "first_legal_reject",
        "first_illegal",
        "reference_rejections",
        "resolved_accept",
        "resolved_reject",
        "resolved_unresolved",
        "budget_exhausted_on_pending",
    ):
        counts.setdefault(key, 0)
    legal = counts["first_legal_accept"] + counts["first_legal_reject"]
    observed = counts["with_first_decision"]
    require(
        observed + counts["no_following_submission"] == counts["total_observations"]
        and legal + counts["first_illegal"] == observed,
        "metrics.observation_denominator",
    )
    return {
        **dict(counts),
        "first_legal_update_rate_among_observed": legal / observed if observed else None,
        "maximum_consecutive_reference_rejections": max(
            (max((len(run) for run in row["reference_rejection_runs"]), default=0) for row in rows),
            default=0,
        ),
        "observation_events_are_not_independent_task_samples": True,
    }


def observation_diagnostics(events, requests, result):
    rows = {}
    for event, request in zip(events, requests, strict=True):
        model = event["model_submission"] or {}
        pending = request["state"]["pending_observation"]
        index = event["submission_count"]  # one-based actual model submission
        if pending:
            row = rows[pending["id"]]
            legal = (
                event["admitted"]
                and model.get("kind") == "update"
                and model.get("observation") == pending["id"]
                and model.get("disposition") in {"accept", "reject"}
            )
            if row["first_decision"] is None:
                row["first_decision"] = {
                    "submission": index,
                    "classification": (
                        "first_legal_" + model["disposition"] if legal else "first_illegal"
                    ),
                    "error": event["error"],
                    "submitted_kind": model.get("kind"),
                    "submitted_observation": model.get("observation"),
                }
            row["pending_submissions"].append(index)
            if event["error"] == REFERENCE_ERROR:
                refs = row["reference_rejection_submissions"]
                runs = row["reference_rejection_runs"]
                if not refs or refs[-1] != index - 1:
                    runs.append([])
                refs.append(index)
                runs[-1].append(index)
            if legal:
                row["resolution"] = model["disposition"]
                row["resolved_at_submission"] = index
        if event["admitted"] and model.get("kind") == "action":
            obs = event["observation"]
            require(obs["id"] not in rows, "metrics.duplicate_observation")
            rows[obs["id"]] = {
                "observation_id": obs["id"],
                "created_at_submission": index,
                "operation": model["operation"],
                "first_decision": None,
                "pending_submissions": [],
                "reference_rejection_submissions": [],
                "reference_rejection_runs": [],
                "resolution": "unresolved",
                "resolved_at_submission": None,
                "budget_exhausted_on_pending": False,
            }
    pending = result["final_state"]["pending_observation"]
    if pending:
        rows[pending["id"]]["budget_exhausted_on_pending"] = result["status"] == "budget_exhausted"
    observations = list(rows.values())
    require(len(observations) == result["actions"], "metrics.every_actual_observation")
    return {"events": observations, "summary": aggregate_observations(observations)}


def financial_trace(events, requests, result, task):
    """Reached is an inspection opportunity, never a semantic correctness label.

    E1: arithmetic combining two selected facts or scaling one with a constant.
    M3: sum/average/divide combining at least two selected revenue facts.
    J1: arithmetic combining at least two selected cost/tax facts.
    J2: multiply combining at least two selected quantity/price facts.
    Intermediate expressions are not judged against Final as if they were answers.
    """
    actions, final_attempts, reached = [], [], []
    key = task["key"]
    for event, request in zip(events, requests, strict=True):
        model = event["model_submission"] or {}
        if event["admitted"] and model.get("kind") == "action":
            obs = event["observation"]
            row = {
                "submission": event["submission_count"],
                "operation": model["operation"],
                "inputs": model["inputs"],
                "subgoal": model["subgoal"],
                "reason": model["reason"],
                "observation_id": obs["id"],
                "value": obs["value"],
                "exact_value": obs["exact_value"],
                "expression": obs["expression"],
                "lineage": obs["lineage"],
            }
            actions.append(row)
            op = model["operation"]
            selected = set(obs["lineage"]) & set(task["selected"])
            inspectable = (
                key == "E1"
                and op != "read"
                and (
                    len(selected) >= 2
                    or (
                        selected
                        and op in {"multiply", "divide"}
                        and any(i.startswith("constant:") for i in model["inputs"])
                    )
                )
                or key == "M3"
                and op in {"sum", "average", "divide"}
                and len(selected) >= 2
                or key == "J1"
                and op != "read"
                and len(selected) >= 2
                or key == "J2"
                and op == "multiply"
                and len(selected) >= 2
            )
            if inspectable:
                reached.append(event["submission_count"])
        if model.get("kind") == "final":
            claim = next(
                (c for c in request["state"]["claims"] if c["id"] == model.get("answer_claim")),
                None,
            )
            final_attempts.append(
                {
                    "submission": event["submission_count"],
                    "submission_content": model,
                    "admitted": event["admitted"],
                    "error": event["error"],
                    "answer_expression": claim["expression"] if claim else None,
                    "target_equivalent": equivalent(
                        claim["expression"], task["target"], task["facts"], task["relations"]
                    )
                    if claim
                    else None,
                }
            )
    return {
        "focus": FOCUS.get(key),
        "inspection_status": (
            "REACHED" if reached else "NOT_REACHED" if key in FOCUS else "NOT_FOCUS_TASK"
        ),
        "inspectable_action_submissions": reached,
        "executed_actions": actions,
        "final_attempts": final_attempts,
        "final_state": result["final_state"],
        "termination": result["termination"],
        "substantive_error_automatically_inferred": False,
        "off_reference_source_membership_is_not_an_error_label": True,
    }
