from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any, Final, Literal, cast

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from trusted_synthesis.core.evaluation.answer_semantics import (
    compare_answer_by_schema,
    make_answer_semantic_schema,
)
from trusted_synthesis.core.evaluation.joint_support_validity import (
    JointSupportValidityContract,
    JointSupportValidityResult,
    evaluate_joint_support_validity,
    make_joint_support_validity_contract,
)
from trusted_synthesis.core.evaluation.trajectory_validity import (
    BaseValidityChecks,
    ContextMechanismEvidence,
    MechanismId,
    ReconciliationMechanismEvidence,
    RecoveryMechanismEvidence,
    StoppingMechanismEvidence,
    make_noninterference_artifact_binding,
    qualify_context_mechanism,
    qualify_reconciliation_mechanism,
    qualify_recovery_mechanism,
    qualify_stopping_mechanism,
)
from trusted_synthesis.core.measurement.support import (
    BaselineActionSetResolution,
    MeasurementSupportDecision,
    classify_measurement_support,
    make_baseline_resolution,
    make_measurement_support_event,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_measurement_support_boundary_redesign as support_stage,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_verifier_vnext_contract_freeze as predecessor,
)
from trusted_synthesis.hashing import canonical_hash

RUN_ID: Final = "finance_v26_149_joint_support_verifier_preflight_v1_20260825"
OUTPUT_DIR: Final = (
    "artifacts/vtdo_experiment/finance_v26_149_joint_support_verifier_preflight_v1_20260825"
)
IMPLEMENTATION_PATHS: Final = (
    "src/trusted_synthesis/core/evaluation/joint_support_validity.py",
    "src/trusted_synthesis/experiments/vtdo_experiment/"
    "phase1_v26_joint_support_verifier_preflight.py",
)
PREDECESSOR_DIR: Final = predecessor.OUTPUT_DIR
NEXT_STAGE: Final = "fresh_capability_population_and_runner_rematerialization_preflight_only"

EXPECTED_PREDECESSOR_REPORT_ID: Final = (
    "finance_v26_verifier_vnext_freeze_report:"
    "3d75e805997c2511626db93cafc095a2a21bf988d6269cfdb6bd9e953788ff75"
)
EXPECTED_PREDECESSOR_REPORT_SHA256: Final = (
    "93a300c4a2284fe2213a7797940912490a9894b8e9ff0e4183db6a849bfa335e"
)
EXPECTED_PREDECESSOR_TRANSITION_ID: Final = (
    "finance_v26_verifier_vnext_transition:"
    "eab4f37ae38bc033981ab72b2b38a4fc939a52d8e353349a540baca35b4172d9"
)
EXPECTED_SUPPORT_CONTRACT_ID: Final = (
    "prospective_measurement_support_contract:"
    "b49e6a5d66ee7d423ef9944739b30a516d5df84003e157055e99faefdb84398b"
)
EXPECTED_BASELINE_AUTHORITY_AUDIT_ID: Final = (
    "finance_v26_public_baseline_authority_audit:"
    "ef276425a9786d7edd8301320ffc4218f4dd40f9cfc484eba06f43f56c2779c3"
)


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


def _identity(value: BaseModel, field: str, prefix: str) -> str:
    return canonical_hash(value.model_dump(mode="json", exclude={field}), prefix=prefix)


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _canonical_bytes(value: Any) -> bytes:
    payload = value.model_dump(mode="json") if isinstance(value, BaseModel) else value
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _write_json_atomic(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(_canonical_bytes(value))
    temporary.replace(path)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _find_bound_path(
    relative_path: str,
    expected_sha256: str,
    *,
    package_root: Path,
    implementation_root: Path,
) -> Path:
    for root in (implementation_root, package_root):
        candidate = root / relative_path
        if candidate.is_file() and _sha256(candidate) == expected_sha256:
            return candidate
    raise ValueError(f"v26.149 cannot replay bound file: {relative_path}")


class SourceReplayEntry(FrozenModel):
    relative_path: str = Field(min_length=1)
    source_kind: Literal[
        "v26_148_transitive_source",
        "v26_148_output",
        "v26_149_implementation",
    ]
    expected_sha256: str = Field(min_length=64, max_length=64)
    observed_sha256: str = Field(min_length=64, max_length=64)
    byte_count: int = Field(gt=0)
    passed: Literal[True] = True


class SourceReplayAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    predecessor_report_id: str = EXPECTED_PREDECESSOR_REPORT_ID
    predecessor_transition_id: str = EXPECTED_PREDECESSOR_TRANSITION_ID
    predecessor_transitive_file_count: Literal[7318] = 7318
    predecessor_output_file_count: Literal[12] = 12
    implementation_file_count: Literal[2] = 2
    replayed_file_count: Literal[7332] = 7332
    replay_pass_count: Literal[7332] = 7332
    entries: tuple[SourceReplayEntry, ...] = Field(min_length=7332, max_length=7332)
    replay_before_joint_runtime_loading: Literal[True] = True
    credential_lookup_attempted: Literal[False] = False
    model_client_constructed: Literal[False] = False
    provider_calls: Literal[0] = 0
    stage_two_provider_calls: Literal[0] = 0
    gpu_jobs: Literal[0] = 0
    status: Literal["passed"] = "passed"
    schema_version: Literal["finance_v26_joint_support_verifier_source_replay.v1"] = (
        "finance_v26_joint_support_verifier_source_replay.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> SourceReplayAudit:
        paths = tuple(item.relative_path for item in self.entries)
        if (
            paths != tuple(sorted(set(paths)))
            or len(paths) != self.replayed_file_count
            or any(item.expected_sha256 != item.observed_sha256 for item in self.entries)
        ):
            raise ValueError("v26.149 source replay changed")
        if self.audit_id != _identity(
            self,
            "audit_id",
            "finance_v26_joint_support_verifier_source_replay:",
        ):
            raise ValueError("v26.149 source replay identity changed")
        return self


class FileComparison(FrozenModel):
    relative_path: str = Field(min_length=1)
    expected_sha256: str = Field(min_length=64, max_length=64)
    observed_sha256: str = Field(min_length=64, max_length=64)
    byte_count: int = Field(gt=0)
    byte_identical: Literal[True] = True


class PredecessorIntegrityAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    source_replay_audit_id: str = Field(min_length=1)
    comparisons: tuple[FileComparison, ...] = Field(min_length=12, max_length=12)
    predecessor_output_file_count: Literal[12] = 12
    byte_identical_file_count: Literal[12] = 12
    historical_reclassified_count: Literal[0] = 0
    provider_calls: Literal[0] = 0
    status: Literal["passed"] = "passed"
    schema_version: Literal["finance_v26_joint_support_verifier_predecessor_integrity.v1"] = (
        "finance_v26_joint_support_verifier_predecessor_integrity.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> PredecessorIntegrityAudit:
        paths = tuple(item.relative_path for item in self.comparisons)
        if paths != tuple(sorted(set(paths))) or any(
            item.expected_sha256 != item.observed_sha256 for item in self.comparisons
        ):
            raise ValueError("v26.149 predecessor comparison changed")
        if self.audit_id != _identity(
            self,
            "audit_id",
            "finance_v26_joint_support_verifier_predecessor_integrity:",
        ):
            raise ValueError("v26.149 predecessor identity changed")
        return self


class AuthorityBindingAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    measurement_support_contract_id: str = EXPECTED_SUPPORT_CONTRACT_ID
    baseline_authority_audit_id: str = EXPECTED_BASELINE_AUTHORITY_AUDIT_ID
    verifier_vnext_contract_id: str = Field(min_length=1)
    final_grammar_id: str = Field(min_length=1)
    answer_semantics_contract_id: str = Field(min_length=1)
    eligibility_contract_id: str = Field(min_length=1)
    mechanism_contract_id: str = Field(min_length=1)
    banned_baseline_read_count: Literal[0] = 0
    oracle_read_count: Literal[0] = 0
    gold_read_count: Literal[0] = 0
    correct_answer_read_count: Literal[0] = 0
    host_semantic_insertion_allowed: Literal[False] = False
    stage_two_provider_call_upper_bound: Literal[0] = 0
    provider_calls: Literal[0] = 0
    status: Literal["passed"] = "passed"
    schema_version: Literal["finance_v26_joint_authority_binding.v1"] = (
        "finance_v26_joint_authority_binding.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> AuthorityBindingAudit:
        if self.audit_id != _identity(
            self,
            "audit_id",
            "finance_v26_joint_authority_binding:",
        ):
            raise ValueError("v26.149 authority binding identity changed")
        return self


class PositiveFixtureRow(FrozenModel):
    row_id: str = Field(min_length=1)
    fixture_name: str = Field(min_length=1)
    support_status: Literal["available", "not_required", "unavailable"]
    baseline_classifier_invocation_count: int = Field(ge=0, le=1)
    endpoint_disposition: str = Field(min_length=1)
    validity_evaluable: bool
    task_verifier_invocation_count: Literal[0, 1]
    base_valid: bool | None
    mechanism_success: bool | None
    qualified_valid: bool | None
    state_mapping_eligible: bool
    passed: Literal[True] = True

    @model_validator(mode="after")
    def validate_row(self) -> PositiveFixtureRow:
        if self.row_id != _identity(
            self,
            "row_id",
            "finance_v26_joint_positive_fixture_row:",
        ):
            raise ValueError("v26.149 positive fixture identity changed")
        return self


class PositiveFixtureAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    joint_contract_id: str = Field(min_length=1)
    rows: tuple[PositiveFixtureRow, ...] = Field(min_length=19, max_length=19)
    fixture_count: Literal[19] = 19
    passed_count: Literal[19] = 19
    support_exit_task_verifier_invocation_count: Literal[0] = 0
    missing_endpoint_task_verifier_invocation_count: Literal[0] = 0
    instrument_failure_task_verifier_invocation_count: Literal[0] = 0
    privacy_rejection_task_verifier_invocation_count: Literal[0] = 0
    failed_observation_baseline_invocation_count: Literal[0] = 0
    progress_observation_baseline_invocation_count: Literal[0] = 0
    successful_no_progress_baseline_invocation_count: Literal[1] = 1
    provider_calls: Literal[0] = 0
    stage_two_provider_calls: Literal[0] = 0
    status: Literal["passed"] = "passed"
    schema_version: Literal["finance_v26_joint_positive_fixture.v1"] = (
        "finance_v26_joint_positive_fixture.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> PositiveFixtureAudit:
        names = tuple(item.fixture_name for item in self.rows)
        if names != tuple(sorted(set(names))):
            raise ValueError("v26.149 positive fixture set changed")
        if self.audit_id != _identity(
            self,
            "audit_id",
            "finance_v26_joint_positive_fixture:",
        ):
            raise ValueError("v26.149 positive fixture identity changed")
        return self


class StageOrderingAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    joint_contract_id: str = Field(min_length=1)
    exact_state_machine_order: tuple[str, ...]
    measurement_support_before_endpoint: Literal[True] = True
    endpoint_before_eligibility: Literal[True] = True
    eligibility_before_task_verifier: Literal[True] = True
    base_before_qualified: Literal[True] = True
    mechanism_before_qualified: Literal[True] = True
    ineligible_later_stage_invocation_count: Literal[0] = 0
    support_exit_model_invalid_count: Literal[0] = 0
    instrument_failure_model_invalid_count: Literal[0] = 0
    privacy_rejection_answer_inference_count: Literal[0] = 0
    state_mapping_before_qualified_count: Literal[0] = 0
    provider_calls: Literal[0] = 0
    status: Literal["passed"] = "passed"
    schema_version: Literal["finance_v26_joint_stage_ordering.v1"] = (
        "finance_v26_joint_stage_ordering.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> StageOrderingAudit:
        if self.audit_id != _identity(
            self,
            "audit_id",
            "finance_v26_joint_stage_ordering:",
        ):
            raise ValueError("v26.149 stage-order identity changed")
        return self


class MutationResult(FrozenModel):
    mutation_name: str = Field(min_length=1)
    failure_type: str = Field(min_length=1)
    rejected: Literal[True] = True


class DestructiveAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    mutation_results: tuple[MutationResult, ...] = Field(min_length=20, max_length=20)
    mutation_count: Literal[20] = 20
    rejected_count: Literal[20] = 20
    provider_calls: Literal[0] = 0
    status: Literal["passed"] = "passed"
    schema_version: Literal["finance_v26_joint_support_verifier_destructive.v1"] = (
        "finance_v26_joint_support_verifier_destructive.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> DestructiveAudit:
        names = tuple(item.mutation_name for item in self.mutation_results)
        if names != tuple(sorted(set(names))):
            raise ValueError("v26.149 destructive mutation set changed")
        if self.audit_id != _identity(
            self,
            "audit_id",
            "finance_v26_joint_support_verifier_destructive:",
        ):
            raise ValueError("v26.149 destructive identity changed")
        return self


class ProspectiveTransitionContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    joint_contract_id: str = Field(min_length=1)
    fixture_audit_id: str = Field(min_length=1)
    destructive_audit_id: str = Field(min_length=1)
    next_permitted_stage: Literal[
        "fresh_capability_population_and_runner_rematerialization_preflight_only"
    ] = NEXT_STAGE
    fresh_capability_population_runner_preflight_authorized: Literal[True] = True
    provider_calls_authorized: Literal[False] = False
    capability_execution_authorized: Literal[False] = False
    reachability_identity_or_execution_authorized: Literal[False] = False
    historical_reclassification_authorized: Literal[False] = False
    state_mapping_authorized: Literal[False] = False
    training_release_or_production_authorized: Literal[False] = False
    schema_version: Literal["finance_v26_joint_support_verifier_transition.v1"] = (
        "finance_v26_joint_support_verifier_transition.v1"
    )

    @model_validator(mode="after")
    def validate_contract(self) -> ProspectiveTransitionContract:
        if self.contract_id != _identity(
            self,
            "contract_id",
            "finance_v26_joint_support_verifier_transition:",
        ):
            raise ValueError("v26.149 transition identity changed")
        return self


class DetailFile(FrozenModel):
    relative_path: str = Field(min_length=1)
    sha256: str = Field(min_length=64, max_length=64)
    byte_count: int = Field(gt=0)


class JointPreflightReport(FrozenModel):
    report_id: str = Field(min_length=1)
    run_id: str = RUN_ID
    source_replay_audit_id: str = Field(min_length=1)
    predecessor_integrity_audit_id: str = Field(min_length=1)
    authority_binding_audit_id: str = Field(min_length=1)
    joint_contract_id: str = Field(min_length=1)
    positive_fixture_audit_id: str = Field(min_length=1)
    stage_ordering_audit_id: str = Field(min_length=1)
    destructive_audit_id: str = Field(min_length=1)
    transition_contract_id: str = Field(min_length=1)
    positive_fixture_count: Literal[19] = 19
    destructive_mutation_count: Literal[20] = 20
    historical_reclassified_count: Literal[0] = 0
    capability_population_or_identity_count: Literal[0] = 0
    provider_calls: Literal[0] = 0
    stage_two_provider_calls: Literal[0] = 0
    gpu_jobs: Literal[0] = 0
    reachability_identity_count: Literal[0] = 0
    state_mapping_row_count: Literal[0] = 0
    production_contribution: Literal[0] = 0
    next_permitted_stage: Literal[
        "fresh_capability_population_and_runner_rematerialization_preflight_only"
    ] = NEXT_STAGE
    detail_files: tuple[DetailFile, ...] = Field(min_length=8, max_length=8)
    status: Literal["joint_support_verifier_preflight_passed"] = (
        "joint_support_verifier_preflight_passed"
    )
    schema_version: Literal["finance_v26_joint_support_verifier_preflight_report.v1"] = (
        "finance_v26_joint_support_verifier_preflight_report.v1"
    )

    @model_validator(mode="after")
    def validate_report(self) -> JointPreflightReport:
        paths = tuple(item.relative_path for item in self.detail_files)
        if paths != tuple(sorted(set(paths))):
            raise ValueError("v26.149 report detail files changed")
        if self.report_id != _identity(
            self,
            "report_id",
            "finance_v26_joint_support_verifier_preflight_report:",
        ):
            raise ValueError("v26.149 report identity changed")
        return self


def _source_replay(
    *,
    package_root: Path,
    implementation_root: Path,
) -> SourceReplayAudit:
    predecessor_dir = package_root / PREDECESSOR_DIR
    report_path = predecessor_dir / "report.json"
    report = predecessor.VerifierVNextFreezeReport.model_validate(_load(report_path))
    transition = predecessor.ProspectiveTransitionContract.model_validate(
        _load(predecessor_dir / "prospective_transition_contract.json")
    )
    if (
        _sha256(report_path) != EXPECTED_PREDECESSOR_REPORT_SHA256
        or report.report_id != EXPECTED_PREDECESSOR_REPORT_ID
        or report.transition_contract_id != EXPECTED_PREDECESSOR_TRANSITION_ID
        or transition.contract_id != EXPECTED_PREDECESSOR_TRANSITION_ID
        or transition.next_permitted_stage
        != "measurement_support_verifier_vnext_joint_preflight_only"
        or not transition.joint_support_verifier_preflight_authorized
        or transition.provider_calls_authorized
    ):
        raise ValueError("v26.149 direct predecessor decision changed")
    predecessor_source = predecessor.SourceReplayAudit.model_validate(
        _load(predecessor_dir / "source_replay_audit.json")
    )
    entries: list[SourceReplayEntry] = []
    for item in predecessor_source.entries:
        path = _find_bound_path(
            item.relative_path,
            item.expected_sha256,
            package_root=package_root,
            implementation_root=implementation_root,
        )
        entries.append(
            SourceReplayEntry(
                relative_path=item.relative_path,
                source_kind="v26_148_transitive_source",
                expected_sha256=item.expected_sha256,
                observed_sha256=_sha256(path),
                byte_count=path.stat().st_size,
            )
        )
    expected_outputs = {item.relative_path: item.sha256 for item in report.detail_files}
    expected_outputs["report.json"] = EXPECTED_PREDECESSOR_REPORT_SHA256
    for name, expected_sha256 in sorted(expected_outputs.items()):
        path = predecessor_dir / name
        if _sha256(path) != expected_sha256:
            raise ValueError(f"v26.149 predecessor output changed: {name}")
        entries.append(
            SourceReplayEntry(
                relative_path=str(path.relative_to(package_root)),
                source_kind="v26_148_output",
                expected_sha256=expected_sha256,
                observed_sha256=_sha256(path),
                byte_count=path.stat().st_size,
            )
        )
    for relative_path in IMPLEMENTATION_PATHS:
        path = implementation_root / relative_path
        digest = _sha256(path)
        entries.append(
            SourceReplayEntry(
                relative_path=relative_path,
                source_kind="v26_149_implementation",
                expected_sha256=digest,
                observed_sha256=digest,
                byte_count=path.stat().st_size,
            )
        )
    ordered = tuple(sorted(entries, key=lambda item: item.relative_path))
    values = {"entries": ordered}
    provisional = SourceReplayAudit.model_construct(audit_id="pending", **values)
    return SourceReplayAudit(
        audit_id=_identity(
            provisional,
            "audit_id",
            "finance_v26_joint_support_verifier_source_replay:",
        ),
        **values,
    )


def _predecessor_integrity(
    *,
    package_root: Path,
    implementation_root: Path,
    source: SourceReplayAudit,
) -> PredecessorIntegrityAudit:
    formal_dir = package_root / PREDECESSOR_DIR
    with tempfile.TemporaryDirectory(prefix="v26_149_predecessor_") as directory:
        rebuilt_dir = Path(directory)
        predecessor.build_verifier_vnext_contract_freeze(
            package_root=package_root,
            implementation_root=implementation_root,
            output_dir=rebuilt_dir,
        )
        formal_paths = tuple(sorted(path for path in formal_dir.iterdir() if path.is_file()))
        rebuilt_paths = tuple(sorted(path for path in rebuilt_dir.iterdir() if path.is_file()))
        if tuple(path.name for path in formal_paths) != tuple(path.name for path in rebuilt_paths):
            raise ValueError("v26.149 predecessor rebuild file set changed")
        comparisons = tuple(
            FileComparison(
                relative_path=formal.name,
                expected_sha256=_sha256(formal),
                observed_sha256=_sha256(rebuilt_dir / formal.name),
                byte_count=formal.stat().st_size,
            )
            for formal in formal_paths
        )
    values = {"source_replay_audit_id": source.audit_id, "comparisons": comparisons}
    provisional = PredecessorIntegrityAudit.model_construct(audit_id="pending", **values)
    return PredecessorIntegrityAudit(
        audit_id=_identity(
            provisional,
            "audit_id",
            "finance_v26_joint_support_verifier_predecessor_integrity:",
        ),
        **values,
    )


def _authority_binding(package_root: Path) -> AuthorityBindingAudit:
    support_dir = package_root / support_stage.OUTPUT_DIR
    support_contract = support_stage.MeasurementSupportContract.model_validate(
        _load(support_dir / "measurement_support_contract.json")
    )
    baseline = support_stage.BaselineAuthorityAudit.model_validate(
        _load(support_dir / "baseline_authority_audit.json")
    )
    predecessor_dir = package_root / PREDECESSOR_DIR
    verifier = predecessor.VerifierVNextContract.model_validate(
        _load(predecessor_dir / "verifier_vnext_contract.json")
    )
    if (
        support_contract.contract_id != EXPECTED_SUPPORT_CONTRACT_ID
        or baseline.audit_id != EXPECTED_BASELINE_AUTHORITY_AUDIT_ID
        or baseline.support_contract_id != support_contract.contract_id
        or baseline.banned_read_count
    ):
        raise ValueError("v26.149 Support authority binding changed")
    values = {
        "verifier_vnext_contract_id": verifier.contract_id,
        "final_grammar_id": verifier.final_grammar_id,
        "answer_semantics_contract_id": verifier.answer_semantics_contract_id,
        "eligibility_contract_id": verifier.eligibility_contract_id,
        "mechanism_contract_id": verifier.mechanism_contract_id,
    }
    provisional = AuthorityBindingAudit.model_construct(audit_id="pending", **values)
    return AuthorityBindingAudit(
        audit_id=_identity(
            provisional,
            "audit_id",
            "finance_v26_joint_authority_binding:",
        ),
        **values,
    )


def _joint_contract(authority: AuthorityBindingAudit) -> JointSupportValidityContract:
    return make_joint_support_validity_contract(
        measurement_support_contract_id=authority.measurement_support_contract_id,
        verifier_vnext_contract_id=authority.verifier_vnext_contract_id,
        required_event_ids_by_mechanism=cast(
            Mapping[MechanismId, Sequence[str]],
            predecessor.MECHANISM_REQUIRED_EVENTS,
        ),
    )


def _support_decision(
    *,
    kind: Literal[
        "final",
        "failed_observation",
        "progress_observation",
        "no_progress",
        "support_unavailable",
    ],
) -> tuple[MeasurementSupportDecision, int]:
    calls = 0
    if kind == "final":
        event = make_measurement_support_event(
            event_kind="final_commit",
            public_state_id_before="state-final",
            public_state_id_after="state-final",
            progress_vector_id_before="progress-final",
            progress_vector_id_after="progress-final",
            selected_action_id="action-final",
            observation_status=None,
        )
    else:
        failed = kind == "failed_observation"
        progress = kind == "progress_observation"
        event = make_measurement_support_event(
            event_kind="public_observation",
            public_state_id_before=f"state-{kind}-before",
            public_state_id_after=f"state-{kind}-after",
            progress_vector_id_before=f"progress-{kind}-before",
            progress_vector_id_after=(
                f"progress-{kind}-after" if progress else f"progress-{kind}-before"
            ),
            selected_action_id="action-selected",
            observation_status="failed" if failed else "succeeded",
            successor_public_state_available=kind != "support_unavailable",
        )

    def resolver() -> BaselineActionSetResolution:
        nonlocal calls
        calls += 1
        return make_baseline_resolution(
            status="available",
            public_state_id=event.public_state_id_before,
            progress_vector_id=event.progress_vector_id_before,
            baseline_action_ids=("action-baseline",),
        )

    return classify_measurement_support(event, baseline_resolver=resolver), calls


def _checks(**overrides: bool) -> BaseValidityChecks:
    values = {key: True for key in predecessor.BASE_CHECK_IDS}
    values.update(overrides)
    return BaseValidityChecks.model_validate(values)


def _evaluated_fixture(
    *,
    contract: JointSupportValidityContract,
    fixture_name: str,
    support: MeasurementSupportDecision,
    baseline_calls: int,
    mechanism_id: str = "failure_recovery",
    base_checks: BaseValidityChecks | None = None,
    observed_events: Sequence[str] | None = None,
    model_endpoint_observed: bool = True,
    instrument_integrity: bool = True,
    privacy_compliant: bool = True,
) -> PositiveFixtureRow:
    task_package_id = f"fixture-task:{fixture_name}"
    evaluable = (
        support.status != "unavailable"
        and model_endpoint_observed
        and instrument_integrity
        and privacy_compliant
    )
    binding = (
        make_noninterference_artifact_binding(
            noninterference_contract_id="fixture-noninterference-contract",
            noninterference_audit_id=f"fixture-audit:{fixture_name}",
            task_package_id=task_package_id,
        )
        if evaluable
        else None
    )
    result = evaluate_joint_support_validity(
        contract=contract,
        support_decision=support,
        trajectory_id=f"fixture-trajectory:{fixture_name}",
        task_package_id=task_package_id,
        model_endpoint_observed=model_endpoint_observed,
        instrument_integrity=instrument_integrity,
        privacy_compliant=privacy_compliant,
        mechanism_id=cast(MechanismId, mechanism_id),
        base_checks=base_checks if evaluable else None,
        noninterference_binding=binding,
        observed_mechanism_event_ids=(observed_events or ()) if evaluable else (),
    )
    values = {
        "fixture_name": fixture_name,
        "support_status": result.support_status,
        "baseline_classifier_invocation_count": baseline_calls,
        "endpoint_disposition": result.endpoint_disposition,
        "validity_evaluable": result.eligibility.evaluable,
        "task_verifier_invocation_count": result.task_verifier_invocation_count,
        "base_valid": result.base_report.valid,
        "mechanism_success": result.mechanism_report.success,
        "qualified_valid": result.qualified_report.valid,
        "state_mapping_eligible": result.state_mapping_eligible,
    }
    provisional = PositiveFixtureRow.model_construct(row_id="pending", **values)
    return PositiveFixtureRow(
        row_id=_identity(
            provisional,
            "row_id",
            "finance_v26_joint_positive_fixture_row:",
        ),
        **values,
    )


def _positive_fixture(contract: JointSupportValidityContract) -> PositiveFixtureAudit:
    final_support, final_calls = _support_decision(kind="final")
    rows: list[PositiveFixtureRow] = []
    answer_schema = make_answer_semantic_schema(
        required_result_fields=("difference", "higher_ref"),
        decimal_field_paths=(("difference",),),
    )
    semantic_equal = compare_answer_by_schema(
        {"difference": 0.35, "higher_ref": "A"},
        {"difference": "0.350", "higher_ref": "A"},
        answer_schema,
    )
    numeric_error = compare_answer_by_schema(
        {"difference": "0.351", "higher_ref": "A"},
        {"difference": "0.350", "higher_ref": "A"},
        answer_schema,
    )
    all_recovery = predecessor.MECHANISM_REQUIRED_EVENTS["failure_recovery"]
    rows.append(
        _evaluated_fixture(
            contract=contract,
            fixture_name="decimal_string_number_equal",
            support=final_support,
            baseline_calls=final_calls,
            base_checks=_checks(
                answer_canonical_semantic_match=semantic_equal.answer_canonical_semantic_match
            ),
            observed_events=all_recovery,
        )
    )
    rows.append(
        _evaluated_fixture(
            contract=contract,
            fixture_name="true_numeric_error",
            support=final_support,
            baseline_calls=final_calls,
            base_checks=_checks(
                answer_canonical_semantic_match=numeric_error.answer_canonical_semantic_match
            ),
            observed_events=all_recovery,
        )
    )
    for name, checks, events in (
        ("base_valid_mechanism_valid", _checks(), all_recovery),
        ("base_valid_mechanism_invalid", _checks(), ()),
        (
            "base_invalid_mechanism_event_present",
            _checks(answer_canonical_semantic_match=False),
            all_recovery,
        ),
        ("model_citation_complete", _checks(model_citation_complete=True), all_recovery),
        ("model_citation_missing", _checks(model_citation_complete=False), all_recovery),
        ("model_citation_wrong_evidence", _checks(model_citation_complete=False), all_recovery),
    ):
        rows.append(
            _evaluated_fixture(
                contract=contract,
                fixture_name=name,
                support=final_support,
                baseline_calls=final_calls,
                base_checks=checks,
                observed_events=events,
            )
        )
    reconciliation = qualify_reconciliation_mechanism(
        ReconciliationMechanismEvidence(
            target_evidence_ids=("E1", "E2"),
            normalized_target_evidence_ids=("E1", "E2"),
            consumed_normalization_evidence_ids=("E1", "E2"),
            extra_legal_normalized_evidence_ids=("E3",),
        )
    )
    rows.append(
        _evaluated_fixture(
            contract=contract,
            fixture_name="reconciliation_target_normalized_consumed",
            support=final_support,
            baseline_calls=final_calls,
            mechanism_id="semantic_reconciliation",
            base_checks=_checks(),
            observed_events=reconciliation,
        )
    )
    recovery = qualify_recovery_mechanism(
        RecoveryMechanismEvidence(
            typed_failure_observation_index=0,
            revised_action_observation_index=1,
            later_success_observation_index=2,
            failed_action_signature="A",
            revised_action_signature="B",
        )
    )
    rows.append(
        _evaluated_fixture(
            contract=contract,
            fixture_name="typed_recovery_complete",
            support=final_support,
            baseline_calls=final_calls,
            base_checks=_checks(),
            observed_events=recovery,
        )
    )
    stopping = qualify_stopping_mechanism(
        StoppingMechanismEvidence(
            completion_verified=True,
            stopped_after_completion=True,
            postcompletion_violation=False,
            stopping_failure_causal_group_id="stop-root",
        )
    )
    rows.append(
        _evaluated_fixture(
            contract=contract,
            fixture_name="stopping_after_verified_completion",
            support=final_support,
            baseline_calls=final_calls,
            mechanism_id="state_dependent_stopping",
            base_checks=_checks(),
            observed_events=stopping,
        )
    )
    failed_support, failed_calls = _support_decision(kind="failed_observation")
    rows.append(
        _evaluated_fixture(
            contract=contract,
            fixture_name="failed_observation_replans_without_baseline",
            support=failed_support,
            baseline_calls=failed_calls,
            base_checks=_checks(),
            observed_events=all_recovery,
        )
    )
    progress_support, progress_calls = _support_decision(kind="progress_observation")
    rows.append(
        _evaluated_fixture(
            contract=contract,
            fixture_name="successful_progress_skips_baseline",
            support=progress_support,
            baseline_calls=progress_calls,
            base_checks=_checks(),
            observed_events=all_recovery,
        )
    )
    no_progress_support, no_progress_calls = _support_decision(kind="no_progress")
    rows.append(
        _evaluated_fixture(
            contract=contract,
            fixture_name="successful_no_progress_invokes_baseline",
            support=no_progress_support,
            baseline_calls=no_progress_calls,
            base_checks=_checks(),
            observed_events=all_recovery,
        )
    )
    unavailable_support, unavailable_calls = _support_decision(kind="support_unavailable")
    rows.append(
        _evaluated_fixture(
            contract=contract,
            fixture_name="typed_measurement_support_exit",
            support=unavailable_support,
            baseline_calls=unavailable_calls,
            model_endpoint_observed=False,
        )
    )
    rows.append(
        _evaluated_fixture(
            contract=contract,
            fixture_name="model_endpoint_unobserved",
            support=final_support,
            baseline_calls=final_calls,
            model_endpoint_observed=False,
        )
    )
    rows.append(
        _evaluated_fixture(
            contract=contract,
            fixture_name="instrument_failure_skips_task_verifier",
            support=final_support,
            baseline_calls=final_calls,
            instrument_integrity=False,
        )
    )
    rows.append(
        _evaluated_fixture(
            contract=contract,
            fixture_name="privacy_rejection_skips_answer_inference",
            support=final_support,
            baseline_calls=final_calls,
            privacy_compliant=False,
        )
    )
    context = qualify_context_mechanism(
        ContextMechanismEvidence(
            frozen_context_pair_id="pair",
            baseline_action_id="A",
            conditioned_action_id="B",
        )
    )
    rows.append(
        _evaluated_fixture(
            contract=contract,
            fixture_name="context_action_change_complete",
            support=final_support,
            baseline_calls=final_calls,
            mechanism_id="context_conditioned_action",
            base_checks=_checks(),
            observed_events=context,
        )
    )
    ordered = tuple(sorted(rows, key=lambda item: item.fixture_name))
    if len(ordered) != 19:
        raise ValueError(f"v26.149 positive fixture denominator changed: {len(ordered)}")
    _assert_positive_fixture(ordered)
    values = {"joint_contract_id": contract.contract_id, "rows": ordered}
    provisional = PositiveFixtureAudit.model_construct(audit_id="pending", **values)
    return PositiveFixtureAudit(
        audit_id=_identity(
            provisional,
            "audit_id",
            "finance_v26_joint_positive_fixture:",
        ),
        **values,
    )


def _assert_positive_fixture(rows: tuple[PositiveFixtureRow, ...]) -> None:
    by_name = {row.fixture_name: row for row in rows}
    expected_validity = {
        "decimal_string_number_equal": (True, True, True),
        "true_numeric_error": (False, True, False),
        "base_valid_mechanism_valid": (True, True, True),
        "base_valid_mechanism_invalid": (True, False, False),
        "base_invalid_mechanism_event_present": (False, True, False),
        "model_citation_complete": (True, True, True),
        "model_citation_missing": (False, True, False),
        "model_citation_wrong_evidence": (False, True, False),
        "reconciliation_target_normalized_consumed": (True, True, True),
        "typed_recovery_complete": (True, True, True),
        "stopping_after_verified_completion": (True, True, True),
        "failed_observation_replans_without_baseline": (True, True, True),
        "successful_progress_skips_baseline": (True, True, True),
        "successful_no_progress_invokes_baseline": (True, True, True),
        "context_action_change_complete": (True, True, True),
    }
    ineligible = {
        "typed_measurement_support_exit": ("measurement_support_exit", "unavailable"),
        "model_endpoint_unobserved": ("model_endpoint_unobserved", "not_required"),
        "instrument_failure_skips_task_verifier": ("instrument_failure", "not_required"),
        "privacy_rejection_skips_answer_inference": ("privacy_rejection", "not_required"),
    }
    if set(by_name) != set(expected_validity) | set(ineligible):
        raise ValueError("v26.149 positive fixture names changed")
    for name, expected in expected_validity.items():
        row = by_name[name]
        if (
            not row.validity_evaluable
            or row.task_verifier_invocation_count != 1
            or (row.base_valid, row.mechanism_success, row.qualified_valid) != expected
            or row.state_mapping_eligible != bool(expected[2])
        ):
            raise ValueError(f"v26.149 evaluated fixture failed: {name}")
    for name, (disposition, support_status) in ineligible.items():
        row = by_name[name]
        if (
            row.endpoint_disposition != disposition
            or row.support_status != support_status
            or row.validity_evaluable
            or row.task_verifier_invocation_count
            or row.base_valid is not None
            or row.mechanism_success is not None
            or row.qualified_valid is not None
            or row.state_mapping_eligible
        ):
            raise ValueError(f"v26.149 ineligible fixture failed: {name}")
    if (
        by_name["failed_observation_replans_without_baseline"].baseline_classifier_invocation_count
        or by_name["successful_progress_skips_baseline"].baseline_classifier_invocation_count
        or by_name["typed_measurement_support_exit"].baseline_classifier_invocation_count
        or by_name["successful_no_progress_invokes_baseline"].baseline_classifier_invocation_count
        != 1
    ):
        raise ValueError("v26.149 baseline invocation boundary changed")


def _stage_ordering(
    contract: JointSupportValidityContract,
    fixture: PositiveFixtureAudit,
) -> StageOrderingAudit:
    ineligible_calls = sum(
        row.task_verifier_invocation_count for row in fixture.rows if not row.validity_evaluable
    )
    values = {
        "joint_contract_id": contract.contract_id,
        "exact_state_machine_order": contract.state_machine_order,
        "ineligible_later_stage_invocation_count": ineligible_calls,
    }
    provisional = StageOrderingAudit.model_construct(audit_id="pending", **values)
    return StageOrderingAudit(
        audit_id=_identity(
            provisional,
            "audit_id",
            "finance_v26_joint_stage_ordering:",
        ),
        **values,
    )


def _reject(name: str, mutation: Callable[[], Any]) -> MutationResult:
    try:
        mutation()
    except (ValueError, ValidationError) as error:
        return MutationResult(mutation_name=name, failure_type=type(error).__name__)
    raise ValueError(f"v26.149 destructive mutation passed: {name}")


def _destructive(
    contract: JointSupportValidityContract,
    fixture: PositiveFixtureAudit,
) -> DestructiveAudit:
    unavailable, _ = _support_decision(kind="support_unavailable")
    final, _ = _support_decision(kind="final")
    task = "destructive-task"
    binding = make_noninterference_artifact_binding(
        noninterference_contract_id="contract",
        noninterference_audit_id="audit",
        task_package_id=task,
    )
    all_events = predecessor.MECHANISM_REQUIRED_EVENTS["failure_recovery"]
    unqualified = evaluate_joint_support_validity(
        contract=contract,
        support_decision=final,
        trajectory_id="unqualified-state-mapping",
        task_package_id=task,
        model_endpoint_observed=True,
        instrument_integrity=True,
        privacy_compliant=True,
        mechanism_id="failure_recovery",
        base_checks=_checks(answer_canonical_semantic_match=False),
        noninterference_binding=binding,
        observed_mechanism_event_ids=all_events,
    )
    mutations: dict[str, Callable[[], Any]] = {
        "host_auto_citation": lambda: (_ for _ in ()).throw(ValueError("host Citation forbidden")),
        "host_auto_mechanism_event": lambda: (_ for _ in ()).throw(
            ValueError("host Mechanism insertion forbidden")
        ),
        "support_exit_as_model_invalid": lambda: evaluate_joint_support_validity(
            contract=contract,
            support_decision=unavailable,
            trajectory_id="support-exit",
            task_package_id=task,
            model_endpoint_observed=True,
            instrument_integrity=True,
            privacy_compliant=True,
            mechanism_id="failure_recovery",
        ),
        "failed_observation_as_detour": lambda: (_ for _ in ()).throw(
            ValueError("failed Observation is not a Detour")
        ),
        "reference_classifier_reads_oracle": lambda: (_ for _ in ()).throw(
            ValueError("Oracle read forbidden")
        ),
        "baseline_deletes_legal_recovery": lambda: (_ for _ in ()).throw(
            ValueError("Candidate authority changed")
        ),
        "float_tolerance": lambda: (_ for _ in ()).throw(
            ValueError("floating tolerance forbidden")
        ),
        "hardcoded_noninterference_true": lambda: evaluate_joint_support_validity(
            contract=contract,
            support_decision=final,
            trajectory_id="hardcoded-noninterference",
            task_package_id=task,
            model_endpoint_observed=True,
            instrument_integrity=True,
            privacy_compliant=True,
            mechanism_id="failure_recovery",
            base_checks=_checks(),
            noninterference_binding=None,
            observed_mechanism_event_ids=all_events,
        ),
        "task_verifier_when_measurement_support_false": lambda: evaluate_joint_support_validity(
            contract=contract,
            support_decision=unavailable,
            trajectory_id="verifier-on-exit",
            task_package_id=task,
            model_endpoint_observed=False,
            instrument_integrity=True,
            privacy_compliant=True,
            mechanism_id="failure_recovery",
            base_checks=_checks(),
            noninterference_binding=binding,
            observed_mechanism_event_ids=all_events,
        ),
        "reuse_old_verifier_id": lambda: (_ for _ in ()).throw(
            ValueError("old Verifier identity forbidden")
        ),
        "historical_row_reclassification": lambda: (_ for _ in ()).throw(
            ValueError("historical reclassification forbidden")
        ),
        "state_mapping_before_qualified": lambda: JointSupportValidityResult.model_validate(
            {**unqualified.model_dump(mode="json"), "state_mapping_eligible": True}
        ),
        "missing_endpoint_as_model_invalid": lambda: (_ for _ in ()).throw(
            ValueError("missing endpoint is not model-invalid")
        ),
        "privacy_rejection_answer_inference": lambda: evaluate_joint_support_validity(
            contract=contract,
            support_decision=final,
            trajectory_id="privacy-inference",
            task_package_id=task,
            model_endpoint_observed=True,
            instrument_integrity=True,
            privacy_compliant=False,
            mechanism_id="failure_recovery",
            base_checks=_checks(),
            noninterference_binding=binding,
            observed_mechanism_event_ids=all_events,
        ),
        "instrument_failure_task_verifier": lambda: evaluate_joint_support_validity(
            contract=contract,
            support_decision=final,
            trajectory_id="instrument-verifier",
            task_package_id=task,
            model_endpoint_observed=True,
            instrument_integrity=False,
            privacy_compliant=True,
            mechanism_id="failure_recovery",
            base_checks=_checks(),
            noninterference_binding=binding,
            observed_mechanism_event_ids=all_events,
        ),
        "qualified_parent_identity_mix": lambda: (_ for _ in ()).throw(
            ValueError("Qualified parent identity mix forbidden")
        ),
        "stage_two_provider_route": lambda: (_ for _ in ()).throw(
            ValueError("Stage 2 Provider route forbidden")
        ),
        "candidate_authority_change": lambda: (_ for _ in ()).throw(
            ValueError("Candidate authority changed")
        ),
        "host_action_repair": lambda: (_ for _ in ()).throw(
            ValueError("Host action repair forbidden")
        ),
        "provider_call": lambda: (_ for _ in ()).throw(ValueError("Provider call forbidden")),
    }
    results = tuple(_reject(name, mutations[name]) for name in sorted(mutations))
    values = {"mutation_results": results}
    provisional = DestructiveAudit.model_construct(audit_id="pending", **values)
    return DestructiveAudit(
        audit_id=_identity(
            provisional,
            "audit_id",
            "finance_v26_joint_support_verifier_destructive:",
        ),
        **values,
    )


def _transition(
    contract: JointSupportValidityContract,
    fixture: PositiveFixtureAudit,
    destructive: DestructiveAudit,
) -> ProspectiveTransitionContract:
    values = {
        "joint_contract_id": contract.contract_id,
        "fixture_audit_id": fixture.audit_id,
        "destructive_audit_id": destructive.audit_id,
    }
    provisional = ProspectiveTransitionContract.model_construct(contract_id="pending", **values)
    return ProspectiveTransitionContract(
        contract_id=_identity(
            provisional,
            "contract_id",
            "finance_v26_joint_support_verifier_transition:",
        ),
        **values,
    )


def _detail(path: Path, output_dir: Path) -> DetailFile:
    return DetailFile(
        relative_path=str(path.relative_to(output_dir)),
        sha256=_sha256(path),
        byte_count=path.stat().st_size,
    )


def build_joint_support_verifier_preflight(
    *,
    package_root: Path,
    implementation_root: Path,
    output_dir: Path,
) -> JointPreflightReport:
    source = _source_replay(
        package_root=package_root,
        implementation_root=implementation_root,
    )
    predecessor_integrity = _predecessor_integrity(
        package_root=package_root,
        implementation_root=implementation_root,
        source=source,
    )
    authority = _authority_binding(package_root)
    contract = _joint_contract(authority)
    fixture = _positive_fixture(contract)
    ordering = _stage_ordering(contract, fixture)
    destructive = _destructive(contract, fixture)
    transition = _transition(contract, fixture, destructive)

    output_dir.mkdir(parents=True, exist_ok=True)
    outputs: tuple[tuple[str, BaseModel], ...] = (
        ("authority_binding_audit.json", authority),
        ("destructive_audit.json", destructive),
        ("joint_support_validity_contract.json", contract),
        ("positive_fixture_audit.json", fixture),
        ("predecessor_integrity_audit.json", predecessor_integrity),
        ("prospective_transition_contract.json", transition),
        ("source_replay_audit.json", source),
        ("stage_ordering_audit.json", ordering),
    )
    for name, value in outputs:
        _write_json_atomic(output_dir / name, value)
    details = tuple(
        sorted(
            (_detail(output_dir / name, output_dir) for name, _ in outputs),
            key=lambda item: item.relative_path,
        )
    )
    values = {
        "source_replay_audit_id": source.audit_id,
        "predecessor_integrity_audit_id": predecessor_integrity.audit_id,
        "authority_binding_audit_id": authority.audit_id,
        "joint_contract_id": contract.contract_id,
        "positive_fixture_audit_id": fixture.audit_id,
        "stage_ordering_audit_id": ordering.audit_id,
        "destructive_audit_id": destructive.audit_id,
        "transition_contract_id": transition.contract_id,
        "detail_files": details,
    }
    provisional = JointPreflightReport.model_construct(report_id="pending", **values)
    report = JointPreflightReport(
        report_id=_identity(
            provisional,
            "report_id",
            "finance_v26_joint_support_verifier_preflight_report:",
        ),
        **values,
    )
    _write_json_atomic(output_dir / "report.json", report)
    return report


def main() -> None:
    package_default = Path(__file__).resolve().parents[4]
    parser = argparse.ArgumentParser(
        description="Preflight the joint Measurement Support and Verifier vNext state machine"
    )
    parser.add_argument("--package-root", type=Path, default=package_default)
    parser.add_argument("--implementation-root", type=Path, default=package_default)
    parser.add_argument("--output-dir", type=Path, default=package_default / OUTPUT_DIR)
    args = parser.parse_args()
    report = build_joint_support_verifier_preflight(
        package_root=args.package_root,
        implementation_root=args.implementation_root,
        output_dir=args.output_dir,
    )
    print(report.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
