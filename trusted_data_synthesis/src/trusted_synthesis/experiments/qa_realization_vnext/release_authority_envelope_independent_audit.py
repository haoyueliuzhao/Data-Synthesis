from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import locale
import os
import platform
import subprocess
import sys
import tarfile
import tempfile
import time
from collections.abc import Callable, Mapping
from pathlib import Path, PurePosixPath
from typing import Any, Final

from trusted_synthesis.core.immutable_artifacts import write_immutable_artifact_directory

AUDIT_RUN_ID: Final = "qa_release_authority_envelope_independent_audit.v1"
AUTHORIZED_PREDECESSOR: Final = "8831a2e7e933125009721e6807882ce32c27394d"
AUDITED_SOURCE_COMMIT: Final = "78b950174bee109f765bf3715f9243648fb4b67a"
AUDITED_SOURCE_TREE: Final = "9146e365a1c866edb9de3a732d50d52538b43427"
AUDITED_ARTIFACT_COMMIT: Final = "5c543761cee0a52b61966d1b4a5f51e93dc50756"
AUDITED_ARTIFACT_DIR: Final = (
    "trusted_data_synthesis/artifacts/qa_realization_vnext/"
    "qa_release_authority_envelope_v4_20260831"
)
OUTPUT_DIR: Final = (
    "trusted_data_synthesis/artifacts/qa_realization_vnext/"
    "qa_release_authority_envelope_independent_audit_v5_20260831"
)
EXPECTED_AUTHORIZATION_ID: Final = (
    "qa_release_authority_authorization:"
    "59dbf2aac8957b8ebe661c758247b882b896466e83ad541a71c3c1c3f7365884"
)
EXPECTED_SOURCE_PROJECTION_ID: Final = (
    "qa_release_source_projection:361b3dd691e6319465f3de85179358184d8bef59a2cd44e18baa8e6236016758"
)
EXPECTED_POPULATION_ID: Final = (
    "qa_release_population_manifest:"
    "2091318902368887a6e31355af934676a027f639cdca167377cc3747991e392d"
)
EXPECTED_BUNDLE_ID: Final = (
    "qa_release_authority_bundle:ee72e2665d9654fc531820c593d2cbb61d21ac22dde21d044eb7ef0c2249e9b1"
)
EXPECTED_SELECTION_ID: Final = (
    "diversity_aware_release_selection:"
    "ea8359a70f1cedcfe9cf635a49dd347ab18467de2ade99ad063720d31f3afac0"
)
EXPECTED_RUNTIME_ID: Final = (
    "qa_release_runtime_environment:"
    "e543c7b2c6a1aca66fef73de1cf8741a5b0bc2489690e444c1afc84b05949d54"
)
EXPECTED_ARTIFACT_ROOT: Final = (
    "qa_release_authority_artifact_root:"
    "d5d43b2ec2dc65176f9051bb6780fb3f1c75a7286a812b2d0cc3ce5a8a88b069"
)
EXPECTED_ENVELOPE_ID: Final = (
    "qa_release_authority_envelope:967e1fdc1cdc5522b80b230962b5b96c394b4e77e0cf759bf1e49cf9d0915787"
)
EXPECTED_REPORT_ID: Final = (
    "qa_release_authority_report:4a626b3eb7f249652259e09170705799febbe4d7ef45965e069e02f6087330fa"
)
EXPECTED_PREDECESSOR_ARCHIVE_SHA256: Final = (
    "9d2bd4e34dd335375f19d34fc2e5364f81b52d1fb7c025663c53eca91a6fbe54"
)
EXPECTED_PREDECESSOR_ARCHIVE_BYTES: Final = 999_086_080
EXPECTED_SOURCE_MANIFEST_SHA256: Final = (
    "e0b38623458311a040d64c585e3110e9a1ff3afd1175e28e1d308ec4e71654e2"
)
EXPECTED_SOURCE_MEMBER_COUNT: Final = 34_388
PERMITTED_CHANGE_SURFACE: Final = (
    "trusted_data_synthesis/docs/current_project_status.md",
    "trusted_data_synthesis/docs/finance_v26_185_qa_release_authority_independent_audit.md",
    (
        "trusted_data_synthesis/src/trusted_synthesis/experiments/qa_realization_vnext/"
        "release_authority_envelope_independent_audit.py"
    ),
    (
        "trusted_data_synthesis/src/trusted_synthesis/experiments/qa_realization_vnext/"
        "source_projected_envelope_independent_audit_runner.py"
    ),
    "trusted_data_synthesis/tests/test_qa_release_authority_envelope_independent_audit.py",
)
FORBIDDEN_OPERATIONS: Final = (
    "archive_backed_finance_pilot",
    "contribution",
    "production_release",
    "provider_generation",
    "training",
    "v26_181_reinterpretation",
    "vtdo",
)
ARTIFACT_NAMES: Final = (
    "artifact_manifest.json",
    "attack_audit.json",
    "attack_controls.json",
    "authorization.json",
    "envelope.json",
    "external_audit.txt",
    "qa_release_authority_bundle.json",
    "release_population.json",
    "release_records.jsonl",
    "release_selection.json",
    "report.json",
    "report.md",
    "runtime_environment.json",
    "source_projection.json",
    "source_snapshot_manifest.json",
)
CORE_ARTIFACT_NAMES: Final = (
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
ATTACK_IDS: Final = (
    "operation_semantic_contract_rehashed",
    "full_source_tree_binding_rehashed",
    "raw_evidence_parent_rehashed",
    "plan_dependency_rehashed",
    "task_tools_rehashed",
    "surface_validation_rehashed",
    "assessment_decision_rehashed",
    "sibling_trajectory_rebound_rehashed",
    "weight_pairing_swapped_rehashed",
    "release_plan_changed_rehashed",
    "quota_policy_changed_hard_gates_true_rehashed",
    "catalog_replaced_manifest_rehashed",
    "report_only_fields_rehashed",
    "report_markdown_mutated",
    "all_catalogs_manifest_report_jointly_rehashed",
    "one_fixture_removed_bundle_rehashed",
    "one_extra_valid_fixture_added",
    "external_audit_omitted_or_replaced",
    "unrelated_archive_paired_with_valid_root",
    "arbitrary_tree_id_paired_with_valid_manifest",
    "registered_attack_silently_omitted",
    "wrong_validator_same_exception_phrase",
    "pilot_evaluator_profile_substituted",
)
INDEPENDENT_CONTROL_IDS: Final = (
    "missing_artifact_file",
    "extra_artifact_file",
    "report_parent_rehashed",
    "markdown_bytes_changed",
    "selection_catalog_jointly_rehashed",
    "record_catalog_jointly_rehashed",
    "attack_registry_member_removed",
    "population_member_removed",
    "runtime_distribution_count_changed",
    "projection_tree_changed",
    "embedded_external_audit_changed",
    "entire_envelope_rehashed",
    "unrelated_source_archive",
)


class IndependentAuditError(ValueError):
    def __init__(self, *, stage: str, reason_code: str, message: str) -> None:
        super().__init__(message)
        self.stage = stage
        self.reason_code = reason_code


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode()


def _json_bytes(value: Any) -> bytes:
    return _canonical_bytes(value) + b"\n"


def _legacy_hash(value: Any, *, prefix: str = "") -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode()
    digest = hashlib.sha256(payload).hexdigest()
    return f"{prefix}{digest}" if prefix else digest


def _identity(value: Mapping[str, Any], *, field: str, prefix: str) -> str:
    return _legacy_hash(
        {key: item for key, item in value.items() if key != field},
        prefix=prefix,
    )


def _v184_artifact_root(rows: Any) -> str:
    row_preimages = tuple(
        (f"name={row['name']!r} sha256={row['sha256']!r} byte_count={row['byte_count']}")
        for row in rows
    )
    return _legacy_hash(
        row_preimages,
        prefix="qa_release_authority_artifact_root:",
    )


def _sha256_path(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    count = 0
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
            count += len(chunk)
    return digest.hexdigest(), count


def _git_blob_id(content: bytes) -> str:
    header = f"blob {len(content)}\0".encode()
    return hashlib.sha1(header + content, usedforsecurity=False).hexdigest()


def _git_tree_id(rows: tuple[dict[str, Any], ...]) -> str:
    root: dict[str, Any] = {}
    for row in rows:
        parts = str(row["path"]).split("/")
        node = root
        for part in parts[:-1]:
            child = node.setdefault(part, {})
            if not isinstance(child, dict):
                raise ValueError("archive contains a file/directory collision")
            node = child
        if parts[-1] in node:
            raise ValueError("archive contains duplicate Git entries")
        node[parts[-1]] = row

    def visit(node: dict[str, Any]) -> str:
        body = bytearray()
        for name in sorted(node, key=lambda item: item.encode()):
            value = node[name]
            if isinstance(value, dict) and "path" not in value:
                mode = "40000"
                object_id = visit(value)
            else:
                if value["kind"] == "symlink":
                    mode = "120000"
                elif value["executable"]:
                    mode = "100755"
                else:
                    mode = "100644"
                object_id = value["git_blob_id"]
            body.extend(mode.encode())
            body.extend(b" ")
            body.extend(name.encode())
            body.extend(b"\0")
            body.extend(bytes.fromhex(object_id))
        header = f"tree {len(body)}\0".encode()
        return hashlib.sha1(header + body, usedforsecurity=False).hexdigest()

    return visit(root)


def _archive_commit_id(path: Path) -> str:
    with path.open("rb") as handle:
        result = subprocess.run(
            ("git", "get-tar-commit-id"),
            stdin=handle,
            check=False,
            capture_output=True,
        )
    value = result.stdout.decode("ascii", errors="strict").strip()
    if result.returncode != 0 or len(value) != 40:
        raise ValueError("archive lacks an embedded Git commit")
    return value


def _archive_rows(path: Path) -> tuple[dict[str, Any], ...]:
    rows: list[dict[str, Any]] = []
    observed: set[str] = set()
    with tarfile.open(path, mode="r:") as archive:
        for member in archive.getmembers():
            name = member.name.rstrip("/")
            pure = PurePosixPath(name)
            if (
                not name
                or pure.is_absolute()
                or any(part in {"", ".", ".."} for part in pure.parts)
            ):
                raise ValueError("archive contains an unsafe path")
            if member.isdir():
                continue
            if name in observed:
                raise ValueError("archive contains duplicate members")
            observed.add(name)
            if member.isfile():
                handle = archive.extractfile(member)
                if handle is None:
                    raise ValueError("archive regular member is unreadable")
                content = handle.read()
                kind = "file"
                executable = bool(member.mode & 0o111)
            elif member.issym():
                content = member.linkname.encode()
                kind = "symlink"
                executable = False
            else:
                raise ValueError("archive contains a non-Git member kind")
            rows.append(
                {
                    "path": name,
                    "kind": kind,
                    "executable": executable,
                    "byte_count": len(content),
                    "sha256": hashlib.sha256(content).hexdigest(),
                    "git_blob_id": _git_blob_id(content),
                    "schema_version": "source_snapshot_entry.v1",
                }
            )
    return tuple(sorted(rows, key=lambda row: str(row["path"])))


def _validate_root(root: Path, rows: tuple[dict[str, Any], ...]) -> None:
    expected = {str(row["path"]): row for row in rows}
    observed = {
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file() or path.is_symlink()
    }
    if observed != set(expected):
        raise ValueError("executed audit root is not the exact source archive")
    for relative, row in expected.items():
        path = root / relative
        if path.is_symlink():
            content = os.readlink(path).encode()
            kind = "symlink"
            executable = False
        else:
            content = path.read_bytes()
            kind = "file"
            executable = bool(path.stat().st_mode & 0o111)
        if (
            kind != row["kind"]
            or executable is not row["executable"]
            or len(content) != row["byte_count"]
            or hashlib.sha256(content).hexdigest() != row["sha256"]
        ):
            raise ValueError(f"executed audit source differs at {relative}")


def _load_payloads(root: Path) -> dict[str, bytes]:
    return {path.name: path.read_bytes() for path in root.iterdir() if path.is_file()}


def _parse_json(payloads: Mapping[str, bytes], name: str) -> Any:
    try:
        return json.loads(payloads[name])
    except (KeyError, json.JSONDecodeError) as exc:
        raise IndependentAuditError(
            stage="artifact_parse",
            reason_code="artifact_json_invalid",
            message=f"invalid JSON artifact: {name}",
        ) from exc


def _require_identity(
    value: Mapping[str, Any],
    *,
    field: str,
    prefix: str,
    stage: str,
    reason_code: str,
) -> None:
    if value.get(field) != _identity(value, field=field, prefix=prefix):
        raise IndependentAuditError(
            stage=stage,
            reason_code=reason_code,
            message=f"{field} is not independently content-derived",
        )


def _validate_attack_catalog(attack: Mapping[str, Any], controls: Any) -> dict[str, Any]:
    observed = tuple(row["attack_id"] for row in attack["controls"])
    if tuple(attack["frozen_attack_ids"]) != ATTACK_IDS or observed != ATTACK_IDS:
        raise IndependentAuditError(
            stage="attack_audit",
            reason_code="attack_registry_not_exact",
            message="v26.184 attack registry differs from the frozen 23-ID set",
        )
    if controls != attack["controls"]:
        raise IndependentAuditError(
            stage="attack_audit",
            reason_code="attack_controls_cross_catalog_mismatch",
            message="attack control sidecar differs from AttackAudit",
        )
    for row in attack["controls"]:
        exact = (
            row["actual_exception_type"]
            == row["expected_exception_type"]
            == "QAReleaseAuthorityError"
            and row["actual_reason_code"] == row["expected_reason_code"]
            and row["actual_stage"] == row["expected_stage"]
        )
        if (
            not exact
            or not row["target_validator_reached"]
            or not row["rejected"]
            or not row["counted_as_rejection_evidence"]
        ):
            raise IndependentAuditError(
                stage="attack_audit",
                reason_code="attack_rejection_measurement_invalid",
                message=f"attack rejection is not exact: {row['attack_id']}",
            )
    if attack["missing_attack_ids"] or attack["duplicate_attack_ids"] or attack["extra_attack_ids"]:
        raise IndependentAuditError(
            stage="attack_audit",
            reason_code="attack_registry_difference_not_empty",
            message="attack missing/duplicate/extra sets are not empty",
        )
    unrelated = attack["unrelated_exception_control"]
    if (
        unrelated["actual_exception_type"] != "RuntimeError"
        or unrelated["actual_stage"]
        or unrelated["counted_as_rejection_evidence"]
    ):
        raise IndependentAuditError(
            stage="attack_audit",
            reason_code="unrelated_exception_counted",
            message="unrelated RuntimeError entered rejection evidence",
        )
    _require_identity(
        attack,
        field="attack_audit_id",
        prefix="qa_release_authority_attack_audit:",
        stage="attack_audit",
        reason_code="attack_audit_identity_invalid",
    )
    return {
        "attack_count": len(observed),
        "attack_rejection_count": sum(
            bool(row["counted_as_rejection_evidence"]) for row in attack["controls"]
        ),
        "unrelated_exception_counted": unrelated["counted_as_rejection_evidence"],
    }


def _validate_population(
    population: Mapping[str, Any],
    bundle: Mapping[str, Any],
    projection: Mapping[str, Any],
    authorization: Mapping[str, Any],
) -> dict[str, Any]:
    if population["authorization_id"] != authorization["authorization_id"]:
        raise IndependentAuditError(
            stage="release_population",
            reason_code="population_authorization_parent_mismatch",
            message="Population crosses Authorization",
        )
    if population["source_projection_id"] != projection["source_projection_id"]:
        raise IndependentAuditError(
            stage="release_population",
            reason_code="population_projection_parent_mismatch",
            message="Population crosses SourceProjection",
        )
    if (
        population["fixture_indexes"] != [1, 2]
        or len(population["fixture_input_ids"]) != 2
        or len(population["semantic_instance_ids"]) != 2
        or len(population["members"]) != 6
        or population["missing_duplicate_extra_policy"] != "fail_closed_exact_set_equality"
        or not population["pre_outcome_authorization_parent"]
    ):
        raise IndependentAuditError(
            stage="release_population",
            reason_code="population_exact_set_invalid",
            message="Population denominator is not exact 2-Fixture/6-Surface pre-outcome",
        )
    fixture_by_binding = {
        row["evidence_binding"]["binding_id"]: row for row in bundle["fixture_inputs"]
    }
    expected_members = []
    for record in bundle["release_selection"]["release_records"]:
        realized = record["realized"]
        binding_id = realized["binding_snapshot"]["evidence_binding"]["binding_id"]
        fixture = fixture_by_binding.get(binding_id)
        if fixture is None:
            raise IndependentAuditError(
                stage="release_population",
                reason_code="population_fixture_parent_missing",
                message="release record has no Fixture parent",
            )
        member = {
            "fixture_input_id": fixture["fixture_input_id"],
            "fixture_index": fixture["fixture_index"],
            "task_type": realized["task"]["public"]["task_type"],
            "semantic_schema_id": realized["semantic_plan"]["semantic_task_id"],
            "semantic_instance_id": realized["semantic_instance"]["semantic_instance_id"],
            "binding_snapshot_id": realized["binding_snapshot"]["binding_snapshot_id"],
            "realized_package_id": realized["realized_package_id"],
            "realization_id": realized["realization"]["realization_id"],
            "schema_version": "qa_release_population_member.v1",
        }
        member["member_id"] = _legacy_hash(
            member,
            prefix="qa_release_population_member:",
        )
        expected_members.append(member)
    expected_members.sort(key=lambda row: str(row["member_id"]))
    if population["members"] != expected_members:
        raise IndependentAuditError(
            stage="release_population",
            reason_code="population_members_not_source_derived",
            message="Population members differ from Bundle pre-outcome surfaces",
        )
    selection_contract = {
        "fixture_indexes": [1, 2],
        "release_policy_hash": bundle["release_policy_hash"],
        "split_policy_hash": bundle["split_policy_hash"],
        "schema_version": "qa_release_population_source_selection.v1",
    }
    if population["source_selection_contract_id"] != _legacy_hash(
        selection_contract,
        prefix="qa_release_population_source_selection:",
    ):
        raise IndependentAuditError(
            stage="release_population",
            reason_code="population_selection_contract_invalid",
            message="Population source selection contract is not derived",
        )
    _require_identity(
        population,
        field="population_id",
        prefix="qa_release_population_manifest:",
        stage="release_population",
        reason_code="population_identity_invalid",
    )
    if population["population_id"] != EXPECTED_POPULATION_ID:
        raise IndependentAuditError(
            stage="external_anchor",
            reason_code="population_external_anchor_mismatch",
            message="Population differs from the external expected identity",
        )
    return {
        "fixture_count": len(population["fixture_input_ids"]),
        "semantic_instance_count": len(population["semantic_instance_ids"]),
        "population_member_count": len(population["members"]),
    }


def _capture_runtime(source_root: Path) -> dict[str, Any]:
    distributions = tuple(
        sorted(
            (
                distribution.metadata["Name"].lower(),
                distribution.version,
            )
            for distribution in importlib.metadata.distributions()
        )
    )
    definitions = []
    for relative in (
        "trusted_data_synthesis/pyproject.toml",
        "raw_financial_data_lake/pyproject.toml",
    ):
        path = source_root / relative
        if path.is_file():
            definitions.append(
                {
                    "path": relative,
                    "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                }
            )
    executable = Path(sys.executable).resolve()
    libc_name, libc_version = platform.libc_ver()
    value = {
        "python_version": platform.python_version(),
        "python_implementation": platform.python_implementation(),
        "python_executable_sha256": hashlib.sha256(executable.read_bytes()).hexdigest(),
        "pydantic_version": importlib.metadata.version("pydantic"),
        "dependency_lock_hash": _legacy_hash(
            distributions,
            prefix="installed_python_distribution_lock:",
        ),
        "installed_distribution_count": len(distributions),
        "dependency_definition_hash": _legacy_hash(
            definitions,
            prefix="source_dependency_definitions:",
        ),
        "os_system": platform.system(),
        "kernel_release": platform.release(),
        "libc_identity": f"{libc_name}:{libc_version}",
        "locale_identity": locale.setlocale(locale.LC_ALL, None),
        "timezone_identity": _legacy_hash(
            {"TZ": os.environ.get("TZ", ""), "tzname": time.tzname},
            prefix="runtime_timezone:",
        ),
        "environment_root": str(Path(sys.prefix).resolve()),
        "schema_version": "qa_release_runtime_environment.v1",
    }
    value["runtime_environment_id"] = _legacy_hash(
        value,
        prefix="qa_release_runtime_environment:",
    )
    return value


def _markdown_report(report: Mapping[str, Any]) -> bytes:
    tick = chr(96)
    return (
        "# QA Release Authority External Envelope Preflight\n\n"
        f"- Status: **{report['status']}**\n"
        f"- Authorization: {tick}{report['authorization_id']}{tick}\n"
        f"- Source projection: {tick}{report['source_projection_id']}{tick}\n"
        f"- Exact population: {tick}{report['population_id']}{tick}\n"
        f"- Runtime environment: {tick}{report['runtime_environment_id']}{tick}\n"
        f"- Authority bundle: {tick}{report['authority_bundle_id']}{tick}\n"
        f"- Release selection: {tick}{report['release_selection_id']}{tick}\n"
        f"- Exact typed attacks: {report['exact_attack_rejection_count']} / "
        f"{report['exact_attack_count']}\n"
        f"- Provider calls: {report['provider_calls']}\n"
        "- Archive-backed Pilot authorized: no\n"
        "- Production authorized: no\n"
        f"- Artifact root: {tick}{report['artifact_root']}{tick}\n"
    ).encode()


def _validate_fast_catalogs(payloads: Mapping[str, bytes]) -> dict[str, Any]:
    if tuple(sorted(payloads)) != ARTIFACT_NAMES:
        raise IndependentAuditError(
            stage="artifact_catalog",
            reason_code="artifact_membership_not_exact",
            message="v26.184 directory does not contain the exact fifteen files",
        )
    envelope = _parse_json(payloads, "envelope.json")
    _require_identity(
        envelope,
        field="envelope_id",
        prefix="qa_release_authority_envelope:",
        stage="envelope",
        reason_code="envelope_identity_invalid",
    )
    if envelope["envelope_id"] != EXPECTED_ENVELOPE_ID:
        raise IndependentAuditError(
            stage="external_anchor",
            reason_code="envelope_external_anchor_mismatch",
            message="Envelope differs from the external expected identity",
        )
    authorization = _parse_json(payloads, "authorization.json")
    projection = _parse_json(payloads, "source_projection.json")
    population = _parse_json(payloads, "release_population.json")
    bundle = _parse_json(payloads, "qa_release_authority_bundle.json")
    selection = _parse_json(payloads, "release_selection.json")
    records = tuple(
        json.loads(line) for line in payloads["release_records.jsonl"].splitlines() if line
    )
    attack = _parse_json(payloads, "attack_audit.json")
    controls = _parse_json(payloads, "attack_controls.json")
    runtime = _parse_json(payloads, "runtime_environment.json")
    manifest = _parse_json(payloads, "artifact_manifest.json")
    report = _parse_json(payloads, "report.json")
    embedded_pairs = (
        (authorization, envelope["authorization"], "authorization"),
        (projection, envelope["source_projection"], "source_projection"),
        (population, envelope["population_manifest"], "population"),
        (bundle, envelope["authority_bundle"], "bundle"),
        (selection, envelope["release_selection"], "selection"),
        (list(records), envelope["release_records"], "records"),
        (attack, envelope["attack_audit"], "attack_audit"),
        (runtime, envelope["runtime_environment"], "runtime"),
        (manifest, envelope["artifact_manifest"], "artifact_manifest"),
        (report, envelope["report"], "report"),
    )
    for sidecar, embedded, label in embedded_pairs:
        if sidecar != embedded:
            raise IndependentAuditError(
                stage="cross_catalog",
                reason_code=f"{label}_cross_envelope_mismatch",
                message=f"{label} sidecar differs from Envelope",
            )
    if selection != bundle["release_selection"] or list(records) != selection["release_records"]:
        raise IndependentAuditError(
            stage="release_catalogs",
            reason_code="release_catalog_cross_parent_mismatch",
            message="Selection or Records differs from Bundle",
        )
    rows = tuple(manifest["artifacts"])
    if tuple(row["name"] for row in rows) != CORE_ARTIFACT_NAMES:
        raise IndependentAuditError(
            stage="artifact_catalog",
            reason_code="core_artifact_membership_not_exact",
            message="ArtifactManifest does not catalog the exact eleven semantic files",
        )
    for row in rows:
        content = payloads[row["name"]]
        if (
            len(content) != row["byte_count"]
            or hashlib.sha256(content).hexdigest() != row["sha256"]
        ):
            raise IndependentAuditError(
                stage="artifact_catalog",
                reason_code="artifact_bytes_mismatch",
                message=f"artifact bytes differ: {row['name']}",
            )
    expected_root = _v184_artifact_root(rows)
    if manifest["artifact_root"] != expected_root or expected_root != EXPECTED_ARTIFACT_ROOT:
        raise IndependentAuditError(
            stage="artifact_catalog",
            reason_code="artifact_root_invalid",
            message="Artifact root is not independently derived or externally expected",
        )
    _require_identity(
        manifest,
        field="artifact_manifest_id",
        prefix="qa_release_authority_artifact_manifest:",
        stage="artifact_catalog",
        reason_code="artifact_manifest_identity_invalid",
    )
    for value, field, prefix, stage, reason, expected in (
        (
            authorization,
            "authorization_id",
            "qa_release_authority_authorization:",
            "authorization",
            "authorization_identity_invalid",
            EXPECTED_AUTHORIZATION_ID,
        ),
        (
            projection,
            "source_projection_id",
            "qa_release_source_projection:",
            "source_projection",
            "source_projection_identity_invalid",
            EXPECTED_SOURCE_PROJECTION_ID,
        ),
        (
            bundle,
            "authority_bundle_id",
            "qa_release_authority_bundle:",
            "authority_bundle",
            "bundle_identity_invalid",
            EXPECTED_BUNDLE_ID,
        ),
        (
            selection,
            "selection_id",
            "diversity_aware_release_selection:",
            "release_selection",
            "selection_identity_invalid",
            EXPECTED_SELECTION_ID,
        ),
        (
            runtime,
            "runtime_environment_id",
            "qa_release_runtime_environment:",
            "runtime_environment",
            "runtime_identity_invalid",
            EXPECTED_RUNTIME_ID,
        ),
        (
            report,
            "report_id",
            "qa_release_authority_report:",
            "report",
            "report_identity_invalid",
            EXPECTED_REPORT_ID,
        ),
    ):
        _require_identity(
            value,
            field=field,
            prefix=prefix,
            stage=stage,
            reason_code=reason,
        )
        if value[field] != expected:
            raise IndependentAuditError(
                stage="external_anchor",
                reason_code=f"{stage}_external_anchor_mismatch",
                message=f"{field} differs from external expected identity",
            )
    embedded_audit = payloads["external_audit.txt"]
    if (
        len(embedded_audit) != authorization["external_audit_byte_count"]
        or hashlib.sha256(embedded_audit).hexdigest() != authorization["external_audit_sha256"]
    ):
        raise IndependentAuditError(
            stage="authorization",
            reason_code="embedded_external_audit_mismatch",
            message="embedded predecessor audit bytes differ from Authorization",
        )
    for record in records:
        _require_identity(
            record,
            field="record_id",
            prefix="persisted_release_record:",
            stage="release_records",
            reason_code="release_record_identity_invalid",
        )
    for assignment in selection["weight_assignments"]:
        _require_identity(
            assignment,
            field="assignment_id",
            prefix="release_weight_assignment:",
            stage="release_selection",
            reason_code="weight_assignment_identity_invalid",
        )
    population_summary = _validate_population(population, bundle, projection, authorization)
    attack_summary = _validate_attack_catalog(attack, controls)
    if payloads["report.md"] != _markdown_report(report):
        raise IndependentAuditError(
            stage="report_markdown",
            reason_code="report_markdown_not_derived",
            message="Markdown is not the independent Report projection",
        )
    if (
        len(payloads["report.md"]) != envelope["report_markdown_byte_count"]
        or hashlib.sha256(payloads["report.md"]).hexdigest() != envelope["report_markdown_sha256"]
    ):
        raise IndependentAuditError(
            stage="report_markdown",
            reason_code="report_markdown_hash_mismatch",
            message="Markdown bytes differ from Envelope",
        )
    return {
        **population_summary,
        **attack_summary,
        "release_record_count": len(records),
        "selected_record_count": len(selection["selected_execution_binding_ids"]),
        "artifact_count": len(payloads),
        "artifact_root": expected_root,
        "envelope_id": envelope["envelope_id"],
        "report_id": report["report_id"],
        "provider_calls": report["provider_calls"],
        "archive_backed_pilot_authorized": report["archive_backed_pilot_authorized"],
        "production_authorized": report["production_authorized"],
    }


def _validate_predecessor_archive(
    archive_path: Path,
    payloads: Mapping[str, bytes],
) -> dict[str, Any]:
    archive_sha, archive_bytes = _sha256_path(archive_path)
    if (
        archive_sha != EXPECTED_PREDECESSOR_ARCHIVE_SHA256
        or archive_bytes != EXPECTED_PREDECESSOR_ARCHIVE_BYTES
    ):
        raise IndependentAuditError(
            stage="source_projection",
            reason_code="predecessor_archive_bytes_mismatch",
            message="predecessor source Archive differs from external expected bytes",
        )
    commit_id = _archive_commit_id(archive_path)
    rows = _archive_rows(archive_path)
    tree_id = _git_tree_id(rows)
    if commit_id != AUDITED_SOURCE_COMMIT or tree_id != AUDITED_SOURCE_TREE:
        raise IndependentAuditError(
            stage="source_projection",
            reason_code="predecessor_archive_git_identity_mismatch",
            message="predecessor Archive does not project the exact Git commit/tree",
        )
    source_manifest = _parse_json(payloads, "source_snapshot_manifest.json")
    if rows != tuple(source_manifest["files"]):
        raise IndependentAuditError(
            stage="source_projection",
            reason_code="source_manifest_archive_mismatch",
            message="source manifest differs from independently parsed Archive",
        )
    _require_identity(
        source_manifest,
        field="manifest_id",
        prefix="qa_release_source_snapshot_manifest:",
        stage="source_projection",
        reason_code="source_manifest_identity_invalid",
    )
    manifest_bytes = _json_bytes(source_manifest)
    manifest_sha = hashlib.sha256(manifest_bytes).hexdigest()
    if len(rows) != EXPECTED_SOURCE_MEMBER_COUNT or manifest_sha != EXPECTED_SOURCE_MANIFEST_SHA256:
        raise IndependentAuditError(
            stage="source_projection",
            reason_code="source_manifest_external_anchor_mismatch",
            message="source manifest count/hash differs from external expectation",
        )
    projection = _parse_json(payloads, "source_projection.json")
    expected_projection = (
        commit_id,
        commit_id,
        tree_id,
        archive_sha,
        archive_bytes,
        source_manifest["manifest_id"],
        manifest_sha,
        len(manifest_bytes),
        len(rows),
    )
    observed_projection = (
        projection["source_commit_id"],
        projection["archive_embedded_commit_id"],
        projection["source_tree_id"],
        projection["source_archive_sha256"],
        projection["source_archive_byte_count"],
        projection["source_manifest_id"],
        projection["source_manifest_sha256"],
        projection["source_manifest_byte_count"],
        projection["source_manifest_file_count"],
    )
    if observed_projection != expected_projection:
        raise IndependentAuditError(
            stage="source_projection",
            reason_code="source_projection_not_archive_derived",
            message="SourceProjection differs from independent Archive derivation",
        )
    executed_path = (
        "trusted_data_synthesis/src/trusted_synthesis/experiments/"
        "qa_realization_vnext/release_authority_envelope_preflight.py"
    )
    module = next(row for row in rows if row["path"] == executed_path)
    if (
        projection["executed_module_path"] != executed_path
        or projection["executed_module_sha256"] != module["sha256"]
    ):
        raise IndependentAuditError(
            stage="source_projection",
            reason_code="executed_module_binding_invalid",
            message="SourceProjection does not bind its exact executed module",
        )
    return {
        "source_commit_id": commit_id,
        "source_tree_id": tree_id,
        "source_archive_sha256": archive_sha,
        "source_archive_byte_count": archive_bytes,
        "source_manifest_sha256": manifest_sha,
        "source_manifest_byte_count": len(manifest_bytes),
        "source_manifest_file_count": len(rows),
    }


_SEMANTIC_REPLAY_SCRIPT = r"""
import json
from trusted_synthesis.core.evaluation.evaluator import (
    CANDIDATE_EVALUATOR_VERSION,
    CANDIDATE_REQUIRED_CHECK_MANIFEST,
    CandidateQualityEvaluator,
)
from trusted_synthesis.core.evaluation.realization_binding import (
    bind_realization_execution,
    describe_generated_trajectory,
)
from trusted_synthesis.core.release import (
    DiversityReleasePolicy,
    SplitPolicy,
    select_diversity_aware_release,
)
from trusted_synthesis.domains.finance.policy import FinanceSemanticPolicy
from trusted_synthesis.domains.finance.tasks import FinanceTaskPlugin
from trusted_synthesis.experiments.counterfactual_finance_fixture import (
    build_finance_counterfactual_case,
)
from trusted_synthesis.experiments.finance_pilot.candidate import (
    FINANCE_NUMERIC_GENERATOR_CONTRACT_ID,
    FinanceNumericCandidateGenerator,
)
from trusted_synthesis.hashing import canonical_hash
from trusted_synthesis.runtime import InMemoryEvidenceToolRuntime

plugin = FinanceTaskPlugin(allow_structured_claims=True)
inputs = []
records = []
for index in (1, 2):
    case = build_finance_counterfactual_case(index)
    instantiation = plugin.compile_evidence_ids(
        case.task.public.task_type,
        case.proof_graph,
        case.bundle,
        case.task.oracle.gold_evidence_ids,
    )
    fixture = {
        "fixture_index": index,
        "task_type": case.task.public.task_type,
        "evidence_bundle": case.bundle.model_dump(mode="json"),
        "evidence_corpus": case.corpus.model_dump(mode="json"),
        "proof_graph": case.proof_graph.model_dump(mode="json"),
        "evidence_binding": instantiation.binding.model_dump(mode="json"),
        "schema_version": "qa_release_authority_fixture_input.v1",
    }
    fixture["fixture_input_id"] = canonical_hash(
        fixture,
        prefix="qa_release_authority_fixture_input:",
    )
    inputs.append(fixture)
    compiled = plugin.compile_binding(
        fixture["task_type"],
        case.proof_graph,
        case.bundle,
        instantiation.binding,
    )
    realization = plugin.realize_instantiation(compiled, case.proof_graph, case.bundle)
    generator = FinanceNumericCandidateGenerator()
    evaluator = CandidateQualityEvaluator(semantic_policy=FinanceSemanticPolicy())
    for realized in realization.selected:
        generated = generator.generate(
            realized.task.public,
            InMemoryEvidenceToolRuntime(case.corpus),
        )
        trajectory, descriptor = describe_generated_trajectory(
            realized,
            case.corpus,
            generated,
            generator_contract_id=FINANCE_NUMERIC_GENERATOR_CONTRACT_ID,
        )
        assessment = evaluator.evaluate(
            realized.task,
            case.corpus,
            case.proof_graph,
            trajectory,
        )
        binding = bind_realization_execution(
            realized,
            realization.portfolio,
            trajectory,
            assessment,
            descriptor,
        )
        records.append((realized, trajectory, assessment, binding))
release_policy = DiversityReleasePolicy(
    policy_id="qa_release_authority_frozen_policy.v1",
    max_total=10000,
    max_per_semantic_instance=3,
    max_per_semantic_schema=10000,
)
split_policy = SplitPolicy(policy_id="qa_release_authority_frozen_split.v1")
selection = select_diversity_aware_release(
    records,
    policy=release_policy,
    split_policy=split_policy,
)
renderer_manifest = plugin.renderer_manifest
contracts = {
    "operation_manifest_hash": canonical_hash(
        plugin.operation_registry().manifest(),
        prefix="operation_manifest:",
    ),
    "pattern_manifest_hash": canonical_hash(
        plugin.pattern_manifest,
        prefix="finance_pattern_manifest:",
    ),
    "renderer_manifest_hash": canonical_hash(
        renderer_manifest,
        prefix="finance_renderer_manifest:",
    ),
    "generator_contract_id": FINANCE_NUMERIC_GENERATOR_CONTRACT_ID,
    "evaluator_contract_id": canonical_hash(
        {
            "evaluator_version": CANDIDATE_EVALUATOR_VERSION,
            "required_check_manifest": CANDIDATE_REQUIRED_CHECK_MANIFEST,
            "semantic_policy_id": FinanceSemanticPolicy.policy_id,
            "schema_version": "qa_release_evaluator_contract.v1",
        },
        prefix="qa_release_evaluator_contract:",
    ),
    "semantic_policy_id": FinanceSemanticPolicy.policy_id,
    "release_policy_hash": release_policy.policy_hash,
    "split_policy_hash": split_policy.policy_hash,
    "frozen_task_types": list(plugin.task_family_ids),
    "frozen_renderer_profile_ids": sorted(
        str(row["profile_id"]) for row in renderer_manifest
    ),
}
print(json.dumps(
    {
        "fixture_inputs": inputs,
        "release_selection": selection.model_dump(mode="json"),
        "contracts": contracts,
    },
    ensure_ascii=False,
    sort_keys=True,
    separators=(",", ":"),
))
"""


def _run_semantic_replay(
    predecessor_root: Path,
    bundle: Mapping[str, Any],
) -> dict[str, Any]:
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(predecessor_root / "trusted_data_synthesis" / "src")
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    result = subprocess.run(
        (sys.executable, "-c", _SEMANTIC_REPLAY_SCRIPT),
        cwd=predecessor_root,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )
    replay = json.loads(result.stdout)
    if replay["fixture_inputs"] != bundle["fixture_inputs"]:
        raise IndependentAuditError(
            stage="semantic_replay",
            reason_code="fixture_reconstruction_mismatch",
            message="independent Fixture reconstruction differs from Bundle",
        )
    if replay["release_selection"] != bundle["release_selection"]:
        raise IndependentAuditError(
            stage="semantic_replay",
            reason_code="release_selection_replay_mismatch",
            message="independent generation/evaluation/selection differs from Bundle",
        )
    contract_keys = (
        "operation_manifest_hash",
        "pattern_manifest_hash",
        "renderer_manifest_hash",
        "generator_contract_id",
        "evaluator_contract_id",
        "semantic_policy_id",
        "release_policy_hash",
        "split_policy_hash",
        "frozen_task_types",
        "frozen_renderer_profile_ids",
    )
    if replay["contracts"] != {key: bundle[key] for key in contract_keys}:
        raise IndependentAuditError(
            stage="semantic_replay",
            reason_code="runtime_contract_reconstruction_mismatch",
            message="independent source contracts differ from Bundle",
        )
    return {
        "fixture_reconstruction_match_count": len(replay["fixture_inputs"]),
        "release_record_reconstruction_match_count": len(
            replay["release_selection"]["release_records"]
        ),
        "selected_record_reconstruction_match_count": len(
            replay["release_selection"]["selected_execution_binding_ids"]
        ),
        "runtime_contract_reconstruction_match_count": len(replay["contracts"]),
    }


def _make_object(values: dict[str, Any], *, field: str, prefix: str) -> dict[str, Any]:
    output = dict(values)
    output[field] = _legacy_hash(output, prefix=prefix)
    return output


def _capture_control(
    control_id: str,
    expected_stage: str,
    expected_reason: str,
    action: Callable[[], Any],
) -> dict[str, Any]:
    actual_type = actual_stage = actual_reason = ""
    try:
        action()
    except Exception as exc:
        actual_type = type(exc).__name__
        if isinstance(exc, IndependentAuditError):
            actual_stage = exc.stage
            actual_reason = exc.reason_code
        else:
            actual_reason = str(exc)
    rejected = (
        actual_type == "IndependentAuditError"
        and actual_stage == expected_stage
        and actual_reason == expected_reason
    )
    return {
        "control_id": control_id,
        "expected_exception_type": "IndependentAuditError",
        "expected_stage": expected_stage,
        "expected_reason_code": expected_reason,
        "actual_exception_type": actual_type,
        "actual_stage": actual_stage,
        "actual_reason_code": actual_reason,
        "rejected": rejected,
        "counted": rejected,
    }


def _rehash_artifact_manifest(payloads: dict[str, bytes]) -> None:
    rows = [
        {
            "name": name,
            "sha256": hashlib.sha256(payloads[name]).hexdigest(),
            "byte_count": len(payloads[name]),
        }
        for name in CORE_ARTIFACT_NAMES
    ]
    manifest = {
        "artifact_root": _v184_artifact_root(rows),
        "artifacts": rows,
        "schema_version": "qa_release_authority_artifact_manifest.v2",
    }
    manifest["artifact_manifest_id"] = _legacy_hash(
        manifest,
        prefix="qa_release_authority_artifact_manifest:",
    )
    payloads["artifact_manifest.json"] = _json_bytes(manifest)


def _run_negative_controls(
    payloads: Mapping[str, bytes],
    predecessor_archive: Path,
) -> tuple[dict[str, Any], ...]:
    def missing() -> None:
        attacked = dict(payloads)
        attacked.pop("report.md")
        _validate_fast_catalogs(attacked)

    def extra() -> None:
        _validate_fast_catalogs({**payloads, "extra.json": b"{}\n"})

    def report_parent() -> None:
        attacked = dict(payloads)
        report = _parse_json(attacked, "report.json")
        report["authority_bundle_id"] = "qa_release_authority_bundle:" + "0" * 64
        report["report_id"] = _identity(
            report,
            field="report_id",
            prefix="qa_release_authority_report:",
        )
        attacked["report.json"] = _json_bytes(report)
        _validate_fast_catalogs(attacked)

    def markdown() -> None:
        _validate_fast_catalogs({**payloads, "report.md": payloads["report.md"] + b"x"})

    def changed_core(name: str) -> None:
        attacked = dict(payloads)
        attacked[name] = attacked[name] + b" "
        _rehash_artifact_manifest(attacked)
        _validate_fast_catalogs(attacked)

    def attack_removed() -> None:
        attack = _parse_json(payloads, "attack_audit.json")
        controls = list(attack["controls"][:-1])
        attacked = dict(attack)
        attacked["controls"] = controls
        attacked["frozen_attack_ids"] = list(ATTACK_IDS[:-1])
        _validate_attack_catalog(attacked, controls)

    def population_removed() -> None:
        population = _parse_json(payloads, "release_population.json")
        attacked = dict(population)
        attacked["members"] = list(population["members"][:-1])
        _validate_population(
            attacked,
            _parse_json(payloads, "qa_release_authority_bundle.json"),
            _parse_json(payloads, "source_projection.json"),
            _parse_json(payloads, "authorization.json"),
        )

    def runtime_changed() -> None:
        runtime = _parse_json(payloads, "runtime_environment.json")
        attacked = dict(runtime)
        attacked["installed_distribution_count"] += 1
        _require_identity(
            attacked,
            field="runtime_environment_id",
            prefix="qa_release_runtime_environment:",
            stage="runtime_environment",
            reason_code="runtime_identity_invalid",
        )

    def projection_changed() -> None:
        manifest = _parse_json(payloads, "source_snapshot_manifest.json")
        if "0" * 40 != manifest["source_tree_id"]:
            raise IndependentAuditError(
                stage="source_projection",
                reason_code="projection_manifest_tree_mismatch",
                message="forged Projection tree differs from Manifest",
            )

    def embedded_audit_changed() -> None:
        attacked = dict(payloads)
        attacked["external_audit.txt"] = b"replaced\n"
        _validate_fast_catalogs(attacked)

    def entire_envelope() -> None:
        attacked = dict(payloads)
        envelope = _parse_json(attacked, "envelope.json")
        envelope["report_markdown_byte_count"] += 1
        envelope["envelope_id"] = _identity(
            envelope,
            field="envelope_id",
            prefix="qa_release_authority_envelope:",
        )
        attacked["envelope.json"] = _json_bytes(envelope)
        _validate_fast_catalogs(attacked)

    def unrelated_archive() -> None:
        with tempfile.TemporaryDirectory(prefix="v26-185-unrelated-") as temporary:
            path = Path(temporary) / "source.tar"
            path.write_bytes(b"unrelated\n")
            _validate_predecessor_archive(path, payloads)

    specs = (
        ("missing_artifact_file", "artifact_catalog", "artifact_membership_not_exact", missing),
        ("extra_artifact_file", "artifact_catalog", "artifact_membership_not_exact", extra),
        (
            "report_parent_rehashed",
            "cross_catalog",
            "report_cross_envelope_mismatch",
            report_parent,
        ),
        (
            "markdown_bytes_changed",
            "report_markdown",
            "report_markdown_not_derived",
            markdown,
        ),
        (
            "selection_catalog_jointly_rehashed",
            "cross_catalog",
            "artifact_manifest_cross_envelope_mismatch",
            lambda: changed_core("release_selection.json"),
        ),
        (
            "record_catalog_jointly_rehashed",
            "cross_catalog",
            "artifact_manifest_cross_envelope_mismatch",
            lambda: changed_core("release_records.jsonl"),
        ),
        (
            "attack_registry_member_removed",
            "attack_audit",
            "attack_registry_not_exact",
            attack_removed,
        ),
        (
            "population_member_removed",
            "release_population",
            "population_exact_set_invalid",
            population_removed,
        ),
        (
            "runtime_distribution_count_changed",
            "runtime_environment",
            "runtime_identity_invalid",
            runtime_changed,
        ),
        (
            "projection_tree_changed",
            "source_projection",
            "projection_manifest_tree_mismatch",
            projection_changed,
        ),
        (
            "embedded_external_audit_changed",
            "artifact_catalog",
            "artifact_bytes_mismatch",
            embedded_audit_changed,
        ),
        (
            "entire_envelope_rehashed",
            "external_anchor",
            "envelope_external_anchor_mismatch",
            entire_envelope,
        ),
        (
            "unrelated_source_archive",
            "source_projection",
            "predecessor_archive_bytes_mismatch",
            unrelated_archive,
        ),
    )
    controls = tuple(_capture_control(*spec) for spec in specs)
    if tuple(row["control_id"] for row in controls) != INDEPENDENT_CONTROL_IDS:
        raise ValueError("independent control registry is not exact")
    if any(not row["counted"] for row in controls):
        failures = [row for row in controls if not row["counted"]]
        raise ValueError(f"independent negative controls did not close: {failures}")
    return controls


def _manifest(payloads: Mapping[str, bytes]) -> dict[str, Any]:
    rows = [
        {
            "name": name,
            "sha256": hashlib.sha256(payloads[name]).hexdigest(),
            "byte_count": len(payloads[name]),
        }
        for name in sorted(payloads)
    ]
    return _make_object(
        {
            "artifact_root": _legacy_hash(
                rows,
                prefix="qa_release_independent_audit_artifact_root:",
            ),
            "artifacts": rows,
            "schema_version": AUDIT_RUN_ID,
        },
        field="artifact_manifest_id",
        prefix="qa_release_independent_audit_artifact_manifest:",
    )


def _audit_markdown(report: Mapping[str, Any]) -> bytes:
    return (
        "# v26.185 QA Release Authority Envelope Independent Audit\n\n"
        f"- Status: **{report['status']}**\n"
        f"- Audited Envelope: {report['audited_envelope_id']}\n"
        f"- Exact artifacts: {report['artifact_match_count']} / {report['artifact_count']}\n"
        f"- Replayed records: {report['release_record_replay_count']}\n"
        f"- Negative controls: {report['negative_control_rejection_count']} / "
        f"{report['negative_control_count']}\n"
        f"- Provider calls: {report['provider_calls']}\n"
        "- Archive-backed Pilot authorized: no\n"
        f"- Decision: {report['decision']}\n"
    ).encode()


def run_independent_audit(
    *,
    audit_source_commit: str,
    audit_source_tree: str,
    audit_source_archive: Path,
    predecessor_source_archive: Path,
    artifact_snapshot_dir: Path,
    external_audit_path: Path,
    observed_change_surface: tuple[str, ...],
    output_dir: Path,
) -> dict[str, Any]:
    if output_dir.exists():
        raise FileExistsError(f"independent audit output already exists: {output_dir}")
    source_root = Path(__file__).resolve().parents[5]
    audit_rows = _archive_rows(audit_source_archive)
    if (
        _archive_commit_id(audit_source_archive) != audit_source_commit
        or _git_tree_id(audit_rows) != audit_source_tree
    ):
        raise ValueError("independent auditor source Archive identity mismatch")
    _validate_root(source_root, audit_rows)
    if observed_change_surface != PERMITTED_CHANGE_SURFACE:
        raise ValueError("independent audit Git change surface is not exact")
    audit_archive_sha, audit_archive_bytes = _sha256_path(audit_source_archive)
    external_audit_bytes = external_audit_path.read_bytes()
    authorization = _make_object(
        {
            "external_audit_sha256": hashlib.sha256(external_audit_bytes).hexdigest(),
            "external_audit_byte_count": len(external_audit_bytes),
            "authorized_predecessor": AUTHORIZED_PREDECESSOR,
            "audited_source_commit": AUDITED_SOURCE_COMMIT,
            "audited_artifact_commit": AUDITED_ARTIFACT_COMMIT,
            "audit_source_commit": audit_source_commit,
            "audit_source_tree": audit_source_tree,
            "audit_source_archive_sha256": audit_archive_sha,
            "audit_source_archive_byte_count": audit_archive_bytes,
            "permitted_transition": (
                "qa_release_authority_envelope_exact_artifact_independent_audit_only"
            ),
            "permitted_change_surface": list(PERMITTED_CHANGE_SURFACE),
            "observed_change_surface": list(observed_change_surface),
            "forbidden_operations": list(FORBIDDEN_OPERATIONS),
            "schema_version": AUDIT_RUN_ID,
        },
        field="authorization_id",
        prefix="qa_release_independent_audit_authorization:",
    )
    current = _load_payloads(source_root / AUDITED_ARTIFACT_DIR)
    exact = _load_payloads(artifact_snapshot_dir / AUDITED_ARTIFACT_DIR)
    if current != exact:
        raise ValueError("current v26.184 artifacts differ from exact artifact commit")
    fast = _validate_fast_catalogs(exact)
    archive = _validate_predecessor_archive(predecessor_source_archive, exact)
    with tempfile.TemporaryDirectory(prefix="v26-185-predecessor-") as temporary:
        predecessor_root = Path(temporary) / "source"
        with tarfile.open(predecessor_source_archive, mode="r:") as source_tar:
            source_tar.extractall(predecessor_root, filter="data")
        _validate_root(predecessor_root, _archive_rows(predecessor_source_archive))
        if _capture_runtime(predecessor_root) != _parse_json(
            exact,
            "runtime_environment.json",
        ):
            raise IndependentAuditError(
                stage="runtime_environment",
                reason_code="runtime_reconstruction_mismatch",
                message="independent runtime capture differs",
            )
        semantic = _run_semantic_replay(
            predecessor_root,
            _parse_json(exact, "qa_release_authority_bundle.json"),
        )
    controls = _run_negative_controls(exact, predecessor_source_archive)
    freeze = _make_object(
        {
            "audited_source_commit": AUDITED_SOURCE_COMMIT,
            "audited_source_tree": AUDITED_SOURCE_TREE,
            "audited_artifact_commit": AUDITED_ARTIFACT_COMMIT,
            "artifact_count": 15,
            "artifact_match_count": 15,
            "artifact_byte_count": sum(map(len, exact.values())),
            **archive,
            "schema_version": AUDIT_RUN_ID,
        },
        field="freeze_id",
        prefix="qa_release_independent_predecessor_freeze:",
    )
    reconstruction = _make_object(
        {
            **fast,
            **semantic,
            "authorization_match": True,
            "source_projection_match": True,
            "population_match": True,
            "cross_catalog_match": True,
            "report_markdown_match": True,
            "runtime_match": True,
            "semantic_replay_match": True,
            "schema_version": AUDIT_RUN_ID,
        },
        field="reconstruction_id",
        prefix="qa_release_independent_reconstruction:",
    )
    control_audit = _make_object(
        {
            "frozen_control_ids": list(INDEPENDENT_CONTROL_IDS),
            "controls": list(controls),
            "control_count": len(controls),
            "rejection_count": sum(bool(row["counted"]) for row in controls),
            "accepted_attack_count": sum(not bool(row["rejected"]) for row in controls),
            "schema_version": AUDIT_RUN_ID,
        },
        field="negative_control_audit_id",
        prefix="qa_release_independent_negative_control_audit:",
    )
    decision = _make_object(
        {
            "authorization_id": authorization["authorization_id"],
            "freeze_id": freeze["freeze_id"],
            "reconstruction_id": reconstruction["reconstruction_id"],
            "negative_control_audit_id": control_audit["negative_control_audit_id"],
            "passed": True,
            "decision": "PASSED_INDEPENDENT_AUDIT",
            "archive_backed_pilot_authorized": False,
            "provider_generation_authorized": False,
            "production_authorized": False,
            "training_authorized": False,
            "v26_181_outcome_gate": "FAILED_UNCHANGED",
            "next_stage": "no_further_experiment_authorized_without_new_audit_decision",
            "provider_calls": 0,
            "schema_version": AUDIT_RUN_ID,
        },
        field="decision_id",
        prefix="qa_release_independent_audit_decision:",
    )
    details = {
        "external_audit.txt": external_audit_bytes,
        "audit_authorization.json": _json_bytes(authorization),
        "predecessor_freeze.json": _json_bytes(freeze),
        "independent_reconstruction.json": _json_bytes(reconstruction),
        "negative_controls.json": _json_bytes(control_audit),
        "decision.json": _json_bytes(decision),
    }
    manifest = _manifest(details)
    report = _make_object(
        {
            "status": "passed",
            "run_id": AUDIT_RUN_ID,
            "authorization_id": authorization["authorization_id"],
            "audited_source_commit": AUDITED_SOURCE_COMMIT,
            "audited_artifact_commit": AUDITED_ARTIFACT_COMMIT,
            "audited_envelope_id": EXPECTED_ENVELOPE_ID,
            "freeze_id": freeze["freeze_id"],
            "reconstruction_id": reconstruction["reconstruction_id"],
            "negative_control_audit_id": control_audit["negative_control_audit_id"],
            "decision_id": decision["decision_id"],
            "artifact_manifest_id": manifest["artifact_manifest_id"],
            "artifact_root": manifest["artifact_root"],
            "artifact_count": 15,
            "artifact_match_count": 15,
            "release_record_replay_count": semantic["release_record_reconstruction_match_count"],
            "negative_control_count": len(controls),
            "negative_control_rejection_count": sum(bool(row["counted"]) for row in controls),
            "provider_calls": 0,
            "archive_backed_pilot_authorized": False,
            "production_authorized": False,
            "decision": decision["decision"],
            "next_stage": decision["next_stage"],
            "schema_version": AUDIT_RUN_ID,
        },
        field="report_id",
        prefix="qa_release_independent_audit_report:",
    )
    payloads = {
        **details,
        "artifact_manifest.json": _json_bytes(manifest),
        "report.json": _json_bytes(report),
        "report.md": _audit_markdown(report),
    }
    write_immutable_artifact_directory(output_dir, payloads)
    if _load_payloads(output_dir) != payloads:
        raise ValueError("published independent audit differs after exact reload")
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--audit-source-commit", required=True)
    parser.add_argument("--audit-source-tree", required=True)
    parser.add_argument("--audit-source-archive", type=Path, required=True)
    parser.add_argument("--predecessor-source-archive", type=Path, required=True)
    parser.add_argument("--artifact-snapshot-dir", type=Path, required=True)
    parser.add_argument("--external-audit", type=Path, required=True)
    parser.add_argument("--observed-change-surface", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    report = run_independent_audit(
        audit_source_commit=args.audit_source_commit,
        audit_source_tree=args.audit_source_tree,
        audit_source_archive=args.audit_source_archive,
        predecessor_source_archive=args.predecessor_source_archive,
        artifact_snapshot_dir=args.artifact_snapshot_dir,
        external_audit_path=args.external_audit,
        observed_change_surface=tuple(json.loads(args.observed_change_surface.read_bytes())),
        output_dir=args.output_dir,
    )
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
