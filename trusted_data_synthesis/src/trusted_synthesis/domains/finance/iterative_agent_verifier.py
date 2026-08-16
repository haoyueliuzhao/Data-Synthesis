from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.core.evaluation.answer import CandidateAnswerNormalizer
from trusted_synthesis.core.evidence.corpus import EvidenceCorpus
from trusted_synthesis.core.evidence.validation import EvidenceValidator
from trusted_synthesis.core.graph.validation import ProofGraphValidator
from trusted_synthesis.core.operations.program import (
    ProgramExecutionError,
    TaskProgramOracleVerifier,
)
from trusted_synthesis.core.operations.registry import OperationRegistry, default_registry
from trusted_synthesis.core.task.answer_schema import allowed_result_fields, required_answer_fields
from trusted_synthesis.core.task.schema import TaskRequirement
from trusted_synthesis.core.trajectory.candidate_verifier import CandidateCheck
from trusted_synthesis.core.trajectory.schema import ActionType, StepStatus, WorkflowKind
from trusted_synthesis.core.trajectory.specification import TrajectoryVerificationContext
from trusted_synthesis.domains.finance.capability_submechanism_runtime import (
    FinanceCapabilitySubmechanismRuntime,
    FinanceSubmechanismScenario,
    submechanism_scenario_from_oracle,
)
from trusted_synthesis.domains.finance.interactive_agent_runtime import (
    FinanceArchiveInteractiveToolRuntime,
    FinanceCapabilityMechanismScenario,
    FinanceTypedRecoveryScenario,
    capability_mechanism_scenario_from_oracle,
    recovery_scenario_from_metadata,
)
from trusted_synthesis.hashing import canonical_hash
from trusted_synthesis.runtime.agent.iterative import (
    MODEL_FORBIDDEN_FIELD_NAMES,
    IterativeAgentSolveResult,
)
from trusted_synthesis.runtime.tools import (
    AgentToolEnvironmentManifest,
    AgentToolObservation,
    AgentToolResult,
    agent_tool_argument_rejection,
)

FINANCE_ITERATIVE_AGENT_VERIFIER_VERSION = "finance_iterative_agent_verifier.v5"


class FinanceIterativeAgentVerificationReport(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    report_id: str = Field(min_length=1)
    task_id: str = Field(min_length=1)
    omega_context_id: str = Field(min_length=1)
    trajectory_id: str = Field(min_length=1)
    audit_id: str = Field(min_length=1)
    environment_manifest_id: str = Field(min_length=1)
    checks: tuple[CandidateCheck, ...] = Field(min_length=1)
    retrieved_evidence_ids: tuple[str, ...]
    selected_evidence_ids: tuple[str, ...]
    cited_evidence_ids: tuple[str, ...]
    gold_evidence_ids: tuple[str, ...] = Field(min_length=1)
    citation_recall: float = Field(ge=0, le=1)
    citation_precision: float = Field(ge=0, le=1)
    selection_recall: float = Field(ge=0, le=1)
    selection_precision: float = Field(ge=0, le=1)
    normalized_candidate_answer: dict[str, Any]
    normalized_oracle_answer: dict[str, Any]
    replayed_tool_call_count: int = Field(ge=0)
    successful_verification_count: int = Field(ge=0)
    evidence_provenance_completeness: float = Field(ge=0, le=1)
    schema_version: str = FINANCE_ITERATIVE_AGENT_VERIFIER_VERSION

    @property
    def valid(self) -> bool:
        return all(item.passed for item in self.checks)

    @model_validator(mode="after")
    def validate_identity(self) -> FinanceIterativeAgentVerificationReport:
        if self.report_id != finance_iterative_agent_verification_report_id(self):
            raise ValueError("Finance iterative Agent verification identity is invalid")
        return self


class FinanceIterativeAgentVerifier:
    """Independent Oracle and deterministic replay gates for real Finance Agent rollouts."""

    def __init__(self, registry: OperationRegistry | None = None) -> None:
        self._registry = registry or default_registry()
        self._oracle = TaskProgramOracleVerifier(self._registry)
        self._normalizer = CandidateAnswerNormalizer()
        self._evidence_validator = EvidenceValidator()
        self._graph_validator = ProofGraphValidator()

    @property
    def manifest_hash(self) -> str:
        return canonical_hash(
            {
                "version": FINANCE_ITERATIVE_AGENT_VERIFIER_VERSION,
                "operation_registry": self._registry.manifest(),
            },
            prefix="finance_iterative_agent_verifier_manifest:",
        )

    def verify(
        self,
        context: TrajectoryVerificationContext,
        shared_corpus: EvidenceCorpus,
        environment: AgentToolEnvironmentManifest,
        result: IterativeAgentSolveResult,
    ) -> FinanceIterativeAgentVerificationReport:
        task = context.task
        trajectory = result.trajectory
        audit = result.audit
        corpus_by_id = shared_corpus.by_id()
        task_corpus_by_id = context.public_corpus.by_id()
        gold_ids = tuple(task.oracle.gold_evidence_ids)
        gold_set = set(gold_ids)
        task_corpus_preserved = all(
            corpus_by_id.get(evidence_id) == item for evidence_id, item in task_corpus_by_id.items()
        )
        observations = result.observations
        retrieved_ids = _observation_evidence(observations, {"search_archive"})
        selected_ids = _observation_evidence(
            observations,
            {"open_document", "query_structured_fact"},
        )
        calculator_ids = _observation_evidence(observations, {"calculator"})
        cited_ids = _answer_citations(result)
        retrieved_set = set(retrieved_ids)
        selected_set = set(selected_ids)
        cited_set = set(cited_ids)
        known_observed_ids = {
            evidence_id for observation in observations for evidence_id in observation.evidence_ids
        }
        selected_known = selected_set <= set(corpus_by_id)
        selected_valid = selected_known and all(
            self._evidence_validator.validate_retrievable(corpus_by_id[item]).passed
            for item in selected_set
        )
        cited_known = cited_set <= set(corpus_by_id)
        cited_valid = cited_known and all(
            self._evidence_validator.validate(corpus_by_id[item]).passed for item in cited_set
        )
        retrieved_known = retrieved_set <= set(corpus_by_id)
        retrieved_valid = retrieved_known and all(
            self._evidence_validator.validate_retrievable(corpus_by_id[item]).passed
            for item in retrieved_set
        )
        citation_recall = _set_recall(cited_set, gold_set)
        citation_precision = _set_precision(cited_set, gold_set)
        selection_recall = _set_recall(selected_set, gold_set)
        selection_precision = _set_precision(selected_set, gold_set)
        provenance_ready = [
            bool(corpus_by_id.get(evidence_id) and _provenance_complete(corpus_by_id[evidence_id]))
            for evidence_id in known_observed_ids
        ]
        provenance_completeness = (
            sum(provenance_ready) / len(provenance_ready) if provenance_ready else 0.0
        )

        replay_failures = _replay_observations(
            shared_corpus,
            environment,
            observations,
            recovery_scenario=recovery_scenario_from_metadata(task.public.metadata),
            capability_scenario=capability_mechanism_scenario_from_oracle(
                task.oracle.selection_contract
            ),
            submechanism_scenario=submechanism_scenario_from_oracle(task.oracle.selection_contract),
        )
        leakage_failures = _model_forbidden_field_paths(
            _model_authored_trajectory_payload(trajectory)
        )
        graph_report = self._graph_validator.validate(
            context.proof_graph,
            context.public_corpus.as_bundle(),
            gold_ids,
        )
        try:
            expected = self._oracle.derive_expected(
                task.oracle.task_program,
                task_corpus_by_id,
            )
            normalized_oracle = self._normalizer.normalize_oracle(
                task,
                expected.final_output,
                tuple(task_corpus_by_id[item] for item in gold_ids),
                node_outputs=expected.node_outputs,
            )
            oracle_failures: tuple[str, ...] = ()
        except ProgramExecutionError as exc:
            normalized_oracle = {}
            oracle_failures = (str(exc),)
        normalized_candidate = self._normalizer.normalize_candidate(
            task.public,
            trajectory.final_answer,
        )
        if task.public.metadata.get("answer_projection_contract_version") == "v1":
            projection = task.oracle.selection_contract.get("answer_projection")
            normalized_oracle = _apply_reference_projection(
                normalized_oracle,
                projection,
            )
            normalized_candidate = _apply_reference_projection(
                normalized_candidate,
                projection,
            )
        schema_failures = _direct_answer_schema_failures(
            task.public.answer_schema,
            trajectory.final_answer,
        )
        requirements = set(task.public.requirements)
        successful_tools = tuple(
            observation.call.tool_id
            for observation in observations
            if observation.status == "succeeded"
        )
        required_tool_failures = _required_tool_failures(requirements, successful_tools)
        verification_observations = tuple(
            observation
            for observation in observations
            if observation.call.tool_id == "cross_check_evidence"
            and observation.status == "succeeded"
        )
        successful_verifications = sum(
            observation.result.get("verified") is True for observation in verification_observations
        )
        verification_support = (
            set(verification_observations[-1].evidence_ids) if verification_observations else set()
        )
        failed_positions = [
            index
            for index, observation in enumerate(observations)
            if observation.status == "failed"
        ]
        recovered = all(
            any(later.status == "succeeded" for later in observations[index + 1 :])
            for index in failed_positions
        )
        tool_steps = tuple(step for step in trajectory.steps if step.tool_name is not None)
        last_tool_is_verified = bool(
            tool_steps
            and tool_steps[-1].tool_name == "cross_check_evidence"
            and tool_steps[-1].status == StepStatus.SUCCEEDED
            and verification_observations
            and verification_observations[-1].result.get("verified") is True
        )
        used_tools = {observation.call.tool_id for observation in observations}
        environment_tools = set(environment.tools_by_id)
        operation_lineage_complete = gold_set <= set(calculator_ids)

        checks = (
            _check("task_identity", trajectory.task_id == task.task_id),
            _check("omega_public_corpus_preserved", task_corpus_preserved),
            _check("candidate_workflow_kind", trajectory.workflow_kind == WorkflowKind.CANDIDATE),
            _check(
                "public_only_generation",
                not leakage_failures,
                leakage_failures,
            ),
            _check(
                "environment_identity",
                audit.environment_manifest_id == environment.manifest_id
                and all(
                    item.environment_manifest_id == environment.manifest_id for item in observations
                ),
            ),
            _check(
                "allowed_environment_tools",
                used_tools <= environment_tools,
                tuple(sorted(used_tools - environment_tools)),
            ),
            _check(
                "required_agent_tools_succeeded",
                not required_tool_failures,
                required_tool_failures,
            ),
            _check(
                "deterministic_tool_replay",
                not replay_failures,
                replay_failures,
            ),
            _check(
                "failed_tool_calls_recovered",
                recovered,
                tuple(f"unrecovered_observation_index={item}" for item in failed_positions),
            ),
            _check("retrieved_evidence_known", retrieved_known),
            _check("retrieved_evidence_valid", retrieved_valid),
            _check("selected_evidence_known", selected_known),
            _check("selected_evidence_retrievable", selected_valid),
            _check("selected_evidence_covers_gold", selection_recall == 1.0),
            _check("citations_were_selected", cited_set <= selected_set),
            _check("cited_evidence_known", cited_known),
            _check("cited_evidence_valid", cited_valid),
            _check(
                "citation_exact_gold",
                citation_recall == 1.0 and citation_precision == 1.0,
                (
                    f"recall={citation_recall:.6f}",
                    f"precision={citation_precision:.6f}",
                ),
            ),
            _check(
                "evidence_provenance_complete",
                provenance_completeness == 1.0,
                (f"completeness={provenance_completeness:.6f}",),
            ),
            _check(
                "proof_graph_binding",
                context.proof_graph.graph_id == task.oracle.proof_graph_id
                and context.proof_graph.graph_hash == task.oracle.proof_graph_hash
                and graph_report.passed,
            ),
            _check(
                "operation_lineage_covers_gold",
                operation_lineage_complete,
                tuple(sorted(gold_set - set(calculator_ids))),
            ),
            _check(
                "verification_support_covers_gold",
                gold_set <= verification_support,
                tuple(sorted(gold_set - verification_support)),
            ),
            _check("verification_succeeded", successful_verifications >= 1),
            _check("stop_after_successful_verification", last_tool_is_verified),
            _check("oracle_program_replay", not oracle_failures, oracle_failures),
            _check("answer_schema_valid", not schema_failures, schema_failures),
            _check(
                "answer_correct",
                not oracle_failures
                and self._normalizer.equivalent(
                    normalized_candidate,
                    normalized_oracle,
                ),
            ),
        )
        values = {
            "task_id": task.task_id,
            "omega_context_id": context.context_id,
            "trajectory_id": trajectory.trajectory_id,
            "audit_id": audit.audit_id,
            "environment_manifest_id": environment.manifest_id,
            "checks": checks,
            "retrieved_evidence_ids": retrieved_ids,
            "selected_evidence_ids": selected_ids,
            "cited_evidence_ids": cited_ids,
            "gold_evidence_ids": gold_ids,
            "citation_recall": citation_recall,
            "citation_precision": citation_precision,
            "selection_recall": selection_recall,
            "selection_precision": selection_precision,
            "normalized_candidate_answer": normalized_candidate,
            "normalized_oracle_answer": normalized_oracle,
            "replayed_tool_call_count": len(observations),
            "successful_verification_count": successful_verifications,
            "evidence_provenance_completeness": provenance_completeness,
            "schema_version": FINANCE_ITERATIVE_AGENT_VERIFIER_VERSION,
        }
        provisional = FinanceIterativeAgentVerificationReport.model_construct(
            report_id="pending",
            **values,
        )
        return FinanceIterativeAgentVerificationReport(
            report_id=finance_iterative_agent_verification_report_id(provisional),
            **values,
        )


def finance_iterative_agent_verification_report_id(
    value: FinanceIterativeAgentVerificationReport,
) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"report_id"}),
        prefix="finance_iterative_agent_verification_report:",
    )


def _check(
    check_id: str,
    passed: bool,
    details: tuple[str, ...] = (),
) -> CandidateCheck:
    return CandidateCheck(check_id=check_id, passed=passed, details=details)


def _observation_evidence(
    observations: tuple[AgentToolObservation, ...],
    tool_ids: set[str],
) -> tuple[str, ...]:
    return tuple(
        dict.fromkeys(
            evidence_id
            for observation in observations
            if observation.call.tool_id in tool_ids and observation.status == "succeeded"
            for evidence_id in observation.evidence_ids
        )
    )


def _answer_citations(result: IterativeAgentSolveResult) -> tuple[str, ...]:
    answer_steps = tuple(
        step
        for step in result.trajectory.steps
        if step.action == ActionType.ANSWER and step.status == StepStatus.SUCCEEDED
    )
    if len(answer_steps) != 1:
        return ()
    return tuple(answer_steps[0].evidence_ids)


def _set_recall(observed: set[str], expected: set[str]) -> float:
    return len(observed & expected) / len(expected) if expected else 1.0


def _set_precision(observed: set[str], expected: set[str]) -> float:
    return len(observed & expected) / len(observed) if observed else 0.0


def _replay_observations(
    corpus: EvidenceCorpus,
    environment: AgentToolEnvironmentManifest,
    observations: tuple[AgentToolObservation, ...],
    *,
    recovery_scenario: FinanceTypedRecoveryScenario | None = None,
    capability_scenario: FinanceCapabilityMechanismScenario | None = None,
    submechanism_scenario: FinanceSubmechanismScenario | None = None,
) -> tuple[str, ...]:
    runtime = (
        FinanceCapabilitySubmechanismRuntime(
            corpus,
            environment,
            scenario=submechanism_scenario,
        )
        if submechanism_scenario is not None
        else FinanceArchiveInteractiveToolRuntime(
            corpus,
            environment,
            recovery_scenario=recovery_scenario,
            capability_scenario=capability_scenario,
        )
    )
    failures: list[str] = []
    for index, observation in enumerate(observations):
        spec = environment.tools_by_id.get(observation.call.tool_id)
        if spec is None:
            failures.append(f"observation:{index}:unknown_tool")
            continue
        replayed = agent_tool_argument_rejection(spec, observation.call) or runtime.execute(
            observation.call
        )
        if _result_payload(replayed) != _observation_payload(observation):
            failures.append(f"observation:{index}:replay_mismatch")
    return tuple(failures)


def _apply_reference_projection(
    answer: dict[str, Any],
    projection: Any,
) -> dict[str, Any]:
    if not isinstance(projection, dict) or not projection:
        return answer
    output = dict(answer)
    for field in ("higher_ref", "selected_ref"):
        value = output.get(field)
        if value is not None and str(value) in projection:
            output[field] = projection[str(value)]
    return output


def _result_payload(result: AgentToolResult) -> dict[str, Any]:
    return {
        "status": result.status,
        "result": result.result,
        "evidence_ids": result.evidence_ids,
        "provenance_hashes": result.provenance_hashes,
        "error_code": result.error_code,
        "error_message": result.error_message,
    }


def _observation_payload(observation: AgentToolObservation) -> dict[str, Any]:
    return {
        "status": observation.status,
        "result": observation.result,
        "evidence_ids": observation.evidence_ids,
        "provenance_hashes": observation.provenance_hashes,
        "error_code": observation.error_code,
        "error_message": observation.error_message,
    }


def _direct_answer_schema_failures(
    answer_schema: dict[str, Any],
    answer: dict[str, Any],
) -> tuple[str, ...]:
    failures: list[str] = []
    unknown_top_level = set(answer) - {"result", "citations"}
    result = answer.get("result")
    if unknown_top_level:
        failures.append(f"unknown_top_level:{','.join(sorted(unknown_top_level))}")
    if not isinstance(result, dict):
        failures.append("result_missing_or_not_object")
        return tuple(failures)
    missing = set(required_answer_fields(answer_schema)) - set(result)
    unknown = set(result) - allowed_result_fields(answer_schema)
    if missing:
        failures.append(f"missing_fields:{','.join(sorted(missing))}")
    if unknown:
        failures.append(f"unknown_fields:{','.join(sorted(unknown))}")
    return tuple(failures)


def _provenance_complete(item: Any) -> bool:
    return bool(
        item.evidence_version_id
        and item.provenance.adapter_id
        and item.provenance.archive_id
        and item.provenance.source_record_id
        and item.source_locator.locator_hash
    )


def _model_forbidden_field_paths(value: Any, *, path: str = "trajectory") -> tuple[str, ...]:
    failures: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            current = f"{path}.{key}"
            if str(key).casefold() in MODEL_FORBIDDEN_FIELD_NAMES:
                failures.append(current)
            failures.extend(_model_forbidden_field_paths(item, path=current))
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            failures.extend(_model_forbidden_field_paths(item, path=f"{path}[{index}]"))
    return tuple(failures)


def _model_authored_trajectory_payload(trajectory: Any) -> dict[str, Any]:
    """Exclude Host-owned tool observations from the model-generation leakage gate."""

    steps = []
    for step in trajectory.steps:
        payload = step.model_dump(mode="json", exclude_none=True)
        if step.action != ActionType.PLAN:
            payload.pop("observation", None)
        steps.append(payload)
    return {
        "steps": steps,
        "final_answer": trajectory.final_answer,
    }


def _required_tool_failures(
    requirements: set[TaskRequirement],
    successful_tools: tuple[str, ...],
) -> tuple[str, ...]:
    tools = set(successful_tools)
    required = {
        TaskRequirement.RETRIEVE_EVIDENCE: {
            "search_archive",
            "open_document",
            "query_structured_fact",
        },
        TaskRequirement.SELECT_EVIDENCE: {"open_document", "query_structured_fact"},
        TaskRequirement.CALCULATE: {"calculator"},
        TaskRequirement.VERIFY_RESULT: {"cross_check_evidence"},
    }
    failures = [
        f"{requirement.value}:{','.join(sorted(tool_ids))}"
        for requirement, tool_ids in required.items()
        if requirement in requirements and not (tools & tool_ids)
    ]
    return tuple(failures)
