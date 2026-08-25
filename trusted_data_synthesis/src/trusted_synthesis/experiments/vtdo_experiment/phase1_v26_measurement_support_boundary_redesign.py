from __future__ import annotations

import argparse
import ast
import hashlib
import inspect
import json
import tempfile
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any, Final, Literal, cast

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.core.measurement.support import (
    BASELINE_ACTION_SET_POLICY_VERSION,
    BaselineActionSetResolution,
    MeasurementSupportContract,
    MeasurementSupportDecision,
    classify_measurement_support,
    make_measurement_support_contract,
    make_measurement_support_event,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_orphan_support_exit_recovery_postrun_audit as predecessor,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_privacy_safe_s1_capability_failure_audit as failed_audit,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_privacy_safe_s1_capability_preflight as capability_preflight,
)
from trusted_synthesis.hashing import canonical_hash
from trusted_synthesis.runtime.agent import prospective_measurement_support as support_runtime
from trusted_synthesis.runtime.agent.prospective_semantic_action_protocol import (
    CanonicalPublicAction,
    SemanticActionState,
    build_semantic_action_state,
    evaluate_canonical_action_proposal,
    make_canonical_action_proposal,
)
from trusted_synthesis.runtime.agent.prospective_thinking_completion import CompletionProjection

RUN_ID: Final = "finance_v26_146_measurement_support_boundary_redesign_v1_20260825"
OUTPUT_DIR: Final = (
    "artifacts/vtdo_experiment/finance_v26_146_measurement_support_boundary_redesign_v1_20260825"
)
IMPLEMENTATION_PATHS: Final = (
    "src/trusted_synthesis/core/measurement/__init__.py",
    "src/trusted_synthesis/core/measurement/support.py",
    "src/trusted_synthesis/runtime/agent/prospective_measurement_support.py",
    "src/trusted_synthesis/experiments/vtdo_experiment/"
    "phase1_v26_measurement_support_boundary_redesign.py",
)
PREDECESSOR_DIR: Final = predecessor.OUTPUT_DIR
FAILED_AUDIT_DIR: Final = failed_audit.OUTPUT_DIR
NEXT_STAGE: Final = "historical_capability_validity_decomposition_audit_only"

EXPECTED_PREDECESSOR_REPORT_ID: Final = (
    "finance_v26_orphan_recovery_postrun_audit_report:"
    "b89eb11ef32169e985b4f7fdb765c140440c4e1e2fdcf5b7d700736a64103602"
)
EXPECTED_PREDECESSOR_REPORT_SHA256: Final = (
    "76666e7c0672115ae72704015f5276f8903b9bc5601106ec3211f4d4bcd7360d"
)
EXPECTED_PREDECESSOR_TRANSITION_ID: Final = (
    "finance_v26_capability_support_boundary_transition:"
    "33a1d469b8d4493d205ef278b2671ccfa55bbc05656eebb2dfd4dc875669c2c1"
)
REGISTERED_PATH_COUNT: Final = 48
REGISTERED_STATE_COUNT: Final = 522
PROMPT_PHASE_COUNT: Final = 3


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
    raise ValueError(f"v26.146 cannot replay bound file: {relative_path}")


class SourceReplayEntry(FrozenModel):
    relative_path: str = Field(min_length=1)
    source_kind: Literal[
        "v26_145_transitive_source",
        "v26_145_output",
        "v26_146_implementation",
    ]
    expected_sha256: str = Field(min_length=64, max_length=64)
    observed_sha256: str = Field(min_length=64, max_length=64)
    byte_count: int = Field(gt=0)
    passed: Literal[True] = True


class SourceReplayAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    predecessor_report_id: str = EXPECTED_PREDECESSOR_REPORT_ID
    predecessor_transition_id: str = EXPECTED_PREDECESSOR_TRANSITION_ID
    predecessor_transitive_file_count: Literal[7283] = 7283
    predecessor_output_file_count: Literal[7] = 7
    implementation_file_count: Literal[4] = 4
    replayed_file_count: Literal[7294] = 7294
    replay_pass_count: Literal[7294] = 7294
    entries: tuple[SourceReplayEntry, ...] = Field(min_length=7294, max_length=7294)
    replay_before_support_design_loading: Literal[True] = True
    credential_lookup_attempted: Literal[False] = False
    model_client_constructed: Literal[False] = False
    provider_calls: Literal[0] = 0
    stage_two_provider_calls: Literal[0] = 0
    gpu_jobs: Literal[0] = 0
    status: Literal["passed"] = "passed"
    schema_version: Literal["finance_v26_measurement_support_source_replay.v1"] = (
        "finance_v26_measurement_support_source_replay.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> SourceReplayAudit:
        paths = tuple(item.relative_path for item in self.entries)
        if (
            paths != tuple(sorted(set(paths)))
            or len(paths) != self.replayed_file_count
            or any(item.expected_sha256 != item.observed_sha256 for item in self.entries)
        ):
            raise ValueError("v26.146 source replay changed")
        if self.audit_id != _identity(
            self,
            "audit_id",
            "finance_v26_measurement_support_source_replay:",
        ):
            raise ValueError("v26.146 source replay identity changed")
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
    predecessor_report_id: str = EXPECTED_PREDECESSOR_REPORT_ID
    predecessor_transition_id: str = EXPECTED_PREDECESSOR_TRANSITION_ID
    comparisons: tuple[FileComparison, ...] = Field(min_length=7, max_length=7)
    predecessor_output_file_count: Literal[7] = 7
    byte_identical_file_count: Literal[7] = 7
    frozen_lineage_endpoint_count: Literal[96] = 96
    frozen_model_outcome_count: Literal[93] = 93
    frozen_support_exit_count: Literal[3] = 3
    historical_reclassified_count: Literal[0] = 0
    provider_calls: Literal[0] = 0
    stage_two_provider_calls: Literal[0] = 0
    status: Literal["passed"] = "passed"
    schema_version: Literal["finance_v26_measurement_support_predecessor_integrity.v1"] = (
        "finance_v26_measurement_support_predecessor_integrity.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> PredecessorIntegrityAudit:
        paths = tuple(item.relative_path for item in self.comparisons)
        if paths != tuple(sorted(set(paths))) or any(
            item.expected_sha256 != item.observed_sha256 for item in self.comparisons
        ):
            raise ValueError("v26.146 predecessor byte comparison changed")
        if self.audit_id != _identity(
            self,
            "audit_id",
            "finance_v26_measurement_support_predecessor_integrity:",
        ):
            raise ValueError("v26.146 predecessor-integrity identity changed")
        return self


class BaselineAuthorityAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    support_contract_id: str = Field(min_length=1)
    baseline_policy_version: Literal["prospective_public_baseline_action_set.v1"] = (
        BASELINE_ACTION_SET_POLICY_VERSION
    )
    audited_function_names: tuple[str, ...] = Field(min_length=7)
    ast_name_or_attribute_count: int = Field(gt=0)
    banned_read_count: Literal[0] = 0
    oracle_read_count: Literal[0] = 0
    gold_read_count: Literal[0] = 0
    correct_answer_read_count: Literal[0] = 0
    future_trajectory_read_count: Literal[0] = 0
    target_evidence_read_count: Literal[0] = 0
    model_prompt_exposure_count: Literal[0] = 0
    candidate_mutation_count: Literal[0] = 0
    model_action_selection_replacement_or_repair_count: Literal[0] = 0
    public_path_condition_read_count: Literal[0] = 0
    current_public_state_only: Literal[True] = True
    stage_two_provider_calls: Literal[0] = 0
    status: Literal["passed"] = "passed"
    schema_version: Literal["finance_v26_public_baseline_authority_audit.v1"] = (
        "finance_v26_public_baseline_authority_audit.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> BaselineAuthorityAudit:
        if self.audited_function_names != tuple(sorted(set(self.audited_function_names))):
            raise ValueError("baseline authority function set changed")
        if self.audit_id != _identity(
            self,
            "audit_id",
            "finance_v26_public_baseline_authority_audit:",
        ):
            raise ValueError("baseline authority identity changed")
        return self


StateCategory = Literal[
    "abi_rescue_state",
    "blocked_action_state",
    "failed_observation_successor",
    "one_detour_successor",
    "progress_observation_successor",
    "registered_reference_state",
    "semantic_recovery_state",
    "successful_no_progress_successor",
    "terminal_verification_state",
]


class StateClosureRow(FrozenModel):
    row_id: str = Field(min_length=1)
    public_state_id: str = Field(min_length=1)
    progress_vector_id: str = Field(min_length=1)
    categories: tuple[StateCategory, ...] = Field(min_length=1)
    visible_action_ids: tuple[str, ...] = Field(min_length=1)
    independently_recomputed_baseline_action_ids: tuple[str, ...]
    resolution: BaselineActionSetResolution
    baseline_subset_of_visible_candidates: Literal[True] = True
    exact_independent_baseline_match: Literal[True] = True
    host_exception_count: Literal[0] = 0

    @model_validator(mode="after")
    def validate_row(self) -> StateClosureRow:
        if self.categories != tuple(sorted(set(self.categories))):
            raise ValueError("state-closure categories are not canonical")
        if self.visible_action_ids != tuple(sorted(set(self.visible_action_ids))):
            raise ValueError("state-closure visible actions are not canonical")
        expected = tuple(sorted(set(self.independently_recomputed_baseline_action_ids)))
        if (
            self.independently_recomputed_baseline_action_ids != expected
            or self.resolution.public_state_id != self.public_state_id
            or self.resolution.progress_vector_id != self.progress_vector_id
            or self.resolution.baseline_action_ids != expected
            or not set(expected).issubset(self.visible_action_ids)
        ):
            raise ValueError("state-closure baseline authority changed")
        if self.row_id != _identity(
            self,
            "row_id",
            "finance_v26_measurement_support_state_closure_row:",
        ):
            raise ValueError("state-closure row identity changed")
        return self


class EventClosureRow(FrozenModel):
    row_id: str = Field(min_length=1)
    predecessor_path_id: str = Field(min_length=1)
    role: Literal["capability", "reachability"]
    mechanism_id: str = Field(min_length=1)
    tier: Literal["easy_control", "frontier", "hard_control"]
    reference_state_index: int = Field(ge=0)
    state_id_before: str = Field(min_length=1)
    state_id_after: str = Field(min_length=1)
    selected_action_id: str = Field(min_length=1)
    decision_kind: str = Field(min_length=1)
    observation_id: str | None
    observation_error_code: str | None
    observation_status: Literal["succeeded", "failed"] | None
    successor_state_available: bool
    progress_vector_changed: bool
    baseline_classifier_call_count: int = Field(ge=0, le=1)
    decision: MeasurementSupportDecision
    model_action_selected_replaced_or_repaired: Literal[False] = False
    provider_calls: Literal[0] = 0
    stage_two_provider_calls: Literal[0] = 0

    @model_validator(mode="after")
    def validate_row(self) -> EventClosureRow:
        if self.decision.public_state_id != self.state_id_before:
            raise ValueError("event-closure support state binding changed")
        if (self.observation_status == "failed" and not self.observation_error_code) or (
            self.observation_status != "failed" and self.observation_error_code is not None
        ):
            raise ValueError("Observation error-code binding changed")
        if not self.successor_state_available:
            expected = (
                f"public_replan_state_unavailable_after_{self.observation_status}_observation"
            )
            if (
                self.decision.status != "unavailable"
                or self.decision.reason_code != expected
                or self.baseline_classifier_call_count != 0
            ):
                raise ValueError("unselectable successor did not produce a typed support exit")
        elif self.decision.reason_code in {
            "terminal_verification",
            "final_commit",
            "non_public_commit",
        }:
            if self.decision.status != "not_required" or self.baseline_classifier_call_count != 0:
                raise ValueError("terminal or non-public event invoked baseline classification")
        elif self.observation_status == "failed":
            if (
                self.decision.status != "not_required"
                or self.decision.reason_code != "failed_observation"
                or self.baseline_classifier_call_count != 0
            ):
                raise ValueError("failed Observation invoked baseline classification")
        elif self.observation_status == "succeeded" and self.progress_vector_changed:
            if (
                self.decision.status != "not_required"
                or self.decision.reason_code not in {"public_progress", "terminal_verification"}
                or self.baseline_classifier_call_count != 0
            ):
                raise ValueError("progress Observation invoked baseline classification")
        elif self.observation_status == "succeeded":
            if (
                self.decision.status not in {"available", "unavailable"}
                or self.baseline_classifier_call_count != 1
            ):
                raise ValueError("successful no-progress event skipped typed baseline")
        elif self.baseline_classifier_call_count != 0 or self.decision.status != "not_required":
            raise ValueError("non-Observation event invoked baseline classification")
        if self.row_id != _identity(
            self,
            "row_id",
            "finance_v26_measurement_support_event_closure_row:",
        ):
            raise ValueError("event-closure row identity changed")
        return self


class SupportClosureCensus(FrozenModel):
    audit_id: str = Field(min_length=1)
    support_contract_id: str = Field(min_length=1)
    baseline_authority_audit_id: str = Field(min_length=1)
    registered_path_count: Literal[48] = 48
    registered_state_count: Literal[522] = 522
    registered_prompt_phase_state_count: Literal[1566] = 1566
    registered_candidate_event_count: int = Field(gt=0)
    semantic_recovery_state_count: int = Field(gt=0)
    unique_typed_state_count: int = Field(gt=522)
    typed_state_resolution_count: int = Field(gt=522)
    baseline_available_state_count: int = Field(gt=0)
    baseline_unavailable_state_count: int = Field(ge=0)
    failed_observation_event_count: int = Field(gt=0)
    failed_observation_not_required_count: int = Field(gt=0)
    failed_observation_typed_support_exit_count: int = Field(ge=0)
    progress_observation_event_count: int = Field(gt=0)
    successful_no_progress_event_count: int = Field(gt=0)
    terminal_or_final_event_count: int = Field(gt=0)
    unselectable_successor_event_count: int = Field(ge=0)
    unselectable_successor_error_counts: dict[str, int] = Field(min_length=1)
    failed_observation_baseline_classifier_call_count: Literal[0] = 0
    progress_observation_baseline_classifier_call_count: Literal[0] = 0
    successful_no_progress_baseline_classifier_call_count: int = Field(gt=0)
    available_decision_count: int = Field(ge=0)
    not_required_decision_count: int = Field(gt=0)
    unavailable_decision_count: int = Field(ge=0)
    baseline_unavailable_decision_count: int = Field(ge=0)
    successor_unavailable_decision_count: int = Field(ge=0)
    ordinary_detour_event_count: int = Field(ge=0)
    typed_measurement_support_exit_count: int = Field(ge=0)
    host_exception_count: Literal[0] = 0
    candidate_authority_violation_count: Literal[0] = 0
    model_action_selection_replacement_or_repair_count: Literal[0] = 0
    provider_calls: Literal[0] = 0
    stage_two_provider_calls: Literal[0] = 0
    state_rows: tuple[StateClosureRow, ...] = Field(min_length=523)
    event_rows: tuple[EventClosureRow, ...] = Field(min_length=1)
    full_typed_closure_passed: Literal[True] = True
    status: Literal["passed"] = "passed"
    schema_version: Literal["finance_v26_measurement_support_closure_census.v1"] = (
        "finance_v26_measurement_support_closure_census.v1"
    )

    @model_validator(mode="after")
    def validate_census(self) -> SupportClosureCensus:
        state_ids = tuple(item.public_state_id for item in self.state_rows)
        event_ids = tuple(item.row_id for item in self.event_rows)
        statuses = Counter(item.decision.status for item in self.event_rows)
        failed = tuple(item for item in self.event_rows if item.observation_status == "failed")
        progress = tuple(
            item
            for item in self.event_rows
            if item.observation_status == "succeeded" and item.progress_vector_changed
        )
        no_progress = tuple(
            item
            for item in self.event_rows
            if (
                item.observation_status == "succeeded"
                and item.successor_state_available
                and not item.progress_vector_changed
            )
        )
        terminals = tuple(item for item in self.event_rows if item.observation_status is None)
        unavailable_successors = tuple(
            item for item in self.event_rows if not item.successor_state_available
        )
        failed_not_required = tuple(
            item for item in failed if item.decision.status == "not_required"
        )
        failed_support_exits = tuple(
            item for item in failed if item.decision.status == "unavailable"
        )
        baseline_unavailable = tuple(
            item
            for item in self.event_rows
            if item.successor_state_available and item.decision.status == "unavailable"
        )
        successor_errors = dict(
            sorted(
                Counter(
                    cast(str, item.observation_error_code) for item in unavailable_successors
                ).items()
            )
        )
        if (
            state_ids != tuple(sorted(set(state_ids)))
            or event_ids != tuple(sorted(set(event_ids)))
            or len(self.state_rows) != self.unique_typed_state_count
            or self.typed_state_resolution_count != self.unique_typed_state_count
            or len(self.event_rows) != self.registered_candidate_event_count
            or sum(item.resolution.status == "available" for item in self.state_rows)
            != self.baseline_available_state_count
            or sum(item.resolution.status == "unavailable" for item in self.state_rows)
            != self.baseline_unavailable_state_count
            or len(failed) != self.failed_observation_event_count
            or len(failed_not_required) != self.failed_observation_not_required_count
            or len(failed_support_exits) != self.failed_observation_typed_support_exit_count
            or len(progress) != self.progress_observation_event_count
            or len(no_progress) != self.successful_no_progress_event_count
            or len(terminals) != self.terminal_or_final_event_count
            or len(unavailable_successors) != self.unselectable_successor_event_count
            or successor_errors != self.unselectable_successor_error_counts
            or sum(item.baseline_classifier_call_count for item in failed) != 0
            or sum(item.baseline_classifier_call_count for item in progress) != 0
            or sum(item.baseline_classifier_call_count for item in no_progress)
            != self.successful_no_progress_baseline_classifier_call_count
            or statuses["available"] != self.available_decision_count
            or statuses["not_required"] != self.not_required_decision_count
            or statuses["unavailable"] != self.unavailable_decision_count
            or len(baseline_unavailable) != self.baseline_unavailable_decision_count
            or len(unavailable_successors) != self.successor_unavailable_decision_count
            or sum(item.decision.ordinary_detour_observed for item in self.event_rows)
            != self.ordinary_detour_event_count
            or self.unavailable_decision_count != self.typed_measurement_support_exit_count
        ):
            raise ValueError("measurement-support closure aggregate changed")
        if self.audit_id != _identity(
            self,
            "audit_id",
            "finance_v26_measurement_support_closure_census:",
        ):
            raise ValueError("measurement-support closure identity changed")
        return self


class OrphanFutureControlRow(FrozenModel):
    row_id: str = Field(min_length=1)
    historical_job_id: str = Field(min_length=1)
    historical_initial_state_id: str = Field(min_length=1)
    historical_successor_state_id: str = Field(min_length=1)
    historical_observation_error_code: Literal["typed_selector_requires_refinement"] = (
        "typed_selector_requires_refinement"
    )
    historical_progress_vector_changed: Literal[False] = False
    historical_terminal_unchanged: Literal[True] = True
    historical_reclassified: Literal[False] = False
    counterfactual_future_contract_only: Literal[True] = True
    future_decision: MeasurementSupportDecision
    baseline_classifier_call_count: Literal[0] = 0
    future_model_replanning_allowed: Literal[True] = True
    provider_calls: Literal[0] = 0

    @model_validator(mode="after")
    def validate_row(self) -> OrphanFutureControlRow:
        if (
            self.future_decision.status != "not_required"
            or self.future_decision.reason_code != "failed_observation"
            or self.future_decision.baseline_classifier_invoked
            or self.future_decision.ordinary_detour_observed
        ):
            raise ValueError("orphan future-only support decision changed")
        if self.row_id != _identity(
            self,
            "row_id",
            "finance_v26_orphan_future_support_control_row:",
        ):
            raise ValueError("orphan future-control row identity changed")
        return self


class OrphanFutureContractControl(FrozenModel):
    audit_id: str = Field(min_length=1)
    support_contract_id: str = Field(min_length=1)
    historical_root_cause_audit_id: str = Field(min_length=1)
    rows: tuple[OrphanFutureControlRow, ...] = Field(min_length=3, max_length=3)
    exact_historical_orphan_count: Literal[3] = 3
    future_not_required_count: Literal[3] = 3
    failed_observation_baseline_classifier_call_count: Literal[0] = 0
    historical_reclassified_count: Literal[0] = 0
    missing_model_endpoint_inferred_count: Literal[0] = 0
    provider_calls: Literal[0] = 0
    stage_two_provider_calls: Literal[0] = 0
    status: Literal["passed"] = "passed"
    schema_version: Literal["finance_v26_orphan_future_support_control.v1"] = (
        "finance_v26_orphan_future_support_control.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> OrphanFutureContractControl:
        if (
            tuple(item.row_id for item in self.rows)
            != tuple(sorted({item.row_id for item in self.rows}))
            or sum(item.future_decision.status == "not_required" for item in self.rows) != 3
        ):
            raise ValueError("orphan future-contract denominator changed")
        if self.audit_id != _identity(
            self,
            "audit_id",
            "finance_v26_orphan_future_support_control:",
        ):
            raise ValueError("orphan future-control identity changed")
        return self


class ProspectiveTransitionContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    support_contract_id: str = Field(min_length=1)
    support_closure_census_id: str = Field(min_length=1)
    orphan_future_control_id: str = Field(min_length=1)
    next_permitted_stage: Literal["historical_capability_validity_decomposition_audit_only"] = (
        NEXT_STAGE
    )
    historical_capability_validity_decomposition_audit_authorized: Literal[True] = True
    exact_historical_complete_raw_input_count: Literal[93] = 93
    historical_support_exit_input_count: Literal[3] = 3
    historical_support_exits_validity_evaluable: Literal[False] = False
    historical_terminal_or_validity_reclassification_authorized: Literal[False] = False
    verifier_change_authorized: Literal[False] = False
    final_grammar_change_authorized: Literal[False] = False
    new_capability_population_or_identity_materialization_authorized: Literal[False] = False
    provider_calls_authorized: Literal[False] = False
    capability_execution_authorized: Literal[False] = False
    reachability_identity_or_execution_authorized: Literal[False] = False
    state_mapping_authorized: Literal[False] = False
    training_release_or_production_authorized: Literal[False] = False
    schema_version: Literal["finance_v26_measurement_support_transition.v1"] = (
        "finance_v26_measurement_support_transition.v1"
    )

    @model_validator(mode="after")
    def validate_contract(self) -> ProspectiveTransitionContract:
        if self.contract_id != _identity(
            self,
            "contract_id",
            "finance_v26_measurement_support_transition:",
        ):
            raise ValueError("v26.146 transition identity changed")
        return self


class MutationResult(FrozenModel):
    mutation_name: str = Field(min_length=1)
    rejected: Literal[True] = True


class DestructiveAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    support_contract_id: str = Field(min_length=1)
    support_closure_census_id: str = Field(min_length=1)
    transition_contract_id: str = Field(min_length=1)
    mutation_results: tuple[MutationResult, ...] = Field(min_length=16, max_length=16)
    mutation_count: Literal[16] = 16
    rejected_count: Literal[16] = 16
    provider_calls: Literal[0] = 0
    stage_two_provider_calls: Literal[0] = 0
    status: Literal["passed"] = "passed"
    schema_version: Literal["finance_v26_measurement_support_destructive.v1"] = (
        "finance_v26_measurement_support_destructive.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> DestructiveAudit:
        names = tuple(item.mutation_name for item in self.mutation_results)
        if names != tuple(sorted(set(names))):
            raise ValueError("v26.146 destructive mutation set changed")
        if self.audit_id != _identity(
            self,
            "audit_id",
            "finance_v26_measurement_support_destructive:",
        ):
            raise ValueError("v26.146 destructive identity changed")
        return self


class DetailFile(FrozenModel):
    relative_path: str = Field(min_length=1)
    sha256: str = Field(min_length=64, max_length=64)
    byte_count: int = Field(gt=0)


class MeasurementSupportRedesignReport(FrozenModel):
    report_id: str = Field(min_length=1)
    run_id: Literal["finance_v26_146_measurement_support_boundary_redesign_v1_20260825"] = RUN_ID
    source_replay_audit_id: str = Field(min_length=1)
    predecessor_integrity_audit_id: str = Field(min_length=1)
    measurement_support_contract_id: str = Field(min_length=1)
    baseline_authority_audit_id: str = Field(min_length=1)
    support_closure_census_id: str = Field(min_length=1)
    orphan_future_control_id: str = Field(min_length=1)
    destructive_audit_id: str = Field(min_length=1)
    transition_contract_id: str = Field(min_length=1)
    registered_path_count: Literal[48] = 48
    registered_state_count: Literal[522] = 522
    registered_candidate_event_count: Literal[3089] = 3089
    unique_typed_state_count: Literal[3306] = 3306
    failed_observation_event_count: Literal[1667] = 1667
    failed_observation_not_required_count: Literal[1587] = 1587
    failed_observation_typed_support_exit_count: Literal[80] = 80
    progress_observation_event_count: Literal[864] = 864
    successful_no_progress_event_count: Literal[510] = 510
    ordinary_detour_event_count: Literal[378] = 378
    baseline_unavailable_decision_count: Literal[0] = 0
    successor_unavailable_decision_count: Literal[80] = 80
    all_reachable_support_states_typed: Literal[True] = True
    host_exception_count: Literal[0] = 0
    failed_observation_baseline_classifier_call_count: Literal[0] = 0
    progress_observation_baseline_classifier_call_count: Literal[0] = 0
    orphan_future_not_required_count: Literal[3] = 3
    historical_reclassified_count: Literal[0] = 0
    verifier_changed: Literal[False] = False
    final_grammar_changed: Literal[False] = False
    capability_population_materialized: Literal[False] = False
    provider_calls: Literal[0] = 0
    stage_two_provider_calls: Literal[0] = 0
    gpu_jobs: Literal[0] = 0
    next_permitted_stage: Literal["historical_capability_validity_decomposition_audit_only"] = (
        NEXT_STAGE
    )
    detail_files: tuple[DetailFile, ...] = Field(min_length=8, max_length=8)
    status: Literal["measurement_support_boundary_redesign_passed"] = (
        "measurement_support_boundary_redesign_passed"
    )
    schema_version: Literal["finance_v26_measurement_support_redesign_report.v1"] = (
        "finance_v26_measurement_support_redesign_report.v1"
    )

    @model_validator(mode="after")
    def validate_report(self) -> MeasurementSupportRedesignReport:
        paths = tuple(item.relative_path for item in self.detail_files)
        if paths != tuple(sorted(set(paths))):
            raise ValueError("v26.146 report detail files changed")
        if self.report_id != _identity(
            self,
            "report_id",
            "finance_v26_measurement_support_redesign_report:",
        ):
            raise ValueError("v26.146 report identity changed")
        return self


def _source_replay(
    *,
    package_root: Path,
    implementation_root: Path,
) -> SourceReplayAudit:
    predecessor_dir = package_root / PREDECESSOR_DIR
    report_path = predecessor_dir / "report.json"
    report = predecessor.PostrunAuditReport.model_validate(_load(report_path))
    transition = predecessor.ProspectiveTransitionContract.model_validate(
        _load(predecessor_dir / "prospective_transition_contract.json")
    )
    if (
        _sha256(report_path) != EXPECTED_PREDECESSOR_REPORT_SHA256
        or report.report_id != EXPECTED_PREDECESSOR_REPORT_ID
        or report.transition_contract_id != EXPECTED_PREDECESSOR_TRANSITION_ID
        or transition.contract_id != EXPECTED_PREDECESSOR_TRANSITION_ID
        or transition.next_permitted_stage != predecessor.NEXT_STAGE
    ):
        raise ValueError("v26.146 direct predecessor decision changed")
    formal_source = predecessor.PostrunSourceReplayAudit.model_validate(
        _load(predecessor_dir / "source_replay_audit.json")
    )
    entries: list[SourceReplayEntry] = []
    for item in formal_source.entries:
        path = _find_bound_path(
            item.relative_path,
            item.expected_sha256,
            package_root=package_root,
            implementation_root=implementation_root,
        )
        entries.append(
            SourceReplayEntry(
                relative_path=item.relative_path,
                source_kind="v26_145_transitive_source",
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
            raise ValueError(f"v26.146 predecessor output changed: {name}")
        entries.append(
            SourceReplayEntry(
                relative_path=str(path.relative_to(package_root)),
                source_kind="v26_145_output",
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
                source_kind="v26_146_implementation",
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
            "finance_v26_measurement_support_source_replay:",
        ),
        **values,
    )


def _predecessor_integrity(
    *,
    package_root: Path,
    implementation_root: Path,
    source_replay: SourceReplayAudit,
) -> PredecessorIntegrityAudit:
    predecessor_dir = package_root / PREDECESSOR_DIR
    with tempfile.TemporaryDirectory(prefix="v26_146_predecessor_") as directory:
        rebuilt_dir = Path(directory)
        predecessor.build_postrun_audit(
            package_root=package_root,
            implementation_root=implementation_root,
            historical_execution_dir=package_root / predecessor.failed_audit.EXECUTION_DIR,
            failed_audit_dir=package_root / predecessor.failed_audit.OUTPUT_DIR,
            preflight_dir=package_root / predecessor.recovery_preflight.OUTPUT_DIR,
            execution_dir=package_root / predecessor.execution.OUTPUT_DIR,
            output_dir=rebuilt_dir,
        )
        formal_paths = tuple(sorted(path for path in predecessor_dir.iterdir() if path.is_file()))
        rebuilt_paths = tuple(sorted(path for path in rebuilt_dir.iterdir() if path.is_file()))
        if tuple(path.name for path in formal_paths) != tuple(path.name for path in rebuilt_paths):
            raise ValueError("v26.146 predecessor rebuild file set changed")
        comparisons = tuple(
            FileComparison(
                relative_path=formal_path.name,
                expected_sha256=_sha256(formal_path),
                observed_sha256=_sha256(rebuilt_dir / formal_path.name),
                byte_count=formal_path.stat().st_size,
            )
            for formal_path in formal_paths
        )
    values = {
        "source_replay_audit_id": source_replay.audit_id,
        "comparisons": comparisons,
    }
    provisional = PredecessorIntegrityAudit.model_construct(audit_id="pending", **values)
    return PredecessorIntegrityAudit(
        audit_id=_identity(
            provisional,
            "audit_id",
            "finance_v26_measurement_support_predecessor_integrity:",
        ),
        **values,
    )


def _baseline_authority(contract: MeasurementSupportContract) -> BaselineAuthorityAudit:
    functions = (
        support_runtime._acquisition_baseline,  # noqa: SLF001
        support_runtime._operation_baseline,  # noqa: SLF001
        support_runtime._public_baseline_actions,  # noqa: SLF001
        support_runtime._verification_baseline,  # noqa: SLF001
        support_runtime.public_progress_vector,
        support_runtime.public_progress_vector_id,
        support_runtime.resolve_public_baseline_action_set,
    )
    names: list[str] = []
    function_names: list[str] = []
    for function in functions:
        function_names.append(function.__name__)
        tree = ast.parse(inspect.getsource(function))
        names.extend(node.id.casefold() for node in ast.walk(tree) if isinstance(node, ast.Name))
        names.extend(
            node.attr.casefold() for node in ast.walk(tree) if isinstance(node, ast.Attribute)
        )
    banned = (
        "oracle",
        "gold",
        "correct_answer",
        "expected_arguments",
        "future_trajectory",
        "target_evidence",
        "reference_workflow",
    )
    banned_count = sum(any(token in name for token in banned) for name in names)
    if banned_count:
        raise ValueError("v26.146 public baseline policy reads a prohibited symbol")
    values = {
        "support_contract_id": contract.contract_id,
        "audited_function_names": tuple(sorted(function_names)),
        "ast_name_or_attribute_count": len(names),
    }
    provisional = BaselineAuthorityAudit.model_construct(audit_id="pending", **values)
    return BaselineAuthorityAudit(
        audit_id=_identity(
            provisional,
            "audit_id",
            "finance_v26_public_baseline_authority_audit:",
        ),
        **values,
    )


def _independent_baseline_action_ids(state: SemanticActionState) -> tuple[str, ...]:
    candidates = tuple(state.action_candidates)
    selected: tuple[CanonicalPublicAction, ...]
    if state.unresolved_symbols:
        symbol = state.unresolved_symbols[0]
        succeeded_modes = {
            item.acquisition_mode
            for item in state.acquisition_history
            if item.status == "succeeded" and item.target_source_symbols == (symbol,)
        }
        selected = tuple(
            item
            for item in candidates
            if item.decision_kind == "acquire_public_input"
            and item.target_source_symbols == (symbol,)
            and item.acquisition_mode not in succeeded_modes
        )
    else:
        operations = tuple(
            item for item in candidates if item.decision_kind == "execute_public_operation"
        )
        if operations:
            first_node = min(str(item.node_id) for item in operations)
            same_node = tuple(item for item in operations if item.node_id == first_node)
            frontier = next(
                item
                for item in state.operation_frontier
                if item.node_id == first_node and item.frontier_status == "executable"
            )
            matching = tuple(
                item
                for item in same_node
                if frontier.required_output_schema is not None
                and frontier.operator_output_schemas.get(str(item.operator_id))
                == frontier.required_output_schema
            )
            selected = matching or same_node
        else:
            verifications = tuple(
                item for item in candidates if item.decision_kind == "verify_terminal_operation"
            )
            if verifications:
                size = max(len(item.evidence_reference_ids) for item in verifications)
                selected = tuple(
                    item for item in verifications if len(item.evidence_reference_ids) == size
                )
            else:
                selected = tuple(
                    item for item in candidates if item.decision_kind == "emit_final_answer"
                )
    return tuple(sorted(item.action_id for item in selected))


def _wrong_decision_kind(decision_kind: str) -> str:
    kinds = (
        "acquire_public_input",
        "execute_public_operation",
        "verify_terminal_operation",
        "emit_final_answer",
    )
    return next(item for item in kinds if item != decision_kind)


def _state_row(
    *,
    state: SemanticActionState,
    categories: Sequence[StateCategory],
) -> StateClosureRow:
    resolution = support_runtime.resolve_public_baseline_action_set(state)
    independent = _independent_baseline_action_ids(state)
    values = {
        "public_state_id": state.state_id,
        "progress_vector_id": support_runtime.public_progress_vector_id(state),
        "categories": tuple(sorted(set(categories))),
        "visible_action_ids": tuple(sorted(item.action_id for item in state.action_candidates)),
        "independently_recomputed_baseline_action_ids": independent,
        "resolution": resolution,
    }
    provisional = StateClosureRow.model_construct(row_id="pending", **values)
    return StateClosureRow(
        row_id=_identity(
            provisional,
            "row_id",
            "finance_v26_measurement_support_state_closure_row:",
        ),
        **values,
    )


def _unavailable_successor_id(
    *,
    state: SemanticActionState,
    selected_action_id: str,
    observation_status: str | None,
) -> str:
    return canonical_hash(
        {
            "state_id_before": state.state_id,
            "selected_action_id": selected_action_id,
            "observation_status": observation_status,
        },
        prefix="prospective_unavailable_public_successor:",
    )


def _event_decision(
    *,
    state: SemanticActionState,
    after: SemanticActionState | None,
    selected_action_id: str,
    observation_status: Literal["succeeded", "failed"] | None,
    event_kind: Literal[
        "public_observation",
        "terminal_verification",
        "final_commit",
        "non_public_commit",
    ],
) -> tuple[MeasurementSupportDecision, int]:
    before_progress = support_runtime.public_progress_vector_id(state)
    after_id = (
        after.state_id
        if after is not None
        else _unavailable_successor_id(
            state=state,
            selected_action_id=selected_action_id,
            observation_status=observation_status,
        )
    )
    event = make_measurement_support_event(
        event_kind=event_kind,
        public_state_id_before=state.state_id,
        public_state_id_after=after_id,
        progress_vector_id_before=before_progress,
        progress_vector_id_after=(
            support_runtime.public_progress_vector_id(after)
            if after is not None
            else before_progress
        ),
        selected_action_id=selected_action_id,
        observation_status=observation_status,
        successor_public_state_available=after is not None,
    )
    call_count = 0

    def resolve() -> BaselineActionSetResolution:
        nonlocal call_count
        call_count += 1
        return support_runtime.resolve_public_baseline_action_set(state)

    return classify_measurement_support(event, baseline_resolver=resolve), call_count


def _event_row(
    *,
    execution: Any,
    state_index: int,
    state: SemanticActionState,
    after: SemanticActionState | None,
    candidate: CanonicalPublicAction,
    observation_id: str | None,
    observation_error_code: str | None = None,
    observation_status: Literal["succeeded", "failed"] | None,
    decision: MeasurementSupportDecision,
    baseline_classifier_call_count: int,
) -> EventClosureRow:
    state_id_after = (
        after.state_id
        if after is not None
        else _unavailable_successor_id(
            state=state,
            selected_action_id=candidate.action_id,
            observation_status=observation_status,
        )
    )
    values = {
        "predecessor_path_id": execution.path.path_id,
        "role": execution.path.role,
        "mechanism_id": execution.path.mechanism_id,
        "tier": execution.path.tier,
        "reference_state_index": state_index,
        "state_id_before": state.state_id,
        "state_id_after": state_id_after,
        "selected_action_id": candidate.action_id,
        "decision_kind": candidate.decision_kind,
        "observation_id": observation_id,
        "observation_error_code": observation_error_code,
        "observation_status": observation_status,
        "successor_state_available": after is not None,
        "progress_vector_changed": (
            after is not None
            and support_runtime.public_progress_vector_id(state)
            != support_runtime.public_progress_vector_id(after)
        ),
        "baseline_classifier_call_count": baseline_classifier_call_count,
        "decision": decision,
    }
    provisional = EventClosureRow.model_construct(row_id="pending", **values)
    return EventClosureRow(
        row_id=_identity(
            provisional,
            "row_id",
            "finance_v26_measurement_support_event_closure_row:",
        ),
        **values,
    )


def _support_closure(
    *,
    package_root: Path,
    implementation_root: Path,
    contract: MeasurementSupportContract,
    authority: BaselineAuthorityAudit,
) -> SupportClosureCensus:
    inputs = capability_preflight._load_role_inputs(  # noqa: SLF001
        package_root=package_root,
        implementation_root=implementation_root,
    )
    executions = tuple(inputs.immediate.executions)
    if (
        len(executions) != REGISTERED_PATH_COUNT
        or sum(len(item.states) for item in executions) != REGISTERED_STATE_COUNT
    ):
        raise ValueError("v26.146 registered role support surface changed")

    state_values: dict[str, tuple[SemanticActionState, set[StateCategory]]] = {}

    def add_state(state: SemanticActionState, *categories: StateCategory) -> None:
        existing = state_values.get(state.state_id)
        if existing is None:
            state_values[state.state_id] = (state, set(categories))
            return
        if existing[0] != state:
            raise ValueError("v26.146 one state ID reconstructed two public states")
        existing[1].update(categories)

    event_rows: list[EventClosureRow] = []
    semantic_recovery_states: set[str] = set()
    for execution in executions:
        package = execution.task.package
        record = package.operational_record
        environment = package.environment
        task = record.task_package.task.public
        for state_index, state in enumerate(execution.states):
            categories: list[StateCategory] = [
                "registered_reference_state",
                "abi_rescue_state",
            ]
            if state.blocked_actions:
                categories.append("blocked_action_state")
            if any(
                item.decision_kind == "verify_terminal_operation"
                for item in state.action_candidates
            ):
                categories.append("terminal_verification_state")
            add_state(state, *categories)

            reference = execution.proposals[state_index]
            invalid = make_canonical_action_proposal(
                state_id=state.state_id,
                action_id=reference.action_id,
                decision_kind=cast(Any, _wrong_decision_kind(reference.decision_kind)),
            )
            rejected = evaluate_canonical_action_proposal(
                state,
                invalid,
                call_index=state_index + 1,
            ).rejection
            if rejected is None:
                raise ValueError("v26.146 semantic-recovery state fixture did not reject")
            recovery_state = build_semantic_action_state(
                task,
                environment,
                tuple(execution.observations[:state_index]),
                semantic_rejections=(rejected,),
            )
            add_state(recovery_state, "semantic_recovery_state")
            semantic_recovery_states.add(recovery_state.state_id)

            for candidate in state.action_candidates:
                proposal = make_canonical_action_proposal(
                    state_id=state.state_id,
                    action_id=candidate.action_id,
                    decision_kind=candidate.decision_kind,
                )
                selected = evaluate_canonical_action_proposal(
                    state,
                    proposal,
                    call_index=state_index + 1,
                )
                if selected.commit is None or selected.rejection is not None:
                    raise ValueError("v26.146 visible Candidate did not Commit")
                commit = selected.commit
                if commit.call is None:
                    kind = "final_commit" if commit.action == "emit_final" else "non_public_commit"
                    decision, calls = _event_decision(
                        state=state,
                        after=state,
                        selected_action_id=candidate.action_id,
                        observation_status=None,
                        event_kind=cast(Any, kind),
                    )
                    event_rows.append(
                        _event_row(
                            execution=execution,
                            state_index=state_index,
                            state=state,
                            after=state,
                            candidate=candidate,
                            observation_id=None,
                            observation_status=None,
                            decision=decision,
                            baseline_classifier_call_count=calls,
                        )
                    )
                    continue
                runtime = capability_preflight.role_base.predecessor._runtime(  # noqa: SLF001
                    record,
                    environment,
                )
                observation = capability_preflight.role_base.predecessor._execute_observation(  # noqa: E501, SLF001
                    record=record,
                    environment=environment,
                    runtime=runtime,
                    observations=tuple(execution.observations[:state_index]),
                    projection=CompletionProjection(
                        request_kind="decision",
                        action="call_tool",
                        tool_id=commit.call.tool_id,
                        arguments=commit.call.arguments,
                    ),
                )
                try:
                    after: SemanticActionState | None = build_semantic_action_state(
                        task,
                        environment,
                        (*execution.observations[:state_index], observation),
                    )
                except ValueError as exc:
                    if str(exc) != "semantic action state has no selectable public action":
                        raise
                    after = None
                status = cast(Literal["succeeded", "failed"], observation.status)
                if after is None:
                    decision, calls = _event_decision(
                        state=state,
                        after=None,
                        selected_action_id=candidate.action_id,
                        observation_status=status,
                        event_kind="public_observation",
                    )
                    event_rows.append(
                        _event_row(
                            execution=execution,
                            state_index=state_index,
                            state=state,
                            after=None,
                            candidate=candidate,
                            observation_id=observation.observation_id,
                            observation_error_code=observation.error_code,
                            observation_status=status,
                            decision=decision,
                            baseline_classifier_call_count=calls,
                        )
                    )
                    continue
                if candidate.decision_kind == "verify_terminal_operation":
                    decision, calls = _event_decision(
                        state=state,
                        after=after,
                        selected_action_id=candidate.action_id,
                        observation_status=None,
                        event_kind="terminal_verification",
                    )
                else:
                    decision, calls = _event_decision(
                        state=state,
                        after=after,
                        selected_action_id=candidate.action_id,
                        observation_status=status,
                        event_kind="public_observation",
                    )
                if status == "failed":
                    add_state(after, "failed_observation_successor")
                elif support_runtime.public_progress_vector_id(
                    state
                ) != support_runtime.public_progress_vector_id(after):
                    add_state(after, "progress_observation_successor")
                else:
                    add_state(after, "successful_no_progress_successor")
                    if decision.ordinary_detour_observed:
                        add_state(after, "one_detour_successor")
                event_rows.append(
                    _event_row(
                        execution=execution,
                        state_index=state_index,
                        state=state,
                        after=after,
                        candidate=candidate,
                        observation_id=observation.observation_id,
                        observation_error_code=observation.error_code,
                        observation_status=status,
                        decision=decision,
                        baseline_classifier_call_count=calls,
                    )
                )

    state_rows = tuple(
        sorted(
            (
                _state_row(state=state, categories=tuple(categories))
                for state, categories in state_values.values()
            ),
            key=lambda item: item.public_state_id,
        )
    )
    ordered_events = tuple(sorted(event_rows, key=lambda item: item.row_id))
    failed = tuple(item for item in ordered_events if item.observation_status == "failed")
    progress = tuple(
        item
        for item in ordered_events
        if item.observation_status == "succeeded" and item.progress_vector_changed
    )
    no_progress = tuple(
        item
        for item in ordered_events
        if item.observation_status == "succeeded" and not item.progress_vector_changed
    )
    terminal = tuple(item for item in ordered_events if item.observation_status is None)
    statuses = Counter(item.decision.status for item in ordered_events)
    values = {
        "support_contract_id": contract.contract_id,
        "baseline_authority_audit_id": authority.audit_id,
        "registered_candidate_event_count": len(ordered_events),
        "semantic_recovery_state_count": len(semantic_recovery_states),
        "unique_typed_state_count": len(state_rows),
        "typed_state_resolution_count": len(state_rows),
        "baseline_available_state_count": sum(
            item.resolution.status == "available" for item in state_rows
        ),
        "baseline_unavailable_state_count": sum(
            item.resolution.status == "unavailable" for item in state_rows
        ),
        "failed_observation_event_count": len(failed),
        "failed_observation_not_required_count": sum(
            item.decision.status == "not_required" for item in failed
        ),
        "failed_observation_typed_support_exit_count": sum(
            item.decision.status == "unavailable" for item in failed
        ),
        "progress_observation_event_count": len(progress),
        "successful_no_progress_event_count": len(no_progress),
        "terminal_or_final_event_count": len(terminal),
        "unselectable_successor_event_count": sum(
            not item.successor_state_available for item in ordered_events
        ),
        "unselectable_successor_error_counts": dict(
            sorted(
                Counter(
                    cast(str, item.observation_error_code)
                    for item in ordered_events
                    if not item.successor_state_available
                ).items()
            )
        ),
        "successful_no_progress_baseline_classifier_call_count": sum(
            item.baseline_classifier_call_count for item in no_progress
        ),
        "available_decision_count": statuses["available"],
        "not_required_decision_count": statuses["not_required"],
        "unavailable_decision_count": statuses["unavailable"],
        "baseline_unavailable_decision_count": sum(
            item.successor_state_available and item.decision.status == "unavailable"
            for item in ordered_events
        ),
        "successor_unavailable_decision_count": sum(
            not item.successor_state_available for item in ordered_events
        ),
        "ordinary_detour_event_count": sum(
            item.decision.ordinary_detour_observed for item in ordered_events
        ),
        "typed_measurement_support_exit_count": statuses["unavailable"],
        "state_rows": state_rows,
        "event_rows": ordered_events,
    }
    provisional = SupportClosureCensus.model_construct(audit_id="pending", **values)
    return SupportClosureCensus(
        audit_id=_identity(
            provisional,
            "audit_id",
            "finance_v26_measurement_support_closure_census:",
        ),
        **values,
    )


def _orphan_future_control(
    *,
    package_root: Path,
    contract: MeasurementSupportContract,
) -> OrphanFutureContractControl:
    root = failed_audit.OrphanRootCauseAudit.model_validate(
        _load(package_root / FAILED_AUDIT_DIR / "orphan_root_cause_audit.json")
    )
    rows: list[OrphanFutureControlRow] = []
    for historical in root.orphan_rows:
        progress_id = canonical_hash(
            {
                "initial_state_id": historical.initial_state_id,
                "successor_state_id": historical.successor_state_id,
                "progress_vector_changed": False,
            },
            prefix="finance_v26_orphan_equal_progress_vector:",
        )
        event = make_measurement_support_event(
            event_kind="public_observation",
            public_state_id_before=historical.initial_state_id,
            public_state_id_after=historical.successor_state_id,
            progress_vector_id_before=progress_id,
            progress_vector_id_after=progress_id,
            selected_action_id=historical.selected_action_id,
            observation_status="failed",
        )
        baseline_calls = 0

        def forbidden_baseline() -> BaselineActionSetResolution:
            nonlocal baseline_calls
            baseline_calls += 1
            raise AssertionError("failed Observation must not resolve a baseline")

        decision = classify_measurement_support(
            event,
            baseline_resolver=forbidden_baseline,
        )
        if baseline_calls:
            raise ValueError("v26.146 orphan control invoked a baseline classifier")
        values = {
            "historical_job_id": historical.job_id,
            "historical_initial_state_id": historical.initial_state_id,
            "historical_successor_state_id": historical.successor_state_id,
            "future_decision": decision,
        }
        provisional = OrphanFutureControlRow.model_construct(row_id="pending", **values)
        rows.append(
            OrphanFutureControlRow(
                row_id=_identity(
                    provisional,
                    "row_id",
                    "finance_v26_orphan_future_support_control_row:",
                ),
                **values,
            )
        )
    values = {
        "support_contract_id": contract.contract_id,
        "historical_root_cause_audit_id": root.audit_id,
        "rows": tuple(sorted(rows, key=lambda item: item.row_id)),
    }
    provisional = OrphanFutureContractControl.model_construct(audit_id="pending", **values)
    return OrphanFutureContractControl(
        audit_id=_identity(
            provisional,
            "audit_id",
            "finance_v26_orphan_future_support_control:",
        ),
        **values,
    )


def _transition(
    *,
    contract: MeasurementSupportContract,
    census: SupportClosureCensus,
    orphan: OrphanFutureContractControl,
) -> ProspectiveTransitionContract:
    values = {
        "support_contract_id": contract.contract_id,
        "support_closure_census_id": census.audit_id,
        "orphan_future_control_id": orphan.audit_id,
    }
    provisional = ProspectiveTransitionContract.model_construct(
        contract_id="pending",
        **values,
    )
    return ProspectiveTransitionContract(
        contract_id=_identity(
            provisional,
            "contract_id",
            "finance_v26_measurement_support_transition:",
        ),
        **values,
    )


def _validated_copy(value: BaseModel, updates: Mapping[str, Any]) -> BaseModel:
    payload = value.model_dump(mode="json")
    payload.update(updates)
    return type(value).model_validate(payload)


def _expect_rejected(name: str, callback: Callable[[], Any]) -> MutationResult:
    try:
        callback()
    except (AssertionError, TypeError, ValueError):
        return MutationResult(mutation_name=name)
    raise AssertionError(f"v26.146 destructive mutation was accepted: {name}")


def _destructive(
    *,
    contract: MeasurementSupportContract,
    census: SupportClosureCensus,
    transition: ProspectiveTransitionContract,
) -> DestructiveAudit:
    failed = next(item for item in census.event_rows if item.observation_status == "failed")
    progress = next(
        item
        for item in census.event_rows
        if item.observation_status == "succeeded" and item.progress_vector_changed
    )
    available_state = next(
        item for item in census.state_rows if item.resolution.status == "available"
    )
    mutations = (
        _expect_rejected(
            "baseline_action_outside_visible_candidates",
            lambda: _validated_copy(
                available_state,
                {
                    "independently_recomputed_baseline_action_ids": (
                        *available_state.independently_recomputed_baseline_action_ids,
                        "not-visible",
                    )
                },
            ),
        ),
        _expect_rejected(
            "baseline_deletes_independently_recomputed_action",
            lambda: _validated_copy(
                available_state,
                {"independently_recomputed_baseline_action_ids": ()},
            ),
        ),
        _expect_rejected(
            "empty_available_baseline_set",
            lambda: _validated_copy(
                available_state.resolution,
                {"baseline_action_ids": ()},
            ),
        ),
        _expect_rejected(
            "failed_observation_counted_as_detour",
            lambda: _validated_copy(
                failed.decision,
                {"ordinary_detour_observed": True},
            ),
        ),
        _expect_rejected(
            "failed_observation_invokes_baseline",
            lambda: _validated_copy(
                failed.decision,
                {"baseline_classifier_invoked": True},
            ),
        ),
        _expect_rejected(
            "final_grammar_change_authorized",
            lambda: _validated_copy(transition, {"final_grammar_change_authorized": True}),
        ),
        _expect_rejected(
            "historical_v26_141_reclassified",
            lambda: _validated_copy(
                transition,
                {"historical_terminal_or_validity_reclassification_authorized": True},
            ),
        ),
        _expect_rejected(
            "maximum_ordinary_detours_increased",
            lambda: _validated_copy(contract, {"maximum_ordinary_detours": 2}),
        ),
        _expect_rejected(
            "new_capability_population_materialized",
            lambda: _validated_copy(
                transition,
                {"new_capability_population_or_identity_materialization_authorized": True},
            ),
        ),
        _expect_rejected(
            "noncanonical_baseline_action_set",
            lambda: _validated_copy(
                available_state.resolution,
                {
                    "baseline_action_ids": (
                        available_state.resolution.baseline_action_ids[0],
                        available_state.resolution.baseline_action_ids[0],
                    )
                },
            ),
        ),
        _expect_rejected(
            "progress_observation_invokes_baseline",
            lambda: _validated_copy(
                progress.decision,
                {"baseline_classifier_invoked": True},
            ),
        ),
        _expect_rejected(
            "provider_call_authorized",
            lambda: _validated_copy(transition, {"provider_calls_authorized": True}),
        ),
        _expect_rejected(
            "stage_two_provider_call_added",
            lambda: _validated_copy(contract, {"stage_two_provider_calls": 1}),
        ),
        _expect_rejected(
            "state_mapping_authorized",
            lambda: _validated_copy(transition, {"state_mapping_authorized": True}),
        ),
        _expect_rejected(
            "support_unavailable_reclassified_as_model_invalid",
            lambda: _validated_copy(contract, {"unavailable_is_model_invalid": True}),
        ),
        _expect_rejected(
            "verifier_change_authorized",
            lambda: _validated_copy(transition, {"verifier_change_authorized": True}),
        ),
    )
    ordered = tuple(sorted(mutations, key=lambda item: item.mutation_name))
    values = {
        "support_contract_id": contract.contract_id,
        "support_closure_census_id": census.audit_id,
        "transition_contract_id": transition.contract_id,
        "mutation_results": ordered,
    }
    provisional = DestructiveAudit.model_construct(audit_id="pending", **values)
    return DestructiveAudit(
        audit_id=_identity(
            provisional,
            "audit_id",
            "finance_v26_measurement_support_destructive:",
        ),
        **values,
    )


def _detail(path: Path, output_dir: Path) -> DetailFile:
    return DetailFile(
        relative_path=str(path.relative_to(output_dir)),
        sha256=_sha256(path),
        byte_count=path.stat().st_size,
    )


def build_measurement_support_redesign(
    *,
    package_root: Path,
    implementation_root: Path,
    output_dir: Path,
) -> MeasurementSupportRedesignReport:
    source = _source_replay(
        package_root=package_root,
        implementation_root=implementation_root,
    )
    predecessor_integrity = _predecessor_integrity(
        package_root=package_root,
        implementation_root=implementation_root,
        source_replay=source,
    )
    contract = make_measurement_support_contract()
    authority = _baseline_authority(contract)
    census = _support_closure(
        package_root=package_root,
        implementation_root=implementation_root,
        contract=contract,
        authority=authority,
    )
    orphan = _orphan_future_control(package_root=package_root, contract=contract)
    transition = _transition(contract=contract, census=census, orphan=orphan)
    destructive = _destructive(contract=contract, census=census, transition=transition)

    output_dir.mkdir(parents=True, exist_ok=True)
    outputs: tuple[tuple[str, BaseModel], ...] = (
        ("baseline_authority_audit.json", authority),
        ("destructive_audit.json", destructive),
        ("measurement_support_contract.json", contract),
        ("orphan_future_contract_control.json", orphan),
        ("predecessor_integrity_audit.json", predecessor_integrity),
        ("prospective_transition_contract.json", transition),
        ("source_replay_audit.json", source),
        ("support_closure_census.json", census),
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
        "measurement_support_contract_id": contract.contract_id,
        "baseline_authority_audit_id": authority.audit_id,
        "support_closure_census_id": census.audit_id,
        "orphan_future_control_id": orphan.audit_id,
        "destructive_audit_id": destructive.audit_id,
        "transition_contract_id": transition.contract_id,
        "registered_candidate_event_count": census.registered_candidate_event_count,
        "unique_typed_state_count": census.unique_typed_state_count,
        "failed_observation_event_count": census.failed_observation_event_count,
        "failed_observation_not_required_count": (census.failed_observation_not_required_count),
        "failed_observation_typed_support_exit_count": (
            census.failed_observation_typed_support_exit_count
        ),
        "progress_observation_event_count": census.progress_observation_event_count,
        "successful_no_progress_event_count": (census.successful_no_progress_event_count),
        "ordinary_detour_event_count": census.ordinary_detour_event_count,
        "baseline_unavailable_decision_count": (census.baseline_unavailable_decision_count),
        "successor_unavailable_decision_count": (census.successor_unavailable_decision_count),
        "detail_files": details,
    }
    provisional = MeasurementSupportRedesignReport.model_construct(
        report_id="pending",
        **values,
    )
    report = MeasurementSupportRedesignReport(
        report_id=_identity(
            provisional,
            "report_id",
            "finance_v26_measurement_support_redesign_report:",
        ),
        **values,
    )
    _write_json_atomic(output_dir / "report.json", report)
    return report


def main() -> None:
    package_default = Path(__file__).resolve().parents[4]
    parser = argparse.ArgumentParser(
        description="Design and audit the v26.146 typed measurement-support boundary"
    )
    parser.add_argument("--package-root", type=Path, default=package_default)
    parser.add_argument("--implementation-root", type=Path, default=package_default)
    parser.add_argument("--output-dir", type=Path, default=package_default / OUTPUT_DIR)
    args = parser.parse_args()
    report = build_measurement_support_redesign(
        package_root=args.package_root,
        implementation_root=args.implementation_root,
        output_dir=args.output_dir,
    )
    print(report.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
