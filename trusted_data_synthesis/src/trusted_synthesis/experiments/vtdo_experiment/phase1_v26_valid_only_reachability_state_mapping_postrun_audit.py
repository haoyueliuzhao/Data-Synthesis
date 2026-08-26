from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from collections import defaultdict
from pathlib import Path
from typing import Any, Final, Literal, cast

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.core.trajectory.empirical_state_mapping import (
    PublicTrajectoryAction,
    ValidOnlyEmpiricalStateAssignment,
    make_empirical_route_projection,
    make_public_trajectory_projection,
    map_independently_valid_public_trajectory_to_state,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_authority_preserving_verifier_replay as authority_verifier,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_reachability_execution as reachability_execution,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_reachability_postrun_audit as reachability_postrun,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_valid_only_reachability_state_mapping_execution as execution,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_valid_only_reachability_state_mapping_preflight as preflight,
)
from trusted_synthesis.hashing import canonical_hash
from trusted_synthesis.runtime.agent import prospective_reachability_runner_vnext as runner_vnext

RUN_ID: Final = "finance_v26_158_valid_only_state_mapping_postrun_audit_v1_20260826"
OUTPUT_DIR: Final = (
    "artifacts/vtdo_experiment/finance_v26_158_valid_only_state_mapping_postrun_audit_v1_20260826"
)
IMPLEMENTATION_PATH: Final = (
    "src/trusted_synthesis/experiments/vtdo_experiment/"
    "phase1_v26_valid_only_reachability_state_mapping_postrun_audit.py"
)
NEXT_STAGE: Final = "no_further_experiment_authorized_without_new_audit_decision"

# Replaced after v26.157 is immutable.
EXPECTED_EXECUTION_REPORT_ID: Final = (
    "finance_v26_valid_only_mapping_execution_report:"
    "8cefac79a20405452c3dc2d70b693b795a58e7053519d028cda94eca0f173016"
)
EXPECTED_EXECUTION_REPORT_SHA256: Final = (
    "cdb5e63e5dba2f9944315d8dde17db9101bc819d3d43a9a59d9b4be8eac5012b"
)
EXPECTED_EXECUTION_TRANSITION_ID: Final = (
    "finance_v26_valid_only_mapping_execution_transition:"
    "cfec069ea14dd7148e81cdc395cfb9b4f1cc67b3a99a97b20cabf064e7db6311"
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
    raise ValueError("v26.158 cannot resolve package root")


class ExecutionReplayAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    execution_report_id: str = EXPECTED_EXECUTION_REPORT_ID
    execution_report_sha256: str = EXPECTED_EXECUTION_REPORT_SHA256
    execution_output_file_count: Literal[8] = 8
    execution_rebuilt_file_count: Literal[8] = 8
    execution_byte_match_count: Literal[8] = 8
    audit_implementation_sha256: str = Field(min_length=64, max_length=64)
    replay_before_saved_assignment_loading: Literal[True] = True
    credential_lookup_attempted: Literal[False] = False
    model_client_constructed: Literal[False] = False
    provider_calls: Literal[0] = 0
    stage_two_provider_calls: Literal[0] = 0
    gpu_jobs: Literal[0] = 0
    status: Literal["passed"] = "passed"

    @model_validator(mode="after")
    def validate_audit(self) -> ExecutionReplayAudit:
        if self.audit_id != _identity(
            self,
            "audit_id",
            "finance_v26_valid_only_mapping_postrun_source_replay:",
        ):
            raise ValueError("v26.158 source replay identity changed")
        return self


class IndependentRawRemappingAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    execution_report_id: str = EXPECTED_EXECUTION_REPORT_ID
    candidate_manifest_id: str = Field(min_length=1)
    mapper_contract_id: str = Field(min_length=1)
    exact_candidate_count: int = Field(ge=1, le=360)
    exact_saved_assignment_count: int = Field(ge=1, le=360)
    exact_raw_remapped_assignment_count: int = Field(ge=1, le=360)
    exact_assignment_byte_match_count: int = Field(ge=1, le=360)
    exact_structural_state_id_match_count: int = Field(ge=1, le=360)
    exact_route_projection_id_match_count: int = Field(ge=1, le=360)
    exact_trajectory_content_hash_match_count: int = Field(ge=1, le=360)
    exact_qualified_report_id_match_count: int = Field(ge=1, le=360)
    exact_omega_context_id_match_count: int = Field(ge=1, le=360)
    exact_static_path_catalog_id_match_count: int = Field(ge=1, le=360)
    exact_raw_observation_prefix_hash_match_count: int = Field(ge=1, le=360)
    remapped_assignments: tuple[ValidOnlyEmpiricalStateAssignment, ...] = Field(min_length=1)
    used_preflight_trajectory_projection_helper: Literal[False] = False
    used_preflight_runtime_alias_helper: Literal[False] = False
    used_execution_assignment_helper: Literal[False] = False
    trusted_saved_assignment_fields_as_mapper_inputs: Literal[False] = False
    shared_frozen_mapper_core_used: Literal[True] = True
    provider_calls: Literal[0] = 0
    status: Literal["passed"] = "passed"

    @model_validator(mode="after")
    def validate_audit(self) -> IndependentRawRemappingAudit:
        counts = (
            self.exact_saved_assignment_count,
            self.exact_raw_remapped_assignment_count,
            self.exact_assignment_byte_match_count,
            self.exact_structural_state_id_match_count,
            self.exact_route_projection_id_match_count,
            self.exact_trajectory_content_hash_match_count,
            self.exact_qualified_report_id_match_count,
            self.exact_omega_context_id_match_count,
            self.exact_static_path_catalog_id_match_count,
            self.exact_raw_observation_prefix_hash_match_count,
        )
        ids = tuple(item.assignment_id for item in self.remapped_assignments)
        if (
            any(item != self.exact_candidate_count for item in counts)
            or len(self.remapped_assignments) != self.exact_candidate_count
            or ids != tuple(sorted(set(ids)))
            or self.audit_id
            != _identity(
                self,
                "audit_id",
                "finance_v26_valid_only_independent_raw_remapping:",
            )
        ):
            raise ValueError("v26.158 independent Raw remapping changed")
        return self


class IndependentAssignmentBindingAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    exact_assignment_count: int = Field(ge=1, le=360)
    trajectory_content_hash_binding_count: int = Field(ge=1, le=360)
    qualified_validity_report_binding_count: int = Field(ge=1, le=360)
    omega_task_context_binding_count: int = Field(ge=1, le=360)
    mapper_contract_binding_count: int = Field(ge=1, le=360)
    structural_state_binding_count: int = Field(ge=1, le=360)
    route_condition_binding_count: int = Field(ge=1, le=360)
    static_path_catalog_binding_count: int = Field(ge=1, le=360)
    raw_observation_prefix_binding_count: int = Field(ge=1, le=360)
    support_exit_assignment_count: Literal[0] = 0
    instrument_failure_assignment_count: Literal[0] = 0
    privacy_failure_assignment_count: Literal[0] = 0
    base_invalid_assignment_count: Literal[0] = 0
    mechanism_unqualified_assignment_count: Literal[0] = 0
    static_path_used_as_empirical_state_count: Literal[0] = 0
    provider_calls: Literal[0] = 0
    status: Literal["passed"] = "passed"

    @model_validator(mode="after")
    def validate_audit(self) -> IndependentAssignmentBindingAudit:
        counts = (
            self.trajectory_content_hash_binding_count,
            self.qualified_validity_report_binding_count,
            self.omega_task_context_binding_count,
            self.mapper_contract_binding_count,
            self.structural_state_binding_count,
            self.route_condition_binding_count,
            self.static_path_catalog_binding_count,
            self.raw_observation_prefix_binding_count,
        )
        if any(
            item != self.exact_assignment_count for item in counts
        ) or self.audit_id != _identity(
            self,
            "audit_id",
            "finance_v26_valid_only_assignment_binding_audit:",
        ):
            raise ValueError("v26.158 Assignment binding audit changed")
        return self


class IndependentObservedStateAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    assignment_count: int = Field(ge=1, le=360)
    unique_structural_state_count: int = Field(ge=1, le=360)
    task_summary_count: Literal[12] = 12
    exact_saved_task_summary_match_count: Literal[12] = 12
    tasks_with_qualified_assignments: int = Field(ge=1, le=12)
    tasks_with_multiple_observed_qualified_states: int = Field(ge=0, le=12)
    task_summaries: tuple[execution.TaskObservedStateSummary, ...] = Field(
        min_length=12,
        max_length=12,
    )
    reachability_measurement_gate_passed: Literal[False] = False
    observed_state_support_is_descriptive_only: Literal[True] = True
    reachability_frequency_estimand_authorized: Literal[False] = False
    state_probability_distribution_authorized: Literal[False] = False
    provider_calls: Literal[0] = 0
    status: Literal["passed"] = "passed"

    @model_validator(mode="after")
    def validate_audit(self) -> IndependentObservedStateAudit:
        if (
            self.tasks_with_qualified_assignments
            != sum(item.assignment_count > 0 for item in self.task_summaries)
            or self.tasks_with_multiple_observed_qualified_states
            != sum(item.multiple_observed_qualified_states for item in self.task_summaries)
            or self.audit_id
            != _identity(
                self,
                "audit_id",
                "finance_v26_valid_only_independent_observed_state:",
            )
        ):
            raise ValueError("v26.158 independent observed-State audit changed")
        return self


class OutcomeInterpretation(FrozenModel):
    interpretation_id: str = Field(min_length=1)
    assignment_count: int = Field(ge=1, le=360)
    unique_structural_state_count: int = Field(ge=1, le=360)
    tasks_with_multiple_observed_qualified_states: int = Field(ge=0, le=12)
    at_least_one_task_has_multiple_qualified_states: bool
    empirical_multiple_state_existence_supported: bool
    per_task_state_support_observed: Literal[True] = True
    valid_only_state_mapping_completed: Literal[True] = True
    reachability_frequency_estimated: Literal[False] = False
    state_probability_distribution_estimated: Literal[False] = False
    compiler_path_equated_to_empirical_state: Literal[False] = False
    support_exit_reclassified_or_mapped: Literal[False] = False
    vtdo_contribution_novelty_or_training_claim_authorized: Literal[False] = False
    status: Literal["bounded_descriptive_state_support"] = "bounded_descriptive_state_support"

    @model_validator(mode="after")
    def validate_interpretation(self) -> OutcomeInterpretation:
        expected = self.tasks_with_multiple_observed_qualified_states > 0
        if (
            self.at_least_one_task_has_multiple_qualified_states != expected
            or self.empirical_multiple_state_existence_supported != expected
            or self.interpretation_id
            != _identity(
                self,
                "interpretation_id",
                "finance_v26_valid_only_mapping_outcome_interpretation:",
            )
        ):
            raise ValueError("v26.158 outcome interpretation changed")
        return self


class MutationResult(FrozenModel):
    mutation_name: str = Field(min_length=1)
    rejected: Literal[True] = True


class DestructiveAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    mutation_count: Literal[16] = 16
    rejected_count: Literal[16] = 16
    mutation_results: tuple[MutationResult, ...] = Field(
        min_length=16,
        max_length=16,
    )
    provider_calls: Literal[0] = 0
    status: Literal["passed"] = "passed"

    @model_validator(mode="after")
    def validate_audit(self) -> DestructiveAudit:
        names = tuple(item.mutation_name for item in self.mutation_results)
        if names != tuple(sorted(set(names))) or self.audit_id != _identity(
            self,
            "audit_id",
            "finance_v26_valid_only_mapping_postrun_destructive:",
        ):
            raise ValueError("v26.158 destructive audit changed")
        return self


class FinalDecisionContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    independent_raw_remapping_audit_id: str = Field(min_length=1)
    independent_assignment_binding_audit_id: str = Field(min_length=1)
    independent_observed_state_audit_id: str = Field(min_length=1)
    outcome_interpretation_id: str = Field(min_length=1)
    next_permitted_stage: str = NEXT_STAGE
    valid_only_state_mapping_evidence_frozen: Literal[True] = True
    provider_calls_authorized: Literal[False] = False
    reachability_rerun_recovery_or_pooling_authorized: Literal[False] = False
    reachability_frequency_estimand_authorized: Literal[False] = False
    state_probability_distribution_authorized: Literal[False] = False
    state_mapping_rerun_repair_or_threshold_change_authorized: Literal[False] = False
    vtdo_training_release_or_production_authorized: Literal[False] = False
    status: Literal["mapping_audit_complete_no_further_transition"] = (
        "mapping_audit_complete_no_further_transition"
    )

    @model_validator(mode="after")
    def validate_contract(self) -> FinalDecisionContract:
        if self.contract_id != _identity(
            self,
            "contract_id",
            "finance_v26_valid_only_mapping_final_decision:",
        ):
            raise ValueError("v26.158 final decision identity changed")
        return self


class DetailFile(FrozenModel):
    relative_path: str = Field(min_length=1)
    sha256: str = Field(min_length=64, max_length=64)
    byte_count: int = Field(gt=0)


class ValidOnlyMappingPostrunAuditReport(FrozenModel):
    report_id: str = Field(min_length=1)
    execution_replay_audit_id: str = Field(min_length=1)
    independent_raw_remapping_audit_id: str = Field(min_length=1)
    independent_assignment_binding_audit_id: str = Field(min_length=1)
    independent_observed_state_audit_id: str = Field(min_length=1)
    outcome_interpretation_id: str = Field(min_length=1)
    destructive_audit_id: str = Field(min_length=1)
    final_decision_contract_id: str = Field(min_length=1)
    assignment_count: int = Field(ge=1, le=360)
    unique_structural_state_count: int = Field(ge=1, le=360)
    tasks_with_multiple_observed_qualified_states: int = Field(ge=0, le=12)
    provider_calls: Literal[0] = 0
    stage_two_provider_calls: Literal[0] = 0
    reachability_frequency_estimand_authorized: Literal[False] = False
    state_probability_distribution_authorized: Literal[False] = False
    detail_files: tuple[DetailFile, ...] = Field(min_length=7, max_length=7)
    status: Literal["valid_only_state_mapping_independently_audited"] = (
        "valid_only_state_mapping_independently_audited"
    )

    @model_validator(mode="after")
    def validate_report(self) -> ValidOnlyMappingPostrunAuditReport:
        if self.report_id != _identity(
            self,
            "report_id",
            "finance_v26_valid_only_mapping_postrun_audit_report:",
        ):
            raise ValueError("v26.158 report identity changed")
        return self


def _execution_replay(
    *,
    package_root: Path,
    implementation_root: Path,
    reachability_execution_dir: Path,
    postrun_dir: Path,
    mapping_preflight_dir: Path,
    execution_dir: Path,
) -> ExecutionReplayAudit:
    report_path = execution_dir / "report.json"
    if not report_path.is_file() or _sha256(report_path) != EXPECTED_EXECUTION_REPORT_SHA256:
        raise ValueError("v26.158 execution report SHA-256 changed")
    report = execution.ValidOnlyMappingExecutionReport.model_validate(_load(report_path))
    if report.report_id != EXPECTED_EXECUTION_REPORT_ID:
        raise ValueError("v26.158 execution report identity changed")
    with tempfile.TemporaryDirectory(prefix="v26_158_execution_rebuild_") as temporary:
        rebuilt_dir = Path(temporary)
        rebuilt = execution.build_execution(
            package_root=package_root,
            implementation_root=implementation_root,
            reachability_execution_dir=reachability_execution_dir,
            postrun_dir=postrun_dir,
            preflight_dir=mapping_preflight_dir,
            output_dir=rebuilt_dir,
        )
        if rebuilt.report_id != EXPECTED_EXECUTION_REPORT_ID:
            raise ValueError("v26.158 independent execution rebuild changed")
        frozen_files = tuple(
            sorted(path.name for path in execution_dir.iterdir() if path.is_file())
        )
        rebuilt_files = tuple(sorted(path.name for path in rebuilt_dir.iterdir() if path.is_file()))
        if frozen_files != rebuilt_files or len(frozen_files) != 8:
            raise ValueError("v26.158 execution output file set changed")
        matches = sum(
            (execution_dir / name).read_bytes() == (rebuilt_dir / name).read_bytes()
            for name in frozen_files
        )
        if matches != 8:
            raise ValueError("v26.158 execution byte reproduction changed")
    values = {"audit_implementation_sha256": _sha256(package_root / IMPLEMENTATION_PATH)}
    provisional = ExecutionReplayAudit.model_construct(audit_id="pending", **values)
    return ExecutionReplayAudit(
        audit_id=_identity(
            provisional,
            "audit_id",
            "finance_v26_valid_only_mapping_postrun_source_replay:",
        ),
        **values,
    )


def _independent_trajectory_projection(
    raw: runner_vnext.FreshReachabilityRawExecution,
):
    observations = {item.call.call_index: item for item in raw.observations}
    actions: list[PublicTrajectoryAction] = []
    for action_index, record in enumerate(raw.commits):
        commit = record.commit
        call = commit.call
        observation = observations.get(call.call_index) if call is not None else None
        actions.append(
            PublicTrajectoryAction(
                action_index=action_index,
                decision_kind=commit.decision_kind,
                action_kind=commit.action,
                tool_id=call.tool_id if call is not None else None,
                arguments=dict(call.arguments) if call is not None else {},
                observation_status=(observation.status if observation is not None else None),
                error_code=(observation.error_code if observation is not None else None),
                observation_result=(dict(observation.result) if observation is not None else None),
                evidence_ids=(
                    tuple(sorted(set(observation.evidence_ids))) if observation is not None else ()
                ),
                provenance_hashes=(
                    tuple(sorted(set(observation.provenance_hashes)))
                    if observation is not None
                    else ()
                ),
            )
        )
    completed = raw.completed_result
    return make_public_trajectory_projection(
        trajectory_id=raw.artifact_id,
        terminal_disposition=raw.terminal_disposition,
        actions=actions,
        semantic_rejections=tuple(item.model_dump(mode="json") for item in raw.semantic_rejections),
        final_result=(
            dict(completed.final_payload.answer.result) if completed is not None else None
        ),
        final_citations=(
            tuple(sorted({item.evidence_id for item in completed.final_payload.answer.citations}))
            if completed is not None
            else ()
        ),
    )


def _independent_runtime_aliases(package: Any, raw: Any) -> dict[str, str]:
    _, _, aliases, _ = authority_verifier.match_empirical_program(
        cast(Any, package.operational_record),
        raw.observations,
    )
    return dict(aliases)


def _independent_raw_remap(
    *,
    formal_assignments: execution.StateAssignmentCatalog,
    mapping_inputs: execution.Inputs,
    reachability_inputs: preflight.Inputs,
) -> IndependentRawRemappingAudit:
    saved = {item.trajectory_id: item for item in formal_assignments.assignments}
    results = {item.job_id: item for item in reachability_inputs.projection.recomputed_results}
    contexts = {item.task_package_id: item for item in mapping_inputs.omega_catalog.contexts}
    remapped: list[ValidOnlyEmpiricalStateAssignment] = []
    for candidate in mapping_inputs.candidate_manifest.candidates:
        result = results[candidate.job_id]
        qualified = result.joint_result.qualified_report
        job = reachability_inputs.jobs[candidate.job_id]
        package = reachability_inputs.packages[candidate.task_package_id]
        raw = reachability_inputs.raws[candidate.job_id]
        context = contexts[candidate.task_package_id]
        if (
            qualified.valid is not True
            or qualified.report_id != candidate.qualified_validity_report_id
            or result.base_trajectory_validity is not True
            or result.mechanism_qualification is not True
            or not result.measurement_support_available
            or not result.instrument_integrity
            or not result.privacy_compliant
        ):
            raise ValueError(
                f"v26.158 invalid Candidate reached independent Mapper: {candidate.job_id}"
            )
        trajectory = _independent_trajectory_projection(raw)
        aliases = _independent_runtime_aliases(package, raw)
        route = make_empirical_route_projection(
            sampling_mode=job.sampling_mode,
            public_condition_id=job.public_condition_id,
            requested_path_id=job.requested_path_id,
            requested_path_strategy=job.requested_path_strategy,
            static_path_catalog_id=candidate.static_path_catalog_id,
            trajectory=trajectory,
        )
        independent = map_independently_valid_public_trajectory_to_state(
            trajectory=trajectory,
            qualified_validity_report=qualified,
            mapper_contract=mapping_inputs.mapper_contract,
            omega_task_context_id=context.context_id,
            route_projection=route,
            runtime_operation_aliases=aliases,
        )
        persisted = saved.get(trajectory.trajectory_id)
        if persisted is None or _canonical_bytes(independent) != _canonical_bytes(persisted):
            raise ValueError(f"v26.158 independent Assignment changed: {candidate.job_id}")
        remapped.append(independent)
    ordered = tuple(sorted(remapped, key=lambda item: item.assignment_id))
    count = len(ordered)
    values = {
        "candidate_manifest_id": mapping_inputs.candidate_manifest.manifest_id,
        "mapper_contract_id": mapping_inputs.mapper_contract.contract_id,
        "exact_candidate_count": mapping_inputs.candidate_manifest.qualified_candidate_count,
        "exact_saved_assignment_count": len(formal_assignments.assignments),
        "exact_raw_remapped_assignment_count": count,
        "exact_assignment_byte_match_count": count,
        "exact_structural_state_id_match_count": count,
        "exact_route_projection_id_match_count": count,
        "exact_trajectory_content_hash_match_count": count,
        "exact_qualified_report_id_match_count": count,
        "exact_omega_context_id_match_count": count,
        "exact_static_path_catalog_id_match_count": count,
        "exact_raw_observation_prefix_hash_match_count": count,
        "remapped_assignments": ordered,
    }
    provisional = IndependentRawRemappingAudit.model_construct(
        audit_id="pending",
        **values,
    )
    return IndependentRawRemappingAudit(
        audit_id=_identity(
            provisional,
            "audit_id",
            "finance_v26_valid_only_independent_raw_remapping:",
        ),
        **values,
    )


def _binding_audit(
    remap: IndependentRawRemappingAudit,
) -> IndependentAssignmentBindingAudit:
    count = remap.exact_raw_remapped_assignment_count
    values = {
        "exact_assignment_count": count,
        "trajectory_content_hash_binding_count": count,
        "qualified_validity_report_binding_count": count,
        "omega_task_context_binding_count": count,
        "mapper_contract_binding_count": count,
        "structural_state_binding_count": count,
        "route_condition_binding_count": count,
        "static_path_catalog_binding_count": count,
        "raw_observation_prefix_binding_count": count,
    }
    provisional = IndependentAssignmentBindingAudit.model_construct(
        audit_id="pending",
        **values,
    )
    return IndependentAssignmentBindingAudit(
        audit_id=_identity(
            provisional,
            "audit_id",
            "finance_v26_valid_only_assignment_binding_audit:",
        ),
        **values,
    )


def _independent_observed_state(
    *,
    remap: IndependentRawRemappingAudit,
    mapping_inputs: execution.Inputs,
    reachability_inputs: preflight.Inputs,
    formal_support: execution.ObservedStateSupportAudit,
) -> IndependentObservedStateAudit:
    candidates = {item.trajectory_id: item for item in mapping_inputs.candidate_manifest.candidates}
    rows_by_task: dict[
        str,
        list[
            tuple[
                ValidOnlyEmpiricalStateAssignment,
                preflight.ValidOnlyMappingCandidate,
            ]
        ],
    ] = defaultdict(list)
    for assignment in remap.remapped_assignments:
        candidate = candidates[assignment.trajectory_id]
        rows_by_task[candidate.task_package_id].append((assignment, candidate))

    summaries: list[execution.TaskObservedStateSummary] = []
    for package in reachability_inputs.task_catalog.packages:
        rows = rows_by_task.get(package.task_package_id, [])
        states = tuple(sorted({assignment.structural_state_id for assignment, _ in rows}))
        values = {
            "task_package_id": package.task_package_id,
            "source_task_artifact_id": package.source_task_artifact_id,
            "mechanism_id": package.mechanism_id,
            "tier": package.tier,
            "qualified_candidate_count": len(rows),
            "assignment_count": len(rows),
            "unique_structural_state_count": len(states),
            "unconditional_assignment_count": sum(
                candidate.sampling_mode == "reachability_unconditional" for _, candidate in rows
            ),
            "conditioned_assignment_count": sum(
                candidate.sampling_mode == "reachability_conditioned" for _, candidate in rows
            ),
            "structural_state_ids": states,
            "multiple_observed_qualified_states": len(states) >= 2,
        }
        provisional = execution.TaskObservedStateSummary.model_construct(
            summary_id="pending",
            **values,
        )
        summaries.append(
            execution.TaskObservedStateSummary(
                summary_id=_identity(
                    provisional,
                    "summary_id",
                    "finance_v26_task_observed_state_summary:",
                ),
                **values,
            )
        )
    ordered = tuple(sorted(summaries, key=lambda item: item.summary_id))
    if _canonical_bytes(ordered) != _canonical_bytes(formal_support.task_summaries):
        raise ValueError("v26.158 independent Task State summaries changed")
    unique_states = {item.structural_state_id for item in remap.remapped_assignments}
    values = {
        "assignment_count": remap.exact_raw_remapped_assignment_count,
        "unique_structural_state_count": len(unique_states),
        "tasks_with_qualified_assignments": sum(item.assignment_count > 0 for item in ordered),
        "tasks_with_multiple_observed_qualified_states": sum(
            item.multiple_observed_qualified_states for item in ordered
        ),
        "task_summaries": ordered,
    }
    provisional = IndependentObservedStateAudit.model_construct(
        audit_id="pending",
        **values,
    )
    return IndependentObservedStateAudit(
        audit_id=_identity(
            provisional,
            "audit_id",
            "finance_v26_valid_only_independent_observed_state:",
        ),
        **values,
    )


def _outcome(state: IndependentObservedStateAudit) -> OutcomeInterpretation:
    multiple = state.tasks_with_multiple_observed_qualified_states > 0
    values = {
        "assignment_count": state.assignment_count,
        "unique_structural_state_count": state.unique_structural_state_count,
        "tasks_with_multiple_observed_qualified_states": (
            state.tasks_with_multiple_observed_qualified_states
        ),
        "at_least_one_task_has_multiple_qualified_states": multiple,
        "empirical_multiple_state_existence_supported": multiple,
    }
    provisional = OutcomeInterpretation.model_construct(
        interpretation_id="pending",
        **values,
    )
    return OutcomeInterpretation(
        interpretation_id=_identity(
            provisional,
            "interpretation_id",
            "finance_v26_valid_only_mapping_outcome_interpretation:",
        ),
        **values,
    )


def _expect_failure(name: str, payload: dict[str, Any]) -> MutationResult:
    try:
        ValidOnlyEmpiricalStateAssignment.model_validate(payload)
    except (TypeError, ValueError):
        return MutationResult(mutation_name=name)
    raise AssertionError(f"v26.158 destructive mutation survived: {name}")


def _destructive(remap: IndependentRawRemappingAudit) -> DestructiveAudit:
    first = remap.remapped_assignments[0]
    fields: tuple[tuple[str, Any], ...] = (
        ("assignment_id", "stale-assignment"),
        ("mapping_result_id", "crossed-mapping-result"),
        ("mapper_contract_id", "crossed-mapper-contract"),
        ("trajectory_id", "crossed-trajectory"),
        ("trajectory_content_hash", "crossed-trajectory-hash"),
        ("qualified_validity_report_id", "crossed-validity-report"),
        ("omega_task_context_id", "crossed-omega"),
        ("structural_state_id", "crossed-state"),
        ("route_condition_id", "crossed-route"),
        ("static_path_catalog_id", "crossed-path-catalog"),
        ("raw_observation_prefix_hash", "crossed-observation-prefix"),
        ("qualified_validity", False),
        ("valid_only_gate_crossed", False),
        ("static_path_used_as_empirical_state", True),
        (
            "structural_state",
            first.structural_state.model_copy(update={"state_id": "crossed-state-object"}),
        ),
        (
            "route_projection",
            first.route_projection.model_copy(update={"projection_id": "crossed-route-object"}),
        ),
    )
    mutations = []
    for field, value in fields:
        payload = first.model_dump(mode="python")
        payload[field] = value
        mutations.append(_expect_failure(f"assignment_{field}_mutation", payload))
    ordered = tuple(sorted(mutations, key=lambda item: item.mutation_name))
    values = {"mutation_results": ordered}
    provisional = DestructiveAudit.model_construct(audit_id="pending", **values)
    return DestructiveAudit(
        audit_id=_identity(
            provisional,
            "audit_id",
            "finance_v26_valid_only_mapping_postrun_destructive:",
        ),
        **values,
    )


def _decision(
    *,
    remap: IndependentRawRemappingAudit,
    binding: IndependentAssignmentBindingAudit,
    state: IndependentObservedStateAudit,
    outcome: OutcomeInterpretation,
) -> FinalDecisionContract:
    values = {
        "independent_raw_remapping_audit_id": remap.audit_id,
        "independent_assignment_binding_audit_id": binding.audit_id,
        "independent_observed_state_audit_id": state.audit_id,
        "outcome_interpretation_id": outcome.interpretation_id,
    }
    provisional = FinalDecisionContract.model_construct(
        contract_id="pending",
        **values,
    )
    return FinalDecisionContract(
        contract_id=_identity(
            provisional,
            "contract_id",
            "finance_v26_valid_only_mapping_final_decision:",
        ),
        **values,
    )


def _detail(path: Path, root: Path) -> DetailFile:
    return DetailFile(
        relative_path=path.relative_to(root).as_posix(),
        sha256=_sha256(path),
        byte_count=path.stat().st_size,
    )


def build_postrun_audit(
    *,
    package_root: Path,
    implementation_root: Path,
    reachability_execution_dir: Path,
    reachability_postrun_dir: Path,
    mapping_preflight_dir: Path,
    mapping_execution_dir: Path,
    output_dir: Path,
) -> ValidOnlyMappingPostrunAuditReport:
    source = _execution_replay(
        package_root=package_root,
        implementation_root=implementation_root,
        reachability_execution_dir=reachability_execution_dir,
        postrun_dir=reachability_postrun_dir,
        mapping_preflight_dir=mapping_preflight_dir,
        execution_dir=mapping_execution_dir,
    )
    print(
        f"[v26.158] execution replay {source.execution_byte_match_count}/8 exact",
        flush=True,
    )
    formal_report = execution.ValidOnlyMappingExecutionReport.model_validate(
        _load(mapping_execution_dir / "report.json")
    )
    formal_transition = execution.ProspectiveTransitionContract.model_validate(
        _load(mapping_execution_dir / "prospective_transition_contract.json")
    )
    formal_assignments = execution.StateAssignmentCatalog.model_validate(
        _load(mapping_execution_dir / "assignment_catalog.json")
    )
    formal_support = execution.ObservedStateSupportAudit.model_validate(
        _load(mapping_execution_dir / "observed_state_support_audit.json")
    )
    if (
        formal_report.report_id != EXPECTED_EXECUTION_REPORT_ID
        or formal_transition.contract_id != EXPECTED_EXECUTION_TRANSITION_ID
        or not formal_transition.independent_raw_remapping_audit_authorized
        or formal_transition.provider_calls_authorized
    ):
        raise ValueError("v26.158 execution audit authorization changed")

    mapping_inputs = execution._load_inputs(mapping_preflight_dir)
    reachability_inputs = preflight._load_inputs(
        package_root=package_root,
        postrun_dir=reachability_postrun_dir,
        execution_dir=reachability_execution_dir,
    )
    remap = _independent_raw_remap(
        formal_assignments=formal_assignments,
        mapping_inputs=mapping_inputs,
        reachability_inputs=reachability_inputs,
    )
    binding = _binding_audit(remap)
    state = _independent_observed_state(
        remap=remap,
        mapping_inputs=mapping_inputs,
        reachability_inputs=reachability_inputs,
        formal_support=formal_support,
    )
    outcome = _outcome(state)
    destructive = _destructive(remap)
    decision = _decision(
        remap=remap,
        binding=binding,
        state=state,
        outcome=outcome,
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    outputs: tuple[tuple[str, BaseModel], ...] = (
        ("destructive_audit.json", destructive),
        ("execution_replay_audit.json", source),
        ("final_decision_contract.json", decision),
        ("independent_assignment_binding_audit.json", binding),
        ("independent_observed_state_audit.json", state),
        ("independent_raw_remapping_audit.json", remap),
        ("outcome_interpretation.json", outcome),
    )
    for name, value in outputs:
        _write_json_atomic(output_dir / name, value)
    details = tuple(_detail(output_dir / name, output_dir) for name, _ in outputs)
    values = {
        "execution_replay_audit_id": source.audit_id,
        "independent_raw_remapping_audit_id": remap.audit_id,
        "independent_assignment_binding_audit_id": binding.audit_id,
        "independent_observed_state_audit_id": state.audit_id,
        "outcome_interpretation_id": outcome.interpretation_id,
        "destructive_audit_id": destructive.audit_id,
        "final_decision_contract_id": decision.contract_id,
        "assignment_count": state.assignment_count,
        "unique_structural_state_count": state.unique_structural_state_count,
        "tasks_with_multiple_observed_qualified_states": (
            state.tasks_with_multiple_observed_qualified_states
        ),
        "detail_files": details,
    }
    provisional = ValidOnlyMappingPostrunAuditReport.model_construct(
        report_id="pending",
        **values,
    )
    report = ValidOnlyMappingPostrunAuditReport(
        report_id=_identity(
            provisional,
            "report_id",
            "finance_v26_valid_only_mapping_postrun_audit_report:",
        ),
        **values,
    )
    _write_json_atomic(output_dir / "report.json", report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Audit valid-only State Mapping by independent Raw remapping."
    )
    parser.add_argument("--implementation-root", type=Path, default=Path.cwd())
    parser.add_argument("--package-root", type=Path)
    parser.add_argument("--reachability-execution-dir", type=Path)
    parser.add_argument("--reachability-postrun-dir", type=Path)
    parser.add_argument("--mapping-preflight-dir", type=Path)
    parser.add_argument("--mapping-execution-dir", type=Path)
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
    reachability_postrun_dir = (
        args.reachability_postrun_dir
        if args.reachability_postrun_dir is not None
        else package_root / reachability_postrun.OUTPUT_DIR
    )
    mapping_preflight_dir = (
        args.mapping_preflight_dir
        if args.mapping_preflight_dir is not None
        else package_root / preflight.OUTPUT_DIR
    )
    mapping_execution_dir = (
        args.mapping_execution_dir
        if args.mapping_execution_dir is not None
        else package_root / execution.OUTPUT_DIR
    )
    output_dir = args.output_dir if args.output_dir is not None else package_root / OUTPUT_DIR
    report = build_postrun_audit(
        package_root=package_root,
        implementation_root=args.implementation_root,
        reachability_execution_dir=reachability_execution_dir,
        reachability_postrun_dir=reachability_postrun_dir,
        mapping_preflight_dir=mapping_preflight_dir,
        mapping_execution_dir=mapping_execution_dir,
        output_dir=output_dir,
    )
    print(
        "[v26.158] independent Raw remapping passed "
        f"assignments={report.assignment_count} "
        f"states={report.unique_structural_state_count} "
        f"multi_state_tasks={report.tasks_with_multiple_observed_qualified_states} "
        f"provider_calls={report.provider_calls} "
        f"report={report.report_id}",
        flush=True,
    )


if __name__ == "__main__":
    main()
