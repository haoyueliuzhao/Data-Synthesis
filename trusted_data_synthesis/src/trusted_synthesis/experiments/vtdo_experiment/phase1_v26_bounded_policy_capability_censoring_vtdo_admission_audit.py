from __future__ import annotations

import argparse
import json
from collections import Counter
from collections.abc import Mapping, Sequence
from decimal import Decimal, localcontext
from pathlib import Path
from typing import Any, Final, cast

from trusted_synthesis.core.evaluation.bounded_policy_endpoint import (
    BoundedPolicyTerminalClass,
    make_bounded_policy_endpoint_projection,
)
from trusted_synthesis.core.trajectory.reachability_frequency_v2 import (
    TaskConditionCellCatalogV2,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_bounded_policy_capability_censoring_vtdo_admission_audit_models as models,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_bounded_policy_endpoint_frequency_postrun_audit_models as postrun_models,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_bounded_policy_endpoint_frequency_preflight as preflight,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_bounded_policy_endpoint_frequency_raw_only_recovery_models as recovery_models,
)

RUN_ID: Final = (
    "finance_v26_166_bounded_policy_capability_censoring_vtdo_admission_audit_v1_20260828"
)
PREDECESSOR_PREFLIGHT_FILES: Final = (
    "frequency_estimand_contract.json",
    "generation_policy.json",
    "report.json",
    "task_condition_cell_catalog.json",
)


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json_once(path: Path, value: Any) -> None:
    payload = models.canonical_bytes(value)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_bytes() != payload:
            raise ValueError(f"v26.166 immutable audit artifact changed: {path}")
        return
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(payload)
    temporary.replace(path)


def _authorization() -> models.ExternalAuditAuthorization:
    values: dict[str, Any] = {}
    provisional = models.ExternalAuditAuthorization.model_construct(
        authorization_id="pending",
        **values,
    )
    return models.ExternalAuditAuthorization(
        authorization_id=models.identity(
            provisional,
            "authorization_id",
            "finance_v26_bounded_policy_capability_censoring_authorization:",
        ),
        **values,
    )


def _binding(package_root: Path, relative_path: str, stage: str) -> models.SourceBinding:
    path = package_root / relative_path
    if not path.is_file():
        raise ValueError(f"v26.166 required source is unavailable: {relative_path}")
    return models.SourceBinding(
        stage=cast(Any, stage),
        relative_path=relative_path,
        sha256=models.sha256(path),
        byte_count=path.stat().st_size,
    )


def _source_replay(
    *,
    package_root: Path,
    authorization: models.ExternalAuditAuthorization,
) -> models.SourceReplayAudit:
    preflight_dir = package_root / preflight.OUTPUT_DIR
    recovery_dir = package_root / recovery_models.OUTPUT_DIR
    postrun_dir = package_root / postrun_models.OUTPUT_DIR
    recovery_names = tuple(sorted(path.name for path in recovery_dir.glob("*.json")))
    postrun_names = tuple(sorted(path.name for path in postrun_dir.glob("*.json")))
    if len(recovery_names) != 13 or len(postrun_names) != 8:
        raise ValueError("v26.166 predecessor direct-artifact denominator changed")
    artifact_bindings = tuple(
        sorted(
            (
                *(
                    _binding(
                        package_root,
                        str((preflight_dir / name).relative_to(package_root)),
                        "v26.163",
                    )
                    for name in PREDECESSOR_PREFLIGHT_FILES
                ),
                *(
                    _binding(
                        package_root,
                        str((recovery_dir / name).relative_to(package_root)),
                        "v26.164",
                    )
                    for name in recovery_names
                ),
                *(
                    _binding(
                        package_root,
                        str((postrun_dir / name).relative_to(package_root)),
                        "v26.165",
                    )
                    for name in postrun_names
                ),
            ),
            key=lambda item: (item.stage, item.relative_path),
        )
    )
    implementation_bindings = tuple(
        sorted(
            (
                _binding(package_root, models.IMPLEMENTATION_PATH, "v26.166"),
                _binding(package_root, models.MODEL_IMPLEMENTATION_PATH, "v26.166"),
            ),
            key=lambda item: item.relative_path,
        )
    )
    values = {
        "authorization_id": authorization.authorization_id,
        "artifact_bindings": artifact_bindings,
        "implementation_bindings": implementation_bindings,
    }
    provisional = models.SourceReplayAudit.model_construct(audit_id="pending", **values)
    return models.SourceReplayAudit(
        audit_id=models.identity(
            provisional,
            "audit_id",
            "finance_v26_bounded_policy_censoring_source_replay:",
        ),
        **values,
    )


def _condition(cell: Any) -> models.CellCondition:
    experimental = cell.experimental_condition
    if experimental.sampling_mode == "reachability_unconditional":
        return "unconditional"
    strategy = experimental.requested_path_strategy
    if strategy not in {
        "structured_direct",
        "search_then_structured",
        "search_then_open",
    }:
        raise ValueError("v26.166 conditioned Cell has an unknown Path strategy")
    return cast(models.CellCondition, strategy)


def _cell_metadata(
    endpoint_catalog: postrun_models.IndependentEndpointCatalog,
) -> dict[str, tuple[str, models.MechanismId, models.Tier]]:
    values: dict[str, tuple[str, models.MechanismId, models.Tier]] = {}
    for row in endpoint_catalog.rows:
        current = (
            row.task_package_id,
            cast(models.MechanismId, row.mechanism_id),
            cast(models.Tier, row.tier),
        )
        previous = values.setdefault(row.task_condition_cell_id, current)
        if previous != current:
            raise ValueError("v26.166 Cell crossed Task, Mechanism, or Tier parents")
    if len(values) != 48:
        raise ValueError("v26.166 endpoint Catalog does not cover all 48 Cells")
    return values


def _cell_support_strata(
    *,
    cells: TaskConditionCellCatalogV2,
    cell_audit: postrun_models.IndependentCellFrequencyAudit,
    endpoint_catalog: postrun_models.IndependentEndpointCatalog,
) -> models.CellSupportStratumCatalog:
    reports = {item.task_condition_cell_id: item for item in cell_audit.reports}
    metadata = _cell_metadata(endpoint_catalog)
    rows = []
    for cell in cells.cells:
        report = reports[cell.cell_id]
        task_package_id, mechanism_id, tier = metadata[cell.cell_id]
        state_ids = tuple(sorted(item.structural_state_id for item in report.state_frequencies))
        if report.q_hat is None:
            raise ValueError("v26.166 passing bounded-policy Cell lacks q")
        stratum = models._support_stratum(report.n_qualified, len(state_ids))
        values = {
            "task_condition_cell_id": cell.cell_id,
            "task_package_id": task_package_id,
            "mechanism_id": mechanism_id,
            "tier": tier,
            "condition": _condition(cell),
            "expected_endpoint_count": report.expected_n_total,
            "bounded_policy_endpoint_count": report.n_policy_endpoints,
            "qualified_count": report.n_qualified,
            "observed_state_count": len(state_ids),
            "observed_state_ids": state_ids,
            "q_hat": report.q_hat,
            "stratum": stratum,
            "pi_instantiated": report.pi_instantiated,
        }
        provisional = models.CellSupportStratumRow.model_construct(
            row_id="pending",
            **values,
        )
        rows.append(
            models.CellSupportStratumRow(
                row_id=models.identity(
                    provisional,
                    "row_id",
                    "finance_v26_bounded_policy_cell_support_stratum_row:",
                ),
                **values,
            )
        )
    ordered = tuple(sorted(rows, key=lambda item: item.row_id))
    values = {"rows": ordered}
    provisional = models.CellSupportStratumCatalog.model_construct(
        catalog_id="pending",
        **values,
    )
    return models.CellSupportStratumCatalog(
        catalog_id=models.identity(
            provisional,
            "catalog_id",
            "finance_v26_bounded_policy_cell_support_stratum_catalog:",
        ),
        **values,
    )


def _capability_checks(
    recovered: recovery_models.RawOnlyRecoveredMeasurementResult,
) -> models.CapabilityGateDAGChecks:
    legacy = recovered.legacy_joint_measurement_projection
    endpoint = recovered.bounded_policy_endpoint_record.projection
    base = legacy.joint_result.base_report.checks
    if endpoint.policy_horizon_status == "exhausted":
        return models.CapabilityGateDAGChecks(
            action_entry=legacy.first_action_interface_qualified,
            program_closure=None,
            operation_lineage=None,
            evidence_support=None,
            terminal_verification=None,
            final_abi=None,
            answer_semantics=None,
            reference_identity=None,
            citation=None,
            mechanism_qualification=None,
            policy_horizon=False,
            noninterference_artifact_bound=None,
        )
    if base is None:
        if legacy.raw_terminal_disposition != "typed_semantic_rejection":
            raise ValueError("v26.166 non-Horizon row lacks Base task-Verifier checks")
        return models.CapabilityGateDAGChecks(
            action_entry=legacy.first_action_interface_qualified,
            program_closure=None,
            operation_lineage=None,
            evidence_support=None,
            terminal_verification=None,
            final_abi=None,
            answer_semantics=None,
            reference_identity=None,
            citation=None,
            mechanism_qualification=None,
            policy_horizon=True,
            noninterference_artifact_bound=None,
        )
    return models.CapabilityGateDAGChecks(
        action_entry=bool(legacy.first_action_interface_qualified and base.action_abi_complete),
        program_closure=bool(legacy.program_closed and base.program_closed),
        operation_lineage=base.operation_lineage_complete,
        evidence_support=bool(
            base.required_evidence_support_complete
            and base.runtime_selected_support_complete
            and base.verification_support_complete
        ),
        terminal_verification=bool(
            base.terminal_verification_complete and base.no_postcompletion_violation
        ),
        final_abi=bool(base.final_abi_complete and base.answer_schema_complete),
        answer_semantics=base.answer_canonical_semantic_match,
        reference_identity=base.reference_identity_match,
        citation=base.model_citation_complete,
        mechanism_qualification=legacy.joint_result.mechanism_report.success,
        policy_horizon=True,
        noninterference_artifact_bound=base.noninterference_artifact_bound,
    )


def _capability_survival_profile(
    *,
    cells: TaskConditionCellCatalogV2,
    endpoint_catalog: postrun_models.IndependentEndpointCatalog,
    recovered_results: Sequence[recovery_models.RawOnlyRecoveredMeasurementResult],
) -> models.CapabilitySurvivalProfileCatalog:
    cell_by_id = {item.cell_id: item for item in cells.cells}
    endpoint_by_job = {item.job_id: item for item in endpoint_catalog.rows}
    recovered_by_job = {item.job_id: item for item in recovered_results}
    if len(endpoint_by_job) != 360 or set(endpoint_by_job) != set(recovered_by_job):
        raise ValueError("v26.166 endpoint and recovery Job denominators differ")
    rows = []
    for job_id in sorted(endpoint_by_job):
        independent = endpoint_by_job[job_id]
        recovered = recovered_by_job[job_id]
        legacy = recovered.legacy_joint_measurement_projection
        endpoint = recovered.bounded_policy_endpoint_record.projection
        if endpoint != independent.endpoint:
            raise ValueError("v26.166 independent and recovered endpoints differ")
        checks = _capability_checks(recovered)
        first = models._first_blocker(checks)
        mechanism_report = legacy.joint_result.mechanism_report
        task_verifier_invoked = legacy.task_verifier_invocation_count == 1
        mechanism_event_evaluable = bool(
            task_verifier_invoked and mechanism_report.success is not None
        )
        values = {
            "job_id": job_id,
            "raw_execution_id": legacy.raw_execution_id,
            "endpoint_projection_id": endpoint.projection_id,
            "task_condition_cell_id": recovered.task_condition_cell_id,
            "task_package_id": recovered.task_package_id,
            "mechanism_id": cast(models.MechanismId, legacy.mechanism_id),
            "tier": cast(models.Tier, legacy.tier),
            "condition": _condition(cell_by_id[recovered.task_condition_cell_id]),
            "terminal_class": endpoint.terminal_class,
            "checks": checks,
            "base_failed_check_ids": legacy.joint_result.base_report.failed_check_ids,
            "mechanism_missing_event_ids": mechanism_report.missing_event_ids,
            "first_authorized_blocker": first,
            "qualified_survivor": endpoint.qualified_validity is True,
            "mechanism_endpoint_qualification": endpoint.mechanism_qualification is True,
            "mechanism_event_evaluable": mechanism_event_evaluable,
            "task_verifier_invoked": task_verifier_invoked,
            "policy_censored": endpoint.policy_horizon_status == "exhausted",
            "typed_semantic_rejection": endpoint.terminal_class == "model_typed_rejection",
            "historical_mapping_eligible": endpoint.state_mapping_eligible,
        }
        provisional = models.CapabilitySurvivalRow.model_construct(
            row_id="pending",
            **values,
        )
        rows.append(
            models.CapabilitySurvivalRow(
                row_id=models.identity(
                    provisional,
                    "row_id",
                    "finance_v26_bounded_policy_capability_survival_row:",
                ),
                **values,
            )
        )
    ordered = tuple(sorted(rows, key=lambda item: item.row_id))
    counts = dict(sorted(Counter(item.first_authorized_blocker for item in ordered).items()))
    values = {"rows": ordered, "first_authorized_blocker_counts": counts}
    provisional = models.CapabilitySurvivalProfileCatalog.model_construct(
        catalog_id="pending",
        **values,
    )
    return models.CapabilitySurvivalProfileCatalog(
        catalog_id=models.identity(
            provisional,
            "catalog_id",
            "finance_v26_bounded_policy_capability_survival_profile:",
        ),
        **values,
    )


def _schema_endpoint(
    *,
    name: str,
    terminal_class: BoundedPolicyTerminalClass,
    horizon: bool = False,
    raw_instrument: bool = True,
    support: bool = True,
    privacy: bool = True,
    transport: bool = True,
    model_terminal: bool = False,
    task_completion: bool | None = None,
    base: bool | None = None,
    mechanism: bool | None = None,
    qualified: bool | None = None,
    verifier_calls: int = 0,
) -> models.TerminalEndpointSchemaCase:
    endpoint = make_bounded_policy_endpoint_projection(
        trajectory_id=f"v26.166-terminal-schema:{name}",
        generation_policy_id="bounded_policy_endpoint_generation_policy:v26.166-fixture",
        terminal_class=terminal_class,
        policy_horizon_reason="ordinary_detour_limit" if horizon else None,
        raw_instrument_integrity=raw_instrument,
        measurement_support_available=support,
        resource_accounting_integrity=True,
        provider_identity_integrity=True,
        thinking_usage_integrity=True,
        privacy_compliant=privacy,
        transport_resolved=transport,
        model_terminal_observed=model_terminal,
        task_completion=task_completion,
        base_validity=base,
        mechanism_qualification=mechanism,
        qualified_validity=qualified,
        task_verifier_invocation_count=verifier_calls,
    )
    values = {
        "case_name": name,
        "endpoint": endpoint,
        "expected_task_completion": task_completion,
        "expected_base_validity": base,
        "expected_mechanism_qualification": mechanism,
        "expected_qualified_validity": qualified,
        "expected_mapping_eligible": qualified is True,
        "expected_task_verifier_invocation_count": verifier_calls,
    }
    provisional = models.TerminalEndpointSchemaCase.model_construct(
        case_id="pending",
        **values,
    )
    return models.TerminalEndpointSchemaCase(
        case_id=models.identity(
            provisional,
            "case_id",
            "finance_v26_terminal_endpoint_schema_case:",
        ),
        **values,
    )


def _terminal_endpoint_schema_audit() -> models.TerminalEndpointSchemaAudit:
    cases = tuple(
        sorted(
            (
                _schema_endpoint(
                    name="completed_endpoint",
                    terminal_class="completed_model_endpoint",
                    model_terminal=True,
                    task_completion=True,
                    base=True,
                    mechanism=True,
                    qualified=True,
                    verifier_calls=1,
                ),
                _schema_endpoint(
                    name="instrument_endpoint",
                    terminal_class="instrument_failure",
                    raw_instrument=False,
                ),
                _schema_endpoint(
                    name="measurement_support_exit",
                    terminal_class="measurement_support_exit",
                    support=False,
                ),
                _schema_endpoint(
                    name="model_result_failure",
                    terminal_class="model_result_failure",
                    model_terminal=True,
                    task_completion=False,
                    base=False,
                    mechanism=True,
                    qualified=False,
                    verifier_calls=1,
                ),
                _schema_endpoint(
                    name="policy_horizon",
                    terminal_class="policy_horizon_exhausted",
                    horizon=True,
                    task_completion=False,
                    base=False,
                    mechanism=False,
                    qualified=False,
                ),
                _schema_endpoint(
                    name="privacy_endpoint",
                    terminal_class="privacy_failure",
                    privacy=False,
                ),
                _schema_endpoint(
                    name="transport_endpoint",
                    terminal_class="provider_transport_failure",
                    transport=False,
                ),
                _schema_endpoint(
                    name="typed_semantic_rejection",
                    terminal_class="model_typed_rejection",
                    model_terminal=True,
                    task_completion=False,
                    base=False,
                    mechanism=False,
                    qualified=False,
                ),
            ),
            key=lambda item: item.case_name,
        )
    )
    values = {"cases": cases}
    provisional = models.TerminalEndpointSchemaAudit.model_construct(
        audit_id="pending",
        **values,
    )
    return models.TerminalEndpointSchemaAudit(
        audit_id=models.identity(
            provisional,
            "audit_id",
            "finance_v26_terminal_endpoint_schema_audit:",
        ),
        **values,
    )


def _typed_rejection_boundary(
    survival: models.CapabilitySurvivalProfileCatalog,
    recovered_results: Sequence[recovery_models.RawOnlyRecoveredMeasurementResult],
) -> models.TypedSemanticRejectionBoundaryAudit:
    legacy_by_job = {
        item.job_id: item.legacy_joint_measurement_projection for item in recovered_results
    }
    rows = []
    for item in survival.rows:
        if not item.typed_semantic_rejection:
            continue
        legacy = legacy_by_job[item.job_id]
        row_values: dict[str, Any] = {
            "job_id": item.job_id,
            "raw_execution_id": item.raw_execution_id,
            "endpoint_projection_id": item.endpoint_projection_id,
            "legacy_mechanism_report_success": legacy.joint_result.mechanism_report.success,
        }
        provisional = models.TypedSemanticRejectionBoundaryRow.model_construct(
            row_id="pending",
            **row_values,
        )
        rows.append(
            models.TypedSemanticRejectionBoundaryRow(
                row_id=models.identity(
                    provisional,
                    "row_id",
                    "finance_v26_typed_semantic_rejection_boundary_row:",
                ),
                **row_values,
            )
        )
    audit_values: dict[str, Any] = {"rows": tuple(sorted(rows, key=lambda item: item.row_id))}
    provisional = models.TypedSemanticRejectionBoundaryAudit.model_construct(
        audit_id="pending",
        **audit_values,
    )
    return models.TypedSemanticRejectionBoundaryAudit(
        audit_id=models.identity(
            provisional,
            "audit_id",
            "finance_v26_typed_semantic_rejection_boundary_audit:",
        ),
        **audit_values,
    )


def _vtdo_admission(
    strata: models.CellSupportStratumCatalog,
) -> models.VTDOAdmissionCatalog:
    rows = []
    for item in strata.rows:
        existence = item.stratum == "observed_multistate_support"
        values = {
            "task_condition_cell_id": item.task_condition_cell_id,
            "support_stratum": item.stratum,
            "state_support_existence": existence,
            "highest_passed_tier": "state_support_existence" if existence else "none",
        }
        provisional = models.VTDOAdmissionRow.model_construct(row_id="pending", **values)
        rows.append(
            models.VTDOAdmissionRow(
                row_id=models.identity(
                    provisional,
                    "row_id",
                    "finance_v26_vtdo_admission_row:",
                ),
                **values,
            )
        )
    values = {"rows": tuple(sorted(rows, key=lambda item: item.row_id))}
    provisional = models.VTDOAdmissionCatalog.model_construct(
        catalog_id="pending",
        **values,
    )
    return models.VTDOAdmissionCatalog(
        catalog_id=models.identity(
            provisional,
            "catalog_id",
            "finance_v26_vtdo_admission_catalog:",
        ),
        **values,
    )


def _coverage_gap_registry(
    strata: models.CellSupportStratumCatalog,
) -> models.CoverageGapRegistry:
    rows = []
    for item in strata.rows:
        if item.stratum == "observed_multistate_support":
            continue
        row_values: dict[str, Any] = {
            "task_condition_cell_id": item.task_condition_cell_id,
            "mechanism_id": item.mechanism_id,
            "tier": item.tier,
            "condition": item.condition,
            "support_stratum": item.stratum,
        }
        provisional = models.CoverageGapRow.model_construct(
            row_id="pending",
            **row_values,
        )
        rows.append(
            models.CoverageGapRow(
                row_id=models.identity(
                    provisional,
                    "row_id",
                    "finance_v26_coverage_gap_row:",
                ),
                **row_values,
            )
        )
    registry_values: dict[str, Any] = {"rows": tuple(sorted(rows, key=lambda item: item.row_id))}
    provisional = models.CoverageGapRegistry.model_construct(
        registry_id="pending",
        **registry_values,
    )
    return models.CoverageGapRegistry(
        registry_id=models.identity(
            provisional,
            "registry_id",
            "finance_v26_coverage_gap_registry:",
        ),
        **registry_values,
    )


def _token_diagnostic(
    provider: postrun_models.IndependentProviderArtifactAudit,
) -> models.EngineeringTokenDiagnostic:
    with localcontext() as context:
        context.prec = 50
        ratio = format(
            Decimal(provider.provider_total_tokens) / Decimal(106),
            "f",
        )
    values = {
        "provider_total_tokens": provider.provider_total_tokens,
        "qualified_trajectory_count": 106,
        "tokens_per_qualified_trajectory": ratio,
    }
    provisional = models.EngineeringTokenDiagnostic.model_construct(
        diagnostic_id="pending",
        **values,
    )
    return models.EngineeringTokenDiagnostic(
        diagnostic_id=models.identity(
            provisional,
            "diagnostic_id",
            "finance_v26_cross_cell_token_per_qualified_diagnostic:",
        ),
        **values,
    )


def _fresh_confirmation_protocol() -> models.FreshConfirmationProtocol:
    values: dict[str, Any] = {}
    provisional = models.FreshConfirmationProtocol.model_construct(
        protocol_id="pending",
        **values,
    )
    return models.FreshConfirmationProtocol(
        protocol_id=models.identity(
            provisional,
            "protocol_id",
            "finance_v26_fresh_vtdo_admission_confirmation_protocol:",
        ),
        **values,
    )


def _transition(
    *,
    authorization: models.ExternalAuditAuthorization,
    source_replay: models.SourceReplayAudit,
    confirmation: models.FreshConfirmationProtocol,
) -> models.TransitionContract:
    values = {
        "authorization_id": authorization.authorization_id,
        "source_replay_audit_id": source_replay.audit_id,
        "fresh_confirmation_protocol_id": confirmation.protocol_id,
    }
    provisional = models.TransitionContract.model_construct(
        transition_id="pending",
        **values,
    )
    return models.TransitionContract(
        transition_id=models.identity(
            provisional,
            "transition_id",
            "finance_v26_bounded_policy_censoring_transition:",
        ),
        **values,
    )


def _detail_files(output_dir: Path, names: Sequence[str]) -> tuple[models.DetailFile, ...]:
    return tuple(
        models.DetailFile(
            relative_path=name,
            sha256=models.sha256(output_dir / name),
            byte_count=(output_dir / name).stat().st_size,
        )
        for name in sorted(names)
    )


def build_audit(
    *,
    package_root: Path,
    output_dir: Path,
) -> models.CapabilityCensoringAuditReport:
    preflight_dir = package_root / preflight.OUTPUT_DIR
    recovery_dir = package_root / recovery_models.OUTPUT_DIR
    postrun_dir = package_root / postrun_models.OUTPUT_DIR

    authorization = _authorization()
    source_replay = _source_replay(
        package_root=package_root,
        authorization=authorization,
    )
    cells = TaskConditionCellCatalogV2.model_validate(
        _load(preflight_dir / "task_condition_cell_catalog.json")
    )
    endpoint_catalog = postrun_models.IndependentEndpointCatalog.model_validate(
        _load(postrun_dir / "independent_endpoint_catalog.json")
    )
    cell_audit = postrun_models.IndependentCellFrequencyAudit.model_validate(
        _load(postrun_dir / "independent_cell_frequency_audit.json")
    )
    provider_audit = postrun_models.IndependentProviderArtifactAudit.model_validate(
        _load(postrun_dir / "independent_provider_artifact_audit.json")
    )
    mapper_audit = postrun_models.IndependentMapperAudit.model_validate(
        _load(postrun_dir / "independent_mapper_audit.json")
    )
    recovered_results = tuple(
        recovery_models.RawOnlyRecoveredMeasurementResult.model_validate(item)
        for item in _load(recovery_dir / "bounded_policy_measurement_results.json")
    )
    if (
        len(recovered_results) != 360
        or mapper_audit.formal_assignment_count != 106
        or cell_audit.exact_report_match_count != 48
    ):
        raise ValueError("v26.166 frozen endpoint, Assignment, or Cell denominator changed")

    strata = _cell_support_strata(
        cells=cells,
        cell_audit=cell_audit,
        endpoint_catalog=endpoint_catalog,
    )
    survival = _capability_survival_profile(
        cells=cells,
        endpoint_catalog=endpoint_catalog,
        recovered_results=recovered_results,
    )
    terminal_schema = _terminal_endpoint_schema_audit()
    typed_boundary = _typed_rejection_boundary(survival, recovered_results)
    admission = _vtdo_admission(strata)
    coverage = _coverage_gap_registry(strata)
    token_diagnostic = _token_diagnostic(provider_audit)
    confirmation = _fresh_confirmation_protocol()
    transition = _transition(
        authorization=authorization,
        source_replay=source_replay,
        confirmation=confirmation,
    )

    details: Mapping[str, Any] = {
        "capability_survival_profile_catalog.json": survival,
        "cell_support_stratum_catalog.json": strata,
        "coverage_gap_registry.json": coverage,
        "engineering_token_diagnostic.json": token_diagnostic,
        "external_audit_authorization.json": authorization,
        "fresh_confirmation_protocol.json": confirmation,
        "source_replay_audit.json": source_replay,
        "terminal_endpoint_schema_audit.json": terminal_schema,
        "transition_contract.json": transition,
        "typed_semantic_rejection_boundary_audit.json": typed_boundary,
        "vtdo_admission_catalog.json": admission,
    }
    for name, value in details.items():
        _write_json_once(output_dir / name, value)
    detail_files = _detail_files(output_dir, tuple(details))
    report_values = {
        "authorization_id": authorization.authorization_id,
        "source_replay_audit_id": source_replay.audit_id,
        "cell_support_stratum_catalog_id": strata.catalog_id,
        "capability_survival_profile_catalog_id": survival.catalog_id,
        "terminal_endpoint_schema_audit_id": terminal_schema.audit_id,
        "typed_semantic_rejection_boundary_audit_id": typed_boundary.audit_id,
        "vtdo_admission_catalog_id": admission.catalog_id,
        "coverage_gap_registry_id": coverage.registry_id,
        "engineering_token_diagnostic_id": token_diagnostic.diagnostic_id,
        "fresh_confirmation_protocol_id": confirmation.protocol_id,
        "transition_id": transition.transition_id,
        "detail_files": detail_files,
    }
    provisional = models.CapabilityCensoringAuditReport.model_construct(
        report_id="pending",
        **report_values,
    )
    report = models.CapabilityCensoringAuditReport(
        report_id=models.identity(
            provisional,
            "report_id",
            "finance_v26_bounded_policy_capability_censoring_audit_report:",
        ),
        **report_values,
    )
    _write_json_once(output_dir / "report.json", report)
    return report


def main() -> None:
    package_default = Path(__file__).resolve().parents[4]
    parser = argparse.ArgumentParser(
        description="Build the credential-free v26.166 capability censoring and VTDO audit."
    )
    parser.add_argument("--package-root", type=Path, default=package_default)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=package_default / models.OUTPUT_DIR,
    )
    args = parser.parse_args()
    report = build_audit(
        package_root=args.package_root.resolve(),
        output_dir=args.output_dir.resolve(),
    )
    print(
        json.dumps(
            {
                "report_id": report.report_id,
                "status": report.status,
                "next_stage": report.next_stage,
                "provider_calls": report.provider_calls,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
