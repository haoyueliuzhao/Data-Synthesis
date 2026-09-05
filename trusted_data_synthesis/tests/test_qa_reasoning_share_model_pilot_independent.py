"""Bounded read-only checks of actual pilot evidence and missing-evidence semantics."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest

from trusted_synthesis.experiments.qa_reasoning_share_model_pilot import (
    adapter,
    engine,
    independent,
    models,
    preflight,
)

ROOT = Path(__file__).resolve().parents[2]
FORMAL = ROOT / (
    "trusted_data_synthesis/artifacts/qa_reasoning_share_model_pilot/"
    "finance_qa_vnext_share_public_protocol_model_adapter_six_session_pilot_v1_20260905"
)


def read(name: str) -> dict[str, Any]:
    return json.loads((FORMAL / name).read_bytes())


def _renew(kind: str, value: dict[str, Any], **changes: Any) -> dict[str, Any]:
    fields = {k: copy.deepcopy(v) for k, v in value.items() if k not in {"id", "schema_version"}}
    return models.record(kind, **(fields | changes))


@pytest.fixture(autouse=True)
def no_host_or_provider_execution(monkeypatch: pytest.MonkeyPatch) -> None:
    def forbidden(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("only independent record replay is allowed")

    monkeypatch.setattr(engine.ModelProtocolEngine, "exchange", forbidden)
    monkeypatch.setattr(engine, "prepare", forbidden)
    monkeypatch.setattr(engine, "parse_submission", forbidden)
    monkeypatch.setattr(adapter, "parse_submission", forbidden)
    monkeypatch.setattr(adapter.DeepSeekAdapter, "perform", forbidden)
    monkeypatch.setattr(adapter.CurlTransport, "send", forbidden)
    monkeypatch.setattr(adapter.MockTransport, "send", forbidden)
    monkeypatch.setattr(preflight, "_credential", forbidden)
    for cls in (engine.RelationSumExecutor, engine.ShareRatioExecutor, engine.ScalePercentExecutor):
        monkeypatch.setattr(cls, "execute", forbidden)


@pytest.fixture(scope="module")
def frozen() -> dict[str, Any]:
    return {
        "inputs": preflight._frozen_inputs(ROOT),
        "config": read("model_config.json"),
        "protocol": read("protocol_contract.json"),
        "binding": read("model_adapter_binding.json"),
        "registration": read("pilot_registration.json"),
        "reports": [read(f"online_reports/M{i:02d}.json") for i in range(1, 7)],
    }


def args(frozen: dict[str, Any], index: int) -> dict[str, Any]:
    return {
        "context": frozen["inputs"]["context"],
        "source": frozen["inputs"]["source"],
        "legacy_contract": frozen["inputs"]["legacy"],
        "protocol": frozen["protocol"],
        "model_config": frozen["config"],
        "adapter_binding": frozen["binding"],
        "session_registration": frozen["registration"]["sessions"][index],
    }


def test_six_actual_sessions_and_summary_replay_exactly(frozen: dict[str, Any]) -> None:
    reports = [
        independent.audit_session(
            **args(frozen, i), session_root=FORMAL / "online" / f"M{i + 1:02d}"
        )
        for i in range(6)
    ]
    assert reports == frozen["reports"]
    assert all(r["evidence_complete"] and r["protocol_valid"] for r in reports)
    assert [r["Y"] for r in reports] == [0, 1, 1, 1, 1, 1]
    assert independent.aggregate_pilot(frozen["registration"], reports) == read(
        "pilot_measurement.json"
    )
    assert all(
        r["provider_calls_by_this_audit"] == r["candidate_runtime_executions"] == 0 for r in reports
    )


def test_m01_exhausted_after_accepting_claim_is_not_a_final_success(frozen: dict[str, Any]) -> None:
    report = frozen["reports"][0]
    records = independent.read_session_records(FORMAL / "online/M01")
    assert report["first_observed_failure"]["turn_index"] == 2
    assert report["first_observed_failure"]["code"] == "admission.public_basis"
    assert report["callback_attempts"] == report["public_submission_attempts"] == 12
    assert report["accepted_claim_count"] == 3 and report["valid_final"] is False
    assert records["events"][-1]["claim"] is not None
    assert records["events"][-1]["post_state"]["terminal"] == "submission_budget_exhausted"
    assert report["qa_valid"] is None and report["qualified"] is False and report["Y"] == 0
    assert report["support_description"]["label"] == "unresolved"


def test_actual_support_descriptions_follow_final_not_first_action(frozen: dict[str, Any]) -> None:
    assert [r["support_description"]["label"] for r in frozen["reports"]] == [
        "unresolved",
        "disclosed_total",
        "reconstructed_total_claim",
        "disclosed_total",
        "disclosed_total",
        "disclosed_total",
    ]
    control = read("control_results/reject_then_direct.json")["independent_validation"]
    records = independent.read_session_records(FORMAL / "controls/reject_then_direct")
    reject = records["events"][1]
    assert reject["submission"]["parsed"]["disposition"] == "reject"
    assert reject["claim"] is None
    assert reject["post_state"]["accepted_claims"] == []
    assert reject["post_state"]["pending_observation"] is None
    assert control["support_description"]["label"] == "disclosed_total"
    assert len(control["support_description"]["declined_observation_ids"]) == 1
    assert control["Y"] is None and control["mock_control_success"] is True


def test_transport_attempt_is_separate_from_submission_and_unreached_update() -> None:
    records = independent.read_session_records(FORMAL / "controls/transport_failure")
    report = read("control_results/transport_failure.json")["independent_validation"]
    assert len(records["events"]) == report["callback_attempts"] == 1
    assert records["events"][0]["submission"] is None
    assert records["events"][0]["receipt"] is None
    assert report["public_submission_attempts"] == 0
    assert report["evidence_complete"] is True and report["protocol_valid"] is True
    assert report["valid_final"] is False and report["Y"] is None
    assert report["phase_metrics"]["update"]["reached"] is False
    assert report["phase_metrics"]["update"]["strict_schema_per_request"]["value"] is None


def test_hash_only_one_turn_probe_is_not_reported_as_complete_failed_session() -> None:
    records = independent.read_session_records(FORMAL / "controls/invalid_json")
    event = records["events"][0]
    assert event["submission"]["parsed"] is event["submission"]["raw_public_json"] is None
    assert event["submission"]["response_byte_count"] > 0
    assert event["provider_response"]["evidence_level"] == "receiver_diagnosis_only"
    assert event["post_state"]["submission_count"] == 1
    assert event["post_state"]["terminal"] is None
    report = read("control_results/invalid_json.json")["independent_validation"]
    assert report["evidence_complete"] is False and report["Y"] is None
    assert report["first_evidence_failure"]["stage"] == "evidence.terminal_stop"


def test_all_actual_schema_results_and_semantic_admission_denominators(
    frozen: dict[str, Any],
) -> None:
    reports = frozen["reports"]
    assert sum(r["raw_public_json_response_count"] for r in reports) == 51
    assert sum(r["receiver_diagnosis_only_response_count"] for r in reports) == 0
    observed = {}
    for kind in ("action", "update", "final"):
        observed[kind] = (
            sum(r["parsed_kind_admission"][kind]["numerator"] for r in reports),
            sum(r["parsed_kind_admission"][kind]["denominator"] for r in reports),
        )
    assert observed == {"action": (14, 20), "update": (14, 22), "final": (5, 9)}
    assert all(r["update_dispositions"]["reject_committed"] == 0 for r in reports)


def test_rehashed_response_attempt_mismatch_is_unknown_not_zero(frozen: dict[str, Any]) -> None:
    records = independent.read_session_records(FORMAL / "online/M06")
    event = records["events"][0]
    event["provider_response"] = _renew(
        "provider_response",
        event["provider_response"],
        attempt_id="share_model_pilot_provider_attempt:" + "0" * 64,
    )
    report = independent.audit_records(**args(frozen, 5), records=records)
    assert report["evidence_complete"] is False
    assert report["Y"] is report["qualified"] is None
    assert report["first_evidence_failure"] is not None


def test_missing_session_keeps_fixed_denominator_but_no_imputed_proportion(
    frozen: dict[str, Any],
) -> None:
    report = independent.aggregate_pilot(frozen["registration"], frozen["reports"][:-1])
    assert report["registered_denominator"] == 6
    assert report["evidence_complete_count"] == 5
    assert report["known_success_count"] == 4
    assert report["q_public_protocol"] is report["success_count"] is None
    assert report["missing_or_unknown_sessions"] == [frozen["registration"]["session_ids"][-1]]
    assert report["workflow_complete"] is False


def test_mock_report_cannot_replace_model_denominator_entry(frozen: dict[str, Any]) -> None:
    mock = read("control_results/direct.json")["independent_validation"]
    report = independent.aggregate_pilot(frozen["registration"], [*frozen["reports"][:-1], mock])
    assert report["q_public_protocol"] is None and report["workflow_complete"] is False
    assert report["errors"][0]["stage"] == "measurement.report_domain"
    assert report["mock_sessions_in_denominator"] == 0


def test_synthetic_mechanism_defect_is_not_an_ordinary_model_negative(
    frozen: dict[str, Any],
) -> None:
    reports = copy.deepcopy(frozen["reports"])
    reports[1] = _renew(
        "session_audit", reports[1], protocol_valid=False, valid_final=False, qualified=False, Y=0
    )
    result = independent.aggregate_pilot(frozen["registration"], reports)
    assert result["evidence_complete_count"] == 6
    assert result["exact_fraction"] == "4/6"
    assert result["workflow_complete"] is False
    assert result["model_attribution_allowed"] is False
    assert result["mechanism_defect_session_ids"] == [reports[1]["session_id"]]
