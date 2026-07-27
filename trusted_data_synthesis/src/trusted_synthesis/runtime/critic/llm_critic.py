from __future__ import annotations

import json
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from trusted_synthesis.core.evaluation.critic.schema import (
    AcceptabilityLabel,
    FailureLocationLabel,
    QualityCriticExample,
    QualityCriticPrediction,
)
from trusted_synthesis.hashing import canonical_hash
from trusted_synthesis.runtime.agent.client import JsonCompletionClient, LLMClientError
from trusted_synthesis.runtime.agent.schema import ModelCallTelemetry

LLM_CRITIC_PROMPT_VERSION = "llm_quality_critic_prompt.v2"


class _CriticResponseContract(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["quality_critic_response.v1"]
    accept_probability: float = Field(ge=0, le=1)
    predicted_acceptability: AcceptabilityLabel
    failure_families: tuple[str, ...] = ()
    root_locations: tuple[FailureLocationLabel, ...] = ()
    dimension_scores: dict[str, float] = Field(default_factory=dict)


class LLMQualityCriticResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    prediction: QualityCriticPrediction
    telemetry: tuple[ModelCallTelemetry, ...]
    prompt_manifest_hash: str


class LLMQualityCritic:
    """Advisory critic. Contract Runtime remains the authoritative decision maker."""

    def __init__(self, client: JsonCompletionClient) -> None:
        self._client = client
        self._response_schema = _CriticResponseContract.model_json_schema()
        self._prompt_manifest_hash = canonical_hash(
            {
                "prompt_version": LLM_CRITIC_PROMPT_VERSION,
                "response_schema": self._response_schema,
                "model_config_hash": client.config.public_manifest_hash,
            },
            prefix="llm_quality_critic_prompt_manifest:",
        )

    def predict(self, example: QualityCriticExample) -> QualityCriticPrediction:
        return self.predict_with_audit(example).prediction

    def predict_with_audit(
        self,
        example: QualityCriticExample,
    ) -> LLMQualityCriticResult:
        prompt = _critic_prompt(
            example.critic_input,
            self._response_schema,
        )
        response, telemetry = _request_critic_response(self._client, prompt)
        successful_call = telemetry[-1]
        identity = {
            "example_id": example.example_id,
            "model_config_hash": self._client.config.public_manifest_hash,
            "prompt_manifest_hash": self._prompt_manifest_hash,
            "response": response.model_dump(mode="json"),
        }
        prediction = QualityCriticPrediction(
            prediction_id=canonical_hash(identity, prefix="quality_critic_prediction:"),
            example_id=example.example_id,
            model_id=successful_call.response_model
            or successful_call.model_selected
            or self._client.config.model,
            model_manifest_hash=self._client.config.public_manifest_hash,
            accept_probability=response.accept_probability,
            predicted_acceptability=response.predicted_acceptability,
            failure_families=response.failure_families,
            root_locations=response.root_locations,
            dimension_scores=response.dimension_scores,
        )
        return LLMQualityCriticResult(
            prediction=prediction,
            telemetry=telemetry,
            prompt_manifest_hash=self._prompt_manifest_hash,
        )


def _request_critic_response(
    client: JsonCompletionClient,
    base_prompt: str,
) -> tuple[_CriticResponseContract, tuple[ModelCallTelemetry, ...]]:
    telemetry: list[ModelCallTelemetry] = []
    previous_payload: dict[str, Any] | None = None
    validation_error = ""
    response: _CriticResponseContract | None = None
    for attempt in range(client.config.contract_repair_attempts + 1):
        prompt = (
            base_prompt
            if attempt == 0
            else _critic_repair_prompt(
                base_prompt,
                previous_payload,
                validation_error,
            )
        )
        try:
            payload, call_telemetry = client.complete_json(prompt)
        except LLMClientError as exc:
            telemetry.extend(exc.telemetry)
            raise LLMClientError(
                "quality critic model call failed",
                tuple(telemetry),
            ) from exc
        previous_payload = payload
        try:
            response = _CriticResponseContract.model_validate(payload)
            telemetry.append(call_telemetry)
            break
        except ValidationError as exc:
            validation_error = str(exc)
            telemetry.append(
                call_telemetry.model_copy(
                    update={
                        "json_contract_success": False,
                        "error_type": "QualityCriticContractError",
                    }
                )
            )
    if response is None:
        raise LLMClientError(
            "model failed the quality critic response contract",
            tuple(telemetry),
        )
    return response, tuple(telemetry)


def _critic_repair_prompt(
    base_prompt: str,
    previous_payload: dict[str, Any] | None,
    validation_error: str,
) -> str:
    repair = {
        "previous_response": previous_payload,
        "contract_error": validation_error,
        "repair_rule": (
            "Repair only the JSON contract. Re-evaluate from the same public input; "
            "no Contract Runtime decision or hidden label is available."
        ),
    }
    return (
        f"{base_prompt}\n\n"
        f"CONTRACT_REPAIR:\n{json.dumps(repair, ensure_ascii=False, sort_keys=True)}"
    )


def _critic_prompt(
    critic_input: dict[str, Any],
    response_schema: dict[str, Any],
) -> str:
    instructions = (
        "Act as an advisory trajectory quality critic. Independently inspect the public "
        "task, evidence corpus, candidate trajectory, and quality contract summary. "
        "Predict acceptability, root failure families, exact target locations, and "
        "dimension scores. Do not assume a missing Contract Runtime result and do not "
        "invent evidence. Return one JSON object matching response_json_schema. This "
        "model opinion is advisory and cannot overrule deterministic contract failures."
    )
    payload = {
        "critic_input": critic_input,
        "response_json_schema": response_schema,
    }
    return f"{instructions}\n\nPAYLOAD:\n{json.dumps(payload, ensure_ascii=False, sort_keys=True)}"
