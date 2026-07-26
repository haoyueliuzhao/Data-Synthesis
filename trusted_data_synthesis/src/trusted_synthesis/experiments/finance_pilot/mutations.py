from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

from trusted_synthesis.core.evidence.schema import EvidenceItem
from trusted_synthesis.core.trajectory.schema import (
    ActionType,
    StepStatus,
    Trajectory,
    TrajectoryStep,
)
from trusted_synthesis.experiments.finance_pilot.task_factory import PilotTaskCase
from trusted_synthesis.hashing import canonical_hash


@dataclass(frozen=True)
class MutationCase:
    mutation_type: str
    source_trajectory_id: str
    trajectory: Trajectory
    expected_failure_gates: tuple[str, ...]

    @property
    def mutation_id(self) -> str:
        return canonical_hash(
            {
                "mutation_type": self.mutation_type,
                "source_trajectory_id": self.source_trajectory_id,
                "trajectory_hash": self.trajectory.trajectory_hash,
            },
            prefix="finance_pilot_mutation:",
        )


_EXPECTED_GATES = {
    "missing_evidence": ("evidence_retrieval_and_selection",),
    "wrong_entity": ("evidence_retrieval_and_selection",),
    "time_shift": ("evidence_retrieval_and_selection",),
    "predicate_mismatch": ("evidence_retrieval_and_selection",),
    "arithmetic_error": ("proof_and_operation",),
    "wrong_answer": ("answer_citation_and_claims",),
    "citation_mismatch": ("answer_citation_and_claims",),
    "unsupported_claim": ("answer_citation_and_claims",),
    "oracle_leakage": ("public_boundary_and_tools",),
    "disallowed_tool": ("public_boundary_and_tools",),
    "failed_step": ("workflow_contract",),
    "multi_error": (
        "public_boundary_and_tools",
        "evidence_retrieval_and_selection",
        "answer_citation_and_claims",
    ),
}


def generate_mutations(
    case: PilotTaskCase,
    candidate: Trajectory,
    mutation_types: tuple[str, ...],
) -> tuple[MutationCase, ...]:
    mutations = []
    for mutation_type in mutation_types:
        mutated = _mutate(case, candidate, mutation_type)
        if mutated is None:
            continue
        finalized = _finalize(candidate, mutated, mutation_type)
        mutations.append(
            MutationCase(
                mutation_type=mutation_type,
                source_trajectory_id=candidate.trajectory_id,
                trajectory=finalized,
                expected_failure_gates=_EXPECTED_GATES[mutation_type],
            )
        )
    return tuple(mutations)


def _mutate(
    case: PilotTaskCase,
    candidate: Trajectory,
    mutation_type: str,
) -> Trajectory | None:
    handlers: dict[str, Callable[[PilotTaskCase, Trajectory], Trajectory | None]] = {
        "missing_evidence": _missing_evidence,
        "wrong_entity": lambda value, item: _wrong_evidence(
            value,
            item,
            lambda evidence, gold: (
                evidence.subject.subject_id
                not in {gold_item.subject.subject_id for gold_item in gold}
            ),
        ),
        "time_shift": lambda value, item: _wrong_evidence(
            value,
            item,
            lambda evidence, gold: (
                evidence.subject.subject_id in {gold_item.subject.subject_id for gold_item in gold}
                and evidence.predicate in {gold_item.predicate for gold_item in gold}
                and _time_label(evidence) not in {_time_label(gold_item) for gold_item in gold}
            ),
        ),
        "predicate_mismatch": lambda value, item: _wrong_evidence(
            value,
            item,
            lambda evidence, gold: (
                evidence.subject.subject_id in {gold_item.subject.subject_id for gold_item in gold}
                and evidence.predicate not in {gold_item.predicate for gold_item in gold}
            ),
        ),
        "arithmetic_error": _arithmetic_error,
        "wrong_answer": _wrong_answer,
        "citation_mismatch": _citation_mismatch,
        "unsupported_claim": _unsupported_claim,
        "oracle_leakage": _oracle_leakage,
        "disallowed_tool": _disallowed_tool,
        "failed_step": _failed_step,
        "multi_error": _multi_error,
    }
    try:
        handler = handlers[mutation_type]
    except KeyError as exc:
        raise ValueError(f"unknown finance pilot mutation: {mutation_type}") from exc
    return handler(case, candidate)


def _missing_evidence(case: PilotTaskCase, candidate: Trajectory) -> Trajectory:
    selected = _step_evidence(candidate, ActionType.SELECT_EVIDENCE)
    remaining = selected[1:] if len(selected) > 1 else ()
    return candidate.model_copy(
        update={
            "steps": _update_steps(
                candidate,
                ActionType.SELECT_EVIDENCE,
                lambda step: step.model_copy(
                    update={
                        "evidence_ids": remaining,
                        "observation": {"selected_count": len(remaining)},
                    }
                ),
            )
        }
    )


def _wrong_evidence(
    case: PilotTaskCase,
    candidate: Trajectory,
    predicate: Callable[[EvidenceItem, tuple[EvidenceItem, ...]], bool],
) -> Trajectory | None:
    gold_ids = set(case.task.oracle.gold_evidence_ids)
    gold = tuple(item for item in case.bundle.evidence if item.evidence_id in gold_ids)
    distractors = [
        item
        for item in case.corpus.evidence
        if item.evidence_id not in gold_ids and predicate(item, gold)
    ]
    if not distractors:
        return None
    selected_id = sorted(item.evidence_id for item in distractors)[0]
    steps = candidate.steps
    for action in (ActionType.SEARCH, ActionType.SELECT_EVIDENCE):
        observation_key = "matched_count" if action == ActionType.SEARCH else "selected_count"

        def replace(step: TrajectoryStep, *, key: str = observation_key) -> TrajectoryStep:
            return step.model_copy(
                update={
                    "evidence_ids": (selected_id,),
                    "observation": {key: 1},
                }
            )

        steps = _update_step_tuple(
            steps,
            action,
            replace,
        )
    return candidate.model_copy(update={"steps": steps})


def _arithmetic_error(case: PilotTaskCase, candidate: Trajectory) -> Trajectory | None:
    if ActionType.CALCULATE not in {step.action for step in candidate.steps}:
        return None
    wrong = _increment_result(dict(candidate.final_answer.get("result") or {}))
    return candidate.model_copy(
        update={
            "steps": _update_steps(
                candidate,
                ActionType.CALCULATE,
                lambda step: step.model_copy(update={"observation": {"result": wrong}}),
            )
        }
    )


def _wrong_answer(case: PilotTaskCase, candidate: Trajectory) -> Trajectory:
    answer = dict(candidate.final_answer)
    answer["result"] = _increment_result(dict(answer.get("result") or {}))
    return candidate.model_copy(
        update={
            "final_answer": answer,
            "steps": _update_steps(
                candidate,
                ActionType.ANSWER,
                lambda step: step.model_copy(update={"observation": answer}),
            ),
        }
    )


def _citation_mismatch(case: PilotTaskCase, candidate: Trajectory) -> Trajectory:
    answer = dict(candidate.final_answer)
    citations = [dict(item) for item in answer.get("citations") or []]
    if citations:
        citations[0] = {
            **citations[0],
            "source_id": "mutated_source",
            "source_locator": {"uri": "https://invalid.example/mutated"},
        }
    answer["citations"] = citations
    return candidate.model_copy(
        update={
            "final_answer": answer,
            "steps": _update_steps(
                candidate,
                ActionType.ANSWER,
                lambda step: step.model_copy(update={"observation": answer}),
            ),
        }
    )


def _unsupported_claim(case: PilotTaskCase, candidate: Trajectory) -> Trajectory:
    answer = {
        **candidate.final_answer,
        "claims": [
            {
                "claim_id": "claim:unsupported_investment_advice",
                "claim_type": "investment_recommendation",
                "predicate": case.bundle.evidence[0].predicate,
                "evidence_ids": [case.bundle.evidence[0].evidence_id],
            }
        ],
    }
    return candidate.model_copy(update={"final_answer": answer})


def _oracle_leakage(case: PilotTaskCase, candidate: Trajectory) -> Trajectory:
    return candidate.model_copy(
        update={
            "steps": _update_steps(
                candidate,
                ActionType.PLAN,
                lambda step: step.model_copy(
                    update={
                        "tool_input": {
                            "gold_evidence_ids": list(case.task.oracle.gold_evidence_ids)
                        }
                    }
                ),
            )
        }
    )


def _disallowed_tool(case: PilotTaskCase, candidate: Trajectory) -> Trajectory:
    return candidate.model_copy(
        update={
            "steps": _update_steps(
                candidate,
                ActionType.SEARCH,
                lambda step: step.model_copy(update={"tool_name": "oracle_evidence.read"}),
            )
        }
    )


def _failed_step(case: PilotTaskCase, candidate: Trajectory) -> Trajectory:
    return candidate.model_copy(
        update={
            "steps": _update_steps(
                candidate,
                ActionType.SELECT_EVIDENCE,
                lambda step: step.model_copy(update={"status": StepStatus.FAILED}),
            )
        }
    )


def _multi_error(case: PilotTaskCase, candidate: Trajectory) -> Trajectory:
    mutated = _oracle_leakage(case, candidate)
    mutated = _missing_evidence(case, mutated)
    mutated = _wrong_answer(case, mutated)
    return _citation_mismatch(case, mutated)


def _increment_result(result: dict[str, Any]) -> dict[str, Any]:
    for field in ("value", "difference"):
        if field not in result:
            continue
        try:
            result[field] = str(Decimal(str(result[field])) + Decimal("1"))
        except (InvalidOperation, TypeError, ValueError):
            result[field] = "__mutated__"
        return result
    result["value"] = "1"
    return result


def _step_evidence(candidate: Trajectory, action: ActionType) -> tuple[str, ...]:
    for step in candidate.steps:
        if step.action == action:
            return step.evidence_ids
    return ()


def _update_steps(
    candidate: Trajectory,
    action: ActionType,
    update: Callable[[TrajectoryStep], TrajectoryStep],
) -> tuple[TrajectoryStep, ...]:
    return _update_step_tuple(candidate.steps, action, update)


def _update_step_tuple(
    steps: tuple[TrajectoryStep, ...],
    action: ActionType,
    update: Callable[[TrajectoryStep], TrajectoryStep],
) -> tuple[TrajectoryStep, ...]:
    return tuple(update(step) if step.action == action else step for step in steps)


def _finalize(source: Trajectory, mutated: Trajectory, mutation_type: str) -> Trajectory:
    identity = {
        "source_trajectory_id": source.trajectory_id,
        "mutation_type": mutation_type,
        "steps": [step.model_dump(mode="json") for step in mutated.steps],
        "final_answer": mutated.final_answer,
        "version": "finance_pilot_mutation.v1",
    }
    return mutated.model_copy(
        update={
            "trajectory_id": canonical_hash(identity, prefix="mutated_candidate:"),
            "generator_version": f"finance_pilot_mutation.v1:{mutation_type}",
        }
    )


def _time_label(item: EvidenceItem) -> str:
    context = item.temporal_context
    point = context.valid_to or context.observed_at or context.valid_from
    return context.label or (point.isoformat() if point else "unspecified")
