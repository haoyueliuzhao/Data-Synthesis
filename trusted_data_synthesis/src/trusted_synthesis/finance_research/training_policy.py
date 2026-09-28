"""Audited next-training design; freezing this definition does not launch a run.

Actual rollout count, token budget, qualified support and training dose require a
later material/runtime registration. H0/H1 calibration is not a training result.
"""

from .contracts import digest
from .encoding import EOS_POLICY, SUPERVISION_POLICY


def training_interface_policy():
    body = {
        "schema_version": "finance_research.training_interface_policy.v2",
        "status": "interface_policy_fixed_large_collection_and_training_not_authorized",
        "probe": {
            "api_model": "deepseek-flash",
            "model_fallback": False,
            "source_record": "ProbeGenerationRecord",
            "student_encoding": "StudentEncodingRecord",
            "API_logP_required_for_SFT": False,
            "API_original_sampling_tokens_claimed": False,
            "raw_requests_responses_tool_execution_retained": True,
            "rollouts_per_task": None,
            "rollout_count_and_token_budget_must_be_registered_before_collection": True,
        },
        "sft": {
            "supervision": SUPERVISION_POLICY,
            "eos": EOS_POLICY,
            "local_EOS": "include actual EOS only on positive response targets",
            "offline_API_EOS": (
                "append one Student EOS to positive response targets; not an observed API token"
            ),
            "failed_response_and_feedback": "context only; zero response targets including EOS",
            "full_public_history_retained": True,
            "context_truncation": False,
            "training_entrypoint": "execute_task_batch_update",
            "batch_size": 5,
            "task_sampling": "uniform_epoch_permutation",
            "coefficient": "mu/(B*p_s)*pi/(n_state*L)",
            "additional_batch_division": False,
            "full_population_G_and_controls": "weighted_examples/execute_training_update",
        },
        "qualification": {
            "native_correctness_implies_CompletePass": False,
            "unknown_can_mint_valid_state": False,
            "same_state_rollouts": "within-state instances; never new states",
            "single_state_task": "static control",
            "request_route_implies_state": False,
            "missing_registered_task_or_state": (
                "block whole training; no task deletion or mass renormalization"
            ),
            "all_qualified_original_packages_retained": True,
            "NLL_style_future_student_selection": False,
            "per_state_quota_topups": False,
        },
        "utility": {
            "name": "J_FinQA_execution@H1",
            "submission_profile": "finqa_program_v1",
            "normal_model_missing_or_invalid_prediction": 0,
            "infrastructure_unknown_or_reference_anomaly": "unscorable; never financial zero",
            "denominator": "complete preregistered feedback cohort; no selected-success mean",
            "receipt": "FeedbackTokenReceipt = actual local TokenReceipt",
            "offline_StudentEncodingRecord_accepted_for_feedback": False,
        },
        "data_roles": {
            "sft": 1000,
            "feedback_meta_training": 350,
            "calibration": 120,
            "official_dev_development_only": 883,
            "official_test_after_candidate_freeze": 1147,
            "TAT_QA_released_labelled_external": 1663,
            "FinanceMath": "not executed until legitimate snapshot and native scorer available",
            "official_source_overlap_disclosed": True,
        },
        "training_comparison_proposal_not_run_registration": {
            "conditions": ["Static", "Delayed-C"],
            "tasks": 1000,
            "tasks_per_update": 5,
            "epochs": 10,
            "updates_if_material_and_resource_admitted": 2000,
            "one_delayed_update_at_step": 1000,
            "feedback_tasks": 350,
            "feedback_repeats": 2,
            "feedback_sessions": 700,
            "dose_requires_actual_material_token_and_resource_registration": True,
            "full_or_novelty_validation_claimed": False,
        },
    }
    return {**body, "policy_id": "finance_training_interface:" + digest(body)}


def training_interface_policy_v3():
    """Current inventory scope plus later training proposal; v2 above is unchanged."""
    body = {
        "schema_version": "finance_research.training_interface_policy.v3",
        "previous_policy_id": training_interface_policy()["policy_id"],
        "current_scope": "fixed_real_Probe_inventory_only",
        "training_authorized": False,
        "frozen_environment": {
            "harness_id": "bigfinance-derived-vtdo-v3",
            "submission_profile": "finqa_program_v2",
            "reference_protocol": "visible-result-handle-v2",
            "new_prompt_harness_comparison": False,
        },
        "probe": {
            "api_model": "deepseek-flash",
            "model_fallback": False,
            "candidate_tasks": 1000,
            "slots_per_task": 8,
            "train_slots_per_task": 6,
            "sealed_diagnostic_slots_per_task": 2,
            "sessions": 8000,
            "max_responses_per_session": 32,
            "maximum_generation_requests": 256000,
            "spending_warning_CNY": "700",
            "hard_cap_CNY": "800",
            "hard_cap_does_not_authorize_retries_or_budget_topups": True,
            "input_output_thinking_concurrency_reservations": (
                "separately preregistered API ledger policy"
            ),
            "thinking": {"type": "disabled"},
            "temperature": 1.0,
            "top_p": 1.0,
            "max_output_tokens": 2048,
            "API_context_limit": 1048576,
            "Student_encoding_context_limit": 24576,
            "source_record": "ProbeGenerationRecord",
            "student_encoding": "StudentEncodingRecord",
            "API_sampling_logP_required_for_SFT": False,
            "offline_IDs_are_API_sampled_tokens": False,
            "feedback_receipt": "actual local TokenReceipt only",
            "API_local_Qwen_token_budgets_equivalent": False,
        },
        "inventory": {
            "order": [
                "freeze tasks slots qualification rules and Mapper",
                "complete fixed collection",
                "joint qualification",
                "freeze actual support mu pi0 r",
                "offline Student encoding",
            ],
            "all_qualified_train_original_packages_retained": True,
            "sealed_packages_can_enter_training": False,
            "quality_ranking_or_best_of_selection": False,
            "NLL_length_style_rarity_future_student_selection": False,
            "per_state_topups": False,
            "state_cloning": False,
            "prior_two_states_assumed": False,
            "missing_candidate_train_support": (
                "admitted=false; retain all 1,000 and missing roster"
            ),
            "silent_supported_subpopulation_or_mu_renormalization": False,
            "mu": "1/1000",
            "pi0_equals_r": "n_xz/n_x as exact Fraction strings",
            "prior_meaning": "empirical qualified train-package frequency, not Probe probability",
            "single_state_task": "static",
            "only_nontrivial_states_supply_pi_degrees_of_freedom": True,
            "native_correctness_or_successful_tool_implies_CompletePass": False,
        },
        "sft": {
            "supervision": SUPERVISION_POLICY,
            "eos": EOS_POLICY,
            "failure_history": "retained context, zero SFT targets; never crop failed prefixes",
            "context_truncation": False,
            "batch_size": 5,
            "coefficient": "mu/(B*p_s)*pi/(n_xz*L_P)",
            "uniform_task_coefficient": "pi/(5*n_xz*L_P)",
            "initial_package_coefficient": "1/(5*n_x*L_P)",
            "extra_batch_division": False,
        },
        "training_comparison_proposal_not_run_registration": {
            "initialization": "original Qwen2.5-7B-Instruct plus new q/v LoRA; never old Static",
            "paired_seeds": [11, 29, 47],
            "arms": ["Static", "Delayed-C"],
            "common_static_prefix_steps_per_seed": 1000,
            "total_steps_per_final_model": 2000,
            "branch_suffix_steps_per_arm": 1000,
            "fork_state": ["model", "Adam", "RNG", "task_schedule_cursor"],
            "physical_SFT_steps_three_seeds": 9000,
            "effective_six_model_training_history_steps": 12000,
            "new_HierLoss_or_auxiliary_data": False,
            "utility": "J_FinQA_execution@H1-R",
            "submission_profile": "finqa_program_v2",
            "feedback_tasks_per_seed": 350,
            "feedback_repeats": 2,
            "feedback_sessions_per_seed": 700,
            "feedback_all_zero": "keep pi; no additional sampling or reward revision",
            "feedback_tokens": "all actual sampled actions and EOS; never apply SFT target mask",
            "direct_policy_gradient_on_real_model": False,
            "single_delayed_update_current_equals_prior": True,
            "N": 0,
            "combined_KL_coefficient": 5,
            "Novelty_or_full_multiround_Full_validation": False,
            "exact_final_multistep_greedy_utility_derivative_claimed": False,
            "dev_tasks": 883,
            "final_model_dev_sessions": 5298,
            "base_dev_sessions": 883,
            "feedback_sessions_all_seeds": 2100,
            "local_sessions": 8281,
            "local_generate_call_cap": 264992,
            "extra_G_replay_recovery_recomputation": "separate budget, not silently included",
            "actual_material_tokens_memory_and_resource_registration_still_required": True,
            "no_positive_mean_DelayedC_increment": (
                "close study, no replacement seeds or added Novelty"
            ),
            "test_TATQA_FinanceMath_used_for_configuration_selection": False,
        },
    }
    return {**body, "policy_id": "finance_training_interface:" + digest(body)}


def conditional_training_interface_policy(scope):
    """Explicit static-supported study, not a relabelled full-population result.

    Sampling weights may be uniform only inside this newly authorized scope.
    The original 1,000-task training dose does not automatically transfer to it.
    """
    body = training_interface_policy_v3()
    previous_id = body.pop("policy_id")
    count = scope["scoped_task_count"]
    body.update(
        schema_version="finance_research.conditional_training_interface_policy.v1",
        previous_full_population_policy_id=previous_id,
        current_scope="explicit_author_anchored_conditional_Probe_inventory_only",
        conditional_scope_id=scope["scope_id"],
        original_candidate_count=1000,
        original_1000_training_admitted=False,
        full_population_generalization_claimed=False,
    )
    body["probe"].update(
        candidate_tasks=count,
        sessions=count * 8,
        maximum_generation_requests=count * 8 * 32,
    )
    body["inventory"].update(
        mu=f"1/{count}",
        mu_interpretation="new conditional study only; not original 1,000-task reweighting",
        missing_candidate_train_support="admitted=false; retain the entire conditional roster",
        original_1000_roster_and_static_exclusions_retained=True,
        additional_task_deletion_or_renormalization=False,
    )
    proposal = body["training_comparison_proposal_not_run_registration"]
    for field in (
        "common_static_prefix_steps_per_seed",
        "total_steps_per_final_model",
        "branch_suffix_steps_per_arm",
        "physical_SFT_steps_three_seeds",
        "effective_six_model_training_history_steps",
    ):
        proposal[field] = None
    proposal.update(
        task_count=count,
        training_dose_status="must preregister conditional task schedule and dose before training",
        original_1000_step_counts_not_transferred=True,
    )
    return {**body, "policy_id": "finance_training_interface:" + digest(body)}
