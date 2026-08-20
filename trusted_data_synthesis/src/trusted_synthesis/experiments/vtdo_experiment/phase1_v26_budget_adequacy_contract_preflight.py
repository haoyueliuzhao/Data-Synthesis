from __future__ import annotations

import argparse
import hashlib
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Literal, TypeVar, cast

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.core.trajectory.executable_task import (
    StaticModelAuthorityPathCatalog,
    matching_sufficient_support_set,
)
from trusted_synthesis.core.trajectory.schema import Trajectory
from trusted_synthesis.domains.finance.executable_support_runtime import (
    FinanceExecutableSupportRuntime,
)
from trusted_synthesis.domains.finance.interactive_agent_runtime import (
    FinanceTypedRecoveryScenario,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_authority_preserving_verifier_replay import (  # noqa: E501
    AuthorityPreservingReplayContract,
    AuthorityPreservingReplayResult,
    AuthorityPreservingVerificationReport,
    AuthorityPreservingVerifierQualificationReport,
    replay_authority_preserving_observations,
    verify_authority_preserving_agent_result,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_budget_adequacy_root_cause_audit import (  # noqa: E501
    BudgetAdequacyDecision,
    BudgetAdequacyRootCauseReport,
    BudgetAdequacyRootCauseSummary,
    BudgetAdequacySourceReplayAudit,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_budget_closed_instrument import (  # noqa: E501
    CompletedTrajectoryScore,
    score_completed_trajectory,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_budget_closed_instrument_preflight import (  # noqa: E501
    BudgetClosedInstrumentContract,
    BudgetClosedInstrumentPreflightReport,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_budget_closed_task_rematerialization import (  # noqa: E501
    BudgetClosedInstrumentPopulationReport,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_empirical_support_pilot import (  # noqa: E501
    evaluate_mechanism_estimand,
    match_empirical_program,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_public_operation_rematerialization import (  # noqa: E501
    OperationalTaskRecord,
)
from trusted_synthesis.hashing import canonical_hash
from trusted_synthesis.runtime.agent.budget_closed import (
    BudgetClosedJsonClient,
    ProviderTokenBudgetAudit,
    ProviderTokenBudgetContract,
)
from trusted_synthesis.runtime.agent.iterative import (
    IterativeAgentProtocolProfile,
    IterativeAgentSolver,
    IterativeAgentSolveResult,
)
from trusted_synthesis.runtime.agent.schema import AgentModelConfig, ModelCallTelemetry
from trusted_synthesis.runtime.tools import (
    AgentToolEnvironmentManifest,
    AgentToolObservation,
)

EXPECTED_ROOT_CAUSE_REPORT_ID = (
    "finance_v26_budget_adequacy_root_cause_report:"
    "bfc54e2c179a475e6f7e6996d844cf4df2e162094668e51e701dd4ce8385ae3f"
)
EXPECTED_ROOT_CAUSE_DECISION_ID = (
    "finance_v26_budget_adequacy_decision:"
    "ad12e014992c31e995e981af1de3cfabf0425595491f5b31ad0e29a9465927a6"
)
EXPECTED_TASK_SOURCE_REPORT_ID = (
    "finance_v26_budget_closed_verifier_bound_instrument_population_report:"
    "9f60f8d7c7522a1fd934bb5a7cdfefb2c91becc73f7e68b2f815dea352ad6484"
)
EXPECTED_INSTRUMENT_PREFLIGHT_REPORT_ID = (
    "finance_v26_budget_closed_instrument_preflight:"
    "6c279f69cb080458952dfb000633f17c4f901aa8098dfac0cb423656ad9684a7"
)
EXPECTED_VERIFIER_QUALIFICATION_REPORT_ID = (
    "finance_v26_authority_verifier_qualification:"
    "f61be6be022c2c8506e818e3bb9690e71fa316c6820fec69458c7ab7c8fa7bb1"
)
EXPECTED_PROVIDER_BUDGET_CONTRACT_ID = (
    "provider_token_budget_contract:"
    "27e7e524cb3139b9dd29b1ca7f2c7eae1956c96af8a982524f814b3ef4415150"
)

EXPECTED_FIXTURE_TASK_COUNT: Literal[8] = 8
EXPECTED_TOTAL_TOKEN_CEILING: Literal[120000] = 120_000
EXPECTED_PROMPT_BYTE_CEILING: Literal[60000] = 60_000
EXPECTED_COMPLETION_BOUND: Literal[4096] = 4_096
EXPECTED_REPAIR_RESERVE: Literal[4096] = 4_096
EXPECTED_FINAL_RESERVE: Literal[4096] = 4_096
EXPECTED_CHAT_ENVELOPE: Literal[256] = 256
CAPABILITY_TASK_COUNT: Literal[12] = 12
CAPABILITY_REPLICAS_PER_TASK: Literal[8] = 8
CAPABILITY_JOB_COUNT: Literal[96] = 96
REACHABILITY_TASK_COUNT: Literal[12] = 12
REACHABILITY_PATHS_PER_TASK: Literal[3] = 3
REACHABILITY_STATE_COUNT: Literal[36] = 36
REACHABILITY_NATURAL_JOB_COUNT: Literal[144] = 144
REACHABILITY_CONDITIONED_JOB_COUNT: Literal[216] = 216
REACHABILITY_JOB_COUNT: Literal[360] = 360
CALIBRATION_MINIMUM_JOB_COUNT: Literal[32] = 32
MAXIMUM_NO_CALL_RATE_NUMERATOR: Literal[1] = 1
MAXIMUM_NO_CALL_RATE_DENOMINATOR: Literal[10] = 10

FRESHNESS_CHANNELS = (
    "source_task_artifact_id",
    "source_task_semantic_signature",
    "source_task_hash",
    "evidence_id",
    "evidence_version_id",
    "source_record_id",
    "semantic_source_id",
    "task_package_id",
    "job_id",
)
RUNNER_STAGE_ORDER = (
    "compiler_witness",
    "raw_execution_persisted",
    "verifier_v2_replay",
    "independent_non_replay_scoring",
    "shared_completed_trajectory_scorer",
    "schema_closed_trace_sidecar",
    "report_aggregation",
)
MODULE_PATH = (
    "src/trusted_synthesis/experiments/vtdo_experiment/"
    "phase1_v26_budget_adequacy_contract_preflight.py"
)

SOURCE_VERSION = "finance_v26_budget_adequacy_contract_source_replay.v1"
CONTRACT_VERSION = "finance_v26_budget_adequacy_contract.v1"
RAW_EXCHANGE_VERSION = "finance_v26_budget_adequacy_fixture_exchange.v1"
RAW_EXECUTION_VERSION = "finance_v26_budget_adequacy_runner_raw_execution.v1"
RUNNER_CONTROL_VERSION = "finance_v26_budget_adequacy_runner_control.v1"
RUNNER_AUDIT_VERSION = "finance_v26_budget_adequacy_runner_control_audit.v1"
WITNESS_BUDGET_ROW_VERSION = "finance_v26_budgeted_public_witness_row.v1"
WITNESS_BUDGET_AUDIT_VERSION = "finance_v26_budgeted_public_witness_audit.v1"
ROLE_PREFLIGHT_VERSION = "finance_v26_budget_adequacy_role_protocol_preflight.v1"
REPORT_VERSION = "finance_v26_budget_adequacy_contract_preflight_report.v1"


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class DetailFile(FrozenModel):
    relative_path: str = Field(min_length=1)
    sha256: str = Field(min_length=64, max_length=64)
    byte_count: int = Field(ge=1)


class BudgetAdequacyContractSourceEntry(FrozenModel):
    relative_path: str = Field(min_length=1)
    expected_sha256: str = Field(min_length=64, max_length=64)
    observed_sha256: str = Field(min_length=64, max_length=64)
    byte_count: int = Field(ge=1)
    source_kind: Literal[
        "v26_88_replayed_source",
        "v26_88_audit_output",
        "v26_89_implementation",
    ]
    passed: Literal[True] = True

    @model_validator(mode="after")
    def validate_entry(self) -> BudgetAdequacyContractSourceEntry:
        if self.expected_sha256 != self.observed_sha256:
            raise ValueError("Budget Adequacy Contract source bytes changed")
        return self


class BudgetAdequacyContractSourceAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    root_cause_report_id: str = EXPECTED_ROOT_CAUSE_REPORT_ID
    entries: tuple[BudgetAdequacyContractSourceEntry, ...] = Field(min_length=1)
    replayed_file_count: int = Field(ge=1)
    replay_pass_count: int = Field(ge=1)
    source_replay_before_control_execution: Literal[True] = True
    model_client_constructed: Literal[False] = False
    model_api_calls: Literal[0] = 0
    gpu_jobs: Literal[0] = 0
    status: Literal["passed"] = "passed"
    schema_version: str = SOURCE_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> BudgetAdequacyContractSourceAudit:
        paths = tuple(item.relative_path for item in self.entries)
        if paths != tuple(sorted(set(paths))):
            raise ValueError("Budget Adequacy Contract source paths are not canonical")
        if self.replayed_file_count != len(self.entries):
            raise ValueError("Budget Adequacy Contract source denominator changed")
        if self.replay_pass_count != self.replayed_file_count:
            raise ValueError("Budget Adequacy Contract source replay is incomplete")
        if self.audit_id != budget_adequacy_contract_source_audit_id(self):
            raise ValueError("Budget Adequacy Contract source identity is invalid")
        return self


class BudgetAdequacyProtocolContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    root_cause_report_id: str = EXPECTED_ROOT_CAUSE_REPORT_ID
    root_cause_decision_id: str = EXPECTED_ROOT_CAUSE_DECISION_ID
    provider_budget_contract_id: str = EXPECTED_PROVIDER_BUDGET_CONTRACT_ID
    maximum_total_tokens: Literal[120000] = EXPECTED_TOTAL_TOKEN_CEILING
    maximum_prompt_utf8_bytes: Literal[60000] = EXPECTED_PROMPT_BYTE_CEILING
    maximum_output_tokens: Literal[4096] = EXPECTED_COMPLETION_BOUND
    provider_chat_envelope_token_upper_bound: Literal[256] = EXPECTED_CHAT_ENVELOPE
    contract_repair_reserve_tokens: Literal[4096] = EXPECTED_REPAIR_RESERVE
    final_answer_reserve_tokens: Literal[4096] = EXPECTED_FINAL_RESERVE
    static_witness_accounting_rule: Literal[
        "sum_request_upper_bounds_plus_current_required_reserve"
    ] = "sum_request_upper_bounds_plus_current_required_reserve"
    budgeted_public_witness_required_per_task: Literal[True] = True
    capability_minimum_budgeted_paths_per_task: Literal[1] = 1
    reachability_minimum_budgeted_paths_per_task: Literal[3] = 3
    reachability_paths_share_one_budget_contract: Literal[True] = True
    runner_control_stage_order: tuple[str, ...] = RUNNER_STAGE_ORDER
    runner_control_source_kind: Literal["compiler_fixture"] = "compiler_fixture"
    runner_control_empirical_rows_per_task: Literal[0] = 0
    maximum_no_call_rate_numerator: Literal[1] = MAXIMUM_NO_CALL_RATE_NUMERATOR
    maximum_no_call_rate_denominator: Literal[10] = MAXIMUM_NO_CALL_RATE_DENOMINATOR
    no_call_rate_confidence_rule: Literal["one_sided_clopper_pearson_95_upper_bound"] = (
        "one_sided_clopper_pearson_95_upper_bound"
    )
    independent_calibration_admission_rule: Literal["one_sided_95_upper_bound_lte_0.10"] = (
        "one_sided_95_upper_bound_lte_0.10"
    )
    independent_calibration_minimum_job_count: Literal[32] = CALIBRATION_MINIMUM_JOB_COUNT
    threshold_basis: Literal["prospective_operational_design_independent_of_v26_86_outcomes"] = (
        "prospective_operational_design_independent_of_v26_86_outcomes"
    )
    current_outcomes_used_to_select_threshold: Literal[False] = False
    resource_terminals_retained_in_role_denominator: Literal[True] = True
    resource_terminals_excluded_from_validity_and_state_mapping: Literal[True] = True
    capability_and_reachability_denominators_separate: Literal[True] = True
    historical_model_outcome_selection_forbidden: Literal[True] = True
    freshness_channels: tuple[str, ...] = FRESHNESS_CHANNELS
    direct_total_token_ceiling_increase_authorized: Literal[False] = False
    prompt_ceiling_relaxation_authorized: Literal[False] = False
    completion_bound_reduction_authorized: Literal[False] = False
    required_reserve_reduction_authorized: Literal[False] = False
    capability_execution_authorized: Literal[False] = False
    reachability_execution_authorized: Literal[False] = False
    schema_version: str = CONTRACT_VERSION

    @model_validator(mode="after")
    def validate_contract(self) -> BudgetAdequacyProtocolContract:
        if self.runner_control_stage_order != RUNNER_STAGE_ORDER:
            raise ValueError("Budget Adequacy Runner stage order changed")
        if self.freshness_channels != FRESHNESS_CHANNELS:
            raise ValueError("Budget Adequacy freshness channels changed")
        if self.maximum_no_call_rate_numerator >= self.maximum_no_call_rate_denominator:
            raise ValueError("Budget Adequacy no-call threshold is invalid")
        if self.contract_id != budget_adequacy_protocol_contract_id(self):
            raise ValueError("Budget Adequacy Protocol Contract identity is invalid")
        return self


class FixtureProviderExchange(FrozenModel):
    exchange_id: str = Field(min_length=1)
    call_index: int = Field(ge=0)
    prompt: str = Field(min_length=1)
    prompt_sha256: str = Field(min_length=64, max_length=64)
    response_payload: dict[str, Any]
    response_sha256: str = Field(min_length=64, max_length=64)
    telemetry: ModelCallTelemetry
    captured_before_agent_contract_scoring: Literal[True] = True
    schema_version: str = RAW_EXCHANGE_VERSION

    @model_validator(mode="after")
    def validate_exchange(self) -> FixtureProviderExchange:
        if self.prompt_sha256 != _sha256_text(self.prompt):
            raise ValueError("fixture Prompt hash changed")
        response = _canonical_bytes(self.response_payload)
        if self.response_sha256 != hashlib.sha256(response).hexdigest():
            raise ValueError("fixture response hash changed")
        if self.telemetry.request_hash != self.prompt_sha256:
            raise ValueError("fixture telemetry crosses Prompts")
        if self.telemetry.response_hash != self.response_sha256:
            raise ValueError("fixture telemetry crosses responses")
        if self.exchange_id != fixture_provider_exchange_id(self):
            raise ValueError("fixture exchange identity is invalid")
        return self


class RunnerControlRawExecution(FrozenModel):
    raw_execution_id: str = Field(min_length=1)
    control_job_id: str = Field(min_length=1)
    budget_adequacy_contract_id: str = Field(min_length=1)
    task_record_id: str = Field(min_length=1)
    task_package_id: str = Field(min_length=1)
    environment_manifest_id: str = Field(min_length=1)
    compiler_trajectory_id: str = Field(min_length=1)
    fixture_usage_rule: Literal["ceil_prompt_and_response_utf8_bytes_divided_by_8"] = (
        "ceil_prompt_and_response_utf8_bytes_divided_by_8"
    )
    exchanges: tuple[FixtureProviderExchange, ...] = Field(min_length=1)
    provider_budget_audit: ProviderTokenBudgetAudit
    solve_result: IterativeAgentSolveResult
    raw_persisted_before_replay_and_scoring: Literal[True] = True
    fixture_usage_not_budget_adequacy_evidence: Literal[True] = True
    exposed_task_used_as_nonempirical_control_only: Literal[True] = True
    model_client_constructed: Literal[False] = False
    model_api_calls: Literal[0] = 0
    gpu_jobs: Literal[0] = 0
    empirical_denominator_eligible: Literal[False] = False
    schema_version: str = RAW_EXECUTION_VERSION

    @model_validator(mode="after")
    def validate_raw(self) -> RunnerControlRawExecution:
        if tuple(item.call_index for item in self.exchanges) != tuple(range(len(self.exchanges))):
            raise ValueError("Runner control exchanges are not contiguous")
        prompts = tuple(item.prompt for item in self.exchanges)
        if prompts != self.solve_result.audit.model_request_prompts:
            raise ValueError("Runner control Raw Prompts differ from Host Prompts")
        if tuple(item.prompt_sha256 for item in self.exchanges) != (
            self.provider_budget_audit.actual_request_prompt_hashes
        ):
            raise ValueError("Runner control budget audit crosses Raw Prompts")
        if len(self.exchanges) != self.provider_budget_audit.provider_call_count:
            raise ValueError("Runner control Provider denominator changed")
        if self.provider_budget_audit.status != "passed":
            raise ValueError("Runner control Provider budget audit failed")
        if self.provider_budget_audit.no_call_terminal is not None:
            raise ValueError("Runner control unexpectedly reached a no-call terminal")
        if self.solve_result.trajectory.task_id != self.task_package_id:
            raise ValueError("Runner control trajectory crosses tasks")
        if self.raw_execution_id != runner_control_raw_execution_id(self):
            raise ValueError("Runner control Raw Execution identity is invalid")
        return self


class RunnerCompletionControl(FrozenModel):
    control_id: str = Field(min_length=1)
    control_job_id: str = Field(min_length=1)
    task_record_id: str = Field(min_length=1)
    task_package_id: str = Field(min_length=1)
    environment_manifest_id: str = Field(min_length=1)
    mechanism_id: str = Field(min_length=1)
    compiler_trajectory_id: str = Field(min_length=1)
    actual_trajectory_id: str = Field(min_length=1)
    raw_execution: DetailFile
    provider_call_count: int = Field(ge=1)
    synthetic_fixture_token_count: int = Field(ge=1)
    observation_count: int = Field(ge=1)
    replay_result: AuthorityPreservingReplayResult
    verification_report: AuthorityPreservingVerificationReport
    independent_non_replay_checks: dict[str, bool]
    non_replay_agreement: Literal[True] = True
    completed_score: CompletedTrajectoryScore
    calls_and_public_results_match_compiler_witness: Literal[True] = True
    final_answer_matches_compiler_witness: Literal[True] = True
    raw_persisted_before_replay_and_scoring: Literal[True] = True
    shared_scorer_present: Literal[True] = True
    schema_closed_sidecar_present: Literal[True] = True
    aggregation_included: Literal[True] = True
    compiler_fixture_excluded_from_empirical_counts: Literal[True] = True
    empirical_row_contribution: Literal[0] = 0
    status: Literal["passed"] = "passed"
    schema_version: str = RUNNER_CONTROL_VERSION

    @model_validator(mode="after")
    def validate_control(self) -> RunnerCompletionControl:
        if not self.replay_result.passed or not self.verification_report.valid:
            raise ValueError("Runner completion control did not pass Verifier v2")
        expected_non_replay = dict(
            sorted(
                (key, value)
                for key, value in self.verification_report.checks.items()
                if key != "runtime_replay_passed"
            )
        )
        if self.independent_non_replay_checks != expected_non_replay:
            raise ValueError("Runner completion control non-Replay Gates disagree")
        score = self.completed_score
        if (
            score.source_kind != "compiler_fixture"
            or score.trajectory_id != self.actual_trajectory_id
            or score.core_terminal != "valid_trajectory"
            or score.trace_sidecar is None
            or not score.instrument_admitted
            or score.empirical_denominator_eligible
        ):
            raise ValueError("Runner completion control shared score changed")
        if self.control_id != runner_completion_control_id(self):
            raise ValueError("Runner completion control identity is invalid")
        return self


class RunnerCompletionControlAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    budget_adequacy_contract_id: str = Field(min_length=1)
    controls: tuple[RunnerCompletionControl, ...] = Field(
        min_length=EXPECTED_FIXTURE_TASK_COUNT,
        max_length=EXPECTED_FIXTURE_TASK_COUNT,
    )
    expected_control_count: Literal[8] = EXPECTED_FIXTURE_TASK_COUNT
    raw_execution_pass_count: int = Field(ge=0, le=EXPECTED_FIXTURE_TASK_COUNT)
    replay_pass_count: int = Field(ge=0, le=EXPECTED_FIXTURE_TASK_COUNT)
    non_replay_pass_count: int = Field(ge=0, le=EXPECTED_FIXTURE_TASK_COUNT)
    completed_score_pass_count: int = Field(ge=0, le=EXPECTED_FIXTURE_TASK_COUNT)
    sidecar_pass_count: int = Field(ge=0, le=EXPECTED_FIXTURE_TASK_COUNT)
    aggregation_pass_count: int = Field(ge=0, le=EXPECTED_FIXTURE_TASK_COUNT)
    control_job_ids_unique: bool
    historical_empirical_job_overlap_count: Literal[0] = 0
    empirical_row_count: Literal[0] = 0
    model_api_calls: Literal[0] = 0
    gpu_jobs: Literal[0] = 0
    status: Literal["passed"] = "passed"
    schema_version: str = RUNNER_AUDIT_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> RunnerCompletionControlAudit:
        if tuple(item.task_package_id for item in self.controls) != tuple(
            sorted(item.task_package_id for item in self.controls)
        ):
            raise ValueError("Runner completion controls are not canonical")
        counts = (
            self.raw_execution_pass_count,
            self.replay_pass_count,
            self.non_replay_pass_count,
            self.completed_score_pass_count,
            self.sidecar_pass_count,
            self.aggregation_pass_count,
        )
        if any(item != self.expected_control_count for item in counts):
            raise ValueError("Runner completion control chain is incomplete")
        ids = tuple(item.control_job_id for item in self.controls)
        if self.control_job_ids_unique != (len(ids) == len(set(ids))):
            raise ValueError("Runner completion control Job uniqueness changed")
        if self.audit_id != runner_completion_control_audit_id(self):
            raise ValueError("Runner completion control audit identity is invalid")
        return self


class BudgetedPublicWitnessRow(FrozenModel):
    row_id: str = Field(min_length=1)
    task_package_id: str = Field(min_length=1)
    mechanism_id: str = Field(min_length=1)
    compiler_trajectory_id: str = Field(min_length=1)
    runner_control_id: str = Field(min_length=1)
    request_count: int = Field(ge=1)
    prompt_utf8_bytes: tuple[int, ...] = Field(min_length=1)
    request_token_upper_bounds: tuple[int, ...] = Field(min_length=1)
    required_reserve_tokens: tuple[int, ...] = Field(min_length=1)
    cumulative_path_upper_bounds: tuple[int, ...] = Field(min_length=1)
    maximum_prompt_utf8_bytes: int = Field(ge=1)
    maximum_cumulative_path_upper_bound: int = Field(ge=1)
    frozen_total_token_ceiling: Literal[120000] = EXPECTED_TOTAL_TOKEN_CEILING
    frozen_prompt_byte_ceiling: Literal[60000] = EXPECTED_PROMPT_BYTE_CEILING
    headroom_or_deficit: int
    prompt_ceiling_passed: bool
    full_witness_budget_qualified: bool
    diagnostic_minimum_ceiling_for_this_fixture_path: int = Field(ge=1)
    fixture_usage_excluded_from_static_accounting: Literal[True] = True
    direct_ceiling_increase_authorized: Literal[False] = False
    empirical_evidence: Literal[False] = False
    schema_version: str = WITNESS_BUDGET_ROW_VERSION

    @model_validator(mode="after")
    def validate_row(self) -> BudgetedPublicWitnessRow:
        lengths = {
            self.request_count,
            len(self.prompt_utf8_bytes),
            len(self.request_token_upper_bounds),
            len(self.required_reserve_tokens),
            len(self.cumulative_path_upper_bounds),
        }
        if len(lengths) != 1:
            raise ValueError("Budgeted Public Witness request denominator changed")
        expected: list[int] = []
        cumulative = 0
        for request, reserve in zip(
            self.request_token_upper_bounds,
            self.required_reserve_tokens,
            strict=True,
        ):
            cumulative += request
            expected.append(cumulative + reserve)
        if self.cumulative_path_upper_bounds != tuple(expected):
            raise ValueError("Budgeted Public Witness path arithmetic changed")
        if self.maximum_prompt_utf8_bytes != max(self.prompt_utf8_bytes):
            raise ValueError("Budgeted Public Witness maximum Prompt changed")
        if self.maximum_cumulative_path_upper_bound != max(expected):
            raise ValueError("Budgeted Public Witness maximum path bound changed")
        if self.headroom_or_deficit != (
            self.frozen_total_token_ceiling - self.maximum_cumulative_path_upper_bound
        ):
            raise ValueError("Budgeted Public Witness headroom changed")
        if self.prompt_ceiling_passed != (
            self.maximum_prompt_utf8_bytes <= self.frozen_prompt_byte_ceiling
        ):
            raise ValueError("Budgeted Public Witness Prompt Gate changed")
        if self.full_witness_budget_qualified != (
            self.prompt_ceiling_passed and self.headroom_or_deficit >= 0
        ):
            raise ValueError("Budgeted Public Witness qualification changed")
        if self.diagnostic_minimum_ceiling_for_this_fixture_path != (
            self.maximum_cumulative_path_upper_bound
        ):
            raise ValueError("Budgeted Public Witness diagnostic ceiling changed")
        if self.row_id != budgeted_public_witness_row_id(self):
            raise ValueError("Budgeted Public Witness row identity is invalid")
        return self


class BudgetedPublicWitnessAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    budget_adequacy_contract_id: str = Field(min_length=1)
    rows: tuple[BudgetedPublicWitnessRow, ...] = Field(
        min_length=EXPECTED_FIXTURE_TASK_COUNT,
        max_length=EXPECTED_FIXTURE_TASK_COUNT,
    )
    observed_fixture_task_count: Literal[8] = EXPECTED_FIXTURE_TASK_COUNT
    qualified_fixture_task_count: int = Field(ge=0, le=EXPECTED_FIXTURE_TASK_COUNT)
    prompt_ceiling_pass_count: int = Field(ge=0, le=EXPECTED_FIXTURE_TASK_COUNT)
    minimum_static_path_upper_bound: int = Field(ge=1)
    maximum_static_path_upper_bound: int = Field(ge=1)
    inherited_120k_budget_adequate_for_fixture_tasks: bool
    current_fixture_tasks_future_selection_eligible: Literal[False] = False
    direct_budget_increase_authorized: Literal[False] = False
    model_api_calls: Literal[0] = 0
    gpu_jobs: Literal[0] = 0
    status: Literal["passed"] = "passed"
    schema_version: str = WITNESS_BUDGET_AUDIT_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> BudgetedPublicWitnessAudit:
        if tuple(item.task_package_id for item in self.rows) != tuple(
            sorted(item.task_package_id for item in self.rows)
        ):
            raise ValueError("Budgeted Public Witness rows are not canonical")
        qualified = sum(item.full_witness_budget_qualified for item in self.rows)
        if self.qualified_fixture_task_count != qualified:
            raise ValueError("Budgeted Public Witness qualified count changed")
        prompt_passes = sum(item.prompt_ceiling_passed for item in self.rows)
        if self.prompt_ceiling_pass_count != prompt_passes:
            raise ValueError("Budgeted Public Witness Prompt count changed")
        bounds = tuple(item.maximum_cumulative_path_upper_bound for item in self.rows)
        if self.minimum_static_path_upper_bound != min(
            bounds
        ) or self.maximum_static_path_upper_bound != max(bounds):
            raise ValueError("Budgeted Public Witness bound range changed")
        if self.inherited_120k_budget_adequate_for_fixture_tasks != (
            qualified == self.observed_fixture_task_count
        ):
            raise ValueError("Budgeted Public Witness aggregate decision changed")
        if self.audit_id != budgeted_public_witness_audit_id(self):
            raise ValueError("Budgeted Public Witness audit identity is invalid")
        return self


class BudgetAdequacyRoleProtocolPreflight(FrozenModel):
    preflight_id: str = Field(min_length=1)
    budget_adequacy_contract_id: str = Field(min_length=1)
    runner_control_audit_id: str = Field(min_length=1)
    budgeted_public_witness_audit_id: str = Field(min_length=1)
    capability_task_count: Literal[12] = CAPABILITY_TASK_COUNT
    capability_replicas_per_task: Literal[8] = CAPABILITY_REPLICAS_PER_TASK
    capability_job_count: Literal[96] = CAPABILITY_JOB_COUNT
    reachability_task_count: Literal[12] = REACHABILITY_TASK_COUNT
    reachability_paths_per_task: Literal[3] = REACHABILITY_PATHS_PER_TASK
    reachability_state_count: Literal[36] = REACHABILITY_STATE_COUNT
    reachability_natural_job_count: Literal[144] = REACHABILITY_NATURAL_JOB_COUNT
    reachability_conditioned_job_count: Literal[216] = REACHABILITY_CONDITIONED_JOB_COUNT
    reachability_job_count: Literal[360] = REACHABILITY_JOB_COUNT
    capability_and_reachability_denominators_separate: Literal[True] = True
    fresh_capability_task_count: Literal[0] = 0
    fresh_reachability_task_count: Literal[0] = 0
    fresh_budgeted_capability_witness_count: Literal[0] = 0
    fresh_budgeted_reachability_path_count: Literal[0] = 0
    exposed_fixture_authority_path_count: Literal[0] = 0
    independent_budget_calibration_job_count: Literal[0] = 0
    independent_no_call_rate_evaluated: Literal[False] = False
    capability_contract_materialized: Literal[False] = False
    capability_manifest_materialized: Literal[False] = False
    reachability_contract_materialized: Literal[False] = False
    reachability_manifest_materialized: Literal[False] = False
    only_independently_valid_model_generated_trajectories_enter_state_mapping: Literal[True] = True
    compiler_fixture_empirical_row_count: Literal[0] = 0
    historical_outcome_used_for_selection: Literal[False] = False
    protocol_preflight_passed: Literal[False] = False
    blocking_reasons: tuple[str, ...] = (
        "fresh_budgeted_capability_tasks_not_materialized",
        "fresh_three_path_reachability_tasks_not_materialized",
        "independent_no_call_calibration_not_executed",
        "inherited_120k_static_witness_adequacy_not_established",
    )
    capability_execution_authorized: Literal[False] = False
    reachability_execution_authorized: Literal[False] = False
    next_permitted_stage: Literal["fresh_budget_feasible_role_task_rematerialization_only"] = (
        "fresh_budget_feasible_role_task_rematerialization_only"
    )
    schema_version: str = ROLE_PREFLIGHT_VERSION

    @model_validator(mode="after")
    def validate_preflight(self) -> BudgetAdequacyRoleProtocolPreflight:
        if self.capability_job_count != (
            self.capability_task_count * self.capability_replicas_per_task
        ):
            raise ValueError("Capability protocol denominator changed")
        if self.reachability_state_count != (
            self.reachability_task_count * self.reachability_paths_per_task
        ):
            raise ValueError("Reachability State denominator changed")
        if self.reachability_job_count != (
            self.reachability_natural_job_count + self.reachability_conditioned_job_count
        ):
            raise ValueError("Reachability Job denominator changed")
        if self.blocking_reasons != tuple(sorted(set(self.blocking_reasons))):
            raise ValueError("Budget Adequacy role blockers are not canonical")
        if self.preflight_id != budget_adequacy_role_preflight_id(self):
            raise ValueError("Budget Adequacy role preflight identity is invalid")
        return self


class BudgetAdequacyContractPreflightReport(FrozenModel):
    report_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    source_replay_audit_id: str = Field(min_length=1)
    budget_adequacy_contract_id: str = Field(min_length=1)
    runner_control_audit_id: str = Field(min_length=1)
    budgeted_public_witness_audit_id: str = Field(min_length=1)
    role_protocol_preflight_id: str = Field(min_length=1)
    immutable_detail_files: tuple[DetailFile, ...] = Field(min_length=5, max_length=5)
    immutable_raw_control_files: tuple[DetailFile, ...] = Field(
        min_length=EXPECTED_FIXTURE_TASK_COUNT,
        max_length=EXPECTED_FIXTURE_TASK_COUNT,
    )
    runner_control_passed: Literal[True] = True
    inherited_120k_budget_adequacy_established: Literal[False] = False
    role_protocol_preflight_passed: Literal[False] = False
    capability_execution_authorized: Literal[False] = False
    reachability_execution_authorized: Literal[False] = False
    fresh_confirmation_authorized: Literal[False] = False
    no_c_vtdo_authorized: Literal[False] = False
    student_training_authorized: Literal[False] = False
    exact_target_authorized: Literal[False] = False
    gp_c_authorized: Literal[False] = False
    model_client_constructed: Literal[False] = False
    model_api_calls: Literal[0] = 0
    gpu_jobs: Literal[0] = 0
    status: Literal["passed"] = "passed"
    next_permitted_stage: Literal["fresh_budget_feasible_role_task_rematerialization_only"] = (
        "fresh_budget_feasible_role_task_rematerialization_only"
    )
    production_contribution: Literal[0] = 0
    schema_version: str = REPORT_VERSION

    @model_validator(mode="after")
    def validate_report(self) -> BudgetAdequacyContractPreflightReport:
        detail_names = tuple(item.relative_path for item in self.immutable_detail_files)
        raw_names = tuple(item.relative_path for item in self.immutable_raw_control_files)
        if detail_names != tuple(sorted(set(detail_names))):
            raise ValueError("Budget Adequacy detail files are not canonical")
        if raw_names != tuple(sorted(set(raw_names))):
            raise ValueError("Budget Adequacy Raw control files are not canonical")
        if self.report_id != budget_adequacy_contract_preflight_report_id(self):
            raise ValueError("Budget Adequacy Contract preflight report identity is invalid")
        return self


T = TypeVar("T", bound=BaseModel)


def _canonical_bytes(payload: Any) -> bytes:
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


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
            raise ValueError(f"immutable Budget Adequacy JSON changed: {path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(serialized, encoding="utf-8")
    temporary.replace(path)


def _write_raw(path: Path, payload: Any) -> None:
    serialized = _canonical_bytes(payload)
    if path.exists():
        if path.read_bytes() != serialized:
            raise ValueError(f"immutable Runner control Raw Execution changed: {path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(serialized)
    temporary.replace(path)


def _load_rows(path: Path, model: type[T]) -> tuple[T, ...]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError(f"expected a JSON list: {path}")
    return tuple(model.model_validate(item) for item in payload)


def _relative_to_package(path: Path, package_root: Path) -> str:
    try:
        return str(path.resolve().relative_to(package_root.resolve()))
    except ValueError as exc:
        raise ValueError(f"Budget Adequacy source escapes package root: {path}") from exc


def _build_source_replay(
    *,
    root_cause_dir: Path,
    root_cause_report: BudgetAdequacyRootCauseReport,
    package_root: Path,
) -> BudgetAdequacyContractSourceAudit:
    inherited = BudgetAdequacySourceReplayAudit.model_validate_json(
        (root_cause_dir / "source_replay_audit.json").read_text(encoding="utf-8")
    )
    expected: dict[str, tuple[str, str]] = {}

    def register(relative: str, sha256: str, kind: str) -> None:
        prior = expected.get(relative)
        if prior is not None and prior[0] != sha256:
            raise ValueError(f"Budget Adequacy source manifests disagree: {relative}")
        expected[relative] = prior or (sha256, kind)

    for item in inherited.entries:
        register(item.relative_path, item.expected_sha256, "v26_88_replayed_source")
    for detail in root_cause_report.immutable_detail_files:
        path = root_cause_dir / detail.relative_path
        if _sha256(path) != detail.sha256 or path.stat().st_size != detail.byte_count:
            raise ValueError(f"changed v26.88 detail: {path}")
        register(
            _relative_to_package(path, package_root),
            detail.sha256,
            "v26_88_audit_output",
        )
    report_path = root_cause_dir / "report.json"
    register(
        _relative_to_package(report_path, package_root),
        _sha256(report_path),
        "v26_88_audit_output",
    )
    register(
        MODULE_PATH,
        _sha256(package_root / MODULE_PATH),
        "v26_89_implementation",
    )
    entries = tuple(
        BudgetAdequacyContractSourceEntry(
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
    provisional = BudgetAdequacyContractSourceAudit.model_construct(audit_id="pending", **values)
    return BudgetAdequacyContractSourceAudit(
        audit_id=budget_adequacy_contract_source_audit_id(provisional),
        **values,
    )


def _runtime(
    record: OperationalTaskRecord,
    environment: AgentToolEnvironmentManifest,
) -> FinanceExecutableSupportRuntime:
    recovery = (
        FinanceTypedRecoveryScenario.model_validate(record.recovery_scenario)
        if record.recovery_scenario is not None
        else None
    )
    return FinanceExecutableSupportRuntime(
        record.public_corpus,
        environment,
        recovery_scenario=recovery,
    )


class _CompilerFixtureClient:
    def __init__(self, config: AgentModelConfig, trajectory: Trajectory) -> None:
        self.config = config
        self._trajectory = trajectory
        self._tool_steps = tuple(item for item in trajectory.steps if item.tool_name is not None)
        self._response_index = 0
        self.exchanges: list[FixtureProviderExchange] = []

    def complete_json(self, prompt: str) -> tuple[dict[str, Any], ModelCallTelemetry]:
        if self._response_index == 0:
            payload: dict[str, Any] = {
                "plan_summary": "Execute the registered public Compiler Witness.",
                "subgoal_labels": ["execute", "verify"],
                "stop_conditions": ["Return the verified projected answer."],
            }
        elif self._response_index <= len(self._tool_steps):
            step = self._tool_steps[self._response_index - 1]
            payload = {
                "decision_type": "tool_call",
                "rationale_summary": "Execute the next public Compiler Witness action.",
                "tool_id": step.tool_name,
                "arguments": step.tool_input,
                "answer": None,
                "cited_evidence_ids": [],
            }
        else:
            answer = cast(Mapping[str, Any], self._trajectory.final_answer)
            citations = cast(Sequence[Mapping[str, Any]], answer["citations"])
            final_fields = {
                "rationale_summary": "Return the verified Compiler Witness answer.",
                "answer": answer["result"],
                "cited_evidence_ids": [str(item["evidence_id"]) for item in citations],
            }
            if prompt.startswith(
                "Return only one JSON object with exactly rationale_summary, answer"
            ):
                payload = final_fields
            else:
                payload = {
                    "decision_type": "final_answer",
                    "tool_id": None,
                    "arguments": None,
                    **final_fields,
                }
        response_bytes = _canonical_bytes(payload)
        prompt_bytes = len(prompt.encode("utf-8"))
        prompt_tokens = max(1, (prompt_bytes + 7) // 8)
        completion_tokens = max(1, (len(response_bytes) + 7) // 8)
        telemetry = ModelCallTelemetry(
            provider=self.config.provider,
            endpoint_host="credential-free.local",
            model_requested=self.config.model,
            model_selected=self.config.model,
            response_model=self.config.model,
            request_hash=_sha256_text(prompt),
            response_hash=hashlib.sha256(response_bytes).hexdigest(),
            http_status=200,
            http_success=True,
            json_contract_success=True,
            finish_reason="stop",
            response_content_length=len(response_bytes),
            prompt_tokens=prompt_tokens,
            prompt_cache_hit_tokens=0,
            prompt_cache_miss_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
            estimated_cost=0.0,
            cost_estimation_method="generic_input_rate",
        )
        values = {
            "call_index": self._response_index,
            "prompt": prompt,
            "prompt_sha256": _sha256_text(prompt),
            "response_payload": payload,
            "response_sha256": hashlib.sha256(response_bytes).hexdigest(),
            "telemetry": telemetry,
        }
        provisional = FixtureProviderExchange.model_construct(exchange_id="pending", **values)
        self.exchanges.append(
            FixtureProviderExchange(
                exchange_id=fixture_provider_exchange_id(provisional),
                **values,
            )
        )
        self._response_index += 1
        return payload, telemetry


def _replace_runtime_references(value: Any, mapping: Mapping[str, str]) -> Any:
    if isinstance(value, str):
        return mapping.get(value, value)
    if isinstance(value, Mapping):
        return {key: _replace_runtime_references(item, mapping) for key, item in value.items()}
    if isinstance(value, list):
        return [_replace_runtime_references(item, mapping) for item in value]
    return value


def _answer_and_citations(
    result: IterativeAgentSolveResult,
) -> tuple[dict[str, Any], tuple[str, ...]]:
    final = result.trajectory.final_answer
    answer = cast(Mapping[str, Any], final["result"])
    citations = cast(Sequence[Mapping[str, Any]], final["citations"])
    return (
        dict(answer),
        tuple(str(item["evidence_id"]) for item in citations),
    )


def _independent_non_replay_checks(
    *,
    record: OperationalTaskRecord,
    result: IterativeAgentSolveResult,
    replay: AuthorityPreservingReplayResult,
) -> dict[str, bool]:
    observations = result.observations
    audit = result.audit
    prompt_hashes = tuple(_sha256_text(item) for item in audit.model_request_prompts)
    prompt_attestations = tuple(
        canonical_hash(
            {
                "prompt_hash": prompt_hash,
                "scanner_manifest_hash": audit.noninterference_scanner_manifest_hash,
                "recursive_noninterference_passed": True,
            },
            prefix="agent_prompt_noninterference_attestation:",
        )
        for prompt_hash in prompt_hashes
    )
    model_input_noninterference_passed = (
        prompt_hashes == audit.model_request_prompt_hashes
        and prompt_attestations == audit.model_request_prompt_noninterference_attestation_hashes
    )
    program_complete, _, runtime_to_node, operation_lineage = match_empirical_program(
        record,
        observations,
    )
    answer, citations = _answer_and_citations(result)
    normalized_answer = dict(
        cast(
            Mapping[str, Any],
            _replace_runtime_references(answer, runtime_to_node),
        )
    )
    for field in ("higher_ref", "selected_ref"):
        reference = normalized_answer.get(field)
        if reference is not None and str(reference) in record.answer_projection:
            normalized_answer[field] = record.answer_projection[str(reference)]
    lattice = record.task_package.evidence_support_lattice
    selected_support = matching_sufficient_support_set(
        lattice,
        replay.selected_evidence_ids,
    )
    citation_support = matching_sufficient_support_set(lattice, citations)
    verification_support = {
        str(evidence_id)
        for item in observations
        if item.call.tool_id == "cross_check_evidence"
        and item.status == "succeeded"
        and item.result.get("verified") is True
        for evidence_id in item.result.get("support") or ()
    }
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
    mechanism = evaluate_mechanism_estimand(
        record,
        observations,
        stopped_by_model=result.audit.stopped_by_model,
    )
    necessary = set(lattice.necessary_evidence_ids)
    return dict(
        sorted(
            {
                "model_input_noninterference_passed": (model_input_noninterference_passed),
                "only_allowed_tools": {item.call.tool_id for item in observations}
                <= set(record.task_package.tool_closure.allowed_tool_ids),
                "operation_lineage_complete": (
                    program_complete and necessary <= set(operation_lineage)
                ),
                "evidence_support_complete": selected_support is not None,
                "verification_complete": necessary <= verification_support,
                "answer_projection_complete": (
                    normalized_answer == record.projected_expected_output
                ),
                "citation_complete": citation_support is not None,
                "mechanism_complete": mechanism.success,
                "no_postcompletion_violation": (
                    first_verified is None or first_verified == len(observations) - 1
                ),
            }.items()
        )
    )


def _calls_and_results_match(
    result: IterativeAgentSolveResult,
    compiler_trajectory: Trajectory,
) -> bool:
    expected = tuple(
        AgentToolObservation.model_validate(item.observation)
        for item in compiler_trajectory.steps
        if item.tool_name is not None
    )
    actual = result.observations
    return len(actual) == len(expected) and all(
        observed.call == frozen.call
        and observed.status == frozen.status
        and observed.result == frozen.result
        and observed.evidence_ids == frozen.evidence_ids
        and observed.provenance_hashes == frozen.provenance_hashes
        for observed, frozen in zip(actual, expected, strict=True)
    )


def _raw_control_path(
    output_dir: Path,
    index: int,
    control_job_id: str,
) -> Path:
    suffix = control_job_id.split(":", 1)[-1][:16]
    return output_dir / "runner_control_raw" / f"{index:02d}_{suffix}.json"


def _control_job_id(
    contract_id: str,
    record: OperationalTaskRecord,
    compiler_trajectory: Trajectory,
) -> str:
    return canonical_hash(
        {
            "budget_adequacy_contract_id": contract_id,
            "task_record_id": record.record_id,
            "task_package_id": record.task_package.package_id,
            "environment_manifest_id": record.environment_manifest_id,
            "compiler_trajectory_id": compiler_trajectory.trajectory_id,
            "source_kind": "compiler_fixture",
        },
        prefix="finance_v26_budget_adequacy_runner_control_job:",
    )


def _run_control(
    *,
    index: int,
    contract: BudgetAdequacyProtocolContract,
    provider_budget_contract: ProviderTokenBudgetContract,
    model_config: AgentModelConfig,
    replay_contract: AuthorityPreservingReplayContract,
    record: OperationalTaskRecord,
    environment: AgentToolEnvironmentManifest,
    compiler_trajectory: Trajectory,
    historical_job_ids: set[str],
    output_dir: Path,
) -> tuple[RunnerCompletionControl, BudgetedPublicWitnessRow]:
    control_job_id = _control_job_id(contract.contract_id, record, compiler_trajectory)
    if control_job_id in historical_job_ids:
        raise ValueError("Runner control reused a historical empirical Job identity")
    fixture = _CompilerFixtureClient(model_config, compiler_trajectory)
    budget_client = BudgetClosedJsonClient(fixture, provider_budget_contract)
    result = IterativeAgentSolver(
        budget_client,
        mode="autonomous_agent",
        maximum_total_tokens=provider_budget_contract.maximum_total_tokens,
        protocol_profile=IterativeAgentProtocolProfile(),
    ).solve_with_audit(
        record.task_package.task.public,
        _runtime(record, environment),
    )
    budget_audit = budget_client.audit()
    raw_values = {
        "control_job_id": control_job_id,
        "budget_adequacy_contract_id": contract.contract_id,
        "task_record_id": record.record_id,
        "task_package_id": record.task_package.package_id,
        "environment_manifest_id": environment.manifest_id,
        "compiler_trajectory_id": compiler_trajectory.trajectory_id,
        "exchanges": tuple(fixture.exchanges),
        "provider_budget_audit": budget_audit,
        "solve_result": result,
    }
    provisional_raw = RunnerControlRawExecution.model_construct(
        raw_execution_id="pending",
        **raw_values,
    )
    raw = RunnerControlRawExecution(
        raw_execution_id=runner_control_raw_execution_id(provisional_raw),
        **raw_values,
    )
    raw_path = _raw_control_path(output_dir, index, control_job_id)
    _write_raw(raw_path, raw.model_dump(mode="json"))
    persisted = RunnerControlRawExecution.model_validate(json.loads(raw_path.read_bytes()))
    replay = replay_authority_preserving_observations(
        replay_contract,
        record,
        environment,
        persisted.solve_result.observations,
    )
    verification = verify_authority_preserving_agent_result(
        replay_contract,
        record,
        environment,
        persisted.solve_result,
    )
    checks = _independent_non_replay_checks(
        record=record,
        result=persisted.solve_result,
        replay=replay,
    )
    score = score_completed_trajectory(
        trajectory=persisted.solve_result.trajectory,
        source_kind="compiler_fixture",
        replay_result_id=replay.replay_id,
        replay_passed=replay.passed,
        non_replay_checks=checks,
        independent_valid=verification.valid,
        resource_budget_audit_id=persisted.provider_budget_audit.audit_id,
        resource_budget_status="passed",
    )
    raw_descriptor = DetailFile(
        relative_path=str(raw_path.relative_to(output_dir)),
        sha256=_sha256(raw_path),
        byte_count=raw_path.stat().st_size,
    )
    control_values = {
        "control_job_id": control_job_id,
        "task_record_id": record.record_id,
        "task_package_id": record.task_package.package_id,
        "environment_manifest_id": environment.manifest_id,
        "mechanism_id": record.mechanism_id,
        "compiler_trajectory_id": compiler_trajectory.trajectory_id,
        "actual_trajectory_id": persisted.solve_result.trajectory.trajectory_id,
        "raw_execution": raw_descriptor,
        "provider_call_count": len(persisted.exchanges),
        "synthetic_fixture_token_count": (
            persisted.provider_budget_audit.cumulative_provider_tokens
        ),
        "observation_count": len(persisted.solve_result.observations),
        "replay_result": replay,
        "verification_report": verification,
        "independent_non_replay_checks": checks,
        "non_replay_agreement": checks
        == dict(
            sorted(
                (key, value)
                for key, value in verification.checks.items()
                if key != "runtime_replay_passed"
            )
        ),
        "completed_score": score,
        "calls_and_public_results_match_compiler_witness": (
            _calls_and_results_match(persisted.solve_result, compiler_trajectory)
        ),
        "final_answer_matches_compiler_witness": (
            persisted.solve_result.trajectory.final_answer == compiler_trajectory.final_answer
        ),
    }
    provisional_control = RunnerCompletionControl.model_construct(
        control_id="pending",
        **control_values,
    )
    control = RunnerCompletionControl(
        control_id=runner_completion_control_id(provisional_control),
        **control_values,
    )
    certificates = persisted.provider_budget_audit.certificates
    requests = tuple(item.request_token_upper_bound for item in certificates)
    reserves = tuple(item.required_reserve_tokens for item in certificates)
    cumulative = 0
    path_bounds: list[int] = []
    for request, reserve in zip(requests, reserves, strict=True):
        cumulative += request
        path_bounds.append(cumulative + reserve)
    maximum_path = max(path_bounds)
    witness_values = {
        "task_package_id": record.task_package.package_id,
        "mechanism_id": record.mechanism_id,
        "compiler_trajectory_id": compiler_trajectory.trajectory_id,
        "runner_control_id": control.control_id,
        "request_count": len(certificates),
        "prompt_utf8_bytes": tuple(item.prompt_utf8_bytes for item in certificates),
        "request_token_upper_bounds": requests,
        "required_reserve_tokens": reserves,
        "cumulative_path_upper_bounds": tuple(path_bounds),
        "maximum_prompt_utf8_bytes": max(item.prompt_utf8_bytes for item in certificates),
        "maximum_cumulative_path_upper_bound": maximum_path,
        "headroom_or_deficit": EXPECTED_TOTAL_TOKEN_CEILING - maximum_path,
        "prompt_ceiling_passed": all(
            item.prompt_utf8_bytes <= EXPECTED_PROMPT_BYTE_CEILING for item in certificates
        ),
        "full_witness_budget_qualified": (
            maximum_path <= EXPECTED_TOTAL_TOKEN_CEILING
            and all(item.prompt_utf8_bytes <= EXPECTED_PROMPT_BYTE_CEILING for item in certificates)
        ),
        "diagnostic_minimum_ceiling_for_this_fixture_path": maximum_path,
    }
    provisional_witness = BudgetedPublicWitnessRow.model_construct(
        row_id="pending",
        **witness_values,
    )
    witness = BudgetedPublicWitnessRow(
        row_id=budgeted_public_witness_row_id(provisional_witness),
        **witness_values,
    )
    return control, witness


def _build_runner_audit(
    *,
    contract: BudgetAdequacyProtocolContract,
    controls: Sequence[RunnerCompletionControl],
    historical_job_ids: set[str],
) -> RunnerCompletionControlAudit:
    rows = tuple(sorted(controls, key=lambda item: item.task_package_id))
    control_ids = {item.control_job_id for item in rows}
    values = {
        "budget_adequacy_contract_id": contract.contract_id,
        "controls": rows,
        "raw_execution_pass_count": sum(
            item.raw_persisted_before_replay_and_scoring for item in rows
        ),
        "replay_pass_count": sum(item.replay_result.passed for item in rows),
        "non_replay_pass_count": sum(
            item.non_replay_agreement and all(item.independent_non_replay_checks.values())
            for item in rows
        ),
        "completed_score_pass_count": sum(
            item.completed_score.core_terminal == "valid_trajectory" for item in rows
        ),
        "sidecar_pass_count": sum(item.completed_score.trace_sidecar is not None for item in rows),
        "aggregation_pass_count": sum(item.aggregation_included for item in rows),
        "control_job_ids_unique": len(control_ids) == len(rows),
        "historical_empirical_job_overlap_count": len(control_ids & historical_job_ids),
    }
    provisional = RunnerCompletionControlAudit.model_construct(
        audit_id="pending",
        **values,
    )
    return RunnerCompletionControlAudit(
        audit_id=runner_completion_control_audit_id(provisional),
        **values,
    )


def _build_witness_audit(
    *,
    contract: BudgetAdequacyProtocolContract,
    rows: Sequence[BudgetedPublicWitnessRow],
) -> BudgetedPublicWitnessAudit:
    ordered = tuple(sorted(rows, key=lambda item: item.task_package_id))
    bounds = tuple(item.maximum_cumulative_path_upper_bound for item in ordered)
    qualified = sum(item.full_witness_budget_qualified for item in ordered)
    values = {
        "budget_adequacy_contract_id": contract.contract_id,
        "rows": ordered,
        "qualified_fixture_task_count": qualified,
        "prompt_ceiling_pass_count": sum(item.prompt_ceiling_passed for item in ordered),
        "minimum_static_path_upper_bound": min(bounds),
        "maximum_static_path_upper_bound": max(bounds),
        "inherited_120k_budget_adequate_for_fixture_tasks": (
            qualified == EXPECTED_FIXTURE_TASK_COUNT
        ),
    }
    provisional = BudgetedPublicWitnessAudit.model_construct(
        audit_id="pending",
        **values,
    )
    return BudgetedPublicWitnessAudit(
        audit_id=budgeted_public_witness_audit_id(provisional),
        **values,
    )


def build_budget_adequacy_contract_preflight(
    *,
    run_id: str,
    root_cause_dir: Path,
    task_source_dir: Path,
    instrument_preflight_dir: Path,
    verifier_qualification_dir: Path,
    output_dir: Path,
    package_root: Path,
) -> BudgetAdequacyContractPreflightReport:
    root_cause_report = BudgetAdequacyRootCauseReport.model_validate_json(
        (root_cause_dir / "report.json").read_text(encoding="utf-8")
    )
    root_cause = BudgetAdequacyRootCauseSummary.model_validate_json(
        (root_cause_dir / "job_budget_diagnostics.json").read_text(encoding="utf-8")
    )
    root_decision = BudgetAdequacyDecision.model_validate_json(
        (root_cause_dir / "budget_adequacy_decision.json").read_text(encoding="utf-8")
    )
    task_report = BudgetClosedInstrumentPopulationReport.model_validate_json(
        (task_source_dir / "report.json").read_text(encoding="utf-8")
    )
    instrument_preflight = BudgetClosedInstrumentPreflightReport.model_validate_json(
        (instrument_preflight_dir / "report.json").read_text(encoding="utf-8")
    )
    verifier_report = AuthorityPreservingVerifierQualificationReport.model_validate_json(
        (verifier_qualification_dir / "report.json").read_text(encoding="utf-8")
    )
    if (
        root_cause_report.report_id != EXPECTED_ROOT_CAUSE_REPORT_ID
        or root_decision.decision_id != EXPECTED_ROOT_CAUSE_DECISION_ID
        or root_cause.audit_id != root_cause_report.root_cause_audit_id
        or root_decision.decision_id != root_cause_report.decision_id
    ):
        raise ValueError("Budget Adequacy Contract received another root-cause result")
    if (
        task_report.report_id != EXPECTED_TASK_SOURCE_REPORT_ID
        or instrument_preflight.report_id != EXPECTED_INSTRUMENT_PREFLIGHT_REPORT_ID
        or verifier_report.report_id != EXPECTED_VERIFIER_QUALIFICATION_REPORT_ID
    ):
        raise ValueError("Budget Adequacy Contract received another Instrument source")
    source = _build_source_replay(
        root_cause_dir=root_cause_dir,
        root_cause_report=root_cause_report,
        package_root=package_root,
    )
    provider_budget_contract = ProviderTokenBudgetContract.model_validate_json(
        (task_source_dir / "provider_token_budget_contract.json").read_text(encoding="utf-8")
    )
    old_contract = BudgetClosedInstrumentContract.model_validate_json(
        (instrument_preflight_dir / "execution_contract.json").read_text(encoding="utf-8")
    )
    replay_contract = AuthorityPreservingReplayContract.model_validate_json(
        (verifier_qualification_dir / "replay_contract.json").read_text(encoding="utf-8")
    )
    if (
        provider_budget_contract.contract_id != EXPECTED_PROVIDER_BUDGET_CONTRACT_ID
        or old_contract.provider_token_budget_contract != provider_budget_contract
    ):
        raise ValueError("Budget Adequacy Contract received another Provider budget")
    contract_values: dict[str, Any] = {}
    provisional_contract = BudgetAdequacyProtocolContract.model_construct(
        contract_id="pending",
        **contract_values,
    )
    contract = BudgetAdequacyProtocolContract(
        contract_id=budget_adequacy_protocol_contract_id(provisional_contract),
        **contract_values,
    )
    records = _load_rows(
        task_source_dir / "operational_task_records.json",
        OperationalTaskRecord,
    )
    environments = _load_rows(
        task_source_dir / "tool_environment_manifests.json",
        AgentToolEnvironmentManifest,
    )
    trajectories = _load_rows(
        task_source_dir / "compiler_trajectories.json",
        Trajectory,
    )
    path_catalogs = _load_rows(
        task_source_dir / "static_model_authority_path_catalogs.json",
        StaticModelAuthorityPathCatalog,
    )
    if not (
        len(records)
        == len(environments)
        == len(trajectories)
        == len(path_catalogs)
        == EXPECTED_FIXTURE_TASK_COUNT
    ):
        raise ValueError("Budget Adequacy Runner control denominator changed")
    exposed_fixture_authority_path_count = sum(len(item.paths) for item in path_catalogs)
    if exposed_fixture_authority_path_count:
        raise ValueError("Instrument-only fixture tasks gained Reachability paths")
    records_by_task = {item.task_package.package_id: item for item in records}
    environments_by_id = {item.manifest_id: item for item in environments}
    historical_job_ids = {item.job_id for item in root_cause.rows}
    model_config = AgentModelConfig.model_validate(old_contract.model_invocation_config)
    controls: list[RunnerCompletionControl] = []
    witness_rows: list[BudgetedPublicWitnessRow] = []
    output_dir.mkdir(parents=True, exist_ok=True)
    for index, trajectory in enumerate(sorted(trajectories, key=lambda item: item.task_id)):
        record = records_by_task[trajectory.task_id]
        environment = environments_by_id[record.environment_manifest_id]
        control, witness = _run_control(
            index=index,
            contract=contract,
            provider_budget_contract=provider_budget_contract,
            model_config=model_config,
            replay_contract=replay_contract,
            record=record,
            environment=environment,
            compiler_trajectory=trajectory,
            historical_job_ids=historical_job_ids,
            output_dir=output_dir,
        )
        controls.append(control)
        witness_rows.append(witness)
    runner_audit = _build_runner_audit(
        contract=contract,
        controls=controls,
        historical_job_ids=historical_job_ids,
    )
    witness_audit = _build_witness_audit(
        contract=contract,
        rows=witness_rows,
    )
    role_values = {
        "budget_adequacy_contract_id": contract.contract_id,
        "runner_control_audit_id": runner_audit.audit_id,
        "budgeted_public_witness_audit_id": witness_audit.audit_id,
        "exposed_fixture_authority_path_count": exposed_fixture_authority_path_count,
    }
    provisional_role = BudgetAdequacyRoleProtocolPreflight.model_construct(
        preflight_id="pending",
        **role_values,
    )
    role_preflight = BudgetAdequacyRoleProtocolPreflight(
        preflight_id=budget_adequacy_role_preflight_id(provisional_role),
        **role_values,
    )
    detail_payloads = {
        "budget_adequacy_contract.json": contract.model_dump(mode="json"),
        "budgeted_public_witness_audit.json": witness_audit.model_dump(mode="json"),
        "role_protocol_preflight.json": role_preflight.model_dump(mode="json"),
        "runner_completion_control_audit.json": runner_audit.model_dump(mode="json"),
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
    raw_files = tuple(
        sorted(
            (item.raw_execution for item in runner_audit.controls),
            key=lambda item: item.relative_path,
        )
    )
    report_values = {
        "run_id": run_id,
        "source_replay_audit_id": source.audit_id,
        "budget_adequacy_contract_id": contract.contract_id,
        "runner_control_audit_id": runner_audit.audit_id,
        "budgeted_public_witness_audit_id": witness_audit.audit_id,
        "role_protocol_preflight_id": role_preflight.preflight_id,
        "immutable_detail_files": details,
        "immutable_raw_control_files": raw_files,
        "inherited_120k_budget_adequacy_established": (
            witness_audit.inherited_120k_budget_adequate_for_fixture_tasks
        ),
    }
    provisional_report = BudgetAdequacyContractPreflightReport.model_construct(
        report_id="pending",
        **report_values,
    )
    report = BudgetAdequacyContractPreflightReport(
        report_id=budget_adequacy_contract_preflight_report_id(provisional_report),
        **report_values,
    )
    _write_json(output_dir / "report.json", report.model_dump(mode="json"))
    return report


def budget_adequacy_contract_source_audit_id(
    value: BudgetAdequacyContractSourceAudit,
) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"audit_id"}),
        prefix="finance_v26_budget_adequacy_contract_source_replay:",
    )


def budget_adequacy_protocol_contract_id(
    value: BudgetAdequacyProtocolContract,
) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"contract_id"}),
        prefix="finance_v26_budget_adequacy_contract:",
    )


def fixture_provider_exchange_id(value: FixtureProviderExchange) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"exchange_id"}),
        prefix="finance_v26_budget_adequacy_fixture_exchange:",
    )


def runner_control_raw_execution_id(value: RunnerControlRawExecution) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"raw_execution_id"}),
        prefix="finance_v26_budget_adequacy_runner_raw_execution:",
    )


def runner_completion_control_id(value: RunnerCompletionControl) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"control_id"}),
        prefix="finance_v26_budget_adequacy_runner_control:",
    )


def runner_completion_control_audit_id(
    value: RunnerCompletionControlAudit,
) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"audit_id"}),
        prefix="finance_v26_budget_adequacy_runner_control_audit:",
    )


def budgeted_public_witness_row_id(value: BudgetedPublicWitnessRow) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"row_id"}),
        prefix="finance_v26_budgeted_public_witness_row:",
    )


def budgeted_public_witness_audit_id(
    value: BudgetedPublicWitnessAudit,
) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"audit_id"}),
        prefix="finance_v26_budgeted_public_witness_audit:",
    )


def budget_adequacy_role_preflight_id(
    value: BudgetAdequacyRoleProtocolPreflight,
) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"preflight_id"}),
        prefix="finance_v26_budget_adequacy_role_protocol_preflight:",
    )


def budget_adequacy_contract_preflight_report_id(
    value: BudgetAdequacyContractPreflightReport,
) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"report_id"}),
        prefix="finance_v26_budget_adequacy_contract_preflight_report:",
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Build the credential-free v26.89 Budget Adequacy Contract and static role preflight."
        )
    )
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--root-cause-dir", type=Path, required=True)
    parser.add_argument("--task-source-dir", type=Path, required=True)
    parser.add_argument("--instrument-preflight-dir", type=Path, required=True)
    parser.add_argument("--verifier-qualification-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--package-root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    report = build_budget_adequacy_contract_preflight(
        run_id=args.run_id,
        root_cause_dir=args.root_cause_dir,
        task_source_dir=args.task_source_dir,
        instrument_preflight_dir=args.instrument_preflight_dir,
        verifier_qualification_dir=args.verifier_qualification_dir,
        output_dir=args.output_dir,
        package_root=args.package_root,
    )
    print(
        json.dumps(
            report.model_dump(mode="json"),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
