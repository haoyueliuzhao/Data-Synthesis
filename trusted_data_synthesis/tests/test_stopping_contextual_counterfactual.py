from __future__ import annotations

from copy import deepcopy
from types import SimpleNamespace
from typing import Any, cast

import pytest

from trusted_synthesis.domains.finance.capability_submechanism_runtime import (
    FINANCE_STOPPING_SHAPE_DECISION_V6_VERSION,
    FINANCE_SUBMECHANISM_ORACLE_KEY,
    FinanceStoppingMeasurementContext,
    FinanceStoppingObservedEvidenceState,
    FinanceStoppingObservedRecord,
    FinanceStoppingResolutionAction,
    FinanceStoppingShapeDecisionContract,
    FinanceStoppingTemporalIdentity,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_submechanism_population import (  # noqa: E501
    PUBLIC_SUBMECHANISM_METADATA_KEY,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_stopping_contextual_counterfactual import (  # noqa: E501
    FinanceStoppingContextualCounterfactualReport,
    _contextual_lexical_leak,
    _paired_core_hash,
    _single_context_counterfactual_ready,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_stopping_contextual_counterfactual_runner import (  # noqa: E501
    FLIP_REPORT_NAME,
    PREFIX,
    RAW_AUDIT_NAME,
    REPORT_MARKDOWN_NAME,
    REPORT_NAME,
    SHAPE_REPORT_NAME,
    _contextual_action_correct,
    _make_manifest,
    _make_overall_report,
    _write_or_verify_json,
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
    return (
        FinanceStoppingResolutionAction(
            tool_id="normalize_metric_unit_period",
            applicable_when="reconcile the active observation with the reference set",
        ),
        FinanceStoppingResolutionAction(
            tool_id="open_document",
            applicable_when="inspect authority when provenance remains uncertain",
        ),
        FinanceStoppingResolutionAction(
            tool_id="query_structured_fact",
            applicable_when="replace the active observation from the archive",
        ),
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
        dimension = "temporal_alignment"
    else:
        observed = required.model_copy(update={"definition_id": "definition:alternate"})
        dimension = "source_definition_compatibility"
    return FinanceStoppingShapeDecisionContract(
        schema_version=FINANCE_STOPPING_SHAPE_DECISION_V6_VERSION,
        contract_kind="contextual_counterfactual_evidence_choice_two_step",
        observed_conflict_signal=(
            "The active observation differs in one registered identity component."
        ),
        observed_evidence_state=FinanceStoppingObservedEvidenceState(
            observed_record=observed,
            required_record=required,
        ),
        oracle_conflict_dimension=dimension,
        state_activation_phase=("after_required_evidence_selection_before_calculation"),
        available_resolution_actions=_actions(),
        resolution_step_count=2,
    )


def test_contextual_pair_changes_only_context_and_flips_action() -> None:
    period = _decision("period")
    definition = _decision("definition")

    assert _single_context_counterfactual_ready(period, definition)
    assert not _contextual_lexical_leak(period)
    assert not _contextual_lexical_leak(definition)


def test_paired_core_hash_ignores_only_context_and_derived_scenario_identity() -> None:
    def paired_task(
        decision: FinanceStoppingShapeDecisionContract,
        scenario_id: str,
        *,
        instruction: str = "Resolve the active evidence state.",
    ) -> Any:
        public_decision = decision.model_dump(mode="json")
        public_decision.pop("oracle_conflict_dimension", None)
        payload = {
            "artifact_id": f"artifact:{scenario_id}",
            "task": {
                "public": {
                    "instruction": instruction,
                    "metadata": {
                        PUBLIC_SUBMECHANISM_METADATA_KEY: {
                            "stopping_shape_decision_contract": public_decision
                        }
                    },
                },
                "oracle": {
                    "selection_contract": {
                        FINANCE_SUBMECHANISM_ORACLE_KEY: {
                            "scenario_id": scenario_id,
                            "stopping_shape_decision_contract": decision.model_dump(mode="json"),
                        }
                    }
                },
            },
        }
        artifact = SimpleNamespace(model_dump=lambda mode: deepcopy(payload))
        return SimpleNamespace(artifact=artifact)

    period = paired_task(_decision("period"), "scenario:period")
    definition = paired_task(_decision("definition"), "scenario:definition")
    changed_core = paired_task(
        _decision("definition"),
        "scenario:definition",
        instruction="A different core instruction.",
    )

    assert _paired_core_hash(period) == _paired_core_hash(definition)
    assert _paired_core_hash(period) != _paired_core_hash(changed_core)


def test_contextual_flip_replay_requires_first_post_prerequisite_action() -> None:
    roles = (SimpleNamespace(evidence_id="fact:a"), SimpleNamespace(evidence_id="fact:b"))
    task = SimpleNamespace(scenario=SimpleNamespace(evidence_roles=roles))
    observations = (
        _observation("open_document", ("fact:a",)),
        _observation("open_document", ("fact:b",)),
        _observation("query_structured_fact", ("fact:a",)),
    )
    record = SimpleNamespace(status="completed", observations=observations)
    assert _contextual_action_correct(record, task, expected_action="query_structured_fact")

    wrong_first = SimpleNamespace(
        status="completed",
        observations=(
            *observations[:2],
            _observation("normalize_metric_unit_period", ()),
            observations[2],
        ),
    )
    assert not _contextual_action_correct(
        wrong_first, task, expected_action="query_structured_fact"
    )


def _observation(tool_id: str, evidence_ids: tuple[str, ...]) -> Any:
    return SimpleNamespace(
        call=SimpleNamespace(tool_id=tool_id),
        status="succeeded",
        evidence_ids=evidence_ids,
    )


def test_current_shape_report_flows_directly_to_overall_report_and_manifest(
    tmp_path,
) -> None:
    wrapper = SimpleNamespace(
        contract_id="contextual:test",
        implementation_manifest_hash="implementation:test",
    )
    raw = SimpleNamespace(
        audit_id="raw:test",
        instrument_status="passed",
        shape_analysis_authorized=True,
        successful_record_count=178,
        behavior_failure_record_count=206,
        auditable_record_count=384,
        recursive_host_field_violation_count=0,
        recursive_host_marker_violation_count=0,
        rejection_reasons=(),
    )
    shape = SimpleNamespace(
        report_id="shape:test",
        all_shapes_contract_passing=True,
        valid_training_trajectory_count=167,
        boundary_candidate_admitted_count=4,
        runtime_control_pass_count=2,
        stopping_behavior_success_rate=0.5,
        full_valid_trajectory_success_rate=0.4,
        answer_semantic_success_rate=0.45,
        shape_results=(),
    )
    flip = SimpleNamespace(
        report_id="flip:test",
        passed=True,
        contextual_flip_consistency=0.25,
        informative_pair_count=4,
        maximum_branch_action_rate_difference=0.25,
    )
    report = _make_overall_report(
        cast(Any, wrapper), cast(Any, raw), cast(Any, shape), cast(Any, flip)
    )
    assert isinstance(report, FinanceStoppingContextualCounterfactualReport)
    assert report.all_v25_46_gates_passing
    assert report.next_permitted_stage == "fresh_three_population_shape_policy_preparation"

    payloads = {
        f"{PREFIX}_records.jsonl": "{}\n",
        f"{PREFIX}_outcomes.jsonl": "{}\n",
        f"{PREFIX}_model_discovery.json": "{}\n",
        RAW_AUDIT_NAME: "{}\n",
        SHAPE_REPORT_NAME: "{}\n",
        FLIP_REPORT_NAME: "{}\n",
        REPORT_NAME: "{}\n",
        REPORT_MARKDOWN_NAME: "report\n",
    }
    for name, value in payloads.items():
        (tmp_path / name).write_text(value, encoding="utf-8")
    manifest = _make_manifest(
        wrapper=cast(Any, wrapper),
        report=report,
        raw=cast(Any, raw),
        shape=cast(Any, shape),
        flip=cast(Any, flip),
        output_dir=tmp_path,
    )
    assert manifest["shape_report_id"] == "shape:test"
    assert manifest["flip_report_id"] == "flip:test"
    assert len(manifest["artifact_sha256"]) == len(payloads)


def test_v25_46_final_artifact_writer_is_immutable(tmp_path) -> None:
    path = tmp_path / "report.json"
    _write_or_verify_json(path, {"decision": "passed"})
    _write_or_verify_json(path, {"decision": "passed"})
    with pytest.raises(ValueError, match="immutable JSON differs"):
        _write_or_verify_json(path, {"decision": "failed"})
