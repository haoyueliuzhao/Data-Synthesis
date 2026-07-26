from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from trusted_synthesis.core.evidence import (
    EpistemicStatus,
    EvidenceKind,
    EvidenceScope,
    ScalarObservation,
    SourceLocator,
    TemporalContext,
)
from trusted_synthesis.core.evidence.schema import (
    EvidenceItem,
    ProvenanceRef,
    SemanticDefinitionRef,
    SourceAuthority,
    SourceRef,
    SubjectRef,
)


@pytest.fixture
def finance_evidence() -> EvidenceItem:
    return EvidenceItem(
        evidence_id="evidence:finance:fact_revenue_2023@kg_test",
        assertion_id="assertion:finance:fact_revenue_2023",
        evidence_version_id="version:finance:fact_revenue_2023@kg_test",
        domain="finance",
        evidence_kind=EvidenceKind.SCALAR,
        subject=SubjectRef(
            subject_id="AAPL_US",
            name="Apple Inc.",
            subject_type="company",
            attributes={"market": "US", "country": "US"},
        ),
        predicate="revenue",
        payload=ScalarObservation(value=Decimal("383285"), unit="million USD", currency="USD"),
        temporal_context=TemporalContext(
            label="FY2023",
            valid_from=date(2022, 9, 25),
            valid_to=date(2023, 9, 30),
            basis="fiscal_period",
            frequency="annual",
        ),
        scope=EvidenceScope(
            scope_type="consolidated_company", scope_id="AAPL_US", label="Apple consolidated"
        ),
        source=SourceRef(
            source_id="sec_companyfacts",
            name="SEC Company Facts",
            authority=SourceAuthority.OFFICIAL,
            provider="SEC",
        ),
        source_locator=SourceLocator(uri="https://data.sec.gov/", raw_object_id="raw_10k_2023"),
        definition=SemanticDefinitionRef(
            definition_id="sdef_revenue",
            text="GAAP revenue reported in the filing.",
            attributes={"comparability_level": "xbrl_concept_level"},
        ),
        provenance=ProvenanceRef(
            adapter_id="finance_archive.v2",
            archive_id="finance_kg:kg_test",
            source_record_id="fact_revenue_2023",
            build_ids={"kg": "kg_test", "standardized_fact": "fact_build_test"},
        ),
        epistemic_status=EpistemicStatus.OBSERVED,
        extraction_confidence=0.99,
        domain_context={"fiscal_year": 2023, "statement_type": "income_statement"},
    )
