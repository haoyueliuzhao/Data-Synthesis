"""Collector phase/identity controls; no real HTTP, credentials, or model calls."""

import asyncio
from types import SimpleNamespace

import pytest

from trusted_synthesis.finance_research import probe_collection as c
from trusted_synthesis.finance_research.contracts import digest


def test_missing_scope_choice_cannot_register_paid_generation(tmp_path):
    with pytest.raises(ValueError, match="explicit choice"):
        c.register(tmp_path / "new-run", coverage_acknowledgement="")


def test_conditional_scope_cannot_be_disguised_as_full_1000(tmp_path):
    with pytest.raises(ValueError, match="full_original_1000"):
        c.register(tmp_path / "new-run", coverage_acknowledgement="conditional_subset")


def test_incomplete_slot_is_never_resampled(tmp_path, monkeypatch):
    slot = {
        "slot_id": "finqa_probe_slot:fixture",
        "task_id": "fixture",
        "slot_index": 0,
        "purpose": "train",
    }
    plan = {"inventory": {"slots": [slot], "registered_slot_denominator": 24}}
    c.publish(c.slot_directory(tmp_path, slot) / "started", {"attempt": 1})
    monkeypatch.setattr(c, "checked_plan", lambda _: plan)
    monkeypatch.setattr(
        c,
        "ledger_for",
        lambda *_: SimpleNamespace(unsettled=lambda: [], snapshot=lambda: {"halt": None}),
    )
    monkeypatch.setattr(c, "_key", lambda _: (_ for _ in ()).throw(AssertionError("read key")))
    asyncio.run(c.collect(tmp_path))
    result = c.read_json(tmp_path / "status.json")
    assert result["phase"] == "BLOCKED_RECOVERY"
    assert result["completed"] == 0 and result["denominator"] == 24
    assert result["automatic_retry"] is False


def test_private_qualification_rejects_partial_generation_seal(tmp_path, monkeypatch):
    plan = {"id": "fixture-plan", "inventory": {"registered_slot_denominator": 24}}
    seal = {
        "protocol_id": "fixture-plan",
        "complete": True,
        "denominator": 24,
        "slots": [{"slot": {"slot_id": "only-one"}}],
    }
    seal["id"] = digest(seal)
    c.publish(tmp_path / "generation_seal", seal)
    monkeypatch.setattr(c, "checked_plan", lambda _: plan)
    monkeypatch.setattr(
        c, "ledger_for", lambda *_: (_ for _ in ()).throw(AssertionError("opened ledger"))
    )
    monkeypatch.setattr(
        c,
        "_qualification_worker_init",
        lambda *_: (_ for _ in ()).throw(AssertionError("read references")),
    )
    with pytest.raises(ValueError, match="all registered"):
        c.qualify(tmp_path)


def test_unknown_budget_blocks_new_slots_before_key_load(tmp_path, monkeypatch):
    plan = {"inventory": {"slots": [], "registered_slot_denominator": 24}}
    monkeypatch.setattr(c, "checked_plan", lambda _: plan)
    monkeypatch.setattr(
        c,
        "ledger_for",
        lambda *_: SimpleNamespace(
            unsettled=lambda: [{"state": "UNKNOWN"}], snapshot=lambda: {"halt": {"unknown": True}}
        ),
    )
    monkeypatch.setattr(c, "_key", lambda _: (_ for _ in ()).throw(AssertionError("read key")))
    asyncio.run(c.collect(tmp_path))
    result = c.read_json(tmp_path / "status.json")
    assert result["phase"] == "BLOCKED_UNSETTLED" and result["denominator"] == 24


def test_conditional_policy_does_not_reuse_original_population_dose():
    from trusted_synthesis.finance_research.training_policy import (
        conditional_training_interface_policy,
    )

    policy = conditional_training_interface_policy({"scoped_task_count": 3, "scope_id": "fixture"})
    assert policy["probe"]["sessions"] == 24
    assert policy["inventory"]["mu"] == "1/3"
    assert policy["original_1000_training_admitted"] is False
    proposal = policy["training_comparison_proposal_not_run_registration"]
    assert proposal["total_steps_per_final_model"] is None
    assert policy["training_authorized"] is False
