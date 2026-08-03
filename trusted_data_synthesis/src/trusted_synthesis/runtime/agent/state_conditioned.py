from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.core.evidence.corpus import EvidenceCorpus
from trusted_synthesis.core.task.schema import PlanningTrack, RetrievalTrack, TaskRequirement
from trusted_synthesis.core.trajectory.schema import Trajectory
from trusted_synthesis.core.vtdo.state_space import (
    PublicStateCondition,
    PublicStateGenerationRequest,
)
from trusted_synthesis.hashing import canonical_hash
from trusted_synthesis.runtime.agent.llm_agent import LLMAgentSolver
from trusted_synthesis.runtime.agent.schema import AgentGenerationAudit
from trusted_synthesis.runtime.tools import InMemoryEvidenceToolRuntime

STATE_CONDITIONED_AGENT_PROVIDER_VERSION = "state_conditioned_agent_provider.v1"
STATE_CONTROLLABILITY_AUDIT_VERSION = "state_condition_controllability.v1"

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
    controllability_audit_id: str = Field(min_length=1)
    generation_audit: AgentGenerationAudit
    schema_version: str = STATE_CONDITIONED_AGENT_PROVIDER_VERSION


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
        self._controllability_audits: list[StateConditionControllabilityAudit] = []

    @property
    def records(self) -> tuple[StateConditionedGenerationRecord, ...]:
        return tuple(self._records)

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
        constraints = project_state_condition_constraints(
            request.state_condition,
            audit,
        )
        for candidate_index in range(request.candidate_count):
            result = self._solver.solve_with_audit(
                request.task_public,
                InMemoryEvidenceToolRuntime(corpus),
                generation_constraints=constraints,
            )
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
                    controllability_audit_id=audit.audit_id,
                    generation_audit=result.audit,
                )
            )
            yield result.trajectory


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
        "execution_requirement": (
            "host_satisfied"
            if plan_given and condition.execution_requirement == "program_equivalent"
            else "host_blocked"
            if plan_given
            else "model_controlled"
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
        "binding_rule": (
            "Honor only model-controlled or shared-control dimensions. Host-satisfied "
            "dimensions are immutable guarantees. Never simulate a host-blocked dimension."
        ),
    }


def state_condition_controllability_audit_id(
    value: StateConditionControllabilityAudit,
) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"audit_id"}),
        prefix="state_condition_controllability_audit:",
    )
