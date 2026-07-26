from __future__ import annotations

from datetime import date
from decimal import Decimal

from trusted_synthesis.core.evaluation.evaluator import QualityEvaluator
from trusted_synthesis.core.evaluation.schema import ReleaseDecision
from trusted_synthesis.core.evidence import (
    EpistemicStatus,
    EvidenceKind,
    ExperimentalResult,
    RuleStatement,
    SourceLocator,
    TemporalContext,
    UncertaintyInterval,
)
from trusted_synthesis.core.evidence.schema import (
    EvidenceBundle,
    EvidenceItem,
    ProvenanceRef,
    SourceAuthority,
    SourceRef,
    SubjectRef,
)
from trusted_synthesis.core.graph.builder import ProofGraphBuilder
from trusted_synthesis.core.task.generator import ProofGraphTaskSynthesizer
from trusted_synthesis.core.trajectory.generator import ReferenceWorkflowCompiler


def _bundle(item: EvidenceItem) -> EvidenceBundle:
    return EvidenceBundle(
        bundle_id=f"bundle:{item.domain}", evidence=(item,), purpose="cross-domain contract"
    )


def _base(domain: str, payload, kind: EvidenceKind, predicate: str) -> EvidenceItem:
    return EvidenceItem(
        evidence_id=f"evidence:{domain}:001@v1",
        assertion_id=f"assertion:{domain}:001",
        evidence_version_id=f"version:{domain}:001@v1",
        domain=domain,
        evidence_kind=kind,
        subject=SubjectRef(
            subject_id=f"{domain}_subject", name=f"{domain.title()} Subject", subject_type=domain
        ),
        predicate=predicate,
        payload=payload,
        temporal_context=TemporalContext(label="effective 2025", valid_to=date(2025, 1, 2)),
        source=SourceRef(
            source_id=f"{domain}_primary",
            name=f"{domain.title()} Primary",
            authority=SourceAuthority.PRIMARY,
        ),
        source_locator=SourceLocator(uri=f"https://example.org/{domain}", text_span="section 1"),
        provenance=ProvenanceRef(
            adapter_id=f"{domain}.v1",
            archive_id=f"{domain}_archive",
            source_record_id=f"{domain}_record_1",
            build_ids={"evidence": "build_1"},
        ),
        epistemic_status=EpistemicStatus.OBSERVED,
        extraction_confidence=1,
    )


def test_same_lookup_program_handles_legal_and_science_payloads() -> None:
    legal = _base(
        "legal",
        RuleStatement(
            rule_text="A filing is required when the threshold is exceeded.",
            conditions=("threshold exceeded",),
            exceptions=("registered exemption",),
            authority="Example Act section 10",
            legal_effect="filing duty",
        ),
        EvidenceKind.RULE,
        "filing_requirement",
    )
    science = _base(
        "science",
        ExperimentalResult(
            metric="test_accuracy",
            value=Decimal("92.4"),
            unit="percent",
            dataset="held-out benchmark",
            method="controlled experiment",
            comparator="baseline",
            uncertainty=UncertaintyInterval(lower=Decimal("91.8"), upper=Decimal("93.0")),
            sample_size=500,
        ),
        EvidenceKind.EXPERIMENTAL_RESULT,
        "experiment_result",
    )

    programs = []
    for item in (legal, science):
        bundle = _bundle(item)
        graph = ProofGraphBuilder().build(bundle)
        task = ProofGraphTaskSynthesizer().fact_retrieval(graph, bundle, item.evidence_id)
        workflow = ReferenceWorkflowCompiler().compile(task, bundle)
        assessment = QualityEvaluator().evaluate(task, bundle, graph, workflow)
        programs.append([node.operator_id for node in task.oracle.task_program.nodes])
        assert assessment.decision == ReleaseDecision.ACCEPTED

    assert programs == [["lookup"], ["lookup"]]
