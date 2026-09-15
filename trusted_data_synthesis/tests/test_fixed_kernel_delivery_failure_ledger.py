"""Small CPU controls for evidence logic; no real sessions or model resources."""

import hashlib
import importlib
import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).parents[1] / "scripts/fixed_kernel_delivery_failure_ledger_20260915.py"
SPEC = importlib.util.spec_from_file_location("delivery_ledger_control", SCRIPT)
ledger = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ledger)


def session(tools, final=None):
    turns, events = [], []
    for index, tool in enumerate(tools):
        raw = ledger.canonical({"tool": tool["tool"], "arguments": tool["arguments"]})
        turns.append(
            {
                "response_index": index,
                "raw_response": raw,
                "raw_response_sha256": hashlib.sha256(raw.encode()).hexdigest(),
            }
        )
        events.append(
            {
                "response_index": index,
                "tool_call": {"call_id": f"tool:{index + 1}", "status": "ok", **tool},
                "final": False,
                "protocol_error": None,
            }
        )
    return {
        "id": "synthetic",
        "turns": turns,
        "events": events,
        "max_responses": 32,
        "identity": {"task_id": "task_test", "family": "dual_sufficient"},
        "initial_messages": [],
        "source_descriptors": [{"source_id": "s1"}, {"source_id": "s2"}],
        "terminal": "response_budget_exhausted",
        "first_final_index": final,
    }


def analyze(tools):
    return ledger.analyze_session(session(tools), {"path": "synthetic"}, "A_alpha0_11", "control")[
        0
    ]


def query(source="s1"):
    return {
        "tool": "query_source",
        "arguments": {"source_id": source, "concept": "us-gaap:Revenue"},
        "result": {"total": 0, "records": []},
    }


def test_final_forms_are_diagnostic_not_repaired():
    assert ledger.protocol_labels('{"final":{}}')[0]["canonical_top_level_final"] == 1
    assert not ledger.protocol_labels('{"Final":{}}')[0]["canonical_top_level_final"]
    assert (
        ledger.protocol_labels('```json\n{"final":{}}\n```')[0]["code_fenced_final_diagnostic_only"]
        == 1
    )
    assert ledger.protocol_labels('{"final":{},"final":{}}')[0]["strict_json_invalid"] == 1
    assert ledger.protocol_labels('{"x":{"final":{}}}')[0]["nested_final_key"] == 1


def test_repeat_uses_public_content_state_not_number_of_tools():
    rows = [
        query(),
        query(),
        {
            "tool": "list_concepts",
            "arguments": {"source_id": "s1"},
            "result": {"concepts": [{"concept": "us-gaap:Revenue"}]},
        },
        query(),
        query(),
        query("s2"),
    ]
    report = analyze(rows)
    assert report["observed_counts"]["query_same_canonical_arguments"] == 3
    assert report["observed_counts"]["query_repeat_without_new_public_evidence"] == 2
    assert report["first_observed_step_one_based"]["list_concepts_nonempty"] == 3
    assert not report["flags"][
        "joint_no_discovery_no_numeric_read_no_successful_calculation_no_final"
    ]


def test_pointer_provenance_is_source_aware_and_preceding():
    rows = [
        {
            "tool": "query_source",
            "arguments": {"source_id": "s1"},
            "result": {
                "records": [{"source_id": "s1", "native_pointer": "/facts/x", "record": {"val": 3}}]
            },
        },
        {
            "tool": "read_json",
            "arguments": {"source_id": "s2", "pointer": "/facts/x"},
            "result": {"items": []},
        },
        {
            "tool": "read_json",
            "arguments": {"source_id": "s1", "pointer": "/facts/x"},
            "result": {"items": [{"pointer": "/facts/x/val", "value": 3}]},
        },
    ]
    report = analyze(rows)
    assert report["observed_counts"]["read_json:pointer_not_observed_in_prior_return"] == 1
    assert report["observed_counts"]["read_json:pointer_from_prior_public_return"] == 1
    assert report["flags"]["numeric_source_read_observed"]


def test_numeric_calculation_provenance_is_not_question_correctness():
    rows = [
        {
            "tool": "read_source",
            "arguments": {"source_id": "s1", "native_pointer": "/facts/x"},
            "result": {
                "source_id": "s1",
                "native_pointer": "/facts/x",
                "record": {"val": 3},
                "exact_value": "3",
                "unit": "USD",
            },
        },
        {
            "tool": "calculate",
            "arguments": {"expression": "x*2", "variables": {"x": {"result_id": "tool:1"}}},
            "result": {"exact_value": "6", "unit": "USD", "used_result_ids": ["tool:1"]},
        },
    ]
    report = analyze(rows)
    assert report["observed_counts"]["calculate_success_all_dependencies_source_traceable"] == 1
    assert report["flags"]["successful_calculation_but_no_final"]
    assert (
        report["calculation_examples"][0]["requested_physical_quantity_correctness"]
        == "NOT_ASSESSED"
    )
    assert "financial_valid" not in report


def test_real_query_runtime_nullable_public_metadata_defect(monkeypatch):
    """One targeted defect control, not a repetition of the audit's eight queries."""
    import pytest

    monkeypatch.syspath_prepend(str(Path(__file__).parents[1] / "src"))
    runtime = importlib.import_module(
        "trusted_synthesis.experiments.finance_qa_vnext_eval_readiness.runtime"
    )
    for nullable_field in ("label", "description"):
        concept = {
            "label": "Revenue",
            "description": "Revenue",
            "units": {"USD": []},
            nullable_field: None,
        }
        sources = runtime.SnapshotSources.synthetic(
            {"s": {"facts": {"us-gaap": {"Revenue": concept}}}}
        )
        with pytest.raises(TypeError, match="NoneType"):
            sources.query({"source_id": "s", "label_contains": "Revenue", "unit": "USD"})
