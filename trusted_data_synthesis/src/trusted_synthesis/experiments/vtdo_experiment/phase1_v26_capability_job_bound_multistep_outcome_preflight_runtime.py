from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from itertools import product
from typing import Any, Final, cast

from trusted_synthesis.core.task.all_typed_rejection_public_feedback import (
    PublicCorrectionBoundTerminal,
    PublicTypedRejectionObservation,
)
from trusted_synthesis.core.task.capability_observation import (
    CapabilityFamily,
    ObservationDepth,
)
from trusted_synthesis.core.task.job_bound_multistep_outcome import (
    CapabilityDevelopmentJob,
    CapabilityDevelopmentJobManifest,
    ComponentAttemptOutcome,
    FrozenGenerationProfile,
    JobBoundOutcomePayload,
    JobBoundRunnerContract,
    ScriptedPreflightOutcomeRow,
    make_identity_model,
)
from trusted_synthesis.core.task.joint_presentation_receipt_hardening import (
    ActionAcceptanceReport,
    HardenedPublicObservation,
    HardenedPublicPrompt,
    StepRuntimeResult,
)
from trusted_synthesis.core.task.state_local_presentation_hardening import (
    StateLocalRankSchedule,
    classify_action_acceptance,
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
    phase1_v26_capability_executed_counterfactual_outcome_closure_runtime as v178_runtime,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_capability_job_bound_multistep_outcome_preflight_models as models,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_capability_validity_causal_reaudit_models as v171_models,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_capability_validity_causal_runtime as v171_runtime,
)
from trusted_synthesis.hashing import canonical_hash
from trusted_synthesis.runtime.agent.prospective_qualified_final_response_grammar import (
    QualifiedFinalResponseGrammar,
    compile_qualified_final_response_grammar,
    make_qualified_final_host_envelope,
    parse_qualified_final_response,
)
from trusted_synthesis.runtime.agent.prospective_semantic_action_response_grammar import (
    RESPONSE_PROTOCOL_VERSION,
    SemanticActionResponseGrammar,
    SemanticActionResponseRejection,
    compile_semantic_action_response_grammar,
    parse_exact_canonical_action_payload,
)

ACCEPTED_DOWNSTREAM_INVALID_PACKAGE_ARTIFACT_ID: Final = (
    "finance_v26_authoritative_parent_history_package_artifact:"
    "d080ecaa16e41fc35629e9262d7ae1a46f0642efbeafba1fa2a691e8ded8e52d"
)
ACCEPTED_DOWNSTREAM_INVALID_SOURCE_CHOICES: Final = (
    "public_choice:0750315e5bc16838f91be9809288a2b25cc7f761d88ecb6fb30ec3c0171bd189",
)


@dataclass(frozen=True)
class RuntimeCatalog:
    runner_by_id: Mapping[str, v176_models.AuthoritativeRunnerInputPackage]
    source_by_artifact: Mapping[str, v171_models.ValiditySeparatedCausalPackage]
    core_by_id: Mapping[str, Any]
    schedule_by_id: Mapping[str, StateLocalRankSchedule]


@dataclass(frozen=True)
class PreparedJob:
    job: CapabilityDevelopmentJob
    runner_package: v176_models.AuthoritativeRunnerInputPackage
    source: v171_models.ValiditySeparatedCausalPackage
    core: Any
    schedules: Mapping[str, StateLocalRankSchedule]
    execution_package_id: str
    source_package_artifact_id: str


@dataclass(frozen=True)
class CandidateDisposition:
    action_id: str
    source_choice_handle: str
    acceptance: ActionAcceptanceReport


@dataclass(frozen=True)
class ResponseSelection:
    action_id: str | None
    abi_valid: bool = True


FirstSelector = Callable[
    [step_runtime.StepRuntimeState, HardenedPublicPrompt, tuple[CandidateDisposition, ...], int],
    ResponseSelection,
]
CorrectionSelector = Callable[
    [
        step_runtime.StepRuntimeState,
        HardenedPublicPrompt,
        tuple[CandidateDisposition, ...],
        int,
        str,
    ],
    ResponseSelection,
]


@dataclass(frozen=True)
class TraceExecution:
    row: ScriptedPreflightOutcomeRow
    prompt_render_count: int
    step_call_count: int
    finalize_call_count: int
    action_abi_parse_count: int
    final_abi_parse_count: int
    later_prompt_after_terminal_count: int


@dataclass(frozen=True)
class RunnerProducts:
    denominator: models.ScriptedDenominatorPreflightAudit
    branches: models.RunnerBranchControlAudit


def runtime_catalog(predecessor: v177.PredecessorObjects) -> RuntimeCatalog:
    runners = {item.runner_package_id: item for item in predecessor.runner.packages}
    sources = {item.artifact_id: item for item in v177._v171_packages(predecessor.source)}
    cores = {item.core_id: item for item in predecessor.source.finance_cores}
    schedules = {item.schedule_id: item for item in predecessor.schedules.schedules}
    if len(runners) != 32 or len(sources) != 32:
        raise ValueError("v26.179 Runtime Catalog denominator changed")
    return RuntimeCatalog(
        runner_by_id=runners,
        source_by_artifact=sources,
        core_by_id=cores,
        schedule_by_id=schedules,
    )


def prepare_job(job: CapabilityDevelopmentJob, catalog: RuntimeCatalog) -> PreparedJob:
    runner = catalog.runner_by_id[job.runner_package_id]
    source = catalog.source_by_artifact[job.source_package_artifact_id]
    if (
        runner.package_id != job.execution_package_id
        or runner.source_v171_package_artifact_id != job.source_package_artifact_id
        or runner.source_package_id != job.source_package_id
        or runner.source_group_id != job.source_group_id
        or runner.finance_core_id != job.finance_core_id
        or runner.capability_family != job.capability_family
        or runner.depth != job.depth
        or runner.schedule_ids != job.schedule_ids
        or source.finance_core_id != job.finance_core_id
        or source.fixed_generation_condition_id != job.fixed_generation_condition_id
    ):
        raise ValueError("v26.179 Job crosses an authoritative Runner or source Package")
    ordered = topological_components(source.components)
    schedules = {
        component.component_key: catalog.schedule_by_id[schedule_id]
        for component, schedule_id in zip(ordered, job.schedule_ids, strict=True)
    }
    return PreparedJob(
        job=job,
        runner_package=runner,
        source=source,
        core=catalog.core_by_id[source.finance_core_id],
        schedules=schedules,
        execution_package_id=job.execution_package_id,
        source_package_artifact_id=job.source_package_artifact_id,
    )


def _runtime_input(context: PreparedJob) -> v171_runtime.RuntimeInput:
    return v171_runtime.RuntimeInput(
        package_id=context.source.package_id,
        capability_family=context.source.capability_family,
        public_task=context.source.public_task,
        components=context.source.components,
        finance_core=context.core,
    )


def _initialize(context: PreparedJob) -> step_runtime.StepRuntimeState:
    return step_runtime.initialize(
        _runtime_input(context),
        package_id=context.execution_package_id,
        replica_index=context.job.replica_index,
        schedules_by_component=context.schedules,
    )


def _candidate_dispositions(
    state: step_runtime.StepRuntimeState,
    prompt: HardenedPublicPrompt,
) -> tuple[CandidateDisposition, ...]:
    mapping = state.pending_source_by_display
    if mapping is None:
        raise ValueError("v26.179 Runner lost its display/source mapping")
    component = state.ordered_components[state.current_index]
    output: list[CandidateDisposition] = []
    for candidate in prompt.candidates:
        source_handle = mapping[candidate.choice_handle]
        output.append(
            CandidateDisposition(
                action_id=candidate.action_id,
                source_choice_handle=source_handle,
                acceptance=classify_action_acceptance(
                    package_id=state.package_id,
                    task=state.runtime_input.public_task,
                    component=component,
                    source_choice_handle=source_handle,
                    visible_failure_receipt=prompt.state.failure_receipt,
                    expected_failure_receipt=state.failure_receipts.get(component.component_key),
                ),
            )
        )
    return tuple(output)


def _reference_selection(
    state: step_runtime.StepRuntimeState,
    prompt: HardenedPublicPrompt,
    rows: tuple[CandidateDisposition, ...],
    _: int,
) -> ResponseSelection:
    del state, rows
    return ResponseSelection(action_id=public_only_select_hardened_action(prompt))


def _reference_correction(
    state: step_runtime.StepRuntimeState,
    prompt: HardenedPublicPrompt,
    rows: tuple[CandidateDisposition, ...],
    component_index: int,
    first_action_id: str,
) -> ResponseSelection:
    del first_action_id
    return _reference_selection(state, prompt, rows, component_index)


def _runner_prompt_hash(
    prompt: HardenedPublicPrompt,
    *,
    profile: FrozenGenerationProfile,
) -> str:
    return canonical_hash(
        {
            "public_prompt": prompt.model_dump(mode="json"),
            "response_abi": {
                "grammar_id": profile.action_grammar_id,
                "state_id": prompt.state.state_token,
                "decision_kind": profile.action_response_decision_kind,
                "protocol": RESPONSE_PROTOCOL_VERSION,
            },
        },
        prefix="capability_job_bound_current_runner_prompt:",
    )


def _parse_action_response(
    prompt: HardenedPublicPrompt,
    selection: ResponseSelection,
    *,
    grammar: SemanticActionResponseGrammar,
    profile: FrozenGenerationProfile,
) -> str | None:
    _runner_prompt_hash(prompt, profile=profile)
    if selection.abi_valid:
        if selection.action_id is None:
            raise ValueError("ABI-valid scripted response lacks an Action ID")
        payload: dict[str, Any] = {
            "state_id": prompt.state.state_token,
            "action_id": selection.action_id,
            "decision_kind": profile.action_response_decision_kind,
            "protocol": RESPONSE_PROTOCOL_VERSION,
        }
        proposal = parse_exact_canonical_action_payload(payload)
        if (
            proposal.state_id != prompt.state.state_token
            or proposal.action_id != selection.action_id
            or proposal.decision_kind != profile.action_response_decision_kind
            or grammar.grammar_id != profile.action_grammar_id
        ):
            raise ValueError("scripted Action response crosses its current Prompt ABI")
        return proposal.action_id
    malformed = {
        "state_id": prompt.state.state_token,
        "action_id": selection.action_id or "abi-invalid",
        "decision_kind": profile.action_response_decision_kind,
    }
    try:
        parse_exact_canonical_action_payload(malformed)
    except SemanticActionResponseRejection:
        return None
    raise ValueError("registered ABI-invalid response crossed the exact four-field Grammar")


def _parse_final_fixture(
    result: StepRuntimeResult,
    source: v171_models.ValiditySeparatedCausalPackage,
    *,
    grammar: QualifiedFinalResponseGrammar,
    profile: FrozenGenerationProfile,
) -> None:
    if grammar.grammar_id != profile.final_grammar_id:
        raise ValueError("scripted Final fixture crosses the frozen Final Grammar")
    terminal_state_id = canonical_hash(
        tuple(item.observation.receipt_id for item in result.steps),
        prefix="capability_job_bound_terminal_state:",
    )
    envelope = make_qualified_final_host_envelope(
        grammar=grammar,
        terminal_state_id=terminal_state_id,
        terminal_commit_id=result.result_id,
    )
    result_payload = result.projected_public_answer or {"preflight_status": "completed_invalid"}
    citations = result.public_citations or (
        source.public_task.semantic_task.records[0].record_handle,
    )
    payload = {
        "answer": {
            "result": result_payload,
            "citations": tuple({"evidence_id": item} for item in citations),
        },
        "rationale_summary": "credential-free scripted Runner preflight",
    }
    parse_qualified_final_response(payload, grammar=grammar, envelope=envelope)


def _attempt(values: dict[str, Any]) -> ComponentAttemptOutcome:
    return cast(
        ComponentAttemptOutcome,
        make_identity_model(
            ComponentAttemptOutcome,
            values,
            field="attempt_id",
            prefix="capability_component_attempt_outcome:",
        ),
    )


def _payload(
    *,
    attempts: Sequence[ComponentAttemptOutcome],
    result: StepRuntimeResult | None,
    final_abi_valid: bool | None,
) -> JobBoundOutcomePayload:
    attempt_tuple = tuple(attempts)
    first_failed = next(
        (item.component_key for item in attempt_tuple if not item.committed),
        None,
    )
    if result is not None and first_failed is None:
        first_failed = next(
            (
                item.component_key
                for item in attempt_tuple
                if not result.mechanism_qualification.component_semantic_checks.get(
                    item.component_key,
                    True,
                )
            ),
            None,
        )
    if result is None:
        terminal = attempt_tuple[-1]
        if not terminal.first_response_abi_valid:
            endpoint = "first_response_abi_invalid"
        elif terminal.correction_terminal_reason is not None:
            endpoint = terminal.correction_terminal_reason
        else:
            raise ValueError("terminal attempt lacks an exact endpoint kind")
        values: dict[str, Any] = {
            "component_attempts": attempt_tuple,
            "reached_component_count": len(attempt_tuple),
            "committed_component_count": sum(item.committed for item in attempt_tuple),
            "correction_count": sum(item.correction_invoked for item in attempt_tuple),
            "correction_feedback_ids": tuple(
                item.correction_feedback_id
                for item in attempt_tuple
                if item.correction_feedback_id is not None
            ),
            "first_failed_component_key": first_failed,
            "first_policy_qualified_valid": False,
            "bounded_policy_endpoint_complete": True,
            "task_verifier_invoked": False,
            "bounded_policy_qualified_valid": False,
            "endpoint_kind": endpoint,
        }
    else:
        final_base = result.task_validity.base_valid
        final_mechanism = result.mechanism_qualification.mechanism_semantically_qualified
        final_qualified = result.qualified_validity.qualified_valid
        correction_count = sum(item.correction_invoked for item in attempt_tuple)
        values = {
            "component_attempts": attempt_tuple,
            "reached_component_count": len(attempt_tuple),
            "committed_component_count": sum(item.committed for item in attempt_tuple),
            "correction_count": correction_count,
            "correction_feedback_ids": tuple(
                item.correction_feedback_id
                for item in attempt_tuple
                if item.correction_feedback_id is not None
            ),
            "first_failed_component_key": first_failed,
            "first_policy_qualified_valid": bool(final_qualified and correction_count == 0),
            "bounded_policy_endpoint_complete": True,
            "task_verifier_invoked": True,
            "final_response_abi_valid": final_abi_valid,
            "final_result_id": result.result_id,
            "final_base_valid": final_base,
            "final_mechanism_qualified": final_mechanism,
            "final_qualified_valid": final_qualified,
            "bounded_policy_qualified_valid": final_qualified,
            "endpoint_kind": ("completed_qualified" if final_qualified else "completed_invalid"),
        }
    return cast(
        JobBoundOutcomePayload,
        make_identity_model(
            JobBoundOutcomePayload,
            values,
            field="attempt_trace_id",
            prefix="capability_job_attempt_trace:",
        ),
    )


def _scripted_row(
    *,
    context: PreparedJob,
    manifest_id: str,
    scenario: str,
    exact_denominator: bool,
    outcome: JobBoundOutcomePayload,
) -> ScriptedPreflightOutcomeRow:
    exact = exact_denominator
    raw_namespace = context.job.raw_namespace
    result_namespace = context.job.result_namespace
    if not exact:
        raw_namespace = canonical_hash(
            {"job_raw_namespace": raw_namespace, "scenario": scenario},
            prefix="capability_scripted_control_raw_namespace:",
        )
        result_namespace = canonical_hash(
            {"job_result_namespace": result_namespace, "scenario": scenario},
            prefix="capability_scripted_control_result_namespace:",
        )
    values = {
        "job_id": context.job.job_id,
        "manifest_id": manifest_id,
        "execution_package_id": context.execution_package_id,
        "source_package_artifact_id": context.source_package_artifact_id,
        "replica_index": context.job.replica_index,
        "attempt_trace_id": outcome.attempt_trace_id,
        "raw_namespace": raw_namespace,
        "result_namespace": result_namespace,
        "scenario": scenario,
        "exact_manifest_denominator_member": exact,
        "outcome": outcome,
    }
    return cast(
        ScriptedPreflightOutcomeRow,
        make_identity_model(
            ScriptedPreflightOutcomeRow,
            values,
            field="row_id",
            prefix="capability_scripted_preflight_outcome_row:",
        ),
    )


def execute_trace(
    *,
    context: PreparedJob,
    manifest_id: str,
    scenario: str,
    profile: FrozenGenerationProfile,
    action_grammar: SemanticActionResponseGrammar,
    final_grammar: QualifiedFinalResponseGrammar,
    first_selector: FirstSelector = _reference_selection,
    correction_selector: CorrectionSelector = _reference_correction,
    exact_denominator: bool = False,
) -> TraceExecution:
    state = _initialize(context)
    attempts: list[ComponentAttemptOutcome] = []
    prompt_count = 0
    step_count = 0
    action_parse_count = 0
    later_prompt_count = 0
    result: StepRuntimeResult | None = None
    final_parse_count = 0
    while state.current_index < len(state.ordered_components):
        component_index = state.current_index
        component = state.ordered_components[component_index]
        prompt = step_runtime.render_next_prompt(state)
        prompt_count += 1
        rows = _candidate_dispositions(state, prompt)
        first = first_selector(state, prompt, rows, component_index)
        action_parse_count += 1
        first_action_id = _parse_action_response(
            prompt,
            first,
            grammar=action_grammar,
            profile=profile,
        )
        if first_action_id is None:
            attempts.append(
                _attempt(
                    {
                        "component_index": component_index,
                        "component_key": component.component_key,
                        "reached_state_token": prompt.state.state_token,
                        "first_response_abi_valid": False,
                        "first_action_acceptance_evaluable": False,
                        "first_action_accepted": False,
                        "correction_invoked": False,
                        "committed": False,
                        "terminal": True,
                    }
                )
            )
            break
        first_row = next(
            (item for item in rows if item.action_id == first_action_id),
            None,
        )
        if first_row is None:
            raise ValueError("ABI-valid first response references an absent current Action")
        first_output = step_runtime.step(state, first_action_id)
        step_count += 1
        if isinstance(first_output, HardenedPublicObservation):
            if not first_output.action_accepted or not first_row.acceptance.accepted:
                raise ValueError("accepted first Action disagrees with production acceptance")
            attempts.append(
                _attempt(
                    {
                        "component_index": component_index,
                        "component_key": component.component_key,
                        "reached_state_token": prompt.state.state_token,
                        "first_response_abi_valid": True,
                        "first_action_acceptance_evaluable": True,
                        "first_action_id": first_action_id,
                        "first_action_state_precondition_valid": (
                            first_row.acceptance.state_precondition_valid
                        ),
                        "first_action_accepted": True,
                        "first_observation_receipt_id": first_output.receipt_id,
                        "correction_invoked": False,
                        "committed": True,
                        "terminal": False,
                    }
                )
            )
            continue
        if not isinstance(first_output, PublicTypedRejectionObservation):
            raise ValueError("first current Action produced an unexpected Runtime object")
        if first_row.acceptance.accepted or first_row.acceptance.rejection_code is None:
            raise ValueError("typed first rejection disagrees with production acceptance")
        feedback = state.public_feedback_by_component[component.component_key][0]
        recovery_prompt = step_runtime.render_next_prompt(state)
        prompt_count += 1
        correction_rows = _candidate_dispositions(state, recovery_prompt)
        correction = correction_selector(
            state,
            recovery_prompt,
            correction_rows,
            component_index,
            first_action_id,
        )
        action_parse_count += 1
        corrected_action_id = _parse_action_response(
            recovery_prompt,
            correction,
            grammar=action_grammar,
            profile=profile,
        )
        if corrected_action_id is None:
            attempts.append(
                _attempt(
                    {
                        "component_index": component_index,
                        "component_key": component.component_key,
                        "reached_state_token": prompt.state.state_token,
                        "first_response_abi_valid": True,
                        "first_action_acceptance_evaluable": True,
                        "first_action_id": first_action_id,
                        "first_action_state_precondition_valid": False,
                        "first_action_accepted": False,
                        "first_rejection_code": first_row.acceptance.rejection_code,
                        "first_observation_receipt_id": (
                            first_output.public_observation_receipt_id
                        ),
                        "correction_invoked": True,
                        "correction_feedback_id": feedback.feedback_id,
                        "correction_response_abi_valid": False,
                        "corrected_action_acceptance_evaluable": False,
                        "corrected_action_accepted": False,
                        "correction_terminal_reason": "correction_response_abi_invalid",
                        "committed": False,
                        "terminal": True,
                    }
                )
            )
            break
        correction_row = next(
            (item for item in correction_rows if item.action_id == corrected_action_id),
            None,
        )
        corrected_output = step_runtime.step(state, corrected_action_id)
        step_count += 1
        if isinstance(corrected_output, HardenedPublicObservation):
            if correction_row is None or not correction_row.acceptance.accepted:
                raise ValueError("accepted correction lacks production acceptance")
            relation = (
                "reference"
                if correction_row.source_choice_handle == component.reference_choice_handle
                else "valid_nonreference"
            )
            attempts.append(
                _attempt(
                    {
                        "component_index": component_index,
                        "component_key": component.component_key,
                        "reached_state_token": prompt.state.state_token,
                        "first_response_abi_valid": True,
                        "first_action_acceptance_evaluable": True,
                        "first_action_id": first_action_id,
                        "first_action_state_precondition_valid": False,
                        "first_action_accepted": False,
                        "first_rejection_code": first_row.acceptance.rejection_code,
                        "first_observation_receipt_id": (
                            first_output.public_observation_receipt_id
                        ),
                        "correction_invoked": True,
                        "correction_feedback_id": feedback.feedback_id,
                        "correction_response_abi_valid": True,
                        "corrected_action_id": corrected_action_id,
                        "corrected_action_relation": relation,
                        "corrected_action_acceptance_evaluable": True,
                        "corrected_action_accepted": True,
                        "correction_observation_receipt_id": corrected_output.receipt_id,
                        "committed": True,
                        "terminal": False,
                    }
                )
            )
            continue
        if not isinstance(corrected_output, PublicCorrectionBoundTerminal):
            raise ValueError("failed correction did not emit the bounded terminal")
        relation_by_class = {
            "same_current_invalid": "same_current_invalid",
            "different_current_invalid": "different_current_invalid",
            "stale_action_id": "stale_action",
            "foreign_or_unbound_action_id": "foreign_or_unbound_action",
            "malformed_action_reference": "foreign_or_unbound_action",
        }
        relation = relation_by_class[corrected_output.second_response_class]
        typed = relation in {"same_current_invalid", "different_current_invalid"}
        correction_receipt = None
        if typed:
            observations = state.public_rejection_observations_by_component[component.component_key]
            correction_receipt = observations[-1].public_observation_receipt_id
        attempts.append(
            _attempt(
                {
                    "component_index": component_index,
                    "component_key": component.component_key,
                    "reached_state_token": prompt.state.state_token,
                    "first_response_abi_valid": True,
                    "first_action_acceptance_evaluable": True,
                    "first_action_id": first_action_id,
                    "first_action_state_precondition_valid": False,
                    "first_action_accepted": False,
                    "first_rejection_code": first_row.acceptance.rejection_code,
                    "first_observation_receipt_id": first_output.public_observation_receipt_id,
                    "correction_invoked": True,
                    "correction_feedback_id": feedback.feedback_id,
                    "correction_response_abi_valid": True,
                    "corrected_action_id": corrected_action_id,
                    "corrected_action_relation": relation,
                    "corrected_action_acceptance_evaluable": typed,
                    "corrected_action_accepted": False,
                    "correction_observation_receipt_id": correction_receipt,
                    "correction_terminal_reason": corrected_output.terminal_reason,
                    "committed": False,
                    "terminal": True,
                }
            )
        )
        try:
            step_runtime.render_next_prompt(state)
        except step_runtime.CorrectionBoundTerminalReached:
            later_prompt_count = 0
        else:
            later_prompt_count = 1
        break
    finalize_count = 0
    if (
        attempts
        and all(item.committed for item in attempts)
        and state.current_index == len(state.ordered_components)
    ):
        result = step_runtime.finalize(state)
        finalize_count = 1
        _parse_final_fixture(
            result,
            context.source,
            grammar=final_grammar,
            profile=profile,
        )
        final_parse_count = 1
    outcome = _payload(
        attempts=attempts,
        result=result,
        final_abi_valid=(True if result is not None else None),
    )
    row = _scripted_row(
        context=context,
        manifest_id=manifest_id,
        scenario=scenario,
        exact_denominator=exact_denominator,
        outcome=outcome,
    )
    return TraceExecution(
        row=row,
        prompt_render_count=prompt_count,
        step_call_count=step_count,
        finalize_call_count=finalize_count,
        action_abi_parse_count=action_parse_count,
        final_abi_parse_count=final_parse_count,
        later_prompt_after_terminal_count=later_prompt_count,
    )


def execute_scripted_denominator(
    *,
    manifest: CapabilityDevelopmentJobManifest,
    runner: JobBoundRunnerContract,
    predecessor: v177.PredecessorObjects,
    profile: FrozenGenerationProfile,
) -> models.ScriptedDenominatorPreflightAudit:
    action_grammar = compile_semantic_action_response_grammar()
    final_grammar = compile_qualified_final_response_grammar()
    catalog = runtime_catalog(predecessor)
    traces = tuple(
        execute_trace(
            context=prepare_job(job, catalog),
            manifest_id=manifest.manifest_id,
            scenario="exact_manifest_reference_preflight",
            profile=profile,
            action_grammar=action_grammar,
            final_grammar=final_grammar,
            exact_denominator=True,
        )
        for job in manifest.jobs
    )
    rows = tuple(item.row for item in traces)
    if tuple(sorted(item.job_id for item in rows)) != manifest.expected_job_ids:
        raise ValueError("scripted denominator differs from the exact Manifest Job set")
    values = {
        "runner_id": runner.runner_id,
        "manifest_id": manifest.manifest_id,
        "rows": rows,
        "exact_job_set_match_count": len(rows),
        "current_prompt_render_count": sum(item.prompt_render_count for item in traces),
        "action_abi_parse_count": sum(item.action_abi_parse_count for item in traces),
        "accepted_action_count": sum(item.outcome.committed_component_count for item in rows),
        "final_abi_parse_count": sum(item.final_abi_parse_count for item in traces),
        "finalized_runtime_result_count": sum(item.finalize_call_count for item in traces),
        "first_policy_qualified_control_count": sum(
            item.outcome.first_policy_qualified_valid for item in rows
        ),
        "bounded_policy_qualified_control_count": sum(
            item.outcome.bounded_policy_qualified_valid for item in rows
        ),
        "component_correction_count": sum(item.outcome.correction_count for item in rows),
    }
    return cast(
        models.ScriptedDenominatorPreflightAudit,
        models.make_identity_model(
            models.ScriptedDenominatorPreflightAudit,
            values,
            field="audit_id",
            prefix="finance_v26_scripted_192_job_denominator_preflight_audit:",
        ),
    )


@dataclass
class _PrefixAggregate:
    prefixes: set[tuple[str, ...]]
    state_tokens: set[str]
    signatures: set[str]
    candidate_evaluation_count: int = 0
    typed_rejection_count: int = 0


def _source_action(
    state: step_runtime.StepRuntimeState,
    prompt: HardenedPublicPrompt,
    source_choice_handle: str,
) -> str:
    mapping = state.pending_source_by_display or {}
    display = next(key for key, value in mapping.items() if value == source_choice_handle)
    return next(item.action_id for item in prompt.candidates if item.choice_handle == display)


def scan_all_accepted_prefixes(
    *,
    manifest: CapabilityDevelopmentJobManifest,
    predecessor: v177.PredecessorObjects,
) -> models.AcceptedPrefixSurfaceAudit:
    catalog = runtime_catalog(predecessor)
    job_by_package_replica = {
        (item.runner_package_id, item.replica_index): item for item in manifest.jobs
    }
    aggregates: dict[tuple[str, str, int], _PrefixAggregate] = {}
    combination_count = 0
    replica_execution_count = 0
    reached_count = 0
    accepted_count = 0
    typed_rejection_count = 0
    candidate_evaluation_count = 0
    for runner_package_id in sorted({item.runner_package_id for item in manifest.jobs}):
        context_zero = prepare_job(job_by_package_replica[(runner_package_id, 0)], catalog)
        ordered = topological_components(context_zero.source.components)
        vectors = tuple(
            cast(tuple[str, ...], tuple(items))
            for items in product(
                *(
                    tuple(choice.choice_handle for choice in component.public_state.choice_legend)
                    for component in ordered
                )
            )
        )
        combination_count += len(vectors)
        for selected in vectors:
            for replica_index in range(6):
                replica_execution_count += 1
                context = prepare_job(
                    job_by_package_replica[(runner_package_id, replica_index)],
                    catalog,
                )
                state = _initialize(context)
                accepted_prefix: list[str] = []
                for component_index, source_handle in enumerate(selected):
                    prompt = step_runtime.render_next_prompt(state)
                    rows = _candidate_dispositions(state, prompt)
                    key = (runner_package_id, ordered[component_index].component_key, replica_index)
                    aggregate = aggregates.setdefault(
                        key,
                        _PrefixAggregate(prefixes=set(), state_tokens=set(), signatures=set()),
                    )
                    signature_payload = tuple(
                        sorted(
                            (
                                item.source_choice_handle,
                                item.acceptance.accepted,
                                item.acceptance.rejection_code,
                            )
                            for item in rows
                        )
                    )
                    aggregate.prefixes.add(tuple(accepted_prefix))
                    aggregate.state_tokens.add(prompt.state.state_token)
                    aggregate.signatures.add(
                        canonical_hash(signature_payload, prefix="accepted_prefix_acceptance:")
                    )
                    aggregate.candidate_evaluation_count += len(rows)
                    local_rejections = sum(not item.acceptance.accepted for item in rows)
                    aggregate.typed_rejection_count += local_rejections
                    reached_count += 1
                    candidate_evaluation_count += len(rows)
                    typed_rejection_count += local_rejections
                    action_id = _source_action(state, prompt, source_handle)
                    output = step_runtime.step(state, action_id)
                    if isinstance(output, HardenedPublicObservation):
                        if not output.action_accepted:
                            raise ValueError("accepted-prefix scan received a failed Observation")
                        accepted_count += 1
                        accepted_prefix.append(source_handle)
                        continue
                    if not isinstance(output, PublicTypedRejectionObservation):
                        raise ValueError("accepted-prefix scan received an unexpected terminal")
                    break
    if combination_count != 772 or replica_execution_count != 4_632:
        raise ValueError("accepted-prefix declared combination denominator changed")
    rows = tuple(
        cast(
            models.AcceptedPrefixSurfaceRow,
            models.make_identity_model(
                models.AcceptedPrefixSurfaceRow,
                {
                    "runner_package_id": key[0],
                    "component_key": key[1],
                    "replica_index": key[2],
                    "accepted_prefix_count": len(value.prefixes),
                    "reached_state_token_count": len(value.state_tokens),
                    "acceptance_signature_count": len(value.signatures),
                    "candidate_evaluation_count": value.candidate_evaluation_count,
                    "typed_rejection_count": value.typed_rejection_count,
                },
                field="row_id",
                prefix="capability_accepted_prefix_surface_row:",
            ),
        )
        for key, value in sorted(aggregates.items())
    )
    values = {
        "rows": rows,
        "reached_prefix_state_count": reached_count,
        "candidate_evaluation_count": candidate_evaluation_count,
        "accepted_action_count": accepted_count,
        "typed_rejection_count": typed_rejection_count,
    }
    return cast(
        models.AcceptedPrefixSurfaceAudit,
        models.make_identity_model(
            models.AcceptedPrefixSurfaceAudit,
            values,
            field="audit_id",
            prefix="finance_v26_accepted_prefix_action_surface_audit:",
        ),
    )


def _invalid_first_on_components(component_keys: set[str]) -> FirstSelector:
    def select(
        state: step_runtime.StepRuntimeState,
        prompt: HardenedPublicPrompt,
        rows: tuple[CandidateDisposition, ...],
        component_index: int,
    ) -> ResponseSelection:
        del prompt, component_index
        component = state.ordered_components[state.current_index]
        if component.component_key in component_keys:
            rejected = tuple(item for item in rows if not item.acceptance.accepted)
            if not rejected:
                raise ValueError("registered correction Component lacks an invalid current Action")
            return ResponseSelection(rejected[0].action_id)
        reference = next(
            item for item in rows if item.source_choice_handle == component.reference_choice_handle
        )
        return ResponseSelection(reference.action_id)

    return select


def _valid_nonreference_correction(
    state: step_runtime.StepRuntimeState,
    prompt: HardenedPublicPrompt,
    rows: tuple[CandidateDisposition, ...],
    component_index: int,
    first_action_id: str,
) -> ResponseSelection:
    del prompt, component_index, first_action_id
    component = state.ordered_components[state.current_index]
    selected = next(
        item
        for item in rows
        if item.acceptance.accepted
        and item.source_choice_handle != component.reference_choice_handle
    )
    return ResponseSelection(selected.action_id)


def _same_invalid_correction(
    state: step_runtime.StepRuntimeState,
    prompt: HardenedPublicPrompt,
    rows: tuple[CandidateDisposition, ...],
    component_index: int,
    first_action_id: str,
) -> ResponseSelection:
    del state, prompt, rows, component_index
    return ResponseSelection(first_action_id)


def _different_invalid_correction(
    state: step_runtime.StepRuntimeState,
    prompt: HardenedPublicPrompt,
    rows: tuple[CandidateDisposition, ...],
    component_index: int,
    first_action_id: str,
) -> ResponseSelection:
    del state, prompt, component_index
    selected = next(
        item for item in rows if item.action_id != first_action_id and not item.acceptance.accepted
    )
    return ResponseSelection(selected.action_id)


def _stale_correction(
    state: step_runtime.StepRuntimeState,
    prompt: HardenedPublicPrompt,
    rows: tuple[CandidateDisposition, ...],
    component_index: int,
    first_action_id: str,
) -> ResponseSelection:
    del prompt, rows, component_index, first_action_id
    prior = sorted(state.seen_public_action_ids - state.current_public_action_ids)
    if not prior:
        raise ValueError("stale-Action control lacks a predecessor public Action")
    return ResponseSelection(prior[0])


def _foreign_correction(
    state: step_runtime.StepRuntimeState,
    prompt: HardenedPublicPrompt,
    rows: tuple[CandidateDisposition, ...],
    component_index: int,
    first_action_id: str,
) -> ResponseSelection:
    del prompt, rows, component_index, first_action_id
    nonce = 0
    while True:
        candidate = canonical_hash(
            {"package_id": state.package_id, "nonce": nonce},
            prefix="foreign_public_action_control:",
        ).split(":", 1)[1][:24]
        if candidate not in state.seen_public_action_ids:
            return ResponseSelection(candidate)
        nonce += 1


def _abi_invalid_first(
    state: step_runtime.StepRuntimeState,
    prompt: HardenedPublicPrompt,
    rows: tuple[CandidateDisposition, ...],
    component_index: int,
) -> ResponseSelection:
    del state, prompt, rows, component_index
    return ResponseSelection(action_id=None, abi_valid=False)


def _source_vector_selector(selected: tuple[str, ...]) -> FirstSelector:
    def select(
        state: step_runtime.StepRuntimeState,
        prompt: HardenedPublicPrompt,
        rows: tuple[CandidateDisposition, ...],
        component_index: int,
    ) -> ResponseSelection:
        del state, prompt
        target = selected[component_index]
        row = next(item for item in rows if item.source_choice_handle == target)
        return ResponseSelection(row.action_id)

    return select


def _two_invalid_component(
    component: CausalTargetComponent,
    task: Any,
) -> CausalTargetComponent:
    if component.public_state.decision_kind != "reconcile_record":
        raise ValueError("two-invalid diagnostic requires a Reconciliation Component")
    entries = list(component.public_state.choice_legend)
    targets = [
        index
        for index, item in enumerate(entries)
        if item.choice_handle != component.reference_choice_handle
    ]
    if len(targets) < 2:
        raise ValueError("two-invalid diagnostic requires two nonreference Choices")
    rules = tuple(item.rule_handle for item in task.semantic_task.resolution_rules)
    operations = tuple(item.operation_handle for item in task.semantic_task.operations)
    for ordinal, index in enumerate(targets[:2]):
        original = entries[index]
        arguments = dict(original.operation.arguments)
        replacements = tuple(
            ("rule_handle", item) for item in rules if item != str(arguments.get("rule_handle"))
        ) + tuple(
            ("operation_handle", item)
            for item in operations
            if item != str(arguments.get("operation_handle"))
        )
        if not replacements:
            raise ValueError("two-invalid diagnostic lacks a grounded mismatch")
        field_name, replacement = replacements[ordinal % len(replacements)]
        arguments[field_name] = replacement
        operation_payload = original.operation.model_dump(mode="python")
        operation_payload["arguments"] = arguments
        operation = type(original.operation).model_validate(operation_payload)
        entries[index] = choice_entry(operation)
    state_payload = component.public_state.model_dump(mode="python")
    state_payload["choice_legend"] = tuple(entries)
    public_state = CausalPublicDecisionState.model_validate(state_payload)
    component_payload = component.model_dump(mode="python", exclude={"component_id"})
    component_payload["public_state"] = public_state
    changed = cast(
        CausalTargetComponent,
        make_identity_model(
            CausalTargetComponent,
            component_payload,
            field="component_id",
            prefix="causal_public_target_component:",
        ),
    )
    if changed.component_id == component.component_id:
        raise ValueError("two-invalid diagnostic Component identity did not change")
    return changed


def _diagnostic_context(
    *,
    base: PreparedJob,
) -> PreparedJob:
    original = next(
        item
        for item in topological_components(base.source.components)
        if item.public_state.decision_kind == "reconcile_record"
        and len(item.public_state.choice_legend) >= 3
    )
    replacement = _two_invalid_component(original, base.source.public_task)
    source = v178_runtime._rematerialize_source_package(
        source=base.source,
        replacement=replacement,
        core=base.core,
    )
    schedules = v178_runtime._diagnostic_schedules(source)
    package_id = canonical_hash(
        {
            "base_job_id": base.job.job_id,
            "source_package_artifact_id": source.artifact_id,
            "component_id": replacement.component_id,
            "scope": "two_different_current_invalid_actions",
        },
        prefix="capability_job_bound_different_invalid_diagnostic_package:",
    )
    return PreparedJob(
        job=base.job,
        runner_package=base.runner_package,
        source=source,
        core=base.core,
        schedules=schedules,
        execution_package_id=package_id,
        source_package_artifact_id=source.artifact_id,
    )


def _branch_row(
    *,
    scenario: models.BranchScenario,
    scope: str,
    trace: TraceExecution,
) -> models.RunnerBranchControlRow:
    values = {
        "scenario": scenario,
        "source_scope": scope,
        "source_job_id": trace.row.job_id,
        "outcome": trace.row,
        "actual_prompt_render_count": trace.prompt_render_count,
        "actual_step_call_count": trace.step_call_count,
        "actual_finalize_call_count": trace.finalize_call_count,
        "later_prompt_after_terminal_count": trace.later_prompt_after_terminal_count,
    }
    return cast(
        models.RunnerBranchControlRow,
        models.make_identity_model(
            models.RunnerBranchControlRow,
            values,
            field="control_id",
            prefix="capability_job_bound_runner_branch_control:",
        ),
    )


def execute_branch_controls(
    *,
    manifest: CapabilityDevelopmentJobManifest,
    predecessor: v177.PredecessorObjects,
    profile: FrozenGenerationProfile,
) -> models.RunnerBranchControlAudit:
    catalog = runtime_catalog(predecessor)
    action_grammar = compile_semantic_action_response_grammar()
    final_grammar = compile_qualified_final_response_grammar()
    jobs = tuple(manifest.jobs)
    first_context = prepare_job(jobs[0], catalog)
    failure_jobs = tuple(
        item
        for item in jobs
        if item.capability_family == CapabilityFamily.FAILURE_RECOVERY and item.replica_index == 0
    )
    d0_job = next(
        item for item in failure_jobs if item.depth == ObservationDepth.D0_OBSERVABILITY_ANCHOR
    )
    d1_job = next(item for item in failure_jobs if item.depth == ObservationDepth.D1_BASIC)
    d3_job = next(item for item in failure_jobs if item.depth == ObservationDepth.D3_STRESS)
    d0 = prepare_job(d0_job, catalog)
    d1 = prepare_job(d1_job, catalog)
    d3 = prepare_job(d3_job, catalog)
    d0_key = topological_components(d0.source.components)[0].component_key
    d1_keys = tuple(item.component_key for item in topological_components(d1.source.components))
    d3_keys = tuple(item.component_key for item in topological_components(d3.source.components))
    if len(d3_keys) < 2:
        raise ValueError("two-Component correction control lacks a D3 component pair")
    accepted_job = next(
        item
        for item in jobs
        if item.authoritative_package_artifact_id == ACCEPTED_DOWNSTREAM_INVALID_PACKAGE_ARTIFACT_ID
        and item.replica_index == 0
    )
    accepted_context = prepare_job(accepted_job, catalog)
    diagnostic_base_job = next(
        item
        for item in jobs
        if item.capability_family == CapabilityFamily.SEMANTIC_RECONCILIATION
        and item.replica_index == 0
        and len(item.schedule_ids) == 1
    )
    diagnostic = _diagnostic_context(base=prepare_job(diagnostic_base_job, catalog))
    diagnostic_key = next(
        item.component_key
        for item in topological_components(diagnostic.source.components)
        if item.public_state.decision_kind == "reconcile_record"
    )

    def run(
        context: PreparedJob,
        scenario: models.BranchScenario,
        *,
        first_selector: FirstSelector = _reference_selection,
        correction_selector: CorrectionSelector = _reference_correction,
    ) -> TraceExecution:
        return execute_trace(
            context=context,
            manifest_id=manifest.manifest_id,
            scenario=scenario,
            profile=profile,
            action_grammar=action_grammar,
            final_grammar=final_grammar,
            first_selector=first_selector,
            correction_selector=correction_selector,
        )

    traces: list[tuple[models.BranchScenario, str, TraceExecution]] = []
    traces.append(
        (
            "direct_first_attempt_qualified",
            "exact_manifest",
            run(first_context, "direct_first_attempt_qualified"),
        )
    )
    traces.append(
        (
            "abi_invalid_first_response",
            "exact_manifest",
            run(first_context, "abi_invalid_first_response", first_selector=_abi_invalid_first),
        )
    )
    traces.append(
        (
            "accepted_first_action_downstream_task_invalid",
            "exact_manifest",
            run(
                accepted_context,
                "accepted_first_action_downstream_task_invalid",
                first_selector=_source_vector_selector(ACCEPTED_DOWNSTREAM_INVALID_SOURCE_CHOICES),
            ),
        )
    )
    traces.append(
        (
            "one_component_correction",
            "exact_manifest",
            run(
                d0,
                "one_component_correction",
                first_selector=_invalid_first_on_components({d0_key}),
            ),
        )
    )
    traces.append(
        (
            "two_component_corrections",
            "exact_manifest",
            run(
                d3,
                "two_component_corrections",
                first_selector=_invalid_first_on_components(set(d3_keys[:2])),
            ),
        )
    )
    traces.append(
        (
            "valid_nonreference_correction",
            "exact_manifest",
            run(
                d0,
                "valid_nonreference_correction",
                first_selector=_invalid_first_on_components({d0_key}),
                correction_selector=_valid_nonreference_correction,
            ),
        )
    )
    traces.append(
        (
            "same_current_invalid_second_response",
            "exact_manifest",
            run(
                d0,
                "same_current_invalid_second_response",
                first_selector=_invalid_first_on_components({d0_key}),
                correction_selector=_same_invalid_correction,
            ),
        )
    )
    traces.append(
        (
            "different_current_invalid_second_response",
            "canonical_diagnostic",
            run(
                diagnostic,
                "different_current_invalid_second_response",
                first_selector=_invalid_first_on_components({diagnostic_key}),
                correction_selector=_different_invalid_correction,
            ),
        )
    )
    traces.append(
        (
            "stale_action_second_response",
            "exact_manifest",
            run(
                d1,
                "stale_action_second_response",
                first_selector=_invalid_first_on_components({d1_keys[-1]}),
                correction_selector=_stale_correction,
            ),
        )
    )
    traces.append(
        (
            "foreign_action_second_response",
            "exact_manifest",
            run(
                d0,
                "foreign_action_second_response",
                first_selector=_invalid_first_on_components({d0_key}),
                correction_selector=_foreign_correction,
            ),
        )
    )
    traces.append(
        (
            "correction_terminal_forbids_third_prompt",
            "exact_manifest",
            run(
                d0,
                "correction_terminal_forbids_third_prompt",
                first_selector=_invalid_first_on_components({d0_key}),
                correction_selector=_same_invalid_correction,
            ),
        )
    )
    rows = tuple(
        _branch_row(scenario=scenario, scope=scope, trace=trace)
        for scenario, scope, trace in traces
    )
    by_scenario = {item.scenario: item for item in rows}
    if not by_scenario[
        "direct_first_attempt_qualified"
    ].outcome.outcome.first_policy_qualified_valid:
        raise ValueError("direct first-attempt control did not finish Qualified")
    abi = by_scenario["abi_invalid_first_response"].outcome.outcome
    if abi.task_verifier_invoked or abi.bounded_policy_qualified_valid:
        raise ValueError("ABI-invalid first response reached Action or Verifier success")
    downstream = by_scenario["accepted_first_action_downstream_task_invalid"].outcome.outcome
    if downstream.correction_count or downstream.bounded_policy_qualified_valid:
        raise ValueError("accepted downstream-invalid control has the wrong terminal")
    if by_scenario["one_component_correction"].outcome.outcome.correction_count != 1:
        raise ValueError("one-Component correction control count changed")
    if by_scenario["two_component_corrections"].outcome.outcome.correction_count != 2:
        raise ValueError("two-Component correction control count changed")
    if not by_scenario[
        "valid_nonreference_correction"
    ].outcome.outcome.bounded_policy_qualified_valid:
        raise ValueError("valid nonreference correction did not preserve Qualified validity")
    terminal_scenarios: set[models.BranchScenario] = {
        "same_current_invalid_second_response",
        "different_current_invalid_second_response",
        "stale_action_second_response",
        "foreign_action_second_response",
    }
    if any(
        by_scenario[item].outcome.outcome.task_verifier_invoked
        or by_scenario[item].outcome.outcome.bounded_policy_qualified_valid
        for item in terminal_scenarios
    ):
        raise ValueError("invalid second-response control escaped its typed terminal")
    if by_scenario["correction_terminal_forbids_third_prompt"].later_prompt_after_terminal_count:
        raise ValueError("bounded correction terminal exposed a third Prompt")
    return cast(
        models.RunnerBranchControlAudit,
        models.make_identity_model(
            models.RunnerBranchControlAudit,
            {"rows": rows},
            field="audit_id",
            prefix="finance_v26_job_bound_runner_branch_control_audit:",
        ),
    )


def execute_runner_preflight(
    *,
    manifest: CapabilityDevelopmentJobManifest,
    runner: JobBoundRunnerContract,
    predecessor: v177.PredecessorObjects,
    profile: FrozenGenerationProfile,
) -> RunnerProducts:
    denominator = execute_scripted_denominator(
        manifest=manifest,
        runner=runner,
        predecessor=predecessor,
        profile=profile,
    )
    branches = execute_branch_controls(
        manifest=manifest,
        predecessor=predecessor,
        profile=profile,
    )
    return RunnerProducts(denominator=denominator, branches=branches)


__all__ = [
    "RunnerProducts",
    "RuntimeCatalog",
    "TraceExecution",
    "execute_branch_controls",
    "execute_runner_preflight",
    "execute_scripted_denominator",
    "execute_trace",
    "prepare_job",
    "runtime_catalog",
    "scan_all_accepted_prefixes",
]
