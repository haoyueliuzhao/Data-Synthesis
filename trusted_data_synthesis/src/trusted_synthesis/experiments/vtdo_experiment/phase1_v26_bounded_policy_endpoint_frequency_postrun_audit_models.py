from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Final, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.canonical_json import strict_canonical_hash
from trusted_synthesis.core.evaluation.bounded_policy_endpoint import (
    BoundedPolicyCellFrequencyReport,
    BoundedPolicyEndpointProjection,
    BoundedPolicyGlobalIntegrityGate,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_bounded_policy_endpoint_frequency_raw_only_recovery_models as recovery_models,
)

FAILED_EXECUTION_DIR: Final = recovery_models.FAILED_EXECUTION_DIR
RECOVERY_DIR: Final = recovery_models.OUTPUT_DIR
OUTPUT_DIR: Final = (
    "artifacts/vtdo_experiment/"
    "finance_v26_165_bounded_policy_endpoint_frequency_postrun_audit_v2_20260828"
)
IMPLEMENTATION_PATH: Final = (
    "src/trusted_synthesis/experiments/vtdo_experiment/"
    "phase1_v26_bounded_policy_endpoint_frequency_postrun_audit.py"
)
MODEL_IMPLEMENTATION_PATH: Final = (
    "src/trusted_synthesis/experiments/vtdo_experiment/"
    "phase1_v26_bounded_policy_endpoint_frequency_postrun_audit_models.py"
)
FINAL_DECISION: Final = "no_further_experiment_authorized_without_new_audit_decision"


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
    import hashlib

    return hashlib.sha256(path.read_bytes()).hexdigest()


class SourceBinding(FrozenModel):
    relative_path: str = Field(min_length=1)
    sha256: str = Field(min_length=64, max_length=64)
    byte_count: int = Field(gt=0)


class PostrunSourceReplayAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    failed_execution_file_count: Literal[9143] = 9_143
    failed_execution_byte_count: Literal[64601865] = 64_601_865
    failed_execution_content_root: str = Field(min_length=1)
    recovery_file_count: Literal[13] = 13
    recovery_byte_count: int = Field(gt=0)
    recovery_content_root: str = Field(min_length=1)
    implementation_files: tuple[SourceBinding, ...] = Field(min_length=6, max_length=6)
    complete_raw_count: Literal[360] = 360
    provider_artifact_triple_count: Literal[2919] = 2_919
    direct_checkpoint_count: Literal[358] = 358
    typed_semantic_rejection_count: Literal[2] = 2
    credential_lookup_attempted: Literal[False] = False
    model_client_constructed: Literal[False] = False
    provider_calls: Literal[0] = 0

    @model_validator(mode="after")
    def validate_audit(self) -> PostrunSourceReplayAudit:
        paths = tuple(item.relative_path for item in self.implementation_files)
        if paths != tuple(sorted(set(paths))) or self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_bounded_policy_postrun_source_replay:",
        ):
            raise ValueError("v26.165 source replay changed")
        return self


class IndependentEndpointRow(FrozenModel):
    row_id: str = Field(min_length=1)
    job_id: str = Field(min_length=1)
    raw_execution_id: str = Field(min_length=1)
    task_condition_cell_id: str = Field(min_length=1)
    task_package_id: str = Field(min_length=1)
    mechanism_id: str = Field(min_length=1)
    tier: str = Field(min_length=1)
    sampling_mode: str = Field(min_length=1)
    raw_terminal_disposition: str = Field(min_length=1)
    terminal_failure_type: str | None
    endpoint: BoundedPolicyEndpointProjection
    independent_verifier_invocation_count: int = Field(ge=0, le=1)
    production_endpoint_exact_match: Literal[True] = True
    recovery_result_exact_parent_match: Literal[True] = True

    @model_validator(mode="after")
    def validate_row(self) -> IndependentEndpointRow:
        if self.endpoint.trajectory_id != self.raw_execution_id or self.row_id != identity(
            self,
            "row_id",
            "finance_v26_bounded_policy_independent_endpoint_row:",
        ):
            raise ValueError("v26.165 independent endpoint row changed")
        return self


class IndependentEndpointCatalog(FrozenModel):
    catalog_id: str = Field(min_length=1)
    rows: tuple[IndependentEndpointRow, ...] = Field(min_length=360, max_length=360)
    row_count: Literal[360] = 360
    bounded_policy_endpoint_count: Literal[360] = 360
    model_terminal_count: Literal[359] = 359
    policy_horizon_endpoint_count: Literal[1] = 1
    validity_evaluable_count: Literal[360] = 360
    base_valid_count: Literal[106] = 106
    mechanism_qualified_count: Literal[226] = 226
    qualified_valid_count: Literal[106] = 106
    terminal_class_counts: dict[str, int]
    raw_terminal_counts: dict[str, int]
    policy_horizon_reason_counts: dict[str, int]
    endpoint_exact_match_count: Literal[360] = 360

    @model_validator(mode="after")
    def validate_catalog(self) -> IndependentEndpointCatalog:
        ids = tuple(item.row_id for item in self.rows)
        if (
            ids != tuple(sorted(set(ids)))
            or sum(self.terminal_class_counts.values()) != 360
            or sum(self.raw_terminal_counts.values()) != 360
            or sum(self.policy_horizon_reason_counts.values()) != 1
            or self.catalog_id
            != identity(
                self,
                "catalog_id",
                "finance_v26_bounded_policy_independent_endpoint_catalog:",
            )
        ):
            raise ValueError("v26.165 independent endpoint Catalog changed")
        return self


class IndependentProviderArtifactAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    provider_call_count: Literal[2919] = 2_919
    provider_envelope_count: Literal[2919] = 2_919
    public_projection_count: Literal[2919] = 2_919
    transport_certificate_count: Literal[2919] = 2_919
    complete_artifact_triple_count: Literal[2919] = 2_919
    exact_model_failure_count: Literal[0] = 0
    thinking_failure_count: Literal[0] = 0
    usage_failure_count: Literal[0] = 0
    privacy_failure_count: Literal[0] = 0
    unresolved_transport_failure_count: Literal[0] = 0
    stage_two_provider_call_count: Literal[0] = 0
    provider_prompt_tokens: Literal[15302382] = 15_302_382
    provider_completion_tokens: Literal[13237351] = 13_237_351
    provider_reasoning_tokens: Literal[12793715] = 12_793_715
    provider_total_tokens: Literal[28539733] = 28_539_733

    @model_validator(mode="after")
    def validate_audit(self) -> IndependentProviderArtifactAudit:
        if self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_bounded_policy_independent_provider_artifacts:",
        ):
            raise ValueError("v26.165 Provider artifact audit changed")
        return self


class IndependentGateAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    gate: BoundedPolicyGlobalIntegrityGate
    production_gate_id: str = Field(min_length=1)
    exact_gate_match: Literal[True] = True
    failure_ids: tuple[str, ...] = ()
    passed: Literal[True] = True

    @model_validator(mode="after")
    def validate_audit(self) -> IndependentGateAudit:
        if (
            not self.gate.passed
            or self.gate.gate_id != self.production_gate_id
            or self.gate.failure_ids
            or self.audit_id
            != identity(
                self,
                "audit_id",
                "finance_v26_bounded_policy_independent_gate_audit:",
            )
        ):
            raise ValueError("v26.165 independent Gate changed")
        return self


class IndependentMapperAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    qualified_row_count: Literal[106] = 106
    production_mapper_invocation_count: Literal[106] = 106
    reference_mapper_invocation_count: Literal[106] = 106
    production_reference_exact_state_match_count: Literal[106] = 106
    recovered_assignment_exact_match_count: Literal[106] = 106
    formal_assignment_count: Literal[106] = 106
    structural_state_count: Literal[53] = 53
    empirical_route_signature_count: Literal[57] = 57
    mapper_invocation_before_global_gate_count: Literal[0] = 0
    policy_horizon_mapping_attempt_count: Literal[0] = 0
    typed_semantic_rejection_mapping_attempt_count: Literal[0] = 0
    provider_calls: Literal[0] = 0

    @model_validator(mode="after")
    def validate_audit(self) -> IndependentMapperAudit:
        if self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_bounded_policy_independent_mapper_audit:",
        ):
            raise ValueError("v26.165 independent Mapper audit changed")
        return self


class IndependentCellFrequencyAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    reports: tuple[BoundedPolicyCellFrequencyReport, ...] = Field(
        min_length=48,
        max_length=48,
    )
    cell_count: Literal[48] = 48
    exact_report_match_count: Literal[48] = 48
    n_total_sum: Literal[360] = 360
    n_policy_endpoint_sum: Literal[360] = 360
    n_qualified_sum: Literal[106] = 106
    q_instantiated_cell_count: Literal[48] = 48
    pi_instantiated_cell_count: Literal[38] = 38
    zero_qualified_cell_count: Literal[10] = 10
    empirical_non_degenerate_cell_count: Literal[27] = 27
    unconditional_cell_count: Literal[12] = 12
    conditioned_cell_count: Literal[36] = 36
    route_used_as_statistics_key_count: Literal[0] = 0
    imputed_zero_state_vector_count: Literal[0] = 0
    simultaneous_multinomial_coverage_claim_count: Literal[0] = 0

    @model_validator(mode="after")
    def validate_audit(self) -> IndependentCellFrequencyAudit:
        ids = tuple(item.report_id for item in self.reports)
        if (
            ids != tuple(sorted(set(ids)))
            or sum(item.n_total for item in self.reports) != 360
            or sum(item.n_policy_endpoints for item in self.reports) != 360
            or sum(item.n_qualified for item in self.reports) != 106
            or self.audit_id
            != identity(
                self,
                "audit_id",
                "finance_v26_bounded_policy_independent_cell_frequency_audit:",
            )
        ):
            raise ValueError("v26.165 independent Cell audit changed")
        return self


class RecoveryBoundaryAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    failed_execution_file_count: Literal[9143] = 9_143
    failed_execution_unchanged: Literal[True] = True
    direct_checkpoint_byte_match_count: Literal[358] = 358
    typed_semantic_rejection_count: Literal[2] = 2
    typed_semantic_rejection_null_to_false_count: Literal[2] = 2
    typed_semantic_rejection_model_terminal_count: Literal[2] = 2
    typed_semantic_rejection_mapping_attempt_count: Literal[0] = 0
    policy_horizon_endpoint_count: Literal[1] = 1
    policy_horizon_later_provider_call_count: Literal[0] = 0
    row_deletion_count: Literal[0] = 0
    historical_reclassification_count: Literal[0] = 0
    recovery_provider_calls: Literal[0] = 0

    @model_validator(mode="after")
    def validate_audit(self) -> RecoveryBoundaryAudit:
        if self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_bounded_policy_recovery_boundary_audit:",
        ):
            raise ValueError("v26.165 recovery boundary audit changed")
        return self


class DetailFile(FrozenModel):
    relative_path: str = Field(min_length=1)
    sha256: str = Field(min_length=64, max_length=64)
    byte_count: int = Field(gt=0)


class PostrunAuditReport(FrozenModel):
    report_id: str = Field(min_length=1)
    source_replay_audit_id: str = Field(min_length=1)
    independent_endpoint_catalog_id: str = Field(min_length=1)
    independent_provider_artifact_audit_id: str = Field(min_length=1)
    independent_gate_audit_id: str = Field(min_length=1)
    independent_mapper_audit_id: str = Field(min_length=1)
    independent_cell_frequency_audit_id: str = Field(min_length=1)
    recovery_boundary_audit_id: str = Field(min_length=1)
    recovered_execution_report_id: str = Field(min_length=1)
    recovered_execution_report_exact_match: Literal[True] = True
    complete_raw_count: Literal[360] = 360
    bounded_policy_endpoint_count: Literal[360] = 360
    global_integrity_gate_passed: Literal[True] = True
    qualified_valid_count: Literal[106] = 106
    formal_assignment_count: Literal[106] = 106
    structural_state_count: Literal[53] = 53
    q_instantiated_cell_count: Literal[48] = 48
    pi_instantiated_cell_count: Literal[38] = 38
    zero_qualified_cell_count: Literal[10] = 10
    empirical_non_degenerate_cell_count: Literal[27] = 27
    credential_lookup_attempted: Literal[False] = False
    model_client_constructed: Literal[False] = False
    provider_calls: Literal[0] = 0
    bounded_policy_finite_sample_empirical_frequency_only: Literal[True] = True
    unrestricted_natural_agent_distribution_claimed: Literal[False] = False
    cross_task_state_probability_claimed: Literal[False] = False
    path_causal_effect_claimed: Literal[False] = False
    simultaneous_multinomial_coverage_claimed: Literal[False] = False
    vtdo_authorized: Literal[False] = False
    training_release_or_production_authorized: Literal[False] = False
    detail_files: tuple[DetailFile, ...]
    final_decision: Literal["no_further_experiment_authorized_without_new_audit_decision"] = (
        FINAL_DECISION
    )
    status: Literal[
        "bounded_policy_frequency_independently_confirmed_no_further_experiment_authorized"
    ] = "bounded_policy_frequency_independently_confirmed_no_further_experiment_authorized"

    @model_validator(mode="after")
    def validate_report(self) -> PostrunAuditReport:
        names = tuple(item.relative_path for item in self.detail_files)
        if names != tuple(sorted(set(names))) or self.report_id != identity(
            self,
            "report_id",
            "finance_v26_bounded_policy_postrun_audit_report:",
        ):
            raise ValueError("v26.165 postrun audit report changed")
        return self
