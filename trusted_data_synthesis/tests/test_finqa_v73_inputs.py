"""CPU-only tests for sample integrity and exact historical request channels."""
import copy
import hashlib
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import finqa_v73_inputs as inputs
from trusted_synthesis.finance_research.v6_task import public_reasoning_tool_specs


@pytest.fixture(autouse=True)
def pure_test_tool_factory(monkeypatch):
    # Unit tests import workspace fixtures; production keeps the frozen-source
    # guard intact. Real frozen factory integration is checked separately.
    monkeypatch.setattr(inputs, "_tool_spec_factory", lambda: public_reasoning_tool_specs)


def row(key, state, cluster="a"):
    native = dict(status="scored", program_executable=True,
                  native=dict(execution_accuracy=int(state == "R")))
    if state == "I":
        native = dict(status="invalid_prediction", program_executable=False)
    return dict(task_key="draw20260928/finqa/" + key, original_task_key="finqa/" + key,
                source_group=dict(group="finqa:report:" + cluster, level="report"), native=native)


def panel(rows):
    return dict(status="COMPLETE", denominator=len(rows), results=rows)


def sample_fixture():
    parent = [row(str(i), "R", str(i % 3)) for i in range(7)]
    high = [row(str(i), "I" if i % 2 else "R", str(i % 3)) for i in range(7)]
    low = [row(str(i), "I" if i < 3 else "R", str(i % 3)) for i in range(7)]
    labels = [dict(task_key=r["task_key"], from_parent1192="R",
                   terminal_category="missing_terminal_submission", stop_reason="no_tool_call") for r in low[:3]]
    return [panel(parent), panel(high), panel(low), dict(low_lr_rows=labels)]


def test_selection_is_hash_stable_and_high_outcome_does_not_filter_K():
    args = sample_fixture()
    result = inputs.select_samples(*args, per_group=2, expected_counts=dict(F=3, K=4))
    reordered = copy.deepcopy(args)
    for p in reordered[:3]:
        p["results"].reverse()
    reordered[3]["low_lr_rows"].reverse()
    assert result == inputs.select_samples(*reordered, per_group=2, expected_counts=dict(F=3, K=4))
    assert {r["old_states"]["H"] for r in result["candidates"]["K"]} == {"I", "R"}
    assert result["source_distributions"]["F"]["selected"]
    assert result["unique_tasks"] == 4


def test_round_robin_uses_distinct_clusters_before_second_member():
    candidates = [dict(task_key=str(i), source_group=dict(group="a")) for i in range(8)]
    candidates += [dict(task_key="z", source_group=dict(group="b"))]
    selected, _ = inputs.round_robin_sample(candidates, salt="fixed", group="F", count=2)
    assert {r["source_group"]["group"] for r in selected} == {"a", "b"}


@pytest.mark.parametrize("mutation", ["missing_label", "different_cluster", "duplicate_task"])
def test_selection_rejects_inconsistent_old_evidence(mutation):
    args = sample_fixture()
    if mutation == "missing_label":
        args[3]["low_lr_rows"].pop()
    elif mutation == "different_cluster":
        args[1]["results"][0]["source_group"]["group"] = "other"
    else:
        args[0]["results"][0] = args[0]["results"][1]
    with pytest.raises(ValueError):
        inputs.select_samples(*args, per_group=2, expected_counts=dict(F=3, K=4))


class Tokenizer:
    def apply_chat_template(self, messages, *, tools, tokenize, add_generation_prompt):
        assert tokenize is False and add_generation_prompt is True
        return json.dumps(dict(messages=messages, tools=tools), sort_keys=True)

    def __call__(self, text, **kwargs):
        assert kwargs == dict(add_special_tokens=False, truncation=False, padding=False)
        return dict(input_ids=[ord(c) for c in text])

    def decode(self, ids, **kwargs):
        return "".join(chr(c) for c in ids)


def turn_fixture(model="P", *, text="old parent response"):
    tokenizer = Tokenizer()
    config = dict(max_new_tokens=2048, context_limit=24576, temperature=0.0)
    identity = dict(point_id=model, tokenizer_digest="tokenizer", chat_template_digest="template")
    registration = dict(model_identity=identity, job=dict(config=config))
    messages = [dict(role="system", content="fixed"), dict(role="user", content="question")]
    tools = inputs._original_tool_specs()
    rendered = tokenizer.apply_chat_template(messages, tools=tools, tokenize=False, add_generation_prompt=True)
    request = dict(messages=messages, tools=tools, config=config,
        rendered_prompt_sha256=hashlib.sha256(rendered.encode()).hexdigest(),
        tool_protocol="qwen2.5-native-tool-call-v1", template_tools_kwarg_used=True)
    receipt = dict(identity=identity, prompt_input_ids=[ord(c) for c in rendered],
        raw_generated_token_ids=[ord(c) for c in text] + [9999], actual_eos=True,
        sampling=dict(eos_token_ids=[9999]), finish_reason="stop",
        request_sha256=inputs.digest(request), raw_response_sha256=hashlib.sha256(text.encode()).hexdigest())
    turn = dict(receipt=receipt, provider_metadata=dict(request=request), raw_text=text,
                finish_reason="stop", tool_calls=[dict(name="submit_program", call_id="submit:1",
                arguments=dict(program="add(1, 2)"))])
    return registration, turn, tokenizer


def test_original_prompt_tokens_are_compared_and_target_not_appended():
    registration, turn, tokenizer = turn_fixture()
    request, prompt, receipt = inputs.verify_turn(turn, registration, tokenizer)
    assert prompt == turn["receipt"]["prompt_input_ids"]
    assert turn["raw_text"] not in json.dumps(request)
    assert receipt["raw_generated_token_ids"][-1] == 9999


@pytest.mark.parametrize("field", ["prompt_input_ids", "request_sha256", "raw_response_sha256", "identity"])
def test_receipt_mismatch_is_rejected(field):
    registration, turn, tokenizer = turn_fixture()
    if field == "prompt_input_ids":
        turn["receipt"][field][0] += 1
    elif field == "identity":
        turn["receipt"][field] = dict(point_id="other")
    else:
        turn["receipt"][field] = "wrong"
    with pytest.raises(ValueError):
        inputs.verify_turn(turn, registration, tokenizer)


def episode_fixture(model):
    registration, turn, tokenizer = turn_fixture(model)
    episode = dict(dataset="finqa", task_id="task", all_provider_calls_settled=True,
        turns=[turn], final_program="add(1, 2)", tool_events=[dict(name="submit_program",
        call_id="submit:1", is_error=False, raw_output=dict(submitted=True, program="add(1, 2)"))])
    return registration, episode, tokenizer


def test_parent_context_uses_successful_submit_event_not_text():
    _, episode, _ = episode_fixture("P")
    episode["turns"].append(dict(raw_text="submit_program in prose", tool_calls=[]))
    assert inputs.parent_submit_index(episode) == 0
    episode["tool_events"][0]["is_error"] = True
    with pytest.raises(ValueError):
        inputs.parent_submit_index(episode)


def write_record(path, body):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(inputs._bound(body)))


def test_materialization_deduplicates_exact_inputs_and_keeps_missing_slot(tmp_path):
    registrations, roots = {}, {}
    for model in inputs.MODEL_ORDER:
        registration, episode, tokenizer = episode_fixture(model)
        registrations[model] = registration
        root = tmp_path / model
        roots[model] = str(root)
        path = root / "episodes/e0/episode.json"
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps(episode))
        run = inputs._bound(dict(tasks=["finqa/task"], episode_keys=["e0"],
            provider=registration["model_identity"], config=registration["job"]["config"]))
        (root / "run.json").write_text(json.dumps(run))
        write_record(root / "generation_seal/seal.json", dict(complete=True,
            all_provider_calls_settled=True, run_id=run["id"], registered_denominator=1,
            episodes=[dict(key="e0", path="episodes/e0/episode.json",
                           sha256=hashlib.sha256(path.read_bytes()).hexdigest())]))
    selection = inputs._bound(dict(unique_tasks=1, selected=[dict(task_key="draw20260928/finqa/task",
        original_task_key="finqa/task", group="F", source_group=dict(group="cluster", level="report"))]))
    # Preserve the selected task and L slot as UNKNOWN instead of sampling anew.
    (tmp_path / "L/episodes/e0/episode.json").unlink()
    result = inputs.materialize_contexts(selection, registrations, tokenizer, generation_roots=roots)
    assert len(result["contexts"]) == 1
    assert result["dedup"]["known_context_slots"] == 2
    assert result["dedup"]["logical_generation_slots"] == 9
    assert result["logical_rows"][0]["contexts"]["L"] is None
    assert result["unknown_contexts"][0]["source_model"] == "L"
    assert len(result["targets"]) == 1
    context = next(iter(result["contexts"].values()))
    assert "raw_generated_token_ids" not in json.dumps(context)
    assert set(result["logical_rows"][0]["source_responses"]) == {"P", "H"}
    assert result["dedup"]["planned_unique_generation_calls"] == 3


class OrderSensitiveTokenizer(Tokenizer):
    def apply_chat_template(self, messages, *, tools, tokenize, add_generation_prompt):
        assert tokenize is False and add_generation_prompt is True
        # Match the order-sensitive tools|tojson behavior rather than hiding it.
        return json.dumps(messages, sort_keys=True) + json.dumps(tools, sort_keys=False)


def test_sorted_saved_tools_restore_only_original_order_and_exact_prompt_tokens():
    registration, turn, _ = turn_fixture()
    tokenizer = OrderSensitiveTokenizer()
    request = turn["provider_metadata"]["request"]
    rendered = tokenizer.apply_chat_template(request["messages"], tools=request["tools"],
        tokenize=False, add_generation_prompt=True)
    request["rendered_prompt_sha256"] = hashlib.sha256(rendered.encode()).hexdigest()
    turn["receipt"]["request_sha256"] = inputs.digest(request)
    turn["receipt"]["prompt_input_ids"] = [ord(char) for char in rendered]
    saved = json.loads(json.dumps(turn, sort_keys=True))
    saved_tools = saved["provider_metadata"]["request"]["tools"]
    assert list(saved_tools[0]) == ["function", "type"]
    assert tokenizer.apply_chat_template(request["messages"], tools=saved_tools,
        tokenize=False, add_generation_prompt=True) != rendered
    restored, actual_ids, _ = inputs.verify_turn(saved, registration, tokenizer)
    assert actual_ids == turn["receipt"]["prompt_input_ids"]
    assert list(restored["tools"][0]) == ["type", "function"]
    assert list(saved_tools[0]) == ["function", "type"]


@pytest.mark.parametrize("mutation", ["description", "parameter", "json_type"])
def test_original_factory_cannot_overwrite_changed_saved_tool_values(mutation):
    _, turn, _ = turn_fixture()
    request = turn["provider_metadata"]["request"]
    function = request["tools"][0]["function"]
    if mutation == "description":
        function["description"] += " new instruction"
    elif mutation == "parameter":
        function["parameters"]["properties"]["new"] = {"type": "string"}
    else:
        # Python considers 0 == False, but their canonical JSON values differ.
        function["parameters"]["additionalProperties"] = 0
    with pytest.raises(ValueError, match="tool values differ"):
        inputs.restore_request_tool_order(request)
