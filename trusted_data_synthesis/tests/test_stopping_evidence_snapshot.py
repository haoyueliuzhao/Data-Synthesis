from __future__ import annotations

from datetime import date

from trusted_synthesis.core.evidence.schema import EvidenceItem, SemanticDefinitionRef, SubjectRef
from trusted_synthesis.experiments.vtdo_experiment.phase1_stopping_evidence_snapshot import (
    _population_identity_matches,
    select_stopping_evidence_snapshot,
    stopping_evidence_snapshot_capacity,
)
from trusted_synthesis.hashing import canonical_hash


def _annual(
    source: EvidenceItem,
    *,
    subject_id: str,
    year: int,
) -> EvidenceItem:
    temporal = source.temporal_context.model_copy(
        update={
            "label": f"FY{year}",
            "valid_from": date(year - 1, 10, 1),
            "valid_to": date(year, 9, 30),
        }
    )
    return source.model_copy(
        update={
            "evidence_id": f"evidence:finance:{subject_id}:revenue:{year}@kg_test",
            "assertion_id": f"assertion:finance:{subject_id}:revenue:{year}",
            "evidence_version_id": (
                f"evidence_version:finance:{subject_id}:revenue:{year}@kg_test"
            ),
            "subject": SubjectRef(
                subject_id=subject_id,
                name=f"Company {subject_id}",
                subject_type="company",
                attributes={"market": "US", "country": "US"},
            ),
            "temporal_context": temporal,
            "scope": source.scope.model_copy(update={"scope_id": subject_id})
            if source.scope
            else None,
            "provenance": source.provenance.model_copy(
                update={"source_record_id": f"{subject_id}:revenue:{year}"}
            ),
            "domain_context": {
                **source.domain_context,
                "fiscal_year": year,
            },
        }
    )


def test_historical_population_identity_is_fail_closed() -> None:
    payload: dict[str, object] = {
        "schema_version": "fixture_population.v1",
        "task_count": 48,
    }
    payload["population_id"] = canonical_hash(payload, prefix="fixture_population:")

    assert _population_identity_matches(payload)
    payload["task_count"] = 49
    assert not _population_identity_matches(payload)


def test_snapshot_selection_preserves_contiguous_peer_series(
    finance_evidence: EvidenceItem,
) -> None:
    evidence = tuple(
        _annual(finance_evidence, subject_id=subject_id, year=year)
        for subject_id in ("AAPL_US", "MSFT_US")
        for year in range(2020, 2026)
    )

    selected = select_stopping_evidence_snapshot(
        evidence,
        maximum_selected_evidence_count=100,
        selection_salt="snapshot-test",
    )
    capacity = stopping_evidence_snapshot_capacity(
        selected,
        selection_salt="snapshot-test",
    )

    assert len(selected) == 12
    assert capacity["temporal_series_count"] == 2
    assert capacity["contiguous_window_count"] == 8
    assert capacity["disjoint_gold_window_capacity"] == 4
    assert capacity["contextual_pair_capacity"] == 6
    assert capacity["period_pair_capacity"] >= 6
    assert capacity["definition_pair_capacity"] == 0
    assert capacity["payload_context_pair_capacity"] == 0


def test_snapshot_selection_drops_non_contiguous_short_fragments(
    finance_evidence: EvidenceItem,
) -> None:
    evidence = tuple(
        _annual(finance_evidence, subject_id="AAPL_US", year=year)
        for year in (2020, 2021, 2023, 2024)
    )

    selected = select_stopping_evidence_snapshot(
        evidence,
        maximum_selected_evidence_count=100,
        selection_salt="snapshot-gap-test",
    )

    assert selected == ()


def test_snapshot_selection_closes_exact_definition_companions(
    finance_evidence: EvidenceItem,
) -> None:
    base = tuple(
        _annual(finance_evidence, subject_id="AAPL_US", year=year) for year in range(2020, 2026)
    )
    target = base[2]
    companion = target.model_copy(
        update={
            "evidence_id": f"{target.evidence_id}:alternate-definition",
            "assertion_id": f"{target.assertion_id}:alternate-definition",
            "evidence_version_id": f"{target.evidence_version_id}:alternate-definition",
            "definition": SemanticDefinitionRef(
                definition_id="definition:alternate-revenue",
                text="Alternate reported revenue definition",
                attributes={"version": "1"},
            ),
            "provenance": target.provenance.model_copy(
                update={
                    "source_record_id": (
                        f"{target.provenance.source_record_id}:alternate-definition"
                    )
                }
            ),
        }
    )
    same_definition_duplicate = target.model_copy(
        update={
            "evidence_id": f"{target.evidence_id}:same-definition",
            "assertion_id": f"{target.assertion_id}:same-definition",
            "evidence_version_id": f"{target.evidence_version_id}:same-definition",
            "provenance": target.provenance.model_copy(
                update={
                    "source_record_id": (f"{target.provenance.source_record_id}:same-definition")
                }
            ),
        }
    )

    selected = select_stopping_evidence_snapshot(
        (*base, companion, same_definition_duplicate),
        maximum_selected_evidence_count=100,
        selection_salt="snapshot-definition-closure-test",
    )
    capacity = stopping_evidence_snapshot_capacity(
        selected,
        selection_salt="snapshot-definition-closure-test",
    )

    selected_ids = {item.evidence_id for item in selected}
    assert companion.evidence_id in selected_ids
    assert same_definition_duplicate.evidence_id not in selected_ids
    assert capacity["definition_pair_capacity"] == 1
