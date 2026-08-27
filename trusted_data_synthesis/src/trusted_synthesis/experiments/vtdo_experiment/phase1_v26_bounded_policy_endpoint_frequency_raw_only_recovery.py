from __future__ import annotations

import argparse
import hashlib
import json
import os
from collections.abc import Mapping, Sequence
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Final, cast

from trusted_synthesis.canonical_json import strict_canonical_hash
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_bounded_policy_endpoint_frequency_execution as execution,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_bounded_policy_endpoint_frequency_execution_models as execution_models,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_bounded_policy_endpoint_frequency_raw_only_recovery_models as models,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_reachability_execution as execution_base,
)
from trusted_synthesis.runtime.agent import prospective_reachability_runner_vnext as runner_vnext
from trusted_synthesis.runtime.agent.prospective_bounded_policy_endpoint_runner import (
    make_bounded_policy_endpoint_record,
)

IMPLEMENTATION_PATH: Final = models.RUNNER_IMPLEMENTATION_PATH
MODEL_IMPLEMENTATION_PATH: Final = models.MODEL_IMPLEMENTATION_PATH


def _canonical_bytes(value: Any) -> bytes:
    return models.canonical_bytes(value)


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json_once(path: Path, value: Any) -> None:
    payload = _canonical_bytes(value)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_bytes() != payload:
            raise ValueError(f"v26.164 Raw-only recovery artifact changed: {path}")
        return
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(payload)
    temporary.replace(path)


def _directory_snapshot(root: Path) -> tuple[int, int, str]:
    entries: list[dict[str, str | int]] = []
    total_bytes = 0
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        byte_count = path.stat().st_size
        total_bytes += byte_count
        entries.append(
            {
                "relative_path": str(path.relative_to(root)),
                "sha256": models.sha256(path),
                "byte_count": byte_count,
            }
        )
    return (
        len(entries),
        total_bytes,
        strict_canonical_hash(
            entries,
            prefix="finance_v26_bounded_policy_failed_execution_content_root:",
        ),
    )


def _implementation_files(
    implementation_root: Path,
) -> tuple[models.RecoveryImplementationFileBinding, ...]:
    bindings = []
    for relative_path in sorted((IMPLEMENTATION_PATH, MODEL_IMPLEMENTATION_PATH)):
        path = implementation_root / relative_path
        bindings.append(
            models.RecoveryImplementationFileBinding(
                relative_path=relative_path,
                sha256=models.sha256(path),
                byte_count=path.stat().st_size,
            )
        )
    return tuple(bindings)


def _prepare_from_failed_freeze(
    *,
    preflight_dir: Path,
    failed_execution_dir: Path,
    package_root: Path,
    implementation_root: Path,
) -> execution_models.PreparedBoundedPolicyExecution:
    if (failed_execution_dir / "frozen_v26_163_report.json").read_bytes() != (
        preflight_dir / "report.json"
    ).read_bytes():
        raise ValueError("v26.164 failed Freeze crossed the exact v26.163 report")
    source = execution_models.ExecutionSourceReplayAudit.model_validate(
        _load(failed_execution_dir / "execution_source_replay_audit.json")
    )
    for item in source.implementation_files:
        path = implementation_root / item.relative_path
        if (
            not path.is_file()
            or models.sha256(path) != item.sha256
            or path.stat().st_size != item.byte_count
        ):
            raise ValueError("v26.164 failed-v1 implementation binding changed")
    if (
        source.preflight_output_byte_match_count != 34
        or source.independent_rebuild_byte_match_count != 34
        or source.credential_lookup_attempted
        or source.provider_calls
    ):
        raise ValueError("v26.164 failed-v1 source replay is not reusable")

    report = execution.BoundedPolicyPreflightReport.model_validate(
        _load(failed_execution_dir / "frozen_v26_163_report.json")
    )
    population = execution.FreshFrequencySourcePopulation.model_validate(
        _load(failed_execution_dir / "frozen_source_population.json")
    )
    selection = execution.RouteBSourceSelectionAudit.model_validate(
        _load(failed_execution_dir / "frozen_source_selection_audit.json")
    )
    tasks = execution.preflight_inputs.reachability.TaskPackageCatalog.model_validate(
        _load(failed_execution_dir / "frozen_task_package_catalog.json")
    )
    paths = execution.preflight_inputs.reachability.PathCatalog.model_validate(
        _load(failed_execution_dir / "frozen_path_catalog.json")
    )
    support = execution.preflight_inputs.reachability.SupportClosureAudit.model_validate(
        _load(failed_execution_dir / "frozen_measurement_support_closure.json")
    )
    detours = (
        execution.preflight_inputs.reachability.ReachabilityDetourQualificationAudit.model_validate(
            _load(failed_execution_dir / "frozen_detour_qualification_audit.json")
        )
    )
    resource = execution.preflight_inputs.reachability.ResourceContract.model_validate(
        _load(failed_execution_dir / "frozen_resource_contract.json")
    )
    policy = execution.preflight.BoundedPolicyEndpointGenerationPolicy.model_validate(
        _load(failed_execution_dir / "frozen_generation_policy.json")
    )
    omega = execution.OmegaTaskContextCatalogV2.model_validate(
        _load(failed_execution_dir / "frozen_omega_task_context_catalog.json")
    )
    cells = execution_models.TaskConditionCellCatalogV2.model_validate(
        _load(failed_execution_dir / "frozen_task_condition_cell_catalog.json")
    )
    assignment = execution.FrequencyAssignmentContract.model_validate(
        _load(failed_execution_dir / "frozen_frequency_assignment_contract.json")
    )
    protocol = execution.MapperV2FrequencyProtocol.model_validate(
        _load(failed_execution_dir / "frozen_mapper_v2_frequency_protocol.json")
    )
    estimand = execution.BoundedPolicyEstimandContract.model_validate(
        _load(failed_execution_dir / "frozen_bounded_policy_estimand_contract.json")
    )
    execution_contract = execution.FrequencyExecutionContract.model_validate(
        _load(failed_execution_dir / "frozen_frequency_execution_contract.json")
    )
    manifest = execution.FrequencyManifest.model_validate(
        _load(failed_execution_dir / "frozen_frequency_manifest.json")
    )
    outcome = execution.BoundedPolicyOutcomeContract.model_validate(
        _load(failed_execution_dir / "frozen_bounded_policy_outcome_contract.json")
    )
    runner = execution.BoundedPolicyRunnerContract.model_validate(
        _load(failed_execution_dir / "frozen_bounded_policy_runner_contract.json")
    )
    joint = execution_base.JointSupportValidityContract.model_validate(
        _load(failed_execution_dir / "frozen_joint_support_validity_contract.json")
    )
    grammar = execution.QualifiedFinalResponseGrammar.model_validate(
        _load(failed_execution_dir / "frozen_qualified_final_response_grammar.json")
    )
    semantic_policy = execution.state_semantics.EmpiricalStateSemanticPolicyV2.model_validate(
        _load(failed_execution_dir / "frozen_mapper_v2_semantic_policy.json")
    )
    mapper_contract = execution.state_semantics.ValidOnlyStateMapperContractV2.model_validate(
        _load(failed_execution_dir / "frozen_mapper_v2_contract.json")
    )
    transition = execution.ProspectiveTransitionContract.model_validate(
        _load(failed_execution_dir / "frozen_preflight_transition_contract.json")
    )
    preexecution = execution_models.PreexecutionBindingAudit.model_validate(
        _load(failed_execution_dir / "preexecution_binding_audit.json")
    )
    static = execution.preflight_static.load_static_inputs(package_root)
    predecessor = execution.preflight_inputs.reachability.bounded.predecessor
    _, replay_contract = predecessor._load_and_replay_verifier_qualification(  # noqa: SLF001
        package_root / predecessor.VERIFIER_QUALIFICATION_DIR,
        package_root,
    )
    legacy_prepared = execution_base.PreparedExecution(
        source_replay=cast(Any, source),
        preflight_report=cast(Any, report),
        frozen_input=cast(Any, SimpleNamespace(audit_id=selection.audit_id)),
        tasks=tasks,
        paths=paths,
        support_closure=support,
        detour_qualification=detours,
        resource=resource,
        execution_contract=cast(Any, execution_contract),
        manifest=cast(Any, manifest),
        outcome_contract=cast(Any, outcome),
        runner_contract=cast(Any, runner),
        joint_contract=joint,
        grammar=grammar,
        transition=cast(Any, transition),
        preexecution_binding=cast(Any, preexecution),
        role_inputs=SimpleNamespace(static=static),
        replay_contract=replay_contract,
    )
    prepared = execution_models.PreparedBoundedPolicyExecution(
        source_replay=source,
        preexecution_binding=preexecution,
        preflight_report=report,
        source_population=population,
        source_selection=selection,
        tasks=tasks,
        paths=paths,
        support_closure=support,
        detour_qualification=detours,
        resource=resource,
        policy=policy,
        omega_catalog=omega,
        cell_catalog=cells,
        assignment_contract=assignment,
        mapper_protocol=protocol,
        estimand_contract=estimand,
        execution_contract=execution_contract,
        manifest=manifest,
        outcome_contract=outcome,
        runner_contract=runner,
        transition=transition,
        joint_contract=joint,
        grammar=grammar,
        semantic_policy=semantic_policy,
        mapper_contract=mapper_contract,
        legacy_prepared=legacy_prepared,
    )
    execution._validate_exact_authorization(prepared)  # noqa: SLF001
    return prepared


def _make_result(
    *,
    job: Any,
    prepared: execution_models.PreparedBoundedPolicyExecution,
    failed_execution_dir: Path,
    checkpoint_by_job: Mapping[str, execution_models.BoundedPolicyFrequencyMeasurementResult],
) -> tuple[
    models.RawOnlyRecoveredMeasurementResult,
    runner_vnext.FreshReachabilityRawExecution,
    models.TypedSemanticRejectionNormalizationRow | None,
]:
    package = execution._package_for_job(prepared, job)  # noqa: SLF001
    binding = execution_base._runtime_binding_for_job(  # noqa: SLF001
        prepared=prepared.legacy_prepared,
        package=package,
        job=job,
    )
    raw = runner_vnext.execute_fresh_reachability_job_raw(
        job=job,
        runner_contract=prepared.runner_contract,
        resource_contract=prepared.resource,
        static=prepared.legacy_prepared.role_inputs.static,
        qualified_grammar=prepared.grammar,
        binding=binding,
        client=None,
        output_dir=failed_execution_dir,
    )
    legacy = execution_base.project_measurement_result(
        raw=raw,
        job=job,
        package=package,
        prepared=prepared.legacy_prepared,
        output_dir=failed_execution_dir,
    )
    provider_identity_integrity = bool(
        legacy.exact_model_passed
        and legacy.fallback_absent
        and legacy.provider_native_tool_absent
        and legacy.dynamic_precall_binding_passed
        and legacy.exact_request_binding_passed
        and legacy.reversible_commit_integrity_passed
        and raw.stage_two_provider_call_count == 0
    )
    typed_rejection = raw.terminal_disposition == "typed_semantic_rejection"
    endpoint = make_bounded_policy_endpoint_record(
        raw=raw,
        policy=prepared.policy,
        provider_identity_integrity=provider_identity_integrity,
        thinking_usage_integrity=bool(
            legacy.thinking_continuity_passed and legacy.provider_usage_complete
        ),
        privacy_artifact_integrity=legacy.privacy_artifact_pairing_passed,
        transport_resolved=not legacy.unresolved_transport_failure,
        task_completion=(
            False if typed_rejection else raw.terminal_disposition == "completed_model_endpoint"
        ),
        base_validity=False if typed_rejection else legacy.base_trajectory_validity,
        mechanism_qualification=(False if typed_rejection else legacy.mechanism_qualification),
        qualified_validity=(False if typed_rejection else legacy.qualified_trajectory_validity),
        task_verifier_invocation_count=(
            0 if typed_rejection else legacy.task_verifier_invocation_count
        ),
    )
    expected_horizon = execution._expected_horizon_reason(raw)  # noqa: SLF001
    if endpoint.projection.policy_horizon_reason != expected_horizon:
        raise ValueError("v26.164 Raw-only recovery Horizon projection changed")

    old_values = {
        "job_id": job.job_id,
        "task_condition_cell_id": job.task_condition_cell_id,
        "task_package_id": job.task_package_id,
        "experimental_condition_id": job.experimental_condition.condition_id,
        "legacy_joint_measurement_projection": legacy,
        "bounded_policy_endpoint_record": endpoint,
    }
    direct_match = False
    if typed_rejection:
        if job.job_id in checkpoint_by_job:
            raise ValueError("v26.164 typed rejection unexpectedly entered direct checkpoint")
    else:
        provisional_old = execution_models.BoundedPolicyFrequencyMeasurementResult.model_construct(
            result_id="pending",
            **old_values,
        )
        old_result = execution_models.BoundedPolicyFrequencyMeasurementResult(
            result_id=execution_models.identity(
                provisional_old,
                "result_id",
                "finance_v26_bounded_policy_frequency_measurement_result:",
            ),
            **old_values,
        )
        checkpoint = checkpoint_by_job.get(job.job_id)
        if checkpoint is None or _canonical_bytes(checkpoint) != _canonical_bytes(old_result):
            raise ValueError("v26.164 direct checkpoint does not match independent Raw projection")
        direct_match = True

    values = {
        **old_values,
        "typed_semantic_rejection_validity_normalized": typed_rejection,
        "direct_checkpoint_byte_match": direct_match,
    }
    provisional = models.RawOnlyRecoveredMeasurementResult.model_construct(
        result_id="pending",
        **values,
    )
    result = models.RawOnlyRecoveredMeasurementResult(
        result_id=models.identity(
            provisional,
            "result_id",
            "finance_v26_bounded_policy_raw_only_measurement_result:",
        ),
        **values,
    )
    normalization = None
    if typed_rejection:
        normalization = models.TypedSemanticRejectionNormalizationRow(
            job_id=job.job_id,
            raw_execution_id=raw.artifact_id,
            terminal_failure_type=raw.terminal_failure_type,
            stage_one_provider_call_count=raw.stage_one_provider_call_count,
            transport_invocation_count=raw.transport_inclusive_invocation_count,
            provider_total_tokens=raw.cumulative_provider_tokens,
            raw_measurement_support_available=raw.measurement_support_available,
            raw_instrument_integrity=raw.instrument_integrity,
            raw_privacy_compliant=raw.privacy_compliant,
            before_task_completion=None,
            before_base_validity=legacy.base_trajectory_validity,
            before_mechanism_qualification=legacy.mechanism_qualification,
            before_qualified_validity=legacy.qualified_trajectory_validity,
            task_verifier_invocation_count=legacy.task_verifier_invocation_count,
        )
    return result, raw, normalization


def _normalization_audit(
    rows: Sequence[models.TypedSemanticRejectionNormalizationRow],
) -> models.TypedSemanticRejectionNormalizationAudit:
    ordered = tuple(sorted(rows, key=lambda item: item.job_id))
    values = {"rows": ordered}
    provisional = models.TypedSemanticRejectionNormalizationAudit.model_construct(
        audit_id="pending",
        **values,
    )
    return models.TypedSemanticRejectionNormalizationAudit(
        audit_id=models.identity(
            provisional,
            "audit_id",
            "finance_v26_bounded_policy_typed_rejection_normalization:",
        ),
        **values,
    )


def _freeze_audit(
    *,
    prepared: execution_models.PreparedBoundedPolicyExecution,
    failed_execution_dir: Path,
    implementation_root: Path,
    checkpoint_by_job: Mapping[str, execution_models.BoundedPolicyFrequencyMeasurementResult],
    raws: Mapping[str, runner_vnext.FreshReachabilityRawExecution],
    before_snapshot: tuple[int, int, str],
    after_snapshot: tuple[int, int, str],
) -> models.FailedExecutionFreezeAudit:
    if before_snapshot != after_snapshot:
        raise ValueError("v26.164 failed execution directory changed during Raw-only recovery")
    typed_ids = tuple(
        sorted(
            job_id
            for job_id, raw in raws.items()
            if raw.terminal_disposition == "typed_semantic_rejection"
        )
    )
    missing_ids = tuple(
        sorted(
            item.job_id for item in prepared.manifest.jobs if item.job_id not in checkpoint_by_job
        )
    )
    implementation_files = _implementation_files(implementation_root)
    values = {
        "failed_execution_directory_name": failed_execution_dir.name,
        "failed_source_replay_audit_id": prepared.source_replay.audit_id,
        "failed_preexecution_binding_audit_id": prepared.preexecution_binding.audit_id,
        "failed_execution_file_count": before_snapshot[0],
        "failed_execution_byte_count": before_snapshot[1],
        "failed_execution_content_root": before_snapshot[2],
        "missing_checkpoint_job_ids": missing_ids,
        "typed_semantic_rejection_job_ids": typed_ids,
        "provider_call_count": sum(item.stage_one_provider_call_count for item in raws.values()),
        "transport_invocation_count": sum(
            item.transport_inclusive_invocation_count for item in raws.values()
        ),
        "provider_artifact_triple_count": sum(
            len(item.provider_envelope_artifacts)
            + len(item.public_payload_projection_artifacts)
            + len(item.transport_invocation_artifacts)
            for item in raws.values()
        ),
        "provider_total_tokens": sum(item.cumulative_provider_tokens for item in raws.values()),
        "raw_instrument_failure_count": sum(
            not item.instrument_integrity for item in raws.values()
        ),
        "privacy_failure_count": sum(not item.privacy_compliant for item in raws.values()),
        "stage_two_provider_call_count": sum(
            item.stage_two_provider_call_count for item in raws.values()
        ),
        "implementation_files": implementation_files,
        "implementation_bundle_sha256": hashlib.sha256(
            _canonical_bytes(tuple(item.model_dump(mode="python") for item in implementation_files))
        ).hexdigest(),
    }
    provisional = models.FailedExecutionFreezeAudit.model_construct(
        audit_id="pending",
        **values,
    )
    return models.FailedExecutionFreezeAudit(
        audit_id=models.identity(
            provisional,
            "audit_id",
            "finance_v26_bounded_policy_failed_execution_freeze:",
        ),
        **values,
    )


def _detail(path: Path, output_dir: Path) -> models.DetailFile:
    return models.DetailFile(
        relative_path=str(path.resolve().relative_to(output_dir.resolve())),
        sha256=models.sha256(path),
        byte_count=path.stat().st_size,
    )


def _recovery_report(
    *,
    freeze: models.FailedExecutionFreezeAudit,
    normalization: models.TypedSemanticRejectionNormalizationAudit,
    execution_report: execution_models.BoundedPolicyExecutionReport,
    transition: execution_models.PostrunTransitionContract,
    detail_files: Sequence[models.DetailFile],
) -> models.RawOnlyRecoveryReport:
    values = {
        "failed_execution_freeze_audit_id": freeze.audit_id,
        "typed_semantic_rejection_normalization_audit_id": normalization.audit_id,
        "recovered_execution_report_id": execution_report.report_id,
        "global_integrity_gate_id": execution_report.global_integrity_gate_id,
        "endpoint_catalog_id": execution_report.endpoint_catalog_id,
        "horizon_reason_audit_id": execution_report.horizon_reason_audit_id,
        "raw_lineage_audit_id": execution_report.raw_lineage_audit_id,
        "mapper_execution_audit_id": execution_report.mapper_execution_audit_id,
        "assignment_catalog_id": execution_report.assignment_catalog_id,
        "cell_frequency_catalog_id": execution_report.cell_frequency_catalog_id,
        "postrun_transition_contract_id": transition.contract_id,
        "policy_horizon_endpoint_count": execution_report.policy_horizon_endpoint_count,
        "formal_assignment_count": execution_report.formal_assignment_count,
        "structural_state_count": execution_report.structural_state_count,
        "pi_instantiated_cell_count": execution_report.pi_instantiated_cell_count,
        "zero_qualified_cell_count": execution_report.zero_qualified_cell_count,
        "empirical_non_degenerate_cell_count": (
            execution_report.empirical_non_degenerate_cell_count
        ),
        "global_integrity_gate_passed": execution_report.global_integrity_gate_passed,
        "detail_files": tuple(sorted(detail_files, key=lambda item: item.relative_path)),
    }
    provisional = models.RawOnlyRecoveryReport.model_construct(report_id="pending", **values)
    return models.RawOnlyRecoveryReport(
        report_id=models.identity(
            provisional,
            "report_id",
            "finance_v26_bounded_policy_raw_only_recovery_report:",
        ),
        **values,
    )


def recover_bounded_policy_execution(
    *,
    preflight_dir: Path,
    failed_execution_dir: Path,
    output_dir: Path,
    package_root: Path,
    implementation_root: Path,
) -> models.RawOnlyRecoveryReport:
    report_path = output_dir / "report.json"
    if report_path.is_file():
        return models.RawOnlyRecoveryReport.model_validate(_load(report_path))
    if os.environ.get("DEEPSEEK_API_KEY"):
        raise ValueError("v26.164 Raw-only recovery requires credential removal")
    if not failed_execution_dir.is_dir() or (failed_execution_dir / "report.json").exists():
        raise ValueError("v26.164 Raw-only recovery requires the immutable failed v1 directory")
    output_dir.mkdir(parents=True, exist_ok=True)
    before_snapshot = _directory_snapshot(failed_execution_dir)
    prepared = _prepare_from_failed_freeze(
        preflight_dir=preflight_dir,
        failed_execution_dir=failed_execution_dir,
        package_root=package_root,
        implementation_root=implementation_root,
    )
    checkpoint = execution._load_checkpoint(  # noqa: SLF001
        failed_execution_dir / execution.CHECKPOINT_NAME,
        prepared=prepared,
        output_dir=failed_execution_dir,
    )
    checkpoint_by_job = {item.job_id: item for item in checkpoint}
    if len(checkpoint_by_job) != 358:
        raise ValueError("v26.164 failed v1 direct checkpoint denominator changed")

    results = []
    raws: dict[str, runner_vnext.FreshReachabilityRawExecution] = {}
    normalization_rows = []
    for index, job in enumerate(prepared.manifest.jobs, start=1):
        result, raw, normalization = _make_result(
            job=job,
            prepared=prepared,
            failed_execution_dir=failed_execution_dir,
            checkpoint_by_job=checkpoint_by_job,
        )
        results.append(result)
        raws[job.job_id] = raw
        if normalization is not None:
            normalization_rows.append(normalization)
        if index % 40 == 0 or index == 360:
            print(
                "[v26.164 recovery] Raw-only projection "
                f"{index}/360 typed_normalized={len(normalization_rows)} provider_calls=0",
                flush=True,
            )
    ordered_results = tuple(results)
    if len(raws) != 360 or len(ordered_results) != 360:
        raise ValueError("v26.164 Raw-only recovered denominator changed")
    normalization = _normalization_audit(normalization_rows)
    gate = execution._global_gate(ordered_results, complete_raw_count=len(raws))  # noqa: SLF001
    if not gate.passed:
        raise ValueError(f"v26.164 recovered Global Gate failed: {gate.failure_ids}")
    assignments, mapper = execution._map_after_global_gate(  # noqa: SLF001
        prepared=prepared,
        results=ordered_results,
        raws=raws,
        gate=gate,
    )
    cells = execution._cell_frequencies(  # noqa: SLF001
        prepared=prepared,
        results=ordered_results,
        gate=gate,
        assignments=assignments,
    )
    horizon = execution._horizon_reason_audit(  # noqa: SLF001
        results=ordered_results,
        raws=raws,
    )
    endpoints = execution._endpoint_catalog(  # noqa: SLF001
        results=ordered_results,
        horizon=horizon,
    )
    lineage = execution._raw_lineage(  # noqa: SLF001
        results=ordered_results,
        raws=raws,
        output_dir=failed_execution_dir,
    )
    after_snapshot = _directory_snapshot(failed_execution_dir)
    freeze = _freeze_audit(
        prepared=prepared,
        failed_execution_dir=failed_execution_dir,
        implementation_root=implementation_root,
        checkpoint_by_job=checkpoint_by_job,
        raws=raws,
        before_snapshot=before_snapshot,
        after_snapshot=after_snapshot,
    )

    aggregate_outputs: tuple[tuple[str, Any], ...] = (
        ("failed_execution_freeze_audit.json", freeze),
        ("typed_semantic_rejection_normalization_audit.json", normalization),
        ("bounded_policy_measurement_results.json", ordered_results),
        ("bounded_policy_global_integrity_gate.json", gate),
        ("bounded_policy_endpoint_catalog.json", endpoints),
        ("bounded_policy_horizon_reason_audit.json", horizon),
        ("bounded_policy_assignment_catalog.json", assignments),
        ("mapper_execution_audit.json", mapper),
        ("bounded_policy_cell_frequency_catalog.json", cells),
        ("raw_lineage_audit.json", lineage),
    )
    for name, value in aggregate_outputs:
        _write_json_once(output_dir / name, value)
    execution_details = tuple(
        execution._detail(output_dir / name, output_dir)  # noqa: SLF001
        for name, _ in aggregate_outputs[2:]
    )
    execution_report = execution._execution_report(  # noqa: SLF001
        prepared=prepared,
        results=ordered_results,
        gate=gate,
        endpoints=endpoints,
        horizon=horizon,
        lineage=lineage,
        mapper=mapper,
        assignments=assignments,
        cells=cells,
        detail_files=execution_details,
    )
    _write_json_once(output_dir / "bounded_policy_execution_report.json", execution_report)
    transition = execution._transition(  # noqa: SLF001
        report=execution_report,
        gate=gate,
        endpoints=endpoints,
        assignments=assignments,
        cells=cells,
    )
    _write_json_once(output_dir / "postrun_transition_contract.json", transition)
    report_names = (
        *(name for name, _ in aggregate_outputs),
        "bounded_policy_execution_report.json",
        "postrun_transition_contract.json",
    )
    detail_files = tuple(_detail(output_dir / name, output_dir) for name in report_names)
    report = _recovery_report(
        freeze=freeze,
        normalization=normalization,
        execution_report=execution_report,
        transition=transition,
        detail_files=detail_files,
    )
    _write_json_once(report_path, report)
    return report


def main() -> None:
    package_default = Path(__file__).resolve().parents[4]
    parser = argparse.ArgumentParser(
        description="Recover the complete v26.164 Route B denominator from immutable Raw only"
    )
    parser.add_argument(
        "--preflight-dir",
        type=Path,
        default=package_default / execution_models.PREFLIGHT_DIR,
    )
    parser.add_argument(
        "--failed-execution-dir",
        type=Path,
        default=package_default / models.FAILED_EXECUTION_DIR,
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=package_default / models.OUTPUT_DIR,
    )
    parser.add_argument("--package-root", type=Path, default=package_default)
    parser.add_argument("--implementation-root", type=Path, default=package_default)
    args = parser.parse_args()
    report = recover_bounded_policy_execution(
        preflight_dir=args.preflight_dir,
        failed_execution_dir=args.failed_execution_dir,
        output_dir=args.output_dir,
        package_root=args.package_root,
        implementation_root=args.implementation_root,
    )
    print(report.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
