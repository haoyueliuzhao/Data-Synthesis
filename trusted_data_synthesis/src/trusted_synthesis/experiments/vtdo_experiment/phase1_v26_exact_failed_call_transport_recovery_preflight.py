from __future__ import annotations

import argparse
import json
import tempfile
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final, Literal, cast

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_exact_final_semantic_action_calibration_online as historical_execution,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_exact_final_semantic_action_postrun_audit as historical_audit,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_final_grammar_privacy_rematerialization as static_stage,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_privacy_first_exact_final_execution as historical_runner,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_privacy_first_exact_final_runner_preflight as historical_preflight,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_semantic_action_calibration_execution as semantic_execution,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_two_stage_semantic_proposal_execution as legacy,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_two_stage_semantic_proposal_calibration_execution import (  # noqa: E501
    _completed_verification,
)
from trusted_synthesis.hashing import canonical_hash
from trusted_synthesis.runtime.agent.compact_budget_prompt import render_compact_final_prompt
from trusted_synthesis.runtime.agent.prospective_exact_final_response_grammar import (
    FinalResponseHostEnvelope,
    make_final_response_host_envelope,
    render_exact_final_primary_prompt,
)
from trusted_synthesis.runtime.agent.prospective_semantic_action_protocol import (
    CanonicalActionCommit,
    PublicSemanticRejectionObservation,
    SemanticActionState,
    build_semantic_action_state,
    evaluate_canonical_action_proposal,
)
from trusted_synthesis.runtime.agent.prospective_semantic_action_response_grammar import (
    parse_exact_canonical_action_payload,
    render_exact_canonical_action_prompt,
    render_exact_canonical_action_semantic_recovery_prompt,
)
from trusted_synthesis.runtime.agent.prospective_thinking_completion import CompletionProjection
from trusted_synthesis.runtime.tools import AgentToolObservation

RUN_ID: Final = "finance_v26_126_exact_failed_call_transport_recovery_preflight_v1_20260823"
OUTPUT_DIR: Final = (
    "artifacts/vtdo_experiment/"
    "finance_v26_126_exact_failed_call_transport_recovery_preflight_v1_20260823"
)
HISTORICAL_EXECUTION_DIR: Final = historical_execution.OUTPUT_DIR
HISTORICAL_AUDIT_DIR: Final = historical_audit.OUTPUT_DIR
IMPLEMENTATION_PATH: Final = (
    "src/trusted_synthesis/experiments/vtdo_experiment/"
    "phase1_v26_exact_failed_call_transport_recovery_preflight.py"
)
EXPECTED_AUDIT_REPORT_ID: Final = (
    "finance_v26_exact_final_postrun_audit_report:"
    "76852aa99e92673608e44286d2545dee0062246a47d29c7254053dfb8e560c03"
)
EXPECTED_AUDIT_SOURCE_REPLAY_ID: Final = (
    "finance_v26_exact_final_postrun_source_replay:"
    "5e6503a95107ffbcd15861ae1e2f87d825782cb81b4a84a0df70b26796ead3e7"
)
EXPECTED_PROVIDER_FAILURE_AUDIT_ID: Final = (
    "finance_v26_exact_final_provider_failure_audit:"
    "e0633b4f618be2967f5eb6b63c1e7dc8c00eac39b94d05c3804deb9613c2b20a"
)
EXPECTED_AUDIT_TRANSITION_ID: Final = (
    "finance_v26_exact_final_postrun_transition:"
    "2ee5689a7248012a676e993f37df6bfca0a432579e5787334ae6a990d2439524"
)
EXPECTED_HISTORICAL_RUNNER_ID: Final = (
    "finance_v26_privacy_first_runner_contract:"
    "a1d2c225906c57742340cf34c07e6d8643bbc4ef293bcf357cecd29b13221a66"
)
EXPECTED_HISTORICAL_OUTCOME_ID: Final = (
    "finance_v26_exact_final_outcome_measurement:"
    "60d018f6f0e9701cc2e5860ddad2649882bacbc4b30b30405fa9a764b1e975e9"
)
EXPECTED_FINAL_GRAMMAR_ID: Final = (
    "prospective_exact_final_response_grammar:"
    "5b1207394aa4088b6e561243580d45997feca8156185d452f21d738683833403"
)
EXPECTED_STAGE_ONE_PROFILE_ID: Final = (
    "finance_v26_stage_one_thinking_profile:"
    "9d89a504a3fee25a60ae392e10cab063b0604f36fb0672e19bc8f1ec45bb3045"
)
EXPECTED_STAGE_TWO_PROFILE_ID: Final = (
    "finance_v26_stage_two_commit_profile:"
    "024f2543b11f26ebc40000c7342d6ff6b4067d78b3dc11be466514fc765734a5"
)
EXPECTED_RESOURCE_ID: Final = (
    "finance_v26_final_grammar_resource_contract:"
    "381e18dff5a538c50cc06aaae9c6c81d110d8214b8c7d3800820d4eb3f09e43c"
)
NEXT_STAGE: Final = "exact_failed_call_transport_recovery_execution_only"
HISTORICAL_AUDIT_OUTPUTS: Final = (
    "source_replay_audit.json",
    "raw_lineage_reaudit.json",
    "provider_failure_audit.json",
    "final_outcome_audit.json",
    "destructive_audit.json",
    "prospective_transition_contract.json",
    "report.json",
)

RecoveryCallRole = Literal[
    "exact_failed_call_replacement",
    "primary_continuation",
    "abi_rescue",
    "semantic_recovery",
    "final_primary",
    "final_abi_rescue",
]


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


def _identity(value: BaseModel, field: str, prefix: str) -> str:
    return canonical_hash(value.model_dump(mode="json", exclude={field}), prefix=prefix)


class SourceReplayEntry(FrozenModel):
    relative_path: str = Field(min_length=1)
    source_kind: Literal[
        "v26_125_transitive_source",
        "v26_125_output",
        "v26_126_implementation",
    ]
    expected_sha256: str = Field(min_length=64, max_length=64)
    observed_sha256: str = Field(min_length=64, max_length=64)
    byte_count: int = Field(gt=0)
    passed: Literal[True] = True


class RecoverySourceReplayAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    predecessor_audit_report_id: str = EXPECTED_AUDIT_REPORT_ID
    predecessor_source_replay_id: str = EXPECTED_AUDIT_SOURCE_REPLAY_ID
    predecessor_transitive_file_count: Literal[2965] = 2965
    predecessor_output_file_count: Literal[7] = 7
    implementation_file_count: Literal[1] = 1
    replayed_file_count: Literal[2973] = 2973
    replay_pass_count: Literal[2973] = 2973
    entries: tuple[SourceReplayEntry, ...] = Field(min_length=2973, max_length=2973)
    credential_lookup_attempted: Literal[False] = False
    model_client_constructed: Literal[False] = False
    provider_calls: Literal[0] = 0
    stage_two_provider_calls: Literal[0] = 0
    gpu_jobs: Literal[0] = 0
    status: Literal["passed"] = "passed"
    schema_version: Literal["finance_v26_transport_recovery_source_replay.v1"] = (
        "finance_v26_transport_recovery_source_replay.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> RecoverySourceReplayAudit:
        paths = tuple(item.relative_path for item in self.entries)
        if paths != tuple(sorted(set(paths))):
            raise ValueError("v26.126 source replay paths changed")
        if any(item.expected_sha256 != item.observed_sha256 for item in self.entries):
            raise ValueError("v26.126 source replay contains a hash mismatch")
        if self.audit_id != _identity(
            self, "audit_id", "finance_v26_transport_recovery_source_replay:"
        ):
            raise ValueError("v26.126 source replay identity changed")
        return self


class ExactFailedCallRecoveryContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    predecessor_audit_report_id: str = EXPECTED_AUDIT_REPORT_ID
    predecessor_provider_failure_audit_id: str = EXPECTED_PROVIDER_FAILURE_AUDIT_ID
    predecessor_transition_contract_id: str = EXPECTED_AUDIT_TRANSITION_ID
    historical_runner_contract_id: str = EXPECTED_HISTORICAL_RUNNER_ID
    historical_outcome_measurement_contract_id: str = EXPECTED_HISTORICAL_OUTCOME_ID
    historical_execution_report_id: str = historical_audit.EXPECTED_EXECUTION_REPORT_ID
    recovery_candidate_ids: tuple[str, ...] = Field(min_length=10, max_length=10)
    exact_recovery_candidate_count: Literal[10] = 10
    frozen_historical_model_outcome_count: Literal[22] = 22
    successful_prefix_zero_generation_replay_required: Literal[True] = True
    exact_failed_request_rebinding_required: Literal[True] = True
    replacement_response_per_failed_call_maximum: Literal[1] = 1
    replacement_failure_retry_allowed: Literal[False] = False
    original_failed_call_usage_imputation_allowed: Literal[False] = False
    original_failed_http_success_usage_unknown_count: Literal[8] = 8
    original_failed_no_http_usage_unknown_count: Literal[2] = 2
    trajectory_accounting_starts_at_successful_prefix_usage: Literal[True] = True
    provider_billing_and_trajectory_accounting_separate: Literal[True] = True
    continuation_uses_original_remaining_resource_bound: Literal[True] = True
    continuation_uses_original_abi_rescue_bound: Literal[True] = True
    continuation_uses_original_semantic_recovery_bound: Literal[True] = True
    semantic_action_protocol_change_allowed: Literal[False] = False
    candidate_space_change_allowed: Literal[False] = False
    final_grammar_change_allowed: Literal[False] = False
    model_thinking_completion_or_rollout_change_allowed: Literal[False] = False
    historical_job_rerun_or_reclassification_allowed: Literal[False] = False
    historical_model_outcome_rerun_or_reclassification_allowed: Literal[False] = False
    stage_two_provider_call_upper_bound: Literal[0] = 0
    provider_calls_authorized: Literal[False] = False
    schema_version: Literal["finance_v26_exact_failed_call_recovery_contract.v1"] = (
        "finance_v26_exact_failed_call_recovery_contract.v1"
    )

    @model_validator(mode="after")
    def validate_contract(self) -> ExactFailedCallRecoveryContract:
        if self.recovery_candidate_ids != tuple(sorted(set(self.recovery_candidate_ids))):
            raise ValueError("v26.126 Recovery Candidate set changed")
        if self.contract_id != _identity(
            self, "contract_id", "finance_v26_exact_failed_call_recovery_contract:"
        ):
            raise ValueError("v26.126 Recovery Contract identity changed")
        return self


class ExactFailedCallRecoveryJob(FrozenModel):
    recovery_job_id: str = Field(min_length=1)
    recovery_contract_id: str = Field(min_length=1)
    candidate: historical_audit.FailedCallRecoveryCandidate
    historical_job: static_stage.FinalGrammarJob
    historical_raw_execution_id: str = Field(min_length=1)
    historical_raw_execution_artifact: legacy.RawFileDescriptor
    historical_job_result_id: str = Field(min_length=1)
    successful_prefix_provider_call_count: int = Field(ge=0, le=2)
    successful_prefix_cumulative_tokens: int = Field(ge=0)
    exact_failed_request_prompt_sha256: str = Field(min_length=64, max_length=64)
    exact_failed_dynamic_certificate_id: str = Field(min_length=1)
    exact_failed_request_binding_certificate_id: str = Field(min_length=1)
    exact_failed_resource_certificate_id: str = Field(min_length=1)
    replacement_response_authorization_count: Literal[1] = 1
    successful_prefix_provider_calls_authorized: Literal[0] = 0
    historical_job_identity_retained_only_as_parent: Literal[True] = True
    historical_job_reclassified: Literal[False] = False
    schema_version: Literal["finance_v26_exact_failed_call_recovery_job.v1"] = (
        "finance_v26_exact_failed_call_recovery_job.v1"
    )

    @model_validator(mode="after")
    def validate_job(self) -> ExactFailedCallRecoveryJob:
        candidate = self.candidate
        if (
            candidate.historical_job_id != self.historical_job.job_id
            or candidate.successful_prefix_provider_call_count
            != self.successful_prefix_provider_call_count
            or candidate.cumulative_provider_tokens_before_failure
            != self.successful_prefix_cumulative_tokens
            or candidate.request_prompt_sha256 != self.exact_failed_request_prompt_sha256
            or candidate.dynamic_certificate_id != self.exact_failed_dynamic_certificate_id
            or candidate.request_binding_certificate_id
            != self.exact_failed_request_binding_certificate_id
            or candidate.resource_certificate_id != self.exact_failed_resource_certificate_id
        ):
            raise ValueError("v26.126 RecoveryJob changed its frozen failed request")
        if self.recovery_job_id != _identity(
            self, "recovery_job_id", "finance_v26_exact_failed_call_recovery_job:"
        ):
            raise ValueError("v26.126 RecoveryJob identity changed")
        return self


class ExactFailedCallRecoveryManifest(FrozenModel):
    manifest_id: str = Field(min_length=1)
    recovery_contract_id: str = Field(min_length=1)
    jobs: tuple[ExactFailedCallRecoveryJob, ...] = Field(min_length=10, max_length=10)
    exact_job_denominator: Literal[10] = 10
    fresh_recovery_job_identity_count: Literal[10] = 10
    historical_job_identity_overlap_count: Literal[0] = 0
    schema_version: Literal["finance_v26_exact_failed_call_recovery_manifest.v1"] = (
        "finance_v26_exact_failed_call_recovery_manifest.v1"
    )

    @model_validator(mode="after")
    def validate_manifest(self) -> ExactFailedCallRecoveryManifest:
        job_ids = tuple(item.recovery_job_id for item in self.jobs)
        historical = {item.historical_job.job_id for item in self.jobs}
        if job_ids != tuple(sorted(set(job_ids))) or len(historical) != 10:
            raise ValueError("v26.126 Recovery Manifest denominator changed")
        if any(item.recovery_contract_id != self.recovery_contract_id for item in self.jobs):
            raise ValueError("v26.126 Recovery Manifest parent changed")
        if set(job_ids) & historical:
            raise ValueError("v26.126 RecoveryJob reused a historical Job identity")
        if self.manifest_id != _identity(
            self, "manifest_id", "finance_v26_exact_failed_call_recovery_manifest:"
        ):
            raise ValueError("v26.126 Recovery Manifest identity changed")
        return self


class ExactFailedCallRecoveryRunnerContract(FrozenModel):
    runner_contract_id: str = Field(min_length=1)
    recovery_contract_id: str = Field(min_length=1)
    recovery_manifest_id: str = Field(min_length=1)
    historical_runner_contract_id: str = EXPECTED_HISTORICAL_RUNNER_ID
    semantic_action_protocol_id: str = static_stage.EXPECTED_ACTION_PROTOCOL_ID
    semantic_action_response_grammar_id: str = static_stage.EXPECTED_ACTION_GRAMMAR_ID
    exact_final_response_grammar_id: str = Field(min_length=1)
    candidate_space_authority_audit_id: str = static_stage.EXPECTED_CANDIDATE_AUDIT_ID
    stage_one_profile_id: str = Field(min_length=1)
    stage_two_profile_id: str = Field(min_length=1)
    resource_contract_id: str = Field(min_length=1)
    exact_recovery_job_denominator: Literal[10] = 10
    exact_request_completion_bound_tokens: Literal[16384] = 16384
    provider_accounting_margin_tokens: Literal[1] = 1
    rollout_upper_bound_tokens: Literal[400000] = 400000
    maximum_primary_stage_one_requests: Literal[11] = 11
    maximum_combined_stage_one_provider_calls: Literal[12] = 12
    maximum_replacement_calls_per_recovery_job: Literal[1] = 1
    maximum_abi_rescue_calls: Literal[1] = 1
    maximum_semantic_recovery_calls: Literal[1] = 1
    prefix_replay_provider_calls: Literal[0] = 0
    raw_only_recovery: Literal[True] = True
    orphan_provider_artifact_fails_closed: Literal[True] = True
    privacy_first_envelope_before_projection: Literal[True] = True
    private_reasoning_persistence_allowed: Literal[False] = False
    original_failed_usage_imputation_allowed: Literal[False] = False
    stage_two_provider_call_upper_bound: Literal[0] = 0
    runner_implemented: Literal[True] = True
    empirical_execution_authorized: Literal[False] = False
    schema_version: Literal["finance_v26_exact_failed_call_recovery_runner_contract.v1"] = (
        "finance_v26_exact_failed_call_recovery_runner_contract.v1"
    )

    @model_validator(mode="after")
    def validate_contract(self) -> ExactFailedCallRecoveryRunnerContract:
        if (
            self.exact_final_response_grammar_id != EXPECTED_FINAL_GRAMMAR_ID
            or self.stage_one_profile_id != EXPECTED_STAGE_ONE_PROFILE_ID
            or self.stage_two_profile_id != EXPECTED_STAGE_TWO_PROFILE_ID
            or self.resource_contract_id != EXPECTED_RESOURCE_ID
        ):
            raise ValueError("v26.126 frozen generation route changed")
        if self.runner_contract_id != _identity(
            self,
            "runner_contract_id",
            "finance_v26_exact_failed_call_recovery_runner_contract:",
        ):
            raise ValueError("v26.126 Recovery Runner Contract identity changed")
        return self


class RecoveryInvocationCertificate(FrozenModel):
    certificate_id: str = Field(min_length=1)
    recovery_runner_contract_id: str = Field(min_length=1)
    recovery_job_id: str = Field(min_length=1)
    recovery_candidate_id: str = Field(min_length=1)
    historical_job_id: str = Field(min_length=1)
    recovery_provider_call_index: int = Field(ge=0, le=11)
    combined_trajectory_call_index: int = Field(ge=0, le=11)
    logical_request_index: int = Field(ge=0, le=10)
    call_role: RecoveryCallRole
    exact_failed_call_replacement: bool
    request_kind: legacy.StageOneRequestKind
    public_attempt_phase: historical_runner.PublicAttemptPhase
    prompt_sha256: str = Field(min_length=64, max_length=64)
    public_state_id: str = Field(min_length=1)
    historical_dynamic_certificate_id: str = Field(min_length=1)
    request_binding_certificate_id: str = Field(min_length=1)
    resource_certificate_id: str = Field(min_length=1)
    cumulative_trajectory_tokens_before: int = Field(ge=0)
    original_failed_call_usage_included: Literal[False] = False
    successful_prefix_replayed_before_certificate: Literal[True] = True
    provider_calls_before_certificate: int = Field(ge=0, le=11)
    stage_two_provider_calls_before_certificate: Literal[0] = 0
    schema_version: Literal["finance_v26_recovery_invocation_certificate.v1"] = (
        "finance_v26_recovery_invocation_certificate.v1"
    )

    @model_validator(mode="after")
    def validate_certificate(self) -> RecoveryInvocationCertificate:
        if self.provider_calls_before_certificate != self.recovery_provider_call_index:
            raise ValueError("v26.126 pre-call authorization ordering changed")
        if self.exact_failed_call_replacement != (self.recovery_provider_call_index == 0):
            raise ValueError("v26.126 replacement authority is not first and single-use")
        if self.exact_failed_call_replacement != (
            self.call_role == "exact_failed_call_replacement"
        ):
            raise ValueError("v26.126 replacement call role changed")
        if self.certificate_id != _identity(
            self,
            "certificate_id",
            "finance_v26_recovery_invocation_certificate:",
        ):
            raise ValueError("v26.126 invocation-certificate identity changed")
        return self


class RecoveryProviderEnvelope(FrozenModel):
    envelope_id: str = Field(min_length=1)
    recovery_runner_contract_id: str = Field(min_length=1)
    recovery_job_id: str = Field(min_length=1)
    recovery_candidate_id: str = Field(min_length=1)
    historical_job_id: str = Field(min_length=1)
    recovery_provider_call_index: int = Field(ge=0, le=11)
    combined_trajectory_call_index: int = Field(ge=0, le=11)
    logical_request_index: int = Field(ge=0, le=10)
    request_kind: legacy.StageOneRequestKind
    public_attempt_phase: historical_runner.PublicAttemptPhase
    call_role: RecoveryCallRole
    prompt_sha256: str = Field(min_length=64, max_length=64)
    invocation_certificate: RecoveryInvocationCertificate
    historical_dynamic_certificate: historical_runner.PrivacyFirstDynamicRequestCertificate
    request_binding_certificate: legacy.StageOneRequestBindingCertificate
    resource_certificate_id: str = Field(min_length=1)
    final_response_host_envelope_id: str | None = None
    provider_telemetry: legacy.ModelCallTelemetry
    failure_artifact: legacy.ProspectiveThinkingFailureArtifact | None = None
    public_content_hash: str | None = None
    public_content_length: int | None = Field(default=None, ge=0)
    payload_content_persisted: Literal[False] = False
    persisted_before_payload_validation: Literal[True] = True
    original_failed_call_usage_imputed: Literal[False] = False
    private_reasoning_content_persisted: Literal[False] = False
    private_reasoning_content_hashed: Literal[False] = False
    raw_http_body_persisted: Literal[False] = False
    raw_request_body_persisted: Literal[False] = False
    stage_two_provider_call_count: Literal[0] = 0
    schema_version: Literal["finance_v26_recovery_provider_envelope.v1"] = (
        "finance_v26_recovery_provider_envelope.v1"
    )

    @model_validator(mode="after")
    def validate_envelope(self) -> RecoveryProviderEnvelope:
        cert = self.invocation_certificate
        dynamic = self.historical_dynamic_certificate
        telemetry = self.provider_telemetry
        if (
            cert.recovery_runner_contract_id != self.recovery_runner_contract_id
            or cert.recovery_job_id != self.recovery_job_id
            or cert.recovery_candidate_id != self.recovery_candidate_id
            or cert.historical_job_id != self.historical_job_id
            or cert.recovery_provider_call_index != self.recovery_provider_call_index
            or cert.combined_trajectory_call_index != self.combined_trajectory_call_index
            or cert.logical_request_index != self.logical_request_index
            or cert.call_role != self.call_role
            or cert.prompt_sha256 != self.prompt_sha256
            or dynamic.certificate_id != cert.historical_dynamic_certificate_id
            or self.request_binding_certificate.certificate_id
            != cert.request_binding_certificate_id
            or self.resource_certificate_id != cert.resource_certificate_id
            or telemetry.request_hash != self.prompt_sha256
            or self.public_content_hash != telemetry.response_hash
            or self.public_content_length != telemetry.response_content_length
        ):
            raise ValueError("v26.126 Recovery Envelope binding changed")
        if self.envelope_id != _identity(
            self,
            "envelope_id",
            "finance_v26_recovery_provider_envelope:",
        ):
            raise ValueError("v26.126 Recovery Envelope identity changed")
        return self


class RecoveryPayloadProjection(FrozenModel):
    projection_id: str = Field(min_length=1)
    recovery_provider_envelope_id: str = Field(min_length=1)
    recovery_job_id: str = Field(min_length=1)
    recovery_provider_call_index: int = Field(ge=0, le=11)
    request_kind: legacy.StageOneRequestKind
    projection_status: historical_runner.PayloadProjectionStatus
    response_payload: dict[str, Any] | None = None
    failure_family: str | None = None
    failure_subtype: str | None = None
    validation_performed_after_envelope_persistence: Literal[True] = True
    invalid_payload_content_persisted: Literal[False] = False
    invalid_payload_key_persisted: Literal[False] = False
    private_reasoning_content_persisted: Literal[False] = False
    schema_version: Literal["finance_v26_recovery_payload_projection.v1"] = (
        "finance_v26_recovery_payload_projection.v1"
    )

    @model_validator(mode="after")
    def validate_projection(self) -> RecoveryPayloadProjection:
        if self.projection_status == "validated_public_payload":
            if (
                self.response_payload is None
                or self.failure_family is not None
                or self.failure_subtype is not None
                or legacy.contains_private_reasoning(self.response_payload)
            ):
                raise ValueError("v26.126 validated Projection is not public")
        elif self.response_payload is not None:
            raise ValueError("v26.126 rejected or absent content was persisted")
        if self.projection_status == "privacy_rejected":
            if (
                self.failure_family != "payload_privacy_failure"
                or self.failure_subtype != "public_payload_omitted_after_privacy_rejection"
            ):
                raise ValueError("v26.126 privacy Projection exposes rejected detail")
        elif self.projection_status == "provider_failure_no_payload":
            if self.failure_family != "provider_or_completion_failure":
                raise ValueError("v26.126 no-payload Projection changed")
        if self.projection_id != _identity(
            self,
            "projection_id",
            "finance_v26_recovery_payload_projection:",
        ):
            raise ValueError("v26.126 Recovery Projection identity changed")
        return self


def validate_recovery_provider_pair(
    envelope: RecoveryProviderEnvelope,
    projection: RecoveryPayloadProjection,
) -> None:
    if (
        projection.recovery_provider_envelope_id != envelope.envelope_id
        or projection.recovery_job_id != envelope.recovery_job_id
        or projection.recovery_provider_call_index != envelope.recovery_provider_call_index
        or projection.request_kind != envelope.request_kind
    ):
        raise ValueError("v26.126 Recovery Envelope/Projection parent changed")


class SuccessfulPrefixReplay(FrozenModel):
    replay_id: str = Field(min_length=1)
    recovery_job_id: str = Field(min_length=1)
    recovery_candidate_id: str = Field(min_length=1)
    historical_job_id: str = Field(min_length=1)
    historical_raw_execution_id: str = Field(min_length=1)
    successful_prefix_provider_call_count: int = Field(ge=0, le=2)
    successful_prefix_provider_envelope_ids: tuple[str, ...]
    successful_prefix_attempt_ids: tuple[str, ...]
    successful_prefix_choice_ids: tuple[str, ...]
    successful_prefix_commit_ids: tuple[str, ...]
    successful_prefix_observation_ids: tuple[str, ...]
    successful_prefix_cumulative_tokens: int = Field(ge=0)
    exact_failed_logical_request_index: int = Field(ge=0, le=2)
    exact_failed_public_state_id: str = Field(min_length=1)
    exact_failed_prompt_sha256: str = Field(min_length=64, max_length=64)
    exact_failed_dynamic_certificate_id: str = Field(min_length=1)
    exact_failed_request_binding_certificate_id: str = Field(min_length=1)
    exact_failed_resource_certificate_id: str = Field(min_length=1)
    runtime_observation_rebuild_count: int = Field(ge=0, le=2)
    historical_prefix_provider_calls_reissued: Literal[0] = 0
    historical_failed_call_reissued: Literal[0] = 0
    original_failed_call_usage_imputed: Literal[False] = False
    status: Literal["passed"] = "passed"
    schema_version: Literal["finance_v26_successful_prefix_replay.v1"] = (
        "finance_v26_successful_prefix_replay.v1"
    )

    @model_validator(mode="after")
    def validate_replay(self) -> SuccessfulPrefixReplay:
        count = self.successful_prefix_provider_call_count
        if any(
            len(values) != count
            for values in (
                self.successful_prefix_provider_envelope_ids,
                self.successful_prefix_attempt_ids,
                self.successful_prefix_choice_ids,
                self.successful_prefix_commit_ids,
                self.successful_prefix_observation_ids,
            )
        ):
            raise ValueError("v26.126 successful prefix partition changed")
        if self.runtime_observation_rebuild_count != count:
            raise ValueError("v26.126 successful prefix Runtime rebuild changed")
        if self.replay_id != _identity(
            self,
            "replay_id",
            "finance_v26_successful_prefix_replay:",
        ):
            raise ValueError("v26.126 successful prefix identity changed")
        return self


class RecoveryCompletedResult(FrozenModel):
    result_id: str = Field(min_length=1)
    recovery_job_id: str = Field(min_length=1)
    job_id: str = Field(min_length=1)
    answer: dict[str, Any] = Field(min_length=1)
    rationale_summary: str = Field(min_length=1)
    cited_evidence_ids: tuple[str, ...] = Field(min_length=1)
    final_attempt_id: str = Field(min_length=1)
    final_response_host_envelope: FinalResponseHostEnvelope
    host_answer_or_rationale_inserted: Literal[False] = False
    schema_version: Literal["finance_v26_recovery_completed_result.v1"] = (
        "finance_v26_recovery_completed_result.v1"
    )

    @model_validator(mode="after")
    def validate_result(self) -> RecoveryCompletedResult:
        if self.cited_evidence_ids != tuple(sorted(set(self.cited_evidence_ids))):
            raise ValueError("v26.126 Recovery cited Evidence is not canonical")
        if self.result_id != _identity(
            self,
            "result_id",
            "finance_v26_recovery_completed_result:",
        ):
            raise ValueError("v26.126 Recovery completed-result identity changed")
        return self


class RecoveryRawExecution(FrozenModel):
    artifact_id: str = Field(min_length=1)
    recovery_runner_contract_id: str = Field(min_length=1)
    recovery_job: ExactFailedCallRecoveryJob
    job: static_stage.FinalGrammarJob
    prefix_replay: SuccessfulPrefixReplay
    operational_record_id: str = Field(min_length=1)
    environment_manifest_id: str = Field(min_length=1)
    path_audit_id: str = Field(min_length=1)
    successor_provider_envelope_artifacts: tuple[legacy.RawFileDescriptor, ...]
    successor_payload_projection_artifacts: tuple[legacy.RawFileDescriptor, ...]
    historical_prefix_provider_telemetry: tuple[legacy.ModelCallTelemetry, ...]
    successor_provider_telemetry: tuple[legacy.ModelCallTelemetry, ...]
    attempts: tuple[historical_runner.PrivacyFirstAttempt, ...] = Field(min_length=1)
    semantic_choices: tuple[semantic_execution.SemanticChoiceRecord, ...]
    commits: tuple[semantic_execution.SemanticActionCommitRecord, ...]
    semantic_rejections: tuple[PublicSemanticRejectionObservation, ...]
    observations: tuple[AgentToolObservation, ...]
    completed_result: RecoveryCompletedResult | None = None
    terminal_disposition: historical_runner.TerminalDisposition
    terminal_failure_type: str | None = None
    execution_error: str | None = None
    historical_successful_prefix_tokens: int = Field(ge=0)
    successor_provider_tokens: int = Field(ge=0)
    cumulative_provider_tokens: int = Field(ge=0)
    historical_successful_prefix_provider_call_count: int = Field(ge=0, le=2)
    successor_provider_call_count: int = Field(ge=0, le=12)
    stage_one_provider_call_count: int = Field(ge=1, le=12)
    exact_failed_call_replacement_attempt_count: Literal[1] = 1
    original_failed_call_usage_unknown_count: Literal[1] = 1
    original_failed_call_usage_imputed: Literal[False] = False
    abi_rescue_attempt_count: int = Field(ge=0, le=1)
    semantic_recovery_attempt_count: int = Field(ge=0, le=1)
    first_choice_semantic_rejection_count: int = Field(ge=0, le=1)
    privacy_rejected_payload_count: int = Field(ge=0, le=12)
    stage_two_provider_call_count: Literal[0] = 0
    model_discovery_call_count: Literal[0] = 0
    telemetry_envelopes_persisted_before_payload_validation: Literal[True] = True
    captured_before_verifier_scoring: Literal[True] = True
    private_reasoning_content_persisted: Literal[False] = False
    historical_job_reclassified: Literal[False] = False
    schema_version: Literal["finance_v26_recovery_raw_execution.v1"] = (
        "finance_v26_recovery_raw_execution.v1"
    )

    @model_validator(mode="after")
    def validate_execution(self) -> RecoveryRawExecution:
        if (
            self.recovery_job.historical_job != self.job
            or self.prefix_replay.recovery_job_id != self.recovery_job.recovery_job_id
            or self.historical_successful_prefix_provider_call_count
            != len(self.historical_prefix_provider_telemetry)
            or self.successor_provider_call_count != len(self.successor_provider_telemetry)
            or self.successor_provider_call_count != len(self.successor_provider_envelope_artifacts)
            or self.successor_provider_call_count
            != len(self.successor_payload_projection_artifacts)
            or self.stage_one_provider_call_count
            != self.historical_successful_prefix_provider_call_count
            + self.successor_provider_call_count
            or self.cumulative_provider_tokens
            != self.historical_successful_prefix_tokens + self.successor_provider_tokens
            or self.abi_rescue_attempt_count
            != sum(item.public_attempt_phase == "abi_rescue" for item in self.attempts)
            or self.semantic_recovery_attempt_count
            != sum(
                item.public_attempt_phase == "semantic_recovery" for item in self.semantic_choices
            )
            or self.first_choice_semantic_rejection_count
            != sum(
                item.public_attempt_phase == "primary" and not item.semantic_accepted
                for item in self.semantic_choices
            )
            or (self.completed_result is not None) != (self.terminal_disposition == "completed")
        ):
            raise ValueError("v26.126 Recovery Raw denominator changed")
        if self.artifact_id != _identity(
            self,
            "artifact_id",
            "finance_v26_recovery_raw_execution:",
        ):
            raise ValueError("v26.126 Recovery Raw identity changed")
        return self


class PrefixReplayAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    exact_recovery_job_count: Literal[10] = 10
    prefix_replay_count: Literal[10] = 10
    zero_prefix_job_count: Literal[6] = 6
    one_call_prefix_job_count: Literal[2] = 2
    two_call_prefix_job_count: Literal[2] = 2
    successful_prefix_provider_call_count: Literal[6] = 6
    rebuilt_observation_count: Literal[6] = 6
    exact_failed_prompt_match_count: Literal[10] = 10
    exact_failed_dynamic_certificate_match_count: Literal[10] = 10
    exact_failed_request_certificate_match_count: Literal[10] = 10
    exact_failed_resource_certificate_match_count: Literal[10] = 10
    original_failed_call_usage_imputation_count: Literal[0] = 0
    provider_calls: Literal[0] = 0
    stage_two_provider_calls: Literal[0] = 0
    rows: tuple[SuccessfulPrefixReplay, ...] = Field(min_length=10, max_length=10)
    status: Literal["passed"] = "passed"
    schema_version: Literal["finance_v26_prefix_replay_audit.v1"] = (
        "finance_v26_prefix_replay_audit.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> PrefixReplayAudit:
        if tuple(item.recovery_job_id for item in self.rows) != tuple(
            sorted(item.recovery_job_id for item in self.rows)
        ):
            raise ValueError("v26.126 Prefix Replay rows changed")
        if self.audit_id != _identity(self, "audit_id", "finance_v26_prefix_replay_audit:"):
            raise ValueError("v26.126 Prefix Replay audit identity changed")
        return self


class ScriptedRecoveryRow(FrozenModel):
    recovery_job_id: str = Field(min_length=1)
    raw_execution_id: str = Field(min_length=1)
    historical_prefix_call_count: int = Field(ge=0, le=2)
    successor_scripted_call_count: int = Field(ge=1, le=12)
    exact_failed_call_replacement_count: Literal[1] = 1
    program_closed: Literal[True] = True
    terminal_verification_completed: Literal[True] = True
    final_abi_crossed: Literal[True] = True
    replay_v3_passed: Literal[True] = True
    independent_validity_passed: Literal[True] = True
    mechanism_passed: Literal[True] = True
    privacy_pairing_passed: Literal[True] = True
    stage_two_provider_calls: Literal[0] = 0


class ScriptedRecoveryAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    exact_recovery_job_count: Literal[10] = 10
    completed_count: Literal[10] = 10
    exact_failed_call_replacement_count: Literal[10] = 10
    independently_valid_count: Literal[10] = 10
    rows: tuple[ScriptedRecoveryRow, ...] = Field(min_length=10, max_length=10)
    real_provider_calls: Literal[0] = 0
    stage_two_provider_calls: Literal[0] = 0
    status: Literal["passed"] = "passed"
    schema_version: Literal["finance_v26_scripted_transport_recovery_audit.v1"] = (
        "finance_v26_scripted_transport_recovery_audit.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> ScriptedRecoveryAudit:
        if tuple(item.recovery_job_id for item in self.rows) != tuple(
            sorted(item.recovery_job_id for item in self.rows)
        ):
            raise ValueError("v26.126 scripted Recovery rows changed")
        if self.audit_id != _identity(
            self, "audit_id", "finance_v26_scripted_transport_recovery_audit:"
        ):
            raise ValueError("v26.126 scripted Recovery audit identity changed")
        return self


class RecoveryControlAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    replacement_transport_failure_call_count: Literal[1] = 1
    replacement_transport_failure_second_call_count: Literal[0] = 0
    malformed_replacement_abi_rescue_count: Literal[1] = 1
    unknown_action_semantic_recovery_count: Literal[1] = 1
    abi_and_semantic_recovery_counters_separate: Literal[True] = True
    completion_16384_admitted: Literal[True] = True
    completion_16385_admitted_and_fully_charged: Literal[True] = True
    completion_16386_instrument_failure: Literal[True] = True
    original_failed_usage_imputation_count: Literal[0] = 0
    complete_raw_recovery_provider_calls: Literal[0] = 0
    orphan_artifact_retry_blocked: Literal[True] = True
    envelope_before_projection_passed: Literal[True] = True
    privacy_rejected_payload_content_count: Literal[0] = 0
    stage_two_provider_calls: Literal[0] = 0
    real_provider_calls: Literal[0] = 0
    status: Literal["passed"] = "passed"
    schema_version: Literal["finance_v26_transport_recovery_control_audit.v1"] = (
        "finance_v26_transport_recovery_control_audit.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> RecoveryControlAudit:
        if self.audit_id != _identity(
            self, "audit_id", "finance_v26_transport_recovery_control_audit:"
        ):
            raise ValueError("v26.126 Recovery control identity changed")
        return self


class MutationResult(FrozenModel):
    name: str = Field(min_length=1)
    rejected: Literal[True] = True
    provider_calls_before_rejection: Literal[0] = 0
    stage_two_provider_calls_before_rejection: Literal[0] = 0


class DestructiveAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    mutation_count: Literal[16] = 16
    rejection_count: Literal[16] = 16
    mutations: tuple[MutationResult, ...] = Field(min_length=16, max_length=16)
    provider_calls: Literal[0] = 0
    stage_two_provider_calls: Literal[0] = 0
    status: Literal["passed"] = "passed"
    schema_version: Literal["finance_v26_transport_recovery_destructive.v1"] = (
        "finance_v26_transport_recovery_destructive.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> DestructiveAudit:
        names = tuple(item.name for item in self.mutations)
        if names != tuple(sorted(set(names))):
            raise ValueError("v26.126 destructive controls changed")
        if self.audit_id != _identity(
            self, "audit_id", "finance_v26_transport_recovery_destructive:"
        ):
            raise ValueError("v26.126 destructive audit identity changed")
        return self


class ProspectiveTransitionContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    recovery_contract_id: str = Field(min_length=1)
    recovery_manifest_id: str = Field(min_length=1)
    recovery_runner_contract_id: str = Field(min_length=1)
    prefix_replay_audit_id: str = Field(min_length=1)
    scripted_recovery_audit_id: str = Field(min_length=1)
    recovery_control_audit_id: str = Field(min_length=1)
    destructive_audit_id: str = Field(min_length=1)
    status: Literal["passed_exact_transport_recovery_preflight"] = (
        "passed_exact_transport_recovery_preflight"
    )
    next_permitted_stage: str = NEXT_STAGE
    provider_calls_authorized: Literal[True] = True
    only_exact_ten_recovery_job_manifest_authorized: Literal[True] = True
    one_replacement_per_exact_failed_call_maximum: Literal[True] = True
    successful_prefix_provider_calls_authorized: Literal[0] = 0
    historical_model_outcome_rerun_authorized: Literal[False] = False
    original_failed_call_usage_imputation_authorized: Literal[False] = False
    semantic_action_candidate_final_grammar_model_or_resource_change_authorized: Literal[False] = (
        False
    )
    post_recovery_independent_audit_required: Literal[True] = True
    role_state_training_release_or_production_authorized: Literal[False] = False
    schema_version: Literal["finance_v26_transport_recovery_runner_transition.v1"] = (
        "finance_v26_transport_recovery_runner_transition.v1"
    )

    @model_validator(mode="after")
    def validate_contract(self) -> ProspectiveTransitionContract:
        if self.contract_id != _identity(
            self,
            "contract_id",
            "finance_v26_transport_recovery_runner_transition:",
        ):
            raise ValueError("v26.126 transition identity changed")
        return self


class DetailFile(FrozenModel):
    relative_path: str = Field(min_length=1)
    sha256: str = Field(min_length=64, max_length=64)
    byte_count: int = Field(gt=0)


class RecoveryPreflightReport(FrozenModel):
    report_id: str = Field(min_length=1)
    run_id: str = RUN_ID
    source_replay_audit_id: str = Field(min_length=1)
    recovery_contract_id: str = Field(min_length=1)
    recovery_manifest_id: str = Field(min_length=1)
    recovery_runner_contract_id: str = Field(min_length=1)
    prefix_replay_audit_id: str = Field(min_length=1)
    scripted_recovery_audit_id: str = Field(min_length=1)
    recovery_control_audit_id: str = Field(min_length=1)
    destructive_audit_id: str = Field(min_length=1)
    transition_contract_id: str = Field(min_length=1)
    detail_files: tuple[DetailFile, ...] = Field(min_length=9, max_length=9)
    exact_recovery_job_count: Literal[10] = 10
    historical_model_outcome_count: Literal[22] = 22
    prefix_replay_provider_calls: Literal[0] = 0
    scripted_provider_calls: int = Field(ge=10)
    real_provider_calls: Literal[0] = 0
    stage_two_provider_calls: Literal[0] = 0
    gpu_jobs: Literal[0] = 0
    empirical_rows_created: Literal[0] = 0
    historical_rows_reclassified: Literal[0] = 0
    status: Literal["passed_exact_transport_recovery_preflight"] = (
        "passed_exact_transport_recovery_preflight"
    )
    next_permitted_stage: str = NEXT_STAGE
    schema_version: Literal["finance_v26_transport_recovery_preflight_report.v1"] = (
        "finance_v26_transport_recovery_preflight_report.v1"
    )

    @model_validator(mode="after")
    def validate_report(self) -> RecoveryPreflightReport:
        if self.report_id != _identity(
            self,
            "report_id",
            "finance_v26_transport_recovery_preflight_report:",
        ):
            raise ValueError("v26.126 preflight report identity changed")
        return self


class PreparedRecoveryPreflight(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", arbitrary_types_allowed=True)

    source_replay: RecoverySourceReplayAudit
    recovery_contract: ExactFailedCallRecoveryContract
    recovery_manifest: ExactFailedCallRecoveryManifest
    runner_contract: ExactFailedCallRecoveryRunnerContract
    static: static_stage.FinalGrammarStaticInputs
    historical_runner_contract: historical_runner.PrivacyFirstRunnerContract


@dataclass(frozen=True)
class PrefixRuntimeState:
    replay: SuccessfulPrefixReplay
    historical_raw: historical_runner.PrivacyFirstRawExecution
    binding: legacy.RuntimeBinding
    runtime: Any
    observations: tuple[AgentToolObservation, ...]
    attempts: tuple[historical_runner.PrivacyFirstAttempt, ...]
    choices: tuple[semantic_execution.SemanticChoiceRecord, ...]
    commits: tuple[semantic_execution.SemanticActionCommitRecord, ...]
    semantic_rejections: tuple[PublicSemanticRejectionObservation, ...]
    failed_state: SemanticActionState
    failed_prompt: str
    historical_prefix_telemetry: tuple[legacy.ModelCallTelemetry, ...]


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _descriptor(path: Path, output_dir: Path) -> legacy.RawFileDescriptor:
    return legacy.RawFileDescriptor(
        relative_path=str(path.resolve().relative_to(output_dir.resolve())),
        sha256=legacy.sha256_file(path),
        byte_count=path.stat().st_size,
    )


def _detail(path: Path, output_dir: Path) -> DetailFile:
    return DetailFile(
        relative_path=str(path.relative_to(output_dir)),
        sha256=legacy.sha256_file(path),
        byte_count=path.stat().st_size,
    )


def _find_bound_path(
    relative_path: str,
    expected_sha256: str,
    *,
    package_root: Path,
    implementation_root: Path,
) -> Path:
    for root in (implementation_root, package_root):
        candidate = root / relative_path
        if candidate.is_file() and legacy.sha256_file(candidate) == expected_sha256:
            return candidate
    raise ValueError(f"v26.126 cannot replay bound file: {relative_path}")


def recovery_raw_path(output_dir: Path, job: ExactFailedCallRecoveryJob) -> Path:
    suffix = job.recovery_job_id.rsplit(":", 1)[-1]
    return output_dir / "recovery_raw_execution" / f"{suffix}.json"


def recovery_envelope_path(
    output_dir: Path,
    job: ExactFailedCallRecoveryJob,
    call_index: int,
) -> Path:
    suffix = job.recovery_job_id.rsplit(":", 1)[-1]
    return output_dir / "recovery_provider_envelopes" / suffix / f"call_{call_index:03d}.json"


def recovery_projection_path(
    output_dir: Path,
    job: ExactFailedCallRecoveryJob,
    call_index: int,
) -> Path:
    suffix = job.recovery_job_id.rsplit(":", 1)[-1]
    return output_dir / "recovery_payload_projections" / suffix / f"call_{call_index:03d}.json"


def _write_json_atomic(path: Path, value: Any) -> None:
    historical_runner.write_json_atomic(path, value)


def build_source_replay(
    *,
    package_root: Path,
    implementation_root: Path,
    historical_audit_dir: Path,
) -> RecoverySourceReplayAudit:
    predecessor = historical_audit.AuditSourceReplay.model_validate(
        _load(historical_audit_dir / "source_replay_audit.json")
    )
    report = historical_audit.PostrunAuditReport.model_validate(
        _load(historical_audit_dir / "report.json")
    )
    if (
        predecessor.audit_id != EXPECTED_AUDIT_SOURCE_REPLAY_ID
        or report.report_id != EXPECTED_AUDIT_REPORT_ID
        or report.source_replay_audit_id != predecessor.audit_id
    ):
        raise ValueError("v26.126 predecessor audit identity changed")
    entries: dict[str, SourceReplayEntry] = {}
    for item in predecessor.entries:
        path = _find_bound_path(
            item.relative_path,
            item.expected_sha256,
            package_root=package_root,
            implementation_root=implementation_root,
        )
        entries[item.relative_path] = SourceReplayEntry(
            relative_path=item.relative_path,
            source_kind="v26_125_transitive_source",
            expected_sha256=item.expected_sha256,
            observed_sha256=legacy.sha256_file(path),
            byte_count=path.stat().st_size,
        )
    details = {item.relative_path: item for item in report.detail_files}
    if set(HISTORICAL_AUDIT_OUTPUTS) != {"report.json", *details}:
        raise ValueError("v26.126 predecessor output set changed")
    for name in HISTORICAL_AUDIT_OUTPUTS:
        path = historical_audit_dir / name
        observed = legacy.sha256_file(path)
        if name != "report.json":
            expected = details[name]
            if expected.sha256 != observed or expected.byte_count != path.stat().st_size:
                raise ValueError("v26.126 predecessor detail binding changed")
        relative = str(Path(HISTORICAL_AUDIT_DIR) / name)
        entries[relative] = SourceReplayEntry(
            relative_path=relative,
            source_kind="v26_125_output",
            expected_sha256=observed,
            observed_sha256=observed,
            byte_count=path.stat().st_size,
        )
    implementation_path = implementation_root / IMPLEMENTATION_PATH
    digest = legacy.sha256_file(implementation_path)
    entries[IMPLEMENTATION_PATH] = SourceReplayEntry(
        relative_path=IMPLEMENTATION_PATH,
        source_kind="v26_126_implementation",
        expected_sha256=digest,
        observed_sha256=digest,
        byte_count=implementation_path.stat().st_size,
    )
    values = {"entries": tuple(entries[key] for key in sorted(entries))}
    provisional = RecoverySourceReplayAudit.model_construct(audit_id="pending", **values)
    return RecoverySourceReplayAudit(
        audit_id=_identity(
            provisional,
            "audit_id",
            "finance_v26_transport_recovery_source_replay:",
        ),
        **values,
    )


def _build_recovery_chain(
    *,
    static: static_stage.FinalGrammarStaticInputs,
    historical_audit_dir: Path,
    historical_execution_dir: Path,
) -> tuple[
    ExactFailedCallRecoveryContract,
    ExactFailedCallRecoveryManifest,
    ExactFailedCallRecoveryRunnerContract,
    historical_runner.PrivacyFirstRunnerContract,
]:
    report = historical_audit.PostrunAuditReport.model_validate(
        _load(historical_audit_dir / "report.json")
    )
    provider = historical_audit.ProviderFailureAudit.model_validate(
        _load(historical_audit_dir / "provider_failure_audit.json")
    )
    transition = historical_audit.ProspectiveTransitionContract.model_validate(
        _load(historical_audit_dir / "prospective_transition_contract.json")
    )
    historical_contract = historical_runner.PrivacyFirstRunnerContract.model_validate(
        _load(historical_execution_dir / "runner_contract.json")
    )
    results = tuple(
        historical_execution.ExactFinalJobResult.model_validate(item)
        for item in _load(historical_execution_dir / "exact_final_job_results.json")
    )
    if (
        report.report_id != EXPECTED_AUDIT_REPORT_ID
        or provider.audit_id != EXPECTED_PROVIDER_FAILURE_AUDIT_ID
        or transition.contract_id != EXPECTED_AUDIT_TRANSITION_ID
        or report.provider_failure_audit_id != provider.audit_id
        or report.transition_contract_id != transition.contract_id
        or transition.next_permitted_stage != historical_audit.NEXT_STAGE
        or transition.provider_calls_authorized
        or historical_contract.contract_id != EXPECTED_HISTORICAL_RUNNER_ID
        or len(results) != 32
    ):
        raise ValueError("v26.126 predecessor recovery authorization changed")
    candidate_ids = tuple(
        sorted(item.candidate_id for item in provider.failed_call_recovery_candidates)
    )
    contract_values = {"recovery_candidate_ids": candidate_ids}
    provisional_contract = ExactFailedCallRecoveryContract.model_construct(
        contract_id="pending", **contract_values
    )
    contract = ExactFailedCallRecoveryContract(
        contract_id=_identity(
            provisional_contract,
            "contract_id",
            "finance_v26_exact_failed_call_recovery_contract:",
        ),
        **contract_values,
    )
    jobs_by_id = {item.job_id: item for item in static.manifest.jobs}
    results_by_id = {item.job_id: item for item in results}
    recovery_jobs: list[ExactFailedCallRecoveryJob] = []
    for candidate in provider.failed_call_recovery_candidates:
        job = jobs_by_id[candidate.historical_job_id]
        result = results_by_id[job.job_id]
        raw_path = historical_runner.raw_execution_path(historical_execution_dir, job)
        raw = historical_runner.PrivacyFirstRawExecution.model_validate(_load(raw_path))
        descriptor = _descriptor(raw_path, historical_execution_dir)
        if (
            result.terminal_category != "instrument_failure"
            or result.raw_execution_artifact != descriptor
            or raw.job != job
            or raw.terminal_disposition != "instrument_failure"
            or candidate.provider_call_index != candidate.successful_prefix_provider_call_count
        ):
            raise ValueError("v26.126 RecoveryJob source is not an exact Instrument terminal")
        values = {
            "recovery_contract_id": contract.contract_id,
            "candidate": candidate,
            "historical_job": job,
            "historical_raw_execution_id": raw.artifact_id,
            "historical_raw_execution_artifact": descriptor,
            "historical_job_result_id": result.result_id,
            "successful_prefix_provider_call_count": (
                candidate.successful_prefix_provider_call_count
            ),
            "successful_prefix_cumulative_tokens": (
                candidate.cumulative_provider_tokens_before_failure
            ),
            "exact_failed_request_prompt_sha256": candidate.request_prompt_sha256,
            "exact_failed_dynamic_certificate_id": candidate.dynamic_certificate_id,
            "exact_failed_request_binding_certificate_id": (
                candidate.request_binding_certificate_id
            ),
            "exact_failed_resource_certificate_id": candidate.resource_certificate_id,
        }
        provisional_job = ExactFailedCallRecoveryJob.model_construct(
            recovery_job_id="pending", **values
        )
        recovery_jobs.append(
            ExactFailedCallRecoveryJob(
                recovery_job_id=_identity(
                    provisional_job,
                    "recovery_job_id",
                    "finance_v26_exact_failed_call_recovery_job:",
                ),
                **values,
            )
        )
    ordered_jobs = tuple(sorted(recovery_jobs, key=lambda item: item.recovery_job_id))
    manifest_values = {
        "recovery_contract_id": contract.contract_id,
        "jobs": ordered_jobs,
    }
    provisional_manifest = ExactFailedCallRecoveryManifest.model_construct(
        manifest_id="pending", **manifest_values
    )
    manifest = ExactFailedCallRecoveryManifest(
        manifest_id=_identity(
            provisional_manifest,
            "manifest_id",
            "finance_v26_exact_failed_call_recovery_manifest:",
        ),
        **manifest_values,
    )
    runner_values = {
        "recovery_contract_id": contract.contract_id,
        "recovery_manifest_id": manifest.manifest_id,
        "exact_final_response_grammar_id": static.final_grammar.grammar_id,
        "stage_one_profile_id": static.stage_one.profile_id,
        "stage_two_profile_id": static.stage_two.profile_id,
        "resource_contract_id": static.resource.contract_id,
    }
    provisional_runner = ExactFailedCallRecoveryRunnerContract.model_construct(
        runner_contract_id="pending", **runner_values
    )
    runner_contract = ExactFailedCallRecoveryRunnerContract(
        runner_contract_id=_identity(
            provisional_runner,
            "runner_contract_id",
            "finance_v26_exact_failed_call_recovery_runner_contract:",
        ),
        **runner_values,
    )
    if (
        historical_contract.exact_final_response_grammar_id
        != runner_contract.exact_final_response_grammar_id
        or historical_contract.semantic_action_protocol_id
        != runner_contract.semantic_action_protocol_id
        or historical_contract.semantic_action_response_grammar_id
        != runner_contract.semantic_action_response_grammar_id
        or historical_contract.candidate_space_authority_audit_id
        != runner_contract.candidate_space_authority_audit_id
        or historical_contract.stage_one_profile_id != runner_contract.stage_one_profile_id
        or historical_contract.stage_two_profile_id != runner_contract.stage_two_profile_id
        or historical_contract.resource_contract_id != runner_contract.resource_contract_id
        or historical_contract.exact_request_completion_bound_tokens
        != runner_contract.exact_request_completion_bound_tokens
        or historical_contract.rollout_upper_bound_tokens
        != runner_contract.rollout_upper_bound_tokens
    ):
        raise ValueError("v26.126 changed the frozen generation or semantic route")
    return contract, manifest, runner_contract, historical_contract


def prepare_recovery_preflight(
    *,
    package_root: Path,
    implementation_root: Path,
    historical_audit_dir: Path,
    historical_execution_dir: Path,
    output_dir: Path,
) -> PreparedRecoveryPreflight:
    source = build_source_replay(
        package_root=package_root,
        implementation_root=implementation_root,
        historical_audit_dir=historical_audit_dir,
    )
    static = static_stage.load_final_grammar_static_inputs(package_root, implementation_root)
    contract, manifest, runner_contract, historical_contract = _build_recovery_chain(
        static=static,
        historical_audit_dir=historical_audit_dir,
        historical_execution_dir=historical_execution_dir,
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_json_atomic(output_dir / "source_replay_audit.json", source.model_dump(mode="json"))
    _write_json_atomic(output_dir / "recovery_contract.json", contract.model_dump(mode="json"))
    _write_json_atomic(output_dir / "recovery_job_manifest.json", manifest.model_dump(mode="json"))
    _write_json_atomic(
        output_dir / "recovery_runner_contract.json",
        runner_contract.model_dump(mode="json"),
    )
    return PreparedRecoveryPreflight(
        source_replay=source,
        recovery_contract=contract,
        recovery_manifest=manifest,
        runner_contract=runner_contract,
        static=static,
        historical_runner_contract=historical_contract,
    )


def load_prepared_recovery(
    *,
    package_root: Path,
    implementation_root: Path,
    preflight_dir: Path,
) -> PreparedRecoveryPreflight:
    report = RecoveryPreflightReport.model_validate(_load(preflight_dir / "report.json"))
    source = RecoverySourceReplayAudit.model_validate(
        _load(preflight_dir / "source_replay_audit.json")
    )
    contract = ExactFailedCallRecoveryContract.model_validate(
        _load(preflight_dir / "recovery_contract.json")
    )
    manifest = ExactFailedCallRecoveryManifest.model_validate(
        _load(preflight_dir / "recovery_job_manifest.json")
    )
    runner_contract = ExactFailedCallRecoveryRunnerContract.model_validate(
        _load(preflight_dir / "recovery_runner_contract.json")
    )
    transition = ProspectiveTransitionContract.model_validate(
        _load(preflight_dir / "prospective_transition_contract.json")
    )
    static = static_stage.load_final_grammar_static_inputs(package_root, implementation_root)
    historical_contract = historical_runner.PrivacyFirstRunnerContract.model_validate(
        _load(package_root / HISTORICAL_EXECUTION_DIR / "runner_contract.json")
    )
    if (
        report.status != "passed_exact_transport_recovery_preflight"
        or report.next_permitted_stage != NEXT_STAGE
        or report.source_replay_audit_id != source.audit_id
        or report.recovery_contract_id != contract.contract_id
        or report.recovery_manifest_id != manifest.manifest_id
        or report.recovery_runner_contract_id != runner_contract.runner_contract_id
        or report.transition_contract_id != transition.contract_id
        or not transition.provider_calls_authorized
        or not transition.only_exact_ten_recovery_job_manifest_authorized
        or contract.provider_calls_authorized
        or runner_contract.empirical_execution_authorized
        or historical_contract.contract_id != EXPECTED_HISTORICAL_RUNNER_ID
    ):
        raise ValueError("v26.126 completed preflight authorization changed")
    return PreparedRecoveryPreflight(
        source_replay=source,
        recovery_contract=contract,
        recovery_manifest=manifest,
        runner_contract=runner_contract,
        static=static,
        historical_runner_contract=historical_contract,
    )


def _request_bound(resource: static_stage.FinalGrammarResourceContract, prompt_bytes: int) -> int:
    return prompt_bytes + resource.chat_envelope_tokens + resource.accounted_completion_bound_tokens


def _old_resource_certificate(
    resource: static_stage.FinalGrammarResourceContract,
    *,
    prompt: str,
    request_kind: legacy.StageOneRequestKind,
    public_attempt_phase: historical_runner.PublicAttemptPhase,
    abi_rescue_count_before: int,
    semantic_recovery_count_before: int,
    cumulative_tokens_before: int,
    combined_provider_call_count_before: int,
) -> semantic_execution.ActionResourceCertificate:
    prompt_bytes = len(prompt.encode("utf-8"))
    prompt_upper = prompt_bytes + resource.chat_envelope_tokens
    request_upper = prompt_upper + resource.accounted_completion_bound_tokens
    abi_prompt_bound = max(
        resource.qualified_maximum_action_abi_rescue_prompt_utf8_bytes,
        resource.qualified_maximum_final_rescue_prompt_utf8_bytes,
    )
    abi = (
        _request_bound(resource, abi_prompt_bound)
        if abi_rescue_count_before == 0 and public_attempt_phase != "abi_rescue"
        else 0
    )
    semantic = (
        _request_bound(
            resource,
            resource.qualified_maximum_semantic_recovery_prompt_utf8_bytes,
        )
        if request_kind == "semantic_proposal"
        and semantic_recovery_count_before == 0
        and public_attempt_phase != "semantic_recovery"
        else 0
    )
    final = (
        _request_bound(resource, resource.qualified_maximum_final_primary_prompt_utf8_bytes)
        if request_kind == "semantic_proposal"
        else 0
    )
    projected = cumulative_tokens_before + request_upper + abi + semantic + final
    denial: str | None = None
    if combined_provider_call_count_before >= resource.maximum_stage_one_provider_calls:
        denial = "stage_one_request_count_exhausted"
    elif prompt_bytes > resource.prompt_upper_bound_bytes:
        denial = "oversized_prompt"
    elif cumulative_tokens_before + request_upper > resource.rollout_upper_bound_tokens:
        denial = "request_bound_exceeds_remaining_budget"
    elif projected > resource.rollout_upper_bound_tokens:
        denial = "required_reserve_not_available"
    values = {
        "resource_contract_id": resource.contract_id,
        "request_index": combined_provider_call_count_before,
        "request_kind": request_kind,
        "public_attempt_phase": public_attempt_phase,
        "request_prompt_sha256": legacy.sha256_text(prompt),
        "prompt_utf8_bytes": prompt_bytes,
        "prompt_token_upper_bound": prompt_upper,
        "request_token_upper_bound": request_upper,
        "cumulative_provider_tokens_before": cumulative_tokens_before,
        "abi_rescue_reserve_tokens": abi,
        "semantic_recovery_reserve_tokens": semantic,
        "final_answer_reserve_tokens": final,
        "required_reserve_tokens": abi + semantic + final,
        "projected_upper_total": projected,
        "rollout_upper_bound_tokens": resource.rollout_upper_bound_tokens,
        "decision": "denied_no_call" if denial else "allowed",
        "denial_reason": denial,
        "provider_call_permitted": denial is None,
    }
    provisional = semantic_execution.ActionResourceCertificate.model_construct(
        certificate_id="pending", **values
    )
    return semantic_execution.ActionResourceCertificate(
        certificate_id=_identity(
            provisional,
            "certificate_id",
            "finance_v26_action_resource_certificate:",
        ),
        **values,
    )


def _old_dynamic_certificate(
    *,
    historical_runner_contract: historical_runner.PrivacyFirstRunnerContract,
    job: static_stage.FinalGrammarJob,
    logical_request_index: int,
    request_kind: legacy.StageOneRequestKind,
    public_attempt_phase: historical_runner.PublicAttemptPhase,
    primary_prompt: str,
    prompt: str,
    public_state_id: str,
    final_response_host_envelope: FinalResponseHostEnvelope | None,
    abi_rescue_count_before: int,
    semantic_recovery_count_before: int,
) -> historical_runner.PrivacyFirstDynamicRequestCertificate:
    provider_phase: legacy.StageOneAttemptPhase = (
        "rescue" if public_attempt_phase == "abi_rescue" else "primary"
    )
    values = {
        "runner_contract_id": historical_runner_contract.contract_id,
        "job_id": job.job_id,
        "logical_request_index": logical_request_index,
        "request_kind": request_kind,
        "public_attempt_phase": public_attempt_phase,
        "provider_attempt_phase": provider_phase,
        "primary_prompt_sha256": legacy.sha256_text(primary_prompt),
        "request_prompt_sha256": legacy.sha256_text(prompt),
        "public_state_id": public_state_id,
        "final_response_host_envelope_id": (
            final_response_host_envelope.envelope_id
            if final_response_host_envelope is not None
            else None
        ),
        "prompt_utf8_bytes": len(prompt.encode("utf-8")),
        "abi_rescue_count_before": abi_rescue_count_before,
        "semantic_recovery_count_before": semantic_recovery_count_before,
    }
    provisional = historical_runner.PrivacyFirstDynamicRequestCertificate.model_construct(
        certificate_id="pending", **values
    )
    return historical_runner.PrivacyFirstDynamicRequestCertificate(
        certificate_id=_identity(
            provisional,
            "certificate_id",
            "finance_v26_privacy_first_dynamic_request_certificate:",
        ),
        **values,
    )


def _historical_provider_pairs(
    raw: historical_runner.PrivacyFirstRawExecution,
    historical_execution_dir: Path,
) -> tuple[
    tuple[
        historical_runner.PrivacyFirstProviderEnvelope, historical_runner.PublicPayloadProjection
    ],
    ...,
]:
    envelopes = tuple(
        historical_runner.PrivacyFirstProviderEnvelope.model_validate(
            _load(historical_execution_dir / item.relative_path)
        )
        for item in raw.provider_envelope_artifacts
    )
    projections = tuple(
        historical_runner.PublicPayloadProjection.model_validate(
            _load(historical_execution_dir / item.relative_path)
        )
        for item in raw.public_payload_projection_artifacts
    )
    if len(envelopes) != len(projections):
        raise ValueError("v26.126 historical Envelope/Projection denominator changed")
    pairs = tuple(zip(envelopes, projections, strict=True))
    for envelope, projection in pairs:
        historical_runner.validate_provider_artifact_pair(envelope, projection)
    return pairs


def _condition(binding: legacy.RuntimeBinding) -> str | None:
    return (
        None
        if binding.source_registered_path.role == "capability"
        else binding.source_registered_path.path_strategy_id
    )


def _primary_action_state_and_prompt(
    *,
    binding: legacy.RuntimeBinding,
    job: static_stage.FinalGrammarJob,
    observations: Sequence[AgentToolObservation],
    semantic_rejections: Sequence[PublicSemanticRejectionObservation],
    logical_request_index: int,
    semantic_recovery_count: int,
    static: static_stage.FinalGrammarStaticInputs,
) -> tuple[SemanticActionState, str]:
    state = build_semantic_action_state(
        binding.record.task_package.task.public,
        binding.environment,
        tuple(observations),
        semantic_rejections=tuple(semantic_rejections),
    )
    presentation_salt = canonical_hash(
        {
            "job_id": job.job_id,
            "logical_request_index": logical_request_index,
            "state_id": state.state_id,
            "semantic_recovery_count": semantic_recovery_count,
        },
        prefix="finance_v26_runner_candidate_presentation:",
    )
    prompt = render_exact_canonical_action_prompt(
        instruction=binding.record.task_package.task.public.instruction,
        state=state,
        public_path_condition=_condition(binding),
        presentation_salt=presentation_salt,
        grammar=static.action_grammar,
    )
    return state, prompt


def replay_successful_prefix(
    *,
    recovery_job: ExactFailedCallRecoveryJob,
    static: static_stage.FinalGrammarStaticInputs,
    historical_runner_contract: historical_runner.PrivacyFirstRunnerContract,
    historical_execution_dir: Path,
) -> PrefixRuntimeState:
    job = recovery_job.historical_job
    candidate = recovery_job.candidate
    raw_path = (
        historical_execution_dir / recovery_job.historical_raw_execution_artifact.relative_path
    )
    if (
        not raw_path.is_file()
        or legacy.sha256_file(raw_path) != recovery_job.historical_raw_execution_artifact.sha256
    ):
        raise ValueError("v26.126 historical Raw bytes changed")
    raw = historical_runner.PrivacyFirstRawExecution.model_validate(_load(raw_path))
    pairs = _historical_provider_pairs(raw, historical_execution_dir)
    prefix_count = candidate.successful_prefix_provider_call_count
    if (
        raw.artifact_id != recovery_job.historical_raw_execution_id
        or raw.job != job
        or raw.terminal_disposition != "instrument_failure"
        or len(pairs) != prefix_count + 1
        or len(raw.attempts) != prefix_count + 1
        or len(raw.semantic_choices) != prefix_count
        or len(raw.commits) != prefix_count
        or len(raw.observations) != prefix_count
        or raw.semantic_rejections
    ):
        raise ValueError("v26.126 historical failed Raw shape changed")
    binding = historical_runner.privacy_first_runtime_binding(static, job)
    runtime = legacy._runtime(binding.record, binding.environment)
    observations: list[AgentToolObservation] = []
    attempts: list[historical_runner.PrivacyFirstAttempt] = []
    choices: list[semantic_execution.SemanticChoiceRecord] = []
    commits: list[semantic_execution.SemanticActionCommitRecord] = []
    for index in range(prefix_count):
        state, prompt = _primary_action_state_and_prompt(
            binding=binding,
            job=job,
            observations=observations,
            semantic_rejections=(),
            logical_request_index=index,
            semantic_recovery_count=0,
            static=static,
        )
        attempt = raw.attempts[index]
        envelope, projection = pairs[index]
        if (
            attempt.disposition != "usable"
            or attempt.logical_request_index != index
            or attempt.provider_call_index != index
            or attempt.prompt_sha256 != legacy.sha256_text(prompt)
            or attempt.public_attempt_phase != "primary"
            or envelope.envelope_id != candidate.successful_prefix_provider_envelope_ids[index]
            or envelope.prompt_sha256 != legacy.sha256_text(prompt)
            or envelope.dynamic_certificate.public_state_id != state.state_id
            or projection.projection_status != "validated_public_payload"
            or projection.response_payload is None
        ):
            raise ValueError("v26.126 successful prefix request changed")
        request = legacy.certify_stage_one_request_pre_call(
            config=static.agent_model_config,
            prompt=prompt,
            request_kind="semantic_proposal",
            phase="primary",
        )
        resource = _old_resource_certificate(
            static.resource,
            prompt=prompt,
            request_kind="semantic_proposal",
            public_attempt_phase="primary",
            abi_rescue_count_before=0,
            semantic_recovery_count_before=0,
            cumulative_tokens_before=sum(
                cast(int, item.total_tokens) for item in raw.provider_telemetry[:index]
            ),
            combined_provider_call_count_before=index,
        )
        dynamic = _old_dynamic_certificate(
            historical_runner_contract=historical_runner_contract,
            job=job,
            logical_request_index=index,
            request_kind="semantic_proposal",
            public_attempt_phase="primary",
            primary_prompt=prompt,
            prompt=prompt,
            public_state_id=state.state_id,
            final_response_host_envelope=None,
            abi_rescue_count_before=0,
            semantic_recovery_count_before=0,
        )
        if (
            request != envelope.request_binding_certificate
            or resource.certificate_id != envelope.resource_certificate_id
            or dynamic != envelope.dynamic_certificate
        ):
            raise ValueError("v26.126 successful prefix certificates changed")
        proposal = parse_exact_canonical_action_payload(projection.response_payload)
        selected = evaluate_canonical_action_proposal(
            state, proposal, call_index=len(observations) + 1
        )
        if selected.rejection is not None or selected.commit is None:
            raise ValueError("v26.126 successful prefix no longer compiles")
        commit = selected.commit
        commit_values = {
            "logical_request_index": index,
            "public_state_id": state.state_id,
            "proposal": proposal,
            "commit": commit,
            "stage_two_profile_id": static.stage_two.profile_id,
            "provider_calls_before_commit": index + 1,
        }
        provisional_commit = semantic_execution.SemanticActionCommitRecord.model_construct(
            record_id="pending", **commit_values
        )
        commit_record = semantic_execution.SemanticActionCommitRecord(
            record_id=_identity(
                provisional_commit,
                "record_id",
                "finance_v26_semantic_action_commit_record:",
            ),
            **commit_values,
        )
        observation: AgentToolObservation | None = None
        progress: bool | None = None
        if commit.call is not None:
            observation = legacy._execute_observation(
                record=binding.record,
                environment=binding.environment,
                runtime=runtime,
                observations=tuple(observations),
                projection=CompletionProjection(
                    request_kind="decision",
                    action="call_tool",
                    tool_id=commit.call.tool_id,
                    arguments=commit.call.arguments,
                ),
            )
            observations.append(observation)
            after = build_semantic_action_state(
                binding.record.task_package.task.public,
                binding.environment,
                tuple(observations),
            )
            progress = semantic_execution._public_progress(state, after, observation)
        choice = semantic_execution._choice_record(
            logical_request_index=index,
            phase="primary",
            state=state,
            proposal=proposal,
            commit=commit,
            rejection=None,
            prior_rejected_action_id=None,
            observation=observation,
            progress=progress,
        )
        if (
            commit_record != raw.commits[index]
            or choice != raw.semantic_choices[index]
            or observation != raw.observations[index]
        ):
            raise ValueError("v26.126 successful prefix semantic replay changed")
        attempts.append(attempt)
        commits.append(commit_record)
        choices.append(choice)
    failed_state, failed_prompt = _primary_action_state_and_prompt(
        binding=binding,
        job=job,
        observations=observations,
        semantic_rejections=(),
        logical_request_index=prefix_count,
        semantic_recovery_count=0,
        static=static,
    )
    failed_attempt = raw.attempts[prefix_count]
    failed_envelope, failed_projection = pairs[prefix_count]
    prefix_tokens = sum(
        cast(int, item.total_tokens) for item in raw.provider_telemetry[:prefix_count]
    )
    request = legacy.certify_stage_one_request_pre_call(
        config=static.agent_model_config,
        prompt=failed_prompt,
        request_kind="semantic_proposal",
        phase="primary",
    )
    resource = _old_resource_certificate(
        static.resource,
        prompt=failed_prompt,
        request_kind="semantic_proposal",
        public_attempt_phase="primary",
        abi_rescue_count_before=0,
        semantic_recovery_count_before=0,
        cumulative_tokens_before=prefix_tokens,
        combined_provider_call_count_before=prefix_count,
    )
    dynamic = _old_dynamic_certificate(
        historical_runner_contract=historical_runner_contract,
        job=job,
        logical_request_index=prefix_count,
        request_kind="semantic_proposal",
        public_attempt_phase="primary",
        primary_prompt=failed_prompt,
        prompt=failed_prompt,
        public_state_id=failed_state.state_id,
        final_response_host_envelope=None,
        abi_rescue_count_before=0,
        semantic_recovery_count_before=0,
    )
    if (
        failed_attempt.disposition != "instrument_failure"
        or failed_attempt.logical_request_index != prefix_count
        or failed_attempt.provider_call_index != prefix_count
        or failed_envelope.envelope_id != candidate.failed_provider_envelope_id
        or failed_projection.projection_id != candidate.failed_payload_projection_id
        or failed_projection.projection_status != "provider_failure_no_payload"
        or failed_envelope.prompt_sha256 != candidate.request_prompt_sha256
        or legacy.sha256_text(failed_prompt) != candidate.request_prompt_sha256
        or dynamic != failed_envelope.dynamic_certificate
        or dynamic.certificate_id != candidate.dynamic_certificate_id
        or request != failed_envelope.request_binding_certificate
        or request.certificate_id != candidate.request_binding_certificate_id
        or resource.certificate_id != failed_envelope.resource_certificate_id
        or resource.certificate_id != candidate.resource_certificate_id
        or prefix_tokens != candidate.cumulative_provider_tokens_before_failure
    ):
        raise ValueError("v26.126 exact failed request reconstruction changed")
    replay_values = {
        "recovery_job_id": recovery_job.recovery_job_id,
        "recovery_candidate_id": candidate.candidate_id,
        "historical_job_id": job.job_id,
        "historical_raw_execution_id": raw.artifact_id,
        "successful_prefix_provider_call_count": prefix_count,
        "successful_prefix_provider_envelope_ids": (
            candidate.successful_prefix_provider_envelope_ids
        ),
        "successful_prefix_attempt_ids": tuple(item.attempt_id for item in attempts),
        "successful_prefix_choice_ids": tuple(item.record_id for item in choices),
        "successful_prefix_commit_ids": tuple(item.record_id for item in commits),
        "successful_prefix_observation_ids": tuple(item.observation_id for item in observations),
        "successful_prefix_cumulative_tokens": prefix_tokens,
        "exact_failed_logical_request_index": prefix_count,
        "exact_failed_public_state_id": failed_state.state_id,
        "exact_failed_prompt_sha256": legacy.sha256_text(failed_prompt),
        "exact_failed_dynamic_certificate_id": dynamic.certificate_id,
        "exact_failed_request_binding_certificate_id": request.certificate_id,
        "exact_failed_resource_certificate_id": resource.certificate_id,
        "runtime_observation_rebuild_count": len(observations),
    }
    provisional_replay = SuccessfulPrefixReplay.model_construct(
        replay_id="pending", **replay_values
    )
    replay = SuccessfulPrefixReplay(
        replay_id=_identity(
            provisional_replay,
            "replay_id",
            "finance_v26_successful_prefix_replay:",
        ),
        **replay_values,
    )
    return PrefixRuntimeState(
        replay=replay,
        historical_raw=raw,
        binding=binding,
        runtime=runtime,
        observations=tuple(observations),
        attempts=tuple(attempts),
        choices=tuple(choices),
        commits=tuple(commits),
        semantic_rejections=(),
        failed_state=failed_state,
        failed_prompt=failed_prompt,
        historical_prefix_telemetry=raw.provider_telemetry[:prefix_count],
    )


class RecoveryJournaledClient:
    def __init__(
        self,
        delegate: Any,
        *,
        runner_contract: ExactFailedCallRecoveryRunnerContract,
        historical_runner_contract: historical_runner.PrivacyFirstRunnerContract,
        resource_contract: static_stage.FinalGrammarResourceContract,
        recovery_job: ExactFailedCallRecoveryJob,
        prefix: PrefixRuntimeState,
        output_dir: Path,
    ) -> None:
        legacy.require_stage_one_model_config(delegate.config)
        if (
            recovery_job.recovery_contract_id != runner_contract.recovery_contract_id
            or recovery_job.historical_job.resource_contract_id != resource_contract.contract_id
            or runner_contract.resource_contract_id != resource_contract.contract_id
            or historical_runner_contract.contract_id
            != runner_contract.historical_runner_contract_id
            or prefix.replay.recovery_job_id != recovery_job.recovery_job_id
        ):
            raise ValueError("v26.126 Recovery ledger crosses frozen identities")
        self._delegate = delegate
        self._runner_contract = runner_contract
        self._historical_runner_contract = historical_runner_contract
        self._resource = resource_contract
        self._job = recovery_job
        self._prefix = prefix
        self._output_dir = output_dir
        self._resource_certificates: list[semantic_execution.ActionResourceCertificate] = []
        self._invocation_certificates: dict[str, RecoveryInvocationCertificate] = {}
        self._telemetry: list[legacy.ModelCallTelemetry] = []
        self._envelope_descriptors: list[legacy.RawFileDescriptor] = []
        self._projection_descriptors: list[legacy.RawFileDescriptor] = []
        self._projection_statuses: list[historical_runner.PayloadProjectionStatus] = []
        self._used_preparations: set[str] = set()
        self._successor_tokens = 0
        self._instrument_failures: set[str] = set()
        self._persistence_order: list[tuple[str, int]] = []

    @property
    def provider_call_count(self) -> int:
        return self._job.successful_prefix_provider_call_count + len(self._telemetry)

    @property
    def successor_provider_call_count(self) -> int:
        return len(self._telemetry)

    @property
    def cumulative_tokens(self) -> int:
        return self._job.successful_prefix_cumulative_tokens + self._successor_tokens

    @property
    def successor_tokens(self) -> int:
        return self._successor_tokens

    @property
    def telemetry(self) -> tuple[legacy.ModelCallTelemetry, ...]:
        return tuple(self._telemetry)

    @property
    def envelope_descriptors(self) -> tuple[legacy.RawFileDescriptor, ...]:
        return tuple(self._envelope_descriptors)

    @property
    def projection_descriptors(self) -> tuple[legacy.RawFileDescriptor, ...]:
        return tuple(self._projection_descriptors)

    @property
    def projection_statuses(self) -> tuple[historical_runner.PayloadProjectionStatus, ...]:
        return tuple(self._projection_statuses)

    @property
    def instrument_failures(self) -> tuple[str, ...]:
        return tuple(sorted(self._instrument_failures))

    @property
    def persistence_order(self) -> tuple[tuple[str, int], ...]:
        return tuple(self._persistence_order)

    def _call_role(
        self,
        request_kind: legacy.StageOneRequestKind,
        public_attempt_phase: historical_runner.PublicAttemptPhase,
    ) -> RecoveryCallRole:
        if not self._telemetry:
            return "exact_failed_call_replacement"
        if request_kind == "final_answer":
            return "final_abi_rescue" if public_attempt_phase == "abi_rescue" else "final_primary"
        if public_attempt_phase == "abi_rescue":
            return "abi_rescue"
        if public_attempt_phase == "semantic_recovery":
            return "semantic_recovery"
        return "primary_continuation"

    def prepare(
        self,
        *,
        logical_request_index: int,
        request_kind: legacy.StageOneRequestKind,
        public_attempt_phase: historical_runner.PublicAttemptPhase,
        primary_prompt: str,
        prompt: str,
        public_state_id: str | None,
        final_response_host_envelope: FinalResponseHostEnvelope | None,
        abi_rescue_count_before: int,
        semantic_recovery_count_before: int,
    ) -> historical_runner.PreparedPrivacyFirstRequest:
        if self._instrument_failures:
            raise historical_runner.InstrumentContractError(
                "cannot prepare after a Recovery Instrument failure"
            )
        if public_state_id is None:
            raise ValueError("v26.126 Recovery request lacks public state")
        provider_phase: legacy.StageOneAttemptPhase = (
            "rescue" if public_attempt_phase == "abi_rescue" else "primary"
        )
        request_binding = legacy.certify_stage_one_request_pre_call(
            config=self._delegate.config,
            prompt=prompt,
            request_kind=request_kind,
            phase=provider_phase,
        )
        resource = _old_resource_certificate(
            self._resource,
            prompt=prompt,
            request_kind=request_kind,
            public_attempt_phase=public_attempt_phase,
            abi_rescue_count_before=abi_rescue_count_before,
            semantic_recovery_count_before=semantic_recovery_count_before,
            cumulative_tokens_before=self.cumulative_tokens,
            combined_provider_call_count_before=self.provider_call_count,
        )
        self._resource_certificates.append(resource)
        dynamic: historical_runner.PrivacyFirstDynamicRequestCertificate | None = None
        if resource.provider_call_permitted:
            dynamic = _old_dynamic_certificate(
                historical_runner_contract=self._historical_runner_contract,
                job=self._job.historical_job,
                logical_request_index=logical_request_index,
                request_kind=request_kind,
                public_attempt_phase=public_attempt_phase,
                primary_prompt=primary_prompt,
                prompt=prompt,
                public_state_id=public_state_id,
                final_response_host_envelope=final_response_host_envelope,
                abi_rescue_count_before=abi_rescue_count_before,
                semantic_recovery_count_before=semantic_recovery_count_before,
            )
        values = {
            "logical_request_index": logical_request_index,
            "request_kind": request_kind,
            "public_attempt_phase": public_attempt_phase,
            "primary_prompt": primary_prompt,
            "prompt": prompt,
            "public_state_id": public_state_id,
            "final_response_host_envelope": final_response_host_envelope,
            "dynamic_certificate": dynamic,
            "request_binding_certificate": request_binding,
            "resource_certificate": resource,
            "provider_invocation_authorized": bool(
                dynamic is not None and resource.provider_call_permitted
            ),
        }
        provisional = historical_runner.PreparedPrivacyFirstRequest.model_construct(
            preparation_id="pending", **values
        )
        prepared = historical_runner.PreparedPrivacyFirstRequest(
            preparation_id=_identity(
                provisional,
                "preparation_id",
                "finance_v26_prepared_privacy_first_request:",
            ),
            **values,
        )
        if dynamic is not None:
            call_index = self.successor_provider_call_count
            call_role = self._call_role(request_kind, public_attempt_phase)
            invocation_values = {
                "recovery_runner_contract_id": self._runner_contract.runner_contract_id,
                "recovery_job_id": self._job.recovery_job_id,
                "recovery_candidate_id": self._job.candidate.candidate_id,
                "historical_job_id": self._job.historical_job.job_id,
                "recovery_provider_call_index": call_index,
                "combined_trajectory_call_index": self.provider_call_count,
                "logical_request_index": logical_request_index,
                "call_role": call_role,
                "exact_failed_call_replacement": call_index == 0,
                "request_kind": request_kind,
                "public_attempt_phase": public_attempt_phase,
                "prompt_sha256": legacy.sha256_text(prompt),
                "public_state_id": public_state_id,
                "historical_dynamic_certificate_id": dynamic.certificate_id,
                "request_binding_certificate_id": request_binding.certificate_id,
                "resource_certificate_id": resource.certificate_id,
                "cumulative_trajectory_tokens_before": self.cumulative_tokens,
                "provider_calls_before_certificate": call_index,
            }
            provisional_invocation = RecoveryInvocationCertificate.model_construct(
                certificate_id="pending", **invocation_values
            )
            invocation = RecoveryInvocationCertificate(
                certificate_id=_identity(
                    provisional_invocation,
                    "certificate_id",
                    "finance_v26_recovery_invocation_certificate:",
                ),
                **invocation_values,
            )
            if call_index == 0:
                candidate = self._job.candidate
                replay = self._prefix.replay
                if (
                    logical_request_index != replay.exact_failed_logical_request_index
                    or public_attempt_phase != "primary"
                    or request_kind != "semantic_proposal"
                    or legacy.sha256_text(prompt) != candidate.request_prompt_sha256
                    or public_state_id != replay.exact_failed_public_state_id
                    or dynamic.certificate_id != candidate.dynamic_certificate_id
                    or request_binding.certificate_id != candidate.request_binding_certificate_id
                    or resource.certificate_id != candidate.resource_certificate_id
                    or self.cumulative_tokens != candidate.cumulative_provider_tokens_before_failure
                ):
                    raise ValueError("v26.126 replacement is not the exact failed request")
            self._invocation_certificates[prepared.preparation_id] = invocation
        return prepared

    def _persist_envelope(
        self,
        *,
        prepared: historical_runner.PreparedPrivacyFirstRequest,
        telemetry: legacy.ModelCallTelemetry,
        failure_artifact: legacy.ProspectiveThinkingFailureArtifact | None,
    ) -> RecoveryProviderEnvelope:
        if prepared.dynamic_certificate is None:
            raise ValueError("v26.126 cannot persist an uncertified call")
        invocation = self._invocation_certificates[prepared.preparation_id]
        call_index = len(self._telemetry)
        values = {
            "recovery_runner_contract_id": self._runner_contract.runner_contract_id,
            "recovery_job_id": self._job.recovery_job_id,
            "recovery_candidate_id": self._job.candidate.candidate_id,
            "historical_job_id": self._job.historical_job.job_id,
            "recovery_provider_call_index": call_index,
            "combined_trajectory_call_index": invocation.combined_trajectory_call_index,
            "logical_request_index": prepared.logical_request_index,
            "request_kind": prepared.request_kind,
            "public_attempt_phase": prepared.public_attempt_phase,
            "call_role": invocation.call_role,
            "prompt_sha256": legacy.sha256_text(prepared.prompt),
            "invocation_certificate": invocation,
            "historical_dynamic_certificate": prepared.dynamic_certificate,
            "request_binding_certificate": prepared.request_binding_certificate,
            "resource_certificate_id": prepared.resource_certificate.certificate_id,
            "final_response_host_envelope_id": (
                prepared.final_response_host_envelope.envelope_id
                if prepared.final_response_host_envelope is not None
                else None
            ),
            "provider_telemetry": telemetry,
            "failure_artifact": failure_artifact,
            "public_content_hash": telemetry.response_hash,
            "public_content_length": telemetry.response_content_length,
        }
        provisional = RecoveryProviderEnvelope.model_construct(envelope_id="pending", **values)
        envelope = RecoveryProviderEnvelope(
            envelope_id=_identity(
                provisional,
                "envelope_id",
                "finance_v26_recovery_provider_envelope:",
            ),
            **values,
        )
        path = recovery_envelope_path(self._output_dir, self._job, call_index)
        _write_json_atomic(path, envelope.model_dump(mode="json"))
        self._telemetry.append(telemetry)
        self._envelope_descriptors.append(_descriptor(path, self._output_dir))
        self._persistence_order.append(("envelope", call_index))
        return envelope

    def _persist_projection(
        self,
        *,
        envelope: RecoveryProviderEnvelope,
        status: historical_runner.PayloadProjectionStatus,
        payload: dict[str, Any] | None,
    ) -> RecoveryPayloadProjection:
        failure_family: str | None = None
        failure_subtype: str | None = None
        if status == "privacy_rejected":
            failure_family = "payload_privacy_failure"
            failure_subtype = "public_payload_omitted_after_privacy_rejection"
        elif status == "provider_failure_no_payload":
            failure_family = "provider_or_completion_failure"
            failure_subtype = "no_public_payload_returned"
        values = {
            "recovery_provider_envelope_id": envelope.envelope_id,
            "recovery_job_id": self._job.recovery_job_id,
            "recovery_provider_call_index": envelope.recovery_provider_call_index,
            "request_kind": envelope.request_kind,
            "projection_status": status,
            "response_payload": payload,
            "failure_family": failure_family,
            "failure_subtype": failure_subtype,
        }
        provisional = RecoveryPayloadProjection.model_construct(projection_id="pending", **values)
        projection = RecoveryPayloadProjection(
            projection_id=_identity(
                provisional,
                "projection_id",
                "finance_v26_recovery_payload_projection:",
            ),
            **values,
        )
        path = recovery_projection_path(
            self._output_dir, self._job, envelope.recovery_provider_call_index
        )
        _write_json_atomic(path, projection.model_dump(mode="json"))
        self._projection_descriptors.append(_descriptor(path, self._output_dir))
        self._projection_statuses.append(status)
        self._persistence_order.append(("projection", envelope.recovery_provider_call_index))
        return projection

    def _charge(
        self,
        prepared: historical_runner.PreparedPrivacyFirstRequest,
        telemetry: legacy.ModelCallTelemetry,
    ) -> None:
        certificate = prepared.resource_certificate
        failures: list[str] = []
        if telemetry.request_hash != certificate.request_prompt_sha256:
            failures.append("request_hash_mismatch")
        if (
            telemetry.model_requested != legacy.STAGE_ONE_MODEL_ID
            or telemetry.model_selected != legacy.STAGE_ONE_MODEL_ID
        ):
            failures.append("requested_or_selected_model_mismatch")
        if telemetry.fallback_used or telemetry.discovery_attempted:
            failures.append("fallback_or_discovery_observed")
        counted = 0
        if telemetry.http_success:
            if telemetry.response_model != legacy.STAGE_ONE_MODEL_ID:
                failures.append("exact_response_model_mismatch_or_missing")
            if telemetry.response_hash is None or telemetry.response_content_length is None:
                failures.append("successful_public_content_hash_or_length_missing")
            prompt_tokens = telemetry.prompt_tokens
            completion_tokens = telemetry.completion_tokens
            total_tokens = telemetry.total_tokens
            if prompt_tokens is None or completion_tokens is None or total_tokens is None:
                failures.append("successful_usage_missing")
            else:
                counted = total_tokens
                if prompt_tokens + completion_tokens != total_tokens:
                    failures.append("prompt_completion_sum_mismatch")
                if prompt_tokens > certificate.prompt_token_upper_bound:
                    failures.append("prompt_upper_bound_exceeded")
                if completion_tokens >= 16386:
                    failures.append("two_or_more_completion_tokens_over_exact_request")
                if total_tokens > certificate.request_token_upper_bound:
                    failures.append("request_upper_bound_exceeded")
                if (
                    self.cumulative_tokens + total_tokens
                    > self._resource.rollout_upper_bound_tokens
                ):
                    failures.append("rollout_upper_bound_exceeded")
        self._successor_tokens += counted
        self._instrument_failures.update(failures)

    def invoke(
        self,
        prepared: historical_runner.PreparedPrivacyFirstRequest,
    ) -> tuple[dict[str, Any], legacy.ModelCallTelemetry]:
        if prepared.preparation_id in self._used_preparations:
            raise historical_runner.InstrumentContractError("Recovery preparation was reused")
        self._used_preparations.add(prepared.preparation_id)
        if not prepared.resource_certificate.provider_call_permitted:
            raise historical_runner.BudgetNoCallError(
                str(prepared.resource_certificate.denial_reason)
            )
        if (
            not prepared.provider_invocation_authorized
            or prepared.dynamic_certificate is None
            or prepared.preparation_id not in self._invocation_certificates
        ):
            raise historical_runner.InstrumentContractError(
                "Recovery invocation lacks all certificates"
            )
        try:
            payload, telemetry = self._delegate.complete_json_certified(
                prepared.prompt, prepared.request_binding_certificate
            )
        except legacy.LLMClientError as exc:
            failure = (
                exc.failure_artifact
                if isinstance(exc.failure_artifact, legacy.ProspectiveThinkingFailureArtifact)
                else None
            )
            if len(exc.telemetry) != 1:
                self._instrument_failures.add("multiple_or_missing_model_attempt_telemetry")
            for telemetry in exc.telemetry:
                envelope = self._persist_envelope(
                    prepared=prepared,
                    telemetry=telemetry,
                    failure_artifact=failure,
                )
                self._charge(prepared, telemetry)
                projection = self._persist_projection(
                    envelope=envelope,
                    status="provider_failure_no_payload",
                    payload=None,
                )
                validate_recovery_provider_pair(envelope, projection)
            if self._instrument_failures:
                raise historical_runner.InstrumentContractError(
                    ";".join(self.instrument_failures)
                ) from exc
            raise
        envelope = self._persist_envelope(
            prepared=prepared,
            telemetry=telemetry,
            failure_artifact=None,
        )
        self._charge(prepared, telemetry)
        if legacy.contains_private_reasoning(payload):
            projection = self._persist_projection(
                envelope=envelope,
                status="privacy_rejected",
                payload=None,
            )
            validate_recovery_provider_pair(envelope, projection)
            if self._instrument_failures:
                raise historical_runner.InstrumentContractError(";".join(self.instrument_failures))
            raise historical_runner.PayloadPrivacyProjectionError
        projection = self._persist_projection(
            envelope=envelope,
            status="validated_public_payload",
            payload=payload,
        )
        validate_recovery_provider_pair(envelope, projection)
        if self._instrument_failures:
            raise historical_runner.InstrumentContractError(";".join(self.instrument_failures))
        return payload, telemetry


def _load_recovery_raw(
    *,
    recovery_job: ExactFailedCallRecoveryJob,
    runner_contract: ExactFailedCallRecoveryRunnerContract,
    static: static_stage.FinalGrammarStaticInputs,
    historical_runner_contract: historical_runner.PrivacyFirstRunnerContract,
    historical_execution_dir: Path,
    output_dir: Path,
) -> RecoveryRawExecution | None:
    path = recovery_raw_path(output_dir, recovery_job)
    if not path.exists():
        return None
    raw = RecoveryRawExecution.model_validate(_load(path))
    if (
        raw.recovery_runner_contract_id != runner_contract.runner_contract_id
        or raw.recovery_job != recovery_job
    ):
        raise ValueError("v26.126 Raw recovery crosses fresh identities")
    prefix = replay_successful_prefix(
        recovery_job=recovery_job,
        static=static,
        historical_runner_contract=historical_runner_contract,
        historical_execution_dir=historical_execution_dir,
    )
    if raw.prefix_replay != prefix.replay:
        raise ValueError("v26.126 Raw recovery historical prefix changed")
    envelopes: list[RecoveryProviderEnvelope] = []
    for descriptor in raw.successor_provider_envelope_artifacts:
        artifact = output_dir / descriptor.relative_path
        if not artifact.is_file() or legacy.sha256_file(artifact) != descriptor.sha256:
            raise ValueError("v26.126 Raw recovery Envelope bytes changed")
        envelopes.append(RecoveryProviderEnvelope.model_validate(_load(artifact)))
    projections: list[RecoveryPayloadProjection] = []
    for descriptor in raw.successor_payload_projection_artifacts:
        artifact = output_dir / descriptor.relative_path
        if not artifact.is_file() or legacy.sha256_file(artifact) != descriptor.sha256:
            raise ValueError("v26.126 Raw recovery Projection bytes changed")
        projections.append(RecoveryPayloadProjection.model_validate(_load(artifact)))
    expected = list(range(raw.successor_provider_call_count))
    if (
        [item.recovery_provider_call_index for item in envelopes] != expected
        or [item.recovery_provider_call_index for item in projections] != expected
        or [item.provider_telemetry for item in envelopes] != list(raw.successor_provider_telemetry)
    ):
        raise ValueError("v26.126 Raw recovery Provider ordering changed")
    for envelope, projection in zip(envelopes, projections, strict=True):
        validate_recovery_provider_pair(envelope, projection)
    return raw


def _assert_no_recovery_orphans(
    output_dir: Path,
    recovery_job: ExactFailedCallRecoveryJob,
) -> None:
    envelope_dir = recovery_envelope_path(output_dir, recovery_job, 0).parent
    projection_dir = recovery_projection_path(output_dir, recovery_job, 0).parent
    envelopes = tuple(envelope_dir.glob("call_*.json")) if envelope_dir.exists() else ()
    projections = tuple(projection_dir.glob("call_*.json")) if projection_dir.exists() else ()
    if envelopes or projections:
        raise ValueError("orphan v26.126 Recovery artifacts forbid another replacement")


def _finish_recovery_raw(
    *,
    recovery_job: ExactFailedCallRecoveryJob,
    runner_contract: ExactFailedCallRecoveryRunnerContract,
    prefix: PrefixRuntimeState,
    ledger: RecoveryJournaledClient,
    attempts: Sequence[historical_runner.PrivacyFirstAttempt],
    choices: Sequence[semantic_execution.SemanticChoiceRecord],
    commits: Sequence[semantic_execution.SemanticActionCommitRecord],
    semantic_rejections: Sequence[PublicSemanticRejectionObservation],
    observations: Sequence[AgentToolObservation],
    completed: RecoveryCompletedResult | None,
    terminal: historical_runner.TerminalDisposition,
    failure_type: str | None,
    error: str | None,
    output_dir: Path,
) -> RecoveryRawExecution:
    values = {
        "recovery_runner_contract_id": runner_contract.runner_contract_id,
        "recovery_job": recovery_job,
        "job": recovery_job.historical_job,
        "prefix_replay": prefix.replay,
        "operational_record_id": prefix.binding.record.record_id,
        "environment_manifest_id": prefix.binding.environment.manifest_id,
        "path_audit_id": recovery_job.historical_job.path_audit_id,
        "successor_provider_envelope_artifacts": ledger.envelope_descriptors,
        "successor_payload_projection_artifacts": ledger.projection_descriptors,
        "historical_prefix_provider_telemetry": prefix.historical_prefix_telemetry,
        "successor_provider_telemetry": ledger.telemetry,
        "attempts": tuple(attempts),
        "semantic_choices": tuple(choices),
        "commits": tuple(commits),
        "semantic_rejections": tuple(semantic_rejections),
        "observations": tuple(observations),
        "completed_result": completed,
        "terminal_disposition": terminal,
        "terminal_failure_type": failure_type,
        "execution_error": error,
        "historical_successful_prefix_tokens": (recovery_job.successful_prefix_cumulative_tokens),
        "successor_provider_tokens": ledger.successor_tokens,
        "cumulative_provider_tokens": ledger.cumulative_tokens,
        "historical_successful_prefix_provider_call_count": (
            recovery_job.successful_prefix_provider_call_count
        ),
        "successor_provider_call_count": ledger.successor_provider_call_count,
        "stage_one_provider_call_count": ledger.provider_call_count,
        "abi_rescue_attempt_count": sum(
            item.public_attempt_phase == "abi_rescue" for item in attempts
        ),
        "semantic_recovery_attempt_count": sum(
            item.public_attempt_phase == "semantic_recovery" for item in choices
        ),
        "first_choice_semantic_rejection_count": sum(
            item.public_attempt_phase == "primary" and not item.semantic_accepted
            for item in choices
        ),
        "privacy_rejected_payload_count": sum(
            item == "privacy_rejected" for item in ledger.projection_statuses
        ),
    }
    provisional = RecoveryRawExecution.model_construct(artifact_id="pending", **values)
    raw = RecoveryRawExecution(
        artifact_id=_identity(
            provisional,
            "artifact_id",
            "finance_v26_recovery_raw_execution:",
        ),
        **values,
    )
    _write_json_atomic(recovery_raw_path(output_dir, recovery_job), raw.model_dump(mode="json"))
    return raw


def execute_recovery_job_raw(
    *,
    recovery_job: ExactFailedCallRecoveryJob,
    runner_contract: ExactFailedCallRecoveryRunnerContract,
    historical_runner_contract: historical_runner.PrivacyFirstRunnerContract,
    static: static_stage.FinalGrammarStaticInputs,
    historical_execution_dir: Path,
    client: Any | None,
    output_dir: Path,
) -> RecoveryRawExecution:
    existing = _load_recovery_raw(
        recovery_job=recovery_job,
        runner_contract=runner_contract,
        static=static,
        historical_runner_contract=historical_runner_contract,
        historical_execution_dir=historical_execution_dir,
        output_dir=output_dir,
    )
    if existing is not None:
        return existing
    _assert_no_recovery_orphans(output_dir, recovery_job)
    if client is None:
        raise ValueError("pending v26.126 RecoveryJob has no Stage 1 client")
    prefix = replay_successful_prefix(
        recovery_job=recovery_job,
        static=static,
        historical_runner_contract=historical_runner_contract,
        historical_execution_dir=historical_execution_dir,
    )
    ledger = RecoveryJournaledClient(
        client,
        runner_contract=runner_contract,
        historical_runner_contract=historical_runner_contract,
        resource_contract=static.resource,
        recovery_job=recovery_job,
        prefix=prefix,
        output_dir=output_dir,
    )
    binding = prefix.binding
    runtime = prefix.runtime
    observations = list(prefix.observations)
    attempts = list(prefix.attempts)
    choices = list(prefix.choices)
    commits = list(prefix.commits)
    semantic_rejections = list(prefix.semantic_rejections)
    abi_rescue_count = recovery_job.candidate.abi_rescue_count_before
    semantic_recovery_count = recovery_job.candidate.semantic_recovery_count_before
    pending_semantic_recovery = False
    prior_rejected_action_id: str | None = None
    condition = _condition(binding)
    terminal: historical_runner.TerminalDisposition = "model_result"
    failure_type: str | None = None
    error: str | None = None
    completed: RecoveryCompletedResult | None = None
    final_state: SemanticActionState | None = None
    final_commit: CanonicalActionCommit | None = None
    logical_index = recovery_job.successful_prefix_provider_call_count
    remaining_action_requests = (
        static.resource.maximum_primary_stage_one_requests - 1 - logical_index
    )
    for _ in range(remaining_action_requests):
        state = build_semantic_action_state(
            binding.record.task_package.task.public,
            binding.environment,
            tuple(observations),
            semantic_rejections=tuple(semantic_rejections),
        )
        presentation_salt = canonical_hash(
            {
                "job_id": recovery_job.historical_job.job_id,
                "logical_request_index": logical_index,
                "state_id": state.state_id,
                "semantic_recovery_count": semantic_recovery_count,
            },
            prefix="finance_v26_runner_candidate_presentation:",
        )
        phase: Literal["primary", "semantic_recovery"] = (
            "semantic_recovery" if pending_semantic_recovery else "primary"
        )
        prompt = (
            render_exact_canonical_action_semantic_recovery_prompt(
                instruction=binding.record.task_package.task.public.instruction,
                state=state,
                public_path_condition=condition,
                presentation_salt=presentation_salt,
            )
            if pending_semantic_recovery
            else render_exact_canonical_action_prompt(
                instruction=binding.record.task_package.task.public.instruction,
                state=state,
                public_path_condition=condition,
                presentation_salt=presentation_salt,
                grammar=static.action_grammar,
            )
        )
        outcome, abi_rescue_count = historical_runner._active_outcome(
            cast(Any, ledger),
            attempts=attempts,
            logical_request_index=logical_index,
            request_kind="semantic_proposal",
            public_attempt_phase=phase,
            primary_prompt=prompt,
            state=state,
            final_response_host_envelope=None,
            static=static,
            abi_rescue_count=abi_rescue_count,
            semantic_recovery_count=semantic_recovery_count,
        )
        current_index = logical_index
        logical_index += 1
        if outcome.attempt.disposition != "usable" or outcome.proposal is None:
            terminal = historical_runner._terminal_from_attempt(outcome.attempt)
            failure_type = (
                outcome.attempt.failure_subtype
                or outcome.attempt.completion_failure_type
                or outcome.attempt.disposition
            )
            error = outcome.attempt.error
            break
        proposal = outcome.proposal
        selected = evaluate_canonical_action_proposal(
            state, proposal, call_index=len(observations) + 1
        )
        if selected.rejection is not None:
            choices.append(
                semantic_execution._choice_record(
                    logical_request_index=current_index,
                    phase=phase,
                    state=state,
                    proposal=proposal,
                    commit=None,
                    rejection=selected.rejection,
                    prior_rejected_action_id=prior_rejected_action_id,
                    observation=None,
                    progress=None,
                )
            )
            if semantic_recovery_count == 0 and selected.rejection.semantic_recovery_available:
                semantic_recovery_count = 1
                semantic_rejections.append(selected.rejection)
                prior_rejected_action_id = proposal.action_id
                pending_semantic_recovery = True
                continue
            terminal = "model_result"
            failure_type = "semantic_recovery_exhausted"
            error = selected.rejection.error_category
            break
        commit = selected.commit
        if commit is None:
            raise ValueError("accepted v26.126 action lacks a Commit")
        commit_values = {
            "logical_request_index": current_index,
            "public_state_id": state.state_id,
            "proposal": proposal,
            "commit": commit,
            "stage_two_profile_id": static.stage_two.profile_id,
            "provider_calls_before_commit": ledger.provider_call_count,
        }
        provisional_commit = semantic_execution.SemanticActionCommitRecord.model_construct(
            record_id="pending", **commit_values
        )
        commits.append(
            semantic_execution.SemanticActionCommitRecord(
                record_id=_identity(
                    provisional_commit,
                    "record_id",
                    "finance_v26_semantic_action_commit_record:",
                ),
                **commit_values,
            )
        )
        pending_semantic_recovery = False
        observation: AgentToolObservation | None = None
        progress: bool | None = None
        if commit.call is not None:
            observation = legacy._execute_observation(
                record=binding.record,
                environment=binding.environment,
                runtime=runtime,
                observations=tuple(observations),
                projection=CompletionProjection(
                    request_kind="decision",
                    action="call_tool",
                    tool_id=commit.call.tool_id,
                    arguments=commit.call.arguments,
                ),
            )
            observations.append(observation)
            after = build_semantic_action_state(
                binding.record.task_package.task.public,
                binding.environment,
                tuple(observations),
                semantic_rejections=tuple(semantic_rejections),
            )
            progress = semantic_execution._public_progress(state, after, observation)
        choices.append(
            semantic_execution._choice_record(
                logical_request_index=current_index,
                phase=phase,
                state=state,
                proposal=proposal,
                commit=commit,
                rejection=None,
                prior_rejected_action_id=prior_rejected_action_id,
                observation=observation,
                progress=progress,
            )
        )
        if commit.action == "emit_final":
            final_state = state
            final_commit = commit
            break
    else:
        terminal = "model_result"
        failure_type = "semantic_action_primary_request_limit_exhausted"
        error = "model did not reach Final within the frozen request limit"
    if (
        final_state is not None
        and final_commit is not None
        and terminal == "model_result"
        and failure_type is None
    ):
        compact_source = render_compact_final_prompt(
            binding.prompt_contract.public_context,
            binding.record.task_package.task.public,
            tuple(observations),
            public_path_condition=condition,
        )
        final_prompt = render_exact_final_primary_prompt(
            compact_source,
            grammar=static.final_grammar,
        )
        host_envelope = make_final_response_host_envelope(
            terminal_state_id=final_state.state_id,
            terminal_commit_id=final_commit.commit_id,
            grammar=static.final_grammar,
        )
        outcome, abi_rescue_count = historical_runner._active_outcome(
            cast(Any, ledger),
            attempts=attempts,
            logical_request_index=logical_index,
            request_kind="final_answer",
            public_attempt_phase="primary",
            primary_prompt=final_prompt,
            state=None,
            final_response_host_envelope=host_envelope,
            static=static,
            abi_rescue_count=abi_rescue_count,
            semantic_recovery_count=semantic_recovery_count,
        )
        if outcome.attempt.disposition == "usable" and outcome.final_payload is not None:
            citations = legacy._selected_evidence_ids(observations)
            if not citations:
                terminal = "model_result"
                failure_type = "final_answer_without_public_evidence"
                error = "Final answer has no selected public Evidence"
            else:
                completed_values = {
                    "recovery_job_id": recovery_job.recovery_job_id,
                    "job_id": recovery_job.historical_job.job_id,
                    "answer": outcome.final_payload.answer,
                    "rationale_summary": outcome.final_payload.rationale_summary,
                    "cited_evidence_ids": citations,
                    "final_attempt_id": outcome.attempt.attempt_id,
                    "final_response_host_envelope": host_envelope,
                }
                provisional_completed = RecoveryCompletedResult.model_construct(
                    result_id="pending", **completed_values
                )
                completed = RecoveryCompletedResult(
                    result_id=_identity(
                        provisional_completed,
                        "result_id",
                        "finance_v26_recovery_completed_result:",
                    ),
                    **completed_values,
                )
                terminal = "completed"
        else:
            terminal = historical_runner._terminal_from_attempt(outcome.attempt)
            failure_type = (
                outcome.attempt.failure_subtype
                or outcome.attempt.completion_failure_type
                or outcome.attempt.disposition
            )
            error = outcome.attempt.error
    if ledger.instrument_failures:
        terminal = "instrument_failure"
        failure_type = "provider_usage_or_binding_contract_failure"
        error = ";".join(ledger.instrument_failures)
        completed = None
    return _finish_recovery_raw(
        recovery_job=recovery_job,
        runner_contract=runner_contract,
        prefix=prefix,
        ledger=ledger,
        attempts=attempts,
        choices=choices,
        commits=commits,
        semantic_rejections=semantic_rejections,
        observations=observations,
        completed=completed,
        terminal=terminal,
        failure_type=failure_type,
        error=error,
        output_dir=output_dir,
    )


class ScriptedTransportFailureClient:
    def __init__(self, config: Any) -> None:
        self.config = config
        self._base = historical_preflight.ScriptedPrivacyFirstClient(config)
        self.call_count = 0

    def complete_json_certified(
        self,
        prompt: str,
        certificate: legacy.StageOneRequestBindingCertificate,
    ) -> tuple[dict[str, Any], legacy.ModelCallTelemetry]:
        _, telemetry = self._base.complete_json_certified(prompt, certificate)
        self.call_count += 1
        failed = telemetry.model_copy(
            update={
                "response_model": None,
                "http_status": None,
                "http_success": False,
                "json_contract_success": False,
                "finish_reason": None,
                "response_hash": None,
                "response_content_length": None,
                "reasoning_content_present": False,
                "reasoning_content_length": None,
                "reasoning_tokens": None,
                "prompt_tokens": None,
                "completion_tokens": None,
                "total_tokens": None,
                "estimated_cost": None,
                "latency_ms": 1,
            }
        )
        raise legacy.LLMClientError(
            "scripted replacement transport failure",
            (failed,),
            request_prompts=(prompt,),
        )


def _build_prefix_audit(
    *,
    prepared: PreparedRecoveryPreflight,
    historical_execution_dir: Path,
) -> PrefixReplayAudit:
    rows = tuple(
        replay_successful_prefix(
            recovery_job=job,
            static=prepared.static,
            historical_runner_contract=prepared.historical_runner_contract,
            historical_execution_dir=historical_execution_dir,
        ).replay
        for job in prepared.recovery_manifest.jobs
    )
    counts = {
        index: sum(item.successful_prefix_provider_call_count == index for item in rows)
        for index in range(3)
    }
    values = {
        "rows": rows,
        "zero_prefix_job_count": counts[0],
        "one_call_prefix_job_count": counts[1],
        "two_call_prefix_job_count": counts[2],
        "successful_prefix_provider_call_count": sum(
            item.successful_prefix_provider_call_count for item in rows
        ),
        "rebuilt_observation_count": sum(item.runtime_observation_rebuild_count for item in rows),
    }
    provisional = PrefixReplayAudit.model_construct(audit_id="pending", **values)
    return PrefixReplayAudit(
        audit_id=_identity(
            provisional,
            "audit_id",
            "finance_v26_prefix_replay_audit:",
        ),
        **values,
    )


def _load_recovery_pairs(
    raw: RecoveryRawExecution,
    root: Path,
) -> tuple[tuple[RecoveryProviderEnvelope, RecoveryPayloadProjection], ...]:
    envelopes = tuple(
        RecoveryProviderEnvelope.model_validate(_load(root / item.relative_path))
        for item in raw.successor_provider_envelope_artifacts
    )
    projections = tuple(
        RecoveryPayloadProjection.model_validate(_load(root / item.relative_path))
        for item in raw.successor_payload_projection_artifacts
    )
    pairs = tuple(zip(envelopes, projections, strict=True))
    for envelope, projection in pairs:
        validate_recovery_provider_pair(envelope, projection)
    return pairs


def _build_scripted_recovery_audit(
    *,
    prepared: PreparedRecoveryPreflight,
    historical_execution_dir: Path,
    root: Path,
) -> tuple[ScriptedRecoveryAudit, tuple[RecoveryRawExecution, ...]]:
    rows: list[ScriptedRecoveryRow] = []
    raws: list[RecoveryRawExecution] = []
    for recovery_job in prepared.recovery_manifest.jobs:
        binding = historical_runner.privacy_first_runtime_binding(
            prepared.static, recovery_job.historical_job
        )
        client = historical_preflight.ScriptedPrivacyFirstClient(
            prepared.static.agent_model_config,
            final_answer=binding.compiler_trajectory.final_answer,
        )
        raw = execute_recovery_job_raw(
            recovery_job=recovery_job,
            runner_contract=prepared.runner_contract,
            historical_runner_contract=prepared.historical_runner_contract,
            static=prepared.static,
            historical_execution_dir=historical_execution_dir,
            client=client,
            output_dir=root,
        )
        replay = legacy.replay_v3(
            cast(Any, raw),
            static=prepared.static.predecessor.historical,
            binding=binding,
        )
        verification, mechanism = _completed_verification(
            raw=cast(Any, raw),
            replay=replay,
            binding=binding,
        )
        pairs = _load_recovery_pairs(raw, root)
        exact_final = sum(
            item.exact_two_field_final_payload
            for item in raw.attempts
            if item.request_kind == "final_answer"
        )
        if (
            raw.terminal_disposition != "completed"
            or raw.completed_result is None
            or raw.successor_provider_call_count != client.call_count
            or raw.exact_failed_call_replacement_attempt_count != 1
            or not replay.passed
            or not verification.valid
            or not mechanism.success
            or exact_final != 1
            or len(pairs) != raw.successor_provider_call_count
            or any(
                envelope.invocation_certificate.exact_failed_call_replacement != (index == 0)
                for index, (envelope, _) in enumerate(pairs)
            )
            or raw.stage_two_provider_call_count
        ):
            raise ValueError(f"v26.126 scripted Recovery failed: {recovery_job.recovery_job_id}")
        rows.append(
            ScriptedRecoveryRow(
                recovery_job_id=recovery_job.recovery_job_id,
                raw_execution_id=raw.artifact_id,
                historical_prefix_call_count=(recovery_job.successful_prefix_provider_call_count),
                successor_scripted_call_count=raw.successor_provider_call_count,
            )
        )
        raws.append(raw)
    values = {"rows": tuple(rows)}
    provisional = ScriptedRecoveryAudit.model_construct(audit_id="pending", **values)
    audit = ScriptedRecoveryAudit(
        audit_id=_identity(
            provisional,
            "audit_id",
            "finance_v26_scripted_transport_recovery_audit:",
        ),
        **values,
    )
    return audit, tuple(raws)


def _single_recovery_ledger_call(
    *,
    prepared: PreparedRecoveryPreflight,
    recovery_job: ExactFailedCallRecoveryJob,
    historical_execution_dir: Path,
    output_dir: Path,
    completion_tokens: int,
) -> tuple[bool, RecoveryJournaledClient]:
    prefix = replay_successful_prefix(
        recovery_job=recovery_job,
        static=prepared.static,
        historical_runner_contract=prepared.historical_runner_contract,
        historical_execution_dir=historical_execution_dir,
    )
    client = historical_preflight.ScriptedPrivacyFirstClient(
        prepared.static.agent_model_config,
        completion_tokens=completion_tokens,
    )
    ledger = RecoveryJournaledClient(
        client,
        runner_contract=prepared.runner_contract,
        historical_runner_contract=prepared.historical_runner_contract,
        resource_contract=prepared.static.resource,
        recovery_job=recovery_job,
        prefix=prefix,
        output_dir=output_dir,
    )
    request = ledger.prepare(
        logical_request_index=prefix.replay.exact_failed_logical_request_index,
        request_kind="semantic_proposal",
        public_attempt_phase="primary",
        primary_prompt=prefix.failed_prompt,
        prompt=prefix.failed_prompt,
        public_state_id=prefix.failed_state.state_id,
        final_response_host_envelope=None,
        abi_rescue_count_before=recovery_job.candidate.abi_rescue_count_before,
        semantic_recovery_count_before=recovery_job.candidate.semantic_recovery_count_before,
    )
    try:
        ledger.invoke(request)
    except historical_runner.InstrumentContractError:
        return False, ledger
    return True, ledger


def _build_control_audit(
    *,
    prepared: PreparedRecoveryPreflight,
    historical_execution_dir: Path,
    root: Path,
) -> RecoveryControlAudit:
    job = next(
        item
        for item in prepared.recovery_manifest.jobs
        if item.successful_prefix_provider_call_count == 0
    )
    binding = historical_runner.privacy_first_runtime_binding(prepared.static, job.historical_job)
    transport_client = ScriptedTransportFailureClient(prepared.static.agent_model_config)
    transport_raw = execute_recovery_job_raw(
        recovery_job=job,
        runner_contract=prepared.runner_contract,
        historical_runner_contract=prepared.historical_runner_contract,
        static=prepared.static,
        historical_execution_dir=historical_execution_dir,
        client=transport_client,
        output_dir=root / "transport_failure",
    )
    if (
        transport_raw.terminal_disposition != "provider_transport_failure"
        or transport_raw.successor_provider_call_count != 1
        or transport_client.call_count != 1
    ):
        raise ValueError("v26.126 replacement Transport failure was retried")
    combined_client = historical_preflight.ScriptedPrivacyFirstClient(
        prepared.static.agent_model_config,
        final_answer=binding.compiler_trajectory.final_answer,
        combined_recovery_control=True,
    )
    combined = execute_recovery_job_raw(
        recovery_job=job,
        runner_contract=prepared.runner_contract,
        historical_runner_contract=prepared.historical_runner_contract,
        static=prepared.static,
        historical_execution_dir=historical_execution_dir,
        client=combined_client,
        output_dir=root / "combined_recovery",
    )
    if (
        combined.terminal_disposition != "completed"
        or combined.abi_rescue_attempt_count != 1
        or combined.semantic_recovery_attempt_count != 1
        or combined.first_choice_semantic_rejection_count != 1
    ):
        raise ValueError("v26.126 ABI and Semantic Recovery control failed")
    boundary: dict[int, tuple[bool, RecoveryJournaledClient]] = {}
    for completion in (16384, 16385, 16386):
        boundary[completion] = _single_recovery_ledger_call(
            prepared=prepared,
            recovery_job=job,
            historical_execution_dir=historical_execution_dir,
            output_dir=root / f"usage_{completion}",
            completion_tokens=completion,
        )
    admitted_16384, ledger_16384 = boundary[16384]
    admitted_16385, ledger_16385 = boundary[16385]
    admitted_16386, ledger_16386 = boundary[16386]
    if (
        not admitted_16384
        or not admitted_16385
        or admitted_16386
        or ledger_16385.successor_tokens != cast(int, ledger_16385.telemetry[0].total_tokens)
        or "two_or_more_completion_tokens_over_exact_request"
        not in ledger_16386.instrument_failures
        or ledger_16384.persistence_order != (("envelope", 0), ("projection", 0))
    ):
        raise ValueError("v26.126 Provider Usage or persistence-order control failed")
    raw_root = root / "raw_recovery"
    raw_client = historical_preflight.ScriptedPrivacyFirstClient(
        prepared.static.agent_model_config,
        final_answer=binding.compiler_trajectory.final_answer,
    )
    first = execute_recovery_job_raw(
        recovery_job=job,
        runner_contract=prepared.runner_contract,
        historical_runner_contract=prepared.historical_runner_contract,
        static=prepared.static,
        historical_execution_dir=historical_execution_dir,
        client=raw_client,
        output_dir=raw_root,
    )
    recovered = execute_recovery_job_raw(
        recovery_job=job,
        runner_contract=prepared.runner_contract,
        historical_runner_contract=prepared.historical_runner_contract,
        static=prepared.static,
        historical_execution_dir=historical_execution_dir,
        client=None,
        output_dir=raw_root,
    )
    if first != recovered:
        raise ValueError("v26.126 complete Raw recovery changed bytes")
    orphan_root = root / "orphan"
    orphan = recovery_envelope_path(orphan_root, job, 0)
    orphan.parent.mkdir(parents=True, exist_ok=True)
    orphan.write_text("{}", encoding="utf-8")
    orphan_client = historical_preflight.ScriptedPrivacyFirstClient(
        prepared.static.agent_model_config
    )
    orphan_blocked = False
    try:
        execute_recovery_job_raw(
            recovery_job=job,
            runner_contract=prepared.runner_contract,
            historical_runner_contract=prepared.historical_runner_contract,
            static=prepared.static,
            historical_execution_dir=historical_execution_dir,
            client=orphan_client,
            output_dir=orphan_root,
        )
    except ValueError:
        orphan_blocked = orphan_client.call_count == 0
    if not orphan_blocked:
        raise ValueError("v26.126 orphan Recovery artifact did not block retry")
    values: dict[str, Any] = {}
    provisional = RecoveryControlAudit.model_construct(audit_id="pending", **values)
    return RecoveryControlAudit(
        audit_id=_identity(
            provisional,
            "audit_id",
            "finance_v26_transport_recovery_control_audit:",
        ),
        **values,
    )


def _with_identity(
    payload: dict[str, Any],
    *,
    identity_field: str,
    prefix: str,
) -> dict[str, Any]:
    return {
        **payload,
        identity_field: canonical_hash(
            {key: value for key, value in payload.items() if key != identity_field},
            prefix=prefix,
        ),
    }


def _expect_rejected(
    model_type: type[BaseModel],
    payload: dict[str, Any],
    name: str,
) -> MutationResult:
    try:
        model_type.model_validate(payload)
    except (ValueError, TypeError):
        return MutationResult(name=name)
    raise ValueError(f"v26.126 destructive mutation was accepted: {name}")


def _build_destructive_audit(
    *,
    prepared: PreparedRecoveryPreflight,
    scripted_raws: Sequence[RecoveryRawExecution],
    scripted_root: Path,
) -> DestructiveAudit:
    contract = prepared.recovery_contract
    manifest = prepared.recovery_manifest
    runner_contract = prepared.runner_contract
    job = manifest.jobs[0]
    other_job = manifest.jobs[1]
    pairs = _load_recovery_pairs(scripted_raws[0], scripted_root)
    envelope, projection = pairs[0]
    raw = scripted_raws[0]
    mutations: list[MutationResult] = []

    payload = contract.model_dump(mode="json")
    payload["recovery_candidate_ids"][-1] = payload["recovery_candidate_ids"][0]
    mutations.append(
        _expect_rejected(
            ExactFailedCallRecoveryContract,
            _with_identity(
                payload,
                identity_field="contract_id",
                prefix="finance_v26_exact_failed_call_recovery_contract:",
            ),
            "candidate_identity_duplicated",
        )
    )
    payload = contract.model_dump(mode="json")
    payload["provider_calls_authorized"] = True
    mutations.append(
        _expect_rejected(
            ExactFailedCallRecoveryContract,
            payload,
            "preflight_contract_authorized_provider_calls",
        )
    )
    payload = job.model_dump(mode="json")
    payload["candidate"] = other_job.candidate.model_dump(mode="json")
    mutations.append(
        _expect_rejected(
            ExactFailedCallRecoveryJob,
            _with_identity(
                payload,
                identity_field="recovery_job_id",
                prefix="finance_v26_exact_failed_call_recovery_job:",
            ),
            "candidate_swapped_between_recovery_jobs",
        )
    )
    payload = job.model_dump(mode="json")
    payload["historical_job_reclassified"] = True
    mutations.append(
        _expect_rejected(
            ExactFailedCallRecoveryJob,
            payload,
            "historical_job_reclassification_enabled",
        )
    )
    payload = job.model_dump(mode="json")
    payload["successful_prefix_provider_calls_authorized"] = 1
    mutations.append(
        _expect_rejected(
            ExactFailedCallRecoveryJob,
            payload,
            "historical_prefix_provider_call_authorized",
        )
    )
    payload = manifest.model_dump(mode="json")
    payload["jobs"] = payload["jobs"][:-1]
    mutations.append(
        _expect_rejected(
            ExactFailedCallRecoveryManifest,
            payload,
            "recovery_job_removed",
        )
    )
    payload = manifest.model_dump(mode="json")
    payload["jobs"][-1] = payload["jobs"][0]
    mutations.append(
        _expect_rejected(
            ExactFailedCallRecoveryManifest,
            _with_identity(
                payload,
                identity_field="manifest_id",
                prefix="finance_v26_exact_failed_call_recovery_manifest:",
            ),
            "recovery_job_duplicated",
        )
    )
    payload = runner_contract.model_dump(mode="json")
    payload["resource_contract_id"] = "finance_v26_final_grammar_resource_contract:" + "f" * 64
    mutations.append(
        _expect_rejected(
            ExactFailedCallRecoveryRunnerContract,
            _with_identity(
                payload,
                identity_field="runner_contract_id",
                prefix="finance_v26_exact_failed_call_recovery_runner_contract:",
            ),
            "resource_contract_changed",
        )
    )
    payload = runner_contract.model_dump(mode="json")
    payload["maximum_replacement_calls_per_recovery_job"] = 2
    mutations.append(
        _expect_rejected(
            ExactFailedCallRecoveryRunnerContract,
            payload,
            "second_replacement_authorized",
        )
    )
    payload = runner_contract.model_dump(mode="json")
    payload["stage_two_provider_call_upper_bound"] = 1
    mutations.append(
        _expect_rejected(
            ExactFailedCallRecoveryRunnerContract,
            payload,
            "stage_two_provider_route_added",
        )
    )
    invocation = envelope.invocation_certificate
    payload = invocation.model_dump(mode="json")
    payload["exact_failed_call_replacement"] = False
    mutations.append(
        _expect_rejected(
            RecoveryInvocationCertificate,
            _with_identity(
                payload,
                identity_field="certificate_id",
                prefix="finance_v26_recovery_invocation_certificate:",
            ),
            "first_recovery_call_not_replacement",
        )
    )
    payload = invocation.model_dump(mode="json")
    payload["original_failed_call_usage_included"] = True
    mutations.append(
        _expect_rejected(
            RecoveryInvocationCertificate,
            payload,
            "original_failed_usage_imputed_in_certificate",
        )
    )
    payload = envelope.model_dump(mode="json")
    payload["recovery_job_id"] = other_job.recovery_job_id
    mutations.append(
        _expect_rejected(
            RecoveryProviderEnvelope,
            _with_identity(
                payload,
                identity_field="envelope_id",
                prefix="finance_v26_recovery_provider_envelope:",
            ),
            "provider_envelope_parent_changed",
        )
    )
    payload = envelope.model_dump(mode="json")
    payload["payload_content_persisted"] = True
    mutations.append(
        _expect_rejected(
            RecoveryProviderEnvelope,
            payload,
            "payload_persisted_in_envelope",
        )
    )
    payload = projection.model_dump(mode="json")
    payload["response_payload"] = {"reasoning_trace": "forbidden"}
    mutations.append(
        _expect_rejected(
            RecoveryPayloadProjection,
            _with_identity(
                payload,
                identity_field="projection_id",
                prefix="finance_v26_recovery_payload_projection:",
            ),
            "private_reasoning_projected",
        )
    )
    payload = raw.model_dump(mode="json")
    payload["original_failed_call_usage_imputed"] = True
    mutations.append(
        _expect_rejected(
            RecoveryRawExecution,
            payload,
            "original_failed_usage_imputed_in_raw",
        )
    )
    ordered = tuple(sorted(mutations, key=lambda item: item.name))
    values = {"mutations": ordered}
    provisional = DestructiveAudit.model_construct(audit_id="pending", **values)
    return DestructiveAudit(
        audit_id=_identity(
            provisional,
            "audit_id",
            "finance_v26_transport_recovery_destructive:",
        ),
        **values,
    )


def build_preflight(
    *,
    package_root: Path,
    implementation_root: Path,
    historical_audit_dir: Path,
    historical_execution_dir: Path,
    output_dir: Path,
) -> RecoveryPreflightReport:
    prepared = prepare_recovery_preflight(
        package_root=package_root,
        implementation_root=implementation_root,
        historical_audit_dir=historical_audit_dir,
        historical_execution_dir=historical_execution_dir,
        output_dir=output_dir,
    )
    prefix = _build_prefix_audit(
        prepared=prepared,
        historical_execution_dir=historical_execution_dir,
    )
    with tempfile.TemporaryDirectory(prefix="v26_126_recovery_preflight_") as temporary:
        temporary_root = Path(temporary)
        scripted_root = temporary_root / "scripted"
        scripted, scripted_raws = _build_scripted_recovery_audit(
            prepared=prepared,
            historical_execution_dir=historical_execution_dir,
            root=scripted_root,
        )
        controls = _build_control_audit(
            prepared=prepared,
            historical_execution_dir=historical_execution_dir,
            root=temporary_root / "controls",
        )
        destructive = _build_destructive_audit(
            prepared=prepared,
            scripted_raws=scripted_raws,
            scripted_root=scripted_root,
        )
    transition_values = {
        "recovery_contract_id": prepared.recovery_contract.contract_id,
        "recovery_manifest_id": prepared.recovery_manifest.manifest_id,
        "recovery_runner_contract_id": prepared.runner_contract.runner_contract_id,
        "prefix_replay_audit_id": prefix.audit_id,
        "scripted_recovery_audit_id": scripted.audit_id,
        "recovery_control_audit_id": controls.audit_id,
        "destructive_audit_id": destructive.audit_id,
    }
    provisional_transition = ProspectiveTransitionContract.model_construct(
        contract_id="pending", **transition_values
    )
    transition = ProspectiveTransitionContract(
        contract_id=_identity(
            provisional_transition,
            "contract_id",
            "finance_v26_transport_recovery_runner_transition:",
        ),
        **transition_values,
    )
    outputs: tuple[tuple[str, BaseModel], ...] = (
        ("source_replay_audit.json", prepared.source_replay),
        ("recovery_contract.json", prepared.recovery_contract),
        ("recovery_job_manifest.json", prepared.recovery_manifest),
        ("recovery_runner_contract.json", prepared.runner_contract),
        ("prefix_replay_audit.json", prefix),
        ("scripted_recovery_audit.json", scripted),
        ("recovery_control_audit.json", controls),
        ("destructive_audit.json", destructive),
        ("prospective_transition_contract.json", transition),
    )
    for name, value in outputs:
        _write_json_atomic(output_dir / name, value.model_dump(mode="json"))
    details = tuple(_detail(output_dir / name, output_dir) for name, _ in outputs)
    report_values = {
        "source_replay_audit_id": prepared.source_replay.audit_id,
        "recovery_contract_id": prepared.recovery_contract.contract_id,
        "recovery_manifest_id": prepared.recovery_manifest.manifest_id,
        "recovery_runner_contract_id": prepared.runner_contract.runner_contract_id,
        "prefix_replay_audit_id": prefix.audit_id,
        "scripted_recovery_audit_id": scripted.audit_id,
        "recovery_control_audit_id": controls.audit_id,
        "destructive_audit_id": destructive.audit_id,
        "transition_contract_id": transition.contract_id,
        "detail_files": details,
        "scripted_provider_calls": sum(
            item.successor_scripted_call_count for item in scripted.rows
        ),
    }
    provisional_report = RecoveryPreflightReport.model_construct(
        report_id="pending", **report_values
    )
    report = RecoveryPreflightReport(
        report_id=_identity(
            provisional_report,
            "report_id",
            "finance_v26_transport_recovery_preflight_report:",
        ),
        **report_values,
    )
    _write_json_atomic(output_dir / "report.json", report.model_dump(mode="json"))
    return report


def main() -> None:
    package_default = Path(__file__).resolve().parents[4]
    parser = argparse.ArgumentParser(
        description="Credential-free v26.126 exact failed-call Transport Recovery preflight"
    )
    parser.add_argument("--package-root", type=Path, default=package_default)
    parser.add_argument("--implementation-root", type=Path, default=package_default)
    parser.add_argument(
        "--historical-audit-dir",
        type=Path,
        default=package_default / HISTORICAL_AUDIT_DIR,
    )
    parser.add_argument(
        "--historical-execution-dir",
        type=Path,
        default=package_default / HISTORICAL_EXECUTION_DIR,
    )
    parser.add_argument("--output-dir", type=Path, default=package_default / OUTPUT_DIR)
    args = parser.parse_args()
    report = build_preflight(
        package_root=args.package_root,
        implementation_root=args.implementation_root,
        historical_audit_dir=args.historical_audit_dir,
        historical_execution_dir=args.historical_execution_dir,
        output_dir=args.output_dir,
    )
    print(report.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
