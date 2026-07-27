from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from trusted_synthesis.core.evidence.schema import EvidenceBundle, EvidenceItem
from trusted_synthesis.core.graph.schema import ProofGraph
from trusted_synthesis.core.operations.registry import OperationRegistry
from trusted_synthesis.core.plugins import TaskPatternRuntimeProtocol
from trusted_synthesis.core.task.binding import EvidenceBinding
from trusted_synthesis.core.task.builder import TaskPackageBuilder
from trusted_synthesis.core.task.difficulty import (
    TaskDifficultyProfile,
    assess_task_difficulty,
)
from trusted_synthesis.core.task.pattern import (
    PatternBindingValidationReport,
    PatternInputKind,
    ProgramNodeTemplate,
    TaskPatternSpec,
)
from trusted_synthesis.core.task.program import (
    InputRefKind,
    OperationNode,
    ProgramInputRef,
    TaskProgram,
    make_program,
)
from trusted_synthesis.core.task.schema import TaskPackage

TASK_PATTERN_COMPILER_VERSION = "task_pattern_compiler.v1"


class TaskPatternInstantiation(BaseModel):
    """Private compilation artifact that binds Pattern, Binding, Program, and Task."""

    model_config = ConfigDict(frozen=True, extra="forbid", arbitrary_types_allowed=True)

    pattern: TaskPatternSpec
    binding: EvidenceBinding
    validation_report: PatternBindingValidationReport
    program: TaskProgram
    task: TaskPackage
    difficulty_profile: TaskDifficultyProfile
    concrete_node_roles: dict[str, tuple[str, ...]]
    compiler_version: str = TASK_PATTERN_COMPILER_VERSION


class TaskPatternCompiler:
    """Compile immutable domain declarations and bindings into universal task packages."""

    def __init__(
        self,
        operation_registry: OperationRegistry,
        runtime: TaskPatternRuntimeProtocol,
    ) -> None:
        self._operation_registry = operation_registry
        self._runtime = runtime
        self._package_builder = TaskPackageBuilder(operation_registry)

    def compile(
        self,
        pattern: TaskPatternSpec,
        binding: EvidenceBinding,
        bundle: EvidenceBundle,
        proof_graph: ProofGraph,
    ) -> TaskPatternInstantiation:
        evidence_by_role = _validate_and_resolve_binding(
            pattern,
            binding,
            bundle,
            proof_graph,
        )
        if self._runtime.domain != pattern.domain:
            raise ValueError("task pattern runtime domain does not match the pattern")
        if pattern.instruction_renderer_id not in self._runtime.renderer_ids:
            raise ValueError(
                "task pattern renderer is not registered by its runtime: "
                f"{pattern.instruction_renderer_id}"
            )
        report = self._runtime.validate_binding(pattern, binding, evidence_by_role)
        if not report.passed:
            raise ValueError(
                "task pattern binding failed domain semantics: " + ", ".join(report.issues)
            )
        program, concrete_node_roles = _instantiate_program(
            pattern,
            binding,
            self._operation_registry,
        )
        materialized = self._runtime.materialize(
            pattern,
            binding,
            evidence_by_role,
            bundle,
            proof_graph,
        )
        answer_schema = _merge_answer_schema(
            pattern.answer_schema,
            materialized.answer_schema,
        )
        evidence = tuple(
            item for role in pattern.evidence_roles for item in evidence_by_role[role.role_id]
        )
        difficulty = assess_task_difficulty(
            pattern=pattern,
            program=program,
            proof_graph=proof_graph,
            evidence_ids=tuple(item.evidence_id for item in evidence),
            semantic_alignment_cost=report.semantic_alignment_cost,
        )
        pattern_identity = {
            "pattern_id": pattern.pattern_id,
            "pattern_version": pattern.pattern_version,
            "pattern_hash": pattern.pattern_hash,
            "schema_version": pattern.schema_version,
            "compiler_version": TASK_PATTERN_COMPILER_VERSION,
            "runtime_id": self._runtime.runtime_id,
            "runtime_version": self._runtime.runtime_version,
            "quality_profile_id": pattern.quality_profile_id,
            "difficulty_base": pattern.difficulty_base,
            "difficulty_base_cost": pattern.difficulty_base_cost,
            "semantic_constraint_count": pattern.semantic_constraint_count,
        }
        binding_identity = {
            "binding_id": binding.binding_id,
            "binding_hash": binding.binding_hash,
            "role_bindings": binding.role_bindings,
            "source_graph_id": binding.source_graph_id,
            "domain_snapshot_id": binding.domain_snapshot_id,
            "schema_version": binding.schema_version,
        }
        task = self._package_builder.build(
            task_domain=pattern.domain,
            task_type=pattern.task_type,
            level=pattern.level,
            instruction=materialized.instruction,
            evidence=evidence,
            bundle=bundle,
            proof_graph=proof_graph,
            program=program,
            answer_schema=answer_schema,
            retrieval_scope=materialized.retrieval_scope,
            retrieval_track=pattern.retrieval_track,
            planning_track=pattern.planning_track,
            oracle_selection_contract={
                **materialized.oracle_selection_contract,
                "pattern_binding": binding_identity,
            },
            source_grounding_requirement=pattern.source_grounding_requirement,
            allow_structured_claims=pattern.allow_structured_claims,
            metadata={
                **pattern.metadata,
                **materialized.metadata,
                "task_pattern": pattern_identity,
                "difficulty_profile": difficulty.model_dump(mode="json"),
            },
            quality_rubric=materialized.quality_rubric or None,
            identity_context={
                "task_pattern_hash": pattern.pattern_hash,
                "evidence_binding_hash": binding.binding_hash,
                "task_pattern_compiler_version": TASK_PATTERN_COMPILER_VERSION,
            },
        )
        return TaskPatternInstantiation(
            pattern=pattern,
            binding=binding,
            validation_report=report,
            program=program,
            task=task,
            difficulty_profile=difficulty,
            concrete_node_roles=concrete_node_roles,
        )


def _merge_answer_schema(
    declared: dict[str, object],
    materialized: dict[str, object],
) -> dict[str, object]:
    conflicts = sorted(
        key for key in set(declared) & set(materialized) if declared[key] != materialized[key]
    )
    if conflicts:
        raise ValueError(
            "task pattern runtime conflicts with the declared answer schema: "
            + ", ".join(conflicts)
        )
    return {**declared, **materialized}


def _validate_and_resolve_binding(
    pattern: TaskPatternSpec,
    binding: EvidenceBinding,
    bundle: EvidenceBundle,
    proof_graph: ProofGraph,
) -> dict[str, tuple[EvidenceItem, ...]]:
    expected_identity = (
        pattern.pattern_id,
        pattern.pattern_version,
        pattern.pattern_hash,
    )
    observed_identity = (
        binding.pattern_id,
        binding.pattern_version,
        binding.pattern_hash,
    )
    if observed_identity != expected_identity:
        raise ValueError("evidence binding does not target this exact task pattern")
    if binding.source_graph_id != proof_graph.graph_id:
        raise ValueError("evidence binding is not pinned to the supplied proof graph")
    role_specs = {role.role_id: role for role in pattern.evidence_roles}
    if set(binding.role_bindings) != set(role_specs):
        missing = sorted(set(role_specs) - set(binding.role_bindings))
        extra = sorted(set(binding.role_bindings) - set(role_specs))
        raise ValueError(f"evidence binding role mismatch: missing={missing}, extra={extra}")
    bundle_by_id = {item.evidence_id: item for item in bundle.evidence}
    resolved: dict[str, tuple[EvidenceItem, ...]] = {}
    all_ids: list[str] = []
    for role in pattern.evidence_roles:
        evidence_ids = binding.role_bindings[role.role_id]
        if len(evidence_ids) < role.min_count:
            raise ValueError(f"evidence role under minimum cardinality: {role.role_id}")
        if role.max_count is not None and len(evidence_ids) > role.max_count:
            raise ValueError(f"evidence role exceeds maximum cardinality: {role.role_id}")
        missing_ids = [
            evidence_id for evidence_id in evidence_ids if evidence_id not in bundle_by_id
        ]
        if missing_ids:
            raise ValueError(f"evidence role references unknown bundle evidence: {missing_ids}")
        items = tuple(bundle_by_id[evidence_id] for evidence_id in evidence_ids)
        invalid_kinds = [
            item.evidence_id for item in items if item.evidence_kind not in role.accepted_kinds
        ]
        if invalid_kinds:
            raise ValueError(f"evidence role kind mismatch for {role.role_id}: {invalid_kinds}")
        invalid_domains = [item.evidence_id for item in items if item.domain != pattern.domain]
        if invalid_domains:
            raise ValueError(
                "task evidence domains must exactly match task_domain; "
                f"role={role.role_id}, evidence={invalid_domains}"
            )
        resolved[role.role_id] = items
        all_ids.extend(evidence_ids)
    if not pattern.allow_shared_evidence and len(all_ids) != len(set(all_ids)):
        raise ValueError("task pattern binding reuses evidence across roles")
    missing_graph = [
        evidence_id for evidence_id in all_ids if not proof_graph.contains_evidence(evidence_id)
    ]
    if missing_graph:
        raise ValueError(f"bound evidence is absent from the proof graph: {missing_graph}")
    return resolved


def _instantiate_program(
    pattern: TaskPatternSpec,
    binding: EvidenceBinding,
    registry: OperationRegistry,
) -> tuple[TaskProgram, dict[str, tuple[str, ...]]]:
    nodes: list[OperationNode] = []
    generated_by_role: dict[str, tuple[str, ...]] = {}
    for template in pattern.program_template:
        current_evidence_ids: tuple[str | None, ...]
        if template.foreach_evidence_role is None:
            current_evidence_ids = (None,)
        else:
            current_evidence_ids = binding.role_bindings[template.foreach_evidence_role]
        generated_ids: list[str] = []
        for index, current_evidence_id in enumerate(current_evidence_ids, start=1):
            node_id = (
                template.node_role_id
                if template.foreach_evidence_role is None
                else f"{template.node_role_id}_{index}"
            )
            definition = registry.require(template.operator_id)
            if template.output_schema != definition.output_schema:
                raise ValueError(
                    "task pattern output schema disagrees with the operation registry: "
                    f"{template.node_role_id}"
                )
            input_refs = _resolve_template_inputs(
                template,
                binding,
                generated_by_role,
                current_evidence_id,
            )
            dependencies = tuple(
                dict.fromkeys(
                    ref.ref_id for ref in input_refs if ref.kind == InputRefKind.OPERATION
                )
            )
            parameters = {
                **template.parameters,
                **binding.node_parameters.get(template.node_role_id, {}),
                **binding.node_parameters.get(node_id, {}),
            }
            node = OperationNode(
                node_id=node_id,
                operator_id=template.operator_id,
                input_refs=input_refs,
                parameters=parameters,
                output_schema=definition.output_schema,
                verifier_id=definition.verifier_id,
                dependencies=dependencies,
            )
            registry.validate_node_contract(node)
            nodes.append(node)
            generated_ids.append(node_id)
        generated_by_role[template.node_role_id] = tuple(generated_ids)
    output_ids = generated_by_role[pattern.output_node_role_id]
    if len(output_ids) != 1:
        raise ValueError("task pattern output role did not compile to one node")
    return make_program(tuple(nodes), output_ids[0]), generated_by_role


def _resolve_template_inputs(
    template: ProgramNodeTemplate,
    binding: EvidenceBinding,
    generated_by_role: dict[str, tuple[str, ...]],
    current_evidence_id: str | None,
) -> tuple[ProgramInputRef, ...]:
    concrete: list[ProgramInputRef] = []
    for ref in template.input_refs:
        if ref.kind == PatternInputKind.EVIDENCE_ROLE:
            concrete.extend(
                ProgramInputRef(
                    kind=InputRefKind.EVIDENCE,
                    ref_id=evidence_id,
                    selector=ref.selector,
                )
                for evidence_id in binding.role_bindings[ref.ref_id]
            )
        elif ref.kind == PatternInputKind.CURRENT_EVIDENCE:
            if current_evidence_id is None:
                raise ValueError("current evidence input has no foreach binding")
            concrete.append(
                ProgramInputRef(
                    kind=InputRefKind.EVIDENCE,
                    ref_id=current_evidence_id,
                    selector=ref.selector,
                )
            )
        else:
            operation_ids = generated_by_role[ref.ref_id]
            if ref.kind == PatternInputKind.OPERATION_NODE and len(operation_ids) != 1:
                raise ValueError("operation_node reference resolved to multiple nodes")
            concrete.extend(
                ProgramInputRef(
                    kind=InputRefKind.OPERATION,
                    ref_id=operation_id,
                    selector=ref.selector,
                )
                for operation_id in operation_ids
            )
    return tuple(concrete)
