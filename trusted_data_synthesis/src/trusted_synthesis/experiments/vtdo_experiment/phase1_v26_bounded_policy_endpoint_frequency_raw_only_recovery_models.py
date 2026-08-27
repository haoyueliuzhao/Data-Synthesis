from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Final, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.canonical_json import strict_canonical_hash
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_bounded_policy_endpoint_frequency_execution as execution,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_bounded_policy_endpoint_frequency_execution_models as execution_models,
)
from trusted_synthesis.runtime.agent.prospective_bounded_policy_endpoint_runner import (
    BoundedPolicyEndpointRecord,
)

FAILED_EXECUTION_DIR: Final = execution_models.OUTPUT_DIR
OUTPUT_DIR: Final = (
    "artifacts/vtdo_experiment/"
    "finance_v26_164_bounded_policy_endpoint_frequency_raw_only_recovery_v3_20260828"
)
MODEL_IMPLEMENTATION_PATH: Final = (
    "src/trusted_synthesis/experiments/vtdo_experiment/"
    "phase1_v26_bounded_policy_endpoint_frequency_raw_only_recovery_models.py"
)
RUNNER_IMPLEMENTATION_PATH: Final = (
    "src/trusted_synthesis/experiments/vtdo_experiment/"
    "phase1_v26_bounded_policy_endpoint_frequency_raw_only_recovery.py"
)
NEXT_STAGE: Final = execution_models.NEXT_STAGE


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", arbitrary_types_allowed=True)


def identity(value: BaseModel, field: str, prefix: str) -> str:
    return strict_canonical_hash(value.model_dump(mode="python", exclude={field}), prefix=prefix)


def json_payload(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, Mapping):
        return {str(key): json_payload(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_payload(item) for item in value]
    return value


def canonical_bytes(value: Any) -> bytes:
    return (
        json.dumps(
            json_payload(value),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class RecoveryImplementationFileBinding(FrozenModel):
    relative_path: str = Field(min_length=1)
    sha256: str = Field(min_length=64, max_length=64)
    byte_count: int = Field(gt=0)


class FailedExecutionFreezeAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    failed_execution_run_id: str = execution_models.RUN_ID
    failed_execution_directory_name: str = Field(min_length=1)
    failed_source_replay_audit_id: str = Field(min_length=1)
    failed_preexecution_binding_audit_id: str = Field(min_length=1)
    preflight_report_id: str = execution_models.EXPECTED_PREFLIGHT_REPORT_ID
    manifest_id: str = execution_models.EXPECTED_MANIFEST_ID
    runner_contract_id: str = execution_models.EXPECTED_RUNNER_CONTRACT_ID
    generation_policy_id: str = execution_models.EXPECTED_POLICY_ID
    failed_execution_file_count: int = Field(gt=0)
    failed_execution_byte_count: int = Field(gt=0)
    failed_execution_content_root: str = Field(min_length=1)
    failed_execution_unchanged_after_recovery: Literal[True] = True
    complete_raw_count: Literal[360] = 360
    direct_checkpoint_count: Literal[358] = 358
    typed_semantic_rejection_count: Literal[2] = 2
    missing_checkpoint_job_ids: tuple[str, ...] = Field(min_length=2, max_length=2)
    typed_semantic_rejection_job_ids: tuple[str, ...] = Field(min_length=2, max_length=2)
    provider_call_count: int = Field(ge=0, le=8280)
    transport_invocation_count: int = Field(ge=0, le=8640)
    provider_artifact_triple_count: int = Field(ge=0)
    provider_total_tokens: int = Field(ge=0)
    raw_instrument_failure_count: Literal[0] = 0
    privacy_failure_count: Literal[0] = 0
    stage_two_provider_call_count: Literal[0] = 0
    implementation_files: tuple[RecoveryImplementationFileBinding, ...] = Field(
        min_length=2,
        max_length=2,
    )
    implementation_bundle_sha256: str = Field(min_length=64, max_length=64)
    credential_lookup_attempted: Literal[False] = False
    model_client_constructed: Literal[False] = False
    recovery_provider_calls: Literal[0] = 0

    @model_validator(mode="after")
    def validate_audit(self) -> FailedExecutionFreezeAudit:
        expected_bundle = hashlib.sha256(
            canonical_bytes(
                tuple(item.model_dump(mode="python") for item in self.implementation_files)
            )
        ).hexdigest()
        if (
            self.missing_checkpoint_job_ids != tuple(sorted(set(self.missing_checkpoint_job_ids)))
            or self.typed_semantic_rejection_job_ids != self.missing_checkpoint_job_ids
            or tuple(item.relative_path for item in self.implementation_files)
            != tuple(sorted({item.relative_path for item in self.implementation_files}))
            or self.provider_artifact_triple_count != self.provider_call_count * 3
            or self.implementation_bundle_sha256 != expected_bundle
            or self.audit_id
            != identity(
                self,
                "audit_id",
                "finance_v26_bounded_policy_failed_execution_freeze:",
            )
        ):
            raise ValueError("v26.164 failed execution Freeze changed")
        return self


class RawOnlyRecoveredMeasurementResult(FrozenModel):
    result_id: str = Field(min_length=1)
    experiment_id: str = execution_models.EXPECTED_PROSPECTIVE_EXECUTION_ID
    job_id: str = Field(min_length=1)
    task_condition_cell_id: str = Field(min_length=1)
    task_package_id: str = Field(min_length=1)
    experimental_condition_id: str = Field(min_length=1)
    generation_policy_id: str = execution_models.EXPECTED_POLICY_ID
    legacy_joint_measurement_projection: execution.execution_base.ReachabilityMeasurementResult
    bounded_policy_endpoint_record: BoundedPolicyEndpointRecord
    raw_only_recovery: Literal[True] = True
    typed_semantic_rejection_validity_normalized: bool
    direct_checkpoint_byte_match: bool
    provider_calls_during_recovery: Literal[0] = 0

    @model_validator(mode="after")
    def validate_result(self) -> RawOnlyRecoveredMeasurementResult:
        legacy = self.legacy_joint_measurement_projection
        endpoint = self.bounded_policy_endpoint_record.projection
        if (
            self.job_id != legacy.job_id
            or self.task_package_id != legacy.task_package_id
            or self.bounded_policy_endpoint_record.raw_execution_id != legacy.raw_execution_id
            or endpoint.generation_policy_id != self.generation_policy_id
        ):
            raise ValueError("v26.164 Raw-only result crossed frozen parents")
        if self.typed_semantic_rejection_validity_normalized:
            if (
                legacy.raw_terminal_disposition != "typed_semantic_rejection"
                or legacy.base_trajectory_validity is not None
                or legacy.mechanism_qualification is not None
                or legacy.qualified_trajectory_validity is not None
                or not endpoint.model_terminal_observed
                or endpoint.terminal_class != "model_typed_rejection"
                or endpoint.task_completion is not False
                or endpoint.base_validity is not False
                or endpoint.mechanism_qualification is not False
                or endpoint.qualified_validity is not False
                or endpoint.state_mapping_eligible
                or endpoint.task_verifier_invocation_count
                or self.direct_checkpoint_byte_match
            ):
                raise ValueError("v26.164 typed semantic rejection normalization changed")
        else:
            exact_validity_required = (
                endpoint.policy_horizon_status == "within_horizon" and endpoint.validity_evaluable
            )
            if not self.direct_checkpoint_byte_match or (
                exact_validity_required
                and (
                    endpoint.model_terminal_observed != legacy.model_endpoint_observed
                    or endpoint.base_validity != legacy.base_trajectory_validity
                    or endpoint.mechanism_qualification != legacy.mechanism_qualification
                    or endpoint.qualified_validity != legacy.qualified_trajectory_validity
                )
            ):
                raise ValueError("v26.164 direct Raw-only projection changed")
        if self.result_id != identity(
            self,
            "result_id",
            "finance_v26_bounded_policy_raw_only_measurement_result:",
        ):
            raise ValueError("v26.164 Raw-only result identity changed")
        return self


class TypedSemanticRejectionNormalizationRow(FrozenModel):
    job_id: str = Field(min_length=1)
    raw_execution_id: str = Field(min_length=1)
    terminal_failure_type: Literal["semantic_recovery_exhausted"]
    stage_one_provider_call_count: int = Field(ge=0, le=23)
    transport_invocation_count: int = Field(ge=0, le=24)
    provider_total_tokens: int = Field(ge=0, le=1_120_000)
    raw_measurement_support_available: Literal[True] = True
    raw_instrument_integrity: Literal[True] = True
    raw_privacy_compliant: Literal[True] = True
    before_task_completion: None = None
    before_base_validity: None = None
    before_mechanism_qualification: None = None
    before_qualified_validity: None = None
    after_task_completion: Literal[False] = False
    after_base_validity: Literal[False] = False
    after_mechanism_qualification: Literal[False] = False
    after_qualified_validity: Literal[False] = False
    after_state_mapping_eligible: Literal[False] = False
    task_verifier_invocation_count: Literal[0] = 0
    provider_calls_during_normalization: Literal[0] = 0


class TypedSemanticRejectionNormalizationAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    rows: tuple[TypedSemanticRejectionNormalizationRow, ...] = Field(
        min_length=2,
        max_length=2,
    )
    row_count: Literal[2] = 2
    before_null_validity_count: Literal[2] = 2
    after_explicit_failure_validity_count: Literal[2] = 2
    model_terminal_count: Literal[2] = 2
    bounded_policy_endpoint_count: Literal[2] = 2
    state_mapping_attempt_count: Literal[0] = 0
    historical_reclassification_count: Literal[0] = 0
    provider_calls: Literal[0] = 0

    @model_validator(mode="after")
    def validate_audit(self) -> TypedSemanticRejectionNormalizationAudit:
        if tuple(item.job_id for item in self.rows) != tuple(
            sorted({item.job_id for item in self.rows})
        ) or self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_bounded_policy_typed_rejection_normalization:",
        ):
            raise ValueError("v26.164 typed rejection audit changed")
        return self


class DetailFile(FrozenModel):
    relative_path: str = Field(min_length=1)
    sha256: str = Field(min_length=64, max_length=64)
    byte_count: int = Field(gt=0)


class RawOnlyRecoveryReport(FrozenModel):
    report_id: str = Field(min_length=1)
    failed_execution_freeze_audit_id: str = Field(min_length=1)
    typed_semantic_rejection_normalization_audit_id: str = Field(min_length=1)
    recovered_execution_report_id: str = Field(min_length=1)
    global_integrity_gate_id: str = Field(min_length=1)
    endpoint_catalog_id: str = Field(min_length=1)
    horizon_reason_audit_id: str = Field(min_length=1)
    raw_lineage_audit_id: str = Field(min_length=1)
    mapper_execution_audit_id: str = Field(min_length=1)
    assignment_catalog_id: str = Field(min_length=1)
    cell_frequency_catalog_id: str = Field(min_length=1)
    postrun_transition_contract_id: str = Field(min_length=1)
    complete_raw_count: Literal[360] = 360
    recovered_measurement_result_count: Literal[360] = 360
    direct_checkpoint_byte_match_count: Literal[358] = 358
    typed_semantic_rejection_normalized_count: Literal[2] = 2
    bounded_policy_endpoint_count: Literal[360] = 360
    policy_horizon_endpoint_count: int = Field(ge=0, le=360)
    formal_assignment_count: int = Field(ge=0, le=360)
    structural_state_count: int = Field(ge=0, le=360)
    q_instantiated_cell_count: Literal[48] = 48
    pi_instantiated_cell_count: int = Field(ge=0, le=48)
    zero_qualified_cell_count: int = Field(ge=0, le=48)
    empirical_non_degenerate_cell_count: int = Field(ge=0, le=48)
    global_integrity_gate_passed: Literal[True] = True
    failed_execution_directory_immutable: Literal[True] = True
    credential_lookup_attempted: Literal[False] = False
    model_client_constructed: Literal[False] = False
    provider_calls: Literal[0] = 0
    stage_two_provider_calls: Literal[0] = 0
    historical_reclassification_count: Literal[0] = 0
    row_deletion_count: Literal[0] = 0
    bounded_policy_finite_sample_empirical_frequency_only: Literal[True] = True
    unrestricted_natural_agent_distribution_claimed: Literal[False] = False
    state_probability_or_vtdo_claimed: Literal[False] = False
    independent_postrun_audit_required: Literal[True] = True
    detail_files: tuple[DetailFile, ...]
    next_permitted_stage: Literal["fresh_bounded_policy_endpoint_frequency_postrun_audit_only"] = (
        NEXT_STAGE
    )
    status: Literal[
        "raw_only_recovery_complete_global_gate_passed_pending_independent_postrun_audit"
    ] = "raw_only_recovery_complete_global_gate_passed_pending_independent_postrun_audit"

    @model_validator(mode="after")
    def validate_report(self) -> RawOnlyRecoveryReport:
        names = tuple(item.relative_path for item in self.detail_files)
        if names != tuple(sorted(set(names))) or self.report_id != identity(
            self,
            "report_id",
            "finance_v26_bounded_policy_raw_only_recovery_report:",
        ):
            raise ValueError("v26.164 Raw-only recovery report changed")
        return self
