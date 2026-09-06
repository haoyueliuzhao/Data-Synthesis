"""A fixed stratified generation source; prompt preference is never QA authority."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from trusted_synthesis.canonical_json import canonical_json_bytes, strict_canonical_hash
from trusted_synthesis.domains.finance.qa_vnext.action_public_contract import public_action_contract
from trusted_synthesis.domains.finance.qa_vnext.protocol import contract
from trusted_synthesis.domains.finance.qa_vnext.runner import build_catalog
from trusted_synthesis.domains.finance.qa_vnext.share_adapter import SHARE_FAMILY, ShareTaskAdapter
from trusted_synthesis.domains.finance.qa_vnext.update_public_contract import public_update_contract

from ..finance_qa_vnext_action_branch.plan import initial_request
from ..finance_qa_vnext_model_execution.models import read_json, record, require, sha
from ..finance_qa_vnext_model_execution.transport import (
    SYSTEM_PROMPT,
    TransportConfig,
    render_http_request,
)
from ..finance_qa_vnext_panel_quotient.rules import quotient_rule

STAGE = "finance_qa_vnext_same_task_support_exploration_pilot"
RUN_TAG = "share_four_neutral_four_guided_v1_20260907"
PARENT_COMMIT = "4a810d51d2c7eccd70e3c241b4223c8bc3195fb9"
LABELS = tuple(f"{profile}{wave:02d}" for wave in range(1, 5) for profile in ("N", "E"))
GUIDANCE = (
    "Exploration preference, not a correctness requirement: While preserving the task goal "
    "and all legal actions, prefer trying to construct a usable denominator from the public "
    "component quantities and their composition relation. If you use this basis, subsequent "
    "calculations should actually consume the corresponding accepted Claim. You may still "
    "choose another legal basis. Do not claim unexecuted results or fabricate support."
)
OLD_PANEL_CONDITION = (
    "trusted_data_synthesis/artifacts/qa_vnext_task_panel/"
    "fixed_eight_task_panel_v1_20260906/preparation/condition.json"
)


def profiles():
    return {
        name: record(
            "support_exploration_profile",
            profile=name,
            description="neutral full-task"
            if name == "N"
            else "soft reconstructed-basis preference",
            system_prompt=SYSTEM_PROMPT if name == "N" else SYSTEM_PROMPT + "\n\n" + GUIDANCE,
            additional_guidance="" if name == "N" else GUIDANCE,
            presentation_changes_only=True,
            correctness_requirement=False,
            available_actions_filtered=False,
            prefilled_response_or_trajectory_prefix=False,
            host_action_selection=False,
            host_claim_or_denominator_repair=False,
            disclosed_total_success_still_qualified=True,
        )
        for name in ("N", "E")
    }


class ExplorationTransportConfig(TransportConfig):
    """Only fixed total budget and per-instance prompt profile differ from inherited transport."""

    maximum_pilot_attempts: Literal[256] = 256
    profile: Literal["N", "E"]

    def as_record(self) -> dict[str, Any]:
        original = super().as_record()
        return record(
            "transport_config",
            **{
                **{
                    key: value
                    for key, value in original.items()
                    if key not in {"id", "schema_version"}
                },
                "messages_policy": (
                    "registered profile system plus canonical current public request; "
                    "stateless; preference is not qualification"
                ),
            },
        )


def configuration(profile: str) -> ExplorationTransportConfig:
    require(profile in {"N", "E"}, "support_exploration.profile")
    return ExplorationTransportConfig(
        profile=profile, system_prompt=profiles()[profile]["system_prompt"]
    )


@dataclass
class SharePanel:
    root: Path
    catalog: Any
    context: dict[str, Any]

    def adapter(self, group: str):
        require(group == "S", "support_exploration.only_existing_share")
        adapter = ShareTaskAdapter(
            self.root, self.catalog.registry, self.catalog.resolve(SHARE_FAMILY).receipt
        )
        require(
            canonical_json_bytes(adapter.context) == canonical_json_bytes(self.context),
            "support_exploration.context_changed",
        )
        return adapter


def load_panel(root: Path):
    """Resolve only the already registered Share source, not all financial source cases."""
    catalog = build_catalog(root)
    adapter = ShareTaskAdapter(root, catalog.registry, catalog.resolve(SHARE_FAMILY).receipt)
    old = read_json((root / OLD_PANEL_CONDITION).read_bytes())
    require(
        canonical_json_bytes(adapter.context) == canonical_json_bytes(old["task_contexts"]["S"]),
        "support_exploration.original_share_context",
    )
    return SharePanel(root, catalog, read_json(canonical_json_bytes(adapter.context)))


def freeze_condition(root, implementation, policy, *, run_tag=RUN_TAG):
    require(run_tag == RUN_TAG, "support_exploration.frozen_run_tag")
    panel = load_panel(root)
    context = panel.context
    condition = record(
        "support_exploration_condition",
        stage=STAGE,
        run_tag=run_tag,
        predecessor_commit=PARENT_COMMIT,
        implementation_id=implementation["id"],
        task_group="S",
        task_type=SHARE_FAMILY,
        task_id=context["task_id"],
        context_id=context["id"],
        protocol_id=contract()["id"],
        registry_hash=strict_canonical_hash(panel.catalog.registry.manifest()),
        original_context=context,
        source_binding_id=context["source_binding"]["id"],
        catalog_id=panel.catalog.descriptor["id"],
        profiles=profiles(),
        configurations={name: configuration(name).as_record() for name in ("N", "E")},
        profile_mixture={name: {"numerator": 1, "denominator": 2} for name in ("N", "E")},
        registered_labels=list(LABELS),
        registered_session_count=8,
        sessions_per_profile=4,
        waves=[[f"N{wave:02d}", f"E{wave:02d}"] for wave in range(1, 5)],
        maximum_parallel_sessions=2,
        fixed_stratified_sampling=True,
        randomized_pairing=False,
        action_public_contract_id=public_action_contract()["id"],
        update_public_contract_id=public_update_contract()["id"],
        rule_id=quotient_rule()["id"],
        new_post_outcome_quotient_rules_allowed=False,
        representation_policy_id=policy["id"],
        maximum_sequence_length=32768,
        maximum_actions_per_session=12,
        maximum_submissions_per_session=32,
        maximum_provider_attempts_per_session=32,
        maximum_provider_attempts=256,
        maximum_reserved_token_allowance=27_525_120,
        maximum_completion_tokens=8192,
        maximum_http_body_bytes=98_304,
        maximum_request_reserved_tokens=107_520,
        automatic_retries=0,
        model_fallbacks=0,
        failed_session_replacements=0,
        outcome_adaptive_prompts_or_population=False,
        historical_sessions_imported=0,
        historical_panel_task_marginal_modified=False,
        neutral_profile_frequency_is_not_guided_profile_frequency=True,
        profile_names_are_not_semantic_classes=True,
        profile_preference_is_not_qualification=True,
        generation_domain="preregistered balanced N/E stratified exploration source",
        source_usage="known_development_source_not_blindtest",
        autonomous_planning=False,
        target=(
            "two qualified actual disclosed/reconstructed denominator production-consumption "
            "supports with exact separation witness"
        ),
        completion_does_not_require_target_witness=True,
        student_forward_calls=0,
        student_parameter_updates=0,
        gpu_jobs=0,
        Contribution=None,
        VTDO_update=False,
        final_training_weights=None,
        old_mainline="remains_paused",
    )
    registrations = []
    for ordinal, label in enumerate(LABELS):
        profile, wave = label[0], int(label[1:])
        session_id = strict_canonical_hash(
            {"condition_id": condition["id"], "label": label},
            prefix="qa_vnext_support_exploration_session:",
        )
        registrations.append(
            record(
                "session_registration",
                label=label,
                ordinal=ordinal,
                wave=wave,
                round=wave,
                profile=profile,
                profile_id=condition["profiles"][profile]["id"],
                session_id=session_id,
                run_condition_id=condition["id"],
                model_configuration_id=condition["configurations"][profile]["id"],
                **{
                    key: condition[key]
                    for key in (
                        "task_group",
                        "task_type",
                        "task_id",
                        "context_id",
                        "protocol_id",
                        "registry_hash",
                    )
                },
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


def wiring_controls(panel, condition, registrations):
    """Only new profile wiring: identical public environment, exact prompt and request budgets."""
    requests, rows = {}, []
    for registration in registrations:
        request = initial_request(panel.adapter("S"))
        profile = registration["profile"]
        config = configuration(profile)
        http = render_http_request(
            request, config, session_id=registration["session_id"], attempt_index=0
        )
        require(
            request["public_action_contract"] == public_action_contract()
            and request["public_update_contract"] == public_update_contract(),
            "support_exploration.publications",
        )
        require(
            http["messages"]
            == [
                {"role": "system", "content": condition["profiles"][profile]["system_prompt"]},
                {"role": "user", "content": canonical_json_bytes(request).decode()},
            ],
            "support_exploration.actual_profile_messages",
        )
        require(
            http["body_byte_count"] <= 98_304 and http["input_admission_upper_bound"] <= 99_328,
            "support_exploration.initial_request_budget",
        )
        requests[registration["label"]] = {"public": request, "http": http}
        rows.append(
            {
                "label": registration["label"],
                "profile": profile,
                "request_id": request["id"],
                "http_request_id": http["id"],
                "body_byte_count": http["body_byte_count"],
                "system_prompt_sha256": sha(http["messages"][0]["content"].encode()),
                "profile_id": registration["profile_id"],
                "available_actions_count": len(request["available_actions"]),
                "complete_candidate_space_preserved": True,
            }
        )
    require(
        len({canonical_json_bytes(item["public"]) for item in requests.values()}) == 1,
        "support_exploration.profile_changed_task_or_legal_space",
    )
    return record(
        "support_exploration_wiring_controls",
        rows=rows,
        passed=True,
        all_eight_public_requests_byte_identical=True,
        actual_system_profiles_differ=True,
        instruction_not_part_of_qa_or_runtime=True,
        host_route_selection=False,
        new_source_or_task_instances=0,
        runtime_executions=0,
        provider_calls=0,
    ), requests
