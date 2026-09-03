# ruff: noqa: E501
from __future__ import annotations

import argparse
import hashlib
import json
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from dataclasses import dataclass
from pathlib import Path
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
OUTPUT_DIR: Final = f"trusted_data_synthesis/artifacts/vtdo_experiment/{RUN_ID}"
LEDGER_DIR: Final = (
    "trusted_data_synthesis/artifacts/vtdo_experiment/authorization_consumption_ledger"
)
V224_DIR: Final = prior.OUTPUT_DIR
V224_MANIFEST_SHA256: Final = "f85a1ea86c4e581ad8f94bae9af9fbc8d28638cc861b1ce138639949278fade1"
MAX_WORKERS: Final = 8


@dataclass(frozen=True)
class PreparedReplacement:
    repository_root: Path
    package_root: Path
    output_dir: Path
    ledger_path: Path
    postrun_audit: models.PostrunRepairAudit
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


def _read_json(path: Path) -> Any:
    return json.loads(path.read_bytes())


def _sha(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _encoded(value: Any) -> bytes:
    return models.canonical_bytes(value) + b"\n"


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


def prepare_replacement(*, repository_root: Path, output_dir: Path) -> PreparedReplacement:
    repository_root = repository_root.resolve()
    output_dir = output_dir.resolve()
    if output_dir != (repository_root / OUTPUT_DIR).resolve():
        raise ValueError("replacement output directory differs from conditional authorization")
    if output_dir.exists():
        raise FileExistsError(f"replacement output already exists:{output_dir}")
    audit = _verify_v224(repository_root)
    source_commit, source_tree = prior._git_identity(repository_root)  # noqa: SLF001
    loaded = _load_exact_runtime(repository_root, output_dir)
    manifest = cast(v209_models.ExecutableDevelopmentManifest, loaded["manifest"])
    exact_job_ids = tuple(sorted(item.job_id for item in manifest.jobs))
    authorization = models.make_identity(
        models.ConditionalReplacementAuthorization,
        {
            "postrun_repair_audit_id": audit.audit_id,
            "repaired_source_commit": source_commit,
            "repaired_source_tree": source_tree,
            "exact_job_ids": exact_job_ids,
        },
        field="authorization_id",
        prefix="finance_v26_225_repaired_replacement_execution_authorization:",
    )
    authorization_bytes = models.canonical_bytes(authorization)
    reparsed = models.ConditionalReplacementAuthorization.model_validate_json(authorization_bytes)
    if models.canonical_bytes(reparsed) != authorization_bytes:
        raise ValueError("replacement authorization exact-byte Guard rejected")
    preparation = models.make_identity(
        models.ReplacementPreparation,
        {
            "postrun_repair_audit_id": audit.audit_id,
            "authorization_id": authorization.authorization_id,
            "authorization_sha256": _sha(authorization_bytes),
            "repaired_source_commit": source_commit,
            "repaired_source_tree": source_tree,
            "exact_job_ids": exact_job_ids,
        },
        field="preparation_id",
        prefix="finance_v26_225_repair_preparation:",
    )
    ledger = repository_root / LEDGER_DIR / f"{_sha(authorization.authorization_id.encode())}.json"
    return PreparedReplacement(
        repository_root=repository_root,
        package_root=repository_root / "trusted_data_synthesis",
        output_dir=output_dir,
        ledger_path=ledger,
        postrun_audit=audit,
        authorization=authorization,
        authorization_bytes=authorization_bytes,
        preparation=preparation,
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
        "conditional_replacement_authorization.json": _encoded(prepared.authorization),
        "replacement_preparation.json": _encoded(prepared.preparation),
    }
    for name, payload in values.items():
        prior._durable_write_no_replace(prepared.output_dir / name, payload)  # noqa: SLF001


def _intent_census(
    prepared: PreparedReplacement, run_start: models.RunStartReceipt
) -> models.ProviderIntentCensus:
    root = prepared.output_dir / "provider_calls"
    intent_paths = tuple(sorted(root.rglob("*_request_metadata.json")))
    descriptor_paths = tuple(sorted(root.rglob("*_descriptor.json")))
    response_paths = tuple(sorted(root.rglob("*_response_metadata.json")))
    error_paths = tuple(sorted(root.rglob("*_error_metadata.json")))
    usage_paths = tuple(sorted(root.rglob("*_usage_metadata.json")))
    job_ids = tuple(
        sorted({str(cast(dict[str, Any], _read_json(path))["job_id"]) for path in intent_paths})
    )
    return models.make_identity(
        models.ProviderIntentCensus,
        {
            "authorization_id": prepared.authorization.authorization_id,
            "run_start_receipt_id": run_start.receipt_id,
            "request_intent_count": len(intent_paths),
            "provider_descriptor_count": len(descriptor_paths),
            "response_metadata_count": len(response_paths),
            "error_metadata_count": len(error_paths),
            "usage_metadata_count": len(usage_paths),
            "job_ids_with_request_intent_sha256": models.canonical_sha256(job_ids),
        },
        field="census_id",
        prefix="finance_v26_226_provider_intent_census:",
    )


def execute_replacement(
    *, prepared: PreparedReplacement, workers: int = MAX_WORKERS
) -> models.ExecutionSummary:
    if workers < 1 or workers > 32:
        raise ValueError("replacement worker count must be in [1,32]")
    _source = prior._git_identity(prepared.repository_root)  # noqa: SLF001
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
                    run_start=run_start,
                    job=ordered[ordinal],
                    job_ordinal=ordinal,
                    client=client,
                    record_model=models.JobExecutionRecord,
                    failure_record_model=models.JobFailureRecord,
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
                            run_start=run_start,
                            job=ordered[queued],
                            job_ordinal=queued,
                            client=client,
                            record_model=models.JobExecutionRecord,
                            failure_record_model=models.JobFailureRecord,
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
    if census.provider_descriptor_count != len(calls):
        raise ValueError("replacement descriptor census differs from Job evidence")
    terminal_partition = {kind: 0 for kind in prior.models.TERMINAL_KINDS}
    for record in records:
        terminal_partition[record.terminal_kind] += 1
    failure_partition = {"unbound_provider_failure": 0, "host_failure": 0}
    for failure in failures:
        failure_partition[failure.failure_kind] += 1
    status: Literal["completed", "incomplete"] = "completed" if not failures else "incomplete"
    if status == "completed" and (
        census.request_intent_count != census.provider_descriptor_count
        or census.response_metadata_count + census.error_metadata_count
        != census.provider_descriptor_count
        or census.usage_metadata_count != census.provider_descriptor_count
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
            "provider_call_count": len(calls),
            "input_tokens": sum(item.input_tokens for item in calls),
            "output_tokens": sum(item.output_tokens for item in calls),
            "replacement_job_count": 192,
        },
        field="summary_id",
        prefix="finance_v26_224_execution_summary:",
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
    parser.add_argument("--prepare-only", action="store_true")
    parser.add_argument("--workers", type=int, default=MAX_WORKERS)
    args = parser.parse_args()
    root = args.repository_root.resolve()
    prepared = prepare_replacement(repository_root=root, output_dir=root / OUTPUT_DIR)
    if args.prepare_only:
        print(models.canonical_bytes(prepared.preparation).decode("utf-8"))
        return
    summary = execute_replacement(prepared=prepared, workers=args.workers)
    print(models.canonical_bytes(summary).decode("utf-8"))


if __name__ == "__main__":
    main()
