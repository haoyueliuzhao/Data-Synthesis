from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any, Final, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.canonical_json import strict_canonical_hash
from trusted_synthesis.core.trajectory.reachability_frequency_v2 import (
    ReachabilityFrequencyAssignmentV2,
    TaskConditionCellCatalogV2,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_reachability_execution as execution_base,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_mapper_v2_reachability_frequency_preflight as preflight,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_mapper_v2_frequency_preflight_models import (  # noqa: E501
    FrequencyAssignmentContract,
    FrequencyEstimandContract,
    FrequencyExecutionContract,
    FrequencyManifest,
    FrequencyOutcomeContract,
    FrequencyPreflightReport,
    FrequencyRunnerContract,
    FreshFrequencySourcePopulation,
    MapperV2FrequencyProtocol,
    OmegaTaskContextCatalogV2,
    ProspectiveTransitionContract,
    ReproducibilityRootAudit,
    SourceSelectionAudit,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_two_stage_semantic_proposal_execution import (  # noqa: E501
    RawFileDescriptor,
)
from trusted_synthesis.runtime.agent.prospective_qualified_final_response_grammar import (
    QualifiedFinalResponseGrammar,
)

RUN_ID: Final = preflight.PROSPECTIVE_EXECUTION_RUN_ID
REPORT_RUN_ID: Final = preflight.PROSPECTIVE_REPORT_RUN_ID
PREFLIGHT_DIR: Final = preflight.OUTPUT_DIR
OUTPUT_DIR: Final = (
    "artifacts/vtdo_experiment/"
    "finance_v26_161_mapper_v2_reachability_frequency_execution_authoritative_v2_20260827"
)
IMPLEMENTATION_PATH: Final = (
    "src/trusted_synthesis/experiments/vtdo_experiment/"
    "phase1_v26_mapper_v2_reachability_frequency_execution.py"
)
NEXT_STAGE: Final = "fresh_mapper_v2_reachability_frequency_postrun_audit_only"

EXPECTED_PREFLIGHT_REPORT_ID: Final = (
    "finance_v26_frequency_preflight_report:"
    "014007ba585d6315ee68dc001a13381b7c742e1468ba4b66a58ef3b938fb5b69"
)
EXPECTED_PREFLIGHT_REPORT_SHA256: Final = (
    "4fb13daa6244af4c9257f58e508a8dde45392ce0574a809eccdb0d74350b5153"
)
EXPECTED_REPRODUCIBILITY_ROOT_ID: Final = (
    "finance_v26_frequency_reproducibility_root:"
    "b5987b716c0019a0a8cc706ecb39d232fdfb1ce400b3c07cdc34d39a35c4a069"
)
EXPECTED_SOURCE_POPULATION_ID: Final = (
    "finance_v26_frequency_source_population:"
    "fe954fe355847ef429aa50603fea12f4bba53af59e4d875e8051e76c94dcc301"
)
EXPECTED_SOURCE_SELECTION_ID: Final = (
    "finance_v26_frequency_source_selection:"
    "23bbbb76584f1ea48f9acb95c0536ea0dfeee37993a7dbf6015c2ad466695da4"
)
EXPECTED_CELL_CATALOG_ID: Final = (
    "mapper_v2_task_condition_cell_catalog:"
    "4a734a3ace027c43a711d00b646a4155e7ba6b04d6f6ab5a18cb8b9931875740"
)
EXPECTED_ASSIGNMENT_CONTRACT_ID: Final = (
    "finance_v26_frequency_assignment_contract:"
    "5156e9e92addda1482f53e4f8fdedcb3c9857f6dd1796354b70a0e4b40d8ceb7"
)
EXPECTED_MAPPER_PROTOCOL_ID: Final = (
    "finance_v26_mapper_v2_frequency_protocol:"
    "fbfb314cfea3e693a34be778b62f7c3a510f4393a1638ae91c18794c328e5007"
)
EXPECTED_ESTIMAND_CONTRACT_ID: Final = (
    "finance_v26_frequency_estimand_contract:"
    "d434124bba9775355f2f16f61c2b432fdae051d751a21437809e7065ffc559c5"
)
EXPECTED_EXECUTION_CONTRACT_ID: Final = (
    "finance_v26_frequency_execution_contract:"
    "69e958c2118dc91891796a82a90e1c03b90a75c1d186609a3acb3d5dbfcd3149"
)
EXPECTED_MANIFEST_ID: Final = (
    "finance_v26_frequency_manifest:"
    "9cdd5be51f2e9dfd815d43f691987790b60ce5f435227409058bdbe00a69c3e4"
)
EXPECTED_OUTCOME_CONTRACT_ID: Final = (
    "finance_v26_frequency_outcome_contract:"
    "d02dfa25cdc1002f5c6a05e62be771cffa090082fb1d96a53b981122f1d4d1bd"
)
EXPECTED_RUNNER_CONTRACT_ID: Final = (
    "finance_v26_frequency_runner_contract:"
    "41f2eb1a60a78631df97e2ff2836712571e72a9bb42c9da76eec42fd54ecd64c"
)
EXPECTED_TRANSITION_ID: Final = (
    "finance_v26_frequency_transition:"
    "b71a815575a0ddd247098e300037709451fe3aa2a72abe492b2230e5855c81b2"
)
EXPECTED_PROSPECTIVE_EXECUTION_ID: Final = (
    "finance_v26_mapper_v2_frequency_execution:"
    "e87a7ae3fe9d9d0ade030fbb270b3ca7219fff27a94e8ffc814099ec93e95d22"
)
EXPECTED_PROSPECTIVE_REPORT_ID: Final = (
    "finance_v26_mapper_v2_frequency_execution_report:"
    "1e3ce9c7bd7b2e06a884217ff8d0a126a5341fc1911b933e6a9b2f9d2bfe244b"
)


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", arbitrary_types_allowed=True)


def _identity(value: BaseModel, field: str, prefix: str) -> str:
    return strict_canonical_hash(value.model_dump(mode="python", exclude={field}), prefix=prefix)


def _json_payload(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, Mapping):
        return {str(key): _json_payload(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_payload(item) for item in value]
    return value


def _canonical_bytes(value: Any) -> bytes:
    return (
        json.dumps(
            _json_payload(value),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")


def _write_json_atomic(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = _canonical_bytes(value)
    if path.exists() and path.read_bytes() == payload:
        return
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(payload)
    temporary.replace(path)


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _descriptor(path: Path, output_dir: Path) -> RawFileDescriptor:
    return RawFileDescriptor(
        relative_path=str(path.resolve().relative_to(output_dir.resolve())),
        sha256=_sha256(path),
        byte_count=path.stat().st_size,
    )


class ImplementationFileBinding(FrozenModel):
    relative_path: str = Field(min_length=1)
    sha256: str = Field(min_length=64, max_length=64)
    byte_count: int = Field(gt=0)


class ExecutionSourceReplayAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    preflight_report_id: str = EXPECTED_PREFLIGHT_REPORT_ID
    preflight_report_sha256: str = EXPECTED_PREFLIGHT_REPORT_SHA256
    reproducibility_root_audit_id: str = EXPECTED_REPRODUCIBILITY_ROOT_ID
    current_stage_input_binding_count: Literal[35] = 35
    current_stage_input_byte_match_count: Literal[35] = 35
    preflight_output_count: Literal[33] = 33
    preflight_output_byte_match_count: Literal[33] = 33
    independent_rebuild_output_count: Literal[33] = 33
    independent_rebuild_byte_match_count: Literal[33] = 33
    v26_158_full_transitive_rebuild_claimed: Literal[False] = False
    missing_historical_snapshot_preserved: Literal[True] = True
    implementation_path: str = IMPLEMENTATION_PATH
    implementation_sha256: str = Field(min_length=64, max_length=64)
    implementation_files: tuple[ImplementationFileBinding, ...] = Field(min_length=2, max_length=2)
    implementation_bundle_sha256: str = Field(min_length=64, max_length=64)
    credential_lookup_attempted: Literal[False] = False
    provider_calls: Literal[0] = 0
    status: Literal["passed"] = "passed"

    @model_validator(mode="after")
    def validate_audit(self) -> ExecutionSourceReplayAudit:
        paths = tuple(item.relative_path for item in self.implementation_files)
        expected_bundle = hashlib.sha256(
            _canonical_bytes(
                tuple(item.model_dump(mode="python") for item in self.implementation_files)
            )
        ).hexdigest()
        if (
            paths != tuple(sorted(set(paths)))
            or self.implementation_bundle_sha256 != expected_bundle
            or self.implementation_path not in paths
            or self.implementation_sha256
            != next(
                item.sha256
                for item in self.implementation_files
                if item.relative_path == self.implementation_path
            )
            or self.audit_id
            != _identity(
                self,
                "audit_id",
                "finance_v26_mapper_v2_frequency_execution_source_replay:",
            )
        ):
            raise ValueError("v26.161 execution source replay changed")
        return self


class PreexecutionBindingAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    preflight_report_id: str = EXPECTED_PREFLIGHT_REPORT_ID
    transition_contract_id: str = EXPECTED_TRANSITION_ID
    execution_contract_id: str = EXPECTED_EXECUTION_CONTRACT_ID
    manifest_id: str = EXPECTED_MANIFEST_ID
    runner_contract_id: str = EXPECTED_RUNNER_CONTRACT_ID
    outcome_contract_id: str = EXPECTED_OUTCOME_CONTRACT_ID
    prospective_execution_id: str = EXPECTED_PROSPECTIVE_EXECUTION_ID
    exact_job_count: Literal[360] = 360
    distinct_task_count: Literal[12] = 12
    distinct_cell_count: Literal[48] = 48
    distinct_path_count: Literal[36] = 36
    unconditional_job_count: Literal[144] = 144
    conditioned_job_count: Literal[216] = 216
    unopened_raw_count: Literal[0] = 0
    unopened_provider_artifact_count: Literal[0] = 0
    unopened_checkpoint_row_count: Literal[0] = 0
    unopened_report_count: Literal[0] = 0
    formal_assignment_count: Literal[0] = 0
    credential_lookup_attempted: Literal[False] = False
    provider_calls: Literal[0] = 0
    passed: Literal[True] = True

    @model_validator(mode="after")
    def validate_audit(self) -> PreexecutionBindingAudit:
        if self.audit_id != _identity(
            self,
            "audit_id",
            "finance_v26_mapper_v2_frequency_preexecution_binding:",
        ):
            raise ValueError("v26.161 preexecution binding changed")
        return self


class FrequencyMeasurementResult(FrozenModel):
    result_id: str = Field(min_length=1)
    experiment_id: str = EXPECTED_PROSPECTIVE_EXECUTION_ID
    job_id: str = Field(min_length=1)
    task_condition_cell_id: str = Field(min_length=1)
    task_package_id: str = Field(min_length=1)
    experimental_condition_id: str = Field(min_length=1)
    generation_policy_id: str = Field(min_length=1)
    joint_measurement_projection: execution_base.ReachabilityMeasurementResult
    formal_mapper_invocation_before_complete_gate: Literal[False] = False

    @model_validator(mode="after")
    def validate_result(self) -> FrequencyMeasurementResult:
        projected = self.joint_measurement_projection
        if (
            self.job_id != projected.job_id
            or self.task_package_id != projected.task_package_id
            or self.result_id
            != _identity(
                self,
                "result_id",
                "finance_v26_mapper_v2_frequency_measurement_result:",
            )
        ):
            raise ValueError("v26.161 frequency Measurement result changed")
        return self


class FrequencyAssignmentCatalog(FrozenModel):
    catalog_id: str = Field(min_length=1)
    experiment_id: str = EXPECTED_PROSPECTIVE_EXECUTION_ID
    measurement_gate_id: str = Field(min_length=1)
    mapper_protocol_id: str = EXPECTED_MAPPER_PROTOCOL_ID
    assignment_contract_id: str = EXPECTED_ASSIGNMENT_CONTRACT_ID
    assignments: tuple[ReachabilityFrequencyAssignmentV2, ...]
    assignment_count: int = Field(ge=0, le=360)
    structural_state_count: int = Field(ge=0, le=360)
    empirical_route_signature_count: int = Field(ge=0, le=360)
    complete_measurement_gate_passed: bool
    failed_gate_created_zero_assignments: Literal[True] = True

    @model_validator(mode="after")
    def validate_catalog(self) -> FrequencyAssignmentCatalog:
        ids = tuple(item.assignment_id for item in self.assignments)
        if (
            ids != tuple(sorted(set(ids)))
            or self.assignment_count != len(self.assignments)
            or self.structural_state_count
            != len({item.structural_state_id for item in self.assignments})
            or self.empirical_route_signature_count
            != len({item.empirical_route_signature_id for item in self.assignments})
            or (not self.complete_measurement_gate_passed and self.assignments)
            or self.catalog_id
            != _identity(
                self,
                "catalog_id",
                "finance_v26_mapper_v2_frequency_assignment_catalog:",
            )
        ):
            raise ValueError("v26.161 Frequency Assignment Catalog changed")
        return self


class MapperExecutionAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    measurement_gate_id: str = Field(min_length=1)
    mapper_protocol_id: str = EXPECTED_MAPPER_PROTOCOL_ID
    qualified_row_count: int = Field(ge=0, le=360)
    production_mapper_invocation_count: int = Field(ge=0, le=360)
    reference_mapper_invocation_count: int = Field(ge=0, le=360)
    production_reference_exact_state_match_count: int = Field(ge=0, le=360)
    formal_assignment_count: int = Field(ge=0, le=360)
    complete_measurement_gate_passed: bool
    mapper_invocation_before_complete_gate_count: Literal[0] = 0
    mapper_v1_assignment_reuse_count: Literal[0] = 0
    diagnostic_assignment_promotion_count: Literal[0] = 0
    provider_calls: Literal[0] = 0

    @model_validator(mode="after")
    def validate_audit(self) -> MapperExecutionAudit:
        expected = self.qualified_row_count if self.complete_measurement_gate_passed else 0
        if (
            self.production_mapper_invocation_count != expected
            or self.reference_mapper_invocation_count != expected
            or self.production_reference_exact_state_match_count != expected
            or self.formal_assignment_count != expected
            or self.audit_id
            != _identity(
                self,
                "audit_id",
                "finance_v26_mapper_v2_frequency_mapper_execution:",
            )
        ):
            raise ValueError("v26.161 Mapper execution audit changed")
        return self


FrequencyDistributionStatus = Literal[
    "measurement_gate_failed",
    "no_qualified_rows",
    "bounded_policy_empirical_qualified_state_frequency",
]


class CellDenominatorDiagnostic(FrozenModel):
    diagnostic_id: str = Field(min_length=1)
    task_condition_cell_id: str = Field(min_length=1)
    task_package_id: str = Field(min_length=1)
    experimental_condition_id: str = Field(min_length=1)
    generation_policy_id: str = Field(min_length=1)
    sampling_mode: Literal["reachability_unconditional", "reachability_conditioned"]
    total_rollout_count: Literal[6, 12]
    validity_evaluable_count: int = Field(ge=0, le=12)
    qualified_rollout_count: int = Field(ge=0, le=12)
    formal_assignment_count: int = Field(ge=0, le=12)
    observed_formal_state_count: int = Field(ge=0, le=12)
    qualified_fraction_of_total: str
    distribution_status: FrequencyDistributionStatus
    descriptive_counts_are_not_cross_task_probability: Literal[True] = True
    independent_postrun_audit_required: Literal[True] = True

    @model_validator(mode="after")
    def validate_diagnostic(self) -> CellDenominatorDiagnostic:
        expected_fraction = format(
            Decimal(self.qualified_rollout_count) / Decimal(self.total_rollout_count),
            "f",
        )
        if (
            self.qualified_fraction_of_total != expected_fraction
            or self.formal_assignment_count > self.qualified_rollout_count
            or self.diagnostic_id
            != _identity(
                self,
                "diagnostic_id",
                "finance_v26_mapper_v2_frequency_cell_denominator:",
            )
        ):
            raise ValueError("v26.161 Cell denominator diagnostic changed")
        return self


class CellDenominatorCatalog(FrozenModel):
    catalog_id: str = Field(min_length=1)
    measurement_gate_id: str = Field(min_length=1)
    diagnostics: tuple[CellDenominatorDiagnostic, ...] = Field(min_length=48, max_length=48)
    cell_count: Literal[48] = 48
    total_rollout_count: Literal[360] = 360
    validity_evaluable_count: int = Field(ge=0, le=360)
    qualified_rollout_count: int = Field(ge=0, le=360)
    formal_assignment_count: int = Field(ge=0, le=360)

    @model_validator(mode="after")
    def validate_catalog(self) -> CellDenominatorCatalog:
        ids = tuple(item.diagnostic_id for item in self.diagnostics)
        if (
            ids != tuple(sorted(set(ids)))
            or self.total_rollout_count
            != sum(item.total_rollout_count for item in self.diagnostics)
            or self.validity_evaluable_count
            != sum(item.validity_evaluable_count for item in self.diagnostics)
            or self.qualified_rollout_count
            != sum(item.qualified_rollout_count for item in self.diagnostics)
            or self.formal_assignment_count
            != sum(item.formal_assignment_count for item in self.diagnostics)
            or self.catalog_id
            != _identity(
                self,
                "catalog_id",
                "finance_v26_mapper_v2_frequency_cell_denominator_catalog:",
            )
        ):
            raise ValueError("v26.161 Cell denominator Catalog changed")
        return self


class RawLineageAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    runner_contract_id: str = EXPECTED_RUNNER_CONTRACT_ID
    manifest_id: str = EXPECTED_MANIFEST_ID
    raw_execution_count: Literal[360] = 360
    measurement_result_count: Literal[360] = 360
    provider_call_count: int = Field(ge=0, le=8280)
    transport_invocation_count: int = Field(ge=0, le=8640)
    provider_envelope_count: int = Field(ge=0, le=8280)
    public_projection_count: int = Field(ge=0, le=8280)
    complete_provider_pair_count: int = Field(ge=0, le=8280)
    raw_descriptors: tuple[RawFileDescriptor, ...] = Field(min_length=360, max_length=360)
    provider_artifact_descriptors: tuple[RawFileDescriptor, ...]
    exact_byte_replay_pass_count: int = Field(ge=360)
    private_reasoning_payload_count: Literal[0] = 0
    invalid_payload_persistence_count: Literal[0] = 0
    raw_http_body_persistence_count: Literal[0] = 0
    raw_request_body_persistence_count: Literal[0] = 0
    stage_two_provider_call_count: Literal[0] = 0

    @model_validator(mode="after")
    def validate_audit(self) -> RawLineageAudit:
        if (
            self.provider_call_count != self.provider_envelope_count
            or self.provider_call_count != self.public_projection_count
            or self.provider_call_count != self.complete_provider_pair_count
            or self.exact_byte_replay_pass_count
            != len(self.raw_descriptors) + len(self.provider_artifact_descriptors)
            or self.audit_id
            != _identity(
                self,
                "audit_id",
                "finance_v26_mapper_v2_frequency_raw_lineage:",
            )
        ):
            raise ValueError("v26.161 Raw Lineage changed")
        return self


class DetailFile(FrozenModel):
    relative_path: str = Field(min_length=1)
    sha256: str = Field(min_length=64, max_length=64)
    byte_count: int = Field(gt=0)


class PostrunTransitionContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    execution_report_id: str = Field(min_length=1)
    measurement_gate_id: str = Field(min_length=1)
    assignment_catalog_id: str = Field(min_length=1)
    frequency_summary_id: str = Field(min_length=1)
    next_permitted_stage: Literal["fresh_mapper_v2_reachability_frequency_postrun_audit_only"] = (
        NEXT_STAGE
    )
    independent_raw_reprojection_required: Literal[True] = True
    independent_reference_mapper_reexecution_required: Literal[True] = True
    provider_calls_authorized: Literal[False] = False
    row_deletion_or_denominator_repair_authorized: Literal[False] = False
    protocol_or_threshold_change_authorized: Literal[False] = False
    vtdo_training_release_or_production_authorized: Literal[False] = False

    @model_validator(mode="after")
    def validate_contract(self) -> PostrunTransitionContract:
        if self.contract_id != _identity(
            self,
            "contract_id",
            "finance_v26_mapper_v2_frequency_execution_transition:",
        ):
            raise ValueError("v26.161 postrun transition changed")
        return self


class FrequencyExecutionReport(FrozenModel):
    report_id: str = Field(min_length=1)
    run_id: str = RUN_ID
    report_run_id: str = REPORT_RUN_ID
    prospective_execution_id: str = EXPECTED_PROSPECTIVE_EXECUTION_ID
    prospective_report_id: str = EXPECTED_PROSPECTIVE_REPORT_ID
    preflight_report_id: str = EXPECTED_PREFLIGHT_REPORT_ID
    source_replay_audit_id: str = Field(min_length=1)
    preexecution_binding_audit_id: str = Field(min_length=1)
    execution_contract_id: str = EXPECTED_EXECUTION_CONTRACT_ID
    manifest_id: str = EXPECTED_MANIFEST_ID
    outcome_contract_id: str = EXPECTED_OUTCOME_CONTRACT_ID
    runner_contract_id: str = EXPECTED_RUNNER_CONTRACT_ID
    measurement_gate_id: str = Field(min_length=1)
    raw_lineage_audit_id: str = Field(min_length=1)
    mapper_execution_audit_id: str = Field(min_length=1)
    assignment_catalog_id: str = Field(min_length=1)
    frequency_summary_id: str = Field(min_length=1)
    cell_denominator_catalog_id: str = Field(min_length=1)
    exact_job_denominator: Literal[360] = 360
    complete_result_count: Literal[360] = 360
    complete_raw_count: Literal[360] = 360
    terminal_counts: dict[str, int]
    measurement_gate_passed: bool
    exact_frequency_estimands_null: bool
    validity_evaluable_count: int = Field(ge=0, le=360)
    base_valid_count: int = Field(ge=0, le=360)
    mechanism_qualified_count: int = Field(ge=0, le=360)
    qualified_valid_count: int = Field(ge=0, le=360)
    formal_assignment_count: int = Field(ge=0, le=360)
    structural_state_count: int = Field(ge=0, le=360)
    empirical_route_signature_count: int = Field(ge=0, le=360)
    frequency_report_count: Literal[48] = 48
    null_frequency_report_count: int = Field(ge=0, le=48)
    no_qualified_cell_count: int = Field(ge=0, le=48)
    provider_call_count: int = Field(ge=0, le=8280)
    transport_inclusive_invocation_count: int = Field(ge=0, le=8640)
    provider_prompt_tokens: int = Field(ge=0)
    provider_completion_tokens: int = Field(ge=0)
    provider_reasoning_tokens: int = Field(ge=0)
    provider_total_tokens: int = Field(ge=0)
    estimated_cost_usd: str = Field(min_length=1)
    bounded_policy_empirical_frequency_only: Literal[True] = True
    unrestricted_natural_agent_distribution_claimed: Literal[False] = False
    cross_task_state_probability_claimed: Literal[False] = False
    confidence_interval_claimed: Literal[False] = False
    vtdo_authorized: Literal[False] = False
    independent_postrun_audit_required: Literal[True] = True
    detail_files: tuple[DetailFile, ...]
    next_permitted_stage: Literal["fresh_mapper_v2_reachability_frequency_postrun_audit_only"] = (
        NEXT_STAGE
    )
    execution_status: Literal[
        "measurement_gate_passed_frequency_pending_independent_audit",
        "measurement_gate_failed_all_frequency_estimands_null_pending_independent_audit",
    ]

    @model_validator(mode="after")
    def validate_report(self) -> FrequencyExecutionReport:
        expected_status = (
            "measurement_gate_passed_frequency_pending_independent_audit"
            if self.measurement_gate_passed
            else "measurement_gate_failed_all_frequency_estimands_null_pending_independent_audit"
        )
        if (
            sum(self.terminal_counts.values()) != 360
            or self.exact_frequency_estimands_null == self.measurement_gate_passed
            or self.execution_status != expected_status
            or (not self.measurement_gate_passed and self.formal_assignment_count != 0)
            or self.report_id
            != _identity(
                self,
                "report_id",
                "finance_v26_mapper_v2_frequency_execution_report:",
            )
        ):
            raise ValueError("v26.161 execution report changed")
        return self


@dataclass(frozen=True)
class PreparedFrequencyExecution:
    source_replay: ExecutionSourceReplayAudit
    preexecution_binding: PreexecutionBindingAudit
    preflight_report: FrequencyPreflightReport
    reproducibility_root: ReproducibilityRootAudit
    source_population: FreshFrequencySourcePopulation
    source_selection: SourceSelectionAudit
    tasks: Any
    paths: Any
    support_closure: Any
    detour_qualification: Any
    resource: Any
    omega_catalog: OmegaTaskContextCatalogV2
    cell_catalog: TaskConditionCellCatalogV2
    assignment_contract: FrequencyAssignmentContract
    mapper_protocol: MapperV2FrequencyProtocol
    estimand_contract: FrequencyEstimandContract
    execution_contract: FrequencyExecutionContract
    manifest: FrequencyManifest
    outcome_contract: FrequencyOutcomeContract
    runner_contract: FrequencyRunnerContract
    transition: ProspectiveTransitionContract
    joint_contract: Any
    grammar: QualifiedFinalResponseGrammar
    semantic_policy: Any
    mapper_contract: Any
    legacy_prepared: execution_base.PreparedExecution
