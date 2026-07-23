from __future__ import annotations

from finraw.fact_standardization import (
    _load_source_definition_context,
    _source_definition_for_fact,
)


class _DefinitionDB:
    def fetchall(self, _sql: str):
        return [
            {
                "definition_id": "sdef_profit_for_year",
                "source_id": "hkex_disclosures",
                "metric_id": "net_income",
                "raw_concept_name": "Profit for the year",
            }
        ]


def test_hkex_compact_source_label_matches_display_definition() -> None:
    context = _load_source_definition_context(_DefinitionDB())

    matched = _source_definition_for_fact(
        {
            "source_id": "hkex_disclosures",
            "metric_id": "net_income",
            "source_field_name": "profitfortheyear",
        },
        context,
    )

    assert matched["definition_id"] == "sdef_profit_for_year"


def test_source_definition_exact_match_still_has_priority() -> None:
    exact = {"definition_id": "exact"}
    normalized = {"definition_id": "normalized"}
    context = {
        ("source", "metric", "Profit for the year"): exact,
        ("source", "metric", "profitfortheyear"): normalized,
    }

    matched = _source_definition_for_fact(
        {
            "source_id": "source",
            "metric_id": "metric",
            "source_field_name": "Profit for the year",
        },
        context,
    )

    assert matched["definition_id"] == "exact"
