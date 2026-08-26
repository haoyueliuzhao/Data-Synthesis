from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.canonical_json import strict_canonical_hash
from trusted_synthesis.core.evaluation.measurement_outcome_v2 import (
    MeasurementOutcomeProjectionV2,
)
from trusted_synthesis.core.evaluation.valid_only_state_mapping_v2 import (
    ValidOnlyStateMapperContractV2,
)
from trusted_synthesis.core.trajectory.empirical_state_mapping_v2 import (
    EmpiricalStateSemanticPolicyV2,
    EmpiricalStructuralStateV2,
    StateContrastArtifactV2,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_mapper_v2_gold_fixtures import (
    MapperV2GoldFixtureAudit,
)


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


def identity(value: BaseModel, field: str, prefix: str) -> str:
    return strict_canonical_hash(value.model_dump(mode="python", exclude={field}), prefix=prefix)


class HistoricalMapperV1FreezeAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    v26_157_report_id: str = Field(min_length=1)
    v26_157_report_sha256: str = Field(min_length=64, max_length=64)
    v26_158_report_id: str = Field(min_length=1)
    v26_158_report_sha256: str = Field(min_length=64, max_length=64)
    mapper_v1_assignment_count: Literal[100] = 100
    mapper_v1_structural_state_count: Literal[41] = 41
    mapper_v1_route_projection_count: Literal[44] = 44
    historical_artifact_files_rewritten: Literal[0] = 0
    historical_reclassified: Literal[False] = False
    provider_calls: Literal[0] = 0
    stage_two_provider_calls: Literal[0] = 0
    status: Literal["passed"] = "passed"

    @model_validator(mode="after")
    def validate_audit(self) -> HistoricalMapperV1FreezeAudit:
        if self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_historical_mapper_v1_freeze:",
        ):
            raise ValueError("historical Mapper v1 freeze identity changed")
        return self


class ResultSemanticsRow(FrozenModel):
    job_id: str = Field(min_length=1)
    trajectory_id: str = Field(min_length=1)
    mapper_v1_state_id: str = Field(min_length=1)
    raw_result_semantics_hash_v1: str = Field(min_length=1)
    verifier_canonical_result_semantics_hash_v1: str = Field(min_length=1)
    representation_differs: bool
    result_only_equivalence_id: str = Field(min_length=1)


class ResultSemanticsDiagnostic(FrozenModel):
    audit_id: str = Field(min_length=1)
    assignment_count: Literal[100] = 100
    mapper_v1_state_count: Literal[41] = 41
    raw_vs_verifier_canonical_result_difference_count: int = Field(ge=0, le=100)
    mapper_v1_states_in_result_only_merge_groups: int = Field(ge=0, le=41)
    assignments_in_result_only_merge_groups: int = Field(ge=0, le=100)
    minimal_result_only_equivalence_class_count: int = Field(ge=1, le=41)
    rows: tuple[ResultSemanticsRow, ...] = Field(min_length=100, max_length=100)
    diagnostic_is_not_mapper_v2_final_partition: Literal[True] = True
    historical_reclassified: Literal[False] = False
    frequency_authorized: Literal[False] = False
    provider_calls: Literal[0] = 0

    @model_validator(mode="after")
    def validate_audit(self) -> ResultSemanticsDiagnostic:
        if len({item.job_id for item in self.rows}) != 100:
            raise ValueError("Result Semantics diagnostic denominator changed")
        if self.raw_vs_verifier_canonical_result_difference_count != sum(
            item.representation_differs for item in self.rows
        ):
            raise ValueError("Result Semantics difference count changed")
        if self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_result_semantics_diagnostic:",
        ):
            raise ValueError("Result Semantics diagnostic identity changed")
        return self


class ConditionRouteRow(FrozenModel):
    job_id: str = Field(min_length=1)
    task_package_id: str = Field(min_length=1)
    sampling_mode: Literal["reachability_unconditional", "reachability_conditioned"]
    public_condition_id: str | None
    requested_path_id: str | None
    requested_path_strategy: str | None
    static_path_catalog_id: str = Field(min_length=1)
    mapper_v1_route_projection_id: str = Field(min_length=1)
    experimental_condition_id: str = Field(min_length=1)
    empirical_route_signature_id: str = Field(min_length=1)


class ConditionRouteDecompositionAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    assignment_count: Literal[100] = 100
    mapper_v1_route_projection_count: Literal[44] = 44
    experimental_condition_id_count: int = Field(ge=1, le=100)
    task_pre_treatment_condition_cell_count: int = Field(ge=1, le=100)
    fixed_condition_cells_split_by_mapper_v1_route_count: int = Field(ge=0, le=100)
    unconditional_task_condition_cell_count: int = Field(ge=1, le=12)
    unconditional_cells_split_by_mapper_v1_route_count: int = Field(ge=0, le=12)
    empirical_route_signature_count: int = Field(ge=1, le=100)
    rows: tuple[ConditionRouteRow, ...] = Field(min_length=100, max_length=100)
    experimental_condition_contains_post_treatment_behavior: Literal[False] = False
    route_signature_is_not_condition: Literal[True] = True
    provider_calls: Literal[0] = 0

    @model_validator(mode="after")
    def validate_audit(self) -> ConditionRouteDecompositionAudit:
        if len({item.job_id for item in self.rows}) != 100:
            raise ValueError("Condition/Route diagnostic denominator changed")
        if self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_condition_route_decomposition:",
        ):
            raise ValueError("Condition/Route decomposition identity changed")
        return self


class TaskConditionSupportRow(FrozenModel):
    task_package_id: str = Field(min_length=1)
    experimental_condition_id: str = Field(min_length=1)
    sampling_mode: Literal["reachability_unconditional", "reachability_conditioned"]
    qualified_rollout_count: int = Field(ge=1)
    mapper_v1_state_ids: tuple[str, ...] = Field(min_length=1)
    result_only_equivalence_ids: tuple[str, ...] = Field(min_length=1)
    mapper_v2_diagnostic_state_ids: tuple[str, ...] = Field(min_length=1)


class TaskSupportSummary(FrozenModel):
    task_package_id: str = Field(min_length=1)
    pooled_mapper_v1_state_ids: tuple[str, ...] = Field(min_length=1)
    pooled_result_only_equivalence_ids: tuple[str, ...] = Field(min_length=1)
    pooled_mapper_v2_diagnostic_state_ids: tuple[str, ...] = Field(min_length=1)
    mapper_v1_multiple_state_across_all_conditions: bool
    mapper_v1_multiple_state_within_any_fixed_condition: bool
    mapper_v1_multiple_state_within_unconditional_condition: bool
    result_only_multiple_state_across_all_conditions: bool
    result_only_multiple_state_within_any_fixed_condition: bool
    result_only_multiple_state_within_unconditional_condition: bool
    mapper_v2_multiple_state_across_all_conditions: bool
    mapper_v2_multiple_state_within_any_fixed_condition: bool
    mapper_v2_multiple_state_within_unconditional_condition: bool


class FixedConditionStateSupportAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    source_population_task_count: Literal[12] = 12
    qualified_task_count: int = Field(ge=1, le=12)
    condition_cell_count: int = Field(ge=12, le=100)
    mapper_v1_pooled_multiple_state_task_count: int = Field(ge=0, le=12)
    mapper_v1_any_fixed_condition_multiple_state_task_count: int = Field(ge=0, le=12)
    mapper_v1_unconditional_multiple_state_task_count: int = Field(ge=0, le=12)
    result_only_pooled_multiple_state_task_count: int = Field(ge=0, le=12)
    result_only_any_fixed_condition_multiple_state_task_count: int = Field(ge=0, le=12)
    result_only_unconditional_multiple_state_task_count: int = Field(ge=0, le=12)
    mapper_v2_pooled_multiple_state_task_count: int = Field(ge=0, le=12)
    mapper_v2_any_fixed_condition_multiple_state_task_count: int = Field(ge=0, le=12)
    mapper_v2_unconditional_multiple_state_task_count: int = Field(ge=0, le=12)
    condition_rows: tuple[TaskConditionSupportRow, ...] = Field(min_length=12)
    task_summaries: tuple[TaskSupportSummary, ...] = Field(min_length=1, max_length=12)
    frequency_fields: None = None
    conditioned_samples_pooled_into_natural_frequency: Literal[False] = False
    frequency_authorized: Literal[False] = False
    provider_calls: Literal[0] = 0

    @model_validator(mode="after")
    def validate_audit(self) -> FixedConditionStateSupportAudit:
        if (
            self.qualified_task_count != len(self.task_summaries)
            or len({item.task_package_id for item in self.task_summaries})
            != self.qualified_task_count
        ):
            raise ValueError("fixed-condition Task denominator changed")
        if self.condition_cell_count != len(self.condition_rows):
            raise ValueError("fixed-condition cell denominator changed")
        if self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_fixed_condition_state_support:",
        ):
            raise ValueError("fixed-condition State Support identity changed")
        return self


class MapperV2DiagnosticRow(FrozenModel):
    job_id: str = Field(min_length=1)
    task_package_id: str = Field(min_length=1)
    trajectory_id: str = Field(min_length=1)
    mapper_v1_assignment_id: str = Field(min_length=1)
    mapper_v1_state_id: str = Field(min_length=1)
    mapper_v2_diagnostic_assignment_id: str = Field(min_length=1)
    mapper_v2_diagnostic_state_id: str = Field(min_length=1)
    experimental_condition_id: str = Field(min_length=1)
    empirical_route_signature_id: str = Field(min_length=1)
    raw_final_payload_hash: str = Field(min_length=1)
    canonical_result_semantics_hash: str = Field(min_length=1)
    transition_reason_ids: tuple[str, ...] = Field(min_length=1)
    historical_reclassified: Literal[False] = False


class MapperV2DiagnosticCatalog(FrozenModel):
    catalog_id: str = Field(min_length=1)
    semantic_policy_id: str = Field(min_length=1)
    mapper_contract_id: str = Field(min_length=1)
    row_count: Literal[100] = 100
    mapper_v1_state_count: Literal[41] = 41
    mapper_v2_diagnostic_state_count: int = Field(ge=1, le=100)
    v1_states_merged_by_v2_count: int = Field(ge=0, le=41)
    v1_states_split_by_v2_count: int = Field(ge=0, le=41)
    rows: tuple[MapperV2DiagnosticRow, ...] = Field(min_length=100, max_length=100)
    formal_new_state_assignment_count: Literal[0] = 0
    historical_reclassified: Literal[False] = False
    frequency_authorized: Literal[False] = False
    vtdo_authorized: Literal[False] = False
    provider_calls: Literal[0] = 0

    @model_validator(mode="after")
    def validate_catalog(self) -> MapperV2DiagnosticCatalog:
        if len({item.job_id for item in self.rows}) != 100:
            raise ValueError("Mapper v2 diagnostic denominator changed")
        if self.mapper_v2_diagnostic_state_count != len(
            {item.mapper_v2_diagnostic_state_id for item in self.rows}
        ):
            raise ValueError("Mapper v2 diagnostic State count changed")
        if self.catalog_id != identity(
            self,
            "catalog_id",
            "finance_v26_mapper_v2_diagnostic_catalog:",
        ):
            raise ValueError("Mapper v2 diagnostic Catalog identity changed")
        return self


class MapperV2StateCatalog(FrozenModel):
    catalog_id: str = Field(min_length=1)
    semantic_policy_id: str = Field(min_length=1)
    state_count: int = Field(ge=1, le=100)
    states: tuple[EmpiricalStructuralStateV2, ...] = Field(min_length=1)
    diagnostic_only: Literal[True] = True
    provider_calls: Literal[0] = 0

    @model_validator(mode="after")
    def validate_catalog(self) -> MapperV2StateCatalog:
        ids = tuple(item.state_id for item in self.states)
        if self.state_count != len(self.states) or ids != tuple(sorted(set(ids))):
            raise ValueError("Mapper v2 State Catalog changed")
        if self.catalog_id != identity(
            self,
            "catalog_id",
            "finance_v26_mapper_v2_state_catalog:",
        ):
            raise ValueError("Mapper v2 State Catalog identity changed")
        return self


class StateContrastCatalog(FrozenModel):
    catalog_id: str = Field(min_length=1)
    state_catalog_id: str = Field(min_length=1)
    state_count: int = Field(ge=1, le=100)
    expected_pair_count: int = Field(ge=0)
    contrast_count: int = Field(ge=0)
    contrasts: tuple[StateContrastArtifactV2, ...]
    every_state_pair_has_difference_witness: Literal[True] = True
    provider_calls: Literal[0] = 0

    @model_validator(mode="after")
    def validate_catalog(self) -> StateContrastCatalog:
        expected = self.state_count * (self.state_count - 1) // 2
        ids = tuple(item.contrast_id for item in self.contrasts)
        if (
            self.expected_pair_count != expected
            or self.contrast_count != expected
            or len(self.contrasts) != expected
            or ids != tuple(sorted(set(ids)))
        ):
            raise ValueError("State Contrast pair denominator changed")
        if self.catalog_id != identity(
            self,
            "catalog_id",
            "finance_v26_state_contrast_catalog:",
        ):
            raise ValueError("State Contrast Catalog identity changed")
        return self


class IndependentReferenceMapperAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    gold_fixture_audit_id: str = Field(min_length=1)
    production_mapper_implementation_sha256: str = Field(min_length=64, max_length=64)
    reference_mapper_implementation_sha256: str = Field(min_length=64, max_length=64)
    trajectory_count: Literal[100] = 100
    exact_state_match_count: Literal[100] = 100
    production_mapper_called_by_reference_count: Literal[0] = 0
    gold_merge_fixture_count: int = Field(ge=1)
    gold_split_fixture_count: int = Field(ge=3)
    gold_pair_relation_pass_count: Literal[5] = 5
    provider_calls: Literal[0] = 0
    status: Literal["passed"] = "passed"

    @model_validator(mode="after")
    def validate_audit(self) -> IndependentReferenceMapperAudit:
        if self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_independent_reference_mapper_audit:",
        ):
            raise ValueError("independent Reference Mapper audit identity changed")
        return self


class MeasurementClassificationDecompositionAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    exact_raw_count: Literal[360] = 360
    historical_support_exit_count: int = Field(ge=0, le=360)
    historical_support_exit_reprojected_as_instrument_failure_count: int = Field(ge=0, le=360)
    raw_native_instrument_integrity_for_support_exit_count: int = Field(ge=0, le=360)
    historical_typed_semantic_rejection_count: int = Field(ge=0, le=360)
    v2_support_instrument_overlap_count: Literal[0] = 0
    v2_typed_rejection_validity_evaluable_count: int = Field(ge=0, le=360)
    v2_projection_count: Literal[360] = 360
    v2_projections: tuple[MeasurementOutcomeProjectionV2, ...] = Field(
        min_length=360,
        max_length=360,
    )
    historical_reclassified: Literal[False] = False
    future_classifier_only: Literal[True] = True
    provider_calls: Literal[0] = 0

    @model_validator(mode="after")
    def validate_audit(self) -> MeasurementClassificationDecompositionAudit:
        if len({item.projection_id for item in self.v2_projections}) != 360:
            raise ValueError("v2 Measurement projection denominator changed")
        if self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_measurement_classification_decomposition:",
        ):
            raise ValueError("Measurement classification decomposition identity changed")
        return self


class MutationResult(FrozenModel):
    mutation_name: str = Field(min_length=1)
    failed_closed: Literal[True] = True


class StateSemanticsDestructiveAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    mutation_count: int = Field(ge=10)
    failed_closed_count: int = Field(ge=10)
    mutations: tuple[MutationResult, ...] = Field(min_length=10)
    unauthorized_provider_calls: Literal[0] = 0

    @model_validator(mode="after")
    def validate_audit(self) -> StateSemanticsDestructiveAudit:
        names = tuple(item.mutation_name for item in self.mutations)
        if (
            self.mutation_count != len(self.mutations)
            or self.failed_closed_count != len(self.mutations)
            or names != tuple(sorted(set(names)))
        ):
            raise ValueError("State Semantics destructive audit changed")
        if self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_state_semantics_destructive_audit:",
        ):
            raise ValueError("State Semantics destructive audit identity changed")
        return self


class StateSemanticsTransitionContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    next_permitted_stage: Literal[
        "fresh_mapper_v2_reachability_frequency_experiment_preflight_only"
    ] = "fresh_mapper_v2_reachability_frequency_experiment_preflight_only"
    fresh_population_required: Literal[True] = True
    complete_measurement_support_denominator_required: Literal[True] = True
    unconditional_and_conditioned_strata_separate: Literal[True] = True
    task_primary_rollout_secondary_statistics_required: Literal[True] = True
    independent_postrun_audit_required: Literal[True] = True
    provider_execution_authorized: Literal[False] = False
    current_historical_frequency_authorized: Literal[False] = False
    current_vtdo_authorized: Literal[False] = False
    historical_rerun_or_reclassification_authorized: Literal[False] = False
    schema_version: str = "finance_v26_state_semantics_transition.v1"

    @model_validator(mode="after")
    def validate_contract(self) -> StateSemanticsTransitionContract:
        if self.contract_id != identity(
            self,
            "contract_id",
            "finance_v26_state_semantics_transition:",
        ):
            raise ValueError("State Semantics transition identity changed")
        return self


class DetailFile(FrozenModel):
    relative_path: str = Field(min_length=1)
    sha256: str = Field(min_length=64, max_length=64)
    byte_count: int = Field(gt=0)


class StateSemanticsAuditReport(FrozenModel):
    report_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    historical_v1_freeze_audit_id: str = Field(min_length=1)
    result_semantics_diagnostic_id: str = Field(min_length=1)
    condition_route_decomposition_audit_id: str = Field(min_length=1)
    fixed_condition_support_audit_id: str = Field(min_length=1)
    semantic_policy_id: str = Field(min_length=1)
    mapper_contract_id: str = Field(min_length=1)
    mapper_v2_diagnostic_catalog_id: str = Field(min_length=1)
    mapper_v2_state_catalog_id: str = Field(min_length=1)
    state_contrast_catalog_id: str = Field(min_length=1)
    mapper_v2_gold_fixture_audit_id: str = Field(min_length=1)
    independent_reference_mapper_audit_id: str = Field(min_length=1)
    measurement_classification_audit_id: str = Field(min_length=1)
    destructive_audit_id: str = Field(min_length=1)
    transition_contract_id: str = Field(min_length=1)
    qualified_trajectory_count: Literal[100] = 100
    mapper_v1_state_count: Literal[41] = 41
    mapper_v2_diagnostic_state_count: int = Field(ge=1, le=100)
    experimental_condition_count: int = Field(ge=1, le=100)
    task_condition_cell_count: int = Field(ge=1, le=100)
    empirical_route_signature_count: int = Field(ge=1, le=100)
    state_contrast_count: int = Field(ge=0)
    provider_calls: Literal[0] = 0
    stage_two_provider_calls: Literal[0] = 0
    gpu_jobs: Literal[0] = 0
    formal_new_state_assignment_count: Literal[0] = 0
    historical_reclassified: Literal[False] = False
    frequency_authorized: Literal[False] = False
    vtdo_authorized: Literal[False] = False
    detail_files: tuple[DetailFile, ...] = Field(min_length=12)
    status: Literal["state_semantics_and_condition_index_audit_passed"] = (
        "state_semantics_and_condition_index_audit_passed"
    )
    schema_version: str = "finance_v26_state_semantics_audit_report.v1"

    @model_validator(mode="after")
    def validate_report(self) -> StateSemanticsAuditReport:
        paths = tuple(item.relative_path for item in self.detail_files)
        if paths != tuple(sorted(set(paths))):
            raise ValueError("State Semantics report detail files are noncanonical")
        if self.report_id != identity(
            self,
            "report_id",
            "finance_v26_state_semantics_audit_report:",
        ):
            raise ValueError("State Semantics audit report identity changed")
        return self


class BuildProducts(FrozenModel):
    historical_freeze: HistoricalMapperV1FreezeAudit
    result_semantics: ResultSemanticsDiagnostic
    condition_route: ConditionRouteDecompositionAudit
    fixed_condition_support: FixedConditionStateSupportAudit
    semantic_policy: EmpiricalStateSemanticPolicyV2
    mapper_contract: ValidOnlyStateMapperContractV2
    diagnostic_catalog: MapperV2DiagnosticCatalog
    state_catalog: MapperV2StateCatalog
    contrast_catalog: StateContrastCatalog
    gold_fixture_audit: MapperV2GoldFixtureAudit
    reference_audit: IndependentReferenceMapperAudit
    classification_audit: MeasurementClassificationDecompositionAudit
    destructive_audit: StateSemanticsDestructiveAudit
    transition: StateSemanticsTransitionContract
    report: StateSemanticsAuditReport
    diagnostic_assignments: tuple[Any, ...] = Field(exclude=True)
