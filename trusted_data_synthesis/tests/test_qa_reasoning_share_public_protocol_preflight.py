"""Read saved evidence and rebuild bytes only; never run an additional fixture session."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from trusted_synthesis.experiments.qa_reasoning_finite_comparison.inputs import (
    files_at,
    validate_manifest,
)
from trusted_synthesis.experiments.qa_reasoning_fixed_fixture.runtime import (
    FixedFixtureRuntimeError,
)
from trusted_synthesis.experiments.qa_reasoning_part_whole_share import runtime as old_runtime
from trusted_synthesis.experiments.qa_reasoning_part_whole_share import source as old_source
from trusted_synthesis.experiments.qa_reasoning_share_public_protocol import engine, preflight
from trusted_synthesis.experiments.qa_reasoning_share_public_protocol.controls import run_controls
from trusted_synthesis.experiments.qa_reasoning_share_public_protocol.fixture import (
    PublicRequestFixture,
)
from trusted_synthesis.experiments.qa_reasoning_share_public_protocol.independent import (
    read_session_records,
)
from trusted_synthesis.experiments.qa_reasoning_share_public_protocol.models import ProtocolError

ROOT = Path(__file__).resolve().parents[2]
FORMAL = ROOT / (
    "trusted_data_synthesis/artifacts/qa_reasoning_share_public_protocol/"
    "finance_qa_vnext_share_public_state_proposal_action_observation_update_protocol_"
    "preflight_v1_20260905"
)
SOURCE_COMMIT = "606b13c35cb3aca4107ee5497451ba51378bb843"
SOURCE_TREE = "6736228347d4d8519c7ac099378a409dc45b8053"


def read(name: str) -> dict[str, Any]:
    return json.loads((FORMAL / name).read_bytes())


@pytest.fixture(autouse=True)
def forbid_new_execution(monkeypatch: pytest.MonkeyPatch) -> None:
    def forbidden(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("additional callback, engine, old source or kernel is forbidden")

    monkeypatch.setattr(preflight, "ProtocolEngine", forbidden)
    monkeypatch.setattr(PublicRequestFixture, "generate", forbidden)
    monkeypatch.setattr(old_runtime, "run_candidate", forbidden)
    monkeypatch.setattr(old_source, "load_source", forbidden)
    for cls in (engine.RelationSumExecutor, engine.ShareRatioExecutor, engine.ScalePercentExecutor):
        monkeypatch.setattr(cls, "execute", forbidden)


def build(path: Path) -> dict[str, Any]:
    return preflight.build_preflight(
        repo_root=ROOT,
        external_audit_path=FORMAL / "external_review.txt",
        source_commit=SOURCE_COMMIT,
        source_tree=SOURCE_TREE,
        output_directory=path,
        replay_from=FORMAL,
    )


def test_byte_rebuild_has_zero_new_callback_or_kernel(tmp_path: Path) -> None:
    original = files_at(FORMAL)
    result = build(tmp_path / "byte_rebuild")
    assert result["new_generator_callbacks"] == result["new_kernel_calls"] == 0
    assert result["report"]["status"] == "passed_as_scoped"
    assert files_at(tmp_path / "byte_rebuild") == original == files_at(FORMAL)


def test_rebuild_never_replaces_existing_output(tmp_path: Path) -> None:
    output = tmp_path / "no_replace"
    build(output)
    before = files_at(output)
    with pytest.raises(FixedFixtureRuntimeError, match="already exists"):
        build(output)
    assert files_at(output) == before


def test_parent_remains_exact_frozen_bytes() -> None:
    freeze, files = preflight.freeze_parent(ROOT)
    assert len(files) == freeze["files"] == 65
    assert sum(map(len, files.values())) == freeze["bytes"] == 254_479
    assert freeze["historical_W_share"] == 1
    assert freeze["historical_compound_task_W"] is None


def test_exact_review_required() -> None:
    review = (FORMAL / "external_review.txt").read_bytes()
    assert preflight.authorize(review)["online_authorization"] is False
    with pytest.raises(ProtocolError, match="authorization.review"):
        preflight.authorize(review + b" ")


def test_formal_manifest_geometry_and_identity() -> None:
    files = files_at(FORMAL)
    manifest = read("artifact_manifest.json")
    assert validate_manifest(files, manifest["manifest_id"], manifest["artifact_root"]) == manifest
    assert len(files) == 71
    assert manifest["member_count"] == 70
    assert manifest["member_bytes"] == 637_560


def test_actual_saved_counts_are_not_preview_counts() -> None:
    report = read("report.json")
    counts = report["counts"]
    assert counts["positive_protocol_sessions"] == 1
    assert counts["generator_callbacks"] == 7
    assert counts["actions"] == counts["updates"] == counts["accepted_claims"] == 3
    assert counts["kernel_calls"] == 3 and counts["finals"] == 1
    assert counts["Provider_calls"] == counts["credential_reads"] == counts["GPU_calls"] == 0
    assert report["model_reachability"] is report["model_class_probabilities"] is None
    assert report["new_W_share"] is report["new_semantic_class_count"] is None
    assert report["next_stage_authorized"] is False


def test_controls_recomputed_without_dispatch_or_state_mutation() -> None:
    _, parent = preflight.freeze_parent(ROOT)
    source, legacy = (json.loads(parent[p]) for p in ("source_binding.json", "contract.json"))
    actual = read_session_records(FORMAL / "session")
    result = run_controls(
        read("protocol_contract.json"), source, legacy, actual["initial_state"], actual["events"]
    )
    assert result == read("direct_controls.json")
    assert result["attempted"] == result["rejected"] == 9
    assert result["both_initial_choices_admitted"]
    assert result["reject_update_admitted_without_claim"]
    assert result["committed_control_updates"] == result["generator_callbacks"] == 0
    assert result["kernel_calls"] == result["extra_complete_protocol_sessions"] == 0
    assert result["source_state_and_transcript_unchanged"]


def test_missing_actual_observation_is_not_fabricated_for_controls() -> None:
    result = run_controls({}, {}, {}, {}, [])
    assert result["status"] == "not_run_missing_actual_pending_state"
    assert result["both_initial_choices_admitted"] is False
    assert result["kernel_calls"] == 0


def test_registration_fsynced_before_session_is_created() -> None:
    receipt = read("registration_receipt.json")
    assert receipt["before_first_callback"] is True
    events = receipt["write_events"]
    assert [e["event_ordinal"] for e in events] == list(range(1, len(events) + 1))
    names = {e["relative_path"] for e in events}
    assert {
        "generator_registration.json",
        "source_authority.json",
        "protocol_contract.json",
    } <= names
    assert not any(name.startswith("session/") for name in names)
    assert all(
        [e["kind"] for e in events if e["relative_path"] == name]
        == ["file_fsync", "directory_fsync"]
        for name in names
    )


def test_committed_declared_members_match_current_sources() -> None:
    authority = read("source_authority.json")
    implementation = preflight.source_group(
        ROOT, SOURCE_COMMIT, SOURCE_TREE, preflight.SOURCE_PATHS
    )
    assert implementation == authority["implementation"]
    binding = read("generator_binding.json")
    registration = read("generator_registration.json")
    assert registration["fixture_source_member"]["sha256"] == binding["source_sha256"]
    assert read("registration_audit.json")["passed"] is True
