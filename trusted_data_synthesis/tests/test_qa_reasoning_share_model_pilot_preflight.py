"""Verify the closed six-session pilot using only its immutable execution bytes."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from trusted_synthesis.experiments.qa_reasoning_finite_comparison.inputs import (
    files_at,
    validate_manifest,
)
from trusted_synthesis.experiments.qa_reasoning_share_model_pilot import (
    adapter,
    controls,
    engine,
    models,
    preflight,
)
from trusted_synthesis.experiments.qa_reasoning_share_public_protocol.models import ProtocolError

ROOT = Path(__file__).resolve().parents[2]
FORMAL = ROOT / (
    "trusted_data_synthesis/artifacts/qa_reasoning_share_model_pilot/"
    "finance_qa_vnext_share_public_protocol_model_adapter_six_session_pilot_v1_20260905"
)
SOURCE_COMMIT = "55fb6aab8d7122b4d930d1c31843e7d3653ccd19"
SOURCE_TREE = "dc9c8c59c7e9b96e1cf0033d6aa9563faa06ce44"


@pytest.fixture(autouse=True)
def forbid_all_new_execution(monkeypatch: pytest.MonkeyPatch) -> None:
    def forbidden(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("replay must not execute any model/mock/kernel or read credentials")

    monkeypatch.setattr(preflight, "ModelProtocolEngine", forbidden)
    monkeypatch.setattr(preflight, "_credential", forbidden)
    monkeypatch.setattr(adapter.DeepSeekAdapter, "perform", forbidden)
    monkeypatch.setattr(adapter.CurlTransport, "send", forbidden)
    monkeypatch.setattr(adapter.MockTransport, "send", forbidden)
    monkeypatch.setattr(controls.Scenario, "handle", forbidden)
    monkeypatch.setattr(controls.Scenario, "public_response", forbidden)
    for cls in (engine.RelationSumExecutor, engine.ShareRatioExecutor, engine.ScalePercentExecutor):
        monkeypatch.setattr(cls, "execute", forbidden)


def read(name: str) -> dict[str, Any]:
    return json.loads((FORMAL / name).read_bytes())


def test_complete_byte_rebuild_without_model_mock_kernel_or_credential(tmp_path: Path) -> None:
    original = files_at(FORMAL)
    result = preflight.replay_pilot(
        repo_root=ROOT, replay_from=FORMAL, output_directory=tmp_path / "replay"
    )
    assert (
        result["new_Provider_attempts"]
        == result["new_mock_callbacks"]
        == result["new_kernel_calls"]
        == 0
    )
    assert result["report"]["status"] == "workflow_completed_as_scoped"
    assert files_at(tmp_path / "replay") == original == files_at(FORMAL)


def test_existing_online_cohort_is_never_restarted() -> None:
    before = files_at(FORMAL)
    with pytest.raises(ProtocolError, match="pilot.no_online_restart_or_replacement"):
        preflight.run_online(
            repo_root=ROOT, output_directory=FORMAL, credential_path=ROOT / "never_read.env"
        )
    assert files_at(FORMAL) == before


def test_final_manifest_exact_members_geometry_and_bytes() -> None:
    files = files_at(FORMAL)
    manifest = read("artifact_manifest.json")
    validate_manifest(files, manifest["manifest_id"], manifest["artifact_root"])
    assert len(files) == 785
    assert manifest["member_count"] == 784
    assert manifest["member_bytes"] == 8_191_735
    assert sum(map(len, files.values())) == 8_312_321
    assert len(files["artifact_manifest.json"]) == 120_586


def test_preparation_freeze_is_unchanged_and_no_network_was_used() -> None:
    preflight._verify_subset(FORMAL, read("preparation_manifest.json"))
    prep = read("preparation_report.json")
    assert prep["all_controls_passed"]
    assert prep["mock_callbacks"] == 14 and prep["mock_kernel_calls"] == 5
    assert prep["Provider_attempts"] == prep["credential_reads"] == 0
    assert prep["online_sessions_started"] == 0
    assert prep["model_reachability"] is None


def test_actual_attempt_ledger_is_fixed_51_not_72_or_six_samples_per_response() -> None:
    registration = read("pilot_registration.json")
    counts = []
    for declaration in registration["sessions"]:
        manifest = read("online/" + declaration["label"] + "/session_manifest.json")
        attempts = [
            read("online/" + declaration["label"] + "/" + event["provider_attempt"])
            for event in manifest["events"]
        ]
        assert [a["ordinal"] for a in attempts] == list(range(1, len(attempts) + 1))
        assert all(a["counted_before_send"] and a["automatic_retries"] == 0 for a in attempts)
        assert all(
            a["provider_attempts_consumed"] == 1 and a["mock_attempts_consumed"] == 0
            for a in attempts
        )
        counts.append(len(attempts))
    assert counts == [12, 7, 12, 6, 9, 5]
    assert sum(counts) == read("pilot_measurement.json")["provider_attempts"] == 51
    assert read("pilot_measurement.json")["registered_denominator"] == 6


def test_actual_usage_is_not_the_reserved_allowance() -> None:
    usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    for path in (FORMAL / "online").glob("M*/turns/*_provider_response.json"):
        response = json.loads(path.read_bytes())
        assert response["status"] == "received" and response["parser_status"] == "valid"
        assert response["received_model"] == "deepseek-v4-pro"
        for key in usage:
            assert type(response["usage"][key]) is int
            usage[key] += response["usage"][key]
    assert usage == {"prompt_tokens": 565_082, "completion_tokens": 24_852, "total_tokens": 589_934}
    assert usage["total_tokens"] < 51 * models.model_config()["maximum_request_reserved_tokens"]


def test_current_declared_sources_and_frozen_parents_have_not_changed() -> None:
    authority = read("source_authority.json")
    actual = preflight.source_group(ROOT, SOURCE_COMMIT, SOURCE_TREE, preflight.SOURCE_PATHS)
    assert actual == authority["implementation"]
    frozen = preflight._frozen_inputs(ROOT)
    assert len(frozen["parent"]) == 71 and len(frozen["original"]) == 65
    assert frozen["context"] == read("public_context.json")
    preflight._parent_unchanged(ROOT, frozen)


def test_current_authority_is_not_inferred_from_old_pass_alone() -> None:
    config = read("model_config.json")
    authorization = read("authorization.json")
    assert authorization == preflight._authorize(
        (FORMAL / "external_review.txt").read_bytes(), config
    )
    assert authorization["external_review_itself_is_online_authorization"] is False
    assert authorization["current_operator_directive"] == "参照审计开展后续实验"
    assert (FORMAL / "operator_directive.txt").read_bytes() == models.DIRECTIVE.encode()
    start = read("online_start_receipt.json")
    assert start["before_any_online_send"] and start["all_six_sessions_predeclared"]
    assert start["credential_file_reads"] == 1


def test_workflow_pass_does_not_require_every_model_session_to_succeed() -> None:
    report = read("report.json")
    measurement = read("pilot_measurement.json")
    assert report["status"] == "workflow_completed_as_scoped"
    assert measurement["success_count"] == 5
    assert measurement["exact_fraction"] == "5/6"
    assert measurement["workflow_complete"] is True
    assert measurement["mechanism_defect_session_ids"] == []
    assert all(g["passed"] for g in read("gate_evaluation.json")["gates"])
    assert report["new_W_share"] is report["new_quotient_class_count"] is None
    assert report["old_W_share"] == 1 and report["older_compound_task_W"] is None
    assert report["next_stage_authorized"] is False
