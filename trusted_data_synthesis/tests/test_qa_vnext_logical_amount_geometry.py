"""Finite physical-cell geometry controls; no production data or model sampling."""

from decimal import Decimal
from html import escape

import pytest
from lxml import html

from trusted_synthesis.experiments.finance_qa_vnext_task_build import issuer_tables


def layout(body_cells, header_cells):
    def row(items):
        result = []
        for item in items:
            value, width = item if isinstance(item, tuple) else (item, 1)
            result.append(f'<td colspan="{width}">{escape(value)}</td>')
        return "<tr>" + "".join(result) + "</tr>"

    table = html.fromstring("<table>" + row(header_cells) + row(body_cells) + "</table>")
    header_row, amount_row = issuer_tables.cells(table)
    annual = [
        {**cell, "period_end": cell["text"] + "-12-31"}
        for cell in header_row
        if cell["text"] in {"2024", "2023"}
    ]
    return amount_row, annual, header_row


def decode(fixture, index=0):
    row, annual, header_row = fixture
    return issuer_tables.row_amount(row, annual[index], year_headers=annual, header_row=header_row)


@pytest.mark.parametrize("printed", ["(2,135)", "$ (2,135)", "($2,135)", "-2135", "−2,135"])
def test_same_cell_signed_amount_and_original_text_survive(printed):
    fixture = layout(["Capex", printed, "10"], ["Label", "2024", "2023"])
    value, reference = decode(fixture)
    assert value == Decimal("-2135")
    assert reference["cells"][0]["raw_text"] == printed
    assert reference["cells"][0]["cell_xpath"].endswith("/tr[2]/td[2]")
    assert reference["geometry_certificate"]["annual_header"] == fixture[1][0]


def test_adjacent_close_outside_header_has_unique_signed_block_and_certificate():
    fixture = layout(
        ["Capex", "$", "(2,135", ")", "", "$", "(1,564", ")"],
        ["Label", ("2024", 2), "", "", ("2023", 2), ""],
    )
    for index, expected in enumerate(("-2135", "-1564")):
        value, reference = decode(fixture, index)
        assert value == Decimal(expected)
        certificate = reference["geometry_certificate"]
        assert certificate["rule"] == issuer_tables.LOGICAL_AMOUNT_RULE
        assert certificate["original_amount_row"] == fixture[0]
        assert certificate["original_header_row"] == fixture[2]
        assert certificate["all_annual_headers"] == fixture[1]
        assert certificate["selection_uses_amount_value_or_reconciliation"] is False
        suffix = next(
            item for item in certificate["symbol_bindings"] if item["roles"] == ["suffix"]
        )
        assert suffix["outside_annual_header"] is True
        assert suffix["cell"]["start"] == fixture[1][index]["stop"]
        assert suffix["candidate_body_cells"] == [certificate["body"]]
        assert reference["cells"][-1]["raw_text"] == ")"


@pytest.mark.parametrize("prefix", [["(", "$"], ["$", "("]])
def test_currency_open_body_and_close_can_occupy_separate_physical_cells(prefix):
    fixture = layout(
        ["Capex", *prefix, "90", ")", "", "70"],
        ["Label", ("2024", 3), "", "", "2023"],
    )
    assert decode(fixture)[0] == -90


def test_two_argument_call_cannot_infer_outside_header_symbols():
    row, annual, _ = layout(["Capex", "(90", ")", "70"], ["Label", "2024", "", "2023"])
    with pytest.raises(ValueError, match="external_symbol_requires_full_headers"):
        issuer_tables.row_amount(row, annual[0])


def test_another_year_digit_cell_is_never_used_to_complete_a_number():
    fixture = layout(["Capex", "(90", "70)"], ["Label", "2024", "2023"])
    with pytest.raises(ValueError, match="missing_or_ambiguous_numeric_cell"):
        decode(fixture)


def test_symbol_under_other_annual_header_cannot_complete_previous_amount():
    fixture = layout(["Capex", "(90", ")", "70"], ["Label", "2024", ("2023", 2)])
    with pytest.raises(ValueError, match="symbol_crosses_annual_column"):
        decode(fixture)


def test_shared_symbol_cell_is_rejected_before_any_closure_choice():
    fixture = layout(["Capex", "(90", ")(", "70)"], ["Label", "2024", "", "2023"])
    for index in (0, 1):
        with pytest.raises(ValueError, match="shared_symbol_cell"):
            decode(fixture, index)


@pytest.mark.parametrize("marker", ["*", "(1)", "%", "—", "–", "-", "−", "N/A"])
def test_markers_inside_annual_amount_column_are_not_signs_or_zero(marker):
    fixture = layout(["Capex", "90", marker, "70"], ["Label", ("2024", 2), "2023"])
    with pytest.raises(ValueError, match="missing_or_ambiguous_numeric_cell"):
        decode(fixture)


@pytest.mark.parametrize("barrier", ["", "*", "%", "(1)", "—", "-"])
def test_symbol_binding_never_skips_blank_annotation_or_numeric_barrier(barrier):
    fixture = layout(["Capex", "(90", barrier, ")", "70"], ["Label", "2024", "", "", "2023"])
    with pytest.raises(ValueError, match="missing_or_ambiguous_numeric_cell"):
        decode(fixture)


def test_complete_amount_does_not_borrow_an_adjacent_footnote():
    fixture = layout(["FCF", "90", "*", "70"], ["Label", "2024", "", "2023"])
    value, reference = decode(fixture)
    assert value == 90
    assert [cell["text"] for cell in reference["cells"]] == ["90"]
    assert reference["geometry_certificate"]["original_amount_row"][2]["raw_text"] == "*"


def test_numeric_body_spanning_headers_is_rejected_even_if_it_already_parses():
    fixture = layout(["Capex", ("(90)", 2)], ["Label", "2024", "2023"])
    with pytest.raises(ValueError, match="uncertain_column_ownership"):
        decode(fixture)


def test_overlapping_annual_headers_do_not_acquire_a_unique_body_by_value():
    fixture = layout(["Capex", "(90)", "70"], ["Label", "2024", "2023"])
    fixture[1][1]["start"] = 1
    with pytest.raises(ValueError, match="ambiguous_annual_headers"):
        decode(fixture)


@pytest.mark.parametrize("auxiliary", ["Change", "Percent", "(1)"])
def test_external_symbol_cannot_cross_a_nonempty_auxiliary_header(auxiliary):
    fixture = layout(["Capex", "(90", ")", "70"], ["Label", "2024", auxiliary, "2023"])
    with pytest.raises(ValueError, match="external_symbol_not_blank_header_slot"):
        decode(fixture)


def test_already_closed_amount_with_extra_close_is_not_salvaged():
    fixture = layout(["Capex", "(90)", ")", "70"], ["Label", "2024", "", "2023"])
    with pytest.raises(ValueError, match="missing_or_ambiguous_numeric_cell"):
        decode(fixture)


def test_superscript_annotation_is_retained_but_not_converted_to_an_amount():
    table = html.fromstring(
        "<table><tr><td>Label</td><td>2024</td><td>2023</td></tr>"
        "<tr><td>Capex</td><td>90<sup>1</sup></td><td>70</td></tr></table>"
    )
    header_row, row = issuer_tables.cells(table)
    annual = [{**cell, "period_end": cell["text"] + "-12-31"} for cell in header_row[1:]]
    assert row[1]["raw_text"] == "901"
    assert row[1]["has_superscript"] is True
    with pytest.raises(ValueError, match="numeric_annotation"):
        issuer_tables.row_amount(row, annual[0], year_headers=annual, header_row=header_row)


@pytest.mark.parametrize(
    "printed", ["(-90)", "1$2", "1,23", "$$90", "$( $90)", "90%", "—", "*", "90 70"]
)
def test_scalar_does_not_erase_malformed_sign_currency_or_annotation(printed):
    assert issuer_tables.scalar(printed) is None
