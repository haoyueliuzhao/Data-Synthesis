from __future__ import annotations

import hashlib
import itertools
import tempfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from trusted_synthesis.canonical_json import strict_canonical_hash
from trusted_synthesis.core.evaluation.joint_support_validity import (
    JointSupportValidityContract,
    evaluate_joint_support_validity,
)
from trusted_synthesis.core.evaluation.trajectory_validity import (
    BaseValidityChecks,
    QualifiedTrajectoryValidityReport,
    make_noninterference_artifact_binding,
)
from trusted_synthesis.core.evaluation.valid_only_state_mapping_v2 import (
    ValidOnlyStateMapperContractV2,
    make_qualified_verifier_input_binding_v2,
)
from trusted_synthesis.core.trajectory.empirical_state_mapping_v2 import (
    EmpiricalStateSemanticPolicyV2,
    EmpiricalStructuralStateV2,
    PublicTrajectoryActionV2,
    PublicTrajectoryProjectionV2,
    ValidOnlyEmpiricalStateAssignmentV2,
    make_empirical_route_signature_v2,
    make_public_trajectory_action_v2,
    make_public_trajectory_projection_v2,
    make_state_contrast_v2,
    map_independently_valid_public_trajectory_to_state_v2,
)
from trusted_synthesis.core.trajectory.reachability_frequency_v2 import (
    FrequencyMeasurementGateV2,
    ReachabilityFrequencyAssignmentV2,
    TaskConditionCellCatalogV2,
    TaskConditionCellV2,
    make_frequency_measurement_gate_v2,
    make_reachability_frequency_assignment_v2,
    summarize_reachability_frequency_v2,
)
from trusted_synthesis.core.trajectory.reference_empirical_state_mapping_v2 import (
    reference_map_public_trajectory_v2,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_reachability_runner_preflight as reachability,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_mapper_v2_frequency_preflight_inputs as base,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_s1_representation_qualification_preflight as s1_runner,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_valid_only_reachability_state_mapping_preflight as mapping_preflight,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_mapper_v2_frequency_preflight_models import (  # noqa: E501
    FrequencyApiFixtureAudit,
    FrequencyManifest,
    FrequencyRunnerContract,
    IndependentMapperPreflightAudit,
    WithinCellContrastAudit,
)
from trusted_synthesis.hashing import canonical_hash
from trusted_synthesis.runtime.agent import prospective_reachability_runner_vnext as runner_vnext
from trusted_synthesis.runtime.agent.prospective_qualified_final_response_grammar import (
    QualifiedFinalResponseGrammar,
)


@dataclass(frozen=True)
class MapperFixtureProducts:
    audit: IndependentMapperPreflightAudit
    frequency_assignments: tuple[ReachabilityFrequencyAssignmentV2, ...]
    mapping_assignments: tuple[ValidOnlyEmpiricalStateAssignmentV2, ...]
    trajectories: tuple[PublicTrajectoryProjectionV2, ...]
    passing_gate: FrequencyMeasurementGateV2


def _base_checks() -> BaseValidityChecks:
    return BaseValidityChecks.model_validate(
        {item: True for item in reachability.predecessor.predecessor.BASE_CHECK_IDS}
    )


def _joint_result(
    *,
    joint: JointSupportValidityContract,
    raw: runner_vnext.FreshReachabilityRawExecution,
    package: reachability.FreshReachabilityTaskPackage,
) -> Any:
    noninterference = make_noninterference_artifact_binding(
        noninterference_contract_id="v26.160-fixture-noninterference-contract",
        noninterference_audit_id=f"v26.160-fixture-audit:{package.task_package_id}",
        task_package_id=package.task_package_id,
    )
    result = evaluate_joint_support_validity(
        contract=joint,
        support_decision=raw.measurement_support_decisions[-1],
        trajectory_id=raw.artifact_id,
        task_package_id=package.task_package_id,
        model_endpoint_observed=True,
        instrument_integrity=True,
        privacy_compliant=True,
        mechanism_id=package.mechanism_id,
        base_checks=_base_checks(),
        noninterference_binding=noninterference,
        observed_mechanism_event_ids=joint.required_event_ids_by_mechanism[package.mechanism_id],
    )
    if result.qualified_report.valid is not True or result.task_verifier_invocation_count != 1:
        raise ValueError("v26.160 fixture did not cross Qualified validity")
    return result


def _trajectory_projection(
    *,
    raw: runner_vnext.FreshReachabilityRawExecution,
    semantic_policy: EmpiricalStateSemanticPolicyV2,
) -> PublicTrajectoryProjectionV2:
    observations = {item.call.call_index: item for item in raw.observations}
    actions: list[PublicTrajectoryActionV2] = []
    for action_index, record in enumerate(raw.commits):
        commit = record.commit
        call = commit.call
        observation = observations.get(call.call_index) if call is not None else None
        actions.append(
            make_public_trajectory_action_v2(
                action_index=action_index,
                decision_kind=commit.decision_kind,
                action_kind=commit.action,
                tool_id=call.tool_id if call is not None else None,
                arguments=dict(call.arguments) if call is not None else None,
                observation_status=observation.status if observation is not None else None,
                error_code=observation.error_code if observation is not None else None,
                observation_result=(dict(observation.result) if observation is not None else None),
                evidence_ids=(observation.evidence_ids if observation is not None else ()),
                provenance_hashes=(
                    observation.provenance_hashes if observation is not None else ()
                ),
                reference_policy=semantic_policy.typed_reference_policy,
            )
        )
    completed = raw.completed_result
    if completed is None:
        raise ValueError("v26.160 fixture trajectory lacks a qualified Final payload")
    raw_result = dict(completed.final_payload.answer.result)
    citations = tuple(
        sorted({item.evidence_id for item in completed.final_payload.answer.citations})
    )
    return make_public_trajectory_projection_v2(
        trajectory_id=raw.artifact_id,
        terminal_disposition=raw.terminal_disposition,
        actions=actions,
        semantic_rejections=tuple(item.model_dump(mode="json") for item in raw.semantic_rejections),
        raw_final_result=raw_result,
        canonical_result=raw_result,
        answer_semantic_schema_id="finance_v26_frequency_fixture_answer_semantics.v1",
        reference_projection_policy_id=semantic_policy.reference_projection_policy_id,
        final_citations=citations,
    )


def _map_trajectory(
    *,
    trajectory: PublicTrajectoryProjectionV2,
    qualified_report: QualifiedTrajectoryValidityReport,
    raw_artifact_hash: str,
    omega_context_id: str,
    cell: TaskConditionCellV2,
    aliases: Mapping[str, str],
    semantic_policy: EmpiricalStateSemanticPolicyV2,
    mapper_contract: ValidOnlyStateMapperContractV2,
) -> ValidOnlyEmpiricalStateAssignmentV2:
    verifier_input_hash = strict_canonical_hash(
        {
            "qualified_validity_report_id": qualified_report.report_id,
            "answer_semantic_schema_id": trajectory.answer_semantic_schema_id,
            "canonical_result_semantics_hash": trajectory.canonical_result_semantics_hash,
            "trajectory_bound_artifact_hash": trajectory.trajectory_bound_artifact_hash,
            "raw_execution_artifact_hash": raw_artifact_hash,
            "runtime_operation_aliases": dict(aliases),
        },
        prefix="finance_v26_frequency_fixture_verifier_input:",
    )
    binding = make_qualified_verifier_input_binding_v2(
        trajectory=trajectory,
        qualified_validity_report=qualified_report,
        raw_execution_artifact_hash=raw_artifact_hash,
        qualified_verifier_input_hash=verifier_input_hash,
    )
    return map_independently_valid_public_trajectory_to_state_v2(
        trajectory=trajectory,
        qualified_validity_report=qualified_report,
        verifier_input_binding=binding,
        mapper_contract=mapper_contract,
        omega_task_context_id=omega_context_id,
        experimental_condition=cell.experimental_condition,
        empirical_route_signature=make_empirical_route_signature_v2(trajectory),
        runtime_operation_aliases=aliases,
        semantic_policy=semantic_policy,
        raw_execution_artifact_hash=raw_artifact_hash,
    )


def make_generation_fixture(
    *,
    tasks: reachability.TaskPackageCatalog,
    registered: Sequence[reachability._CompiledPath],
    unconditional: Sequence[reachability._CompiledPath],
    manifest: FrequencyManifest,
    resource: reachability.ResourceContract,
    runner: FrequencyRunnerContract,
    joint: JointSupportValidityContract,
    grammar: QualifiedFinalResponseGrammar,
    static: Any,
) -> reachability.RunnerFixtureAudit:
    return reachability._make_fixture(  # noqa: SLF001
        tasks=tasks,
        registered_paths=registered,
        unconditional_paths=unconditional,
        manifest=cast(Any, manifest),
        resource=resource,
        runner=cast(Any, runner),
        joint=joint,
        grammar=grammar,
        static=static,
    )


def make_independent_mapper_preflight(
    *,
    tasks: reachability.TaskPackageCatalog,
    registered: Sequence[reachability._CompiledPath],
    unconditional: Sequence[reachability._CompiledPath],
    manifest: FrequencyManifest,
    resource: reachability.ResourceContract,
    runner: FrequencyRunnerContract,
    joint: JointSupportValidityContract,
    grammar: QualifiedFinalResponseGrammar,
    static: Any,
    cells: TaskConditionCellCatalogV2,
    omega_contexts: Mapping[str, str],
    semantic_policy: EmpiricalStateSemanticPolicyV2,
    mapper_contract: ValidOnlyStateMapperContractV2,
) -> MapperFixtureProducts:
    packages = {item.task_package_id: item for item in tasks.packages}
    paths = {
        cast(reachability.FreshReachabilityPath, item.path).path_id: item for item in registered
    }
    natural = {item.package.task_package_id: item for item in unconditional}
    jobs_by_cell: dict[str, list[Any]] = {}
    for job in manifest.jobs:
        jobs_by_cell.setdefault(job.task_condition_cell_id, []).append(job)
    cells_by_id = {item.cell_id: item for item in cells.cells}
    selected_jobs = tuple(
        sorted(
            (sorted(rows, key=lambda item: item.job_id)[0] for rows in jobs_by_cell.values()),
            key=lambda item: item.job_id,
        )
    )
    if len(selected_jobs) != base.CELL_COUNT:
        raise ValueError("v26.160 Mapper fixture does not cover all TaskConditionCells")
    passing_gate = make_frequency_measurement_gate_v2(
        exact_job_denominator=base.CELL_COUNT,
        complete_raw_count=base.CELL_COUNT,
        model_endpoint_count=base.CELL_COUNT,
        validity_evaluable_count=base.CELL_COUNT,
    )
    mapped: list[ValidOnlyEmpiricalStateAssignmentV2] = []
    frequency: list[ReachabilityFrequencyAssignmentV2] = []
    trajectories: list[PublicTrajectoryProjectionV2] = []
    reference_state_ids: list[str] = []
    with tempfile.TemporaryDirectory(prefix="v26_160_mapper_fixture_") as temporary:
        root = Path(temporary)
        for job in selected_jobs:
            package = packages[job.task_package_id]
            execution = (
                natural[job.task_package_id]
                if job.requested_path_id is None
                else paths[job.requested_path_id]
            )
            final_answer = reachability._reference_final_answer(  # noqa: SLF001
                execution,
                old_grammar=static.final_grammar,
            )
            client = s1_runner.ScriptedS1QualificationClient(
                static.agent_model_config,
                final_answer=final_answer,
            )
            binding = reachability._runtime_binding(  # noqa: SLF001
                package,
                package.frozen_input_audit_id,
                path_strategy_id=execution.path_strategy_id,
                public_path_condition=execution.public_path_condition,
            )
            raw = runner_vnext.execute_fresh_reachability_job_raw(
                job=job,
                runner_contract=runner,
                resource_contract=resource,
                static=static,
                qualified_grammar=grammar,
                binding=binding,
                client=client,
                output_dir=root,
            )
            recovered = runner_vnext.execute_fresh_reachability_job_raw(
                job=job,
                runner_contract=runner,
                resource_contract=resource,
                static=static,
                qualified_grammar=grammar,
                binding=binding,
                client=None,
                output_dir=root,
            )
            if recovered != raw or raw.terminal_disposition != "completed_model_endpoint":
                raise ValueError("v26.160 Mapper fixture Raw execution or recovery changed")
            joint_result = _joint_result(joint=joint, raw=raw, package=package)
            trajectory = _trajectory_projection(raw=raw, semantic_policy=semantic_policy)
            aliases = mapping_preflight._runtime_aliases(package, raw)  # noqa: SLF001
            cell = cells_by_id[job.task_condition_cell_id]
            raw_hash = strict_canonical_hash(raw, prefix="finance_v26_frequency_fixture_raw:")
            assignment = _map_trajectory(
                trajectory=trajectory,
                qualified_report=joint_result.qualified_report,
                raw_artifact_hash=raw_hash,
                omega_context_id=omega_contexts[package.task_package_id],
                cell=cell,
                aliases=aliases,
                semantic_policy=semantic_policy,
                mapper_contract=mapper_contract,
            )
            reference = reference_map_public_trajectory_v2(
                trajectory=trajectory,
                omega_task_context_id=omega_contexts[package.task_package_id],
                runtime_operation_aliases=aliases,
                semantic_policy=semantic_policy,
            )
            if reference.structural_state != assignment.structural_state:
                raise ValueError("v26.160 production and Reference Mapper disagree")
            mapped.append(assignment)
            trajectories.append(trajectory)
            reference_state_ids.append(reference.structural_state.state_id)
            frequency.append(
                make_reachability_frequency_assignment_v2(
                    experiment_id=runner.execution_run_id,
                    job_id=job.job_id,
                    cell=cell,
                    mapping_assignment=assignment,
                    measurement_gate=passing_gate,
                )
            )
    try:
        wrong_reference = reference_map_public_trajectory_v2(
            trajectory=trajectories[0],
            omega_task_context_id="intentional-mismatch-omega",
            runtime_operation_aliases={},
            semantic_policy=semantic_policy,
        )
        if wrong_reference.structural_state == mapped[0].structural_state:
            raise AssertionError("intentional Reference Mapper mismatch was not observable")
        raise ValueError("intentional production/reference State mismatch")
    except ValueError:
        mismatch_rejected = 1
    values = {
        "mapper_protocol_id": manifest.mapper_protocol_id,
        "runner_contract_id": runner.contract_id,
        "intentional_mismatch_rejection_count": mismatch_rejected,
        "fixture_hash": hashlib.sha256(
            base._canonical_bytes(
                {
                    "assignment_ids": sorted(item.assignment_id for item in mapped),
                    "reference_state_ids": sorted(reference_state_ids),
                    "frequency_assignment_ids": sorted(item.assignment_id for item in frequency),
                }
            )
        ).hexdigest(),
    }
    audit = cast(
        IndependentMapperPreflightAudit,
        base._model(
            IndependentMapperPreflightAudit,
            values,
            field="audit_id",
            prefix="finance_v26_frequency_independent_mapper_preflight:",
        ),
    )
    return MapperFixtureProducts(
        audit=audit,
        frequency_assignments=tuple(frequency),
        mapping_assignments=tuple(mapped),
        trajectories=tuple(trajectories),
        passing_gate=passing_gate,
    )


def _synthetic_report(
    *,
    trajectory_id: str,
    verifier_contract_id: str,
) -> QualifiedTrajectoryValidityReport:
    values: dict[str, Any] = {
        "verifier_contract_id": verifier_contract_id,
        "trajectory_id": trajectory_id,
        "eligibility_id": f"{trajectory_id}:eligibility",
        "base_report_id": f"{trajectory_id}:base",
        "mechanism_report_id": f"{trajectory_id}:mechanism",
        "valid": True,
        "state_mapping_eligible": True,
    }
    provisional = QualifiedTrajectoryValidityReport.model_construct(report_id="pending", **values)
    return QualifiedTrajectoryValidityReport(
        report_id=canonical_hash(
            provisional.model_dump(mode="json", exclude={"report_id"}),
            prefix="prospective_qualified_trajectory_validity_report:",
        ),
        **values,
    )


def _synthetic_action(
    semantic_policy: EmpiricalStateSemanticPolicyV2,
    *,
    index: int,
    subject: str,
    failed: bool = False,
) -> PublicTrajectoryActionV2:
    observation_result: Mapping[str, Any] = (
        {"retry_contract": "refine"} if failed else {"evidence_ids": [], "facts": []}
    )
    return make_public_trajectory_action_v2(
        action_index=index,
        decision_kind="acquire_public_input",
        action_kind="call_tool",
        tool_id="query_structured_fact",
        arguments={"subject_alias": subject},
        observation_status="failed" if failed else "succeeded",
        error_code="typed_selector_requires_refinement" if failed else None,
        observation_result=observation_result,
        reference_policy=semantic_policy.typed_reference_policy,
    )


def _synthetic_trajectory(
    *,
    trajectory_id: str,
    actions: Sequence[PublicTrajectoryActionV2],
    canonical_result: Mapping[str, Any],
    semantic_policy: EmpiricalStateSemanticPolicyV2,
) -> PublicTrajectoryProjectionV2:
    return make_public_trajectory_projection_v2(
        trajectory_id=trajectory_id,
        terminal_disposition="completed_model_endpoint",
        actions=actions,
        raw_final_result={"value": "1"},
        canonical_result=dict(canonical_result),
        answer_semantic_schema_id="finance_v26_frequency_contrast_fixture.v1",
        reference_projection_policy_id=semantic_policy.reference_projection_policy_id,
        final_citations=(),
    )


def make_within_cell_contrast_audit(
    *,
    fixture_cell: TaskConditionCellV2,
    omega_context_id: str,
    semantic_policy: EmpiricalStateSemanticPolicyV2,
    mapper_contract: ValidOnlyStateMapperContractV2,
    mapper_protocol_id: str,
) -> WithinCellContrastAudit:
    base_action = _synthetic_action(semantic_policy, index=0, subject="base")
    action_variant = _synthetic_action(semantic_policy, index=0, subject="variant")
    failed = _synthetic_action(semantic_policy, index=0, subject="base", failed=True)
    success_after_failure = _synthetic_action(semantic_policy, index=1, subject="base")
    trajectories = (
        _synthetic_trajectory(
            trajectory_id="v26.160-contrast-base",
            actions=(base_action,),
            canonical_result={"value": "1"},
            semantic_policy=semantic_policy,
        ),
        _synthetic_trajectory(
            trajectory_id="v26.160-contrast-action",
            actions=(action_variant,),
            canonical_result={"value": "1"},
            semantic_policy=semantic_policy,
        ),
        _synthetic_trajectory(
            trajectory_id="v26.160-contrast-result",
            actions=(base_action,),
            canonical_result={"value": "2"},
            semantic_policy=semantic_policy,
        ),
        _synthetic_trajectory(
            trajectory_id="v26.160-contrast-failure-temporal",
            actions=(failed, success_after_failure),
            canonical_result={"value": "1"},
            semantic_policy=semantic_policy,
        ),
    )
    states: list[EmpiricalStructuralStateV2] = []
    for trajectory in trajectories:
        report = _synthetic_report(
            trajectory_id=trajectory.trajectory_id,
            verifier_contract_id=mapper_contract.qualified_verifier_contract_id,
        )
        raw_hash = strict_canonical_hash(trajectory, prefix="v26.160-contrast-raw:")
        assignment = _map_trajectory(
            trajectory=trajectory,
            qualified_report=report,
            raw_artifact_hash=raw_hash,
            omega_context_id=omega_context_id,
            cell=fixture_cell,
            aliases={},
            semantic_policy=semantic_policy,
            mapper_contract=mapper_contract,
        )
        reference = reference_map_public_trajectory_v2(
            trajectory=trajectory,
            omega_task_context_id=omega_context_id,
            runtime_operation_aliases={},
            semantic_policy=semantic_policy,
        )
        if reference.structural_state != assignment.structural_state:
            raise ValueError("v26.160 contrast fixture Reference Mapper mismatch")
        states.append(assignment.structural_state)
    contrasts = tuple(
        make_state_contrast_v2(left, right) for left, right in itertools.combinations(states, 2)
    )
    action_only = sum(
        item.differing_dimensions == ("action_multiplicity_or_payload",) for item in contrasts
    )
    result_only = sum(item.differing_dimensions == ("canonical_result",) for item in contrasts)
    failure_temporal = sum(
        "failure_pattern" in item.differing_dimensions
        or "temporal_relation" in item.differing_dimensions
        for item in contrasts
    )
    if action_only < 1 or result_only < 1 or failure_temporal < 1:
        raise ValueError("v26.160 contrast categories are incomplete")
    pair_count = len(contrasts)
    values = {
        "mapper_protocol_id": mapper_protocol_id,
        "fixture_task_package_id": fixture_cell.task_package_id,
        "fixture_task_condition_cell_id": fixture_cell.cell_id,
        "fixture_state_count": len(states),
        "within_task_state_pair_count": pair_count,
        "within_task_state_contrast_count": pair_count,
        "within_task_condition_state_pair_count": pair_count,
        "within_task_condition_state_contrast_count": pair_count,
        "action_only_pair_count": action_only,
        "result_only_pair_count": result_only,
        "failure_or_temporal_pair_count": failure_temporal,
    }
    return cast(
        WithinCellContrastAudit,
        base._model(
            WithinCellContrastAudit,
            values,
            field="audit_id",
            prefix="finance_v26_frequency_within_cell_contrast:",
        ),
    )


def make_frequency_api_fixture(
    *,
    runner: FrequencyRunnerContract,
    cells: TaskConditionCellCatalogV2,
    mapper_products: MapperFixtureProducts,
) -> FrequencyApiFixtureAudit:
    passing = summarize_reachability_frequency_v2(
        experiment_id=runner.execution_run_id,
        measurement_gate=mapper_products.passing_gate,
        cell_catalog=cells,
        assignments=mapper_products.frequency_assignments,
    )
    if passing.null_report_count != 0:
        raise ValueError("v26.160 complete fixture unexpectedly has a null cell")
    missing_assignments = mapper_products.frequency_assignments[1:]
    missing = summarize_reachability_frequency_v2(
        experiment_id=runner.execution_run_id,
        measurement_gate=mapper_products.passing_gate,
        cell_catalog=cells,
        assignments=missing_assignments,
    )
    missing_null = sum(item.null_reason == "no_qualified_rows" for item in missing.reports)
    failed_gate = make_frequency_measurement_gate_v2(
        exact_job_denominator=base.CELL_COUNT,
        complete_raw_count=base.CELL_COUNT,
        model_endpoint_count=base.CELL_COUNT - 1,
        validity_evaluable_count=base.CELL_COUNT - 1,
        measurement_support_exit_count=1,
    )
    failed = summarize_reachability_frequency_v2(
        experiment_id=runner.execution_run_id,
        measurement_gate=failed_gate,
        cell_catalog=cells,
        assignments=(),
    )
    first = mapper_products.frequency_assignments[0]
    try:
        summarize_reachability_frequency_v2(
            experiment_id=runner.execution_run_id,
            measurement_gate=mapper_products.passing_gate,
            cell_catalog=cells,
            assignments=(first.model_copy(update={"task_package_id": "crossed-task"}),),
        )
    except ValueError:
        strong_key_rejected = 1
    else:
        raise ValueError("v26.160 crossed TaskCondition key was accepted")
    unconditional = next(
        item
        for item in cells.cells
        if item.task_package_id == first.task_package_id
        and item.experimental_condition.sampling_mode == "reachability_unconditional"
    )
    conditioned = next(
        item
        for item in mapper_products.frequency_assignments
        if item.task_package_id == first.task_package_id
        and item.mapping_assignment.experimental_condition.sampling_mode
        == "reachability_conditioned"
    )
    try:
        summarize_reachability_frequency_v2(
            experiment_id=runner.execution_run_id,
            measurement_gate=mapper_products.passing_gate,
            cell_catalog=cells,
            assignments=(
                conditioned.model_copy(update={"task_condition_cell_id": unconditional.cell_id}),
            ),
        )
    except ValueError:
        conditioned_rejected = 1
    else:
        raise ValueError("v26.160 Conditioned row entered an Unconditional cell")
    try:
        TaskConditionCellV2.model_validate(
            {
                **unconditional.model_dump(mode="python"),
                "empirical_route_signature_id": "forbidden-route-condition",
            }
        )
    except ValueError:
        route_rejected = 1
    else:
        raise ValueError("v26.160 empirical Route entered TaskConditionCell")
    values = {
        "task_condition_cell_catalog_id": cells.catalog_id,
        "strong_key_rejection_count": strong_key_rejected,
        "conditioned_into_unconditional_rejection_count": conditioned_rejected,
        "route_as_condition_rejection_count": route_rejected,
        "failed_gate_all_report_null_count": failed.null_report_count,
        "missing_qualified_cell_null_count": missing_null,
    }
    return cast(
        FrequencyApiFixtureAudit,
        base._model(
            FrequencyApiFixtureAudit,
            values,
            field="audit_id",
            prefix="finance_v26_frequency_api_fixture:",
        ),
    )
