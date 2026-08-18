from __future__ import annotations

import argparse
import hashlib
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Literal, cast

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.core.trajectory.executable_task import matching_sufficient_support_set
from trusted_synthesis.domains.finance.executable_support_runtime import (
    FinanceExecutableSupportRuntime,
)
from trusted_synthesis.domains.finance.interactive_agent_runtime import (
    FinanceTypedRecoveryScenario,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_authority_preserving_operation_hardening import (  # noqa: E501
    AuthorityPreservingHardeningReport,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_capability_reachability_failure_audit import (  # noqa: E501
    CapabilityReachabilityFailureAuditReport,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_empirical_support_pilot import (  # noqa: E501
    FAILURE_STAGE_ORDER,
    VERIFICATION_CHECK_IDS,
    EmpiricalPilotRollout,
    evaluate_mechanism_estimand,
    match_empirical_program,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_fresh_capability_population import (  # noqa: E501
    FreshCapabilityPopulationReport,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_public_operation_rematerialization import (  # noqa: E501
    OperationalTaskRecord,
)
from trusted_synthesis.hashing import canonical_hash
from trusted_synthesis.runtime.agent.iterative import IterativeAgentSolveResult
from trusted_synthesis.runtime.agent.public_operation import (
    public_action_neutral_repair_result,
    public_operation_step_rejection,
    public_postcompletion_action_rejection,
    public_terminal_verification_rejection,
)
from trusted_synthesis.runtime.tools import (
    ARGUMENT_PATCH_REQUIRED_POLICY,
    AgentToolEnvironmentManifest,
    AgentToolObservation,
    AgentToolResult,
    agent_tool_argument_rejection,
    make_agent_tool_observation,
)

V26_AUTHORITY_VERIFIER_REPLAY_VERSION = "finance_v26_authority_verifier_replay.v2"
V26_AUTHORITY_VERIFIER_CONTRACT_VERSION = "finance_v26_authority_verifier_contract.v2"
V26_AUTHORITY_VERIFICATION_REPORT_VERSION = "finance_v26_authority_verification_report.v2"
V26_AUTHORITY_VERIFIER_QUALIFICATION_VERSION = "finance_v26_authority_verifier_qualification.v1"
V26_AUTHORITY_VERIFIER_DIAGNOSTIC_VERSION = "finance_v26_authority_verifier_diagnostic.v1"
V26_AUTHORITY_VERIFIER_MUTATION_VERSION = "finance_v26_authority_verifier_mutation.v1"

_IMPLEMENTATION_SOURCE_PATHS = (
    (
        "src/trusted_synthesis/experiments/vtdo_experiment/"
        "phase1_v26_authority_preserving_verifier_replay.py"
    ),
    (
        "src/trusted_synthesis/experiments/vtdo_experiment/"
        "phase1_v26_capability_reachability_failure_audit.py"
    ),
    ("src/trusted_synthesis/experiments/vtdo_experiment/phase1_v26_empirical_support_pilot.py"),
    "src/trusted_synthesis/runtime/agent/iterative.py",
    "src/trusted_synthesis/runtime/agent/public_operation.py",
)
_REPLAY_EXECUTION_ORDER = (
    "identical_failed_action_gate",
    "public_postcompletion_gate",
    "public_tool_argument_gate",
    "public_terminal_verification_gate",
    "public_operation_gate",
    "finance_tool_runtime",
    "public_action_neutral_projection",
    "tool_output_contract",
    "canonical_json_semantic_comparison",
)
_ACTION_BINDING_FIELDS = frozenset(
    {
        "available_resolution_actions",
        "correct_operator",
        "correct_parameters",
        "correct_tool_id",
        "expected_arguments",
        "operator",
        "parameters",
        "required_argument_patch",
        "required_next_tools",
        "required_prerequisite_action",
        "suggested_argument_patch",
    }
)

EmpiricalRole = Literal["capability_development", "state_reachability"]
MutationKind = Literal[
    "environment_identity",
    "result_payload",
    "action_binding_payload",
]


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class BoundFile(FrozenModel):
    relative_path: str = Field(min_length=1)
    sha256: str = Field(min_length=64, max_length=64)
    record_count: int = Field(ge=1)


class ImplementationSource(FrozenModel):
    relative_path: str = Field(min_length=1)
    sha256: str = Field(min_length=64, max_length=64)


class AuthorityPreservingReplayContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    source_failure_audit_report_id: str = Field(min_length=1)
    replay_execution_order: tuple[str, ...] = _REPLAY_EXECUTION_ORDER
    public_operation_contract_required: Literal[True] = True
    public_action_neutral_repair_required: Literal[True] = True
    typed_terminal_target_required: Literal[True] = True
    failed_result_projection: Literal["typed_action_neutral_semantics_only"] = (
        "typed_action_neutral_semantics_only"
    )
    comparison_rule: Literal["canonical_json_semantic_equality"] = (
        "canonical_json_semantic_equality"
    )
    model_repair_decision_retained: Literal[True] = True
    historical_outcome_rescoring_permitted: Literal[False] = False
    schema_version: str = V26_AUTHORITY_VERIFIER_CONTRACT_VERSION

    @model_validator(mode="after")
    def validate_contract(self) -> AuthorityPreservingReplayContract:
        if self.replay_execution_order != _REPLAY_EXECUTION_ORDER:
            raise ValueError("authority-preserving Replay execution order changed")
        if self.contract_id != authority_preserving_replay_contract_id(self):
            raise ValueError("authority-preserving Replay Contract identity is invalid")
        return self


class AuthorityPreservingReplayResult(FrozenModel):
    replay_id: str = Field(min_length=1)
    contract_id: str = Field(min_length=1)
    task_package_id: str = Field(min_length=1)
    environment_manifest_id: str = Field(min_length=1)
    observation_count: int = Field(ge=0)
    replayed_observation_count: int = Field(ge=0)
    selected_evidence_ids: tuple[str, ...]
    failure_ids: tuple[str, ...]
    passed: bool
    schema_version: str = V26_AUTHORITY_VERIFIER_REPLAY_VERSION

    @model_validator(mode="after")
    def validate_result(self) -> AuthorityPreservingReplayResult:
        if self.passed != (not self.failure_ids):
            raise ValueError("authority-preserving Replay status is inconsistent")
        if self.passed and self.replayed_observation_count != self.observation_count:
            raise ValueError("passing Replay did not cover every Observation")
        if self.replay_id != authority_preserving_replay_result_id(self):
            raise ValueError("authority-preserving Replay identity is invalid")
        return self


class AuthorityPreservingVerificationReport(FrozenModel):
    report_id: str = Field(min_length=1)
    replay_id: str = Field(min_length=1)
    task_package_id: str = Field(min_length=1)
    verifier_binding_id: str = Field(min_length=1)
    trajectory_id: str = Field(min_length=1)
    checks: dict[str, bool]
    selected_evidence_ids: tuple[str, ...]
    operation_lineage_evidence_ids: tuple[str, ...]
    verification_support_ids: tuple[str, ...]
    cited_evidence_ids: tuple[str, ...]
    satisfying_selected_support_set_id: str | None = None
    satisfying_citation_support_set_id: str | None = None
    mechanism_event_ids: tuple[str, ...]
    normalized_answer: dict[str, Any]
    matched_program_node_ids: tuple[str, ...]
    earliest_failure_stage: str | None = None
    valid: bool
    verifier_implementation_id: Literal["core.authority_preserving_executable_task_verifier"] = (
        "core.authority_preserving_executable_task_verifier"
    )
    verifier_version: Literal["authority_preserving_executable_task_verifier.v2"] = (
        "authority_preserving_executable_task_verifier.v2"
    )
    schema_version: str = V26_AUTHORITY_VERIFICATION_REPORT_VERSION

    @model_validator(mode="after")
    def validate_report(self) -> AuthorityPreservingVerificationReport:
        if set(self.checks) != set(VERIFICATION_CHECK_IDS):
            raise ValueError("authority-preserving Verifier Gate vector is incomplete")
        if self.valid != all(self.checks.values()):
            raise ValueError("authority-preserving Verifier validity is inconsistent")
        if self.earliest_failure_stage != _earliest_failure_stage(self.checks):
            raise ValueError("authority-preserving Verifier failure stage is inconsistent")
        if self.report_id != authority_preserving_verification_report_id(self):
            raise ValueError("authority-preserving Verification identity is invalid")
        return self


class HistoricalVerifierDiagnostic(FrozenModel):
    diagnostic_id: str = Field(min_length=1)
    role: EmpiricalRole
    rollout_id: str = Field(min_length=1)
    job_id: str = Field(min_length=1)
    task_package_id: str = Field(min_length=1)
    mechanism_id: str = Field(min_length=1)
    historical_verification_report_id: str = Field(min_length=1)
    prospective_verification_report_id: str = Field(min_length=1)
    historical_runtime_replay_passed: bool
    prospective_runtime_replay_passed: Literal[True] = True
    non_replay_checks_identical: Literal[True] = True
    historical_independent_validity: bool
    prospective_v2_validity: bool
    prospective_validity_candidate: bool
    historical_validity_reclassified: Literal[False] = False
    historical_path_assignment_changed: Literal[False] = False
    creates_state_support: Literal[False] = False
    schema_version: str = V26_AUTHORITY_VERIFIER_DIAGNOSTIC_VERSION

    @model_validator(mode="after")
    def validate_diagnostic(self) -> HistoricalVerifierDiagnostic:
        if self.prospective_validity_candidate != (
            not self.historical_independent_validity and self.prospective_v2_validity
        ):
            raise ValueError("prospective Verifier candidate status is inconsistent")
        if self.diagnostic_id != historical_verifier_diagnostic_id(self):
            raise ValueError("historical Verifier diagnostic identity is invalid")
        return self


class VerifierMutationAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    role: EmpiricalRole
    source_rollout_id: str = Field(min_length=1)
    mutation_kind: MutationKind
    mutated_observation_index: int = Field(ge=0)
    replay_failure_ids: tuple[str, ...] = Field(min_length=1)
    mutation_rejected: Literal[True] = True
    historical_outcome_mutated: Literal[False] = False
    schema_version: str = V26_AUTHORITY_VERIFIER_MUTATION_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> VerifierMutationAudit:
        if self.audit_id != verifier_mutation_audit_id(self):
            raise ValueError("Verifier mutation audit identity is invalid")
        return self


class AuthorityPreservingVerifierQualificationReport(FrozenModel):
    report_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    source_failure_audit_report_id: str = Field(min_length=1)
    source_failure_audit_report_sha256: str = Field(min_length=64, max_length=64)
    replay_contract: AuthorityPreservingReplayContract
    completed_trajectory_count: Literal[45] = 45
    capability_completed_trajectory_count: Literal[14] = 14
    reachability_completed_trajectory_count: Literal[31] = 31
    historical_runtime_replay_pass_count: Literal[27] = 27
    historical_runtime_replay_failure_count: Literal[18] = 18
    authority_preserving_replay_pass_count: Literal[45] = 45
    non_replay_check_identity_count: Literal[45] = 45
    prospective_validity_candidate_count: Literal[15] = 15
    historical_validity_reclassification_count: Literal[0] = 0
    environment_identity_mutation_reject_count: Literal[45] = 45
    result_payload_mutation_reject_count: Literal[45] = 45
    action_binding_mutation_reject_count: Literal[18] = 18
    destructive_mutation_reject_count: Literal[108] = 108
    historical_capability_valid_count: Literal[4] = 4
    historical_reachability_valid_count: Literal[21] = 21
    historical_admitted_state_count: Literal[0] = 0
    historical_admitted_task_count: Literal[0] = 0
    historical_results_reclassified: Literal[False] = False
    historical_state_support_freeze_mutated: Literal[False] = False
    capability_confirmation_authorized: Literal[False] = False
    state_support_confirmation_authorized: Literal[False] = False
    no_c_vtdo_authorized: Literal[False] = False
    student_training_authorized: Literal[False] = False
    exact_target_authorized: Literal[False] = False
    gp_c_authorized: Literal[False] = False
    production_contribution: Literal[0] = 0
    next_permitted_stage: Literal[
        "fresh_verifier_bound_task_rematerialization_and_instrument_preflight_only"
    ] = "fresh_verifier_bound_task_rematerialization_and_instrument_preflight_only"
    source_artifact_files: tuple[BoundFile, ...] = Field(min_length=10)
    immutable_detail_files: tuple[BoundFile, ...] = Field(min_length=3, max_length=3)
    implementation_source_files: tuple[ImplementationSource, ...] = Field(
        min_length=5, max_length=5
    )
    api_call_count: Literal[0] = 0
    gpu_job_count: Literal[0] = 0
    status: Literal["passed"] = "passed"
    schema_version: str = V26_AUTHORITY_VERIFIER_QUALIFICATION_VERSION

    @model_validator(mode="after")
    def validate_report(self) -> AuthorityPreservingVerifierQualificationReport:
        if tuple(item.relative_path for item in self.implementation_source_files) != tuple(
            sorted(_IMPLEMENTATION_SOURCE_PATHS)
        ):
            raise ValueError("Verifier qualification implementation manifest is incomplete")
        if tuple(item.relative_path for item in self.immutable_detail_files) != (
            "destructive_mutation_audits.json",
            "historical_verifier_diagnostics.json",
            "replay_contract.json",
        ):
            raise ValueError("Verifier qualification detail manifest is incomplete")
        if self.report_id != authority_preserving_verifier_qualification_report_id(self):
            raise ValueError("authority-preserving Verifier qualification identity is invalid")
        return self


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _record_count(path: Path) -> int:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return len(payload) if isinstance(payload, list) else 1


def _write_json(path: Path, payload: Any) -> None:
    serialized = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if path.exists():
        if path.read_text(encoding="utf-8") != serialized:
            raise ValueError(f"Verifier qualification immutable JSON changed: {path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(serialized, encoding="utf-8")
    temporary.replace(path)


def _canonical_payload(value: AgentToolResult | AgentToolObservation) -> dict[str, Any]:
    payload = {
        "status": value.status,
        "result": value.result,
        "evidence_ids": value.evidence_ids,
        "provenance_hashes": value.provenance_hashes,
        "host_events": value.host_events,
        "error_code": value.error_code,
        "error_message": value.error_message,
    }
    return cast(dict[str, Any], json.loads(json.dumps(payload, sort_keys=True)))


def _call_signature(observation: AgentToolObservation) -> str:
    return canonical_hash(
        {
            "tool_id": observation.call.tool_id,
            "arguments": observation.call.arguments,
        },
        prefix="finance_v26_authority_verifier_failed_call:",
    )


def _observation_identity_valid(observation: AgentToolObservation) -> bool:
    try:
        AgentToolObservation.model_validate(observation.model_dump(mode="json"))
    except ValueError:
        return False
    return True


def replay_authority_preserving_observations(
    contract: AuthorityPreservingReplayContract,
    record: OperationalTaskRecord,
    environment: AgentToolEnvironmentManifest,
    observations: Sequence[AgentToolObservation],
) -> AuthorityPreservingReplayResult:
    package = record.task_package
    if package.operation_contract is None:
        raise ValueError("authority-preserving Replay requires a public Operation contract")
    if package.action_neutral_repair_contract is None:
        raise ValueError("authority-preserving Replay requires an action-neutral repair contract")
    if package.terminal_verification_target is None:
        raise ValueError("authority-preserving Replay requires a typed terminal target")
    recovery = (
        FinanceTypedRecoveryScenario.model_validate(record.recovery_scenario)
        if record.recovery_scenario is not None
        else None
    )
    runtime = FinanceExecutableSupportRuntime(
        record.public_corpus,
        environment,
        recovery_scenario=recovery,
    )
    task = package.task.public
    failures: list[str] = []
    failed_signatures: set[str] = set()
    observed: list[AgentToolObservation] = []
    replayed_count = 0
    for index, observation in enumerate(observations):
        if not _observation_identity_valid(observation):
            failures.append(f"observation:{index}:identity")
            observed.append(observation)
            continue
        if observation.environment_manifest_id != environment.manifest_id:
            failures.append(f"observation:{index}:environment_identity")
            observed.append(observation)
            continue
        spec = environment.tools_by_id.get(observation.call.tool_id)
        if spec is None:
            failures.append(f"observation:{index}:unknown_tool")
            observed.append(observation)
            continue
        signature = _call_signature(observation)
        if signature in failed_signatures:
            replayed = AgentToolResult(
                status="failed",
                result={
                    "retry_contract": {
                        "policy": ARGUMENT_PATCH_REQUIRED_POLICY,
                        "suggested_argument_patch": {
                            "rule": (
                                "change at least one argument according to the latest public "
                                "error; the identical failed action remains blocked"
                            )
                        },
                    }
                },
                error_code="identical_failed_action_blocked",
                error_message="The Host blocked an identical failed action without executing it.",
            )
        else:
            replayed = (
                public_postcompletion_action_rejection(task, tuple(observed), observation.call)
                or agent_tool_argument_rejection(spec, observation.call)
                or public_terminal_verification_rejection(task, tuple(observed), observation.call)
                or public_operation_step_rejection(task, tuple(observed), observation.call)
                or runtime.execute(observation.call)
            )
        replayed = public_action_neutral_repair_result(
            task,
            tuple(observed),
            observation.call,
            replayed,
        )
        if replayed.status == "succeeded":
            try:
                spec.validate_output(replayed.result)
            except ValueError as error:
                failures.append(f"observation:{index}:output_contract:{error}")
        if _canonical_payload(replayed) != _canonical_payload(observation):
            failures.append(f"observation:{index}:replay_mismatch")
        replayed_count += 1
        if observation.status == "succeeded":
            failed_signatures.clear()
        else:
            failed_signatures.add(signature)
        observed.append(observation)
    values: dict[str, Any] = {
        "contract_id": contract.contract_id,
        "task_package_id": package.package_id,
        "environment_manifest_id": environment.manifest_id,
        "observation_count": len(observations),
        "replayed_observation_count": replayed_count,
        "selected_evidence_ids": tuple(sorted(runtime.selected_evidence_ids)),
        "failure_ids": tuple(failures),
        "passed": not failures,
    }
    provisional = AuthorityPreservingReplayResult.model_construct(replay_id="pending", **values)
    return AuthorityPreservingReplayResult(
        replay_id=authority_preserving_replay_result_id(provisional),
        **values,
    )


def _successful_observations(
    observations: Sequence[AgentToolObservation],
    tool_id: str,
) -> tuple[AgentToolObservation, ...]:
    return tuple(
        item for item in observations if item.call.tool_id == tool_id and item.status == "succeeded"
    )


def _replace_runtime_references(value: Any, mapping: Mapping[str, str]) -> Any:
    if isinstance(value, str):
        return mapping.get(value, value)
    if isinstance(value, Mapping):
        return {key: _replace_runtime_references(item, mapping) for key, item in value.items()}
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


def _answer_and_citations(
    result: IterativeAgentSolveResult,
) -> tuple[dict[str, Any], tuple[str, ...]]:
    final = result.trajectory.final_answer
    answer = final.get("result") if isinstance(final, Mapping) else None
    citations = final.get("citations") if isinstance(final, Mapping) else None
    if not isinstance(answer, Mapping) or not isinstance(citations, list):
        return {}, ()
    evidence_ids = tuple(
        str(item["evidence_id"])
        for item in citations
        if isinstance(item, Mapping) and item.get("evidence_id")
    )
    return dict(answer), evidence_ids


def _earliest_failure_stage(checks: Mapping[str, bool]) -> str | None:
    return next((stage for check, stage in FAILURE_STAGE_ORDER if not checks[check]), None)


def verify_authority_preserving_agent_result(
    contract: AuthorityPreservingReplayContract,
    record: OperationalTaskRecord,
    environment: AgentToolEnvironmentManifest,
    result: IterativeAgentSolveResult,
) -> AuthorityPreservingVerificationReport:
    replay = replay_authority_preserving_observations(
        contract,
        record,
        environment,
        result.observations,
    )
    program_complete, matched_nodes, runtime_to_node, operation_lineage = match_empirical_program(
        record, result.observations
    )
    answer, citations = _answer_and_citations(result)
    normalized_answer = _project_answer(
        cast(dict[str, Any], _replace_runtime_references(answer, runtime_to_node)),
        record.answer_projection,
    )
    lattice = record.task_package.evidence_support_lattice
    selected_support = matching_sufficient_support_set(lattice, replay.selected_evidence_ids)
    citation_support = matching_sufficient_support_set(lattice, citations)
    verification_support = tuple(
        sorted(
            {
                str(evidence_id)
                for item in _successful_observations(result.observations, "cross_check_evidence")
                if item.result.get("verified") is True
                for evidence_id in item.result.get("support") or ()
            }
        )
    )
    mechanism = evaluate_mechanism_estimand(
        record,
        result.observations,
        stopped_by_model=result.audit.stopped_by_model,
    )
    first_verified = next(
        (
            index
            for index, item in enumerate(result.observations)
            if item.call.tool_id == "cross_check_evidence"
            and item.status == "succeeded"
            and item.result.get("verified") is True
        ),
        None,
    )
    no_postcompletion = first_verified is None or first_verified == len(result.observations) - 1
    necessary = set(lattice.necessary_evidence_ids)
    noninterference = bool(
        result.audit.public_state_condition_hash is None
        and len(result.audit.model_request_prompts)
        == len(result.audit.model_request_prompt_noninterference_attestation_hashes)
    )
    checks = {
        "runtime_replay_passed": replay.passed,
        "model_input_noninterference_passed": noninterference,
        "only_allowed_tools": {item.call.tool_id for item in result.observations}
        <= set(record.task_package.tool_closure.allowed_tool_ids),
        "operation_lineage_complete": program_complete and necessary <= set(operation_lineage),
        "evidence_support_complete": selected_support is not None,
        "verification_complete": necessary <= set(verification_support),
        "answer_projection_complete": normalized_answer == record.projected_expected_output,
        "citation_complete": citation_support is not None,
        "mechanism_complete": mechanism.success,
        "no_postcompletion_violation": no_postcompletion,
    }
    values: dict[str, Any] = {
        "replay_id": replay.replay_id,
        "task_package_id": record.task_package.package_id,
        "verifier_binding_id": record.task_package.verifier_binding.binding_id,
        "trajectory_id": result.trajectory.trajectory_id,
        "checks": checks,
        "selected_evidence_ids": replay.selected_evidence_ids,
        "operation_lineage_evidence_ids": operation_lineage,
        "verification_support_ids": verification_support,
        "cited_evidence_ids": citations,
        "satisfying_selected_support_set_id": (
            selected_support.support_set_id if selected_support is not None else None
        ),
        "satisfying_citation_support_set_id": (
            citation_support.support_set_id if citation_support is not None else None
        ),
        "mechanism_event_ids": mechanism.observed_event_ids,
        "normalized_answer": normalized_answer,
        "matched_program_node_ids": matched_nodes,
        "earliest_failure_stage": _earliest_failure_stage(checks),
        "valid": all(checks.values()),
    }
    provisional = AuthorityPreservingVerificationReport.model_construct(
        report_id="pending", **values
    )
    return AuthorityPreservingVerificationReport(
        report_id=authority_preserving_verification_report_id(provisional),
        **values,
    )


def _load_raw_payload(rollout: EmpiricalPilotRollout, run_dir: Path) -> dict[str, Any]:
    path = Path(rollout.raw_artifact_uri).resolve()
    try:
        path.relative_to(run_dir.resolve())
    except ValueError as error:
        raise ValueError("Verifier qualification raw Artifact is outside its run") from error
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != rollout.raw_artifact_sha256:
        raise ValueError("Verifier qualification raw Artifact hash replay failed")
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise ValueError("Verifier qualification raw Artifact is not an object")
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    if canonical != raw:
        raise ValueError("Verifier qualification raw Artifact is not canonical JSON")
    return cast(dict[str, Any], payload)


def _load_solve_result(payload: Mapping[str, Any]) -> IterativeAgentSolveResult:
    trajectory = payload.get("trajectory")
    audit = payload.get("agent_audit")
    if not isinstance(trajectory, Mapping) or not isinstance(audit, Mapping):
        raise ValueError("Verifier qualification requires a completed trajectory")
    observations = tuple(
        step["observation"]
        for step in trajectory.get("steps") or ()
        if isinstance(step, Mapping)
        and isinstance(step.get("observation"), Mapping)
        and "observation_id" in step["observation"]
    )
    return IterativeAgentSolveResult.model_validate(
        {
            "trajectory": trajectory,
            "audit": audit,
            "observations": observations,
        }
    )


def _load_rollouts(run_dir: Path) -> tuple[EmpiricalPilotRollout, ...]:
    return tuple(
        EmpiricalPilotRollout.model_validate(item)
        for item in json.loads((run_dir / "empirical_rollouts.json").read_text(encoding="utf-8"))
    )


def _load_capability_records(task_source_dir: Path) -> tuple[OperationalTaskRecord, ...]:
    report = FreshCapabilityPopulationReport.model_validate_json(
        (task_source_dir / "report.json").read_text(encoding="utf-8")
    )
    return tuple(report.task_records)


def _load_reachability_records(task_source_dir: Path) -> tuple[OperationalTaskRecord, ...]:
    report = AuthorityPreservingHardeningReport.model_validate_json(
        (task_source_dir / "report.json").read_text(encoding="utf-8")
    )
    return tuple(
        item for item in report.task_records if item.intended_use == "vtdo_multistate_candidate"
    )


def _load_environments(task_source_dir: Path) -> dict[str, AgentToolEnvironmentManifest]:
    values = tuple(
        AgentToolEnvironmentManifest.model_validate(item)
        for item in json.loads(
            (task_source_dir / "tool_environment_manifests.json").read_text(encoding="utf-8")
        )
    )
    return {item.manifest_id: item for item in values}


def _historical_diagnostics(
    *,
    contract: AuthorityPreservingReplayContract,
    role: EmpiricalRole,
    run_dir: Path,
    rollouts: Sequence[EmpiricalPilotRollout],
    records: Mapping[str, OperationalTaskRecord],
    environments: Mapping[str, AgentToolEnvironmentManifest],
) -> tuple[
    tuple[HistoricalVerifierDiagnostic, ...],
    tuple[tuple[EmpiricalPilotRollout, OperationalTaskRecord, IterativeAgentSolveResult], ...],
]:
    diagnostics = []
    fixtures = []
    for rollout in rollouts:
        historical = rollout.verification
        if historical is None:
            continue
        record = records[rollout.task_record_id]
        result = _load_solve_result(_load_raw_payload(rollout, run_dir))
        prospective = verify_authority_preserving_agent_result(
            contract,
            record,
            environments[record.environment_manifest_id],
            result,
        )
        historical_non_replay = {
            key: value for key, value in historical.checks.items() if key != "runtime_replay_passed"
        }
        prospective_non_replay = {
            key: value
            for key, value in prospective.checks.items()
            if key != "runtime_replay_passed"
        }
        if historical_non_replay != prospective_non_replay:
            raise ValueError("Verifier v2 changed a non-Replay historical Gate")
        values: dict[str, Any] = {
            "role": role,
            "rollout_id": rollout.rollout_id,
            "job_id": rollout.job_id,
            "task_package_id": rollout.task_package_id,
            "mechanism_id": rollout.mechanism_id,
            "historical_verification_report_id": historical.report_id,
            "prospective_verification_report_id": prospective.report_id,
            "historical_runtime_replay_passed": historical.checks["runtime_replay_passed"],
            "prospective_runtime_replay_passed": prospective.checks["runtime_replay_passed"],
            "non_replay_checks_identical": historical_non_replay == prospective_non_replay,
            "historical_independent_validity": historical.valid,
            "prospective_v2_validity": prospective.valid,
            "prospective_validity_candidate": not historical.valid and prospective.valid,
        }
        provisional = HistoricalVerifierDiagnostic.model_construct(
            diagnostic_id="pending", **values
        )
        diagnostics.append(
            HistoricalVerifierDiagnostic(
                diagnostic_id=historical_verifier_diagnostic_id(provisional),
                **values,
            )
        )
        fixtures.append((rollout, record, result))
    return (
        tuple(sorted(diagnostics, key=lambda item: item.diagnostic_id)),
        tuple(fixtures),
    )


def _mutated_observation(
    observation: AgentToolObservation,
    *,
    environment_manifest_id: str | None = None,
    result: dict[str, Any] | None = None,
) -> AgentToolObservation:
    tool_result = AgentToolResult(
        status=observation.status,
        result=observation.result if result is None else result,
        evidence_ids=observation.evidence_ids,
        provenance_hashes=observation.provenance_hashes,
        host_events=observation.host_events,
        error_code=observation.error_code,
        error_message=observation.error_message,
    )
    return make_agent_tool_observation(
        environment_manifest_id=(
            observation.environment_manifest_id
            if environment_manifest_id is None
            else environment_manifest_id
        ),
        call=observation.call,
        result=tool_result,
        observation_time_hash=observation.observation_time_hash,
    )


def _mutation_audit(
    *,
    contract: AuthorityPreservingReplayContract,
    role: EmpiricalRole,
    rollout: EmpiricalPilotRollout,
    record: OperationalTaskRecord,
    result: IterativeAgentSolveResult,
    environment: AgentToolEnvironmentManifest,
    mutation_kind: MutationKind,
) -> VerifierMutationAudit:
    observations = list(result.observations)
    if mutation_kind == "action_binding_payload":
        index = next(
            (position for position, item in enumerate(observations) if item.status == "failed"),
            None,
        )
        if index is None:
            raise ValueError("action-binding mutation requires a failed Observation")
        source = observations[index]
        mutated_result = dict(source.result)
        mutated_result["suggested_argument_patch"] = {"tool_id": "forbidden_binding"}
        observations[index] = _mutated_observation(source, result=mutated_result)
    else:
        index = 0
        source = observations[index]
        if mutation_kind == "environment_identity":
            observations[index] = _mutated_observation(
                source,
                environment_manifest_id="agent_tool_environment:tampered",
            )
        else:
            mutated_result = dict(source.result)
            mutated_result["audit_mutation"] = True
            observations[index] = _mutated_observation(source, result=mutated_result)
    replay = replay_authority_preserving_observations(
        contract,
        record,
        environment,
        observations,
    )
    if replay.passed:
        raise ValueError(f"Verifier mutation passed unexpectedly: {mutation_kind}")
    values: dict[str, Any] = {
        "role": role,
        "source_rollout_id": rollout.rollout_id,
        "mutation_kind": mutation_kind,
        "mutated_observation_index": index,
        "replay_failure_ids": replay.failure_ids,
    }
    provisional = VerifierMutationAudit.model_construct(audit_id="pending", **values)
    return VerifierMutationAudit(
        audit_id=verifier_mutation_audit_id(provisional),
        **values,
    )


def _mutation_audits(
    *,
    contract: AuthorityPreservingReplayContract,
    role: EmpiricalRole,
    fixtures: Sequence[
        tuple[EmpiricalPilotRollout, OperationalTaskRecord, IterativeAgentSolveResult]
    ],
    environments: Mapping[str, AgentToolEnvironmentManifest],
) -> tuple[VerifierMutationAudit, ...]:
    output = []
    for rollout, record, result in fixtures:
        environment = environments[record.environment_manifest_id]
        for kind in ("environment_identity", "result_payload"):
            output.append(
                _mutation_audit(
                    contract=contract,
                    role=role,
                    rollout=rollout,
                    record=record,
                    result=result,
                    environment=environment,
                    mutation_kind=cast(MutationKind, kind),
                )
            )
        historical = rollout.verification
        if historical is not None and not historical.checks["runtime_replay_passed"]:
            output.append(
                _mutation_audit(
                    contract=contract,
                    role=role,
                    rollout=rollout,
                    record=record,
                    result=result,
                    environment=environment,
                    mutation_kind="action_binding_payload",
                )
            )
    return tuple(sorted(output, key=lambda item: item.audit_id))


def _bound_file(path: Path, package_root: Path) -> BoundFile:
    return BoundFile(
        relative_path=str(path.relative_to(package_root)),
        sha256=_sha256(path),
        record_count=_record_count(path),
    )


def _detail_file(path: Path, output_dir: Path, record_count: int) -> BoundFile:
    return BoundFile(
        relative_path=str(path.relative_to(output_dir)),
        sha256=_sha256(path),
        record_count=record_count,
    )


def _implementation_sources(package_root: Path) -> tuple[ImplementationSource, ...]:
    return tuple(
        ImplementationSource(relative_path=value, sha256=_sha256(package_root / value))
        for value in sorted(_IMPLEMENTATION_SOURCE_PATHS)
    )


def _source_artifacts(
    *,
    package_root: Path,
    failure_audit_dir: Path,
    capability_run_dir: Path,
    capability_task_source_dir: Path,
    reachability_run_dir: Path,
    reachability_task_source_dir: Path,
) -> tuple[BoundFile, ...]:
    paths = (
        failure_audit_dir / "report.json",
        failure_audit_dir / "verifier_replay_differentials.json",
        capability_run_dir / "empirical_rollouts.json",
        capability_run_dir / "report.json",
        capability_task_source_dir / "operational_task_records.json",
        capability_task_source_dir / "tool_environment_manifests.json",
        capability_task_source_dir / "report.json",
        reachability_run_dir / "empirical_rollouts.json",
        reachability_run_dir / "report.json",
        reachability_task_source_dir / "operational_task_records.json",
        reachability_task_source_dir / "tool_environment_manifests.json",
        reachability_task_source_dir / "report.json",
    )
    return tuple(
        sorted(
            (_bound_file(path, package_root) for path in paths),
            key=lambda item: item.relative_path,
        )
    )


def build_authority_preserving_verifier_qualification(
    *,
    run_id: str,
    failure_audit_dir: Path,
    capability_run_dir: Path,
    capability_task_source_dir: Path,
    reachability_run_dir: Path,
    reachability_task_source_dir: Path,
    output_dir: Path,
    package_root: Path,
) -> AuthorityPreservingVerifierQualificationReport:
    source_audit = CapabilityReachabilityFailureAuditReport.model_validate_json(
        (failure_audit_dir / "report.json").read_text(encoding="utf-8")
    )
    if source_audit.next_permitted_stage != "authority_preserving_verifier_replay_repair_only":
        raise ValueError("v26.75 is not authorized by the source failure audit")
    contract_values = {"source_failure_audit_report_id": source_audit.report_id}
    provisional_contract = AuthorityPreservingReplayContract.model_construct(
        contract_id="pending", **contract_values
    )
    contract = AuthorityPreservingReplayContract(
        contract_id=authority_preserving_replay_contract_id(provisional_contract),
        **contract_values,
    )

    capability_rollouts = _load_rollouts(capability_run_dir)
    reachability_rollouts = _load_rollouts(reachability_run_dir)
    capability_records_tuple = _load_capability_records(capability_task_source_dir)
    reachability_records_tuple = _load_reachability_records(reachability_task_source_dir)
    capability_records = {item.record_id: item for item in capability_records_tuple}
    reachability_records = {item.record_id: item for item in reachability_records_tuple}
    capability_environments = _load_environments(capability_task_source_dir)
    reachability_environments = _load_environments(reachability_task_source_dir)

    capability_diagnostics, capability_fixtures = _historical_diagnostics(
        contract=contract,
        role="capability_development",
        run_dir=capability_run_dir,
        rollouts=capability_rollouts,
        records=capability_records,
        environments=capability_environments,
    )
    reachability_diagnostics, reachability_fixtures = _historical_diagnostics(
        contract=contract,
        role="state_reachability",
        run_dir=reachability_run_dir,
        rollouts=reachability_rollouts,
        records=reachability_records,
        environments=reachability_environments,
    )
    diagnostics = tuple(
        sorted(
            (*capability_diagnostics, *reachability_diagnostics),
            key=lambda item: item.diagnostic_id,
        )
    )
    mutations = tuple(
        sorted(
            (
                *_mutation_audits(
                    contract=contract,
                    role="capability_development",
                    fixtures=capability_fixtures,
                    environments=capability_environments,
                ),
                *_mutation_audits(
                    contract=contract,
                    role="state_reachability",
                    fixtures=reachability_fixtures,
                    environments=reachability_environments,
                ),
            ),
            key=lambda item: item.audit_id,
        )
    )
    if len(diagnostics) != 45 or not all(
        item.prospective_runtime_replay_passed and item.non_replay_checks_identical
        for item in diagnostics
    ):
        raise ValueError("Verifier v2 qualification did not preserve the completed denominator")
    mutation_counts = {
        kind: sum(item.mutation_kind == kind for item in mutations)
        for kind in ("environment_identity", "result_payload", "action_binding_payload")
    }
    if mutation_counts != {
        "environment_identity": 45,
        "result_payload": 45,
        "action_binding_payload": 18,
    }:
        raise ValueError("Verifier v2 destructive mutation matrix is incomplete")

    output_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "destructive_mutation_audits.json": mutations,
        "historical_verifier_diagnostics.json": diagnostics,
        "replay_contract.json": contract,
    }
    for relative, value in paths.items():
        payload: Any
        if isinstance(value, BaseModel):
            payload = value.model_dump(mode="json")
        else:
            payload = [item.model_dump(mode="json") for item in value]
        _write_json(output_dir / relative, payload)
    details = tuple(
        _detail_file(
            output_dir / relative,
            output_dir,
            1 if isinstance(value, BaseModel) else len(value),
        )
        for relative, value in sorted(paths.items())
    )
    historical_replay_pass = sum(item.historical_runtime_replay_passed for item in diagnostics)
    prospective_candidates = sum(item.prospective_validity_candidate for item in diagnostics)
    values: dict[str, Any] = {
        "run_id": run_id,
        "source_failure_audit_report_id": source_audit.report_id,
        "source_failure_audit_report_sha256": _sha256(failure_audit_dir / "report.json"),
        "replay_contract": contract,
        "completed_trajectory_count": len(diagnostics),
        "capability_completed_trajectory_count": len(capability_diagnostics),
        "reachability_completed_trajectory_count": len(reachability_diagnostics),
        "historical_runtime_replay_pass_count": historical_replay_pass,
        "historical_runtime_replay_failure_count": len(diagnostics) - historical_replay_pass,
        "authority_preserving_replay_pass_count": sum(
            item.prospective_runtime_replay_passed for item in diagnostics
        ),
        "non_replay_check_identity_count": sum(
            item.non_replay_checks_identical for item in diagnostics
        ),
        "prospective_validity_candidate_count": prospective_candidates,
        "historical_validity_reclassification_count": 0,
        "environment_identity_mutation_reject_count": mutation_counts["environment_identity"],
        "result_payload_mutation_reject_count": mutation_counts["result_payload"],
        "action_binding_mutation_reject_count": mutation_counts["action_binding_payload"],
        "destructive_mutation_reject_count": len(mutations),
        "historical_capability_valid_count": source_audit.capability_independently_valid_count,
        "historical_reachability_valid_count": source_audit.reachability_independently_valid_count,
        "historical_admitted_state_count": source_audit.admitted_state_count,
        "historical_admitted_task_count": source_audit.admitted_task_count,
        "source_artifact_files": _source_artifacts(
            package_root=package_root,
            failure_audit_dir=failure_audit_dir,
            capability_run_dir=capability_run_dir,
            capability_task_source_dir=capability_task_source_dir,
            reachability_run_dir=reachability_run_dir,
            reachability_task_source_dir=reachability_task_source_dir,
        ),
        "immutable_detail_files": details,
        "implementation_source_files": _implementation_sources(package_root),
    }
    provisional = AuthorityPreservingVerifierQualificationReport.model_construct(
        report_id="pending", **values
    )
    report = AuthorityPreservingVerifierQualificationReport(
        report_id=authority_preserving_verifier_qualification_report_id(provisional),
        **values,
    )
    _write_json(output_dir / "report.json", report.model_dump(mode="json"))
    return report


def authority_preserving_replay_contract_id(
    value: AuthorityPreservingReplayContract,
) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"contract_id"}),
        prefix="finance_v26_authority_verifier_contract:",
    )


def authority_preserving_replay_result_id(
    value: AuthorityPreservingReplayResult,
) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"replay_id"}),
        prefix="finance_v26_authority_verifier_replay:",
    )


def authority_preserving_verification_report_id(
    value: AuthorityPreservingVerificationReport,
) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"report_id"}),
        prefix="finance_v26_authority_verification_report:",
    )


def historical_verifier_diagnostic_id(value: HistoricalVerifierDiagnostic) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"diagnostic_id"}),
        prefix="finance_v26_authority_verifier_diagnostic:",
    )


def verifier_mutation_audit_id(value: VerifierMutationAudit) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"audit_id"}),
        prefix="finance_v26_authority_verifier_mutation:",
    )


def authority_preserving_verifier_qualification_report_id(
    value: AuthorityPreservingVerifierQualificationReport,
) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"report_id"}),
        prefix="finance_v26_authority_verifier_qualification:",
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Qualify the prospective Finance v26 authority-preserving Verifier Replay"
    )
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--failure-audit-dir", type=Path, required=True)
    parser.add_argument("--capability-run-dir", type=Path, required=True)
    parser.add_argument("--capability-task-source-dir", type=Path, required=True)
    parser.add_argument("--reachability-run-dir", type=Path, required=True)
    parser.add_argument("--reachability-task-source-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--package-root", type=Path, default=Path(__file__).resolve().parents[4])
    args = parser.parse_args()
    report = build_authority_preserving_verifier_qualification(
        run_id=args.run_id,
        failure_audit_dir=args.failure_audit_dir,
        capability_run_dir=args.capability_run_dir,
        capability_task_source_dir=args.capability_task_source_dir,
        reachability_run_dir=args.reachability_run_dir,
        reachability_task_source_dir=args.reachability_task_source_dir,
        output_dir=args.output_dir,
        package_root=args.package_root,
    )
    print(
        json.dumps(
            {
                "report_id": report.report_id,
                "status": report.status,
                "completed_trajectories": report.completed_trajectory_count,
                "v2_replay_passes": report.authority_preserving_replay_pass_count,
                "prospective_validity_candidates": report.prospective_validity_candidate_count,
                "mutation_rejects": report.destructive_mutation_reject_count,
                "next_permitted_stage": report.next_permitted_stage,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
