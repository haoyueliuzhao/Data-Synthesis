from __future__ import annotations

from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from trusted_synthesis.core.task.program import (
    InputRefKind,
    OperationNode,
    ProgramInputRef,
    TaskProgram,
    make_program,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_boundary import (
    CapabilityRuntimeArm,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_boundary_analysis import (
    ConfidenceInterval,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_ladder import (
    DifficultyTier,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_sensitive_frontier import (
    CAPABILITY_AXES,
    CAPABILITY_SENSITIVE_FAMILIES,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_multitier_capability_population import (
    _public_contract_metadata,
    finance_operation_execution_contract,
    finance_public_calculation_instruction,
    population_cli_summary,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_multitier_confirmation import (
    FinanceMultiTierFlashReport,
    MultiTierInformationCell,
    _make_support_rules,
    _select_pro_anchor_groups,
    multitier_flash_report_id,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_pro_flash_agent_pilot import (
    ExplorerArm,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_workflow_information_audit import (
    InformationGate,
)


def test_multitier_support_excludes_host_axes_and_recovery_easy() -> None:
    rules = {(item.runtime_arm, item.family): item for item in _make_support_rules()}

    scripted_stopping = rules[
        (
            CapabilityRuntimeArm.SCRIPTED_TOOL,
            "finance.stopping_decision_control",
        )
    ]
    assert scripted_stopping.primary_tiers == ()
    assert set(scripted_stopping.secondary_tiers) == set(DifficultyTier)

    scripted_branching = rules[
        (
            CapabilityRuntimeArm.SCRIPTED_TOOL,
            "finance.branching_operation_plan",
        )
    ]
    assert scripted_branching.primary_tiers == ()
    assert set(scripted_branching.secondary_tiers) == set(DifficultyTier)

    for runtime in (
        CapabilityRuntimeArm.SCRIPTED_TOOL,
        CapabilityRuntimeArm.AUTONOMOUS_AGENT,
    ):
        recovery = rules[(runtime, "finance.recovery_guided_search")]
        assert recovery.primary_tiers == (
            DifficultyTier.FRONTIER,
            DifficultyTier.HARD_CONTROL,
        )
        assert recovery.secondary_tiers == (DifficultyTier.EASY_CONTROL,)


def test_sparse_pro_anchor_selection_is_preregistered_and_balanced() -> None:
    groups = tuple(
        SimpleNamespace(family=family, group_id=f"{family}:group:{index}")
        for family in CAPABILITY_SENSITIVE_FAMILIES
        for index in range(3)
    )
    population = SimpleNamespace(groups=groups)

    first = _select_pro_anchor_groups(population, "frozen-anchor-salt")
    second = _select_pro_anchor_groups(population, "frozen-anchor-salt")

    assert first == second
    assert set(first) == set(CAPABILITY_SENSITIVE_FAMILIES)
    assert len(set(first.values())) == len(CAPABILITY_SENSITIVE_FAMILIES)


def test_population_cli_summary_uses_frozen_audits() -> None:
    population = SimpleNamespace(
        population_id="population:v25.12",
        groups=tuple(range(21)),
        tasks=tuple(range(63)),
        audit=SimpleNamespace(
            static_record_count=189,
            multi_tier_population_ready=True,
        ),
        public_contract_audit=SimpleNamespace(passed_record_count=189),
        excluded_evidence_version_ids=tuple(range(470)),
    )

    assert population_cli_summary(population) == {
        "population_id": "population:v25.12",
        "group_count": 21,
        "task_count": 63,
        "static_contract_count": 189,
        "static_contract_pass_count": 189,
        "excluded_evidence_version_count": 470,
        "ready": True,
    }


def _formula_evidence(count: int) -> tuple[SimpleNamespace, ...]:
    return tuple(
        SimpleNamespace(
            evidence_id=f"evidence:test:{index}",
            subject=SimpleNamespace(name="Example Corp"),
            predicate="revenue",
            temporal_context=SimpleNamespace(
                label=f"FY20{20 + index}",
                basis="fiscal_year",
                frequency="annual",
            ),
            source=SimpleNamespace(source_id="official_test_source"),
            definition=SimpleNamespace(definition_id="revenue.gaap.v1"),
            payload=SimpleNamespace(unit="USD", currency="USD"),
        )
        for index in range(count)
    )


def _ref(ref_id: str, *, operation: bool = False) -> ProgramInputRef:
    return ProgramInputRef(
        kind=InputRefKind.OPERATION if operation else InputRefKind.EVIDENCE,
        ref_id=ref_id,
        selector="value" if operation else None,
    )


def _node(
    node_id: str,
    operator: str,
    refs: tuple[ProgramInputRef, ...],
    *,
    output_schema: str = "scalar",
) -> OperationNode:
    return OperationNode(
        node_id=node_id,
        operator_id=operator,
        input_refs=refs,
        output_schema=output_schema,
        verifier_id=f"{operator}.test.v1",
        dependencies=tuple(ref.ref_id for ref in refs if ref.kind == InputRefKind.OPERATION),
    )


def _calculation_program() -> TaskProgram:
    nodes = (
        _node("d1", "difference", (_ref("evidence:test:0"), _ref("evidence:test:1"))),
        _node("r1", "ratio", (_ref("d1", operation=True), _ref("evidence:test:0"))),
        _node("d2", "difference", (_ref("evidence:test:1"), _ref("evidence:test:2"))),
        _node("r2", "ratio", (_ref("d2", operation=True), _ref("evidence:test:1"))),
        _node("result", "difference", (_ref("r1", operation=True), _ref("r2", operation=True))),
    )
    return make_program(nodes, "result")


def _comparison_program() -> TaskProgram:
    nodes = (
        _node("d1", "difference", (_ref("evidence:test:0"), _ref("evidence:test:1"))),
        _node("d2", "difference", (_ref("evidence:test:1"), _ref("evidence:test:2"))),
        _node(
            "result",
            "compare",
            (_ref("d1", operation=True), _ref("d2", operation=True)),
            output_schema="comparison",
        ),
    )
    return make_program(nodes, "result")


def test_public_finance_calculation_contract_exposes_exact_signed_formula() -> None:
    gold = _formula_evidence(3)

    program = _calculation_program()
    contract = finance_operation_execution_contract(
        family="finance.calculation_chain",
        tier=DifficultyTier.FRONTIER,
        gold=gold,
        program=program,
    )

    expressions = {item["step_id"]: item["expression"] for item in contract["steps"]}
    assert expressions["d1"] == "v2 - v1"
    assert expressions["r1"] == "d1 / v1"
    assert expressions["d2"] == "v3 - v2"
    assert expressions["r2"] == "d2 / v2"
    assert contract["final_output_rule"] == "value = result"
    assert contract["source_program_hash"] == program.program_hash
    assert "100 *" not in expressions["r1"]


def test_public_comparison_contract_constrains_label_and_absolute_gap() -> None:
    gold = _formula_evidence(3)
    program = _comparison_program()
    metadata = _public_contract_metadata(
        family="finance.definition_reconciliation",
        tier=DifficultyTier.FRONTIER,
        gold=gold,
        program=program,
        answer_projection={"d1": "first interval", "d2": "second interval"},
        recovery_branches=(),
    )
    guidance = metadata["agent_contract_guidance"]

    assert guidance["answer_field_constraints"] == {
        "higher_ref": {"allowed_values": ("first interval", "second interval", None)},
        "difference": {"numeric_minimum": "0"},
    }
    assert guidance["operation_execution_contract"]["final_output_rule"] == (
        "higher_ref plus absolute difference"
    )
    assert guidance["answer_observation_constraints"] == {
        "source_tool_id": "calculator",
        "source_operation_role": "terminal",
        "source_result_selector": ("result", "output"),
        "field_selectors": {"difference": ("difference",)},
        "exact_fields": ("difference",),
    }
    instruction = finance_public_calculation_instruction(
        "Compare the intervals.",
        family="finance.definition_reconciliation",
        tier=DifficultyTier.FRONTIER,
        gold=gold,
        program=program,
    )
    assert "exact signed arithmetic step disclosed by the Host" in instruction
    assert "higher_ref plus absolute difference" in instruction


def test_formula_contract_separates_workflow_tier_from_program_tier() -> None:
    program = make_program(
        (
            _node(
                "result",
                "compare",
                (_ref("evidence:test:0"), _ref("evidence:test:1")),
                output_schema="comparison",
            ),
        ),
        "result",
    )
    contract = finance_operation_execution_contract(
        family="finance.branching_operation_plan",
        tier=DifficultyTier.HARD_CONTROL,
        gold=_formula_evidence(2),
        program=program,
    )

    assert contract["observed_workflow_tier"] == "hard_control"
    assert contract["program_semantic_tier"] == "easy_control"
    assert contract["final_output_rule"] == "higher_ref plus absolute difference"
    assert contract["steps"][-1]["inputs"] == ("v1", "v2")
    assert contract["variables"][0]["selection_match"]["collection_selector"] == ("facts",)


def _flash_report_values(*, information_passed: bool) -> dict[str, object]:
    interval = ConfidenceInterval(lower=0.0, point=0.0, upper=0.0)
    gates = tuple(
        InformationGate(
            gate_id=f"gate:{index}",
            observed=0.0,
            requirement=">=0",
            passed=information_passed,
        )
        for index in range(9)
    )
    cells = tuple(
        MultiTierInformationCell(
            model_arm=ExplorerArm.FLASH,
            runtime_arm=runtime,
            primary_families=("finance.calculation_chain",),
            primary_tiers_by_family={"finance.calculation_chain": tuple(DifficultyTier)},
            task_count=1,
            rollout_count=5,
            mean_success_rate=0.0,
            boundary_task_fraction=0.0,
            residual_information_eigenvalues=tuple(0.0 for _ in CAPABILITY_AXES),
            residual_numerical_rank=0,
            residual_effective_rank=0.0,
            residual_condition_number=1.0,
            general_factor_fraction=1.0,
            marginal_axis_information={axis: 0.0 for axis in CAPABILITY_AXES},
            marginal_axis_intervals={axis: interval for axis in CAPABILITY_AXES},
            informative_axis_count=0,
            family_information_share={family: 0.0 for family in CAPABILITY_SENSITIVE_FAMILIES},
            group_information_share={"group:test": 0.0},
            maximum_family_information_share=0.0,
            maximum_group_information_share=0.0,
            primary_aligned_family_count=1,
            gates=gates,
            passed=information_passed,
        )
        for runtime in (
            CapabilityRuntimeArm.SCRIPTED_TOOL,
            CapabilityRuntimeArm.AUTONOMOUS_AGENT,
        )
    )
    return {
        "contract_id": "contract:v25.12",
        "population_id": "population:v25.12",
        "requested_rollout_count": 630,
        "recorded_rollout_count": 630,
        "primary_rollout_count": 540,
        "secondary_diagnostic_rollout_count": 90,
        "information_cells": cells,
        "technical_resolution_rate": 1.0,
        "technical_status": "passed",
        "all_information_cells_ready": information_passed,
        "flash_information_ready": information_passed,
        "failure_codes": (() if information_passed else ("information:scripted_tool",)),
        "outcome_set_hash": "outcomes:v25.12",
        "api_call_count": 630,
        "total_model_tokens": 63_000,
        "estimated_cost_usd": 1.0,
        "pro_stage_authorized": information_passed,
        "next_permitted_stage": (
            "pro_sparse_anchor" if information_passed else "flash_support_or_task_redesign_only"
        ),
    }


def test_flash_information_failure_blocks_pro_stage() -> None:
    values = _flash_report_values(information_passed=False)
    provisional = FinanceMultiTierFlashReport.model_construct(
        report_id="pending",
        **values,
    )
    report = FinanceMultiTierFlashReport(
        report_id=multitier_flash_report_id(provisional),
        **values,
    )

    assert report.pro_stage_authorized is False
    assert report.next_permitted_stage == "flash_support_or_task_redesign_only"

    invalid = dict(values)
    invalid["pro_stage_authorized"] = True
    with pytest.raises(ValidationError, match="Flash stage transition is inconsistent"):
        FinanceMultiTierFlashReport(report_id="forged", **invalid)
