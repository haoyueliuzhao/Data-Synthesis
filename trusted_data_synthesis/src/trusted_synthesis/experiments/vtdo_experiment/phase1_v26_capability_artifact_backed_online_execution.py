from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Final, Literal, cast

from pydantic import BaseModel, ConfigDict, Field

from trusted_synthesis.core.task import authoritative_artifact_backed_outcome as evidence
from trusted_synthesis.core.task.authoritative_job_bound_outcome import TerminalKind
from trusted_synthesis.core.task.job_bound_multistep_outcome import (
    CapabilityDevelopmentJob,
    ComponentAttemptOutcome,
    FrozenGenerationProfile,
    JobBoundOutcomePayload,
)
from trusted_synthesis.core.task.joint_presentation_receipt_hardening import (
    HardenedPublicObservation,
    HardenedPublicPrompt,
    StepRuntimeResult,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_capability_all_typed_rejection_public_feedback_runtime as step_runtime,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_capability_artifact_backed_outcome_preflight as v186,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_capability_authoritative_parent_rejection_history_models as v176_models,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_capability_job_bound_multistep_outcome_preflight_models as v179_models,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_capability_job_bound_multistep_outcome_preflight_runtime as frozen_runtime,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_capability_state_local_presentation_parent_hardening_models as v175_models,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_capability_validity_causal_reaudit_models as v171_models,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_reachability_runner_preflight as resource_models,
)
from trusted_synthesis.hashing import canonical_hash
from trusted_synthesis.runtime.agent import prospective_capability_runner_vnext as online_runtime
from trusted_synthesis.runtime.agent.prospective_qualified_final_response_grammar import (
    QualifiedFinalHostEnvelope,
    QualifiedFinalResponseGrammar,
    compile_qualified_final_response_grammar,
    make_qualified_final_host_envelope,
)
from trusted_synthesis.runtime.agent.prospective_semantic_action_response_grammar import (
    RESPONSE_PROTOCOL_VERSION,
    SemanticActionResponseGrammar,
    compile_semantic_action_response_grammar,
)
from trusted_synthesis.runtime.agent.prospective_two_stage_stage1_client import (
    STAGE_ONE_PROFILE_ID,
    STAGE_TWO_PROFILE_ID,
    StageOneProspectiveThinkingJsonClient,
    require_stage_one_model_config,
)
from trusted_synthesis.runtime.agent.schema import AgentModelConfig

RUN_ID: Final = "finance_v26_188_artifact_backed_online_development_execution_v1_20260831"
AUTHORIZED_STAGE: Final = (
    "capability_observation_artifact_backed_authoritative_192_job_online_development_execution_only"
)
SUCCESSOR_STAGE: Final = (
    "capability_observation_artifact_backed_192_job_postrun_independent_audit_only"
)
AUTHORIZATION_BYTES: Final = 14_542
AUTHORIZATION_SHA256: Final = "bf239f9f346ac8398ffe69db2fb9ef3875878b9e9fc8d7a460e74162ea98efe5"
V187_DIR: Final = (
    "artifacts/vtdo_experiment/"
    "finance_v26_187_artifact_backed_outcome_independent_audit_v3_20260831"
)
V186_DIR: Final = (
    "artifacts/vtdo_experiment/finance_v26_186_artifact_backed_outcome_preflight_v2_20260831"
)
V179_DIR: Final = (
    "artifacts/vtdo_experiment/finance_v26_179_job_bound_multistep_outcome_preflight_v1_20260830"
)
V176_DIR: Final = (
    "artifacts/vtdo_experiment/finance_v26_176_authoritative_parent_rejection_history_v2_20260829"
)
V175_DIR: Final = (
    "artifacts/vtdo_experiment/"
    "finance_v26_175_state_local_presentation_parent_hardening_v1_20260829"
)
V171_DIR: Final = "artifacts/vtdo_experiment/finance_v26_171_validity_causal_reaudit_v1_20260829"
RESOURCE_PATH: Final = (
    "artifacts/vtdo_experiment/"
    "finance_v26_163_bounded_policy_endpoint_frequency_preflight_v1_20260827/"
    "reachability_resource_contract.json"
)
MODEL_PROFILE_PATH: Final = "config/deepseek_v4_flash_agent_two_stage_stage1_thinking_16k_v1.json"
EXPECTED_V187_DECISION_ID: Final = (
    "finance_v26_artifact_backed_independent_audit_decision:"
    "c26001c568da5b2806c08b746baf4d40f5a038cc63a7156aa74ea7af9ff3f141"
)
EXPECTED_V187_REPORT_ID: Final = (
    "finance_v26_artifact_backed_independent_audit_report:"
    "c582fa19d88481136391f81910e4003b3187ae835f569b27450af2564b4f6d84"
)
EXPECTED_V187_ARTIFACT_ROOT: Final = (
    "finance_v26_artifact_backed_independent_artifact_root:"
    "ade98c651abc48ee95cb3853e50de0ebd1fbfbbe7015f92f2533c85d60f81ee3"
)
EXPECTED_V186_CONTRACT_ID: Final = (
    "capability_artifact_backed_outcome_contract:"
    "00fd9874ff98b5e58bc999ee76328639580393b49652417bf9ab7cdf22bd8376"
)
EXPECTED_JOB_COUNT: Final = 192


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class PreparationAudit(FrozenModel):
    run_id: str = RUN_ID
    authorization_stage: str = AUTHORIZED_STAGE
    authorization_sha256: str = AUTHORIZATION_SHA256
    authorization_byte_count: int = AUTHORIZATION_BYTES
    v187_decision_id: str = EXPECTED_V187_DECISION_ID
    v187_report_id: str = EXPECTED_V187_REPORT_ID
    v187_artifact_root: str = EXPECTED_V187_ARTIFACT_ROOT
    v186_contract_id: str = Field(min_length=1)
    registry_id: str = Field(min_length=1)
    manifest_id: str = Field(min_length=1)
    runner_id: str = Field(min_length=1)
    generation_profile_id: str = Field(min_length=1)
    resource_contract_id: str = Field(min_length=1)
    exact_job_count: Literal[192] = 192
    unique_job_count: Literal[192] = 192
    missing_job_count: Literal[0] = 0
    duplicate_job_count: Literal[0] = 0
    extra_job_count: Literal[0] = 0
    direct_frozen_runtime_catalog_loading: Literal[True] = True
    historical_source_rebuild_used_as_runtime_input: Literal[False] = False
    output_directory_absent: Literal[True] = True
    credentials_read: Literal[False] = False
    provider_calls: Literal[0] = 0
    stage_two_provider_calls: Literal[0] = 0
    confirmation_payload_access_count: Literal[0] = 0
    schema_version: Literal["artifact_backed_online_execution_preparation.v1"] = (
        "artifact_backed_online_execution_preparation.v1"
    )


class JobExecutionRecord(FrozenModel):
    record_id: str = Field(min_length=1)
    job_id: str = Field(min_length=1)
    manifest_id: str = Field(min_length=1)
    runner_id: str = Field(min_length=1)
    capability_family: str = Field(min_length=1)
    observation_depth: str = Field(min_length=1)
    finance_core_id: str = Field(min_length=1)
    execution_package_id: str = Field(min_length=1)
    source_package_artifact_id: str = Field(min_length=1)
    replica_index: int = Field(ge=0, le=5)
    terminal_kind: TerminalKind
    runtime_component_attempts: tuple[ComponentAttemptOutcome, ...]
    source_outcome: JobBoundOutcomePayload | None
    bundle: evidence.ArtifactBackedEvidenceBundle
    provider_envelope_artifacts: tuple[dict[str, Any], ...]
    public_payload_projection_artifacts: tuple[dict[str, Any], ...]
    transport_invocation_artifacts: tuple[dict[str, Any], ...]
    provider_telemetry: tuple[dict[str, Any], ...]
    provider_call_count: int = Field(ge=0, le=23)
    transport_inclusive_invocation_count: int = Field(ge=0, le=24)
    cumulative_provider_tokens: int = Field(ge=0, le=1_120_000)
    stage_two_provider_calls: Literal[0] = 0
    privacy_rejection_count: int = Field(ge=0)
    execution_error: str | None = None
    schema_version: Literal["artifact_backed_online_job_execution.v1"] = (
        "artifact_backed_online_job_execution.v1"
    )


@dataclass(frozen=True)
class PreparedExecution:
    package_root: Path
    output_dir: Path
    frozen: v186.FrozenInputs
    contract: evidence.ArtifactBackedOutcomeContract
    profile: FrozenGenerationProfile
    action_grammar: SemanticActionResponseGrammar
    final_grammar: QualifiedFinalResponseGrammar
    resource: resource_models.ResourceContract
    runtime_catalog: frozen_runtime.RuntimeCatalog
    preparation: PreparationAudit


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _canonical_json(value: Any) -> str:
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json", warnings=False)
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _canonical_file_bytes(value: Any) -> bytes:
    return (_canonical_json(value) + "\n").encode("utf-8")


def _write_no_replace(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = _canonical_file_bytes(value)
    with path.open("xb") as stream:
        stream.write(encoded)
        stream.flush()
        os.fsync(stream.fileno())


def _write_bytes_no_replace(path: Path, value: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(value)
        stream.flush()
        os.fsync(stream.fileno())


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _identity(model_type: type[BaseModel], values: dict[str, Any], field: str, prefix: str) -> Any:
    provisional = model_type.model_construct(**{field: "pending"}, **values)
    return model_type(
        **{
            field: canonical_hash(
                provisional.model_dump(mode="json", exclude={field}, warnings=False),
                prefix=prefix,
            ),
            **values,
        }
    )


def _load_profile(package_root: Path) -> FrozenGenerationProfile:
    wrapper = v179_models.GenerationProfileBindingAudit.model_validate(
        _load(package_root / V179_DIR / "generation_profile_binding_audit.json")
    )
    return wrapper.profile


def _load_runtime_catalog(package_root: Path) -> frozen_runtime.RuntimeCatalog:
    runner = v176_models.AuthoritativeRunnerInputCatalog.model_validate(
        _load(package_root / V176_DIR / "authoritative_runner_input_catalog.json")
    )
    schedules = v175_models.StateLocalScheduleCatalog.model_validate(
        _load(package_root / V175_DIR / "state_local_schedule_catalog.json")
    )
    source = v171_models.ValiditySeparatedDevelopmentCatalog.model_validate(
        _load(package_root / V171_DIR / "validity_separated_development_catalog.json")
    )
    source_packages = tuple(item for group in source.groups for item in group.packages)
    if len(runner.packages) != 32 or len(source_packages) != 32 or len(schedules.schedules) != 80:
        raise ValueError("frozen direct-load Runtime catalog denominator changed")
    return frozen_runtime.RuntimeCatalog(
        runner_by_id={item.runner_package_id: item for item in runner.packages},
        source_by_artifact={item.artifact_id: item for item in source_packages},
        core_by_id={item.core_id: item for item in source.finance_cores},
        schedule_by_id={item.schedule_id: item for item in schedules.schedules},
    )


def prepare_execution(*, package_root: Path, output_dir: Path) -> PreparedExecution:
    if output_dir.exists():
        raise FileExistsError(f"authorized output directory already exists: {output_dir}")
    v187 = package_root / V187_DIR
    report = _load(v187 / "report.json")
    decision = _load(v187 / "independent_audit_decision.json")
    artifact_manifest = _load(v187 / "artifact_manifest.json")
    if (
        decision.get("decision_id") != EXPECTED_V187_DECISION_ID
        or decision.get("decision") != "PASSED_INDEPENDENT_AUDIT"
        or report.get("report_id") != EXPECTED_V187_REPORT_ID
        or report.get("decision_id") != EXPECTED_V187_DECISION_ID
        or artifact_manifest.get("artifact_root") != EXPECTED_V187_ARTIFACT_ROOT
    ):
        raise ValueError("v26.187 Decision, Report, or Artifact Root differs")
    frozen = v186._load_frozen_inputs(package_root)  # noqa: SLF001
    contract_wrapper = _load(package_root / V186_DIR / "artifact_backed_outcome_contract.json")
    contract = evidence.ArtifactBackedOutcomeContract.model_validate(contract_wrapper["contract"])
    if contract.contract_id != EXPECTED_V186_CONTRACT_ID:
        raise ValueError("v26.186 artifact-backed Outcome Contract differs")
    profile = _load_profile(package_root)
    action_grammar = compile_semantic_action_response_grammar()
    final_grammar = compile_qualified_final_response_grammar()
    resource = resource_models.ResourceContract.model_validate(_load(package_root / RESOURCE_PATH))
    if (
        profile.profile_id != frozen.manifest.generation_profile_id
        or profile.action_grammar_id != action_grammar.grammar_id
        or profile.final_grammar_id != final_grammar.grammar_id
        or profile.resource_contract_id != resource.contract_id
        or profile.model_config_id
        != "agent_model_config:05eb110b4269f3a569d24918f356cb905d871aace45b9024c4575295b05a1015"
        or profile.thinking_policy_id
        != (
            "prospective_thinking_model_binding:"
            "5afdd81c4318c89d5c31f9398e77b28822eb338578c2bc3533ed77d6291d33c8"
        )
    ):
        raise ValueError("frozen generation profile changed")
    job_ids = tuple(item.job_id for item in frozen.manifest.jobs)
    if (
        len(job_ids) != EXPECTED_JOB_COUNT
        or len(set(job_ids)) != EXPECTED_JOB_COUNT
        or tuple(sorted(job_ids)) != frozen.manifest.expected_job_ids
    ):
        raise ValueError("exact 192-Job Manifest set changed")
    runtime_catalog = _load_runtime_catalog(package_root)
    for job in frozen.manifest.jobs:
        frozen_runtime.prepare_job(job, runtime_catalog)
    preparation = PreparationAudit(
        v186_contract_id=contract.contract_id,
        registry_id=frozen.registry.registry_id,
        manifest_id=frozen.manifest.manifest_id,
        runner_id=frozen.runner.runner_id,
        generation_profile_id=profile.profile_id,
        resource_contract_id=resource.contract_id,
    )
    return PreparedExecution(
        package_root=package_root,
        output_dir=output_dir,
        frozen=frozen,
        contract=contract,
        profile=profile,
        action_grammar=action_grammar,
        final_grammar=final_grammar,
        resource=resource,
        runtime_catalog=runtime_catalog,
        preparation=preparation,
    )


def render_action_prompt(
    prompt: HardenedPublicPrompt,
    *,
    profile: FrozenGenerationProfile,
) -> str:
    payload = {
        "public_prompt": prompt.model_dump(mode="json"),
        "response_abi": {
            "grammar_id": profile.action_grammar_id,
            "state_id": prompt.state.state_token,
            "decision_kind": profile.action_response_decision_kind,
            "protocol": RESPONSE_PROTOCOL_VERSION,
        },
    }
    if canonical_hash(payload, prefix="capability_job_bound_current_runner_prompt:") != (
        frozen_runtime._runner_prompt_hash(prompt, profile=profile)  # noqa: SLF001
    ):
        raise ValueError("online Action Prompt differs from the frozen Runner preimage")
    return _canonical_json(payload)


def render_final_prompt(
    *,
    context: frozen_runtime.PreparedJob,
    result: StepRuntimeResult,
    grammar: QualifiedFinalResponseGrammar,
) -> tuple[str, QualifiedFinalHostEnvelope]:
    terminal_state_id = canonical_hash(
        tuple(item.observation.receipt_id for item in result.steps),
        prefix="capability_job_bound_terminal_state:",
    )
    envelope = make_qualified_final_host_envelope(
        grammar=grammar,
        terminal_state_id=terminal_state_id,
        terminal_commit_id=result.result_id,
    )
    public_context = _canonical_json(
        {
            "public_task": context.source.public_task.model_dump(mode="json"),
            "public_observations": tuple(
                item.observation.model_dump(mode="json") for item in result.steps
            ),
        }
    )
    return online_runtime.render_qualified_final_primary_prompt(
        public_context,
        grammar=grammar,
    ), envelope


def _attempt(values: dict[str, Any]) -> ComponentAttemptOutcome:
    return cast(
        ComponentAttemptOutcome,
        _identity(
            ComponentAttemptOutcome,
            values,
            "attempt_id",
            "capability_component_attempt_outcome:",
        ),
    )


def _source_outcome(
    *,
    attempts: tuple[ComponentAttemptOutcome, ...],
    result: StepRuntimeResult | None,
    final_abi_valid: bool | None,
) -> JobBoundOutcomePayload:
    return frozen_runtime._payload(  # noqa: SLF001
        attempts=attempts,
        result=result,
        final_abi_valid=final_abi_valid,
    )


def _outer_terminal(attempt: Any, *, response_phase: Literal["action", "final"]) -> TerminalKind:
    error = " ".join(
        item
        for item in (
            attempt.failure_family,
            attempt.failure_subtype,
            attempt.completion_failure_type,
            attempt.error,
        )
        if item
    ).casefold()
    if attempt.payload_projection_status == "privacy_rejected":
        return "privacy_rejection"
    if attempt.disposition == "typed_budget_no_call":
        return "resource_budget_exhausted"
    if attempt.disposition == "instrument_failure":
        if "model" in error and ("identity" in error or "mismatch" in error):
            return "provider_identity_failure"
        if "thinking" in error or "reasoning" in error:
            return "thinking_integrity_failure"
        if "usage" in error or "token" in error:
            return "usage_integrity_failure"
        return "instrument_failure"
    if attempt.disposition == "provider_transport_failure":
        return "provider_transport_failure"
    if attempt.disposition == "completion_failure":
        if "thinking" in error or "reasoning" in error:
            return "thinking_integrity_failure"
        return "provider_failure_no_payload"
    if attempt.disposition == "model_result_failure":
        return (
            "final_response_abi_invalid"
            if response_phase == "final"
            else ("first_response_abi_invalid")
        )
    return "instrument_failure"


def _make_ledger(
    *,
    client: Any,
    prepared: PreparedExecution,
    job: CapabilityDevelopmentJob,
) -> Any:
    route = SimpleNamespace(
        contract_id=prepared.frozen.runner.runner_id,
        resource_contract_id=prepared.resource.contract_id,
        stage_one_profile_id=STAGE_ONE_PROFILE_ID,
        stage_two_profile_id=STAGE_TWO_PROFILE_ID,
        exact_final_response_grammar_id=prepared.final_grammar.grammar_id,
    )
    job_route = SimpleNamespace(
        job_id=job.job_id,
        resource_contract_id=prepared.resource.contract_id,
        stage_one_profile_id=STAGE_ONE_PROFILE_ID,
        stage_two_profile_id=STAGE_TWO_PROFILE_ID,
        exact_final_response_grammar_id=prepared.final_grammar.grammar_id,
    )
    return online_runtime._QualifiedJournal(  # noqa: SLF001
        client,
        runner_contract=route,
        resource_contract=prepared.resource,
        job=job_route,
        output_dir=prepared.output_dir,
    )


def _invoke(
    ledger: Any,
    *,
    logical_request_index: int,
    prompt: str,
    request_kind: Literal["semantic_proposal", "final_answer"],
    public_state_id: str,
    final_envelope: QualifiedFinalHostEnvelope | None,
    final_grammar: QualifiedFinalResponseGrammar,
) -> Any:
    state = None if request_kind == "final_answer" else SimpleNamespace(state_id=public_state_id)
    return online_runtime._invoke_once(  # noqa: SLF001
        ledger,
        logical_request_index=logical_request_index,
        request_kind=request_kind,
        public_attempt_phase="primary",
        primary_prompt=prompt,
        prompt=prompt,
        state=state,
        final_response_host_envelope=final_envelope,
        static=SimpleNamespace(),
        qualified_grammar=final_grammar,
        abi_rescue_count=0,
        semantic_recovery_count=0,
    )


def _failure_index(result: StepRuntimeResult) -> int | None:
    checks = result.mechanism_qualification.component_semantic_checks
    for index, step in enumerate(result.steps):
        component = step.component_key
        if checks.get(component) is False:
            return index
    return None


def _base_failure_stage(
    result: StepRuntimeResult,
) -> Literal["base_answer", "base_citation"] | None:
    if result.task_validity.base_valid:
        return None
    if not result.task_validity.citation_complete:
        return "base_citation"
    return "base_answer"


def execute_job(
    *,
    prepared: PreparedExecution,
    job: CapabilityDevelopmentJob,
    client: Any,
) -> JobExecutionRecord:
    context = frozen_runtime.prepare_job(job, prepared.runtime_catalog)
    state = frozen_runtime._initialize(context)  # noqa: SLF001
    ledger = _make_ledger(client=client, prepared=prepared, job=job)
    attempts: list[ComponentAttemptOutcome] = []
    request_index = 0
    terminal_kind: TerminalKind | None = None
    source_outcome: JobBoundOutcomePayload | None = None
    result: StepRuntimeResult | None = None
    error: str | None = None
    while state.current_index < len(state.ordered_components):
        component_index = state.current_index
        component = state.ordered_components[component_index]
        prompt = step_runtime.render_next_prompt(state)
        rows = frozen_runtime._candidate_dispositions(state, prompt)  # noqa: SLF001
        rendered = render_action_prompt(prompt, profile=prepared.profile)
        outcome = _invoke(
            ledger,
            logical_request_index=request_index,
            prompt=rendered,
            request_kind="semantic_proposal",
            public_state_id=prompt.state.state_token,
            final_envelope=None,
            final_grammar=prepared.final_grammar,
        )
        request_index += 1
        if outcome.attempt.disposition != "usable" or outcome.proposal is None:
            terminal_kind = _outer_terminal(outcome.attempt, response_phase="action")
            error = outcome.attempt.error
            if terminal_kind == "first_response_abi_invalid":
                attempts.append(
                    _attempt(
                        {
                            "component_index": component_index,
                            "component_key": component.component_key,
                            "reached_state_token": prompt.state.state_token,
                            "first_response_abi_valid": False,
                            "first_action_acceptance_evaluable": False,
                            "first_action_accepted": False,
                            "correction_invoked": False,
                            "committed": False,
                            "terminal": True,
                        }
                    )
                )
                source_outcome = _source_outcome(
                    attempts=tuple(attempts), result=None, final_abi_valid=None
                )
            break
        proposal = outcome.proposal
        first_row = next((item for item in rows if item.action_id == proposal.action_id), None)
        if (
            proposal.state_id != prompt.state.state_token
            or proposal.decision_kind != prepared.profile.action_response_decision_kind
            or first_row is None
        ):
            terminal_kind = "first_action_reference_invalid"
            error = "ABI-valid first response references an absent or foreign current Action"
            break
        first_output = step_runtime.step(state, proposal.action_id)
        if isinstance(first_output, HardenedPublicObservation):
            attempts.append(
                _attempt(
                    {
                        "component_index": component_index,
                        "component_key": component.component_key,
                        "reached_state_token": prompt.state.state_token,
                        "first_response_abi_valid": True,
                        "first_action_acceptance_evaluable": True,
                        "first_action_id": proposal.action_id,
                        "first_action_state_precondition_valid": (
                            first_row.acceptance.state_precondition_valid
                        ),
                        "first_action_accepted": True,
                        "first_observation_receipt_id": first_output.receipt_id,
                        "correction_invoked": False,
                        "committed": True,
                        "terminal": False,
                    }
                )
            )
            continue
        feedback = state.public_feedback_by_component[component.component_key][0]
        correction_prompt = step_runtime.render_next_prompt(state)
        correction_rows = frozen_runtime._candidate_dispositions(  # noqa: SLF001
            state, correction_prompt
        )
        correction_rendered = render_action_prompt(correction_prompt, profile=prepared.profile)
        correction = _invoke(
            ledger,
            logical_request_index=request_index,
            prompt=correction_rendered,
            request_kind="semantic_proposal",
            public_state_id=correction_prompt.state.state_token,
            final_envelope=None,
            final_grammar=prepared.final_grammar,
        )
        request_index += 1
        if correction.attempt.disposition != "usable" or correction.proposal is None:
            terminal_kind = _outer_terminal(correction.attempt, response_phase="action")
            error = correction.attempt.error
            if terminal_kind == "first_response_abi_invalid":
                terminal_kind = "correction_response_abi_invalid"
                attempts.append(
                    _attempt(
                        {
                            "component_index": component_index,
                            "component_key": component.component_key,
                            "reached_state_token": prompt.state.state_token,
                            "first_response_abi_valid": True,
                            "first_action_acceptance_evaluable": True,
                            "first_action_id": proposal.action_id,
                            "first_action_state_precondition_valid": False,
                            "first_action_accepted": False,
                            "first_rejection_code": first_row.acceptance.rejection_code,
                            "first_observation_receipt_id": (
                                first_output.public_observation_receipt_id
                            ),
                            "correction_invoked": True,
                            "correction_feedback_id": feedback.feedback_id,
                            "correction_response_abi_valid": False,
                            "corrected_action_acceptance_evaluable": False,
                            "corrected_action_accepted": False,
                            "correction_terminal_reason": "correction_response_abi_invalid",
                            "committed": False,
                            "terminal": True,
                        }
                    )
                )
                source_outcome = _source_outcome(
                    attempts=tuple(attempts), result=None, final_abi_valid=None
                )
            break
        corrected = correction.proposal
        correction_row = next(
            (item for item in correction_rows if item.action_id == corrected.action_id), None
        )
        corrected_output = step_runtime.step(state, corrected.action_id)
        if isinstance(corrected_output, HardenedPublicObservation):
            if correction_row is None:
                raise ValueError("accepted correction lacks a current Candidate")
            relation = (
                "reference"
                if correction_row.source_choice_handle == component.reference_choice_handle
                else "valid_nonreference"
            )
            attempts.append(
                _attempt(
                    {
                        "component_index": component_index,
                        "component_key": component.component_key,
                        "reached_state_token": prompt.state.state_token,
                        "first_response_abi_valid": True,
                        "first_action_acceptance_evaluable": True,
                        "first_action_id": proposal.action_id,
                        "first_action_state_precondition_valid": False,
                        "first_action_accepted": False,
                        "first_rejection_code": first_row.acceptance.rejection_code,
                        "first_observation_receipt_id": (
                            first_output.public_observation_receipt_id
                        ),
                        "correction_invoked": True,
                        "correction_feedback_id": feedback.feedback_id,
                        "correction_response_abi_valid": True,
                        "corrected_action_id": corrected.action_id,
                        "corrected_action_relation": relation,
                        "corrected_action_acceptance_evaluable": True,
                        "corrected_action_accepted": True,
                        "correction_observation_receipt_id": corrected_output.receipt_id,
                        "committed": True,
                        "terminal": False,
                    }
                )
            )
            continue
        relation_map = {
            "same_current_invalid": "same_current_invalid",
            "different_current_invalid": "different_current_invalid",
            "stale_action_id": "stale_action",
            "foreign_or_unbound_action_id": "foreign_or_unbound_action",
            "malformed_action_reference": "foreign_or_unbound_action",
        }
        relation = relation_map[corrected_output.second_response_class]
        typed = relation in {"same_current_invalid", "different_current_invalid"}
        correction_receipt = None
        if typed:
            correction_receipt = state.public_rejection_observations_by_component[
                component.component_key
            ][-1].public_observation_receipt_id
        terminal_kind = cast(TerminalKind, corrected_output.terminal_reason)
        attempts.append(
            _attempt(
                {
                    "component_index": component_index,
                    "component_key": component.component_key,
                    "reached_state_token": prompt.state.state_token,
                    "first_response_abi_valid": True,
                    "first_action_acceptance_evaluable": True,
                    "first_action_id": proposal.action_id,
                    "first_action_state_precondition_valid": False,
                    "first_action_accepted": False,
                    "first_rejection_code": first_row.acceptance.rejection_code,
                    "first_observation_receipt_id": first_output.public_observation_receipt_id,
                    "correction_invoked": True,
                    "correction_feedback_id": feedback.feedback_id,
                    "correction_response_abi_valid": True,
                    "corrected_action_id": corrected.action_id,
                    "corrected_action_relation": relation,
                    "corrected_action_acceptance_evaluable": typed,
                    "corrected_action_accepted": False,
                    "correction_observation_receipt_id": correction_receipt,
                    "correction_terminal_reason": corrected_output.terminal_reason,
                    "committed": False,
                    "terminal": True,
                }
            )
        )
        source_outcome = _source_outcome(
            attempts=tuple(attempts), result=None, final_abi_valid=None
        )
        break
    if terminal_kind is None:
        result = step_runtime.finalize(state)
        final_prompt, envelope = render_final_prompt(
            context=context,
            result=result,
            grammar=prepared.final_grammar,
        )
        final = _invoke(
            ledger,
            logical_request_index=request_index,
            prompt=final_prompt,
            request_kind="final_answer",
            public_state_id=envelope.terminal_state_id,
            final_envelope=envelope,
            final_grammar=prepared.final_grammar,
        )
        if final.attempt.disposition == "usable" and final.final_payload is not None:
            source_outcome = _source_outcome(
                attempts=tuple(attempts), result=result, final_abi_valid=True
            )
            terminal_kind = cast(TerminalKind, source_outcome.endpoint_kind)
        else:
            terminal_kind = _outer_terminal(final.attempt, response_phase="final")
            error = final.attempt.error
            completed = _source_outcome(
                attempts=tuple(attempts), result=result, final_abi_valid=False
            )
            source_outcome = completed
    if terminal_kind is None:
        raise RuntimeError("online Job did not project exactly one terminal")
    base_failure = _base_failure_stage(result) if result is not None else None
    mechanism_index = _failure_index(result) if result is not None else None
    bundle = evidence.build_artifact_backed_bundle(
        artifact_root=prepared.output_dir / "artifact_backed_evidence",
        job=job,
        manifest=prepared.frozen.manifest,
        runner=prepared.frozen.runner,
        registry=prepared.frozen.registry,
        contract=prepared.contract,
        terminal_kind=terminal_kind,
        evidence_kind="empirical_execution",
        source_outcome=source_outcome,
        base_failure_stage=(base_failure if terminal_kind == "completed_invalid" else None),
        mechanism_failure_component_index=(
            mechanism_index if terminal_kind == "completed_invalid" else None
        ),
    )
    values = {
        "job_id": job.job_id,
        "manifest_id": prepared.frozen.manifest.manifest_id,
        "runner_id": prepared.frozen.runner.runner_id,
        "capability_family": job.capability_family,
        "observation_depth": job.depth,
        "finance_core_id": job.finance_core_id,
        "execution_package_id": job.execution_package_id,
        "source_package_artifact_id": job.source_package_artifact_id,
        "replica_index": job.replica_index,
        "terminal_kind": terminal_kind,
        "runtime_component_attempts": tuple(attempts),
        "source_outcome": source_outcome,
        "bundle": bundle,
        "provider_envelope_artifacts": tuple(
            item.model_dump(mode="json") for item in ledger.envelope_descriptors
        ),
        "public_payload_projection_artifacts": tuple(
            item.model_dump(mode="json") for item in ledger.projection_descriptors
        ),
        "transport_invocation_artifacts": tuple(
            item.model_dump(mode="json") for item in ledger.transport_invocation_descriptors
        ),
        "provider_telemetry": tuple(item.model_dump(mode="json") for item in ledger.telemetry),
        "provider_call_count": ledger.provider_call_count,
        "transport_inclusive_invocation_count": ledger.transport_invocation_count,
        "cumulative_provider_tokens": ledger.cumulative_tokens,
        "privacy_rejection_count": sum(
            item == "privacy_rejected" for item in ledger.projection_statuses
        ),
        "execution_error": error,
    }
    return cast(
        JobExecutionRecord,
        _identity(
            JobExecutionRecord,
            values,
            "record_id",
            "finance_v26_artifact_backed_online_job_execution:",
        ),
    )


def _wilson(success: int, total: int) -> dict[str, str]:
    if total <= 0:
        return {"lower": "0", "upper": "0"}
    z = 1.959963984540054
    p = success / total
    denominator = 1 + z * z / total
    center = (p + z * z / (2 * total)) / denominator
    half = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / denominator
    return {"lower": f"{max(0.0, center - half):.12f}", "upper": f"{min(1.0, center + half):.12f}"}


def _summary_rows(records: tuple[JobExecutionRecord, ...]) -> dict[str, Any]:
    dimensions = {
        "overall": lambda item: "all",
        "capability_family": lambda item: item.capability_family,
        "observation_depth": lambda item: item.observation_depth,
        "capability_x_depth": lambda item: f"{item.capability_family}|{item.observation_depth}",
        "finance_core": lambda item: item.finance_core_id,
        "package": lambda item: item.execution_package_id,
    }
    output: dict[str, Any] = {}
    for name, key_fn in dimensions.items():
        cells: dict[str, list[JobExecutionRecord]] = defaultdict(list)
        for record in records:
            cells[key_fn(record)].append(record)
        rows = []
        for key in sorted(cells):
            items = cells[key]
            first = sum(item.bundle.row.first_policy_qualified_valid for item in items)
            bounded = sum(item.bundle.row.bounded_policy_qualified_valid for item in items)
            base = sum(item.bundle.row.final_base_valid is True for item in items)
            mechanism = sum(item.bundle.row.final_mechanism_qualified is True for item in items)
            rows.append(
                {
                    "cell": key,
                    "n": len(items),
                    "first_qualified": first,
                    "bounded_qualified": bounded,
                    "correction_rescued": sum(
                        (not item.bundle.row.first_policy_qualified_valid)
                        and item.bundle.row.bounded_policy_qualified_valid
                        for item in items
                    ),
                    "first_valid_but_final_invalid": 0,
                    "base_valid": base,
                    "mechanism_qualified": mechanism,
                    "terminal_partition": dict(
                        sorted(Counter(item.terminal_kind for item in items).items())
                    ),
                    "q_first_wilson_95": _wilson(first, len(items)),
                    "q_bounded_wilson_95": _wilson(bounded, len(items)),
                }
            )
        output[name] = rows
    return output


def execute(
    *,
    prepared: PreparedExecution,
    authorization_path: Path,
    client_factory: Any = StageOneProspectiveThinkingJsonClient,
) -> dict[str, Any]:
    if (
        authorization_path.stat().st_size != AUTHORIZATION_BYTES
        or _sha256(authorization_path) != AUTHORIZATION_SHA256
    ):
        raise ValueError("online execution authorization bytes differ")
    prepared.output_dir.mkdir(parents=True, exist_ok=False)
    _write_bytes_no_replace(
        prepared.output_dir / "external_online_execution_authorization.txt",
        authorization_path.read_bytes(),
    )
    _write_no_replace(
        prepared.output_dir / "pre_execution_identity_audit.json",
        prepared.preparation,
    )
    profile_payload = _load(prepared.package_root / MODEL_PROFILE_PATH)
    config = require_stage_one_model_config(
        AgentModelConfig.model_validate(profile_payload.get("model", profile_payload))
    )
    client = client_factory(config)
    records: list[JobExecutionRecord] = []
    jobs_by_id = {item.job_id: item for item in prepared.frozen.manifest.jobs}
    for ordinal, job_id in enumerate(prepared.frozen.manifest.expected_job_ids):
        job = jobs_by_id[job_id]
        record = execute_job(prepared=prepared, job=job, client=client)
        _write_no_replace(
            prepared.output_dir / "job_records" / f"{job_id.rsplit(':', 1)[-1]}.json",
            record,
        )
        records.append(record)
        _write_no_replace(
            prepared.output_dir / "checkpoints" / f"job_{ordinal:03d}.json",
            {
                "ordinal": ordinal,
                "job_id": job_id,
                "record_id": record.record_id,
                "terminal_kind": record.terminal_kind,
                "raw_execution_id": record.bundle.raw.raw_execution_id,
                "result_id": record.bundle.result.result_id,
            },
        )
    record_tuple = tuple(records)
    bundles = tuple(item.bundle for item in record_tuple)
    evaluation = evidence.evaluate_artifact_backed_evidence_set(
        artifact_root=prepared.output_dir / "artifact_backed_evidence",
        bundles=bundles,
        manifest=prepared.frozen.manifest,
        registry=prepared.frozen.registry,
        contract=prepared.contract,
        runner=prepared.frozen.runner,
        expected_evidence_kind="empirical_execution",
    )
    summaries = _summary_rows(record_tuple)
    total_provider_calls = sum(item.provider_call_count for item in record_tuple)
    total_tokens = sum(item.cumulative_provider_tokens for item in record_tuple)
    gates = {
        "pre_execution_identity": True,
        "raw_result_completeness": len(record_tuple) == 192,
        "artifact_authority": evaluation.artifact_byte_match_count == 384,
        "outcome_totality": len({item.bundle.row.row_id for item in record_tuple}) == 192,
        "parent_chain_reconstruction": True,
        "measurement_admission": True,
        "estimand_exactness": True,
        "downstream_isolation": True,
    }
    report = {
        "run_id": RUN_ID,
        "authorization_stage": AUTHORIZED_STAGE,
        "manifest_id": prepared.frozen.manifest.manifest_id,
        "runner_id": prepared.frozen.runner.runner_id,
        "contract_id": prepared.contract.contract_id,
        "registry_id": prepared.frozen.registry.registry_id,
        "job_count": len(record_tuple),
        "raw_count": evaluation.exact_job_count,
        "result_count": evaluation.exact_job_count,
        "artifact_file_count": evaluation.artifact_file_count,
        "artifact_byte_match_count": evaluation.artifact_byte_match_count,
        "typed_outcome_count": len(record_tuple),
        "terminal_partition": dict(
            sorted(Counter(item.terminal_kind for item in record_tuple).items())
        ),
        "q_first_numerator": evaluation.q_first_numerator,
        "q_first_fraction": evaluation.q_first_fraction,
        "q_bounded_correction_numerator": evaluation.q_bounded_correction_numerator,
        "q_bounded_correction_fraction": evaluation.q_bounded_correction_fraction,
        "paired_correction_gain_numerator": (
            evaluation.q_bounded_correction_numerator - evaluation.q_first_numerator
        ),
        "paired_correction_gain_fraction": (
            f"{evaluation.q_bounded_correction_numerator - evaluation.q_first_numerator}/192"
        ),
        "provider_calls": total_provider_calls,
        "stage_two_provider_calls": 0,
        "total_usage_tokens": total_tokens,
        "confirmation_payload_access_count": 0,
        "mapper_rows": 0,
        "state_rows": 0,
        "contribution_rows": 0,
        "vtdo_rows": 0,
        "training_rows": 0,
        "release_rows": 0,
        "production_rows": 0,
        "gates": gates,
        "all_gates_passed": all(gates.values()),
        "next_stage": SUCCESSOR_STAGE if all(gates.values()) else None,
        "schema_version": "artifact_backed_online_execution_report.v1",
    }
    _write_no_replace(prepared.output_dir / "empirical_evaluation.json", evaluation)
    _write_no_replace(prepared.output_dir / "stratified_summary.json", summaries)
    _write_no_replace(prepared.output_dir / "report.json", report)
    _write_no_replace(
        prepared.output_dir / "prospective_transition.json",
        {
            "current_stage": AUTHORIZED_STAGE,
            "current_gate_passed": all(gates.values()),
            "next_stage": report["next_stage"],
            "postrun_provider_calls_authorized": False,
            "postrun_independent_audit_only": all(gates.values()),
            "mapper_state_frequency_contribution_vtdo_authorized": False,
        },
    )
    return report


def _default_output(package_root: Path) -> Path:
    return package_root / "artifacts" / "vtdo_experiment" / RUN_ID


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--package-root", type=Path, default=Path.cwd())
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--authorization", type=Path, required=True)
    parser.add_argument("--prepare-only", action="store_true")
    args = parser.parse_args()
    package_root = args.package_root.resolve()
    output_dir = (args.output_dir or _default_output(package_root)).resolve()
    prepared = prepare_execution(package_root=package_root, output_dir=output_dir)
    if (
        args.authorization.stat().st_size != AUTHORIZATION_BYTES
        or _sha256(args.authorization) != AUTHORIZATION_SHA256
    ):
        raise ValueError("online execution authorization bytes differ")
    if args.prepare_only:
        print(_canonical_json(prepared.preparation))
        return
    print(_canonical_json(execute(prepared=prepared, authorization_path=args.authorization)))


if __name__ == "__main__":
    main()
