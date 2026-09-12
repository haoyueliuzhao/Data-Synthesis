"""Date-driven source/public/Final controls, including real-shaped JNJ years."""

import copy
import json

import pytest
from finraw.qa import operators, pipeline
from finraw.qa.semantic_constraints import (
    SemanticConstraintContext,
    _evaluate_contiguous,
    _evaluate_eq,
)

from trusted_synthesis.experiments.finance_qa_vnext_eval_readiness import periods

CALENDAR = [
    ("2019-01-01", "2019-12-31"),
    ("2020-01-01", "2020-12-31"),
    ("2021-01-01", "2021-12-31"),
]
SEPTEMBER = [
    ("2010-09-27", "2011-09-25"),
    ("2011-09-26", "2012-09-30"),
    ("2012-10-01", "2013-09-29"),
]
SKIPPED_YEAR = [
    ("2018-12-31", "2019-12-29"),
    ("2019-12-30", "2021-01-03"),
    ("2021-01-04", "2022-01-02"),
]
REPEATED_YEAR = [
    ("2010-01-04", "2011-01-02"),
    ("2011-01-03", "2012-01-01"),
    ("2012-01-02", "2012-12-30"),
]


def fixture(actual=SEPTEMBER, quantity="three_year_peak_then_same_period_metric"):
    metrics = ["revenue", "net_income"] if "peak" in quantity else ["revenue"]
    facts, native = {}, {}
    for metric in metrics:
        for index, (start, end) in enumerate(actual):
            identifier = f"{metric}_{index}"
            facts[identifier] = {
                "fact_id": identifier,
                "metric_id": metric,
                "entity_id": "example",
                "period_start": start,
                "period_end": end,
                "frequency": "annual",
                "fiscal_year": int(end[:4]),
                "fiscal_quarter": "FY",
                "normalized_value": str([10, 30, 20][index]),
                "normalized_unit": "million",
                "normalized_currency": "USD",
            }
            native[identifier] = {
                "metric_id": metric,
                "source_cluster": "cik:example",
                "record": {"start": start, "end": end, "fy": 2030},
            }
    target = {
        "actual_periods": [list(pair) for pair in actual],
        "metric_ids": metrics,
        "quantity": quantity,
        "source_cluster": "cik:example",
    }
    if quantity in {"difference", "relative_change"}:
        target.pop("actual_periods")
        target.pop("metric_ids")
        target.update(
            previous_period=list(actual[0]), current_period=list(actual[1]), metric_id=metrics[0]
        )
    return (
        {"task_id": "task_example", "target": target, "match": {"fact_ids": list(facts)}},
        facts,
        native,
    )


def context(facts, kind="mean"):
    primary = [key for key in facts if key.startswith("revenue")]
    secondary = [key for key in facts if key.startswith("net_income")]
    bindings = (
        {"series": primary}
        if kind == "mean"
        else {"primary_series": primary, "secondary_series": secondary}
    )
    return SemanticConstraintContext(
        spec={},
        binding={"input_bindings": bindings},
        fact_map=facts,
        rows=list(facts.values()),
        metric_ontology={},
        policy={},
    )


@pytest.mark.parametrize("actual", [CALENDAR, SEPTEMBER, SKIPPED_YEAR, REPEATED_YEAR])
@pytest.mark.parametrize(
    "quantity", ["three_annual_flow_mean", "three_year_peak_then_same_period_metric"]
)
def test_actual_source_contract_and_saved_public_pass(actual, quantity):
    item, facts, native = fixture(actual, quantity)
    contract = periods.build_contract(item, facts, native)
    question = periods.render_public_periods(contract)
    public = {"question": question, "period_contract": contract}
    messages = [{"role": "user", "content": json.dumps(public)}]
    result = periods.validate_public_periods(
        messages, contract, native, canonical_target=item["target"]
    )
    assert result["passed"], result
    assert all(
        row["label_basis"] == ("calendar_year" if actual == CALENDAR else "actual_interval")
        for row in contract["periods"]
    )
    assert "2030" not in question
    assert "normalized_value" not in question and "fact_id" not in question


@pytest.mark.parametrize("actual", [CALENDAR, SEPTEMBER, SKIPPED_YEAR, REPEATED_YEAR])
def test_source_durations_override_year_index_for_contiguity(actual):
    _, facts, _ = fixture(actual)
    result = _evaluate_contiguous(context(facts), {"field": "periods"})
    assert result.passed, result
    assert "actual_intervals" in result.observed["series"]


@pytest.mark.parametrize("offset", [-1, 1, 7])
def test_gap_and_overlap_rejected_without_year_change(offset):
    from datetime import date, timedelta

    actual = copy.deepcopy(CALENDAR)
    actual[1] = (
        (date.fromisoformat(actual[1][0]) + timedelta(days=offset)).isoformat(),
        actual[1][1],
    )
    item, facts, native = fixture(actual)
    assert not _evaluate_contiguous(context(facts), {"field": "periods"}).passed
    with pytest.raises(ValueError, match="gap_or_overlap"):
        periods.build_contract(item, facts, native)


def test_native_mismatch_fails_even_when_contract_and_fact_agree():
    item, facts, native = fixture()
    native["revenue_0"]["record"]["end"] = "2011-12-31"
    with pytest.raises(ValueError, match="native_date_mismatch"):
        periods.build_contract(item, facts, native)


def test_same_index_different_actual_interval_cannot_supply_secondary():
    item, facts, native = fixture(CALENDAR)
    facts["net_income_1"]["period_start"] = "2020-02-01"
    native["net_income_1"]["record"]["start"] = "2020-02-01"
    assert not _evaluate_eq(
        context(facts, "peak"), {"field": "secondary_period_coverage", "value": 1.0}
    ).passed
    with pytest.raises(ValueError, match="coverage_missing"):
        periods.build_contract(item, facts, native)
    chosen = operators._arg_extreme(
        [[facts[key] for key in facts if key.startswith("revenue")]], {}
    )
    with pytest.raises(operators.OperatorError, match="found 0"):
        operators._select_by_period(
            [chosen, [facts[key] for key in facts if key.startswith("net_income")]], {}
        )


@pytest.mark.parametrize("actual", [SKIPPED_YEAR, REPEATED_YEAR])
def test_peak_lookup_distinguishes_repeated_or_missing_end_year(actual):
    _, facts, _ = fixture(actual)
    primary = [facts[key] for key in facts if key.startswith("revenue")]
    secondary = [facts[key] for key in facts if key.startswith("net_income")]
    chosen = operators._arg_extreme([primary], {})
    selected = operators._select_by_period([chosen, secondary], {})
    assert selected["secondary_fact_id"] == "net_income_1"
    assert selected["actual_period"] == {
        "start": actual[1][0],
        "end": actual[1][1],
        "period_type": "duration",
    }
    assert _evaluate_eq(
        context(facts, "peak"), {"field": "secondary_period_coverage", "value": 1.0}
    ).passed


@pytest.mark.parametrize("quantity", ["difference", "relative_change"])
@pytest.mark.parametrize("actual", [CALENDAR[:2], [(None, "2020-12-31"), (None, "2021-12-31")]])
def test_dual_period_contract_supports_true_flows_and_stock_instants(quantity, actual):
    item, facts, native = fixture(actual, quantity)
    contract = periods.build_contract(item, facts, native)
    assert periods.validate_public_periods(
        periods.render_public_periods(contract), contract, native, canonical_target=item["target"]
    )["passed"]


@pytest.mark.parametrize(
    "mutation",
    [
        "false_calendar",
        "calendar_question",
        "period_line",
        "reverse_set",
        "missing_middle",
        "native_wrong_metric",
        "target_changed",
        "quantity_changed",
        "lowest",
        "FY_alias",
        "envelope_mismatch",
    ],
)
def test_independent_saved_public_validator_rejects_mutations(mutation):
    item, facts, native = fixture()
    contract = periods.build_contract(item, facts, native)
    text = periods.render_public_periods(contract)
    target = copy.deepcopy(item["target"])
    if mutation == "false_calendar":
        contract["periods"][0]["label_basis"] = "calendar_year"
        text = periods.render_public_periods(contract)
    elif mutation == "calendar_question":
        text = "Which calendar year had the highest revenue?\n" + text
    elif mutation == "period_line":
        text = text.replace("2010-09-27 through 2011-09-25", "2011-01-01 through 2011-12-31")
    elif mutation == "reverse_set":
        contract["periods"].reverse()
        text = periods.render_public_periods(contract)
    elif mutation == "missing_middle":
        contract["periods"].pop(1)
        text = periods.render_public_periods(contract)
    elif mutation == "native_wrong_metric":
        native["net_income_1"]["metric_id"] = "operating_income"
    elif mutation == "target_changed":
        target["actual_periods"][0] = ["2011-01-01", "2011-12-31"]
    elif mutation == "quantity_changed":
        target["quantity"] = "three_annual_flow_mean"
    elif mutation == "lowest":
        text = "Select the lowest primary observation.\n" + text
    elif mutation == "FY_alias":
        text = "Compare FY2011 to FY2013.\n" + text
    elif mutation == "envelope_mismatch":
        text = [{"role": "user", "content": json.dumps({"question": text, "period_contract": {}})}]
    result = periods.validate_public_periods(text, contract, native, canonical_target=target)
    assert not result["passed"], (mutation, result)


@pytest.mark.parametrize("quantity", ["difference", "relative_change"])
def test_direction_is_checked_independently_of_numeric_answer(quantity):
    item, facts, native = fixture(CALENDAR[:2], quantity)
    contract = periods.build_contract(item, facts, native)
    text = periods.render_public_periods(contract).replace(
        "current minus previous", "previous minus current"
    )
    result = periods.validate_public_periods(
        text, contract, native, canonical_target=item["target"]
    )
    assert "period.public_direction_reversed" in result["errors"]


@pytest.mark.parametrize("shape", ["id", "dict", "interval"])
def test_final_requires_same_actual_interval(shape):
    item, facts, native = fixture()
    contract = periods.build_contract(item, facts, native)
    selected = contract["periods"][1]
    if shape == "id":
        final = {"period_id": selected["period_id"]}
    elif shape == "dict":
        final = {
            "actual_period": {
                "start": selected["start"],
                "end": selected["end"],
                "period_type": "duration",
            }
        }
    else:
        final = {"period": selected["start"] + "/" + selected["end"]}
    assert periods.validate_final_period(final, contract, selected)["passed"]
    assert not periods.validate_final_period(final, contract, contract["periods"][0])["passed"]


@pytest.mark.parametrize(
    "final",
    [
        {"period": "2012"},
        {"period": 2012},
        {},
        {"period": "2012-01-01/2012-12-31"},
        {"period_id": "period:duration:2011-09-26:2012-09-30", "period": "2012"},
    ],
)
def test_final_year_alias_and_calendar_substitution_fail(final):
    item, facts, native = fixture()
    contract = periods.build_contract(item, facts, native)
    assert not periods.validate_final_period(final, contract)["passed"]


def test_validator_does_not_call_renderer_or_pipeline(monkeypatch):
    item, facts, native = fixture()
    contract = periods.build_contract(item, facts, native)
    text = periods.render_public_periods(contract)

    def forbidden(*args, **kwargs):
        raise AssertionError("generator called by independent checker")

    monkeypatch.setattr(periods, "render_public_periods", forbidden)
    monkeypatch.setattr(periods, "build_contract", forbidden)
    monkeypatch.setattr(periods, "_period", forbidden)
    monkeypatch.setattr(pipeline, "_period_unit_label", forbidden)
    assert periods.validate_public_periods(text, contract, native, canonical_target=item["target"])[
        "passed"
    ]


@pytest.mark.parametrize(
    "prefix",
    [
        "Compare the periods 2011-01-01 through 2011-12-31.",
        "Compare 2013-09-29 through 2010-09-27.",
    ],
)
def test_wrong_actual_question_dates_not_repaired_by_correct_attached_contract(prefix):
    item, facts, native = fixture()
    contract = periods.build_contract(item, facts, native)
    text = prefix + "\n" + periods.render_public_periods(contract)
    assert not periods.validate_public_periods(
        text, contract, native, canonical_target=item["target"]
    )["passed"]


@pytest.mark.parametrize("frequency", ["annual", "ANNUAL", ""])
def test_annual_frequency_never_implies_calendar(frequency):
    assert (
        pipeline._period_unit_label({"basis": "multi_period", "frequency": frequency}) == "period"
    )
    assert (
        pipeline._period_output_format("2011", {"basis": "multi_period", "frequency": frequency})
        == "period_label"
    )


@pytest.mark.parametrize("actual", [CALENDAR, SEPTEMBER, SKIPPED_YEAR, REPEATED_YEAR])
def test_actual_period_scope_overrides_wrong_calendar_semantics(actual):
    scope = {
        "basis": "multi_period",
        "frequency": "annual",
        "start_year": 2011,
        "end_year": 2013,
        "actual_periods": [
            {"period_start": start, "period_end": end, "period_type": "duration"}
            for start, end in actual
        ],
    }
    display = pipeline._question_display_time_scope(
        scope, {"comparability": {"time_basis": "calendar_year"}}
    )
    assert display["basis"] == "actual_period_set"
    assert "start_year" not in display
    assert pipeline._period_unit_label(display) == (
        "calendar year" if actual == CALENDAR else "actual reporting period"
    )
    assert all(
        start in pipeline._period_label(display) and end in pipeline._period_label(display)
        for start, end in actual
    )
    assert pipeline._period_output_format("2012", display) == "actual_interval"
