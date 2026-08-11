from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from trusted_synthesis.experiments.counterfactual_finance_fixture import (
    build_finance_counterfactual_case,
)
from trusted_synthesis.experiments.vtdo_experiment.multistate import (
    FinanceMultiStateConfig,
    build_finance_task_state_artifact,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_agent_population import (
    compile_finance_agent_case,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_ladder import (
    CandidateTaskContract,
    CapabilityCalibrationThresholds,
    DifficultyComponent,
    DifficultyTier,
    FinanceAgentDifficultyVector,
    FinanceCapabilityLadderContract,
    PublicGuidanceView,
    RuntimeQualificationThresholds,
    RuntimeTaskContract,
    SemanticLadderAudit,
    _public_metadata_view,
    capability_candidate_id,
    capability_candidate_population_hash,
    capability_runtime_context,
    finance_agent_difficulty_vector_hash,
    make_semantic_ladder_audit,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_ladder_runner import (
    CapabilityCellSummary,
    CapabilityRuntimeArm,
    CapabilityStage,
    CapabilityStageReport,
    _capability_gates,
    _qualification_gates,
    _validate_completed_stage_report,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_pro_flash_agent_pilot import (
    EXPECTED_FAMILIES,
    EXPECTED_MODELS,
    ExplorerArm,
)
from trusted_synthesis.runtime.agent import IterativeAgentProtocolProfile


def _vector(*, protocol_score: float, semantic_score: float = 3.0) -> FinanceAgentDifficultyVector:
    values = {
        "semantic": DifficultyComponent(
            score=semantic_score,
            features={"operations": 2.0},
        ),
        "agentic": DifficultyComponent(score=4.0, features={"distractors": 8.0}),
        "protocol": DifficultyComponent(
            score=protocol_score,
            features={"observation_bytes": 2000.0},
        ),
        "capability_score": semantic_score + 4.0,
    }
    provisional = FinanceAgentDifficultyVector.model_construct(
        vector_hash="pending",
        **values,
    )
    return FinanceAgentDifficultyVector(
        vector_hash=finance_agent_difficulty_vector_hash(provisional),
        **values,
    )


def test_capability_score_does_not_absorb_protocol_friction() -> None:
    low_friction = _vector(protocol_score=1.0)
    high_friction = _vector(protocol_score=9.0)

    assert low_friction.capability_score == high_friction.capability_score == 7.0
    assert low_friction.vector_hash != high_friction.vector_hash


def test_candidate_population_hash_survives_json_round_trip() -> None:
    values = {
        "task_id": "task-1",
        "family": "finance.comparison",
        "source_artifact_id": "artifact-1",
        "source_omega_context_id": "context-1",
        "public_corpus_id": "corpus-1",
        "public_corpus_hash": "corpus-hash-1",
        "public_evidence_version_set_hash": "evidence-set-hash-1",
        "gold_evidence_count": 2,
        "public_evidence_count": 8,
        "difficulty": _vector(protocol_score=1.0),
        "deterministic_selection_key": "selection-1",
    }
    provisional = CandidateTaskContract.model_construct(
        candidate_id="pending",
        **values,
    )
    candidate = CandidateTaskContract(
        candidate_id=capability_candidate_id(provisional),
        **values,
    )
    reloaded = CandidateTaskContract.model_validate_json(candidate.model_dump_json())

    before = capability_candidate_population_hash((candidate,))
    after = capability_candidate_population_hash((reloaded,))

    assert before == after


def _semantic_tasks(
    *, semantic_score: float, count_per_family: int
) -> tuple[RuntimeTaskContract, ...]:
    return tuple(
        RuntimeTaskContract.model_construct(
            family=family,
            difficulty=_vector(protocol_score=1.0, semantic_score=semantic_score),
        )
        for family in EXPECTED_FAMILIES
        for _ in range(count_per_family)
    )


def test_semantic_ladder_audit_blocks_guidance_only_frontier() -> None:
    audit = make_semantic_ladder_audit(
        _semantic_tasks(semantic_score=3.0, count_per_family=3),
        _semantic_tasks(semantic_score=3.1, count_per_family=5),
        _semantic_tasks(semantic_score=3.2, count_per_family=2),
    )
    reloaded = SemanticLadderAudit.model_validate_json(audit.model_dump_json())

    assert reloaded.frontier_mean_gain == pytest.approx(0.1)
    assert reloaded.passing_family_count == 0
    assert reloaded.semantic_frontier_ready is False


def test_semantic_ladder_audit_authorizes_broad_family_gain() -> None:
    audit = make_semantic_ladder_audit(
        _semantic_tasks(semantic_score=3.0, count_per_family=3),
        _semantic_tasks(semantic_score=4.2, count_per_family=5),
        _semantic_tasks(semantic_score=4.8, count_per_family=2),
    )

    assert audit.frontier_mean_gain == pytest.approx(1.2)
    assert audit.passing_family_count == 6
    assert audit.semantic_frontier_ready is True


def test_guidance_views_remove_only_registered_public_hints() -> None:
    metadata = {
        "agent_contract_guidance": {
            "evidence_roles": {"earlier": [{"predicate": "revenue"}]},
            "temporal_growth": {"input_role_order": ["earlier", "later"]},
            "general_rules": ["Use machine decimals."],
            "terminal_operation_contract": {"allowed_operator_ids": ["growth"]},
        },
        "unrelated_public_metadata": {"preserved": True},
    }

    full = _public_metadata_view(metadata, PublicGuidanceView.FULL)
    frontier = _public_metadata_view(metadata, PublicGuidanceView.ROLES_HIDDEN)
    hard = _public_metadata_view(metadata, PublicGuidanceView.MINIMAL)

    assert "evidence_roles" in full["agent_contract_guidance"]
    assert "evidence_roles" not in frontier["agent_contract_guidance"]
    assert "temporal_growth" in frontier["agent_contract_guidance"]
    assert set(hard["agent_contract_guidance"]) == {
        "general_rules",
        "terminal_operation_contract",
    }
    assert hard["unrelated_public_metadata"] == {"preserved": True}


def test_runtime_context_freezes_tier_and_low_friction_profile(tmp_path: Path) -> None:
    case = compile_finance_agent_case(build_finance_counterfactual_case(1))
    artifact = build_finance_task_state_artifact(
        case,
        FinanceMultiStateConfig(
            finance_archive_config_path=tmp_path / "unused.json",
            task_count=1,
        ),
    )
    profile = IterativeAgentProtocolProfile(
        initial_plan_mode="implicit_public",
        observation_view="compact",
        contract_repair_token_reserve=100,
        final_answer_token_reserve=200,
    )

    context, manifest = capability_runtime_context(
        artifact,
        DifficultyTier.FRONTIER,
        profile,
    )

    runtime = context.task.public.metadata["capability_ladder_runtime"]
    assert runtime["tier"] == "frontier"
    assert runtime["guidance_view"] == "roles_hidden"
    assert runtime["protocol_profile_hash"] == profile.profile_hash
    assert runtime["tool_environment_manifest_id"] == manifest.manifest_id
    assert context.task.public.program_skeleton is None
    assert context.task.oracle == artifact.omega.task.oracle


def test_every_tier_uses_a_distinct_public_runtime_identity(tmp_path: Path) -> None:
    case = compile_finance_agent_case(build_finance_counterfactual_case(2))
    artifact = build_finance_task_state_artifact(
        case,
        FinanceMultiStateConfig(
            finance_archive_config_path=tmp_path / "unused.json",
            task_count=1,
        ),
    )
    profile = IterativeAgentProtocolProfile(initial_plan_mode="implicit_public")

    contexts = [capability_runtime_context(artifact, tier, profile)[0] for tier in DifficultyTier]

    assert len({item.context_id for item in contexts}) == len(DifficultyTier)
    tiers = {item.task.public.metadata["capability_ladder_runtime"]["tier"] for item in contexts}
    assert len(tiers) == len(DifficultyTier)


def _summary(
    model: ExplorerArm,
    runtime: CapabilityRuntimeArm,
    *,
    attempted: int = 9,
    completed: int = 9,
    valid: int = 9,
    budget_exhaustions: int = 0,
) -> CapabilityCellSummary:
    interactive = runtime != CapabilityRuntimeArm.DIRECT_FIXED_RETRIEVAL
    tool_calls = 27 if interactive else 0
    return CapabilityCellSummary(
        model_arm=model,
        runtime_arm=runtime,
        task_count=3,
        attempted_count=attempted,
        completed_count=completed,
        valid_count=valid,
        answer_correct_count=valid,
        final_answer_emission_count=completed,
        api_call_count=18,
        json_contract_success_count=18,
        contract_repair_count=0,
        host_forced_verification_call_count=0,
        tool_call_count=tool_calls,
        successful_tool_call_count=tool_calls,
        observation_replay_count=completed,
        authority_integrity_count=completed,
        budget_exhaustion_count=budget_exhaustions,
        accepted_state_count=valid,
        mean_state_entropy=0.25,
        mean_decision_trace_diversity=0.5,
        total_model_tokens=1_000,
        estimated_cost_usd=0.1,
        mean_api_latency_ms=100.0,
        failure_counts={},
        verifier_issue_counts={},
    )


def _gate_contract() -> FinanceCapabilityLadderContract:
    return FinanceCapabilityLadderContract.model_construct(
        runtime_qualification_thresholds=RuntimeQualificationThresholds(),
        capability_calibration_thresholds=CapabilityCalibrationThresholds(),
    )


def test_runtime_qualification_gates_are_fail_closed() -> None:
    summaries = tuple(
        _summary(model, runtime)
        for model in ExplorerArm
        for runtime in (
            CapabilityRuntimeArm.SCRIPTED_TOOL,
            CapabilityRuntimeArm.AUTONOMOUS_AGENT,
        )
    )
    discovered = {arm: (EXPECTED_MODELS[arm.value],) for arm in ExplorerArm}

    passing = _qualification_gates(_gate_contract(), summaries, discovered)
    assert all(item.passed for item in passing)

    repaired = (
        summaries[0].model_copy(
            update={
                "api_call_count": 20,
                "json_contract_success_count": 18,
                "contract_repair_count": 2,
            }
        ),
        *summaries[1:],
    )
    repaired_gates = {
        item.gate_id: item for item in _qualification_gates(_gate_contract(), repaired, discovered)
    }
    assert repaired_gates["raw_json_response_contract"].passed is True
    assert repaired_gates["bounded_json_contract_resolution"].passed is True

    damaged = (
        repaired[0],
        repaired[1].model_copy(
            update={
                "budget_exhaustion_count": 1,
                "host_forced_verification_call_count": 2,
            }
        ),
        *repaired[2:],
    )
    failing = _qualification_gates(_gate_contract(), damaged, discovered)
    by_id = {item.gate_id: item for item in failing}
    assert by_id["no_budget_exhaustion"].passed is False
    assert by_id["no_budget_exhaustion"].observed == {"budget_exhaustion_count": 1.0}
    assert by_id["bounded_host_verification_repair"].passed is False


def test_capability_gates_measure_autonomy_not_generic_tool_necessity() -> None:
    summaries = (
        _summary(
            ExplorerArm.PRO,
            CapabilityRuntimeArm.DIRECT_FIXED_RETRIEVAL,
            attempted=10,
            completed=10,
            valid=4,
        ),
        _summary(
            ExplorerArm.PRO,
            CapabilityRuntimeArm.SCRIPTED_TOOL,
            attempted=10,
            completed=10,
            valid=8,
        ),
        _summary(
            ExplorerArm.PRO,
            CapabilityRuntimeArm.AUTONOMOUS_AGENT,
            attempted=10,
            completed=10,
            valid=7,
        ),
        _summary(
            ExplorerArm.FLASH,
            CapabilityRuntimeArm.DIRECT_FIXED_RETRIEVAL,
            attempted=10,
            completed=10,
            valid=4,
        ),
        _summary(
            ExplorerArm.FLASH,
            CapabilityRuntimeArm.SCRIPTED_TOOL,
            attempted=10,
            completed=10,
            valid=6,
        ),
        _summary(
            ExplorerArm.FLASH,
            CapabilityRuntimeArm.AUTONOMOUS_AGENT,
            attempted=10,
            completed=10,
            valid=5,
        ),
    )

    gates = _capability_gates(_gate_contract(), summaries)
    by_id = {item.gate_id: item for item in gates}

    assert all(item.passed for item in gates)
    autonomy = by_id["autonomous_agent_necessity"]
    assert autonomy.observed["maximum_autonomy_gain_vs_fixed_retrieval"] == pytest.approx(0.3)
    assert "tool_necessity" not in by_id


def test_completed_stage_report_resume_is_content_bound(tmp_path: Path) -> None:
    checkpoint = tmp_path / "checkpoint.jsonl"
    rollouts = tmp_path / "rollouts.jsonl"
    checkpoint.write_text('{"record": 1}\n', encoding="utf-8")
    rollouts.write_text('{"record": 1}\n', encoding="utf-8")

    def digest(path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()

    audit = SemanticLadderAudit.model_construct(audit_hash="audit-1")
    contract = FinanceCapabilityLadderContract.model_construct(
        contract_id="contract-1",
        semantic_ladder_audit=audit,
    )
    report = CapabilityStageReport.model_construct(
        contract_id="contract-1",
        run_identity="run-1",
        stage=CapabilityStage.RUNTIME_QUALIFICATION,
        requested_rollout_count=2,
        recorded_rollout_count=2,
        checkpoint_sha256=digest(checkpoint),
        rollout_records_sha256=digest(rollouts),
        semantic_ladder_audit_hash="audit-1",
    )

    _validate_completed_stage_report(
        report,
        contract=contract,
        stage=CapabilityStage.RUNTIME_QUALIFICATION,
        run_identity="run-1",
        expected_rollout_count=2,
        checkpoint_path=checkpoint,
        records_path=rollouts,
    )

    rollouts.write_text('{"record": 2}\n', encoding="utf-8")
    with pytest.raises(ValueError, match="rollout hash changed"):
        _validate_completed_stage_report(
            report,
            contract=contract,
            stage=CapabilityStage.RUNTIME_QUALIFICATION,
            run_identity="run-1",
            expected_rollout_count=2,
            checkpoint_path=checkpoint,
            records_path=rollouts,
        )
