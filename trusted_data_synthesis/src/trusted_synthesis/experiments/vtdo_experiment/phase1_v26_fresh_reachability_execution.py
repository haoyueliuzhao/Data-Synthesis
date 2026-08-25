from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
import threading
from collections import Counter, defaultdict
from collections.abc import Callable, Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Final, Literal, cast

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.core.evaluation.answer_semantics import (
    AnswerSemanticComparison,
    compare_answer_by_schema,
    make_answer_semantic_schema,
)
from trusted_synthesis.core.evaluation.joint_support_validity import (
    JointSupportValidityContract,
    JointSupportValidityResult,
    evaluate_joint_support_validity,
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
    MeasurementSupportDecision,
    classify_measurement_support,
    make_baseline_resolution,
    make_measurement_support_event,
)
from trusted_synthesis.core.trajectory.executable_task import matching_sufficient_support_set
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_reachability_runner_preflight as preflight,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_privacy_first_exact_final_execution as privacy_runner,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_semantic_action_calibration_online as semantic_online,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_two_stage_semantic_proposal_execution as legacy,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_verifier_vnext_contract_freeze as verifier_freeze,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_authority_preserving_verifier_replay import (  # noqa: E501
    AuthorityPreservingReplayContract,
    AuthorityPreservingReplayResult,
    match_empirical_program,
    replay_authority_preserving_observations,
)
from trusted_synthesis.hashing import canonical_hash
from trusted_synthesis.runtime.agent import prospective_reachability_runner_vnext as runner_vnext
from trusted_synthesis.runtime.agent.compact_budget_prompt import render_compact_final_prompt
from trusted_synthesis.runtime.agent.prospective_measurement_support import (
    classify_non_observation_support,
)
from trusted_synthesis.runtime.agent.prospective_qualified_final_response_grammar import (
    QualifiedFinalResponseGrammar,
    make_qualified_final_host_envelope,
)
from trusted_synthesis.runtime.agent.prospective_semantic_action_protocol import (
    build_semantic_action_state,
)
from trusted_synthesis.runtime.agent.prospective_two_stage_stage1_client import (
    StageOneProspectiveThinkingJsonClient,
)
from trusted_synthesis.runtime.agent.schema import AgentModelConfig

RUN_ID: Final = preflight.PROSPECTIVE_EXECUTION_RUN_ID
REPORT_RUN_ID: Final = preflight.PROSPECTIVE_REPORT_RUN_ID
PREFLIGHT_DIR: Final = preflight.OUTPUT_DIR
OUTPUT_DIR: Final = (
    "artifacts/vtdo_experiment/finance_v26_154_fresh_reachability_execution_v1_20260826"
)
IMPLEMENTATION_PATH: Final = (
    "src/trusted_synthesis/experiments/vtdo_experiment/phase1_v26_fresh_reachability_execution.py"
)
POSTRUN_STAGE: Final = "fresh_reachability_postrun_audit_only"

EXPECTED_PREFLIGHT_REPORT_ID: Final = (
    "finance_v26_fresh_reachability_preflight_report:"
    "4a055bf214893ee068db0cfb499e8d1beff7961a2cd8c98118196ae520adb666"
)
EXPECTED_PREFLIGHT_REPORT_SHA256: Final = (
    "bbc8908613072cdf25a67b65632746f42ab8759577106bc8d071a8ec30b6629e"
)
EXPECTED_PREFLIGHT_SOURCE_REPLAY_ID: Final = (
    "finance_v26_fresh_reachability_source_replay:"
    "be5c0f7b17a0989c5b03884a675f7362bd9f26dfaa036434092d9f0f790bbf40"
)
EXPECTED_FROZEN_INPUT_ID: Final = (
    "finance_v26_frozen_reachability_input_audit:"
    "de404a62e42860cc3383e2d24b12e4402b11102ba4f1e6a7e00bb07816d63521"
)
EXPECTED_TASK_CATALOG_ID: Final = (
    "finance_v26_fresh_reachability_task_catalog:"
    "3c2cd7acba456bd4147a2a5bee269171bddf0ec9c835f27af18d8113f657599f"
)
EXPECTED_PATH_CATALOG_ID: Final = (
    "finance_v26_fresh_reachability_path_catalog:"
    "71c0b44c157d63f2a77541ff231292eee09d91a8a70449c7fa99150f7e33c496"
)
EXPECTED_SUPPORT_CLOSURE_ID: Final = (
    "finance_v26_fresh_reachability_support_closure:"
    "be779c26f12b03e58002b717d5cc43e816b12265f0bd3a335c0721e627dba51d"
)
EXPECTED_DETOUR_QUALIFICATION_ID: Final = (
    "finance_v26_fresh_reachability_detour_audit:"
    "8d459c7124e92478269ffe5f53335a828bc2ee6279c3f4f930dda804e1327cd5"
)
EXPECTED_RESOURCE_CONTRACT_ID: Final = (
    "finance_v26_fresh_reachability_resource_contract:"
    "5f16af263fdd7395a6b6a0abe9aefe333072a4a53c4433927cdb7e396d57a621"
)
EXPECTED_EXECUTION_CONTRACT_ID: Final = (
    "finance_v26_fresh_reachability_execution_contract:"
    "292fc9a3e54a6128091bf52c6fb91e9f9ab5fbf37643fa752ce55908db4e33b5"
)
EXPECTED_MANIFEST_ID: Final = (
    "finance_v26_fresh_reachability_manifest:"
    "65e2e92ed30915fd615bf0dba6c72a7b764ab2c927dc355339bac303fb9830c0"
)
EXPECTED_OUTCOME_CONTRACT_ID: Final = (
    "finance_v26_fresh_reachability_outcome_contract:"
    "92b5aa2dd501538181b52613604f505d120a3d468ab3b70fd5cd539f63aa1663"
)
EXPECTED_RUNNER_CONTRACT_ID: Final = (
    "finance_v26_fresh_reachability_runner_contract:"
    "1c98edf4575b941b63dd81ea9e2bdf231a797ec6e979588bc80de550bc171206"
)
EXPECTED_TRANSITION_ID: Final = (
    "finance_v26_fresh_reachability_transition:"
    "aab44ab4bd316015f6ea97049fb1aa73ddfcec7c2c5ccffd673bdcc1357c4471"
)
EXPECTED_TRANSITION_SHA256: Final = (
    "63efea9b30f4b29ab6a16e1cd4225ca484723aac3f40b90e0eb630b7c3933e6b"
)
EXPECTED_PROSPECTIVE_EXECUTION_ID: Final = (
    "finance_v26_fresh_reachability_execution:"
    "3ecaeff28dba29932b0e4d8aff506af152bb36b3dd59859941ed6b98a795842c"
)
EXPECTED_PROSPECTIVE_REPORT_ID: Final = (
    "finance_v26_fresh_reachability_execution_report:"
    "d6f431047ec9c5f620dbaea2408ed394127a45190630eb8ca046baa23af1c556"
)
EXPECTED_NONINTERFERENCE_CONTRACT_ID: Final = (
    "finance_v26_responsibility_noninterference_contract:"
    "f6793d4ff0fbd901e3841d1f7f59248b6e17469746ec083eb1b8e2418c3bc494"
)

PREFLIGHT_OUTPUTS: Final = (
    "destructive_audit.json",
    "detour_qualification_audit.json",
    "frozen_reachability_input_audit.json",
    "joint_support_validity_contract.json",
    "predecessor_integrity_audit.json",
    "prospective_transition_contract.json",
    "qualified_final_response_grammar.json",
    "reachability_execution_contract.json",
    "reachability_manifest.json",
    "reachability_outcome_contract.json",
    "reachability_path_catalog.json",
    "reachability_resource_contract.json",
    "reachability_runner_contract.json",
    "reachability_runner_control_audit.json",
    "reachability_runner_fixture_audit.json",
    "reachability_task_package_catalog.json",
    "report.json",
    "source_replay_audit.json",
    "support_closure_audit.json",
)


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", arbitrary_types_allowed=True)


def _identity(value: BaseModel, field: str, prefix: str) -> str:
    return canonical_hash(value.model_dump(mode="json", exclude={field}), prefix=prefix)


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _json_payload(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, Mapping):
        return {str(key): _json_payload(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_payload(item) for item in value]
    return value


def _canonical_bytes(value: Any) -> bytes:
    return (
        json.dumps(
            _json_payload(value),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")


def _write_json_atomic(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(_canonical_bytes(value))
    temporary.replace(path)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _descriptor(path: Path, output_dir: Path) -> legacy.RawFileDescriptor:
    return legacy.RawFileDescriptor(
        relative_path=str(path.resolve().relative_to(output_dir.resolve())),
        sha256=_sha256(path),
        byte_count=path.stat().st_size,
    )


class SourceReplayEntry(FrozenModel):
    relative_path: str = Field(min_length=1)
    source_kind: Literal[
        "v26_153_transitive_source",
        "v26_153_output",
        "v26_154_implementation",
    ]
    expected_sha256: str = Field(min_length=64, max_length=64)
    observed_sha256: str = Field(min_length=64, max_length=64)
    byte_count: int = Field(gt=0)
    passed: Literal[True] = True


class ExecutionSourceReplayAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    predecessor_report_id: str = EXPECTED_PREFLIGHT_REPORT_ID
    predecessor_source_replay_id: str = EXPECTED_PREFLIGHT_SOURCE_REPLAY_ID
    predecessor_transitive_file_count: Literal[10136] = 10136
    predecessor_output_file_count: Literal[19] = 19
    implementation_file_count: Literal[1] = 1
    replayed_file_count: Literal[10156] = 10156
    replay_pass_count: Literal[10156] = 10156
    entries: tuple[SourceReplayEntry, ...] = Field(min_length=10156, max_length=10156)
    replay_before_profile_parsing: Literal[True] = True
    replay_before_credential_lookup: Literal[True] = True
    replay_before_client_construction: Literal[True] = True
    credential_lookup_attempted: Literal[False] = False
    model_client_constructed: Literal[False] = False
    provider_calls: Literal[0] = 0
    stage_two_provider_calls: Literal[0] = 0
    gpu_jobs: Literal[0] = 0
    status: Literal["passed"] = "passed"

    @model_validator(mode="after")
    def validate_audit(self) -> ExecutionSourceReplayAudit:
        paths = tuple(item.relative_path for item in self.entries)
        if (
            paths != tuple(sorted(set(paths)))
            or len(paths) != self.replayed_file_count
            or any(item.expected_sha256 != item.observed_sha256 for item in self.entries)
            or self.audit_id
            != _identity(
                self,
                "audit_id",
                "finance_v26_fresh_reachability_execution_source_replay:",
            )
        ):
            raise ValueError("v26.154 source replay changed")
        return self


class PreexecutionBindingAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    predecessor_report_id: str = EXPECTED_PREFLIGHT_REPORT_ID
    manifest_id: str = EXPECTED_MANIFEST_ID
    runner_contract_id: str = EXPECTED_RUNNER_CONTRACT_ID
    outcome_contract_id: str = EXPECTED_OUTCOME_CONTRACT_ID
    rebuilt_preflight_output_count: Literal[19] = 19
    byte_identical_preflight_output_count: Literal[19] = 19
    exact_job_count: Literal[360] = 360
    distinct_task_count: Literal[12] = 12
    registered_path_count: Literal[36] = 36
    mechanism_tier_cell_count: Literal[12] = 12
    source_task_first_exposure_count: Literal[12] = 12
    unconditional_job_count: Literal[144] = 144
    conditioned_job_count: Literal[216] = 216
    preserved_v26_132_seed_count: Literal[360] = 360
    historical_job_overlap_count: Literal[0] = 0
    fresh_reachability_identity_count: Literal[360] = 360
    state_mapping_identity_count: Literal[0] = 0
    credential_lookup_attempted: Literal[False] = False
    real_model_client_constructed: Literal[False] = False
    real_provider_calls: Literal[0] = 0
    stage_two_provider_calls: Literal[0] = 0
    status: Literal["passed"] = "passed"

    @model_validator(mode="after")
    def validate_audit(self) -> PreexecutionBindingAudit:
        if self.audit_id != _identity(
            self,
            "audit_id",
            "finance_v26_fresh_reachability_preexecution_binding:",
        ):
            raise ValueError("v26.154 preexecution binding changed")
        return self


class OnlineNoninterferenceAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    noninterference_contract_id: str = EXPECTED_NONINTERFERENCE_CONTRACT_ID
    runner_contract_id: str = EXPECTED_RUNNER_CONTRACT_ID
    qualified_final_grammar_id: str = Field(min_length=1)
    task_package_id: str = Field(min_length=1)
    job_id: str = Field(min_length=1)
    reached_prompt_count: int = Field(ge=0, le=24)
    prompt_hash_match_count: int = Field(ge=0, le=24)
    sensitive_key_count: Literal[0] = 0
    host_answer_insert_count: Literal[0] = 0
    host_citation_insert_count: Literal[0] = 0
    host_rationale_insert_count: Literal[0] = 0
    model_owned_final_fields: tuple[str, str, str] = (
        "answer.citations",
        "answer.result",
        "rationale_summary",
    )
    passed: Literal[True] = True

    @model_validator(mode="after")
    def validate_audit(self) -> OnlineNoninterferenceAudit:
        if self.prompt_hash_match_count != self.reached_prompt_count:
            raise ValueError("v26.154 online Prompt hash binding changed")
        if self.audit_id != _identity(
            self, "audit_id", "finance_v26_fresh_reachability_online_noninterference:"
        ):
            raise ValueError("v26.154 online noninterference identity changed")
        return self


class ReachabilityMeasurementResult(FrozenModel):
    result_id: str = Field(min_length=1)
    job_id: str = Field(min_length=1)
    task_package_id: str = Field(min_length=1)
    source_task_artifact_id: str = Field(min_length=1)
    mechanism_id: MechanismId
    tier: Literal["easy_control", "frontier", "hard_control"]
    sampling_mode: preflight.SamplingMode
    replicate_index: int = Field(ge=0, le=11)
    seed: int = Field(ge=0)
    requested_path_id: str | None
    requested_path_strategy: preflight.PathStrategy | None
    public_path_condition: str | None
    public_condition_id: str | None
    condition_binding_valid: Literal[True] = True
    raw_execution_id: str = Field(min_length=1)
    raw_execution_artifact: legacy.RawFileDescriptor
    raw_terminal_disposition: runner_vnext.RunnerTerminal
    terminal_failure_type: str | None = None
    execution_error: str | None = None

    measurement_support_available: bool
    model_endpoint_observed: bool
    instrument_integrity: bool
    privacy_compliant: bool
    validity_evaluable: bool
    endpoint_projection_matches_raw: bool
    support_decision_source: Literal[
        "raw_last", "typed_detour_limit_exit", "endpoint_no_public_commit"
    ]
    support_decision: MeasurementSupportDecision
    joint_result: JointSupportValidityResult
    online_noninterference_audit: OnlineNoninterferenceAudit | None = None
    runtime_replay: AuthorityPreservingReplayResult | None = None
    answer_comparison: AnswerSemanticComparison | None = None
    base_trajectory_validity: bool | None
    mechanism_qualification: bool | None
    qualified_trajectory_validity: bool | None
    state_mapping_eligible: bool
    task_verifier_invocation_count: Literal[0, 1]
    observed_mechanism_event_ids: tuple[str, ...]

    first_action_interface_qualified: bool
    program_closed: bool
    terminal_verification_complete: bool
    exact_qualified_final_payload_count: int = Field(ge=0, le=1)
    provider_call_count: int = Field(ge=0, le=23)
    transport_inclusive_invocation_count: int = Field(ge=0, le=24)
    provider_prompt_tokens: int = Field(ge=0)
    provider_completion_tokens: int = Field(ge=0)
    provider_reasoning_tokens: int = Field(ge=0)
    provider_total_tokens: int = Field(ge=0, le=1_120_000)
    estimated_cost_usd: str = Field(min_length=1)

    exact_model_passed: bool
    fallback_absent: bool
    provider_native_tool_absent: bool
    thinking_continuity_passed: bool
    provider_usage_complete: bool
    dynamic_precall_binding_passed: bool
    exact_request_binding_passed: bool
    privacy_artifact_pairing_passed: bool
    reversible_commit_integrity_passed: bool
    rollout_budget_passed: bool
    unresolved_transport_failure: bool
    typed_budget_no_call: bool
    measurement_gate_failure_ids: tuple[str, ...]
    static_path_used_as_empirical_state: Literal[False] = False
    reachability_measurement_row_count: Literal[1] = 1
    stage_two_provider_call_count: Literal[0] = 0
    state_mapping_row_count: Literal[0] = 0

    @model_validator(mode="after")
    def validate_result(self) -> ReachabilityMeasurementResult:
        evaluable = all(
            (
                self.measurement_support_available,
                self.model_endpoint_observed,
                self.instrument_integrity,
                self.privacy_compliant,
            )
        )
        conditioned = self.sampling_mode == "reachability_conditioned"
        condition_fields = (
            self.requested_path_id,
            self.requested_path_strategy,
            self.public_path_condition,
            self.public_condition_id,
        )
        if (
            self.validity_evaluable != evaluable
            or conditioned != all(item is not None for item in condition_fields)
            or (not conditioned and any(item is not None for item in condition_fields))
            or (conditioned and self.requested_path_strategy != self.public_path_condition)
        ):
            raise ValueError("v26.154 eligibility or condition binding changed")
        if (
            self.joint_result.eligibility.evaluable != evaluable
            or self.joint_result.qualified_report.valid != self.qualified_trajectory_validity
            or self.joint_result.base_report.valid != self.base_trajectory_validity
            or self.joint_result.mechanism_report.success != self.mechanism_qualification
            or self.joint_result.state_mapping_eligible != self.state_mapping_eligible
            or self.joint_result.task_verifier_invocation_count
            != self.task_verifier_invocation_count
            or self.state_mapping_eligible != (self.qualified_trajectory_validity is True)
        ):
            raise ValueError("v26.154 joint result projection changed")
        for item, name in (
            (self.runtime_replay, "runtime Replay"),
            (self.online_noninterference_audit, "noninterference"),
            (self.answer_comparison, "Answer comparison"),
        ):
            if evaluable != (item is not None):
                raise ValueError(f"v26.154 {name} eligibility changed")
        if self.result_id != _identity(
            self,
            "result_id",
            "finance_v26_fresh_reachability_measurement_result:",
        ):
            raise ValueError("v26.154 result identity changed")
        return self


class UnconditionalTaskSummary(FrozenModel):
    summary_id: str = Field(min_length=1)
    task_package_id: str = Field(min_length=1)
    source_task_artifact_id: str = Field(min_length=1)
    mechanism_id: MechanismId
    tier: Literal["easy_control", "frontier", "hard_control"]
    sampling_mode: Literal["reachability_unconditional"] = "reachability_unconditional"
    job_count: Literal[12] = 12
    model_endpoint_count: int = Field(ge=0, le=12)
    evaluable_count: int = Field(ge=0, le=12)
    base_valid_count: int = Field(ge=0, le=12)
    mechanism_qualified_count: int = Field(ge=0, le=12)
    qualified_valid_count: int = Field(ge=0, le=12)
    state_mapping_eligible_count: int = Field(ge=0, le=12)
    base_fraction: str | None
    mechanism_fraction: str | None
    qualified_fraction: str | None
    terminal_counts: dict[str, int]
    estimand_authorized: bool

    @model_validator(mode="after")
    def validate_summary(self) -> UnconditionalTaskSummary:
        expected = (
            (
                f"{self.base_valid_count}/12",
                f"{self.mechanism_qualified_count}/12",
                f"{self.qualified_valid_count}/12",
            )
            if self.estimand_authorized
            else (None, None, None)
        )
        if (
            sum(self.terminal_counts.values()) != 12
            or self.state_mapping_eligible_count != self.qualified_valid_count
            or (self.base_fraction, self.mechanism_fraction, self.qualified_fraction) != expected
            or self.summary_id
            != _identity(
                self,
                "summary_id",
                "finance_v26_fresh_reachability_unconditional_task_estimand:",
            )
        ):
            raise ValueError("v26.154 unconditional Task summary changed")
        return self


class ConditionedPathSummary(FrozenModel):
    summary_id: str = Field(min_length=1)
    path_id: str = Field(min_length=1)
    path_strategy_id: preflight.PathStrategy
    public_path_condition: str = Field(min_length=1)
    public_condition_id: str = Field(min_length=1)
    task_package_id: str = Field(min_length=1)
    source_task_artifact_id: str = Field(min_length=1)
    mechanism_id: MechanismId
    tier: Literal["easy_control", "frontier", "hard_control"]
    sampling_mode: Literal["reachability_conditioned"] = "reachability_conditioned"
    job_count: Literal[6] = 6
    model_endpoint_count: int = Field(ge=0, le=6)
    evaluable_count: int = Field(ge=0, le=6)
    base_valid_count: int = Field(ge=0, le=6)
    mechanism_qualified_count: int = Field(ge=0, le=6)
    qualified_valid_count: int = Field(ge=0, le=6)
    state_mapping_eligible_count: int = Field(ge=0, le=6)
    base_fraction: str | None
    mechanism_fraction: str | None
    qualified_fraction: str | None
    terminal_counts: dict[str, int]
    estimand_authorized: bool
    static_path_is_target_condition: Literal[True] = True
    empirical_state_mapping_row_count: Literal[0] = 0

    @model_validator(mode="after")
    def validate_summary(self) -> ConditionedPathSummary:
        expected = (
            (
                f"{self.base_valid_count}/6",
                f"{self.mechanism_qualified_count}/6",
                f"{self.qualified_valid_count}/6",
            )
            if self.estimand_authorized
            else (None, None, None)
        )
        if (
            self.path_strategy_id != self.public_path_condition
            or sum(self.terminal_counts.values()) != 6
            or self.state_mapping_eligible_count != self.qualified_valid_count
            or (self.base_fraction, self.mechanism_fraction, self.qualified_fraction) != expected
            or self.summary_id
            != _identity(
                self,
                "summary_id",
                "finance_v26_fresh_reachability_conditioned_path_estimand:",
            )
        ):
            raise ValueError("v26.154 conditioned Path summary changed")
        return self


class MechanismReachabilitySummary(FrozenModel):
    summary_id: str = Field(min_length=1)
    mechanism_id: MechanismId
    independent_task_count: Literal[3] = 3
    conditioned_path_count: Literal[9] = 9
    unconditional_job_count: Literal[36] = 36
    conditioned_job_count: Literal[54] = 54
    unconditional_base_valid_count: int = Field(ge=0, le=36)
    unconditional_mechanism_qualified_count: int = Field(ge=0, le=36)
    unconditional_qualified_valid_count: int = Field(ge=0, le=36)
    conditioned_base_valid_count: int = Field(ge=0, le=54)
    conditioned_mechanism_qualified_count: int = Field(ge=0, le=54)
    conditioned_qualified_valid_count: int = Field(ge=0, le=54)
    tasks_with_unconditional_qualified_trajectory: int = Field(ge=0, le=3)
    paths_with_conditioned_qualified_trajectory: int = Field(ge=0, le=9)
    unconditional_task_weighted_qualified_fraction: str | None
    conditioned_path_weighted_qualified_fraction: str | None
    estimand_authorized: bool

    @model_validator(mode="after")
    def validate_summary(self) -> MechanismReachabilitySummary:
        if self.summary_id != _identity(
            self,
            "summary_id",
            "finance_v26_fresh_reachability_mechanism_estimand:",
        ):
            raise ValueError("v26.154 Mechanism summary changed")
        return self


class MeasurementGateAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    outcome_contract_id: str = EXPECTED_OUTCOME_CONTRACT_ID
    exact_denominator: Literal[360] = 360
    complete_raw_count: int = Field(ge=0, le=360)
    model_endpoint_count: int = Field(ge=0, le=360)
    measurement_support_exit_count: int = Field(ge=0, le=360)
    instrument_failure_count: int = Field(ge=0, le=360)
    privacy_failure_count: int = Field(ge=0, le=360)
    exact_model_thinking_usage_failure_count: int = Field(ge=0, le=360)
    typed_budget_no_call_count: int = Field(ge=0, le=360)
    unresolved_transport_failure_count: int = Field(ge=0, le=360)
    failure_ids: tuple[str, ...]
    passed: bool
    reachability_estimands_authorized: bool
    state_mapping_eligibility_estimand_authorized: bool
    state_mapping_contract_or_execution_authorized: Literal[False] = False
    noncompensatory: Literal[True] = True

    @model_validator(mode="after")
    def validate_audit(self) -> MeasurementGateAudit:
        checks = {
            "complete_raw_360_of_360": self.complete_raw_count == 360,
            "model_endpoint_360_of_360": self.model_endpoint_count == 360,
            "measurement_support_exit_zero": self.measurement_support_exit_count == 0,
            "instrument_failure_zero": self.instrument_failure_count == 0,
            "privacy_failure_zero": self.privacy_failure_count == 0,
            "exact_model_thinking_usage_failure_zero": (
                self.exact_model_thinking_usage_failure_count == 0
            ),
            "typed_budget_no_call_zero": self.typed_budget_no_call_count == 0,
            "unresolved_transport_failure_zero": (self.unresolved_transport_failure_count == 0),
        }
        failures = tuple(sorted(key for key, value in checks.items() if not value))
        if (
            self.failure_ids != failures
            or self.passed != all(checks.values())
            or self.reachability_estimands_authorized != self.passed
            or self.state_mapping_eligibility_estimand_authorized != self.passed
            or self.audit_id
            != _identity(
                self,
                "audit_id",
                "finance_v26_fresh_reachability_measurement_gate:",
            )
        ):
            raise ValueError("v26.154 Measurement Gate changed")
        return self


class RawLineageAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    runner_contract_id: str = EXPECTED_RUNNER_CONTRACT_ID
    manifest_id: str = EXPECTED_MANIFEST_ID
    raw_execution_count: Literal[360] = 360
    job_result_count: Literal[360] = 360
    provider_call_count: int = Field(ge=0, le=8280)
    transport_invocation_count: int = Field(ge=0, le=8640)
    provider_envelope_count: int = Field(ge=0, le=8280)
    public_projection_count: int = Field(ge=0, le=8280)
    complete_provider_pair_count: int = Field(ge=0, le=8280)
    raw_descriptors: tuple[legacy.RawFileDescriptor, ...] = Field(
        min_length=360,
        max_length=360,
    )
    provider_artifact_descriptors: tuple[legacy.RawFileDescriptor, ...]
    private_reasoning_payload_count: Literal[0] = 0
    invalid_payload_persistence_count: Literal[0] = 0
    raw_http_body_persistence_count: Literal[0] = 0
    raw_request_body_persistence_count: Literal[0] = 0
    stage_two_provider_call_count: Literal[0] = 0
    state_mapping_row_count: Literal[0] = 0
    exact_byte_replay_pass_count: int = Field(ge=360)
    status: Literal["passed"] = "passed"

    @model_validator(mode="after")
    def validate_audit(self) -> RawLineageAudit:
        if (
            self.provider_call_count != self.provider_envelope_count
            or self.provider_call_count != self.public_projection_count
            or self.provider_call_count != self.complete_provider_pair_count
            or self.exact_byte_replay_pass_count
            != len(self.raw_descriptors) + len(self.provider_artifact_descriptors)
            or self.audit_id
            != _identity(
                self,
                "audit_id",
                "finance_v26_fresh_reachability_raw_lineage:",
            )
        ):
            raise ValueError("v26.154 Raw Lineage changed")
        return self


class ReachabilityExecutionReport(FrozenModel):
    report_id: str = Field(min_length=1)
    run_id: str = RUN_ID
    report_run_id: str = REPORT_RUN_ID
    source_replay_audit_id: str = Field(min_length=1)
    preexecution_binding_audit_id: str = Field(min_length=1)
    preflight_report_id: str = EXPECTED_PREFLIGHT_REPORT_ID
    prospective_report_id: str = EXPECTED_PROSPECTIVE_REPORT_ID
    execution_contract_id: str = EXPECTED_EXECUTION_CONTRACT_ID
    manifest_id: str = EXPECTED_MANIFEST_ID
    outcome_contract_id: str = EXPECTED_OUTCOME_CONTRACT_ID
    runner_contract_id: str = EXPECTED_RUNNER_CONTRACT_ID
    joint_support_validity_contract_id: str = preflight.EXPECTED_JOINT_CONTRACT_ID
    raw_lineage_audit_id: str = Field(min_length=1)
    measurement_gate_audit_id: str = Field(min_length=1)
    exact_job_denominator: Literal[360] = 360
    distinct_task_count: Literal[12] = 12
    conditioned_path_count: Literal[36] = 36
    unconditional_job_count: Literal[144] = 144
    conditioned_job_count: Literal[216] = 216
    complete_result_count: Literal[360] = 360
    complete_raw_count: Literal[360] = 360
    terminal_counts: dict[str, int]
    measurement_gate_passed: bool
    reachability_estimands_authorized: bool
    base_valid_count: int = Field(ge=0, le=360)
    mechanism_qualified_count: int = Field(ge=0, le=360)
    qualified_valid_count: int = Field(ge=0, le=360)
    state_mapping_eligible_count: int = Field(ge=0, le=360)
    unconditional_base_valid_count: int = Field(ge=0, le=144)
    unconditional_mechanism_qualified_count: int = Field(ge=0, le=144)
    unconditional_qualified_valid_count: int = Field(ge=0, le=144)
    conditioned_base_valid_count: int = Field(ge=0, le=216)
    conditioned_mechanism_qualified_count: int = Field(ge=0, le=216)
    conditioned_qualified_valid_count: int = Field(ge=0, le=216)
    unconditional_task_weighted_base_fraction: str | None
    unconditional_task_weighted_mechanism_fraction: str | None
    unconditional_task_weighted_qualified_fraction: str | None
    conditioned_path_weighted_base_fraction: str | None
    conditioned_path_weighted_mechanism_fraction: str | None
    conditioned_path_weighted_qualified_fraction: str | None
    unconditional_task_summaries: tuple[UnconditionalTaskSummary, ...] = Field(
        min_length=12,
        max_length=12,
    )
    conditioned_path_summaries: tuple[ConditionedPathSummary, ...] = Field(
        min_length=36,
        max_length=36,
    )
    mechanism_summaries: tuple[MechanismReachabilitySummary, ...] = Field(
        min_length=4,
        max_length=4,
    )
    provider_call_count: int = Field(ge=0, le=8280)
    transport_inclusive_invocation_count: int = Field(ge=0, le=8640)
    provider_prompt_tokens: int = Field(ge=0)
    provider_completion_tokens: int = Field(ge=0)
    provider_reasoning_tokens: int = Field(ge=0)
    provider_total_tokens: int = Field(ge=0)
    estimated_cost_usd: str = Field(min_length=1)
    task_is_primary_unconditional_sampling_unit: Literal[True] = True
    path_is_primary_conditioned_sampling_unit: Literal[True] = True
    rollout_is_secondary_repeated_measure: Literal[True] = True
    static_path_used_as_empirical_state: Literal[False] = False
    independent_postrun_audit_required: Literal[True] = True
    state_mapping_contract_count: Literal[0] = 0
    state_mapping_rows: Literal[0] = 0
    training_rows: Literal[0] = 0
    release_rows: Literal[0] = 0
    production_contribution: Literal[0] = 0
    next_permitted_stage: Literal["fresh_reachability_postrun_audit_only"] = POSTRUN_STAGE
    execution_status: Literal[
        "measurement_gate_passed_pending_independent_audit",
        "measurement_gate_failed_pending_independent_audit",
    ]

    @model_validator(mode="after")
    def validate_report(self) -> ReachabilityExecutionReport:
        fractions = (
            self.unconditional_task_weighted_base_fraction,
            self.unconditional_task_weighted_mechanism_fraction,
            self.unconditional_task_weighted_qualified_fraction,
            self.conditioned_path_weighted_base_fraction,
            self.conditioned_path_weighted_mechanism_fraction,
            self.conditioned_path_weighted_qualified_fraction,
        )
        expected_status = (
            "measurement_gate_passed_pending_independent_audit"
            if self.measurement_gate_passed
            else "measurement_gate_failed_pending_independent_audit"
        )
        if (
            sum(self.terminal_counts.values()) != 360
            or self.reachability_estimands_authorized != self.measurement_gate_passed
            or (all(item is not None for item in fractions) != self.measurement_gate_passed)
            or self.state_mapping_eligible_count != self.qualified_valid_count
            or self.base_valid_count
            != self.unconditional_base_valid_count + self.conditioned_base_valid_count
            or self.mechanism_qualified_count
            != self.unconditional_mechanism_qualified_count
            + self.conditioned_mechanism_qualified_count
            or self.qualified_valid_count
            != self.unconditional_qualified_valid_count + self.conditioned_qualified_valid_count
            or self.execution_status != expected_status
            or self.report_id
            != _identity(
                self,
                "report_id",
                "finance_v26_fresh_reachability_execution_report:",
            )
        ):
            raise ValueError("v26.154 report Gate or partition changed")
        return self


@dataclass(frozen=True)
class PreparedExecution:
    source_replay: ExecutionSourceReplayAudit
    preflight_report: preflight.ReachabilityPreflightReport
    frozen_input: preflight.FrozenReachabilityInputAudit
    tasks: preflight.TaskPackageCatalog
    paths: preflight.PathCatalog
    support_closure: preflight.SupportClosureAudit
    detour_qualification: preflight.ReachabilityDetourQualificationAudit
    resource: preflight.ResourceContract
    execution_contract: preflight.ExecutionContract
    manifest: preflight.ReachabilityManifest
    outcome_contract: preflight.OutcomeContract
    runner_contract: preflight.RunnerContract
    joint_contract: JointSupportValidityContract
    grammar: QualifiedFinalResponseGrammar
    transition: preflight.ProspectiveTransitionContract
    preexecution_binding: PreexecutionBindingAudit
    role_inputs: Any
    replay_contract: AuthorityPreservingReplayContract


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
    raise ValueError(f"v26.154 cannot replay bound file: {relative_path}")


def build_execution_source_replay(
    *,
    package_root: Path,
    implementation_root: Path,
    preflight_dir: Path,
) -> ExecutionSourceReplayAudit:
    predecessor_source = preflight.SourceReplayAudit.model_validate(
        _load(preflight_dir / "source_replay_audit.json")
    )
    report_path = preflight_dir / "report.json"
    transition_path = preflight_dir / "prospective_transition_contract.json"
    report = preflight.ReachabilityPreflightReport.model_validate(_load(report_path))
    if (
        predecessor_source.audit_id != EXPECTED_PREFLIGHT_SOURCE_REPLAY_ID
        or report.report_id != EXPECTED_PREFLIGHT_REPORT_ID
        or _sha256(report_path) != EXPECTED_PREFLIGHT_REPORT_SHA256
        or _sha256(transition_path) != EXPECTED_TRANSITION_SHA256
    ):
        raise ValueError("v26.154 predecessor report, transition, or replay changed")

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
            source_kind="v26_153_transitive_source",
            expected_sha256=item.expected_sha256,
            observed_sha256=_sha256(path),
            byte_count=path.stat().st_size,
        )

    details = {item.relative_path: item for item in report.detail_files}
    if set(PREFLIGHT_OUTPUTS) != {"report.json", *details}:
        raise ValueError("v26.154 predecessor output set changed")
    for name in PREFLIGHT_OUTPUTS:
        path = preflight_dir / name
        if not path.is_file():
            raise ValueError(f"v26.154 predecessor output missing: {name}")
        observed = _sha256(path)
        if name != "report.json":
            detail = details[name]
            if detail.sha256 != observed or detail.byte_count != path.stat().st_size:
                raise ValueError("v26.154 predecessor detail binding changed")
        relative = str(Path(PREFLIGHT_DIR) / name)
        entries[relative] = SourceReplayEntry(
            relative_path=relative,
            source_kind="v26_153_output",
            expected_sha256=observed,
            observed_sha256=observed,
            byte_count=path.stat().st_size,
        )

    implementation_path = implementation_root / IMPLEMENTATION_PATH
    observed = _sha256(implementation_path)
    entries[IMPLEMENTATION_PATH] = SourceReplayEntry(
        relative_path=IMPLEMENTATION_PATH,
        source_kind="v26_154_implementation",
        expected_sha256=observed,
        observed_sha256=observed,
        byte_count=implementation_path.stat().st_size,
    )
    ordered = tuple(entries[key] for key in sorted(entries))
    values: dict[str, Any] = {"entries": ordered}
    provisional = ExecutionSourceReplayAudit.model_construct(audit_id="pending", **values)
    return ExecutionSourceReplayAudit(
        audit_id=_identity(
            provisional,
            "audit_id",
            "finance_v26_fresh_reachability_execution_source_replay:",
        ),
        **values,
    )


def _rebuild_preflight(
    *,
    package_root: Path,
    implementation_root: Path,
    preflight_dir: Path,
) -> PreexecutionBindingAudit:
    with tempfile.TemporaryDirectory(prefix="v26_154_preflight_rebuild_") as temporary:
        rebuilt = Path(temporary)
        report = preflight.build_fresh_reachability_preflight(
            package_root=package_root,
            implementation_root=implementation_root,
            output_dir=rebuilt,
        )
        for name in PREFLIGHT_OUTPUTS:
            if (preflight_dir / name).read_bytes() != (rebuilt / name).read_bytes():
                raise ValueError(f"v26.154 predecessor rebuild changed: {name}")
    manifest = preflight.ReachabilityManifest.model_validate(
        _load(preflight_dir / "reachability_manifest.json")
    )
    if report.report_id != EXPECTED_PREFLIGHT_REPORT_ID:
        raise ValueError("v26.154 rebuilt predecessor report identity changed")
    values: dict[str, Any] = {
        "exact_job_count": len(manifest.jobs),
        "distinct_task_count": len({item.task_package_id for item in manifest.jobs}),
        "registered_path_count": manifest.distinct_path_count,
        "mechanism_tier_cell_count": len(
            {(item.mechanism_id, item.tier) for item in manifest.jobs}
        ),
        "unconditional_job_count": sum(
            item.sampling_mode == "reachability_unconditional" for item in manifest.jobs
        ),
        "conditioned_job_count": sum(
            item.sampling_mode == "reachability_conditioned" for item in manifest.jobs
        ),
        "preserved_v26_132_seed_count": sum(
            item.frozen_v26_132_seed_preserved for item in manifest.jobs
        ),
    }
    provisional = PreexecutionBindingAudit.model_construct(audit_id="pending", **values)
    return PreexecutionBindingAudit(
        audit_id=_identity(
            provisional,
            "audit_id",
            "finance_v26_fresh_reachability_preexecution_binding:",
        ),
        **values,
    )


def prepare_execution(
    *,
    preflight_dir: Path,
    output_dir: Path,
    package_root: Path,
    implementation_root: Path,
) -> PreparedExecution:
    output_dir.mkdir(parents=True, exist_ok=True)
    source = build_execution_source_replay(
        package_root=package_root,
        implementation_root=implementation_root,
        preflight_dir=preflight_dir,
    )
    _write_json_atomic(output_dir / "execution_source_replay_audit.json", source)
    preexecution = _rebuild_preflight(
        package_root=package_root,
        implementation_root=implementation_root,
        preflight_dir=preflight_dir,
    )

    report = preflight.ReachabilityPreflightReport.model_validate(
        _load(preflight_dir / "report.json")
    )
    frozen_input = preflight.FrozenReachabilityInputAudit.model_validate(
        _load(preflight_dir / "frozen_reachability_input_audit.json")
    )
    tasks = preflight.TaskPackageCatalog.model_validate(
        _load(preflight_dir / "reachability_task_package_catalog.json")
    )
    paths = preflight.PathCatalog.model_validate(
        _load(preflight_dir / "reachability_path_catalog.json")
    )
    support = preflight.SupportClosureAudit.model_validate(
        _load(preflight_dir / "support_closure_audit.json")
    )
    detours = preflight.ReachabilityDetourQualificationAudit.model_validate(
        _load(preflight_dir / "detour_qualification_audit.json")
    )
    resource = preflight.ResourceContract.model_validate(
        _load(preflight_dir / "reachability_resource_contract.json")
    )
    execution = preflight.ExecutionContract.model_validate(
        _load(preflight_dir / "reachability_execution_contract.json")
    )
    manifest = preflight.ReachabilityManifest.model_validate(
        _load(preflight_dir / "reachability_manifest.json")
    )
    outcome = preflight.OutcomeContract.model_validate(
        _load(preflight_dir / "reachability_outcome_contract.json")
    )
    runner = preflight.RunnerContract.model_validate(
        _load(preflight_dir / "reachability_runner_contract.json")
    )
    joint = JointSupportValidityContract.model_validate(
        _load(preflight_dir / "joint_support_validity_contract.json")
    )
    grammar = QualifiedFinalResponseGrammar.model_validate(
        _load(preflight_dir / "qualified_final_response_grammar.json")
    )
    transition = preflight.ProspectiveTransitionContract.model_validate(
        _load(preflight_dir / "prospective_transition_contract.json")
    )
    noninterference_contract = (
        verifier_freeze.ResponsibilityAndNoninterferenceContract.model_validate(
            _load(
                package_root
                / verifier_freeze.OUTPUT_DIR
                / "responsibility_noninterference_contract.json"
            )
        )
    )
    role_inputs = preflight.old_capability._load_role_inputs(  # noqa: SLF001
        package_root=package_root,
        implementation_root=implementation_root,
    )
    _, replay_contract = preflight.bounded.predecessor._load_and_replay_verifier_qualification(  # noqa: SLF001
        package_root / preflight.bounded.predecessor.VERIFIER_QUALIFICATION_DIR,
        package_root,
    )

    modes = Counter(item.sampling_mode for item in manifest.jobs)
    conditioned_paths = {
        item.requested_path_id
        for item in manifest.jobs
        if item.sampling_mode == "reachability_conditioned"
    }
    if (
        report.report_id != EXPECTED_PREFLIGHT_REPORT_ID
        or report.source_replay_audit_id != EXPECTED_PREFLIGHT_SOURCE_REPLAY_ID
        or report.frozen_input_audit_id != EXPECTED_FROZEN_INPUT_ID
        or report.task_catalog_id != EXPECTED_TASK_CATALOG_ID
        or report.path_catalog_id != EXPECTED_PATH_CATALOG_ID
        or report.support_closure_audit_id != EXPECTED_SUPPORT_CLOSURE_ID
        or report.detour_qualification_audit_id != EXPECTED_DETOUR_QUALIFICATION_ID
        or report.resource_contract_id != EXPECTED_RESOURCE_CONTRACT_ID
        or report.execution_contract_id != EXPECTED_EXECUTION_CONTRACT_ID
        or report.manifest_id != EXPECTED_MANIFEST_ID
        or report.outcome_contract_id != EXPECTED_OUTCOME_CONTRACT_ID
        or report.runner_contract_id != EXPECTED_RUNNER_CONTRACT_ID
        or report.transition_contract_id != EXPECTED_TRANSITION_ID
        or report.prospective_execution_id != EXPECTED_PROSPECTIVE_EXECUTION_ID
        or report.prospective_report_id != EXPECTED_PROSPECTIVE_REPORT_ID
        or report.status != "fresh_reachability_runner_preflight_passed"
        or report.next_permitted_stage != preflight.NEXT_STAGE
        or report.provider_calls
        or report.stage_two_provider_calls
        or report.state_mapping_rows
        or frozen_input.audit_id != EXPECTED_FROZEN_INPUT_ID
        or frozen_input.frozen_population_id != report.source_population_id
        or frozen_input.model_exposure_count_before_preflight
        or frozen_input.fresh_source_reselection_count
        or tasks.catalog_id != EXPECTED_TASK_CATALOG_ID
        or paths.catalog_id != EXPECTED_PATH_CATALOG_ID
        or support.audit_id != EXPECTED_SUPPORT_CLOSURE_ID
        or detours.audit_id != EXPECTED_DETOUR_QUALIFICATION_ID
        or resource.contract_id != EXPECTED_RESOURCE_CONTRACT_ID
        or resource.detour_qualification_audit_id != detours.audit_id
        or execution.contract_id != EXPECTED_EXECUTION_CONTRACT_ID
        or manifest.manifest_id != EXPECTED_MANIFEST_ID
        or outcome.contract_id != EXPECTED_OUTCOME_CONTRACT_ID
        or runner.contract_id != EXPECTED_RUNNER_CONTRACT_ID
        or joint.contract_id != preflight.EXPECTED_JOINT_CONTRACT_ID
        or runner.qualified_final_grammar_id != grammar.grammar_id
        or transition.contract_id != EXPECTED_TRANSITION_ID
        or transition.next_permitted_stage != preflight.NEXT_STAGE
        or not transition.exact_fresh_360_job_execution_authorized
        or transition.state_mapping_contract_or_rows_authorized
        or len(manifest.jobs) != 360
        or len({item.job_id for item in manifest.jobs}) != 360
        or len({item.seed for item in manifest.jobs}) != 360
        or len({item.task_package_id for item in manifest.jobs}) != 12
        or modes
        != Counter(
            {
                "reachability_unconditional": 144,
                "reachability_conditioned": 216,
            }
        )
        or len(conditioned_paths) != 36
        or None in conditioned_paths
        or manifest.prospective_execution_run_id != RUN_ID
        or runner.execution_run_id != RUN_ID
        or runner.stage_two_provider_call_upper_bound
        or not runner.reachability_identity_or_route_present
        or outcome.measurement_gate
        != (
            "complete_raw_360_of_360",
            "model_endpoint_360_of_360",
            "measurement_support_exit_zero",
            "instrument_failure_zero",
            "privacy_failure_zero",
            "exact_model_thinking_usage_failure_zero",
            "typed_budget_no_call_zero",
            "unresolved_transport_failure_zero",
        )
        or not outcome.static_route_condition_not_accepted_as_empirical_state
        or not outcome.state_mapping_eligibility_requires_qualified_valid_true
        or outcome.state_mapping_rows
        or noninterference_contract.contract_id != EXPECTED_NONINTERFERENCE_CONTRACT_ID
    ):
        raise ValueError("v26.154 exact online authorization changed")

    frozen: tuple[tuple[str, Any], ...] = (
        ("preexecution_binding_audit.json", preexecution),
        ("frozen_v26_153_report.json", report),
        ("frozen_reachability_input_audit.json", frozen_input),
        ("frozen_reachability_task_package_catalog.json", tasks),
        ("frozen_reachability_path_catalog.json", paths),
        ("frozen_support_closure_audit.json", support),
        ("frozen_detour_qualification_audit.json", detours),
        ("frozen_reachability_resource_contract.json", resource),
        ("frozen_reachability_execution_contract.json", execution),
        ("frozen_reachability_manifest.json", manifest),
        ("frozen_reachability_outcome_contract.json", outcome),
        ("frozen_reachability_runner_contract.json", runner),
        ("frozen_joint_support_validity_contract.json", joint),
        ("frozen_qualified_final_response_grammar.json", grammar),
        ("frozen_preflight_transition_contract.json", transition),
        ("frozen_responsibility_noninterference_contract.json", noninterference_contract),
    )
    for name, value in frozen:
        _write_json_atomic(output_dir / name, value)

    return PreparedExecution(
        source_replay=source,
        preflight_report=report,
        frozen_input=frozen_input,
        tasks=tasks,
        paths=paths,
        support_closure=support,
        detour_qualification=detours,
        resource=resource,
        execution_contract=execution,
        manifest=manifest,
        outcome_contract=outcome,
        runner_contract=runner,
        joint_contract=joint,
        grammar=grammar,
        transition=transition,
        preexecution_binding=preexecution,
        role_inputs=role_inputs,
        replay_contract=replay_contract,
    )


def _package_for_job(
    prepared: PreparedExecution,
    job: preflight.FreshReachabilityJob,
) -> preflight.FreshReachabilityTaskPackage:
    package = next(
        (item for item in prepared.tasks.packages if item.task_package_id == job.task_package_id),
        None,
    )
    if (
        package is None
        or package.source_task_artifact_id != job.source_task_artifact_id
        or package.mechanism_id != job.mechanism_id
        or package.tier != job.tier
    ):
        raise ValueError("v26.154 Job is detached from its TaskPackage")
    return package


def _path_for_job(
    prepared: PreparedExecution,
    job: preflight.FreshReachabilityJob,
) -> preflight.FreshReachabilityPath | None:
    if job.sampling_mode == "reachability_unconditional":
        if any(
            item is not None
            for item in (
                job.requested_path_id,
                job.requested_path_strategy,
                job.public_path_condition,
                job.public_condition_id,
            )
        ):
            raise ValueError("v26.154 unconditional Job carries a route condition")
        return None
    path = next(
        (item for item in prepared.paths.paths if item.path_id == job.requested_path_id),
        None,
    )
    if (
        path is None
        or path.task_package_id != job.task_package_id
        or path.source_task_artifact_id != job.source_task_artifact_id
        or path.path_strategy_id != job.requested_path_strategy
        or path.public_path_condition != job.public_path_condition
        or path.public_condition_id != job.public_condition_id
    ):
        raise ValueError("v26.154 conditioned Job crossed its frozen Path")
    return path


def _runtime_binding_for_job(
    *,
    prepared: PreparedExecution,
    package: preflight.FreshReachabilityTaskPackage,
    job: preflight.FreshReachabilityJob,
) -> runner_vnext.FreshReachabilityRuntimeBinding:
    path = _path_for_job(prepared, job)
    return preflight._runtime_binding(  # noqa: SLF001
        package,
        prepared.frozen_input.audit_id,
        path_strategy_id=("unconditional" if path is None else path.path_strategy_id),
        public_path_condition=(None if path is None else path.public_path_condition),
    )


def _provider_pairs(
    raw: runner_vnext.FreshReachabilityRawExecution,
    output_dir: Path,
) -> tuple[
    tuple[
        privacy_runner.PrivacyFirstProviderEnvelope,
        privacy_runner.PublicPayloadProjection,
    ],
    ...,
]:
    envelopes: list[privacy_runner.PrivacyFirstProviderEnvelope] = []
    projections: list[privacy_runner.PublicPayloadProjection] = []
    for descriptor in raw.provider_envelope_artifacts:
        path = output_dir / descriptor.relative_path
        if (
            not path.is_file()
            or _sha256(path) != descriptor.sha256
            or path.stat().st_size != descriptor.byte_count
        ):
            raise ValueError("v26.154 Provider Envelope binding changed")
        envelopes.append(privacy_runner.PrivacyFirstProviderEnvelope.model_validate(_load(path)))
    for descriptor in raw.public_payload_projection_artifacts:
        path = output_dir / descriptor.relative_path
        if (
            not path.is_file()
            or _sha256(path) != descriptor.sha256
            or path.stat().st_size != descriptor.byte_count
        ):
            raise ValueError("v26.154 public Projection binding changed")
        projections.append(privacy_runner.PublicPayloadProjection.model_validate(_load(path)))
    pairs = tuple(zip(envelopes, projections, strict=True))
    for envelope, projection in pairs:
        privacy_runner.validate_provider_artifact_pair(envelope, projection)
    return pairs


def _endpoint_observed(raw: runner_vnext.FreshReachabilityRawExecution) -> bool:
    if raw.terminal_disposition in {
        "measurement_support_exit",
        "typed_budget_no_call",
        "provider_transport_failure",
        "instrument_failure",
    }:
        return False
    if raw.terminal_disposition == "privacy_rejection":
        return True
    return True


def _support_decision(
    raw: runner_vnext.FreshReachabilityRawExecution,
    package: preflight.FreshReachabilityTaskPackage,
) -> tuple[
    MeasurementSupportDecision,
    Literal["raw_last", "typed_detour_limit_exit", "endpoint_no_public_commit"],
]:
    if raw.measurement_support_decisions:
        decision = raw.measurement_support_decisions[-1]
        if (
            raw.terminal_disposition == "measurement_support_exit"
            and decision.status != "unavailable"
        ):
            event = make_measurement_support_event(
                event_kind="public_observation",
                public_state_id_before=decision.public_state_id,
                public_state_id_after=canonical_hash(
                    {"decision_id": decision.decision_id, "terminal": raw.terminal_disposition},
                    prefix="finance_v26_detour_limit_support_exit_state:",
                ),
                progress_vector_id_before=decision.progress_vector_id,
                progress_vector_id_after=decision.progress_vector_id,
                selected_action_id=decision.selected_action_id,
                observation_status="succeeded",
            )
            typed = classify_measurement_support(
                event,
                baseline_resolver=lambda: make_baseline_resolution(
                    status="unavailable",
                    public_state_id=event.public_state_id_before,
                    progress_vector_id=event.progress_vector_id_before,
                    reason_code=raw.terminal_failure_type or "ordinary_detour_allowance_exhausted",
                ),
            )
            return typed, "typed_detour_limit_exit"
        return decision, "raw_last"
    state = build_semantic_action_state(
        package.operational_record.task_package.task.public,
        package.environment,
        (),
    )
    return (
        classify_non_observation_support(
            event_kind="non_public_commit",
            state=state,
            selected_action_id=None,
        ),
        "endpoint_no_public_commit",
    )


def _prompt_payload_sensitive_count(prompt: str, *, action: bool) -> int:
    if action:
        payload = preflight.prompt_base._privacy_safe_prompt_payload(  # noqa: SLF001
            prompt
        ).model_dump(mode="json")
    else:
        payload = runner_vnext._qualified_final_prompt_payload(prompt)  # noqa: SLF001
    return len(preflight.prompt_base._sensitive_key_paths(payload))  # noqa: SLF001


def _online_noninterference(
    *,
    raw: runner_vnext.FreshReachabilityRawExecution,
    package: preflight.FreshReachabilityTaskPackage,
    job: preflight.FreshReachabilityJob,
    prepared: PreparedExecution,
) -> OnlineNoninterferenceAudit:
    attempts_by_index: dict[int, list[Any]] = defaultdict(list)
    for attempt in raw.attempts:
        attempts_by_index[attempt.logical_request_index].append(attempt)
    choices = {item.logical_request_index: item for item in raw.semantic_choices}
    commits = {item.commit.commit_id: item for item in raw.commits}
    rejection_by_id = {item.rejection_id: item for item in raw.semantic_rejections}

    observations: list[Any] = []
    rejections: list[Any] = []
    matched = 0
    sensitive = 0
    final_state = None
    final_commit = None
    binding = _runtime_binding_for_job(
        prepared=prepared,
        package=package,
        job=job,
    )

    for logical_index in sorted(attempts_by_index):
        group = attempts_by_index[logical_index]
        if group[0].request_kind != "semantic_proposal":
            continue
        state = build_semantic_action_state(
            package.operational_record.task_package.task.public,
            package.environment,
            tuple(observations),
            semantic_rejections=tuple(rejections),
        )
        phase: Literal["primary", "semantic_recovery"] = (
            "semantic_recovery"
            if group[0].public_attempt_phase == "semantic_recovery"
            else "primary"
        )
        typed_failure = None
        if phase == "semantic_recovery":
            if not rejections:
                raise ValueError("v26.154 Semantic Recovery Prompt lacks a public rejection")
            rejection = rejections[-1]
            typed_failure = {
                "family": "semantic_action_rejection",
                "subtype": rejection.error_category,
                "rejection_id": rejection.rejection_id,
            }
        salt = runner_vnext._presentation_salt(  # noqa: SLF001
            binding=binding,
            state=state,
            logical_index=logical_index,
        )
        primary = preflight.prompt_base.render_privacy_safe_s1_action_prompt(
            phase=phase,
            instruction=package.operational_record.task_package.task.public.instruction,
            state=state,
            public_path_condition=job.public_path_condition,
            presentation_salt=salt,
            typed_failure=typed_failure,
            grammar=prepared.role_inputs.static.action_grammar,
        )
        for position, attempt in enumerate(group):
            expected = primary
            if attempt.public_attempt_phase == "abi_rescue":
                initial = group[0]
                expected = preflight.prompt_base.render_privacy_safe_s1_action_prompt(
                    phase="abi_rescue",
                    instruction=package.operational_record.task_package.task.public.instruction,
                    state=state,
                    public_path_condition=job.public_path_condition,
                    presentation_salt=salt,
                    typed_failure={
                        "family": initial.failure_family or "channel_parse_failure",
                        "subtype": (
                            initial.failure_subtype
                            or initial.completion_failure_type
                            or "completion_failure"
                        ),
                    },
                    grammar=prepared.role_inputs.static.action_grammar,
                )
            if (
                legacy.sha256_text(expected) != attempt.prompt_sha256
                or len(expected.encode("utf-8")) != attempt.prompt_utf8_bytes
            ):
                raise ValueError("v26.154 reached Action Prompt hash changed")
            matched += 1
            sensitive += _prompt_payload_sensitive_count(expected, action=True)
            if position > 1:
                raise ValueError("v26.154 Action request exceeded one ABI Rescue")

        choice = choices.get(logical_index)
        if choice is None:
            continue
        if choice.observation_status is not None:
            observation = raw.observations[len(observations)]
            if observation.status != choice.observation_status:
                raise ValueError("v26.154 Choice Observation binding changed")
            observations.append(observation)
        if choice.rejection_id is not None:
            rejection = rejection_by_id.get(choice.rejection_id)
            if rejection is None:
                raise ValueError("v26.154 Choice rejection binding changed")
            rejections.append(rejection)
        if choice.commit_id is not None:
            commit_record = commits.get(choice.commit_id)
            if commit_record is None:
                raise ValueError("v26.154 Choice Commit binding changed")
            if commit_record.commit.action == "emit_final":
                final_state = state
                final_commit = commit_record.commit

    final_groups = [
        (index, group)
        for index, group in sorted(attempts_by_index.items())
        if group[0].request_kind == "final_answer"
    ]
    if final_groups:
        if final_state is None or final_commit is None:
            raise ValueError("v26.154 Final Prompt lacks its model-selected Commit")
        compact = render_compact_final_prompt(
            package.prompt_contract.public_context,
            package.operational_record.task_package.task.public,
            tuple(observations),
            public_path_condition=job.public_path_condition,
        )
        primary = runner_vnext.render_qualified_final_primary_prompt(
            compact,
            grammar=prepared.grammar,
        )
        envelope = make_qualified_final_host_envelope(
            terminal_state_id=final_state.state_id,
            terminal_commit_id=final_commit.commit_id,
            grammar=prepared.grammar,
        )
        for _, group in final_groups:
            for position, attempt in enumerate(group):
                expected = primary
                if attempt.public_attempt_phase == "abi_rescue":
                    initial = group[0]
                    expected = runner_vnext.render_qualified_final_rescue_prompt(
                        primary,
                        failure_family=initial.failure_family or "channel_parse_failure",
                        failure_subtype=(
                            initial.failure_subtype
                            or initial.completion_failure_type
                            or "completion_failure"
                        ),
                    )
                if (
                    legacy.sha256_text(expected) != attempt.prompt_sha256
                    or len(expected.encode("utf-8")) != attempt.prompt_utf8_bytes
                    or attempt.final_response_host_envelope_id != envelope.envelope_id
                ):
                    raise ValueError("v26.154 reached Final Prompt or Host Envelope changed")
                matched += 1
                sensitive += _prompt_payload_sensitive_count(expected, action=False)
                if position > 1:
                    raise ValueError("v26.154 Final request exceeded one ABI Rescue")

    if matched != len(raw.attempts) or sensitive:
        raise ValueError("v26.154 online Prompt noninterference failed")
    values = {
        "qualified_final_grammar_id": prepared.grammar.grammar_id,
        "task_package_id": package.task_package_id,
        "job_id": raw.job_id,
        "reached_prompt_count": len(raw.attempts),
        "prompt_hash_match_count": matched,
    }
    provisional = OnlineNoninterferenceAudit.model_construct(audit_id="pending", **values)
    return OnlineNoninterferenceAudit(
        audit_id=_identity(
            provisional,
            "audit_id",
            "finance_v26_fresh_reachability_online_noninterference:",
        ),
        **values,
    )


def _decimal_field_paths(expected: Mapping[str, Any]) -> tuple[tuple[str, ...], ...]:
    paths: list[tuple[str, ...]] = []
    for key, value in expected.items():
        if isinstance(value, bool) or value is None:
            continue
        try:
            number = Decimal(str(value))
        except (InvalidOperation, TypeError, ValueError):
            continue
        if number.is_finite():
            paths.append((str(key),))
    return tuple(sorted(paths))


def _replace_runtime_references(value: Any, mapping: Mapping[str, str]) -> Any:
    if isinstance(value, str):
        return mapping.get(value, value)
    if isinstance(value, Mapping):
        return {str(key): _replace_runtime_references(item, mapping) for key, item in value.items()}
    if isinstance(value, list):
        return [_replace_runtime_references(item, mapping) for item in value]
    return value


def _project_answer(value: Mapping[str, Any], projection: Mapping[str, str]) -> dict[str, Any]:
    output = dict(value)
    for field in ("higher_ref", "selected_ref"):
        reference = output.get(field)
        if reference is not None and str(reference) in projection:
            output[field] = projection[str(reference)]
    return output


def _verification_support_ids(observations: Sequence[Any]) -> tuple[str, ...]:
    return tuple(
        sorted(
            {
                str(evidence_id)
                for item in observations
                if item.call.tool_id == "cross_check_evidence"
                and item.status == "succeeded"
                and item.result.get("verified") is True
                for evidence_id in item.result.get("support") or ()
            }
        )
    )


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


def _call_signature(observation: Any) -> str:
    return canonical_hash(
        {
            "tool_id": observation.call.tool_id,
            "arguments": observation.call.arguments,
        },
        prefix="finance_v26_fresh_reachability_mechanism_action:",
    )


def _mechanism_events(
    *,
    mechanism_id: MechanismId,
    record: Any,
    observations: Sequence[Any],
    completed: bool,
) -> tuple[str, ...]:
    successful = lambda tool: tuple(  # noqa: E731
        item for item in observations if item.call.tool_id == tool and item.status == "succeeded"
    )
    if mechanism_id == "context_conditioned_action":
        calculators = successful("calculator")
        private = record.mechanism_private_state
        expected = str(private.get("expected_first_action"))
        baseline = str(private.get("alternate_action"))
        actual = str(calculators[0].call.arguments.get("operator")) if calculators else baseline
        conditioned = actual if actual == expected else baseline
        return qualify_context_mechanism(
            ContextMechanismEvidence(
                frozen_context_pair_id=record.task_package.mechanism_contract.contract_id,
                baseline_action_id=baseline,
                conditioned_action_id=conditioned,
            )
        )

    if mechanism_id == "semantic_reconciliation":
        target = tuple(
            sorted(str(item) for item in record.mechanism_private_state["target_evidence_ids"])
        )
        normalized_by_reference: dict[str, str] = {}
        for item in successful("normalize_metric_unit_period"):
            reference = item.result.get("normalized_operation_ref")
            rows = item.result.get("normalized_values")
            if not reference or not isinstance(rows, list):
                continue
            evidence = {
                str(row["evidence_id"])
                for row in rows
                if isinstance(row, Mapping) and row.get("evidence_id")
            }
            if len(evidence) == 1:
                normalized_by_reference[str(reference)] = next(iter(evidence))
        consumed_references = {
            str(operand.get("operation_ref"))
            for item in successful("calculator")
            for operand in item.call.arguments.get("operands", ())
            if isinstance(operand, Mapping) and operand.get("operation_ref")
        }
        normalized = tuple(sorted(set(normalized_by_reference.values()) & set(target)))
        consumed = tuple(
            sorted(
                {
                    evidence
                    for reference, evidence in normalized_by_reference.items()
                    if reference in consumed_references and evidence in set(target)
                }
            )
        )
        extra = tuple(sorted(set(normalized_by_reference.values()) - set(target)))
        return qualify_reconciliation_mechanism(
            ReconciliationMechanismEvidence(
                target_evidence_ids=target,
                normalized_target_evidence_ids=normalized,
                consumed_normalization_evidence_ids=consumed,
                extra_legal_normalized_evidence_ids=extra,
            )
        )

    if mechanism_id == "failure_recovery":
        failures = tuple(
            (index, item)
            for index, item in enumerate(observations)
            if item.call.tool_id == "query_structured_fact"
            and item.status == "failed"
            and item.error_code == "typed_selector_requires_refinement"
        )
        failure_index = failures[0][0] if failures else None
        failed_signature = _call_signature(failures[0][1]) if failures else None
        revised_index = None
        revised_signature = None
        if failures:
            failure_index_value = failures[0][0]
            for index, item in enumerate(
                observations[failure_index_value + 1 :], failure_index_value + 1
            ):
                signature = _call_signature(item)
                if item.call.tool_id == "query_structured_fact" and signature != failed_signature:
                    revised_index = index
                    revised_signature = signature
                    break
        later_success = None
        if revised_index is not None:
            later_success = next(
                (
                    index
                    for index, item in enumerate(
                        observations[revised_index + 1 :], revised_index + 1
                    )
                    if item.status == "succeeded"
                ),
                None,
            )
        return qualify_recovery_mechanism(
            RecoveryMechanismEvidence(
                typed_failure_observation_index=failure_index,
                revised_action_observation_index=revised_index,
                later_success_observation_index=later_success,
                failed_action_signature=failed_signature,
                revised_action_signature=revised_signature,
            )
        )

    verified_indices = tuple(
        index
        for index, item in enumerate(observations)
        if item.call.tool_id == "cross_check_evidence"
        and item.status == "succeeded"
        and item.result.get("verified") is True
    )
    violation = _postcompletion_violation(observations)
    return qualify_stopping_mechanism(
        StoppingMechanismEvidence(
            completion_verified=bool(verified_indices),
            stopped_after_completion=bool(
                completed and verified_indices and verified_indices[-1] == len(observations) - 1
            ),
            postcompletion_violation=violation,
            stopping_failure_causal_group_id=f"{record.record_id}:stopping",
        )
    )


def _program_progress(record: Any, observations: Sequence[Any]) -> tuple[bool, bool]:
    _, _, program_closed, terminal_completed, verified = semantic_online._progress_diagnostic(  # noqa: SLF001
        record, observations
    )
    return bool(program_closed and terminal_completed), bool(verified)


def _base_inputs(
    *,
    raw: runner_vnext.FreshReachabilityRawExecution,
    package: preflight.FreshReachabilityTaskPackage,
    replay: AuthorityPreservingReplayResult,
    noninterference: OnlineNoninterferenceAudit,
) -> tuple[BaseValidityChecks, AnswerSemanticComparison]:
    record = package.operational_record
    observations = raw.observations
    program_complete, _, runtime_to_node, operation_lineage = match_empirical_program(
        record, observations
    )
    expected = cast(dict[str, Any], record.projected_expected_output)
    observed_result: Mapping[str, Any] | None = None
    model_citations: tuple[str, ...] = ()
    if raw.completed_result is not None:
        observed_result = raw.completed_result.final_payload.answer.result
        model_citations = tuple(
            sorted(
                {item.evidence_id for item in raw.completed_result.final_payload.answer.citations}
            )
        )
    normalized = (
        _project_answer(
            cast(
                Mapping[str, Any],
                _replace_runtime_references(observed_result, runtime_to_node),
            ),
            record.answer_projection,
        )
        if observed_result is not None
        else None
    )
    schema = make_answer_semantic_schema(
        required_result_fields=tuple(expected),
        decimal_field_paths=_decimal_field_paths(expected),
    )
    comparison = compare_answer_by_schema(normalized, expected, schema)

    lattice = record.task_package.evidence_support_lattice
    necessary = set(lattice.necessary_evidence_ids)
    selected = tuple(sorted(replay.selected_evidence_ids))
    selected_support = matching_sufficient_support_set(lattice, selected)
    citation_support = matching_sufficient_support_set(lattice, model_citations)
    verification_support = _verification_support_ids(observations)
    program_closed, terminal_verified = _program_progress(record, observations)
    checks = BaseValidityChecks(
        action_abi_complete=raw.first_action_interface_qualified,
        program_closed=program_closed,
        operation_lineage_complete=bool(program_complete and necessary <= set(operation_lineage)),
        required_evidence_support_complete=necessary <= set(selected),
        runtime_selected_support_complete=selected_support is not None,
        model_citation_complete=citation_support is not None,
        terminal_verification_complete=terminal_verified,
        final_abi_complete=bool(
            raw.completed_result is not None and raw.exact_qualified_final_payload_count == 1
        ),
        answer_schema_complete=comparison.answer_schema_match,
        answer_canonical_semantic_match=comparison.answer_canonical_semantic_match,
        reference_identity_match=comparison.reference_identity_match,
        verification_support_complete=necessary <= set(verification_support),
        no_postcompletion_violation=not _postcompletion_violation(observations),
        noninterference_artifact_bound=noninterference.passed,
    )
    return checks, comparison


def project_measurement_result(
    *,
    raw: runner_vnext.FreshReachabilityRawExecution,
    job: preflight.FreshReachabilityJob,
    package: preflight.FreshReachabilityTaskPackage,
    prepared: PreparedExecution,
    output_dir: Path,
) -> ReachabilityMeasurementResult:
    if raw.job_id != job.job_id or raw.job_payload != job.model_dump(mode="json"):
        raise ValueError("v26.154 Raw execution crossed its Job identity")
    _path_for_job(prepared, job)
    pairs = _provider_pairs(raw, output_dir)
    projection_counts = Counter(item.projection_status for _, item in pairs)
    exact_model, fallback_absent, native_absent, thinking, usage = semantic_online._telemetry_flags(
        raw.provider_telemetry
    )  # noqa: SLF001
    dynamic = all(
        item.dynamic_certificate_id is not None and item.resource_certificate_id is not None
        for item in raw.attempts
        if item.provider_call_made
    )
    exact_request = all(
        item.request_binding_certificate_id is not None
        for item in raw.attempts
        if item.provider_call_made
    )
    pairing = bool(
        len(pairs)
        == len(raw.provider_envelope_artifacts)
        == len(raw.public_payload_projection_artifacts)
        == raw.stage_one_provider_call_count
    )
    reversible = all(
        item.reversible_same_action_id_passed
        and not item.semantic_choice_inserted_by_host
        and item.stage_two_provider_calls == 0
        for item in raw.commits
    )
    resource_passed = bool(
        raw.cumulative_provider_tokens <= prepared.resource.rollout_upper_bound_tokens
        and raw.stage_one_provider_call_count <= prepared.resource.maximum_stage_one_provider_calls
        and raw.transport_inclusive_invocation_count
        <= prepared.resource.maximum_transport_inclusive_invocations
        and raw.ordinary_detour_count <= prepared.runner_contract.maximum_ordinary_detours
    )
    privacy_compliant = bool(
        raw.privacy_compliant
        and raw.privacy_rejected_payload_count == 0
        and projection_counts["privacy_rejected"] == 0
        and pairing
    )
    model_endpoint = _endpoint_observed(raw)
    support_available = bool(
        raw.measurement_support_available
        and raw.terminal_disposition != "measurement_support_exit"
        and all(item.status != "unavailable" for item in raw.measurement_support_decisions)
    )
    preliminary_instrument = bool(
        raw.instrument_integrity
        and raw.terminal_disposition != "instrument_failure"
        and exact_model
        and fallback_absent
        and native_absent
        and thinking
        and usage
        and dynamic
        and exact_request
        and pairing
        and reversible
        and resource_passed
        and raw.stage_two_provider_call_count == 0
    )

    prompt_audit: OnlineNoninterferenceAudit | None = None
    replay: AuthorityPreservingReplayResult | None = None
    precheck_failures: list[str] = []
    if support_available and model_endpoint and preliminary_instrument and privacy_compliant:
        try:
            prompt_audit = _online_noninterference(
                raw=raw,
                package=package,
                job=job,
                prepared=prepared,
            )
        except Exception as error:
            precheck_failures.append(f"online_noninterference:{type(error).__name__}")
        try:
            candidate_replay = replay_authority_preserving_observations(
                prepared.replay_contract,
                package.operational_record,
                package.environment,
                raw.observations,
            )
            if candidate_replay.passed:
                replay = candidate_replay
            else:
                precheck_failures.extend(candidate_replay.failure_ids)
        except Exception as error:
            precheck_failures.append(f"runtime_replay:{type(error).__name__}")

    instrument = preliminary_instrument and not precheck_failures
    evaluable = bool(support_available and model_endpoint and instrument and privacy_compliant)
    if not evaluable:
        prompt_audit = None
        replay = None

    support_decision, support_source = _support_decision(raw, package)
    base_checks: BaseValidityChecks | None = None
    comparison: AnswerSemanticComparison | None = None
    binding = None
    observed_events: tuple[str, ...] = ()
    program_closed, terminal_verified = _program_progress(
        package.operational_record, raw.observations
    )
    if evaluable:
        if prompt_audit is None or replay is None:
            raise ValueError("v26.154 evaluable endpoint lacks verifier prerequisites")
        base_checks, comparison = _base_inputs(
            raw=raw,
            package=package,
            replay=replay,
            noninterference=prompt_audit,
        )
        binding = make_noninterference_artifact_binding(
            noninterference_contract_id=EXPECTED_NONINTERFERENCE_CONTRACT_ID,
            noninterference_audit_id=prompt_audit.audit_id,
            task_package_id=package.task_package_id,
        )
        observed_events = _mechanism_events(
            mechanism_id=package.mechanism_id,
            record=package.operational_record,
            observations=raw.observations,
            completed=raw.completed_result is not None,
        )

    joint = evaluate_joint_support_validity(
        contract=prepared.joint_contract,
        support_decision=support_decision,
        trajectory_id=raw.artifact_id,
        task_package_id=package.task_package_id,
        model_endpoint_observed=model_endpoint,
        instrument_integrity=instrument,
        privacy_compliant=privacy_compliant,
        mechanism_id=package.mechanism_id,
        base_checks=base_checks,
        noninterference_binding=binding,
        observed_mechanism_event_ids=observed_events,
    )

    gate_failures: list[str] = []
    if not support_available:
        gate_failures.append("measurement_support_exit")
    if not model_endpoint:
        gate_failures.append("model_endpoint_unobserved")
    if not instrument:
        gate_failures.append("instrument_failure")
    if not privacy_compliant:
        gate_failures.append("privacy_failure")
    if not (exact_model and thinking and usage):
        gate_failures.append("exact_model_thinking_usage_failure")
    if raw.terminal_disposition == "typed_budget_no_call":
        gate_failures.append("typed_budget_no_call")
    if raw.terminal_disposition == "provider_transport_failure":
        gate_failures.append("unresolved_transport_failure")

    cost = sum(
        (
            Decimal(str(item.estimated_cost))
            for item in raw.provider_telemetry
            if item.estimated_cost is not None
        ),
        Decimal("0"),
    )
    values: dict[str, Any] = {
        "job_id": job.job_id,
        "task_package_id": job.task_package_id,
        "source_task_artifact_id": job.source_task_artifact_id,
        "mechanism_id": job.mechanism_id,
        "tier": job.tier,
        "sampling_mode": job.sampling_mode,
        "requested_path_id": job.requested_path_id,
        "requested_path_strategy": job.requested_path_strategy,
        "public_path_condition": job.public_path_condition,
        "public_condition_id": job.public_condition_id,
        "condition_binding_valid": True,
        "replicate_index": job.replicate_index,
        "seed": job.seed,
        "raw_execution_id": raw.artifact_id,
        "raw_execution_artifact": _descriptor(
            runner_vnext._raw_path(output_dir, job),  # noqa: SLF001
            output_dir,
        ),
        "raw_terminal_disposition": raw.terminal_disposition,
        "terminal_failure_type": raw.terminal_failure_type,
        "execution_error": raw.execution_error,
        "measurement_support_available": support_available,
        "model_endpoint_observed": model_endpoint,
        "instrument_integrity": instrument,
        "privacy_compliant": privacy_compliant,
        "validity_evaluable": evaluable,
        "endpoint_projection_matches_raw": model_endpoint == raw.model_endpoint_observed,
        "support_decision_source": support_source,
        "support_decision": support_decision,
        "joint_result": joint,
        "online_noninterference_audit": prompt_audit,
        "runtime_replay": replay,
        "answer_comparison": comparison,
        "base_trajectory_validity": joint.base_report.valid,
        "mechanism_qualification": joint.mechanism_report.success,
        "qualified_trajectory_validity": joint.qualified_report.valid,
        "state_mapping_eligible": joint.state_mapping_eligible,
        "task_verifier_invocation_count": joint.task_verifier_invocation_count,
        "observed_mechanism_event_ids": observed_events,
        "first_action_interface_qualified": raw.first_action_interface_qualified,
        "program_closed": program_closed,
        "terminal_verification_complete": terminal_verified,
        "exact_qualified_final_payload_count": raw.exact_qualified_final_payload_count,
        "provider_call_count": raw.stage_one_provider_call_count,
        "transport_inclusive_invocation_count": raw.transport_inclusive_invocation_count,
        "provider_prompt_tokens": sum(item.prompt_tokens or 0 for item in raw.provider_telemetry),
        "provider_completion_tokens": sum(
            item.completion_tokens or 0 for item in raw.provider_telemetry
        ),
        "provider_reasoning_tokens": sum(
            item.reasoning_tokens or 0 for item in raw.provider_telemetry
        ),
        "provider_total_tokens": sum(item.total_tokens or 0 for item in raw.provider_telemetry),
        "estimated_cost_usd": format(cost, "f"),
        "exact_model_passed": exact_model,
        "fallback_absent": fallback_absent,
        "provider_native_tool_absent": native_absent,
        "thinking_continuity_passed": thinking,
        "provider_usage_complete": usage,
        "dynamic_precall_binding_passed": dynamic,
        "exact_request_binding_passed": exact_request,
        "privacy_artifact_pairing_passed": pairing,
        "reversible_commit_integrity_passed": reversible,
        "rollout_budget_passed": resource_passed,
        "unresolved_transport_failure": (raw.terminal_disposition == "provider_transport_failure"),
        "typed_budget_no_call": raw.terminal_disposition == "typed_budget_no_call",
        "measurement_gate_failure_ids": tuple(sorted(set(gate_failures))),
    }
    provisional = ReachabilityMeasurementResult.model_construct(result_id="pending", **values)
    return ReachabilityMeasurementResult(
        result_id=_identity(
            provisional,
            "result_id",
            "finance_v26_fresh_reachability_measurement_result:",
        ),
        **values,
    )


def _measurement_gate(
    results: Sequence[ReachabilityMeasurementResult],
    *,
    complete_raw_count: int,
) -> MeasurementGateAudit:
    values: dict[str, Any] = {
        "complete_raw_count": complete_raw_count,
        "model_endpoint_count": sum(item.model_endpoint_observed for item in results),
        "measurement_support_exit_count": sum(
            not item.measurement_support_available for item in results
        ),
        "instrument_failure_count": sum(not item.instrument_integrity for item in results),
        "privacy_failure_count": sum(not item.privacy_compliant for item in results),
        "exact_model_thinking_usage_failure_count": sum(
            not (
                item.exact_model_passed
                and item.thinking_continuity_passed
                and item.provider_usage_complete
            )
            for item in results
        ),
        "typed_budget_no_call_count": sum(item.typed_budget_no_call for item in results),
        "unresolved_transport_failure_count": sum(
            item.unresolved_transport_failure for item in results
        ),
    }
    checks = {
        "complete_raw_360_of_360": values["complete_raw_count"] == 360,
        "model_endpoint_360_of_360": values["model_endpoint_count"] == 360,
        "measurement_support_exit_zero": values["measurement_support_exit_count"] == 0,
        "instrument_failure_zero": values["instrument_failure_count"] == 0,
        "privacy_failure_zero": values["privacy_failure_count"] == 0,
        "exact_model_thinking_usage_failure_zero": (
            values["exact_model_thinking_usage_failure_count"] == 0
        ),
        "typed_budget_no_call_zero": values["typed_budget_no_call_count"] == 0,
        "unresolved_transport_failure_zero": (values["unresolved_transport_failure_count"] == 0),
    }
    passed = all(checks.values())
    values.update(
        {
            "failure_ids": tuple(sorted(key for key, value in checks.items() if not value)),
            "passed": passed,
            "reachability_estimands_authorized": passed,
            "state_mapping_eligibility_estimand_authorized": passed,
        }
    )
    provisional = MeasurementGateAudit.model_construct(audit_id="pending", **values)
    return MeasurementGateAudit(
        audit_id=_identity(
            provisional,
            "audit_id",
            "finance_v26_fresh_reachability_measurement_gate:",
        ),
        **values,
    )


def _unconditional_task_summaries(
    results: Sequence[ReachabilityMeasurementResult],
    *,
    authorized: bool,
) -> tuple[UnconditionalTaskSummary, ...]:
    grouped: dict[str, list[ReachabilityMeasurementResult]] = defaultdict(list)
    for item in results:
        if item.sampling_mode == "reachability_unconditional":
            grouped[item.task_package_id].append(item)
    if len(grouped) != 12 or sum(map(len, grouped.values())) != 144:
        raise ValueError("v26.154 unconditional Task denominator changed")
    summaries: list[UnconditionalTaskSummary] = []
    for task_package_id in sorted(grouped):
        rows = grouped[task_package_id]
        if len(rows) != 12:
            raise ValueError("v26.154 unconditional Task lacks twelve replicas")
        first = rows[0]
        base = sum(item.base_trajectory_validity is True for item in rows)
        mechanism = sum(item.mechanism_qualification is True for item in rows)
        qualified = sum(item.qualified_trajectory_validity is True for item in rows)
        values: dict[str, Any] = {
            "task_package_id": task_package_id,
            "source_task_artifact_id": first.source_task_artifact_id,
            "mechanism_id": first.mechanism_id,
            "tier": first.tier,
            "model_endpoint_count": sum(item.model_endpoint_observed for item in rows),
            "evaluable_count": sum(item.validity_evaluable for item in rows),
            "base_valid_count": base,
            "mechanism_qualified_count": mechanism,
            "qualified_valid_count": qualified,
            "state_mapping_eligible_count": sum(item.state_mapping_eligible for item in rows),
            "base_fraction": f"{base}/12" if authorized else None,
            "mechanism_fraction": f"{mechanism}/12" if authorized else None,
            "qualified_fraction": f"{qualified}/12" if authorized else None,
            "terminal_counts": dict(
                sorted(Counter(item.raw_terminal_disposition for item in rows).items())
            ),
            "estimand_authorized": authorized,
        }
        provisional = UnconditionalTaskSummary.model_construct(summary_id="pending", **values)
        summaries.append(
            UnconditionalTaskSummary(
                summary_id=_identity(
                    provisional,
                    "summary_id",
                    "finance_v26_fresh_reachability_unconditional_task_estimand:",
                ),
                **values,
            )
        )
    return tuple(summaries)


def _conditioned_path_summaries(
    results: Sequence[ReachabilityMeasurementResult],
    *,
    authorized: bool,
) -> tuple[ConditionedPathSummary, ...]:
    grouped: dict[str, list[ReachabilityMeasurementResult]] = defaultdict(list)
    for item in results:
        if item.sampling_mode == "reachability_conditioned":
            grouped[cast(str, item.requested_path_id)].append(item)
    if len(grouped) != 36 or sum(map(len, grouped.values())) != 216:
        raise ValueError("v26.154 conditioned Path denominator changed")
    summaries: list[ConditionedPathSummary] = []
    for path_id in sorted(grouped):
        rows = grouped[path_id]
        if len(rows) != 6:
            raise ValueError("v26.154 conditioned Path lacks six replicas")
        first = rows[0]
        strategy = cast(preflight.PathStrategy, first.requested_path_strategy)
        condition = cast(str, first.public_path_condition)
        condition_id = cast(str, first.public_condition_id)
        if any(
            (
                item.requested_path_strategy,
                item.public_path_condition,
                item.public_condition_id,
            )
            != (strategy, condition, condition_id)
            for item in rows
        ):
            raise ValueError("v26.154 conditioned Path rows crossed route bindings")
        base = sum(item.base_trajectory_validity is True for item in rows)
        mechanism = sum(item.mechanism_qualification is True for item in rows)
        qualified = sum(item.qualified_trajectory_validity is True for item in rows)
        values: dict[str, Any] = {
            "path_id": path_id,
            "path_strategy_id": strategy,
            "public_path_condition": condition,
            "public_condition_id": condition_id,
            "task_package_id": first.task_package_id,
            "source_task_artifact_id": first.source_task_artifact_id,
            "mechanism_id": first.mechanism_id,
            "tier": first.tier,
            "model_endpoint_count": sum(item.model_endpoint_observed for item in rows),
            "evaluable_count": sum(item.validity_evaluable for item in rows),
            "base_valid_count": base,
            "mechanism_qualified_count": mechanism,
            "qualified_valid_count": qualified,
            "state_mapping_eligible_count": sum(item.state_mapping_eligible for item in rows),
            "base_fraction": f"{base}/6" if authorized else None,
            "mechanism_fraction": f"{mechanism}/6" if authorized else None,
            "qualified_fraction": f"{qualified}/6" if authorized else None,
            "terminal_counts": dict(
                sorted(Counter(item.raw_terminal_disposition for item in rows).items())
            ),
            "estimand_authorized": authorized,
        }
        provisional = ConditionedPathSummary.model_construct(summary_id="pending", **values)
        summaries.append(
            ConditionedPathSummary(
                summary_id=_identity(
                    provisional,
                    "summary_id",
                    "finance_v26_fresh_reachability_conditioned_path_estimand:",
                ),
                **values,
            )
        )
    return tuple(summaries)


SummaryCountField = Literal[
    "base_valid_count",
    "mechanism_qualified_count",
    "qualified_valid_count",
]


def _mean_primary_fraction(
    rows: Sequence[UnconditionalTaskSummary] | Sequence[ConditionedPathSummary],
    field: SummaryCountField,
    *,
    denominator: int,
) -> str:
    total = sum(Decimal(getattr(item, field)) / Decimal(denominator) for item in rows)
    return format(total / Decimal(len(rows)), "f")


def _mechanism_summaries(
    tasks: Sequence[UnconditionalTaskSummary],
    paths: Sequence[ConditionedPathSummary],
    *,
    authorized: bool,
) -> tuple[MechanismReachabilitySummary, ...]:
    task_groups: dict[MechanismId, list[UnconditionalTaskSummary]] = defaultdict(list)
    path_groups: dict[MechanismId, list[ConditionedPathSummary]] = defaultdict(list)
    for item in tasks:
        task_groups[item.mechanism_id].append(item)
    for item in paths:
        path_groups[item.mechanism_id].append(item)
    summaries: list[MechanismReachabilitySummary] = []
    for mechanism_id in sorted(task_groups):
        task_rows = task_groups[mechanism_id]
        path_rows = path_groups[mechanism_id]
        if len(task_rows) != 3 or len(path_rows) != 9:
            raise ValueError("v26.154 Mechanism Task/Path partition changed")
        values: dict[str, Any] = {
            "mechanism_id": mechanism_id,
            "unconditional_base_valid_count": sum(item.base_valid_count for item in task_rows),
            "unconditional_mechanism_qualified_count": sum(
                item.mechanism_qualified_count for item in task_rows
            ),
            "unconditional_qualified_valid_count": sum(
                item.qualified_valid_count for item in task_rows
            ),
            "conditioned_base_valid_count": sum(item.base_valid_count for item in path_rows),
            "conditioned_mechanism_qualified_count": sum(
                item.mechanism_qualified_count for item in path_rows
            ),
            "conditioned_qualified_valid_count": sum(
                item.qualified_valid_count for item in path_rows
            ),
            "tasks_with_unconditional_qualified_trajectory": sum(
                item.qualified_valid_count > 0 for item in task_rows
            ),
            "paths_with_conditioned_qualified_trajectory": sum(
                item.qualified_valid_count > 0 for item in path_rows
            ),
            "unconditional_task_weighted_qualified_fraction": (
                _mean_primary_fraction(
                    task_rows,
                    "qualified_valid_count",
                    denominator=12,
                )
                if authorized
                else None
            ),
            "conditioned_path_weighted_qualified_fraction": (
                _mean_primary_fraction(
                    path_rows,
                    "qualified_valid_count",
                    denominator=6,
                )
                if authorized
                else None
            ),
            "estimand_authorized": authorized,
        }
        provisional = MechanismReachabilitySummary.model_construct(
            summary_id="pending",
            **values,
        )
        summaries.append(
            MechanismReachabilitySummary(
                summary_id=_identity(
                    provisional,
                    "summary_id",
                    "finance_v26_fresh_reachability_mechanism_estimand:",
                ),
                **values,
            )
        )
    return tuple(summaries)


def _raw_lineage(
    *,
    prepared: PreparedExecution,
    results: Sequence[ReachabilityMeasurementResult],
    raws: Mapping[str, runner_vnext.FreshReachabilityRawExecution],
    output_dir: Path,
) -> RawLineageAudit:
    raw_descriptors = tuple(
        item.raw_execution_artifact for item in sorted(results, key=lambda row: row.job_id)
    )
    provider_descriptors = tuple(
        descriptor
        for job_id in sorted(raws)
        for descriptor in (
            *raws[job_id].provider_envelope_artifacts,
            *raws[job_id].public_payload_projection_artifacts,
            *raws[job_id].transport_invocation_artifacts,
        )
    )
    all_descriptors = (*raw_descriptors, *provider_descriptors)
    for descriptor in all_descriptors:
        path = output_dir / descriptor.relative_path
        if (
            not path.is_file()
            or _sha256(path) != descriptor.sha256
            or path.stat().st_size != descriptor.byte_count
        ):
            raise ValueError("v26.154 Raw Lineage byte replay changed")
    provider_calls = sum(item.stage_one_provider_call_count for item in raws.values())
    transport = sum(item.transport_inclusive_invocation_count for item in raws.values())
    values = {
        "provider_call_count": provider_calls,
        "transport_invocation_count": transport,
        "provider_envelope_count": sum(
            len(item.provider_envelope_artifacts) for item in raws.values()
        ),
        "public_projection_count": sum(
            len(item.public_payload_projection_artifacts) for item in raws.values()
        ),
        "complete_provider_pair_count": provider_calls,
        "raw_descriptors": raw_descriptors,
        "provider_artifact_descriptors": provider_descriptors,
        "exact_byte_replay_pass_count": len(all_descriptors),
    }
    provisional = RawLineageAudit.model_construct(audit_id="pending", **values)
    return RawLineageAudit(
        audit_id=_identity(
            provisional,
            "audit_id",
            "finance_v26_fresh_reachability_raw_lineage:",
        ),
        **values,
    )


def _execution_report(
    *,
    prepared: PreparedExecution,
    results: Sequence[ReachabilityMeasurementResult],
    lineage: RawLineageAudit,
    gate: MeasurementGateAudit,
) -> ReachabilityExecutionReport:
    tasks = _unconditional_task_summaries(results, authorized=gate.passed)
    paths = _conditioned_path_summaries(results, authorized=gate.passed)
    mechanisms = _mechanism_summaries(tasks, paths, authorized=gate.passed)
    unconditional = tuple(
        item for item in results if item.sampling_mode == "reachability_unconditional"
    )
    conditioned = tuple(
        item for item in results if item.sampling_mode == "reachability_conditioned"
    )
    if len(unconditional) != 144 or len(conditioned) != 216:
        raise ValueError("v26.154 report sampling partition changed")

    def count_true(
        rows: Sequence[ReachabilityMeasurementResult],
        field: Literal[
            "base_trajectory_validity",
            "mechanism_qualification",
            "qualified_trajectory_validity",
        ],
    ) -> int:
        return sum(getattr(item, field) is True for item in rows)

    unconditional_base = count_true(unconditional, "base_trajectory_validity")
    unconditional_mechanism = count_true(unconditional, "mechanism_qualification")
    unconditional_qualified = count_true(unconditional, "qualified_trajectory_validity")
    conditioned_base = count_true(conditioned, "base_trajectory_validity")
    conditioned_mechanism = count_true(conditioned, "mechanism_qualification")
    conditioned_qualified = count_true(conditioned, "qualified_trajectory_validity")
    estimated_cost = sum(
        (Decimal(item.estimated_cost_usd) for item in results),
        Decimal("0"),
    )
    values: dict[str, Any] = {
        "source_replay_audit_id": prepared.source_replay.audit_id,
        "preexecution_binding_audit_id": prepared.preexecution_binding.audit_id,
        "raw_lineage_audit_id": lineage.audit_id,
        "measurement_gate_audit_id": gate.audit_id,
        "terminal_counts": dict(
            sorted(Counter(item.raw_terminal_disposition for item in results).items())
        ),
        "measurement_gate_passed": gate.passed,
        "reachability_estimands_authorized": gate.reachability_estimands_authorized,
        "base_valid_count": unconditional_base + conditioned_base,
        "mechanism_qualified_count": unconditional_mechanism + conditioned_mechanism,
        "qualified_valid_count": unconditional_qualified + conditioned_qualified,
        "state_mapping_eligible_count": sum(item.state_mapping_eligible for item in results),
        "unconditional_base_valid_count": unconditional_base,
        "unconditional_mechanism_qualified_count": unconditional_mechanism,
        "unconditional_qualified_valid_count": unconditional_qualified,
        "conditioned_base_valid_count": conditioned_base,
        "conditioned_mechanism_qualified_count": conditioned_mechanism,
        "conditioned_qualified_valid_count": conditioned_qualified,
        "unconditional_task_weighted_base_fraction": (
            _mean_primary_fraction(tasks, "base_valid_count", denominator=12)
            if gate.passed
            else None
        ),
        "unconditional_task_weighted_mechanism_fraction": (
            _mean_primary_fraction(tasks, "mechanism_qualified_count", denominator=12)
            if gate.passed
            else None
        ),
        "unconditional_task_weighted_qualified_fraction": (
            _mean_primary_fraction(tasks, "qualified_valid_count", denominator=12)
            if gate.passed
            else None
        ),
        "conditioned_path_weighted_base_fraction": (
            _mean_primary_fraction(paths, "base_valid_count", denominator=6)
            if gate.passed
            else None
        ),
        "conditioned_path_weighted_mechanism_fraction": (
            _mean_primary_fraction(paths, "mechanism_qualified_count", denominator=6)
            if gate.passed
            else None
        ),
        "conditioned_path_weighted_qualified_fraction": (
            _mean_primary_fraction(paths, "qualified_valid_count", denominator=6)
            if gate.passed
            else None
        ),
        "unconditional_task_summaries": tasks,
        "conditioned_path_summaries": paths,
        "mechanism_summaries": mechanisms,
        "provider_call_count": sum(item.provider_call_count for item in results),
        "transport_inclusive_invocation_count": sum(
            item.transport_inclusive_invocation_count for item in results
        ),
        "provider_prompt_tokens": sum(item.provider_prompt_tokens for item in results),
        "provider_completion_tokens": sum(item.provider_completion_tokens for item in results),
        "provider_reasoning_tokens": sum(item.provider_reasoning_tokens for item in results),
        "provider_total_tokens": sum(item.provider_total_tokens for item in results),
        "estimated_cost_usd": format(estimated_cost, "f"),
        "execution_status": (
            "measurement_gate_passed_pending_independent_audit"
            if gate.passed
            else "measurement_gate_failed_pending_independent_audit"
        ),
    }
    provisional = ReachabilityExecutionReport.model_construct(report_id="pending", **values)
    return ReachabilityExecutionReport(
        report_id=_identity(
            provisional,
            "report_id",
            "finance_v26_fresh_reachability_execution_report:",
        ),
        **values,
    )


ClientFactory = Callable[
    [
        AgentModelConfig,
        preflight.FreshReachabilityJob,
        runner_vnext.FreshReachabilityRuntimeBinding,
    ],
    Any,
]


def _default_client_factory(
    config: AgentModelConfig,
    _job: preflight.FreshReachabilityJob,
    _binding: runner_vnext.FreshReachabilityRuntimeBinding,
) -> Any:
    return StageOneProspectiveThinkingJsonClient(config)


def _run_one_job(
    *,
    job: preflight.FreshReachabilityJob,
    prepared: PreparedExecution,
    client_factory: ClientFactory | None,
    output_dir: Path,
) -> tuple[ReachabilityMeasurementResult, runner_vnext.FreshReachabilityRawExecution]:
    package = _package_for_job(prepared, job)
    binding = _runtime_binding_for_job(
        prepared=prepared,
        package=package,
        job=job,
    )
    client = (
        None
        if client_factory is None
        else client_factory(
            prepared.role_inputs.static.agent_model_config,
            job,
            binding,
        )
    )
    raw = runner_vnext.execute_fresh_reachability_job_raw(
        job=job,
        runner_contract=prepared.runner_contract,
        resource_contract=prepared.resource,
        static=prepared.role_inputs.static,
        qualified_grammar=prepared.grammar,
        binding=binding,
        client=client,
        output_dir=output_dir,
    )
    result = project_measurement_result(
        raw=raw,
        job=job,
        package=package,
        prepared=prepared,
        output_dir=output_dir,
    )
    return result, raw


def _write_checkpoint(
    path: Path,
    rows: Sequence[ReachabilityMeasurementResult],
) -> None:
    payload = b"\n".join(_canonical_bytes(item).rstrip(b"\n") for item in rows)
    if payload:
        payload += b"\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(payload)
    temporary.replace(path)


def _load_checkpoint(
    path: Path,
    *,
    prepared: PreparedExecution,
    output_dir: Path,
) -> tuple[ReachabilityMeasurementResult, ...]:
    if not path.exists():
        return ()
    rows = tuple(
        ReachabilityMeasurementResult.model_validate_json(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    )
    jobs = {item.job_id: item for item in prepared.manifest.jobs}
    if len({item.job_id for item in rows}) != len(rows):
        raise ValueError("v26.154 checkpoint contains duplicate Jobs")
    for result in rows:
        job = jobs.get(result.job_id)
        if job is None:
            raise ValueError("v26.154 checkpoint crosses the Manifest")
        if (
            result.sampling_mode,
            result.requested_path_id,
            result.requested_path_strategy,
            result.public_path_condition,
            result.public_condition_id,
        ) != (
            job.sampling_mode,
            job.requested_path_id,
            job.requested_path_strategy,
            job.public_path_condition,
            job.public_condition_id,
        ):
            raise ValueError("v26.154 checkpoint route binding changed")
        raw_path = runner_vnext._raw_path(output_dir, job)  # noqa: SLF001
        if (
            not raw_path.is_file()
            or _sha256(raw_path) != result.raw_execution_artifact.sha256
            or raw_path.stat().st_size != result.raw_execution_artifact.byte_count
        ):
            raise ValueError("v26.154 checkpoint Raw binding changed")
    return rows


def _assert_no_orphan_artifacts(
    output_dir: Path,
    job: preflight.FreshReachabilityJob,
) -> None:
    envelope_dir = privacy_runner.provider_envelope_path(output_dir, cast(Any, job), 0).parent
    projection_dir = privacy_runner.payload_projection_path(output_dir, cast(Any, job), 0).parent
    invocation_dir = preflight.s1_runner._invocation_path(  # noqa: SLF001
        output_dir, cast(Any, job), 0
    ).parent
    counts = (
        len(tuple(envelope_dir.glob("call_*.json"))) if envelope_dir.exists() else 0,
        len(tuple(projection_dir.glob("call_*.json"))) if projection_dir.exists() else 0,
        (len(tuple(invocation_dir.glob("invocation_*.json"))) if invocation_dir.exists() else 0),
    )
    if any(counts):
        raise ValueError(
            "orphan v26.154 artifacts forbid retry: "
            f"job={job.job_id} envelopes={counts[0]} projections={counts[1]} "
            f"invocations={counts[2]}"
        )


def run_fresh_reachability_execution(
    *,
    preflight_dir: Path,
    output_dir: Path,
    package_root: Path,
    implementation_root: Path,
    workers: int,
    client_factory: ClientFactory = _default_client_factory,
) -> ReachabilityExecutionReport:
    prepared = prepare_execution(
        preflight_dir=preflight_dir,
        output_dir=output_dir,
        package_root=package_root,
        implementation_root=implementation_root,
    )
    checkpoint_path = output_dir / "fresh_reachability_results.checkpoint.jsonl"
    existing = _load_checkpoint(
        checkpoint_path,
        prepared=prepared,
        output_dir=output_dir,
    )
    completed = {item.job_id: item for item in existing}
    jobs = prepared.manifest.jobs
    pending = [item for item in jobs if item.job_id not in completed]
    report_path = output_dir / "report.json"
    if pending and report_path.exists():
        raise ValueError("v26.154 report exists while frozen Jobs remain pending")
    if not pending and report_path.exists():
        report = ReachabilityExecutionReport.model_validate(_load(report_path))
        if (
            report.runner_contract_id != prepared.runner_contract.contract_id
            or report.source_replay_audit_id != prepared.source_replay.audit_id
        ):
            raise ValueError("v26.154 completed report crosses frozen bindings")
        return report

    raw_recovery_jobs = [
        item
        for item in pending
        if runner_vnext._raw_path(output_dir, item).exists()  # noqa: SLF001
    ]
    model_pending_jobs = [
        item
        for item in pending
        if not runner_vnext._raw_path(output_dir, item).exists()  # noqa: SLF001
    ]
    for job in model_pending_jobs:
        _assert_no_orphan_artifacts(output_dir, job)

    print(
        f"[v26.154] resuming {len(completed)}/360; "
        f"raw-only recovery {len(raw_recovery_jobs)}; "
        f"executing {len(model_pending_jobs)} Jobs with {workers} workers",
        flush=True,
    )
    raw_by_job: dict[str, runner_vnext.FreshReachabilityRawExecution] = {}
    for job in jobs:
        raw_path = runner_vnext._raw_path(output_dir, job)  # noqa: SLF001
        if raw_path.exists() and job.job_id in completed:
            raw_by_job[job.job_id] = runner_vnext.FreshReachabilityRawExecution.model_validate(
                _load(raw_path)
            )

    lock = threading.Lock()

    def record_completion(
        *,
        job: preflight.FreshReachabilityJob,
        result: ReachabilityMeasurementResult,
        raw: runner_vnext.FreshReachabilityRawExecution,
        recovered: bool = False,
    ) -> None:
        with lock:
            completed[job.job_id] = result
            raw_by_job[job.job_id] = raw
            ordered = tuple(completed[item.job_id] for item in jobs if item.job_id in completed)
            _write_checkpoint(checkpoint_path, ordered)
            label = " recovered" if recovered else ""
            print(
                f"[v26.154]{label} completed {len(completed)}/360 "
                f"{job.job_id.rsplit(':', 1)[-1][:12]} "
                f"mechanism={job.mechanism_id} tier={job.tier} "
                f"sampling={job.sampling_mode} "
                f"route={job.public_path_condition or 'none'} "
                f"terminal={raw.terminal_disposition} "
                f"M={result.measurement_support_available} "
                f"O={result.model_endpoint_observed} "
                f"R={result.instrument_integrity} "
                f"P={result.privacy_compliant} "
                f"base={result.base_trajectory_validity} "
                f"mechanism_q={result.mechanism_qualification} "
                f"qualified={result.qualified_trajectory_validity} "
                f"calls={result.provider_call_count}",
                flush=True,
            )

    worker_failures: list[tuple[preflight.FreshReachabilityJob, str]] = []
    with ThreadPoolExecutor(max_workers=max(1, min(workers, len(pending) or 1))) as executor:
        futures = {
            executor.submit(
                _run_one_job,
                job=job,
                prepared=prepared,
                client_factory=(None if job in raw_recovery_jobs else client_factory),
                output_dir=output_dir,
            ): job
            for job in pending
        }
        for future in as_completed(futures):
            job = futures[future]
            try:
                result, raw = future.result()
            except Exception as error:
                worker_failures.append((job, type(error).__name__))
                print(
                    "[v26.154] worker exception retained for Raw-only recovery: "
                    f"job={job.job_id} type={type(error).__name__} "
                    f"raw_persisted={runner_vnext._raw_path(output_dir, job).is_file()}",  # noqa: SLF001
                    flush=True,
                )
                continue
            record_completion(job=job, result=result, raw=raw)

    unresolved: list[tuple[preflight.FreshReachabilityJob, str]] = []
    for job, failure_type in worker_failures:
        if not runner_vnext._raw_path(output_dir, job).is_file():  # noqa: SLF001
            unresolved.append((job, failure_type))
            continue
        try:
            result, raw = _run_one_job(
                job=job,
                prepared=prepared,
                client_factory=None,
                output_dir=output_dir,
            )
        except Exception as error:
            unresolved.append((job, type(error).__name__))
            print(
                "[v26.154] Raw-only recovery failed closed: "
                f"job={job.job_id} type={type(error).__name__}",
                flush=True,
            )
            continue
        record_completion(job=job, result=result, raw=raw, recovered=True)

    if unresolved:
        raise RuntimeError(
            "v26.154 unresolved worker failures after every future drained: "
            f"count={len(unresolved)} "
            f"types={dict(sorted(Counter(kind for _, kind in unresolved).items()))}"
        )

    results = tuple(completed[item.job_id] for item in jobs)
    if len(results) != 360:
        raise ValueError("v26.154 execution denominator is incomplete")
    for job in jobs:
        if job.job_id not in raw_by_job:
            raw_by_job[job.job_id] = runner_vnext.FreshReachabilityRawExecution.model_validate(
                _load(runner_vnext._raw_path(output_dir, job))  # noqa: SLF001
            )

    lineage = _raw_lineage(
        prepared=prepared,
        results=results,
        raws=raw_by_job,
        output_dir=output_dir,
    )
    gate = _measurement_gate(results, complete_raw_count=len(raw_by_job))
    report = _execution_report(
        prepared=prepared,
        results=results,
        lineage=lineage,
        gate=gate,
    )
    noninterference_rows = tuple(
        item.online_noninterference_audit
        for item in results
        if item.online_noninterference_audit is not None
    )
    _write_json_atomic(output_dir / "fresh_reachability_measurement_results.json", results)
    _write_json_atomic(
        output_dir / "online_noninterference_audits.json",
        noninterference_rows,
    )
    _write_json_atomic(output_dir / "raw_lineage_audit.json", lineage)
    _write_json_atomic(output_dir / "measurement_gate_audit.json", gate)
    _write_json_atomic(
        output_dir / "unconditional_task_estimand_summaries.json",
        report.unconditional_task_summaries,
    )
    _write_json_atomic(
        output_dir / "conditioned_path_estimand_summaries.json",
        report.conditioned_path_summaries,
    )
    _write_json_atomic(
        output_dir / "mechanism_estimand_summaries.json",
        report.mechanism_summaries,
    )
    _write_json_atomic(report_path, report)
    return report


def main() -> None:
    package_default = Path(__file__).resolve().parents[4]
    parser = argparse.ArgumentParser(
        description="Run the exact v26.154 fresh Reachability denominator"
    )
    parser.add_argument(
        "--preflight-dir",
        type=Path,
        default=package_default / PREFLIGHT_DIR,
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=package_default / OUTPUT_DIR,
    )
    parser.add_argument("--package-root", type=Path, default=package_default)
    parser.add_argument("--implementation-root", type=Path, default=package_default)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--prepare-only", action="store_true")
    args = parser.parse_args()

    if args.prepare_only:
        prepared = prepare_execution(
            preflight_dir=args.preflight_dir,
            output_dir=args.output_dir,
            package_root=args.package_root,
            implementation_root=args.implementation_root,
        )
        print(
            json.dumps(
                {
                    "status": "prepared",
                    "source_replay_audit_id": prepared.source_replay.audit_id,
                    "preexecution_binding_audit_id": prepared.preexecution_binding.audit_id,
                    "manifest_id": prepared.manifest.manifest_id,
                    "runner_contract_id": prepared.runner_contract.contract_id,
                    "outcome_contract_id": prepared.outcome_contract.contract_id,
                    "expected_jobs": len(prepared.manifest.jobs),
                    "distinct_tasks": len(
                        {item.task_package_id for item in prepared.manifest.jobs}
                    ),
                    "authorized_reachability_jobs": len(prepared.manifest.jobs),
                    "state_mapping_jobs": 0,
                    "model_client_constructed": False,
                    "provider_calls": 0,
                    "stage_two_provider_calls": 0,
                },
                indent=2,
            )
        )
        return

    report = run_fresh_reachability_execution(
        preflight_dir=args.preflight_dir,
        output_dir=args.output_dir,
        package_root=args.package_root,
        implementation_root=args.implementation_root,
        workers=args.workers,
    )
    print(report.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
