from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.hashing import canonical_hash
from trusted_synthesis.runtime.agent.client import OpenAICompatibleJsonClient
from trusted_synthesis.runtime.agent.schema import AgentModelConfig

THINKING_MODE_POLICY_VERSION = "prospective_thinking_mode_policy.v1"
THINKING_MODE_BINDING_VERSION = "prospective_thinking_model_binding.v1"
THINKING_REQUEST_BODY_FRAGMENT = {"thinking": {"type": "enabled"}}


class ProspectiveThinkingModePolicy(BaseModel):
    """Future-only provider-call policy; historical replay remains byte preserving."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    policy_id: str = Field(min_length=1)
    effective_date: Literal["2026-08-21"] = "2026-08-21"
    scope: Literal["all_new_provider_model_calls"] = "all_new_provider_model_calls"
    required_request_body_fragment: dict[str, Any] = Field(
        default_factory=lambda: {
            "thinking": {"type": "enabled"},
        }
    )
    configuration_admission: Literal["exact_match_before_client_construction"] = (
        "exact_match_before_client_construction"
    )
    historical_provider_calls_in_scope: Literal[False] = False
    non_provider_fixture_calls_in_scope: Literal[False] = False
    historical_results_reclassified: Literal[False] = False
    reasoning_content_persisted: Literal[False] = False
    reasoning_length_and_token_telemetry_retained: Literal[True] = True
    reasoning_tokens_count_toward_completion_usage: Literal[True] = True
    completion_usage_counts_toward_rollout_budget: Literal[True] = True
    schema_version: str = THINKING_MODE_POLICY_VERSION

    @model_validator(mode="after")
    def validate_policy(self) -> ProspectiveThinkingModePolicy:
        if self.required_request_body_fragment != THINKING_REQUEST_BODY_FRAGMENT:
            raise ValueError("prospective thinking request fragment changed")
        if self.policy_id != prospective_thinking_mode_policy_id(self):
            raise ValueError("prospective thinking policy identity is invalid")
        return self


class ProspectiveThinkingModelBinding(BaseModel):
    """Content-addressed proof that a future model config enables thinking."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    binding_id: str = Field(min_length=1)
    policy_id: str = Field(min_length=1)
    model_config_id: str = Field(min_length=1)
    provider: str = Field(min_length=1)
    model: str = Field(min_length=1)
    thinking_type: Literal["enabled"] = "enabled"
    schema_version: str = THINKING_MODE_BINDING_VERSION

    @model_validator(mode="after")
    def validate_binding(self) -> ProspectiveThinkingModelBinding:
        if self.policy_id != PROSPECTIVE_THINKING_MODE_POLICY.policy_id:
            raise ValueError("prospective thinking binding uses another policy")
        if self.binding_id != prospective_thinking_model_binding_id(self):
            raise ValueError("prospective thinking binding identity is invalid")
        return self


def prospective_thinking_mode_policy_id(value: ProspectiveThinkingModePolicy) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"policy_id"}),
        prefix="prospective_thinking_mode_policy:",
    )


def prospective_thinking_model_binding_id(
    value: ProspectiveThinkingModelBinding,
) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"binding_id"}),
        prefix="prospective_thinking_model_binding:",
    )


def _build_policy() -> ProspectiveThinkingModePolicy:
    values: dict[str, Any] = {}
    provisional = ProspectiveThinkingModePolicy.model_construct(
        policy_id="pending",
        **values,
    )
    return ProspectiveThinkingModePolicy(
        policy_id=prospective_thinking_mode_policy_id(provisional),
        **values,
    )


PROSPECTIVE_THINKING_MODE_POLICY = _build_policy()


def enable_prospective_thinking(config: AgentModelConfig) -> AgentModelConfig:
    """Create a new config identity with the required provider request fragment."""

    overrides = dict(config.request_body_overrides)
    noncanonical_keys = tuple(
        sorted(key for key in overrides if key.casefold() == "thinking" and key != "thinking")
    )
    if noncanonical_keys:
        raise ValueError("thinking request field must use the canonical lowercase spelling")
    overrides["thinking"] = {"type": "enabled"}
    values = config.model_dump(mode="python")
    values["request_body_overrides"] = overrides
    enabled = AgentModelConfig.model_validate(values)
    require_prospective_thinking(enabled)
    return enabled


def require_prospective_thinking(config: AgentModelConfig) -> AgentModelConfig:
    """Fail closed unless the config has the exact prospective thinking setting."""

    thinking_keys = tuple(
        key for key in config.request_body_overrides if key.casefold() == "thinking"
    )
    if thinking_keys != ("thinking",):
        raise ValueError(
            "prospective model calls require exactly one canonical thinking request field"
        )
    if config.request_body_overrides["thinking"] != {"type": "enabled"}:
        raise ValueError("prospective model calls require thinking={'type': 'enabled'}")
    return config


def bind_prospective_thinking(
    config: AgentModelConfig,
) -> ProspectiveThinkingModelBinding:
    require_prospective_thinking(config)
    values = {
        "policy_id": PROSPECTIVE_THINKING_MODE_POLICY.policy_id,
        "model_config_id": config.public_manifest_hash,
        "provider": config.provider,
        "model": config.model,
    }
    provisional = ProspectiveThinkingModelBinding.model_construct(
        binding_id="pending",
        **values,
    )
    return ProspectiveThinkingModelBinding(
        binding_id=prospective_thinking_model_binding_id(provisional),
        **values,
    )


class ThinkingRequiredOpenAICompatibleJsonClient(OpenAICompatibleJsonClient):
    """OpenAI-compatible client admitted only under the future thinking policy."""

    def __init__(self, config: AgentModelConfig) -> None:
        self._thinking_mode_binding = bind_prospective_thinking(config)
        super().__init__(config)

    @property
    def thinking_mode_binding(self) -> ProspectiveThinkingModelBinding:
        return self._thinking_mode_binding
