# ruff: noqa: E501
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from typing import Any, Final, Literal, cast

from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_exact_v209_parent_bound_online_execution as prior,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_exact_v209_parent_bound_online_execution_repair_models as models,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_repaired_full_condition_final_request_contract_continuity_repair_preflight_models as v209_models,
)
from trusted_synthesis.runtime.agent.prospective_two_stage_stage1_client import (
    require_stage_one_model_config,
)
from trusted_synthesis.runtime.agent.schema import AgentModelConfig

RUN_ID: Final = (
    "finance_v26_226_fresh_exact_v209_parent_bound_postresponse_serializer_repair_"
    "exact_192_job_replacement_online_execution_v1_20260903"
)
PREFLIGHT_RUN_ID: Final = (
    "finance_v26_225_postrun_independent_audit_and_postresponse_serializer_"
    "repair_preflight_v1_20260904"
)
PREFLIGHT_DIR: Final = f"trusted_data_synthesis/artifacts/vtdo_experiment/{PREFLIGHT_RUN_ID}"
OUTPUT_DIR: Final = f"trusted_data_synthesis/artifacts/vtdo_experiment/{RUN_ID}"
LEDGER_DIR: Final = (
    "trusted_data_synthesis/artifacts/vtdo_experiment/authorization_consumption_ledger"
)
V224_DIR: Final = prior.OUTPUT_DIR
V224_MANIFEST_SHA256: Final = "f85a1ea86c4e581ad8f94bae9af9fbc8d28638cc861b1ce138639949278fade1"
MAX_WORKERS: Final = 8
IMPLEMENTATION_PATHS: Final = (
    "trusted_data_synthesis/src/trusted_synthesis/experiments/vtdo_experiment/"
    "phase1_v26_fresh_exact_v209_parent_bound_online_execution.py",
    "trusted_data_synthesis/src/trusted_synthesis/experiments/vtdo_experiment/"
    "phase1_v26_fresh_exact_v209_parent_bound_online_execution_repair.py",
    "trusted_data_synthesis/src/trusted_synthesis/experiments/vtdo_experiment/"
    "phase1_v26_fresh_exact_v209_parent_bound_online_execution_repair_models.py",
    "trusted_data_synthesis/tests/"
    "test_v26_fresh_exact_v209_parent_bound_online_execution_repair.py",
)
PREFLIGHT_GATES: Final = (
    "P0_EXACT_V224_FAILURE_RECONSTRUCTION_PASS",
    "P1_TYPED_DICT_SERIALIZATION_REPAIR_PASS",
    "P2_MOCK_SUCCESS_PROVIDER_JOURNAL_AND_FIVE_LAYERS_PASS",
    "P3_MOCK_ERROR_PROVIDER_JOURNAL_PASS",
    "P4_EXACT_PARENT_AND_192_JOB_BINDING_PASS",
    "P5_EXPECTED_BYTE_AND_FULL_REHASH_REJECTION_PASS",
    "P6_ZERO_REAL_PROVIDER_AND_CREDENTIAL_BOUNDARY_PASS",
)


@dataclass(frozen=True)
class PreparedReplacement:
    repository_root: Path
    package_root: Path
    output_dir: Path
    ledger_path: Path
    postrun_audit: models.PostrunRepairAudit
    repair_control_audit: models.RepairControlAudit
    authorization: models.ConditionalReplacementAuthorization
    authorization_bytes: bytes
    preparation: models.ReplacementPreparation
    catalog: v209_models.ExecutableRunnerPackageCatalog
    manifest: v209_models.ExecutableDevelopmentManifest
    implementation: v209_models.ImplementationBinding
    frozen_parents: prior.v209.FrozenParents
    runtime: prior.v188.PreparedExecution
    config: AgentModelConfig
    bindings: prior.FrozenBindings


@dataclass(frozen=True)
class RepairPreflightObjects:
    source_identity: models.RepairPreflightSourceIdentity
    postrun_audit: models.PostrunRepairAudit
    repair_control_audit: models.RepairControlAudit
    authorization: models.ConditionalReplacementAuthorization
    authorization_bytes: bytes
    preparation: models.ReplacementPreparation
    attack_audit: models.AuthorizationAttackAudit
    gate: models.RepairPreflightGateEvaluation
    decision: models.RepairPreflightDecision
    transition: models.RepairPreflightTransition
    loaded: dict[str, Any]


def _read_json(path: Path) -> Any:
    return json.loads(path.read_bytes())


def _sha(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _encoded(value: Any) -> bytes:
    return models.canonical_bytes(value) + b"\n"


def _git_show_bytes(repository_root: Path, commit: str, path: str) -> bytes:
    return subprocess.run(
        ("git", "show", f"{commit}:{path}"),
        cwd=repository_root,
        check=True,
        capture_output=True,
    ).stdout


def _source_identity(
    repository_root: Path, source_commit: str, source_tree: str
) -> models.RepairPreflightSourceIdentity:
    actual_tree = subprocess.run(
        ("git", "rev-parse", f"{source_commit}^{{tree}}"),
        cwd=repository_root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    if actual_tree != source_tree:
        raise ValueError("repair source commit-to-tree relation differs")
    members = tuple(
        models.SourceMember(
            relative_path=path,
            sha256=_sha(payload),
            byte_count=len(payload),
        )
        for path in sorted(IMPLEMENTATION_PATHS)
        for payload in (_git_show_bytes(repository_root, source_commit, path),)
    )
    return models.make_identity(
        models.RepairPreflightSourceIdentity,
        {
            "source_commit": source_commit,
            "source_tree": source_tree,
            "implementation_members": members,
            "implementation_member_set_sha256": models.canonical_sha256(
                tuple(item.model_dump(mode="json", warnings=False) for item in members)
            ),
        },
        field="source_id",
        prefix="finance_v26_225_repair_source_identity:",
    )


def _verify_source_overlay(
    repository_root: Path, source: models.RepairPreflightSourceIdentity
) -> None:
    changed = subprocess.run(
        ("git", "status", "--porcelain", "--untracked-files=no"),
        cwd=repository_root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    if changed.strip():
        raise ValueError("replacement requires a clean tracked worktree")
    ancestor = subprocess.run(
        ("git", "merge-base", "--is-ancestor", source.source_commit, "HEAD"),
        cwd=repository_root,
        check=False,
    )
    if ancestor.returncode != 0:
        raise ValueError("repair implementation commit is not an ancestor of HEAD")
    for member in source.implementation_members:
        current = (repository_root / member.relative_path).read_bytes()
        committed = _git_show_bytes(repository_root, source.source_commit, member.relative_path)
        if (
            current != committed
            or _sha(current) != member.sha256
            or len(current) != member.byte_count
        ):
            raise ValueError(f"repair implementation member differs:{member.relative_path}")
    overlays = tuple(
        item
        for item in subprocess.run(
            ("git", "diff", "--name-only", f"{source.source_commit}..HEAD"),
            cwd=repository_root,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.splitlines()
        if item
    )
    allowed_exact = {
        "trusted_data_synthesis/docs/current_project_status.md",
        "trusted_data_synthesis/docs/"
        "finance_v26_225_postrun_independent_audit_and_postresponse_serializer_"
        "repair_preflight.md",
    }
    allowed_prefix = f"{PREFLIGHT_DIR}/"
    if any(item not in allowed_exact and not item.startswith(allowed_prefix) for item in overlays):
        raise ValueError("record overlay contains a non-authorized path")


def _verify_v224(repository_root: Path) -> models.PostrunRepairAudit:
    root = repository_root / V224_DIR
    files = {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file()
    }
    if len(files) != 398 or sum(len(item) for item in files.values()) != 680_947:
        raise ValueError("v26.224 formal execution geometry differs")
    manifest_bytes = files["execution_artifact_manifest.json"]
    if _sha(manifest_bytes) != V224_MANIFEST_SHA256:
        raise ValueError("v26.224 Manifest bytes differ")
    manifest = prior.models.ArtifactManifest.model_validate_json(manifest_bytes)
    payloads = {
        path: payload
        for path, payload in files.items()
        if path != "execution_artifact_manifest.json"
    }
    rebuilt = prior.models.artifact_manifest(prior.RUN_ID, payloads)
    if prior.models.canonical_bytes(manifest) != prior.models.canonical_bytes(rebuilt):
        raise ValueError("v26.224 Manifest independent rebuild differs")
    summary = prior.models.ExecutionSummary.model_validate_json(files["execution_summary.json"])
    transition = prior.models.Transition.model_validate_json(files["prospective_transition.json"])
    consumption = prior.models.AuthorizationConsumptionReceipt.model_validate_json(
        files["authorization_consumption_receipt.json"]
    )
    run_start = prior.models.RunStartReceipt.model_validate_json(files["run_start_receipt.json"])
    failures = tuple(
        prior.models.JobFailureRecord.model_validate_json(payload)
        for path, payload in sorted(files.items())
        if path.startswith("job_failures/")
    )
    intents = tuple(
        cast(dict[str, Any], json.loads(payload))
        for path, payload in sorted(files.items())
        if path.endswith("_request_metadata.json")
    )
    exact_job_ids = tuple(sorted(item.job_id for item in failures))
    intent_job_ids = tuple(sorted(str(item["job_id"]) for item in intents))
    exact_failure_text = "builtins:AttributeError:'dict' object has no attribute 'model_dump'"
    frozen_source = prior.subprocess.run(
        (
            "git",
            "show",
            f"{models.V224_SOURCE_COMMIT}:trusted_data_synthesis/src/trusted_synthesis/experiments/"
            "vtdo_experiment/phase1_v26_fresh_exact_v209_parent_bound_online_execution.py",
        ),
        cwd=repository_root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    current_source = (
        repository_root
        / "trusted_data_synthesis/src/trusted_synthesis/experiments/vtdo_experiment/"
        "phase1_v26_fresh_exact_v209_parent_bound_online_execution.py"
    ).read_text(encoding="utf-8")
    response_count = sum(
        path.startswith("provider_calls/") and path.endswith("_response_metadata.json")
        for path in files
    )
    usage_count = sum(
        path.startswith("provider_calls/") and path.endswith("_usage_metadata.json")
        for path in files
    )
    error_count = sum(
        path.startswith("provider_calls/") and path.endswith("_error_metadata.json")
        for path in files
    )
    descriptor_count = sum(
        path.startswith("provider_calls/") and path.endswith("_descriptor.json") for path in files
    )
    five_layer_count = sum(
        path.startswith(prefix)
        for path in files
        for prefix in (
            "evidence/raw/",
            "evidence/result/",
            "evidence/trace/",
            "evidence/outcome/",
            "checkpoints/",
        )
    )
    if (
        manifest.manifest_id != models.V224_MANIFEST_ID
        or manifest.artifact_root != models.V224_ARTIFACT_ROOT
        or summary.summary_id != models.V224_SUMMARY_ID
        or transition.transition_id != models.V224_TRANSITION_ID
        or consumption.receipt_id != models.V224_CONSUMPTION_ID
        or run_start.execution_source_commit != models.V224_SOURCE_COMMIT
        or run_start.execution_source_tree != models.V224_SOURCE_TREE
        or len(failures) != 192
        or len(intents) != 192
        or exact_job_ids != intent_job_ids
        or models.canonical_sha256(exact_job_ids) != prior.models.EXACT_JOB_SET_SHA256
        or {item.job_ordinal for item in failures} != set(range(192))
        or {item.error_sha256 for item in failures} != {models.FAILURE_SHA256}
        or _sha(exact_failure_text.encode("utf-8")) != models.FAILURE_SHA256
        or response_count != 0
        or usage_count != 0
        or error_count != 0
        or descriptor_count != 0
        or five_layer_count != 0
        or summary.provider_call_count != 0
        or summary.failure_record_count != 192
        or summary.execution_status != "incomplete"
        or frozen_source.count('redacted.model_dump(mode="json", warnings=False)') != 2
        or 'redacted.model_dump(mode="json", warnings=False)' in current_source
        or current_source.count("dict(redacted)") != 2
    ):
        raise ValueError("v26.224 independent failure reconstruction differs")
    return models.make_identity(
        models.PostrunRepairAudit,
        {},
        field="audit_id",
        prefix="finance_v26_225_postrun_repair_audit:",
    )


def _load_exact_runtime(repository_root: Path, output_dir: Path) -> dict[str, Any]:
    v209_root = repository_root / prior.V209_DIR
    prior._verify_formal_directory(  # noqa: SLF001
        v209_root,
        file_count=21,
        total_bytes=44_916_386,
        member_count=20,
        member_bytes=44_912_918,
        manifest_id=prior.v223_models.V209_MANIFEST_ID,
        artifact_root=prior.v223_models.V209_ARTIFACT_ROOT,
        manifest_file_sha256=prior.V209_MANIFEST_FILE_SHA256,
    )
    catalog = v209_models.ExecutableRunnerPackageCatalog.model_validate(
        _read_json(v209_root / "executable_runner_package_catalog.json")
    )
    manifest = v209_models.ExecutableDevelopmentManifest.model_validate(
        _read_json(v209_root / "executable_development_manifest.json")
    )
    implementation = v209_models.ImplementationBinding.model_validate(
        _read_json(v209_root / "implementation_binding.json")
    )
    saved_predecessor = cast(dict[str, Any], _read_json(v209_root / "predecessor_freeze.json"))
    parents = prior.v209._predecessor_freeze(  # noqa: SLF001
        repository_root=repository_root,
        authorization_id=str(saved_predecessor["authorization_id"]),
    )
    runtime = prior.v188.prepare_execution(
        package_root=repository_root / "trusted_data_synthesis",
        output_dir=output_dir / "runtime_reserved",
    )
    profile = cast(dict[str, Any], _read_json(repository_root / prior.MODEL_PROFILE))
    config = require_stage_one_model_config(
        AgentModelConfig.model_validate(profile.get("model", profile))
    )
    return {
        "catalog": catalog,
        "manifest": manifest,
        "implementation": implementation,
        "parents": parents,
        "runtime": runtime,
        "config": config,
        "bindings": prior._load_bindings(repository_root),  # noqa: SLF001
    }


class _FakeHttpResponse:
    status = 200

    def __enter__(self) -> _FakeHttpResponse:
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(
            {
                "model": "deepseek-v4-flash",
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {"content": "{}", "reasoning_content": "x"},
                    }
                ],
                "usage": {
                    "prompt_tokens": 10,
                    "completion_tokens": 2,
                    "total_tokens": 12,
                    "completion_tokens_details": {"reasoning_tokens": 1},
                },
            },
            separators=(",", ":"),
        ).encode("utf-8")


def _canonical_file(path: Path, value: Any) -> bytes:
    payload = path.read_bytes()
    if payload != _encoded(value):
        raise ValueError(f"noncanonical persisted Provider evidence:{path}")
    return payload


def _provider_relation_projection(
    *,
    output_dir: Path,
    authorization_id: str,
    run_start_receipt_id: str,
) -> dict[str, Any]:
    provider_root = output_dir / "provider_calls"
    files = tuple(sorted(path for path in provider_root.rglob("*") if path.is_file()))
    intent_paths = tuple(path for path in files if path.name.endswith("_request_metadata.json"))
    descriptor_paths = tuple(path for path in files if path.name.endswith("_descriptor.json"))
    response_paths = tuple(path for path in files if path.name.endswith("_response_metadata.json"))
    error_paths = tuple(path for path in files if path.name.endswith("_error_metadata.json"))
    usage_paths = tuple(path for path in files if path.name.endswith("_usage_metadata.json"))
    recognized = {
        *intent_paths,
        *descriptor_paths,
        *response_paths,
        *error_paths,
        *usage_paths,
    }
    if set(files) != recognized:
        raise ValueError("Provider evidence tree contains an unrecognized file")

    def stem_key(path: Path, suffix: str) -> str:
        relative = path.relative_to(output_dir).as_posix()
        if not relative.endswith(suffix):
            raise ValueError("Provider evidence suffix differs")
        return relative[: -len(suffix)]

    intents = {stem_key(path, "_request_metadata.json"): path for path in intent_paths}
    descriptors = {stem_key(path, "_descriptor.json"): path for path in descriptor_paths}
    if len(intents) != len(intent_paths) or len(descriptors) != len(descriptor_paths):
        raise ValueError("duplicate Provider evidence key")
    orphan_intents = set(intents) - set(descriptors)
    orphan_descriptors = set(descriptors) - set(intents)
    intent_job_ids = tuple(
        sorted({str(cast(dict[str, Any], _read_json(path))["job_id"]) for path in intent_paths})
    )
    relations: list[Any] = []
    invalid = 0
    invalid_reasons: list[str] = []
    for key in sorted(set(intents) & set(descriptors)):
        try:
            intent = cast(dict[str, Any], _read_json(intents[key]))
            _canonical_file(intents[key], intent)
            descriptor = prior.models.ProviderCallDescriptor.model_validate_json(
                descriptors[key].read_bytes()
            )
            _canonical_file(descriptors[key], descriptor)
            safe_job = hashlib.sha256(descriptor.job_id.encode("utf-8")).hexdigest()
            expected_key = f"provider_calls/{safe_job}/call_{descriptor.call_ordinal:02d}"
            if key != expected_key:
                raise ValueError("Provider evidence path differs from Job/call")
            if (
                descriptor.run_start_receipt_id != run_start_receipt_id
                or intent.get("run_start_receipt_id") != run_start_receipt_id
                or intent.get("job_id") != descriptor.job_id
                or intent.get("call_ordinal") != descriptor.call_ordinal
                or intent.get("request_sha256") != descriptor.request_sha256
                or intent.get("request_byte_count", 0) <= 0
                or intent.get("provider_call_authorized") is not True
                or intent.get("retry_authorized") is not False
                or intent.get("raw_request_persisted") is not False
                or _sha(intents[key].read_bytes()) != descriptor.intention_sha256
            ):
                raise ValueError("Provider request intent relation differs")
            kinds = tuple(item.artifact_kind for item in descriptor.artifacts)
            expected_kinds = (
                ("error_metadata", "request_metadata", "usage_metadata")
                if descriptor.status != "succeeded"
                else ("request_metadata", "response_metadata", "usage_metadata")
            )
            if tuple(sorted(kinds)) != expected_kinds or len(set(kinds)) != 3:
                raise ValueError("Provider descriptor artifact partition differs")
            by_kind = {item.artifact_kind: item for item in descriptor.artifacts}
            for kind, artifact in by_kind.items():
                expected_path = f"{key}_{kind}.json"
                actual = output_dir / artifact.relative_path
                if artifact.relative_path != expected_path or not actual.is_file():
                    raise ValueError("Provider artifact path relation differs")
                payload = actual.read_bytes()
                if (
                    artifact.sha256 != _sha(payload)
                    or artifact.byte_count != len(payload)
                    or artifact.provider_call_id != descriptor.provider_call_id
                ):
                    raise ValueError("Provider artifact actual bytes differ")
                parsed = _read_json(actual)
                _canonical_file(actual, parsed)
                if (
                    kind != "request_metadata"
                    and parsed.get("provider_call_id") != descriptor.provider_call_id
                ):
                    raise ValueError("Provider artifact call parent differs")
            request_artifact = by_kind["request_metadata"]
            if request_artifact.relative_path != intents[key].relative_to(output_dir).as_posix():
                raise ValueError("Provider descriptor request artifact differs")
            usage = cast(
                dict[str, Any], _read_json(output_dir / by_kind["usage_metadata"].relative_path)
            )
            telemetry = cast(dict[str, Any], usage.get("telemetry"))
            if (
                telemetry.get("request_hash") != descriptor.request_sha256
                or int(telemetry.get("prompt_tokens") or 0) != descriptor.input_tokens
                or int(telemetry.get("completion_tokens") or 0) != descriptor.output_tokens
            ):
                raise ValueError("Provider Usage relation differs")
            if descriptor.status == "succeeded":
                response = cast(
                    dict[str, Any],
                    _read_json(output_dir / by_kind["response_metadata"].relative_path),
                )
                if (
                    response.get("public_projection_sha256") != descriptor.response_sha256
                    or telemetry.get("http_success") is not True
                ):
                    raise ValueError("Provider response relation differs")
            else:
                error = cast(
                    dict[str, Any],
                    _read_json(output_dir / by_kind["error_metadata"].relative_path),
                )
                expected_status = (
                    "provider_error"
                    if telemetry.get("http_status") is not None
                    else "transport_error"
                )
                if (
                    error.get("error_sha256") != descriptor.error_sha256
                    or descriptor.status != expected_status
                ):
                    raise ValueError("Provider error relation differs")
            relations.append(
                (
                    descriptor.provider_call_id,
                    descriptor.descriptor_id,
                    tuple(
                        (
                            item.artifact_kind,
                            item.artifact_id,
                            item.relative_path,
                            item.sha256,
                            item.byte_count,
                        )
                        for item in descriptor.artifacts
                    ),
                )
            )
        except (KeyError, TypeError, ValueError) as error:
            invalid += 1
            invalid_reasons.append(str(error))
    return {
        "request_intent_count": len(intent_paths),
        "provider_descriptor_count": len(descriptor_paths),
        "response_metadata_count": len(response_paths),
        "error_metadata_count": len(error_paths),
        "usage_metadata_count": len(usage_paths),
        "job_ids": intent_job_ids,
        "exact_provider_relation_set_sha256": models.canonical_sha256(tuple(relations)),
        "orphan_request_intent_count": len(orphan_intents),
        "orphan_descriptor_count": len(orphan_descriptors),
        "invalid_relation_count": invalid,
        "invalid_relation_reasons": tuple(invalid_reasons),
        "relation_closed": (
            not orphan_intents
            and not orphan_descriptors
            and invalid == 0
            and len(intent_paths) == len(descriptor_paths)
            and len(response_paths) + len(error_paths) == len(descriptor_paths)
            and len(usage_paths) == len(descriptor_paths)
        ),
        "authorization_id": authorization_id,
    }


def _admit_prepared_authorization(prepared: PreparedReplacement) -> None:
    formal_authorization_path = (
        prepared.repository_root / PREFLIGHT_DIR / "conditional_replacement_authorization.json"
    )
    if (
        not formal_authorization_path.is_file()
        or formal_authorization_path.read_bytes() != prepared.authorization_bytes
    ):
        raise ValueError("replacement fixed formal Authorization bytes differ")
    reparsed = models.ConditionalReplacementAuthorization.model_validate_json(
        prepared.authorization_bytes
    )
    expected_ledger = (
        prepared.repository_root / LEDGER_DIR / f"{_sha(reparsed.authorization_id.encode())}.json"
    )
    if (
        _encoded(reparsed) != prepared.authorization_bytes
        or reparsed != prepared.authorization
        or prepared.preparation.authorization_id != reparsed.authorization_id
        or prepared.preparation.authorization_sha256 != _sha(prepared.authorization_bytes)
        or prepared.preparation.postrun_repair_audit_id != prepared.postrun_audit.audit_id
        or prepared.preparation.repair_control_audit_id != prepared.repair_control_audit.audit_id
        or prepared.preparation.repair_source_identity_id != reparsed.repair_source_identity_id
        or reparsed.postrun_repair_audit_id != prepared.postrun_audit.audit_id
        or reparsed.repair_control_audit_id != prepared.repair_control_audit.audit_id
        or reparsed.repaired_source_commit != prepared.preparation.repaired_source_commit
        or reparsed.repaired_source_tree != prepared.preparation.repaired_source_tree
        or reparsed.exact_job_ids != prepared.preparation.exact_job_ids
        or prepared.ledger_path != expected_ledger
    ):
        raise ValueError("replacement exact-byte Authorization Guard rejected")


def _validate_record_files(output_dir: Path, record: models.JobExecutionRecord) -> None:
    descriptors: tuple[Any, ...] = (
        record.raw,
        record.result,
        record.trace,
        record.outcome,
        record.checkpoint,
    )
    values = tuple(
        cast(dict[str, Any], _read_json(output_dir / item.relative_path)) for item in descriptors
    )
    for descriptor, value in zip(descriptors, values, strict=True):
        payload = _canonical_file(output_dir / descriptor.relative_path, value)
        if descriptor.payload_sha256 != _sha(payload) or descriptor.payload_byte_count != len(
            payload
        ):
            raise ValueError("five-layer actual bytes differ")
    raw, result, trace, outcome, checkpoint = values
    if (
        raw.get("authorization_id") != record.authorization_id
        or result.get("raw_descriptor") != record.raw.model_dump(mode="json", warnings=False)
        or trace.get("raw_descriptor") != record.raw.model_dump(mode="json", warnings=False)
        or trace.get("result_descriptor") != record.result.model_dump(mode="json", warnings=False)
        or outcome.get("trace_descriptor") != record.trace.model_dump(mode="json", warnings=False)
        or checkpoint.get("outcome_descriptor")
        != record.outcome.model_dump(mode="json", warnings=False)
    ):
        raise ValueError("five-layer embedded parent differs")


def _run_repair_controls(
    *,
    repository_root: Path,
    loaded: dict[str, Any],
    audit: models.PostrunRepairAudit,
) -> models.RepairControlAudit:
    source_root = repository_root / (
        "trusted_data_synthesis/src/trusted_synthesis/experiments/vtdo_experiment"
    )
    online_source_sha = _sha(
        (source_root / "phase1_v26_fresh_exact_v209_parent_bound_online_execution.py").read_bytes()
    )
    models_source_sha = _sha(
        (
            source_root
            / "phase1_v26_fresh_exact_v209_parent_bound_online_execution_repair_models.py"
        ).read_bytes()
    )
    config = cast(AgentModelConfig, loaded["config"])
    manifest = cast(v209_models.ExecutableDevelopmentManifest, loaded["manifest"])
    job = sorted(manifest.jobs, key=lambda item: item.job_id)[0]
    original_urlopen = prior.urllib.request.urlopen
    previous_key = os.environ.get(config.api_key_env)
    os.environ[config.api_key_env] = "synthetic-control-key"
    try:
        with TemporaryDirectory(prefix="v26_225_repair_control_") as directory:
            root = Path(directory)
            records: list[models.JobExecutionRecord | models.JobFailureRecord] = []
            http_counts = [0, 0]
            for mode in ("success", "error"):
                output_dir = root / mode
                output_dir.mkdir(parents=True)
                authorization_id = f"v26_225_synthetic_{mode}_authorization"
                prepared = SimpleNamespace(
                    output_dir=output_dir,
                    authorization=SimpleNamespace(authorization_id=authorization_id),
                    bindings=loaded["bindings"],
                    frozen_parents=loaded["parents"],
                    config=config,
                    runtime=loaded["runtime"],
                    implementation=loaded["implementation"],
                )
                run_start = models.make_identity(
                    models.RunStartReceipt,
                    {
                        "consumption_receipt_id": f"synthetic-{mode}-consumption",
                        "preparation_id": f"synthetic-{mode}-preparation",
                        "authorization_id": authorization_id,
                        "execution_source_commit": "0" * 40,
                        "execution_source_tree": "1" * 40,
                        "started_at_utc": "2026-09-03T00:00:00Z",
                    },
                    field="receipt_id",
                    prefix="finance_v26_226_replacement_run_start_receipt:",
                )
                if mode == "success":

                    def success_urlopen(*_args: Any, **_kwargs: Any) -> _FakeHttpResponse:
                        http_counts[0] += 1
                        return _FakeHttpResponse()

                    prior.urllib.request.urlopen = success_urlopen
                else:

                    def error_urlopen(*_args: Any, **_kwargs: Any) -> Any:
                        http_counts[1] += 1
                        raise prior.urllib.error.URLError("synthetic transport failure")

                    prior.urllib.request.urlopen = error_urlopen
                record = cast(
                    models.JobExecutionRecord | models.JobFailureRecord,
                    prior._execute_job(  # noqa: SLF001
                        prepared=cast(Any, prepared),
                        run_start=cast(Any, run_start),
                        job=job,
                        job_ordinal=0,
                        client=prior.ExactRequestBodyDeepSeekClient(config),
                        record_model=cast(Any, models.JobExecutionRecord),
                        failure_record_model=cast(Any, models.JobFailureRecord),
                        record_identity_prefix="finance_v26_226_replacement_job_record:",
                        failure_identity_prefix="finance_v26_226_replacement_job_failure:",
                    ),
                )
                records.append(record)
                projection = _provider_relation_projection(
                    output_dir=output_dir,
                    authorization_id=authorization_id,
                    run_start_receipt_id=run_start.receipt_id,
                )
                if not projection["relation_closed"]:
                    raise ValueError(f"repair mock Provider journal did not close:{projection}")
            success_record = records[0]
            error_record = records[1]
            if (
                http_counts != [1, 1]
                or not isinstance(success_record, models.JobExecutionRecord)
                or success_record.terminal_kind != "first_response_abi_invalid"
                or not isinstance(error_record, models.JobFailureRecord)
                or error_record.failure_kind != "unbound_provider_failure"
                or len(success_record.provider_calls) != 1
                or len(error_record.provider_calls) != 1
                or success_record.provider_calls[0].status != "succeeded"
                or error_record.provider_calls[0].status != "transport_error"
            ):
                raise ValueError("repair mock execution controls differ")
            _validate_record_files(root / "success", success_record)
            success_files = tuple((root / "success" / "provider_calls").rglob("*.json"))
            error_files = tuple((root / "error" / "provider_calls").rglob("*.json"))
            five_layer_files = tuple(
                path
                for prefix in (
                    "evidence/raw",
                    "evidence/result",
                    "evidence/trace",
                    "evidence/outcome",
                    "checkpoints",
                )
                for path in (root / "success" / prefix).rglob("*.json")
            )
            if len(success_files) != 4 or len(error_files) != 4 or len(five_layer_files) != 5:
                raise ValueError("repair control persisted geometry differs")
            return models.make_identity(
                models.RepairControlAudit,
                {
                    "postrun_repair_audit_id": audit.audit_id,
                    "repaired_online_source_sha256": online_source_sha,
                    "repaired_models_source_sha256": models_source_sha,
                },
                field="audit_id",
                prefix="finance_v26_225_repair_control_audit:",
            )
    finally:
        prior.urllib.request.urlopen = original_urlopen
        if previous_key is None:
            os.environ.pop(config.api_key_env, None)
        else:
            os.environ[config.api_key_env] = previous_key


def _authorization_attack_audit(
    authorization: models.ConditionalReplacementAuthorization,
    authorization_bytes: bytes,
) -> models.AuthorizationAttackAudit:
    base = authorization.model_dump(mode="json", exclude={"authorization_id"}, warnings=False)
    mutations = (
        {"postrun_repair_audit_id": "forged-postrun-audit"},
        {"repair_control_audit_id": "forged-control-audit"},
        {"repair_source_identity_id": "forged-source-identity"},
        {"repaired_source_commit": "f" * 40},
        {"repaired_source_tree": "e" * 40},
        {
            "postrun_repair_audit_id": "forged-postrun-audit-2",
            "repair_control_audit_id": "forged-control-audit-2",
        },
        {
            "repair_source_identity_id": "forged-source-identity-2",
            "repaired_source_commit": "d" * 40,
        },
        {
            "repair_control_audit_id": "forged-control-audit-3",
            "repaired_source_tree": "c" * 40,
        },
    )
    candidates = []
    for mutation in mutations:
        values = {**base, **mutation}
        candidate = models.make_identity(
            models.ConditionalReplacementAuthorization,
            values,
            field="authorization_id",
            prefix="finance_v26_225_repaired_replacement_execution_authorization:",
        )
        if _encoded(candidate) == authorization_bytes:
            raise ValueError("full-rehash authorization attack was accepted")
        candidates.append(candidate)
    if len(candidates) != 8:
        raise ValueError("authorization attack partition differs")
    return models.make_identity(
        models.AuthorizationAttackAudit,
        {
            "authorization_id": authorization.authorization_id,
            "authorization_sha256": _sha(authorization_bytes),
        },
        field="audit_id",
        prefix="finance_v26_225_authorization_attack_audit:",
    )


def _construct_preflight_objects(
    *,
    repository_root: Path,
    runtime_output_dir: Path,
    source_identity: models.RepairPreflightSourceIdentity,
) -> RepairPreflightObjects:
    audit = _verify_v224(repository_root)
    loaded = _load_exact_runtime(repository_root, runtime_output_dir)
    repair_control = _run_repair_controls(
        repository_root=repository_root,
        loaded=loaded,
        audit=audit,
    )
    manifest = cast(v209_models.ExecutableDevelopmentManifest, loaded["manifest"])
    exact_job_ids = tuple(sorted(item.job_id for item in manifest.jobs))
    authorization = models.make_identity(
        models.ConditionalReplacementAuthorization,
        {
            "postrun_repair_audit_id": audit.audit_id,
            "repair_control_audit_id": repair_control.audit_id,
            "repair_source_identity_id": source_identity.source_id,
            "repaired_source_commit": source_identity.source_commit,
            "repaired_source_tree": source_identity.source_tree,
            "exact_job_ids": exact_job_ids,
        },
        field="authorization_id",
        prefix="finance_v26_225_repaired_replacement_execution_authorization:",
    )
    authorization_bytes = _encoded(authorization)
    preparation = models.make_identity(
        models.ReplacementPreparation,
        {
            "postrun_repair_audit_id": audit.audit_id,
            "repair_control_audit_id": repair_control.audit_id,
            "repair_source_identity_id": source_identity.source_id,
            "authorization_id": authorization.authorization_id,
            "authorization_sha256": _sha(authorization_bytes),
            "repaired_source_commit": source_identity.source_commit,
            "repaired_source_tree": source_identity.source_tree,
            "exact_job_ids": exact_job_ids,
        },
        field="preparation_id",
        prefix="finance_v26_225_repair_preparation:",
    )
    attack = _authorization_attack_audit(authorization, authorization_bytes)
    gate = models.make_identity(
        models.RepairPreflightGateEvaluation,
        {
            "source_identity_id": source_identity.source_id,
            "postrun_repair_audit_id": audit.audit_id,
            "repair_control_audit_id": repair_control.audit_id,
            "authorization_id": authorization.authorization_id,
            "authorization_sha256": _sha(authorization_bytes),
            "gates": PREFLIGHT_GATES,
        },
        field="gate_id",
        prefix="finance_v26_225_repair_gate_evaluation:",
    )
    decision = models.make_identity(
        models.RepairPreflightDecision,
        {
            "gate_id": gate.gate_id,
            "authorization_id": authorization.authorization_id,
        },
        field="decision_id",
        prefix="finance_v26_225_repair_decision:",
    )
    transition = models.make_identity(
        models.RepairPreflightTransition,
        {
            "decision_id": decision.decision_id,
            "authorization_id": authorization.authorization_id,
        },
        field="transition_id",
        prefix="finance_v26_225_repair_transition:",
    )
    return RepairPreflightObjects(
        source_identity=source_identity,
        postrun_audit=audit,
        repair_control_audit=repair_control,
        authorization=authorization,
        authorization_bytes=authorization_bytes,
        preparation=preparation,
        attack_audit=attack,
        gate=gate,
        decision=decision,
        transition=transition,
        loaded=loaded,
    )


def _preflight_payloads(objects: RepairPreflightObjects) -> dict[str, bytes]:
    return {
        "repair_directive.txt": models.REPAIR_DIRECTIVE.encode("utf-8"),
        "conditional_run_authorization.txt": models.CONDITIONAL_RUN_DIRECTIVE.encode("utf-8"),
        "source_identity.json": _encoded(objects.source_identity),
        "v224_postrun_repair_audit.json": _encoded(objects.postrun_audit),
        "repair_control_audit.json": _encoded(objects.repair_control_audit),
        "conditional_replacement_authorization.json": objects.authorization_bytes,
        "replacement_preparation.json": _encoded(objects.preparation),
        "authorization_attack_audit.json": _encoded(objects.attack_audit),
        "preflight_gate_evaluation.json": _encoded(objects.gate),
        "preflight_decision.json": _encoded(objects.decision),
        "preflight_transition.json": _encoded(objects.transition),
    }


def build_repair_preflight(
    *, repository_root: Path, output_dir: Path
) -> models.RepairPreflightArtifactManifest:
    repository_root = repository_root.resolve()
    output_dir = output_dir.resolve()
    if output_dir != (repository_root / PREFLIGHT_DIR).resolve():
        raise ValueError("repair preflight output directory differs")
    if output_dir.exists():
        raise FileExistsError(f"repair preflight already exists:{output_dir}")
    source_commit, source_tree = prior._git_identity(repository_root)  # noqa: SLF001
    source = _source_identity(repository_root, source_commit, source_tree)
    objects = _construct_preflight_objects(
        repository_root=repository_root,
        runtime_output_dir=repository_root / OUTPUT_DIR,
        source_identity=source,
    )
    payloads = _preflight_payloads(objects)
    output_dir.mkdir(parents=True, exist_ok=False)
    for name, payload in payloads.items():
        prior._durable_write_no_replace(output_dir / name, payload)  # noqa: SLF001
    manifest = models.repair_preflight_artifact_manifest(PREFLIGHT_RUN_ID, payloads)
    prior._durable_write_no_replace(  # noqa: SLF001
        output_dir / "artifact_manifest.json", _encoded(manifest)
    )
    return manifest


def _load_fixed_preflight(
    *, repository_root: Path, runtime_output_dir: Path
) -> RepairPreflightObjects:
    root = repository_root / PREFLIGHT_DIR
    files = {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file()
    }
    expected_names = {
        "repair_directive.txt",
        "conditional_run_authorization.txt",
        "source_identity.json",
        "v224_postrun_repair_audit.json",
        "repair_control_audit.json",
        "conditional_replacement_authorization.json",
        "replacement_preparation.json",
        "authorization_attack_audit.json",
        "preflight_gate_evaluation.json",
        "preflight_decision.json",
        "preflight_transition.json",
        "artifact_manifest.json",
    }
    if set(files) != expected_names:
        raise ValueError("repair formal preflight file set differs")
    saved_source = models.RepairPreflightSourceIdentity.model_validate_json(
        files["source_identity.json"]
    )
    source = _source_identity(repository_root, saved_source.source_commit, saved_source.source_tree)
    if _encoded(source) != files["source_identity.json"]:
        raise ValueError("repair formal source identity bytes differ")
    _verify_source_overlay(repository_root, source)
    objects = _construct_preflight_objects(
        repository_root=repository_root,
        runtime_output_dir=runtime_output_dir,
        source_identity=source,
    )
    payloads = _preflight_payloads(objects)
    if any(files[name] != payload for name, payload in payloads.items()):
        raise ValueError("repair formal expected object bytes differ")
    saved_manifest = models.RepairPreflightArtifactManifest.model_validate_json(
        files["artifact_manifest.json"]
    )
    rebuilt_manifest = models.repair_preflight_artifact_manifest(PREFLIGHT_RUN_ID, payloads)
    if (
        _encoded(saved_manifest) != files["artifact_manifest.json"]
        or saved_manifest != rebuilt_manifest
    ):
        raise ValueError("repair formal Manifest rebuild differs")
    return objects


def prepare_replacement(*, repository_root: Path, output_dir: Path) -> PreparedReplacement:
    repository_root = repository_root.resolve()
    output_dir = output_dir.resolve()
    if output_dir != (repository_root / OUTPUT_DIR).resolve():
        raise ValueError("replacement output directory differs from conditional authorization")
    if output_dir.exists():
        raise FileExistsError(f"replacement output already exists:{output_dir}")
    objects = _load_fixed_preflight(
        repository_root=repository_root,
        runtime_output_dir=output_dir,
    )
    loaded = objects.loaded
    manifest = cast(v209_models.ExecutableDevelopmentManifest, loaded["manifest"])
    authorization = objects.authorization
    ledger = repository_root / LEDGER_DIR / f"{_sha(authorization.authorization_id.encode())}.json"
    return PreparedReplacement(
        repository_root=repository_root,
        package_root=repository_root / "trusted_data_synthesis",
        output_dir=output_dir,
        ledger_path=ledger,
        postrun_audit=objects.postrun_audit,
        repair_control_audit=objects.repair_control_audit,
        authorization=authorization,
        authorization_bytes=objects.authorization_bytes,
        preparation=objects.preparation,
        catalog=cast(v209_models.ExecutableRunnerPackageCatalog, loaded["catalog"]),
        manifest=manifest,
        implementation=cast(v209_models.ImplementationBinding, loaded["implementation"]),
        frozen_parents=cast(prior.v209.FrozenParents, loaded["parents"]),
        runtime=cast(prior.v188.PreparedExecution, loaded["runtime"]),
        config=cast(AgentModelConfig, loaded["config"]),
        bindings=cast(prior.FrozenBindings, loaded["bindings"]),
    )


def _consume(
    prepared: PreparedReplacement,
) -> tuple[models.AuthorizationConsumptionReceipt, models.RunStartReceipt]:
    _admit_prepared_authorization(prepared)
    consumption = models.make_identity(
        models.AuthorizationConsumptionReceipt,
        {
            "preparation_id": prepared.preparation.preparation_id,
            "authorization_id": prepared.authorization.authorization_id,
            "authorization_sha256": _sha(prepared.authorization_bytes),
            "consumed_at_utc": prior._utc_now(),  # noqa: SLF001
        },
        field="receipt_id",
        prefix="finance_v26_226_replacement_authorization_consumption_receipt:",
    )
    prior._durable_write_no_replace(prepared.ledger_path, _encoded(consumption))  # noqa: SLF001
    prepared.output_dir.mkdir(parents=True, exist_ok=False)
    prior._durable_write_no_replace(  # noqa: SLF001
        prepared.output_dir / "authorization_consumption_receipt.json", _encoded(consumption)
    )
    run_start = models.make_identity(
        models.RunStartReceipt,
        {
            "consumption_receipt_id": consumption.receipt_id,
            "preparation_id": prepared.preparation.preparation_id,
            "authorization_id": prepared.authorization.authorization_id,
            "execution_source_commit": prepared.preparation.repaired_source_commit,
            "execution_source_tree": prepared.preparation.repaired_source_tree,
            "started_at_utc": prior._utc_now(),  # noqa: SLF001
        },
        field="receipt_id",
        prefix="finance_v26_226_replacement_run_start_receipt:",
    )
    prior._durable_write_no_replace(  # noqa: SLF001
        prepared.output_dir / "run_start_receipt.json", _encoded(run_start)
    )
    return consumption, run_start


def _write_ingress(prepared: PreparedReplacement) -> None:
    values: dict[str, bytes] = {
        "repair_directive.txt": models.REPAIR_DIRECTIVE.encode("utf-8"),
        "conditional_run_authorization.txt": models.CONDITIONAL_RUN_DIRECTIVE.encode("utf-8"),
        "v224_postrun_repair_audit.json": _encoded(prepared.postrun_audit),
        "repair_control_audit.json": _encoded(prepared.repair_control_audit),
        "conditional_replacement_authorization.json": _encoded(prepared.authorization),
        "replacement_preparation.json": _encoded(prepared.preparation),
    }
    for name, payload in values.items():
        prior._durable_write_no_replace(prepared.output_dir / name, payload)  # noqa: SLF001


def _intent_census(
    prepared: PreparedReplacement, run_start: models.RunStartReceipt
) -> models.ProviderIntentCensus:
    projection = _provider_relation_projection(
        output_dir=prepared.output_dir,
        authorization_id=prepared.authorization.authorization_id,
        run_start_receipt_id=run_start.receipt_id,
    )
    return models.make_identity(
        models.ProviderIntentCensus,
        {
            "authorization_id": prepared.authorization.authorization_id,
            "run_start_receipt_id": run_start.receipt_id,
            "request_intent_count": projection["request_intent_count"],
            "provider_descriptor_count": projection["provider_descriptor_count"],
            "response_metadata_count": projection["response_metadata_count"],
            "error_metadata_count": projection["error_metadata_count"],
            "usage_metadata_count": projection["usage_metadata_count"],
            "job_ids_with_request_intent_sha256": models.canonical_sha256(projection["job_ids"]),
            "exact_provider_relation_set_sha256": projection["exact_provider_relation_set_sha256"],
            "orphan_request_intent_count": projection["orphan_request_intent_count"],
            "orphan_descriptor_count": projection["orphan_descriptor_count"],
            "invalid_relation_count": projection["invalid_relation_count"],
            "relation_closed": projection["relation_closed"],
        },
        field="census_id",
        prefix="finance_v26_226_provider_intent_census:",
    )


def execute_replacement(
    *, prepared: PreparedReplacement, workers: int = MAX_WORKERS
) -> models.ExecutionSummary:
    if workers < 1 or workers > 32:
        raise ValueError("replacement worker count must be in [1,32]")
    refreshed = _load_fixed_preflight(
        repository_root=prepared.repository_root,
        runtime_output_dir=prepared.output_dir,
    )
    if (
        refreshed.authorization != prepared.authorization
        or refreshed.authorization_bytes != prepared.authorization_bytes
        or refreshed.preparation != prepared.preparation
        or refreshed.postrun_audit != prepared.postrun_audit
        or refreshed.repair_control_audit != prepared.repair_control_audit
    ):
        raise ValueError("replacement fixed preflight changed after preparation")
    consumption, run_start = _consume(prepared)
    _write_ingress(prepared)
    prior._load_env_key(prepared.package_root, prepared.config.api_key_env)  # noqa: SLF001
    client = prior.ExactRequestBodyDeepSeekClient(prepared.config)
    jobs = {item.job_id: item for item in prepared.manifest.jobs}
    ordered = tuple(jobs[item] for item in prepared.authorization.exact_job_ids)
    outputs: dict[int, models.JobExecutionRecord | models.JobFailureRecord] = {}
    pending: dict[Future[Any], int] = {}
    next_ordinal = 0
    with ThreadPoolExecutor(max_workers=workers) as pool:
        while next_ordinal < min(workers, len(ordered)):
            ordinal = next_ordinal
            pending[
                pool.submit(
                    prior._execute_job,  # noqa: SLF001
                    prepared=cast(Any, prepared),
                    run_start=cast(Any, run_start),
                    job=ordered[ordinal],
                    job_ordinal=ordinal,
                    client=client,
                    record_model=cast(Any, models.JobExecutionRecord),
                    failure_record_model=cast(Any, models.JobFailureRecord),
                    record_identity_prefix="finance_v26_226_replacement_job_record:",
                    failure_identity_prefix="finance_v26_226_replacement_job_failure:",
                )
            ] = ordinal
            next_ordinal += 1
        while pending:
            completed, _ = wait(tuple(pending), return_when=FIRST_COMPLETED)
            for future in completed:
                ordinal = pending.pop(future)
                output = cast(models.JobExecutionRecord | models.JobFailureRecord, future.result())
                outputs[ordinal] = output
                directory = (
                    "job_records"
                    if isinstance(output, models.JobExecutionRecord)
                    else "job_failures"
                )
                prior._durable_write_no_replace(  # noqa: SLF001
                    prepared.output_dir / directory / f"job_{ordinal:03d}.json",
                    _encoded(output),
                )
                if next_ordinal < len(ordered):
                    queued = next_ordinal
                    pending[
                        pool.submit(
                            prior._execute_job,  # noqa: SLF001
                            prepared=cast(Any, prepared),
                            run_start=cast(Any, run_start),
                            job=ordered[queued],
                            job_ordinal=queued,
                            client=client,
                            record_model=cast(Any, models.JobExecutionRecord),
                            failure_record_model=cast(Any, models.JobFailureRecord),
                            record_identity_prefix="finance_v26_226_replacement_job_record:",
                            failure_identity_prefix="finance_v26_226_replacement_job_failure:",
                        )
                    ] = queued
                    next_ordinal += 1
    if tuple(sorted(outputs)) != tuple(range(192)):
        raise ValueError("replacement exact Job coverage differs")
    records = tuple(
        cast(models.JobExecutionRecord, outputs[index])
        for index in sorted(outputs)
        if isinstance(outputs[index], models.JobExecutionRecord)
    )
    failures = tuple(
        cast(models.JobFailureRecord, outputs[index])
        for index in sorted(outputs)
        if isinstance(outputs[index], models.JobFailureRecord)
    )
    census = _intent_census(prepared, run_start)
    prior._durable_write_no_replace(  # noqa: SLF001
        prepared.output_dir / "provider_intent_census.json", _encoded(census)
    )
    calls = tuple(call for item in records for call in item.provider_calls) + tuple(
        call for item in failures for call in item.provider_calls
    )
    persisted_calls = tuple(
        prior.models.ProviderCallDescriptor.model_validate_json(path.read_bytes())
        for path in sorted((prepared.output_dir / "provider_calls").rglob("*_descriptor.json"))
    )
    if census.provider_descriptor_count != len(calls) or tuple(
        sorted(models.canonical_bytes(item) for item in calls)
    ) != tuple(sorted(models.canonical_bytes(item) for item in persisted_calls)):
        raise ValueError("replacement descriptor census differs from Job evidence")
    for record in records:
        _validate_record_files(prepared.output_dir, record)
    terminal_partition = {kind: 0 for kind in prior.models.TERMINAL_KINDS}
    for record in records:
        terminal_partition[record.terminal_kind] += 1
    failure_partition = {"unbound_provider_failure": 0, "host_failure": 0}
    for failure in failures:
        failure_partition[failure.failure_kind] += 1
    status: Literal["completed", "incomplete"] = "completed" if not failures else "incomplete"
    if status == "completed" and (
        not census.relation_closed or any(not item.provider_calls for item in records)
    ):
        raise ValueError("completed replacement lacks closed Provider-intent evidence")
    summary = models.make_identity(
        models.ExecutionSummary,
        {
            "preparation_id": prepared.preparation.preparation_id,
            "consumption_receipt_id": consumption.receipt_id,
            "run_start_receipt_id": run_start.receipt_id,
            "authorization_id": prepared.authorization.authorization_id,
            "execution_status": status,
            "records": records,
            "failure_records": failures,
            "exact_job_set_sha256": prepared.authorization.exact_job_set_sha256,
            "completed_job_record_count": len(records),
            "failure_record_count": len(failures),
            "raw_count": len(records),
            "result_count": len(records),
            "trace_count": len(records),
            "outcome_count": len(records),
            "checkpoint_count": len(records),
            "terminal_partition": terminal_partition,
            "failure_partition": failure_partition,
            "request_intent_count": census.request_intent_count,
            "provider_descriptor_count": census.provider_descriptor_count,
            "attempted_provider_call_lower_bound": census.provider_descriptor_count,
            "attempted_provider_call_upper_bound": census.request_intent_count,
            "provider_call_count": len(calls),
            "input_tokens": sum(item.input_tokens for item in calls),
            "output_tokens": sum(item.output_tokens for item in calls),
            "replacement_job_count": 192,
        },
        field="summary_id",
        prefix="finance_v26_226_execution_summary:",
    )
    prior._durable_write_no_replace(  # noqa: SLF001
        prepared.output_dir / "execution_summary.json", _encoded(summary)
    )
    transition = models.make_identity(
        models.Transition,
        {
            "summary_id": summary.summary_id,
            "authorization_id": prepared.authorization.authorization_id,
            "execution_status": status,
            "provider_intent_census_id": census.census_id,
            "status": (
                "COMPLETED_AWAITING_POSTRUN_INDEPENDENT_AUDIT"
                if status == "completed"
                else "INCOMPLETE_AWAITING_POSTRUN_INDEPENDENT_AUDIT"
            ),
        },
        field="transition_id",
        prefix="finance_v26_226_transition:",
    )
    prior._durable_write_no_replace(  # noqa: SLF001
        prepared.output_dir / "prospective_transition.json", _encoded(transition)
    )
    payloads = {
        path.relative_to(prepared.output_dir).as_posix(): path.read_bytes()
        for path in prepared.output_dir.rglob("*")
        if path.is_file() and path.name != "execution_artifact_manifest.json"
    }
    artifact = models.artifact_manifest(RUN_ID, payloads)
    prior._durable_write_no_replace(  # noqa: SLF001
        prepared.output_dir / "execution_artifact_manifest.json", _encoded(artifact)
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository-root", type=Path, default=Path.cwd())
    parser.add_argument("--build-repair-preflight", action="store_true")
    parser.add_argument("--prepare-only", action="store_true")
    parser.add_argument("--workers", type=int, default=MAX_WORKERS)
    args = parser.parse_args()
    root = args.repository_root.resolve()
    if args.build_repair_preflight:
        manifest = build_repair_preflight(
            repository_root=root,
            output_dir=root / PREFLIGHT_DIR,
        )
        print(models.canonical_bytes(manifest).decode("utf-8"))
        return
    prepared = prepare_replacement(repository_root=root, output_dir=root / OUTPUT_DIR)
    if args.prepare_only:
        print(models.canonical_bytes(prepared.preparation).decode("utf-8"))
        return
    summary = execute_replacement(prepared=prepared, workers=args.workers)
    print(models.canonical_bytes(summary).decode("utf-8"))


if __name__ == "__main__":
    main()
