from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from trusted_synthesis.core.trajectory.candidate_verifier import CandidateVerificationReport
from trusted_synthesis.core.trajectory.schema import Trajectory


class CandidateObservationIndex(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", arbitrary_types_allowed=True)

    checks: dict[str, bool]
    check_details: dict[str, tuple[str, ...]]
    steps_by_action: dict[str, tuple[int, ...]]
    steps_by_program_node: dict[str, tuple[int, ...]]
    retrieved_evidence_ids: tuple[str, ...]
    selected_evidence_ids: tuple[str, ...]
    citation_evidence_ids: tuple[str, ...]
    answer_result: object = Field(default=None)


def build_observation_index(
    report: CandidateVerificationReport,
    trajectory: Trajectory,
) -> CandidateObservationIndex:
    steps_by_action: dict[str, list[int]] = {}
    steps_by_program_node: dict[str, list[int]] = {}
    for step in trajectory.steps:
        steps_by_action.setdefault(step.action.value, []).append(step.step_index)
        if step.program_node_id:
            steps_by_program_node.setdefault(step.program_node_id, []).append(step.step_index)
    citations = trajectory.final_answer.get("citations") or ()
    citation_ids = tuple(
        dict.fromkeys(
            str(item["evidence_id"])
            for item in citations
            if isinstance(item, dict) and item.get("evidence_id")
        )
    )
    return CandidateObservationIndex(
        checks={item.check_id: item.passed for item in report.checks},
        check_details={item.check_id: item.details for item in report.checks},
        steps_by_action={key: tuple(value) for key, value in steps_by_action.items()},
        steps_by_program_node={key: tuple(value) for key, value in steps_by_program_node.items()},
        retrieved_evidence_ids=report.retrieved_evidence_ids,
        selected_evidence_ids=report.selected_evidence_ids,
        citation_evidence_ids=citation_ids,
        answer_result=trajectory.final_answer.get("result"),
    )
