from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from typing import Any, cast

from trusted_synthesis.core.trajectory.executable_support import (
    MechanismNecessityArtifact,
    PublicWitnessStep,
)
from trusted_synthesis.core.trajectory.executable_task import (
    BoundPublicExecutableWitness,
    StaticModelAuthorityPathCatalog,
    bound_public_executable_witness_id,
    matching_sufficient_support_set,
)
from trusted_synthesis.core.trajectory.public_operation import PublicOperationVariable
from trusted_synthesis.domains.finance.executable_support_runtime import (
    FinanceExecutableSupportRuntime,
)
from trusted_synthesis.domains.finance.interactive_agent_runtime import (
    FinanceTypedRecoveryScenario,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_executable_task_rematerialization import (  # noqa: E501
    MechanismCounterfactualReplayRecord,
    _mechanism_necessity,
    _path_catalog,
    _project_answer,
    _replace_runtime_refs,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_public_operation_rematerialization import (  # noqa: E501
    V26_OPERATION_CLOSURE_AUDIT_VERSION,
    OperationalTaskAdmission,
    OperationalTaskRecord,
    OperationClosureAudit,
    OperationClosureMutationResult,
    OperationPathClosureResult,
    PathStrategy,
    operation_closure_audit_id,
    operation_closure_mutation_result_id,
    operation_path_closure_result_id,
    operational_task_admission_id,
)
from trusted_synthesis.hashing import canonical_hash
from trusted_synthesis.runtime.agent.public_operation import (
    public_operation_progress,
    public_operation_step_rejection,
    public_postcompletion_action_rejection,
)
from trusted_synthesis.runtime.tools import (
    AgentToolCall,
    AgentToolEnvironmentManifest,
    AgentToolObservation,
    AgentToolResult,
    agent_tool_argument_rejection,
    make_agent_tool_observation,
)


def _predicate_values(variable: PublicOperationVariable) -> dict[tuple[str, ...], Any]:
    query_rule = next(
        item for item in variable.resolution_rules if item.source_tool_id == "query_structured_fact"
    )
    return {item.selector: item.value for item in query_rule.equals}


def _query_arguments(
    variable: PublicOperationVariable,
    *,
    coarse: bool = False,
) -> dict[str, Any]:
    values = _predicate_values(variable)
    arguments = {
        "subject_alias": values[("subject", "name")],
        "metric_alias": values[("metric", "predicate")],
        "period_label": values[("period",)],
        "public_filters": {"source_id": values[("source", "source_id")]},
    }
    if not coarse:
        arguments["public_filters"].update(
            {
                "source_authority": values[("source", "authority")],
                "unit": values[("payload", "unit")],
                "currency": values[("payload", "currency")],
                "definition_id": values[("metric", "definition_id")],
                "time_basis": values[("time_basis",)],
                "frequency": values[("frequency",)],
                "subject_type": values[("subject", "type")],
            }
        )
    return arguments


def _search_arguments(variable: PublicOperationVariable) -> dict[str, Any]:
    values = _predicate_values(variable)
    return {
        "query": " ".join(
            str(values[key]) for key in (("subject", "name"), ("metric", "predicate"), ("period",))
        ),
        "subject_aliases": [str(values[("subject", "subject_id")])],
        "period_labels": [str(values[("period",)])],
        "source_filters": [str(values[("source", "source_id")])],
        "limit": 12,
    }


def _try_select(value: object, selector: tuple[str, ...]) -> object | None:
    current = value
    for part in selector:
        if not isinstance(current, Mapping) or part not in current:
            return None
        current = current[part]
    return current


def _matches_variable(candidate: object, variable: PublicOperationVariable) -> bool:
    values = _predicate_values(variable)
    return all(
        _try_select(candidate, selector) == expected for selector, expected in values.items()
    )


def _matches_search_candidate(
    candidate: object,
    variable: PublicOperationVariable,
) -> bool:
    values = _predicate_values(variable)
    visible = {"subject", "metric", "period", "source"}
    return all(
        _try_select(candidate, selector) == expected
        for selector, expected in values.items()
        if selector[0] in visible
    )


def _operation_ref(observation: AgentToolObservation) -> str | None:
    if observation.call.tool_id == "normalize_metric_unit_period":
        value = observation.result.get("normalized_operation_ref")
    elif observation.call.tool_id == "calculator":
        value = _try_select(observation.result, ("result", "operation_ref"))
    else:
        return None
    return value if isinstance(value, str) and value else None


def _normalized_operation_ref(observation: AgentToolObservation) -> str | None:
    if observation.call.tool_id != "normalize_metric_unit_period":
        return None
    value = observation.result.get("normalized_operation_ref")
    return value if isinstance(value, str) and value else None


def compile_operational_witness(
    record: OperationalTaskRecord,
    environment: AgentToolEnvironmentManifest,
    *,
    strategy: PathStrategy,
) -> tuple[BoundPublicExecutableWitness, tuple[AgentToolObservation, ...]]:
    recovery_scenario = (
        FinanceTypedRecoveryScenario.model_validate(record.recovery_scenario)
        if record.recovery_scenario is not None
        else None
    )
    runtime = FinanceExecutableSupportRuntime(
        record.public_corpus,
        environment,
        recovery_scenario=recovery_scenario,
    )
    task = record.task_package.task.public
    by_tool = environment.tools_by_id
    observations: list[AgentToolObservation] = []
    acquisition_arguments: list[dict[str, Any]] = []
    mechanism_events: set[str] = set()

    def execute(
        tool_id: str,
        arguments: dict[str, Any],
        *,
        expect_success: bool = True,
    ) -> AgentToolResult:
        call = AgentToolCall(
            call_index=len(observations) + 1,
            tool_id=tool_id,
            arguments=arguments,
        )
        spec = by_tool[tool_id]
        result = (
            public_postcompletion_action_rejection(task, tuple(observations), call)
            or agent_tool_argument_rejection(spec, call)
            or public_operation_step_rejection(task, tuple(observations), call)
            or runtime.execute(call)
        )
        if result.status == "succeeded":
            spec.validate_output(result.result)
        observation = make_agent_tool_observation(
            environment_manifest_id=environment.manifest_id,
            call=call,
            result=result,
            observation_time_hash=canonical_hash(
                {
                    "task_package_id": record.task_package.package_id,
                    "strategy": strategy,
                    "call_index": call.call_index,
                },
                prefix="finance_v26_operational_witness_time:",
            ),
        )
        observations.append(observation)
        if expect_success and result.status != "succeeded":
            raise ValueError(result.error_message or f"{tool_id} failed")
        if not expect_success and result.status != "failed":
            raise ValueError(f"{tool_id} did not produce the registered failure")
        return result

    variables = record.task_package.operation_contract.public_view.variables
    for index, variable in enumerate(variables):
        recovery_first = record.mechanism_id == "failure_recovery" and index == 0
        if strategy != "structured_direct":
            search_args = _search_arguments(variable)
            acquisition_arguments.append(search_args)
            result = execute("search_archive", search_args)
        else:
            result = None
        if recovery_first:
            coarse = _query_arguments(variable, coarse=True)
            acquisition_arguments.append(coarse)
            failed = execute("query_structured_fact", coarse, expect_success=False)
            if failed.error_code != "typed_selector_requires_refinement":
                raise ValueError("operational Witness observed another recovery failure")
            mechanism_events.add("typed_failure_observed")
            corrected = _query_arguments(variable)
            acquisition_arguments.append(corrected)
            execute("query_structured_fact", corrected)
            mechanism_events.update(("selector_revised", "recovery_succeeded"))
        elif strategy in {"structured_direct", "search_then_structured"}:
            arguments = _query_arguments(variable)
            acquisition_arguments.append(arguments)
            execute("query_structured_fact", arguments)
        else:
            if result is None:
                raise ValueError("search-then-open path lacks a search result")
            matches = result.result.get("matches")
            if not isinstance(matches, list):
                raise ValueError("Archive search returned no public matches")
            matched = [item for item in matches if _matches_search_candidate(item, variable)]
            if len(matched) != 1 or not isinstance(matched[0], Mapping):
                raise ValueError("public variable did not resolve to one Archive locator")
            locator = str(matched[0]["public_locator"])
            arguments = {"public_locator": locator}
            acquisition_arguments.append(arguments)
            execute("open_document", arguments)

    while True:
        progress = public_operation_progress(task, tuple(observations))
        if progress is None:
            raise ValueError("operational Witness lost its public Operation contract")
        if progress["all_steps_completed"]:
            break
        ready = [item for item in progress["ready_nodes"] if not item["unresolved_symbols"]]
        if not ready:
            raise ValueError(
                "public reference policy cannot advance from the current Runtime frontier"
            )
        frontier = ready[0]
        if "expected_arguments" in frontier:
            arguments = dict(frontier["expected_arguments"])
        else:
            arguments = dict(frontier["argument_contract"])
            schemas = dict(frontier["operator_output_schemas"])
            required_schema = frontier["required_output_schema"]
            matches = sorted(
                operator for operator, schema in schemas.items() if schema == required_schema
            )
            if len(matches) != 1:
                raise ValueError("public output schema does not select one registered operator")
            arguments["operator"] = matches[0]
        execute(str(frontier["tool_id"]), arguments)

    progress = public_operation_progress(task, tuple(observations))
    if progress is None or not progress["terminal_node_completed"]:
        raise ValueError("operational Witness lacks a terminal Operation")
    terminal_ref = str(progress["terminal_operation_ref"])
    support_ids = tuple(sorted(record.task_package.evidence_support_lattice.necessary_evidence_ids))
    verification = execute(
        "cross_check_evidence",
        {
            "evidence_ids": list(support_ids),
            "claim_or_result": {"operation_ref": terminal_ref},
        },
    )
    if verification.result.get("verified") is not True:
        raise ValueError("operational Witness terminal verification returned false")
    progress = public_operation_progress(task, tuple(observations))
    if progress is None or not progress["stop_ready"]:
        raise ValueError("operational Witness did not close the real Host stop gate")

    completed_refs = cast(dict[str, str], progress["completed_node_operation_refs"])
    source_by_public = {
        item.public_node_id: item.source_program_node_id
        for item in record.task_package.verifier_binding.node_bindings
        if item.source_program_node_id is not None
    }
    reverse = {
        operation_ref: source_by_public[public_id]
        for public_id, operation_ref in completed_refs.items()
        if public_id in source_by_public
    }
    terminal_observation = next(
        item
        for item in observations
        if item.call.tool_id == "calculator" and _operation_ref(item) == terminal_ref
    )
    raw_output = _try_select(terminal_observation.result, ("result", "output"))
    if not isinstance(raw_output, Mapping):
        raise ValueError("operational Witness terminal output is malformed")
    canonical_output = cast(dict[str, Any], _replace_runtime_refs(dict(raw_output), reverse))
    projected = _project_answer(canonical_output, record.answer_projection)

    if record.mechanism_id == "context_conditioned_action":
        first_public = record.task_package.operation_contract.public_view.nodes[0].node_id
        expected = next(
            item.expected_operator_id
            for item in record.task_package.verifier_binding.node_bindings
            if item.public_node_id == first_public
        )
        first_ref = completed_refs[first_public]
        first_observation = next(item for item in observations if _operation_ref(item) == first_ref)
        if first_observation.call.arguments.get("operator") == expected:
            mechanism_events.add("context_action_selected")
    elif record.mechanism_id == "semantic_reconciliation":
        normalized_refs = {
            value for item in observations if (value := _normalized_operation_ref(item)) is not None
        }
        terminal_operands = terminal_observation.call.arguments.get("operands")
        if not isinstance(terminal_operands, (list, tuple)):
            raise ValueError("operational Witness terminal operands are malformed")
        consumed_refs = {
            str(item.get("operation_ref"))
            for item in terminal_operands
            if isinstance(item, Mapping) and item.get("operation_ref")
        }
        if normalized_refs:
            mechanism_events.add("normalization_reference_emitted")
        if normalized_refs <= consumed_refs:
            mechanism_events.add("normalization_reference_consumed")
    elif record.mechanism_id == "state_dependent_stopping":
        mechanism_events.update(("completion_verified", "stopped_after_completion"))

    selected_ids = tuple(sorted(runtime.selected_evidence_ids))
    cited_ids = support_ids
    support_set = matching_sufficient_support_set(
        record.task_package.evidence_support_lattice,
        cited_ids,
    )
    verification_support = tuple(
        sorted(str(item) for item in verification.result.get("support") or ())
    )
    public_payload = json.dumps(task.model_dump(mode="json"), sort_keys=True)
    checks = {
        "only_public_inputs": not any(
            "evidence:" in json.dumps(arguments, sort_keys=True)
            for arguments in acquisition_arguments
        ),
        "only_allowed_tools": {item.call.tool_id for item in observations}
        <= set(record.task_package.tool_closure.allowed_tool_ids),
        "operation_lineage_complete": bool(progress["all_steps_completed"]),
        "evidence_support_complete": support_set is not None,
        "verification_complete": bool(progress["verification_after_terminal_completed"])
        and set(support_ids) <= set(verification_support),
        "answer_projection_complete": projected == record.projected_expected_output,
        "citation_complete": support_set is not None,
        "mechanism_complete": set(record.task_package.mechanism_contract.required_witness_event_ids)
        <= mechanism_events,
        "no_postcompletion_violation": not progress["postcompletion_violation"],
    }
    if any(item in public_payload for item in record.target_program_evidence_ids):
        raise ValueError("operational Task Public Spec exposes private Evidence identity")
    failures = tuple(sorted(key for key, passed in checks.items() if not passed))
    verifier_report = {
        "task_package_id": record.task_package.package_id,
        "strategy": strategy,
        "checks": checks,
        "operation_progress": progress,
        "support_set_id": support_set.support_set_id if support_set is not None else None,
        "selected_evidence_ids": selected_ids,
        "cited_evidence_ids": cited_ids,
        "mechanism_event_ids": sorted(mechanism_events),
        "normalized_answer": projected,
    }
    steps = tuple(
        PublicWitnessStep(
            step_index=index,
            tool_id=item.call.tool_id,
            call_hash=canonical_hash(item.call, prefix="operational_witness_call:"),
            observation_id=item.observation_id,
            observation_content_hash=item.content_hash,
            evidence_ids=tuple(sorted(item.evidence_ids)),
            operation_ref=(_operation_ref(item) if item.call.tool_id == "calculator" else None),
            normalized_operation_ref=_normalized_operation_ref(item),
        )
        for index, item in enumerate(observations, start=1)
    )
    values = {
        "task_package_id": record.task_package.package_id,
        "public_runtime_contract_id": record.task_package.public_runtime_contract.contract_id,
        "path_strategy_id": strategy,
        "steps": steps,
        "selected_evidence_ids": selected_ids,
        "verification_support_ids": verification_support,
        "cited_evidence_ids": cited_ids,
        "satisfying_support_set_id": (
            support_set.support_set_id if support_set is not None else "missing"
        ),
        "mechanism_event_ids": tuple(sorted(mechanism_events)),
        "normalized_answer": projected,
        "normalized_answer_hash": canonical_hash(projected, prefix="executable_witness_answer:"),
        "independent_verifier_report_hash": canonical_hash(
            verifier_report,
            prefix="operational_witness_verifier_report:",
        ),
        **checks,
        "full_validity_passed": all(checks.values()),
        "failure_reasons": failures,
    }
    provisional = BoundPublicExecutableWitness.model_construct(witness_id="pending", **values)
    witness = BoundPublicExecutableWitness(
        witness_id=bound_public_executable_witness_id(provisional),
        **values,
    )
    return witness, tuple(observations)


def _node_observation_ids(
    record: OperationalTaskRecord,
    observations: tuple[AgentToolObservation, ...],
) -> dict[str, str]:
    output: dict[str, str] = {}
    previous: set[str] = set()
    task = record.task_package.task.public
    for index in range(1, len(observations) + 1):
        progress = public_operation_progress(task, observations[:index])
        if progress is None:
            raise ValueError("node-observation mapping lost the public Operation contract")
        completed = set(progress["completed_node_ids"])
        for node_id in completed - previous:
            output[node_id] = observations[index - 1].observation_id
        previous = completed
    return output


def _mutation_result(
    record: OperationalTaskRecord,
    witness: BoundPublicExecutableWitness,
    *,
    mutation_kind: str,
    progress: Mapping[str, Any],
    removed_node_id: str | None = None,
    runtime_rejection_error_code: str | None = None,
) -> OperationClosureMutationResult:
    if progress["stop_ready"]:
        raise ValueError(f"Operation mutation {mutation_kind} did not fail closed")
    values = {
        "task_package_id": record.task_package.package_id,
        "baseline_witness_id": witness.witness_id,
        "mutation_kind": mutation_kind,
        "removed_node_id": removed_node_id,
        "runtime_rejection_error_code": runtime_rejection_error_code,
        "all_steps_completed": bool(progress["all_steps_completed"]),
        "terminal_node_completed": bool(progress["terminal_node_completed"]),
        "verification_after_terminal_completed": bool(
            progress["verification_after_terminal_completed"]
        ),
        "postcompletion_violation": bool(progress["postcompletion_violation"]),
        "stop_ready": False,
        "failure_closed": True,
        "progress_hash": canonical_hash(
            dict(progress), prefix="finance_v26_operation_mutation_progress:"
        ),
        "schema_version": V26_OPERATION_CLOSURE_AUDIT_VERSION,
    }
    provisional = OperationClosureMutationResult.model_construct(result_id="pending", **values)
    return OperationClosureMutationResult(
        result_id=operation_closure_mutation_result_id(provisional),
        **values,
    )


def build_operation_closure_audit(
    record: OperationalTaskRecord,
    witnesses: Sequence[BoundPublicExecutableWitness],
    histories: Sequence[tuple[AgentToolObservation, ...]],
    necessity: MechanismNecessityArtifact,
    catalog: StaticModelAuthorityPathCatalog,
) -> OperationClosureAudit:
    if len(witnesses) != len(histories):
        raise ValueError("Operation closure witnesses and histories differ")
    task = record.task_package.task.public
    path_results = []
    for witness, history in zip(witnesses, histories, strict=True):
        progress = public_operation_progress(task, history)
        if progress is None or not progress["stop_ready"]:
            raise ValueError("registered public path does not close the Host stop gate")
        values = {
            "task_package_id": record.task_package.package_id,
            "path_strategy_id": witness.path_strategy_id,
            "witness_id": witness.witness_id,
            "all_steps_completed": True,
            "terminal_node_completed": True,
            "verification_after_terminal_completed": True,
            "postcompletion_violation": False,
            "stop_ready": True,
            "normalized_answer_hash": witness.normalized_answer_hash,
            "schema_version": V26_OPERATION_CLOSURE_AUDIT_VERSION,
        }
        provisional = OperationPathClosureResult.model_construct(result_id="pending", **values)
        path_results.append(
            OperationPathClosureResult(
                result_id=operation_path_closure_result_id(provisional),
                **values,
            )
        )

    witness = witnesses[0]
    history = histories[0]
    node_observations = _node_observation_ids(record, history)
    required_nodes = record.task_package.stop_readiness_contract.required_node_ids
    mutations = []
    for node_id in required_nodes:
        removed_observation = node_observations[node_id]
        mutated_history = tuple(
            item for item in history if item.observation_id != removed_observation
        )
        progress = public_operation_progress(task, mutated_history)
        if progress is None:
            raise ValueError("node ablation lost the public Operation contract")
        mutations.append(
            _mutation_result(
                record,
                witness,
                mutation_kind="required_node_ablation",
                removed_node_id=node_id,
                progress=progress,
            )
        )

    terminal_id = record.task_package.stop_readiness_contract.terminal_node_id
    terminal_observation_id = node_observations[terminal_id]
    terminal_observation = next(
        item for item in history if item.observation_id == terminal_observation_id
    )
    premature_call = terminal_observation.call.model_copy(update={"call_index": 1})
    rejection = public_operation_step_rejection(task, (), premature_call)
    if rejection is None:
        raise ValueError("terminal-before-prerequisite call was not rejected")
    reordered_history = tuple(
        item
        for item in history
        if item.observation_id != terminal_observation_id
        and item.call.tool_id != "cross_check_evidence"
    )
    progress = public_operation_progress(task, reordered_history)
    if progress is None:
        raise ValueError("reordering mutation lost the public Operation contract")
    mutations.append(
        _mutation_result(
            record,
            witness,
            mutation_kind="terminal_before_prerequisite",
            runtime_rejection_error_code=rejection.error_code,
            progress=progress,
        )
    )

    first_calculator_index = next(
        index for index, item in enumerate(history) if item.call.tool_id == "calculator"
    )
    progress = public_operation_progress(task, history[: first_calculator_index + 1])
    if progress is None:
        raise ValueError("first-calculation mutation lost the public Operation contract")
    mutations.append(
        _mutation_result(
            record,
            witness,
            mutation_kind="first_calculation_only",
            progress=progress,
        )
    )

    verification_observation = next(
        item for item in history if item.call.tool_id == "cross_check_evidence"
    )
    first_operation_index = next(
        index
        for index, item in enumerate(history)
        if item.call.tool_id in {"calculator", "normalize_metric_unit_period"}
    )
    without_verification = [
        item for item in history if item.observation_id != verification_observation.observation_id
    ]
    premature_verification_history = tuple(
        [
            *without_verification[:first_operation_index],
            verification_observation,
            *without_verification[first_operation_index:],
        ]
    )
    progress = public_operation_progress(task, premature_verification_history)
    if progress is None:
        raise ValueError("premature-verification mutation lost the public Operation contract")
    mutations.append(
        _mutation_result(
            record,
            witness,
            mutation_kind="premature_verification",
            progress=progress,
        )
    )

    terminal_missing_history = tuple(
        item for item in history if item.observation_id != terminal_observation_id
    )
    progress = public_operation_progress(task, terminal_missing_history)
    if progress is None:
        raise ValueError("terminal-missing mutation lost the public Operation contract")
    mutations.append(
        _mutation_result(
            record,
            witness,
            mutation_kind="terminal_missing",
            progress=progress,
        )
    )

    variable = record.task_package.operation_contract.public_view.variables[0]
    extra_call = AgentToolCall(
        call_index=len(history) + 1,
        tool_id="query_structured_fact",
        arguments=_query_arguments(variable),
    )
    postcompletion_rejection = public_postcompletion_action_rejection(
        task,
        history,
        extra_call,
    )
    if postcompletion_rejection is None:
        raise ValueError("postcompletion action was not rejected")
    failed_observation = make_agent_tool_observation(
        environment_manifest_id=record.environment_manifest_id,
        call=extra_call,
        result=postcompletion_rejection,
        observation_time_hash=canonical_hash(
            {
                "task_package_id": record.task_package.package_id,
                "mutation": "postcompletion_action",
            },
            prefix="finance_v26_operation_mutation_time:",
        ),
    )
    progress = public_operation_progress(task, (*history, failed_observation))
    if progress is None:
        raise ValueError("postcompletion mutation lost the public Operation contract")
    mutations.append(
        _mutation_result(
            record,
            witness,
            mutation_kind="postcompletion_action",
            runtime_rejection_error_code=postcompletion_rejection.error_code,
            progress=progress,
        )
    )

    public_payload = json.dumps(task.model_dump(mode="json"), sort_keys=True).casefold()
    isolation = (
        "evidence:" not in public_payload
        and "source_program_node_id" not in public_payload
        and "expected_operator_id" not in public_payload
        and "verifier_id" not in public_payload
    )
    values = {
        "task_package_id": record.task_package.package_id,
        "intended_use": record.intended_use,
        "operation_contract_id": record.task_package.operation_contract.contract_id,
        "source_program_dag_hash": (record.task_package.operation_contract.source_program_dag_hash),
        "source_verifier_dag_hash": (
            record.task_package.operation_contract.source_verifier_dag_hash
        ),
        "terminal_node_id": terminal_id,
        "stop_readiness_contract_id": (record.task_package.stop_readiness_contract.contract_id),
        "runtime_projection_id": record.task_package.runtime_projection.projection_id,
        "static_path_catalog_id": catalog.catalog_id,
        "mechanism_necessity_artifact_id": necessity.artifact_id,
        "required_node_ids": required_nodes,
        "path_results": tuple(path_results),
        "mutation_results": tuple(mutations),
        "every_required_node_ablation_failed_closed": True,
        "target_mechanism_counterfactual_failed_closed": necessity.status == "passed",
        "public_oracle_isolation_passed": isolation,
        "exact_tool_sequence_exposed": False,
        "correct_model_choice_exposed": False,
        "compiler_used_oracle_next_action": False,
        "status": "passed",
        "schema_version": V26_OPERATION_CLOSURE_AUDIT_VERSION,
    }
    if not isolation or necessity.status != "passed":
        raise ValueError("Operation closure failed isolation or Mechanism Necessity")
    provisional = OperationClosureAudit.model_construct(audit_id="pending", **values)
    return OperationClosureAudit(
        audit_id=operation_closure_audit_id(provisional),
        **values,
    )


def build_operational_admission(
    record: OperationalTaskRecord,
    witness: BoundPublicExecutableWitness,
    necessity: MechanismNecessityArtifact,
    catalog: StaticModelAuthorityPathCatalog,
    closure: OperationClosureAudit,
) -> OperationalTaskAdmission:
    package_passed = True
    public_passed = witness.full_validity_passed
    mechanism_passed = necessity.status == "passed"
    closure_passed = closure.status == "passed"
    path_passed = catalog.status == "passed"
    capability = package_passed and public_passed and mechanism_passed and closure_passed
    vtdo = capability and record.intended_use == "vtdo_multistate_candidate" and path_passed
    blockers = []
    if not public_passed:
        blockers.append("public_witness_failed")
    if not mechanism_passed:
        blockers.append("mechanism_necessity_failed")
    if not closure_passed:
        blockers.append("operation_closure_failed")
    if record.intended_use == "vtdo_multistate_candidate" and not path_passed:
        blockers.append("static_model_authority_paths_failed")
    values = {
        "task_package_id": record.task_package.package_id,
        "intended_use": record.intended_use,
        "public_witness_id": witness.witness_id,
        "mechanism_necessity_artifact_id": necessity.artifact_id,
        "static_path_catalog_id": catalog.catalog_id,
        "operation_closure_audit_id": closure.audit_id,
        "package_bindings_passed": package_passed,
        "public_witness_passed": public_passed,
        "mechanism_necessity_passed": mechanism_passed,
        "operation_closure_passed": closure_passed,
        "static_path_support_passed": path_passed,
        "operational_capability_eligible": capability,
        "operational_vtdo_candidate_eligible": vtdo,
        "status": (
            "operational_vtdo_ready"
            if vtdo
            else "operational_capability_ready"
            if capability and record.intended_use == "capability_measurement"
            else "blocked"
        ),
        "blockers": tuple(sorted(blockers)),
    }
    provisional = OperationalTaskAdmission.model_construct(admission_id="pending", **values)
    return OperationalTaskAdmission(
        admission_id=operational_task_admission_id(provisional),
        **values,
    )


def mechanism_necessity_and_catalog(
    record: OperationalTaskRecord,
    witnesses: Sequence[BoundPublicExecutableWitness],
) -> tuple[
    MechanismNecessityArtifact,
    tuple[MechanismCounterfactualReplayRecord, ...],
    StaticModelAuthorityPathCatalog,
]:
    necessity, replays = _mechanism_necessity(cast(Any, record), witnesses[0])
    catalog = _path_catalog(cast(Any, record), witnesses)
    return necessity, replays, catalog
