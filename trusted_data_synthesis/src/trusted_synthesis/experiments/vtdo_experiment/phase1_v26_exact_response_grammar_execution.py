from __future__ import annotations

from pathlib import Path
from typing import Any, Final, cast

from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_two_stage_semantic_proposal_execution as legacy,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_exact_response_grammar_rematerialization import (  # noqa: E501
    ExactGrammarRematerializationReport,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_two_stage_profile_and_manifest_preflight import (  # noqa: E501
    TwoStageExecutionContract,
    TwoStageManifest,
    TwoStagePathAudit,
    TwoStageTaskPackage,
)
from trusted_synthesis.runtime.agent.compact_budget_prompt import render_compact_final_prompt
from trusted_synthesis.runtime.agent.prospective_action_constructibility import (
    PublicActionState,
    build_public_action_state,
    compile_semantic_decision,
)
from trusted_synthesis.runtime.agent.prospective_thinking_completion import (
    CompletionProjection,
)
from trusted_synthesis.runtime.agent.prospective_two_stage_exact_response_grammar import (
    ExactResponseModelRejection,
    StageOneResponseGrammarArtifact,
    parse_exact_semantic_proposal_payload,
    render_exact_semantic_proposal_prompt,
    render_exact_semantic_proposal_rescue_prompt,
)
from trusted_synthesis.runtime.agent.prospective_two_stage_semantic_proposal import (
    ModelResultRejection,
    parse_final_answer_payload,
    semantic_proposal_signature,
)

RUNNER_RUN_ID: Final = "finance_v26_113_exact_response_grammar_runner_preflight_v1_20260823"
EXECUTION_RUN_ID: Final = "finance_v26_114_exact_response_grammar_calibration_execution_v1_20260823"
V26_112_DIR: Final = (
    "artifacts/vtdo_experiment/finance_v26_112_exact_response_grammar_rematerialization_v1_20260823"
)
EXPECTED_V26_112_REPORT_ID: Final = (
    "finance_v26_exact_grammar_rematerialization_report:"
    "88b4a2cac6d43e46d52a45a0af7956787b78805893daf86af2ac01abde5e2f8f"
)
EXPECTED_V26_112_CONTRACT_ID: Final = (
    "finance_v26_two_stage_execution_contract:"
    "a162af1661dd51e253cf77dff5628a73df1c92e2d335cc6aeadc000dfc952329"
)
EXPECTED_V26_112_MANIFEST_ID: Final = (
    "finance_v26_two_stage_manifest:"
    "3b9377e0d41e9af761df93a2009402c6ac3f7efa84d41695f7b192dc85d67416"
)
EXPECTED_RESPONSE_GRAMMAR_ID: Final = (
    "prospective_stage_one_response_grammar:"
    "641ea2e9b4391cc46026f7b0d187ba5f7a674fe28e271a4b58e37aeed87a6b52"
)


def load_exact_grammar_static_inputs(
    package_root: Path, implementation_root: Path
) -> tuple[legacy.TwoStageStaticInputs, StageOneResponseGrammarArtifact]:
    root = implementation_root / V26_112_DIR
    report = ExactGrammarRematerializationReport.model_validate(
        legacy.load_canonical_json(root / "report.json")
    )
    contract = TwoStageExecutionContract.model_validate(
        legacy.load_canonical_json(root / "two_stage_execution_contract.json")
    )
    manifest = TwoStageManifest.model_validate(
        legacy.load_canonical_json(root / "two_stage_job_manifest.json")
    )
    grammar = StageOneResponseGrammarArtifact.model_validate(
        legacy.load_canonical_json(root / "stage_one_response_grammar.json")
    )
    tasks = cast(
        tuple[TwoStageTaskPackage, ...],
        legacy._load_models(root / "two_stage_task_packages.json", TwoStageTaskPackage),
    )
    paths = cast(
        tuple[TwoStagePathAudit, ...],
        legacy._load_models(root / "two_stage_path_audits.json", TwoStagePathAudit),
    )
    predecessor = legacy.load_two_stage_static_inputs(package_root, package_root)
    if (
        report.report_id != EXPECTED_V26_112_REPORT_ID
        or contract.contract_id != EXPECTED_V26_112_CONTRACT_ID
        or manifest.manifest_id != EXPECTED_V26_112_MANIFEST_ID
        or grammar.grammar_id != EXPECTED_RESPONSE_GRAMMAR_ID
        or report.response_grammar_id != grammar.grammar_id
        or report.execution_contract_id != contract.contract_id
        or report.manifest_id != manifest.manifest_id
        or manifest.contract_id != contract.contract_id
        or report.next_permitted_stage != "exact_response_grammar_runner_preflight_only"
        or report.execution_authorized
        or any(item.compact_prompt_contract_id != grammar.grammar_id for item in tasks)
    ):
        raise ValueError("v26.113 exact-Grammar static predecessor binding changed")
    static = legacy.TwoStageStaticInputs(
        report=predecessor.report,
        predecessor_contract=contract,
        manifest=manifest,
        resource=predecessor.resource,
        stage_one=predecessor.stage_one,
        stage_two=predecessor.stage_two,
        tasks=tasks,
        paths=paths,
        agent_model_config=predecessor.agent_model_config,
        historical=predecessor.historical,
    )
    for job in manifest.jobs:
        legacy.two_stage_runtime_binding(static, job)
    return static, grammar


def make_exact_grammar_runner_contract(
    static: legacy.TwoStageStaticInputs,
) -> legacy.TwoStageRunnerContract:
    values: dict[str, Any] = {
        "predecessor_static_contract_id": static.predecessor_contract.contract_id,
        "predecessor_manifest_id": static.manifest.manifest_id,
        "stage_one_profile_id": static.stage_one.profile_id,
        "stage_two_profile_id": static.stage_two.profile_id,
        "resource_contract_id": static.resource.contract_id,
        "runner_run_id": RUNNER_RUN_ID,
        "execution_run_id": EXECUTION_RUN_ID,
    }
    provisional = legacy.TwoStageRunnerContract.model_construct(contract_id="pending", **values)
    return legacy.TwoStageRunnerContract(
        contract_id=legacy.two_stage_runner_contract_id(provisional), **values
    )


def _invoke_exact_attempt(
    ledger: legacy.JournaledStageOneClient,
    *,
    logical_request_index: int,
    request_kind: legacy.StageOneRequestKind,
    phase: legacy.StageOneAttemptPhase,
    primary_prompt: str,
    prompt: str,
    state: PublicActionState | None,
    rescue_available_before: bool,
) -> legacy._AttemptOutcome:
    prepared = ledger.prepare(
        logical_request_index=logical_request_index,
        request_kind=request_kind,
        phase=phase,
        primary_prompt=primary_prompt,
        prompt=prompt,
        public_state_id=state.state_id if state is not None else None,
        rescue_available_before=rescue_available_before,
    )
    before = ledger.provider_call_count
    try:
        payload, _ = ledger.invoke(prepared)
    except legacy.BudgetNoCallError as exc:
        return legacy._AttemptOutcome(
            attempt=legacy._make_attempt(
                prepared=prepared,
                provider_call_index=None,
                disposition="typed_budget_no_call",
                response_payload_present=False,
                error=str(exc),
            )
        )
    except legacy.InstrumentContractError as exc:
        index = before if ledger.provider_call_count > before else None
        return legacy._AttemptOutcome(
            attempt=legacy._make_attempt(
                prepared=prepared,
                provider_call_index=index,
                disposition="instrument_failure",
                response_payload_present=False,
                error=str(exc),
            )
        )
    except legacy.LLMClientError as exc:
        index = before if ledger.provider_call_count > before else None
        failure_type = (
            exc.failure_artifact.failure_type
            if isinstance(exc.failure_artifact, legacy.ProspectiveThinkingFailureArtifact)
            else type(exc).__name__
        )
        disposition: legacy.AttemptDisposition = (
            "completion_failure"
            if exc.telemetry and all(item.http_success for item in exc.telemetry)
            else "provider_transport_failure"
        )
        return legacy._AttemptOutcome(
            attempt=legacy._make_attempt(
                prepared=prepared,
                provider_call_index=index,
                disposition=disposition,
                response_payload_present=False,
                completion_failure_type=failure_type,
                error=str(exc),
            )
        )
    try:
        if request_kind == "semantic_proposal":
            if state is None:
                raise ValueError("semantic Proposal parsing lacks a public state")
            proposal = parse_exact_semantic_proposal_payload(payload, expected_state=state)
            attempt = legacy._make_attempt(
                prepared=prepared,
                provider_call_index=before,
                disposition="usable",
                response_payload_present=True,
            )
            return legacy._AttemptOutcome(attempt=attempt, payload=payload, proposal=proposal)
        answer = parse_final_answer_payload(payload)
        attempt = legacy._make_attempt(
            prepared=prepared,
            provider_call_index=before,
            disposition="usable",
            response_payload_present=True,
        )
        return legacy._AttemptOutcome(attempt=attempt, payload=payload, answer=answer)
    except (ExactResponseModelRejection, ModelResultRejection) as exc:
        return legacy._AttemptOutcome(
            attempt=legacy._make_attempt(
                prepared=prepared,
                provider_call_index=before,
                disposition="model_result_failure",
                response_payload_present=True,
                classification=exc.classification,
                error=str(exc),
            ),
            payload=payload,
        )


def _active_exact_outcome(
    ledger: legacy.JournaledStageOneClient,
    *,
    attempts: list[legacy.StageOneAttempt],
    logical_request_index: int,
    request_kind: legacy.StageOneRequestKind,
    primary_prompt: str,
    state: PublicActionState | None,
    rescue_used: bool,
) -> tuple[legacy._AttemptOutcome, bool]:
    primary = _invoke_exact_attempt(
        ledger,
        logical_request_index=logical_request_index,
        request_kind=request_kind,
        phase="primary",
        primary_prompt=primary_prompt,
        prompt=primary_prompt,
        state=state,
        rescue_available_before=not rescue_used,
    )
    attempts.append(primary.attempt)
    if not rescue_used and legacy._rescue_allowed(primary.attempt):
        rescue_used = True
        family = (
            primary.attempt.model_failure_classification.family
            if primary.attempt.model_failure_classification is not None
            else "channel_parse_failure"
        )
        subtype = (
            primary.attempt.model_failure_classification.subtype
            if primary.attempt.model_failure_classification is not None
            else str(primary.attempt.completion_failure_type or "completion_failure")
        )
        if request_kind == "semantic_proposal":
            rescue_prompt = render_exact_semantic_proposal_rescue_prompt(
                primary_prompt, failure_family=family, failure_subtype=subtype
            )
        else:
            rescue_prompt = legacy.render_semantically_sufficient_final_rescue_prompt(
                primary_prompt, failure_type=subtype
            )
        rescue = _invoke_exact_attempt(
            ledger,
            logical_request_index=logical_request_index,
            request_kind=request_kind,
            phase="rescue",
            primary_prompt=primary_prompt,
            prompt=rescue_prompt,
            state=state,
            rescue_available_before=False,
        )
        attempts.append(rescue.attempt)
        return rescue, rescue_used
    return primary, rescue_used


def execute_exact_grammar_job_raw(
    *,
    job: legacy.TwoStageJob,
    runner_contract: legacy.TwoStageRunnerContract,
    static: legacy.TwoStageStaticInputs,
    binding: legacy.RuntimeBinding,
    client: legacy.StageOneClient | None,
    output_dir: Path,
) -> legacy.TwoStageRawExecution:
    raw_path = legacy.raw_execution_path(output_dir, job)
    if raw_path.exists():
        raw = legacy.TwoStageRawExecution.model_validate(legacy.load_canonical_json(raw_path))
        if raw.runner_contract_id != runner_contract.contract_id or raw.job != job:
            raise ValueError("v26.113 Raw recovery crosses frozen identities")
        for descriptor in raw.provider_call_artifacts:
            path = output_dir / descriptor.relative_path
            if not path.is_file() or legacy.sha256_file(path) != descriptor.sha256:
                raise ValueError("v26.113 Raw recovery Provider bytes changed")
            legacy.RawStageOneProviderCall.model_validate(legacy.load_canonical_json(path))
        return raw
    provider_dir = legacy.raw_provider_path(output_dir, job, 0).parent
    if provider_dir.exists() and any(provider_dir.glob("call_*.json")):
        raise ValueError("orphan v26.113 Provider Artifacts forbid retry")
    if client is None:
        raise ValueError("pending v26.113 fixture Job has no Stage 1 client")
    if (
        job.contract_id != static.predecessor_contract.contract_id
        or job.task_package_id not in {item.task_package_id for item in static.tasks}
        or job.path_audit_id not in {item.path_audit_id for item in static.paths}
    ):
        raise ValueError("v26.113 Job differs from its exact static identity chain")
    ledger = legacy.JournaledStageOneClient(
        client,
        runner_contract=runner_contract,
        resource_contract=static.resource,
        job=job,
        output_dir=output_dir,
    )
    runtime = legacy._runtime(binding.record, binding.environment)
    observations: list[legacy.AgentToolObservation] = []
    attempts: list[legacy.StageOneAttempt] = []
    commits: list[legacy.StageTwoCommitRecord] = []
    failed_signatures: set[str] = set()
    rescue_used = False
    condition = (
        None
        if binding.source_registered_path.role == "capability"
        else binding.source_registered_path.path_strategy_id
    )
    terminal: legacy.TerminalDisposition = "model_result"
    failure_type: str | None = None
    error: str | None = None
    completed: legacy.TwoStageCompletedResult | None = None
    logical_index = 0
    for _ in range(static.resource.maximum_primary_stage_one_requests - 1):
        state = build_public_action_state(
            binding.record.task_package.task.public,
            binding.environment,
            tuple(observations),
        )
        prompt = render_exact_semantic_proposal_prompt(
            instruction=binding.record.task_package.task.public.instruction,
            state=state,
            public_path_condition=condition,
        )
        outcome, rescue_used = _active_exact_outcome(
            ledger,
            attempts=attempts,
            logical_request_index=logical_index,
            request_kind="semantic_proposal",
            primary_prompt=prompt,
            state=state,
            rescue_used=rescue_used,
        )
        logical_index += 1
        if outcome.attempt.disposition != "usable" or outcome.proposal is None:
            terminal = legacy._terminal_from_attempt(outcome.attempt)
            classification = outcome.attempt.model_failure_classification
            failure_type = (
                classification.subtype
                if classification is not None
                else outcome.attempt.completion_failure_type or outcome.attempt.disposition
            )
            error = outcome.attempt.error
            break
        proposal = outcome.proposal
        signature = semantic_proposal_signature(proposal)
        if signature in failed_signatures:
            terminal = "model_result"
            failure_type = "duplicate_failed_semantic_proposal"
            error = "model repeated a semantic proposal with a typed failure"
            break
        try:
            commit = compile_semantic_decision(state, proposal, call_index=len(observations) + 1)
        except ValueError as exc:
            terminal = "model_result"
            failure_type = "semantic_compile_rejection"
            error = str(exc)
            break
        commit_values: dict[str, Any] = {
            "logical_request_index": logical_index - 1,
            "public_state_id": state.state_id,
            "proposal": proposal,
            "commit": commit,
            "stage_two_profile_id": static.stage_two.profile_id,
            "provider_calls_before_commit": ledger.provider_call_count,
        }
        provisional_commit = legacy.StageTwoCommitRecord.model_construct(
            record_id="pending", **commit_values
        )
        commits.append(
            legacy.StageTwoCommitRecord(
                record_id=legacy.stage_two_commit_record_id(provisional_commit),
                **commit_values,
            )
        )
        if commit.action == "emit_final":
            break
        if commit.call is None:
            raise ValueError("v26.113 tool Commit lacks its public call")
        observation = legacy._execute_observation(
            record=binding.record,
            environment=binding.environment,
            runtime=runtime,
            observations=tuple(observations),
            projection=CompletionProjection(
                request_kind="decision",
                action="call_tool",
                tool_id=commit.call.tool_id,
                arguments=commit.call.arguments,
            ),
        )
        observations.append(observation)
        if observation.status == "failed":
            failed_signatures.add(signature)
    else:
        terminal = "model_result"
        failure_type = "stage_one_primary_request_limit_exhausted"
        error = "model did not reach final Commit within the frozen request limit"
    if (
        commits
        and commits[-1].commit.action == "emit_final"
        and terminal == "model_result"
        and failure_type is None
    ):
        final_prompt = render_compact_final_prompt(
            binding.prompt_contract.public_context,
            binding.record.task_package.task.public,
            tuple(observations),
            public_path_condition=condition,
        )
        outcome, rescue_used = _active_exact_outcome(
            ledger,
            attempts=attempts,
            logical_request_index=logical_index,
            request_kind="final_answer",
            primary_prompt=final_prompt,
            state=None,
            rescue_used=rescue_used,
        )
        if outcome.attempt.disposition == "usable" and outcome.answer is not None:
            citations = legacy._selected_evidence_ids(observations)
            if not citations:
                terminal = "model_result"
                failure_type = "final_answer_without_public_evidence"
                error = "final answer has no selected public Evidence"
            else:
                result_values: dict[str, Any] = {
                    "job_id": job.job_id,
                    "answer": outcome.answer,
                    "cited_evidence_ids": citations,
                    "final_attempt_id": outcome.attempt.attempt_id,
                }
                provisional = legacy.TwoStageCompletedResult.model_construct(
                    result_id="pending", **result_values
                )
                completed = legacy.TwoStageCompletedResult(
                    result_id=legacy.two_stage_completed_result_id(provisional),
                    **result_values,
                )
                terminal = "completed"
        else:
            terminal = legacy._terminal_from_attempt(outcome.attempt)
            classification = outcome.attempt.model_failure_classification
            failure_type = (
                classification.subtype
                if classification is not None
                else outcome.attempt.completion_failure_type or outcome.attempt.disposition
            )
            error = outcome.attempt.error
    if ledger.instrument_failures:
        terminal = "instrument_failure"
        failure_type = "provider_usage_or_binding_contract_failure"
        error = ";".join(ledger.instrument_failures)
        completed = None
    return legacy._finish_raw(
        runner_contract=runner_contract,
        job=job,
        binding=binding,
        ledger=ledger,
        attempts=attempts,
        commits=commits,
        observations=observations,
        completed=completed,
        terminal=terminal,
        failure_type=failure_type,
        error=error,
        output_dir=output_dir,
    )
