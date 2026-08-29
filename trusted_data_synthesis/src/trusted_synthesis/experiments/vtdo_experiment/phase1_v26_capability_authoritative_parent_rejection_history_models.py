from __future__ import annotations

from typing import Any, Final, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.core.task.capability_observation import (
    CapabilityFamily,
    ObservationDepth,
)
from trusted_synthesis.core.task.state_local_presentation_hardening import StepRuntimeResult
from trusted_synthesis.hashing import canonical_hash

V26_AUTHORITATIVE_PARENT_HISTORY_VERSION = "authoritative_parent_rejection_history.v1"
AUTHORIZED_STAGE: Final[
    Literal[
        "capability_observation_authoritative_package_runner_parent_"
        "and_typed_rejection_history_hardening_only"
    ]
] = (
    "capability_observation_authoritative_package_runner_parent_"
    "and_typed_rejection_history_hardening_only"
)
NEXT_STAGE: Final[
    Literal[
        "capability_observation_authoritative_parent_closed_rejection_history_"
        "state_bound_step_runtime_development_runner_preflight_only"
    ]
] = (
    "capability_observation_authoritative_parent_closed_rejection_history_"
    "state_bound_step_runtime_development_runner_preflight_only"
)


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


def identity(value: BaseModel, field: str, prefix: str) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={field}, warnings=False),
        prefix=prefix,
    )


def make_identity_model(
    model_type: type[BaseModel],
    values: dict[str, Any],
    *,
    field: str,
    prefix: str,
) -> Any:
    provisional = model_type.model_construct(**{field: "pending"}, **values)
    return model_type(**{field: identity(provisional, field, prefix)}, **values)


class FileBinding(FrozenModel):
    relative_path: str = Field(min_length=1)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    byte_count: int = Field(ge=1)
    source_kind: Literal[
        "external_audit_input",
        "implementation",
        "predecessor_artifact",
        "formal_output",
    ]


class ExternalAuditAuthorization(FrozenModel):
    authorization_id: str = Field(min_length=1)
    review_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    review_byte_count: int = Field(ge=1)
    authorized_stage: Literal[
        "capability_observation_authoritative_package_runner_parent_"
        "and_typed_rejection_history_hardening_only"
    ] = AUTHORIZED_STAGE
    provider_calls_authorized: Literal[False] = False
    development_jobs_authorized: Literal[False] = False
    confirmation_payload_access_authorized: Literal[False] = False
    schema_version: str = V26_AUTHORITATIVE_PARENT_HISTORY_VERSION

    @model_validator(mode="after")
    def validate_authorization(self) -> ExternalAuditAuthorization:
        if self.authorization_id != identity(
            self,
            "authorization_id",
            "finance_v26_authoritative_parent_history_external_authorization:",
        ):
            raise ValueError("v26.176 external Authorization identity is invalid")
        return self


class TransitiveSourceRoot(FrozenModel):
    root_id: str = Field(min_length=1)
    entry_modules: tuple[str, ...] = Field(min_length=4)
    files: tuple[FileBinding, ...] = Field(min_length=1)
    file_count: int = Field(ge=1)
    unresolved_import_count: Literal[0] = 0
    schema_version: str = V26_AUTHORITATIVE_PARENT_HISTORY_VERSION

    @model_validator(mode="after")
    def validate_root(self) -> TransitiveSourceRoot:
        if self.file_count != len(self.files):
            raise ValueError("v26.176 source Root file count changed")
        if len({item.relative_path for item in self.files}) != self.file_count:
            raise ValueError("v26.176 source Root repeats a file")
        if self.root_id != identity(
            self,
            "root_id",
            "finance_v26_authoritative_parent_history_transitive_source_root:",
        ):
            raise ValueError("v26.176 source Root identity is invalid")
        return self


class PredecessorFreezeAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    predecessor_report_id: str = Field(min_length=1)
    predecessor_catalog_id: str = Field(min_length=1)
    predecessor_runner_input_catalog_id: str = Field(min_length=1)
    predecessor_transition_id: str = Field(min_length=1)
    predecessor_files: tuple[FileBinding, ...] = Field(min_length=19, max_length=19)
    predecessor_file_count: Literal[19] = 19
    independent_rebuild_match_count: Literal[19] = 19
    predecessor_mutation_count: Literal[0] = 0
    stale_runner_transition_blocked: Literal[True] = True
    schema_version: str = V26_AUTHORITATIVE_PARENT_HISTORY_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> PredecessorFreezeAudit:
        if len(self.predecessor_files) != self.predecessor_file_count:
            raise ValueError("v26.175 predecessor Freeze denominator changed")
        if self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_v175_predecessor_freeze_audit:",
        ):
            raise ValueError("v26.175 predecessor Freeze identity is invalid")
        return self


class V175DefectReproductionAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    omitted_runner_inherited_contract_field_count: Literal[4] = 4
    accepted_runner_inherited_contract_attack_count: Literal[4] = 4
    accepted_development_public_task_attack_count: Literal[1] = 1
    accepted_development_inherited_contract_attack_count: Literal[4] = 4
    accepted_saved_replica_result_attack_count: Literal[1] = 1
    accepted_fully_rehashed_attack_count: Literal[10] = 10
    full_choice_combination_replica_count: Literal[1] = 1
    full_choice_combination_execution_count: Literal[772] = 772
    typed_rejection_feedback_persisted_count: Literal[0] = 0
    corrected_second_response_execution_count: Literal[0] = 0
    repeated_wrong_action_terminal_count: Literal[0] = 0
    stale_runner_transition_blocked: Literal[True] = True
    historical_reclassification_count: Literal[0] = 0
    schema_version: str = V26_AUTHORITATIVE_PARENT_HISTORY_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> V175DefectReproductionAudit:
        if self.accepted_fully_rehashed_attack_count != sum(
            (
                self.accepted_runner_inherited_contract_attack_count,
                self.accepted_development_public_task_attack_count,
                self.accepted_development_inherited_contract_attack_count,
                self.accepted_saved_replica_result_attack_count,
            )
        ):
            raise ValueError("v26.175 accepted-attack partition changed")
        if self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_v175_parent_history_defect_reproduction:",
        ):
            raise ValueError("v26.175 defect reproduction identity is invalid")
        return self


class AuthoritativePackageRunnerParentContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    authoritative_source_levels: tuple[str, ...] = (
        "v26.171_source_object",
        "v26.173_package_parent",
        "v26.174_package_and_contract_parents",
        "v26.175_schedule_and_package_parent",
    )
    development_metadata_fields: tuple[str, ...] = Field(min_length=20)
    runner_metadata_fields: tuple[str, ...] = Field(min_length=20)
    inherited_v174_contract_fields: tuple[str, ...] = (
        "mechanism_semantics_contract_id",
        "failure_receipt_contract_id",
        "step_runtime_contract_id",
        "sequential_estimand_contract_id",
    )
    exact_source_object_reconstruction_required: Literal[True] = True
    exact_authoritative_contract_ids_required: Literal[True] = True
    public_task_id_reconstruction_required: Literal[True] = True
    all_six_replica_results_fresh_replay_required: Literal[True] = True
    saved_result_as_replay_oracle_allowed: Literal[False] = False
    runner_exact_source_set_required: Literal[True] = True
    fully_rehashed_attack_must_fail: Literal[True] = True
    schema_version: str = V26_AUTHORITATIVE_PARENT_HISTORY_VERSION

    @model_validator(mode="after")
    def validate_contract(self) -> AuthoritativePackageRunnerParentContract:
        if len(set(self.development_metadata_fields)) != len(self.development_metadata_fields):
            raise ValueError("Authoritative Parent Contract repeats a Development field")
        if len(set(self.runner_metadata_fields)) != len(self.runner_metadata_fields):
            raise ValueError("Authoritative Parent Contract repeats a Runner field")
        if self.contract_id != identity(
            self,
            "contract_id",
            "authoritative_package_runner_parent_contract:",
        ):
            raise ValueError("Authoritative Package/Runner Parent Contract identity is invalid")
        return self


class TypedRejectionHistoryContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    model_visible_feedback_fields: tuple[str, ...] = (
        "feedback_id",
        "component_key",
        "rejected_action_id",
        "rejected_choice_handle",
        "selected_operation_hash",
        "rejection_code",
        "observation_receipt_id",
        "action_acceptance_report_id",
        "predecessor_feedback_id",
        "corrected_response_attempt_index",
        "corrected_response_attempt_bound",
    )
    corrected_response_attempt_bound: Literal[1] = 1
    first_rejection_must_parent_next_public_state: Literal[True] = True
    corrected_response_must_execute_production_step: Literal[True] = True
    repeated_wrong_action_must_emit_typed_terminal: Literal[True] = True
    later_prompt_after_terminal_allowed: Literal[False] = False
    rejection_retry_delta_required: Literal[0] = 0
    rejection_tool_call_delta_required: Literal[0] = 0
    rejection_component_advance_allowed: Literal[False] = False
    all_six_replicas_required: Literal[True] = True
    schedule_metadata_model_visible_allowed: Literal[False] = False
    schema_version: str = V26_AUTHORITATIVE_PARENT_HISTORY_VERSION

    @model_validator(mode="after")
    def validate_contract(self) -> TypedRejectionHistoryContract:
        if len(set(self.model_visible_feedback_fields)) != len(self.model_visible_feedback_fields):
            raise ValueError("typed-rejection history Contract repeats a public field")
        if self.contract_id != identity(
            self,
            "contract_id",
            "typed_rejection_history_contract:",
        ):
            raise ValueError("typed-rejection history Contract identity is invalid")
        return self


class AuthoritativeDevelopmentPackage(FrozenModel):
    artifact_id: str = Field(min_length=1)
    source_v175_package_artifact_id: str = Field(min_length=1)
    package_id: str = Field(min_length=1)
    source_v174_package_artifact_id: str = Field(min_length=1)
    source_v173_package_artifact_id: str = Field(min_length=1)
    source_v171_package_artifact_id: str = Field(min_length=1)
    source_package_id: str = Field(min_length=1)
    source_group_id: str = Field(min_length=1)
    finance_core_id: str = Field(min_length=1)
    capability_family: CapabilityFamily
    depth: ObservationDepth
    public_task_id: str = Field(min_length=1)
    topological_component_keys: tuple[str, ...] = Field(min_length=1, max_length=4)
    reference_path_hash: str = Field(min_length=1)
    presentation_contract_id: str = Field(min_length=1)
    interaction_parent_receipt_contract_id: str = Field(min_length=1)
    schedule_catalog_id: str = Field(min_length=1)
    schedule_ids: tuple[str, ...] = Field(min_length=1, max_length=4)
    mechanism_semantics_contract_id: str = Field(min_length=1)
    failure_receipt_contract_id: str = Field(min_length=1)
    step_runtime_contract_id: str = Field(min_length=1)
    sequential_estimand_contract_id: str = Field(min_length=1)
    authoritative_parent_contract_id: str = Field(min_length=1)
    typed_rejection_history_contract_id: str = Field(min_length=1)
    replica_results: tuple[StepRuntimeResult, ...] = Field(min_length=6, max_length=6)
    provider_calls: Literal[0] = 0
    development_jobs: Literal[0] = 0
    schema_version: str = V26_AUTHORITATIVE_PARENT_HISTORY_VERSION

    @model_validator(mode="after")
    def validate_package(self) -> AuthoritativeDevelopmentPackage:
        if len(self.schedule_ids) != len(self.topological_component_keys):
            raise ValueError("Authoritative Development Schedule denominator changed")
        if tuple(item.replica_index for item in self.replica_results) != tuple(range(6)):
            raise ValueError("Authoritative Development does not contain ordered Replicas")
        if any(
            item.package_id != self.package_id
            or item.source_package_id != self.source_package_id
            or tuple(step.component_key for step in item.steps) != self.topological_component_keys
            or item.reference_path_hash != self.reference_path_hash
            or not item.qualified_validity.qualified_valid
            for item in self.replica_results
        ):
            raise ValueError("Authoritative Development Replica parents are inconsistent")
        if self.artifact_id != identity(
            self,
            "artifact_id",
            "finance_v26_authoritative_parent_history_package_artifact:",
        ):
            raise ValueError("Authoritative Development Package identity is invalid")
        return self


class AuthoritativeDevelopmentGroup(FrozenModel):
    group_id: str = Field(min_length=1)
    source_group_id: str = Field(min_length=1)
    finance_core_id: str = Field(min_length=1)
    capability_family: CapabilityFamily
    packages: tuple[AuthoritativeDevelopmentPackage, ...] = Field(min_length=4, max_length=4)
    schema_version: str = V26_AUTHORITATIVE_PARENT_HISTORY_VERSION

    @model_validator(mode="after")
    def validate_group(self) -> AuthoritativeDevelopmentGroup:
        if tuple(item.depth for item in self.packages) != tuple(ObservationDepth):
            raise ValueError("Authoritative Development Group does not contain D0-D3")
        if any(
            item.source_group_id != self.source_group_id
            or item.finance_core_id != self.finance_core_id
            or item.capability_family != self.capability_family
            for item in self.packages
        ):
            raise ValueError("Authoritative Development Group crosses a source parent")
        if self.group_id != identity(
            self,
            "group_id",
            "finance_v26_authoritative_parent_history_group:",
        ):
            raise ValueError("Authoritative Development Group identity is invalid")
        return self


class AuthoritativeDevelopmentCatalog(FrozenModel):
    catalog_id: str = Field(min_length=1)
    source_v175_catalog_id: str = Field(min_length=1)
    source_v174_catalog_id: str = Field(min_length=1)
    source_v173_catalog_id: str = Field(min_length=1)
    source_v171_catalog_id: str = Field(min_length=1)
    presentation_contract_id: str = Field(min_length=1)
    interaction_parent_receipt_contract_id: str = Field(min_length=1)
    schedule_catalog_id: str = Field(min_length=1)
    mechanism_semantics_contract_id: str = Field(min_length=1)
    failure_receipt_contract_id: str = Field(min_length=1)
    step_runtime_contract_id: str = Field(min_length=1)
    sequential_estimand_contract_id: str = Field(min_length=1)
    authoritative_parent_contract_id: str = Field(min_length=1)
    typed_rejection_history_contract_id: str = Field(min_length=1)
    groups: tuple[AuthoritativeDevelopmentGroup, ...] = Field(min_length=8, max_length=8)
    group_count: Literal[8] = 8
    package_count: Literal[32] = 32
    replica_result_count: Literal[192] = 192
    provider_calls: Literal[0] = 0
    development_jobs: Literal[0] = 0
    confirmation_payload_access_count: Literal[0] = 0
    schema_version: str = V26_AUTHORITATIVE_PARENT_HISTORY_VERSION

    @model_validator(mode="after")
    def validate_catalog(self) -> AuthoritativeDevelopmentCatalog:
        packages = tuple(item for group in self.groups for item in group.packages)
        if len(packages) != self.package_count:
            raise ValueError("Authoritative Development Package denominator changed")
        if sum(len(item.replica_results) for item in packages) != self.replica_result_count:
            raise ValueError("Authoritative Development Replica denominator changed")
        for field_name in (
            "artifact_id",
            "source_v175_package_artifact_id",
            "package_id",
            "source_v174_package_artifact_id",
            "source_v173_package_artifact_id",
            "source_v171_package_artifact_id",
            "source_package_id",
        ):
            values = tuple(getattr(item, field_name) for item in packages)
            if len(values) != len(set(values)):
                raise ValueError(f"Authoritative Development repeats a parent:{field_name}")
        expected = {
            "presentation_contract_id": self.presentation_contract_id,
            "interaction_parent_receipt_contract_id": (self.interaction_parent_receipt_contract_id),
            "schedule_catalog_id": self.schedule_catalog_id,
            "mechanism_semantics_contract_id": self.mechanism_semantics_contract_id,
            "failure_receipt_contract_id": self.failure_receipt_contract_id,
            "step_runtime_contract_id": self.step_runtime_contract_id,
            "sequential_estimand_contract_id": self.sequential_estimand_contract_id,
            "authoritative_parent_contract_id": self.authoritative_parent_contract_id,
            "typed_rejection_history_contract_id": self.typed_rejection_history_contract_id,
        }
        if any(
            getattr(package, field_name) != expected_value
            for package in packages
            for field_name, expected_value in expected.items()
        ):
            raise ValueError("Authoritative Development Package crosses a Contract")
        if self.catalog_id != identity(
            self,
            "catalog_id",
            "finance_v26_authoritative_parent_history_development_catalog:",
        ):
            raise ValueError("Authoritative Development Catalog identity is invalid")
        return self


class AuthoritativeRunnerInputPackage(FrozenModel):
    runner_package_id: str = Field(min_length=1)
    source_development_package_artifact_id: str = Field(min_length=1)
    source_v175_package_artifact_id: str = Field(min_length=1)
    package_id: str = Field(min_length=1)
    source_v174_package_artifact_id: str = Field(min_length=1)
    source_v173_package_artifact_id: str = Field(min_length=1)
    source_v171_package_artifact_id: str = Field(min_length=1)
    source_package_id: str = Field(min_length=1)
    source_group_id: str = Field(min_length=1)
    finance_core_id: str = Field(min_length=1)
    capability_family: CapabilityFamily
    depth: ObservationDepth
    public_task_id: str = Field(min_length=1)
    topological_component_keys: tuple[str, ...] = Field(min_length=1, max_length=4)
    reference_path_hash: str = Field(min_length=1)
    presentation_contract_id: str = Field(min_length=1)
    interaction_parent_receipt_contract_id: str = Field(min_length=1)
    schedule_catalog_id: str = Field(min_length=1)
    schedule_ids: tuple[str, ...] = Field(min_length=1, max_length=4)
    mechanism_semantics_contract_id: str = Field(min_length=1)
    failure_receipt_contract_id: str = Field(min_length=1)
    step_runtime_contract_id: str = Field(min_length=1)
    sequential_estimand_contract_id: str = Field(min_length=1)
    authoritative_parent_contract_id: str = Field(min_length=1)
    typed_rejection_history_contract_id: str = Field(min_length=1)
    materialized_prompt_count: Literal[0] = 0
    materialized_observation_count: Literal[0] = 0
    reference_trace_payload_accessible: Literal[False] = False
    precommitted_choice_vector_allowed: Literal[False] = False
    schema_version: str = V26_AUTHORITATIVE_PARENT_HISTORY_VERSION

    @model_validator(mode="after")
    def validate_package(self) -> AuthoritativeRunnerInputPackage:
        forbidden = {"prompts", "observations", "replica_results", "steps", "traces"}
        if set(type(self).model_fields) & forbidden:
            raise ValueError("Authoritative Runner Input exposes a dynamic payload")
        if len(self.schedule_ids) != len(self.topological_component_keys):
            raise ValueError("Authoritative Runner Input Schedule denominator changed")
        if self.runner_package_id != identity(
            self,
            "runner_package_id",
            "finance_v26_authoritative_parent_history_runner_input_package:",
        ):
            raise ValueError("Authoritative Runner Input Package identity is invalid")
        return self


class AuthoritativeRunnerInputCatalog(FrozenModel):
    catalog_id: str = Field(min_length=1)
    source_development_catalog_id: str = Field(min_length=1)
    presentation_contract_id: str = Field(min_length=1)
    interaction_parent_receipt_contract_id: str = Field(min_length=1)
    schedule_catalog_id: str = Field(min_length=1)
    mechanism_semantics_contract_id: str = Field(min_length=1)
    failure_receipt_contract_id: str = Field(min_length=1)
    step_runtime_contract_id: str = Field(min_length=1)
    sequential_estimand_contract_id: str = Field(min_length=1)
    authoritative_parent_contract_id: str = Field(min_length=1)
    typed_rejection_history_contract_id: str = Field(min_length=1)
    expected_source_artifact_ids: tuple[str, ...] = Field(min_length=32, max_length=32)
    expected_source_package_ids: tuple[str, ...] = Field(min_length=32, max_length=32)
    packages: tuple[AuthoritativeRunnerInputPackage, ...] = Field(min_length=32, max_length=32)
    package_count: Literal[32] = 32
    future_job_count: Literal[192] = 192
    materialized_prompt_count: Literal[0] = 0
    materialized_observation_count: Literal[0] = 0
    provider_calls: Literal[0] = 0
    development_jobs: Literal[0] = 0
    schema_version: str = V26_AUTHORITATIVE_PARENT_HISTORY_VERSION

    @model_validator(mode="after")
    def validate_catalog(self) -> AuthoritativeRunnerInputCatalog:
        if len(self.packages) != self.package_count:
            raise ValueError("Authoritative Runner Input denominator changed")
        runner_ids = tuple(item.runner_package_id for item in self.packages)
        source_artifacts = tuple(
            item.source_development_package_artifact_id for item in self.packages
        )
        source_ids = tuple(item.source_package_id for item in self.packages)
        if len(set(runner_ids)) != self.package_count:
            raise ValueError("Authoritative Runner Input repeats a Runner Package")
        if len(set(source_artifacts)) != self.package_count or len(set(source_ids)) != 32:
            raise ValueError("Authoritative Runner Input repeats a source Package")
        if set(source_artifacts) != set(self.expected_source_artifact_ids):
            raise ValueError("Authoritative Runner Input source artifact set changed")
        if set(source_ids) != set(self.expected_source_package_ids):
            raise ValueError("Authoritative Runner Input source Package set changed")
        expected = {
            "presentation_contract_id": self.presentation_contract_id,
            "interaction_parent_receipt_contract_id": (self.interaction_parent_receipt_contract_id),
            "schedule_catalog_id": self.schedule_catalog_id,
            "mechanism_semantics_contract_id": self.mechanism_semantics_contract_id,
            "failure_receipt_contract_id": self.failure_receipt_contract_id,
            "step_runtime_contract_id": self.step_runtime_contract_id,
            "sequential_estimand_contract_id": self.sequential_estimand_contract_id,
            "authoritative_parent_contract_id": self.authoritative_parent_contract_id,
            "typed_rejection_history_contract_id": self.typed_rejection_history_contract_id,
        }
        if any(
            getattr(package, field_name) != expected_value
            for package in self.packages
            for field_name, expected_value in expected.items()
        ):
            raise ValueError("Authoritative Runner Input crosses a Contract")
        if self.catalog_id != identity(
            self,
            "catalog_id",
            "finance_v26_authoritative_parent_history_runner_input_catalog:",
        ):
            raise ValueError("Authoritative Runner Input Catalog identity is invalid")
        return self


class MutationResult(FrozenModel):
    mutation: str = Field(min_length=1)
    surface: Literal[
        "development_parent",
        "runner_parent",
        "saved_replica_result",
        "typed_rejection_history",
        "runner_denominator",
    ]
    fully_rehashed: Literal[True] = True
    rejected: Literal[True] = True
    error_code: str = Field(min_length=1)


class AuthoritativeParentReconstructionAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    development_package_match_count: Literal[32] = 32
    development_metadata_field_match_count: int = Field(ge=640)
    inherited_contract_package_match_count: Literal[128] = 128
    fresh_replica_replay_count: Literal[192] = 192
    fresh_replica_byte_match_count: Literal[192] = 192
    runner_package_match_count: Literal[32] = 32
    runner_metadata_field_match_count: int = Field(ge=640)
    runner_inherited_contract_match_count: Literal[128] = 128
    runner_missing_count: Literal[0] = 0
    runner_duplicate_count: Literal[0] = 0
    runner_extra_count: Literal[0] = 0
    mutations: tuple[MutationResult, ...] = Field(min_length=20)
    mutation_count: int = Field(ge=20)
    rejection_count: int = Field(ge=20)
    accepted_mutation_count: Literal[0] = 0
    schema_version: str = V26_AUTHORITATIVE_PARENT_HISTORY_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> AuthoritativeParentReconstructionAudit:
        if self.mutation_count != len(self.mutations):
            raise ValueError("Authoritative Parent mutation denominator changed")
        if self.rejection_count != self.mutation_count:
            raise ValueError("Authoritative Parent reconstruction accepted a mutation")
        if self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_authoritative_parent_reconstruction_audit:",
        ):
            raise ValueError("Authoritative Parent Reconstruction Audit identity is invalid")
        return self


class ReplicaTrajectoryOutcome(FrozenModel):
    execution_id: str = Field(min_length=1)
    package_artifact_id: str = Field(min_length=1)
    package_id: str = Field(min_length=1)
    replica_index: int = Field(ge=0, le=5)
    selected_source_choice_handles: tuple[str, ...] = Field(min_length=1, max_length=4)
    nonreference_choice_count: int = Field(ge=0, le=4)
    attempted_component_count: int = Field(ge=1, le=4)
    committed_component_count: int = Field(ge=0, le=4)
    all_actions_accepted: bool
    typed_rejection: bool
    first_failed_component_key: str | None = None
    dependency_receipt_consistent: Literal[True] = True
    exact_failure_receipt_consistent: Literal[True] = True
    display_source_roundtrip_passed: Literal[True] = True
    base_valid: bool | None = None
    mechanism_semantically_qualified: bool | None = None
    qualified_valid: bool | None = None
    reference_path_match: bool | None = None
    semantic_outcome_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    schema_version: str = V26_AUTHORITATIVE_PARENT_HISTORY_VERSION

    @model_validator(mode="after")
    def validate_outcome(self) -> ReplicaTrajectoryOutcome:
        if self.all_actions_accepted == self.typed_rejection:
            raise ValueError("Replica trajectory terminal partition is inconsistent")
        if self.all_actions_accepted:
            if self.qualified_valid != (
                bool(self.base_valid) and bool(self.mechanism_semantically_qualified)
            ):
                raise ValueError("Replica trajectory Qualified conjunction changed")
        elif any(
            item is not None
            for item in (
                self.base_valid,
                self.mechanism_semantically_qualified,
                self.qualified_valid,
                self.reference_path_match,
            )
        ):
            raise ValueError("typed-rejected trajectory contains terminal validity")
        if self.execution_id != identity(
            self,
            "execution_id",
            "all_replica_trajectory_outcome:",
        ):
            raise ValueError("all-Replica trajectory outcome identity is invalid")
        return self


class AllReplicaTrajectoryAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    outcomes: tuple[ReplicaTrajectoryOutcome, ...] = Field(min_length=4632, max_length=4632)
    package_count: Literal[32] = 32
    replica_count: Literal[6] = 6
    declared_combination_count_per_replica: Literal[772] = 772
    execution_count: Literal[4632] = 4632
    reference_execution_count: Literal[192] = 192
    single_nonreference_execution_count: Literal[876] = 876
    multi_nonreference_execution_count: Literal[3564] = 3564
    fully_accepted_execution_count: int = Field(ge=1)
    typed_rejected_execution_count: int = Field(ge=1)
    base_valid_count: int = Field(ge=1)
    mechanism_semantically_qualified_count: int = Field(ge=1)
    qualified_valid_count: int = Field(ge=1)
    semantic_outcome_replica_mismatch_count: Literal[0] = 0
    dependency_receipt_failure_count: Literal[0] = 0
    exact_failure_receipt_failure_count: Literal[0] = 0
    display_source_roundtrip_failure_count: Literal[0] = 0
    qualified_conjunction_mismatch_count: Literal[0] = 0
    runtime_exception_count: Literal[0] = 0
    schema_version: str = V26_AUTHORITATIVE_PARENT_HISTORY_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> AllReplicaTrajectoryAudit:
        if len(self.outcomes) != self.execution_count:
            raise ValueError("all-Replica trajectory denominator changed")
        if (
            self.fully_accepted_execution_count + self.typed_rejected_execution_count
            != self.execution_count
        ):
            raise ValueError("all-Replica trajectory terminal partition changed")
        if self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_all_replica_trajectory_audit:",
        ):
            raise ValueError("all-Replica Trajectory Audit identity is invalid")
        return self


class TypedRejectionRecoveryRow(FrozenModel):
    row_id: str = Field(min_length=1)
    package_artifact_id: str = Field(min_length=1)
    package_id: str = Field(min_length=1)
    component_key: str = Field(min_length=1)
    replica_index: int = Field(ge=0, le=5)
    rejected_action_id: str = Field(min_length=1)
    first_rejection_observation_id: str = Field(min_length=1)
    first_rejection_acceptance_id: str = Field(min_length=1)
    first_feedback_id: str = Field(min_length=1)
    recovery_prompt_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    recovery_prompt_parent_match: Literal[True] = True
    recovery_prompt_attempt_index: Literal[1] = 1
    initial_rejection_retry_delta: Literal[0] = 0
    initial_rejection_tool_call_delta: Literal[0] = 0
    initial_rejection_component_advance: Literal[False] = False
    corrected_action_accepted: Literal[True] = True
    corrected_action_component_advance: Literal[True] = True
    corrected_final_result_id: str = Field(min_length=1)
    corrected_final_qualified: Literal[True] = True
    repeated_wrong_second_feedback_id: str = Field(min_length=1)
    repeated_wrong_typed_rejected: Literal[True] = True
    repeated_wrong_retry_delta: Literal[0] = 0
    repeated_wrong_tool_call_delta: Literal[0] = 0
    repeated_wrong_component_advance: Literal[False] = False
    repeated_wrong_terminal_emitted: Literal[True] = True
    later_prompt_blocked: Literal[True] = True
    hidden_parent_exposure_count: Literal[0] = 0
    schema_version: str = V26_AUTHORITATIVE_PARENT_HISTORY_VERSION

    @model_validator(mode="after")
    def validate_row(self) -> TypedRejectionRecoveryRow:
        if self.row_id != identity(
            self,
            "row_id",
            "typed_rejection_recovery_row:",
        ):
            raise ValueError("typed-rejection recovery row identity is invalid")
        return self


class TypedRejectionRecoveryAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    rows: tuple[TypedRejectionRecoveryRow, ...] = Field(min_length=120, max_length=120)
    recovery_component_count: Literal[20] = 20
    replica_count: Literal[6] = 6
    corrected_second_response_execution_count: Literal[120] = 120
    corrected_final_qualified_count: Literal[120] = 120
    repeated_wrong_action_execution_count: Literal[120] = 120
    repeated_wrong_typed_terminal_count: Literal[120] = 120
    model_visible_feedback_parent_match_count: Literal[120] = 120
    later_prompt_after_terminal_count: Literal[0] = 0
    rejection_retry_invocation_count: Literal[0] = 0
    rejection_tool_call_count: Literal[0] = 0
    rejection_component_advance_count: Literal[0] = 0
    hidden_parent_exposure_count: Literal[0] = 0
    provider_calls: Literal[0] = 0
    development_jobs: Literal[0] = 0
    schema_version: str = V26_AUTHORITATIVE_PARENT_HISTORY_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> TypedRejectionRecoveryAudit:
        if len(self.rows) != self.corrected_second_response_execution_count:
            raise ValueError("typed-rejection recovery denominator changed")
        if self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_typed_rejection_recovery_audit:",
        ):
            raise ValueError("typed-rejection Recovery Audit identity is invalid")
        return self


class ProductionDestructiveAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    mutations: tuple[MutationResult, ...] = Field(min_length=25)
    mutation_count: int = Field(ge=25)
    rejection_count: int = Field(ge=25)
    acceptance_count: Literal[0] = 0
    schema_version: str = V26_AUTHORITATIVE_PARENT_HISTORY_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> ProductionDestructiveAudit:
        if self.mutation_count != len(self.mutations):
            raise ValueError("v26.176 destructive denominator changed")
        if self.rejection_count != self.mutation_count:
            raise ValueError("v26.176 destructive mutation was accepted")
        if self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_authoritative_parent_history_destructive_audit:",
        ):
            raise ValueError("v26.176 Production Destructive Audit identity is invalid")
        return self


class StaticGate(FrozenModel):
    gate: str = Field(min_length=1)
    passed: Literal[True] = True
    observed: int | bool | str
    required: int | bool | str


class StaticAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    gates: tuple[StaticGate, ...] = Field(min_length=20)
    gate_count: int = Field(ge=20)
    passed_gate_count: int = Field(ge=20)
    failed_gate_count: Literal[0] = 0
    provider_calls: Literal[0] = 0
    stage_2_provider_calls: Literal[0] = 0
    development_jobs: Literal[0] = 0
    confirmation_payload_access_count: Literal[0] = 0
    mapper_call_count: Literal[0] = 0
    state_assignment_count: Literal[0] = 0
    frequency_row_count: Literal[0] = 0
    schema_version: str = V26_AUTHORITATIVE_PARENT_HISTORY_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> StaticAudit:
        if self.gate_count != len(self.gates) or self.passed_gate_count != self.gate_count:
            raise ValueError("v26.176 Static Gate denominator changed")
        if self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_authoritative_parent_history_static_audit:",
        ):
            raise ValueError("v26.176 Static Audit identity is invalid")
        return self


class ProspectiveTransition(FrozenModel):
    transition_id: str = Field(min_length=1)
    predecessor_transition_id: str = Field(min_length=1)
    development_catalog_id: str = Field(min_length=1)
    runner_input_catalog_id: str = Field(min_length=1)
    parent_reconstruction_audit_id: str = Field(min_length=1)
    typed_rejection_recovery_audit_id: str = Field(min_length=1)
    all_replica_trajectory_audit_id: str = Field(min_length=1)
    static_audit_id: str = Field(min_length=1)
    blocked_predecessor_stage: str = Field(min_length=1)
    consumed_stage: Literal[
        "capability_observation_authoritative_package_runner_parent_"
        "and_typed_rejection_history_hardening_only"
    ] = AUTHORIZED_STAGE
    next_stage: Literal[
        "capability_observation_authoritative_parent_closed_rejection_history_"
        "state_bound_step_runtime_development_runner_preflight_only"
    ] = NEXT_STAGE
    future_job_count: Literal[192] = 192
    provider_calls_authorized: Literal[False] = False
    development_jobs_authorized: Literal[False] = False
    schema_version: str = V26_AUTHORITATIVE_PARENT_HISTORY_VERSION

    @model_validator(mode="after")
    def validate_transition(self) -> ProspectiveTransition:
        if self.blocked_predecessor_stage == self.next_stage:
            raise ValueError("v26.176 did not replace the blocked v26.175 transition")
        if self.transition_id != identity(
            self,
            "transition_id",
            "finance_v26_authoritative_parent_history_transition:",
        ):
            raise ValueError("v26.176 Transition identity is invalid")
        return self


class HardeningReport(FrozenModel):
    report_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    authorization_id: str = Field(min_length=1)
    source_root_id: str = Field(min_length=1)
    predecessor_audit_id: str = Field(min_length=1)
    defect_audit_id: str = Field(min_length=1)
    parent_contract_id: str = Field(min_length=1)
    rejection_history_contract_id: str = Field(min_length=1)
    development_catalog_id: str = Field(min_length=1)
    runner_input_catalog_id: str = Field(min_length=1)
    parent_reconstruction_audit_id: str = Field(min_length=1)
    all_replica_trajectory_audit_id: str = Field(min_length=1)
    typed_rejection_recovery_audit_id: str = Field(min_length=1)
    destructive_audit_id: str = Field(min_length=1)
    static_audit_id: str = Field(min_length=1)
    transition_id: str = Field(min_length=1)
    detail_files: tuple[FileBinding, ...] = Field(min_length=1)
    detail_file_count: int = Field(ge=1)
    provider_calls: Literal[0] = 0
    development_jobs: Literal[0] = 0
    next_stage: str = Field(min_length=1)
    schema_version: str = V26_AUTHORITATIVE_PARENT_HISTORY_VERSION

    @model_validator(mode="after")
    def validate_report(self) -> HardeningReport:
        if self.detail_file_count != len(self.detail_files):
            raise ValueError("v26.176 report detail-file denominator changed")
        if self.report_id != identity(
            self,
            "report_id",
            "finance_v26_authoritative_parent_history_hardening_report:",
        ):
            raise ValueError("v26.176 Report identity is invalid")
        return self


class BuildProducts(FrozenModel):
    authorization: ExternalAuditAuthorization
    source_root: TransitiveSourceRoot
    predecessor: PredecessorFreezeAudit
    defect: V175DefectReproductionAudit
    parent_contract: AuthoritativePackageRunnerParentContract
    rejection_history_contract: TypedRejectionHistoryContract
    development_catalog: AuthoritativeDevelopmentCatalog
    runner_input_catalog: AuthoritativeRunnerInputCatalog
    parent_reconstruction_audit: AuthoritativeParentReconstructionAudit
    all_replica_trajectory_audit: AllReplicaTrajectoryAudit
    typed_rejection_recovery_audit: TypedRejectionRecoveryAudit
    destructive: ProductionDestructiveAudit
    static: StaticAudit
    transition: ProspectiveTransition
    report: HardeningReport
