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
