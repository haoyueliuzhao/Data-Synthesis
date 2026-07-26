from __future__ import annotations

from datetime import date
from decimal import Decimal

from trusted_synthesis.core.evaluation.evaluator import QualityEvaluator
from trusted_synthesis.core.evaluation.schema import ReleaseDecision
from trusted_synthesis.core.evidence.schema import (
    EntityRef,
    EvidenceBundle,
    EvidenceItem,
    EvidenceStatus,
    PropertyRef,
    ProvenanceRef,
    SourceAuthority,
    SourceRef,
    TimeRef,
)
from trusted_synthesis.core.task.generator import EvidenceTaskSynthesizer
from trusted_synthesis.core.trajectory.generator import DeterministicTrajectoryGenerator


def test_core_pipeline_accepts_science_evidence_without_finance_code() -> None:
    evidence = EvidenceItem(
        evidence_id="evidence:science:experiment_accuracy",
        domain="science",
        entity=EntityRef(
            entity_id="paper_001",
            name="Example Paper",
            entity_type="paper",
        ),
        property=PropertyRef(
            property_id="test_accuracy",
            name="Test Accuracy",
            category="experiment_result",
            period_type="point_in_time",
        ),
        value=Decimal("92.4"),
        unit="percent",
        time=TimeRef(label="experiment run 1", end=date(2025, 1, 2)),
        source=SourceRef(
            source_id="paper_pdf",
            name="Paper PDF",
            authority=SourceAuthority.OFFICIAL,
        ),
        provenance=ProvenanceRef(
            adapter_id="science_memory.v1",
            archive_id="science_test",
            source_record_id="table_2_row_1",
            build_ids={"evidence": "science_build_1"},
        ),
        status=EvidenceStatus.ACCEPTED,
        confidence=1,
    )
    bundle = EvidenceBundle(
        bundle_id="bundle_science",
        evidence=(evidence,),
        purpose="domain transfer test",
    )
    task = EvidenceTaskSynthesizer().fact_retrieval(bundle, evidence.evidence_id)
    trajectory = DeterministicTrajectoryGenerator().generate(task, bundle)

    assert task.domain == "science"
    assert (
        QualityEvaluator().evaluate(task, bundle, trajectory).decision == ReleaseDecision.ACCEPTED
    )
