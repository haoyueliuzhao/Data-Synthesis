from __future__ import annotations

import argparse
import json
import os
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Final, cast

from trusted_synthesis.canonical_json import strict_canonical_hash
from trusted_synthesis.core.evaluation.bounded_policy_endpoint import (
    BoundedPolicyGlobalIntegrityGate,
    PolicyHorizonReason,
    make_bounded_policy_endpoint_projection,
    make_bounded_policy_global_integrity_gate,
    summarize_bounded_policy_cell,
)
from trusted_synthesis.core.evaluation.valid_only_state_mapping_v2 import (
    make_qualified_verifier_input_binding_v2,
)
from trusted_synthesis.core.trajectory.empirical_state_mapping_v2 import (
    make_empirical_route_signature_v2,
    map_independently_valid_public_trajectory_to_state_v2,
)
from trusted_synthesis.core.trajectory.reference_empirical_state_mapping_v2 import (
    reference_map_public_trajectory_v2,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_bounded_policy_endpoint_frequency_execution as execution,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_bounded_policy_endpoint_frequency_execution_models as execution_models,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_bounded_policy_endpoint_frequency_postrun_audit_models as models,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_bounded_policy_endpoint_frequency_raw_only_recovery as recovery,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_bounded_policy_endpoint_frequency_raw_only_recovery_models as recovery_models,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_reachability_execution as execution_base,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_reachability_postrun_audit as independent,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_valid_only_reachability_state_mapping_preflight as mapping_preflight,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_valid_only_state_semantics_audit as state_semantics,
)
from trusted_synthesis.hashing import canonical_hash
from trusted_synthesis.runtime.agent import prospective_reachability_runner_vnext as runner_vnext

IMPLEMENTATION_PATH: Final = models.IMPLEMENTATION_PATH
MODEL_IMPLEMENTATION_PATH: Final = models.MODEL_IMPLEMENTATION_PATH
IMPLEMENTATION_PATHS: Final = (
    execution_models.RUNNER_IMPLEMENTATION_PATH,
    execution_models.MODEL_IMPLEMENTATION_PATH,
    recovery_models.RUNNER_IMPLEMENTATION_PATH,
    recovery_models.MODEL_IMPLEMENTATION_PATH,
    IMPLEMENTATION_PATH,
    MODEL_IMPLEMENTATION_PATH,
)
HORIZON_REASONS: Final[tuple[PolicyHorizonReason, ...]] = (
    "ordinary_detour_limit",
    "primary_request_limit",
    "provider_call_limit",
    "rollout_token_limit",
    "transport_invocation_limit",
)


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json_once(path: Path, value: Any) -> None:
    payload = models.canonical_bytes(value)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_bytes() != payload:
            raise ValueError(f"v26.165 immutable audit artifact changed: {path}")
        return
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(payload)
    temporary.replace(path)


def _directory_snapshot(root: Path, *, prefix: str) -> tuple[int, int, str]:
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
        strict_canonical_hash(entries, prefix=prefix),
    )


def _source_replay(
    *,
    failed_execution_dir: Path,
    recovery_dir: Path,
    implementation_root: Path,
) -> models.PostrunSourceReplayAudit:
    failed = _directory_snapshot(
        failed_execution_dir,
        prefix="finance_v26_bounded_policy_failed_execution_content_root:",
    )
    recovered = _directory_snapshot(
        recovery_dir,
        prefix="finance_v26_bounded_policy_postrun_directory_root:",
    )
    freeze = recovery_models.FailedExecutionFreezeAudit.model_validate(
        _load(recovery_dir / "failed_execution_freeze_audit.json")
    )
    if (
        failed
        != (
            freeze.failed_execution_file_count,
            freeze.failed_execution_byte_count,
            freeze.failed_execution_content_root,
        )
        or recovered[0] != 13
    ):
        raise ValueError("v26.165 predecessor directory Freeze changed")
    bindings = []
    for relative_path in sorted(IMPLEMENTATION_PATHS):
        path = implementation_root / relative_path
        bindings.append(
            models.SourceBinding(
                relative_path=relative_path,
                sha256=models.sha256(path),
                byte_count=path.stat().st_size,
            )
        )
    values = {
        "failed_execution_file_count": failed[0],
        "failed_execution_byte_count": failed[1],
        "failed_execution_content_root": failed[2],
        "recovery_file_count": recovered[0],
        "recovery_byte_count": recovered[1],
        "recovery_content_root": recovered[2],
        "implementation_files": tuple(bindings),
    }
    provisional = models.PostrunSourceReplayAudit.model_construct(
        audit_id="pending",
        **values,
    )
    return models.PostrunSourceReplayAudit(
        audit_id=models.identity(
            provisional,
            "audit_id",
            "finance_v26_bounded_policy_postrun_source_replay:",
        ),
        **values,
    )


def _independent_inputs(
    prepared: execution_models.PreparedBoundedPolicyExecution,
) -> independent.AuditInputs:
    return independent.AuditInputs(
        report=cast(Any, prepared.preflight_report),
        manifest=cast(Any, prepared.manifest),
        tasks=prepared.tasks,
        paths=prepared.paths,
        frozen_input=cast(Any, SimpleNamespace(audit_id=prepared.source_selection.audit_id)),
        resource=prepared.resource,
        runner_contract=cast(Any, prepared.runner_contract),
        joint_contract=prepared.joint_contract,
        grammar=prepared.grammar,
        role_inputs=prepared.legacy_prepared.role_inputs,
        replay_contract=prepared.legacy_prepared.replay_contract,
    )


def _horizon_reason(raw: runner_vnext.FreshReachabilityRawExecution) -> PolicyHorizonReason | None:
    failure = str(raw.terminal_failure_type or "")
    if (
        raw.terminal_disposition == "measurement_support_exit"
        and failure == "ordinary_detour_allowance_exhausted"
    ):
        return "ordinary_detour_limit"
    if failure == "semantic_action_primary_request_limit_exhausted":
        return "primary_request_limit"
    if raw.terminal_disposition != "typed_budget_no_call":
        return None
    if "transport" in failure:
        return "transport_invocation_limit"
    if failure == "stage_one_request_count_exhausted":
        return "provider_call_limit"
    if failure in {
        "request_bound_exceeds_remaining_budget",
        "required_reserve_not_available",
    }:
        return "rollout_token_limit"
    raise ValueError("v26.165 independently found an undeclared budget Horizon")


def _terminal_class(
    raw: runner_vnext.FreshReachabilityRawExecution,
    horizon: PolicyHorizonReason | None,
) -> str:
    if horizon is not None:
        return "policy_horizon_exhausted"
    return {
        "completed_model_endpoint": "completed_model_endpoint",
        "model_result_failure": "model_result_failure",
        "typed_semantic_rejection": "model_typed_rejection",
        "measurement_support_exit": "measurement_support_exit",
        "instrument_failure": "instrument_failure",
        "privacy_rejection": "privacy_failure",
        "provider_transport_failure": "provider_transport_failure",
    }[raw.terminal_disposition]


def _resource_integrity(
    raw: runner_vnext.FreshReachabilityRawExecution,
    prepared: execution_models.PreparedBoundedPolicyExecution,
) -> bool:
    return bool(
        raw.cumulative_provider_tokens <= prepared.policy.maximum_rollout_tokens
        and raw.stage_one_provider_call_count <= prepared.policy.maximum_provider_calls
        and raw.transport_inclusive_invocation_count
        <= prepared.policy.maximum_transport_invocations
    )


def _independent_endpoint_rows(
    *,
    prepared: execution_models.PreparedBoundedPolicyExecution,
    failed_execution_dir: Path,
    recovery_dir: Path,
) -> tuple[
    tuple[models.IndependentEndpointRow, ...],
    models.IndependentProviderArtifactAudit,
    dict[str, runner_vnext.FreshReachabilityRawExecution],
    dict[str, execution_base.ReachabilityMeasurementResult],
]:
    packages = {item.task_package_id: item for item in prepared.tasks.packages}
    production_results = tuple(
        recovery_models.RawOnlyRecoveredMeasurementResult.model_validate(item)
        for item in _load(recovery_dir / "bounded_policy_measurement_results.json")
    )
    production_by_job = {item.job_id: item for item in production_results}
    inputs = _independent_inputs(prepared)
    rows = []
    raws: dict[str, runner_vnext.FreshReachabilityRawExecution] = {}
    independent_results: dict[str, execution_base.ReachabilityMeasurementResult] = {}
    envelope_count = projection_count = transport_count = 0
    exact_failures = thinking_failures = usage_failures = privacy_failures = 0
    unresolved_transport = stage_two_calls = 0
    prompt_tokens = completion_tokens = reasoning_tokens = total_tokens = 0
    for index, job in enumerate(sorted(prepared.manifest.jobs, key=lambda item: item.job_id), 1):
        raw_path = runner_vnext._raw_path(failed_execution_dir, job)  # noqa: SLF001
        raw = runner_vnext.FreshReachabilityRawExecution.model_validate(_load(raw_path))
        if raw.job_id != job.job_id or raw.job_payload != job.model_dump(mode="json"):
            raise ValueError("v26.165 Raw crossed the exact frozen Job")
        pairs = independent._provider_pairs(raw, failed_execution_dir)  # noqa: SLF001
        exact_model, fallback_absent, native_absent, thinking, usage = (
            independent.semantic_online._telemetry_flags(raw.provider_telemetry)  # noqa: SLF001
        )
        request_binding = all(
            item.dynamic_certificate_id is not None
            and item.resource_certificate_id is not None
            and item.request_binding_certificate_id is not None
            for item in raw.attempts
            if item.provider_call_made
        )
        pairing = bool(
            len(pairs)
            == len(raw.provider_envelope_artifacts)
            == len(raw.public_payload_projection_artifacts)
            == raw.stage_one_provider_call_count
            == len(raw.transport_invocation_artifacts)
        )
        reversible = all(
            item.reversible_same_action_id_passed
            and not item.semantic_choice_inserted_by_host
            and item.stage_two_provider_calls == 0
            for item in raw.commits
        )
        resource = _resource_integrity(raw, prepared)
        privacy = bool(
            raw.privacy_compliant
            and raw.privacy_rejected_payload_count == 0
            and all(projection.projection_status != "privacy_rejected" for _, projection in pairs)
            and pairing
        )
        transport_resolved = raw.terminal_disposition != "provider_transport_failure"
        provider_identity = bool(
            exact_model
            and fallback_absent
            and native_absent
            and request_binding
            and pairing
            and reversible
            and raw.stage_two_provider_call_count == 0
        )
        horizon = _horizon_reason(raw)
        model_terminal = independent._endpoint_observed(raw)  # noqa: SLF001
        support_available = bool(
            horizon is not None
            or (
                raw.measurement_support_available
                and raw.terminal_disposition != "measurement_support_exit"
                and all(item.status != "unavailable" for item in raw.measurement_support_decisions)
            )
        )
        integrity = bool(
            raw.instrument_integrity
            and resource
            and provider_identity
            and thinking
            and usage
            and privacy
            and transport_resolved
        )
        task_completion: bool | None = None
        base_valid: bool | None = None
        mechanism_qualified: bool | None = None
        qualified_valid: bool | None = None
        verifier_calls = 0
        if horizon is not None:
            task_completion = False
            base_valid = False
            mechanism_qualified = False
            qualified_valid = False
        elif model_terminal and support_available and integrity:
            package = packages[job.task_package_id]
            independent_result = independent._project_measurement_independently(  # noqa: SLF001
                raw=raw,
                job=cast(Any, job),
                package=package,
                inputs=inputs,
                execution_dir=failed_execution_dir,
            )
            independent_results[job.job_id] = independent_result
            if raw.terminal_disposition == "typed_semantic_rejection":
                if (
                    independent_result.validity_evaluable
                    or independent_result.base_trajectory_validity is not None
                    or independent_result.mechanism_qualification is not None
                    or independent_result.qualified_trajectory_validity is not None
                    or independent_result.task_verifier_invocation_count != 0
                ):
                    raise ValueError(
                        f"v26.165 typed rejection legacy-null boundary changed: {job.job_id}"
                    )
                task_completion = False
                base_valid = False
                mechanism_qualified = False
                qualified_valid = False
            else:
                if not independent_result.validity_evaluable:
                    raise ValueError(
                        "v26.165 independent Verifier rejected an eligible endpoint: "
                        f"job={job.job_id} terminal={raw.terminal_disposition} "
                        f"failure={raw.terminal_failure_type} "
                        f"base={independent_result.base_trajectory_validity} "
                        f"mechanism={independent_result.mechanism_qualification} "
                        f"qualified={independent_result.qualified_trajectory_validity}"
                    )
                task_completion = raw.terminal_disposition == "completed_model_endpoint"
                base_valid = bool(independent_result.base_trajectory_validity is True)
                mechanism_qualified = bool(independent_result.mechanism_qualification is True)
                qualified_valid = bool(independent_result.qualified_trajectory_validity is True)
                verifier_calls = independent_result.task_verifier_invocation_count
        endpoint = make_bounded_policy_endpoint_projection(
            trajectory_id=raw.artifact_id,
            generation_policy_id=prepared.policy.policy_id,
            terminal_class=cast(Any, _terminal_class(raw, horizon)),
            policy_horizon_reason=horizon,
            raw_instrument_integrity=raw.instrument_integrity,
            measurement_support_available=support_available,
            resource_accounting_integrity=resource,
            provider_identity_integrity=provider_identity,
            thinking_usage_integrity=bool(thinking and usage),
            privacy_compliant=privacy,
            transport_resolved=transport_resolved,
            model_terminal_observed=model_terminal,
            task_completion=task_completion,
            base_validity=base_valid,
            mechanism_qualification=mechanism_qualified,
            qualified_validity=qualified_valid,
            task_verifier_invocation_count=verifier_calls,
        )
        production = production_by_job[job.job_id]
        if (
            endpoint != production.bounded_policy_endpoint_record.projection
            or production.legacy_joint_measurement_projection.raw_execution_id != raw.artifact_id
        ):
            raise ValueError(f"v26.165 independent endpoint mismatch: {job.job_id}")
        values = {
            "job_id": job.job_id,
            "raw_execution_id": raw.artifact_id,
            "task_condition_cell_id": job.task_condition_cell_id,
            "task_package_id": job.task_package_id,
            "mechanism_id": job.mechanism_id,
            "tier": job.tier,
            "sampling_mode": job.sampling_mode,
            "raw_terminal_disposition": raw.terminal_disposition,
            "terminal_failure_type": raw.terminal_failure_type,
            "endpoint": endpoint,
            "independent_verifier_invocation_count": verifier_calls,
        }
        provisional = models.IndependentEndpointRow.model_construct(row_id="pending", **values)
        rows.append(
            models.IndependentEndpointRow(
                row_id=models.identity(
                    provisional,
                    "row_id",
                    "finance_v26_bounded_policy_independent_endpoint_row:",
                ),
                **values,
            )
        )
        raws[job.job_id] = raw
        envelope_count += len(raw.provider_envelope_artifacts)
        projection_count += len(raw.public_payload_projection_artifacts)
        transport_count += len(raw.transport_invocation_artifacts)
        exact_failures += int(not exact_model)
        thinking_failures += int(not thinking)
        usage_failures += int(not usage)
        privacy_failures += int(not privacy)
        unresolved_transport += int(not transport_resolved)
        stage_two_calls += raw.stage_two_provider_call_count
        prompt_tokens += sum(item.prompt_tokens for item in raw.provider_telemetry)
        completion_tokens += sum(item.completion_tokens for item in raw.provider_telemetry)
        reasoning_tokens += sum(item.reasoning_tokens for item in raw.provider_telemetry)
        total_tokens += raw.cumulative_provider_tokens
        if index % 40 == 0:
            print(f"[v26.165] independent endpoint {index}/360", flush=True)
    provider_values = {
        "provider_call_count": envelope_count,
        "provider_envelope_count": envelope_count,
        "public_projection_count": projection_count,
        "transport_certificate_count": transport_count,
        "complete_artifact_triple_count": envelope_count,
        "exact_model_failure_count": exact_failures,
        "thinking_failure_count": thinking_failures,
        "usage_failure_count": usage_failures,
        "privacy_failure_count": privacy_failures,
        "unresolved_transport_failure_count": unresolved_transport,
        "stage_two_provider_call_count": stage_two_calls,
        "provider_prompt_tokens": prompt_tokens,
        "provider_completion_tokens": completion_tokens,
        "provider_reasoning_tokens": reasoning_tokens,
        "provider_total_tokens": total_tokens,
    }
    provisional_provider = models.IndependentProviderArtifactAudit.model_construct(
        audit_id="pending",
        **provider_values,
    )
    provider = models.IndependentProviderArtifactAudit(
        audit_id=models.identity(
            provisional_provider,
            "audit_id",
            "finance_v26_bounded_policy_independent_provider_artifacts:",
        ),
        **provider_values,
    )
    return (
        tuple(sorted(rows, key=lambda item: item.row_id)),
        provider,
        raws,
        independent_results,
    )


def _endpoint_catalog(
    rows: Sequence[models.IndependentEndpointRow],
) -> models.IndependentEndpointCatalog:
    terminal_counts = Counter(item.endpoint.terminal_class for item in rows)
    raw_counts = Counter(item.raw_terminal_disposition for item in rows)
    horizon_counts = Counter(
        item.endpoint.policy_horizon_reason
        for item in rows
        if item.endpoint.policy_horizon_reason is not None
    )
    values = {
        "rows": tuple(rows),
        "bounded_policy_endpoint_count": sum(
            item.endpoint.bounded_policy_endpoint_observed for item in rows
        ),
        "model_terminal_count": sum(item.endpoint.model_terminal_observed for item in rows),
        "policy_horizon_endpoint_count": sum(
            item.endpoint.policy_terminal_observed for item in rows
        ),
        "validity_evaluable_count": sum(item.endpoint.validity_evaluable for item in rows),
        "base_valid_count": sum(item.endpoint.base_validity is True for item in rows),
        "mechanism_qualified_count": sum(
            item.endpoint.mechanism_qualification is True for item in rows
        ),
        "qualified_valid_count": sum(item.endpoint.qualified_validity is True for item in rows),
        "terminal_class_counts": dict(sorted(terminal_counts.items())),
        "raw_terminal_counts": dict(sorted(raw_counts.items())),
        "policy_horizon_reason_counts": {
            reason: horizon_counts[reason] for reason in HORIZON_REASONS
        },
    }
    provisional = models.IndependentEndpointCatalog.model_construct(
        catalog_id="pending",
        **values,
    )
    return models.IndependentEndpointCatalog(
        catalog_id=models.identity(
            provisional,
            "catalog_id",
            "finance_v26_bounded_policy_independent_endpoint_catalog:",
        ),
        **values,
    )


def _gate_audit(
    *,
    catalog: models.IndependentEndpointCatalog,
    recovery_dir: Path,
) -> models.IndependentGateAudit:
    rows = tuple(item.endpoint for item in catalog.rows)
    gate = make_bounded_policy_global_integrity_gate(
        exact_job_denominator=360,
        complete_raw_count=len(rows),
        bounded_policy_endpoint_count=sum(item.bounded_policy_endpoint_observed for item in rows),
        raw_instrument_failure_count=sum(not item.raw_instrument_integrity for item in rows),
        resource_accounting_failure_count=sum(
            not item.resource_accounting_integrity for item in rows
        ),
        privacy_failure_count=sum(not item.privacy_compliant for item in rows),
        provider_identity_thinking_usage_failure_count=sum(
            not (item.provider_identity_integrity and item.thinking_usage_integrity)
            for item in rows
        ),
        unresolved_transport_failure_count=sum(not item.transport_resolved for item in rows),
        unsupported_measurement_exit_count=sum(
            not item.measurement_support_available for item in rows
        ),
    )
    production = BoundedPolicyGlobalIntegrityGate.model_validate(
        _load(recovery_dir / "bounded_policy_global_integrity_gate.json")
    )
    values = {
        "gate": gate,
        "production_gate_id": production.gate_id,
        "exact_gate_match": gate == production,
        "failure_ids": gate.failure_ids,
        "passed": gate.passed,
    }
    provisional = models.IndependentGateAudit.model_construct(audit_id="pending", **values)
    return models.IndependentGateAudit(
        audit_id=models.identity(
            provisional,
            "audit_id",
            "finance_v26_bounded_policy_independent_gate_audit:",
        ),
        **values,
    )


def _mapper_audit(
    *,
    prepared: execution_models.PreparedBoundedPolicyExecution,
    catalog: models.IndependentEndpointCatalog,
    gate: models.IndependentGateAudit,
    raws: Mapping[str, runner_vnext.FreshReachabilityRawExecution],
    independent_results: Mapping[str, execution_base.ReachabilityMeasurementResult],
    recovery_dir: Path,
) -> tuple[models.IndependentMapperAudit, dict[str, list[str]]]:
    if not gate.passed:
        raise ValueError("v26.165 Mapper requires a passing independent Gate")
    jobs = {item.job_id: item for item in prepared.manifest.jobs}
    cells = {item.cell_id: item for item in prepared.cell_catalog.cells}
    contexts = {item.task_package_id: item.context_id for item in prepared.omega_catalog.contexts}
    recovered_catalog = execution_models.BoundedPolicyAssignmentCatalog.model_validate(
        _load(recovery_dir / "bounded_policy_assignment_catalog.json")
    )
    recovered_by_job = {item.job_id: item for item in recovered_catalog.assignments}
    qualified_rows = tuple(
        item for item in catalog.rows if item.endpoint.qualified_validity is True
    )
    state_ids_by_cell: dict[str, list[str]] = defaultdict(list)
    exact_matches = 0
    states = set()
    routes = set()
    for row in qualified_rows:
        job = jobs[row.job_id]
        raw = raws[row.job_id]
        result = independent_results[row.job_id]
        package = execution._package_for_job(prepared, job)  # noqa: SLF001
        aliases = mapping_preflight._runtime_aliases(package, raw)  # noqa: SLF001
        trajectory = state_semantics._trajectory_projection_v2(  # noqa: SLF001
            raw=raw,
            result=result,
            semantic_policy=prepared.semantic_policy,
        )
        comparison = result.answer_comparison
        if comparison is None:
            raise ValueError("v26.165 Qualified endpoint lacks Answer comparison")
        raw_hash = result.raw_execution_artifact.sha256
        alias_hash = canonical_hash(
            aliases,
            prefix="finance_v26_runtime_operation_alias_binding:",
        )
        verifier_input_hash = strict_canonical_hash(
            {
                "qualified_validity_report_id": result.joint_result.qualified_report.report_id,
                "answer_comparison_id": comparison.comparison_id,
                "answer_semantic_schema_id": trajectory.answer_semantic_schema_id,
                "canonical_result_semantics_hash": trajectory.canonical_result_semantics_hash,
                "trajectory_bound_artifact_hash": trajectory.trajectory_bound_artifact_hash,
                "raw_execution_sha256": raw_hash,
                "runtime_operation_alias_binding_hash": alias_hash,
            },
            prefix="finance_v26_qualified_verifier_input_v2:",
        )
        binding = make_qualified_verifier_input_binding_v2(
            trajectory=trajectory,
            qualified_validity_report=result.joint_result.qualified_report,
            raw_execution_artifact_hash=raw_hash,
            qualified_verifier_input_hash=verifier_input_hash,
        )
        cell = cells[row.task_condition_cell_id]
        mapping = map_independently_valid_public_trajectory_to_state_v2(
            trajectory=trajectory,
            qualified_validity_report=result.joint_result.qualified_report,
            verifier_input_binding=binding,
            mapper_contract=prepared.mapper_contract,
            omega_task_context_id=contexts[job.task_package_id],
            experimental_condition=cell.experimental_condition,
            empirical_route_signature=make_empirical_route_signature_v2(trajectory),
            runtime_operation_aliases=aliases,
            semantic_policy=prepared.semantic_policy,
            raw_execution_artifact_hash=raw_hash,
        )
        reference = reference_map_public_trajectory_v2(
            trajectory=trajectory,
            omega_task_context_id=contexts[job.task_package_id],
            runtime_operation_aliases=aliases,
            semantic_policy=prepared.semantic_policy,
        )
        recovered = recovered_by_job[row.job_id]
        reference_match = reference.structural_state == mapping.structural_state
        recovered_match = models.canonical_bytes(
            recovered.mapping_assignment
        ) == models.canonical_bytes(mapping)
        if not reference_match or not recovered_match:
            recovered_dump = recovered.mapping_assignment.model_dump(mode="json")
            mapping_dump = mapping.model_dump(mode="json")
            differing_fields = tuple(
                sorted(
                    key
                    for key in set(recovered_dump) | set(mapping_dump)
                    if recovered_dump.get(key) != mapping_dump.get(key)
                )
            )
            raise ValueError(
                "v26.165 independent Mapper mismatch: "
                f"job={row.job_id} reference_match={reference_match} "
                f"recovered_match={recovered_match} "
                f"mapping_state={mapping.structural_state_id} "
                f"recovered_state={recovered.structural_state_id} "
                f"mapping_route={mapping.empirical_route_signature_id} "
                f"recovered_route={recovered.empirical_route_signature_id} "
                f"differing_fields={differing_fields}"
            )
        exact_matches += 1
        states.add(mapping.structural_state_id)
        routes.add(mapping.empirical_route_signature_id)
        state_ids_by_cell[row.task_condition_cell_id].append(mapping.structural_state_id)
    values = {
        "qualified_row_count": len(qualified_rows),
        "production_mapper_invocation_count": len(qualified_rows),
        "reference_mapper_invocation_count": len(qualified_rows),
        "production_reference_exact_state_match_count": exact_matches,
        "recovered_assignment_exact_match_count": exact_matches,
        "formal_assignment_count": len(recovered_by_job),
        "structural_state_count": len(states),
        "empirical_route_signature_count": len(routes),
    }
    provisional = models.IndependentMapperAudit.model_construct(audit_id="pending", **values)
    return (
        models.IndependentMapperAudit(
            audit_id=models.identity(
                provisional,
                "audit_id",
                "finance_v26_bounded_policy_independent_mapper_audit:",
            ),
            **values,
        ),
        state_ids_by_cell,
    )


def _cell_audit(
    *,
    prepared: execution_models.PreparedBoundedPolicyExecution,
    catalog: models.IndependentEndpointCatalog,
    gate: models.IndependentGateAudit,
    state_ids_by_cell: Mapping[str, Sequence[str]],
    recovery_dir: Path,
) -> models.IndependentCellFrequencyAudit:
    rows_by_cell: dict[str, list[models.IndependentEndpointRow]] = defaultdict(list)
    for row in catalog.rows:
        rows_by_cell[row.task_condition_cell_id].append(row)
    reports = []
    for cell in prepared.cell_catalog.cells:
        rows = rows_by_cell[cell.cell_id]
        expected = (
            12 if cell.experimental_condition.sampling_mode == "reachability_unconditional" else 6
        )
        reports.append(
            summarize_bounded_policy_cell(
                task_condition_cell_id=cell.cell_id,
                generation_policy_id=prepared.policy.policy_id,
                global_gate=gate.gate,
                expected_n_total=expected,
                observed_n_total=len(rows),
                endpoint_count=sum(item.endpoint.bounded_policy_endpoint_observed for item in rows),
                qualified_state_ids=tuple(state_ids_by_cell.get(cell.cell_id, ())),
            )
        )
    ordered = tuple(sorted(reports, key=lambda item: item.report_id))
    production = execution_models.BoundedPolicyCellFrequencyCatalog.model_validate(
        _load(recovery_dir / "bounded_policy_cell_frequency_catalog.json")
    )
    exact = sum(
        models.canonical_bytes(left) == models.canonical_bytes(right)
        for left, right in zip(ordered, production.reports, strict=True)
    )
    values = {
        "reports": ordered,
        "exact_report_match_count": exact,
        "n_total_sum": sum(item.n_total for item in ordered),
        "n_policy_endpoint_sum": sum(item.n_policy_endpoints for item in ordered),
        "n_qualified_sum": sum(item.n_qualified for item in ordered),
        "q_instantiated_cell_count": sum(item.q_hat is not None for item in ordered),
        "pi_instantiated_cell_count": sum(item.pi_instantiated for item in ordered),
        "zero_qualified_cell_count": sum(
            item.pi_null_reason == "no_qualified_rows" for item in ordered
        ),
        "empirical_non_degenerate_cell_count": sum(
            item.empirical_non_degenerate is True for item in ordered
        ),
        "unconditional_cell_count": sum(
            item.experimental_condition.sampling_mode == "reachability_unconditional"
            for item in prepared.cell_catalog.cells
        ),
        "conditioned_cell_count": sum(
            item.experimental_condition.sampling_mode == "reachability_conditioned"
            for item in prepared.cell_catalog.cells
        ),
        "simultaneous_multinomial_coverage_claim_count": sum(
            item.marginal_wilson_interval.simultaneous_multinomial_coverage_claimed
            for report in ordered
            for item in report.state_frequencies
        ),
    }
    provisional = models.IndependentCellFrequencyAudit.model_construct(
        audit_id="pending",
        **values,
    )
    return models.IndependentCellFrequencyAudit(
        audit_id=models.identity(
            provisional,
            "audit_id",
            "finance_v26_bounded_policy_independent_cell_frequency_audit:",
        ),
        **values,
    )


def _recovery_boundary(
    *,
    catalog: models.IndependentEndpointCatalog,
    raws: Mapping[str, runner_vnext.FreshReachabilityRawExecution],
    failed_execution_dir: Path,
    recovery_dir: Path,
) -> models.RecoveryBoundaryAudit:
    freeze = recovery_models.FailedExecutionFreezeAudit.model_validate(
        _load(recovery_dir / "failed_execution_freeze_audit.json")
    )
    normalization = recovery_models.TypedSemanticRejectionNormalizationAudit.model_validate(
        _load(recovery_dir / "typed_semantic_rejection_normalization_audit.json")
    )
    checkpoint_count = len(
        tuple(
            line
            for line in (failed_execution_dir / execution.CHECKPOINT_NAME)
            .read_text(encoding="utf-8")
            .splitlines()
            if line
        )
    )
    horizon_raws = tuple(
        raws[item.job_id] for item in catalog.rows if item.endpoint.policy_terminal_observed
    )
    values = {
        "failed_execution_file_count": freeze.failed_execution_file_count,
        "failed_execution_unchanged": (
            _directory_snapshot(
                failed_execution_dir,
                prefix="finance_v26_bounded_policy_failed_execution_content_root:",
            )[2]
            == freeze.failed_execution_content_root
        ),
        "direct_checkpoint_byte_match_count": checkpoint_count,
        "typed_semantic_rejection_count": len(normalization.rows),
        "typed_semantic_rejection_null_to_false_count": sum(
            item.after_qualified_validity is False for item in normalization.rows
        ),
        "typed_semantic_rejection_model_terminal_count": sum(
            item.endpoint.terminal_class == "model_typed_rejection" for item in catalog.rows
        ),
        "policy_horizon_endpoint_count": len(horizon_raws),
        "policy_horizon_later_provider_call_count": sum(
            item.later_provider_calls_after_support_exit for item in horizon_raws
        ),
        "recovery_provider_calls": freeze.recovery_provider_calls,
    }
    provisional = models.RecoveryBoundaryAudit.model_construct(audit_id="pending", **values)
    return models.RecoveryBoundaryAudit(
        audit_id=models.identity(
            provisional,
            "audit_id",
            "finance_v26_bounded_policy_recovery_boundary_audit:",
        ),
        **values,
    )


def _detail(path: Path, output_dir: Path) -> models.DetailFile:
    return models.DetailFile(
        relative_path=str(path.resolve().relative_to(output_dir.resolve())),
        sha256=models.sha256(path),
        byte_count=path.stat().st_size,
    )


def build_postrun_audit(
    *,
    failed_execution_dir: Path,
    recovery_dir: Path,
    output_dir: Path,
    package_root: Path,
    implementation_root: Path,
) -> models.PostrunAuditReport:
    report_path = output_dir / "report.json"
    if report_path.is_file():
        return models.PostrunAuditReport.model_validate(_load(report_path))
    if os.environ.get("DEEPSEEK_API_KEY"):
        raise ValueError("v26.165 postrun audit requires credential removal")
    output_dir.mkdir(parents=True, exist_ok=True)
    source = _source_replay(
        failed_execution_dir=failed_execution_dir,
        recovery_dir=recovery_dir,
        implementation_root=implementation_root,
    )
    prepared = recovery._prepare_from_failed_freeze(  # noqa: SLF001
        preflight_dir=package_root / execution_models.PREFLIGHT_DIR,
        failed_execution_dir=failed_execution_dir,
        package_root=package_root,
        implementation_root=implementation_root,
    )
    rows, provider, raws, independent_results = _independent_endpoint_rows(
        prepared=prepared,
        failed_execution_dir=failed_execution_dir,
        recovery_dir=recovery_dir,
    )
    catalog = _endpoint_catalog(rows)
    gate = _gate_audit(catalog=catalog, recovery_dir=recovery_dir)
    mapper, states = _mapper_audit(
        prepared=prepared,
        catalog=catalog,
        gate=gate,
        raws=raws,
        independent_results=independent_results,
        recovery_dir=recovery_dir,
    )
    cells = _cell_audit(
        prepared=prepared,
        catalog=catalog,
        gate=gate,
        state_ids_by_cell=states,
        recovery_dir=recovery_dir,
    )
    boundary = _recovery_boundary(
        catalog=catalog,
        raws=raws,
        failed_execution_dir=failed_execution_dir,
        recovery_dir=recovery_dir,
    )
    outputs: tuple[tuple[str, Any], ...] = (
        ("source_replay_audit.json", source),
        ("independent_endpoint_catalog.json", catalog),
        ("independent_provider_artifact_audit.json", provider),
        ("independent_gate_audit.json", gate),
        ("independent_mapper_audit.json", mapper),
        ("independent_cell_frequency_audit.json", cells),
        ("recovery_boundary_audit.json", boundary),
    )
    for name, value in outputs:
        _write_json_once(output_dir / name, value)
    detail_files = tuple(_detail(output_dir / name, output_dir) for name, _ in outputs)
    recovered_report = execution_models.BoundedPolicyExecutionReport.model_validate(
        _load(recovery_dir / "bounded_policy_execution_report.json")
    )
    values = {
        "source_replay_audit_id": source.audit_id,
        "independent_endpoint_catalog_id": catalog.catalog_id,
        "independent_provider_artifact_audit_id": provider.audit_id,
        "independent_gate_audit_id": gate.audit_id,
        "independent_mapper_audit_id": mapper.audit_id,
        "independent_cell_frequency_audit_id": cells.audit_id,
        "recovery_boundary_audit_id": boundary.audit_id,
        "recovered_execution_report_id": recovered_report.report_id,
        "complete_raw_count": len(raws),
        "bounded_policy_endpoint_count": catalog.bounded_policy_endpoint_count,
        "global_integrity_gate_passed": gate.passed,
        "qualified_valid_count": catalog.qualified_valid_count,
        "formal_assignment_count": mapper.formal_assignment_count,
        "structural_state_count": mapper.structural_state_count,
        "q_instantiated_cell_count": cells.q_instantiated_cell_count,
        "pi_instantiated_cell_count": cells.pi_instantiated_cell_count,
        "zero_qualified_cell_count": cells.zero_qualified_cell_count,
        "empirical_non_degenerate_cell_count": cells.empirical_non_degenerate_cell_count,
        "detail_files": tuple(sorted(detail_files, key=lambda item: item.relative_path)),
    }
    provisional = models.PostrunAuditReport.model_construct(report_id="pending", **values)
    report = models.PostrunAuditReport(
        report_id=models.identity(
            provisional,
            "report_id",
            "finance_v26_bounded_policy_postrun_audit_report:",
        ),
        **values,
    )
    _write_json_once(report_path, report)
    return report


def main() -> None:
    package_default = Path(__file__).resolve().parents[4]
    parser = argparse.ArgumentParser(
        description="Independently audit the v26.164 bounded-policy frequency denominator"
    )
    parser.add_argument(
        "--failed-execution-dir",
        type=Path,
        default=package_default / models.FAILED_EXECUTION_DIR,
    )
    parser.add_argument(
        "--recovery-dir",
        type=Path,
        default=package_default / models.RECOVERY_DIR,
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=package_default / models.OUTPUT_DIR,
    )
    parser.add_argument("--package-root", type=Path, default=package_default)
    parser.add_argument("--implementation-root", type=Path, default=package_default)
    args = parser.parse_args()
    report = build_postrun_audit(
        failed_execution_dir=args.failed_execution_dir,
        recovery_dir=args.recovery_dir,
        output_dir=args.output_dir,
        package_root=args.package_root,
        implementation_root=args.implementation_root,
    )
    print(report.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
