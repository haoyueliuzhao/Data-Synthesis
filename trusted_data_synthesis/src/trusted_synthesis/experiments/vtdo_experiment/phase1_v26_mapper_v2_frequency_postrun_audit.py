from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Final, Literal, cast

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from trusted_synthesis.canonical_json import strict_canonical_hash
from trusted_synthesis.core.trajectory.reachability_frequency_v2 import (
    ReachabilityFrequencySummaryV2,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_reachability_postrun_audit as independent,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_mapper_v2_frequency_preflight_inputs as preflight_inputs,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_mapper_v2_frequency_static as preflight_static,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_mapper_v2_reachability_frequency_execution as execution,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_mapper_v2_frequency_preflight_models import (  # noqa: E501
    FrequencyManifest,
    FrequencyRunnerContract,
    TaskConditionCellCatalogV2,
)
from trusted_synthesis.runtime.agent import prospective_reachability_runner_vnext as runner_vnext

RUN_ID: Final = "finance_v26_162_mapper_v2_frequency_postrun_audit_v1_20260827"
OUTPUT_DIR: Final = (
    "artifacts/vtdo_experiment/finance_v26_162_mapper_v2_frequency_postrun_audit_v1_20260827"
)
IMPLEMENTATION_PATH: Final = (
    "src/trusted_synthesis/experiments/vtdo_experiment/"
    "phase1_v26_mapper_v2_frequency_postrun_audit.py"
)
EXECUTION_DIR: Final = execution.OUTPUT_DIR
NEXT_STAGE: Final = "fresh_bounded_policy_endpoint_frequency_preflight_only"

EXPECTED_REPORT_ID: Final = (
    "finance_v26_mapper_v2_frequency_execution_report:"
    "152679635b6d16da3ae3723bcbf827c322a859cbcd782025022de8dfc0eafd06"
)
EXPECTED_REPORT_SHA256: Final = "53f24149e5f981c67ad438060cf1826b2efaf74430633f5973b20b527c24165e"
EXPECTED_GATE_ID: Final = (
    "mapper_v2_frequency_measurement_gate:"
    "93a07ac068af312b20254589aabd509f661cd34a2d50c3e43111a0f91c335551"
)
EXPECTED_RAW_LINEAGE_ID: Final = (
    "finance_v26_mapper_v2_frequency_raw_lineage:"
    "48e34e4dbaa0818376bee5723ad7760938f7e1e54de65024c0c5bbe7e86a368d"
)
EXPECTED_MANIFEST_ID: Final = execution.EXPECTED_MANIFEST_ID
EXPECTED_SUPPORT_EXIT_JOB_ID: Final = (
    "finance_v26_frequency_job:53e29a176c06a64c701928ec7d2e958de595de83261e9abe95a45d63def57857"
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


def _resolve_package_root(root: Path) -> Path:
    if (root / "src" / "trusted_synthesis").is_dir():
        return root
    candidate = root / "trusted_data_synthesis"
    if (candidate / "src" / "trusted_synthesis").is_dir():
        return candidate
    raise ValueError("v26.162 cannot resolve package root")


def _find_bound_file(
    relative_path: str,
    expected_sha256: str,
    *,
    package_root: Path,
    implementation_root: Path,
) -> Path:
    candidates = (implementation_root / relative_path, package_root / relative_path)
    for path in candidates:
        if path.is_file() and _sha256(path) == expected_sha256:
            return path
    raise ValueError(f"v26.162 bound file unavailable: {relative_path}")


class FileBinding(FrozenModel):
    relative_path: str = Field(min_length=1)
    source_kind: Literal[
        "v26_161_execution_file",
        "v26_161_implementation",
        "v26_162_implementation",
    ]
    sha256: str = Field(min_length=64, max_length=64)
    byte_count: int = Field(gt=0)


class SourceReplayAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    execution_report_id: str = EXPECTED_REPORT_ID
    execution_report_sha256: str = EXPECTED_REPORT_SHA256
    execution_file_count: int = Field(gt=9_000)
    execution_file_byte_match_count: int = Field(gt=9_000)
    execution_implementation_count: Literal[2] = 2
    audit_implementation_count: Literal[1] = 1
    file_bindings: tuple[FileBinding, ...] = Field(min_length=9_000)
    credential_lookup_attempted: Literal[False] = False
    provider_calls: Literal[0] = 0
    status: Literal["passed"] = "passed"

    @model_validator(mode="after")
    def validate_audit(self) -> SourceReplayAudit:
        paths = tuple(item.relative_path for item in self.file_bindings)
        if (
            len(paths) != len(set(paths))
            or self.execution_file_count != self.execution_file_byte_match_count
            or self.execution_file_count + 3 != len(self.file_bindings)
            or self.audit_id
            != _identity(
                self,
                "audit_id",
                "finance_v26_mapper_v2_frequency_postrun_source_replay:",
            )
        ):
            raise ValueError("v26.162 source replay changed")
        return self


class ProviderArtifactAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    raw_execution_count: Literal[360] = 360
    provider_call_count: Literal[3134] = 3134
    provider_envelope_count: Literal[3134] = 3134
    public_projection_count: Literal[3134] = 3134
    transport_certificate_count: Literal[3134] = 3134
    complete_artifact_triple_count: Literal[3134] = 3134
    exact_model_failure_count: Literal[0] = 0
    thinking_failure_count: Literal[0] = 0
    usage_failure_count: Literal[0] = 0
    privacy_failure_count: Literal[0] = 0
    unresolved_transport_failure_count: Literal[0] = 0
    stage_two_provider_call_count: Literal[0] = 0
    private_reasoning_payload_count: Literal[0] = 0
    raw_http_body_count: Literal[0] = 0
    raw_request_body_count: Literal[0] = 0
    provider_calls: Literal[0] = 0

    @model_validator(mode="after")
    def validate_audit(self) -> ProviderArtifactAudit:
        if self.audit_id != _identity(
            self,
            "audit_id",
            "finance_v26_mapper_v2_frequency_independent_provider_artifacts:",
        ):
            raise ValueError("v26.162 Provider artifact audit changed")
        return self


MeasurementSupportStatus = Literal["available", "exited"]
DetourAllowanceStatus = Literal["within_allowance", "exhausted"]


class IndependentMeasurementProjection(FrozenModel):
    projection_id: str = Field(min_length=1)
    job_id: str = Field(min_length=1)
    raw_execution_id: str = Field(min_length=1)
    task_condition_cell_id: str = Field(min_length=1)
    task_package_id: str = Field(min_length=1)
    mechanism_id: str = Field(min_length=1)
    tier: str = Field(min_length=1)
    sampling_mode: Literal["reachability_unconditional", "reachability_conditioned"]
    raw_terminal_disposition: str = Field(min_length=1)
    terminal_failure_type: str | None = None
    raw_native_instrument_integrity: bool
    measurement_support_status: MeasurementSupportStatus
    resource_accounting_integrity: bool
    detour_allowance_status: DetourAllowanceStatus
    provider_identity_integrity: bool
    thinking_integrity: bool
    usage_integrity: bool
    request_binding_integrity: bool
    provider_artifact_pairing_integrity: bool
    reversible_commit_integrity: bool
    privacy_compliant: bool
    model_endpoint_observed: bool
    validity_evaluable: bool
    base_valid: bool | None
    mechanism_qualified: bool | None
    qualified_valid: bool | None
    task_verifier_invocation_count: int = Field(ge=0, le=1)
    provider_call_count: int = Field(ge=0, le=23)
    transport_invocation_count: int = Field(ge=0, le=24)
    provider_total_tokens: int = Field(ge=0, le=1_120_000)
    ordinary_detour_count: int = Field(ge=0, le=2)
    later_provider_calls_after_support_exit: Literal[0] = 0
    support_instrument_overlap: Literal[False] = False
    support_resource_overlap: Literal[False] = False
    historical_reclassified: Literal[False] = False

    @model_validator(mode="after")
    def validate_projection(self) -> IndependentMeasurementProjection:
        support_exit = self.measurement_support_status == "exited"
        resource_failure = not self.resource_accounting_integrity
        instrument_failure = not self.raw_native_instrument_integrity
        integrity = all(
            (
                self.raw_native_instrument_integrity,
                self.resource_accounting_integrity,
                self.provider_identity_integrity,
                self.thinking_integrity,
                self.usage_integrity,
                self.request_binding_integrity,
                self.provider_artifact_pairing_integrity,
                self.reversible_commit_integrity,
                self.privacy_compliant,
            )
        )
        expected_evaluable = bool(not support_exit and integrity and self.model_endpoint_observed)
        if (
            self.validity_evaluable != expected_evaluable
            or (support_exit and instrument_failure)
            or (support_exit and resource_failure)
            or self.support_instrument_overlap
            or self.support_resource_overlap
            or (not self.validity_evaluable and self.base_valid is not None)
            or (not self.validity_evaluable and self.mechanism_qualified is not None)
            or (not self.validity_evaluable and self.qualified_valid is not None)
            or (
                self.validity_evaluable
                and self.qualified_valid
                != bool(self.base_valid is True and self.mechanism_qualified is True)
            )
            or self.projection_id
            != _identity(
                self,
                "projection_id",
                "finance_v26_mapper_v2_frequency_independent_projection:",
            )
        ):
            raise ValueError("v26.162 independent Measurement projection changed")
        return self


class IndependentProjectionCatalog(FrozenModel):
    catalog_id: str = Field(min_length=1)
    projections: tuple[IndependentMeasurementProjection, ...] = Field(
        min_length=360,
        max_length=360,
    )
    projection_count: Literal[360] = 360
    model_endpoint_count: Literal[359] = 359
    validity_evaluable_count: Literal[359] = 359
    measurement_support_exit_count: Literal[1] = 1
    raw_native_instrument_failure_count: Literal[0] = 0
    resource_accounting_failure_count: Literal[0] = 0
    support_instrument_overlap_count: Literal[0] = 0
    support_resource_overlap_count: Literal[0] = 0
    base_valid_count: Literal[139] = 139
    mechanism_qualified_count: Literal[270] = 270
    qualified_valid_count: Literal[139] = 139
    historical_formal_instrument_count: Literal[1] = 1
    historical_projection_overlap_count: Literal[1] = 1
    online_projector_used_as_outcome_oracle: Literal[False] = False
    provider_calls: Literal[0] = 0

    @model_validator(mode="after")
    def validate_catalog(self) -> IndependentProjectionCatalog:
        rows = self.projections
        if (
            len({item.job_id for item in rows}) != 360
            or len({item.projection_id for item in rows}) != 360
            or self.model_endpoint_count != sum(item.model_endpoint_observed for item in rows)
            or self.validity_evaluable_count != sum(item.validity_evaluable for item in rows)
            or self.measurement_support_exit_count
            != sum(item.measurement_support_status == "exited" for item in rows)
            or self.raw_native_instrument_failure_count
            != sum(not item.raw_native_instrument_integrity for item in rows)
            or self.resource_accounting_failure_count
            != sum(not item.resource_accounting_integrity for item in rows)
            or self.base_valid_count != sum(item.base_valid is True for item in rows)
            or self.mechanism_qualified_count
            != sum(item.mechanism_qualified is True for item in rows)
            or self.qualified_valid_count != sum(item.qualified_valid is True for item in rows)
            or self.catalog_id
            != _identity(
                self,
                "catalog_id",
                "finance_v26_mapper_v2_frequency_independent_projection_catalog:",
            )
        ):
            raise ValueError("v26.162 projection Catalog changed")
        return self


class IndependentGateAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    historical_formal_gate_id: str = EXPECTED_GATE_ID
    complete_raw_count: Literal[360] = 360
    model_endpoint_count: Literal[359] = 359
    validity_evaluable_count: Literal[359] = 359
    measurement_support_exit_count: Literal[1] = 1
    raw_native_instrument_failure_count: Literal[0] = 0
    resource_accounting_failure_count: Literal[0] = 0
    privacy_failure_count: Literal[0] = 0
    exact_model_thinking_usage_failure_count: Literal[0] = 0
    typed_budget_no_call_count: Literal[0] = 0
    unresolved_transport_failure_count: Literal[0] = 0
    historical_formal_instrument_failure_count: Literal[1] = 1
    independent_failure_ids: tuple[str, ...] = (
        "measurement_support_exit_zero",
        "model_endpoint_360_of_360",
        "validity_evaluable_360_of_360",
    )
    passed: Literal[False] = False
    every_frequency_estimand_null: Literal[True] = True
    historical_gate_repaired: Literal[False] = False
    provider_calls: Literal[0] = 0

    @model_validator(mode="after")
    def validate_audit(self) -> IndependentGateAudit:
        if self.audit_id != _identity(
            self,
            "audit_id",
            "finance_v26_mapper_v2_frequency_independent_gate:",
        ):
            raise ValueError("v26.162 independent Gate changed")
        return self


class CellDiagnostic(FrozenModel):
    diagnostic_id: str = Field(min_length=1)
    task_condition_cell_id: str = Field(min_length=1)
    task_package_id: str = Field(min_length=1)
    sampling_mode: Literal["reachability_unconditional", "reachability_conditioned"]
    n_total: Literal[6, 12]
    n_evaluable: int = Field(ge=0, le=12)
    n_qualified: int = Field(ge=0, le=12)
    global_frequency_status: Literal["measurement_gate_failed"] = "measurement_gate_failed"
    distribution: None = None
    null_reason: Literal["measurement_gate_failed"] = "measurement_gate_failed"

    @model_validator(mode="after")
    def validate_diagnostic(self) -> CellDiagnostic:
        if self.diagnostic_id != _identity(
            self,
            "diagnostic_id",
            "finance_v26_mapper_v2_frequency_independent_cell:",
        ):
            raise ValueError("v26.162 Cell diagnostic changed")
        return self


class CellAndNullAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    cells: tuple[CellDiagnostic, ...] = Field(min_length=48, max_length=48)
    cell_count: Literal[48] = 48
    n_total_sum: Literal[360] = 360
    n_evaluable_sum: Literal[359] = 359
    n_qualified_sum: Literal[139] = 139
    zero_qualified_cell_count: Literal[8] = 8
    zero_qualified_unconditional_cell_count: Literal[1] = 1
    zero_qualified_conditioned_cell_count: Literal[7] = 7
    minimum_n_qualified: Literal[0] = 0
    maximum_n_qualified: Literal[10] = 10
    null_report_count: Literal[48] = 48
    imputed_state_vector_count: Literal[0] = 0
    formal_assignment_count: Literal[0] = 0
    production_mapper_invocation_count: Literal[0] = 0
    reference_mapper_invocation_count: Literal[0] = 0
    structural_state_count: Literal[0] = 0
    empirical_route_signature_count: Literal[0] = 0
    provider_calls: Literal[0] = 0

    @model_validator(mode="after")
    def validate_audit(self) -> CellAndNullAudit:
        if (
            len({item.task_condition_cell_id for item in self.cells}) != 48
            or self.n_total_sum != sum(item.n_total for item in self.cells)
            or self.n_evaluable_sum != sum(item.n_evaluable for item in self.cells)
            or self.n_qualified_sum != sum(item.n_qualified for item in self.cells)
            or self.zero_qualified_cell_count != sum(item.n_qualified == 0 for item in self.cells)
            or self.audit_id
            != _identity(
                self,
                "audit_id",
                "finance_v26_mapper_v2_frequency_independent_cell_null_audit:",
            )
        ):
            raise ValueError("v26.162 Cell/null audit changed")
        return self


class SupportBoundaryAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    job_id: Literal[
        "finance_v26_frequency_job:53e29a176c06a64c701928ec7d2e958de595de83261e9abe95a45d63def57857"
    ] = EXPECTED_SUPPORT_EXIT_JOB_ID
    mechanism_id: Literal["state_dependent_stopping"] = "state_dependent_stopping"
    tier: Literal["hard_control"] = "hard_control"
    sampling_mode: Literal["reachability_conditioned"] = "reachability_conditioned"
    requested_path_strategy: Literal["search_then_open"] = "search_then_open"
    raw_terminal_disposition: Literal["measurement_support_exit"] = "measurement_support_exit"
    terminal_failure_type: Literal["ordinary_detour_allowance_exhausted"] = (
        "ordinary_detour_allowance_exhausted"
    )
    ordinary_detour_count: Literal[2] = 2
    stage_one_provider_call_count: Literal[3] = 3
    transport_invocation_count: Literal[3] = 3
    provider_total_tokens: Literal[40041] = 40041
    later_provider_calls: Literal[0] = 0
    task_verifier_calls: Literal[0] = 0
    state_mapping_rows: Literal[0] = 0
    raw_native_instrument_integrity: Literal[True] = True
    resource_accounting_integrity: Literal[True] = True
    historical_formal_instrument_integrity: Literal[False] = False
    historical_rollout_budget_passed: Literal[False] = False
    causal_classification: Literal["one_measurement_support_exit_with_projection_overlap"] = (
        "one_measurement_support_exit_with_projection_overlap"
    )
    historical_reclassified: Literal[False] = False
    provider_calls: Literal[0] = 0

    @model_validator(mode="after")
    def validate_audit(self) -> SupportBoundaryAudit:
        if self.audit_id != _identity(
            self,
            "audit_id",
            "finance_v26_mapper_v2_frequency_support_boundary:",
        ):
            raise ValueError("v26.162 Support boundary changed")
        return self


class MutationResult(FrozenModel):
    mutation_name: str = Field(min_length=1)
    failed_closed: Literal[True] = True


class DestructiveAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    mutations: tuple[MutationResult, ...] = Field(min_length=12)
    mutation_count: int = Field(ge=12)
    rejected_count: int = Field(ge=12)
    provider_calls: Literal[0] = 0

    @model_validator(mode="after")
    def validate_audit(self) -> DestructiveAudit:
        names = tuple(item.mutation_name for item in self.mutations)
        if (
            names != tuple(sorted(set(names)))
            or self.mutation_count != len(names)
            or self.rejected_count != len(names)
            or self.audit_id
            != _identity(
                self,
                "audit_id",
                "finance_v26_mapper_v2_frequency_postrun_destructive:",
            )
        ):
            raise ValueError("v26.162 destructive audit changed")
        return self


class RouteBDecisionContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    postrun_gate_audit_id: str = Field(min_length=1)
    support_boundary_audit_id: str = Field(min_length=1)
    selected_route: Literal["route_b_defined_bounded_policy"] = "route_b_defined_bounded_policy"
    next_permitted_stage: Literal["fresh_bounded_policy_endpoint_frequency_preflight_only"] = (
        NEXT_STAGE
    )
    policy_horizon_is_generation_endpoint: Literal[True] = True
    policy_horizon_endpoint_observed: Literal[True] = True
    policy_horizon_task_completion: Literal[False] = False
    policy_horizon_base_validity: Literal[False] = False
    policy_horizon_qualified_validity: Literal[False] = False
    policy_horizon_state_mapping_eligible: Literal[False] = False
    raw_instrument_support_resource_orthogonality_required: Literal[True] = True
    fresh_policy_id_required: Literal[True] = True
    fresh_population_required: Literal[True] = True
    fresh_outcome_gate_runner_required: Literal[True] = True
    q_and_conditional_pi_estimands_required: Literal[True] = True
    global_integrity_and_cell_estimand_gates_required: Literal[True] = True
    uncertainty_and_minimum_sample_policy_required: Literal[True] = True
    provider_execution_authorized: Literal[False] = False
    historical_reclassification_authorized: Literal[False] = False
    frequency_or_vtdo_authorized: Literal[False] = False

    @model_validator(mode="after")
    def validate_contract(self) -> RouteBDecisionContract:
        if self.contract_id != _identity(
            self,
            "contract_id",
            "finance_v26_route_b_bounded_policy_decision:",
        ):
            raise ValueError("v26.162 Route B decision changed")
        return self


class DetailFile(FrozenModel):
    relative_path: str = Field(min_length=1)
    sha256: str = Field(min_length=64, max_length=64)
    byte_count: int = Field(gt=0)


class PostrunAuditReport(FrozenModel):
    report_id: str = Field(min_length=1)
    run_id: str = RUN_ID
    execution_report_id: str = EXPECTED_REPORT_ID
    source_replay_audit_id: str = Field(min_length=1)
    provider_artifact_audit_id: str = Field(min_length=1)
    projection_catalog_id: str = Field(min_length=1)
    independent_gate_audit_id: str = Field(min_length=1)
    cell_null_audit_id: str = Field(min_length=1)
    support_boundary_audit_id: str = Field(min_length=1)
    destructive_audit_id: str = Field(min_length=1)
    route_b_decision_contract_id: str = Field(min_length=1)
    exact_raw_count: Literal[360] = 360
    provider_artifact_triple_count: Literal[3134] = 3134
    independent_model_endpoint_count: Literal[359] = 359
    independent_validity_evaluable_count: Literal[359] = 359
    independent_support_exit_count: Literal[1] = 1
    independent_raw_instrument_failure_count: Literal[0] = 0
    independent_resource_failure_count: Literal[0] = 0
    base_valid_count: Literal[139] = 139
    mechanism_qualified_count: Literal[270] = 270
    qualified_valid_count: Literal[139] = 139
    zero_qualified_cell_count: Literal[8] = 8
    formal_assignment_count: Literal[0] = 0
    null_frequency_report_count: Literal[48] = 48
    independent_gate_passed: Literal[False] = False
    exact_frequency_estimands_null: Literal[True] = True
    historical_reclassified: Literal[False] = False
    provider_calls: Literal[0] = 0
    stage_two_provider_calls: Literal[0] = 0
    detail_files: tuple[DetailFile, ...]
    next_permitted_stage: Literal["fresh_bounded_policy_endpoint_frequency_preflight_only"] = (
        NEXT_STAGE
    )

    @model_validator(mode="after")
    def validate_report(self) -> PostrunAuditReport:
        if self.report_id != _identity(
            self,
            "report_id",
            "finance_v26_mapper_v2_frequency_postrun_audit_report:",
        ):
            raise ValueError("v26.162 report changed")
        return self


@dataclass(frozen=True)
class AuditInputs:
    report: execution.FrequencyExecutionReport
    manifest: FrequencyManifest
    cells: TaskConditionCellCatalogV2
    tasks: Any
    paths: Any
    resource: Any
    runner_contract: FrequencyRunnerContract
    joint_contract: Any
    grammar: Any
    independent_inputs: independent.AuditInputs


@dataclass(frozen=True)
class AuditProducts:
    source_replay: SourceReplayAudit
    provider_artifacts: ProviderArtifactAudit
    projections: IndependentProjectionCatalog
    gate: IndependentGateAudit
    cells: CellAndNullAudit
    support: SupportBoundaryAudit
    destructive: DestructiveAudit
    route_b: RouteBDecisionContract
    report: PostrunAuditReport


def _source_replay(
    *,
    execution_dir: Path,
    package_root: Path,
    implementation_root: Path,
) -> SourceReplayAudit:
    report_path = execution_dir / "report.json"
    report = execution.FrequencyExecutionReport.model_validate(_load(report_path))
    if _sha256(report_path) != EXPECTED_REPORT_SHA256 or report.report_id != EXPECTED_REPORT_ID:
        raise ValueError("v26.162 execution report binding changed")
    prior_source = execution.ExecutionSourceReplayAudit.model_validate(
        _load(execution_dir / "execution_source_replay_audit.json")
    )
    bindings: list[FileBinding] = []
    execution_files = tuple(sorted(path for path in execution_dir.rglob("*") if path.is_file()))
    if not execution_files or any(path.name.endswith(".tmp") for path in execution_files):
        raise ValueError("v26.162 execution file set is incomplete")
    for path in execution_files:
        bindings.append(
            FileBinding(
                relative_path=str(path.relative_to(package_root)),
                source_kind="v26_161_execution_file",
                sha256=_sha256(path),
                byte_count=path.stat().st_size,
            )
        )
    for item in prior_source.implementation_files:
        path = _find_bound_file(
            item.relative_path,
            item.sha256,
            package_root=package_root,
            implementation_root=implementation_root,
        )
        bindings.append(
            FileBinding(
                relative_path=f"implementation/{item.relative_path}",
                source_kind="v26_161_implementation",
                sha256=item.sha256,
                byte_count=path.stat().st_size,
            )
        )
    audit_path = implementation_root / IMPLEMENTATION_PATH
    bindings.append(
        FileBinding(
            relative_path=f"implementation/{IMPLEMENTATION_PATH}",
            source_kind="v26_162_implementation",
            sha256=_sha256(audit_path),
            byte_count=audit_path.stat().st_size,
        )
    )
    ordered = tuple(sorted(bindings, key=lambda item: item.relative_path))
    values = {
        "execution_file_count": len(execution_files),
        "execution_file_byte_match_count": len(execution_files),
        "file_bindings": ordered,
    }
    provisional = SourceReplayAudit.model_construct(audit_id="pending", **values)
    return SourceReplayAudit(
        audit_id=_identity(
            provisional,
            "audit_id",
            "finance_v26_mapper_v2_frequency_postrun_source_replay:",
        ),
        **values,
    )


def _load_inputs(
    *,
    execution_dir: Path,
    package_root: Path,
    implementation_root: Path,
) -> AuditInputs:
    report = execution.FrequencyExecutionReport.model_validate(_load(execution_dir / "report.json"))
    manifest = FrequencyManifest.model_validate(
        _load(execution_dir / "frozen_frequency_manifest.json")
    )
    cells = TaskConditionCellCatalogV2.model_validate(
        _load(execution_dir / "frozen_task_condition_cell_catalog.json")
    )
    tasks = preflight_inputs.reachability.TaskPackageCatalog.model_validate(
        _load(execution_dir / "frozen_task_package_catalog.json")
    )
    paths = preflight_inputs.reachability.PathCatalog.model_validate(
        _load(execution_dir / "frozen_path_catalog.json")
    )
    resource = preflight_inputs.reachability.ResourceContract.model_validate(
        _load(execution_dir / "frozen_resource_contract.json")
    )
    runner_contract = FrequencyRunnerContract.model_validate(
        _load(execution_dir / "frozen_frequency_runner_contract.json")
    )
    joint = independent.JointSupportValidityContract.model_validate(
        _load(execution_dir / "frozen_joint_support_validity_contract.json")
    )
    grammar = independent.QualifiedFinalResponseGrammar.model_validate(
        _load(execution_dir / "frozen_qualified_final_response_grammar.json")
    )
    source_selection_id = _load(execution_dir / "frozen_source_selection_audit.json")["audit_id"]
    static = preflight_static.load_static_inputs(package_root)
    _, replay_contract = (
        preflight_inputs.reachability.bounded.predecessor._load_and_replay_verifier_qualification(  # noqa: SLF001,E501
            package_root
            / preflight_inputs.reachability.bounded.predecessor.VERIFIER_QUALIFICATION_DIR,
            package_root,
        )
    )
    independent_inputs = independent.AuditInputs(
        report=cast(Any, report),
        manifest=cast(Any, manifest),
        tasks=tasks,
        paths=paths,
        frozen_input=cast(Any, SimpleNamespace(audit_id=source_selection_id)),
        resource=resource,
        runner_contract=cast(Any, runner_contract),
        joint_contract=joint,
        grammar=grammar,
        role_inputs=SimpleNamespace(static=static),
        replay_contract=replay_contract,
    )
    if (
        report.report_id != EXPECTED_REPORT_ID
        or report.measurement_gate_id != EXPECTED_GATE_ID
        or report.raw_lineage_audit_id != EXPECTED_RAW_LINEAGE_ID
        or report.complete_raw_count != 360
        or manifest.manifest_id != EXPECTED_MANIFEST_ID
        or len(manifest.jobs) != 360
        or len(cells.cells) != 48
        or len(tasks.packages) != 12
        or len(paths.paths) != 36
    ):
        raise ValueError("v26.162 frozen execution input changed")
    return AuditInputs(
        report=report,
        manifest=manifest,
        cells=cells,
        tasks=tasks,
        paths=paths,
        resource=resource,
        runner_contract=runner_contract,
        joint_contract=joint,
        grammar=grammar,
        independent_inputs=independent_inputs,
    )


def _resource_integrity(raw: runner_vnext.FreshReachabilityRawExecution, resource: Any) -> bool:
    return bool(
        raw.cumulative_provider_tokens <= resource.rollout_upper_bound_tokens
        and raw.stage_one_provider_call_count <= resource.maximum_stage_one_provider_calls
        and raw.transport_inclusive_invocation_count
        <= resource.maximum_transport_inclusive_invocations
    )


def _independent_rows(
    *,
    inputs: AuditInputs,
    execution_dir: Path,
) -> tuple[
    tuple[IndependentMeasurementProjection, ...],
    ProviderArtifactAudit,
    dict[str, runner_vnext.FreshReachabilityRawExecution],
]:
    packages = {item.task_package_id: item for item in inputs.tasks.packages}
    rows: list[IndependentMeasurementProjection] = []
    raws: dict[str, runner_vnext.FreshReachabilityRawExecution] = {}
    envelope_count = projection_count = transport_count = 0
    exact_failures = thinking_failures = usage_failures = privacy_failures = 0
    unresolved_transport = stage_two_calls = 0
    for job in sorted(inputs.manifest.jobs, key=lambda item: item.job_id):
        raw_path = runner_vnext._raw_path(execution_dir, job)  # noqa: SLF001
        raw = runner_vnext.FreshReachabilityRawExecution.model_validate(_load(raw_path))
        if raw.job_id != job.job_id or raw.job_payload != job.model_dump(mode="json"):
            raise ValueError("v26.162 Raw crossed its frozen Job")
        pairs = independent._provider_pairs(raw, execution_dir)  # noqa: SLF001
        exact_model, fallback_absent, native_absent, thinking, usage = (
            independent.semantic_online._telemetry_flags(raw.provider_telemetry)  # noqa: SLF001
        )
        request_binding = all(
            item.dynamic_certificate_id is not None
            and item.resource_certificate_id is not None
            and item.request_binding_certificate_id is not None
            for item in raw.attempts
            if item.provider_call_made
        )
        pairing = bool(
            len(pairs)
            == len(raw.provider_envelope_artifacts)
            == len(raw.public_payload_projection_artifacts)
            == raw.stage_one_provider_call_count
            == len(raw.transport_invocation_artifacts)
        )
        reversible = all(
            item.reversible_same_action_id_passed
            and not item.semantic_choice_inserted_by_host
            and item.stage_two_provider_calls == 0
            for item in raw.commits
        )
        resource_integrity = _resource_integrity(raw, inputs.resource)
        support_exit = raw.terminal_disposition == "measurement_support_exit"
        model_endpoint = independent._endpoint_observed(raw)  # noqa: SLF001
        integrity = all(
            (
                raw.instrument_integrity,
                resource_integrity,
                exact_model,
                fallback_absent,
                native_absent,
                thinking,
                usage,
                request_binding,
                pairing,
                reversible,
                raw.privacy_compliant,
                raw.stage_two_provider_call_count == 0,
            )
        )
        evaluable = bool(not support_exit and model_endpoint and integrity)
        base_valid: bool | None = None
        mechanism_qualified: bool | None = None
        qualified_valid: bool | None = None
        verifier_calls = 0
        if evaluable:
            package = packages[job.task_package_id]
            result = independent._project_measurement_independently(  # noqa: SLF001
                raw=raw,
                job=cast(Any, job),
                package=package,
                inputs=inputs.independent_inputs,
                execution_dir=execution_dir,
            )
            if not result.validity_evaluable:
                raise ValueError(
                    "v26.162 independent projector rejected an evaluable endpoint: "
                    f"{job.job_id}|{raw.terminal_disposition}|{result.measurement_gate_failure_ids}"
                )
            base_valid = result.base_trajectory_validity
            mechanism_qualified = result.mechanism_qualification
            qualified_valid = result.qualified_trajectory_validity
            verifier_calls = result.task_verifier_invocation_count
        values = {
            "job_id": job.job_id,
            "raw_execution_id": raw.artifact_id,
            "task_condition_cell_id": job.task_condition_cell_id,
            "task_package_id": job.task_package_id,
            "mechanism_id": job.mechanism_id,
            "tier": job.tier,
            "sampling_mode": job.sampling_mode,
            "raw_terminal_disposition": raw.terminal_disposition,
            "terminal_failure_type": raw.terminal_failure_type,
            "raw_native_instrument_integrity": raw.instrument_integrity,
            "measurement_support_status": "exited" if support_exit else "available",
            "resource_accounting_integrity": resource_integrity,
            "detour_allowance_status": (
                "within_allowance" if raw.ordinary_detour_count <= 1 else "exhausted"
            ),
            "provider_identity_integrity": bool(exact_model and fallback_absent and native_absent),
            "thinking_integrity": thinking,
            "usage_integrity": usage,
            "request_binding_integrity": request_binding,
            "provider_artifact_pairing_integrity": pairing,
            "reversible_commit_integrity": reversible,
            "privacy_compliant": raw.privacy_compliant,
            "model_endpoint_observed": model_endpoint,
            "validity_evaluable": evaluable,
            "base_valid": base_valid,
            "mechanism_qualified": mechanism_qualified,
            "qualified_valid": qualified_valid,
            "task_verifier_invocation_count": verifier_calls,
            "provider_call_count": raw.stage_one_provider_call_count,
            "transport_invocation_count": raw.transport_inclusive_invocation_count,
            "provider_total_tokens": raw.cumulative_provider_tokens,
            "ordinary_detour_count": raw.ordinary_detour_count,
        }
        provisional = IndependentMeasurementProjection.model_construct(
            projection_id="pending",
            **values,
        )
        rows.append(
            IndependentMeasurementProjection(
                projection_id=_identity(
                    provisional,
                    "projection_id",
                    "finance_v26_mapper_v2_frequency_independent_projection:",
                ),
                **values,
            )
        )
        raws[job.job_id] = raw
        envelope_count += len(raw.provider_envelope_artifacts)
        projection_count += len(raw.public_payload_projection_artifacts)
        transport_count += len(raw.transport_invocation_artifacts)
        exact_failures += int(not exact_model)
        thinking_failures += int(not thinking)
        usage_failures += int(not usage)
        privacy_failures += int(not raw.privacy_compliant)
        unresolved_transport += int(raw.terminal_disposition == "provider_transport_failure")
        stage_two_calls += raw.stage_two_provider_call_count
    provider_values = {
        "provider_envelope_count": envelope_count,
        "public_projection_count": projection_count,
        "transport_certificate_count": transport_count,
        "complete_artifact_triple_count": envelope_count,
        "exact_model_failure_count": exact_failures,
        "thinking_failure_count": thinking_failures,
        "usage_failure_count": usage_failures,
        "privacy_failure_count": privacy_failures,
        "unresolved_transport_failure_count": unresolved_transport,
        "stage_two_provider_call_count": stage_two_calls,
    }
    provisional_provider = ProviderArtifactAudit.model_construct(
        audit_id="pending", **provider_values
    )
    provider = ProviderArtifactAudit(
        audit_id=_identity(
            provisional_provider,
            "audit_id",
            "finance_v26_mapper_v2_frequency_independent_provider_artifacts:",
        ),
        **provider_values,
    )
    return tuple(sorted(rows, key=lambda item: item.job_id)), provider, raws


def _projection_catalog(
    *,
    rows: Sequence[IndependentMeasurementProjection],
    execution_dir: Path,
) -> IndependentProjectionCatalog:
    # Historical online outputs are loaded only after the independent rows are complete.
    formal_rows = tuple(
        execution.FrequencyMeasurementResult.model_validate(item)
        for item in _load(execution_dir / "frequency_measurement_results.json")
    )
    formal_by_job = {item.job_id: item.joint_measurement_projection for item in formal_rows}
    overlap = sum(
        item.measurement_support_status == "exited"
        and item.raw_native_instrument_integrity
        and not formal_by_job[item.job_id].instrument_integrity
        for item in rows
    )
    values = {
        "projections": tuple(rows),
        "model_endpoint_count": sum(item.model_endpoint_observed for item in rows),
        "validity_evaluable_count": sum(item.validity_evaluable for item in rows),
        "measurement_support_exit_count": sum(
            item.measurement_support_status == "exited" for item in rows
        ),
        "raw_native_instrument_failure_count": sum(
            not item.raw_native_instrument_integrity for item in rows
        ),
        "resource_accounting_failure_count": sum(
            not item.resource_accounting_integrity for item in rows
        ),
        "support_instrument_overlap_count": sum(item.support_instrument_overlap for item in rows),
        "support_resource_overlap_count": sum(item.support_resource_overlap for item in rows),
        "base_valid_count": sum(item.base_valid is True for item in rows),
        "mechanism_qualified_count": sum(item.mechanism_qualified is True for item in rows),
        "qualified_valid_count": sum(item.qualified_valid is True for item in rows),
        "historical_formal_instrument_count": sum(
            not item.instrument_integrity for item in formal_by_job.values()
        ),
        "historical_projection_overlap_count": overlap,
    }
    provisional = IndependentProjectionCatalog.model_construct(catalog_id="pending", **values)
    return IndependentProjectionCatalog(
        catalog_id=_identity(
            provisional,
            "catalog_id",
            "finance_v26_mapper_v2_frequency_independent_projection_catalog:",
        ),
        **values,
    )


def _gate(catalog: IndependentProjectionCatalog) -> IndependentGateAudit:
    values = {
        "complete_raw_count": len(catalog.projections),
        "model_endpoint_count": catalog.model_endpoint_count,
        "validity_evaluable_count": catalog.validity_evaluable_count,
        "measurement_support_exit_count": catalog.measurement_support_exit_count,
        "raw_native_instrument_failure_count": catalog.raw_native_instrument_failure_count,
        "resource_accounting_failure_count": catalog.resource_accounting_failure_count,
    }
    provisional = IndependentGateAudit.model_construct(audit_id="pending", **values)
    return IndependentGateAudit(
        audit_id=_identity(
            provisional,
            "audit_id",
            "finance_v26_mapper_v2_frequency_independent_gate:",
        ),
        **values,
    )


def _cell_and_null_audit(
    *,
    inputs: AuditInputs,
    catalog: IndependentProjectionCatalog,
    execution_dir: Path,
) -> CellAndNullAudit:
    rows_by_cell: dict[str, list[IndependentMeasurementProjection]] = defaultdict(list)
    for row in catalog.projections:
        rows_by_cell[row.task_condition_cell_id].append(row)
    diagnostics: list[CellDiagnostic] = []
    for cell in inputs.cells.cells:
        rows = rows_by_cell[cell.cell_id]
        values = {
            "task_condition_cell_id": cell.cell_id,
            "task_package_id": cell.task_package_id,
            "sampling_mode": cell.experimental_condition.sampling_mode,
            "n_total": len(rows),
            "n_evaluable": sum(item.validity_evaluable for item in rows),
            "n_qualified": sum(item.qualified_valid is True for item in rows),
        }
        provisional = CellDiagnostic.model_construct(diagnostic_id="pending", **values)
        diagnostics.append(
            CellDiagnostic(
                diagnostic_id=_identity(
                    provisional,
                    "diagnostic_id",
                    "finance_v26_mapper_v2_frequency_independent_cell:",
                ),
                **values,
            )
        )
    assignment = execution.FrequencyAssignmentCatalog.model_validate(
        _load(execution_dir / "frequency_assignment_catalog.json")
    )
    mapper = execution.MapperExecutionAudit.model_validate(
        _load(execution_dir / "mapper_execution_audit.json")
    )
    summary = ReachabilityFrequencySummaryV2.model_validate(
        _load(execution_dir / "task_condition_frequency_summary.json")
    )
    ordered = tuple(sorted(diagnostics, key=lambda item: item.diagnostic_id))
    zero_rows = tuple(item for item in ordered if item.n_qualified == 0)
    values = {
        "cells": ordered,
        "n_total_sum": sum(item.n_total for item in ordered),
        "n_evaluable_sum": sum(item.n_evaluable for item in ordered),
        "n_qualified_sum": sum(item.n_qualified for item in ordered),
        "zero_qualified_cell_count": len(zero_rows),
        "zero_qualified_unconditional_cell_count": sum(
            item.sampling_mode == "reachability_unconditional" for item in zero_rows
        ),
        "zero_qualified_conditioned_cell_count": sum(
            item.sampling_mode == "reachability_conditioned" for item in zero_rows
        ),
        "minimum_n_qualified": min(item.n_qualified for item in ordered),
        "maximum_n_qualified": max(item.n_qualified for item in ordered),
        "null_report_count": summary.null_report_count,
        "imputed_state_vector_count": sum(
            item.distribution is not None for item in summary.reports
        ),
        "formal_assignment_count": assignment.assignment_count,
        "production_mapper_invocation_count": mapper.production_mapper_invocation_count,
        "reference_mapper_invocation_count": mapper.reference_mapper_invocation_count,
        "structural_state_count": assignment.structural_state_count,
        "empirical_route_signature_count": assignment.empirical_route_signature_count,
    }
    provisional = CellAndNullAudit.model_construct(audit_id="pending", **values)
    return CellAndNullAudit(
        audit_id=_identity(
            provisional,
            "audit_id",
            "finance_v26_mapper_v2_frequency_independent_cell_null_audit:",
        ),
        **values,
    )


def _support_boundary(
    *,
    catalog: IndependentProjectionCatalog,
    raws: Mapping[str, runner_vnext.FreshReachabilityRawExecution],
    execution_dir: Path,
) -> SupportBoundaryAudit:
    row = next(item for item in catalog.projections if item.measurement_support_status == "exited")
    raw = raws[row.job_id]
    formal = next(
        item
        for item in _load(execution_dir / "frequency_measurement_results.json")
        if item["job_id"] == row.job_id
    )["joint_measurement_projection"]
    values = {
        "job_id": row.job_id,
        "mechanism_id": row.mechanism_id,
        "tier": row.tier,
        "sampling_mode": row.sampling_mode,
        "requested_path_strategy": raw.job_payload["requested_path_strategy"],
        "raw_terminal_disposition": raw.terminal_disposition,
        "terminal_failure_type": raw.terminal_failure_type,
        "ordinary_detour_count": raw.ordinary_detour_count,
        "stage_one_provider_call_count": raw.stage_one_provider_call_count,
        "transport_invocation_count": raw.transport_inclusive_invocation_count,
        "provider_total_tokens": raw.cumulative_provider_tokens,
        "later_provider_calls": raw.later_provider_calls_after_support_exit,
        "task_verifier_calls": raw.task_verifier_invocation_count,
        "state_mapping_rows": raw.state_mapping_row_count,
        "raw_native_instrument_integrity": raw.instrument_integrity,
        "resource_accounting_integrity": row.resource_accounting_integrity,
        "historical_formal_instrument_integrity": formal["instrument_integrity"],
        "historical_rollout_budget_passed": formal["rollout_budget_passed"],
    }
    provisional = SupportBoundaryAudit.model_construct(audit_id="pending", **values)
    return SupportBoundaryAudit(
        audit_id=_identity(
            provisional,
            "audit_id",
            "finance_v26_mapper_v2_frequency_support_boundary:",
        ),
        **values,
    )


def _expect_failure(name: str, callback: Any) -> MutationResult:
    try:
        callback()
    except (AssertionError, TypeError, ValueError, ValidationError):
        return MutationResult(mutation_name=name)
    raise AssertionError(f"v26.162 destructive mutation did not fail: {name}")


def _destructive(
    *,
    catalog: IndependentProjectionCatalog,
    gate: IndependentGateAudit,
    cells: CellAndNullAudit,
) -> DestructiveAudit:
    support = next(
        item for item in catalog.projections if item.measurement_support_status == "exited"
    )
    mutations = (
        _expect_failure(
            "support_exit_instrument_overlap",
            lambda: IndependentMeasurementProjection.model_validate(
                {
                    **support.model_dump(mode="python"),
                    "raw_native_instrument_integrity": False,
                }
            ),
        ),
        _expect_failure(
            "support_exit_resource_overlap",
            lambda: IndependentMeasurementProjection.model_validate(
                {
                    **support.model_dump(mode="python"),
                    "resource_accounting_integrity": False,
                }
            ),
        ),
        _expect_failure(
            "support_exit_validity_imputed",
            lambda: IndependentMeasurementProjection.model_validate(
                {**support.model_dump(mode="python"), "base_valid": False}
            ),
        ),
        _expect_failure(
            "support_exit_endpoint_imputed",
            lambda: IndependentMeasurementProjection.model_validate(
                {**support.model_dump(mode="python"), "model_endpoint_observed": True}
            ),
        ),
        _expect_failure(
            "gate_repaired",
            lambda: IndependentGateAudit.model_validate(
                {**gate.model_dump(mode="python"), "passed": True}
            ),
        ),
        _expect_failure(
            "gate_support_deleted",
            lambda: IndependentGateAudit.model_validate(
                {**gate.model_dump(mode="python"), "measurement_support_exit_count": 0}
            ),
        ),
        _expect_failure(
            "cell_assignment_inserted",
            lambda: CellAndNullAudit.model_validate(
                {**cells.model_dump(mode="python"), "formal_assignment_count": 1}
            ),
        ),
        _expect_failure(
            "cell_null_report_deleted",
            lambda: CellAndNullAudit.model_validate(
                {**cells.model_dump(mode="python"), "null_report_count": 47}
            ),
        ),
        _expect_failure(
            "zero_qualified_cell_hidden",
            lambda: CellAndNullAudit.model_validate(
                {**cells.model_dump(mode="python"), "zero_qualified_cell_count": 0}
            ),
        ),
        _expect_failure(
            "projection_row_deleted",
            lambda: IndependentProjectionCatalog.model_validate(
                {**catalog.model_dump(mode="python"), "projections": catalog.projections[:-1]}
            ),
        ),
        _expect_failure(
            "historical_reclassification",
            lambda: IndependentMeasurementProjection.model_validate(
                {**support.model_dump(mode="python"), "historical_reclassified": True}
            ),
        ),
        _expect_failure(
            "online_projector_promoted_to_oracle",
            lambda: IndependentProjectionCatalog.model_validate(
                {
                    **catalog.model_dump(mode="python"),
                    "online_projector_used_as_outcome_oracle": True,
                }
            ),
        ),
    )
    ordered = tuple(sorted(mutations, key=lambda item: item.mutation_name))
    values = {
        "mutations": ordered,
        "mutation_count": len(ordered),
        "rejected_count": len(ordered),
    }
    provisional = DestructiveAudit.model_construct(audit_id="pending", **values)
    return DestructiveAudit(
        audit_id=_identity(
            provisional,
            "audit_id",
            "finance_v26_mapper_v2_frequency_postrun_destructive:",
        ),
        **values,
    )


def _route_b(gate: IndependentGateAudit, support: SupportBoundaryAudit) -> RouteBDecisionContract:
    values = {
        "postrun_gate_audit_id": gate.audit_id,
        "support_boundary_audit_id": support.audit_id,
    }
    provisional = RouteBDecisionContract.model_construct(contract_id="pending", **values)
    return RouteBDecisionContract(
        contract_id=_identity(
            provisional,
            "contract_id",
            "finance_v26_route_b_bounded_policy_decision:",
        ),
        **values,
    )


def _detail(path: Path, output_dir: Path) -> DetailFile:
    return DetailFile(
        relative_path=str(path.relative_to(output_dir)),
        sha256=_sha256(path),
        byte_count=path.stat().st_size,
    )


def build_postrun_audit(
    *,
    execution_dir: Path,
    output_dir: Path,
    package_root: Path,
    implementation_root: Path,
) -> AuditProducts:
    package_root = _resolve_package_root(package_root)
    implementation_root = _resolve_package_root(implementation_root)
    source = _source_replay(
        execution_dir=execution_dir,
        package_root=package_root,
        implementation_root=implementation_root,
    )
    inputs = _load_inputs(
        execution_dir=execution_dir,
        package_root=package_root,
        implementation_root=implementation_root,
    )
    rows, provider, raws = _independent_rows(inputs=inputs, execution_dir=execution_dir)
    catalog = _projection_catalog(rows=rows, execution_dir=execution_dir)
    gate = _gate(catalog)
    cells = _cell_and_null_audit(
        inputs=inputs,
        catalog=catalog,
        execution_dir=execution_dir,
    )
    support = _support_boundary(catalog=catalog, raws=raws, execution_dir=execution_dir)
    destructive = _destructive(catalog=catalog, gate=gate, cells=cells)
    route_b = _route_b(gate, support)
    output_dir.mkdir(parents=True, exist_ok=True)
    outputs: tuple[tuple[str, Any], ...] = (
        ("cell_and_null_audit.json", cells),
        ("destructive_audit.json", destructive),
        ("independent_gate_audit.json", gate),
        ("independent_projection_catalog.json", catalog),
        ("provider_artifact_audit.json", provider),
        ("route_b_decision_contract.json", route_b),
        ("source_replay_audit.json", source),
        ("support_boundary_audit.json", support),
    )
    for name, value in outputs:
        _write_json_atomic(output_dir / name, value)
    details = tuple(
        sorted(
            (_detail(output_dir / name, output_dir) for name, _ in outputs),
            key=lambda item: item.relative_path,
        )
    )
    report_values = {
        "source_replay_audit_id": source.audit_id,
        "provider_artifact_audit_id": provider.audit_id,
        "projection_catalog_id": catalog.catalog_id,
        "independent_gate_audit_id": gate.audit_id,
        "cell_null_audit_id": cells.audit_id,
        "support_boundary_audit_id": support.audit_id,
        "destructive_audit_id": destructive.audit_id,
        "route_b_decision_contract_id": route_b.contract_id,
        "detail_files": details,
    }
    provisional_report = PostrunAuditReport.model_construct(report_id="pending", **report_values)
    report = PostrunAuditReport(
        report_id=_identity(
            provisional_report,
            "report_id",
            "finance_v26_mapper_v2_frequency_postrun_audit_report:",
        ),
        **report_values,
    )
    _write_json_atomic(output_dir / "report.json", report)
    return AuditProducts(
        source_replay=source,
        provider_artifacts=provider,
        projections=catalog,
        gate=gate,
        cells=cells,
        support=support,
        destructive=destructive,
        route_b=route_b,
        report=report,
    )


def main() -> None:
    package_default = Path(__file__).resolve().parents[4]
    parser = argparse.ArgumentParser(
        description="Credential-free independent v26.162 Mapper-v2 frequency postrun audit"
    )
    parser.add_argument(
        "--execution-dir",
        type=Path,
        default=package_default / EXECUTION_DIR,
    )
    parser.add_argument("--output-dir", type=Path, default=package_default / OUTPUT_DIR)
    parser.add_argument("--package-root", type=Path, default=package_default)
    parser.add_argument("--implementation-root", type=Path, default=package_default)
    args = parser.parse_args()
    products = build_postrun_audit(
        execution_dir=args.execution_dir,
        output_dir=args.output_dir,
        package_root=args.package_root,
        implementation_root=args.implementation_root,
    )
    print(products.report.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
