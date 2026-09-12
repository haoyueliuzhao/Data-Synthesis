"""Synthetic controls for actual-period parents and finite panel reconstruction."""

import copy
import json
from collections import Counter
from decimal import Decimal

import pytest
from finraw.derived_facts import _annual_rows, _iter_yoy_and_difference
from test_qa_vnext_catalog_bridge_panels import fixture

from trusted_synthesis.experiments.finance_qa_vnext_eval_readiness import panel, panel_rules
from trusted_synthesis.experiments.finance_qa_vnext_task_build.protocol import (
    CASH,
    FLOW_METRICS,
    METRIC_TAGS,
)


def annual_row(identifier, start, end, amount):
    return {
        "fact_id": identifier,
        "entity_id": "SYNTH",
        "metric_id": "gross_profit",
        "source_id": "sec_companyfacts",
        "fiscal_year": int(end[:4]),
        "fiscal_quarter": "FY",
        "period_start": start,
        "period_end": end,
        "normalized_unit": "million USD",
        "normalized_currency": "USD",
        "value_decimal": Decimal(str(amount)),
        "verification_status": "single_source",
        "confidence_score": 1,
    }


@pytest.mark.parametrize("quantity", ["difference", "yoy_growth"])
def test_actual_annual_derived_parent_survives_skipped_and_duplicate_end_year(quantity):
    rows = [
        annual_row("p", "2018-12-31", "2019-12-29", 100),
        annual_row("q", "2019-12-30", "2021-01-03", 120),
        annual_row("r", "2021-01-04", "2022-01-02", 150),
        annual_row("s", "2022-01-03", "2023-01-01", 180),
        annual_row("t", "2023-01-02", "2023-12-31", 200),
    ]
    report = {"skipped_counts": Counter()}
    annual = _annual_rows(rows, report)
    assert len(annual) == 5
    results = [
        row for row in _iter_yoy_and_difference(annual, report) if row["derived_type"] == quantity
    ]
    assert len(results) == 4
    assert [row["input_fact_ids"] for row in results] == [
        ["p", "q"],
        ["q", "r"],
        ["r", "s"],
        ["s", "t"],
    ]
    assert results[-1]["time_scope"]["previous_year"] == results[-1]["time_scope"]["year"] == 2023
    assert results[-1]["time_scope"]["period_start"] == "2023-01-02"


@pytest.mark.parametrize("current_start", ["2020-12-31", "2021-01-02"])
def test_actual_annual_derived_rejects_overlap_or_gap(current_start):
    rows = [
        annual_row("p", "2020-01-01", "2020-12-31", 100),
        annual_row("q", current_start, "2021-12-31", 120),
    ]
    report = {"skipped_counts": Counter()}
    assert not list(_iter_yoy_and_difference(_annual_rows(rows, report), report))
    assert report["skipped_counts"]["annual_actual_flow_gap_or_overlap"] == 1


def test_actual_annual_same_endyear_not_collapsed_in_annual_rows():
    rows = [
        annual_row("p", "2022-01-03", "2023-01-01", 180),
        annual_row("q", "2023-01-02", "2023-12-31", 200),
    ]
    assert len(_annual_rows(rows, {"skipped_counts": Counter()})) == 2


def test_new_rule_is_bounded_and_does_not_authorize_models():
    rule = panel.policy()
    assert rule["model_requests"] == rule["new_downloads"] == 0
    assert rule["previous_registered_impact_rows"] == 886
    assert rule["previous_export_impact_rows"] == 874
    assert rule["compile_reserve_per_group"] == 8
    assert sum(rule["quotas"]["dev"].values()) == 180
    assert sum(rule["quotas"]["confirm"].values()) == 720


@pytest.mark.parametrize("split", ["dev", "confirm"])
def test_new_enumeration_preserves_original_semantic_ids_and_prior_order(split):
    from trusted_synthesis.experiments.finance_qa_vnext_catalog_bridge import panel_rules as old

    facts, bindings, usage, payloads = fixture(split)
    previous, _, _ = old.enumerate_targets(facts, bindings, usage, split, payloads)
    order = [row["task_id"] for group in old.GROUPS for row in reversed(previous[group])]
    selected, rejected = panel_rules.enumerate_all(facts, bindings, usage, split, payloads, order)
    assert not rejected
    for group in old.GROUPS:
        assert [row["task_id"] for row in selected[group]] == [
            row["task_id"] for row in reversed(previous[group])
        ]
        assert {row["task_id"] for row in selected[group]} == {
            row["task_id"] for row in previous[group]
        }
    for group in ("composition_required", "other_financial"):
        for row in selected[group]:
            assert len(row["match"]["target_time_scope"]["actual_periods"]) == 3


def cash_fixture():
    facts, bindings, usage, _ = fixture()
    template_fact = facts["revenue2020"]
    template_binding = bindings["revenue2020"]
    f, b, u = {}, {}, {}
    metrics = [
        CASH,
        *FLOW_METRICS,
        "effect_of_exchange_rate_on_cash_and_cash_equivalents",
        "change_in_cash_including_exchange_rate_effect",
    ]
    specifications = [
        ("previous", CASH, None, "2019-12-31", 100),
        ("current", CASH, None, "2020-12-31", 130),
    ]
    specifications.extend(
        (metric, metric, "2020-01-01", "2020-12-31", amount)
        for metric, amount in zip(metrics[1:], [60, -20, -12, 2, 30], strict=True)
    )
    for key, metric, start, end, amount in specifications:
        f[key] = {
            **template_fact,
            "fact_id": key,
            "metric_id": metric,
            "period_start": start,
            "period_end": end,
            "normalized_value": str(amount),
            "source_definition_id": "definition-" + metric,
        }
        raw = {
            **template_binding["record"],
            "val": amount * 1000000,
            "end": end,
            "accn": "same-accession",
        }
        if start is None:
            raw.pop("start", None)
        else:
            raw["start"] = start
        b[key] = {
            **copy.deepcopy(template_binding),
            "metric_id": metric,
            "tag": METRIC_TAGS[metric][0],
            "source_definition_id": f[key]["source_definition_id"],
            "native_definition": {"label": metric, "description": "Registered US-GAAP " + metric},
            "record": raw,
            "all_equal_source_occurrences": [{"pointer": "/" + key, "record": raw}],
        }
        u[key] = usage["revenue2020"]
    return f, b, u


def test_cash_dual_is_real_balance_and_complete_four_component_relation():
    facts, bindings, usage = cash_fixture()
    lookup = {
        (row["entity_id"], row["metric_id"], row["period_start"], row["period_end"]): row
        for row in facts.values()
    }
    certificate = panel_rules.cash_certificate(
        facts["previous"], facts["current"], lookup, bindings, usage, "dev"
    )
    assert [row["basis"] for row in certificate["witnesses"]] == ["endpoint", "movement"]
    assert all(Decimal(row["output"]["value"]) == 30 for row in certificate["witnesses"])
    assert len(certificate["witnesses"][1]["input_bindings"]) == 4
    assert certificate["account_scope"] == "cash_only"


@pytest.mark.parametrize(
    "mutation", ["missing_fx", "wrong_fx_scope", "gap", "no_common_accession", "bad_closure"]
)
def test_cash_bridge_rejects_incomplete_or_wrongly_typed_relation(mutation):
    facts, bindings, usage = cash_fixture()
    fx = "effect_of_exchange_rate_on_cash_and_cash_equivalents"
    if mutation == "missing_fx":
        del facts[fx]
    elif mutation == "wrong_fx_scope":
        bindings[fx]["tag"] = METRIC_TAGS["effect_of_exchange_rate_on_cash_including_restricted"][0]
    elif mutation == "gap":
        facts[fx]["period_start"] = "2020-01-02"
    elif mutation == "no_common_accession":
        bindings[fx]["all_equal_source_occurrences"][0]["record"]["accn"] = "different"
    else:
        facts["current"]["normalized_value"] = "131"
        bindings["current"]["record"]["val"] = 131000000
    lookup = {
        (row["entity_id"], row["metric_id"], row["period_start"], row["period_end"]): row
        for row in facts.values()
    }
    with pytest.raises(ValueError):
        panel_rules.cash_certificate(
            facts["previous"], facts["current"], lookup, bindings, usage, "dev"
        )


def test_run_rejects_unfrozen_policy_before_source_reads(tmp_path):
    with pytest.raises(ValueError, match="frozen_panel_policy"):
        panel.run(
            tmp_path,
            tmp_path / "out",
            tmp_path / "work",
            expected_policy_id="wrong",
            expected_source_metadata_id="wrong",
            freeze_id="none",
        )
    assert not (tmp_path / "out").exists()


def test_synthetic_actual_native_KG_QA_and_saved_public_export(tmp_path, monkeypatch):
    """Reuse the existing all-synthetic native build; replace only target/export APIs."""
    from test_qa_vnext_catalog_bridge_panels import (
        test_synthetic_real_native_KG_QA_and_export_chain,
    )

    from trusted_synthesis.experiments.finance_qa_vnext_catalog_bridge import (
        panel_rules as old_rules,
    )
    from trusted_synthesis.experiments.finance_qa_vnext_catalog_bridge import (
        panels as old_panels,
    )

    def enumerate_targets(facts, bindings, usage, split, payloads):
        result, rejected = panel_rules.enumerate_all(facts, bindings, usage, split, payloads, [])
        return result, rejected, {}

    def export(
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
        split,
    ):
        for key, native in bindings.items():
            native.setdefault("metric_id", facts[key]["metric_id"])
        compiled = (qa_id, candidates, plans, compilations, {})
        emitted, rejected = panel.export_batch(
            db, kg, compiled, items, facts, bindings, sources, output, split, "synthetic-freeze", {}
        )
        for entry in emitted:
            bundle = json.loads((output / entry["path"]).read_bytes())
            assert bundle["validation"]["actual_period_check"]["passed"]
            assert len(json.loads((output / entry["public_path"]).read_bytes())) == 1
        return emitted, rejected

    monkeypatch.setattr(old_rules, "enumerate_targets", enumerate_targets)
    monkeypatch.setattr(old_panels, "export_batch", export)
    test_synthetic_real_native_KG_QA_and_export_chain(tmp_path, monkeypatch)
