from __future__ import annotations

import hashlib
import json
from collections import Counter
from collections.abc import Sequence
from pathlib import Path, PurePosixPath
from typing import Any, Final, Literal, cast

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.core.task.authoritative_job_bound_outcome import (
    AuthoritativeTerminalRegistry,
    ComponentAttemptEvidence,
    EvidenceKind,
    FailureLocus,
    JobComponentSequence,
    RawExecutionEvidencePayload,
    TerminalKind,
    expected_provider_artifact_ids,
    expected_transport_artifact_ids,
)
from trusted_synthesis.core.task.authoritative_job_bound_outcome import (
    make_identity_model as make_v2_identity_model,
)
from trusted_synthesis.core.task.job_bound_multistep_outcome import (
    CapabilityDevelopmentJob,
    CapabilityDevelopmentJobManifest,
    ComponentAttemptOutcome,
    JobBoundOutcomePayload,
    JobBoundRunnerContract,
)
from trusted_synthesis.hashing import canonical_hash

ARTIFACT_BACKED_OUTCOME_VERSION: Final = "authoritative_artifact_backed_outcome.v3"
EXPECTED_JOB_COUNT: Final = 192

FailureStage = Literal[
    "provider",
    "transport",
    "privacy",
    "resource",
    "instrument",
    "model_identity",
    "thinking",
    "usage",
    "action_abi",
    "action_reference",
    "state_precondition",
    "operation_support",
    "final_abi",
    "base_answer",
    "base_citation",
    "mechanism",
    "policy",
]
BaseFailureStage = Literal["base_answer", "base_citation"]


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


def identity(value: BaseModel, field: str, prefix: str) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={field}, warnings=False),
        prefix=prefix,
    )


def make_identity_model(
    model_type: type[BaseModel],
    values: dict[str, Any],
    *,
    field: str,
    prefix: str,
) -> Any:
    provisional = model_type.model_construct(**{field: "pending"}, **values)
    return model_type(**{field: identity(provisional, field, prefix)}, **values)


def canonical_model_bytes(value: BaseModel) -> bytes:
    return (
        json.dumps(
            value.model_dump(mode="json", warnings=False),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
        + b"\n"
    )


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def expected_raw_artifact_filename(job: CapabilityDevelopmentJob) -> str:
    return f"raw--{job.job_id.split(':', 1)[-1]}.json"


def expected_result_artifact_filename(job: CapabilityDevelopmentJob) -> str:
    return f"result--{job.job_id.split(':', 1)[-1]}.json"


class TerminalValidityEvidence(FrozenModel):
    validity_id: str = Field(min_length=1)
    task_completion: bool | None
    task_verifier_invoked: bool
    final_response_abi_valid: bool | None = None
    final_result_id: str | None = None
    final_base_valid: bool | None = None
    final_mechanism_qualified: bool | None = None
    final_qualified_valid: bool | None = None
    base_failure_stage: BaseFailureStage | None = None
    mechanism_failure_component_index: int | None = Field(default=None, ge=0, le=3)
    mechanism_failure_component_key: str | None = None
    schema_version: str = ARTIFACT_BACKED_OUTCOME_VERSION

    @model_validator(mode="after")
    def validate_validity(self) -> TerminalValidityEvidence:
        verifier_values = (
            self.final_result_id,
            self.final_base_valid,
            self.final_mechanism_qualified,
            self.final_qualified_valid,
        )
        if self.task_verifier_invoked:
            if (
                self.task_completion is not True
                or self.final_response_abi_valid is not True
                or any(item is None for item in verifier_values)
            ):
                raise ValueError("completed validity lacks exact Final Verifier evidence")
            expected_qualified = bool(self.final_base_valid and self.final_mechanism_qualified)
            if self.final_qualified_valid != expected_qualified:
                raise ValueError("completed Qualified validity is not Base and Mechanism")
            if (self.final_base_valid is False) != (self.base_failure_stage is not None):
                raise ValueError("Base validity and Base failure stage differ")
            mechanism_coordinates = (
                self.mechanism_failure_component_index,
                self.mechanism_failure_component_key,
            )
            if (self.final_mechanism_qualified is False) != all(
                item is not None for item in mechanism_coordinates
            ):
                raise ValueError("Mechanism validity and failure coordinates differ")
            if any(item is None for item in mechanism_coordinates) and any(
                item is not None for item in mechanism_coordinates
            ):
                raise ValueError("Mechanism failure coordinates are partial")
        else:
            if any(item is not None for item in verifier_values):
                raise ValueError("non-Verifier terminal carries Final validity")
            if self.base_failure_stage is not None or any(
                item is not None
                for item in (
                    self.mechanism_failure_component_index,
                    self.mechanism_failure_component_key,
                )
            ):
                raise ValueError("non-Verifier terminal carries Final failure details")
        if self.validity_id != identity(
            self,
            "validity_id",
            "capability_artifact_backed_terminal_validity:",
        ):
            raise ValueError("TerminalValidityEvidence identity is invalid")
        return self


class ArtifactBackedRawExecutionDescriptor(FrozenModel):
    raw_execution_id: str = Field(min_length=1)
    evidence_kind: EvidenceKind
    job_id: str = Field(min_length=1)
    manifest_id: str = Field(min_length=1)
    runner_id: str = Field(min_length=1)
    execution_package_id: str = Field(min_length=1)
    source_package_artifact_id: str = Field(min_length=1)
    replica_index: int = Field(ge=0, le=5)
    raw_namespace: str = Field(min_length=1)
    artifact_relative_path: str = Field(min_length=1)
    artifact_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    artifact_byte_count: int = Field(gt=0)
    payload_id: str = Field(min_length=1)
    canonical_json_required: Literal[True] = True
    schema_version: str = ARTIFACT_BACKED_OUTCOME_VERSION

    @model_validator(mode="after")
    def validate_descriptor(self) -> ArtifactBackedRawExecutionDescriptor:
        _validate_relative_path(self.artifact_relative_path)
        if self.raw_execution_id != identity(
            self,
            "raw_execution_id",
            "capability_artifact_backed_raw_execution:",
        ):
            raise ValueError("artifact-backed Raw descriptor identity is invalid")
        return self


class ArtifactBackedJobResultPayload(FrozenModel):
    payload_id: str = Field(min_length=1)
    job_id: str = Field(min_length=1)
    raw_execution_id: str = Field(min_length=1)
    terminal_kind: TerminalKind
    validity: TerminalValidityEvidence
    schema_version: str = ARTIFACT_BACKED_OUTCOME_VERSION

    @model_validator(mode="after")
    def validate_payload(self) -> ArtifactBackedJobResultPayload:
        completed = self.terminal_kind in {"completed_qualified", "completed_invalid"}
        if completed != self.validity.task_verifier_invoked:
            raise ValueError("terminal kind and Final Verifier invocation differ")
        if self.terminal_kind == "completed_qualified" and (
            self.validity.final_qualified_valid is not True
        ):
            raise ValueError("completed-qualified Result lacks Qualified validity")
        if self.terminal_kind == "completed_invalid" and (
            self.validity.final_qualified_valid is not False
        ):
            raise ValueError("completed-invalid Result lacks invalid conjunction")
        if self.terminal_kind == "final_response_abi_invalid" and (
            self.validity.final_response_abi_valid is not False
        ):
            raise ValueError("Final-ABI-invalid Result lacks exact ABI disposition")
        if self.payload_id != identity(
            self,
            "payload_id",
            "capability_artifact_backed_job_result_payload:",
        ):
            raise ValueError("artifact-backed Job Result payload identity is invalid")
        return self


class ArtifactBackedJobResultDescriptor(FrozenModel):
    result_id: str = Field(min_length=1)
    evidence_kind: EvidenceKind
    job_id: str = Field(min_length=1)
    raw_execution_id: str = Field(min_length=1)
    result_namespace: str = Field(min_length=1)
    artifact_relative_path: str = Field(min_length=1)
    artifact_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    artifact_byte_count: int = Field(gt=0)
    payload_id: str = Field(min_length=1)
    canonical_json_required: Literal[True] = True
    schema_version: str = ARTIFACT_BACKED_OUTCOME_VERSION

    @model_validator(mode="after")
    def validate_descriptor(self) -> ArtifactBackedJobResultDescriptor:
        _validate_relative_path(self.artifact_relative_path)
        if self.result_id != identity(
            self,
            "result_id",
            "capability_artifact_backed_job_result:",
        ):
            raise ValueError("artifact-backed Result descriptor identity is invalid")
        return self


class ArtifactBackedAttemptTrace(FrozenModel):
    trace_id: str = Field(min_length=1)
    evidence_kind: EvidenceKind
    job_id: str = Field(min_length=1)
    raw_execution_id: str = Field(min_length=1)
    result_id: str = Field(min_length=1)
    terminal_kind: TerminalKind
    component_attempts: tuple[ComponentAttemptEvidence, ...] = Field(max_length=4)
    failure_loci: tuple[FailureLocus, ...] = ()
    correction_count: int = Field(ge=0, le=4)
    terminal_projection_count: Literal[1] = 1
    schema_version: str = ARTIFACT_BACKED_OUTCOME_VERSION

    @model_validator(mode="after")
    def validate_trace(self) -> ArtifactBackedAttemptTrace:
        attempts = self.component_attempts
        if tuple(item.component_index for item in attempts) != tuple(range(len(attempts))):
            raise ValueError("artifact-backed AttemptTrace is not contiguous")
        if len({item.component_key for item in attempts}) != len(attempts):
            raise ValueError("artifact-backed AttemptTrace repeats a Component")
        terminal_indices = tuple(index for index, item in enumerate(attempts) if item.terminal)
        if terminal_indices and terminal_indices != (len(attempts) - 1,):
            raise ValueError("artifact-backed AttemptTrace continues after a terminal")
        if self.correction_count != sum(item.correction_invoked for item in attempts):
            raise ValueError("artifact-backed AttemptTrace correction count changed")
        if len({item.locus_id for item in self.failure_loci}) != len(self.failure_loci):
            raise ValueError("artifact-backed AttemptTrace repeats a FailureLocus")
        if self.trace_id != identity(
            self,
            "trace_id",
            "capability_artifact_backed_attempt_trace:",
        ):
            raise ValueError("artifact-backed AttemptTrace identity is invalid")
        return self


class ArtifactBackedCapabilityOutcomeRow(FrozenModel):
    row_id: str = Field(min_length=1)
    evidence_kind: EvidenceKind
    job_id: str = Field(min_length=1)
    manifest_id: str = Field(min_length=1)
    runner_id: str = Field(min_length=1)
    execution_package_id: str = Field(min_length=1)
    source_package_artifact_id: str = Field(min_length=1)
    replica_index: int = Field(ge=0, le=5)
    raw_namespace: str = Field(min_length=1)
    result_namespace: str = Field(min_length=1)
    raw_execution_id: str = Field(min_length=1)
    result_id: str = Field(min_length=1)
    trace_id: str = Field(min_length=1)
    terminal_kind: TerminalKind
    correction_count: int = Field(ge=0, le=4)
    first_policy_qualified_valid: bool
    bounded_policy_qualified_valid: bool
    task_completion: bool | None
    task_verifier_invoked: bool
    final_result_id: str | None = None
    final_base_valid: bool | None = None
    final_mechanism_qualified: bool | None = None
    final_qualified_valid: bool | None = None
    first_runtime_uncommitted_locus_id: str | None = None
    first_base_invalid_locus_id: str | None = None
    first_mechanism_failed_locus_id: str | None = None
    terminal_locus_id: str | None = None
    terminal_projection_count: Literal[1] = 1
    schema_version: str = ARTIFACT_BACKED_OUTCOME_VERSION

    @model_validator(mode="after")
    def validate_row(self) -> ArtifactBackedCapabilityOutcomeRow:
        expected_first = bool(self.final_qualified_valid is True and self.correction_count == 0)
        if self.first_policy_qualified_valid != expected_first:
            raise ValueError("artifact-backed q_first row value is not derived")
        if self.bounded_policy_qualified_valid != (self.final_qualified_valid is True):
            raise ValueError("artifact-backed bounded row value is not derived")
        if self.final_qualified_valid is not None and self.final_qualified_valid != bool(
            self.final_base_valid and self.final_mechanism_qualified
        ):
            raise ValueError("artifact-backed Qualified validity is not its conjunction")
        if self.row_id != identity(
            self,
            "row_id",
            "capability_artifact_backed_outcome_row:",
        ):
            raise ValueError("artifact-backed Outcome row identity is invalid")
        return self


class ArtifactBackedOutcomeContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    predecessor_registry_id: str = Field(min_length=1)
    predecessor_contract_id: str = Field(min_length=1)
    manifest_id: str = Field(min_length=1)
    runner_id: str = Field(min_length=1)
    job_component_sequences: tuple[JobComponentSequence, ...] = Field(
        min_length=192,
        max_length=192,
    )
    exact_job_count: Literal[192] = 192
    raw_and_result_sha256_required: Literal[True] = True
    raw_and_result_byte_count_required: Literal[True] = True
    canonical_artifact_loader_required: Literal[True] = True
    completed_validity_definition: Literal[
        "independent_base_and_mechanism_with_qualified_conjunction"
    ] = "independent_base_and_mechanism_with_qualified_conjunction"
    failure_locus_definition: Literal[
        "derived_only_from_attempt_trace_and_final_verifier_artifact"
    ] = "derived_only_from_attempt_trace_and_final_verifier_artifact"
    empirical_admissible_registration_status: Literal["reachable"] = "reachable"
    estimator_revalidates_registry: Literal[True] = True
    estimator_revalidates_contract: Literal[True] = True
    estimator_revalidates_manifest: Literal[True] = True
    estimator_revalidates_job: Literal[True] = True
    estimator_revalidates_runner: Literal[True] = True
    arbitrary_caller_loci_authoritative: Literal[False] = False
    exact_artifact_job_set_required: Literal[True] = True
    formal_empirical_rows_materialized: Literal[False] = False
    provider_calls: Literal[0] = 0
    schema_version: str = ARTIFACT_BACKED_OUTCOME_VERSION

    @model_validator(mode="after")
    def validate_contract(self) -> ArtifactBackedOutcomeContract:
        job_ids = tuple(item.job_id for item in self.job_component_sequences)
        if job_ids != tuple(sorted(set(job_ids))):
            raise ValueError("artifact-backed Contract Job sequences are not exact")
        if self.contract_id != identity(
            self,
            "contract_id",
            "capability_artifact_backed_outcome_contract:",
        ):
            raise ValueError("artifact-backed Outcome Contract identity is invalid")
        return self


class ArtifactBackedPreflightEvaluation(FrozenModel):
    evaluation_id: str = Field(min_length=1)
    contract_id: str = Field(min_length=1)
    manifest_id: str = Field(min_length=1)
    registry_id: str = Field(min_length=1)
    runner_id: str = Field(min_length=1)
    evidence_kind: Literal["scripted_preflight_control"] = "scripted_preflight_control"
    raw_descriptor_count: Literal[192] = 192
    result_descriptor_count: Literal[192] = 192
    trace_count: Literal[192] = 192
    outcome_row_count: Literal[192] = 192
    artifact_file_count: Literal[384] = 384
    artifact_byte_match_count: Literal[384] = 384
    exact_job_set_match: Literal[True] = True
    parent_revalidation_passed: Literal[True] = True
    failure_locus_reconstruction_passed: Literal[True] = True
    terminal_kind_counts: dict[str, int]
    empirical: Literal[False] = False
    empirical_numerator_materialized: Literal[False] = False
    provider_calls: Literal[0] = 0
    schema_version: str = ARTIFACT_BACKED_OUTCOME_VERSION

    @model_validator(mode="after")
    def validate_evaluation(self) -> ArtifactBackedPreflightEvaluation:
        if sum(self.terminal_kind_counts.values()) != self.outcome_row_count:
            raise ValueError("preflight terminal counts do not partition the exact Job set")
        if self.evaluation_id != identity(
            self,
            "evaluation_id",
            "capability_artifact_backed_preflight_evaluation:",
        ):
            raise ValueError("artifact-backed preflight evaluation identity is invalid")
        return self


class ArtifactBackedEmpiricalEvaluation(FrozenModel):
    evaluation_id: str = Field(min_length=1)
    contract_id: str = Field(min_length=1)
    manifest_id: str = Field(min_length=1)
    registry_id: str = Field(min_length=1)
    runner_id: str = Field(min_length=1)
    evidence_kind: Literal["empirical_execution"] = "empirical_execution"
    exact_job_count: Literal[192] = 192
    artifact_file_count: Literal[384] = 384
    artifact_byte_match_count: Literal[384] = 384
    terminal_kind_counts: dict[str, int]
    q_first_numerator: int = Field(ge=0, le=192)
    q_bounded_correction_numerator: int = Field(ge=0, le=192)
    q_first_fraction: str = Field(pattern=r"^[0-9]+/192$")
    q_bounded_correction_fraction: str = Field(pattern=r"^[0-9]+/192$")
    empirical: Literal[True] = True
    schema_version: str = ARTIFACT_BACKED_OUTCOME_VERSION

    @model_validator(mode="after")
    def validate_evaluation(self) -> ArtifactBackedEmpiricalEvaluation:
        if self.q_first_numerator > self.q_bounded_correction_numerator:
            raise ValueError("artifact-backed q_first exceeds bounded correction")
        if self.q_first_fraction != f"{self.q_first_numerator}/192":
            raise ValueError("artifact-backed q_first fraction is inconsistent")
        if self.q_bounded_correction_fraction != (f"{self.q_bounded_correction_numerator}/192"):
            raise ValueError("artifact-backed bounded fraction is inconsistent")
        if sum(self.terminal_kind_counts.values()) != self.exact_job_count:
            raise ValueError("empirical terminal counts do not partition the exact Job set")
        if self.evaluation_id != identity(
            self,
            "evaluation_id",
            "capability_artifact_backed_empirical_evaluation:",
        ):
            raise ValueError("artifact-backed empirical evaluation identity is invalid")
        return self


class ArtifactBackedEvidenceBundle(FrozenModel):
    raw: ArtifactBackedRawExecutionDescriptor
    result: ArtifactBackedJobResultDescriptor
    trace: ArtifactBackedAttemptTrace
    row: ArtifactBackedCapabilityOutcomeRow


def _validate_relative_path(value: str) -> None:
    path = PurePosixPath(value)
    if path.is_absolute() or not path.parts or any(part in {"", ".", ".."} for part in path.parts):
        raise ValueError("artifact descriptor path is not safe and relative")


def _strict_revalidate(model_type: type[BaseModel], value: BaseModel) -> Any:
    return model_type.model_validate(value.model_dump(mode="python", warnings=False))


def _artifact_path(root: Path, relative_path: str) -> Path:
    _validate_relative_path(relative_path)
    resolved_root = root.resolve()
    candidate = root.joinpath(*PurePosixPath(relative_path).parts)
    current = root
    for part in PurePosixPath(relative_path).parts:
        current = current / part
        if current.is_symlink():
            raise ValueError("artifact path contains a symlink")
    resolved_candidate = candidate.resolve(strict=False)
    if not resolved_candidate.is_relative_to(resolved_root):
        raise ValueError("artifact path escapes its exact root")
    return candidate


def write_canonical_artifact(root: Path, relative_path: str, value: BaseModel) -> tuple[str, int]:
    path = _artifact_path(root, relative_path)
    if path.exists():
        raise FileExistsError(f"artifact already exists:{relative_path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = canonical_model_bytes(value)
    with path.open("xb") as handle:
        handle.write(payload)
        handle.flush()
    return sha256_bytes(payload), len(payload)


def _load_canonical_artifact(
    *,
    root: Path,
    relative_path: str,
    expected_sha256: str,
    expected_byte_count: int,
    model_type: type[BaseModel],
) -> BaseModel:
    path = _artifact_path(root, relative_path)
    if not path.is_file() or path.is_symlink():
        raise ValueError("artifact descriptor does not resolve to a regular file")
    payload = path.read_bytes()
    if len(payload) != expected_byte_count or sha256_bytes(payload) != expected_sha256:
        raise ValueError("artifact descriptor does not bind the actual file bytes")
    try:
        decoded = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise ValueError("artifact is not valid JSON") from exc
    model = model_type.model_validate(decoded)
    if canonical_model_bytes(model) != payload:
        raise ValueError("artifact bytes are not the exact canonical model serialization")
    return model


def project_component_attempt(source: ComponentAttemptOutcome) -> ComponentAttemptEvidence:
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
            raise ValueError("source terminal attempt lacks an exact terminal mapping")
    return cast(
        ComponentAttemptEvidence,
        make_v2_identity_model(
            ComponentAttemptEvidence,
            {
                "component_index": source.component_index,
                "component_key": source.component_key,
                "reached_state_token": source.reached_state_token,
                "first_response_abi_valid": source.first_response_abi_valid,
                "first_action_reference_valid": first_reference_valid,
                "first_action_state_precondition_valid": (
                    source.first_action_state_precondition_valid
                ),
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
            },
            field="attempt_id",
            prefix="capability_authoritative_component_attempt:",
        ),
    )


def make_terminal_validity(
    *,
    terminal_kind: TerminalKind,
    policy_task_completion: bool | None,
    source_outcome: JobBoundOutcomePayload | None = None,
    base_failure_stage: BaseFailureStage | None = None,
    mechanism_failure_component_index: int | None = None,
) -> TerminalValidityEvidence:
    values: dict[str, Any] = {
        "task_completion": policy_task_completion,
        "task_verifier_invoked": False,
        "final_response_abi_valid": (
            False if terminal_kind == "final_response_abi_invalid" else None
        ),
    }
    if terminal_kind in {"completed_qualified", "completed_invalid"}:
        if source_outcome is None or not source_outcome.task_verifier_invoked:
            raise ValueError("completed terminal lacks exact source Verifier evidence")
        if source_outcome.endpoint_kind != terminal_kind:
            raise ValueError("completed terminal differs from source Outcome endpoint")
        mechanism_key = None
        if source_outcome.final_mechanism_qualified is False:
            if mechanism_failure_component_index is None:
                raise ValueError("Mechanism-invalid completion lacks a Verifier coordinate")
            if mechanism_failure_component_index >= len(source_outcome.component_attempts):
                raise ValueError("Mechanism failure coordinate is absent from the attempt trace")
            mechanism_key = source_outcome.component_attempts[
                mechanism_failure_component_index
            ].component_key
        values.update(
            task_completion=True,
            task_verifier_invoked=True,
            final_response_abi_valid=source_outcome.final_response_abi_valid,
            final_result_id=source_outcome.final_result_id,
            final_base_valid=source_outcome.final_base_valid,
            final_mechanism_qualified=source_outcome.final_mechanism_qualified,
            final_qualified_valid=source_outcome.final_qualified_valid,
            base_failure_stage=(
                base_failure_stage if source_outcome.final_base_valid is False else None
            ),
            mechanism_failure_component_index=mechanism_failure_component_index,
            mechanism_failure_component_key=mechanism_key,
        )
    return cast(
        TerminalValidityEvidence,
        make_identity_model(
            TerminalValidityEvidence,
            values,
            field="validity_id",
            prefix="capability_artifact_backed_terminal_validity:",
        ),
    )


def _failure_locus(
    *,
    stage: FailureStage,
    component_key: str | None,
    attempt_index: int | None,
    reason_code: str,
    evaluability: Literal["unevaluable", "evaluated_false", "not_applicable"],
    source_descriptor_id: str,
) -> FailureLocus:
    return cast(
        FailureLocus,
        make_v2_identity_model(
            FailureLocus,
            {
                "stage": stage,
                "component_key": component_key,
                "attempt_index": attempt_index,
                "reason_code": reason_code,
                "evaluability": evaluability,
                "source_descriptor_id": source_descriptor_id,
            },
            field="locus_id",
            prefix="capability_authoritative_failure_locus:",
        ),
    )


def derive_failure_loci(
    *,
    raw_descriptor: ArtifactBackedRawExecutionDescriptor,
    raw_payload: RawExecutionEvidencePayload,
    result_descriptor: ArtifactBackedJobResultDescriptor,
    result_payload: ArtifactBackedJobResultPayload,
) -> tuple[FailureLocus, ...]:
    terminal_kind = result_payload.terminal_kind
    validity = result_payload.validity
    loci: list[FailureLocus] = []
    if terminal_kind == "completed_qualified":
        return ()
    if terminal_kind == "completed_invalid":
        if validity.final_base_valid is False:
            if validity.base_failure_stage is None:
                raise ValueError("Base-invalid completion lacks a derived failure stage")
            loci.append(
                _failure_locus(
                    stage=validity.base_failure_stage,
                    component_key=None,
                    attempt_index=None,
                    reason_code=f"final_{validity.base_failure_stage}_invalid",
                    evaluability="evaluated_false",
                    source_descriptor_id=result_descriptor.result_id,
                )
            )
        if validity.final_mechanism_qualified is False:
            loci.append(
                _failure_locus(
                    stage="mechanism",
                    component_key=validity.mechanism_failure_component_key,
                    attempt_index=validity.mechanism_failure_component_index,
                    reason_code="final_mechanism_unqualified",
                    evaluability="evaluated_false",
                    source_descriptor_id=result_descriptor.result_id,
                )
            )
        if not loci:
            raise ValueError("completed-invalid terminal has no derived invalid factor")
        return tuple(loci)
    component_mapping: dict[
        str,
        tuple[FailureStage, str, Literal["unevaluable", "evaluated_false", "not_applicable"]],
    ] = {
        "first_response_abi_invalid": (
            "action_abi",
            "first_response_abi_invalid",
            "unevaluable",
        ),
        "correction_response_abi_invalid": (
            "action_abi",
            "correction_response_abi_invalid",
            "unevaluable",
        ),
        "first_action_reference_invalid": (
            "action_reference",
            "first_action_reference_invalid",
            "unevaluable",
        ),
        "correction_action_reference_invalid": (
            "action_reference",
            "correction_action_reference_invalid",
            "unevaluable",
        ),
        "correction_attempt_typed_invalid": (
            "state_precondition",
            "correction_attempt_typed_invalid",
            "evaluated_false",
        ),
        "measurement_support_exit": (
            "operation_support",
            "measurement_support_exit",
            "not_applicable",
        ),
    }
    if terminal_kind in component_mapping:
        attempts = raw_payload.component_attempts
        if not attempts or attempts[-1].terminal_kind != terminal_kind:
            raise ValueError("Component terminal lacks its exact terminal attempt")
        stage, reason, evaluability = component_mapping[terminal_kind]
        attempt = attempts[-1]
        return (
            _failure_locus(
                stage=stage,
                component_key=attempt.component_key,
                attempt_index=attempt.component_index,
                reason_code=reason,
                evaluability=evaluability,
                source_descriptor_id=raw_descriptor.raw_execution_id,
            ),
        )
    outer_mapping: dict[
        str,
        tuple[FailureStage, Literal["unevaluable", "not_applicable"]],
    ] = {
        "final_response_abi_invalid": ("final_abi", "unevaluable"),
        "provider_failure_no_payload": ("provider", "unevaluable"),
        "provider_transport_failure": ("transport", "unevaluable"),
        "privacy_rejection": ("privacy", "unevaluable"),
        "resource_budget_exhausted": ("resource", "unevaluable"),
        "instrument_failure": ("instrument", "unevaluable"),
        "provider_identity_failure": ("model_identity", "unevaluable"),
        "thinking_integrity_failure": ("thinking", "unevaluable"),
        "usage_integrity_failure": ("usage", "unevaluable"),
        "policy_horizon_exhausted": ("policy", "not_applicable"),
    }
    stage, evaluability = outer_mapping[terminal_kind]
    source_id = (
        result_descriptor.result_id
        if terminal_kind == "final_response_abi_invalid"
        else raw_descriptor.raw_execution_id
    )
    return (
        _failure_locus(
            stage=stage,
            component_key=None,
            attempt_index=None,
            reason_code=terminal_kind,
            evaluability=evaluability,
            source_descriptor_id=source_id,
        ),
    )


def _locus_projection(loci: Sequence[FailureLocus]) -> dict[str, str | None]:
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


def _build_trace_and_row(
    *,
    job: CapabilityDevelopmentJob,
    manifest: CapabilityDevelopmentJobManifest,
    runner: JobBoundRunnerContract,
    raw: ArtifactBackedRawExecutionDescriptor,
    raw_payload: RawExecutionEvidencePayload,
    result: ArtifactBackedJobResultDescriptor,
    result_payload: ArtifactBackedJobResultPayload,
) -> tuple[ArtifactBackedAttemptTrace, ArtifactBackedCapabilityOutcomeRow]:
    loci = derive_failure_loci(
        raw_descriptor=raw,
        raw_payload=raw_payload,
        result_descriptor=result,
        result_payload=result_payload,
    )
    trace = cast(
        ArtifactBackedAttemptTrace,
        make_identity_model(
            ArtifactBackedAttemptTrace,
            {
                "evidence_kind": raw.evidence_kind,
                "job_id": job.job_id,
                "raw_execution_id": raw.raw_execution_id,
                "result_id": result.result_id,
                "terminal_kind": result_payload.terminal_kind,
                "component_attempts": raw_payload.component_attempts,
                "failure_loci": loci,
                "correction_count": sum(
                    item.correction_invoked for item in raw_payload.component_attempts
                ),
            },
            field="trace_id",
            prefix="capability_artifact_backed_attempt_trace:",
        ),
    )
    validity = result_payload.validity
    row = cast(
        ArtifactBackedCapabilityOutcomeRow,
        make_identity_model(
            ArtifactBackedCapabilityOutcomeRow,
            {
                "evidence_kind": raw.evidence_kind,
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
                "terminal_kind": result_payload.terminal_kind,
                "correction_count": trace.correction_count,
                "first_policy_qualified_valid": bool(
                    validity.final_qualified_valid is True and trace.correction_count == 0
                ),
                "bounded_policy_qualified_valid": validity.final_qualified_valid is True,
                "task_completion": validity.task_completion,
                "task_verifier_invoked": validity.task_verifier_invoked,
                "final_result_id": validity.final_result_id,
                "final_base_valid": validity.final_base_valid,
                "final_mechanism_qualified": validity.final_mechanism_qualified,
                "final_qualified_valid": validity.final_qualified_valid,
                **_locus_projection(loci),
            },
            field="row_id",
            prefix="capability_artifact_backed_outcome_row:",
        ),
    )
    return trace, row


def _generic_terminal_attempt(
    *,
    terminal_kind: TerminalKind,
    state_token: str,
    component_key: str,
) -> ComponentAttemptEvidence:
    values: dict[str, Any] = {
        "component_index": 0,
        "component_key": component_key,
        "reached_state_token": state_token,
        "correction_invoked": False,
        "committed": False,
        "terminal": True,
        "terminal_kind": terminal_kind,
    }
    if terminal_kind == "first_response_abi_invalid":
        values.update(first_response_abi_valid=False)
    elif terminal_kind == "first_action_reference_invalid":
        values.update(
            first_response_abi_valid=True,
            first_action_reference_valid=False,
            first_action_accepted=False,
        )
    elif terminal_kind in {
        "correction_response_abi_invalid",
        "correction_action_reference_invalid",
        "correction_attempt_typed_invalid",
    }:
        values.update(
            first_response_abi_valid=True,
            first_action_reference_valid=True,
            first_action_state_precondition_valid=False,
            first_action_accepted=False,
            correction_invoked=True,
        )
        if terminal_kind == "correction_response_abi_invalid":
            values.update(correction_response_abi_valid=False)
        elif terminal_kind == "correction_action_reference_invalid":
            values.update(
                correction_response_abi_valid=True,
                corrected_action_reference_valid=False,
                corrected_action_accepted=False,
            )
        else:
            values.update(
                correction_response_abi_valid=True,
                corrected_action_reference_valid=True,
                corrected_action_state_precondition_valid=False,
                corrected_action_accepted=False,
            )
    elif terminal_kind == "measurement_support_exit":
        values.update(
            first_response_abi_valid=True,
            first_action_reference_valid=True,
            first_action_state_precondition_valid=True,
            first_action_accepted=True,
        )
    else:
        raise ValueError("terminal kind is not Component-local")
    return cast(
        ComponentAttemptEvidence,
        make_v2_identity_model(
            ComponentAttemptEvidence,
            values,
            field="attempt_id",
            prefix="capability_authoritative_component_attempt:",
        ),
    )


def build_artifact_backed_bundle(
    *,
    artifact_root: Path,
    job: CapabilityDevelopmentJob,
    manifest: CapabilityDevelopmentJobManifest,
    runner: JobBoundRunnerContract,
    registry: AuthoritativeTerminalRegistry,
    contract: ArtifactBackedOutcomeContract,
    terminal_kind: TerminalKind,
    evidence_kind: EvidenceKind,
    source_outcome: JobBoundOutcomePayload | None = None,
    base_failure_stage: BaseFailureStage | None = None,
    mechanism_failure_component_index: int | None = None,
) -> ArtifactBackedEvidenceBundle:
    policy = next(item for item in registry.policies if item.terminal_kind == terminal_kind)
    if source_outcome is not None:
        attempts = tuple(
            project_component_attempt(item) for item in source_outcome.component_attempts
        )
    elif terminal_kind in {
        "first_response_abi_invalid",
        "correction_response_abi_invalid",
        "first_action_reference_invalid",
        "correction_action_reference_invalid",
        "correction_attempt_typed_invalid",
        "measurement_support_exit",
    }:
        attempts = (
            _generic_terminal_attempt(
                terminal_kind=terminal_kind,
                state_token=canonical_hash(
                    {"job_id": job.job_id, "terminal_kind": terminal_kind},
                    prefix="capability_artifact_backed_terminal_state:",
                ).split(":", 1)[1][:24],
                component_key=contract.job_component_sequences[
                    tuple(item.job_id for item in contract.job_component_sequences).index(
                        job.job_id
                    )
                ].ordered_component_keys[0],
            ),
        )
    else:
        attempts = ()
    validity = make_terminal_validity(
        terminal_kind=terminal_kind,
        policy_task_completion=policy.expected_task_completion,
        source_outcome=source_outcome,
        base_failure_stage=base_failure_stage,
        mechanism_failure_component_index=mechanism_failure_component_index,
    )
    raw_payload = cast(
        RawExecutionEvidencePayload,
        make_v2_identity_model(
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
                    prefix="capability_artifact_backed_terminal_evidence:",
                ),
                "final_parser_input_hash": (
                    canonical_hash(
                        {"job_id": job.job_id, "terminal_kind": terminal_kind},
                        prefix="capability_artifact_backed_final_parser_input:",
                    )
                    if terminal_kind == "final_response_abi_invalid"
                    else None
                ),
                "final_parser_rejected": (
                    True if terminal_kind == "final_response_abi_invalid" else None
                ),
            },
            field="payload_id",
            prefix="capability_authoritative_raw_execution_payload:",
        ),
    )
    raw_path = expected_raw_artifact_filename(job)
    raw_sha256, raw_bytes = write_canonical_artifact(artifact_root, raw_path, raw_payload)
    raw = cast(
        ArtifactBackedRawExecutionDescriptor,
        make_identity_model(
            ArtifactBackedRawExecutionDescriptor,
            {
                "evidence_kind": evidence_kind,
                "job_id": job.job_id,
                "manifest_id": manifest.manifest_id,
                "runner_id": runner.runner_id,
                "execution_package_id": job.execution_package_id,
                "source_package_artifact_id": job.source_package_artifact_id,
                "replica_index": job.replica_index,
                "raw_namespace": job.raw_namespace,
                "artifact_relative_path": raw_path,
                "artifact_sha256": raw_sha256,
                "artifact_byte_count": raw_bytes,
                "payload_id": raw_payload.payload_id,
            },
            field="raw_execution_id",
            prefix="capability_artifact_backed_raw_execution:",
        ),
    )
    result_payload = cast(
        ArtifactBackedJobResultPayload,
        make_identity_model(
            ArtifactBackedJobResultPayload,
            {
                "job_id": job.job_id,
                "raw_execution_id": raw.raw_execution_id,
                "terminal_kind": terminal_kind,
                "validity": validity,
            },
            field="payload_id",
            prefix="capability_artifact_backed_job_result_payload:",
        ),
    )
    result_path = expected_result_artifact_filename(job)
    result_sha256, result_bytes = write_canonical_artifact(
        artifact_root,
        result_path,
        result_payload,
    )
    result = cast(
        ArtifactBackedJobResultDescriptor,
        make_identity_model(
            ArtifactBackedJobResultDescriptor,
            {
                "evidence_kind": evidence_kind,
                "job_id": job.job_id,
                "raw_execution_id": raw.raw_execution_id,
                "result_namespace": job.result_namespace,
                "artifact_relative_path": result_path,
                "artifact_sha256": result_sha256,
                "artifact_byte_count": result_bytes,
                "payload_id": result_payload.payload_id,
            },
            field="result_id",
            prefix="capability_artifact_backed_job_result:",
        ),
    )
    trace, row = _build_trace_and_row(
        job=job,
        manifest=manifest,
        runner=runner,
        raw=raw,
        raw_payload=raw_payload,
        result=result,
        result_payload=result_payload,
    )
    bundle = ArtifactBackedEvidenceBundle(raw=raw, result=result, trace=trace, row=row)
    validate_artifact_backed_bundle(
        artifact_root=artifact_root,
        job=job,
        manifest=manifest,
        runner=runner,
        registry=registry,
        contract=contract,
        bundle=bundle,
        expected_evidence_kind=evidence_kind,
    )
    return bundle


def _validated_parents(
    *,
    registry: AuthoritativeTerminalRegistry,
    contract: ArtifactBackedOutcomeContract,
    manifest: CapabilityDevelopmentJobManifest,
    runner: JobBoundRunnerContract,
) -> tuple[
    AuthoritativeTerminalRegistry,
    ArtifactBackedOutcomeContract,
    CapabilityDevelopmentJobManifest,
    JobBoundRunnerContract,
]:
    registry = cast(
        AuthoritativeTerminalRegistry,
        _strict_revalidate(AuthoritativeTerminalRegistry, registry),
    )
    contract = cast(
        ArtifactBackedOutcomeContract,
        _strict_revalidate(ArtifactBackedOutcomeContract, contract),
    )
    manifest = cast(
        CapabilityDevelopmentJobManifest,
        _strict_revalidate(CapabilityDevelopmentJobManifest, manifest),
    )
    runner = cast(
        JobBoundRunnerContract,
        _strict_revalidate(JobBoundRunnerContract, runner),
    )
    jobs = tuple(
        cast(
            CapabilityDevelopmentJob,
            _strict_revalidate(CapabilityDevelopmentJob, item),
        )
        for item in manifest.jobs
    )
    if jobs != manifest.jobs:
        raise ValueError("Manifest Job revalidation changed canonical objects")
    if (
        contract.predecessor_registry_id != registry.registry_id
        or contract.manifest_id != manifest.manifest_id
        or contract.runner_id != runner.runner_id
        or runner.manifest_id != manifest.manifest_id
    ):
        raise ValueError("artifact-backed Contract crosses its exact authority parents")
    sequences = {
        item.job_id: item.ordered_component_keys for item in contract.job_component_sequences
    }
    if set(sequences) != set(manifest.expected_job_ids):
        raise ValueError("artifact-backed Contract crosses the Manifest Job set")
    return registry, contract, manifest, runner


def validate_artifact_backed_bundle(
    *,
    artifact_root: Path,
    job: CapabilityDevelopmentJob,
    manifest: CapabilityDevelopmentJobManifest,
    runner: JobBoundRunnerContract,
    registry: AuthoritativeTerminalRegistry,
    contract: ArtifactBackedOutcomeContract,
    bundle: ArtifactBackedEvidenceBundle,
    expected_evidence_kind: EvidenceKind,
) -> None:
    registry, contract, manifest, runner = _validated_parents(
        registry=registry,
        contract=contract,
        manifest=manifest,
        runner=runner,
    )
    job = cast(CapabilityDevelopmentJob, _strict_revalidate(CapabilityDevelopmentJob, job))
    manifest_job = next((item for item in manifest.jobs if item.job_id == job.job_id), None)
    if manifest_job != job:
        raise ValueError("artifact-backed bundle Job is not the exact Manifest object")
    raw = cast(
        ArtifactBackedRawExecutionDescriptor,
        _strict_revalidate(ArtifactBackedRawExecutionDescriptor, bundle.raw),
    )
    result = cast(
        ArtifactBackedJobResultDescriptor,
        _strict_revalidate(ArtifactBackedJobResultDescriptor, bundle.result),
    )
    trace = cast(
        ArtifactBackedAttemptTrace,
        _strict_revalidate(ArtifactBackedAttemptTrace, bundle.trace),
    )
    row = cast(
        ArtifactBackedCapabilityOutcomeRow,
        _strict_revalidate(ArtifactBackedCapabilityOutcomeRow, bundle.row),
    )
    policy = next(item for item in registry.policies if item.terminal_kind == row.terminal_kind)
    if (
        expected_evidence_kind == "empirical_execution"
        and policy.registration_status != contract.empirical_admissible_registration_status
    ):
        raise ValueError("non-reachable terminal policy cannot enter empirical evidence")
    expected_raw_parents = (
        expected_evidence_kind,
        job.job_id,
        manifest.manifest_id,
        runner.runner_id,
        job.execution_package_id,
        job.source_package_artifact_id,
        job.replica_index,
        job.raw_namespace,
        expected_raw_artifact_filename(job),
    )
    observed_raw_parents = (
        raw.evidence_kind,
        raw.job_id,
        raw.manifest_id,
        raw.runner_id,
        raw.execution_package_id,
        raw.source_package_artifact_id,
        raw.replica_index,
        raw.raw_namespace,
        raw.artifact_relative_path,
    )
    if observed_raw_parents != expected_raw_parents:
        raise ValueError("artifact-backed Raw descriptor crosses the exact Manifest Job")
    raw_payload = cast(
        RawExecutionEvidencePayload,
        _load_canonical_artifact(
            root=artifact_root,
            relative_path=raw.artifact_relative_path,
            expected_sha256=raw.artifact_sha256,
            expected_byte_count=raw.artifact_byte_count,
            model_type=RawExecutionEvidencePayload,
        ),
    )
    if raw.payload_id != raw_payload.payload_id or (
        raw_payload.job_id,
        raw_payload.terminal_kind,
    ) != (job.job_id, row.terminal_kind):
        raise ValueError("artifact-backed Raw payload crosses its descriptor")
    if raw_payload.provider_artifact_ids != expected_provider_artifact_ids(
        job,
        row.terminal_kind,
    ) or raw_payload.transport_artifact_ids != expected_transport_artifact_ids(
        job,
        row.terminal_kind,
    ):
        raise ValueError("artifact-backed Raw payload crosses exact transport parents")
    sequence = next(
        item.ordered_component_keys
        for item in contract.job_component_sequences
        if item.job_id == job.job_id
    )
    observed_components = tuple(item.component_key for item in raw_payload.component_attempts)
    if observed_components != sequence[: len(observed_components)]:
        raise ValueError("artifact-backed attempt sequence crosses the frozen Job")
    completed = row.terminal_kind in {"completed_qualified", "completed_invalid"}
    if completed and (
        observed_components != sequence
        or not all(item.committed for item in raw_payload.component_attempts)
        or any(item.terminal for item in raw_payload.component_attempts)
    ):
        raise ValueError("completed artifact-backed terminal lacks exact committed attempts")
    expected_result_parents = (
        expected_evidence_kind,
        job.job_id,
        raw.raw_execution_id,
        job.result_namespace,
        expected_result_artifact_filename(job),
    )
    observed_result_parents = (
        result.evidence_kind,
        result.job_id,
        result.raw_execution_id,
        result.result_namespace,
        result.artifact_relative_path,
    )
    if observed_result_parents != expected_result_parents:
        raise ValueError("artifact-backed Result descriptor crosses Raw or Job")
    result_payload = cast(
        ArtifactBackedJobResultPayload,
        _load_canonical_artifact(
            root=artifact_root,
            relative_path=result.artifact_relative_path,
            expected_sha256=result.artifact_sha256,
            expected_byte_count=result.artifact_byte_count,
            model_type=ArtifactBackedJobResultPayload,
        ),
    )
    if result.payload_id != result_payload.payload_id or (
        result_payload.job_id,
        result_payload.raw_execution_id,
        result_payload.terminal_kind,
    ) != (job.job_id, raw.raw_execution_id, row.terminal_kind):
        raise ValueError("artifact-backed Result payload crosses its descriptor")
    validity = result_payload.validity
    policy_values = (
        policy.expected_task_completion,
        policy.expected_task_verifier_invoked,
        policy.expected_base_validity,
        policy.expected_mechanism_qualification,
        policy.expected_qualified_validity,
    )
    observed_values = (
        validity.task_completion,
        validity.task_verifier_invoked,
        validity.final_base_valid,
        validity.final_mechanism_qualified,
        validity.final_qualified_valid,
    )
    if row.terminal_kind == "completed_invalid":
        if not (
            validity.task_completion is True
            and validity.task_verifier_invoked
            and validity.final_qualified_valid is False
            and (validity.final_base_valid is False or validity.final_mechanism_qualified is False)
        ):
            raise ValueError("completed-invalid terminal lost independent validity factors")
    elif row.terminal_kind == "completed_qualified":
        if observed_values != policy_values:
            raise ValueError("completed Outcome differs from exact terminal policy")
    elif (
        validity.task_completion,
        validity.task_verifier_invoked,
    ) != (
        policy.expected_task_completion,
        policy.expected_task_verifier_invoked,
    ):
        raise ValueError("non-completed Outcome differs from its terminal boundary policy")
    expected_trace, expected_row = _build_trace_and_row(
        job=job,
        manifest=manifest,
        runner=runner,
        raw=raw,
        raw_payload=raw_payload,
        result=result,
        result_payload=result_payload,
    )
    if trace != expected_trace:
        raise ValueError("AttemptTrace or FailureLocus is not reconstructed from artifacts")
    if row != expected_row:
        raise ValueError("Outcome row is not reconstructed from artifact-backed evidence")


def evaluate_artifact_backed_evidence_set(
    *,
    artifact_root: Path,
    bundles: Sequence[ArtifactBackedEvidenceBundle],
    manifest: CapabilityDevelopmentJobManifest,
    registry: AuthoritativeTerminalRegistry,
    contract: ArtifactBackedOutcomeContract,
    runner: JobBoundRunnerContract,
    expected_evidence_kind: EvidenceKind,
) -> ArtifactBackedPreflightEvaluation | ArtifactBackedEmpiricalEvaluation:
    registry, contract, manifest, runner = _validated_parents(
        registry=registry,
        contract=contract,
        manifest=manifest,
        runner=runner,
    )
    if len(bundles) != EXPECTED_JOB_COUNT:
        raise ValueError("artifact-backed evidence differs from the exact Manifest denominator")
    by_job: dict[str, ArtifactBackedEvidenceBundle] = {}
    for item in bundles:
        item = cast(
            ArtifactBackedEvidenceBundle,
            _strict_revalidate(ArtifactBackedEvidenceBundle, item),
        )
        if item.row.job_id in by_job:
            raise ValueError("artifact-backed evidence repeats a Job")
        by_job[item.row.job_id] = item
    if set(by_job) != set(manifest.expected_job_ids):
        raise ValueError("artifact-backed evidence Job set differs from the Manifest")
    identity_sets = (
        {item.raw.raw_execution_id for item in bundles},
        {item.result.result_id for item in bundles},
        {item.trace.trace_id for item in bundles},
        {item.row.row_id for item in bundles},
    )
    if any(len(items) != EXPECTED_JOB_COUNT for items in identity_sets):
        raise ValueError("artifact-backed evidence repeats a content identity")
    jobs = {item.job_id: item for item in manifest.jobs}
    for job_id in manifest.expected_job_ids:
        validate_artifact_backed_bundle(
            artifact_root=artifact_root,
            job=jobs[job_id],
            manifest=manifest,
            runner=runner,
            registry=registry,
            contract=contract,
            bundle=by_job[job_id],
            expected_evidence_kind=expected_evidence_kind,
        )
    rows = tuple(by_job[job_id].row for job_id in manifest.expected_job_ids)
    terminal_counts = dict(sorted(Counter(item.terminal_kind for item in rows).items()))
    common = {
        "contract_id": contract.contract_id,
        "manifest_id": manifest.manifest_id,
        "registry_id": registry.registry_id,
        "runner_id": runner.runner_id,
        "terminal_kind_counts": terminal_counts,
    }
    if expected_evidence_kind == "scripted_preflight_control":
        return cast(
            ArtifactBackedPreflightEvaluation,
            make_identity_model(
                ArtifactBackedPreflightEvaluation,
                common,
                field="evaluation_id",
                prefix="capability_artifact_backed_preflight_evaluation:",
            ),
        )
    q_first = sum(item.first_policy_qualified_valid for item in rows)
    q_bounded = sum(item.bounded_policy_qualified_valid for item in rows)
    return cast(
        ArtifactBackedEmpiricalEvaluation,
        make_identity_model(
            ArtifactBackedEmpiricalEvaluation,
            {
                **common,
                "q_first_numerator": q_first,
                "q_bounded_correction_numerator": q_bounded,
                "q_first_fraction": f"{q_first}/192",
                "q_bounded_correction_fraction": f"{q_bounded}/192",
            },
            field="evaluation_id",
            prefix="capability_artifact_backed_empirical_evaluation:",
        ),
    )


def contract_from_v2(
    *,
    registry: AuthoritativeTerminalRegistry,
    predecessor_contract_id: str,
    manifest: CapabilityDevelopmentJobManifest,
    runner: JobBoundRunnerContract,
    job_component_sequences: Sequence[JobComponentSequence],
) -> ArtifactBackedOutcomeContract:
    return cast(
        ArtifactBackedOutcomeContract,
        make_identity_model(
            ArtifactBackedOutcomeContract,
            {
                "predecessor_registry_id": registry.registry_id,
                "predecessor_contract_id": predecessor_contract_id,
                "manifest_id": manifest.manifest_id,
                "runner_id": runner.runner_id,
                "job_component_sequences": tuple(job_component_sequences),
            },
            field="contract_id",
            prefix="capability_artifact_backed_outcome_contract:",
        ),
    )


__all__ = [
    "ARTIFACT_BACKED_OUTCOME_VERSION",
    "ArtifactBackedAttemptTrace",
    "ArtifactBackedCapabilityOutcomeRow",
    "ArtifactBackedEmpiricalEvaluation",
    "ArtifactBackedEvidenceBundle",
    "ArtifactBackedJobResultDescriptor",
    "ArtifactBackedJobResultPayload",
    "ArtifactBackedOutcomeContract",
    "ArtifactBackedPreflightEvaluation",
    "ArtifactBackedRawExecutionDescriptor",
    "BaseFailureStage",
    "TerminalValidityEvidence",
    "build_artifact_backed_bundle",
    "canonical_model_bytes",
    "contract_from_v2",
    "derive_failure_loci",
    "evaluate_artifact_backed_evidence_set",
    "expected_raw_artifact_filename",
    "expected_result_artifact_filename",
    "identity",
    "make_identity_model",
    "make_terminal_validity",
    "project_component_attempt",
    "sha256_bytes",
    "validate_artifact_backed_bundle",
    "write_canonical_artifact",
]
