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
    phase1_v26_two_stage_semantic_proposal_execution as legacy,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_two_stage_semantic_proposal_runner_preflight as legacy_preflight,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_exact_response_grammar_execution import (  # noqa: E501
    EXPECTED_RESPONSE_GRAMMAR_ID,
    EXPECTED_V26_112_CONTRACT_ID,
    EXPECTED_V26_112_MANIFEST_ID,
    EXPECTED_V26_112_REPORT_ID,
    _active_exact_outcome,
    execute_exact_grammar_job_raw,
    load_exact_grammar_static_inputs,
    make_exact_grammar_runner_contract,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_two_stage_semantic_proposal_calibration_execution import (  # noqa: E501
    _completed_verification,
)
from trusted_synthesis.hashing import canonical_hash
from trusted_synthesis.runtime.agent.prospective_action_constructibility import (
    build_public_action_state,
    decompile_public_call,
    make_semantic_decision_proposal,
)
from trusted_synthesis.runtime.agent.prospective_two_stage_exact_response_grammar import (
    EXACT_RESPONSE_PROTOCOL_VERSION,
    exact_semantic_proposal_payload,
    prompt_only_reference_payload,
    public_action_state_from_exact_prompt,
    render_exact_semantic_proposal_prompt,
)
from trusted_synthesis.runtime.agent.prospective_two_stage_semantic_proposal import (
    final_answer_payload,
)
from trusted_synthesis.runtime.tools import AgentToolCall

RUN_ID: Final = "finance_v26_113_exact_response_grammar_runner_preflight_v1_20260823"
NEXT_STAGE: Final = "exact_response_grammar_calibration_execution_only"
V26_112_DIR: Final = (
    "artifacts/vtdo_experiment/finance_v26_112_exact_response_grammar_rematerialization_v1_20260823"
)
IMPLEMENTATION_PATHS: Final = (
    "src/trusted_synthesis/experiments/vtdo_experiment/"
    "phase1_v26_exact_response_grammar_execution.py",
    "src/trusted_synthesis/experiments/vtdo_experiment/"
    "phase1_v26_exact_response_grammar_runner_preflight.py",
)
V26_112_OUTPUTS: Final = (
    "cross_artifact_binding_audit.json",
    "destructive_preflight_audit.json",
    "report.json",
    "response_constructibility_audit.json",
    "source_replay_audit.json",
    "stage_one_response_grammar.json",
    "two_stage_execution_contract.json",
    "two_stage_job_manifest.json",
    "two_stage_path_audits.json",
    "two_stage_task_packages.json",
)


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class SourceReplayEntry(FrozenModel):
    relative_path: str = Field(min_length=1)
    source_kind: Literal["v26_112_transitive_source", "v26_112_output", "v26_113_implementation"]
    expected_sha256: str = Field(min_length=64, max_length=64)
    observed_sha256: str = Field(min_length=64, max_length=64)
    byte_count: int = Field(gt=0)
    passed: Literal[True] = True

    @model_validator(mode="after")
    def validate_entry(self) -> SourceReplayEntry:
        if self.expected_sha256 != self.observed_sha256:
            raise ValueError("v26.113 source replay changed")
        return self


class RunnerSourceReplayAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    predecessor_report_id: str = EXPECTED_V26_112_REPORT_ID
    entries: tuple[SourceReplayEntry, ...] = Field(min_length=2041, max_length=2041)
    predecessor_transitive_file_count: Literal[2029] = 2029
    predecessor_output_file_count: Literal[10] = 10
    implementation_file_count: Literal[2] = 2
    replayed_file_count: Literal[2041] = 2041
    replay_pass_count: Literal[2041] = 2041
    replay_before_profile_parsing: Literal[True] = True
    replay_before_credential_lookup: Literal[True] = True
    replay_before_client_construction: Literal[True] = True
    credential_lookup_attempted: Literal[False] = False
    model_client_constructed: Literal[False] = False
    provider_calls: Literal[0] = 0
    gpu_jobs: Literal[0] = 0
    schema_version: Literal["finance_v26_exact_grammar_runner_source_replay.v1"] = (
        "finance_v26_exact_grammar_runner_source_replay.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> RunnerSourceReplayAudit:
        paths = tuple(item.relative_path for item in self.entries)
        if paths != tuple(sorted(set(paths))):
            raise ValueError("v26.113 source replay paths are not canonical")
        if self.audit_id != _identity(
            self, "audit_id", "finance_v26_exact_grammar_runner_source_replay:"
        ):
            raise ValueError("v26.113 source replay identity changed")
        return self


class RunnerBindingAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    runner_contract_id: str = Field(min_length=1)
    static_contract_id: str = EXPECTED_V26_112_CONTRACT_ID
    manifest_id: str = EXPECTED_V26_112_MANIFEST_ID
    response_grammar_id: str = EXPECTED_RESPONSE_GRAMMAR_ID
    response_protocol: Literal["prospective_two_stage_stage_one_exact_response.v2"] = (
        EXACT_RESPONSE_PROTOCOL_VERSION
    )
    model: Literal["deepseek-v4-flash"] = "deepseek-v4-flash"
    max_tokens: Literal[16384] = 16384
    thinking_type: Literal["enabled"] = "enabled"
    response_format_type: Literal["json_object"] = "json_object"
    fallback_count: Literal[0] = 0
    discovery_enabled: Literal[False] = False
    stage_two_provider_call_upper_bound: Literal[0] = 0
    exact_grammar_primary_and_rescue_required: Literal[True] = True
    ordinary_uncertified_entrypoint_allowed: Literal[False] = False
    credential_lookup_attempted: Literal[False] = False
    real_client_constructed: Literal[False] = False
    provider_calls: Literal[0] = 0
    schema_version: Literal["finance_v26_exact_grammar_runner_binding.v1"] = (
        "finance_v26_exact_grammar_runner_binding.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> RunnerBindingAudit:
        if self.audit_id != _identity(
            self, "audit_id", "finance_v26_exact_grammar_runner_binding:"
        ):
            raise ValueError("v26.113 Runner binding identity changed")
        return self


class RunnerFixtureRow(FrozenModel):
    job_id: str = Field(min_length=1)
    raw_execution_id: str = Field(min_length=1)
    stage_one_provider_call_count: int = Field(gt=0)
    stage_two_commit_count: int = Field(gt=0)
    observation_count: int = Field(gt=0)
    exact_grammar_payload_count: int = Field(gt=0)
    replay_v3_passed: Literal[True] = True
    independent_validity_passed: Literal[True] = True
    mechanism_score_passed: Literal[True] = True
    requested_path_preserved: Literal[True] = True
    final_answer_preserved: Literal[True] = True


class RunnerFixtureAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    runner_contract_id: str = Field(min_length=1)
    response_grammar_id: str = EXPECTED_RESPONSE_GRAMMAR_ID
    rows: tuple[RunnerFixtureRow, ...] = Field(min_length=32, max_length=32)
    job_count: Literal[32] = 32
    stage_one_scripted_provider_call_count: Literal[256] = 256
    semantic_proposal_payload_count: Literal[224] = 224
    exact_grammar_payload_count: Literal[224] = 224
    stage_two_commit_count: Literal[224] = 224
    public_observation_count: Literal[192] = 192
    dynamic_certificate_count: Literal[256] = 256
    exact_request_certificate_count: Literal[256] = 256
    resource_certificate_count: Literal[256] = 256
    raw_provider_artifact_count: Literal[256] = 256
    replay_v3_pass_count: Literal[32] = 32
    independent_validity_pass_count: Literal[32] = 32
    mechanism_success_count: Literal[32] = 32
    final_answer_match_count: Literal[32] = 32
    requested_path_match_count: Literal[32] = 32
    stage_two_provider_call_count: Literal[0] = 0
    real_provider_call_count: Literal[0] = 0
    fixture_aggregate_sha256: str = Field(min_length=64, max_length=64)
    schema_version: Literal["finance_v26_exact_grammar_runner_fixture.v1"] = (
        "finance_v26_exact_grammar_runner_fixture.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> RunnerFixtureAudit:
        if self.audit_id != _identity(
            self, "audit_id", "finance_v26_exact_grammar_runner_fixture:"
        ):
            raise ValueError("v26.113 Runner fixture identity changed")
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
    rescue_blocked_after_instrument_failure: Literal[True] = True
    serialization_rescue_accepted: Literal[True] = True
    rescue_uses_exact_response_protocol: Literal[True] = True
    raw_provider_certificate_triple_count: Literal[256] = 256
    certificate_parent_binding_pass_count: Literal[256] = 256
    privacy_pass_count: Literal[256] = 256
    stage_two_provider_call_count: Literal[0] = 0
    real_provider_call_count: Literal[0] = 0
    schema_version: Literal["finance_v26_exact_grammar_certificate_usage_recovery.v1"] = (
        "finance_v26_exact_grammar_certificate_usage_recovery.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> CertificateUsageRecoveryAudit:
        if self.audit_id != _identity(
            self, "audit_id", "finance_v26_exact_grammar_certificate_usage_recovery:"
        ):
            raise ValueError("v26.113 certificate/recovery identity changed")
        return self


class MutationResult(FrozenModel):
    mutation_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    rejected: Literal[True] = True
    provider_calls: Literal[0] = 0
    stage_two_provider_calls: Literal[0] = 0

    @model_validator(mode="after")
    def validate_result(self) -> MutationResult:
        if self.mutation_id != _identity(
            self, "mutation_id", "finance_v26_exact_grammar_runner_mutation:"
        ):
            raise ValueError("v26.113 mutation identity changed")
        return self


class DestructiveRunnerAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    mutations: tuple[MutationResult, ...] = Field(min_length=10, max_length=10)
    mutation_count: Literal[10] = 10
    rejection_count: Literal[10] = 10
    provider_calls: Literal[0] = 0
    stage_two_provider_calls: Literal[0] = 0
    status: Literal["passed"] = "passed"
    schema_version: Literal["finance_v26_exact_grammar_runner_destructive.v1"] = (
        "finance_v26_exact_grammar_runner_destructive.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> DestructiveRunnerAudit:
        if self.audit_id != _identity(
            self, "audit_id", "finance_v26_exact_grammar_runner_destructive:"
        ):
            raise ValueError("v26.113 destructive identity changed")
        return self


class DetailFile(FrozenModel):
    relative_path: str = Field(min_length=1)
    sha256: str = Field(min_length=64, max_length=64)
    byte_count: int = Field(gt=0)


class ExactGrammarRunnerPreflightReport(FrozenModel):
    report_id: str = Field(min_length=1)
    run_id: str = RUN_ID
    predecessor_report_id: str = EXPECTED_V26_112_REPORT_ID
    source_replay_audit_id: str = Field(min_length=1)
    response_grammar_id: str = EXPECTED_RESPONSE_GRAMMAR_ID
    runner_contract_id: str = Field(min_length=1)
    runner_binding_audit_id: str = Field(min_length=1)
    runner_fixture_audit_id: str = Field(min_length=1)
    certificate_usage_recovery_audit_id: str = Field(min_length=1)
    destructive_runner_audit_id: str = Field(min_length=1)
    detail_files: tuple[DetailFile, ...] = Field(min_length=6, max_length=6)
    status: Literal["exact_response_grammar_runner_preflight_passed"] = (
        "exact_response_grammar_runner_preflight_passed"
    )
    next_permitted_stage: str = NEXT_STAGE
    exact_job_denominator: Literal[32] = 32
    model_profile_changed: Literal[False] = False
    completion_bound_changed: Literal[False] = False
    rollout_bound_changed: Literal[False] = False
    public_action_state_changed: Literal[False] = False
    stage_two_compiler_changed: Literal[False] = False
    task_or_seed_selection_changed: Literal[False] = False
    credential_lookup_attempted: Literal[False] = False
    real_model_client_constructed: Literal[False] = False
    real_provider_calls: Literal[0] = 0
    stage_two_provider_calls: Literal[0] = 0
    gpu_jobs: Literal[0] = 0
    empirical_rows: Literal[0] = 0
    execution_authorized: Literal[True] = True
    role_experiment_authorized: Literal[False] = False
    state_mapping_authorized: Literal[False] = False
    production_contribution: Literal[0] = 0
    schema_version: Literal["finance_v26_exact_grammar_runner_preflight_report.v1"] = (
        "finance_v26_exact_grammar_runner_preflight_report.v1"
    )

    @model_validator(mode="after")
    def validate_report(self) -> ExactGrammarRunnerPreflightReport:
        paths = tuple(item.relative_path for item in self.detail_files)
        if paths != tuple(sorted(set(paths))):
            raise ValueError("v26.113 report details are not canonical")
        if self.report_id != _identity(
            self, "report_id", "finance_v26_exact_grammar_runner_preflight_report:"
        ):
            raise ValueError("v26.113 report identity changed")
        return self


def _identity(value: BaseModel, field: str, prefix: str) -> str:
    payload = value.model_dump(mode="json")
    payload.pop(field, None)
    return canonical_hash(payload, prefix=prefix)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = value.model_dump(mode="json") if isinstance(value, BaseModel) else value
    path.write_text(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
        encoding="utf-8",
    )


def _build_source_replay(package_root: Path, implementation_root: Path) -> RunnerSourceReplayAudit:
    predecessor_root = implementation_root / V26_112_DIR
    report = _load_json(predecessor_root / "report.json")
    replay = _load_json(predecessor_root / "source_replay_audit.json")
    if report["report_id"] != EXPECTED_V26_112_REPORT_ID:
        raise ValueError("v26.113 predecessor report changed")
    entries: dict[str, SourceReplayEntry] = {}
    for item in replay["entries"]:
        relative = item["relative_path"]
        path = package_root / relative
        if not path.is_file():
            path = implementation_root / relative
        observed = _sha256(path)
        entries[relative] = SourceReplayEntry(
            relative_path=relative,
            source_kind="v26_112_transitive_source",
            expected_sha256=item["observed_sha256"],
            observed_sha256=observed,
            byte_count=path.stat().st_size,
        )
    for name in V26_112_OUTPUTS:
        relative = f"{V26_112_DIR}/{name}"
        path = implementation_root / relative
        digest = _sha256(path)
        entries[relative] = SourceReplayEntry(
            relative_path=relative,
            source_kind="v26_112_output",
            expected_sha256=digest,
            observed_sha256=digest,
            byte_count=path.stat().st_size,
        )
    for relative in IMPLEMENTATION_PATHS:
        path = implementation_root / relative
        digest = _sha256(path)
        entries[relative] = SourceReplayEntry(
            relative_path=relative,
            source_kind="v26_113_implementation",
            expected_sha256=digest,
            observed_sha256=digest,
            byte_count=path.stat().st_size,
        )
    values = {"entries": tuple(entries[key] for key in sorted(entries))}
    provisional = RunnerSourceReplayAudit.model_construct(audit_id="pending", **values)
    return RunnerSourceReplayAudit(
        audit_id=_identity(
            provisional,
            "audit_id",
            "finance_v26_exact_grammar_runner_source_replay:",
        ),
        **values,
    )


class ScriptedExactGrammarClient:
    def __init__(
        self,
        config: legacy_preflight.AgentModelConfig,
        *,
        compiler_calls: Sequence[AgentToolCall] = (),
        final_answer: Mapping[str, Any] | None = None,
        queued_payloads: Sequence[Mapping[str, Any]] = (),
        completion_tokens: int = 64,
    ) -> None:
        self.config = config
        self._compiler_calls = tuple(compiler_calls)
        self._final_answer = dict(final_answer or {"value": "fixture"})
        self._queued_payloads = [dict(item) for item in queued_payloads]
        self._completion_tokens = completion_tokens
        self._semantic_index = 0
        self.call_count = 0

    def complete_json_certified(
        self,
        prompt: str,
        certificate: legacy_preflight.StageOneRequestBindingCertificate,
    ) -> tuple[dict[str, Any], legacy_preflight.ModelCallTelemetry]:
        expected = legacy_preflight.certify_stage_one_request_pre_call(
            config=self.config,
            prompt=prompt,
            request_kind=certificate.request_kind,
            phase=certificate.phase,
        )
        if expected != certificate:
            raise legacy.LLMClientError("scripted exact-Grammar certificate changed")
        if self._queued_payloads:
            payload = self._queued_payloads.pop(0)
        elif certificate.request_kind == "final_answer":
            payload = final_answer_payload(self._final_answer)
        elif certificate.phase == "rescue":
            payload = prompt_only_reference_payload(prompt)
        else:
            state = public_action_state_from_exact_prompt(prompt)
            if self._semantic_index < len(self._compiler_calls):
                proposal = decompile_public_call(state, self._compiler_calls[self._semantic_index])
                self._semantic_index += 1
            else:
                proposal = make_semantic_decision_proposal(
                    state_id=state.state_id, decision_kind="emit_final_answer"
                )
            payload = exact_semantic_proposal_payload(proposal)
        prompt_tokens = len(prompt.encode("utf-8"))
        completion_tokens = self._completion_tokens
        self.call_count += 1
        telemetry = legacy_preflight.ModelCallTelemetry(
            provider="deepseek",
            endpoint_host="api.deepseek.com",
            model_requested=legacy_preflight.STAGE_ONE_MODEL_ID,
            model_selected=legacy_preflight.STAGE_ONE_MODEL_ID,
            response_model=legacy_preflight.STAGE_ONE_MODEL_ID,
            request_hash=legacy.sha256_text(prompt),
            response_hash=canonical_hash(payload, prefix="scripted_exact_grammar_response:"),
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


def _compiler_calls(binding: Any) -> tuple[AgentToolCall, ...]:
    return legacy_preflight._compiler_calls(binding)


def _fixture_hash(raws: Sequence[legacy.TwoStageRawExecution]) -> str:
    payload = [item.model_dump(mode="json") for item in raws]
    return hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
    ).hexdigest()


def _single_ledger_call(
    static: legacy.TwoStageStaticInputs,
    contract: legacy.TwoStageRunnerContract,
    job: legacy.TwoStageJob,
    root: Path,
    completion_tokens: int,
) -> tuple[bool, int, legacy.JournaledStageOneClient]:
    client = ScriptedExactGrammarClient(
        static.agent_model_config, completion_tokens=completion_tokens
    )
    ledger = legacy.JournaledStageOneClient(
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
        phase="primary",
        primary_prompt=prompt,
        prompt=prompt,
        public_state_id=None,
        rescue_available_before=False,
    )
    try:
        ledger.invoke(prepared)
    except legacy.InstrumentContractError:
        return False, ledger.cumulative_tokens, ledger
    return True, ledger.cumulative_tokens, ledger


def _build_fixture_and_controls(
    static: legacy.TwoStageStaticInputs,
    contract: legacy.TwoStageRunnerContract,
) -> tuple[RunnerFixtureAudit, CertificateUsageRecoveryAudit]:
    raws: list[legacy.TwoStageRawExecution] = []
    rows: list[RunnerFixtureRow] = []
    certificate_count = 0
    parent_pass = 0
    privacy_pass = 0
    exact_payloads = 0
    with tempfile.TemporaryDirectory(prefix="v26_113_runner_fixture_") as temporary:
        root = Path(temporary)
        for job in sorted(static.manifest.jobs, key=lambda item: item.job_id):
            binding = legacy.two_stage_runtime_binding(static, job)
            client = ScriptedExactGrammarClient(
                static.agent_model_config,
                compiler_calls=_compiler_calls(binding),
                final_answer=binding.compiler_trajectory.final_answer,
            )
            raw = execute_exact_grammar_job_raw(
                job=job,
                runner_contract=contract,
                static=static,
                binding=binding,
                client=client,
                output_dir=root,
            )
            expected_observations = legacy_preflight._compiler_observations(binding)
            replay = legacy.replay_v3(raw, static=static, binding=binding)
            verification, mechanism = _completed_verification(
                raw=raw, replay=replay, binding=binding
            )
            if (
                raw.terminal_disposition != "completed"
                or legacy_preflight._observation_semantic_projection(raw.observations)
                != legacy_preflight._observation_semantic_projection(expected_observations)
                or raw.completed_result is None
                or raw.completed_result.answer != binding.compiler_trajectory.final_answer
                or not replay.passed
                or not verification.valid
                or not mechanism.success
            ):
                raise ValueError(f"v26.113 direct Runner fixture failed: {job.job_id}")
            job_exact_payloads = 0
            for descriptor in raw.provider_call_artifacts:
                provider = legacy.RawStageOneProviderCall.model_validate(
                    legacy.load_canonical_json(root / descriptor.relative_path)
                )
                certificate_count += 1
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
                        set(payload)
                        != {
                            "stage",
                            "state_id",
                            "decision_kind",
                            "tool_id",
                            "node_id",
                            "operator_id",
                            "operand_sources",
                            "direct_arguments",
                            "evidence_ids",
                            "protocol",
                        }
                        or payload.get("protocol") != EXACT_RESPONSE_PROTOCOL_VERSION
                    ):
                        raise ValueError("v26.113 scripted payload differs from exact Grammar")
                    exact_payloads += 1
                    job_exact_payloads += 1
            rows.append(
                RunnerFixtureRow(
                    job_id=job.job_id,
                    raw_execution_id=raw.artifact_id,
                    stage_one_provider_call_count=raw.stage_one_provider_call_count,
                    stage_two_commit_count=len(raw.commits),
                    observation_count=len(raw.observations),
                    exact_grammar_payload_count=job_exact_payloads,
                )
            )
            raws.append(raw)
        sample = raws[0]
        binding = legacy.two_stage_runtime_binding(static, sample.job)
        recovered = execute_exact_grammar_job_raw(
            job=sample.job,
            runner_contract=contract,
            static=static,
            binding=binding,
            client=None,
            output_dir=root,
        )
        if recovered != sample:
            raise ValueError("v26.113 complete Raw recovery changed")
        orphan_root = root / "orphan_control"
        orphan_path = legacy.raw_provider_path(orphan_root, sample.job, 0)
        orphan_path.parent.mkdir(parents=True, exist_ok=True)
        orphan_path.write_text("{}\n", encoding="utf-8")
        try:
            execute_exact_grammar_job_raw(
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
        control_client = ScriptedExactGrammarClient(static.agent_model_config)
        ledger = legacy.JournaledStageOneClient(
            control_client,
            runner_contract=contract,
            resource_contract=static.resource,
            job=sample.job,
            output_dir=root / "precall_controls",
        )
        oversized = ledger.prepare(
            logical_request_index=0,
            request_kind="semantic_proposal",
            phase="primary",
            primary_prompt="x" * 60001,
            prompt="x" * 60001,
            public_state_id="fixture-state",
            rescue_available_before=True,
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
            phase="primary",
            primary_prompt=prompt,
            prompt=prompt,
            public_state_id=None,
            rescue_available_before=False,
        )
        ledger.invoke(reusable)
        try:
            ledger.invoke(reusable)
        except legacy.InstrumentContractError:
            reuse_rejected = True
        else:
            reuse_rejected = False
        budget_client = ScriptedExactGrammarClient(
            static.agent_model_config, completion_tokens=16385
        )
        budget_ledger = legacy.JournaledStageOneClient(
            budget_client,
            runner_contract=contract,
            resource_contract=static.resource,
            job=sample.job,
            output_dir=root / "remaining_budget_control",
        )
        large_prompt = "b" * 59000
        budget_denied = False
        for index in range(4):
            prepared = budget_ledger.prepare(
                logical_request_index=index,
                request_kind="final_answer",
                phase="primary",
                primary_prompt=large_prompt,
                prompt=large_prompt,
                public_state_id=None,
                rescue_available_before=False,
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
        rescue_client = ScriptedExactGrammarClient(
            static.agent_model_config,
            queued_payloads=({"stage": "semantic_decision_proposal"},),
        )
        rescue_ledger = legacy.JournaledStageOneClient(
            rescue_client,
            runner_contract=contract,
            resource_contract=static.resource,
            job=sample.job,
            output_dir=root / "serialization_rescue_control",
        )
        rescue_state = build_public_action_state(
            binding.record.task_package.task.public,
            binding.environment,
            (),
        )
        rescue_condition = (
            None
            if binding.source_registered_path.role == "capability"
            else binding.source_registered_path.path_strategy_id
        )
        rescue_primary_prompt = render_exact_semantic_proposal_prompt(
            instruction=binding.record.task_package.task.public.instruction,
            state=rescue_state,
            public_path_condition=rescue_condition,
        )
        rescue_attempts: list[legacy.StageOneAttempt] = []
        rescue_outcome, rescue_used = _active_exact_outcome(
            rescue_ledger,
            attempts=rescue_attempts,
            logical_request_index=0,
            request_kind="semantic_proposal",
            primary_prompt=rescue_primary_prompt,
            state=rescue_state,
            rescue_used=False,
        )
        rescue_provider = legacy.RawStageOneProviderCall.model_validate(
            legacy.load_canonical_json(root / rescue_ledger.descriptors[-1].relative_path)
        )
        controls = {
            "complete_raw_recovery_byte_identical": recovered == sample,
            "orphan_provider_artifact_rejected": orphan_rejected,
            "oversized_prompt_rejected_before_provider": oversized_rejected,
            "reused_preparation_rejected": reuse_rejected,
            "insufficient_remaining_budget_rejected_before_provider": budget_denied,
            "completion_16384_admitted": admitted_16384 and charged_16384 > 16384,
            "completion_16385_admitted_and_charged": admitted_16385
            and charged_16385 > charged_16384,
            "completion_16386_instrument_failure": not admitted_16386,
            "rescue_blocked_after_instrument_failure": bool(failed_ledger.instrument_failures),
            "serialization_rescue_accepted": bool(
                rescue_used
                and len(rescue_attempts) == 2
                and rescue_outcome.attempt.disposition == "usable"
                and rescue_outcome.proposal is not None
            ),
            "rescue_uses_exact_response_protocol": bool(
                rescue_provider.response_payload
                and rescue_provider.response_payload.get("protocol")
                == EXACT_RESPONSE_PROTOCOL_VERSION
            ),
            "raw_provider_certificate_triple_count": certificate_count,
            "certificate_parent_binding_pass_count": parent_pass,
            "privacy_pass_count": privacy_pass,
        }
    fixture_values = {
        "runner_contract_id": contract.contract_id,
        "rows": tuple(rows),
        "fixture_aggregate_sha256": _fixture_hash(raws),
    }
    provisional_fixture = RunnerFixtureAudit.model_construct(audit_id="pending", **fixture_values)
    fixture = RunnerFixtureAudit(
        audit_id=_identity(
            provisional_fixture,
            "audit_id",
            "finance_v26_exact_grammar_runner_fixture:",
        ),
        **fixture_values,
    )
    recovery_values = {"runner_contract_id": contract.contract_id, **controls}
    provisional_recovery = CertificateUsageRecoveryAudit.model_construct(
        audit_id="pending", **recovery_values
    )
    recovery = CertificateUsageRecoveryAudit(
        audit_id=_identity(
            provisional_recovery,
            "audit_id",
            "finance_v26_exact_grammar_certificate_usage_recovery:",
        ),
        **recovery_values,
    )
    if exact_payloads != 224:
        raise ValueError("v26.113 exact payload denominator changed")
    return fixture, recovery


def _expect_rejection(name: str, action: Any) -> MutationResult:
    try:
        action()
    except (ValueError, legacy.InstrumentContractError):
        provisional = MutationResult.model_construct(mutation_id="pending", name=name)
        return MutationResult(
            mutation_id=_identity(
                provisional,
                "mutation_id",
                "finance_v26_exact_grammar_runner_mutation:",
            ),
            name=name,
        )
    raise AssertionError(f"v26.113 mutation accepted: {name}")


def _build_destructive(
    static: legacy.TwoStageStaticInputs,
    contract: legacy.TwoStageRunnerContract,
    grammar: BaseModel,
) -> DestructiveRunnerAudit:
    sample = static.manifest.jobs[0]

    def stale(model: BaseModel, **updates: Any) -> BaseModel:
        payload = model.model_dump(mode="json")
        payload.update(updates)
        return type(model).model_validate(payload)

    def invalid_stage_one_config(**updates: Any) -> None:
        payload = static.agent_model_config.model_dump(mode="json")
        payload.update(updates)
        legacy.require_stage_one_model_config(
            type(static.agent_model_config).model_validate(payload)
        )

    mutations = (
        _expect_rejection(
            "wrong_static_contract",
            lambda: stale(contract, predecessor_static_contract_id="changed"),
        ),
        _expect_rejection(
            "wrong_manifest",
            lambda: stale(contract, predecessor_manifest_id="changed"),
        ),
        _expect_rejection(
            "wrong_response_grammar",
            lambda: stale(grammar, grammar_id="prospective_stage_one_response_grammar:changed"),
        ),
        _expect_rejection(
            "wrong_model",
            lambda: invalid_stage_one_config(model="deepseek-v4-pro"),
        ),
        _expect_rejection(
            "thinking_disabled",
            lambda: invalid_stage_one_config(
                request_body_overrides={"thinking": {"type": "disabled"}, "top_p": 0.9}
            ),
        ),
        _expect_rejection(
            "wrong_completion_bound",
            lambda: invalid_stage_one_config(max_output_tokens=32768),
        ),
        _expect_rejection(
            "wrong_rollout_bound",
            lambda: stale(static.resource, rollout_upper_bound_tokens=261000),
        ),
        _expect_rejection(
            "stage_two_provider_route",
            lambda: stale(static.stage_two, provider_call_upper_bound=1),
        ),
        _expect_rejection(
            "unknown_job",
            lambda: stale(sample, job_id="finance_v26_two_stage_job:unknown"),
        ),
        _expect_rejection(
            "job_contract_parent_changed",
            lambda: stale(sample, contract_id="finance_v26_two_stage_execution_contract:changed"),
        ),
    )
    values = {"mutations": tuple(sorted(mutations, key=lambda item: item.name))}
    provisional = DestructiveRunnerAudit.model_construct(audit_id="pending", **values)
    return DestructiveRunnerAudit(
        audit_id=_identity(
            provisional, "audit_id", "finance_v26_exact_grammar_runner_destructive:"
        ),
        **values,
    )


def _detail(path: Path, output_dir: Path) -> DetailFile:
    return DetailFile(
        relative_path=str(path.relative_to(output_dir)),
        sha256=_sha256(path),
        byte_count=path.stat().st_size,
    )


def build(
    *, package_root: Path, implementation_root: Path, output_dir: Path
) -> ExactGrammarRunnerPreflightReport:
    replay = _build_source_replay(package_root, implementation_root)
    static, grammar = load_exact_grammar_static_inputs(package_root, implementation_root)
    contract = make_exact_grammar_runner_contract(static)
    binding_values = {"runner_contract_id": contract.contract_id}
    provisional_binding = RunnerBindingAudit.model_construct(audit_id="pending", **binding_values)
    binding = RunnerBindingAudit(
        audit_id=_identity(
            provisional_binding, "audit_id", "finance_v26_exact_grammar_runner_binding:"
        ),
        **binding_values,
    )
    fixture, recovery = _build_fixture_and_controls(static, contract)
    destructive = _build_destructive(static, contract, grammar)
    outputs: tuple[tuple[str, Any], ...] = (
        ("source_replay_audit.json", replay),
        ("runner_contract.json", contract),
        ("runner_binding_audit.json", binding),
        ("runner_fixture_audit.json", fixture),
        ("certificate_usage_recovery_audit.json", recovery),
        ("destructive_runner_audit.json", destructive),
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for name, value in outputs:
        path = output_dir / name
        _write_json(path, value)
        paths.append(path)
    details = tuple(
        sorted(
            (_detail(path, output_dir) for path in paths),
            key=lambda item: item.relative_path,
        )
    )
    values = {
        "source_replay_audit_id": replay.audit_id,
        "runner_contract_id": contract.contract_id,
        "runner_binding_audit_id": binding.audit_id,
        "runner_fixture_audit_id": fixture.audit_id,
        "certificate_usage_recovery_audit_id": recovery.audit_id,
        "destructive_runner_audit_id": destructive.audit_id,
        "detail_files": details,
    }
    provisional = ExactGrammarRunnerPreflightReport.model_construct(report_id="pending", **values)
    report = ExactGrammarRunnerPreflightReport(
        report_id=_identity(
            provisional,
            "report_id",
            "finance_v26_exact_grammar_runner_preflight_report:",
        ),
        **values,
    )
    _write_json(output_dir / "report.json", report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--package-root", type=Path, required=True)
    parser.add_argument("--implementation-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    report = build(
        package_root=args.package_root,
        implementation_root=args.implementation_root,
        output_dir=args.output_dir,
    )
    print(report.model_dump_json())


if __name__ == "__main__":
    main()
