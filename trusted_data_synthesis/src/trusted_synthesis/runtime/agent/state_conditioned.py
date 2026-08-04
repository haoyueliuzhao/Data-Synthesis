from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.core.evidence.corpus import EvidenceCorpus
from trusted_synthesis.core.task.schema import PlanningTrack, RetrievalTrack, TaskRequirement
from trusted_synthesis.core.trajectory.schema import Trajectory
from trusted_synthesis.core.vtdo.state_space import (
    PublicStateCondition,
    PublicStateGenerationRequest,
)
from trusted_synthesis.hashing import canonical_hash
from trusted_synthesis.runtime.agent.client import LLMClientError
from trusted_synthesis.runtime.agent.llm_agent import LLMAgentSolver
from trusted_synthesis.runtime.agent.schema import (
    AgentGenerationAudit,
    HostInteractionProgress,
    ModelCallTelemetry,
)
from trusted_synthesis.runtime.tools import InMemoryEvidenceToolRuntime

STATE_CONDITIONED_AGENT_PROVIDER_VERSION = "state_conditioned_agent_provider.v4"
STATE_CONTROLLABILITY_AUDIT_VERSION = "state_condition_controllability.v3"

ControlStatus = Literal[
    "model_controlled",
    "shared_control",
    "host_satisfied",
    "host_blocked",
]


class StateConditionControllabilityAudit(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    audit_id: str = Field(min_length=1)
    task_id: str = Field(min_length=1)
    condition_id: str = Field(min_length=1)
    interaction_protocol: Literal["full_response", "host_instrumented"]
    dimension_status: dict[str, ControlStatus] = Field(min_length=1)
    blocked_dimensions: tuple[str, ...] = ()
    condition_requestable: bool
    schema_version: str = STATE_CONTROLLABILITY_AUDIT_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> StateConditionControllabilityAudit:
        expected_blocked = tuple(
            sorted(
                dimension
                for dimension, status in self.dimension_status.items()
                if status == "host_blocked"
            )
        )
        if self.blocked_dimensions != expected_blocked:
            raise ValueError("state controllability blocked dimensions are inconsistent")
        if self.condition_requestable != (not expected_blocked):
            raise ValueError("state controllability request status is inconsistent")
        if self.audit_id != state_condition_controllability_audit_id(self):
            raise ValueError("state controllability audit identity is invalid")
        return self


class StateConditionedGenerationRecord(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    request_id: str = Field(min_length=1)
    candidate_index: int = Field(ge=0)
    request_seed: int
    candidate_seed: int
    trajectory_id: str = Field(min_length=1)
    trajectory_hash: str = Field(min_length=1)
    controllability_audit_id: str = Field(min_length=1)
    generation_audit: AgentGenerationAudit
    schema_version: str = STATE_CONDITIONED_AGENT_PROVIDER_VERSION


class StateConditionedGenerationFailureRecord(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    failure_id: str = Field(min_length=1)
    request_id: str = Field(min_length=1)
    candidate_index: int = Field(ge=0)
    request_seed: int
    candidate_seed: int
    controllability_audit_id: str = Field(min_length=1)
    error_type: str = Field(min_length=1)
    error_message: str = Field(min_length=1)
    telemetry: tuple[ModelCallTelemetry, ...] = ()
    failure_artifact: dict[str, Any] | None = None
    interaction_progress: HostInteractionProgress | None = None
    schema_version: str = STATE_CONDITIONED_AGENT_PROVIDER_VERSION

    @model_validator(mode="after")
    def validate_failure(self) -> StateConditionedGenerationFailureRecord:
        if self.failure_id != state_conditioned_generation_failure_record_id(self):
            raise ValueError("state-conditioned generation failure identity is invalid")
        return self


class StateConditionedLLMTrajectoryProvider:
    """Bind public state requests to an LLM without exposing Omega or Oracle fields."""

    provider_version = STATE_CONDITIONED_AGENT_PROVIDER_VERSION

    def __init__(
        self,
        *,
        provider_id: str,
        solver: LLMAgentSolver,
        public_corpora_by_task_id: Mapping[str, EvidenceCorpus],
        reject_protocol_blocked: bool = True,
    ) -> None:
        if not provider_id:
            raise ValueError("state-conditioned provider ID cannot be empty")
        if not public_corpora_by_task_id:
            raise ValueError("state-conditioned provider requires public corpora")
        self.provider_id = provider_id
        self._solver = solver
        self._corpora = dict(public_corpora_by_task_id)
        self._reject_protocol_blocked = reject_protocol_blocked
        self._records: list[StateConditionedGenerationRecord] = []
        self._failure_records: list[StateConditionedGenerationFailureRecord] = []
        self._controllability_audits: list[StateConditionControllabilityAudit] = []

    @property
    def records(self) -> tuple[StateConditionedGenerationRecord, ...]:
        return tuple(self._records)

    @property
    def failure_records(self) -> tuple[StateConditionedGenerationFailureRecord, ...]:
        return tuple(self._failure_records)

    @property
    def controllability_audits(self) -> tuple[StateConditionControllabilityAudit, ...]:
        return tuple(self._controllability_audits)

    def generate(
        self,
        request: PublicStateGenerationRequest,
    ) -> Iterable[Trajectory]:
        corpus = self._corpora.get(request.task_public.task_id)
        if corpus is None:
            raise ValueError("state-conditioned request has no bound public corpus")
        if (
            corpus.corpus_id != request.public_corpus_id
            or corpus.corpus_hash != request.public_corpus_hash
        ):
            raise ValueError("state-conditioned request mutates the public corpus boundary")
        audit = assess_state_condition_controllability(
            request,
            interaction_protocol=self._solver.interaction_protocol,
        )
        self._controllability_audits.append(audit)
        if self._reject_protocol_blocked and not audit.condition_requestable:
            raise ValueError(
                "state condition is not requestable under the current agent contract: "
                + ",".join(audit.blocked_dimensions)
            )
        base_constraints = project_state_condition_constraints(
            request.state_condition,
            audit,
        )
        for candidate_index in range(request.candidate_count):
            candidate_seed = _candidate_generation_seed(request.seed, candidate_index)
            constraints = {
                **base_constraints,
                "sampling_context": {
                    "request_seed": request.seed,
                    "candidate_index": candidate_index,
                    "candidate_seed": candidate_seed,
                },
            }
            try:
                result = self._solver.solve_with_audit(
                    request.task_public,
                    InMemoryEvidenceToolRuntime(corpus),
                    generation_constraints=constraints,
                )
            except LLMClientError as exc:
                failure_artifact = (
                    exc.failure_artifact.model_dump(mode="json")
                    if isinstance(exc.failure_artifact, BaseModel)
                    else dict(exc.failure_artifact)
                    if isinstance(exc.failure_artifact, Mapping)
                    else None
                )
                values = {
                    "request_id": request.request_id,
                    "candidate_index": candidate_index,
                    "request_seed": request.seed,
                    "candidate_seed": candidate_seed,
                    "controllability_audit_id": audit.audit_id,
                    "error_type": type(exc).__name__,
                    "error_message": str(exc),
                    "telemetry": exc.telemetry,
                    "failure_artifact": failure_artifact,
                    "interaction_progress": exc.interaction_progress,
                    "schema_version": STATE_CONDITIONED_AGENT_PROVIDER_VERSION,
                }
                provisional = StateConditionedGenerationFailureRecord.model_construct(
                    failure_id="pending",
                    **values,
                )
                self._failure_records.append(
                    StateConditionedGenerationFailureRecord(
                        failure_id=state_conditioned_generation_failure_record_id(provisional),
                        **values,
                    )
                )
                continue
            expected_hash = canonical_hash(
                constraints,
                prefix="agent_generation_constraints:",
            )
            if result.audit.generation_constraints_hash != expected_hash:
                raise ValueError("LLM generation audit lost the public state condition")
            self._records.append(
                StateConditionedGenerationRecord(
                    request_id=request.request_id,
                    candidate_index=candidate_index,
                    request_seed=request.seed,
                    candidate_seed=candidate_seed,
                    trajectory_id=result.trajectory.trajectory_id,
                    trajectory_hash=result.trajectory.trajectory_hash,
                    controllability_audit_id=audit.audit_id,
                    generation_audit=result.audit,
                )
            )
            yield result.trajectory


def state_conditioned_generation_failure_record_id(
    value: StateConditionedGenerationFailureRecord,
) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"failure_id"}),
        prefix="state_conditioned_generation_failure:",
    )


def assess_state_condition_controllability(
    request: PublicStateGenerationRequest,
    *,
    interaction_protocol: Literal["full_response", "host_instrumented"],
) -> StateConditionControllabilityAudit:
    task = request.task_public
    condition = request.state_condition
    resolved = task.retrieval_track == RetrievalTrack.RESOLVED
    plan_given = task.planning_track == PlanningTrack.PLAN_GIVEN
    verification_required = TaskRequirement.VERIFY_RESULT in task.requirements
    dimension_status: dict[str, ControlStatus] = {
        "acquisition_requirement": (
            "host_satisfied"
            if resolved and condition.acquisition_requirement in {"none", "bounded"}
            else "host_blocked"
            if resolved
            else "model_controlled"
        ),
        "evidence_support_requirement": (
            "host_satisfied"
            if plan_given and condition.evidence_support_requirement == "required_roles"
            else "host_blocked"
            if plan_given
            else "model_controlled"
        ),
        "retrieval_elaboration": (
            "host_satisfied"
            if condition.retrieval_elaboration == "unconstrained"
            else "model_controlled"
            if not resolved
            else "host_satisfied"
            if condition.retrieval_elaboration == "required_only"
            else "host_blocked"
        ),
        "execution_requirement": (
            "host_satisfied"
            if plan_given and condition.execution_requirement == "program_equivalent"
            else "host_blocked"
            if plan_given
            else "model_controlled"
        ),
        "execution_elaboration": (
            "host_satisfied"
            if condition.execution_elaboration == "unconstrained"
            else "model_controlled"
            if not plan_given
            else "host_satisfied"
            if condition.execution_elaboration
            in {"baseline_program", "program_projection"}
            else "host_blocked"
        ),
        "verification_requirement": (
            "host_satisfied"
            if (
                verification_required
                and condition.verification_requirement == "full"
                or not verification_required
                and condition.verification_requirement == "none"
            )
            else "host_blocked"
        ),
        "lineage_requirement": (
            "host_satisfied"
            if plan_given and condition.lineage_requirement in {"direct", "citation_minimum"}
            else "host_blocked"
            if plan_given
            else "shared_control"
        ),
        "minimum_tool_calls": (
            "host_satisfied" if plan_given else "model_controlled"
        ),
        "minimum_evidence_count": (
            "host_satisfied" if plan_given else "model_controlled"
        ),
        "minimum_reasoning_depth": (
            "host_satisfied" if plan_given else "model_controlled"
        ),
        "minimum_verification_degree": (
            "host_satisfied"
            if verification_required and condition.minimum_verification_degree <= 1.0
            else "host_blocked"
            if condition.minimum_verification_degree > 0
            else "host_satisfied"
        ),
    }
    values = {
        "task_id": task.task_id,
        "condition_id": condition.condition_id,
        "interaction_protocol": interaction_protocol,
        "dimension_status": dimension_status,
        "blocked_dimensions": tuple(
            sorted(
                dimension
                for dimension, status in dimension_status.items()
                if status == "host_blocked"
            )
        ),
        "condition_requestable": not any(
            status == "host_blocked" for status in dimension_status.values()
        ),
        "schema_version": STATE_CONTROLLABILITY_AUDIT_VERSION,
    }
    provisional = StateConditionControllabilityAudit.model_construct(
        audit_id="pending",
        **values,
    )
    return StateConditionControllabilityAudit(
        audit_id=state_condition_controllability_audit_id(provisional),
        **values,
    )


def project_state_condition_constraints(
    condition: PublicStateCondition,
    controllability: StateConditionControllabilityAudit,
) -> dict[str, object]:
    if controllability.condition_id != condition.condition_id:
        raise ValueError("controllability audit belongs to another state condition")
    target = condition.model_dump(
        mode="json",
        exclude={
            "condition_id",
            "task_id",
            "forbidden_surface_template",
            "schema_version",
        },
    )
    return {
        "contract_version": STATE_CONDITIONED_AGENT_PROVIDER_VERSION,
        "target_behavior": target,
        "dimension_control": dict(sorted(controllability.dimension_status.items())),
        "control_plan": _state_control_plan(condition, controllability),
        "binding_rule": (
            "Honor only model-controlled or shared-control dimensions. Host-satisfied "
            "dimensions are immutable guarantees. Never simulate a host-blocked dimension."
        ),
    }


def _state_control_plan(
    condition: PublicStateCondition,
    controllability: StateConditionControllabilityAudit,
) -> dict[str, object]:
    retrieval_rules = {
        "unconstrained": "Use any valid public search strategy.",
        "required_only": (
            "Maximize public query specificity using the exact subject, predicate, and time "
            "constraints needed by the task. Do not intentionally retrieve contextual rows."
        ),
        "semantic_context": (
            "Retrieve the required rows plus nearby semantically related context. Keep a "
            "non-empty subject or predicate constraint, but omit exact temporal filters so "
            "the query is broader than required-only and narrower than the whole corpus."
        ),
        "full_corpus": (
            "Return an empty model-owned search query. The Host will add only the immutable "
            "corpus boundary, yielding the complete public corpus."
        ),
    }
    execution_rules = {
        "unconstrained": "Use any independently valid registered operation graph.",
        "baseline_program": (
            "Use the shortest semantically complete registered operation graph for the task. "
            "Do not add lookup operations solely to create optional transparent projections."
        ),
        "program_projection": (
            "Preserve the registered lookup projection nodes that belong to the shortest "
            "semantically complete operation graph, and feed their outputs to the semantic "
            "operation. Do not add another projection layer."
        ),
        "transparent_projection": (
            "Insert a registered lookup projection for each raw Evidence input consumed by a "
            "semantic operation, then feed the lookup step outputs to that operation."
        ),
    }
    return {
        "retrieval": {
            "mode": condition.retrieval_elaboration,
            "control_status": controllability.dimension_status["retrieval_elaboration"],
            "rule": retrieval_rules[condition.retrieval_elaboration],
        },
        "execution": {
            "mode": condition.execution_elaboration,
            "control_status": controllability.dimension_status["execution_elaboration"],
            "rule": execution_rules[condition.execution_elaboration],
        },
    }


def state_condition_controllability_audit_id(
    value: StateConditionControllabilityAudit,
) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"audit_id"}),
        prefix="state_condition_controllability_audit:",
    )


def _candidate_generation_seed(request_seed: int, candidate_index: int) -> int:
    digest = canonical_hash(
        {
            "request_seed": request_seed,
            "candidate_index": candidate_index,
            "provider_version": STATE_CONDITIONED_AGENT_PROVIDER_VERSION,
        },
        prefix="state_conditioned_candidate_seed:",
    ).rsplit(":", 1)[-1]
    return int(digest[:16], 16)
