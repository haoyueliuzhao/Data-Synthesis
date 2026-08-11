from __future__ import annotations

import json
from pathlib import Path

import pytest

from trusted_synthesis.experiments.counterfactual_finance_fixture import (
    build_finance_counterfactual_case,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_agent_runtime_pilot import AgentPilotArm
from trusted_synthesis.experiments.vtdo_experiment.phase1_explorer_runtime_factorial import (
    _runtime_arm_contracts,
    scripted_tool_policy_hash,
    scripted_tool_sequence,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_explorer_runtime_factorial_runner import (
    FACTORIAL_ROLLOUT_RECORD_VERSION,
    FinanceFactorialRolloutRecord,
    _load_checkpoint,
    factorial_rollout_record_id,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_pro_flash_agent_pilot import (
    EXPECTED_FAMILIES,
    ExplorerArm,
    FinanceProFlashPilotContract,
    PilotStage,
)
from trusted_synthesis.runtime.agent.iterative import (
    AgentLoopPlanContract,
    _make_failure_artifact,
)


def test_scripted_policy_is_public_complete_and_bounded() -> None:
    sequences = {family: scripted_tool_sequence(family) for family in EXPECTED_FAMILIES}

    assert scripted_tool_policy_hash()
    assert all(sequence[0] == "search_archive" for sequence in sequences.values())
    assert all(sequence[-1] == "cross_check_evidence" for sequence in sequences.values())
    assert all(1 <= len(sequence) <= 12 for sequence in sequences.values())
    assert "gold" not in json.dumps(sequences).casefold()
    assert "oracle" not in json.dumps(sequences).casefold()


def test_factorial_runtime_arms_separate_model_and_host_authority() -> None:
    base = FinanceProFlashPilotContract.model_construct(
        maximum_model_tokens_per_rollout=60_000,
        maximum_tool_calls=12,
    )
    arms = _runtime_arm_contracts(base)
    by_arm = {item.arm: item for item in arms}

    assert set(by_arm) == set(AgentPilotArm)
    assert not by_arm[AgentPilotArm.DIRECT_BARE].uses_tool_environment
    assert by_arm[AgentPilotArm.SCRIPTED_TOOL].script_policy_hash == (scripted_tool_policy_hash())
    assert "tool_selection" in by_arm[AgentPilotArm.SCRIPTED_TOOL].host_decision_authorities
    assert "tool_selection" in by_arm[AgentPilotArm.AUTONOMOUS_AGENT].model_decision_authorities
    assert (
        by_arm[AgentPilotArm.SCRIPTED_TOOL].token_budget
        == by_arm[AgentPilotArm.AUTONOMOUS_AGENT].token_budget
    )


def test_plan_contract_rejects_unbounded_surface_output() -> None:
    with pytest.raises(ValueError, match="at most 6"):
        AgentLoopPlanContract(
            plan_summary="compact",
            subgoal_labels=tuple(f"step-{index}" for index in range(7)),
            stop_conditions=("verified",),
        )
    with pytest.raises(ValueError, match="64 characters"):
        AgentLoopPlanContract(
            plan_summary="compact",
            subgoal_labels=("a" * 65, "verify"),
            stop_conditions=("verified",),
        )


def test_iterative_failure_artifact_retains_public_progress() -> None:
    task = build_finance_counterfactual_case(1).task.public
    artifact = _make_failure_artifact(
        task=task,
        mode="autonomous_agent",
        environment_manifest_id="environment:test",
        protocol_profile_hash="protocol-profile:test",
        plan=None,
        decisions=(),
        observations=(),
        telemetry=(),
        failure_message="expected failure",
    )

    assert artifact.task_id == task.task_id
    assert artifact.failure_message == "expected failure"
    assert artifact.artifact_id.startswith("iterative_agent_failure_artifact:")
    assert artifact.protocol_profile_hash == "protocol-profile:test"


def test_factorial_checkpoint_rejects_another_run(tmp_path: Path) -> None:
    values = {
        "run_identity": "run:one",
        "contract_id": "contract:test",
        "stage": PilotStage.CALIBRATION,
        "model_arm": ExplorerArm.FLASH,
        "runtime_arm": AgentPilotArm.AUTONOMOUS_AGENT,
        "task_id": "task:test",
        "task_family": EXPECTED_FAMILIES[0],
        "replicate": 0,
        "attempt_id": "attempt:test",
        "requested_model": "deepseek-v4-flash",
        "model_config_hash": "model:test",
        "status": "failed",
        "trajectory": None,
        "agent_audit": None,
        "observations": (),
        "verification": None,
        "verification_payload": None,
        "state_assignment": None,
        "telemetry": (),
        "failure_artifact": None,
        "error_type": "ExpectedFailure",
        "error_message": "test",
        "schema_version": FACTORIAL_ROLLOUT_RECORD_VERSION,
    }
    provisional = FinanceFactorialRolloutRecord.model_construct(record_id="pending", **values)
    record = FinanceFactorialRolloutRecord(
        record_id=factorial_rollout_record_id(provisional),
        **values,
    )
    path = tmp_path / "factorial.jsonl"
    path.write_text(json.dumps(record.model_dump(mode="json")) + "\n", encoding="utf-8")

    with pytest.raises(ValueError, match="another run"):
        _load_checkpoint(
            path,
            run_identity="run:two",
            task_ids={"task:test"},
            replicas=1,
        )
