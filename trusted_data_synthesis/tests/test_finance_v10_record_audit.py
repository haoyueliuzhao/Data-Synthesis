"""Synthetic record-corruption controls; no original model/API/GPU calls."""

import copy
import json

from test_finance_public_reasoning import call, mocked_episode
from test_finance_research_datasets import finqa_record

from trusted_synthesis.finance_research import v10_record_audit as audit
from trusted_synthesis.finance_research.datasets import adapt_finqa
from trusted_synthesis.finance_research.providers import canonical_assistant_message


class TextTokenizer:
    """Fixture renderer, not the real tokenizer used by the actual audit."""

    def apply_chat_template(self, messages, **kwargs):
        return "\n".join(m.get("content", "") for m in messages) + "\nassistant"


def episode(responses):
    bundle = adapt_finqa([finqa_record()], split="train", revision="v10-CPU-only")[0]
    saved, _ = mocked_episode(bundle, responses)
    slot = dict(task_id=bundle.public.task_id, slot_id="synthetic/s0", slot_index=0)
    return bundle.public, saved, slot


def test_public_content_and_raw_arguments_view_and_request_chain_are_distinct_from_quality():
    task, saved, slot = episode(
        [
            (
                "Two source figures are 8 and 2.",
                [call("run_program", {"program": "subtract(8, 2)"})],
            ),
            (
                "The execution returned 6; submit this program.",
                [call("submit_program", {"program": "subtract(8, 2)"})],
            ),
        ]
    )
    row, detail = audit.inspect_episode(
        saved, task, slot, q_native=True, tokenizer=TextTokenizer(), capture=True
    )
    assert not row["issues"] and row["checks"]["request_history_chain_exact"]
    assert row["counts"]["public_content_nonempty_turns"] == 2
    assert row["counts"]["observations_with_next_model_request"] == 1
    assert row["counts"]["terminal_observations_without_next_request"] == 1
    assert row["substantive_reasoning"] == row["semantic_observation_update"] == "not_measured"
    assert row["positive_mask"] is None and not row["material_admission"]
    assert (
        detail["turns"][0]["actual_next_request"]
        == saved.turns[1].provider_metadata["public_request"]
    )
    assert detail["turns"][1]["actual_next_request"] is None
    assert detail["turns"][0]["Student_text"]["rendered_response"].startswith(
        saved.turns[0].raw_text
    )


def test_missing_observation_in_actual_next_request_is_not_repaired():
    task, saved, slot = episode(
        [
            ("R: compute.", [call("run_program", {"program": "subtract(8, 2)"})]),
            ("U: use the result.", [call("submit_program", {"program": "subtract(8, 2)"})]),
        ]
    )
    changed = copy.deepcopy(saved.turns[1].provider_metadata)
    changed["public_request"]["messages"].pop()
    edited = saved.model_copy(
        update={
            "turns": (
                saved.turns[0],
                saved.turns[1].model_copy(update={"provider_metadata": changed}),
            )
        }
    )
    row, detail = audit.inspect_episode(edited, task, slot, q_native=True, capture=True)
    assert not row["checks"]["request_history_chain_exact"]
    assert detail["turns"][1]["actual_request"] == changed["public_request"]
    assert row["semantic_observation_update"] == "not_measured"


def test_error_then_changed_action_is_only_a_mechanical_candidate():
    task, saved, slot = episode(
        [
            ("R: I will calculate.", [call("run_program", {"program": "divide(8, 0)"})]),
            ("U: use another expression.", [call("submit_program", {"program": "subtract(8, 2)"})]),
        ]
    )
    row, _ = audit.inspect_episode(saved, task, slot, q_native=True)
    assert row["case_candidates"]["error_then_changed_action_candidate"]
    assert row["has_saved_tool_error"] and row["semantic_revision"] == "not_measured"
    assert row["checks"]["Student_text_rendering_checked"] is False
    assert row["checks"]["Student_public_body_preserved"] is None


def test_case_categories_may_overlap_and_do_not_select_only_correct_answers():
    task, saved, slot = episode(
        [
            ("I will submit.", [call("submit_program", {"program": "add(8, 2)"})]),
        ]
    )
    flags = audit.behavior_candidates(saved, False)
    assert flags["direct_submission"] and flags["normal_model_failure"]
    assert not flags["execute_then_submit"]
    row, _ = audit.inspect_episode(saved, task, slot, q_native=False)
    assert row["financial_process_correctness"] == "not_measured"


def test_unparsed_original_call_remains_raw_view_evidence_not_invented_student_action():
    task, saved, slot = episode([("", [call("run_program", {"program": "subtract(8, 2)"})])])
    turn = saved.turns[0]
    metadata = copy.deepcopy(turn.provider_metadata)
    metadata["api_response"]["choices"][0]["message"]["tool_calls"][0]["function"]["arguments"] = (
        "{"
    )
    turn = turn.model_copy(update={"provider_metadata": metadata, "tool_calls": ()})
    edited = saved.model_copy(
        update={
            "turns": (turn,),
            "tool_events": (),
            "stop_reason": "no_tool_call",
            "final_program": None,
            "messages": (*saved.messages[:2], canonical_assistant_message(turn)),
        }
    )
    row, detail = audit.inspect_episode(
        edited, task, slot, q_native=False, tokenizer=TextTokenizer(), capture=True
    )
    assert row["counts"]["turns_with_unparsed_API_tool_calls"] == 1
    assert row["counts"]["view_unparsed_call_segments"] == 1
    assert row["counts"]["Student_unparsed_API_calls_not_in_structured_response"] == 1
    assert not detail["turns"][0]["parsed_tool_calls"]
    assert detail["turns"][0]["Student_text"]["rendered_response"] == ""
    assert not row["material_admission"]


def test_durable_event_order_failure_is_detected_without_replaying_tools(tmp_path):
    _, saved, _ = episode([("Submit.", [call("submit_program", {"program": "subtract(8, 2)"})])])
    turn = saved.turns[0]
    events = [
        dict(kind="model_call_returned", step=0, payload=turn.model_dump(mode="json")),
        dict(
            kind="model_call_intent",
            step=0,
            payload={"messages": turn.provider_metadata["public_request"]["messages"]},
        ),
        dict(kind="episode_completed", step=None, payload=saved.model_dump(mode="json")),
    ]
    for index, value in enumerate(events):
        path = tmp_path / "events" / f"{index:06d}"
        path.mkdir(parents=True)
        (path / "event.json").write_text(json.dumps(value))
    result = audit.inspect_case_events(tmp_path, saved)
    assert not result["chronological_order_exact"]
    assert result["issues"] == ["model_intent_return_order:0"]


def test_publication_uses_flat_immutable_sets_and_retains_rows_before_case_files(tmp_path):
    report = audit.bound(dict(schema="synthetic-only", processed_originals=2))
    rows = [dict(original_ordinal=i) for i in range(2)]
    cases = {"original_0000": dict(task_id="synthetic", original_ordinal=0)}
    source = b"# explicit test source, no experiment execution\n"
    result = audit.publish_results(tmp_path / "audit", report, rows, cases, source)
    root = tmp_path / "audit"
    assert len((root / "results/rows.jsonl").read_text().splitlines()) == 2
    assert (root / "results/audit_source.py").read_bytes() == source
    assert (root / "cases/original_0000/record.json").is_file()
    assert result["row_count"] == 2 and result["executed_audit_source_sha256"] == audit.sha(source)
    assert json.loads((root / "complete/record.json").read_text()) == result
