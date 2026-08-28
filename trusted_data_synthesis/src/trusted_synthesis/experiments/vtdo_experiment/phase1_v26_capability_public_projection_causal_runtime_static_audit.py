from __future__ import annotations

import copy
import re
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from typing import Any, cast

from pydantic import BaseModel

from trusted_synthesis.core.operations.program import ProgramVerification
from trusted_synthesis.core.task.capability_observation import CapabilityFamily
from trusted_synthesis.core.task.causal_capability_depth import (
    PUBLIC_ACTION_ID_LENGTH,
    CausalCapabilityDepthRuntime,
    CausalCounterfactualKind,
    CausalDepthVerifierContract,
    CausalDepthWitness,
    CausalDepthWitnessContract,
    CausalFinanceBinding,
    CausalFinanceSnapshot,
    CausalMechanismValidityReport,
    CausalQualifiedValidityReport,
    CausalRuntimeObservation,
    CausalTaskValidityReport,
    CausalTerminalKind,
    DepthPromptProjectionContract,
    FinanceEffect,
    FinanceEffectKind,
    HostExecutableDepthGraph,
    apply_effects,
    event_multiplicities,
    initial_snapshot,
    scan_public_leakage,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_capability_public_projection_causal_runtime_models as models,
)
from trusted_synthesis.hashing import canonical_hash


def _make_model(
    model_type: type[BaseModel],
    values: dict[str, Any],
    *,
    field: str,
    prefix: str,
) -> Any:
    provisional = model_type.model_construct(**{field: "pending"}, **values)
    return model_type(**{field: models.identity(provisional, field, prefix)}, **values)


def _trace_hash(observations: tuple[CausalRuntimeObservation, ...]) -> str:
    return canonical_hash(
        tuple(item.observation_id for item in observations),
        prefix="causal_depth_trace:",
    )


def _ordered_event_check(
    observations: tuple[CausalRuntimeObservation, ...],
    earlier: str,
    later: str,
) -> bool:
    earlier_indices = tuple(
        item.call_index for item in observations if earlier in item.emitted_event_types
    )
    later_indices = tuple(
        item.call_index for item in observations if later in item.emitted_event_types
    )
    if not later_indices:
        return True
    return bool(earlier_indices) and max(earlier_indices) < min(later_indices)


def compile_validity_reports(
    *,
    package_id: str,
    graph: HostExecutableDepthGraph,
    binding: CausalFinanceBinding,
    program_verification: ProgramVerification,
    observations: tuple[CausalRuntimeObservation, ...],
    final_snapshot: CausalFinanceSnapshot,
) -> tuple[
    CausalTaskValidityReport,
    CausalMechanismValidityReport,
    CausalQualifiedValidityReport,
]:
    trace_hash = _trace_hash(observations)
    operation_lineage = set(binding.operation_node_ids) <= set(
        final_snapshot.completed_operation_node_ids
    )
    if graph.capability_family == CapabilityFamily.CONTEXT_CONDITIONED_ACTION:
        operand_binding = (
            binding.expected_operator_id is not None
            and final_snapshot.selected_operator_id == binding.expected_operator_id
        )
    elif graph.capability_family == CapabilityFamily.SEMANTIC_RECONCILIATION:
        operand_binding = set(binding.normalization_reference_ids) <= set(
            final_snapshot.consumed_reference_ids
        )
    elif graph.capability_family == CapabilityFamily.FAILURE_RECOVERY:
        operand_binding = bool(final_snapshot.revised_selector_ids)
    else:
        operand_binding = bool(final_snapshot.readiness_check_ids) and final_snapshot.stopped
    task_values = {
        "package_id": package_id,
        "graph_id": graph.graph_id,
        "finance_binding_id": binding.binding_id,
        "trace_hash": trace_hash,
        "task_program_id": binding.task_program_id,
        "task_verifier_binding_id": binding.task_verifier_binding_id,
        "independent_program_replay_passed": program_verification.passed,
        "operation_lineage_complete": operation_lineage,
        "finance_operand_binding_passed": operand_binding,
        "expected_result_match": final_snapshot.result_hash == binding.expected_result_hash,
        "program_closed": final_snapshot.program_closed,
        "terminal_verified": final_snapshot.terminal_verified,
        "postcompletion_control_passed": not final_snapshot.postcompletion_violation,
        "base_valid": all(
            (
                program_verification.passed,
                operation_lineage,
                operand_binding,
                final_snapshot.result_hash == binding.expected_result_hash,
                final_snapshot.program_closed,
                final_snapshot.terminal_verified,
                not final_snapshot.postcompletion_violation,
            )
        ),
    }
    task = cast(
        CausalTaskValidityReport,
        _make_model(
            CausalTaskValidityReport,
            task_values,
            field="report_id",
            prefix="causal_task_validity_report:",
        ),
    )
    observed_events = event_multiplicities(observations)
    state_by_id = {item.state_id: item for item in graph.states}
    preconditions = all(
        observation.after_snapshot_id
        == state_by_id[observation.to_state_id].finance_snapshot.snapshot_id
        for observation in observations
    )
    produced: set[str] = set()
    produced_before_consumed = True
    for observation in observations:
        produced.update(observation.emitted_reference_ids)
        if not set(observation.consumed_reference_ids) <= produced:
            produced_before_consumed = False
    recovery_order = _ordered_event_check(
        observations,
        "typed_failure_observed",
        "recovery_succeeded",
    )
    stop_order = _ordered_event_check(
        observations,
        "terminal_verified",
        "stopped_after_completion",
    )
    mechanism_values = {
        "package_id": package_id,
        "graph_id": graph.graph_id,
        "trace_hash": trace_hash,
        "expected_event_multiplicities": graph.required_event_multiplicities,
        "observed_event_multiplicities": observed_events,
        "reference_preconditions_respected": preconditions,
        "produced_before_consumed": produced_before_consumed,
        "recovery_after_matching_failure": recovery_order,
        "stop_after_verification": stop_order,
        "mechanism_qualified": all(
            (
                graph.required_event_multiplicities == observed_events,
                preconditions,
                produced_before_consumed,
                recovery_order,
                stop_order,
            )
        ),
    }
    mechanism = cast(
        CausalMechanismValidityReport,
        _make_model(
            CausalMechanismValidityReport,
            mechanism_values,
            field="report_id",
            prefix="causal_mechanism_validity_report:",
        ),
    )
    qualified_values = {
        "package_id": package_id,
        "task_report_id": task.report_id,
        "mechanism_report_id": mechanism.report_id,
        "base_valid": task.base_valid,
        "mechanism_qualified": mechanism.mechanism_qualified,
        "qualified_valid": task.base_valid and mechanism.mechanism_qualified,
    }
    qualified = cast(
        CausalQualifiedValidityReport,
        _make_model(
            CausalQualifiedValidityReport,
            qualified_values,
            field="report_id",
            prefix="causal_qualified_validity_report:",
        ),
    )
    return task, mechanism, qualified


def compile_baseline_witness(
    *,
    package_id: str,
    graph: HostExecutableDepthGraph,
    binding: CausalFinanceBinding,
    witness_contract: CausalDepthWitnessContract,
    verifier_contract: CausalDepthVerifierContract,
    program_verification: ProgramVerification,
) -> CausalDepthWitness:
    if (
        witness_contract.graph_id != graph.graph_id
        or witness_contract.finance_binding_id != binding.binding_id
        or witness_contract.required_event_multiplicities != graph.required_event_multiplicities
        or verifier_contract.witness_contract_id != witness_contract.contract_id
        or verifier_contract.finance_binding_id != binding.binding_id
    ):
        raise ValueError("causal Witness compiler received crossed contracts")
    runtime = CausalCapabilityDepthRuntime(graph, binding)
    candidate_by_id = {item.candidate_id: item for item in graph.candidates}
    for candidate_id in graph.reference_path_candidate_ids:
        state = runtime.state
        if state.reference_candidate_id != candidate_id:
            raise ValueError("causal reference policy left the current State")
        runtime.execute(candidate_by_id[candidate_id].public_action_id)
    if runtime.state_id != graph.success_terminal_state_id:
        raise ValueError("causal reference policy did not reach the success terminal")
    observations = tuple(runtime.observations)
    task, mechanism, qualified = compile_validity_reports(
        package_id=package_id,
        graph=graph,
        binding=binding,
        program_verification=program_verification,
        observations=observations,
        final_snapshot=runtime.snapshot,
    )
    if not qualified.qualified_valid:
        raise ValueError("causal baseline failed joint task and mechanism validity")
    values = {
        "package_id": package_id,
        "graph_id": graph.graph_id,
        "witness_contract_id": witness_contract.contract_id,
        "verifier_contract_id": verifier_contract.contract_id,
        "observations": observations,
        "final_state_id": runtime.state_id,
        "final_snapshot_id": runtime.snapshot.snapshot_id,
        "task_validity": task,
        "mechanism_validity": mechanism,
        "qualified_validity": qualified,
    }
    return cast(
        CausalDepthWitness,
        _make_model(
            CausalDepthWitness,
            values,
            field="witness_id",
            prefix="causal_depth_witness:",
        ),
    )


def compute_target_load(
    package_id: str,
    graph: HostExecutableDepthGraph,
    witness: CausalDepthWitness,
) -> models.CausalCompiledTargetLoad:
    candidate_by_id = {item.candidate_id: item for item in graph.candidates}
    transition_by_candidate = {item.candidate_id: item for item in graph.transitions}
    reference_effects = sum(
        len(transition_by_candidate[item].effects) for item in graph.reference_path_candidate_ids
    )
    branch_alternatives = sum(
        max(0, len(state.candidate_ids) - 1)
        for state in graph.states
        if state.terminal_kind == CausalTerminalKind.NONE
    )
    dependency_updates = sum(
        bool(state.public_state.history)
        for state in graph.states
        if state.terminal_kind == CausalTerminalKind.NONE
    )
    target_choices = sum(
        candidate_by_id[item].target_capability_action
        for item in graph.reference_path_candidate_ids
    )
    dimensions = {
        "branch_alternatives": branch_alternatives,
        "causal_nonterminal_states": sum(
            state.terminal_kind == CausalTerminalKind.NONE for state in graph.states
        ),
        "finance_effects_on_reference_path": reference_effects,
        "history_dependent_public_updates": dependency_updates,
        "model_owned_target_choices": target_choices,
        "runtime_reference_calls": len(witness.observations),
    }
    values = {
        "package_id": package_id,
        "graph_id": graph.graph_id,
        "witness_id": witness.witness_id,
        "capability_family": graph.capability_family,
        "depth": graph.depth,
        "dimensions": dimensions,
        "total": sum(dimensions.values()),
    }
    return cast(
        models.CausalCompiledTargetLoad,
        _make_model(
            models.CausalCompiledTargetLoad,
            values,
            field="load_id",
            prefix="compiled_causal_capability_target_load:",
        ),
    )


def _counterfactual_runtime(
    package: models.CausalDepthPackage,
    kind: CausalCounterfactualKind,
) -> tuple[str, tuple[CausalRuntimeObservation, ...], CausalFinanceSnapshot, str]:
    graph = package.graph
    runtime = CausalCapabilityDepthRuntime(graph, package.finance_binding)
    candidate_by_id = {item.candidate_id: item for item in graph.candidates}
    for reference_id in graph.reference_path_candidate_ids:
        state = runtime.state
        alternatives = tuple(
            candidate_by_id[item]
            for item in state.candidate_ids
            if item != reference_id and candidate_by_id[item].target_capability_action
        )
        if alternatives:
            ordered = tuple(sorted(alternatives, key=lambda item: item.semantic_choice_hash))
            selected = (
                ordered[0]
                if kind == CausalCounterfactualKind.REMOVE_TARGET_MECHANISM
                else ordered[-1]
            )
            runtime.execute(selected.public_action_id)
            if runtime.state.terminal_kind == CausalTerminalKind.NONE:
                raise ValueError("causal Counterfactual did not reach a typed terminal")
            return (
                selected.candidate_id,
                tuple(runtime.observations),
                runtime.snapshot,
                runtime.state_id,
            )
        runtime.execute(candidate_by_id[reference_id].public_action_id)
    raise ValueError("causal Counterfactual found no registered target alternative")


def build_counterfactual_catalog(
    packages: Sequence[models.CausalDepthPackage],
    program_verifications: Mapping[str, ProgramVerification],
) -> models.CausalCounterfactualCatalog:
    rows: list[models.CausalCounterfactualReplay] = []
    for package in packages:
        verification = program_verifications[package.finance_core_id]
        for kind in CausalCounterfactualKind:
            candidate_id, observations, snapshot, _ = _counterfactual_runtime(package, kind)
            task, mechanism, qualified = compile_validity_reports(
                package_id=package.package_id,
                graph=package.graph,
                binding=package.finance_binding,
                program_verification=verification,
                observations=observations,
                final_snapshot=snapshot,
            )
            if task.base_valid or mechanism.mechanism_qualified or qualified.qualified_valid:
                raise ValueError("target mechanism Counterfactual retained joint validity")
            values = {
                "package_id": package.package_id,
                "graph_id": package.graph.graph_id,
                "baseline_witness_id": package.baseline_witness.witness_id,
                "counterfactual_kind": kind,
                "intervention_candidate_id": candidate_id,
                "observations": observations,
                "task_validity": task,
                "mechanism_validity": mechanism,
                "qualified_validity": qualified,
                "counterfactual_base_valid": task.base_valid,
                "counterfactual_mechanism_qualified": mechanism.mechanism_qualified,
                "counterfactual_qualified_valid": qualified.qualified_valid,
            }
            rows.append(
                _make_model(
                    models.CausalCounterfactualReplay,
                    values,
                    field="replay_id",
                    prefix="finance_v26_causal_depth_counterfactual_replay:",
                )
            )
    values = {"replays": tuple(sorted(rows, key=lambda item: item.replay_id))}
    return cast(
        models.CausalCounterfactualCatalog,
        _make_model(
            models.CausalCounterfactualCatalog,
            values,
            field="catalog_id",
            prefix="finance_v26_causal_depth_counterfactual_catalog:",
        ),
    )


def build_leakage_audit(
    catalog: models.CausalDevelopmentCatalog,
    contract: DepthPromptProjectionContract,
    policy: models.CandidatePresentationPolicy,
) -> models.PublicProjectionLeakageAudit:
    packages = tuple(package for group in catalog.groups for package in group.packages)
    projections = tuple(
        projection for package in packages for projection in package.prompt_binding.projections
    )
    candidates = tuple(
        option
        for package in packages
        for state in package.graph.states
        for option in state.public_state.options
    )
    findings = tuple(
        finding
        for projection in projections
        for finding in scan_public_leakage(projection.semantic_payload)
    )
    nonopaque = sum(
        re.fullmatch(rf"[0-9a-f]{{{PUBLIC_ACTION_ID_LENGTH}}}", item.action_id) is None
        for item in candidates
    )
    unequal = sum(
        len(
            {
                len(
                    __import__("json")
                    .dumps(
                        item.model_dump(mode="json"),
                        ensure_ascii=False,
                        sort_keys=True,
                        separators=(",", ":"),
                    )
                    .encode("utf-8")
                )
                for item in state.public_state.options
            }
        )
        > 1
        for package in packages
        for state in package.graph.states
        if state.terminal_kind == CausalTerminalKind.NONE
    )
    position_cells: dict[tuple[str, str, str, int], Counter[int]] = defaultdict(Counter)
    id_free_failures = 0
    for package in packages:
        candidate_by_id = {item.candidate_id: item for item in package.graph.candidates}
        for state in package.graph.states:
            if state.terminal_kind != CausalTerminalKind.NONE:
                continue
            reference = candidate_by_id[cast(str, state.reference_candidate_id)]
            option = next(
                item
                for item in state.public_state.options
                if item.action_id == reference.public_action_id
            )
            cell = (
                package.capability_family.value,
                package.depth.value,
                state.host_phase,
                len(state.public_state.options),
            )
            position_cells[cell][option.presentation_index] += 1
            semantic_hashes = {
                candidate_by_id[item].semantic_choice_hash for item in state.candidate_ids
            }
            if (
                len(semantic_hashes) != len(state.candidate_ids)
                or reference.public_action_id in reference.semantic_choice_hash
            ):
                id_free_failures += 1
    unbalanced = 0
    for (*_, option_count), counts in position_cells.items():
        position_values = tuple(counts.get(index, 0) for index in range(option_count))
        if max(position_values) - min(position_values) > 1:
            unbalanced += 1
    values = {
        "projection_contract_id": contract.contract_id,
        "presentation_policy_id": policy.policy_id,
        "prompt_projection_count": len(projections),
        "public_candidate_count": len(candidates),
        "recursive_host_key_leak_count": sum("host_only_key" in item for item in findings),
        "recursive_answer_cue_count": sum("forbidden_scalar" in item for item in findings),
        "nonopaque_action_id_count": nonopaque,
        "unequal_candidate_encoding_state_count": unequal,
        "unbalanced_reference_position_cell_count": unbalanced,
        "id_free_semantic_choice_failure_count": id_free_failures,
    }
    if any(
        values[key]
        for key in (
            "recursive_host_key_leak_count",
            "recursive_answer_cue_count",
            "nonopaque_action_id_count",
            "unequal_candidate_encoding_state_count",
            "unbalanced_reference_position_cell_count",
            "id_free_semantic_choice_failure_count",
        )
    ):
        raise ValueError(f"causal Public Projection audit failed:{values}")
    return cast(
        models.PublicProjectionLeakageAudit,
        _make_model(
            models.PublicProjectionLeakageAudit,
            values,
            field="audit_id",
            prefix="finance_v26_public_projection_leakage_audit:",
        ),
    )


def build_runtime_audit(
    catalog: models.CausalDevelopmentCatalog,
) -> models.CausalRuntimeAudit:
    packages = tuple(package for group in catalog.groups for package in group.packages)
    nonterminal = tuple(
        state
        for package in packages
        for state in package.graph.states
        if state.terminal_kind == CausalTerminalKind.NONE
    )
    divergent = 0
    for package in packages:
        transition_by_candidate = {item.candidate_id: item for item in package.graph.transitions}
        for state in package.graph.states:
            if (
                state.terminal_kind == CausalTerminalKind.NONE
                and len({transition_by_candidate[item].to_state_id for item in state.candidate_ids})
                >= 2
            ):
                divergent += 1
    family_packages = {
        family: tuple(item for item in packages if item.capability_family == family)
        for family in CapabilityFamily
    }
    context_pass = sum(
        next(
            transition.to_state_id
            for transition in package.graph.transitions
            if transition.candidate_id == package.graph.reference_path_candidate_ids[0]
        )
        != next(
            transition.to_state_id
            for transition in package.graph.transitions
            if transition.from_state_id == package.graph.initial_state_id
            and transition.candidate_id != package.graph.reference_path_candidate_ids[0]
        )
        for package in family_packages[CapabilityFamily.CONTEXT_CONDITIONED_ACTION]
    )
    reconciliation_rejections = 0
    for package in family_packages[CapabilityFamily.SEMANTIC_RECONCILIATION]:
        try:
            apply_effects(
                initial_snapshot(),
                (
                    FinanceEffect(
                        kind=FinanceEffectKind.CONSUME_REFERENCE,
                        value=package.finance_binding.normalization_reference_ids[0],
                    ),
                ),
                package.finance_binding,
            )
        except ValueError:
            reconciliation_rejections += 1
    recovery_rejections = 0
    for package in family_packages[CapabilityFamily.FAILURE_RECOVERY]:
        try:
            apply_effects(
                initial_snapshot(),
                (
                    FinanceEffect(
                        kind=FinanceEffectKind.REVISE_SELECTOR,
                        value=package.finance_binding.selector_ids[0],
                    ),
                ),
                package.finance_binding,
            )
        except ValueError:
            recovery_rejections += 1
    stopping_rejections = 0
    postcompletion_terminals = 0
    for package in family_packages[CapabilityFamily.STATE_DEPENDENT_STOPPING]:
        try:
            apply_effects(
                initial_snapshot(),
                (FinanceEffect(kind=FinanceEffectKind.STOP),),
                package.finance_binding,
            )
        except ValueError:
            stopping_rejections += 1
        if any(
            state.terminal_kind == CausalTerminalKind.POSTCOMPLETION_VIOLATION
            for state in package.graph.states
        ):
            postcompletion_terminals += 1
    values = {
        "baseline_task_valid_count": sum(
            item.baseline_witness.task_validity.base_valid for item in packages
        ),
        "baseline_mechanism_qualified_count": sum(
            item.baseline_witness.mechanism_validity.mechanism_qualified for item in packages
        ),
        "baseline_qualified_valid_count": sum(
            item.baseline_witness.qualified_validity.qualified_valid for item in packages
        ),
        "nonterminal_state_count": len(nonterminal),
        "branch_divergent_state_count": divergent,
        "finance_program_coupled_package_count": sum(
            item.graph.finance_binding_id == item.finance_binding.binding_id
            and item.baseline_witness.task_validity.operation_lineage_complete
            for item in packages
        ),
        "context_dependent_candidate_set_pass_count": context_pass,
        "reconciliation_unproduced_consumption_rejection_count": reconciliation_rejections,
        "recovery_without_failure_rejection_count": recovery_rejections,
        "stopping_before_verification_rejection_count": stopping_rejections,
        "postcompletion_violation_terminal_count": postcompletion_terminals,
    }
    return cast(
        models.CausalRuntimeAudit,
        _make_model(
            models.CausalRuntimeAudit,
            values,
            field="audit_id",
            prefix="finance_v26_causal_runtime_audit:",
        ),
    )


def _raw_identity(payload: dict[str, Any], field: str, prefix: str) -> str:
    return canonical_hash(
        {key: value for key, value in payload.items() if key != field},
        prefix=prefix,
    )


def _rehash_package_lineage(
    catalog_payload: dict[str, Any],
    group_index: int,
    package_index: int,
) -> None:
    package = catalog_payload["groups"][group_index]["packages"][package_index]
    package["artifact_id"] = _raw_identity(
        package,
        "artifact_id",
        "finance_v26_causal_depth_package_artifact:",
    )
    group = catalog_payload["groups"][group_index]
    group["group_id"] = _raw_identity(
        group,
        "group_id",
        "finance_v26_causal_depth_group:",
    )
    catalog_payload["catalog_id"] = _raw_identity(
        catalog_payload,
        "catalog_id",
        "finance_v26_causal_development_catalog:",
    )


def build_parent_binding_audit(
    catalog: models.CausalDevelopmentCatalog,
) -> models.ParentBindingAudit:
    base = catalog.model_dump(mode="json")
    all_packages = tuple(package for group in catalog.groups for package in group.packages)
    mutation_kinds = tuple(range(10))
    rejected = 0
    for group_index, group in enumerate(catalog.groups):
        for package_index, source_package in enumerate(group.packages):
            other = next(
                item
                for item in all_packages
                if item.finance_core_id != source_package.finance_core_id
            )
            other_family = next(
                item
                for item in all_packages
                if item.capability_family != source_package.capability_family
            )
            other_depth = next(item for item in all_packages if item.depth != source_package.depth)
            for mutation_kind in mutation_kinds:
                payload = copy.deepcopy(base)
                package = payload["groups"][group_index]["packages"][package_index]
                signature = package["signature"]
                if mutation_kind == 0:
                    child = package["finance_binding"]
                    child["finance_core_id"] = other.finance_core_id
                    child["binding_id"] = _raw_identity(
                        child, "binding_id", "causal_finance_program_binding:"
                    )
                    signature["finance_binding_id"] = child["binding_id"]
                elif mutation_kind == 1:
                    child = package["graph"]
                    child["finance_binding_id"] = other.finance_binding.binding_id
                    child["graph_id"] = _raw_identity(child, "graph_id", "host_causal_depth_graph:")
                    signature["graph_id"] = child["graph_id"]
                elif mutation_kind == 2:
                    child = package["witness_contract"]
                    child["capability_family"] = other_family.capability_family.value
                    child["contract_id"] = _raw_identity(
                        child, "contract_id", "causal_depth_witness_contract:"
                    )
                    signature["witness_contract_id"] = child["contract_id"]
                elif mutation_kind == 3:
                    child = package["verifier_contract"]
                    child["finance_binding_id"] = other.finance_binding.binding_id
                    child["contract_id"] = _raw_identity(
                        child, "contract_id", "causal_depth_verifier_contract:"
                    )
                    signature["verifier_contract_id"] = child["contract_id"]
                elif mutation_kind == 4:
                    child = package["baseline_witness"]
                    child["witness_contract_id"] = other.witness_contract.contract_id
                    child["witness_id"] = _raw_identity(
                        child, "witness_id", "causal_depth_witness:"
                    )
                    signature["baseline_witness_id"] = child["witness_id"]
                elif mutation_kind == 5:
                    child = package["target_load"]
                    child["depth"] = other_depth.depth.value
                    child["load_id"] = _raw_identity(
                        child, "load_id", "compiled_causal_capability_target_load:"
                    )
                    signature["target_load_id"] = child["load_id"]
                elif mutation_kind == 6:
                    child = package["nuisance_binding"]
                    child["base_operational_task_package_id"] = (
                        other.finance_binding.base_operational_task_package_id
                    )
                    child["binding_id"] = _raw_identity(
                        child, "binding_id", "causal_depth_nuisance_binding:"
                    )
                    signature["nuisance_binding_id"] = child["binding_id"]
                elif mutation_kind == 7:
                    child = package["prompt_binding"]
                    child["fixed_generation_condition_id"] = "crossed_condition:000"
                    child["binding_id"] = _raw_identity(
                        child, "binding_id", "causal_depth_prompt_binding:"
                    )
                    signature["prompt_binding_id"] = child["binding_id"]
                elif mutation_kind == 8:
                    signature["target_load_id"] = other.target_load.load_id
                else:
                    child = package["prompt_binding"]
                    projection = child["projections"][0]
                    projection["contract_id"] = "crossed_projection_contract:000"
                    projection["projection_id"] = _raw_identity(
                        projection,
                        "projection_id",
                        "causal_depth_public_prompt_projection:",
                    )
                    child["binding_id"] = _raw_identity(
                        child, "binding_id", "causal_depth_prompt_binding:"
                    )
                    signature["prompt_binding_id"] = child["binding_id"]
                signature["signature_id"] = _raw_identity(
                    signature,
                    "signature_id",
                    "causal_depth_package_signature:",
                )
                _rehash_package_lineage(payload, group_index, package_index)
                try:
                    models.CausalDevelopmentCatalog.model_validate(payload)
                except (TypeError, ValueError):
                    rejected += 1
                else:
                    raise ValueError(
                        "recomputed crossed parent escaped validation:"
                        f"{source_package.package_id}:{mutation_kind}"
                    )
    values = {"crossed_parent_rejection_count": rejected}
    return cast(
        models.ParentBindingAudit,
        _make_model(
            models.ParentBindingAudit,
            values,
            field="audit_id",
            prefix="finance_v26_causal_depth_parent_binding_audit:",
        ),
    )


def build_static_audit(
    *,
    catalog: models.CausalDevelopmentCatalog,
    leakage: models.PublicProjectionLeakageAudit,
    runtime: models.CausalRuntimeAudit,
    counterfactuals: models.CausalCounterfactualCatalog,
    parent_binding: models.ParentBindingAudit,
    source_root: models.TransitiveSourceRoot,
    interpretation: models.OperationalWitnessInterpretation,
) -> models.CausalDepthStaticAudit:
    packages = tuple(package for group in catalog.groups for package in group.packages)
    evidence_by_gate: dict[models.StaticGateName, int] = {
        "candidate_encoding_equality": leakage.public_candidate_count,
        "candidate_position_balance": leakage.prompt_projection_count,
        "causal_counterfactual_validity": len(counterfactuals.replays),
        "causal_finance_binding": runtime.finance_program_coupled_package_count,
        "causal_runtime_branching": runtime.branch_divergent_state_count,
        "confirmation_access_zero": 1,
        "context_dependency": runtime.context_dependent_candidate_set_pass_count,
        "development_catalog_closure": len(packages),
        "finance_program_verifier": runtime.baseline_task_valid_count,
        "historical_v168_freeze": 1,
        "host_public_separation": leakage.prompt_projection_count,
        "id_free_semantic_selection": leakage.public_candidate_count,
        "operational_witness_interpretation": interpretation.unique_finance_core_count,
        "parent_binding_fail_closed": parent_binding.crossed_parent_rejection_count,
        "prompt_recursive_leakage_zero": leakage.prompt_projection_count,
        "provider_zero": 1,
        "reconciliation_preconditions": (
            runtime.reconciliation_unproduced_consumption_rejection_count
        ),
        "recovery_preconditions": runtime.recovery_without_failure_rejection_count,
        "source_transitive_closure": source_root.file_count,
        "stopping_preconditions": runtime.stopping_before_verification_rejection_count,
        "target_load_monotonicity": len(catalog.groups),
        "task_level_necessity": counterfactuals.base_invalid_count,
    }
    gates = tuple(
        models.StaticGateResult(gate=cast(Any, name), evidence_count=evidence_by_gate[name])
        for name in sorted(evidence_by_gate)
    )
    values = {"gates": gates}
    return cast(
        models.CausalDepthStaticAudit,
        _make_model(
            models.CausalDepthStaticAudit,
            values,
            field="audit_id",
            prefix="finance_v26_causal_depth_static_audit:",
        ),
    )
