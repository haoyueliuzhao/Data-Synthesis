"""Small pure controls; no artifact rescoring, model, GPU or private reference."""

from collections import Counter, defaultdict

import pytest
from report_finance_reference_revision_20260928 import (
    checked_invocation,
    digest,
    identity_summary,
    reference_values,
)


def test_reference_counts_only_whole_values_at_actual_resolver_fields():
    tool = {
        "name": "calculate",
        "normalized_arguments": {
            "expression": "prev:r9.output.result",
            "variables": {
                "a": "prev:r1.output.result",
                "b": "prose prev:r2.output.result",
                "c": ["prev:r3.output.value", "not a ref"],
            },
        },
    }
    assert reference_values(tool) == ["prev:r1.output.result", "prev:r3.output.value"]
    assert reference_values(
        {
            "name": "final_answer",
            "normalized_arguments": {
                "answer": ["prev:r1.output.result", "x"],
                "program": "prev:r2.output.program",
            },
        }
    ) == ["prev:r1.output.result"]
    assert reference_values(
        {
            "name": "read_source",
            "normalized_arguments": {"source_id": "prev:r1.output.sources.0.source_id"},
        }
    ) == ["prev:r1.output.sources.0.source_id"]
    assert not reference_values(
        {"name": "list_sources", "normalized_arguments": {"x": "prev:r1.output"}}
    )


def test_invocation_validates_coordinates_and_separates_model_from_tool():
    coordinates = {"run_id": "run", "episode_id": "ep", "attempt_index": 1, "turn_index": 2}
    model = {**coordinates, "invocation_id": "invocation:" + digest(coordinates)}
    assert (
        checked_invocation(
            model, expected_scope={"run_id": "run", "episode_id": "ep", "attempt": 1}
        )
        == coordinates
    )
    tool = {
        **coordinates,
        "invocation_id": "invocation:" + digest({**coordinates, "tool_index": 0}),
    }
    checked_invocation(tool, tool_index=0)
    with pytest.raises(ValueError, match="coordinates"):
        checked_invocation(model, tool_index=0)
    with pytest.raises(ValueError, match="foreign"):
        checked_invocation(
            model, expected_scope={"run_id": "other", "episode_id": "ep", "attempt": 1}
        )


def test_duplicate_technical_call_strings_are_counted_not_execution_deduplicated():
    counters = defaultdict(Counter)
    counters["model_invocation_ids"].update(["m1", "m2"])
    counters["tool_invocation_ids"].update(["t1", "t2"])
    counters["receipt_call_ids"].update(["same", "same"])
    counters["point_call_ids"].update([("p1", "same"), ("p2", "same")])
    result = identity_summary(counters)
    assert result["token_receipts"]["count"] == 2
    assert result["token_receipts"]["repeated_technical_call_id_strings"] == 1
    assert result["model_invocation_ids"]["unique"] == 2
    counters["model_invocation_ids"].update(["m1"])
    with pytest.raises(ValueError, match="duplicate actual"):
        identity_summary(counters)
