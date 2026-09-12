"""One preregistered source/period/trajectory version, with conditional fixed A/B study."""

from ..finance_qa_vnext_task_build.archive import record
from . import collection, materials, power, source_policy, transport

OUTPUT = "trusted_data_synthesis/artifacts/qa_vnext_eval_readiness/eval_readiness_20260912"
WORK = "trusted_data_synthesis/artifacts/qa_vnext_eval_readiness/runtime_20260912"
AUDITS = "trusted_data_synthesis/artifacts/qa_vnext_eval_readiness/eval_readiness_20260912_audits"
COLLECTION = "trusted_data_synthesis/artifacts/qa_vnext_eval_readiness/fixed_AB_20260912"
AUDIT_ATTACHMENT = (
    "/home/zhuxinrui/.codex/attachments/7b65d26b-54b3-4274-85b9-07c8e52e7c94/pasted-text.txt"
)


def policy(panel_policy):
    return record(
        "eval_readiness_protocol",
        stage_name="actual-period panels and complete trajectory admission",
        prior_training_candidates=243,
        prior_panel_exports=874,
        prior_registered_panel_targets=886,
        parent_bridge_manifest=source_policy.BRIDGE_MANIFEST,
        old_training_surfaces_changed=False,
        old_Oracle_source_reaudit=False,
        old_36_script_controls_rerun=False,
        old_167_material_rows_reencoded=False,
        old_confirm_Student_arm_outputs_in_this_study=0,
        old_confirm_content_seen_during_construction_and_audit=True,
        source_increment=source_policy.policy(),
        source_margin_user_choice="one bounded attempt up to 17 before any Teacher output",
        panel=panel_policy,
        public_period_rule=(
            "actual start/end/type grounded in original native rows; annual is not calendar; "
            "mean/peak show all three intervals; no answer or chosen peak in public contract"
        ),
        period_Final_rule="selected actual interval identity, never year-index equality alone",
        independent_period_audit_required=True,
        old_96_counterexamples_retained_with_new_version_impact=True,
        primary_utility=(
            "correct first Final plus full actual source/period/unit/executed support; "
            "mean all three operands or another proved public sufficient basis; "
            "argmax complete candidate comparison plus same-actual-period secondary lookup"
        ),
        primary_requires_fine_mapping=False,
        fine_mapping_required_for_training_kernel=True,
        pending_records_retained=True,
        public_sources="complete pinned snapshot via source-driven bounded query/read/pagination",
        controls={
            "old_control_reuse": "reference only, no replay or re-encoding",
            "new_synthetic": "fixed new-structure positive and negative contract controls",
            "real_fixture_selection": (
                "first TaskID in each split/family/quantity/actual-period-kind cell; "
                "period kind calendar duration, non-calendar duration, or instant"
            ),
            "real_case_rules": (
                "source_bound_cases fixed before production, no Teacher observations"
            ),
            "new_CPU_tokenizer_constructions": 1,
            "maximum_sequence_length": 24576,
            "model_weights": 0,
            "GPU": 0,
            "scripts_are_training_material": False,
        },
        evaluation_rewrite_requests=0,
        model=transport.policy(),
        registered_collection_policy=collection.policy(),
        registered_original_package_consumer=materials.policy(),
        power=power.policy(),
        prior_known_token_debit=221538,
        common_token_cap=1_000_000_000,
        common_ledger="existing SQLite rewrite ledger plus same-transaction Teacher/session gates",
        preparation_Teacher_sessions=0,
        preparation_Student_runs=0,
        no_live_pilot_or_prompt_selection=True,
        formal_collection_gate=[
            "panel exactly dev180/confirm720 with three equal groups",
            "independent actual-period public/source audit passed",
            "all fixed new synthetic and actual-source trajectory controls passed",
            "new original CPU token representations passed",
            "training canonical catalog and public bytes locked",
            "strict live callback, common-budget and original package consumer controls passed",
            "complete predeclared study implementation registered; no pilot",
        ],
        fixed_collection={
            "pools": ["A", "B"],
            "duals_sessions_per_task_basis_pool": 32,
            "control_sessions_per_task_pool": 24,
            "max_responses": 32,
            "max_tools": 32,
            "at_current_243_candidates_sessions": 23104,
            "at_current_243_candidates_requests": 739328,
            "at_260_candidates_sessions": 25280,
            "at_260_candidates_requests": 808960,
            "workers": 8,
            "complete_fixed_registry_required_before_population_selection": True,
            "ordinary_session_failure": "retained once; continue other registered sessions",
            "fatal_budget_auth_model_or_billing_failure": (
                "persist study stop; keep all partial/inflight/unknown charges; "
                "select no population"
            ),
            "no_eight_package_early_stop": True,
            "no_new_sources_after_Teacher_outputs": True,
            "no_resampling_failed_sessions": True,
        },
        inherited_design={
            "accepted_N": [180, 185, 190, 195, 200],
            "three_dual_groups_equal": True,
            "control_twice_each": True,
            "training_packages_per_method_pool": 8,
            "heldout_packages_per_method_pool": 2,
            "alpha": ["1/2,1/2", "1/3,2/3", "2/3,1/3"],
            "global_mass_shift": "1/10",
            "per_target_token_coefficient": "alpha/(40*whole_package_target_tokens)",
            "control_coefficient": "1/(40*whole_package_target_tokens)",
            "five_tasks_per_update": 5,
            "packages_per_update": 64,
            "epochs": 10,
            "updates_at_180": 360,
            "updates_at_200": 400,
            "max_training_runs_pool_A": 9,
            "max_training_runs_pool_B": 6,
            "direction": "mean paired primary utility strictly positive; no per-seed extra gate",
            "primary_confirmation_pool": "B",
            "dev_sessions": 1620,
            "confirm_sessions": 8640,
            "fixed_common_material_kernel": (
                "public bytes/guidance/fine classes/original responses fixed"
            ),
        },
        shortage_rule=(
            "any panel quota/semantics/complete-trajectory gate fails: no formal collection; "
            "no further source search or quota relaxation in this version"
        ),
    )
