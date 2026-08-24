from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_orphan_support_exit_recovery_preflight as preflight,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_privacy_safe_s1_capability_failure_audit as failed_audit,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_privacy_safe_s1_capability_online as capability_online,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_two_stage_semantic_proposal_execution as legacy,
)
from trusted_synthesis.hashing import canonical_hash

RUN_ID: Final = "finance_v26_144_orphan_support_exit_recovery_execution_v1_20260825"
OUTPUT_DIR: Final = (
    "artifacts/vtdo_experiment/finance_v26_144_orphan_support_exit_recovery_execution_v1_20260825"
)
IMPLEMENTATION_PATH: Final = (
    "src/trusted_synthesis/experiments/vtdo_experiment/"
    "phase1_v26_orphan_support_exit_recovery_execution.py"
)
NEXT_STAGE: Final = "orphan_support_exit_recovery_postrun_audit_only"

EXPECTED_PREFLIGHT_REPORT_ID: Final = (
    "finance_v26_orphan_support_exit_preflight_report:"
    "ee6af1ef4e1462316a953fb247347792b1a04e017a371f9ba756801ce90de0ac"
)
EXPECTED_PREFLIGHT_SOURCE_ID: Final = (
    "finance_v26_orphan_recovery_source_replay:"
    "6f57246215f1310516c7d197e7226d5e0c03135f337895def336d06204272bff"
)
EXPECTED_MANIFEST_ID: Final = (
    "finance_v26_orphan_support_exit_recovery_manifest:"
    "9ecaa1ab2e16c937fef67fa024be42f2f3d5a69338fc7be27812135a49583244"
)
EXPECTED_RUNNER_ID: Final = (
    "finance_v26_orphan_support_exit_runner_contract:"
    "5d6ffa0344dec1f7798e1d5f4ac7dfa8da158d7d73c8c137c40748bcb2d25be4"
)
EXPECTED_OUTCOME_ID: Final = (
    "finance_v26_orphan_support_exit_outcome_contract:"
    "91f65d4c0ed677aee782d222169437db4e2180be6f384fd37829ee2b7fd5e29d"
)
EXPECTED_EXECUTION_ID: Final = (
    "finance_v26_orphan_support_exit_recovery_execution:"
    "de3a15652e87723cca7c6d241c808bf74532fa04c512e21312959a92ebf5c504"
)
EXPECTED_REPORT_IDENTITY: Final = (
    "finance_v26_orphan_support_exit_recovery_report:"
    "6f666c17ae2ece4dfb3ff09dbb3286ea5778f8a2c3bda900da48f7fcd81f6c6c"
)
EXPECTED_PREFLIGHT_TRANSITION_ID: Final = (
    "finance_v26_orphan_support_exit_transition:"
    "b437327598149b20e0829e7946e729eb5830a987276e9f01f4c20f47a32f25c0"
)

PREFLIGHT_OUTPUTS: Final = (
    "candidate_catalog.json",
    "destructive_audit.json",
    "outcome_contract.json",
    "predecessor_rebuild_audit.json",
    "prospective_execution.json",
    "prospective_report.json",
    "prospective_transition_contract.json",
    "recovery_contract.json",
    "recovery_manifest.json",
    "report.json",
    "runner_contract.json",
    "runner_fixture_audit.json",
    "source_replay_audit.json",
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


def _write_jsonl_atomic(path: Path, values: tuple[BaseModel, ...]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(b"".join(_canonical_bytes(value) + b"\n" for value in values))
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
    raise ValueError(f"v26.144 cannot replay bound file: {relative_path}")


class SourceReplayEntry(FrozenModel):
    relative_path: str = Field(min_length=1)
    source_kind: Literal[
        "v26_143_transitive_source",
        "v26_143_output",
        "v26_144_implementation",
    ]
    expected_sha256: str = Field(min_length=64, max_length=64)
    observed_sha256: str = Field(min_length=64, max_length=64)
    byte_count: int = Field(gt=0)
    passed: Literal[True] = True


class ExecutionSourceReplayAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    preflight_report_id: str = EXPECTED_PREFLIGHT_REPORT_ID
    preflight_source_replay_id: str = EXPECTED_PREFLIGHT_SOURCE_ID
    preflight_transitive_file_count: Literal[7242] = 7242
    preflight_output_file_count: Literal[13] = 13
    implementation_file_count: Literal[1] = 1
    replayed_file_count: Literal[7256] = 7256
    replay_pass_count: Literal[7256] = 7256
    entries: tuple[SourceReplayEntry, ...] = Field(min_length=7256, max_length=7256)
    replay_before_recovery_input_loading: Literal[True] = True
    credential_lookup_attempted: Literal[False] = False
    model_client_constructed: Literal[False] = False
    provider_calls: Literal[0] = 0
    stage_two_provider_calls: Literal[0] = 0
    gpu_jobs: Literal[0] = 0
    status: Literal["passed"] = "passed"
    schema_version: Literal["finance_v26_orphan_recovery_execution_source_replay.v1"] = (
        "finance_v26_orphan_recovery_execution_source_replay.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> ExecutionSourceReplayAudit:
        paths = tuple(item.relative_path for item in self.entries)
        if (
            paths != tuple(sorted(set(paths)))
            or len(paths) != self.replayed_file_count
            or any(item.expected_sha256 != item.observed_sha256 for item in self.entries)
        ):
            raise ValueError("v26.144 source replay changed")
        if self.audit_id != _identity(
            self,
            "audit_id",
            "finance_v26_orphan_recovery_execution_source_replay:",
        ):
            raise ValueError("v26.144 source replay identity changed")
        return self


class PreflightFileComparison(FrozenModel):
    relative_path: str = Field(min_length=1)
    expected_sha256: str = Field(min_length=64, max_length=64)
    observed_sha256: str = Field(min_length=64, max_length=64)
    byte_count: int = Field(gt=0)
    byte_identical: Literal[True] = True


class ExecutionPreflightBindingAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    preflight_report_id: str = EXPECTED_PREFLIGHT_REPORT_ID
    recovery_manifest_id: str = EXPECTED_MANIFEST_ID
    runner_contract_id: str = EXPECTED_RUNNER_ID
    outcome_contract_id: str = EXPECTED_OUTCOME_ID
    prospective_execution_id: str = EXPECTED_EXECUTION_ID
    prospective_report_id: str = EXPECTED_REPORT_IDENTITY
    preflight_transition_contract_id: str = EXPECTED_PREFLIGHT_TRANSITION_ID
    file_comparisons: tuple[PreflightFileComparison, ...] = Field(
        min_length=13,
        max_length=13,
    )
    preflight_output_count: Literal[13] = 13
    byte_identical_preflight_output_count: Literal[13] = 13
    exact_recovery_job_count: Literal[3] = 3
    fresh_recovery_job_identity_count: Literal[3] = 3
    provider_call_upper_bound: Literal[0] = 0
    stage_two_provider_call_upper_bound: Literal[0] = 0
    credential_lookup_attempted: Literal[False] = False
    model_client_constructed: Literal[False] = False
    provider_calls: Literal[0] = 0
    status: Literal["passed"] = "passed"
    schema_version: Literal["finance_v26_orphan_recovery_execution_binding.v1"] = (
        "finance_v26_orphan_recovery_execution_binding.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> ExecutionPreflightBindingAudit:
        paths = tuple(item.relative_path for item in self.file_comparisons)
        if paths != tuple(sorted(PREFLIGHT_OUTPUTS)) or any(
            item.expected_sha256 != item.observed_sha256 for item in self.file_comparisons
        ):
            raise ValueError("v26.144 preflight reconstruction changed")
        if self.audit_id != _identity(
            self,
            "audit_id",
            "finance_v26_orphan_recovery_execution_binding:",
        ):
            raise ValueError("v26.144 preflight binding identity changed")
        return self


class RecoveryRawExecution(FrozenModel):
    artifact_id: str = Field(min_length=1)
    prospective_execution_id: str = EXPECTED_EXECUTION_ID
    runner_contract_id: str = EXPECTED_RUNNER_ID
    outcome_contract_id: str = EXPECTED_OUTCOME_ID
    recovery_job: preflight.OrphanSupportExitRecoveryJob
    historical_envelope_id: str = Field(min_length=1)
    historical_projection_id: str = Field(min_length=1)
    historical_transport_certificate_id: str = Field(min_length=1)
    selected_action_id: str = Field(min_length=1)
    commit_record_id: str = Field(min_length=1)
    observation_id: str = Field(min_length=1)
    observation_error_code: Literal["typed_selector_requires_refinement"] = (
        "typed_selector_requires_refinement"
    )
    successor_state_id: str = Field(min_length=1)
    successor_prompt_sha256: str = Field(min_length=64, max_length=64)
    terminal_disposition: str = preflight.TYPED_TERMINAL
    terminal_failure_type: Literal["reference_policy_unavailable"] = "reference_policy_unavailable"
    terminal_error: str = failed_audit.REFERENCE_FAILURE
    exact_model_action_commit_observation_preserved: Literal[True] = True
    historical_prefix_provider_calls_reissued: Literal[0] = 0
    new_provider_calls: Literal[0] = 0
    later_provider_calls: Literal[0] = 0
    stage_two_provider_calls: Literal[0] = 0
    historical_raw_execution_created: Literal[False] = False
    historical_terminal_assigned: Literal[False] = False
    support_exit_counts_as_model_invalid: Literal[False] = False
    support_exit_counts_as_instrument_failure: Literal[False] = False
    support_exit_counts_as_measurement_support_boundary: Literal[True] = True
    schema_version: Literal["finance_v26_orphan_support_exit_recovery_raw.v1"] = (
        "finance_v26_orphan_support_exit_recovery_raw.v1"
    )

    @model_validator(mode="after")
    def validate_raw(self) -> RecoveryRawExecution:
        candidate = self.recovery_job.candidate
        if (
            self.historical_envelope_id != candidate.envelope_id
            or self.historical_projection_id != candidate.projection_id
            or self.historical_transport_certificate_id != candidate.transport_certificate_id
            or self.selected_action_id != candidate.selected_action_id
            or self.commit_record_id != candidate.commit_record_id
            or self.observation_id != candidate.observation_id
            or self.successor_state_id != candidate.successor_state_id
            or self.successor_prompt_sha256 != candidate.successor_prompt_sha256
            or self.terminal_error != candidate.reference_failure_message
        ):
            raise ValueError("v26.144 Raw changed its exact persisted prefix")
        if self.artifact_id != _identity(
            self,
            "artifact_id",
            "finance_v26_orphan_support_exit_recovery_raw:",
        ):
            raise ValueError("v26.144 Raw identity changed")
        return self


class RecoveryJobResult(FrozenModel):
    result_id: str = Field(min_length=1)
    prospective_execution_id: str = EXPECTED_EXECUTION_ID
    recovery_job_id: str = Field(min_length=1)
    recovery_raw_execution_id: str = Field(min_length=1)
    historical_job_id: str = Field(min_length=1)
    terminal_disposition: str = preflight.TYPED_TERMINAL
    model_outcome: Literal[False] = False
    model_invalid_trajectory: Literal[False] = False
    instrument_failure: Literal[False] = False
    measurement_support_boundary_exit: Literal[True] = True
    new_provider_calls: Literal[0] = 0
    historical_terminal_reclassified: Literal[False] = False
    schema_version: Literal["finance_v26_orphan_support_exit_recovery_result.v1"] = (
        "finance_v26_orphan_support_exit_recovery_result.v1"
    )

    @model_validator(mode="after")
    def validate_result(self) -> RecoveryJobResult:
        if self.result_id != _identity(
            self,
            "result_id",
            "finance_v26_orphan_support_exit_recovery_result:",
        ):
            raise ValueError("v26.144 result identity changed")
        return self


class RawLineageAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    prospective_execution_id: str = EXPECTED_EXECUTION_ID
    recovery_manifest_id: str = EXPECTED_MANIFEST_ID
    raw_files: tuple[legacy.RawFileDescriptor, ...] = Field(min_length=3, max_length=3)
    result_files: tuple[legacy.RawFileDescriptor, ...] = Field(min_length=3, max_length=3)
    checkpoint_file: legacy.RawFileDescriptor
    exact_recovery_raw_count: Literal[3] = 3
    exact_recovery_result_count: Literal[3] = 3
    checkpoint_result_count: Literal[3] = 3
    typed_support_exit_count: Literal[3] = 3
    new_provider_call_count: Literal[0] = 0
    historical_raw_or_terminal_creation_count: Literal[0] = 0
    status: Literal["complete"] = "complete"
    schema_version: Literal["finance_v26_orphan_support_exit_raw_lineage.v1"] = (
        "finance_v26_orphan_support_exit_raw_lineage.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> RawLineageAudit:
        raw_paths = tuple(item.relative_path for item in self.raw_files)
        result_paths = tuple(item.relative_path for item in self.result_files)
        if raw_paths != tuple(sorted(set(raw_paths))) or result_paths != tuple(
            sorted(set(result_paths))
        ):
            raise ValueError("v26.144 Raw lineage path set changed")
        if self.audit_id != _identity(
            self,
            "audit_id",
            "finance_v26_orphan_support_exit_raw_lineage:",
        ):
            raise ValueError("v26.144 Raw lineage identity changed")
        return self


class EndpointOutcomeAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    raw_lineage_audit_id: str = Field(min_length=1)
    outcome_contract_id: str = EXPECTED_OUTCOME_ID
    frozen_complete_raw_model_outcome_count: Literal[93] = 93
    fresh_recovery_support_exit_count: Literal[3] = 3
    exact_lineage_endpoint_count: Literal[96] = 96
    frozen_model_valid_trajectory_count: Literal[17] = 17
    frozen_model_invalid_trajectory_count: Literal[76] = 76
    measurement_support_boundary_exit_count: Literal[3] = 3
    instrument_failure_count: Literal[0] = 0
    exact_capability_gate_passed: Literal[False] = False
    exact_task_weighted_capability_estimate_available: Literal[False] = False
    complete_raw_subset_remains_descriptive_only: Literal[True] = True
    reachability_authorized: Literal[False] = False
    schema_version: Literal["finance_v26_orphan_support_exit_endpoint_outcome.v1"] = (
        "finance_v26_orphan_support_exit_endpoint_outcome.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> EndpointOutcomeAudit:
        if (
            self.frozen_complete_raw_model_outcome_count + self.fresh_recovery_support_exit_count
            != self.exact_lineage_endpoint_count
            or self.frozen_model_valid_trajectory_count + self.frozen_model_invalid_trajectory_count
            != self.frozen_complete_raw_model_outcome_count
        ):
            raise ValueError("v26.144 endpoint partition changed")
        if self.audit_id != _identity(
            self,
            "audit_id",
            "finance_v26_orphan_support_exit_endpoint_outcome:",
        ):
            raise ValueError("v26.144 endpoint outcome identity changed")
        return self


class PostrunTransitionContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    raw_lineage_audit_id: str = Field(min_length=1)
    endpoint_outcome_audit_id: str = Field(min_length=1)
    next_permitted_stage: str = NEXT_STAGE
    independent_postrun_audit_required: Literal[True] = True
    provider_calls_authorized: Literal[False] = False
    capability_continuation_authorized: Literal[False] = False
    historical_job_rerun_or_reclassification_authorized: Literal[False] = False
    historical_raw_or_terminal_creation_authorized: Literal[False] = False
    reachability_identity_or_execution_authorized: Literal[False] = False
    state_mapping_training_release_or_production_authorized: Literal[False] = False
    status: Literal["postrun_audit_only"] = "postrun_audit_only"
    schema_version: Literal["finance_v26_orphan_support_exit_postrun_transition.v1"] = (
        "finance_v26_orphan_support_exit_postrun_transition.v1"
    )

    @model_validator(mode="after")
    def validate_contract(self) -> PostrunTransitionContract:
        if self.contract_id != _identity(
            self,
            "contract_id",
            "finance_v26_orphan_support_exit_postrun_transition:",
        ):
            raise ValueError("v26.144 postrun transition identity changed")
        return self


class DetailFile(FrozenModel):
    relative_path: str = Field(min_length=1)
    sha256: str = Field(min_length=64, max_length=64)
    byte_count: int = Field(gt=0)


class RecoveryExecutionReport(FrozenModel):
    report_id: str = Field(min_length=1)
    run_id: str = RUN_ID
    pre_registered_report_identity: str = EXPECTED_REPORT_IDENTITY
    prospective_execution_id: str = EXPECTED_EXECUTION_ID
    source_replay_audit_id: str = Field(min_length=1)
    preexecution_binding_audit_id: str = Field(min_length=1)
    raw_lineage_audit_id: str = Field(min_length=1)
    endpoint_outcome_audit_id: str = Field(min_length=1)
    transition_contract_id: str = Field(min_length=1)
    detail_files: tuple[DetailFile, ...] = Field(min_length=3, max_length=3)
    exact_recovery_job_count: Literal[3] = 3
    completed_recovery_raw_count: Literal[3] = 3
    typed_support_exit_count: Literal[3] = 3
    fresh_provider_call_count: Literal[0] = 0
    stage_two_provider_call_count: Literal[0] = 0
    credential_lookup_attempted: Literal[False] = False
    model_client_constructed: Literal[False] = False
    historical_terminal_reclassification_count: Literal[0] = 0
    exact_capability_gate_passed: Literal[False] = False
    next_permitted_stage: str = NEXT_STAGE
    status: Literal["completed_zero_call_support_exit_recovery"] = (
        "completed_zero_call_support_exit_recovery"
    )
    schema_version: Literal["finance_v26_orphan_support_exit_execution_report.v1"] = (
        "finance_v26_orphan_support_exit_execution_report.v1"
    )

    @model_validator(mode="after")
    def validate_report(self) -> RecoveryExecutionReport:
        if self.report_id != _identity(
            self,
            "report_id",
            "finance_v26_orphan_support_exit_recovery_execution_report:",
        ):
            raise ValueError("v26.144 execution report identity changed")
        return self


@dataclass(frozen=True)
class PreparedExecution:
    source_replay: ExecutionSourceReplayAudit
    preexecution_binding: ExecutionPreflightBindingAudit
    predecessor_prepared: capability_online.PreparedExecution
    root_cause: failed_audit.OrphanRootCauseAudit
    candidate_catalog: preflight.OrphanSupportExitCandidateCatalog
    recovery_contract: preflight.OrphanSupportExitRecoveryContract
    recovery_manifest: preflight.OrphanSupportExitRecoveryManifest
    outcome_contract: preflight.OrphanSupportExitOutcomeContract
    runner_contract: preflight.OrphanSupportExitRunnerContract
    prospective_execution: preflight.ProspectiveRecoveryExecution
    prospective_report: preflight.ProspectiveRecoveryReport
    preflight_transition: preflight.ProspectiveTransitionContract
    preflight_report: preflight.RecoveryPreflightReport


def _source_replay(
    *,
    package_root: Path,
    implementation_root: Path,
    preflight_dir: Path,
) -> ExecutionSourceReplayAudit:
    prior_source = preflight.RecoverySourceReplayAudit.model_validate(
        _load(preflight_dir / "source_replay_audit.json")
    )
    prior_report = preflight.RecoveryPreflightReport.model_validate(
        _load(preflight_dir / "report.json")
    )
    if (
        prior_source.audit_id != EXPECTED_PREFLIGHT_SOURCE_ID
        or prior_report.report_id != EXPECTED_PREFLIGHT_REPORT_ID
    ):
        raise ValueError("v26.144 preflight identity changed")
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
                source_kind="v26_143_transitive_source",
                expected_sha256=item.expected_sha256,
                observed_sha256=_sha256(path),
                byte_count=path.stat().st_size,
            )
        )
    for name in PREFLIGHT_OUTPUTS:
        path = preflight_dir / name
        digest = _sha256(path)
        entries.append(
            SourceReplayEntry(
                relative_path=str(path.relative_to(package_root)),
                source_kind="v26_143_output",
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
            source_kind="v26_144_implementation",
            expected_sha256=digest,
            observed_sha256=digest,
            byte_count=implementation.stat().st_size,
        )
    )
    values = {"entries": tuple(sorted(entries, key=lambda item: item.relative_path))}
    provisional = ExecutionSourceReplayAudit.model_construct(audit_id="pending", **values)
    return ExecutionSourceReplayAudit(
        audit_id=_identity(
            provisional,
            "audit_id",
            "finance_v26_orphan_recovery_execution_source_replay:",
        ),
        **values,
    )


def _rebuild_preflight(
    *,
    package_root: Path,
    implementation_root: Path,
    historical_execution_dir: Path,
    failed_audit_dir: Path,
    preflight_dir: Path,
) -> tuple[
    ExecutionPreflightBindingAudit,
    capability_online.PreparedExecution,
    failed_audit.OrphanRootCauseAudit,
    dict[str, BaseModel],
]:
    source = preflight._source_replay(  # noqa: SLF001
        package_root=package_root,
        implementation_root=implementation_root,
        predecessor_dir=failed_audit_dir,
    )
    rebuilt, predecessor_prepared, root_cause = preflight._rebuild_predecessor(  # noqa: SLF001
        package_root=package_root,
        implementation_root=implementation_root,
        execution_dir=historical_execution_dir,
        predecessor_dir=failed_audit_dir,
    )
    catalog = preflight._catalog(  # noqa: SLF001
        root_cause=root_cause,
        prepared=predecessor_prepared,
        execution_dir=historical_execution_dir,
    )
    contract = preflight._recovery_contract(catalog)  # noqa: SLF001
    manifest = preflight._manifest(contract=contract, catalog=catalog)  # noqa: SLF001
    outcome = preflight._outcome_contract(manifest)  # noqa: SLF001
    runner = preflight._runner_contract(  # noqa: SLF001
        contract=contract,
        manifest=manifest,
        outcome=outcome,
    )
    execution, prospective_report = preflight._prospective_identities(  # noqa: SLF001
        manifest=manifest,
        outcome=outcome,
        runner=runner,
    )
    fixture = preflight._fixture(  # noqa: SLF001
        manifest=manifest,
        runner=runner,
        root_cause=root_cause,
        prepared=predecessor_prepared,
        execution_dir=historical_execution_dir,
    )
    destructive = preflight._destructive(manifest=manifest, fixture=fixture)  # noqa: SLF001
    transition = preflight._transition(  # noqa: SLF001
        contract=contract,
        manifest=manifest,
        outcome=outcome,
        runner=runner,
        execution=execution,
        report=prospective_report,
    )
    objects: dict[str, BaseModel] = {
        "candidate_catalog.json": catalog,
        "destructive_audit.json": destructive,
        "outcome_contract.json": outcome,
        "predecessor_rebuild_audit.json": rebuilt,
        "prospective_execution.json": execution,
        "prospective_report.json": prospective_report,
        "prospective_transition_contract.json": transition,
        "recovery_contract.json": contract,
        "recovery_manifest.json": manifest,
        "runner_contract.json": runner,
        "runner_fixture_audit.json": fixture,
        "source_replay_audit.json": source,
    }
    details = tuple(
        preflight.DetailFile(
            relative_path=name,
            sha256=_sha256(preflight_dir / name),
            byte_count=(preflight_dir / name).stat().st_size,
        )
        for name in objects
    )
    report_values = {
        "source_replay_audit_id": source.audit_id,
        "predecessor_rebuild_audit_id": rebuilt.audit_id,
        "candidate_catalog_id": catalog.catalog_id,
        "recovery_contract_id": contract.contract_id,
        "recovery_manifest_id": manifest.manifest_id,
        "outcome_contract_id": outcome.contract_id,
        "runner_contract_id": runner.runner_contract_id,
        "prospective_execution_id": execution.execution_id,
        "prospective_report_id": prospective_report.report_id,
        "runner_fixture_audit_id": fixture.audit_id,
        "destructive_audit_id": destructive.audit_id,
        "transition_contract_id": transition.contract_id,
        "detail_files": details,
    }
    provisional_report = preflight.RecoveryPreflightReport.model_construct(
        report_id="pending",
        **report_values,
    )
    report = preflight.RecoveryPreflightReport(
        report_id=_identity(
            provisional_report,
            "report_id",
            "finance_v26_orphan_support_exit_preflight_report:",
        ),
        **report_values,
    )
    objects["report.json"] = report
    comparisons: list[PreflightFileComparison] = []
    for name, value in sorted(objects.items()):
        expected = (preflight_dir / name).read_bytes()
        observed = _canonical_bytes(value)
        if expected != observed:
            raise ValueError(f"v26.144 preflight output changed: {name}")
        comparisons.append(
            PreflightFileComparison(
                relative_path=name,
                expected_sha256=hashlib.sha256(expected).hexdigest(),
                observed_sha256=hashlib.sha256(observed).hexdigest(),
                byte_count=len(expected),
            )
        )
    values = {"file_comparisons": tuple(comparisons)}
    provisional = ExecutionPreflightBindingAudit.model_construct(audit_id="pending", **values)
    binding = ExecutionPreflightBindingAudit(
        audit_id=_identity(
            provisional,
            "audit_id",
            "finance_v26_orphan_recovery_execution_binding:",
        ),
        **values,
    )
    return binding, predecessor_prepared, root_cause, objects


def prepare_execution(
    *,
    package_root: Path,
    implementation_root: Path,
    historical_execution_dir: Path,
    failed_audit_dir: Path,
    preflight_dir: Path,
    output_dir: Path,
) -> PreparedExecution:
    source = _source_replay(
        package_root=package_root,
        implementation_root=implementation_root,
        preflight_dir=preflight_dir,
    )
    binding, predecessor_prepared, root_cause, objects = _rebuild_preflight(
        package_root=package_root,
        implementation_root=implementation_root,
        historical_execution_dir=historical_execution_dir,
        failed_audit_dir=failed_audit_dir,
        preflight_dir=preflight_dir,
    )
    catalog = preflight.OrphanSupportExitCandidateCatalog.model_validate(
        objects["candidate_catalog.json"]
    )
    contract = preflight.OrphanSupportExitRecoveryContract.model_validate(
        objects["recovery_contract.json"]
    )
    manifest = preflight.OrphanSupportExitRecoveryManifest.model_validate(
        objects["recovery_manifest.json"]
    )
    outcome = preflight.OrphanSupportExitOutcomeContract.model_validate(
        objects["outcome_contract.json"]
    )
    runner = preflight.OrphanSupportExitRunnerContract.model_validate(
        objects["runner_contract.json"]
    )
    prospective_execution = preflight.ProspectiveRecoveryExecution.model_validate(
        objects["prospective_execution.json"]
    )
    prospective_report = preflight.ProspectiveRecoveryReport.model_validate(
        objects["prospective_report.json"]
    )
    transition = preflight.ProspectiveTransitionContract.model_validate(
        objects["prospective_transition_contract.json"]
    )
    report = preflight.RecoveryPreflightReport.model_validate(objects["report.json"])
    if (
        manifest.manifest_id != EXPECTED_MANIFEST_ID
        or runner.runner_contract_id != EXPECTED_RUNNER_ID
        or outcome.contract_id != EXPECTED_OUTCOME_ID
        or prospective_execution.execution_id != EXPECTED_EXECUTION_ID
        or prospective_report.report_id != EXPECTED_REPORT_IDENTITY
        or transition.contract_id != EXPECTED_PREFLIGHT_TRANSITION_ID
        or report.report_id != EXPECTED_PREFLIGHT_REPORT_ID
    ):
        raise ValueError("v26.144 exact execution identity chain changed")
    output_dir.mkdir(parents=True, exist_ok=True)
    for name, value in objects.items():
        _write_json_atomic(output_dir / f"frozen_{name}", value)
    _write_json_atomic(output_dir / "online_source_replay_audit.json", source)
    _write_json_atomic(output_dir / "preexecution_binding_audit.json", binding)
    return PreparedExecution(
        source_replay=source,
        preexecution_binding=binding,
        predecessor_prepared=predecessor_prepared,
        root_cause=root_cause,
        candidate_catalog=catalog,
        recovery_contract=contract,
        recovery_manifest=manifest,
        outcome_contract=outcome,
        runner_contract=runner,
        prospective_execution=prospective_execution,
        prospective_report=prospective_report,
        preflight_transition=transition,
        preflight_report=report,
    )


def _raw_path(output_dir: Path, job: preflight.OrphanSupportExitRecoveryJob) -> Path:
    digest = job.recovery_job_id.rsplit(":", 1)[-1]
    return output_dir / "raw_executions" / f"{digest}.json"


def _result_path(output_dir: Path, job: preflight.OrphanSupportExitRecoveryJob) -> Path:
    digest = job.recovery_job_id.rsplit(":", 1)[-1]
    return output_dir / "job_results" / f"{digest}.json"


def execute_recovery_job(
    *,
    job: preflight.OrphanSupportExitRecoveryJob,
    prepared: PreparedExecution,
    historical_execution_dir: Path,
    output_dir: Path,
) -> tuple[RecoveryRawExecution, RecoveryJobResult]:
    raw_path = _raw_path(output_dir, job)
    result_path = _result_path(output_dir, job)
    if raw_path.exists() or result_path.exists():
        if not raw_path.exists() or not result_path.exists():
            raise ValueError("v26.144 orphan Raw/result pair is incomplete")
        raw = RecoveryRawExecution.model_validate(_load(raw_path))
        result = RecoveryJobResult.model_validate(_load(result_path))
        if (
            raw.recovery_job.recovery_job_id != job.recovery_job_id
            or result.recovery_job_id != job.recovery_job_id
            or result.recovery_raw_execution_id != raw.artifact_id
        ):
            raise ValueError("v26.144 recovered Raw/result parent changed")
        return raw, result
    root_rows = {item.job_id: item for item in prepared.root_cause.orphan_rows}
    historical_jobs = {item.job_id: item for item in prepared.predecessor_prepared.manifest.jobs}
    candidate = preflight._candidate(  # noqa: SLF001
        root_row=root_rows[job.candidate.historical_job_id],
        job=historical_jobs[job.candidate.historical_job_id],
        prepared=prepared.predecessor_prepared,
        execution_dir=historical_execution_dir,
    )
    if candidate != job.candidate:
        raise ValueError("v26.144 execution prefix differs from RecoveryJob")
    raw_values = {
        "recovery_job": job,
        "historical_envelope_id": candidate.envelope_id,
        "historical_projection_id": candidate.projection_id,
        "historical_transport_certificate_id": candidate.transport_certificate_id,
        "selected_action_id": candidate.selected_action_id,
        "commit_record_id": candidate.commit_record_id,
        "observation_id": candidate.observation_id,
        "successor_state_id": candidate.successor_state_id,
        "successor_prompt_sha256": candidate.successor_prompt_sha256,
    }
    provisional_raw = RecoveryRawExecution.model_construct(artifact_id="pending", **raw_values)
    raw = RecoveryRawExecution(
        artifact_id=_identity(
            provisional_raw,
            "artifact_id",
            "finance_v26_orphan_support_exit_recovery_raw:",
        ),
        **raw_values,
    )
    result_values = {
        "recovery_job_id": job.recovery_job_id,
        "recovery_raw_execution_id": raw.artifact_id,
        "historical_job_id": candidate.historical_job_id,
    }
    provisional_result = RecoveryJobResult.model_construct(
        result_id="pending",
        **result_values,
    )
    result = RecoveryJobResult(
        result_id=_identity(
            provisional_result,
            "result_id",
            "finance_v26_orphan_support_exit_recovery_result:",
        ),
        **result_values,
    )
    _write_json_atomic(raw_path, raw)
    _write_json_atomic(result_path, result)
    return raw, result


def _descriptor(path: Path, output_dir: Path) -> legacy.RawFileDescriptor:
    return legacy.RawFileDescriptor(
        relative_path=str(path.relative_to(output_dir)),
        sha256=_sha256(path),
        byte_count=path.stat().st_size,
    )


def _lineage(
    *,
    prepared: PreparedExecution,
    output_dir: Path,
    raws: tuple[RecoveryRawExecution, ...],
    results: tuple[RecoveryJobResult, ...],
) -> RawLineageAudit:
    checkpoint = output_dir / "checkpoint_results.jsonl"
    values = {
        "raw_files": tuple(
            sorted(
                (
                    _descriptor(_raw_path(output_dir, item.recovery_job), output_dir)
                    for item in raws
                ),
                key=lambda item: item.relative_path,
            )
        ),
        "result_files": tuple(
            sorted(
                (
                    _descriptor(
                        _result_path(
                            output_dir,
                            next(
                                job
                                for job in prepared.recovery_manifest.jobs
                                if job.recovery_job_id == item.recovery_job_id
                            ),
                        ),
                        output_dir,
                    )
                    for item in results
                ),
                key=lambda item: item.relative_path,
            )
        ),
        "checkpoint_file": _descriptor(checkpoint, output_dir),
    }
    provisional = RawLineageAudit.model_construct(audit_id="pending", **values)
    return RawLineageAudit(
        audit_id=_identity(
            provisional,
            "audit_id",
            "finance_v26_orphan_support_exit_raw_lineage:",
        ),
        **values,
    )


def _endpoint(lineage: RawLineageAudit) -> EndpointOutcomeAudit:
    values = {"raw_lineage_audit_id": lineage.audit_id}
    provisional = EndpointOutcomeAudit.model_construct(audit_id="pending", **values)
    return EndpointOutcomeAudit(
        audit_id=_identity(
            provisional,
            "audit_id",
            "finance_v26_orphan_support_exit_endpoint_outcome:",
        ),
        **values,
    )


def _transition(
    *,
    lineage: RawLineageAudit,
    endpoint: EndpointOutcomeAudit,
) -> PostrunTransitionContract:
    values = {
        "raw_lineage_audit_id": lineage.audit_id,
        "endpoint_outcome_audit_id": endpoint.audit_id,
    }
    provisional = PostrunTransitionContract.model_construct(contract_id="pending", **values)
    return PostrunTransitionContract(
        contract_id=_identity(
            provisional,
            "contract_id",
            "finance_v26_orphan_support_exit_postrun_transition:",
        ),
        **values,
    )


def _detail(path: Path, output_dir: Path) -> DetailFile:
    return DetailFile(
        relative_path=str(path.relative_to(output_dir)),
        sha256=_sha256(path),
        byte_count=path.stat().st_size,
    )


def run_recovery_execution(
    *,
    package_root: Path,
    implementation_root: Path,
    historical_execution_dir: Path,
    failed_audit_dir: Path,
    preflight_dir: Path,
    output_dir: Path,
) -> RecoveryExecutionReport:
    prepared = prepare_execution(
        package_root=package_root,
        implementation_root=implementation_root,
        historical_execution_dir=historical_execution_dir,
        failed_audit_dir=failed_audit_dir,
        preflight_dir=preflight_dir,
        output_dir=output_dir,
    )
    report_path = output_dir / "report.json"
    if report_path.exists():
        report = RecoveryExecutionReport.model_validate(_load(report_path))
        if report.prospective_execution_id != EXPECTED_EXECUTION_ID:
            raise ValueError("v26.144 completed report execution identity changed")
        return report
    raw_rows: list[RecoveryRawExecution] = []
    result_rows: list[RecoveryJobResult] = []
    for job in prepared.recovery_manifest.jobs:
        raw, result = execute_recovery_job(
            job=job,
            prepared=prepared,
            historical_execution_dir=historical_execution_dir,
            output_dir=output_dir,
        )
        raw_rows.append(raw)
        result_rows.append(result)
        _write_jsonl_atomic(
            output_dir / "checkpoint_results.jsonl",
            tuple(sorted(result_rows, key=lambda item: item.recovery_job_id)),
        )
    raws = tuple(sorted(raw_rows, key=lambda item: item.recovery_job.recovery_job_id))
    results = tuple(sorted(result_rows, key=lambda item: item.recovery_job_id))
    lineage = _lineage(
        prepared=prepared,
        output_dir=output_dir,
        raws=raws,
        results=results,
    )
    endpoint = _endpoint(lineage)
    transition = _transition(lineage=lineage, endpoint=endpoint)
    _write_json_atomic(output_dir / "raw_lineage_audit.json", lineage)
    _write_json_atomic(output_dir / "endpoint_outcome_audit.json", endpoint)
    _write_json_atomic(output_dir / "prospective_transition_contract.json", transition)
    details = tuple(
        _detail(output_dir / name, output_dir)
        for name in (
            "endpoint_outcome_audit.json",
            "prospective_transition_contract.json",
            "raw_lineage_audit.json",
        )
    )
    values = {
        "source_replay_audit_id": prepared.source_replay.audit_id,
        "preexecution_binding_audit_id": prepared.preexecution_binding.audit_id,
        "raw_lineage_audit_id": lineage.audit_id,
        "endpoint_outcome_audit_id": endpoint.audit_id,
        "transition_contract_id": transition.contract_id,
        "detail_files": details,
    }
    provisional = RecoveryExecutionReport.model_construct(report_id="pending", **values)
    report = RecoveryExecutionReport(
        report_id=_identity(
            provisional,
            "report_id",
            "finance_v26_orphan_support_exit_recovery_execution_report:",
        ),
        **values,
    )
    _write_json_atomic(report_path, report)
    return report


def main() -> None:
    package_default = Path(__file__).resolve().parents[4]
    parser = argparse.ArgumentParser(
        description="Execute the exact three-Job zero-call v26.144 support-exit recovery"
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
        default=package_default / preflight.OUTPUT_DIR,
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=package_default / OUTPUT_DIR,
    )
    parser.add_argument("--prepare-only", action="store_true")
    args = parser.parse_args()
    if args.prepare_only:
        prepared = prepare_execution(
            package_root=args.package_root,
            implementation_root=args.implementation_root,
            historical_execution_dir=args.historical_execution_dir,
            failed_audit_dir=args.failed_audit_dir,
            preflight_dir=args.preflight_dir,
            output_dir=args.output_dir,
        )
        print(prepared.preexecution_binding.model_dump_json(indent=2))
        return
    report = run_recovery_execution(
        package_root=args.package_root,
        implementation_root=args.implementation_root,
        historical_execution_dir=args.historical_execution_dir,
        failed_audit_dir=args.failed_audit_dir,
        preflight_dir=args.preflight_dir,
        output_dir=args.output_dir,
    )
    print(report.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
