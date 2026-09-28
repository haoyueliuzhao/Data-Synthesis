"""Mocked HTTP only: exact thinking/body evidence, tariff bounds and unknown stops."""

import asyncio
import json
from types import SimpleNamespace

import pytest
from test_finance_research_probe_budget import budget, usage

from trusted_synthesis.finance_research.contracts import (
    ProviderCallError,
    PublicSource,
    PublicTask,
    RunConfig,
    digest,
)
from trusted_synthesis.finance_research.probe_budget import BudgetUnavailable
from trusted_synthesis.finance_research.probe_provider import BudgetedDeepSeekFlashProvider


def config(**changes):
    return RunConfig(
        role="sft",
        harness_id="bigfinance-derived-vtdo-v3",
        submission_profile="finqa_program_v2",
        context_limit=1048576,
        **changes,
    )


def value(**changes):
    return {
        "id": "actual-response-1",
        "model": "deepseek-flash",
        "choices": [
            {
                "finish_reason": "tool_calls",
                "message": {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [
                        {
                            "id": "call-real-1",
                            "type": "function",
                            "function": {
                                "name": "read_source",
                                "arguments": '{ "source_id" : "table:0" }',
                            },
                        }
                    ],
                },
            }
        ],
        "usage": usage(),
        **changes,
    }


class Client:
    def __init__(self, response=None, *, status=200, failure=None):
        self.response = value() if response is None else response
        self.status, self.failure, self.calls = status, failure, []

    async def post(self, url, **kwargs):
        self.calls.append((url, kwargs))
        if self.failure:
            raise self.failure
        return SimpleNamespace(status_code=self.status, content=json.dumps(self.response).encode())


def provider(ledger, client, episode="slot-0"):
    return BudgetedDeepSeekFlashProvider(
        ledger=ledger, api_key="fixture-memory-secret-123456789", episode_id=episode, client=client
    )


def test_actual_wire_request_matches_public_evidence_and_cache_accounting(tmp_path):
    ledger = budget(tmp_path)
    client = Client()
    api = provider(ledger, client)
    turn = asyncio.run(
        api.chat([{"role": "user", "content": "original public source"}], [], config())
    )
    sent = client.calls[0][1]["content"]
    body = json.loads(sent)
    assert body == turn.provider_metadata["public_request"]
    assert body["thinking"] == {"type": "disabled"}
    assert body["model"] == "deepseek-flash" and body["max_tokens"] == 2048
    assert "seed" not in body and "reasoning_effort" not in body
    assert digest(body) == turn.provider_metadata["request_sha256"]
    assert (
        turn.receipt is None and turn.tool_calls[0].raw_arguments == '{ "source_id" : "table:0" }'
    )
    record = ledger.request_record(turn.provider_metadata["budget_invocation_id"])
    assert record["request_body"] == sent and record["state"] == "SETTLED"
    assert record["response_body"] == json.dumps(client.response).encode()
    assert ledger.snapshot()["settled_tariff_microcny"] == 280
    assert b"fixture-memory-secret" not in record["request_body"] + record["response_body"]


def test_timeout_holds_budget_stops_new_work_and_never_retries(tmp_path):
    ledger = budget(tmp_path)
    client = Client(failure=TimeoutError("fixture timeout"))
    api = provider(ledger, client)
    with pytest.raises(ProviderCallError) as captured:
        asyncio.run(api.chat([], [], config()))
    assert captured.value.settlement == "unknown"
    assert len(client.calls) == api.actual_model_calls == 1
    assert ledger.snapshot()["held_microcny"] == 2_113_536
    next_api = provider(ledger, Client(), "slot-1")
    with pytest.raises(BudgetUnavailable):
        asyncio.run(next_api.chat([], [], config()))
    assert next_api.actual_model_calls == 0


def test_cancellation_after_request_start_also_keeps_unknown_reservation(tmp_path):
    ledger = budget(tmp_path)
    client = Client(failure=asyncio.CancelledError())
    api = provider(ledger, client)
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(api.chat([], [], config()))
    state = ledger.snapshot()
    assert state["unknown_requests"] == 1 and state["held_microcny"] == 2_113_536
    assert state["halt"] and api.actual_model_calls == 1


def test_non_2xx_without_usage_is_known_service_failure_but_unknown_cost(tmp_path):
    ledger = budget(tmp_path)
    api = provider(ledger, Client({"error": "rate limited"}, status=429))
    with pytest.raises(ProviderCallError) as captured:
        asyncio.run(api.chat([], [], config()))
    assert captured.value.settlement == "unknown"
    state = ledger.snapshot()
    assert state["held_microcny"] == 2_113_536 and state["unknown_requests"] == 1
    row = ledger.request_record(ledger.unsettled()[0]["invocation_id"])
    assert row["http_status"] == 429 and row["response_classification"] == "service_failure"


def test_non_2xx_with_real_usage_is_charged_and_halted_not_refunded(tmp_path):
    ledger = budget(tmp_path)
    api = provider(ledger, Client({"error": "server error", "usage": usage()}, status=503))
    with pytest.raises(ProviderCallError) as captured:
        asyncio.run(api.chat([], [], config()))
    assert captured.value.settlement == "service_failure"
    state = ledger.snapshot()
    assert state["settled_tariff_microcny"] == 280 and state["held_microcny"] == 0
    assert state["halt"] and state["unknown_requests"] == 0


@pytest.mark.parametrize("finish", ["aborted", "insufficient_system_resource"])
def test_explicit_infrastructure_finish_preserves_charge_and_stops(tmp_path, finish):
    returned = value()
    returned["choices"][0]["finish_reason"] = finish
    ledger = budget(tmp_path)
    api = provider(ledger, Client(returned))
    with pytest.raises(ProviderCallError) as captured:
        asyncio.run(api.chat([], [], config()))
    assert captured.value.settlement == "unknown" and captured.value.evidence["billing_usage_known"]
    assert ledger.snapshot()["settled_tariff_microcny"] == 280 and ledger.snapshot()["halt"]


def test_disabled_thinking_violation_preserves_usage_then_stops(tmp_path):
    returned = value()
    returned["choices"][0]["message"]["reasoning_content"] = "unexpected reasoning"
    returned["usage"]["completion_tokens_details"] = {"reasoning_tokens": 2}
    ledger = budget(tmp_path)
    api = provider(ledger, Client(returned))
    with pytest.raises(ProviderCallError):
        asyncio.run(api.chat([], [], config()))
    assert ledger.snapshot()["settled_tariff_microcny"] == 280 and ledger.snapshot()["halt"]


def test_content_filter_and_bad_tool_arguments_are_settled_model_terminals(tmp_path):
    ledger = budget(tmp_path)
    returned = value()
    returned["choices"][0]["finish_reason"] = "content_filter"
    returned["choices"][0]["message"] = {"role": "assistant", "content": ""}
    filtered = asyncio.run(provider(ledger, Client(returned)).chat([], [], config()))
    assert filtered.finish_reason == "content_filter" and filtered.tool_calls == ()
    bad = value()
    bad["choices"][0]["message"]["tool_calls"][0]["function"]["arguments"] = "{broken"
    turn = asyncio.run(provider(ledger, Client(bad), "slot-1").chat([], [], config()))
    assert turn.tool_calls == () and turn.provider_metadata["model_tool_format_failure"]
    assert not ledger.snapshot()["halt"] and ledger.snapshot()["requests_dispatched"] == 2


def test_model_and_output_contract_cannot_fallback(tmp_path):
    ledger = budget(tmp_path)
    with pytest.raises(ValueError, match="deepseek-flash"):
        BudgetedDeepSeekFlashProvider(
            ledger=ledger, api_key="fixture", episode_id="slot-0", model="deepseek-v4-pro"
        )
    api = provider(ledger, Client())
    with pytest.raises(ValueError):
        asyncio.run(api.chat([], [], config(max_new_tokens=4096)))
    assert api.actual_model_calls == ledger.snapshot()["requests_reserved"] == 0


def test_three_turn_probe_encoder_binding_uses_exact_sent_thinking_and_invocation(tmp_path):
    from trusted_synthesis.finance_research.encoding import probe_generation_record
    from trusted_synthesis.finance_research.harness import run_episode

    responses = [
        ("read_source", {"source_id": "table:0"}),
        (
            "calculate",
            {
                "expression": "a-b",
                "variables": {"a": "prev:r1.output.content.1.1", "b": "prev:r1.output.content.1.2"},
            },
        ),
        (
            "final_answer",
            {"answer": "prev:r2.output.result", "scale": "", "program": "subtract(120, 90)"},
        ),
    ]

    class ChainClient(Client):
        async def post(self, url, **kwargs):
            index = len(self.calls)
            name, arguments = responses[index]
            self.response = value(id=f"response-{index}")
            self.response["choices"][0]["message"]["tool_calls"] = [
                {
                    "id": f"tool-{index}",
                    "type": "function",
                    "function": {"name": name, "arguments": json.dumps(arguments)},
                }
            ]
            return await super().post(url, **kwargs)

    ledger = budget(tmp_path)
    client = ChainClient()
    api = provider(ledger, client)
    task = PublicTask(
        dataset="finqa",
        task_id="probe-fixture",
        question="Revenue increase?",
        sources=(
            PublicSource(
                source_id="table:0",
                kind="table",
                locator="fixture",
                content=[["metric", "current", "prior"], ["Revenue", "120", "90"]],
            ),
        ),
        version="fixture",
    )
    episode = asyncio.run(
        run_episode(
            task,
            api,
            config(),
            invocation_context={
                "run_id": ledger.run_id,
                "episode_id": "slot-0",
                "attempt_index": 1,
            },
        )
    )
    assert episode.stop_reason == "final_answer" and episode.final_answer == "30"
    probe = probe_generation_record(episode)
    assert len(probe.public_requests) == 3
    for index, turn in enumerate(episode.turns):
        assert turn.provider_metadata["public_request"] == json.loads(
            client.calls[index][1]["content"]
        )
        assert (
            turn.provider_metadata["budget_invocation_id"]
            == turn.provider_metadata["harness_invocation"]["invocation_id"]
        )
    assert ledger.snapshot()["requests_dispatched"] == 3
