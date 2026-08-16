from __future__ import annotations

import hashlib
import json
from types import SimpleNamespace
from typing import Any, cast

import pytest
from pydantic import ValidationError

from trusted_synthesis.domains.finance.public_tool_results import (
    FailedResultPublic,
    PublicCompletionState,
)
from trusted_synthesis.experiments.counterfactual_finance_fixture import (
    build_finance_counterfactual_case,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_stopping_instrument_reset import (
    make_raw_instrument_audit,
    make_static_noninterference_audit,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_stopping_instrument_reset_finalize import (  # noqa: E501
    _make_report,
    _write_or_verify_json,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_stopping_shape_policy_protocol import (
    FinanceStoppingInstrumentResetGrammarProtocol,
    load_stopping_shape_grammar_protocol,
    prepare_instrument_reset_grammar_protocol,
)
from trusted_synthesis.runtime.agent.iterative import _make_failure_artifact
from trusted_synthesis.runtime.agent.schema import ModelCallTelemetry


def test_v25_45_static_recursive_noninterference_gate_passes() -> None:
    audit = make_static_noninterference_audit()

    assert audit.ready is True
    assert audit.rejection_reasons == ()
    assert audit.host_field_mutation_rejection_count == audit.host_field_mutation_count
    assert audit.host_marker_mutation_rejection_count == audit.host_marker_mutation_count
    assert audit.whitelist_alias_mutation_rejection_count == (
        audit.whitelist_alias_mutation_count
    )
    assert audit.serialized_prompt_mutation_rejection_count == (
        audit.serialized_prompt_mutation_count
    )
    assert audit.nested_extra_forbid_count == audit.nested_model_count


@pytest.mark.parametrize(
    "payload",
    [
        {"completion_state": {"complete": False, "completion_reason": "host-only"}},
        {"completion_state": {"complete": False, "trigger_label": "host-only"}},
        {"resolution_status": "host-only"},
        {"oracle_stage": "host-only"},
    ],
)
def test_v25_45_public_result_whitelist_rejects_future_host_aliases(
    payload: dict[str, object],
) -> None:
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        FailedResultPublic.model_validate(payload)


def test_v25_45_nested_public_schema_is_extra_forbid() -> None:
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        PublicCompletionState.model_validate(
            {"complete": False, "nested_host_hint": "continue"}
        )


def test_v25_45_reset_grammar_is_independent_of_historical_outcomes(tmp_path) -> None:
    snapshot = tmp_path / "snapshot.jsonl"
    snapshot.write_text('{"evidence_id":"snapshot:test"}\n', encoding="utf-8")
    calibration = tmp_path / "calibration.json"
    calibration.write_text(
        json.dumps({"contract_id": "calibration:test"}), encoding="utf-8"
    )
    populations = []
    for index in range(43):
        path = tmp_path / f"population_{index:02d}.json"
        path.write_text(
            json.dumps({"population_id": f"population:{index:02d}"}),
            encoding="utf-8",
        )
        populations.append(path)
    output = tmp_path / "reset_grammar.json"

    protocol = prepare_instrument_reset_grammar_protocol(
        source_finance_artifacts_path=snapshot,
        source_finance_artifacts_id="snapshot:test",
        source_calibration_contract_path=calibration,
        historical_population_paths=tuple(populations),
        output_path=output,
        run_id="test-reset-grammar",
    )
    loaded = load_stopping_shape_grammar_protocol(output)
    payload = protocol.model_dump(mode="json")

    assert isinstance(loaded, FinanceStoppingInstrumentResetGrammarProtocol)
    assert protocol.source_outcome_artifacts_used is False
    assert protocol.historical_shape_support_transferred is False
    assert len(protocol.historical_population_references) == 43
    assert all(not design.source_result_admitted for design in protocol.shape_designs)
    assert all(
        not design.historical_result_transfer_authorized
        for design in protocol.shape_designs
    )
    assert not any(key.startswith("source_v25_43") for key in payload)
    assert "source_v25_43_report" not in json.dumps(payload, sort_keys=True)


def test_fail_closed_behavior_outcomes_remain_noninterference_auditable() -> None:
    task = build_finance_counterfactual_case(1).task.public
    prompt = "Return a public JSON decision."
    request_hash = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
    telemetry = ModelCallTelemetry(
        provider="fixture",
        endpoint_host="fixture.invalid",
        model_requested="fixture-model",
        model_selected="fixture-model",
        response_model="fixture-model",
        request_hash=request_hash,
        response_hash="response:test",
        http_status=200,
        http_success=True,
        json_contract_success=True,
        prompt_tokens=4,
        completion_tokens=2,
        total_tokens=6,
    )
    failure = _make_failure_artifact(
        task=task,
        mode="autonomous_agent",
        environment_manifest_id="environment:test",
        protocol_profile_hash="profile:test",
        plan=None,
        decisions=(),
        observations=(),
        telemetry=(telemetry,),
        plan_prompt_hash="plan:test",
        decision_prompt_hashes=("decision:test",),
        model_request_prompts=(prompt,),
        failure_message="bounded capability failure",
    )
    task_id = task.task_id
    record = SimpleNamespace(
        status="failed",
        agent_audit=None,
        failure_artifact=failure,
        observations=(),
        task_artifact_id=task_id,
    )
    reset = SimpleNamespace(contract_id="reset:test")
    base = SimpleNamespace(task_expected_host_events={task_id: ()})

    audit = make_raw_instrument_audit(
        cast(Any, reset), cast(Any, base), (record,) * 384
    )

    assert audit.instrument_status == "passed"
    assert audit.shape_analysis_authorized is True
    assert audit.auditable_record_count == 384
    assert audit.successful_record_count == 0
    assert audit.behavior_failure_record_count == 384
    assert audit.contamination_task_count == 0
    assert audit.unattested_task_count == 0


def test_instrument_reset_finalizer_uses_shape_contract_decision() -> None:
    reset = SimpleNamespace(contract_id="reset:test")
    raw = SimpleNamespace(
        audit_id="audit:test",
        instrument_status="passed",
        shape_analysis_authorized=True,
    )
    shape = SimpleNamespace(
        report_id="shape:test",
        boundary_candidate_admitted_count=3,
        runtime_control_pass_count=2,
        all_shapes_contract_passing=False,
    )

    report = _make_report(
        cast(Any, reset), cast(Any, raw), cast(Any, shape)
    )

    assert report.all_shapes_admitted is False
    assert report.next_permitted_stage == "stopping_shape_redesign_only"
    assert report.boundary_candidate_admitted_count == 3
    assert report.runtime_control_pass_count == 2


def test_instrument_reset_finalization_output_is_immutable(tmp_path) -> None:
    path = tmp_path / "final.json"
    value = {"decision": "stopping_shape_redesign_only", "count": 3}

    _write_or_verify_json(path, value)
    _write_or_verify_json(path, value)

    with pytest.raises(ValueError, match="differs from deterministic recomputation"):
        _write_or_verify_json(path, {**value, "count": 4})
