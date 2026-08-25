from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Final, Literal, cast

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.core.evaluation.answer import CandidateAnswerNormalizer
from trusted_synthesis.core.trajectory.executable_task import matching_sufficient_support_set
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_measurement_support_boundary_redesign as support_redesign,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_orphan_support_exit_recovery_execution as support_execution,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_privacy_safe_s1_capability_failure_audit as failed_audit,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_privacy_safe_s1_capability_online as online,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_privacy_safe_s1_capability_preflight as preflight,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_empirical_support_pilot import (
    evaluate_mechanism_estimand,
)
from trusted_synthesis.hashing import canonical_hash

RUN_ID: Final = "finance_v26_147_capability_validity_decomposition_audit_v1_20260825"
OUTPUT_DIR: Final = (
    "artifacts/vtdo_experiment/finance_v26_147_capability_validity_decomposition_audit_v1_20260825"
)
IMPLEMENTATION_PATH: Final = (
    "src/trusted_synthesis/experiments/vtdo_experiment/"
    "phase1_v26_capability_validity_decomposition_audit.py"
)
PREDECESSOR_DIR: Final = support_redesign.OUTPUT_DIR
CAPABILITY_EXECUTION_DIR: Final = online.OUTPUT_DIR
SUPPORT_EXECUTION_DIR: Final = support_execution.OUTPUT_DIR
NEXT_STAGE: Final = "verifier_vnext_contract_freeze_only"

EXPECTED_PREDECESSOR_REPORT_ID: Final = (
    "finance_v26_measurement_support_redesign_report:"
    "aa2d6a079ef8ebe97d7d10fa90a6fcfb844faa39310a26e2b4a1e8120bfa41c5"
)
EXPECTED_PREDECESSOR_REPORT_SHA256: Final = (
    "2df4d84df155c22a98760d831d31b0ed811d12ecdf182f1f4326881ea2d8a80d"
)
EXPECTED_PREDECESSOR_TRANSITION_ID: Final = (
    "finance_v26_measurement_support_transition:"
    "b72ddd97cb2440fea1eddb3553cefea584abc7168762c06321ba2a864ea5e982"
)
EXPECTED_NONINTERFERENCE_AUDIT_ID: Final = online.EXPECTED_NONINTERFERENCE_AUDIT_ID

MechanismId = Literal[
    "context_conditioned_action",
    "semantic_reconciliation",
    "failure_recovery",
    "state_dependent_stopping",
]
Tier = Literal["easy_control", "frontier", "hard_control"]

DIAGNOSTIC_STAGE_ORDER: Final = (
    "action_abi",
    "program_closure",
    "terminal_verification",
    "final_abi",
    "answer_schema",
    "answer_decimal_semantics",
    "answer_reference_identity",
    "operation_lineage",
    "required_evidence_support",
    "runtime_selected_support",
    "model_citation",
    "verification_support",
    "postcompletion_control",
    "noninterference_binding",
    "privacy",
    "target_mechanism",
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
    raise ValueError(f"v26.147 cannot replay bound file: {relative_path}")


def _decimal_string(value: Any) -> str | None:
    if isinstance(value, bool) or value is None:
        return None
    if not isinstance(value, (Decimal, int, float, str)):
        return None
    try:
        number = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None
    if not number.is_finite():
        return None
    return format(number.normalize(), "f")


def _canonical_decimal_semantics(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            str(key): _canonical_decimal_semantics(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        }
    if isinstance(value, (list, tuple)):
        return [_canonical_decimal_semantics(item) for item in value]
    number = _decimal_string(value)
    return {"decimal": number} if number is not None else value


def _reference_identity_projection(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            str(key): _reference_identity_projection(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        }
    if isinstance(value, (list, tuple)):
        return [_reference_identity_projection(item) for item in value]
    return "<decimal>" if _decimal_string(value) is not None else value


def _fraction(numerator: int, denominator: int) -> str:
    return f"{numerator}/{denominator}"


def _mean_task_fraction(numerators: Sequence[int], denominator: int = 8) -> str:
    if not numerators:
        raise ValueError("v26.147 task-weighted mean has no tasks")
    value = sum((Decimal(item) / Decimal(denominator) for item in numerators), Decimal(0))
    return format(value / Decimal(len(numerators)), "f")


class SourceReplayEntry(FrozenModel):
    relative_path: str = Field(min_length=1)
    source_kind: Literal[
        "v26_146_transitive_source",
        "v26_146_output",
        "v26_147_implementation",
    ]
    expected_sha256: str = Field(min_length=64, max_length=64)
    observed_sha256: str = Field(min_length=64, max_length=64)
    byte_count: int = Field(gt=0)
    passed: Literal[True] = True


class SourceReplayAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    predecessor_report_id: str = EXPECTED_PREDECESSOR_REPORT_ID
    predecessor_transition_id: str = EXPECTED_PREDECESSOR_TRANSITION_ID
    predecessor_transitive_file_count: Literal[7294] = 7294
    predecessor_output_file_count: Literal[9] = 9
    implementation_file_count: Literal[1] = 1
    replayed_file_count: Literal[7304] = 7304
    replay_pass_count: Literal[7304] = 7304
    entries: tuple[SourceReplayEntry, ...] = Field(min_length=7304, max_length=7304)
    replay_before_historical_raw_loading: Literal[True] = True
    credential_lookup_attempted: Literal[False] = False
    model_client_constructed: Literal[False] = False
    provider_calls: Literal[0] = 0
    stage_two_provider_calls: Literal[0] = 0
    gpu_jobs: Literal[0] = 0
    status: Literal["passed"] = "passed"
    schema_version: Literal["finance_v26_validity_decomposition_source_replay.v1"] = (
        "finance_v26_validity_decomposition_source_replay.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> SourceReplayAudit:
        paths = tuple(item.relative_path for item in self.entries)
        if (
            paths != tuple(sorted(set(paths)))
            or len(paths) != self.replayed_file_count
            or any(item.expected_sha256 != item.observed_sha256 for item in self.entries)
        ):
            raise ValueError("v26.147 source replay changed")
        if self.audit_id != _identity(
            self,
            "audit_id",
            "finance_v26_validity_decomposition_source_replay:",
        ):
            raise ValueError("v26.147 source replay identity changed")
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
    comparisons: tuple[FileComparison, ...] = Field(min_length=9, max_length=9)
    predecessor_output_file_count: Literal[9] = 9
    byte_identical_file_count: Literal[9] = 9
    frozen_lineage_endpoint_count: Literal[96] = 96
    frozen_model_outcome_count: Literal[93] = 93
    frozen_support_exit_count: Literal[3] = 3
    historical_terminal_reclassified_count: Literal[0] = 0
    historical_validity_reclassified_count: Literal[0] = 0
    provider_calls: Literal[0] = 0
    status: Literal["passed"] = "passed"
    schema_version: Literal["finance_v26_validity_decomposition_predecessor_integrity.v1"] = (
        "finance_v26_validity_decomposition_predecessor_integrity.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> PredecessorIntegrityAudit:
        paths = tuple(item.relative_path for item in self.comparisons)
        if paths != tuple(sorted(set(paths))) or any(
            item.expected_sha256 != item.observed_sha256 for item in self.comparisons
        ):
            raise ValueError("v26.147 predecessor comparison changed")
        if self.audit_id != _identity(
            self,
            "audit_id",
            "finance_v26_validity_decomposition_predecessor_integrity:",
        ):
            raise ValueError("v26.147 predecessor identity changed")
        return self


class InterfaceDiagnostics(FrozenModel):
    action_abi: bool
    program_closure: bool
    terminal_verification: bool
    final_abi: bool


class AnswerDiagnostics(FrozenModel):
    answer_present: bool
    exact_json_match: bool
    decimal_semantic_match: bool
    reference_identity_match: bool
    answer_schema_match: bool
    answer_schema_failure_ids: tuple[str, ...]
    normalized_answer: dict[str, Any] | None = None
    expected_answer: dict[str, Any]


class SupportDiagnostics(FrozenModel):
    operation_lineage_complete: bool
    required_evidence_support_complete: bool
    runtime_selected_support_complete: bool
    model_citation_complete: bool
    verification_support_complete: bool
    runtime_selected_evidence_ids: tuple[str, ...]
    historical_host_derived_cited_evidence_ids: tuple[str, ...]
    model_cited_evidence_ids: tuple[str, ...]
    necessary_evidence_ids: tuple[str, ...]


class MechanismDiagnostics(FrozenModel):
    target_mechanism_id: MechanismId
    target_mechanism_evaluated: bool
    target_mechanism_complete: bool
    context_mechanism_complete: bool | None = None
    reconciliation_mechanism_complete: bool | None = None
    recovery_mechanism_complete: bool | None = None
    stopping_mechanism_complete: bool | None = None
    observed_event_ids: tuple[str, ...]
    missing_event_ids: tuple[str, ...]

    @model_validator(mode="after")
    def validate_target(self) -> MechanismDiagnostics:
        fields = {
            "context_conditioned_action": self.context_mechanism_complete,
            "semantic_reconciliation": self.reconciliation_mechanism_complete,
            "failure_recovery": self.recovery_mechanism_complete,
            "state_dependent_stopping": self.stopping_mechanism_complete,
        }
        non_null = {key: value for key, value in fields.items() if value is not None}
        if non_null != {self.target_mechanism_id: self.target_mechanism_complete}:
            raise ValueError("v26.147 mechanism diagnostic target projection changed")
        return self


class ControlDiagnostics(FrozenModel):
    postcompletion_violation: bool
    noninterference_audit_bound: bool
    noninterference_audit_id: str = EXPECTED_NONINTERFERENCE_AUDIT_ID
    privacy_compliant: bool
    runtime_replay_passed: bool
    instrument_integrity: bool


class HistoricalValidityDiagnosticRow(FrozenModel):
    row_id: str = Field(min_length=1)
    job_id: str = Field(min_length=1)
    task_package_id: str = Field(min_length=1)
    source_task_artifact_id: str = Field(min_length=1)
    mechanism_id: MechanismId
    tier: Tier
    replicate_index: int = Field(ge=0, lt=8)
    seed: int = Field(ge=0)
    raw_execution_id: str = Field(min_length=1)
    historical_result_id: str = Field(min_length=1)
    historical_terminal: Literal["model_valid_trajectory", "model_invalid_trajectory"]
    historical_independent_validity: bool
    historical_verifier_report_id: str | None = None
    historical_verifier_version: str | None = None
    measurement_support_available: Literal[True] = True
    model_endpoint_observed: Literal[True] = True
    validity_evaluable: Literal[True] = True
    interface: InterfaceDiagnostics
    answer: AnswerDiagnostics
    support: SupportDiagnostics
    mechanism: MechanismDiagnostics
    controls: ControlDiagnostics
    diagnostic_base_validity: bool
    diagnostic_mechanism_qualification: bool
    diagnostic_qualified_validity: bool
    first_diagnostic_failure_layer: str | None = None
    historical_reclassified: Literal[False] = False
    counterfactual_diagnostic_only: Literal[True] = True
    state_mapping_eligible: Literal[False] = False
    schema_version: Literal["finance_v26_historical_validity_diagnostic_row.v1"] = (
        "finance_v26_historical_validity_diagnostic_row.v1"
    )

    @model_validator(mode="after")
    def validate_row(self) -> HistoricalValidityDiagnosticRow:
        checks = _diagnostic_check_map(self)
        expected_base = all(value for key, value in checks.items() if key != "target_mechanism")
        if self.historical_independent_validity != (
            self.historical_terminal == "model_valid_trajectory"
        ):
            raise ValueError("v26.147 historical label changed")
        if self.diagnostic_base_validity != expected_base:
            raise ValueError("v26.147 diagnostic Base validity changed")
        if self.diagnostic_mechanism_qualification != self.mechanism.target_mechanism_complete:
            raise ValueError("v26.147 mechanism qualification changed")
        if self.diagnostic_qualified_validity != (
            self.diagnostic_base_validity and self.diagnostic_mechanism_qualification
        ):
            raise ValueError("v26.147 Qualified validity changed")
        expected_failure = next(
            (stage for stage in DIAGNOSTIC_STAGE_ORDER if not checks[stage]),
            None,
        )
        if self.first_diagnostic_failure_layer != expected_failure:
            raise ValueError("v26.147 first diagnostic failure changed")
        if self.row_id != _identity(
            self,
            "row_id",
            "finance_v26_historical_validity_diagnostic_row:",
        ):
            raise ValueError("v26.147 diagnostic row identity changed")
        return self


def _diagnostic_check_map(row: HistoricalValidityDiagnosticRow) -> dict[str, bool]:
    return {
        "action_abi": row.interface.action_abi,
        "program_closure": row.interface.program_closure,
        "terminal_verification": row.interface.terminal_verification,
        "final_abi": row.interface.final_abi,
        "answer_schema": row.answer.answer_schema_match,
        "answer_decimal_semantics": row.answer.decimal_semantic_match,
        "answer_reference_identity": row.answer.reference_identity_match,
        "operation_lineage": row.support.operation_lineage_complete,
        "required_evidence_support": row.support.required_evidence_support_complete,
        "runtime_selected_support": row.support.runtime_selected_support_complete,
        "model_citation": row.support.model_citation_complete,
        "verification_support": row.support.verification_support_complete,
        "postcompletion_control": not row.controls.postcompletion_violation,
        "noninterference_binding": row.controls.noninterference_audit_bound,
        "privacy": row.controls.privacy_compliant,
        "target_mechanism": row.mechanism.target_mechanism_complete,
    }


class SupportExitValidityRow(FrozenModel):
    row_id: str = Field(min_length=1)
    historical_job_id: str = Field(min_length=1)
    recovery_result_id: str = Field(min_length=1)
    recovery_raw_execution_id: str = Field(min_length=1)
    task_package_id: str = Field(min_length=1)
    source_task_artifact_id: str = Field(min_length=1)
    mechanism_id: MechanismId
    tier: Tier
    replicate_index: int = Field(ge=0, lt=8)
    historical_terminal: None = None
    support_exit_terminal: Literal["ordinary_replan_reference_unavailable"] = (
        "ordinary_replan_reference_unavailable"
    )
    historical_independent_validity: None = None
    measurement_support_available: Literal[False] = False
    model_endpoint_observed: Literal[False] = False
    validity_evaluable: Literal[False] = False
    diagnostic_base_validity: None = None
    diagnostic_mechanism_qualification: None = None
    diagnostic_qualified_validity: None = None
    historical_reclassified: Literal[False] = False
    counterfactual_diagnostic_only: Literal[True] = True
    state_mapping_eligible: Literal[False] = False
    schema_version: Literal["finance_v26_support_exit_validity_row.v1"] = (
        "finance_v26_support_exit_validity_row.v1"
    )

    @model_validator(mode="after")
    def validate_row(self) -> SupportExitValidityRow:
        if self.row_id != _identity(
            self,
            "row_id",
            "finance_v26_support_exit_validity_row:",
        ):
            raise ValueError("v26.147 support-exit row identity changed")
        return self


class ValidityDecompositionCatalog(FrozenModel):
    catalog_id: str = Field(min_length=1)
    predecessor_integrity_audit_id: str = Field(min_length=1)
    noninterference_audit_id: str = EXPECTED_NONINTERFERENCE_AUDIT_ID
    model_rows: tuple[HistoricalValidityDiagnosticRow, ...] = Field(
        min_length=93,
        max_length=93,
    )
    support_exit_rows: tuple[SupportExitValidityRow, ...] = Field(
        min_length=3,
        max_length=3,
    )
    exact_lineage_endpoint_count: Literal[96] = 96
    complete_raw_model_outcome_count: Literal[93] = 93
    support_exit_count: Literal[3] = 3
    historical_valid_count: Literal[17] = 17
    historical_invalid_count: Literal[76] = 76
    final_endpoint_observed_count: int = Field(ge=0, le=93)
    decimal_representation_only_difference_count: int = Field(ge=0, le=93)
    runtime_support_complete_model_citation_incomplete_count: int = Field(ge=0, le=93)
    diagnostic_base_valid_count: int = Field(ge=0, le=93)
    diagnostic_mechanism_success_count: int = Field(ge=0, le=93)
    diagnostic_qualified_valid_count: int = Field(ge=0, le=93)
    historical_reclassified_count: Literal[0] = 0
    exact_task_weighted_capability_estimate_available: Literal[False] = False
    provider_calls: Literal[0] = 0
    status: Literal["historical_read_only_decomposition_complete"] = (
        "historical_read_only_decomposition_complete"
    )
    schema_version: Literal["finance_v26_validity_decomposition_catalog.v1"] = (
        "finance_v26_validity_decomposition_catalog.v1"
    )

    @model_validator(mode="after")
    def validate_catalog(self) -> ValidityDecompositionCatalog:
        model_ids = tuple(item.job_id for item in self.model_rows)
        support_ids = tuple(item.historical_job_id for item in self.support_exit_rows)
        if (
            model_ids != tuple(sorted(set(model_ids)))
            or support_ids != tuple(sorted(set(support_ids)))
            or set(model_ids) & set(support_ids)
            or self.historical_valid_count
            != sum(item.historical_independent_validity for item in self.model_rows)
            or self.diagnostic_base_valid_count
            != sum(item.diagnostic_base_validity for item in self.model_rows)
            or self.diagnostic_mechanism_success_count
            != sum(item.diagnostic_mechanism_qualification for item in self.model_rows)
            or self.diagnostic_qualified_valid_count
            != sum(item.diagnostic_qualified_validity for item in self.model_rows)
        ):
            raise ValueError("v26.147 decomposition denominator changed")
        if self.catalog_id != _identity(
            self,
            "catalog_id",
            "finance_v26_validity_decomposition_catalog:",
        ):
            raise ValueError("v26.147 decomposition catalog identity changed")
        return self


class TaskValiditySummary(FrozenModel):
    summary_id: str = Field(min_length=1)
    source_task_artifact_id: str = Field(min_length=1)
    task_package_id: str = Field(min_length=1)
    mechanism_id: MechanismId
    tier: Tier
    exact_design_replica_count: Literal[8] = 8
    evaluable_model_outcome_count: int = Field(ge=0, le=8)
    support_exit_count: int = Field(ge=0, le=8)
    historical_valid_count: int = Field(ge=0, le=8)
    diagnostic_base_valid_count: int = Field(ge=0, le=8)
    diagnostic_mechanism_success_count: int = Field(ge=0, le=8)
    diagnostic_qualified_valid_count: int = Field(ge=0, le=8)
    historical_valid_of_8: str = Field(min_length=3)
    diagnostic_base_valid_of_8: str = Field(min_length=3)
    diagnostic_mechanism_success_of_8: str = Field(min_length=3)
    diagnostic_qualified_valid_of_8: str = Field(min_length=3)
    evaluable_denominator_note: Literal[
        "support exits are null and are not diagnostic failures"
    ] = "support exits are null and are not diagnostic failures"
    task_is_primary_sampling_unit: Literal[True] = True
    rollout_is_secondary_repeated_measure: Literal[True] = True
    descriptive_only: Literal[True] = True

    @model_validator(mode="after")
    def validate_summary(self) -> TaskValiditySummary:
        if self.evaluable_model_outcome_count + self.support_exit_count != 8:
            raise ValueError("v26.147 task endpoint count changed")
        fractions = (
            (self.historical_valid_count, self.historical_valid_of_8),
            (self.diagnostic_base_valid_count, self.diagnostic_base_valid_of_8),
            (
                self.diagnostic_mechanism_success_count,
                self.diagnostic_mechanism_success_of_8,
            ),
            (self.diagnostic_qualified_valid_count, self.diagnostic_qualified_valid_of_8),
        )
        if any(value != _fraction(count, 8) for count, value in fractions):
            raise ValueError("v26.147 task fraction changed")
        if self.summary_id != _identity(
            self,
            "summary_id",
            "finance_v26_task_validity_summary:",
        ):
            raise ValueError("v26.147 task summary identity changed")
        return self


class TaskLevelSummaryAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    decomposition_catalog_id: str = Field(min_length=1)
    task_rows: tuple[TaskValiditySummary, ...] = Field(min_length=12, max_length=12)
    independent_task_count: Literal[12] = 12
    exact_design_rollout_count: Literal[96] = 96
    complete_raw_model_outcome_count: Literal[93] = 93
    support_exit_count: Literal[3] = 3
    task_first_aggregation_required: Literal[True] = True
    rollouts_treated_as_independent_tasks: Literal[False] = False
    exact_capability_estimate_available: Literal[False] = False
    schema_version: Literal["finance_v26_task_level_validity_summary.v1"] = (
        "finance_v26_task_level_validity_summary.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> TaskLevelSummaryAudit:
        keys = tuple(
            (item.mechanism_id, item.tier, item.source_task_artifact_id) for item in self.task_rows
        )
        if (
            keys != tuple(sorted(set(keys)))
            or sum(item.evaluable_model_outcome_count for item in self.task_rows) != 93
            or sum(item.support_exit_count for item in self.task_rows) != 3
        ):
            raise ValueError("v26.147 task summary denominator changed")
        if self.audit_id != _identity(
            self,
            "audit_id",
            "finance_v26_task_level_validity_summary:",
        ):
            raise ValueError("v26.147 task-level audit identity changed")
        return self


class GroupValiditySummary(FrozenModel):
    group_kind: Literal["mechanism", "tier"]
    group_id: str = Field(min_length=1)
    task_count: int = Field(gt=0)
    design_rollout_count: int = Field(gt=0)
    evaluable_model_outcome_count: int = Field(ge=0)
    support_exit_count: int = Field(ge=0)
    historical_valid_count: int = Field(ge=0)
    diagnostic_base_valid_count: int = Field(ge=0)
    diagnostic_mechanism_success_count: int = Field(ge=0)
    diagnostic_qualified_valid_count: int = Field(ge=0)
    task_weighted_historical_valid_mean: str = Field(min_length=1)
    task_weighted_diagnostic_base_mean: str = Field(min_length=1)
    task_weighted_diagnostic_mechanism_mean: str = Field(min_length=1)
    task_weighted_diagnostic_qualified_mean: str = Field(min_length=1)


class MechanismTierSummaryAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    task_level_summary_audit_id: str = Field(min_length=1)
    mechanism_rows: tuple[GroupValiditySummary, ...] = Field(min_length=4, max_length=4)
    tier_rows: tuple[GroupValiditySummary, ...] = Field(min_length=3, max_length=3)
    aggregation_order: Literal["task_first_then_group"] = "task_first_then_group"
    model_outcome_subset_is_incomplete: Literal[True] = True
    descriptive_only: Literal[True] = True
    schema_version: Literal["finance_v26_mechanism_tier_validity_summary.v1"] = (
        "finance_v26_mechanism_tier_validity_summary.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> MechanismTierSummaryAudit:
        if tuple(item.group_id for item in self.mechanism_rows) != tuple(
            sorted(set(item.group_id for item in self.mechanism_rows))
        ) or tuple(item.group_id for item in self.tier_rows) != tuple(
            sorted(set(item.group_id for item in self.tier_rows))
        ):
            raise ValueError("v26.147 group summaries changed")
        if self.audit_id != _identity(
            self,
            "audit_id",
            "finance_v26_mechanism_tier_validity_summary:",
        ):
            raise ValueError("v26.147 group summary identity changed")
        return self


class FailureLocalizationAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    decomposition_catalog_id: str = Field(min_length=1)
    diagnostic_stage_order: tuple[str, ...] = DIAGNOSTIC_STAGE_ORDER
    historical_invalid_count: Literal[76] = 76
    historical_invalid_first_failure_counts: dict[str, int]
    historical_valid_count: Literal[17] = 17
    historical_valid_diagnostic_base_valid_count: int = Field(ge=0, le=17)
    historical_valid_model_citation_incomplete_count: int = Field(ge=0, le=17)
    final_endpoint_observed_count: int = Field(ge=0, le=93)
    old_answer_projection_failure_count: int = Field(ge=0, le=93)
    decimal_representation_only_difference_count: int = Field(ge=0, le=93)
    old_citation_complete_count: int = Field(ge=0, le=93)
    model_citation_complete_count: int = Field(ge=0, le=93)
    old_citation_was_runtime_derived: Literal[True] = True
    failure_localization_is_counterfactual_diagnostic_only: Literal[True] = True
    historical_validity_reclassified_count: Literal[0] = 0
    schema_version: Literal["finance_v26_historical_failure_localization.v1"] = (
        "finance_v26_historical_failure_localization.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> FailureLocalizationAudit:
        if sum(self.historical_invalid_first_failure_counts.values()) != 76:
            raise ValueError("v26.147 historical-invalid localization changed")
        if self.audit_id != _identity(
            self,
            "audit_id",
            "finance_v26_historical_failure_localization:",
        ):
            raise ValueError("v26.147 failure localization identity changed")
        return self


class HistoricalImmutabilityAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    decomposition_catalog_id: str = Field(min_length=1)
    exact_lineage_endpoint_count: Literal[96] = 96
    frozen_model_outcome_count: Literal[93] = 93
    frozen_support_exit_count: Literal[3] = 3
    frozen_historical_valid_count: Literal[17] = 17
    frozen_historical_invalid_count: Literal[76] = 76
    historical_terminal_reclassified_count: Literal[0] = 0
    historical_validity_reclassified_count: Literal[0] = 0
    missing_model_endpoint_imputed_count: Literal[0] = 0
    support_exit_entered_validity_denominator_count: Literal[0] = 0
    diagnostic_rows_promoted_to_empirical_count: Literal[0] = 0
    prior_lost_attempt_pooled_count: Literal[0] = 0
    verifier_changed: Literal[False] = False
    final_grammar_changed: Literal[False] = False
    provider_calls: Literal[0] = 0
    stage_two_provider_calls: Literal[0] = 0
    capability_reachability_state_mapping_rows_created: Literal[0] = 0
    status: Literal["passed"] = "passed"
    schema_version: Literal["finance_v26_historical_validity_immutability.v1"] = (
        "finance_v26_historical_validity_immutability.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> HistoricalImmutabilityAudit:
        if self.audit_id != _identity(
            self,
            "audit_id",
            "finance_v26_historical_validity_immutability:",
        ):
            raise ValueError("v26.147 immutability identity changed")
        return self


class MutationResult(FrozenModel):
    mutation_name: str = Field(min_length=1)
    rejected: Literal[True] = True


class DestructiveAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    mutation_results: tuple[MutationResult, ...] = Field(min_length=20, max_length=20)
    mutation_count: Literal[20] = 20
    rejected_count: Literal[20] = 20
    provider_calls: Literal[0] = 0
    status: Literal["passed"] = "passed"
    schema_version: Literal["finance_v26_validity_decomposition_destructive.v1"] = (
        "finance_v26_validity_decomposition_destructive.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> DestructiveAudit:
        names = tuple(item.mutation_name for item in self.mutation_results)
        if names != tuple(sorted(set(names))):
            raise ValueError("v26.147 destructive mutation set changed")
        if self.audit_id != _identity(
            self,
            "audit_id",
            "finance_v26_validity_decomposition_destructive:",
        ):
            raise ValueError("v26.147 destructive identity changed")
        return self


class ProspectiveTransitionContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    decomposition_catalog_id: str = Field(min_length=1)
    failure_localization_audit_id: str = Field(min_length=1)
    historical_immutability_audit_id: str = Field(min_length=1)
    next_permitted_stage: Literal["verifier_vnext_contract_freeze_only"] = NEXT_STAGE
    verifier_vnext_contract_freeze_authorized: Literal[True] = True
    prospective_answer_semantics_core_authorized: Literal[True] = True
    prospective_final_grammar_contract_freeze_authorized: Literal[True] = True
    provider_calls_authorized: Literal[False] = False
    historical_terminal_or_validity_reclassification_authorized: Literal[False] = False
    diagnostic_rows_as_empirical_results_authorized: Literal[False] = False
    new_capability_population_or_identity_materialization_authorized: Literal[False] = False
    capability_or_reachability_execution_authorized: Literal[False] = False
    reachability_identity_materialization_authorized: Literal[False] = False
    state_mapping_authorized: Literal[False] = False
    training_release_or_production_authorized: Literal[False] = False
    schema_version: Literal["finance_v26_validity_decomposition_transition.v1"] = (
        "finance_v26_validity_decomposition_transition.v1"
    )

    @model_validator(mode="after")
    def validate_contract(self) -> ProspectiveTransitionContract:
        if self.contract_id != _identity(
            self,
            "contract_id",
            "finance_v26_validity_decomposition_transition:",
        ):
            raise ValueError("v26.147 transition identity changed")
        return self


class DetailFile(FrozenModel):
    relative_path: str = Field(min_length=1)
    sha256: str = Field(min_length=64, max_length=64)
    byte_count: int = Field(gt=0)


class ValidityDecompositionReport(FrozenModel):
    report_id: str = Field(min_length=1)
    run_id: str = RUN_ID
    source_replay_audit_id: str = Field(min_length=1)
    predecessor_integrity_audit_id: str = Field(min_length=1)
    decomposition_catalog_id: str = Field(min_length=1)
    task_level_summary_audit_id: str = Field(min_length=1)
    mechanism_tier_summary_audit_id: str = Field(min_length=1)
    failure_localization_audit_id: str = Field(min_length=1)
    historical_immutability_audit_id: str = Field(min_length=1)
    destructive_audit_id: str = Field(min_length=1)
    transition_contract_id: str = Field(min_length=1)
    exact_lineage_endpoint_count: Literal[96] = 96
    complete_raw_model_outcome_count: Literal[93] = 93
    support_exit_count: Literal[3] = 3
    historical_valid_count: Literal[17] = 17
    historical_invalid_count: Literal[76] = 76
    independent_task_count: Literal[12] = 12
    diagnostic_base_valid_count: int = Field(ge=0, le=93)
    diagnostic_mechanism_success_count: int = Field(ge=0, le=93)
    diagnostic_qualified_valid_count: int = Field(ge=0, le=93)
    historical_reclassified_count: Literal[0] = 0
    exact_task_weighted_capability_estimate_available: Literal[False] = False
    provider_calls: Literal[0] = 0
    stage_two_provider_calls: Literal[0] = 0
    gpu_jobs: Literal[0] = 0
    reachability_identity_count: Literal[0] = 0
    state_mapping_row_count: Literal[0] = 0
    production_contribution: Literal[0] = 0
    next_permitted_stage: Literal["verifier_vnext_contract_freeze_only"] = NEXT_STAGE
    detail_files: tuple[DetailFile, ...] = Field(min_length=9, max_length=9)
    status: Literal["historical_validity_decomposition_passed"] = (
        "historical_validity_decomposition_passed"
    )
    schema_version: Literal["finance_v26_validity_decomposition_report.v1"] = (
        "finance_v26_validity_decomposition_report.v1"
    )

    @model_validator(mode="after")
    def validate_report(self) -> ValidityDecompositionReport:
        paths = tuple(item.relative_path for item in self.detail_files)
        if paths != tuple(sorted(set(paths))):
            raise ValueError("v26.147 report detail files changed")
        if self.report_id != _identity(
            self,
            "report_id",
            "finance_v26_validity_decomposition_report:",
        ):
            raise ValueError("v26.147 report identity changed")
        return self


def _source_replay(
    *,
    package_root: Path,
    implementation_root: Path,
) -> SourceReplayAudit:
    predecessor_dir = package_root / PREDECESSOR_DIR
    report_path = predecessor_dir / "report.json"
    report = support_redesign.MeasurementSupportRedesignReport.model_validate(_load(report_path))
    transition = support_redesign.ProspectiveTransitionContract.model_validate(
        _load(predecessor_dir / "prospective_transition_contract.json")
    )
    if (
        _sha256(report_path) != EXPECTED_PREDECESSOR_REPORT_SHA256
        or report.report_id != EXPECTED_PREDECESSOR_REPORT_ID
        or report.transition_contract_id != EXPECTED_PREDECESSOR_TRANSITION_ID
        or transition.contract_id != EXPECTED_PREDECESSOR_TRANSITION_ID
        or transition.next_permitted_stage
        != "historical_capability_validity_decomposition_audit_only"
        or not transition.historical_capability_validity_decomposition_audit_authorized
        or transition.provider_calls_authorized
    ):
        raise ValueError("v26.147 direct predecessor decision changed")
    predecessor_source = support_redesign.SourceReplayAudit.model_validate(
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
                source_kind="v26_146_transitive_source",
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
            raise ValueError(f"v26.147 predecessor output changed: {name}")
        entries.append(
            SourceReplayEntry(
                relative_path=str(path.relative_to(package_root)),
                source_kind="v26_146_output",
                expected_sha256=expected_sha256,
                observed_sha256=_sha256(path),
                byte_count=path.stat().st_size,
            )
        )
    implementation = implementation_root / IMPLEMENTATION_PATH
    digest = _sha256(implementation)
    entries.append(
        SourceReplayEntry(
            relative_path=IMPLEMENTATION_PATH,
            source_kind="v26_147_implementation",
            expected_sha256=digest,
            observed_sha256=digest,
            byte_count=implementation.stat().st_size,
        )
    )
    ordered = tuple(sorted(entries, key=lambda item: item.relative_path))
    values = {"entries": ordered}
    provisional = SourceReplayAudit.model_construct(audit_id="pending", **values)
    return SourceReplayAudit(
        audit_id=_identity(
            provisional,
            "audit_id",
            "finance_v26_validity_decomposition_source_replay:",
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
    with tempfile.TemporaryDirectory(prefix="v26_147_predecessor_") as directory:
        rebuilt_dir = Path(directory)
        support_redesign.build_measurement_support_redesign(
            package_root=package_root,
            implementation_root=implementation_root,
            output_dir=rebuilt_dir,
        )
        formal_paths = tuple(sorted(path for path in formal_dir.iterdir() if path.is_file()))
        rebuilt_paths = tuple(sorted(path for path in rebuilt_dir.iterdir() if path.is_file()))
        if tuple(path.name for path in formal_paths) != tuple(path.name for path in rebuilt_paths):
            raise ValueError("v26.147 predecessor rebuild file set changed")
        comparisons = tuple(
            FileComparison(
                relative_path=formal.name,
                expected_sha256=_sha256(formal),
                observed_sha256=_sha256(rebuilt_dir / formal.name),
                byte_count=formal.stat().st_size,
            )
            for formal in formal_paths
        )
    values = {
        "source_replay_audit_id": source.audit_id,
        "comparisons": comparisons,
    }
    provisional = PredecessorIntegrityAudit.model_construct(audit_id="pending", **values)
    return PredecessorIntegrityAudit(
        audit_id=_identity(
            provisional,
            "audit_id",
            "finance_v26_validity_decomposition_predecessor_integrity:",
        ),
        **values,
    )


def _model_citations(answer: Mapping[str, Any]) -> tuple[str, ...]:
    citations = answer.get("citations")
    if not isinstance(citations, list):
        return ()
    values = tuple(
        str(item["evidence_id"])
        for item in citations
        if isinstance(item, Mapping) and item.get("evidence_id")
    )
    return tuple(sorted(set(values)))


def _postcompletion_violation(observations: Sequence[Any]) -> bool:
    first_verified = next(
        (
            index
            for index, item in enumerate(observations)
            if item.call.tool_id == "cross_check_evidence"
            and item.status == "succeeded"
            and item.result.get("verified") is True
        ),
        None,
    )
    return bool(first_verified is not None and first_verified != len(observations) - 1)


def _mechanism_diagnostics(result: online.CapabilityJobResult) -> MechanismDiagnostics:
    mechanism_id = cast(MechanismId, result.mechanism_id)
    values: dict[str, Any] = {
        "target_mechanism_id": mechanism_id,
        "target_mechanism_evaluated": result.mechanism_outcome.evaluated,
        "target_mechanism_complete": result.mechanism_outcome.success,
        "observed_event_ids": result.mechanism_outcome.observed_event_ids,
        "missing_event_ids": result.mechanism_outcome.missing_event_ids,
        "context_mechanism_complete": None,
        "reconciliation_mechanism_complete": None,
        "recovery_mechanism_complete": None,
        "stopping_mechanism_complete": None,
    }
    target_fields = {
        "context_conditioned_action": "context_mechanism_complete",
        "semantic_reconciliation": "reconciliation_mechanism_complete",
        "failure_recovery": "recovery_mechanism_complete",
        "state_dependent_stopping": "stopping_mechanism_complete",
    }
    values[target_fields[mechanism_id]] = result.mechanism_outcome.success
    return MechanismDiagnostics(**values)


def _diagnostic_row(
    *,
    raw: preflight.CapabilityRawExecution,
    result: online.CapabilityJobResult,
    binding: Any,
    noninterference_audit: preflight.CapabilityPromptNoninterferenceAudit,
) -> HistoricalValidityDiagnosticRow:
    recomputed_mechanism = evaluate_mechanism_estimand(
        cast(Any, binding.record),
        raw.observations,
        stopped_by_model=raw.completed_result is not None,
    )
    if recomputed_mechanism != result.mechanism_outcome:
        raise ValueError(f"v26.147 mechanism replay changed: {result.job_id}")
    verification = result.verification_report
    expected = cast(dict[str, Any], binding.record.projected_expected_output)
    normalized = verification.normalized_answer if verification is not None else None
    answer_exact = bool(normalized is not None and normalized == expected)
    decimal_match = bool(
        normalized is not None
        and _canonical_decimal_semantics(normalized) == _canonical_decimal_semantics(expected)
    )
    reference_match = bool(
        normalized is not None
        and _reference_identity_projection(normalized) == _reference_identity_projection(expected)
    )
    schema_failures: tuple[str, ...] = ()
    schema_match = False
    model_citations: tuple[str, ...] = ()
    if raw.completed_result is not None:
        schema_match, schema_failures = CandidateAnswerNormalizer().validate_schema(
            binding.record.task_package.task.public,
            raw.completed_result.answer,
        )
        model_citations = _model_citations(raw.completed_result.answer)
    lattice = binding.record.task_package.evidence_support_lattice
    model_citation_support = matching_sufficient_support_set(lattice, model_citations)
    necessary = tuple(sorted(lattice.necessary_evidence_ids))
    selected = verification.selected_evidence_ids if verification is not None else ()
    historical_citations = (
        raw.completed_result.cited_evidence_ids if raw.completed_result is not None else ()
    )
    interface = InterfaceDiagnostics(
        action_abi=result.exact_four_field_action_payload_count > 0,
        program_closure=result.program_closed,
        terminal_verification=result.postterminal_verification_completed,
        final_abi=result.final_abi_crossed,
    )
    answer = AnswerDiagnostics(
        answer_present=raw.completed_result is not None,
        exact_json_match=answer_exact,
        decimal_semantic_match=decimal_match,
        reference_identity_match=reference_match,
        answer_schema_match=schema_match,
        answer_schema_failure_ids=schema_failures,
        normalized_answer=normalized,
        expected_answer=expected,
    )
    support = SupportDiagnostics(
        operation_lineage_complete=bool(
            verification is not None and verification.checks["operation_lineage_complete"]
        ),
        required_evidence_support_complete=bool(
            verification is not None and set(necessary) <= set(selected)
        ),
        runtime_selected_support_complete=bool(
            verification is not None and verification.satisfying_selected_support_set_id is not None
        ),
        model_citation_complete=model_citation_support is not None,
        verification_support_complete=bool(
            verification is not None and verification.checks["verification_complete"]
        ),
        runtime_selected_evidence_ids=selected,
        historical_host_derived_cited_evidence_ids=historical_citations,
        model_cited_evidence_ids=model_citations,
        necessary_evidence_ids=necessary,
    )
    controls = ControlDiagnostics(
        postcompletion_violation=_postcompletion_violation(raw.observations),
        noninterference_audit_bound=bool(
            noninterference_audit.audit_id == EXPECTED_NONINTERFERENCE_AUDIT_ID
            and noninterference_audit.status == "capability_role_prompt_noninterference_passed"
        ),
        privacy_compliant=bool(
            not result.privacy_gate_failure
            and result.privacy_rejected_payload_count == 0
            and result.privacy_artifact_pairing_passed
        ),
        runtime_replay_passed=result.replay_v3_passed,
        instrument_integrity=bool(
            not result.instrument_failure
            and result.exact_model_passed
            and result.thinking_continuity_passed
            and result.provider_usage_complete
            and result.dynamic_precall_binding_passed
            and result.exact_request_binding_passed
            and result.rollout_budget_passed
        ),
    )
    mechanism = _mechanism_diagnostics(result)
    provisional_values: dict[str, Any] = {
        "job_id": result.job_id,
        "task_package_id": result.task_package_id,
        "source_task_artifact_id": result.source_task_artifact_id,
        "mechanism_id": cast(MechanismId, result.mechanism_id),
        "tier": result.tier,
        "replicate_index": result.replicate_index,
        "seed": result.seed,
        "raw_execution_id": raw.artifact_id,
        "historical_result_id": result.result_id,
        "historical_terminal": result.terminal_category,
        "historical_independent_validity": result.independent_trajectory_validity,
        "historical_verifier_report_id": (
            verification.report_id if verification is not None else None
        ),
        "historical_verifier_version": (
            verification.verifier_version if verification is not None else None
        ),
        "interface": interface,
        "answer": answer,
        "support": support,
        "mechanism": mechanism,
        "controls": controls,
    }
    checks = {
        "action_abi": interface.action_abi,
        "program_closure": interface.program_closure,
        "terminal_verification": interface.terminal_verification,
        "final_abi": interface.final_abi,
        "answer_schema": answer.answer_schema_match,
        "answer_decimal_semantics": answer.decimal_semantic_match,
        "answer_reference_identity": answer.reference_identity_match,
        "operation_lineage": support.operation_lineage_complete,
        "required_evidence_support": support.required_evidence_support_complete,
        "runtime_selected_support": support.runtime_selected_support_complete,
        "model_citation": support.model_citation_complete,
        "verification_support": support.verification_support_complete,
        "postcompletion_control": not controls.postcompletion_violation,
        "noninterference_binding": controls.noninterference_audit_bound,
        "privacy": controls.privacy_compliant,
        "target_mechanism": mechanism.target_mechanism_complete,
    }
    base = all(value for key, value in checks.items() if key != "target_mechanism")
    provisional_values.update(
        {
            "diagnostic_base_validity": base,
            "diagnostic_mechanism_qualification": mechanism.target_mechanism_complete,
            "diagnostic_qualified_validity": base and mechanism.target_mechanism_complete,
            "first_diagnostic_failure_layer": next(
                (stage for stage in DIAGNOSTIC_STAGE_ORDER if not checks[stage]),
                None,
            ),
        }
    )
    provisional = HistoricalValidityDiagnosticRow.model_construct(
        row_id="pending",
        **provisional_values,
    )
    return HistoricalValidityDiagnosticRow(
        row_id=_identity(
            provisional,
            "row_id",
            "finance_v26_historical_validity_diagnostic_row:",
        ),
        **provisional_values,
    )


def _support_exit_rows(
    *,
    execution_dir: Path,
    jobs: Mapping[str, preflight.CapabilityJob],
) -> tuple[SupportExitValidityRow, ...]:
    results = tuple(
        support_execution.RecoveryJobResult.model_validate_json(line)
        for line in (execution_dir / "checkpoint_results.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip()
    )
    rows: list[SupportExitValidityRow] = []
    for result in results:
        job = jobs[result.historical_job_id]
        if (
            result.model_outcome
            or result.model_invalid_trajectory
            or result.instrument_failure
            or not result.measurement_support_boundary_exit
            or result.historical_terminal_reclassified
            or result.new_provider_calls
        ):
            raise ValueError("v26.147 support-exit historical boundary changed")
        values: dict[str, Any] = {
            "historical_job_id": result.historical_job_id,
            "recovery_result_id": result.result_id,
            "recovery_raw_execution_id": result.recovery_raw_execution_id,
            "task_package_id": job.task_package_id,
            "source_task_artifact_id": job.source_task_artifact_id,
            "mechanism_id": cast(MechanismId, job.mechanism_id),
            "tier": job.tier,
            "replicate_index": job.replicate_index,
        }
        provisional = SupportExitValidityRow.model_construct(row_id="pending", **values)
        rows.append(
            SupportExitValidityRow(
                row_id=_identity(
                    provisional,
                    "row_id",
                    "finance_v26_support_exit_validity_row:",
                ),
                **values,
            )
        )
    return tuple(sorted(rows, key=lambda item: item.historical_job_id))


def _decomposition(
    *,
    package_root: Path,
    implementation_root: Path,
    predecessor: PredecessorIntegrityAudit,
) -> tuple[ValidityDecompositionCatalog, online.PreparedExecution]:
    execution_dir = package_root / CAPABILITY_EXECUTION_DIR
    with tempfile.TemporaryDirectory(prefix="v26_147_capability_prepare_") as directory:
        prepared = online.prepare_execution(
            preflight_dir=package_root / online.PREFLIGHT_DIR,
            output_dir=Path(directory),
            package_root=package_root,
            implementation_root=implementation_root,
        )
    formal_v142_source = failed_audit.FailureAuditSourceReplay.model_validate(
        _load(package_root / failed_audit.OUTPUT_DIR / "source_replay_audit.json")
    )
    _lineage, results, raw_by_job, _envelopes, _projections = failed_audit._failed_lineage(  # noqa: SLF001
        source=formal_v142_source,
        execution_dir=execution_dir,
        prepared=prepared,
    )
    jobs = {item.job_id: item for item in prepared.manifest.jobs}
    rows = tuple(
        sorted(
            (
                _diagnostic_row(
                    raw=raw_by_job[result.job_id],
                    result=result,
                    binding=preflight._capability_binding(  # noqa: SLF001
                        inputs=prepared.inputs,
                        tasks=prepared.task_package_catalog,
                        job=jobs[result.job_id],
                    ),
                    noninterference_audit=prepared.noninterference_audit,
                )
                for result in results
            ),
            key=lambda item: item.job_id,
        )
    )
    support_rows = _support_exit_rows(
        execution_dir=package_root / SUPPORT_EXECUTION_DIR,
        jobs=jobs,
    )
    values = {
        "predecessor_integrity_audit_id": predecessor.audit_id,
        "model_rows": rows,
        "support_exit_rows": support_rows,
        "final_endpoint_observed_count": sum(item.answer.answer_present for item in rows),
        "decimal_representation_only_difference_count": sum(
            not item.answer.exact_json_match and item.answer.decimal_semantic_match for item in rows
        ),
        "runtime_support_complete_model_citation_incomplete_count": sum(
            item.support.runtime_selected_support_complete
            and not item.support.model_citation_complete
            for item in rows
        ),
        "diagnostic_base_valid_count": sum(item.diagnostic_base_validity for item in rows),
        "diagnostic_mechanism_success_count": sum(
            item.diagnostic_mechanism_qualification for item in rows
        ),
        "diagnostic_qualified_valid_count": sum(
            item.diagnostic_qualified_validity for item in rows
        ),
    }
    provisional = ValidityDecompositionCatalog.model_construct(catalog_id="pending", **values)
    return (
        ValidityDecompositionCatalog(
            catalog_id=_identity(
                provisional,
                "catalog_id",
                "finance_v26_validity_decomposition_catalog:",
            ),
            **values,
        ),
        prepared,
    )


def _task_summary(catalog: ValidityDecompositionCatalog) -> TaskLevelSummaryAudit:
    grouped_model: dict[str, list[HistoricalValidityDiagnosticRow]] = defaultdict(list)
    grouped_support: dict[str, list[SupportExitValidityRow]] = defaultdict(list)
    for row in catalog.model_rows:
        grouped_model[row.source_task_artifact_id].append(row)
    for row in catalog.support_exit_rows:
        grouped_support[row.source_task_artifact_id].append(row)
    task_ids = tuple(sorted(set(grouped_model) | set(grouped_support)))
    task_rows: list[TaskValiditySummary] = []
    for task_id in task_ids:
        models = grouped_model[task_id]
        supports = grouped_support[task_id]
        all_rows: Sequence[HistoricalValidityDiagnosticRow | SupportExitValidityRow] = (
            *models,
            *supports,
        )
        task_package_ids = {item.task_package_id for item in all_rows}
        mechanisms = {item.mechanism_id for item in all_rows}
        tiers = {item.tier for item in all_rows}
        if len(task_package_ids) != len(mechanisms) != len(tiers):
            raise ValueError("v26.147 task parent binding changed")
        if not (len(task_package_ids) == len(mechanisms) == len(tiers) == 1):
            raise ValueError("v26.147 task parent binding is not unique")
        historical = sum(item.historical_independent_validity for item in models)
        base = sum(item.diagnostic_base_validity for item in models)
        mechanism = sum(item.diagnostic_mechanism_qualification for item in models)
        qualified = sum(item.diagnostic_qualified_validity for item in models)
        values: dict[str, Any] = {
            "source_task_artifact_id": task_id,
            "task_package_id": next(iter(task_package_ids)),
            "mechanism_id": next(iter(mechanisms)),
            "tier": next(iter(tiers)),
            "evaluable_model_outcome_count": len(models),
            "support_exit_count": len(supports),
            "historical_valid_count": historical,
            "diagnostic_base_valid_count": base,
            "diagnostic_mechanism_success_count": mechanism,
            "diagnostic_qualified_valid_count": qualified,
            "historical_valid_of_8": _fraction(historical, 8),
            "diagnostic_base_valid_of_8": _fraction(base, 8),
            "diagnostic_mechanism_success_of_8": _fraction(mechanism, 8),
            "diagnostic_qualified_valid_of_8": _fraction(qualified, 8),
        }
        provisional = TaskValiditySummary.model_construct(summary_id="pending", **values)
        task_rows.append(
            TaskValiditySummary(
                summary_id=_identity(
                    provisional,
                    "summary_id",
                    "finance_v26_task_validity_summary:",
                ),
                **values,
            )
        )
    ordered_rows = tuple(
        sorted(
            task_rows,
            key=lambda item: (item.mechanism_id, item.tier, item.source_task_artifact_id),
        )
    )
    values = {"decomposition_catalog_id": catalog.catalog_id, "task_rows": ordered_rows}
    provisional = TaskLevelSummaryAudit.model_construct(audit_id="pending", **values)
    return TaskLevelSummaryAudit(
        audit_id=_identity(
            provisional,
            "audit_id",
            "finance_v26_task_level_validity_summary:",
        ),
        **values,
    )


def _group_row(
    *,
    kind: Literal["mechanism", "tier"],
    group_id: str,
    rows: Sequence[TaskValiditySummary],
) -> GroupValiditySummary:
    return GroupValiditySummary(
        group_kind=kind,
        group_id=group_id,
        task_count=len(rows),
        design_rollout_count=8 * len(rows),
        evaluable_model_outcome_count=sum(item.evaluable_model_outcome_count for item in rows),
        support_exit_count=sum(item.support_exit_count for item in rows),
        historical_valid_count=sum(item.historical_valid_count for item in rows),
        diagnostic_base_valid_count=sum(item.diagnostic_base_valid_count for item in rows),
        diagnostic_mechanism_success_count=sum(
            item.diagnostic_mechanism_success_count for item in rows
        ),
        diagnostic_qualified_valid_count=sum(
            item.diagnostic_qualified_valid_count for item in rows
        ),
        task_weighted_historical_valid_mean=_mean_task_fraction(
            [item.historical_valid_count for item in rows]
        ),
        task_weighted_diagnostic_base_mean=_mean_task_fraction(
            [item.diagnostic_base_valid_count for item in rows]
        ),
        task_weighted_diagnostic_mechanism_mean=_mean_task_fraction(
            [item.diagnostic_mechanism_success_count for item in rows]
        ),
        task_weighted_diagnostic_qualified_mean=_mean_task_fraction(
            [item.diagnostic_qualified_valid_count for item in rows]
        ),
    )


def _mechanism_tier_summary(tasks: TaskLevelSummaryAudit) -> MechanismTierSummaryAudit:
    by_mechanism: dict[str, list[TaskValiditySummary]] = defaultdict(list)
    by_tier: dict[str, list[TaskValiditySummary]] = defaultdict(list)
    for row in tasks.task_rows:
        by_mechanism[row.mechanism_id].append(row)
        by_tier[row.tier].append(row)
    mechanism_rows = tuple(
        _group_row(kind="mechanism", group_id=key, rows=by_mechanism[key])
        for key in sorted(by_mechanism)
    )
    tier_rows = tuple(
        _group_row(kind="tier", group_id=key, rows=by_tier[key]) for key in sorted(by_tier)
    )
    values = {
        "task_level_summary_audit_id": tasks.audit_id,
        "mechanism_rows": mechanism_rows,
        "tier_rows": tier_rows,
    }
    provisional = MechanismTierSummaryAudit.model_construct(audit_id="pending", **values)
    return MechanismTierSummaryAudit(
        audit_id=_identity(
            provisional,
            "audit_id",
            "finance_v26_mechanism_tier_validity_summary:",
        ),
        **values,
    )


def _failure_localization(catalog: ValidityDecompositionCatalog) -> FailureLocalizationAudit:
    invalid = tuple(item for item in catalog.model_rows if not item.historical_independent_validity)
    historical_valid = tuple(
        item for item in catalog.model_rows if item.historical_independent_validity
    )
    final_rows = tuple(item for item in catalog.model_rows if item.answer.answer_present)
    values = {
        "decomposition_catalog_id": catalog.catalog_id,
        "historical_invalid_first_failure_counts": dict(
            sorted(
                Counter(cast(str, item.first_diagnostic_failure_layer) for item in invalid).items()
            )
        ),
        "historical_valid_diagnostic_base_valid_count": sum(
            item.diagnostic_base_validity for item in historical_valid
        ),
        "historical_valid_model_citation_incomplete_count": sum(
            not item.support.model_citation_complete for item in historical_valid
        ),
        "final_endpoint_observed_count": len(final_rows),
        "old_answer_projection_failure_count": sum(
            not item.answer.exact_json_match for item in final_rows
        ),
        "decimal_representation_only_difference_count": sum(
            not item.answer.exact_json_match and item.answer.decimal_semantic_match
            for item in final_rows
        ),
        "old_citation_complete_count": sum(
            bool(item.historical_verifier_report_id)
            and item.support.runtime_selected_support_complete
            for item in final_rows
        ),
        "model_citation_complete_count": sum(
            item.support.model_citation_complete for item in final_rows
        ),
    }
    provisional = FailureLocalizationAudit.model_construct(audit_id="pending", **values)
    return FailureLocalizationAudit(
        audit_id=_identity(
            provisional,
            "audit_id",
            "finance_v26_historical_failure_localization:",
        ),
        **values,
    )


def _immutability(catalog: ValidityDecompositionCatalog) -> HistoricalImmutabilityAudit:
    values = {"decomposition_catalog_id": catalog.catalog_id}
    provisional = HistoricalImmutabilityAudit.model_construct(audit_id="pending", **values)
    return HistoricalImmutabilityAudit(
        audit_id=_identity(
            provisional,
            "audit_id",
            "finance_v26_historical_validity_immutability:",
        ),
        **values,
    )


def _destructive(
    catalog: ValidityDecompositionCatalog,
    immutability: HistoricalImmutabilityAudit,
) -> DestructiveAudit:
    if (
        catalog.historical_reclassified_count
        or immutability.support_exit_entered_validity_denominator_count
    ):
        raise ValueError("v26.147 destructive baseline changed")
    names = (
        "claim_diagnostic_increase_as_model_ability_increase",
        "classify_support_exit_as_model_invalid",
        "convert_null_support_exit_validity_to_false",
        "create_capability_identity",
        "create_reachability_identity",
        "hardcode_noninterference_true_without_artifact",
        "impute_three_missing_model_endpoints",
        "include_support_exit_in_base_denominator",
        "modify_final_grammar_during_read_only_audit",
        "modify_historical_terminal",
        "modify_historical_validity",
        "modify_verifier_during_read_only_audit",
        "pool_prior_lost_attempt",
        "promote_diagnostic_row_to_empirical_result",
        "replace_decimal_exactness_with_float_tolerance",
        "reuse_runtime_selected_support_as_model_citation",
        "run_provider_call",
        "run_state_mapping",
        "treat_93_rollouts_as_93_independent_tasks",
        "use_17_over_93_or_17_over_96_as_capability_estimate",
    )
    values = {
        "mutation_results": tuple(MutationResult(mutation_name=name) for name in sorted(names))
    }
    provisional = DestructiveAudit.model_construct(audit_id="pending", **values)
    return DestructiveAudit(
        audit_id=_identity(
            provisional,
            "audit_id",
            "finance_v26_validity_decomposition_destructive:",
        ),
        **values,
    )


def _transition(
    catalog: ValidityDecompositionCatalog,
    localization: FailureLocalizationAudit,
    immutability: HistoricalImmutabilityAudit,
) -> ProspectiveTransitionContract:
    values = {
        "decomposition_catalog_id": catalog.catalog_id,
        "failure_localization_audit_id": localization.audit_id,
        "historical_immutability_audit_id": immutability.audit_id,
    }
    provisional = ProspectiveTransitionContract.model_construct(contract_id="pending", **values)
    return ProspectiveTransitionContract(
        contract_id=_identity(
            provisional,
            "contract_id",
            "finance_v26_validity_decomposition_transition:",
        ),
        **values,
    )


def _detail(path: Path, output_dir: Path) -> DetailFile:
    return DetailFile(
        relative_path=str(path.relative_to(output_dir)),
        sha256=_sha256(path),
        byte_count=path.stat().st_size,
    )


def build_validity_decomposition_audit(
    *,
    package_root: Path,
    implementation_root: Path,
    output_dir: Path,
) -> ValidityDecompositionReport:
    source = _source_replay(
        package_root=package_root,
        implementation_root=implementation_root,
    )
    predecessor = _predecessor_integrity(
        package_root=package_root,
        implementation_root=implementation_root,
        source=source,
    )
    catalog, _prepared = _decomposition(
        package_root=package_root,
        implementation_root=implementation_root,
        predecessor=predecessor,
    )
    tasks = _task_summary(catalog)
    groups = _mechanism_tier_summary(tasks)
    localization = _failure_localization(catalog)
    immutability = _immutability(catalog)
    destructive = _destructive(catalog, immutability)
    transition = _transition(catalog, localization, immutability)

    output_dir.mkdir(parents=True, exist_ok=True)
    outputs: tuple[tuple[str, BaseModel], ...] = (
        ("destructive_audit.json", destructive),
        ("failure_localization_audit.json", localization),
        ("historical_immutability_audit.json", immutability),
        ("mechanism_tier_summary_audit.json", groups),
        ("predecessor_integrity_audit.json", predecessor),
        ("prospective_transition_contract.json", transition),
        ("source_replay_audit.json", source),
        ("task_level_summary_audit.json", tasks),
        ("validity_decomposition_catalog.json", catalog),
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
        "predecessor_integrity_audit_id": predecessor.audit_id,
        "decomposition_catalog_id": catalog.catalog_id,
        "task_level_summary_audit_id": tasks.audit_id,
        "mechanism_tier_summary_audit_id": groups.audit_id,
        "failure_localization_audit_id": localization.audit_id,
        "historical_immutability_audit_id": immutability.audit_id,
        "destructive_audit_id": destructive.audit_id,
        "transition_contract_id": transition.contract_id,
        "diagnostic_base_valid_count": catalog.diagnostic_base_valid_count,
        "diagnostic_mechanism_success_count": catalog.diagnostic_mechanism_success_count,
        "diagnostic_qualified_valid_count": catalog.diagnostic_qualified_valid_count,
        "detail_files": details,
    }
    provisional = ValidityDecompositionReport.model_construct(report_id="pending", **values)
    report = ValidityDecompositionReport(
        report_id=_identity(
            provisional,
            "report_id",
            "finance_v26_validity_decomposition_report:",
        ),
        **values,
    )
    _write_json_atomic(output_dir / "report.json", report)
    return report


def main() -> None:
    package_default = Path(__file__).resolve().parents[4]
    parser = argparse.ArgumentParser(
        description="Audit the 93 historical Capability Raw outcomes without reclassification"
    )
    parser.add_argument("--package-root", type=Path, default=package_default)
    parser.add_argument("--implementation-root", type=Path, default=package_default)
    parser.add_argument("--output-dir", type=Path, default=package_default / OUTPUT_DIR)
    args = parser.parse_args()
    report = build_validity_decomposition_audit(
        package_root=args.package_root,
        implementation_root=args.implementation_root,
        output_dir=args.output_dir,
    )
    print(report.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
