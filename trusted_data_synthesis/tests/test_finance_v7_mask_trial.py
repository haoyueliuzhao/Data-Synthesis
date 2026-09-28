"""Bounded controller mocks: no HTTP, credentials, GPU, or budget database."""

import asyncio

import pytest

from trusted_synthesis.finance_research import v7_review_mask_trial as trial
from trusted_synthesis.finance_research.contracts import digest
from trusted_synthesis.finance_research.storage import encode


class Ledger:
    def __init__(self):
        self.halt = False
        self.unknown = 2  # Previously acknowledged historical events are retained.
        self.spent = 1000
        self.pending = 0
        self.unacknowledged = 0

    def snapshot(self):
        return dict(
            halt=self.halt,
            pending_requests=self.pending,
            unacknowledged_unknown_requests=self.unacknowledged,
            unknown_requests=self.unknown,
            settled_tariff_microcny=self.spent,
        )


class Client:
    def __init__(self, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False


def prepared(tmp_path, monkeypatch, *, unknown_first=False):
    jobs = []
    for index in range(12):
        request = dict(max_output_tokens=16384, mock_coordinate=index)
        jobs.append(dict(key=f"job:{index}", request=request, request_sha256=digest(request)))
    plan = dict(id="synthetic_plan", maximum_calls=12, jobs=jobs)
    ledger, paid_calls, published, statuses = Ledger(), [], {}, []
    root = tmp_path / "trial"
    monkeypatch.setattr(trial, "checked_plan", lambda output: plan)
    monkeypatch.setattr(trial, "ledger_for", lambda value: ledger)
    monkeypatch.setattr(trial, "_key", lambda path: "synthetic-no-real-credential")
    monkeypatch.setattr(trial.httpx, "AsyncClient", Client)
    monkeypatch.setattr(trial, "status", lambda output, value: statuses.append(value))
    monkeypatch.setattr(
        trial,
        "inspect_slot_review",
        lambda raw, request: dict(
            interface_admitted=True,
            semantic_consistent=False,
            validation=dict(v_trace="unknown"),
            error="synthetic semantic uncertainty",
        ),
    )

    def publish(path, value, name="record.json"):
        path.mkdir(parents=True, exist_ok=False)
        (path / name).write_bytes(encode(value))
        published[str(path.relative_to(root))] = value

    async def response(**kwargs):
        index = len(paid_calls)
        paid_calls.append(kwargs["episode_id"])
        assert kwargs["client"].__class__ is Client
        await asyncio.sleep(0)  # At most four real-time in-flight mock calls.
        if unknown_first and index == 0:
            ledger.unknown += 1
            ledger.unacknowledged += 1
            ledger.halt = True
            raise RuntimeError("synthetic unknown settlement; not an HTTP request")
        ledger.spent += 10
        return dict(
            finish_reason="tool_calls",
            review_format_error=None,
            review_text="{}",
            mock_call_index=index,
        )

    monkeypatch.setattr(trial, "publish", publish)
    monkeypatch.setattr(trial, "request_review", response)
    return root, ledger, paid_calls, published, statuses


def test_twelve_successful_interfaces_never_expand_or_admit_full_review(tmp_path, monkeypatch):
    root, ledger, calls, published, statuses = prepared(tmp_path, monkeypatch)
    result = asyncio.run(trial.run(root, tmp_path / "unused.env"))
    assert len(calls) == len(set(calls)) == 12
    assert result["returned"] == result["interface_passed"] == result["denominator"] == 12
    assert result["semantic_consistent"] == 0
    assert result["technical_trial_admitted"] is True
    assert result["original_full_review_gate_admitted"] is False
    assert not result["automatic_expansion"] and not result["full_generation_started"]
    assert not result["training_started"]
    assert result["extra_settled_microcny"] == 120
    assert ledger.unknown == 2
    assert len([p for p in published if p.endswith("/response")]) == 12
    assert statuses[-1]["phase"] == "FIXED_12_TRIAL_COMPLETE"
    assert all(s["denominator"] == 12 and not s["automatic_expansion"] for s in statuses)


def test_unknown_stops_new_dispatch_after_at_most_four_inflight_without_retry(
    tmp_path, monkeypatch
):
    root, ledger, calls, published, statuses = prepared(tmp_path, monkeypatch, unknown_first=True)
    result = asyncio.run(trial.run(root, tmp_path / "unused.env"))
    assert 1 <= len(calls) <= 4
    assert len(set(calls)) == len(calls)
    assert result["returned"] == len(calls) - 1
    assert len(result["errors"]) == 1 and result["errors"][0]["retry"] is False
    assert ledger.halt and ledger.unknown == 3 and ledger.unacknowledged == 1
    assert result["technical_trial_admitted"] is False
    assert result["original_full_review_gate_admitted"] is False
    assert not result["automatic_expansion"] and not result["training_started"]
    assert len([p for p in published if p.endswith("/blocked")]) == 1
    assert statuses[-1]["phase"] == "FIXED_12_TRIAL_BLOCKED"


def test_any_started_run_is_never_implicitly_resent(tmp_path, monkeypatch):
    root, _, calls, _, _ = prepared(tmp_path, monkeypatch, unknown_first=True)
    asyncio.run(trial.run(root, tmp_path / "unused.env"))
    first_count = len(calls)
    with pytest.raises(ValueError, match="never implicit resend"):
        asyncio.run(trial.run(root, tmp_path / "unused.env"))
    assert len(calls) == first_count


@pytest.mark.parametrize("block", ["halt", "pending", "unacknowledged"])
def test_existing_halt_or_unclear_cost_blocks_before_any_call(tmp_path, monkeypatch, block):
    root, ledger, calls, published, _ = prepared(tmp_path, monkeypatch)
    setattr(ledger, block, True if block == "halt" else 1)
    with pytest.raises(ValueError, match="blocks R5"):
        asyncio.run(trial.run(root, tmp_path / "unused.env"))
    assert calls == [] and published == {}


@pytest.mark.parametrize("count,maximum", [(13, 12), (12, 13), (11, 12)])
def test_checked_plan_rejects_any_non_twelve_denominator(monkeypatch, tmp_path, count, maximum):
    value = dict(runtime_binding={"fixture": "sha"}, jobs=[{}] * count, maximum_calls=maximum)
    value["id"] = digest(value)
    monkeypatch.setattr(trial, "read_json", lambda path: value)
    monkeypatch.setattr(trial, "runtime_binding", lambda: {"fixture": "sha"})
    with pytest.raises(ValueError, match="fixed denominator"):
        trial.checked_plan(tmp_path)
