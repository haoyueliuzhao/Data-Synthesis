"""V10 authentic replay/unsent recovery: real V7 CPU tools, mocked HTTP only."""

import asyncio
import copy
import json
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from test_finance_research_datasets import finqa_record
from test_finance_research_probe_provider import value
from test_finance_unknown_abandonment import table
from test_finance_v7_probe_provider import v7_config
from test_finance_v10_budget import (  # noqa: F401
    BATCH_ID,
    SLOTS,
    register,
    stopped_history,
    synthetic_parent,
    wallet,
)

from trusted_synthesis.finance_research import v10_generation as gen
from trusted_synthesis.finance_research.contracts import Episode, digest, invocation_identity
from trusted_synthesis.finance_research.datasets import adapt_finqa
from trusted_synthesis.finance_research.harness import (
    episode_tool_specs,
    public_initial_messages,
    run_episode,
)
from trusted_synthesis.finance_research.providers import _json
from trusted_synthesis.finance_research.settlement import episode_is_complete
from trusted_synthesis.finance_research.storage import EventSink, read_json
from trusted_synthesis.finance_research.v10_budget import (
    NETWORK_REASON,
    acknowledge_connection_unknowns,
    generation_episode_id,
)

KEY = "synthetic-memory-key-not-a-credential"


class ChainClient:
    def __init__(self, *, failure=None, responses=None):
        self.calls, self.failure = [], failure
        self.responses = responses or [
            response(
                "run_program",
                "R: Compute the original public revenue difference; keep this text.",
                0,
            ),
            response(
                "submit_program", "U: The actual execution returned 6; submit that program.", 1
            ),
        ]

    async def post(self, url, **kwargs):
        self.calls.append((url, kwargs))
        if self.failure is not None:
            raise self.failure
        assert len(self.calls) <= len(self.responses), "unexpected extra model send"
        return SimpleNamespace(
            status_code=200, content=json.dumps(self.responses[len(self.calls) - 1]).encode()
        )


def response(tool, content, index):
    result = value(id=f"original-response-{index}")
    result["choices"][0]["message"].update(
        content=content,
        tool_calls=[
            dict(
                id=f"original-call-{index}",
                type="function",
                function=dict(name=tool, arguments='{ "program" : "subtract(8, 2)" }'),
            )
        ],
    )
    return result


@pytest.fixture
def context(wallet, tmp_path, monkeypatch):  # noqa: F811
    register(wallet)
    bundle = adapt_finqa([finqa_record()], split="train", revision="V10-CPU-mock")[0]
    task = bundle.public.model_copy(update={"task_id": SLOTS[0]["task_id"]})
    cfg = v7_config()
    plan = dict(
        id="synthetic-protocol-v10",
        batch_id=BATCH_ID,
        slots=SLOTS,
        slot_denominator=8000,
        task_denominator=1000,
        original={"synthetic": True},
        configs_by_task={task.task_id: cfg.model_dump(mode="json")},
        launch_order=[SLOTS[0]["slot_id"]],
        concurrency=1,
        budget_database=str(wallet.path),
        budget_config=wallet.config,
        budget_config_sha256=digest(wallet.config),
    )
    monkeypatch.setattr(gen, "public_tasks", lambda original: {task.task_id: task})
    return SimpleNamespace(
        ledger=wallet,
        task=task,
        config=cfg,
        plan=plan,
        slot=SLOTS[0],
        output=tmp_path / "new-generation",
    )


def episode(context, client, *, sink=None, stopped=None, operator_stop=None):
    api = gen.RecoverableProbe(
        context.ledger,
        KEY,
        context.slot["slot_id"],
        client,
        stopped=stopped,
        operator_stop=operator_stop,
    )
    saved = asyncio.run(
        run_episode(
            context.task,
            api,
            context.config,
            sink=sink,
            invocation_context=dict(
                run_id=context.ledger.run_id, episode_id=context.slot["slot_id"], attempt_index=1
            ),
        )
    )
    return saved, api


def first_request(context):
    coords = invocation_identity(
        dict(run_id=context.ledger.run_id, episode_id=context.slot["slot_id"], attempt_index=1),
        turn_index=0,
    )
    body = gen._body(
        public_initial_messages(context.task, context.config),
        episode_tool_specs(context.config),
        context.config,
    )
    return dict(
        invocation_id=coords["invocation_id"],
        coordinates=coords,
        request=body,
        request_body=_json(body).encode(),
    )


def test_real_v7_tools_submit_preserve_original_public_text_and_wire(context):
    client = ChainClient()
    saved, api = episode(context, client)
    assert episode_is_complete(saved) and saved.stop_reason == "final_answer"
    assert saved.final_program == "subtract(8, 2)" and saved.final_answer is None
    assert saved.tool_events[0].raw_output["result"] == 6
    assert saved.tool_events[1].raw_output == {"program": "subtract(8, 2)", "submitted": True}
    assert saved.actual_model_calls == api.actual_model_calls == api.new_HTTP_calls == 2
    assert len(client.calls) == 2
    for index, turn in enumerate(saved.turns):
        assert turn.raw_text == client.responses[index]["choices"][0]["message"]["content"]
        assert turn.provider_metadata["api_response_raw"] == json.dumps(client.responses[index])
        assert turn.tool_calls[0].raw_arguments == '{ "program" : "subtract(8, 2)" }'
        wire = json.loads(client.calls[index][1]["content"])
        assert wire == turn.provider_metadata["public_request"]
        assert wire["model"] == "deepseek-flash" and wire["thinking"] == {"type": "disabled"}
        assert KEY not in json.dumps(turn.model_dump(mode="json"))
    integrity = gen.integrity_record(context.task, saved, context.slot)
    assert all(integrity["checks"].values())
    assert integrity["semantic_quality_not_assessed"]


def test_whole_settled_prefix_replay_has_zero_new_http_and_no_resettlement(context):
    original, _ = episode(context, ChainClient())
    before = {
        name: table(context.ledger.path, name)
        for name in ("requests", "counters", "events", "v10_quotas")
    }
    client = ChainClient(failure=AssertionError("replay must not make HTTP call"))
    replayed, api = episode(context, client)
    assert episode_is_complete(replayed) and not client.calls
    assert api.actual_model_calls == replayed.actual_model_calls == original.actual_model_calls == 2
    assert api.new_HTTP_calls == 0 and len(api.replayed_ids) == 2
    assert [t.raw_text for t in replayed.turns] == [t.raw_text for t in original.turns]
    assert [e.raw_output for e in replayed.tool_events] == [
        e.raw_output for e in original.tool_events
    ]
    assert all(t.provider_metadata["restored_original_paid_response"] for t in replayed.turns)
    assert all(table(context.ledger.path, name) == rows for name, rows in before.items())


def test_changed_settled_request_body_is_not_a_new_sample(context):
    episode(context, ChainClient())
    api = gen.RecoverableProbe(context.ledger, KEY, context.slot["slot_id"], ChainClient())
    messages = copy.deepcopy(public_initial_messages(context.task, context.config))
    messages[-1]["content"] += " unregistered change"
    with pytest.raises(ValueError, match="settled prefix"):
        asyncio.run(api.chat(messages, episode_tool_specs(context.config), context.config))
    assert api.new_HTTP_calls == 0 and not api.client.calls


def test_reserved_continues_original_hold_once_then_original_two_turn_episode(context):
    request = first_request(context)
    context.ledger.reserve(**request)
    before = context.ledger.snapshot()
    saved, api = episode(context, ChainClient())
    after = context.ledger.snapshot()
    assert episode_is_complete(saved) and api.new_HTTP_calls == 2
    assert after["requests_reserved"] == before["requests_reserved"] + 1
    assert after["requests_dispatched"] == before["requests_dispatched"] + 2
    assert context.ledger.request_record(request["invocation_id"])["state"] == "SETTLED"


@pytest.mark.parametrize("state", ["DISPATCHED", "UNKNOWN"])
def test_dispatched_or_unknown_is_never_resent(context, state):
    request = first_request(context)
    context.ledger.reserve(**request)
    context.ledger.mark_dispatched(request["invocation_id"])
    if state == "UNKNOWN":
        context.ledger.unknown(request["invocation_id"], reason="original unresolved evidence")
    before = table(context.ledger.path, "requests")
    client = ChainClient()
    saved, api = episode(context, client)
    assert not episode_is_complete(saved) and saved.stop_reason == "provider_error"
    assert api.new_HTTP_calls == 0 and not client.calls
    assert table(context.ledger.path, "requests") == before


@pytest.mark.parametrize("reason", ["budget_halt", "user_stop"])
def test_pre_call_budget_and_user_stop_are_not_native_zero(context, reason):
    stop = asyncio.Event()
    if reason == "budget_halt":
        context.ledger.halt(reason="explicit budget stop", invocation_id="stop")
    else:
        stop.set()
    before = context.ledger.snapshot()
    saved, api = episode(context, ChainClient(), operator_stop=stop)
    assert saved.actual_model_calls == api.new_HTTP_calls == 0
    assert saved.call_settlements[0].state == "pre_call_rejected"
    assert not episode_is_complete(saved) and saved.stop_reason == "provider_error"
    assert "Q_native" not in saved.model_dump(mode="json")
    assert context.ledger.snapshot() == before


def test_prefix_cannot_seal_or_reach_private_scoring(context, monkeypatch):
    monkeypatch.setattr(
        gen, "validate_paid_generation", lambda *a: pytest.fail("prefix passed seal barrier")
    )
    monkeypatch.setattr(
        gen, "load_public_snapshot", lambda *a: pytest.fail("prefix reached private scoring")
    )
    with pytest.raises(ValueError, match="all 8000"):
        gen.seal_generation(context.output, context.plan, context.ledger, {})
    with pytest.raises(ValueError, match="full generation seal"):
        gen.score_native_support(
            context.output, context.plan, {"protocol_id": context.plan["id"], "slots": []}
        )
    assert not (context.output / "generation_seal").exists()
    assert not (context.output / "native_support").exists()


@pytest.mark.parametrize("origin", ["canonical_episode", "durable_terminal_event"])
def test_completed_artifact_without_outcome_recovers_without_http(context, origin):
    directory = gen.slot_directory(context.output, context.slot)
    attempt = directory / "attempts/attempt0001"
    sink = EventSink(attempt / "events") if origin == "durable_terminal_event" else None
    saved, _ = episode(context, ChainClient(), sink=sink)
    if origin == "canonical_episode":
        gen.publish(directory / "episode", saved.model_dump(mode="json"), "episode.json")
    before = table(context.ledger.path, "requests")
    gen.recover_local_completed(context.output, context.plan)
    outcome = gen.completed_slots(context.output, context.plan)[context.slot["slot_id"]]
    assert outcome["recovery_from_original_terminal"]
    assert outcome["new_model_calls_during_recovery"] == 0
    assert Episode.model_validate_json(Path(outcome["episode_path"]).read_bytes()) == saved
    gen.recover_local_completed(context.output, context.plan)
    assert table(context.ledger.path, "requests") == before
    assert gen.validate_paid_generation(
        context.output, context.plan, context.ledger, {context.slot["slot_id"]: outcome}
    )


def test_collect_publishes_real_episode_and_reentry_does_not_send(context):
    client = ChainClient()
    result = asyncio.run(
        gen.collect(context.output, context.plan, context.ledger, KEY, client=client)
    )
    assert not result["blocked"] and len(result["completed"]) == 1
    assert len(client.calls) == 2
    outcome = result["completed"][context.slot["slot_id"]]
    attempt = read_json(Path(outcome["completed_attempt"]) / "result/record.json")
    assert attempt["actual_new_HTTP_calls"] == attempt["original_paid_invocations_represented"] == 2
    assert not attempt["replayed_settled_invocation_ids"]
    assert not (context.output / "generation_seal").exists()
    no_send = ChainClient(failure=AssertionError("completed slot resent"))
    again = asyncio.run(
        gen.collect(context.output, context.plan, context.ledger, KEY, client=no_send)
    )
    assert again["completed"] == result["completed"] and not no_send.calls


def test_mock_connection_failure_binds_original_intent_and_retains_unknown_terminal(context):
    client = ChainClient(failure=httpx.ReadError("synthetic network disconnection"))
    result = asyncio.run(
        gen.collect(context.output, context.plan, context.ledger, KEY, client=client)
    )
    assert result["blocked"] and not result["completed"] and len(client.calls) == 1
    assert context.ledger.snapshot()["halt"]["reason"] == NETWORK_REASON
    expected = gen.expected_generation_unknowns(context.output, context.plan, context.ledger)
    assert len(expected) == 1
    row = context.ledger.request_record(next(iter(expected)))
    assert json.loads(row["evidence_json"])["budget_coordinates"] == json.loads(
        row["coordinates_json"]
    )
    with pytest.raises(ValueError, match="unacknowledged"):
        gen.materialize_generation_unknowns(context.output, context.plan, context.ledger)
    receipt = acknowledge_connection_unknowns(
        context.ledger, batch_id=BATCH_ID, expected_requests=expected
    )
    assert receipt["records"][0]["model_response"] is None
    gen.materialize_generation_unknowns(context.output, context.plan, context.ledger)
    outcome = gen.completed_slots(context.output, context.plan)[context.slot["slot_id"]]
    assert outcome["status"] == "NETWORK_UNKNOWN_TERMINAL"
    assert outcome["Q_native"] is None and not outcome["native_zero_claimed"]
    assert outcome["episode_path"] is None and Path(outcome["partial_episode_path"]).is_file()
    assert context.ledger.request_record(row["invocation_id"]) == row
    before = context.ledger.snapshot()
    no_send = ChainClient(failure=AssertionError("UNKNOWN sampled again"))
    asyncio.run(gen.collect(context.output, context.plan, context.ledger, KEY, client=no_send))
    assert not no_send.calls and context.ledger.snapshot() == before


def test_build_plan_preserves_original_per_task_configs_and_fixed_new_ids(context, monkeypatch):
    original = dict(
        id="synthetic-parent",
        slots=[{**s, "slot_id": f"old-slot:{i}"} for i, s in enumerate(SLOTS)],
        task_ids=list(dict.fromkeys(s["task_id"] for s in SLOTS)),
        configs_by_task={
            t: v7_config(max_new_tokens=2048 if i % 2 else 16384).model_dump(mode="json")
            for i, t in enumerate(dict.fromkeys(s["task_id"] for s in SLOTS))
        },
        original_snapshot="synthetic-snapshot",
        snapshot_id="synthetic-snapshot-id",
    )
    validated = []
    monkeypatch.setattr(gen, "read_json", lambda path: original)
    monkeypatch.setattr(
        gen,
        "validate_material_registration",
        lambda value: validated.append(value) or {"fixture_validated": True},
    )
    monkeypatch.setattr(gen, "source_binding", lambda: {"synthetic": "0" * 64})
    monkeypatch.setattr(gen, "sha", lambda path: "0" * 64)
    monkeypatch.setattr(gen.subprocess, "check_output", lambda *a, **kw: "synthetic-source\n")
    plan = gen.build_plan(wallet=context.ledger.path)
    assert validated == [original]
    assert len(plan["slots"]) == 8000 and len(plan["launch_order"]) == 8000
    assert plan["configs_by_task"] == original["configs_by_task"]
    assert plan["task_ids"] == original["task_ids"]
    assert all(
        s["slot_id"] == generation_episode_id(BATCH_ID, s["task_id"], s["slot_index"])
        for s in plan["slots"]
    )
    assert not {s["slot_id"] for s in plan["slots"]} & {s["slot_id"] for s in original["slots"]}
    assert plan["launch_order"][:1000] == [
        s["slot_id"] for s in plan["slots"] if s["slot_index"] == 0
    ]
    assert plan["api_model"] == "deepseek-flash" and plan["concurrency"] == 8
    assert plan["require_some_reason_supervision_for_reasoning_mainline"] is True
