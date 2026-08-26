from __future__ import annotations

import argparse
import hashlib
import itertools
import json
from collections import defaultdict
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final, cast

from pydantic import BaseModel

from trusted_synthesis.canonical_json import strict_canonical_hash, to_canonical_json_data
from trusted_synthesis.core.evaluation.measurement_outcome_v2 import (
    MeasurementOutcomeProjectionV2,
    MeasurementSupportStatusV2,
    MeasurementTerminalClassV2,
    make_measurement_outcome_projection_v2,
)
from trusted_synthesis.core.evaluation.valid_only_state_mapping_v2 import (
    ValidOnlyStateMapperContractV2,
    make_qualified_verifier_input_binding_v2,
    make_valid_only_state_mapper_contract_v2,
)
from trusted_synthesis.core.trajectory.empirical_state_mapping_v2 import (
    EmpiricalStateSemanticPolicyV2,
    EmpiricalStructuralStateV2,
    ExperimentalConditionV2,
    PublicTrajectoryActionV2,
    PublicTrajectoryProjectionV2,
    ValidOnlyEmpiricalStateAssignmentV2,
    extract_typed_action_references_v2,
    make_empirical_route_signature_v2,
    make_empirical_state_semantic_policy_v2,
    make_experimental_condition_v2,
    make_public_trajectory_action_v2,
    make_public_trajectory_projection_v2,
    make_state_contrast_v2,
    map_independently_valid_public_trajectory_to_state_v2,
)
from trusted_synthesis.core.trajectory.reference_empirical_state_mapping_v2 import (
    IndependentReferenceMappingV2,
    reference_map_public_trajectory_v2,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_valid_only_reachability_state_mapping_execution as mapping_execution,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_valid_only_reachability_state_mapping_postrun_audit as mapping_postrun,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_valid_only_reachability_state_mapping_preflight as mapping_preflight,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_mapper_v2_gold_fixtures import (
    MapperV2GoldFixtureAudit,
    build_mapper_v2_gold_fixture_audit,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_state_semantics_audit_models import (
    BuildProducts,
    ConditionRouteDecompositionAudit,
    ConditionRouteRow,
    DetailFile,
    FixedConditionStateSupportAudit,
    HistoricalMapperV1FreezeAudit,
    IndependentReferenceMapperAudit,
    MapperV2DiagnosticCatalog,
    MapperV2DiagnosticRow,
    MapperV2StateCatalog,
    MeasurementClassificationDecompositionAudit,
    MutationResult,
    ResultSemanticsDiagnostic,
    ResultSemanticsRow,
    StateContrastCatalog,
    StateSemanticsAuditReport,
    StateSemanticsDestructiveAudit,
    StateSemanticsTransitionContract,
    TaskConditionSupportRow,
    TaskSupportSummary,
    identity,
)
from trusted_synthesis.hashing import canonical_hash

RUN_ID: Final = "finance_v26_159_valid_only_state_semantics_audit_v1_20260826"
OUTPUT_DIR: Final = (
    "artifacts/vtdo_experiment/finance_v26_159_valid_only_state_semantics_audit_v1_20260826"
)
IMPLEMENTATION_PATH: Final = (
    "src/trusted_synthesis/experiments/vtdo_experiment/"
    "phase1_v26_valid_only_state_semantics_audit.py"
)
MAPPER_V2_PATH: Final = "src/trusted_synthesis/core/trajectory/empirical_state_mapping_v2.py"
REFERENCE_MAPPER_V2_PATH: Final = (
    "src/trusted_synthesis/core/trajectory/reference_empirical_state_mapping_v2.py"
)
DEFAULT_REACHABILITY_EXECUTION_DIR: Final = (
    "artifacts/vtdo_experiment/finance_v26_154_fresh_reachability_execution_v1_20260826"
)
DEFAULT_REACHABILITY_POSTRUN_DIR: Final = (
    "artifacts/vtdo_experiment/finance_v26_155_fresh_reachability_postrun_audit_v1_20260826"
)
DEFAULT_MAPPING_PREFLIGHT_DIR: Final = (
    "artifacts/vtdo_experiment/finance_v26_156_valid_only_state_mapping_preflight_v1_20260826"
)
DEFAULT_MAPPING_EXECUTION_DIR: Final = (
    "artifacts/vtdo_experiment/finance_v26_157_valid_only_state_mapping_execution_v1_20260826"
)
DEFAULT_MAPPING_POSTRUN_DIR: Final = (
    "artifacts/vtdo_experiment/finance_v26_158_valid_only_state_mapping_postrun_audit_v1_20260826"
)
DEFAULT_VERIFIER_FREEZE_DIR: Final = (
    "artifacts/vtdo_experiment/finance_v26_148_verifier_vnext_contract_freeze_v1_20260825"
)


@dataclass(frozen=True)
class AuditInputs:
    reachability: mapping_preflight.Inputs
    candidate_manifest: mapping_preflight.ValidOnlyMappingCandidateManifest
    omega_catalog: mapping_preflight.OmegaTaskContextCatalog
    mapping_report: mapping_execution.ValidOnlyMappingExecutionReport
    assignment_catalog: mapping_execution.StateAssignmentCatalog
    state_catalog: mapping_execution.StructuralStateCatalog
    route_catalog: mapping_execution.RouteProjectionCatalog
    mapping_postrun_report: mapping_postrun.ValidOnlyMappingPostrunAuditReport
    answer_semantics_contract_id: str


@dataclass(frozen=True)
class MappingRecord:
    candidate: mapping_preflight.ValidOnlyMappingCandidate
    v1_assignment: Any
    v2_assignment: ValidOnlyEmpiricalStateAssignmentV2
    reference_mapping: IndependentReferenceMappingV2
    task_package_id: str
    result: Any


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _canonical_bytes(value: Any) -> bytes:
    return (
        json.dumps(
            to_canonical_json_data(value),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
        + b"\n"
    )


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
    raise ValueError("v26.159 cannot resolve package root")


def _model(
    model_type: type[BaseModel],
    values: dict[str, Any],
    *,
    identity_field: str,
    prefix: str,
) -> Any:
    provisional = model_type.model_construct(**{identity_field: "pending", **values})
    return model_type(**{identity_field: identity(provisional, identity_field, prefix), **values})


def _load_inputs(
    *,
    package_root: Path,
    reachability_execution_dir: Path,
    reachability_postrun_dir: Path,
    mapping_preflight_dir: Path,
    mapping_execution_dir: Path,
    mapping_postrun_dir: Path,
    verifier_freeze_dir: Path,
) -> AuditInputs:
    reachability = mapping_preflight._load_inputs(  # noqa: SLF001
        package_root=package_root,
        postrun_dir=reachability_postrun_dir,
        execution_dir=reachability_execution_dir,
    )
    candidate_manifest = mapping_preflight.ValidOnlyMappingCandidateManifest.model_validate(
        _load(mapping_preflight_dir / "candidate_manifest.json")
    )
    omega_catalog = mapping_preflight.OmegaTaskContextCatalog.model_validate(
        _load(mapping_preflight_dir / "omega_task_context_catalog.json")
    )
    mapping_report = mapping_execution.ValidOnlyMappingExecutionReport.model_validate(
        _load(mapping_execution_dir / "report.json")
    )
    assignment_catalog = mapping_execution.StateAssignmentCatalog.model_validate(
        _load(mapping_execution_dir / "assignment_catalog.json")
    )
    state_catalog = mapping_execution.StructuralStateCatalog.model_validate(
        _load(mapping_execution_dir / "structural_state_catalog.json")
    )
    route_catalog = mapping_execution.RouteProjectionCatalog.model_validate(
        _load(mapping_execution_dir / "route_projection_catalog.json")
    )
    postrun_report = mapping_postrun.ValidOnlyMappingPostrunAuditReport.model_validate(
        _load(mapping_postrun_dir / "report.json")
    )
    answer_contract = _load(verifier_freeze_dir / "answer_semantics_contract.json")
    if (
        candidate_manifest.qualified_candidate_count != 100
        or assignment_catalog.assignment_count != 100
        or state_catalog.unique_structural_state_count != 41
        or route_catalog.unique_route_projection_count != 44
        or mapping_report.assignment_count != 100
        or postrun_report.assignment_count != 100
        or not isinstance(answer_contract.get("contract_id"), str)
    ):
        raise ValueError("v26.159 historical Mapper input denominator changed")
    return AuditInputs(
        reachability=reachability,
        candidate_manifest=candidate_manifest,
        omega_catalog=omega_catalog,
        mapping_report=mapping_report,
        assignment_catalog=assignment_catalog,
        state_catalog=state_catalog,
        route_catalog=route_catalog,
        mapping_postrun_report=postrun_report,
        answer_semantics_contract_id=answer_contract["contract_id"],
    )


def _semantic_policy(inputs: AuditInputs) -> EmpiricalStateSemanticPolicyV2:
    reference_policy_id = strict_canonical_hash(
        {
            "runtime_operation_reference_projection": (
                "authority_verifier.match_empirical_program.runtime_to_node"
            ),
            "answer_reference_projection_fields": ("higher_ref", "selected_ref"),
            "projection_source": "qualified_verifier_comparison.observed_canonical_result",
            "host_semantic_repair": False,
        },
        prefix="finance_v26_reference_projection_policy_v2:",
    )
    decimal_policy_id = strict_canonical_hash(
        {
            "answer_semantics_contract_id": inputs.answer_semantics_contract_id,
            "rule": "Decimal(str(value)).normalize()",
            "floating_tolerance_allowed": False,
        },
        prefix="finance_v26_decimal_canonicalization_policy_v2:",
    )
    return make_empirical_state_semantic_policy_v2(
        answer_semantics_contract_id=inputs.answer_semantics_contract_id,
        reference_projection_policy_id=reference_policy_id,
        decimal_canonicalization_policy_id=decimal_policy_id,
    )


def _mapper_contract(
    *,
    inputs: AuditInputs,
    semantic_policy: EmpiricalStateSemanticPolicyV2,
    package_root: Path,
) -> ValidOnlyStateMapperContractV2:
    verifier_ids = {
        item.verifier_vnext_contract_id for item in inputs.reachability.task_catalog.packages
    }
    if len(verifier_ids) != 1:
        raise ValueError("v26.159 crossed Qualified Verifier Contracts")
    implementation_id = strict_canonical_hash(
        {
            "relative_path": MAPPER_V2_PATH,
            "sha256": _sha256(package_root / MAPPER_V2_PATH),
        },
        prefix="finance_v26_empirical_state_mapper_v2_implementation:",
    )
    return make_valid_only_state_mapper_contract_v2(
        qualified_verifier_contract_id=next(iter(verifier_ids)),
        mapper_implementation_id=implementation_id,
        semantic_policy_id=semantic_policy.policy_id,
    )


def _trajectory_projection_v2(
    *,
    raw: Any,
    result: Any,
    semantic_policy: EmpiricalStateSemanticPolicyV2,
) -> PublicTrajectoryProjectionV2:
    comparison = result.answer_comparison
    if comparison is None or comparison.observed_canonical_result is None:
        raise ValueError(f"v26.159 Qualified trajectory lacks Canonical Result: {result.job_id}")
    observations = {item.call.call_index: item for item in raw.observations}
    actions: list[PublicTrajectoryActionV2] = []
    for action_index, record in enumerate(raw.commits):
        commit = record.commit
        call = commit.call
        observation = observations.get(call.call_index) if call is not None else None
        actions.append(
            make_public_trajectory_action_v2(
                action_index=action_index,
                decision_kind=commit.decision_kind,
                action_kind=commit.action,
                tool_id=call.tool_id if call is not None else None,
                arguments=dict(call.arguments) if call is not None else None,
                observation_status=observation.status if observation is not None else None,
                error_code=observation.error_code if observation is not None else None,
                observation_result=(dict(observation.result) if observation is not None else None),
                evidence_ids=(observation.evidence_ids if observation is not None else ()),
                provenance_hashes=(
                    observation.provenance_hashes if observation is not None else ()
                ),
                reference_policy=semantic_policy.typed_reference_policy,
            )
        )
    completed = raw.completed_result
    if completed is None:
        raise ValueError(f"v26.159 Qualified trajectory lacks Final payload: {result.job_id}")
    raw_final_result = dict(completed.final_payload.answer.result)
    citations = tuple(
        sorted({item.evidence_id for item in completed.final_payload.answer.citations})
    )
    return make_public_trajectory_projection_v2(
        trajectory_id=raw.artifact_id,
        terminal_disposition=raw.terminal_disposition,
        actions=actions,
        semantic_rejections=tuple(item.model_dump(mode="json") for item in raw.semantic_rejections),
        raw_final_result=raw_final_result,
        canonical_result=comparison.observed_canonical_result,
        answer_semantic_schema_id=comparison.schema_id,
        reference_projection_policy_id=semantic_policy.reference_projection_policy_id,
        final_citations=citations,
    )


def _map_records(
    *,
    inputs: AuditInputs,
    semantic_policy: EmpiricalStateSemanticPolicyV2,
    mapper_contract: ValidOnlyStateMapperContractV2,
) -> tuple[MappingRecord, ...]:
    candidates = {item.job_id: item for item in inputs.candidate_manifest.candidates}
    results = {item.job_id: item for item in inputs.reachability.projection.recomputed_results}
    contexts = {item.task_package_id: item for item in inputs.omega_catalog.contexts}
    v1_by_trajectory = {item.trajectory_id: item for item in inputs.assignment_catalog.assignments}
    records: list[MappingRecord] = []
    for job_id in sorted(candidates):
        candidate = candidates[job_id]
        result = results[job_id]
        raw = inputs.reachability.raws[job_id]
        job = inputs.reachability.jobs[job_id]
        package = inputs.reachability.packages[job.task_package_id]
        context = contexts[job.task_package_id]
        aliases = mapping_preflight._runtime_aliases(package, raw)  # noqa: SLF001
        trajectory = _trajectory_projection_v2(
            raw=raw,
            result=result,
            semantic_policy=semantic_policy,
        )
        if candidate.trajectory_id != trajectory.trajectory_id:
            raise ValueError(f"v26.159 Candidate crossed Raw trajectory: {job_id}")
        condition = make_experimental_condition_v2(
            sampling_mode=job.sampling_mode,
            public_condition_id=job.public_condition_id,
            requested_path_id=job.requested_path_id,
            requested_path_strategy=job.requested_path_strategy,
            static_path_catalog_id=inputs.reachability.path_catalog.catalog_id,
        )
        route = make_empirical_route_signature_v2(trajectory)
        qualified_report = result.joint_result.qualified_report
        answer_comparison = result.answer_comparison
        if answer_comparison is None:
            raise ValueError(f"v26.159 Qualified row lacks Answer comparison: {job_id}")
        verifier_input_hash = strict_canonical_hash(
            {
                "qualified_validity_report_id": qualified_report.report_id,
                "answer_comparison_id": answer_comparison.comparison_id,
                "answer_semantic_schema_id": trajectory.answer_semantic_schema_id,
                "canonical_result_semantics_hash": (trajectory.canonical_result_semantics_hash),
                "trajectory_bound_artifact_hash": trajectory.trajectory_bound_artifact_hash,
                "raw_execution_sha256": candidate.raw_execution_sha256,
                "runtime_operation_alias_binding_hash": (
                    candidate.runtime_operation_alias_binding_hash
                ),
            },
            prefix="finance_v26_qualified_verifier_input_v2:",
        )
        binding = make_qualified_verifier_input_binding_v2(
            trajectory=trajectory,
            qualified_validity_report=qualified_report,
            raw_execution_artifact_hash=candidate.raw_execution_sha256,
            qualified_verifier_input_hash=verifier_input_hash,
        )
        assignment = map_independently_valid_public_trajectory_to_state_v2(
            trajectory=trajectory,
            qualified_validity_report=qualified_report,
            verifier_input_binding=binding,
            mapper_contract=mapper_contract,
            omega_task_context_id=context.context_id,
            experimental_condition=condition,
            empirical_route_signature=route,
            runtime_operation_aliases=aliases,
            semantic_policy=semantic_policy,
            raw_execution_artifact_hash=candidate.raw_execution_sha256,
        )
        reference = reference_map_public_trajectory_v2(
            trajectory=trajectory,
            omega_task_context_id=context.context_id,
            runtime_operation_aliases=aliases,
            semantic_policy=semantic_policy,
        )
        if reference.structural_state != assignment.structural_state:
            raise ValueError(f"v26.159 independent Reference Mapper mismatch: {job_id}")
        records.append(
            MappingRecord(
                candidate=candidate,
                v1_assignment=v1_by_trajectory[trajectory.trajectory_id],
                v2_assignment=assignment,
                reference_mapping=reference,
                task_package_id=job.task_package_id,
                result=result,
            )
        )
    if len(records) != 100:
        raise ValueError("v26.159 Mapper v2 diagnostic denominator changed")
    return tuple(records)


def _historical_freeze(
    *,
    inputs: AuditInputs,
    mapping_execution_dir: Path,
    mapping_postrun_dir: Path,
) -> HistoricalMapperV1FreezeAudit:
    values = {
        "v26_157_report_id": inputs.mapping_report.report_id,
        "v26_157_report_sha256": _sha256(mapping_execution_dir / "report.json"),
        "v26_158_report_id": inputs.mapping_postrun_report.report_id,
        "v26_158_report_sha256": _sha256(mapping_postrun_dir / "report.json"),
    }
    return _model(
        HistoricalMapperV1FreezeAudit,
        values,
        identity_field="audit_id",
        prefix="finance_v26_historical_mapper_v1_freeze:",
    )


def _result_semantics(
    records: Sequence[MappingRecord],
) -> tuple[ResultSemanticsDiagnostic, dict[str, str]]:
    provisional_rows: list[tuple[MappingRecord, str, str, str]] = []
    groups: dict[str, set[str]] = defaultdict(set)
    for record in records:
        v1_state = record.v1_assignment.structural_state
        canonical_result = record.v2_assignment.structural_state.canonical_result
        canonical_hash_v1 = canonical_hash(
            canonical_result,
            prefix="empirical_result_semantics:",
        )
        state_payload = v1_state.model_dump(mode="json", exclude={"state_id"})
        state_payload["result_semantics_hash"] = canonical_hash_v1
        equivalence_id = strict_canonical_hash(
            state_payload,
            prefix="finance_v26_result_only_equivalence:",
        )
        groups[equivalence_id].add(v1_state.state_id)
        provisional_rows.append(
            (record, v1_state.result_semantics_hash, canonical_hash_v1, equivalence_id)
        )
    merge_groups = {key for key, state_ids in groups.items() if len(state_ids) > 1}
    merged_v1_states = (
        set().union(*(groups[key] for key in merge_groups)) if merge_groups else set()
    )
    rows = tuple(
        ResultSemanticsRow(
            job_id=record.candidate.job_id,
            trajectory_id=record.v1_assignment.trajectory_id,
            mapper_v1_state_id=record.v1_assignment.structural_state_id,
            raw_result_semantics_hash_v1=raw_hash,
            verifier_canonical_result_semantics_hash_v1=canonical_hash_v1,
            representation_differs=raw_hash != canonical_hash_v1,
            result_only_equivalence_id=equivalence_id,
        )
        for record, raw_hash, canonical_hash_v1, equivalence_id in sorted(
            provisional_rows,
            key=lambda row: row[0].candidate.job_id,
        )
    )
    values = {
        "raw_vs_verifier_canonical_result_difference_count": sum(
            item.representation_differs for item in rows
        ),
        "mapper_v1_states_in_result_only_merge_groups": len(merged_v1_states),
        "assignments_in_result_only_merge_groups": sum(
            item.result_only_equivalence_id in merge_groups for item in rows
        ),
        "minimal_result_only_equivalence_class_count": len(groups),
        "rows": rows,
    }
    audit = _model(
        ResultSemanticsDiagnostic,
        values,
        identity_field="audit_id",
        prefix="finance_v26_result_semantics_diagnostic:",
    )
    return audit, {item.job_id: item.result_only_equivalence_id for item in rows}


def _condition_route(
    records: Sequence[MappingRecord],
) -> ConditionRouteDecompositionAudit:
    rows = tuple(
        ConditionRouteRow(
            job_id=record.candidate.job_id,
            task_package_id=record.task_package_id,
            sampling_mode=record.v2_assignment.experimental_condition.sampling_mode,
            public_condition_id=record.v2_assignment.experimental_condition.public_condition_id,
            requested_path_id=record.v2_assignment.experimental_condition.requested_path_id,
            requested_path_strategy=(
                record.v2_assignment.experimental_condition.requested_path_strategy
            ),
            static_path_catalog_id=(
                record.v2_assignment.experimental_condition.static_path_catalog_id
            ),
            mapper_v1_route_projection_id=record.v1_assignment.route_condition_id,
            experimental_condition_id=record.v2_assignment.experimental_condition_id,
            empirical_route_signature_id=record.v2_assignment.empirical_route_signature_id,
        )
        for record in sorted(records, key=lambda item: item.candidate.job_id)
    )
    cells: dict[tuple[str, str], list[ConditionRouteRow]] = defaultdict(list)
    for row in rows:
        cells[(row.task_package_id, row.experimental_condition_id)].append(row)
    unconditional = {
        key: values
        for key, values in cells.items()
        if values[0].sampling_mode == "reachability_unconditional"
    }
    values = {
        "experimental_condition_id_count": len({item.experimental_condition_id for item in rows}),
        "task_pre_treatment_condition_cell_count": len(cells),
        "fixed_condition_cells_split_by_mapper_v1_route_count": sum(
            len({item.mapper_v1_route_projection_id for item in cell}) > 1
            for cell in cells.values()
        ),
        "unconditional_task_condition_cell_count": len(unconditional),
        "unconditional_cells_split_by_mapper_v1_route_count": sum(
            len({item.mapper_v1_route_projection_id for item in cell}) > 1
            for cell in unconditional.values()
        ),
        "empirical_route_signature_count": len(
            {item.empirical_route_signature_id for item in rows}
        ),
        "rows": rows,
    }
    return _model(
        ConditionRouteDecompositionAudit,
        values,
        identity_field="audit_id",
        prefix="finance_v26_condition_route_decomposition:",
    )


def _fixed_condition_support(
    records: Sequence[MappingRecord],
    result_only_ids: Mapping[str, str],
) -> FixedConditionStateSupportAudit:
    grouped: dict[tuple[str, str], list[MappingRecord]] = defaultdict(list)
    for record in records:
        grouped[(record.task_package_id, record.v2_assignment.experimental_condition_id)].append(
            record
        )
    condition_rows = tuple(
        TaskConditionSupportRow(
            task_package_id=task_id,
            experimental_condition_id=condition_id,
            sampling_mode=cell[0].v2_assignment.experimental_condition.sampling_mode,
            qualified_rollout_count=len(cell),
            mapper_v1_state_ids=tuple(
                sorted({item.v1_assignment.structural_state_id for item in cell})
            ),
            result_only_equivalence_ids=tuple(
                sorted({result_only_ids[item.candidate.job_id] for item in cell})
            ),
            mapper_v2_diagnostic_state_ids=tuple(
                sorted({item.v2_assignment.structural_state_id for item in cell})
            ),
        )
        for (task_id, condition_id), cell in sorted(grouped.items())
    )
    by_task: dict[str, list[TaskConditionSupportRow]] = defaultdict(list)
    for row in condition_rows:
        by_task[row.task_package_id].append(row)
    summaries: list[TaskSupportSummary] = []
    for task_id, cells in sorted(by_task.items()):
        v1 = tuple(sorted({state for cell in cells for state in cell.mapper_v1_state_ids}))
        result_only = tuple(
            sorted({state for cell in cells for state in cell.result_only_equivalence_ids})
        )
        v2 = tuple(
            sorted({state for cell in cells for state in cell.mapper_v2_diagnostic_state_ids})
        )
        unconditional = [
            cell for cell in cells if cell.sampling_mode == "reachability_unconditional"
        ]
        summaries.append(
            TaskSupportSummary(
                task_package_id=task_id,
                pooled_mapper_v1_state_ids=v1,
                pooled_result_only_equivalence_ids=result_only,
                pooled_mapper_v2_diagnostic_state_ids=v2,
                mapper_v1_multiple_state_across_all_conditions=len(v1) > 1,
                mapper_v1_multiple_state_within_any_fixed_condition=any(
                    len(cell.mapper_v1_state_ids) > 1 for cell in cells
                ),
                mapper_v1_multiple_state_within_unconditional_condition=any(
                    len(cell.mapper_v1_state_ids) > 1 for cell in unconditional
                ),
                result_only_multiple_state_across_all_conditions=len(result_only) > 1,
                result_only_multiple_state_within_any_fixed_condition=any(
                    len(cell.result_only_equivalence_ids) > 1 for cell in cells
                ),
                result_only_multiple_state_within_unconditional_condition=any(
                    len(cell.result_only_equivalence_ids) > 1 for cell in unconditional
                ),
                mapper_v2_multiple_state_across_all_conditions=len(v2) > 1,
                mapper_v2_multiple_state_within_any_fixed_condition=any(
                    len(cell.mapper_v2_diagnostic_state_ids) > 1 for cell in cells
                ),
                mapper_v2_multiple_state_within_unconditional_condition=any(
                    len(cell.mapper_v2_diagnostic_state_ids) > 1 for cell in unconditional
                ),
            )
        )
    summary_tuple = tuple(summaries)
    values = {
        "qualified_task_count": len(summary_tuple),
        "condition_cell_count": len(condition_rows),
        "mapper_v1_pooled_multiple_state_task_count": sum(
            item.mapper_v1_multiple_state_across_all_conditions for item in summary_tuple
        ),
        "mapper_v1_any_fixed_condition_multiple_state_task_count": sum(
            item.mapper_v1_multiple_state_within_any_fixed_condition for item in summary_tuple
        ),
        "mapper_v1_unconditional_multiple_state_task_count": sum(
            item.mapper_v1_multiple_state_within_unconditional_condition for item in summary_tuple
        ),
        "result_only_pooled_multiple_state_task_count": sum(
            item.result_only_multiple_state_across_all_conditions for item in summary_tuple
        ),
        "result_only_any_fixed_condition_multiple_state_task_count": sum(
            item.result_only_multiple_state_within_any_fixed_condition for item in summary_tuple
        ),
        "result_only_unconditional_multiple_state_task_count": sum(
            item.result_only_multiple_state_within_unconditional_condition for item in summary_tuple
        ),
        "mapper_v2_pooled_multiple_state_task_count": sum(
            item.mapper_v2_multiple_state_across_all_conditions for item in summary_tuple
        ),
        "mapper_v2_any_fixed_condition_multiple_state_task_count": sum(
            item.mapper_v2_multiple_state_within_any_fixed_condition for item in summary_tuple
        ),
        "mapper_v2_unconditional_multiple_state_task_count": sum(
            item.mapper_v2_multiple_state_within_unconditional_condition for item in summary_tuple
        ),
        "condition_rows": condition_rows,
        "task_summaries": summary_tuple,
    }
    return _model(
        FixedConditionStateSupportAudit,
        values,
        identity_field="audit_id",
        prefix="finance_v26_fixed_condition_state_support:",
    )


def _diagnostic_catalog(
    *,
    records: Sequence[MappingRecord],
    result_semantics: ResultSemanticsDiagnostic,
    semantic_policy: EmpiricalStateSemanticPolicyV2,
    mapper_contract: ValidOnlyStateMapperContractV2,
) -> MapperV2DiagnosticCatalog:
    v1_to_v2: dict[str, set[str]] = defaultdict(set)
    v2_to_v1: dict[str, set[str]] = defaultdict(set)
    result_rows = {item.job_id: item for item in result_semantics.rows}
    for record in records:
        v1 = record.v1_assignment.structural_state_id
        v2 = record.v2_assignment.structural_state_id
        v1_to_v2[v1].add(v2)
        v2_to_v1[v2].add(v1)
    rows: list[MapperV2DiagnosticRow] = []
    for record in sorted(records, key=lambda item: item.candidate.job_id):
        v1 = record.v1_assignment.structural_state_id
        v2 = record.v2_assignment.structural_state_id
        reasons = ["experimental_condition_empirical_route_decoupled"]
        if result_rows[record.candidate.job_id].representation_differs:
            reasons.append("verifier_canonical_result_replaced_raw_representation")
        if len(v2_to_v1[v2]) > 1:
            reasons.append("mapper_v1_states_merged_under_v2")
        if len(v1_to_v2[v1]) > 1:
            reasons.append("mapper_v1_state_split_under_v2")
        if len(reasons) == 1:
            reasons.append("typed_reference_lineage_and_temporal_policy_applied")
        rows.append(
            MapperV2DiagnosticRow(
                job_id=record.candidate.job_id,
                task_package_id=record.task_package_id,
                trajectory_id=record.v2_assignment.trajectory_id,
                mapper_v1_assignment_id=record.v1_assignment.assignment_id,
                mapper_v1_state_id=v1,
                mapper_v2_diagnostic_assignment_id=record.v2_assignment.assignment_id,
                mapper_v2_diagnostic_state_id=v2,
                experimental_condition_id=record.v2_assignment.experimental_condition_id,
                empirical_route_signature_id=record.v2_assignment.empirical_route_signature_id,
                raw_final_payload_hash=record.v2_assignment.raw_final_payload_hash,
                canonical_result_semantics_hash=(
                    record.v2_assignment.canonical_result_semantics_hash
                ),
                transition_reason_ids=tuple(sorted(reasons)),
            )
        )
    values = {
        "semantic_policy_id": semantic_policy.policy_id,
        "mapper_contract_id": mapper_contract.contract_id,
        "mapper_v2_diagnostic_state_count": len(v2_to_v1),
        "v1_states_merged_by_v2_count": len(
            {v1 for state_ids in v2_to_v1.values() if len(state_ids) > 1 for v1 in state_ids}
        ),
        "v1_states_split_by_v2_count": sum(len(values) > 1 for values in v1_to_v2.values()),
        "rows": tuple(rows),
    }
    return _model(
        MapperV2DiagnosticCatalog,
        values,
        identity_field="catalog_id",
        prefix="finance_v26_mapper_v2_diagnostic_catalog:",
    )


def _state_and_contrast_catalogs(
    records: Sequence[MappingRecord],
    semantic_policy: EmpiricalStateSemanticPolicyV2,
) -> tuple[MapperV2StateCatalog, StateContrastCatalog]:
    by_id = {
        record.v2_assignment.structural_state_id: record.v2_assignment.structural_state
        for record in records
    }
    states = tuple(by_id[key] for key in sorted(by_id))
    state_catalog = _model(
        MapperV2StateCatalog,
        {
            "semantic_policy_id": semantic_policy.policy_id,
            "state_count": len(states),
            "states": states,
        },
        identity_field="catalog_id",
        prefix="finance_v26_mapper_v2_state_catalog:",
    )
    contrasts = tuple(
        sorted(
            (
                make_state_contrast_v2(left, right)
                for left, right in itertools.combinations(states, 2)
            ),
            key=lambda item: item.contrast_id,
        )
    )
    contrast_catalog = _model(
        StateContrastCatalog,
        {
            "state_catalog_id": state_catalog.catalog_id,
            "state_count": len(states),
            "expected_pair_count": len(states) * (len(states) - 1) // 2,
            "contrast_count": len(contrasts),
            "contrasts": contrasts,
        },
        identity_field="catalog_id",
        prefix="finance_v26_state_contrast_catalog:",
    )
    return state_catalog, contrast_catalog


def _reference_audit(
    records: Sequence[MappingRecord],
    package_root: Path,
    gold_fixture_audit: MapperV2GoldFixtureAudit,
) -> IndependentReferenceMapperAudit:
    matches = sum(
        record.reference_mapping.structural_state == record.v2_assignment.structural_state
        for record in records
    )
    if matches != 100:
        raise ValueError("v26.159 Reference Mapper mismatch")
    values = {
        "gold_fixture_audit_id": gold_fixture_audit.audit_id,
        "production_mapper_implementation_sha256": _sha256(package_root / MAPPER_V2_PATH),
        "reference_mapper_implementation_sha256": _sha256(package_root / REFERENCE_MAPPER_V2_PATH),
        "gold_merge_fixture_count": gold_fixture_audit.merge_fixture_count,
        "gold_split_fixture_count": gold_fixture_audit.split_fixture_count,
        "gold_pair_relation_pass_count": gold_fixture_audit.production_pass_count,
    }
    return _model(
        IndependentReferenceMapperAudit,
        values,
        identity_field="audit_id",
        prefix="finance_v26_independent_reference_mapper_audit:",
    )


def _terminal_class(raw: Any) -> MeasurementTerminalClassV2:
    mapping: dict[str, MeasurementTerminalClassV2] = {
        "completed_model_endpoint": "completed_model_endpoint",
        "model_result_failure": "model_result_failure",
        "typed_semantic_rejection": "model_typed_rejection",
        "measurement_support_exit": "measurement_support_exit",
        "instrument_failure": "instrument_failure",
        "privacy_rejection": "privacy_failure",
        "typed_budget_no_call": "typed_budget_no_call",
        "provider_transport_failure": "provider_transport_failure",
    }
    return mapping[raw.terminal_disposition]


def _measurement_classification(inputs: AuditInputs) -> MeasurementClassificationDecompositionAudit:
    results = {item.job_id: item for item in inputs.reachability.projection.recomputed_results}
    projections: list[MeasurementOutcomeProjectionV2] = []
    support_exit_count = 0
    old_overlap_count = 0
    raw_support_instrument_count = 0
    typed_rejection_count = 0
    typed_rejection_evaluable = 0
    for job_id, raw in sorted(inputs.reachability.raws.items()):
        result = results[job_id]
        support_exit = raw.terminal_disposition == "measurement_support_exit"
        typed_rejection = raw.terminal_disposition == "typed_semantic_rejection"
        support_exit_count += support_exit
        old_overlap_count += bool(support_exit and not result.instrument_integrity)
        raw_support_instrument_count += bool(support_exit and raw.instrument_integrity)
        typed_rejection_count += typed_rejection
        support_status: MeasurementSupportStatusV2
        if support_exit:
            support_status = "unavailable"
        else:
            support_status = cast(MeasurementSupportStatusV2, result.support_decision.status)
        provider_response = any(item.provider_call_made for item in raw.attempts)
        public_payload = any(
            item.response_payload_present
            and item.payload_projection_status == "validated_public_payload"
            for item in raw.attempts
        )
        model_terminal = raw.terminal_disposition in {
            "completed_model_endpoint",
            "model_result_failure",
            "typed_semantic_rejection",
        }
        projection = make_measurement_outcome_projection_v2(
            trajectory_id=raw.artifact_id,
            terminal_class=_terminal_class(raw),
            raw_instrument_integrity=raw.instrument_integrity,
            measurement_support_status=support_status,
            resource_accounting_integrity=raw.terminal_disposition != "instrument_failure",
            detour_allowance_status=raw.ordinary_detour_count <= 1,
            privacy_compliant=raw.privacy_compliant,
            provider_response_observed=provider_response,
            public_payload_observed=public_payload,
            model_action_observed=bool(raw.commits or raw.semantic_rejections),
            model_terminal_observed=model_terminal,
            completed_task_endpoint=raw.terminal_disposition == "completed_model_endpoint",
        )
        typed_rejection_evaluable += bool(typed_rejection and projection.validity_evaluable)
        projections.append(projection)
    ordered = tuple(sorted(projections, key=lambda item: item.projection_id))
    values = {
        "historical_support_exit_count": support_exit_count,
        "historical_support_exit_reprojected_as_instrument_failure_count": old_overlap_count,
        "raw_native_instrument_integrity_for_support_exit_count": raw_support_instrument_count,
        "historical_typed_semantic_rejection_count": typed_rejection_count,
        "v2_typed_rejection_validity_evaluable_count": typed_rejection_evaluable,
        "v2_projections": ordered,
    }
    return _model(
        MeasurementClassificationDecompositionAudit,
        values,
        identity_field="audit_id",
        prefix="finance_v26_measurement_classification_decomposition:",
    )


def _expect_failure(name: str, operation: Callable[[], Any]) -> MutationResult:
    try:
        operation()
    except Exception:
        return MutationResult(mutation_name=name)
    raise ValueError(f"v26.159 destructive mutation did not fail closed: {name}")


def _destructive(
    *,
    records: Sequence[MappingRecord],
    mapper_contract: ValidOnlyStateMapperContractV2,
    semantic_policy: EmpiricalStateSemanticPolicyV2,
) -> StateSemanticsDestructiveAudit:
    first = records[0]
    assignment = first.v2_assignment
    trajectory_payload = assignment.model_dump(mode="python")
    state_payload = assignment.structural_state.model_dump(mode="python")
    condition_payload = assignment.experimental_condition.model_dump(mode="python")
    route_payload = assignment.empirical_route_signature.model_dump(mode="python")
    contract_payload = mapper_contract.model_dump(mode="python")
    mutations = (
        _expect_failure(
            "assignment_canonical_result_hash_changed",
            lambda: ValidOnlyEmpiricalStateAssignmentV2.model_validate(
                {**trajectory_payload, "canonical_result_semantics_hash": "changed"}
            ),
        ),
        _expect_failure(
            "assignment_experimental_condition_parent_changed",
            lambda: ValidOnlyEmpiricalStateAssignmentV2.model_validate(
                {**trajectory_payload, "experimental_condition_id": "changed"}
            ),
        ),
        _expect_failure(
            "condition_post_treatment_field_inserted",
            lambda: ExperimentalConditionV2.model_validate(
                {**condition_payload, "empirical_tool_ids": []}
            ),
        ),
        _expect_failure(
            "route_event_changed_under_stale_identity",
            lambda: assignment.empirical_route_signature.__class__.model_validate(
                {
                    **route_payload,
                    "events": [
                        {**route_payload["events"][0], "decision_kind": "changed"},
                        *route_payload["events"][1:],
                    ],
                }
            ),
        ),
        _expect_failure(
            "state_canonical_result_changed_under_stale_hash",
            lambda: EmpiricalStructuralStateV2.model_validate(
                {**state_payload, "canonical_result": {"changed": True}}
            ),
        ),
        _expect_failure(
            "state_lineage_namespace_removed",
            lambda: EmpiricalStructuralStateV2.model_validate(
                {
                    **state_payload,
                    "typed_lineage": [{"lineage_kind": "untyped", "value": "value"}],
                }
            ),
        ),
        _expect_failure(
            "same_state_contrast_requested",
            lambda: make_state_contrast_v2(
                assignment.structural_state,
                assignment.structural_state,
            ),
        ),
        _expect_failure(
            "unknown_tool_reference_schema",
            lambda: extract_typed_action_references_v2(
                tool_id="unknown-tool",
                arguments={},
                observation_result={},
                policy=semantic_policy.typed_reference_policy,
            ),
        ),
        _expect_failure(
            "mapper_contract_required_binding_deleted",
            lambda: ValidOnlyStateMapperContractV2.model_validate(
                {
                    **contract_payload,
                    "required_assignment_bindings": contract_payload[
                        "required_assignment_bindings"
                    ][:-1],
                }
            ),
        ),
        _expect_failure(
            "measurement_support_instrument_overlap",
            lambda: make_measurement_outcome_projection_v2(
                trajectory_id="destructive-overlap",
                terminal_class="measurement_support_exit",
                raw_instrument_integrity=False,
                measurement_support_status="unavailable",
                resource_accounting_integrity=True,
                detour_allowance_status=False,
                privacy_compliant=True,
                provider_response_observed=True,
                public_payload_observed=True,
                model_action_observed=True,
                model_terminal_observed=False,
                completed_task_endpoint=False,
            ),
        ),
        _expect_failure(
            "state_raw_final_payload_field_inserted",
            lambda: EmpiricalStructuralStateV2.model_validate(
                {**state_payload, "raw_final_payload_hash": "forbidden"}
            ),
        ),
        _expect_failure(
            "diagnostic_assignment_frequency_authorized",
            lambda: ValidOnlyEmpiricalStateAssignmentV2.model_validate(
                {**trajectory_payload, "frequency_authorized": True}
            ),
        ),
    )
    ordered = tuple(sorted(mutations, key=lambda item: item.mutation_name))
    values = {
        "mutation_count": len(ordered),
        "failed_closed_count": len(ordered),
        "mutations": ordered,
    }
    return _model(
        StateSemanticsDestructiveAudit,
        values,
        identity_field="audit_id",
        prefix="finance_v26_state_semantics_destructive_audit:",
    )


def _transition() -> StateSemanticsTransitionContract:
    return _model(
        StateSemanticsTransitionContract,
        {},
        identity_field="contract_id",
        prefix="finance_v26_state_semantics_transition:",
    )


def _detail(path: Path, package_root: Path) -> DetailFile:
    try:
        relative_path = path.relative_to(package_root).as_posix()
    except ValueError:
        relative_path = (Path(OUTPUT_DIR) / path.name).as_posix()
    return DetailFile(
        relative_path=relative_path,
        sha256=_sha256(path),
        byte_count=path.stat().st_size,
    )


def build_state_semantics_audit(
    *,
    implementation_root: Path,
    output_dir: Path,
    reachability_execution_dir: Path | None = None,
    reachability_postrun_dir: Path | None = None,
    mapping_preflight_dir: Path | None = None,
    mapping_execution_dir: Path | None = None,
    mapping_postrun_dir: Path | None = None,
    verifier_freeze_dir: Path | None = None,
) -> BuildProducts:
    package_root = _resolve_package_root(implementation_root)
    reachability_execution_dir = reachability_execution_dir or (
        package_root / DEFAULT_REACHABILITY_EXECUTION_DIR
    )
    reachability_postrun_dir = reachability_postrun_dir or (
        package_root / DEFAULT_REACHABILITY_POSTRUN_DIR
    )
    mapping_preflight_dir = mapping_preflight_dir or (package_root / DEFAULT_MAPPING_PREFLIGHT_DIR)
    mapping_execution_dir = mapping_execution_dir or (package_root / DEFAULT_MAPPING_EXECUTION_DIR)
    mapping_postrun_dir = mapping_postrun_dir or (package_root / DEFAULT_MAPPING_POSTRUN_DIR)
    verifier_freeze_dir = verifier_freeze_dir or (package_root / DEFAULT_VERIFIER_FREEZE_DIR)
    inputs = _load_inputs(
        package_root=package_root,
        reachability_execution_dir=reachability_execution_dir,
        reachability_postrun_dir=reachability_postrun_dir,
        mapping_preflight_dir=mapping_preflight_dir,
        mapping_execution_dir=mapping_execution_dir,
        mapping_postrun_dir=mapping_postrun_dir,
        verifier_freeze_dir=verifier_freeze_dir,
    )
    semantic_policy = _semantic_policy(inputs)
    mapper_contract = _mapper_contract(
        inputs=inputs,
        semantic_policy=semantic_policy,
        package_root=package_root,
    )
    records = _map_records(
        inputs=inputs,
        semantic_policy=semantic_policy,
        mapper_contract=mapper_contract,
    )
    historical_freeze = _historical_freeze(
        inputs=inputs,
        mapping_execution_dir=mapping_execution_dir,
        mapping_postrun_dir=mapping_postrun_dir,
    )
    result_semantics, result_only_ids = _result_semantics(records)
    condition_route = _condition_route(records)
    fixed_support = _fixed_condition_support(records, result_only_ids)
    diagnostic_catalog = _diagnostic_catalog(
        records=records,
        result_semantics=result_semantics,
        semantic_policy=semantic_policy,
        mapper_contract=mapper_contract,
    )
    state_catalog, contrast_catalog = _state_and_contrast_catalogs(
        records,
        semantic_policy,
    )
    gold_fixture_audit = build_mapper_v2_gold_fixture_audit(
        semantic_policy=semantic_policy,
        mapper_contract=mapper_contract,
    )
    reference_audit = _reference_audit(records, package_root, gold_fixture_audit)
    classification_audit = _measurement_classification(inputs)
    destructive_audit = _destructive(
        records=records,
        mapper_contract=mapper_contract,
        semantic_policy=semantic_policy,
    )
    transition = _transition()

    output_dir.mkdir(parents=True, exist_ok=True)
    details: tuple[tuple[str, BaseModel], ...] = (
        ("historical_mapper_v1_freeze_audit.json", historical_freeze),
        ("result_semantics_diagnostic.json", result_semantics),
        ("condition_route_decomposition_audit.json", condition_route),
        ("fixed_condition_state_support_audit.json", fixed_support),
        ("mapper_v2_semantic_policy.json", semantic_policy),
        ("mapper_v2_contract.json", mapper_contract),
        ("mapper_v2_diagnostic_catalog.json", diagnostic_catalog),
        ("mapper_v2_state_catalog.json", state_catalog),
        ("state_contrast_catalog.json", contrast_catalog),
        ("mapper_v2_gold_fixture_audit.json", gold_fixture_audit),
        ("independent_reference_mapper_audit.json", reference_audit),
        ("measurement_classification_decomposition_audit.json", classification_audit),
        ("destructive_audit.json", destructive_audit),
        ("prospective_transition_contract.json", transition),
    )
    for name, value in details:
        _write_json_atomic(output_dir / name, value)
    detail_files = tuple(
        sorted(
            (_detail(output_dir / name, package_root) for name, _ in details),
            key=lambda item: item.relative_path,
        )
    )
    report_values = {
        "run_id": RUN_ID,
        "historical_v1_freeze_audit_id": historical_freeze.audit_id,
        "result_semantics_diagnostic_id": result_semantics.audit_id,
        "condition_route_decomposition_audit_id": condition_route.audit_id,
        "fixed_condition_support_audit_id": fixed_support.audit_id,
        "semantic_policy_id": semantic_policy.policy_id,
        "mapper_contract_id": mapper_contract.contract_id,
        "mapper_v2_diagnostic_catalog_id": diagnostic_catalog.catalog_id,
        "mapper_v2_state_catalog_id": state_catalog.catalog_id,
        "state_contrast_catalog_id": contrast_catalog.catalog_id,
        "mapper_v2_gold_fixture_audit_id": gold_fixture_audit.audit_id,
        "independent_reference_mapper_audit_id": reference_audit.audit_id,
        "measurement_classification_audit_id": classification_audit.audit_id,
        "destructive_audit_id": destructive_audit.audit_id,
        "transition_contract_id": transition.contract_id,
        "mapper_v2_diagnostic_state_count": state_catalog.state_count,
        "experimental_condition_count": condition_route.experimental_condition_id_count,
        "task_condition_cell_count": (condition_route.task_pre_treatment_condition_cell_count),
        "empirical_route_signature_count": condition_route.empirical_route_signature_count,
        "state_contrast_count": contrast_catalog.contrast_count,
        "detail_files": detail_files,
    }
    report = _model(
        StateSemanticsAuditReport,
        report_values,
        identity_field="report_id",
        prefix="finance_v26_state_semantics_audit_report:",
    )
    _write_json_atomic(output_dir / "report.json", report)
    return BuildProducts(
        historical_freeze=historical_freeze,
        result_semantics=result_semantics,
        condition_route=condition_route,
        fixed_condition_support=fixed_support,
        semantic_policy=semantic_policy,
        mapper_contract=mapper_contract,
        diagnostic_catalog=diagnostic_catalog,
        state_catalog=state_catalog,
        contrast_catalog=contrast_catalog,
        gold_fixture_audit=gold_fixture_audit,
        reference_audit=reference_audit,
        classification_audit=classification_audit,
        destructive_audit=destructive_audit,
        transition=transition,
        report=report,
        diagnostic_assignments=tuple(record.v2_assignment for record in records),
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build the zero-call v26.159 State Semantics and Condition Index audit."
    )
    parser.add_argument("--implementation-root", type=Path, default=Path.cwd())
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    package_root = _resolve_package_root(args.implementation_root)
    output_dir = args.output_dir or package_root / OUTPUT_DIR
    report = build_state_semantics_audit(
        implementation_root=args.implementation_root,
        output_dir=output_dir,
    ).report
    print(json.dumps(report.model_dump(mode="json"), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
