from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import tarfile
import tempfile
from collections.abc import Callable, Mapping
from pathlib import Path, PurePosixPath
from typing import Any, TypeVar

from pydantic import BaseModel

from trusted_synthesis.canonical_json import canonical_json_bytes
from trusted_synthesis.core.evaluation.realization_binding import bind_realization_execution
from trusted_synthesis.core.immutable_artifacts import write_immutable_artifact_directory
from trusted_synthesis.core.release.diversity_selector import DiversityAwareReleaseSelection
from trusted_synthesis.experiments.qa_realization_vnext.release_authority import (
    QAReleaseAuthorityBundle,
    QAReleaseAuthorityError,
    build_qa_release_authority_bundle,
    load_and_reconstruct_qa_release_authority_bundle,
)
from trusted_synthesis.experiments.qa_realization_vnext.release_authority_envelope import (
    FROZEN_ATTACK_IDS,
    AuthorityArtifactRow,
    AuthorityAttackAudit,
    AuthorityAttackControl,
    QAReleaseAuthorityArtifactManifest,
    QAReleaseAuthorityAuthorization,
    QAReleaseAuthorityEnvelope,
    QAReleaseAuthorityReport,
    QAReleasePopulationManifest,
    QAReleaseSourceProjection,
    RuntimeEnvironmentIdentity,
    SourceSnapshotEntry,
    SourceSnapshotManifest,
    build_authorization,
    build_population_manifest,
    capture_runtime_environment,
)
from trusted_synthesis.experiments.qa_realization_vnext.release_authority_preflight import (
    _assessment_decision_attack,
    _operation_contract_attack,
    _plan_dependency_attack,
    _quota_attack,
    _raw_evidence_attack,
    _release_plan_attack,
    _source_tree_attack,
    _surface_validation_attack,
    _task_tools_attack,
    _weight_pairing_attack,
)
from trusted_synthesis.hashing import canonical_hash

T = TypeVar("T")

EXECUTED_MODULE_PATH = (
    "trusted_data_synthesis/src/trusted_synthesis/experiments/qa_realization_vnext/"
    "release_authority_envelope_preflight.py"
)
CORE_ARTIFACT_NAMES = (
    "attack_audit.json",
    "attack_controls.json",
    "authorization.json",
    "external_audit.txt",
    "qa_release_authority_bundle.json",
    "release_population.json",
    "release_records.jsonl",
    "release_selection.json",
    "runtime_environment.json",
    "source_projection.json",
    "source_snapshot_manifest.json",
)
DIRECTORY_ARTIFACT_NAMES = frozenset(
    (*CORE_ARTIFACT_NAMES, "artifact_manifest.json", "envelope.json", "report.json", "report.md")
)


def _identity(value: BaseModel, *, field: str, prefix: str) -> str:
    return canonical_hash(value.model_dump(mode="json", exclude={field}), prefix=prefix)


def _json_bytes(value: Any) -> bytes:
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json")
    return canonical_json_bytes(value) + b"\n"


def _jsonl_bytes(values: Any) -> bytes:
    return b"".join(_json_bytes(value) for value in values)


def _sha256_path(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    byte_count = 0
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
            byte_count += len(chunk)
    return digest.hexdigest(), byte_count


def _git_blob_id(content: bytes) -> str:
    header = f"blob {len(content)}\0".encode()
    return hashlib.sha1(header + content, usedforsecurity=False).hexdigest()


def _git_tree_id(entries: tuple[SourceSnapshotEntry, ...]) -> str:
    root: dict[str, Any] = {}
    for entry in entries:
        parts = entry.path.split("/")
        node = root
        for part in parts[:-1]:
            child = node.setdefault(part, {})
            if not isinstance(child, dict):
                raise ValueError("source archive contains a file/directory collision")
            node = child
        if parts[-1] in node:
            raise ValueError("source archive contains duplicate Git tree entries")
        node[parts[-1]] = entry

    def hash_tree(node: dict[str, Any]) -> str:
        body = bytearray()
        for name in sorted(node, key=lambda item: item.encode("utf-8")):
            value = node[name]
            if isinstance(value, dict):
                mode = "40000"
                object_id = hash_tree(value)
            else:
                mode = (
                    "120000"
                    if value.kind == "symlink"
                    else ("100755" if value.executable else "100644")
                )
                object_id = value.git_blob_id
            body.extend(mode.encode("ascii"))
            body.extend(b" ")
            body.extend(name.encode("utf-8"))
            body.extend(b"\0")
            body.extend(bytes.fromhex(object_id))
        header = f"tree {len(body)}\0".encode()
        return hashlib.sha1(header + body, usedforsecurity=False).hexdigest()

    return hash_tree(root)


def _validated_archive_path(name: str) -> PurePosixPath:
    path = PurePosixPath(name)
    if not name or path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise ValueError("Git archive contains an unsafe member path")
    return path


def _archive_commit_id(source_archive_path: Path) -> str:
    with source_archive_path.open("rb") as handle:
        result = subprocess.run(
            ("git", "get-tar-commit-id"),
            stdin=handle,
            capture_output=True,
            check=False,
        )
    commit_id = result.stdout.decode("ascii", errors="strict").strip()
    if result.returncode != 0 or len(commit_id) != 40:
        raise ValueError("source archive lacks an exact embedded Git commit identity")
    return commit_id


def _archive_entries(
    source_archive_path: Path,
    *,
    extract_root: Path | None = None,
) -> tuple[SourceSnapshotEntry, ...]:
    if extract_root is not None:
        extract_root.mkdir(parents=True, exist_ok=False)
    entries: list[SourceSnapshotEntry] = []
    observed: set[str] = set()
    with tarfile.open(source_archive_path, mode="r:") as archive:
        for member in archive.getmembers():
            path = _validated_archive_path(member.name.rstrip("/"))
            relative = path.as_posix()
            target = extract_root.joinpath(*path.parts) if extract_root is not None else None
            if member.isdir():
                if target is not None:
                    target.mkdir(parents=True, exist_ok=True)
                continue
            if relative in observed:
                raise ValueError("Git archive contains duplicate file members")
            observed.add(relative)
            if member.isfile():
                handle = archive.extractfile(member)
                if handle is None:
                    raise ValueError("Git archive regular file cannot be read")
                content = handle.read()
                kind = "file"
                executable = bool(member.mode & 0o111)
                if target is not None:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(content)
                    target.chmod(0o755 if executable else 0o644)
            elif member.issym():
                content = member.linkname.encode("utf-8")
                kind = "symlink"
                executable = False
                if target is not None:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    os.symlink(member.linkname, target)
            else:
                raise ValueError("Git archive contains a non-Git file member type")
            entries.append(
                SourceSnapshotEntry(
                    path=relative,
                    kind=kind,
                    executable=executable,
                    byte_count=len(content),
                    sha256=hashlib.sha256(content).hexdigest(),
                    git_blob_id=_git_blob_id(content),
                )
            )
    if not entries:
        raise ValueError("Git archive contains no files")
    return tuple(sorted(entries, key=lambda row: row.path))


def extract_git_archive(source_archive_path: Path, extract_root: Path) -> None:
    """Safely extract only regular Git files and symlinks into a new directory."""

    _archive_entries(source_archive_path, extract_root=extract_root)


def _validate_extracted_root(
    root: Path,
    entries: tuple[SourceSnapshotEntry, ...],
) -> None:
    expected = {row.path: row for row in entries}
    observed_paths = {
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file() or path.is_symlink()
    }
    if observed_paths != set(expected):
        raise ValueError("executed source root is not the exact archive projection")
    for relative, row in expected.items():
        path = root / relative
        if path.is_symlink():
            content = os.readlink(path).encode("utf-8")
            kind = "symlink"
            executable = False
        else:
            content = path.read_bytes()
            kind = "file"
            executable = bool(path.stat().st_mode & 0o111)
        if (
            kind != row.kind
            or executable is not row.executable
            or len(content) != row.byte_count
            or hashlib.sha256(content).hexdigest() != row.sha256
            or _git_blob_id(content) != row.git_blob_id
        ):
            raise ValueError("executed source file differs from its archive member")


def verify_source_archive_projection(
    *,
    source_archive_path: Path,
    source_commit_id: str,
    source_tree_id: str,
    executed_source_root: Path | None = None,
) -> tuple[QAReleaseSourceProjection, SourceSnapshotManifest]:
    """Derive commit, manifest, and Git tree from one mandatory archive."""

    archive_sha, archive_bytes = _sha256_path(source_archive_path)
    archive_commit = _archive_commit_id(source_archive_path)
    entries = _archive_entries(source_archive_path)
    derived_tree_id = _git_tree_id(entries)
    if archive_commit != source_commit_id:
        raise ValueError("source archive embedded commit identity mismatch")
    if derived_tree_id != source_tree_id:
        raise ValueError("source archive recomputed Git tree identity mismatch")
    if executed_source_root is not None:
        _validate_extracted_root(executed_source_root, entries)
    manifest_payload = {
        "source_commit_id": source_commit_id,
        "source_tree_id": derived_tree_id,
        "source_archive_sha256": archive_sha,
        "source_archive_byte_count": archive_bytes,
        "files": entries,
        "file_count": len(entries),
        "schema_version": "qa_release_source_snapshot_manifest.v2",
    }
    provisional_manifest = SourceSnapshotManifest.model_construct(
        manifest_id="pending",
        **manifest_payload,
    )
    manifest = SourceSnapshotManifest(
        manifest_id=_identity(
            provisional_manifest,
            field="manifest_id",
            prefix="qa_release_source_snapshot_manifest:",
        ),
        **manifest_payload,
    )
    manifest_bytes = _json_bytes(manifest)
    executed_module = next(
        (row for row in entries if row.path == EXECUTED_MODULE_PATH),
        None,
    )
    if executed_module is None:
        raise ValueError("source archive omits the executed authority module")
    projection_payload = {
        "source_commit_id": source_commit_id,
        "source_tree_id": derived_tree_id,
        "archive_embedded_commit_id": archive_commit,
        "source_archive_sha256": archive_sha,
        "source_archive_byte_count": archive_bytes,
        "source_manifest_id": manifest.manifest_id,
        "source_manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
        "source_manifest_byte_count": len(manifest_bytes),
        "source_manifest_file_count": len(entries),
        "executed_module_path": EXECUTED_MODULE_PATH,
        "executed_module_sha256": executed_module.sha256,
        "projection_contract": "git_archive_to_extracted_tree_to_git_tree.v1",
        "schema_version": "qa_release_source_projection.v1",
    }
    provisional_projection = QAReleaseSourceProjection.model_construct(
        source_projection_id="pending",
        **projection_payload,
    )
    projection = QAReleaseSourceProjection(
        source_projection_id=_identity(
            provisional_projection,
            field="source_projection_id",
            prefix="qa_release_source_projection:",
        ),
        **projection_payload,
    )
    return projection, manifest


def _authority_call(
    *,
    stage: str,
    reason_code: str,
    action: Callable[[], T],
    required_message: str | None = None,
) -> T:
    try:
        return action()
    except QAReleaseAuthorityError:
        raise
    except (ValueError, OSError, KeyError, json.JSONDecodeError) as exc:
        if required_message is not None and required_message not in str(exc):
            raise QAReleaseAuthorityError(
                reason_code="unexpected_validator_failure",
                stage="attack_measurement",
                message=str(exc),
            ) from exc
        raise QAReleaseAuthorityError(
            reason_code=reason_code,
            stage=stage,
            message=str(exc),
        ) from exc


def _build_attack_audit(
    controls: tuple[AuthorityAttackControl, ...],
    unrelated: AuthorityAttackControl,
) -> AuthorityAttackAudit:
    observed = tuple(row.attack_id for row in controls)
    payload = {
        "frozen_attack_ids": FROZEN_ATTACK_IDS,
        "controls": controls,
        "unrelated_exception_control": unrelated,
        "missing_attack_ids": tuple(item for item in FROZEN_ATTACK_IDS if item not in observed),
        "duplicate_attack_ids": tuple(
            sorted({item for item in observed if observed.count(item) > 1})
        ),
        "extra_attack_ids": tuple(item for item in observed if item not in FROZEN_ATTACK_IDS),
        "schema_version": "qa_release_authority_attack_audit.v1",
    }
    provisional = AuthorityAttackAudit.model_construct(attack_audit_id="pending", **payload)
    return AuthorityAttackAudit(
        attack_audit_id=_identity(
            provisional,
            field="attack_audit_id",
            prefix="qa_release_authority_attack_audit:",
        ),
        **payload,
    )


def _artifact_manifest(payloads: Mapping[str, bytes]) -> QAReleaseAuthorityArtifactManifest:
    rows = tuple(
        AuthorityArtifactRow(
            name=name,
            sha256=hashlib.sha256(payloads[name]).hexdigest(),
            byte_count=len(payloads[name]),
        )
        for name in sorted(payloads)
    )
    artifact_root = canonical_hash(rows, prefix="qa_release_authority_artifact_root:")
    payload = {
        "artifact_root": artifact_root,
        "artifacts": rows,
        "schema_version": "qa_release_authority_artifact_manifest.v2",
    }
    provisional = QAReleaseAuthorityArtifactManifest.model_construct(
        artifact_manifest_id="pending",
        **payload,
    )
    return QAReleaseAuthorityArtifactManifest(
        artifact_manifest_id=_identity(
            provisional,
            field="artifact_manifest_id",
            prefix="qa_release_authority_artifact_manifest:",
        ),
        **payload,
    )


def _build_report(
    *,
    authorization: QAReleaseAuthorityAuthorization,
    source_projection: QAReleaseSourceProjection,
    population: QAReleasePopulationManifest,
    runtime: RuntimeEnvironmentIdentity,
    bundle: QAReleaseAuthorityBundle,
    attack_audit: AuthorityAttackAudit,
    artifact_manifest: QAReleaseAuthorityArtifactManifest,
) -> QAReleaseAuthorityReport:
    selection = bundle.release_selection
    payload = {
        "status": "passed",
        "authorization_id": authorization.authorization_id,
        "source_projection_id": source_projection.source_projection_id,
        "population_id": population.population_id,
        "runtime_environment_id": runtime.runtime_environment_id,
        "authority_bundle_id": bundle.authority_bundle_id,
        "release_selection_id": selection.selection_id,
        "attack_audit_id": attack_audit.attack_audit_id,
        "artifact_root": artifact_manifest.artifact_root,
        "artifact_manifest_id": artifact_manifest.artifact_manifest_id,
        "fixture_count": len(bundle.fixture_inputs),
        "release_record_count": len(selection.release_records),
        "selected_record_count": len(selection.selected_execution_binding_ids),
        "frozen_task_type_count": len(bundle.frozen_task_types),
        "frozen_renderer_profile_count": len(bundle.frozen_renderer_profile_ids),
        "exact_attack_count": len(attack_audit.controls),
        "exact_attack_rejection_count": sum(
            row.counted_as_rejection_evidence for row in attack_audit.controls
        ),
        "provider_calls": 0,
        "unrelated_exception_counted": (
            attack_audit.unrelated_exception_control.counted_as_rejection_evidence
        ),
        "archive_backed_pilot_authorized": False,
        "production_authorized": False,
        "schema_version": "qa_release_authority_report.v2",
    }
    provisional = QAReleaseAuthorityReport.model_construct(report_id="pending", **payload)
    return QAReleaseAuthorityReport(
        report_id=_identity(
            provisional,
            field="report_id",
            prefix="qa_release_authority_report:",
        ),
        **payload,
    )


def _markdown_report(report: QAReleaseAuthorityReport) -> bytes:
    return (
        "# QA Release Authority External Envelope Preflight\n\n"
        f"- Status: **{report.status}**\n"
        f"- Authorization: `{report.authorization_id}`\n"
        f"- Source projection: `{report.source_projection_id}`\n"
        f"- Exact population: `{report.population_id}`\n"
        f"- Runtime environment: `{report.runtime_environment_id}`\n"
        f"- Authority bundle: `{report.authority_bundle_id}`\n"
        f"- Release selection: `{report.release_selection_id}`\n"
        f"- Exact typed attacks: {report.exact_attack_rejection_count} / "
        f"{report.exact_attack_count}\n"
        f"- Provider calls: {report.provider_calls}\n"
        "- Archive-backed Pilot authorized: no\n"
        "- Production authorized: no\n"
        f"- Artifact root: `{report.artifact_root}`\n"
    ).encode()


def _build_payloads(
    *,
    external_audit_bytes: bytes,
    authorization: QAReleaseAuthorityAuthorization,
    source_projection: QAReleaseSourceProjection,
    source_manifest: SourceSnapshotManifest,
    population: QAReleasePopulationManifest,
    runtime: RuntimeEnvironmentIdentity,
    bundle: QAReleaseAuthorityBundle,
    attack_audit: AuthorityAttackAudit,
) -> tuple[dict[str, bytes], QAReleaseAuthorityEnvelope]:
    core_payloads = {
        "attack_audit.json": _json_bytes(attack_audit),
        "attack_controls.json": _json_bytes(attack_audit.controls),
        "authorization.json": _json_bytes(authorization),
        "external_audit.txt": external_audit_bytes,
        "qa_release_authority_bundle.json": _json_bytes(bundle),
        "release_population.json": _json_bytes(population),
        "release_records.jsonl": _jsonl_bytes(bundle.release_selection.release_records),
        "release_selection.json": _json_bytes(bundle.release_selection),
        "runtime_environment.json": _json_bytes(runtime),
        "source_projection.json": _json_bytes(source_projection),
        "source_snapshot_manifest.json": _json_bytes(source_manifest),
    }
    artifact_manifest = _artifact_manifest(core_payloads)
    report = _build_report(
        authorization=authorization,
        source_projection=source_projection,
        population=population,
        runtime=runtime,
        bundle=bundle,
        attack_audit=attack_audit,
        artifact_manifest=artifact_manifest,
    )
    report_markdown = _markdown_report(report)
    envelope_payload = {
        "authorization": authorization,
        "source_projection": source_projection,
        "population_manifest": population,
        "runtime_environment": runtime,
        "authority_bundle": bundle,
        "release_selection": bundle.release_selection,
        "release_records": bundle.release_selection.release_records,
        "attack_audit": attack_audit,
        "artifact_manifest": artifact_manifest,
        "report": report,
        "report_markdown_sha256": hashlib.sha256(report_markdown).hexdigest(),
        "report_markdown_byte_count": len(report_markdown),
        "schema_version": "qa_release_authority_envelope.v1",
    }
    provisional = QAReleaseAuthorityEnvelope.model_construct(
        envelope_id="pending",
        **envelope_payload,
    )
    envelope = QAReleaseAuthorityEnvelope(
        envelope_id=_identity(
            provisional,
            field="envelope_id",
            prefix="qa_release_authority_envelope:",
        ),
        **envelope_payload,
    )
    payloads = {
        **core_payloads,
        "artifact_manifest.json": _json_bytes(artifact_manifest),
        "envelope.json": _json_bytes(envelope),
        "report.json": _json_bytes(report),
        "report.md": report_markdown,
    }
    return payloads, envelope


def _validate_external_audit(
    authorization: QAReleaseAuthorityAuthorization,
    audit_bytes: bytes,
) -> None:
    if (
        len(audit_bytes) != authorization.external_audit_byte_count
        or hashlib.sha256(audit_bytes).hexdigest() != authorization.external_audit_sha256
    ):
        raise ValueError("external audit bytes differ from the authorization parent")


def _require_exact_attack_ids(observed_ids: tuple[str, ...]) -> None:
    if observed_ids != FROZEN_ATTACK_IDS:
        raise ValueError("authority attack registry membership or order is not exact")


def _load_json(payloads: Mapping[str, bytes], name: str) -> Any:
    return json.loads(payloads[name])


def _load_jsonl(payload: bytes) -> tuple[Any, ...]:
    return tuple(json.loads(line) for line in payload.splitlines() if line)


def _validate_artifact_payloads_before_source_replay(
    payloads: Mapping[str, bytes],
    *,
    expected_envelope_id: str,
    expected_authorization_id: str,
    expected_population_id: str,
    external_audit_bytes: bytes,
) -> tuple[
    QAReleaseAuthorityEnvelope,
    QAReleaseAuthorityAuthorization,
    QAReleaseAuthorityArtifactManifest,
    QAReleaseAuthorityReport,
]:
    if set(payloads) != DIRECTORY_ARTIFACT_NAMES:
        raise QAReleaseAuthorityError(
            reason_code="artifact_membership_not_exact",
            stage="artifact_catalog",
            message="QA release authority directory membership is not exact",
        )
    envelope = _authority_call(
        stage="envelope",
        reason_code="envelope_schema_or_identity_invalid",
        action=lambda: QAReleaseAuthorityEnvelope.model_validate(
            _load_json(payloads, "envelope.json")
        ),
    )
    if envelope.envelope_id != expected_envelope_id:
        raise QAReleaseAuthorityError(
            reason_code="external_envelope_anchor_mismatch",
            stage="external_anchor",
            message="envelope identity differs from the external expected identity",
        )
    if envelope.authorization.authorization_id != expected_authorization_id:
        raise QAReleaseAuthorityError(
            reason_code="external_authorization_anchor_mismatch",
            stage="external_anchor",
            message="authorization identity differs from the external expected identity",
        )
    if envelope.population_manifest.population_id != expected_population_id:
        raise QAReleaseAuthorityError(
            reason_code="external_population_anchor_mismatch",
            stage="external_anchor",
            message="population identity differs from the external expected identity",
        )
    authorization = _authority_call(
        stage="authorization",
        reason_code="authorization_sidecar_invalid",
        action=lambda: QAReleaseAuthorityAuthorization.model_validate(
            _load_json(payloads, "authorization.json")
        ),
    )
    if authorization != envelope.authorization:
        raise QAReleaseAuthorityError(
            reason_code="authorization_cross_catalog_mismatch",
            stage="authorization",
            message="authorization sidecar differs from the top envelope",
        )
    _authority_call(
        stage="authorization",
        reason_code="external_audit_bytes_mismatch",
        action=lambda: _validate_external_audit(authorization, external_audit_bytes),
    )
    if payloads["external_audit.txt"] != external_audit_bytes:
        raise QAReleaseAuthorityError(
            reason_code="external_audit_sidecar_mismatch",
            stage="authorization",
            message="frozen external audit sidecar differs from supplied external bytes",
        )
    artifact_manifest = _authority_call(
        stage="artifact_catalog",
        reason_code="artifact_manifest_invalid",
        action=lambda: QAReleaseAuthorityArtifactManifest.model_validate(
            _load_json(payloads, "artifact_manifest.json")
        ),
    )
    if artifact_manifest != envelope.artifact_manifest:
        raise QAReleaseAuthorityError(
            reason_code="artifact_manifest_cross_envelope_mismatch",
            stage="envelope",
            message="artifact manifest sidecar differs from the top envelope",
        )
    if tuple(row.name for row in artifact_manifest.artifacts) != CORE_ARTIFACT_NAMES:
        raise QAReleaseAuthorityError(
            reason_code="artifact_catalog_membership_not_exact",
            stage="artifact_catalog",
            message="artifact manifest does not catalog the exact semantic sidecars",
        )
    for row in artifact_manifest.artifacts:
        content = payloads[row.name]
        if len(content) != row.byte_count or hashlib.sha256(content).hexdigest() != row.sha256:
            raise QAReleaseAuthorityError(
                reason_code="artifact_catalog_bytes_mismatch",
                stage="artifact_catalog",
                message=f"artifact bytes differ for {row.name}",
            )
    report = _authority_call(
        stage="report",
        reason_code="report_schema_or_identity_invalid",
        action=lambda: QAReleaseAuthorityReport.model_validate(_load_json(payloads, "report.json")),
    )
    if report != envelope.report:
        raise QAReleaseAuthorityError(
            reason_code="report_cross_envelope_mismatch",
            stage="report",
            message="content-addressed report sidecar differs from the top envelope",
        )
    markdown = payloads["report.md"]
    if (
        len(markdown) != envelope.report_markdown_byte_count
        or hashlib.sha256(markdown).hexdigest() != envelope.report_markdown_sha256
        or markdown != _markdown_report(report)
    ):
        raise QAReleaseAuthorityError(
            reason_code="report_markdown_bytes_mismatch",
            stage="report_markdown",
            message="Markdown report is not the exact report projection",
        )
    return envelope, authorization, artifact_manifest, report


def validate_qa_release_authority_payloads(
    payloads: Mapping[str, bytes],
    *,
    expected_envelope_id: str,
    expected_authorization_id: str,
    expected_population_id: str,
    external_audit_bytes: bytes,
    source_archive_path: Path,
) -> QAReleaseAuthorityReport:
    envelope, authorization, artifact_manifest, report = (
        _validate_artifact_payloads_before_source_replay(
            payloads,
            expected_envelope_id=expected_envelope_id,
            expected_authorization_id=expected_authorization_id,
            expected_population_id=expected_population_id,
            external_audit_bytes=external_audit_bytes,
        )
    )
    with tempfile.TemporaryDirectory(prefix="qa-release-source-loader-") as temporary:
        extracted_root = Path(temporary) / "source"
        _authority_call(
            stage="source_projection",
            reason_code="source_archive_projection_invalid",
            action=lambda: extract_git_archive(source_archive_path, extracted_root),
        )
        projection, source_manifest = _authority_call(
            stage="source_projection",
            reason_code="source_archive_projection_invalid",
            action=lambda: verify_source_archive_projection(
                source_archive_path=source_archive_path,
                source_commit_id=envelope.source_projection.source_commit_id,
                source_tree_id=envelope.source_projection.source_tree_id,
                executed_source_root=extracted_root,
            ),
        )
        if projection != envelope.source_projection:
            raise QAReleaseAuthorityError(
                reason_code="source_projection_cross_envelope_mismatch",
                stage="source_projection",
                message="archive-derived source projection differs from the top envelope",
            )
        persisted_manifest = _authority_call(
            stage="source_projection",
            reason_code="source_manifest_sidecar_invalid",
            action=lambda: SourceSnapshotManifest.model_validate(
                _load_json(payloads, "source_snapshot_manifest.json")
            ),
        )
        if persisted_manifest != source_manifest:
            raise QAReleaseAuthorityError(
                reason_code="source_manifest_cross_projection_mismatch",
                stage="source_projection",
                message="source manifest sidecar differs from the archive projection",
            )
        runtime = _authority_call(
            stage="runtime_environment",
            reason_code="runtime_environment_sidecar_invalid",
            action=lambda: RuntimeEnvironmentIdentity.model_validate(
                _load_json(payloads, "runtime_environment.json")
            ),
        )
        observed_runtime = capture_runtime_environment(extracted_root)
        if runtime != observed_runtime or runtime != envelope.runtime_environment:
            raise QAReleaseAuthorityError(
                reason_code="runtime_environment_mismatch",
                stage="runtime_environment",
                message="executing runtime differs from the frozen environment identity",
            )

    bundle = _authority_call(
        stage="bundle_schema",
        reason_code="bundle_sidecar_invalid",
        action=lambda: QAReleaseAuthorityBundle.model_validate(
            _load_json(payloads, "qa_release_authority_bundle.json")
        ),
    )
    if bundle != envelope.authority_bundle:
        raise QAReleaseAuthorityError(
            reason_code="bundle_cross_envelope_mismatch",
            stage="envelope",
            message="authority bundle sidecar differs from the top envelope",
        )
    load_and_reconstruct_qa_release_authority_bundle(
        bundle,
        expected_source_tree_id=envelope.source_projection.source_tree_id,
        expected_source_archive_sha256=envelope.source_projection.source_archive_sha256,
        expected_source_snapshot_manifest_sha256=envelope.source_projection.source_manifest_sha256,
    )
    population = _authority_call(
        stage="release_population",
        reason_code="release_population_sidecar_invalid",
        action=lambda: QAReleasePopulationManifest.model_validate(
            _load_json(payloads, "release_population.json")
        ),
    )
    expected_population = build_population_manifest(
        authorization=authorization,
        source_projection=envelope.source_projection,
        bundle=bundle,
    )
    if population != expected_population or population != envelope.population_manifest:
        raise QAReleaseAuthorityError(
            reason_code="release_population_exact_set_mismatch",
            stage="release_population",
            message="persisted release population is not the exact source-derived set",
        )
    selection = _authority_call(
        stage="release_selection",
        reason_code="release_selection_sidecar_invalid",
        action=lambda: DiversityAwareReleaseSelection.model_validate(
            _load_json(payloads, "release_selection.json")
        ),
    )
    records = tuple(
        type(selection.release_records[0]).model_validate(row)
        for row in _load_jsonl(payloads["release_records.jsonl"])
    )
    if selection != bundle.release_selection or records != selection.release_records:
        raise QAReleaseAuthorityError(
            reason_code="release_catalog_cross_parent_mismatch",
            stage="release_catalogs",
            message="selection or records sidecar differs from the embedded authority objects",
        )
    controls = tuple(
        AuthorityAttackControl.model_validate(row)
        for row in _load_json(payloads, "attack_controls.json")
    )
    attack_audit = _authority_call(
        stage="attack_audit",
        reason_code="attack_audit_sidecar_invalid",
        action=lambda: AuthorityAttackAudit.model_validate(
            _load_json(payloads, "attack_audit.json")
        ),
    )
    if controls != attack_audit.controls or attack_audit != envelope.attack_audit:
        raise QAReleaseAuthorityError(
            reason_code="attack_audit_cross_catalog_mismatch",
            stage="attack_audit",
            message="attack controls and audit are not the exact top-envelope set",
        )
    expected_report = _build_report(
        authorization=authorization,
        source_projection=envelope.source_projection,
        population=population,
        runtime=envelope.runtime_environment,
        bundle=bundle,
        attack_audit=attack_audit,
        artifact_manifest=artifact_manifest,
    )
    if report != expected_report:
        raise QAReleaseAuthorityError(
            reason_code="report_not_source_derived",
            stage="report",
            message="report fields differ from reconstructed authority parents",
        )
    return report


def load_qa_release_authority_envelope_directory(
    output_dir: Path,
    *,
    expected_envelope_id: str,
    expected_authorization_id: str,
    expected_population_id: str,
    external_audit_path: Path,
    source_archive_path: Path,
) -> dict[str, Any]:
    payloads = {path.name: path.read_bytes() for path in output_dir.iterdir() if path.is_file()}
    report = validate_qa_release_authority_payloads(
        payloads,
        expected_envelope_id=expected_envelope_id,
        expected_authorization_id=expected_authorization_id,
        expected_population_id=expected_population_id,
        external_audit_bytes=external_audit_path.read_bytes(),
        source_archive_path=source_archive_path,
    )
    return report.model_dump(mode="json")


def _typed_validator_action(
    action: Callable[[], Any],
    *,
    stage: str,
    reason_code: str,
    required_message: str,
) -> None:
    _authority_call(
        stage=stage,
        reason_code=reason_code,
        action=action,
        required_message=required_message,
    )


def _capture_attack(
    attack_id: str,
    expected_reason_code: str,
    expected_stage: str,
    action: Callable[[], Any],
) -> AuthorityAttackControl:
    actual_type = actual_reason = actual_stage = ""
    try:
        action()
    except Exception as exc:
        actual_type = type(exc).__name__
        if isinstance(exc, QAReleaseAuthorityError):
            actual_reason = exc.reason_code
            actual_stage = exc.stage
        else:
            actual_reason = str(exc)
    exact = (
        actual_type == "QAReleaseAuthorityError"
        and actual_reason == expected_reason_code
        and actual_stage == expected_stage
    )
    return AuthorityAttackControl(
        attack_id=attack_id,
        expected_reason_code=expected_reason_code,
        expected_stage=expected_stage,
        actual_exception_type=actual_type,
        actual_reason_code=actual_reason,
        actual_stage=actual_stage,
        target_validator_reached=exact,
        rejected=exact,
        counted_as_rejection_evidence=exact,
    )


def _placeholder_controls() -> tuple[AuthorityAttackControl, ...]:
    return tuple(
        AuthorityAttackControl(
            attack_id=attack_id,
            expected_reason_code=reason,
            expected_stage=stage,
            actual_exception_type="QAReleaseAuthorityError",
            actual_reason_code=reason,
            actual_stage=stage,
            target_validator_reached=True,
            rejected=True,
            counted_as_rejection_evidence=True,
        )
        for attack_id, reason, stage in _attack_expectations()
    )


def _unrelated_exception_control() -> AuthorityAttackControl:
    return AuthorityAttackControl(
        attack_id="unrelated_pre_gate_exception",
        expected_reason_code="target_authority_validator",
        expected_stage="authority_gate",
        actual_exception_type="RuntimeError",
        actual_reason_code="unrelated setup failure",
        actual_stage="",
        target_validator_reached=False,
        rejected=False,
        counted_as_rejection_evidence=False,
    )


def _attack_expectations() -> tuple[tuple[str, str, str], ...]:
    return (
        (
            "operation_semantic_contract_rehashed",
            "runtime_semantic_contract_mismatch",
            "runtime_contracts",
        ),
        (
            "full_source_tree_binding_rehashed",
            "full_source_snapshot_binding_mismatch",
            "source_snapshot",
        ),
        ("raw_evidence_parent_rehashed", "fixture_evidence_parent_mismatch", "evidence_parents"),
        ("plan_dependency_rehashed", "canonical_plan_dependency_invalid", "canonical_plan"),
        ("task_tools_rehashed", "realized_task_tools_invalid", "realized_task_package"),
        ("surface_validation_rehashed", "surface_validation_not_derived", "surface_realization"),
        ("assessment_decision_rehashed", "assessment_decision_not_derived", "quality_assessment"),
        (
            "sibling_trajectory_rebound_rehashed",
            "trajectory_descriptor_parent_mismatch",
            "execution_binding",
        ),
        (
            "weight_pairing_swapped_rehashed",
            "release_weight_pairing_not_derived",
            "release_selection",
        ),
        ("release_plan_changed_rehashed", "release_plan_not_derived", "release_selection"),
        (
            "quota_policy_changed_hard_gates_true_rehashed",
            "release_quota_not_derived",
            "release_selection",
        ),
        (
            "catalog_replaced_manifest_rehashed",
            "artifact_root_external_anchor_mismatch",
            "artifact_catalog",
        ),
        ("report_only_fields_rehashed", "report_cross_envelope_mismatch", "report"),
        ("report_markdown_mutated", "report_markdown_bytes_mismatch", "report_markdown"),
        (
            "all_catalogs_manifest_report_jointly_rehashed",
            "artifact_manifest_cross_envelope_mismatch",
            "envelope",
        ),
        (
            "one_fixture_removed_bundle_rehashed",
            "external_population_anchor_mismatch",
            "external_anchor",
        ),
        ("one_extra_valid_fixture_added", "external_population_anchor_mismatch", "external_anchor"),
        ("external_audit_omitted_or_replaced", "external_audit_bytes_mismatch", "authorization"),
        (
            "unrelated_archive_paired_with_valid_root",
            "source_archive_projection_invalid",
            "source_projection",
        ),
        (
            "arbitrary_tree_id_paired_with_valid_manifest",
            "source_manifest_tree_mismatch",
            "source_projection",
        ),
        ("registered_attack_silently_omitted", "attack_registry_not_exact", "attack_audit"),
        (
            "wrong_validator_same_exception_phrase",
            "wrong_validator_not_counted",
            "attack_measurement",
        ),
        (
            "pilot_evaluator_profile_substituted",
            "runtime_semantic_contract_mismatch",
            "runtime_contracts",
        ),
    )


def _rewrite_model_identity(payload: dict[str, Any], field: str, prefix: str) -> None:
    payload[field] = canonical_hash(
        {key: value for key, value in payload.items() if key != field},
        prefix=prefix,
    )


def _mutated_report_payloads(payloads: Mapping[str, bytes]) -> dict[str, bytes]:
    attacked = dict(payloads)
    report = _load_json(attacked, "report.json")
    report["authority_bundle_id"] = canonical_hash(
        {"forged": True},
        prefix="qa_release_authority_bundle:",
    )
    _rewrite_model_identity(report, "report_id", "qa_release_authority_report:")
    attacked["report.json"] = _json_bytes(report)
    return attacked


def _jointly_rehashed_catalog_payloads(payloads: Mapping[str, bytes]) -> dict[str, bytes]:
    attacked = dict(payloads)
    for name in CORE_ARTIFACT_NAMES:
        if name != "external_audit.txt":
            attacked[name] = attacked[name] + b" "
    manifest = _artifact_manifest({name: attacked[name] for name in CORE_ARTIFACT_NAMES})
    attacked["artifact_manifest.json"] = _json_bytes(manifest)
    report_payload = _load_json(attacked, "report.json")
    report_payload["artifact_root"] = manifest.artifact_root
    report_payload["artifact_manifest_id"] = manifest.artifact_manifest_id
    _rewrite_model_identity(report_payload, "report_id", "qa_release_authority_report:")
    attacked["report.json"] = _json_bytes(report_payload)
    return attacked


def _altered_population_id(
    *,
    fixture_indexes: tuple[int, ...],
    authorization: QAReleaseAuthorityAuthorization,
    source_projection: QAReleaseSourceProjection,
) -> str:
    bundle = build_qa_release_authority_bundle(
        source_tree_id=source_projection.source_tree_id,
        source_archive_sha256=source_projection.source_archive_sha256,
        source_snapshot_manifest_sha256=source_projection.source_manifest_sha256,
        fixture_indexes=fixture_indexes,
    )
    return build_population_manifest(
        authorization=authorization,
        source_projection=source_projection,
        bundle=bundle,
    ).population_id


def _require_population_anchor(observed: str, expected: str) -> None:
    if observed != expected:
        raise QAReleaseAuthorityError(
            reason_code="external_population_anchor_mismatch",
            stage="external_anchor",
            message="mutated population differs from external expected population",
        )


def _run_attack_controls(
    *,
    bundle: QAReleaseAuthorityBundle,
    authorization: QAReleaseAuthorityAuthorization,
    source_projection: QAReleaseSourceProjection,
    source_manifest: SourceSnapshotManifest,
    population: QAReleasePopulationManifest,
    base_payloads: Mapping[str, bytes],
    envelope: QAReleaseAuthorityEnvelope,
    external_audit_bytes: bytes,
    source_archive_path: Path,
) -> tuple[AuthorityAttackControl, ...]:
    records = bundle.release_selection.release_records
    first, second = records[:2]
    comparison = next(row for row in records if row.realized.task.public.task_type == "comparison")

    def typed(
        action: Callable[[], Any], stage: str, reason: str, message: str
    ) -> Callable[[], None]:
        return lambda: _typed_validator_action(
            action,
            stage=stage,
            reason_code=reason,
            required_message=message,
        )

    def sibling_attack() -> None:
        bind_realization_execution(
            second.realized,
            second.execution_binding.realization_portfolio,
            second.trajectory,
            second.assessment,
            first.execution_binding.execution_descriptor,
        )

    def artifact_root_attack() -> None:
        rows = list(envelope.artifact_manifest.artifacts)
        rows[0] = rows[0].model_copy(update={"sha256": "0" * 64})
        attacked_root = canonical_hash(tuple(rows), prefix="qa_release_authority_artifact_root:")
        if attacked_root != envelope.artifact_manifest.artifact_root:
            raise QAReleaseAuthorityError(
                reason_code="artifact_root_external_anchor_mismatch",
                stage="artifact_catalog",
                message="fully rehashed catalog differs from the envelope anchor",
            )

    def validate_payloads(
        attacked: Mapping[str, bytes], audit: bytes = external_audit_bytes
    ) -> None:
        _validate_artifact_payloads_before_source_replay(
            attacked,
            expected_envelope_id=envelope.envelope_id,
            expected_authorization_id=authorization.authorization_id,
            expected_population_id=population.population_id,
            external_audit_bytes=audit,
        )

    def removed_population_attack() -> None:
        observed = _altered_population_id(
            fixture_indexes=(1,),
            authorization=authorization,
            source_projection=source_projection,
        )
        _require_population_anchor(observed, population.population_id)

    def extra_population_attack() -> None:
        observed = _altered_population_id(
            fixture_indexes=(1, 2, 3),
            authorization=authorization,
            source_projection=source_projection,
        )
        _require_population_anchor(observed, population.population_id)

    def unrelated_archive_attack() -> None:
        with tempfile.TemporaryDirectory(prefix="qa-release-unrelated-archive-") as temporary:
            path = Path(temporary) / "unrelated.tar"
            path.write_bytes(b"unrelated archive\n")
            _authority_call(
                stage="source_projection",
                reason_code="source_archive_projection_invalid",
                action=lambda: verify_source_archive_projection(
                    source_archive_path=path,
                    source_commit_id=source_projection.source_commit_id,
                    source_tree_id=source_projection.source_tree_id,
                ),
            )

    def arbitrary_tree_attack() -> None:
        payload = source_projection.model_dump(mode="json")
        payload["source_tree_id"] = "0" * 40
        _rewrite_model_identity(payload, "source_projection_id", "qa_release_source_projection:")
        attacked = QAReleaseSourceProjection.model_validate(payload)
        if attacked.source_tree_id != source_manifest.source_tree_id:
            raise QAReleaseAuthorityError(
                reason_code="source_manifest_tree_mismatch",
                stage="source_projection",
                message="arbitrary source tree differs from archive-derived manifest",
            )

    def omitted_attack() -> None:
        _authority_call(
            stage="attack_audit",
            reason_code="attack_registry_not_exact",
            action=lambda: _require_exact_attack_ids(FROZEN_ATTACK_IDS[:-1]),
        )

    def wrong_validator_attack() -> None:
        observed = _capture_attack(
            "wrong_validator_probe",
            "runtime_semantic_contract_mismatch",
            "runtime_contracts",
            lambda: (_ for _ in ()).throw(ValueError("runtime_semantic_contract_mismatch")),
        )
        if not observed.counted_as_rejection_evidence:
            raise QAReleaseAuthorityError(
                reason_code="wrong_validator_not_counted",
                stage="attack_measurement",
                message="matching exception text without typed stage was not counted",
            )

    def evaluator_substitution_attack() -> None:
        payload = bundle.model_dump(mode="json")
        payload["evaluator_contract_id"] = canonical_hash(
            {"profile": "archive_backed_pilot"},
            prefix="qa_release_evaluator_contract:",
        )
        _rewrite_model_identity(payload, "authority_bundle_id", "qa_release_authority_bundle:")
        load_and_reconstruct_qa_release_authority_bundle(
            payload,
            expected_source_tree_id=source_projection.source_tree_id,
            expected_source_archive_sha256=source_projection.source_archive_sha256,
            expected_source_snapshot_manifest_sha256=source_projection.source_manifest_sha256,
        )

    actions: dict[str, Callable[[], Any]] = {
        "operation_semantic_contract_rehashed": lambda: _operation_contract_attack(bundle),
        "full_source_tree_binding_rehashed": lambda: _source_tree_attack(bundle),
        "raw_evidence_parent_rehashed": lambda: _raw_evidence_attack(bundle),
        "plan_dependency_rehashed": typed(
            lambda: _plan_dependency_attack(comparison.realized.semantic_plan),
            "canonical_plan",
            "canonical_plan_dependency_invalid",
            "unknown operation node",
        ),
        "task_tools_rehashed": typed(
            lambda: _task_tools_attack(first.realized),
            "realized_task_package",
            "realized_task_tools_invalid",
            "tools cross the CanonicalSemanticPlan",
        ),
        "surface_validation_rehashed": typed(
            lambda: _surface_validation_attack(first.realized.realization),
            "surface_realization",
            "surface_validation_not_derived",
            "persisted validation is not derived",
        ),
        "assessment_decision_rehashed": typed(
            lambda: _assessment_decision_attack(first.assessment),
            "quality_assessment",
            "assessment_decision_not_derived",
            "decision is not derived",
        ),
        "sibling_trajectory_rebound_rehashed": typed(
            sibling_attack,
            "execution_binding",
            "trajectory_descriptor_parent_mismatch",
            "execution descriptor crosses its public task",
        ),
        "weight_pairing_swapped_rehashed": typed(
            lambda: _weight_pairing_attack(bundle.release_selection),
            "release_selection",
            "release_weight_pairing_not_derived",
            "not source-derived",
        ),
        "release_plan_changed_rehashed": typed(
            lambda: _release_plan_attack(bundle.release_selection),
            "release_selection",
            "release_plan_not_derived",
            "not source-derived",
        ),
        "quota_policy_changed_hard_gates_true_rehashed": typed(
            lambda: _quota_attack(bundle.release_selection),
            "release_selection",
            "release_quota_not_derived",
            "not source-derived",
        ),
        "catalog_replaced_manifest_rehashed": artifact_root_attack,
        "report_only_fields_rehashed": lambda: validate_payloads(
            _mutated_report_payloads(base_payloads)
        ),
        "report_markdown_mutated": lambda: validate_payloads(
            {**base_payloads, "report.md": base_payloads["report.md"] + b"mutated\n"}
        ),
        "all_catalogs_manifest_report_jointly_rehashed": lambda: validate_payloads(
            _jointly_rehashed_catalog_payloads(base_payloads)
        ),
        "one_fixture_removed_bundle_rehashed": removed_population_attack,
        "one_extra_valid_fixture_added": extra_population_attack,
        "external_audit_omitted_or_replaced": lambda: _authority_call(
            stage="authorization",
            reason_code="external_audit_bytes_mismatch",
            action=lambda: _validate_external_audit(authorization, b"replaced audit\n"),
        ),
        "unrelated_archive_paired_with_valid_root": unrelated_archive_attack,
        "arbitrary_tree_id_paired_with_valid_manifest": arbitrary_tree_attack,
        "registered_attack_silently_omitted": omitted_attack,
        "wrong_validator_same_exception_phrase": wrong_validator_attack,
        "pilot_evaluator_profile_substituted": evaluator_substitution_attack,
    }
    controls = tuple(
        _capture_attack(attack_id, reason, stage, actions[attack_id])
        for attack_id, reason, stage in _attack_expectations()
    )
    _require_exact_attack_ids(tuple(row.attack_id for row in controls))
    return controls


def run_release_authority_envelope_preflight(
    *,
    source_commit_id: str,
    source_tree_id: str,
    source_archive_path: Path,
    external_audit_path: Path,
    observed_change_surface: tuple[str, ...],
    output_dir: Path,
) -> dict[str, Any]:
    if output_dir.exists():
        raise FileExistsError(f"immutable authority envelope output already exists: {output_dir}")
    source_root = Path(__file__).resolve().parents[5]
    expected_module = (source_root / EXECUTED_MODULE_PATH).resolve()
    if expected_module != Path(__file__).resolve():
        raise ValueError("authority preflight is not executing from its projected source root")
    source_projection, source_manifest = verify_source_archive_projection(
        source_archive_path=source_archive_path,
        source_commit_id=source_commit_id,
        source_tree_id=source_tree_id,
        executed_source_root=source_root,
    )
    external_audit_bytes = external_audit_path.read_bytes()
    authorization = build_authorization(
        external_audit_bytes=external_audit_bytes,
        source_commit_id=source_commit_id,
        observed_change_surface=observed_change_surface,
    )
    bundle = build_qa_release_authority_bundle(
        source_tree_id=source_projection.source_tree_id,
        source_archive_sha256=source_projection.source_archive_sha256,
        source_snapshot_manifest_sha256=source_projection.source_manifest_sha256,
    )
    load_and_reconstruct_qa_release_authority_bundle(
        bundle,
        expected_source_tree_id=source_projection.source_tree_id,
        expected_source_archive_sha256=source_projection.source_archive_sha256,
        expected_source_snapshot_manifest_sha256=source_projection.source_manifest_sha256,
    )
    population = build_population_manifest(
        authorization=authorization,
        source_projection=source_projection,
        bundle=bundle,
    )
    runtime = capture_runtime_environment(source_root)
    placeholders = _placeholder_controls()
    unrelated = _unrelated_exception_control()
    placeholder_audit = _build_attack_audit(placeholders, unrelated)
    base_payloads, base_envelope = _build_payloads(
        external_audit_bytes=external_audit_bytes,
        authorization=authorization,
        source_projection=source_projection,
        source_manifest=source_manifest,
        population=population,
        runtime=runtime,
        bundle=bundle,
        attack_audit=placeholder_audit,
    )
    controls = _run_attack_controls(
        bundle=bundle,
        authorization=authorization,
        source_projection=source_projection,
        source_manifest=source_manifest,
        population=population,
        base_payloads=base_payloads,
        envelope=base_envelope,
        external_audit_bytes=external_audit_bytes,
        source_archive_path=source_archive_path,
    )
    if controls != placeholders:
        raise ValueError("measured attack controls differ from the frozen typed expectations")
    attack_audit = _build_attack_audit(controls, unrelated)
    payloads, envelope = _build_payloads(
        external_audit_bytes=external_audit_bytes,
        authorization=authorization,
        source_projection=source_projection,
        source_manifest=source_manifest,
        population=population,
        runtime=runtime,
        bundle=bundle,
        attack_audit=attack_audit,
    )
    if envelope != base_envelope or payloads != base_payloads:
        raise ValueError("measured attack evidence changed the deterministic authority envelope")
    write_immutable_artifact_directory(output_dir, payloads)
    loaded = load_qa_release_authority_envelope_directory(
        output_dir,
        expected_envelope_id=envelope.envelope_id,
        expected_authorization_id=authorization.authorization_id,
        expected_population_id=population.population_id,
        external_audit_path=external_audit_path,
        source_archive_path=source_archive_path,
    )
    if loaded != envelope.report.model_dump(mode="json"):
        raise ValueError("published envelope report differs after exact external-anchor reload")
    return {
        **loaded,
        "envelope_id": envelope.envelope_id,
        "source_commit_id": source_commit_id,
        "source_tree_id": source_tree_id,
        "source_archive_sha256": source_projection.source_archive_sha256,
        "source_archive_byte_count": source_projection.source_archive_byte_count,
        "source_manifest_sha256": source_projection.source_manifest_sha256,
        "source_manifest_byte_count": source_projection.source_manifest_byte_count,
        "source_manifest_file_count": source_projection.source_manifest_file_count,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-commit-id", required=True)
    parser.add_argument("--source-tree-id", required=True)
    parser.add_argument("--source-archive", type=Path, required=True)
    parser.add_argument("--external-audit", type=Path, required=True)
    parser.add_argument("--observed-change-surface", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    observed_change_surface = tuple(json.loads(args.observed_change_surface.read_bytes()))
    report = run_release_authority_envelope_preflight(
        source_commit_id=args.source_commit_id,
        source_tree_id=args.source_tree_id,
        source_archive_path=args.source_archive,
        external_audit_path=args.external_audit,
        observed_change_surface=observed_change_surface,
        output_dir=args.output_dir,
    )
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
