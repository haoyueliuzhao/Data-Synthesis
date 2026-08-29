from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Final

from pydantic import BaseModel

from trusted_synthesis.core.task.all_typed_rejection_public_feedback import (
    HostTypedRejectionBinding,
    PublicCorrectionBoundTerminal,
    PublicTypedRejectionFeedback,
    PublicTypedRejectionObservation,
    make_host_typed_rejection_binding,
    make_public_typed_rejection_feedback,
    make_public_typed_rejection_observation,
    prompt_with_public_typed_rejection_history,
)
from trusted_synthesis.core.task.joint_presentation_receipt_hardening import (
    ActionAcceptanceReport,
    HardenedPublicObservation,
    HardenedPublicPrompt,
)
from trusted_synthesis.core.task.public_semantic_capability_depth import canonical_bytes
from trusted_synthesis.core.task.state_local_presentation_hardening import (
    StateLocalRankSchedule,
    classify_action_acceptance,
    make_state_local_rank_schedule,
    public_only_select_hardened_action,
    topological_components,
)
from trusted_synthesis.core.task.validity_separated_capability_depth import (
    CausalPublicDecisionState,
    CausalTargetComponent,
    choice_entry,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_capability_all_typed_rejection_public_feedback as v177,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_capability_all_typed_rejection_public_feedback_runtime as step_runtime,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_capability_authoritative_parent_rejection_history_models as v176_models,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_capability_executed_counterfactual_outcome_closure_models as models,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_capability_validity_causal_reaudit_models as v171_models,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_capability_validity_causal_runtime as v171_runtime,
)
from trusted_synthesis.hashing import canonical_hash

CANONICAL_CONTROL_SCHEDULE_CONTRACT_ID: Final = canonical_hash(
    {
        "stage": models.AUTHORIZED_STAGE,
        "policy": "diagnostic_controls_are_content_rematerialized_and_model_unexposed",
    },
    prefix="canonical_valid_control_schedule_contract:",
)


def _roundtrip(value: BaseModel) -> BaseModel:
    return type(value).model_validate(value.model_dump(mode="python"))


def _runtime_input(
    source: v171_models.ValiditySeparatedCausalPackage,
    core: Any,
) -> v171_runtime.RuntimeInput:
    return v171_runtime.RuntimeInput(
        package_id=source.package_id,
        capability_family=source.capability_family,
        public_task=source.public_task,
        components=source.components,
        finance_core=core,
    )


def _state_at_component(
    *,
    source: v171_models.ValiditySeparatedCausalPackage,
    core: Any,
    control_package_id: str,
    schedules: Mapping[str, StateLocalRankSchedule],
    component_key: str,
    replica_index: int,
) -> step_runtime.StepRuntimeState:
    state = step_runtime.initialize(
        _runtime_input(source, core),
        package_id=control_package_id,
        replica_index=replica_index,
        schedules_by_component=schedules,
    )
    while state.ordered_components[state.current_index].component_key != component_key:
        prompt = step_runtime.render_next_prompt(state)
        observation = step_runtime.step(state, public_only_select_hardened_action(prompt))
        if (
            not isinstance(observation, HardenedPublicObservation)
            or not observation.action_accepted
        ):
            raise ValueError("canonical control reference prefix did not commit")
    return state


def _candidate_acceptances(
    state: step_runtime.StepRuntimeState,
    prompt: HardenedPublicPrompt,
) -> tuple[tuple[Any, str, ActionAcceptanceReport], ...]:
    mapping = state.pending_source_by_display
    if mapping is None:
        raise ValueError("canonical control lost its display/source mapping")
    component = state.ordered_components[state.current_index]
    rows: list[tuple[Any, str, ActionAcceptanceReport]] = []
    for candidate in prompt.candidates:
        source_handle = mapping[candidate.choice_handle]
        acceptance = classify_action_acceptance(
            package_id=state.package_id,
            task=state.runtime_input.public_task,
            component=component,
            source_choice_handle=source_handle,
            visible_failure_receipt=prompt.state.failure_receipt,
            expected_failure_receipt=state.failure_receipts.get(component.component_key),
        )
        rows.append((candidate, source_handle, acceptance))
    return tuple(rows)


def scan_exact_catalog(
    predecessor: v177.PredecessorObjects,
) -> models.ExactCatalogReachabilityAudit:
    source_by_artifact = {
        item.artifact_id: item for item in v177._v171_packages(predecessor.source)
    }
    core_by_id = {item.core_id: item for item in predecessor.source.finance_cores}
    state_rows: list[models.ExactCatalogStateScanRow] = []
    branch_counts: Counter[tuple[str, str]] = Counter()
    acceptance_count = 0
    rejection_count = 0
    component_ids: set[str] = set()
    for package in v177._development_packages(predecessor.development):
        source = source_by_artifact[package.source_v171_package_artifact_id]
        schedules = v177._schedule_mapping(
            package=package,
            source=source,
            schedule_catalog=predecessor.schedules,
        )
        for component in topological_components(source.components):
            component_ids.add(component.component_id)
            for replica_index in range(6):
                state = v177._state_at_component(
                    package=package,
                    source=source,
                    core=core_by_id[source.finance_core_id],
                    schedules=schedules,
                    component_key=component.component_key,
                    replica_index=replica_index,
                )
                prompt = step_runtime.render_next_prompt(state)
                reports = _candidate_acceptances(state, prompt)
                rejected: list[str] = []
                for _, _, report in reports:
                    if report.accepted:
                        acceptance_count += 1
                    else:
                        rejection_count += 1
                        if report.rejection_code is None:
                            raise ValueError("exact-Catalog rejected Action has no typed code")
                        key = (component.public_state.decision_kind, report.rejection_code)
                        branch_counts[key] += 1
                        rejected.append("|".join(key))
                state_rows.append(
                    models.make_identity_model(
                        models.ExactCatalogStateScanRow,
                        {
                            "package_id": package.package_id,
                            "source_package_artifact_id": source.artifact_id,
                            "component_id": component.component_id,
                            "component_key": component.component_key,
                            "decision_kind": component.public_state.decision_kind,
                            "replica_index": replica_index,
                            "prompt_hash": prompt.prompt_hash,
                            "candidate_count": len(reports),
                            "acceptance_report_ids": tuple(item[2].report_id for item in reports),
                            "rejected_branch_keys": tuple(sorted(rejected)),
                        },
                        field="row_id",
                        prefix="exact_catalog_typed_rejection_state_scan_row:",
                    )
                )
    if len(component_ids) != 80 or len(state_rows) != 480:
        raise ValueError("complete exact-Catalog scan denominator changed")
    reachability = tuple(
        models.make_identity_model(
            models.ExactCatalogReachabilityRow,
            {
                "decision_kind": decision_kind,
                "rejection_code": rejection_code,
                "observed_rejection_count": branch_counts[(decision_kind, rejection_code)],
                "exact_catalog_status": (
                    "reachable"
                    if branch_counts[(decision_kind, rejection_code)]
                    else "registered_but_unreachable_under_valid_public_object_model"
                ),
            },
            field="row_id",
            prefix="exact_catalog_typed_rejection_reachability_row:",
        )
        for decision_kind, rejection_code in models.REGISTERED_REJECTION_BRANCHES
    )
    return models.make_identity_model(
        models.ExactCatalogReachabilityAudit,
        {
            "state_rows": tuple(state_rows),
            "reachability_rows": reachability,
            "candidate_scan_count": acceptance_count + rejection_count,
            "acceptance_count": acceptance_count,
            "rejection_count": rejection_count,
        },
        field="audit_id",
        prefix="finance_v26_exact_catalog_rejection_reachability_audit:",
    )


def _control_operation(
    component: CausalTargetComponent,
    task: Any,
) -> tuple[CausalTargetComponent, str, str]:
    decision = component.public_state.decision_kind
    if decision not in {
        "reconcile_record",
        "consume_normalized_output",
        "assess_dynamic_readiness",
    }:
        raise ValueError(f"unsupported canonical control Decision:{decision}")
    entries = list(component.public_state.choice_legend)
    target_index = next(
        index
        for index, item in enumerate(entries)
        if item.choice_handle != component.reference_choice_handle
    )
    original = entries[target_index]
    arguments = dict(original.operation.arguments)
    if decision == "reconcile_record":
        rules = tuple(item.rule_handle for item in task.semantic_task.resolution_rules)
        operations = tuple(item.operation_handle for item in task.semantic_task.operations)
        replacements = tuple(
            ("rule_handle", item) for item in rules if item != str(arguments.get("rule_handle"))
        ) + tuple(
            ("operation_handle", item)
            for item in operations
            if item != str(arguments.get("operation_handle"))
        )
        if not replacements:
            raise ValueError("canonical Reconciliation control lacks a grounded mismatch")
        field_name, replacement = replacements[0]
        arguments[field_name] = replacement
    elif decision == "consume_normalized_output":
        arguments["input_symbol"] = f"{arguments['input_symbol']}:canonical_control"
    else:
        arguments["assertion"] = f"{arguments['assertion']}:canonical_control"
    operation_payload = original.operation.model_dump(mode="python")
    operation_payload["arguments"] = arguments
    operation = type(original.operation).model_validate(operation_payload)
    if _roundtrip(operation) != operation:
        raise ValueError("canonical control Operation round-trip changed bytes")
    entry = choice_entry(operation)
    if _roundtrip(entry) != entry or entry.choice_handle == original.choice_handle:
        raise ValueError("canonical control Choice identity was not freshly derived")
    entries[target_index] = entry
    state_payload = component.public_state.model_dump(mode="python")
    state_payload["choice_legend"] = tuple(entries)
    public_state = CausalPublicDecisionState.model_validate(state_payload)
    if _roundtrip(public_state) != public_state:
        raise ValueError("canonical control public State round-trip changed bytes")
    component_payload = component.model_dump(mode="python", exclude={"component_id"})
    component_payload["public_state"] = public_state
    changed = models.make_identity_model(
        CausalTargetComponent,
        component_payload,
        field="component_id",
        prefix="causal_public_target_component:",
    )
    if _roundtrip(changed) != changed or changed.component_id == component.component_id:
        raise ValueError("canonical control Component was not content-rematerialized")
    return changed, original.choice_handle, entry.choice_handle


def _rematerialize_source_package(
    *,
    source: v171_models.ValiditySeparatedCausalPackage,
    replacement: CausalTargetComponent,
    core: Any,
) -> v171_models.ValiditySeparatedCausalPackage:
    components = tuple(
        replacement if item.component_key == replacement.component_key else item
        for item in source.components
    )
    presentations: list[v171_models.ReplicaPresentation] = []
    for component in components:
        for replica_index in range(6):
            prompt = v171_runtime.prompt_for_component(
                package_id=source.package_id,
                task=source.public_task,
                component=component,
                replica_index=replica_index,
            )
            presentations.append(
                models.make_identity_model(
                    v171_models.ReplicaPresentation,
                    {
                        "package_id": source.package_id,
                        "component_id": component.component_id,
                        "replica_index": replica_index,
                        "prompt": prompt,
                    },
                    field="presentation_id",
                    prefix="causal_deleaked_replica_presentation:",
                )
            )
    baseline_prompts = tuple(
        next(
            item.prompt
            for item in presentations
            if item.component_id == component.component_id and item.replica_index == 0
        )
        for component in components
    )
    prompt_binding = models.make_identity_model(
        v171_models.CausalPromptBinding,
        {
            "package_id": source.package_id,
            "public_task_id": source.public_task.task_id,
            "component_contract_id": source.component_contract_id,
            "presentation_policy_id": source.presentation_policy_id,
            "baseline_prompts": baseline_prompts,
            "prompt_count": len(baseline_prompts),
            "dynamic_predecessor_receipts_required": any(
                item.dependency_component_keys for item in components
            ),
        },
        field="binding_id",
        prefix="causal_public_prompt_binding:",
    )
    baseline = v171_runtime.execute_runtime(
        v171_runtime.RuntimeInput(
            package_id=source.package_id,
            capability_family=source.capability_family,
            public_task=source.public_task,
            components=components,
            finance_core=core,
        )
    )
    if not baseline.qualified_validity.qualified_valid:
        raise ValueError("canonical control source Package lost its reference baseline")
    values = {
        "package_id": source.package_id,
        "source_v170_package_artifact_id": source.source_v170_package_artifact_id,
        "source_v170_group_id": source.source_v170_group_id,
        "capability_family": source.capability_family,
        "depth": source.depth,
        "finance_core_id": source.finance_core_id,
        "fixed_generation_condition_id": source.fixed_generation_condition_id,
        "validity_contract_id": source.validity_contract_id,
        "component_contract_id": source.component_contract_id,
        "presentation_policy_id": source.presentation_policy_id,
        "parent_binding_contract_id": source.parent_binding_contract_id,
        "public_task": source.public_task,
        "source_parent_binding": source.source_parent_binding,
        "components": components,
        "prompt_binding": prompt_binding,
        "replica_presentations": tuple(presentations),
        "target_load": source.target_load,
        "baseline_execution": baseline,
    }
    package = models.make_identity_model(
        v171_models.ValiditySeparatedCausalPackage,
        values,
        field="artifact_id",
        prefix="finance_v26_validity_causal_package_artifact:",
    )
    roundtrip = v171_models.ValiditySeparatedCausalPackage.model_validate(
        package.model_dump(mode="python")
    )
    if roundtrip != package or package.artifact_id == source.artifact_id:
        raise ValueError("canonical control source Package was not fully rematerialized")
    return package


def _diagnostic_schedules(
    source: v171_models.ValiditySeparatedCausalPackage,
) -> dict[str, StateLocalRankSchedule]:
    output: dict[str, StateLocalRankSchedule] = {}
    for component in topological_components(source.components):
        schedule = make_state_local_rank_schedule(
            schedule_contract_id=CANONICAL_CONTROL_SCHEDULE_CONTRACT_ID,
            source_package_artifact_id=source.artifact_id,
            component=component,
        )
        if _roundtrip(schedule) != schedule:
            raise ValueError("canonical control Schedule round-trip changed bytes")
        output[component.component_key] = schedule
    return output


@dataclass(frozen=True)
class _ControlSpec:
    object: models.CanonicalControlObject
    package: v176_models.AuthoritativeDevelopmentPackage
    source: v171_models.ValiditySeparatedCausalPackage
    core: Any
    schedules: Mapping[str, StateLocalRankSchedule]
    component_key: str
    rejection_code: str


@dataclass(frozen=True)
class HostCounterfactualSeed:
    execution_row: models.ValidControlExecutionRow
    initial_prompt: HardenedPublicPrompt
    recovery_base_prompt: HardenedPublicPrompt
    observation: PublicTypedRejectionObservation
    feedback: PublicTypedRejectionFeedback
    host_binding: HostTypedRejectionBinding
    recovery_prompt: HardenedPublicPrompt
    acceptance: ActionAcceptanceReport
    source_choice_handle: str


@dataclass(frozen=True)
class ValidControlProducts:
    audit: models.ValidControlExecutionAudit
    host_seeds: tuple[HostCounterfactualSeed, ...]


def _control_specs(predecessor: v177.PredecessorObjects) -> tuple[_ControlSpec, ...]:
    source_by_artifact = {
        item.artifact_id: item for item in v177._v171_packages(predecessor.source)
    }
    core_by_id = {item.core_id: item for item in predecessor.source.finance_cores}
    output: list[_ControlSpec] = []
    for registration in v177.PRODUCTION_REJECTION_REGISTRY:
        decision = str(registration["decision_kind"])
        rejection = str(registration["rejection_code"])
        for package in v177._development_packages(predecessor.development):
            original_source = source_by_artifact[package.source_v171_package_artifact_id]
            core = core_by_id[original_source.finance_core_id]
            original_schedules = v177._schedule_mapping(
                package=package,
                source=original_source,
                schedule_catalog=predecessor.schedules,
            )
            for original_component in topological_components(original_source.components):
                if original_component.public_state.decision_kind != decision:
                    continue
                exact = decision == "revise_selector" and rejection == (
                    "typed_current_state_target_mismatch"
                )
                rematerialized = decision in {
                    "reconcile_record",
                    "consume_normalized_output",
                    "assess_dynamic_readiness",
                }
                old_choice = original_component.reference_choice_handle
                new_choice = old_choice
                control_component = original_component
                control_source = original_source
                schedules: Mapping[str, StateLocalRankSchedule] = original_schedules
                if rematerialized:
                    control_component, old_choice, new_choice = _control_operation(
                        original_component,
                        original_source.public_task,
                    )
                    control_source = _rematerialize_source_package(
                        source=original_source,
                        replacement=control_component,
                        core=core,
                    )
                    schedules = _diagnostic_schedules(control_source)
                else:
                    reconstructed_entries = tuple(
                        choice_entry(item.operation)
                        for item in original_component.public_state.choice_legend
                    )
                    if reconstructed_entries != original_component.public_state.choice_legend:
                        raise ValueError("exact control Choice handles do not reconstruct")
                    component_payload = original_component.model_dump(
                        mode="python",
                        exclude={"component_id"},
                    )
                    reconstructed_component = models.make_identity_model(
                        CausalTargetComponent,
                        component_payload,
                        field="component_id",
                        prefix="causal_public_target_component:",
                    )
                    if reconstructed_component != original_component:
                        raise ValueError("exact control Component identity does not reconstruct")
                    if _roundtrip(original_source) != original_source:
                        raise ValueError("exact control source Package does not round-trip")
                control_package_id = (
                    package.package_id
                    if exact
                    else canonical_hash(
                        {
                            "base_v176_package_id": package.package_id,
                            "control_source_package_artifact_id": control_source.artifact_id,
                            "component_id": control_component.component_id,
                            "decision_kind": decision,
                            "rejection_code": rejection,
                        },
                        prefix="canonical_valid_typed_rejection_control_package:",
                    )
                )
                control_object = models.make_identity_model(
                    models.CanonicalControlObject,
                    {
                        "control_package_id": control_package_id,
                        "base_v176_package_id": package.package_id,
                        "original_source_package_artifact_id": original_source.artifact_id,
                        "control_source_package_artifact_id": control_source.artifact_id,
                        "component_key": original_component.component_key,
                        "original_component_id": original_component.component_id,
                        "control_component_id": control_component.component_id,
                        "decision_kind": decision,
                        "rejection_code": rejection,
                        "control_origin": ("exact_catalog" if exact else "canonical_diagnostic"),
                        "component_content_rematerialized": rematerialized,
                        "source_package_content_rematerialized": rematerialized,
                    },
                    field="object_id",
                    prefix="canonical_valid_typed_rejection_control_object:",
                )
                if rematerialized and old_choice == new_choice:
                    raise ValueError("canonical diagnostic Choice handle did not change")
                output.append(
                    _ControlSpec(
                        object=control_object,
                        package=package,
                        source=control_source,
                        core=core,
                        schedules=schedules,
                        component_key=original_component.component_key,
                        rejection_code=rejection,
                    )
                )
    if len(output) != 72:
        raise ValueError("canonical control object denominator changed")
    return tuple(output)


@dataclass(frozen=True)
class _PreparedControl:
    state: step_runtime.StepRuntimeState
    recovery_base_prompt: HardenedPublicPrompt
    initial_prompt: HardenedPublicPrompt
    invalid_action_id: str
    source_choice_handle: str
    acceptance: ActionAcceptanceReport


def _prepare_control(spec: _ControlSpec, replica_index: int) -> _PreparedControl:
    state = _state_at_component(
        source=spec.source,
        core=spec.core,
        control_package_id=spec.object.control_package_id,
        schedules=spec.schedules,
        component_key=spec.component_key,
        replica_index=replica_index,
    )
    recovery_base_prompt = step_runtime.render_next_prompt(state)
    initial_prompt = recovery_base_prompt
    if spec.rejection_code == "typed_failure_receipt_mismatch":
        initial_prompt = v177._replace_prompt_failure_receipt(
            recovery_base_prompt,
            v177._mismatched_failure_receipt(recovery_base_prompt),
        )
        state.pending_prompt = initial_prompt
    reports = _candidate_acceptances(state, initial_prompt)
    rejected = tuple(item for item in reports if item[2].rejection_code == spec.rejection_code)
    if not rejected:
        raise ValueError(
            f"canonical valid control branch is unreachable:{spec.object.decision_kind}:"
            f"{spec.rejection_code}"
        )
    if spec.rejection_code == "typed_failure_receipt_mismatch":
        reference_action = public_only_select_hardened_action(recovery_base_prompt)
        selected = next(item for item in rejected if item[0].action_id == reference_action)
    else:
        selected = rejected[0]
    if not selected[2].publicly_grounded or not selected[2].publicly_executable:
        raise ValueError("canonical control conflates legality with typed precondition")
    return _PreparedControl(
        state=state,
        recovery_base_prompt=recovery_base_prompt,
        initial_prompt=initial_prompt,
        invalid_action_id=selected[0].action_id,
        source_choice_handle=selected[1],
        acceptance=selected[2],
    )


def _execute_initial_control(
    spec: _ControlSpec,
    replica_index: int,
) -> tuple[
    _PreparedControl,
    PublicTypedRejectionObservation,
    PublicTypedRejectionFeedback,
    HostTypedRejectionBinding,
    HardenedPublicPrompt,
]:
    prepared = _prepare_control(spec, replica_index)
    state = prepared.state
    before_retry = v177._retry_count(state.events)
    before_tools = state.local_tool_invocation_count
    before_index = state.current_index
    observation = step_runtime.step(state, prepared.invalid_action_id)
    if not isinstance(observation, PublicTypedRejectionObservation):
        raise ValueError("canonical valid control did not emit public typed rejection")
    if (
        v177._retry_count(state.events) != before_retry
        or state.local_tool_invocation_count != before_tools
        or state.current_index != before_index
    ):
        raise ValueError("canonical valid typed rejection committed Runtime behavior")
    feedback = state.public_feedback_by_component[spec.component_key][0]
    host_binding = state.host_rejection_bindings_by_component[spec.component_key][0]
    recovery_prompt = step_runtime.render_next_prompt(state)
    expected_recovery = prompt_with_public_typed_rejection_history(
        prepared.recovery_base_prompt,
        (feedback,),
    )
    if recovery_prompt != expected_recovery:
        raise ValueError("canonical valid control recovery Prompt does not reconstruct")
    if not v177._independent_public_projection_matches(
        observation=observation,
        feedback=feedback,
    ):
        raise ValueError("canonical valid control public preimage does not reconstruct")
    return prepared, observation, feedback, host_binding, recovery_prompt


def execute_valid_controls(
    predecessor: v177.PredecessorObjects,
) -> ValidControlProducts:
    specs = _control_specs(predecessor)
    rows: list[models.ValidControlExecutionRow] = []
    seeds: list[HostCounterfactualSeed] = []
    for spec in specs:
        for replica_index in range(6):
            prepared, observation, feedback, host_binding, recovery_prompt = (
                _execute_initial_control(spec, replica_index)
            )
            state = prepared.state
            before_index = state.current_index
            corrected = step_runtime.step(
                state,
                public_only_select_hardened_action(recovery_prompt),
            )
            if (
                not isinstance(corrected, HardenedPublicObservation)
                or not corrected.action_accepted
                or state.current_index != before_index + 1
            ):
                raise ValueError("canonical valid control reference correction did not commit once")
            repeated, _, _, _, _ = _execute_initial_control(spec, replica_index)
            repeated_prompt = step_runtime.render_next_prompt(repeated.state)
            if spec.rejection_code == "typed_failure_receipt_mismatch":
                repeated.state.pending_prompt = v177._replace_prompt_failure_receipt(
                    repeated_prompt,
                    v177._mismatched_failure_receipt(repeated_prompt),
                )
            terminal = step_runtime.step(repeated.state, repeated.invalid_action_id)
            if not isinstance(terminal, PublicCorrectionBoundTerminal):
                raise ValueError("canonical valid control repeated invalid did not terminalize")
            try:
                step_runtime.render_next_prompt(repeated.state)
            except step_runtime.CorrectionBoundTerminalReached:
                later_prompt_count = 0
            else:
                later_prompt_count = 1
            if later_prompt_count:
                raise ValueError("canonical valid control terminal exposed a third Prompt")
            row = models.make_identity_model(
                models.ValidControlExecutionRow,
                {
                    "control_object_id": spec.object.object_id,
                    "package_id": spec.object.control_package_id,
                    "component_key": spec.component_key,
                    "decision_kind": spec.object.decision_kind,
                    "rejection_code": spec.rejection_code,
                    "replica_index": replica_index,
                    "control_origin": spec.object.control_origin,
                    "initial_prompt_hash": prepared.initial_prompt.prompt_hash,
                    "public_observation_receipt_id": observation.public_observation_receipt_id,
                    "public_feedback_id": feedback.feedback_id,
                    "host_binding_id": host_binding.binding_id,
                    "recovery_prompt_hash": recovery_prompt.prompt_hash,
                },
                field="row_id",
                prefix="canonical_valid_typed_rejection_control_execution_row:",
            )
            rows.append(row)
            seeds.append(
                HostCounterfactualSeed(
                    execution_row=row,
                    initial_prompt=prepared.initial_prompt,
                    recovery_base_prompt=prepared.recovery_base_prompt,
                    observation=observation,
                    feedback=feedback,
                    host_binding=host_binding,
                    recovery_prompt=recovery_prompt,
                    acceptance=prepared.acceptance,
                    source_choice_handle=prepared.source_choice_handle,
                )
            )
    audit = models.make_identity_model(
        models.ValidControlExecutionAudit,
        {
            "control_objects": tuple(item.object for item in specs),
            "rows": tuple(rows),
        },
        field="audit_id",
        prefix="finance_v26_canonical_valid_rejection_control_execution_audit:",
    )
    return ValidControlProducts(audit=audit, host_seeds=tuple(seeds))


def _changed_acceptance(
    acceptance: ActionAcceptanceReport,
    updates: Mapping[str, Any],
) -> ActionAcceptanceReport:
    values = acceptance.model_dump(mode="python", exclude={"report_id"})
    values.update(updates)
    return models.make_identity_model(
        ActionAcceptanceReport,
        values,
        field="report_id",
        prefix="state_bound_action_acceptance_report:",
    )


def _host_counterfactual(
    seed: HostCounterfactualSeed,
    intervention: str,
) -> HostTypedRejectionBinding:
    baseline = seed.host_binding
    package_id = baseline.package_id
    component_key = baseline.component_key
    source_choice_handle = baseline.source_choice_handle
    acceptance = seed.acceptance
    runtime_event_ids = baseline.runtime_event_ids
    suffix = canonical_hash(
        {
            "control_execution_row_id": seed.execution_row.row_id,
            "intervention": intervention,
        },
        prefix="host_counterfactual_value:",
    )
    if intervention in {"package_id", "joint_all_host_parents"}:
        package_id = f"{package_id}:counterfactual:{suffix}"
    if intervention in {"component_key", "joint_all_host_parents"}:
        component_key = f"{component_key}:counterfactual:{suffix}"
    if intervention in {"source_choice_handle", "joint_all_host_parents"}:
        source_choice_handle = f"{source_choice_handle}:counterfactual:{suffix}"
    acceptance_updates: dict[str, Any] = {}
    if package_id != baseline.package_id:
        acceptance_updates["package_id"] = package_id
    if component_key != baseline.component_key:
        acceptance_updates["component_key"] = component_key
    if source_choice_handle != baseline.source_choice_handle:
        acceptance_updates["source_choice_handle"] = source_choice_handle
    if intervention in {"selected_operation_hash", "joint_all_host_parents"}:
        acceptance_updates["selected_operation_hash"] = canonical_hash(
            {"baseline": acceptance.selected_operation_hash, "nonce": suffix},
            prefix="counterfactual_selected_runtime_operation:",
        )
    if intervention in {"action_acceptance_report", "joint_all_host_parents"}:
        acceptance_updates["findings"] = tuple(
            sorted({*acceptance.findings, f"host_counterfactual:{suffix}"})
        )
    if acceptance_updates:
        acceptance = _changed_acceptance(acceptance, acceptance_updates)
    if intervention in {"runtime_event_identities", "joint_all_host_parents"}:
        runtime_event_ids = tuple(
            canonical_hash(
                {"baseline_event_id": item, "nonce": suffix},
                prefix="counterfactual_runtime_event:",
            )
            for item in runtime_event_ids
        )
    observation = make_public_typed_rejection_observation(
        prompt=seed.initial_prompt,
        public_rejected_action_id=seed.observation.public_rejected_action_id,
        public_displayed_choice_handle=seed.observation.public_displayed_choice_handle,
        public_rejection_code=seed.observation.public_rejection_code,
        correction_attempt_index=seed.observation.correction_attempt_index,
    )
    feedback = make_public_typed_rejection_feedback(
        observation=observation,
        predecessor_public_feedback_id=seed.feedback.predecessor_public_feedback_id,
    )
    if observation != seed.observation or feedback != seed.feedback:
        raise ValueError("Host counterfactual changed its fixed public inputs")
    return make_host_typed_rejection_binding(
        package_id=package_id,
        component_key=component_key,
        source_choice_handle=source_choice_handle,
        acceptance=acceptance,
        runtime_event_ids=runtime_event_ids,
        observation=observation,
        feedback=feedback,
    )


def execute_host_counterfactuals(
    seeds: Sequence[HostCounterfactualSeed],
) -> models.ExecutedHostCounterfactualAudit:
    if len(seeds) != 432:
        raise ValueError("Host counterfactual base-control denominator changed")
    rows: list[models.HostCounterfactualInterventionRow] = []
    for seed in seeds:
        baseline_observation_bytes = canonical_bytes(seed.observation.model_dump(mode="json"))
        baseline_feedback_bytes = canonical_bytes(seed.feedback.model_dump(mode="json"))
        baseline_binding_bytes = canonical_bytes(seed.host_binding.model_dump(mode="json"))
        baseline_prompt_bytes = canonical_bytes(seed.recovery_prompt.model_dump(mode="json"))
        for intervention in models.HOST_COUNTERFACTUAL_INTERVENTIONS:
            counterfactual = _host_counterfactual(seed, intervention)
            counterfactual_prompt = prompt_with_public_typed_rejection_history(
                seed.recovery_base_prompt,
                (seed.feedback,),
            )
            observation_bytes = canonical_bytes(seed.observation.model_dump(mode="json"))
            feedback_bytes = canonical_bytes(seed.feedback.model_dump(mode="json"))
            binding_bytes = canonical_bytes(counterfactual.model_dump(mode="json"))
            prompt_bytes = canonical_bytes(counterfactual_prompt.model_dump(mode="json"))
            if (
                counterfactual.binding_id == seed.host_binding.binding_id
                or binding_bytes == baseline_binding_bytes
                or observation_bytes != baseline_observation_bytes
                or feedback_bytes != baseline_feedback_bytes
                or prompt_bytes != baseline_prompt_bytes
                or counterfactual_prompt.prompt_hash != seed.recovery_prompt.prompt_hash
            ):
                raise ValueError(f"Host counterfactual invariance failed:{intervention}")
            rows.append(
                models.make_identity_model(
                    models.HostCounterfactualInterventionRow,
                    {
                        "control_execution_row_id": seed.execution_row.row_id,
                        "intervention_kind": intervention,
                        "baseline_host_binding_id": seed.host_binding.binding_id,
                        "counterfactual_host_binding_id": counterfactual.binding_id,
                    },
                    field="row_id",
                    prefix="executed_host_counterfactual_intervention_row:",
                )
            )
    return models.make_identity_model(
        models.ExecutedHostCounterfactualAudit,
        {"rows": tuple(rows)},
        field="audit_id",
        prefix="finance_v26_executed_host_counterfactual_invariance_audit:",
    )


__all__ = [
    "HostCounterfactualSeed",
    "ValidControlProducts",
    "execute_host_counterfactuals",
    "execute_valid_controls",
    "scan_exact_catalog",
]
