from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from collections import defaultdict
from pathlib import Path
from typing import Any, Final, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.core.evaluation.valid_only_state_mapping import (
    ValidOnlyStateMapperContract,
)
from trusted_synthesis.core.trajectory.empirical_state_mapping import (
    EmpiricalRouteProjection,
    EmpiricalStructuralState,
    ValidOnlyEmpiricalStateAssignment,
    make_empirical_route_projection,
    map_independently_valid_public_trajectory_to_state,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_reachability_execution as reachability_execution,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_reachability_postrun_audit as postrun,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_valid_only_reachability_state_mapping_preflight as preflight,
)
from trusted_synthesis.hashing import canonical_hash

RUN_ID: Final = "finance_v26_157_valid_only_state_mapping_execution_v1_20260826"
OUTPUT_DIR: Final = (
    "artifacts/vtdo_experiment/finance_v26_157_valid_only_state_mapping_execution_v1_20260826"
)
IMPLEMENTATION_PATH: Final = (
    "src/trusted_synthesis/experiments/vtdo_experiment/"
    "phase1_v26_valid_only_reachability_state_mapping_execution.py"
)
NEXT_STAGE: Final = "valid_only_state_mapping_independent_raw_remap_audit_only"

# Replaced after v26.156 is immutable.
EXPECTED_PREFLIGHT_REPORT_ID: Final = (
    "finance_v26_valid_only_mapping_preflight_report:"
    "ac21b3b79c2906540da1bd2b2501e962026d7794ca451d5802981fc2390dc975"
)
EXPECTED_PREFLIGHT_REPORT_SHA256: Final = (
    "64264e761653b11db245f8fe13bffc5ae6aaa80b48e0f7021a20b0f91136b978"
)
EXPECTED_RUNNER_CONTRACT_ID: Final = (
    "finance_v26_valid_only_mapping_runner_contract:"
    "362a8474cfd31fb63153a9616f6145bdb360f4f0905ba8fc9bb552be6354b2c4"
)
EXPECTED_TRANSITION_ID: Final = (
    "finance_v26_valid_only_mapping_transition:"
    "c09299f19017eb91def5ee9517f0ae9e45cae67051420c24b492c9b04220253f"
)
EXPECTED_PROSPECTIVE_EXECUTION_ID: Final = (
    "finance_v26_valid_only_state_mapping_execution:"
    "b84de25e5d7e6bcb51b663787efc5435bd386eaa9d88c213b8440e24b36720d2"
)


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", arbitrary_types_allowed=True)


def _identity(value: BaseModel, field: str, prefix: str) -> str:
    return canonical_hash(value.model_dump(mode="json", exclude={field}), prefix=prefix)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical_bytes(value: Any) -> bytes:
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json")
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        + b"\n"
    )


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json_atomic(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(_canonical_bytes(value))
    temporary.replace(path)


def _resolve_package_root(implementation_root: Path) -> Path:
    if (implementation_root / "src" / "trusted_synthesis").is_dir():
        return implementation_root
    candidate = implementation_root / "trusted_data_synthesis"
    if (candidate / "src" / "trusted_synthesis").is_dir():
        return candidate
    raise ValueError("v26.157 cannot resolve package root")


class PreflightReplayAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    preflight_report_id: str = EXPECTED_PREFLIGHT_REPORT_ID
    preflight_report_sha256: str = EXPECTED_PREFLIGHT_REPORT_SHA256
    preflight_output_file_count: Literal[11] = 11
    preflight_rebuilt_file_count: Literal[11] = 11
    preflight_byte_match_count: Literal[11] = 11
    execution_implementation_sha256: str = Field(min_length=64, max_length=64)
    replay_before_assignment_loading: Literal[True] = True
    credential_lookup_attempted: Literal[False] = False
    model_client_constructed: Literal[False] = False
    provider_calls: Literal[0] = 0
    stage_two_provider_calls: Literal[0] = 0
    gpu_jobs: Literal[0] = 0
    status: Literal["passed"] = "passed"

    @model_validator(mode="after")
    def validate_audit(self) -> PreflightReplayAudit:
        if self.audit_id != _identity(
            self,
            "audit_id",
            "finance_v26_valid_only_mapping_execution_source_replay:",
        ):
            raise ValueError("v26.157 source replay identity changed")
        return self


class StructuralStateCatalog(FrozenModel):
    catalog_id: str = Field(min_length=1)
    mapper_contract_id: str = Field(min_length=1)
    omega_task_context_catalog_id: str = Field(min_length=1)
    assignment_count: int = Field(ge=1, le=360)
    unique_structural_state_count: int = Field(ge=1, le=360)
    states: tuple[EmpiricalStructuralState, ...] = Field(min_length=1)
    provider_calls: Literal[0] = 0

    @model_validator(mode="after")
    def validate_catalog(self) -> StructuralStateCatalog:
        ids = tuple(item.state_id for item in self.states)
        if (
            self.unique_structural_state_count != len(self.states)
            or ids != tuple(sorted(set(ids)))
            or self.catalog_id
            != _identity(
                self,
                "catalog_id",
                "finance_v26_valid_only_structural_state_catalog:",
            )
        ):
            raise ValueError("v26.157 structural State Catalog changed")
        return self


class RouteProjectionCatalog(FrozenModel):
    catalog_id: str = Field(min_length=1)
    static_path_catalog_id: str = Field(min_length=1)
    assignment_count: int = Field(ge=1, le=360)
    unique_route_projection_count: int = Field(ge=1, le=360)
    projections: tuple[EmpiricalRouteProjection, ...] = Field(min_length=1)
    route_projection_is_not_structural_state: Literal[True] = True
    provider_calls: Literal[0] = 0

    @model_validator(mode="after")
    def validate_catalog(self) -> RouteProjectionCatalog:
        ids = tuple(item.projection_id for item in self.projections)
        if (
            self.unique_route_projection_count != len(self.projections)
            or ids != tuple(sorted(set(ids)))
            or self.catalog_id
            != _identity(
                self,
                "catalog_id",
                "finance_v26_valid_only_route_projection_catalog:",
            )
        ):
            raise ValueError("v26.157 route projection Catalog changed")
        return self


class TaskObservedStateSummary(FrozenModel):
    summary_id: str = Field(min_length=1)
    task_package_id: str = Field(min_length=1)
    source_task_artifact_id: str = Field(min_length=1)
    mechanism_id: str = Field(min_length=1)
    tier: str = Field(min_length=1)
    qualified_candidate_count: int = Field(ge=0, le=30)
    assignment_count: int = Field(ge=0, le=30)
    unique_structural_state_count: int = Field(ge=0, le=30)
    unconditional_assignment_count: int = Field(ge=0, le=12)
    conditioned_assignment_count: int = Field(ge=0, le=18)
    structural_state_ids: tuple[str, ...] = ()
    multiple_observed_qualified_states: bool
    frequency_or_probability_estimate: None = None
    schema_version: str = "finance_v26_task_observed_state_summary.v1"

    @model_validator(mode="after")
    def validate_summary(self) -> TaskObservedStateSummary:
        if (
            self.assignment_count != self.qualified_candidate_count
            or self.assignment_count
            != self.unconditional_assignment_count + self.conditioned_assignment_count
            or self.unique_structural_state_count != len(self.structural_state_ids)
            or self.structural_state_ids != tuple(sorted(set(self.structural_state_ids)))
            or self.multiple_observed_qualified_states != (self.unique_structural_state_count >= 2)
            or self.summary_id
            != _identity(
                self,
                "summary_id",
                "finance_v26_task_observed_state_summary:",
            )
        ):
            raise ValueError("v26.157 Task observed-State summary changed")
        return self


class ObservedStateSupportAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    exact_mapping_candidate_count: int = Field(ge=1, le=360)
    exact_assignment_count: int = Field(ge=1, le=360)
    unique_structural_state_count: int = Field(ge=1, le=360)
    task_summary_count: Literal[12] = 12
    tasks_with_qualified_assignments: int = Field(ge=1, le=12)
    tasks_with_multiple_observed_qualified_states: int = Field(ge=0, le=12)
    task_summaries: tuple[TaskObservedStateSummary, ...] = Field(
        min_length=12,
        max_length=12,
    )
    observed_state_support_is_descriptive_only: Literal[True] = True
    reachability_frequency_estimand_authorized: Literal[False] = False
    state_probability_distribution_authorized: Literal[False] = False
    vtdo_update_authorized: Literal[False] = False
    provider_calls: Literal[0] = 0
    status: Literal["passed"] = "passed"

    @model_validator(mode="after")
    def validate_audit(self) -> ObservedStateSupportAudit:
        if (
            self.exact_assignment_count != self.exact_mapping_candidate_count
            or self.tasks_with_qualified_assignments
            != sum(item.assignment_count > 0 for item in self.task_summaries)
            or self.tasks_with_multiple_observed_qualified_states
            != sum(item.multiple_observed_qualified_states for item in self.task_summaries)
            or self.audit_id
            != _identity(
                self,
                "audit_id",
                "finance_v26_valid_only_observed_state_support:",
            )
        ):
            raise ValueError("v26.157 observed State Support audit changed")
        return self


class MappingExecutionIntegrityAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    candidate_manifest_id: str = Field(min_length=1)
    mapper_contract_id: str = Field(min_length=1)
    exact_candidate_count: int = Field(ge=1, le=360)
    exact_assignment_count: int = Field(ge=1, le=360)
    exact_valid_only_authorization_count: int = Field(ge=1, le=360)
    exact_eight_parent_binding_count: int = Field(ge=1, le=360)
    exact_raw_trajectory_reconstruction_count: int = Field(ge=1, le=360)
    exact_runtime_alias_binding_count: int = Field(ge=1, le=360)
    mapper_invocation_count: int = Field(ge=1, le=360)
    support_exit_mapping_attempt_count: Literal[0] = 0
    instrument_failure_mapping_attempt_count: Literal[0] = 0
    privacy_failure_mapping_attempt_count: Literal[0] = 0
    base_invalid_mapping_attempt_count: Literal[0] = 0
    mechanism_unqualified_mapping_attempt_count: Literal[0] = 0
    nonqualified_mapping_attempt_count: Literal[0] = 0
    static_path_used_as_empirical_state_count: Literal[0] = 0
    host_inserted_state_count: Literal[0] = 0
    provider_calls: Literal[0] = 0
    stage_two_provider_calls: Literal[0] = 0
    status: Literal["passed"] = "passed"

    @model_validator(mode="after")
    def validate_audit(self) -> MappingExecutionIntegrityAudit:
        counts = (
            self.exact_assignment_count,
            self.exact_valid_only_authorization_count,
            self.exact_eight_parent_binding_count,
            self.exact_raw_trajectory_reconstruction_count,
            self.exact_runtime_alias_binding_count,
            self.mapper_invocation_count,
        )
        if any(item != self.exact_candidate_count for item in counts) or self.audit_id != _identity(
            self,
            "audit_id",
            "finance_v26_valid_only_mapping_execution_integrity:",
        ):
            raise ValueError("v26.157 Mapping execution integrity changed")
        return self


class ProspectiveTransitionContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    mapping_execution_integrity_audit_id: str = Field(min_length=1)
    observed_state_support_audit_id: str = Field(min_length=1)
    next_permitted_stage: str = NEXT_STAGE
    independent_raw_remapping_audit_authorized: Literal[True] = True
    provider_calls_authorized: Literal[False] = False
    mapping_rerun_or_repair_authorized: Literal[False] = False
    reachability_frequency_estimand_authorized: Literal[False] = False
    state_probability_distribution_authorized: Literal[False] = False
    vtdo_training_release_or_production_authorized: Literal[False] = False
    status: Literal["independent_raw_remap_audit_only"] = "independent_raw_remap_audit_only"

    @model_validator(mode="after")
    def validate_contract(self) -> ProspectiveTransitionContract:
        if self.contract_id != _identity(
            self,
            "contract_id",
            "finance_v26_valid_only_mapping_execution_transition:",
        ):
            raise ValueError("v26.157 transition identity changed")
        return self


class DetailFile(FrozenModel):
    relative_path: str = Field(min_length=1)
    sha256: str = Field(min_length=64, max_length=64)
    byte_count: int = Field(gt=0)


class ValidOnlyMappingExecutionReport(FrozenModel):
    report_id: str = Field(min_length=1)
    prospective_execution_id: str = EXPECTED_PROSPECTIVE_EXECUTION_ID
    preflight_replay_audit_id: str = Field(min_length=1)
    candidate_manifest_id: str = Field(min_length=1)
    assignment_count: int = Field(ge=1, le=360)
    unique_structural_state_count: int = Field(ge=1, le=360)
    tasks_with_multiple_observed_qualified_states: int = Field(ge=0, le=12)
    structural_state_catalog_id: str = Field(min_length=1)
    route_projection_catalog_id: str = Field(min_length=1)
    observed_state_support_audit_id: str = Field(min_length=1)
    execution_integrity_audit_id: str = Field(min_length=1)
    transition_contract_id: str = Field(min_length=1)
    provider_calls: Literal[0] = 0
    stage_two_provider_calls: Literal[0] = 0
    reachability_frequency_estimand_authorized: Literal[False] = False
    state_probability_distribution_authorized: Literal[False] = False
    detail_files: tuple[DetailFile, ...] = Field(min_length=7, max_length=7)
    status: Literal["valid_only_state_mapping_execution_complete"] = (
        "valid_only_state_mapping_execution_complete"
    )

    @model_validator(mode="after")
    def validate_report(self) -> ValidOnlyMappingExecutionReport:
        if self.report_id != _identity(
            self,
            "report_id",
            "finance_v26_valid_only_mapping_execution_report:",
        ):
            raise ValueError("v26.157 report identity changed")
        return self


class Inputs(FrozenModel):
    preflight_report: preflight.ValidOnlyMappingPreflightReport
    candidate_manifest: preflight.ValidOnlyMappingCandidateManifest
    omega_catalog: preflight.OmegaTaskContextCatalog
    mapper_contract: ValidOnlyStateMapperContract
    mapper_protocol: preflight.EmpiricalStateMapperProtocol
    runner_contract: preflight.ValidOnlyMappingRunnerContract
    preflight_transition: preflight.ProspectiveTransitionContract


def _preflight_replay(
    *,
    package_root: Path,
    implementation_root: Path,
    reachability_execution_dir: Path,
    postrun_dir: Path,
    preflight_dir: Path,
) -> PreflightReplayAudit:
    report_path = preflight_dir / "report.json"
    if not report_path.is_file() or _sha256(report_path) != EXPECTED_PREFLIGHT_REPORT_SHA256:
        raise ValueError("v26.157 preflight report SHA-256 changed")
    report = preflight.ValidOnlyMappingPreflightReport.model_validate(_load(report_path))
    if report.report_id != EXPECTED_PREFLIGHT_REPORT_ID:
        raise ValueError("v26.157 preflight report identity changed")
    with tempfile.TemporaryDirectory(prefix="v26_157_preflight_rebuild_") as temporary:
        rebuilt_dir = Path(temporary)
        rebuilt = preflight.build_preflight(
            package_root=package_root,
            implementation_root=implementation_root,
            execution_dir=reachability_execution_dir,
            postrun_dir=postrun_dir,
            output_dir=rebuilt_dir,
        )
        if rebuilt.report_id != EXPECTED_PREFLIGHT_REPORT_ID:
            raise ValueError("v26.157 independent preflight rebuild changed")
        frozen_files = tuple(
            sorted(path.name for path in preflight_dir.iterdir() if path.is_file())
        )
        rebuilt_files = tuple(sorted(path.name for path in rebuilt_dir.iterdir() if path.is_file()))
        if frozen_files != rebuilt_files or len(frozen_files) != 11:
            raise ValueError("v26.157 preflight output file set changed")
        matches = sum(
            (preflight_dir / name).read_bytes() == (rebuilt_dir / name).read_bytes()
            for name in frozen_files
        )
        if matches != 11:
            raise ValueError("v26.157 preflight byte reproduction changed")
    values = {"execution_implementation_sha256": _sha256(package_root / IMPLEMENTATION_PATH)}
    provisional = PreflightReplayAudit.model_construct(audit_id="pending", **values)
    return PreflightReplayAudit(
        audit_id=_identity(
            provisional,
            "audit_id",
            "finance_v26_valid_only_mapping_execution_source_replay:",
        ),
        **values,
    )


def _load_inputs(preflight_dir: Path) -> Inputs:
    report = preflight.ValidOnlyMappingPreflightReport.model_validate(
        _load(preflight_dir / "report.json")
    )
    manifest = preflight.ValidOnlyMappingCandidateManifest.model_validate(
        _load(preflight_dir / "candidate_manifest.json")
    )
    omega = preflight.OmegaTaskContextCatalog.model_validate(
        _load(preflight_dir / "omega_task_context_catalog.json")
    )
    mapper_contract = ValidOnlyStateMapperContract.model_validate(
        _load(preflight_dir / "valid_only_mapper_contract.json")
    )
    protocol = preflight.EmpiricalStateMapperProtocol.model_validate(
        _load(preflight_dir / "mapper_protocol.json")
    )
    runner = preflight.ValidOnlyMappingRunnerContract.model_validate(
        _load(preflight_dir / "runner_contract.json")
    )
    transition = preflight.ProspectiveTransitionContract.model_validate(
        _load(preflight_dir / "prospective_transition_contract.json")
    )
    if (
        report.report_id != EXPECTED_PREFLIGHT_REPORT_ID
        or runner.contract_id != EXPECTED_RUNNER_CONTRACT_ID
        or transition.contract_id != EXPECTED_TRANSITION_ID
        or runner.prospective_execution_id != EXPECTED_PROSPECTIVE_EXECUTION_ID
        or transition.next_permitted_stage
        != "valid_only_observed_reachability_state_mapping_execution_only"
        or not transition.state_mapping_execution_authorized
        or transition.provider_calls_authorized
        or manifest.qualified_candidate_count != report.qualified_candidate_count
        or manifest.state_assignment_count
        or manifest.structural_state_count
    ):
        raise ValueError("v26.157 preflight authorization changed")
    return Inputs(
        preflight_report=report,
        candidate_manifest=manifest,
        omega_catalog=omega,
        mapper_contract=mapper_contract,
        mapper_protocol=protocol,
        runner_contract=runner,
        preflight_transition=transition,
    )


def _map_assignments(
    *,
    inputs: Inputs,
    reachability_inputs: preflight.Inputs,
) -> tuple[ValidOnlyEmpiricalStateAssignment, ...]:
    results = {item.job_id: item for item in reachability_inputs.projection.recomputed_results}
    contexts = {item.task_package_id: item for item in inputs.omega_catalog.contexts}
    assignments: list[ValidOnlyEmpiricalStateAssignment] = []
    for candidate in inputs.candidate_manifest.candidates:
        result = results[candidate.job_id]
        report = result.joint_result.qualified_report
        if (
            report.valid is not True
            or not result.state_mapping_eligible
            or report.report_id != candidate.qualified_validity_report_id
            or result.qualified_trajectory_validity is not True
        ):
            raise ValueError(
                f"v26.157 Candidate lost independent Qualified validity: {candidate.job_id}"
            )
        job = reachability_inputs.jobs[candidate.job_id]
        package = reachability_inputs.packages[candidate.task_package_id]
        context = contexts[candidate.task_package_id]
        raw = reachability_inputs.raws[candidate.job_id]
        descriptor = result.raw_execution_artifact
        if (
            descriptor.relative_path != candidate.raw_execution_relative_path
            or descriptor.sha256 != candidate.raw_execution_sha256
            or raw.artifact_id != candidate.trajectory_id
            or raw.terminal_disposition == "measurement_support_exit"
            or not raw.measurement_support_available
            or not raw.instrument_integrity
            or not raw.privacy_compliant
        ):
            raise ValueError(f"v26.157 Candidate Raw binding changed: {candidate.job_id}")

        trajectory = preflight._trajectory_projection(raw)
        aliases = preflight._runtime_aliases(package, raw)
        route = make_empirical_route_projection(
            sampling_mode=job.sampling_mode,
            public_condition_id=job.public_condition_id,
            requested_path_id=job.requested_path_id,
            requested_path_strategy=job.requested_path_strategy,
            static_path_catalog_id=inputs.mapper_protocol.static_path_catalog_id,
            trajectory=trajectory,
        )
        if (
            trajectory.trajectory_content_hash != candidate.trajectory_content_hash
            or trajectory.raw_observation_prefix_hash != candidate.raw_observation_prefix_hash
            or context.context_id != candidate.omega_task_context_id
            or route.projection_id != candidate.route_condition_id
            or canonical_hash(
                aliases,
                prefix="finance_v26_runtime_operation_alias_binding:",
            )
            != candidate.runtime_operation_alias_binding_hash
        ):
            raise ValueError(f"v26.157 Candidate mapping input changed: {candidate.job_id}")
        assignment = map_independently_valid_public_trajectory_to_state(
            trajectory=trajectory,
            qualified_validity_report=report,
            mapper_contract=inputs.mapper_contract,
            omega_task_context_id=context.context_id,
            route_projection=route,
            runtime_operation_aliases=aliases,
        )
        if (
            assignment.trajectory_content_hash != candidate.trajectory_content_hash
            or assignment.qualified_validity_report_id != candidate.qualified_validity_report_id
            or assignment.omega_task_context_id != candidate.omega_task_context_id
            or assignment.route_condition_id != candidate.route_condition_id
            or assignment.static_path_catalog_id != candidate.static_path_catalog_id
            or assignment.raw_observation_prefix_hash != candidate.raw_observation_prefix_hash
        ):
            raise ValueError(f"v26.157 Assignment parent binding changed: {candidate.job_id}")
        assignments.append(assignment)
    ordered = tuple(sorted(assignments, key=lambda item: item.assignment_id))
    if len(ordered) != inputs.candidate_manifest.qualified_candidate_count:
        raise ValueError("v26.157 State Assignment denominator changed")
    return ordered


def _state_catalog(
    *,
    inputs: Inputs,
    assignments: tuple[ValidOnlyEmpiricalStateAssignment, ...],
) -> StructuralStateCatalog:
    by_id: dict[str, EmpiricalStructuralState] = {}
    for item in assignments:
        previous = by_id.setdefault(item.structural_state_id, item.structural_state)
        if _canonical_bytes(previous) != _canonical_bytes(item.structural_state):
            raise ValueError("v26.157 structural State identity collision")
    states = tuple(sorted(by_id.values(), key=lambda item: item.state_id))
    values = {
        "mapper_contract_id": inputs.mapper_contract.contract_id,
        "omega_task_context_catalog_id": inputs.omega_catalog.catalog_id,
        "assignment_count": len(assignments),
        "unique_structural_state_count": len(states),
        "states": states,
    }
    provisional = StructuralStateCatalog.model_construct(catalog_id="pending", **values)
    return StructuralStateCatalog(
        catalog_id=_identity(
            provisional,
            "catalog_id",
            "finance_v26_valid_only_structural_state_catalog:",
        ),
        **values,
    )


def _route_catalog(
    *,
    inputs: Inputs,
    assignments: tuple[ValidOnlyEmpiricalStateAssignment, ...],
) -> RouteProjectionCatalog:
    by_id: dict[str, EmpiricalRouteProjection] = {}
    for item in assignments:
        previous = by_id.setdefault(
            item.route_condition_id,
            item.route_projection,
        )
        if _canonical_bytes(previous) != _canonical_bytes(item.route_projection):
            raise ValueError("v26.157 route projection identity collision")
    projections = tuple(sorted(by_id.values(), key=lambda item: item.projection_id))
    values = {
        "static_path_catalog_id": inputs.mapper_protocol.static_path_catalog_id,
        "assignment_count": len(assignments),
        "unique_route_projection_count": len(projections),
        "projections": projections,
    }
    provisional = RouteProjectionCatalog.model_construct(catalog_id="pending", **values)
    return RouteProjectionCatalog(
        catalog_id=_identity(
            provisional,
            "catalog_id",
            "finance_v26_valid_only_route_projection_catalog:",
        ),
        **values,
    )


class StateAssignmentCatalog(FrozenModel):
    catalog_id: str = Field(min_length=1)
    candidate_manifest_id: str = Field(min_length=1)
    mapper_contract_id: str = Field(min_length=1)
    assignment_count: int = Field(ge=1, le=360)
    assignments: tuple[ValidOnlyEmpiricalStateAssignment, ...] = Field(min_length=1)
    provider_calls: Literal[0] = 0

    @model_validator(mode="after")
    def validate_catalog(self) -> StateAssignmentCatalog:
        ids = tuple(item.assignment_id for item in self.assignments)
        trajectories = tuple(item.trajectory_id for item in self.assignments)
        if (
            self.assignment_count != len(self.assignments)
            or ids != tuple(sorted(set(ids)))
            or len(set(trajectories)) != len(trajectories)
            or self.catalog_id
            != _identity(
                self,
                "catalog_id",
                "finance_v26_valid_only_state_assignment_catalog:",
            )
        ):
            raise ValueError("v26.157 State Assignment Catalog changed")
        return self


def _assignment_catalog(
    *,
    inputs: Inputs,
    assignments: tuple[ValidOnlyEmpiricalStateAssignment, ...],
) -> StateAssignmentCatalog:
    values = {
        "candidate_manifest_id": inputs.candidate_manifest.manifest_id,
        "mapper_contract_id": inputs.mapper_contract.contract_id,
        "assignment_count": len(assignments),
        "assignments": assignments,
    }
    provisional = StateAssignmentCatalog.model_construct(
        catalog_id="pending",
        **values,
    )
    return StateAssignmentCatalog(
        catalog_id=_identity(
            provisional,
            "catalog_id",
            "finance_v26_valid_only_state_assignment_catalog:",
        ),
        **values,
    )


def _observed_state_support(
    *,
    inputs: Inputs,
    reachability_inputs: preflight.Inputs,
    assignments: tuple[ValidOnlyEmpiricalStateAssignment, ...],
    state_catalog: StructuralStateCatalog,
) -> ObservedStateSupportAudit:
    candidates = {item.trajectory_id: item for item in inputs.candidate_manifest.candidates}
    assignments_by_task: dict[
        str,
        list[tuple[ValidOnlyEmpiricalStateAssignment, preflight.ValidOnlyMappingCandidate]],
    ] = defaultdict(list)
    for assignment in assignments:
        candidate = candidates[assignment.trajectory_id]
        assignments_by_task[candidate.task_package_id].append((assignment, candidate))

    summaries: list[TaskObservedStateSummary] = []
    for package in reachability_inputs.task_catalog.packages:
        rows = assignments_by_task.get(package.task_package_id, [])
        state_ids = tuple(sorted({item.structural_state_id for item, _ in rows}))
        values = {
            "task_package_id": package.task_package_id,
            "source_task_artifact_id": package.source_task_artifact_id,
            "mechanism_id": package.mechanism_id,
            "tier": package.tier,
            "qualified_candidate_count": len(rows),
            "assignment_count": len(rows),
            "unique_structural_state_count": len(state_ids),
            "unconditional_assignment_count": sum(
                candidate.sampling_mode == "reachability_unconditional" for _, candidate in rows
            ),
            "conditioned_assignment_count": sum(
                candidate.sampling_mode == "reachability_conditioned" for _, candidate in rows
            ),
            "structural_state_ids": state_ids,
            "multiple_observed_qualified_states": len(state_ids) >= 2,
        }
        provisional = TaskObservedStateSummary.model_construct(
            summary_id="pending",
            **values,
        )
        summaries.append(
            TaskObservedStateSummary(
                summary_id=_identity(
                    provisional,
                    "summary_id",
                    "finance_v26_task_observed_state_summary:",
                ),
                **values,
            )
        )
    ordered = tuple(sorted(summaries, key=lambda item: item.summary_id))
    values = {
        "exact_mapping_candidate_count": (inputs.candidate_manifest.qualified_candidate_count),
        "exact_assignment_count": len(assignments),
        "unique_structural_state_count": (state_catalog.unique_structural_state_count),
        "tasks_with_qualified_assignments": sum(item.assignment_count > 0 for item in ordered),
        "tasks_with_multiple_observed_qualified_states": sum(
            item.multiple_observed_qualified_states for item in ordered
        ),
        "task_summaries": ordered,
    }
    provisional = ObservedStateSupportAudit.model_construct(
        audit_id="pending",
        **values,
    )
    return ObservedStateSupportAudit(
        audit_id=_identity(
            provisional,
            "audit_id",
            "finance_v26_valid_only_observed_state_support:",
        ),
        **values,
    )


def _integrity(
    *,
    inputs: Inputs,
    assignments: tuple[ValidOnlyEmpiricalStateAssignment, ...],
) -> MappingExecutionIntegrityAudit:
    count = len(assignments)
    if any(
        item.mapper_contract_id != inputs.mapper_contract.contract_id
        or item.qualified_validity is not True
        or not item.valid_only_gate_crossed
        or item.static_path_used_as_empirical_state
        for item in assignments
    ):
        raise ValueError("v26.157 valid-only Assignment integrity changed")
    values = {
        "candidate_manifest_id": inputs.candidate_manifest.manifest_id,
        "mapper_contract_id": inputs.mapper_contract.contract_id,
        "exact_candidate_count": inputs.candidate_manifest.qualified_candidate_count,
        "exact_assignment_count": count,
        "exact_valid_only_authorization_count": count,
        "exact_eight_parent_binding_count": count,
        "exact_raw_trajectory_reconstruction_count": count,
        "exact_runtime_alias_binding_count": count,
        "mapper_invocation_count": count,
    }
    provisional = MappingExecutionIntegrityAudit.model_construct(
        audit_id="pending",
        **values,
    )
    return MappingExecutionIntegrityAudit(
        audit_id=_identity(
            provisional,
            "audit_id",
            "finance_v26_valid_only_mapping_execution_integrity:",
        ),
        **values,
    )


def _transition(
    *,
    integrity: MappingExecutionIntegrityAudit,
    support: ObservedStateSupportAudit,
) -> ProspectiveTransitionContract:
    values = {
        "mapping_execution_integrity_audit_id": integrity.audit_id,
        "observed_state_support_audit_id": support.audit_id,
    }
    provisional = ProspectiveTransitionContract.model_construct(
        contract_id="pending",
        **values,
    )
    return ProspectiveTransitionContract(
        contract_id=_identity(
            provisional,
            "contract_id",
            "finance_v26_valid_only_mapping_execution_transition:",
        ),
        **values,
    )


def _detail(path: Path, root: Path) -> DetailFile:
    return DetailFile(
        relative_path=path.relative_to(root).as_posix(),
        sha256=_sha256(path),
        byte_count=path.stat().st_size,
    )


def build_execution(
    *,
    package_root: Path,
    implementation_root: Path,
    reachability_execution_dir: Path,
    postrun_dir: Path,
    preflight_dir: Path,
    output_dir: Path,
) -> ValidOnlyMappingExecutionReport:
    source = _preflight_replay(
        package_root=package_root,
        implementation_root=implementation_root,
        reachability_execution_dir=reachability_execution_dir,
        postrun_dir=postrun_dir,
        preflight_dir=preflight_dir,
    )
    print(
        f"[v26.157] preflight replay {source.preflight_byte_match_count}/11 exact",
        flush=True,
    )
    inputs = _load_inputs(preflight_dir)
    reachability_inputs = preflight._load_inputs(
        package_root=package_root,
        postrun_dir=postrun_dir,
        execution_dir=reachability_execution_dir,
    )
    assignments = _map_assignments(
        inputs=inputs,
        reachability_inputs=reachability_inputs,
    )
    assignment_catalog = _assignment_catalog(
        inputs=inputs,
        assignments=assignments,
    )
    state_catalog = _state_catalog(inputs=inputs, assignments=assignments)
    route_catalog = _route_catalog(inputs=inputs, assignments=assignments)
    support = _observed_state_support(
        inputs=inputs,
        reachability_inputs=reachability_inputs,
        assignments=assignments,
        state_catalog=state_catalog,
    )
    integrity = _integrity(inputs=inputs, assignments=assignments)
    transition = _transition(integrity=integrity, support=support)

    output_dir.mkdir(parents=True, exist_ok=True)
    outputs: tuple[tuple[str, BaseModel], ...] = (
        ("assignment_catalog.json", assignment_catalog),
        ("execution_integrity_audit.json", integrity),
        ("observed_state_support_audit.json", support),
        ("preflight_replay_audit.json", source),
        ("prospective_transition_contract.json", transition),
        ("route_projection_catalog.json", route_catalog),
        ("structural_state_catalog.json", state_catalog),
    )
    for name, value in outputs:
        _write_json_atomic(output_dir / name, value)
    details = tuple(_detail(output_dir / name, output_dir) for name, _ in outputs)
    values = {
        "preflight_replay_audit_id": source.audit_id,
        "candidate_manifest_id": inputs.candidate_manifest.manifest_id,
        "assignment_count": len(assignments),
        "unique_structural_state_count": (state_catalog.unique_structural_state_count),
        "tasks_with_multiple_observed_qualified_states": (
            support.tasks_with_multiple_observed_qualified_states
        ),
        "structural_state_catalog_id": state_catalog.catalog_id,
        "route_projection_catalog_id": route_catalog.catalog_id,
        "observed_state_support_audit_id": support.audit_id,
        "execution_integrity_audit_id": integrity.audit_id,
        "transition_contract_id": transition.contract_id,
        "detail_files": details,
    }
    provisional = ValidOnlyMappingExecutionReport.model_construct(
        report_id="pending",
        **values,
    )
    report = ValidOnlyMappingExecutionReport(
        report_id=_identity(
            provisional,
            "report_id",
            "finance_v26_valid_only_mapping_execution_report:",
        ),
        **values,
    )
    _write_json_atomic(output_dir / "report.json", report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Execute valid-only empirical Reachability State Mapping."
    )
    parser.add_argument("--implementation-root", type=Path, default=Path.cwd())
    parser.add_argument("--package-root", type=Path)
    parser.add_argument("--reachability-execution-dir", type=Path)
    parser.add_argument("--postrun-dir", type=Path)
    parser.add_argument("--preflight-dir", type=Path)
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    package_root = (
        args.package_root
        if args.package_root is not None
        else _resolve_package_root(args.implementation_root)
    )
    reachability_execution_dir = (
        args.reachability_execution_dir
        if args.reachability_execution_dir is not None
        else package_root / reachability_execution.OUTPUT_DIR
    )
    postrun_dir = (
        args.postrun_dir if args.postrun_dir is not None else package_root / postrun.OUTPUT_DIR
    )
    preflight_dir = (
        args.preflight_dir
        if args.preflight_dir is not None
        else package_root / preflight.OUTPUT_DIR
    )
    output_dir = args.output_dir if args.output_dir is not None else package_root / OUTPUT_DIR
    report = build_execution(
        package_root=package_root,
        implementation_root=args.implementation_root,
        reachability_execution_dir=reachability_execution_dir,
        postrun_dir=postrun_dir,
        preflight_dir=preflight_dir,
        output_dir=output_dir,
    )
    print(
        "[v26.157] valid-only State Mapping complete "
        f"assignments={report.assignment_count} "
        f"states={report.unique_structural_state_count} "
        f"multi_state_tasks={report.tasks_with_multiple_observed_qualified_states} "
        f"provider_calls={report.provider_calls} "
        f"report={report.report_id}",
        flush=True,
    )


if __name__ == "__main__":
    main()
