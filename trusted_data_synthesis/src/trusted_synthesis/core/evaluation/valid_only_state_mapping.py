from __future__ import annotations

from collections.abc import Callable
from typing import Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.core.evaluation.trajectory_validity import (
    QualifiedTrajectoryValidityReport,
)
from trusted_synthesis.hashing import canonical_hash

VALID_ONLY_STATE_MAPPING_VERSION = "valid_only_state_mapping.v1"
REQUIRED_ASSIGNMENT_BINDINGS = (
    "mapper_contract_id",
    "omega_task_context_id",
    "qualified_validity_report_id",
    "raw_observation_prefix_hash",
    "route_condition_id",
    "static_path_catalog_id",
    "structural_state_id",
    "trajectory_content_hash",
)

MappedStateT = TypeVar("MappedStateT")


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


def _identity(value: BaseModel, field: str, prefix: str) -> str:
    return canonical_hash(value.model_dump(mode="json", exclude={field}), prefix=prefix)


class ValidOnlyStateMapperContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    qualified_verifier_contract_id: str = Field(min_length=1)
    mapper_implementation_id: str = Field(min_length=1)
    mapper_version: str = Field(min_length=1)
    required_assignment_bindings: tuple[str, ...] = REQUIRED_ASSIGNMENT_BINDINGS
    eligibility_rule: Literal["qualified_validity_report.valid_is_true"] = (
        "qualified_validity_report.valid_is_true"
    )
    support_exit_mapping_forbidden: Literal[True] = True
    instrument_failure_mapping_forbidden: Literal[True] = True
    privacy_rejection_mapping_forbidden: Literal[True] = True
    base_invalid_mapping_forbidden: Literal[True] = True
    mechanism_unqualified_mapping_forbidden: Literal[True] = True
    static_route_is_not_empirical_state: Literal[True] = True
    schema_version: str = VALID_ONLY_STATE_MAPPING_VERSION

    @model_validator(mode="after")
    def validate_contract(self) -> ValidOnlyStateMapperContract:
        if self.required_assignment_bindings != REQUIRED_ASSIGNMENT_BINDINGS:
            raise ValueError("valid-only Mapping bindings are incomplete or noncanonical")
        if self.contract_id != _identity(
            self,
            "contract_id",
            "valid_only_state_mapper_contract:",
        ):
            raise ValueError("valid-only State Mapper Contract identity is invalid")
        return self


class ValidOnlyMappingAuthorization(FrozenModel):
    authorization_id: str = Field(min_length=1)
    mapper_contract_id: str = Field(min_length=1)
    qualified_validity_report_id: str = Field(min_length=1)
    qualified_verifier_contract_id: str = Field(min_length=1)
    trajectory_id: str = Field(min_length=1)
    omega_task_context_id: str = Field(min_length=1)
    raw_observation_prefix_hash: str = Field(min_length=1)
    qualified_validity: Literal[True] = True
    state_mapping_eligible: Literal[True] = True
    mapper_invocation_authorized: Literal[True] = True
    schema_version: str = VALID_ONLY_STATE_MAPPING_VERSION

    @model_validator(mode="after")
    def validate_authorization(self) -> ValidOnlyMappingAuthorization:
        if self.authorization_id != _identity(
            self,
            "authorization_id",
            "valid_only_state_mapping_authorization:",
        ):
            raise ValueError("valid-only Mapping authorization identity is invalid")
        return self


class ValidOnlyMappingResult(FrozenModel, Generic[MappedStateT]):
    result_id: str = Field(min_length=1)
    authorization: ValidOnlyMappingAuthorization
    mapped_state: MappedStateT
    mapper_invocation_count: Literal[1] = 1
    host_state_insertion: Literal[False] = False
    schema_version: str = VALID_ONLY_STATE_MAPPING_VERSION

    @model_validator(mode="after")
    def validate_result(self) -> ValidOnlyMappingResult[MappedStateT]:
        if self.result_id != _identity(
            self,
            "result_id",
            "valid_only_state_mapping_result:",
        ):
            raise ValueError("valid-only Mapping result identity is invalid")
        return self


def make_valid_only_state_mapper_contract(
    *,
    qualified_verifier_contract_id: str,
    mapper_implementation_id: str,
    mapper_version: str,
) -> ValidOnlyStateMapperContract:
    values = {
        "qualified_verifier_contract_id": qualified_verifier_contract_id,
        "mapper_implementation_id": mapper_implementation_id,
        "mapper_version": mapper_version,
    }
    provisional = ValidOnlyStateMapperContract.model_construct(
        contract_id="pending",
        **values,
    )
    return ValidOnlyStateMapperContract(
        contract_id=_identity(
            provisional,
            "contract_id",
            "valid_only_state_mapper_contract:",
        ),
        **values,
    )


def authorize_independently_valid_trajectory_mapping(
    *,
    trajectory_id: str,
    qualified_validity_report: QualifiedTrajectoryValidityReport,
    mapper_contract: ValidOnlyStateMapperContract,
    omega_task_context_id: str,
    raw_observation_prefix_hash: str,
) -> ValidOnlyMappingAuthorization:
    if qualified_validity_report.trajectory_id != trajectory_id:
        raise ValueError("valid-only Mapper received another trajectory's validity report")
    if (
        qualified_validity_report.verifier_contract_id
        != mapper_contract.qualified_verifier_contract_id
    ):
        raise ValueError("valid-only Mapper crossed Verifier Contracts")
    if (
        qualified_validity_report.valid is not True
        or not qualified_validity_report.state_mapping_eligible
    ):
        raise ValueError("valid-only Mapper rejected a non-Qualified trajectory")
    values = {
        "mapper_contract_id": mapper_contract.contract_id,
        "qualified_validity_report_id": qualified_validity_report.report_id,
        "qualified_verifier_contract_id": qualified_validity_report.verifier_contract_id,
        "trajectory_id": trajectory_id,
        "omega_task_context_id": omega_task_context_id,
        "raw_observation_prefix_hash": raw_observation_prefix_hash,
    }
    provisional = ValidOnlyMappingAuthorization.model_construct(
        authorization_id="pending",
        **values,
    )
    return ValidOnlyMappingAuthorization(
        authorization_id=_identity(
            provisional,
            "authorization_id",
            "valid_only_state_mapping_authorization:",
        ),
        **values,
    )


def map_independently_valid_trajectory_to_state(
    *,
    trajectory_id: str,
    qualified_validity_report: QualifiedTrajectoryValidityReport,
    mapper_contract: ValidOnlyStateMapperContract,
    omega_task_context_id: str,
    raw_observation_prefix_hash: str,
    mapper: Callable[[ValidOnlyMappingAuthorization], MappedStateT],
) -> ValidOnlyMappingResult[MappedStateT]:
    authorization = authorize_independently_valid_trajectory_mapping(
        trajectory_id=trajectory_id,
        qualified_validity_report=qualified_validity_report,
        mapper_contract=mapper_contract,
        omega_task_context_id=omega_task_context_id,
        raw_observation_prefix_hash=raw_observation_prefix_hash,
    )
    mapped_state = mapper(authorization)
    values = {
        "authorization": authorization,
        "mapped_state": mapped_state,
    }
    provisional = ValidOnlyMappingResult[MappedStateT].model_construct(
        result_id="pending",
        **values,
    )
    return ValidOnlyMappingResult[MappedStateT](
        result_id=_identity(
            provisional,
            "result_id",
            "valid_only_state_mapping_result:",
        ),
        **values,
    )
