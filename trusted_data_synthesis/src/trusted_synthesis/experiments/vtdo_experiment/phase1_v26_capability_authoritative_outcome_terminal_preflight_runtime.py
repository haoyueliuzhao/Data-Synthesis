from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, cast

from pydantic import ValidationError

from trusted_synthesis.core.task.authoritative_job_bound_outcome import (
    AuthoritativeCapabilityOutcomeRow,
    AuthoritativeTerminalRegistry,
    ComponentAttemptEvidence,
    EvidenceKind,
    FailureLocus,
    JobBoundAttemptTrace,
    JobResultDescriptor,
    JobResultEvidencePayload,
    RawExecutionDescriptor,
    RawExecutionEvidencePayload,
    TerminalKind,
    expected_provider_artifact_ids,
    expected_raw_artifact_path,
    expected_result_artifact_path,
    expected_transport_artifact_ids,
    make_identity_model,
)
from trusted_synthesis.core.task.job_bound_multistep_outcome import (
    CapabilityDevelopmentJob,
    CapabilityDevelopmentJobManifest,
    ComponentAttemptOutcome,
    JobBoundOutcomePayload,
    JobBoundRunnerContract,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_capability_job_bound_multistep_outcome_preflight_runtime as v179_runtime,
)
from trusted_synthesis.hashing import canonical_hash
from trusted_synthesis.runtime.agent.prospective_qualified_final_response_grammar import (
    QualifiedFinalResponseGrammar,
    make_qualified_final_host_envelope,
    parse_qualified_final_response,
)


@dataclass(frozen=True)
class AuthoritativeEvidenceBundle:
    raw: RawExecutionDescriptor
    result: JobResultDescriptor
    trace: JobBoundAttemptTrace
    row: AuthoritativeCapabilityOutcomeRow


@dataclass(frozen=True)
class FinalParserSemanticResult:
    parser_rejected: bool
    escaped_exception_phase: str
    exception_type: str
    exception_message: str
    parser_input_hash: str
    parser_invocation_count: int


ExactFinalParser = Callable[..., Any]


def _attempt(values: dict[str, Any]) -> ComponentAttemptEvidence:
    return cast(
        ComponentAttemptEvidence,
        make_identity_model(
            ComponentAttemptEvidence,
            values,
            field="attempt_id",
            prefix="capability_authoritative_component_attempt:",
        ),
    )


def project_v179_attempt(source: ComponentAttemptOutcome) -> ComponentAttemptEvidence:
    first_reference_valid = None
    if source.first_response_abi_valid:
        first_reference_valid = source.first_action_acceptance_evaluable
    corrected_reference_valid = None
    if source.correction_response_abi_valid:
        corrected_reference_valid = source.corrected_action_acceptance_evaluable
    terminal_kind: TerminalKind | None = None
    if source.terminal:
        if not source.first_response_abi_valid:
            terminal_kind = "first_response_abi_invalid"
        elif source.correction_terminal_reason == "correction_response_abi_invalid":
            terminal_kind = "correction_response_abi_invalid"
        elif source.correction_terminal_reason == "correction_attempt_typed_invalid":
            terminal_kind = "correction_attempt_typed_invalid"
        elif source.correction_terminal_reason == "correction_action_reference_invalid":
            terminal_kind = "correction_action_reference_invalid"
        else:
            raise ValueError("v26.179 terminal attempt lacks a v26.181 terminal mapping")
    values = {
        "component_index": source.component_index,
        "component_key": source.component_key,
        "reached_state_token": source.reached_state_token,
        "first_response_abi_valid": source.first_response_abi_valid,
        "first_action_reference_valid": first_reference_valid,
        "first_action_state_precondition_valid": (source.first_action_state_precondition_valid),
        "first_action_accepted": (
            source.first_action_accepted if source.first_response_abi_valid else None
        ),
        "correction_invoked": source.correction_invoked,
        "correction_response_abi_valid": source.correction_response_abi_valid,
        "corrected_action_reference_valid": corrected_reference_valid,
        "corrected_action_state_precondition_valid": (
            source.corrected_action_accepted
            if source.corrected_action_acceptance_evaluable
            else None
        ),
        "corrected_action_accepted": source.corrected_action_accepted,
        "committed": source.committed,
        "terminal": source.terminal,
        "terminal_kind": terminal_kind,
    }
    return _attempt(values)


def _generic_component_attempt(
    *,
    job: CapabilityDevelopmentJob,
    terminal_kind: TerminalKind,
    state_token: str,
    component_key: str,
) -> ComponentAttemptEvidence:
    base: dict[str, Any] = {
        "component_index": 0,
        "component_key": component_key,
        "reached_state_token": state_token,
        "correction_invoked": False,
        "committed": False,
        "terminal": True,
        "terminal_kind": terminal_kind,
    }
    if terminal_kind == "first_response_abi_invalid":
        base.update(first_response_abi_valid=False)
    elif terminal_kind == "first_action_reference_invalid":
        base.update(
            first_response_abi_valid=True,
            first_action_reference_valid=False,
            first_action_accepted=False,
        )
    elif terminal_kind in {
        "correction_response_abi_invalid",
        "correction_action_reference_invalid",
        "correction_attempt_typed_invalid",
    }:
        base.update(
            first_response_abi_valid=True,
            first_action_reference_valid=True,
            first_action_state_precondition_valid=False,
            first_action_accepted=False,
            correction_invoked=True,
        )
        if terminal_kind == "correction_response_abi_invalid":
            base.update(correction_response_abi_valid=False)
        elif terminal_kind == "correction_action_reference_invalid":
            base.update(
                correction_response_abi_valid=True,
                corrected_action_reference_valid=False,
                corrected_action_accepted=False,
            )
        else:
            base.update(
                correction_response_abi_valid=True,
                corrected_action_reference_valid=True,
                corrected_action_state_precondition_valid=False,
                corrected_action_accepted=False,
            )
    elif terminal_kind == "measurement_support_exit":
        base.update(
            first_response_abi_valid=True,
            first_action_reference_valid=True,
            first_action_state_precondition_valid=True,
            first_action_accepted=True,
        )
    else:
        raise ValueError(f"terminal is not Component-local:{job.job_id}:{terminal_kind}")
    return _attempt(base)


def _terminal_failure_stage(terminal_kind: TerminalKind) -> tuple[str, str, bool]:
    mapping: dict[str, tuple[str, str, bool]] = {
        "completed_invalid": ("base_answer", "completed_base_invalid", False),
        "first_response_abi_invalid": ("action_abi", "first_response_abi_invalid", True),
        "correction_response_abi_invalid": (
            "action_abi",
            "correction_response_abi_invalid",
            True,
        ),
        "first_action_reference_invalid": (
            "action_reference",
            "first_action_reference_invalid",
            True,
        ),
        "correction_action_reference_invalid": (
            "action_reference",
            "correction_action_reference_invalid",
            True,
        ),
        "correction_attempt_typed_invalid": (
            "state_precondition",
            "correction_attempt_typed_invalid",
            True,
        ),
        "final_response_abi_invalid": ("final_abi", "final_response_abi_invalid", False),
        "provider_failure_no_payload": ("provider", "provider_failure_no_payload", False),
        "provider_transport_failure": ("transport", "provider_transport_failure", False),
        "privacy_rejection": ("privacy", "privacy_rejection", False),
        "resource_budget_exhausted": ("resource", "resource_budget_exhausted", False),
        "instrument_failure": ("instrument", "instrument_failure", False),
        "provider_identity_failure": ("model_identity", "provider_identity_failure", False),
        "thinking_integrity_failure": ("thinking", "thinking_integrity_failure", False),
        "usage_integrity_failure": ("usage", "usage_integrity_failure", False),
        "policy_horizon_exhausted": ("policy", "policy_horizon_exhausted", False),
        "measurement_support_exit": (
            "operation_support",
            "measurement_support_exit",
            True,
        ),
    }
    return mapping[terminal_kind]


def _row_locus_values(loci: tuple[FailureLocus, ...]) -> dict[str, str | None]:
    runtime_stages = {
        "action_abi",
        "action_reference",
        "state_precondition",
        "operation_support",
    }
    return {
        "first_runtime_uncommitted_locus_id": next(
            (item.locus_id for item in loci if item.stage in runtime_stages),
            None,
        ),
        "first_base_invalid_locus_id": next(
            (item.locus_id for item in loci if item.stage in {"base_answer", "base_citation"}),
            None,
        ),
        "first_mechanism_failed_locus_id": next(
            (item.locus_id for item in loci if item.stage == "mechanism"),
            None,
        ),
        "terminal_locus_id": loci[-1].locus_id if loci else None,
    }


def build_authoritative_bundle(
    *,
    job: CapabilityDevelopmentJob,
    manifest: CapabilityDevelopmentJobManifest,
    runner: JobBoundRunnerContract,
    registry: AuthoritativeTerminalRegistry,
    terminal_kind: TerminalKind,
    evidence_kind: EvidenceKind,
    source_outcome: JobBoundOutcomePayload | None = None,
    final_parser_result: FinalParserSemanticResult | None = None,
    state_token: str | None = None,
    component_key: str | None = None,
) -> AuthoritativeEvidenceBundle:
    policy = next(item for item in registry.policies if item.terminal_kind == terminal_kind)
    if source_outcome is not None:
        attempts = tuple(project_v179_attempt(item) for item in source_outcome.component_attempts)
    elif terminal_kind in {
        "first_response_abi_invalid",
        "correction_response_abi_invalid",
        "first_action_reference_invalid",
        "correction_action_reference_invalid",
        "correction_attempt_typed_invalid",
        "measurement_support_exit",
    }:
        attempts = (
            _generic_component_attempt(
                job=job,
                terminal_kind=terminal_kind,
                state_token=state_token
                or canonical_hash(
                    {"job_id": job.job_id, "terminal_kind": terminal_kind},
                    prefix="capability_authoritative_terminal_state:",
                ).split(":", 1)[1][:24],
                component_key=component_key or f"fixture:{job.execution_package_id}",
            ),
        )
    elif terminal_kind in {
        "completed_qualified",
        "completed_invalid",
        "final_response_abi_invalid",
    }:
        raise ValueError(f"terminal fixture requires a completed source Outcome:{terminal_kind}")
    else:
        attempts = ()
    parser_hash = None
    parser_rejected = None
    if terminal_kind == "final_response_abi_invalid":
        if final_parser_result is None:
            raise ValueError("Final-ABI-invalid bundle lacks semantic parser evidence")
        if not (
            final_parser_result.parser_rejected
            and final_parser_result.escaped_exception_phase == "final_parser"
            and final_parser_result.exception_type == "ValidationError"
        ):
            raise ValueError("Final parser evidence is not the exact semantic rejection")
        parser_hash = final_parser_result.parser_input_hash
        parser_rejected = True
    raw_payload = cast(
        RawExecutionEvidencePayload,
        make_identity_model(
            RawExecutionEvidencePayload,
            {
                "job_id": job.job_id,
                "terminal_kind": terminal_kind,
                "component_attempts": attempts,
                "provider_artifact_ids": expected_provider_artifact_ids(job, terminal_kind),
                "transport_artifact_ids": expected_transport_artifact_ids(job, terminal_kind),
                "terminal_evidence_id": canonical_hash(
                    {
                        "job_id": job.job_id,
                        "terminal_kind": terminal_kind,
                        "source_trace_id": (
                            source_outcome.attempt_trace_id if source_outcome is not None else None
                        ),
                    },
                    prefix="capability_authoritative_terminal_evidence:",
                ),
                "final_parser_input_hash": parser_hash,
                "final_parser_rejected": parser_rejected,
            },
            field="payload_id",
            prefix="capability_authoritative_raw_execution_payload:",
        ),
    )
    raw = cast(
        RawExecutionDescriptor,
        make_identity_model(
            RawExecutionDescriptor,
            {
                "evidence_kind": evidence_kind,
                "job_id": job.job_id,
                "manifest_id": manifest.manifest_id,
                "runner_id": runner.runner_id,
                "execution_package_id": job.execution_package_id,
                "source_package_artifact_id": job.source_package_artifact_id,
                "replica_index": job.replica_index,
                "raw_namespace": job.raw_namespace,
                "raw_artifact_path": expected_raw_artifact_path(job),
                "payload": raw_payload,
            },
            field="raw_execution_id",
            prefix="capability_authoritative_raw_execution_descriptor:",
        ),
    )
    loci: tuple[FailureLocus, ...] = ()
    if terminal_kind != "completed_qualified":
        stage, reason, component_local = _terminal_failure_stage(terminal_kind)
        locus_specs = [(stage, reason, component_local)]
        if terminal_kind == "completed_invalid":
            locus_specs.append(("mechanism", "completed_mechanism_unqualified", True))
        built_loci: list[FailureLocus] = []
        for locus_stage, locus_reason, locus_component_local in locus_specs:
            component = attempts[-1].component_key if locus_component_local and attempts else None
            attempt_index = len(attempts) - 1 if component is not None else None
            built_loci.append(
                cast(
                    FailureLocus,
                    make_identity_model(
                        FailureLocus,
                        {
                            "stage": locus_stage,
                            "component_key": component,
                            "attempt_index": attempt_index,
                            "reason_code": locus_reason,
                            "evaluability": (
                                "evaluated_false"
                                if policy.expected_qualified_validity is False
                                else "unevaluable"
                            ),
                            "source_descriptor_id": raw.raw_execution_id,
                        },
                        field="locus_id",
                        prefix="capability_authoritative_failure_locus:",
                    ),
                )
            )
        loci = tuple(built_loci)
    final_result_id = None
    if terminal_kind in {"completed_qualified", "completed_invalid"}:
        final_result_id = (
            source_outcome.final_result_id
            if source_outcome is not None
            else canonical_hash(
                {"job_id": job.job_id, "terminal_kind": terminal_kind},
                prefix="capability_authoritative_final_result_fixture:",
            )
        )
    result_payload = cast(
        JobResultEvidencePayload,
        make_identity_model(
            JobResultEvidencePayload,
            {
                "job_id": job.job_id,
                "raw_execution_id": raw.raw_execution_id,
                "terminal_kind": terminal_kind,
                "task_completion": policy.expected_task_completion,
                "task_verifier_invoked": policy.expected_task_verifier_invoked,
                "final_result_id": final_result_id,
                "final_base_valid": policy.expected_base_validity,
                "final_mechanism_qualified": policy.expected_mechanism_qualification,
                "final_qualified_valid": policy.expected_qualified_validity,
                "failure_locus_ids": tuple(item.locus_id for item in loci),
            },
            field="payload_id",
            prefix="capability_authoritative_job_result_payload:",
        ),
    )
    result = cast(
        JobResultDescriptor,
        make_identity_model(
            JobResultDescriptor,
            {
                "evidence_kind": evidence_kind,
                "job_id": job.job_id,
                "raw_execution_id": raw.raw_execution_id,
                "result_namespace": job.result_namespace,
                "result_artifact_path": expected_result_artifact_path(job),
                "payload": result_payload,
            },
            field="result_id",
            prefix="capability_authoritative_job_result_descriptor:",
        ),
    )
    trace = cast(
        JobBoundAttemptTrace,
        make_identity_model(
            JobBoundAttemptTrace,
            {
                "evidence_kind": evidence_kind,
                "job_id": job.job_id,
                "raw_execution_id": raw.raw_execution_id,
                "result_id": result.result_id,
                "terminal_kind": terminal_kind,
                "component_attempts": attempts,
                "failure_loci": loci,
                "correction_count": sum(item.correction_invoked for item in attempts),
            },
            field="trace_id",
            prefix="capability_authoritative_job_bound_attempt_trace:",
        ),
    )
    row_values: dict[str, Any] = {
        "evidence_kind": evidence_kind,
        "job_id": job.job_id,
        "manifest_id": manifest.manifest_id,
        "runner_id": runner.runner_id,
        "execution_package_id": job.execution_package_id,
        "source_package_artifact_id": job.source_package_artifact_id,
        "replica_index": job.replica_index,
        "raw_namespace": job.raw_namespace,
        "result_namespace": job.result_namespace,
        "raw_execution_id": raw.raw_execution_id,
        "result_id": result.result_id,
        "trace_id": trace.trace_id,
        "terminal_kind": terminal_kind,
        "correction_count": trace.correction_count,
        "first_policy_qualified_valid": bool(
            policy.expected_qualified_validity is True and trace.correction_count == 0
        ),
        "bounded_policy_qualified_valid": policy.expected_qualified_validity is True,
        "task_completion": policy.expected_task_completion,
        "task_verifier_invoked": policy.expected_task_verifier_invoked,
        "final_result_id": final_result_id,
        "final_base_valid": policy.expected_base_validity,
        "final_mechanism_qualified": policy.expected_mechanism_qualification,
        "final_qualified_valid": policy.expected_qualified_validity,
        **_row_locus_values(loci),
    }
    row = cast(
        AuthoritativeCapabilityOutcomeRow,
        make_identity_model(
            AuthoritativeCapabilityOutcomeRow,
            row_values,
            field="row_id",
            prefix="capability_authoritative_outcome_row:",
        ),
    )
    return AuthoritativeEvidenceBundle(raw=raw, result=result, trace=trace, row=row)


def evaluate_malformed_final_parser(
    *,
    grammar: QualifiedFinalResponseGrammar,
    parser: ExactFinalParser = parse_qualified_final_response,
    escaped_exception_phase: str = "final_parser",
) -> FinalParserSemanticResult:
    terminal_state_id = canonical_hash(
        {"control": "v26.181-malformed-final"},
        prefix="capability_authoritative_terminal_state:",
    )
    terminal_commit_id = canonical_hash(
        {"control": "v26.181-malformed-final"},
        prefix="capability_authoritative_terminal_commit:",
    )
    envelope = make_qualified_final_host_envelope(
        grammar=grammar,
        terminal_state_id=terminal_state_id,
        terminal_commit_id=terminal_commit_id,
    )
    malformed: dict[str, Any] = {}
    parser_input_hash = canonical_hash(
        {
            "grammar_id": grammar.grammar_id,
            "terminal_state_id": terminal_state_id,
            "terminal_commit_id": terminal_commit_id,
            "payload": malformed,
        },
        prefix="capability_authoritative_final_parser_input:",
    )
    parser_invocation_count = 1
    try:
        parser(malformed, grammar=grammar, envelope=envelope)
    except ValidationError as exc:
        error = exc
    except Exception as exc:
        raise ValueError("malformed Final did not fail at the exact Final parser boundary") from exc
    else:
        raise AssertionError("malformed Final was accepted by the exact Final parser")
    message = str(error)
    if "Final response requires exactly answer and rationale_summary" not in message:
        raise ValueError("Final parser ValidationError lacks the exact malformed-payload reason")
    if escaped_exception_phase != "final_parser":
        raise ValueError("Final parser rejection was relabeled to a later exception phase")
    return FinalParserSemanticResult(
        parser_rejected=True,
        escaped_exception_phase=escaped_exception_phase,
        exception_type=type(error).__name__,
        exception_message=message,
        parser_input_hash=parser_input_hash,
        parser_invocation_count=parser_invocation_count,
    )


def select_unknown_first_action(
    *,
    state: Any,
    candidate_action_ids: tuple[str, ...],
) -> str:
    nonce = 0
    current = set(candidate_action_ids)
    while True:
        candidate = canonical_hash(
            {"package_id": state.package_id, "nonce": nonce},
            prefix="capability_authoritative_unknown_first_action:",
        ).split(":", 1)[1][:24]
        if candidate not in current and candidate not in state.seen_public_action_ids:
            return candidate
        nonce += 1


def prepare_unknown_first_action_control(
    *,
    context: v179_runtime.PreparedJob,
) -> tuple[str, str, str]:
    state = v179_runtime._initialize(context)
    component = state.ordered_components[state.current_index]
    prompt = v179_runtime.step_runtime.render_next_prompt(state)
    rows = v179_runtime._candidate_dispositions(state, prompt)
    unknown = select_unknown_first_action(
        state=state,
        candidate_action_ids=tuple(item.action_id for item in rows),
    )
    if unknown in {item.action_id for item in rows}:
        raise ValueError("unknown-first-Action control selected a current Candidate")
    return unknown, prompt.state.state_token, component.component_key


__all__ = [
    "AuthoritativeEvidenceBundle",
    "FinalParserSemanticResult",
    "build_authoritative_bundle",
    "evaluate_malformed_final_parser",
    "prepare_unknown_first_action_control",
    "project_v179_attempt",
    "select_unknown_first_action",
]
