from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import Counter
from collections.abc import Sequence
from pathlib import Path
from typing import Any, Literal, TypeVar, cast

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_budget_closed_instrument_postrun_audit import (  # noqa: E501
    BudgetPostrunAuditReport,
    BudgetPostrunSourceReplayAudit,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_budget_closed_instrument_recovery import (  # noqa: E501
    BudgetRecoveryRawExecution,
    BudgetRecoveryReport,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_budget_closed_instrument_requalification import (  # noqa: E501
    BudgetClosedInstrumentRollout,
    BudgetClosedRolloutDiagnostic,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_public_operation_rematerialization import (  # noqa: E501
    OperationalTaskRecord,
)
from trusted_synthesis.hashing import canonical_hash
from trusted_synthesis.runtime.agent.budget_closed import (
    ProviderRequestKind,
    ProviderTokenBudgetContract,
)
from trusted_synthesis.runtime.agent.public_operation import public_operation_progress
from trusted_synthesis.runtime.tools import AgentToolObservation

EXPECTED_RECOVERY_REPORT_ID = (
    "finance_v26_budget_recovery_report:"
    "4afbad8525b598269630912e79048490dbe4e3235d8789aad0f10b922798c4ea"
)
EXPECTED_POSTRUN_AUDIT_REPORT_ID = (
    "finance_v26_budget_closed_postrun_audit:"
    "a7318da72819ce66bdc93ab5117faec5f9f59b32aebd33f5324f2198bd705939"
)
EXPECTED_BUDGET_CONTRACT_ID = (
    "provider_token_budget_contract:"
    "27e7e524cb3139b9dd29b1ca7f2c7eae1956c96af8a982524f814b3ef4415150"
)
EXPECTED_JOB_COUNT: Literal[32] = 32
EXPECTED_NO_CALL_COUNT: Literal[24] = 24
EXPECTED_MODEL_INVALID_COUNT: Literal[8] = 8
EXPECTED_TOTAL_TOKEN_CEILING: Literal[120000] = 120_000
EXPECTED_PROMPT_BYTE_CEILING: Literal[60000] = 60_000
EXPECTED_COMPLETION_BOUND: Literal[4096] = 4_096
EXPECTED_REPAIR_RESERVE: Literal[4096] = 4_096
EXPECTED_FINAL_RESERVE: Literal[4096] = 4_096
EXPECTED_CHAT_ENVELOPE: Literal[256] = 256

AUDIT_MODULE_PATH = (
    "src/trusted_synthesis/experiments/vtdo_experiment/"
    "phase1_v26_budget_adequacy_root_cause_audit.py"
)

SOURCE_VERSION = "finance_v26_budget_adequacy_source_replay.v1"
JOB_ROW_VERSION = "finance_v26_budget_adequacy_job_diagnostic.v1"
GROUP_ROW_VERSION = "finance_v26_budget_adequacy_group_summary.v1"
GROUP_AUDIT_VERSION = "finance_v26_budget_adequacy_group_audit.v1"
ROOT_CAUSE_VERSION = "finance_v26_budget_adequacy_root_cause.v1"
DECISION_VERSION = "finance_v26_budget_adequacy_decision.v1"
REPORT_VERSION = "finance_v26_budget_adequacy_root_cause_report.v1"

BudgetTerminal = Literal["budget_exhausted_no_call", "model_invalid_trajectory"]
DenialAttribution = Literal["request_bound", "required_reserve", "prompt_ceiling"]
ProgressClass = Literal[
    "no_registered_node_completed",
    "partial_program",
    "one_required_node_remaining",
    "terminal_completed_unverified",
    "verified_stop_ready",
]


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class BudgetAdequacySourceEntry(FrozenModel):
    relative_path: str = Field(min_length=1)
    expected_sha256: str = Field(min_length=64, max_length=64)
    observed_sha256: str = Field(min_length=64, max_length=64)
    byte_count: int = Field(ge=1)
    source_kind: Literal[
        "v26_87_replayed_source",
        "v26_87_audit_output",
        "v26_88_implementation",
    ]
    passed: Literal[True] = True

    @model_validator(mode="after")
    def validate_entry(self) -> BudgetAdequacySourceEntry:
        if self.expected_sha256 != self.observed_sha256:
            raise ValueError("budget adequacy source bytes changed")
        return self


class BudgetAdequacySourceReplayAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    postrun_audit_report_id: str = EXPECTED_POSTRUN_AUDIT_REPORT_ID
    recovery_report_id: str = EXPECTED_RECOVERY_REPORT_ID
    entries: tuple[BudgetAdequacySourceEntry, ...] = Field(min_length=1)
    replayed_file_count: int = Field(ge=1)
    replay_pass_count: int = Field(ge=1)
    source_replay_before_diagnostics: Literal[True] = True
    model_client_constructed: Literal[False] = False
    model_api_calls: Literal[0] = 0
    gpu_jobs: Literal[0] = 0
    status: Literal["passed"] = "passed"
    schema_version: str = SOURCE_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> BudgetAdequacySourceReplayAudit:
        paths = tuple(item.relative_path for item in self.entries)
        if paths != tuple(sorted(set(paths))):
            raise ValueError("budget adequacy source paths are not canonical")
        if self.replayed_file_count != len(self.entries):
            raise ValueError("budget adequacy source denominator changed")
        if self.replay_pass_count != self.replayed_file_count:
            raise ValueError("budget adequacy source replay is incomplete")
        if self.audit_id != budget_adequacy_source_audit_id(self):
            raise ValueError("budget adequacy source audit identity is invalid")
        return self


class BudgetAdequacyJobDiagnostic(FrozenModel):
    row_id: str = Field(min_length=1)
    job_id: str = Field(min_length=1)
    rollout_id: str = Field(min_length=1)
    task_package_id: str = Field(min_length=1)
    task_record_id: str = Field(min_length=1)
    mechanism_id: str = Field(min_length=1)
    replicate_index: int = Field(ge=0, le=3)
    recovery_role: Literal["zero_generation_replay", "unopened_model_continuation"]
    terminal_category: BudgetTerminal
    provider_call_count: int = Field(ge=1)
    provider_total_tokens: int = Field(ge=1, le=EXPECTED_TOTAL_TOKEN_CEILING)
    certificate_count: int = Field(ge=1)
    attempted_prompt_count: int = Field(ge=1)
    post_terminal_short_circuit_prompt_count: int = Field(ge=0, le=1)
    request_kind_sequence: tuple[ProviderRequestKind, ...] = Field(min_length=1)
    prompt_utf8_bytes_sequence: tuple[int, ...] = Field(min_length=1)
    provider_total_token_sequence: tuple[int, ...] = Field(min_length=1)
    initial_prompt_utf8_bytes: int = Field(ge=1, le=EXPECTED_PROMPT_BYTE_CEILING)
    final_certificate_prompt_utf8_bytes: int = Field(ge=1, le=EXPECTED_PROMPT_BYTE_CEILING)
    maximum_certificate_prompt_utf8_bytes: int = Field(ge=1, le=EXPECTED_PROMPT_BYTE_CEILING)
    prompt_growth_from_initial_bytes: int = Field(ge=0)
    observation_count: int = Field(ge=0)
    observation_artifact_utf8_bytes: int = Field(ge=0)
    successful_observation_count: int = Field(ge=0)
    failed_observation_count: int = Field(ge=0)
    identical_call_repeat_count: int = Field(ge=0)
    identical_failed_call_repeat_count: int = Field(ge=0)
    required_node_count: int = Field(ge=1)
    completed_node_count: int = Field(ge=0)
    remaining_node_count: int = Field(ge=0)
    terminal_node_completed: bool
    postterminal_verification_completed: bool
    stop_ready: bool
    progress_class: ProgressClass
    program_progress_matches_frozen_diagnostic: Literal[True] = True
    budget_denied: bool
    denied_request_index: int | None = Field(default=None, ge=0)
    denied_request_kind: ProviderRequestKind | None = None
    denied_repaired_request_kind: ProviderRequestKind | None = None
    denial_reason: str | None = None
    denial_attribution: DenialAttribution | None = None
    token_usage_before_denial: int | None = Field(
        default=None, ge=0, le=EXPECTED_TOTAL_TOKEN_CEILING
    )
    remaining_headroom_before_denial: int | None = Field(default=None, ge=0)
    denied_prompt_utf8_bytes: int | None = Field(
        default=None, ge=1, le=EXPECTED_PROMPT_BYTE_CEILING
    )
    denied_prompt_increment_from_last_permitted: int | None = Field(default=None, ge=0)
    prompt_token_upper_bound: int | None = Field(default=None, ge=1)
    completion_token_upper_bound: int | None = Field(default=None, ge=1)
    request_token_upper_bound: int | None = Field(default=None, ge=1)
    contract_repair_reserve_tokens: int | None = Field(default=None, ge=0)
    final_answer_reserve_tokens: int | None = Field(default=None, ge=0)
    required_reserve_tokens: int | None = Field(default=None, ge=0)
    projected_without_reserve: int | None = Field(default=None, ge=1)
    projected_upper_total: int | None = Field(default=None, ge=1)
    request_only_deficit: int | None = Field(default=None, ge=0)
    reserve_contribution_to_deficit: int | None = Field(default=None, ge=0)
    headroom_deficit: int | None = Field(default=None, ge=0)
    minimum_ceiling_for_observed_denied_call: int | None = Field(default=None, ge=1)
    request_would_fit_without_reserves: bool | None = None
    projected_if_denied_prompt_reset_to_initial: int | None = Field(default=None, ge=1)
    reset_to_initial_prompt_would_fit: bool | None = None
    final_answer_only_candidate: bool
    prompt_growth_causal_attribution_established: Literal[False] = False
    observed_denied_call_completion_implication: Literal[False] = False
    schema_version: str = JOB_ROW_VERSION

    @model_validator(mode="after")
    def validate_row(self) -> BudgetAdequacyJobDiagnostic:
        if len(self.request_kind_sequence) != self.certificate_count:
            raise ValueError("budget adequacy request-kind denominator changed")
        if len(self.prompt_utf8_bytes_sequence) != self.certificate_count:
            raise ValueError("budget adequacy Prompt denominator changed")
        if len(self.provider_total_token_sequence) != self.provider_call_count:
            raise ValueError("budget adequacy Usage denominator changed")
        if self.initial_prompt_utf8_bytes != self.prompt_utf8_bytes_sequence[0]:
            raise ValueError("budget adequacy initial Prompt changed")
        if self.final_certificate_prompt_utf8_bytes != self.prompt_utf8_bytes_sequence[-1]:
            raise ValueError("budget adequacy final certificate Prompt changed")
        if self.maximum_certificate_prompt_utf8_bytes != max(self.prompt_utf8_bytes_sequence):
            raise ValueError("budget adequacy maximum Prompt changed")
        if self.prompt_growth_from_initial_bytes != (
            self.final_certificate_prompt_utf8_bytes - self.initial_prompt_utf8_bytes
        ):
            raise ValueError("budget adequacy Prompt-growth arithmetic changed")
        if self.observation_count != (
            self.successful_observation_count + self.failed_observation_count
        ):
            raise ValueError("budget adequacy Observation denominator changed")
        if self.remaining_node_count != self.required_node_count - self.completed_node_count:
            raise ValueError("budget adequacy Program-progress arithmetic changed")
        if self.completed_node_count > self.required_node_count:
            raise ValueError("budget adequacy completed too many Program nodes")
        denial_fields = (
            self.denied_request_index,
            self.denied_request_kind,
            self.denial_reason,
            self.denial_attribution,
            self.token_usage_before_denial,
            self.remaining_headroom_before_denial,
            self.denied_prompt_utf8_bytes,
            self.denied_prompt_increment_from_last_permitted,
            self.prompt_token_upper_bound,
            self.completion_token_upper_bound,
            self.request_token_upper_bound,
            self.contract_repair_reserve_tokens,
            self.final_answer_reserve_tokens,
            self.required_reserve_tokens,
            self.projected_without_reserve,
            self.projected_upper_total,
            self.request_only_deficit,
            self.reserve_contribution_to_deficit,
            self.headroom_deficit,
            self.minimum_ceiling_for_observed_denied_call,
            self.request_would_fit_without_reserves,
            self.projected_if_denied_prompt_reset_to_initial,
            self.reset_to_initial_prompt_would_fit,
        )
        if self.budget_denied:
            if any(item is None for item in denial_fields):
                raise ValueError("budget adequacy denial diagnostics are incomplete")
            if self.terminal_category != "budget_exhausted_no_call":
                raise ValueError("budget adequacy denial lost its terminal")
            if self.certificate_count != self.provider_call_count + 1:
                raise ValueError("budget adequacy denied certificate denominator changed")
            if self.attempted_prompt_count != self.certificate_count + 1:
                raise ValueError("budget adequacy short-circuit Prompt denominator changed")
            if self.post_terminal_short_circuit_prompt_count != 1:
                raise ValueError("budget adequacy denial lost its short-circuit Prompt")
            assert self.denied_request_index is not None
            assert self.token_usage_before_denial is not None
            assert self.remaining_headroom_before_denial is not None
            assert self.prompt_token_upper_bound is not None
            assert self.completion_token_upper_bound is not None
            assert self.request_token_upper_bound is not None
            assert self.required_reserve_tokens is not None
            assert self.projected_without_reserve is not None
            assert self.projected_upper_total is not None
            assert self.request_only_deficit is not None
            assert self.reserve_contribution_to_deficit is not None
            assert self.headroom_deficit is not None
            assert self.minimum_ceiling_for_observed_denied_call is not None
            assert self.denied_prompt_utf8_bytes is not None
            assert self.projected_if_denied_prompt_reset_to_initial is not None
            if self.denied_request_index != self.provider_call_count:
                raise ValueError("budget adequacy denial request index changed")
            if self.remaining_headroom_before_denial != (
                EXPECTED_TOTAL_TOKEN_CEILING - self.token_usage_before_denial
            ):
                raise ValueError("budget adequacy remaining headroom changed")
            if self.prompt_token_upper_bound != (
                self.denied_prompt_utf8_bytes + EXPECTED_CHAT_ENVELOPE
            ):
                raise ValueError("budget adequacy Prompt upper bound changed")
            if self.completion_token_upper_bound != EXPECTED_COMPLETION_BOUND:
                raise ValueError("budget adequacy completion bound changed")
            if self.request_token_upper_bound != (
                self.prompt_token_upper_bound + self.completion_token_upper_bound
            ):
                raise ValueError("budget adequacy request upper bound changed")
            if self.projected_without_reserve != (
                self.token_usage_before_denial + self.request_token_upper_bound
            ):
                raise ValueError("budget adequacy request projection changed")
            if self.projected_upper_total != (
                self.projected_without_reserve + self.required_reserve_tokens
            ):
                raise ValueError("budget adequacy total projection changed")
            expected_request_deficit = max(
                0, self.projected_without_reserve - EXPECTED_TOTAL_TOKEN_CEILING
            )
            expected_deficit = max(0, self.projected_upper_total - EXPECTED_TOTAL_TOKEN_CEILING)
            if self.request_only_deficit != expected_request_deficit:
                raise ValueError("budget adequacy request-only deficit changed")
            if self.headroom_deficit != expected_deficit:
                raise ValueError("budget adequacy total deficit changed")
            if self.reserve_contribution_to_deficit != (
                expected_deficit - expected_request_deficit
            ):
                raise ValueError("budget adequacy reserve contribution changed")
            if self.minimum_ceiling_for_observed_denied_call != self.projected_upper_total:
                raise ValueError("budget adequacy one-call ceiling changed")
            if self.request_would_fit_without_reserves != (expected_request_deficit == 0):
                raise ValueError("budget adequacy reserve counterfactual changed")
            expected_reset = (
                self.token_usage_before_denial
                + self.initial_prompt_utf8_bytes
                + EXPECTED_CHAT_ENVELOPE
                + EXPECTED_COMPLETION_BOUND
                + self.required_reserve_tokens
            )
            if self.projected_if_denied_prompt_reset_to_initial != expected_reset:
                raise ValueError("budget adequacy Prompt-reset diagnostic changed")
            if self.reset_to_initial_prompt_would_fit != (
                expected_reset <= EXPECTED_TOTAL_TOKEN_CEILING
            ):
                raise ValueError("budget adequacy Prompt-reset result changed")
            if self.denial_attribution == "required_reserve" and expected_request_deficit:
                raise ValueError("budget adequacy reserve-only attribution changed")
            if self.denial_attribution == "request_bound" and not expected_request_deficit:
                raise ValueError("budget adequacy request-bound attribution changed")
        elif any(item is not None for item in denial_fields):
            raise ValueError("budget adequacy model-invalid row carries denial diagnostics")
        elif (
            self.terminal_category != "model_invalid_trajectory"
            or self.certificate_count != self.provider_call_count
            or self.attempted_prompt_count != self.certificate_count
            or self.post_terminal_short_circuit_prompt_count != 0
        ):
            raise ValueError("budget adequacy model-invalid control changed")
        if self.final_answer_only_candidate and not (
            self.budget_denied and self.denied_request_kind == "final_answer" and self.stop_ready
        ):
            raise ValueError("budget adequacy final-answer-only classification changed")
        if self.row_id != budget_adequacy_job_row_id(self):
            raise ValueError("budget adequacy Job row identity is invalid")
        return self


class BudgetAdequacyGroupSummary(FrozenModel):
    summary_id: str = Field(min_length=1)
    group_type: Literal["mechanism", "task"]
    group_id: str = Field(min_length=1)
    attempted_count: int = Field(ge=1)
    no_call_count: int = Field(ge=0)
    model_invalid_count: int = Field(ge=0)
    denial_reason_counts: dict[str, int]
    denial_attribution_counts: dict[str, int]
    denied_request_kind_counts: dict[str, int]
    zero_progress_no_call_count: int = Field(ge=0)
    terminal_completed_unverified_no_call_count: int = Field(ge=0)
    failed_observation_count: int = Field(ge=0)
    identical_call_repeat_count: int = Field(ge=0)
    minimum_headroom_deficit: int | None = Field(default=None, ge=0)
    median_headroom_deficit: int | None = Field(default=None, ge=0)
    maximum_headroom_deficit: int | None = Field(default=None, ge=0)
    minimum_prompt_growth_bytes: int | None = Field(default=None, ge=0)
    median_prompt_growth_bytes: int | None = Field(default=None, ge=0)
    maximum_prompt_growth_bytes: int | None = Field(default=None, ge=0)
    descriptive_only: Literal[True] = True
    schema_version: str = GROUP_ROW_VERSION

    @model_validator(mode="after")
    def validate_summary(self) -> BudgetAdequacyGroupSummary:
        if self.attempted_count != self.no_call_count + self.model_invalid_count:
            raise ValueError("budget adequacy group terminal denominator changed")
        if sum(self.denial_reason_counts.values()) != self.no_call_count:
            raise ValueError("budget adequacy group denial-reason denominator changed")
        if sum(self.denial_attribution_counts.values()) != self.no_call_count:
            raise ValueError("budget adequacy group attribution denominator changed")
        if sum(self.denied_request_kind_counts.values()) != self.no_call_count:
            raise ValueError("budget adequacy group request-kind denominator changed")
        metrics = (
            self.minimum_headroom_deficit,
            self.median_headroom_deficit,
            self.maximum_headroom_deficit,
            self.minimum_prompt_growth_bytes,
            self.median_prompt_growth_bytes,
            self.maximum_prompt_growth_bytes,
        )
        if (self.no_call_count == 0) != all(item is None for item in metrics):
            raise ValueError("budget adequacy group optional metrics changed")
        if self.summary_id != budget_adequacy_group_summary_id(self):
            raise ValueError("budget adequacy group identity is invalid")
        return self


class BudgetAdequacyGroupAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    mechanism_summaries: tuple[BudgetAdequacyGroupSummary, ...] = Field(min_length=4, max_length=4)
    task_summaries: tuple[BudgetAdequacyGroupSummary, ...] = Field(min_length=8, max_length=8)
    mechanism_count: Literal[4] = 4
    task_count: Literal[8] = 8
    job_count: Literal[32] = EXPECTED_JOB_COUNT
    status: Literal["passed"] = "passed"
    schema_version: str = GROUP_AUDIT_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> BudgetAdequacyGroupAudit:
        mechanisms = tuple(item.group_id for item in self.mechanism_summaries)
        tasks = tuple(item.group_id for item in self.task_summaries)
        if mechanisms != tuple(sorted(set(mechanisms))):
            raise ValueError("budget adequacy mechanisms are not canonical")
        if tasks != tuple(sorted(set(tasks))):
            raise ValueError("budget adequacy tasks are not canonical")
        if sum(item.attempted_count for item in self.mechanism_summaries) != self.job_count:
            raise ValueError("budget adequacy mechanism denominator changed")
        if sum(item.attempted_count for item in self.task_summaries) != self.job_count:
            raise ValueError("budget adequacy task denominator changed")
        if self.audit_id != budget_adequacy_group_audit_id(self):
            raise ValueError("budget adequacy group audit identity is invalid")
        return self


class BudgetAdequacyRootCauseSummary(FrozenModel):
    audit_id: str = Field(min_length=1)
    rows: tuple[BudgetAdequacyJobDiagnostic, ...] = Field(min_length=32, max_length=32)
    observed_job_count: Literal[32] = EXPECTED_JOB_COUNT
    typed_no_call_count: Literal[24] = EXPECTED_NO_CALL_COUNT
    model_invalid_count: Literal[8] = EXPECTED_MODEL_INVALID_COUNT
    completed_model_trajectory_count: Literal[0] = 0
    denied_request_kind_counts: dict[str, int]
    denial_reason_counts: dict[str, int]
    denial_attribution_counts: dict[str, int]
    no_call_by_mechanism: dict[str, int]
    zero_progress_no_call_count: int = Field(ge=0, le=24)
    positive_progress_no_call_count: int = Field(ge=0, le=24)
    terminal_completed_unverified_no_call_count: int = Field(ge=0, le=24)
    final_answer_only_candidate_count: int = Field(ge=0, le=24)
    failed_observation_count_in_no_call_rows: int = Field(ge=0)
    identical_call_repeat_count_in_no_call_rows: int = Field(ge=0)
    identical_failed_call_repeat_count_in_no_call_rows: int = Field(ge=0)
    minimum_token_usage_before_denial: int = Field(ge=0)
    median_token_usage_before_denial: int = Field(ge=0)
    maximum_token_usage_before_denial: int = Field(ge=0)
    minimum_denied_prompt_utf8_bytes: int = Field(ge=1)
    median_denied_prompt_utf8_bytes: int = Field(ge=1)
    maximum_denied_prompt_utf8_bytes: int = Field(ge=1)
    minimum_prompt_growth_bytes: int = Field(ge=0)
    median_prompt_growth_bytes: int = Field(ge=0)
    maximum_prompt_growth_bytes: int = Field(ge=0)
    minimum_headroom_deficit: int = Field(ge=0)
    median_headroom_deficit: int = Field(ge=0)
    p90_headroom_deficit: int = Field(ge=0)
    maximum_headroom_deficit: int = Field(ge=0)
    common_ceiling_for_only_observed_denied_calls: int = Field(ge=EXPECTED_TOTAL_TOKEN_CEILING)
    request_would_fit_without_reserves_count: int = Field(ge=0, le=24)
    reset_to_initial_prompt_would_fit_count: int = Field(ge=0, le=24)
    all_denials_at_decision_request: bool
    no_prompt_ceiling_denial_observed: bool
    one_more_call_does_not_imply_completion: Literal[True] = True
    prompt_growth_causal_attribution_not_established: Literal[True] = True
    budget_compliance_retained: Literal[True] = True
    budget_adequacy_established: Literal[False] = False
    status: Literal["passed"] = "passed"
    schema_version: str = ROOT_CAUSE_VERSION

    @model_validator(mode="after")
    def validate_summary(self) -> BudgetAdequacyRootCauseSummary:
        if tuple(item.job_id for item in self.rows) != tuple(
            sorted(item.job_id for item in self.rows)
        ):
            raise ValueError("budget adequacy Job rows are not canonical")
        no_calls = tuple(item for item in self.rows if item.budget_denied)
        if len(no_calls) != self.typed_no_call_count:
            raise ValueError("budget adequacy no-call denominator changed")
        if self.model_invalid_count != len(self.rows) - len(no_calls):
            raise ValueError("budget adequacy model-invalid denominator changed")
        if sum(self.denied_request_kind_counts.values()) != len(no_calls):
            raise ValueError("budget adequacy denied-kind denominator changed")
        if sum(self.denial_reason_counts.values()) != len(no_calls):
            raise ValueError("budget adequacy denial-reason denominator changed")
        if sum(self.denial_attribution_counts.values()) != len(no_calls):
            raise ValueError("budget adequacy attribution denominator changed")
        if sum(self.no_call_by_mechanism.values()) != len(no_calls):
            raise ValueError("budget adequacy mechanism no-call denominator changed")
        if self.zero_progress_no_call_count + self.positive_progress_no_call_count != len(no_calls):
            raise ValueError("budget adequacy progress denominator changed")
        projected = tuple(
            cast(int, item.minimum_ceiling_for_observed_denied_call) for item in no_calls
        )
        if self.common_ceiling_for_only_observed_denied_calls != max(projected):
            raise ValueError("budget adequacy observed one-call ceiling changed")
        if self.audit_id != budget_adequacy_root_cause_id(self):
            raise ValueError("budget adequacy root-cause identity is invalid")
        return self


class BudgetAdequacyDecision(FrozenModel):
    decision_id: str = Field(min_length=1)
    root_cause_audit_id: str = Field(min_length=1)
    group_audit_id: str = Field(min_length=1)
    recovery_report_id: str = EXPECTED_RECOVERY_REPORT_ID
    postrun_audit_report_id: str = EXPECTED_POSTRUN_AUDIT_REPORT_ID
    budget_compliance_status: Literal["retained_passed"] = "retained_passed"
    budget_adequacy_status: Literal["not_established"] = "not_established"
    observed_budget_censoring_dominant: Literal[True] = True
    model_policy_efficiency_confounding_retained: Literal[True] = True
    direct_total_budget_increase_authorized: Literal[False] = False
    prompt_compression_change_authorized: Literal[False] = False
    reserve_reduction_authorized: Literal[False] = False
    historical_result_reclassified: Literal[False] = False
    static_budgeted_public_witness_required: Literal[True] = True
    per_reachability_path_budget_witness_required: Literal[True] = True
    same_budget_for_natural_and_conditioned_paths_required: Literal[True] = True
    completed_runner_control_required: Literal[True] = True
    independent_calibration_no_call_gate_required: Literal[True] = True
    empirical_no_call_threshold_frozen: Literal[False] = False
    next_permitted_stage: Literal[
        "fresh_budget_adequacy_contract_and_static_role_preflight_only"
    ] = "fresh_budget_adequacy_contract_and_static_role_preflight_only"
    capability_development_execution_authorized: Literal[False] = False
    state_reachability_execution_authorized: Literal[False] = False
    fresh_confirmation_authorized: Literal[False] = False
    no_c_vtdo_authorized: Literal[False] = False
    student_training_authorized: Literal[False] = False
    exact_target_authorized: Literal[False] = False
    gp_c_authorized: Literal[False] = False
    production_contribution: Literal[0] = 0
    model_client_constructed: Literal[False] = False
    model_api_calls: Literal[0] = 0
    gpu_jobs: Literal[0] = 0
    status: Literal["passed"] = "passed"
    schema_version: str = DECISION_VERSION

    @model_validator(mode="after")
    def validate_decision(self) -> BudgetAdequacyDecision:
        if self.decision_id != budget_adequacy_decision_id(self):
            raise ValueError("budget adequacy decision identity is invalid")
        return self


class DetailFile(FrozenModel):
    relative_path: str = Field(min_length=1)
    sha256: str = Field(min_length=64, max_length=64)
    byte_count: int = Field(ge=1)


class BudgetAdequacyRootCauseReport(FrozenModel):
    report_id: str = Field(min_length=1)
    source_replay_audit_id: str = Field(min_length=1)
    root_cause_audit_id: str = Field(min_length=1)
    group_audit_id: str = Field(min_length=1)
    decision_id: str = Field(min_length=1)
    recovery_report_id: str = EXPECTED_RECOVERY_REPORT_ID
    postrun_audit_report_id: str = EXPECTED_POSTRUN_AUDIT_REPORT_ID
    immutable_detail_files: tuple[DetailFile, ...] = Field(min_length=4, max_length=4)
    model_client_constructed: Literal[False] = False
    model_api_calls: Literal[0] = 0
    gpu_jobs: Literal[0] = 0
    status: Literal["passed"] = "passed"
    next_permitted_stage: Literal[
        "fresh_budget_adequacy_contract_and_static_role_preflight_only"
    ] = "fresh_budget_adequacy_contract_and_static_role_preflight_only"
    production_contribution: Literal[0] = 0
    schema_version: str = REPORT_VERSION

    @model_validator(mode="after")
    def validate_report(self) -> BudgetAdequacyRootCauseReport:
        names = tuple(item.relative_path for item in self.immutable_detail_files)
        if names != tuple(sorted(set(names))):
            raise ValueError("budget adequacy detail files are not canonical")
        if self.report_id != budget_adequacy_report_id(self):
            raise ValueError("budget adequacy report identity is invalid")
        return self


T = TypeVar("T", bound=BaseModel)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _write_json(path: Path, payload: Any) -> None:
    serialized = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if path.exists():
        if path.read_text(encoding="utf-8") != serialized:
            raise ValueError(f"immutable budget adequacy JSON changed: {path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(serialized, encoding="utf-8")
    temporary.replace(path)


def _relative_to_package(path: Path, package_root: Path) -> str:
    try:
        return str(path.resolve().relative_to(package_root.resolve()))
    except ValueError as exc:
        raise ValueError(f"budget adequacy source escapes package root: {path}") from exc


def _canonical_json_payload(path: Path) -> dict[str, Any]:
    raw = path.read_bytes()
    payload = json.loads(raw)
    canonical = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    if raw != canonical:
        raise ValueError(f"budget adequacy Raw Artifact is not canonical JSON: {path}")
    if not isinstance(payload, dict):
        raise ValueError(f"budget adequacy Raw Artifact is not an object: {path}")
    return payload


def _load_rows(path: Path, model: type[T]) -> tuple[T, ...]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError(f"budget adequacy expected a JSON list: {path}")
    return tuple(model.model_validate(item) for item in payload)


def _build_source_replay(
    *,
    postrun_audit_dir: Path,
    postrun_report: BudgetPostrunAuditReport,
    package_root: Path,
) -> BudgetAdequacySourceReplayAudit:
    inherited = BudgetPostrunSourceReplayAudit.model_validate_json(
        (postrun_audit_dir / "source_replay_audit.json").read_text(encoding="utf-8")
    )
    expected: dict[str, tuple[str, str]] = {}

    def register(relative: str, sha256: str, kind: str) -> None:
        prior = expected.get(relative)
        if prior is not None and prior[0] != sha256:
            raise ValueError(f"budget adequacy source manifests disagree: {relative}")
        expected[relative] = prior or (sha256, kind)

    for item in inherited.entries:
        register(item.relative_path, item.expected_sha256, "v26_87_replayed_source")
    for detail in postrun_report.immutable_detail_files:
        path = postrun_audit_dir / detail.relative_path
        if _sha256(path) != detail.sha256 or path.stat().st_size != detail.byte_count:
            raise ValueError(f"budget adequacy received changed v26.87 detail: {path}")
        register(
            _relative_to_package(path, package_root),
            detail.sha256,
            "v26_87_audit_output",
        )
    report_path = postrun_audit_dir / "report.json"
    register(
        _relative_to_package(report_path, package_root),
        _sha256(report_path),
        "v26_87_audit_output",
    )
    register(
        AUDIT_MODULE_PATH,
        _sha256(package_root / AUDIT_MODULE_PATH),
        "v26_88_implementation",
    )
    entries = tuple(
        BudgetAdequacySourceEntry(
            relative_path=relative,
            expected_sha256=expected_sha,
            observed_sha256=_sha256(package_root / relative),
            byte_count=(package_root / relative).stat().st_size,
            source_kind=cast(Any, kind),
        )
        for relative, (expected_sha, kind) in sorted(expected.items())
    )
    values = {
        "entries": entries,
        "replayed_file_count": len(entries),
        "replay_pass_count": len(entries),
    }
    provisional = BudgetAdequacySourceReplayAudit.model_construct(audit_id="pending", **values)
    return BudgetAdequacySourceReplayAudit(
        audit_id=budget_adequacy_source_audit_id(provisional), **values
    )


def _observations(raw: BudgetRecoveryRawExecution) -> tuple[AgentToolObservation, ...]:
    if raw.solve_result is not None:
        return raw.solve_result.observations
    if raw.failure_artifact is not None:
        return raw.failure_artifact.observations
    return ()


def _observation_bytes(observations: Sequence[AgentToolObservation]) -> int:
    return sum(
        len(
            json.dumps(
                item.model_dump(mode="json"),
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        )
        for item in observations
    )


def _repeat_counts(observations: Sequence[AgentToolObservation]) -> tuple[int, int]:
    all_calls = Counter(
        canonical_hash(
            {"tool_id": item.call.tool_id, "arguments": item.call.arguments},
            prefix="finance_v26_budget_call_signature:",
        )
        for item in observations
    )
    failed_calls = Counter(
        canonical_hash(
            {"tool_id": item.call.tool_id, "arguments": item.call.arguments},
            prefix="finance_v26_budget_call_signature:",
        )
        for item in observations
        if item.status == "failed"
    )
    return (
        sum(max(0, count - 1) for count in all_calls.values()),
        sum(max(0, count - 1) for count in failed_calls.values()),
    )


def _progress_class(
    *,
    completed: int,
    required: int,
    terminal_completed: bool,
    verification_completed: bool,
    stop_ready: bool,
) -> ProgressClass:
    if stop_ready and verification_completed:
        return "verified_stop_ready"
    if terminal_completed:
        return "terminal_completed_unverified"
    if completed == 0:
        return "no_registered_node_completed"
    if completed == required - 1:
        return "one_required_node_remaining"
    return "partial_program"


def _denial_attribution(reason: str) -> DenialAttribution:
    if reason == "request_bound_exceeds_remaining_budget":
        return "request_bound"
    if reason == "required_reserve_not_available":
        return "required_reserve"
    if reason == "oversized_prompt":
        return "prompt_ceiling"
    raise ValueError(f"budget adequacy received another no-call reason: {reason}")


def _build_job_rows(
    *,
    recovery_dir: Path,
    records: Sequence[OperationalTaskRecord],
    rollouts: Sequence[BudgetClosedInstrumentRollout],
    diagnostics: Sequence[BudgetClosedRolloutDiagnostic],
    budget_contract: ProviderTokenBudgetContract,
) -> tuple[BudgetAdequacyJobDiagnostic, ...]:
    if (
        budget_contract.contract_id != EXPECTED_BUDGET_CONTRACT_ID
        or budget_contract.maximum_total_tokens != EXPECTED_TOTAL_TOKEN_CEILING
        or budget_contract.maximum_prompt_utf8_bytes != EXPECTED_PROMPT_BYTE_CEILING
        or budget_contract.maximum_output_tokens != EXPECTED_COMPLETION_BOUND
        or budget_contract.contract_repair_reserve_tokens != EXPECTED_REPAIR_RESERVE
        or budget_contract.final_answer_reserve_tokens != EXPECTED_FINAL_RESERVE
        or budget_contract.provider_chat_envelope_token_upper_bound != EXPECTED_CHAT_ENVELOPE
    ):
        raise ValueError("budget adequacy audit received another Provider budget Contract")
    records_by_id = {item.record_id: item for item in records}
    diagnostics_by_job = {item.job_id: item for item in diagnostics}
    rows: list[BudgetAdequacyJobDiagnostic] = []
    for rollout in rollouts:
        raw_path = Path(rollout.raw_execution_artifact_uri)
        if _sha256(raw_path) != rollout.raw_execution_artifact_sha256:
            raise ValueError("budget adequacy Raw Execution bytes changed")
        raw = BudgetRecoveryRawExecution.model_validate(_canonical_json_payload(raw_path))
        if raw.job.job_id != rollout.job_id or raw.task_record_id != rollout.task_record_id:
            raise ValueError("budget adequacy Raw Execution binding changed")
        record = records_by_id[rollout.task_record_id]
        frozen = diagnostics_by_job[rollout.job_id]
        observations = _observations(raw)
        progress = public_operation_progress(record.task_package.task.public, observations)
        if progress is None:
            raise ValueError("budget adequacy audit lost public Program progress")
        required = len(record.task_package.stop_readiness_contract.required_node_ids)
        completed = len(progress["completed_node_ids"])
        terminal_completed = bool(progress["terminal_node_completed"])
        verification_completed = bool(progress["verification_after_terminal_completed"])
        stop_ready = bool(progress["stop_ready"])
        progress_matches = bool(
            frozen.required_node_count == required
            and frozen.completed_node_count == completed
            and frozen.terminal_node_completed == terminal_completed
            and frozen.postterminal_verification_completed == verification_completed
            and frozen.stop_ready == stop_ready
            and frozen.failed_observation_count
            == sum(item.status == "failed" for item in observations)
        )
        certificates = raw.provider_budget_audit.certificates
        prompt_bytes = tuple(item.prompt_utf8_bytes for item in certificates)
        request_kinds = tuple(item.request_kind for item in certificates)
        usage_tokens = tuple(
            item.counted_tokens for item in raw.provider_budget_audit.usage_records
        )
        repeat_count, failed_repeat_count = _repeat_counts(observations)
        no_call = raw.provider_budget_audit.no_call_terminal is not None
        denied = certificates[-1] if no_call else None
        last_permitted = certificates[-2] if no_call else certificates[-1]
        attribution = (
            _denial_attribution(cast(str, denied.denial_reason)) if denied is not None else None
        )
        cumulative = denied.cumulative_provider_tokens_before if denied is not None else None
        projected_without_reserve = (
            cumulative + denied.request_token_upper_bound
            if denied is not None and cumulative is not None
            else None
        )
        projected = denied.projected_upper_total if denied is not None else None
        request_deficit = (
            max(0, cast(int, projected_without_reserve) - EXPECTED_TOTAL_TOKEN_CEILING)
            if projected_without_reserve is not None
            else None
        )
        total_deficit = (
            max(0, cast(int, projected) - EXPECTED_TOTAL_TOKEN_CEILING)
            if projected is not None
            else None
        )
        reset_projection = (
            cast(int, cumulative)
            + prompt_bytes[0]
            + EXPECTED_CHAT_ENVELOPE
            + EXPECTED_COMPLETION_BOUND
            + cast(int, denied.required_reserve_tokens)
            if denied is not None
            else None
        )
        progress_class = _progress_class(
            completed=completed,
            required=required,
            terminal_completed=terminal_completed,
            verification_completed=verification_completed,
            stop_ready=stop_ready,
        )
        values = {
            "job_id": rollout.job_id,
            "rollout_id": rollout.rollout_id,
            "task_package_id": rollout.task_package_id,
            "task_record_id": rollout.task_record_id,
            "mechanism_id": rollout.mechanism_id,
            "replicate_index": rollout.replicate_index,
            "recovery_role": raw.recovery_role,
            "terminal_category": rollout.terminal_category,
            "provider_call_count": rollout.provider_call_count,
            "provider_total_tokens": rollout.provider_total_tokens,
            "certificate_count": len(certificates),
            "attempted_prompt_count": len(raw.attempted_model_prompts),
            "post_terminal_short_circuit_prompt_count": len(
                raw.post_terminal_short_circuit_prompts
            ),
            "request_kind_sequence": request_kinds,
            "prompt_utf8_bytes_sequence": prompt_bytes,
            "provider_total_token_sequence": usage_tokens,
            "initial_prompt_utf8_bytes": prompt_bytes[0],
            "final_certificate_prompt_utf8_bytes": prompt_bytes[-1],
            "maximum_certificate_prompt_utf8_bytes": max(prompt_bytes),
            "prompt_growth_from_initial_bytes": prompt_bytes[-1] - prompt_bytes[0],
            "observation_count": len(observations),
            "observation_artifact_utf8_bytes": _observation_bytes(observations),
            "successful_observation_count": sum(
                item.status == "succeeded" for item in observations
            ),
            "failed_observation_count": sum(item.status == "failed" for item in observations),
            "identical_call_repeat_count": repeat_count,
            "identical_failed_call_repeat_count": failed_repeat_count,
            "required_node_count": required,
            "completed_node_count": completed,
            "remaining_node_count": required - completed,
            "terminal_node_completed": terminal_completed,
            "postterminal_verification_completed": verification_completed,
            "stop_ready": stop_ready,
            "progress_class": progress_class,
            "program_progress_matches_frozen_diagnostic": progress_matches,
            "budget_denied": no_call,
            "denied_request_index": denied.request_index if denied is not None else None,
            "denied_request_kind": denied.request_kind if denied is not None else None,
            "denied_repaired_request_kind": (
                denied.repaired_request_kind if denied is not None else None
            ),
            "denial_reason": denied.denial_reason if denied is not None else None,
            "denial_attribution": attribution,
            "token_usage_before_denial": cumulative,
            "remaining_headroom_before_denial": (
                EXPECTED_TOTAL_TOKEN_CEILING - cast(int, cumulative)
                if cumulative is not None
                else None
            ),
            "denied_prompt_utf8_bytes": denied.prompt_utf8_bytes if denied is not None else None,
            "denied_prompt_increment_from_last_permitted": (
                denied.prompt_utf8_bytes - last_permitted.prompt_utf8_bytes
                if denied is not None
                else None
            ),
            "prompt_token_upper_bound": (
                denied.prompt_token_upper_bound if denied is not None else None
            ),
            "completion_token_upper_bound": (
                denied.completion_token_upper_bound if denied is not None else None
            ),
            "request_token_upper_bound": (
                denied.request_token_upper_bound if denied is not None else None
            ),
            "contract_repair_reserve_tokens": (
                denied.contract_repair_reserve_tokens if denied is not None else None
            ),
            "final_answer_reserve_tokens": (
                denied.final_answer_reserve_tokens if denied is not None else None
            ),
            "required_reserve_tokens": (
                denied.required_reserve_tokens if denied is not None else None
            ),
            "projected_without_reserve": projected_without_reserve,
            "projected_upper_total": projected,
            "request_only_deficit": request_deficit,
            "reserve_contribution_to_deficit": (
                cast(int, total_deficit) - cast(int, request_deficit)
                if total_deficit is not None and request_deficit is not None
                else None
            ),
            "headroom_deficit": total_deficit,
            "minimum_ceiling_for_observed_denied_call": projected,
            "request_would_fit_without_reserves": (
                request_deficit == 0 if request_deficit is not None else None
            ),
            "projected_if_denied_prompt_reset_to_initial": reset_projection,
            "reset_to_initial_prompt_would_fit": (
                reset_projection <= EXPECTED_TOTAL_TOKEN_CEILING
                if reset_projection is not None
                else None
            ),
            "final_answer_only_candidate": bool(
                no_call
                and denied is not None
                and denied.request_kind == "final_answer"
                and stop_ready
            ),
        }
        provisional = BudgetAdequacyJobDiagnostic.model_construct(row_id="pending", **values)
        rows.append(
            BudgetAdequacyJobDiagnostic(row_id=budget_adequacy_job_row_id(provisional), **values)
        )
    return tuple(sorted(rows, key=lambda item: item.job_id))


def _nearest_rank(values: Sequence[int], numerator: int, denominator: int) -> int:
    ordered = sorted(values)
    if not ordered:
        raise ValueError("budget adequacy quantile received no values")
    index = max(0, math.ceil(len(ordered) * numerator / denominator) - 1)
    return ordered[index]


def _counter(values: Sequence[str]) -> dict[str, int]:
    return dict(sorted(Counter(values).items()))


def _build_group_summary(
    *,
    group_type: Literal["mechanism", "task"],
    group_id: str,
    rows: Sequence[BudgetAdequacyJobDiagnostic],
) -> BudgetAdequacyGroupSummary:
    no_calls = tuple(item for item in rows if item.budget_denied)
    deficits = tuple(cast(int, item.headroom_deficit) for item in no_calls)
    growth = tuple(item.prompt_growth_from_initial_bytes for item in no_calls)
    values = {
        "group_type": group_type,
        "group_id": group_id,
        "attempted_count": len(rows),
        "no_call_count": len(no_calls),
        "model_invalid_count": len(rows) - len(no_calls),
        "denial_reason_counts": _counter(tuple(cast(str, item.denial_reason) for item in no_calls)),
        "denial_attribution_counts": _counter(
            tuple(cast(str, item.denial_attribution) for item in no_calls)
        ),
        "denied_request_kind_counts": _counter(
            tuple(cast(str, item.denied_request_kind) for item in no_calls)
        ),
        "zero_progress_no_call_count": sum(item.completed_node_count == 0 for item in no_calls),
        "terminal_completed_unverified_no_call_count": sum(
            item.progress_class == "terminal_completed_unverified" for item in no_calls
        ),
        "failed_observation_count": sum(item.failed_observation_count for item in rows),
        "identical_call_repeat_count": sum(item.identical_call_repeat_count for item in rows),
        "minimum_headroom_deficit": min(deficits) if deficits else None,
        "median_headroom_deficit": _nearest_rank(deficits, 1, 2) if deficits else None,
        "maximum_headroom_deficit": max(deficits) if deficits else None,
        "minimum_prompt_growth_bytes": min(growth) if growth else None,
        "median_prompt_growth_bytes": _nearest_rank(growth, 1, 2) if growth else None,
        "maximum_prompt_growth_bytes": max(growth) if growth else None,
    }
    provisional = BudgetAdequacyGroupSummary.model_construct(summary_id="pending", **values)
    return BudgetAdequacyGroupSummary(
        summary_id=budget_adequacy_group_summary_id(provisional), **values
    )


def _build_group_audit(
    rows: Sequence[BudgetAdequacyJobDiagnostic],
) -> BudgetAdequacyGroupAudit:
    mechanisms = tuple(sorted({item.mechanism_id for item in rows}))
    tasks = tuple(sorted({item.task_package_id for item in rows}))
    mechanism_summaries = tuple(
        _build_group_summary(
            group_type="mechanism",
            group_id=mechanism,
            rows=tuple(item for item in rows if item.mechanism_id == mechanism),
        )
        for mechanism in mechanisms
    )
    task_summaries = tuple(
        _build_group_summary(
            group_type="task",
            group_id=task,
            rows=tuple(item for item in rows if item.task_package_id == task),
        )
        for task in tasks
    )
    values = {
        "mechanism_summaries": mechanism_summaries,
        "task_summaries": task_summaries,
    }
    provisional = BudgetAdequacyGroupAudit.model_construct(audit_id="pending", **values)
    return BudgetAdequacyGroupAudit(audit_id=budget_adequacy_group_audit_id(provisional), **values)


def _build_root_cause(
    rows: tuple[BudgetAdequacyJobDiagnostic, ...],
) -> BudgetAdequacyRootCauseSummary:
    no_calls = tuple(item for item in rows if item.budget_denied)
    usage = tuple(cast(int, item.token_usage_before_denial) for item in no_calls)
    prompts = tuple(cast(int, item.denied_prompt_utf8_bytes) for item in no_calls)
    growth = tuple(item.prompt_growth_from_initial_bytes for item in no_calls)
    deficits = tuple(cast(int, item.headroom_deficit) for item in no_calls)
    values = {
        "rows": rows,
        "typed_no_call_count": len(no_calls),
        "model_invalid_count": len(rows) - len(no_calls),
        "denied_request_kind_counts": _counter(
            tuple(cast(str, item.denied_request_kind) for item in no_calls)
        ),
        "denial_reason_counts": _counter(tuple(cast(str, item.denial_reason) for item in no_calls)),
        "denial_attribution_counts": _counter(
            tuple(cast(str, item.denial_attribution) for item in no_calls)
        ),
        "no_call_by_mechanism": _counter(tuple(item.mechanism_id for item in no_calls)),
        "zero_progress_no_call_count": sum(item.completed_node_count == 0 for item in no_calls),
        "positive_progress_no_call_count": sum(item.completed_node_count > 0 for item in no_calls),
        "terminal_completed_unverified_no_call_count": sum(
            item.progress_class == "terminal_completed_unverified" for item in no_calls
        ),
        "final_answer_only_candidate_count": sum(
            item.final_answer_only_candidate for item in no_calls
        ),
        "failed_observation_count_in_no_call_rows": sum(
            item.failed_observation_count for item in no_calls
        ),
        "identical_call_repeat_count_in_no_call_rows": sum(
            item.identical_call_repeat_count for item in no_calls
        ),
        "identical_failed_call_repeat_count_in_no_call_rows": sum(
            item.identical_failed_call_repeat_count for item in no_calls
        ),
        "minimum_token_usage_before_denial": min(usage),
        "median_token_usage_before_denial": _nearest_rank(usage, 1, 2),
        "maximum_token_usage_before_denial": max(usage),
        "minimum_denied_prompt_utf8_bytes": min(prompts),
        "median_denied_prompt_utf8_bytes": _nearest_rank(prompts, 1, 2),
        "maximum_denied_prompt_utf8_bytes": max(prompts),
        "minimum_prompt_growth_bytes": min(growth),
        "median_prompt_growth_bytes": _nearest_rank(growth, 1, 2),
        "maximum_prompt_growth_bytes": max(growth),
        "minimum_headroom_deficit": min(deficits),
        "median_headroom_deficit": _nearest_rank(deficits, 1, 2),
        "p90_headroom_deficit": _nearest_rank(deficits, 9, 10),
        "maximum_headroom_deficit": max(deficits),
        "common_ceiling_for_only_observed_denied_calls": max(
            cast(int, item.minimum_ceiling_for_observed_denied_call) for item in no_calls
        ),
        "request_would_fit_without_reserves_count": sum(
            item.request_would_fit_without_reserves is True for item in no_calls
        ),
        "reset_to_initial_prompt_would_fit_count": sum(
            item.reset_to_initial_prompt_would_fit is True for item in no_calls
        ),
        "all_denials_at_decision_request": all(
            item.denied_request_kind == "decision" for item in no_calls
        ),
        "no_prompt_ceiling_denial_observed": all(
            item.denial_attribution != "prompt_ceiling" for item in no_calls
        ),
    }
    provisional = BudgetAdequacyRootCauseSummary.model_construct(audit_id="pending", **values)
    return BudgetAdequacyRootCauseSummary(
        audit_id=budget_adequacy_root_cause_id(provisional), **values
    )


def _build_decision(
    *,
    root_cause: BudgetAdequacyRootCauseSummary,
    group_audit: BudgetAdequacyGroupAudit,
) -> BudgetAdequacyDecision:
    values = {
        "root_cause_audit_id": root_cause.audit_id,
        "group_audit_id": group_audit.audit_id,
    }
    provisional = BudgetAdequacyDecision.model_construct(decision_id="pending", **values)
    return BudgetAdequacyDecision(decision_id=budget_adequacy_decision_id(provisional), **values)


def build_budget_adequacy_root_cause_audit(
    *,
    recovery_dir: Path,
    postrun_audit_dir: Path,
    task_source_dir: Path,
    output_dir: Path,
    package_root: Path,
) -> BudgetAdequacyRootCauseReport:
    recovery_report = BudgetRecoveryReport.model_validate_json(
        (recovery_dir / "report.json").read_text(encoding="utf-8")
    )
    postrun_report = BudgetPostrunAuditReport.model_validate_json(
        (postrun_audit_dir / "report.json").read_text(encoding="utf-8")
    )
    if (
        recovery_report.report_id != EXPECTED_RECOVERY_REPORT_ID
        or postrun_report.report_id != EXPECTED_POSTRUN_AUDIT_REPORT_ID
        or postrun_report.recovery_report_id != recovery_report.report_id
    ):
        raise ValueError("budget adequacy audit received another instrument result")
    source = _build_source_replay(
        postrun_audit_dir=postrun_audit_dir,
        postrun_report=postrun_report,
        package_root=package_root,
    )
    rollouts = _load_rows(recovery_dir / "rollout_aggregate.json", BudgetClosedInstrumentRollout)
    diagnostics = _load_rows(
        recovery_dir / "rollout_diagnostics.json", BudgetClosedRolloutDiagnostic
    )
    records = _load_rows(task_source_dir / "operational_task_records.json", OperationalTaskRecord)
    budget_contract = ProviderTokenBudgetContract.model_validate_json(
        (task_source_dir / "provider_token_budget_contract.json").read_text(encoding="utf-8")
    )
    if (
        len(rollouts) != EXPECTED_JOB_COUNT
        or len(diagnostics) != EXPECTED_JOB_COUNT
        or len(records) != 8
    ):
        raise ValueError("budget adequacy input denominator changed")
    rows = _build_job_rows(
        recovery_dir=recovery_dir,
        records=records,
        rollouts=rollouts,
        diagnostics=diagnostics,
        budget_contract=budget_contract,
    )
    root_cause = _build_root_cause(rows)
    group_audit = _build_group_audit(rows)
    decision = _build_decision(root_cause=root_cause, group_audit=group_audit)
    output_dir.mkdir(parents=True, exist_ok=True)
    detail_payloads = {
        "budget_adequacy_decision.json": decision.model_dump(mode="json"),
        "group_budget_summary.json": group_audit.model_dump(mode="json"),
        "job_budget_diagnostics.json": root_cause.model_dump(mode="json"),
        "source_replay_audit.json": source.model_dump(mode="json"),
    }
    for relative, payload in detail_payloads.items():
        _write_json(output_dir / relative, payload)
    details = tuple(
        DetailFile(
            relative_path=relative,
            sha256=_sha256(output_dir / relative),
            byte_count=(output_dir / relative).stat().st_size,
        )
        for relative in sorted(detail_payloads)
    )
    values = {
        "source_replay_audit_id": source.audit_id,
        "root_cause_audit_id": root_cause.audit_id,
        "group_audit_id": group_audit.audit_id,
        "decision_id": decision.decision_id,
        "immutable_detail_files": details,
    }
    provisional = BudgetAdequacyRootCauseReport.model_construct(report_id="pending", **values)
    report = BudgetAdequacyRootCauseReport(
        report_id=budget_adequacy_report_id(provisional), **values
    )
    _write_json(output_dir / "report.json", report.model_dump(mode="json"))
    return report


def budget_adequacy_source_audit_id(value: BudgetAdequacySourceReplayAudit) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"audit_id"}),
        prefix="finance_v26_budget_adequacy_source_replay:",
    )


def budget_adequacy_job_row_id(value: BudgetAdequacyJobDiagnostic) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"row_id"}),
        prefix="finance_v26_budget_adequacy_job_diagnostic:",
    )


def budget_adequacy_group_summary_id(value: BudgetAdequacyGroupSummary) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"summary_id"}),
        prefix="finance_v26_budget_adequacy_group_summary:",
    )


def budget_adequacy_group_audit_id(value: BudgetAdequacyGroupAudit) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"audit_id"}),
        prefix="finance_v26_budget_adequacy_group_audit:",
    )


def budget_adequacy_root_cause_id(value: BudgetAdequacyRootCauseSummary) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"audit_id"}),
        prefix="finance_v26_budget_adequacy_root_cause:",
    )


def budget_adequacy_decision_id(value: BudgetAdequacyDecision) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"decision_id"}),
        prefix="finance_v26_budget_adequacy_decision:",
    )


def budget_adequacy_report_id(value: BudgetAdequacyRootCauseReport) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"report_id"}),
        prefix="finance_v26_budget_adequacy_root_cause_report:",
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the credential-free v26.88 Budget Adequacy root-cause audit."
    )
    parser.add_argument("--recovery-dir", type=Path, required=True)
    parser.add_argument("--postrun-audit-dir", type=Path, required=True)
    parser.add_argument("--task-source-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--package-root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    report = build_budget_adequacy_root_cause_audit(
        recovery_dir=args.recovery_dir,
        postrun_audit_dir=args.postrun_audit_dir,
        task_source_dir=args.task_source_dir,
        output_dir=args.output_dir,
        package_root=args.package_root,
    )
    print(json.dumps(report.model_dump(mode="json"), ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
