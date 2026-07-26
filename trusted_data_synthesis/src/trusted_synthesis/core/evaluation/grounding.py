from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict

from trusted_synthesis.core.evidence.schema import EvidenceItem
from trusted_synthesis.core.plugins import SourceGroundingVerifierProtocol
from trusted_synthesis.core.task.schema import VerifierRequirement


class SourceGroundingStatus(str, Enum):
    VERIFIED = "verified"
    NOT_APPLICABLE = "not_applicable"
    MISSING_REQUIRED_VERIFIER = "missing_required_verifier"
    FAILED = "failed"


class SourceGroundingEvaluation(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    status: SourceGroundingStatus
    failures: tuple[str, ...] = ()

    @property
    def passed(self) -> bool:
        return self.status in {
            SourceGroundingStatus.VERIFIED,
            SourceGroundingStatus.NOT_APPLICABLE,
        }


def evaluate_source_grounding(
    evidence: tuple[EvidenceItem, ...],
    requirement: VerifierRequirement,
    verifier: SourceGroundingVerifierProtocol | None,
) -> SourceGroundingEvaluation:
    if requirement == VerifierRequirement.NOT_APPLICABLE:
        return SourceGroundingEvaluation(status=SourceGroundingStatus.NOT_APPLICABLE)
    if verifier is None:
        return SourceGroundingEvaluation(
            status=SourceGroundingStatus.MISSING_REQUIRED_VERIFIER,
            failures=("missing_required_source_grounding_verifier",),
        )
    if not evidence:
        return SourceGroundingEvaluation(
            status=SourceGroundingStatus.FAILED,
            failures=("required_source_grounding_has_no_evidence",),
        )
    failures: list[str] = []
    for item in evidence:
        report = verifier.verify(item)
        failures.extend(f"{item.evidence_id}:{failure}" for failure in report.failures)
    return SourceGroundingEvaluation(
        status=(SourceGroundingStatus.FAILED if failures else SourceGroundingStatus.VERIFIED),
        failures=tuple(failures),
    )


def grounding_requirement(metadata: dict[str, object]) -> VerifierRequirement:
    value = metadata.get("source_grounding_requirement", VerifierRequirement.NOT_APPLICABLE.value)
    return VerifierRequirement(str(value))
