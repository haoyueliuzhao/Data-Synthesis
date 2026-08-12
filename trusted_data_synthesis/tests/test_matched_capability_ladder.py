from __future__ import annotations

import copy

import pytest
from pydantic import ValidationError

from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_boundary import (
    CapabilityRuntimeArm,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_ladder import (
    DifficultyTier,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_sensitive_frontier import (
    CAPABILITY_SENSITIVE_FAMILIES,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_matched_capability_ladder import (
    matched_group_invariant_failures,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_matched_tier_localization import (
    MATCHED_ROLLOUT_COUNT,
    WORKFLOW_RUNTIME_ARMS,
    MatchedLocalizationThresholds,
    MatchedTierCell,
    _select_shared_tier,
    _wilson_interval,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_pro_flash_agent_pilot import (
    ExplorerArm,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_public_contract_satisfiability import (
    PublicContractCheck,
    PublicContractSatisfiabilityRecord,
    make_public_contract_audit,
    public_contract_record_id,
)


def _matched_variant(tier: str) -> dict[str, object]:
    tier_index = {
        "easy_control": 1,
        "frontier": 2,
        "hard_control": 3,
    }[tier]
    gold = [
        {
            "evidence_id": "evidence:earlier",
            "evidence_version_id": "evidence-version:earlier",
            "subject": {"subject_id": "entity:alpha"},
            "predicate": "revenue",
            "temporal_context": {"label": "FY2023"},
            "definition": {"definition_id": "metric:revenue"},
            "source": {"source_id": "official-filing"},
        },
        {
            "evidence_id": "evidence:later",
            "evidence_version_id": "evidence-version:later",
            "subject": {"subject_id": "entity:alpha"},
            "predicate": "revenue",
            "temporal_context": {"label": "FY2024"},
            "definition": {"definition_id": "metric:revenue"},
            "source": {"source_id": "official-filing"},
        },
    ]
    distractors = [
        {
            "evidence_id": f"evidence:distractor:{index}",
            "evidence_version_id": f"evidence-version:distractor:{index}",
        }
        for index in range(1, (tier_index - 1) * 3 + 1)
    ]
    strict = {
        "public_source_count": tier_index,
        "query_decomposition_rounds": tier_index,
        "reconciliation_count": tier_index,
        "required_verification_count": tier_index,
        "required_recovery_count": tier_index - 1,
        "distractor_branch_count": (tier_index - 1) * 3,
        "tool_type_count": tier_index + 2,
        "minimal_tool_calls": tier_index * 3,
        "stopping_condition_count": tier_index,
    }
    fixed = {
        "gold_evidence_count": 2,
        "gold_subject_count": 1,
        "operation_count": 1,
        "operation_dag_depth": 1,
        "operation_branch_count": 1,
        "evidence_hop_count": 2,
        "minimum_evidence_selection_calls": 2,
    }
    return {
        "family": "finance.calculation_chain",
        "tier": tier,
        "evidence_bundle": {"evidence": gold},
        "public_corpus": {"evidence": [*gold, *distractors]},
        "task": {
            "public": {"answer_schema": {"type": "numeric", "required_fields": ["value"]}},
            "oracle": {
                "task_program": {
                    "nodes": [
                        {
                            "node_id": "result",
                            "operator_id": "difference",
                            "input_refs": [
                                {
                                    "kind": "evidence",
                                    "ref_id": "evidence:earlier",
                                    "selector": None,
                                    "role_id": "earlier",
                                },
                                {
                                    "kind": "evidence",
                                    "ref_id": "evidence:later",
                                    "selector": None,
                                    "role_id": "later",
                                },
                            ],
                            "parameters": {},
                        }
                    ],
                    "output_node_id": "result",
                }
            },
        },
        "answer_projection": {},
        "projected_expected_output": {"value": "10"},
        "structure": {
            **fixed,
            **strict,
            "single_retrieval_solvable": tier == "easy_control",
        },
        "verification": {"passed": True},
    }


def test_matched_ladder_accepts_only_workflow_difficulty_changes() -> None:
    variants = tuple(
        _matched_variant(tier)
        for tier in ("easy_control", "frontier", "hard_control")
    )

    assert matched_group_invariant_failures(variants) == ()


def test_matched_ladder_rejects_answer_and_corpus_mutations() -> None:
    variants = [
        _matched_variant(tier)
        for tier in ("easy_control", "frontier", "hard_control")
    ]
    answer_mutation = copy.deepcopy(variants)
    answer_mutation[-1]["projected_expected_output"] = {"value": "11"}
    assert {
        "core_semantics",
        "projected_output",
    } <= set(matched_group_invariant_failures(answer_mutation))

    corpus_mutation = copy.deepcopy(variants)
    corpus_mutation[1]["public_corpus"] = copy.deepcopy(
        corpus_mutation[0]["public_corpus"]
    )
    assert "public_corpus_nesting" in matched_group_invariant_failures(
        corpus_mutation
    )


def test_matched_ladder_rejects_program_and_fixed_dimension_mutations() -> None:
    variants = [
        _matched_variant(tier)
        for tier in ("easy_control", "frontier", "hard_control")
    ]
    variants[1]["task"]["oracle"]["task_program"]["nodes"][0]["operator_id"] = "ratio"
    variants[2]["structure"]["gold_evidence_count"] = 3

    failures = set(matched_group_invariant_failures(variants))
    assert "operation_program" in failures
    assert "core_semantics" in failures
    assert "fixed:gold_evidence_count" in failures


def _passing_record(
    *,
    family: str,
    task_index: int,
    runtime: str,
) -> PublicContractSatisfiabilityRecord:
    check_ids = (
        "compiler_prompt_verifier_consistency",
        "tool_precondition_closure",
        "public_valid_witness",
        "minimum_call_accounting",
    )
    values = {
        "task_artifact_id": f"task:{family}:{task_index}",
        "task_id": f"public-task:{family}:{task_index}",
        "family": family,
        "runtime_arm": runtime,
        "checks": tuple(
            PublicContractCheck(check_id=check_id, passed=True, details={})
            for check_id in check_ids
        ),
        "passed": True,
    }
    provisional = PublicContractSatisfiabilityRecord.model_construct(
        record_id="pending",
        **values,
    )
    return PublicContractSatisfiabilityRecord(
        record_id=public_contract_record_id(provisional),
        **values,
    )


def test_public_contract_audit_scales_to_63_balanced_tasks() -> None:
    runtimes = (
        "direct_fixed_retrieval",
        "scripted_tool",
        "autonomous_agent",
    )
    records = tuple(
        _passing_record(
            family=family,
            task_index=task_index,
            runtime=runtime,
        )
        for family in CAPABILITY_SENSITIVE_FAMILIES
        for task_index in range(9)
        for runtime in runtimes
    )

    audit = make_public_contract_audit(
        population_id="population:matched",
        records=records,
    )

    assert len(audit.records) == 189
    assert audit.passed_record_count == 189
    assert audit.all_public_contracts_satisfiable is True


def _tier_cell(
    *,
    model: ExplorerArm,
    tier: DifficultyTier,
    group_successes: tuple[int, int, int],
) -> MatchedTierCell:
    success_count = sum(group_successes)
    group_rates = {
        f"group:{index}": successes / 5
        for index, successes in enumerate(group_successes)
    }
    return MatchedTierCell(
        model_arm=model,
        runtime_arm=CapabilityRuntimeArm.SCRIPTED_TOOL,
        family="finance.calculation_chain",
        tier=tier,
        attempted_count=15,
        technical_resolution_count=15,
        bounded_json_resolution_count=15,
        observation_replay_count=15,
        authority_integrity_count=15,
        semantic_success_count=success_count,
        valid_success_count=success_count,
        semantic_success_rate=success_count / 15,
        semantic_success_interval=_wilson_interval(success_count, 15),
        group_success_rates=group_rates,
        group_rate_variance=__import__("statistics").pvariance(group_rates.values()),
        budget_exhaustion_count=0,
        runtime_infrastructure_failure_count=0,
        api_call_count=15,
        total_model_tokens=1_500,
        estimated_cost_usd=0.15,
    )


def test_matched_selection_uses_one_shared_tier_for_both_models() -> None:
    cells = {}
    values = {
        DifficultyTier.EASY_CONTROL: {
            ExplorerArm.PRO: (4, 4, 4),
            ExplorerArm.FLASH: (3, 3, 3),
        },
        DifficultyTier.FRONTIER: {
            ExplorerArm.PRO: (5, 5, 5),
            ExplorerArm.FLASH: (5, 5, 5),
        },
        DifficultyTier.HARD_CONTROL: {
            ExplorerArm.PRO: (0, 0, 0),
            ExplorerArm.FLASH: (0, 0, 0),
        },
    }
    for tier, models in values.items():
        for model, group_successes in models.items():
            cell = _tier_cell(
                model=model,
                tier=tier,
                group_successes=group_successes,
            )
            cells[
                (
                    model,
                    CapabilityRuntimeArm.SCRIPTED_TOOL,
                    "finance.calculation_chain",
                    tier,
                )
            ] = cell

    selection = _select_shared_tier(
        CapabilityRuntimeArm.SCRIPTED_TOOL,
        "finance.calculation_chain",
        cells,
        MatchedLocalizationThresholds(),
    )

    assert selection.selected_tier == DifficultyTier.EASY_CONTROL
    assert selection.selected_tier_shared_by_models is True
    assert selection.informative_group_counts[DifficultyTier.EASY_CONTROL] == 3


def test_matched_selection_rejects_aggregate_boundary_without_group_support() -> None:
    cells = {}
    for tier in DifficultyTier:
        for model in ExplorerArm:
            group_successes = (
                (5, 0, 0)
                if tier == DifficultyTier.EASY_CONTROL
                else (0, 0, 0)
            )
            cell = _tier_cell(
                model=model,
                tier=tier,
                group_successes=group_successes,
            )
            cells[
                (
                    model,
                    CapabilityRuntimeArm.SCRIPTED_TOOL,
                    "finance.calculation_chain",
                    tier,
                )
            ] = cell

    selection = _select_shared_tier(
        CapabilityRuntimeArm.SCRIPTED_TOOL,
        "finance.calculation_chain",
        cells,
        MatchedLocalizationThresholds(),
    )

    assert selection.selected_tier is None
    assert "insufficient_ladder_group_support" in selection.failure_reasons


def test_matched_localization_excludes_direct_from_boundary_selection() -> None:
    assert WORKFLOW_RUNTIME_ARMS == (
        CapabilityRuntimeArm.SCRIPTED_TOOL,
        CapabilityRuntimeArm.AUTONOMOUS_AGENT,
    )
    assert MATCHED_ROLLOUT_COUNT == 1_260

    with pytest.raises(ValidationError, match="workflow Runtime"):
        MatchedLocalizationThresholds(
            minimum_workflow_boundary_families={
                CapabilityRuntimeArm.DIRECT_FIXED_RETRIEVAL: 3,
                CapabilityRuntimeArm.SCRIPTED_TOOL: 3,
            }
        )
