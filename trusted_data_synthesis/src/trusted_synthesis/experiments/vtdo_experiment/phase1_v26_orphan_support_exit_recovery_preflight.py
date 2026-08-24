from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from pathlib import Path
from typing import Any, Final, Literal, cast

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_privacy_first_exact_final_execution as privacy_runner,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_privacy_safe_s1_capability_failure_audit as predecessor,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_privacy_safe_s1_capability_online as online,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_privacy_safe_s1_capability_preflight as preflight,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_two_stage_semantic_proposal_execution as legacy,
)
from trusted_synthesis.hashing import canonical_hash
from trusted_synthesis.runtime.agent.prospective_semantic_action_protocol import (
    build_semantic_action_state,
    evaluate_canonical_action_proposal,
)
from trusted_synthesis.runtime.agent.prospective_semantic_action_response_grammar import (
    parse_exact_canonical_action_payload,
)
from trusted_synthesis.runtime.agent.prospective_thinking_completion import CompletionProjection

RUN_ID: Final = "finance_v26_143_orphan_support_exit_recovery_preflight_v1_20260824"
OUTPUT_DIR: Final = (
    "artifacts/vtdo_experiment/"
    "finance_v26_143_orphan_support_exit_recovery_preflight_v1_20260824"
)
IMPLEMENTATION_PATH: Final = (
    "src/trusted_synthesis/experiments/vtdo_experiment/"
    "phase1_v26_orphan_support_exit_recovery_preflight.py"
)
NEXT_STAGE: Final = "orphan_reference_unavailable_support_exit_recovery_execution_only"
TYPED_TERMINAL: Final = "ordinary_replan_reference_unavailable"

EXPECTED_PREDECESSOR_REPORT_ID: Final = (
    "finance_v26_capability_failed_lineage_audit_report:"
    "93972cc33691eec1ab18a767ab2193a9eee490ed22c92e2c07c8eece858bdee2"
)
EXPECTED_PREDECESSOR_SOURCE_ID: Final = (
    "finance_v26_capability_failed_lineage_source_replay:"
    "3a9edf9608a4de0550292427b836bea2e025187d8ae822b3efd873de1f11e751"
)
EXPECTED_FAILED_LINEAGE_ID: Final = (
    "finance_v26_capability_failed_lineage:"
    "b7b2b671fed238a52cd71c9473e3d1d3761b78b0ac6804577d2b34fbe88b1757"
)
EXPECTED_ROOT_CAUSE_ID: Final = (
    "finance_v26_orphan_reference_root_cause:"
    "41194a48e2f79183b5e1970fcac38b1915e57c25d0d5fb1ade1fb734a79dd5e1"
)
EXPECTED_TRANSITION_ID: Final = (
    "finance_v26_capability_failed_lineage_transition:"
    "a242c1f561f6464801b1cb105158a991e4c252962bb524028c408d6467e1d9a3"
)

PREDECESSOR_OUTPUTS: Final = (
    "destructive_audit.json",
    "failed_lineage_audit.json",
    "orphan_root_cause_audit.json",
    "partial_capability_outcome_audit.json",
    "prospective_transition_contract.json",
    "source_replay_audit.json",
    "report.json",
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


def _value_sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


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
    raise ValueError(f"v26.143 cannot replay bound file: {relative_path}")


class SourceReplayEntry(FrozenModel):
    relative_path: str = Field(min_length=1)
    source_kind: Literal[
        "v26_142_transitive_source",
        "v26_142_output",
        "v26_143_implementation",
    ]
    expected_sha256: str = Field(min_length=64, max_length=64)
    observed_sha256: str = Field(min_length=64, max_length=64)
    byte_count: int = Field(gt=0)
    passed: Literal[True] = True


class RecoverySourceReplayAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    predecessor_report_id: str = EXPECTED_PREDECESSOR_REPORT_ID
    predecessor_source_replay_id: str = EXPECTED_PREDECESSOR_SOURCE_ID
    predecessor_transitive_file_count: Literal[7234] = 7234
    predecessor_output_file_count: Literal[7] = 7
    implementation_file_count: Literal[1] = 1
    replayed_file_count: Literal[7242] = 7242
    replay_pass_count: Literal[7242] = 7242
    entries: tuple[SourceReplayEntry, ...] = Field(min_length=7242, max_length=7242)
    replay_before_role_input_loading: Literal[True] = True
    credential_lookup_attempted: Literal[False] = False
    model_client_constructed: Literal[False] = False
    provider_calls: Literal[0] = 0
    stage_two_provider_calls: Literal[0] = 0
    gpu_jobs: Literal[0] = 0
    status: Literal["passed"] = "passed"
    schema_version: Literal["finance_v26_orphan_recovery_source_replay.v1"] = (
        "finance_v26_orphan_recovery_source_replay.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> RecoverySourceReplayAudit:
        paths = tuple(item.relative_path for item in self.entries)
        if (
            paths != tuple(sorted(set(paths)))
            or len(paths) != self.replayed_file_count
            or any(item.expected_sha256 != item.observed_sha256 for item in self.entries)
        ):
            raise ValueError("v26.143 source replay changed")
        if self.audit_id != _identity(
            self,
            "audit_id",
            "finance_v26_orphan_recovery_source_replay:",
        ):
            raise ValueError("v26.143 source replay identity changed")
        return self


class FileComparison(FrozenModel):
    relative_path: str = Field(min_length=1)
    expected_sha256: str = Field(min_length=64, max_length=64)
    observed_sha256: str = Field(min_length=64, max_length=64)
    byte_count: int = Field(gt=0)
    byte_identical: Literal[True] = True


class PredecessorRebuildAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    predecessor_report_id: str = EXPECTED_PREDECESSOR_REPORT_ID
    predecessor_source_replay_id: str = EXPECTED_PREDECESSOR_SOURCE_ID
    failed_lineage_audit_id: str = EXPECTED_FAILED_LINEAGE_ID
    orphan_root_cause_audit_id: str = EXPECTED_ROOT_CAUSE_ID
    predecessor_transition_contract_id: str = EXPECTED_TRANSITION_ID
    file_comparisons: tuple[FileComparison, ...] = Field(min_length=7, max_length=7)
    predecessor_output_count: Literal[7] = 7
    byte_identical_output_count: Literal[7] = 7
    complete_raw_execution_count: Literal[93] = 93
    orphan_job_count: Literal[3] = 3
    provider_call_count: Literal[858] = 858
    provider_calls: Literal[0] = 0
    stage_two_provider_calls: Literal[0] = 0
    historical_terminal_reclassification_count: Literal[0] = 0
    status: Literal["passed"] = "passed"
    schema_version: Literal["finance_v26_orphan_recovery_predecessor_rebuild.v1"] = (
        "finance_v26_orphan_recovery_predecessor_rebuild.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> PredecessorRebuildAudit:
        paths = tuple(item.relative_path for item in self.file_comparisons)
        if (
            paths != tuple(sorted(PREDECESSOR_OUTPUTS))
            or any(item.expected_sha256 != item.observed_sha256 for item in self.file_comparisons)
        ):
            raise ValueError("v26.143 predecessor rebuild changed")
        if self.audit_id != _identity(
            self,
            "audit_id",
            "finance_v26_orphan_recovery_predecessor_rebuild:",
        ):
            raise ValueError("v26.143 predecessor rebuild identity changed")
        return self


class OrphanSupportExitCandidate(FrozenModel):
    candidate_id: str = Field(min_length=1)
    root_cause_row_id: str = Field(min_length=1)
    historical_job_id: str = Field(min_length=1)
    source_task_artifact_id: str = Field(min_length=1)
    mechanism_id: Literal["failure_recovery"] = "failure_recovery"
    tier: Literal["easy_control", "hard_control"]
    replicate_index: int = Field(ge=0, le=7)
    envelope_id: str = Field(min_length=1)
    projection_id: str = Field(min_length=1)
    transport_certificate_id: str = Field(min_length=1)
    envelope_artifact_sha256: str = Field(min_length=64, max_length=64)
    projection_artifact_sha256: str = Field(min_length=64, max_length=64)
    transport_artifact_sha256: str = Field(min_length=64, max_length=64)
    prefix_provider_call_count: Literal[1] = 1
    prefix_provider_total_tokens: int = Field(gt=0)
    exact_model_http_success: Literal[True] = True
    thinking_complete: Literal[True] = True
    usage_complete: Literal[True] = True
    public_payload_sha256: str = Field(min_length=64, max_length=64)
    initial_prompt_sha256: str = Field(min_length=64, max_length=64)
    initial_state_id: str = Field(min_length=1)
    initial_candidate_order_sha256: str = Field(min_length=64, max_length=64)
    proposal_id: str = Field(min_length=1)
    selected_action_id: str = Field(min_length=1)
    selected_decision_kind: Literal["acquire_public_input"] = "acquire_public_input"
    initial_reference_action_id: str = Field(min_length=1)
    selected_prompt_only_reference: Literal[False] = False
    commit_record_id: str = Field(min_length=1)
    observation_id: str = Field(min_length=1)
    observation_content_hash: str = Field(min_length=1)
    observation_status: Literal["failed"] = "failed"
    observation_error_code: Literal["typed_selector_requires_refinement"] = (
        "typed_selector_requires_refinement"
    )
    choice_record_id: str = Field(min_length=1)
    progress_event_id: str = Field(min_length=1)
    progress_vector_changed: Literal[False] = False
    ordinary_detour_count_after: Literal[0] = 0
    successor_state_id: str = Field(min_length=1)
    successor_candidate_order_sha256: str = Field(min_length=64, max_length=64)
    successor_prompt_sha256: str = Field(min_length=64, max_length=64)
    successor_prompt_utf8_bytes: int = Field(gt=0, le=60000)
    successor_classifier_sensitive_key_count: Literal[0] = 0
    reference_failure_type: Literal["ValueError"] = "ValueError"
    reference_failure_message: str = predecessor.REFERENCE_FAILURE
    typed_terminal: str = TYPED_TERMINAL
    later_provider_invocation_count: Literal[0] = 0
    historical_raw_execution_exists: Literal[False] = False
    historical_terminal_assigned: Literal[False] = False
    schema_version: Literal["finance_v26_orphan_support_exit_candidate.v1"] = (
        "finance_v26_orphan_support_exit_candidate.v1"
    )

    @model_validator(mode="after")
    def validate_candidate(self) -> OrphanSupportExitCandidate:
        if self.reference_failure_message != predecessor.REFERENCE_FAILURE:
            raise ValueError("v26.143 reference failure changed")
        if self.candidate_id != _identity(
            self,
            "candidate_id",
            "finance_v26_orphan_support_exit_candidate:",
        ):
            raise ValueError("v26.143 support-exit Candidate identity changed")
        return self


class OrphanSupportExitCandidateCatalog(FrozenModel):
    catalog_id: str = Field(min_length=1)
    predecessor_root_cause_audit_id: str = EXPECTED_ROOT_CAUSE_ID
    candidates: tuple[OrphanSupportExitCandidate, ...] = Field(min_length=3, max_length=3)
    exact_candidate_count: Literal[3] = 3
    exact_prefix_reconstruction_count: Literal[3] = 3
    exact_action_commit_observation_successor_count: Literal[3] = 3
    later_provider_invocation_count: Literal[0] = 0
    historical_raw_or_terminal_materialization_count: Literal[0] = 0
    provider_calls: Literal[0] = 0
    schema_version: Literal["finance_v26_orphan_support_exit_candidate_catalog.v1"] = (
        "finance_v26_orphan_support_exit_candidate_catalog.v1"
    )

    @model_validator(mode="after")
    def validate_catalog(self) -> OrphanSupportExitCandidateCatalog:
        ids = tuple(item.candidate_id for item in self.candidates)
        jobs = {item.historical_job_id for item in self.candidates}
        if ids != tuple(sorted(set(ids))) or len(jobs) != 3:
            raise ValueError("v26.143 Candidate Catalog denominator changed")
        if self.catalog_id != _identity(
            self,
            "catalog_id",
            "finance_v26_orphan_support_exit_candidate_catalog:",
        ):
            raise ValueError("v26.143 Candidate Catalog identity changed")
        return self


class OrphanSupportExitRecoveryContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    predecessor_report_id: str = EXPECTED_PREDECESSOR_REPORT_ID
    predecessor_failed_lineage_id: str = EXPECTED_FAILED_LINEAGE_ID
    predecessor_root_cause_id: str = EXPECTED_ROOT_CAUSE_ID
    predecessor_transition_id: str = EXPECTED_TRANSITION_ID
    candidate_catalog_id: str = Field(min_length=1)
    candidate_ids: tuple[str, ...] = Field(min_length=3, max_length=3)
    exact_recovery_candidate_count: Literal[3] = 3
    exact_persisted_prefix_binding_required: Literal[True] = True
    exact_model_action_commit_observation_preserved: Literal[True] = True
    exact_successor_state_and_prompt_preserved: Literal[True] = True
    reference_unavailable_typed_support_exit_only: Literal[True] = True
    typed_terminal: str = TYPED_TERMINAL
    historical_prefix_provider_calls_reissued: Literal[0] = 0
    later_provider_call_upper_bound: Literal[0] = 0
    stage_two_provider_call_upper_bound: Literal[0] = 0
    historical_raw_or_terminal_creation_allowed: Literal[False] = False
    historical_job_rerun_or_reclassification_allowed: Literal[False] = False
    host_action_selection_replacement_or_repair_allowed: Literal[False] = False
    s1_candidate_prompt_grammar_classifier_model_thinking_resource_change_allowed: Literal[
        False
    ] = False
    reachability_or_state_mapping_allowed: Literal[False] = False
    provider_calls_authorized: Literal[False] = False
    schema_version: Literal["finance_v26_orphan_support_exit_recovery_contract.v1"] = (
        "finance_v26_orphan_support_exit_recovery_contract.v1"
    )

    @model_validator(mode="after")
    def validate_contract(self) -> OrphanSupportExitRecoveryContract:
        if self.candidate_ids != tuple(sorted(set(self.candidate_ids))):
            raise ValueError("v26.143 Recovery Contract Candidate set changed")
        if self.contract_id != _identity(
            self,
            "contract_id",
            "finance_v26_orphan_support_exit_recovery_contract:",
        ):
            raise ValueError("v26.143 Recovery Contract identity changed")
        return self


class OrphanSupportExitRecoveryJob(FrozenModel):
    recovery_job_id: str = Field(min_length=1)
    recovery_contract_id: str = Field(min_length=1)
    candidate: OrphanSupportExitCandidate
    historical_job_identity_retained_only_as_parent: Literal[True] = True
    historical_job_reclassified: Literal[False] = False
    historical_raw_execution_created: Literal[False] = False
    prefix_provider_calls_authorized: Literal[0] = 0
    later_provider_calls_authorized: Literal[0] = 0
    typed_support_exit_authorization_count: Literal[1] = 1
    schema_version: Literal["finance_v26_orphan_support_exit_recovery_job.v1"] = (
        "finance_v26_orphan_support_exit_recovery_job.v1"
    )

    @model_validator(mode="after")
    def validate_job(self) -> OrphanSupportExitRecoveryJob:
        if self.recovery_job_id == self.candidate.historical_job_id:
            raise ValueError("v26.143 RecoveryJob reused historical identity")
        if self.recovery_job_id != _identity(
            self,
            "recovery_job_id",
            "finance_v26_orphan_support_exit_recovery_job:",
        ):
            raise ValueError("v26.143 RecoveryJob identity changed")
        return self


class OrphanSupportExitRecoveryManifest(FrozenModel):
    manifest_id: str = Field(min_length=1)
    recovery_contract_id: str = Field(min_length=1)
    jobs: tuple[OrphanSupportExitRecoveryJob, ...] = Field(min_length=3, max_length=3)
    exact_job_denominator: Literal[3] = 3
    fresh_recovery_job_identity_count: Literal[3] = 3
    historical_job_identity_overlap_count: Literal[0] = 0
    provider_call_upper_bound: Literal[0] = 0
    schema_version: Literal["finance_v26_orphan_support_exit_recovery_manifest.v1"] = (
        "finance_v26_orphan_support_exit_recovery_manifest.v1"
    )

    @model_validator(mode="after")
    def validate_manifest(self) -> OrphanSupportExitRecoveryManifest:
        ids = tuple(item.recovery_job_id for item in self.jobs)
        historical = {item.candidate.historical_job_id for item in self.jobs}
        if ids != tuple(sorted(set(ids))) or len(historical) != 3:
            raise ValueError("v26.143 Recovery Manifest denominator changed")
        if any(item.recovery_contract_id != self.recovery_contract_id for item in self.jobs):
            raise ValueError("v26.143 Recovery Manifest parent changed")
        if set(ids) & historical:
            raise ValueError("v26.143 Recovery Manifest reused historical Job identity")
        if self.manifest_id != _identity(
            self,
            "manifest_id",
            "finance_v26_orphan_support_exit_recovery_manifest:",
        ):
            raise ValueError("v26.143 Recovery Manifest identity changed")
        return self


class OrphanSupportExitOutcomeContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    recovery_manifest_id: str = Field(min_length=1)
    predecessor_failed_lineage_id: str = EXPECTED_FAILED_LINEAGE_ID
    frozen_complete_raw_model_outcome_count: Literal[93] = 93
    exact_recovery_support_exit_count: Literal[3] = 3
    exact_lineage_endpoint_count: Literal[96] = 96
    frozen_independently_valid_model_outcome_count: Literal[17] = 17
    required_recovery_terminal: str = TYPED_TERMINAL
    support_exit_counts_as_model_invalid: Literal[False] = False
    support_exit_counts_as_instrument_failure: Literal[False] = False
    support_exit_counts_as_measurement_support_boundary: Literal[True] = True
    exact_capability_gate_passed: Literal[False] = False
    exact_task_weighted_capability_estimate_available: Literal[False] = False
    complete_raw_subset_remains_descriptive_only: Literal[True] = True
    reachability_authorized: Literal[False] = False
    schema_version: Literal["finance_v26_orphan_support_exit_outcome_contract.v1"] = (
        "finance_v26_orphan_support_exit_outcome_contract.v1"
    )

    @model_validator(mode="after")
    def validate_contract(self) -> OrphanSupportExitOutcomeContract:
        if (
            self.frozen_complete_raw_model_outcome_count
            + self.exact_recovery_support_exit_count
            != self.exact_lineage_endpoint_count
        ):
            raise ValueError("v26.143 Outcome endpoint denominator changed")
        if self.contract_id != _identity(
            self,
            "contract_id",
            "finance_v26_orphan_support_exit_outcome_contract:",
        ):
            raise ValueError("v26.143 Outcome Contract identity changed")
        return self


class OrphanSupportExitRunnerContract(FrozenModel):
    runner_contract_id: str = Field(min_length=1)
    recovery_contract_id: str = Field(min_length=1)
    recovery_manifest_id: str = Field(min_length=1)
    outcome_contract_id: str = Field(min_length=1)
    exact_recovery_job_denominator: Literal[3] = 3
    persisted_prefix_replay_only: Literal[True] = True
    typed_terminal: str = TYPED_TERMINAL
    terminal_emitted_before_later_provider_preparation: Literal[True] = True
    historical_prefix_provider_calls_reissued: Literal[0] = 0
    later_provider_call_upper_bound: Literal[0] = 0
    stage_two_provider_call_upper_bound: Literal[0] = 0
    model_client_route_present: Literal[False] = False
    credential_lookup_route_present: Literal[False] = False
    host_reference_fallback_route_present: Literal[False] = False
    raw_only_completed_recovery: Literal[True] = True
    orphan_artifact_mismatch_fails_closed: Literal[True] = True
    runner_implemented: Literal[True] = True
    empirical_execution_authorized: Literal[False] = False
    schema_version: Literal["finance_v26_orphan_support_exit_runner_contract.v1"] = (
        "finance_v26_orphan_support_exit_runner_contract.v1"
    )

    @model_validator(mode="after")
    def validate_contract(self) -> OrphanSupportExitRunnerContract:
        if self.runner_contract_id != _identity(
            self,
            "runner_contract_id",
            "finance_v26_orphan_support_exit_runner_contract:",
        ):
            raise ValueError("v26.143 Runner Contract identity changed")
        return self


class ProspectiveRecoveryExecution(FrozenModel):
    execution_id: str = Field(min_length=1)
    recovery_manifest_id: str = Field(min_length=1)
    runner_contract_id: str = Field(min_length=1)
    outcome_contract_id: str = Field(min_length=1)
    exact_job_denominator: Literal[3] = 3
    provider_call_upper_bound: Literal[0] = 0
    schema_version: Literal["finance_v26_orphan_support_exit_prospective_execution.v1"] = (
        "finance_v26_orphan_support_exit_prospective_execution.v1"
    )

    @model_validator(mode="after")
    def validate_execution(self) -> ProspectiveRecoveryExecution:
        if self.execution_id != _identity(
            self,
            "execution_id",
            "finance_v26_orphan_support_exit_recovery_execution:",
        ):
            raise ValueError("v26.143 prospective execution identity changed")
        return self


class ProspectiveRecoveryReport(FrozenModel):
    report_id: str = Field(min_length=1)
    prospective_execution_id: str = Field(min_length=1)
    outcome_contract_id: str = Field(min_length=1)
    exact_job_denominator: Literal[3] = 3
    schema_version: Literal["finance_v26_orphan_support_exit_prospective_report.v1"] = (
        "finance_v26_orphan_support_exit_prospective_report.v1"
    )

    @model_validator(mode="after")
    def validate_report(self) -> ProspectiveRecoveryReport:
        if self.report_id != _identity(
            self,
            "report_id",
            "finance_v26_orphan_support_exit_recovery_report:",
        ):
            raise ValueError("v26.143 prospective report identity changed")
        return self


class SupportExitFixtureRow(FrozenModel):
    fixture_id: str = Field(min_length=1)
    recovery_job_id: str = Field(min_length=1)
    recovery_candidate_id: str = Field(min_length=1)
    historical_job_id: str = Field(min_length=1)
    envelope_id: str = Field(min_length=1)
    projection_id: str = Field(min_length=1)
    transport_certificate_id: str = Field(min_length=1)
    commit_record_id: str = Field(min_length=1)
    observation_id: str = Field(min_length=1)
    successor_state_id: str = Field(min_length=1)
    successor_prompt_sha256: str = Field(min_length=64, max_length=64)
    typed_terminal: str = TYPED_TERMINAL
    terminal_failure_type: Literal["reference_policy_unavailable"] = (
        "reference_policy_unavailable"
    )
    terminal_error: str = predecessor.REFERENCE_FAILURE
    model_action_commit_observation_retained: Literal[True] = True
    historical_prefix_provider_calls_reissued: Literal[0] = 0
    new_provider_calls: Literal[0] = 0
    later_provider_calls: Literal[0] = 0
    stage_two_provider_calls: Literal[0] = 0
    historical_raw_created: Literal[False] = False
    historical_terminal_assigned: Literal[False] = False
    fixture_only: Literal[True] = True
    schema_version: Literal["finance_v26_orphan_support_exit_fixture_row.v1"] = (
        "finance_v26_orphan_support_exit_fixture_row.v1"
    )

    @model_validator(mode="after")
    def validate_row(self) -> SupportExitFixtureRow:
        if self.terminal_error != predecessor.REFERENCE_FAILURE:
            raise ValueError("v26.143 fixture error changed")
        if self.fixture_id != _identity(
            self,
            "fixture_id",
            "finance_v26_orphan_support_exit_fixture_row:",
        ):
            raise ValueError("v26.143 fixture row identity changed")
        return self


class RunnerFixtureAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    runner_contract_id: str = Field(min_length=1)
    recovery_manifest_id: str = Field(min_length=1)
    rows: tuple[SupportExitFixtureRow, ...] = Field(min_length=3, max_length=3)
    exact_fixture_job_count: Literal[3] = 3
    exact_prefix_replay_count: Literal[3] = 3
    typed_support_exit_count: Literal[3] = 3
    historical_prefix_provider_call_reissue_count: Literal[0] = 0
    new_provider_call_count: Literal[0] = 0
    later_provider_call_count: Literal[0] = 0
    stage_two_provider_call_count: Literal[0] = 0
    historical_raw_or_terminal_creation_count: Literal[0] = 0
    status: Literal["passed"] = "passed"
    schema_version: Literal["finance_v26_orphan_support_exit_runner_fixture.v1"] = (
        "finance_v26_orphan_support_exit_runner_fixture.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> RunnerFixtureAudit:
        ids = tuple(item.fixture_id for item in self.rows)
        if ids != tuple(sorted(set(ids))):
            raise ValueError("v26.143 Runner fixture denominator changed")
        if self.audit_id != _identity(
            self,
            "audit_id",
            "finance_v26_orphan_support_exit_runner_fixture:",
        ):
            raise ValueError("v26.143 Runner fixture identity changed")
        return self


class MutationResult(FrozenModel):
    mutation_name: str = Field(min_length=1)
    rejected: Literal[True] = True


class DestructiveAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    mutation_results: tuple[MutationResult, ...] = Field(min_length=18, max_length=18)
    mutation_count: Literal[18] = 18
    rejected_count: Literal[18] = 18
    provider_calls: Literal[0] = 0
    status: Literal["passed"] = "passed"
    schema_version: Literal["finance_v26_orphan_support_exit_destructive.v1"] = (
        "finance_v26_orphan_support_exit_destructive.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> DestructiveAudit:
        names = tuple(item.mutation_name for item in self.mutation_results)
        if names != tuple(sorted(set(names))):
            raise ValueError("v26.143 destructive mutation set changed")
        if self.audit_id != _identity(
            self,
            "audit_id",
            "finance_v26_orphan_support_exit_destructive:",
        ):
            raise ValueError("v26.143 destructive audit identity changed")
        return self


class ProspectiveTransitionContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    recovery_contract_id: str = Field(min_length=1)
    recovery_manifest_id: str = Field(min_length=1)
    runner_contract_id: str = Field(min_length=1)
    outcome_contract_id: str = Field(min_length=1)
    prospective_execution_id: str = Field(min_length=1)
    prospective_report_id: str = Field(min_length=1)
    next_permitted_stage: str = NEXT_STAGE
    exact_three_job_recovery_execution_authorized: Literal[True] = True
    exact_typed_support_exit_required: Literal[True] = True
    provider_calls_authorized: Literal[False] = False
    historical_job_rerun_or_reclassification_authorized: Literal[False] = False
    historical_raw_or_terminal_creation_authorized: Literal[False] = False
    host_action_selection_replacement_or_repair_authorized: Literal[False] = False
    capability_continuation_authorized: Literal[False] = False
    reachability_identity_or_execution_authorized: Literal[False] = False
    state_mapping_training_release_or_production_authorized: Literal[False] = False
    status: Literal["exact_zero_call_recovery_execution_only"] = (
        "exact_zero_call_recovery_execution_only"
    )
    schema_version: Literal["finance_v26_orphan_support_exit_transition.v1"] = (
        "finance_v26_orphan_support_exit_transition.v1"
    )

    @model_validator(mode="after")
    def validate_contract(self) -> ProspectiveTransitionContract:
        if self.contract_id != _identity(
            self,
            "contract_id",
            "finance_v26_orphan_support_exit_transition:",
        ):
            raise ValueError("v26.143 transition identity changed")
        return self


class DetailFile(FrozenModel):
    relative_path: str = Field(min_length=1)
    sha256: str = Field(min_length=64, max_length=64)
    byte_count: int = Field(gt=0)


class RecoveryPreflightReport(FrozenModel):
    report_id: str = Field(min_length=1)
    run_id: str = RUN_ID
    source_replay_audit_id: str = Field(min_length=1)
    predecessor_rebuild_audit_id: str = Field(min_length=1)
    candidate_catalog_id: str = Field(min_length=1)
    recovery_contract_id: str = Field(min_length=1)
    recovery_manifest_id: str = Field(min_length=1)
    outcome_contract_id: str = Field(min_length=1)
    runner_contract_id: str = Field(min_length=1)
    prospective_execution_id: str = Field(min_length=1)
    prospective_report_id: str = Field(min_length=1)
    runner_fixture_audit_id: str = Field(min_length=1)
    destructive_audit_id: str = Field(min_length=1)
    transition_contract_id: str = Field(min_length=1)
    detail_files: tuple[DetailFile, ...] = Field(min_length=12, max_length=12)
    exact_recovery_job_count: Literal[3] = 3
    exact_prefix_reconstruction_count: Literal[3] = 3
    typed_support_exit_fixture_count: Literal[3] = 3
    fresh_recovery_job_identity_count: Literal[3] = 3
    real_provider_calls: Literal[0] = 0
    stage_two_provider_calls: Literal[0] = 0
    gpu_jobs: Literal[0] = 0
    historical_raw_or_terminal_creation_count: Literal[0] = 0
    next_permitted_stage: str = NEXT_STAGE
    status: Literal["passed_orphan_support_exit_recovery_preflight"] = (
        "passed_orphan_support_exit_recovery_preflight"
    )
    schema_version: Literal["finance_v26_orphan_support_exit_preflight_report.v1"] = (
        "finance_v26_orphan_support_exit_preflight_report.v1"
    )

    @model_validator(mode="after")
    def validate_report(self) -> RecoveryPreflightReport:
        if self.report_id != _identity(
            self,
            "report_id",
            "finance_v26_orphan_support_exit_preflight_report:",
        ):
            raise ValueError("v26.143 report identity changed")
        return self


def _source_replay(
    *,
    package_root: Path,
    implementation_root: Path,
    predecessor_dir: Path,
) -> RecoverySourceReplayAudit:
    prior = predecessor.FailureAuditSourceReplay.model_validate(
        _load(predecessor_dir / "source_replay_audit.json")
    )
    report = predecessor.CapabilityFailureAuditReport.model_validate(
        _load(predecessor_dir / "report.json")
    )
    if prior.audit_id != EXPECTED_PREDECESSOR_SOURCE_ID or report.report_id != (
        EXPECTED_PREDECESSOR_REPORT_ID
    ):
        raise ValueError("v26.143 predecessor identity changed")
    entries: list[SourceReplayEntry] = []
    for item in prior.entries:
        path = _find_bound_path(
            item.relative_path,
            item.expected_sha256,
            package_root=package_root,
            implementation_root=implementation_root,
        )
        entries.append(
            SourceReplayEntry(
                relative_path=item.relative_path,
                source_kind="v26_142_transitive_source",
                expected_sha256=item.expected_sha256,
                observed_sha256=_sha256(path),
                byte_count=path.stat().st_size,
            )
        )
    for name in PREDECESSOR_OUTPUTS:
        path = predecessor_dir / name
        relative = str(path.relative_to(package_root))
        digest = _sha256(path)
        entries.append(
            SourceReplayEntry(
                relative_path=relative,
                source_kind="v26_142_output",
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
            source_kind="v26_143_implementation",
            expected_sha256=digest,
            observed_sha256=digest,
            byte_count=implementation.stat().st_size,
        )
    )
    values = {"entries": tuple(sorted(entries, key=lambda item: item.relative_path))}
    provisional = RecoverySourceReplayAudit.model_construct(audit_id="pending", **values)
    return RecoverySourceReplayAudit(
        audit_id=_identity(
            provisional,
            "audit_id",
            "finance_v26_orphan_recovery_source_replay:",
        ),
        **values,
    )


def _rebuild_predecessor(
    *,
    package_root: Path,
    implementation_root: Path,
    execution_dir: Path,
    predecessor_dir: Path,
) -> tuple[
    PredecessorRebuildAudit,
    online.PreparedExecution,
    predecessor.OrphanRootCauseAudit,
]:
    source = predecessor._source_replay(  # noqa: SLF001
        package_root=package_root,
        implementation_root=implementation_root,
        execution_dir=execution_dir,
    )
    with tempfile.TemporaryDirectory(prefix="v26_143_prepared_") as temporary:
        prepared = online.prepare_execution(
            preflight_dir=package_root / online.PREFLIGHT_DIR,
            output_dir=Path(temporary),
            package_root=package_root,
            implementation_root=implementation_root,
        )
        lineage, results, _raws, envelopes, projections = predecessor._failed_lineage(  # noqa: SLF001
            source=source,
            execution_dir=execution_dir,
            prepared=prepared,
        )
        partial = predecessor._partial_outcome(  # noqa: SLF001
            lineage=lineage,
            results=results,
            envelopes=envelopes,
            projections=projections,
        )
        root_cause = predecessor._orphan_root_cause(  # noqa: SLF001
            lineage=lineage,
            prepared=prepared,
            execution_dir=execution_dir,
        )
    destructive = predecessor._destructive(  # noqa: SLF001
        lineage=lineage,
        root_cause=root_cause,
    )
    transition = predecessor._transition(  # noqa: SLF001
        lineage=lineage,
        root_cause=root_cause,
    )
    objects: list[tuple[str, BaseModel]] = [
        ("destructive_audit.json", destructive),
        ("failed_lineage_audit.json", lineage),
        ("orphan_root_cause_audit.json", root_cause),
        ("partial_capability_outcome_audit.json", partial),
        ("prospective_transition_contract.json", transition),
        ("source_replay_audit.json", source),
    ]
    details = tuple(
        predecessor.DetailFile(
            relative_path=name,
            sha256=_sha256(predecessor_dir / name),
            byte_count=(predecessor_dir / name).stat().st_size,
        )
        for name, _ in objects
    )
    report_values = {
        "source_replay_audit_id": source.audit_id,
        "failed_lineage_audit_id": lineage.audit_id,
        "partial_outcome_audit_id": partial.audit_id,
        "orphan_root_cause_audit_id": root_cause.audit_id,
        "destructive_audit_id": destructive.audit_id,
        "transition_contract_id": transition.contract_id,
        "detail_files": details,
    }
    provisional_report = predecessor.CapabilityFailureAuditReport.model_construct(
        report_id="pending",
        **report_values,
    )
    rebuilt_report = predecessor.CapabilityFailureAuditReport(
        report_id=_identity(
            provisional_report,
            "report_id",
            "finance_v26_capability_failed_lineage_audit_report:",
        ),
        **report_values,
    )
    objects.append(("report.json", rebuilt_report))
    comparisons: list[FileComparison] = []
    for name, value in sorted(objects):
        expected = (predecessor_dir / name).read_bytes()
        observed = _canonical_bytes(value)
        if expected != observed:
            raise ValueError(f"v26.143 predecessor output changed: {name}")
        comparisons.append(
            FileComparison(
                relative_path=name,
                expected_sha256=hashlib.sha256(expected).hexdigest(),
                observed_sha256=hashlib.sha256(observed).hexdigest(),
                byte_count=len(expected),
            )
        )
    values = {"file_comparisons": tuple(comparisons)}
    provisional = PredecessorRebuildAudit.model_construct(audit_id="pending", **values)
    rebuilt = PredecessorRebuildAudit(
        audit_id=_identity(
            provisional,
            "audit_id",
            "finance_v26_orphan_recovery_predecessor_rebuild:",
        ),
        **values,
    )
    return rebuilt, prepared, root_cause


def _candidate(
    *,
    root_row: predecessor.OrphanRootCauseRow,
    job: preflight.CapabilityJob,
    prepared: online.PreparedExecution,
    execution_dir: Path,
) -> OrphanSupportExitCandidate:
    digest = job.job_id.rsplit(":", 1)[-1]
    envelope_path = execution_dir / "raw_provider_envelopes" / digest / "call_000.json"
    projection_path = execution_dir / "public_payload_projections" / digest / "call_000.json"
    transport_path = (
        execution_dir
        / "transport_invocation_certificates"
        / digest
        / "invocation_000.json"
    )
    envelope = privacy_runner.PrivacyFirstProviderEnvelope.model_validate(_load(envelope_path))
    projection = privacy_runner.PublicPayloadProjection.model_validate(_load(projection_path))
    invocation = preflight.runner_base.TransportInvocationCertificate.model_validate(
        _load(transport_path)
    )
    privacy_runner.validate_provider_artifact_pair(envelope, projection)
    payload = projection.response_payload
    if payload is None:
        raise ValueError("v26.143 orphan public payload is absent")
    binding = preflight._capability_binding(  # noqa: SLF001
        inputs=prepared.inputs,
        tasks=prepared.task_package_catalog,
        job=job,
    )
    state = build_semantic_action_state(
        binding.record.task_package.task.public,
        binding.environment,
        (),
        semantic_rejections=(),
    )
    salt = preflight.role_base._presentation_salt(  # noqa: SLF001
        selection_id=binding.selection_id,
        package=binding.package.predecessor_package,
        strategy="structured_direct",
        state=state,
        logical_index=0,
    )
    prompt = preflight.prompt_base.render_privacy_safe_s1_action_prompt(
        phase="primary",
        instruction=binding.record.task_package.task.public.instruction,
        state=state,
        public_path_condition=None,
        presentation_salt=salt,
        typed_failure=None,
        grammar=prepared.inputs.static.action_grammar,
    )
    decoded, candidates = (
        preflight.runner_base.predecessor.predecessor._decode_compact_prompt_with_expected_salt(  # noqa: E501, SLF001
            prompt,
            presentation_salt=salt,
        )
    )
    reference = preflight.runner_base._reference_proposal_from_s1_prompt(prompt)  # noqa: SLF001
    proposal = parse_exact_canonical_action_payload(payload)
    selected = evaluate_canonical_action_proposal(state, proposal, call_index=1)
    if selected.commit is None or selected.commit.call is None or selected.rejection is not None:
        raise ValueError("v26.143 orphan first public Action does not Commit")
    commit_record = preflight.runner_base._semantic_commit_record(  # noqa: SLF001
        logical_request_index=0,
        state=state,
        proposal=proposal,
        commit=selected.commit,
        stage_two_profile_id=prepared.inputs.static.stage_two.profile_id,
        provider_calls_before_commit=1,
    )
    runtime = preflight.legacy._runtime(binding.record, binding.environment)  # noqa: SLF001
    observation = preflight.legacy._execute_observation(  # noqa: SLF001
        record=binding.record,
        environment=binding.environment,
        runtime=runtime,
        observations=(),
        projection=CompletionProjection(
            request_kind="decision",
            action="call_tool",
            tool_id=selected.commit.call.tool_id,
            arguments=selected.commit.call.arguments,
        ),
    )
    successor = build_semantic_action_state(
        binding.record.task_package.task.public,
        binding.environment,
        (observation,),
        semantic_rejections=(),
    )
    event = preflight.runner_base._progress_event(  # noqa: SLF001
        logical_request_index=0,
        before=state,
        after=successor,
        observation=observation,
        selected_action_id=proposal.action_id,
        reference_action_id=reference.action_id,
        ordinary_detour_count_before=0,
    )
    choice = preflight.action_execution._choice_record(  # noqa: SLF001
        logical_request_index=0,
        phase="primary",
        state=state,
        proposal=proposal,
        commit=selected.commit,
        rejection=None,
        prior_rejected_action_id=None,
        observation=observation,
        progress=event.progress_vector_changed,
    )
    successor_salt = preflight.role_base._presentation_salt(  # noqa: SLF001
        selection_id=binding.selection_id,
        package=binding.package.predecessor_package,
        strategy="structured_direct",
        state=successor,
        logical_index=1,
    )
    successor_prompt = preflight.prompt_base.render_privacy_safe_s1_action_prompt(
        phase="primary",
        instruction=binding.record.task_package.task.public.instruction,
        state=successor,
        public_path_condition=None,
        presentation_salt=successor_salt,
        typed_failure=None,
        grammar=prepared.inputs.static.action_grammar,
    )
    successor_decoded, successor_candidates = (
        preflight.runner_base.predecessor.predecessor._decode_compact_prompt_with_expected_salt(  # noqa: E501, SLF001
            successor_prompt,
            presentation_salt=successor_salt,
        )
    )
    sensitive = preflight.prompt_base._sensitive_key_paths(  # noqa: SLF001
        preflight.prompt_base._privacy_safe_prompt_payload(successor_prompt).model_dump(  # noqa: SLF001
            mode="json"
        )
    )
    error: ValueError | None = None
    try:
        preflight.runner_base._reference_proposal_from_s1_prompt(successor_prompt)  # noqa: SLF001
    except ValueError as caught:
        error = caught
    telemetry = envelope.provider_telemetry
    root_fields = {
        "job_id": job.job_id,
        "initial_state_id": state.state_id,
        "selected_action_id": proposal.action_id,
        "public_observation_error_code": observation.error_code,
        "successor_state_id": successor.state_id,
        "successor_prompt_sha256": legacy.sha256_text(successor_prompt),
    }
    expected_root_fields = {
        "job_id": root_row.job_id,
        "initial_state_id": root_row.initial_state_id,
        "selected_action_id": root_row.selected_action_id,
        "public_observation_error_code": root_row.public_observation_error_code,
        "successor_state_id": root_row.successor_state_id,
        "successor_prompt_sha256": root_row.successor_prompt_sha256,
    }
    if (
        root_fields != expected_root_fields
        or decoded != state
        or successor_decoded != successor
        or {item.action_id for item in candidates}
        != {item.action_id for item in state.action_candidates}
        or {item.action_id for item in successor_candidates}
        != {item.action_id for item in successor.action_candidates}
        or sensitive
        or legacy.sha256_text(prompt) != envelope.prompt_sha256
        or error is None
        or str(error) != predecessor.REFERENCE_FAILURE
        or observation.status != "failed"
        or observation.error_code != "typed_selector_requires_refinement"
        or invocation.job_id != job.job_id
        or invocation.transport_invocation_index != 0
        or (transport_path.parent / "invocation_001.json").exists()
        or (execution_dir / "raw_executions" / f"{digest}.json").exists()
    ):
        raise ValueError("v26.143 exact orphan prefix reconstruction changed")
    values = {
        "root_cause_row_id": root_row.row_id,
        "historical_job_id": job.job_id,
        "source_task_artifact_id": job.source_task_artifact_id,
        "tier": job.tier,
        "replicate_index": job.replicate_index,
        "envelope_id": envelope.envelope_id,
        "projection_id": projection.projection_id,
        "transport_certificate_id": invocation.certificate_id,
        "envelope_artifact_sha256": _sha256(envelope_path),
        "projection_artifact_sha256": _sha256(projection_path),
        "transport_artifact_sha256": _sha256(transport_path),
        "prefix_provider_total_tokens": cast(int, telemetry.total_tokens),
        "exact_model_http_success": bool(
            telemetry.http_success
            and telemetry.model_requested
            == telemetry.model_selected
            == telemetry.response_model
            == "deepseek-v4-flash"
        ),
        "thinking_complete": bool(
            telemetry.reasoning_content_present
            and cast(int, telemetry.reasoning_content_length) > 0
            and cast(int, telemetry.reasoning_tokens) > 0
        ),
        "usage_complete": all(
            item is not None
            for item in (
                telemetry.prompt_tokens,
                telemetry.completion_tokens,
                telemetry.reasoning_tokens,
                telemetry.total_tokens,
            )
        ),
        "public_payload_sha256": _value_sha256(payload),
        "initial_prompt_sha256": legacy.sha256_text(prompt),
        "initial_state_id": state.state_id,
        "initial_candidate_order_sha256": _value_sha256(
            tuple(item.action_id for item in candidates)
        ),
        "proposal_id": proposal.proposal_id,
        "selected_action_id": proposal.action_id,
        "initial_reference_action_id": reference.action_id,
        "commit_record_id": commit_record.record_id,
        "observation_id": observation.observation_id,
        "observation_content_hash": observation.content_hash,
        "choice_record_id": choice.record_id,
        "progress_event_id": event.event_id,
        "successor_state_id": successor.state_id,
        "successor_candidate_order_sha256": _value_sha256(
            tuple(item.action_id for item in successor_candidates)
        ),
        "successor_prompt_sha256": legacy.sha256_text(successor_prompt),
        "successor_prompt_utf8_bytes": len(successor_prompt.encode("utf-8")),
    }
    provisional = OrphanSupportExitCandidate.model_construct(candidate_id="pending", **values)
    return OrphanSupportExitCandidate(
        candidate_id=_identity(
            provisional,
            "candidate_id",
            "finance_v26_orphan_support_exit_candidate:",
        ),
        **values,
    )


def _catalog(
    *,
    root_cause: predecessor.OrphanRootCauseAudit,
    prepared: online.PreparedExecution,
    execution_dir: Path,
) -> OrphanSupportExitCandidateCatalog:
    jobs = {item.job_id: item for item in prepared.manifest.jobs}
    candidates = tuple(
        sorted(
            (
                _candidate(
                    root_row=row,
                    job=jobs[row.job_id],
                    prepared=prepared,
                    execution_dir=execution_dir,
                )
                for row in root_cause.orphan_rows
            ),
            key=lambda item: item.candidate_id,
        )
    )
    values = {"candidates": candidates}
    provisional = OrphanSupportExitCandidateCatalog.model_construct(
        catalog_id="pending",
        **values,
    )
    return OrphanSupportExitCandidateCatalog(
        catalog_id=_identity(
            provisional,
            "catalog_id",
            "finance_v26_orphan_support_exit_candidate_catalog:",
        ),
        **values,
    )


def _recovery_contract(
    catalog: OrphanSupportExitCandidateCatalog,
) -> OrphanSupportExitRecoveryContract:
    values = {
        "candidate_catalog_id": catalog.catalog_id,
        "candidate_ids": tuple(item.candidate_id for item in catalog.candidates),
    }
    provisional = OrphanSupportExitRecoveryContract.model_construct(
        contract_id="pending",
        **values,
    )
    return OrphanSupportExitRecoveryContract(
        contract_id=_identity(
            provisional,
            "contract_id",
            "finance_v26_orphan_support_exit_recovery_contract:",
        ),
        **values,
    )


def _manifest(
    *,
    contract: OrphanSupportExitRecoveryContract,
    catalog: OrphanSupportExitCandidateCatalog,
) -> OrphanSupportExitRecoveryManifest:
    jobs: list[OrphanSupportExitRecoveryJob] = []
    for candidate in catalog.candidates:
        values = {
            "recovery_contract_id": contract.contract_id,
            "candidate": candidate,
        }
        provisional = OrphanSupportExitRecoveryJob.model_construct(
            recovery_job_id="pending",
            **values,
        )
        jobs.append(
            OrphanSupportExitRecoveryJob(
                recovery_job_id=_identity(
                    provisional,
                    "recovery_job_id",
                    "finance_v26_orphan_support_exit_recovery_job:",
                ),
                **values,
            )
        )
    values = {
        "recovery_contract_id": contract.contract_id,
        "jobs": tuple(sorted(jobs, key=lambda item: item.recovery_job_id)),
    }
    provisional_manifest = OrphanSupportExitRecoveryManifest.model_construct(
        manifest_id="pending",
        **values,
    )
    return OrphanSupportExitRecoveryManifest(
        manifest_id=_identity(
            provisional_manifest,
            "manifest_id",
            "finance_v26_orphan_support_exit_recovery_manifest:",
        ),
        **values,
    )


def _outcome_contract(
    manifest: OrphanSupportExitRecoveryManifest,
) -> OrphanSupportExitOutcomeContract:
    values = {"recovery_manifest_id": manifest.manifest_id}
    provisional = OrphanSupportExitOutcomeContract.model_construct(
        contract_id="pending",
        **values,
    )
    return OrphanSupportExitOutcomeContract(
        contract_id=_identity(
            provisional,
            "contract_id",
            "finance_v26_orphan_support_exit_outcome_contract:",
        ),
        **values,
    )


def _runner_contract(
    *,
    contract: OrphanSupportExitRecoveryContract,
    manifest: OrphanSupportExitRecoveryManifest,
    outcome: OrphanSupportExitOutcomeContract,
) -> OrphanSupportExitRunnerContract:
    values = {
        "recovery_contract_id": contract.contract_id,
        "recovery_manifest_id": manifest.manifest_id,
        "outcome_contract_id": outcome.contract_id,
    }
    provisional = OrphanSupportExitRunnerContract.model_construct(
        runner_contract_id="pending",
        **values,
    )
    return OrphanSupportExitRunnerContract(
        runner_contract_id=_identity(
            provisional,
            "runner_contract_id",
            "finance_v26_orphan_support_exit_runner_contract:",
        ),
        **values,
    )


def _prospective_identities(
    *,
    manifest: OrphanSupportExitRecoveryManifest,
    outcome: OrphanSupportExitOutcomeContract,
    runner: OrphanSupportExitRunnerContract,
) -> tuple[ProspectiveRecoveryExecution, ProspectiveRecoveryReport]:
    execution_values = {
        "recovery_manifest_id": manifest.manifest_id,
        "runner_contract_id": runner.runner_contract_id,
        "outcome_contract_id": outcome.contract_id,
    }
    provisional_execution = ProspectiveRecoveryExecution.model_construct(
        execution_id="pending",
        **execution_values,
    )
    execution = ProspectiveRecoveryExecution(
        execution_id=_identity(
            provisional_execution,
            "execution_id",
            "finance_v26_orphan_support_exit_recovery_execution:",
        ),
        **execution_values,
    )
    report_values = {
        "prospective_execution_id": execution.execution_id,
        "outcome_contract_id": outcome.contract_id,
    }
    provisional_report = ProspectiveRecoveryReport.model_construct(
        report_id="pending",
        **report_values,
    )
    report = ProspectiveRecoveryReport(
        report_id=_identity(
            provisional_report,
            "report_id",
            "finance_v26_orphan_support_exit_recovery_report:",
        ),
        **report_values,
    )
    return execution, report


def _fixture(
    *,
    manifest: OrphanSupportExitRecoveryManifest,
    runner: OrphanSupportExitRunnerContract,
    root_cause: predecessor.OrphanRootCauseAudit,
    prepared: online.PreparedExecution,
    execution_dir: Path,
) -> RunnerFixtureAudit:
    root_rows = {item.job_id: item for item in root_cause.orphan_rows}
    historical_jobs = {item.job_id: item for item in prepared.manifest.jobs}
    rows: list[SupportExitFixtureRow] = []
    for job in manifest.jobs:
        candidate = _candidate(
            root_row=root_rows[job.candidate.historical_job_id],
            job=historical_jobs[job.candidate.historical_job_id],
            prepared=prepared,
            execution_dir=execution_dir,
        )
        if candidate != job.candidate:
            raise ValueError("v26.143 fixture prefix differs from RecoveryJob")
        values = {
            "recovery_job_id": job.recovery_job_id,
            "recovery_candidate_id": candidate.candidate_id,
            "historical_job_id": candidate.historical_job_id,
            "envelope_id": candidate.envelope_id,
            "projection_id": candidate.projection_id,
            "transport_certificate_id": candidate.transport_certificate_id,
            "commit_record_id": candidate.commit_record_id,
            "observation_id": candidate.observation_id,
            "successor_state_id": candidate.successor_state_id,
            "successor_prompt_sha256": candidate.successor_prompt_sha256,
        }
        provisional = SupportExitFixtureRow.model_construct(
            fixture_id="pending",
            **values,
        )
        rows.append(
            SupportExitFixtureRow(
                fixture_id=_identity(
                    provisional,
                    "fixture_id",
                    "finance_v26_orphan_support_exit_fixture_row:",
                ),
                **values,
            )
        )
    audit_values: dict[str, Any] = {
        "runner_contract_id": runner.runner_contract_id,
        "recovery_manifest_id": manifest.manifest_id,
        "rows": tuple(sorted(rows, key=lambda item: item.fixture_id)),
    }
    provisional_audit = RunnerFixtureAudit.model_construct(audit_id="pending", **audit_values)
    return RunnerFixtureAudit(
        audit_id=_identity(
            provisional_audit,
            "audit_id",
            "finance_v26_orphan_support_exit_runner_fixture:",
        ),
        **audit_values,
    )


def _destructive(
    *,
    manifest: OrphanSupportExitRecoveryManifest,
    fixture: RunnerFixtureAudit,
) -> DestructiveAudit:
    if len(manifest.jobs) != 3 or len(fixture.rows) != 3:
        raise ValueError("v26.143 destructive baseline changed")
    names = (
        "assign_historical_terminal",
        "authorize_later_provider_call",
        "change_observation_error_code",
        "change_successor_prompt",
        "classify_support_exit_as_instrument_failure",
        "classify_support_exit_as_model_invalid",
        "create_historical_raw_execution",
        "drop_recovery_job",
        "duplicate_recovery_job",
        "fallback_to_host_reference_action",
        "materialize_reachability_identity",
        "modify_model_action",
        "pool_prior_lost_attempt",
        "reissue_historical_prefix_provider_call",
        "reuse_historical_job_identity",
        "state_mapping_authorized",
        "treat_partial_subset_as_exact_capability_estimate",
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
            "finance_v26_orphan_support_exit_destructive:",
        ),
        **values,
    )


def _transition(
    *,
    contract: OrphanSupportExitRecoveryContract,
    manifest: OrphanSupportExitRecoveryManifest,
    outcome: OrphanSupportExitOutcomeContract,
    runner: OrphanSupportExitRunnerContract,
    execution: ProspectiveRecoveryExecution,
    report: ProspectiveRecoveryReport,
) -> ProspectiveTransitionContract:
    values = {
        "recovery_contract_id": contract.contract_id,
        "recovery_manifest_id": manifest.manifest_id,
        "runner_contract_id": runner.runner_contract_id,
        "outcome_contract_id": outcome.contract_id,
        "prospective_execution_id": execution.execution_id,
        "prospective_report_id": report.report_id,
    }
    provisional = ProspectiveTransitionContract.model_construct(
        contract_id="pending",
        **values,
    )
    return ProspectiveTransitionContract(
        contract_id=_identity(
            provisional,
            "contract_id",
            "finance_v26_orphan_support_exit_transition:",
        ),
        **values,
    )


def _detail(path: Path, output_dir: Path) -> DetailFile:
    return DetailFile(
        relative_path=str(path.relative_to(output_dir)),
        sha256=_sha256(path),
        byte_count=path.stat().st_size,
    )


def build_preflight(
    *,
    package_root: Path,
    implementation_root: Path,
    execution_dir: Path,
    predecessor_dir: Path,
    output_dir: Path,
) -> RecoveryPreflightReport:
    source = _source_replay(
        package_root=package_root,
        implementation_root=implementation_root,
        predecessor_dir=predecessor_dir,
    )
    rebuilt, prepared, root_cause = _rebuild_predecessor(
        package_root=package_root,
        implementation_root=implementation_root,
        execution_dir=execution_dir,
        predecessor_dir=predecessor_dir,
    )
    catalog = _catalog(
        root_cause=root_cause,
        prepared=prepared,
        execution_dir=execution_dir,
    )
    contract = _recovery_contract(catalog)
    manifest = _manifest(contract=contract, catalog=catalog)
    outcome = _outcome_contract(manifest)
    runner = _runner_contract(
        contract=contract,
        manifest=manifest,
        outcome=outcome,
    )
    execution, prospective_report = _prospective_identities(
        manifest=manifest,
        outcome=outcome,
        runner=runner,
    )
    fixture = _fixture(
        manifest=manifest,
        runner=runner,
        root_cause=root_cause,
        prepared=prepared,
        execution_dir=execution_dir,
    )
    destructive = _destructive(manifest=manifest, fixture=fixture)
    transition = _transition(
        contract=contract,
        manifest=manifest,
        outcome=outcome,
        runner=runner,
        execution=execution,
        report=prospective_report,
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    outputs: tuple[tuple[str, BaseModel], ...] = (
        ("candidate_catalog.json", catalog),
        ("destructive_audit.json", destructive),
        ("outcome_contract.json", outcome),
        ("predecessor_rebuild_audit.json", rebuilt),
        ("prospective_execution.json", execution),
        ("prospective_report.json", prospective_report),
        ("prospective_transition_contract.json", transition),
        ("recovery_contract.json", contract),
        ("recovery_manifest.json", manifest),
        ("runner_contract.json", runner),
        ("runner_fixture_audit.json", fixture),
        ("source_replay_audit.json", source),
    )
    for name, value in outputs:
        _write_json_atomic(output_dir / name, value)
    details = tuple(_detail(output_dir / name, output_dir) for name, _ in outputs)
    values = {
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
    provisional = RecoveryPreflightReport.model_construct(report_id="pending", **values)
    report = RecoveryPreflightReport(
        report_id=_identity(
            provisional,
            "report_id",
            "finance_v26_orphan_support_exit_preflight_report:",
        ),
        **values,
    )
    _write_json_atomic(output_dir / "report.json", report)
    return report


def main() -> None:
    package_default = Path(__file__).resolve().parents[4]
    parser = argparse.ArgumentParser(
        description="Preflight exact zero-call support exits for three v26.141 orphan prefixes"
    )
    parser.add_argument("--package-root", type=Path, default=package_default)
    parser.add_argument("--implementation-root", type=Path, default=package_default)
    parser.add_argument(
        "--execution-dir",
        type=Path,
        default=package_default / predecessor.EXECUTION_DIR,
    )
    parser.add_argument(
        "--predecessor-dir",
        type=Path,
        default=package_default / predecessor.OUTPUT_DIR,
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=package_default / OUTPUT_DIR,
    )
    args = parser.parse_args()
    report = build_preflight(
        package_root=args.package_root,
        implementation_root=args.implementation_root,
        execution_dir=args.execution_dir,
        predecessor_dir=args.predecessor_dir,
        output_dir=args.output_dir,
    )
    print(report.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
