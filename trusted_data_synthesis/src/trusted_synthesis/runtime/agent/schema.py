from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.core.trajectory.schema import Trajectory
from trusted_synthesis.hashing import canonical_hash

AGENT_RESPONSE_SCHEMA_VERSION = "agent_response.v3"
AGENT_EXECUTION_TRACE_VERSION = "agent_execution_trace.v1"
AGENT_SEARCH_SCHEMA_VERSION = "agent_search.v1"
AGENT_GENERATION_SCHEMA_VERSION = "agent_generation_audit.v2"


class AgentModelConfig(BaseModel):
    """Serializable model routing policy. Credentials are environment-only."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    provider: str = Field(min_length=1)
    endpoint: str = Field(min_length=1)
    models_endpoint: str | None = None
    model: str = Field(min_length=1)
    fallback_models: tuple[str, ...] = ()
    api_key_env: str = Field(min_length=1)
    timeout_seconds: float = Field(default=60, gt=0)
    max_output_tokens: int = Field(default=4096, ge=1)
    temperature: float = Field(default=0, ge=0, le=2)
    maximum_model_attempts: int = Field(default=2, ge=1)
    contract_repair_attempts: int = Field(default=1, ge=0, le=3)
    auto_discover_models: bool = True
    require_requested_model: bool = True
    preferred_model_patterns: tuple[str, ...] = ()
    input_cost_per_million: float = Field(default=0, ge=0)
    output_cost_per_million: float = Field(default=0, ge=0)
    extra_headers: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_credential_boundary(self) -> AgentModelConfig:
        forbidden = {
            "authorization",
            "proxy-authorization",
            "x-api-key",
            "api-key",
        }
        observed = {key.casefold() for key in self.extra_headers}
        if observed & forbidden:
            raise ValueError("model credentials must be supplied only through api_key_env")
        return self

    @property
    def public_manifest_hash(self) -> str:
        return canonical_hash(self, prefix="agent_model_config:")


class ModelCallTelemetry(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    provider: str
    endpoint_host: str
    model_requested: str
    model_selected: str | None = None
    response_model: str | None = None
    request_hash: str
    response_hash: str | None = None
    http_status: int | None = None
    http_success: bool = False
    json_contract_success: bool = False
    prompt_tokens: int | None = Field(default=None, ge=0)
    completion_tokens: int | None = Field(default=None, ge=0)
    total_tokens: int | None = Field(default=None, ge=0)
    estimated_cost: float | None = Field(default=None, ge=0)
    latency_ms: float | None = Field(default=None, ge=0)
    fallback_used: bool = False
    discovery_attempted: bool = False
    discovered_model_count: int = Field(default=0, ge=0)
    error_type: str | None = None
    error_message: str | None = None
    contract_errors: tuple[str, ...] = ()
    response_shape: dict[str, Any] = Field(default_factory=dict)


class AgentExecutionStep(BaseModel):
    """One concrete tool or operation execution, not a copy of a plan node."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    execution_id: str = Field(min_length=1)
    planned_node_id: str | None = None
    operator_id: str = Field(min_length=1)
    tool_name: str | None = None
    input_refs: tuple[str, ...] = Field(min_length=1)
    parameters: dict[str, Any] = Field(default_factory=dict)
    evidence_ids: tuple[str, ...] = ()
    observation: dict[str, Any]
    status: Literal["succeeded", "failed"]
    rationale_summary: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_observation(self) -> AgentExecutionStep:
        if "result" not in self.observation or not isinstance(self.observation["result"], dict):
            raise ValueError("execution observation must contain a structured result")
        return self


class AgentExecutionTrace(BaseModel):
    """Concrete executions bound to evidence and earlier execution outputs."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    trace_version: Literal["agent_execution_trace.v1"] = "agent_execution_trace.v1"
    steps: tuple[AgentExecutionStep, ...] = Field(min_length=1)
    output_execution_id: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_execution_graph(self) -> AgentExecutionTrace:
        execution_ids = [item.execution_id for item in self.steps]
        if len(execution_ids) != len(set(execution_ids)):
            raise ValueError("agent execution trace contains duplicate execution IDs")
        known_executions: set[str] = set()
        for step in self.steps:
            for ref in step.input_refs:
                if ref.startswith("execution:"):
                    execution_id = ref.removeprefix("execution:").split("#", 1)[0]
                    if execution_id not in known_executions:
                        raise ValueError("agent execution refs must be topologically ordered")
                elif not ref.startswith("evidence:"):
                    raise ValueError(f"unsupported agent execution input ref: {ref}")
            known_executions.add(step.execution_id)
        if self.output_execution_id not in known_executions:
            raise ValueError("execution trace output does not reference an executed step")
        return self


class AgentSearchQuery(BaseModel):
    """Public search language. Gold evidence IDs are intentionally not representable."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    subject_ids: tuple[str, ...] = ()
    predicates: tuple[str, ...] = ()
    temporal_labels: tuple[str, ...] = ()
    aliases: tuple[str, ...] = ()
    source_authorities: tuple[str, ...] = ()
    semantic_constraints: dict[str, Any] = Field(default_factory=dict)
    partial_constraints: dict[str, Any] = Field(default_factory=dict)


class AgentSearchResponseContract(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["agent_search.v1"] = "agent_search.v1"
    plan_summary: str = Field(min_length=1)
    search_query: AgentSearchQuery


class AgentCitation(BaseModel):
    """A citation copied from one retrieved evidence item."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    evidence_id: str = Field(min_length=1)
    source_id: str = Field(min_length=1)
    source_locator: dict[str, Any]


class AgentFinalAnswer(BaseModel):
    """Universal answer envelope; task schemas constrain the result payload."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    result: dict[str, Any]
    citations: tuple[AgentCitation, ...]
    status: Any | None = None
    claims: tuple[dict[str, Any], ...] | None = None


class AgentResponseContract(BaseModel):
    """The model's decisions; normalization must not repair their semantics."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["agent_response.v3"] = "agent_response.v3"
    plan_summary: str = Field(min_length=1)
    selected_evidence_ids: tuple[str, ...] = Field(min_length=1)
    execution_trace: AgentExecutionTrace
    verification_result: dict[str, Any] | None = None
    final_answer: AgentFinalAnswer


class AgentGenerationAudit(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    audit_id: str
    task_id: str
    trajectory_id: str
    retrieval_track: str
    planning_track: str
    model_config_hash: str
    prompt_manifest_hash: str
    search_prompt_manifest_hash: str | None = None
    answer_prompt_manifest_hash: str
    executed_search_query_hash: str
    model_search_used: bool = False
    response_contract_hash: str
    telemetry: tuple[ModelCallTelemetry, ...]
    selected_model: str | None = None
    contract_repair_count: int = Field(default=0, ge=0)
    schema_version: str = AGENT_GENERATION_SCHEMA_VERSION


class AgentSolveResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    trajectory: Trajectory
    audit: AgentGenerationAudit
