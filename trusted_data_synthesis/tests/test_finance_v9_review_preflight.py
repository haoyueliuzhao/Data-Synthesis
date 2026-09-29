"""Zero-model request-size and immutable conditional inventory controls."""

from types import SimpleNamespace

import pytest
from test_finance_research_probe_budget import sheet
from test_finance_v8_single_target_review import fixture

from trusted_synthesis.finance_research import v9_review_preflight as preflight
from trusted_synthesis.finance_research.probe_budget import V6_PURPOSE, ProbeBudget
from trusted_synthesis.finance_research.v6_collection import bound, persist
from trusted_synthesis.finance_research.v6_review_provider import _request_body


def test_request_bytes_match_actual_provider_without_wallet_or_http():
    _, _, requests, _, _ = fixture()
    request = requests[0]["s0"]
    preflight.bind_capacity(request, generation_tokens=100, fragments=10, actions=1)
    ledger = object.__new__(ProbeBudget)
    ledger.purpose = V6_PURPOSE
    ledger.price_sheet = sheet()
    ledger.config = {"amendment_id": "fixture"}
    ledger.allowed_output_limits = (2048, 16384, 32768, 65536, 131072)
    actual, _ = _request_body(ledger, request)
    assert preflight.request_body(request) == actual
    request["model"] = "other-model"
    with pytest.raises(ValueError, match="fixed API model"):
        preflight.request_body(request)


def test_capacity_is_not_predicted_usage_and_bytes_not_input_tokens():
    jobs = [dict(capacity=dict(max_output_tokens=16384), exact_http_body_bytes=1000)]
    result = preflight.cost_summary(jobs, sheet(), remaining_microcny=200000)
    assert result["exact_http_body_bytes_total"] == 1000
    assert result["frozen_output_tokens_total"] == 16384
    assert result["output_full_capacity_cost_microcny"] == 131072
    assert result["official_input_token_ceiling_total"] == 1048576
    assert result["guaranteed_tariff_upper_bound_microcny"] == 2228224
    assert result["output_full_capacity_cost_fits_remaining"] is True
    assert result["guaranteed_upper_bound_fits_remaining"] is False
    assert result["actual_api_input_tokens_known"] is False
    assert result["output_capacity_is_not_predicted_usage"] is True


def test_all_11382_slot_minimum_output_caps_exceed_original_remaining_budget():
    jobs = [dict(capacity=dict(max_output_tokens=16384))] * 11382
    result = preflight.cost_summary(jobs, sheet(), 641235370)
    assert result["output_full_capacity_cost_microcny"] == 1491861504
    assert not result["output_full_capacity_cost_fits_remaining"]


def test_native_false_originals_retained_but_never_dispatch_jobs():
    prepared, _, requests, _, _ = fixture()
    prepared["mechanical"]["s0"]["native_correct"] = False
    task = prepared["bundle"]["task_id"]
    reference = __import__("json").loads(requests[0]["s0"]["messages"][1]["content"])[
        "review_only_private_reference"
    ]
    data = dict(
        prepared=bound(prepared),
        private_reference=reference,
        episodes={s: dict(path=s) for s in prepared["mechanical"]},
        generation_tokens={s: 100 for s in prepared["mechanical"]},
    )
    inventory = SimpleNamespace(
        prepared=lambda _: data,
        slots={task: [dict(task_id=task, slot_id=f"s{i}", slot_index=i) for i in range(8)]},
        plan={"id": "parent"},
        seal={"id": "seal"},
        native={"id": "native"},
    )
    payload = preflight.prepare_task(inventory, task)
    assert len(payload["prepared"]["bundle"]["slots"]) == 8
    assert len(payload["requests"]) == len(payload["jobs"]) == 14
    assert "s0" not in payload["q_true_slot_ids"]
    assert len(payload["slot_features"]) == 8
    assert payload["alignment_capacity"]["generation_tokens"] == 800
    assert all(j["slot_id"] != "s0" for j in payload["jobs"])


def test_task_input_id_detects_changes_and_no_api_exists(tmp_path):
    task = "task"
    value = bound(
        dict(
            schema="v9_conditioned_task_review_inputs.v1",
            task_id=task,
            prepared=bound(dict(bundle={"task_id": task})),
        )
    )
    path = preflight.task_input_path(tmp_path, task)
    persist(path.parent, value)
    assert preflight.load_task_input(tmp_path, task) == value
    with pytest.raises(ValueError, match="immutable artifact differs"):
        persist(path.parent, {**value, "task_id": "other"})
    assert not hasattr(preflight, "request_review")
    assert not hasattr(preflight, "ledger_for")
