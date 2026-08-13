from __future__ import annotations

from typing import Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.core.evidence.corpus import EvidenceCorpus
from trusted_synthesis.core.evidence.schema import EvidenceBundle, EvidenceItem
from trusted_synthesis.core.trajectory.schema import ActionType
from trusted_synthesis.hashing import canonical_hash

AGENT_TOOL_ENVIRONMENT_VERSION = "agent_tool_environment.v1"
AGENT_TOOL_OBSERVATION_VERSION = "agent_tool_observation.v1"
ARGUMENT_PATCH_REQUIRED_POLICY = "argument_patch_required"
PREREQUISITE_ACTION_REQUIRED_POLICY = "prerequisite_action_required"

ToolSemanticRole = Literal[
    "acquire",
    "inspect",
    "query",
    "calculate",
    "normalize",
    "verify",
]
ToolExecutionStatus = Literal["succeeded", "failed"]


class AgentToolSpec(BaseModel):
    """One model-visible tool contract; execution remains Host-owned."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    tool_id: str = Field(min_length=1)
    tool_version: str = Field(min_length=1)
    semantic_role: ToolSemanticRole
    trajectory_action: ActionType
    description: str = Field(min_length=1)
    input_contract: dict[str, Any] = Field(min_length=1)
    output_contract: dict[str, Any] = Field(min_length=1)
    required_input_fields: tuple[str, ...] = Field(min_length=1)
    required_output_fields: tuple[str, ...] = Field(min_length=1)
    allow_additional_input_fields: bool = False
    allow_additional_output_fields: bool = False
    model_selectable: bool = True
    host_executes: Literal[True] = True
    content_addressed_observation: Literal[True] = True

    @model_validator(mode="after")
    def validate_io_contract(self) -> AgentToolSpec:
        if not set(self.required_input_fields) <= set(self.input_contract):
            raise ValueError("Agent tool required inputs are absent from its input contract")
        if not set(self.required_output_fields) <= set(self.output_contract):
            raise ValueError("Agent tool required outputs are absent from its output contract")
        if len(self.required_input_fields) != len(set(self.required_input_fields)):
            raise ValueError("Agent tool required inputs are duplicated")
        if len(self.required_output_fields) != len(set(self.required_output_fields)):
            raise ValueError("Agent tool required outputs are duplicated")
        return self

    def validate_arguments(self, arguments: dict[str, Any]) -> None:
        missing = set(self.required_input_fields) - set(arguments)
        unknown = set(arguments) - set(self.input_contract)
        if missing:
            raise ValueError(f"Agent tool call lacks required fields: {sorted(missing)}")
        if unknown and not self.allow_additional_input_fields:
            raise ValueError(f"Agent tool call contains unknown fields: {sorted(unknown)}")

    def validate_output(self, result: dict[str, Any]) -> None:
        missing = set(self.required_output_fields) - set(result)
        unknown = set(result) - set(self.output_contract)
        if missing:
            raise ValueError(f"Agent tool result lacks required fields: {sorted(missing)}")
        if unknown and not self.allow_additional_output_fields:
            raise ValueError(f"Agent tool result contains unknown fields: {sorted(unknown)}")

    @property
    def spec_hash(self) -> str:
        return canonical_hash(self, prefix="agent_tool_spec:")


class AgentToolEnvironmentManifest(BaseModel):
    """Immutable public boundary shared by scripted and autonomous Agent arms."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    manifest_id: str = Field(min_length=1)
    environment_id: str = Field(min_length=1)
    corpus_id: str = Field(min_length=1)
    corpus_hash: str = Field(min_length=1)
    snapshot_id: str = Field(min_length=1)
    snapshot_hash: str = Field(min_length=1)
    network_policy: Literal["forbidden", "snapshot_on_first_use"]
    tools: tuple[AgentToolSpec, ...] = Field(min_length=1)
    maximum_tool_calls: int = Field(ge=1)
    maximum_failed_tool_calls: int = Field(ge=0)
    maximum_total_observation_bytes: int = Field(ge=1)
    tool_timeout_seconds: float = Field(gt=0)
    schema_version: str = AGENT_TOOL_ENVIRONMENT_VERSION

    @model_validator(mode="after")
    def validate_manifest(self) -> AgentToolEnvironmentManifest:
        tool_ids = [item.tool_id for item in self.tools]
        if len(tool_ids) != len(set(tool_ids)):
            raise ValueError("Agent tool environment contains duplicate tool IDs")
        if not any(item.model_selectable for item in self.tools):
            raise ValueError("Agent tool environment exposes no model-selectable tool")
        if self.maximum_failed_tool_calls > self.maximum_tool_calls:
            raise ValueError("failed-tool budget cannot exceed total tool-call budget")
        if self.manifest_id != agent_tool_environment_manifest_id(self):
            raise ValueError("Agent tool environment manifest identity is invalid")
        return self

    @property
    def tools_by_id(self) -> dict[str, AgentToolSpec]:
        return {item.tool_id: item for item in self.tools}


class AgentToolCall(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    call_index: int = Field(ge=1)
    tool_id: str = Field(min_length=1)
    arguments: dict[str, Any]


class AgentToolResult(BaseModel):
    """Raw executor result before the Host assigns an immutable observation identity."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    status: ToolExecutionStatus
    result: dict[str, Any]
    evidence_ids: tuple[str, ...] = ()
    provenance_hashes: tuple[str, ...] = ()
    error_code: str | None = None
    error_message: str | None = None

    @model_validator(mode="after")
    def validate_result(self) -> AgentToolResult:
        if len(self.evidence_ids) != len(set(self.evidence_ids)):
            raise ValueError("Agent tool result contains duplicate Evidence IDs")
        if len(self.provenance_hashes) != len(set(self.provenance_hashes)):
            raise ValueError("Agent tool result contains duplicate provenance hashes")
        if self.status == "succeeded" and (self.error_code or self.error_message):
            raise ValueError("successful Agent tool result cannot contain an error")
        if self.status == "failed" and not self.error_code:
            raise ValueError("failed Agent tool result requires an error code")
        return self


def agent_tool_argument_rejection(
    spec: AgentToolSpec,
    call: AgentToolCall,
) -> AgentToolResult | None:
    """Turn model-owned argument contract errors into replayable failed observations."""

    if call.tool_id != spec.tool_id:
        raise ValueError("Agent tool call and ToolSpec identities differ")
    try:
        spec.validate_arguments(call.arguments)
    except ValueError as exc:
        return AgentToolResult(
            status="failed",
            result={},
            error_code="agent_tool_argument_contract",
            error_message=str(exc) or type(exc).__name__,
        )
    return None


class AgentToolObservation(BaseModel):
    """Content-addressed, replayable observation created by the Host."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    observation_id: str = Field(min_length=1)
    environment_manifest_id: str = Field(min_length=1)
    call: AgentToolCall
    status: ToolExecutionStatus
    result: dict[str, Any]
    evidence_ids: tuple[str, ...] = ()
    provenance_hashes: tuple[str, ...] = ()
    content_hash: str = Field(min_length=1)
    observation_time_hash: str = Field(min_length=1)
    error_code: str | None = None
    error_message: str | None = None
    schema_version: str = AGENT_TOOL_OBSERVATION_VERSION

    @model_validator(mode="after")
    def validate_observation(self) -> AgentToolObservation:
        if self.status == "succeeded" and (self.error_code or self.error_message):
            raise ValueError("successful Agent tool observation cannot contain an error")
        if self.status == "failed" and not self.error_code:
            raise ValueError("failed Agent tool observation requires an error code")
        expected_content_hash = canonical_hash(
            {
                "status": self.status,
                "result": self.result,
                "evidence_ids": self.evidence_ids,
                "provenance_hashes": self.provenance_hashes,
                "error_code": self.error_code,
                "error_message": self.error_message,
            },
            prefix="agent_tool_content:",
        )
        if self.content_hash != expected_content_hash:
            raise ValueError("Agent tool observation content hash is invalid")
        if self.observation_id != agent_tool_observation_id(self):
            raise ValueError("Agent tool observation identity is invalid")
        return self


class InteractiveAgentToolRuntime(Protocol):
    @property
    def manifest(self) -> AgentToolEnvironmentManifest: ...

    def execute(self, call: AgentToolCall) -> AgentToolResult: ...


class EvidenceToolRuntime(Protocol):
    def search(self, retrieval_scope: dict[str, object]) -> tuple[EvidenceItem, ...]: ...


class InMemoryEvidenceToolRuntime:
    """Test runtime that implements public-scope retrieval without oracle IDs."""

    def __init__(self, corpus: EvidenceCorpus | EvidenceBundle) -> None:
        self._corpus = (
            corpus if isinstance(corpus, EvidenceCorpus) else EvidenceCorpus.from_bundle(corpus)
        )
        self.last_query: dict[str, object] | None = None

    def search(self, retrieval_scope: dict[str, object]) -> tuple[EvidenceItem, ...]:
        self.last_query = retrieval_scope
        subjects = _string_set(retrieval_scope.get("subject_ids"))
        predicates = _string_set(retrieval_scope.get("predicates"))
        temporal_labels = _string_set(retrieval_scope.get("temporal_labels"))
        aliases = _string_set(retrieval_scope.get("aliases"))
        authorities = _string_set(retrieval_scope.get("source_authorities"))
        semantic = _mapping(retrieval_scope.get("semantic_constraints"))
        partial = _mapping(retrieval_scope.get("partial_constraints"))
        definitions = _string_set(semantic.get("definition_ids"))
        scopes = _string_set(semantic.get("scope_ids"))
        semantic_times = _string_set(semantic.get("temporal_labels"))
        semantic_authorities = _string_set(semantic.get("source_authorities"))
        semantic_subject_types = _string_set(semantic.get("subject_types"))
        semantic_time_bases = _string_set(semantic.get("time_bases"))
        semantic_frequencies = _string_set(semantic.get("frequencies"))
        semantic_epistemic_statuses = _string_set(semantic.get("epistemic_statuses"))
        apply_semantic_filters = retrieval_scope.get("apply_semantic_filters") is True
        partial_predicate = _optional_string(partial.get("predicate"))
        partial_definition = _optional_string(partial.get("definition_id"))
        return tuple(
            item
            for item in self._corpus.evidence
            if (not subjects or item.subject.subject_id in subjects)
            and (not predicates or item.predicate in predicates)
            and (not temporal_labels or bool(_time_labels(item) & temporal_labels))
            and (not aliases or item.subject.subject_id in aliases or item.subject.name in aliases)
            and (not authorities or item.source.authority.value in authorities)
            and (
                not apply_semantic_filters
                or not definitions
                or item.definition.definition_id in definitions
            )
            and (
                not apply_semantic_filters
                or not scopes
                or item.scope is not None
                and item.scope.scope_id in scopes
            )
            and (
                not apply_semantic_filters
                or not semantic_times
                or bool(_time_labels(item) & semantic_times)
            )
            and (
                not apply_semantic_filters
                or not semantic_authorities
                or item.source.authority.value in semantic_authorities
            )
            and (
                not apply_semantic_filters
                or not semantic_subject_types
                or item.subject.subject_type in semantic_subject_types
            )
            and (
                not apply_semantic_filters
                or not semantic_time_bases
                or item.temporal_context.basis in semantic_time_bases
            )
            and (
                not apply_semantic_filters
                or not semantic_frequencies
                or item.temporal_context.frequency in semantic_frequencies
            )
            and (
                not apply_semantic_filters
                or not semantic_epistemic_statuses
                or item.epistemic_status.value in semantic_epistemic_statuses
            )
            and (partial_predicate is None or item.predicate == partial_predicate)
            and (partial_definition is None or item.definition.definition_id == partial_definition)
        )


def make_agent_tool_environment_manifest(
    *,
    environment_id: str,
    corpus_id: str,
    corpus_hash: str,
    snapshot_id: str,
    snapshot_hash: str,
    network_policy: Literal["forbidden", "snapshot_on_first_use"],
    tools: tuple[AgentToolSpec, ...],
    maximum_tool_calls: int,
    maximum_failed_tool_calls: int,
    maximum_total_observation_bytes: int,
    tool_timeout_seconds: float,
) -> AgentToolEnvironmentManifest:
    values = {
        "environment_id": environment_id,
        "corpus_id": corpus_id,
        "corpus_hash": corpus_hash,
        "snapshot_id": snapshot_id,
        "snapshot_hash": snapshot_hash,
        "network_policy": network_policy,
        "tools": tools,
        "maximum_tool_calls": maximum_tool_calls,
        "maximum_failed_tool_calls": maximum_failed_tool_calls,
        "maximum_total_observation_bytes": maximum_total_observation_bytes,
        "tool_timeout_seconds": tool_timeout_seconds,
        "schema_version": AGENT_TOOL_ENVIRONMENT_VERSION,
    }
    provisional = AgentToolEnvironmentManifest.model_construct(
        manifest_id="pending",
        **values,
    )
    return AgentToolEnvironmentManifest(
        manifest_id=agent_tool_environment_manifest_id(provisional),
        **values,
    )


def make_agent_tool_observation(
    *,
    environment_manifest_id: str,
    call: AgentToolCall,
    result: AgentToolResult,
    observation_time_hash: str,
) -> AgentToolObservation:
    content_hash = canonical_hash(
        {
            "status": result.status,
            "result": result.result,
            "evidence_ids": result.evidence_ids,
            "provenance_hashes": result.provenance_hashes,
            "error_code": result.error_code,
            "error_message": result.error_message,
        },
        prefix="agent_tool_content:",
    )
    values = {
        "environment_manifest_id": environment_manifest_id,
        "call": call,
        "status": result.status,
        "result": result.result,
        "evidence_ids": result.evidence_ids,
        "provenance_hashes": result.provenance_hashes,
        "content_hash": content_hash,
        "observation_time_hash": observation_time_hash,
        "error_code": result.error_code,
        "error_message": result.error_message,
        "schema_version": AGENT_TOOL_OBSERVATION_VERSION,
    }
    provisional = AgentToolObservation.model_construct(
        observation_id="pending",
        **values,
    )
    return AgentToolObservation(
        observation_id=agent_tool_observation_id(provisional),
        **values,
    )


def agent_tool_environment_manifest_id(value: AgentToolEnvironmentManifest) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"manifest_id"}),
        prefix="agent_tool_environment:",
    )


def agent_tool_observation_id(value: AgentToolObservation) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"observation_id"}),
        prefix="agent_tool_observation:",
    )


def _time_label(item: EvidenceItem) -> str:
    context = item.temporal_context
    if context.label:
        return context.label
    if context.valid_to:
        return context.valid_to.isoformat()
    if context.observed_at:
        return context.observed_at.isoformat()
    return "the stated period"


def _time_labels(item: EvidenceItem) -> set[str]:
    context = item.temporal_context
    labels = {context.label} if context.label else set()
    labels.update(
        value.isoformat()
        for value in (
            context.valid_from,
            context.valid_to,
            context.observed_at,
        )
        if value is not None
    )
    if not labels:
        labels.add("the stated period")
    return labels


def _string_set(value: object | None) -> set[str]:
    if not isinstance(value, (list, tuple, set)):
        return set()
    return {str(item) for item in value}


def _mapping(value: object | None) -> dict[str, object]:
    if not isinstance(value, dict):
        return {}
    return {str(key): item for key, item in value.items()}


def _optional_string(value: object | None) -> str | None:
    return None if value in (None, "") else str(value)
