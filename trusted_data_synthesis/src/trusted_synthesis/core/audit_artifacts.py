from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.hashing import canonical_hash

ATOMIC_AUDIT_CASE_VERSION = "atomic_audit_case.v2"


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class AtomicAuditCaseResult(FrozenModel):
    """Content-addressed result of one independently replayed hard-gate case."""

    case_id: str = Field(min_length=1)
    check_id: str = Field(min_length=1)
    subject_id: str = Field(min_length=1)
    input_artifact_ids: tuple[str, ...] = Field(min_length=1)
    output_artifact_ids: tuple[str, ...] = Field(min_length=1)
    implementation_manifest: dict[str, Any]
    implementation_manifest_hash: str = Field(min_length=1)
    implementation_artifact_uri: str = Field(min_length=1)
    implementation_artifact_sha256: str = Field(min_length=64, max_length=64)
    replay_implementation_manifest: dict[str, Any]
    replay_implementation_manifest_hash: str = Field(min_length=1)
    replay_implementation_artifact_uri: str = Field(min_length=1)
    replay_implementation_artifact_sha256: str = Field(min_length=64, max_length=64)
    result_payload: dict[str, Any]
    result_payload_hash: str = Field(min_length=1)
    replay_result_payload_hash: str = Field(min_length=1)
    artifact_uri: str = Field(min_length=1)
    artifact_sha256: str = Field(min_length=64, max_length=64)
    check_passed: bool
    replay_passed: Literal[True] = True
    schema_version: str = ATOMIC_AUDIT_CASE_VERSION

    @model_validator(mode="after")
    def validate_case(self) -> AtomicAuditCaseResult:
        if len(self.input_artifact_ids) != len(set(self.input_artifact_ids)):
            raise ValueError("atomic audit inputs must be unique")
        if len(self.output_artifact_ids) != len(set(self.output_artifact_ids)):
            raise ValueError("atomic audit outputs must be unique")
        expected_implementation_hash = canonical_hash(
            self.implementation_manifest,
            prefix="atomic_audit_implementation:",
        )
        expected_replay_hash = canonical_hash(
            self.replay_implementation_manifest,
            prefix="atomic_audit_replay_implementation:",
        )
        if self.implementation_manifest_hash != expected_implementation_hash:
            raise ValueError("atomic audit implementation manifest hash is invalid")
        if self.replay_implementation_manifest_hash != expected_replay_hash:
            raise ValueError("atomic audit replay implementation manifest hash is invalid")
        if self.implementation_artifact_sha256 != _payload_sha256(
            self.implementation_manifest
        ):
            raise ValueError("atomic audit implementation artifact SHA-256 is invalid")
        if self.replay_implementation_artifact_sha256 != _payload_sha256(
            self.replay_implementation_manifest
        ):
            raise ValueError("atomic audit replay implementation artifact SHA-256 is invalid")
        if self.implementation_manifest_hash == self.replay_implementation_manifest_hash:
            raise ValueError("atomic audit replay must use an independent implementation identity")
        if self.result_payload.get("check_id") != self.check_id:
            raise ValueError("atomic audit payload check identity is inconsistent")
        if self.result_payload.get("subject_id") != self.subject_id:
            raise ValueError("atomic audit payload subject identity is inconsistent")
        if self.result_payload.get("passed") is not self.check_passed:
            raise ValueError("atomic audit payload status is inconsistent")
        expected_payload_hash = canonical_hash(
            self.result_payload,
            prefix="atomic_audit_result_payload:",
        )
        if self.result_payload_hash != expected_payload_hash:
            raise ValueError("atomic audit result payload hash is invalid")
        if self.replay_result_payload_hash != expected_payload_hash:
            raise ValueError("atomic audit independent replay differs from the frozen result")
        if self.artifact_sha256 != _payload_sha256(self.result_payload):
            raise ValueError("atomic audit artifact SHA-256 is invalid")
        if self.case_id != atomic_audit_case_id(self):
            raise ValueError("atomic audit case identity is invalid")
        return self


def make_atomic_audit_case_result(
    *,
    check_id: str,
    subject_id: str,
    input_artifact_ids: Sequence[str],
    output_artifact_ids: Sequence[str],
    implementation_manifest: Mapping[str, Any],
    replay_implementation_manifest: Mapping[str, Any],
    check_passed: bool,
    result_details: Mapping[str, Any] | None = None,
    artifact_uri: str | None = None,
) -> AtomicAuditCaseResult:
    primary_manifest = dict(implementation_manifest)
    replay_manifest = dict(replay_implementation_manifest)
    implementation_hash = canonical_hash(
        primary_manifest,
        prefix="atomic_audit_implementation:",
    )
    replay_implementation_hash = canonical_hash(
        replay_manifest,
        prefix="atomic_audit_replay_implementation:",
    )
    payload = {
        "check_id": check_id,
        "subject_id": subject_id,
        "passed": check_passed,
        "details": dict(result_details or {}),
    }
    payload_hash = canonical_hash(payload, prefix="atomic_audit_result_payload:")
    sha256 = _payload_sha256(payload)
    values = {
        "check_id": check_id,
        "subject_id": subject_id,
        "input_artifact_ids": tuple(sorted(input_artifact_ids)),
        "output_artifact_ids": tuple(sorted(output_artifact_ids)),
        "implementation_manifest": primary_manifest,
        "implementation_manifest_hash": implementation_hash,
        "implementation_artifact_uri": (
            f"embedded://atomic-audit-implementation/{implementation_hash}"
        ),
        "implementation_artifact_sha256": _payload_sha256(primary_manifest),
        "replay_implementation_manifest": replay_manifest,
        "replay_implementation_manifest_hash": replay_implementation_hash,
        "replay_implementation_artifact_uri": (
            f"embedded://atomic-audit-replay-implementation/{replay_implementation_hash}"
        ),
        "replay_implementation_artifact_sha256": _payload_sha256(replay_manifest),
        "result_payload": payload,
        "result_payload_hash": payload_hash,
        "replay_result_payload_hash": payload_hash,
        "artifact_uri": artifact_uri or f"embedded://atomic-audit/{sha256}",
        "artifact_sha256": sha256,
        "check_passed": check_passed,
        "schema_version": ATOMIC_AUDIT_CASE_VERSION,
    }
    provisional = AtomicAuditCaseResult.model_construct(case_id="pending", **values)
    return AtomicAuditCaseResult(case_id=atomic_audit_case_id(provisional), **values)


def atomic_audit_case_id(value: AtomicAuditCaseResult) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"case_id"}),
        prefix="atomic_audit_case:",
    )


def _payload_sha256(payload: Mapping[str, Any]) -> str:
    serialized = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(serialized).hexdigest()
