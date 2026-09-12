"""Independent-auditor controls; every financial amount below is synthetic."""

import ast
import copy
import importlib.util
import json
import sqlite3
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/audit_qa_vnext_eval_readiness_panels.py"
SPEC = importlib.util.spec_from_file_location("independent_eval_panel_audit", SCRIPT)
audit = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(audit)


def _record(kind, **fields):
    body = {"schema_version": "synthetic." + kind, **fields}
    return {**body, "id": kind + ":" + audit.digest(body)}


def _fixture(quantity="three_year_peak_then_same_period_metric", *, calendar=False, pairs=None):
    if pairs is None:
        pairs = (
            [(f"{year}-01-01", f"{year}-12-31") for year in (2011, 2012, 2013)]
            if calendar
            else [
                ("2010-09-27", "2011-09-25"),
                ("2011-09-26", "2012-09-30"),
                ("2012-10-01", "2013-09-29"),
            ]
        )
    pairs = list(pairs)
    cluster = "cik:0000000001"
    if quantity == "three_year_peak_then_same_period_metric":
        metrics = ["revenue", "net_income"]
        operation = {
            "kind": "argmax_then_lookup",
            "primary_metric_id": "revenue",
            "secondary_metric_id": "net_income",
            "candidate_count": 3,
            "same_actual_period_required": True,
        }
        question = (
            "Identify SYNTH's peak-Revenue actual reporting period, "
            "then give its Net Income for that period."
        )
    elif quantity == "three_annual_flow_mean":
        metrics, operation = (
            ["revenue"],
            {"kind": "arithmetic_mean", "metric_id": "revenue", "operand_count": 3},
        )
        question = "What was SYNTH's average Revenue over the three source observations?"
    else:
        pairs = pairs[:2]
        metrics = ["gross_profit"]
        operation = {
            "kind": quantity,
            "metric_id": "gross_profit",
            "direction": "current_minus_previous",
        }
        if quantity == "relative_change":
            operation.update(denominator="strictly_positive_previous", multiplier=100)
            question = "What was SYNTH's year-over-year growth rate of Gross Profit?"
        else:
            question = "Calculate SYNTH's change in Gross Profit between the two source periods."
    target = {
        "quantity": quantity,
        "source_cluster": cluster,
        "metric_ids": metrics,
        "actual_periods": pairs,
        "unit": "percent" if quantity == "relative_change" else "million USD",
    }
    contract = {
        "schema": "actual_period_contract.v1",
        "task_id": "task:synthetic",
        "source_cluster": cluster,
        "quantity": quantity,
        "metric_ids": metrics,
        "operation": operation,
        "periods": [
            {
                "period_id": audit.period_id(start, end),
                "start": start,
                "end": end,
                "period_type": "duration" if start else "instant",
                "label_basis": "calendar_year"
                if start == end[:4] + "-01-01" and end == start[:4] + "-12-31"
                else "actual_interval",
            }
            for start, end in pairs
        ],
    }
    contract["id"] = "actual_period_contract:" + audit.digest(contract, ensure_ascii=True)
    public = {
        "question": question,
        "period_contract": contract,
        "quantity_contract": {"unit": target["unit"]},
        "tool_contract": {"Final": "First Final stops; include the selected actual period_id."},
    }
    _attach(public, question)
    natives = [
        {
            "metric_id": metric,
            "source_cluster": cluster,
            "record": {"start": start, "end": end, "val": 123, "fy": 2026},
        }
        for metric in metrics
        for start, end in pairs
    ]
    final = {
        "value": "123",
        "period_id": audit.period_id(*pairs[1]),
        "actual_period": {"start": pairs[1][0], "end": pairs[1][1]},
    }
    return public, target, natives, final


def _attach(public, question):
    """Handwritten fixture serialization, never imports the production renderer."""
    contract = public["period_contract"]
    lines = ["Actual comparison periods (inclusive source dates):"]
    for period in contract["periods"]:
        fragment = (
            f"{period['start']} through {period['end']}"
            if period["start"]
            else f"instant at {period['end']}"
        )
        lines.append(f"Period {period['period_id']}: {fragment}.")
    lines.append(
        "Compute current minus previous."
        if contract["operation"]["kind"] in {"difference", "relative_change"}
        else "Use the complete stated set of actual reporting periods."
    )
    lines.extend([audit.BEGIN, json.dumps(contract, sort_keys=True), audit.END])
    public["question"] = question + "\n\n" + "\n".join(lines)


@pytest.mark.parametrize(
    "quantity",
    [
        "difference",
        "relative_change",
        "three_annual_flow_mean",
        "three_year_peak_then_same_period_metric",
    ],
)
@pytest.mark.parametrize("calendar", [True, False])
def test_independent_actual_period_positive_contracts(quantity, calendar):
    public, target, natives, final = _fixture(quantity, calendar=calendar)
    assert audit.public_period_errors(public, target, natives, final=final) == []


@pytest.mark.parametrize("case_index", range(96))
def test_all_96_synthetic_calendar_fiscal_counterexample_shapes_rejected(case_index):
    public, target, natives, final = _fixture()
    split = "dev" if case_index < 18 else "confirm"
    base = (
        f"Identify SYNTH-{split}-{case_index}'s peak-Revenue calendar year, "
        "then give its Net Income for that period."
    )
    _attach(public, base)
    errors = audit.public_period_errors(public, target, natives, final=final)
    assert "no_calendar_label_for_noncalendar_actual_target" in errors


def test_real_calendar_year_wording_requires_complete_Jan1_Dec31_intervals():
    public, target, natives, final = _fixture(calendar=True)
    _attach(
        public,
        "Identify SYNTH's peak-Revenue calendar year, then give its Net Income for that period.",
    )
    assert audit.public_period_errors(public, target, natives, final=final) == []


def test_JNJ_same_end_year_distinct_annual_intervals_remain_distinct():
    pairs = [
        ("2021-01-04", "2022-01-02"),
        ("2022-01-03", "2023-01-01"),
        ("2023-01-02", "2023-12-31"),
    ]
    public, target, natives, final = _fixture(pairs=pairs)
    assert audit.public_period_errors(public, target, natives, final=final) == []
    assert len({row["period_id"] for row in public["period_contract"]["periods"]}) == 3
    assert len({end[:4] for _, end in pairs}) == 2
    final["period_id"] = "2023"
    assert "reference_final_exact_interval_identity" in audit.public_period_errors(
        public, target, natives, final=final
    )


@pytest.mark.parametrize(
    "mutation",
    [
        "calendar_label",
        "wrong_date",
        "mixed_interval",
        "wrong_year",
        "minimum",
        "wrong_metric_role",
    ],
)
def test_correct_appended_contract_cannot_hide_wrong_original_peak_question(mutation):
    public, target, natives, final = _fixture()
    base = public["question"].split("\n\n", 1)[0]
    if mutation == "calendar_label":
        base = base.replace("actual reporting period", "calendar year")
    elif mutation == "wrong_date":
        base += " Use 2011-01-01 through 2011-12-31."
    elif mutation == "mixed_interval":
        base += " Use 2010-09-27 through 2012-09-30."
    elif mutation == "wrong_year":
        base += " Select the 2020 year."
    elif mutation == "minimum":
        base = base.replace("peak-Revenue", "lowest Revenue")
    else:
        base = (
            "Identify SYNTH's peak-Net Income actual reporting period, "
            "then give its Revenue for that period."
        )
    _attach(public, base)
    assert audit.public_period_errors(public, target, natives, final=final)


@pytest.mark.parametrize("operation", ["sum", "median", "maximum", "difference"])
def test_correct_mean_contract_cannot_hide_wrong_base_operation(operation):
    public, target, natives, _ = _fixture("three_annual_flow_mean")
    base = public["question"].split("\n\n", 1)[0].replace("average", operation)
    _attach(public, base)
    assert audit.public_period_errors(public, target, natives)


def test_correct_forward_contract_cannot_hide_reversed_base_difference():
    public, target, natives, _ = _fixture("difference")
    _attach(public, "Calculate SYNTH's change in Gross Profit as previous minus current.")
    assert "question_no_reversed_difference_direction" in audit.public_period_errors(
        public, target, natives
    )


def test_reversed_actual_interval_order_is_not_hidden_by_matching_date_set():
    public, target, natives, _ = _fixture("difference")
    left, right = target["actual_periods"]
    _attach(
        public,
        f"Calculate SYNTH's change in Gross Profit between {right[0]} through {right[1]} "
        f"and {left[0]} through {left[1]}.",
    )
    assert "base_question_two_intervals_forward_order" in audit.public_period_errors(
        public, target, natives
    )


@pytest.mark.parametrize(
    "mutation",
    [
        "missing_middle",
        "same_year_wrong_actual_interval",
        "secondary_other_interval",
        "wrong_metric",
    ],
)
def test_native_period_metric_coverage_not_replaced_by_equal_amounts(mutation):
    public, target, natives, final = _fixture()
    if mutation == "missing_middle":
        natives.pop(1)
    elif mutation == "same_year_wrong_actual_interval":
        natives[1]["record"].update(start="2012-01-01", end="2012-12-31")
    elif mutation == "secondary_other_interval":
        natives[-2]["record"].update(
            start=natives[-3]["record"]["start"], end=natives[-3]["record"]["end"]
        )
    else:
        natives[1]["metric_id"] = "operating_income"
    assert all(native["record"]["val"] == 123 for native in natives)
    assert "every_metric_in_every_exact_native_interval" in audit.public_period_errors(
        public, target, natives, final=final
    )


@pytest.mark.parametrize("offset", [-1, 1])
def test_actual_duration_gap_or_overlap_rejected(offset):
    from datetime import date, timedelta

    public, target, natives, final = _fixture()
    changed = (
        date.fromisoformat(target["actual_periods"][1][0]) + timedelta(days=offset)
    ).isoformat()
    target["actual_periods"][1] = (changed, target["actual_periods"][1][1])
    row = public["period_contract"]["periods"][1]
    row.update(start=changed, period_id=audit.period_id(changed, row["end"]))
    body = {key: value for key, value in public["period_contract"].items() if key != "id"}
    public["period_contract"]["id"] = "actual_period_contract:" + audit.digest(
        body, ensure_ascii=True
    )
    for native in natives:
        if native["record"]["end"] == row["end"]:
            native["record"]["start"] = changed
    _attach(
        public,
        "Identify SYNTH's peak-Revenue actual reporting period, "
        "then give its Net Income for that period.",
    )
    assert "no_actual_period_gap_or_overlap" in audit.public_period_errors(
        public, target, natives, final=final
    )


@pytest.mark.parametrize(
    "mutation",
    ["unit", "quantity", "metric", "direction", "period_id", "human_dates", "contract_block"],
)
def test_persisted_contract_or_human_layer_mutations_are_rejected(mutation):
    public, target, natives, _ = _fixture("difference")
    if mutation == "unit":
        public["quantity_contract"]["unit"] = "USD"
    elif mutation == "quantity":
        public["period_contract"]["quantity"] = "relative_change"
    elif mutation == "metric":
        public["period_contract"]["metric_ids"] = ["revenue"]
    elif mutation == "direction":
        public["period_contract"]["operation"]["direction"] = "previous_minus_current"
    elif mutation == "period_id":
        public["period_contract"]["periods"][0]["period_id"] = "2011"
    elif mutation == "human_dates":
        public["question"] = public["question"].replace(
            "through 2011-09-25.", "through 2012-09-30."
        )
    else:
        public["question"] = public["question"].replace(audit.BEGIN, "MISSING")
    assert audit.public_period_errors(public, target, natives)


def _cash_fixture(restricted=False):
    metric = audit.RESTRICTED if restricted else audit.CASH
    target = {
        "metric_id": metric,
        "previous_period": (None, "2020-12-31"),
        "current_period": (None, "2021-12-31"),
    }
    fx = (
        "effect_of_exchange_rate_on_cash_including_restricted"
        if restricted
        else "effect_of_exchange_rate_on_cash_and_cash_equivalents"
    )
    change = (
        "change_in_cash_including_restricted_and_exchange_rate_effect"
        if restricted
        else "change_in_cash_including_exchange_rate_effect"
    )
    specifications = [
        ("previous", metric, None, "2020-12-31"),
        ("current", metric, None, "2021-12-31"),
    ]
    specifications.extend(
        (name, name, "2021-01-01", "2021-12-31") for name in [*audit.FLOW_METRICS, fx, change]
    )
    bindings = {
        identifier: {
            "metric_id": name,
            "tag": next(iter(audit.TAGS[name])),
            "record": {"start": start, "end": end, "val": 100},
        }
        for identifier, name, start, end in specifications
    }
    certificate = {
        "leaf_fact_ids": list(bindings),
        "account_scope": "including_restricted" if restricted else "cash_only",
        "source_citations": [{"accession": "synthetic"}],
    }
    return target, certificate, bindings


@pytest.mark.parametrize("restricted", [False, True])
def test_independent_cash_account_full_typed_bridge(restricted):
    target, certificate, bindings = _cash_fixture(restricted)
    assert audit.account_scope_errors(target, certificate, bindings) == []


@pytest.mark.parametrize(
    "mutation",
    ["account_scope", "foreign_FX_tag", "foreign_total_tag", "wrong_interval", "missing_component"],
)
def test_equal_cash_amounts_do_not_allow_account_or_flow_scope_mix(mutation):
    target, certificate, bindings = _cash_fixture()
    fx = "effect_of_exchange_rate_on_cash_and_cash_equivalents"
    if mutation == "account_scope":
        certificate["account_scope"] = "including_restricted"
    elif mutation == "foreign_FX_tag":
        bindings[fx]["tag"] = next(
            iter(audit.TAGS["effect_of_exchange_rate_on_cash_including_restricted"])
        )
    elif mutation == "foreign_total_tag":
        bindings["change_in_cash_including_exchange_rate_effect"]["tag"] = next(
            iter(audit.TAGS["change_in_cash_including_restricted_and_exchange_rate_effect"])
        )
    elif mutation == "wrong_interval":
        bindings[fx]["record"]["start"] = "2021-01-02"
    else:
        certificate["leaf_fact_ids"].remove(fx)
    assert audit.account_scope_errors(target, certificate, bindings)


def test_json_pointer_is_exact_and_does_not_match_by_val_or_year():
    payload = {
        "facts": {
            "us-gaap": {
                "Metric/Tag": {
                    "units": {
                        "USD": [
                            {"start": "2022-01-03", "end": "2023-01-01", "val": 1},
                            {"start": "2023-01-02", "end": "2023-12-31", "val": 1},
                        ]
                    }
                }
            }
        }
    }
    left = audit.resolve_pointer(payload, "/facts/us-gaap/Metric~1Tag/units/USD/0")
    right = audit.resolve_pointer(payload, "/facts/us-gaap/Metric~1Tag/units/USD/1")
    assert left["val"] == right["val"] and left["end"][:4] == right["end"][:4]
    assert left["start"] != right["start"]
    with pytest.raises(ValueError):
        audit.resolve_pointer(payload, "/facts/us-gaap/Metric~1Tag/units/USD/01")


def test_auditor_has_no_generator_or_new_period_validator_imports():
    tree = ast.parse(SCRIPT.read_text())
    imported = {
        node.module.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
    }
    imported |= {
        alias.name.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    assert imported <= {
        "argparse",
        "hashlib",
        "json",
        "re",
        "collections",
        "datetime",
        "fractions",
        "functools",
        "pathlib",
    }


def test_audit_paths_reject_symlink_and_parent_escape(tmp_path):
    panels = tmp_path / "stage/panels"
    panels.mkdir(parents=True)
    instance = audit.Audit(tmp_path, panels)
    (panels / "real").mkdir()
    (panels / "alias").symlink_to(panels / "real", target_is_directory=True)
    with pytest.raises(ValueError):
        instance.path(panels, "alias/source.json")
    with pytest.raises(ValueError):
        instance.path(panels, "../source.json")


def _gap_fixture(tmp_path, monkeypatch, *, additions=14):
    panel_directory = tmp_path / "new/panels"
    (panel_directory / "dev").mkdir(parents=True)
    instance = audit.Audit(tmp_path, panel_directory)
    instance.old_directory = tmp_path / "old/panels"
    originals = [
        {"task_id": f"task:confirm:{index}", "reason": "original_compiler_gap"}
        for index in range(12)
    ]
    targets = [
        {"task_id": row["task_id"], "target": {"source_cluster": "cik:1"}} for row in originals
    ]
    compilations = [
        {"task_id": row["task_id"], "candidate_id": f"old_candidate:{index}"}
        for index, row in enumerate(originals)
    ]
    old_dev = [
        {"task_id": f"task:old_dev:{index}", "family": "dual_sufficient"} for index in range(46)
    ]
    tables = {
        "confirm/QA_export_rejections.json": originals,
        "confirm/QA/target_bindings.json": targets,
        "confirm/QA/pattern_compilations.json": compilations,
        "dev/catalog.json": {"tasks": old_dev},
        "dev/QA/target_bindings.json": old_dev,
    }
    monkeypatch.setattr(
        instance,
        "old_file",
        lambda path: copy.deepcopy(tables[str(path.relative_to(instance.old_directory))]),
    )
    new_dev = [
        *old_dev,
        *[
            {"task_id": f"task:new_dev:{index}", "family": "dual_sufficient"}
            for index in range(additions)
        ],
    ]
    (panel_directory / "dev/catalog.json").write_text(json.dumps({"tasks": new_dev}))
    cases = [
        _record(
            "archived_panel_gap_case",
            task_id=row["task_id"],
            original_rejection=row,
            canonical_target=targets[index]["target"],
            original_compilation=compilations[index],
            exact_input_set_parents=[],
        )
        for index, row in enumerate(originals)
    ]
    diagnosis = {"cases": cases, "case_count": 12}
    panels = {
        "confirm": {
            "impact": {
                "tasks": [
                    {"task_id": row["task_id"], "new_status": "selected_new_version"}
                    for row in originals
                ]
            }
        }
    }
    instance.bundles = {
        row["task_id"]: {"parents": {"qa_id": "new:" + row["task_id"]}} for row in originals
    }
    return instance, panels, diagnosis


def test_26_gap_cases_distinguish_real_old_targets_from_missing_dev_slots(tmp_path, monkeypatch):
    instance, panels, diagnosis = _gap_fixture(tmp_path, monkeypatch)
    rows = instance.gap_cases(panels, diagnosis)
    assert len(rows) == 26 and not instance.failures
    assert all(row["old_task_id"] is not None for row in rows[:12])
    assert all(
        row["old_task_id"] is None and row["original_target_did_not_exist"] for row in rows[12:]
    )
    assert [row["new_task_id"] for row in rows[12:]] == [
        f"task:new_dev:{index}" for index in range(14)
    ]


def test_duplicate_archived_gap_id_cannot_replace_another_case(tmp_path, monkeypatch):
    instance, panels, diagnosis = _gap_fixture(tmp_path, monkeypatch)
    diagnosis["cases"][-1] = copy.deepcopy(diagnosis["cases"][0])
    instance.gap_cases(panels, diagnosis)
    assert any(
        row["code"] == "all_twelve_original_confirmation_gaps_exactly_once"
        for row in instance.failures
    )


def test_unfilled_old_dev_enumeration_slots_are_preserved_not_fabricated(tmp_path, monkeypatch):
    instance, panels, diagnosis = _gap_fixture(tmp_path, monkeypatch, additions=12)
    rows = instance.gap_cases(panels, diagnosis)
    assert len(rows) == 26
    assert all(
        row["new_task_id"] is None and row["new_status"] == "unfilled_source_shortfall"
        for row in rows[-2:]
    )


def test_independent_auditor_over_new_synthetic_real_QA_exports(tmp_path, monkeypatch):
    from test_qa_vnext_eval_readiness_panels import (
        test_synthetic_actual_native_KG_QA_and_saved_public_export,
    )

    test_synthetic_actual_native_KG_QA_and_saved_public_export(tmp_path, monkeypatch)
    directory = tmp_path / "panel"
    sources = audit.read(directory / "public_source_index.json")
    bindings = audit.read(directory / "native_bindings.json")
    instance = audit.Audit(tmp_path, directory)
    for source in sources.values():
        ref = source["complete_original_snapshot"]
        instance.source_refs[ref["path"]] = ref
    db = sqlite3.connect(f"file:{tmp_path / 'work/native.sqlite3'}?mode=ro", uri=True)
    db.row_factory = sqlite3.Row
    names = {
        "standardized_facts": "fact_id",
        "derived_facts": "derived_id",
        "qa_candidates": "candidate_id",
        "qa_samples": "qa_id",
        "qa_operation_plans": "plan_id",
        "kg_builds": "kg_build_id",
        "qa_builds": "qa_build_id",
        "qa_quality_checks": "check_id",
    }
    tables = {
        name: {row[key]: dict(row) for row in db.execute("SELECT * FROM " + name)}
        for name, key in names.items()
    }
    db.close()
    compilations = {
        row["id"]: row for row in audit.read(directory / "QA/pattern_compilations.json")
    }
    for path in sorted((directory / "tasks").glob("*/task_bundle.json")):
        bundle = audit.read(path)
        surface = bundle["surface"]
        public_path = path.parent / "public_messages.json"
        row = {
            "task_id": bundle["task_id"],
            "bundle_id": bundle["id"],
            "path": str(path.relative_to(directory)),
            "public_path": str(public_path.relative_to(directory)),
            "public_messages_sha256": surface["public_messages_sha256"],
        }
        instance.task(directory, row, sources, bindings, tables, compilations, "dev", set())
    assert len(instance.task_ids) == 18
    assert not instance.failures, instance.failures[:10]
