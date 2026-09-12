"""Post-run independent audit controls; never generate, filter or rewrite panels."""

import ast
import importlib.util
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/audit_qa_vnext_catalog_panels.py"
SPEC = importlib.util.spec_from_file_location("catalog_panels_independent_audit", SCRIPT)
AUDIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT)

FISCAL = [
    ["2010-09-27", "2011-09-25"],
    ["2011-09-26", "2012-09-30"],
    ["2012-10-01", "2013-09-29"],
]
CALENDAR = [[f"{year}-01-01", f"{year}-12-31"] for year in (2011, 2012, 2013)]


@pytest.mark.parametrize(
    "question,periods,mismatch",
    [
        ("Which calendar year had the highest revenue?", FISCAL, True),
        ("Identify the peak-Revenue calendar year.", FISCAL, True),
        ("Compare the calendar years' reported amounts.", FISCAL, True),
        ("Which CALENDAR-YEAR had the highest revenue?", FISCAL, True),
        ("Which calendar year had the highest revenue?", CALENDAR, False),
        ("Which fiscal year had the highest revenue?", FISCAL, False),
        ("Which financial year had the highest revenue?", FISCAL, False),
        ("Across the three annual observations, what was the mean?", FISCAL, False),
        ("What was the change from 2011-09-26 to 2013-09-29?", FISCAL, False),
        ("Which fiscal year had the highest revenue?", CALENDAR, False),
    ],
)
def test_explicit_calendar_vs_actual_fiscal_positive_and_negative_controls(
    question, periods, mismatch
):
    assert AUDIT.calendar_period_mismatch(question, periods) is mismatch


def test_any_noncalendar_component_invalidates_calendar_window_label():
    periods = [*CALENDAR[:2], FISCAL[2]]
    assert AUDIT.calendar_period_mismatch("Identify the peak calendar year.", periods)


def test_missing_actual_periods_cannot_silently_pass():
    with pytest.raises(ValueError, match="nonempty actual-period"):
        AUDIT.calendar_period_mismatch("Which calendar year?", [])


def test_literal_census_distinguishes_calendar_fiscal_and_financial():
    assert AUDIT.year_kind_literals("calendar year") == {
        "calendar": True,
        "fiscal": False,
        "financial": False,
    }
    assert AUDIT.year_kind_literals("financial years") == {
        "calendar": False,
        "fiscal": False,
        "financial": True,
    }


def test_auditor_has_no_generator_executor_or_model_imports():
    syntax = ast.parse(SCRIPT.read_text())
    roots = set()
    for node in ast.walk(syntax):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            roots.add(node.module.split(".")[0])
    assert roots.isdisjoint({"trusted_synthesis", "finraw", "torch", "transformers", "httpx"})
