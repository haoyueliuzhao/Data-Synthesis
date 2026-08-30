from __future__ import annotations

import argparse
import hashlib
import inspect
import json
import sys
import tempfile
from pathlib import Path
from typing import Any, cast


def _configure_exact_source(package_root: Path) -> None:
    source_root = package_root / "src"
    if not (source_root / "trusted_synthesis").is_dir():
        raise ValueError("independent runner package root lacks exact source")
    sys.path.insert(0, str(source_root))


def _build_context(package_root: Path) -> dict[str, Any]:
    from trusted_synthesis.experiments.vtdo_experiment import (
        phase1_v26_capability_authoritative_outcome_terminal_preflight as preflight,
    )

    frozen = preflight._load_frozen_inputs(package_root)
    registry_audit = preflight._terminal_registry(
        package_root=package_root,
        frozen=frozen,
    )
    registry = registry_audit.registry
    contract = preflight._outcome_contract(frozen=frozen, registry=registry)
    catalogs = preflight._scripted_catalogs(frozen=frozen, registry=registry)
    return {
        "preflight": preflight,
        "frozen": frozen,
        "registry": registry,
        "contract": contract,
        "catalogs": catalogs,
    }


def _rehash(
    model_type: type[Any],
    source: Any,
    updates: dict[str, Any],
    *,
    identity_field: str,
    prefix: str,
) -> Any:
    from trusted_synthesis.core.task.authoritative_job_bound_outcome import (
        make_identity_model,
    )

    values = source.model_dump(mode="python", exclude={identity_field}, warnings=False)
    values.update(updates)
    return make_identity_model(
        model_type,
        values,
        field=identity_field,
        prefix=prefix,
    )


def _mixed_completion_controls(context: dict[str, Any]) -> list[dict[str, Any]]:
    from trusted_synthesis.core.task.job_bound_multistep_outcome import (
        JobBoundOutcomePayload,
        make_identity_model,
    )
    from trusted_synthesis.experiments.vtdo_experiment import (
        phase1_v26_capability_authoritative_outcome_terminal_preflight_runtime as runtime,
    )

    frozen = context["frozen"]
    registry = context["registry"]
    source_row = next(
        item.outcome
        for item in frozen.branches.rows
        if item.scenario == "accepted_first_action_downstream_task_invalid"
    )
    source = source_row.outcome
    job = next(item for item in frozen.manifest.jobs if item.job_id == source_row.job_id)
    rows: list[dict[str, Any]] = []
    for base_valid, mechanism_qualified in ((True, False), (False, True)):
        values = source.model_dump(
            mode="python",
            exclude={"attempt_trace_id"},
            warnings=False,
        )
        values.update(
            {
                "final_base_valid": base_valid,
                "final_mechanism_qualified": mechanism_qualified,
                "final_qualified_valid": False,
                "first_policy_qualified_valid": False,
                "bounded_policy_qualified_valid": False,
                "endpoint_kind": "completed_invalid",
            }
        )
        mixed = cast(
            JobBoundOutcomePayload,
            make_identity_model(
                JobBoundOutcomePayload,
                values,
                field="attempt_trace_id",
                prefix="capability_job_attempt_trace:",
            ),
        )
        bundle = runtime.build_authoritative_bundle(
            job=job,
            manifest=frozen.manifest,
            runner=frozen.runner,
            registry=registry,
            terminal_kind="completed_invalid",
            evidence_kind="scripted_preflight_control",
            source_outcome=mixed,
        )
        observed = (
            bundle.row.final_base_valid,
            bundle.row.final_mechanism_qualified,
        )
        rows.append(
            {
                "control": (
                    "completed_invalid_base_true_mechanism_false"
                    if base_valid
                    else "completed_invalid_base_false_mechanism_true"
                ),
                "source_outcome_validated": True,
                "source_attempt_trace_id": mixed.attempt_trace_id,
                "source_base_valid": base_valid,
                "source_mechanism_qualified": mechanism_qualified,
                "projected_base_valid": observed[0],
                "projected_mechanism_qualified": observed[1],
                "semantic_state_preserved": observed == (base_valid, mechanism_qualified),
            }
        )
    return rows


def _empirical_bundles(context: dict[str, Any]) -> list[Any]:
    from trusted_synthesis.experiments.vtdo_experiment import (
        phase1_v26_capability_authoritative_outcome_terminal_preflight_runtime as runtime,
    )

    frozen = context["frozen"]
    registry = context["registry"]
    scripted_by_job = {item.job_id: item for item in frozen.scripted.rows}
    return [
        runtime.build_authoritative_bundle(
            job=job,
            manifest=frozen.manifest,
            runner=frozen.runner,
            registry=registry,
            terminal_kind="completed_qualified",
            evidence_kind="empirical_execution",
            source_outcome=scripted_by_job[job.job_id].outcome,
        )
        for job in frozen.manifest.jobs
    ]


def _evaluate_bundles(context: dict[str, Any], bundles: list[Any]) -> Any:
    from trusted_synthesis.core.task.authoritative_job_bound_outcome import (
        evaluate_exact_evidence_set,
    )

    frozen = context["frozen"]
    return evaluate_exact_evidence_set(
        raws=tuple(item.raw for item in bundles),
        results=tuple(item.result for item in bundles),
        traces=tuple(item.trace for item in bundles),
        rows=tuple(item.row for item in bundles),
        manifest=frozen.manifest,
        registry=context["registry"],
        contract=context["contract"],
        runner_id=frozen.runner.runner_id,
        expected_evidence_kind="empirical_execution",
    )


def _diagnostic_empirical_controls(
    context: dict[str, Any],
    baseline: list[Any],
) -> list[dict[str, Any]]:
    from trusted_synthesis.experiments.vtdo_experiment import (
        phase1_v26_capability_authoritative_outcome_terminal_preflight_runtime as runtime,
    )

    frozen = context["frozen"]
    registry = context["registry"]
    contract = context["contract"]
    policies = {item.terminal_kind: item for item in registry.policies}
    job = frozen.manifest.jobs[0]
    sequence = next(
        item.ordered_component_keys
        for item in contract.job_component_sequences
        if item.job_id == job.job_id
    )
    rows: list[dict[str, Any]] = []
    for terminal_kind in ("policy_horizon_exhausted", "measurement_support_exit"):
        diagnostic = runtime.build_authoritative_bundle(
            job=job,
            manifest=frozen.manifest,
            runner=frozen.runner,
            registry=registry,
            terminal_kind=terminal_kind,
            evidence_kind="empirical_execution",
            component_key=sequence[0],
        )
        attacked = list(baseline)
        attacked[0] = diagnostic
        evaluation = _evaluate_bundles(context, attacked)
        rows.append(
            {
                "control": f"{terminal_kind}_diagnostic_to_empirical",
                "terminal_kind": terminal_kind,
                "registration_status": policies[terminal_kind].registration_status,
                "estimator_admitted": True,
                "evaluation_id": evaluation.evaluation_id,
                "empirical": evaluation.empirical,
                "denominator_count": evaluation.outcome_row_count,
                "terminal_count_in_denominator": evaluation.terminal_kind_counts[terminal_kind],
            }
        )
    return rows


def _forge_locus_bundle(
    context: dict[str, Any],
    baseline: Any,
    *,
    stage: str,
    component_key: str | None,
    attempt_index: int | None,
    reason_code: str,
) -> tuple[Any, Any, Any, Any, Any]:
    from trusted_synthesis.core.task.authoritative_job_bound_outcome import (
        AuthoritativeCapabilityOutcomeRow,
        FailureLocus,
        JobBoundAttemptTrace,
        JobResultDescriptor,
        JobResultEvidencePayload,
        make_identity_model,
    )

    locus = make_identity_model(
        FailureLocus,
        {
            "stage": stage,
            "component_key": component_key,
            "attempt_index": attempt_index,
            "reason_code": reason_code,
            "evaluability": "evaluated_false",
            "source_descriptor_id": baseline.raw.raw_execution_id,
        },
        field="locus_id",
        prefix="capability_authoritative_failure_locus:",
    )
    result_payload = _rehash(
        JobResultEvidencePayload,
        baseline.result.payload,
        {"failure_locus_ids": (locus.locus_id,)},
        identity_field="payload_id",
        prefix="capability_authoritative_job_result_payload:",
    )
    result = _rehash(
        JobResultDescriptor,
        baseline.result,
        {"payload": result_payload},
        identity_field="result_id",
        prefix="capability_authoritative_job_result_descriptor:",
    )
    trace = _rehash(
        JobBoundAttemptTrace,
        baseline.trace,
        {"result_id": result.result_id, "failure_loci": (locus,)},
        identity_field="trace_id",
        prefix="capability_authoritative_job_bound_attempt_trace:",
    )
    row_updates: dict[str, Any] = {
        "result_id": result.result_id,
        "trace_id": trace.trace_id,
        "terminal_locus_id": locus.locus_id,
    }
    if stage in {"base_answer", "base_citation"}:
        row_updates["first_base_invalid_locus_id"] = locus.locus_id
    if stage == "mechanism":
        row_updates["first_mechanism_failed_locus_id"] = locus.locus_id
    row = _rehash(
        AuthoritativeCapabilityOutcomeRow,
        baseline.row,
        row_updates,
        identity_field="row_id",
        prefix="capability_authoritative_outcome_row:",
    )
    return baseline.raw, result, trace, row, locus


def _failure_locus_controls(context: dict[str, Any], baseline: Any) -> list[dict[str, Any]]:
    from trusted_synthesis.core.task.authoritative_job_bound_outcome import (
        validate_authoritative_bundle,
    )

    frozen = context["frozen"]
    job = frozen.manifest.jobs[0]
    controls = (
        (
            "completed_qualified_with_forged_base_locus",
            "base_answer",
            None,
            None,
            "forged_base_failure",
        ),
        (
            "completed_qualified_with_crossed_component_locus",
            "mechanism",
            "forged:component:not-in-trace",
            0,
            "forged_mechanism_failure",
        ),
    )
    rows: list[dict[str, Any]] = []
    for control, stage, component_key, attempt_index, reason in controls:
        raw, result, trace, row, locus = _forge_locus_bundle(
            context,
            baseline,
            stage=stage,
            component_key=component_key,
            attempt_index=attempt_index,
            reason_code=reason,
        )
        validate_authoritative_bundle(
            job=job,
            manifest=frozen.manifest,
            runner_id=frozen.runner.runner_id,
            registry=context["registry"],
            contract=context["contract"],
            raw=raw,
            result=result,
            trace=trace,
            row=row,
            expected_evidence_kind="empirical_execution",
        )
        rows.append(
            {
                "control": control,
                "fully_rehashed": True,
                "validator_admitted": True,
                "terminal_kind": row.terminal_kind,
                "final_qualified_valid": row.final_qualified_valid,
                "locus_id": locus.locus_id,
                "locus_stage": locus.stage,
                "locus_component_key": locus.component_key,
                "locus_attempt_index": locus.attempt_index,
            }
        )
    return rows


def _artifact_byte_control(context: dict[str, Any], baseline: Any) -> dict[str, Any]:
    from trusted_synthesis.core.task.authoritative_job_bound_outcome import (
        JobResultDescriptor,
        RawExecutionDescriptor,
        validate_authoritative_bundle,
    )

    frozen = context["frozen"]
    job = frozen.manifest.jobs[0]
    with tempfile.TemporaryDirectory(prefix="v26_181_byte_control_") as directory:
        root = Path(directory)
        raw_path = root / baseline.raw.raw_artifact_path
        result_path = root / baseline.result.result_artifact_path
        raw_path.parent.mkdir(parents=True, exist_ok=True)
        result_path.parent.mkdir(parents=True, exist_ok=True)
        raw_path.write_bytes(b'{"payload":"first"}\n')
        result_path.write_bytes(b'{"payload":"first"}\n')
        before_sha = hashlib.sha256(raw_path.read_bytes() + result_path.read_bytes()).hexdigest()
        validate_authoritative_bundle(
            job=job,
            manifest=frozen.manifest,
            runner_id=frozen.runner.runner_id,
            registry=context["registry"],
            contract=context["contract"],
            raw=baseline.raw,
            result=baseline.result,
            trace=baseline.trace,
            row=baseline.row,
            expected_evidence_kind="empirical_execution",
        )
        raw_path.write_bytes(b'{"payload":"mutated"}\n')
        result_path.write_bytes(b'{"payload":"mutated"}\n')
        after_sha = hashlib.sha256(raw_path.read_bytes() + result_path.read_bytes()).hexdigest()
        validate_authoritative_bundle(
            job=job,
            manifest=frozen.manifest,
            runner_id=frozen.runner.runner_id,
            registry=context["registry"],
            contract=context["contract"],
            raw=baseline.raw,
            result=baseline.result,
            trace=baseline.trace,
            row=baseline.row,
            expected_evidence_kind="empirical_execution",
        )
    parameters = inspect.signature(validate_authoritative_bundle).parameters
    return {
        "control": "raw_result_path_same_bytes_changed",
        "before_combined_sha256": before_sha,
        "after_combined_sha256": after_sha,
        "bytes_changed": before_sha != after_sha,
        "validator_admitted_before": True,
        "validator_admitted_after": True,
        "validator_accepts_artifact_root": "artifact_root" in parameters,
        "raw_descriptor_binds_sha256": "raw_artifact_sha256" in RawExecutionDescriptor.model_fields,
        "raw_descriptor_binds_byte_count": "raw_artifact_byte_count"
        in RawExecutionDescriptor.model_fields,
        "result_descriptor_binds_sha256": "result_artifact_sha256"
        in JobResultDescriptor.model_fields,
        "result_descriptor_binds_byte_count": "result_artifact_byte_count"
        in JobResultDescriptor.model_fields,
    }


def _invalid_parent_is_rejected(model_type: type[Any], value: Any) -> bool:
    try:
        model_type.model_validate(value.model_dump(mode="python", warnings=False))
    except Exception:
        return True
    return False


def _field_values(value: Any) -> dict[str, Any]:
    return {field: getattr(value, field) for field in type(value).model_fields}


def _parent_injection_controls(
    context: dict[str, Any],
    baseline: list[Any],
) -> list[dict[str, Any]]:
    from trusted_synthesis.core.task.authoritative_job_bound_outcome import (
        AuthoritativeJobBoundOutcomeContract,
        AuthoritativeTerminalRegistry,
        evaluate_exact_evidence_set,
    )
    from trusted_synthesis.core.task.job_bound_multistep_outcome import (
        CapabilityDevelopmentJobManifest,
    )

    frozen = context["frozen"]
    registry = context["registry"]
    contract = context["contract"]
    cases: list[tuple[str, type[Any], Any, Any, Any]] = []

    registry_values = _field_values(registry)
    registry_values["unmapped_source_label_count"] = 1
    forged_registry = AuthoritativeTerminalRegistry.model_construct(**registry_values)
    cases.append(
        (
            "invalid_registry_model_construct_injection",
            AuthoritativeTerminalRegistry,
            forged_registry,
            contract,
            frozen.manifest,
        )
    )

    contract_values = _field_values(contract)
    contract_values["formal_empirical_rows_materialized"] = True
    forged_contract = AuthoritativeJobBoundOutcomeContract.model_construct(**contract_values)
    cases.append(
        (
            "invalid_contract_model_construct_injection",
            AuthoritativeJobBoundOutcomeContract,
            registry,
            forged_contract,
            frozen.manifest,
        )
    )

    manifest_values = _field_values(frozen.manifest)
    manifest_values["provider_calls"] = 1
    forged_manifest = CapabilityDevelopmentJobManifest.model_construct(**manifest_values)
    cases.append(
        (
            "invalid_manifest_model_construct_injection",
            CapabilityDevelopmentJobManifest,
            registry,
            contract,
            forged_manifest,
        )
    )

    rows: list[dict[str, Any]] = []
    for control, model_type, selected_registry, selected_contract, selected_manifest in cases:
        invalid_parent = (
            selected_registry
            if model_type is AuthoritativeTerminalRegistry
            else selected_contract
            if model_type is AuthoritativeJobBoundOutcomeContract
            else selected_manifest
        )
        rejected_on_direct_revalidation = _invalid_parent_is_rejected(model_type, invalid_parent)
        evaluation = evaluate_exact_evidence_set(
            raws=tuple(item.raw for item in baseline),
            results=tuple(item.result for item in baseline),
            traces=tuple(item.trace for item in baseline),
            rows=tuple(item.row for item in baseline),
            manifest=selected_manifest,
            registry=selected_registry,
            contract=selected_contract,
            runner_id=frozen.runner.runner_id,
            expected_evidence_kind="empirical_execution",
        )
        rows.append(
            {
                "control": control,
                "parent_model": model_type.__name__,
                "direct_parent_revalidation_rejected": rejected_on_direct_revalidation,
                "production_estimator_admitted": True,
                "evaluation_id": evaluation.evaluation_id,
            }
        )
    return rows


def run(package_root: Path) -> dict[str, Any]:
    context = _build_context(package_root)
    empirical = _empirical_bundles(context)
    baseline_evaluation = _evaluate_bundles(context, empirical)
    return {
        "schema_version": "v26_181_independent_negative_control_runner.v1",
        "exact_package_root": str(package_root),
        "baseline_empirical_evaluation_id": baseline_evaluation.evaluation_id,
        "mixed_completion_controls": _mixed_completion_controls(context),
        "diagnostic_empirical_controls": _diagnostic_empirical_controls(context, empirical),
        "failure_locus_controls": _failure_locus_controls(context, empirical[0]),
        "artifact_byte_control": _artifact_byte_control(context, empirical[0]),
        "parent_injection_controls": _parent_injection_controls(context, empirical),
        "provider_calls": 0,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--package-root", type=Path, required=True)
    args = parser.parse_args()
    package_root = args.package_root.resolve()
    _configure_exact_source(package_root)
    payload = run(package_root)
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")))


if __name__ == "__main__":
    main()
