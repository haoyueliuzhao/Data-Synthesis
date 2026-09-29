"""Finite 108-call controller mocks: no HTTP, API credentials, GPU or real ledger."""

import asyncio

import pytest

from trusted_synthesis.finance_research import v8_review_validation as trial
from trusted_synthesis.finance_research.storage import encode


class Ledger:
    def __init__(self):
        self.halt, self.unacknowledged = None, 0
        self.consumed, self.spent = 0, 0

    def snapshot(self):
        return dict(
            halt=self.halt,
            pending_requests=16,  # The separately registered generation stays active.
            unknown_requests=2,  # Acknowledged historical unknowns remain held.
            unacknowledged_unknown_requests=self.unacknowledged,
            settled_tariff_microcny=self.spent,
            request_partition=dict(consumed=dict(technical_review=self.consumed)),
        )


class Client:
    def __init__(self, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False


def scope():
    tasks = [f"fixed/{i}" for i in range(6)]
    jobs = []
    for slot in range(8):
        for task in tasks:
            for reviewer in (0, 1):
                jobs.append(
                    dict(
                        key=trial.job_key("slot", task, reviewer, f"s{slot}"),
                        stage="slot",
                        task_id=task,
                        slot_id=f"s{slot}",
                        slot_index=slot,
                        reviewer=reviewer,
                    )
                )
    for task in tasks:
        for reviewer in (0, 1):
            jobs.append(
                dict(
                    key=trial.job_key("alignment", task, reviewer),
                    stage="alignment",
                    task_id=task,
                    slot_id=None,
                    reviewer=reviewer,
                )
            )
    return dict(id="mock-fixed-full", maximum_calls=108, task_ids=tasks, jobs=jobs)


def setup(tmp_path, monkeypatch, *, unknown_first=False, malformed=False, real_paths=1):
    plan, ledger, calls, published, statuses = scope(), Ledger(), [], {}, []
    plan["negative_controls_id"] = "mock-finite-controls"
    output = tmp_path / "full108"
    monkeypatch.setattr(trial, "checked_plan", lambda path: plan)
    monkeypatch.setattr(trial, "ledger_for", lambda p: ledger)
    monkeypatch.setattr(trial, "_key", lambda path: "no-api-credential")
    monkeypatch.setattr(trial.httpx, "AsyncClient", Client)
    monkeypatch.setattr(trial, "status", lambda path, value: statuses.append(value))
    monkeypatch.setattr(
        trial, "checked", lambda path: dict(id="mock-finite-controls", passed=True)
    )

    class Context:
        def __init__(self, path, protocol):
            self.aligned = []

        def request(self, job):
            return dict(
                max_output_tokens=16384,
                task_bundle_sha256="mock-bundle",
                stage=job["stage"],
                coordinate=job["key"],
            )

        def prepare_alignment(self, task):
            assert len(calls) == 96
            self.aligned.append(task)

    monkeypatch.setattr(trial, "ReviewContext", Context)
    assessment = dict(interface_admitted=True, semantic_consistent=True, validation={})
    monkeypatch.setattr(trial, "inspect_slot_review", lambda raw, req: assessment)
    monkeypatch.setattr(trial, "inspect_alignment", lambda raw, req: assessment)
    monkeypatch.setattr(
        trial,
        "_end_to_end",
        lambda *args: dict(
            real_end_to_end_accepted_packages=real_paths,
            original1000_training_admitted=False,
            tasks={},
        ),
    )

    def publish(path, value, name="record.json"):
        path.mkdir(parents=True, exist_ok=False)
        (path / name).write_bytes(encode(value))
        published[str(path.relative_to(output))] = value

    async def response(**kwargs):
        index = len(calls)
        calls.append(kwargs["episode_id"])
        ledger.consumed += 1
        await asyncio.sleep(0)
        if unknown_first and index == 0:
            ledger.halt = "mock unknown"
            ledger.unacknowledged = 1
            raise RuntimeError("mock unknown settlement, no HTTP")
        ledger.spent += 10
        return dict(
            finish_reason="tool_calls",
            review_format_error="mock malformed JSON" if malformed else None,
            review_text="{}",
            peak_tariff_upper_bound_microcny=10,
            actual_model_calls=1,
            usage=dict(prompt_tokens=1, completion_tokens=1, total_tokens=2),
        )

    monkeypatch.setattr(trial, "publish", publish)
    monkeypatch.setattr(trial, "request_review", response)
    return output, plan, ledger, calls, published, statuses


def test_registered_negative_controls_pass_without_model_calls():
    result = trial.negative_controls()
    assert result["passed"] and result["positive_control"]
    assert len(result["cases"]) == 6 and not any(c["false_pass"] for c in result["cases"])
    assert result["model_calls"] == 0 and result["synthetic_only"]


def test_exact_96_plus_12_scope_and_no_pilot():
    value = scope()
    trial.fixed_scope(value)
    value["jobs"] = value["jobs"][:12]
    with pytest.raises(ValueError, match="full108 scope"):
        trial.fixed_scope(value)


@pytest.mark.parametrize("real_paths,expected", [(1, True), (0, False)])
def test_fixed108_all_fresh_with_generation_pending_and_real_path_required(
    tmp_path, monkeypatch, real_paths, expected
):
    output, _, ledger, calls, published, statuses = setup(
        tmp_path, monkeypatch, real_paths=real_paths
    )
    result = asyncio.run(trial.run(output, tmp_path / "unused.env"))
    assert len(calls) == len(set(calls)) == 108
    assert all(c.startswith("v8review:") for c in calls)
    assert result["returned"] == 108 and result["stages"]["slot"]["returned"] == 96
    assert result["stages"]["alignment"]["returned"] == 12
    assert result["returned_review_cost_upper_bound_microcny"] == 1080
    assert result["returned_review_usage"]["total_tokens"] == 216
    assert result["review_engineering_ready"] is expected
    assert ledger.snapshot()["pending_requests"] == 16
    assert result["original1000_training_admitted"] is False
    assert not result["automatic_next_trial"] and not result["automatic_production_review"]
    assert not result["training_started"]
    assert len([p for p in published if p.endswith("/response")]) == 108
    assert statuses[-1]["phase"] == "V8_VALIDATION_COMPLETE"


def test_normal_malformed_returns_retained_unknown_do_not_percentage_stop(tmp_path, monkeypatch):
    output, _, _, calls, published, _ = setup(
        tmp_path, monkeypatch, malformed=True, real_paths=0
    )
    result = asyncio.run(trial.run(output, tmp_path / "unused.env"))
    assert len(calls) == 108 and result["returned"] == 108
    assert result["stages"]["slot"]["interface_passed"] == 0
    assert result["stages"]["alignment"]["interface_passed"] == 0
    assert not result["review_engineering_ready"] and not result["errors"]
    assert all(
        value["validation"] is None
        for path, value in published.items()
        if path.endswith("/assessment")
    )


def test_unknown_safety_stop_never_retries_and_keeps_at_most_four_inflight(tmp_path, monkeypatch):
    output, _, ledger, calls, _, statuses = setup(tmp_path, monkeypatch, unknown_first=True)
    result = asyncio.run(trial.run(output, tmp_path / "unused.env"))
    assert 1 <= len(calls) <= 4 and len(set(calls)) == len(calls)
    assert result["returned"] == len(calls) - 1
    assert len(result["errors"]) == 1 and not result["errors"][0]["retry"]
    assert not result["review_engineering_ready"] and ledger.unacknowledged == 1
    assert statuses[-1]["phase"] == "V8_VALIDATION_STOPPED_SAFETY"
    previous = len(calls)
    with pytest.raises(ValueError, match="never implicit resend"):
        asyncio.run(trial.run(output, tmp_path / "unused.env"))
    assert len(calls) == previous


@pytest.mark.parametrize("condition", ["halt", "unknown", "consumed"])
def test_existing_safety_or_consumed_partition_blocks_before_first_call(
    tmp_path, monkeypatch, condition
):
    output, _, ledger, calls, published, _ = setup(tmp_path, monkeypatch)
    if condition == "halt":
        ledger.halt = "mock stop"
    elif condition == "unknown":
        ledger.unacknowledged = 1
    else:
        ledger.consumed = 1
    with pytest.raises(ValueError):
        asyncio.run(trial.run(output, tmp_path / "unused.env"))
    assert not calls and not published
