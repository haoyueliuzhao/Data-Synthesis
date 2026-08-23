from __future__ import annotations

import argparse
import json
from collections import Counter
from collections.abc import Mapping, Sequence
from decimal import Decimal
from pathlib import Path
from typing import Any, Final, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_exact_response_grammar_calibration_execution import (  # noqa: E501
    ExactGrammarExecutionReport,
    ExactGrammarJobResult,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_exact_response_grammar_calibration_postrun_audit import (  # noqa: E501
    PostrunAuditReport,
    PostrunSourceReplayAudit,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_exact_response_grammar_execution import (  # noqa: E501
    load_exact_grammar_static_inputs,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_two_stage_semantic_proposal_execution import (  # noqa: E501
    RawStageOneProviderCall,
    TwoStageRawExecution,
    load_canonical_json,
    sha256_file,
    two_stage_runtime_binding,
)
from trusted_synthesis.hashing import canonical_hash
from trusted_synthesis.runtime.agent.prospective_action_constructibility import (
    PublicActionState,
    SemanticDecisionProposal,
    build_public_action_state,
    compile_semantic_decision,
)
from trusted_synthesis.runtime.agent.prospective_two_stage_exact_response_grammar import (
    parse_exact_semantic_proposal_payload,
)

RUN_ID: Final = "finance_v26_116_semantic_proposal_distribution_audit_v1_20260823"
EXECUTION_DIR: Final = (
    "artifacts/vtdo_experiment/"
    "finance_v26_114_exact_response_grammar_calibration_execution_v1_20260823"
)
PREDECESSOR_AUDIT_DIR: Final = (
    "artifacts/vtdo_experiment/"
    "finance_v26_115_exact_response_grammar_calibration_postrun_audit_v1_20260823"
)
OUTPUT_DIR: Final = (
    "artifacts/vtdo_experiment/finance_v26_116_semantic_proposal_distribution_audit_v1_20260823"
)
IMPLEMENTATION_PATH: Final = (
    "src/trusted_synthesis/experiments/vtdo_experiment/"
    "phase1_v26_semantic_proposal_distribution_audit.py"
)
EXPECTED_EXECUTION_REPORT_ID: Final = (
    "finance_v26_exact_grammar_execution_report:"
    "7b531b1887f1a244ecb0154975946f6e3739d1773bb850e1e5c91a9aa72a5ca3"
)
EXPECTED_PREDECESSOR_REPORT_ID: Final = (
    "finance_v26_exact_grammar_postrun_audit_report:"
    "853fba47e8c1c00a3f189dc2fe6a9114167a4422e5751527f5f6a488466e0eaf"
)
NEXT_STAGE: Final = "semantic_action_selection_protocol_design_only"

ProposalOutcome = Literal[
    "committed",
    "compile_rejected_tool_grammar",
    "compile_rejected_unresolved_operation",
    "compile_rejected_operand_grounding",
    "duplicate_failed_public_call",
]


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class SourceReplayEntry(FrozenModel):
    relative_path: str = Field(min_length=1)
    source_kind: str = Field(min_length=1)
    expected_sha256: str = Field(min_length=64, max_length=64)
    observed_sha256: str = Field(min_length=64, max_length=64)
    byte_count: int = Field(gt=0)
    passed: Literal[True] = True


class SemanticAuditSourceReplay(FrozenModel):
    audit_id: str = Field(min_length=1)
    predecessor_source_replay_id: str = Field(min_length=1)
    predecessor_report_id: str = EXPECTED_PREDECESSOR_REPORT_ID
    predecessor_transitive_file_count: Literal[2172] = 2172
    predecessor_output_file_count: Literal[8] = 8
    implementation_file_count: Literal[1] = 1
    replayed_file_count: Literal[2181] = 2181
    replay_pass_count: Literal[2181] = 2181
    entries: tuple[SourceReplayEntry, ...] = Field(min_length=2181, max_length=2181)
    replay_before_proposal_diagnostics: Literal[True] = True
    credential_lookup_attempted: Literal[False] = False
    model_client_constructed: Literal[False] = False
    provider_calls: Literal[0] = 0
    gpu_jobs: Literal[0] = 0
    status: Literal["passed"] = "passed"
    schema_version: Literal["finance_v26_semantic_distribution_source_replay.v1"] = (
        "finance_v26_semantic_distribution_source_replay.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> SemanticAuditSourceReplay:
        paths = tuple(item.relative_path for item in self.entries)
        if paths != tuple(sorted(paths)) or len(set(paths)) != 2181:
            raise ValueError("v26.116 source replay paths are not canonical and unique")
        if any(item.expected_sha256 != item.observed_sha256 for item in self.entries):
            raise ValueError("v26.116 source replay contains a hash mismatch")
        if self.audit_id != _identity(
            self, "audit_id", "finance_v26_semantic_distribution_source_replay:"
        ):
            raise ValueError("v26.116 source replay identity changed")
        return self


class ProposalDiagnostic(FrozenModel):
    diagnostic_id: str = Field(min_length=1)
    job_id: str = Field(min_length=1)
    mechanism_id: str = Field(min_length=1)
    path_strategy_id: str = Field(min_length=1)
    provider_artifact_id: str = Field(min_length=1)
    provider_call_index: int = Field(ge=0)
    logical_request_index: int = Field(ge=0)
    phase: Literal["primary", "rescue"]
    state_id: str = Field(min_length=1)
    decision_kind: str = Field(min_length=1)
    tool_id: str | None
    node_id: str | None
    operator_id: str | None
    operand_sources: tuple[str, ...]
    direct_argument_fields: tuple[str, ...]
    evidence_id_count: int = Field(ge=0)
    unresolved_symbol_count_before: int = Field(ge=0)
    unresolved_symbol_count_after: int | None = Field(default=None, ge=0)
    ready_operation_count: int = Field(ge=0)
    executable_operation_count: int = Field(ge=0)
    allowed_decision_kinds: tuple[str, ...]
    frontier_decision_kind_allowed: bool
    tool_registered: bool | None
    decision_tool_effective: bool | None
    selected_node_in_ready_frontier: bool | None
    selected_node_resolved: bool | None
    operator_available: bool | None
    operand_sources_exact: bool | None
    evidence_available: bool | None
    required_tool_fields_present: bool | None
    additional_tool_fields_allowed: bool | None
    missing_tool_fields: tuple[str, ...]
    unexpected_tool_fields: tuple[str, ...]
    expected_operand_sources: tuple[str, ...]
    independent_compile_passed: bool
    commit_observed: bool
    duplicate_failed_public_call: bool
    prior_failed_observation_error_code: str | None
    observation_status: Literal["succeeded", "failed"] | None
    observation_error_code: str | None
    outcome: ProposalOutcome
    raw_direct_argument_values_retained: Literal[False] = False
    private_reasoning_retained: Literal[False] = False
    schema_version: Literal["finance_v26_semantic_proposal_diagnostic.v1"] = (
        "finance_v26_semantic_proposal_diagnostic.v1"
    )

    @model_validator(mode="after")
    def validate_diagnostic(self) -> ProposalDiagnostic:
        if self.commit_observed != (self.outcome == "committed"):
            raise ValueError("v26.116 Commit and outcome disagree")
        if self.duplicate_failed_public_call != (self.outcome == "duplicate_failed_public_call"):
            raise ValueError("v26.116 duplicate-call diagnosis and outcome disagree")
        if self.diagnostic_id != _identity(
            self, "diagnostic_id", "finance_v26_semantic_proposal_diagnostic:"
        ):
            raise ValueError("v26.116 Proposal diagnostic identity changed")
        return self


class ProposalDiagnosticSet(FrozenModel):
    audit_id: str = Field(min_length=1)
    execution_report_id: str = EXPECTED_EXECUTION_REPORT_ID
    provider_payload_denominator: Literal[81] = 81
    exact_abi_accepted_count: Literal[54] = 54
    diagnostic_count: Literal[54] = 54
    unique_diagnostic_id_count: Literal[54] = 54
    dynamic_state_reconstruction_pass_count: Literal[54] = 54
    exact_state_binding_pass_count: Literal[54] = 54
    diagnostics: tuple[ProposalDiagnostic, ...] = Field(min_length=54, max_length=54)
    raw_direct_argument_values_retained: Literal[False] = False
    private_reasoning_retained: Literal[False] = False
    schema_version: Literal["finance_v26_semantic_proposal_diagnostic_set.v1"] = (
        "finance_v26_semantic_proposal_diagnostic_set.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> ProposalDiagnosticSet:
        keys = tuple(
            (item.job_id, item.provider_call_index, item.diagnostic_id) for item in self.diagnostics
        )
        if (
            keys != tuple(sorted(keys))
            or len({item.diagnostic_id for item in self.diagnostics}) != 54
        ):
            raise ValueError("v26.116 Proposal diagnostics are not canonical and unique")
        if self.audit_id != _identity(
            self, "audit_id", "finance_v26_semantic_proposal_diagnostic_set:"
        ):
            raise ValueError("v26.116 Proposal diagnostic-set identity changed")
        return self


class SemanticProposalDistributionAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    provider_payload_count: Literal[81] = 81
    exact_abi_accepted_count: Literal[54] = 54
    exact_abi_acceptance_fraction: Literal["0.666666666667"] = "0.666666666667"
    accepted_decision_kind_counts: dict[str, int]
    accepted_tool_counts: dict[str, int]
    accepted_phase_counts: dict[str, int]
    accepted_logical_request_index_counts: dict[str, int]
    committed_count: Literal[30] = 30
    accepted_to_commit_fraction: Literal["0.555555555556"] = "0.555555555556"
    committed_decision_kind_counts: dict[str, int]
    decision_kind_commit_fractions: dict[str, str]
    outcome_counts: dict[str, int]
    accepted_by_mechanism: dict[str, int]
    committed_by_mechanism: dict[str, int]
    accepted_by_path_strategy: dict[str, int]
    committed_by_path_strategy: dict[str, int]
    verify_terminal_proposal_count: Literal[0] = 0
    emit_final_proposal_count: Literal[0] = 0
    interpretation: Literal[
        "exact_abi_crossed_but_semantic_action_selection_and_progression_failed"
    ] = "exact_abi_crossed_but_semantic_action_selection_and_progression_failed"
    schema_version: Literal["finance_v26_semantic_proposal_distribution_audit.v1"] = (
        "finance_v26_semantic_proposal_distribution_audit.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> SemanticProposalDistributionAudit:
        if self.accepted_decision_kind_counts != {
            "acquire_public_input": 42,
            "execute_public_operation": 12,
        }:
            raise ValueError("v26.116 accepted Decision distribution changed")
        if self.committed_decision_kind_counts != {
            "acquire_public_input": 29,
            "execute_public_operation": 1,
        }:
            raise ValueError("v26.116 committed Decision distribution changed")
        if self.outcome_counts != {
            "commit_rejected_operand_grounding": 4,
            "commit_rejected_tool_grammar": 10,
            "commit_rejected_unresolved_operation": 7,
            "committed": 30,
            "duplicate_failed_public_call": 3,
        }:
            raise ValueError("v26.116 Proposal outcome partition changed")
        if self.audit_id != _identity(
            self, "audit_id", "finance_v26_semantic_proposal_distribution:"
        ):
            raise ValueError("v26.116 Proposal distribution identity changed")
        return self


class ActionSelectionFailureAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    accepted_without_commit_count: Literal[24] = 24
    failure_dimension_counts: dict[str, int]
    failure_decision_kind_counts: dict[str, int]
    tool_grammar_missing_field_signatures: dict[str, int]
    tool_grammar_unexpected_field_signatures: dict[str, int]
    unresolved_operation_node_counts: dict[str, int]
    operand_source_mismatch_signatures: dict[str, int]
    duplicate_prior_error_counts: dict[str, int]
    tool_not_registered_count: Literal[0] = 0
    ineffective_decision_tool_count: Literal[0] = 0
    node_not_in_ready_frontier_count: Literal[0] = 0
    unavailable_operator_count: Literal[0] = 0
    unavailable_evidence_count: Literal[0] = 0
    unresolved_operation_frontier_count: Literal[7] = 7
    operand_grounding_mismatch_count: Literal[4] = 4
    tool_grammar_mismatch_count: Literal[10] = 10
    duplicate_failed_public_call_count: Literal[3] = 3
    root_cause_scope: Literal[
        "model_semantic_action_selection_not_response_serialization_or_stage_two_compilation"
    ] = "model_semantic_action_selection_not_response_serialization_or_stage_two_compilation"
    causal_exclusivity_claimed: Literal[False] = False
    empirical_rows_reclassified: Literal[0] = 0
    schema_version: Literal["finance_v26_action_selection_failure_audit.v1"] = (
        "finance_v26_action_selection_failure_audit.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> ActionSelectionFailureAudit:
        if self.failure_dimension_counts != {
            "duplicate_failed_public_call": 3,
            "operand_grounding": 4,
            "public_state_frontier": 7,
            "tool_argument_grammar": 10,
        }:
            raise ValueError("v26.116 Action Selection failure partition changed")
        if self.audit_id != _identity(self, "audit_id", "finance_v26_action_selection_failure:"):
            raise ValueError("v26.116 Action Selection failure identity changed")
        return self


class TrajectoryProgressionAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    job_count: Literal[32] = 32
    jobs_with_accepted_proposal: int = Field(ge=0, le=32)
    jobs_with_commit: int = Field(ge=0, le=32)
    jobs_with_successful_observation: int = Field(ge=0, le=32)
    jobs_with_two_or_more_commits: int = Field(ge=0, le=32)
    maximum_commits_per_job: int = Field(ge=0)
    commit_count_distribution: dict[str, int]
    terminal_failure_type_counts: dict[str, int]
    committed_logical_request_index_counts: dict[str, int]
    successful_observation_logical_request_index_counts: dict[str, int]
    committed_acquisition_count: Literal[29] = 29
    successful_acquisition_count: Literal[22] = 22
    successful_acquisition_reduced_unresolved_symbols_count: int = Field(ge=0)
    committed_operation_count: Literal[1] = 1
    successful_operation_count: Literal[1] = 1
    committed_verification_count: Literal[0] = 0
    emitted_final_count: Literal[0] = 0
    program_closed_count: Literal[0] = 0
    independently_valid_count: Literal[0] = 0
    stage_two_provider_call_count: Literal[0] = 0
    interpretation: Literal[
        "semantic_actions_started_but_no_job_reached_verification_or_program_closure"
    ] = "semantic_actions_started_but_no_job_reached_verification_or_program_closure"
    schema_version: Literal["finance_v26_trajectory_progression_audit.v1"] = (
        "finance_v26_trajectory_progression_audit.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> TrajectoryProgressionAudit:
        if sum(self.commit_count_distribution.values()) != 32:
            raise ValueError("v26.116 commit-count Job denominator changed")
        if self.audit_id != _identity(self, "audit_id", "finance_v26_trajectory_progression:"):
            raise ValueError("v26.116 trajectory progression identity changed")
        return self


class ProspectiveTransitionContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    observed_result: Literal["semantic_action_selection_failure_distribution_measured"] = (
        "semantic_action_selection_failure_distribution_measured"
    )
    exact_response_grammar_primary_blocker_rejected: Literal[True] = True
    completion_budget_primary_blocker_rejected: Literal[True] = True
    stage_two_compiler_primary_blocker_rejected: Literal[True] = True
    semantic_action_selection_is_current_object: Literal[True] = True
    host_stage_metadata_preflight_prioritized: Literal[False] = False
    response_grammar_optimization_authorized: Literal[False] = False
    completion_or_rollout_increase_authorized: Literal[False] = False
    host_semantic_selection_or_repair_authorized: Literal[False] = False
    historical_rerun_or_reclassification_authorized: Literal[False] = False
    provider_calls_authorized: Literal[False] = False
    fresh_protocol_and_credential_free_preflight_required_before_future_calls: Literal[True] = True
    role_experiment_authorized: Literal[False] = False
    state_mapping_authorized: Literal[False] = False
    training_authorized: Literal[False] = False
    production_contribution: Literal[0] = 0
    next_permitted_stage: Literal["semantic_action_selection_protocol_design_only"] = NEXT_STAGE
    schema_version: Literal["finance_v26_semantic_action_selection_transition.v1"] = (
        "finance_v26_semantic_action_selection_transition.v1"
    )

    @model_validator(mode="after")
    def validate_contract(self) -> ProspectiveTransitionContract:
        if self.contract_id != _identity(
            self, "contract_id", "finance_v26_semantic_action_selection_transition:"
        ):
            raise ValueError("v26.116 transition identity changed")
        return self


class MutationResult(FrozenModel):
    name: str = Field(min_length=1)
    rejected: Literal[True] = True
    provider_calls_before_rejection: Literal[0] = 0


class DestructiveAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    mutation_count: Literal[21] = 21
    rejection_count: Literal[21] = 21
    mutations: tuple[MutationResult, ...] = Field(min_length=21, max_length=21)
    provider_calls: Literal[0] = 0
    stage_two_provider_calls: Literal[0] = 0
    status: Literal["passed"] = "passed"
    schema_version: Literal["finance_v26_semantic_distribution_destructive.v1"] = (
        "finance_v26_semantic_distribution_destructive.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> DestructiveAudit:
        if self.audit_id != _identity(
            self, "audit_id", "finance_v26_semantic_distribution_destructive:"
        ):
            raise ValueError("v26.116 destructive identity changed")
        return self


class DetailFile(FrozenModel):
    relative_path: str = Field(min_length=1)
    sha256: str = Field(min_length=64, max_length=64)
    byte_count: int = Field(gt=0)


class SemanticProposalAuditReport(FrozenModel):
    report_id: str = Field(min_length=1)
    run_id: Literal["finance_v26_116_semantic_proposal_distribution_audit_v1_20260823"] = RUN_ID
    execution_report_id: str = EXPECTED_EXECUTION_REPORT_ID
    predecessor_report_id: str = EXPECTED_PREDECESSOR_REPORT_ID
    source_replay_audit_id: str = Field(min_length=1)
    proposal_diagnostic_set_id: str = Field(min_length=1)
    distribution_audit_id: str = Field(min_length=1)
    action_selection_failure_audit_id: str = Field(min_length=1)
    trajectory_progression_audit_id: str = Field(min_length=1)
    transition_contract_id: str = Field(min_length=1)
    destructive_audit_id: str = Field(min_length=1)
    detail_files: tuple[DetailFile, ...] = Field(min_length=7, max_length=7)
    exact_job_denominator: Literal[32] = 32
    exact_abi_accepted_count: Literal[54] = 54
    semantic_commit_count: Literal[30] = 30
    accepted_without_commit_count: Literal[24] = 24
    program_closed_count: Literal[0] = 0
    independently_valid_count: Literal[0] = 0
    credential_lookup_attempted: Literal[False] = False
    model_client_constructed: Literal[False] = False
    provider_calls: Literal[0] = 0
    stage_two_provider_calls: Literal[0] = 0
    gpu_jobs: Literal[0] = 0
    empirical_rows_reclassified: Literal[0] = 0
    capability_rows: Literal[0] = 0
    reachability_rows: Literal[0] = 0
    state_mapping_rows: Literal[0] = 0
    production_contribution: Literal[0] = 0
    status: Literal["semantic_action_selection_failure_distribution_audited"] = (
        "semantic_action_selection_failure_distribution_audited"
    )
    next_permitted_stage: Literal["semantic_action_selection_protocol_design_only"] = NEXT_STAGE
    schema_version: Literal["finance_v26_semantic_proposal_audit_report.v1"] = (
        "finance_v26_semantic_proposal_audit_report.v1"
    )

    @model_validator(mode="after")
    def validate_report(self) -> SemanticProposalAuditReport:
        if self.report_id != _identity(
            self, "report_id", "finance_v26_semantic_proposal_audit_report:"
        ):
            raise ValueError("v26.116 report identity changed")
        return self


class LoadedEvidence(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", arbitrary_types_allowed=True)

    execution_report: ExactGrammarExecutionReport
    predecessor_report: PostrunAuditReport
    results: tuple[ExactGrammarJobResult, ...]
    raws: tuple[TwoStageRawExecution, ...]
    providers: tuple[RawStageOneProviderCall, ...]
    providers_by_relative_path: dict[str, RawStageOneProviderCall]


def _identity(value: BaseModel, field: str, prefix: str) -> str:
    return canonical_hash(value.model_dump(mode="json", exclude={field}), prefix=prefix)


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(_canonical_bytes(value))
    temporary.replace(path)


def _find_bound_path(
    relative_path: str,
    expected_sha256: str,
    *,
    package_root: Path,
    implementation_root: Path,
) -> Path:
    for root in (implementation_root, package_root):
        candidate = root / relative_path
        if candidate.is_file() and sha256_file(candidate) == expected_sha256:
            return candidate
    raise ValueError(f"v26.116 cannot replay bound file: {relative_path}")


def _source_entry(path: Path, relative_path: str, source_kind: str) -> SourceReplayEntry:
    digest = sha256_file(path)
    return SourceReplayEntry(
        relative_path=relative_path,
        source_kind=source_kind,
        expected_sha256=digest,
        observed_sha256=digest,
        byte_count=path.stat().st_size,
    )


def _build_source_replay(
    *,
    package_root: Path,
    implementation_root: Path,
    predecessor_audit_dir: Path,
) -> tuple[SemanticAuditSourceReplay, PostrunAuditReport]:
    predecessor_source = PostrunSourceReplayAudit.model_validate(
        _load_json(predecessor_audit_dir / "source_replay_audit.json")
    )
    predecessor_report = PostrunAuditReport.model_validate(
        _load_json(predecessor_audit_dir / "report.json")
    )
    if predecessor_report.report_id != EXPECTED_PREDECESSOR_REPORT_ID:
        raise ValueError("v26.116 predecessor report identity changed")
    entries: dict[str, SourceReplayEntry] = {}
    for item in predecessor_source.entries:
        path = _find_bound_path(
            item.relative_path,
            item.expected_sha256,
            package_root=package_root,
            implementation_root=implementation_root,
        )
        entries[item.relative_path] = SourceReplayEntry(
            relative_path=item.relative_path,
            source_kind="v26_115_transitive_source",
            expected_sha256=item.expected_sha256,
            observed_sha256=sha256_file(path),
            byte_count=path.stat().st_size,
        )
    predecessor_paths = tuple(
        sorted(path for path in predecessor_audit_dir.iterdir() if path.is_file())
    )
    if len(predecessor_paths) != 8:
        raise ValueError("v26.116 predecessor output-file denominator changed")
    detail_by_path = {item.relative_path: item for item in predecessor_report.detail_files}
    relative_root = Path(PREDECESSOR_AUDIT_DIR)
    for path in predecessor_paths:
        relative = str(relative_root / path.name)
        if path.name != "report.json":
            detail = detail_by_path.get(path.name)
            if (
                detail is None
                or detail.sha256 != sha256_file(path)
                or detail.byte_count != path.stat().st_size
            ):
                raise ValueError("v26.116 predecessor detail binding changed")
        entries[relative] = _source_entry(path, relative, "v26_115_output")
    implementation = implementation_root / IMPLEMENTATION_PATH
    entries[IMPLEMENTATION_PATH] = _source_entry(
        implementation, IMPLEMENTATION_PATH, "v26_116_implementation"
    )
    ordered = tuple(entries[key] for key in sorted(entries))
    values: dict[str, Any] = {
        "predecessor_source_replay_id": predecessor_source.audit_id,
        "entries": ordered,
    }
    provisional = SemanticAuditSourceReplay.model_construct(audit_id="pending", **values)
    audit = SemanticAuditSourceReplay(
        audit_id=_identity(
            provisional, "audit_id", "finance_v26_semantic_distribution_source_replay:"
        ),
        **values,
    )
    return audit, predecessor_report


def _load_evidence(
    *,
    execution_dir: Path,
    predecessor_report: PostrunAuditReport,
) -> LoadedEvidence:
    execution_report = ExactGrammarExecutionReport.model_validate(
        _load_json(execution_dir / "report.json")
    )
    if execution_report.report_id != EXPECTED_EXECUTION_REPORT_ID:
        raise ValueError("v26.116 execution report identity changed")
    results = tuple(
        ExactGrammarJobResult.model_validate(item)
        for item in _load_json(execution_dir / "two_stage_job_results.json")
    )
    raw_paths = tuple(sorted((execution_dir / "raw_execution").glob("*.json")))
    raws = tuple(
        TwoStageRawExecution.model_validate(load_canonical_json(path)) for path in raw_paths
    )
    provider_paths = tuple(sorted((execution_dir / "raw_provider_calls").glob("*/*.json")))
    providers = tuple(
        RawStageOneProviderCall.model_validate(load_canonical_json(path)) for path in provider_paths
    )
    if (
        len(results) != 32
        or len(raws) != 32
        or len(providers) != 81
        or predecessor_report.exact_job_denominator != 32
        or predecessor_report.exact_abi_accepted_count != 54
        or predecessor_report.semantic_commit_count != 30
    ):
        raise ValueError("v26.116 evidence denominator changed")
    return LoadedEvidence(
        execution_report=execution_report,
        predecessor_report=predecessor_report,
        results=results,
        raws=raws,
        providers=providers,
        providers_by_relative_path={
            str(path.relative_to(execution_dir)): artifact
            for path, artifact in zip(provider_paths, providers, strict=True)
        },
    )


def _allowed_decision_kinds(state: PublicActionState) -> tuple[str, ...]:
    allowed: set[str] = set()
    effective_acquisition_tools = {
        tool_id
        for item in state.variable_affordances
        if item.symbol in set(state.unresolved_symbols)
        for tool_id in item.acquisition_tool_ids
    }
    effective_acquisition_tools.update(
        item.tool_id
        for item in state.tool_grammars
        if item.semantic_role in {"acquire", "inspect", "query"}
    )
    if effective_acquisition_tools:
        allowed.add("acquire_public_input")
    if any(not item.unresolved_symbols for item in state.ready_operations):
        allowed.add("execute_public_operation")
    if state.terminal_operation_ref and not state.terminal_verification_completed:
        allowed.add("verify_terminal_operation")
    if state.final_answer_allowed:
        allowed.add("emit_final_answer")
    return tuple(sorted(allowed))


def _semantic_projection(proposal: SemanticDecisionProposal) -> dict[str, Any]:
    return proposal.model_dump(
        mode="json",
        exclude={"proposal_id", "model_selected_every_semantic_field", "schema_version"},
    )


def _diagnostic_values(
    *,
    state: PublicActionState,
    proposal: SemanticDecisionProposal,
) -> dict[str, Any]:
    grammars = {item.tool_id: item for item in state.tool_grammars}
    grammar = grammars.get(str(proposal.tool_id)) if proposal.tool_id is not None else None
    tool_registered = proposal.tool_id in grammars if proposal.tool_id is not None else None
    ready = {item.node_id: item for item in state.ready_operations}
    operation = ready.get(str(proposal.node_id)) if proposal.node_id is not None else None
    decision_tool_effective: bool | None = None
    selected_node_in_ready: bool | None = None
    selected_node_resolved: bool | None = None
    operator_available: bool | None = None
    operand_sources_exact: bool | None = None
    evidence_available: bool | None = None
    expected_operand_sources: tuple[str, ...] = ()
    if proposal.decision_kind == "acquire_public_input":
        effective = {
            tool_id
            for item in state.variable_affordances
            if item.symbol in set(state.unresolved_symbols)
            for tool_id in item.acquisition_tool_ids
        }
        effective.update(
            item.tool_id
            for item in state.tool_grammars
            if item.semantic_role in {"acquire", "inspect", "query"}
        )
        decision_tool_effective = proposal.tool_id in effective
    elif proposal.decision_kind == "execute_public_operation":
        selected_node_in_ready = operation is not None
        decision_tool_effective = operation is not None and operation.tool_id == proposal.tool_id
        selected_node_resolved = operation is not None and not operation.unresolved_symbols
        if operation is not None:
            expected_operand_sources = tuple(item.source_symbol for item in operation.operand_slots)
            operand_sources_exact = proposal.operand_sources == expected_operand_sources
            if operation.node_kind == "normalization":
                operator_available = proposal.operator_id is None
            else:
                operator_available = proposal.operator_id in set(operation.allowed_operator_ids)
    elif proposal.decision_kind == "verify_terminal_operation":
        decision_tool_effective = bool(
            tool_registered
            and state.terminal_operation_ref
            and not state.terminal_verification_completed
        )
        evidence_available = set(proposal.evidence_ids) <= set(state.selected_evidence_ids)
    else:
        decision_tool_effective = state.final_answer_allowed and proposal.tool_id is None
    arguments = proposal.direct_arguments or {}
    missing = (
        tuple(sorted(set(grammar.required_input_fields) - set(arguments)))
        if grammar is not None and proposal.decision_kind == "acquire_public_input"
        else ()
    )
    extra = (
        tuple(sorted(set(arguments) - set(grammar.input_contract)))
        if grammar is not None and proposal.decision_kind == "acquire_public_input"
        else ()
    )
    required_present = (
        not missing
        if grammar is not None and proposal.decision_kind == "acquire_public_input"
        else None
    )
    additional_allowed = (
        not extra or grammar.allow_additional_input_fields
        if grammar is not None and proposal.decision_kind == "acquire_public_input"
        else None
    )
    allowed_decisions = _allowed_decision_kinds(state)
    return {
        "allowed_decision_kinds": allowed_decisions,
        "frontier_decision_kind_allowed": proposal.decision_kind in allowed_decisions,
        "tool_registered": tool_registered,
        "decision_tool_effective": decision_tool_effective,
        "selected_node_in_ready_frontier": selected_node_in_ready,
        "selected_node_resolved": selected_node_resolved,
        "operator_available": operator_available,
        "operand_sources_exact": operand_sources_exact,
        "evidence_available": evidence_available,
        "required_tool_fields_present": required_present,
        "additional_tool_fields_allowed": additional_allowed,
        "missing_tool_fields": missing,
        "unexpected_tool_fields": extra,
        "expected_operand_sources": expected_operand_sources,
    }


def _same_public_call(left: Any, right: Any) -> bool:
    return left.tool_id == right.tool_id and left.arguments == right.arguments


def _proposal_outcome(
    *,
    commit_observed: bool,
    duplicate_failed_public_call: bool,
    compile_error: str | None,
) -> ProposalOutcome:
    if commit_observed:
        if compile_error is not None:
            raise ValueError("v26.116 observed Commit failed independent compilation")
        return "committed"
    if duplicate_failed_public_call:
        if compile_error is not None:
            raise ValueError("v26.116 duplicate public call failed independent compilation")
        return "duplicate_failed_public_call"
    mapping: dict[str, ProposalOutcome] = {
        "compiled public call violates the exposed tool grammar": ("compile_rejected_tool_grammar"),
        "semantic proposal selects an unresolved public Operation": (
            "compile_rejected_unresolved_operation"
        ),
        "semantic proposal changes registered public operand sources": (
            "compile_rejected_operand_grounding"
        ),
    }
    if compile_error not in mapping:
        raise ValueError(f"v26.116 unregistered Proposal outcome: {compile_error}")
    return mapping[compile_error]


def _build_diagnostics(
    loaded: LoadedEvidence,
    *,
    package_root: Path,
    implementation_root: Path,
) -> ProposalDiagnosticSet:
    static, _ = load_exact_grammar_static_inputs(package_root, implementation_root)
    rows: list[ProposalDiagnostic] = []
    for raw in sorted(loaded.raws, key=lambda item: item.job.job_id):
        binding = two_stage_runtime_binding(static, raw.job)
        artifacts = {
            item.provider_call_index: item
            for item in (
                loaded.providers_by_relative_path[descriptor.relative_path]
                for descriptor in raw.provider_call_artifacts
            )
        }
        commit_rows = {
            item.proposal.proposal_id: (index, item) for index, item in enumerate(raw.commits)
        }
        for attempt in raw.attempts:
            if attempt.disposition != "usable":
                continue
            if not attempt.provider_call_made or attempt.provider_call_index is None:
                raise ValueError("v26.116 usable attempt lacks a Provider artifact")
            artifact = artifacts[attempt.provider_call_index]
            if artifact.response_payload is None:
                raise ValueError("v26.116 usable attempt lacks a public payload")
            observations_before = raw.observations[: attempt.logical_request_index]
            state = build_public_action_state(
                binding.record.task_package.task.public,
                binding.environment,
                observations_before,
            )
            if state.state_id != artifact.dynamic_certificate.public_state_id:
                raise ValueError("v26.116 dynamic state reconstruction changed")
            proposal = parse_exact_semantic_proposal_payload(
                artifact.response_payload,
                expected_state=state,
            )
            commit_row = commit_rows.get(proposal.proposal_id)
            observed_commit = commit_row is not None
            observation = None
            if commit_row is not None:
                commit_index, raw_commit = commit_row
                if (
                    raw_commit.logical_request_index != attempt.logical_request_index
                    or _semantic_projection(raw_commit.proposal) != _semantic_projection(proposal)
                ):
                    raise ValueError("v26.116 accepted Proposal and Commit binding changed")
                observation = raw.observations[commit_index]
            compilation = None
            compile_error = None
            try:
                compilation = compile_semantic_decision(
                    state,
                    proposal,
                    call_index=attempt.logical_request_index + 1,
                )
            except ValueError as exc:
                compile_error = str(exc)
            if observed_commit:
                assert commit_row is not None
                if compilation != commit_row[1].commit:
                    raise ValueError("v26.116 independent Commit compilation changed")
            prior_failed_observation = next(
                (
                    item
                    for item in reversed(observations_before)
                    if compilation is not None
                    and compilation.call is not None
                    and item.status == "failed"
                    and _same_public_call(item.call, compilation.call)
                ),
                None,
            )
            duplicate = bool(not observed_commit and prior_failed_observation is not None)
            outcome = _proposal_outcome(
                commit_observed=observed_commit,
                duplicate_failed_public_call=duplicate,
                compile_error=compile_error,
            )
            if outcome.startswith("compile_rejected") and raw.execution_error != compile_error:
                raise ValueError("v26.116 compile rejection and Raw terminal differ")
            state_after = None
            if observation is not None:
                state_after = build_public_action_state(
                    binding.record.task_package.task.public,
                    binding.environment,
                    observations_before + (observation,),
                )
            shape = _diagnostic_values(state=state, proposal=proposal)
            values: dict[str, Any] = {
                "job_id": raw.job.job_id,
                "mechanism_id": raw.job.mechanism_id,
                "path_strategy_id": raw.job.path_strategy_id,
                "provider_artifact_id": artifact.artifact_id,
                "provider_call_index": artifact.provider_call_index,
                "logical_request_index": attempt.logical_request_index,
                "phase": attempt.phase,
                "state_id": state.state_id,
                "decision_kind": proposal.decision_kind,
                "tool_id": proposal.tool_id,
                "node_id": proposal.node_id,
                "operator_id": proposal.operator_id,
                "operand_sources": proposal.operand_sources,
                "direct_argument_fields": tuple(sorted((proposal.direct_arguments or {}).keys())),
                "evidence_id_count": len(proposal.evidence_ids),
                "unresolved_symbol_count_before": len(state.unresolved_symbols),
                "unresolved_symbol_count_after": (
                    len(state_after.unresolved_symbols) if state_after is not None else None
                ),
                "ready_operation_count": len(state.ready_operations),
                "executable_operation_count": sum(
                    not item.unresolved_symbols for item in state.ready_operations
                ),
                **shape,
                "independent_compile_passed": compilation is not None,
                "commit_observed": observed_commit,
                "duplicate_failed_public_call": duplicate,
                "prior_failed_observation_error_code": (
                    prior_failed_observation.error_code
                    if prior_failed_observation is not None
                    else None
                ),
                "observation_status": observation.status if observation is not None else None,
                "observation_error_code": (
                    observation.error_code if observation is not None else None
                ),
                "outcome": outcome,
            }
            provisional = ProposalDiagnostic.model_construct(diagnostic_id="pending", **values)
            rows.append(
                ProposalDiagnostic(
                    diagnostic_id=_identity(
                        provisional,
                        "diagnostic_id",
                        "finance_v26_semantic_proposal_diagnostic:",
                    ),
                    **values,
                )
            )
    ordered = tuple(
        sorted(
            rows,
            key=lambda item: (item.job_id, item.provider_call_index, item.diagnostic_id),
        )
    )
    if len(ordered) != 54:
        raise ValueError("v26.116 accepted Proposal denominator changed")
    values = {
        "provider_payload_denominator": len(loaded.providers),
        "exact_abi_accepted_count": len(ordered),
        "diagnostic_count": len(ordered),
        "unique_diagnostic_id_count": len({item.diagnostic_id for item in ordered}),
        "dynamic_state_reconstruction_pass_count": len(ordered),
        "exact_state_binding_pass_count": len(ordered),
        "diagnostics": ordered,
    }
    provisional_set = ProposalDiagnosticSet.model_construct(audit_id="pending", **values)
    return ProposalDiagnosticSet(
        audit_id=_identity(
            provisional_set,
            "audit_id",
            "finance_v26_semantic_proposal_diagnostic_set:",
        ),
        **values,
    )


def _fraction(numerator: int, denominator: int) -> str:
    return format(Decimal(numerator) / Decimal(denominator), ".12f")


def _build_distribution(
    diagnostics: ProposalDiagnosticSet,
) -> SemanticProposalDistributionAudit:
    rows = diagnostics.diagnostics
    decisions = Counter(item.decision_kind for item in rows)
    committed = Counter(item.decision_kind for item in rows if item.commit_observed)
    values: dict[str, Any] = {
        "provider_payload_count": diagnostics.provider_payload_denominator,
        "exact_abi_accepted_count": len(rows),
        "exact_abi_acceptance_fraction": _fraction(
            len(rows), diagnostics.provider_payload_denominator
        ),
        "accepted_decision_kind_counts": dict(sorted(decisions.items())),
        "accepted_tool_counts": dict(sorted(Counter(str(item.tool_id) for item in rows).items())),
        "accepted_phase_counts": dict(sorted(Counter(item.phase for item in rows).items())),
        "accepted_logical_request_index_counts": dict(
            sorted(Counter(str(item.logical_request_index) for item in rows).items())
        ),
        "committed_count": sum(committed.values()),
        "accepted_to_commit_fraction": _fraction(sum(committed.values()), len(rows)),
        "committed_decision_kind_counts": dict(sorted(committed.items())),
        "decision_kind_commit_fractions": {
            key: _fraction(committed[key], count) for key, count in sorted(decisions.items())
        },
        "outcome_counts": dict(
            sorted(
                Counter(
                    item.outcome.replace("compile_rejected", "commit_rejected") for item in rows
                ).items()
            )
        ),
        "accepted_by_mechanism": dict(sorted(Counter(item.mechanism_id for item in rows).items())),
        "committed_by_mechanism": dict(
            sorted(Counter(item.mechanism_id for item in rows if item.commit_observed).items())
        ),
        "accepted_by_path_strategy": dict(
            sorted(Counter(item.path_strategy_id for item in rows).items())
        ),
        "committed_by_path_strategy": dict(
            sorted(Counter(item.path_strategy_id for item in rows if item.commit_observed).items())
        ),
        "verify_terminal_proposal_count": decisions["verify_terminal_operation"],
        "emit_final_proposal_count": decisions["emit_final_answer"],
    }
    provisional = SemanticProposalDistributionAudit.model_construct(audit_id="pending", **values)
    return SemanticProposalDistributionAudit(
        audit_id=_identity(provisional, "audit_id", "finance_v26_semantic_proposal_distribution:"),
        **values,
    )


def _signature(values: Sequence[str]) -> str:
    return json.dumps(list(values), ensure_ascii=False, separators=(",", ":"))


def _build_failure_audit(
    diagnostics: ProposalDiagnosticSet,
) -> ActionSelectionFailureAudit:
    failed = tuple(item for item in diagnostics.diagnostics if not item.commit_observed)
    dimension_by_outcome = {
        "compile_rejected_tool_grammar": "tool_argument_grammar",
        "compile_rejected_unresolved_operation": "public_state_frontier",
        "compile_rejected_operand_grounding": "operand_grounding",
        "duplicate_failed_public_call": "duplicate_failed_public_call",
    }
    if any(item.outcome not in dimension_by_outcome for item in failed):
        raise ValueError("v26.116 unregistered uncommitted Proposal outcome")
    tool_grammar = tuple(item for item in failed if item.outcome == "compile_rejected_tool_grammar")
    unresolved = tuple(
        item for item in failed if item.outcome == "compile_rejected_unresolved_operation"
    )
    operands = tuple(
        item for item in failed if item.outcome == "compile_rejected_operand_grounding"
    )
    duplicates = tuple(item for item in failed if item.outcome == "duplicate_failed_public_call")
    values: dict[str, Any] = {
        "accepted_without_commit_count": len(failed),
        "failure_dimension_counts": dict(
            sorted(Counter(dimension_by_outcome[item.outcome] for item in failed).items())
        ),
        "failure_decision_kind_counts": dict(
            sorted(Counter(item.decision_kind for item in failed).items())
        ),
        "tool_grammar_missing_field_signatures": dict(
            sorted(Counter(_signature(item.missing_tool_fields) for item in tool_grammar).items())
        ),
        "tool_grammar_unexpected_field_signatures": dict(
            sorted(
                Counter(_signature(item.unexpected_tool_fields) for item in tool_grammar).items()
            )
        ),
        "unresolved_operation_node_counts": dict(
            sorted(Counter(str(item.node_id) for item in unresolved).items())
        ),
        "operand_source_mismatch_signatures": dict(
            sorted(
                Counter(
                    f"expected={_signature(item.expected_operand_sources)};"
                    f"proposed={_signature(item.operand_sources)}"
                    for item in operands
                ).items()
            )
        ),
        "duplicate_prior_error_counts": dict(
            sorted(
                Counter(
                    str(item.prior_failed_observation_error_code) for item in duplicates
                ).items()
            )
        ),
        "tool_not_registered_count": sum(item.tool_registered is False for item in failed),
        "ineffective_decision_tool_count": sum(
            item.decision_tool_effective is False for item in failed
        ),
        "node_not_in_ready_frontier_count": sum(
            item.selected_node_in_ready_frontier is False for item in failed
        ),
        "unavailable_operator_count": sum(item.operator_available is False for item in failed),
        "unavailable_evidence_count": sum(item.evidence_available is False for item in failed),
        "unresolved_operation_frontier_count": len(unresolved),
        "operand_grounding_mismatch_count": len(operands),
        "tool_grammar_mismatch_count": len(tool_grammar),
        "duplicate_failed_public_call_count": len(duplicates),
    }
    if len(failed) != 24:
        raise ValueError("v26.116 accepted-without-Commit denominator changed")
    provisional = ActionSelectionFailureAudit.model_construct(audit_id="pending", **values)
    return ActionSelectionFailureAudit(
        audit_id=_identity(provisional, "audit_id", "finance_v26_action_selection_failure:"),
        **values,
    )


def _build_progression(
    diagnostics: ProposalDiagnosticSet,
    loaded: LoadedEvidence,
) -> TrajectoryProgressionAudit:
    rows = diagnostics.diagnostics
    accepted_jobs = {item.job_id for item in rows}
    committed_rows = tuple(item for item in rows if item.commit_observed)
    committed_jobs = {item.job_id for item in committed_rows}
    successful_rows = tuple(
        item for item in committed_rows if item.observation_status == "succeeded"
    )
    successful_jobs = {item.job_id for item in successful_rows}
    commit_counts = Counter(len(raw.commits) for raw in loaded.raws)
    values: dict[str, Any] = {
        "jobs_with_accepted_proposal": len(accepted_jobs),
        "jobs_with_commit": len(committed_jobs),
        "jobs_with_successful_observation": len(successful_jobs),
        "jobs_with_two_or_more_commits": sum(len(raw.commits) >= 2 for raw in loaded.raws),
        "maximum_commits_per_job": max(len(raw.commits) for raw in loaded.raws),
        "commit_count_distribution": {
            str(key): value for key, value in sorted(commit_counts.items())
        },
        "terminal_failure_type_counts": dict(
            sorted(Counter(str(raw.terminal_failure_type) for raw in loaded.raws).items())
        ),
        "committed_logical_request_index_counts": dict(
            sorted(Counter(str(item.logical_request_index) for item in committed_rows).items())
        ),
        "successful_observation_logical_request_index_counts": dict(
            sorted(Counter(str(item.logical_request_index) for item in successful_rows).items())
        ),
        "committed_acquisition_count": sum(
            item.decision_kind == "acquire_public_input" for item in committed_rows
        ),
        "successful_acquisition_count": sum(
            item.decision_kind == "acquire_public_input" and item.observation_status == "succeeded"
            for item in committed_rows
        ),
        "successful_acquisition_reduced_unresolved_symbols_count": sum(
            item.decision_kind == "acquire_public_input"
            and item.observation_status == "succeeded"
            and item.unresolved_symbol_count_after is not None
            and item.unresolved_symbol_count_after < item.unresolved_symbol_count_before
            for item in committed_rows
        ),
        "committed_operation_count": sum(
            item.decision_kind == "execute_public_operation" for item in committed_rows
        ),
        "successful_operation_count": sum(
            item.decision_kind == "execute_public_operation"
            and item.observation_status == "succeeded"
            for item in committed_rows
        ),
        "committed_verification_count": sum(
            item.decision_kind == "verify_terminal_operation" for item in committed_rows
        ),
        "emitted_final_count": sum(
            item.decision_kind == "emit_final_answer" for item in committed_rows
        ),
        "program_closed_count": sum(item.program_closed for item in loaded.results),
        "independently_valid_count": sum(item.independent_validity for item in loaded.results),
        "stage_two_provider_call_count": sum(
            raw.stage_two_provider_call_count for raw in loaded.raws
        ),
    }
    provisional = TrajectoryProgressionAudit.model_construct(audit_id="pending", **values)
    return TrajectoryProgressionAudit(
        audit_id=_identity(provisional, "audit_id", "finance_v26_trajectory_progression:"),
        **values,
    )


def _build_transition() -> ProspectiveTransitionContract:
    provisional = ProspectiveTransitionContract.model_construct(contract_id="pending")
    return ProspectiveTransitionContract(
        contract_id=_identity(
            provisional,
            "contract_id",
            "finance_v26_semantic_action_selection_transition:",
        )
    )


def _audit_gate(values: Mapping[str, Any]) -> None:
    expected = {
        "source_replay_count": 2181,
        "diagnostic_count": 54,
        "accepted_acquisition_count": 42,
        "accepted_operation_count": 12,
        "commit_count": 30,
        "committed_acquisition_count": 29,
        "committed_operation_count": 1,
        "tool_grammar_failure_count": 10,
        "frontier_failure_count": 7,
        "operand_failure_count": 4,
        "duplicate_failure_count": 3,
        "tool_selection_failure_count": 0,
        "node_selection_failure_count": 0,
        "operator_failure_count": 0,
        "evidence_failure_count": 0,
        "verification_proposal_count": 0,
        "final_proposal_count": 0,
        "program_closed_count": 0,
        "independently_valid_count": 0,
        "provider_calls_authorized": False,
        "next_permitted_stage": NEXT_STAGE,
    }
    if dict(values) != expected:
        raise ValueError("v26.116 destructive control changed a frozen audit Gate")


def _build_destructive(
    source: SemanticAuditSourceReplay,
    diagnostics: ProposalDiagnosticSet,
    distribution: SemanticProposalDistributionAudit,
    failures: ActionSelectionFailureAudit,
    progression: TrajectoryProgressionAudit,
    transition: ProspectiveTransitionContract,
) -> DestructiveAudit:
    baseline: dict[str, Any] = {
        "source_replay_count": source.replayed_file_count,
        "diagnostic_count": diagnostics.diagnostic_count,
        "accepted_acquisition_count": distribution.accepted_decision_kind_counts[
            "acquire_public_input"
        ],
        "accepted_operation_count": distribution.accepted_decision_kind_counts[
            "execute_public_operation"
        ],
        "commit_count": distribution.committed_count,
        "committed_acquisition_count": distribution.committed_decision_kind_counts[
            "acquire_public_input"
        ],
        "committed_operation_count": distribution.committed_decision_kind_counts[
            "execute_public_operation"
        ],
        "tool_grammar_failure_count": failures.tool_grammar_mismatch_count,
        "frontier_failure_count": failures.unresolved_operation_frontier_count,
        "operand_failure_count": failures.operand_grounding_mismatch_count,
        "duplicate_failure_count": failures.duplicate_failed_public_call_count,
        "tool_selection_failure_count": failures.tool_not_registered_count,
        "node_selection_failure_count": failures.node_not_in_ready_frontier_count,
        "operator_failure_count": failures.unavailable_operator_count,
        "evidence_failure_count": failures.unavailable_evidence_count,
        "verification_proposal_count": distribution.verify_terminal_proposal_count,
        "final_proposal_count": distribution.emit_final_proposal_count,
        "program_closed_count": progression.program_closed_count,
        "independently_valid_count": progression.independently_valid_count,
        "provider_calls_authorized": transition.provider_calls_authorized,
        "next_permitted_stage": transition.next_permitted_stage,
    }
    _audit_gate(baseline)
    mutations: list[MutationResult] = []
    for name, current in baseline.items():
        mutated = dict(baseline)
        if isinstance(current, bool):
            mutated[name] = not current
        elif isinstance(current, int):
            mutated[name] = current + 1
        else:
            mutated[name] = f"{current}.mutated"
        try:
            _audit_gate(mutated)
        except ValueError:
            mutations.append(MutationResult(name=f"changed_{name}"))
        else:
            raise ValueError(f"v26.116 destructive mutation passed: {name}")
    values: dict[str, Any] = {"mutations": tuple(mutations)}
    provisional = DestructiveAudit.model_construct(audit_id="pending", **values)
    return DestructiveAudit(
        audit_id=_identity(
            provisional,
            "audit_id",
            "finance_v26_semantic_distribution_destructive:",
        ),
        **values,
    )


def _detail(path: Path, output_dir: Path) -> DetailFile:
    return DetailFile(
        relative_path=str(path.relative_to(output_dir)),
        sha256=sha256_file(path),
        byte_count=path.stat().st_size,
    )


def build(
    *,
    package_root: Path,
    implementation_root: Path,
    execution_dir: Path,
    predecessor_audit_dir: Path,
    output_dir: Path,
) -> SemanticProposalAuditReport:
    source, predecessor = _build_source_replay(
        package_root=package_root,
        implementation_root=implementation_root,
        predecessor_audit_dir=predecessor_audit_dir,
    )
    loaded = _load_evidence(
        execution_dir=execution_dir,
        predecessor_report=predecessor,
    )
    diagnostics = _build_diagnostics(
        loaded,
        package_root=package_root,
        implementation_root=implementation_root,
    )
    distribution = _build_distribution(diagnostics)
    failures = _build_failure_audit(diagnostics)
    progression = _build_progression(diagnostics, loaded)
    transition = _build_transition()
    destructive = _build_destructive(
        source,
        diagnostics,
        distribution,
        failures,
        progression,
        transition,
    )
    outputs: tuple[tuple[str, BaseModel], ...] = (
        ("source_replay_audit.json", source),
        ("proposal_diagnostics.json", diagnostics),
        ("semantic_proposal_distribution_audit.json", distribution),
        ("action_selection_failure_audit.json", failures),
        ("trajectory_progression_audit.json", progression),
        ("prospective_transition_contract.json", transition),
        ("destructive_audit.json", destructive),
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    for name, value in outputs:
        _write_json(output_dir / name, value.model_dump(mode="json"))
    details = tuple(_detail(output_dir / name, output_dir) for name, _ in outputs)
    values: dict[str, Any] = {
        "source_replay_audit_id": source.audit_id,
        "proposal_diagnostic_set_id": diagnostics.audit_id,
        "distribution_audit_id": distribution.audit_id,
        "action_selection_failure_audit_id": failures.audit_id,
        "trajectory_progression_audit_id": progression.audit_id,
        "transition_contract_id": transition.contract_id,
        "destructive_audit_id": destructive.audit_id,
        "detail_files": details,
        "exact_job_denominator": len(loaded.results),
        "exact_abi_accepted_count": diagnostics.exact_abi_accepted_count,
        "semantic_commit_count": distribution.committed_count,
        "accepted_without_commit_count": failures.accepted_without_commit_count,
        "program_closed_count": progression.program_closed_count,
        "independently_valid_count": progression.independently_valid_count,
        "stage_two_provider_calls": progression.stage_two_provider_call_count,
    }
    provisional = SemanticProposalAuditReport.model_construct(report_id="pending", **values)
    report = SemanticProposalAuditReport(
        report_id=_identity(
            provisional, "report_id", "finance_v26_semantic_proposal_audit_report:"
        ),
        **values,
    )
    _write_json(output_dir / "report.json", report.model_dump(mode="json"))
    return report


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Independently audit v26.114 Semantic Proposal action selection"
    )
    parser.add_argument("--package-root", type=Path, default=Path(__file__).resolve().parents[4])
    parser.add_argument(
        "--implementation-root",
        type=Path,
        default=Path(__file__).resolve().parents[4],
    )
    parser.add_argument("--execution-dir", type=Path, default=Path(EXECUTION_DIR))
    parser.add_argument(
        "--predecessor-audit-dir",
        type=Path,
        default=Path(PREDECESSOR_AUDIT_DIR),
    )
    parser.add_argument("--output-dir", type=Path, default=Path(OUTPUT_DIR))
    args = parser.parse_args()
    report = build(
        package_root=args.package_root,
        implementation_root=args.implementation_root,
        execution_dir=args.execution_dir,
        predecessor_audit_dir=args.predecessor_audit_dir,
        output_dir=args.output_dir,
    )
    print(report.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
