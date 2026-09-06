"""Control execution is local and categorically outside the model population."""

from __future__ import annotations

import socket
from pathlib import Path
from typing import Any

import pytest

from trusted_synthesis.canonical_json import canonical_json_bytes
from trusted_synthesis.experiments.finance_qa_vnext_model_execution import controls
from trusted_synthesis.experiments.finance_qa_vnext_model_execution.models import (
    identity,
    read_json,
)
from trusted_synthesis.experiments.finance_qa_vnext_model_execution.plan import (
    load_panel,
    verify_directory,
)
from trusted_synthesis.experiments.finance_qa_vnext_model_execution.transport import (
    HttpxSender,
    TransportConfig,
)

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def result(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, dict[str, Any]]:
    directory = tmp_path_factory.mktemp("online-controls") / "controls"
    with pytest.MonkeyPatch.context() as patch:

        def forbidden(*args: Any, **kwargs: Any) -> Any:
            pytest.fail("offline controls must not reach HttpxSender or a network socket")

        patch.setattr(socket, "create_connection", forbidden)
        patch.setattr(socket.socket, "connect", forbidden)
        patch.setattr(HttpxSender, "send", forbidden)
        report = controls.run_controls(load_panel(ROOT), directory, TransportConfig())
    return directory, report


def test_all_controls_pass_without_model_population_or_supervision_export(
    result: tuple[Path, dict[str, Any]],
) -> None:
    directory, report = result
    identity(report, "offline_controls")
    assert report["passed"], {
        row["name"]: row["checks"] for row in report["controls"] if not row["passed"]
    }
    assert report["provider_attempts"] == report["population_sessions"] == 0
    assert report["mock_attempts"] == 23
    assert report["runtime_submissions"] == 21
    assert report["exported_candidates"] == 0
    assert report["control_count"] == 4
    assert report["student_parameter_loads"] == report["student_forward_calls"] == 0
    assert report["student_parameter_updates"] == report["gpu_jobs"] == 0
    for row in report["controls"]:
        qualification = read_json((directory / row["name"] / "qualification.json").read_bytes())
        exported = read_json((directory / row["name"] / "export.json").read_bytes())
        assert qualification["evidence_complete"], qualification["errors"]
        assert qualification["control_evidence"]
        assert not qualification["model_origin_verified"]
        assert not qualification["qualified"]
        assert not qualification["export_eligible"]
        assert exported["candidate_count"] == 0
        assert exported["rows"] == []
        assert "model_origin_not_independently_verified" in exported["session_exclusion_reasons"]


def test_branch_reaches_all_17_submissions_in_same_registered_runtime(
    result: tuple[Path, dict[str, Any]],
) -> None:
    directory, report = result
    row = report["controls"][0]
    assert row["name"] == "B_complete_17"
    assert row["mock_attempts"] == row["runtime_submissions"] == 17
    saved = read_json((directory / row["name"] / "runtime/session.json").read_bytes())
    assert saved["bounds"] == {"actions": 12, "submissions": 32}
    assert [event["parsed"]["kind"] for event in saved["events"]].count("action") == 8
    assert [event["parsed"]["kind"] for event in saved["events"]].count("update") == 8
    assert saved["events"][-1]["parsed"]["kind"] == "final"
    assert saved["final"]["qa_validation"]["qa_valid"]


def test_correction_preserves_invalid_first_response_and_gets_fresh_state_feedback(
    result: tuple[Path, dict[str, Any]],
) -> None:
    directory, report = result
    row = report["controls"][1]
    assert row["name"] == "C_feedback_correction"
    assert row["runtime_submissions"] == row["mock_attempts"] == 4
    root = directory / row["name"]
    saved = read_json((root / "runtime/session.json").read_bytes())
    first, second = saved["events"][:2]
    assert first["parsed"]["kind"] == "action"
    assert first["parsed"]["state_id"] == "offline-control.invalid-current-state"
    assert first["receipt"]["error_code"] == "admission.current_state"
    assert not first["receipt"]["admitted"]
    assert second["receipt"]["admitted"]
    assert second["request"]["state"]["last_feedback"]["admitted"] is False
    assert first["request"]["state"]["id"] != second["request"]["state"]["id"]
    old_raw = (root / "transport/attempts/000_public_content.txt").read_bytes()
    assert old_raw == (root / "runtime/turns/000_response.txt").read_bytes()
    assert old_raw == canonical_json_bytes(first["parsed"])
    assert all(event["submission"]["host_repairs"] == [] for event in saved["events"])


@pytest.mark.parametrize(
    ("name", "reason"),
    [
        ("C_empty_content", "provider.no_public_content"),
        ("C_wrong_model", "provider.model_identity_mismatch"),
    ],
)
def test_no_response_and_wrong_model_have_typed_stop_no_submission_and_audited_prefix(
    result: tuple[Path, dict[str, Any]], name: str, reason: str
) -> None:
    directory, report = result
    row = next(row for row in report["controls"] if row["name"] == name)
    assert row["mock_attempts"] == 1 and row["runtime_submissions"] == 0
    root = directory / name
    session = read_json((root / "runtime/session.json").read_bytes())
    qualification = read_json((root / "qualification.json").read_bytes())
    outcome = read_json((root / "transport/attempts/000_outcome.json").read_bytes())
    assert session["callback_stop"]["reason"] == reason
    assert session["callback_stop"]["external_evidence_id"] == outcome["id"]
    assert session["events"] == [] and session["final"] is None
    assert not list((root / "runtime/turns").glob("*_submission.json"))
    assert not list((root / "runtime/turns").glob("*_receipt.json"))
    assert qualification["evidence_complete"] and qualification["trajectory_valid"]
    assert qualification["status"] == "known_failure"
    assert qualification["depth_scope"] == "reached_prefix"
    assert qualification["qa_valid"] is None


def test_every_actual_unchanged_control_request_fits_allowance_without_future_generalization(
    result: tuple[Path, dict[str, Any]],
) -> None:
    _, report = result
    measurements = [value for row in report["controls"] for value in row["request_measurements"]]
    assert len(measurements) == report["mock_attempts"]
    assert all(value["untruncated_current_public_request"] for value in measurements)
    assert report["maximum_actual_http_body_bytes"] == max(
        value["body_byte_count"] for value in measurements
    )
    assert 0 < report["maximum_actual_http_body_bytes"] < 98304
    assert 0 < report["maximum_input_admission_proxy"] < 99328
    assert (
        report["maximum_input_admission_proxy"] == report["maximum_actual_http_body_bytes"] + 1024
    )
    assert report["observed_request_fit_does_not_prove_all_future_requests_fit"]
    assert report["future_requests_still_require_per_attempt_guard"]
    assert report["input_admission_proxy_is_exact_provider_tokens"] is False


def test_full_control_artifact_sets_are_sealed_and_re_readable(
    result: tuple[Path, dict[str, Any]],
) -> None:
    directory, report = result
    manifest = verify_directory(directory, kind="offline_controls_manifest")
    assert manifest["report_id"] == report["id"]
    assert read_json((directory / "report.json").read_bytes()) == report
    for row in report["controls"]:
        local = verify_directory(directory / row["name"], kind="offline_control_manifest")
        assert local["control_id"] == row["id"]
        registration = read_json((directory / row["name"] / "registration.json").read_bytes())
        start = read_json((directory / row["name"] / "start.json").read_bytes())
        assert registration["offline_control"]
        assert not registration["registered_model_population_member"]
        assert start["registered_id"] == registration["id"]
        assert registration["maximum_actions"] == 12
        assert (
            registration["maximum_submissions"] == registration["maximum_provider_attempts"] == 32
        )
