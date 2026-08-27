from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.canonical_json import strict_canonical_hash
from trusted_synthesis.core.evaluation.bounded_policy_endpoint import (
    BoundedPolicyCellFrequencyReport,
    BoundedPolicyEndpointGenerationPolicy,
    PolicyHorizonReason,
)
from trusted_synthesis.core.trajectory.empirical_state_mapping_v2 import (
    ValidOnlyEmpiricalStateAssignmentV2,
)
from trusted_synthesis.core.trajectory.reachability_frequency_v2 import (
    TaskConditionCellCatalogV2,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_bounded_policy_endpoint_frequency_preflight as preflight,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_reachability_execution as execution_base,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_bounded_policy_endpoint_frequency_preflight_models import (  # noqa: E501
    BoundedPolicyEstimandContract,
    BoundedPolicyOutcomeContract,
    BoundedPolicyPreflightReport,
    BoundedPolicyRunnerContract,
    ProspectiveTransitionContract,
    RouteBSourceSelectionAudit,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_mapper_v2_frequency_preflight_models import (  # noqa: E501
    FrequencyAssignmentContract,
    FrequencyExecutionContract,
    FrequencyManifest,
    FreshFrequencySourcePopulation,
    MapperV2FrequencyProtocol,
    OmegaTaskContextCatalogV2,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_two_stage_semantic_proposal_execution import (  # noqa: E501
    RawFileDescriptor,
)
from trusted_synthesis.runtime.agent.prospective_bounded_policy_endpoint_runner import (
    BoundedPolicyEndpointRecord,
)
from trusted_synthesis.runtime.agent.prospective_qualified_final_response_grammar import (
    QualifiedFinalResponseGrammar,
)

RUN_ID: Final = preflight.PROSPECTIVE_EXECUTION_RUN_ID
REPORT_RUN_ID: Final = preflight.PROSPECTIVE_REPORT_RUN_ID
PREFLIGHT_DIR: Final = preflight.OUTPUT_DIR
OUTPUT_DIR: Final = (
    "artifacts/vtdo_experiment/"
    "finance_v26_164_bounded_policy_endpoint_frequency_execution_v1_20260827"
)
MODEL_IMPLEMENTATION_PATH: Final = (
    "src/trusted_synthesis/experiments/vtdo_experiment/"
    "phase1_v26_bounded_policy_endpoint_frequency_execution_models.py"
)
RUNNER_IMPLEMENTATION_PATH: Final = (
    "src/trusted_synthesis/experiments/vtdo_experiment/"
    "phase1_v26_bounded_policy_endpoint_frequency_execution.py"
)
NEXT_STAGE: Final = "fresh_bounded_policy_endpoint_frequency_postrun_audit_only"

EXPECTED_PREFLIGHT_REPORT_ID: Final = (
    "finance_v26_bounded_policy_preflight_report:"
    "93af17282d46c1114f3d568978b92ae63b017680d952b1b19890e2fe83e9ec06"
)
EXPECTED_PREFLIGHT_REPORT_SHA256: Final = (
    "78e91be467f17388c64a2bc6ed573a98fe13eecc328611db2392beacb0607f7d"
)
EXPECTED_PREDECESSOR_REPLAY_ID: Final = (
    "finance_v26_bounded_policy_predecessor_replay:"
    "3b2e254ed316eaae157d75bd8521aa9ae14e98aec8837692591e9c4c99112e35"
)
EXPECTED_SOURCE_POPULATION_ID: Final = (
    "finance_v26_frequency_source_population:"
    "3443b578cf293dda451ff822a681abc6dbb502c24fcafac00b9cdab77ff49bc4"
)
EXPECTED_SOURCE_SELECTION_ID: Final = (
    "finance_v26_bounded_policy_source_selection:"
    "2d522be3ae43eca15d7631433de4bbb505667edea3ef9ef1b20c495b67497c5f"
)
EXPECTED_TASK_CATALOG_ID: Final = (
    "finance_v26_fresh_reachability_task_catalog:"
    "468343551326133e89f1576ede569d58b5835247dab084dbe1c8ca8316d42509"
)
EXPECTED_PATH_CATALOG_ID: Final = (
    "finance_v26_fresh_reachability_path_catalog:"
    "d47d6115019ee9184947825391114f25692926d409fd61d114caf6a6ed4d92f0"
)
EXPECTED_SUPPORT_ID: Final = (
    "finance_v26_fresh_reachability_support_closure:"
    "a5d317059d4184a2b3f55b0e9839050c1d95b1e44aa738e84adaf04e8bae1634"
)
EXPECTED_DETOUR_ID: Final = (
    "finance_v26_fresh_reachability_detour_audit:"
    "9ce2e4eda242ab3c9a1e469d36a4ccf232ccb93fc8c49d8f090887c7097f41b0"
)
EXPECTED_RESOURCE_ID: Final = (
    "finance_v26_fresh_reachability_resource_contract:"
    "64507d067b2842c93da2d622b18d7b27973bf23396968994dda6e50fe06ef0e5"
)
EXPECTED_POLICY_ID: Final = (
    "bounded_policy_endpoint_generation_policy:"
    "481664d9ed21cb7f610754ff290021b7fb6ce5451ff57600b572224bff60bbe2"
)
EXPECTED_SEMANTIC_POLICY_ID: Final = (
    "empirical_state_semantic_policy:"
    "588bf09238a4a16c830ad9216d40d311229b537204cdb383ebb117be2cededca"
)
EXPECTED_MAPPER_CONTRACT_ID: Final = (
    "valid_only_state_mapper_contract_v2:"
    "af984e1acc450f34fed741dd88790322e84db3098f0aad4c8329fb70a1311982"
)
EXPECTED_OMEGA_CATALOG_ID: Final = (
    "finance_v26_frequency_omega_catalog:"
    "022035c23405d63a52ca14508ae5a12ed3d410bad575faf6dd2640899451c4ee"
)
EXPECTED_CELL_CATALOG_ID: Final = (
    "mapper_v2_task_condition_cell_catalog:"
    "d0d306a6c550cc6cf37ab4f670e7f05adb3c4091f6015164f16a9856cf8fb8da"
)
EXPECTED_ASSIGNMENT_CONTRACT_ID: Final = (
    "finance_v26_frequency_assignment_contract:"
    "373ec434d95778f87819361cf0278345a418c6208b9c187954de2f3936f82a36"
)
EXPECTED_MAPPER_PROTOCOL_ID: Final = (
    "finance_v26_mapper_v2_frequency_protocol:"
    "0bbd75c1acb82fa449944e5c55a7a1596f041a40e2e67f44f3a52345c46cbb23"
)
EXPECTED_ESTIMAND_CONTRACT_ID: Final = (
    "finance_v26_bounded_policy_estimand_contract:"
    "ad923ed5024db84733618f50218baeae39705b12ccffc002478cd623172bb221"
)
EXPECTED_EXECUTION_CONTRACT_ID: Final = (
    "finance_v26_frequency_execution_contract:"
    "014e22dca706d22b102eb69195de37a9362c5cf06138fe98e3d4250c8f7fa950"
)
EXPECTED_MANIFEST_ID: Final = (
    "finance_v26_frequency_manifest:"
    "5d4d25a257b1e5cb4de613f79bc97f8c2c346642a93883e47b98b49e9941933d"
)
EXPECTED_OUTCOME_CONTRACT_ID: Final = (
    "finance_v26_bounded_policy_outcome_contract:"
    "8b4f38bfe2a2af4060f076afb4b06eea81431c3fdff7f55532c64fe509bcaf57"
)
EXPECTED_RUNNER_CONTRACT_ID: Final = (
    "finance_v26_bounded_policy_runner_contract:"
    "f79d0d54670b5c13024a353f5ddf38d69f554988e6c50f8139c4d3717cb5d8e7"
)
EXPECTED_TRANSITION_ID: Final = (
    "finance_v26_bounded_policy_transition:"
    "bb2fd59f49bbbf2ff5aa8e89b5499fe07cc8011823b9f7317b7d7868d10c155c"
)
EXPECTED_PROSPECTIVE_EXECUTION_ID: Final = (
    "finance_v26_bounded_policy_frequency_execution:"
    "a05757fbceccb300af43c867c65d220fdb75a5734af33d1966fe1b24bc96e05e"
)
EXPECTED_PROSPECTIVE_REPORT_ID: Final = (
    "finance_v26_bounded_policy_frequency_execution_report:"
    "d80e3536f4acb40aa30238aa662b2e79287c1680917211314e499ae8ddd330c0"
)


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


class ImplementationFileBinding(FrozenModel):
    relative_path: str = Field(min_length=1)
    sha256: str = Field(min_length=64, max_length=64)
    byte_count: int = Field(gt=0)


class ExecutionSourceReplayAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    preflight_report_id: str = EXPECTED_PREFLIGHT_REPORT_ID
    preflight_report_sha256: str = EXPECTED_PREFLIGHT_REPORT_SHA256
    predecessor_replay_audit_id: str = EXPECTED_PREDECESSOR_REPLAY_ID
    preflight_output_count: Literal[34] = 34
    preflight_output_byte_match_count: Literal[34] = 34
    independent_rebuild_output_count: Literal[34] = 34
    independent_rebuild_byte_match_count: Literal[34] = 34
    implementation_files: tuple[ImplementationFileBinding, ...] = Field(min_length=2, max_length=2)
    implementation_bundle_sha256: str = Field(min_length=64, max_length=64)
    migrated_checkout_snapshot_available: Literal[False] = False
    external_recovered_snapshot_available: Literal[True] = True
    external_recovered_snapshot_sha256: str = preflight.EXPECTED_SOURCE_SNAPSHOT_SHA256
    external_recovered_snapshot_byte_count: Literal[604998387] = 604_998_387
    v26_158_full_transitive_rebuild_claimed: Literal[False] = False
    credential_lookup_attempted: Literal[False] = False
    provider_calls: Literal[0] = 0
    status: Literal["passed"] = "passed"

    @model_validator(mode="after")
    def validate_audit(self) -> ExecutionSourceReplayAudit:
        paths = tuple(item.relative_path for item in self.implementation_files)
        expected_bundle = hashlib.sha256(
            canonical_bytes(
                tuple(item.model_dump(mode="python") for item in self.implementation_files)
            )
        ).hexdigest()
        if (
            paths != tuple(sorted(set(paths)))
            or self.implementation_bundle_sha256 != expected_bundle
            or self.audit_id
            != identity(
                self,
                "audit_id",
                "finance_v26_bounded_policy_execution_source_replay:",
            )
        ):
            raise ValueError("v26.164 execution source replay changed")
        return self


class PreexecutionBindingAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    preflight_report_id: str = EXPECTED_PREFLIGHT_REPORT_ID
    transition_contract_id: str = EXPECTED_TRANSITION_ID
    execution_contract_id: str = EXPECTED_EXECUTION_CONTRACT_ID
    manifest_id: str = EXPECTED_MANIFEST_ID
    runner_contract_id: str = EXPECTED_RUNNER_CONTRACT_ID
    outcome_contract_id: str = EXPECTED_OUTCOME_CONTRACT_ID
    generation_policy_id: str = EXPECTED_POLICY_ID
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
    unopened_endpoint_record_count: Literal[0] = 0
    formal_assignment_count: Literal[0] = 0
    credential_lookup_attempted: Literal[False] = False
    provider_calls: Literal[0] = 0
    passed: Literal[True] = True

    @model_validator(mode="after")
    def validate_audit(self) -> PreexecutionBindingAudit:
        if self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_bounded_policy_preexecution_binding:",
        ):
            raise ValueError("v26.164 preexecution binding changed")
        return self


class BoundedPolicyFrequencyMeasurementResult(FrozenModel):
    result_id: str = Field(min_length=1)
    experiment_id: str = EXPECTED_PROSPECTIVE_EXECUTION_ID
    job_id: str = Field(min_length=1)
    task_condition_cell_id: str = Field(min_length=1)
    task_package_id: str = Field(min_length=1)
    experimental_condition_id: str = Field(min_length=1)
    generation_policy_id: str = EXPECTED_POLICY_ID
    legacy_joint_measurement_projection: execution_base.ReachabilityMeasurementResult
    bounded_policy_endpoint_record: BoundedPolicyEndpointRecord
    formal_mapper_invocation_before_global_gate: Literal[False] = False

    @model_validator(mode="after")
    def validate_result(self) -> BoundedPolicyFrequencyMeasurementResult:
        legacy = self.legacy_joint_measurement_projection
        endpoint = self.bounded_policy_endpoint_record.projection
        if (
            self.job_id != legacy.job_id
            or self.task_package_id != legacy.task_package_id
            or self.bounded_policy_endpoint_record.raw_execution_id != legacy.raw_execution_id
            or endpoint.generation_policy_id != self.generation_policy_id
        ):
            raise ValueError("v26.164 Measurement result crossed frozen parents")
        if endpoint.policy_horizon_status == "within_horizon" and endpoint.validity_evaluable:
            if (
                endpoint.model_terminal_observed != legacy.model_endpoint_observed
                or endpoint.base_validity != legacy.base_trajectory_validity
                or endpoint.mechanism_qualification != legacy.mechanism_qualification
                or endpoint.qualified_validity != legacy.qualified_trajectory_validity
            ):
                raise ValueError("v26.164 model endpoint changed frozen validity")
        if self.result_id != identity(
            self,
            "result_id",
            "finance_v26_bounded_policy_frequency_measurement_result:",
        ):
            raise ValueError("v26.164 Measurement result identity changed")
        return self


class BoundedPolicyFrequencyAssignment(FrozenModel):
    assignment_id: str = Field(min_length=1)
    experiment_id: str = EXPECTED_PROSPECTIVE_EXECUTION_ID
    job_id: str = Field(min_length=1)
    task_condition_cell_id: str = Field(min_length=1)
    task_package_id: str = Field(min_length=1)
    experimental_condition_id: str = Field(min_length=1)
    generation_policy_id: str = EXPECTED_POLICY_ID
    global_integrity_gate_id: str = Field(min_length=1)
    mapping_assignment: ValidOnlyEmpiricalStateAssignmentV2
    structural_state_id: str = Field(min_length=1)
    empirical_route_signature_id: str = Field(min_length=1)
    qualified_validity: Literal[True] = True
    global_integrity_gate_passed: Literal[True] = True
    frequency_denominator_eligible: Literal[True] = True
    route_signature_excluded_from_statistics_key: Literal[True] = True
    schema_version: str = "bounded_policy_frequency_assignment.v1"

    @model_validator(mode="after")
    def validate_assignment(self) -> BoundedPolicyFrequencyAssignment:
        mapped = self.mapping_assignment
        if (
            self.experimental_condition_id != mapped.experimental_condition_id
            or self.structural_state_id != mapped.structural_state_id
            or self.empirical_route_signature_id != mapped.empirical_route_signature_id
            or mapped.qualified_validity is not True
            or not mapped.valid_only_gate_crossed
            or mapped.historical_reclassified
            or self.assignment_id
            != identity(
                self,
                "assignment_id",
                "finance_v26_bounded_policy_frequency_assignment:",
            )
        ):
            raise ValueError("v26.164 bounded-policy Assignment changed")
        return self


class BoundedPolicyAssignmentCatalog(FrozenModel):
    catalog_id: str = Field(min_length=1)
    experiment_id: str = EXPECTED_PROSPECTIVE_EXECUTION_ID
    global_integrity_gate_id: str = Field(min_length=1)
    mapper_protocol_id: str = EXPECTED_MAPPER_PROTOCOL_ID
    assignment_contract_id: str = EXPECTED_ASSIGNMENT_CONTRACT_ID
    assignments: tuple[BoundedPolicyFrequencyAssignment, ...]
    assignment_count: int = Field(ge=0, le=360)
    structural_state_count: int = Field(ge=0, le=360)
    empirical_route_signature_count: int = Field(ge=0, le=360)
    global_integrity_gate_passed: bool
    failed_gate_created_zero_assignments: Literal[True] = True

    @model_validator(mode="after")
    def validate_catalog(self) -> BoundedPolicyAssignmentCatalog:
        ids = tuple(item.assignment_id for item in self.assignments)
        if (
            ids != tuple(sorted(set(ids)))
            or self.assignment_count != len(self.assignments)
            or self.structural_state_count
            != len({item.structural_state_id for item in self.assignments})
            or self.empirical_route_signature_count
            != len({item.empirical_route_signature_id for item in self.assignments})
            or (not self.global_integrity_gate_passed and self.assignments)
            or self.catalog_id
            != identity(
                self,
                "catalog_id",
                "finance_v26_bounded_policy_frequency_assignment_catalog:",
            )
        ):
            raise ValueError("v26.164 Assignment Catalog changed")
        return self


class MapperExecutionAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    global_integrity_gate_id: str = Field(min_length=1)
    mapper_protocol_id: str = EXPECTED_MAPPER_PROTOCOL_ID
    qualified_row_count: int = Field(ge=0, le=360)
    production_mapper_invocation_count: int = Field(ge=0, le=360)
    reference_mapper_invocation_count: int = Field(ge=0, le=360)
    production_reference_exact_state_match_count: int = Field(ge=0, le=360)
    formal_assignment_count: int = Field(ge=0, le=360)
    global_integrity_gate_passed: bool
    mapper_invocation_before_global_gate_count: Literal[0] = 0
    policy_horizon_mapping_attempt_count: Literal[0] = 0
    mapper_v1_assignment_reuse_count: Literal[0] = 0
    provider_calls: Literal[0] = 0

    @model_validator(mode="after")
    def validate_audit(self) -> MapperExecutionAudit:
        expected = self.qualified_row_count if self.global_integrity_gate_passed else 0
        if (
            self.production_mapper_invocation_count != expected
            or self.reference_mapper_invocation_count != expected
            or self.production_reference_exact_state_match_count != expected
            or self.formal_assignment_count != expected
            or self.audit_id
            != identity(
                self,
                "audit_id",
                "finance_v26_bounded_policy_mapper_execution:",
            )
        ):
            raise ValueError("v26.164 Mapper execution changed")
        return self


class HorizonReasonRow(FrozenModel):
    reason: PolicyHorizonReason
    endpoint_count: int = Field(ge=0, le=360)
    later_provider_call_count: Literal[0] = 0
    raw_instrument_failure_count: Literal[0] = 0
    resource_accounting_failure_count: Literal[0] = 0
    measurement_support_exit_count: Literal[0] = 0
    model_semantic_error_count: Literal[0] = 0


class HorizonReasonAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    generation_policy_id: str = EXPECTED_POLICY_ID
    rows: tuple[HorizonReasonRow, ...] = Field(min_length=5, max_length=5)
    policy_horizon_endpoint_count: int = Field(ge=0, le=360)
    undeclared_horizon_reason_count: Literal[0] = 0
    historical_reclassification_count: Literal[0] = 0

    @model_validator(mode="after")
    def validate_audit(self) -> HorizonReasonAudit:
        reasons = tuple(item.reason for item in self.rows)
        if (
            reasons
            != (
                "ordinary_detour_limit",
                "primary_request_limit",
                "provider_call_limit",
                "rollout_token_limit",
                "transport_invocation_limit",
            )
            or self.policy_horizon_endpoint_count != sum(item.endpoint_count for item in self.rows)
            or self.audit_id
            != identity(
                self,
                "audit_id",
                "finance_v26_bounded_policy_horizon_reason_audit:",
            )
        ):
            raise ValueError("v26.164 Horizon reason audit changed")
        return self


class BoundedPolicyEndpointCatalog(FrozenModel):
    catalog_id: str = Field(min_length=1)
    experiment_id: str = EXPECTED_PROSPECTIVE_EXECUTION_ID
    generation_policy_id: str = EXPECTED_POLICY_ID
    records: tuple[BoundedPolicyEndpointRecord, ...] = Field(min_length=360, max_length=360)
    record_count: Literal[360] = 360
    bounded_policy_endpoint_count: int = Field(ge=0, le=360)
    model_terminal_count: int = Field(ge=0, le=360)
    policy_horizon_endpoint_count: int = Field(ge=0, le=360)
    terminal_class_counts: dict[str, int]
    raw_terminal_disposition_counts: dict[str, int]
    horizon_reason_audit_id: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_catalog(self) -> BoundedPolicyEndpointCatalog:
        ids = tuple(item.record_id for item in self.records)
        projections = tuple(item.projection for item in self.records)
        if (
            ids != tuple(sorted(set(ids)))
            or self.bounded_policy_endpoint_count
            != sum(item.bounded_policy_endpoint_observed for item in projections)
            or self.model_terminal_count
            != sum(item.model_terminal_observed for item in projections)
            or self.policy_horizon_endpoint_count
            != sum(item.policy_terminal_observed for item in projections)
            or sum(self.terminal_class_counts.values()) != 360
            or sum(self.raw_terminal_disposition_counts.values()) != 360
            or self.catalog_id
            != identity(
                self,
                "catalog_id",
                "finance_v26_bounded_policy_endpoint_catalog:",
            )
        ):
            raise ValueError("v26.164 endpoint Catalog changed")
        return self


class BoundedPolicyCellFrequencyCatalog(FrozenModel):
    catalog_id: str = Field(min_length=1)
    experiment_id: str = EXPECTED_PROSPECTIVE_EXECUTION_ID
    generation_policy_id: str = EXPECTED_POLICY_ID
    global_integrity_gate_id: str = Field(min_length=1)
    reports: tuple[BoundedPolicyCellFrequencyReport, ...] = Field(min_length=48, max_length=48)
    cell_count: Literal[48] = 48
    n_total_sum: Literal[360] = 360
    n_policy_endpoint_sum: int = Field(ge=0, le=360)
    n_qualified_sum: int = Field(ge=0, le=360)
    q_instantiated_cell_count: int = Field(ge=0, le=48)
    pi_instantiated_cell_count: int = Field(ge=0, le=48)
    zero_qualified_cell_count: int = Field(ge=0, le=48)
    empirical_non_degenerate_cell_count: int = Field(ge=0, le=48)
    global_integrity_gate_passed: bool

    @model_validator(mode="after")
    def validate_catalog(self) -> BoundedPolicyCellFrequencyCatalog:
        ids = tuple(item.report_id for item in self.reports)
        if (
            ids != tuple(sorted(set(ids)))
            or sum(item.n_total for item in self.reports) != self.n_total_sum
            or sum(item.n_policy_endpoints for item in self.reports) != self.n_policy_endpoint_sum
            or sum(item.n_qualified for item in self.reports) != self.n_qualified_sum
            or sum(item.q_hat is not None for item in self.reports)
            != self.q_instantiated_cell_count
            or sum(item.pi_instantiated for item in self.reports) != self.pi_instantiated_cell_count
            or sum(item.pi_null_reason == "no_qualified_rows" for item in self.reports)
            != self.zero_qualified_cell_count
            or sum(item.empirical_non_degenerate is True for item in self.reports)
            != self.empirical_non_degenerate_cell_count
            or any(
                item.global_integrity_gate_passed != self.global_integrity_gate_passed
                for item in self.reports
            )
            or self.catalog_id
            != identity(
                self,
                "catalog_id",
                "finance_v26_bounded_policy_cell_frequency_catalog:",
            )
        ):
            raise ValueError("v26.164 Cell Frequency Catalog changed")
        return self


class RawLineageAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    runner_contract_id: str = EXPECTED_RUNNER_CONTRACT_ID
    manifest_id: str = EXPECTED_MANIFEST_ID
    raw_execution_count: Literal[360] = 360
    measurement_result_count: Literal[360] = 360
    endpoint_record_count: Literal[360] = 360
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
            != identity(
                self,
                "audit_id",
                "finance_v26_bounded_policy_raw_lineage:",
            )
        ):
            raise ValueError("v26.164 Raw Lineage changed")
        return self


class DetailFile(FrozenModel):
    relative_path: str = Field(min_length=1)
    sha256: str = Field(min_length=64, max_length=64)
    byte_count: int = Field(gt=0)


class PostrunTransitionContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    execution_report_id: str = Field(min_length=1)
    global_integrity_gate_id: str = Field(min_length=1)
    endpoint_catalog_id: str = Field(min_length=1)
    assignment_catalog_id: str = Field(min_length=1)
    cell_frequency_catalog_id: str = Field(min_length=1)
    next_permitted_stage: Literal["fresh_bounded_policy_endpoint_frequency_postrun_audit_only"] = (
        NEXT_STAGE
    )
    independent_raw_reprojection_required: Literal[True] = True
    independent_reference_mapper_reexecution_required: Literal[True] = True
    independent_q_pi_recalculation_required: Literal[True] = True
    provider_calls_authorized: Literal[False] = False
    row_deletion_or_denominator_repair_authorized: Literal[False] = False
    policy_mapper_threshold_or_interval_change_authorized: Literal[False] = False
    state_probability_vtdo_training_release_or_production_authorized: Literal[False] = False

    @model_validator(mode="after")
    def validate_contract(self) -> PostrunTransitionContract:
        if self.contract_id != identity(
            self,
            "contract_id",
            "finance_v26_bounded_policy_execution_transition:",
        ):
            raise ValueError("v26.164 postrun transition changed")
        return self


class BoundedPolicyExecutionReport(FrozenModel):
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
    generation_policy_id: str = EXPECTED_POLICY_ID
    global_integrity_gate_id: str = Field(min_length=1)
    endpoint_catalog_id: str = Field(min_length=1)
    horizon_reason_audit_id: str = Field(min_length=1)
    raw_lineage_audit_id: str = Field(min_length=1)
    mapper_execution_audit_id: str = Field(min_length=1)
    assignment_catalog_id: str = Field(min_length=1)
    cell_frequency_catalog_id: str = Field(min_length=1)
    exact_job_denominator: Literal[360] = 360
    complete_result_count: Literal[360] = 360
    complete_raw_count: Literal[360] = 360
    bounded_policy_endpoint_count: int = Field(ge=0, le=360)
    model_terminal_count: int = Field(ge=0, le=360)
    policy_horizon_endpoint_count: int = Field(ge=0, le=360)
    raw_terminal_counts: dict[str, int]
    bounded_policy_terminal_counts: dict[str, int]
    policy_horizon_reason_counts: dict[str, int]
    global_integrity_gate_passed: bool
    all_cell_estimands_null: bool
    validity_evaluable_count: int = Field(ge=0, le=360)
    base_valid_count: int = Field(ge=0, le=360)
    mechanism_qualified_count: int = Field(ge=0, le=360)
    qualified_valid_count: int = Field(ge=0, le=360)
    formal_assignment_count: int = Field(ge=0, le=360)
    structural_state_count: int = Field(ge=0, le=360)
    empirical_route_signature_count: int = Field(ge=0, le=360)
    cell_report_count: Literal[48] = 48
    q_instantiated_cell_count: int = Field(ge=0, le=48)
    pi_instantiated_cell_count: int = Field(ge=0, le=48)
    zero_qualified_cell_count: int = Field(ge=0, le=48)
    empirical_non_degenerate_cell_count: int = Field(ge=0, le=48)
    provider_call_count: int = Field(ge=0, le=8280)
    transport_inclusive_invocation_count: int = Field(ge=0, le=8640)
    provider_prompt_tokens: int = Field(ge=0)
    provider_completion_tokens: int = Field(ge=0)
    provider_reasoning_tokens: int = Field(ge=0)
    provider_total_tokens: int = Field(ge=0)
    estimated_cost_usd: str = Field(min_length=1)
    bounded_policy_finite_sample_empirical_frequency_only: Literal[True] = True
    unrestricted_natural_agent_distribution_claimed: Literal[False] = False
    cross_task_state_probability_claimed: Literal[False] = False
    path_causal_effect_claimed: Literal[False] = False
    simultaneous_multinomial_coverage_claimed: Literal[False] = False
    vtdo_authorized: Literal[False] = False
    independent_postrun_audit_required: Literal[True] = True
    detail_files: tuple[DetailFile, ...]
    next_permitted_stage: Literal["fresh_bounded_policy_endpoint_frequency_postrun_audit_only"] = (
        NEXT_STAGE
    )
    execution_status: Literal[
        "global_integrity_gate_passed_bounded_policy_frequency_pending_independent_audit",
        "global_integrity_gate_failed_all_cell_estimands_null_pending_independent_audit",
    ]

    @model_validator(mode="after")
    def validate_report(self) -> BoundedPolicyExecutionReport:
        expected_status = (
            "global_integrity_gate_passed_bounded_policy_frequency_pending_independent_audit"
            if self.global_integrity_gate_passed
            else "global_integrity_gate_failed_all_cell_estimands_null_pending_independent_audit"
        )
        if (
            sum(self.raw_terminal_counts.values()) != 360
            or sum(self.bounded_policy_terminal_counts.values()) != 360
            or sum(self.policy_horizon_reason_counts.values()) != self.policy_horizon_endpoint_count
            or self.all_cell_estimands_null == self.global_integrity_gate_passed
            or self.execution_status != expected_status
            or (not self.global_integrity_gate_passed and self.formal_assignment_count != 0)
            or self.report_id
            != identity(
                self,
                "report_id",
                "finance_v26_bounded_policy_frequency_execution_report:",
            )
        ):
            raise ValueError("v26.164 execution report changed")
        return self


@dataclass(frozen=True)
class PreparedBoundedPolicyExecution:
    source_replay: ExecutionSourceReplayAudit
    preexecution_binding: PreexecutionBindingAudit
    preflight_report: BoundedPolicyPreflightReport
    source_population: FreshFrequencySourcePopulation
    source_selection: RouteBSourceSelectionAudit
    tasks: Any
    paths: Any
    support_closure: Any
    detour_qualification: Any
    resource: Any
    policy: BoundedPolicyEndpointGenerationPolicy
    omega_catalog: OmegaTaskContextCatalogV2
    cell_catalog: TaskConditionCellCatalogV2
    assignment_contract: FrequencyAssignmentContract
    mapper_protocol: MapperV2FrequencyProtocol
    estimand_contract: BoundedPolicyEstimandContract
    execution_contract: FrequencyExecutionContract
    manifest: FrequencyManifest
    outcome_contract: BoundedPolicyOutcomeContract
    runner_contract: BoundedPolicyRunnerContract
    transition: ProspectiveTransitionContract
    joint_contract: Any
    grammar: QualifiedFinalResponseGrammar
    semantic_policy: Any
    mapper_contract: Any
    legacy_prepared: execution_base.PreparedExecution
