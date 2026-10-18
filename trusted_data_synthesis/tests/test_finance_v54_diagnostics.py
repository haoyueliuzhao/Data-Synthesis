"""CPU controls for exact original-parser classification and bounded selection."""

import pytest

import finqa_v54_diagnostics as diagnostics

VALID = '<tool_call>{"name":"run_program","arguments":{"program":"add(1,2)"}}</tool_call>'


@pytest.mark.parametrize(("raw", "category"), [
    ("The answer is 3.", "A_no_opening_envelope"),
    ("<tool_call broken>" + VALID, "B_malformed_tag_in_prose_prefix"),
    (VALID + "unpermitted trailing prose", "C_non_envelope_between_or_after_envelopes"),
    ('<tool_call>{"name":"x","arguments":{},"extra":1}</tool_call>', "D_invalid_call_object_schema"),
    ('<tool_call>{"name":"x","arguments":{}}', "E_missing_closing_envelope"),
    ('<tool_call>{"name":"x","name":"y","arguments":{}}</tool_call>',
     "F_strict_JSON_or_argument_extraction_exception"),
    ('<tool_call>{"name":"x","arguments":{"value":NaN}}</tool_call>',
     "F_strict_JSON_or_argument_extraction_exception"),
    ("Allowed initial prose\n" + VALID, "G_accepted_tool_envelopes"),
    ('<tool_call>{"name":"x","arguments":{"text":"</tool_call>"}}</tool_call>',
     "G_accepted_tool_envelopes"),
])
def test_first_original_rejection_branch_and_unchanged_parse_result(raw, category):
    result = diagnostics.classify_response(raw, call_prefix="saved")
    prefix, calls = diagnostics.qwen_protocol.parse_qwen_native_response(raw, call_prefix="saved")
    assert result["category"] == category
    assert result["canonical_prefix"] == prefix
    assert result["calls"] == [call.model_dump(mode="json") for call in calls]
    if raw == VALID + "unpermitted trailing prose":
        assert result["calls"] == []  # A valid prefix never becomes an accepted trajectory.


def test_selection_is_bounded_deterministic_category_then_digest_round_robin():
    rows = [dict(available=True, category=category, task_key=f"q{i}",
                 episode={"sha256":f"{i:064d}"})
            for category in ("C", "A", "B") for i in reversed(range(12))]
    selected = diagnostics.select_examples(rows)
    assert len(selected) == 10
    assert [row["category"] for row in selected[:3]] == ["A", "B", "C"]
    assert [row["task_key"] for row in selected[:3]] == ["q0"]*3
    assert diagnostics.select_examples(list(reversed(rows))) == selected
    assert not diagnostics.select_examples([dict(available=False, category="NA")])


def test_normalized_quantiles_preserve_endpoints_and_do_not_reweight_C():
    values = diagnostics.quantiles([-2.0, 0.0, 2.0])
    assert values["0"] == -2 and values["0.5"] == 0 and values["1"] == 2
    assert values["0.25"] == -1
    assert diagnostics.quantiles([]) is None
