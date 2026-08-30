from __future__ import annotations

from pathlib import Path

import pytest

from trusted_synthesis.experiments.qa_realization_vnext.release_authority import (
    QAReleaseAuthorityBundle,
    QAReleaseAuthorityError,
    build_qa_release_authority_bundle,
    load_and_reconstruct_qa_release_authority_bundle,
)
from trusted_synthesis.experiments.qa_realization_vnext.release_authority_preflight import (
    _run_attack_controls,
    load_qa_release_authority_artifact_directory,
    run_release_authority_preflight,
)
from trusted_synthesis.hashing import canonical_hash


@pytest.fixture(scope="module")
def authority_bundle() -> QAReleaseAuthorityBundle:
    return build_qa_release_authority_bundle(
        source_tree_id="a" * 40,
        source_archive_sha256="b" * 64,
        source_snapshot_manifest_sha256="c" * 64,
    )


def test_authority_bundle_json_reload_reconstructs_every_stage(
    authority_bundle: QAReleaseAuthorityBundle,
) -> None:
    reloaded = QAReleaseAuthorityBundle.model_validate_json(authority_bundle.model_dump_json())
    reconstructed = load_and_reconstruct_qa_release_authority_bundle(
        reloaded,
        expected_source_tree_id="a" * 40,
        expected_source_archive_sha256="b" * 64,
        expected_source_snapshot_manifest_sha256="c" * 64,
    )
    assert canonical_hash(reconstructed.model_dump(mode="json")) == canonical_hash(
        authority_bundle.model_dump(mode="json")
    )
    assert len(reloaded.release_selection.release_records) == 6
    assert len(reloaded.frozen_task_types) == 8
    assert len(reloaded.frozen_renderer_profile_ids) == 32


def test_authority_bundle_rejects_wrong_executed_source(
    authority_bundle: QAReleaseAuthorityBundle,
) -> None:
    with pytest.raises(QAReleaseAuthorityError) as captured:
        load_and_reconstruct_qa_release_authority_bundle(
            authority_bundle,
            expected_source_tree_id="0" * 40,
            expected_source_archive_sha256="b" * 64,
            expected_source_snapshot_manifest_sha256="c" * 64,
        )
    assert captured.value.reason_code == "full_source_snapshot_binding_mismatch"
    assert captured.value.stage == "source_snapshot"
    assert captured.value.target_validator_reached is True


def test_fully_rehashed_attacks_reach_exact_authority_gates(
    authority_bundle: QAReleaseAuthorityBundle,
) -> None:
    controls = _run_attack_controls(authority_bundle)
    counted = tuple(item for item in controls if item.counted_as_rejection_evidence)
    unrelated = next(item for item in controls if item.attack_id == "unrelated_pre_gate_exception")

    assert len(counted) == 12
    assert all(item.mutation_kind == "fully_rehashed" for item in counted)
    assert all(item.rejected and item.target_validator_reached for item in counted)
    assert unrelated.actual_exception_type == "RuntimeError"
    assert unrelated.counted_as_rejection_evidence is False


def test_preflight_publishes_once_and_exact_loader_rehashes_bytes(
    tmp_path: Path,
) -> None:
    source_manifest = tmp_path / "source_manifest.json"
    source_manifest.write_bytes(b'{"tree":"fixture"}\n')
    output = tmp_path / "authority"
    report = run_release_authority_preflight(
        source_tree_id="a" * 40,
        source_archive_sha256="b" * 64,
        source_manifest_path=source_manifest,
        output_dir=output,
    )
    assert load_qa_release_authority_artifact_directory(output) == report
    with pytest.raises(FileExistsError):
        run_release_authority_preflight(
            source_tree_id="a" * 40,
            source_archive_sha256="b" * 64,
            source_manifest_path=source_manifest,
            output_dir=output,
        )

    record_path = output / "release_records.jsonl"
    record_path.write_bytes(record_path.read_bytes() + b" ")
    with pytest.raises(ValueError, match="byte count mismatch|SHA-256 mismatch"):
        load_qa_release_authority_artifact_directory(output)
