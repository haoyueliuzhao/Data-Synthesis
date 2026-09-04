# ruff: noqa: E501
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Final, NoReturn, cast

from pydantic import ValidationError

from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_capability_all_typed_rejection_public_feedback_runtime as step_runtime,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_capability_job_bound_multistep_outcome_preflight_runtime as frozen_runtime,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_exact_v209_parent_bound_online_execution_repair as v226,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_exact_v209_parent_bound_online_execution_repair_models as v226_models,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_exact_v209_subsequent_action_evidence_domain_closure_models as models,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_repaired_full_condition_final_request_contract_continuity_repair_preflight as v209,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_repaired_full_condition_final_request_contract_continuity_repair_preflight_models as v209_models,
)

RUN_ID: Final = (
    "finance_v26_227_fresh_exact_v209_subsequent_action_parser_reference_"
    "evidence_domain_closure_preflight_v2_20260904"
)
OUTPUT_DIR: Final = f"trusted_data_synthesis/artifacts/vtdo_experiment/{RUN_ID}"
V226_DIR: Final = (
    "trusted_data_synthesis/artifacts/vtdo_experiment/"
    "finance_v26_226_fresh_exact_v209_parent_bound_postresponse_serializer_repair_"
    "exact_192_job_replacement_online_execution_v1_20260904"
)
MODELS_FILE: Final = (
    "trusted_data_synthesis/src/trusted_synthesis/experiments/vtdo_experiment/"
    "phase1_v26_fresh_exact_v209_subsequent_action_evidence_domain_closure_models.py"
)
PREFLIGHT_FILE: Final = (
    "trusted_data_synthesis/src/trusted_synthesis/experiments/vtdo_experiment/"
    "phase1_v26_fresh_exact_v209_subsequent_action_evidence_domain_closure_preflight.py"
)
IMPLEMENTATION_FILES: Final = tuple(sorted((MODELS_FILE, PREFLIGHT_FILE)))
V226_MANIFEST_FILE: Final = "execution_artifact_manifest.json"
V226_SUMMARY_FILE: Final = "execution_summary.json"
V226_TRANSITION_FILE: Final = "prospective_transition.json"


class V227Error(ValueError):
    def __init__(self, stage: str, reason: str) -> None:
        super().__init__(reason)
        self.stage = stage
        self.reason = reason


def _fail(stage: str, reason: str) -> NoReturn:
    raise V227Error(stage, reason)


def _sha(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _safe(value: str) -> str:
    return _sha(value.encode("utf-8"))


def _load_bytes(payload: bytes) -> dict[str, Any]:
    value = json.loads(payload)
    if not isinstance(value, dict):
        _fail("json.object", "expected one JSON object")
    return cast(dict[str, Any], value)


def _load(path: Path) -> dict[str, Any]:
    return _load_bytes(path.read_bytes())


def _encoded(value: Any) -> bytes:
    return models.canonical_bytes(value) + b"\n"


def _make(model_type: type[Any], values: dict[str, Any], field: str, prefix: str) -> Any:
    return models.make_identity(model_type, values, field=field, prefix=prefix)


def _git(repository_root: Path, *arguments: str) -> bytes:
    completed = subprocess.run(
        ("git", *arguments), cwd=repository_root, check=False, capture_output=True
    )
    if completed.returncode:
        _fail("source.git", completed.stderr.decode("utf-8", errors="replace"))
    return completed.stdout


def _all_files(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file()
    }


@dataclass(frozen=True)
class FrozenV226:
    freeze: models.V226Freeze
    files: dict[str, bytes]
    artifact: v226_models.ArtifactManifest
    summary: v226_models.ExecutionSummary
    transition: v226_models.Transition
    host_failures: tuple[v226_models.JobFailureRecord, ...]
    provider_failures: tuple[v226_models.JobFailureRecord, ...]


def _failure_source_projection(
    relative_path: str,
    payload: bytes,
    record: v226_models.JobFailureRecord,
) -> dict[str, Any]:
    return {
        "relative_path": relative_path,
        "sha256": _sha(payload),
        "byte_count": len(payload),
        "record_sha256": models.canonical_sha256(record),
        "record_id": record.record_id,
        "job_id": record.job_id,
        "job_ordinal": record.job_ordinal,
        "failure_kind": record.failure_kind,
        "error_sha256": record.error_sha256,
        "provider_call_ids": tuple(item.provider_call_id for item in record.provider_calls),
    }


def _verify_v226(*, repository_root: Path, external_authorization_id: str) -> FrozenV226:
    root = repository_root / V226_DIR
    files = _all_files(root)
    if len(files) != 3_428 or sum(map(len, files.values())) != 99_765_014:
        _fail("freeze.v226.geometry", "v26.226 formal directory geometry differs")
    manifest_bytes = files.get(V226_MANIFEST_FILE, b"")
    if _sha(manifest_bytes) != models.V226_MANIFEST_SHA256:
        _fail("freeze.v226.manifest_bytes", "v26.226 Manifest file differs")
    artifact = v226_models.ArtifactManifest.model_validate(_load_bytes(manifest_bytes))
    members = {item.relative_path: item for item in artifact.members}
    if (
        artifact.manifest_id != models.V226_MANIFEST_ID
        or artifact.artifact_root != models.V226_ARTIFACT_ROOT
        or len(members) != 3_427
        or artifact.total_member_bytes != 99_047_004
        or set(members) != set(files) - {V226_MANIFEST_FILE}
    ):
        _fail("freeze.v226.manifest", "v26.226 Manifest or Root differs")
    for relative_path, member in members.items():
        payload = files[relative_path]
        if len(payload) != member.byte_count or _sha(payload) != member.sha256:
            _fail("freeze.v226.member", f"v26.226 member differs:{relative_path}")

    summary_bytes = files[V226_SUMMARY_FILE]
    transition_bytes = files[V226_TRANSITION_FILE]
    if (
        _sha(summary_bytes) != models.V226_SUMMARY_SHA256
        or _sha(transition_bytes) != models.V226_TRANSITION_SHA256
    ):
        _fail("freeze.v226.summary_transition_bytes", "v26.226 summary/transition bytes differ")
    summary = v226_models.ExecutionSummary.model_validate(_load_bytes(summary_bytes))
    transition = v226_models.Transition.model_validate(_load_bytes(transition_bytes))
    if (
        summary.summary_id != models.V226_SUMMARY_ID
        or transition.transition_id != models.V226_TRANSITION_ID
        or summary.execution_status != "incomplete"
        or summary.completed_job_record_count != 156
        or summary.failure_record_count != 36
        or summary.failure_partition != {"unbound_provider_failure": 33, "host_failure": 3}
        or summary.authorization_consumption_count != 1
        or transition.execution_status != "incomplete"
        or transition.replacement_or_recovery_authorized
    ):
        _fail("freeze.v226.state", "v26.226 immutable execution state differs")

    actual_tree = (
        _git(repository_root, "rev-parse", f"{models.V226_SOURCE_COMMIT}^{{tree}}").decode().strip()
    )
    if actual_tree != models.V226_SOURCE_TREE:
        _fail("freeze.v226.source", "v26.226 source commit/tree relation differs")

    host: list[v226_models.JobFailureRecord] = []
    provider: list[v226_models.JobFailureRecord] = []
    host_projection: list[dict[str, Any]] = []
    provider_projection: list[dict[str, Any]] = []
    summary_by_ordinal = {item.job_ordinal: item for item in summary.failure_records}
    if len(summary_by_ordinal) != 36:
        _fail("freeze.v226.failure_set", "v26.226 failure ordinal set is not unique")
    for ordinal, embedded in sorted(summary_by_ordinal.items()):
        relative_path = f"job_failures/job_{ordinal:03d}.json"
        failure_payload = files.get(relative_path)
        if failure_payload is None:
            _fail("freeze.v226.failure_path", f"missing {relative_path}")
        record = v226_models.JobFailureRecord.model_validate(_load_bytes(failure_payload))
        if failure_payload != _encoded(record) or record != embedded:
            _fail("freeze.v226.failure_bytes", f"failure row differs:{ordinal}")
        projection = _failure_source_projection(relative_path, failure_payload, record)
        if record.failure_kind == "host_failure":
            host.append(record)
            host_projection.append(projection)
        else:
            provider.append(record)
            provider_projection.append(projection)
    host_tuple = tuple(sorted(host, key=lambda item: item.job_ordinal))
    provider_tuple = tuple(sorted(provider, key=lambda item: item.job_ordinal))
    if (
        tuple(item.job_ordinal for item in host_tuple) != models.HOST_FAILURE_ORDINALS
        or tuple(item.job_id for item in host_tuple) != models.HOST_FAILURE_JOB_IDS
        or tuple(item.record_id for item in host_tuple) != models.HOST_FAILURE_RECORD_IDS
        or tuple(item.error_sha256 for item in host_tuple) != models.HOST_FAILURE_ERROR_SHA256S
        or len(provider_tuple) != 33
    ):
        _fail("freeze.v226.failure_partition", "v26.226 failure partition differs")

    # These set hashes are frozen constants in the schema.  Recomputing them here
    # prevents an equal-cardinality replacement of either source population.
    host_set_sha = models.canonical_sha256(tuple(host_projection))
    provider_set_sha = models.canonical_sha256(tuple(provider_projection))
    if (
        host_set_sha != models.V226Freeze.model_fields["host_failure_source_set_sha256"].default
        or provider_set_sha
        != models.V226Freeze.model_fields["unbound_provider_failure_exclusion_set_sha256"].default
    ):
        _fail("freeze.v226.failure_set_hash", "v26.226 host/provider source set differs")

    freeze = cast(
        models.V226Freeze,
        _make(
            models.V226Freeze,
            {
                "external_authorization_id": external_authorization_id,
                "host_failure_source_set_sha256": host_set_sha,
                "unbound_provider_failure_exclusion_set_sha256": provider_set_sha,
            },
            "freeze_id",
            "finance_v26_227_v226_freeze:",
        ),
    )
    return FrozenV226(
        freeze=freeze,
        files=files,
        artifact=artifact,
        summary=summary,
        transition=transition,
        host_failures=host_tuple,
        provider_failures=provider_tuple,
    )


def _external_authorization(
    external_review_path: Path,
) -> tuple[models.ExternalAuthorization, bytes, bytes]:
    review = external_review_path.read_bytes()
    directive = models.OPERATOR_DIRECTIVE.encode("utf-8")
    if (
        len(review) != models.EXTERNAL_REVIEW_BYTE_COUNT
        or _sha(review) != models.EXTERNAL_REVIEW_SHA256
        or len(directive) != 30
        or _sha(directive) != models.OPERATOR_DIRECTIVE_SHA256
    ):
        _fail("authorization.external", "external review or operator directive differs")
    authorization = cast(
        models.ExternalAuthorization,
        _make(
            models.ExternalAuthorization,
            {},
            "authorization_id",
            "finance_v26_227_external_authorization:",
        ),
    )
    return authorization, review, directive


def _source_identity(
    *, repository_root: Path, source_identity: tuple[str, str]
) -> models.SourceIdentity:
    commit, tree = source_identity
    actual_tree = _git(repository_root, "rev-parse", f"{commit}^{{tree}}").decode().strip()
    if actual_tree != tree:
        _fail("source.tree", "source commit/tree relation differs")
    members: list[models.SourceMember] = []
    for relative_path in IMPLEMENTATION_FILES:
        committed = _git(repository_root, "show", f"{commit}:{relative_path}")
        current = (repository_root / relative_path).read_bytes()
        if committed != current:
            _fail("source.working_tree", f"working source differs:{relative_path}")
        members.append(
            models.SourceMember(
                relative_path=relative_path,
                sha256=_sha(committed),
                byte_count=len(committed),
            )
        )
    member_payloads = tuple(item.model_dump(mode="json") for item in members)
    return cast(
        models.SourceIdentity,
        _make(
            models.SourceIdentity,
            {
                "source_commit": commit,
                "source_tree": tree,
                "implementation_members": tuple(members),
                "implementation_member_set_sha256": models.canonical_sha256(member_payloads),
            },
            "source_identity_id",
            "finance_v26_227_source_identity:",
        ),
    )


def _host_failure_row(
    *, root: Path, freeze_id: str, record: v226_models.JobFailureRecord
) -> models.HostFailureRow:
    relative_path = f"job_failures/job_{record.job_ordinal:03d}.json"
    payload = (root / relative_path).read_bytes()
    public_payloads: list[dict[str, Any]] = []
    public_hashes: list[str] = []
    for call in record.provider_calls:
        response = tuple(
            item for item in call.artifacts if item.artifact_kind == "response_metadata"
        )
        if len(response) != 1:
            _fail("source.response_descriptor", "one response projection is required")
        descriptor = response[0]
        artifact_path = root / descriptor.relative_path
        artifact_bytes = artifact_path.read_bytes()
        if (
            _sha(artifact_bytes) != descriptor.sha256
            or len(artifact_bytes) != descriptor.byte_count
        ):
            _fail("source.response_bytes", f"response metadata differs:{artifact_path}")
        artifact = _load_bytes(artifact_bytes)
        projection = artifact.get("public_projection")
        projection_sha = artifact.get("public_projection_sha256")
        if (
            not isinstance(projection, dict)
            or projection != descriptor.public_projection
            or projection_sha != descriptor.public_projection_sha256
            or projection_sha != models.canonical_sha256(projection)
            or artifact.get("provider_call_id") != call.provider_call_id
            or artifact.get("raw_provider_response_persisted")
            or artifact.get("private_reasoning_persisted")
        ):
            _fail("source.response_projection", "persisted public projection differs")
        public_payloads.append(cast(dict[str, Any], projection))
        public_hashes.append(str(projection_sha))
    expected_kind = (
        "subsequent_action_parser_rejection"
        if record.job_ordinal in {6, 22}
        else "subsequent_action_reference_failure"
    )
    return cast(
        models.HostFailureRow,
        _make(
            models.HostFailureRow,
            {
                "v226_freeze_id": freeze_id,
                "job_id": record.job_id,
                "job_ordinal": record.job_ordinal,
                "failure_record_id": record.record_id,
                "failure_relative_path": relative_path,
                "failure_file_sha256": _sha(payload),
                "failure_file_byte_count": len(payload),
                "failure_record": record.model_dump(mode="json", warnings=False),
                "failure_record_sha256": models.canonical_sha256(record),
                "public_payloads": tuple(public_payloads),
                "public_payload_sha256s": tuple(public_hashes),
                "expected_evidence_kind": expected_kind,
            },
            "row_id",
            "finance_v26_227_host_failure_row:",
        ),
    )


@dataclass(frozen=True)
class Replay:
    records: tuple[v209_models.ExecutableInvocationRecord, ...]
    terminal: str


def _bind_replay_to_v226_source(*, host: models.HostFailureRow, replay: Replay) -> None:
    source = v226_models.JobFailureRecord.model_validate(host.failure_record)
    if len(source.provider_calls) != len(replay.records):
        _fail(
            "replay.source_geometry",
            "replay invocation count differs from frozen v26.226 Provider-call count",
        )
    for invocation, provider_call in zip(replay.records, source.provider_calls, strict=True):
        if (
            provider_call.status != "succeeded"
            or invocation.canonical_request_body_sha256 != provider_call.request_sha256
            or invocation.public_response_sha256 != provider_call.response_sha256
        ):
            _fail(
                "replay.source_binding",
                "replayed request/response differs from frozen v26.226 source call",
            )


def _replay(
    *,
    job: v209_models.ExecutableDevelopmentJob,
    public_payloads: tuple[dict[str, Any], ...],
    loaded: dict[str, Any],
) -> Replay:
    transport = v209.ScriptedTransport()
    for payload in public_payloads:
        transport.queue(payload)
    runner = v209._make_runner(  # noqa: SLF001
        transport=transport,
        config=loaded["config"],
        parents=loaded["parents"],
        prepared=loaded["runtime"],
        implementation_id=loaded["implementation"].implementation_id,
    )
    context = v209._context_for_job(  # noqa: SLF001
        job=job, parents=loaded["parents"], prepared=loaded["runtime"]
    )
    state = frozen_runtime._initialize(context)  # noqa: SLF001
    records: list[v209_models.ExecutableInvocationRecord] = []
    invocation_index = 0
    terminal: str | None = None
    while state.current_index < len(state.ordered_components):
        outcome = runner.invoke_action(job=job, invocation_index=invocation_index, state=state)
        invocation_index += 1
        records.append(outcome.record)
        if outcome.terminal is not None:
            terminal = outcome.terminal
            break
        if outcome.record.action_accepted is True:
            continue
        if not isinstance(outcome.runtime_output, step_runtime.PublicTypedRejectionObservation):
            _fail("replay.action", "nonterminal Action rejection lacks public feedback")
        correction = runner.invoke_correction(
            job=job, invocation_index=invocation_index, state=state
        )
        invocation_index += 1
        records.append(correction.record)
        if correction.terminal is not None:
            terminal = correction.terminal
            break
        if correction.record.action_accepted is True:
            continue
        terminal = correction.terminal
        break
    if terminal is None:
        _fail("replay.terminal", "host-failure replay unexpectedly reached Final")
    if len(transport.dispatches) != len(public_payloads) or len(records) != len(public_payloads):
        _fail("replay.geometry", "replay invocation/public projection geometry differs")
    return Replay(records=tuple(records), terminal=terminal)


def _evidence(
    *,
    authorization_id: str,
    freeze_id: str,
    source_identity_id: str,
    host: models.HostFailureRow,
    replay: Replay,
) -> models.ObservedEvidence:
    record = replay.records[-1]
    payload = host.public_payloads[-1]
    common = {
        "external_authorization_id": authorization_id,
        "v226_freeze_id": freeze_id,
        "source_identity_id": source_identity_id,
        "host_failure_row_id": host.row_id,
        "job_id": host.job_id,
        "job_ordinal": host.job_ordinal,
        "invocation_records": tuple(
            item.model_dump(mode="json", warnings=False) for item in replay.records
        ),
        "public_payload": payload,
        "public_payload_sha256": host.public_payload_sha256s[-1],
        "current_state_id": record.current_state_id,
        "current_candidate_action_ids": record.candidate_action_ids,
        "observed_state_id": payload.get("state_id"),
        "observed_action_id": payload.get("action_id"),
    }
    if host.expected_evidence_kind == "subsequent_action_parser_rejection":
        return cast(
            models.ParserSubsequentActionEvidence,
            _make(
                models.ParserSubsequentActionEvidence,
                common,
                "evidence_id",
                "finance_v26_227_parser_subsequent_action_evidence:",
            ),
        )
    return cast(
        models.ReferenceSubsequentActionEvidence,
        _make(
            models.ReferenceSubsequentActionEvidence,
            common,
            "evidence_id",
            "finance_v26_227_reference_subsequent_action_evidence:",
        ),
    )


class ReplayEvidenceAuthority:
    """No-replace authority populated only from the exact local Runner replay."""

    def __init__(self, expected_host_failure_row_ids: tuple[str, ...]) -> None:
        self._expected = frozenset(expected_host_failure_row_ids)
        self._observed: dict[str, bytes] = {}

    def observe(self, evidence: models.ObservedEvidence) -> None:
        admitted = models.EVIDENCE_ADAPTER.validate_python(
            evidence.model_dump(mode="python", warnings=False)
        )
        key = admitted.host_failure_row_id
        if key not in self._expected or key in self._observed:
            raise ValueError("replay Evidence authority rejects unknown/replaced source")
        self._observed[key] = models.canonical_bytes(admitted)

    def require(self, evidence: models.ObservedEvidence) -> None:
        payload = models.canonical_bytes(evidence)
        if self._observed.get(evidence.host_failure_row_id) != payload:
            raise ValueError("Evidence differs from exact replay authority")

    @property
    def observation_count(self) -> int:
        return len(self._observed)


class SubsequentActionDispatcher:
    def __init__(
        self,
        binding: models.DispatcherBinding,
        authority: ReplayEvidenceAuthority,
    ) -> None:
        self.binding = binding
        self.authority = authority

    def _derive(self, evidence: models.ObservedEvidence) -> models.DispatcherDecision:
        admitted = models.EVIDENCE_ADAPTER.validate_python(
            evidence.model_dump(mode="python", warnings=False)
        )
        if isinstance(admitted, models.ParserSubsequentActionEvidence):
            terminal = models.PARSER_TERMINAL
            policy = models.PARSER_POLICY_ID
            rule = "subsequent_action_exact_parser_rejection"
        else:
            terminal = models.REFERENCE_TERMINAL
            policy = models.REFERENCE_POLICY_ID
            rule = "subsequent_action_parsed_reference_not_current"
        return cast(
            models.DispatcherDecision,
            _make(
                models.DispatcherDecision,
                {
                    "dispatcher_binding_id": self.binding.binding_id,
                    "evidence": admitted,
                    "evidence_sha256": models.canonical_sha256(admitted),
                    "job_id": admitted.job_id,
                    "job_ordinal": admitted.job_ordinal,
                    "terminal_kind": terminal,
                    "terminal_policy_id": policy,
                    "derivation_rule": rule,
                },
                "decision_id",
                "finance_v26_227_subsequent_action_dispatcher_decision:",
            ),
        )

    def prospective(self, evidence: models.ObservedEvidence) -> models.DispatcherDecision:
        """Construct a candidate decision for the full-rehash negative control."""
        return self._derive(evidence)

    def dispatch(self, evidence: models.ObservedEvidence) -> models.DispatcherDecision:
        admitted = models.EVIDENCE_ADAPTER.validate_python(
            evidence.model_dump(mode="python", warnings=False)
        )
        self.authority.require(admitted)
        return self._derive(admitted)


def _layer(
    *,
    layer_kind: models.LayerKind,
    authorization_id: str,
    freeze_id: str,
    source_identity_id: str,
    host: models.HostFailureRow,
    evidence: models.ObservedEvidence,
    decision: models.DispatcherDecision,
    parent: models.LayerArtifact | None,
) -> models.LayerArtifact:
    sequence = models.LAYER_KINDS.index(layer_kind)
    payload: dict[str, Any] = {
        "layer_kind": layer_kind,
        "job_id": host.job_id,
        "job_ordinal": host.job_ordinal,
        "terminal_kind": decision.terminal_kind,
        "terminal_policy_id": decision.terminal_policy_id,
        "evidence_id": evidence.evidence_id,
        "evidence_sha256": models.canonical_sha256(evidence),
        "dispatcher_decision_id": decision.decision_id,
        "parent_artifact_id": None if parent is None else parent.artifact_id,
        "persisted_sequence": sequence,
        "formal_empirical_row": False,
    }
    if layer_kind == "raw":
        payload["observed_evidence"] = evidence.model_dump(mode="json", warnings=False)
        payload["host_failure_source"] = {
            "host_failure_row_id": host.row_id,
            "failure_record_id": host.failure_record_id,
            "failure_relative_path": host.failure_relative_path,
            "failure_file_sha256": host.failure_file_sha256,
        }
    elif layer_kind == "result":
        payload["derived_decision"] = decision.model_dump(mode="json", warnings=False)
    elif layer_kind == "trace":
        payload["invocation_records"] = evidence.invocation_records
    elif layer_kind == "outcome":
        payload["terminal_projection"] = {
            "terminal_kind": decision.terminal_kind,
            "terminal_policy_id": decision.terminal_policy_id,
            "derivation_rule": decision.derivation_rule,
        }
    else:
        payload["closed_layer_ids"] = ()
    relative_path = (
        f"replay_checkpoints/job_{host.job_ordinal:03d}.json"
        if layer_kind == "checkpoint"
        else f"replay_evidence/{layer_kind}/{_safe(host.job_id)}.json"
    )
    return cast(
        models.LayerArtifact,
        _make(
            models.LayerArtifact,
            {
                "layer_kind": layer_kind,
                "external_authorization_id": authorization_id,
                "v226_freeze_id": freeze_id,
                "source_identity_id": source_identity_id,
                "host_failure_row_id": host.row_id,
                "evidence_id": evidence.evidence_id,
                "dispatcher_decision_id": decision.decision_id,
                "job_id": host.job_id,
                "job_ordinal": host.job_ordinal,
                "terminal_kind": decision.terminal_kind,
                "parent_artifact_id": None if parent is None else parent.artifact_id,
                "payload": payload,
                "payload_sha256": models.canonical_sha256(payload),
                "relative_path": relative_path,
                "persisted_sequence": sequence,
            },
            "artifact_id",
            "finance_v26_227_replay_layer_artifact:",
        ),
    )


def _five_layers(
    *,
    authorization_id: str,
    freeze_id: str,
    source_identity_id: str,
    host: models.HostFailureRow,
    evidence: models.ObservedEvidence,
    decision: models.DispatcherDecision,
) -> models.FiveLayerArtifacts:
    made: list[models.LayerArtifact] = []
    for kind in models.LAYER_KINDS:
        made.append(
            _layer(
                layer_kind=cast(models.LayerKind, kind),
                authorization_id=authorization_id,
                freeze_id=freeze_id,
                source_identity_id=source_identity_id,
                host=host,
                evidence=evidence,
                decision=decision,
                parent=made[-1] if made else None,
            )
        )
    # The checkpoint summarizes the complete prior chain without changing its
    # authoritative parent edge.  Rebuild it with the exact four closed IDs.
    checkpoint = made[-1]
    checkpoint_payload = dict(checkpoint.payload)
    checkpoint_payload["closed_layer_ids"] = tuple(item.artifact_id for item in made[:-1])
    made[-1] = cast(
        models.LayerArtifact,
        _make(
            models.LayerArtifact,
            {
                **checkpoint.model_dump(
                    mode="python", exclude={"artifact_id", "payload", "payload_sha256"}
                ),
                "payload": checkpoint_payload,
                "payload_sha256": models.canonical_sha256(checkpoint_payload),
            },
            "artifact_id",
            "finance_v26_227_replay_layer_artifact:",
        ),
    )
    raw, result, trace, outcome, checkpoint = made
    return cast(
        models.FiveLayerArtifacts,
        _make(
            models.FiveLayerArtifacts,
            {
                "raw": raw,
                "result": result,
                "trace": trace,
                "outcome": outcome,
                "checkpoint": checkpoint,
            },
            "chain_id",
            "finance_v26_227_replay_five_layer_chain:",
        ),
    )


def _control(
    *,
    authorization_id: str,
    freeze_id: str,
    source_identity_id: str,
    dispatcher_binding_id: str,
    host: models.HostFailureRow,
    evidence: models.ObservedEvidence,
    decision: models.DispatcherDecision,
    layers: models.FiveLayerArtifacts,
) -> models.ControlRow:
    return cast(
        models.ControlRow,
        _make(
            models.ControlRow,
            {
                "external_authorization_id": authorization_id,
                "v226_freeze_id": freeze_id,
                "source_identity_id": source_identity_id,
                "dispatcher_binding_id": dispatcher_binding_id,
                "host_failure": host,
                "evidence": evidence,
                "dispatcher_decision": decision,
                "five_layers": layers,
                "replay_observed_record_count": len(evidence.invocation_records),
            },
            "control_id",
            "finance_v26_227_positive_control_row:",
        ),
    )


def _assert_rejects(factory: Any, *, stage: str) -> None:
    try:
        factory()
    except (ValidationError, ValueError, TypeError, KeyError):
        return
    _fail(stage, "negative control was accepted")


def _negative_audit(
    *,
    authorization_id: str,
    freeze: FrozenV226,
    source_identity_id: str,
    dispatcher: SubsequentActionDispatcher,
    controls: tuple[models.ControlRow, ...],
) -> models.NegativeAudit:
    parser = cast(
        models.ParserSubsequentActionEvidence,
        controls[0].evidence,
    )
    reference = cast(
        models.ReferenceSubsequentActionEvidence,
        controls[2].evidence,
    )

    def reconstruct(evidence: models.ObservedEvidence) -> models.ObservedEvidence:
        model_type = type(evidence)
        prefix = (
            "finance_v26_227_parser_subsequent_action_evidence:"
            if isinstance(evidence, models.ParserSubsequentActionEvidence)
            else "finance_v26_227_reference_subsequent_action_evidence:"
        )
        values = evidence.model_dump(mode="python", exclude={"evidence_id"})
        return cast(models.ObservedEvidence, _make(model_type, values, "evidence_id", prefix))

    _assert_rejects(
        lambda: models.ParserSubsequentActionEvidence.model_validate(
            {**parser.model_dump(mode="python"), "phase": "first_action"}
        ),
        stage="attack.phase",
    )
    _assert_rejects(
        lambda: models.ReferenceSubsequentActionEvidence.model_validate(
            {
                **parser.model_dump(
                    mode="python",
                    exclude={
                        "evidence_id",
                        "evidence_kind",
                        "parser_exception_type",
                        "parser_exception_family",
                        "parser_exception_subtype",
                        "parser_rejected",
                    },
                ),
                "evidence_id": "forged",
                "evidence_kind": "subsequent_action_reference_failure",
                "job_ordinal": 149,
                "parser_accepted": True,
                "current_reference_valid": False,
            }
        ),
        stage="attack.type",
    )

    cross_values = parser.model_dump(mode="python", exclude={"evidence_id"})
    cross_values["invocation_records"] = reference.invocation_records
    _assert_rejects(
        lambda: reconstruct(
            cast(
                models.ObservedEvidence,
                models.ParserSubsequentActionEvidence.model_construct(
                    evidence_id="pending", **cross_values
                ),
            )
        ),
        stage="attack.cross_job",
    )

    truncated = parser.model_dump(mode="python", exclude={"evidence_id"})
    truncated["invocation_records"] = parser.invocation_records[1:]
    _assert_rejects(
        lambda: _make(
            models.ParserSubsequentActionEvidence,
            truncated,
            "evidence_id",
            "finance_v26_227_parser_subsequent_action_evidence:",
        ),
        stage="attack.prefix",
    )

    stale_state = parser.model_dump(mode="python", exclude={"evidence_id"})
    stale_state["current_state_id"] = cast(dict[str, Any], parser.invocation_records[0])[
        "current_state_id"
    ]
    _assert_rejects(
        lambda: _make(
            models.ParserSubsequentActionEvidence,
            stale_state,
            "evidence_id",
            "finance_v26_227_parser_subsequent_action_evidence:",
        ),
        stage="attack.state",
    )

    stale_candidates = parser.model_dump(mode="python", exclude={"evidence_id"})
    stale_candidates["current_candidate_action_ids"] = tuple(
        reversed(parser.current_candidate_action_ids)
    )
    _assert_rejects(
        lambda: _make(
            models.ParserSubsequentActionEvidence,
            stale_candidates,
            "evidence_id",
            "finance_v26_227_parser_subsequent_action_evidence:",
        ),
        stage="attack.candidates",
    )

    forged = parser.model_dump(mode="python", exclude={"evidence_id"})
    forged_payload = dict(parser.public_payload)
    forged_action = next(
        item for item in parser.current_candidate_action_ids if item != parser.observed_action_id
    )
    forged_payload["action_id"] = forged_action
    forged["public_payload"] = forged_payload
    forged["public_payload_sha256"] = models.canonical_sha256(forged_payload)
    forged["observed_action_id"] = forged_action
    forged_records = [copy.deepcopy(item) for item in parser.invocation_records]
    terminal_record_values = dict(forged_records[-1])
    terminal_record_values.pop("invocation_id")
    terminal_record_values["public_response_sha256"] = forged["public_payload_sha256"]
    terminal_record = cast(
        v209_models.ExecutableInvocationRecord,
        _make(
            v209_models.ExecutableInvocationRecord,
            terminal_record_values,
            "invocation_id",
            "fresh_repaired_final_continuity_executable_invocation_record:",
        ),
    )
    forged_records[-1] = terminal_record.model_dump(mode="json", warnings=False)
    forged["invocation_records"] = tuple(forged_records)

    def fully_rehashed() -> None:
        candidate = cast(
            models.ObservedEvidence,
            _make(
                models.ParserSubsequentActionEvidence,
                forged,
                "evidence_id",
                "finance_v26_227_parser_subsequent_action_evidence:",
            ),
        )
        candidate_decision = dispatcher.prospective(candidate)
        host = controls[0].host_failure
        candidate_layers = _five_layers(
            authorization_id=authorization_id,
            freeze_id=freeze.freeze.freeze_id,
            source_identity_id=source_identity_id,
            host=host,
            evidence=candidate,
            decision=candidate_decision,
        )
        if (
            len(
                {
                    candidate_layers.raw.artifact_id,
                    candidate_layers.result.artifact_id,
                    candidate_layers.trace.artifact_id,
                    candidate_layers.outcome.artifact_id,
                    candidate_layers.checkpoint.artifact_id,
                }
            )
            != 5
        ):
            _fail("attack.full_rehash", "five candidate layer identities were not built")
        # Despite complete downstream rehashing, admission is against the exact
        # replay-owned Evidence bytes and therefore rejects before any Raw write.
        dispatcher.dispatch(candidate)

    _assert_rejects(fully_rehashed, stage="attack.full_rehash")

    provider_failure = freeze.provider_failures[0]
    _assert_rejects(
        lambda: models.HostFailureRow.model_validate(
            {
                **controls[0].host_failure.model_dump(mode="python"),
                "failure_record": provider_failure.model_dump(mode="json"),
                "failure_record_id": provider_failure.record_id,
                "job_id": provider_failure.job_id,
            }
        ),
        stage="attack.provider_failure",
    )
    return cast(
        models.NegativeAudit,
        _make(
            models.NegativeAudit,
            {
                "external_authorization_id": authorization_id,
                "v226_freeze_id": freeze.freeze.freeze_id,
                "source_identity_id": source_identity_id,
                "dispatcher_binding_id": dispatcher.binding.binding_id,
            },
            "audit_id",
            "finance_v26_227_negative_audit:",
        ),
    )


def _artifact_manifest(payloads: dict[str, bytes]) -> models.ArtifactManifest:
    members = tuple(
        models.ArtifactMember(relative_path=path, sha256=_sha(payload), byte_count=len(payload))
        for path, payload in sorted(payloads.items())
    )
    member_payloads = tuple(item.model_dump(mode="json") for item in members)
    return cast(
        models.ArtifactManifest,
        _make(
            models.ArtifactManifest,
            {
                "run_id": RUN_ID,
                "members": members,
                "file_count": len(members),
                "total_member_bytes": sum(item.byte_count for item in members),
                "artifact_root": models.canonical_hash(
                    member_payloads, prefix="finance_v26_227_artifact_root:"
                ),
            },
            "manifest_id",
            "finance_v26_227_artifact_manifest:",
        ),
    )


def build(
    *,
    repository_root: Path,
    output_dir: Path,
    external_review_path: Path,
    source_identity: tuple[str, str],
) -> models.Report:
    if output_dir.exists():
        _fail("output.exists", "v26.227 output directory already exists")
    external, review, directive = _external_authorization(external_review_path)
    frozen = _verify_v226(
        repository_root=repository_root,
        external_authorization_id=external.authorization_id,
    )
    source = _source_identity(repository_root=repository_root, source_identity=source_identity)
    binding = cast(
        models.DispatcherBinding,
        _make(
            models.DispatcherBinding,
            {
                "external_authorization_id": external.authorization_id,
                "v226_freeze_id": frozen.freeze.freeze_id,
                "source_identity_id": source.source_identity_id,
            },
            "binding_id",
            "finance_v26_227_subsequent_action_dispatcher_binding:",
        ),
    )

    v226_root = repository_root / V226_DIR
    host_rows = tuple(
        _host_failure_row(root=v226_root, freeze_id=frozen.freeze.freeze_id, record=record)
        for record in frozen.host_failures
    )
    authority = ReplayEvidenceAuthority(tuple(item.row_id for item in host_rows))
    dispatcher = SubsequentActionDispatcher(binding, authority)
    with TemporaryDirectory(prefix="finance_v26_227_runtime_") as temporary:
        loaded = v226._load_exact_runtime(  # noqa: SLF001
            repository_root, Path(temporary)
        )
        registry = loaded["bindings"].terminal_registry
        registry_rows = {item.terminal_kind: item.policy_id for item in registry.policies}
        if (
            registry.registry_id != binding.frozen_v195_terminal_registry_id
            or registry_rows.get(models.PARSER_TERMINAL) != models.PARSER_POLICY_ID
            or registry_rows.get(models.REFERENCE_TERMINAL) != models.REFERENCE_POLICY_ID
        ):
            _fail("dispatcher.registry", "exact v26.195 terminal policy differs")
        jobs = {item.job_id: item for item in loaded["manifest"].jobs}
        controls_list: list[models.ControlRow] = []
        for host in host_rows:
            replay = _replay(
                job=jobs[host.job_id],
                public_payloads=host.public_payloads,
                loaded=loaded,
            )
            _bind_replay_to_v226_source(host=host, replay=replay)
            expected_terminal = (
                models.PARSER_TERMINAL
                if host.expected_evidence_kind == "subsequent_action_parser_rejection"
                else models.REFERENCE_TERMINAL
            )
            if replay.terminal != expected_terminal:
                _fail("replay.terminal", "derived replay terminal differs")
            evidence = _evidence(
                authorization_id=external.authorization_id,
                freeze_id=frozen.freeze.freeze_id,
                source_identity_id=source.source_identity_id,
                host=host,
                replay=replay,
            )
            authority.observe(evidence)
            decision = dispatcher.dispatch(evidence)
            layers = _five_layers(
                authorization_id=external.authorization_id,
                freeze_id=frozen.freeze.freeze_id,
                source_identity_id=source.source_identity_id,
                host=host,
                evidence=evidence,
                decision=decision,
            )
            controls_list.append(
                _control(
                    authorization_id=external.authorization_id,
                    freeze_id=frozen.freeze.freeze_id,
                    source_identity_id=source.source_identity_id,
                    dispatcher_binding_id=binding.binding_id,
                    host=host,
                    evidence=evidence,
                    decision=decision,
                    layers=layers,
                )
            )
    if authority.observation_count != 3:
        _fail("replay.authority", "exact replay authority did not close three rows")
    controls = tuple(controls_list)
    control_audit = cast(
        models.ControlAudit,
        _make(
            models.ControlAudit,
            {
                "external_authorization_id": external.authorization_id,
                "v226_freeze_id": frozen.freeze.freeze_id,
                "source_identity_id": source.source_identity_id,
                "dispatcher_binding_id": binding.binding_id,
                "controls": controls,
            },
            "audit_id",
            "finance_v26_227_control_audit:",
        ),
    )
    negative = _negative_audit(
        authorization_id=external.authorization_id,
        freeze=frozen,
        source_identity_id=source.source_identity_id,
        dispatcher=dispatcher,
        controls=controls,
    )
    scope = cast(
        models.ScopeAudit,
        _make(
            models.ScopeAudit,
            {
                "external_authorization_id": external.authorization_id,
                "v226_freeze_id": frozen.freeze.freeze_id,
                "source_identity_id": source.source_identity_id,
                "control_audit_id": control_audit.audit_id,
                "negative_audit_id": negative.audit_id,
            },
            "audit_id",
            "finance_v26_227_scope_audit:",
        ),
    )
    gate_evidence = (
        frozen.freeze.freeze_id,
        models.canonical_sha256(
            tuple(item.host_failure.model_dump(mode="json") for item in controls)
        ),
        models.canonical_sha256(tuple(item.evidence.invocation_records for item in controls)),
        controls[0].evidence.evidence_id,
        controls[2].evidence.evidence_id,
        control_audit.audit_id,
        negative.audit_id,
        scope.audit_id,
    )
    gates = tuple(
        cast(
            models.Gate,
            _make(
                models.Gate,
                {"gate_name": gate_name, "evidence_id": evidence_id},
                "gate_id",
                "finance_v26_227_evidence_domain_gate:",
            ),
        )
        for gate_name, evidence_id in zip(models.GATE_NAMES, gate_evidence, strict=True)
    )
    gate = cast(
        models.GateEvaluation,
        _make(
            models.GateEvaluation,
            {"gates": gates},
            "evaluation_id",
            "finance_v26_227_gate_evaluation:",
        ),
    )
    decision = cast(
        models.Decision,
        _make(
            models.Decision,
            {
                "external_authorization_id": external.authorization_id,
                "v226_freeze_id": frozen.freeze.freeze_id,
                "source_identity_id": source.source_identity_id,
                "dispatcher_binding_id": binding.binding_id,
                "control_audit_id": control_audit.audit_id,
                "negative_audit_id": negative.audit_id,
                "scope_audit_id": scope.audit_id,
                "gate_evaluation_id": gate.evaluation_id,
            },
            "decision_id",
            "finance_v26_227_decision:",
        ),
    )
    transition = cast(
        models.Transition,
        _make(
            models.Transition,
            {
                "decision_id": decision.decision_id,
                "gate_evaluation_id": gate.evaluation_id,
            },
            "transition_id",
            "finance_v26_227_transition:",
        ),
    )
    report = cast(
        models.Report,
        _make(
            models.Report,
            {
                "run_id": RUN_ID,
                "external_authorization_id": external.authorization_id,
                "v226_freeze_id": frozen.freeze.freeze_id,
                "source_identity_id": source.source_identity_id,
                "dispatcher_binding_id": binding.binding_id,
                "control_audit_id": control_audit.audit_id,
                "negative_audit_id": negative.audit_id,
                "scope_audit_id": scope.audit_id,
                "gate_evaluation_id": gate.evaluation_id,
                "decision_id": decision.decision_id,
                "transition_id": transition.transition_id,
            },
            "report_id",
            "finance_v26_227_report:",
        ),
    )

    payloads: dict[str, bytes] = {
        "control_audit.json": _encoded(control_audit),
        "decision.json": _encoded(decision),
        "dispatcher_binding.json": _encoded(binding),
        "external_authorization.json": _encoded(external),
        "external_review.txt": review,
        "gate_evaluation.json": _encoded(gate),
        "negative_control_audit.json": _encoded(negative),
        "operator_directive.txt": directive,
        "prospective_transition.json": _encoded(transition),
        "report.json": _encoded(report),
        "scope_boundary_audit.json": _encoded(scope),
        "source_identity.json": _encoded(source),
        "v226_freeze.json": _encoded(frozen.freeze),
    }
    for control in controls:
        safe_job = _safe(control.host_failure.job_id)
        payloads[f"host_failure_rows/job_{control.host_failure.job_ordinal:03d}.json"] = _encoded(
            control.host_failure
        )
        payloads[f"replay_evidence/observed/{safe_job}.json"] = _encoded(control.evidence)
        payloads[f"replay_evidence/decision/{safe_job}.json"] = _encoded(
            control.dispatcher_decision
        )
        for layer in (
            control.five_layers.raw,
            control.five_layers.result,
            control.five_layers.trace,
            control.five_layers.outcome,
            control.five_layers.checkpoint,
        ):
            if layer.relative_path in payloads:
                _fail("artifact.path", f"duplicate artifact path:{layer.relative_path}")
            payloads[layer.relative_path] = _encoded(layer)
    artifact = _artifact_manifest(payloads)
    output_dir.mkdir(parents=True, exist_ok=False)
    for relative_path, payload in sorted(payloads.items()):
        path = output_dir / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
    (output_dir / "artifact_manifest.json").write_bytes(_encoded(artifact))
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--external-review", type=Path, required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--source-tree", required=True)
    args = parser.parse_args()
    build(
        repository_root=args.repository_root.resolve(),
        output_dir=args.output_dir.resolve(),
        external_review_path=args.external_review.resolve(),
        source_identity=(args.source_commit, args.source_tree),
    )


if __name__ == "__main__":
    main()
