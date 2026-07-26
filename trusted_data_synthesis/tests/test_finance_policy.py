from __future__ import annotations

import pytest

from trusted_synthesis.core.evidence.schema import EvidenceBundle, EvidenceItem
from trusted_synthesis.core.evidence.validation import EvidenceValidator
from trusted_synthesis.core.graph.builder import ProofGraphBuilder
from trusted_synthesis.core.task.generator import ProofGraphTaskSynthesizer, TaskSynthesisError
from trusted_synthesis.domains.finance.policy import FinanceSemanticPolicy
from trusted_synthesis.domains.finance.verification import FinanceClaimVerifier


def test_finance_policy_runs_in_evidence_and_task_gates(
    finance_evidence: EvidenceItem,
) -> None:
    policy = FinanceSemanticPolicy()
    report = EvidenceValidator(policy).validate(finance_evidence)

    assert report.passed
    assert any(check.check_id.startswith("domain_semantic:") for check in report.checks)

    incompatible = finance_evidence.model_copy(
        update={
            "evidence_id": "evidence:finance:incompatible@kg_test",
            "assertion_id": "assertion:finance:incompatible",
            "evidence_version_id": "version:finance:incompatible@kg_test",
            "temporal_context": finance_evidence.temporal_context.model_copy(
                update={"basis": "calendar_period"}
            ),
            "provenance": finance_evidence.provenance.model_copy(
                update={"source_record_id": "incompatible"}
            ),
        }
    )
    bundle = EvidenceBundle(
        bundle_id="bundle_finance_policy",
        evidence=(finance_evidence, incompatible),
        purpose="finance policy integration",
    )
    graph = ProofGraphBuilder().build(bundle)

    with pytest.raises(TaskSynthesisError, match="time_basis"):
        ProofGraphTaskSynthesizer(policy).comparison(
            graph,
            bundle,
            finance_evidence.evidence_id,
            incompatible.evidence_id,
        )


def test_finance_claim_verifier_rejects_forbidden_extensions(
    finance_evidence: EvidenceItem,
) -> None:
    verifier = FinanceClaimVerifier()
    support = (finance_evidence,)
    valid = verifier.verify_claim(
        {
            "claim_id": "claim:revenue_observed",
            "claim_type": "observed_metric",
            "predicate": "revenue",
            "evidence_ids": [finance_evidence.evidence_id],
            "subject_ids": [finance_evidence.subject.subject_id],
            "period_labels": [finance_evidence.temporal_context.label],
            "value": "383285",
            "unit": "million USD",
            "currency": "USD",
        },
        support,
    )
    forbidden = verifier.verify_claim(
        {
            "claim_id": "claim:buy",
            "claim_type": "investment_recommendation",
            "predicate": "revenue",
            "evidence_ids": [finance_evidence.evidence_id],
        },
        support,
    )

    assert valid.passed
    assert not forbidden.passed
    assert "forbidden_claim_type" in forbidden.issues


def test_finance_claim_verifier_rejects_unknown_support_without_crashing(
    finance_evidence: EvidenceItem,
) -> None:
    result = FinanceClaimVerifier().verify_claim(
        {
            "claim_id": "claim:unknown_support",
            "claim_type": "observed_metric",
            "predicate": "revenue",
            "evidence_ids": ["evidence:finance:unknown@kg_test"],
        },
        (finance_evidence,),
    )

    assert not result.passed
    assert "supporting_evidence_invalid" in result.issues
