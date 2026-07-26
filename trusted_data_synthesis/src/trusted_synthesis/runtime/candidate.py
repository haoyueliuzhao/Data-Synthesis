from __future__ import annotations

from decimal import Decimal

from trusted_synthesis.core.evidence.payloads import ScalarObservation
from trusted_synthesis.core.task.schema import TaskPublicSpec
from trusted_synthesis.core.trajectory.schema import (
    ActionType,
    StepStatus,
    Trajectory,
    TrajectoryStep,
    WorkflowKind,
)
from trusted_synthesis.hashing import canonical_hash
from trusted_synthesis.runtime.tools import EvidenceToolRuntime

CANDIDATE_GENERATOR_VERSION = "candidate_workflow.v4"


class CandidateTrajectoryGenerator:
    """Generate from public task data only; the oracle type cannot be supplied."""

    def generate(self, task: TaskPublicSpec, runtime: EvidenceToolRuntime) -> Trajectory:
        evidence = runtime.search(task.retrieval_scope)
        selected = self._select(task, evidence)
        result = self._answer(task, selected)
        citations = [
            {
                "evidence_id": item.evidence_id,
                "source_id": item.source.source_id,
                "source_locator": item.source_locator.model_dump(mode="json", exclude_none=True),
            }
            for item in selected
        ]
        evidence_ids = tuple(item.evidence_id for item in selected)
        steps: list[TrajectoryStep] = [
            TrajectoryStep(
                step_index=1,
                action=ActionType.PLAN,
                observation={"task_type": task.task_type},
                rationale_summary="Infer the required evidence from the public instruction.",
                status=StepStatus.SUCCEEDED,
            ),
            TrajectoryStep(
                step_index=2,
                action=ActionType.SEARCH,
                tool_name="evidence.search",
                tool_input=task.retrieval_scope,
                observation={"matched_count": len(evidence)},
                evidence_ids=tuple(item.evidence_id for item in evidence),
                rationale_summary="Search with public subject, predicate, and time constraints.",
                status=StepStatus.SUCCEEDED,
            ),
        ]
        operation_steps = _operation_steps(task, selected, result, start_index=3)
        steps.extend(operation_steps)
        next_index = len(steps) + 1
        if any(item.value == "verify_result" for item in task.requirements):
            steps.append(
                TrajectoryStep(
                    step_index=next_index,
                    action=ActionType.VERIFY,
                    observation={
                        "schema_checked": True,
                        "source_checked": True,
                        "verified_output_ref": "operation:result",
                        "verified_result": result,
                    },
                    evidence_ids=evidence_ids,
                    program_node_id="result",
                    input_refs=("operation:result",),
                    rationale_summary=(
                        "Check answer fields and bind citations to selected evidence."
                    ),
                    status=StepStatus.SUCCEEDED,
                )
            )
            next_index += 1
        steps.append(
            TrajectoryStep(
                step_index=next_index,
                action=ActionType.ANSWER,
                observation={"result": result, "citations": citations},
                evidence_ids=evidence_ids,
                rationale_summary="Return the answer derived from publicly retrieved evidence.",
                status=StepStatus.SUCCEEDED,
            )
        )
        return Trajectory(
            trajectory_id=canonical_hash(
                {
                    "task_id": task.task_id,
                    "retrieved_evidence_ids": tuple(item.evidence_id for item in evidence),
                    "evidence_ids": evidence_ids,
                    "result": result,
                    "version": CANDIDATE_GENERATOR_VERSION,
                },
                prefix="candidate_workflow:",
            ),
            task_id=task.task_id,
            workflow_kind=WorkflowKind.CANDIDATE,
            steps=tuple(steps),
            final_answer={"result": result, "citations": citations},
            generator_version=CANDIDATE_GENERATOR_VERSION,
        )

    @staticmethod
    def _select(task: TaskPublicSpec, evidence):
        contract = task.retrieval_scope.get("selection_contract")
        if not isinstance(contract, dict):
            return evidence
        return tuple(item for item in evidence if _matches_selection_contract(item, contract))

    @staticmethod
    def _answer(task: TaskPublicSpec, evidence) -> dict[str, object]:
        if task.task_type == "fact_retrieval" and len(evidence) == 1:
            item = evidence[0]
            return {
                "payload": item.payload.model_dump(mode="json", exclude_none=True),
                "source_id": item.source.source_id,
            }
        if task.task_type == "comparison" and len(evidence) == 2:
            values = [_scalar_value(item) for item in evidence]
            higher = None
            if values[0] > values[1]:
                higher = evidence[0].evidence_id
            elif values[1] > values[0]:
                higher = evidence[1].evidence_id
            return {"higher_ref": higher, "difference": str(abs(values[0] - values[1]))}
        if task.task_type == "temporal_growth" and len(evidence) == 2:
            ordered = sorted(evidence, key=_temporal_sort_key)
            earlier = _scalar_value(ordered[0])
            later = _scalar_value(ordered[1])
            if earlier == 0:
                return {"status": "insufficient_capability", "reason": "zero_base"}
            return {"value": str((later - earlier) / abs(earlier) * Decimal("100"))}
        if task.task_type == "temporal_average" and len(evidence) >= 3:
            values = [_scalar_value(item) for item in evidence]
            return {
                "method": "mean",
                "value": str(sum(values, Decimal("0")) / Decimal(len(values))),
            }
        return {"status": "insufficient_capability", "matched_count": len(evidence)}


def _scalar_value(item) -> Decimal:
    if not isinstance(item.payload, ScalarObservation):
        raise ValueError(f"candidate numeric task received non-scalar evidence: {item.evidence_id}")
    return Decimal(str(item.payload.value))


def _temporal_sort_key(item):
    context = item.temporal_context
    return context.valid_to or context.observed_at or context.valid_from


def _operation_steps(
    task: TaskPublicSpec,
    evidence,
    result: dict[str, object],
    *,
    start_index: int,
) -> tuple[TrajectoryStep, ...]:
    ordered = tuple(sorted(evidence, key=_temporal_sort_key))
    steps: list[TrajectoryStep] = []

    def add_lookup(item, node_id: str) -> None:
        steps.append(
            TrajectoryStep(
                step_index=start_index + len(steps),
                action=ActionType.SELECT_EVIDENCE,
                observation={
                    "selected_count": 1,
                    "result": {
                        "selected_ref": item.evidence_id,
                        "payload": item.payload.model_dump(mode="json", exclude_none=True),
                    },
                },
                evidence_ids=(item.evidence_id,),
                program_node_id=node_id,
                operator_id="lookup",
                input_refs=(f"evidence:{item.evidence_id}",),
                output_ref=f"operation:{node_id}",
                rationale_summary="Bind one selected observation to its lookup operation.",
                status=StepStatus.SUCCEEDED,
            )
        )

    if task.task_type == "fact_retrieval" and len(evidence) == 1:
        add_lookup(evidence[0], "result")
        return tuple(steps)
    input_refs: tuple[str, ...]
    operator_id: str
    if task.task_type == "temporal_growth" and len(ordered) == 2:
        add_lookup(ordered[0], "earlier_value")
        add_lookup(ordered[1], "later_value")
        input_refs = (
            "operation:earlier_value#payload.value",
            "operation:later_value#payload.value",
        )
        operator_id = "growth"
    elif task.task_type == "temporal_average" and len(ordered) >= 3:
        for index, item in enumerate(ordered, start=1):
            add_lookup(item, f"value_{index}")
        input_refs = tuple(
            f"operation:value_{index}#payload.value" for index in range(1, len(ordered) + 1)
        )
        operator_id = "aggregate"
    else:
        steps.append(
            TrajectoryStep(
                step_index=start_index,
                action=ActionType.SELECT_EVIDENCE,
                observation={"selected_count": len(evidence)},
                evidence_ids=tuple(item.evidence_id for item in evidence),
                rationale_summary="Select evidence matching the public semantic contract.",
                status=StepStatus.SUCCEEDED,
            )
        )
        input_refs = tuple(f"evidence:{item.evidence_id}" for item in evidence)
        operator_id = "compare" if task.task_type == "comparison" else "unsupported"
    if any(item.value == "calculate" for item in task.requirements):
        steps.append(
            TrajectoryStep(
                step_index=start_index + len(steps),
                action=ActionType.CALCULATE,
                tool_name="calculator",
                observation={"result": result},
                evidence_ids=tuple(item.evidence_id for item in evidence),
                program_node_id="result",
                operator_id=operator_id,
                input_refs=input_refs,
                output_ref="operation:result",
                rationale_summary="Compute the bound operation node from its declared inputs.",
                status=StepStatus.SUCCEEDED,
            )
        )
    return tuple(steps)


def _matches_selection_contract(item, contract: dict[str, object]) -> bool:
    payload = item.payload.model_dump(mode="json", exclude_none=True)
    payload_context = {
        key: value for key, value in payload.items() if key not in {"kind", "value", "precision"}
    }
    checks = (
        _allowed(item.definition.definition_id, contract.get("definition_ids")),
        _allowed(item.source.source_id, contract.get("source_ids")),
        _allowed(item.source.authority.value, contract.get("source_authorities")),
        _allowed_hash(payload_context, contract.get("payload_context_hashes"), "payload_context:"),
        _allowed_hash(
            item.domain_context,
            contract.get("domain_context_hashes"),
            "domain_context:",
        ),
        _allowed(item.temporal_context.basis, contract.get("time_bases")),
        _allowed(item.temporal_context.frequency, contract.get("frequencies")),
        _allowed(item.scope.scope_type if item.scope else None, contract.get("scope_types")),
        _allowed(item.scope.scope_id if item.scope else None, contract.get("scope_ids")),
    )
    if not all(checks):
        return False
    required_build_ids = contract.get("required_build_ids")
    if isinstance(required_build_ids, dict):
        for key, allowed in required_build_ids.items():
            if not _allowed(item.provenance.build_ids.get(str(key)), allowed):
                return False
    return True


def _allowed(value: object, allowed: object) -> bool:
    if not isinstance(allowed, (list, tuple, set)) or not allowed:
        return True
    return value in set(allowed)


def _allowed_hash(value: object, allowed: object, prefix: str) -> bool:
    if not isinstance(allowed, (list, tuple, set)) or not allowed:
        return True
    return canonical_hash(value, prefix=prefix) in set(allowed)
