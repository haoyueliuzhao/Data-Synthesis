# ruff: noqa: E501
from __future__ import annotations

import copy
import hashlib
import inspect
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from pydantic import BaseModel

from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_capability_all_typed_rejection_public_feedback_runtime as step_runtime,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_capability_job_bound_multistep_outcome_preflight_runtime as frozen_runtime,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_repaired_full_condition_exact_online_execution_authorization_models as v211_models,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_repaired_full_condition_final_request_contract_continuity_repair_preflight as v209,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_repaired_full_condition_final_request_contract_continuity_repair_preflight_models as v209_models,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_repaired_full_condition_online_consumer_terminal_persistence_models as v212_models,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_repaired_full_condition_online_consumer_terminal_persistence_runtime as v212_runtime,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_repaired_observation_derived_terminal_models as models,
)
from trusted_synthesis.hashing import canonical_hash
from trusted_synthesis.runtime.agent.schema import AgentModelConfig


def _encoded(value: Any) -> bytes:
    return models.canonical_bytes(value) + b"\n"


def _identified(values: dict[str, Any], *, field: str, prefix: str) -> dict[str, Any]:
    result = dict(values)
    result[field] = canonical_hash(values, prefix=prefix)
    return result


class ObservationDerivedTerminalDispatcher:
    """Derive a terminal from strict observed evidence; no terminal label is accepted."""

    def __init__(self, binding: models.ObservationDerivedDispatcherBinding) -> None:
        self._binding = binding
        self._policy_by_terminal = dict(
            zip(binding.terminal_kinds, binding.terminal_policy_ids, strict=True)
        )

    def dispatch(self, evidence: models.ObservedEvidence) -> models.DerivedTerminalDecision:
        strict = models.OBSERVED_EVIDENCE_ADAPTER.validate_python(
            evidence.model_dump(mode="python", warnings=False)
        )
        terminal: str
        rule: str
        if isinstance(strict, models.CompletedRunnerEvidence):
            terminal = "completed_qualified" if strict.qualified_valid else "completed_invalid"
            rule = "final_base_and_mechanism_conjunction"
        elif isinstance(strict, models.ParserRejectionEvidence):
            terminal = (
                "correction_response_abi_invalid"
                if strict.phase == "correction"
                else "first_response_abi_invalid"
            )
            rule = "action_parser_rejection_phase"
        elif isinstance(strict, models.FinalParserRejectionEvidence):
            terminal = "final_response_abi_invalid"
            rule = "final_parser_validation_rejection"
        elif isinstance(strict, models.ActionReferenceFailureEvidence):
            terminal = (
                "correction_action_reference_invalid"
                if strict.phase == "correction"
                else "first_action_reference_invalid"
            )
            rule = "parsed_action_absent_from_current_candidates"
        elif isinstance(strict, models.CorrectionBoundFailureEvidence):
            terminal = "correction_attempt_typed_invalid"
            rule = "second_invalid_correction_reaches_frozen_bound"
        elif isinstance(strict, models.ProviderNoPayloadEvidence):
            terminal = "provider_failure_no_payload"
            rule = "typed_provider_no_payload_exception"
        elif isinstance(strict, models.TransportFailureEvidence):
            terminal = "provider_transport_failure"
            rule = "typed_transport_exception"
        elif isinstance(strict, models.PrivacyFailureEvidence):
            terminal = "privacy_rejection"
            rule = "typed_privacy_exception"
        elif isinstance(strict, models.ResourceFailureEvidence):
            terminal = "resource_budget_exhausted"
            rule = "typed_resource_exception"
        elif isinstance(strict, models.InstrumentFailureEvidence):
            terminal = "instrument_failure"
            rule = "typed_instrument_exception"
        elif isinstance(strict, models.ProviderIdentityFailureEvidence):
            terminal = "provider_identity_failure"
            rule = "typed_provider_identity_exception"
        elif isinstance(strict, models.ThinkingIntegrityFailureEvidence):
            terminal = "thinking_integrity_failure"
            rule = "typed_thinking_integrity_exception"
        elif isinstance(strict, models.UsageIntegrityFailureEvidence):
            terminal = "usage_integrity_failure"
            rule = "typed_usage_integrity_exception"
        else:
            raise TypeError("observed evidence type is not registered")
        return cast(
            models.DerivedTerminalDecision,
            models.make_identity(
                models.DerivedTerminalDecision,
                {
                    "dispatcher_binding_id": self._binding.binding_id,
                    "evidence_id": strict.evidence_id,
                    "evidence_sha256": models.canonical_sha256(strict),
                    "job_id": strict.job_id,
                    "terminal_kind": terminal,
                    "terminal_policy_id": self._policy_by_terminal[terminal],
                    "derivation_rule": rule,
                },
                field="decision_id",
                prefix="fresh_repaired_derived_terminal_decision:",
            ),
        )


class ObservationBoundPersistencePipeline:
    """Re-derive the decision from evidence before any durable Raw write."""

    def __init__(
        self,
        *,
        root: Path,
        binding: models.ObservationBoundPersistenceBinding,
        dispatcher: ObservationDerivedTerminalDispatcher,
    ) -> None:
        self._root = root
        self._binding = binding
        self._dispatcher = dispatcher
        self._persisted_evidence_ids: set[str] = set()

    def persist(
        self,
        *,
        namespace: str,
        evidence: models.ObservedEvidence,
        decision: models.DerivedTerminalDecision,
    ) -> models.PersistedEvidenceDescriptor:
        strict = models.OBSERVED_EVIDENCE_ADAPTER.validate_python(
            evidence.model_dump(mode="python", warnings=False)
        )
        expected = self._dispatcher.dispatch(strict)
        if (
            models.canonical_bytes(expected) != models.canonical_bytes(decision)
            or strict.job_id != decision.job_id
            or strict.evidence_id in self._persisted_evidence_ids
        ):
            raise ValueError("terminal decision is not an exact derivation from observed evidence")
        safe = hashlib.sha256(strict.evidence_id.encode("utf-8")).hexdigest()
        raw = _identified(
            {
                "persistence_binding_id": self._binding.binding_id,
                "evidence_kind": "scripted_observation_control",
                "job_id": strict.job_id,
                "observed_evidence": strict.model_dump(mode="json", warnings=False),
                "derived_terminal_decision": decision.model_dump(mode="json", warnings=False),
                "formal_empirical_row": False,
                "provider_calls": 0,
                "schema_version": models.SCHEMA_VERSION,
            },
            field="raw_id",
            prefix="fresh_repaired_observation_terminal_raw:",
        )
        result = _identified(
            {
                "persistence_binding_id": self._binding.binding_id,
                "job_id": strict.job_id,
                "raw_id": raw["raw_id"],
                "evidence_id": strict.evidence_id,
                "decision_id": decision.decision_id,
                "terminal_kind": decision.terminal_kind,
                "formal_empirical_row": False,
                "provider_calls": 0,
                "schema_version": models.SCHEMA_VERSION,
            },
            field="result_id",
            prefix="fresh_repaired_observation_terminal_result:",
        )
        trace = _identified(
            {
                "persistence_binding_id": self._binding.binding_id,
                "job_id": strict.job_id,
                "raw_id": raw["raw_id"],
                "result_id": result["result_id"],
                "evidence_id": strict.evidence_id,
                "decision_id": decision.decision_id,
                "terminal_kind": decision.terminal_kind,
                "formal_empirical_row": False,
                "provider_calls": 0,
                "schema_version": models.SCHEMA_VERSION,
            },
            field="trace_id",
            prefix="fresh_repaired_observation_terminal_trace:",
        )
        outcome = _identified(
            {
                "persistence_binding_id": self._binding.binding_id,
                "job_id": strict.job_id,
                "raw_id": raw["raw_id"],
                "result_id": result["result_id"],
                "trace_id": trace["trace_id"],
                "evidence_id": strict.evidence_id,
                "decision_id": decision.decision_id,
                "terminal_kind": decision.terminal_kind,
                "formal_empirical_row": False,
                "provider_calls": 0,
                "schema_version": models.SCHEMA_VERSION,
            },
            field="outcome_id",
            prefix="fresh_repaired_observation_terminal_outcome:",
        )
        checkpoint = _identified(
            {
                "persistence_binding_id": self._binding.binding_id,
                "job_id": strict.job_id,
                "raw_id": raw["raw_id"],
                "result_id": result["result_id"],
                "trace_id": trace["trace_id"],
                "outcome_id": outcome["outcome_id"],
                "evidence_id": strict.evidence_id,
                "decision_id": decision.decision_id,
                "terminal_kind": decision.terminal_kind,
                "formal_empirical_row": False,
                "provider_calls": 0,
                "schema_version": models.SCHEMA_VERSION,
            },
            field="checkpoint_id",
            prefix="fresh_repaired_observation_terminal_checkpoint:",
        )
        values = (
            ("raw", raw),
            ("result", result),
            ("trace", trace),
            ("outcome", outcome),
            ("checkpoint", checkpoint),
        )
        paths: dict[str, Path] = {}
        for layer, value in values:
            path = self._root / namespace / layer / f"{safe}.json"
            v212_runtime._durable_write_no_replace(path, _encoded(value))
            if path.read_bytes() != _encoded(value):
                raise ValueError("actual persisted evidence bytes differ")
            paths[layer] = path
        self._persisted_evidence_ids.add(strict.evidence_id)
        return cast(
            models.PersistedEvidenceDescriptor,
            models.make_identity(
                models.PersistedEvidenceDescriptor,
                {
                    "job_id": strict.job_id,
                    "evidence_id": strict.evidence_id,
                    "decision_id": decision.decision_id,
                    "terminal_kind": decision.terminal_kind,
                    "raw_id": raw["raw_id"],
                    "result_id": result["result_id"],
                    "trace_id": trace["trace_id"],
                    "outcome_id": outcome["outcome_id"],
                    "checkpoint_id": checkpoint["checkpoint_id"],
                    "raw_relative_path": paths["raw"].relative_to(self._root).as_posix(),
                    "result_relative_path": paths["result"].relative_to(self._root).as_posix(),
                    "trace_relative_path": paths["trace"].relative_to(self._root).as_posix(),
                    "outcome_relative_path": paths["outcome"].relative_to(self._root).as_posix(),
                    "checkpoint_relative_path": paths["checkpoint"]
                    .relative_to(self._root)
                    .as_posix(),
                    "persistence_sequence": tuple(layer for layer, _value in values),
                },
                field="descriptor_id",
                prefix="finance_v26_213_persisted_evidence_descriptor:",
            ),
        )


class SingleConsumerParentGuard:
    def __init__(
        self,
        *,
        expected_consumer: models.SingleConsumerImplementationBinding,
        expected_composition: models.SingleConsumerCompositionContract,
    ) -> None:
        self._consumer = expected_consumer
        self._composition = expected_composition

    def admit(self, consumer: object, composition: object) -> None:
        if (
            type(consumer) is not models.SingleConsumerImplementationBinding
            or type(composition) is not models.SingleConsumerCompositionContract
        ):
            raise ValueError("single consumer implementation parent type differs")
        assert isinstance(consumer, models.SingleConsumerImplementationBinding)
        assert isinstance(composition, models.SingleConsumerCompositionContract)
        strict_consumer = models.SingleConsumerImplementationBinding.model_validate(
            consumer.model_dump(mode="python", warnings=False)
        )
        strict_composition = models.SingleConsumerCompositionContract.model_validate(
            composition.model_dump(mode="python", warnings=False)
        )
        if (
            models.canonical_bytes(strict_consumer) != models.canonical_bytes(self._consumer)
            or models.canonical_bytes(strict_composition)
            != models.canonical_bytes(self._composition)
            or strict_composition.consumer_binding_id != strict_consumer.binding_id
        ):
            raise ValueError("single consumer implementation parent bytes differ")


def _completed_evidence(
    *,
    job_id: str,
    records: tuple[v209_models.ExecutableInvocationRecord, ...],
    final_payload: dict[str, Any],
    result: Any,
) -> models.CompletedRunnerEvidence:
    final_result = result.model_dump(mode="json", warnings=False)
    task = result.task_validity
    mechanism = result.mechanism_qualification
    qualified = result.qualified_validity
    return cast(
        models.CompletedRunnerEvidence,
        models.make_identity(
            models.CompletedRunnerEvidence,
            {
                "job_id": job_id,
                "invocation_records": tuple(
                    item.model_dump(mode="json", warnings=False) for item in records
                ),
                "final_public_payload": final_payload,
                "final_result": final_result,
                "final_result_sha256": models.canonical_sha256(final_result),
                "final_result_id": result.result_id,
                "task_report_id": task.report_id,
                "mechanism_report_id": mechanism.report_id,
                "qualified_report_id": qualified.report_id,
                "base_valid": task.base_valid,
                "mechanism_valid": mechanism.mechanism_semantically_qualified,
                "qualified_valid": qualified.qualified_valid,
            },
            field="evidence_id",
            prefix="fresh_repaired_completed_runner_evidence:",
        ),
    )


def _make_runner(
    *,
    transport: Any,
    config: AgentModelConfig,
    parents: Any,
    prepared: Any,
    implementation_id: str,
) -> v209.FinalContinuityRepairedFullConditionRunner:
    return v209.FinalContinuityRepairedFullConditionRunner(
        transport=transport,
        config=config,
        profile=parents.profile,
        prepared=prepared,
        implementation_id=implementation_id,
        prompt_contract=parents.prompt_contract,
        prompt_schema=parents.prompt_schema,
    )


@dataclass(frozen=True)
class MainExecution:
    census: v209_models.ExecutableInvocationCensus
    control: v209_models.FullConditionExecutionControlAudit
    evidences: tuple[models.CompletedRunnerEvidence, ...]
    decisions: tuple[models.DerivedTerminalDecision, ...]
    descriptors: tuple[models.PersistedEvidenceDescriptor, ...]


def _execute_manifest_main_path(
    *,
    manifest: v209_models.ExecutableDevelopmentManifest,
    execution: v209_models.ExecutableExecutionContract,
    implementation: v209_models.ImplementationBinding,
    parents: Any,
    prepared: Any,
    config: AgentModelConfig,
    transport_factory: v212_runtime.ProviderTransportFactory,
    dispatcher: ObservationDerivedTerminalDispatcher,
    pipeline: ObservationBoundPersistencePipeline,
) -> MainExecution:
    all_records: list[v209_models.ExecutableInvocationRecord] = []
    rows: list[v209_models.ExecutableJobControlRow] = []
    evidences: list[models.CompletedRunnerEvidence] = []
    decisions: list[models.DerivedTerminalDecision] = []
    descriptors: list[models.PersistedEvidenceDescriptor] = []
    correction_distribution: Counter[int] = Counter()
    for job in sorted(manifest.jobs, key=lambda item: item.job_id):
        context = v209._context_for_job(job=job, parents=parents, prepared=prepared)
        state = frozen_runtime._initialize(context)
        transport = transport_factory.create()
        runner = _make_runner(
            transport=transport,
            config=config,
            parents=parents,
            prepared=prepared,
            implementation_id=implementation.implementation_id,
        )
        records: list[v209_models.ExecutableInvocationRecord] = []
        invocation_index = 0
        action_count = 0
        subsequent_count = 0
        correction_count = 0
        while state.current_index < len(state.ordered_components):
            component_index = state.current_index
            branch_origin = copy.deepcopy(state)
            prompt = step_runtime.render_next_prompt(state)
            dispositions = frozen_runtime._candidate_dispositions(state, prompt)
            reference = frozen_runtime._reference_selection(
                state, prompt, dispositions, component_index
            )
            if reference.action_id is None:
                raise ValueError("reference Action lacks Action ID")
            invalid = next((item for item in dispositions if not item.acceptance.accepted), None)
            transport.queue(
                v209._action_payload(
                    state_id=prompt.state.state_token,
                    action_id=reference.action_id,
                    profile=parents.profile,
                )
            )
            action = runner.invoke_action(job=job, invocation_index=invocation_index, state=state)
            invocation_index += 1
            action_count += 1
            subsequent_count += int(component_index > 0)
            records.append(action.record)
            all_records.append(action.record)
            if action.terminal is not None or action.record.action_accepted is not True:
                raise ValueError("reference Action did not commit")
            if invalid is None:
                continue
            rejected = step_runtime.step(branch_origin, invalid.action_id)
            if not isinstance(rejected, step_runtime.PublicTypedRejectionObservation):
                raise ValueError("registered invalid Action did not reject")
            correction_prompt = step_runtime.render_next_prompt(branch_origin)
            correction_rows = frozen_runtime._candidate_dispositions(
                branch_origin, correction_prompt
            )
            corrected = frozen_runtime._reference_correction(
                branch_origin,
                correction_prompt,
                correction_rows,
                component_index,
                invalid.action_id,
            )
            if corrected.action_id is None:
                raise ValueError("reference Correction lacks Action ID")
            transport.queue(
                v209._action_payload(
                    state_id=correction_prompt.state.state_token,
                    action_id=corrected.action_id,
                    profile=parents.profile,
                )
            )
            correction = runner.invoke_correction(
                job=job,
                invocation_index=invocation_index,
                state=branch_origin,
            )
            invocation_index += 1
            correction_count += 1
            records.append(correction.record)
            all_records.append(correction.record)
            if correction.terminal is not None or correction.record.action_accepted is not True:
                raise ValueError("reference Correction did not commit")
        preview = step_runtime.finalize(copy.deepcopy(state))
        final_payload = v209._final_payload(preview, context.source)
        transport.queue(final_payload)
        final = runner.invoke_final(
            job=job,
            invocation_index=invocation_index,
            state=state,
            context=context,
        )
        records.append(final.record)
        all_records.append(final.record)
        if final.terminal is not None or final.final_result is None:
            raise ValueError("reference Final did not complete")
        observed = _completed_evidence(
            job_id=job.job_id,
            records=tuple(records),
            final_payload=final_payload,
            result=final.final_result,
        )
        decision = dispatcher.dispatch(observed)
        persisted = pipeline.persist(
            namespace="manifest_observed_evidence",
            evidence=observed,
            decision=decision,
        )
        if decision.terminal_kind != "completed_qualified":
            raise ValueError("reference Final did not derive completed_qualified")
        evidences.append(observed)
        decisions.append(decision)
        descriptors.append(persisted)
        invocation_ids = tuple(item.invocation_id for item in records)
        raw_id = canonical_hash(
            {"job_id": job.job_id, "invocation_ids": invocation_ids},
            prefix="fresh_repaired_final_continuity_executable_control_raw:",
        )
        result_id = canonical_hash(
            {"job_id": job.job_id, "raw_id": raw_id, "qualified_valid": True},
            prefix="fresh_repaired_final_continuity_executable_control_result:",
        )
        trace_id = canonical_hash(
            {"job_id": job.job_id, "raw_id": raw_id, "result_id": result_id},
            prefix="fresh_repaired_final_continuity_executable_control_trace:",
        )
        outcome_id = canonical_hash(
            {"job_id": job.job_id, "trace_id": trace_id, "qualified_valid": True},
            prefix="fresh_repaired_final_continuity_executable_control_outcome:",
        )
        rows.append(
            cast(
                v209_models.ExecutableJobControlRow,
                v209_models.make_identity(
                    v209_models.ExecutableJobControlRow,
                    {
                        "job_id": job.job_id,
                        "source_v206_job_id": job.source_v206_job_id,
                        "invocation_ids": invocation_ids,
                        "subsequent_action_count": subsequent_count,
                        "correction_count": correction_count,
                        "action_and_correction_count": action_count + correction_count,
                        "raw_id": raw_id,
                        "result_id": result_id,
                        "trace_id": trace_id,
                        "outcome_id": outcome_id,
                    },
                    field="row_id",
                    prefix="finance_v26_209_executable_job_control_row:",
                ),
            )
        )
        correction_distribution[correction_count] += 1
    if correction_distribution != Counter({0: 144, 1: 12, 2: 12, 3: 12, 4: 12}):
        raise ValueError("Correction distribution differs")
    ordered = tuple(sorted(all_records, key=lambda item: (item.job_id, item.invocation_index)))
    census = cast(
        v209_models.ExecutableInvocationCensus,
        v209_models.make_identity(
            v209_models.ExecutableInvocationCensus,
            {
                "execution_contract_id": execution.contract_id,
                "manifest_id": manifest.manifest_id,
                "implementation_id": implementation.implementation_id,
                "rows": ordered,
                "maximum_message_byte_count": max(
                    item.canonical_messages_byte_count for item in ordered
                ),
                "maximum_request_body_byte_count": max(
                    item.canonical_request_body_byte_count for item in ordered
                ),
            },
            field="census_id",
            prefix="finance_v26_209_executable_invocation_census:",
        ),
    )
    control = cast(
        v209_models.FullConditionExecutionControlAudit,
        v209_models.make_identity(
            v209_models.FullConditionExecutionControlAudit,
            {
                "execution_contract_id": execution.contract_id,
                "invocation_census_id": census.census_id,
                "rows": tuple(sorted(rows, key=lambda item: item.job_id)),
            },
            field="audit_id",
            prefix="finance_v26_209_full_condition_execution_control_audit:",
        ),
    )
    return MainExecution(
        census=census,
        control=control,
        evidences=tuple(evidences),
        decisions=tuple(decisions),
        descriptors=tuple(descriptors),
    )


def _parser_evidence(
    *,
    job_id: str,
    phase: str,
    outcome: v209.InvocationOutcome,
    payload: dict[str, Any],
) -> models.ObservedEvidence:
    if phase == "final":
        return cast(
            models.FinalParserRejectionEvidence,
            models.make_identity(
                models.FinalParserRejectionEvidence,
                {
                    "job_id": job_id,
                    "invocation_record": outcome.record.model_dump(mode="json", warnings=False),
                    "public_payload": payload,
                },
                field="evidence_id",
                prefix="fresh_repaired_final_parser_rejection_evidence:",
            ),
        )
    return cast(
        models.ParserRejectionEvidence,
        models.make_identity(
            models.ParserRejectionEvidence,
            {
                "job_id": job_id,
                "phase": phase,
                "invocation_record": outcome.record.model_dump(mode="json", warnings=False),
                "public_payload": payload,
            },
            field="evidence_id",
            prefix="fresh_repaired_parser_rejection_evidence:",
        ),
    )


def _reference_evidence(
    *,
    job_id: str,
    phase: str,
    outcome: v209.InvocationOutcome,
    payload: dict[str, Any],
) -> models.ActionReferenceFailureEvidence:
    record = outcome.record
    return cast(
        models.ActionReferenceFailureEvidence,
        models.make_identity(
            models.ActionReferenceFailureEvidence,
            {
                "job_id": job_id,
                "phase": phase,
                "invocation_record": record.model_dump(mode="json", warnings=False),
                "public_payload": payload,
                "current_state_id": record.current_state_id,
                "current_candidate_action_ids": record.candidate_action_ids,
                "observed_action_id": cast(str, record.selected_action_id),
            },
            field="evidence_id",
            prefix="fresh_repaired_action_reference_failure_evidence:",
        ),
    )


class ProviderNoPayloadError(v209.TypedTransportFailure):
    def __init__(self) -> None:
        super().__init__("provider_failure_no_payload", "provider returned no public payload")


class ProviderTransportError(v209.TypedTransportFailure):
    def __init__(self) -> None:
        super().__init__("provider_transport_failure", "typed transport failure")


class PrivacyEvidenceError(v209.TypedTransportFailure):
    def __init__(self) -> None:
        super().__init__("privacy_rejection", "public payload failed privacy projection")


class ResourceBudgetError(v209.TypedTransportFailure):
    def __init__(self) -> None:
        super().__init__("resource_budget_exhausted", "resource budget exhausted")


class InstrumentEvidenceError(v209.TypedTransportFailure):
    def __init__(self) -> None:
        super().__init__("instrument_failure", "instrument evidence failure")


class ProviderIdentityError(v209.TypedTransportFailure):
    def __init__(self) -> None:
        super().__init__("provider_identity_failure", "provider identity differs")


class ThinkingIntegrityError(v209.TypedTransportFailure):
    def __init__(self) -> None:
        super().__init__("thinking_integrity_failure", "Thinking telemetry differs")


class UsageIntegrityError(v209.TypedTransportFailure):
    def __init__(self) -> None:
        super().__init__("usage_integrity_failure", "Usage telemetry differs")


OUTER_EVIDENCE_TYPES: tuple[tuple[type[v209.TypedTransportFailure], type[BaseModel]], ...] = (
    (ProviderNoPayloadError, models.ProviderNoPayloadEvidence),
    (ProviderTransportError, models.TransportFailureEvidence),
    (PrivacyEvidenceError, models.PrivacyFailureEvidence),
    (ResourceBudgetError, models.ResourceFailureEvidence),
    (InstrumentEvidenceError, models.InstrumentFailureEvidence),
    (ProviderIdentityError, models.ProviderIdentityFailureEvidence),
    (ThinkingIntegrityError, models.ThinkingIntegrityFailureEvidence),
    (UsageIntegrityError, models.UsageIntegrityFailureEvidence),
)


def _outer_evidence(
    *,
    job: v209_models.ExecutableDevelopmentJob,
    context: Any,
    parents: Any,
    prepared: Any,
    config: AgentModelConfig,
    implementation_id: str,
    error_type: type[v209.TypedTransportFailure],
    evidence_type: type[BaseModel],
) -> models.ObservedEvidence:
    state = frozen_runtime._initialize(context)
    transport = v209.ScriptedTransport()
    error = error_type()
    transport.queue(error)
    outcome = _make_runner(
        transport=transport,
        config=config,
        parents=parents,
        prepared=prepared,
        implementation_id=implementation_id,
    ).invoke_action(job=job, invocation_index=0, state=state)
    return cast(
        models.ObservedEvidence,
        models.make_identity(
            evidence_type,
            {
                "job_id": job.job_id,
                "invocation_record": outcome.record.model_dump(mode="json", warnings=False),
                "exception_reason_sha256": hashlib.sha256(error.reason.encode("utf-8")).hexdigest(),
            },
            field="evidence_id",
            prefix="fresh_repaired_typed_exception_evidence:",
        ),
    )


def _completed_invalid_evidence(
    *,
    manifest: v209_models.ExecutableDevelopmentManifest,
    parents: Any,
    prepared: Any,
    config: AgentModelConfig,
    implementation_id: str,
) -> models.CompletedRunnerEvidence:
    for job in sorted(manifest.jobs, key=lambda item: item.job_id):
        context = v209._context_for_job(job=job, parents=parents, prepared=prepared)
        initial = frozen_runtime._initialize(context)
        prompt = step_runtime.render_next_prompt(initial)
        dispositions = frozen_runtime._candidate_dispositions(initial, prompt)
        reference = frozen_runtime._reference_selection(initial, prompt, dispositions, 0)
        alternatives = tuple(
            item
            for item in dispositions
            if item.action_id != reference.action_id and item.acceptance.accepted
        )
        for alternative in alternatives:
            state = copy.deepcopy(initial)
            transport = v209.ScriptedTransport()
            runner = _make_runner(
                transport=transport,
                config=config,
                parents=parents,
                prepared=prepared,
                implementation_id=implementation_id,
            )
            records: list[v209_models.ExecutableInvocationRecord] = []
            transport.queue(
                v209._action_payload(
                    state_id=prompt.state.state_token,
                    action_id=alternative.action_id,
                    profile=parents.profile,
                )
            )
            first = runner.invoke_action(job=job, invocation_index=0, state=state)
            records.append(first.record)
            if first.terminal is not None or first.record.action_accepted is not True:
                continue
            invocation_index = 1
            failed = False
            while state.current_index < len(state.ordered_components):
                current = step_runtime.render_next_prompt(state)
                current_rows = frozen_runtime._candidate_dispositions(state, current)
                selected = frozen_runtime._reference_selection(
                    state, current, current_rows, state.current_index
                )
                if selected.action_id is None:
                    failed = True
                    break
                transport.queue(
                    v209._action_payload(
                        state_id=current.state.state_token,
                        action_id=selected.action_id,
                        profile=parents.profile,
                    )
                )
                continued = runner.invoke_action(
                    job=job,
                    invocation_index=invocation_index,
                    state=state,
                )
                invocation_index += 1
                records.append(continued.record)
                if continued.terminal is not None or continued.record.action_accepted is not True:
                    failed = True
                    break
            if failed:
                continue
            preview = step_runtime.finalize(copy.deepcopy(state))
            final_payload = v209._final_payload(preview, context.source)
            transport.queue(final_payload)
            final = runner.invoke_final(
                job=job,
                invocation_index=invocation_index,
                state=state,
                context=context,
            )
            records.append(final.record)
            if final.terminal is not None or final.final_result is None:
                continue
            evidence = _completed_evidence(
                job_id=job.job_id,
                records=tuple(records),
                final_payload=final_payload,
                result=final.final_result,
            )
            if not evidence.qualified_valid:
                return evidence
    raise ValueError("no actual completed-invalid Runner evidence was found")


def _diagnostic_evidences(
    *,
    manifest: v209_models.ExecutableDevelopmentManifest,
    implementation: v209_models.ImplementationBinding,
    parents: Any,
    prepared: Any,
    config: AgentModelConfig,
    qualified: models.CompletedRunnerEvidence,
) -> tuple[models.ObservedEvidence, ...]:
    first_job = sorted(manifest.jobs, key=lambda item: item.job_id)[0]
    context = v209._context_for_job(job=first_job, parents=parents, prepared=prepared)
    invalid_first_state = frozen_runtime._initialize(context)
    invalid_first_prompt = step_runtime.render_next_prompt(invalid_first_state)
    invalid_first_rows = frozen_runtime._candidate_dispositions(
        invalid_first_state, invalid_first_prompt
    )
    invalid_first_payload = {
        "state_id": invalid_first_prompt.state.state_token,
        "action_id": invalid_first_rows[0].action_id,
        "decision_kind": parents.profile.decision_kind_value,
    }
    invalid_first_transport = v209.ScriptedTransport()
    invalid_first_transport.queue(invalid_first_payload)
    invalid_first = _make_runner(
        transport=invalid_first_transport,
        config=config,
        parents=parents,
        prepared=prepared,
        implementation_id=implementation.implementation_id,
    ).invoke_action(job=first_job, invocation_index=0, state=invalid_first_state)

    correction_job, _correction_context, correction_state = v209._find_correction_state(
        manifest=manifest, parents=parents, prepared=prepared
    )
    correction_prompt = step_runtime.render_next_prompt(correction_state)
    correction_rows = frozen_runtime._candidate_dispositions(correction_state, correction_prompt)
    invalid_correction_payload = {
        "state_id": correction_prompt.state.state_token,
        "action_id": correction_rows[0].action_id,
        "decision_kind": parents.profile.decision_kind_value,
    }
    invalid_correction_transport = v209.ScriptedTransport()
    invalid_correction_transport.queue(invalid_correction_payload)
    invalid_correction = _make_runner(
        transport=invalid_correction_transport,
        config=config,
        parents=parents,
        prepared=prepared,
        implementation_id=implementation.implementation_id,
    ).invoke_correction(
        job=correction_job,
        invocation_index=1,
        state=copy.deepcopy(correction_state),
    )

    first_reference_state = frozen_runtime._initialize(context)
    first_reference_prompt = step_runtime.render_next_prompt(first_reference_state)
    unknown_first_payload = v209._action_payload(
        state_id=first_reference_prompt.state.state_token,
        action_id="f" * 24,
        profile=parents.profile,
    )
    unknown_first_transport = v209.ScriptedTransport()
    unknown_first_transport.queue(unknown_first_payload)
    unknown_first = _make_runner(
        transport=unknown_first_transport,
        config=config,
        parents=parents,
        prepared=prepared,
        implementation_id=implementation.implementation_id,
    ).invoke_action(job=first_job, invocation_index=0, state=first_reference_state)

    unknown_correction_payload = v209._action_payload(
        state_id=correction_prompt.state.state_token,
        action_id="e" * 24,
        profile=parents.profile,
    )
    unknown_correction_transport = v209.ScriptedTransport()
    unknown_correction_transport.queue(unknown_correction_payload)
    unknown_correction = _make_runner(
        transport=unknown_correction_transport,
        config=config,
        parents=parents,
        prepared=prepared,
        implementation_id=implementation.implementation_id,
    ).invoke_correction(
        job=correction_job,
        invocation_index=1,
        state=copy.deepcopy(correction_state),
    )

    invalid_current = next(item for item in correction_rows if not item.acceptance.accepted)
    repeated_invalid_payload = v209._action_payload(
        state_id=correction_prompt.state.state_token,
        action_id=invalid_current.action_id,
        profile=parents.profile,
    )
    repeated_invalid_transport = v209.ScriptedTransport()
    repeated_invalid_transport.queue(repeated_invalid_payload)
    repeated_invalid = _make_runner(
        transport=repeated_invalid_transport,
        config=config,
        parents=parents,
        prepared=prepared,
        implementation_id=implementation.implementation_id,
    ).invoke_correction(
        job=correction_job,
        invocation_index=1,
        state=copy.deepcopy(correction_state),
    )
    if repeated_invalid.runtime_output is None:
        raise ValueError("repeated invalid Correction lacks actual terminal object")
    correction_bound = cast(
        models.CorrectionBoundFailureEvidence,
        models.make_identity(
            models.CorrectionBoundFailureEvidence,
            {
                "job_id": correction_job.job_id,
                "invocation_record": repeated_invalid.record.model_dump(
                    mode="json", warnings=False
                ),
                "public_payload": repeated_invalid_payload,
                "correction_terminal": repeated_invalid.runtime_output.model_dump(
                    mode="json", warnings=False
                ),
            },
            field="evidence_id",
            prefix="fresh_repaired_correction_bound_failure_evidence:",
        ),
    )

    final_state = v209._reference_complete_state(context)
    invalid_final_payload: dict[str, Any] = {}
    invalid_final_transport = v209.ScriptedTransport()
    invalid_final_transport.queue(invalid_final_payload)
    invalid_final = _make_runner(
        transport=invalid_final_transport,
        config=config,
        parents=parents,
        prepared=prepared,
        implementation_id=implementation.implementation_id,
    ).invoke_final(
        job=first_job,
        invocation_index=len(final_state.ordered_components),
        state=final_state,
        context=context,
    )
    completed_invalid = _completed_invalid_evidence(
        manifest=manifest,
        parents=parents,
        prepared=prepared,
        config=config,
        implementation_id=implementation.implementation_id,
    )
    observed: list[models.ObservedEvidence] = [
        qualified,
        completed_invalid,
        _parser_evidence(
            job_id=first_job.job_id,
            phase="first_action",
            outcome=invalid_first,
            payload=invalid_first_payload,
        ),
        _parser_evidence(
            job_id=correction_job.job_id,
            phase="correction",
            outcome=invalid_correction,
            payload=invalid_correction_payload,
        ),
        _reference_evidence(
            job_id=first_job.job_id,
            phase="first_action",
            outcome=unknown_first,
            payload=unknown_first_payload,
        ),
        _reference_evidence(
            job_id=correction_job.job_id,
            phase="correction",
            outcome=unknown_correction,
            payload=unknown_correction_payload,
        ),
        correction_bound,
        _parser_evidence(
            job_id=first_job.job_id,
            phase="final",
            outcome=invalid_final,
            payload=invalid_final_payload,
        ),
    ]
    observed.extend(
        _outer_evidence(
            job=first_job,
            context=context,
            parents=parents,
            prepared=prepared,
            config=config,
            implementation_id=implementation.implementation_id,
            error_type=error_type,
            evidence_type=evidence_type,
        )
        for error_type, evidence_type in OUTER_EVIDENCE_TYPES
    )
    return tuple(observed)


def _negative_control(
    name: str,
    reason: str,
    layer_ids: tuple[str, ...] = (),
) -> models.NegativeControl:
    return cast(
        models.NegativeControl,
        models.make_identity(
            models.NegativeControl,
            {
                "control_name": name,
                "rejection_reason_sha256": hashlib.sha256(reason.encode("utf-8")).hexdigest(),
                "fully_rehashed_downstream_layer_ids": layer_ids,
            },
            field="control_id",
            prefix="finance_v26_213_terminal_provenance_negative_control:",
        ),
    )


def _in_memory_downstream_layer_ids(
    *,
    binding: models.ObservationBoundPersistenceBinding,
    evidence: models.ObservedEvidence,
    decision: models.DerivedTerminalDecision,
) -> tuple[str, ...]:
    strict = models.OBSERVED_EVIDENCE_ADAPTER.validate_python(
        evidence.model_dump(mode="python", warnings=False)
    )
    raw = _identified(
        {
            "persistence_binding_id": binding.binding_id,
            "evidence_kind": "scripted_observation_control",
            "job_id": strict.job_id,
            "observed_evidence": strict.model_dump(mode="json", warnings=False),
            "derived_terminal_decision": decision.model_dump(mode="json", warnings=False),
            "formal_empirical_row": False,
            "provider_calls": 0,
            "schema_version": models.SCHEMA_VERSION,
        },
        field="raw_id",
        prefix="fresh_repaired_observation_terminal_raw:",
    )
    result = _identified(
        {
            "persistence_binding_id": binding.binding_id,
            "job_id": strict.job_id,
            "raw_id": raw["raw_id"],
            "evidence_id": strict.evidence_id,
            "decision_id": decision.decision_id,
            "terminal_kind": decision.terminal_kind,
            "formal_empirical_row": False,
            "provider_calls": 0,
            "schema_version": models.SCHEMA_VERSION,
        },
        field="result_id",
        prefix="fresh_repaired_observation_terminal_result:",
    )
    trace = _identified(
        {
            "persistence_binding_id": binding.binding_id,
            "job_id": strict.job_id,
            "raw_id": raw["raw_id"],
            "result_id": result["result_id"],
            "evidence_id": strict.evidence_id,
            "decision_id": decision.decision_id,
            "terminal_kind": decision.terminal_kind,
            "formal_empirical_row": False,
            "provider_calls": 0,
            "schema_version": models.SCHEMA_VERSION,
        },
        field="trace_id",
        prefix="fresh_repaired_observation_terminal_trace:",
    )
    outcome = _identified(
        {
            "persistence_binding_id": binding.binding_id,
            "job_id": strict.job_id,
            "raw_id": raw["raw_id"],
            "result_id": result["result_id"],
            "trace_id": trace["trace_id"],
            "evidence_id": strict.evidence_id,
            "decision_id": decision.decision_id,
            "terminal_kind": decision.terminal_kind,
            "formal_empirical_row": False,
            "provider_calls": 0,
            "schema_version": models.SCHEMA_VERSION,
        },
        field="outcome_id",
        prefix="fresh_repaired_observation_terminal_outcome:",
    )
    checkpoint = _identified(
        {
            "persistence_binding_id": binding.binding_id,
            "job_id": strict.job_id,
            "raw_id": raw["raw_id"],
            "result_id": result["result_id"],
            "trace_id": trace["trace_id"],
            "outcome_id": outcome["outcome_id"],
            "evidence_id": strict.evidence_id,
            "decision_id": decision.decision_id,
            "terminal_kind": decision.terminal_kind,
            "formal_empirical_row": False,
            "provider_calls": 0,
            "schema_version": models.SCHEMA_VERSION,
        },
        field="checkpoint_id",
        prefix="fresh_repaired_observation_terminal_checkpoint:",
    )
    return (
        cast(str, raw["raw_id"]),
        cast(str, result["result_id"]),
        cast(str, trace["trace_id"]),
        cast(str, outcome["outcome_id"]),
        cast(str, checkpoint["checkpoint_id"]),
    )


def _negative_controls(
    *,
    root: Path,
    dispatcher: ObservationDerivedTerminalDispatcher,
    persistence_binding: models.ObservationBoundPersistenceBinding,
    dispatcher_binding: models.ObservationDerivedDispatcherBinding,
    evidences: tuple[models.CompletedRunnerEvidence, ...],
    decisions: tuple[models.DerivedTerminalDecision, ...],
) -> models.NegativeControlAudit:
    controls: list[models.NegativeControl] = []
    parameters = tuple(inspect.signature(dispatcher.dispatch).parameters)
    if parameters != ("evidence",):
        raise ValueError("Dispatcher exposes a caller terminal argument")
    controls.append(
        _negative_control("caller_terminal_argument_absent", "terminal_argument_absent")
    )

    attack_root = root / "negative_controls"
    attack_pipeline = ObservationBoundPersistencePipeline(
        root=attack_root,
        binding=persistence_binding,
        dispatcher=dispatcher,
    )
    qualified = evidences[0]
    relabeled = cast(
        models.DerivedTerminalDecision,
        models.make_identity(
            models.DerivedTerminalDecision,
            {
                "dispatcher_binding_id": dispatcher_binding.binding_id,
                "evidence_id": qualified.evidence_id,
                "evidence_sha256": models.canonical_sha256(qualified),
                "job_id": qualified.job_id,
                "terminal_kind": "provider_identity_failure",
                "terminal_policy_id": dispatcher_binding.terminal_policy_ids[
                    dispatcher_binding.terminal_kinds.index("provider_identity_failure")
                ],
                "derivation_rule": "forged_relabel",
            },
            field="decision_id",
            prefix="fresh_repaired_derived_terminal_decision:",
        ),
    )
    relabeled_layers = _in_memory_downstream_layer_ids(
        binding=persistence_binding,
        evidence=qualified,
        decision=relabeled,
    )
    try:
        attack_pipeline.persist(
            namespace="qualified_relabel",
            evidence=qualified,
            decision=relabeled,
        )
    except ValueError:
        controls.append(
            _negative_control(
                "qualified_runner_evidence_relabel",
                "decision_not_derived_from_observed_evidence",
                relabeled_layers,
            )
        )
    else:
        raise ValueError("Qualified evidence relabel attack was admitted")

    cross = decisions[1]
    cross_layers = _in_memory_downstream_layer_ids(
        binding=persistence_binding,
        evidence=qualified,
        decision=cross,
    )
    try:
        attack_pipeline.persist(
            namespace="cross_job",
            evidence=qualified,
            decision=cross,
        )
    except ValueError:
        controls.append(
            _negative_control(
                "cross_job_terminal_decision_substitution",
                "cross_job_decision_not_derived_from_evidence",
                cross_layers,
            )
        )
    else:
        raise ValueError("cross-Job terminal decision attack was admitted")

    invalid_values = qualified.model_dump(mode="python", exclude={"evidence_id"}, warnings=False)
    invalid_values["base_valid"] = False
    invalid_values["qualified_valid"] = False
    invalid_id = canonical_hash(
        invalid_values,
        prefix="fresh_repaired_completed_runner_evidence:",
    )
    invalid = models.CompletedRunnerEvidence.model_construct(
        evidence_id=invalid_id,
        **invalid_values,
    )
    try:
        dispatcher.dispatch(invalid)
    except ValueError:
        controls.append(
            _negative_control(
                "completed_invalid_factorization_inconsistent_with_final",
                "completed_factors_differ_from_actual_final_result",
            )
        )
    else:
        raise ValueError("inconsistent completed-invalid factorization was admitted")
    if attack_root.exists() and any(path.is_file() for path in attack_root.rglob("*")):
        raise ValueError("negative terminal provenance control wrote Raw evidence")
    return cast(
        models.NegativeControlAudit,
        models.make_identity(
            models.NegativeControlAudit,
            {"controls": tuple(controls)},
            field="audit_id",
            prefix="finance_v26_213_terminal_provenance_negative_control_audit:",
        ),
    )


@dataclass(frozen=True)
class PreflightExecution:
    consumption_receipt: v212_models.PreflightConsumptionReceipt
    run_start_receipt: v212_models.PreflightRunStartReceipt
    execution_audit: models.SingleConsumerExecutionAudit
    terminal_audit: models.TerminalEvidenceAudit
    negative_audit: models.NegativeControlAudit
    census: v209_models.ExecutableInvocationCensus
    control: v209_models.FullConditionExecutionControlAudit


class RepairedOnlineExecutionConsumer:
    """One entry from exact authorization guard through observation-bound persistence."""

    def __init__(
        self,
        *,
        binding: models.SingleConsumerImplementationBinding,
        composition: models.SingleConsumerCompositionContract,
        dispatcher_binding: models.ObservationDerivedDispatcherBinding,
        persistence_binding: models.ObservationBoundPersistenceBinding,
        consumption_contract: v212_models.AuthorizationConsumptionReceiptContract,
        run_start_contract: v212_models.RunStartReceiptContract,
        authorization: v211_models.ExactOnlineExecutionAuthorization,
        authorization_bytes: bytes,
    ) -> None:
        self._binding = binding
        self._composition = composition
        self._dispatcher_binding = dispatcher_binding
        self._persistence_binding = persistence_binding
        self._consumption_contract = consumption_contract
        self._run_start_contract = run_start_contract
        self._authorization = authorization
        self._authorization_bytes = authorization_bytes
        self._guard = SingleConsumerParentGuard(
            expected_consumer=binding,
            expected_composition=composition,
        )

    def execute_preflight(
        self,
        *,
        root: Path,
        manifest: v209_models.ExecutableDevelopmentManifest,
        execution: v209_models.ExecutableExecutionContract,
        implementation: v209_models.ImplementationBinding,
        parents: Any,
        prepared: Any,
        config: AgentModelConfig,
        saved_census: v209_models.ExecutableInvocationCensus,
        saved_control: v209_models.FullConditionExecutionControlAudit,
    ) -> PreflightExecution:
        self._guard.admit(self._binding, self._composition)
        durable_consumer = v212_runtime.DurableAuthorizationConsumer(
            contract=self._consumption_contract,
            consumer_binding_id=self._binding.binding_id,
            expected_authorization=self._authorization,
            expected_authorization_file_bytes=self._authorization_bytes,
        )
        consumption = durable_consumer.consume_preflight_lease(root / "consumer_ingress")
        run_writer = v212_runtime.DurableRunStartReceiptWriter(
            contract=self._run_start_contract,
            consumer_binding_id=self._binding.binding_id,
            manifest_id=manifest.manifest_id,
            exact_job_set_sha256=models.canonical_sha256(manifest.expected_job_ids),
        )
        run_start = run_writer.write(root / "consumer_ingress", consumption)
        credential_boundary_probe_count = 0

        def boundary_probe() -> None:
            nonlocal credential_boundary_probe_count
            credential_boundary_probe_count += 1

        def writer_builder() -> ObservationBoundPersistencePipeline:
            dispatcher = ObservationDerivedTerminalDispatcher(self._dispatcher_binding)
            return ObservationBoundPersistencePipeline(
                root=root,
                binding=self._persistence_binding,
                dispatcher=dispatcher,
            )

        products = v212_runtime.CredentialBoundFactoryGate().open(
            root=root / "consumer_ingress",
            consumption=consumption,
            run_start=run_start,
            credential_boundary_probe=boundary_probe,
            transport_factory_builder=v212_runtime.ProviderTransportFactory,
            writer_factory_builder=writer_builder,
        )
        if credential_boundary_probe_count != 1 or not isinstance(
            products.writer_factory_marker,
            ObservationBoundPersistencePipeline,
        ):
            raise ValueError("single consumer factory order differs")
        dispatcher = ObservationDerivedTerminalDispatcher(self._dispatcher_binding)
        pipeline = products.writer_factory_marker
        main = _execute_manifest_main_path(
            manifest=manifest,
            execution=execution,
            implementation=implementation,
            parents=parents,
            prepared=prepared,
            config=config,
            transport_factory=products.transport_factory,
            dispatcher=dispatcher,
            pipeline=pipeline,
        )
        if (
            main.census != saved_census
            or main.control != saved_control
            or products.transport_factory.construction_count != 192
            or sum(len(transport.dispatches) for transport in products.transport_factory.transports)
            != 792
            or any(transport.provider_calls for transport in products.transport_factory.transports)
        ):
            raise ValueError("single consumer v26.209 replay differs")
        execution_audit = cast(
            models.SingleConsumerExecutionAudit,
            models.make_identity(
                models.SingleConsumerExecutionAudit,
                {
                    "consumer_binding_id": self._binding.binding_id,
                    "composition_contract_id": self._composition.contract_id,
                    "consumption_receipt_id": consumption.receipt_id,
                    "run_start_receipt_id": run_start.receipt_id,
                    "v209_invocation_census_id": main.census.census_id,
                    "v209_execution_control_audit_id": main.control.audit_id,
                    "descriptors": main.descriptors,
                },
                field="audit_id",
                prefix="finance_v26_213_single_consumer_execution_audit:",
            ),
        )
        terminal_evidences = _diagnostic_evidences(
            manifest=manifest,
            implementation=implementation,
            parents=parents,
            prepared=prepared,
            config=config,
            qualified=main.evidences[0],
        )
        controls: list[models.TerminalEvidenceControl] = []
        main_by_evidence = {
            item.evidence_id: (decision, descriptor)
            for item, decision, descriptor in zip(
                main.evidences,
                main.decisions,
                main.descriptors,
                strict=True,
            )
        }
        for expected, evidence in zip(models.TERMINAL_KINDS, terminal_evidences, strict=True):
            existing = main_by_evidence.get(evidence.evidence_id)
            if existing is None:
                decision = dispatcher.dispatch(evidence)
                descriptor = pipeline.persist(
                    namespace="terminal_evidence_controls",
                    evidence=evidence,
                    decision=decision,
                )
            else:
                decision, descriptor = existing
            if decision.terminal_kind != expected:
                raise ValueError("diagnostic observed evidence derived an unexpected terminal")
            controls.append(
                cast(
                    models.TerminalEvidenceControl,
                    models.make_identity(
                        models.TerminalEvidenceControl,
                        {
                            "expected_terminal": expected,
                            "observed_evidence": evidence,
                            "derived_decision": decision,
                            "persistence": descriptor,
                        },
                        field="control_id",
                        prefix="finance_v26_213_terminal_evidence_control:",
                    ),
                )
            )
        terminal_audit = cast(
            models.TerminalEvidenceAudit,
            models.make_identity(
                models.TerminalEvidenceAudit,
                {
                    "dispatcher_binding_id": self._dispatcher_binding.binding_id,
                    "controls": tuple(controls),
                },
                field="audit_id",
                prefix="finance_v26_213_terminal_evidence_audit:",
            ),
        )
        negative = _negative_controls(
            root=root,
            dispatcher=dispatcher,
            persistence_binding=self._persistence_binding,
            dispatcher_binding=self._dispatcher_binding,
            evidences=main.evidences,
            decisions=main.decisions,
        )
        return PreflightExecution(
            consumption_receipt=consumption,
            run_start_receipt=run_start,
            execution_audit=execution_audit,
            terminal_audit=terminal_audit,
            negative_audit=negative,
            census=main.census,
            control=main.control,
        )
