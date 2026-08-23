from __future__ import annotations

import argparse
import inspect
import json
from collections import Counter
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.core.task.schema import TaskPublicSpec
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_action_constructibility_two_stage_preflight import (  # noqa: E501
    _path_binding,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_exact_response_grammar_execution import (  # noqa: E501
    load_exact_grammar_static_inputs,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_semantic_proposal_distribution_audit import (  # noqa: E501
    SemanticAuditSourceReplay,
    SemanticProposalAuditReport,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_two_stage_semantic_proposal_execution import (  # noqa: E501
    sha256_file,
)
from trusted_synthesis.hashing import canonical_hash
from trusted_synthesis.runtime.agent.prospective_semantic_action_protocol import (
    ABI_RESCUE_LIMIT,
    SEMANTIC_ACTION_PROTOCOL_VERSION,
    SEMANTIC_RECOVERY_LIMIT,
    CanonicalActionCommit,
    CanonicalActionProposal,
    CanonicalPublicAction,
    PublicSemanticRejectionObservation,
    RecoveryChannelAccounting,
    SemanticActionState,
    accepted_action_ids,
    build_semantic_action_state,
    decompile_canonical_public_call,
    evaluate_canonical_action_proposal,
    make_canonical_action_proposal,
    prompt_only_reference_proposal,
    render_semantic_action_prompt,
)
from trusted_synthesis.runtime.tools import (
    AgentToolCall,
    AgentToolEnvironmentManifest,
    AgentToolObservation,
)

RUN_ID: Final = "finance_v26_117_semantic_action_protocol_preflight_v1_20260823"
PREDECESSOR_DIR: Final = (
    "artifacts/vtdo_experiment/finance_v26_116_semantic_proposal_distribution_audit_v1_20260823"
)
OUTPUT_DIR: Final = (
    "artifacts/vtdo_experiment/finance_v26_117_semantic_action_protocol_preflight_v1_20260823"
)
IMPLEMENTATION_PATH: Final = (
    "src/trusted_synthesis/experiments/vtdo_experiment/"
    "phase1_v26_semantic_action_protocol_preflight.py"
)
RUNTIME_PATH: Final = "src/trusted_synthesis/runtime/agent/prospective_semantic_action_protocol.py"
EXPECTED_PREDECESSOR_REPORT_ID: Final = (
    "finance_v26_semantic_proposal_audit_report:"
    "fe7abe69942f51ed79ce1eddf62878a5f68f8e9f68f85328f45b12f2db85d171"
)
EXPECTED_PREDECESSOR_TRANSITION_ID: Final = (
    "finance_v26_semantic_action_selection_transition:"
    "82a944e8a123794a7add9a6615a4bdc44a985d363edb846f6ce20319fb3e7159"
)
NEXT_STAGE: Final = (
    "fresh_semantic_action_protocol_taskpackage_contract_manifest_and_runner_preflight_only"
)


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


def _identity(value: BaseModel, field: str, prefix: str) -> str:
    payload = value.model_dump(mode="json")
    payload.pop(field, None)
    return canonical_hash(payload, prefix=prefix)


class SourceReplayEntry(FrozenModel):
    relative_path: str = Field(min_length=1)
    source_kind: str = Field(min_length=1)
    expected_sha256: str = Field(min_length=64, max_length=64)
    observed_sha256: str = Field(min_length=64, max_length=64)
    byte_count: int = Field(gt=0)
    passed: Literal[True] = True


class SemanticActionSourceReplay(FrozenModel):
    audit_id: str = Field(min_length=1)
    predecessor_source_replay_id: str = Field(min_length=1)
    predecessor_report_id: Literal[
        "finance_v26_semantic_proposal_audit_report:"
        "fe7abe69942f51ed79ce1eddf62878a5f68f8e9f68f85328f45b12f2db85d171"
    ] = EXPECTED_PREDECESSOR_REPORT_ID
    predecessor_transitive_file_count: Literal[2181] = 2181
    predecessor_output_file_count: Literal[8] = 8
    implementation_file_count: Literal[2] = 2
    replayed_file_count: Literal[2191] = 2191
    replay_pass_count: Literal[2191] = 2191
    entries: tuple[SourceReplayEntry, ...] = Field(min_length=2191, max_length=2191)
    replay_before_protocol_construction: Literal[True] = True
    credential_lookup_attempted: Literal[False] = False
    model_client_constructed: Literal[False] = False
    provider_calls: Literal[0] = 0
    gpu_jobs: Literal[0] = 0
    status: Literal["passed"] = "passed"
    schema_version: Literal["finance_v26_semantic_action_source_replay.v1"] = (
        "finance_v26_semantic_action_source_replay.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> SemanticActionSourceReplay:
        paths = tuple(item.relative_path for item in self.entries)
        if paths != tuple(sorted(paths)) or len(set(paths)) != 2191:
            raise ValueError("v26.117 source replay paths are not canonical and unique")
        if any(item.expected_sha256 != item.observed_sha256 for item in self.entries):
            raise ValueError("v26.117 source replay contains a hash mismatch")
        if self.audit_id != _identity(
            self, "audit_id", "finance_v26_semantic_action_source_replay:"
        ):
            raise ValueError("v26.117 source replay identity changed")
        return self


class SemanticActionProtocolContract(FrozenModel):
    protocol_id: str = Field(min_length=1)
    predecessor_transition_contract_id: str = EXPECTED_PREDECESSOR_TRANSITION_ID
    protocol_version: str = SEMANTIC_ACTION_PROTOCOL_VERSION
    canonical_model_selectable_object: Literal["content_addressed_action_id"] = (
        "content_addressed_action_id"
    )
    semantic_proposal_fields: tuple[str, ...] = (
        "action_id",
        "decision_kind",
        "protocol",
        "state_id",
    )
    acquisition_argument_generation_removed_from_model: Literal[True] = True
    operation_frontier_statuses: tuple[str, ...] = (
        "blocked_dependencies",
        "dependency_ready",
        "executable",
        "terminal_verifiable",
    )
    execute_operation_selectable_status: Literal["executable"] = "executable"
    canonical_source_reference_required: Literal[True] = True
    current_visible_state_and_proposal_are_acceptance_sufficient: Literal[True] = True
    semantic_rejection_is_typed_public_observation: Literal[True] = True
    semantic_rejection_is_immediate_job_terminal: Literal[False] = False
    abi_rescue_limit: Literal[1] = ABI_RESCUE_LIMIT
    semantic_recovery_limit: Literal[1] = SEMANTIC_RECOVERY_LIMIT
    abi_and_semantic_recovery_counters_separate: Literal[True] = True
    stage_two_provider_calls: Literal[0] = 0
    stage_two_selects_or_repairs_semantics: Literal[False] = False
    outcome_measures: tuple[str, ...] = (
        "first_proposal_legal",
        "eventual_legal_within_bound",
        "public_progress_after_commit",
        "final_valid_trajectory",
    )
    outcome_measures_are_not_equated: Literal[True] = True
    v26_116_failure_counts_used_to_set_limits_or_thresholds: Literal[False] = False
    outer_response_abi_or_stage_metadata_changed: Literal[False] = False
    provider_calls_authorized: Literal[False] = False
    schema_version: Literal["finance_v26_semantic_action_protocol_contract.v1"] = (
        "finance_v26_semantic_action_protocol_contract.v1"
    )

    @model_validator(mode="after")
    def validate_contract(self) -> SemanticActionProtocolContract:
        if self.protocol_id != _identity(
            self, "protocol_id", "finance_v26_semantic_action_protocol:"
        ):
            raise ValueError("v26.117 semantic action protocol identity changed")
        return self


class CanonicalActionLanguageAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    protocol_id: str = Field(min_length=1)
    compiler_path_count: Literal[48] = 48
    public_decision_state_count: Literal[324] = 324
    public_tool_call_count: Literal[276] = 276
    final_decision_count: Literal[48] = 48
    decision_kind_counts: dict[str, int]
    acquisition_mode_counts: dict[str, int]
    acquisition_tool_counts: dict[str, int]
    unique_public_state_count: int = Field(gt=0)
    unique_action_id_count: int = Field(gt=0)
    unique_source_reference_id_count: int = Field(gt=0)
    unique_document_reference_id_count: int = Field(ge=0)
    acquisition_reversible_compilation_count: Literal[156] = 156
    operation_reversible_compilation_count: Literal[72] = 72
    verification_reversible_compilation_count: Literal[48] = 48
    final_reversible_compilation_count: Literal[48] = 48
    complete_reversible_compilation_count: Literal[324] = 324
    visible_candidate_acceptance_equality_state_count: Literal[324] = 324
    model_generated_direct_argument_object_count: Literal[0] = 0
    one_public_object_one_canonical_identifier_passed: Literal[True] = True
    status: Literal["passed"] = "passed"
    schema_version: Literal["finance_v26_canonical_action_language_audit.v1"] = (
        "finance_v26_canonical_action_language_audit.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> CanonicalActionLanguageAudit:
        if self.decision_kind_counts != {
            "acquire_public_input": 156,
            "emit_final_answer": 48,
            "execute_public_operation": 72,
            "verify_terminal_operation": 48,
        }:
            raise ValueError("v26.117 canonical Decision distribution changed")
        if self.acquisition_tool_counts != {
            "open_document": 21,
            "query_structured_fact": 87,
            "search_archive": 48,
        }:
            raise ValueError("v26.117 acquisition Tool distribution changed")
        if self.audit_id != _identity(self, "audit_id", "finance_v26_canonical_action_language:"):
            raise ValueError("v26.117 canonical action-language identity changed")
        return self


class OperationFrontierAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    public_state_count: Literal[324] = 324
    frontier_row_counts: dict[str, int]
    state_counts_with_status: dict[str, int]
    operation_candidate_count: int = Field(gt=0)
    candidates_from_executable_count: int = Field(gt=0)
    candidates_from_blocked_dependencies_count: Literal[0] = 0
    candidates_from_dependency_ready_count: Literal[0] = 0
    candidates_from_terminal_verifiable_count: Literal[0] = 0
    validator_visible_candidate_mismatch_count: Literal[0] = 0
    unresolved_ready_alias_used: Literal[False] = False
    status: Literal["passed"] = "passed"
    schema_version: Literal["finance_v26_operation_frontier_audit.v1"] = (
        "finance_v26_operation_frontier_audit.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> OperationFrontierAudit:
        if not {
            "blocked_dependencies",
            "dependency_ready",
            "executable",
            "terminal_verifiable",
        } <= set(self.frontier_row_counts):
            raise ValueError("v26.117 did not exercise every Operation frontier partition")
        if self.operation_candidate_count != self.candidates_from_executable_count:
            raise ValueError("v26.117 Operation candidate frontier changed")
        if self.audit_id != _identity(self, "audit_id", "finance_v26_operation_frontier_audit:"):
            raise ValueError("v26.117 Operation-frontier identity changed")
        return self


class PromptOnlyPathControl(FrozenModel):
    audit_id: str = Field(min_length=1)
    path_count: Literal[48] = 48
    serialized_prompt_count: Literal[324] = 324
    prompt_parse_count: Literal[324] = 324
    prompt_only_proposal_count: Literal[324] = 324
    exact_compiler_call_match_count: Literal[276] = 276
    exact_final_ready_count: Literal[48] = 48
    exact_path_completion_count: Literal[48] = 48
    path_strategy_counts: dict[str, int]
    typed_runtime_refinement_count: Literal[12] = 12
    maximum_prompt_utf8_bytes: int = Field(gt=0)
    parser_schema_read_count: Literal[0] = 0
    internal_proposal_read_count: Literal[0] = 0
    oracle_or_expected_argument_read_count: Literal[0] = 0
    final_serialized_prompt_only: Literal[True] = True
    status: Literal["passed"] = "passed"
    schema_version: Literal["finance_v26_prompt_only_path_control.v1"] = (
        "finance_v26_prompt_only_path_control.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> PromptOnlyPathControl:
        if self.path_strategy_counts != {
            "search_then_open": 12,
            "search_then_structured": 12,
            "structured_direct": 24,
        }:
            raise ValueError("v26.117 path-strategy denominator changed")
        if self.audit_id != _identity(self, "audit_id", "finance_v26_prompt_only_path_control:"):
            raise ValueError("v26.117 Prompt-only path identity changed")
        return self


class SemanticRecoveryContinuityAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    typed_runtime_failure_count_in_48_paths: Literal[12] = 12
    typed_runtime_failure_visible_block_count: Literal[12] = 12
    hidden_historical_failure_lookup_count: Literal[0] = 0
    semantic_rejection_fixture_count: Literal[1] = 1
    typed_neutral_rejection_count: Literal[1] = 1
    rejection_immediate_job_terminal_count: Literal[0] = 0
    recovery_state_rebuild_count: Literal[1] = 1
    recovery_prompt_parse_count: Literal[1] = 1
    recovery_commit_count: Literal[1] = 1
    recovery_exact_next_call_match_count: Literal[1] = 1
    abi_rescue_count_before_semantic_rejection: Literal[1] = 1
    abi_rescue_count_after_semantic_rejection: Literal[1] = 1
    semantic_recovery_count_before: Literal[0] = 0
    semantic_recovery_count_after: Literal[1] = 1
    exact_failed_argument_values_retained: Literal[0] = 0
    correct_tool_node_operator_operand_evidence_exposed: Literal[0] = 0
    semantic_rejection_and_abi_rescue_separate: Literal[True] = True
    status: Literal["passed"] = "passed"
    schema_version: Literal["finance_v26_semantic_recovery_continuity_audit.v1"] = (
        "finance_v26_semantic_recovery_continuity_audit.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> SemanticRecoveryContinuityAudit:
        if self.audit_id != _identity(
            self, "audit_id", "finance_v26_semantic_recovery_continuity:"
        ):
            raise ValueError("v26.117 semantic recovery identity changed")
        return self


class StageTwoAuthorityAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    canonical_commit_count: Literal[324] = 324
    tool_call_commit_count: Literal[276] = 276
    final_commit_count: Literal[48] = 48
    reversible_commit_count: Literal[324] = 324
    compiler_selected_tool_count: Literal[0] = 0
    compiler_selected_node_count: Literal[0] = 0
    compiler_selected_operator_count: Literal[0] = 0
    compiler_selected_operand_count: Literal[0] = 0
    compiler_selected_evidence_count: Literal[0] = 0
    compiler_semantic_repair_count: Literal[0] = 0
    stage_two_provider_calls: Literal[0] = 0
    provider_profile_present: Literal[False] = False
    provider_client_route_present: Literal[False] = False
    status: Literal["passed"] = "passed"
    schema_version: Literal["finance_v26_stage_two_authority_audit.v1"] = (
        "finance_v26_stage_two_authority_audit.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> StageTwoAuthorityAudit:
        if self.audit_id != _identity(self, "audit_id", "finance_v26_stage_two_authority_audit:"):
            raise ValueError("v26.117 Stage 2 authority identity changed")
        return self


class MutationResult(FrozenModel):
    name: str = Field(min_length=1)
    rejected: Literal[True] = True
    provider_calls_before_rejection: Literal[0] = 0
    stage_two_provider_calls_before_rejection: Literal[0] = 0


class DestructiveAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    mutation_count: Literal[20] = 20
    rejection_count: Literal[20] = 20
    mutations: tuple[MutationResult, ...] = Field(min_length=20, max_length=20)
    provider_calls: Literal[0] = 0
    stage_two_provider_calls: Literal[0] = 0
    status: Literal["passed"] = "passed"
    schema_version: Literal["finance_v26_semantic_action_destructive_audit.v1"] = (
        "finance_v26_semantic_action_destructive_audit.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> DestructiveAudit:
        names = tuple(item.name for item in self.mutations)
        if names != tuple(sorted(set(names))) or len(names) != 20:
            raise ValueError("v26.117 destructive controls are not canonical and unique")
        if self.audit_id != _identity(self, "audit_id", "finance_v26_semantic_action_destructive:"):
            raise ValueError("v26.117 destructive-audit identity changed")
        return self


class ProspectiveTransitionContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    status: Literal["passed_static_design_preflight"] = "passed_static_design_preflight"
    next_permitted_stage: str = NEXT_STAGE
    fresh_taskpackage_contract_manifest_job_and_runner_identities_required: Literal[True] = True
    exact_credential_free_runner_preflight_required_before_provider_call: Literal[True] = True
    provider_calls_authorized: Literal[False] = False
    historical_v26_114_payload_reparse_authorized: Literal[False] = False
    historical_rerun_recovery_or_reclassification_authorized: Literal[False] = False
    host_semantic_choice_or_repair_authorized: Literal[False] = False
    response_grammar_or_stage_metadata_optimization_authorized: Literal[False] = False
    model_profile_completion_or_rollout_change_authorized: Literal[False] = False
    role_state_training_release_or_production_authorized: Literal[False] = False
    schema_version: Literal["finance_v26_semantic_action_transition.v1"] = (
        "finance_v26_semantic_action_transition.v1"
    )

    @model_validator(mode="after")
    def validate_contract(self) -> ProspectiveTransitionContract:
        if self.contract_id != _identity(
            self, "contract_id", "finance_v26_semantic_action_transition:"
        ):
            raise ValueError("v26.117 transition identity changed")
        return self


class DetailFile(FrozenModel):
    relative_path: str = Field(min_length=1)
    sha256: str = Field(min_length=64, max_length=64)
    byte_count: int = Field(gt=0)


class SemanticActionPreflightReport(FrozenModel):
    report_id: str = Field(min_length=1)
    run_id: Literal["finance_v26_117_semantic_action_protocol_preflight_v1_20260823"] = RUN_ID
    source_replay_audit_id: str = Field(min_length=1)
    protocol_id: str = Field(min_length=1)
    canonical_action_language_audit_id: str = Field(min_length=1)
    operation_frontier_audit_id: str = Field(min_length=1)
    prompt_only_path_control_id: str = Field(min_length=1)
    semantic_recovery_audit_id: str = Field(min_length=1)
    stage_two_authority_audit_id: str = Field(min_length=1)
    destructive_audit_id: str = Field(min_length=1)
    transition_contract_id: str = Field(min_length=1)
    detail_files: tuple[DetailFile, ...] = Field(min_length=9, max_length=9)
    compiler_path_count: Literal[48] = 48
    prompt_only_decision_count: Literal[324] = 324
    reversible_tool_call_count: Literal[276] = 276
    final_ready_count: Literal[48] = 48
    semantic_recovery_fixture_pass_count: Literal[1] = 1
    historical_v26_114_payloads_reparsed: Literal[0] = 0
    historical_empirical_rows_reclassified: Literal[0] = 0
    provider_calls: Literal[0] = 0
    stage_two_provider_calls: Literal[0] = 0
    gpu_jobs: Literal[0] = 0
    empirical_rows: Literal[0] = 0
    next_permitted_stage: str = NEXT_STAGE
    status: Literal["passed_static_design_preflight"] = "passed_static_design_preflight"
    schema_version: Literal["finance_v26_semantic_action_preflight_report.v1"] = (
        "finance_v26_semantic_action_preflight_report.v1"
    )

    @model_validator(mode="after")
    def validate_report(self) -> SemanticActionPreflightReport:
        if self.report_id != _identity(
            self, "report_id", "finance_v26_semantic_action_preflight_report:"
        ):
            raise ValueError("v26.117 report identity changed")
        return self


@dataclass(frozen=True)
class _ControlFixtures:
    states: tuple[SemanticActionState, ...]
    proposals: tuple[CanonicalActionProposal, ...]
    commits: tuple[CanonicalActionCommit, ...]
    blocked_state: SemanticActionState
    blocked_observations: tuple[AgentToolObservation, ...]
    blocked_instruction: str
    blocked_path_condition: str | None
    blocked_expected_call: AgentToolCall
    blocked_task: TaskPublicSpec
    blocked_environment: AgentToolEnvironmentManifest
    dependency_state: SemanticActionState
    later_action_by_id: dict[str, CanonicalPublicAction]


def _load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )


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
    raise ValueError(f"v26.117 cannot replay bound file: {relative_path}")


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
    predecessor_dir: Path,
) -> tuple[SemanticActionSourceReplay, SemanticProposalAuditReport]:
    predecessor_source = SemanticAuditSourceReplay.model_validate(
        _load_json(predecessor_dir / "source_replay_audit.json")
    )
    predecessor_report = SemanticProposalAuditReport.model_validate(
        _load_json(predecessor_dir / "report.json")
    )
    if predecessor_report.report_id != EXPECTED_PREDECESSOR_REPORT_ID:
        raise ValueError("v26.117 predecessor report identity changed")
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
            source_kind="v26_116_transitive_source",
            expected_sha256=item.expected_sha256,
            observed_sha256=sha256_file(path),
            byte_count=path.stat().st_size,
        )
    predecessor_paths = tuple(sorted(path for path in predecessor_dir.iterdir() if path.is_file()))
    if len(predecessor_paths) != 8:
        raise ValueError("v26.117 predecessor output-file denominator changed")
    detail_by_path = {item.relative_path: item for item in predecessor_report.detail_files}
    relative_root = Path(PREDECESSOR_DIR)
    for path in predecessor_paths:
        relative = str(relative_root / path.name)
        if path.name != "report.json":
            detail = detail_by_path.get(path.name)
            if (
                detail is None
                or detail.sha256 != sha256_file(path)
                or detail.byte_count != path.stat().st_size
            ):
                raise ValueError("v26.117 predecessor detail binding changed")
        entries[relative] = _source_entry(path, relative, "v26_116_output")
    for relative in (IMPLEMENTATION_PATH, RUNTIME_PATH):
        path = implementation_root / relative
        entries[relative] = _source_entry(path, relative, "v26_117_implementation")
    ordered = tuple(entries[key] for key in sorted(entries))
    values: dict[str, Any] = {
        "predecessor_source_replay_id": predecessor_source.audit_id,
        "entries": ordered,
    }
    provisional = SemanticActionSourceReplay.model_construct(audit_id="pending", **values)
    return (
        SemanticActionSourceReplay(
            audit_id=_identity(
                provisional,
                "audit_id",
                "finance_v26_semantic_action_source_replay:",
            ),
            **values,
        ),
        predecessor_report,
    )


def _build_protocol(predecessor: SemanticProposalAuditReport) -> SemanticActionProtocolContract:
    if predecessor.transition_contract_id != EXPECTED_PREDECESSOR_TRANSITION_ID:
        raise ValueError("v26.117 predecessor transition identity changed")
    provisional = SemanticActionProtocolContract.model_construct(protocol_id="pending")
    return SemanticActionProtocolContract(
        protocol_id=_identity(provisional, "protocol_id", "finance_v26_semantic_action_protocol:")
    )


def _build_path_controls(
    *,
    package_root: Path,
    implementation_root: Path,
    protocol: SemanticActionProtocolContract,
) -> tuple[
    CanonicalActionLanguageAudit,
    OperationFrontierAudit,
    PromptOnlyPathControl,
    StageTwoAuthorityAudit,
    _ControlFixtures,
]:
    static, _ = load_exact_grammar_static_inputs(package_root, implementation_root)
    historical = static.historical
    if len(historical.path_audits) != 48:
        raise ValueError("v26.117 frozen Compiler path denominator changed")
    states: list[SemanticActionState] = []
    proposals: list[CanonicalActionProposal] = []
    commits: list[CanonicalActionCommit] = []
    state_ids: set[str] = set()
    action_ids: set[str] = set()
    source_reference_ids: set[str] = set()
    document_reference_ids: set[str] = set()
    decision_counts: Counter[str] = Counter()
    acquisition_modes: Counter[str] = Counter()
    acquisition_tools: Counter[str] = Counter()
    frontier_rows: Counter[str] = Counter()
    frontier_states: Counter[str] = Counter()
    path_strategies: Counter[str] = Counter()
    operation_candidates = 0
    acceptance_equal = 0
    exact_call_matches = 0
    final_ready = 0
    typed_refinements = 0
    visible_block_count = 0
    maximum_prompt_bytes = 0
    blocked_fixture: (
        tuple[
            SemanticActionState,
            tuple[AgentToolObservation, ...],
            str,
            str | None,
            AgentToolCall,
            TaskPublicSpec,
            AgentToolEnvironmentManifest,
        ]
        | None
    ) = None
    dependency_state: SemanticActionState | None = None
    later_action_by_id: dict[str, CanonicalPublicAction] = {}
    for exact_path in historical.path_audits:
        binding = _path_binding(historical, exact_path)
        observations: list[AgentToolObservation] = []
        path_condition = (
            None
            if binding.source_path.role == "capability"
            else binding.source_path.path_strategy_id
        )
        path_strategies[path_condition or "structured_direct"] += 1
        for step in binding.compiler_trajectory.steps:
            if step.tool_name is None:
                continue
            state = build_semantic_action_state(
                binding.record.task_package.task.public,
                binding.environment,
                tuple(observations),
            )
            state = SemanticActionState.model_validate_json(state.model_dump_json())
            states.append(state)
            state_ids.add(state.state_id)
            action_ids.update(item.action_id for item in state.action_candidates)
            source_reference_ids.update(item.reference_id for item in state.source_references)
            document_reference_ids.update(item.reference_id for item in state.document_references)
            later_action_by_id.update({item.action_id: item for item in state.action_candidates})
            statuses = {item.frontier_status for item in state.operation_frontier}
            frontier_rows.update(item.frontier_status for item in state.operation_frontier)
            frontier_states.update(statuses)
            if dependency_state is None and "dependency_ready" in statuses:
                dependency_state = state
            operation_candidates += sum(
                item.decision_kind == "execute_public_operation" for item in state.action_candidates
            )
            if accepted_action_ids(state) == tuple(
                item.action_id for item in state.action_candidates
            ):
                acceptance_equal += 1
            prompt = render_semantic_action_prompt(
                instruction=binding.record.task_package.task.public.instruction,
                state=state,
                public_path_condition=path_condition,
            )
            maximum_prompt_bytes = max(maximum_prompt_bytes, len(prompt.encode("utf-8")))
            proposal = prompt_only_reference_proposal(prompt)
            expected = AgentToolCall(
                call_index=len(observations) + 1,
                tool_id=step.tool_name,
                arguments=step.tool_input,
            )
            reverse = decompile_canonical_public_call(state, expected)
            if reverse.action_id != proposal.action_id:
                raise ValueError("v26.117 Prompt-only choice differs from reversible action")
            selection = evaluate_canonical_action_proposal(
                state,
                proposal,
                call_index=expected.call_index,
            )
            if selection.commit is None or selection.commit.call != expected:
                raise ValueError("v26.117 Prompt-only Commit changed a Compiler call")
            exact_call_matches += 1
            proposals.append(proposal)
            commits.append(selection.commit)
            decision_counts[proposal.decision_kind] += 1
            selected = next(
                item for item in state.action_candidates if item.action_id == proposal.action_id
            )
            if selected.acquisition_mode is not None:
                acquisition_modes[selected.acquisition_mode] += 1
                acquisition_tools[str(selected.tool_id)] += 1
            observation = AgentToolObservation.model_validate(step.observation)
            observations.append(observation)
            if observation.error_code == "typed_selector_requires_refinement":
                typed_refinements += 1
        final_state = build_semantic_action_state(
            binding.record.task_package.task.public,
            binding.environment,
            tuple(observations),
        )
        final_state = SemanticActionState.model_validate_json(final_state.model_dump_json())
        states.append(final_state)
        state_ids.add(final_state.state_id)
        action_ids.update(item.action_id for item in final_state.action_candidates)
        source_reference_ids.update(item.reference_id for item in final_state.source_references)
        document_reference_ids.update(item.reference_id for item in final_state.document_references)
        later_action_by_id.update({item.action_id: item for item in final_state.action_candidates})
        statuses = {item.frontier_status for item in final_state.operation_frontier}
        frontier_rows.update(item.frontier_status for item in final_state.operation_frontier)
        frontier_states.update(statuses)
        if accepted_action_ids(final_state) == tuple(
            item.action_id for item in final_state.action_candidates
        ):
            acceptance_equal += 1
        final_prompt = render_semantic_action_prompt(
            instruction=binding.record.task_package.task.public.instruction,
            state=final_state,
            public_path_condition=path_condition,
        )
        maximum_prompt_bytes = max(maximum_prompt_bytes, len(final_prompt.encode("utf-8")))
        final_proposal = prompt_only_reference_proposal(final_prompt)
        final_selection = evaluate_canonical_action_proposal(
            final_state,
            final_proposal,
            call_index=len(observations) + 1,
        )
        if final_selection.commit is None or final_selection.commit.call is not None:
            raise ValueError("v26.117 Prompt-only control did not reach exact Final")
        proposals.append(final_proposal)
        commits.append(final_selection.commit)
        decision_counts[final_proposal.decision_kind] += 1
        final_ready += 1
    # Capture a current state immediately after each typed failure.
    for exact_path in historical.path_audits:
        binding = _path_binding(historical, exact_path)
        observations = []
        path_condition = (
            None
            if binding.source_path.role == "capability"
            else binding.source_path.path_strategy_id
        )
        tool_steps = tuple(
            item for item in binding.compiler_trajectory.steps if item.tool_name is not None
        )
        for index, step in enumerate(tool_steps):
            state = build_semantic_action_state(
                binding.record.task_package.task.public,
                binding.environment,
                tuple(observations),
            )
            if state.blocked_actions:
                visible_block_count += 1
                if blocked_fixture is None:
                    expected_step = tool_steps[index]
                    blocked_fixture = (
                        state,
                        tuple(observations),
                        binding.record.task_package.task.public.instruction,
                        path_condition,
                        AgentToolCall(
                            call_index=len(observations) + 1,
                            tool_id=str(expected_step.tool_name),
                            arguments=expected_step.tool_input,
                        ),
                        binding.record.task_package.task.public,
                        binding.environment,
                    )
            observations.append(AgentToolObservation.model_validate(step.observation))
    if (
        blocked_fixture is None
        or dependency_state is None
        or len(states) != 324
        or len(proposals) != 324
        or len(commits) != 324
        or exact_call_matches != 276
        or final_ready != 48
        or typed_refinements != 12
        or visible_block_count != 12
        or acceptance_equal != 324
    ):
        raise ValueError("v26.117 full-path control denominator changed")
    language_values: dict[str, Any] = {
        "protocol_id": protocol.protocol_id,
        "decision_kind_counts": dict(sorted(decision_counts.items())),
        "acquisition_mode_counts": dict(sorted(acquisition_modes.items())),
        "acquisition_tool_counts": dict(sorted(acquisition_tools.items())),
        "unique_public_state_count": len(state_ids),
        "unique_action_id_count": len(action_ids),
        "unique_source_reference_id_count": len(source_reference_ids),
        "unique_document_reference_id_count": len(document_reference_ids),
    }
    provisional_language = CanonicalActionLanguageAudit.model_construct(
        audit_id="pending", **language_values
    )
    language = CanonicalActionLanguageAudit(
        audit_id=_identity(
            provisional_language,
            "audit_id",
            "finance_v26_canonical_action_language:",
        ),
        **language_values,
    )
    frontier_values: dict[str, Any] = {
        "frontier_row_counts": dict(sorted(frontier_rows.items())),
        "state_counts_with_status": dict(sorted(frontier_states.items())),
        "operation_candidate_count": operation_candidates,
        "candidates_from_executable_count": operation_candidates,
    }
    provisional_frontier = OperationFrontierAudit.model_construct(
        audit_id="pending", **frontier_values
    )
    frontier = OperationFrontierAudit(
        audit_id=_identity(
            provisional_frontier,
            "audit_id",
            "finance_v26_operation_frontier_audit:",
        ),
        **frontier_values,
    )
    prompt_values: dict[str, Any] = {
        "path_strategy_counts": dict(sorted(path_strategies.items())),
        "maximum_prompt_utf8_bytes": maximum_prompt_bytes,
    }
    provisional_prompt = PromptOnlyPathControl.model_construct(audit_id="pending", **prompt_values)
    prompt_audit = PromptOnlyPathControl(
        audit_id=_identity(
            provisional_prompt,
            "audit_id",
            "finance_v26_prompt_only_path_control:",
        ),
        **prompt_values,
    )
    authority_provisional = StageTwoAuthorityAudit.model_construct(audit_id="pending")
    authority = StageTwoAuthorityAudit(
        audit_id=_identity(
            authority_provisional,
            "audit_id",
            "finance_v26_stage_two_authority_audit:",
        )
    )
    return (
        language,
        frontier,
        prompt_audit,
        authority,
        _ControlFixtures(
            states=tuple(states),
            proposals=tuple(proposals),
            commits=tuple(commits),
            blocked_state=blocked_fixture[0],
            blocked_observations=blocked_fixture[1],
            blocked_instruction=blocked_fixture[2],
            blocked_path_condition=blocked_fixture[3],
            blocked_expected_call=blocked_fixture[4],
            blocked_task=blocked_fixture[5],
            blocked_environment=blocked_fixture[6],
            dependency_state=dependency_state,
            later_action_by_id=later_action_by_id,
        ),
    )


def _build_recovery(
    fixtures: _ControlFixtures,
) -> tuple[SemanticRecoveryContinuityAudit, SemanticActionState, CanonicalActionCommit]:
    state = fixtures.blocked_state
    blocked = state.blocked_actions[0]
    proposal = make_canonical_action_proposal(
        state_id=state.state_id,
        action_id=blocked.action_id,
        decision_kind=blocked.decision_kind,
    )
    rejected = evaluate_canonical_action_proposal(
        state,
        proposal,
        call_index=len(fixtures.blocked_observations) + 1,
    )
    if rejected.rejection is None or rejected.commit is not None or rejected.job_terminal:
        raise ValueError("v26.117 semantic rejection did not remain a neutral continuation")
    before = RecoveryChannelAccounting(
        abi_rescue_count=1,
        semantic_recovery_count=0,
    )
    after = RecoveryChannelAccounting(
        abi_rescue_count=1,
        semantic_recovery_count=1,
    )
    recovery_state = SemanticActionState.model_validate_json(
        SemanticActionState(
            **build_semantic_action_state(
                task=fixtures.blocked_task,
                environment=fixtures.blocked_environment,
                observations=fixtures.blocked_observations,
                semantic_rejections=(rejected.rejection,),
            ).model_dump(mode="python")
        ).model_dump_json()
    )
    recovery_prompt = render_semantic_action_prompt(
        instruction=fixtures.blocked_instruction,
        state=recovery_state,
        public_path_condition=fixtures.blocked_path_condition,
    )
    recovery_proposal = prompt_only_reference_proposal(recovery_prompt)
    recovered = evaluate_canonical_action_proposal(
        recovery_state,
        recovery_proposal,
        call_index=fixtures.blocked_expected_call.call_index,
    )
    if (
        recovered.commit is None
        or recovered.commit.call != fixtures.blocked_expected_call
        or before.abi_rescue_count != after.abi_rescue_count
        or before.semantic_recovery_count + 1 != after.semantic_recovery_count
    ):
        raise ValueError("v26.117 semantic recovery continuity changed")
    values: dict[str, Any] = {}
    provisional = SemanticRecoveryContinuityAudit.model_construct(audit_id="pending", **values)
    return (
        SemanticRecoveryContinuityAudit(
            audit_id=_identity(
                provisional,
                "audit_id",
                "finance_v26_semantic_recovery_continuity:",
            ),
            **values,
        ),
        recovery_state,
        recovered.commit,
    )


def _expect_rejection(name: str, operation: Callable[[], Any]) -> MutationResult:
    try:
        operation()
    except (ValueError, TypeError):
        return MutationResult(name=name)
    raise ValueError(f"v26.117 destructive mutation passed: {name}")


def _state_identity(raw: Mapping[str, Any]) -> str:
    payload = dict(raw)
    payload.pop("state_id", None)
    return canonical_hash(payload, prefix="prospective_semantic_action_state:")


def _build_destructive(
    fixtures: _ControlFixtures,
    recovery_state: SemanticActionState,
    recovery_commit: CanonicalActionCommit,
) -> DestructiveAudit:
    proposal = fixtures.proposals[0]
    proposal_raw = proposal.model_dump(mode="json")
    commit_raw = recovery_commit.model_dump(mode="json")
    rejection = recovery_state.semantic_rejections[0]
    rejection_raw = rejection.model_dump(mode="json")
    blocked_state = fixtures.blocked_state

    def proposal_extra(field: str, value: Any) -> Callable[[], Any]:
        return lambda: CanonicalActionProposal.model_validate({**proposal_raw, field: value})

    def commit_flag(field: str, value: Any = True) -> Callable[[], Any]:
        return lambda: CanonicalActionCommit.model_validate({**commit_raw, field: value})

    dependency_raw = fixtures.dependency_state.model_dump(mode="json")
    dependency_node = next(
        item.node_id
        for item in fixtures.dependency_state.operation_frontier
        if item.frontier_status == "dependency_ready"
    )
    later_operation = next(
        item
        for item in fixtures.later_action_by_id.values()
        if item.decision_kind == "execute_public_operation" and item.node_id == dependency_node
    )
    injected_candidates = tuple(
        sorted(
            (
                *fixtures.dependency_state.action_candidates,
                later_operation,
            ),
            key=lambda item: item.action_id,
        )
    )
    dependency_raw["action_candidates"] = [
        item.model_dump(mode="json") for item in injected_candidates
    ]
    dependency_raw["state_id"] = _state_identity(dependency_raw)

    blocked_action = blocked_state.blocked_actions[0]
    historical_action = fixtures.later_action_by_id.get(blocked_action.action_id)
    if historical_action is None:
        raise ValueError("v26.117 blocked action lacks a public historical candidate")
    blocked_raw = blocked_state.model_dump(mode="json")
    blocked_raw["action_candidates"] = [
        item.model_dump(mode="json")
        for item in sorted(
            (*blocked_state.action_candidates, historical_action),
            key=lambda item: item.action_id,
        )
    ]
    blocked_raw["state_id"] = _state_identity(blocked_raw)

    signature_parameters = tuple(inspect.signature(evaluate_canonical_action_proposal).parameters)

    def hidden_history_parameter() -> None:
        if signature_parameters == ("state", "proposal", "call_index"):
            raise ValueError("hidden historical failure is not an acceptance input")

    mutations = (
        _expect_rejection(
            "abi_and_semantic_recovery_counters_coupled",
            lambda: RecoveryChannelAccounting.model_validate(
                {
                    "abi_rescue_count": 1,
                    "semantic_recovery_count": 1,
                    "counters_are_independent": False,
                }
            ),
        ),
        _expect_rejection(
            "blocked_action_reinserted_as_selectable",
            lambda: SemanticActionState.model_validate(blocked_raw),
        ),
        _expect_rejection("compiler_fills_evidence", commit_flag("compiler_selected_evidence")),
        _expect_rejection("compiler_fills_node", commit_flag("compiler_selected_node")),
        _expect_rejection("compiler_fills_operand", commit_flag("compiler_selected_operand")),
        _expect_rejection("compiler_fills_operator", commit_flag("compiler_selected_operator")),
        _expect_rejection("compiler_fills_tool", commit_flag("compiler_selected_tool")),
        _expect_rejection("compiler_repairs_semantics", commit_flag("compiler_repaired_semantics")),
        _expect_rejection(
            "dependency_ready_operation_made_selectable",
            lambda: SemanticActionState.model_validate(dependency_raw),
        ),
        _expect_rejection("hidden_old_failure_used_by_acceptance", hidden_history_parameter),
        _expect_rejection(
            "proposal_carries_direct_arguments", proposal_extra("direct_arguments", {"x": 1})
        ),
        _expect_rejection(
            "proposal_carries_evidence_ids", proposal_extra("evidence_ids", ["evidence:x"])
        ),
        _expect_rejection(
            "proposal_carries_node_id", proposal_extra("node_id", "operation_stage_01")
        ),
        _expect_rejection(
            "proposal_carries_operand_sources", proposal_extra("operand_sources", ["source:x"])
        ),
        _expect_rejection("proposal_carries_operator_id", proposal_extra("operator_id", "compare")),
        _expect_rejection("proposal_carries_tool_id", proposal_extra("tool_id", "calculator")),
        _expect_rejection(
            "rejection_exposes_exact_argument_values",
            lambda: PublicSemanticRejectionObservation.model_validate(
                {**rejection_raw, "direct_arguments": {"x": 1}}
            ),
        ),
        _expect_rejection(
            "rejection_exposes_required_argument_patch",
            lambda: PublicSemanticRejectionObservation.model_validate(
                {**rejection_raw, "required_argument_patch": {"x": 1}}
            ),
        ),
        _expect_rejection(
            "rejection_terminates_job",
            lambda: PublicSemanticRejectionObservation.model_validate(
                {**rejection_raw, "job_terminal": True}
            ),
        ),
        _expect_rejection(
            "stage_two_provider_route_added", commit_flag("stage_two_provider_calls", 1)
        ),
    )
    ordered = tuple(sorted(mutations, key=lambda item: item.name))
    values: dict[str, Any] = {"mutations": ordered}
    provisional = DestructiveAudit.model_construct(audit_id="pending", **values)
    return DestructiveAudit(
        audit_id=_identity(
            provisional,
            "audit_id",
            "finance_v26_semantic_action_destructive:",
        ),
        **values,
    )


def _build_transition() -> ProspectiveTransitionContract:
    provisional = ProspectiveTransitionContract.model_construct(contract_id="pending")
    return ProspectiveTransitionContract(
        contract_id=_identity(
            provisional,
            "contract_id",
            "finance_v26_semantic_action_transition:",
        )
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
    predecessor_dir: Path,
    output_dir: Path,
) -> SemanticActionPreflightReport:
    source, predecessor = _build_source_replay(
        package_root=package_root,
        implementation_root=implementation_root,
        predecessor_dir=predecessor_dir,
    )
    protocol = _build_protocol(predecessor)
    language, frontier, prompt, authority, fixtures = _build_path_controls(
        package_root=package_root,
        implementation_root=implementation_root,
        protocol=protocol,
    )
    recovery, recovery_state, recovery_commit = _build_recovery(fixtures)
    destructive = _build_destructive(fixtures, recovery_state, recovery_commit)
    transition = _build_transition()
    outputs: tuple[tuple[str, BaseModel], ...] = (
        ("source_replay_audit.json", source),
        ("semantic_action_protocol_contract.json", protocol),
        ("canonical_action_language_audit.json", language),
        ("operation_frontier_audit.json", frontier),
        ("prompt_only_path_control.json", prompt),
        ("semantic_recovery_continuity_audit.json", recovery),
        ("stage_two_authority_audit.json", authority),
        ("destructive_audit.json", destructive),
        ("prospective_transition_contract.json", transition),
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    for name, value in outputs:
        _write_json(output_dir / name, value.model_dump(mode="json"))
    details = tuple(_detail(output_dir / name, output_dir) for name, _ in outputs)
    values: dict[str, Any] = {
        "source_replay_audit_id": source.audit_id,
        "protocol_id": protocol.protocol_id,
        "canonical_action_language_audit_id": language.audit_id,
        "operation_frontier_audit_id": frontier.audit_id,
        "prompt_only_path_control_id": prompt.audit_id,
        "semantic_recovery_audit_id": recovery.audit_id,
        "stage_two_authority_audit_id": authority.audit_id,
        "destructive_audit_id": destructive.audit_id,
        "transition_contract_id": transition.contract_id,
        "detail_files": details,
    }
    provisional = SemanticActionPreflightReport.model_construct(report_id="pending", **values)
    report = SemanticActionPreflightReport(
        report_id=_identity(
            provisional,
            "report_id",
            "finance_v26_semantic_action_preflight_report:",
        ),
        **values,
    )
    _write_json(output_dir / "report.json", report.model_dump(mode="json"))
    return report


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Credential-free v26.117 Semantic Action protocol preflight"
    )
    parser.add_argument(
        "--package-root",
        type=Path,
        default=Path(__file__).resolve().parents[4],
    )
    parser.add_argument(
        "--implementation-root",
        type=Path,
        default=Path(__file__).resolve().parents[4],
    )
    parser.add_argument("--predecessor-dir", type=Path, default=Path(PREDECESSOR_DIR))
    parser.add_argument("--output-dir", type=Path, default=Path(OUTPUT_DIR))
    args = parser.parse_args()
    report = build(
        package_root=args.package_root,
        implementation_root=args.implementation_root,
        predecessor_dir=args.predecessor_dir,
        output_dir=args.output_dir,
    )
    print(report.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
