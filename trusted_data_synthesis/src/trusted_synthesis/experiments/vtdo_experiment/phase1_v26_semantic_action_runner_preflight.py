from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Final, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_exact_response_grammar_runner_preflight as exact_preflight,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_semantic_action_calibration_execution as runner,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_two_stage_semantic_proposal_execution as legacy,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_semantic_action_rematerialization import (  # noqa: E501
    OUTPUT_DIR as V26_118_DIR,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_semantic_action_rematerialization import (  # noqa: E501
    SemanticActionRematerializationReport,
    SemanticActionStaticInputs,
    load_semantic_action_static_inputs,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_semantic_action_rematerialization import (  # noqa: E501
    SourceReplayAudit as V26_118SourceReplay,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_two_stage_semantic_proposal_calibration_execution import (  # noqa: E501
    _completed_verification,
)
from trusted_synthesis.hashing import canonical_hash
from trusted_synthesis.runtime.agent.prospective_semantic_action_protocol import (
    build_semantic_action_state,
    evaluate_canonical_action_proposal,
    make_canonical_action_proposal,
)
from trusted_synthesis.runtime.agent.prospective_semantic_action_response_grammar import (
    RESPONSE_PROTOCOL_VERSION,
    exact_canonical_action_payload,
    parse_exact_canonical_action_payload,
    prompt_only_reference_payload,
    render_exact_canonical_action_prompt,
    semantic_action_state_from_response_prompt,
)
from trusted_synthesis.runtime.agent.prospective_two_stage_semantic_proposal import (
    final_answer_payload,
)

RUN_ID: Final = "finance_v26_119_semantic_action_runner_preflight_v1_20260823"
NEXT_STAGE: Final = "semantic_action_calibration_execution_only"
OUTPUT_DIR: Final = (
    "artifacts/vtdo_experiment/finance_v26_119_semantic_action_runner_preflight_v1_20260823"
)
IMPLEMENTATION_PATHS: Final = (
    "src/trusted_synthesis/experiments/vtdo_experiment/"
    "phase1_v26_semantic_action_calibration_execution.py",
    "src/trusted_synthesis/experiments/vtdo_experiment/"
    "phase1_v26_semantic_action_runner_preflight.py",
)
EXPECTED_V26_118_REPORT_ID: Final = (
    "finance_v26_semantic_action_rematerialization_report:"
    "eb1820c71ac6a0a5b062d6c3db1f31768ed5dc9c68827d4dd79777f622ab0519"
)
EXPECTED_V26_118_CONTRACT_ID: Final = (
    "finance_v26_semantic_action_execution_contract:"
    "fe49aceaeaeebf3442cabde8ace4bf985889e40cbe19e015cc4a3c8d59662b77"
)
EXPECTED_V26_118_MANIFEST_ID: Final = (
    "finance_v26_semantic_action_manifest:"
    "b517318004dfdc2ffce1de97e7a94acab9138ee2d0bca410da179a835ab88bcd"
)
EXPECTED_V26_118_RESOURCE_ID: Final = (
    "finance_v26_semantic_action_resource_contract:"
    "358453a9075d5df7a158b9a11100bf27585dacde644f993058452a0f0a851bdf"
)
EXPECTED_RESPONSE_GRAMMAR_ID: Final = (
    "prospective_semantic_action_response_grammar:"
    "bbda30254855071bc024f6217cea4eec57512eaa50c8e5e0f7755c6e92d07e82"
)
V26_118_OUTPUTS: Final = (
    "candidate_space_authority_audit.json",
    "cross_artifact_binding_audit.json",
    "destructive_audit.json",
    "prospective_transition_contract.json",
    "report.json",
    "semantic_action_execution_contract.json",
    "semantic_action_job_manifest.json",
    "semantic_action_path_audits.json",
    "semantic_action_resource_contract.json",
    "semantic_action_response_grammar.json",
    "semantic_action_task_packages.json",
    "source_replay_audit.json",
)


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


def _identity(value: BaseModel, field: str, prefix: str) -> str:
    return canonical_hash(value.model_dump(mode="json", exclude={field}), prefix=prefix)


class SourceReplayEntry(FrozenModel):
    relative_path: str = Field(min_length=1)
    source_kind: Literal[
        "v26_118_transitive_source",
        "v26_118_output",
        "v26_119_implementation",
    ]
    expected_sha256: str = Field(min_length=64, max_length=64)
    observed_sha256: str = Field(min_length=64, max_length=64)
    byte_count: int = Field(gt=0)
    passed: Literal[True] = True


class RunnerSourceReplayAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    predecessor_report_id: str = EXPECTED_V26_118_REPORT_ID
    predecessor_transitive_file_count: Literal[2203] = 2203
    predecessor_output_file_count: Literal[12] = 12
    implementation_file_count: Literal[2] = 2
    replayed_file_count: Literal[2217] = 2217
    replay_pass_count: Literal[2217] = 2217
    entries: tuple[SourceReplayEntry, ...] = Field(min_length=2217, max_length=2217)
    replay_before_profile_parsing: Literal[True] = True
    replay_before_credential_lookup: Literal[True] = True
    replay_before_client_construction: Literal[True] = True
    credential_lookup_attempted: Literal[False] = False
    model_client_constructed: Literal[False] = False
    provider_calls: Literal[0] = 0
    gpu_jobs: Literal[0] = 0
    schema_version: Literal["finance_v26_semantic_action_runner_source_replay.v1"] = (
        "finance_v26_semantic_action_runner_source_replay.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> RunnerSourceReplayAudit:
        paths = tuple(item.relative_path for item in self.entries)
        if paths != tuple(sorted(set(paths))) or len(paths) != 2217:
            raise ValueError("v26.119 source replay paths are not canonical and unique")
        if any(item.expected_sha256 != item.observed_sha256 for item in self.entries):
            raise ValueError("v26.119 source replay contains a hash mismatch")
        if self.audit_id != _identity(
            self, "audit_id", "finance_v26_semantic_action_runner_source_replay:"
        ):
            raise ValueError("v26.119 source replay identity changed")
        return self


class RunnerBindingAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    runner_contract_id: str = Field(min_length=1)
    static_contract_id: str = EXPECTED_V26_118_CONTRACT_ID
    manifest_id: str = EXPECTED_V26_118_MANIFEST_ID
    resource_contract_id: str = EXPECTED_V26_118_RESOURCE_ID
    response_grammar_id: str = EXPECTED_RESPONSE_GRAMMAR_ID
    response_protocol: Literal["prospective_semantic_action_exact_response.v1"] = (
        RESPONSE_PROTOCOL_VERSION
    )
    model: Literal["deepseek-v4-flash"] = "deepseek-v4-flash"
    max_tokens: Literal[16384] = 16384
    thinking_type: Literal["enabled"] = "enabled"
    response_format_type: Literal["json_object"] = "json_object"
    rollout_upper_bound_tokens: Literal[400000] = 400000
    fallback_count: Literal[0] = 0
    discovery_enabled: Literal[False] = False
    stage_two_provider_call_upper_bound: Literal[0] = 0
    ordinary_uncertified_entrypoint_allowed: Literal[False] = False
    credential_lookup_attempted: Literal[False] = False
    real_client_constructed: Literal[False] = False
    provider_calls: Literal[0] = 0
    schema_version: Literal["finance_v26_semantic_action_runner_binding.v1"] = (
        "finance_v26_semantic_action_runner_binding.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> RunnerBindingAudit:
        if self.audit_id != _identity(
            self, "audit_id", "finance_v26_semantic_action_runner_binding:"
        ):
            raise ValueError("v26.119 Runner binding identity changed")
        return self


class RunnerFixtureRow(FrozenModel):
    job_id: str = Field(min_length=1)
    raw_execution_id: str = Field(min_length=1)
    stage_one_provider_call_count: int = Field(gt=0)
    semantic_payload_count: int = Field(gt=0)
    semantic_choice_count: int = Field(gt=0)
    stage_two_commit_count: int = Field(gt=0)
    observation_count: int = Field(gt=0)
    replay_v3_passed: Literal[True] = True
    independent_validity_passed: Literal[True] = True
    mechanism_score_passed: Literal[True] = True
    requested_path_preserved: Literal[True] = True
    final_answer_preserved: Literal[True] = True


class RunnerFixtureAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    runner_contract_id: str = Field(min_length=1)
    rows: tuple[RunnerFixtureRow, ...] = Field(min_length=32, max_length=32)
    job_count: Literal[32] = 32
    stage_one_scripted_provider_call_count: Literal[256] = 256
    exact_four_field_payload_count: Literal[224] = 224
    semantic_choice_count: Literal[224] = 224
    first_choice_accepted_count: Literal[224] = 224
    stage_two_commit_count: Literal[224] = 224
    public_observation_count: Literal[192] = 192
    dynamic_certificate_count: Literal[256] = 256
    request_binding_certificate_count: Literal[256] = 256
    resource_certificate_count: Literal[256] = 256
    raw_provider_artifact_count: Literal[256] = 256
    replay_v3_pass_count: Literal[32] = 32
    independent_validity_pass_count: Literal[32] = 32
    mechanism_success_count: Literal[32] = 32
    final_answer_match_count: Literal[32] = 32
    requested_path_match_count: Literal[32] = 32
    abi_rescue_count: Literal[0] = 0
    semantic_recovery_count: Literal[0] = 0
    stage_two_provider_call_count: Literal[0] = 0
    real_provider_call_count: Literal[0] = 0
    fixture_aggregate_sha256: str = Field(min_length=64, max_length=64)
    schema_version: Literal["finance_v26_semantic_action_runner_fixture.v1"] = (
        "finance_v26_semantic_action_runner_fixture.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> RunnerFixtureAudit:
        if self.audit_id != _identity(
            self, "audit_id", "finance_v26_semantic_action_runner_fixture:"
        ):
            raise ValueError("v26.119 Runner fixture identity changed")
        return self


class SemanticRecoveryControlAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    runner_contract_id: str = Field(min_length=1)
    combined_abi_and_semantic_recovery_fixture_count: Literal[1] = 1
    malformed_primary_payload_count: Literal[1] = 1
    abi_rescue_attempt_count: Literal[1] = 1
    abi_rescue_exact_four_field_count: Literal[1] = 1
    first_choice_semantic_rejection_count: Literal[1] = 1
    first_choice_failure_retained_count: Literal[1] = 1
    semantic_recovery_attempt_count: Literal[1] = 1
    recovery_selected_different_action_count: Literal[1] = 1
    recovery_commit_count: Literal[1] = 1
    recovery_public_progress_count: Literal[1] = 1
    completed_after_recovery_count: Literal[1] = 1
    abi_count_before_semantic_recovery: Literal[1] = 1
    semantic_count_before_semantic_recovery: Literal[1] = 1
    rejection_immediate_terminal_count: Literal[0] = 0
    correct_action_id_exposed_count: Literal[0] = 0
    exact_failed_argument_values_exposed_count: Literal[0] = 0
    stage_two_provider_call_count: Literal[0] = 0
    real_provider_call_count: Literal[0] = 0
    status: Literal["passed"] = "passed"
    schema_version: Literal["finance_v26_semantic_recovery_runner_control.v1"] = (
        "finance_v26_semantic_recovery_runner_control.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> SemanticRecoveryControlAudit:
        if self.audit_id != _identity(
            self, "audit_id", "finance_v26_semantic_recovery_runner_control:"
        ):
            raise ValueError("v26.119 Semantic Recovery control identity changed")
        return self


class CertificateUsageRecoveryAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    runner_contract_id: str = Field(min_length=1)
    complete_raw_recovery_byte_identical: Literal[True] = True
    complete_raw_recovery_provider_calls: Literal[0] = 0
    orphan_provider_artifact_rejected: Literal[True] = True
    oversized_prompt_rejected_before_provider: Literal[True] = True
    reused_preparation_rejected: Literal[True] = True
    insufficient_remaining_budget_rejected_before_provider: Literal[True] = True
    completion_16384_admitted: Literal[True] = True
    completion_16385_admitted_and_charged: Literal[True] = True
    completion_16386_instrument_failure: Literal[True] = True
    calls_blocked_after_instrument_failure: Literal[True] = True
    raw_provider_certificate_triple_count: Literal[256] = 256
    certificate_parent_binding_pass_count: Literal[256] = 256
    privacy_pass_count: Literal[256] = 256
    stage_two_provider_call_count: Literal[0] = 0
    real_provider_call_count: Literal[0] = 0
    schema_version: Literal["finance_v26_semantic_action_certificate_usage_recovery.v1"] = (
        "finance_v26_semantic_action_certificate_usage_recovery.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> CertificateUsageRecoveryAudit:
        if self.audit_id != _identity(
            self,
            "audit_id",
            "finance_v26_semantic_action_certificate_usage_recovery:",
        ):
            raise ValueError("v26.119 certificate/Usage/Recovery identity changed")
        return self


class OutcomeMeasurementContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    runner_contract_id: str = Field(min_length=1)
    experimental_condition_components: tuple[str, ...] = (
        "task",
        "role",
        "model_profile",
        "canonical_semantic_action_protocol",
        "bounded_recovery_policy",
    )
    measured_object: Literal[
        "state_interpretation_and_action_selection_in_canonical_public_action_space"
    ] = "state_interpretation_and_action_selection_in_canonical_public_action_space"
    required_funnel: tuple[str, ...] = (
        "provider_response",
        "exact_four_field_proposal",
        "visible_action_id_match",
        "first_choice_accepted",
        "reversible_stage_two_commit",
        "runtime_observation",
        "typed_semantic_rejection",
        "bounded_semantic_recovery",
        "public_program_progress",
        "terminal_verification",
        "final_answer",
        "independent_validity",
    )
    required_job_metrics: tuple[str, ...] = (
        "first_action_id_legal",
        "first_action_public_progress",
        "semantic_rejection_count",
        "semantic_recovery_used",
        "recovery_selected_different_action",
        "recovery_committed",
        "recovery_public_progress",
        "program_closure",
        "independent_validity",
    )
    first_choice_failure_retained_after_eventual_success: Literal[True] = True
    metrics_may_rescue_each_other: Literal[False] = False
    compare_as_same_distribution_with_v26_114: Literal[False] = False
    model_ability_increased_claim_authorized: Literal[False] = False
    allowed_interpretation: Literal[
        "executable_behavior_under_canonical_semantic_action_interface"
    ] = "executable_behavior_under_canonical_semantic_action_interface"
    schema_version: Literal["finance_v26_semantic_action_outcome_measurement.v1"] = (
        "finance_v26_semantic_action_outcome_measurement.v1"
    )

    @model_validator(mode="after")
    def validate_contract(self) -> OutcomeMeasurementContract:
        if self.contract_id != _identity(
            self, "contract_id", "finance_v26_semantic_action_outcome_measurement:"
        ):
            raise ValueError("v26.119 outcome-measurement Contract identity changed")
        return self


class MutationResult(FrozenModel):
    name: str = Field(min_length=1)
    rejected: Literal[True] = True
    provider_calls: Literal[0] = 0
    stage_two_provider_calls: Literal[0] = 0


class DestructiveRunnerAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    mutation_count: Literal[16] = 16
    rejection_count: Literal[16] = 16
    mutations: tuple[MutationResult, ...] = Field(min_length=16, max_length=16)
    provider_calls: Literal[0] = 0
    stage_two_provider_calls: Literal[0] = 0
    status: Literal["passed"] = "passed"
    schema_version: Literal["finance_v26_semantic_action_runner_destructive.v1"] = (
        "finance_v26_semantic_action_runner_destructive.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> DestructiveRunnerAudit:
        names = tuple(item.name for item in self.mutations)
        if names != tuple(sorted(set(names))) or len(names) != 16:
            raise ValueError("v26.119 destructive controls are not canonical and unique")
        if self.audit_id != _identity(
            self, "audit_id", "finance_v26_semantic_action_runner_destructive:"
        ):
            raise ValueError("v26.119 destructive Runner identity changed")
        return self


class ProspectiveTransitionContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    status: Literal["passed_runner_preflight"] = "passed_runner_preflight"
    next_permitted_stage: str = NEXT_STAGE
    exact_manifest_job_denominator: Literal[32] = 32
    exact_manifest_execution_authorized: Literal[True] = True
    provider_calls_in_this_preflight: Literal[0] = 0
    model_profile_protocol_resource_task_manifest_or_job_change_authorized: Literal[False] = False
    historical_rerun_recovery_or_reclassification_authorized: Literal[False] = False
    host_semantic_choice_or_repair_authorized: Literal[False] = False
    role_state_training_release_or_production_authorized: Literal[False] = False
    schema_version: Literal["finance_v26_semantic_action_runner_transition.v1"] = (
        "finance_v26_semantic_action_runner_transition.v1"
    )

    @model_validator(mode="after")
    def validate_contract(self) -> ProspectiveTransitionContract:
        if self.contract_id != _identity(
            self, "contract_id", "finance_v26_semantic_action_runner_transition:"
        ):
            raise ValueError("v26.119 transition identity changed")
        return self


class DetailFile(FrozenModel):
    relative_path: str = Field(min_length=1)
    sha256: str = Field(min_length=64, max_length=64)
    byte_count: int = Field(gt=0)


class SemanticActionRunnerPreflightReport(FrozenModel):
    report_id: str = Field(min_length=1)
    run_id: str = RUN_ID
    source_replay_audit_id: str = Field(min_length=1)
    runner_contract_id: str = Field(min_length=1)
    runner_binding_audit_id: str = Field(min_length=1)
    runner_fixture_audit_id: str = Field(min_length=1)
    semantic_recovery_control_audit_id: str = Field(min_length=1)
    certificate_usage_recovery_audit_id: str = Field(min_length=1)
    outcome_measurement_contract_id: str = Field(min_length=1)
    destructive_runner_audit_id: str = Field(min_length=1)
    transition_contract_id: str = Field(min_length=1)
    detail_files: tuple[DetailFile, ...] = Field(min_length=9, max_length=9)
    exact_job_denominator: Literal[32] = 32
    scripted_job_count: Literal[32] = 32
    combined_recovery_fixture_count: Literal[1] = 1
    provider_calls: Literal[0] = 0
    stage_two_provider_calls: Literal[0] = 0
    gpu_jobs: Literal[0] = 0
    empirical_rows: Literal[0] = 0
    next_permitted_stage: str = NEXT_STAGE
    status: Literal["passed_runner_preflight"] = "passed_runner_preflight"
    schema_version: Literal["finance_v26_semantic_action_runner_preflight_report.v1"] = (
        "finance_v26_semantic_action_runner_preflight_report.v1"
    )

    @model_validator(mode="after")
    def validate_report(self) -> SemanticActionRunnerPreflightReport:
        if self.report_id != _identity(
            self, "report_id", "finance_v26_semantic_action_runner_preflight_report:"
        ):
            raise ValueError("v26.119 report identity changed")
        return self


def _load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _write_json(path: Path, value: BaseModel) -> None:
    path.write_text(
        json.dumps(
            value.model_dump(mode="json"),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n",
        encoding="utf-8",
    )


def _entry(path: Path, relative: str, kind: Any, expected: str | None = None) -> SourceReplayEntry:
    digest = legacy.sha256_file(path)
    return SourceReplayEntry(
        relative_path=relative,
        source_kind=kind,
        expected_sha256=expected or digest,
        observed_sha256=digest,
        byte_count=path.stat().st_size,
    )


def _find_bound_path(
    relative: str,
    expected: str,
    package_root: Path,
    implementation_root: Path,
) -> Path:
    for root in (implementation_root, package_root):
        path = root / relative
        if path.is_file() and legacy.sha256_file(path) == expected:
            return path
    raise ValueError(f"v26.119 cannot replay bound file: {relative}")


def _build_source_replay(package_root: Path, implementation_root: Path) -> RunnerSourceReplayAudit:
    root = package_root / V26_118_DIR
    predecessor_source = V26_118SourceReplay.model_validate(
        _load_json(root / "source_replay_audit.json")
    )
    predecessor_report = SemanticActionRematerializationReport.model_validate(
        _load_json(root / "report.json")
    )
    if predecessor_report.report_id != EXPECTED_V26_118_REPORT_ID:
        raise ValueError("v26.119 predecessor report identity changed")
    entries: dict[str, SourceReplayEntry] = {}
    for item in predecessor_source.entries:
        path = _find_bound_path(
            item.relative_path,
            item.expected_sha256,
            package_root,
            implementation_root,
        )
        entries[item.relative_path] = _entry(
            path,
            item.relative_path,
            "v26_118_transitive_source",
            item.expected_sha256,
        )
    detail = {item.relative_path: item for item in predecessor_report.detail_files}
    for name in V26_118_OUTPUTS:
        path = root / name
        if not path.is_file():
            raise ValueError("v26.119 predecessor output is missing")
        if name != "report.json":
            expected = detail.get(name)
            if (
                expected is None
                or expected.sha256 != legacy.sha256_file(path)
                or expected.byte_count != path.stat().st_size
            ):
                raise ValueError("v26.119 predecessor detail binding changed")
        relative = str(Path(V26_118_DIR) / name)
        entries[relative] = _entry(path, relative, "v26_118_output")
    for relative in IMPLEMENTATION_PATHS:
        path = implementation_root / relative
        entries[relative] = _entry(path, relative, "v26_119_implementation")
    values = {"entries": tuple(entries[key] for key in sorted(entries))}
    provisional = RunnerSourceReplayAudit.model_construct(audit_id="pending", **values)
    return RunnerSourceReplayAudit(
        audit_id=_identity(
            provisional,
            "audit_id",
            "finance_v26_semantic_action_runner_source_replay:",
        ),
        **values,
    )


class ScriptedSemanticActionClient:
    def __init__(
        self,
        config: legacy.AgentModelConfig,
        *,
        final_answer: Mapping[str, Any] | None = None,
        completion_tokens: int = 64,
        combined_recovery_control: bool = False,
    ) -> None:
        self.config = config
        self._final_answer = dict(final_answer or {"value": "fixture"})
        self._completion_tokens = completion_tokens
        self._combined_recovery_control = combined_recovery_control
        self._semantic_call_count = 0
        self.call_count = 0

    def complete_json_certified(
        self,
        prompt: str,
        certificate: legacy.StageOneRequestBindingCertificate,
    ) -> tuple[dict[str, Any], legacy.ModelCallTelemetry]:
        expected = legacy.certify_stage_one_request_pre_call(
            config=self.config,
            prompt=prompt,
            request_kind=certificate.request_kind,
            phase=certificate.phase,
        )
        if expected != certificate:
            raise legacy.LLMClientError("scripted semantic-action certificate changed")
        if certificate.request_kind == "final_answer":
            payload = final_answer_payload(self._final_answer)
        elif self._combined_recovery_control and self._semantic_call_count == 0:
            payload = {"state_id": "malformed"}
            self._semantic_call_count += 1
        elif self._combined_recovery_control and self._semantic_call_count == 1:
            state = semantic_action_state_from_response_prompt(prompt)
            payload = {
                "state_id": state.state_id,
                "action_id": ("prospective_canonical_public_action:" + "f" * 64),
                "decision_kind": state.action_candidates[0].decision_kind,
                "protocol": RESPONSE_PROTOCOL_VERSION,
            }
            self._semantic_call_count += 1
        else:
            payload = prompt_only_reference_payload(prompt)
            self._semantic_call_count += 1
        prompt_tokens = len(prompt.encode("utf-8"))
        completion_tokens = self._completion_tokens
        self.call_count += 1
        telemetry = legacy.ModelCallTelemetry(
            provider="deepseek",
            endpoint_host="api.deepseek.com",
            model_requested=legacy.STAGE_ONE_MODEL_ID,
            model_selected=legacy.STAGE_ONE_MODEL_ID,
            response_model=legacy.STAGE_ONE_MODEL_ID,
            request_hash=legacy.sha256_text(prompt),
            response_hash=canonical_hash(payload, prefix="scripted_semantic_action_response:"),
            http_status=200,
            http_success=True,
            json_contract_success=True,
            finish_reason="stop",
            response_content_length=len(
                json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
            ),
            reasoning_content_present=True,
            reasoning_content_length=32,
            reasoning_tokens=min(16, completion_tokens),
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
            estimated_cost=0,
            cost_estimation_method="conservative_cache_miss",
            latency_ms=0,
            fallback_used=False,
            discovery_attempted=False,
            discovered_model_count=0,
        )
        return payload, telemetry


def _fixture_hash(raws: Sequence[runner.SemanticActionRawExecution]) -> str:
    return hashlib.sha256(
        json.dumps(
            [item.model_dump(mode="json") for item in raws],
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def _single_ledger_call(
    static: SemanticActionStaticInputs,
    contract: runner.SemanticActionRunnerContract,
    job: Any,
    root: Path,
    completion_tokens: int,
) -> tuple[bool, int, runner.JournaledSemanticActionClient]:
    client = ScriptedSemanticActionClient(
        static.agent_model_config, completion_tokens=completion_tokens
    )
    ledger = runner.JournaledSemanticActionClient(
        client,
        runner_contract=contract,
        resource_contract=static.resource,
        job=job,
        output_dir=root,
    )
    prompt = "Return fixture JSON."
    prepared = ledger.prepare(
        logical_request_index=0,
        request_kind="final_answer",
        public_attempt_phase="primary",
        primary_prompt=prompt,
        prompt=prompt,
        public_state_id=None,
        abi_rescue_count_before=1,
        semantic_recovery_count_before=1,
    )
    try:
        ledger.invoke(prepared)
    except runner.InstrumentContractError:
        return False, ledger.cumulative_tokens, ledger
    return True, ledger.cumulative_tokens, ledger


def _build_fixtures(
    static: SemanticActionStaticInputs,
    contract: runner.SemanticActionRunnerContract,
) -> tuple[
    RunnerFixtureAudit,
    SemanticRecoveryControlAudit,
    CertificateUsageRecoveryAudit,
]:
    raws: list[runner.SemanticActionRawExecution] = []
    rows: list[RunnerFixtureRow] = []
    certificates = 0
    parent_pass = 0
    privacy_pass = 0
    exact_payloads = 0
    with tempfile.TemporaryDirectory(prefix="v26_119_runner_fixture_") as temporary:
        root = Path(temporary)
        for job in sorted(static.manifest.jobs, key=lambda item: item.job_id):
            binding = runner.semantic_action_runtime_binding(static, job)
            client = ScriptedSemanticActionClient(
                static.agent_model_config,
                final_answer=binding.compiler_trajectory.final_answer,
            )
            raw = runner.execute_semantic_action_job_raw(
                job=job,
                runner_contract=contract,
                static=static,
                binding=binding,
                client=client,
                output_dir=root,
            )
            expected_observations = exact_preflight.legacy_preflight._compiler_observations(binding)
            replay = legacy.replay_v3(
                raw,
                static=static.historical,
                binding=binding,
            )
            verification, mechanism = _completed_verification(
                raw=raw, replay=replay, binding=binding
            )
            if (
                raw.terminal_disposition != "completed"
                or exact_preflight.legacy_preflight._observation_semantic_projection(
                    raw.observations
                )
                != exact_preflight.legacy_preflight._observation_semantic_projection(
                    expected_observations
                )
                or raw.completed_result is None
                or raw.completed_result.answer != binding.compiler_trajectory.final_answer
                or not replay.passed
                or not verification.valid
                or not mechanism.success
                or raw.semantic_rejections
            ):
                raise ValueError(f"v26.119 direct Runner fixture failed: {job.job_id}")
            job_payloads = 0
            for descriptor in raw.provider_call_artifacts:
                provider = runner.RawActionProviderCall.model_validate(
                    legacy.load_canonical_json(root / descriptor.relative_path)
                )
                certificates += 1
                parent_pass += int(
                    provider.runner_contract_id == contract.contract_id
                    and provider.job_id == job.job_id
                    and provider.dynamic_certificate.job_id == job.job_id
                    and provider.request_binding_certificate.prompt_sha256 == provider.prompt_sha256
                )
                privacy_pass += int(
                    not provider.private_reasoning_content_persisted
                    and not provider.private_reasoning_content_hashed
                    and not provider.raw_http_body_persisted
                    and not provider.raw_request_body_persisted
                )
                if provider.request_kind == "semantic_proposal":
                    payload = provider.response_payload or {}
                    if (
                        set(payload) != {"state_id", "action_id", "decision_kind", "protocol"}
                        or payload.get("protocol") != RESPONSE_PROTOCOL_VERSION
                    ):
                        raise ValueError("v26.119 scripted payload is not exact four-field")
                    exact_payloads += 1
                    job_payloads += 1
            rows.append(
                RunnerFixtureRow(
                    job_id=job.job_id,
                    raw_execution_id=raw.artifact_id,
                    stage_one_provider_call_count=raw.stage_one_provider_call_count,
                    semantic_payload_count=job_payloads,
                    semantic_choice_count=len(raw.semantic_choices),
                    stage_two_commit_count=len(raw.commits),
                    observation_count=len(raw.observations),
                )
            )
            raws.append(raw)
        sample = raws[0]
        binding = runner.semantic_action_runtime_binding(static, sample.job)
        recovered = runner.execute_semantic_action_job_raw(
            job=sample.job,
            runner_contract=contract,
            static=static,
            binding=binding,
            client=None,
            output_dir=root,
        )
        orphan_root = root / "orphan_control"
        orphan_path = runner.raw_provider_path(orphan_root, sample.job, 0)
        orphan_path.parent.mkdir(parents=True, exist_ok=True)
        orphan_path.write_text("{}\n", encoding="utf-8")
        try:
            runner.execute_semantic_action_job_raw(
                job=sample.job,
                runner_contract=contract,
                static=static,
                binding=binding,
                client=None,
                output_dir=orphan_root,
            )
        except ValueError:
            orphan_rejected = True
        else:
            orphan_rejected = False
        control_client = ScriptedSemanticActionClient(static.agent_model_config)
        ledger = runner.JournaledSemanticActionClient(
            control_client,
            runner_contract=contract,
            resource_contract=static.resource,
            job=sample.job,
            output_dir=root / "precall_controls",
        )
        oversized = ledger.prepare(
            logical_request_index=0,
            request_kind="semantic_proposal",
            public_attempt_phase="primary",
            primary_prompt="x" * 60001,
            prompt="x" * 60001,
            public_state_id="fixture-state",
            abi_rescue_count_before=0,
            semantic_recovery_count_before=0,
        )
        before = control_client.call_count
        try:
            ledger.invoke(oversized)
        except Exception:
            pass
        oversized_rejected = control_client.call_count == before
        prompt = "Return fixture JSON."
        reusable = ledger.prepare(
            logical_request_index=1,
            request_kind="final_answer",
            public_attempt_phase="primary",
            primary_prompt=prompt,
            prompt=prompt,
            public_state_id=None,
            abi_rescue_count_before=1,
            semantic_recovery_count_before=1,
        )
        ledger.invoke(reusable)
        try:
            ledger.invoke(reusable)
        except runner.InstrumentContractError:
            reuse_rejected = True
        else:
            reuse_rejected = False
        budget_client = ScriptedSemanticActionClient(
            static.agent_model_config, completion_tokens=16385
        )
        budget_ledger = runner.JournaledSemanticActionClient(
            budget_client,
            runner_contract=contract,
            resource_contract=static.resource,
            job=sample.job,
            output_dir=root / "budget_control",
        )
        large_prompt = "b" * 59000
        budget_denied = False
        for index in range(8):
            prepared = budget_ledger.prepare(
                logical_request_index=index,
                request_kind="final_answer",
                public_attempt_phase="primary",
                primary_prompt=large_prompt,
                prompt=large_prompt,
                public_state_id=None,
                abi_rescue_count_before=1,
                semantic_recovery_count_before=1,
            )
            try:
                budget_ledger.invoke(prepared)
            except Exception:
                budget_denied = not prepared.resource_certificate.provider_call_permitted
                break
        admitted_16384, charged_16384, _ = _single_ledger_call(
            static, contract, sample.job, root / "usage_16384", 16384
        )
        admitted_16385, charged_16385, _ = _single_ledger_call(
            static, contract, sample.job, root / "usage_16385", 16385
        )
        admitted_16386, _, failed_ledger = _single_ledger_call(
            static, contract, sample.job, root / "usage_16386", 16386
        )
        recovery_sample = next(
            item for item in raws if item.semantic_choices[0].public_progress_after_commit is True
        )
        recovery_binding = runner.semantic_action_runtime_binding(static, recovery_sample.job)
        recovery_root = root / "combined_recovery"
        recovery_client = ScriptedSemanticActionClient(
            static.agent_model_config,
            final_answer=recovery_binding.compiler_trajectory.final_answer,
            combined_recovery_control=True,
        )
        recovery_raw = runner.execute_semantic_action_job_raw(
            job=recovery_sample.job,
            runner_contract=contract,
            static=static,
            binding=recovery_binding,
            client=recovery_client,
            output_dir=recovery_root,
        )
        recovery_choices = tuple(
            item
            for item in recovery_raw.semantic_choices
            if item.public_attempt_phase == "semantic_recovery"
        )
        recovery_providers = tuple(
            runner.RawActionProviderCall.model_validate(
                legacy.load_canonical_json(recovery_root / item.relative_path)
            )
            for item in recovery_raw.provider_call_artifacts
        )
        semantic_provider = next(
            item for item in recovery_providers if item.public_attempt_phase == "semantic_recovery"
        )
        rejection = recovery_raw.semantic_rejections[0]
        recovery_values = {
            "runner_contract_id": contract.contract_id,
            "recovery_public_progress_count": sum(
                item.public_progress_after_commit is True for item in recovery_choices
            ),
            "completed_after_recovery_count": int(recovery_raw.terminal_disposition == "completed"),
            "abi_count_before_semantic_recovery": (
                semantic_provider.dynamic_certificate.abi_rescue_count_before
            ),
            "semantic_count_before_semantic_recovery": (
                semantic_provider.dynamic_certificate.semantic_recovery_count_before
            ),
            "correct_action_id_exposed_count": int(
                rejection.correct_tool_exposed
                or rejection.correct_node_exposed
                or rejection.correct_operator_exposed
                or rejection.correct_operand_exposed
                or rejection.correct_evidence_exposed
            ),
        }
        recovery_provisional = SemanticRecoveryControlAudit.model_construct(
            audit_id="pending", **recovery_values
        )
        recovery_audit = SemanticRecoveryControlAudit(
            audit_id=_identity(
                recovery_provisional,
                "audit_id",
                "finance_v26_semantic_recovery_runner_control:",
            ),
            **recovery_values,
        )
        certificate_values = {
            "runner_contract_id": contract.contract_id,
            "complete_raw_recovery_byte_identical": recovered == sample,
            "orphan_provider_artifact_rejected": orphan_rejected,
            "oversized_prompt_rejected_before_provider": oversized_rejected,
            "reused_preparation_rejected": reuse_rejected,
            "insufficient_remaining_budget_rejected_before_provider": budget_denied,
            "completion_16384_admitted": admitted_16384 and charged_16384 > 16384,
            "completion_16385_admitted_and_charged": (
                admitted_16385 and charged_16385 > charged_16384
            ),
            "completion_16386_instrument_failure": not admitted_16386,
            "calls_blocked_after_instrument_failure": bool(failed_ledger.instrument_failures),
            "raw_provider_certificate_triple_count": certificates,
            "certificate_parent_binding_pass_count": parent_pass,
            "privacy_pass_count": privacy_pass,
        }
    fixture_values = {
        "runner_contract_id": contract.contract_id,
        "rows": tuple(rows),
        "fixture_aggregate_sha256": _fixture_hash(raws),
    }
    fixture_provisional = RunnerFixtureAudit.model_construct(audit_id="pending", **fixture_values)
    fixture = RunnerFixtureAudit(
        audit_id=_identity(
            fixture_provisional,
            "audit_id",
            "finance_v26_semantic_action_runner_fixture:",
        ),
        **fixture_values,
    )
    certificate_provisional = CertificateUsageRecoveryAudit.model_construct(
        audit_id="pending", **certificate_values
    )
    certificate = CertificateUsageRecoveryAudit(
        audit_id=_identity(
            certificate_provisional,
            "audit_id",
            "finance_v26_semantic_action_certificate_usage_recovery:",
        ),
        **certificate_values,
    )
    if exact_payloads != 224:
        raise ValueError("v26.119 exact four-field payload denominator changed")
    return fixture, recovery_audit, certificate


def _expect_rejection(name: str, action: Any) -> MutationResult:
    try:
        action()
    except (ValueError, TypeError, runner.InstrumentContractError):
        return MutationResult(name=name)
    raise ValueError(f"v26.119 destructive mutation passed: {name}")


def _build_destructive(
    static: SemanticActionStaticInputs,
    contract: runner.SemanticActionRunnerContract,
) -> DestructiveRunnerAudit:
    sample = static.manifest.jobs[0]
    binding = runner.semantic_action_runtime_binding(static, sample)
    state = build_semantic_action_state(
        binding.record.task_package.task.public, binding.environment, ()
    )
    prompt = render_exact_canonical_action_prompt(
        instruction=binding.record.task_package.task.public.instruction,
        state=state,
        public_path_condition=None,
        presentation_salt="destructive-control",
        grammar=static.grammar,
    )
    proposal = parse_exact_canonical_action_payload(prompt_only_reference_payload(prompt))
    selected = state.action_candidates[0]
    rejection_result = evaluate_canonical_action_proposal(
        state,
        make_canonical_action_proposal(
            state_id=state.state_id,
            action_id="prospective_canonical_public_action:" + "f" * 64,
            decision_kind=selected.decision_kind,
        ),
        call_index=1,
    )
    if rejection_result.rejection is None:
        raise ValueError("v26.119 rejection mutation fixture failed")
    rejection = rejection_result.rejection

    def stale(model: BaseModel, **updates: Any) -> BaseModel:
        payload = model.model_dump(mode="json")
        payload.update(updates)
        return type(model).model_validate(payload)

    def invalid_config(**updates: Any) -> None:
        payload = static.agent_model_config.model_dump(mode="json")
        payload.update(updates)
        legacy.require_stage_one_model_config(
            type(static.agent_model_config).model_validate(payload)
        )

    mutations = (
        _expect_rejection(
            "abi_semantic_counters_coupled",
            lambda: stale(contract, abi_and_semantic_recovery_counters_separate=False),
        ),
        _expect_rejection(
            "early_empirical_authorization",
            lambda: stale(contract, empirical_execution_authorized=True),
        ),
        _expect_rejection(
            "job_contract_parent_changed",
            lambda: stale(sample, contract_id="finance_v26_semantic_action_execution_contract:x"),
        ),
        _expect_rejection(
            "private_reasoning_persistence",
            lambda: runner.SemanticActionRawExecution.model_validate(
                {
                    **_minimal_raw_for_mutation(static, contract, sample),
                    "private_reasoning_content_persisted": True,
                }
            ),
        ),
        _expect_rejection(
            "rejection_exposes_correct_action",
            lambda: stale(rejection, correct_tool_exposed=True),
        ),
        _expect_rejection(
            "rejection_terminates_job",
            lambda: stale(rejection, job_terminal=True),
        ),
        _expect_rejection(
            "response_extra_field",
            lambda: parse_exact_canonical_action_payload(
                {**exact_canonical_action_payload(proposal), "stage": "stage_1"}
            ),
        ),
        _expect_rejection(
            "response_protocol_changed",
            lambda: parse_exact_canonical_action_payload(
                {**exact_canonical_action_payload(proposal), "protocol": "changed"}
            ),
        ),
        _expect_rejection(
            "runner_manifest_parent_changed",
            lambda: stale(contract, predecessor_manifest_id="changed"),
        ),
        _expect_rejection(
            "runner_static_contract_parent_changed",
            lambda: stale(contract, predecessor_static_contract_id="changed"),
        ),
        _expect_rejection(
            "stage_two_provider_route",
            lambda: stale(contract, stage_two_provider_call_upper_bound=1),
        ),
        _expect_rejection(
            "thinking_disabled",
            lambda: invalid_config(
                request_body_overrides={"thinking": {"type": "disabled"}, "top_p": 0.9}
            ),
        ),
        _expect_rejection(
            "unknown_job_identity",
            lambda: stale(sample, job_id="finance_v26_semantic_action_job:unknown"),
        ),
        _expect_rejection(
            "wrong_completion_bound",
            lambda: invalid_config(max_output_tokens=32768),
        ),
        _expect_rejection(
            "wrong_model",
            lambda: invalid_config(model="deepseek-v4-pro"),
        ),
        _expect_rejection(
            "wrong_response_grammar",
            lambda: stale(contract, response_grammar_id="changed"),
        ),
    )
    values = {"mutations": tuple(sorted(mutations, key=lambda item: item.name))}
    provisional = DestructiveRunnerAudit.model_construct(audit_id="pending", **values)
    return DestructiveRunnerAudit(
        audit_id=_identity(
            provisional,
            "audit_id",
            "finance_v26_semantic_action_runner_destructive:",
        ),
        **values,
    )


def _minimal_raw_for_mutation(
    static: SemanticActionStaticInputs,
    contract: runner.SemanticActionRunnerContract,
    sample: Any,
) -> dict[str, Any]:
    binding = runner.semantic_action_runtime_binding(static, sample)
    client = ScriptedSemanticActionClient(
        static.agent_model_config,
        final_answer=binding.compiler_trajectory.final_answer,
    )
    with tempfile.TemporaryDirectory(prefix="v26_119_raw_mutation_") as temporary:
        raw = runner.execute_semantic_action_job_raw(
            job=sample,
            runner_contract=contract,
            static=static,
            binding=binding,
            client=client,
            output_dir=Path(temporary),
        )
    return raw.model_dump(mode="json")


def _detail(path: Path, output_dir: Path) -> DetailFile:
    return DetailFile(
        relative_path=str(path.relative_to(output_dir)),
        sha256=legacy.sha256_file(path),
        byte_count=path.stat().st_size,
    )


def build(
    *,
    package_root: Path,
    implementation_root: Path,
    output_dir: Path,
) -> SemanticActionRunnerPreflightReport:
    replay = _build_source_replay(package_root, implementation_root)
    static = load_semantic_action_static_inputs(package_root, implementation_root)
    if (
        static.report.report_id != EXPECTED_V26_118_REPORT_ID
        or static.contract.contract_id != EXPECTED_V26_118_CONTRACT_ID
        or static.manifest.manifest_id != EXPECTED_V26_118_MANIFEST_ID
        or static.resource.contract_id != EXPECTED_V26_118_RESOURCE_ID
        or static.grammar.grammar_id != EXPECTED_RESPONSE_GRAMMAR_ID
    ):
        raise ValueError("v26.119 exact static identity chain changed")
    contract = runner.make_semantic_action_runner_contract(static)
    binding_values = {"runner_contract_id": contract.contract_id}
    binding_provisional = RunnerBindingAudit.model_construct(audit_id="pending", **binding_values)
    binding = RunnerBindingAudit(
        audit_id=_identity(
            binding_provisional,
            "audit_id",
            "finance_v26_semantic_action_runner_binding:",
        ),
        **binding_values,
    )
    fixture, recovery, certificate = _build_fixtures(static, contract)
    outcome_provisional = OutcomeMeasurementContract.model_construct(
        contract_id="pending", runner_contract_id=contract.contract_id
    )
    outcome = OutcomeMeasurementContract(
        contract_id=_identity(
            outcome_provisional,
            "contract_id",
            "finance_v26_semantic_action_outcome_measurement:",
        ),
        runner_contract_id=contract.contract_id,
    )
    destructive = _build_destructive(static, contract)
    transition_provisional = ProspectiveTransitionContract.model_construct(contract_id="pending")
    transition = ProspectiveTransitionContract(
        contract_id=_identity(
            transition_provisional,
            "contract_id",
            "finance_v26_semantic_action_runner_transition:",
        )
    )
    outputs: tuple[tuple[str, BaseModel], ...] = (
        ("source_replay_audit.json", replay),
        ("runner_contract.json", contract),
        ("runner_binding_audit.json", binding),
        ("runner_fixture_audit.json", fixture),
        ("semantic_recovery_control_audit.json", recovery),
        ("certificate_usage_recovery_audit.json", certificate),
        ("outcome_measurement_contract.json", outcome),
        ("destructive_runner_audit.json", destructive),
        ("prospective_transition_contract.json", transition),
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    for name, value in outputs:
        _write_json(output_dir / name, value)
    details = tuple(_detail(output_dir / name, output_dir) for name, _ in outputs)
    values = {
        "source_replay_audit_id": replay.audit_id,
        "runner_contract_id": contract.contract_id,
        "runner_binding_audit_id": binding.audit_id,
        "runner_fixture_audit_id": fixture.audit_id,
        "semantic_recovery_control_audit_id": recovery.audit_id,
        "certificate_usage_recovery_audit_id": certificate.audit_id,
        "outcome_measurement_contract_id": outcome.contract_id,
        "destructive_runner_audit_id": destructive.audit_id,
        "transition_contract_id": transition.contract_id,
        "detail_files": details,
    }
    provisional = SemanticActionRunnerPreflightReport.model_construct(report_id="pending", **values)
    report = SemanticActionRunnerPreflightReport(
        report_id=_identity(
            provisional,
            "report_id",
            "finance_v26_semantic_action_runner_preflight_report:",
        ),
        **values,
    )
    _write_json(output_dir / "report.json", report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Credential-free v26.119 Semantic Action Runner preflight"
    )
    parser.add_argument("--package-root", type=Path, default=Path(__file__).resolve().parents[4])
    parser.add_argument(
        "--implementation-root", type=Path, default=Path(__file__).resolve().parents[4]
    )
    parser.add_argument("--output-dir", type=Path, default=Path(OUTPUT_DIR))
    args = parser.parse_args()
    report = build(
        package_root=args.package_root,
        implementation_root=args.implementation_root,
        output_dir=args.output_dir,
    )
    print(report.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
