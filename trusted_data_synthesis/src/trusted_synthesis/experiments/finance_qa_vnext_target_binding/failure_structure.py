"""Mechanical intersections of saved old judgments, never new grading."""

from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path

from .core import (
    OLD,
    STATUSES,
    read_json,
    record,
    reference,
    require,
    require_frozen_ledger,
    seal,
)

DIMENSIONS = ("quantity", "formula", "source", "unit", "publication", "execution", "Final")
SEMANTIC = {
    "formula": "formula_applicability",
    "source": "variable_correspondence",
    "unit": "unit_handling",
    "publication": "publication_alignment",
}
TECHNICAL = (
    "first_three_have_pre_or_same_call_evidence",
    "calculation_quantity_interpretation_established",
    "selected_tool_result_matches_publication",
    "explicit_Final_result_reference_consistent",
)


def vector(row):
    q, review = row["qualification"], row["semantic_review"]
    values = {"quantity": q["task_answer_status"]}
    values.update({name: review[field]["status"] for name, field in SEMANTIC.items()})
    values["execution"] = "PASS" if row["actual_calculations"] > 0 else "FAIL"
    consistency = review["final_answer_consistency"]["status"]
    delivered = q["delivery_status"] == "FINAL_DELIVERED"
    # Preserve the old consistency unknown. Missing delivery must not become PASS.
    values["Final"] = consistency if delivered or consistency != "PASS" else "NOT_ESTABLISHED"
    require(all(s in STATUSES for s in values.values()), "failure.saved_status_vocabulary")
    require(
        type(row["actual_calculations"]) is int and row["actual_calculations"] >= 0,
        "failure.actual_calculation_count",
    )
    technical = {key: q["trace_checks"][key] for key in TECHNICAL}
    require(all(type(v) is bool for v in technical.values()), "failure.saved_boolean_gates")
    selected = q["original_calculation_quantity"]["call_id"]
    remaining = {
        **technical,
        "selected_successful_calculation_recorded": selected is not None
        and row["actual_calculations"] > 0,
        "actual_Final_delivered": delivered,
        "actual_Final_amount_check_PASS": q["actual_Final_amount_consistency"]["status"] == "PASS",
    }
    projected = all(v == "PASS" for v in values.values()) and all(remaining.values())
    # A consistency check over saved booleans, not a call to any financial qualifier.
    require(
        projected == q["complete_verifiable_trajectory"],
        "failure.saved_gate_projection_consistency",
    )
    failed = [name for name in DIMENSIONS if values[name] == "FAIL"]
    unknown = [name for name in DIMENSIONS if values[name] not in {"PASS", "FAIL"}]
    nonpass = [name for name in DIMENSIONS if values[name] != "PASS"]
    category = (
        "INFORMATION_INSUFFICIENT"
        if unknown
        else "ALL_SEVEN_PASS"
        if not failed
        else "ONLY_ONE_FAIL"
        if len(failed) == 1
        else "MULTIPLE_FAIL"
    )
    return record(
        "saved_failure_vector",
        phase=row["phase"],
        task_key=row["task_key"],
        variant=row["variant"],
        arm=row["variant"].rsplit("_", 1)[0],
        seed=int(row["variant"].rsplit("_", 1)[1]),
        group=row["group"],
        original_review_id=row["review_id"],
        original_row_id=row["id"],
        original_qualification_id=q["id"],
        conditions=values,
        failed_conditions=failed,
        unknown_conditions=unknown,
        nonPASS_conditions=nonpass,
        exclusive_category=category,
        original_Final_consistency_status=consistency,
        original_Final_delivery_status=q["delivery_status"],
        actual_successful_calculation_count=row["actual_calculations"],
        old_model_requests=row["model_requests"],
        old_tool_calls=row["tool_calls"],
        saved_remaining_gates=remaining,
        original_complete_trajectory_PASS=q["complete_verifiable_trajectory"],
        original_trace_status=q["trace_status"],
        saved_gate_projection_matches_original=True,
        new_semantic_judgments=0,
        successor_policy_or_local_case_revision_used=False,
    )


def summarize(rows):
    patterns = defaultdict(list)
    for row in rows:
        patterns[tuple(row["conditions"][d] for d in DIMENSIONS)].append(row)
    single = {
        name: dict(
            Counter(row["conditions"][name] for row in rows if row["nonPASS_conditions"] == [name])
        )
        for name in DIMENSIONS
    }
    return {
        "registered_sessions": len(rows),
        "unique_tasks": len({row["task_key"] for row in rows}),
        "original_complete_trajectory_PASS": sum(
            row["original_complete_trajectory_PASS"] for row in rows
        ),
        "old_model_requests": sum(row["old_model_requests"] for row in rows),
        "old_tool_calls": sum(row["old_tool_calls"] for row in rows),
        "sessions_with_more_than_one_tool_call": sum(row["old_tool_calls"] > 1 for row in rows),
        "exclusive_categories": dict(Counter(row["exclusive_category"] for row in rows)),
        "information_insufficient_with_known_FAIL": sum(
            bool(row["unknown_conditions"]) and bool(row["failed_conditions"]) for row in rows
        ),
        "marginal_status_counts": {
            d: dict(Counter(row["conditions"][d] for row in rows)) for d in DIMENSIONS
        },
        "exactly_one_nonPASS_by_condition_and_status": single,
        "at_least_two_nonPASS_including_unknowns": sum(
            len(row["nonPASS_conditions"]) >= 2 for row in rows
        ),
        "all_seven_PASS_but_remaining_gate_not_PASS": sum(
            not row["nonPASS_conditions"] and not row["original_complete_trajectory_PASS"]
            for row in rows
        ),
        "remaining_gate_false_counts": {
            name: sum(not row["saved_remaining_gates"][name] for row in rows)
            for name in rows[0]["saved_remaining_gates"]
        }
        if rows
        else {},
        "pairwise_nonPASS_intersections_not_causal": {
            a + "+" + b: sum(
                a in r["nonPASS_conditions"] and b in r["nonPASS_conditions"] for r in rows
            )
            for a, b in combinations(DIMENSIONS, 2)
        },
        "exact_joint_patterns": [
            {
                "conditions": dict(zip(DIMENSIONS, pattern, strict=True)),
                "count": len(group),
                "original_complete_trajectory_PASS": sum(
                    r["original_complete_trajectory_PASS"] for r in group
                ),
                "sessions": [r["phase"] + "/" + r["task_key"] + "/" + r["variant"] for r in group],
            }
            for pattern, group in sorted(patterns.items())
        ],
    }


def grouped(rows, fields):
    groups = defaultdict(list)
    for row in rows:
        groups["/".join(str(row[field]) for field in fields)].append(row)
    return {name: summarize(group) for name, group in sorted(groups.items())}


def build(root, guard):
    root = Path(root).resolve()
    ledger, manifest = require_frozen_ledger(root)
    rows, refs, saved_utilities = [], [], {}
    for phase, expected in (("dev", 108), ("confirm", 144)):
        path = OLD + f"/reviewed/{phase}/report.json"
        source = read_json(root / path)
        require(len(source["rows"]) == expected, "failure.exact_original_denominator")
        require(source["registered_sessions"] == expected, "failure.registered_denominator")
        refs.append(reference(root, path))
        saved_utilities[phase] = {k: v["utility"] for k, v in source["by_variant"].items()}
        rows.extend(vector(row) for row in source["rows"])
    require(len(rows) == 252, "failure.exact_252_once")
    require(
        len({(r["phase"], r["task_key"], r["variant"]) for r in rows}) == 252,
        "failure.no_duplicate_sessions",
    )
    report = record(
        "saved_failure_structure",
        target_ledger_id=ledger["id"],
        target_ledger_manifest_id=manifest["id"],
        original_reports=refs,
        dimensions=list(DIMENSIONS),
        dimension_definition={
            "quantity": (
                "Original task_answer_status including original secondary/Final-amount checks."
            ),
            **{
                name: "Original semantic_review." + field + ".status."
                for name, field in SEMANTIC.items()
            },
            "execution": (
                "Observed existence of at least one successful calculate: PAS"
                "S if present, FAIL if absent. No claim about why absent."
            ),
            "Final": (
                "Original final_answer_consistency, additionally forbidding P"
                "ASS when no actual Final was delivered. Raw consistency and "
                "delivery stay separate."
            ),
        },
        category_definition={
            "ALL_SEVEN_PASS": (
                "All seven displayed conditions PASS; remaining technical gat"
                "es are retained separately."
            ),
            "ONLY_ONE_FAIL": "Exactly one FAIL and no unknown condition.",
            "MULTIPLE_FAIL": "At least two FAIL conditions and no unknown condition.",
            "INFORMATION_INSUFFICIENT": (
                "At least one original unknown/NOT_ESTABLISHED condition; kno"
                "wn FAIL intersections remain recorded."
            ),
        },
        all_sessions=summarize(rows),
        by_phase=grouped(rows, ("phase",)),
        by_phase_arm=grouped(rows, ("phase", "arm")),
        by_phase_variant=grouped(rows, ("phase", "variant")),
        by_phase_seed=grouped(rows, ("phase", "seed")),
        by_phase_task=grouped(rows, ("phase", "task_key")),
        by_phase_arm_group=grouped(rows, ("phase", "arm", "group")),
        original_by_variant_utility_strings=saved_utilities,
        all_1260_original_semantic_judgments_reused_without_regrading=True,
        local_18_new_judgments_used=False,
        no_new_primary_score_or_candidate_selection=True,
        not_a_model_repair_effect_or_causal_mediation_analysis=True,
        repeated_tasks_and_seeds_not_independent=True,
        guard=guard.receipt(),
    )
    payloads = {
        "report.json": report,
        "vectors.json": record("all_saved_failure_vectors", rows=rows),
    }
    sealed = seal(root, "failure_structure", payloads)
    return {
        "id": report["id"],
        "manifest_id": sealed["id"],
        "counts": report["all_sessions"]["exclusive_categories"],
    }
