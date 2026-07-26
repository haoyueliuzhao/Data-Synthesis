from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict

from trusted_synthesis.core.evidence.epistemic import EpistemicStatus
from trusted_synthesis.core.evidence.schema import EvidenceItem


class CheckStatus(str, Enum):
    PASSED = "passed"
    FAILED = "failed"
    WARNING = "warning"


class ValidationCheck(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    check_id: str
    status: CheckStatus
    message: str


class EvidenceValidationReport(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    evidence_id: str
    checks: tuple[ValidationCheck, ...]

    @property
    def passed(self) -> bool:
        return all(check.status != CheckStatus.FAILED for check in self.checks)


class EvidenceValidator:
    """Domain-neutral structural validation; domain policies run separately."""

    def __init__(self, semantic_policy: Any | None = None) -> None:
        self._semantic_policy = semantic_policy

    def validate(self, evidence: EvidenceItem) -> EvidenceValidationReport:
        structural = self.validate_structural(evidence)
        domain = self.validate_domain(evidence)
        return EvidenceValidationReport(
            evidence_id=evidence.evidence_id,
            checks=(*structural.checks, *domain.checks),
        )

    def validate_structural(self, evidence: EvidenceItem) -> EvidenceValidationReport:
        checks = [
            self._check_epistemic_status(evidence),
            self._check_version_identity(evidence),
            self._check_lineage(evidence),
            self._check_source_locator(evidence),
            self._check_temporal_consistency(evidence),
            self._check_source_identity(evidence),
        ]
        return EvidenceValidationReport(evidence_id=evidence.evidence_id, checks=tuple(checks))

    def validate_domain(self, evidence: EvidenceItem) -> EvidenceValidationReport:
        if self._semantic_policy is None:
            return EvidenceValidationReport(evidence_id=evidence.evidence_id, checks=())
        report = self._semantic_policy.validate_evidence(evidence)
        checks = tuple(
            _check(
                f"domain_semantic:{check_id}",
                passed,
                f"Domain semantic check passed: {check_id}",
                f"Domain semantic check failed: {check_id}",
            )
            for check_id, passed in sorted(report.checks.items())
        )
        return EvidenceValidationReport(evidence_id=evidence.evidence_id, checks=checks)

    @staticmethod
    def _check_epistemic_status(evidence: EvidenceItem) -> ValidationCheck:
        passed = evidence.epistemic_status not in {
            EpistemicStatus.REJECTED,
            EpistemicStatus.SUPERSEDED,
        }
        return _check(
            "epistemic_status_usable",
            passed,
            "Evidence has a usable epistemic status",
            f"Evidence status is {evidence.epistemic_status}",
        )

    @staticmethod
    def _check_version_identity(evidence: EvidenceItem) -> ValidationCheck:
        passed = bool(evidence.assertion_id and evidence.evidence_version_id)
        return _check(
            "assertion_version_complete",
            passed,
            "Assertion and evidence version identities are complete",
            "Assertion or evidence version identity is missing",
        )

    @staticmethod
    def _check_lineage(evidence: EvidenceItem) -> ValidationCheck:
        provenance = evidence.provenance
        passed = bool(
            provenance.adapter_id
            and provenance.archive_id
            and provenance.source_record_id
            and provenance.build_ids
        )
        return _check(
            "lineage_complete",
            passed,
            "Evidence has archive and build lineage",
            "Lineage is incomplete",
        )

    @staticmethod
    def _check_source_locator(evidence: EvidenceItem) -> ValidationCheck:
        passed = bool(evidence.source_locator)
        return _check(
            "source_span_valid",
            passed,
            "Evidence has a source locator",
            "Evidence has no source locator",
        )

    @staticmethod
    def _check_temporal_consistency(evidence: EvidenceItem) -> ValidationCheck:
        context = evidence.temporal_context
        passed = not (
            context.valid_from and context.valid_to and context.valid_from > context.valid_to
        )
        return _check(
            "temporal_consistency",
            passed,
            "Temporal context is consistent",
            "Temporal context is inconsistent",
        )

    @staticmethod
    def _check_source_identity(evidence: EvidenceItem) -> ValidationCheck:
        passed = bool(evidence.source.source_id and evidence.source.name)
        return _check(
            "source_identity_complete",
            passed,
            "Source identity is complete",
            "Source identity is incomplete",
        )


def _check(
    check_id: str,
    passed: bool,
    passed_message: str,
    failed_message: str,
) -> ValidationCheck:
    return ValidationCheck(
        check_id=check_id,
        status=CheckStatus.PASSED if passed else CheckStatus.FAILED,
        message=passed_message if passed else failed_message,
    )
