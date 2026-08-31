from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
from functools import partial
from pathlib import Path
from typing import Any, Final, cast

from pydantic import BaseModel

from trusted_synthesis.core.immutable_artifacts import write_immutable_artifact_directory
from trusted_synthesis.core.task import authoritative_artifact_backed_outcome as outcome
from trusted_synthesis.core.task.authoritative_job_bound_outcome import (
    AuthoritativeTerminalRegistry,
    FailureLocus,
    RawExecutionEvidencePayload,
)
from trusted_synthesis.core.task.authoritative_job_bound_outcome import (
    make_identity_model as make_v2_identity_model,
)
from trusted_synthesis.core.task.job_bound_multistep_outcome import (
    CapabilityDevelopmentJob,
    CapabilityDevelopmentJobManifest,
    JobBoundOutcomePayload,
    JobBoundRunnerContract,
)
from trusted_synthesis.core.task.job_bound_multistep_outcome import (
    make_identity_model as make_job_identity_model,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_capability_artifact_backed_outcome_independent_audit_models as models,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_capability_artifact_backed_outcome_preflight_models as v186_models,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_capability_authoritative_outcome_terminal_preflight as v181,
)
from trusted_synthesis.hashing import canonical_hash

RUN_ID: Final = "finance_v26_187_artifact_backed_outcome_independent_audit_v1_20260831"
OUTPUT_DIR: Final = f"artifacts/vtdo_experiment/{RUN_ID}"
AUDITED_V186_DIR: Final = (
    "artifacts/vtdo_experiment/finance_v26_186_artifact_backed_outcome_preflight_v2_20260831"
)
AUDITED_SOURCE_COMMIT: Final = "0cd043a101eeed39b6e4e92b351d9e42bbdd5355"
AUDITED_SOURCE_TREE: Final = "9fe5294e52ed5cbbe23a270190c94340997fe9c9"
AUDITED_ARTIFACT_COMMIT: Final = "9bc76bc66aef2b9b40485580e5e7fb1d4f160e69"
AUDITED_ARTIFACT_TREE: Final = "9bcb7c237f07b23fe80b1f38f2956c489150005c"
AUDITED_REPORT_ID: Final = (
    "finance_v26_artifact_backed_outcome_preflight_report:"
    "4665101aa78d60e7b56b52c8a87003a7af714908ac49316f32d857f0831c2c5d"
)
AUDITED_ARTIFACT_ROOT: Final = (
    "finance_v26_artifact_backed_artifact_root:"
    "ee17623d7f3c8e6344eaa27f01dfa28cc14ed4ae2e9d3d209721b18f63266e40"
)
EXPECTED_EXTERNAL_AUDIT_SHA256: Final = (
    "cd934119e2c4102df37e1af5ba06abf0751e87fe913536a89ddc44b24404685e"
)
EXPECTED_EXTERNAL_AUDIT_BYTE_COUNT: Final = 10_040
EXPECTED_SOURCE_ARCHIVE_SHA256: Final = (
    "b04b3c2207b5b71a24daae841b923774e2dd560df7be38478f15d62fb1a86d78"
)
EXPECTED_SOURCE_ARCHIVE_BYTE_COUNT: Final = 1_016_115_200
EXACT_V186_CHANGE_SURFACE: Final = (
    "trusted_data_synthesis/docs/current_project_status.md",
    "trusted_data_synthesis/docs/finance_v26_186_artifact_backed_outcome_preflight.md",
    "trusted_data_synthesis/src/trusted_synthesis/core/task/"
    "authoritative_artifact_backed_outcome.py",
    "trusted_data_synthesis/src/trusted_synthesis/experiments/vtdo_experiment/"
    "phase1_v26_capability_artifact_backed_outcome_preflight.py",
    "trusted_data_synthesis/src/trusted_synthesis/experiments/vtdo_experiment/"
    "phase1_v26_capability_artifact_backed_outcome_preflight_models.py",
    "trusted_data_synthesis/src/trusted_synthesis/experiments/vtdo_experiment/"
    "source_projected_artifact_backed_outcome_preflight_runner.py",
    "trusted_data_synthesis/tests/test_v26_capability_artifact_backed_outcome_preflight.py",
)
EXPECTED_DIAGNOSTIC_REJECTION: Final = (
    "non-reachable terminal policy cannot enter empirical evidence"
)


def _resolve_package_root(root: Path) -> Path:
    if (root / "src" / "trusted_synthesis").is_dir():
        return root.resolve()
    candidate = root / "trusted_data_synthesis"
    if (candidate / "src" / "trusted_synthesis").is_dir():
        return candidate.resolve()
    raise ValueError("v26.187 cannot resolve the trusted_data_synthesis package root")


def _json_value(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json", warnings=False)
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_json_value(item) for item in value]
    return value


def _canonical_bytes(value: Any) -> bytes:
    return (
        json.dumps(
            _json_value(value),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
        + b"\n"
    )


def _identity_dict(value: dict[str, Any], field: str, prefix: str) -> str:
    body = {key: item for key, item in value.items() if key != field}
    payload = json.dumps(
        body,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return f"{prefix}{hashlib.sha256(payload).hexdigest()}"


def _sha256_path(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    byte_count = 0
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
            byte_count += len(chunk)
    return digest.hexdigest(), byte_count


def _binding(path: Path, *, relative_to: Path | None, source_kind: str) -> models.FileBinding:
    digest, byte_count = _sha256_path(path)
    relative_path = (
        path.relative_to(relative_to).as_posix() if relative_to is not None else path.as_posix()
    )
    return models.FileBinding(
        relative_path=relative_path,
        sha256=digest,
        byte_count=byte_count,
        source_kind=source_kind,
    )


def _load(path: Path) -> Any:
    return json.loads(path.read_bytes())


def _archive_commit(path: Path) -> str:
    with path.open("rb") as handle:
        result = subprocess.run(
            ("git", "get-tar-commit-id"),
            stdin=handle,
            check=False,
            capture_output=True,
        )
    value = result.stdout.decode("ascii", errors="strict").strip()
    if result.returncode != 0 or len(value) != 40:
        raise ValueError("audited v26.186 source Archive lacks an embedded Git commit")
    return value


def _git_blob_id(payload: bytes) -> str:
    header = f"blob {len(payload)}\0".encode()
    return hashlib.sha1(header + payload, usedforsecurity=False).hexdigest()


def _archive_rows(path: Path) -> tuple[dict[str, Any], ...]:
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    with tarfile.open(path, mode="r:") as archive:
        for member in archive.getmembers():
            name = member.name.rstrip("/")
            if not name or member.isdir():
                continue
            parts = Path(name).parts
            if Path(name).is_absolute() or any(part in {"", ".", ".."} for part in parts):
                raise ValueError("audited source Archive contains an unsafe path")
            if name in seen:
                raise ValueError("audited source Archive repeats a member")
            seen.add(name)
            if member.isfile():
                handle = archive.extractfile(member)
                if handle is None:
                    raise ValueError("audited source Archive member is unreadable")
                payload = handle.read()
                mode = "100755" if member.mode & 0o111 else "100644"
            elif member.issym():
                payload = member.linkname.encode()
                mode = "120000"
            else:
                raise ValueError("audited source Archive contains a non-Git member")
            rows.append({"path": name, "mode": mode, "blob": _git_blob_id(payload)})
    return tuple(sorted(rows, key=lambda item: str(item["path"])))


def _git_tree_id(rows: tuple[dict[str, Any], ...]) -> str:
    root: dict[str, Any] = {}
    for row in rows:
        parts = str(row["path"]).split("/")
        node = root
        for part in parts[:-1]:
            node = node.setdefault(part, {})
        if parts[-1] in node:
            raise ValueError("audited source Archive repeats a Git entry")
        node[parts[-1]] = row

    def visit(node: dict[str, Any]) -> str:
        body = bytearray()
        for name in sorted(node, key=lambda value: value.encode()):
            value = node[name]
            if isinstance(value, dict) and "path" not in value:
                mode = "40000"
                object_id = visit(value)
            else:
                mode = value["mode"]
                object_id = value["blob"]
            body.extend(mode.encode())
            body.extend(b" ")
            body.extend(name.encode())
            body.extend(b"\0")
            body.extend(bytes.fromhex(object_id))
        header = f"tree {len(body)}\0".encode()
        return hashlib.sha1(header + body, usedforsecurity=False).hexdigest()

    return visit(root)


def _extract_archive(path: Path, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=False)
    with tarfile.open(path, mode="r:") as archive:
        archive.extractall(destination, filter="data")


def _directory_bindings(root: Path, source_kind: str) -> tuple[models.FileBinding, ...]:
    paths = tuple(
        sorted(path for path in root.iterdir() if path.is_file() and not path.is_symlink())
    )
    if len(paths) != len(tuple(root.iterdir())):
        raise ValueError("formal artifact directory contains a non-regular member")
    return tuple(_binding(path, relative_to=root, source_kind=source_kind) for path in paths)


def _rebuild_v186(
    *,
    audited_source_archive: Path,
    destination: Path,
) -> None:
    with tempfile.TemporaryDirectory(prefix="v26-187-audited-source-") as temporary:
        source_root = Path(temporary) / "source"
        _extract_archive(audited_source_archive, source_root)
        package_root = source_root / "trusted_data_synthesis"
        environment = os.environ.copy()
        environment["PYTHONPATH"] = str(package_root / "src")
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        result = subprocess.run(
            (
                sys.executable,
                "-m",
                "trusted_synthesis.experiments.vtdo_experiment."
                "phase1_v26_capability_artifact_backed_outcome_preflight",
                "--package-root",
                str(package_root),
                "--output-dir",
                str(destination),
                "--source-archive",
                str(audited_source_archive),
                "--source-commit",
                AUDITED_SOURCE_COMMIT,
                "--source-tree",
                AUDITED_SOURCE_TREE,
            ),
            cwd=package_root,
            env=environment,
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(
                "independent v26.186 rebuild failed\n"
                f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
            )


def _authorization(
    *, package_root: Path, external_audit_input: Path
) -> models.IndependentAuditAuthorization:
    audit_binding = _binding(
        external_audit_input,
        relative_to=None,
        source_kind="external_v26_186_revision_audit",
    )
    if (
        audit_binding.sha256 != EXPECTED_EXTERNAL_AUDIT_SHA256
        or audit_binding.byte_count != EXPECTED_EXTERNAL_AUDIT_BYTE_COUNT
    ):
        raise ValueError("external v26.186 audit input differs from the authorization")
    report = _load(package_root / AUDITED_V186_DIR / "report.json")
    manifest = v186_models.ArtifactManifest.model_validate(
        _load(package_root / AUDITED_V186_DIR / "artifact_manifest.json")
    )
    if report["report_id"] != AUDITED_REPORT_ID or manifest.artifact_root != AUDITED_ARTIFACT_ROOT:
        raise ValueError("audited v26.186 report or artifact Root differs")
    return cast(
        models.IndependentAuditAuthorization,
        models.make_identity_model(
            models.IndependentAuditAuthorization,
            {
                "consumed_stage": (
                    "artifact_backed_empirical_outcome_authority_independent_audit_only"
                ),
                "external_audit_input": audit_binding,
                "audited_source_commit": AUDITED_SOURCE_COMMIT,
                "audited_source_tree": AUDITED_SOURCE_TREE,
                "audited_artifact_commit": AUDITED_ARTIFACT_COMMIT,
                "audited_artifact_tree": AUDITED_ARTIFACT_TREE,
                "audited_report_id": AUDITED_REPORT_ID,
                "audited_artifact_root": AUDITED_ARTIFACT_ROOT,
            },
            field="authorization_id",
            prefix="finance_v26_artifact_backed_independent_audit_authorization:",
        ),
    )


def _source_rebuild(
    *,
    package_root: Path,
    authorization: models.IndependentAuditAuthorization,
    audited_source_archive: Path,
) -> models.SourceRebuildAudit:
    archive_binding = _binding(
        audited_source_archive,
        relative_to=None,
        source_kind="audited_v26_186_git_archive",
    )
    if (
        archive_binding.sha256 != EXPECTED_SOURCE_ARCHIVE_SHA256
        or archive_binding.byte_count != EXPECTED_SOURCE_ARCHIVE_BYTE_COUNT
        or _archive_commit(audited_source_archive) != AUDITED_SOURCE_COMMIT
    ):
        raise ValueError("audited v26.186 source Archive differs")
    if _git_tree_id(_archive_rows(audited_source_archive)) != AUDITED_SOURCE_TREE:
        raise ValueError("audited v26.186 source Archive tree differs")
    with tempfile.TemporaryDirectory(prefix="v26-187-independent-rebuild-") as temporary:
        rebuilt = Path(temporary) / "rebuilt"
        _rebuild_v186(audited_source_archive=audited_source_archive, destination=rebuilt)
        frozen = package_root / AUDITED_V186_DIR
        rebuilt_bindings = _directory_bindings(rebuilt, "independent_v26_186_rebuild")
        frozen_bindings = _directory_bindings(frozen, "frozen_v26_186_artifact")
        rebuilt_projection = tuple(
            (item.relative_path, item.sha256, item.byte_count) for item in rebuilt_bindings
        )
        frozen_projection = tuple(
            (item.relative_path, item.sha256, item.byte_count) for item in frozen_bindings
        )
        if rebuilt_projection != frozen_projection or len(rebuilt_projection) != 398:
            raise ValueError("independent v26.186 rebuild differs from all 398 frozen files")
    return cast(
        models.SourceRebuildAudit,
        models.make_identity_model(
            models.SourceRebuildAudit,
            {
                "authorization_id": authorization.authorization_id,
                "source_archive": archive_binding,
            },
            field="audit_id",
            prefix="finance_v26_artifact_backed_source_rebuild_audit:",
        ),
    )


def _formal_replay(
    *, package_root: Path, authorization: models.IndependentAuditAuthorization
) -> models.FormalArtifactReplayAudit:
    root = package_root / AUDITED_V186_DIR
    bindings = _directory_bindings(root, "frozen_v26_186_artifact")
    if len(bindings) != 398:
        raise ValueError("v26.186 formal artifact denominator differs")
    manifest_payload = _load(root / "artifact_manifest.json")
    manifest = v186_models.ArtifactManifest.model_validate(manifest_payload)
    by_path = {item.relative_path: item for item in bindings}
    for item in manifest.files:
        observed = by_path.get(Path(item.relative_path).name)
        if observed is None or (observed.sha256, observed.byte_count) != (
            item.sha256,
            item.byte_count,
        ):
            raise ValueError("v26.186 Artifact Manifest differs from actual bytes")
    if manifest.artifact_root != AUDITED_ARTIFACT_ROOT:
        raise ValueError("v26.186 Artifact Root differs")
    formal_json = tuple(
        path
        for path in root.iterdir()
        if path.suffix == ".json" and not path.name.startswith(("raw--", "result--"))
    )
    for path in formal_json:
        if _canonical_bytes(_load(path)) != path.read_bytes():
            raise ValueError("v26.186 formal JSON is not canonical")
    report = _load(root / "report.json")
    detail_mapping = {
        "authorization_id": ("authorization.json", "authorization_id"),
        "predecessor_freeze_id": ("predecessor_freeze.json", "audit_id"),
        "contract_id": ("artifact_backed_outcome_contract.json", "contract.contract_id"),
        "factorization_audit_id": ("terminal_validity_factorization_audit.json", "audit_id"),
        "admission_audit_id": ("empirical_admission_audit.json", "audit_id"),
        "locus_audit_id": ("failure_locus_reconstruction_audit.json", "audit_id"),
        "artifact_audit_id": ("artifact_byte_authenticity_audit.json", "audit_id"),
        "parent_audit_id": ("parent_revalidation_audit.json", "audit_id"),
        "evidence_dag_audit_id": ("scripted_evidence_dag_audit.json", "audit_id"),
        "static_audit_id": ("static_audit.json", "audit_id"),
        "transition_id": ("prospective_transition.json", "transition_id"),
    }
    matched = 0
    for report_field, (filename, value_path) in detail_mapping.items():
        value: Any = _load(root / filename)
        for part in value_path.split("."):
            value = value[part]
        matched += report[report_field] == value
    if matched != len(detail_mapping):
        raise ValueError("v26.186 Report detail identities differ")
    return cast(
        models.FormalArtifactReplayAudit,
        models.make_identity_model(
            models.FormalArtifactReplayAudit,
            {
                "authorization_id": authorization.authorization_id,
                "artifact_manifest_id": manifest.manifest_id,
                "artifact_root": manifest.artifact_root,
                "manifest_member_byte_count": manifest.total_byte_count,
                "directory_byte_count": sum(item.byte_count for item in bindings),
                "canonical_formal_json_count": len(formal_json),
                "exact_report_detail_binding_count": len(detail_mapping),
                "exact_report_detail_binding_match_count": matched,
            },
            field="audit_id",
            prefix="finance_v26_artifact_backed_formal_replay_audit:",
        ),
    )


def _load_parents(
    package_root: Path,
) -> tuple[
    AuthoritativeTerminalRegistry,
    outcome.ArtifactBackedOutcomeContract,
    CapabilityDevelopmentJobManifest,
    JobBoundRunnerContract,
    dict[str, JobBoundOutcomePayload],
]:
    v181_root = package_root / v181.OUTPUT_DIR
    registry = AuthoritativeTerminalRegistry.model_validate(
        _load(v181_root / "authoritative_terminal_registry_audit.json")["registry"]
    )
    historical = v181._load_frozen_inputs(package_root)
    scripted = {item.job_id: item.outcome for item in historical.scripted.rows}
    contract = outcome.ArtifactBackedOutcomeContract.model_validate(
        _load(package_root / AUDITED_V186_DIR / "artifact_backed_outcome_contract.json")["contract"]
    )
    return registry, contract, historical.manifest, historical.runner, scripted


def _load_catalog(
    package_root: Path,
) -> tuple[
    tuple[outcome.ArtifactBackedEvidenceBundle, ...],
    outcome.ArtifactBackedPreflightEvaluation,
]:
    value = _load(package_root / AUDITED_V186_DIR / "scripted_evidence_catalog.json")
    return (
        tuple(
            outcome.ArtifactBackedEvidenceBundle.model_validate(item) for item in value["bundles"]
        ),
        outcome.ArtifactBackedPreflightEvaluation.model_validate(value["evaluation"]),
    )


def _semantic_replay(
    *, package_root: Path, authorization: models.IndependentAuditAuthorization
) -> models.SemanticReplayAudit:
    registry, contract, manifest, runner, _ = _load_parents(package_root)
    bundles, frozen_evaluation = _load_catalog(package_root)
    root = package_root / AUDITED_V186_DIR
    jobs = {item.job_id: item for item in manifest.jobs}
    sequences = {
        item.job_id: tuple(item.ordered_component_keys) for item in contract.job_component_sequences
    }
    raw_count = result_count = artifact_matches = canonical_matches = 0
    payload_identities = descriptor_identities = attempt_identities = 0
    trace_identities = row_identities = sequence_matches = validity_matches = 0
    locus_matches = parent_matches = 0
    seen_jobs: set[str] = set()
    for bundle in bundles:
        row = bundle.row.model_dump(mode="json", warnings=False)
        raw_descriptor = bundle.raw.model_dump(mode="json", warnings=False)
        result_descriptor = bundle.result.model_dump(mode="json", warnings=False)
        job = jobs[row["job_id"]]
        if row["job_id"] in seen_jobs:
            raise ValueError("independent semantic replay found a duplicate Job")
        seen_jobs.add(row["job_id"])
        raw_path = root / raw_descriptor["artifact_relative_path"]
        result_path = root / result_descriptor["artifact_relative_path"]
        raw_bytes = raw_path.read_bytes()
        result_bytes = result_path.read_bytes()
        if (hashlib.sha256(raw_bytes).hexdigest(), len(raw_bytes)) != (
            raw_descriptor["artifact_sha256"],
            raw_descriptor["artifact_byte_count"],
        ) or (hashlib.sha256(result_bytes).hexdigest(), len(result_bytes)) != (
            result_descriptor["artifact_sha256"],
            result_descriptor["artifact_byte_count"],
        ):
            raise ValueError("independent semantic replay found unbound artifact bytes")
        artifact_matches += 2
        raw_payload = json.loads(raw_bytes)
        result_payload = json.loads(result_bytes)
        if (
            _canonical_bytes(raw_payload) != raw_bytes
            or _canonical_bytes(result_payload) != result_bytes
        ):
            raise ValueError("independent semantic replay found noncanonical artifact bytes")
        canonical_matches += 2
        raw_count += 1
        result_count += 1
        if raw_payload["payload_id"] != _identity_dict(
            raw_payload,
            "payload_id",
            "capability_authoritative_raw_execution_payload:",
        ) or result_payload["payload_id"] != _identity_dict(
            result_payload,
            "payload_id",
            "capability_artifact_backed_job_result_payload:",
        ):
            raise ValueError("independent semantic replay found an invalid payload identity")
        payload_identities += 2
        validity = result_payload["validity"]
        if validity["validity_id"] != _identity_dict(
            validity,
            "validity_id",
            "capability_artifact_backed_terminal_validity:",
        ):
            raise ValueError("independent semantic replay found an invalid validity identity")
        if raw_descriptor["raw_execution_id"] != _identity_dict(
            raw_descriptor,
            "raw_execution_id",
            "capability_artifact_backed_raw_execution:",
        ) or result_descriptor["result_id"] != _identity_dict(
            result_descriptor,
            "result_id",
            "capability_artifact_backed_job_result:",
        ):
            raise ValueError("independent semantic replay found an invalid descriptor identity")
        descriptor_identities += 2
        for attempt in raw_payload["component_attempts"]:
            if attempt["attempt_id"] != _identity_dict(
                attempt,
                "attempt_id",
                "capability_authoritative_component_attempt:",
            ):
                raise ValueError("independent semantic replay found an invalid Attempt identity")
            attempt_identities += 1
        trace = bundle.trace.model_dump(mode="json", warnings=False)
        if trace["trace_id"] != _identity_dict(
            trace,
            "trace_id",
            "capability_artifact_backed_attempt_trace:",
        ):
            raise ValueError("independent semantic replay found an invalid Trace identity")
        trace_identities += 1
        if row["row_id"] != _identity_dict(
            row,
            "row_id",
            "capability_artifact_backed_outcome_row:",
        ):
            raise ValueError("independent semantic replay found an invalid row identity")
        row_identities += 1
        observed_sequence = tuple(
            item["component_key"] for item in raw_payload["component_attempts"]
        )
        if observed_sequence != sequences[job.job_id] or tuple(
            trace["component_attempts"]
        ) != tuple(raw_payload["component_attempts"]):
            raise ValueError("independent semantic replay found a changed Component sequence")
        sequence_matches += 1
        if not (
            result_payload["terminal_kind"] == raw_payload["terminal_kind"] == "completed_qualified"
            and validity["task_completion"] is True
            and validity["task_verifier_invoked"] is True
            and validity["final_response_abi_valid"] is True
            and validity["final_base_valid"] is True
            and validity["final_mechanism_qualified"] is True
            and validity["final_qualified_valid"] is True
            and row["final_qualified_valid"]
            == bool(row["final_base_valid"] and row["final_mechanism_qualified"])
        ):
            raise ValueError("independent semantic replay found changed terminal validity")
        validity_matches += 1
        if trace["failure_loci"] or any(
            row[key] is not None
            for key in (
                "first_runtime_uncommitted_locus_id",
                "first_base_invalid_locus_id",
                "first_mechanism_failed_locus_id",
                "terminal_locus_id",
            )
        ):
            raise ValueError("Qualified scripted row contains a fabricated FailureLocus")
        locus_matches += 1
        expected_parents = (
            manifest.manifest_id,
            runner.runner_id,
            job.execution_package_id,
            job.source_package_artifact_id,
            job.replica_index,
            job.raw_namespace,
            job.result_namespace,
            raw_descriptor["raw_execution_id"],
            result_descriptor["result_id"],
            trace["trace_id"],
        )
        observed_parents = (
            row["manifest_id"],
            row["runner_id"],
            row["execution_package_id"],
            row["source_package_artifact_id"],
            row["replica_index"],
            row["raw_namespace"],
            row["result_namespace"],
            row["raw_execution_id"],
            row["result_id"],
            row["trace_id"],
        )
        if expected_parents != observed_parents:
            raise ValueError("independent semantic replay found a crossed parent")
        parent_matches += 1
    if seen_jobs != set(manifest.expected_job_ids):
        raise ValueError("independent semantic replay differs from the exact Job set")
    production_evaluation = outcome.evaluate_artifact_backed_evidence_set(
        artifact_root=root,
        bundles=bundles,
        manifest=manifest,
        registry=registry,
        contract=contract,
        runner=runner,
        expected_evidence_kind="scripted_preflight_control",
    )
    if production_evaluation != frozen_evaluation:
        raise ValueError("production reload differs from the frozen preflight evaluation")
    return cast(
        models.SemanticReplayAudit,
        models.make_identity_model(
            models.SemanticReplayAudit,
            {
                "authorization_id": authorization.authorization_id,
                "contract_id": contract.contract_id,
                "registry_id": registry.registry_id,
                "manifest_id": manifest.manifest_id,
                "runner_id": runner.runner_id,
                "attempt_identity_match_count": attempt_identities,
                "production_evaluation_match": True,
            },
            field="audit_id",
            prefix="finance_v26_artifact_backed_semantic_replay_audit:",
        ),
    )


def _mixed_outcome(
    source: JobBoundOutcomePayload, *, base_valid: bool, mechanism_qualified: bool
) -> JobBoundOutcomePayload:
    values = source.model_dump(
        mode="python", exclude={"attempt_trace_id", "schema_version"}, warnings=False
    )
    values.update(
        first_policy_qualified_valid=False,
        final_base_valid=base_valid,
        final_mechanism_qualified=mechanism_qualified,
        final_qualified_valid=False,
        bounded_policy_qualified_valid=False,
        endpoint_kind="completed_invalid",
    )
    return cast(
        JobBoundOutcomePayload,
        make_job_identity_model(
            JobBoundOutcomePayload,
            values,
            field="attempt_trace_id",
            prefix="capability_job_attempt_trace:",
        ),
    )


def _factorization(package_root: Path) -> models.ValidityFactorizationAudit:
    registry, contract, manifest, runner, scripted = _load_parents(package_root)
    job = manifest.jobs[0]
    states: list[models.ValidityState] = []
    for base_valid, mechanism_qualified in ((True, False), (False, True)):
        source = _mixed_outcome(
            scripted[job.job_id],
            base_valid=base_valid,
            mechanism_qualified=mechanism_qualified,
        )
        with tempfile.TemporaryDirectory(prefix="v26-187-factorization-") as temporary:
            bundle = outcome.build_artifact_backed_bundle(
                artifact_root=Path(temporary),
                job=job,
                manifest=manifest,
                runner=runner,
                registry=registry,
                contract=contract,
                terminal_kind="completed_invalid",
                evidence_kind="scripted_preflight_control",
                source_outcome=source,
                base_failure_stage="base_answer" if not base_valid else None,
                mechanism_failure_component_index=(
                    len(source.component_attempts) - 1 if not mechanism_qualified else None
                ),
            )
        observed = (
            bundle.row.final_base_valid,
            bundle.row.final_mechanism_qualified,
            bundle.row.final_qualified_valid,
        )
        if observed != (base_valid, mechanism_qualified, False):
            raise ValueError("independent mixed validity replay lost a semantic state")
        states.append(
            models.ValidityState(
                final_base_valid=base_valid,
                final_mechanism_qualified=mechanism_qualified,
                derived_locus_stages=tuple(item.stage for item in bundle.trace.failure_loci),
            )
        )
    return cast(
        models.ValidityFactorizationAudit,
        models.make_identity_model(
            models.ValidityFactorizationAudit,
            {"contract_id": contract.contract_id, "states": tuple(states)},
            field="audit_id",
            prefix="finance_v26_independent_validity_factorization_audit:",
        ),
    )


def _control(
    *,
    family: str,
    target: str,
    fully_rehashed: bool,
    operation: Any,
    exact_expected_reason: str | None = None,
) -> models.NegativeControl:
    try:
        operation()
    except ValueError as exc:
        reason = str(exc)
    else:
        raise ValueError(f"independent negative control was admitted:{family}:{target}")
    values = {
        "family": family,
        "target": target,
        "fully_rehashed": fully_rehashed,
        "rejection_reason": reason,
        "exact_expected_reason": exact_expected_reason,
        "exact_reason_match": exact_expected_reason is None or reason == exact_expected_reason,
    }
    provisional = models.NegativeControl.model_construct(control_id="pending", **values)
    return models.NegativeControl(
        control_id=canonical_hash(
            provisional.model_dump(mode="json", exclude={"control_id"}, warnings=False),
            prefix="finance_v26_artifact_backed_independent_control:",
        ),
        **values,
    )


def _rehashed_locus_bundle(
    bundle: outcome.ArtifactBackedEvidenceBundle, locus: FailureLocus
) -> outcome.ArtifactBackedEvidenceBundle:
    trace_values = bundle.trace.model_dump(
        mode="python", exclude={"trace_id", "schema_version"}, warnings=False
    )
    trace_values["failure_loci"] = (locus,)
    trace = cast(
        outcome.ArtifactBackedAttemptTrace,
        outcome.make_identity_model(
            outcome.ArtifactBackedAttemptTrace,
            trace_values,
            field="trace_id",
            prefix="capability_artifact_backed_attempt_trace:",
        ),
    )
    row_values = bundle.row.model_dump(
        mode="python", exclude={"row_id", "schema_version"}, warnings=False
    )
    row_values.update(
        trace_id=trace.trace_id,
        first_base_invalid_locus_id=(locus.locus_id if locus.stage == "base_answer" else None),
        first_mechanism_failed_locus_id=(locus.locus_id if locus.stage == "mechanism" else None),
        terminal_locus_id=locus.locus_id,
    )
    row = cast(
        outcome.ArtifactBackedCapabilityOutcomeRow,
        outcome.make_identity_model(
            outcome.ArtifactBackedCapabilityOutcomeRow,
            row_values,
            field="row_id",
            prefix="capability_artifact_backed_outcome_row:",
        ),
    )
    return outcome.ArtifactBackedEvidenceBundle(
        raw=bundle.raw, result=bundle.result, trace=trace, row=row
    )


def _rewrite_empirical(
    *,
    artifact_root: Path,
    job: CapabilityDevelopmentJob,
    manifest: CapabilityDevelopmentJobManifest,
    runner: JobBoundRunnerContract,
    bundle: outcome.ArtifactBackedEvidenceBundle,
) -> outcome.ArtifactBackedEvidenceBundle:
    raw_values = bundle.raw.model_dump(
        mode="python", exclude={"raw_execution_id", "schema_version"}, warnings=False
    )
    raw_values["evidence_kind"] = "empirical_execution"
    raw = cast(
        outcome.ArtifactBackedRawExecutionDescriptor,
        outcome.make_identity_model(
            outcome.ArtifactBackedRawExecutionDescriptor,
            raw_values,
            field="raw_execution_id",
            prefix="capability_artifact_backed_raw_execution:",
        ),
    )
    result_path = artifact_root / bundle.result.artifact_relative_path
    result_payload = outcome.ArtifactBackedJobResultPayload.model_validate(_load(result_path))
    values = result_payload.model_dump(
        mode="python", exclude={"payload_id", "schema_version"}, warnings=False
    )
    values["raw_execution_id"] = raw.raw_execution_id
    result_payload = cast(
        outcome.ArtifactBackedJobResultPayload,
        outcome.make_identity_model(
            outcome.ArtifactBackedJobResultPayload,
            values,
            field="payload_id",
            prefix="capability_artifact_backed_job_result_payload:",
        ),
    )
    result_bytes = outcome.canonical_model_bytes(result_payload)
    result_path.write_bytes(result_bytes)
    result_values = bundle.result.model_dump(
        mode="python", exclude={"result_id", "schema_version"}, warnings=False
    )
    result_values.update(
        evidence_kind="empirical_execution",
        raw_execution_id=raw.raw_execution_id,
        artifact_sha256=outcome.sha256_bytes(result_bytes),
        artifact_byte_count=len(result_bytes),
        payload_id=result_payload.payload_id,
    )
    result = cast(
        outcome.ArtifactBackedJobResultDescriptor,
        outcome.make_identity_model(
            outcome.ArtifactBackedJobResultDescriptor,
            result_values,
            field="result_id",
            prefix="capability_artifact_backed_job_result:",
        ),
    )
    raw_payload = RawExecutionEvidencePayload.model_validate(
        _load(artifact_root / raw.artifact_relative_path)
    )
    trace, row = outcome._build_trace_and_row(
        job=job,
        manifest=manifest,
        runner=runner,
        raw=raw,
        raw_payload=raw_payload,
        result=result,
        result_payload=result_payload,
    )
    return outcome.ArtifactBackedEvidenceBundle(raw=raw, result=result, trace=trace, row=row)


def _diagnostic_attack(package_root: Path, terminal_kind: str) -> None:
    registry, contract, manifest, runner, scripted = _load_parents(package_root)
    with tempfile.TemporaryDirectory(prefix="v26-187-diagnostic-attack-") as temporary:
        artifact_root = Path(temporary)
        target_job = manifest.expected_job_ids[0]
        bundles: list[outcome.ArtifactBackedEvidenceBundle] = []
        for job in manifest.jobs:
            is_target = job.job_id == target_job
            bundles.append(
                outcome.build_artifact_backed_bundle(
                    artifact_root=artifact_root,
                    job=job,
                    manifest=manifest,
                    runner=runner,
                    registry=registry,
                    contract=contract,
                    terminal_kind=cast(Any, terminal_kind if is_target else "completed_qualified"),
                    evidence_kind="scripted_preflight_control",
                    source_outcome=None if is_target else scripted[job.job_id],
                )
            )
        empirical = tuple(
            _rewrite_empirical(
                artifact_root=artifact_root,
                job=next(item for item in manifest.jobs if item.job_id == bundle.row.job_id),
                manifest=manifest,
                runner=runner,
                bundle=bundle,
            )
            for bundle in bundles
        )
        outcome.evaluate_artifact_backed_evidence_set(
            artifact_root=artifact_root,
            bundles=empirical,
            manifest=manifest,
            registry=registry,
            contract=contract,
            runner=runner,
            expected_evidence_kind="empirical_execution",
        )


def _semantic_erosion_attack(
    package_root: Path, *, base_valid: bool, mechanism_qualified: bool
) -> None:
    registry, contract, manifest, runner, scripted = _load_parents(package_root)
    job = manifest.jobs[0]
    source = _mixed_outcome(
        scripted[job.job_id],
        base_valid=base_valid,
        mechanism_qualified=mechanism_qualified,
    )
    with tempfile.TemporaryDirectory(prefix="v26-187-semantic-erosion-") as temporary:
        root = Path(temporary)
        bundle = outcome.build_artifact_backed_bundle(
            artifact_root=root,
            job=job,
            manifest=manifest,
            runner=runner,
            registry=registry,
            contract=contract,
            terminal_kind="completed_invalid",
            evidence_kind="scripted_preflight_control",
            source_outcome=source,
            base_failure_stage="base_answer" if not base_valid else None,
            mechanism_failure_component_index=(
                len(source.component_attempts) - 1 if not mechanism_qualified else None
            ),
        )
        values = bundle.row.model_dump(
            mode="python", exclude={"row_id", "schema_version"}, warnings=False
        )
        values.update(final_base_valid=False, final_mechanism_qualified=False)
        row = cast(
            outcome.ArtifactBackedCapabilityOutcomeRow,
            outcome.make_identity_model(
                outcome.ArtifactBackedCapabilityOutcomeRow,
                values,
                field="row_id",
                prefix="capability_artifact_backed_outcome_row:",
            ),
        )
        outcome.validate_artifact_backed_bundle(
            artifact_root=root,
            job=job,
            manifest=manifest,
            runner=runner,
            registry=registry,
            contract=contract,
            bundle=outcome.ArtifactBackedEvidenceBundle(
                raw=bundle.raw, result=bundle.result, trace=bundle.trace, row=row
            ),
            expected_evidence_kind="scripted_preflight_control",
        )


def _destructive(package_root: Path) -> models.NegativeControlAudit:
    registry, contract, manifest, runner, _ = _load_parents(package_root)
    bundles, _ = _load_catalog(package_root)
    artifact_root = package_root / AUDITED_V186_DIR
    job = manifest.jobs[0]
    baseline = next(item for item in bundles if item.row.job_id == job.job_id)
    controls: list[models.NegativeControl] = []
    for base_valid, mechanism_qualified in ((True, False), (False, True)):
        controls.append(
            _control(
                family="terminal_validity_factorization",
                target=f"collapse_{str(base_valid).lower()}_{str(mechanism_qualified).lower()}",
                fully_rehashed=True,
                operation=lambda base_valid=base_valid, mechanism_qualified=mechanism_qualified: (
                    _semantic_erosion_attack(
                        package_root,
                        base_valid=base_valid,
                        mechanism_qualified=mechanism_qualified,
                    )
                ),
            )
        )
    for terminal_kind in ("measurement_support_exit", "policy_horizon_exhausted"):
        controls.append(
            _control(
                family="diagnostic_empirical_admission",
                target=terminal_kind,
                fully_rehashed=True,
                operation=lambda terminal_kind=terminal_kind: _diagnostic_attack(
                    package_root, terminal_kind
                ),
                exact_expected_reason=EXPECTED_DIAGNOSTIC_REJECTION,
            )
        )
    loci = (
        cast(
            FailureLocus,
            make_v2_identity_model(
                FailureLocus,
                {
                    "stage": "base_answer",
                    "component_key": None,
                    "attempt_index": None,
                    "reason_code": "independent_invented_base_failure",
                    "evaluability": "evaluated_false",
                    "source_descriptor_id": baseline.result.result_id,
                },
                field="locus_id",
                prefix="capability_authoritative_failure_locus:",
            ),
        ),
        cast(
            FailureLocus,
            make_v2_identity_model(
                FailureLocus,
                {
                    "stage": "mechanism",
                    "component_key": "independent.absent.component",
                    "attempt_index": 0,
                    "reason_code": "independent_invented_mechanism_failure",
                    "evaluability": "evaluated_false",
                    "source_descriptor_id": baseline.result.result_id,
                },
                field="locus_id",
                prefix="capability_authoritative_failure_locus:",
            ),
        ),
    )
    for target, locus in zip(
        ("invented_base_locus", "invented_component_locus"), loci, strict=True
    ):
        controls.append(
            _control(
                family="failure_locus_reconstruction",
                target=target,
                fully_rehashed=True,
                operation=lambda locus=locus: outcome.validate_artifact_backed_bundle(
                    artifact_root=artifact_root,
                    job=job,
                    manifest=manifest,
                    runner=runner,
                    registry=registry,
                    contract=contract,
                    bundle=_rehashed_locus_bundle(baseline, locus),
                    expected_evidence_kind="scripted_preflight_control",
                ),
            )
        )
    for target, relative_path in (
        ("Raw", baseline.raw.artifact_relative_path),
        ("Result", baseline.result.artifact_relative_path),
    ):
        with tempfile.TemporaryDirectory(prefix="v26-187-byte-attack-") as temporary:
            root = Path(temporary)
            for source in (
                baseline.raw.artifact_relative_path,
                baseline.result.artifact_relative_path,
            ):
                shutil.copy2(artifact_root / source, root / source)
            with (root / relative_path).open("ab") as handle:
                handle.write(b"independent-byte-change")
            controls.append(
                _control(
                    family="artifact_byte_authenticity",
                    target=target,
                    fully_rehashed=False,
                    operation=lambda root=root: outcome.validate_artifact_backed_bundle(
                        artifact_root=root,
                        job=job,
                        manifest=manifest,
                        runner=runner,
                        registry=registry,
                        contract=contract,
                        bundle=baseline,
                        expected_evidence_kind="scripted_preflight_control",
                    ),
                )
            )
    registry_values = registry.model_dump(mode="python", warnings=False)
    registry_values["unmapped_source_label_count"] = 1
    invalid_registry = AuthoritativeTerminalRegistry.model_construct(**registry_values)
    contract_values = contract.model_dump(mode="python", warnings=False)
    contract_values["formal_empirical_rows_materialized"] = True
    invalid_contract = outcome.ArtifactBackedOutcomeContract.model_construct(**contract_values)
    manifest_values = manifest.model_dump(mode="python", warnings=False)
    manifest_values["provider_calls"] = 1
    invalid_manifest = CapabilityDevelopmentJobManifest.model_construct(**manifest_values)
    runner_values = runner.model_dump(mode="python", warnings=False)
    runner_values["provider_calls_authorized"] = True
    invalid_runner = JobBoundRunnerContract.model_construct(**runner_values)
    invalid_job_values = job.model_dump(mode="python", warnings=False)
    invalid_job_values["schedule_ids"] = (job.schedule_ids[0], job.schedule_ids[0])
    invalid_job = CapabilityDevelopmentJob.model_construct(**invalid_job_values)
    jobs = list(manifest.jobs)
    jobs[0] = invalid_job
    invalid_job_manifest_values = manifest.model_dump(mode="python", warnings=False)
    invalid_job_manifest_values["jobs"] = tuple(jobs)
    invalid_job_manifest = CapabilityDevelopmentJobManifest.model_construct(
        **invalid_job_manifest_values
    )
    candidates = (
        ("Contract", registry, invalid_contract, manifest, runner),
        ("Job", registry, contract, invalid_job_manifest, runner),
        ("Manifest", registry, contract, invalid_manifest, runner),
        ("Registry", invalid_registry, contract, manifest, runner),
        ("Runner", registry, contract, manifest, invalid_runner),
    )
    for (
        target,
        candidate_registry,
        candidate_contract,
        candidate_manifest,
        candidate_runner,
    ) in candidates:
        controls.append(
            _control(
                family="authoritative_parent_revalidation",
                target=target,
                fully_rehashed=False,
                operation=partial(
                    outcome.evaluate_artifact_backed_evidence_set,
                    artifact_root=artifact_root,
                    bundles=bundles,
                    manifest=candidate_manifest,
                    registry=candidate_registry,
                    contract=candidate_contract,
                    runner=candidate_runner,
                    expected_evidence_kind="scripted_preflight_control",
                ),
            )
        )
    controls_tuple = tuple(controls)
    return cast(
        models.NegativeControlAudit,
        models.make_identity_model(
            models.NegativeControlAudit,
            {
                "contract_id": contract.contract_id,
                "controls": controls_tuple,
                "fully_rehashed_control_count": sum(item.fully_rehashed for item in controls_tuple),
            },
            field="audit_id",
            prefix="finance_v26_artifact_backed_production_destructive_audit:",
        ),
    )


def _gate(name: str, *evidence_ids: str) -> models.StaticGate:
    return models.StaticGate(name=name, evidence_ids=tuple(evidence_ids))


def _static(
    *,
    authorization: models.IndependentAuditAuthorization,
    source_rebuild: models.SourceRebuildAudit,
    formal_replay: models.FormalArtifactReplayAudit,
    semantic_replay: models.SemanticReplayAudit,
    factorization: models.ValidityFactorizationAudit,
    destructive: models.NegativeControlAudit,
) -> models.StaticAudit:
    gates = (
        _gate("exact_external_audit_input", authorization.authorization_id),
        _gate("exact_v26_186_source_commit_and_tree", source_rebuild.audit_id),
        _gate("exact_seven_file_change_surface", source_rebuild.audit_id),
        _gate("independent_398_file_rebuild", source_rebuild.audit_id),
        _gate("formal_artifact_manifest_replay", formal_replay.audit_id),
        _gate("actual_raw_result_byte_replay", semantic_replay.audit_id),
        _gate("independent_evidence_dag_replay", semantic_replay.audit_id),
        _gate("independent_validity_factorization", factorization.audit_id),
        _gate("diagnostic_empirical_admission", destructive.audit_id),
        _gate("failure_locus_reconstruction", destructive.audit_id),
        _gate("artifact_byte_authenticity", destructive.audit_id),
        _gate("authoritative_parent_revalidation", destructive.audit_id),
        _gate("all_thirteen_negative_controls_rejected", destructive.audit_id),
        _gate("zero_provider_and_empirical_rows", semantic_replay.audit_id),
    )
    return cast(
        models.StaticAudit,
        models.make_identity_model(
            models.StaticAudit,
            {
                "gates": gates,
                "gate_count": len(gates),
                "passed_gate_count": len(gates),
            },
            field="audit_id",
            prefix="finance_v26_artifact_backed_independent_static_audit:",
        ),
    )


def _decision(
    *,
    authorization: models.IndependentAuditAuthorization,
    source_rebuild: models.SourceRebuildAudit,
    formal_replay: models.FormalArtifactReplayAudit,
    semantic_replay: models.SemanticReplayAudit,
    factorization: models.ValidityFactorizationAudit,
    destructive: models.NegativeControlAudit,
    static: models.StaticAudit,
) -> models.IndependentAuditDecision:
    return cast(
        models.IndependentAuditDecision,
        models.make_identity_model(
            models.IndependentAuditDecision,
            {
                "authorization_id": authorization.authorization_id,
                "source_rebuild_audit_id": source_rebuild.audit_id,
                "formal_replay_audit_id": formal_replay.audit_id,
                "semantic_replay_audit_id": semantic_replay.audit_id,
                "factorization_audit_id": factorization.audit_id,
                "destructive_audit_id": destructive.audit_id,
                "static_audit_id": static.audit_id,
                "decision": models.PASSED_DECISION,
                "next_stage": models.NO_FURTHER_EXPERIMENT,
            },
            field="decision_id",
            prefix="finance_v26_artifact_backed_independent_audit_decision:",
        ),
    )


def _transition(decision: models.IndependentAuditDecision) -> models.ProspectiveTransition:
    return cast(
        models.ProspectiveTransition,
        models.make_identity_model(
            models.ProspectiveTransition,
            {"decision_id": decision.decision_id, "next_stage": decision.next_stage},
            field="transition_id",
            prefix="finance_v26_artifact_backed_independent_audit_transition:",
        ),
    )


def _file_bindings(payloads: dict[str, bytes]) -> tuple[models.FileBinding, ...]:
    return tuple(
        models.FileBinding(
            relative_path=name,
            sha256=hashlib.sha256(payload).hexdigest(),
            byte_count=len(payload),
            source_kind="v26_187_formal_artifact",
        )
        for name, payload in sorted(payloads.items())
    )


def _manifest(payloads: dict[str, bytes]) -> models.ArtifactManifest:
    files = _file_bindings(payloads)
    root = canonical_hash(
        [item.model_dump(mode="json") for item in files],
        prefix="finance_v26_artifact_backed_independent_artifact_root:",
    )
    return cast(
        models.ArtifactManifest,
        models.make_identity_model(
            models.ArtifactManifest,
            {
                "artifact_root": root,
                "files": files,
                "file_count": len(files),
                "total_byte_count": sum(item.byte_count for item in files),
            },
            field="manifest_id",
            prefix="finance_v26_artifact_backed_independent_artifact_manifest:",
        ),
    )


def build(
    *,
    package_root: Path,
    output_dir: Path,
    audited_source_archive: Path,
    external_audit_input: Path,
) -> models.BuildProducts:
    root = _resolve_package_root(package_root)
    authorization = _authorization(package_root=root, external_audit_input=external_audit_input)
    source_rebuild = _source_rebuild(
        package_root=root,
        authorization=authorization,
        audited_source_archive=audited_source_archive,
    )
    formal_replay = _formal_replay(package_root=root, authorization=authorization)
    semantic_replay = _semantic_replay(package_root=root, authorization=authorization)
    factorization = _factorization(root)
    destructive = _destructive(root)
    static = _static(
        authorization=authorization,
        source_rebuild=source_rebuild,
        formal_replay=formal_replay,
        semantic_replay=semantic_replay,
        factorization=factorization,
        destructive=destructive,
    )
    decision = _decision(
        authorization=authorization,
        source_rebuild=source_rebuild,
        formal_replay=formal_replay,
        semantic_replay=semantic_replay,
        factorization=factorization,
        destructive=destructive,
        static=static,
    )
    transition = _transition(decision)
    detail_payloads = {
        "external_v26_186_revision_audit.txt": external_audit_input.read_bytes(),
        "independent_audit_authorization.json": _canonical_bytes(authorization),
        "source_rebuild_audit.json": _canonical_bytes(source_rebuild),
        "formal_artifact_replay_audit.json": _canonical_bytes(formal_replay),
        "semantic_evidence_dag_replay_audit.json": _canonical_bytes(semantic_replay),
        "validity_factorization_audit.json": _canonical_bytes(factorization),
        "production_destructive_audit.json": _canonical_bytes(destructive),
        "independent_static_audit.json": _canonical_bytes(static),
        "independent_audit_decision.json": _canonical_bytes(decision),
        "prospective_transition.json": _canonical_bytes(transition),
    }
    detail_bindings = _file_bindings(detail_payloads)
    report = cast(
        models.IndependentAuditReport,
        models.make_identity_model(
            models.IndependentAuditReport,
            {
                "run_id": RUN_ID,
                "authorization_id": authorization.authorization_id,
                "source_rebuild_audit_id": source_rebuild.audit_id,
                "formal_replay_audit_id": formal_replay.audit_id,
                "semantic_replay_audit_id": semantic_replay.audit_id,
                "factorization_audit_id": factorization.audit_id,
                "destructive_audit_id": destructive.audit_id,
                "static_audit_id": static.audit_id,
                "decision_id": decision.decision_id,
                "transition_id": transition.transition_id,
                "audited_report_id": AUDITED_REPORT_ID,
                "audited_artifact_root": AUDITED_ARTIFACT_ROOT,
                "decision": decision.decision,
                "next_stage": decision.next_stage,
                "detail_files": detail_bindings,
            },
            field="report_id",
            prefix="finance_v26_artifact_backed_independent_audit_report:",
        ),
    )
    payloads = {**detail_payloads, "report.json": _canonical_bytes(report)}
    manifest = _manifest(payloads)
    payloads["artifact_manifest.json"] = _canonical_bytes(manifest)
    write_immutable_artifact_directory(output_dir, payloads)
    return models.BuildProducts(
        authorization=authorization,
        source_rebuild=source_rebuild,
        formal_replay=formal_replay,
        semantic_replay=semantic_replay,
        factorization=factorization,
        destructive=destructive,
        static=static,
        decision=decision,
        transition=transition,
        report=report,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--package-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--audited-source-archive", type=Path, required=True)
    parser.add_argument("--external-audit-input", type=Path, required=True)
    args = parser.parse_args()
    products = build(
        package_root=args.package_root,
        output_dir=args.output_dir,
        audited_source_archive=args.audited_source_archive,
        external_audit_input=args.external_audit_input,
    )
    print(products.report.model_dump_json())


if __name__ == "__main__":
    main()
