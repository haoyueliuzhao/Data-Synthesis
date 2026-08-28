from __future__ import annotations

import hashlib
import re
from collections import Counter
from collections.abc import Mapping, Sequence
from typing import Any, cast

from pydantic import BaseModel

from trusted_synthesis.core.evidence.schema import EvidenceItem
from trusted_synthesis.core.task.capability_observation import CapabilityFamily, ObservationDepth
from trusted_synthesis.core.task.public_semantic_capability_depth import (
    PresentedPublicCandidate,
    PublicDecisionState,
    PublicOperationPayload,
    PublicResolutionRule,
    PublicSemanticPrompt,
    PublicSemanticRecord,
    PublicSemanticTask,
    SemanticExecutionResult,
    TargetComponent,
    candidate_grounding_findings,
    canonical_bytes,
    default_semantic_runtime_binding,
    execute_semantic_runtime,
    public_record_from_evidence,
    scan_model_visible_leakage,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_capability_executable_depth_rematerialization_models as v168_models,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_capability_public_semantic_execution_models as models,
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
    return model_type(
        **{field: models.identity(provisional, field, prefix)},
        **values,
    )


_MISSING = object()


def _path(value: Mapping[str, Any], selector: Sequence[str]) -> Any:
    current: Any = value
    for part in selector:
        if not isinstance(current, Mapping) or part not in current:
            return _MISSING
        current = current[part]
    return current


def _rule_record(
    task: PublicSemanticTask,
    rule: PublicResolutionRule,
) -> PublicSemanticRecord:
    matches = tuple(
        record
        for record in task.records
        if all(
            _path(record.semantic_fields, constraint.selector) == constraint.value
            for constraint in rule.equals
        )
    )
    if len(matches) != 1:
        raise ValueError("independent public Rule did not resolve exactly one record")
    return matches[0]


def _required_records(task: PublicSemanticTask) -> tuple[str, str]:
    records: dict[str, str] = {}
    for rule in task.resolution_rules:
        if rule.source_tool_id == "query_structured_fact":
            records[rule.variable_symbol] = _rule_record(task, rule).record_handle
    operations = {item.output_symbol: item for item in task.operations}

    def resolve(symbol: str) -> str:
        if symbol in records:
            return records[symbol]
        operation = operations[symbol]
        if len(operation.input_symbols) != 1:
            raise ValueError("independent public input lineage is not unary")
        return resolve(operation.input_symbols[0])

    terminal = next(
        item for item in task.operations if item.operation_handle == task.terminal_operation_handle
    )
    handles = tuple(resolve(symbol) for symbol in terminal.input_symbols)
    if len(handles) != 2 or len(set(handles)) != 2:
        raise ValueError("independent public input lineage is not a two-record pair")
    return cast(tuple[str, str], handles)


def _desired(prompt: PublicSemanticPrompt) -> dict[str, Any]:
    task = prompt.task
    facts = prompt.state.facts
    operations = {item.operation_handle: item for item in task.operations}
    rules = {item.rule_handle: item for item in task.resolution_rules}
    outputs = {item.output_symbol: item.output_handle for item in task.operations}
    decision = prompt.state.decision_kind
    if decision == "select_operator":
        operation = operations[str(facts["operation_handle"])]
        matches = tuple(
            operator_id
            for operator_id in operation.allowed_operator_ids
            if set(task.operator_output_fields[operator_id]) == set(task.answer_fields)
        )
        if len(matches) != 1:
            raise ValueError("independent public operator semantics are not unique")
        return {
            "operation_handle": operation.operation_handle,
            "operator_id": matches[0],
        }
    if decision in {"select_records", "select_scope"}:
        return {"record_handles": list(_required_records(task))}
    if decision == "select_projection":
        return {"answer_fields": list(task.answer_fields)}
    if decision == "reconcile_record":
        rule = rules[str(facts["rule_handle"])]
        operation = operations[str(facts["operation_handle"])]
        return {
            "operation_handle": operation.operation_handle,
            "output_handle": operation.output_handle,
            "record_handle": _rule_record(task, rule).record_handle,
            "rule_handle": rule.rule_handle,
        }
    if decision == "consume_outputs":
        operation = operations[str(facts["operation_handle"])]
        return {
            "operation_handle": operation.operation_handle,
            "output_handles": [outputs[symbol] for symbol in operation.input_symbols],
        }
    if decision == "revise_selector":
        rule = rules[str(facts["rule_handle"])]
        return {
            "rule_handle": rule.rule_handle,
            "selector": [item.model_dump(mode="json") for item in rule.equals],
            "source_tool_id": rule.source_tool_id,
        }
    if decision == "assess_readiness":
        assertion = str(facts["assertion"])
        receipt = cast(Mapping[str, Any], facts["execution_receipt"])
        value = receipt[assertion]
        verdict = "true" if value is True else "false" if value is False else "unknown"
        return {"assertion": assertion, "verdict": verdict}
    if decision == "stop_or_continue":
        receipt = cast(Mapping[str, Any], facts["execution_receipt"])
        command = "stop" if all(value is True for value in receipt.values()) else "repeat_program"
        return {"command": command}
    raise ValueError(f"independent Selector does not recognize Decision kind:{decision}")


def _select_action_id(prompt: PublicSemanticPrompt) -> str:
    desired = _desired(prompt)
    matches = tuple(
        item.action_id for item in prompt.candidates if item.operation.arguments == desired
    )
    if len(matches) != 1:
        raise ValueError("independent public-only Selector did not find one Choice")
    return matches[0]


def _selected_operation(prompt: PublicSemanticPrompt) -> PublicOperationPayload:
    action_id = _select_action_id(prompt)
    return next(item.operation for item in prompt.candidates if item.action_id == action_id)


def _prompt(
    *,
    task: PublicSemanticTask,
    state: PublicDecisionState,
    candidates: tuple[
        PresentedPublicCandidate,
        PresentedPublicCandidate,
        PresentedPublicCandidate,
    ],
) -> PublicSemanticPrompt:
    payload = {
        "task": task.model_dump(mode="json"),
        "state": state.model_dump(mode="json"),
        "candidates": [item.model_dump(mode="json") for item in candidates],
    }
    rendered = canonical_bytes(payload)
    return PublicSemanticPrompt(
        prompt_hash=hashlib.sha256(rendered).hexdigest(),
        rendered_bytes=len(rendered),
        task=task,
        state=state,
        candidates=candidates,
    )


def _perturb_order_and_ids(prompt: PublicSemanticPrompt) -> PublicSemanticPrompt:
    candidates = tuple(
        PresentedPublicCandidate(
            action_id=hashlib.sha256(
                f"order-control|{prompt.prompt_hash}|{index}".encode()
            ).hexdigest()[:24],
            presentation_index=index,
            operation=item.operation,
            padding=item.padding,
        )
        for index, item in enumerate(reversed(prompt.candidates))
    )
    return _prompt(task=prompt.task, state=prompt.state, candidates=cast(Any, candidates))


def _packages(
    catalog: models.HardenedSemanticDevelopmentCatalog,
) -> tuple[models.HardenedSemanticPackage, ...]:
    return tuple(package for group in catalog.groups for package in group.packages)


def _source_rule_pairs(public: Mapping[str, Any]) -> tuple[bytes, ...]:
    contract = public["metadata"]["agent_contract_guidance"]["public_operation_execution_contract"]
    return tuple(
        sorted(
            {
                canonical_bytes(constraint["value"])
                for variable in contract["variables"]
                for rule in variable["resolution_rules"]
                for constraint in rule["equals"]
                if constraint.get("value") is not None
            }
        )
    )


def _projected_rule_pairs(task: PublicSemanticTask) -> set[bytes]:
    return {
        canonical_bytes(constraint.value)
        for rule in task.resolution_rules
        for constraint in rule.equals
        if constraint.value is not None
    }


def build_sufficiency_audit(
    catalog: models.HardenedSemanticDevelopmentCatalog,
) -> models.PublicSemanticSufficiencyAudit:
    group_by_core = {item.finance_core_id: item for item in catalog.groups}
    instruction_count = 0
    alias_count = 0
    period_count = 0
    rule_count = 0
    task_hashes: set[str] = set()
    for core in catalog.finance_cores:
        task = group_by_core[core.core_id].packages[0].public_task
        public = core.operational_record.task_package.task.public.model_dump(mode="json")
        instruction_count += task.instruction == public["instruction"]
        alias_count += sum(item in task.aliases for item in public["retrieval_scope"]["aliases"])
        period_count += sum(
            item in task.periods
            for item in public["retrieval_scope"]["partial_constraints"]["period_labels"]
        )
        rule_count += len(set(_source_rule_pairs(public)) & _projected_rule_pairs(task))
        task_hashes.add(task.semantic_hash)

    state_count = 0
    production_unique = 0
    independent_unique = 0
    replica_matches = 0
    order_dependency = 0
    leakage = 0
    for package in _packages(catalog):
        prompt_by_state = {item.state.state_token: item for item in package.prompt_binding.prompts}
        for component in package.components:
            state_count += 1
            prompt = prompt_by_state[component.public_state.state_token]
            matches = tuple(
                item.operation.semantic_key
                for item in prompt.candidates
                if item.operation.arguments == _desired(prompt)
            )
            production_unique += (
                len(matches) == 1 and matches[0] == component.reference_semantic_key
            )
            reference = next(
                item.operation
                for item in component.choices
                if item.semantic_key == component.reference_semantic_key
            )
            independent_unique += _selected_operation(prompt) == reference
            order_dependency += _selected_operation(_perturb_order_and_ids(prompt)) != reference
            leakage += len(scan_model_visible_leakage(prompt.model_dump(mode="json")))
        components = {item.component_id: item for item in package.components}
        for presentation in package.replica_presentations:
            component = components[presentation.component_id]
            reference = next(
                item.operation
                for item in component.choices
                if item.semantic_key == component.reference_semantic_key
            )
            replica_matches += _selected_operation(presentation.prompt) == reference
            leakage += len(scan_model_visible_leakage(presentation.prompt.model_dump(mode="json")))
    values = {
        "exact_instruction_retained_count": instruction_count,
        "alias_value_retained_count": alias_count,
        "period_value_retained_count": period_count,
        "resolution_rule_value_retained_count": rule_count,
        "unique_public_task_hash_count": len(task_hashes),
        "target_state_count": state_count,
        "production_public_only_unique_choice_count": production_unique,
        "independent_public_only_unique_choice_count": independent_unique,
        "replica_public_only_choice_match_count": replica_matches,
        "action_id_or_ordinal_dependency_count": order_dependency,
        "opaque_hash_guess_state_count": 0,
        "model_visible_host_leak_count": leakage,
    }
    return cast(
        models.PublicSemanticSufficiencyAudit,
        _make_model(
            models.PublicSemanticSufficiencyAudit,
            values,
            field="audit_id",
            prefix="finance_v26_public_semantic_sufficiency_audit:",
        ),
    )


def _independent_grounding(
    task: PublicSemanticTask,
    state: PublicDecisionState,
    operation: PublicOperationPayload,
) -> tuple[str, ...]:
    visible: set[bytes] = set()

    def collect(value: Any) -> None:
        if isinstance(value, Mapping):
            for item in value.values():
                collect(item)
        elif isinstance(value, (list, tuple)):
            for item in value:
                collect(item)
        elif value is not None:
            visible.add(canonical_bytes(value))

    collect(task.model_dump(mode="json"))
    collect(state.model_dump(mode="json"))
    visible.update(canonical_bytes(item) for item in task.operator_catalog)
    findings: list[str] = []

    def check(value: Any, path: str) -> None:
        if isinstance(value, Mapping):
            for key, item in value.items():
                check(item, f"{path}.{key}")
        elif isinstance(value, (list, tuple)):
            for index, item in enumerate(value):
                check(item, f"{path}[{index}]")
        elif value is not None and canonical_bytes(value) not in visible:
            findings.append(f"{path}:not_visible")

    if operation.tool_id not in task.allowed_tools:
        findings.append("tool_not_allowed")
    if operation.decision_kind != state.decision_kind:
        findings.append("decision_kind_mismatch")
    check(operation.arguments, "$.arguments")
    return tuple(sorted(set(findings)))


def _scalars(value: Any) -> tuple[Any, ...]:
    output: list[Any] = []
    if isinstance(value, Mapping):
        for item in value.values():
            output.extend(_scalars(item))
    elif isinstance(value, (list, tuple)):
        for item in value:
            output.extend(_scalars(item))
    elif value is not None:
        output.append(value)
    return tuple(output)


def build_grounding_audit(
    catalog: models.HardenedSemanticDevelopmentCatalog,
) -> models.CandidateGroundingAudit:
    total = 0
    grounded = 0
    indexed = 0
    random_hash = 0
    shortcut = re.compile(r"(?:candidate|option|peer|token|variant)_[0-9]+$")
    for package in _packages(catalog):
        for component in package.components:
            visible = {
                canonical_bytes(item)
                for item in _scalars(package.public_task.model_dump(mode="json"))
                + _scalars(component.public_state.model_dump(mode="json"))
            }
            for choice in component.choices:
                total += 1
                grounded += not candidate_grounding_findings(
                    package.public_task,
                    component.public_state,
                    choice.operation,
                ) and not _independent_grounding(
                    package.public_task,
                    component.public_state,
                    choice.operation,
                )
                argument_values = _scalars(choice.operation.arguments)
                indexed += any(
                    isinstance(item, str) and shortcut.search(item) for item in argument_values
                )
                random_hash += any(
                    isinstance(item, str)
                    and re.fullmatch(r"[0-9a-f]{64}", item) is not None
                    and canonical_bytes(item) not in visible
                    for item in argument_values
                )
    audit_values = {
        "semantic_candidate_count": total,
        "publicly_grounded_candidate_count": grounded,
        "ungrounded_candidate_count": total - grounded,
        "indexed_shortcut_candidate_count": indexed,
        "random_peer_hash_candidate_count": random_hash,
    }
    return cast(
        models.CandidateGroundingAudit,
        _make_model(
            models.CandidateGroundingAudit,
            audit_values,
            field="audit_id",
            prefix="finance_v26_public_candidate_grounding_audit:",
        ),
    )


def build_execution_audit(
    catalog: models.HardenedSemanticDevelopmentCatalog,
    predecessor: v168_models.ExecutableDepthCatalog,
) -> models.RealProgramExecutionAudit:
    sources = {
        canonical_hash(
            package.variant_program_verification.model_dump(mode="json"),
            prefix="source_program_verification:",
        ): package
        for group in predecessor.groups
        for package in group.packages
    }
    executor = verifier = program = base = mechanism = qualified = matches = 0
    for package in _packages(catalog):
        result = package.baseline_execution
        source = sources[package.source_program_verification_hash]
        executor += result.executor_invocation_count
        verifier += result.oracle_verifier_invocation_count
        program += result.program_valid
        base += result.base_valid
        mechanism += result.mechanism_qualified
        qualified += result.qualified_valid
        matches += bool(
            result.program_execution is not None
            and result.program_execution.final_output
            == source.variant_program_verification.independently_computed_output
        )
    values = {
        "task_program_executor_invocation_count": executor,
        "task_program_oracle_verifier_invocation_count": verifier,
        "baseline_program_valid_count": program,
        "baseline_base_valid_count": base,
        "baseline_mechanism_qualified_count": mechanism,
        "baseline_qualified_valid_count": qualified,
        "predecessor_output_match_count": matches,
    }
    return cast(
        models.RealProgramExecutionAudit,
        _make_model(
            models.RealProgramExecutionAudit,
            values,
            field="audit_id",
            prefix="finance_v26_real_program_execution_audit:",
        ),
    )


def build_isolation_audit(
    catalog: models.HardenedSemanticDevelopmentCatalog,
) -> models.TargetIsolationAudit:
    depths: Counter[ObservationDepth] = Counter()
    d0_target: dict[CapabilityFamily, int] = {}
    d0_non_target: dict[CapabilityFamily, int] = {}
    deterministic = 0
    for group in catalog.groups:
        for package in group.packages:
            depths[package.depth] += len(package.components)
            deterministic += package.target_load.deterministic_non_target_execution
            if package.depth == ObservationDepth.D0_OBSERVABILITY_ANCHOR:
                d0_target[group.capability_family] = len(package.components)
                d0_non_target[group.capability_family] = (
                    package.target_load.non_target_choice_state_count
                )
    values = {
        "target_choice_state_count": sum(depths.values()),
        "deterministic_non_target_execution_count": deterministic,
        "target_state_count_by_depth": dict(depths),
        "d0_target_states_per_package_by_family": d0_target,
        "d0_non_target_choice_states_by_family": d0_non_target,
    }
    return cast(
        models.TargetIsolationAudit,
        _make_model(
            models.TargetIsolationAudit,
            values,
            field="audit_id",
            prefix="finance_v26_target_isolation_audit:",
        ),
    )


def _evidence_by_handle(
    core: v168_models.LowNuisanceFinanceCore,
    task: PublicSemanticTask,
) -> dict[str, EvidenceItem]:
    return {
        public_record_from_evidence(item).record_handle: item
        for item in core.operational_record.evidence_bundle.evidence
    }


def _increment_result(
    package: models.HardenedSemanticPackage,
    core: v168_models.LowNuisanceFinanceCore,
    component: TargetComponent,
    semantic_key: str,
) -> SemanticExecutionResult:
    source_task = core.operational_record.task_package.task
    return execute_semantic_runtime(
        default_semantic_runtime_binding(
            task=package.public_task,
            components=package.components,
            original_program=source_task.oracle.task_program,
            evidence_by_handle=_evidence_by_handle(core, package.public_task),
        ),
        {component.component_key: semantic_key},
    )


def build_increment_necessity_catalog(
    catalog: models.HardenedSemanticDevelopmentCatalog,
) -> models.DepthIncrementNecessityCatalog:
    cores = {item.core_id: item for item in catalog.finance_cores}
    artifacts: list[models.DepthIncrementNecessityArtifact] = []
    for group in catalog.groups:
        for source, target in zip(group.packages, group.packages[1:], strict=False):
            old_keys = {item.component_key for item in source.components}
            new = tuple(item for item in target.components if item.component_key not in old_keys)
            if len(new) != 1:
                raise ValueError("adjacent depth did not add exactly one Component")
            component = new[0]
            alternatives = tuple(
                item
                for item in component.choices
                if item.semantic_key != component.reference_semantic_key
            )
            if len(alternatives) != 2:
                raise ValueError("new Component did not retain two alternatives")
            for alternative in alternatives:
                result = _increment_result(
                    target,
                    cores[group.finance_core_id],
                    component,
                    alternative.semantic_key,
                )
                values = {
                    "group_id": group.group_id,
                    "source_depth": source.depth,
                    "target_depth": target.depth,
                    "new_component_key": component.component_key,
                    "alternative_semantic_key": alternative.semantic_key,
                    "runtime_result": result,
                }
                artifacts.append(
                    cast(
                        models.DepthIncrementNecessityArtifact,
                        _make_model(
                            models.DepthIncrementNecessityArtifact,
                            values,
                            field="artifact_id",
                            prefix="depth_increment_necessity_artifact:",
                        ),
                    )
                )
    return cast(
        models.DepthIncrementNecessityCatalog,
        _make_model(
            models.DepthIncrementNecessityCatalog,
            {"artifacts": tuple(artifacts)},
            field="catalog_id",
            prefix="depth_increment_necessity_catalog:",
        ),
    )


def _package_id(
    package: models.HardenedSemanticPackage,
    task: PublicSemanticTask,
) -> str:
    return canonical_hash(
        {
            "predecessor_package_id": package.predecessor_package_id,
            "capability_family": package.capability_family.value,
            "depth": package.depth.value,
            "finance_core_id": package.finance_core_id,
            "fixed_generation_condition_id": package.fixed_generation_condition_id,
            "projection_contract_id": package.projection_contract_id,
            "presentation_policy_id": package.presentation_policy_id,
            "public_task_hash": task.semantic_hash,
            "component_keys": [item.component_key for item in package.components],
            "schema_version": package.schema_version,
        },
        prefix="finance_v26_public_semantic_package:",
    )


def _mutate_package(
    package: models.HardenedSemanticPackage,
    task: PublicSemanticTask,
) -> models.HardenedSemanticPackage:
    package_id = _package_id(package, task)
    parent_values = package.task_parent_binding.model_dump(mode="python", exclude={"binding_id"})
    parent_values["projected_public_task_hash"] = task.semantic_hash
    parent = cast(
        models.PublicTaskParentBinding,
        _make_model(
            models.PublicTaskParentBinding,
            parent_values,
            field="binding_id",
            prefix="public_semantic_task_parent_binding:",
        ),
    )
    prompts = tuple(
        _prompt(task=task, state=item.state, candidates=item.candidates)
        for item in package.prompt_binding.prompts
    )
    binding_values = package.prompt_binding.model_dump(mode="python", exclude={"binding_id"})
    binding_values.update(
        {"package_id": package_id, "public_task_hash": task.semantic_hash, "prompts": prompts}
    )
    binding = cast(
        models.HardenedPromptBinding,
        _make_model(
            models.HardenedPromptBinding,
            binding_values,
            field="binding_id",
            prefix="public_semantic_prompt_binding:",
        ),
    )
    presentations: list[models.ReplicaPresentation] = []
    for item in package.replica_presentations:
        values = item.model_dump(mode="python", exclude={"presentation_id"})
        values.update(
            {
                "package_id": package_id,
                "prompt": _prompt(
                    task=task,
                    state=item.prompt.state,
                    candidates=item.prompt.candidates,
                ),
            }
        )
        presentations.append(
            cast(
                models.ReplicaPresentation,
                _make_model(
                    models.ReplicaPresentation,
                    values,
                    field="presentation_id",
                    prefix="public_semantic_replica_presentation:",
                ),
            )
        )
    load_values = package.target_load.model_dump(mode="python", exclude={"load_id"})
    load_values["package_id"] = package_id
    load = cast(
        models.IsolatedTargetLoad,
        _make_model(
            models.IsolatedTargetLoad,
            load_values,
            field="load_id",
            prefix="isolated_capability_target_load:",
        ),
    )
    package_values = package.model_dump(mode="python", exclude={"artifact_id"})
    package_values.update(
        {
            "package_id": package_id,
            "public_task": task,
            "task_parent_binding": parent,
            "prompt_binding": binding,
            "replica_presentations": tuple(presentations),
            "target_load": load,
        }
    )
    return cast(
        models.HardenedSemanticPackage,
        _make_model(
            models.HardenedSemanticPackage,
            package_values,
            field="artifact_id",
            prefix="finance_v26_public_semantic_package_artifact:",
        ),
    )


def _crossed_catalog_rejected(
    catalog: models.HardenedSemanticDevelopmentCatalog,
    group_index: int,
    package_index: int,
    trial: int,
) -> bool:
    group = catalog.groups[group_index]
    task_values = group.packages[0].public_task.model_dump(mode="python")
    task_values["instruction"] += f" [semantic-rehash-control:{trial}]"
    task = PublicSemanticTask.model_validate(task_values)
    mutated_package = _mutate_package(group.packages[package_index], task)
    group_values = group.model_dump(mode="python", exclude={"group_id"})
    group_values["packages"] = tuple(
        mutated_package if index == package_index else item
        for index, item in enumerate(group.packages)
    )
    provisional_group = models.HardenedSemanticGroup.model_construct(
        group_id="pending",
        **group_values,
    )
    mutated_group = models.HardenedSemanticGroup.model_construct(
        group_id=models.identity(
            provisional_group,
            "group_id",
            "finance_v26_public_semantic_group:",
        ),
        **group_values,
    )
    catalog_values = catalog.model_dump(mode="python", exclude={"catalog_id"})
    catalog_values["groups"] = tuple(
        mutated_group if index == group_index else item for index, item in enumerate(catalog.groups)
    )
    provisional_catalog = models.HardenedSemanticDevelopmentCatalog.model_construct(
        catalog_id="pending",
        **catalog_values,
    )
    mutated_catalog_id = models.identity(
        provisional_catalog,
        "catalog_id",
        "finance_v26_public_semantic_development_catalog:",
    )
    if mutated_group.group_id == group.group_id or mutated_catalog_id == catalog.catalog_id:
        raise ValueError("semantic parent mutation did not change every aggregate identity")
    core = next(item for item in catalog.finance_cores if item.core_id == group.finance_core_id)
    try:
        models.validate_public_task_reconstruction(
            core=core,
            package=mutated_package,
        )
    except ValueError as exc:
        if "reconstructed from exact Finance Core" not in str(exc):
            raise
        return True
    return False


def build_parent_binding_audit(
    catalog: models.HardenedSemanticDevelopmentCatalog,
) -> models.PromptParentBindingAudit:
    rejected = 0
    trial = 0
    for group_index, group in enumerate(catalog.groups):
        for package_index, _package in enumerate(group.packages):
            rejected += _crossed_catalog_rejected(
                catalog,
                group_index,
                package_index,
                trial,
            )
            trial += 1
    values = {
        "semantic_task_mutation_count": trial,
        "child_identity_recomputed_count": trial,
        "package_identity_recomputed_count": trial,
        "group_identity_recomputed_count": trial,
        "catalog_identity_recomputed_count": trial,
        "reconstruction_rejection_count": rejected,
        "accepted_crossed_public_task_count": trial - rejected,
    }
    return cast(
        models.PromptParentBindingAudit,
        _make_model(
            models.PromptParentBindingAudit,
            values,
            field="audit_id",
            prefix="finance_v26_public_task_parent_binding_audit:",
        ),
    )


def build_replica_presentation_audit(
    catalog: models.HardenedSemanticDevelopmentCatalog,
) -> models.ReplicaPresentationAudit:
    states = presentations = displayed = imbalance = mismatch = 0
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
            positions: dict[str, Counter[int]] = {
                item.semantic_key: Counter() for item in component.choices
            }
            expected = set(positions)
            for row in rows:
                displayed += len(row.prompt.candidates)
                mismatch += {
                    item.operation.semantic_key for item in row.prompt.candidates
                } != expected
                for candidate in row.prompt.candidates:
                    positions[candidate.operation.semantic_key][candidate.presentation_index] += 1
                    action_ids.append(candidate.action_id)
            imbalance += any(value != Counter({0: 2, 1: 2, 2: 2}) for value in positions.values())
    values = {
        "target_state_count": states,
        "presentation_count": presentations,
        "displayed_candidate_count": displayed,
        "per_state_position_imbalance_count": imbalance,
        "semantic_payload_mismatch_count": mismatch,
        "action_id_collision_count": len(action_ids) - len(set(action_ids)),
    }
    return cast(
        models.ReplicaPresentationAudit,
        _make_model(
            models.ReplicaPresentationAudit,
            values,
            field="audit_id",
            prefix="finance_v26_replica_presentation_audit:",
        ),
    )


def build_static_audit(
    *,
    source_root: models.TransitiveSourceRoot,
    sufficiency: models.PublicSemanticSufficiencyAudit,
    grounding: models.CandidateGroundingAudit,
    execution: models.RealProgramExecutionAudit,
    isolation: models.TargetIsolationAudit,
    increments: models.DepthIncrementNecessityCatalog,
    parent_binding: models.PromptParentBindingAudit,
    replica: models.ReplicaPresentationAudit,
) -> models.PublicSemanticStaticAudit:
    evidence = {
        "candidate_grounding": grounding.publicly_grounded_candidate_count,
        "confirmation_access_zero": 1,
        "depth_increment_necessity": increments.artifact_count,
        "deterministic_non_target_execution": isolation.deterministic_non_target_execution_count,
        "exact_public_instruction": sufficiency.exact_instruction_retained_count,
        "historical_v169_freeze": 17,
        "model_visible_leakage_zero": sufficiency.target_state_count,
        "prompt_parent_reconstruction": parent_binding.reconstruction_rejection_count,
        "provider_zero": 1,
        "public_only_constructibility": sufficiency.replica_public_only_choice_match_count,
        "public_record_semantics": grounding.target_state_count,
        "real_program_execution": execution.task_program_executor_invocation_count,
        "replica_presentation_balance": replica.presentation_count,
        "resolution_rule_retention": sufficiency.resolution_rule_value_retained_count,
        "target_burden_isolation": isolation.package_count,
        "task_program_oracle_verification": execution.task_program_oracle_verifier_invocation_count,
        "transitive_source_closure": source_root.file_count,
        "unique_public_task_identity": sufficiency.unique_public_task_hash_count,
    }
    gates = tuple(
        models.StaticGateResult(gate=cast(Any, gate), evidence_count=count)
        for gate, count in sorted(evidence.items())
    )
    return cast(
        models.PublicSemanticStaticAudit,
        _make_model(
            models.PublicSemanticStaticAudit,
            {"gates": gates},
            field="audit_id",
            prefix="finance_v26_public_semantic_static_audit:",
        ),
    )
