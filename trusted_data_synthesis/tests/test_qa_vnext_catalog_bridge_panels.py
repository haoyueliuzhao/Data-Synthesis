"""Synthetic controls only: no production panel enumeration or remote requests."""

import copy
import hashlib
import json
from decimal import Decimal
from pathlib import Path

import pytest
from finraw.qa.graph_patterns import get_pattern
from finraw.qa.plans import execute_plan
from finraw.qa.semantic_constraints import validate_semantic_constraints

from trusted_synthesis.experiments.finance_qa_vnext_catalog_bridge import (
    panel_native,
    panel_rules,
    panels,
)
from trusted_synthesis.experiments.finance_qa_vnext_task_build.protocol import (
    METRIC_TAGS,
    SPLIT_SALT,
    source_split,
)


def fixture(split="dev"):
    cik = next(
        str(i).zfill(10) for i in range(1, 1000) if source_split("cik:" + str(i).zfill(10)) == split
    )
    cluster = "cik:" + cik
    definitions = {
        "gross_profit": (
            "Aggregate revenue less cost of goods and services sold or operating expenses "
            "directly attributable to the revenue generation activity."
        ),
        "revenue": "Amount of revenue recognized from goods sold and services rendered.",
        "cost_of_revenue": (
            "The aggregate costs related to goods produced and sold and services rendered "
            "by an entity during the reporting period."
        ),
        "net_income": "Net income attributable to the consolidated entity.",
        "operating_income": "Income from operations during the reporting period.",
        "net_cash_provided_by_used_in_operating_activities": (
            "Net cash provided by or used in operating activities."
        ),
    }
    amounts = {
        2019: [30, 100, 70, 10, 15, 20],
        2020: [40, 130, 90, 20, 25, 35],
        2021: [50, 120, 70, 15, 20, 30],
    }
    facts, bindings, usage = {}, {}, {}
    payload = {"cik": int(cik), "facts": {"us-gaap": {}}}
    for year, values in amounts.items():
        for metric, amount in zip(definitions, values, strict=True):
            key = metric + str(year)
            tag = "CostOfRevenue" if metric == "cost_of_revenue" else METRIC_TAGS[metric][0]
            native = {
                "val": amount * 1000000,
                "start": f"{year}-01-01",
                "end": f"{year}-12-31",
                "fy": year,
                "fp": "FY",
                "form": "10-K",
                "filed": f"{year + 1}-02-15",
                "accn": f"filing-{year}",
            }
            concept = payload["facts"]["us-gaap"].setdefault(
                tag, {"label": metric, "description": definitions[metric], "units": {"USD": []}}
            )
            pointer = f"/facts/us-gaap/{tag}/units/USD/{len(concept['units']['USD'])}"
            concept["units"]["USD"].append(native)
            facts[key] = {
                "fact_id": key,
                "entity_id": "SYNTH_US",
                "entity_type": "company",
                "metric_id": metric,
                "normalized_value": str(amount),
                "normalized_unit": "million USD",
                "normalized_currency": "USD",
                "period_start": native["start"],
                "period_end": native["end"],
                "fiscal_year": year,
                "fiscal_quarter": "FY",
                "source_definition_id": "definition-" + metric,
                "source_id": "sec_companyfacts",
                "raw_object_id": "raw1",
                "graph_ready": 1,
                "verification_status": "single_source",
                "frequency": "annual",
                "time_basis": "fiscal_period",
                "is_forecast": False,
                "financial_scope_type": "consolidated_entity",
                "entity_scope_id": "SYNTH_US",
                "comparability_level": "xbrl_concept_level",
                "vintage_policy": "fixed_native",
                "metric_period_type": "period_flow",
            }
            bindings[key] = {
                "entity_id": "SYNTH_US",
                "tag": tag,
                "source_definition_id": "definition-" + metric,
                "source_cluster": cluster,
                "split": split,
                "allowed_uses": [split],
                "raw_object_id": "raw1",
                "raw_sha256": "0" * 64,
                "record": native,
                "pointer": pointer,
                "native_definition": {"label": metric, "description": definitions[metric]},
                "document_id": "doc1",
                "all_equal_source_occurrences": [{"pointer": pointer, "record": native}],
            }
            usage[key] = {"split": split, "allowed_uses": [split], "source_cluster": cluster}
    return facts, bindings, usage, {"raw1": payload}


def enumerate_fixture(split="dev"):
    facts, bindings, usage, payloads = fixture(split)
    selected, rejected, report = panel_rules.enumerate_targets(
        facts, bindings, usage, split, payloads
    )
    return facts, bindings, usage, payloads, selected, rejected, report


def test_frozen_panel_scope_and_no_request_budget():
    policy = panels.policy()
    assert policy["source_split_salt"] == SPLIT_SALT
    assert sum(policy["per_group_targets"]["dev"].values()) == 180
    assert sum(policy["per_group_targets"]["confirm"].values()) == 720
    assert policy["new_API_requests"] == 0
    assert not policy["score"]["Teacher_success_selection"]
    assert not policy["historical_train_dev_issuers_blanket_excluded"]


@pytest.mark.parametrize("split", ["dev", "confirm"])
def test_three_groups_have_distinct_registered_structures_and_exact_targets(split):
    facts, bindings, usage, payloads, selected, rejected, report = enumerate_fixture(split)
    assert report["qualified_counts"] == {
        "dual_sufficient": 4,
        "composition_required": 4,
        "other_financial": 2,
    }
    assert not rejected
    for items in selected.values():
        for item in items:
            pattern = get_pattern(item["pattern_id"])
            check = validate_semantic_constraints(
                pattern,
                item["match"],
                facts,
                {key: {"period_type": "period_flow"} for key in METRIC_TAGS},
                panel_rules.semantic_policy(),
            )
            assert check.passed, check.errors
            result = execute_plan(pattern.operator_template, item["match"]["input_bindings"], facts)
            assert result.status == "passed", result.errors
            expected = panel_rules.independent_answer(item, facts)
            assert Decimal(expected["value"]) == Decimal(result.output["value"])
            if "period" in expected:
                assert str(result.output["period"]) == expected["period"]


def test_dual_evidence_genuinely_source_disjoint_for_amount_and_rate():
    *_, selected, rejected, report = enumerate_fixture()
    for item in selected["dual_sufficient"]:
        left, right = item["certificate"]["witnesses"]
        assert Decimal(left["output"]["value"]) == Decimal(right["output"]["value"])
        assert set(left["input_bindings"].values()).isdisjoint(right["input_bindings"].values())
        assert all(not row["is_Teacher_trajectory"] for row in (left, right))


def test_middle_annual_component_changes_mean_without_changing_endpoints():
    facts, bindings, usage, payloads, selected, *_ = enumerate_fixture()
    item = next(
        row
        for row in selected["composition_required"]
        if row["target"]["metric_ids"] == ["net_income"]
    )
    original = panel_rules.independent_answer(item, facts)
    changed = copy.deepcopy(facts)
    changed["net_income2020"]["normalized_value"] = "23"
    alternate = panel_rules.independent_answer(item, changed)
    assert Decimal(alternate["value"]) - Decimal(original["value"]) == 1
    assert changed["net_income2019"] == facts["net_income2019"]
    assert changed["net_income2021"] == facts["net_income2021"]
    assert item["certificate"]["complete_original_snapshot_available"]


@pytest.mark.parametrize("metric", ["net_income", "revenue"])
def test_same_concept_whole_window_source_is_not_hidden_to_force_integration(metric):
    facts, bindings, usage, payloads = fixture()
    tag = METRIC_TAGS[metric][0]
    payloads["raw1"]["facts"]["us-gaap"][tag]["units"]["USD"].append(
        {"start": "2019-01-01", "end": "2021-12-31", "val": 45000000}
    )
    selected, failures, _ = panel_rules.enumerate_targets(facts, bindings, usage, "dev", payloads)
    assert len(selected["composition_required"]) == 3
    assert len(selected["other_financial"]) == 2
    assert any(
        row["reason"] == "panel.full_source_contains_same_concept_window_aggregate"
        for row in failures
    )
    assert payloads["raw1"]["facts"]["us-gaap"][tag]["units"]["USD"][-1]["val"] == 45000000


@pytest.mark.parametrize("change", ["native_label", "usage_label", "CIK_label"])
def test_split_cannot_be_changed_by_relabeling(change):
    facts, bindings, usage, payloads = fixture()
    key = "net_income2019"
    if change == "native_label":
        bindings[key]["split"] = "confirm"
    elif change == "usage_label":
        usage[key] = {"split": "confirm", "allowed_uses": ["confirm"]}
    else:
        bindings[key]["source_cluster"] = next(
            "cik:" + str(i).zfill(10)
            for i in range(1, 1000)
            if source_split("cik:" + str(i).zfill(10)) == "train"
        )
    with pytest.raises(ValueError):
        panel_rules.basic([facts[key]], bindings, usage, "dev")


def test_native_selector_verifies_CIK_and_original_split():
    facts, bindings, usage, payloads = fixture()
    entity = {"entity_id": "SYNTH_US", "cik": str(payloads["raw1"]["cik"])}
    raw = {"raw_object_id": "raw1", "content_sha256": "0" * 64}
    selected, _, _ = panel_native.select_native(payloads["raw1"], entity, raw, expected_split="dev")
    assert len(selected) == len(facts)
    assert all(row["split"] == "dev" and row["allowed_uses"] == ["dev"] for row in selected)
    with pytest.raises(ValueError, match="original_salt"):
        panel_native.select_native(payloads["raw1"], entity, raw, expected_split="confirm")
    wrong = copy.deepcopy(payloads["raw1"])
    wrong["cik"] += 1
    with pytest.raises(ValueError, match="CIK_join"):
        panel_native.select_native(wrong, entity, raw, expected_split="dev")


@pytest.mark.parametrize("change", ["gap", "definition", "unit", "missing_middle", "peak_tie"])
def test_period_definition_unit_and_peak_ambiguity_rejections(change):
    facts, bindings, usage, payloads = fixture()
    if change == "gap":
        for key in facts:
            if key.endswith("2020"):
                facts[key]["period_start"] = "2020-01-02"
                bindings[key]["record"]["start"] = "2020-01-02"
    elif change == "definition":
        facts["net_income2020"]["source_definition_id"] = "changed"
        bindings["net_income2020"]["source_definition_id"] = "changed"
    elif change == "unit":
        facts["net_income2020"]["normalized_unit"] = "USD"
    elif change == "missing_middle":
        del facts["net_income2020"]
    else:
        facts["revenue2021"]["normalized_value"] = "130"
        bindings["revenue2021"]["record"]["val"] = 130000000
    selected, rejected, _ = panel_rules.enumerate_targets(facts, bindings, usage, "dev", payloads)
    assert rejected
    if change == "peak_tie":
        assert not selected["other_financial"]
        assert any(row["reason"] == "panel.ambiguous_primary_peak" for row in rejected)
    else:
        assert not any(
            row["target"]["metric_ids"] == ["net_income"]
            for row in selected["composition_required"]
        )


def test_peak_lookup_is_not_a_change_or_average_template():
    facts, bindings, usage, payloads, selected, *_ = enumerate_fixture()
    for item in selected["other_financial"]:
        assert item["pattern_id"] == "temporal_argmax_then_metric_lookup"
        assert [
            step["operator"]
            for step in item["certificate"]["witnesses"][0]["operator_dag"]["operators"]
        ] == ["argmax", "select_by_period"]
        assert panel_rules.independent_answer(item, facts)["period"] == "2020"


@pytest.mark.parametrize(
    "final,correct",
    [
        ({"value": "20", "unit": "million USD", "period": 2020}, True),
        ({"value": "20", "unit": "USD", "period": 2020}, False),
        ({"value": "20", "unit": "million USD", "period": 2019}, False),
        ({"value": "20", "unit": "million USD"}, False),
        ({"value": "NaN", "unit": "million USD", "period": 2020}, False),
    ],
)
def test_fixed_final_scoring_is_not_primary_trace_qualification(final, correct):
    score = panels.score_final(
        final, {"value": "20", "period": "2020"}, "three_year_peak_then_same_period_metric"
    )
    assert score["target_correct"] is correct
    assert score["complete_trajectory_qualified"] is None
    assert not score["is_primary_utility_score"]


def test_complete_original_source_access_includes_nonreference_records(tmp_path):
    source = {"selected": {"annual": [1, 2, 3]}, "unrelated_original_concept": {"endpoint": 999}}
    raw = json.dumps(source).encode()
    path = tmp_path / "original.json"
    path.write_bytes(raw)
    reference = {
        "complete_original_snapshot": {
            "path": "original.json",
            "sha256": hashlib.sha256(raw).hexdigest(),
            "bytes": len(raw),
        }
    }
    assert panels.read_complete_source(tmp_path, reference) == source
    assert (
        panels.read_complete_source(
            tmp_path, reference, pointer="/unrelated_original_concept/endpoint"
        )
        == 999
    )
    assert panels.read_complete_source(tmp_path, reference, pointer="/selected/annual/1") == 2
    path.write_bytes(raw + b" ")
    with pytest.raises(ValueError, match="snapshot_identity"):
        panels.read_complete_source(tmp_path, reference)


def test_source_cluster_count_not_multiplied_by_quantity_or_window():
    rows = [
        {"source_cluster": "cik:1", "raw_snapshot_sha256": "raw1", "periods": ["2019", "2020"]},
        {"source_cluster": "cik:1", "raw_snapshot_sha256": "raw1", "periods": ["2020", "2021"]},
    ]
    result = panels.correlation_report(rows)
    assert result["task_count"] == 2
    assert result["source_CIK_cluster_count"] == result["original_snapshot_count"] == 1
    assert result["overlapping_issuer_period_pairs"] == 1
    assert not result["effective_sample_size_or_power_inferred"]


def test_no_production_run_without_frozen_rule_identity(tmp_path):
    with pytest.raises(ValueError, match="frozen_rule_identity"):
        panels.run(
            tmp_path,
            tmp_path / "output",
            tmp_path / "work",
            expected_policy_id="wrong",
            expected_source_metadata_id="wrong",
            freeze_id="x",
        )
    assert not (tmp_path / "output").exists()


def test_synthetic_real_native_KG_QA_and_export_chain(tmp_path, monkeypatch):
    """Original ontology metadata only; every financial amount is synthetic."""
    from finraw.qa import pipeline

    from trusted_synthesis.experiments.finance_qa_vnext_task_build.archive import WORK, RecordDB

    root = Path(__file__).resolve().parents[2]
    real_database = root / WORK / "qa_build.sqlite3"
    if not real_database.exists():
        pytest.skip("optional archived ontology metadata is not installed")
    _, _, _, payloads = fixture()
    payload = payloads["raw1"]
    for tag, concept in payload["facts"]["us-gaap"].items():
        current = dict(concept["units"]["USD"][-1])
        current.update(
            start="2022-01-01", end="2022-12-31", fy=2022, filed="2023-02-15", accn="filing-2022"
        )
        current["val"] += 1000000
        if tag == METRIC_TAGS["revenue"][0]:
            current["val"] += 1000000
        concept["units"]["USD"].append(current)
    raw_bytes = json.dumps(payload).encode()
    (tmp_path / "synthetic.json").write_bytes(raw_bytes)
    archived = RecordDB(str(real_database))
    raw = archived.fetchone("SELECT * FROM raw_objects WHERE source_id='sec_companyfacts' LIMIT 1")
    entity = dict(
        archived.fetchone(
            "SELECT * FROM canonical_entities WHERE entity_type='company' AND market='US' LIMIT 1"
        )
    )
    entity.update(
        entity_id="SYNTH_US",
        canonical_name="Synthetic Panel Control",
        ticker="SYNTH",
        cik=str(payload["cik"]).zfill(10),
    )
    raw.update(
        raw_object_id="raw_panel_synthetic",
        storage_uri="/workspace/Data Synthesis/synthetic.json",
        original_url="https://example.invalid/synthetic.json",
        content_sha256=hashlib.sha256(raw_bytes).hexdigest(),
        content_size_bytes=len(raw_bytes),
    )

    class ArchiveMetadata:
        def fetchall(self, sql, params=()):
            return (
                [entity]
                if sql == "SELECT * FROM canonical_entities"
                else archived.fetchall(sql, params)
            )

        def fetchone(self, sql, params=()):
            return archived.fetchone(sql, params)

        def close(self):
            pass

    def open_db(path):
        return (
            ArchiveMetadata() if str(path).endswith(WORK + "/qa_build.sqlite3") else RecordDB(path)
        )

    monkeypatch.setattr(panel_native, "RecordDB", open_db)
    metadata = {
        "rows": [
            {
                "split": "dev",
                "historical_confirmation_issuer": False,
                "entity": entity,
                "raw_object": raw,
                "source_cluster": "cik:" + entity["cik"],
                "all_pinned_snapshot_references": [raw],
            }
        ]
    }
    output = tmp_path / "panel"
    db, inputs, bindings, native = panel_native.build(
        tmp_path, output, tmp_path / "work" / "native.sqlite3", metadata, "dev"
    )
    try:
        kg = native["kg_build"]
        facts = pipeline._load_facts_by_id(
            db, list(bindings), kg["input_fact_build_id"], kg["input_entity_build_id"]
        )
        usage = {key: {"split": "dev", "allowed_uses": ["dev"]} for key in bindings}
        selected, failures, _ = panel_rules.enumerate_targets(
            facts, bindings, usage, "dev", {raw["raw_object_id"]: payload}
        )
        items = [row for group in panel_rules.GROUPS for row in selected[group]]
        assert all(selected[group] for group in panel_rules.GROUPS), failures
        sources = panels.public_source_index(inputs, facts, bindings, output)
        qa_id, candidates, plans, compilations, validation = panels.compile_batch(
            db, kg, items, facts, bindings, usage, output / "QA", "dev"
        )
        exported, rejected = panels.export_batch(
            db,
            kg,
            qa_id,
            items,
            candidates,
            plans,
            compilations,
            facts,
            bindings,
            usage,
            sources,
            output,
            "dev",
        )
        assert not rejected, (rejected, validation)
        assert len(exported) == len(items) == 18
        assert set(row["family"] for row in exported) == set(panel_rules.GROUPS)
        for row in exported:
            bundle = json.loads((output / row["path"]).read_bytes())
            assert bundle["split"] == "dev"
            assert bundle["Teacher_sessions"] == bundle["Student_sessions"] == 0
            assert "private" not in bundle["public"]
            assert bundle["public"]["source_document"]["native_annual_record_count"] == 24
    finally:
        db.close()
        archived.close()
