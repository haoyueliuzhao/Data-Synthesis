from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from trusted_synthesis.experiments.qa_realization_vnext import (
    release_authority_envelope_independent_audit as audit,
)


@pytest.fixture(scope="module")
def payloads() -> dict[str, bytes]:
    root = (
        Path(__file__).resolve().parents[1]
        / "artifacts/qa_realization_vnext/qa_release_authority_envelope_v4_20260831"
    )
    return audit._load_payloads(root)


def test_independent_catalog_reconstruction_passes(payloads: dict[str, bytes]) -> None:
    result = audit._validate_fast_catalogs(payloads)
    assert result["artifact_count"] == 15
    assert result["release_record_count"] == 6
    assert result["attack_rejection_count"] == 23
    assert result["provider_calls"] == 0


def test_git_tree_reconstruction_treats_file_rows_as_leaves() -> None:
    content = b"payload\n"
    row = {
        "path": "file.txt",
        "kind": "file",
        "executable": False,
        "git_blob_id": audit._git_blob_id(content),
    }
    assert audit._git_tree_id((row,)) == "5c71942e43e4451d2770e34da7784705c90c63c1"


def test_independent_external_anchor_rejects_fully_rehashed_envelope(
    payloads: dict[str, bytes],
) -> None:
    attacked = dict(payloads)
    envelope = audit._parse_json(attacked, "envelope.json")
    envelope["report_markdown_byte_count"] += 1
    envelope["envelope_id"] = audit._identity(
        envelope,
        field="envelope_id",
        prefix="qa_release_authority_envelope:",
    )
    attacked["envelope.json"] = audit._json_bytes(envelope)
    with pytest.raises(audit.IndependentAuditError) as captured:
        audit._validate_fast_catalogs(attacked)
    assert captured.value.stage == "external_anchor"
    assert captured.value.reason_code == "envelope_external_anchor_mismatch"


def test_latest_audit_authorization_bytes_are_exact() -> None:
    path = Path(
        "/home/zhuxinrui/.codex/attachments/d1038bec-9e84-4c38-8a36-82efa4337202/pasted-text.txt"
    )
    content = path.read_bytes()
    assert len(content) == 9_348
    assert hashlib.sha256(content).hexdigest() == (
        "925b1818862ed22852b117f62a8cbde438c568f9e852bb6c35bb88c181a2bb1f"
    )
