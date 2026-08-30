from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from trusted_synthesis.core.immutable_artifacts import write_immutable_artifact_directory
from trusted_synthesis.experiments.qa_realization_vnext.parent_authority_preflight import (
    AttackControl,
    QAParentAuthorityPreflight,
    RawReferenceBinding,
    SourceFileBinding,
)

_REPO_ROOT = Path(__file__).resolve().parents[2]
_FORMAL = (
    _REPO_ROOT
    / "trusted_data_synthesis/artifacts/qa_realization_vnext/"
    "parent_authority_v2_20260831"
)


def test_parent_authority_v2_formal_artifacts_revalidate_exact_bytes() -> None:
    report = QAParentAuthorityPreflight.model_validate_json(
        (_FORMAL / "report.json").read_bytes()
    )
    source_rows = tuple(
        SourceFileBinding.model_validate_json(line)
        for line in (_FORMAL / "source_manifest.jsonl").read_bytes().splitlines()
        if line
    )
    raw_rows = tuple(
        RawReferenceBinding.model_validate_json(line)
        for line in (_FORMAL / "raw_reference_manifest.jsonl").read_bytes().splitlines()
        if line
    )
    attacks = tuple(
        AttackControl.model_validate_json(line)
        for line in (_FORMAL / "attack_matrix.jsonl").read_bytes().splitlines()
        if line
    )
    artifact_manifest = json.loads((_FORMAL / "artifact_manifest.json").read_bytes())

    assert all(report.gates.values())
    assert report.source_file_count == len(source_rows) == 15
    assert report.raw_reference_file_count == len(raw_rows) == 3
    assert report.attack_control_count == report.rejected_attack_count == len(attacks) == 11
    assert all(row.passed and row.observed == "rejected" for row in attacks)
    assert all(
        hashlib.sha256((_REPO_ROOT / row.path).read_bytes()).hexdigest() == row.sha256
        for row in source_rows
    )
    assert all(
        hashlib.sha256((_REPO_ROOT / row.path).read_bytes()).hexdigest()
        == row.expected_sha256
        == row.observed_sha256
        for row in raw_rows
    )
    assert all(
        hashlib.sha256((_FORMAL / row["filename"]).read_bytes()).hexdigest()
        == row["sha256"]
        and (_FORMAL / row["filename"]).stat().st_size == row["byte_count"]
        for row in artifact_manifest["files"]
    )


def test_immutable_artifact_writer_rejects_overwrite_without_byte_drift(
    tmp_path: Path,
) -> None:
    output = tmp_path / "formal"
    write_immutable_artifact_directory(output, {"report.json": b"original\n"})

    with pytest.raises(FileExistsError, match="already exists"):
        write_immutable_artifact_directory(output, {"report.json": b"attacked\n"})

    assert (output / "report.json").read_bytes() == b"original\n"
    assert not output.with_name(".formal.write-lock").exists()
