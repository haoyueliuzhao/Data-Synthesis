"""Durable-file cost controls for the new 32 rows; no Provider or tokenizer execution."""

import copy
from decimal import Decimal
from pathlib import Path

import pytest

from trusted_synthesis.experiments.finance_qa_vnext_basis_conditioned_support.costs import (
    cost_summary,
    costs,
)
from trusted_synthesis.experiments.finance_qa_vnext_basis_conditioned_support.plan import (
    LABELS,
    MODEL,
    SOURCE,
    TASKS,
    encode,
    read_json,
    registrations,
)
from trusted_synthesis.experiments.finance_qa_vnext_thinking_comparison.online.common import write

ROOT = Path(__file__).resolve().parents[2]


def batch(tmp_path, change=None, change_frozen=False):
    public = {task: read_json(ROOT / SOURCE / f"preparation/public/{task}.json") for task in TASKS}
    expected = registrations(public)
    observed = copy.deepcopy(expected)
    if change:
        change(observed)
    for task in TASKS:
        write(tmp_path / "preparation", f"public/{task}.json", encode(public[task]))
    write(
        tmp_path / "preparation",
        "registrations.json",
        encode(observed if change_frozen else expected),
    )
    write(tmp_path / "online", "launch.json", encode({"registrations": observed}))
    return tmp_path / "online"


def attempt(
    online,
    index=0,
    *,
    label=None,
    time="2026-09-11T00:00:00+00:00",
    usage=None,
    outcome=True,
    tool=None,
):
    turns = online / "sessions" / (label or LABELS[0]) / "turns"
    write(
        turns,
        f"{index:03d}_reservation.json",
        encode(
            {
                "index": index,
                "started_utc": time,
                "request_bytes": 100,
                "reserved_token_allowance": 115712,
                "requested_model": MODEL,
                "provider_call": True,
            }
        ),
    )
    if outcome:
        write(
            turns,
            f"{index:03d}_outcome.json",
            encode(
                {
                    "usage": usage,
                    "response_bytes": 200,
                    "elapsed_ns": 987654,
                    "reasoning_telemetry": {"nonempty": True, "characters": 17},
                }
            ),
        )
        write(turns, f"{index:03d}_assistant.raw", b"fixture public response")
        write(turns, f"{index:03d}_response_projection.json", b"{}")
    if tool is not None:
        write(turns, f"{index:03d}_tool.json", encode(tool))


def usage():
    return {
        "prompt_tokens": 120,
        "completion_tokens": 10,
        "total_tokens": 130,
        "prompt_cache_hit_tokens": 100,
        "prompt_cache_miss_tokens": 20,
        "completion_tokens_details": {"reasoning_tokens": 7},
    }


def test_all_32_empty_reservation_sessions_remain_present(tmp_path):
    result = costs(batch(tmp_path))
    assert [row["label"] for row in result["rows"]] == list(LABELS)
    assert {row["arm"] for row in result["rows"]} == {"endpoint", "movement"}
    assert result["aggregate"]["reserved_attempts"] == 0
    assert result["registered_rate_estimate_cny"] == "0"
    assert result["all_registered_sessions_included"]
    for row in result["rows"]:
        assert row["recorded_outcomes"] == row["reserved_attempts"] == 0
        assert row["actual_billed_cost"] is None
        assert row["attempts_by_registered_rate_window"] == {}
        for metric in row["provider_usage"].values():
            assert metric == {
                "observed_sum": 0,
                "observed_attempts": 0,
                "missing_attempts": 0,
                "complete_sum": 0,
            }
    assert result["price_checked_date"] == "2026-09-09"
    assert "inherited" in result["price_checked_date_role"]
    assert result["current_price_reverified"] is False
    assert result["registered_pricing_policy"]["current_price_reverified"] is False
    assert result["price_estimates_are_not_settled_invoices"]


@pytest.mark.parametrize(
    "reported",
    [
        None,
        {},
        {"prompt_cache_hit_tokens": 100, "completion_tokens": 10},
        {"prompt_cache_hit_tokens": True, "prompt_cache_miss_tokens": 20, "completion_tokens": 10},
    ],
)
def test_missing_or_noninteger_billing_usage_is_unknown_not_zero(tmp_path, reported):
    online = batch(tmp_path)
    attempt(online, usage=reported)
    result = costs(online)
    row = result["rows"][0]
    assert row["reserved_attempts"] == row["recorded_outcomes"] == 1
    assert row["published_rate_estimate_cny"] is None
    assert row["registered_rate_estimate_cny"] is None
    assert result["registered_rate_estimate_cny"] is None
    assert result["usage_missing_is_not_zero"]


def test_reservation_without_outcome_retains_missing_attempt(tmp_path):
    online = batch(tmp_path)
    attempt(online, 0, usage=usage())
    attempt(online, 1, outcome=False)
    result = costs(online)
    row = result["rows"][0]
    assert row["reserved_attempts"] == 2 and row["recorded_outcomes"] == 1
    assert row["provider_usage"]["completion_tokens"] == {
        "observed_sum": 10,
        "observed_attempts": 1,
        "missing_attempts": 1,
        "complete_sum": None,
    }
    assert (
        result["aggregate"]["provider_usage"]["completion_tokens"]
        == row["provider_usage"]["completion_tokens"]
    )
    assert row["attempts_by_registered_rate_window"] == {"offpeak": 2}
    assert row["published_rate_estimate_cny"] is None
    assert result["registered_rate_estimate_cny"] is None


def test_actual_utc_request_windows_and_reasoning_are_not_double_counted(tmp_path):
    online = batch(tmp_path)
    times = (
        "00:59:59",
        "01:00:00",
        "03:59:59",
        "04:00:00",
        "05:59:59",
        "06:00:00",
        "09:59:59",
        "10:00:00",
    )
    for index, hour in enumerate(times):
        attempt(online, index, time=f"2026-09-11T{hour}+00:00", usage=usage())
    result = costs(online)
    row = result["rows"][0]
    assert row["attempts_by_registered_rate_window"] == {"offpeak": 4, "peak": 4}
    # Each off-peak request is (100*.05 + 20*1.5 + 10*4.5)/1e6 = .00008 CNY.
    assert Decimal(row["registered_rate_estimate_cny"]) == Decimal("0.00096")
    assert Decimal(result["registered_rate_estimate_cny"]) == Decimal("0.00096")
    assert Decimal(row["published_rate_estimate_cny"]["offpeak"]) == Decimal("0.00064")
    assert Decimal(row["published_rate_estimate_cny"]["peak"]) == Decimal("0.00128")
    provider = result["aggregate"]["provider_usage"]
    assert provider["reasoning_tokens"]["complete_sum"] == 56
    assert provider["completion_tokens"]["complete_sum"] == 80
    assert provider["total_tokens"]["complete_sum"] == 1040
    assert result["reasoning_is_subset_not_added_twice"]
    assert result["registered_pricing_policy"]["reasoning_already_in_completion"]


def test_unreported_reasoning_subset_does_not_hide_observed_billing_usage(tmp_path):
    online = batch(tmp_path)
    reported = usage()
    reported.pop("completion_tokens_details")
    attempt(online, usage=reported)
    result = costs(online)
    assert result["aggregate"]["provider_usage"]["reasoning_tokens"]["complete_sum"] is None
    assert Decimal(result["registered_rate_estimate_cny"]) == Decimal("0.00008")


def test_request_outcome_tool_and_byte_telemetry_preserves_prior_shape(tmp_path):
    online = batch(tmp_path)
    outputs = [
        {
            "tool": "calculate",
            "status": "ok",
            "result": {"operation_count": 3, "dependency_depth": 2},
        },
        {"tool": "calculate", "status": "error", "error": "fixture syntax error"},
        {"tool": "read_source", "status": "ok", "result": {"records": []}},
    ]
    for index, tool in enumerate(outputs):
        attempt(online, index, usage=usage(), tool=tool)
    result = cost_summary(online)
    row = result["rows"][0]
    assert row["reserved_attempts"] == row["recorded_outcomes"] == 3
    assert row["public_model_responses"] == row["tool_calls"] == 3
    assert row["tool_errors"] == row["successful_calculations"] == 1
    assert row["successful_expression_operations"] == 3
    assert row["maximum_expression_dependency_depth"] == 2
    assert row["http_request_bytes"] == 300 and row["maximum_http_request_bytes"] == 100
    assert row["http_response_bytes"] == 600 and row["response_projection_bytes"] == 6
    assert row["raw_assistant_bytes"] == 3 * len(b"fixture public response")
    assert row["reasoning_nonempty_responses"] == 3
    assert row["reasoning_characters_observed"] == 51
    assert row["summed_request_elapsed_ns"] == 3 * 987654
    assert row["reserved_token_allowance"] == 3 * 115712
    assert result["aggregate"]["successful_expression_operations"] == 3
    assert result["summed_latency_is_not_parallel_wall_clock"]
    assert result["expression_operations_are_not_old_atomic_actions"]


@pytest.mark.parametrize(
    "field,value",
    [
        ("label", "E_X2_B2_01"),
        ("arm", "N"),
        ("requested_basis", "movement"),
        ("task_key", "X2"),
        ("replicate", 8),
        ("requested_model", "other-model"),
        ("condition_id", "old_E_condition"),
        ("id", "tampered_registration"),
    ],
)
@pytest.mark.parametrize("change_frozen", [False, True])
def test_wrong_registration_metadata_is_rejected_even_if_both_copies_change(
    tmp_path,
    field,
    value,
    change_frozen,
):
    def change(rows):
        rows[0][field] = value

    online = batch(tmp_path, change=change, change_frozen=change_frozen)
    with pytest.raises(ValueError, match="exact_frozen_new_32_registration_identity"):
        costs(online)


@pytest.mark.parametrize(
    "change",
    [
        lambda rows: rows.pop(),
        lambda rows: rows.append(copy.deepcopy(rows[0])),
        lambda rows: rows.reverse(),
    ],
)
def test_missing_extra_or_reordered_rows_cannot_change_denominator(tmp_path, change):
    with pytest.raises(ValueError, match="exact_frozen_new_32_registration_identity"):
        costs(batch(tmp_path, change=change, change_frozen=True))


@pytest.mark.parametrize("time", ["2026-09-11T01:00:00", "2026-09-11T01:00:00+08:00"])
def test_non_utc_or_undated_timezone_cannot_choose_a_pricing_window(tmp_path, time):
    online = batch(tmp_path)
    attempt(online, time=time, usage=usage())
    with pytest.raises(ValueError, match="cost.reservation_UTC"):
        costs(online)
