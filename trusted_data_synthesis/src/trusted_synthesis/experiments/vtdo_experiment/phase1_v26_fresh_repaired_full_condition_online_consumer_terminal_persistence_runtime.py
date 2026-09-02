# ruff: noqa: E501
from __future__ import annotations

import copy
import hashlib
import os
from collections import Counter, deque
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

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
    phase1_v26_fresh_repaired_full_condition_online_consumer_terminal_persistence_models as models,
)
from trusted_synthesis.hashing import canonical_hash
from trusted_synthesis.runtime.agent.schema import AgentModelConfig


def _sha(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _encoded(value: Any) -> bytes:
    return models.canonical_bytes(value) + b"\n"


def _durable_write_no_replace(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "wb", closefd=False) as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
    finally:
        os.close(descriptor)
    directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)


def _strict_file(path: Path, expected: Any) -> None:
    if path.is_symlink() or not path.is_file() or path.read_bytes() != _encoded(expected):
        raise ValueError(f"durable receipt bytes differ:{path.name}")


class DurableAuthorizationConsumer:
    """Exact-byte, durable no-replace consumer for an isolated preflight lease."""

    def __init__(
        self,
        *,
        contract: models.AuthorizationConsumptionReceiptContract,
        consumer_binding_id: str,
        expected_authorization: v211_models.ExactOnlineExecutionAuthorization,
        expected_authorization_file_bytes: bytes,
    ) -> None:
        strict = v211_models.ExactOnlineExecutionAuthorization.model_validate(
            expected_authorization.model_dump(mode="python", warnings=False)
        )
        if (
            expected_authorization_file_bytes != v211_models.canonical_bytes(strict) + b"\n"
            or strict.authorization_id != contract.exact_v211_authorization_id
        ):
            raise ValueError("exact v26.211 authorization bytes differ")
        self._contract = contract
        self._consumer_binding_id = consumer_binding_id
        self._authorization = strict
        self._authorization_bytes = expected_authorization_file_bytes

    def consume_preflight_lease(self, root: Path) -> models.PreflightConsumptionReceipt:
        receipt = cast(
            models.PreflightConsumptionReceipt,
            models.make_identity(
                models.PreflightConsumptionReceipt,
                {
                    "contract_id": self._contract.contract_id,
                    "consumer_binding_id": self._consumer_binding_id,
                    "authorization_id": self._authorization.authorization_id,
                    "authorization_sha256": _sha(self._authorization_bytes),
                },
                field="receipt_id",
                prefix="fresh_repaired_preflight_authorization_consumption_receipt:",
            ),
        )
        _durable_write_no_replace(
            root / "authorization_consumption_receipt.json", _encoded(receipt)
        )
        return receipt


class DurableRunStartReceiptWriter:
    def __init__(
        self,
        *,
        contract: models.RunStartReceiptContract,
        consumer_binding_id: str,
        manifest_id: str,
        exact_job_set_sha256: str,
    ) -> None:
        self._contract = contract
        self._consumer_binding_id = consumer_binding_id
        self._manifest_id = manifest_id
        self._job_set_sha = exact_job_set_sha256

    def write(
        self,
        root: Path,
        consumption: models.PreflightConsumptionReceipt,
    ) -> models.PreflightRunStartReceipt:
        _strict_file(root / "authorization_consumption_receipt.json", consumption)
        if consumption.contract_id != self._contract.consumption_contract_id:
            raise ValueError("Run Start Receipt crosses consumption Contract")
        receipt = cast(
            models.PreflightRunStartReceipt,
            models.make_identity(
                models.PreflightRunStartReceipt,
                {
                    "contract_id": self._contract.contract_id,
                    "consumption_receipt_id": consumption.receipt_id,
                    "consumer_binding_id": self._consumer_binding_id,
                    "manifest_id": self._manifest_id,
                    "exact_job_set_sha256": self._job_set_sha,
                },
                field="receipt_id",
                prefix="fresh_repaired_preflight_run_start_receipt:",
            ),
        )
        _durable_write_no_replace(root / "run_start_receipt.json", _encoded(receipt))
        return receipt


class PreflightProviderTransport:
    """Injected-transport implementation with exact request-chain checks and no network path."""

    def __init__(self) -> None:
        self._queue: deque[Mapping[str, Any]] = deque()
        self.dispatches: list[v209.TransportDispatch] = []
        self.provider_calls = 0

    def queue(self, value: Mapping[str, Any]) -> None:
        self._queue.append(value)

    def send(self, dispatch: v209.TransportDispatch) -> Mapping[str, Any]:
        if (
            dispatch.receipt.certificate_id != dispatch.certificate.certificate_id
            or dispatch.receipt.request_id != dispatch.certificate.request_id
            or v209_models.canonical_sha256(dispatch.request_body)
            != dispatch.certificate.canonical_request_body_sha256
        ):
            raise v209.TypedTransportFailure(
                "instrument_failure",
                "preflight transport received an invalid request chain",
            )
        if not self._queue:
            raise v209.TypedTransportFailure(
                "instrument_failure",
                "preflight transport response queue is empty",
            )
        self.dispatches.append(dispatch)
        return self._queue.popleft()


class ProviderTransportFactory:
    def __init__(self) -> None:
        self.construction_count = 0
        self.transports: list[PreflightProviderTransport] = []

    def create(self) -> PreflightProviderTransport:
        self.construction_count += 1
        value = PreflightProviderTransport()
        self.transports.append(value)
        return value


@dataclass(frozen=True)
class GuardedFactoryProducts:
    transport_factory: ProviderTransportFactory
    writer_factory_marker: object


class CredentialBoundFactoryGate:
    """Requires both durable receipts before a boundary probe or any factory construction."""

    def open(
        self,
        *,
        root: Path,
        consumption: models.PreflightConsumptionReceipt,
        run_start: models.PreflightRunStartReceipt,
        credential_boundary_probe: Any,
        transport_factory_builder: Any,
        writer_factory_builder: Any,
    ) -> GuardedFactoryProducts:
        _strict_file(root / "authorization_consumption_receipt.json", consumption)
        _strict_file(root / "run_start_receipt.json", run_start)
        if (
            run_start.consumption_receipt_id != consumption.receipt_id
            or run_start.consumer_binding_id != consumption.consumer_binding_id
        ):
            raise ValueError("factory Gate crosses durable receipt parents")
        credential_boundary_probe()
        transport = transport_factory_builder()
        writer = writer_factory_builder()
        if not isinstance(transport, ProviderTransportFactory):
            raise TypeError("transport factory type differs")
        return GuardedFactoryProducts(transport_factory=transport, writer_factory_marker=writer)


class RepairedImplementationParentGuard:
    """Exact-object guard for the repaired consumer and composition implementation parents."""

    def __init__(
        self,
        *,
        expected_consumer: models.OnlineExecutionConsumerImplementationBinding,
        expected_composition: models.RepairedCompositionContract,
    ) -> None:
        self._consumer = models.OnlineExecutionConsumerImplementationBinding.model_validate(
            expected_consumer.model_dump(mode="python", warnings=False)
        )
        self._composition = models.RepairedCompositionContract.model_validate(
            expected_composition.model_dump(mode="python", warnings=False)
        )

    def admit(
        self,
        *,
        consumer: object,
        composition: object,
    ) -> None:
        if type(consumer) is not models.OnlineExecutionConsumerImplementationBinding:
            raise ValueError("consumer implementation parent type differs")
        if type(composition) is not models.RepairedCompositionContract:
            raise ValueError("repaired composition parent type differs")
        assert isinstance(consumer, models.OnlineExecutionConsumerImplementationBinding)
        assert isinstance(composition, models.RepairedCompositionContract)
        strict_consumer = models.OnlineExecutionConsumerImplementationBinding.model_validate(
            consumer.model_dump(mode="python", warnings=False)
        )
        strict_composition = models.RepairedCompositionContract.model_validate(
            composition.model_dump(mode="python", warnings=False)
        )
        if (
            models.canonical_bytes(strict_consumer) != models.canonical_bytes(self._consumer)
            or models.canonical_bytes(strict_composition)
            != models.canonical_bytes(self._composition)
            or strict_composition.consumer_binding_id != strict_consumer.binding_id
        ):
            raise ValueError("repaired implementation parent bytes differ")


def execute_exact_v209_runner(
    *,
    manifest: v209_models.ExecutableDevelopmentManifest,
    execution: v209_models.ExecutableExecutionContract,
    implementation: v209_models.ImplementationBinding,
    parents: Any,
    prepared: Any,
    config: AgentModelConfig,
    transport_factory: ProviderTransportFactory,
) -> tuple[
    v209_models.ExecutableInvocationCensus,
    v209_models.FullConditionExecutionControlAudit,
]:
    """Drive the actual v26.209 Runner with a source-bound zero-Provider transport."""

    all_records: list[v209_models.ExecutableInvocationRecord] = []
    job_rows: list[v209_models.ExecutableJobControlRow] = []
    correction_distribution: Counter[int] = Counter()
    for job in sorted(manifest.jobs, key=lambda item: item.job_id):
        context = v209._context_for_job(job=job, parents=parents, prepared=prepared)
        state = frozen_runtime._initialize(context)
        transport = transport_factory.create()
        runner = v209.FinalContinuityRepairedFullConditionRunner(
            transport=transport,
            config=config,
            profile=parents.profile,
            prepared=prepared,
            implementation_id=implementation.implementation_id,
            prompt_contract=parents.prompt_contract,
            prompt_schema=parents.prompt_schema,
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
                state,
                prompt,
                dispositions,
                component_index,
            )
            if reference.action_id is None:
                raise ValueError("v26.212 reference Action lacks Action ID")
            invalid = next((item for item in dispositions if not item.acceptance.accepted), None)
            transport.queue(
                v209._action_payload(
                    state_id=prompt.state.state_token,
                    action_id=reference.action_id,
                    profile=parents.profile,
                )
            )
            action = runner.invoke_action(
                job=job,
                invocation_index=invocation_index,
                state=state,
            )
            invocation_index += 1
            action_count += 1
            subsequent_count += int(component_index > 0)
            records.append(action.record)
            all_records.append(action.record)
            if action.terminal is not None or action.record.action_accepted is not True:
                raise ValueError("v26.212 reference Action did not commit")
            if invalid is None:
                continue
            rejected = step_runtime.step(branch_origin, invalid.action_id)
            if not isinstance(rejected, step_runtime.PublicTypedRejectionObservation):
                raise ValueError("v26.212 registered invalid Action did not reject")
            correction_prompt = step_runtime.render_next_prompt(branch_origin)
            correction_rows = frozen_runtime._candidate_dispositions(
                branch_origin,
                correction_prompt,
            )
            corrected = frozen_runtime._reference_correction(
                branch_origin,
                correction_prompt,
                correction_rows,
                component_index,
                invalid.action_id,
            )
            if corrected.action_id is None:
                raise ValueError("v26.212 reference Correction lacks Action ID")
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
                raise ValueError("v26.212 reference Correction did not commit")
        preview_result = step_runtime.finalize(copy.deepcopy(state))
        transport.queue(v209._final_payload(preview_result, context.source))
        final = runner.invoke_final(
            job=job,
            invocation_index=invocation_index,
            state=state,
            context=context,
        )
        records.append(final.record)
        all_records.append(final.record)
        if final.terminal is not None or final.final_result is None:
            raise ValueError("v26.212 reference Final terminalized")
        result = final.final_result
        if (
            not result.task_validity.base_valid
            or not result.mechanism_qualification.mechanism_semantically_qualified
            or not result.qualified_validity.qualified_valid
        ):
            raise ValueError("v26.212 scripted path is not Qualified")
        if len(transport.dispatches) != len(records) or transport.provider_calls != 0:
            raise ValueError("v26.212 transport dispatch geometry differs")
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
        job_rows.append(
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
        raise ValueError("v26.212 Correction distribution differs")
    ordered_records = tuple(
        sorted(all_records, key=lambda item: (item.job_id, item.invocation_index))
    )
    census = cast(
        v209_models.ExecutableInvocationCensus,
        v209_models.make_identity(
            v209_models.ExecutableInvocationCensus,
            {
                "execution_contract_id": execution.contract_id,
                "manifest_id": manifest.manifest_id,
                "implementation_id": implementation.implementation_id,
                "rows": ordered_records,
                "maximum_message_byte_count": max(
                    item.canonical_messages_byte_count for item in ordered_records
                ),
                "maximum_request_body_byte_count": max(
                    item.canonical_request_body_byte_count for item in ordered_records
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
                "rows": tuple(sorted(job_rows, key=lambda item: item.job_id)),
            },
            field="audit_id",
            prefix="finance_v26_209_full_condition_execution_control_audit:",
        ),
    )
    return census, control


def _identified(values: dict[str, Any], *, field: str, prefix: str) -> dict[str, Any]:
    result = dict(values)
    result[field] = canonical_hash(values, prefix=prefix)
    return result


class CompleteTerminalDispatcher:
    def __init__(self, binding: models.TerminalRegistryDispatcherBinding) -> None:
        self._binding = binding
        self._policies = dict(zip(binding.terminal_kinds, binding.terminal_policy_ids, strict=True))

    def dispatch(
        self,
        *,
        terminal_kind: str,
        source_binding_id: str,
        job_id: str,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        policy_id = self._policies.get(terminal_kind)
        if policy_id is None:
            raise ValueError("terminal kind is absent from complete reachable Registry")
        signal = _identified(
            {
                "terminal_registry_dispatcher_binding_id": self._binding.binding_id,
                "terminal_policy_id": policy_id,
                "terminal_kind": terminal_kind,
                "source_binding_id": source_binding_id,
                "job_id": job_id,
                "source_bound": True,
                "provider_calls": 0,
                "schema_version": models.SCHEMA_VERSION,
            },
            field="signal_id",
            prefix="fresh_repaired_online_terminal_signal:",
        )
        decision = _identified(
            {
                "terminal_registry_dispatcher_binding_id": self._binding.binding_id,
                "terminal_policy_id": policy_id,
                "terminal_signal_id": signal["signal_id"],
                "terminal_kind": terminal_kind,
                "job_id": job_id,
                "terminal_projection_count": 1,
                "provider_calls": 0,
                "schema_version": models.SCHEMA_VERSION,
            },
            field="decision_id",
            prefix="fresh_repaired_online_terminal_decision:",
        )
        return signal, decision


@dataclass(frozen=True)
class PersistedChain:
    raw: dict[str, Any]
    result: dict[str, Any]
    trace: dict[str, Any]
    outcome: dict[str, Any]
    checkpoint: dict[str, Any]
    raw_path: Path
    result_path: Path
    trace_path: Path
    outcome_path: Path
    checkpoint_path: Path
    sequence: tuple[str, ...]


class RawResultWriter:
    def __init__(self, root: Path, binding: models.RawResultWriterBinding) -> None:
        self._root = root
        self._binding = binding
        self._raw_by_job: dict[str, dict[str, Any]] = {}
        self.events: list[tuple[str, str]] = []

    @staticmethod
    def _safe(job_id: str) -> str:
        return hashlib.sha256(job_id.encode("utf-8")).hexdigest()

    def write_raw(
        self,
        *,
        namespace: str,
        job_id: str,
        source_binding_id: str,
        invocation_ids: tuple[str, ...],
        terminal_signal: dict[str, Any],
        terminal_decision: dict[str, Any],
    ) -> tuple[dict[str, Any], Path]:
        if job_id in self._raw_by_job:
            raise ValueError("Raw already exists for Job")
        raw = _identified(
            {
                "writer_binding_id": self._binding.binding_id,
                "evidence_kind": "scripted_preflight_control",
                "job_id": job_id,
                "source_binding_id": source_binding_id,
                "invocation_ids": invocation_ids,
                "terminal_signal": terminal_signal,
                "terminal_decision": terminal_decision,
                "formal_empirical_row": False,
                "provider_calls": 0,
                "schema_version": models.SCHEMA_VERSION,
            },
            field="raw_id",
            prefix="fresh_repaired_online_preflight_raw:",
        )
        path = self._root / namespace / "raw" / f"{self._safe(job_id)}.json"
        _durable_write_no_replace(path, _encoded(raw))
        self._raw_by_job[job_id] = raw
        self.events.append((job_id, "raw"))
        return raw, path

    def write_result(
        self,
        *,
        namespace: str,
        job_id: str,
        raw: dict[str, Any],
    ) -> tuple[dict[str, Any], Path]:
        if self._raw_by_job.get(job_id) != raw:
            raise ValueError("Result lacks prior exact Raw")
        result = _identified(
            {
                "writer_binding_id": self._binding.binding_id,
                "evidence_kind": "scripted_preflight_control",
                "job_id": job_id,
                "raw_id": raw["raw_id"],
                "terminal_kind": raw["terminal_decision"]["terminal_kind"],
                "qualified_valid": raw["terminal_decision"]["terminal_kind"]
                == "completed_qualified",
                "formal_empirical_row": False,
                "provider_calls": 0,
                "schema_version": models.SCHEMA_VERSION,
            },
            field="result_id",
            prefix="fresh_repaired_online_preflight_result:",
        )
        path = self._root / namespace / "result" / f"{self._safe(job_id)}.json"
        _durable_write_no_replace(path, _encoded(result))
        self.events.append((job_id, "result"))
        return result, path


class TraceOutcomeCheckpointReconstructor:
    def __init__(
        self,
        root: Path,
        binding: models.TraceOutcomeCheckpointBinding,
    ) -> None:
        self._root = root
        self._binding = binding
        self.events: list[tuple[str, str]] = []

    def reconstruct_and_write(
        self,
        *,
        namespace: str,
        job_id: str,
        raw: dict[str, Any],
        raw_path: Path,
        result: dict[str, Any],
        result_path: Path,
    ) -> tuple[
        dict[str, Any],
        Path,
        dict[str, Any],
        Path,
        dict[str, Any],
        Path,
    ]:
        if (
            raw_path.read_bytes() != _encoded(raw)
            or result_path.read_bytes() != _encoded(result)
            or result["raw_id"] != raw["raw_id"]
            or result["job_id"] != job_id
        ):
            raise ValueError("Trace reconstruction lacks exact Raw/Result bytes")
        safe = hashlib.sha256(job_id.encode("utf-8")).hexdigest()
        trace = _identified(
            {
                "reconstructor_binding_id": self._binding.binding_id,
                "job_id": job_id,
                "raw_id": raw["raw_id"],
                "result_id": result["result_id"],
                "terminal_signal_id": raw["terminal_signal"]["signal_id"],
                "terminal_decision_id": raw["terminal_decision"]["decision_id"],
                "terminal_kind": result["terminal_kind"],
                "formal_empirical_row": False,
                "provider_calls": 0,
                "schema_version": models.SCHEMA_VERSION,
            },
            field="trace_id",
            prefix="fresh_repaired_online_preflight_trace:",
        )
        trace_path = self._root / namespace / "trace" / f"{safe}.json"
        _durable_write_no_replace(trace_path, _encoded(trace))
        self.events.append((job_id, "trace"))
        outcome = _identified(
            {
                "reconstructor_binding_id": self._binding.binding_id,
                "job_id": job_id,
                "raw_id": raw["raw_id"],
                "result_id": result["result_id"],
                "trace_id": trace["trace_id"],
                "terminal_kind": result["terminal_kind"],
                "qualified_valid": result["qualified_valid"],
                "formal_empirical_row": False,
                "provider_calls": 0,
                "schema_version": models.SCHEMA_VERSION,
            },
            field="outcome_id",
            prefix="fresh_repaired_online_preflight_outcome:",
        )
        outcome_path = self._root / namespace / "outcome" / f"{safe}.json"
        _durable_write_no_replace(outcome_path, _encoded(outcome))
        self.events.append((job_id, "outcome"))
        checkpoint = _identified(
            {
                "reconstructor_binding_id": self._binding.binding_id,
                "job_id": job_id,
                "raw_id": raw["raw_id"],
                "result_id": result["result_id"],
                "trace_id": trace["trace_id"],
                "outcome_id": outcome["outcome_id"],
                "terminal_kind": result["terminal_kind"],
                "formal_empirical_row": False,
                "provider_calls": 0,
                "schema_version": models.SCHEMA_VERSION,
            },
            field="checkpoint_id",
            prefix="fresh_repaired_online_preflight_checkpoint:",
        )
        checkpoint_path = self._root / namespace / "checkpoint" / f"{safe}.json"
        _durable_write_no_replace(checkpoint_path, _encoded(checkpoint))
        self.events.append((job_id, "checkpoint"))
        return trace, trace_path, outcome, outcome_path, checkpoint, checkpoint_path


class EvidencePersistencePipeline:
    def __init__(
        self,
        *,
        root: Path,
        raw_result_binding: models.RawResultWriterBinding,
        trace_outcome_checkpoint_binding: models.TraceOutcomeCheckpointBinding,
    ) -> None:
        self._writer = RawResultWriter(root, raw_result_binding)
        self._reconstructor = TraceOutcomeCheckpointReconstructor(
            root,
            trace_outcome_checkpoint_binding,
        )

    def persist(
        self,
        *,
        namespace: str,
        job_id: str,
        source_binding_id: str,
        invocation_ids: tuple[str, ...],
        terminal_signal: dict[str, Any],
        terminal_decision: dict[str, Any],
    ) -> PersistedChain:
        raw, raw_path = self._writer.write_raw(
            namespace=namespace,
            job_id=job_id,
            source_binding_id=source_binding_id,
            invocation_ids=invocation_ids,
            terminal_signal=terminal_signal,
            terminal_decision=terminal_decision,
        )
        result, result_path = self._writer.write_result(
            namespace=namespace,
            job_id=job_id,
            raw=raw,
        )
        trace, trace_path, outcome, outcome_path, checkpoint, checkpoint_path = (
            self._reconstructor.reconstruct_and_write(
                namespace=namespace,
                job_id=job_id,
                raw=raw,
                raw_path=raw_path,
                result=result,
                result_path=result_path,
            )
        )
        sequence = tuple(
            event
            for observed_job, event in (*self._writer.events, *self._reconstructor.events)
            if observed_job == job_id
        )
        if sequence != ("raw", "result", "trace", "outcome", "checkpoint"):
            raise ValueError("evidence persistence sequence differs")
        return PersistedChain(
            raw=raw,
            result=result,
            trace=trace,
            outcome=outcome,
            checkpoint=checkpoint,
            raw_path=raw_path,
            result_path=result_path,
            trace_path=trace_path,
            outcome_path=outcome_path,
            checkpoint_path=checkpoint_path,
            sequence=sequence,
        )
