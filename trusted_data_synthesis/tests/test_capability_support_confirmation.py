from __future__ import annotations

from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_boundary import (
    CapabilityRuntimeArm,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_ladder import (
    DifficultyTier,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_support_confirmation import (
    GROUPS_PER_FAMILY,
    CapabilitySupportRule,
    _confirmation_manifest_payload,
    _confirmation_tier_schedule,
    _runtime_metrics,
    _select_anchor_tier,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_multitier_runtime_resolution import (
    FailureLayer,
)


def test_support_anchor_selection_prefers_boundary_then_harder_tier() -> None:
    rates = {
        DifficultyTier.EASY_CONTROL: 1.0,
        DifficultyTier.FRONTIER: 0.5,
        DifficultyTier.HARD_CONTROL: 0.0,
    }
    assert _select_anchor_tier(rates) == DifficultyTier.FRONTIER

    tied = {
        DifficultyTier.EASY_CONTROL: 0.5,
        DifficultyTier.FRONTIER: 0.5,
        DifficultyTier.HARD_CONTROL: 1.0,
    }
    assert _select_anchor_tier(tied) == DifficultyTier.FRONTIER


@pytest.mark.parametrize("anchor", tuple(DifficultyTier))
def test_support_confirmation_schedule_freezes_five_groups(
    anchor: DifficultyTier,
) -> None:
    schedule = _confirmation_tier_schedule(anchor)
    assert len(schedule) == GROUPS_PER_FAMILY
    assert schedule.count(anchor) == 3
    assert all(item in DifficultyTier for item in schedule)


def test_support_rule_excludes_host_controlled_axis() -> None:
    rule = CapabilitySupportRule(
        runtime_arm=CapabilityRuntimeArm.SCRIPTED_TOOL,
        family="finance.branching_operation_plan",
        primary_axis="planning",
        runtime_responsibility=0.0,
        development_attempts_by_tier={tier: 2 for tier in DifficultyTier},
        development_success_rates_by_tier={tier: 0.5 for tier in DifficultyTier},
        development_status="host_controlled",
        anchor_tier=None,
        confirmation_tier_schedule=(),
        rationale="Planning is delegated to the scripted Host.",
    )
    assert rule.confirmation_tier_schedule == ()

    with pytest.raises(ValidationError, match="host-controlled"):
        CapabilitySupportRule(
            **rule.model_dump(exclude={"anchor_tier", "confirmation_tier_schedule"}),
            anchor_tier=DifficultyTier.FRONTIER,
            confirmation_tier_schedule=_confirmation_tier_schedule(DifficultyTier.FRONTIER),
        )


def test_support_rule_requires_complete_five_group_schedule() -> None:
    payload = {
        "runtime_arm": CapabilityRuntimeArm.AUTONOMOUS_AGENT,
        "family": "finance.definition_reconciliation",
        "primary_axis": "reconciliation",
        "runtime_responsibility": 1.0,
        "development_attempts_by_tier": {tier: 2 for tier in DifficultyTier},
        "development_success_rates_by_tier": {
            DifficultyTier.EASY_CONTROL: 1.0,
            DifficultyTier.FRONTIER: 0.5,
            DifficultyTier.HARD_CONTROL: 0.0,
        },
        "development_status": "mixed",
        "anchor_tier": DifficultyTier.FRONTIER,
        "rationale": "Fresh Confirmation uses a frozen boundary schedule.",
    }
    with pytest.raises(ValidationError, match="group schedule"):
        CapabilitySupportRule(
            **payload,
            confirmation_tier_schedule=(DifficultyTier.FRONTIER,),
        )
    valid = CapabilitySupportRule(
        **payload,
        confirmation_tier_schedule=_confirmation_tier_schedule(DifficultyTier.FRONTIER),
    )
    assert len(valid.confirmation_tier_schedule) == GROUPS_PER_FAMILY


def test_runtime_metrics_allow_preregistered_sparse_tier_support() -> None:
    terminals = tuple(
        SimpleNamespace(
            primary_failure_layer=FailureLayer.L6_SUCCESS,
            runtime_eligible_for_capability_denominator=True,
            tier=tier,
            api_transport_resolved=True,
            bounded_json_resolution_success=True,
            observation_replay_success=True,
            authority_integrity_success=True,
            terminal_resolved=True,
            failure_attributed=False,
            prompt_pathology=False,
            valid_success=True,
            api_call_count=1,
            total_model_tokens=10,
            estimated_cost_usd=0.001,
        )
        for tier in (DifficultyTier.FRONTIER, DifficultyTier.HARD_CONTROL)
    )

    metrics = _runtime_metrics(terminals)  # type: ignore[arg-type]

    assert metrics.observed_tiers == (
        DifficultyTier.FRONTIER,
        DifficultyTier.HARD_CONTROL,
    )
    assert set(metrics.tier_valid_success_given_runtime_eligible) == {
        DifficultyTier.FRONTIER,
        DifficultyTier.HARD_CONTROL,
    }
    assert DifficultyTier.EASY_CONTROL not in (metrics.tier_valid_success_given_runtime_eligible)


def test_confirmation_manifest_normalizes_discovered_models_for_replay() -> None:
    payload = _confirmation_manifest_payload(
        contract_id="contract:test",
        discovered_models=("deepseek-v4-flash", "deepseek-v4-pro"),
        records_sha256="a" * 64,
        outcomes_sha256="b" * 64,
        terminal_outcomes_sha256="c" * 64,
        report_id="report:test",
        report_sha256="d" * 64,
    )

    assert payload["discovered_models"] == [
        "deepseek-v4-flash",
        "deepseek-v4-pro",
    ]
