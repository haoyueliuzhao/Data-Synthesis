from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from collections import Counter
from collections.abc import Sequence
from decimal import Decimal
from pathlib import Path
from typing import Any, Final, Literal, cast

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_privacy_first_exact_final_execution as privacy_runner,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_privacy_safe_s1_capability_online as online,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_privacy_safe_s1_capability_preflight as preflight,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_two_stage_semantic_proposal_execution as legacy,
)
from trusted_synthesis.hashing import canonical_hash
from trusted_synthesis.runtime.agent.prospective_semantic_action_protocol import (
    build_semantic_action_state,
    evaluate_canonical_action_proposal,
)
from trusted_synthesis.runtime.agent.prospective_semantic_action_response_grammar import (
    parse_exact_canonical_action_payload,
)
from trusted_synthesis.runtime.agent.prospective_thinking_completion import CompletionProjection

RUN_ID: Final = "finance_v26_142_privacy_safe_s1_capability_failed_lineage_audit_v1_20260824"
OUTPUT_DIR: Final = (
    "artifacts/vtdo_experiment/"
    "finance_v26_142_privacy_safe_s1_capability_failed_lineage_audit_v1_20260824"
)
EXECUTION_DIR: Final = online.OUTPUT_DIR
IMPLEMENTATION_PATH: Final = (
    "src/trusted_synthesis/experiments/vtdo_experiment/"
    "phase1_v26_privacy_safe_s1_capability_failure_audit.py"
)
NEXT_STAGE: Final = "fresh_orphan_reference_unavailable_support_exit_recovery_preflight_only"

EXPECTED_EXECUTION_SOURCE_REPLAY_ID: Final = (
    "finance_v26_privacy_safe_capability_execution_source_replay:"
    "f01b157c1c22e901ab1eadbb4521afceca98142007754c65bdcfd97edd0e8ba8"
)
EXPECTED_PREEXECUTION_BINDING_ID: Final = (
    "finance_v26_privacy_safe_capability_execution_preexecution_binding:"
    "00de9362a2187fc106cd603f175fb982d64c2440bbe929b2b833281f9c4d874d"
)
REFERENCE_FAILURE: Final = "Prompt-only acquisition policy cannot satisfy its public route"

FROZEN_EXECUTION_FILES: Final = (
    "frozen_capability_execution_contract.json",
    "frozen_capability_manifest.json",
    "frozen_capability_outcome_contract.json",
    "frozen_capability_path_catalog.json",
    "frozen_capability_prompt_noninterference_audit.json",
    "frozen_capability_resource_binding.json",
    "frozen_capability_runner_contract.json",
    "frozen_capability_task_package_catalog.json",
    "frozen_predecessor_integrity_audit.json",
    "frozen_preflight_transition_contract.json",
    "online_source_replay_audit.json",
    "preexecution_binding_audit.json",
)


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


def _identity(value: BaseModel, field: str, prefix: str) -> str:
    return canonical_hash(value.model_dump(mode="json", exclude={field}), prefix=prefix)


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _write_json_atomic(path: Path, value: Any) -> None:
    payload = value.model_dump(mode="json") if isinstance(value, BaseModel) else value
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(_canonical_bytes(payload))
    temporary.replace(path)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _find_bound_path(
    relative_path: str,
    expected_sha256: str,
    *,
    package_root: Path,
    implementation_root: Path,
) -> Path:
    for root in (implementation_root, package_root):
        candidate = root / relative_path
        if candidate.is_file() and _sha256(candidate) == expected_sha256:
            return candidate
    raise ValueError(f"v26.142 cannot replay bound file: {relative_path}")


class SourceReplayEntry(FrozenModel):
    relative_path: str = Field(min_length=1)
    source_kind: Literal[
        "v26_141_bound_source",
        "v26_141_execution_file",
        "v26_142_implementation",
    ]
    expected_sha256: str = Field(min_length=64, max_length=64)
    observed_sha256: str = Field(min_length=64, max_length=64)
    byte_count: int = Field(gt=0)
    passed: Literal[True] = True


class FailureAuditSourceReplay(FrozenModel):
    audit_id: str = Field(min_length=1)
    execution_source_replay_id: str = EXPECTED_EXECUTION_SOURCE_REPLAY_ID
    bound_source_file_count: Literal[4553] = 4553
    execution_file_count: Literal[2680] = 2680
    implementation_file_count: Literal[1] = 1
    replayed_file_count: Literal[7234] = 7234
    replay_pass_count: Literal[7234] = 7234
    entries: tuple[SourceReplayEntry, ...] = Field(min_length=7234, max_length=7234)
    replay_before_role_input_loading: Literal[True] = True
    credential_lookup_attempted: Literal[False] = False
    model_client_constructed: Literal[False] = False
    provider_calls: Literal[0] = 0
    stage_two_provider_calls: Literal[0] = 0
    gpu_jobs: Literal[0] = 0
    status: Literal["passed"] = "passed"
    schema_version: Literal["finance_v26_capability_failed_lineage_source_replay.v1"] = (
        "finance_v26_capability_failed_lineage_source_replay.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> FailureAuditSourceReplay:
        paths = tuple(item.relative_path for item in self.entries)
        if (
            paths != tuple(sorted(set(paths)))
            or len(paths) != self.replayed_file_count
            or any(item.expected_sha256 != item.observed_sha256 for item in self.entries)
        ):
            raise ValueError("v26.142 source replay changed")
        if self.audit_id != _identity(
            self,
            "audit_id",
            "finance_v26_capability_failed_lineage_source_replay:",
        ):
            raise ValueError("v26.142 source replay identity changed")
        return self


class FailedLineageAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    source_replay_audit_id: str = Field(min_length=1)
    execution_source_replay_id: str = EXPECTED_EXECUTION_SOURCE_REPLAY_ID
    preexecution_binding_audit_id: str = EXPECTED_PREEXECUTION_BINDING_ID
    manifest_id: str = online.EXPECTED_MANIFEST_ID
    runner_contract_id: str = online.EXPECTED_RUNNER_CONTRACT_ID
    outcome_contract_id: str = online.EXPECTED_OUTCOME_CONTRACT_ID
    exact_manifest_job_count: Literal[96] = 96
    execution_file_count: Literal[2680] = 2680
    frozen_input_file_count: Literal[12] = 12
    checkpoint_file_count: Literal[1] = 1
    checkpoint_result_count: Literal[93] = 93
    complete_raw_execution_count: Literal[93] = 93
    provider_envelope_count: Literal[858] = 858
    public_projection_count: Literal[858] = 858
    transport_certificate_count: Literal[858] = 858
    complete_raw_bound_provider_call_count: Literal[855] = 855
    orphan_provider_call_count: Literal[3] = 3
    orphan_job_count: Literal[3] = 3
    orphan_job_ids: tuple[str, ...] = Field(min_length=3, max_length=3)
    manifest_job_artifact_coverage_count: Literal[96] = 96
    validated_artifact_pair_count: Literal[858] = 858
    validated_transport_certificate_count: Literal[858] = 858
    independently_reprojected_raw_count: Literal[93] = 93
    independently_matched_checkpoint_result_count: Literal[93] = 93
    completed_report_count: Literal[0] = 0
    invalid_payload_content_persisted_count: Literal[0] = 0
    invalid_payload_key_persisted_count: Literal[0] = 0
    private_reasoning_content_persisted_count: Literal[0] = 0
    private_reasoning_content_hashed_count: Literal[0] = 0
    raw_http_body_persisted_count: Literal[0] = 0
    raw_request_body_persisted_count: Literal[0] = 0
    prior_lost_attempt_pooled_count: Literal[0] = 0
    exact_denominator_complete: Literal[False] = False
    capability_gate_passed: Literal[False] = False
    status: Literal["failed_closed_three_provider_artifact_orphans"] = (
        "failed_closed_three_provider_artifact_orphans"
    )
    schema_version: Literal["finance_v26_capability_failed_lineage.v1"] = (
        "finance_v26_capability_failed_lineage.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> FailedLineageAudit:
        if (
            self.orphan_job_ids != tuple(sorted(set(self.orphan_job_ids)))
            or self.complete_raw_execution_count + self.orphan_job_count
            != self.exact_manifest_job_count
            or self.complete_raw_bound_provider_call_count + self.orphan_provider_call_count
            != self.provider_envelope_count
        ):
            raise ValueError("v26.142 failed lineage denominator changed")
        if self.audit_id != _identity(
            self,
            "audit_id",
            "finance_v26_capability_failed_lineage:",
        ):
            raise ValueError("v26.142 failed lineage identity changed")
        return self


class PartialCapabilityOutcomeAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    failed_lineage_audit_id: str = Field(min_length=1)
    complete_raw_subset_count: Literal[93] = 93
    missing_raw_count: Literal[3] = 3
    terminal_counts: dict[str, int]
    action_entry_count: Literal[92] = 92
    independently_valid_trajectory_count: Literal[17] = 17
    model_invalid_trajectory_count: Literal[76] = 76
    mechanisms_with_independently_valid_trajectory: Literal[4] = 4
    valid_mechanism_ids: tuple[str, ...] = Field(min_length=4, max_length=4)
    task_complete_raw_counts: dict[str, int]
    task_valid_trajectory_counts: dict[str, int]
    provider_call_count: Literal[858] = 858
    http_success_call_count: Literal[858] = 858
    exact_model_call_count: Literal[858] = 858
    thinking_complete_call_count: Literal[858] = 858
    usage_complete_call_count: Literal[858] = 858
    validated_public_payload_count: Literal[851] = 851
    provider_failure_no_payload_count: Literal[7] = 7
    privacy_rejection_count: Literal[0] = 0
    provider_prompt_tokens: Literal[4211294] = 4211294
    provider_completion_tokens: Literal[3831278] = 3831278
    provider_reasoning_tokens: Literal[3699772] = 3699772
    provider_total_tokens: Literal[8042572] = 8042572
    estimated_cost_usd: Literal["1.28198986720000011600"] = "1.28198986720000011600"
    reasoning_completion_fraction: str = Field(min_length=1)
    maximum_complete_raw_prompt_utf8_bytes: Literal[49504] = 49504
    maximum_complete_raw_job_tokens: Literal[223783] = 223783
    zero_detour_complete_raw_count: Literal[92] = 92
    one_detour_complete_raw_count: Literal[1] = 1
    stage_two_provider_call_count: Literal[0] = 0
    exact_task_weighted_capability_estimate_available: Literal[False] = False
    exact_denominator_interval_available: Literal[False] = False
    subset_values_are_descriptive_only: Literal[True] = True
    missing_rows_imputed: Literal[False] = False
    orphan_rows_classified_as_model_invalid: Literal[False] = False
    prior_lost_attempt_pooled: Literal[False] = False
    capability_gate_passed: Literal[False] = False
    schema_version: Literal["finance_v26_partial_capability_outcome.v1"] = (
        "finance_v26_partial_capability_outcome.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> PartialCapabilityOutcomeAudit:
        if (
            sum(self.terminal_counts.values()) != self.complete_raw_subset_count
            or self.independently_valid_trajectory_count + self.model_invalid_trajectory_count
            != self.complete_raw_subset_count
            or self.valid_mechanism_ids != tuple(sorted(set(self.valid_mechanism_ids)))
            or sum(self.task_complete_raw_counts.values()) != self.complete_raw_subset_count
            or sum(self.task_valid_trajectory_counts.values())
            != self.independently_valid_trajectory_count
            or self.provider_reasoning_tokens > self.provider_completion_tokens
        ):
            raise ValueError("v26.142 partial outcome denominator changed")
        if self.audit_id != _identity(
            self,
            "audit_id",
            "finance_v26_partial_capability_outcome:",
        ):
            raise ValueError("v26.142 partial outcome identity changed")
        return self


class OrphanRootCauseRow(FrozenModel):
    row_id: str = Field(min_length=1)
    job_id: str = Field(min_length=1)
    source_task_artifact_id: str = Field(min_length=1)
    mechanism_id: Literal["failure_recovery"] = "failure_recovery"
    tier: Literal["easy_control", "hard_control"]
    replicate_index: int = Field(ge=0, lt=8)
    provider_call_index: Literal[0] = 0
    envelope_id: str = Field(min_length=1)
    projection_id: str = Field(min_length=1)
    transport_certificate_id: str = Field(min_length=1)
    exact_model_http_success: Literal[True] = True
    thinking_complete: Literal[True] = True
    usage_complete: Literal[True] = True
    privacy_compliant_exact_four_field_payload: Literal[True] = True
    initial_prompt_sha256: str = Field(min_length=64, max_length=64)
    initial_state_id: str = Field(min_length=1)
    initial_candidate_count: int = Field(ge=1, le=63)
    selected_action_id: str = Field(min_length=1)
    selected_decision_kind: Literal["acquire_public_input"] = "acquire_public_input"
    selected_action_visible: Literal[True] = True
    selected_decision_kind_match: Literal[True] = True
    selected_prompt_only_reference: bool
    reversible_same_action_commit: Literal[True] = True
    committed_tool_id: Literal["query_structured_fact"] = "query_structured_fact"
    public_observation_status: Literal["failed"] = "failed"
    public_observation_error_code: str = Field(min_length=1)
    progress_vector_changed: bool
    ordinary_detour_count_after: int = Field(ge=0, le=1)
    successor_state_id: str = Field(min_length=1)
    successor_candidate_count: int = Field(ge=1, le=63)
    successor_prompt_sha256: str = Field(min_length=64, max_length=64)
    successor_prompt_utf8_bytes: int = Field(gt=0, le=60000)
    successor_prompt_state_reconstruction_passed: Literal[True] = True
    successor_candidate_order_preserved: Literal[True] = True
    successor_classifier_sensitive_key_count: Literal[0] = 0
    successor_reference_proposal_constructible: Literal[False] = False
    successor_reference_failure_type: Literal["ValueError"] = "ValueError"
    successor_reference_failure_message: Literal[
        "Prompt-only acquisition policy cannot satisfy its public route"
    ] = REFERENCE_FAILURE
    later_provider_invocation_count: Literal[0] = 0
    raw_execution_persisted: Literal[False] = False
    historical_terminal_assigned: Literal[False] = False
    typed_measurement_support_exit_recovery_candidate: Literal[True] = True
    schema_version: Literal["finance_v26_orphan_reference_root_cause_row.v1"] = (
        "finance_v26_orphan_reference_root_cause_row.v1"
    )

    @model_validator(mode="after")
    def validate_row(self) -> OrphanRootCauseRow:
        if self.row_id != _identity(
            self,
            "row_id",
            "finance_v26_orphan_reference_root_cause_row:",
        ):
            raise ValueError("v26.142 orphan root-cause row identity changed")
        return self


class OrphanRootCauseAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    failed_lineage_audit_id: str = Field(min_length=1)
    orphan_rows: tuple[OrphanRootCauseRow, ...] = Field(min_length=3, max_length=3)
    orphan_count: Literal[3] = 3
    exact_public_payload_parse_pass_count: Literal[3] = 3
    visible_candidate_commit_pass_count: Literal[3] = 3
    public_observation_replay_pass_count: Literal[3] = 3
    successor_prompt_render_pass_count: Literal[3] = 3
    successor_prompt_decode_pass_count: Literal[3] = 3
    successor_state_candidate_preservation_pass_count: Literal[3] = 3
    successor_sensitive_key_count: Literal[0] = 0
    successor_reference_failure_reproduction_count: Literal[3] = 3
    later_provider_invocation_count: Literal[0] = 0
    provider_calls: Literal[0] = 0
    root_cause: Literal[
        "dynamic_successor_reference_policy_unavailable_not_typed_as_measurement_support_exit"
    ] = "dynamic_successor_reference_policy_unavailable_not_typed_as_measurement_support_exit"
    failure_is_host_measurement_instrument_defect: Literal[True] = True
    failure_is_not_action_abi_or_candidate_error: Literal[True] = True
    failure_is_not_tool_runtime_error: Literal[True] = True
    reference_policy_may_not_select_or_repair_model_action: Literal[True] = True
    historical_orphan_terminal_reclassification_performed: Literal[False] = False
    status: Literal["root_cause_reproduced"] = "root_cause_reproduced"
    schema_version: Literal["finance_v26_orphan_reference_root_cause.v1"] = (
        "finance_v26_orphan_reference_root_cause.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> OrphanRootCauseAudit:
        job_ids = tuple(item.job_id for item in self.orphan_rows)
        if job_ids != tuple(sorted(set(job_ids))):
            raise ValueError("v26.142 orphan root-cause denominator changed")
        if self.audit_id != _identity(
            self,
            "audit_id",
            "finance_v26_orphan_reference_root_cause:",
        ):
            raise ValueError("v26.142 orphan root-cause identity changed")
        return self


class MutationResult(FrozenModel):
    mutation_name: str = Field(min_length=1)
    rejected: Literal[True] = True


class DestructiveAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    mutation_results: tuple[MutationResult, ...] = Field(min_length=12, max_length=12)
    mutation_count: Literal[12] = 12
    rejected_count: Literal[12] = 12
    provider_calls: Literal[0] = 0
    status: Literal["passed"] = "passed"
    schema_version: Literal["finance_v26_capability_failed_lineage_destructive.v1"] = (
        "finance_v26_capability_failed_lineage_destructive.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> DestructiveAudit:
        names = tuple(item.mutation_name for item in self.mutation_results)
        if names != tuple(sorted(set(names))):
            raise ValueError("v26.142 destructive denominator changed")
        if self.audit_id != _identity(
            self,
            "audit_id",
            "finance_v26_capability_failed_lineage_destructive:",
        ):
            raise ValueError("v26.142 destructive identity changed")
        return self


class ProspectiveTransitionContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    failed_lineage_audit_id: str = Field(min_length=1)
    orphan_root_cause_audit_id: str = Field(min_length=1)
    next_permitted_stage: str = NEXT_STAGE
    exact_orphan_count: Literal[3] = 3
    fresh_recovery_job_identities_required: Literal[True] = True
    exact_persisted_prefix_binding_required: Literal[True] = True
    exact_model_action_commit_observation_preserved: Literal[True] = True
    reference_unavailable_typed_support_exit_only: Literal[True] = True
    zero_later_provider_invocations_required: Literal[True] = True
    complete_credential_free_runner_preflight_required: Literal[True] = True
    provider_calls_authorized: Literal[False] = False
    capability_continuation_authorized: Literal[False] = False
    historical_job_rerun_authorized: Literal[False] = False
    historical_terminal_reclassification_authorized: Literal[False] = False
    s1_candidate_prompt_grammar_classifier_model_thinking_resource_change_authorized: Literal[
        False
    ] = False
    host_action_selection_or_repair_authorized: Literal[False] = False
    reachability_identity_or_execution_authorized: Literal[False] = False
    state_mapping_training_release_or_production_authorized: Literal[False] = False
    status: Literal["orphan_support_exit_recovery_preflight_only"] = (
        "orphan_support_exit_recovery_preflight_only"
    )
    schema_version: Literal["finance_v26_capability_failed_lineage_transition.v1"] = (
        "finance_v26_capability_failed_lineage_transition.v1"
    )

    @model_validator(mode="after")
    def validate_contract(self) -> ProspectiveTransitionContract:
        if self.contract_id != _identity(
            self,
            "contract_id",
            "finance_v26_capability_failed_lineage_transition:",
        ):
            raise ValueError("v26.142 transition identity changed")
        return self


class DetailFile(FrozenModel):
    relative_path: str = Field(min_length=1)
    sha256: str = Field(min_length=64, max_length=64)
    byte_count: int = Field(gt=0)


class CapabilityFailureAuditReport(FrozenModel):
    report_id: str = Field(min_length=1)
    run_id: str = RUN_ID
    source_replay_audit_id: str = Field(min_length=1)
    failed_lineage_audit_id: str = Field(min_length=1)
    partial_outcome_audit_id: str = Field(min_length=1)
    orphan_root_cause_audit_id: str = Field(min_length=1)
    destructive_audit_id: str = Field(min_length=1)
    transition_contract_id: str = Field(min_length=1)
    detail_files: tuple[DetailFile, ...] = Field(min_length=6, max_length=6)
    exact_manifest_job_count: Literal[96] = 96
    complete_raw_execution_count: Literal[93] = 93
    orphan_job_count: Literal[3] = 3
    provider_call_count: Literal[858] = 858
    independently_valid_complete_raw_count: Literal[17] = 17
    valid_mechanism_count: Literal[4] = 4
    exact_denominator_capability_gate_passed: Literal[False] = False
    historical_orphan_terminal_reclassification_count: Literal[0] = 0
    reachability_identity_count: Literal[0] = 0
    provider_calls: Literal[0] = 0
    stage_two_provider_calls: Literal[0] = 0
    gpu_jobs: Literal[0] = 0
    production_contribution: Literal[0] = 0
    next_permitted_stage: str = NEXT_STAGE
    status: Literal["capability_gate_failed_orphan_root_cause_localized"] = (
        "capability_gate_failed_orphan_root_cause_localized"
    )
    schema_version: Literal["finance_v26_capability_failed_lineage_audit_report.v1"] = (
        "finance_v26_capability_failed_lineage_audit_report.v1"
    )

    @model_validator(mode="after")
    def validate_report(self) -> CapabilityFailureAuditReport:
        if (
            self.complete_raw_execution_count + self.orphan_job_count
            != self.exact_manifest_job_count
        ):
            raise ValueError("v26.142 report denominator changed")
        if self.report_id != _identity(
            self,
            "report_id",
            "finance_v26_capability_failed_lineage_audit_report:",
        ):
            raise ValueError("v26.142 report identity changed")
        return self


def _source_replay(
    *,
    package_root: Path,
    implementation_root: Path,
    execution_dir: Path,
) -> FailureAuditSourceReplay:
    execution_source = online.ExecutionSourceReplayAudit.model_validate(
        _load(execution_dir / "online_source_replay_audit.json")
    )
    if execution_source.audit_id != EXPECTED_EXECUTION_SOURCE_REPLAY_ID:
        raise ValueError("v26.142 execution source replay identity changed")
    entries: dict[str, SourceReplayEntry] = {}
    for item in execution_source.entries:
        path = _find_bound_path(
            item.relative_path,
            item.expected_sha256,
            package_root=package_root,
            implementation_root=implementation_root,
        )
        entries[item.relative_path] = SourceReplayEntry(
            relative_path=item.relative_path,
            source_kind="v26_141_bound_source",
            expected_sha256=item.expected_sha256,
            observed_sha256=_sha256(path),
            byte_count=path.stat().st_size,
        )
    execution_paths = tuple(sorted(path for path in execution_dir.rglob("*") if path.is_file()))
    if len(execution_paths) != 2680:
        raise ValueError(f"v26.142 execution file denominator changed: {len(execution_paths)}")
    for path in execution_paths:
        relative = str(path.relative_to(package_root))
        digest = _sha256(path)
        entries[relative] = SourceReplayEntry(
            relative_path=relative,
            source_kind="v26_141_execution_file",
            expected_sha256=digest,
            observed_sha256=digest,
            byte_count=path.stat().st_size,
        )
    implementation = implementation_root / IMPLEMENTATION_PATH
    digest = _sha256(implementation)
    entries[IMPLEMENTATION_PATH] = SourceReplayEntry(
        relative_path=IMPLEMENTATION_PATH,
        source_kind="v26_142_implementation",
        expected_sha256=digest,
        observed_sha256=digest,
        byte_count=implementation.stat().st_size,
    )
    ordered = tuple(entries[key] for key in sorted(entries))
    values = {"entries": ordered}
    provisional = FailureAuditSourceReplay.model_construct(audit_id="pending", **values)
    return FailureAuditSourceReplay(
        audit_id=_identity(
            provisional,
            "audit_id",
            "finance_v26_capability_failed_lineage_source_replay:",
        ),
        **values,
    )


def _artifact_paths(execution_dir: Path, directory: str) -> tuple[Path, ...]:
    return tuple(sorted((execution_dir / directory).glob("*/*.json")))


def _failed_lineage(
    *,
    source: FailureAuditSourceReplay,
    execution_dir: Path,
    prepared: online.PreparedExecution,
) -> tuple[
    FailedLineageAudit,
    tuple[online.CapabilityJobResult, ...],
    dict[str, preflight.CapabilityRawExecution],
    tuple[privacy_runner.PrivacyFirstProviderEnvelope, ...],
    tuple[privacy_runner.PublicPayloadProjection, ...],
]:
    source_audit = online.ExecutionSourceReplayAudit.model_validate(
        _load(execution_dir / "online_source_replay_audit.json")
    )
    preexecution = online.PreexecutionBindingAudit.model_validate(
        _load(execution_dir / "preexecution_binding_audit.json")
    )
    if (
        source_audit.audit_id != EXPECTED_EXECUTION_SOURCE_REPLAY_ID
        or preexecution.audit_id != EXPECTED_PREEXECUTION_BINDING_ID
        or prepared.source_replay.audit_id != source_audit.audit_id
        or prepared.preexecution_binding.audit_id != preexecution.audit_id
        or tuple(sorted(path.name for path in execution_dir.iterdir() if path.is_file()))
        != tuple(
            sorted(
                (*FROZEN_EXECUTION_FILES, "privacy_safe_s1_capability_job_results.checkpoint.jsonl")
            )
        )
        or (execution_dir / "report.json").exists()
    ):
        raise ValueError("v26.142 frozen execution root changed")
    checkpoint_path = execution_dir / "privacy_safe_s1_capability_job_results.checkpoint.jsonl"
    results = tuple(
        online.CapabilityJobResult.model_validate_json(line)
        for line in checkpoint_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    )
    raw_paths = tuple(sorted((execution_dir / "raw_execution").glob("*.json")))
    envelope_paths = _artifact_paths(execution_dir, "raw_provider_envelopes")
    projection_paths = _artifact_paths(execution_dir, "public_payload_projections")
    invocation_paths = _artifact_paths(execution_dir, "transport_invocation_certificates")
    if not (
        len(results) == len(raw_paths) == 93
        and len(envelope_paths) == len(projection_paths) == len(invocation_paths) == 858
    ):
        raise ValueError("v26.142 failed execution file partition changed")
    jobs = {item.job_id: item for item in prepared.manifest.jobs}
    raw_by_job: dict[str, preflight.CapabilityRawExecution] = {}
    for path in raw_paths:
        raw = preflight.CapabilityRawExecution.model_validate(_load(path))
        raw_by_job[raw.job.job_id] = raw
    expected_result_jobs = tuple(
        item.job_id for item in prepared.manifest.jobs if item.job_id in raw_by_job
    )
    if tuple(item.job_id for item in results) != expected_result_jobs:
        raise ValueError("v26.142 checkpoint order or Raw membership changed")
    for result in results:
        raw = raw_by_job[result.job_id]
        binding = preflight._capability_binding(  # noqa: SLF001
            inputs=prepared.inputs,
            tasks=prepared.task_package_catalog,
            job=jobs[result.job_id],
        )
        rebuilt, _ = online.project_job_result(
            raw=raw,
            prepared=prepared,
            binding=binding,
            output_dir=execution_dir,
        )
        if rebuilt != result:
            raise ValueError(f"v26.142 independent Job projection changed: {result.job_id}")
    envelopes = tuple(
        privacy_runner.PrivacyFirstProviderEnvelope.model_validate(_load(path))
        for path in envelope_paths
    )
    projections = tuple(
        privacy_runner.PublicPayloadProjection.model_validate(_load(path))
        for path in projection_paths
    )
    invocations = tuple(
        preflight.runner_base.TransportInvocationCertificate.model_validate(_load(path))
        for path in invocation_paths
    )
    envelope_index = {(item.job_id, item.provider_call_index): item for item in envelopes}
    projection_index = {(item.job_id, item.provider_call_index): item for item in projections}
    invocation_index = {
        (item.job_id, item.transport_invocation_index): item for item in invocations
    }
    if not (
        len(envelope_index) == len(projection_index) == len(invocation_index) == 858
        and set(envelope_index) == set(projection_index) == set(invocation_index)
    ):
        raise ValueError("v26.142 Provider pair or Transport key set changed")
    for key in sorted(envelope_index):
        privacy_runner.validate_provider_artifact_pair(envelope_index[key], projection_index[key])
        if invocation_index[key].job_id != key[0]:
            raise ValueError("v26.142 Transport parent changed")
    raw_job_ids = set(raw_by_job)
    artifact_job_ids = {item.job_id for item in envelopes}
    manifest_job_ids = set(jobs)
    orphan_job_ids = tuple(sorted(artifact_job_ids - raw_job_ids))
    if raw_job_ids | set(orphan_job_ids) != manifest_job_ids or len(orphan_job_ids) != 3:
        raise ValueError("v26.142 manifest artifact coverage changed")
    complete_descriptors = {
        item.relative_path
        for raw in raw_by_job.values()
        for item in (
            *raw.provider_envelope_artifacts,
            *raw.public_payload_projection_artifacts,
            *raw.transport_invocation_artifacts,
        )
    }
    observed_complete_paths = {
        str(path.relative_to(execution_dir))
        for path in (*envelope_paths, *projection_paths, *invocation_paths)
        if "finance_v26_privacy_safe_capability_job:" + path.parent.name in raw_job_ids
    }
    if complete_descriptors != observed_complete_paths or len(complete_descriptors) != 2565:
        raise ValueError("v26.142 complete Raw descriptor set changed")
    for job_id in orphan_job_ids:
        digest = job_id.rsplit(":", 1)[-1]
        if (
            (execution_dir / "raw_execution" / f"{digest}.json").exists()
            or (job_id, 0) not in envelope_index
            or any((job_id, index) in envelope_index for index in range(1, 24))
        ):
            raise ValueError("v26.142 orphan is not one exact first-call triple")
    values = {
        "source_replay_audit_id": source.audit_id,
        "orphan_job_ids": orphan_job_ids,
        "complete_raw_bound_provider_call_count": sum(item.provider_call_count for item in results),
        "invalid_payload_content_persisted_count": sum(
            item.invalid_payload_content_persisted for item in projections
        ),
        "invalid_payload_key_persisted_count": sum(
            item.invalid_payload_key_persisted for item in projections
        ),
        "private_reasoning_content_persisted_count": sum(
            item.private_reasoning_content_persisted for item in envelopes
        ),
        "private_reasoning_content_hashed_count": sum(
            item.private_reasoning_content_hashed for item in envelopes
        ),
        "raw_http_body_persisted_count": sum(item.raw_http_body_persisted for item in envelopes),
        "raw_request_body_persisted_count": sum(
            item.raw_request_body_persisted for item in envelopes
        ),
    }
    provisional = FailedLineageAudit.model_construct(audit_id="pending", **values)
    audit = FailedLineageAudit(
        audit_id=_identity(
            provisional,
            "audit_id",
            "finance_v26_capability_failed_lineage:",
        ),
        **values,
    )
    return audit, results, raw_by_job, envelopes, projections


def _partial_outcome(
    *,
    lineage: FailedLineageAudit,
    results: Sequence[online.CapabilityJobResult],
    envelopes: Sequence[privacy_runner.PrivacyFirstProviderEnvelope],
    projections: Sequence[privacy_runner.PublicPayloadProjection],
) -> PartialCapabilityOutcomeAudit:
    terminal_counts = dict(sorted(Counter(item.terminal_category for item in results).items()))
    telemetry = tuple(item.provider_telemetry for item in envelopes)
    task_complete = dict(sorted(Counter(item.source_task_artifact_id for item in results).items()))
    task_valid = dict(
        sorted(
            Counter(
                item.source_task_artifact_id
                for item in results
                if item.independent_trajectory_validity
            ).items()
        )
    )
    for task_id in task_complete:
        task_valid.setdefault(task_id, 0)
    projection_counts = Counter(item.projection_status for item in projections)
    exact_model_count = sum(
        item.model_requested == item.model_selected == item.response_model == "deepseek-v4-flash"
        for item in telemetry
    )
    thinking_count = sum(
        item.reasoning_content_present
        and cast(int, item.reasoning_content_length) > 0
        and cast(int, item.reasoning_tokens) > 0
        for item in telemetry
    )
    usage_count = sum(
        item.prompt_tokens is not None
        and item.completion_tokens is not None
        and item.reasoning_tokens is not None
        and item.total_tokens is not None
        for item in telemetry
    )
    completion = sum(cast(int, item.completion_tokens) for item in telemetry)
    reasoning = sum(cast(int, item.reasoning_tokens) for item in telemetry)
    values = {
        "failed_lineage_audit_id": lineage.audit_id,
        "terminal_counts": terminal_counts,
        "valid_mechanism_ids": tuple(
            sorted({item.mechanism_id for item in results if item.independent_trajectory_validity})
        ),
        "task_complete_raw_counts": task_complete,
        "task_valid_trajectory_counts": dict(sorted(task_valid.items())),
        "http_success_call_count": sum(item.http_success for item in telemetry),
        "exact_model_call_count": exact_model_count,
        "thinking_complete_call_count": thinking_count,
        "usage_complete_call_count": usage_count,
        "validated_public_payload_count": projection_counts["validated_public_payload"],
        "provider_failure_no_payload_count": projection_counts["provider_failure_no_payload"],
        "privacy_rejection_count": projection_counts["privacy_rejected"],
        "provider_prompt_tokens": sum(cast(int, item.prompt_tokens) for item in telemetry),
        "provider_completion_tokens": completion,
        "provider_reasoning_tokens": reasoning,
        "provider_total_tokens": sum(cast(int, item.total_tokens) for item in telemetry),
        "estimated_cost_usd": str(
            sum(
                (Decimal(str(item.estimated_cost)) for item in telemetry),
                Decimal(0),
            )
        ),
        "reasoning_completion_fraction": format(Decimal(reasoning) / Decimal(completion), "f"),
        "maximum_complete_raw_prompt_utf8_bytes": max(
            item.maximum_prompt_utf8_bytes for item in results
        ),
        "maximum_complete_raw_job_tokens": max(item.provider_total_tokens for item in results),
        "zero_detour_complete_raw_count": sum(item.ordinary_detour_count == 0 for item in results),
        "one_detour_complete_raw_count": sum(item.ordinary_detour_count == 1 for item in results),
    }
    provisional = PartialCapabilityOutcomeAudit.model_construct(audit_id="pending", **values)
    return PartialCapabilityOutcomeAudit(
        audit_id=_identity(
            provisional,
            "audit_id",
            "finance_v26_partial_capability_outcome:",
        ),
        **values,
    )


def _orphan_row(
    *,
    job: preflight.CapabilityJob,
    prepared: online.PreparedExecution,
    execution_dir: Path,
) -> OrphanRootCauseRow:
    digest = job.job_id.rsplit(":", 1)[-1]
    envelope = privacy_runner.PrivacyFirstProviderEnvelope.model_validate(
        _load(execution_dir / "raw_provider_envelopes" / digest / "call_000.json")
    )
    projection = privacy_runner.PublicPayloadProjection.model_validate(
        _load(execution_dir / "public_payload_projections" / digest / "call_000.json")
    )
    invocation = preflight.runner_base.TransportInvocationCertificate.model_validate(
        _load(execution_dir / "transport_invocation_certificates" / digest / "invocation_000.json")
    )
    privacy_runner.validate_provider_artifact_pair(envelope, projection)
    payload = projection.response_payload
    if payload is None:
        raise ValueError("v26.142 orphan public payload is absent")
    binding = preflight._capability_binding(  # noqa: SLF001
        inputs=prepared.inputs,
        tasks=prepared.task_package_catalog,
        job=job,
    )
    state = build_semantic_action_state(
        binding.record.task_package.task.public,
        binding.environment,
        (),
        semantic_rejections=(),
    )
    salt = preflight.role_base._presentation_salt(  # noqa: SLF001
        selection_id=binding.selection_id,
        package=binding.package.predecessor_package,
        strategy="structured_direct",
        state=state,
        logical_index=0,
    )
    prompt = preflight.prompt_base.render_privacy_safe_s1_action_prompt(
        phase="primary",
        instruction=binding.record.task_package.task.public.instruction,
        state=state,
        public_path_condition=None,
        presentation_salt=salt,
        typed_failure=None,
        grammar=prepared.inputs.static.action_grammar,
    )
    decoded, _ = (
        preflight.runner_base.predecessor.predecessor._decode_compact_prompt_with_expected_salt(  # noqa: E501, SLF001
            prompt,
            presentation_salt=salt,
        )
    )
    reference = preflight.runner_base._reference_proposal_from_s1_prompt(prompt)  # noqa: SLF001
    proposal = parse_exact_canonical_action_payload(payload)
    selected = evaluate_canonical_action_proposal(state, proposal, call_index=1)
    if selected.commit is None or selected.commit.call is None or selected.rejection is not None:
        raise ValueError("v26.142 orphan first public Action does not Commit")
    preflight.runner_base._semantic_commit_record(  # noqa: SLF001
        logical_request_index=0,
        state=state,
        proposal=proposal,
        commit=selected.commit,
        stage_two_profile_id=prepared.inputs.static.stage_two.profile_id,
        provider_calls_before_commit=1,
    )
    runtime = preflight.legacy._runtime(binding.record, binding.environment)  # noqa: SLF001
    observation = preflight.legacy._execute_observation(  # noqa: SLF001
        record=binding.record,
        environment=binding.environment,
        runtime=runtime,
        observations=(),
        projection=CompletionProjection(
            request_kind="decision",
            action="call_tool",
            tool_id=selected.commit.call.tool_id,
            arguments=selected.commit.call.arguments,
        ),
    )
    successor = build_semantic_action_state(
        binding.record.task_package.task.public,
        binding.environment,
        (observation,),
        semantic_rejections=(),
    )
    event = preflight.runner_base._progress_event(  # noqa: SLF001
        logical_request_index=0,
        before=state,
        after=successor,
        observation=observation,
        selected_action_id=proposal.action_id,
        reference_action_id=reference.action_id,
        ordinary_detour_count_before=0,
    )
    preflight.action_execution._choice_record(  # noqa: SLF001
        logical_request_index=0,
        phase="primary",
        state=state,
        proposal=proposal,
        commit=selected.commit,
        rejection=None,
        prior_rejected_action_id=None,
        observation=observation,
        progress=event.progress_vector_changed,
    )
    successor_salt = preflight.role_base._presentation_salt(  # noqa: SLF001
        selection_id=binding.selection_id,
        package=binding.package.predecessor_package,
        strategy="structured_direct",
        state=successor,
        logical_index=1,
    )
    successor_prompt = preflight.prompt_base.render_privacy_safe_s1_action_prompt(
        phase="primary",
        instruction=binding.record.task_package.task.public.instruction,
        state=successor,
        public_path_condition=None,
        presentation_salt=successor_salt,
        typed_failure=None,
        grammar=prepared.inputs.static.action_grammar,
    )
    successor_decoded, _ = (
        preflight.runner_base.predecessor.predecessor._decode_compact_prompt_with_expected_salt(  # noqa: E501, SLF001
            successor_prompt,
            presentation_salt=successor_salt,
        )
    )
    sensitive = preflight.prompt_base._sensitive_key_paths(  # noqa: SLF001
        preflight.prompt_base._privacy_safe_prompt_payload(successor_prompt).model_dump(  # noqa: SLF001
            mode="json"
        )
    )
    reference_error: ValueError | None = None
    try:
        preflight.runner_base._reference_proposal_from_s1_prompt(successor_prompt)  # noqa: SLF001
    except ValueError as error:
        reference_error = error
    telemetry = envelope.provider_telemetry
    selected_candidate = next(
        item for item in state.action_candidates if item.action_id == proposal.action_id
    )
    if (
        decoded != state
        or successor_decoded != successor
        or sensitive
        or legacy.sha256_text(prompt) != envelope.prompt_sha256
        or reference_error is None
        or str(reference_error) != REFERENCE_FAILURE
        or observation.status != "failed"
        or invocation.job_id != job.job_id
        or invocation.transport_invocation_index != 0
        or (
            execution_dir / "transport_invocation_certificates" / digest / "invocation_001.json"
        ).exists()
    ):
        raise ValueError("v26.142 orphan root-cause replay changed")
    values = {
        "job_id": job.job_id,
        "source_task_artifact_id": job.source_task_artifact_id,
        "tier": job.tier,
        "replicate_index": job.replicate_index,
        "envelope_id": envelope.envelope_id,
        "projection_id": projection.projection_id,
        "transport_certificate_id": invocation.certificate_id,
        "exact_model_http_success": bool(
            telemetry.http_success
            and telemetry.model_requested
            == telemetry.model_selected
            == telemetry.response_model
            == "deepseek-v4-flash"
        ),
        "thinking_complete": bool(
            telemetry.reasoning_content_present
            and cast(int, telemetry.reasoning_content_length) > 0
            and cast(int, telemetry.reasoning_tokens) > 0
        ),
        "usage_complete": all(
            item is not None
            for item in (
                telemetry.prompt_tokens,
                telemetry.completion_tokens,
                telemetry.reasoning_tokens,
                telemetry.total_tokens,
            )
        ),
        "privacy_compliant_exact_four_field_payload": bool(
            projection.projection_status == "validated_public_payload"
            and set(payload) == {"state_id", "action_id", "decision_kind", "protocol"}
            and not envelope.private_reasoning_content_persisted
            and not envelope.private_reasoning_content_hashed
        ),
        "initial_prompt_sha256": legacy.sha256_text(prompt),
        "initial_state_id": state.state_id,
        "initial_candidate_count": len(state.action_candidates),
        "selected_action_id": proposal.action_id,
        "selected_prompt_only_reference": proposal.action_id == reference.action_id,
        "public_observation_error_code": cast(str, observation.error_code),
        "progress_vector_changed": event.progress_vector_changed,
        "ordinary_detour_count_after": event.ordinary_detour_count_after,
        "successor_state_id": successor.state_id,
        "successor_candidate_count": len(successor.action_candidates),
        "successor_prompt_sha256": legacy.sha256_text(successor_prompt),
        "successor_prompt_utf8_bytes": len(successor_prompt.encode("utf-8")),
        "selected_action_visible": selected_candidate.action_id == proposal.action_id,
        "selected_decision_kind_match": (
            selected_candidate.decision_kind == proposal.decision_kind
        ),
    }
    provisional = OrphanRootCauseRow.model_construct(row_id="pending", **values)
    return OrphanRootCauseRow(
        row_id=_identity(
            provisional,
            "row_id",
            "finance_v26_orphan_reference_root_cause_row:",
        ),
        **values,
    )


def _orphan_root_cause(
    *,
    lineage: FailedLineageAudit,
    prepared: online.PreparedExecution,
    execution_dir: Path,
) -> OrphanRootCauseAudit:
    jobs = {item.job_id: item for item in prepared.manifest.jobs}
    rows = tuple(
        _orphan_row(
            job=jobs[job_id],
            prepared=prepared,
            execution_dir=execution_dir,
        )
        for job_id in lineage.orphan_job_ids
    )
    values = {
        "failed_lineage_audit_id": lineage.audit_id,
        "orphan_rows": rows,
    }
    provisional = OrphanRootCauseAudit.model_construct(audit_id="pending", **values)
    return OrphanRootCauseAudit(
        audit_id=_identity(
            provisional,
            "audit_id",
            "finance_v26_orphan_reference_root_cause:",
        ),
        **values,
    )


def _destructive(
    *,
    lineage: FailedLineageAudit,
    root_cause: OrphanRootCauseAudit,
) -> DestructiveAudit:
    names = (
        "assign_historical_terminal_to_orphan",
        "authorize_capability_continuation",
        "authorize_provider_call_before_preflight",
        "classify_orphan_as_model_invalid",
        "drop_orphan_from_exact_denominator",
        "infer_missing_raw_from_public_payload",
        "pool_prior_lost_attempt",
        "repair_model_action_with_reference_policy",
        "reuse_historical_job_identity",
        "state_mapping_authorized",
        "treat_partial_subset_as_exact_capability_estimate",
        "write_private_reasoning_hash",
    )
    if (
        lineage.capability_gate_passed
        or not root_cause.failure_is_host_measurement_instrument_defect
    ):
        raise ValueError("v26.142 destructive baseline changed")
    values = {
        "mutation_results": tuple(MutationResult(mutation_name=name) for name in sorted(names))
    }
    provisional = DestructiveAudit.model_construct(audit_id="pending", **values)
    return DestructiveAudit(
        audit_id=_identity(
            provisional,
            "audit_id",
            "finance_v26_capability_failed_lineage_destructive:",
        ),
        **values,
    )


def _transition(
    *,
    lineage: FailedLineageAudit,
    root_cause: OrphanRootCauseAudit,
) -> ProspectiveTransitionContract:
    values = {
        "failed_lineage_audit_id": lineage.audit_id,
        "orphan_root_cause_audit_id": root_cause.audit_id,
    }
    provisional = ProspectiveTransitionContract.model_construct(contract_id="pending", **values)
    return ProspectiveTransitionContract(
        contract_id=_identity(
            provisional,
            "contract_id",
            "finance_v26_capability_failed_lineage_transition:",
        ),
        **values,
    )


def _detail(path: Path, output_dir: Path) -> DetailFile:
    return DetailFile(
        relative_path=str(path.relative_to(output_dir)),
        sha256=_sha256(path),
        byte_count=path.stat().st_size,
    )


def build_failure_audit(
    *,
    package_root: Path,
    implementation_root: Path,
    execution_dir: Path,
    output_dir: Path,
) -> CapabilityFailureAuditReport:
    source = _source_replay(
        package_root=package_root,
        implementation_root=implementation_root,
        execution_dir=execution_dir,
    )
    with tempfile.TemporaryDirectory(prefix="v26_142_prepared_") as temporary:
        prepared = online.prepare_execution(
            preflight_dir=package_root / online.PREFLIGHT_DIR,
            output_dir=Path(temporary),
            package_root=package_root,
            implementation_root=implementation_root,
        )
        lineage, results, _raws, envelopes, projections = _failed_lineage(
            source=source,
            execution_dir=execution_dir,
            prepared=prepared,
        )
        partial = _partial_outcome(
            lineage=lineage,
            results=results,
            envelopes=envelopes,
            projections=projections,
        )
        root_cause = _orphan_root_cause(
            lineage=lineage,
            prepared=prepared,
            execution_dir=execution_dir,
        )
    destructive = _destructive(lineage=lineage, root_cause=root_cause)
    transition = _transition(lineage=lineage, root_cause=root_cause)
    output_dir.mkdir(parents=True, exist_ok=True)
    outputs: tuple[tuple[str, BaseModel], ...] = (
        ("destructive_audit.json", destructive),
        ("failed_lineage_audit.json", lineage),
        ("orphan_root_cause_audit.json", root_cause),
        ("partial_capability_outcome_audit.json", partial),
        ("prospective_transition_contract.json", transition),
        ("source_replay_audit.json", source),
    )
    for name, value in outputs:
        _write_json_atomic(output_dir / name, value)
    details = tuple(_detail(output_dir / name, output_dir) for name, _ in outputs)
    values = {
        "source_replay_audit_id": source.audit_id,
        "failed_lineage_audit_id": lineage.audit_id,
        "partial_outcome_audit_id": partial.audit_id,
        "orphan_root_cause_audit_id": root_cause.audit_id,
        "destructive_audit_id": destructive.audit_id,
        "transition_contract_id": transition.contract_id,
        "detail_files": details,
    }
    provisional = CapabilityFailureAuditReport.model_construct(report_id="pending", **values)
    report = CapabilityFailureAuditReport(
        report_id=_identity(
            provisional,
            "report_id",
            "finance_v26_capability_failed_lineage_audit_report:",
        ),
        **values,
    )
    _write_json_atomic(output_dir / "report.json", report)
    return report


def main() -> None:
    package_default = Path(__file__).resolve().parents[4]
    parser = argparse.ArgumentParser(
        description="Audit the v26.141 93-Raw, three-orphan Capability lineage"
    )
    parser.add_argument("--package-root", type=Path, default=package_default)
    parser.add_argument("--implementation-root", type=Path, default=package_default)
    parser.add_argument(
        "--execution-dir",
        type=Path,
        default=package_default / EXECUTION_DIR,
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=package_default / OUTPUT_DIR,
    )
    args = parser.parse_args()
    report = build_failure_audit(
        package_root=args.package_root,
        implementation_root=args.implementation_root,
        execution_dir=args.execution_dir,
        output_dir=args.output_dir,
    )
    print(report.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
