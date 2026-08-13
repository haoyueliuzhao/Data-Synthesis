from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from statistics import fmean
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_boundary_analysis import (
    ConfidenceInterval,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_mechanism_confirmation import (
    CapabilityMechanismConfirmationPopulation,
    FinanceCapabilityMechanismConfirmationContract,
    FinanceCapabilityMechanismConfirmationReport,
    MechanismSelectionFreeze,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_mechanism_flash_development import (  # noqa: E501
    MechanismBehaviorObservation,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_mechanism_repair import (
    PRIOR_CONFIRMED_MECHANISM_IDS,
    REPAIRED_MECHANISM_IDS,
    CapabilityMechanismRepairPopulation,
    FinanceCapabilityMechanismRepairContract,
    FinanceCapabilityMechanismRepairReport,
    MechanismRepairSelectionFreeze,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_sensitive_frontier import (
    CAPABILITY_AXES,
    _symmetric_eigenvalues,
)
from trusted_synthesis.hashing import canonical_hash

MECHANISM_GEOMETRY_VERSION = "finance_capability_mechanism_information_geometry.v2"
MECHANISM_GEOMETRY_SOURCE_VERSION = "finance_capability_mechanism_information_geometry_source.v1"
MECHANISM_GEOMETRY_CONTRACT_VERSION = (
    "finance_capability_mechanism_information_geometry_contract.v2"
)
MECHANISM_GEOMETRY_SPECTRUM_VERSION = (
    "finance_capability_mechanism_information_geometry_spectrum.v1"
)
MECHANISM_GEOMETRY_REPORT_VERSION = "finance_capability_mechanism_information_geometry_report.v2"
CONFIRMED_MECHANISM_IDS = (*PRIOR_CONFIRMED_MECHANISM_IDS, *REPAIRED_MECHANISM_IDS)
SourceKind = Literal["v25_21_confirmation", "v25_22_repair_confirmation"]


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class MechanismGeometryThresholds(FrozenModel):
    minimum_rank: int = Field(default=4, ge=1)
    minimum_effective_rank: float = Field(default=3.0, ge=1)
    maximum_condition_number: float = Field(default=100.0, gt=1)
    minimum_boundary_task_fraction: float = Field(default=0.25, ge=0, le=1)
    boundary_probability_lower: float = Field(default=0.10, ge=0, le=1)
    boundary_probability_upper: float = Field(default=0.90, ge=0, le=1)
    maximum_general_factor_fraction: float = Field(default=0.85, ge=0, le=1)
    minimum_marginal_axis_information: float = Field(default=1e-4, gt=0)
    minimum_informative_axis_count: int = Field(default=4, ge=1)
    maximum_mechanism_information_share: float = Field(default=0.60, gt=0, le=1)
    expected_groups_per_mechanism: int = Field(default=5, ge=1)
    expected_replicates_per_task: int = Field(default=5, ge=1)
    bootstrap_replicates: int = Field(default=400, ge=100)

    @model_validator(mode="after")
    def validate_thresholds(self) -> MechanismGeometryThresholds:
        if self.boundary_probability_lower >= self.boundary_probability_upper:
            raise ValueError("mechanism geometry boundary interval is empty")
        if self.minimum_informative_axis_count > len(CAPABILITY_AXES):
            raise ValueError("mechanism geometry requires too many informative axes")
        return self


class MechanismGeometrySource(FrozenModel):
    source_kind: SourceKind
    population_path: str = Field(min_length=1)
    population_sha256: str = Field(min_length=64, max_length=64)
    population_id: str = Field(min_length=1)
    contract_path: str = Field(min_length=1)
    contract_sha256: str = Field(min_length=64, max_length=64)
    contract_id: str = Field(min_length=1)
    report_path: str = Field(min_length=1)
    report_sha256: str = Field(min_length=64, max_length=64)
    report_id: str = Field(min_length=1)
    behavior_path: str = Field(min_length=1)
    behavior_sha256: str = Field(min_length=64, max_length=64)
    behavior_set_hash: str = Field(min_length=1)
    mechanism_ids: tuple[str, ...] = Field(min_length=1)
    requested_rollout_count: int = Field(ge=1)
    recorded_rollout_count: int = Field(ge=1)
    api_call_count: int = Field(ge=0)
    model_tokens: int = Field(ge=0)
    estimated_cost_usd: float = Field(ge=0)
    schema_version: str = MECHANISM_GEOMETRY_SOURCE_VERSION

    @model_validator(mode="after")
    def validate_source(self) -> MechanismGeometrySource:
        expected = (
            PRIOR_CONFIRMED_MECHANISM_IDS
            if self.source_kind == "v25_21_confirmation"
            else REPAIRED_MECHANISM_IDS
        )
        if self.mechanism_ids != expected:
            raise ValueError("mechanism geometry source changes confirmed mechanisms")
        if self.recorded_rollout_count != self.requested_rollout_count:
            raise ValueError("mechanism geometry source denominator is incomplete")
        return self


class FinanceMechanismGeometryContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    sources: tuple[MechanismGeometrySource, ...] = Field(min_length=2, max_length=2)
    confirmed_mechanism_ids: tuple[str, ...] = CONFIRMED_MECHANISM_IDS
    thresholds: MechanismGeometryThresholds = Field(default_factory=MechanismGeometryThresholds)
    random_seed: int
    response_variable: Literal["valid_success"] = "valid_success"
    geometry_population: Literal["mechanism_required_only"] = "mechanism_required_only"
    matched_controls_role: Literal["confirmation_only_excluded_from_geometry"] = (
        "confirmation_only_excluded_from_geometry"
    )
    outcome_conditioning: Literal["runtime_eligible_only"] = "runtime_eligible_only"
    demand_normalization: Literal["task_l2"] = "task_l2"
    raw_matrix_role: Literal["primary_authorizing"] = "primary_authorizing"
    residual_matrix_role: Literal["general_difficulty_robustness_gate"] = (
        "general_difficulty_robustness_gate"
    )
    implementation_manifest: dict[str, str]
    implementation_manifest_hash: str = Field(min_length=1)
    pro_api_calls_authorized: Literal[False] = False
    beneficiary_screening_authorized: Literal[False] = False
    exact_target_evaluated: Literal[False] = False
    gp_c_evaluated: Literal[False] = False
    production_contribution: float = Field(default=0, ge=0, le=0)
    next_permitted_stage: Literal["flash_mechanism_information_geometry"] = (
        "flash_mechanism_information_geometry"
    )
    schema_version: str = MECHANISM_GEOMETRY_CONTRACT_VERSION

    @model_validator(mode="after")
    def validate_contract(self) -> FinanceMechanismGeometryContract:
        if tuple(item.source_kind for item in self.sources) != (
            "v25_21_confirmation",
            "v25_22_repair_confirmation",
        ):
            raise ValueError("mechanism geometry source order or coverage is invalid")
        if self.confirmed_mechanism_ids != CONFIRMED_MECHANISM_IDS:
            raise ValueError("mechanism geometry changes the frozen mechanism set")
        if tuple(item for source in self.sources for item in source.mechanism_ids) != (
            self.confirmed_mechanism_ids
        ):
            raise ValueError("mechanism geometry source partition is incomplete")
        if not self.implementation_manifest:
            raise ValueError("mechanism geometry implementation manifest is empty")
        expected_implementation_hash = canonical_hash(
            self.implementation_manifest,
            prefix="finance_capability_mechanism_information_geometry_implementation:",
        )
        if self.implementation_manifest_hash != expected_implementation_hash:
            raise ValueError("mechanism geometry implementation manifest hash is invalid")
        if self.contract_id != mechanism_geometry_contract_id(self):
            raise ValueError("mechanism geometry contract identity is invalid")
        return self


class MechanismGeometryGate(FrozenModel):
    gate_id: str = Field(min_length=1)
    category: Literal[
        "source_coverage",
        "raw_information",
        "residual_information",
        "distribution_coverage",
    ]
    observed: float
    requirement: str = Field(min_length=1)
    passed: bool


class MechanismGeometrySpectrum(FrozenModel):
    task_count: int = Field(ge=1)
    rollout_count: int = Field(ge=1)
    distinct_normalized_demand_count: int = Field(ge=1)
    nonzero_weight_task_count: int = Field(ge=0)
    conditional_success_rate: float = Field(ge=0, le=1)
    boundary_task_fraction: float = Field(ge=0, le=1)
    raw_matrix: tuple[tuple[float, ...], ...]
    residual_matrix: tuple[tuple[float, ...], ...]
    raw_eigenvalues: tuple[float, ...]
    residual_eigenvalues: tuple[float, ...]
    raw_numerical_rank: int = Field(ge=0)
    raw_effective_rank: float = Field(ge=0)
    raw_condition_number: float = Field(ge=1)
    residual_numerical_rank: int = Field(ge=0)
    residual_effective_rank: float = Field(ge=0)
    residual_condition_number: float = Field(ge=1)
    general_factor_fraction: float = Field(ge=0, le=1)
    marginal_axis_information: dict[str, float]
    marginal_axis_intervals: dict[str, ConfidenceInterval]
    informative_axis_count: int = Field(ge=0)
    mechanism_task_count: dict[str, int]
    mechanism_group_count: dict[str, int]
    mechanism_success_rate: dict[str, float]
    mechanism_information_share: dict[str, float]
    maximum_mechanism_information_share: float = Field(ge=0, le=1)
    task_success_probability: dict[str, float]
    schema_version: str = MECHANISM_GEOMETRY_SPECTRUM_VERSION

    @model_validator(mode="after")
    def validate_spectrum(self) -> MechanismGeometrySpectrum:
        axes = set(CAPABILITY_AXES)
        if len(self.raw_matrix) != len(CAPABILITY_AXES) or any(
            len(row) != len(CAPABILITY_AXES) for row in self.raw_matrix
        ):
            raise ValueError("mechanism raw matrix shape is invalid")
        if len(self.residual_matrix) != len(CAPABILITY_AXES) or any(
            len(row) != len(CAPABILITY_AXES) for row in self.residual_matrix
        ):
            raise ValueError("mechanism residual matrix shape is invalid")
        if set(self.marginal_axis_information) != axes:
            raise ValueError("mechanism marginal information is incomplete")
        if set(self.marginal_axis_intervals) != axes:
            raise ValueError("mechanism marginal intervals are incomplete")
        mechanism_keys = set(CONFIRMED_MECHANISM_IDS)
        for values in (
            self.mechanism_task_count,
            self.mechanism_group_count,
            self.mechanism_success_rate,
            self.mechanism_information_share,
        ):
            if set(values) != mechanism_keys:
                raise ValueError("mechanism spectrum coverage is incomplete")
        if not math.isclose(
            self.maximum_mechanism_information_share,
            max(self.mechanism_information_share.values()),
            abs_tol=1e-12,
        ):
            raise ValueError("maximum mechanism information share is inconsistent")
        return self


class FinanceMechanismGeometryReport(FrozenModel):
    report_id: str = Field(min_length=1)
    contract_id: str = Field(min_length=1)
    source_report_ids: tuple[str, ...] = Field(min_length=2, max_length=2)
    source_rollout_count: int = Field(ge=1)
    geometry_task_count: int = Field(ge=1)
    geometry_rollout_count: int = Field(ge=1)
    confirmed_mechanism_ids: tuple[str, ...] = CONFIRMED_MECHANISM_IDS
    spectrum: MechanismGeometrySpectrum
    gates: tuple[MechanismGeometryGate, ...] = Field(min_length=10)
    information_geometry_ready: bool
    failure_codes: tuple[str, ...]
    source_api_call_count: int = Field(ge=0)
    source_model_tokens: int = Field(ge=0)
    source_estimated_cost_usd: float = Field(ge=0)
    geometry_api_call_count: Literal[0] = 0
    gpu_jobs: Literal[0] = 0
    pro_sparse_anchor_authorized: bool
    beneficiary_screening_authorized: Literal[False] = False
    exact_target_evaluated: Literal[False] = False
    gp_c_evaluated: Literal[False] = False
    production_contribution: float = Field(default=0, ge=0, le=0)
    next_permitted_stage: Literal[
        "pro_sparse_anchor_preparation",
        "capability_mechanism_support_redesign_only",
    ]
    schema_version: str = MECHANISM_GEOMETRY_REPORT_VERSION

    @model_validator(mode="after")
    def validate_report(self) -> FinanceMechanismGeometryReport:
        ready = all(item.passed for item in self.gates)
        if self.information_geometry_ready != ready:
            raise ValueError("mechanism geometry readiness is inconsistent")
        if self.pro_sparse_anchor_authorized != ready:
            raise ValueError("mechanism geometry Pro authorization is inconsistent")
        expected = (
            "pro_sparse_anchor_preparation"
            if ready
            else "capability_mechanism_support_redesign_only"
        )
        if self.next_permitted_stage != expected:
            raise ValueError("mechanism geometry transition is not fail-closed")
        if self.report_id != mechanism_geometry_report_id(self):
            raise ValueError("mechanism geometry report identity is invalid")
        return self


@dataclass(frozen=True)
class _GeometryRow:
    task_id: str
    group_id: str
    mechanism_id: str
    probability: float
    general_difficulty: float
    demand: tuple[float, ...]
    realizations: tuple[int, ...]


def mechanism_geometry_contract_id(value: FinanceMechanismGeometryContract) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"contract_id"}),
        prefix="finance_capability_mechanism_information_geometry_contract:",
    )


def mechanism_geometry_report_id(value: FinanceMechanismGeometryReport) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"report_id"}),
        prefix="finance_capability_mechanism_information_geometry_report:",
    )


def prepare_mechanism_geometry_contract(
    *,
    prior_population_path: Path,
    prior_contract_path: Path,
    prior_report_path: Path,
    prior_behavior_path: Path,
    repair_population_path: Path,
    repair_contract_path: Path,
    repair_report_path: Path,
    repair_behavior_path: Path,
    output_path: Path,
    run_id: str,
    random_seed: int,
) -> FinanceMechanismGeometryContract:
    if output_path.exists():
        raise ValueError("mechanism geometry contract is immutable")
    sources = (
        _load_source(
            "v25_21_confirmation",
            prior_population_path,
            prior_contract_path,
            prior_report_path,
            prior_behavior_path,
        )[0],
        _load_source(
            "v25_22_repair_confirmation",
            repair_population_path,
            repair_contract_path,
            repair_report_path,
            repair_behavior_path,
        )[0],
    )
    implementation = _implementation_manifest()
    values = {
        "run_id": run_id,
        "sources": sources,
        "random_seed": random_seed,
        "implementation_manifest": implementation,
        "implementation_manifest_hash": canonical_hash(
            implementation,
            prefix="finance_capability_mechanism_information_geometry_implementation:",
        ),
    }
    provisional = FinanceMechanismGeometryContract.model_construct(contract_id="pending", **values)
    contract = FinanceMechanismGeometryContract(
        contract_id=mechanism_geometry_contract_id(provisional), **values
    )
    _write_json(output_path, contract.model_dump(mode="json"))
    return contract


def run_mechanism_geometry(
    *,
    contract_path: Path,
    output_path: Path,
    markdown_path: Path,
) -> FinanceMechanismGeometryReport:
    if output_path.exists() or markdown_path.exists():
        raise ValueError("mechanism geometry report is immutable")
    contract = FinanceMechanismGeometryContract.model_validate_json(
        contract_path.read_text(encoding="utf-8")
    )
    implementation = _implementation_manifest()
    if implementation != contract.implementation_manifest:
        raise ValueError("mechanism geometry implementation changed after freeze")
    rows: list[_GeometryRow] = []
    replayed_sources = []
    for source in contract.sources:
        descriptor, source_rows = _load_source(
            source.source_kind,
            Path(source.population_path),
            Path(source.contract_path),
            Path(source.report_path),
            Path(source.behavior_path),
        )
        if descriptor != source:
            raise ValueError("mechanism geometry source changed after contract freeze")
        replayed_sources.append(descriptor)
        rows.extend(source_rows)
    spectrum = _make_spectrum(
        rows,
        thresholds=contract.thresholds,
        seed=contract.random_seed,
    )
    gates = _make_gates(spectrum, contract.thresholds)
    ready = all(item.passed for item in gates)
    values = {
        "contract_id": contract.contract_id,
        "source_report_ids": tuple(item.report_id for item in replayed_sources),
        "source_rollout_count": sum(item.recorded_rollout_count for item in replayed_sources),
        "geometry_task_count": spectrum.task_count,
        "geometry_rollout_count": spectrum.rollout_count,
        "spectrum": spectrum,
        "gates": gates,
        "information_geometry_ready": ready,
        "failure_codes": tuple(item.gate_id for item in gates if not item.passed),
        "source_api_call_count": sum(item.api_call_count for item in replayed_sources),
        "source_model_tokens": sum(item.model_tokens for item in replayed_sources),
        "source_estimated_cost_usd": sum(item.estimated_cost_usd for item in replayed_sources),
        "pro_sparse_anchor_authorized": ready,
        "next_permitted_stage": (
            "pro_sparse_anchor_preparation"
            if ready
            else "capability_mechanism_support_redesign_only"
        ),
    }
    provisional = FinanceMechanismGeometryReport.model_construct(report_id="pending", **values)
    report = FinanceMechanismGeometryReport(
        report_id=mechanism_geometry_report_id(provisional), **values
    )
    _write_json(output_path, report.model_dump(mode="json"))
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text(_render_markdown(report), encoding="utf-8")
    return report


def _load_source(
    kind: SourceKind,
    population_path: Path,
    contract_path: Path,
    report_path: Path,
    behavior_path: Path,
) -> tuple[MechanismGeometrySource, tuple[_GeometryRow, ...]]:
    if kind == "v25_21_confirmation":
        population = CapabilityMechanismConfirmationPopulation.model_validate_json(
            population_path.read_text(encoding="utf-8")
        )
        contract = FinanceCapabilityMechanismConfirmationContract.model_validate_json(
            contract_path.read_text(encoding="utf-8")
        )
        report = FinanceCapabilityMechanismConfirmationReport.model_validate_json(
            report_path.read_text(encoding="utf-8")
        )
        mechanism_ids = PRIOR_CONFIRMED_MECHANISM_IDS
        if (
            tuple(report.confirmed_mechanism_ids) != mechanism_ids
            or report.information_geometry_authorized
        ):
            raise ValueError("v25.21 source does not preserve its partial confirmation result")
        if contract.source_population_id != population.population_id:
            raise ValueError("v25.21 contract/population identity differs")
        _validate_prior_source_chain(population, contract, population_path)
    else:
        population = CapabilityMechanismRepairPopulation.model_validate_json(
            population_path.read_text(encoding="utf-8")
        )
        contract = FinanceCapabilityMechanismRepairContract.model_validate_json(
            contract_path.read_text(encoding="utf-8")
        )
        report = FinanceCapabilityMechanismRepairReport.model_validate_json(
            report_path.read_text(encoding="utf-8")
        )
        mechanism_ids = REPAIRED_MECHANISM_IDS
        if (
            tuple(report.selected_or_confirmed_mechanism_ids) != mechanism_ids
            or not report.information_geometry_authorized
        ):
            raise ValueError("v25.22 source does not authorize combined geometry")
        if contract.source_population_id != population.population_id:
            raise ValueError("v25.22 contract/population identity differs")
        _validate_repair_source_chain(population, contract, population_path)
    if report.contract_id != contract.contract_id:
        raise ValueError("mechanism geometry report/contract identity differs")
    if report.recorded_rollout_count != report.requested_rollout_count:
        raise ValueError("mechanism geometry source report denominator is incomplete")
    observations = _load_behaviors(behavior_path)
    expected = {
        (binding.binding_id, replicate)
        for binding in contract.bindings
        for replicate in range(contract.replicas)
    }
    observed = {(item.binding_id, item.replicate) for item in observations}
    if len(observed) != len(observations) or observed != expected:
        raise ValueError("mechanism geometry behavior denominator differs from contract")
    binding_by_id = {item.binding_id: item for item in contract.bindings}
    for item in observations:
        binding = binding_by_id[item.binding_id]
        task_id = binding.task_artifact_id
        if (
            item.contract_id != contract.contract_id
            or item.task_artifact_id != task_id
            or item.group_id != contract.task_group_ids[task_id]
            or item.mechanism_id != contract.task_mechanism_ids[task_id]
            or item.mechanism_tier != contract.task_mechanism_tiers[task_id]
            or item.variant_role != contract.task_variant_roles[task_id]
        ):
            raise ValueError("mechanism geometry behavior identity differs from binding")
        if not item.runtime_eligible:
            raise ValueError("mechanism geometry source contains an ineligible Runtime outcome")
    rows = _geometry_rows(contract, observations, mechanism_ids)
    descriptor = MechanismGeometrySource(
        source_kind=kind,
        population_path=str(population_path.resolve()),
        population_sha256=_sha256(population_path),
        population_id=population.population_id,
        contract_path=str(contract_path.resolve()),
        contract_sha256=_sha256(contract_path),
        contract_id=contract.contract_id,
        report_path=str(report_path.resolve()),
        report_sha256=_sha256(report_path),
        report_id=report.report_id,
        behavior_path=str(behavior_path.resolve()),
        behavior_sha256=_sha256(behavior_path),
        behavior_set_hash=_behavior_set_hash(observations),
        mechanism_ids=mechanism_ids,
        requested_rollout_count=report.requested_rollout_count,
        recorded_rollout_count=report.recorded_rollout_count,
        api_call_count=report.api_call_count,
        model_tokens=report.total_model_tokens,
        estimated_cost_usd=report.estimated_cost_usd,
    )
    return descriptor, rows


def _validate_prior_source_chain(
    population: CapabilityMechanismConfirmationPopulation,
    contract: FinanceCapabilityMechanismConfirmationContract,
    population_path: Path,
) -> None:
    _require_same_file(
        Path(contract.source_population_path),
        population_path,
        "v25.21 contract population",
    )
    _validate_path_hash_fields(
        population.model_dump(mode="json"),
        label="v25.21 population",
    )
    _validate_path_hash_fields(
        contract.model_dump(mode="json"),
        label="v25.21 contract",
    )
    freeze = MechanismSelectionFreeze.model_validate_json(
        Path(population.source_selection_freeze_path).read_text(encoding="utf-8")
    )
    if freeze.freeze_id != population.source_selection_freeze_id:
        raise ValueError("v25.21 population selection freeze identity differs")
    _validate_path_hash_fields(
        freeze.model_dump(mode="json"),
        label="v25.21 selection freeze",
    )
    _validate_source_implementation_manifest(
        contract.implementation_manifest,
        contract.implementation_manifest_hash,
        prefix="finance_capability_mechanism_confirmation_implementation:",
        label="v25.21 contract",
    )
    _require_json_identity(
        Path(contract.source_v25_20_contract_path),
        "contract_id",
        contract.source_v25_20_contract_id,
        "v25.21 source runtime contract",
    )


def _validate_repair_source_chain(
    population: CapabilityMechanismRepairPopulation,
    contract: FinanceCapabilityMechanismRepairContract,
    population_path: Path,
) -> None:
    _require_same_file(
        Path(contract.source_population_path),
        population_path,
        "v25.22 contract population",
    )
    _validate_path_hash_fields(
        population.model_dump(mode="json"),
        label="v25.22 population",
    )
    _validate_path_hash_fields(
        contract.model_dump(mode="json"),
        label="v25.22 contract",
    )
    if set(population.exclusion_population_sha256) != set(
        population.exclusion_population_paths
    ):
        raise ValueError("v25.22 exclusion population hash coverage differs")
    for path_value in population.exclusion_population_paths:
        _require_hash(
            Path(path_value),
            population.exclusion_population_sha256[path_value],
            "v25.22 exclusion population",
        )
    freeze_path = Path(str(population.selection_freeze_path))
    freeze = MechanismRepairSelectionFreeze.model_validate_json(
        freeze_path.read_text(encoding="utf-8")
    )
    if freeze.freeze_id != population.selection_freeze_id:
        raise ValueError("v25.22 population selection freeze identity differs")
    if (
        Path(str(contract.source_selection_freeze_path)).resolve() != freeze_path.resolve()
        or contract.source_selection_freeze_sha256 != population.selection_freeze_sha256
        or contract.source_selection_freeze_id != population.selection_freeze_id
    ):
        raise ValueError("v25.22 population and contract selection freeze differ")
    _validate_path_hash_fields(
        freeze.model_dump(mode="json"),
        label="v25.22 selection freeze",
    )
    _validate_source_implementation_manifest(
        contract.implementation_manifest,
        contract.implementation_manifest_hash,
        prefix="finance_capability_mechanism_repair_implementation:",
        label="v25.22 contract",
    )
    _require_json_identity(
        Path(contract.source_v25_20_contract_path),
        "contract_id",
        contract.source_v25_20_contract_id,
        "v25.22 source runtime contract",
    )


def _validate_path_hash_fields(value: Mapping[str, object], *, label: str) -> None:
    for key, path_value in value.items():
        if not key.endswith("_path") or not isinstance(path_value, str):
            continue
        hash_key = f"{key[:-5]}_sha256"
        expected = value.get(hash_key)
        if not isinstance(expected, str):
            raise ValueError(f"{label} lacks {hash_key}")
        _require_hash(Path(path_value), expected, f"{label}:{key}")


def _require_hash(path: Path, expected: str, label: str) -> None:
    if not path.is_file() or _sha256(path) != expected:
        raise ValueError(f"{label} changed after freeze:{path}")


def _require_same_file(left: Path, right: Path, label: str) -> None:
    if left.resolve() != right.resolve():
        raise ValueError(f"{label} path differs from the geometry source")


def _require_json_identity(
    path: Path,
    field: str,
    expected: str,
    label: str,
) -> None:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, Mapping) or raw.get(field) != expected:
        raise ValueError(f"{label} identity differs")


def _validate_source_implementation_manifest(
    manifest: Mapping[str, str],
    observed_hash: str,
    *,
    prefix: str,
    label: str,
) -> None:
    if not manifest or canonical_hash(dict(manifest), prefix=prefix) != observed_hash:
        raise ValueError(f"{label} implementation manifest identity differs")


def _geometry_rows(
    contract: FinanceCapabilityMechanismConfirmationContract
    | FinanceCapabilityMechanismRepairContract,
    observations: Sequence[MechanismBehaviorObservation],
    mechanism_ids: tuple[str, ...],
) -> tuple[_GeometryRow, ...]:
    task_by_id = {item.artifact_id: item for item in contract.tasks}
    binding_by_task = {item.task_artifact_id: item for item in contract.bindings}
    grouped: dict[str, list[MechanismBehaviorObservation]] = defaultdict(list)
    for item in observations:
        if item.mechanism_id in mechanism_ids and item.variant_role == "mechanism_required":
            grouped[item.task_artifact_id].append(item)
    rows = []
    for task_id, values in sorted(grouped.items()):
        if len(values) != contract.replicas:
            raise ValueError("mechanism geometry task has an incomplete replica denominator")
        task = task_by_id[task_id]
        binding = binding_by_task[task_id]
        realizations = tuple(int(item.valid_success) for item in values)
        rows.append(
            _GeometryRow(
                task_id=task_id,
                group_id=values[0].group_id,
                mechanism_id=values[0].mechanism_id,
                probability=sum(realizations) / len(realizations),
                general_difficulty=binding.general_difficulty,
                demand=_normalize_demand(task.capability_demand.values),
                realizations=realizations,
            )
        )
    return tuple(rows)


def _make_spectrum(
    rows: Sequence[_GeometryRow],
    *,
    thresholds: MechanismGeometryThresholds,
    seed: int,
) -> MechanismGeometrySpectrum:
    if not rows:
        raise ValueError("mechanism geometry has no rows")
    raw, residual, general_fraction = _matrices(rows)
    raw_values = _eigenvalues(raw)
    residual_values = _eigenvalues(residual)
    raw_positive = _positive_eigenvalues(raw_values)
    residual_positive = _positive_eigenvalues(residual_values)
    intervals = _bootstrap_axis_intervals(
        rows,
        replicates=thresholds.bootstrap_replicates,
        seed=seed,
    )
    weights = [item.probability * (1 - item.probability) for item in rows]
    total_weight = sum(weights)
    mechanism_weight = {
        mechanism_id: sum(
            weight
            for row, weight in zip(rows, weights, strict=True)
            if row.mechanism_id == mechanism_id
        )
        for mechanism_id in CONFIRMED_MECHANISM_IDS
    }
    shares = {
        key: value / total_weight if total_weight else 0.0
        for key, value in mechanism_weight.items()
    }
    mechanism_rows = {
        mechanism_id: tuple(item for item in rows if item.mechanism_id == mechanism_id)
        for mechanism_id in CONFIRMED_MECHANISM_IDS
    }
    return MechanismGeometrySpectrum(
        task_count=len(rows),
        rollout_count=sum(len(item.realizations) for item in rows),
        distinct_normalized_demand_count=len(
            {tuple(round(value, 12) for value in item.demand) for item in rows}
        ),
        nonzero_weight_task_count=sum(value > 0 for value in weights),
        conditional_success_rate=fmean(item.probability for item in rows),
        boundary_task_fraction=sum(
            thresholds.boundary_probability_lower
            <= item.probability
            <= thresholds.boundary_probability_upper
            for item in rows
        )
        / len(rows),
        raw_matrix=raw,
        residual_matrix=residual,
        raw_eigenvalues=raw_values,
        residual_eigenvalues=residual_values,
        raw_numerical_rank=len(raw_positive),
        raw_effective_rank=_effective_rank(raw_positive),
        raw_condition_number=_condition_number(raw_positive),
        residual_numerical_rank=len(residual_positive),
        residual_effective_rank=_effective_rank(residual_positive),
        residual_condition_number=_condition_number(residual_positive),
        general_factor_fraction=general_fraction,
        marginal_axis_information={
            axis: raw[index][index] for index, axis in enumerate(CAPABILITY_AXES)
        },
        marginal_axis_intervals=intervals,
        informative_axis_count=sum(
            intervals[axis].lower >= thresholds.minimum_marginal_axis_information
            for axis in CAPABILITY_AXES
        ),
        mechanism_task_count={key: len(value) for key, value in mechanism_rows.items()},
        mechanism_group_count={
            key: len({item.group_id for item in value}) for key, value in mechanism_rows.items()
        },
        mechanism_success_rate={
            key: fmean(item.probability for item in value) for key, value in mechanism_rows.items()
        },
        mechanism_information_share=shares,
        maximum_mechanism_information_share=max(shares.values()),
        task_success_probability={item.task_id: item.probability for item in rows},
    )


def _make_gates(
    spectrum: MechanismGeometrySpectrum,
    thresholds: MechanismGeometryThresholds,
) -> tuple[MechanismGeometryGate, ...]:
    expected_tasks = len(CONFIRMED_MECHANISM_IDS) * thresholds.expected_groups_per_mechanism
    expected_rollouts = expected_tasks * thresholds.expected_replicates_per_task
    values = (
        (
            "complete_mechanism_task_denominator",
            spectrum.task_count == expected_tasks,
            spectrum.task_count,
            f"={expected_tasks}",
            "source_coverage",
        ),
        (
            "complete_mechanism_rollout_denominator",
            spectrum.rollout_count == expected_rollouts,
            spectrum.rollout_count,
            f"={expected_rollouts}",
            "source_coverage",
        ),
        (
            "balanced_mechanism_group_coverage",
            all(
                value == thresholds.expected_groups_per_mechanism
                for value in spectrum.mechanism_group_count.values()
            ),
            min(spectrum.mechanism_group_count.values()),
            f"={thresholds.expected_groups_per_mechanism}",
            "source_coverage",
        ),
        (
            "distinct_normalized_demand_coverage",
            spectrum.distinct_normalized_demand_count >= thresholds.minimum_rank,
            spectrum.distinct_normalized_demand_count,
            f">={thresholds.minimum_rank}",
            "distribution_coverage",
        ),
        (
            "boundary_task_fraction",
            spectrum.boundary_task_fraction >= thresholds.minimum_boundary_task_fraction,
            spectrum.boundary_task_fraction,
            f">={thresholds.minimum_boundary_task_fraction}",
            "distribution_coverage",
        ),
        (
            "raw_numerical_rank",
            spectrum.raw_numerical_rank >= thresholds.minimum_rank,
            spectrum.raw_numerical_rank,
            f">={thresholds.minimum_rank}",
            "raw_information",
        ),
        (
            "raw_effective_rank",
            spectrum.raw_effective_rank >= thresholds.minimum_effective_rank,
            spectrum.raw_effective_rank,
            f">={thresholds.minimum_effective_rank}",
            "raw_information",
        ),
        (
            "raw_condition_number",
            spectrum.raw_condition_number <= thresholds.maximum_condition_number,
            spectrum.raw_condition_number,
            f"<={thresholds.maximum_condition_number}",
            "raw_information",
        ),
        (
            "residual_numerical_rank",
            spectrum.residual_numerical_rank >= thresholds.minimum_rank,
            spectrum.residual_numerical_rank,
            f">={thresholds.minimum_rank}",
            "residual_information",
        ),
        (
            "residual_effective_rank",
            spectrum.residual_effective_rank >= thresholds.minimum_effective_rank,
            spectrum.residual_effective_rank,
            f">={thresholds.minimum_effective_rank}",
            "residual_information",
        ),
        (
            "residual_condition_number",
            spectrum.residual_condition_number <= thresholds.maximum_condition_number,
            spectrum.residual_condition_number,
            f"<={thresholds.maximum_condition_number}",
            "residual_information",
        ),
        (
            "general_factor_fraction",
            spectrum.general_factor_fraction <= thresholds.maximum_general_factor_fraction,
            spectrum.general_factor_fraction,
            f"<={thresholds.maximum_general_factor_fraction}",
            "residual_information",
        ),
        (
            "informative_axis_count",
            spectrum.informative_axis_count >= thresholds.minimum_informative_axis_count,
            spectrum.informative_axis_count,
            f">={thresholds.minimum_informative_axis_count}",
            "raw_information",
        ),
        (
            "mechanism_information_dominance",
            spectrum.maximum_mechanism_information_share
            <= thresholds.maximum_mechanism_information_share,
            spectrum.maximum_mechanism_information_share,
            f"<={thresholds.maximum_mechanism_information_share}",
            "distribution_coverage",
        ),
    )
    return tuple(
        MechanismGeometryGate(
            gate_id=gate_id,
            category=category,
            observed=float(observed),
            requirement=requirement,
            passed=passed,
        )
        for gate_id, passed, observed, requirement, category in values
    )


def _matrices(
    rows: Sequence[_GeometryRow],
) -> tuple[
    tuple[tuple[float, ...], ...],
    tuple[tuple[float, ...], ...],
    float,
]:
    demands = [list(item.demand) for item in rows]
    weights = [item.probability * (1 - item.probability) for item in rows]
    centered = _center_columns(demands, weights)
    residual_values = _residualize(
        centered,
        [item.general_difficulty for item in rows],
        weights,
    )
    raw = _weighted_second_moment(demands, weights)
    centered_matrix = _weighted_second_moment(centered, weights)
    residual = _weighted_second_moment(residual_values, weights)
    centered_trace = _trace(centered_matrix)
    residual_trace = _trace(residual)
    fraction = min(1.0, max(0.0, 1 - residual_trace / centered_trace)) if centered_trace else 1.0
    return raw, residual, fraction


def _normalize_demand(values: Mapping[str, float]) -> tuple[float, ...]:
    raw = tuple(float(values[axis]) for axis in CAPABILITY_AXES)
    norm = math.sqrt(sum(value * value for value in raw))
    if norm <= 0:
        raise ValueError("mechanism geometry demand vector is empty")
    return tuple(value / norm for value in raw)


def _center_columns(
    values: Sequence[Sequence[float]],
    weights: Sequence[float],
) -> list[list[float]]:
    means = [
        _weighted_mean([row[index] for row in values], weights)
        for index in range(len(values[0]))
    ]
    return [[value - means[index] for index, value in enumerate(row)] for row in values]


def _residualize(
    values: Sequence[Sequence[float]],
    general: Sequence[float],
    weights: Sequence[float],
) -> list[list[float]]:
    mean_general = _weighted_mean(general, weights)
    centered_general = [value - mean_general for value in general]
    variance = sum(
        weight * value * value
        for weight, value in zip(weights, centered_general, strict=True)
    )
    if variance <= 1e-15:
        return [list(row) for row in values]
    output = [[0.0 for _ in row] for row in values]
    for axis in range(len(values[0])):
        slope = (
            sum(
                weights[index] * centered_general[index] * row[axis]
                for index, row in enumerate(values)
            )
            / variance
        )
        for index, row in enumerate(values):
            output[index][axis] = row[axis] - slope * centered_general[index]
    return output


def _weighted_mean(values: Sequence[float], weights: Sequence[float]) -> float:
    if len(values) != len(weights) or not values:
        raise ValueError("weighted geometry inputs are incomplete")
    if any(weight < 0 for weight in weights):
        raise ValueError("weighted geometry contains a negative information weight")
    total = sum(weights)
    if total <= 1e-15:
        return fmean(values)
    return sum(
        value * weight for value, weight in zip(values, weights, strict=True)
    ) / total


def _weighted_second_moment(
    values: Sequence[Sequence[float]], weights: Sequence[float]
) -> tuple[tuple[float, ...], ...]:
    size = len(values[0])
    matrix = [[0.0 for _ in range(size)] for _ in range(size)]
    for value, weight in zip(values, weights, strict=True):
        for row in range(size):
            for column in range(size):
                matrix[row][column] += weight * value[row] * value[column] / len(values)
    return tuple(tuple(row) for row in matrix)


def _eigenvalues(matrix: Sequence[Sequence[float]]) -> tuple[float, ...]:
    values = sorted(_symmetric_eigenvalues([list(row) for row in matrix]), reverse=True)
    return tuple(0.0 if abs(value) <= 1e-15 else max(0.0, value) for value in values)


def _positive_eigenvalues(values: Sequence[float]) -> tuple[float, ...]:
    maximum = max(values, default=0.0)
    tolerance = max(1e-12, maximum * 1e-6)
    return tuple(value for value in values if maximum > tolerance and value > tolerance)


def _effective_rank(values: Sequence[float]) -> float:
    total = sum(values)
    if total <= 0:
        return 0.0
    probabilities = [value / total for value in values]
    return math.exp(-sum(value * math.log(value) for value in probabilities if value > 0))


def _condition_number(values: Sequence[float]) -> float:
    return values[0] / values[-1] if values else 1e12


def _trace(matrix: Sequence[Sequence[float]]) -> float:
    return sum(matrix[index][index] for index in range(len(matrix)))


def _bootstrap_axis_intervals(
    rows: Sequence[_GeometryRow],
    *,
    replicates: int,
    seed: int,
) -> dict[str, ConfidenceInterval]:
    rng = random.Random(seed)
    by_mechanism = {
        mechanism_id: tuple(item for item in rows if item.mechanism_id == mechanism_id)
        for mechanism_id in CONFIRMED_MECHANISM_IDS
    }
    point_raw, _, _ = _matrices(rows)
    points = {axis: point_raw[index][index] for index, axis in enumerate(CAPABILITY_AXES)}
    samples: dict[str, list[float]] = {axis: [] for axis in CAPABILITY_AXES}
    for _ in range(replicates):
        resampled = []
        for mechanism_rows in by_mechanism.values():
            for _ in range(len(mechanism_rows)):
                row = rng.choice(mechanism_rows)
                realizations = tuple(
                    rng.choice(row.realizations) for _ in range(len(row.realizations))
                )
                resampled.append(
                    _GeometryRow(
                        task_id=row.task_id,
                        group_id=row.group_id,
                        mechanism_id=row.mechanism_id,
                        probability=sum(realizations) / len(realizations),
                        general_difficulty=row.general_difficulty,
                        demand=row.demand,
                        realizations=realizations,
                    )
                )
        raw, _, _ = _matrices(resampled)
        for index, axis in enumerate(CAPABILITY_AXES):
            samples[axis].append(raw[index][index])
    return {
        axis: ConfidenceInterval(
            lower=min(_quantile(values, 0.025), points[axis]),
            point=points[axis],
            upper=max(_quantile(values, 0.975), points[axis]),
        )
        for axis, values in samples.items()
    }


def _quantile(values: Sequence[float], probability: float) -> float:
    ordered = sorted(values)
    position = probability * (len(ordered) - 1)
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def _load_behaviors(path: Path) -> tuple[MechanismBehaviorObservation, ...]:
    with path.open(encoding="utf-8") as handle:
        return tuple(
            MechanismBehaviorObservation.model_validate_json(line)
            for line in handle
            if line.strip()
        )


def _behavior_set_hash(
    values: Sequence[MechanismBehaviorObservation],
) -> str:
    ordered = sorted(values, key=lambda item: (item.binding_id, item.replicate))
    return canonical_hash(
        [item.model_dump(mode="json") for item in ordered],
        prefix="finance_capability_mechanism_information_geometry_behavior_set:",
    )


def _implementation_manifest() -> dict[str, str]:
    root = Path(__file__).resolve().parents[4]
    paths = (
        Path(__file__).resolve(),
        Path(__file__).with_name("phase1_capability_boundary_analysis.py"),
        Path(__file__).with_name("phase1_capability_mechanism_confirmation.py"),
        Path(__file__).with_name("phase1_capability_mechanism_flash_development.py"),
        Path(__file__).with_name("phase1_capability_mechanism_repair.py"),
        Path(__file__).with_name("phase1_capability_sensitive_frontier.py"),
        root / "src/trusted_synthesis/hashing.py",
    )
    return {str(path.relative_to(root)): _sha256(path) for path in sorted(paths)}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_json(path: Path, value: object) -> None:
    if path.exists():
        raise ValueError(f"immutable output exists:{path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _render_markdown(report: FinanceMechanismGeometryReport) -> str:
    spectrum = report.spectrum
    lines = [
        "# Finance v25.23 Capability Mechanism Information Geometry",
        "",
        "This stage replays two independent held-out Confirmation sources. "
        "No model API or GPU was used by the geometry computation.",
        "",
        "## Decision",
        "",
        f"- Information geometry ready: **{report.information_geometry_ready}**",
        f"- Next permitted stage: `{report.next_permitted_stage}`",
        f"- Geometry tasks / rollouts: {report.geometry_task_count} / "
        f"{report.geometry_rollout_count}",
        f"- Raw rank / effective rank / condition: "
        f"{spectrum.raw_numerical_rank} / {spectrum.raw_effective_rank:.6f} / "
        f"{spectrum.raw_condition_number:.6f}",
        f"- Residual rank / effective rank / condition: "
        f"{spectrum.residual_numerical_rank} / "
        f"{spectrum.residual_effective_rank:.6f} / "
        f"{spectrum.residual_condition_number:.6f}",
        f"- Boundary task fraction: {spectrum.boundary_task_fraction:.4%}",
        f"- Informative axes: {spectrum.informative_axis_count}/{len(CAPABILITY_AXES)}",
        f"- Maximum mechanism information share: "
        f"{spectrum.maximum_mechanism_information_share:.4%}",
        "",
        "## Gates",
        "",
        "| Gate | Observed | Requirement | Passed |",
        "| --- | ---: | ---: | :---: |",
    ]
    lines.extend(
        f"| {item.gate_id} | {item.observed:.8g} | {item.requirement} | "
        f"{'yes' if item.passed else 'no'} |"
        for item in report.gates
    )
    lines.extend(
        [
            "",
            "## Claim Boundary",
            "",
            "Mechanism confirmation is necessary but not sufficient for a "
            "well-conditioned capability distribution. A failed geometry result "
            "does not invalidate the four mechanisms; it blocks Pro anchors, "
            "Beneficiary screening, Exact Target, GP-C, and Contribution.",
            "",
            "Source cost values are inherited telemetry estimates, not provider invoices.",
            "",
        ]
    )
    return "\n".join(lines)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    prepare = subparsers.add_parser("prepare")
    prepare.add_argument("--prior-population", type=Path, required=True)
    prepare.add_argument("--prior-contract", type=Path, required=True)
    prepare.add_argument("--prior-report", type=Path, required=True)
    prepare.add_argument("--prior-behaviors", type=Path, required=True)
    prepare.add_argument("--repair-population", type=Path, required=True)
    prepare.add_argument("--repair-contract", type=Path, required=True)
    prepare.add_argument("--repair-report", type=Path, required=True)
    prepare.add_argument("--repair-behaviors", type=Path, required=True)
    prepare.add_argument("--output", type=Path, required=True)
    prepare.add_argument("--run-id", required=True)
    prepare.add_argument("--random-seed", type=int, default=2523)
    run = subparsers.add_parser("run")
    run.add_argument("--contract", type=Path, required=True)
    run.add_argument("--output", type=Path, required=True)
    run.add_argument("--markdown", type=Path, required=True)
    return parser


def main() -> None:
    args = _parser().parse_args()
    if args.command == "prepare":
        contract = prepare_mechanism_geometry_contract(
            prior_population_path=args.prior_population,
            prior_contract_path=args.prior_contract,
            prior_report_path=args.prior_report,
            prior_behavior_path=args.prior_behaviors,
            repair_population_path=args.repair_population,
            repair_contract_path=args.repair_contract,
            repair_report_path=args.repair_report,
            repair_behavior_path=args.repair_behaviors,
            output_path=args.output,
            run_id=args.run_id,
            random_seed=args.random_seed,
        )
        print(
            json.dumps(
                {
                    "contract_id": contract.contract_id,
                    "confirmed_mechanism_ids": contract.confirmed_mechanism_ids,
                    "next_permitted_stage": contract.next_permitted_stage,
                },
                indent=2,
            )
        )
    else:
        report = run_mechanism_geometry(
            contract_path=args.contract,
            output_path=args.output,
            markdown_path=args.markdown,
        )
        print(
            json.dumps(
                {
                    "report_id": report.report_id,
                    "information_geometry_ready": report.information_geometry_ready,
                    "failure_codes": report.failure_codes,
                    "next_permitted_stage": report.next_permitted_stage,
                },
                indent=2,
            )
        )


if __name__ == "__main__":
    main()
