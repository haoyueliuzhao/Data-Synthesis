"""Bounded A/T wiring controls only; synthetic fixtures, no provider or old replays."""

import ast
import inspect
import json
import subprocess
from decimal import Decimal
from pathlib import Path

import pytest

from trusted_synthesis.experiments.finance_qa_vnext_finqa_difficulty.sources import catalog
from trusted_synthesis.experiments.finance_qa_vnext_thinking_comparison import evaluate as previous
from trusted_synthesis.experiments.finance_qa_vnext_thinking_comparison.online.common import (
    SYSTEM as PREVIOUS_SYSTEM,
)
from trusted_synthesis.experiments.finance_qa_vnext_thinking_comparison.online.common import (
    encode,
)
from trusted_synthesis.experiments.finance_qa_vnext_trace_delivery import evaluate
from trusted_synthesis.experiments.finance_qa_vnext_trace_delivery.instructions import (
    SYSTEMS,
    TRACE_SUFFIX,
    capsule_files,
)
from trusted_synthesis.experiments.finance_qa_vnext_trace_delivery.plan import (
    CONDITIONS,
    LABELS,
    MODEL,
    TASKS,
    WORKER_PYTHON,
    condition,
    registrations,
)
from trusted_synthesis.experiments.finance_qa_vnext_trace_delivery.stage import (
    assert_public,
    public_document,
)

ROOT = Path(__file__).resolve().parents[2]
PREVIOUS_ONLINE = (
    ROOT
    / "trusted_data_synthesis/src/trusted_synthesis/experiments"
    / "finance_qa_vnext_thinking_comparison/online"
)
CAPSULE_MEMBERS = {"common.py", "worker.py", "calculator.py", "isolate.py", "projection.py"}


def control_private(value="13"):
    return {
        "facts": {"source:x": {"value": value}},
        "target": "source:x",
        "relations": {},
        "unit": "percent",
    }


def run_isolated(base, arm, script):
    """Exercise the same standalone capsule that collection will launch, without HTTP."""
    base.mkdir(parents=True)
    code = base / "worker_code"
    code.mkdir()
    for name, content in capsule_files(ROOT, arm).items():
        (code / name).write_bytes(content)
    public = {
        "task_id": "synthetic-control-not-panel",
        "question": "A constructed control; the answer unit is percent.",
        "numeric_catalog": [{"id": "source:x", "segment": "p0", "value": "13", "token": "13"}],
        "segments": {"p0": {"text": "13 units", "locator": ["pre_text", 0]}},
    }
    (base / "public.json").write_bytes(encode(public))
    (base / "private.json").write_text(
        '{"program":"NEVER_VISIBLE_PRIVATE_REFERENCE","exe_ans":9999}'
    )
    (base / "script.json").write_bytes(encode(script))
    output = base / "session"
    completed = subprocess.run(
        [
            WORKER_PYTHON,
            "-I",
            "-S",
            "-B",
            str(code / "worker.py"),
            "--public",
            str(base / "public.json"),
            "--output",
            str(output),
            "--forbidden",
            str(base / "private.json"),
            "--script",
            str(base / "script.json"),
            "--model",
            MODEL,
        ],
        cwd=code,
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
        env={"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8"},
    )
    assert completed.returncode == 0, completed.stderr
    return output, json.loads((output / "result.json").read_text()), public


@pytest.fixture(scope="module")
def paired_controls(tmp_path_factory):
    base = tmp_path_factory.mktemp("trace_delivery_synthetic")
    # A legal product with absent provenance and deliberately wrong financial interpretation.
    # It must execute in both arms; no evaluator may demand a corrected relation or sources.
    script = [
        {
            "message": "A deliberately inappropriate relation for this constructed control.",
            "tool": "calculate",
            "arguments": {"expression": "q*p", "variables": {"q": "13", "p": "33.32"}},
        },
        {"final": {"value": "433.16", "unit": "percent", "result_id": "tool:1"}},
        {"tool": "calculate", "arguments": {"expression": "9999"}},
    ]
    return {arm: run_isolated(base / arm, arm, script) for arm in ("A", "T")}


def test_capsules_preserve_every_old_byte_except_appended_t_system_assignment():
    old = {name: (PREVIOUS_ONLINE / name).read_bytes() for name in CAPSULE_MEMBERS}
    autonomous = capsule_files(ROOT, "A")
    delivery = capsule_files(ROOT, "T")
    assert set(autonomous) == set(delivery) == CAPSULE_MEMBERS
    assert autonomous == old
    assert {name for name in old if delivery[name] != old[name]} == {"common.py"}
    assert delivery["common.py"].startswith(old["common.py"])
    appended = ast.parse(delivery["common.py"][len(old["common.py"]) :])
    assert len(appended.body) == 1 and isinstance(appended.body[0], ast.Assign)
    assignment = appended.body[0]
    assert len(assignment.targets) == 1
    assert isinstance(assignment.targets[0], ast.Name) and assignment.targets[0].id == "SYSTEM"
    assert isinstance(assignment.value, ast.BinOp) and isinstance(assignment.value.op, ast.Add)
    assert isinstance(assignment.value.left, ast.Name) and assignment.value.left.id == "SYSTEM"
    assert isinstance(assignment.value.right, ast.Constant)
    assert assignment.value.right.value == "\n\n" + TRACE_SUFFIX
    namespace = {}
    exec(compile(delivery["common.py"], "synthetic_capsule_common.py", "exec"), namespace)
    assert namespace["SYSTEM"] == SYSTEMS["T"]


def test_t_is_one_fixed_suffix_of_the_literal_autonomous_system():
    assert set(SYSTEMS) == set(CONDITIONS) == {"A", "T"}
    assert SYSTEMS["A"].encode() == PREVIOUS_SYSTEM.encode()
    assert TRACE_SUFFIX.strip() and SYSTEMS["T"] == PREVIOUS_SYSTEM + "\n\n" + TRACE_SUFFIX
    assert not any(key in TRACE_SUFFIX for key in TASKS)


def test_preregistered_population_is_paired_all_flash_and_bounded():
    assert TASKS == ("N1", "N2", "N3", "N4", "N5", "N6")
    assert MODEL == "deepseek-v4-flash"
    assert len(LABELS) == len(set(LABELS)) == 24
    expected = tuple(
        f"{arm}_{key}_{rep:02d}"
        for rep in (1, 2)
        for key in TASKS
        for arm in (("A", "T") if rep == 1 else ("T", "A"))
    )
    assert LABELS == expected
    rows = registrations({key: {"task_id": "synthetic:" + key, "id": key} for key in TASKS})
    assert {row["requested_model"] for row in rows} == {MODEL}
    assert sum(row["response_budget"] for row in rows) == 768
    assert all(row["tool_budget"] == 32 and row["fresh_independent_session"] for row in rows)
    for key in TASKS:
        for arm in ("A", "T"):
            assert [
                row["replicate"] for row in rows if row["task_key"] == key and row["arm"] == arm
            ] == [1, 2]
    assert condition()["maximum_model_requests"] == 768


def test_public_document_whitelists_full_source_and_all_numbers_without_instruction():
    entry = {
        "filename": "synthetic_annual_report_not_an_experimental_task",
        "qa": {"question": "What percentage is represented?", "program": "hidden", "exe_ans": 9999},
        "table": [["period", "2020", "2019"], ["amount", "13.00", "29.00"]],
        "pre_text": ["An unrelated 11.7% observation is retained."],
        "post_text": ["A rounded amount of 13 and a fine amount of 13.004 coexist."],
        "arm": "not public",
    }
    segments, facts = catalog(entry)
    task = {
        "qa_id": "synthetic:full-source",
        "entry": entry,
        "facts": facts,
        "selected": [next(iter(facts))],
    }
    result = public_document(task)
    assert result["source"] == {key: entry[key] for key in ("table", "pre_text", "post_text")}
    assert result["segments"] == segments and result["numeric_catalog"] == list(facts.values())
    assert len(result["numeric_catalog"]) > len(task["selected"])
    assert (
        not {"arm", "instruction", "instructions", "selected", "facts", "reference", "target"}
        & result.keys()
    )
    assert "hidden" not in encode(result).decode() and "9999" not in encode(result).decode()


def test_private_targets_condition_labels_and_instructions_are_rejected_recursively():
    for name in (
        "program",
        "exe_ans",
        "target",
        "selected",
        "facts",
        "reference",
        "arm",
        "instruction",
    ):
        with pytest.raises(ValueError, match="hidden_field"):
            assert_public({"source": [{name: "synthetic private or condition metadata"}]})


@pytest.mark.parametrize("arm", ("A", "T"))
def test_first_final_still_ends_without_compute_even_in_t(tmp_path, arm):
    output, result, _ = run_isolated(
        tmp_path / arm,
        arm,
        [
            {"final": None, "tool": "calculate", "arguments": {"expression": "1/0"}},
            {"tool": "calculate", "arguments": {"expression": "13"}},
        ],
    )
    assert result["terminal"] == "model_final"
    assert result["model_requests"] == 1 and result["tool_calls"] == 0
    assert result["provider_attempts"] == 0 and not result["online_answer_feedback"]
    assert not (output / "turns/000_tool.json").exists()


def test_t_missing_provenance_and_wrong_finance_still_execute_with_no_online_repair(
    paired_controls,
):
    output, result, _ = paired_controls["T"]
    calculation = result["events"][0]["tool_call"]["output"]
    assert calculation["status"] == "ok" and calculation["result"]["exact_value"] == "10829/25"
    assert not calculation["result"]["source_declarations_validated"]
    assert not calculation["result"]["financial_meaning_certified"]
    assert result["terminal"] == "model_final" and result["model_requests"] == 2
    assert result["tool_calls"] == 1 and not result["online_answer_feedback"]
    messages = json.loads((output / "turns/001_http_request.body").read_text())["messages"]
    assert len(messages) == 4
    assert json.loads(messages[-1]["content"]) == {"tool_result": calculation}
    assert (
        evaluate.answer_score("433.16", "percent", control_private())["task_answer_status"]
        == "FAIL"
    )


def test_actual_http_request_body_contains_t_suffix_and_no_other_condition_change(paired_controls):
    for index in (0, 1):
        bodies = {}
        for arm, (output, result, _) in paired_controls.items():
            body = json.loads((output / f"turns/{index:03d}_http_request.body").read_text())
            assert body["messages"][0] == {"role": "system", "content": SYSTEMS[arm]}
            assert body["model"] == result["requested_model"] == MODEL
            assert body["thinking"] == {"type": "enabled"}
            assert body["reasoning_effort"] == "high" and body["max_tokens"] == 16384
            assert not {"temperature", "top_p", "tools", "reasoning_content"} & body.keys()
            body["messages"][0]["content"] = PREVIOUS_SYSTEM
            bodies[arm] = body
        assert bodies["A"] == bodies["T"]


def test_continuous_history_remains_literal_and_auditor_requires_the_actual_system(paired_controls):
    for arm, (output, _, public) in paired_controls.items():
        first = json.loads((output / "turns/000_http_request.body").read_text())["messages"]
        second = json.loads((output / "turns/001_http_request.body").read_text())["messages"]
        assert second[: len(first)] == first
        assert (
            second[len(first)]["content"].encode()
            == (output / "turns/000_assistant.raw").read_bytes()
        )
        audit = evaluate.audit_session(
            output, public, control_private(), expected_system=SYSTEMS[arm], model_required=False
        )
        assert audit["raw_model_and_history_verified"] and audit["no_final_retry"]
        assert audit["calculations"][0]["independent_execution_verified"]
        with pytest.raises(ValueError, match="full_exact_history"):
            evaluate.audit_session(
                output,
                public,
                control_private(),
                expected_system=SYSTEMS["T" if arm == "A" else "A"],
                model_required=False,
            )
        with pytest.raises(ValueError, match="actual_model_origin"):
            evaluate.audit_session(output, public, control_private(), expected_system=SYSTEMS[arm])


def test_isolated_capsules_still_deny_private_reference_access(paired_controls):
    for output, result, _ in paired_controls.values():
        isolation = json.loads((output / "isolation.json").read_text())
        assert isolation["landlock_abi"] >= 3
        assert isolation["private_read_probes"] and all(
            row["read_denied"] for row in isolation["private_read_probes"]
        )
        assert isolation["repository_modules_loaded"] == []
        assert isolation["isolated_mode"] and isolation["no_site"]
        assert result["origin"] == "scripted_control" and result["provider_attempts"] == 0
        assert all(
            b"NEVER_VISIBLE_PRIVATE_REFERENCE" not in path.read_bytes()
            for path in output.rglob("*")
            if path.is_file()
        )


def test_frozen_v2_numeric_and_display_function_source_is_unchanged():
    for name in ("answer_score", "display_compatible", "trace_checks"):
        assert (
            inspect.getsource(getattr(evaluate, name)).encode()
            == inspect.getsource(getattr(previous, name)).encode()
        )


def test_frozen_v2_representative_precision_boundaries_have_identical_scores():
    cases = (
        ("997/70", "14.242857142857142", "percent"),
        ("997/70", "14.23", "percent"),
        ("997/70", "0.14242857142857142", "percent"),
        ("1/3", "0.333333333333", "%"),
        ("1/3", "333333333333/1000000000000", "%"),
        ("13", None, "percent"),
    )
    for target, value, unit in cases:
        assert evaluate.answer_score(value, unit, control_private(target)) == previous.answer_score(
            value, unit, control_private(target)
        )
    assert evaluate.answer_score("0.333333333333", "%", control_private("1/3"))["numeric_correct"]
    assert not evaluate.answer_score("333333333333/1000000000000", "%", control_private("1/3"))[
        "numeric_correct"
    ]


def test_missing_or_incorrect_units_are_not_relaxed_by_trace_instruction():
    for unit in (None, "", "USD million", "ratio", "basis points"):
        score = evaluate.answer_score("13", unit, control_private())
        assert score == previous.answer_score("13", unit, control_private())
        assert score["numeric_correct"] and not score["unit_correct"]
        assert score["task_answer_status"] == "FAIL"


def test_new_billion_publication_aliases_do_not_convert_or_relax_numbers():
    private = {**control_private("68.9"), "unit": "USD_billion"}
    for unit in ("USD_billion", "USD billion", "billions", "billions of dollars"):
        assert evaluate.answer_score("68.9", unit, private)["task_answer_status"] == "PASS"
    assert evaluate.answer_score("68.9", "USD_million", private)["task_answer_status"] == "FAIL"
    assert evaluate.answer_score("0.0689", "USD_billion", private)["task_answer_status"] == "FAIL"


def test_internal_rounding_compatibility_is_distinct_from_reference_precision():
    private = control_private("1530000/139549")
    review = {
        "published_value": "10.967741935",
        "published_unit": "percent",
        "secondary_answer_values": [{"value": "10.97", "unit": "percent"}],
        "final_answer_consistency": {"status": "PASS"},
    }
    before = encode(review)
    score = evaluate.answer_score(review["published_value"], review["published_unit"], private)
    diagnostic = evaluate.internal_final_diagnostics(review)
    assert diagnostic["status"] == "PASS"
    assert diagnostic["pairs"] == [
        {"secondary_index": 0, "internal_display_intervals_overlap": True}
    ]
    assert not evaluate.display_compatible(
        score["reference_exact_value"], "percent", "10.97", "percent"
    )
    assert score["task_answer_status"] == "FAIL" and diagnostic["diagnostic_only"]
    assert not diagnostic["affects_answer_score"] and not diagnostic["affects_trace_score"]
    assert encode(review) == before
    assert score == previous.answer_score(
        review["published_value"], review["published_unit"], private
    )


def test_internal_scale_conflict_and_absent_secondary_are_separate_diagnostics():
    assert (
        evaluate.internal_display_compatible("0.14912841106", "percent", "14.91284", "percent")
        is False
    )
    assert evaluate.internal_display_compatible("13", "percent", "13", "USD_million") is False
    assert evaluate.internal_display_compatible(None, "percent", "13", "percent") is None
    diagnostic = evaluate.internal_final_diagnostics(
        {
            "published_value": "13",
            "published_unit": "percent",
            "secondary_answer_values": [],
            "final_answer_consistency": {"status": "PASS"},
        }
    )
    assert diagnostic["status"] == "NOT_ESTABLISHED" and diagnostic["pairs"] == []
    assert not diagnostic["affects_answer_score"] and not diagnostic["affects_trace_score"]


def test_blinded_packet_omits_system_arm_model_and_cost_metadata():
    audit = {
        "label": "T_synthetic_01",
        "arm": "T",
        "requested_model": MODEL,
        "system_prompt": SYSTEMS["T"],
        "usages": [987654321],
        "raw_final": {"value": "13"},
        "terminal": "model_final",
        "calculations": [],
        "first_final_index": 0,
    }
    packet = evaluate.blinded_packet(
        audit, "synthetic-control", {0: '{"final":{"value":"13"}}'}, "R-synthetic"
    )
    raw = encode(packet).decode()
    assert not any(text in raw for text in ("T_synthetic_01", MODEL, TRACE_SUFFIX, "987654321"))
    assert not {"arm", "system_prompt", "requested_model", "usages"} & packet.keys()


def test_cost_uses_same_flash_rate_for_a_and_t_and_keeps_unknown_reservations(tmp_path):
    online = tmp_path / "synthetic_cost_only"
    rows = [
        {"label": label, "task_key": "synthetic", "arm": arm, "requested_model": MODEL}
        for label, arm in (("A_known", "A"), ("T_known", "T"), ("T_unknown", "T"))
    ]
    for row in rows:
        turns = online / "sessions" / row["label"] / "turns"
        turns.mkdir(parents=True)
        (turns / "000_reservation.json").write_bytes(
            encode(
                {"request_bytes": 100, "reserved_token_allowance": 115712, "requested_model": MODEL}
            )
        )
        if row["label"] == "T_unknown":
            continue
        (turns / "000_outcome.json").write_bytes(
            encode(
                {
                    "usage": {
                        "prompt_tokens": 100,
                        "completion_tokens": 10,
                        "total_tokens": 110,
                        "prompt_cache_hit_tokens": 40,
                        "prompt_cache_miss_tokens": 60,
                        "completion_tokens_details": {"reasoning_tokens": 6},
                    },
                    "response_bytes": 70,
                    "reasoning_telemetry": {"nonempty": True, "characters": 17},
                    "elapsed_ns": 1000,
                }
            )
        )
    (online / "launch.json").write_bytes(encode({"registrations": rows}))
    report = evaluate.cost_summary(online)
    costs = {row["label"]: row for row in report["rows"]}
    assert (
        costs["A_known"]["published_rate_estimate_cny"]
        == costs["T_known"]["published_rate_estimate_cny"]
    )
    expected = (
        Decimal(40) * Decimal("0.05") + Decimal(60) * Decimal("1.5") + Decimal(10) * Decimal("4.5")
    ) / Decimal(1000000)
    assert Decimal(costs["T_known"]["published_rate_estimate_cny"]["offpeak"]) == expected
    assert costs["T_unknown"]["published_rate_estimate_cny"] is None
    assert report["aggregate"]["reserved_attempts"] == 3
    assert report["aggregate"]["provider_usage"]["total_tokens"]["complete_sum"] is None
    assert report["aggregate"]["provider_usage"]["total_tokens"]["observed_sum"] == 220
    assert (
        report["all_registered_sessions_included"] and report["reasoning_is_subset_not_added_twice"]
    )


def test_full_population_amortization_has_no_finite_cost_at_zero_trace_yield():
    # Purely constructed accounting inputs, not records of experimental observations.
    rows = [
        {
            "label": f"synthetic-fixture-{key}-{rep}",
            "arm": "T",
            "task_key": key,
            "terminal": "model_final" if rep == 1 else "unknown_transport",
            "answer": {"task_answer_status": "FAIL" if rep == 1 else "UNDETERMINED"},
            "formula_driven_trace_verified": False,
            "successful_calculations": 0,
        }
        for key in TASKS
        for rep in (1, 2)
    ]
    costs = {
        "rows": [
            {
                "label": row["label"],
                "arm": "T",
                "published_rate_estimate_cny": {"offpeak": "0.01", "peak": "0.02"},
                "provider_usage": {
                    "total_tokens": {
                        "observed_sum": 100,
                        "observed_attempts": 1,
                        "missing_attempts": 0,
                        "complete_sum": 100,
                    }
                },
                "reserved_attempts": 1,
                "tool_calls": 0,
                "successful_calculations": 0,
                "summed_request_elapsed_ns": 10,
            }
            for row in rows
        ],
        "aggregate": {"provider_usage": {"total_tokens": {}}},
    }
    summary = evaluate.condition_summary("T", rows, costs)
    assert summary["registered"] == 12
    assert summary["answer_counts"] == {"FAIL": 6, "UNDETERMINED": 6}
    assert summary["costs"]["amortized_estimate_cny_per_verified_trace"] is None
    assert summary["costs"]["total_tokens_per_verified_trace"] is None
    rows[0]["answer"]["task_answer_status"] = "PASS"
    rows[0]["formula_driven_trace_verified"] = True
    rows[0]["successful_calculations"] = 1
    costs["rows"][0]["successful_calculations"] = 1
    costs["rows"][0]["tool_calls"] = 1
    summary = evaluate.condition_summary("T", rows, costs)
    assert summary["answer_pass_rate"] == summary["formula_driven_verified_rate"] == "1/12"
    assert summary["by_task"][TASKS[0]]["answer_pass_rate"] == "1/2"
    assert Decimal(
        summary["costs"]["amortized_estimate_cny_per_verified_trace"]["offpeak"]
    ) == Decimal("0.12")
    assert summary["costs"]["total_tokens_per_verified_trace"] == "1200"
