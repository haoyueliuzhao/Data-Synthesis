from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
from collections import Counter
from pathlib import Path
from typing import Any, Final, cast

from pydantic import BaseModel

from trusted_synthesis.core.task import fresh_artifact_backed_outcome_authority as authority
from trusted_synthesis.core.task import (
    fresh_artifact_backed_terminal_to_outcome_integration as integration,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_artifact_backed_terminal_to_outcome_online_execution_models as v200_models,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_artifact_backed_terminal_to_outcome_postrun_independent_audit_models as models,
)

RUN_ID: Final = (
    "finance_v26_201_fresh_artifact_backed_terminal_to_outcome_postrun_"
    "independent_audit_v1_20260902"
)
OUTPUT_DIR: Final = f"artifacts/vtdo_experiment/{RUN_ID}"
V200_DIR: Final = (
    "artifacts/vtdo_experiment/"
    "finance_v26_200_fresh_artifact_backed_terminal_to_outcome_exact_192_job_"
    "online_execution_v1_20260901"
)
V200_SUMMARY_ID: Final = (
    "finance_v26_200_online_execution_summary:"
    "efe14591ff3551b83cbcc4e4b39e396780b13e65f92ebe8e5903d51a3bbeb4ef"
)
V200_RUN_START_ID: Final = (
    "finance_v26_200_online_run_start_receipt:"
    "c0320a61e0103fcbe81a0678b4f6ad11d6e7d9f28d474da6f2b10403fa66145e"
)
V200_ARTIFACT_MANIFEST_ID: Final = (
    "finance_v26_200_execution_artifact_manifest:"
    "e50288c4c7e2bf1b13e89e1ecef3079ab3736521450ad243a9017f216606d1a6"
)
V200_ARTIFACT_ROOT: Final = (
    "finance_v26_200_execution_artifact_root:"
    "e95f87d91231f1ab22df15742661c535052b87f5b4fbbc84c32337e0d4b023a5"
)
V200_SOURCE_COMMIT: Final = "e3d1b8d2922e44a5edde0d63433a8f3781edecef"
V200_SOURCE_TREE: Final = "738c30f294cca2097baffed3a5e17e7c298fab80"
V200_AUTHORIZATION_ID: Final = (
    "fresh_terminal_to_outcome_exact_online_execution_authorization:"
    "42aaca7f87e5766e7338c04a22d0eb49132a718e46506f4d1ca4459811cce600"
)


def _load(path: Path) -> Any:
    return json.loads(path.read_bytes())


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _canonical_json(value: Any) -> str:
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json", warnings=False)
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _write_no_replace(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = (_canonical_json(value) + "\n").encode("utf-8")
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "wb", closefd=False) as stream:
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
    finally:
        os.close(descriptor)


def _safe(identifier: str) -> str:
    return hashlib.sha256(identifier.encode("utf-8")).hexdigest()


def _git_identity(repository_root: Path) -> tuple[str, str]:
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repository_root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    tree = subprocess.run(
        ["git", "rev-parse", "HEAD^{tree}"],
        cwd=repository_root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    return commit, tree


def _independent_terminal(
    raw: v200_models.EmpiricalIntegratedRawPayload,
) -> integration.ReachableTerminalKind:
    evidence = raw.terminal_evidence
    exception_map: dict[integration.ObservedExceptionType, integration.ReachableTerminalKind] = {
        "ProviderNoPayloadError": "provider_failure_no_payload",
        "ProviderTransportError": "provider_transport_failure",
        "PrivacyProjectionRejected": "privacy_rejection",
        "ResourceBudgetError": "resource_budget_exhausted",
        "InstrumentIntegrityError": "instrument_failure",
        "ProviderIdentityIntegrityError": "provider_identity_failure",
        "ThinkingIntegrityError": "thinking_integrity_failure",
        "UsageIntegrityError": "usage_integrity_failure",
    }
    if evidence.exception_type is not None:
        return exception_map[evidence.exception_type]
    payload = evidence.public_terminal_projection
    if payload is None:
        raise ValueError("v26.201 Raw lacks terminal source evidence")
    if payload.phase == "primary_action":
        if payload.response_abi_valid is False:
            return "first_response_abi_invalid"
        if payload.action_reference_valid is False:
            return "first_action_reference_invalid"
    elif payload.phase == "correction_action":
        if payload.correction_response_abi_valid is False:
            return "correction_response_abi_invalid"
        if payload.correction_action_reference_valid is False:
            return "correction_action_reference_invalid"
        if payload.correction_state_precondition_valid is False:
            return "correction_attempt_typed_invalid"
    elif payload.final_response_abi_valid is False:
        return "final_response_abi_invalid"
    elif payload.final_qualified_valid is True:
        return "completed_qualified"
    elif payload.task_verifier_invoked:
        return "completed_invalid"
    raise ValueError("v26.201 independent terminal reconstruction is non-total")


_FAILURE_STAGE: Final[dict[integration.ReachableTerminalKind, authority.FailureStage]] = {
    "completed_invalid": "base_answer",
    "first_response_abi_invalid": "action_abi",
    "correction_response_abi_invalid": "action_abi",
    "first_action_reference_invalid": "action_reference",
    "correction_action_reference_invalid": "action_reference",
    "correction_attempt_typed_invalid": "state_precondition",
    "final_response_abi_invalid": "final_abi",
    "provider_failure_no_payload": "provider",
    "provider_transport_failure": "transport",
    "privacy_rejection": "privacy",
    "resource_budget_exhausted": "resource",
    "instrument_failure": "instrument",
    "provider_identity_failure": "model_identity",
    "thinking_integrity_failure": "thinking",
    "usage_integrity_failure": "usage",
}


def _independent_loci(
    *,
    terminal: integration.ReachableTerminalKind,
    component_key: str,
    source_descriptor_id: str,
) -> tuple[authority.FreshFailureLocus, ...]:
    if terminal == "completed_qualified":
        return ()
    return (
        cast(
            authority.FreshFailureLocus,
            authority.make_identity_model(
                authority.FreshFailureLocus,
                {
                    "stage": _FAILURE_STAGE[terminal],
                    "component_key": component_key,
                    "attempt_index": (
                        1
                        if terminal.startswith("correction_")
                        or terminal == "correction_attempt_typed_invalid"
                        else 0
                    ),
                    "reason_code": terminal,
                    "source_descriptor_id": source_descriptor_id,
                },
                field="locus_id",
                prefix="fresh_kernel_failure_locus:",
            ),
        ),
    )


def _shape_label(shape: tuple[str, ...]) -> str:
    return "|".join(shape)


def build(
    *,
    repository_root: Path,
    output_dir: Path,
) -> dict[str, Any]:
    repository_root = repository_root.resolve()
    package_root = repository_root / "trusted_data_synthesis"
    v200_root = package_root / V200_DIR
    output_dir = output_dir.resolve()
    if output_dir.exists():
        raise FileExistsError(f"v26.201 output already exists: {output_dir}")
    files = tuple(path for path in v200_root.rglob("*") if path.is_file())
    if len(files) != 1154 or sum(path.stat().st_size for path in files) != 4_304_518:
        raise ValueError("v26.200 execution directory geometry differs")
    summary = v200_models.OnlineExecutionSummary.model_validate(
        _load(v200_root / "execution_summary.json")
    )
    run_start = v200_models.RunStartReceipt.model_validate(
        _load(v200_root / "run_start_receipt.json")
    )
    manifest = v200_models.ExecutionArtifactManifest.model_validate(
        _load(v200_root / "execution_artifact_manifest.json")
    )
    if (
        summary.summary_id != V200_SUMMARY_ID
        or run_start.receipt_id != V200_RUN_START_ID
        or manifest.manifest_id != V200_ARTIFACT_MANIFEST_ID
        or manifest.artifact_root != V200_ARTIFACT_ROOT
        or run_start.execution_source_commit != V200_SOURCE_COMMIT
        or run_start.execution_source_tree != V200_SOURCE_TREE
        or summary.authorization_id != V200_AUTHORIZATION_ID
        or summary.execution_status != "completed"
        or run_start.manifest_execution_ordinal != 1
        or not run_start.authorization_consumed
    ):
        raise ValueError("v26.200 execution authority differs")
    actual = {
        path.relative_to(v200_root).as_posix(): path
        for path in files
        if path.name != "execution_artifact_manifest.json"
    }
    member_map = {item.relative_path: item for item in manifest.members}
    if set(actual) != set(member_map) or len(member_map) != 1153:
        raise ValueError("v26.200 Artifact Manifest path set differs")
    for name, member in member_map.items():
        path = actual[name]
        if _sha256(path) != member.sha256 or path.stat().st_size != member.byte_count:
            raise ValueError(f"v26.200 Artifact Manifest member differs:{name}")
    freeze = cast(
        models.V200ExecutionFreeze,
        models.make_identity(
            models.V200ExecutionFreeze,
            {
                "run_start_receipt_id": run_start.receipt_id,
                "execution_summary_id": summary.summary_id,
                "execution_artifact_manifest_id": manifest.manifest_id,
                "execution_artifact_root": manifest.artifact_root,
                "online_authorization_id": summary.authorization_id,
                "manifest_id": summary.manifest_id,
                "execution_source_commit": run_start.execution_source_commit,
                "execution_source_tree": run_start.execution_source_tree,
            },
            field="freeze_id",
            prefix="finance_v26_201_v200_execution_freeze:",
        ),
    )

    record_paths = tuple(sorted((v200_root / "job_records").glob("*.json")))
    if len(record_paths) != 192:
        raise ValueError("v26.200 Job-record denominator differs")
    rows: list[models.IndependentJobAuditRow] = []
    terminal_counts: Counter[str] = Counter()
    shape_counts: Counter[str] = Counter()
    http_200 = model_complete = thinking_present = thinking_tokens = usage_complete = 0
    exact_abi = projections = privacy = reasoning_budget = total_tokens = 0
    for record_path in record_paths:
        record = v200_models.OnlineJobExecutionRecord.model_validate(_load(record_path))
        raw_path = v200_root / "fresh_outcome_artifacts" / record.bundle.raw.artifact_relative_path
        result_path = (
            v200_root / "fresh_outcome_artifacts" / record.bundle.result.artifact_relative_path
        )
        raw_bytes = raw_path.read_bytes()
        result_bytes = result_path.read_bytes()
        raw = v200_models.EmpiricalIntegratedRawPayload.model_validate_json(raw_bytes)
        result = authority.FreshJobResultPayload.model_validate_json(result_bytes)
        reconstructed = _independent_terminal(raw)
        loci = _independent_loci(
            terminal=reconstructed,
            component_key=raw.terminal_evidence.component_key,
            source_descriptor_id=record.bundle.result.result_id,
        )
        raw_match = (
            _sha256_bytes(raw_bytes) == record.bundle.raw.artifact_sha256
            and len(raw_bytes) == record.bundle.raw.artifact_byte_count
        )
        result_match = (
            _sha256_bytes(result_bytes) == record.bundle.result.artifact_sha256
            and len(result_bytes) == record.bundle.result.artifact_byte_count
        )
        parent_match = (
            raw.job_id == record.job_id
            and result.job_id == record.job_id
            and result.raw_execution_id == record.bundle.raw.raw_execution_id
            and record.bundle.result.raw_execution_id == record.bundle.raw.raw_execution_id
        )
        trace_match = (
            record.bundle.trace.job_id == record.job_id
            and record.bundle.trace.raw_execution_id == record.bundle.raw.raw_execution_id
            and record.bundle.trace.result_id == record.bundle.result.result_id
        )
        outcome_match = (
            record.bundle.row.job_id == record.job_id
            and record.bundle.row.raw_execution_id == record.bundle.raw.raw_execution_id
            and record.bundle.row.result_id == record.bundle.result.result_id
            and record.bundle.row.trace_id == record.bundle.trace.trace_id
            and record.bundle.row.terminal_kind == reconstructed
        )
        if not all(
            (
                raw_match,
                result_match,
                parent_match,
                trace_match,
                outcome_match,
                tuple(loci) == record.bundle.trace.failure_loci,
                record.terminal_kind == reconstructed,
                raw_path.stat().st_mtime_ns <= result_path.stat().st_mtime_ns,
            )
        ):
            raise ValueError(f"v26.201 Job reconstruction differs:{record.job_id}")
        telemetry = raw.provider_telemetry
        if len(telemetry) != 1 or raw.provider_calls != 1:
            raise ValueError("v26.200 Provider-call denominator differs")
        item = telemetry[0]
        http_ok = item.get("http_status") == 200
        model_ok = (
            item.get("model_requested")
            == item.get("model_selected")
            == item.get("response_model")
            == "deepseek-v4-flash"
        )
        thinking_ok = item.get("reasoning_content_present") is True
        thinking_token_ok = item.get("reasoning_tokens") is not None
        usage_ok = all(
            item.get(key) is not None
            for key in ("prompt_tokens", "completion_tokens", "total_tokens")
        )
        if not all((http_ok, model_ok, thinking_ok, thinking_token_ok, usage_ok)):
            raise ValueError("v26.200 Provider telemetry integrity differs")
        http_200 += 1
        model_complete += 1
        thinking_present += 1
        thinking_tokens += 1
        usage_complete += 1
        total_tokens += int(item["total_tokens"])
        reasoning_budget += item.get("error_type") == "ReasoningBudgetExhaustedError"
        projection_path = (
            v200_root / "kernel_artifacts" / "projections" / _safe(record.job_id) / "000.json"
        )
        shape: tuple[str, ...] | None = None
        crossed = False
        if projection_path.is_file():
            projection = _load(projection_path)
            projections += 1
            privacy += projection.get("status") == "privacy_rejected"
            payload = projection.get("payload")
            if not isinstance(payload, dict):
                raise ValueError("v26.200 public Projection payload differs")
            shape = tuple(sorted(payload))
            shape_counts[_shape_label(shape)] += 1
            crossed = set(payload) == {
                "state_id",
                "action_id",
                "decision_kind",
                "protocol",
            }
            exact_abi += crossed
        terminal_counts[reconstructed] += 1
        rows.append(
            cast(
                models.IndependentJobAuditRow,
                models.make_identity(
                    models.IndependentJobAuditRow,
                    {
                        "job_id": record.job_id,
                        "package_id": record.package_id,
                        "replica_index": record.replica_index,
                        "terminal_kind": record.terminal_kind,
                        "independently_reconstructed_terminal_kind": reconstructed,
                        "raw_execution_id": record.bundle.raw.raw_execution_id,
                        "result_id": record.bundle.result.result_id,
                        "trace_id": record.bundle.trace.trace_id,
                        "outcome_row_id": record.bundle.row.row_id,
                        "exact_action_abi_crossed": crossed,
                        "public_payload_key_shape": shape,
                    },
                    field="audit_row_id",
                    prefix="finance_v26_201_independent_job_audit_row:",
                ),
            )
        )
    row_tuple = tuple(sorted(rows, key=lambda item: item.job_id))
    reconstruction = cast(
        models.ByteReconstructionAudit,
        models.make_identity(
            models.ByteReconstructionAudit,
            {"v200_freeze_id": freeze.freeze_id, "rows": row_tuple},
            field="audit_id",
            prefix="finance_v26_201_byte_reconstruction_audit:",
        ),
    )
    response = cast(
        models.ResponseInterfaceAudit,
        models.make_identity(
            models.ResponseInterfaceAudit,
            {
                "byte_reconstruction_audit_id": reconstruction.audit_id,
                "terminal_partition": dict(sorted(terminal_counts.items())),
                "public_payload_key_shape_counts": dict(sorted(shape_counts.items())),
            },
            field="audit_id",
            prefix="finance_v26_201_response_interface_audit:",
        ),
    )
    observed = (
        http_200,
        model_complete,
        thinking_present,
        thinking_tokens,
        usage_complete,
        projections,
        privacy,
        exact_abi,
        reasoning_budget,
        total_tokens,
    )
    expected = (192, 192, 192, 192, 192, 188, 0, 0, 4, 1_824_320)
    if observed != expected:
        raise ValueError(f"v26.201 response audit aggregate differs:{observed}")
    decision = cast(
        models.PostrunIndependentAuditDecision,
        models.make_identity(
            models.PostrunIndependentAuditDecision,
            {
                "v200_freeze_id": freeze.freeze_id,
                "byte_reconstruction_audit_id": reconstruction.audit_id,
                "response_interface_audit_id": response.audit_id,
                "decision": "v26_200_exact_online_execution_accepted_as_complete",
            },
            field="decision_id",
            prefix="finance_v26_201_postrun_independent_audit_decision:",
        ),
    )
    transition = cast(
        models.ProspectiveTransition,
        models.make_identity(
            models.ProspectiveTransition,
            {"decision_id": decision.decision_id},
            field="transition_id",
            prefix="finance_v26_201_transition:",
        ),
    )
    source_commit, source_tree = _git_identity(repository_root)
    output_dir.mkdir(parents=True, exist_ok=False)
    _write_no_replace(output_dir / "v26_200_execution_freeze.json", freeze)
    _write_no_replace(output_dir / "byte_reconstruction_audit.json", reconstruction)
    _write_no_replace(output_dir / "response_interface_audit.json", response)
    _write_no_replace(output_dir / "independent_audit_decision.json", decision)
    _write_no_replace(output_dir / "prospective_transition.json", transition)
    report = {
        "run_id": RUN_ID,
        "consumed_stage": models.CONSUMED_STAGE,
        "source_commit": source_commit,
        "source_tree": source_tree,
        "v200_freeze_id": freeze.freeze_id,
        "byte_reconstruction_audit_id": reconstruction.audit_id,
        "response_interface_audit_id": response.audit_id,
        "decision_id": decision.decision_id,
        "transition_id": transition.transition_id,
        "v200_execution_status": summary.execution_status,
        "exact_job_count": 192,
        "raw_result_trace_outcome_counts": [192, 192, 192, 192],
        "terminal_partition": dict(sorted(terminal_counts.items())),
        "provider_calls_in_v200": 192,
        "provider_calls_during_audit": 0,
        "total_usage_tokens": total_tokens,
        "exact_action_abi_count": exact_abi,
        "empirical_estimate_count": 0,
        "mapper_state_frequency_contribution_vtdo_rows": 0,
        "decision": decision.decision,
        "next_decision": transition.next_decision,
        "schema_version": models.SCHEMA_VERSION,
    }
    _write_no_replace(output_dir / "report.json", report)
    _write_no_replace(
        output_dir / "source_identity.json",
        {"source_commit": source_commit, "source_tree": source_tree},
    )
    members = tuple(
        models.ArtifactMember(
            relative_path=path.relative_to(output_dir).as_posix(),
            sha256=_sha256(path),
            byte_count=path.stat().st_size,
        )
        for path in sorted(item for item in output_dir.rglob("*") if item.is_file())
    )
    artifact_manifest = models.artifact_manifest(run_id=RUN_ID, members=members)
    _write_no_replace(output_dir / "artifact_manifest.json", artifact_manifest)
    return {
        **report,
        "artifact_manifest_id": artifact_manifest.manifest_id,
        "artifact_root": artifact_manifest.artifact_root,
    }


def _default_output(package_root: Path) -> Path:
    return package_root / OUTPUT_DIR


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository-root", type=Path, default=Path.cwd())
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    repository_root = args.repository_root.resolve()
    package_root = repository_root / "trusted_data_synthesis"
    output_dir = (args.output_dir or _default_output(package_root)).resolve()
    print(_canonical_json(build(repository_root=repository_root, output_dir=output_dir)))


if __name__ == "__main__":
    main()
