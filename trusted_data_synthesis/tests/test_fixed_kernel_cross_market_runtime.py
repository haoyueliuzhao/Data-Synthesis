"""Synthetic-only native currency/source/symbolic-proof controls; no live models."""

import copy
import json
from fractions import Fraction

import fixed_kernel_cross_market_runtime_20260926 as m
import pytest

from trusted_synthesis.experiments.finance_qa_vnext_task_build.archive import record


def fact(index, year, value, metric="revenue", currency="HKD"):
    digest = str(year)[-1] * 64
    return {
        "fact_id": "f" + str(index),
        "entity_id": "issuer:test",
        "source_cluster": "issuer_cluster:test",
        "metric_id": metric,
        "source_definition_id": "pdf:def:" + metric,
        "native_definition": {"metric_id": metric, "basis": "HKFRS"},
        "currency": currency,
        "statement_scope": "consolidated_entity",
        "raw_object_id": "pdf" + str(year),
        "raw_sha256": digest,
        "original_url": "https://www.hkexnews.hk/example" + str(year) + ".pdf",
        "native_pointer": "pdf://" + digest + "#page=5&row=" + str(index),
        "record": {"start": f"{year}-01-01", "end": f"{year}-12-31", "val": str(value)},
        "label": metric,
        "evidence": {"page": 5, "raw_value_text": str(value)},
    }


def fixture(facts, family="composition_required", quantity="three_annual_flow_mean"):
    sources = [
        {
            **{
                key: f[key]
                for key in (
                    "raw_object_id",
                    "raw_sha256",
                    "original_url",
                    "native_pointer",
                    "record",
                    "label",
                    "evidence",
                )
            },
            "source_id": f["fact_id"],
            "source_kind": "official_report_pdf_numeric_record",
            "concept": "pdf-financial:" + f["metric_id"],
            "unit": f["currency"],
        }
        for f in facts
    ]
    documents = {
        f["raw_object_id"]: {key: f[key] for key in ("raw_object_id", "raw_sha256", "original_url")}
        for f in facts
    }
    periods = list(
        {f["record"]["end"]: m.runtime.actual_period(f["record"]) for f in facts}.values()
    )
    metrics = list(dict.fromkeys(f["metric_id"] for f in facts))
    public = {
        "question": "Synthetic native-currency arithmetic control.",
        "sources": sources,
        "source_documents": list(documents.values()),
        "period_contract": {
            "task_id": "synthetic",
            "periods": periods,
            "quantity": quantity,
            "metric_ids": metrics,
            "operation": {
                "kind": "arithmetic_mean"
                if family == "composition_required"
                else "argmax_then_lookup"
            },
        },
        "quantity_contract": {"unit": "million " + facts[0]["currency"], "decimal_places": 6},
        "source_policy": {"kind": "all_prequalified_fixed_window_records"},
        "tool_contract": {"native_currency_only": True},
    }
    messages = [{"role": "user", "content": json.dumps(public)}]
    identity = dict(
        task_id="synthetic",
        family=family,
        surface_version_id="synthetic-view",
        public_messages_sha256=m.p.sha(m.p.encode(messages)),
        parent_manifest_id="synthetic-panel",
    )
    certificate = record(
        "panel_composition_certificate"
        if family == "composition_required"
        else "panel_other_financial_certificate",
        complete=True,
        leaf_fact_ids=[f["fact_id"] for f in facts],
    )
    target = dict(
        quantity=quantity,
        metric_ids=metrics,
        unit=public["quantity_contract"]["unit"],
        actual_periods=[[period["start"], period["end"]] for period in periods],
    )
    bundle = dict(
        task_id="synthetic",
        family=family,
        source_cluster="issuer_cluster:test",
        public=public,
        private=dict(canonical_target=target, relation_certificate=certificate),
    )
    return public, messages, identity, bundle, {f["fact_id"]: f for f in facts}


def evaluate(parts, actions):
    public, messages, identity, bundle, natives = parts
    runtime = m.build_runtime()
    sources = runtime.Sources(public)
    session = runtime.generate(
        messages,
        identity,
        sources,
        scripted=[json.dumps(action) for action in actions],
        requested_basis="neutral",
    )
    return session, runtime.assess_session(session, bundle, natives, sources)


def read(identifier, unit="million HKD"):
    return {"tool": "read_source", "arguments": {"source_id": identifier, "unit": unit}}


@pytest.mark.parametrize("currency", m.CURRENCIES)
def test_three_actual_period_mean_native_currency(currency):
    parts = fixture([fact(i, 2020 + i, (i + 1) * 1000000, currency=currency) for i in range(3)])
    unit = "million " + currency
    session, assessed = evaluate(
        parts,
        [
            *[read("f" + str(i), unit) for i in range(3)],
            {
                "tool": "calculate",
                "arguments": {
                    "expression": "(a+b+c)/3",
                    "variables": {
                        name: {"result_id": "tool:" + str(index + 1)}
                        for index, name in enumerate("abc")
                    },
                    "unit": unit,
                },
            },
            {"final": {"value": "2", "unit": unit, "result_id": "tool:4"}},
        ],
    )
    assert assessed["financial_valid"] is True
    assert assessed["actual_method"] == "temporal_component_integration"
    assert session["source_view_runtime_binding_id"] == m.binding()["id"]


def test_answer_only_constant_does_not_supply_financial_proof():
    parts = fixture([fact(i, 2020 + i, (i + 1) * 1000000) for i in range(3)])
    _, assessed = evaluate(
        parts,
        [
            {
                "tool": "calculate",
                "arguments": {"expression": "2", "variables": {}, "unit": "million HKD"},
            },
            {"final": {"value": "2", "unit": "million HKD", "result_id": "tool:1"}},
        ],
    )
    assert assessed["financial_valid"] is False


def test_no_cross_currency_conversion():
    with pytest.raises(ValueError, match="no_cross_currency"):
        m.convert(Fraction(1), "HKD", "CNY")


def test_no_cross_currency_arithmetic_even_ratio():
    prior = {
        "tool:1": {"status": "ok", "result": {"exact_value": "3", "unit": "HKD"}},
        "tool:2": {"status": "ok", "result": {"exact_value": "2", "unit": "CNY"}},
    }
    with pytest.raises(ValueError, match="no_cross_currency_arithmetic"):
        m.calculate_with_units(
            {
                "expression": "a/b",
                "variables": {"a": {"result_id": "tool:1"}, "b": {"result_id": "tool:2"}},
            },
            prior,
        )


def test_multi_document_same_currency_and_tampered_hash_rejected():
    public, *_ = fixture([fact(i, 2020 + i, i + 1) for i in range(3)])
    assert len(m.SourceViewSources(public).references) == 3
    public["source_documents"][0]["raw_sha256"] = "x" * 64
    with pytest.raises(ValueError, match="exact_original_document_join"):
        m.SourceViewSources(public)


def test_pdf_pointer_not_fake_sec_pointer():
    public, *_ = fixture([fact(i, 2020 + i, i + 1) for i in range(3)])
    public["sources"][0]["native_pointer"] = "/facts/us-gaap/Revenues/units/USD/0"
    with pytest.raises(ValueError, match="real_pdf_native_source"):
        m.SourceViewSources(public)


def test_equal_values_different_metric_not_aliases():
    parts = fixture([fact(i, 2020 + i, 1000000) for i in range(3)])
    altered = copy.deepcopy(parts[-1]["f0"])
    altered.update(
        metric_id="net_income",
        source_definition_id="different",
        native_definition={"metric_id": "net_income"},
    )
    support = m.Support(parts[3], {**parts[-1], "alternative": altered}, {})
    assert support.symbols["f0"] != support.symbols["alternative"]


def test_peak_lookup_requires_all_periods_and_exact_selected_interval():
    facts = [fact(i, 2020 + i, value) for i, value in enumerate((3000000, 5000000, 4000000))]
    facts += [fact(i + 3, 2020 + i, 1000000 + i * 100000, "net_income") for i in range(3)]
    parts = fixture(facts, "other_financial", "three_year_peak_then_same_period_metric")
    actions = [
        *[read("f" + str(i)) for i in range(3)],
        {"tool": "select_max", "arguments": {"result_ids": ["tool:1", "tool:2", "tool:3"]}},
        read("f4"),
        {
            "tool": "lookup_selected",
            "arguments": {"selection_result_id": "tool:4", "source_result_id": "tool:5"},
        },
        {
            "final": {
                "value": "1.1",
                "unit": "million HKD",
                "result_id": "tool:6",
                "period_id": "period:duration:2021-01-01:2021-12-31",
            }
        },
    ]
    _, assessed = evaluate(parts, actions)
    assert assessed["financial_valid"] is True, assessed
    actions[-1]["final"]["period_id"] = "period:duration:2020-01-01:2020-12-31"
    _, assessed = evaluate(parts, actions)
    assert assessed["financial_valid"] is False


def test_first_final_stops_even_if_wrong():
    parts = fixture([fact(i, 2020 + i, i + 1) for i in range(3)])
    session, assessed = evaluate(parts, [{"final": {"value": "2"}}, read("f0")])
    assert len(session["turns"]) == 1
    assert assessed["financial_valid"] is False


def dual_fixture(relative=False):
    facts = [
        fact(0, 2020, 20000000, "gross_profit"),
        fact(1, 2021, 30000000, "gross_profit"),
        fact(2, 2020, 100000000, "revenue"),
        fact(3, 2020, -80000000, "cost_of_revenue"),
        fact(4, 2021, 120000000, "revenue"),
        fact(5, 2021, -90000000, "cost_of_revenue"),
    ]
    parts = fixture(facts, "dual_sufficient", "relative_change" if relative else "difference")
    public, _, _, bundle, _ = parts
    public["period_contract"]["metric_ids"] = ["gross_profit"]
    public["period_contract"]["operation"] = {
        "kind": "relative_change" if relative else "difference",
        "direction": "current_minus_previous",
    }
    endpoint = record(
        "financial_witness",
        basis="endpoint",
        input_bindings={"previous": "f0", "current": "f1"},
        operator_dag={
            "operators": [
                {
                    "step_id": "change",
                    "operator": "difference",
                    "inputs": [{"binding": "previous"}, {"binding": "current"}],
                }
            ],
            "output_step": "change",
        },
    )
    movement = record(
        "financial_witness",
        basis="movement",
        input_bindings={
            "previous_revenue": "f2",
            "previous_cost": "f3",
            "current_revenue": "f4",
            "current_cost": "f5",
        },
        operator_dag={
            "operators": [
                {
                    "step_id": "previous",
                    "operator": "sum",
                    "inputs": [{"binding": "previous_revenue"}, {"binding": "previous_cost"}],
                },
                {
                    "step_id": "current",
                    "operator": "sum",
                    "inputs": [{"binding": "current_revenue"}, {"binding": "current_cost"}],
                },
                {
                    "step_id": "change",
                    "operator": "difference",
                    "inputs": [{"step": "previous"}, {"step": "current"}],
                },
            ],
            "output_step": "change",
        },
    )
    certificate = record(
        "financial_relation_certificate",
        complete=True,
        family="annual_flow",
        leaf_fact_ids=[f["fact_id"] for f in facts],
        public_fact_ids=[f["fact_id"] for f in facts],
        previous_component_fact_ids=["f2", "f3"],
        previous_component_coefficients=[1, 1],
        witnesses=[endpoint, movement],
    )
    target = dict(
        source_cluster="issuer_cluster:test",
        quantity="relative_change" if relative else "difference",
        metric_id="gross_profit",
        previous_period=["2020-01-01", "2020-12-31"],
        current_period=["2021-01-01", "2021-12-31"],
        unit="percent" if relative else "million HKD",
    )
    if relative:
        public["quantity_contract"]["unit"] = "percent"
        public["period_contract"]["operation"].update(
            denominator="strictly_positive_previous", multiplier=100
        )
        outer = []
        for witness in (endpoint, movement):
            dag = copy.deepcopy(witness["operator_dag"])
            denominator = (
                {"binding": "previous"} if witness["basis"] == "endpoint" else {"step": "previous"}
            )
            dag["operators"].append(
                {
                    "step_id": "growth",
                    "operator": "ratio_percent",
                    "inputs": [{"step": "change"}, denominator],
                }
            )
            dag["output_step"] = "growth"
            outer.append(
                record(
                    "financial_witness",
                    basis=witness["basis"],
                    input_bindings=witness["input_bindings"],
                    operator_dag=dag,
                )
            )
        certificate = record(
            "relative_quantity_certificate",
            quantity="relative_change",
            family="annual_flow",
            base_relation_certificate=certificate,
            leaf_fact_ids=certificate["leaf_fact_ids"],
            public_fact_ids=certificate["public_fact_ids"],
            witnesses=outer,
        )
    bundle["private"].update(canonical_target=target, relation_certificate=certificate)
    messages = [{"role": "user", "content": json.dumps(public)}]
    identity = {**parts[2], "public_messages_sha256": m.p.sha(m.p.encode(messages))}
    return public, messages, identity, bundle, parts[-1]


@pytest.mark.parametrize("relative", [False, True])
@pytest.mark.parametrize("movement", [False, True])
def test_gross_profit_signed_cost_two_paths_and_growth(relative, movement):
    parts = dual_fixture(relative)
    indices = [2, 3, 4, 5] if movement else [0, 1]
    variables = {
        name: {"result_id": "tool:" + str(index + 1)}
        for index, name in enumerate("abcd" if movement else "ab")
    }
    expression = "(c+d)-(a+b)" if movement else "b-a"
    if relative:
        expression = "(" + expression + ")/(a+b)" if movement else "(b-a)/a"
    unit = "percent" if relative else "million HKD"
    actions = [
        *[read("f" + str(i)) for i in indices],
        {
            "tool": "calculate",
            "arguments": {"expression": expression, "variables": variables, "unit": unit},
        },
        {
            "final": {
                "value": "50" if relative else "10",
                "unit": unit,
                "result_id": "tool:" + str(len(indices) + 1),
            }
        },
    ]
    _, assessed = evaluate(parts, actions)
    assert assessed["financial_valid"] is True, assessed
    assert assessed["actual_method"] == ("movement" if movement else "endpoint")


def test_invalid_private_certificate_is_fatal_not_zero_reward():
    parts = dual_fixture()
    parts[3]["private"]["relation_certificate"]["complete"] = False
    with pytest.raises(ValueError, match="record_identity"):
        evaluate(parts, [{"final": {"value": "10", "unit": "million HKD", "result_id": "tool:1"}}])
