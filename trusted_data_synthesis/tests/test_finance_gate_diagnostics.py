from trusted_synthesis.finance_research.gate_diagnostics import (
    diagnose_episode,
    eligible_references,
)


def test_program_or_prose_does_not_count_as_executed_reference():
    event = {
        "name": "final_answer",
        "normalized_arguments": {"answer": 3, "program": "prev:r1.output.result"},
    }
    assert eligible_references(event) == []
    event = {
        "name": "calculate",
        "normalized_arguments": {
            "expression": "prev:r1.output.result",
            "variables": {"a": "prev:r2.output.result"},
        },
    }
    assert eligible_references(event) == [(("variables", "a"), "prev:r2.output.result")]


def test_unchecked_observation_is_null_not_false():
    result = diagnose_episode(
        {"turns": [{"receipt": None}], "tool_events": []},
        None,
        exact_registered_chain_match=False,
        numerical_replay_passed=True,
    )
    assert result["exact_registered_chain_match"] is False
    assert result["observation_checked"] is False
    assert result["prev_reference_used"] is None and result["visible_handle_verified"] is None
    assert result["numerical_replay_passed"] is True and result["new_model_calls"] == 0
