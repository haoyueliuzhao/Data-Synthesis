from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, cast

from pydantic import BaseModel, ValidationError

from trusted_synthesis.core.audit_artifacts import (
    AtomicAuditCaseResult,
    make_atomic_audit_case_result,
)
from trusted_synthesis.core.evaluation.contracts import QualityContractCompiler
from trusted_synthesis.core.operations.program import (
    ProgramExecutionError,
    TaskProgramExecutor,
    TaskProgramOracleVerifier,
)
from trusted_synthesis.core.operations.registry import default_registry
from trusted_synthesis.core.synthesis import ProofCarryingSampleCompiler
from trusted_synthesis.core.synthesis.schema import CompiledProofCarryingArtifacts
from trusted_synthesis.core.synthesis.validation import validate_compiled_artifacts
from trusted_synthesis.core.trajectory.admission import (
    DESTRUCTIVE_MUTATION_CHECKS,
    EXECUTABLE_CLOSURE_CHECKS,
    PUBLIC_SUFFICIENCY_CHECKS,
    AuditKind,
    JointCompilationAdmissionArtifact,
    JointCompilationAuditEvidence,
    RuntimePublicProjection,
    admit_joint_compilation,
    make_executable_component_manifest,
    make_joint_compilation_audit_evidence,
    make_runtime_public_projection,
)
from trusted_synthesis.core.trajectory.scaffolding import (
    SCAFFOLD_AIDS_BY_LEVEL,
    SCAFFOLD_GATES,
    SCAFFOLD_LEVELS,
    CapabilityPrerequisiteGraph,
    CapabilityScaffoldAdmissionArtifact,
    CapabilityScaffoldGateEvidence,
    CapabilityScaffoldLadderCompilation,
    MinimalPublicStateSummarySpec,
    ScaffoldGate,
    ScaffoldLevel,
    admit_capability_scaffold_ladder,
    compile_capability_scaffold_ladder,
    compile_public_state_summary,
    make_capability_prerequisite_graph,
    make_capability_prerequisite_node,
    make_capability_scaffold_gate_evidence,
    make_minimal_public_state_summary_spec,
    make_public_state_observation,
    make_scaffold_invariant_state_mapping_contract,
    scaffold_gate_checks,
    separate_scaffold_trace_for_state_mapping,
)
from trusted_synthesis.core.trajectory.specification import TrajectoryVerificationContext
from trusted_synthesis.core.vtdo.state_space import (
    AdmissibleTrajectoryVariation,
    TrajectoryStateSpaceCompilation,
    compile_trajectory_state_space,
    make_admissible_trajectory_variation,
)
from trusted_synthesis.domains.finance.adapter import FinanceArchiveAdapter
from trusted_synthesis.domains.finance.plugins import finance_plugin_set
from trusted_synthesis.domains.finance.policy import FinanceSemanticPolicy
from trusted_synthesis.domains.finance.quality_clauses import FinanceQualityClauseProvider
from trusted_synthesis.domains.finance.schema import FinanceArchiveConfig
from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_heterogeneous_mainline import (
    CapabilityHeterogeneousMainlineProtocol,
    MainlinePreflightReport,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_sensitive_frontier import (
    CapabilitySensitiveTaskArtifact,
    build_capability_sensitive_frontier_population,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_compiler_assisted_bridge import (
    BRIDGE_MECHANISMS,
    STATIC_CONSTRUCT_CHECKS,
    BridgeMechanism,
    BridgeStaticConstructAudit,
    CompilerAssistedBridgeContract,
    authorize_bridge_development,
    make_bridge_static_construct_audit,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_fresh_population import (
    V26CrossPopulationFreshnessAudit,
    V26FreshTaskPopulation,
    build_v26_cross_population_freshness_audit,
    build_v26_fresh_task_population,
    load_v26_selected_source_tasks,
    replay_v26_cross_population_freshness_audit,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_no_api_contracts import (
    V26CredentialFreeReplayObservation,
    V26ImmutableFileRecord,
    V26NoApiExperimentReport,
    v26_no_api_experiment_report_id,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_stage_router import (
    V26Stage,
    V26StageArtifactReference,
    V26StageLedger,
    advance_v26_stage,
    initialize_v26_stage_ledger,
    load_v26_stage_ledger,
    make_v26_stage_artifact_reference,
    replay_v26_stage_ledger,
    write_v26_stage_ledger,
)
from trusted_synthesis.hashing import canonical_hash

V26_NO_API_RUNNER_ID = "finance.v26.no_api_joint_scaffold"
V26_NO_API_RUNNER_VERSION = "1.0.0"
V26_JOINT_AUDITOR_VERSION = "1.0.0"
V26_SCAFFOLD_EVALUATOR_VERSION = "1.0.0"
V26_BRIDGE_STATIC_AUDITOR_VERSION = "1.0.0"


@dataclass
class _VariationProvider:
    variation_provider_id: str = "finance.v26.no_api_variation_provider"
    variation_provider_version: str = "1.0.0"

    def compile_variations(
        self,
        context: TrajectoryVerificationContext,
    ) -> tuple[AdmissibleTrajectoryVariation, ...]:
        evidence_count = max(1, len(context.evidence_bundle.evidence))
        depth = _program_depth(context.task.oracle.task_program.nodes)
        return (
            make_admissible_trajectory_variation(
                acquisition_requirement="bounded",
                evidence_support_requirement="required_roles",
                minimum_tool_calls=1,
                minimum_evidence_count=evidence_count,
            ),
            make_admissible_trajectory_variation(
                acquisition_requirement="expanded",
                evidence_support_requirement="expanded_context",
                execution_requirement="independent_reordering",
                verification_requirement="intermediate",
                lineage_requirement="output_upstream",
                minimum_tool_calls=2,
                minimum_evidence_count=evidence_count,
                minimum_reasoning_depth=depth,
                minimum_verification_degree=0.5,
            ),
            make_admissible_trajectory_variation(
                acquisition_requirement="multi_stage",
                evidence_support_requirement="expanded_context",
                execution_requirement="composed_execution",
                verification_requirement="full",
                lineage_requirement="full",
                minimum_tool_calls=3,
                minimum_evidence_count=evidence_count,
                minimum_reasoning_depth=depth,
                minimum_verification_degree=1.0,
            ),
        )


@dataclass(frozen=True)
class _CompilationContext:
    root: Any
    source_task: CapabilitySensitiveTaskArtifact
    compiled: CompiledProofCarryingArtifacts
    state_space: TrajectoryStateSpaceCompilation
    runtime_projections: tuple[RuntimePublicProjection, ...]


@dataclass(frozen=True)
class _ScaffoldContext:
    root: Any
    source_task: CapabilitySensitiveTaskArtifact
    compiled: CompiledProofCarryingArtifacts
    joint_admission: JointCompilationAdmissionArtifact
    ladder: CapabilityScaffoldLadderCompilation


def _program_depth(nodes: Sequence[Any]) -> int:
    depth_by_node: dict[str, int] = {}
    for node in nodes:
        depth_by_node[node.node_id] = 1 + max(
            (depth_by_node.get(ref, 0) for ref in node.dependencies),
            default=0,
        )
    return max(depth_by_node.values(), default=1)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_json(path: Path, payload: Any) -> None:
    if path.exists():
        raise ValueError(f"immutable v26 artifact already exists: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _payload_artifact_id(payload: Mapping[str, Any]) -> str:
    for key in (
        "artifact_id",
        "compilation_id",
        "evidence_id",
        "admission_id",
        "ladder_id",
        "audit_id",
        "authorization_id",
    ):
        if payload.get(key):
            return str(payload[key])
    return canonical_hash(payload, prefix="v26_no_api_payload:")


def _write_models(path: Path, values: Sequence[BaseModel]) -> None:
    rows = sorted(
        (item.model_dump(mode="json") for item in values),
        key=_payload_artifact_id,
    )
    _write_json(path, rows)


_REPORT_ACCOUNTING_PATHS = {
    "joint_compilation_count": "joint/compiled_proof_artifacts.json",
    "trajectory_state_space_count": "joint/trajectory_state_spaces.json",
    "joint_audit_evidence_count": "joint/joint_audit_evidence.json",
    "joint_admission_count": "joint/joint_admissions.json",
    "scaffold_ladder_count": "scaffold/ladders.json",
    "scaffold_gate_evidence_count": "scaffold/gate_evidence.json",
    "scaffold_admission_count": "scaffold/admissions.json",
    "bridge_static_audit_count": "bridge/static_construct_audits.json",
}


def _read_json_rows(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list) or any(not isinstance(item, dict) for item in payload):
        raise ValueError(f"v26 accounting artifact is not a JSON object list: {path}")
    return cast(list[dict[str, Any]], payload)


def _artifact_accounting(output_dir: Path) -> dict[str, int]:
    rows_by_field = {
        field: _read_json_rows(output_dir / relative_path)
        for field, relative_path in _REPORT_ACCOUNTING_PATHS.items()
    }
    joint_cases = sum(
        len(cast(list[Any], row.get("case_results", [])))
        for row in rows_by_field["joint_audit_evidence_count"]
    )
    scaffold_cases = [
        case
        for row in rows_by_field["scaffold_gate_evidence_count"]
        for case in cast(list[dict[str, Any]], row.get("case_results", []))
    ]
    bridge_cases = sum(
        len(cast(list[Any], row.get("case_results", [])))
        for row in rows_by_field["bridge_static_audit_count"]
    )
    return {
        **{field: len(rows) for field, rows in rows_by_field.items()},
        "joint_atomic_case_count": joint_cases,
        "scaffold_atomic_case_count": len(scaffold_cases),
        "history_collision_case_count": sum(
            item.get("check_id") == "history_collision_sufficiency" for item in scaffold_cases
        ),
        "cross_level_mapping_case_count": sum(
            item.get("check_id") == "cross_level_behavior_equivalence_registered"
            for item in scaffold_cases
        ),
        "bridge_static_atomic_case_count": bridge_cases,
    }


def _immutable_file(path: Path, root: Path) -> V26ImmutableFileRecord:
    return V26ImmutableFileRecord(
        relative_path=str(path.relative_to(root)),
        sha256=_sha256(path),
        byte_count=path.stat().st_size,
    )


def _finance_compiler(
    archive_config_path: Path,
) -> tuple[ProofCarryingSampleCompiler, Any]:
    adapter = FinanceArchiveAdapter(FinanceArchiveConfig.from_json(archive_config_path))
    inspection = adapter.inspect()
    if not inspection["compatible"]:
        raise ValueError(f"incompatible Finance Archive: {inspection['errors']}")
    registry = default_registry()
    grounding = adapter.source_grounding_verifier()
    plugin_set = finance_plugin_set(adapter, registry, grounding)
    quality = QualityContractCompiler(
        registry,
        domain_provider=FinanceQualityClauseProvider(),
    )
    compiler = ProofCarryingSampleCompiler(
        registry,
        quality,
        plugin_set,
        semantic_policy=FinanceSemanticPolicy(),
        source_grounding_verifier=grounding,
    )
    return compiler, grounding


def _compile_development_tasks(
    population: V26FreshTaskPopulation,
    *,
    archive_config_path: Path,
) -> tuple[_CompilationContext, ...]:
    sources = load_v26_selected_source_tasks(population)
    source_by_task = {item.task.task_id: item for item in sources}
    root_by_task = {item.task_id: item for item in population.tasks}
    compiler, grounding = _finance_compiler(archive_config_path)
    contexts: list[_CompilationContext] = []
    for task_id in population.task_ids:
        source = source_by_task[task_id]
        reports = tuple(grounding.verify(item) for item in source.public_corpus.evidence)
        if not reports or any(not item.passed for item in reports):
            failures = {item.evidence_id: item.failures for item in reports if not item.passed}
            raise ValueError(f"public Corpus source grounding failed: {failures}")
        compiled = compiler.compile(
            source.task,
            source.evidence_bundle,
            source.proof_graph,
            public_corpus=source.public_corpus,
        )
        validate_compiled_artifacts(compiled)
        state_space = compile_trajectory_state_space(
            compiled.joint_compilation,
            _VariationProvider(),
        )
        projections = tuple(
            make_runtime_public_projection(
                compiled,
                state_space,
                runtime_id=runtime_id,
            )
            for runtime_id in ("scripted", "autonomous")
        )
        contexts.append(
            _CompilationContext(
                root=root_by_task[task_id],
                source_task=source,
                compiled=compiled,
                state_space=state_space,
                runtime_projections=projections,
            )
        )
    return tuple(sorted(contexts, key=lambda item: item.compiled.task.task_id))


def _joint_manifest(auditor_id: str, check_id: str) -> dict[str, str]:
    return {
        "auditor_id": auditor_id,
        "auditor_version": V26_JOINT_AUDITOR_VERSION,
        "check_id": check_id,
    }


def _joint_case(
    *,
    check_id: str,
    joint_id: str,
    auditor_id: str,
    primary_passed: bool,
    replay_passed: bool,
    details: Mapping[str, Any],
) -> AtomicAuditCaseResult:
    if primary_passed != replay_passed:
        raise ValueError(f"independent Joint audit disagrees for {check_id}")
    output_id = canonical_hash(
        {"joint_id": joint_id, "auditor_id": auditor_id, "check_id": check_id},
        prefix="finance_v26_joint_audit_output:",
    )
    return make_atomic_audit_case_result(
        check_id=check_id,
        subject_id=joint_id,
        input_artifact_ids=(joint_id,),
        output_artifact_ids=(output_id,),
        implementation_manifest=_joint_manifest(auditor_id, check_id),
        replay_implementation_manifest=_joint_manifest(
            f"{auditor_id}.independent",
            check_id,
        ),
        check_passed=primary_passed and replay_passed,
        result_details=dict(details),
    )


def _public_sufficiency_results(
    context: _CompilationContext,
) -> dict[str, tuple[bool, bool, dict[str, Any]]]:
    compiled = context.compiled
    public = compiled.task.public
    serialized = json.dumps(
        [item.model_dump(mode="json") for item in context.runtime_projections],
        ensure_ascii=False,
        sort_keys=True,
    )
    secrets = (
        compiled.task.oracle.task_program.program_id,
        compiled.evidence_bundle.bundle_id,
        compiled.proof_graph.graph_id,
        *compiled.task.oracle.gold_evidence_ids,
    )
    corpus_ids = {item.evidence_id for item in compiled.public_corpus.evidence}
    gold_ids = set(compiled.task.oracle.gold_evidence_ids)
    decision_primary = bool(
        public.instruction and public.allowed_tools and public.answer_schema and public.requirements
    )
    decision_replay = bool(
        public.retrieval_scope
        and set(context.source_task.required_tool_ids) <= set(public.allowed_tools)
    )
    evidence_by_id = {item.evidence_id: item for item in compiled.evidence_bundle.evidence}
    ablated = dict(evidence_by_id)
    if gold_ids:
        ablated.pop(sorted(gold_ids)[0], None)
    ablation_primary = False
    try:
        TaskProgramExecutor(default_registry()).execute(
            compiled.task.oracle.task_program,
            ablated,
        )
    except ProgramExecutionError:
        ablation_primary = True
    ablation_replay = False
    try:
        TaskProgramOracleVerifier(default_registry()).derive_expected(
            compiled.task.oracle.task_program,
            ablated,
        )
    except ProgramExecutionError:
        ablation_replay = True
    oracle_primary = not any(secret in serialized for secret in secrets)
    oracle_replay = all(
        projection.public_artifact == compiled.public_artifact
        and projection.public_corpus_hash == compiled.public_corpus.corpus_hash
        for projection in context.runtime_projections
    )
    source_primary = all(
        projection.joint_compilation_id == compiled.joint_compilation.artifact_id
        and projection.omega_context_id == compiled.joint_compilation.omega.context_id
        for projection in context.runtime_projections
    )
    source_replay = len({item.runtime_id for item in context.runtime_projections}) == 2 and all(
        item.task_id == compiled.task.task_id for item in context.runtime_projections
    )
    return {
        "decision_information_present": (
            decision_primary,
            decision_replay,
            {"required_tool_count": len(context.source_task.required_tool_ids)},
        ),
        "critical_state_ablation_changes_decidability": (
            ablation_primary,
            ablation_replay,
            {
                "gold_count": len(gold_ids),
                "distractor_count": len(corpus_ids - gold_ids),
                "ablation_execution_rejected": ablation_primary,
                "ablation_oracle_replay_rejected": ablation_replay,
            },
        ),
        "oracle_fields_absent": (
            oracle_primary,
            oracle_replay,
            {"secret_marker_count": sum(secret in serialized for secret in secrets)},
        ),
        "runtime_projection_from_joint_source": (
            source_primary,
            source_replay,
            {"runtime_ids": sorted(item.runtime_id for item in context.runtime_projections)},
        ),
    }


def _executable_closure_results(
    context: _CompilationContext,
) -> dict[str, tuple[bool, bool, dict[str, Any]]]:
    source = context.source_task
    compiled = context.compiled
    node_ids = {item.node_id for item in compiled.task.oracle.task_program.nodes}
    referenced = {
        dependency
        for node in compiled.task.oracle.task_program.nodes
        for dependency in node.dependencies
    }
    preconditions_primary = referenced <= node_ids
    preconditions_replay = not source.verification.invariant_failures
    locator_primary = all(
        item.source_locator.storage_uri and item.source_locator.raw_object_id
        for item in compiled.public_corpus.evidence
    )
    locator_replay = all(
        item.provenance.source_record_id and item.provenance.content_hash
        for item in compiled.public_corpus.evidence
    )
    replay_primary = (
        source.execution.final_output == source.verification.independently_computed_output
        and source.verification.passed
    )
    replay_secondary = (
        source.execution.program_id == compiled.task.oracle.task_program.program_id
        and source.verification.program_id == source.execution.program_id
    )
    budget = source.structure.minimal_tool_calls
    budget_primary = budget >= len(source.query_stages) + len(
        compiled.task.oracle.task_program.nodes
    )
    budget_replay = budget >= len(source.required_tool_ids) and budget > 0
    return {
        "action_preconditions_closed": (
            preconditions_primary,
            preconditions_replay,
            {"operation_count": len(node_ids), "dependency_count": len(referenced)},
        ),
        "evidence_locators_reachable": (
            locator_primary,
            locator_replay,
            {"public_evidence_count": len(compiled.public_corpus.evidence)},
        ),
        "tool_order_replayable": (
            replay_primary,
            replay_secondary,
            {"program_id": source.execution.program_id},
        ),
        "budget_feasible": (
            budget_primary,
            budget_replay,
            {"minimal_tool_calls": budget},
        ),
    }


def _mutated_compiled_payload(
    compiled: CompiledProofCarryingArtifacts,
    check_id: str,
) -> dict[str, Any]:
    payload = compiled.model_dump(mode="json")
    if check_id == "remove_required_evidence_rejected":
        payload["evidence_bundle"]["evidence"].pop(0)
    elif check_id == "mutate_program_node_rejected":
        payload["task"]["oracle"]["task_program"]["nodes"][0]["operator_id"] = "unknown"
    elif check_id == "swap_operand_rejected":
        nodes = payload["task"]["oracle"]["task_program"]["nodes"]
        node = next(item for item in nodes if len(item["input_refs"]) >= 2)
        node["input_refs"] = list(reversed(node["input_refs"]))
    elif check_id == "change_time_or_unit_rejected":
        payload["evidence_bundle"]["evidence"][0]["payload"]["unit"] = "mutated-unit"
    elif check_id == "break_proof_edge_rejected":
        payload["proof_graph"]["edges"].pop(0)
    elif check_id == "inject_host_only_field_rejected":
        payload["public_artifact"]["host_event"] = "oracle-complete"
    elif check_id == "mutate_state_mapper_rejected":
        payload["joint_compilation"]["component_manifest"]["task_id"] = "task:mutated"
    elif check_id == "replace_public_projection_rejected":
        payload["public_artifact"]["task_public"]["task_id"] = "task:replacement"
    else:
        raise ValueError(f"unknown destructive mutation check: {check_id}")
    return payload


def _rejects_compiled_mutation(
    context: _CompilationContext,
    check_id: str,
) -> tuple[bool, bool, dict[str, Any]]:
    if check_id == "replace_public_projection_rejected":
        payload = context.runtime_projections[0].model_dump(mode="json")
        payload["public_artifact"]["task_public"]["task_id"] = "task:replacement"
        primary = False
        try:
            RuntimePublicProjection.model_validate(payload)
        except (ValidationError, ValueError, TypeError):
            primary = True
        replay = False
        try:
            RuntimePublicProjection.model_validate_json(
                json.dumps(payload, ensure_ascii=False, sort_keys=True)
            )
        except (ValidationError, ValueError, TypeError):
            replay = True
        return primary, replay, {"mutation_id": check_id}
    compiled = context.compiled
    payload = _mutated_compiled_payload(compiled, check_id)
    primary = False
    try:
        CompiledProofCarryingArtifacts.model_validate(payload)
    except (ValidationError, ValueError, TypeError, IndexError):
        primary = True
    replay = False
    try:
        parsed = CompiledProofCarryingArtifacts.model_validate_json(
            json.dumps(payload, ensure_ascii=False, sort_keys=True)
        )
        validate_compiled_artifacts(parsed)
    except (ValidationError, ValueError, TypeError, IndexError):
        replay = True
    return primary, replay, {"mutation_id": check_id}


def _destructive_mutation_results(
    context: _CompilationContext,
) -> dict[str, tuple[bool, bool, dict[str, Any]]]:
    return {
        check_id: _rejects_compiled_mutation(context, check_id)
        for check_id in DESTRUCTIVE_MUTATION_CHECKS
    }


def _compile_joint_audits(
    context: _CompilationContext,
) -> tuple[JointCompilationAuditEvidence, ...]:
    joint_id = context.compiled.joint_compilation.artifact_id
    results_by_kind: dict[
        AuditKind,
        dict[str, tuple[bool, bool, dict[str, Any]]],
    ] = {
        "public_sufficiency": _public_sufficiency_results(context),
        "executable_closure": _executable_closure_results(context),
        "destructive_mutation": _destructive_mutation_results(context),
    }
    expected_by_kind: dict[AuditKind, tuple[str, ...]] = {
        "public_sufficiency": PUBLIC_SUFFICIENCY_CHECKS,
        "executable_closure": EXECUTABLE_CLOSURE_CHECKS,
        "destructive_mutation": DESTRUCTIVE_MUTATION_CHECKS,
    }
    audits: list[JointCompilationAuditEvidence] = []
    for kind, expected in expected_by_kind.items():
        results = results_by_kind[kind]
        if tuple(results) != expected:
            raise ValueError(f"Joint audit implementation order differs for {kind}")
        auditor_id = f"{V26_NO_API_RUNNER_ID}.joint.{kind}"
        cases = tuple(
            _joint_case(
                check_id=check_id,
                joint_id=joint_id,
                auditor_id=auditor_id,
                primary_passed=results[check_id][0],
                replay_passed=results[check_id][1],
                details=results[check_id][2],
            )
            for check_id in expected
        )
        audits.append(
            make_joint_compilation_audit_evidence(
                audit_kind=kind,
                joint_compilation_id=joint_id,
                case_results=cases,
                auditor_id=auditor_id,
                auditor_version=V26_JOINT_AUDITOR_VERSION,
            )
        )
    return tuple(audits)


def _component_manifest(
    context: _CompilationContext,
    component_kind: Literal["independent_verifier", "trajectory_materializer"],
) -> Any:
    component_id = f"{V26_NO_API_RUNNER_ID}.{component_kind}"
    check_id = f"{component_kind}_contract_replay"
    joint_id = context.compiled.joint_compilation.artifact_id
    registry = default_registry()
    evidence = {item.evidence_id: item for item in context.compiled.evidence_bundle.evidence}
    if component_kind == "independent_verifier":
        validate_compiled_artifacts(context.compiled)
        replayed = CompiledProofCarryingArtifacts.model_validate_json(
            context.compiled.model_dump_json()
        )
        validate_compiled_artifacts(replayed)
        passed = replayed == context.compiled
    else:
        execution = TaskProgramExecutor(registry).execute(
            context.compiled.task.oracle.task_program,
            evidence,
        )
        verification = TaskProgramOracleVerifier(registry).verify(
            context.compiled.task.oracle.task_program,
            evidence,
            execution.node_outputs,
        )
        passed = (
            verification.passed
            and execution.final_output == verification.independently_computed_output
            and execution.final_output == context.source_task.execution.final_output
        )
    primary_manifest = {
        "component_id": component_id,
        "component_version": V26_NO_API_RUNNER_VERSION,
        "check_id": check_id,
    }
    replay_manifest = {
        "component_id": f"{component_id}.independent",
        "component_version": V26_NO_API_RUNNER_VERSION,
        "check_id": check_id,
    }
    replay_case = make_atomic_audit_case_result(
        check_id=check_id,
        subject_id=component_id,
        input_artifact_ids=(joint_id,),
        output_artifact_ids=(component_id,),
        implementation_manifest=primary_manifest,
        replay_implementation_manifest=replay_manifest,
        check_passed=passed,
        result_details={"task_id": context.compiled.task.task_id},
    )
    return make_executable_component_manifest(
        component_kind=component_kind,
        component_id=component_id,
        component_version=V26_NO_API_RUNNER_VERSION,
        joint_compilation_id=joint_id,
        input_schema={"joint_compilation_id": "string", "task_id": "string"},
        output_schema={"passed": "boolean", "result_hash": "string"},
        replay_case=replay_case,
    )


def _admit_joint_context(
    context: _CompilationContext,
    audits: Sequence[JointCompilationAuditEvidence],
) -> JointCompilationAdmissionArtifact:
    by_kind = {item.audit_kind: item for item in audits}
    admission = admit_joint_compilation(
        context.compiled,
        context.state_space,
        runtime_projections=context.runtime_projections,
        public_sufficiency_evidence=by_kind["public_sufficiency"],
        executable_closure_evidence=by_kind["executable_closure"],
        destructive_mutation_evidence=by_kind["destructive_mutation"],
        verifier_manifest=_component_manifest(context, "independent_verifier"),
        materialization_manifest=_component_manifest(context, "trajectory_materializer"),
    )
    if admission.status != "admitted":
        raise ValueError(f"Joint Compilation blocked: {admission.blockers}")
    return admission


def _capability_graph(target: str) -> CapabilityPrerequisiteGraph:
    interpret = make_capability_prerequisite_node(
        node_key="interpret_public_state",
        capability_id="state_interpretation",
        public_requirement_id="interpret_public_relation_and_completion_state",
        observable_input_kinds=("public_relation_state", "public_completion_condition"),
        model_decision_kind="relation_classification",
        allowed_public_effects=("update_public_completion_state",),
        completion_evaluator_id="finance.v26.public_state_interpretation",
        completion_evaluator_version="1.0.0",
    )
    target_specs: dict[str, tuple[str, str, tuple[str, ...], tuple[str, ...]]] = {
        "planning": (
            "select_contextual_action",
            "select_the_context_consistent_tool_category",
            ("public_relation_state", "public_tool_result"),
            ("acquire_public_evidence", "transform_public_value"),
        ),
        "reconciliation": (
            "reconcile_semantics",
            "identify_and_reconcile_the_public_definition_difference",
            ("public_relation_state", "public_evidence_role"),
            ("transform_public_value", "validate_public_candidate"),
        ),
        "recovery": (
            "repair_failure",
            "repair_the_typed_public_failure",
            ("public_failure_category", "public_tool_result"),
            ("repair_public_failure", "validate_public_candidate"),
        ),
        "stopping": (
            "decide_stopping",
            "continue_or_stop_from_public_completion_conditions",
            ("public_completion_condition", "public_budget_state"),
            ("update_public_completion_state", "terminate_if_publicly_complete"),
        ),
    }
    key, requirement, inputs, effects = target_specs[target]
    decision_kind = (
        "continue_or_stop"
        if target == "stopping"
        else ("failure_recovery" if target == "recovery" else "tool_category_selection")
    )
    decide = make_capability_prerequisite_node(
        node_key=key,
        capability_id=target,
        public_requirement_id=requirement,
        prerequisite_node_keys=("interpret_public_state",),
        observable_input_kinds=cast(Any, inputs),
        model_decision_kind=cast(Any, decision_kind),
        allowed_public_effects=cast(Any, effects),
        completion_evaluator_id=f"finance.v26.{target}",
        completion_evaluator_version="1.0.0",
    )
    return make_capability_prerequisite_graph(
        target_capability_id=target,
        nodes=(interpret, decide),
        target_node_keys=(key,),
    )


def _summary_spec() -> MinimalPublicStateSummarySpec:
    return make_minimal_public_state_summary_spec(
        compiler_id="finance.v26.minimal_public_state_summary",
        compiler_version="2.0.0",
        source_kinds=(
            "task_public",
            "public_tool_schema",
            "public_tool_observation",
            "public_runtime_counter",
        ),
        included_fields=(
            "selected_evidence_roles",
            "completed_operation_types",
            "unmet_public_preconditions",
            "resolved_relation_types",
            "unresolved_relation_types",
            "available_operation_references",
            "remaining_tool_budget",
            "public_completion_conditions",
            "typed_failure_category",
            "typed_failure_category_history",
            "public_completion_condition_history",
        ),
    )


def _compile_scaffold_context(
    context: _CompilationContext,
    admission: JointCompilationAdmissionArtifact,
) -> _ScaffoldContext:
    mapping = make_scaffold_invariant_state_mapping_contract(admission)
    ladder = compile_capability_scaffold_ladder(
        context.compiled,
        admission,
        runtime_id="autonomous",
        target_capability_id=context.root.target_capability_id,
        scaffold_policy_version="finance.v26.bridge_scaffold.v1",
        dependency_graph=_capability_graph(context.root.target_capability_id),
        summary_spec=_summary_spec(),
        state_mapping_contract=mapping,
    )
    return _ScaffoldContext(
        root=context.root,
        source_task=context.source_task,
        compiled=context.compiled,
        joint_admission=admission,
        ladder=ladder,
    )


def _history_collision_passes(context: _ScaffoldContext) -> tuple[bool, dict[str, Any]]:
    task_id = context.compiled.task.task_id
    spec = context.ladder.summary_spec
    common_final = {
        "typed_failure_category": "resolved_public_failure",
        "typed_failure_category_history": "resolved_public_failure",
        "public_completion_conditions": ("evidence_and_operation_complete",),
        "public_completion_condition_history": "evidence_and_operation_complete",
    }
    histories = (
        (
            ("lookup_timeout", "evidence_missing"),
            ("definition_mismatch", "normalization_pending"),
        ),
        (
            ("definition_mismatch", "normalization_pending"),
            ("lookup_timeout", "evidence_missing"),
        ),
    )
    summaries = []
    for history in histories:
        observations = [
            make_public_state_observation(
                task_id=task_id,
                sequence_index=index,
                source_kind="public_tool_observation",
                values={
                    "typed_failure_category": failure,
                    "typed_failure_category_history": failure,
                    "public_completion_conditions": (condition,),
                    "public_completion_condition_history": condition,
                },
            )
            for index, (failure, condition) in enumerate(history)
        ]
        observations.append(
            make_public_state_observation(
                task_id=task_id,
                sequence_index=len(observations),
                source_kind="public_runtime_counter",
                values=cast(Any, common_final),
            )
        )
        summaries.append(compile_public_state_summary(spec, observations))
    left, right = summaries
    latest_equal = (
        left.values["typed_failure_category"] == right.values["typed_failure_category"]
        and left.values["public_completion_conditions"]
        == right.values["public_completion_conditions"]
    )
    histories_distinct = (
        left.values["typed_failure_category_history"]
        != right.values["typed_failure_category_history"]
        and left.values["public_completion_condition_history"]
        != right.values["public_completion_condition_history"]
    )
    return latest_equal and histories_distinct and left.summary_id != right.summary_id, {
        "latest_values_equal": latest_equal,
        "ordered_histories_distinct": histories_distinct,
        "left_summary_id": left.summary_id,
        "right_summary_id": right.summary_id,
    }


def _cross_level_mapping_passes(
    context: _ScaffoldContext,
) -> tuple[bool, dict[str, Any]]:
    behavior = {
        "tool_choice": "query_structured_fact",
        "tool_arguments": {"role": "required_financial_evidence"},
        "evidence_selection": tuple(context.compiled.task.oracle.gold_evidence_ids),
        "recovery_action": "retry_with_typed_constraint",
        "verification_action": "independent_program_replay",
        "stop_decision": "stop_when_public_completion_holds",
    }
    views = tuple(
        separate_scaffold_trace_for_state_mapping(
            context.ladder.state_mapping_contract,
            behavior_payload=behavior,
            scaffold_trace={
                "scaffold_level": projection.scaffold_level,
                "scaffold_policy_version": projection.scaffold_policy_version,
                "public_state_summary": bool(projection.public_summary_spec),
                "capability_contract": bool(projection.public_capability_nodes),
                "action_effect_contract": bool(projection.public_capability_nodes),
                "public_subgoal_dag": bool(projection.public_dependency_edges),
            },
        )
        for projection in context.ladder.projections
    )
    behavior_ids = {item.behavior_state_identity for item in views}
    trace_hashes = {item.scaffold_trace_hash for item in views}
    return len(behavior_ids) == 1 and len(trace_hashes) == 4, {
        "behavior_identity_count": len(behavior_ids),
        "scaffold_trace_hash_count": len(trace_hashes),
    }


def _history_collision_replay_passes(context: _ScaffoldContext) -> bool:
    spec = MinimalPublicStateSummarySpec.model_validate_json(
        context.ladder.summary_spec.model_dump_json()
    )
    task_id = context.compiled.task.task_id
    expected_failures = [
        ["lookup_timeout", "definition_mismatch", "resolved_public_failure"],
        ["definition_mismatch", "lookup_timeout", "resolved_public_failure"],
    ]
    expected_conditions = [
        ["evidence_missing", "normalization_pending", "evidence_and_operation_complete"],
        ["normalization_pending", "evidence_missing", "evidence_and_operation_complete"],
    ]
    summaries = []
    for failures, conditions in zip(expected_failures, expected_conditions, strict=True):
        observations = tuple(
            make_public_state_observation(
                task_id=task_id,
                sequence_index=index,
                source_kind=(
                    "public_runtime_counter"
                    if index == len(failures) - 1
                    else "public_tool_observation"
                ),
                values={
                    "typed_failure_category": failure,
                    "typed_failure_category_history": failure,
                    "public_completion_conditions": (condition,),
                    "public_completion_condition_history": condition,
                },
            )
            for index, (failure, condition) in enumerate(zip(failures, conditions, strict=True))
        )
        summary = compile_public_state_summary(spec, observations)
        summaries.append(type(summary).model_validate_json(summary.model_dump_json()))
    left, right = summaries
    return bool(
        left.values["typed_failure_category_history"] == expected_failures[0]
        and right.values["typed_failure_category_history"] == expected_failures[1]
        and left.values["public_completion_condition_history"] == expected_conditions[0]
        and right.values["public_completion_condition_history"] == expected_conditions[1]
        and left.values["typed_failure_category"]
        == right.values["typed_failure_category"]
        == "resolved_public_failure"
        and left.values["public_completion_conditions"]
        == right.values["public_completion_conditions"]
        == ["evidence_and_operation_complete"]
        and left.summary_id != right.summary_id
    )


def _cross_level_mapping_replay_passes(context: _ScaffoldContext) -> bool:
    mapping = type(context.ladder.state_mapping_contract).model_validate_json(
        context.ladder.state_mapping_contract.model_dump_json()
    )
    behavior = {
        "stop_decision": "stop_when_public_completion_holds",
        "verification_action": "independent_program_replay",
        "recovery_action": "retry_with_typed_constraint",
        "evidence_selection": tuple(context.compiled.task.oracle.gold_evidence_ids),
        "tool_arguments": {"role": "required_financial_evidence"},
        "tool_choice": "query_structured_fact",
    }
    views = []
    for projection in reversed(context.ladder.projections):
        view = separate_scaffold_trace_for_state_mapping(
            mapping,
            behavior_payload=behavior,
            scaffold_trace={
                "public_subgoal_dag": bool(projection.public_dependency_edges),
                "action_effect_contract": bool(projection.public_capability_nodes),
                "capability_contract": bool(projection.public_capability_nodes),
                "public_state_summary": bool(projection.public_summary_spec),
                "scaffold_policy_version": projection.scaffold_policy_version,
                "scaffold_level": projection.scaffold_level,
            },
        )
        views.append(type(view).model_validate_json(view.model_dump_json()))
    return bool(
        len({item.behavior_state_identity for item in views}) == 1
        and len({item.scaffold_trace_hash for item in views}) == len(SCAFFOLD_LEVELS)
    )


def _scaffold_replay_checks(
    context: _ScaffoldContext,
) -> dict[tuple[ScaffoldLevel, ScaffoldGate, str], bool]:
    compiled = CompiledProofCarryingArtifacts.model_validate_json(
        context.compiled.model_dump_json()
    )
    joint_admission = JointCompilationAdmissionArtifact.model_validate_json(
        context.joint_admission.model_dump_json()
    )
    ladder = CapabilityScaffoldLadderCompilation.model_validate_json(
        context.ladder.model_dump_json()
    )
    replay_context = _ScaffoldContext(
        root=context.root,
        source_task=context.source_task,
        compiled=compiled,
        joint_admission=joint_admission,
        ladder=ladder,
    )
    history_passed = _history_collision_replay_passes(replay_context)
    mapping_passed = _cross_level_mapping_replay_passes(replay_context)
    results: dict[tuple[ScaffoldLevel, ScaffoldGate, str], bool] = {}
    for projection in reversed(ladder.projections):
        level = projection.scaffold_level
        serialized = json.dumps(projection.model_dump(mode="json"), sort_keys=True)
        gold_ids = tuple(compiled.task.oracle.gold_evidence_ids)
        previous = ladder.projections[max(0, projection.scaffold_rank - 1)]
        exact_aids = projection.aid_kinds == SCAFFOLD_AIDS_BY_LEVEL[level]
        checks = {
            "answer_contract_unchanged": (
                projection.base_runtime_projection.public_artifact.task_public.answer_schema
                == compiled.task.public.answer_schema
            ),
            "evidence_manifest_unchanged": (
                projection.base_runtime_projection.public_corpus_hash
                == compiled.public_corpus.corpus_hash
            ),
            "program_manifest_unchanged": (
                ladder.joint_admission.compiled_artifacts.task.oracle.task_program.program_hash
                == compiled.task.oracle.task_program.program_hash
            ),
            "proof_graph_manifest_unchanged": (
                ladder.joint_admission.compiled_artifacts.proof_graph.graph_hash
                == compiled.proof_graph.graph_hash
            ),
            "quality_contract_unchanged": (
                ladder.joint_admission.compiled_artifacts.quality_contract.contract_hash
                == compiled.quality_contract.contract_hash
            ),
            "decision_information_present": bool(
                projection.base_runtime_projection.public_artifact.task_public.instruction
            ),
            "critical_information_ablation_registered": bool(gold_ids),
            "runtime_projection_replayable": (
                projection.base_runtime_projection in ladder.joint_admission.runtime_projections
            ),
            "history_collision_sufficiency": history_passed,
            "model_selects_target_decision": all(
                item.target_authority == "model" for item in projection.public_capability_nodes
            ),
            "correct_action_absent": not projection.correct_action_exposed,
            "correct_arguments_absent": not projection.correct_arguments_exposed,
            "hidden_program_path_absent": not projection.hidden_program_path_exposed,
            "gold_fields_absent": not any(item in serialized for item in gold_ids),
            "host_events_absent": "host_event" not in serialized,
            "mechanism_labels_absent": "mechanism_activation" not in serialized,
            "internal_completion_state_absent": "internal_completion" not in serialized,
            "zero_aid_baseline_exact": level != "gamma_0" or not projection.aid_kinds,
            "unassisted_control_registered": ladder.projections[0].scaffold_level == "gamma_0",
            "incremental_aid_set_exact": exact_aids,
            "predecessor_projection_registered": (
                level == "gamma_0" or previous.scaffold_rank == projection.scaffold_rank - 1
            ),
            "required_increment_ablation_registered": (
                level == "gamma_0" or set(previous.aid_kinds) < set(projection.aid_kinds)
            ),
            "irrelevant_aid_control_registered": exact_aids,
            "scaffold_rank_order_preserved": (
                projection.scaffold_rank == SCAFFOLD_LEVELS.index(level)
            ),
            "gamma_zero_projection_exists": ladder.projections[0].scaffold_level == "gamma_0",
            "semantic_root_unchanged_on_removal": all(
                item.joint_compilation_id == ladder.joint_compilation_id
                for item in reversed(ladder.projections)
            ),
            "scaffold_absent_from_answer_and_gold": all(
                aid not in json.dumps(compiled.task.public.answer_schema, sort_keys=True)
                for aid in projection.aid_kinds
            ),
            "gamma_zero_evaluation_independently_executable": (
                ladder.joint_admission.verifier_manifest.replay_case.check_passed
            ),
            "task_definition_unchanged_on_removal": all(
                item.base_runtime_projection.task_id == compiled.task.task_id
                for item in reversed(ladder.projections)
            ),
            "state_mapper_root_unchanged": all(
                item.state_mapping_contract_id == ladder.state_mapping_contract.mapping_contract_id
                for item in reversed(ladder.projections)
            ),
            "scaffold_fields_stripped_before_mapping": (
                ladder.state_mapping_contract.strip_before_state_mapping
            ),
            "behavioral_decisions_preserved": mapping_passed,
            "scaffold_trace_side_channel_registered": (
                ladder.state_mapping_contract.scaffold_trace_preserved_for_audit
            ),
            "cross_level_behavior_equivalence_registered": mapping_passed,
        }
        for gate in SCAFFOLD_GATES:
            for check_id in scaffold_gate_checks(level, gate):
                if check_id not in checks:
                    raise ValueError(
                        f"unimplemented independent Scaffold replay: {level}:{gate}:{check_id}"
                    )
                results[(level, gate, check_id)] = checks[check_id]
    return results


def _scaffold_check(
    context: _ScaffoldContext,
    *,
    level: ScaffoldLevel,
    gate: ScaffoldGate,
    check_id: str,
    replay_passed: bool,
) -> tuple[bool, bool, dict[str, Any]]:
    ladder = context.ladder
    projection = next(item for item in ladder.projections if item.scaffold_level == level)
    compiled = context.compiled
    serialized = json.dumps(projection.model_dump(mode="json"), sort_keys=True)
    gold_ids = tuple(compiled.task.oracle.gold_evidence_ids)
    history_passed, history_details = _history_collision_passes(context)
    mapping_passed, mapping_details = _cross_level_mapping_passes(context)
    exact_aids = projection.aid_kinds == SCAFFOLD_AIDS_BY_LEVEL[level]
    previous_rank = max(0, projection.scaffold_rank - 1)
    previous = ladder.projections[previous_rank]
    checks: dict[str, bool] = {
        "answer_contract_unchanged": (
            projection.base_runtime_projection.public_artifact.task_public.answer_schema
            == compiled.task.public.answer_schema
        ),
        "evidence_manifest_unchanged": (
            projection.base_runtime_projection.public_corpus_hash
            == compiled.public_corpus.corpus_hash
        ),
        "program_manifest_unchanged": (
            ladder.joint_admission.compiled_artifacts.task.oracle.task_program.program_hash
            == compiled.task.oracle.task_program.program_hash
        ),
        "proof_graph_manifest_unchanged": (
            ladder.joint_admission.compiled_artifacts.proof_graph.graph_hash
            == compiled.proof_graph.graph_hash
        ),
        "quality_contract_unchanged": (
            ladder.joint_admission.compiled_artifacts.quality_contract.contract_hash
            == compiled.quality_contract.contract_hash
        ),
        "decision_information_present": bool(
            projection.base_runtime_projection.public_artifact.task_public.instruction
        ),
        "critical_information_ablation_registered": bool(gold_ids),
        "runtime_projection_replayable": (
            projection.base_runtime_projection in ladder.joint_admission.runtime_projections
        ),
        "history_collision_sufficiency": history_passed,
        "model_selects_target_decision": all(
            item.target_authority == "model" for item in projection.public_capability_nodes
        ),
        "correct_action_absent": not projection.correct_action_exposed,
        "correct_arguments_absent": not projection.correct_arguments_exposed,
        "hidden_program_path_absent": not projection.hidden_program_path_exposed,
        "gold_fields_absent": not any(item in serialized for item in gold_ids),
        "host_events_absent": "host_event" not in serialized,
        "mechanism_labels_absent": "mechanism_activation" not in serialized,
        "internal_completion_state_absent": "internal_completion" not in serialized,
        "zero_aid_baseline_exact": level != "gamma_0" or not projection.aid_kinds,
        "unassisted_control_registered": ladder.projections[0].scaffold_level == "gamma_0",
        "incremental_aid_set_exact": exact_aids,
        "predecessor_projection_registered": (
            level == "gamma_0" or previous.scaffold_rank == projection.scaffold_rank - 1
        ),
        "required_increment_ablation_registered": (
            level == "gamma_0" or set(previous.aid_kinds) < set(projection.aid_kinds)
        ),
        "irrelevant_aid_control_registered": exact_aids,
        "scaffold_rank_order_preserved": projection.scaffold_rank == SCAFFOLD_LEVELS.index(level),
        "gamma_zero_projection_exists": ladder.projections[0].scaffold_level == "gamma_0",
        "semantic_root_unchanged_on_removal": all(
            item.joint_compilation_id == ladder.joint_compilation_id for item in ladder.projections
        ),
        "scaffold_absent_from_answer_and_gold": all(
            aid not in json.dumps(compiled.task.public.answer_schema, sort_keys=True)
            for aid in projection.aid_kinds
        ),
        "gamma_zero_evaluation_independently_executable": (
            ladder.joint_admission.verifier_manifest.replay_case.check_passed
        ),
        "task_definition_unchanged_on_removal": all(
            item.base_runtime_projection.task_id == compiled.task.task_id
            for item in ladder.projections
        ),
        "state_mapper_root_unchanged": all(
            item.state_mapping_contract_id == ladder.state_mapping_contract.mapping_contract_id
            for item in ladder.projections
        ),
        "scaffold_fields_stripped_before_mapping": (
            ladder.state_mapping_contract.strip_before_state_mapping
        ),
        "behavioral_decisions_preserved": mapping_passed,
        "scaffold_trace_side_channel_registered": (
            ladder.state_mapping_contract.scaffold_trace_preserved_for_audit
        ),
        "cross_level_behavior_equivalence_registered": mapping_passed,
    }
    expected = scaffold_gate_checks(level, gate)
    if check_id not in expected or check_id not in checks:
        raise ValueError(f"unimplemented scaffold audit check: {level}:{gate}:{check_id}")
    primary = checks[check_id]
    details: dict[str, Any] = {
        "scaffold_level": level,
        "gate": gate,
        "aid_kinds": projection.aid_kinds,
    }
    if check_id == "history_collision_sufficiency":
        details.update(history_details)
    if check_id in {
        "behavioral_decisions_preserved",
        "cross_level_behavior_equivalence_registered",
    }:
        details.update(mapping_details)
    return primary, replay_passed, details


def _scaffold_gate_evidence(
    context: _ScaffoldContext,
) -> tuple[CapabilityScaffoldGateEvidence, ...]:
    rows: list[CapabilityScaffoldGateEvidence] = []
    replay_checks = _scaffold_replay_checks(context)
    for projection in context.ladder.projections:
        level = projection.scaffold_level
        for gate in SCAFFOLD_GATES:
            evaluator_id = f"{V26_NO_API_RUNNER_ID}.scaffold.{gate}"
            cases = []
            for check_id in scaffold_gate_checks(level, gate):
                primary, replay, details = _scaffold_check(
                    context,
                    level=level,
                    gate=gate,
                    check_id=check_id,
                    replay_passed=replay_checks[(level, gate, check_id)],
                )
                if primary != replay:
                    raise ValueError(f"independent Scaffold audit disagrees for {check_id}")
                cases.append(
                    make_atomic_audit_case_result(
                        check_id=check_id,
                        subject_id=projection.projection_id,
                        input_artifact_ids=(context.ladder.ladder_id, projection.projection_id),
                        output_artifact_ids=(
                            canonical_hash(
                                {
                                    "projection_id": projection.projection_id,
                                    "gate": gate,
                                    "check_id": check_id,
                                },
                                prefix="finance_v26_scaffold_audit_output:",
                            ),
                        ),
                        implementation_manifest={
                            "evaluator_id": evaluator_id,
                            "evaluator_version": V26_SCAFFOLD_EVALUATOR_VERSION,
                            "check_id": check_id,
                        },
                        replay_implementation_manifest={
                            "evaluator_id": f"{evaluator_id}.independent",
                            "evaluator_version": V26_SCAFFOLD_EVALUATOR_VERSION,
                            "check_id": check_id,
                        },
                        check_passed=primary and replay,
                        result_details=details,
                    )
                )
            rows.append(
                make_capability_scaffold_gate_evidence(
                    ladder_id=context.ladder.ladder_id,
                    projection_id=projection.projection_id,
                    joint_compilation_id=context.ladder.joint_compilation_id,
                    scaffold_level=level,
                    gate=gate,
                    case_results=cases,
                    evaluator_id=evaluator_id,
                    evaluator_version=V26_SCAFFOLD_EVALUATOR_VERSION,
                )
            )
    return tuple(rows)


def _bridge_static_check(
    *,
    contract: CompilerAssistedBridgeContract,
    mechanism: BridgeMechanism,
    context: _ScaffoldContext,
    admission: CapabilityScaffoldAdmissionArtifact,
    check_id: str,
    replay_passed: bool,
) -> tuple[bool, bool, dict[str, Any]]:
    mechanism_contract = next(
        item for item in contract.mechanisms if item.mechanism_id == mechanism
    )
    serialized = json.dumps(
        [item.model_dump(mode="json") for item in context.ladder.projections],
        sort_keys=True,
    )
    gold_ids = context.compiled.task.oracle.gold_evidence_ids
    check_map = {
        "estimand_definition_frozen": bool(mechanism_contract.estimands),
        "estimand_evaluator_replayable": all(
            item.outcome_type == "bernoulli" and item.definition
            for item in mechanism_contract.estimands
        ),
        "public_mutation_preserves_nontarget_semantics": all(
            item.joint_compilation_id == context.ladder.joint_compilation_id
            and item.base_runtime_projection.task_id == context.compiled.task.task_id
            for item in context.ladder.projections
        ),
        "oracle_fields_absent": not any(item in serialized for item in gold_ids),
        "host_only_labels_absent": all(
            not projection.correct_action_exposed
            and not projection.correct_arguments_exposed
            and not projection.hidden_program_path_exposed
            and not projection.host_completion_label_exposed
            for projection in context.ladder.projections
        ),
        "construct_fidelity_exact": (
            admission.status == "admitted"
            and all(
                passed for gates in admission.gates_by_level.values() for passed in gates.values()
            )
        ),
    }
    passed = check_map[check_id]
    return (
        passed,
        replay_passed,
        {
            "mechanism_id": mechanism,
            "task_id": context.compiled.task.task_id,
            "scaffold_admission_id": admission.admission_id,
        },
    )


def _bridge_static_replay_checks(
    *,
    contract: CompilerAssistedBridgeContract,
    mechanism: BridgeMechanism,
    context: _ScaffoldContext,
    admission: CapabilityScaffoldAdmissionArtifact,
) -> dict[str, bool]:
    replayed_contract = CompilerAssistedBridgeContract.model_validate_json(
        contract.model_dump_json()
    )
    replayed_ladder = CapabilityScaffoldLadderCompilation.model_validate_json(
        context.ladder.model_dump_json()
    )
    replayed_admission = CapabilityScaffoldAdmissionArtifact.model_validate_json(
        admission.model_dump_json()
    )
    replayed_compiled = CompiledProofCarryingArtifacts.model_validate_json(
        context.compiled.model_dump_json()
    )
    mechanism_contract = next(
        item for item in reversed(replayed_contract.mechanisms) if item.mechanism_id == mechanism
    )
    serialized = json.dumps(
        [item.model_dump(mode="json") for item in reversed(replayed_ladder.projections)],
        sort_keys=True,
    )
    gold_ids = tuple(replayed_compiled.task.oracle.gold_evidence_ids)
    return {
        "estimand_definition_frozen": len(mechanism_contract.estimands) > 0,
        "estimand_evaluator_replayable": all(
            bool(item.definition) and item.outcome_type == "bernoulli"
            for item in reversed(mechanism_contract.estimands)
        ),
        "public_mutation_preserves_nontarget_semantics": all(
            projection.base_runtime_projection.task_id == replayed_compiled.task.task_id
            and projection.joint_compilation_id == replayed_ladder.joint_compilation_id
            for projection in reversed(replayed_ladder.projections)
        ),
        "oracle_fields_absent": all(item not in serialized for item in gold_ids),
        "host_only_labels_absent": all(
            not any(
                (
                    projection.correct_action_exposed,
                    projection.correct_arguments_exposed,
                    projection.hidden_program_path_exposed,
                    projection.host_completion_label_exposed,
                )
            )
            for projection in reversed(replayed_ladder.projections)
        ),
        "construct_fidelity_exact": bool(
            replayed_admission.status == "admitted"
            and not replayed_admission.blockers
            and all(
                all(gates.values())
                for _, gates in sorted(replayed_admission.gates_by_level.items())
            )
        ),
    }


def _bridge_static_audits(
    contract: CompilerAssistedBridgeContract,
    contexts: Sequence[_ScaffoldContext],
    admissions: Sequence[CapabilityScaffoldAdmissionArtifact],
) -> tuple[BridgeStaticConstructAudit, ...]:
    admission_by_joint = {item.joint_compilation_id: item for item in admissions}
    rows: list[BridgeStaticConstructAudit] = []
    for mechanism in BRIDGE_MECHANISMS:
        selected = [item for item in contexts if item.root.mechanism_id == mechanism]
        task_admission_ids = {
            item.compiled.task.task_id: admission_by_joint[
                item.ladder.joint_compilation_id
            ].admission_id
            for item in selected
        }
        auditor_id = f"{V26_NO_API_RUNNER_ID}.bridge_static.{mechanism}"
        cases: list[AtomicAuditCaseResult] = []
        for context in selected:
            admission = admission_by_joint[context.ladder.joint_compilation_id]
            replay_checks = _bridge_static_replay_checks(
                contract=contract,
                mechanism=mechanism,
                context=context,
                admission=admission,
            )
            for check_id in STATIC_CONSTRUCT_CHECKS:
                primary, replay, details = _bridge_static_check(
                    contract=contract,
                    mechanism=mechanism,
                    context=context,
                    admission=admission,
                    check_id=check_id,
                    replay_passed=replay_checks[check_id],
                )
                if primary != replay:
                    raise ValueError(f"Bridge static replay disagrees for {check_id}")
                cases.append(
                    make_atomic_audit_case_result(
                        check_id=check_id,
                        subject_id=admission.admission_id,
                        input_artifact_ids=(contract.contract_id, admission.admission_id),
                        output_artifact_ids=(
                            canonical_hash(
                                {
                                    "admission_id": admission.admission_id,
                                    "check_id": check_id,
                                },
                                prefix="finance_v26_bridge_static_output:",
                            ),
                        ),
                        implementation_manifest={
                            "auditor_id": auditor_id,
                            "auditor_version": V26_BRIDGE_STATIC_AUDITOR_VERSION,
                            "check_id": check_id,
                        },
                        replay_implementation_manifest={
                            "auditor_id": f"{auditor_id}.independent",
                            "auditor_version": V26_BRIDGE_STATIC_AUDITOR_VERSION,
                            "check_id": check_id,
                        },
                        check_passed=primary and replay,
                        result_details=details,
                    )
                )
        rows.append(
            make_bridge_static_construct_audit(
                contract_id=contract.contract_id,
                mechanism_id=mechanism,
                task_admission_ids=task_admission_ids,
                case_results=cases,
                auditor_id=auditor_id,
                auditor_version=V26_BRIDGE_STATIC_AUDITOR_VERSION,
            )
        )
    return tuple(rows)


def _artifact_reference(role: Any, path: Path) -> V26StageArtifactReference:
    return make_v26_stage_artifact_reference(role, path)


def _advance(
    ledger: V26StageLedger,
    *,
    stage: V26Stage,
    references: Sequence[V26StageArtifactReference],
    output_dir: Path,
) -> V26StageLedger:
    advanced = advance_v26_stage(
        ledger,
        stage=stage,
        artifacts=references,
        model_api_calls=0,
        gpu_jobs=0,
    )
    write_v26_stage_ledger(
        advanced,
        output_dir / "ledgers" / f"{len(advanced.completed_stages):02d}_{stage}.json",
    )
    return advanced


def _run_credential_free_replay(
    output_dir: Path,
    ledger: V26StageLedger,
) -> V26CredentialFreeReplayObservation:
    command = (
        sys.executable,
        "-m",
        "trusted_synthesis.experiments.vtdo_experiment.phase1_v26_no_api_compilation_runner",
        "replay",
        "--output-dir",
        str(output_dir),
    )
    environment = {key: value for key, value in os.environ.items() if not _credential_like_key(key)}
    environment["CUDA_VISIBLE_DEVICES"] = ""
    completed = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
        env=environment,
        cwd=Path(__file__).resolve().parents[4],
    )
    if completed.returncode != 0:
        raise RuntimeError(
            "credential-free replay failed: "
            f"stdout={completed.stdout!r} stderr={completed.stderr!r}"
        )
    payload = json.loads(completed.stdout)
    if payload != {
        "ledger_id": ledger.ledger_id,
        "next_stage": "bridge_rollout",
        "model_api_calls": 0,
        "gpu_jobs": 0,
    }:
        raise ValueError("credential-free replay returned another stage identity")
    return V26CredentialFreeReplayObservation(
        command=command,
        credential_like_environment_key_count=0,
        cuda_visible_devices="",
        return_code=0,
        replayed_ledger_id=ledger.ledger_id,
        replayed_next_stage="bridge_rollout",
        model_api_calls=0,
        gpu_jobs=0,
    )


def _credential_like_key(key: str) -> bool:
    normalized = key.upper()
    return any(
        marker in normalized for marker in ("API_KEY", "TOKEN", "SECRET", "PASSWORD", "CREDENTIAL")
    )


def run_v26_no_api_compilation(
    *,
    run_id: str,
    protocol_path: Path,
    preflight_path: Path,
    archive_config_path: Path,
    development_source_population_path: Path,
    output_dir: Path,
) -> V26NoApiExperimentReport:
    if output_dir.exists():
        raise ValueError("v26 no-API experiment output is immutable")
    output_dir.mkdir(parents=True)
    protocol = CapabilityHeterogeneousMainlineProtocol.model_validate_json(
        protocol_path.read_text(encoding="utf-8")
    )
    preflight = MainlinePreflightReport.model_validate_json(
        preflight_path.read_text(encoding="utf-8")
    )
    if preflight.status != "passed" or preflight.protocol_id != protocol.protocol_id:
        raise ValueError("v26 no-API experiment requires a passing bound preflight")

    development_path = output_dir / "population" / "development.json"
    development = build_v26_fresh_task_population(
        protocol_id=protocol.protocol_id,
        phase="development",
        source_population_path=development_source_population_path,
        selection_salt=f"{run_id}:development",
        output_path=development_path,
    )
    development_tasks = load_v26_selected_source_tasks(development)
    excluded_evidence_ids = tuple(
        sorted(
            {
                evidence.evidence_id
                for task in development_tasks
                for evidence in task.public_corpus.evidence
            }
        )
    )
    source_payload = json.loads(development_source_population_path.read_text(encoding="utf-8"))
    source_artifacts_path = Path(source_payload["source_artifacts_path"])
    confirmation_source_path = output_dir / "population" / "confirmation_source.json"
    build_capability_sensitive_frontier_population(
        source_artifacts_path=source_artifacts_path,
        output_path=confirmation_source_path,
        run_id=f"{run_id}_fresh_confirmation_source",
        sampling_salt=f"{run_id}:fresh-confirmation-source",
        excluded_evidence_ids=excluded_evidence_ids,
    )
    confirmation_path = output_dir / "population" / "confirmation.json"
    confirmation = build_v26_fresh_task_population(
        protocol_id=protocol.protocol_id,
        phase="fresh_confirmation",
        source_population_path=confirmation_source_path,
        selection_salt=f"{run_id}:fresh-confirmation",
        output_path=confirmation_path,
    )
    freshness = build_v26_cross_population_freshness_audit(development, confirmation)
    replay_v26_cross_population_freshness_audit(freshness, development, confirmation)
    freshness_path = output_dir / "population" / "cross_population_freshness_audit.json"
    _write_json(freshness_path, freshness.model_dump(mode="json"))

    ledger = initialize_v26_stage_ledger(
        run_id=run_id,
        protocol_path=protocol_path,
        preflight_path=preflight_path,
    )
    ledger = _advance(
        ledger,
        stage="fresh_task_population",
        references=(_artifact_reference("fresh_task_population", development_path),),
        output_dir=output_dir,
    )

    compilation_contexts = _compile_development_tasks(
        development,
        archive_config_path=archive_config_path,
    )
    compiled_path = output_dir / "joint" / "compiled_proof_artifacts.json"
    states_path = output_dir / "joint" / "trajectory_state_spaces.json"
    _write_models(compiled_path, [item.compiled for item in compilation_contexts])
    _write_models(states_path, [item.state_space for item in compilation_contexts])
    ledger = _advance(
        ledger,
        stage="joint_compilation",
        references=(
            _artifact_reference("cross_population_freshness_audit", freshness_path),
            _artifact_reference("compiled_proof_artifacts", compiled_path),
            _artifact_reference("trajectory_state_space", states_path),
        ),
        output_dir=output_dir,
    )

    audits_by_joint: dict[str, tuple[JointCompilationAuditEvidence, ...]] = {}
    joint_audits: list[JointCompilationAuditEvidence] = []
    for context in compilation_contexts:
        audits = _compile_joint_audits(context)
        audits_by_joint[context.compiled.joint_compilation.artifact_id] = audits
        joint_audits.extend(audits)
    joint_audits_path = output_dir / "joint" / "joint_audit_evidence.json"
    _write_models(joint_audits_path, joint_audits)
    ledger = _advance(
        ledger,
        stage="joint_audit",
        references=(_artifact_reference("joint_audit_evidence", joint_audits_path),),
        output_dir=output_dir,
    )

    joint_admissions = tuple(
        _admit_joint_context(
            context,
            audits_by_joint[context.compiled.joint_compilation.artifact_id],
        )
        for context in compilation_contexts
    )
    joint_admissions_path = output_dir / "joint" / "joint_admissions.json"
    _write_models(joint_admissions_path, joint_admissions)
    ledger = _advance(
        ledger,
        stage="joint_admission",
        references=(_artifact_reference("joint_admission", joint_admissions_path),),
        output_dir=output_dir,
    )

    joint_by_id = {item.joint_compilation_id: item for item in joint_admissions}
    scaffold_contexts = tuple(
        _compile_scaffold_context(
            context,
            joint_by_id[context.compiled.joint_compilation.artifact_id],
        )
        for context in compilation_contexts
    )
    ladders = tuple(item.ladder for item in scaffold_contexts)
    ladders_path = output_dir / "scaffold" / "ladders.json"
    _write_models(ladders_path, ladders)
    ledger = _advance(
        ledger,
        stage="scaffold_compilation",
        references=(_artifact_reference("scaffold_ladder", ladders_path),),
        output_dir=output_dir,
    )

    evidence_by_ladder: dict[str, tuple[CapabilityScaffoldGateEvidence, ...]] = {}
    scaffold_evidence: list[CapabilityScaffoldGateEvidence] = []
    for scaffold_context in scaffold_contexts:
        evidence = _scaffold_gate_evidence(scaffold_context)
        evidence_by_ladder[scaffold_context.ladder.ladder_id] = evidence
        scaffold_evidence.extend(evidence)
    scaffold_evidence_path = output_dir / "scaffold" / "gate_evidence.json"
    _write_models(scaffold_evidence_path, scaffold_evidence)
    ledger = _advance(
        ledger,
        stage="scaffold_audit",
        references=(_artifact_reference("scaffold_gate_evidence", scaffold_evidence_path),),
        output_dir=output_dir,
    )

    scaffold_admissions = tuple(
        admit_capability_scaffold_ladder(
            scaffold_context.ladder,
            evidence_by_ladder[scaffold_context.ladder.ladder_id],
        )
        for scaffold_context in scaffold_contexts
    )
    if any(item.status != "admitted" for item in scaffold_admissions):
        blocked = {item.ladder_id: item.blockers for item in scaffold_admissions if item.blockers}
        raise ValueError(f"Scaffold Admission blocked: {blocked}")
    scaffold_admissions_path = output_dir / "scaffold" / "admissions.json"
    _write_models(scaffold_admissions_path, scaffold_admissions)
    ledger = _advance(
        ledger,
        stage="scaffold_admission",
        references=(_artifact_reference("scaffold_admission", scaffold_admissions_path),),
        output_dir=output_dir,
    )

    static_audits = _bridge_static_audits(
        protocol.capability_bridge,
        scaffold_contexts,
        scaffold_admissions,
    )
    static_audits_path = output_dir / "bridge" / "static_construct_audits.json"
    _write_models(static_audits_path, static_audits)
    authorization = authorize_bridge_development(protocol.capability_bridge, static_audits)
    if authorization.status != "authorized":
        raise ValueError(f"Bridge Development blocked: {authorization.blockers}")
    authorization_path = output_dir / "bridge" / "development_authorization.json"
    _write_json(authorization_path, authorization.model_dump(mode="json"))
    ledger = _advance(
        ledger,
        stage="bridge_development_authorization",
        references=(_artifact_reference("bridge_development_authorization", authorization_path),),
        output_dir=output_dir,
    )
    if ledger.next_stage != "bridge_rollout" or ledger.model_api_call_count or ledger.gpu_job_count:
        raise ValueError("v26 no-API run crossed its authorization boundary")
    final_ledger_path = output_dir / "finance_v26_stage_ledger.json"
    write_v26_stage_ledger(ledger, final_ledger_path)
    replay = _run_credential_free_replay(output_dir, ledger)

    artifact_files = tuple(
        sorted(
            (path for path in output_dir.rglob("*.json") if path.name != "report.json"),
            key=lambda path: str(path.relative_to(output_dir)),
        )
    )
    immutable_files = tuple(_immutable_file(path, output_dir) for path in artifact_files)
    accounting = _artifact_accounting(output_dir)
    values = {
        "run_id": run_id,
        "protocol_id": protocol.protocol_id,
        "development_population_id": development.population_id,
        "confirmation_population_id": confirmation.population_id,
        "freshness_audit_id": freshness.audit_id,
        "freshness_overlap_count_by_channel": {
            item.channel: item.overlap_count for item in freshness.channels
        },
        **accounting,
        "bridge_development_authorization_id": authorization.authorization_id,
        "final_ledger_id": ledger.ledger_id,
        "completed_stages": ledger.completed_stages,
        "next_stage": "bridge_rollout",
        "credential_free_replay": replay,
        "immutable_files": immutable_files,
        "model_api_calls": 0,
        "gpu_jobs": 0,
        "status": "passed",
    }
    provisional = V26NoApiExperimentReport.model_construct(report_id="pending", **values)
    report = V26NoApiExperimentReport(
        report_id=v26_no_api_experiment_report_id(provisional),
        **values,
    )
    _write_json(output_dir / "report.json", report.model_dump(mode="json"))
    return report


def replay_v26_no_api_compilation(output_dir: Path) -> V26StageLedger:
    output_dir = output_dir.resolve()
    ledger = load_v26_stage_ledger(output_dir / "finance_v26_stage_ledger.json")
    replay_v26_stage_ledger(ledger)
    if (
        ledger.next_stage != "bridge_rollout"
        or ledger.model_api_call_count != 0
        or ledger.gpu_job_count != 0
    ):
        raise ValueError("v26 credential-free replay crossed the frozen boundary")
    freshness_payload = json.loads(
        (output_dir / "population" / "cross_population_freshness_audit.json").read_text(
            encoding="utf-8"
        )
    )
    freshness = V26CrossPopulationFreshnessAudit.model_validate(freshness_payload)
    development = V26FreshTaskPopulation.model_validate_json(
        (output_dir / "population" / "development.json").read_text(encoding="utf-8")
    )
    confirmation = V26FreshTaskPopulation.model_validate_json(
        (output_dir / "population" / "confirmation.json").read_text(encoding="utf-8")
    )
    replay_v26_cross_population_freshness_audit(
        freshness,
        development,
        confirmation,
    )
    if (output_dir / "report.json").exists():
        report = V26NoApiExperimentReport.model_validate_json(
            (output_dir / "report.json").read_text(encoding="utf-8")
        )
        if report.final_ledger_id != ledger.ledger_id:
            raise ValueError("v26 report and replayed Ledger identities differ")
        accounting = _artifact_accounting(output_dir)
        for field, observed in accounting.items():
            if getattr(report, field) != observed:
                raise ValueError(f"v26 report accounting differs for {field}")
        actual_paths = tuple(
            sorted(
                str(path.relative_to(output_dir))
                for path in output_dir.rglob("*.json")
                if path.name != "report.json"
            )
        )
        reported_paths = tuple(sorted(item.relative_path for item in report.immutable_files))
        if reported_paths != actual_paths:
            raise ValueError("v26 report immutable file coverage is incomplete")
        for item in report.immutable_files:
            path = output_dir / item.relative_path
            if (
                not path.is_file()
                or path.stat().st_size != item.byte_count
                or _sha256(path) != item.sha256
            ):
                raise ValueError(f"v26 immutable file replay failed: {item.relative_path}")
    return ledger


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the v26 credential-free Joint/Scaffold chain")
    subparsers = parser.add_subparsers(dest="command", required=True)
    run = subparsers.add_parser("run")
    run.add_argument("--run-id", required=True)
    run.add_argument("--protocol", type=Path, required=True)
    run.add_argument("--preflight", type=Path, required=True)
    run.add_argument("--archive-config", type=Path, required=True)
    run.add_argument("--development-source-population", type=Path, required=True)
    run.add_argument("--output-dir", type=Path, required=True)
    replay = subparsers.add_parser("replay")
    replay.add_argument("--output-dir", type=Path, required=True)
    return parser


def main() -> None:
    args = _parser().parse_args()
    if args.command == "run":
        report = run_v26_no_api_compilation(
            run_id=args.run_id,
            protocol_path=args.protocol,
            preflight_path=args.preflight,
            archive_config_path=args.archive_config,
            development_source_population_path=args.development_source_population,
            output_dir=args.output_dir,
        )
        print(report.model_dump_json(indent=2))
        return
    ledger = replay_v26_no_api_compilation(args.output_dir)
    print(
        json.dumps(
            {
                "ledger_id": ledger.ledger_id,
                "next_stage": ledger.next_stage,
                "model_api_calls": ledger.model_api_call_count,
                "gpu_jobs": ledger.gpu_job_count,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
