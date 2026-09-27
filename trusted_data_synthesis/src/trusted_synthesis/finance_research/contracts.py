"""Small public/private, provider, and episode contracts for the new research path."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, model_validator

Role = Literal["sft", "feedback", "development", "test", "calibration", "reserve"]
Tier = Literal["EVAL_NATIVE", "VTDO_FEEDBACK"]


def digest(value: Any) -> str:
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json")
    return hashlib.sha256(
        json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
    ).hexdigest()


class Record(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class PublicSource(Record):
    source_id: str
    kind: Literal["text", "table"]
    content: str | list[list[str]]
    locator: str


class PublicTask(Record):
    dataset: str
    task_id: str
    question: str
    sources: tuple[PublicSource, ...]
    version: str
    answer_contract: dict[str, Any] = Field(default_factory=dict)


class PrivateReference(Record):
    dataset: str
    task_id: str
    answer: Any
    scale: str = ""
    program: str | list[Any] | None = None
    annotations: dict[str, Any] = Field(default_factory=dict)


class Lineage(Record):
    dataset: str
    original_split: str
    original_id: str
    parent_ids: tuple[str, ...] = ()
    source_group: str
    source_group_level: Literal["report", "context", "question", "unknown"]
    company: str | None = None
    report: str | None = None
    year: str | None = None
    context_fingerprint: str
    question_fingerprint: str
    raw_sha256: str
    revision: str
    strata: dict[str, Any] = Field(default_factory=dict)


class TaskBundle(Record):
    public: PublicTask
    reference: PrivateReference
    lineage: Lineage

    @model_validator(mode="after")
    def bound_identity(self):
        if (self.public.dataset, self.public.task_id) != (
            self.reference.dataset,
            self.reference.task_id,
        ) or self.public.dataset != self.lineage.dataset:
            raise ValueError("public/reference/lineage identity mismatch")
        return self


class RunConfig(Record):
    harness_id: str = "bigfinance-derived-vtdo-v1"
    max_steps: int = Field(default=32, ge=1, le=256)
    max_new_tokens: int = Field(default=2048, ge=1)
    context_limit: int = Field(default=24576, ge=1)
    temperature: float = Field(default=1.0, ge=0)
    top_p: float = Field(default=1.0, gt=0, le=1)
    top_k: int = Field(default=0, ge=0)
    seed: int = 20260928
    tier: Tier = "EVAL_NATIVE"
    role: Role = "test"
    api_model: Literal["deepseek-flash"] = "deepseek-flash"

    @model_validator(mode="after")
    def reserve_output(self):
        if self.max_new_tokens >= self.context_limit:
            raise ValueError("context_limit must include prompt and output reservation")
        return self


class ModelIdentity(Record):
    backend: Literal["local_torch", "deepseek_api", "scripted"]
    model_id: str
    parameter_digest: str | None = None
    point_id: str | None = None
    tokenizer_digest: str | None = None
    chat_template_digest: str | None = None


class TokenReceipt(Record):
    call_id: str
    identity: ModelIdentity
    request_sha256: str
    prompt_input_ids: tuple[int, ...]
    raw_generated_token_ids: tuple[int, ...]
    sampled_token_logprobs: tuple[float, ...] | None
    actual_eos: bool
    finish_reason: str
    rng_before_sha256: str
    rng_after_sha256: str
    sampling: dict[str, Any]
    raw_response_sha256: str


class ToolCall(Record):
    call_id: str
    name: str
    raw_arguments: str
    arguments: dict[str, Any]


class ModelTurn(Record):
    raw_text: str
    tool_calls: tuple[ToolCall, ...] = ()
    finish_reason: str = "stop"
    receipt: TokenReceipt | None = None
    usage: dict[str, int] = Field(default_factory=dict)
    provider_metadata: dict[str, Any] = Field(default_factory=dict)


class ToolEvent(Record):
    call_id: str
    name: str
    raw_arguments: str
    normalized_arguments: dict[str, Any]
    executed_arguments: dict[str, Any]
    raw_output: Any
    visible_output: str
    is_error: bool = False


class Episode(Record):
    task_id: str
    dataset: str
    public_task_sha256: str
    config: RunConfig
    provider: ModelIdentity
    turns: tuple[ModelTurn, ...]
    tool_events: tuple[ToolEvent, ...]
    messages: tuple[dict[str, Any], ...]
    final_answer: Any = None
    final_scale: str = ""
    final_program: str | list[Any] | None = None
    stop_reason: str
    error: str | None = None
    actual_model_calls: int | None
    provider_attempts: int = 0
    elapsed_seconds: float
    # Native accuracy is assigned offline; it is never a model-visible observation.


class ModelProvider(Protocol):
    identity: ModelIdentity

    async def chat(
        self, messages: list[dict[str, Any]], tools: list[dict[str, Any]], config: RunConfig
    ) -> ModelTurn: ...


class ContextLimitError(RuntimeError):
    """No history compaction, truncation, or hidden retry is permitted."""
