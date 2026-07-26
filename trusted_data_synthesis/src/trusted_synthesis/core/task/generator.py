from __future__ import annotations

from trusted_synthesis.core.evidence.schema import EvidenceBundle, EvidenceItem
from trusted_synthesis.core.task.schema import (
    OperationSpec,
    TaskLevel,
    TaskRequirement,
    TaskSpec,
)
from trusted_synthesis.hashing import canonical_hash


class TaskSynthesisError(ValueError):
    pass


class EvidenceTaskSynthesizer:
    def fact_retrieval(self, bundle: EvidenceBundle, evidence_id: str) -> TaskSpec:
        evidence = self._find(bundle, evidence_id)
        semantics = {
            "kind": "fact_retrieval",
            "evidence_id": evidence.evidence_id,
            "bundle_id": bundle.bundle_id,
        }
        return TaskSpec(
            task_id=canonical_hash(semantics, prefix="task:"),
            domain=evidence.domain,
            level=TaskLevel.FACT_RETRIEVAL,
            instruction=(
                f"What was {evidence.entity.name}'s {evidence.property.name} "
                f"for {evidence.time.label}? Report the value and identify the source."
            ),
            requirements=(
                TaskRequirement.RETRIEVE_EVIDENCE,
                TaskRequirement.SELECT_EVIDENCE,
                TaskRequirement.CITE_SOURCE,
                TaskRequirement.VERIFY_RESULT,
            ),
            operation=OperationSpec(
                operator_id="lookup",
                input_evidence_ids=(evidence.evidence_id,),
                output_schema="value_with_source",
            ),
            evidence_bundle_id=bundle.bundle_id,
            hidden_evidence_ids=(evidence.evidence_id,),
            answer_schema={
                "type": "value_with_source",
                "unit": evidence.unit,
                "currency": evidence.currency,
            },
            metadata={"semantic_key": evidence.semantic_key},
        )

    def comparison(
        self,
        bundle: EvidenceBundle,
        left_evidence_id: str,
        right_evidence_id: str,
    ) -> TaskSpec:
        left = self._find(bundle, left_evidence_id)
        right = self._find(bundle, right_evidence_id)
        self._validate_comparable(left, right)
        semantics = {
            "kind": "comparison",
            "left": left.evidence_id,
            "right": right.evidence_id,
            "bundle_id": bundle.bundle_id,
        }
        return TaskSpec(
            task_id=canonical_hash(semantics, prefix="task:"),
            domain=left.domain,
            level=TaskLevel.EVIDENCE_INTEGRATION,
            instruction=(
                f"Compare {left.property.name} for {left.entity.name} in {left.time.label} "
                f"with {right.entity.name} in {right.time.label}. Which is higher, and by how much?"
            ),
            requirements=(
                TaskRequirement.RETRIEVE_EVIDENCE,
                TaskRequirement.SELECT_EVIDENCE,
                TaskRequirement.CALCULATE,
                TaskRequirement.CITE_SOURCE,
                TaskRequirement.VERIFY_RESULT,
            ),
            operation=OperationSpec(
                operator_id="compare",
                input_evidence_ids=(left.evidence_id, right.evidence_id),
                output_schema="comparison",
            ),
            evidence_bundle_id=bundle.bundle_id,
            hidden_evidence_ids=(left.evidence_id, right.evidence_id),
            answer_schema={
                "type": "comparison",
                "unit": left.unit,
                "currency": left.currency,
                "required_fields": ["higher_evidence_id", "difference"],
            },
            metadata={"comparability_key": left.semantic_key},
        )

    @staticmethod
    def _find(bundle: EvidenceBundle, evidence_id: str) -> EvidenceItem:
        for evidence in bundle.evidence:
            if evidence.evidence_id == evidence_id:
                return evidence
        raise TaskSynthesisError(f"Evidence not found in bundle: {evidence_id}")

    @staticmethod
    def _validate_comparable(left: EvidenceItem, right: EvidenceItem) -> None:
        mismatches = []
        for field, left_value, right_value in (
            ("domain", left.domain, right.domain),
            ("property", left.property.property_id, right.property.property_id),
            ("unit", left.unit, right.unit),
            ("currency", left.currency, right.currency),
            ("period type", left.property.period_type, right.property.period_type),
            (
                "definition comparability",
                left.definition.comparability_level,
                right.definition.comparability_level,
            ),
        ):
            if left_value != right_value:
                mismatches.append(field)
        if mismatches:
            raise TaskSynthesisError(f"Evidence is not comparable: {', '.join(mismatches)}")
