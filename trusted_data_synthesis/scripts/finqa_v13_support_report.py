"""Read-only final V13 support accounting; never repair or rerun the experiment.

Print one deterministic JSON record. The caller may archive it separately from
the immutable production artifacts; no files, API calls or GPU work are written.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

from trusted_synthesis.finance_research.contracts import digest

DEFAULT_ROOT = Path(
    "/data1/zhuxinrui/projects/Data-Synthesis/trusted_data_synthesis/artifacts/"
    "finance_research_20260928/finqa_v6_01/v13_material_02"
)


def read_source(root, relative, schema):
    path = root / relative
    raw = path.read_bytes()
    value = json.loads(raw)
    if value.get("schema") != schema or value.get("id") != digest(
        {k: v for k, v in value.items() if k != "id"}
    ):
        raise ValueError("sealed source identity changed: " + str(path))
    return value, dict(path=str(path), id=value["id"], sha256=hashlib.sha256(raw).hexdigest())


def summarize(root=DEFAULT_ROOT):
    root = Path(root).resolve()
    support, support_ref = read_source(
        root, "material/support/record.json", "v13_conditional_support_manifest.v1"
    )
    result, result_ref = read_source(
        root, "material/result/record.json", "v13_material_freeze_result.v1"
    )
    seal, seal_ref = read_source(
        root, "completion_seal/record.json", "v13_material_completion_seal.v1"
    )
    if (
        result["support"] != support_ref
        or result["protocol_id"] != seal["protocol_id"]
        or result["registration_id"] != seal["registration_id"]
        or support["N"] != seal["fixed_common_tasks"]
        or support["package_count"] != seal["fixed_common_candidate_packages"]
    ):
        raise ValueError("material/support/completion belong to different frozen runs")
    profile, resolved = support["capability_profile"], support["task_support"]
    blockers = Counter(b["reason"] for b in profile["blockers"])
    encoding_reasons = Counter(
        failure["reason"]
        for blocker in profile["blockers"]
        if blocker["reason"] == "fixed_original_encoding_unresolved"
        for failure in blocker["failures"]
    )
    coverage = profile["package_reason_coverage"]
    inherited = support["package_count"] - seal["purpose_expected"]["projection"]
    singleton_count = sum(row["deterministic_singleton"] for row in resolved.values())
    projection_known = sum(v["approved_characters"] is not None for v in coverage.values())
    if (
        singleton_count != len(support["registered_singleton_tasks"])
        or singleton_count != seal["deterministic_singleton_tasks"]
        or len(resolved) != singleton_count + seal["mapping_complete_calls"]
        or support["N"] - len(resolved) != blockers["whole_task_mapping_unresolved"]
        or projection_known != inherited + seal["projection_usable_calls"]
        or support["package_count"] - projection_known
        != blockers["predeclared_projection_unresolved"]
    ):
        raise ValueError("fixed-denominator support accounting differs between sealed records")
    body = dict(
        schema="v13_final_support_analysis.v1",
        material_root=str(root),
        protocol_id=result["protocol_id"],
        registration_id=result["registration_id"],
        source_records=dict(support=support_ref, result=result_ref, completion_seal=seal_ref),
        report_script=dict(
            repository_path="trusted_data_synthesis/scripts/finqa_v13_support_report.py",
            sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        ),
        phase=result["phase"],
        fixed_population=dict(tasks=support["N"], packages=support["package_count"]),
        calls=dict(
            registered=seal["expected_calls"],
            authentic_terminals=len(seal["terminals"]),
            returned=seal["actual_returns"],
            network_unknown=seal["network_unknowns"],
            returns_by_purpose=seal["actual_returns_by_purpose"],
            failures_by_purpose=seal["failures"],
            all_registered_jobs_terminal=seal["all_registered_jobs_have_authentic_terminals"],
            all_model_responses_returned=seal["all_model_responses_returned"],
        ),
        projection=dict(
            inherited_original_V12_usable=inherited,
            new_registered_calls=seal["purpose_expected"]["projection"],
            new_usable=seal["projection_usable_calls"],
            total_known_usable=projection_known,
            missing=support["package_count"] - projection_known,
            failed_projection_does_not_invalidate_original_process=True,
            known_zero_positive_reason_character_packages=sum(
                v["approved_characters"] == 0 for v in coverage.values()
            ),
            full_raw_public_content_characters=profile["raw_public_content_characters"],
            known_subset_positive_public_content_characters=profile[
                "observed_known_approved_public_content_characters"
            ],
            full_positive_public_content_characters=profile["approved_public_content_characters"],
            character_coverage_is_not_reasoning_quality=True,
        ),
        mapping=dict(
            deterministic_true_singletons=singleton_count,
            model_registered_calls=seal["purpose_expected"]["mapping"],
            model_complete=seal["mapping_complete_calls"],
            resolved_tasks=len(resolved),
            unresolved_tasks=support["N"] - len(resolved),
            singleton_chi=None,
            singleton_chi_status="not_required_for_weighting",
            incomplete_mapping_does_not_invalidate_original_process=True,
        ),
        resolved_subset_only=dict(
            scope="424 resolved tasks only; not the fixed 744-task population or an admitted pool",
            tasks=len(resolved),
            packages=sum(row["n_x"] for row in resolved.values()),
            states=sum(len(row["states"]) for row in resolved.values()),
            multi_state_tasks=sum(len(row["states"]) > 1 for row in resolved.values()),
            one_state_tasks=sum(len(row["states"]) == 1 for row in resolved.values()),
            chi_0_1_contrast_tasks=sum(
                set(row["chi"].values()) == {0, 1} for row in resolved.values()
            ),
            state_count_minus_task_count=sum(len(row["states"]) - 1 for row in resolved.values()),
            chi_state_histogram=dict(
                Counter(
                    "null" if chi is None else str(chi)
                    for row in resolved.values()
                    for chi in row["chi"].values()
                )
            ),
            task_state_count_histogram=dict(
                Counter(str(len(row["states"])) for row in resolved.values())
            ),
            state_package_count_histogram=dict(
                Counter(str(n) for row in resolved.values() for n in row["states"].values())
            ),
            no_subset_training_authorized=True,
            no_projection_to_full_population=True,
        ),
        full_population_capability=dict(
            state_count=profile["state_count"],
            D_pi=profile["D_pi"],
            M_flex=profile["M_flex"],
            multi_state_tasks=profile["multi_state_tasks"],
            chi_flexible_tasks=profile["chi_flexible_tasks"],
            chi_flexible_mass=profile["chi_flexible_mass"],
            manual_intervention_dose=profile["manual_intervention_dose"],
            interpretation=(
                "Unknown because complete fixed-population mapping is unavailable; "
                "not measured zero or proven degeneracy."
            ),
        ),
        encoding=dict(
            started_packages=profile["encoding_started_packages"],
            deferred_packages=encoding_reasons["whole_pool_authority_barrier_unresolved"],
            observed_encoding_failure_packages=sum(
                reason != "whole_pool_authority_barrier_unresolved"
                for blocker in profile["blockers"]
                if blocker["reason"] == "fixed_original_encoding_unresolved"
                for reason in [blocker["failures"][0]["reason"]]
            ),
            blocker_failure_reason_counts=dict(encoding_reasons),
            full_supervised_tokens=profile["supervised_tokens"],
            all_public_reasoning_masked=profile["all_public_reasoning_masked"],
            encoding_directory_exists=(root / "encoding").exists(),
            interpretation=(
                "2468 deferred encodings are consequences of the whole-pool authority barrier, "
                "not 2468 model or tokenizer failures."
            ),
        ),
        admission=dict(
            material_complete=support["material_complete"],
            training_admitted=result["training_admitted"],
            binding_exists=(root / "material/binding/record.json").exists(),
            training_started=seal["training_started"],
            no_fixed_original_removed=result["no_fixed_original_removed"],
            five_arm_experiment_started=False,
            completed_formal_seed_arm_runs=0,
            formal_student_checkpoints=0,
            formal_dev883_evaluations=0,
            current_round_student_or_dev_results_available=False,
        ),
        conditional_plan_not_execution=dict(
            registered_task_count=support["N"],
            planned_arms=["Static", "Manual+", "Manual-", "C-only", "Full"],
            planned_seeds=[11, 29, 47],
            planned_seed_arm_runs=15,
            steps_per_epoch=support["execution_plan"]["steps_per_epoch"],
            real_tail_batch_size=support["execution_plan"]["tail_batch_size"],
            shared_step=support["execution_plan"]["shared_step"],
            outer_steps=support["execution_plan"]["outer_steps"],
            final_step=support["execution_plan"]["final_step"],
            loss_coefficient=support["execution_plan"]["loss_coefficient"],
            planned_dev_tasks_per_model=883,
            planned_dev_sessions=13245,
            none_of_these_plan_coordinates_are_observed_training_results=True,
        ),
        mainline_experiment_boundaries=dict(
            Exp0=dict(
                name="support_and_state_validation",
                status="attempt_completed_but_material_gate_blocked",
                realized=(
                    "Full fixed population retained; all calls terminal; "
                    "projection and state support remain incomplete."
                ),
            ),
            Exp1=dict(
                name="Static_Manual_fixed_intervention",
                status="not_started_this_round",
                blocker="Complete material and actual Student training unavailable.",
            ),
            Exp2=dict(
                name="C_N_mechanisms",
                status="not_started_this_round",
                realized_mechanism_student_experiments=0,
            ),
            Exp3=dict(
                name="full_five_arm_experiment",
                status="not_started_this_round",
                completed_formal_seed_arm_runs=0,
            ),
            Exp4=dict(
                name="restricted_mathematical_study",
                status="not_rerun_this_round",
                historical_boundary=(
                    "Historical work was only a synthetic fixed-potential demonstration; "
                    "it does not prove dynamic Student convergence."
                ),
                historical_artifacts_reaudited_by_this_report=False,
            ),
            Exp5=dict(
                name="fixed_pi_training_objective_ablation",
                status="deferred_not_started_this_round",
            ),
        ),
        report_only=True,
        source_records_modified=False,
        semantic_rejudgment=False,
        subset_selection=False,
        API_calls_by_this_report=0,
        GPU_used_by_this_report=False,
        report_scope=(
            "Final factual accounting of this blocked V13 attempt, "
            "not a claim of successful five-arm completion."
        ),
    )
    return body | dict(id=digest(body))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    args = parser.parse_args()
    print(json.dumps(summarize(args.root), ensure_ascii=False, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
