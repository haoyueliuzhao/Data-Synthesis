"""Shared V6 generation/review ledger controls; no real HTTP, model or GPU."""

import asyncio
import json
from concurrent.futures import ThreadPoolExecutor

import pytest
from test_finance_research_probe_budget import budget, sheet, usage
from test_finance_research_probe_provider import Client, config, provider, value

from trusted_synthesis.finance_research.contracts import ProviderCallError, invocation_identity
from trusted_synthesis.finance_research.harness import episode_tool_specs, system_message
from trusted_synthesis.finance_research.probe_budget import (
    V6_PURPOSE,
    BudgetUnavailable,
    DuplicateInvocation,
    InvalidUsage,
    ProbeBudget,
)


def v6_budget(tmp_path, **changes):
    return ProbeBudget(
        **{
            "path": tmp_path / "joint.sqlite",
            "run_id": "v6-joint-fixture",
            "price_sheet": sheet(),
            "max_output_tokens": 16384,
            "purpose": V6_PURPOSE,
            **changes,
        }
    )


def reserve(ledger, episode, output):
    coordinates = invocation_identity(
        {"run_id": ledger.run_id, "episode_id": episode, "attempt_index": 1}, turn_index=0
    )
    request = {"model": "deepseek-flash", "max_tokens": output, "thinking": {"type": "disabled"}}
    amount = ledger.reserve(
        coordinates["invocation_id"],
        coordinates=coordinates,
        request=request,
        request_body=json.dumps(request).encode(),
    )
    return coordinates["invocation_id"], amount


def settle(ledger, invocation, output):
    ledger.mark_dispatched(invocation)
    return ledger.settle(
        invocation,
        usage=usage(output=output),
        http_status=200,
        response_classification="model_response",
        response_body=b"{}",
    )


def v6_config(**changes):
    return config(
        harness_id="bigfinance-derived-vtdo-v6",
        submission_profile="finqa-public-reasoning-v1",
        **changes,
    )


def call(api, cfg):
    return asyncio.run(
        api.chat(
            [system_message(cfg), {"role": "user", "content": "public"}],
            episode_tool_specs(cfg),
            cfg,
        )
    )


def test_one_800_CNY_database_has_request_specific_reserves_and_actual_cost(tmp_path):
    generation = v6_budget(tmp_path)
    review = v6_budget(tmp_path)
    gen_id, gen_hold = reserve(generation, "generation/slot0", 2048)
    rev_id, rev_hold = reserve(review, "review/slot0/reviewer0", 16384)
    assert (gen_hold, rev_hold) == (2_113_536, 2_228_224)
    assert generation.snapshot()["held_microcny"] == gen_hold + rev_hold
    assert review.snapshot()["hard_cap_microcny"] == 800_000_000
    assert review.config["schema"] == "probe_budget.v2"
    assert settle(review, rev_id, 10000) == 80_120
    assert settle(generation, gen_id, 20) == 280
    reopened = v6_budget(tmp_path).snapshot()
    assert reopened["settled_tariff_microcny"] == 80_400 and reopened["held_microcny"] == 0
    assert reopened["requests_dispatched"] == reopened["requests_reserved"] == 2
    assert reopened["actual_completion_tokens_settled"] == 10020
    with pytest.raises(DuplicateInvocation):
        reserve(generation, "generation/slot0", 2048)


@pytest.mark.parametrize("limit,actual", [(2048, 2049), (16384, 16385)])
def test_settlement_checks_each_request_not_global_16384(tmp_path, limit, actual):
    ledger = v6_budget(tmp_path)
    identity, held = reserve(ledger, "bounded", limit)
    with pytest.raises(InvalidUsage):
        settle(ledger, identity, actual)
    assert ledger.snapshot()["held_microcny"] == held
    assert ledger.snapshot()["settled_tariff_microcny"] == 0
    assert ledger.request_record(identity)["state"] == "DISPATCHED"


def test_joint_concurrent_exposure_and_halt_cover_generation_and_review(tmp_path):
    ledger = v6_budget(
        tmp_path,
        price_sheet=sheet(input_miss_cny_per_million="200", context_input_token_ceiling=500000),
    )

    def attempt(index):
        try:
            return reserve(ledger, str(index), 2048 if index % 2 else 16384)
        except BudgetUnavailable:
            return None

    with ThreadPoolExecutor(max_workers=6) as pool:
        accepted = [result for result in pool.map(attempt, range(12)) if result is not None]
    assert len(accepted) == 7
    assert ledger.snapshot()["held_microcny"] == sum(row[1] for row in accepted) < 800_000_000
    ledger.unknown(accepted[0][0], reason="mock unknown review cost")
    reopened = v6_budget(tmp_path, price_sheet=ledger.price_sheet)
    for limit in (2048, 16384):
        with pytest.raises(BudgetUnavailable):
            reserve(reopened, f"after-halt-{limit}", limit)
    assert reopened.snapshot()["unknown_requests"] == 1


@pytest.mark.parametrize(
    "change",
    [
        {"run_id": "fresh-counter-name"},
        {"hard_cap_microcny": 900_000_000},
        {"request_cap": 999999},
        {"purpose": "finqa_fixed_probe_inventory_v1", "max_output_tokens": 2048},
        {"price_sheet": sheet(output_cny_per_million="9")},
    ],
)
def test_reopen_cannot_reset_or_change_joint_budget(tmp_path, change):
    ledger = v6_budget(tmp_path)
    identity, _ = reserve(ledger, "first", 2048)
    settle(ledger, identity, 20)
    with pytest.raises(ValueError, match="different"):
        v6_budget(tmp_path, **change)
    assert v6_budget(tmp_path).snapshot()["settled_tariff_microcny"] == 280


def test_legacy_default_schema_reserve_and_output_contract_unchanged(tmp_path):
    legacy = budget(tmp_path)
    assert legacy.config["schema"] == "probe_budget.v1"
    assert "allowed_output_limits" not in legacy.config
    assert legacy.reservation_microcny == 2_113_536
    assert legacy.allowed_output_limits == (2048,)
    with pytest.raises(ValueError, match="contract"):
        reserve(legacy, "new-review-on-old-run", 16384)
    turn = asyncio.run(provider(legacy, Client()).chat([], [], config()))
    assert turn.provider_metadata["public_request"]["max_tokens"] == 2048
    assert legacy.snapshot()["settled_tariff_microcny"] == 280


def test_v6_generation_uses_2048_and_overage_halts_entire_joint_budget(tmp_path):
    ledger = v6_budget(tmp_path)
    client = Client(value(usage=usage(output=2049)))
    api = provider(ledger, client)
    with pytest.raises(ProviderCallError) as caught:
        call(api, v6_config())
    assert caught.value.settlement == "unknown" and len(client.calls) == 1
    assert json.loads(client.calls[0][1]["content"])["max_tokens"] == 2048
    assert ledger.snapshot()["unknown_requests"] == 1
    assert ledger.snapshot()["held_microcny"] == 2_113_536
    with pytest.raises(BudgetUnavailable):
        reserve(ledger, "subsequent-review", 16384)


def test_review_limit_cannot_be_used_as_generation_limit(tmp_path):
    ledger, client = v6_budget(tmp_path), Client()
    with pytest.raises(ValueError):
        call(provider(ledger, client), v6_config(max_new_tokens=16384))
    assert not client.calls and ledger.snapshot()["requests_reserved"] == 0


def test_v6_generation_requires_v6_joint_purpose_not_old_budget(tmp_path):
    legacy, client = budget(tmp_path), Client()
    with pytest.raises(ValueError):
        call(provider(legacy, client), v6_config())
    assert not client.calls and legacy.snapshot()["requests_reserved"] == 0


def test_legacy_generation_cannot_consume_v6_joint_budget(tmp_path):
    ledger, client = v6_budget(tmp_path), Client()
    with pytest.raises(ValueError):
        asyncio.run(provider(ledger, client).chat([], [], config()))
    assert not client.calls and ledger.snapshot()["requests_reserved"] == 0
