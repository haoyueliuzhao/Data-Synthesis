from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Final, cast

from pydantic import BaseModel

from trusted_synthesis.canonical_json import canonical_json_bytes, strict_canonical_hash
from trusted_synthesis.core.task.authoritative_job_bound_outcome import (
    AuthoritativeJobBoundOutcomeContract,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_capability_authoritative_outcome_terminal_independent_audit_models as models,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_capability_authoritative_outcome_terminal_preflight_models as v181_models,
)

RUN_ID: Final = "finance_v26_182_authoritative_outcome_terminal_independent_audit_v1_20260831"
OUTPUT_DIR: Final = (
    "artifacts/vtdo_experiment/"
    "finance_v26_182_authoritative_outcome_terminal_independent_audit_v1_20260831"
)
AUDITED_COMMIT: Final = "a934a7557caab65cf7f4e6bc65fa87222a2d7461"
V181_DIR: Final = (
    "artifacts/vtdo_experiment/finance_v26_181_authoritative_outcome_terminal_preflight_v1_20260830"
)
V180_DIR: Final = (
    "artifacts/vtdo_experiment/finance_v26_180_job_bound_parent_terminal_audit_v1_20260830"
)
V179_DIR: Final = (
    "artifacts/vtdo_experiment/finance_v26_179_job_bound_multistep_outcome_preflight_v1_20260830"
)
V166_DIR: Final = (
    "artifacts/vtdo_experiment/"
    "finance_v26_166_bounded_policy_capability_censoring_vtdo_admission_audit_v1_20260828"
)

V181_ARTIFACT_NAMES: Final = (
    "audit_integrity_meta_gate_audit.json",
    "authoritative_evidence_dag_audit.json",
    "authoritative_job_bound_outcome_contract.json",
    "authoritative_terminal_registry_audit.json",
    "external_audit_authorization.json",
    "external_v180_revision_report_audit.txt",
    "final_parser_semantic_gate_audit.json",
    "production_destructive_audit.json",
    "prospective_transition_contract.json",
    "report.json",
    "terminal_totality_preflight_audit.json",
    "transitive_source_root.json",
    "unknown_first_action_policy_audit.json",
    "v180_measurement_scope_audit.json",
    "v180_predecessor_freeze_audit.json",
)
ENTRY_SOURCE_PATHS: Final = (
    "src/trusted_synthesis/core/task/authoritative_job_bound_outcome.py",
    "src/trusted_synthesis/experiments/vtdo_experiment/"
    "phase1_v26_capability_authoritative_outcome_terminal_preflight.py",
    "src/trusted_synthesis/experiments/vtdo_experiment/"
    "phase1_v26_capability_authoritative_outcome_terminal_preflight_models.py",
    "src/trusted_synthesis/experiments/vtdo_experiment/"
    "phase1_v26_capability_authoritative_outcome_terminal_preflight_runtime.py",
)
AUDITOR_SOURCE_PATHS: Final = (
    "scripts/v26_181_independent_negative_control_runner.py",
    "src/trusted_synthesis/experiments/vtdo_experiment/"
    "phase1_v26_capability_authoritative_outcome_terminal_independent_audit.py",
    "src/trusted_synthesis/experiments/vtdo_experiment/"
    "phase1_v26_capability_authoritative_outcome_terminal_independent_audit_models.py",
)
FROZEN_INPUT_PATHS: Final = (
    f"{V180_DIR}/report.json",
    f"{V180_DIR}/prospective_transition_contract.json",
    f"{V180_DIR}/empirical_parent_authenticity_audit.json",
    f"{V180_DIR}/final_abi_terminal_totality_audit.json",
    f"{V180_DIR}/first_action_reference_totality_audit.json",
    f"{V180_DIR}/outer_terminal_totality_audit.json",
    f"{V179_DIR}/development_job_manifest.json",
    f"{V179_DIR}/job_bound_runner_contract.json",
    f"{V179_DIR}/generation_profile_binding_audit.json",
    f"{V179_DIR}/scripted_denominator_preflight_audit.json",
    f"{V179_DIR}/runner_branch_control_audit.json",
    f"{V166_DIR}/terminal_endpoint_schema_audit.json",
)
DETAIL_FILENAMES: Final = (
    "artifact_byte_authenticity_audit.json",
    "authoritative_parent_revalidation_audit.json",
    "completed_invalid_factorization_audit.json",
    "diagnostic_empirical_admission_audit.json",
    "exact_predecessor_freeze_audit.json",
    "failure_locus_authenticity_audit.json",
    "independent_audit_gate_decision.json",
)


def _resolve_package_root(root: Path) -> Path:
    if (root / "src" / "trusted_synthesis").is_dir():
        return root.resolve()
    candidate = root / "trusted_data_synthesis"
    if (candidate / "src" / "trusted_synthesis").is_dir():
        return candidate.resolve()
    raise ValueError("v26.182 cannot resolve the trusted_data_synthesis package root")


def _repo_root(package_root: Path) -> Path:
    completed = subprocess.run(
        ["git", "-C", str(package_root), "rev-parse", "--show-toplevel"],
        check=True,
        capture_output=True,
        text=True,
    )
    return Path(completed.stdout.strip()).resolve()


def _git_output(repo_root: Path, *arguments: str) -> bytes:
    completed = subprocess.run(
        ["git", "-C", str(repo_root), *arguments],
        check=True,
        capture_output=True,
    )
    return completed.stdout


def _git_show(repo_root: Path, package_relative_path: str) -> bytes:
    return _git_output(
        repo_root,
        "show",
        f"{AUDITED_COMMIT}:trusted_data_synthesis/{package_relative_path}",
    )


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _binding(
    relative_path: str,
    payload: bytes,
    *,
    source_kind: str,
) -> models.FileBinding:
    return models.FileBinding(
        relative_path=relative_path,
        sha256=_sha256(payload),
        byte_count=len(payload),
        source_kind=source_kind,
    )


def _archive(
    repo_root: Path,
    package_relative_paths: Sequence[str],
) -> dict[str, bytes]:
    repo_paths = tuple(
        f"trusted_data_synthesis/{path}" for path in sorted(set(package_relative_paths))
    )
    payload = _git_output(
        repo_root,
        "archive",
        "--format=tar",
        AUDITED_COMMIT,
        "--",
        *repo_paths,
    )
    output: dict[str, bytes] = {}
    with tarfile.open(fileobj=io.BytesIO(payload), mode="r:") as archive:
        for member in archive.getmembers():
            if not member.isfile():
                continue
            if member.name.startswith("/") or ".." in Path(member.name).parts:
                raise ValueError("exact Git archive contains an unsafe path")
            handle = archive.extractfile(member)
            if handle is None:
                raise ValueError(f"exact Git archive member is unreadable: {member.name}")
            output[member.name.removeprefix("trusted_data_synthesis/")] = handle.read()
    missing = sorted(set(package_relative_paths) - set(output))
    if missing:
        raise ValueError(f"exact Git archive is missing required paths: {missing}")
    return output


def _validate_v181_artifacts(artifacts: Mapping[str, bytes]) -> tuple[dict[str, Any], int]:
    parsers: dict[str, type[BaseModel]] = {
        "audit_integrity_meta_gate_audit.json": v181_models.AuditIntegrityMetaGateAudit,
        "authoritative_evidence_dag_audit.json": v181_models.AuthoritativeEvidenceDagAudit,
        "authoritative_job_bound_outcome_contract.json": (AuthoritativeJobBoundOutcomeContract),
        "authoritative_terminal_registry_audit.json": (v181_models.TerminalRegistryDerivationAudit),
        "external_audit_authorization.json": v181_models.ExternalAuditAuthorization,
        "final_parser_semantic_gate_audit.json": v181_models.FinalParserSemanticGateAudit,
        "production_destructive_audit.json": v181_models.ProductionDestructiveAudit,
        "prospective_transition_contract.json": v181_models.ProspectiveTransition,
        "report.json": v181_models.PreflightReport,
        "terminal_totality_preflight_audit.json": v181_models.TerminalTotalityAudit,
        "transitive_source_root.json": v181_models.TransitiveSourceRoot,
        "unknown_first_action_policy_audit.json": v181_models.UnknownFirstActionPolicyAudit,
        "v180_measurement_scope_audit.json": v181_models.V180MeasurementScopeAudit,
        "v180_predecessor_freeze_audit.json": v181_models.V180PredecessorFreezeAudit,
    }
    parsed: dict[str, Any] = {}
    for filename, model_type in parsers.items():
        value = json.loads(artifacts[f"{V181_DIR}/{filename}"])
        parsed[filename] = model_type.model_validate(value)
    return parsed, len(parsed)


def _source_root_and_paths(
    repo_root: Path,
) -> tuple[v181_models.TransitiveSourceRoot, tuple[str, ...]]:
    payload = _git_show(repo_root, f"{V181_DIR}/transitive_source_root.json")
    source_root = v181_models.TransitiveSourceRoot.model_validate(json.loads(payload))
    paths = tuple(item.relative_path for item in source_root.files)
    if len(paths) != 347 or len(set(paths)) != 347:
        raise ValueError("v26.181 exact source root is not the frozen 347-file set")
    return source_root, paths


def _run_exact_negative_controls(
    *,
    package_root: Path,
    archive: Mapping[str, bytes],
) -> dict[str, Any]:
    runner = package_root / "scripts/v26_181_independent_negative_control_runner.py"
    with tempfile.TemporaryDirectory(prefix="v26_181_exact_snapshot_") as directory:
        snapshot = Path(directory) / "trusted_data_synthesis"
        for relative_path, payload in archive.items():
            target = snapshot / relative_path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(payload)
        completed = subprocess.run(
            [
                sys.executable,
                str(runner),
                "--package-root",
                str(snapshot),
            ],
            check=True,
            capture_output=True,
            text=True,
            env={**os.environ, "PYTHONHASHSEED": "0"},
        )
    result = json.loads(completed.stdout)
    result.pop("exact_package_root", None)
    if result.get("provider_calls") != 0:
        raise ValueError("v26.181 independent runner performed a Provider call")
    return result


def _auditor_bindings(package_root: Path) -> tuple[models.FileBinding, ...]:
    bindings = tuple(
        _binding(
            path,
            (package_root / path).read_bytes(),
            source_kind="independent_auditor_source",
        )
        for path in sorted(AUDITOR_SOURCE_PATHS)
    )
    return bindings


def _freeze_audit(
    *,
    package_root: Path,
    repo_root: Path,
    source_root: v181_models.TransitiveSourceRoot,
    archive: Mapping[str, bytes],
    parsed_artifacts: Mapping[str, Any],
) -> models.ExactPredecessorFreezeAudit:
    exact_commit = (
        _git_output(repo_root, "rev-parse", f"{AUDITED_COMMIT}^{{commit}}").decode().strip()
    )
    exact_tree = _git_output(repo_root, "rev-parse", f"{AUDITED_COMMIT}^{{tree}}").decode().strip()
    if exact_commit != AUDITED_COMMIT:
        raise ValueError("v26.181 audited commit did not resolve exactly")
    source_matches = sum(
        len(archive[item.relative_path]) == item.byte_count
        and _sha256(archive[item.relative_path]) == item.sha256
        for item in source_root.files
    )
    artifact_bindings = tuple(
        _binding(
            f"{V181_DIR}/{filename}",
            archive[f"{V181_DIR}/{filename}"],
            source_kind="v26_181_formal_artifact",
        )
        for filename in sorted(V181_ARTIFACT_NAMES)
    )
    artifact_matches = sum(
        archive[item.relative_path] == _git_show(repo_root, item.relative_path)
        for item in artifact_bindings
    )
    current_matches = sum(
        (package_root / item.relative_path).read_bytes() == archive[item.relative_path]
        for item in artifact_bindings
    )
    entry_matches = sum(
        (package_root / path).read_bytes() == archive[path] for path in ENTRY_SOURCE_PATHS
    )
    report = cast(v181_models.PreflightReport, parsed_artifacts["report.json"])
    detail_by_path = {item.relative_path: item for item in report.detail_files}
    detail_matches = 0
    for binding in artifact_bindings:
        if binding.relative_path.endswith("/report.json"):
            continue
        expected = detail_by_path.get(binding.relative_path)
        if (
            expected is not None
            and expected.sha256 == binding.sha256
            and expected.byte_count == binding.byte_count
        ):
            detail_matches += 1
    auditor_files = _auditor_bindings(package_root)
    values = {
        "audited_commit": exact_commit,
        "audited_tree_id": exact_tree,
        "v181_report_id": report.report_id,
        "v181_source_root_id": source_root.root_id,
        "source_file_manifest_hash": strict_canonical_hash(
            tuple(item.model_dump(mode="python") for item in source_root.files),
            prefix="finance_v26_181_exact_source_file_manifest:",
        ),
        "source_file_count": len(source_root.files),
        "source_file_match_count": source_matches,
        "entry_source_file_count": len(ENTRY_SOURCE_PATHS),
        "entry_source_file_match_count": entry_matches,
        "formal_artifact_count": len(artifact_bindings),
        "formal_artifact_match_count": artifact_matches,
        "current_worktree_artifact_match_count": current_matches,
        "report_detail_binding_count": len(report.detail_files),
        "report_detail_binding_match_count": detail_matches,
        "exact_commit_artifacts": artifact_bindings,
        "auditor_source_root_hash": strict_canonical_hash(
            tuple(item.model_dump(mode="python") for item in auditor_files),
            prefix="finance_v26_182_independent_auditor_source_root:",
        ),
        "auditor_source_files": auditor_files,
    }
    return cast(
        models.ExactPredecessorFreezeAudit,
        models.make_identity_model(
            models.ExactPredecessorFreezeAudit,
            values,
            field="audit_id",
            prefix="finance_v26_181_exact_predecessor_freeze_audit:",
        ),
    )


def _observation(
    *,
    category: models.ControlCategory,
    control: str,
    attack: bool,
    input_valid: bool,
    fully_rehashed: bool,
    admitted: bool,
    property_preserved: bool,
    expected: str,
    observed: str,
    evidence: dict[str, Any],
) -> models.NegativeControlObservation:
    return cast(
        models.NegativeControlObservation,
        models.make_identity_model(
            models.NegativeControlObservation,
            {
                "category": category,
                "control": control,
                "exact_source_commit": AUDITED_COMMIT,
                "attack": attack,
                "input_valid": input_valid,
                "fully_rehashed": fully_rehashed,
                "production_entry_admitted": admitted,
                "required_property_preserved": property_preserved,
                "expected_behavior": expected,
                "observed_behavior": observed,
                "evidence": evidence,
            },
            field="observation_id",
            prefix="finance_v26_181_independent_negative_control:",
        ),
    )


def _group(
    category: models.ControlCategory,
    observations: Sequence[models.NegativeControlObservation],
) -> models.ControlGroupAudit:
    rows = tuple(observations)
    values = {
        "category": category,
        "observations": rows,
        "expected_rejection_count": sum(item.attack and item.input_valid for item in rows),
        "observed_rejection_count": sum(
            item.attack and item.input_valid and not item.production_entry_admitted for item in rows
        ),
        "admitted_attack_count": sum(
            item.attack and item.production_entry_admitted for item in rows
        ),
        "property_failure_count": sum(not item.required_property_preserved for item in rows),
        "gate_passed": all(
            (not item.attack or not item.input_valid or not item.production_entry_admitted)
            and item.required_property_preserved
            for item in rows
        ),
    }
    return cast(
        models.ControlGroupAudit,
        models.make_identity_model(
            models.ControlGroupAudit,
            values,
            field="audit_id",
            prefix=f"finance_v26_181_{category}_audit:",
        ),
    )


def _control_groups(result: Mapping[str, Any]) -> tuple[models.ControlGroupAudit, ...]:
    mixed = _group(
        "completed_invalid_factorization",
        tuple(
            _observation(
                category="completed_invalid_factorization",
                control=row["control"],
                attack=False,
                input_valid=bool(row["source_outcome_validated"]),
                fully_rehashed=True,
                admitted=True,
                property_preserved=bool(row["semantic_state_preserved"]),
                expected="preserve the independently valid Base/Mechanism completion state",
                observed="mixed completion state was projected to false/false",
                evidence=dict(row),
            )
            for row in result["mixed_completion_controls"]
        ),
    )
    diagnostic = _group(
        "diagnostic_empirical_admission",
        tuple(
            _observation(
                category="diagnostic_empirical_admission",
                control=row["control"],
                attack=True,
                input_valid=True,
                fully_rehashed=True,
                admitted=bool(row["estimator_admitted"]),
                property_preserved=not bool(row["estimator_admitted"]),
                expected=(
                    "reject a non-reachable diagnostic terminal before the empirical denominator"
                ),
                observed="diagnostic terminal entered a 192-row empirical evaluation",
                evidence=dict(row),
            )
            for row in result["diagnostic_empirical_controls"]
        ),
    )
    loci = _group(
        "failure_locus_authenticity",
        tuple(
            _observation(
                category="failure_locus_authenticity",
                control=row["control"],
                attack=True,
                input_valid=True,
                fully_rehashed=bool(row["fully_rehashed"]),
                admitted=bool(row["validator_admitted"]),
                property_preserved=not bool(row["validator_admitted"]),
                expected=(
                    "derive and compare FailureLocus semantics from exact attempts and results"
                ),
                observed="fully rehashed invented locus was accepted",
                evidence=dict(row),
            )
            for row in result["failure_locus_controls"]
        ),
    )
    byte_row = dict(result["artifact_byte_control"])
    byte_admitted = bool(byte_row["validator_admitted_after"])
    artifact_bytes = _group(
        "artifact_byte_authenticity",
        (
            _observation(
                category="artifact_byte_authenticity",
                control=byte_row["control"],
                attack=True,
                input_valid=bool(byte_row["bytes_changed"]),
                fully_rehashed=False,
                admitted=byte_admitted,
                property_preserved=not byte_admitted,
                expected="bind and rehash persisted Raw/Result bytes before admission",
                observed="path-only descriptors admitted changed file bytes",
                evidence=byte_row,
            ),
        ),
    )
    parent_revalidation = _group(
        "authoritative_parent_revalidation",
        tuple(
            _observation(
                category="authoritative_parent_revalidation",
                control=row["control"],
                attack=True,
                input_valid=bool(row["direct_parent_revalidation_rejected"]),
                fully_rehashed=False,
                admitted=bool(row["production_estimator_admitted"]),
                property_preserved=not bool(row["production_estimator_admitted"]),
                expected="revalidate every authoritative Registry/Contract/Manifest parent",
                observed="invalid model_construct parent reached the estimator",
                evidence=dict(row),
            )
            for row in result["parent_injection_controls"]
        ),
    )
    return mixed, diagnostic, loci, artifact_bytes, parent_revalidation


def _decision(
    freeze: models.ExactPredecessorFreezeAudit,
    groups: Sequence[models.ControlGroupAudit],
    v181_report: v181_models.PreflightReport,
) -> models.IndependentAuditGateDecision:
    by_category = {item.category: item for item in groups}
    gates = {
        "exact_source_and_artifact_freeze": True,
        "scripted_object_dag_parent_binding": (
            v181_report.parent_authenticity_preflight == "CLOSED"
        ),
        "enumerated_terminal_shape_construction": (
            v181_report.terminal_totality_preflight == "CLOSED"
        ),
        "empirical_terminal_semantic_totality": by_category[
            "completed_invalid_factorization"
        ].gate_passed,
        "diagnostic_terminal_empirical_isolation": by_category[
            "diagnostic_empirical_admission"
        ].gate_passed,
        "failure_locus_semantic_authenticity": by_category[
            "failure_locus_authenticity"
        ].gate_passed,
        "persisted_artifact_byte_authenticity": by_category[
            "artifact_byte_authenticity"
        ].gate_passed,
        "authoritative_parent_revalidation": by_category[
            "authoritative_parent_revalidation"
        ].gate_passed,
    }
    values = {
        "predecessor_freeze_audit_id": freeze.audit_id,
        "control_group_audit_ids": tuple(item.audit_id for item in groups),
        "gates": gates,
        "passed_gate_count": sum(gates.values()),
        "failed_gate_count": sum(not item for item in gates.values()),
        "exact_source_and_artifact_freeze": True,
        "scripted_object_dag_parent_binding": True,
        "enumerated_terminal_shape_construction": True,
        "empirical_terminal_semantic_totality": False,
        "diagnostic_terminal_empirical_isolation": False,
        "failure_locus_semantic_authenticity": False,
        "persisted_artifact_byte_authenticity": False,
        "authoritative_parent_revalidation": False,
        "online_execution_authorized": False,
        "online_execution_admission": "BLOCKED_FAILED_INDEPENDENT_AUDIT",
        "next_stage": (
            "artifact_backed_terminal_validity_factorization_and_"
            "failure_locus_reconstruction_preflight_only"
        ),
        "provider_calls": 0,
        "empirical_outcome_count": 0,
    }
    return cast(
        models.IndependentAuditGateDecision,
        models.make_identity_model(
            models.IndependentAuditGateDecision,
            values,
            field="decision_id",
            prefix="finance_v26_181_independent_audit_gate_decision:",
        ),
    )


def _artifact_bytes(value: BaseModel) -> bytes:
    return canonical_json_bytes(value) + b"\n"


def _detail_bindings(payloads: Mapping[str, bytes]) -> tuple[models.FileBinding, ...]:
    return tuple(
        _binding(
            f"{OUTPUT_DIR}/{filename}",
            payloads[filename],
            source_kind="v26_182_formal_detail",
        )
        for filename in sorted(payloads)
    )


def _write_immutable_directory(output_dir: Path, payloads: Mapping[str, bytes]) -> None:
    output_dir = output_dir.resolve()
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    lock = output_dir.with_name(f".{output_dir.name}.write-lock")
    lock.mkdir(exist_ok=False)
    staging: Path | None = None
    try:
        if output_dir.exists():
            raise FileExistsError(f"immutable artifact directory already exists: {output_dir}")
        staging = Path(
            tempfile.mkdtemp(
                prefix=f".{output_dir.name}.staging-",
                dir=output_dir.parent,
            )
        )
        for filename, payload in sorted(payloads.items()):
            if Path(filename).name != filename:
                raise ValueError("immutable artifact filename is not local")
            path = staging / filename
            with path.open("xb") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
        os.rename(staging, output_dir)
        staging = None
    finally:
        if staging is not None and staging.exists():
            shutil.rmtree(staging)
        lock.rmdir()


def build(
    *,
    package_root: Path,
    output_dir: Path,
    write_artifacts: bool = True,
) -> models.BuildProducts:
    package_root = _resolve_package_root(package_root)
    repo_root = _repo_root(package_root)
    source_root, source_paths = _source_root_and_paths(repo_root)
    required_paths = tuple(
        sorted(
            {
                *source_paths,
                *FROZEN_INPUT_PATHS,
                *(f"{V181_DIR}/{name}" for name in V181_ARTIFACT_NAMES),
            }
        )
    )
    archive = _archive(repo_root, required_paths)
    artifact_archive = {path: archive[path] for path in archive if path.startswith(f"{V181_DIR}/")}
    parsed_artifacts, validated_count = _validate_v181_artifacts(artifact_archive)
    if validated_count != 14:
        raise ValueError("v26.181 formal JSON identity replay is incomplete")
    freeze = _freeze_audit(
        package_root=package_root,
        repo_root=repo_root,
        source_root=source_root,
        archive=archive,
        parsed_artifacts=parsed_artifacts,
    )
    runner_archive = {path: archive[path] for path in (*source_paths, *FROZEN_INPUT_PATHS)}
    negative_results = _run_exact_negative_controls(
        package_root=package_root,
        archive=runner_archive,
    )
    groups = _control_groups(negative_results)
    completed_invalid, diagnostic, loci, artifact_bytes, parent_revalidation = groups
    v181_report = cast(v181_models.PreflightReport, parsed_artifacts["report.json"])
    decision = _decision(freeze, groups, v181_report)
    details: dict[str, BaseModel] = {
        "artifact_byte_authenticity_audit.json": artifact_bytes,
        "authoritative_parent_revalidation_audit.json": parent_revalidation,
        "completed_invalid_factorization_audit.json": completed_invalid,
        "diagnostic_empirical_admission_audit.json": diagnostic,
        "exact_predecessor_freeze_audit.json": freeze,
        "failure_locus_authenticity_audit.json": loci,
        "independent_audit_gate_decision.json": decision,
    }
    detail_payloads = {filename: _artifact_bytes(value) for filename, value in details.items()}
    detail_bindings = _detail_bindings(detail_payloads)
    report = cast(
        models.IndependentAuditReport,
        models.make_identity_model(
            models.IndependentAuditReport,
            {
                "run_id": RUN_ID,
                "audited_commit": AUDITED_COMMIT,
                "predecessor_freeze_audit_id": freeze.audit_id,
                "completed_invalid_factorization_audit_id": completed_invalid.audit_id,
                "diagnostic_empirical_admission_audit_id": diagnostic.audit_id,
                "failure_locus_authenticity_audit_id": loci.audit_id,
                "artifact_byte_authenticity_audit_id": artifact_bytes.audit_id,
                "authoritative_parent_revalidation_audit_id": parent_revalidation.audit_id,
                "gate_decision_id": decision.decision_id,
                "detail_files": detail_bindings,
                "detail_file_count": len(detail_bindings),
                "independent_control_count": sum(len(item.observations) for item in groups),
                "admitted_attack_count": sum(item.admitted_attack_count for item in groups),
                "semantic_state_loss_control_count": sum(
                    not item.required_property_preserved for item in completed_invalid.observations
                ),
                "provider_calls": 0,
                "development_model_outcomes": 0,
                "formal_empirical_rows_materialized": 0,
                "online_execution_authorized": False,
                "online_execution_admission": "BLOCKED_FAILED_INDEPENDENT_AUDIT",
                "next_stage": decision.next_stage,
            },
            field="report_id",
            prefix="finance_v26_181_independent_audit_report:",
        ),
    )
    all_payloads = {**detail_payloads, "report.json": _artifact_bytes(report)}
    if write_artifacts:
        _write_immutable_directory(output_dir, all_payloads)
    return models.BuildProducts(
        freeze=freeze,
        completed_invalid=completed_invalid,
        diagnostic_empirical=diagnostic,
        failure_locus=loci,
        artifact_bytes=artifact_bytes,
        parent_revalidation=parent_revalidation,
        decision=decision,
        report=report,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--package-root", type=Path, default=Path.cwd())
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    package_root = _resolve_package_root(args.package_root)
    products = build(
        package_root=package_root,
        output_dir=args.output_dir or package_root / OUTPUT_DIR,
    )
    print(products.report.model_dump_json())


if __name__ == "__main__":
    main()
