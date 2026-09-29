"""Conditional production boundaries without API, live wallet, or GPU."""

import asyncio
import copy

import pytest
from test_finance_v8_single_target_review import align, fixture

from trusted_synthesis.finance_research import v9_production_review as production
from trusted_synthesis.finance_research.contracts import digest
from trusted_synthesis.finance_research.storage import encode
from trusted_synthesis.finance_research.v8_single_target_review import resolve_pair


def test_native_false_adapter_is_not_a_model_judgment_and_cannot_skip_true():
    prepared, _, _, _, sides = fixture()
    with pytest.raises(ValueError, match="cannot skip"):
        production.native_ineligible_placeholder(prepared, "s0", 0)
    prepared["mechanical"]["s0"]["native_correct"] = False
    for reviewer in (0, 1):
        sides[reviewer]["s0"] = production.native_ineligible_placeholder(prepared, "s0", reviewer)
        row = sides[reviewer]["s0"]
        assert row["not_a_model_judgment"] and row["model_calls"] == 0
        assert row["interface_admitted"] is None and row["raw_review_sha256"] is None
        assert row["public_inventory_status"] == "not_assessed_native_ineligible"
    _, _, alignments = align(prepared, sides)
    result = resolve_pair(prepared, *sides, *alignments)
    assert len(result["slots"]) == 8
    assert len(result["valid_slots_retained"]) == 7
    assert not result["slots"]["s0"]["common_material_valid"]
    assert result["slots"]["s0"]["encoding_manifest"] is None


def test_all_native_false_original_task_retained_without_model_or_alignment():
    prepared, _, _, _, _ = fixture()
    for checks in prepared["mechanical"].values():
        checks["native_correct"] = False
    sides = [
        {
            sid: production.native_ineligible_placeholder(prepared, sid, r)
            for sid in prepared["mechanical"]
        }
        for r in (0, 1)
    ]
    result = resolve_pair(prepared, *sides, None, None)
    assert len(result["slots"]) == 8 and result["valid_slots_retained"] == []
    assert result["task_mapping"] == "incomplete" and not any(result["alignment_called"])


def complete_scope():
    tasks = [f"t{i}" for i in range(1000)]
    slots = [
        dict(slot_id=f"{task}/s{i}", task_id=task, slot_index=i) for task in tasks for i in range(8)
    ]
    # 771*7 + 49*6 = 5691 native-correct slots across exactly820 tasks.
    eligible = [
        s
        for s in slots
        if int(s["task_id"][1:]) < 820
        and s["slot_index"] < (7 if int(s["task_id"][1:]) < 771 else 6)
    ]
    assert len(eligible) == 5691
    jobs = [
        dict(
            key=production.job_key("slot", s["task_id"], r, s["slot_id"]),
            stage="slot",
            task_id=s["task_id"],
            slot_id=s["slot_id"],
            reviewer=r,
        )
        for s in eligible
        for r in (0, 1)
    ]
    jobs += [
        dict(
            key=production.job_key("alignment", t, r),
            stage="alignment",
            task_id=t,
            slot_id=None,
            reviewer=r,
        )
        for t in tasks[:820]
        for r in (0, 1)
    ]
    return dict(
        original_task_ids=tasks,
        slots=slots,
        native_eligible_slot_ids=[s["slot_id"] for s in eligible],
        native_supported_task_ids=tasks[:820],
        jobs=jobs,
        maximum_calls=13022,
        review_policy_id=production.policy_definition()["id"],
    )


def test_full_scope_not_an_affordable_or_supported_training_prefix():
    plan = complete_scope()
    production.fixed_scope(plan)
    changed = copy.deepcopy(plan)
    changed["jobs"].pop()
    with pytest.raises(ValueError, match="complete matrix"):
        production.fixed_scope(changed)
    changed = copy.deepcopy(plan)
    changed["original_task_ids"] = changed["original_task_ids"][:820]
    with pytest.raises(ValueError, match="cover changed"):
        production.fixed_scope(changed)


class Ledger:
    def __init__(self):
        self.calls = 0
        self.halt = None

    def snapshot(self):
        return dict(
            halt=self.halt,
            unacknowledged_unknown_requests=int(self.halt is not None),
            request_partition=dict(consumed=dict(production_review=self.calls)),
        )


class Client:
    def __init__(self, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False


def mocked_controller(tmp_path, monkeypatch, *, fail=False, malformed=False):
    jobs = [
        dict(key=f"slot-{i}", stage="slot", task_id="t", slot_id=f"s{i // 2}", reviewer=i % 2)
        for i in range(4)
    ]
    jobs += [
        dict(key=f"alignment-{r}", stage="alignment", task_id="t", slot_id=None, reviewer=r)
        for r in (0, 1)
    ]
    plan = dict(id="mock", jobs=jobs, concurrency=2, native_supported_task_ids=["t"])
    monkeypatch.setattr(production, "MAXIMUM_CALLS", 6)
    monkeypatch.setattr(production, "SLOT_CALLS", 4)
    monkeypatch.setattr(production, "checked_plan", lambda path: plan)
    monkeypatch.setattr(production, "_key", lambda path: "not-a-credential")
    monkeypatch.setattr(production.httpx, "AsyncClient", Client)
    ledger, invocations, barriers = Ledger(), [], []
    monkeypatch.setattr(production, "ledger_for", lambda p: ledger)

    class Context:
        def __init__(self, *args):
            pass

        def request(self, job):
            return dict(
                model="deepseek-flash",
                max_output_tokens=16384,
                task_bundle_sha256="mock",
                stage=job["stage"],
            )

        def prepare_alignment(self, task):
            assert len(invocations) == 4
            barriers.append("alignment")

    monkeypatch.setattr(production, "ProductionContext", Context)

    def publish(path, value, name="record.json"):
        path.mkdir(parents=True, exist_ok=False)
        (path / name).write_bytes(encode(value))

    monkeypatch.setattr(production, "publish", publish)
    monkeypatch.setattr(production, "status", lambda *args: None)

    async def response(**kwargs):
        index = len(invocations)
        invocations.append(kwargs["episode_id"])
        ledger.calls += 1
        await asyncio.sleep(0)
        if fail and index == 0:
            ledger.halt = "unknown"
            raise RuntimeError("mock unresolved cost")
        return dict(
            finish_reason="length" if malformed else "tool_calls",
            review_format_error=None,
            review_text="{}",
            peak_tariff_upper_bound_microcny=10,
            usage=dict(prompt_tokens=1, completion_tokens=2),
            semantic_review_request_sha256=digest(kwargs["request"]),
        )

    monkeypatch.setattr(production, "request_review", response)

    def good(raw, req):
        return dict(interface_admitted=True, semantic_consistent=True, validation={})

    monkeypatch.setattr(production, "inspect_slot_review", good)
    monkeypatch.setattr(production, "inspect_alignment", good)

    def seal(*args):
        assert len(invocations) == 6
        barriers.append("seal")
        return dict(id="sealed")

    def freeze(*args):
        assert barriers == ["alignment", "seal"]
        barriers.append("freeze")
        return dict(id="material")

    monkeypatch.setattr(production, "complete_seal", seal)
    monkeypatch.setattr(production, "freeze_material", freeze)
    return tmp_path / "run", invocations, barriers


@pytest.mark.parametrize("malformed", [False, True])
def test_one_full_cohort_and_barriers_even_with_normal_unknown_returns(
    tmp_path, monkeypatch, malformed
):
    output, calls, barriers = mocked_controller(tmp_path, monkeypatch, malformed=malformed)
    value = asyncio.run(production.run(output, tmp_path / "unused"))
    assert value["returned"] == value["denominator"] == 6
    assert len(set(calls)) == 6 and all(c.startswith("v8prod:") for c in calls)
    assert barriers == ["alignment", "seal", "freeze"]
    assert value["returned_cost_and_usage"]["cost_microcny"] == 60
    assert not value["training_started"] and not value["automatic_next_cohort"]
    if malformed:
        assert value["stages"]["slot"]["interface_passed"] == 0
    with pytest.raises(ValueError, match="never implicit resend"):
        asyncio.run(production.run(output, tmp_path / "unused"))


def test_financial_unknown_does_not_mint_prefix_population(tmp_path, monkeypatch):
    output, calls, barriers = mocked_controller(tmp_path, monkeypatch, fail=True)
    value = asyncio.run(production.run(output, tmp_path / "unused"))
    assert len(calls) <= 2 and not barriers
    assert value["completion_seal_id"] is None and value["material_result_id"] is None
    assert value["errors"] and not value["training_started"]


def test_missing_funding_prevents_registration_before_any_paid_action(tmp_path):
    with pytest.raises(FileNotFoundError):
        production.register(tmp_path, funding_path=tmp_path / "missing-funding.json")
