from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict

from trusted_synthesis.core.evidence.schema import EvidenceItem, EvidenceStatus


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
    def validate(self, evidence: EvidenceItem) -> EvidenceValidationReport:
        checks = (
            self._check_status(evidence),
            self._check_lineage(evidence),
            self._check_value_contract(evidence),
            self._check_time(evidence),
            self._check_source(evidence),
        )
        return EvidenceValidationReport(evidence_id=evidence.evidence_id, checks=checks)

    @staticmethod
    def _check_status(evidence: EvidenceItem) -> ValidationCheck:
        passed = evidence.status == EvidenceStatus.ACCEPTED
        return ValidationCheck(
            check_id="accepted_evidence_status",
            status=CheckStatus.PASSED if passed else CheckStatus.FAILED,
            message="Evidence is accepted" if passed else f"Evidence status is {evidence.status}",
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
        return ValidationCheck(
            check_id="lineage_complete",
            status=CheckStatus.PASSED if passed else CheckStatus.FAILED,
            message="Evidence has archive and build lineage" if passed else "Lineage is incomplete",
        )

    @staticmethod
    def _check_value_contract(evidence: EvidenceItem) -> ValidationCheck:
        numeric = not isinstance(evidence.value, (str, bool))
        passed = not numeric or bool(evidence.unit)
        return ValidationCheck(
            check_id="numeric_unit_present",
            status=CheckStatus.PASSED if passed else CheckStatus.FAILED,
            message="Value and unit contract is valid"
            if passed
            else "Numeric evidence has no unit",
        )

    @staticmethod
    def _check_time(evidence: EvidenceItem) -> ValidationCheck:
        passed = bool(evidence.time.label and (evidence.time.end or evidence.time.start))
        return ValidationCheck(
            check_id="time_scope_complete",
            status=CheckStatus.PASSED if passed else CheckStatus.FAILED,
            message="Time scope is explicit" if passed else "Time scope has no date boundary",
        )

    @staticmethod
    def _check_source(evidence: EvidenceItem) -> ValidationCheck:
        passed = bool(evidence.source.source_id and evidence.source.name)
        return ValidationCheck(
            check_id="source_identity_complete",
            status=CheckStatus.PASSED if passed else CheckStatus.FAILED,
            message="Source identity is complete" if passed else "Source identity is incomplete",
        )
