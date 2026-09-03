from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.core.evaluation.answer import CandidateAnswerNormalizer
from trusted_synthesis.core.evidence.corpus import EvidenceCorpus
from trusted_synthesis.core.evidence.schema import EvidenceItem
from trusted_synthesis.core.operations.program import (
    ProgramExecution,
    ProgramVerification,
    TaskProgramExecutor,
    TaskProgramOracleVerifier,
)
from trusted_synthesis.core.operations.registry import (
    OperationRegistry,
    operation_semantic_contract_hash,
)
from trusted_synthesis.core.task.answer_schema import required_answer_fields
from trusted_synthesis.core.task.program import (
    InputRefKind,
    OperationNode,
    ProgramInputRef,
    TaskProgram,
    make_program,
)
from trusted_synthesis.core.task.realization import RealizedTaskPackage
from trusted_synthesis.core.task.schema import PublicProgramNode, TaskRequirement
from trusted_synthesis.core.task.semantic import CanonicalProgramInput, CanonicalProgramNode
from trusted_synthesis.core.trajectory.schema import (
    ActionType,
    StepStatus,
    Trajectory,
    TrajectoryStep,
    WorkflowKind,
)
from trusted_synthesis.hashing import canonical_hash

PUBLIC_PLAN_CANDIDATE_EXECUTOR_VERSION = "public_plan_candidate_executor.v1"
PUBLIC_PLAN_CANDIDATE_EXECUTOR_CONTRACT_ID = canonical_hash(
    {
        "implementation": "PublicPlanCandidateExecutor",
        "inputs": (
            "RealizedTaskPackage",
            "CanonicalSemanticPlan",
            "BindingSnapshot",
            "EvidenceCorpus",
            "OperationRegistry",
        ),
        "authority": "public_plan_and_exact_binding_only",
        "node_execution": "registry_topological_complete",
        "oracle_use": "independent_post_execution_verifier_only",
        "task_type_specific_branch_count": 0,
        "version": PUBLIC_PLAN_CANDIDATE_EXECUTOR_VERSION,
    },
    prefix="public_plan_candidate_executor_contract:",
)


class PublicPlanCandidateExecution(BaseModel):
    """One complete public-plan execution and its independent node replay."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    execution_id: str = Field(min_length=1)
    realized_package_id: str = Field(min_length=1)
    semantic_plan_id: str = Field(min_length=1)
    binding_snapshot_id: str = Field(min_length=1)
    corpus_id: str = Field(min_length=1)
    executor_contract_id: str = PUBLIC_PLAN_CANDIDATE_EXECUTOR_CONTRACT_ID
    public_role_bindings: dict[str, str] = Field(min_length=1)
    public_to_canonical_node_keys: dict[str, str] = Field(min_length=1)
    reconstructed_program: TaskProgram
    program_execution: ProgramExecution
    independent_verification: ProgramVerification
    trajectory: Trajectory
    actual_node_count: int = Field(ge=1)
    actual_edge_count: int = Field(ge=0)
    maximum_dependency_depth: int = Field(ge=1)
    independently_replayed_node_count: int = Field(ge=1)
    gates: dict[str, bool]
    schema_version: str = "public_plan_candidate_execution.v1"

    @model_validator(mode="after")
    def validate_execution(self) -> PublicPlanCandidateExecution:
        if any(not value for value in self.gates.values()):
            raise ValueError("public Plan candidate execution failed a hard Gate")
        if self.executor_contract_id != PUBLIC_PLAN_CANDIDATE_EXECUTOR_CONTRACT_ID:
            raise ValueError("public Plan executor Contract identity differs")
        if (
            self.program_execution.program_id != self.reconstructed_program.program_id
            or self.independent_verification.program_id != self.reconstructed_program.program_id
            or self.trajectory.task_id == ""
            or self.trajectory.program_execution != self.program_execution.model_dump(mode="json")
        ):
            raise ValueError("public Plan execution object lineage differs")
        if self.actual_node_count != len(self.reconstructed_program.nodes):
            raise ValueError("public Plan execution node count is not derived")
        if self.actual_edge_count != sum(
            len(node.dependencies) for node in self.reconstructed_program.nodes
        ):
            raise ValueError("public Plan execution edge count is not derived")
        if self.independently_replayed_node_count != sum(
            self.independent_verification.node_statuses.values()
        ):
            raise ValueError("public Plan replay count is not derived")
        if self.maximum_dependency_depth != _maximum_dependency_depth(self.reconstructed_program):
            raise ValueError("public Plan dependency depth is not derived")
        expected = canonical_hash(
            self.model_dump(mode="json", exclude={"execution_id"}),
            prefix="public_plan_candidate_execution:",
        )
        if self.execution_id != expected:
            raise ValueError("public Plan candidate execution identity is invalid")
        return self


class PublicPlanCandidateExecutor:
    """Execute every public Program node without consulting a hidden Oracle Program."""

    def __init__(self, registry: OperationRegistry) -> None:
        self._registry = registry
        self._executor = TaskProgramExecutor(registry)
        self._verifier = TaskProgramOracleVerifier(registry)
        self._answer_normalizer = CandidateAnswerNormalizer()

    def generate(
        self,
        realized: RealizedTaskPackage,
        corpus: EvidenceCorpus,
    ) -> PublicPlanCandidateExecution:
        public = realized.task.public
        skeleton = public.program_skeleton
        if skeleton is None:
            raise ValueError("public Plan executor requires a plan-given Program skeleton")
        bound_evidence = _validate_bound_evidence(realized, corpus)
        public_roles = _resolve_public_roles(skeleton.nodes, bound_evidence)
        reconstructed = _reconstruct_program(
            skeleton.nodes,
            skeleton.output_node_id,
            public_roles,
            self._registry,
        )
        if (
            reconstructed.program_id != realized.semantic_plan.source_program_id
            or reconstructed.program_hash != realized.semantic_plan.source_program_hash
        ):
            raise ValueError("public Program reconstruction differs from the semantic Plan source")
        canonical_nodes = _map_canonical_nodes(realized, reconstructed, self._registry)
        execution = self._executor.execute(reconstructed, bound_evidence)
        verification = self._verifier.verify(
            reconstructed,
            bound_evidence,
            execution.node_outputs,
        )
        if not verification.passed:
            raise ValueError("independent nodewise Oracle replay rejected public execution")
        final_result = _project_public_result(
            public.answer_schema,
            execution,
            bound_evidence,
            realized.binding_snapshot.role_bindings,
        )
        normalized_result = self._answer_normalizer.normalize_result(public, final_result)
        citations = [
            {
                "evidence_id": evidence_id,
                "source_id": bound_evidence[evidence_id].source.source_id,
                "source_locator": bound_evidence[evidence_id].source_locator.model_dump(
                    mode="json", exclude_none=True
                ),
            }
            for evidence_id in realized.binding_snapshot.evidence_ids
        ]
        steps = _trajectory_steps(
            realized,
            reconstructed,
            execution,
            verification,
            normalized_result,
            citations,
            self._registry,
        )
        trajectory_payload = {
            "task_id": public.task_id,
            "workflow_kind": WorkflowKind.CANDIDATE,
            "steps": steps,
            "program_execution": execution.model_dump(mode="json"),
            "final_answer": {"result": normalized_result, "citations": citations},
            "generator_version": PUBLIC_PLAN_CANDIDATE_EXECUTOR_VERSION,
        }
        trajectory = Trajectory(
            trajectory_id=canonical_hash(
                {
                    "realized_package_id": realized.realized_package_id,
                    "semantic_plan_id": realized.semantic_plan.plan_id,
                    "binding_snapshot_id": realized.binding_snapshot.binding_snapshot_id,
                    "corpus_hash": corpus.corpus_hash,
                    "program_execution": execution,
                    "independent_verification": verification,
                    "version": PUBLIC_PLAN_CANDIDATE_EXECUTOR_VERSION,
                },
                prefix="public_plan_candidate_trajectory:",
            ),
            **trajectory_payload,
        )
        node_count = len(reconstructed.nodes)
        edge_count = sum(len(node.dependencies) for node in reconstructed.nodes)
        depth = _maximum_dependency_depth(reconstructed)
        replayed = sum(verification.node_statuses.values())
        mapped_plan_keys = tuple(canonical_nodes.values())
        gates = {
            "binding_snapshot_evidence_exact": set(bound_evidence)
            == set(realized.binding_snapshot.evidence_ids),
            "public_role_binding_total": set(public_roles)
            == {
                item.role_id
                for node in skeleton.nodes
                for item in node.inputs
                if item.kind == InputRefKind.EVIDENCE
            },
            "source_program_identity_exact": (
                reconstructed.program_id == realized.semantic_plan.source_program_id
                and reconstructed.program_hash == realized.semantic_plan.source_program_hash
            ),
            "actual_nodes_equal_plan_nodes": (
                node_count == len(realized.semantic_plan.nodes)
                and len(mapped_plan_keys) == len(set(mapped_plan_keys))
                and set(mapped_plan_keys)
                == {node.node_key for node in realized.semantic_plan.nodes}
            ),
            "actual_edges_equal_plan_edges": edge_count
            == sum(
                item.kind == "operation"
                for node in realized.semantic_plan.nodes
                for item in node.inputs
            ),
            "program_execution_non_null": bool(execution.node_outputs),
            "every_node_independently_replayed": replayed == node_count,
            "independent_replay_passed": verification.passed,
            "trajectory_program_execution_bound": trajectory.program_execution
            == execution.model_dump(mode="json"),
            "task_type_specific_result_branch_zero": True,
        }
        payload = {
            "realized_package_id": realized.realized_package_id,
            "semantic_plan_id": realized.semantic_plan.plan_id,
            "binding_snapshot_id": realized.binding_snapshot.binding_snapshot_id,
            "corpus_id": corpus.corpus_id,
            "executor_contract_id": PUBLIC_PLAN_CANDIDATE_EXECUTOR_CONTRACT_ID,
            "public_role_bindings": dict(sorted(public_roles.items())),
            "public_to_canonical_node_keys": dict(sorted(canonical_nodes.items())),
            "reconstructed_program": reconstructed,
            "program_execution": execution,
            "independent_verification": verification,
            "trajectory": trajectory,
            "actual_node_count": node_count,
            "actual_edge_count": edge_count,
            "maximum_dependency_depth": depth,
            "independently_replayed_node_count": replayed,
            "gates": gates,
            "schema_version": "public_plan_candidate_execution.v1",
        }
        draft = PublicPlanCandidateExecution.model_construct(execution_id="pending", **payload)
        return PublicPlanCandidateExecution(
            execution_id=canonical_hash(
                draft.model_dump(mode="json", exclude={"execution_id"}),
                prefix="public_plan_candidate_execution:",
            ),
            **payload,
        )


def _validate_bound_evidence(
    realized: RealizedTaskPackage,
    corpus: EvidenceCorpus,
) -> dict[str, EvidenceItem]:
    by_id = corpus.by_id()
    snapshot = realized.binding_snapshot
    try:
        evidence = tuple(by_id[evidence_id] for evidence_id in snapshot.evidence_ids)
    except KeyError as exc:
        raise ValueError(f"BindingSnapshot evidence is absent from Corpus: {exc.args[0]}") from exc
    if tuple(item.evidence_version_id for item in evidence) != snapshot.evidence_version_ids:
        raise ValueError("Corpus evidence versions differ from BindingSnapshot")
    if tuple(item.provenance.source_record_id for item in evidence) != snapshot.source_record_ids:
        raise ValueError("Corpus source records differ from BindingSnapshot")
    return {item.evidence_id: item for item in evidence}


def _resolve_public_roles(
    nodes: tuple[PublicProgramNode, ...],
    evidence_by_id: Mapping[str, EvidenceItem],
) -> dict[str, str]:
    resolved: dict[str, str] = {}
    for node in nodes:
        for item in node.inputs:
            if item.kind != InputRefKind.EVIDENCE:
                continue
            matches = tuple(
                evidence_id
                for evidence_id, evidence in evidence_by_id.items()
                if _matches_public_constraints(evidence, item.semantic_constraints)
            )
            if len(matches) != 1:
                raise ValueError(
                    f"public evidence role {item.role_id} resolved to {len(matches)} rows"
                )
            previous = resolved.setdefault(item.role_id, matches[0])
            if previous != matches[0]:
                raise ValueError("public evidence role resolution is inconsistent")
    if set(resolved.values()) != set(evidence_by_id):
        raise ValueError("public role binding does not cover the exact BindingSnapshot")
    return resolved


def _matches_public_constraints(item: EvidenceItem, constraints: Mapping[str, Any]) -> bool:
    observed = {
        "subject_id": item.subject.subject_id,
        "predicate": item.predicate,
        "temporal_label": item.temporal_context.label,
        "time_basis": item.temporal_context.basis,
        "frequency": item.temporal_context.frequency,
        "definition_id": item.definition.definition_id,
        "scope_type": item.scope.scope_type if item.scope is not None else None,
        "scope_id": item.scope.scope_id if item.scope is not None else None,
        "source_name": item.source.name,
        "source_authority": item.source.authority.value,
        "epistemic_status": item.epistemic_status.value,
    }
    return all(observed.get(str(key)) == value for key, value in constraints.items())


def _reconstruct_program(
    nodes: tuple[PublicProgramNode, ...],
    output_node_id: str,
    role_bindings: Mapping[str, str],
    registry: OperationRegistry,
) -> TaskProgram:
    concrete: list[OperationNode] = []
    for node in nodes:
        refs = tuple(
            ProgramInputRef(
                kind=item.kind,
                ref_id=(
                    role_bindings[item.role_id]
                    if item.kind == InputRefKind.EVIDENCE
                    else item.role_id
                ),
                selector=item.selector,
            )
            for item in node.inputs
        )
        definition = registry.require(node.operator_id)
        dependencies = tuple(
            dict.fromkeys(ref.ref_id for ref in refs if ref.kind == InputRefKind.OPERATION)
        )
        if dependencies != node.dependencies:
            raise ValueError("public Program dependencies disagree with input references")
        if node.output_schema != definition.output_schema:
            raise ValueError("public Program output schema differs from Operation Registry")
        if node.tool_capability != definition.tool_capability:
            raise ValueError("public Program tool capability differs from Operation Registry")
        concrete_node = OperationNode(
            node_id=node.public_node_id,
            operator_id=node.operator_id,
            input_refs=refs,
            parameters=node.parameters,
            output_schema=definition.output_schema,
            verifier_id=definition.verifier_id,
            dependencies=dependencies,
        )
        registry.validate_node_contract(concrete_node)
        concrete.append(concrete_node)
    return make_program(tuple(concrete), output_node_id)


def _canonical_inputs_for_node(
    realized: RealizedTaskPackage,
    node: OperationNode,
    mapped: Mapping[str, CanonicalProgramNode],
    registry: OperationRegistry,
) -> tuple[CanonicalProgramInput, ...]:
    role_by_evidence = {
        evidence_id: (role_id, position)
        for role_id, evidence_ids in realized.binding_snapshot.role_bindings.items()
        for position, evidence_id in enumerate(evidence_ids)
    }
    inputs = []
    for ref in node.input_refs:
        if ref.kind == InputRefKind.EVIDENCE:
            try:
                role_id, position = role_by_evidence[ref.ref_id]
            except KeyError as exc:
                raise ValueError(
                    f"Program evidence is absent from BindingSnapshot roles: {ref.ref_id}"
                ) from exc
            inputs.append(
                CanonicalProgramInput(
                    kind="evidence_role",
                    role_id=role_id,
                    role_position=position,
                    selector=ref.selector,
                )
            )
        else:
            try:
                parent = mapped[ref.ref_id]
            except KeyError as exc:
                raise ValueError(
                    f"Program dependency is not topologically available: {ref.ref_id}"
                ) from exc
            inputs.append(
                CanonicalProgramInput(
                    kind="operation",
                    operation_key=parent.node_key,
                    operation_topology_key=parent.topology_node_key,
                    selector=ref.selector,
                )
            )
    if registry.require(node.operator_id).input_order_policy == "permutation_invariant":
        inputs.sort(key=canonical_hash)
    return tuple(inputs)


def _map_canonical_nodes(
    realized: RealizedTaskPackage,
    program: TaskProgram,
    registry: OperationRegistry,
) -> dict[str, str]:
    plan_nodes = realized.semantic_plan.nodes
    if len(plan_nodes) != len(program.nodes):
        raise ValueError("public Program and CanonicalSemanticPlan node counts differ")
    mapped_models: dict[str, CanonicalProgramNode] = {}
    result: dict[str, str] = {}
    for node in program.nodes:
        definition = registry.require(node.operator_id)
        inputs = _canonical_inputs_for_node(realized, node, mapped_models, registry)
        matches = tuple(
            candidate
            for candidate in plan_nodes
            if candidate.node_key not in result.values()
            and candidate.operator_id == node.operator_id
            and candidate.inputs == inputs
            and candidate.parameters == node.parameters
            and candidate.output_schema == node.output_schema
            and candidate.verifier_id == node.verifier_id
            and candidate.input_order_policy == definition.input_order_policy
            and candidate.tool_capability == definition.tool_capability
            and candidate.operation_semantic_contract_hash
            == operation_semantic_contract_hash(definition)
            and candidate.operation_implementation_hash == definition.implementation_hash
        )
        if len(matches) != 1:
            raise ValueError(
                f"public Program node {node.node_id} maps to {len(matches)} canonical Plan nodes"
            )
        mapped_models[node.node_id] = matches[0]
        result[node.node_id] = matches[0].node_key
    if mapped_models[program.output_node_id].node_key != realized.semantic_plan.output_node_key:
        raise ValueError("public Program output differs from CanonicalSemanticPlan output")
    return result


def _project_public_result(
    answer_schema: Mapping[str, Any],
    execution: ProgramExecution,
    evidence_by_id: Mapping[str, EvidenceItem],
    role_bindings: Mapping[str, tuple[str, ...]],
) -> dict[str, Any]:
    projection = answer_schema.get("result_projection")
    result = dict(execution.final_output)
    if isinstance(projection, Mapping):
        if projection.get("mode") == "replace":
            result = {}
        fields = projection.get("fields")
        if not isinstance(fields, Mapping):
            raise ValueError("public result projection has no field map")
        for field, spec in fields.items():
            if not isinstance(spec, Mapping):
                raise ValueError("public result projection field is not an object")
            result[str(field)] = _resolve_projection_spec(
                spec,
                execution,
                evidence_by_id,
                role_bindings,
            )
    for field in required_answer_fields(dict(answer_schema)):
        if field not in result and field in answer_schema:
            result[field] = answer_schema[field]
    return result


def _resolve_projection_spec(
    spec: Mapping[str, Any],
    execution: ProgramExecution,
    evidence_by_id: Mapping[str, EvidenceItem],
    role_bindings: Mapping[str, tuple[str, ...]],
) -> Any:
    kind = spec.get("kind")
    if kind == "literal":
        return spec.get("value")
    if kind == "node_output":
        value: Any = execution.node_outputs[str(spec["node_id"])]
        return _select_projection_value(value, spec.get("selector"))
    if kind == "evidence_role":
        evidence_id = role_bindings[str(spec["role_id"])][int(spec.get("role_position", 0))]
        return _select_projection_value(evidence_by_id[evidence_id], spec.get("selector"))
    if kind == "operation_reference_choice":
        observed = _select_projection_value(
            execution.node_outputs[str(spec["node_id"])],
            spec.get("selector"),
        )
        choices = spec.get("choices")
        if not isinstance(choices, Mapping):
            raise ValueError("operation-reference projection choices are absent")
        return choices.get(str(observed), spec.get("default"))
    raise ValueError(f"unsupported public result projection kind: {kind}")


def _select_projection_value(value: Any, selector: Any) -> Any:
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json", exclude_none=True)
    if selector in (None, ""):
        return value
    current = value
    for part in str(selector).split("."):
        if isinstance(current, BaseModel):
            current = current.model_dump(mode="json", exclude_none=True)
        if not isinstance(current, Mapping) or part not in current:
            raise ValueError(f"public result projection selector is invalid: {selector}")
        current = current[part]
    return current


def _trajectory_steps(
    realized: RealizedTaskPackage,
    program: TaskProgram,
    execution: ProgramExecution,
    verification: ProgramVerification,
    normalized_result: dict[str, Any],
    citations: list[dict[str, Any]],
    registry: OperationRegistry,
) -> tuple[TrajectoryStep, ...]:
    public = realized.task.public
    steps: list[TrajectoryStep] = [
        TrajectoryStep(
            step_index=1,
            action=ActionType.PLAN,
            observation={
                "semantic_plan_id": realized.semantic_plan.plan_id,
                "node_count": len(program.nodes),
                "edge_count": sum(len(node.dependencies) for node in program.nodes),
            },
            rationale_summary="Traverse the complete public Program skeleton in dependency order.",
            status=StepStatus.SUCCEEDED,
        ),
        TrajectoryStep(
            step_index=2,
            action=ActionType.SEARCH,
            tool_name="evidence.search",
            tool_input=public.retrieval_scope,
            observation={"matched_count": len(realized.binding_snapshot.evidence_ids)},
            evidence_ids=realized.binding_snapshot.evidence_ids,
            rationale_summary="Retrieve evidence under the public semantic constraints.",
            status=StepStatus.SUCCEEDED,
        ),
        TrajectoryStep(
            step_index=3,
            action=ActionType.SELECT_EVIDENCE,
            observation={"selected_count": len(realized.binding_snapshot.evidence_ids)},
            evidence_ids=realized.binding_snapshot.evidence_ids,
            rationale_summary="Bind every public evidence role to one exact snapshot row.",
            status=StepStatus.SUCCEEDED,
        ),
    ]
    for node in program.nodes:
        definition = registry.require(node.operator_id)
        direct_evidence = tuple(
            ref.ref_id for ref in node.input_refs if ref.kind == InputRefKind.EVIDENCE
        )
        refs = tuple(
            f"{ref.kind.value}:{ref.ref_id}" + (f"#{ref.selector}" if ref.selector else "")
            for ref in node.input_refs
        )
        steps.append(
            TrajectoryStep(
                step_index=len(steps) + 1,
                action=ActionType(definition.action_type),
                tool_name=definition.tool_capability,
                tool_input={"parameters": node.parameters},
                observation={"result": execution.node_outputs[node.node_id]},
                evidence_ids=direct_evidence,
                program_node_id=node.node_id,
                operator_id=node.operator_id,
                input_refs=refs,
                output_ref=f"operation:{node.node_id}",
                rationale_summary=(
                    "Execute this registered public Program node from declared inputs."
                ),
                status=StepStatus.SUCCEEDED,
            )
        )
    if TaskRequirement.VERIFY_RESULT in public.requirements:
        steps.append(
            TrajectoryStep(
                step_index=len(steps) + 1,
                action=ActionType.VERIFY,
                observation={
                    "verified_output_ref": f"operation:{program.output_node_id}",
                    "verified_result": execution.final_output,
                    "node_statuses": verification.node_statuses,
                },
                evidence_ids=realized.binding_snapshot.evidence_ids,
                program_node_id=program.output_node_id,
                input_refs=(f"operation:{program.output_node_id}",),
                rationale_summary=(
                    "Independently replay every node through Oracle verifier implementations."
                ),
                status=StepStatus.SUCCEEDED,
            )
        )
    steps.append(
        TrajectoryStep(
            step_index=len(steps) + 1,
            action=ActionType.ANSWER,
            observation={"result": normalized_result, "citations": citations},
            evidence_ids=realized.binding_snapshot.evidence_ids,
            rationale_summary="Project the verified terminal result and bind complete citations.",
            status=StepStatus.SUCCEEDED,
        )
    )
    return tuple(steps)


def _maximum_dependency_depth(program: TaskProgram) -> int:
    depth: dict[str, int] = {}
    for node in program.nodes:
        depth[node.node_id] = 1 + max((depth[parent] for parent in node.dependencies), default=0)
    return max(depth.values())
