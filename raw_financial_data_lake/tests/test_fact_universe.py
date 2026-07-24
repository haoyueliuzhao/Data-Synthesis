from __future__ import annotations

import json

from finraw.db.client import MetadataDB
from finraw.fact_universe import (
    DerivedChain,
    active_fact_universe_build_id,
    allocate_stratum_quotas,
    build_fact_universe,
    derived_chain_closure_report,
    select_balanced_derived_members,
    select_derived_chain_priority,
)


def test_allocate_stratum_quotas_is_exact_and_deterministic() -> None:
    counts = {"large": 80, "medium": 15, "small": 5}

    first = allocate_stratum_quotas(counts, 37, minimum_per_stratum=1)
    second = allocate_stratum_quotas(counts, 37, minimum_per_stratum=1)

    assert first == second
    assert sum(first.values()) == 37
    assert all(first[key] >= 1 for key in counts)
    assert all(first[key] <= counts[key] for key in counts)


def test_derived_chain_priority_balances_closed_derived_facts() -> None:
    chains = [
        DerivedChain(
            "cn_1", "yoy_growth", "greater_china", frozenset({"cn_1", "cn_2"})
        ),
        DerivedChain(
            "cn_2", "yoy_growth", "greater_china", frozenset({"cn_2", "cn_3"})
        ),
        DerivedChain(
            "us_1", "yoy_growth", "international", frozenset({"us_1", "us_2"})
        ),
        DerivedChain(
            "us_2", "yoy_growth", "international", frozenset({"us_1", "us_2"})
        ),
        DerivedChain(
            "us_3", "yoy_growth", "international", frozenset({"us_3", "us_4"})
        ),
    ]
    regions = {
        "cn_1": "greater_china",
        "cn_2": "greater_china",
        "cn_3": "greater_china",
        "us_1": "international",
        "us_2": "international",
        "us_3": "international",
        "us_4": "international",
    }

    priority, report = select_derived_chain_priority(
        chains,
        regions,
        broad_fact_budget=4,
        target_greater_china_share=0.5,
        target_fraction=1.0,
        evaluation_interval=1,
    )

    assert priority == {"us_1", "us_2"}
    assert report["target_broad_derived_count"] == 2
    assert report["priority_closed_broad_derived_count"] == 2
    closure = derived_chain_closure_report(
        chains,
        priority | {"cn_1", "cn_2", "cn_3"},
    )
    assert closure["bucket_counts"]["greater_china"] == 2
    assert closure["bucket_counts"]["international"] == 2
    assert closure["greater_china_share"] == 0.5


def test_explicit_derived_members_ignore_accidental_broad_closure() -> None:
    chains = [
        DerivedChain(
            f"cn_{index}",
            "yoy_growth",
            "greater_china",
            frozenset({f"cn_fact_{index}"}),
        )
        for index in range(2)
    ] + [
        DerivedChain(
            f"us_{index}",
            "difference" if index % 2 else "yoy_growth",
            "international",
            frozenset({"us_shared"}),
        )
        for index in range(10)
    ]
    regions = {
        "cn_fact_0": "greater_china",
        "cn_fact_1": "greater_china",
        "us_shared": "international",
    }

    selected, report = select_balanced_derived_members(
        chains,
        set(regions),
        regions,
        target_greater_china_share=0.5,
    )

    assert len(selected) == 4
    assert report["candidate_distribution"]["total"] == 12
    assert report["member_distribution"]["bucket_counts"] == {
        "greater_china": 2,
        "international": 2,
        "mixed_global": 0,
        "unclassified": 0,
    }
    assert report["member_distribution"]["greater_china_share"] == 0.5


def test_build_fact_universe_reports_pinned_derived_build(tmp_path) -> None:
    db = MetadataDB(str(tmp_path / "metadata.sqlite3"))
    db.init_schema()
    try:
        _seed_fact_pool(db)
        for derived_id, entity_id, input_fact_ids in [
            ("cn_yoy", "CN_COMPANY", ["cn_fact_00", "cn_fact_01"]),
            ("us_yoy", "US_COMPANY", ["us_fact_00", "us_fact_01"]),
        ]:
            db.execute(
                "INSERT INTO derived_facts ("
                "derived_id, build_id, input_build_id, derived_type, "
                "input_fact_ids, entity_scope, verification_status, is_active"
                ") VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    derived_id,
                    "derived_build_test",
                    "fact_build_test",
                    "yoy_growth",
                    json.dumps(input_fact_ids),
                    json.dumps({"entity_id": entity_id}),
                    "single_source",
                    1,
                ),
            )

        report = build_fact_universe(
            db,
            {
                "fact_universe": {
                    "enabled": True,
                    "target_greater_china_share": 0.5,
                    "minimum_stratum_coverage": 1.0,
                    "derived_chain_priority": {
                        "enabled": True,
                        "target_fraction": 1.0,
                        "evaluation_interval": 1,
                        "minimum_greater_china_share": 0.4,
                        "maximum_greater_china_share": 0.6,
                    },
                }
            },
        )

        assert report["quality_status"] == "passed"
        assert (
            report["derived_chain_priority"]["input_derived_build_id"]
            == "derived_build_test"
        )
        assert report["derived_chain_priority"]["closure_distribution"]["total"] == 2
        members = db.fetchall(
            "SELECT derived_id, region_bucket "
            "FROM fact_universe_derived_members "
            "WHERE universe_build_id = ? ORDER BY derived_id",
            (report["universe_build_id"],),
        )
        assert [tuple(row) for row in members] == [
            ("cn_yoy", "greater_china"),
            ("us_yoy", "international"),
        ]
    finally:
        db.close()


def test_build_fact_universe_retains_gc_and_balances_broad_facts(tmp_path) -> None:
    db = MetadataDB(str(tmp_path / "metadata.sqlite3"))
    db.init_schema()
    try:
        _seed_fact_pool(db)
        config = {
            "fact_universe": {
                "enabled": True,
                "policy_id": "test_regional_balance",
                "target_greater_china_share": 0.5,
                "include_forecasts": False,
                "minimum_per_stratum": 1,
                "minimum_stratum_coverage": 1.0,
            }
        }

        first = build_fact_universe(db, config, batch_size=3)
        first_members = db.fetchall(
            "SELECT fact_id, region_bucket FROM fact_universe_members "
            "WHERE universe_build_id = ? ORDER BY fact_id",
            (first["universe_build_id"],),
        )

        assert first["quality_status"] == "passed"
        assert first["actual_greater_china_share"] == 0.5
        assert len(first_members) == 8
        assert (
            sum(row["region_bucket"] == "greater_china" for row in first_members) == 4
        )
        assert {
            row["fact_id"]
            for row in first_members
            if row["region_bucket"] == "greater_china"
        } == {f"cn_fact_{index:02d}" for index in range(4)}

        second = build_fact_universe(db, config, batch_size=4)
        second_members = db.fetchall(
            "SELECT fact_id, region_bucket FROM fact_universe_members "
            "WHERE universe_build_id = ? ORDER BY fact_id",
            (second["universe_build_id"],),
        )

        assert first["membership_manifest_hash"] == second["membership_manifest_hash"]
        assert [tuple(row) for row in first_members] == [
            tuple(row) for row in second_members
        ]
        assert (
            active_fact_universe_build_id(
                db,
                input_fact_build_id="fact_build_test",
            )
            == second["universe_build_id"]
        )
        old = db.fetchone(
            "SELECT is_active, superseded_by FROM fact_universe_builds "
            "WHERE universe_build_id = ?",
            (first["universe_build_id"],),
        )
        assert old["is_active"] == 0
        assert old["superseded_by"] == second["universe_build_id"]
    finally:
        db.close()


def _seed_fact_pool(db: MetadataDB) -> None:
    for source_id, market in [
        ("cninfo_announcements", "CN"),
        ("sec_companyfacts", "US"),
    ]:
        db.execute(
            "INSERT INTO source_registry ("
            "source_id, source_name, source_type, authority_level, market, is_active"
            ") VALUES (?, ?, ?, ?, ?, ?)",
            (source_id, source_id, "api", "S1_official", market, 1),
        )
    for entity_id, country, market in [
        ("CN_COMPANY", "CN", "CN"),
        ("US_COMPANY", "US", "US"),
    ]:
        db.execute(
            "INSERT INTO canonical_entities ("
            "entity_id, canonical_name, entity_type, market, country, build_id, is_active"
            ") VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                entity_id,
                entity_id,
                "company",
                market,
                country,
                "entity_build_test",
                1,
            ),
        )
    db.execute(
        "INSERT INTO metrics ("
        "metric_id, canonical_name, metric_category, build_id, is_active"
        ") VALUES (?, ?, ?, ?, ?)",
        ("revenue", "Revenue", "financial_statement", "metric_build_test", 1),
    )

    facts = []
    facts.extend(
        (f"cn_fact_{index:02d}", "CN_COMPANY", "cninfo_announcements", 2020 + index)
        for index in range(4)
    )
    facts.extend(
        (f"us_fact_{index:02d}", "US_COMPANY", "sec_companyfacts", 2010 + index)
        for index in range(12)
    )
    for fact_id, entity_id, source_id, year in facts:
        db.execute(
            "INSERT INTO atomic_facts ("
            "fact_id, build_id, entity_id, metric_id, value, source_id, is_active"
            ") VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                fact_id,
                "atomic_build_test",
                entity_id,
                "revenue",
                year,
                source_id,
                1,
            ),
        )
        db.execute(
            "INSERT INTO standardized_facts ("
            "fact_id, build_id, entity_id, metric_id, normalized_value, "
            "normalized_unit, normalized_currency, period_end, fiscal_year, "
            "frequency, is_forecast, source_id, verification_status, "
            "graph_ready, is_active"
            ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                fact_id,
                "fact_build_test",
                entity_id,
                "revenue",
                year,
                "USD",
                "USD",
                f"{year}-12-31",
                year,
                "annual",
                0,
                source_id,
                "single_source",
                1,
                1,
            ),
        )
