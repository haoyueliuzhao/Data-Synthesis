# ruff: noqa: E501
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Final, Literal, NoReturn, cast

from pydantic import BaseModel

from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_exact_v209_parent_bound_online_execution as v224,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_exact_v209_parent_bound_online_execution_repair as v226_repair,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_exact_v209_unbound_provider_failure_recovery_online_authorization_manifest_byte_repair as v232,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_exact_v209_unbound_provider_failure_recovery_online_authorization_manifest_byte_repair_models as v232_models,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_exact_v209_unbound_provider_failure_recovery_online_execution_models as models,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_exact_v209_unbound_provider_failure_source_authority_recovery_population_preflight as v229,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_exact_v209_unbound_provider_failure_source_authority_recovery_population_preflight_models as v229_models,
)

RUN_ID: Final = models.RUN_ID
OUTPUT_DIR: Final = f"trusted_data_synthesis/artifacts/vtdo_experiment/{RUN_ID}"
LEDGER_DIR: Final = v224.LEDGER_DIR
V229_DIR: Final = (
    "trusted_data_synthesis/artifacts/vtdo_experiment/"
    "finance_v26_229_fresh_exact_v209_unbound_provider_failure_source_authority_and_"
    "recovery_population_preflight_v1_20260904"
)
V232_DIR: Final = (
    "trusted_data_synthesis/artifacts/vtdo_experiment/"
    "finance_v26_232_fresh_exact_v209_unbound_provider_failure_recovery_population_bound_"
    "online_execution_authorization_predecessor_manifest_actual_byte_authority_repair_"
    "v1_20260904"
)
IMPLEMENTATION_PATHS: Final = tuple(
    sorted(
        (
            "trusted_data_synthesis/src/trusted_synthesis/experiments/vtdo_experiment/"
            "phase1_v26_fresh_exact_v209_unbound_provider_failure_recovery_online_execution.py",
            "trusted_data_synthesis/src/trusted_synthesis/experiments/vtdo_experiment/"
            "phase1_v26_fresh_exact_v209_unbound_provider_failure_recovery_online_execution_models.py",
        )
    )
)
MAX_WORKERS: Final = 8


class V233Error(ValueError):
    def __init__(self, stage: str, reason: str) -> None:
        super().__init__(f"{stage}:{reason}")
        self.stage = stage


class RecoveryExecutionFailure(RuntimeError):
    pass


def _fail(stage: str, reason: str) -> NoReturn:
    raise V233Error(stage, reason)


def _sha(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _encoded(value: Any) -> bytes:
    return models.canonical_bytes(value) + b"\n"


def _load(path: Path) -> Any:
    return json.loads(path.read_bytes())


def _safe(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _durable_write(path: Path, payload: bytes) -> None:
    v224._durable_write_no_replace(path, payload)  # noqa: SLF001


@dataclass(frozen=True)
class PreparedRecoveryExecution:
    repository_root: Path
    package_root: Path
    output_dir: Path
    ledger_path: Path
    review_bytes: bytes
    external_decision: models.ExternalExecutionDecision
    authorization: v232_models.ExactOnlineAuthorization
    authorization_file_bytes: bytes
    admission: v232_models.Admission
    preparation: models.ExecutionPreparation
    recovery_population: v229_models.RecoveryPopulation
    source: v229.SourceData
    replay: v229_models.RequestReplayAudit
    manifest: Any
    implementation: Any
    frozen_parents: Any
    runtime: Any
    config: Any
    bindings: Any


def _external_decision(review: bytes) -> models.ExternalExecutionDecision:
    directive = models.OPERATOR_DIRECTIVE.encode("utf-8")
    if (
        len(review) != models.EXTERNAL_REVIEW_BYTE_COUNT
        or _sha(review) != models.EXTERNAL_REVIEW_SHA256
    ):
        _fail("external.review", "v26.232 audit bytes differ")
    if (
        len(directive) != models.OPERATOR_DIRECTIVE_BYTE_COUNT
        or _sha(directive) != models.OPERATOR_DIRECTIVE_SHA256
    ):
        _fail("external.directive", "operator directive bytes differ")
    return models.make_identity(
        models.ExternalExecutionDecision,
        {},
        field="decision_id",
        prefix=models.ExternalExecutionDecision.prefix(),
    )


def _exact_saved(path: Path, value: BaseModel) -> None:
    if path.read_bytes() != _encoded(value):
        _fail("freeze.actual_bytes", f"saved object bytes differ:{path.name}")


def prepare_execution(
    *, repository_root: Path, output_dir: Path, external_review_path: Path
) -> PreparedRecoveryExecution:
    repository_root = repository_root.resolve()
    package_root = repository_root / "trusted_data_synthesis"
    output_dir = output_dir.resolve()
    if output_dir != (repository_root / OUTPUT_DIR).resolve():
        _fail("scope.output", "v26.233 output directory is fixed")
    review = external_review_path.read_bytes()
    external = _external_decision(review)
    v232_root = repository_root / V232_DIR
    _, manifest232 = v229._verify_manifest(  # noqa: SLF001
        v232_root,
        "artifact_manifest.json",
        file_count=23,
        total_bytes=115_377,
        member_count=22,
        member_bytes=111_695,
        manifest_id="finance_v26_232_artifact_manifest:f0c46ed0882f33033496f0dbb542e304167ca767ed3290bc25142a8b4228b02e",
        artifact_root="finance_v26_232_artifact_root:7f49da2bf737dcb50ca975780301647c6128a62248622d63109b6c363c343cf8",
    )
    auth_path = v232_root / "exact_online_execution_authorization.json"
    auth_bytes = auth_path.read_bytes()
    authorization = v232_models.ExactOnlineAuthorization.model_validate_json(auth_bytes)
    if (
        authorization.authorization_id != models.AUTHORIZATION_ID
        or len(auth_bytes) != models.AUTHORIZATION_BYTE_COUNT
        or _sha(auth_bytes) != models.AUTHORIZATION_SHA256
        or auth_bytes != v232_models.canonical_bytes(authorization)
    ):
        _fail("freeze.authorization", "v26.232 authorization actual bytes differ")
    guard = v232.PrecredentialGuard(authorization)
    admission = guard.admit(**v232._request(authorization))  # noqa: SLF001

    v229_root = repository_root / V229_DIR
    _, manifest229 = v229._verify_manifest(  # noqa: SLF001
        v229_root,
        "artifact_manifest.json",
        file_count=117,
        total_bytes=1_105_367,
        member_count=116,
        member_bytes=1_088_415,
        manifest_id="finance_v26_229_artifact_manifest:968a9b5adee2a0c5011c753ec777de8bc91a768745f09943ea676cd2e9e2f863",
        artifact_root="finance_v26_229_artifact_root:0e99bbf37aff7faeb3f5adef51eeccd086d3cc760c09de6ecf236de914b6abe1",
    )
    population = v229_models.RecoveryPopulation.model_validate_json(
        (v229_root / "recovery_population.json").read_bytes()
    )
    if (
        tuple(sorted(item.recovery_job_id for item in population.jobs))
        != authorization.recovery_job_ids
    ):
        _fail("freeze.population", "authorization Recovery Job set differs")
    v228_freeze = v229_models.V228Freeze.model_validate_json(
        (v229_root / "v228_freeze.json").read_bytes()
    )
    source_identity = cast(dict[str, Any], _load(v229_root / "source_identity.json"))
    source = v229._source_authority(  # noqa: SLF001
        repository_root, v228_freeze, str(source_identity["source_identity_id"])
    )
    _exact_saved(v229_root / "v226_source_authority_audit.json", source.audit)
    _exact_saved(v229_root / "provider_journal_authority.json", source.journal)
    replay = v229._request_replay(repository_root, source)  # noqa: SLF001
    _exact_saved(v229_root / "request_replay_audit.json", replay)
    if (
        len(source.public_prefixes) != 33
        or sum(map(len, source.public_prefixes.values())) != 55
        or len(replay.rows) != 33
    ):
        _fail("freeze.replay", "33-Job/55-prefix Recovery geometry differs")
    with TemporaryDirectory(prefix="finance-v26-233-prepare-") as temp:
        loaded = v226_repair._load_exact_runtime(repository_root, Path(temp))  # noqa: SLF001
    config = loaded["config"]
    if (
        config.model != "deepseek-v4-flash"
        or config.max_output_tokens != 16_384
        or config.request_body_overrides.get("thinking") != {"type": "enabled"}
    ):
        _fail("freeze.model", "exact 16K Thinking model profile differs")
    preparation = models.make_identity(
        models.ExecutionPreparation,
        {
            "external_decision_id": external.decision_id,
            "v26_232_manifest_id": manifest232["manifest_id"],
            "v26_232_artifact_root": manifest232["artifact_root"],
            "v26_229_manifest_id": manifest229["manifest_id"],
            "v26_229_artifact_root": manifest229["artifact_root"],
            "v26_229_source_authority_audit_id": source.audit.audit_id,
            "v26_229_request_replay_audit_id": replay.audit_id,
            "recovery_population_id": population.population_id,
            "recovery_job_ids": authorization.recovery_job_ids,
        },
        field="preparation_id",
        prefix=models.ExecutionPreparation.prefix(),
    )
    ledger = repository_root / LEDGER_DIR / f"{_safe(authorization.authorization_id)}.json"
    if output_dir.exists() or ledger.exists():
        raise FileExistsError("v26.233 authorization was already consumed or output exists")
    return PreparedRecoveryExecution(
        repository_root=repository_root,
        package_root=package_root,
        output_dir=output_dir,
        ledger_path=ledger,
        review_bytes=review,
        external_decision=external,
        authorization=authorization,
        authorization_file_bytes=auth_bytes,
        admission=admission,
        preparation=preparation,
        recovery_population=population,
        source=source,
        replay=replay,
        manifest=loaded["manifest"],
        implementation=loaded["implementation"],
        frozen_parents=loaded["parents"],
        runtime=loaded["runtime"],
        config=config,
        bindings=loaded["bindings"],
    )


def _execution_source(repository_root: Path) -> models.ExecutionSourceIdentity:
    commit, tree = v224._git_identity(repository_root)  # noqa: SLF001
    members: list[models.SourceMember] = []
    for relative in IMPLEMENTATION_PATHS:
        current = (repository_root / relative).read_bytes()
        committed = subprocess.run(
            ("git", "show", f"{commit}:{relative}"),
            cwd=repository_root,
            check=True,
            capture_output=True,
        ).stdout
        if current != committed:
            _fail("source.member", f"execution source differs from commit:{relative}")
        members.append(
            models.SourceMember(
                relative_path=relative, sha256=_sha(current), byte_count=len(current)
            )
        )
    return models.make_identity(
        models.ExecutionSourceIdentity,
        {
            "source_commit": commit,
            "source_tree": tree,
            "members": tuple(members),
            "member_set_sha256": models.canonical_sha256(
                tuple(item.model_dump(mode="json") for item in members)
            ),
        },
        field="source_id",
        prefix=models.ExecutionSourceIdentity.prefix(),
    )


class RecoveryTransport(v224.LiveV209Transport):
    def __init__(
        self,
        *,
        source_exit_authority: Any,
        client: Any,
        journal: v224.ProviderJournal,
        historical_job_id: str,
        public_prefix: tuple[dict[str, Any], ...],
        source_row: v229_models.V226SourceRow,
        replay_row: v229_models.RequestReplayRow,
    ) -> None:
        super().__init__(
            source_exit_authority=source_exit_authority,
            client=client,
            journal=journal,
            job_id=historical_job_id,
        )
        self._public_prefix = public_prefix
        self._source_row = source_row
        self._replay_row = replay_row
        self._dispatch_count = 0
        self._local_replay_count = 0
        self._exact_failed_request_reissue_count = 0
        self._primary_request_count = sum(phase != "correction" for phase in replay_row.phases[:-1])
        self._total_usage_tokens = sum(
            item.input_tokens + item.output_tokens for item in source_row.provider_calls[:-1]
        )

    @property
    def local_replay_count(self) -> int:
        return self._local_replay_count

    @property
    def exact_failed_request_reissue_count(self) -> int:
        return self._exact_failed_request_reissue_count

    def send(self, dispatch: Any) -> Any:
        index = self._dispatch_count
        if index >= len(self._replay_row.request_sha256s) and (
            len(self.provider_calls) + self._replay_row.successful_prefix_call_count >= 23
        ):
            raise RecoveryExecutionFailure("combined Provider-call bound would be exceeded")
        request = v224.v209_models.canonical_bytes(dict(dispatch.request_body))
        if index < self._replay_row.successful_prefix_call_count:
            call = self._source_row.provider_calls[index]
            if (
                _sha(request) != self._replay_row.request_sha256s[index]
                or len(request) != call.request_byte_count
                or dispatch.certificate.certificate_id != call.certificate_id
                or dispatch.receipt.receipt_id != call.pre_transport_receipt_id
                or dispatch.certificate.phase != self._replay_row.phases[index]
            ):
                raise RecoveryExecutionFailure("local successful-prefix replay authority differs")
            self.queue(self._public_prefix[index])
            value = v224.v217_runtime.ExitTracingScriptedTransport.send(self, dispatch)
            self._dispatch_count += 1
            self._local_replay_count += 1
            return value
        if index == self._replay_row.successful_prefix_call_count:
            if (
                _sha(request) != self._replay_row.failed_request_sha256
                or len(request) != self._replay_row.failed_request_byte_count
                or dispatch.certificate.certificate_id
                != self._replay_row.failed_request_certificate_id
                or dispatch.receipt.receipt_id != self._replay_row.failed_pre_transport_receipt_id
                or dispatch.certificate.phase != self._replay_row.phases[-1]
            ):
                raise RecoveryExecutionFailure(
                    "first online request is not the exact captured failed request"
                )
            self._exact_failed_request_reissue_count += 1
            if self._exact_failed_request_reissue_count != 1:
                raise RecoveryExecutionFailure(
                    "captured failed request was reissued more than once"
                )
        try:
            value = super().send(dispatch)
        finally:
            self._dispatch_count += 1
        return value


def _runtime_view(prepared: PreparedRecoveryExecution) -> Any:
    return prepared


def _subsequent_decision(
    evidence: models.SubsequentActionEvidence,
) -> models.SubsequentActionDecision:
    parser = evidence.evidence_kind == "subsequent_action_parser_rejection"
    return models.make_identity(
        models.SubsequentActionDecision,
        {
            "evidence": evidence,
            "evidence_sha256": models.canonical_sha256(evidence),
            "terminal_kind": (
                "first_response_abi_invalid" if parser else "first_action_reference_invalid"
            ),
            "terminal_policy_id": "fresh_kernel_terminal_policy:"
            + (
                "b5fb980fc0c80b2c72a964d538cf487e9a27403aff0ebe4e88ffb3b29847c04f"
                if parser
                else "443b4c076ea4d694590fbafcd66d1c23681679bd24368ad43a354299c480fe3b"
            ),
            "derivation_rule": (
                "subsequent_action_exact_parser_rejection"
                if parser
                else "subsequent_action_parsed_reference_not_current"
            ),
        },
        field="decision_id",
        prefix=models.SubsequentActionDecision.prefix(),
    )


def _derive_recovery_terminal(
    *,
    prepared: PreparedRecoveryExecution,
    run_start: models.RecoveryRunStartReceipt,
    recovery_job: v229_models.RecoveryPopulationJob,
    outcome: Any,
    public_value: Any,
    records: tuple[Any, ...],
    runner_authority: Any,
    failure_dispatcher: Any,
) -> v224.TerminalProjection:
    record = outcome.record
    if record.phase == "subsequent_action" and record.typed_terminal in {
        "first_response_abi_invalid",
        "first_action_reference_invalid",
    }:
        if not isinstance(public_value, dict):
            raise RecoveryExecutionFailure("subsequent-Action terminal lacks public object")
        kind: models.SubsequentEvidenceKind = (
            "subsequent_action_parser_rejection"
            if record.typed_terminal == "first_response_abi_invalid"
            else "subsequent_action_reference_failure"
        )
        evidence = models.make_identity(
            models.SubsequentActionEvidence,
            {
                "evidence_kind": kind,
                "run_start_receipt_id": run_start.receipt_id,
                "recovery_job_id": recovery_job.recovery_job_id,
                "recovery_candidate_id": recovery_job.candidate.candidate_id,
                "historical_job_id": recovery_job.candidate.historical_job_id,
                "job_ordinal": recovery_job.candidate.job_ordinal,
                "invocation_records": tuple(
                    item.model_dump(mode="json", warnings=False) for item in records
                ),
                "public_payload": public_value,
                "public_payload_sha256": models.canonical_sha256(public_value),
                "current_state_id": record.current_state_id,
                "current_candidate_action_ids": record.candidate_action_ids,
            },
            field="evidence_id",
            prefix=models.SubsequentActionEvidence.prefix(),
        )
        decision = _subsequent_decision(evidence)
        policies = {
            item.terminal_kind: item.policy_id
            for item in prepared.bindings.terminal_registry.policies
            if item.registration_status == "reachable"
        }
        if policies.get(decision.terminal_kind) != decision.terminal_policy_id:
            raise RecoveryExecutionFailure("subsequent-Action terminal policy differs")
        return v224.TerminalProjection(
            terminal_kind=decision.terminal_kind,
            terminal_source="current_state_runner_observation",
            evidence=evidence,
            decision=decision,
        )
    return v224._derive_terminal(  # noqa: SLF001
        prepared=cast(Any, prepared),
        outcome=outcome,
        job_id=recovery_job.candidate.historical_job_id,
        public_value=public_value,
        records=records,
        runner_authority=runner_authority,
        failure_dispatcher=failure_dispatcher,
    )


def _layer_namespace(recovery_job_id: str, kind: str) -> str:
    return v224.outcome_authority.canonical_hash(
        {
            "recovery_job_id": recovery_job_id,
            "layer_kind": kind,
            "schema_version": models.SCHEMA_VERSION,
        },
        prefix=f"finance_v26_233_recovery_{kind}_namespace:",
    )


def _write_layer(
    *,
    prepared: PreparedRecoveryExecution,
    run_start: models.RecoveryRunStartReceipt,
    recovery_job: v229_models.RecoveryPopulationJob,
    kind: models.LayerKind,
    sequence: int,
    terminal_kind: Any,
    terminal_source: Any,
    parents: tuple[models.RecoveryLayerDescriptor, ...],
    provider_calls: tuple[Any, ...],
    payload: dict[str, Any],
) -> models.RecoveryLayerDescriptor:
    relative = f"recovery_evidence/{kind}/{_safe(recovery_job.recovery_job_id)}.json"
    body = _encoded(payload)
    _durable_write(prepared.output_dir / relative, body)
    return models.make_identity(
        models.RecoveryLayerDescriptor,
        {
            "run_start_receipt_id": run_start.receipt_id,
            "recovery_job_id": recovery_job.recovery_job_id,
            "historical_job_id": recovery_job.candidate.historical_job_id,
            "job_ordinal": recovery_job.candidate.job_ordinal,
            "layer_kind": kind,
            "namespace_id": _layer_namespace(recovery_job.recovery_job_id, kind),
            "relative_path": relative,
            "terminal_kind": terminal_kind,
            "terminal_source": terminal_source,
            "parent_descriptor_ids": tuple(item.descriptor_id for item in parents),
            "provider_call_descriptor_ids": tuple(item.descriptor_id for item in provider_calls),
            "payload_sha256": _sha(body),
            "payload_byte_count": len(body),
            "persisted_sequence": sequence,
        },
        field="descriptor_id",
        prefix=models.RecoveryLayerDescriptor.prefix(),
    )


def _persist_chain(
    *,
    prepared: PreparedRecoveryExecution,
    run_start: models.RecoveryRunStartReceipt,
    recovery_job: v229_models.RecoveryPopulationJob,
    replay_row: v229_models.RequestReplayRow,
    projection: v224.TerminalProjection,
    records: tuple[Any, ...],
    provider_calls: tuple[Any, ...],
    failure_dispatcher: Any,
) -> models.RecoveryJobRecord:
    if isinstance(projection.evidence, models.SubsequentActionEvidence):
        rederived = _subsequent_decision(projection.evidence)
        persistence_binding_id = prepared.bindings.main_persistence.binding_id
    elif projection.terminal_source == "current_state_runner_observation":
        rederived = v224.v213_runtime.ObservationDerivedTerminalDispatcher(
            prepared.bindings.main_dispatcher
        ).dispatch(projection.evidence)
        persistence_binding_id = prepared.bindings.main_persistence.binding_id
    else:
        v224.v218_runtime.ExactRegistryComplementAuthority(
            registry=prepared.bindings.terminal_registry,
            expected_binding=prepared.bindings.failure_complement,
        ).admit(prepared.bindings.failure_complement)
        rederived = failure_dispatcher.dispatch(projection.evidence)
        persistence_binding_id = prepared.bindings.failure_persistence.binding_id
    if models.canonical_bytes(rederived) != models.canonical_bytes(projection.decision):
        raise RecoveryExecutionFailure("terminal decision rederivation differs")
    common = {
        "run_start_receipt_id": run_start.receipt_id,
        "authorization_id": prepared.authorization.authorization_id,
        "recovery_job_id": recovery_job.recovery_job_id,
        "recovery_candidate_id": recovery_job.candidate.candidate_id,
        "historical_job_id": recovery_job.candidate.historical_job_id,
        "job_ordinal": recovery_job.candidate.job_ordinal,
        "successful_prefix_projection_count": replay_row.successful_prefix_call_count,
        "successful_prefix_provider_reissue_count": 0,
        "exact_failed_request_reissue_count": 1,
        "terminal_kind": projection.terminal_kind,
        "terminal_source": projection.terminal_source,
        "formal_empirical_row": False,
        "historical_v26_226_mutation": False,
        "schema_version": models.SCHEMA_VERSION,
    }
    raw = _write_layer(
        prepared=prepared,
        run_start=run_start,
        recovery_job=recovery_job,
        kind="raw",
        sequence=0,
        terminal_kind=projection.terminal_kind,
        terminal_source=projection.terminal_source,
        parents=(),
        provider_calls=provider_calls,
        payload={
            **common,
            "persistence_binding_id": persistence_binding_id,
            "source_row_id": replay_row.source_row_id,
            "observed_evidence": projection.evidence.model_dump(mode="json", warnings=False),
            "derived_terminal_decision": projection.decision.model_dump(
                mode="json", warnings=False
            ),
            "invocation_records": tuple(
                item.model_dump(mode="json", warnings=False) for item in records
            ),
            "fresh_provider_calls": tuple(
                item.model_dump(mode="json", warnings=False) for item in provider_calls
            ),
        },
    )
    result = _write_layer(
        prepared=prepared,
        run_start=run_start,
        recovery_job=recovery_job,
        kind="result",
        sequence=1,
        terminal_kind=projection.terminal_kind,
        terminal_source=projection.terminal_source,
        parents=(raw,),
        provider_calls=provider_calls,
        payload={**common, "raw_descriptor": raw.model_dump(mode="json")},
    )
    trace = _write_layer(
        prepared=prepared,
        run_start=run_start,
        recovery_job=recovery_job,
        kind="trace",
        sequence=2,
        terminal_kind=projection.terminal_kind,
        terminal_source=projection.terminal_source,
        parents=(raw, result),
        provider_calls=provider_calls,
        payload={
            **common,
            "raw_descriptor": raw.model_dump(mode="json"),
            "result_descriptor": result.model_dump(mode="json"),
            "invocation_records": tuple(
                item.model_dump(mode="json", warnings=False) for item in records
            ),
            "fresh_provider_calls": tuple(
                item.model_dump(mode="json", warnings=False) for item in provider_calls
            ),
        },
    )
    outcome = _write_layer(
        prepared=prepared,
        run_start=run_start,
        recovery_job=recovery_job,
        kind="outcome",
        sequence=3,
        terminal_kind=projection.terminal_kind,
        terminal_source=projection.terminal_source,
        parents=(trace,),
        provider_calls=provider_calls,
        payload={**common, "trace_descriptor": trace.model_dump(mode="json")},
    )
    checkpoint = _write_layer(
        prepared=prepared,
        run_start=run_start,
        recovery_job=recovery_job,
        kind="checkpoint",
        sequence=4,
        terminal_kind=projection.terminal_kind,
        terminal_source=projection.terminal_source,
        parents=(outcome,),
        provider_calls=provider_calls,
        payload={**common, "outcome_descriptor": outcome.model_dump(mode="json")},
    )
    return models.make_identity(
        models.RecoveryJobRecord,
        {
            "run_start_receipt_id": run_start.receipt_id,
            "authorization_id": prepared.authorization.authorization_id,
            "recovery_job_id": recovery_job.recovery_job_id,
            "recovery_candidate_id": recovery_job.candidate.candidate_id,
            "historical_job_id": recovery_job.candidate.historical_job_id,
            "job_ordinal": recovery_job.candidate.job_ordinal,
            "failed_request_phase": replay_row.phases[-1],
            "successful_prefix_projection_count": replay_row.successful_prefix_call_count,
            "provider_calls": provider_calls,
            "terminal_kind": projection.terminal_kind,
            "terminal_source": projection.terminal_source,
            "invocation_record_count": len(records),
            "layers": (raw, result, trace, outcome, checkpoint),
        },
        field="record_id",
        prefix=models.RecoveryJobRecord.prefix(),
    )


def _execute_job(
    *,
    prepared: PreparedRecoveryExecution,
    run_start: models.RecoveryRunStartReceipt,
    recovery_job: v229_models.RecoveryPopulationJob,
    historical_job: Any,
    source_row: v229_models.V226SourceRow,
    replay_row: v229_models.RequestReplayRow,
    public_prefix: tuple[dict[str, Any], ...],
    client: Any,
) -> models.RecoveryJobRecord | models.RecoveryFailureRecord:
    transport: RecoveryTransport | None = None
    try:
        authority_root = (
            prepared.output_dir / "source_authority" / _safe(recovery_job.recovery_job_id)
        )
        source_exit, runner_authority, failure_dispatcher = v224._failure_runtime(  # noqa: SLF001
            prepared=cast(Any, _runtime_view(prepared)),
            job_id=historical_job.job_id,
            root=authority_root,
        )
        journal = v224.ProviderJournal(
            root=prepared.output_dir,
            run_start=cast(Any, run_start),
            job_id=recovery_job.recovery_job_id,
        )
        transport = RecoveryTransport(
            source_exit_authority=source_exit,
            client=client,
            journal=journal,
            historical_job_id=historical_job.job_id,
            public_prefix=public_prefix,
            source_row=source_row,
            replay_row=replay_row,
        )
        runner = v224._online_runner(  # noqa: SLF001
            prepared=cast(Any, _runtime_view(prepared)),
            transport=transport,
            source_exit=source_exit,
            runner_authority=runner_authority,
        )
        context = v224.v209._context_for_job(  # noqa: SLF001
            job=historical_job, parents=prepared.frozen_parents, prepared=prepared.runtime
        )
        state = v224.frozen_runtime._initialize(context)  # noqa: SLF001
        records: list[Any] = []
        invocation_index = 0
        projection: v224.TerminalProjection | None = None
        while state.current_index < len(state.ordered_components):
            action = runner.invoke_action(
                job=historical_job, invocation_index=invocation_index, state=state
            )
            invocation_index += 1
            records.append(action.record)
            if action.terminal is not None:
                projection = _derive_recovery_terminal(
                    prepared=prepared,
                    run_start=run_start,
                    recovery_job=recovery_job,
                    outcome=action,
                    public_value=transport.last_response,
                    records=tuple(records),
                    runner_authority=runner_authority,
                    failure_dispatcher=failure_dispatcher,
                )
                break
            if action.record.action_accepted is True:
                continue
            if not isinstance(
                action.runtime_output, v224.step_runtime.PublicTypedRejectionObservation
            ):
                raise RecoveryExecutionFailure("nonterminal Action rejection lacks public feedback")
            correction = runner.invoke_correction(
                job=historical_job, invocation_index=invocation_index, state=state
            )
            invocation_index += 1
            records.append(correction.record)
            if correction.terminal is not None or correction.record.action_accepted is not True:
                projection = _derive_recovery_terminal(
                    prepared=prepared,
                    run_start=run_start,
                    recovery_job=recovery_job,
                    outcome=correction,
                    public_value=transport.last_response,
                    records=tuple(records),
                    runner_authority=runner_authority,
                    failure_dispatcher=failure_dispatcher,
                )
                break
        if projection is None:
            final = runner.invoke_final(
                job=historical_job, invocation_index=invocation_index, state=state, context=context
            )
            records.append(final.record)
            projection = _derive_recovery_terminal(
                prepared=prepared,
                run_start=run_start,
                recovery_job=recovery_job,
                outcome=final,
                public_value=transport.last_response,
                records=tuple(records),
                runner_authority=runner_authority,
                failure_dispatcher=failure_dispatcher,
            )
        if (
            transport.local_replay_count != replay_row.successful_prefix_call_count
            or transport.exact_failed_request_reissue_count != 1
            or not transport.provider_calls
        ):
            raise RecoveryExecutionFailure("Recovery replay/reissue closure differs")
        return _persist_chain(
            prepared=prepared,
            run_start=run_start,
            recovery_job=recovery_job,
            replay_row=replay_row,
            projection=projection,
            records=tuple(records),
            provider_calls=transport.provider_calls,
            failure_dispatcher=failure_dispatcher,
        )
    except BaseException as error:
        if isinstance(error, (KeyboardInterrupt, SystemExit)):
            raise
        calls = () if transport is None else transport.provider_calls
        if transport is None or transport.exact_failed_request_reissue_count != 1 or not calls:
            raise RecoveryExecutionFailure(
                "job failed before the exact captured request was durably reissued"
            ) from error
        provider_failed = any(item.status != "succeeded" for item in calls)
        return models.make_identity(
            models.RecoveryFailureRecord,
            {
                "run_start_receipt_id": run_start.receipt_id,
                "authorization_id": prepared.authorization.authorization_id,
                "recovery_job_id": recovery_job.recovery_job_id,
                "recovery_candidate_id": recovery_job.candidate.candidate_id,
                "historical_job_id": recovery_job.candidate.historical_job_id,
                "job_ordinal": recovery_job.candidate.job_ordinal,
                "failed_request_phase": replay_row.phases[-1],
                "successful_prefix_projection_count": replay_row.successful_prefix_call_count,
                "provider_calls": calls,
                "failure_kind": "unbound_provider_failure" if provider_failed else "host_failure",
                "error_sha256": _sha(
                    f"{type(error).__module__}:{type(error).__qualname__}:{error}".encode()
                ),
            },
            field="record_id",
            prefix=models.RecoveryFailureRecord.prefix(),
        )


def _consume(
    prepared: PreparedRecoveryExecution, source: models.ExecutionSourceIdentity
) -> tuple[models.AuthorizationConsumptionReceipt, models.RecoveryRunStartReceipt]:
    consumption = models.make_identity(
        models.AuthorizationConsumptionReceipt,
        {
            "preparation_id": prepared.preparation.preparation_id,
            "consumed_at_utc": _utc_now(),
        },
        field="receipt_id",
        prefix=models.AuthorizationConsumptionReceipt.prefix(),
    )
    _durable_write(prepared.ledger_path, _encoded(consumption))
    prepared.output_dir.mkdir(parents=True, exist_ok=False)
    _durable_write(
        prepared.output_dir / "authorization_consumption_receipt.json", _encoded(consumption)
    )
    run_start = models.make_identity(
        models.RecoveryRunStartReceipt,
        {
            "consumption_receipt_id": consumption.receipt_id,
            "preparation_id": prepared.preparation.preparation_id,
            "execution_source_id": source.source_id,
            "execution_source_commit": source.source_commit,
            "execution_source_tree": source.source_tree,
            "started_at_utc": _utc_now(),
        },
        field="receipt_id",
        prefix=models.RecoveryRunStartReceipt.prefix(),
    )
    if prepared.ledger_path.read_bytes() != _encoded(consumption):
        _fail("ingress.ledger", "authorization ledger bytes differ")
    _durable_write(prepared.output_dir / "recovery_run_start_receipt.json", _encoded(run_start))
    return consumption, run_start


def _write_ingress(
    prepared: PreparedRecoveryExecution, source: models.ExecutionSourceIdentity
) -> None:
    values = {
        "external_review.txt": prepared.review_bytes,
        "operator_directive.txt": models.OPERATOR_DIRECTIVE.encode("utf-8"),
        "external_execution_decision.json": _encoded(prepared.external_decision),
        "execution_source_identity.json": _encoded(source),
        "execution_preparation.json": _encoded(prepared.preparation),
        "exact_v26_232_online_execution_authorization.json": prepared.authorization_file_bytes,
        "precredential_admission.json": _encoded(prepared.admission),
    }
    for name, payload in values.items():
        _durable_write(prepared.output_dir / name, payload)


def execute(
    *,
    prepared: PreparedRecoveryExecution,
    workers: int = MAX_WORKERS,
    client_factory: type[v224.ExactRequestBodyDeepSeekClient] = v224.ExactRequestBodyDeepSeekClient,
) -> models.ExecutionSummary:
    if workers < 1 or workers > 16:
        _fail("scope.workers", "Recovery worker count must be in [1,16]")
    source_identity = _execution_source(prepared.repository_root)
    consumption, run_start = _consume(prepared, source_identity)
    _write_ingress(prepared, source_identity)
    v224._load_env_key(prepared.package_root, prepared.config.api_key_env)  # noqa: SLF001
    client = client_factory(prepared.config)
    historical_jobs = {item.job_id: item for item in prepared.manifest.jobs}
    source_rows = {item.job_ordinal: item for item in prepared.source.audit.source_rows}
    replay_rows = {item.job_ordinal: item for item in prepared.replay.rows}
    recovery_jobs = tuple(
        sorted(prepared.recovery_population.jobs, key=lambda item: item.candidate.job_ordinal)
    )
    outputs: dict[int, models.RecoveryJobRecord | models.RecoveryFailureRecord] = {}
    pending: dict[Future[models.RecoveryJobRecord | models.RecoveryFailureRecord], int] = {}
    next_index = 0
    with ThreadPoolExecutor(max_workers=workers) as pool:
        while next_index < min(workers, len(recovery_jobs)):
            job = recovery_jobs[next_index]
            ordinal = job.candidate.job_ordinal
            pending[
                pool.submit(
                    _execute_job,
                    prepared=prepared,
                    run_start=run_start,
                    recovery_job=job,
                    historical_job=historical_jobs[job.candidate.historical_job_id],
                    source_row=source_rows[ordinal],
                    replay_row=replay_rows[ordinal],
                    public_prefix=prepared.source.public_prefixes[ordinal],
                    client=client,
                )
            ] = ordinal
            next_index += 1
        while pending:
            completed, _ = wait(tuple(pending), return_when=FIRST_COMPLETED)
            for future in completed:
                ordinal = pending.pop(future)
                output = future.result()
                outputs[ordinal] = output
                directory = (
                    "recovery_job_records"
                    if isinstance(output, models.RecoveryJobRecord)
                    else "recovery_failures"
                )
                _durable_write(
                    prepared.output_dir / directory / f"job_{ordinal:03d}.json", _encoded(output)
                )
                if next_index < len(recovery_jobs):
                    job = recovery_jobs[next_index]
                    queued = job.candidate.job_ordinal
                    pending[
                        pool.submit(
                            _execute_job,
                            prepared=prepared,
                            run_start=run_start,
                            recovery_job=job,
                            historical_job=historical_jobs[job.candidate.historical_job_id],
                            source_row=source_rows[queued],
                            replay_row=replay_rows[queued],
                            public_prefix=prepared.source.public_prefixes[queued],
                            client=client,
                        )
                    ] = queued
                    next_index += 1
    expected_ordinals = tuple(item.candidate.job_ordinal for item in recovery_jobs)
    if tuple(sorted(outputs)) != expected_ordinals:
        _fail("execution.coverage", "exact 33-Job Recovery scheduling did not close")
    records = tuple(
        cast(models.RecoveryJobRecord, outputs[i])
        for i in sorted(outputs)
        if isinstance(outputs[i], models.RecoveryJobRecord)
    )
    failures = tuple(
        cast(models.RecoveryFailureRecord, outputs[i])
        for i in sorted(outputs)
        if isinstance(outputs[i], models.RecoveryFailureRecord)
    )
    calls = tuple(call for item in (*records, *failures) for call in item.provider_calls)
    terminals = {kind: 0 for kind in v224.models.TERMINAL_KINDS}
    for item in records:
        terminals[item.terminal_kind] += 1
    failure_partition = {"unbound_provider_failure": 0, "host_failure": 0}
    for item in failures:
        failure_partition[item.failure_kind] += 1
    phases = {"first_action": 0, "subsequent_action": 0, "final": 0}
    for item in (*records, *failures):
        phases[item.failed_request_phase] += 1
    status: Literal["completed", "incomplete"] = "completed" if not failures else "incomplete"
    summary = models.make_identity(
        models.ExecutionSummary,
        {
            "preparation_id": prepared.preparation.preparation_id,
            "consumption_receipt_id": consumption.receipt_id,
            "run_start_receipt_id": run_start.receipt_id,
            "execution_status": status,
            "records": records,
            "failures": failures,
            "terminal_record_count": len(records),
            "failure_record_count": len(failures),
            "provider_call_count": len(calls),
            "input_tokens": sum(item.input_tokens for item in calls),
            "output_tokens": sum(item.output_tokens for item in calls),
            "terminal_partition": terminals,
            "failure_partition": failure_partition,
            "failed_request_phase_partition": phases,
            "five_layer_file_count": len(records) * 5,
        },
        field="summary_id",
        prefix=models.ExecutionSummary.prefix(),
    )
    _durable_write(prepared.output_dir / "execution_summary.json", _encoded(summary))
    transition = models.make_identity(
        models.Transition,
        {
            "summary_id": summary.summary_id,
            "execution_status": status,
            "status": "COMPLETED_AWAITING_POSTRUN_INDEPENDENT_AUDIT"
            if status == "completed"
            else "INCOMPLETE_AWAITING_POSTRUN_INDEPENDENT_AUDIT",
        },
        field="transition_id",
        prefix=models.Transition.prefix(),
    )
    _durable_write(prepared.output_dir / "prospective_transition.json", _encoded(transition))
    artifact = v224.models.artifact_manifest(
        RUN_ID,
        {
            path.relative_to(prepared.output_dir).as_posix(): path.read_bytes()
            for path in prepared.output_dir.rglob("*")
            if path.is_file() and path.name != "execution_artifact_manifest.json"
        },
    )
    _durable_write(prepared.output_dir / "execution_artifact_manifest.json", _encoded(artifact))
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository-root", type=Path, default=Path.cwd())
    parser.add_argument("--external-audit", type=Path, required=True)
    parser.add_argument("--prepare-only", action="store_true")
    parser.add_argument("--workers", type=int, default=MAX_WORKERS)
    args = parser.parse_args()
    root = args.repository_root.resolve()
    prepared = prepare_execution(
        repository_root=root,
        output_dir=root / OUTPUT_DIR,
        external_review_path=args.external_audit,
    )
    if args.prepare_only:
        print(models.canonical_bytes(prepared.preparation).decode("utf-8"))
        return
    summary = execute(prepared=prepared, workers=args.workers)
    print(models.canonical_bytes(summary).decode("utf-8"))


if __name__ == "__main__":
    main()
