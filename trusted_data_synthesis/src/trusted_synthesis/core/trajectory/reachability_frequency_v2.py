from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.canonical_json import strict_canonical_hash
from trusted_synthesis.core.trajectory.empirical_state_mapping_v2 import (
    ExperimentalConditionV2,
    ValidOnlyEmpiricalStateAssignmentV2,
)

REACHABILITY_FREQUENCY_V2_VERSION = "mapper_v2_reachability_frequency.v1"
TASK_CONDITION_STATISTICS_KEY = (
    "task_package_id",
    "experimental_condition_id",
    "generation_policy_id",
)


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


def _identity(value: BaseModel, field: str, prefix: str) -> str:
    return strict_canonical_hash(value.model_dump(mode="python", exclude={field}), prefix=prefix)


class BoundedGenerationPolicyV2(FrozenModel):
    policy_id: str = Field(min_length=1)
    resource_contract_id: str = Field(min_length=1)
    measurement_support_contract_id: str = Field(min_length=1)
    maximum_ordinary_detours: Literal[1] = 1
    maximum_abi_rescues: Literal[1] = 1
    maximum_semantic_recoveries: Literal[1] = 1
    maximum_transport_replacements: Literal[1] = 1
    policy_family: Literal["bounded_dynamic_policy"] = "bounded_dynamic_policy"
    unrestricted_natural_distribution_claimed: Literal[False] = False
    generation_condition_enters_every_frequency_cell: Literal[True] = True
    schema_version: str = REACHABILITY_FREQUENCY_V2_VERSION

    @model_validator(mode="after")
    def validate_policy(self) -> BoundedGenerationPolicyV2:
        if self.policy_id != _identity(
            self,
            "policy_id",
            "bounded_reachability_generation_policy:",
        ):
            raise ValueError("bounded Reachability generation-policy identity changed")
        return self


class TaskConditionCellV2(FrozenModel):
    cell_id: str = Field(min_length=1)
    task_package_id: str = Field(min_length=1)
    experimental_condition_id: str = Field(min_length=1)
    generation_policy_id: str = Field(min_length=1)
    experimental_condition: ExperimentalConditionV2
    statistics_key_fields: tuple[str, str, str] = TASK_CONDITION_STATISTICS_KEY
    empirical_route_signature_is_conditioning_variable: Literal[False] = False
    schema_version: str = REACHABILITY_FREQUENCY_V2_VERSION

    @model_validator(mode="after")
    def validate_cell(self) -> TaskConditionCellV2:
        if (
            self.experimental_condition_id != self.experimental_condition.condition_id
            or self.statistics_key_fields != TASK_CONDITION_STATISTICS_KEY
            or self.cell_id != _identity(self, "cell_id", "mapper_v2_task_condition_cell:")
        ):
            raise ValueError("Mapper v2 TaskConditionCell identity changed")
        return self


class TaskConditionCellCatalogV2(FrozenModel):
    catalog_id: str = Field(min_length=1)
    static_path_catalog_id: str = Field(min_length=1)
    generation_policy_id: str = Field(min_length=1)
    cells: tuple[TaskConditionCellV2, ...] = Field(min_length=1)
    task_count: int = Field(ge=1)
    cell_count: int = Field(ge=1)
    unconditional_cell_count: int = Field(ge=1)
    conditioned_cell_count: int = Field(ge=1)
    conditioned_path_count: int = Field(ge=1)
    empirical_route_signature_count: Literal[0] = 0
    formal_assignment_count: Literal[0] = 0
    schema_version: str = REACHABILITY_FREQUENCY_V2_VERSION

    @model_validator(mode="after")
    def validate_catalog(self) -> TaskConditionCellCatalogV2:
        ids = tuple(item.cell_id for item in self.cells)
        task_ids = {item.task_package_id for item in self.cells}
        unconditional = tuple(
            item
            for item in self.cells
            if item.experimental_condition.sampling_mode == "reachability_unconditional"
        )
        conditioned = tuple(
            item
            for item in self.cells
            if item.experimental_condition.sampling_mode == "reachability_conditioned"
        )
        path_ids = {
            item.experimental_condition.requested_path_id
            for item in conditioned
            if item.experimental_condition.requested_path_id is not None
        }
        if (
            ids != tuple(sorted(set(ids)))
            or self.cell_count != len(self.cells)
            or self.task_count != len(task_ids)
            or self.unconditional_cell_count != len(unconditional)
            or self.conditioned_cell_count != len(conditioned)
            or self.conditioned_path_count != len(path_ids)
            or any(item.generation_policy_id != self.generation_policy_id for item in self.cells)
            or any(
                item.experimental_condition.static_path_catalog_id != self.static_path_catalog_id
                for item in self.cells
            )
            or len({item.task_package_id for item in unconditional}) != self.task_count
            or self.catalog_id
            != _identity(self, "catalog_id", "mapper_v2_task_condition_cell_catalog:")
        ):
            raise ValueError("Mapper v2 TaskConditionCell Catalog changed")
        return self


class FrequencyMeasurementGateV2(FrozenModel):
    gate_id: str = Field(min_length=1)
    exact_job_denominator: int = Field(ge=1)
    complete_raw_count: int = Field(ge=0)
    model_endpoint_count: int = Field(ge=0)
    validity_evaluable_count: int = Field(ge=0)
    measurement_support_exit_count: int = Field(ge=0)
    instrument_failure_count: int = Field(ge=0)
    privacy_failure_count: int = Field(ge=0)
    exact_model_thinking_usage_failure_count: int = Field(ge=0)
    typed_budget_no_call_count: int = Field(ge=0)
    unresolved_transport_failure_count: int = Field(ge=0)
    passed: bool
    exact_frequency_estimands_null: bool
    row_deletion_or_denominator_repair_allowed: Literal[False] = False
    schema_version: str = REACHABILITY_FREQUENCY_V2_VERSION

    @model_validator(mode="after")
    def validate_gate(self) -> FrequencyMeasurementGateV2:
        failures = (
            self.measurement_support_exit_count,
            self.instrument_failure_count,
            self.privacy_failure_count,
            self.exact_model_thinking_usage_failure_count,
            self.typed_budget_no_call_count,
            self.unresolved_transport_failure_count,
        )
        expected = (
            self.complete_raw_count == self.exact_job_denominator
            and self.model_endpoint_count == self.exact_job_denominator
            and self.validity_evaluable_count == self.exact_job_denominator
            and not any(failures)
        )
        if (
            self.passed != expected
            or self.exact_frequency_estimands_null == expected
            or self.gate_id != _identity(self, "gate_id", "mapper_v2_frequency_measurement_gate:")
        ):
            raise ValueError("Mapper v2 frequency Measurement Gate changed")
        return self


class ReachabilityFrequencyAssignmentV2(FrozenModel):
    assignment_id: str = Field(min_length=1)
    experiment_id: str = Field(min_length=1)
    job_id: str = Field(min_length=1)
    task_condition_cell_id: str = Field(min_length=1)
    task_package_id: str = Field(min_length=1)
    experimental_condition_id: str = Field(min_length=1)
    generation_policy_id: str = Field(min_length=1)
    mapping_assignment: ValidOnlyEmpiricalStateAssignmentV2
    structural_state_id: str = Field(min_length=1)
    empirical_route_signature_id: str = Field(min_length=1)
    qualified_validity: Literal[True] = True
    complete_measurement_gate_passed: Literal[True] = True
    frequency_denominator_eligible: Literal[True] = True
    route_signature_excluded_from_statistics_key: Literal[True] = True
    schema_version: str = REACHABILITY_FREQUENCY_V2_VERSION

    @model_validator(mode="after")
    def validate_assignment(self) -> ReachabilityFrequencyAssignmentV2:
        mapped = self.mapping_assignment
        if (
            self.experimental_condition_id != mapped.experimental_condition_id
            or self.structural_state_id != mapped.structural_state_id
            or self.empirical_route_signature_id != mapped.empirical_route_signature_id
            or mapped.qualified_validity is not True
            or not mapped.valid_only_gate_crossed
            or mapped.historical_reclassified
            or self.assignment_id
            != _identity(self, "assignment_id", "mapper_v2_reachability_frequency_assignment:")
        ):
            raise ValueError("Mapper v2 Reachability Frequency Assignment changed")
        return self


class StateFrequencyCountV2(FrozenModel):
    structural_state_id: str = Field(min_length=1)
    qualified_rollout_count: int = Field(ge=1)
    qualified_rollout_denominator: int = Field(ge=1)
    exact_fraction: str = Field(pattern=r"^[0-9]+(?:\.[0-9]+)?$")

    @model_validator(mode="after")
    def validate_frequency(self) -> StateFrequencyCountV2:
        expected = format(
            Decimal(self.qualified_rollout_count) / Decimal(self.qualified_rollout_denominator),
            "f",
        )
        if self.qualified_rollout_count > self.qualified_rollout_denominator:
            raise ValueError("State frequency count exceeds its denominator")
        if self.exact_fraction != expected:
            raise ValueError("State frequency fraction changed")
        return self


FrequencyNullReason = Literal["measurement_gate_failed", "no_qualified_rows"]


class TaskConditionFrequencyReportV2(FrozenModel):
    report_id: str = Field(min_length=1)
    task_condition_cell_id: str = Field(min_length=1)
    task_package_id: str = Field(min_length=1)
    experimental_condition_id: str = Field(min_length=1)
    generation_policy_id: str = Field(min_length=1)
    sampling_mode: Literal["reachability_unconditional", "reachability_conditioned"]
    qualified_rollout_count: int = Field(ge=0)
    observed_state_count: int = Field(ge=0)
    distribution: tuple[StateFrequencyCountV2, ...] | None
    null_reason: FrequencyNullReason | None
    task_is_primary_statistical_unit: Literal[True] = True
    rollouts_are_secondary_repeated_measures: Literal[True] = True
    empirical_route_signature_is_not_conditioning_variable: Literal[True] = True
    schema_version: str = REACHABILITY_FREQUENCY_V2_VERSION

    @model_validator(mode="after")
    def validate_report(self) -> TaskConditionFrequencyReportV2:
        if self.distribution is None:
            if self.null_reason is None or self.qualified_rollout_count != 0:
                raise ValueError("null Task-condition frequency report changed")
        else:
            state_ids = tuple(item.structural_state_id for item in self.distribution)
            if (
                self.null_reason is not None
                or not self.distribution
                or state_ids != tuple(sorted(set(state_ids)))
                or self.qualified_rollout_count
                != sum(item.qualified_rollout_count for item in self.distribution)
                or self.observed_state_count != len(self.distribution)
                or any(
                    item.qualified_rollout_denominator != self.qualified_rollout_count
                    for item in self.distribution
                )
            ):
                raise ValueError("Task-condition frequency distribution changed")
        if self.report_id != _identity(
            self,
            "report_id",
            "mapper_v2_task_condition_frequency_report:",
        ):
            raise ValueError("Task-condition frequency report identity changed")
        return self


class ReachabilityFrequencySummaryV2(FrozenModel):
    summary_id: str = Field(min_length=1)
    experiment_id: str = Field(min_length=1)
    measurement_gate_id: str = Field(min_length=1)
    task_condition_cell_catalog_id: str = Field(min_length=1)
    reports: tuple[TaskConditionFrequencyReportV2, ...] = Field(min_length=1)
    report_count: int = Field(ge=1)
    null_report_count: int = Field(ge=0)
    unconditional_report_count: int = Field(ge=1)
    conditioned_report_count: int = Field(ge=1)
    pooled_across_tasks_report_count: Literal[0] = 0
    conditioned_rows_in_unconditional_estimand_count: Literal[0] = 0
    empirical_route_conditioned_report_count: Literal[0] = 0
    schema_version: str = REACHABILITY_FREQUENCY_V2_VERSION

    @model_validator(mode="after")
    def validate_summary(self) -> ReachabilityFrequencySummaryV2:
        ids = tuple(item.report_id for item in self.reports)
        if (
            ids != tuple(sorted(set(ids)))
            or self.report_count != len(self.reports)
            or self.null_report_count != sum(item.distribution is None for item in self.reports)
            or self.unconditional_report_count
            != sum(item.sampling_mode == "reachability_unconditional" for item in self.reports)
            or self.conditioned_report_count
            != sum(item.sampling_mode == "reachability_conditioned" for item in self.reports)
            or self.summary_id
            != _identity(self, "summary_id", "mapper_v2_reachability_frequency_summary:")
        ):
            raise ValueError("Mapper v2 Reachability Frequency Summary changed")
        return self


def make_bounded_generation_policy_v2(
    *,
    resource_contract_id: str,
    measurement_support_contract_id: str,
) -> BoundedGenerationPolicyV2:
    values = {
        "resource_contract_id": resource_contract_id,
        "measurement_support_contract_id": measurement_support_contract_id,
    }
    provisional = BoundedGenerationPolicyV2.model_construct(policy_id="pending", **values)
    return BoundedGenerationPolicyV2(
        policy_id=_identity(
            provisional,
            "policy_id",
            "bounded_reachability_generation_policy:",
        ),
        **values,
    )


def make_task_condition_cell_v2(
    *,
    task_package_id: str,
    experimental_condition: ExperimentalConditionV2,
    generation_policy_id: str,
) -> TaskConditionCellV2:
    values = {
        "task_package_id": task_package_id,
        "experimental_condition_id": experimental_condition.condition_id,
        "generation_policy_id": generation_policy_id,
        "experimental_condition": experimental_condition,
    }
    provisional = TaskConditionCellV2.model_construct(cell_id="pending", **values)
    return TaskConditionCellV2(
        cell_id=_identity(provisional, "cell_id", "mapper_v2_task_condition_cell:"),
        **values,
    )


def make_frequency_measurement_gate_v2(
    *,
    exact_job_denominator: int,
    complete_raw_count: int,
    model_endpoint_count: int,
    validity_evaluable_count: int,
    measurement_support_exit_count: int = 0,
    instrument_failure_count: int = 0,
    privacy_failure_count: int = 0,
    exact_model_thinking_usage_failure_count: int = 0,
    typed_budget_no_call_count: int = 0,
    unresolved_transport_failure_count: int = 0,
) -> FrequencyMeasurementGateV2:
    failures = (
        measurement_support_exit_count,
        instrument_failure_count,
        privacy_failure_count,
        exact_model_thinking_usage_failure_count,
        typed_budget_no_call_count,
        unresolved_transport_failure_count,
    )
    passed = (
        complete_raw_count == exact_job_denominator
        and model_endpoint_count == exact_job_denominator
        and validity_evaluable_count == exact_job_denominator
        and not any(failures)
    )
    values = {
        "exact_job_denominator": exact_job_denominator,
        "complete_raw_count": complete_raw_count,
        "model_endpoint_count": model_endpoint_count,
        "validity_evaluable_count": validity_evaluable_count,
        "measurement_support_exit_count": measurement_support_exit_count,
        "instrument_failure_count": instrument_failure_count,
        "privacy_failure_count": privacy_failure_count,
        "exact_model_thinking_usage_failure_count": exact_model_thinking_usage_failure_count,
        "typed_budget_no_call_count": typed_budget_no_call_count,
        "unresolved_transport_failure_count": unresolved_transport_failure_count,
        "passed": passed,
        "exact_frequency_estimands_null": not passed,
    }
    provisional = FrequencyMeasurementGateV2.model_construct(gate_id="pending", **values)
    return FrequencyMeasurementGateV2(
        gate_id=_identity(
            provisional,
            "gate_id",
            "mapper_v2_frequency_measurement_gate:",
        ),
        **values,
    )


def make_reachability_frequency_assignment_v2(
    *,
    experiment_id: str,
    job_id: str,
    cell: TaskConditionCellV2,
    mapping_assignment: ValidOnlyEmpiricalStateAssignmentV2,
    measurement_gate: FrequencyMeasurementGateV2,
) -> ReachabilityFrequencyAssignmentV2:
    if not measurement_gate.passed:
        raise ValueError("frequency Assignment requires a complete passing Measurement Gate")
    if mapping_assignment.experimental_condition_id != cell.experimental_condition_id:
        raise ValueError("frequency Assignment crossed Experimental Conditions")
    values = {
        "experiment_id": experiment_id,
        "job_id": job_id,
        "task_condition_cell_id": cell.cell_id,
        "task_package_id": cell.task_package_id,
        "experimental_condition_id": cell.experimental_condition_id,
        "generation_policy_id": cell.generation_policy_id,
        "mapping_assignment": mapping_assignment,
        "structural_state_id": mapping_assignment.structural_state_id,
        "empirical_route_signature_id": mapping_assignment.empirical_route_signature_id,
    }
    provisional = ReachabilityFrequencyAssignmentV2.model_construct(
        assignment_id="pending",
        **values,
    )
    return ReachabilityFrequencyAssignmentV2(
        assignment_id=_identity(
            provisional,
            "assignment_id",
            "mapper_v2_reachability_frequency_assignment:",
        ),
        **values,
    )


def summarize_reachability_frequency_v2(
    *,
    experiment_id: str,
    measurement_gate: FrequencyMeasurementGateV2,
    cell_catalog: TaskConditionCellCatalogV2,
    assignments: Sequence[ReachabilityFrequencyAssignmentV2],
) -> ReachabilityFrequencySummaryV2:
    by_cell: dict[str, list[ReachabilityFrequencyAssignmentV2]] = defaultdict(list)
    known = {item.cell_id: item for item in cell_catalog.cells}
    seen_jobs: set[str] = set()
    for assignment in assignments:
        cell = known.get(assignment.task_condition_cell_id)
        if cell is None:
            raise ValueError("frequency Assignment references an unknown TaskConditionCell")
        if assignment.job_id in seen_jobs:
            raise ValueError("frequency summary received duplicate Job Assignment")
        if (
            assignment.experiment_id != experiment_id
            or assignment.task_package_id != cell.task_package_id
            or assignment.experimental_condition_id != cell.experimental_condition_id
            or assignment.generation_policy_id != cell.generation_policy_id
        ):
            raise ValueError("frequency Assignment crossed its strong statistics key")
        seen_jobs.add(assignment.job_id)
        by_cell[cell.cell_id].append(assignment)
    if assignments and not measurement_gate.passed:
        raise ValueError("failed Measurement Gate cannot admit frequency Assignments")

    reports: list[TaskConditionFrequencyReportV2] = []
    for cell in cell_catalog.cells:
        rows = by_cell[cell.cell_id]
        distribution: tuple[StateFrequencyCountV2, ...] | None
        null_reason: FrequencyNullReason | None
        if not measurement_gate.passed:
            distribution = None
            null_reason = "measurement_gate_failed"
        elif not rows:
            distribution = None
            null_reason = "no_qualified_rows"
        else:
            counts = Counter(item.structural_state_id for item in rows)
            denominator = len(rows)
            distribution = tuple(
                StateFrequencyCountV2(
                    structural_state_id=state_id,
                    qualified_rollout_count=count,
                    qualified_rollout_denominator=denominator,
                    exact_fraction=format(Decimal(count) / Decimal(denominator), "f"),
                )
                for state_id, count in sorted(counts.items())
            )
            null_reason = None
        values = {
            "task_condition_cell_id": cell.cell_id,
            "task_package_id": cell.task_package_id,
            "experimental_condition_id": cell.experimental_condition_id,
            "generation_policy_id": cell.generation_policy_id,
            "sampling_mode": cell.experimental_condition.sampling_mode,
            "qualified_rollout_count": len(rows),
            "observed_state_count": 0 if distribution is None else len(distribution),
            "distribution": distribution,
            "null_reason": null_reason,
        }
        provisional = TaskConditionFrequencyReportV2.model_construct(
            report_id="pending",
            **values,
        )
        reports.append(
            TaskConditionFrequencyReportV2(
                report_id=_identity(
                    provisional,
                    "report_id",
                    "mapper_v2_task_condition_frequency_report:",
                ),
                **values,
            )
        )
    ordered = tuple(sorted(reports, key=lambda item: item.report_id))
    values = {
        "experiment_id": experiment_id,
        "measurement_gate_id": measurement_gate.gate_id,
        "task_condition_cell_catalog_id": cell_catalog.catalog_id,
        "reports": ordered,
        "report_count": len(ordered),
        "null_report_count": sum(item.distribution is None for item in ordered),
        "unconditional_report_count": sum(
            item.sampling_mode == "reachability_unconditional" for item in ordered
        ),
        "conditioned_report_count": sum(
            item.sampling_mode == "reachability_conditioned" for item in ordered
        ),
    }
    provisional = ReachabilityFrequencySummaryV2.model_construct(
        summary_id="pending",
        **values,
    )
    return ReachabilityFrequencySummaryV2(
        summary_id=_identity(
            provisional,
            "summary_id",
            "mapper_v2_reachability_frequency_summary:",
        ),
        **values,
    )


def make_task_condition_cell_catalog_v2(
    *,
    static_path_catalog_id: str,
    generation_policy_id: str,
    cells: Sequence[TaskConditionCellV2],
) -> TaskConditionCellCatalogV2:
    ordered = tuple(sorted(cells, key=lambda item: item.cell_id))
    values = {
        "static_path_catalog_id": static_path_catalog_id,
        "generation_policy_id": generation_policy_id,
        "cells": ordered,
        "task_count": len({item.task_package_id for item in ordered}),
        "cell_count": len(ordered),
        "unconditional_cell_count": sum(
            item.experimental_condition.sampling_mode == "reachability_unconditional"
            for item in ordered
        ),
        "conditioned_cell_count": sum(
            item.experimental_condition.sampling_mode == "reachability_conditioned"
            for item in ordered
        ),
        "conditioned_path_count": len(
            {
                item.experimental_condition.requested_path_id
                for item in ordered
                if item.experimental_condition.requested_path_id is not None
            }
        ),
    }
    provisional = TaskConditionCellCatalogV2.model_construct(catalog_id="pending", **values)
    return TaskConditionCellCatalogV2(
        catalog_id=_identity(
            provisional,
            "catalog_id",
            "mapper_v2_task_condition_cell_catalog:",
        ),
        **values,
    )


def task_condition_statistics_key_v2(
    assignment: ReachabilityFrequencyAssignmentV2,
) -> Mapping[str, str]:
    return {
        "task_package_id": assignment.task_package_id,
        "experimental_condition_id": assignment.experimental_condition_id,
        "generation_policy_id": assignment.generation_policy_id,
    }
