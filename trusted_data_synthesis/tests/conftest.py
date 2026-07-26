from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from trusted_synthesis.core.evidence.schema import (
    DefinitionRef,
    EntityRef,
    EvidenceItem,
    EvidenceStatus,
    PropertyRef,
    ProvenanceRef,
    SourceAuthority,
    SourceRef,
    TimeRef,
)


@pytest.fixture
def finance_evidence() -> EvidenceItem:
    return EvidenceItem(
        evidence_id="evidence:finance:fact_revenue_2023",
        domain="finance",
        entity=EntityRef(
            entity_id="AAPL_US",
            name="Apple Inc.",
            entity_type="company",
            market="US",
            country="US",
        ),
        property=PropertyRef(
            property_id="revenue",
            name="Revenue",
            category="financial_statement",
            period_type="period_flow",
        ),
        value=Decimal("383285"),
        unit="million USD",
        currency="USD",
        time=TimeRef(
            label="FY2023",
            start=date(2022, 9, 25),
            end=date(2023, 9, 30),
            basis="fiscal_period",
            frequency="annual",
        ),
        source=SourceRef(
            source_id="sec_companyfacts",
            name="SEC Company Facts",
            authority=SourceAuthority.OFFICIAL,
            provider="SEC",
            uri="https://data.sec.gov/",
        ),
        definition=DefinitionRef(
            definition_id="sdef_revenue",
            text="GAAP revenue reported in the filing.",
            comparability_level="xbrl_concept_level",
        ),
        provenance=ProvenanceRef(
            adapter_id="finance_archive.v1",
            archive_id="finance_kg:kg_test",
            source_record_id="fact_revenue_2023",
            raw_object_id="raw_10k_2023",
            build_ids={"kg": "kg_test", "standardized_fact": "fact_build_test"},
        ),
        status=EvidenceStatus.ACCEPTED,
        confidence=0.99,
    )
