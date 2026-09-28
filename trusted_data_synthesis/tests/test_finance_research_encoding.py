"""Mocked API evidence + deterministic character tokenizer; no API/GPU/model."""

import asyncio
import copy
import json
from types import SimpleNamespace

import pytest

from trusted_synthesis.finance_research.contracts import (
    CallSettlement,
    Episode,
    RunConfig,
    TokenReceipt,
    ToolEvent,
    digest,
)
from trusted_synthesis.finance_research.encoding import (
    FeedbackTokenReceipt,
    StudentEncodingRecord,
    encode_probe_for_student,
    probe_generation_record,
)
from trusted_synthesis.finance_research.materials import (
    MaterialRegistration,
    QualificationDecision,
    build_material_pool,
)
from trusted_synthesis.finance_research.providers import (
    DeepSeekFlashProvider,
    canonical_assistant_message,
)
from trusted_synthesis.finance_research.training_policy import training_interface_policy


class CharacterTokenizer:
    special_tokens_map = {"eos_token": "<EOS>"}
    chat_template = "mock Student canonical template, not production"
    eos_token_id = 0

    def get_vocab(self):
        return {"mock": 1}

    def apply_chat_template(self, messages, **kwargs):
        for message in messages:
            for call in message.get("tool_calls", []):
                assert isinstance(call["function"]["arguments"], dict)
        return json.dumps(messages, ensure_ascii=False) + "\n<assistant>\n"

    def __call__(self, text, **kwargs):
        assert kwargs == {"add_special_tokens": False, "truncation": False, "padding": False}
        return {"input_ids": [ord(char) + 1 for char in text]}


def api_episode():
    raw_args = [
        '{ "source_id" : "missing" }',
        '{ "source_id" : "table_0" }',
        '{ "answer" : "3", "program" : "add(1, 2)" }',
    ]
    names = ["read_source", "read_source", "final_answer"]

    class Client:
        def __init__(self):
            self.index = 0

        async def post(self, url, **kwargs):
            index = self.index
            self.index += 1
            value = {
                "id": f"mock-api-{index}",
                "model": "deepseek-flash",
                "choices": [
                    {
                        "finish_reason": "tool_calls",
                        "message": {
                            "role": "assistant",
                            "content": "",
                            "tool_calls": [
                                {
                                    "id": f"call-{index}",
                                    "type": "function",
                                    "function": {
                                        "name": names[index],
                                        "arguments": raw_args[index],
                                    },
                                }
                            ],
                        },
                    }
                ],
                "usage": {"prompt_tokens": 10, "completion_tokens": 12},
            }
            return SimpleNamespace(raise_for_status=lambda: None, json=lambda: value)

    provider = DeepSeekFlashProvider(api_key="mock-not-real", client=Client())
    config = RunConfig(role="sft", max_new_tokens=64)
    messages = [
        {"role": "user", "content": "original public FinQA fixture question + complete table"}
    ]
    turns, events, settlements = [], [], []
    for index in range(3):
        turn = asyncio.run(provider.chat(copy.deepcopy(messages), [], config))
        turns.append(turn)
        call = turn.tool_calls[0]
        event = ToolEvent(
            call_id=call.call_id,
            name=call.name,
            raw_arguments=call.raw_arguments,
            normalized_arguments=call.arguments,
            executed_arguments=call.arguments,
            raw_output={"error": "missing"} if index == 0 else {"answer": "3"},
            visible_output="actual mock failure feedback" if index == 0 else "actual mock success",
            is_error=index == 0,
        )
        events.append(event)
        settlements.append(
            CallSettlement(
                attempt_index=index,
                state="returned",
                actual_model_calls=1,
                request_sha256=turn.provider_metadata["request_sha256"],
            )
        )
        messages += [
            canonical_assistant_message(turn),
            {"role": "tool", "tool_call_id": call.call_id, "content": event.visible_output},
        ]
    return Episode(
        task_id="finqa:mock",
        dataset="finqa",
        public_task_sha256="e" * 64,
        config=config,
        provider=provider.identity,
        turns=tuple(turns),
        tool_events=tuple(events),
        messages=tuple(messages),
        final_answer="3",
        final_program="add(1, 2)",
        stop_reason="final_answer",
        actual_model_calls=3,
        provider_attempts=3,
        call_settlements=tuple(settlements),
        all_provider_calls_settled=True,
        elapsed_seconds=0.01,
    )


def registration(ep, verdict="CompletePass"):
    return MaterialRegistration(
        source_manifest_sha256="a" * 64,
        validator_binding_id="mock-validator",
        qualification_registration_id="mock-independent-rule",
        state_support={ep.task_id: ("one-state",)},
        mu={ep.task_id: "1"},
        pi0={ep.task_id: {"one-state": "1"}},
        decisions=(
            QualificationDecision(
                episode_sha256=digest(ep),
                task_id=ep.task_id,
                verdict=verdict,
                state_id="one-state" if verdict == "CompletePass" else None,
                evidence_sha256="b" * 64,
                reason="explicit fixture qualification; not real proof",
            ),
        ),
    )


def test_API_probe_to_student_SFT_without_API_tokens_or_logP():
    ep = api_episode()
    probe = probe_generation_record(ep)
    encoded = encode_probe_for_student(probe, CharacterTokenizer())
    assert all(turn.receipt is None for turn in ep.turns)
    assert FeedbackTokenReceipt is TokenReceipt and not isinstance(encoded, TokenReceipt)
    assert not encoded.api_original_sampling_tokens_claimed and not encoded.context_truncated
    assert [row.supervised for row in encoded.rows] == [False, True, True]
    assert not encoded.rows[0].student_eos_appended and not encoded.rows[0].target_ids
    assert encoded.rows[1].target_ids[-1] == encoded.rows[2].target_ids[-1] == 0
    assert '{ "source_id" : "table_0" }' in encoded.rows[1].rendered_response
    assert "actual mock failure feedback" in encoded.rows[1].rendered_prompt
    assert "missing" in encoded.rows[1].rendered_prompt
    pool = build_material_pool([ep], registration(ep), student_encodings=[encoded])
    assert pool.admitted and pool.manifest.offline_student_encoding_used
    assert pool.packages[0]["encoding_origin"] == "offline_student_tokenizer"
    assert (
        len(pool.manifest.packages[0].rows) == 3
        and len(pool.row_arrays(pool.packages[0]["package_id"])) == 2
    )
    assert not pool.manifest.state_semantics_independently_proven


def test_API_probe_requires_real_request_and_explicit_settlement():
    ep = api_episode()
    with pytest.raises(ValueError, match="settled"):
        probe_generation_record(ep.model_copy(update={"all_provider_calls_settled": False}))
    badturn = ep.turns[0].model_copy(
        update={"provider_metadata": {**ep.turns[0].provider_metadata, "public_request": {}}}
    )
    with pytest.raises(ValueError, match="request/response"):
        probe_generation_record(ep.model_copy(update={"turns": (badturn,) + ep.turns[1:]}))
    with pytest.raises(ValueError, match="StudentEncodingRecord"):
        build_material_pool([ep], registration(ep))


def test_probe_cannot_drop_failure_history_or_repair_tool_argument_bytes():
    ep = api_episode()
    meta = copy.deepcopy(ep.turns[1].provider_metadata)
    meta["public_request"]["messages"] = meta["public_request"]["messages"][:1]
    meta["request_sha256"] = digest(meta["public_request"])
    altered = ep.model_copy(
        update={
            "turns": (
                ep.turns[0],
                ep.turns[1].model_copy(update={"provider_metadata": meta}),
                ep.turns[2],
            )
        }
    )
    with pytest.raises(ValueError, match="history"):
        probe_generation_record(altered)
    turn = ep.turns[0]
    badcall = turn.tool_calls[0].model_copy(update={"raw_arguments": '{"source_id":"missing"}'})
    altered = ep.model_copy(
        update={"turns": (turn.model_copy(update={"tool_calls": (badcall,)}),) + ep.turns[1:]}
    )
    with pytest.raises(ValueError, match="arguments"):
        probe_generation_record(altered)


def test_offline_encoding_rejects_overlength_and_false_API_token_claim():
    probe = probe_generation_record(api_episode())
    with pytest.raises(ValueError, match="untruncated"):
        encode_probe_for_student(probe, CharacterTokenizer(), context_limit=32)
    encoded = encode_probe_for_student(probe, CharacterTokenizer())
    body = encoded.model_dump(mode="json")
    body["api_original_sampling_tokens_claimed"] = True
    with pytest.raises(ValueError, match="policy"):
        StudentEncodingRecord.model_validate(body)
    assert all(turn.receipt is None for turn in probe.episode.turns)


def test_one_actual_API_response_cannot_fill_two_training_packages():
    ep = api_episode()
    duplicate = ep.model_copy(update={"config": ep.config.model_copy(update={"seed": 999})})
    reg = registration(ep)
    repeated = registration(duplicate)
    reg = reg.model_copy(update={"decisions": reg.decisions + repeated.decisions})
    encodings = [
        encode_probe_for_student(probe_generation_record(row), CharacterTokenizer())
        for row in (ep, duplicate)
    ]
    with pytest.raises(ValueError, match="multiple training packages"):
        build_material_pool([ep, duplicate], reg, student_encodings=encodings)


def test_native_correctness_unknown_never_mints_state_and_policy_does_not_authorize_training():
    ep = api_episode()
    pool = build_material_pool([ep], registration(ep, "unknown"))
    assert not pool.admitted and not pool.packages
    assert len(pool.manifest.inventory) == 1
    policy = training_interface_policy()
    assert policy["probe"]["api_model"] == "deepseek-flash"
    assert policy["utility"]["name"] == "J_FinQA_execution@H1"
    assert policy["probe"]["rollouts_per_task"] is None
    assert "not_authorized" in policy["status"]
    assert policy["sft"]["batch_size"] == 5 and not policy["sft"]["additional_batch_division"]
    assert (
        policy["training_comparison_proposal_not_run_registration"][
            "updates_if_material_and_resource_admitted"
        ]
        == 2000
    )
