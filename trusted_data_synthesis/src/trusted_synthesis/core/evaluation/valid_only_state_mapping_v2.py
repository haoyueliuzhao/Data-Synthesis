from __future__ import annotations

from collections.abc import Callable
from typing import Generic, Literal, Protocol, TypeVar

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.canonical_json import strict_canonical_hash
from trusted_synthesis.core.evaluation.trajectory_validity import (
    QualifiedTrajectoryValidityReport,
)

VALID_ONLY_STATE_MAPPING_V2_VERSION = "valid_only_state_mapping.v2"
REQUIRED_ASSIGNMENT_BINDINGS_V2 = (
    "canonical_result_semantics_hash",
    "empirical_route_signature_id",
    "experimental_condition_id",
    "mapper_contract_id",
    "omega_task_context_id",
    "qualified_validity_report_id",
    "qualified_verifier_input_hash",
    "raw_execution_artifact_hash",
    "raw_final_payload_hash",
    "raw_observation_prefix_hash",
    "static_path_catalog_id",
    "structural_state_id",
    "trajectory_bound_artifact_hash",
    "trajectory_semantic_content_hash",
)

MappedStateT = TypeVar("MappedStateT")
TrajectoryT = TypeVar("TrajectoryT", bound="ContentAddressedTrajectoryV2")


class ContentAddressedTrajectoryV2(Protocol):
    trajectory_id: str
    trajectory_semantic_content_hash: str
    trajectory_bound_artifact_hash: str
    raw_observation_prefix_hash: str


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


def _identity(value: BaseModel, field: str, prefix: str) -> str:
    return strict_canonical_hash(value.model_dump(mode="python", exclude={field}), prefix=prefix)


class QualifiedVerifierInputBindingV2(FrozenModel):
    binding_id: str = Field(min_length=1)
    qualified_validity_report_id: str = Field(min_length=1)
    qualified_verifier_contract_id: str = Field(min_length=1)
    trajectory_id: str = Field(min_length=1)
    trajectory_semantic_content_hash: str = Field(min_length=1)
    trajectory_bound_artifact_hash: str = Field(min_length=1)
    raw_execution_artifact_hash: str = Field(min_length=1)
    qualified_verifier_input_hash: str = Field(min_length=1)
    valid_only_binding_emitted_after_verifier_input_freeze: Literal[True] = True
    schema_version: str = "qualified_verifier_input_binding.v2"

    @model_validator(mode="after")
    def validate_binding(self) -> QualifiedVerifierInputBindingV2:
        if self.binding_id != _identity(
            self,
            "binding_id",
            "qualified_verifier_input_binding:",
        ):
            raise ValueError("Qualified Verifier input binding identity changed")
        return self


class ValidOnlyStateMapperContractV2(FrozenModel):
    contract_id: str = Field(min_length=1)
    qualified_verifier_contract_id: str = Field(min_length=1)
    mapper_implementation_id: str = Field(min_length=1)
    mapper_version: Literal["empirical_structural_state_mapping.v2"] = (
        "empirical_structural_state_mapping.v2"
    )
    semantic_policy_id: str = Field(min_length=1)
    required_assignment_bindings: tuple[str, ...] = REQUIRED_ASSIGNMENT_BINDINGS_V2
    eligibility_rule: Literal["qualified_validity_report.valid_is_true"] = (
        "qualified_validity_report.valid_is_true"
    )
    trajectory_object_is_core_mapper_argument: Literal[True] = True
    trajectory_content_binding_required: Literal[True] = True
    raw_execution_artifact_binding_required: Literal[True] = True
    qualified_verifier_input_binding_required: Literal[True] = True
    support_exit_mapping_forbidden: Literal[True] = True
    instrument_failure_mapping_forbidden: Literal[True] = True
    privacy_rejection_mapping_forbidden: Literal[True] = True
    base_invalid_mapping_forbidden: Literal[True] = True
    mechanism_unqualified_mapping_forbidden: Literal[True] = True
    historical_v1_reclassification_forbidden: Literal[True] = True
    schema_version: str = VALID_ONLY_STATE_MAPPING_V2_VERSION

    @model_validator(mode="after")
    def validate_contract(self) -> ValidOnlyStateMapperContractV2:
        if self.required_assignment_bindings != REQUIRED_ASSIGNMENT_BINDINGS_V2:
            raise ValueError("valid-only v2 Mapping bindings are incomplete or noncanonical")
        if self.contract_id != _identity(
            self,
            "contract_id",
            "valid_only_state_mapper_contract_v2:",
        ):
            raise ValueError("valid-only v2 State Mapper Contract identity changed")
        return self


class ValidOnlyMappingAuthorizationV2(FrozenModel):
    authorization_id: str = Field(min_length=1)
    mapper_contract_id: str = Field(min_length=1)
    qualified_verifier_input_binding_id: str = Field(min_length=1)
    qualified_validity_report_id: str = Field(min_length=1)
    qualified_verifier_contract_id: str = Field(min_length=1)
    qualified_verifier_input_hash: str = Field(min_length=1)
    trajectory_id: str = Field(min_length=1)
    trajectory_semantic_content_hash: str = Field(min_length=1)
    trajectory_bound_artifact_hash: str = Field(min_length=1)
    raw_execution_artifact_hash: str = Field(min_length=1)
    omega_task_context_id: str = Field(min_length=1)
    raw_observation_prefix_hash: str = Field(min_length=1)
    qualified_validity: Literal[True] = True
    state_mapping_eligible: Literal[True] = True
    mapper_invocation_authorized: Literal[True] = True
    schema_version: str = VALID_ONLY_STATE_MAPPING_V2_VERSION

    @model_validator(mode="after")
    def validate_authorization(self) -> ValidOnlyMappingAuthorizationV2:
        if self.authorization_id != _identity(
            self,
            "authorization_id",
            "valid_only_state_mapping_authorization_v2:",
        ):
            raise ValueError("valid-only v2 Mapping authorization identity changed")
        return self


class ValidOnlyMappingResultV2(FrozenModel, Generic[MappedStateT]):
    result_id: str = Field(min_length=1)
    authorization: ValidOnlyMappingAuthorizationV2
    mapped_state: MappedStateT
    mapper_invocation_count: Literal[1] = 1
    trajectory_passed_to_mapper_by_core: Literal[True] = True
    host_state_insertion: Literal[False] = False
    schema_version: str = VALID_ONLY_STATE_MAPPING_V2_VERSION

    @model_validator(mode="after")
    def validate_result(self) -> ValidOnlyMappingResultV2[MappedStateT]:
        if self.result_id != _identity(
            self,
            "result_id",
            "valid_only_state_mapping_result_v2:",
        ):
            raise ValueError("valid-only v2 Mapping result identity changed")
        return self


def make_qualified_verifier_input_binding_v2(
    *,
    trajectory: ContentAddressedTrajectoryV2,
    qualified_validity_report: QualifiedTrajectoryValidityReport,
    raw_execution_artifact_hash: str,
    qualified_verifier_input_hash: str,
) -> QualifiedVerifierInputBindingV2:
    if qualified_validity_report.trajectory_id != trajectory.trajectory_id:
        raise ValueError("Qualified Verifier input binding crossed trajectories")
    values = {
        "qualified_validity_report_id": qualified_validity_report.report_id,
        "qualified_verifier_contract_id": qualified_validity_report.verifier_contract_id,
        "trajectory_id": trajectory.trajectory_id,
        "trajectory_semantic_content_hash": trajectory.trajectory_semantic_content_hash,
        "trajectory_bound_artifact_hash": trajectory.trajectory_bound_artifact_hash,
        "raw_execution_artifact_hash": raw_execution_artifact_hash,
        "qualified_verifier_input_hash": qualified_verifier_input_hash,
    }
    provisional = QualifiedVerifierInputBindingV2.model_construct(binding_id="pending", **values)
    return QualifiedVerifierInputBindingV2(
        binding_id=_identity(
            provisional,
            "binding_id",
            "qualified_verifier_input_binding:",
        ),
        **values,
    )


def make_valid_only_state_mapper_contract_v2(
    *,
    qualified_verifier_contract_id: str,
    mapper_implementation_id: str,
    semantic_policy_id: str,
) -> ValidOnlyStateMapperContractV2:
    values = {
        "qualified_verifier_contract_id": qualified_verifier_contract_id,
        "mapper_implementation_id": mapper_implementation_id,
        "semantic_policy_id": semantic_policy_id,
    }
    provisional = ValidOnlyStateMapperContractV2.model_construct(
        contract_id="pending",
        **values,
    )
    return ValidOnlyStateMapperContractV2(
        contract_id=_identity(
            provisional,
            "contract_id",
            "valid_only_state_mapper_contract_v2:",
        ),
        **values,
    )


def authorize_independently_valid_trajectory_mapping_v2(
    *,
    trajectory: ContentAddressedTrajectoryV2,
    qualified_validity_report: QualifiedTrajectoryValidityReport,
    verifier_input_binding: QualifiedVerifierInputBindingV2,
    mapper_contract: ValidOnlyStateMapperContractV2,
    omega_task_context_id: str,
    raw_execution_artifact_hash: str,
) -> ValidOnlyMappingAuthorizationV2:
    if qualified_validity_report.trajectory_id != trajectory.trajectory_id:
        raise ValueError("valid-only v2 Mapper received another trajectory's validity report")
    if (
        qualified_validity_report.verifier_contract_id
        != mapper_contract.qualified_verifier_contract_id
    ):
        raise ValueError("valid-only v2 Mapper crossed Verifier Contracts")
    if (
        qualified_validity_report.valid is not True
        or not qualified_validity_report.state_mapping_eligible
    ):
        raise ValueError("valid-only v2 Mapper rejected a non-Qualified trajectory")
    expected = {
        "qualified_validity_report_id": qualified_validity_report.report_id,
        "qualified_verifier_contract_id": qualified_validity_report.verifier_contract_id,
        "trajectory_id": trajectory.trajectory_id,
        "trajectory_semantic_content_hash": trajectory.trajectory_semantic_content_hash,
        "trajectory_bound_artifact_hash": trajectory.trajectory_bound_artifact_hash,
        "raw_execution_artifact_hash": raw_execution_artifact_hash,
    }
    observed = verifier_input_binding.model_dump(mode="python", include=set(expected))
    if observed != expected:
        raise ValueError("valid-only v2 Mapper rejected a crossed trajectory content binding")
    values = {
        "mapper_contract_id": mapper_contract.contract_id,
        "qualified_verifier_input_binding_id": verifier_input_binding.binding_id,
        "qualified_validity_report_id": qualified_validity_report.report_id,
        "qualified_verifier_contract_id": qualified_validity_report.verifier_contract_id,
        "qualified_verifier_input_hash": verifier_input_binding.qualified_verifier_input_hash,
        "trajectory_id": trajectory.trajectory_id,
        "trajectory_semantic_content_hash": trajectory.trajectory_semantic_content_hash,
        "trajectory_bound_artifact_hash": trajectory.trajectory_bound_artifact_hash,
        "raw_execution_artifact_hash": raw_execution_artifact_hash,
        "omega_task_context_id": omega_task_context_id,
        "raw_observation_prefix_hash": trajectory.raw_observation_prefix_hash,
    }
    provisional = ValidOnlyMappingAuthorizationV2.model_construct(
        authorization_id="pending",
        **values,
    )
    return ValidOnlyMappingAuthorizationV2(
        authorization_id=_identity(
            provisional,
            "authorization_id",
            "valid_only_state_mapping_authorization_v2:",
        ),
        **values,
    )


def map_independently_valid_trajectory_to_state_v2(
    *,
    trajectory: TrajectoryT,
    qualified_validity_report: QualifiedTrajectoryValidityReport,
    verifier_input_binding: QualifiedVerifierInputBindingV2,
    mapper_contract: ValidOnlyStateMapperContractV2,
    omega_task_context_id: str,
    raw_execution_artifact_hash: str,
    mapper: Callable[[ValidOnlyMappingAuthorizationV2, TrajectoryT], MappedStateT],
) -> ValidOnlyMappingResultV2[MappedStateT]:
    authorization = authorize_independently_valid_trajectory_mapping_v2(
        trajectory=trajectory,
        qualified_validity_report=qualified_validity_report,
        verifier_input_binding=verifier_input_binding,
        mapper_contract=mapper_contract,
        omega_task_context_id=omega_task_context_id,
        raw_execution_artifact_hash=raw_execution_artifact_hash,
    )
    mapped_state = mapper(authorization, trajectory)
    values = {"authorization": authorization, "mapped_state": mapped_state}
    provisional = ValidOnlyMappingResultV2[MappedStateT].model_construct(
        result_id="pending",
        **values,
    )
    return ValidOnlyMappingResultV2[MappedStateT](
        result_id=_identity(
            provisional,
            "result_id",
            "valid_only_state_mapping_result_v2:",
        ),
        **values,
    )
