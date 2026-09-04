from __future__ import annotations

import hashlib
from collections import Counter
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.canonical_json import canonical_json_bytes, strict_canonical_hash
from trusted_synthesis.core.operations.registry import OperationRegistry
from trusted_synthesis.core.task.program import (
    InputRefKind,
    ProgramInputRef,
    make_program,
)
from trusted_synthesis.core.task.program_depth import (
    ProgramDepthMetrics,
    admit_program_depth_metrics,
    derive_program_depth_metrics,
)
from trusted_synthesis.core.trajectory.public_plan_executor import PublicPlanCandidateExecution
from trusted_synthesis.core.trajectory.schema import ActionType, StepStatus, Trajectory

TASK_TYPE_BY_OPERATOR_SEQUENCE: dict[tuple[str, ...], str] = {
    ("compare",): "comparison",
    ("lookup", "lookup", "lookup", "lookup", "growth", "growth", "compare"): (
        "derived_growth_comparison"
    ),
    ("lookup",): "fact_retrieval",
    ("registered_compare",): "registered_cross_metric_comparison",
    ("lookup", "lookup", "ratio"): "registered_ratio",
    ("lookup", "lookup", "difference"): "temporal_absolute_change",
    ("lookup", "lookup", "lookup", "aggregate"): "temporal_average",
    ("lookup", "lookup", "growth"): "temporal_growth",
}
EXPECTED_NODE_DEPTHS = {
    "comparison": (1, 1, 1, 3),
    "derived_growth_comparison": (7, 3, 2, 4),
    "fact_retrieval": (1, 1, 0, 2),
    "registered_cross_metric_comparison": (1, 1, 1, 3),
    "registered_ratio": (3, 2, 1, 3),
    "temporal_absolute_change": (3, 2, 1, 3),
    "temporal_average": (4, 2, 1, 3),
    "temporal_growth": (3, 2, 1, 3),
}
EXPECTED_TASK_TYPES = tuple(sorted(EXPECTED_NODE_DEPTHS))
DEPTH_ATTACK_NAMES = (
    "delete_required_semantic_dependency",
    "bypass_derived_semantic_chain",
    "inflate_with_irrelevant_lookup",
)


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class DepthMetricContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    registry_manifest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    authoritative_fields: tuple[str, ...] = (
        "node_count",
        "structural_dependency_depth",
        "semantic_operation_depth",
        "workflow_interaction_depth",
    )
    node_count_definition: str = "all exact source Program nodes"
    structural_dependency_depth_definition: str = (
        "longest output-ancestor DAG path counting every Program node"
    )
    semantic_operation_depth_definition: str = (
        "longest output-ancestor DAG path with semantic=1 and transparent_projection=0"
    )
    workflow_interaction_depth_definition: str = (
        "evidence_resolution_stage + semantic_operation_depth + independent_verification_stage"
    )
    transparent_projection_role: Literal["transparent_projection"] = "transparent_projection"
    semantic_operation_role: Literal["semantic"] = "semantic"
    registry_program_role_is_authority: Literal[True] = True
    pure_retrieval_semantic_depth: Literal[0] = 0
    evidence_resolution_stage_count: Literal[1] = 1
    independent_verification_stage_count: Literal[1] = 1
    plan_template_stage_counted: Literal[False] = False
    answer_template_stage_counted: Literal[False] = False
    exact_source_program_required: Literal[True] = True
    output_dependency_closure_required: Literal[True] = True
    legacy_program_depth_authoritative: Literal[False] = False
    legacy_semantic_only_depth_authoritative: Literal[False] = False
    future_depth_sampling_requires_this_contract: Literal[True] = True
    realistic_difficulty_claimed: Literal[False] = False
    schema_version: str = "qa_program_depth_metric_contract.v1"

    @model_validator(mode="after")
    def validate_contract(self) -> DepthMetricContract:
        expected = strict_canonical_hash(
            self.model_dump(mode="python", exclude={"contract_id"}),
            prefix="qa_program_depth_metric_contract:",
        )
        if self.contract_id != expected:
            raise ValueError("QA Program depth Contract identity differs")
        return self


class DepthMetricRow(FrozenModel):
    row_id: str = Field(min_length=1)
    contract_id: str = Field(min_length=1)
    task_type: str = Field(min_length=1)
    execution_id: str = Field(min_length=1)
    trajectory_id: str = Field(min_length=1)
    metrics: ProgramDepthMetrics
    operator_sequence: tuple[str, ...] = Field(min_length=1)
    registry_role_sequence: tuple[str, ...] = Field(min_length=1)
    workflow_source_bound: Literal[True] = True
    schema_version: str = "qa_program_depth_metric_row.v1"

    @model_validator(mode="after")
    def validate_row(self) -> DepthMetricRow:
        expected_depths = EXPECTED_NODE_DEPTHS.get(self.task_type)
        observed = (
            self.metrics.node_count,
            self.metrics.structural_dependency_depth,
            self.metrics.semantic_operation_depth,
            self.metrics.workflow_interaction_depth,
        )
        if (
            expected_depths is None
            or observed != expected_depths
            or len(self.registry_role_sequence) != self.metrics.node_count
            or self.row_id
            != strict_canonical_hash(
                self.model_dump(mode="python", exclude={"row_id"}),
                prefix="qa_program_depth_metric_row:",
            )
        ):
            raise ValueError("QA Program depth row differs")
        return self


class DepthMetricContractAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    contract_id: str = Field(min_length=1)
    registry_manifest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    rows: tuple[DepthMetricRow, ...] = Field(min_length=8, max_length=8)
    task_types: tuple[str, ...] = EXPECTED_TASK_TYPES
    node_count_distribution: dict[str, int]
    structural_dependency_depth_distribution: dict[str, int]
    semantic_operation_depth_distribution: dict[str, int]
    workflow_interaction_depth_distribution: dict[str, int]
    maximum_structural_dependency_depth: Literal[3] = 3
    maximum_semantic_operation_depth: Literal[2] = 2
    semantic_depth_three_plus_count: Literal[0] = 0
    schema_consistent: Literal[True] = True
    output_dependency_closed_count: Literal[8] = 8
    workflow_source_bound_count: Literal[8] = 8
    provider_calls: Literal[0] = 0
    gpu_jobs: Literal[0] = 0
    schema_version: str = "qa_program_depth_metric_audit.v1"

    @model_validator(mode="after")
    def validate_audit(self) -> DepthMetricContractAudit:
        if (
            tuple(row.task_type for row in self.rows) != EXPECTED_TASK_TYPES
            or self.node_count_distribution != {"1": 3, "3": 3, "4": 1, "7": 1}
            or self.structural_dependency_depth_distribution != {"1": 3, "2": 4, "3": 1}
            or self.semantic_operation_depth_distribution != {"0": 1, "1": 6, "2": 1}
            or self.workflow_interaction_depth_distribution != {"2": 1, "3": 6, "4": 1}
            or any(
                row.metrics.registry_manifest_sha256 != self.registry_manifest_sha256
                for row in self.rows
            )
            or self.audit_id
            != strict_canonical_hash(
                self.model_dump(mode="python", exclude={"audit_id"}),
                prefix="qa_program_depth_metric_audit:",
            )
        ):
            raise ValueError("QA Program depth Audit differs")
        return self


class DepthNegativeControl(FrozenModel):
    name: str = Field(min_length=1)
    candidate_program_id: str = Field(min_length=1)
    candidate_program_hash: str = Field(min_length=1)
    retained_final_answer_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    final_answer_retained: Literal[True] = True
    rejected: Literal[True] = True
    rejection_stage: Literal["exact_source_program_admission", "output_dependency_closure"]
    reason_type: str = Field(min_length=1)
    reason_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    output_writes: Literal[0] = 0
    provider_calls: Literal[0] = 0


class DepthNegativeControlAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    contract_id: str = Field(min_length=1)
    controls: tuple[DepthNegativeControl, ...] = Field(min_length=3, max_length=3)
    attempted_count: Literal[3] = 3
    rejected_count: Literal[3] = 3
    accepted_count: Literal[0] = 0
    final_answer_retained_count: Literal[3] = 3
    output_write_count: Literal[0] = 0
    provider_calls: Literal[0] = 0
    gpu_jobs: Literal[0] = 0
    schema_version: str = "qa_program_depth_negative_control_audit.v1"

    @model_validator(mode="after")
    def validate_audit(self) -> DepthNegativeControlAudit:
        if tuple(
            control.name for control in self.controls
        ) != DEPTH_ATTACK_NAMES or self.audit_id != strict_canonical_hash(
            self.model_dump(mode="python", exclude={"audit_id"}),
            prefix="qa_program_depth_negative_control_audit:",
        ):
            raise ValueError("QA Program depth negative-control Audit differs")
        return self


class DepthMetricProducts(FrozenModel):
    contract: DepthMetricContract
    audit: DepthMetricContractAudit
    negative_audit: DepthNegativeControlAudit


def build_depth_metric_audit(
    *,
    executions: tuple[PublicPlanCandidateExecution, ...],
    trajectories: tuple[Trajectory, ...],
    registry: OperationRegistry,
) -> DepthMetricProducts:
    if len(executions) != 8 or len(trajectories) != 8:
        raise ValueError("depth metric denominator must contain exactly eight canonical cases")
    registry_manifest_sha256 = hashlib.sha256(canonical_json_bytes(registry.manifest())).hexdigest()
    contract = _identified(
        DepthMetricContract,
        {"registry_manifest_sha256": registry_manifest_sha256},
        "contract_id",
        "qa_program_depth_metric_contract:",
    )
    trajectories_by_task = {trajectory.task_id: trajectory for trajectory in trajectories}
    if len(trajectories_by_task) != 8:
        raise ValueError("depth metric candidate trajectories repeat a Task identity")

    rows: list[DepthMetricRow] = []
    derived_case: tuple[PublicPlanCandidateExecution, Trajectory] | None = None
    for execution in executions:
        program = execution.reconstructed_program
        operator_sequence = tuple(node.operator_id for node in program.nodes)
        try:
            task_type = TASK_TYPE_BY_OPERATOR_SEQUENCE[operator_sequence]
            trajectory = trajectories_by_task[execution.trajectory.task_id]
        except KeyError as exc:
            raise ValueError("depth metric case differs from the exact eight-case catalog") from exc
        metrics = derive_program_depth_metrics(program, registry)
        _validate_workflow_source(
            execution,
            trajectory,
            registry,
            semantic_operation_depth=metrics.semantic_operation_depth,
        )
        roles = tuple(registry.require(node.operator_id).program_role for node in program.nodes)
        row = _identified(
            DepthMetricRow,
            {
                "contract_id": contract.contract_id,
                "task_type": task_type,
                "execution_id": execution.execution_id,
                "trajectory_id": trajectory.trajectory_id,
                "metrics": metrics,
                "operator_sequence": operator_sequence,
                "registry_role_sequence": roles,
            },
            "row_id",
            "qa_program_depth_metric_row:",
        )
        rows.append(row)
        if task_type == "derived_growth_comparison":
            derived_case = (execution, trajectory)

    rows_tuple = tuple(sorted(rows, key=lambda row: row.task_type))
    audit = _identified(
        DepthMetricContractAudit,
        {
            "contract_id": contract.contract_id,
            "registry_manifest_sha256": registry_manifest_sha256,
            "rows": rows_tuple,
            "node_count_distribution": _distribution(row.metrics.node_count for row in rows_tuple),
            "structural_dependency_depth_distribution": _distribution(
                row.metrics.structural_dependency_depth for row in rows_tuple
            ),
            "semantic_operation_depth_distribution": _distribution(
                row.metrics.semantic_operation_depth for row in rows_tuple
            ),
            "workflow_interaction_depth_distribution": _distribution(
                row.metrics.workflow_interaction_depth for row in rows_tuple
            ),
        },
        "audit_id",
        "qa_program_depth_metric_audit:",
    )
    if derived_case is None:
        raise ValueError("derived-growth depth source case is absent")
    negative = _depth_negative_controls(
        contract_id=contract.contract_id,
        source_execution=derived_case[0],
        source_trajectory=derived_case[1],
        registry=registry,
    )
    return DepthMetricProducts(contract=contract, audit=audit, negative_audit=negative)


def _validate_workflow_source(
    execution: PublicPlanCandidateExecution,
    trajectory: Trajectory,
    registry: OperationRegistry,
    *,
    semantic_operation_depth: int,
) -> None:
    program = execution.reconstructed_program
    if (
        trajectory.task_id != execution.trajectory.task_id
        or trajectory.program_execution != execution.program_execution.model_dump(mode="json")
        or not execution.independent_verification.passed
    ):
        raise ValueError("workflow depth source differs from exact execution and replay")
    steps = trajectory.steps
    plans = tuple(step for step in steps if step.action == ActionType.PLAN)
    searches = tuple(step for step in steps if step.action == ActionType.SEARCH)
    selections = tuple(
        step
        for step in steps
        if step.action == ActionType.SELECT_EVIDENCE and step.operator_id is None
    )
    operations = tuple(step for step in steps if step.operator_id is not None)
    verifies = tuple(step for step in steps if step.action == ActionType.VERIFY)
    answers = tuple(step for step in steps if step.action == ActionType.ANSWER)
    if (
        not all(len(group) == 1 for group in (plans, searches, selections, answers))
        or len(verifies) > 1
        or (len(verifies) == 0 and semantic_operation_depth != 0)
    ):
        raise ValueError("workflow depth source stage cardinality differs")
    if (
        tuple(step.program_node_id for step in operations)
        != tuple(node.node_id for node in program.nodes)
        or tuple(step.operator_id for step in operations)
        != tuple(node.operator_id for node in program.nodes)
        or any(
            step.action != ActionType(registry.require(node.operator_id).action_type)
            for step, node in zip(operations, program.nodes, strict=True)
        )
        or any(step.status != StepStatus.SUCCEEDED for step in steps)
    ):
        raise ValueError("workflow depth source Program actions differ")
    first_operation = operations[0].step_index
    last_operation = operations[-1].step_index
    if not (
        plans[0].step_index
        < searches[0].step_index
        < selections[0].step_index
        < first_operation
        <= last_operation
        < answers[0].step_index
    ):
        raise ValueError("workflow depth source causal order differs")
    if verifies:
        verify = verifies[0]
        if not (
            last_operation < verify.step_index < answers[0].step_index
            and verify.program_node_id == program.output_node_id
            and verify.input_refs == (f"operation:{program.output_node_id}",)
        ):
            raise ValueError("workflow depth independent verification binding differs")


def _depth_negative_controls(
    *,
    contract_id: str,
    source_execution: PublicPlanCandidateExecution,
    source_trajectory: Trajectory,
    registry: OperationRegistry,
) -> DepthNegativeControlAudit:
    source = source_execution.reconstructed_program
    final_answer_sha256 = hashlib.sha256(
        canonical_json_bytes(source_trajectory.final_answer)
    ).hexdigest()
    controls: list[DepthNegativeControl] = []

    nodes = list(source.nodes)
    first_lookup = next(node for node in nodes if node.operator_id == "lookup")
    left_growth = next(node for node in nodes if node.node_id == "left_growth")
    output = next(node for node in nodes if node.node_id == source.output_node_id)
    retained_left_lookups = tuple(
        node for node in nodes if node.node_id in set(left_growth.dependencies)
    )
    duplicated_left_result = tuple(
        ProgramInputRef(
            kind=InputRefKind.OPERATION,
            ref_id=left_growth.node_id,
            selector="value",
        )
        for _ in range(2)
    )
    deleted_output = output.model_copy(
        update={
            "input_refs": duplicated_left_result,
            "dependencies": (left_growth.node_id,),
        }
    )
    deleted = make_program(
        (*retained_left_lookups, left_growth, deleted_output), source.output_node_id
    )

    lookup_nodes = tuple(node for node in nodes if node.operator_id == "lookup")
    bypass_inputs = tuple(
        ProgramInputRef(
            kind=InputRefKind.EVIDENCE,
            ref_id=node.input_refs[0].ref_id,
            selector="payload.value",
        )
        for node in (lookup_nodes[0], lookup_nodes[2])
    )
    bypass_output = output.model_copy(
        update={
            "input_refs": bypass_inputs,
            "dependencies": (),
        }
    )
    bypass = make_program((bypass_output,), source.output_node_id)

    irrelevant = first_lookup.model_copy(update={"node_id": "depth_attack_irrelevant_lookup"})
    inflated = make_program((*source.nodes, irrelevant), source.output_node_id)

    for name, candidate in zip(DEPTH_ATTACK_NAMES, (deleted, bypass, inflated), strict=True):
        try:
            metrics = derive_program_depth_metrics(candidate, registry)
            admit_program_depth_metrics(
                expected_program=source,
                candidate_program=candidate,
                candidate_metrics=metrics,
                registry=registry,
            )
        except ValueError as exc:
            stage: Literal["exact_source_program_admission", "output_dependency_closure"] = (
                "output_dependency_closure"
                if "outside output dependency closure" in str(exc)
                else "exact_source_program_admission"
            )
            controls.append(
                DepthNegativeControl(
                    name=name,
                    candidate_program_id=candidate.program_id,
                    candidate_program_hash=candidate.program_hash,
                    retained_final_answer_sha256=final_answer_sha256,
                    rejection_stage=stage,
                    reason_type=type(exc).__name__,
                    reason_sha256=hashlib.sha256(str(exc).encode("utf-8")).hexdigest(),
                )
            )
        else:
            raise ValueError(f"QA Program depth attack was accepted: {name}")

    return _identified(
        DepthNegativeControlAudit,
        {"contract_id": contract_id, "controls": tuple(controls)},
        "audit_id",
        "qa_program_depth_negative_control_audit:",
    )


def _distribution(values: Any) -> dict[str, int]:
    counts = Counter(values)
    return {str(key): counts[key] for key in sorted(counts)}


def _identified(model_type: type[Any], values: dict[str, Any], field: str, prefix: str) -> Any:
    draft = model_type.model_construct(**{field: "pending", **values})
    return model_type(
        **{
            field: strict_canonical_hash(
                draft.model_dump(mode="python", exclude={field}), prefix=prefix
            ),
            **values,
        }
    )
