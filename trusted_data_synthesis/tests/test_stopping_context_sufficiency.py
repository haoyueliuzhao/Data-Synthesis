from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest
from pydantic import ValidationError

from trusted_synthesis.domains.finance.capability_submechanism_runtime import (
    FINANCE_STOPPING_SHAPE_DECISION_V7_VERSION,
    FinanceStoppingMeasurementContext,
    FinanceStoppingObservedEvidenceState,
    FinanceStoppingObservedRecord,
    FinanceStoppingPublicRelationState,
    FinanceStoppingResolutionAction,
    FinanceStoppingShapeDecisionContract,
    FinanceStoppingTemporalIdentity,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_stopping_context_sufficiency import (  # noqa: E501
    ACTION_FUNCTION_BY_TOOL,
    CONTEXT_SUFFICIENCY_CONTRACT_KIND,
    SHARED_RESOLUTION_POLICY,
    _action_descriptions_are_symmetric,
    _artifact_id,
    _lexical_context_action_overlap,
    _public_action_rows,
    _public_relation_payload,
    _publicly_applicable_action_labels,
    _single_context_counterfactual_ready,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_stopping_context_sufficiency_decision import (  # noqa: E501
    ContextSufficiencyScientificDecision,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_stopping_context_sufficiency_runner import (  # noqa: E501
    _contextual_action_correct,
    _paired_branch_balanced_bootstrap_lcb,
)


def _record() -> FinanceStoppingObservedRecord:
    return FinanceStoppingObservedRecord(
        subject_alias="issuer:alpha",
        metric_alias="revenue",
        temporal_identity=FinanceStoppingTemporalIdentity(
            label="FY2024",
            observed_at="2024-12-31",
            valid_to="2024-12-31",
        ),
        source_id="official_filing",
        definition_id="definition:revenue",
        measurement_context=FinanceStoppingMeasurementContext(unit="million USD", currency="USD"),
    )


def _actions() -> tuple[FinanceStoppingResolutionAction, ...]:
    return tuple(
        FinanceStoppingResolutionAction(tool_id=tool_id, applicable_when=description)
        for tool_id, description in ACTION_FUNCTION_BY_TOOL.items()
    )


def _decision(condition: str) -> FinanceStoppingShapeDecisionContract:
    required = _record()
    if condition == "period":
        observed = required.model_copy(
            update={
                "temporal_identity": required.temporal_identity.model_copy(
                    update={"label": "FY2023", "observed_at": "2023-12-31"}
                )
            }
        )
        relation = FinanceStoppingPublicRelationState(
            observation_identity_relation="unresolved",
            meaning_compatibility_relation="aligned",
            measurement_compatibility_relation="aligned",
            authority_relation="aligned",
        )
        dimension = "temporal_alignment"
    else:
        observed = required.model_copy(update={"definition_id": "definition:alternate"})
        relation = FinanceStoppingPublicRelationState(
            observation_identity_relation="aligned",
            meaning_compatibility_relation="unresolved",
            measurement_compatibility_relation="aligned",
            authority_relation="aligned",
        )
        dimension = "source_definition_compatibility"
    return FinanceStoppingShapeDecisionContract(
        schema_version=FINANCE_STOPPING_SHAPE_DECISION_V7_VERSION,
        contract_kind=CONTEXT_SUFFICIENCY_CONTRACT_KIND,
        observed_conflict_signal=(
            "One public relation remains unresolved after required record selection."
        ),
        observed_evidence_state=FinanceStoppingObservedEvidenceState(
            observed_record=observed,
            required_record=required,
        ),
        public_relation_state=relation,
        shared_resolution_policy=SHARED_RESOLUTION_POLICY,
        oracle_conflict_dimension=dimension,
        state_activation_phase="after_required_evidence_selection_before_calculation",
        available_resolution_actions=_actions(),
        resolution_step_count=2,
    )


def test_public_context_is_sufficient_symmetric_and_shortcut_resistant() -> None:
    period = _decision("period")
    definition = _decision("definition")
    period_state = _public_relation_payload(period)
    definition_state = _public_relation_payload(definition)
    actions = _public_action_rows(period)

    assert _single_context_counterfactual_ready(period, definition)
    assert _publicly_applicable_action_labels(period_state, actions) == ("query_structured_fact",)
    assert _publicly_applicable_action_labels(definition_state, actions) == (
        "normalize_metric_unit_period",
    )
    assert _publicly_applicable_action_labels(period_state, tuple(reversed(actions))) == (
        "query_structured_fact",
    )
    relabeled = tuple(
        (f"candidate_{index}", description) for index, (_, description) in enumerate(actions)
    )
    assert _publicly_applicable_action_labels(period_state, relabeled) == ("candidate_2",)
    removed = {
        key: ("aligned" if key.endswith("_relation") else value)
        for key, value in period_state.items()
    }
    assert _publicly_applicable_action_labels(removed, actions) == ()
    assert _action_descriptions_are_symmetric(actions)
    assert not _lexical_context_action_overlap(period)
    assert not _lexical_context_action_overlap(definition)


def test_first_action_estimand_cannot_be_rescued_by_later_correct_action() -> None:
    roles = (SimpleNamespace(evidence_id="fact:a"), SimpleNamespace(evidence_id="fact:b"))
    task = SimpleNamespace(scenario=SimpleNamespace(evidence_roles=roles))
    record = SimpleNamespace(
        status="completed",
        observations=(
            _observation("open_document", ("fact:a",)),
            _observation("open_document", ("fact:b",)),
            _observation("normalize_metric_unit_period", ()),
            _observation("query_structured_fact", ("fact:a",)),
        ),
    )

    assert not _contextual_action_correct(record, task, expected_action="query_structured_fact")


def test_paired_hierarchical_bootstrap_is_deterministic_and_branch_balanced() -> None:
    all_correct = tuple(tuple(True for _ in range(8)) for _ in range(4))
    none_correct = tuple(tuple(False for _ in range(8)) for _ in range(4))

    assert (
        _paired_branch_balanced_bootstrap_lcb(
            all_correct,
            all_correct,
            replicates=10_000,
            seed=20260847,
        )
        == 1.0
    )
    first = _paired_branch_balanced_bootstrap_lcb(
        all_correct,
        none_correct,
        replicates=10_000,
        seed=20260847,
    )
    second = _paired_branch_balanced_bootstrap_lcb(
        all_correct,
        none_correct,
        replicates=10_000,
        seed=20260847,
    )
    assert first == second == 0.5


def test_scientific_decision_cannot_reauthorize_closed_stages() -> None:
    values = {
        "population_id": "population:test",
        "report_id": "report:test",
        "mechanism_report_id": "mechanism:test",
        "source_sha256": {
            "population": "a" * 64,
            "report": "b" * 64,
            "mechanism_report": "c" * 64,
        },
    }
    provisional = ContextSufficiencyScientificDecision.model_construct(
        decision_id="pending",
        **values,
    )
    decision = ContextSufficiencyScientificDecision(
        decision_id=_artifact_id(
            provisional,
            "decision_id",
            "finance_stopping_context_sufficiency_scientific_decision:",
        ),
        **values,
    )

    assert decision.production_contribution == 0.0
    assert not decision.additional_flash_rollouts_authorized
    assert not decision.pro_api_calls_authorized
    assert not decision.gp_c_authorized
    with pytest.raises(ValidationError):
        ContextSufficiencyScientificDecision.model_validate(
            {**decision.model_dump(mode="json"), "gp_c_authorized": True}
        )


def _observation(tool_id: str, evidence_ids: tuple[str, ...]) -> Any:
    return SimpleNamespace(
        call=SimpleNamespace(tool_id=tool_id),
        status="succeeded",
        evidence_ids=evidence_ids,
    )
