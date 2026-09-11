"""Synthetic public-source screen controls; no dataset, model or task generation."""

import json
from copy import deepcopy

import pytest

from trusted_synthesis.experiments.finance_qa_vnext_basis_scale_preparation.screen import (
    GROUPS,
    screen_public,
)


def entry(table, *, context=(), table_ori=None):
    result = {
        "id": "SYNTHETIC/2020/public_shape_only-1",
        "filename": "SYNTHETIC/2020/public_shape_only",
        "table": deepcopy(table),
        "pre_text": list(context),
        "post_text": [],
        "qa": {"question": "Original synthetic question; do not rewrite or assign a new task."},
    }
    if table_ori is not None:
        result["table_ori"] = deepcopy(table_ori)
    return result


def stock(*, ending="110", extra=None):
    rows = [
        ["(dollars in millions)", "2019"],
        ["Balance at beginning of year", "100"],
        ["Additions charged to expense", "15"],
        ["Settlements", "(5)"],
    ]
    if extra is not None:
        rows.append(["Other adjustments", extra])
    rows.append(["Balance at end of year", ending])
    return entry(
        rows,
        context=["The following table reconciles activity in the warranty reserve."],
    )


def flow():
    return entry(
        [
            ["", "2019", "2018"],
            ["North", "60", "50"],
            ["South", "40", "35"],
            ["Other", "20", "15"],
            ["Total consolidated revenues", "120", "100"],
        ],
        context=["The table summarizes revenues by reporting segment, in millions of dollars."],
    )


def metric():
    return entry(
        [
            ["(dollars in millions)", "2019", "2018"],
            ["Cash provided by operating activities", "150", "120"],
            ["Cash used in investing activities", "(40)", "(30)"],
            ["Dividends paid", "(10)", "(5)"],
            ["Free cash flow", "100", "85"],
        ],
        context=[
            "Our free cash flow is defined as cash provided by operating activities, less "
            "cash used in investing activities and dividends paid.",
            "The following table reconciles this non-GAAP measure.",
        ],
    )


def codes(result):
    return {item["code"] for item in result["source_scope_warnings"]}


def lead(result, group):
    return next(item for item in result["leads"] if item["group"] == group)


@pytest.mark.parametrize(
    "maker,group",
    [
        (stock, "stock_rollforward"),
        (flow, "annual_flow_components"),
        (metric, "defined_metric_reconstruction"),
    ],
)
def test_public_shapes_only_create_review_needed_leads(maker, group):
    result = screen_public(maker())
    assert result["status"] == "SCREENED_LEAD"
    assert group in result["groups"]
    for item in result["leads"]:
        assert item["review_status"] == "REVIEW_NEEDED"
        assert item["component_completeness_and_hierarchy_status"] == "REVIEW_NEEDED"
        assert item["physical_unit_status"] == "REVIEW_NEEDED"
        assert item["period_scope_status"] == "REVIEW_NEEDED"
        assert item["relation_certified"] is False
        assert item["new_task_created"] is False
    assert result["relation_certificate_created"] is False
    assert result["task_created"] is False


@pytest.mark.parametrize("ending,equal", [("110", True), ("111", False)])
def test_arithmetic_closure_never_certifies_or_rejects_the_financial_relation(ending, equal):
    result = screen_public(stock(ending=ending))
    check = lead(result, "stock_rollforward")["diagnostics"][0]
    assert check["status"] == "COMPUTED_DIAGNOSTIC_ONLY"
    assert check["equal"] is equal
    assert check["equality_is_not_financial_sufficiency"] is True
    assert result["status"] == "SCREENED_LEAD"
    assert result["closure_used_to_certify_relation"] is False


def test_no_subset_sum_search_to_make_a_bridge_close():
    result = screen_public(stock(ending="110", extra="999"))
    check = lead(result, "stock_rollforward")["diagnostics"][0]
    assert check["selected_component_rows"] == [2, 3, 4]
    assert check["sum_of_displayed_signed_components"] == "1009"
    assert check["equal"] is False
    assert result["subset_sum_search_performed"] is False


@pytest.mark.parametrize("dash", ["—", "–", "-", "N/A"])
def test_dash_and_missing_symbols_are_unknown_never_zero(dash):
    fixture = stock()
    fixture["table"][2][1] = dash
    result = screen_public(fixture)
    assert "DASH_OR_NA_IS_UNKNOWN_NOT_ZERO" in codes(result)
    check = lead(result, "stock_rollforward")["diagnostics"][0]
    assert check["status"] == "UNDETERMINED"
    assert check["unknown_cells"][0]["raw"] == dash
    assert "endpoint_difference" not in check


def test_table_ori_is_authoritative_and_cleaned_2014_artifact_is_not_repaired():
    original = stock()["table"]
    original[2][1] = "—"
    cleaned = deepcopy(original)
    cleaned[2][1] = "2014"
    fixture = stock()
    fixture.update(table_ori=original, table=cleaned)
    result = screen_public(fixture)
    assert result["source"]["authoritative_table_field"] == "table_ori"
    assert result["table_comparison"]["differences"] == [
        {
            "row_index": 2,
            "column_index": 1,
            "authoritative_value": "—",
            "cleaned_value": "2014",
            "authoritative_present": True,
            "cleaned_present": True,
        }
    ]
    assert "AUTHORITATIVE_AND_CLEANED_TABLE_DIFFER" in codes(result)
    assert lead(result, "stock_rollforward")["diagnostics"][0]["status"] == "UNDETERMINED"
    assert result["automatic_source_repair_performed"] is False
    assert fixture["table"][2][1] == "2014"


@pytest.mark.parametrize("bad", [[], None, "malformed"])
def test_bad_original_table_does_not_silently_fall_back_to_cleaned_view(bad):
    fixture = stock()
    fixture["table_ori"] = bad
    result = screen_public(fixture)
    assert result["source"]["authoritative_table_field"] == "table_ori"
    assert result["status"] == "NO_LEAD"
    assert "AUTHORITATIVE_TABLE_MISSING_EMPTY_OR_MALFORMED" in codes(result)


def test_unmodified_original_question_identity_is_not_a_constructed_task():
    fixture = stock()
    result = screen_public(fixture)
    identity = result["original_question_identity"]
    assert identity["original_id"] == fixture["id"]
    assert identity["original_question"] == fixture["qa"]["question"]
    assert identity["identity_kind"] == "ORIGINAL_SOURCE_QUESTION"
    assert identity["is_new_task"] is False
    assert identity["question_rewritten_or_generated"] is False


def test_private_answer_program_and_hidden_labels_cannot_change_the_public_screen():
    first = stock()
    second = deepcopy(first)
    second["qa"].update(answer="10", program="subtract(110,100)", exe_ans=10, gold_inds=[1])
    second.update(private_target="pretend dual", intended_method="movement", train_split=True)
    assert screen_public(first) == screen_public(second)
    assert screen_public(second)["private_answer_or_program_used"] is False


def test_screen_is_pure_and_preserves_all_input_source_bytes_as_values():
    fixture = metric()
    before = deepcopy(fixture)
    first = screen_public(fixture)
    second = screen_public(fixture)
    assert fixture == before
    assert first == second
    assert first["id"].startswith("public_source_screen:")


def test_beginning_and_ending_alone_do_not_provide_a_second_relation():
    result = screen_public(
        entry(
            [
                ["(in millions)", "2019", "2018"],
                ["Balance at January 1", "11", "11"],
                ["Balance at December 31", "11", "11"],
            ],
            context=["Reconciliation of our unrecognized tax benefits."],
        )
    )
    assert result["status"] == "NO_LEAD"
    assert "ENDPOINT_LABELS_WITHOUT_ACTUAL_MOVEMENT_ROWS" in codes(result)


def test_numerically_matching_arbitrary_rows_without_financial_scope_are_not_a_lead():
    result = screen_public(
        entry(
            [
                ["", "2019"],
                ["Opening item", "100"],
                ["Extra", "10"],
                ["Closing item", "110"],
            ]
        )
    )
    assert result["status"] == "NO_LEAD"


def test_weighted_average_option_price_column_is_never_summed_as_movement():
    result = screen_public(
        entry(
            [
                ["", "Options", "Weighted-average exercise price"],
                ["Balance January 1 2019", "100", "$4.00"],
                ["Granted", "20", "6.00"],
                ["Exercised", "(10)", "3.00"],
                ["Balance December 31 2019", "110", "$4.50"],
            ],
            context=["The table summarizes stock option activity."],
        )
    )
    checks = lead(result, "stock_rollforward")["diagnostics"]
    assert checks[0]["equal"] is True
    assert checks[1]["reason"] == "NONADDITIVE_UNIT_COLUMN"
    assert checks[1]["status"] == "NOT_COMPUTED"
    assert "USD_million" not in json.dumps(result)


def test_diagnostic_does_not_invent_a_negative_sign_from_an_outflow_label():
    fixture = stock()
    fixture["table"][3][1] = "5"
    result = screen_public(fixture)
    check = lead(result, "stock_rollforward")["diagnostics"][0]
    assert check["sum_of_displayed_signed_components"] == "20"
    assert check["row_sign_interpretation_applied"] is False
    assert check["equal"] is False


def test_subtotals_stop_diagnostic_addition_instead_of_double_counting_or_searching():
    fixture = stock()
    fixture["table"].insert(-1, ["Total movement", "10"])
    result = screen_public(fixture)
    check = lead(result, "stock_rollforward")["diagnostics"][0]
    assert check["status"] == "NOT_COMPUTED"
    assert check["reason"] == "INTERMEDIATE_HIERARCHY_REQUIRES_REVIEW"


def test_multi_year_stock_blocks_are_separate_leads_not_separate_certified_tasks():
    result = screen_public(
        entry(
            [
                ["Balance at January 1 2018", "100"],
                ["Additions", "15"],
                ["Settlements", "(5)"],
                ["Balance at December 31 2018", "110"],
                ["Additions", "12"],
                ["Settlements", "(7)"],
                ["Balance at December 31 2019", "115"],
            ],
            context=["Activity in the warranty reserve, in millions of dollars."],
        )
    )
    blocks = [item for item in result["leads"] if item["group"] == "stock_rollforward"]
    assert [item["candidate_endpoint_rows"] for item in blocks] == [[0, 3], [3, 6]]
    assert result["task_created"] is False


def test_one_year_segment_table_cannot_supply_an_annual_comparison():
    fixture = flow()
    fixture["table"] = [row[:2] for row in fixture["table"]]
    result = screen_public(fixture)
    assert result["status"] == "NO_LEAD"
    assert "FLOW_COMPARISON_NEEDS_TWO_PUBLIC_YEARS" in codes(result)


def test_amounts_that_look_like_years_do_not_establish_comparison_periods():
    result = screen_public(
        entry(
            [
                ["Description", "First value", "Second value"],
                ["North", "2019", "2018"],
                ["South", "2002", "2001"],
                ["Total consolidated revenues", "4021", "4019"],
            ],
            context=["Revenues by reporting segment, in millions."],
        )
    )
    assert result["period_evidence"] == []
    assert result["status"] == "NO_LEAD"


def test_filename_year_does_not_substitute_for_public_period_headers():
    fixture = flow()
    fixture["table"][0] = ["", "Current", "Prior"]
    fixture["filename"] = "Example/2019/report"
    fixture["id"] = "Example/2018/report-question"
    result = screen_public(fixture)
    assert result["period_evidence"] == []
    assert result["status"] == "NO_LEAD"


def test_vertical_annual_metric_bridge_is_a_flow_not_a_stock_rollforward():
    result = screen_public(
        entry(
            [
                ["(in millions)", "Amount"],
                ["2018 revenues", "100"],
                ["Price", "12"],
                ["Volume", "(2)"],
                ["2019 revenues", "110"],
            ],
            context=["The following analysis explains the change in annual revenues."],
        )
    )
    assert result["groups"] == ["annual_flow_components"]
    assert lead(result, "annual_flow_components")["diagnostics"][0]["equal"] is True


def test_different_endpoint_metric_names_are_not_coerced_into_one_bridge():
    result = screen_public(
        entry(
            [
                ["(in millions)", "Amount"],
                ["2018 sales", "100"],
                ["Other", "10"],
                ["2019 operating income", "110"],
            ]
        )
    )
    assert result["status"] == "NO_LEAD"


def test_company_definition_can_overlap_a_flow_bridge_but_never_double_count_tasks():
    result = screen_public(
        entry(
            [
                ["(in millions)", "Amount"],
                ["2018 net revenue", "100"],
                ["Base rates", "12"],
                ["Other", "(2)"],
                ["2019 net revenue", "110"],
            ],
            context=["Net revenue is the company's measure of gross margin."],
        )
    )
    assert result["groups"] == ["annual_flow_components", "defined_metric_reconstruction"]
    assert "GROUP_OVERLAP_REQUIRES_TASK_LEVEL_REVIEW" in codes(result)
    assert result["task_created"] is False


def test_adjusted_metric_summary_and_external_reference_are_not_local_reconciliation():
    result = screen_public(
        entry(
            [
                ["(in millions)", "2019", "2018"],
                ["Net sales", "100", "90"],
                ["Net income", "10", "9"],
                ["Adjusted EBITDA", "20", "18"],
            ],
            context=[
                "Adjusted EBITDA is a non-GAAP measure.",
                "For definitions and reconciliations, see the results of operations section.",
            ],
        )
    )
    assert result["status"] == "NO_LEAD"
    assert "EXTERNAL_DEFINITION_REFERENCE" in codes(result)
    assert "METRIC_NAME_OR_EXTERNAL_REFERENCE_WITHOUT_LOCAL_TWO_PERIOD_RECONCILIATION" in codes(
        result
    )


def test_company_metric_reconstruction_requires_two_public_years():
    fixture = metric()
    fixture["table"] = [row[:2] for row in fixture["table"]]
    result = screen_public(fixture)
    assert "defined_metric_reconstruction" not in result["groups"]


def test_adjusted_ebitda_components_require_sign_and_hierarchy_review_even_with_definition():
    result = screen_public(
        entry(
            [
                ["(in thousands)", "2019", "2018"],
                ["Net income", "10", "9"],
                ["Interest expense", "2", "1"],
                ["Income tax", "3", "2"],
                ["Depreciation", "4", "3"],
                ["Total adjustments", "9", "6"],
                ["Adjusted EBITDA", "19", "15"],
            ],
            context=[
                "The following reconciliation describes our non-GAAP adjusted EBITDA measure."
            ],
        )
    )
    item = lead(result, "defined_metric_reconstruction")
    assert item["review_status"] == "REVIEW_NEEDED"
    assert item["diagnostics"][0]["status"] == "NOT_COMPUTED"


def test_explicit_FFO_reconciliation_is_a_defined_metric_lead_only():
    result = screen_public(
        entry(
            [
                ["(in millions)", "2019", "2018"],
                ["Net income", "100", "80"],
                ["Depreciation", "100", "90"],
                ["Gains on property sales", "(20)", "(10)"],
                ["Funds from operations", "180", "160"],
            ],
            context=[
                "Our funds from operations is a non-GAAP measure defined as net income plus "
                "depreciation less gains on property sales. The reconciliation follows.",
            ],
        )
    )
    item = lead(result, "defined_metric_reconstruction")
    assert item["review_status"] == "REVIEW_NEEDED"
    assert item["relation_certified"] is False


def test_cash_end_of_year_wording_retains_a_stock_rollforward_lead():
    result = screen_public(
        entry(
            [
                ["(in millions)", "2019"],
                ["Cash and cash equivalents, beginning of the year", "100"],
                ["Cash provided by operations", "20"],
                ["Cash used for financing", "(10)"],
                ["Cash and cash equivalents, end of the year", "110"],
            ],
            context=["The table reconciles changes in cash and cash equivalents."],
        )
    )
    assert "stock_rollforward" in result["groups"]
    assert result["relation_certificate_created"] is False


def test_scope_change_and_partial_explanation_are_retained_as_review_warnings():
    fixture = flow()
    fixture["post_text"] = [
        "Prior-year figures are not directly comparable because only the acquired company "
        "was included in the prior year.",
        "The increase was primarily due to new products, partially offset by currency effects.",
    ]
    result = screen_public(fixture)
    assert result["status"] == "SCREENED_LEAD"
    assert {"NONCOMPARABLE_SCOPE", "PARTIAL_DRIVER_EXPLANATION"} <= codes(result)
    assert result["relation_certificate_created"] is False


def test_forward_looking_valuation_measure_is_not_assumed_to_be_a_stock_account():
    result = screen_public(
        entry(
            [
                ["(in millions)", "2019", "2018"],
                ["Beginning of the year", "100", "90"],
                ["Changes in prices", "10", "10"],
                ["End of the year", "110", "100"],
            ],
            context=[
                "Changes in the standardized measure of discounted future net cash flows "
                "from oil and gas reserves."
            ],
        )
    )
    assert "stock_rollforward" not in result["groups"]
    assert "VALUATION_MEASURE_NOT_AUTOMATICALLY_A_STOCK_ACCOUNT" in codes(result)


def test_all_evidence_pointers_resolve_to_exact_unchanged_public_values():
    fixture = metric()
    fixture["table_ori"] = deepcopy(fixture["table"])
    fixture["table"][1][1] = "a cleaned variant"
    result = screen_public(fixture)

    def visit(value):
        if isinstance(value, dict):
            if "pointer" in value and "original_value" in value:
                actual = fixture
                for part in value["pointer"]:
                    actual = actual[part]
                assert actual == value["original_value"]
                if isinstance(actual, str):
                    assert value["quote"] == actual
            for child in value.values():
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)

    visit(result)


def test_status_vocabulary_has_no_certified_or_generated_task_state():
    for fixture in (stock(), flow(), metric(), entry([["x", "y"]])):
        result = screen_public(fixture)
        assert result["status"] in {"SCREENED_LEAD", "NO_LEAD"}
        assert set(result["groups"]) <= set(GROUPS)
        assert all(item["review_status"] == "REVIEW_NEEDED" for item in result["leads"])
        assert "PUBLIC_RELATION_REVIEWED" not in json.dumps(result)
