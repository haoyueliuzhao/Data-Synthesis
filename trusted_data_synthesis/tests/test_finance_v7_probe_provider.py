"""V7 generation caps on the existing joint budget; only mocked HTTP/temp SQLite."""

import asyncio
import copy
import json

import pytest
from test_finance_research_datasets import finqa_record
from test_finance_research_probe_budget import budget, usage
from test_finance_research_probe_provider import Client, config, provider, value
from test_finance_v6_budget_amendment import amendment, paused_budget, reopen

from trusted_synthesis.finance_research.contracts import ProviderCallError
from trusted_synthesis.finance_research.datasets import adapt_finqa
from trusted_synthesis.finance_research.harness import (
    episode_tool_specs,
    run_episode,
    system_message,
)
from trusted_synthesis.finance_research.probe_budget import BudgetUnavailable
from trusted_synthesis.finance_research.probe_provider import ENDPOINT


def v7_config(**changes):
    return config(
        **dict(
            harness_id="bigfinance-derived-vtdo-v7", submission_profile="finqa-public-reasoning-v2"
        )
        | changes
    )


def joint_budget(tmp_path):
    old, _ = paused_budget(tmp_path / "existing-joint.sqlite3")
    amendment(old)
    return reopen(old.path)


def call(api, cfg, *, messages=None):
    return asyncio.run(
        api.chat(
            [system_message(cfg), {"role": "user", "content": "original public input"}]
            if messages is None
            else messages,
            episode_tool_specs(cfg),
            cfg,
        )
    )


@pytest.mark.parametrize("cap,actual", [(2048, 20), (16384, 10000)])
def test_v7_uses_only_its_registered_actual_cap_and_keeps_historical_spend(tmp_path, cap, actual):
    ledger = joint_budget(tmp_path)
    before = ledger.snapshot()
    returned = value(usage=usage(output=actual))
    returned["choices"][0]["message"]["content"] = "R: public task-specific reasoning."
    client = Client(returned)
    turn = call(provider(ledger, client, "v7-slot:new-original"), v7_config(max_new_tokens=cap))
    body = json.loads(client.calls[0][1]["content"])
    assert client.calls[0][0] == ENDPOINT
    assert body == turn.provider_metadata["public_request"]
    assert body["model"] == "deepseek-flash" and body["thinking"] == {"type": "disabled"}
    assert body["temperature"] == body["top_p"] == 1 and body["max_tokens"] == cap
    assert (
        "parallel_tool_calls" not in body and "seed" not in body and "reasoning_effort" not in body
    )
    assert turn.raw_text == returned["choices"][0]["message"]["content"]
    assert turn.provider_metadata["api_response"] == returned and turn.receipt is None
    expected_hold = ledger.price_sheet.cost_microcny(hit=0, miss=1048576, output=cap)
    expected_cost = ledger.price_sheet.cost_microcny(hit=41, miss=59, output=actual)
    assert turn.provider_metadata["budget_reserved_microcny"] == expected_hold
    assert (
        ledger.snapshot()["settled_tariff_microcny"]
        == before["settled_tariff_microcny"] + expected_cost
    )
    assert ledger.snapshot()["requests_reserved"] == before["requests_reserved"] + 1
    saved = ledger.request_record(turn.provider_metadata["budget_invocation_id"])
    assert json.loads(saved["coordinates_json"])["episode_id"] == "v7-slot:new-original"
    assert saved["state"] == "SETTLED" and json.loads(saved["request_body"])["max_tokens"] == cap


@pytest.mark.parametrize("cap", [4096, 32768, 65536, 131072])
def test_v7_cannot_use_other_caps_even_when_joint_review_ledger_has_larger_capacity(tmp_path, cap):
    ledger, client = joint_budget(tmp_path), Client()
    before = ledger.snapshot()
    with pytest.raises(ValueError, match="contract"):
        call(provider(ledger, client, "v7-slot:rejected"), v7_config(max_new_tokens=cap))
    assert not client.calls and ledger.snapshot() == before


@pytest.mark.parametrize(
    "harness,profile,cap",
    [
        ("bigfinance-derived-vtdo-v6", "finqa-public-reasoning-v1", 16384),
        ("bigfinance-derived-vtdo-v6", "finqa-public-reasoning-v2", 16384),
        ("bigfinance-derived-vtdo-v7", "finqa-public-reasoning-v1", 2048),
        ("bigfinance-derived-vtdo-v3", "finqa_program_v2", 16384),
    ],
)
def test_new_allowance_never_leaks_to_v6_legacy_or_mixed_profiles(tmp_path, harness, profile, cap):
    ledger, client = joint_budget(tmp_path), Client()
    cfg = config(harness_id=harness, submission_profile=profile, max_new_tokens=cap)
    before = ledger.snapshot()
    with pytest.raises(ValueError):
        call(provider(ledger, client), cfg)
    assert not client.calls and ledger.snapshot() == before


def test_v7_requires_original_joint_purpose_and_keeps_frozen_decoder_contract(tmp_path):
    legacy, client = budget(tmp_path), Client()
    with pytest.raises(ValueError):
        call(provider(legacy, client), v7_config())
    assert not client.calls and legacy.snapshot()["requests_reserved"] == 0
    ledger = joint_budget(tmp_path)
    for change in (
        dict(temperature=0),
        dict(max_steps=64),
        dict(context_limit=24576),
        dict(role="feedback"),
    ):
        client, before = Client(), ledger.snapshot()
        with pytest.raises(ValueError):
            call(provider(ledger, client), v7_config(**change))
        assert not client.calls and ledger.snapshot() == before


@pytest.mark.parametrize("cap", [2048, 16384])
def test_v7_usage_over_its_own_request_cap_halts_without_reclaiming_unknown_cost(tmp_path, cap):
    ledger = joint_budget(tmp_path)
    before = ledger.snapshot()
    client = Client(value(usage=usage(output=cap + 1)))
    with pytest.raises(ProviderCallError) as error:
        call(provider(ledger, client, "v7-slot:overage"), v7_config(max_new_tokens=cap))
    assert error.value.settlement == "unknown" and len(client.calls) == 1
    assert ledger.snapshot()["held_microcny"] == ledger.price_sheet.cost_microcny(
        hit=0, miss=1048576, output=cap
    )
    assert ledger.snapshot()["settled_tariff_microcny"] == before["settled_tariff_microcny"]
    with pytest.raises(BudgetUnavailable):
        call(provider(ledger, Client(), "v7-slot:after-halt"), v7_config())


def test_v7_actual_harness_system_and_budgeted_native_submission_roundtrip(tmp_path):
    bundle = adapt_finqa([finqa_record()], split="train", revision="V7-provider-CPU")[0]
    ledger, cfg = joint_budget(tmp_path), v7_config(max_new_tokens=16384)
    returned = value(usage=usage(output=4096))
    returned["choices"][0]["message"].update(
        content="R: Use the public revenue difference.",
        tool_calls=[
            dict(
                id="v7-submit",
                type="function",
                function=dict(name="submit_program", arguments='{"program":"subtract(8, 2)"}'),
            )
        ],
    )
    client = Client(returned)
    sid = "v7-slot:complete-new-candidate"
    episode = asyncio.run(
        run_episode(
            bundle.public,
            provider(ledger, client, sid),
            cfg,
            invocation_context=dict(run_id=ledger.run_id, episode_id=sid, attempt_index=1),
        )
    )
    assert episode.stop_reason == "final_answer" and episode.final_program == "subtract(8, 2)"
    assert episode.config.harness_id == "bigfinance-derived-vtdo-v7"
    assert episode.config.submission_profile == "finqa-public-reasoning-v2"
    assert episode.actual_model_calls == 1 and episode.all_provider_calls_settled
    assert len(client.calls) == 1
    wrong_messages = copy.deepcopy(list(episode.messages[:2]))
    wrong_messages[0]["content"] += " unregistered system change"
    fresh_client, before = Client(returned), ledger.snapshot()
    with pytest.raises(ValueError):
        call(provider(ledger, fresh_client, "v7-slot:bad-system"), cfg, messages=wrong_messages)
    assert not fresh_client.calls and ledger.snapshot() == before
