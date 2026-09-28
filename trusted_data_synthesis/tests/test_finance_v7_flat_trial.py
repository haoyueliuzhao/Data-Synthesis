"""R6 controller selection controls, without API, credentials, ledger, or GPU."""

import asyncio

import pytest

from trusted_synthesis.finance_research import v7_review_flat_trial as current
from trusted_synthesis.finance_research import v7_review_mask_trial as shared
from trusted_synthesis.finance_research.contracts import digest


def test_r6_uses_new_plan_and_semantic_inspector_with_disjoint_episode_prefix(
    monkeypatch, tmp_path
):
    from trusted_synthesis.finance_research.v7_flat_review import inspect_slot_review

    seen = {}

    async def fake_run(output, env_file, **kwargs):
        seen.update(kwargs)
        return {"sent": 0}

    monkeypatch.setattr(current, "fixed_run", fake_run)
    assert asyncio.run(current.run(tmp_path, tmp_path / "unused.env")) == {"sent": 0}
    assert seen["plan_loader"] is current.checked_plan
    assert seen["review_inspector"] is inspect_slot_review
    assert seen["episode_prefix"] == "v7flat6:"


def test_parameterized_fixed_runner_still_refuses_expansion_before_ledger(monkeypatch, tmp_path):
    def never(*args, **kwargs):
        pytest.fail("invalid denominator must not open credentials or ledger")

    monkeypatch.setattr(shared, "ledger_for", never)
    with pytest.raises(ValueError, match="exactly twelve"):
        asyncio.run(
            shared.run(
                tmp_path,
                tmp_path / "unused.env",
                plan_loader=lambda _: {"maximum_calls": 13, "jobs": [{}] * 13},
            )
        )


@pytest.mark.parametrize("wire,count", [("v6_slot_review.v5", 12), ("v6_slot_review.v6", 13)])
def test_r6_plan_refuses_old_wire_or_changed_denominator(monkeypatch, tmp_path, wire, count):
    plan = dict(
        runtime_binding={"source": "test"},
        wire_protocol=wire,
        maximum_calls=count,
        jobs=[{}] * count,
    )
    plan["id"] = digest(plan)
    monkeypatch.setattr(current, "read_json", lambda _: plan)
    monkeypatch.setattr(current, "runtime_binding", lambda: {"source": "test"})
    with pytest.raises(ValueError, match="registered wire"):
        current.checked_plan(tmp_path)
