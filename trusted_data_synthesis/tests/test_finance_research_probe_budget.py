"""Synthetic tariff/accounting controls. No credentials, network, model or GPU."""

import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor

import pytest

from trusted_synthesis.finance_research.contracts import invocation_identity
from trusted_synthesis.finance_research.probe_budget import (
    HARD_CAP_MICROCNY,
    BudgetUnavailable,
    DuplicateInvocation,
    InvalidUsage,
    ProbeBudget,
    ProbePriceSheet,
)


def sheet(**changes):
    return ProbePriceSheet(
        **{
            "input_hit_cny_per_million": "0.04",
            "input_miss_cny_per_million": "2",
            "output_cny_per_million": "8",
            "context_input_token_ceiling": 1048576,
            "official_max_output_tokens": 393216,
            "source_url": "https://api-docs.deepseek.com/zh-cn/quick_start/pricing/",
            "checked_at_utc": "2026-09-28T07:00:00Z",
            "source_sha256": "0" * 64,
            **changes,
        }
    )


def budget(tmp_path, **changes):
    return ProbeBudget(
        tmp_path / "budget.sqlite",
        run_id="inventory-fixture",
        price_sheet=sheet(**changes),
        max_output_tokens=2048,
    )


def reserve(ledger, episode="slot-0"):
    coords = invocation_identity(
        {"run_id": ledger.run_id, "episode_id": episode, "attempt_index": 1}, turn_index=0
    )
    body = {"model": "deepseek-flash", "max_tokens": 2048, "thinking": {"type": "disabled"}}
    ledger.reserve(
        coords["invocation_id"],
        coordinates=coords,
        request=body,
        request_body=json.dumps(body).encode(),
    )
    return coords["invocation_id"]


def usage(hit=41, miss=59, output=20):
    return {
        "prompt_tokens": hit + miss,
        "prompt_cache_hit_tokens": hit,
        "prompt_cache_miss_tokens": miss,
        "completion_tokens": output,
        "total_tokens": hit + miss + output,
        "prompt_tokens_details": {"cached_tokens": hit},
    }


def test_actual_usage_settlement_releases_only_excess_reservation_and_rounds_up(tmp_path):
    ledger = budget(tmp_path)
    assert ledger.reservation_microcny == 2_113_536
    identity = reserve(ledger)
    assert ledger.snapshot()["held_microcny"] == 2_113_536
    ledger.mark_dispatched(identity)
    charged = ledger.settle(
        identity,
        usage=usage(),
        http_status=200,
        response_classification="model_response",
        response_body=b'{"usage":"fixture"}',
    )
    assert charged == 280  # 41*.04 + 59*2 + 20*8 = 279.64 micro-CNY, upward.
    state = ledger.snapshot()
    assert state["settled_tariff_microcny"] == 280 and state["held_microcny"] == 0
    assert state["actual_cache_hit_tokens_settled"] == 41
    assert state["actual_cache_miss_tokens_settled"] == 59
    assert state["actual_prompt_tokens_settled"] == 100
    assert state["actual_completion_tokens_settled"] == 20
    assert sheet().cost_microcny(hit=1, miss=0, output=0) == 1
    with pytest.raises(DuplicateInvocation):
        reserve(ledger)
    with pytest.raises(ValueError, match="dispatched"):
        ledger.settle(
            identity,
            usage=usage(),
            http_status=200,
            response_classification="model_response",
            response_body=b"{}",
        )


def test_unknown_holds_full_reservation_halts_and_survives_reopen(tmp_path):
    ledger = budget(tmp_path)
    identity = reserve(ledger)
    ledger.mark_dispatched(identity)
    ledger.unknown(identity, reason="timeout", evidence={"status": "unknown"})
    reopened = budget(tmp_path)
    state = reopened.snapshot()
    assert state["unknown_requests"] == 1 and state["held_microcny"] == 2_113_536
    assert state["settled_tariff_microcny"] == 0 and state["halt"]["reason"] == "timeout"
    assert reopened.unsettled()[0]["state"] == "UNKNOWN"
    with pytest.raises(BudgetUnavailable):
        reserve(reopened, "next-slot")


def test_atomic_concurrent_reservations_cannot_exceed_800_CNY(tmp_path):
    # Deliberately artificial high miss price exercises the cap in only 12 attempts.
    ledger = budget(tmp_path, input_miss_cny_per_million="200", context_input_token_ceiling=500000)

    def attempt(index):
        try:
            reserve(ledger, str(index))
            return True
        except BudgetUnavailable:
            return False

    with ThreadPoolExecutor(max_workers=8) as pool:
        accepted = list(pool.map(attempt, range(12)))
    assert sum(accepted) == 7
    state = ledger.snapshot()
    assert state["exposure_microcny"] == 700_114_688 < HARD_CAP_MICROCNY
    assert state["exposure_warning_reached"] and not state["warning_reached"]
    with sqlite3.connect(ledger.path) as db:
        assert (
            db.execute("SELECT COUNT(*) FROM requests").fetchone()[0] == state["requests_reserved"]
        )
        assert (
            db.execute("SELECT SUM(reserved_microcny) FROM requests").fetchone()[0]
            == state["held_microcny"]
        )


@pytest.mark.parametrize(
    "change",
    [
        {"prompt_cache_hit_tokens": 42},
        {"total_tokens": 121},
        {"prompt_cache_miss_tokens": None},
        {"completion_tokens": True},
        {"prompt_tokens_details": {"cached_tokens": 9}},
        {"completion_tokens": 3000, "total_tokens": 3100},
    ],
)
def test_inconsistent_usage_is_not_silently_settled(change):
    with pytest.raises(InvalidUsage):
        sheet().usage({**usage(), **change}, output_limit=2048)


def test_database_cannot_mix_run_tariff_or_output_contract(tmp_path):
    ledger = budget(tmp_path)
    with pytest.raises(ValueError, match="different"):
        ProbeBudget(
            ledger.path, run_id="other-purpose-run", price_sheet=sheet(), max_output_tokens=2048
        )
    with pytest.raises(ValueError, match="different"):
        ProbeBudget(
            ledger.path,
            run_id=ledger.run_id,
            price_sheet=sheet(output_cny_per_million="9"),
            max_output_tokens=2048,
        )


def test_request_cap_is_independent_of_money(tmp_path):
    ledger = budget(tmp_path)
    with sqlite3.connect(ledger.path) as db:
        db.execute("UPDATE counters SET requests=256000 WHERE singleton=1")
    with pytest.raises(BudgetUnavailable, match="256000"):
        reserve(ledger)


def test_new_100_CNY_run_freezes_80_warning_and_42240_requests(tmp_path):
    limits = {
        "hard_cap_microcny": 100_000_000,
        "warning_microcny": 80_000_000,
        "request_cap": 42_240,
    }
    ledger = ProbeBudget(
        tmp_path / "new.sqlite",
        run_id="new-structured-inventory",
        price_sheet=sheet(),
        max_output_tokens=2048,
        **limits,
    )

    def attempt(index):
        try:
            reserve(ledger, str(index))
            return True
        except BudgetUnavailable:
            return False

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(attempt, range(52)))
    state = ledger.snapshot()
    assert sum(results) == 47 and state["exposure_microcny"] == 99_336_192
    assert state["hard_cap_microcny"] == 100_000_000
    assert state["warning_microcny"] == 80_000_000 and state["exposure_warning_reached"]
    assert state["request_cap"] == 42_240
    with pytest.raises(ValueError, match="different"):
        ProbeBudget(ledger.path, run_id=ledger.run_id, price_sheet=sheet(), max_output_tokens=2048)
    with pytest.raises(ValueError, match="different"):
        ProbeBudget(
            ledger.path,
            run_id="old-inventory",
            price_sheet=sheet(),
            max_output_tokens=2048,
            **limits,
        )


def test_new_request_cap_does_not_fall_back_to_old_256000(tmp_path):
    ledger = ProbeBudget(
        tmp_path / "new.sqlite",
        run_id="new-structured-inventory",
        price_sheet=sheet(),
        max_output_tokens=2048,
        hard_cap_microcny=100_000_000,
        warning_microcny=80_000_000,
        request_cap=42_240,
    )
    with sqlite3.connect(ledger.path) as db:
        db.execute("UPDATE counters SET requests=42240 WHERE singleton=1")
    with pytest.raises(BudgetUnavailable, match="42240"):
        reserve(ledger)


@pytest.mark.parametrize(
    "limits",
    [
        {"hard_cap_microcny": True},
        {"hard_cap_microcny": 0},
        {"hard_cap_microcny": 100_000_000, "warning_microcny": 700_000_000},
        {"request_cap": 1.5},
        {"request_cap": 0},
    ],
)
def test_invalid_explicit_limits_fail_before_database_creation(tmp_path, limits):
    path = tmp_path / "invalid.sqlite"
    with pytest.raises(ValueError):
        ProbeBudget(
            path, run_id="bad-limits", price_sheet=sheet(), max_output_tokens=2048, **limits
        )
    assert not path.exists()
