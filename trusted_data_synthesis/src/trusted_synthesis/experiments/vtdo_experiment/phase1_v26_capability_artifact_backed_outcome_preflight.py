from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import tarfile
import tempfile
from dataclasses import dataclass
from functools import partial
from pathlib import Path
from typing import Any, Final, cast

from pydantic import BaseModel

from trusted_synthesis.core.immutable_artifacts import write_immutable_artifact_directory
from trusted_synthesis.core.task import authoritative_artifact_backed_outcome as outcome
from trusted_synthesis.core.task.authoritative_job_bound_outcome import (
    AuthoritativeJobBoundOutcomeContract,
    AuthoritativeTerminalRegistry,
    FailureLocus,
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
    phase1_v26_capability_artifact_backed_outcome_preflight_models as models,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_capability_authoritative_outcome_terminal_independent_audit_models as v182_models,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_capability_authoritative_outcome_terminal_preflight as v181,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_capability_authoritative_outcome_terminal_preflight_models as v181_models,
)
from trusted_synthesis.hashing import canonical_hash

RUN_ID: Final = "finance_v26_186_artifact_backed_outcome_preflight_v2_20260831"
OUTPUT_DIR: Final = f"artifacts/vtdo_experiment/{RUN_ID}"
V181_DIR: Final = v181.OUTPUT_DIR
V182_DIR: Final = (
    "artifacts/vtdo_experiment/"
    "finance_v26_182_authoritative_outcome_terminal_independent_audit_v1_20260831"
)
EXPECTED_V182_REPORT_ID: Final = (
    "finance_v26_181_independent_audit_report:"
    "71e7810db19c41f68c0bb3a72cb5e361d84a29f99691ea4f1d8e41f60bda7e62"
)
EXPECTED_V182_DECISION_ID: Final = (
    "finance_v26_181_independent_audit_gate_decision:"
    "851fe904add0efe9599f75e414dcee61aff9ad2f74060abe6dcddf4a38e89b05"
)
EXPECTED_V181_REPORT_ID: Final = (
    "finance_v26_authoritative_outcome_preflight_report:"
    "2fec6e40b8eb04cf510896979ed1088a2f716e8acd7d78641f4e027f368c99e8"
)


@dataclass(frozen=True)
class FrozenInputs:
    v181_report: v181_models.PreflightReport
    v182_report: v182_models.IndependentAuditReport
    v182_decision: v182_models.IndependentAuditGateDecision
    registry: AuthoritativeTerminalRegistry
    predecessor_contract: AuthoritativeJobBoundOutcomeContract
    manifest: CapabilityDevelopmentJobManifest
    runner: JobBoundRunnerContract
    scripted_outcomes: dict[str, JobBoundOutcomePayload]


@dataclass(frozen=True)
class Catalogs:
    bundles: tuple[outcome.ArtifactBackedEvidenceBundle, ...]
    evaluation: outcome.ArtifactBackedPreflightEvaluation


def _resolve_package_root(root: Path) -> Path:
    if (root / "src" / "trusted_synthesis").is_dir():
        return root.resolve()
    candidate = root / "trusted_data_synthesis"
    if (candidate / "src" / "trusted_synthesis").is_dir():
        return candidate.resolve()
    raise ValueError("v26.186 cannot resolve the trusted_data_synthesis package root")


def _load(path: Path) -> Any:
    return json.loads(path.read_bytes())


def _json_value(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json", warnings=False)
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
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


def _sha256_path(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    count = 0
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
            count += len(chunk)
    return digest.hexdigest(), count


def _binding(
    *,
    package_root: Path,
    path: Path,
    source_kind: str,
) -> models.FileBinding:
    sha256, byte_count = _sha256_path(path)
    return models.FileBinding(
        relative_path=path.relative_to(package_root).as_posix(),
        sha256=sha256,
        byte_count=byte_count,
        source_kind=cast(Any, source_kind),
    )


def _archive_commit(path: Path) -> str:
    with path.open("rb") as handle:
        result = subprocess.run(
            ("git", "get-tar-commit-id"),
            stdin=handle,
            check=False,
            capture_output=True,
            text=False,
        )
    value = result.stdout.decode("ascii", errors="strict").strip()
    if result.returncode != 0 or len(value) != 40:
        raise ValueError("v26.186 source Archive lacks an embedded Git commit")
    return value


def _git_blob_id(payload: bytes) -> str:
    header = f"blob {len(payload)}\0".encode()
    return hashlib.sha1(header + payload, usedforsecurity=False).hexdigest()


def _archive_rows(path: Path) -> tuple[dict[str, Any], ...]:
    rows: list[dict[str, Any]] = []
    observed: set[str] = set()
    with tarfile.open(path, mode="r:") as archive:
        for member in archive.getmembers():
            name = member.name.rstrip("/")
            if not name or member.isdir():
                continue
            parts = Path(name).parts
            if Path(name).is_absolute() or any(part in {"", ".", ".."} for part in parts):
                raise ValueError("v26.186 source Archive contains an unsafe path")
            if name in observed:
                raise ValueError("v26.186 source Archive repeats a member")
            observed.add(name)
            if member.isfile():
                handle = archive.extractfile(member)
                if handle is None:
                    raise ValueError("v26.186 source Archive member is unreadable")
                payload = handle.read()
                kind = "file"
                executable = bool(member.mode & 0o111)
            elif member.issym():
                payload = member.linkname.encode()
                kind = "symlink"
                executable = False
            else:
                raise ValueError("v26.186 source Archive contains a non-Git member")
            rows.append(
                {
                    "path": name,
                    "kind": kind,
                    "executable": executable,
                    "git_blob_id": _git_blob_id(payload),
                }
            )
    return tuple(sorted(rows, key=lambda item: str(item["path"])))


def _git_tree_id(rows: tuple[dict[str, Any], ...]) -> str:
    root: dict[str, Any] = {}
    for row in rows:
        parts = str(row["path"]).split("/")
        node = root
        for part in parts[:-1]:
            child = node.setdefault(part, {})
            if not isinstance(child, dict) or "path" in child:
                raise ValueError("v26.186 source Archive contains a path collision")
            node = child
        if parts[-1] in node:
            raise ValueError("v26.186 source Archive repeats a Git entry")
        node[parts[-1]] = row

    def visit(node: dict[str, Any]) -> str:
        body = bytearray()
        for name in sorted(node, key=lambda value: value.encode()):
            value = node[name]
            if isinstance(value, dict) and "path" not in value:
                mode = "40000"
                object_id = visit(value)
            else:
                mode = (
                    "120000"
                    if value["kind"] == "symlink"
                    else ("100755" if value["executable"] else "100644")
                )
                object_id = value["git_blob_id"]
            body.extend(mode.encode())
            body.extend(b" ")
            body.extend(name.encode())
            body.extend(b"\0")
            body.extend(bytes.fromhex(object_id))
        header = f"tree {len(body)}\0".encode()
        return hashlib.sha1(header + body, usedforsecurity=False).hexdigest()

    return visit(root)


def _load_frozen_inputs(package_root: Path) -> FrozenInputs:
    v181_dir = package_root / V181_DIR
    v182_dir = package_root / V182_DIR
    v181_report = v181_models.PreflightReport.model_validate(_load(v181_dir / "report.json"))
    v182_report = v182_models.IndependentAuditReport.model_validate(_load(v182_dir / "report.json"))
    v182_decision = v182_models.IndependentAuditGateDecision.model_validate(
        _load(v182_dir / "independent_audit_gate_decision.json")
    )
    if (
        v181_report.report_id != EXPECTED_V181_REPORT_ID
        or v182_report.report_id != EXPECTED_V182_REPORT_ID
        or v182_decision.decision_id != EXPECTED_V182_DECISION_ID
        or v182_report.next_stage != models.AUTHORIZED_STAGE
        or v182_decision.next_stage != models.AUTHORIZED_STAGE
        or v182_decision.failed_gate_count != 5
    ):
        raise ValueError("v26.181/v26.182 exact authorization parents differ")
    registry_audit = _load(v181_dir / "authoritative_terminal_registry_audit.json")
    registry = AuthoritativeTerminalRegistry.model_validate(registry_audit["registry"])
    predecessor_contract = AuthoritativeJobBoundOutcomeContract.model_validate(
        _load(v181_dir / "authoritative_job_bound_outcome_contract.json")
    )
    historical = v181._load_frozen_inputs(package_root)
    scripted_outcomes = {item.job_id: item.outcome for item in historical.scripted.rows}
    if set(scripted_outcomes) != set(historical.manifest.expected_job_ids):
        raise ValueError("v26.179 scripted outcomes differ from the exact Manifest")
    return FrozenInputs(
        v181_report=v181_report,
        v182_report=v182_report,
        v182_decision=v182_decision,
        registry=registry,
        predecessor_contract=predecessor_contract,
        manifest=historical.manifest,
        runner=historical.runner,
        scripted_outcomes=scripted_outcomes,
    )


def _authorization(
    *,
    frozen: FrozenInputs,
    source_commit: str,
    source_tree: str,
    source_archive: Path,
) -> models.PreflightAuthorization:
    archive_sha256, archive_byte_count = _sha256_path(source_archive)
    if _archive_commit(source_archive) != source_commit:
        raise ValueError("v26.186 source Archive commit differs from the authorization")
    if _git_tree_id(_archive_rows(source_archive)) != source_tree:
        raise ValueError("v26.186 source Archive tree differs from the authorization")
    return cast(
        models.PreflightAuthorization,
        models.make_identity_model(
            models.PreflightAuthorization,
            {
                "v26_182_report_id": frozen.v182_report.report_id,
                "v26_182_gate_decision_id": frozen.v182_decision.decision_id,
                "source_commit": source_commit,
                "source_tree": source_tree,
                "source_archive_sha256": archive_sha256,
                "source_archive_byte_count": archive_byte_count,
            },
            field="authorization_id",
            prefix="finance_v26_artifact_backed_outcome_authorization:",
        ),
    )


def _freeze(
    *,
    package_root: Path,
    frozen: FrozenInputs,
    authorization: models.PreflightAuthorization,
) -> models.PredecessorFreezeAudit:
    v181_paths = tuple(
        sorted(path for path in (package_root / V181_DIR).iterdir() if path.is_file())
    )
    v182_paths = tuple(
        sorted(path for path in (package_root / V182_DIR).iterdir() if path.is_file())
    )
    if len(v181_paths) != 15 or len(v182_paths) != 8:
        raise ValueError("v26.181/v26.182 formal artifact denominator differs")
    return cast(
        models.PredecessorFreezeAudit,
        models.make_identity_model(
            models.PredecessorFreezeAudit,
            {
                "authorization_id": authorization.authorization_id,
                "v26_181_report_id": frozen.v181_report.report_id,
                "v26_182_report_id": frozen.v182_report.report_id,
                "v26_182_gate_decision_id": frozen.v182_decision.decision_id,
                "v26_181_files": tuple(
                    _binding(
                        package_root=package_root,
                        path=path,
                        source_kind="v26_181_formal_artifact",
                    )
                    for path in v181_paths
                ),
                "v26_182_files": tuple(
                    _binding(
                        package_root=package_root,
                        path=path,
                        source_kind="v26_182_formal_artifact",
                    )
                    for path in v182_paths
                ),
            },
            field="audit_id",
            prefix="finance_v26_artifact_backed_predecessor_freeze:",
        ),
    )


def _contract(
    *,
    frozen: FrozenInputs,
    authorization: models.PreflightAuthorization,
    freeze: models.PredecessorFreezeAudit,
) -> tuple[outcome.ArtifactBackedOutcomeContract, models.OutcomeContractAudit]:
    contract = outcome.contract_from_v2(
        registry=frozen.registry,
        predecessor_contract_id=frozen.predecessor_contract.contract_id,
        manifest=frozen.manifest,
        runner=frozen.runner,
        job_component_sequences=frozen.predecessor_contract.job_component_sequences,
    )
    audit = cast(
        models.OutcomeContractAudit,
        models.make_identity_model(
            models.OutcomeContractAudit,
            {
                "authorization_id": authorization.authorization_id,
                "predecessor_freeze_id": freeze.audit_id,
                "contract": contract,
                "registry_id": frozen.registry.registry_id,
                "predecessor_contract_id": frozen.predecessor_contract.contract_id,
                "manifest_id": frozen.manifest.manifest_id,
                "runner_id": frozen.runner.runner_id,
            },
            field="audit_id",
            prefix="finance_v26_artifact_backed_outcome_contract_audit:",
        ),
    )
    return contract, audit


def _scripted_catalogs(
    *,
    artifact_root: Path,
    frozen: FrozenInputs,
    contract: outcome.ArtifactBackedOutcomeContract,
) -> Catalogs:
    bundles = tuple(
        outcome.build_artifact_backed_bundle(
            artifact_root=artifact_root,
            job=job,
            manifest=frozen.manifest,
            runner=frozen.runner,
            registry=frozen.registry,
            contract=contract,
            terminal_kind="completed_qualified",
            evidence_kind="scripted_preflight_control",
            source_outcome=frozen.scripted_outcomes[job.job_id],
        )
        for job in frozen.manifest.jobs
    )
    evaluation = outcome.evaluate_artifact_backed_evidence_set(
        artifact_root=artifact_root,
        bundles=bundles,
        manifest=frozen.manifest,
        registry=frozen.registry,
        contract=contract,
        runner=frozen.runner,
        expected_evidence_kind="scripted_preflight_control",
    )
    if not isinstance(evaluation, outcome.ArtifactBackedPreflightEvaluation):
        raise TypeError("scripted artifact-backed evaluation was mislabeled empirical")
    return Catalogs(bundles=bundles, evaluation=evaluation)


def _mixed_outcome(
    source: JobBoundOutcomePayload,
    *,
    base_valid: bool,
    mechanism_qualified: bool,
) -> JobBoundOutcomePayload:
    values = source.model_dump(
        mode="python",
        exclude={"attempt_trace_id", "schema_version"},
        warnings=False,
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


def _control_id(family: str, target: str, values: dict[str, Any]) -> str:
    return canonical_hash(
        {"family": family, "target": target, **values},
        prefix="finance_v26_artifact_backed_control:",
    )


def _capture_rejection(
    *,
    family: str,
    target: str,
    fully_rehashed: bool,
    operation: Any,
) -> models.RejectionControl:
    try:
        operation()
    except ValueError as exc:
        reason = str(exc)
    else:
        raise ValueError(f"negative control was admitted:{family}:{target}")
    values = {
        "fully_rehashed": fully_rehashed,
        "rejection_reason": reason,
    }
    return models.RejectionControl(
        control_id=_control_id(family, target, values),
        family=cast(Any, family),
        target=target,
        fully_rehashed=fully_rehashed,
        rejection_reason=reason,
    )


def _factorization(
    *,
    frozen: FrozenInputs,
    contract: outcome.ArtifactBackedOutcomeContract,
) -> models.TerminalValidityFactorizationAudit:
    job = frozen.manifest.jobs[0]
    source = frozen.scripted_outcomes[job.job_id]
    specifications = ((True, False), (False, True))
    controls: list[models.FactorizationControl] = []
    for base_valid, mechanism_qualified in specifications:
        mixed = _mixed_outcome(
            source,
            base_valid=base_valid,
            mechanism_qualified=mechanism_qualified,
        )
        with tempfile.TemporaryDirectory(prefix="v26-186-factorization-") as temporary:
            bundle = outcome.build_artifact_backed_bundle(
                artifact_root=Path(temporary),
                job=job,
                manifest=frozen.manifest,
                runner=frozen.runner,
                registry=frozen.registry,
                contract=contract,
                terminal_kind="completed_invalid",
                evidence_kind="scripted_preflight_control",
                source_outcome=mixed,
                base_failure_stage="base_answer" if not base_valid else None,
                mechanism_failure_component_index=(
                    len(mixed.component_attempts) - 1 if not mechanism_qualified else None
                ),
            )
        control_values = {
            "final_base_valid": base_valid,
            "final_mechanism_qualified": mechanism_qualified,
            "final_qualified_valid": False,
            "reconstructed_base_valid": bundle.row.final_base_valid,
            "reconstructed_mechanism_qualified": bundle.row.final_mechanism_qualified,
            "reconstructed_qualified_valid": bundle.row.final_qualified_valid,
            "derived_locus_stages": tuple(item.stage for item in bundle.trace.failure_loci),
        }
        controls.append(
            models.FactorizationControl(
                control_id=_control_id(
                    "factorization",
                    str(specifications.index((base_valid, mechanism_qualified))),
                    control_values,
                ),
                **control_values,
            )
        )
    return cast(
        models.TerminalValidityFactorizationAudit,
        models.make_identity_model(
            models.TerminalValidityFactorizationAudit,
            {"contract_id": contract.contract_id, "controls": tuple(controls)},
            field="audit_id",
            prefix="finance_v26_terminal_validity_factorization_audit:",
        ),
    )


def _rehashed_locus_attack(
    *,
    bundle: outcome.ArtifactBackedEvidenceBundle,
    locus: FailureLocus,
) -> outcome.ArtifactBackedEvidenceBundle:
    trace_values = bundle.trace.model_dump(
        mode="python",
        exclude={"trace_id", "schema_version"},
        warnings=False,
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
        mode="python",
        exclude={"row_id", "schema_version"},
        warnings=False,
    )
    row_values.update(
        trace_id=trace.trace_id,
        first_base_invalid_locus_id=(
            locus.locus_id if locus.stage in {"base_answer", "base_citation"} else None
        ),
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
        raw=bundle.raw,
        result=bundle.result,
        trace=trace,
        row=row,
    )


def _locus_audit(
    *,
    artifact_root: Path,
    frozen: FrozenInputs,
    contract: outcome.ArtifactBackedOutcomeContract,
    catalogs: Catalogs,
) -> models.FailureLocusReconstructionAudit:
    job = frozen.manifest.jobs[0]
    baseline = next(item for item in catalogs.bundles if item.row.job_id == job.job_id)
    base_locus = cast(
        FailureLocus,
        make_v2_identity_model(
            FailureLocus,
            {
                "stage": "base_answer",
                "component_key": None,
                "attempt_index": None,
                "reason_code": "invented_base_failure",
                "evaluability": "evaluated_false",
                "source_descriptor_id": baseline.result.result_id,
            },
            field="locus_id",
            prefix="capability_authoritative_failure_locus:",
        ),
    )
    mechanism_locus = cast(
        FailureLocus,
        make_v2_identity_model(
            FailureLocus,
            {
                "stage": "mechanism",
                "component_key": "invented.absent.component",
                "attempt_index": 0,
                "reason_code": "invented_mechanism_failure",
                "evaluability": "evaluated_false",
                "source_descriptor_id": baseline.result.result_id,
            },
            field="locus_id",
            prefix="capability_authoritative_failure_locus:",
        ),
    )
    controls = tuple(
        _capture_rejection(
            family="failure_locus_reconstruction",
            target=target,
            fully_rehashed=True,
            operation=lambda item=item: outcome.validate_artifact_backed_bundle(
                artifact_root=artifact_root,
                job=job,
                manifest=frozen.manifest,
                runner=frozen.runner,
                registry=frozen.registry,
                contract=contract,
                bundle=_rehashed_locus_attack(bundle=baseline, locus=item),
                expected_evidence_kind="scripted_preflight_control",
            ),
        )
        for target, item in (
            ("invented_base_locus", base_locus),
            ("invented_absent_component_locus", mechanism_locus),
        )
    )
    return cast(
        models.FailureLocusReconstructionAudit,
        models.make_identity_model(
            models.FailureLocusReconstructionAudit,
            {"contract_id": contract.contract_id, "controls": controls},
            field="audit_id",
            prefix="finance_v26_failure_locus_reconstruction_audit:",
        ),
    )


def _artifact_audit(
    *,
    artifact_root: Path,
    frozen: FrozenInputs,
    contract: outcome.ArtifactBackedOutcomeContract,
    catalogs: Catalogs,
) -> models.ArtifactByteAuthenticityAudit:
    job = frozen.manifest.jobs[0]
    bundle = next(item for item in catalogs.bundles if item.row.job_id == job.job_id)
    controls: list[models.RejectionControl] = []
    for target, relative_path in (
        ("Raw", bundle.raw.artifact_relative_path),
        ("Result", bundle.result.artifact_relative_path),
    ):
        with tempfile.TemporaryDirectory(prefix="v26-186-byte-attack-") as temporary:
            attack_root = Path(temporary)
            shutil.copy2(
                artifact_root / bundle.raw.artifact_relative_path,
                attack_root / bundle.raw.artifact_relative_path,
            )
            shutil.copy2(
                artifact_root / bundle.result.artifact_relative_path,
                attack_root / bundle.result.artifact_relative_path,
            )
            with (attack_root / relative_path).open("ab") as handle:
                handle.write(b"changed")
            controls.append(
                _capture_rejection(
                    family="artifact_byte_authenticity",
                    target=target,
                    fully_rehashed=False,
                    operation=lambda attack_root=attack_root: (
                        outcome.validate_artifact_backed_bundle(
                            artifact_root=attack_root,
                            job=job,
                            manifest=frozen.manifest,
                            runner=frozen.runner,
                            registry=frozen.registry,
                            contract=contract,
                            bundle=bundle,
                            expected_evidence_kind="scripted_preflight_control",
                        )
                    ),
                )
            )
    return cast(
        models.ArtifactByteAuthenticityAudit,
        models.make_identity_model(
            models.ArtifactByteAuthenticityAudit,
            {"contract_id": contract.contract_id, "controls": tuple(controls)},
            field="audit_id",
            prefix="finance_v26_artifact_byte_authenticity_repair_audit:",
        ),
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
        mode="python",
        exclude={"raw_execution_id", "schema_version"},
        warnings=False,
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
    result_payload = outcome.ArtifactBackedJobResultPayload.model_validate(
        json.loads(result_path.read_bytes())
    )
    result_payload_values = result_payload.model_dump(
        mode="python",
        exclude={"payload_id", "schema_version"},
        warnings=False,
    )
    result_payload_values["raw_execution_id"] = raw.raw_execution_id
    result_payload = cast(
        outcome.ArtifactBackedJobResultPayload,
        outcome.make_identity_model(
            outcome.ArtifactBackedJobResultPayload,
            result_payload_values,
            field="payload_id",
            prefix="capability_artifact_backed_job_result_payload:",
        ),
    )
    result_bytes = outcome.canonical_model_bytes(result_payload)
    result_path.write_bytes(result_bytes)
    result_values = bundle.result.model_dump(
        mode="python",
        exclude={"result_id", "schema_version"},
        warnings=False,
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
    raw_payload = outcome.RawExecutionEvidencePayload.model_validate(
        json.loads((artifact_root / raw.artifact_relative_path).read_bytes())
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


def _empirical_attack(
    *,
    frozen: FrozenInputs,
    contract: outcome.ArtifactBackedOutcomeContract,
    terminal_kind: str,
) -> None:
    with tempfile.TemporaryDirectory(prefix="v26-186-empirical-attack-") as temporary:
        artifact_root = Path(temporary)
        target_job_id = frozen.manifest.expected_job_ids[0]
        scripted: list[outcome.ArtifactBackedEvidenceBundle] = []
        for job in frozen.manifest.jobs:
            target = job.job_id == target_job_id
            bundle = outcome.build_artifact_backed_bundle(
                artifact_root=artifact_root,
                job=job,
                manifest=frozen.manifest,
                runner=frozen.runner,
                registry=frozen.registry,
                contract=contract,
                terminal_kind=cast(Any, terminal_kind if target else "completed_qualified"),
                evidence_kind="scripted_preflight_control",
                source_outcome=(None if target else frozen.scripted_outcomes[job.job_id]),
            )
            scripted.append(bundle)
        empirical = tuple(
            _rewrite_empirical(
                artifact_root=artifact_root,
                job=next(
                    item for item in frozen.manifest.jobs if item.job_id == item_bundle.row.job_id
                ),
                manifest=frozen.manifest,
                runner=frozen.runner,
                bundle=item_bundle,
            )
            for item_bundle in scripted
        )
        outcome.evaluate_artifact_backed_evidence_set(
            artifact_root=artifact_root,
            bundles=empirical,
            manifest=frozen.manifest,
            registry=frozen.registry,
            contract=contract,
            runner=frozen.runner,
            expected_evidence_kind="empirical_execution",
        )


def _admission_audit(
    *,
    frozen: FrozenInputs,
    contract: outcome.ArtifactBackedOutcomeContract,
) -> models.EmpiricalAdmissionAudit:
    controls = tuple(
        _capture_rejection(
            family="diagnostic_empirical_admission",
            target=terminal_kind,
            fully_rehashed=True,
            operation=lambda terminal_kind=terminal_kind: _empirical_attack(
                frozen=frozen,
                contract=contract,
                terminal_kind=terminal_kind,
            ),
        )
        for terminal_kind in ("measurement_support_exit", "policy_horizon_exhausted")
    )
    return cast(
        models.EmpiricalAdmissionAudit,
        models.make_identity_model(
            models.EmpiricalAdmissionAudit,
            {"contract_id": contract.contract_id, "controls": controls},
            field="audit_id",
            prefix="finance_v26_artifact_backed_empirical_admission_audit:",
        ),
    )


def _parent_audit(
    *,
    artifact_root: Path,
    frozen: FrozenInputs,
    contract: outcome.ArtifactBackedOutcomeContract,
    catalogs: Catalogs,
) -> models.ParentRevalidationAudit:
    registry_values = frozen.registry.model_dump(mode="python", warnings=False)
    registry_values["unmapped_source_label_count"] = 1
    invalid_registry = AuthoritativeTerminalRegistry.model_construct(**registry_values)
    contract_values = contract.model_dump(mode="python", warnings=False)
    contract_values["formal_empirical_rows_materialized"] = True
    invalid_contract = outcome.ArtifactBackedOutcomeContract.model_construct(**contract_values)
    manifest_values = frozen.manifest.model_dump(mode="python", warnings=False)
    manifest_values["provider_calls"] = 1
    invalid_manifest = CapabilityDevelopmentJobManifest.model_construct(**manifest_values)
    runner_values = frozen.runner.model_dump(mode="python", warnings=False)
    runner_values["provider_calls_authorized"] = True
    invalid_runner = JobBoundRunnerContract.model_construct(**runner_values)
    job = frozen.manifest.jobs[0]
    job_values = job.model_dump(mode="python", warnings=False)
    job_values["schedule_ids"] = (job.schedule_ids[0], job.schedule_ids[0])
    invalid_job = CapabilityDevelopmentJob.model_construct(**job_values)
    jobs = list(frozen.manifest.jobs)
    jobs[0] = invalid_job
    job_manifest_values = frozen.manifest.model_dump(mode="python", warnings=False)
    job_manifest_values["jobs"] = tuple(jobs)
    invalid_job_manifest = CapabilityDevelopmentJobManifest.model_construct(**job_manifest_values)
    specifications = (
        ("Contract", frozen.registry, invalid_contract, frozen.manifest, frozen.runner),
        ("Job", frozen.registry, contract, invalid_job_manifest, frozen.runner),
        ("Manifest", frozen.registry, contract, invalid_manifest, frozen.runner),
        ("Registry", invalid_registry, contract, frozen.manifest, frozen.runner),
        ("Runner", frozen.registry, contract, frozen.manifest, invalid_runner),
    )

    def evaluate_candidate(
        *,
        registry: AuthoritativeTerminalRegistry,
        candidate_contract: outcome.ArtifactBackedOutcomeContract,
        manifest: CapabilityDevelopmentJobManifest,
        runner: JobBoundRunnerContract,
    ) -> None:
        outcome.evaluate_artifact_backed_evidence_set(
            artifact_root=artifact_root,
            bundles=catalogs.bundles,
            manifest=manifest,
            registry=registry,
            contract=candidate_contract,
            runner=runner,
            expected_evidence_kind="scripted_preflight_control",
        )

    controls = tuple(
        _capture_rejection(
            family="authoritative_parent_revalidation",
            target=target,
            fully_rehashed=False,
            operation=partial(
                evaluate_candidate,
                registry=registry,
                candidate_contract=candidate_contract,
                manifest=manifest,
                runner=runner,
            ),
        )
        for target, registry, candidate_contract, manifest, runner in specifications
    )
    return cast(
        models.ParentRevalidationAudit,
        models.make_identity_model(
            models.ParentRevalidationAudit,
            {
                "contract_id": contract.contract_id,
                "controls": controls,
                "parent_types": tuple(sorted(item[0] for item in specifications)),
            },
            field="audit_id",
            prefix="finance_v26_authoritative_parent_revalidation_repair_audit:",
        ),
    )


def _evidence_dag(
    *,
    contract: outcome.ArtifactBackedOutcomeContract,
    catalogs: Catalogs,
) -> models.ScriptedEvidenceDagAudit:
    return cast(
        models.ScriptedEvidenceDagAudit,
        models.make_identity_model(
            models.ScriptedEvidenceDagAudit,
            {"contract_id": contract.contract_id, "evaluation": catalogs.evaluation},
            field="audit_id",
            prefix="finance_v26_artifact_backed_scripted_evidence_dag_audit:",
        ),
    )


def _gate(name: str, *evidence_ids: str) -> models.StaticGate:
    return cast(
        models.StaticGate,
        models.make_identity_model(
            models.StaticGate,
            {"name": name, "evidence_ids": tuple(evidence_ids)},
            field="gate_id",
            prefix="finance_v26_artifact_backed_static_gate:",
        ),
    )


def _static_audit(
    *,
    authorization: models.PreflightAuthorization,
    freeze: models.PredecessorFreezeAudit,
    contract_audit: models.OutcomeContractAudit,
    factorization: models.TerminalValidityFactorizationAudit,
    admission: models.EmpiricalAdmissionAudit,
    locus: models.FailureLocusReconstructionAudit,
    artifacts: models.ArtifactByteAuthenticityAudit,
    parents: models.ParentRevalidationAudit,
    evidence_dag: models.ScriptedEvidenceDagAudit,
) -> models.StaticAudit:
    gates = (
        _gate("exact_v26_182_authorization", authorization.authorization_id),
        _gate("immutable_predecessor_freeze", freeze.audit_id),
        _gate("artifact_backed_contract", contract_audit.audit_id),
        _gate("completed_validity_factorized", factorization.audit_id),
        _gate("diagnostic_empirical_isolation", admission.audit_id),
        _gate("failure_locus_reconstructed", locus.audit_id),
        _gate("raw_result_bytes_bound", artifacts.audit_id),
        _gate("registry_revalidated", parents.audit_id),
        _gate("contract_revalidated", parents.audit_id),
        _gate("manifest_job_revalidated", parents.audit_id),
        _gate("runner_revalidated", parents.audit_id),
        _gate("exact_scripted_evidence_dag", evidence_dag.audit_id),
        _gate("zero_empirical_denominator", evidence_dag.audit_id, admission.audit_id),
        _gate("zero_provider_calls", authorization.authorization_id),
    )
    return cast(
        models.StaticAudit,
        models.make_identity_model(
            models.StaticAudit,
            {"gates": gates, "gate_count": len(gates), "passed_gate_count": len(gates)},
            field="audit_id",
            prefix="finance_v26_artifact_backed_static_audit:",
        ),
    )


def _transition(
    *,
    authorization: models.PreflightAuthorization,
    freeze: models.PredecessorFreezeAudit,
    contract_audit: models.OutcomeContractAudit,
    factorization: models.TerminalValidityFactorizationAudit,
    admission: models.EmpiricalAdmissionAudit,
    locus: models.FailureLocusReconstructionAudit,
    artifacts: models.ArtifactByteAuthenticityAudit,
    parents: models.ParentRevalidationAudit,
    evidence_dag: models.ScriptedEvidenceDagAudit,
    static: models.StaticAudit,
) -> models.ProspectiveTransition:
    return cast(
        models.ProspectiveTransition,
        models.make_identity_model(
            models.ProspectiveTransition,
            {
                "authorization_id": authorization.authorization_id,
                "predecessor_freeze_id": freeze.audit_id,
                "contract_audit_id": contract_audit.audit_id,
                "factorization_audit_id": factorization.audit_id,
                "admission_audit_id": admission.audit_id,
                "locus_audit_id": locus.audit_id,
                "artifact_audit_id": artifacts.audit_id,
                "parent_audit_id": parents.audit_id,
                "evidence_dag_audit_id": evidence_dag.audit_id,
                "static_audit_id": static.audit_id,
            },
            field="transition_id",
            prefix="finance_v26_artifact_backed_outcome_transition:",
        ),
    )


def _report(
    *,
    authorization: models.PreflightAuthorization,
    freeze: models.PredecessorFreezeAudit,
    contract_audit: models.OutcomeContractAudit,
    factorization: models.TerminalValidityFactorizationAudit,
    admission: models.EmpiricalAdmissionAudit,
    locus: models.FailureLocusReconstructionAudit,
    artifacts: models.ArtifactByteAuthenticityAudit,
    parents: models.ParentRevalidationAudit,
    evidence_dag: models.ScriptedEvidenceDagAudit,
    static: models.StaticAudit,
    transition: models.ProspectiveTransition,
) -> models.PreflightReport:
    controls = (
        *admission.controls,
        *locus.controls,
        *artifacts.controls,
        *parents.controls,
    )
    return cast(
        models.PreflightReport,
        models.make_identity_model(
            models.PreflightReport,
            {
                "run_id": RUN_ID,
                "authorization_id": authorization.authorization_id,
                "predecessor_freeze_id": freeze.audit_id,
                "contract_id": contract_audit.contract.contract_id,
                "factorization_audit_id": factorization.audit_id,
                "admission_audit_id": admission.audit_id,
                "locus_audit_id": locus.audit_id,
                "artifact_audit_id": artifacts.audit_id,
                "parent_audit_id": parents.audit_id,
                "evidence_dag_audit_id": evidence_dag.audit_id,
                "static_audit_id": static.audit_id,
                "transition_id": transition.transition_id,
                "fully_rehashed_negative_control_count": sum(
                    item.fully_rehashed for item in controls
                ),
                "negative_control_rejection_count": len(controls),
            },
            field="report_id",
            prefix="finance_v26_artifact_backed_outcome_preflight_report:",
        ),
    )


def _manifest(payloads: dict[str, bytes]) -> models.ArtifactManifest:
    bindings = tuple(
        models.FileBinding(
            relative_path=name,
            sha256=hashlib.sha256(payload).hexdigest(),
            byte_count=len(payload),
            source_kind=(
                "scripted_raw_artifact"
                if name.startswith("raw--")
                else (
                    "scripted_result_artifact"
                    if name.startswith("result--")
                    else "v26_186_formal_artifact"
                )
            ),
        )
        for name, payload in sorted(payloads.items())
    )
    artifact_root = canonical_hash(
        [item.model_dump(mode="json", warnings=False) for item in bindings],
        prefix="finance_v26_artifact_backed_artifact_root:",
    )
    return cast(
        models.ArtifactManifest,
        models.make_identity_model(
            models.ArtifactManifest,
            {
                "artifact_root": artifact_root,
                "files": bindings,
                "file_count": len(bindings),
                "total_byte_count": sum(item.byte_count for item in bindings),
            },
            field="manifest_id",
            prefix="finance_v26_artifact_backed_artifact_manifest:",
        ),
    )


def build(
    *,
    package_root: Path,
    output_dir: Path,
    source_archive: Path,
    source_commit: str,
    source_tree: str,
) -> models.BuildProducts:
    root = _resolve_package_root(package_root)
    frozen = _load_frozen_inputs(root)
    authorization = _authorization(
        frozen=frozen,
        source_commit=source_commit,
        source_tree=source_tree,
        source_archive=source_archive,
    )
    freeze = _freeze(package_root=root, frozen=frozen, authorization=authorization)
    contract, contract_audit = _contract(
        frozen=frozen,
        authorization=authorization,
        freeze=freeze,
    )
    with tempfile.TemporaryDirectory(prefix="v26-186-scripted-artifacts-") as temporary:
        artifact_root = Path(temporary)
        catalogs = _scripted_catalogs(
            artifact_root=artifact_root,
            frozen=frozen,
            contract=contract,
        )
        factorization = _factorization(frozen=frozen, contract=contract)
        locus = _locus_audit(
            artifact_root=artifact_root,
            frozen=frozen,
            contract=contract,
            catalogs=catalogs,
        )
        artifacts = _artifact_audit(
            artifact_root=artifact_root,
            frozen=frozen,
            contract=contract,
            catalogs=catalogs,
        )
        admission = _admission_audit(frozen=frozen, contract=contract)
        parents = _parent_audit(
            artifact_root=artifact_root,
            frozen=frozen,
            contract=contract,
            catalogs=catalogs,
        )
        evidence_dag = _evidence_dag(contract=contract, catalogs=catalogs)
        static = _static_audit(
            authorization=authorization,
            freeze=freeze,
            contract_audit=contract_audit,
            factorization=factorization,
            admission=admission,
            locus=locus,
            artifacts=artifacts,
            parents=parents,
            evidence_dag=evidence_dag,
        )
        transition = _transition(
            authorization=authorization,
            freeze=freeze,
            contract_audit=contract_audit,
            factorization=factorization,
            admission=admission,
            locus=locus,
            artifacts=artifacts,
            parents=parents,
            evidence_dag=evidence_dag,
            static=static,
        )
        report = _report(
            authorization=authorization,
            freeze=freeze,
            contract_audit=contract_audit,
            factorization=factorization,
            admission=admission,
            locus=locus,
            artifacts=artifacts,
            parents=parents,
            evidence_dag=evidence_dag,
            static=static,
            transition=transition,
        )
        payloads = {
            "authorization.json": _canonical_bytes(authorization),
            "predecessor_freeze.json": _canonical_bytes(freeze),
            "artifact_backed_outcome_contract.json": _canonical_bytes(contract_audit),
            "terminal_validity_factorization_audit.json": _canonical_bytes(factorization),
            "empirical_admission_audit.json": _canonical_bytes(admission),
            "failure_locus_reconstruction_audit.json": _canonical_bytes(locus),
            "artifact_byte_authenticity_audit.json": _canonical_bytes(artifacts),
            "parent_revalidation_audit.json": _canonical_bytes(parents),
            "scripted_evidence_catalog.json": _canonical_bytes(
                {"bundles": catalogs.bundles, "evaluation": catalogs.evaluation}
            ),
            "scripted_evidence_dag_audit.json": _canonical_bytes(evidence_dag),
            "static_audit.json": _canonical_bytes(static),
            "prospective_transition.json": _canonical_bytes(transition),
            "report.json": _canonical_bytes(report),
        }
        for path in artifact_root.iterdir():
            if not path.is_file() or path.is_symlink():
                raise ValueError("scripted artifact root contains a non-regular member")
            if path.name in payloads:
                raise ValueError("scripted artifact collides with a formal detail filename")
            payloads[path.name] = path.read_bytes()
        manifest = _manifest(payloads)
        payloads["artifact_manifest.json"] = _canonical_bytes(manifest)
        write_immutable_artifact_directory(output_dir, payloads)
    return models.BuildProducts(
        authorization=authorization,
        freeze=freeze,
        contract_audit=contract_audit,
        factorization=factorization,
        admission=admission,
        locus=locus,
        artifacts=artifacts,
        parents=parents,
        evidence_dag=evidence_dag,
        static=static,
        transition=transition,
        report=report,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--package-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--source-archive", type=Path, required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--source-tree", required=True)
    args = parser.parse_args()
    products = build(
        package_root=args.package_root,
        output_dir=args.output_dir,
        source_archive=args.source_archive,
        source_commit=args.source_commit,
        source_tree=args.source_tree,
    )
    print(products.report.model_dump_json())


if __name__ == "__main__":
    main()
