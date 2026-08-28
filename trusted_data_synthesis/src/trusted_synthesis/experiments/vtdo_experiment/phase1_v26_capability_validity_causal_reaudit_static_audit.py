from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Mapping
from typing import Any, cast

from pydantic import ValidationError

from trusted_synthesis.core.task.capability_observation import CapabilityFamily
from trusted_synthesis.core.task.public_semantic_capability_depth import (
    default_semantic_runtime_binding,
    execute_semantic_runtime,
    public_record_from_evidence,
)
from trusted_synthesis.core.task.validity_separated_capability_depth import (
    COMPONENT_DECISION_CONTRACT,
    CausalPublicDecisionState,
    CausalPublicPrompt,
    CausalTargetComponent,
    PresentedChoiceCandidate,
    PublicChoiceLegendEntry,
    StaticQualifiedValidityReport,
    candidate_legality_findings,
    canonical_bytes,
    make_prompt,
    public_only_select_action,
    public_prompt_shortcut_findings,
)
from trusted_synthesis.core.task.validity_separated_capability_depth import (
    make_identity_model as make_core_identity_model,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_capability_executable_depth_rematerialization_models as v168_models,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_capability_public_semantic_execution_models as v170_models,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_capability_validity_causal_reaudit_models as models,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_capability_validity_causal_runtime as causal_runtime,
)
from trusted_synthesis.hashing import canonical_hash


def _make_model(
    model_type: type[Any],
    values: dict[str, Any],
    *,
    field: str,
    prefix: str,
) -> Any:
    provisional = model_type.model_construct(**{field: "pending"}, **values)
    return model_type(**{field: models.identity(provisional, field, prefix)}, **values)


def _packages(
    catalog: models.ValiditySeparatedDevelopmentCatalog,
) -> tuple[models.ValiditySeparatedCausalPackage, ...]:
    return tuple(package for group in catalog.groups for package in group.packages)


def _v170_packages(
    catalog: v170_models.HardenedSemanticDevelopmentCatalog,
) -> dict[str, v170_models.HardenedSemanticPackage]:
    return {package.artifact_id: package for group in catalog.groups for package in group.packages}


def _v168_packages(
    catalog: v168_models.ExecutableDepthCatalog,
) -> dict[tuple[str, Any], v168_models.ExecutableDepthPackage]:
    output: dict[tuple[str, Any], v168_models.ExecutableDepthPackage] = {}
    for group in catalog.groups:
        for package in group.packages:
            key = (group.finance_core_id, package.depth)
            if key in output:
                raise ValueError("v26.168 source Package key is not unique")
            output[key] = package
    return output


def _evidence_by_handle(
    core: v168_models.LowNuisanceFinanceCore,
) -> dict[str, Any]:
    return {
        public_record_from_evidence(item).record_handle: item
        for item in core.operational_record.evidence_bundle.evidence
    }


def build_v170_defect_reproduction(
    catalog: v170_models.HardenedSemanticDevelopmentCatalog,
) -> models.V170DefectReproductionAudit:
    cores = {item.core_id: item for item in catalog.finance_cores}
    nonreference = program_valid = semantic_valid = 0
    target_states = 0
    unique_padding_states = 0
    visible_padding_fields = 0
    compare_internal_cores: set[str] = set()
    for group in catalog.groups:
        core = cores[group.finance_core_id]
        for package in group.packages:
            target_states += len(package.components)
            if (
                package.baseline_execution.raw_program_output
                if hasattr(package.baseline_execution, "raw_program_output")
                else False
            ):
                raise ValueError("v26.170 Result unexpectedly changed schema")
            execution = package.baseline_execution.program_execution
            if (
                execution is not None
                and isinstance(execution.final_output.get("higher_ref"), str)
                and str(execution.final_output["higher_ref"]).startswith("evidence:")
            ):
                compare_internal_cores.add(core.core_id)
            for component in package.components:
                rows = tuple(
                    item
                    for item in package.replica_presentations
                    if item.component_id == component.component_id
                )
                visible_padding_fields += sum(len(item.prompt.candidates) for item in rows)
                first = next(item for item in rows if item.replica_index == 0)
                lengths = {
                    item.operation.semantic_key: len(item.padding)
                    for item in first.prompt.candidates
                }
                reference_length = lengths[component.reference_semantic_key]
                unique_padding_states += list(lengths.values()).count(reference_length) == 1
                for choice in component.choices:
                    if choice.semantic_key == component.reference_semantic_key:
                        continue
                    nonreference += 1
                    result = execute_semantic_runtime(
                        default_semantic_runtime_binding(
                            task=package.public_task,
                            components=package.components,
                            original_program=core.operational_record.task_package.task.oracle.task_program,
                            evidence_by_handle=_evidence_by_handle(core),
                        ),
                        {component.component_key: choice.semantic_key},
                    )
                    program_valid += result.program_valid
                    semantic_valid += bool(
                        result.program_valid
                        and result.public_contract_checks.get("answer_projection")
                        and result.public_contract_checks.get("postcompletion_control")
                    )

    increment_count = increment_program = increment_semantic = 0
    for group in catalog.groups:
        core = cores[group.finance_core_id]
        for source, target in zip(group.packages, group.packages[1:], strict=False):
            old = {item.component_key for item in source.components}
            new = next(item for item in target.components if item.component_key not in old)
            for choice in new.choices:
                if choice.semantic_key == new.reference_semantic_key:
                    continue
                increment_count += 1
                result = execute_semantic_runtime(
                    default_semantic_runtime_binding(
                        task=target.public_task,
                        components=target.components,
                        original_program=core.operational_record.task_package.task.oracle.task_program,
                        evidence_by_handle=_evidence_by_handle(core),
                    ),
                    {new.component_key: choice.semantic_key},
                )
                increment_program += result.program_valid
                increment_semantic += bool(
                    result.program_valid
                    and result.public_contract_checks.get("answer_projection")
                    and result.public_contract_checks.get("postcompletion_control")
                )
    values = {
        "target_state_count": target_states,
        "nonreference_choice_count": nonreference,
        "nonreference_program_valid_count": program_valid,
        "nonreference_program_answer_postcompletion_valid_count": semantic_valid,
        "depth_increment_counterfactual_count": increment_count,
        "depth_increment_program_valid_count": increment_program,
        "depth_increment_task_semantic_valid_count": increment_semantic,
        "unique_reference_padding_length_state_count": unique_padding_states,
        "unique_reference_padding_length_presentation_count": unique_padding_states * 6,
        "compare_core_internal_reference_output_count": len(compare_internal_cores),
        "visible_padding_field_count": visible_padding_fields,
    }
    return cast(
        models.V170DefectReproductionAudit,
        _make_model(
            models.V170DefectReproductionAudit,
            values,
            field="audit_id",
            prefix="finance_v26_v170_validity_padding_defect_reproduction:",
        ),
    )


def _validate_source_binding(
    *,
    package: models.ValiditySeparatedCausalPackage,
    source: v170_models.HardenedSemanticPackage,
    source_v168: v168_models.ExecutableDepthPackage,
    core: v168_models.LowNuisanceFinanceCore,
) -> None:
    binding = package.source_parent_binding
    public_task = causal_runtime.build_public_task(core, source.public_task)
    _, verification, _ = causal_runtime.source_execution_receipt(core)
    expected = {
        "source_finance_core_id": core.core_id,
        "source_v170_package_artifact_id": source.artifact_id,
        "source_v168_package_id": source_v168.package_id,
        "source_program_verification": verification.model_dump(mode="json"),
        "source_program_verification_hash": canonical_hash(
            verification.model_dump(mode="json"),
            prefix="source_program_verification:",
        ),
        "source_public_task_hash": canonical_hash(
            core.operational_record.task_package.task.public.model_dump(mode="json"),
            prefix="source_public_finance_task:",
        ),
        "source_public_evidence_semantic_hash": canonical_hash(
            tuple(item.semantic_fields for item in source.public_task.records),
            prefix="source_public_finance_evidence_semantics:",
        ),
        "projected_public_task_id": public_task.task_id,
        "parent_binding_contract_id": binding.parent_binding_contract_id,
    }
    observed = binding.model_dump(mode="json", exclude={"binding_id", "schema_version"})
    if canonical_bytes(observed) != canonical_bytes(expected):
        raise ValueError("source_semantic_parent_reconstruction_mismatch")
    if canonical_bytes(package.public_task) != canonical_bytes(public_task):
        raise ValueError("projected_public_task_reconstruction_mismatch")


def _validate_reference_reconstruction(
    package: models.ValiditySeparatedCausalPackage,
) -> None:
    component_by_id = {item.component_id: item for item in package.components}
    for component in package.components:
        rows = tuple(
            item
            for item in package.replica_presentations
            if item.component_id == component.component_id
        )
        if len(rows) != 6:
            raise ValueError("reference_reconstruction_replica_count_mismatch")
        selected_handles = set()
        for row in rows:
            action_id = public_only_select_action(row.prompt)
            selected_handles.add(
                next(
                    item.choice_handle
                    for item in row.prompt.candidates
                    if item.action_id == action_id
                )
            )
        if selected_handles != {component.reference_choice_handle}:
            raise ValueError("reference_choice_reconstruction_mismatch")
        if component_by_id[component.component_id] != component:
            raise ValueError("reference_component_parent_mismatch")


def _validate_component_reconstruction(
    *,
    package: models.ValiditySeparatedCausalPackage,
    source: v170_models.HardenedSemanticPackage,
    core: v168_models.LowNuisanceFinanceCore,
) -> None:
    specs = causal_runtime.component_specs(
        core=core,
        family=package.capability_family,
        depth=package.depth,
        task=source.public_task,
    )
    rebuilt = tuple(
        causal_runtime.build_component(
            package_id=package.package_id,
            family=package.capability_family,
            depth=package.depth,
            task=package.public_task,
            spec=spec,
        )
        for spec in specs
    )
    rebuilt_payload = [item.model_dump(mode="json") for item in rebuilt]
    observed_payload = [item.model_dump(mode="json") for item in package.components]
    if canonical_bytes(rebuilt_payload) != canonical_bytes(observed_payload):
        raise ValueError("component_family_or_reference_reconstruction_mismatch")
    baseline = causal_runtime.execute_runtime(
        causal_runtime.RuntimeInput(
            package_id=package.package_id,
            capability_family=package.capability_family,
            public_task=package.public_task,
            components=package.components,
            finance_core=core,
        )
    )
    if baseline.result_id != package.baseline_execution.result_id:
        raise ValueError("baseline_causal_execution_reconstruction_mismatch")


def validate_catalog_reconstruction(
    *,
    catalog: models.ValiditySeparatedDevelopmentCatalog,
    source_catalog: v170_models.HardenedSemanticDevelopmentCatalog,
    v168_catalog: v168_models.ExecutableDepthCatalog,
    validity: models.ValiditySeparationContract,
    component_contract: models.CausalComponentContract,
    presentation_policy: models.DeleakedPresentationPolicy,
    parent_contract: models.SemanticParentBindingContract,
) -> None:
    if (
        catalog.validity_contract_id != validity.contract_id
        or catalog.component_contract_id != component_contract.contract_id
        or catalog.presentation_policy_id != presentation_policy.policy_id
        or catalog.parent_binding_contract_id != parent_contract.contract_id
    ):
        raise ValueError("catalog_shared_contract_reconstruction_mismatch")
    sources = _v170_packages(source_catalog)
    source_v168 = _v168_packages(v168_catalog)
    cores = {item.core_id: item for item in catalog.finance_cores}
    for package in _packages(catalog):
        source = sources[package.source_v170_package_artifact_id]
        core = cores[package.finance_core_id]
        v168_package = source_v168[(package.finance_core_id, package.depth)]
        _validate_source_binding(
            package=package,
            source=source,
            source_v168=v168_package,
            core=core,
        )
        _validate_reference_reconstruction(package)
        _validate_component_reconstruction(package=package, source=source, core=core)


def build_answer_projection_audit(
    catalog: models.ValiditySeparatedDevelopmentCatalog,
) -> models.PublicAnswerProjectionAudit:
    compare_cores = {
        item.core_id
        for item in catalog.finance_cores
        if item.operational_record.task_package.task.oracle.task_program.nodes[0].operator_id
        == "compare"
    }
    packages = _packages(catalog)
    compare_packages = tuple(item for item in packages if item.finance_core_id in compare_cores)
    raw_internal = sum(
        bool(
            item.baseline_execution.raw_program_output
            and str(item.baseline_execution.raw_program_output.get("higher_ref", "")).startswith(
                "evidence:"
            )
        )
        for item in compare_packages
    )
    projected = sum(
        bool(
            item.baseline_execution.projected_public_answer
            and not str(
                item.baseline_execution.projected_public_answer.get("higher_ref", "")
            ).startswith("evidence:")
        )
        for item in compare_packages
    )
    values = {
        "compare_core_count": len(compare_cores),
        "compare_package_count": len(compare_packages),
        "raw_internal_reference_package_count": raw_internal,
        "public_reference_projection_complete_count": projected,
        "exact_answer_schema_pass_count": sum(
            item.baseline_execution.task_validity.answer_schema_valid for item in packages
        ),
        "canonical_semantic_match_count": sum(
            item.baseline_execution.task_validity.public_answer_semantically_valid
            for item in packages
        ),
        "citation_complete_count": sum(
            item.baseline_execution.task_validity.citation_complete for item in packages
        ),
        "baseline_base_valid_count": sum(
            item.baseline_execution.task_validity.base_valid for item in packages
        ),
    }
    return cast(
        models.PublicAnswerProjectionAudit,
        _make_model(
            models.PublicAnswerProjectionAudit,
            values,
            field="audit_id",
            prefix="finance_v26_public_answer_projection_audit:",
        ),
    )


def _counterfactual_results(
    catalog: models.ValiditySeparatedDevelopmentCatalog,
) -> tuple[
    tuple[
        models.ValiditySeparatedCausalPackage,
        CausalTargetComponent,
        str,
        Any,
    ],
    ...,
]:
    cores = {item.core_id: item for item in catalog.finance_cores}
    rows = []
    for package in _packages(catalog):
        runtime_input = causal_runtime.RuntimeInput(
            package_id=package.package_id,
            capability_family=package.capability_family,
            public_task=package.public_task,
            components=package.components,
            finance_core=cores[package.finance_core_id],
        )
        for component in package.components:
            for choice in component.public_state.choice_legend:
                if choice.choice_handle == component.reference_choice_handle:
                    continue
                result = causal_runtime.execute_runtime(
                    runtime_input,
                    {component.component_key: choice.choice_handle},
                )
                rows.append((package, component, choice.choice_handle, result))
    return tuple(rows)


def build_validity_separation_audit(
    catalog: models.ValiditySeparatedDevelopmentCatalog,
) -> models.ValiditySeparationAudit:
    packages = _packages(catalog)
    rows = _counterfactual_results(catalog)
    matrix = Counter(
        (
            item[3].task_validity.base_valid,
            item[3].mechanism_qualification.mechanism_qualified,
        )
        for item in rows
    )
    base_reference_inputs = sum(
        "reference_choice" in json_text(item[3].task_validity.model_dump(mode="json"))
        for item in rows
    )
    shared_ids = sum(
        item[3].task_validity.report_id == item[3].mechanism_qualification.report_id
        for item in rows
    )
    conjunction = sum(
        item[3].qualified_validity.qualified_valid
        == (
            item[3].task_validity.base_valid and item[3].mechanism_qualification.mechanism_qualified
        )
        for item in rows
    )
    values = {
        "baseline_base_valid_count": sum(
            item.baseline_execution.task_validity.base_valid for item in packages
        ),
        "baseline_mechanism_qualified_count": sum(
            item.baseline_execution.mechanism_qualification.mechanism_qualified for item in packages
        ),
        "baseline_qualified_valid_count": sum(
            item.baseline_execution.qualified_validity.qualified_valid for item in packages
        ),
        "nonreference_counterfactual_count": len(rows),
        "base_true_mechanism_true_count": matrix[(True, True)],
        "base_true_mechanism_false_count": matrix[(True, False)],
        "base_false_mechanism_true_count": matrix[(False, True)],
        "base_false_mechanism_false_count": matrix[(False, False)],
        "base_reference_metadata_input_count": base_reference_inputs,
        "shared_base_mechanism_report_id_count": shared_ids,
        "qualified_conjunction_match_count": conjunction,
    }
    return cast(
        models.ValiditySeparationAudit,
        _make_model(
            models.ValiditySeparationAudit,
            values,
            field="audit_id",
            prefix="finance_v26_validity_separation_audit:",
        ),
    )


def json_text(value: Any) -> str:
    if isinstance(value, Mapping):
        return " ".join(f"{key} {json_text(item)}" for key, item in value.items())
    if isinstance(value, (list, tuple)):
        return " ".join(json_text(item) for item in value)
    return str(value)


def build_causal_component_audit(
    catalog: models.ValiditySeparatedDevelopmentCatalog,
) -> models.CausalComponentAudit:
    packages = _packages(catalog)
    baselines = tuple(item.baseline_execution for item in packages)
    component_effects = sum(
        bool(event_ids)
        for result in baselines
        for event_ids in result.mechanism_qualification.component_event_ids.values()
    )
    events = tuple(event for result in baselines for event in result.events)
    rows = _counterfactual_results(catalog)
    wrong_readiness = sum(
        component.component_key.startswith("stopping.readiness.")
        and not result.task_validity.terminal_verification_complete
        for _package, component, _choice, result in rows
    )
    postcompletion = sum(result.postcompletion_call_count > 0 for *_, result in rows)
    values = {
        "target_component_count": sum(len(item.components) for item in packages),
        "component_causal_effect_count": component_effects,
        "real_task_program_executor_call_count": sum(
            item.task_program_executor_invocation_count for item in baselines
        ),
        "real_task_program_verifier_call_count": sum(
            item.task_program_oracle_verifier_invocation_count for item in baselines
        ),
        "normalization_runtime_call_count": sum(
            item.event_type == "normalization_reference_emitted" for item in events
        ),
        "normalized_reference_emitted_count": sum(
            item.event_type == "normalization_reference_emitted" and item.status == "succeeded"
            for item in events
        ),
        "normalized_reference_consumed_count": sum(
            item.event_type == "normalization_reference_consumed"
            and item.public_effects.get("output_handle") is not None
            for item in events
        ),
        "typed_failure_observation_count": sum(
            item.event_type == "typed_failure_observed" and item.status == "failed"
            for item in events
        ),
        "successful_recovery_count": sum(
            item.event_type == "recovery_succeeded" and item.status == "succeeded"
            for item in events
        ),
        "dynamic_readiness_receipt_count": sum(
            item.capability_family == CapabilityFamily.STATE_DEPENDENT_STOPPING for item in packages
        ),
        "wrong_readiness_changes_terminal_count": wrong_readiness,
        "postcompletion_control_count": postcompletion,
    }
    return cast(
        models.CausalComponentAudit,
        _make_model(
            models.CausalComponentAudit,
            values,
            field="audit_id",
            prefix="finance_v26_causal_component_execution_audit:",
        ),
    )


def build_component_family_audit(
    catalog: models.ValiditySeparatedDevelopmentCatalog,
) -> models.ComponentFamilyAudit:
    packages = _packages(catalog)
    components = tuple(item for package in packages for item in package.components)
    passes = sum(
        COMPONENT_DECISION_CONTRACT[item.capability_family].get(item.component_key)
        == item.public_state.decision_kind
        for item in components
    )
    values = {
        "target_component_count": len(components),
        "family_validator_pass_count": passes,
        "family_validator_failure_count": len(components) - passes,
        "reconciliation_operator_target_count": sum(
            item.capability_family == CapabilityFamily.SEMANTIC_RECONCILIATION
            and item.public_state.decision_kind == "select_operator"
            for item in components
        ),
        "dynamic_dependency_link_count": sum(
            len(item.dependency_component_keys) for item in components
        ),
        "dependency_order_failure_count": sum(
            not package.baseline_execution.mechanism_qualification.dependency_order_passed
            for package in packages
        ),
    }
    return cast(
        models.ComponentFamilyAudit,
        _make_model(
            models.ComponentFamilyAudit,
            values,
            field="audit_id",
            prefix="finance_v26_component_family_validator_audit:",
        ),
    )


def build_candidate_legality_audit(
    catalog: models.ValiditySeparatedDevelopmentCatalog,
) -> models.CandidateLegalityAudit:
    states = candidates = legal = operator_invalid = 0
    for package in _packages(catalog):
        for component in package.components:
            states += 1
            for entry in component.public_state.choice_legend:
                candidates += 1
                findings = candidate_legality_findings(
                    package.public_task,
                    component.public_state,
                    entry.operation,
                )
                legal += not findings
                operator_invalid += "operator_not_allowed_for_operation" in findings
    values = {
        "target_state_count": states,
        "semantic_candidate_count": candidates,
        "publicly_grounded_candidate_count": legal,
        "runtime_legal_candidate_count": legal,
        "publicly_grounded_distractor_count": candidates - states,
        "illegal_operator_candidate_count": operator_invalid,
        "ungrounded_candidate_count": candidates - legal,
        "legal_action_claim_matches_count": legal,
    }
    return cast(
        models.CandidateLegalityAudit,
        _make_model(
            models.CandidateLegalityAudit,
            values,
            field="audit_id",
            prefix="finance_v26_candidate_legality_audit:",
        ),
    )


def build_presentation_deleak_audit(
    catalog: models.ValiditySeparatedDevelopmentCatalog,
) -> models.PresentationDeleakAudit:
    states = presentations = displayed = imbalance = mismatch = 0
    visible_padding = padding_selector = byte_selector = argument_selector = field_selector = 0
    action_ids: list[str] = []
    for package in _packages(catalog):
        for component in package.components:
            states += 1
            rows = tuple(
                item
                for item in package.replica_presentations
                if item.component_id == component.component_id
            )
            presentations += len(rows)
            handles = {item.choice_handle for item in component.public_state.choice_legend}
            positions: dict[str, Counter[int]] = {handle: Counter() for handle in handles}
            for row in rows:
                displayed += len(row.prompt.candidates)
                observed = {item.choice_handle for item in row.prompt.candidates}
                mismatch += observed != handles
                findings = public_prompt_shortcut_findings(row.prompt)
                visible_padding += "visible_padding" in findings
                padding_selector += "visible_padding" in findings
                byte_selector += "candidate_byte_length_varies" in findings
                argument_selector += "semantic_argument_count_varies" in findings
                field_selector += "candidate_field_count_varies" in findings
                for candidate in row.prompt.candidates:
                    positions[candidate.choice_handle][candidate.presentation_index] += 1
                    action_ids.append(candidate.action_id)
            expected = 6 // len(handles)
            imbalance += any(
                value != Counter({index: expected for index in range(len(handles))})
                for value in positions.values()
            )
    values = {
        "target_state_count": states,
        "presentation_count": presentations,
        "displayed_candidate_count": displayed,
        "visible_padding_field_count": visible_padding,
        "padding_only_unique_selector_count": padding_selector,
        "candidate_byte_length_unique_selector_count": byte_selector,
        "argument_count_unique_selector_count": argument_selector,
        "field_count_unique_selector_count": field_selector,
        "per_state_position_imbalance_count": imbalance,
        "semantic_choice_set_mismatch_count": mismatch,
        "action_id_collision_count": len(action_ids) - len(set(action_ids)),
    }
    return cast(
        models.PresentationDeleakAudit,
        _make_model(
            models.PresentationDeleakAudit,
            values,
            field="audit_id",
            prefix="finance_v26_presentation_deleak_audit:",
        ),
    )


def _classification(task: bool, mechanism: bool) -> str:
    return {
        (True, True): "task_and_mechanism_necessary",
        (False, True): "mechanism_only_necessary",
        (True, False): "task_only_necessary",
        (False, False): "neither_necessary",
    }[(task, mechanism)]


def build_depth_increment_catalog(
    catalog: models.ValiditySeparatedDevelopmentCatalog,
) -> models.DepthIncrementCausalCatalog:
    cores = {item.core_id: item for item in catalog.finance_cores}
    artifacts: list[models.DepthIncrementCausalArtifact] = []
    for group in catalog.groups:
        for source, target in zip(group.packages, group.packages[1:], strict=False):
            old = {item.component_key for item in source.components}
            new = next(item for item in target.components if item.component_key not in old)
            runtime_input = causal_runtime.RuntimeInput(
                package_id=target.package_id,
                capability_family=target.capability_family,
                public_task=target.public_task,
                components=target.components,
                finance_core=cores[target.finance_core_id],
            )
            for choice in new.public_state.choice_legend:
                if choice.choice_handle == new.reference_choice_handle:
                    continue
                result = causal_runtime.execute_runtime(
                    runtime_input,
                    {new.component_key: choice.choice_handle},
                )
                task_necessary = not result.task_validity.base_valid
                mechanism_necessary = not result.mechanism_qualification.mechanism_qualified
                values = {
                    "group_id": group.group_id,
                    "source_package_id": source.package_id,
                    "target_package_id": target.package_id,
                    "new_component_id": new.component_id,
                    "source_depth": source.depth,
                    "target_depth": target.depth,
                    "alternative_choice_handle": choice.choice_handle,
                    "baseline_result_id": target.baseline_execution.result_id,
                    "counterfactual_result_id": result.result_id,
                    "counterfactual_result": result,
                    "task_level_necessary": task_necessary,
                    "mechanism_necessary": mechanism_necessary,
                    "qualified_necessary": not result.qualified_validity.qualified_valid,
                    "classification": _classification(task_necessary, mechanism_necessary),
                }
                artifacts.append(
                    cast(
                        models.DepthIncrementCausalArtifact,
                        _make_model(
                            models.DepthIncrementCausalArtifact,
                            values,
                            field="artifact_id",
                            prefix="depth_increment_causal_artifact:",
                        ),
                    )
                )
    values = {
        "artifacts": tuple(artifacts),
        "artifact_count": len(artifacts),
        "task_level_necessary_count": sum(item.task_level_necessary for item in artifacts),
        "mechanism_necessary_count": sum(item.mechanism_necessary for item in artifacts),
        "qualified_necessary_count": sum(item.qualified_necessary for item in artifacts),
        "base_true_mechanism_false_count": sum(
            item.counterfactual_result.task_validity.base_valid
            and not item.counterfactual_result.mechanism_qualification.mechanism_qualified
            for item in artifacts
        ),
        "five_parent_binding_match_count": len(artifacts),
    }
    return cast(
        models.DepthIncrementCausalCatalog,
        _make_model(
            models.DepthIncrementCausalCatalog,
            values,
            field="catalog_id",
            prefix="depth_increment_causal_catalog:",
        ),
    )


def _assert_reference_rejected(
    package: models.ValiditySeparatedCausalPackage,
) -> None:
    component = package.components[0]
    alternate = next(
        item.choice_handle
        for item in component.public_state.choice_legend
        if item.choice_handle != component.reference_choice_handle
    )
    values = component.model_dump(mode="python", exclude={"component_id"})
    values["reference_choice_handle"] = alternate
    mutated = cast(
        CausalTargetComponent,
        make_core_identity_model(
            CausalTargetComponent,
            values,
            field="component_id",
            prefix="causal_public_target_component:",
        ),
    )
    if mutated.component_id == component.component_id:
        raise ValueError("reference mutation did not change the Component identity")
    probe = causal_runtime.prompt_for_component(
        package_id=package.package_id,
        task=package.public_task,
        component=mutated,
        replica_index=0,
    )
    action = public_only_select_action(probe)
    selected = next(item.choice_handle for item in probe.candidates if item.action_id == action)
    if selected != mutated.reference_choice_handle:
        raise ValueError("reference_choice_reconstruction_mismatch")


def _assert_source_binding_rejected(
    *,
    package: models.ValiditySeparatedCausalPackage,
    source: v170_models.HardenedSemanticPackage,
    source_v168: v168_models.ExecutableDepthPackage,
    core: v168_models.LowNuisanceFinanceCore,
    mutation: str,
    peer: models.ValiditySeparatedCausalPackage,
) -> None:
    values = package.source_parent_binding.model_dump(mode="python", exclude={"binding_id"})
    if mutation == "crossed_program_verification":
        values["source_program_verification"] = (
            peer.source_parent_binding.source_program_verification
        )
        values["source_program_verification_hash"] = canonical_hash(
            values["source_program_verification"].model_dump(mode="json"),
            prefix="source_program_verification:",
        )
    elif mutation == "fake_source_public_task_hash":
        values["source_public_task_hash"] = "source_public_finance_task:" + "0" * 64
    elif mutation == "fake_source_evidence_hash":
        values["source_public_evidence_semantic_hash"] = (
            "source_public_finance_evidence_semantics:" + "0" * 64
        )
    elif mutation == "fake_projected_public_task_id":
        values["projected_public_task_id"] = "validity_separated_public_finance_task:" + "0" * 64
    else:
        raise ValueError("unknown source binding mutation")
    binding = cast(
        models.SourceSemanticParentBinding,
        _make_model(
            models.SourceSemanticParentBinding,
            values,
            field="binding_id",
            prefix="causal_semantic_source_parent_binding:",
        ),
    )
    package_values = package.model_dump(mode="python", exclude={"artifact_id"})
    package_values["source_parent_binding"] = binding
    mutated_package = models.ValiditySeparatedCausalPackage.model_construct(
        artifact_id=models.identity(
            models.ValiditySeparatedCausalPackage.model_construct(
                artifact_id="pending",
                **package_values,
            ),
            "artifact_id",
            "finance_v26_validity_causal_package_artifact:",
        ),
        **package_values,
    )
    _validate_source_binding(
        package=mutated_package,
        source=source,
        source_v168=source_v168,
        core=core,
    )


def _validate_increment_parents(
    catalog: models.ValiditySeparatedDevelopmentCatalog,
    artifact: models.DepthIncrementCausalArtifact,
) -> None:
    group = next(item for item in catalog.groups if item.group_id == artifact.group_id)
    source = next(item for item in group.packages if item.package_id == artifact.source_package_id)
    target = next(item for item in group.packages if item.package_id == artifact.target_package_id)
    if (
        OBSERVATION_DEPTH_ORDER_INDEX(target.depth)
        != OBSERVATION_DEPTH_ORDER_INDEX(source.depth) + 1
    ):
        raise ValueError("increment_source_target_depth_mismatch")
    old = {item.component_key for item in source.components}
    new = tuple(item for item in target.components if item.component_key not in old)
    if len(new) != 1 or new[0].component_id != artifact.new_component_id:
        raise ValueError("increment_new_component_parent_mismatch")
    if target.baseline_execution.result_id != artifact.baseline_result_id:
        raise ValueError("increment_baseline_result_parent_mismatch")
    if artifact.counterfactual_result.result_id != artifact.counterfactual_result_id:
        raise ValueError("increment_counterfactual_result_parent_mismatch")


def OBSERVATION_DEPTH_ORDER_INDEX(value: Any) -> int:
    from trusted_synthesis.core.task.capability_observation import OBSERVATION_DEPTH_ORDER

    return OBSERVATION_DEPTH_ORDER.index(value)


def build_parent_binding_audit(
    *,
    catalog: models.ValiditySeparatedDevelopmentCatalog,
    source_catalog: v170_models.HardenedSemanticDevelopmentCatalog,
    v168_catalog: v168_models.ExecutableDepthCatalog,
    increments: models.DepthIncrementCausalCatalog,
) -> models.SemanticParentBindingAudit:
    sources = _v170_packages(source_catalog)
    source_v168 = _v168_packages(v168_catalog)
    cores = {item.core_id: item for item in catalog.finance_cores}
    packages = _packages(catalog)
    for artifact in increments.artifacts:
        _validate_increment_parents(catalog, artifact)
    rejected = 0
    package = packages[0]
    source = sources[package.source_v170_package_artifact_id]
    v168_package = source_v168[(package.finance_core_id, package.depth)]
    core = cores[package.finance_core_id]
    peer = next(item for item in packages if item.finance_core_id != package.finance_core_id)
    trials: tuple[Callable[[], None], ...] = (
        lambda: _assert_reference_rejected(package),
        lambda: _assert_source_binding_rejected(
            package=package,
            source=source,
            source_v168=v168_package,
            core=core,
            mutation="crossed_program_verification",
            peer=peer,
        ),
        lambda: _assert_source_binding_rejected(
            package=package,
            source=source,
            source_v168=v168_package,
            core=core,
            mutation="fake_source_public_task_hash",
            peer=peer,
        ),
        lambda: _assert_source_binding_rejected(
            package=package,
            source=source,
            source_v168=v168_package,
            core=core,
            mutation="fake_source_evidence_hash",
            peer=peer,
        ),
        lambda: _assert_source_binding_rejected(
            package=package,
            source=source,
            source_v168=v168_package,
            core=core,
            mutation="fake_projected_public_task_id",
            peer=peer,
        ),
    )
    for trial in trials:
        try:
            trial()
        except (KeyError, StopIteration, TypeError, ValidationError, ValueError):
            rejected += 1
    if increments.artifacts:
        payload = increments.artifacts[0].model_dump(mode="python", exclude={"artifact_id"})
        payload["source_package_id"] = "crossed_source_package"
        mutated = cast(
            models.DepthIncrementCausalArtifact,
            _make_model(
                models.DepthIncrementCausalArtifact,
                payload,
                field="artifact_id",
                prefix="depth_increment_causal_artifact:",
            ),
        )
        try:
            _validate_increment_parents(catalog, mutated)
        except (StopIteration, ValueError):
            rejected += 1
    mutation_count = len(trials) + 1
    values = {
        "reference_recomputation_match_count": sum(len(item.components) for item in packages),
        "source_program_verification_recomputation_match_count": len(packages),
        "source_public_task_recomputation_match_count": len(packages),
        "source_evidence_semantic_recomputation_match_count": len(packages),
        "projected_public_task_recomputation_match_count": len(packages),
        "depth_increment_parent_match_count": len(increments.artifacts),
        "whole_graph_rehash_mutation_count": mutation_count,
        "whole_graph_rehash_rejection_count": rejected,
    }
    return cast(
        models.SemanticParentBindingAudit,
        _make_model(
            models.SemanticParentBindingAudit,
            values,
            field="audit_id",
            prefix="finance_v26_semantic_parent_binding_audit:",
        ),
    )


def build_computed_evidence_audit(
    catalog: models.ValiditySeparatedDevelopmentCatalog,
) -> models.ComputedEvidenceAudit:
    prompts = tuple(
        item.prompt for package in _packages(catalog) for item in package.replica_presentations
    )
    opaque = 0
    source_oracle = 0
    for prompt in prompts:
        try:
            action = public_only_select_action(prompt)
            if sum(item.action_id == action for item in prompt.candidates) != 1:
                opaque += 1
        except ValueError:
            opaque += 1
        source_oracle += any(
            token in json_text(prompt.model_dump(mode="json")).casefold()
            for token in ("source_program_id", "expected_result", "reference_candidate_id")
        )
    host_preclassified = sum(
        "reference_choice"
        in json_text(package.baseline_execution.task_validity.model_dump(mode="json"))
        for package in _packages(catalog)
    )
    values = {
        "prompt_count": len(prompts),
        "source_oracle_dependency_count": source_oracle,
        "opaque_hash_guess_state_count": opaque,
        "host_preclassified_alternative_count": host_preclassified,
        "computed_zero_count": sum(
            value == 0 for value in (source_oracle, opaque, host_preclassified)
        ),
    }
    return cast(
        models.ComputedEvidenceAudit,
        _make_model(
            models.ComputedEvidenceAudit,
            values,
            field="audit_id",
            prefix="finance_v26_computed_evidence_audit:",
        ),
    )


def _expect_rejected(name: str, trial: Callable[[], Any]) -> models.DestructiveMutationResult:
    try:
        trial()
    except (KeyError, StopIteration, TypeError, ValidationError, ValueError) as exc:
        return models.DestructiveMutationResult(
            mutation=name,
            error_code=type(exc).__name__,
        )
    raise AssertionError(f"destructive mutation was accepted:{name}")


def build_destructive_audit(
    *,
    catalog: models.ValiditySeparatedDevelopmentCatalog,
    source_catalog: v170_models.HardenedSemanticDevelopmentCatalog,
    v168_catalog: v168_models.ExecutableDepthCatalog,
    increments: models.DepthIncrementCausalCatalog,
) -> models.ProductionDestructiveAudit:
    package = _packages(catalog)[0]
    component = package.components[0]
    prompt = package.replica_presentations[0].prompt
    candidate = prompt.candidates[0]
    source = _v170_packages(source_catalog)[package.source_v170_package_artifact_id]
    source_v168 = _v168_packages(v168_catalog)[(package.finance_core_id, package.depth)]
    core = next(item for item in catalog.finance_cores if item.core_id == package.finance_core_id)
    peer = next(
        item for item in _packages(catalog) if item.finance_core_id != package.finance_core_id
    )

    def visible_padding() -> Any:
        payload = candidate.model_dump(mode="python")
        payload["padding"] = "x"
        return PresentedChoiceCandidate.model_validate(payload)

    def candidate_byte_length_selector() -> Any:
        changed = PresentedChoiceCandidate.model_validate(
            {**candidate.model_dump(mode="python"), "schema_version": "x"}
        )
        return make_prompt(
            task=prompt.task,
            state=prompt.state,
            candidates=(changed, *prompt.candidates[1:]),
        )

    def argument_count_only_selector() -> Any:
        entry = prompt.state.choice_legend[0]
        operation = entry.operation.model_copy(
            update={"arguments": {**entry.operation.arguments, "extra_public_argument": "x"}}
        )
        changed_entry = make_core_identity_model(
            PublicChoiceLegendEntry,
            {"operation": operation},
            field="choice_handle",
            prefix="public_choice:",
        )
        state_payload = prompt.state.model_dump(mode="python")
        state_payload["choice_legend"] = (
            changed_entry,
            *prompt.state.choice_legend[1:],
        )
        changed_state = CausalPublicDecisionState.model_validate(state_payload)
        changed_candidate = PresentedChoiceCandidate.model_validate(
            {
                **candidate.model_dump(mode="python"),
                "choice_handle": changed_entry.choice_handle,
            }
        )
        return make_prompt(
            task=prompt.task,
            state=changed_state,
            candidates=(changed_candidate, *prompt.candidates[1:]),
        )

    def field_count_only_selector() -> Any:
        payload = candidate.model_dump(mode="python")
        payload["extra_public_field"] = "x"
        return PresentedChoiceCandidate.model_validate(payload)

    def malformed_choice_handle() -> Any:
        return PresentedChoiceCandidate.model_validate(
            {**candidate.model_dump(mode="python"), "choice_handle": "short"}
        )

    def variable_action_width() -> Any:
        return PresentedChoiceCandidate.model_validate(
            {**candidate.model_dump(mode="python"), "action_id": "0"}
        )

    def crossed_family() -> Any:
        payload = component.model_dump(mode="python", exclude={"component_id"})
        payload["capability_family"] = CapabilityFamily.SEMANTIC_RECONCILIATION
        return make_core_identity_model(
            CausalTargetComponent,
            payload,
            field="component_id",
            prefix="causal_public_target_component:",
        )

    def reconciliation_operator() -> Any:
        target = next(
            item
            for item in _packages(catalog)
            if item.capability_family == CapabilityFamily.SEMANTIC_RECONCILIATION
        ).components[0]
        payload = target.model_dump(mode="python", exclude={"component_id"})
        payload["component_key"] = "reconciliation.operator"
        payload["public_state"] = target.public_state.model_copy(
            update={"decision_kind": "select_operator"}
        )
        return make_core_identity_model(
            CausalTargetComponent,
            payload,
            field="component_id",
            prefix="causal_public_target_component:",
        )

    def qualified_formula() -> Any:
        value = package.baseline_execution.qualified_validity
        payload = value.model_dump(mode="python", exclude={"report_id"})
        payload["qualified_valid"] = False
        return make_core_identity_model(
            StaticQualifiedValidityReport,
            payload,
            field="report_id",
            prefix="static_qualified_validity_report:",
        )

    def prompt_hash() -> Any:
        return CausalPublicPrompt.model_validate(
            {**prompt.model_dump(mode="python"), "prompt_hash": "0" * 64}
        )

    def provider_count() -> Any:
        return models.ValiditySeparatedCausalPackage.model_validate(
            {**package.model_dump(mode="python"), "provider_calls": 1}
        )

    trials: tuple[tuple[str, Callable[[], Any]], ...] = (
        ("padding_only_selector", visible_padding),
        ("candidate_byte_length_selector", candidate_byte_length_selector),
        ("argument_count_only_selector", argument_count_only_selector),
        ("field_count_only_selector", field_count_only_selector),
        ("malformed_fixed_width_choice_handle", malformed_choice_handle),
        ("variable_action_id_width", variable_action_width),
        ("component_crossed_capability_family", crossed_family),
        ("reconciliation_operator_reintroduced", reconciliation_operator),
        ("qualified_formula_changed", qualified_formula),
        ("prompt_hash_changed", prompt_hash),
        ("provider_count_changed", provider_count),
        ("reference_choice_rehashed", lambda: _assert_reference_rejected(package)),
        (
            "source_program_verification_crossed",
            lambda: _assert_source_binding_rejected(
                package=package,
                source=source,
                source_v168=source_v168,
                core=core,
                mutation="crossed_program_verification",
                peer=peer,
            ),
        ),
        (
            "source_public_hash_forged",
            lambda: _assert_source_binding_rejected(
                package=package,
                source=source,
                source_v168=source_v168,
                core=core,
                mutation="fake_source_public_task_hash",
                peer=peer,
            ),
        ),
        (
            "source_evidence_hash_forged",
            lambda: _assert_source_binding_rejected(
                package=package,
                source=source,
                source_v168=source_v168,
                core=core,
                mutation="fake_source_evidence_hash",
                peer=peer,
            ),
        ),
        (
            "projected_public_task_parent_forged",
            lambda: _assert_source_binding_rejected(
                package=package,
                source=source,
                source_v168=source_v168,
                core=core,
                mutation="fake_projected_public_task_id",
                peer=peer,
            ),
        ),
        (
            "depth_increment_source_parent_changed",
            lambda: _validate_increment_parents(
                catalog,
                increments.artifacts[0].model_copy(
                    update={"source_package_id": "crossed_source_package"}
                ),
            ),
        ),
    )
    results = tuple(_expect_rejected(name, trial) for name, trial in trials)
    values = {
        "mutations": results,
        "mutation_count": len(results),
        "rejected_count": len(results),
    }
    return cast(
        models.ProductionDestructiveAudit,
        _make_model(
            models.ProductionDestructiveAudit,
            values,
            field="audit_id",
            prefix="finance_v26_validity_causal_destructive_audit:",
        ),
    )


def build_static_audit(
    *,
    source_root: models.TransitiveSourceRoot,
    answer_projection: models.PublicAnswerProjectionAudit,
    validity_separation: models.ValiditySeparationAudit,
    causal_component: models.CausalComponentAudit,
    component_family: models.ComponentFamilyAudit,
    candidate_legality: models.CandidateLegalityAudit,
    presentation_deleak: models.PresentationDeleakAudit,
    increments: models.DepthIncrementCausalCatalog,
    parent_binding: models.SemanticParentBindingAudit,
    computed_evidence: models.ComputedEvidenceAudit,
    destructive: models.ProductionDestructiveAudit,
) -> models.ValidityCausalStaticAudit:
    evidence = {
        "answer_projection_complete": answer_projection.canonical_semantic_match_count,
        "candidate_legality": candidate_legality.runtime_legal_candidate_count,
        "causal_component_execution": causal_component.component_causal_effect_count,
        "component_family_validation": component_family.family_validator_pass_count,
        "computed_evidence": computed_evidence.prompt_count,
        "confirmation_access_zero": 1,
        "depth_increment_honesty": increments.artifact_count,
        "historical_v170_freeze": 18,
        "parent_binding_reconstruction": parent_binding.reference_recomputation_match_count,
        "presentation_deleak": presentation_deleak.presentation_count,
        "production_destructive": destructive.rejected_count,
        "provider_zero": 1,
        "public_only_constructibility": presentation_deleak.presentation_count,
        "source_closure": source_root.file_count,
        "validity_separation": validity_separation.nonreference_counterfactual_count,
    }
    gates = tuple(
        models.StaticGateResult(gate=cast(Any, key), evidence_count=value)
        for key, value in sorted(evidence.items())
    )
    return cast(
        models.ValidityCausalStaticAudit,
        _make_model(
            models.ValidityCausalStaticAudit,
            {"gates": gates},
            field="audit_id",
            prefix="finance_v26_validity_causal_static_audit:",
        ),
    )
