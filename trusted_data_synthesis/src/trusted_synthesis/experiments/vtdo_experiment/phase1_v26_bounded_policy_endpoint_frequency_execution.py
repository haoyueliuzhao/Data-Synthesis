from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
import threading
from collections import Counter, defaultdict
from collections.abc import Callable, Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor, as_completed
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Final, cast

from trusted_synthesis.canonical_json import strict_canonical_hash
from trusted_synthesis.core.evaluation.bounded_policy_endpoint import (
    BoundedPolicyGlobalIntegrityGate,
    PolicyHorizonReason,
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
    phase1_v26_bounded_policy_endpoint_frequency_execution_models as models,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_bounded_policy_endpoint_frequency_preflight as preflight,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_reachability_execution as execution_base,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_mapper_v2_frequency_preflight_inputs as preflight_inputs,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_mapper_v2_frequency_static as preflight_static,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_valid_only_reachability_state_mapping_preflight as mapping_preflight,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_valid_only_state_semantics_audit as state_semantics,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_bounded_policy_endpoint_frequency_preflight_models import (  # noqa: E501
    BoundedPolicyEstimandContract,
    BoundedPolicyOutcomeContract,
    BoundedPolicyPreflightReport,
    BoundedPolicyRunnerContract,
    PredecessorReplayAudit,
    ProspectiveTransitionContract,
    RouteBSourceSelectionAudit,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_mapper_v2_frequency_preflight_models import (  # noqa: E501
    FrequencyAssignmentContract,
    FrequencyExecutionContract,
    FrequencyManifest,
    FreshFrequencySourcePopulation,
    MapperV2FrequencyProtocol,
    OmegaTaskContextCatalogV2,
)
from trusted_synthesis.hashing import canonical_hash
from trusted_synthesis.runtime.agent import prospective_reachability_runner_vnext as runner_vnext
from trusted_synthesis.runtime.agent.prospective_bounded_policy_endpoint_runner import (
    make_bounded_policy_endpoint_record,
)
from trusted_synthesis.runtime.agent.prospective_qualified_final_response_grammar import (
    QualifiedFinalResponseGrammar,
)
from trusted_synthesis.runtime.agent.prospective_two_stage_stage1_client import (
    StageOneProspectiveThinkingJsonClient,
)
from trusted_synthesis.runtime.agent.schema import AgentModelConfig

IMPLEMENTATION_PATH: Final = models.RUNNER_IMPLEMENTATION_PATH
MODEL_IMPLEMENTATION_PATH: Final = models.MODEL_IMPLEMENTATION_PATH
CHECKPOINT_NAME: Final = "bounded_policy_measurement_results.checkpoint.jsonl"
HORIZON_REASONS: Final[tuple[PolicyHorizonReason, ...]] = (
    "ordinary_detour_limit",
    "primary_request_limit",
    "provider_call_limit",
    "rollout_token_limit",
    "transport_invocation_limit",
)


def _json_payload(value: Any) -> Any:
    return models.json_payload(value)


def _canonical_bytes(value: Any) -> bytes:
    return models.canonical_bytes(value)


def _write_json_once(path: Path, value: Any) -> None:
    payload = _canonical_bytes(value)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_bytes() != payload:
            raise ValueError(f"v26.164 immutable artifact changed: {path}")
        return
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(payload)
    temporary.replace(path)


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _resolve_package_root(root: Path) -> Path:
    if (root / "src" / "trusted_synthesis").is_dir():
        return root
    candidate = root / "trusted_data_synthesis"
    if (candidate / "src" / "trusted_synthesis").is_dir():
        return candidate
    raise ValueError("v26.164 cannot resolve trusted_data_synthesis package root")


def _preflight_output_names(
    preflight_dir: Path,
) -> tuple[BoundedPolicyPreflightReport, tuple[str, ...]]:
    report = BoundedPolicyPreflightReport.model_validate(_load(preflight_dir / "report.json"))
    names = tuple(sorted(("report.json", *(item.relative_path for item in report.detail_files))))
    if len(names) != 34 or len(set(names)) != 34:
        raise ValueError("v26.164 frozen v26.163 output set changed")
    return report, names


def build_execution_source_replay(
    *,
    package_root: Path,
    implementation_root: Path,
    preflight_dir: Path,
) -> models.ExecutionSourceReplayAudit:
    report, names = _preflight_output_names(preflight_dir)
    report_path = preflight_dir / "report.json"
    predecessor = PredecessorReplayAudit.model_validate(
        _load(preflight_dir / "predecessor_replay_audit.json")
    )
    if (
        report.report_id != models.EXPECTED_PREFLIGHT_REPORT_ID
        or models.sha256(report_path) != models.EXPECTED_PREFLIGHT_REPORT_SHA256
        or predecessor.audit_id != models.EXPECTED_PREDECESSOR_REPLAY_ID
        or predecessor.migrated_checkout_snapshot_available
        or not predecessor.external_recovered_snapshot_available
        or predecessor.external_recovered_snapshot_sha256
        != preflight.EXPECTED_SOURCE_SNAPSHOT_SHA256
        or predecessor.external_recovered_snapshot_byte_count != 604_998_387
        or predecessor.v26_158_full_transitive_rebuild_claimed
    ):
        raise ValueError("v26.164 frozen v26.163 replay boundary changed")

    details = {item.relative_path: item for item in report.detail_files}
    direct_matches = 0
    for name in names:
        path = preflight_dir / name
        if not path.is_file():
            raise ValueError(f"v26.164 frozen v26.163 output missing: {name}")
        if name != "report.json":
            descriptor = details[name]
            if (
                models.sha256(path) != descriptor.sha256
                or path.stat().st_size != descriptor.byte_count
            ):
                raise ValueError(f"v26.164 frozen v26.163 output changed: {name}")
        direct_matches += 1

    with tempfile.TemporaryDirectory(prefix="v26_164_preflight_rebuild_") as temporary:
        rebuilt = Path(temporary)
        products = preflight.build_bounded_policy_endpoint_frequency_preflight(
            implementation_root=package_root,
            artifact_root=preflight.RECOVERED_ARTIFACT_ROOT,
            output_dir=rebuilt,
        )
        if products.report.report_id != models.EXPECTED_PREFLIGHT_REPORT_ID:
            raise ValueError("v26.164 rebuilt v26.163 report identity changed")
        rebuild_matches = 0
        for name in names:
            if (preflight_dir / name).read_bytes() != (rebuilt / name).read_bytes():
                raise ValueError(f"v26.164 independent preflight rebuild changed: {name}")
            rebuild_matches += 1

    implementation_files: list[models.ImplementationFileBinding] = []
    for relative_path in sorted((IMPLEMENTATION_PATH, MODEL_IMPLEMENTATION_PATH)):
        path = implementation_root / relative_path
        if not path.is_file():
            path = package_root / relative_path
        implementation_files.append(
            models.ImplementationFileBinding(
                relative_path=relative_path,
                sha256=models.sha256(path),
                byte_count=path.stat().st_size,
            )
        )
    implementation_bundle = tuple(implementation_files)
    values = {
        "preflight_output_byte_match_count": direct_matches,
        "independent_rebuild_output_count": rebuild_matches,
        "independent_rebuild_byte_match_count": rebuild_matches,
        "implementation_files": implementation_bundle,
        "implementation_bundle_sha256": hashlib.sha256(
            _canonical_bytes(
                tuple(item.model_dump(mode="python") for item in implementation_bundle)
            )
        ).hexdigest(),
    }
    provisional = models.ExecutionSourceReplayAudit.model_construct(audit_id="pending", **values)
    return models.ExecutionSourceReplayAudit(
        audit_id=models.identity(
            provisional,
            "audit_id",
            "finance_v26_bounded_policy_execution_source_replay:",
        ),
        **values,
    )


def _artifact_counts(output_dir: Path, manifest: FrequencyManifest) -> tuple[int, int]:
    raw_count = 0
    artifact_count = 0
    for job in manifest.jobs:
        if runner_vnext._raw_path(output_dir, job).is_file():  # noqa: SLF001
            raw_count += 1
        envelope_dir = execution_base.privacy_runner.provider_envelope_path(
            output_dir,
            cast(Any, job),
            0,
        ).parent
        projection_dir = execution_base.privacy_runner.payload_projection_path(
            output_dir,
            cast(Any, job),
            0,
        ).parent
        invocation_dir = execution_base.preflight.s1_runner._invocation_path(  # noqa: SLF001
            output_dir,
            cast(Any, job),
            0,
        ).parent
        artifact_count += sum(
            len(tuple(path.glob(pattern))) if path.exists() else 0
            for path, pattern in (
                (envelope_dir, "call_*.json"),
                (projection_dir, "call_*.json"),
                (invocation_dir, "invocation_*.json"),
            )
        )
    return raw_count, artifact_count


def _preexecution_binding(
    *,
    output_dir: Path,
    manifest: FrequencyManifest,
) -> models.PreexecutionBindingAudit:
    path = output_dir / "preexecution_binding_audit.json"
    if path.exists():
        return models.PreexecutionBindingAudit.model_validate(_load(path))
    raw_count, provider_count = _artifact_counts(output_dir, manifest)
    checkpoint = output_dir / CHECKPOINT_NAME
    checkpoint_rows = (
        len(tuple(line for line in checkpoint.read_text(encoding="utf-8").splitlines() if line))
        if checkpoint.exists()
        else 0
    )
    report_count = int((output_dir / "report.json").exists())
    endpoint_count = int((output_dir / "bounded_policy_endpoint_catalog.json").exists())
    if raw_count or provider_count or checkpoint_rows or report_count or endpoint_count:
        raise ValueError("v26.164 denominator was opened before the preexecution freeze")
    modes = Counter(item.sampling_mode for item in manifest.jobs)
    values = {
        "distinct_task_count": len({item.task_package_id for item in manifest.jobs}),
        "distinct_cell_count": len({item.task_condition_cell_id for item in manifest.jobs}),
        "distinct_path_count": len(
            {item.requested_path_id for item in manifest.jobs if item.requested_path_id is not None}
        ),
        "unconditional_job_count": modes["reachability_unconditional"],
        "conditioned_job_count": modes["reachability_conditioned"],
        "unopened_raw_count": raw_count,
        "unopened_provider_artifact_count": provider_count,
        "unopened_checkpoint_row_count": checkpoint_rows,
        "unopened_report_count": report_count,
        "unopened_endpoint_record_count": endpoint_count,
    }
    provisional = models.PreexecutionBindingAudit.model_construct(audit_id="pending", **values)
    audit = models.PreexecutionBindingAudit(
        audit_id=models.identity(
            provisional,
            "audit_id",
            "finance_v26_bounded_policy_preexecution_binding:",
        ),
        **values,
    )
    _write_json_once(path, audit)
    return audit


def _validate_exact_authorization(prepared: models.PreparedBoundedPolicyExecution) -> None:
    report = prepared.preflight_report
    manifest = prepared.manifest
    cells = {item.cell_id: item for item in prepared.cell_catalog.cells}
    modes = Counter(item.sampling_mode for item in manifest.jobs)
    if (
        report.report_id != models.EXPECTED_PREFLIGHT_REPORT_ID
        or report.predecessor_replay_audit_id != models.EXPECTED_PREDECESSOR_REPLAY_ID
        or report.source_population_id != models.EXPECTED_SOURCE_POPULATION_ID
        or report.source_selection_audit_id != models.EXPECTED_SOURCE_SELECTION_ID
        or report.task_package_catalog_id != models.EXPECTED_TASK_CATALOG_ID
        or report.path_catalog_id != models.EXPECTED_PATH_CATALOG_ID
        or report.support_closure_audit_id != models.EXPECTED_SUPPORT_ID
        or report.detour_qualification_audit_id != models.EXPECTED_DETOUR_ID
        or report.resource_contract_id != models.EXPECTED_RESOURCE_ID
        or report.generation_policy_id != models.EXPECTED_POLICY_ID
        or report.semantic_policy_id != models.EXPECTED_SEMANTIC_POLICY_ID
        or report.mapper_contract_id != models.EXPECTED_MAPPER_CONTRACT_ID
        or report.omega_task_context_catalog_id != models.EXPECTED_OMEGA_CATALOG_ID
        or report.task_condition_cell_catalog_id != models.EXPECTED_CELL_CATALOG_ID
        or report.frequency_assignment_contract_id != models.EXPECTED_ASSIGNMENT_CONTRACT_ID
        or report.mapper_protocol_id != models.EXPECTED_MAPPER_PROTOCOL_ID
        or report.estimand_contract_id != models.EXPECTED_ESTIMAND_CONTRACT_ID
        or report.execution_contract_id != models.EXPECTED_EXECUTION_CONTRACT_ID
        or report.manifest_id != models.EXPECTED_MANIFEST_ID
        or report.outcome_contract_id != models.EXPECTED_OUTCOME_CONTRACT_ID
        or report.runner_contract_id != models.EXPECTED_RUNNER_CONTRACT_ID
        or report.transition_contract_id != models.EXPECTED_TRANSITION_ID
        or report.prospective_execution_id != models.EXPECTED_PROSPECTIVE_EXECUTION_ID
        or report.prospective_report_id != models.EXPECTED_PROSPECTIVE_REPORT_ID
        or report.status != "fresh_bounded_policy_endpoint_frequency_preflight_passed"
        or report.next_permitted_stage != preflight.NEXT_STAGE
        or prepared.source_population.population_id != models.EXPECTED_SOURCE_POPULATION_ID
        or prepared.source_selection.audit_id != models.EXPECTED_SOURCE_SELECTION_ID
        or prepared.tasks.catalog_id != models.EXPECTED_TASK_CATALOG_ID
        or prepared.paths.catalog_id != models.EXPECTED_PATH_CATALOG_ID
        or prepared.support_closure.audit_id != models.EXPECTED_SUPPORT_ID
        or prepared.detour_qualification.audit_id != models.EXPECTED_DETOUR_ID
        or prepared.resource.contract_id != models.EXPECTED_RESOURCE_ID
        or prepared.policy.policy_id != models.EXPECTED_POLICY_ID
        or prepared.semantic_policy.policy_id != models.EXPECTED_SEMANTIC_POLICY_ID
        or prepared.mapper_contract.contract_id != models.EXPECTED_MAPPER_CONTRACT_ID
        or prepared.omega_catalog.catalog_id != models.EXPECTED_OMEGA_CATALOG_ID
        or prepared.cell_catalog.catalog_id != models.EXPECTED_CELL_CATALOG_ID
        or prepared.assignment_contract.contract_id != models.EXPECTED_ASSIGNMENT_CONTRACT_ID
        or prepared.mapper_protocol.protocol_id != models.EXPECTED_MAPPER_PROTOCOL_ID
        or prepared.estimand_contract.contract_id != models.EXPECTED_ESTIMAND_CONTRACT_ID
        or prepared.execution_contract.contract_id != models.EXPECTED_EXECUTION_CONTRACT_ID
        or manifest.manifest_id != models.EXPECTED_MANIFEST_ID
        or prepared.outcome_contract.contract_id != models.EXPECTED_OUTCOME_CONTRACT_ID
        or prepared.runner_contract.contract_id != models.EXPECTED_RUNNER_CONTRACT_ID
        or prepared.transition.contract_id != models.EXPECTED_TRANSITION_ID
        or prepared.transition.next_permitted_stage != preflight.NEXT_STAGE
        or not prepared.transition.exact_fresh_360_job_manifest_execution_authorized
        or not prepared.transition.bounded_policy_endpoint_semantics_required
        or len(manifest.jobs) != 360
        or len({item.job_id for item in manifest.jobs}) != 360
        or len({item.seed for item in manifest.jobs}) != 360
        or len(cells) != 48
        or modes
        != Counter(
            {
                "reachability_unconditional": 144,
                "reachability_conditioned": 216,
            }
        )
        or manifest.prospective_execution_run_id != models.RUN_ID
        or manifest.prospective_report_run_id != models.REPORT_RUN_ID
        or prepared.runner_contract.execution_run_id != models.RUN_ID
        or prepared.runner_contract.maximum_primary_stage_one_requests != 21
        or prepared.runner_contract.maximum_stage_one_provider_calls != 23
        or prepared.runner_contract.maximum_transport_inclusive_invocations != 24
        or prepared.runner_contract.maximum_ordinary_detours != 1
        or prepared.policy.maximum_primary_requests != 21
        or prepared.policy.maximum_provider_calls != 23
        or prepared.policy.maximum_transport_invocations != 24
        or prepared.policy.maximum_rollout_tokens != 1_120_000
        or prepared.policy.maximum_ordinary_detours != 1
        or prepared.outcome_contract.global_integrity_gate
        != (
            "bounded_policy_endpoint_360_of_360",
            "complete_raw_360_of_360",
            "privacy_failure_zero",
            "provider_identity_thinking_usage_failure_zero",
            "raw_instrument_failure_zero",
            "resource_accounting_failure_zero",
            "unresolved_transport_failure_zero",
            "unsupported_measurement_exit_zero",
        )
        or any(item.execution_opened for item in manifest.jobs)
        or any(item.task_condition_cell_id not in cells for item in manifest.jobs)
        or any(
            cells[item.task_condition_cell_id].experimental_condition != item.experimental_condition
            for item in manifest.jobs
        )
    ):
        raise ValueError("v26.164 exact online authorization changed")


def prepare_bounded_policy_execution(
    *,
    preflight_dir: Path,
    output_dir: Path,
    package_root: Path,
    implementation_root: Path,
) -> models.PreparedBoundedPolicyExecution:
    package_root = _resolve_package_root(package_root)
    output_dir.mkdir(parents=True, exist_ok=True)
    source = build_execution_source_replay(
        package_root=package_root,
        implementation_root=implementation_root,
        preflight_dir=preflight_dir,
    )
    _write_json_once(output_dir / "execution_source_replay_audit.json", source)

    report = BoundedPolicyPreflightReport.model_validate(_load(preflight_dir / "report.json"))
    population = FreshFrequencySourcePopulation.model_validate(
        _load(preflight_dir / "fresh_reachability_source_population.json")
    )
    selection = RouteBSourceSelectionAudit.model_validate(
        _load(preflight_dir / "source_selection_audit.json")
    )
    tasks = preflight_inputs.reachability.TaskPackageCatalog.model_validate(
        _load(preflight_dir / "reachability_task_package_catalog.json")
    )
    paths = preflight_inputs.reachability.PathCatalog.model_validate(
        _load(preflight_dir / "reachability_path_catalog.json")
    )
    support = preflight_inputs.reachability.SupportClosureAudit.model_validate(
        _load(preflight_dir / "support_closure_audit.json")
    )
    detours = preflight_inputs.reachability.ReachabilityDetourQualificationAudit.model_validate(
        _load(preflight_dir / "detour_qualification_audit.json")
    )
    resource = preflight_inputs.reachability.ResourceContract.model_validate(
        _load(preflight_dir / "reachability_resource_contract.json")
    )
    policy = preflight.BoundedPolicyEndpointGenerationPolicy.model_validate(
        _load(preflight_dir / "generation_policy.json")
    )
    omega = OmegaTaskContextCatalogV2.model_validate(
        _load(preflight_dir / "omega_task_context_catalog.json")
    )
    cells = models.TaskConditionCellCatalogV2.model_validate(
        _load(preflight_dir / "task_condition_cell_catalog.json")
    )
    assignment = FrequencyAssignmentContract.model_validate(
        _load(preflight_dir / "frequency_assignment_contract.json")
    )
    protocol = MapperV2FrequencyProtocol.model_validate(
        _load(preflight_dir / "mapper_v2_frequency_protocol.json")
    )
    estimand = BoundedPolicyEstimandContract.model_validate(
        _load(preflight_dir / "frequency_estimand_contract.json")
    )
    execution = FrequencyExecutionContract.model_validate(
        _load(preflight_dir / "frequency_execution_contract.json")
    )
    manifest = FrequencyManifest.model_validate(_load(preflight_dir / "frequency_manifest.json"))
    outcome = BoundedPolicyOutcomeContract.model_validate(
        _load(preflight_dir / "frequency_outcome_contract.json")
    )
    runner = BoundedPolicyRunnerContract.model_validate(
        _load(preflight_dir / "frequency_runner_contract.json")
    )
    transition = ProspectiveTransitionContract.model_validate(
        _load(preflight_dir / "prospective_transition_contract.json")
    )
    joint = execution_base.JointSupportValidityContract.model_validate(
        _load(preflight_dir / "joint_support_validity_contract.json")
    )
    grammar = QualifiedFinalResponseGrammar.model_validate(
        _load(preflight_dir / "qualified_final_response_grammar.json")
    )
    semantic_policy = state_semantics.EmpiricalStateSemanticPolicyV2.model_validate(
        _load(preflight_dir / "mapper_v2_semantic_policy.json")
    )
    mapper_contract = state_semantics.ValidOnlyStateMapperContractV2.model_validate(
        _load(preflight_dir / "mapper_v2_contract.json")
    )
    preexecution = _preexecution_binding(output_dir=output_dir, manifest=manifest)

    static = preflight_static.load_static_inputs(package_root)
    _, replay_contract = (
        preflight_inputs.reachability.bounded.predecessor._load_and_replay_verifier_qualification(  # noqa: SLF001,E501
            package_root
            / preflight_inputs.reachability.bounded.predecessor.VERIFIER_QUALIFICATION_DIR,
            package_root,
        )
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
        execution_contract=cast(Any, execution),
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
    prepared = models.PreparedBoundedPolicyExecution(
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
        execution_contract=execution,
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
    _validate_exact_authorization(prepared)

    frozen: tuple[tuple[str, Any], ...] = (
        ("frozen_v26_163_report.json", report),
        ("frozen_source_population.json", population),
        ("frozen_source_selection_audit.json", selection),
        ("frozen_task_package_catalog.json", tasks),
        ("frozen_path_catalog.json", paths),
        ("frozen_resource_contract.json", resource),
        ("frozen_measurement_support_closure.json", support),
        ("frozen_detour_qualification_audit.json", detours),
        ("frozen_generation_policy.json", policy),
        ("frozen_omega_task_context_catalog.json", omega),
        ("frozen_task_condition_cell_catalog.json", cells),
        ("frozen_frequency_assignment_contract.json", assignment),
        ("frozen_mapper_v2_frequency_protocol.json", protocol),
        ("frozen_bounded_policy_estimand_contract.json", estimand),
        ("frozen_frequency_execution_contract.json", execution),
        ("frozen_frequency_manifest.json", manifest),
        ("frozen_bounded_policy_outcome_contract.json", outcome),
        ("frozen_bounded_policy_runner_contract.json", runner),
        ("frozen_joint_support_validity_contract.json", joint),
        ("frozen_qualified_final_response_grammar.json", grammar),
        ("frozen_mapper_v2_semantic_policy.json", semantic_policy),
        ("frozen_mapper_v2_contract.json", mapper_contract),
        ("frozen_preflight_transition_contract.json", transition),
    )
    for name, value in frozen:
        _write_json_once(output_dir / name, value)
    return prepared


ClientFactory = Callable[[AgentModelConfig, Any, Any], Any]


def _default_client_factory(config: AgentModelConfig, _job: Any, _binding: Any) -> Any:
    return StageOneProspectiveThinkingJsonClient(config)


def _package_for_job(prepared: models.PreparedBoundedPolicyExecution, job: Any) -> Any:
    return execution_base._package_for_job(prepared.legacy_prepared, job)  # noqa: SLF001


def _expected_horizon_reason(raw: runner_vnext.FreshReachabilityRawExecution) -> str | None:
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
    raise ValueError("v26.164 undeclared typed-budget terminal cannot enter Route B")


def _run_one_job(
    *,
    job: Any,
    prepared: models.PreparedBoundedPolicyExecution,
    client_factory: ClientFactory | None,
    output_dir: Path,
) -> tuple[
    models.BoundedPolicyFrequencyMeasurementResult,
    runner_vnext.FreshReachabilityRawExecution,
]:
    package = _package_for_job(prepared, job)
    binding = execution_base._runtime_binding_for_job(  # noqa: SLF001
        prepared=prepared.legacy_prepared,
        package=package,
        job=job,
    )
    client = (
        None
        if client_factory is None
        else client_factory(
            prepared.legacy_prepared.role_inputs.static.agent_model_config,
            job,
            binding,
        )
    )
    raw = runner_vnext.execute_fresh_reachability_job_raw(
        job=job,
        runner_contract=prepared.runner_contract,
        resource_contract=prepared.resource,
        static=prepared.legacy_prepared.role_inputs.static,
        qualified_grammar=prepared.grammar,
        binding=binding,
        client=client,
        output_dir=output_dir,
    )
    legacy = execution_base.project_measurement_result(
        raw=raw,
        job=job,
        package=package,
        prepared=prepared.legacy_prepared,
        output_dir=output_dir,
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
    endpoint = make_bounded_policy_endpoint_record(
        raw=raw,
        policy=prepared.policy,
        provider_identity_integrity=provider_identity_integrity,
        thinking_usage_integrity=bool(
            legacy.thinking_continuity_passed and legacy.provider_usage_complete
        ),
        privacy_artifact_integrity=legacy.privacy_artifact_pairing_passed,
        transport_resolved=not legacy.unresolved_transport_failure,
        task_completion=raw.terminal_disposition == "completed_model_endpoint",
        base_validity=legacy.base_trajectory_validity,
        mechanism_qualification=legacy.mechanism_qualification,
        qualified_validity=legacy.qualified_trajectory_validity,
        task_verifier_invocation_count=legacy.task_verifier_invocation_count,
    )
    expected_horizon = _expected_horizon_reason(raw)
    actual_horizon = endpoint.projection.policy_horizon_reason
    if expected_horizon != actual_horizon:
        raise ValueError(
            "frozen v26.163 endpoint adapter did not recognize a declared Horizon: "
            f"expected={expected_horizon} actual={actual_horizon} "
            f"terminal={raw.terminal_disposition} failure={raw.terminal_failure_type}"
        )
    values = {
        "job_id": job.job_id,
        "task_condition_cell_id": job.task_condition_cell_id,
        "task_package_id": job.task_package_id,
        "experimental_condition_id": job.experimental_condition.condition_id,
        "legacy_joint_measurement_projection": legacy,
        "bounded_policy_endpoint_record": endpoint,
    }
    provisional = models.BoundedPolicyFrequencyMeasurementResult.model_construct(
        result_id="pending",
        **values,
    )
    return (
        models.BoundedPolicyFrequencyMeasurementResult(
            result_id=models.identity(
                provisional,
                "result_id",
                "finance_v26_bounded_policy_frequency_measurement_result:",
            ),
            **values,
        ),
        raw,
    )


def _write_checkpoint(
    path: Path,
    rows: Sequence[models.BoundedPolicyFrequencyMeasurementResult],
) -> None:
    payload = b"\n".join(_canonical_bytes(item).rstrip(b"\n") for item in rows)
    if payload:
        payload += b"\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(payload)
    temporary.replace(path)


def _load_checkpoint(
    path: Path,
    *,
    prepared: models.PreparedBoundedPolicyExecution,
    output_dir: Path,
) -> tuple[models.BoundedPolicyFrequencyMeasurementResult, ...]:
    if not path.exists():
        return ()
    rows = tuple(
        models.BoundedPolicyFrequencyMeasurementResult.model_validate_json(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    )
    jobs = {item.job_id: item for item in prepared.manifest.jobs}
    if len({item.job_id for item in rows}) != len(rows):
        raise ValueError("v26.164 checkpoint contains duplicate Jobs")
    for result in rows:
        job = jobs.get(result.job_id)
        legacy = result.legacy_joint_measurement_projection
        if (
            job is None
            or result.task_condition_cell_id != job.task_condition_cell_id
            or result.experimental_condition_id != job.experimental_condition.condition_id
            or result.generation_policy_id != job.generation_policy_id
        ):
            raise ValueError("v26.164 checkpoint crossed the exact Manifest or Cell")
        raw_path = runner_vnext._raw_path(output_dir, job)  # noqa: SLF001
        descriptor = legacy.raw_execution_artifact
        if (
            not raw_path.is_file()
            or models.sha256(raw_path) != descriptor.sha256
            or raw_path.stat().st_size != descriptor.byte_count
        ):
            raise ValueError("v26.164 checkpoint Raw binding changed")
        raw = runner_vnext.FreshReachabilityRawExecution.model_validate(_load(raw_path))
        expected_hash = strict_canonical_hash(
            raw,
            prefix="bounded_policy_parent_raw_execution:",
        )
        if result.bounded_policy_endpoint_record.raw_execution_content_hash != expected_hash:
            raise ValueError("v26.164 checkpoint endpoint crossed Raw content")
    return rows


def _global_gate(
    results: Sequence[models.BoundedPolicyFrequencyMeasurementResult],
    *,
    complete_raw_count: int,
) -> BoundedPolicyGlobalIntegrityGate:
    rows = tuple(item.bounded_policy_endpoint_record.projection for item in results)
    return make_bounded_policy_global_integrity_gate(
        exact_job_denominator=360,
        complete_raw_count=complete_raw_count,
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


def _make_frequency_assignment(
    *,
    job: Any,
    cell: Any,
    mapping_assignment: Any,
    gate: BoundedPolicyGlobalIntegrityGate,
) -> models.BoundedPolicyFrequencyAssignment:
    if not gate.passed:
        raise ValueError("v26.164 Assignment requires a passing Global Integrity Gate")
    values = {
        "job_id": job.job_id,
        "task_condition_cell_id": cell.cell_id,
        "task_package_id": cell.task_package_id,
        "experimental_condition_id": cell.experimental_condition_id,
        "global_integrity_gate_id": gate.gate_id,
        "mapping_assignment": mapping_assignment,
        "structural_state_id": mapping_assignment.structural_state_id,
        "empirical_route_signature_id": mapping_assignment.empirical_route_signature_id,
    }
    provisional = models.BoundedPolicyFrequencyAssignment.model_construct(
        assignment_id="pending",
        **values,
    )
    return models.BoundedPolicyFrequencyAssignment(
        assignment_id=models.identity(
            provisional,
            "assignment_id",
            "finance_v26_bounded_policy_frequency_assignment:",
        ),
        **values,
    )


def _map_after_global_gate(
    *,
    prepared: models.PreparedBoundedPolicyExecution,
    results: Sequence[models.BoundedPolicyFrequencyMeasurementResult],
    raws: Mapping[str, runner_vnext.FreshReachabilityRawExecution],
    gate: BoundedPolicyGlobalIntegrityGate,
) -> tuple[models.BoundedPolicyAssignmentCatalog, models.MapperExecutionAudit]:
    qualified = tuple(
        item
        for item in results
        if item.bounded_policy_endpoint_record.projection.qualified_validity is True
    )
    cells = {item.cell_id: item for item in prepared.cell_catalog.cells}
    contexts = {item.task_package_id: item.context_id for item in prepared.omega_catalog.contexts}
    jobs = {item.job_id: item for item in prepared.manifest.jobs}
    assignments: list[models.BoundedPolicyFrequencyAssignment] = []
    exact_matches = 0
    if gate.passed:
        for result in qualified:
            legacy = result.legacy_joint_measurement_projection
            raw = raws[result.job_id]
            job = jobs[result.job_id]
            package = _package_for_job(prepared, job)
            cell = cells[result.task_condition_cell_id]
            aliases = mapping_preflight._runtime_aliases(package, raw)  # noqa: SLF001
            trajectory = state_semantics._trajectory_projection_v2(  # noqa: SLF001
                raw=raw,
                result=legacy,
                semantic_policy=prepared.semantic_policy,
            )
            comparison = legacy.answer_comparison
            if comparison is None:
                raise ValueError("v26.164 Qualified row lacks Answer semantic comparison")
            raw_hash = legacy.raw_execution_artifact.sha256
            alias_hash = canonical_hash(
                aliases,
                prefix="finance_v26_runtime_operation_alias_binding:",
            )
            verifier_input_hash = strict_canonical_hash(
                {
                    "qualified_validity_report_id": (
                        legacy.joint_result.qualified_report.report_id
                    ),
                    "answer_comparison_id": comparison.comparison_id,
                    "answer_semantic_schema_id": trajectory.answer_semantic_schema_id,
                    "canonical_result_semantics_hash": trajectory.canonical_result_semantics_hash,
                    "trajectory_bound_artifact_hash": trajectory.trajectory_bound_artifact_hash,
                    "raw_execution_sha256": raw_hash,
                    "runtime_operation_alias_binding_hash": alias_hash,
                },
                prefix="finance_v26_qualified_verifier_input_v2:",
            )
            verifier_binding = make_qualified_verifier_input_binding_v2(
                trajectory=trajectory,
                qualified_validity_report=legacy.joint_result.qualified_report,
                raw_execution_artifact_hash=raw_hash,
                qualified_verifier_input_hash=verifier_input_hash,
            )
            mapping_assignment = map_independently_valid_public_trajectory_to_state_v2(
                trajectory=trajectory,
                qualified_validity_report=legacy.joint_result.qualified_report,
                verifier_input_binding=verifier_binding,
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
            if reference.structural_state != mapping_assignment.structural_state:
                raise ValueError(f"v26.164 independent Reference Mapper mismatch: {job.job_id}")
            exact_matches += 1
            assignments.append(
                _make_frequency_assignment(
                    job=job,
                    cell=cell,
                    mapping_assignment=mapping_assignment,
                    gate=gate,
                )
            )

    ordered = tuple(sorted(assignments, key=lambda item: item.assignment_id))
    catalog_values = {
        "global_integrity_gate_id": gate.gate_id,
        "assignments": ordered,
        "assignment_count": len(ordered),
        "structural_state_count": len({item.structural_state_id for item in ordered}),
        "empirical_route_signature_count": len(
            {item.empirical_route_signature_id for item in ordered}
        ),
        "global_integrity_gate_passed": gate.passed,
    }
    provisional_catalog = models.BoundedPolicyAssignmentCatalog.model_construct(
        catalog_id="pending",
        **catalog_values,
    )
    catalog = models.BoundedPolicyAssignmentCatalog(
        catalog_id=models.identity(
            provisional_catalog,
            "catalog_id",
            "finance_v26_bounded_policy_frequency_assignment_catalog:",
        ),
        **catalog_values,
    )
    mapper_values = {
        "global_integrity_gate_id": gate.gate_id,
        "qualified_row_count": len(qualified),
        "production_mapper_invocation_count": len(ordered),
        "reference_mapper_invocation_count": len(ordered),
        "production_reference_exact_state_match_count": exact_matches,
        "formal_assignment_count": len(ordered),
        "global_integrity_gate_passed": gate.passed,
    }
    provisional_mapper = models.MapperExecutionAudit.model_construct(
        audit_id="pending",
        **mapper_values,
    )
    mapper_audit = models.MapperExecutionAudit(
        audit_id=models.identity(
            provisional_mapper,
            "audit_id",
            "finance_v26_bounded_policy_mapper_execution:",
        ),
        **mapper_values,
    )
    return catalog, mapper_audit


def _cell_frequencies(
    *,
    prepared: models.PreparedBoundedPolicyExecution,
    results: Sequence[models.BoundedPolicyFrequencyMeasurementResult],
    gate: BoundedPolicyGlobalIntegrityGate,
    assignments: models.BoundedPolicyAssignmentCatalog,
) -> models.BoundedPolicyCellFrequencyCatalog:
    results_by_cell: dict[str, list[models.BoundedPolicyFrequencyMeasurementResult]] = defaultdict(
        list
    )
    assignment_states_by_cell: dict[str, list[str]] = defaultdict(list)
    for result in results:
        results_by_cell[result.task_condition_cell_id].append(result)
    for assignment in assignments.assignments:
        assignment_states_by_cell[assignment.task_condition_cell_id].append(
            assignment.structural_state_id
        )
    reports = []
    for cell in prepared.cell_catalog.cells:
        rows = results_by_cell[cell.cell_id]
        expected = (
            12 if cell.experimental_condition.sampling_mode == "reachability_unconditional" else 6
        )
        endpoint_count = sum(
            item.bounded_policy_endpoint_record.projection.bounded_policy_endpoint_observed
            for item in rows
        )
        if gate.passed:
            qualified_identifiers = tuple(assignment_states_by_cell[cell.cell_id])
        else:
            qualified_identifiers = tuple(
                item.job_id
                for item in rows
                if item.bounded_policy_endpoint_record.projection.qualified_validity is True
            )
        reports.append(
            summarize_bounded_policy_cell(
                task_condition_cell_id=cell.cell_id,
                generation_policy_id=prepared.policy.policy_id,
                global_gate=gate,
                expected_n_total=expected,
                observed_n_total=len(rows),
                endpoint_count=endpoint_count,
                qualified_state_ids=qualified_identifiers,
            )
        )
    ordered = tuple(sorted(reports, key=lambda item: item.report_id))
    values = {
        "global_integrity_gate_id": gate.gate_id,
        "reports": ordered,
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
        "global_integrity_gate_passed": gate.passed,
    }
    provisional = models.BoundedPolicyCellFrequencyCatalog.model_construct(
        catalog_id="pending",
        **values,
    )
    return models.BoundedPolicyCellFrequencyCatalog(
        catalog_id=models.identity(
            provisional,
            "catalog_id",
            "finance_v26_bounded_policy_cell_frequency_catalog:",
        ),
        **values,
    )


def _horizon_reason_audit(
    *,
    results: Sequence[models.BoundedPolicyFrequencyMeasurementResult],
    raws: Mapping[str, runner_vnext.FreshReachabilityRawExecution],
) -> models.HorizonReasonAudit:
    by_reason: dict[str, list[models.BoundedPolicyFrequencyMeasurementResult]] = defaultdict(list)
    for result in results:
        reason = result.bounded_policy_endpoint_record.projection.policy_horizon_reason
        if reason is not None:
            by_reason[reason].append(result)
    rows = []
    for reason in HORIZON_REASONS:
        reason_results = by_reason[reason]
        projections = tuple(
            item.bounded_policy_endpoint_record.projection for item in reason_results
        )
        reason_raws = tuple(raws[item.job_id] for item in reason_results)
        rows.append(
            models.HorizonReasonRow(
                reason=reason,
                endpoint_count=len(reason_results),
                later_provider_call_count=sum(
                    item.later_provider_calls_after_support_exit for item in reason_raws
                ),
                raw_instrument_failure_count=sum(
                    not item.raw_instrument_integrity for item in projections
                ),
                resource_accounting_failure_count=sum(
                    not item.resource_accounting_integrity for item in projections
                ),
                measurement_support_exit_count=sum(
                    not item.measurement_support_available for item in projections
                ),
                model_semantic_error_count=sum(item.model_outcome for item in projections),
            )
        )
    values = {
        "rows": tuple(rows),
        "policy_horizon_endpoint_count": sum(item.endpoint_count for item in rows),
    }
    provisional = models.HorizonReasonAudit.model_construct(audit_id="pending", **values)
    return models.HorizonReasonAudit(
        audit_id=models.identity(
            provisional,
            "audit_id",
            "finance_v26_bounded_policy_horizon_reason_audit:",
        ),
        **values,
    )


def _endpoint_catalog(
    *,
    results: Sequence[models.BoundedPolicyFrequencyMeasurementResult],
    horizon: models.HorizonReasonAudit,
) -> models.BoundedPolicyEndpointCatalog:
    ordered_results = tuple(
        sorted(results, key=lambda item: item.bounded_policy_endpoint_record.record_id)
    )
    records = tuple(item.bounded_policy_endpoint_record for item in ordered_results)
    projections = tuple(item.projection for item in records)
    values = {
        "records": records,
        "bounded_policy_endpoint_count": sum(
            item.bounded_policy_endpoint_observed for item in projections
        ),
        "model_terminal_count": sum(item.model_terminal_observed for item in projections),
        "policy_horizon_endpoint_count": sum(item.policy_terminal_observed for item in projections),
        "terminal_class_counts": dict(
            sorted(Counter(item.terminal_class for item in projections).items())
        ),
        "raw_terminal_disposition_counts": dict(
            sorted(
                Counter(
                    item.legacy_joint_measurement_projection.raw_terminal_disposition
                    for item in results
                ).items()
            )
        ),
        "horizon_reason_audit_id": horizon.audit_id,
    }
    provisional = models.BoundedPolicyEndpointCatalog.model_construct(
        catalog_id="pending",
        **values,
    )
    return models.BoundedPolicyEndpointCatalog(
        catalog_id=models.identity(
            provisional,
            "catalog_id",
            "finance_v26_bounded_policy_endpoint_catalog:",
        ),
        **values,
    )


def _raw_lineage(
    *,
    results: Sequence[models.BoundedPolicyFrequencyMeasurementResult],
    raws: Mapping[str, runner_vnext.FreshReachabilityRawExecution],
    output_dir: Path,
) -> models.RawLineageAudit:
    raw_descriptors = tuple(
        item.legacy_joint_measurement_projection.raw_execution_artifact
        for item in sorted(results, key=lambda row: row.job_id)
    )
    provider_descriptors = tuple(
        descriptor
        for job_id in sorted(raws)
        for descriptor in (
            *raws[job_id].provider_envelope_artifacts,
            *raws[job_id].public_payload_projection_artifacts,
            *raws[job_id].transport_invocation_artifacts,
        )
    )
    all_descriptors = (*raw_descriptors, *provider_descriptors)
    for descriptor in all_descriptors:
        path = output_dir / descriptor.relative_path
        if (
            not path.is_file()
            or models.sha256(path) != descriptor.sha256
            or path.stat().st_size != descriptor.byte_count
        ):
            raise ValueError("v26.164 Raw Lineage byte replay changed")
    provider_calls = sum(item.stage_one_provider_call_count for item in raws.values())
    values = {
        "provider_call_count": provider_calls,
        "transport_invocation_count": sum(
            item.transport_inclusive_invocation_count for item in raws.values()
        ),
        "provider_envelope_count": sum(
            len(item.provider_envelope_artifacts) for item in raws.values()
        ),
        "public_projection_count": sum(
            len(item.public_payload_projection_artifacts) for item in raws.values()
        ),
        "complete_provider_pair_count": provider_calls,
        "raw_descriptors": raw_descriptors,
        "provider_artifact_descriptors": provider_descriptors,
        "exact_byte_replay_pass_count": len(all_descriptors),
    }
    provisional = models.RawLineageAudit.model_construct(audit_id="pending", **values)
    return models.RawLineageAudit(
        audit_id=models.identity(
            provisional,
            "audit_id",
            "finance_v26_bounded_policy_raw_lineage:",
        ),
        **values,
    )


def _detail(path: Path, output_dir: Path) -> models.DetailFile:
    return models.DetailFile(
        relative_path=str(path.resolve().relative_to(output_dir.resolve())),
        sha256=models.sha256(path),
        byte_count=path.stat().st_size,
    )


def _execution_report(
    *,
    prepared: models.PreparedBoundedPolicyExecution,
    results: Sequence[models.BoundedPolicyFrequencyMeasurementResult],
    gate: BoundedPolicyGlobalIntegrityGate,
    endpoints: models.BoundedPolicyEndpointCatalog,
    horizon: models.HorizonReasonAudit,
    lineage: models.RawLineageAudit,
    mapper: models.MapperExecutionAudit,
    assignments: models.BoundedPolicyAssignmentCatalog,
    cells: models.BoundedPolicyCellFrequencyCatalog,
    detail_files: Sequence[models.DetailFile],
) -> models.BoundedPolicyExecutionReport:
    legacy = tuple(item.legacy_joint_measurement_projection for item in results)
    projections = tuple(item.bounded_policy_endpoint_record.projection for item in results)
    cost = sum((Decimal(item.estimated_cost_usd) for item in legacy), Decimal("0"))
    reason_counts = {item.reason: item.endpoint_count for item in horizon.rows}
    values = {
        "source_replay_audit_id": prepared.source_replay.audit_id,
        "preexecution_binding_audit_id": prepared.preexecution_binding.audit_id,
        "global_integrity_gate_id": gate.gate_id,
        "endpoint_catalog_id": endpoints.catalog_id,
        "horizon_reason_audit_id": horizon.audit_id,
        "raw_lineage_audit_id": lineage.audit_id,
        "mapper_execution_audit_id": mapper.audit_id,
        "assignment_catalog_id": assignments.catalog_id,
        "cell_frequency_catalog_id": cells.catalog_id,
        "bounded_policy_endpoint_count": endpoints.bounded_policy_endpoint_count,
        "model_terminal_count": endpoints.model_terminal_count,
        "policy_horizon_endpoint_count": endpoints.policy_horizon_endpoint_count,
        "raw_terminal_counts": endpoints.raw_terminal_disposition_counts,
        "bounded_policy_terminal_counts": endpoints.terminal_class_counts,
        "policy_horizon_reason_counts": reason_counts,
        "global_integrity_gate_passed": gate.passed,
        "all_cell_estimands_null": not gate.passed,
        "validity_evaluable_count": sum(item.validity_evaluable for item in projections),
        "base_valid_count": sum(item.base_validity is True for item in projections),
        "mechanism_qualified_count": sum(
            item.mechanism_qualification is True for item in projections
        ),
        "qualified_valid_count": sum(item.qualified_validity is True for item in projections),
        "formal_assignment_count": assignments.assignment_count,
        "structural_state_count": assignments.structural_state_count,
        "empirical_route_signature_count": assignments.empirical_route_signature_count,
        "q_instantiated_cell_count": cells.q_instantiated_cell_count,
        "pi_instantiated_cell_count": cells.pi_instantiated_cell_count,
        "zero_qualified_cell_count": cells.zero_qualified_cell_count,
        "empirical_non_degenerate_cell_count": cells.empirical_non_degenerate_cell_count,
        "provider_call_count": lineage.provider_call_count,
        "transport_inclusive_invocation_count": lineage.transport_invocation_count,
        "provider_prompt_tokens": sum(item.provider_prompt_tokens for item in legacy),
        "provider_completion_tokens": sum(item.provider_completion_tokens for item in legacy),
        "provider_reasoning_tokens": sum(item.provider_reasoning_tokens for item in legacy),
        "provider_total_tokens": sum(item.provider_total_tokens for item in legacy),
        "estimated_cost_usd": format(cost, "f"),
        "detail_files": tuple(sorted(detail_files, key=lambda item: item.relative_path)),
        "execution_status": (
            "global_integrity_gate_passed_bounded_policy_frequency_pending_independent_audit"
            if gate.passed
            else "global_integrity_gate_failed_all_cell_estimands_null_pending_independent_audit"
        ),
    }
    provisional = models.BoundedPolicyExecutionReport.model_construct(
        report_id="pending",
        **values,
    )
    return models.BoundedPolicyExecutionReport(
        report_id=models.identity(
            provisional,
            "report_id",
            "finance_v26_bounded_policy_frequency_execution_report:",
        ),
        **values,
    )


def _transition(
    *,
    report: models.BoundedPolicyExecutionReport,
    gate: BoundedPolicyGlobalIntegrityGate,
    endpoints: models.BoundedPolicyEndpointCatalog,
    assignments: models.BoundedPolicyAssignmentCatalog,
    cells: models.BoundedPolicyCellFrequencyCatalog,
) -> models.PostrunTransitionContract:
    values = {
        "execution_report_id": report.report_id,
        "global_integrity_gate_id": gate.gate_id,
        "endpoint_catalog_id": endpoints.catalog_id,
        "assignment_catalog_id": assignments.catalog_id,
        "cell_frequency_catalog_id": cells.catalog_id,
    }
    provisional = models.PostrunTransitionContract.model_construct(
        contract_id="pending",
        **values,
    )
    return models.PostrunTransitionContract(
        contract_id=models.identity(
            provisional,
            "contract_id",
            "finance_v26_bounded_policy_execution_transition:",
        ),
        **values,
    )


def run_bounded_policy_execution(
    *,
    preflight_dir: Path,
    output_dir: Path,
    package_root: Path,
    implementation_root: Path,
    workers: int,
    client_factory: ClientFactory = _default_client_factory,
) -> models.BoundedPolicyExecutionReport:
    prepared = prepare_bounded_policy_execution(
        preflight_dir=preflight_dir,
        output_dir=output_dir,
        package_root=package_root,
        implementation_root=implementation_root,
    )
    checkpoint_path = output_dir / CHECKPOINT_NAME
    existing = _load_checkpoint(
        checkpoint_path,
        prepared=prepared,
        output_dir=output_dir,
    )
    completed = {item.job_id: item for item in existing}
    jobs = prepared.manifest.jobs
    pending = [item for item in jobs if item.job_id not in completed]
    report_path = output_dir / "report.json"
    if pending and report_path.exists():
        raise ValueError("v26.164 report exists while frozen Jobs remain pending")
    if not pending and report_path.exists():
        report = models.BoundedPolicyExecutionReport.model_validate(_load(report_path))
        if (
            report.runner_contract_id != prepared.runner_contract.contract_id
            or report.source_replay_audit_id != prepared.source_replay.audit_id
        ):
            raise ValueError("v26.164 completed report crossed frozen bindings")
        return report

    raw_recovery_jobs = [
        item
        for item in pending
        if runner_vnext._raw_path(output_dir, item).exists()  # noqa: SLF001
    ]
    model_pending_jobs = [
        item
        for item in pending
        if not runner_vnext._raw_path(output_dir, item).exists()  # noqa: SLF001
    ]
    for job in model_pending_jobs:
        execution_base._assert_no_orphan_artifacts(output_dir, job)  # noqa: SLF001

    print(
        f"[v26.164] resuming {len(completed)}/360; "
        f"raw-only recovery {len(raw_recovery_jobs)}; "
        f"executing {len(model_pending_jobs)} Jobs with {workers} workers",
        flush=True,
    )
    raw_by_job: dict[str, runner_vnext.FreshReachabilityRawExecution] = {}
    for job in jobs:
        raw_path = runner_vnext._raw_path(output_dir, job)  # noqa: SLF001
        if raw_path.exists() and job.job_id in completed:
            raw_by_job[job.job_id] = runner_vnext.FreshReachabilityRawExecution.model_validate(
                _load(raw_path)
            )
    lock = threading.Lock()

    def record_completion(
        *,
        job: Any,
        result: models.BoundedPolicyFrequencyMeasurementResult,
        raw: runner_vnext.FreshReachabilityRawExecution,
        recovered: bool = False,
    ) -> None:
        with lock:
            completed[job.job_id] = result
            raw_by_job[job.job_id] = raw
            ordered = tuple(completed[item.job_id] for item in jobs if item.job_id in completed)
            _write_checkpoint(checkpoint_path, ordered)
            endpoint = result.bounded_policy_endpoint_record.projection
            label = " recovered" if recovered else ""
            print(
                f"[v26.164]{label} completed {len(completed)}/360 "
                f"{job.job_id.rsplit(':', 1)[-1][:12]} "
                f"mechanism={job.mechanism_id} tier={job.tier} "
                f"sampling={job.sampling_mode} "
                f"route={job.public_path_condition or 'none'} "
                f"raw_terminal={raw.terminal_disposition} "
                f"policy_terminal={endpoint.terminal_class} "
                f"horizon={endpoint.policy_horizon_reason or 'none'} "
                f"endpoint={endpoint.bounded_policy_endpoint_observed} "
                f"qualified={endpoint.qualified_validity} "
                f"calls={raw.stage_one_provider_call_count}",
                flush=True,
            )

    worker_failures: list[tuple[Any, str]] = []
    with ThreadPoolExecutor(max_workers=max(1, min(workers, len(pending) or 1))) as executor:
        futures = {
            executor.submit(
                _run_one_job,
                job=job,
                prepared=prepared,
                client_factory=(None if job in raw_recovery_jobs else client_factory),
                output_dir=output_dir,
            ): job
            for job in pending
        }
        for future in as_completed(futures):
            job = futures[future]
            try:
                result, raw = future.result()
            except Exception as error:
                worker_failures.append((job, type(error).__name__))
                print(
                    "[v26.164] worker exception retained for Raw-only recovery: "
                    f"job={job.job_id} type={type(error).__name__} "
                    f"raw_persisted={runner_vnext._raw_path(output_dir, job).is_file()}",  # noqa: SLF001
                    flush=True,
                )
                continue
            record_completion(job=job, result=result, raw=raw)

    unresolved: list[tuple[Any, str]] = []
    for job, failure_type in worker_failures:
        if not runner_vnext._raw_path(output_dir, job).is_file():  # noqa: SLF001
            unresolved.append((job, failure_type))
            continue
        try:
            result, raw = _run_one_job(
                job=job,
                prepared=prepared,
                client_factory=None,
                output_dir=output_dir,
            )
        except Exception as error:
            unresolved.append((job, type(error).__name__))
            print(
                "[v26.164] Raw-only recovery failed closed: "
                f"job={job.job_id} type={type(error).__name__}",
                flush=True,
            )
            continue
        record_completion(job=job, result=result, raw=raw, recovered=True)
    if unresolved:
        raise RuntimeError(
            "v26.164 unresolved worker failures after every future drained: "
            f"count={len(unresolved)} "
            f"types={dict(sorted(Counter(kind for _, kind in unresolved).items()))}"
        )

    results = tuple(completed[item.job_id] for item in jobs)
    if len(results) != 360:
        raise ValueError("v26.164 execution denominator is incomplete")
    for job in jobs:
        if job.job_id not in raw_by_job:
            raw_by_job[job.job_id] = runner_vnext.FreshReachabilityRawExecution.model_validate(
                _load(runner_vnext._raw_path(output_dir, job))  # noqa: SLF001
            )

    gate = _global_gate(results, complete_raw_count=len(raw_by_job))
    assignments, mapper_audit = _map_after_global_gate(
        prepared=prepared,
        results=results,
        raws=raw_by_job,
        gate=gate,
    )
    cells = _cell_frequencies(
        prepared=prepared,
        results=results,
        gate=gate,
        assignments=assignments,
    )
    horizon = _horizon_reason_audit(results=results, raws=raw_by_job)
    endpoints = _endpoint_catalog(results=results, horizon=horizon)
    lineage = _raw_lineage(results=results, raws=raw_by_job, output_dir=output_dir)

    outputs: tuple[tuple[str, Any], ...] = (
        ("bounded_policy_measurement_results.json", results),
        ("bounded_policy_global_integrity_gate.json", gate),
        ("bounded_policy_endpoint_catalog.json", endpoints),
        ("bounded_policy_horizon_reason_audit.json", horizon),
        ("bounded_policy_assignment_catalog.json", assignments),
        ("mapper_execution_audit.json", mapper_audit),
        ("bounded_policy_cell_frequency_catalog.json", cells),
        ("raw_lineage_audit.json", lineage),
    )
    for name, value in outputs:
        _write_json_once(output_dir / name, value)
    details = tuple(_detail(output_dir / name, output_dir) for name, _ in outputs)
    report = _execution_report(
        prepared=prepared,
        results=results,
        gate=gate,
        endpoints=endpoints,
        horizon=horizon,
        lineage=lineage,
        mapper=mapper_audit,
        assignments=assignments,
        cells=cells,
        detail_files=details,
    )
    _write_json_once(report_path, report)
    transition = _transition(
        report=report,
        gate=gate,
        endpoints=endpoints,
        assignments=assignments,
        cells=cells,
    )
    _write_json_once(output_dir / "postrun_transition_contract.json", transition)
    return report


def main() -> None:
    package_default = Path(__file__).resolve().parents[4]
    parser = argparse.ArgumentParser(
        description="Run the exact v26.164 Route B bounded-policy 360-Job denominator"
    )
    parser.add_argument(
        "--preflight-dir",
        type=Path,
        default=package_default / models.PREFLIGHT_DIR,
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=package_default / models.OUTPUT_DIR,
    )
    parser.add_argument("--package-root", type=Path, default=package_default)
    parser.add_argument("--implementation-root", type=Path, default=package_default)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--prepare-only", action="store_true")
    args = parser.parse_args()
    if args.prepare_only:
        prepared = prepare_bounded_policy_execution(
            preflight_dir=args.preflight_dir,
            output_dir=args.output_dir,
            package_root=args.package_root,
            implementation_root=args.implementation_root,
        )
        print(
            json.dumps(
                {
                    "status": "prepared",
                    "source_replay_audit_id": prepared.source_replay.audit_id,
                    "preexecution_binding_audit_id": prepared.preexecution_binding.audit_id,
                    "manifest_id": prepared.manifest.manifest_id,
                    "runner_contract_id": prepared.runner_contract.contract_id,
                    "generation_policy_id": prepared.policy.policy_id,
                    "exact_jobs": len(prepared.manifest.jobs),
                    "distinct_cells": len(prepared.cell_catalog.cells),
                    "model_client_constructed": False,
                    "provider_calls": 0,
                    "formal_assignments": 0,
                },
                indent=2,
                sort_keys=True,
            )
        )
        return
    report = run_bounded_policy_execution(
        preflight_dir=args.preflight_dir,
        output_dir=args.output_dir,
        package_root=args.package_root,
        implementation_root=args.implementation_root,
        workers=args.workers,
    )
    print(report.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
