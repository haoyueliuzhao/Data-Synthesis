"""Only new source-view compilation and live/replay contract controls."""

import copy
import importlib
import sys
from pathlib import Path

SCRIPTS = Path(__file__).parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
compiler = importlib.import_module("fixed_kernel_source_view_compile_20260915")
view_runtime = importlib.import_module("fixed_kernel_source_view_runtime_20260915")
p = view_runtime.p


def inputs():
    periods = [
        {"start": "2020-01-01", "end": "2020-12-31"},
        {"start": "2021-01-01", "end": "2021-12-31"},
    ]
    public = {
        "question": "Synthetic question",
        "period_contract": {"task_id": "synthetic", "periods": periods},
        "quantity_contract": {"unit": "USD", "decimal_places": 2},
        "tool_contract": dict.fromkeys(
            ("calculate", "select_max", "compare", "lookup_selected", "Final"), "synthetic"
        ),
    }
    records = [
        {
            "source_id": "old-" + str(index),
            "source_kind": "original_companyfacts_observation",
            "raw_sha256": "synthetic-source-sha",
            "native_pointer": "/facts/us-gaap/X/units/USD/" + str(index),
            "original_url": "https://example.invalid/synthetic",
            "unit": "USD",
            "label": "Original label",
            "definition": "Original definition",
            "concept": concept,
            "record": {"start": str(year) + "-01-01", "end": str(year) + "-12-31", "val": value},
            "graph_ready_for_registered_tasks": index % 2 == 0,
        }
        for index, (concept, year, value) in enumerate(
            [
                ("us-gaap:Revenue", 2020, 5),
                ("us-gaap:Revenue", 2021, 8),
                ("us-gaap:OtherMetric", 2021, 19),
                ("us-gaap:Revenue", 2025, 25),
            ]
        )
    ]
    return public, {"source_id": "raw-public-object", "native_annual_records": records}


def test_public_window_keeps_other_metrics_and_is_value_and_route_blind():
    public, document = inputs()
    result, _ = compiler.compile_public(public, document, p)
    assert len(result["sources"]) == 3
    assert {row["concept"] for row in result["sources"]} == {
        "us-gaap:Revenue",
        "us-gaap:OtherMetric",
    }
    altered = copy.deepcopy(public)
    altered["period_contract"].update(metric_ids=["unrelated"], operation={"kind": "different"})
    other, _ = compiler.compile_public(altered, document, p)
    assert result["sources"] == other["sources"]
    modified = copy.deepcopy(document)
    modified["native_annual_records"][0]["record"]["val"] = 999
    shifted, _ = compiler.compile_public(public, modified, p)
    assert [row["source_id"] for row in result["sources"]] == [
        row["source_id"] for row in shifted["sources"]
    ]
    assert all("graph_ready_for_registered_tasks" not in row for row in result["sources"])


def test_mechanical_read_uses_original_amount_pointer_and_unit_conversion():
    public, document = inputs()
    visible, _ = compiler.compile_public(public, document, p)
    sources = view_runtime.SourceViewSources(visible)
    row = visible["sources"][0]
    args = {"source_id": row["source_id"], "unit": "million USD"}
    actual = sources.read_source(args)
    trained = view_runtime.training.read_source(args, visible)
    assert all(actual[key] == value for key, value in trained.items())
    assert actual["source_id"] == "raw-public-object"
    assert actual["native_pointer"] == row["native_pointer"]
    assert actual["record"] == row["record"]
    assert actual["actual_period"]["end"] == row["record"]["end"]


def test_fresh_tools_and_identical_online_offline_replay():
    public, document = inputs()
    visible, _ = compiler.compile_public(public, document, p)
    messages = [{"role": "user", "content": p.encode(visible).decode()}]
    identity = {
        "task_id": "synthetic",
        "family": "dual_sufficient",
        "surface_version_id": "new-view",
        "parent_manifest_id": "new-manifest",
        "public_messages_sha256": p.sha(p.encode(messages)),
    }
    sources = view_runtime.SourceViewSources(visible)
    bound = view_runtime.build_runtime()
    scripted = [
        {"tool": "read_source", "arguments": {"source_id": visible["sources"][0]["source_id"]}},
        {
            "tool": "calculate",
            "arguments": {
                "expression": "x+1",
                "variables": {"x": {"result_id": "tool:1"}},
                "unit": "USD",
            },
        },
        {"final": {"value": "20", "unit": "USD", "result_id": "tool:2"}},
    ]
    session = bound.generate(
        messages, identity, sources, scripted=scripted, requested_basis="neutral"
    )
    assert session["events"][0]["tool_call"]["call_id"] == "tool:1"
    assert session["first_final_index"] == 2
    assert len(session["initial_messages"]) == 2
    assert bound.replay_session(session, sources) == session
    assert session["starts_without_Probe_history"] is True
    assert session["utility_environment"] == "J_sources_not_J_snapshot"
