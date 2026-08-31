from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Literal, Protocol

from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_json_explicit_prompt_contract_preflight as v192,
)
from trusted_synthesis.runtime.agent.prospective_two_stage_stage1_client import (
    make_stage_one_request_body,
)
from trusted_synthesis.runtime.agent.schema import AgentModelConfig

PromptKind = Literal["action", "correction", "final"]


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


@dataclass(frozen=True)
class ZeroCallInvocation:
    prompt_kind: PromptKind
    prompt_core_canonical_json: str
    rendered_prompt: str
    request_body_canonical_json: str
    rendered_before_request_body: bool
    request_body_validated_before_sink: bool
    event_sequence: tuple[Literal["render", "body", "validate", "sink"], ...]

    @property
    def rendered_prompt_sha256(self) -> str:
        return hashlib.sha256(self.rendered_prompt.encode("utf-8")).hexdigest()

    @property
    def request_body_sha256(self) -> str:
        return hashlib.sha256(self.request_body_canonical_json.encode("utf-8")).hexdigest()


class ProviderTransport(Protocol):
    def invoke(self, *, request_body: dict[str, Any], fixture_response: Any) -> Any: ...


class CredentialFreeFixtureTransport:
    def __init__(self) -> None:
        self.sink_invocation_count = 0
        self.provider_calls = 0

    def invoke(self, *, request_body: dict[str, Any], fixture_response: Any) -> Any:
        if request_body.get("response_format") != {"type": "json_object"}:
            raise ValueError("fixture transport received an unvalidated request")
        self.sink_invocation_count += 1
        return fixture_response


class CredentialFreeExactFutureRunner:
    """Exact future invocation seam; the preflight injects a zero-network fixture sink."""

    def __init__(
        self,
        *,
        contract: v192.JsonExplicitPromptContract,
        schema: v192.JsonExplicitPromptSchema,
        config: AgentModelConfig,
        transport: ProviderTransport,
    ) -> None:
        self._contract = contract
        self._schema = schema
        self._config = config
        self._transport = transport
        self._invocations: list[ZeroCallInvocation] = []

    @property
    def invocations(self) -> tuple[ZeroCallInvocation, ...]:
        return tuple(self._invocations)

    def invoke_action(self, *, core: dict[str, Any], fixture_response: Any) -> Any:
        return self._invoke(prompt_kind="action", core=core, fixture_response=fixture_response)

    def invoke_correction(self, *, core: dict[str, Any], fixture_response: Any) -> Any:
        return self._invoke(prompt_kind="correction", core=core, fixture_response=fixture_response)

    def invoke_final(self, *, core: str, fixture_response: Any) -> Any:
        return self._invoke(prompt_kind="final", core=core, fixture_response=fixture_response)

    def _invoke(
        self,
        *,
        prompt_kind: PromptKind,
        core: dict[str, Any] | str,
        fixture_response: Any,
    ) -> Any:
        events: list[Literal["render", "body", "validate", "sink"]] = []
        rendered_prompt = v192._render_prompt(  # noqa: SLF001
            prompt_kind=prompt_kind,
            core=core,
            contract=self._contract,
            schema=self._schema,
        )
        events.append("render")
        request_body = make_stage_one_request_body(self._config, rendered_prompt)
        request_body_json = _canonical_json(request_body)
        events.append("body")
        reparsed = json.loads(request_body_json)
        if reparsed != request_body or reparsed.get("response_format") != {"type": "json_object"}:
            raise ValueError("request body failed exact JSON-object validation before sink")
        events.append("validate")
        response = self._transport.invoke(
            request_body=request_body,
            fixture_response=fixture_response,
        )
        events.append("sink")
        self._invocations.append(
            ZeroCallInvocation(
                prompt_kind=prompt_kind,
                prompt_core_canonical_json=_canonical_json(core),
                rendered_prompt=rendered_prompt,
                request_body_canonical_json=request_body_json,
                rendered_before_request_body=True,
                request_body_validated_before_sink=True,
                event_sequence=tuple(events),
            )
        )
        return response


__all__ = [
    "CredentialFreeExactFutureRunner",
    "CredentialFreeFixtureTransport",
    "ProviderTransport",
    "ZeroCallInvocation",
]
