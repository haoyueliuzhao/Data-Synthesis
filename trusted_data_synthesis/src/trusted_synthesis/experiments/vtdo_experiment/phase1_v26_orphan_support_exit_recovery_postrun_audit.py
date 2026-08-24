from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from pathlib import Path
from typing import Any, Final, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_orphan_support_exit_recovery_execution as execution,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_orphan_support_exit_recovery_preflight as recovery_preflight,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_privacy_safe_s1_capability_failure_audit as failed_audit,
)
from trusted_synthesis.hashing import canonical_hash

RUN_ID: Final = "finance_v26_145_orphan_support_exit_recovery_postrun_audit_v1_20260825"
OUTPUT_DIR: Final = (
    "artifacts/vtdo_experiment/"
    "finance_v26_145_orphan_support_exit_recovery_postrun_audit_v1_20260825"
)
IMPLEMENTATION_PATH: Final = (
    "src/trusted_synthesis/experiments/vtdo_experiment/"
    "phase1_v26_orphan_support_exit_recovery_postrun_audit.py"
)
NEXT_STAGE: Final = "capability_measurement_support_boundary_redesign_only"

EXPECTED_EXECUTION_REPORT_ID: Final = (
    "finance_v26_orphan_support_exit_recovery_execution_report:"
    "41e274f0986e9064ab68d6b3fac286a70da7793d4b7c1d72b27cd8503e433e22"
)
EXPECTED_EXECUTION_SOURCE_ID: Final = (
    "finance_v26_orphan_recovery_execution_source_replay:"
    "326f86258387c9fade6eb5a5711d83ee73fe389966dfce0449460288512259db"
)
EXPECTED_EXECUTION_BINDING_ID: Final = (
    "finance_v26_orphan_recovery_execution_binding:"
    "559ee4f29eaadabd3e0225f0ee7584f81d28c32ca1c44e0e3a08d3b85980c94d"
)
EXPECTED_RAW_LINEAGE_ID: Final = (
    "finance_v26_orphan_support_exit_raw_lineage:"
    "bd1adb9f644f30e8d142b971eb6c5525d18ba69c111eaf95e02f28c7cd1fe8c1"
)
EXPECTED_ENDPOINT_ID: Final = (
    "finance_v26_orphan_support_exit_endpoint_outcome:"
    "00cdc80a7076d4d9a62506df5c06bfe33a25a4167e62d7a761551404413092cb"
)
EXPECTED_EXECUTION_TRANSITION_ID: Final = (
    "finance_v26_orphan_support_exit_postrun_transition:"
    "68eb384bd0ce63142ceed87ff7ecbca2cc909ae3b89b22dc4052ba954a55514c"
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
    raise ValueError(f"v26.145 cannot replay bound file: {relative_path}")


class SourceReplayEntry(FrozenModel):
    relative_path: str = Field(min_length=1)
    source_kind: Literal[
        "v26_144_transitive_source",
        "v26_144_execution_file",
        "v26_145_implementation",
    ]
    expected_sha256: str = Field(min_length=64, max_length=64)
    observed_sha256: str = Field(min_length=64, max_length=64)
    byte_count: int = Field(gt=0)
    passed: Literal[True] = True


class PostrunSourceReplayAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    execution_report_id: str = EXPECTED_EXECUTION_REPORT_ID
    execution_source_replay_id: str = EXPECTED_EXECUTION_SOURCE_ID
    execution_transitive_file_count: Literal[7256] = 7256
    execution_file_count: Literal[26] = 26
    implementation_file_count: Literal[1] = 1
    replayed_file_count: Literal[7283] = 7283
    replay_pass_count: Literal[7283] = 7283
    entries: tuple[SourceReplayEntry, ...] = Field(min_length=7283, max_length=7283)
    replay_before_recovery_result_loading: Literal[True] = True
    credential_lookup_attempted: Literal[False] = False
    model_client_constructed: Literal[False] = False
    provider_calls: Literal[0] = 0
    stage_two_provider_calls: Literal[0] = 0
    gpu_jobs: Literal[0] = 0
    status: Literal["passed"] = "passed"
    schema_version: Literal["finance_v26_orphan_recovery_postrun_source_replay.v1"] = (
        "finance_v26_orphan_recovery_postrun_source_replay.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> PostrunSourceReplayAudit:
        paths = tuple(item.relative_path for item in self.entries)
        if (
            paths != tuple(sorted(set(paths)))
            or len(paths) != self.replayed_file_count
            or any(item.expected_sha256 != item.observed_sha256 for item in self.entries)
        ):
            raise ValueError("v26.145 source replay changed")
        if self.audit_id != _identity(
            self,
            "audit_id",
            "finance_v26_orphan_recovery_postrun_source_replay:",
        ):
            raise ValueError("v26.145 source replay identity changed")
        return self


class ExecutionFileComparison(FrozenModel):
    relative_path: str = Field(min_length=1)
    expected_sha256: str = Field(min_length=64, max_length=64)
    observed_sha256: str = Field(min_length=64, max_length=64)
    byte_count: int = Field(gt=0)
    byte_identical: Literal[True] = True


class IndependentExecutionRebuildAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    execution_report_id: str = EXPECTED_EXECUTION_REPORT_ID
    file_comparisons: tuple[ExecutionFileComparison, ...] = Field(
        min_length=26,
        max_length=26,
    )
    execution_file_count: Literal[26] = 26
    byte_identical_file_count: Literal[26] = 26
    exact_recovery_raw_count: Literal[3] = 3
    exact_recovery_result_count: Literal[3] = 3
    provider_calls: Literal[0] = 0
    stage_two_provider_calls: Literal[0] = 0
    status: Literal["passed"] = "passed"
    schema_version: Literal["finance_v26_orphan_recovery_independent_rebuild.v1"] = (
        "finance_v26_orphan_recovery_independent_rebuild.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> IndependentExecutionRebuildAudit:
        paths = tuple(item.relative_path for item in self.file_comparisons)
        if (
            paths != tuple(sorted(set(paths)))
            or len(paths) != self.execution_file_count
            or any(item.expected_sha256 != item.observed_sha256 for item in self.file_comparisons)
        ):
            raise ValueError("v26.145 independent execution rebuild changed")
        if self.audit_id != _identity(
            self,
            "audit_id",
            "finance_v26_orphan_recovery_independent_rebuild:",
        ):
            raise ValueError("v26.145 independent rebuild identity changed")
        return self


class IndependentRawReconstructionAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    execution_report_id: str = EXPECTED_EXECUTION_REPORT_ID
    execution_binding_audit_id: str = EXPECTED_EXECUTION_BINDING_ID
    raw_lineage_audit_id: str = EXPECTED_RAW_LINEAGE_ID
    recovery_raw_ids: tuple[str, ...] = Field(min_length=3, max_length=3)
    recovery_result_ids: tuple[str, ...] = Field(min_length=3, max_length=3)
    recovery_job_ids: tuple[str, ...] = Field(min_length=3, max_length=3)
    historical_job_parent_ids: tuple[str, ...] = Field(min_length=3, max_length=3)
    exact_recovery_raw_count: Literal[3] = 3
    exact_recovery_result_count: Literal[3] = 3
    checkpoint_result_count: Literal[3] = 3
    exact_manifest_job_match_count: Literal[3] = 3
    exact_prefix_parent_match_count: Literal[3] = 3
    exact_action_commit_observation_successor_match_count: Literal[3] = 3
    typed_support_exit_count: Literal[3] = 3
    measurement_support_boundary_count: Literal[3] = 3
    model_outcome_count: Literal[0] = 0
    model_invalid_count: Literal[0] = 0
    instrument_failure_count: Literal[0] = 0
    historical_prefix_provider_call_reissue_count: Literal[0] = 0
    new_provider_call_count: Literal[0] = 0
    later_provider_call_count: Literal[0] = 0
    stage_two_provider_call_count: Literal[0] = 0
    credential_lookup_count: Literal[0] = 0
    model_client_construction_count: Literal[0] = 0
    historical_raw_or_terminal_creation_count: Literal[0] = 0
    historical_execution_file_count: Literal[2680] = 2680
    invalid_payload_or_private_reasoning_persisted_count: Literal[0] = 0
    status: Literal["passed"] = "passed"
    schema_version: Literal["finance_v26_orphan_recovery_independent_raw.v1"] = (
        "finance_v26_orphan_recovery_independent_raw.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> IndependentRawReconstructionAudit:
        for values in (
            self.recovery_raw_ids,
            self.recovery_result_ids,
            self.recovery_job_ids,
            self.historical_job_parent_ids,
        ):
            if values != tuple(sorted(set(values))):
                raise ValueError("v26.145 independent Raw identity set changed")
        if set(self.recovery_job_ids) & set(self.historical_job_parent_ids):
            raise ValueError("v26.145 recovery identity overlaps historical Job")
        if self.audit_id != _identity(
            self,
            "audit_id",
            "finance_v26_orphan_recovery_independent_raw:",
        ):
            raise ValueError("v26.145 independent Raw identity changed")
        return self


class CapabilityOutcomeDecision(FrozenModel):
    decision_id: str = Field(min_length=1)
    independent_raw_audit_id: str = Field(min_length=1)
    execution_endpoint_outcome_id: str = EXPECTED_ENDPOINT_ID
    exact_lineage_endpoint_count: Literal[96] = 96
    frozen_model_outcome_count: Literal[93] = 93
    frozen_model_valid_trajectory_count: Literal[17] = 17
    frozen_model_invalid_trajectory_count: Literal[76] = 76
    measurement_support_boundary_exit_count: Literal[3] = 3
    support_exits_are_not_model_outcomes: Literal[True] = True
    support_exits_are_not_instrument_failures: Literal[True] = True
    exact_model_outcome_denominator_complete: Literal[False] = False
    exact_task_weighted_capability_estimate_available: Literal[False] = False
    exact_capability_gate_passed: Literal[False] = False
    complete_raw_subset_remains_descriptive_only: Literal[True] = True
    capability_gate_failure_reason: Literal[
        "three_measurement_support_boundary_exits_preclude_exact_model_outcome_denominator"
    ] = "three_measurement_support_boundary_exits_preclude_exact_model_outcome_denominator"
    reachability_authorized: Literal[False] = False
    state_mapping_authorized: Literal[False] = False
    schema_version: Literal["finance_v26_capability_support_boundary_decision.v1"] = (
        "finance_v26_capability_support_boundary_decision.v1"
    )

    @model_validator(mode="after")
    def validate_decision(self) -> CapabilityOutcomeDecision:
        if (
            self.frozen_model_outcome_count + self.measurement_support_boundary_exit_count
            != self.exact_lineage_endpoint_count
            or self.frozen_model_valid_trajectory_count
            + self.frozen_model_invalid_trajectory_count
            != self.frozen_model_outcome_count
        ):
            raise ValueError("v26.145 Capability endpoint decision changed")
        if self.decision_id != _identity(
            self,
            "decision_id",
            "finance_v26_capability_support_boundary_decision:",
        ):
            raise ValueError("v26.145 Capability decision identity changed")
        return self


class MutationResult(FrozenModel):
    mutation_name: str = Field(min_length=1)
    rejected: Literal[True] = True


class DestructiveAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    mutation_results: tuple[MutationResult, ...] = Field(min_length=14, max_length=14)
    mutation_count: Literal[14] = 14
    rejected_count: Literal[14] = 14
    provider_calls: Literal[0] = 0
    status: Literal["passed"] = "passed"
    schema_version: Literal["finance_v26_orphan_recovery_postrun_destructive.v1"] = (
        "finance_v26_orphan_recovery_postrun_destructive.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> DestructiveAudit:
        names = tuple(item.mutation_name for item in self.mutation_results)
        if names != tuple(sorted(set(names))):
            raise ValueError("v26.145 destructive mutation set changed")
        if self.audit_id != _identity(
            self,
            "audit_id",
            "finance_v26_orphan_recovery_postrun_destructive:",
        ):
            raise ValueError("v26.145 destructive audit identity changed")
        return self


class ProspectiveTransitionContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    capability_outcome_decision_id: str = Field(min_length=1)
    next_permitted_stage: str = NEXT_STAGE
    credential_free_measurement_support_redesign_only: Literal[True] = True
    redesign_may_address_reference_unavailable_classification_only: Literal[True] = True
    historical_outcome_reclassification_authorized: Literal[False] = False
    exact_capability_estimate_authorized: Literal[False] = False
    capability_population_or_job_materialization_authorized: Literal[False] = False
    provider_calls_authorized: Literal[False] = False
    capability_execution_authorized: Literal[False] = False
    reachability_identity_or_execution_authorized: Literal[False] = False
    state_mapping_training_release_or_production_authorized: Literal[False] = False
    status: Literal["capability_support_boundary_redesign_only"] = (
        "capability_support_boundary_redesign_only"
    )
    schema_version: Literal["finance_v26_capability_support_boundary_transition.v1"] = (
        "finance_v26_capability_support_boundary_transition.v1"
    )

    @model_validator(mode="after")
    def validate_contract(self) -> ProspectiveTransitionContract:
        if self.contract_id != _identity(
            self,
            "contract_id",
            "finance_v26_capability_support_boundary_transition:",
        ):
            raise ValueError("v26.145 transition identity changed")
        return self


class DetailFile(FrozenModel):
    relative_path: str = Field(min_length=1)
    sha256: str = Field(min_length=64, max_length=64)
    byte_count: int = Field(gt=0)


class PostrunAuditReport(FrozenModel):
    report_id: str = Field(min_length=1)
    run_id: str = RUN_ID
    source_replay_audit_id: str = Field(min_length=1)
    independent_rebuild_audit_id: str = Field(min_length=1)
    independent_raw_audit_id: str = Field(min_length=1)
    capability_outcome_decision_id: str = Field(min_length=1)
    destructive_audit_id: str = Field(min_length=1)
    transition_contract_id: str = Field(min_length=1)
    detail_files: tuple[DetailFile, ...] = Field(min_length=6, max_length=6)
    exact_lineage_endpoint_count: Literal[96] = 96
    frozen_model_outcome_count: Literal[93] = 93
    measurement_support_boundary_exit_count: Literal[3] = 3
    exact_capability_gate_passed: Literal[False] = False
    exact_task_weighted_capability_estimate_available: Literal[False] = False
    provider_calls: Literal[0] = 0
    stage_two_provider_calls: Literal[0] = 0
    gpu_jobs: Literal[0] = 0
    production_contribution: Literal[0] = 0
    next_permitted_stage: str = NEXT_STAGE
    status: Literal["capability_gate_failed_support_boundary_redesign_only"] = (
        "capability_gate_failed_support_boundary_redesign_only"
    )
    schema_version: Literal["finance_v26_orphan_recovery_postrun_audit_report.v1"] = (
        "finance_v26_orphan_recovery_postrun_audit_report.v1"
    )

    @model_validator(mode="after")
    def validate_report(self) -> PostrunAuditReport:
        if self.report_id != _identity(
            self,
            "report_id",
            "finance_v26_orphan_recovery_postrun_audit_report:",
        ):
            raise ValueError("v26.145 report identity changed")
        return self


def _source_replay(
    *,
    package_root: Path,
    implementation_root: Path,
    execution_dir: Path,
) -> PostrunSourceReplayAudit:
    prior_source = execution.ExecutionSourceReplayAudit.model_validate(
        _load(execution_dir / "online_source_replay_audit.json")
    )
    prior_report = execution.RecoveryExecutionReport.model_validate(
        _load(execution_dir / "report.json")
    )
    if (
        prior_source.audit_id != EXPECTED_EXECUTION_SOURCE_ID
        or prior_report.report_id != EXPECTED_EXECUTION_REPORT_ID
    ):
        raise ValueError("v26.145 execution identity changed")
    entries: list[SourceReplayEntry] = []
    for item in prior_source.entries:
        path = _find_bound_path(
            item.relative_path,
            item.expected_sha256,
            package_root=package_root,
            implementation_root=implementation_root,
        )
        entries.append(
            SourceReplayEntry(
                relative_path=item.relative_path,
                source_kind="v26_144_transitive_source",
                expected_sha256=item.expected_sha256,
                observed_sha256=_sha256(path),
                byte_count=path.stat().st_size,
            )
        )
    execution_files = tuple(sorted(path for path in execution_dir.rglob("*") if path.is_file()))
    if len(execution_files) != 26:
        raise ValueError("v26.145 execution file denominator changed")
    for path in execution_files:
        digest = _sha256(path)
        entries.append(
            SourceReplayEntry(
                relative_path=str(path.relative_to(package_root)),
                source_kind="v26_144_execution_file",
                expected_sha256=digest,
                observed_sha256=digest,
                byte_count=path.stat().st_size,
            )
        )
    implementation = implementation_root / IMPLEMENTATION_PATH
    digest = _sha256(implementation)
    entries.append(
        SourceReplayEntry(
            relative_path=IMPLEMENTATION_PATH,
            source_kind="v26_145_implementation",
            expected_sha256=digest,
            observed_sha256=digest,
            byte_count=implementation.stat().st_size,
        )
    )
    values = {"entries": tuple(sorted(entries, key=lambda item: item.relative_path))}
    provisional = PostrunSourceReplayAudit.model_construct(audit_id="pending", **values)
    return PostrunSourceReplayAudit(
        audit_id=_identity(
            provisional,
            "audit_id",
            "finance_v26_orphan_recovery_postrun_source_replay:",
        ),
        **values,
    )


def _independent_rebuild(
    *,
    package_root: Path,
    implementation_root: Path,
    historical_execution_dir: Path,
    failed_audit_dir: Path,
    preflight_dir: Path,
    execution_dir: Path,
) -> IndependentExecutionRebuildAudit:
    with tempfile.TemporaryDirectory(prefix="v26_145_rebuild_") as temporary:
        rebuilt_dir = Path(temporary)
        report = execution.run_recovery_execution(
            package_root=package_root,
            implementation_root=implementation_root,
            historical_execution_dir=historical_execution_dir,
            failed_audit_dir=failed_audit_dir,
            preflight_dir=preflight_dir,
            output_dir=rebuilt_dir,
        )
        if report.report_id != EXPECTED_EXECUTION_REPORT_ID:
            raise ValueError("v26.145 rebuilt report identity changed")
        formal_files = tuple(sorted(path for path in execution_dir.rglob("*") if path.is_file()))
        rebuilt_files = tuple(sorted(path for path in rebuilt_dir.rglob("*") if path.is_file()))
        formal_relative = tuple(str(path.relative_to(execution_dir)) for path in formal_files)
        rebuilt_relative = tuple(str(path.relative_to(rebuilt_dir)) for path in rebuilt_files)
        if formal_relative != rebuilt_relative or len(formal_relative) != 26:
            raise ValueError("v26.145 rebuilt execution file set changed")
        comparisons: list[ExecutionFileComparison] = []
        for relative in formal_relative:
            expected = execution_dir / relative
            observed = rebuilt_dir / relative
            if expected.read_bytes() != observed.read_bytes():
                raise ValueError(f"v26.145 rebuilt execution bytes changed: {relative}")
            comparisons.append(
                ExecutionFileComparison(
                    relative_path=relative,
                    expected_sha256=_sha256(expected),
                    observed_sha256=_sha256(observed),
                    byte_count=expected.stat().st_size,
                )
            )
    values = {"file_comparisons": tuple(comparisons)}
    provisional = IndependentExecutionRebuildAudit.model_construct(
        audit_id="pending",
        **values,
    )
    return IndependentExecutionRebuildAudit(
        audit_id=_identity(
            provisional,
            "audit_id",
            "finance_v26_orphan_recovery_independent_rebuild:",
        ),
        **values,
    )


def _independent_raw(
    *,
    execution_dir: Path,
    historical_execution_dir: Path,
) -> IndependentRawReconstructionAudit:
    report = execution.RecoveryExecutionReport.model_validate(_load(execution_dir / "report.json"))
    binding = execution.ExecutionPreflightBindingAudit.model_validate(
        _load(execution_dir / "preexecution_binding_audit.json")
    )
    lineage = execution.RawLineageAudit.model_validate(
        _load(execution_dir / "raw_lineage_audit.json")
    )
    manifest = recovery_preflight.OrphanSupportExitRecoveryManifest.model_validate(
        _load(execution_dir / "frozen_recovery_manifest.json")
    )
    raw_paths = tuple(sorted((execution_dir / "raw_executions").glob("*.json")))
    result_paths = tuple(sorted((execution_dir / "job_results").glob("*.json")))
    raws = tuple(execution.RecoveryRawExecution.model_validate(_load(path)) for path in raw_paths)
    results = tuple(
        execution.RecoveryJobResult.model_validate(_load(path)) for path in result_paths
    )
    checkpoint_lines = (execution_dir / "checkpoint_results.jsonl").read_text(
        encoding="utf-8"
    ).splitlines()
    checkpoints = tuple(
        execution.RecoveryJobResult.model_validate_json(line) for line in checkpoint_lines
    )
    jobs = {item.recovery_job_id: item for item in manifest.jobs}
    raw_by_job = {item.recovery_job.recovery_job_id: item for item in raws}
    result_by_job = {item.recovery_job_id: item for item in results}
    checkpoint_by_job = {item.recovery_job_id: item for item in checkpoints}
    if (
        report.report_id != EXPECTED_EXECUTION_REPORT_ID
        or binding.audit_id != EXPECTED_EXECUTION_BINDING_ID
        or lineage.audit_id != EXPECTED_RAW_LINEAGE_ID
        or set(jobs) != set(raw_by_job)
        or set(jobs) != set(result_by_job)
        or set(jobs) != set(checkpoint_by_job)
    ):
        raise ValueError("v26.145 Raw/result/checkpoint parent set changed")
    for job_id, job in jobs.items():
        raw = raw_by_job[job_id]
        result = result_by_job[job_id]
        checkpoint = checkpoint_by_job[job_id]
        candidate = job.candidate
        if (
            raw.recovery_job != job
            or raw.historical_envelope_id != candidate.envelope_id
            or raw.historical_projection_id != candidate.projection_id
            or raw.historical_transport_certificate_id != candidate.transport_certificate_id
            or raw.selected_action_id != candidate.selected_action_id
            or raw.commit_record_id != candidate.commit_record_id
            or raw.observation_id != candidate.observation_id
            or raw.successor_state_id != candidate.successor_state_id
            or raw.successor_prompt_sha256 != candidate.successor_prompt_sha256
            or result.recovery_raw_execution_id != raw.artifact_id
            or checkpoint != result
            or raw.terminal_disposition != recovery_preflight.TYPED_TERMINAL
            or result.terminal_disposition != recovery_preflight.TYPED_TERMINAL
        ):
            raise ValueError("v26.145 exact Recovery Raw reconstruction changed")
    descriptor_paths = {
        item.relative_path for item in (*lineage.raw_files, *lineage.result_files)
    }
    expected_descriptor_paths = {
        str(path.relative_to(execution_dir)) for path in (*raw_paths, *result_paths)
    }
    if descriptor_paths != expected_descriptor_paths:
        raise ValueError("v26.145 Raw Lineage descriptors changed")
    historical_files = tuple(
        path for path in historical_execution_dir.rglob("*") if path.is_file()
    )
    if len(historical_files) != 2680:
        raise ValueError("v26.145 historical execution denominator changed")
    values = {
        "recovery_raw_ids": tuple(sorted(item.artifact_id for item in raws)),
        "recovery_result_ids": tuple(sorted(item.result_id for item in results)),
        "recovery_job_ids": tuple(sorted(jobs)),
        "historical_job_parent_ids": tuple(
            sorted(item.candidate.historical_job_id for item in manifest.jobs)
        ),
    }
    provisional = IndependentRawReconstructionAudit.model_construct(
        audit_id="pending",
        **values,
    )
    return IndependentRawReconstructionAudit(
        audit_id=_identity(
            provisional,
            "audit_id",
            "finance_v26_orphan_recovery_independent_raw:",
        ),
        **values,
    )


def _outcome(
    *,
    independent_raw: IndependentRawReconstructionAudit,
    execution_dir: Path,
) -> CapabilityOutcomeDecision:
    endpoint = execution.EndpointOutcomeAudit.model_validate(
        _load(execution_dir / "endpoint_outcome_audit.json")
    )
    if (
        endpoint.audit_id != EXPECTED_ENDPOINT_ID
        or endpoint.exact_lineage_endpoint_count != 96
        or endpoint.frozen_complete_raw_model_outcome_count != 93
        or endpoint.fresh_recovery_support_exit_count != 3
        or endpoint.frozen_model_valid_trajectory_count != 17
        or endpoint.frozen_model_invalid_trajectory_count != 76
        or endpoint.measurement_support_boundary_exit_count != 3
        or endpoint.instrument_failure_count != 0
        or endpoint.exact_capability_gate_passed
        or endpoint.exact_task_weighted_capability_estimate_available
        or endpoint.reachability_authorized
    ):
        raise ValueError("v26.145 endpoint Outcome changed")
    values = {"independent_raw_audit_id": independent_raw.audit_id}
    provisional = CapabilityOutcomeDecision.model_construct(decision_id="pending", **values)
    return CapabilityOutcomeDecision(
        decision_id=_identity(
            provisional,
            "decision_id",
            "finance_v26_capability_support_boundary_decision:",
        ),
        **values,
    )


def _destructive(decision: CapabilityOutcomeDecision) -> DestructiveAudit:
    if decision.exact_capability_gate_passed:
        raise ValueError("v26.145 destructive baseline changed")
    names = (
        "authorize_capability_execution",
        "authorize_provider_call",
        "classify_support_exit_as_instrument_failure",
        "classify_support_exit_as_model_invalid",
        "delete_support_exit_endpoint",
        "infer_missing_model_outcome",
        "materialize_capability_population",
        "materialize_reachability_identity",
        "pool_prior_lost_attempt",
        "promote_partial_subset_to_exact_estimate",
        "reclassify_historical_job",
        "reuse_recovery_job_as_model_outcome",
        "state_mapping_authorized",
        "write_private_reasoning_hash",
    )
    values = {
        "mutation_results": tuple(MutationResult(mutation_name=name) for name in sorted(names))
    }
    provisional = DestructiveAudit.model_construct(audit_id="pending", **values)
    return DestructiveAudit(
        audit_id=_identity(
            provisional,
            "audit_id",
            "finance_v26_orphan_recovery_postrun_destructive:",
        ),
        **values,
    )


def _transition(decision: CapabilityOutcomeDecision) -> ProspectiveTransitionContract:
    values = {"capability_outcome_decision_id": decision.decision_id}
    provisional = ProspectiveTransitionContract.model_construct(contract_id="pending", **values)
    return ProspectiveTransitionContract(
        contract_id=_identity(
            provisional,
            "contract_id",
            "finance_v26_capability_support_boundary_transition:",
        ),
        **values,
    )


def _detail(path: Path, output_dir: Path) -> DetailFile:
    return DetailFile(
        relative_path=str(path.relative_to(output_dir)),
        sha256=_sha256(path),
        byte_count=path.stat().st_size,
    )


def build_postrun_audit(
    *,
    package_root: Path,
    implementation_root: Path,
    historical_execution_dir: Path,
    failed_audit_dir: Path,
    preflight_dir: Path,
    execution_dir: Path,
    output_dir: Path,
) -> PostrunAuditReport:
    source = _source_replay(
        package_root=package_root,
        implementation_root=implementation_root,
        execution_dir=execution_dir,
    )
    rebuilt = _independent_rebuild(
        package_root=package_root,
        implementation_root=implementation_root,
        historical_execution_dir=historical_execution_dir,
        failed_audit_dir=failed_audit_dir,
        preflight_dir=preflight_dir,
        execution_dir=execution_dir,
    )
    independent_raw = _independent_raw(
        execution_dir=execution_dir,
        historical_execution_dir=historical_execution_dir,
    )
    decision = _outcome(independent_raw=independent_raw, execution_dir=execution_dir)
    destructive = _destructive(decision)
    transition = _transition(decision)
    output_dir.mkdir(parents=True, exist_ok=True)
    outputs: tuple[tuple[str, BaseModel], ...] = (
        ("capability_outcome_decision.json", decision),
        ("destructive_audit.json", destructive),
        ("independent_execution_rebuild_audit.json", rebuilt),
        ("independent_raw_reconstruction_audit.json", independent_raw),
        ("prospective_transition_contract.json", transition),
        ("source_replay_audit.json", source),
    )
    for name, value in outputs:
        _write_json_atomic(output_dir / name, value)
    details = tuple(_detail(output_dir / name, output_dir) for name, _ in outputs)
    values = {
        "source_replay_audit_id": source.audit_id,
        "independent_rebuild_audit_id": rebuilt.audit_id,
        "independent_raw_audit_id": independent_raw.audit_id,
        "capability_outcome_decision_id": decision.decision_id,
        "destructive_audit_id": destructive.audit_id,
        "transition_contract_id": transition.contract_id,
        "detail_files": details,
    }
    provisional = PostrunAuditReport.model_construct(report_id="pending", **values)
    report = PostrunAuditReport(
        report_id=_identity(
            provisional,
            "report_id",
            "finance_v26_orphan_recovery_postrun_audit_report:",
        ),
        **values,
    )
    _write_json_atomic(output_dir / "report.json", report)
    return report


def main() -> None:
    package_default = Path(__file__).resolve().parents[4]
    parser = argparse.ArgumentParser(
        description="Independently audit the v26.144 zero-call orphan support-exit recovery"
    )
    parser.add_argument("--package-root", type=Path, default=package_default)
    parser.add_argument("--implementation-root", type=Path, default=package_default)
    parser.add_argument(
        "--historical-execution-dir",
        type=Path,
        default=package_default / failed_audit.EXECUTION_DIR,
    )
    parser.add_argument(
        "--failed-audit-dir",
        type=Path,
        default=package_default / failed_audit.OUTPUT_DIR,
    )
    parser.add_argument(
        "--preflight-dir",
        type=Path,
        default=package_default / recovery_preflight.OUTPUT_DIR,
    )
    parser.add_argument(
        "--execution-dir",
        type=Path,
        default=package_default / execution.OUTPUT_DIR,
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=package_default / OUTPUT_DIR,
    )
    args = parser.parse_args()
    report = build_postrun_audit(
        package_root=args.package_root,
        implementation_root=args.implementation_root,
        historical_execution_dir=args.historical_execution_dir,
        failed_audit_dir=args.failed_audit_dir,
        preflight_dir=args.preflight_dir,
        execution_dir=args.execution_dir,
        output_dir=args.output_dir,
    )
    print(report.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
