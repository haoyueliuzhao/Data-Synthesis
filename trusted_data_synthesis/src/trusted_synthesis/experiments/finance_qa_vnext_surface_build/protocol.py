"""Prospective source-extension and protected-question realization contract."""

from ..finance_qa_vnext_task_build import factory
from ..finance_qa_vnext_task_build.archive import record
from ..finance_qa_vnext_task_build.protocol import CAPS, SPLIT_SALT
from ..finance_qa_vnext_task_build.protocol import policy as source_policy
from .budget import COMMON_NEW_EXPERIMENT_CAP, INPUT_RESERVATION, OUTPUT_CAP, REQUEST_CAP, TOKEN_CAP
from .transport import ENDPOINT, MAX_PROMPT_BYTES, MODEL


def qa_config():
    config = factory.qa_config()
    config["qa"]["question_generation"].update(
        {
            "mode": "controlled_llm",
            "strategy": "protected_rewrite",
            "variants": 2,
            "max_attempts": 2,
            "variant_order": "response_order",
            "style_variant_id": "direct",
            "api_quality_gate": {"observational_only": True},
            "surface_variation": {"enabled": False, "llm_selects_variants": False},
        }
    )
    return config


def policy():
    inherited = source_policy()
    source_keys = (
        "source_scope",
        "source_split",
        "allowed_current_use",
        "native_snapshot_selection",
        "all_leaf_usage_required",
        "metrics_and_tag_priority",
        "observation_end_years",
        "observation_filter",
        "observation_selection",
        "source_occurrences",
        "target_periods",
        "task_identity",
        "relation_rules",
        "quantities",
        "issuer_table_policy",
        "company_defined_metric_rule",
        "enumeration",
    )
    return record(
        "protected_surface_protocol",
        stage="source_coverage_and_protected_question_realization_20260912",
        parent_commit="b3d7e7b182c1dbcdd8fff65a836518491a04d4ee",
        parent_stage_qualification="PASS_AS_SCOPED; 221 template tasks; LLM NOT_ENABLED",
        parent_source_protocol_id=inherited["id"],
        inherited_source_rules={key: inherited[key] for key in source_keys},
        effective_source_extension={
            "same_split_salt": SPLIT_SALT,
            "same_CIK_clusters": True,
            "archived_train_10K_source_bytes": True,
            "additional_admitted_HTTP_sources": [],
            "Oracle_2020_fetch": (
                "SEC 403; publisher rendered XBRL download not admitted as full 10-K"
            ),
            "definition_domain": [
                "stop explicit definition at colon or period",
                "explicit calculate-as-follows plus complete signed reconciliation",
                "exact TI subtract-capex-from-CFO clause plus exactly those two row roles",
                "trailing numeric/star annotations require following source note, "
                "retained verbatim",
            ],
            "dashes": "not numeric, never infer zero by closure or a later-year value",
            "positive_capex_sign_conversion": False,
            "period_definition_consistency": "same exact definition and component-label identity",
        },
        candidate_caps=CAPS,
        total_task_cap=260,
        enumeration=(
            "inherited source-cluster round robin and stable target identity; "
            "no rewrite yield selection"
        ),
        first_20={
            "duals": 12,
            "controls": 8,
            "included_in_total": True,
            "extend_gate": (
                "20 QA-valid retained tasks; real requests >0 and true accepted rewrites >0"
            ),
        },
        qa_config=qa_config(),
        acceptance={
            "actual_rendered_question": (
                "finite English temporal quantity parser + unchanged opaque slots"
            ),
            "difference": "signed current minus previous; no sum, absolute value or inverse",
            "growth": "100*(current-previous)/previous with positive previous",
            "unsupported_language": "reject candidate; deterministic canonical fallback",
            "candidate_selection": (
                "first valid in original response order; no style/Student selection"
            ),
            "repair": "one only after explicit structure/semantic failure; no transport retries",
            "all_registered_tasks_retained": True,
            "no_change_surface_only": "separately counted, not true rewrite",
        },
        strict_model_request={
            "purpose": "question_rewrite_only",
            "model": MODEL,
            "endpoint": ENDPOINT,
            "thinking": "disabled",
            "actual_response_identity": "exact API model string; not a weights/version hash",
            "temperature_top_p": "omitted",
            "auto_discovery": False,
            "cache": False,
            "model_fallback": [],
            "HTTP_attempts_per_reservation": 1,
            "redirects": False,
            "max_prompt_bytes_including_system": MAX_PROMPT_BYTES,
            "max_output_tokens": OUTPUT_CAP,
            "forbidden_prompt_material": (
                "answers, source-correct-role tables, endpoint/movement labels or route menus"
            ),
            "allowed_prompt_material": "protected question and necessary public task semantics",
            "not_equivalent_to_old_Teacher_contract": True,
        },
        budget={
            "request_cap": REQUEST_CAP,
            "per_task_cap": 2,
            "rewrite_token_allocation": TOKEN_CAP,
            "input_tokens_reserved_per_request": INPUT_RESERVATION,
            "output_tokens_reserved_per_request": OUTPUT_CAP,
            "mechanism": (
                "SQLite BEGIN IMMEDIATE, persistent reserve before HTTP, no inflight replay"
            ),
            "unknown_usage": "hold full reservation; do not claim zero consumption",
            "usage_overrun": "record actual reported usage, flag breach, prohibit further reserves",
            "existing_new_experiment_global_cap_unchanged": COMMON_NEW_EXPERIMENT_CAP,
            "rewrite_is_deducted_from_existing_cap": True,
            "allocation_is_not_a_new_extra_global_allowance": True,
        },
        task_surface_identity={
            "canonical_task_ID": (
                "source cluster, metric definition, actual periods and quantity only"
            ),
            "surface_version_ID": "canonical task ID + actual public input bytes",
            "all_future_pools_conditions_arms": "same frozen teacher_visible.json bytes",
            "old_response_prefix_relabeling": False,
        },
        downstream={
            "Teacher_calls": 0,
            "Student_runs": 0,
            "GPU_runs": 0,
            "tokenizer_loads": 0,
            "training_population_selected": False,
            "about_200_design": (
                "unchanged; report supply for 180-200, never equate candidate count with readiness"
            ),
            "material_pool_design": "each A/B 2560 train + 640 sealed; same public bytes",
            "new_task_worker_X1_X2_reuse": False,
            "training_and_material_generation_authorized_by_this_stage": False,
        },
    )
