"""Three explicit new source bindings, two profiles and twelve fixed fresh sessions.

Source admission belongs to the parameterized source module. This plan accepts
already-built adapters and binding records; it never loads the historical Share
source, substitutes a source after results, or executes a financial operation.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from trusted_synthesis.canonical_json import canonical_json_bytes, strict_canonical_hash
from trusted_synthesis.domains.finance.qa_vnext.action_public_contract import public_action_contract
from trusted_synthesis.domains.finance.qa_vnext.bound_share_adapter import BoundShareTaskAdapter
from trusted_synthesis.domains.finance.qa_vnext.protocol import contract
from trusted_synthesis.domains.finance.qa_vnext.update_public_contract import public_update_contract

from ..finance_qa_vnext_action_branch.plan import initial_request
from ..finance_qa_vnext_model_execution.models import identity, read_json, record, require, sha
from ..finance_qa_vnext_model_execution.transport import render_http_request
from ..finance_qa_vnext_support_exploration.plan import ExplorationTransportConfig, profiles

STAGE = "finance_qa_vnext_cross_binding_dual_support_transfer_pilot"
RUN_TAG = "cross_binding_dual_support_v1_20260907"
SOURCE_KEYS = ("unp_2016", "jpm_2014", "jpm_2015")
TASK_KEYS = ("T01", "T02", "T03")
LABELS = tuple(
    f"{task}_{profile}{wave:02d}" for wave in (1, 2) for task in TASK_KEYS for profile in ("N", "E")
)
TASK_FIELDS = ("task_group", "task_type", "task_id", "context_id", "protocol_id", "registry_hash")


def _identified(value):
    ref = value.get("id")
    require(isinstance(ref, str) and ":" in ref, "cross_binding.plan_identity")
    require(
        ref
        == strict_canonical_hash(
            {key: item for key, item in value.items() if key != "id"},
            prefix=ref.split(":", 1)[0] + ":",
        ),
        "cross_binding.plan_identity",
    )


class CrossBindingTransportConfig(ExplorationTransportConfig):
    """Retain the exact N/E prompt/HTTP semantics; only the fixed cohort bound changes."""

    maximum_pilot_attempts: Literal[384] = 384


def configuration(profile: str) -> CrossBindingTransportConfig:
    require(profile in {"N", "E"}, "cross_binding.profile")
    return CrossBindingTransportConfig(
        profile=profile, system_prompt=profiles()[profile]["system_prompt"]
    )


@dataclass
class TaskPanel:
    sources: dict[str, Any]
    contexts: dict[str, dict[str, Any]]
    registry_hashes: dict[str, str]

    def adapter(self, task_key: str):
        require(task_key in self.sources, "cross_binding.registered_adapter_key")
        adapter = BoundShareTaskAdapter(self.sources[task_key])
        require(
            canonical_json_bytes(adapter.context) == canonical_json_bytes(self.contexts[task_key])
            and strict_canonical_hash(adapter.registry.manifest())
            == self.registry_hashes[task_key],
            "cross_binding.frozen_adapter_context_or_registry",
        )
        return adapter


def freeze_condition(
    adapters: list[Any],
    source_records: list[dict[str, Any]],
    implementation: dict[str, Any],
    representation_policy: dict[str, Any],
    rule: dict[str, Any],
    *,
    run_tag: str = RUN_TAG,
) -> tuple[dict[str, Any], list[dict[str, Any]], TaskPanel]:
    """Freeze the complete three-source plan before any model response is available."""
    require(run_tag == RUN_TAG, "cross_binding.fixed_run_tag")
    identity(implementation, "implementation")
    _identified(representation_policy)
    _identified(rule)
    require(
        representation_policy["maximum_sequence_length"] == 32768
        and representation_policy["truncation"] is False,
        "cross_binding.original_representation_policy",
    )
    require(
        len(adapters) == len(source_records) == 3
        and tuple(adapter.source.source_key for adapter in adapters) == SOURCE_KEYS,
        "cross_binding.exact_three_new_source_bindings",
    )
    tasks, sources, contexts, registry_hashes = [], {}, {}, {}
    for key, adapter, binding in zip(TASK_KEYS, adapters, source_records, strict=True):
        _identified(binding)
        context = read_json(canonical_json_bytes(adapter.context))
        require(
            canonical_json_bytes(binding) == canonical_json_bytes(adapter.source.binding_record)
            and adapter.source.task_id == context["task_id"],
            "cross_binding.actual_source_adapter_binding",
        )
        registry_hash = strict_canonical_hash(adapter.registry.manifest())
        sources[key], contexts[key], registry_hashes[key] = adapter.source, context, registry_hash
        tasks.append(
            {
                "task_key": key,
                "task_group": key,
                "source_key": adapter.source.source_key,
                "task_type": context["task_type"],
                "task_id": context["task_id"],
                "context_id": context["id"],
                "protocol_id": contract()["id"],
                "registry_hash": registry_hash,
                "source_binding_id": adapter.source.source_binding_id,
                "source_record_id": binding["id"],
                "source_binding": binding,
                "context": context,
                "source_usage": "cross_binding_mechanism_development_not_blind_evaluation",
            }
        )
    require(
        all(
            len({task[field] for task in tasks}) == 3
            for field in (
                "task_id",
                "context_id",
                "source_binding_id",
                "source_record_id",
            )
        ),
        "cross_binding.independent_task_and_source_identities",
    )
    panel = TaskPanel(sources, contexts, registry_hashes)
    frozen_profiles = profiles()
    configurations = {profile: configuration(profile).as_record() for profile in ("N", "E")}
    waves = [[label for label in LABELS if label.endswith(f"{wave:02d}")] for wave in (1, 2)]
    condition = record(
        "cross_binding_condition",
        stage=STAGE,
        run_tag=run_tag,
        implementation_id=implementation["id"],
        tasks=tasks,
        task_count=3,
        task_keys=list(TASK_KEYS),
        task_contexts=contexts,
        source_keys=list(SOURCE_KEYS),
        source_binding_ids=[task["source_binding_id"] for task in tasks],
        task_marginal=[
            {
                "task_id": task["task_id"],
                "task_group": task["task_group"],
                "numerator": 1,
                "denominator": 3,
            }
            for task in tasks
        ],
        task_marginal_is_frozen_design_choice=True,
        profiles=frozen_profiles,
        configurations=configurations,
        profile_mixture={profile: {"numerator": 1, "denominator": 2} for profile in ("N", "E")},
        registered_labels=list(LABELS),
        registered_session_count=12,
        sessions_per_task=4,
        sessions_per_task_profile=2,
        rounds=2,
        waves=waves,
        maximum_parallel_sessions=6,
        fixed_wave_barrier=True,
        outcome_adaptive_scheduling=False,
        randomized_pairing=False,
        source_substitution_or_post_outcome_population_reduction=False,
        action_public_contract_id=public_action_contract()["id"],
        update_public_contract_id=public_update_contract()["id"],
        protocol_id=contract()["id"],
        rule_id=rule["id"],
        parameterized_rule_frozen_before_sampling=True,
        new_post_outcome_quotient_rules_allowed=False,
        representation_policy_id=representation_policy["id"],
        maximum_sequence_length=32768,
        maximum_actions_per_session=12,
        maximum_submissions_per_session=32,
        maximum_provider_attempts_per_session=32,
        maximum_provider_attempts=384,
        maximum_reserved_token_allowance=41_287_680,
        maximum_completion_tokens=8192,
        maximum_http_body_bytes=98_304,
        maximum_request_reserved_tokens=107_520,
        automatic_retries=0,
        model_fallbacks=0,
        failed_session_replacements=0,
        halt_future_waves_on_integrity_or_internal_failure=True,
        already_started_wave_members_remain_in_denominator=True,
        valid_final_stops_immediately=True,
        source_choice_after_model_results=False,
        maximum_same_task_pairs=6,
        maximum_total_same_task_pairs=18,
        cross_task_quotient_pairs_allowed=False,
        mechanism_labels_are_not_cross_task_class_ids=True,
        historical_sessions_imported=0,
        historical_class_ids_imported=False,
        old_panel_task_marginal_modified=False,
        original_unp_2015_not_a_new_task=True,
        profile_preference_is_not_qualification=True,
        profile_names_are_not_semantic_classes=True,
        disclosed_support_allowed_in_guided_profile=True,
        reconstructed_support_allowed_in_neutral_profile=True,
        original_system_prompts_and_responses_retained=True,
        completion_requires_all_successes_or_dual_support=False,
        full_support_training_materialized=False,
        final_training_weights=None,
        independent_evaluation_bound_and_ready=False,
        independent_evaluation_readiness_is_not_collection_gate=True,
        given_public_plan_and_legal_candidates=True,
        autonomous_planning_claimed=False,
        student_forward_calls=0,
        student_parameter_updates=0,
        gpu_jobs=0,
        Contribution=None,
        VTDO_update=False,
        old_mainline="remains_paused",
    )
    by_key = {task["task_key"]: task for task in tasks}
    registrations = []
    for ordinal, label in enumerate(LABELS):
        task_key, profile_repeat = label.split("_")
        profile, wave = profile_repeat[0], int(profile_repeat[1:])
        task = by_key[task_key]
        registrations.append(
            record(
                "session_registration",
                label=label,
                ordinal=ordinal,
                wave=wave,
                round=wave,
                task_key=task_key,
                source_key=task["source_key"],
                source_binding_id=task["source_binding_id"],
                profile=profile,
                profile_id=frozen_profiles[profile]["id"],
                model_configuration_id=configurations[profile]["id"],
                run_condition_id=condition["id"],
                session_id=strict_canonical_hash(
                    {"condition_id": condition["id"], "label": label},
                    prefix="qa_vnext_cross_binding_session:",
                ),
                **{key: task[key] for key in TASK_FIELDS},
                maximum_actions=12,
                maximum_submissions=32,
                maximum_provider_attempts=32,
                replacement_allowed=False,
                reference_route=None,
                independent_initial_state=True,
                reads_other_session_responses=False,
            )
        )
    return condition, registrations, panel


def wiring_controls(
    panel: TaskPanel, condition: dict[str, Any], registrations: list[dict[str, Any]]
):
    """Read-only initial-request checks; no Runtime construction or Operation execution."""
    require(
        [row["label"] for row in registrations] == list(LABELS), "cross_binding.control_population"
    )
    requests, rows = {}, []
    canonical_by_task: dict[str, bytes] = {}
    for registration in registrations:
        task_key, profile = registration["task_key"], registration["profile"]
        request = initial_request(panel.adapter(task_key))
        raw = canonical_json_bytes(request)
        if task_key in canonical_by_task:
            require(
                raw == canonical_by_task[task_key],
                "cross_binding.profile_changed_legal_environment",
            )
        canonical_by_task[task_key] = raw
        http = render_http_request(
            request, configuration(profile), session_id=registration["session_id"], attempt_index=0
        )
        require(
            request["public_action_contract"] == public_action_contract()
            and request["public_update_contract"] == public_update_contract(),
            "cross_binding.publications",
        )
        require(
            http["messages"]
            == [
                {"role": "system", "content": condition["profiles"][profile]["system_prompt"]},
                {"role": "user", "content": raw.decode()},
            ]
            and http["body_byte_count"] <= 98_304
            and http["input_admission_upper_bound"] <= 99_328,
            "cross_binding.exact_prompt_and_request_budget",
        )
        requests[registration["label"]] = {"public": request, "http": http}
        rows.append(
            {
                "label": registration["label"],
                "task_key": task_key,
                "profile": profile,
                "request_id": request["id"],
                "http_request_id": http["id"],
                "body_byte_count": http["body_byte_count"],
                "system_prompt_sha256": sha(http["messages"][0]["content"].encode()),
                "full_legal_action_space_unchanged": True,
                "no_filled_response_or_route_constraint": True,
            }
        )
    return record(
        "cross_binding_wiring_controls",
        rows=rows,
        all_expected_outcomes=True,
        task_count=3,
        registered_sessions=12,
        maximum_parallel_sessions=6,
        provider_calls=0,
        runtime_calls=0,
        operation_calls=0,
        maximum_initial_body_bytes=max(row["body_byte_count"] for row in rows),
        future_generated_states_guaranteed_to_fit=False,
    ), requests
