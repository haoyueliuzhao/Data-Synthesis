from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from typing import Any, Final, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from trusted_synthesis.hashing import canonical_hash
from trusted_synthesis.runtime.agent.compact_budget_prompt import FINAL_HEADER

FINAL_RESPONSE_PROTOCOL_VERSION: Final = "prospective_exact_final_response.v1"
FINAL_RESPONSE_GRAMMAR_VERSION: Final = "prospective_exact_final_response_grammar.v1"
FINAL_PRIMARY_PROMPT_VERSION: Final = "prospective_exact_final_primary_prompt.v1"
FINAL_RESCUE_PROMPT_VERSION: Final = "prospective_exact_final_rescue_prompt.v1"
FINAL_FIELD_ORDER: Final = ("answer", "rationale_summary")
MAXIMUM_FINAL_PROMPT_UTF8_BYTES: Final = 60_000


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


def _identity(value: BaseModel, field: str, prefix: str) -> str:
    return canonical_hash(value.model_dump(mode="json", exclude={field}), prefix=prefix)


def _contains_private_reasoning(value: Any) -> bool:
    if isinstance(value, Mapping):
        for key, item in value.items():
            normalized = str(key).casefold()
            if "reasoning" in normalized and normalized not in {
                "reasoning_content_present",
                "reasoning_content_length",
                "reasoning_tokens",
            }:
                return True
            if _contains_private_reasoning(item):
                return True
    elif isinstance(value, (list, tuple)):
        return any(_contains_private_reasoning(item) for item in value)
    return False


class ExactFinalResponsePayload(FrozenModel):
    answer: dict[str, Any] = Field(min_length=1)
    rationale_summary: str = Field(min_length=1)

    @model_validator(mode="before")
    @classmethod
    def validate_exact_shape(cls, value: Any) -> Any:
        if not isinstance(value, Mapping) or set(value) != set(FINAL_FIELD_ORDER):
            raise ValueError("Final response requires exactly answer and rationale_summary")
        if _contains_private_reasoning(value):
            raise ValueError("Final response contains private reasoning fields")
        return value


class FinalResponseFieldGrammar(FrozenModel):
    name: Literal["answer", "rationale_summary"]
    json_type: Literal["object", "string"]
    always_present: Literal[True] = True
    model_generated: Literal[True] = True


class ExactFinalResponseGrammar(FrozenModel):
    grammar_id: str = Field(min_length=1)
    response_protocol: Literal["prospective_exact_final_response.v1"] = (
        FINAL_RESPONSE_PROTOCOL_VERSION
    )
    field_order: tuple[str, str] = FINAL_FIELD_ORDER
    fields: tuple[FinalResponseFieldGrammar, FinalResponseFieldGrammar]
    exact_top_level_field_set_required: Literal[True] = True
    extra_fields_allowed: Literal[False] = False
    wrapper_allowed: Literal[False] = False
    exactly_one_json_object_required: Literal[True] = True
    primary_and_rescue_share_grammar: Literal[True] = True
    parser_compiled_from_same_grammar: Literal[True] = True
    json_mode_lexical_cue_required: Literal[True] = True
    host_bound_metadata_fields: tuple[str, str, str, str] = (
        "stage",
        "protocol",
        "terminal_state_id",
        "terminal_commit_id",
    )
    model_generates_host_metadata: Literal[False] = False
    host_answer_or_rationale_insertion_allowed: Literal[False] = False
    private_reasoning_content_allowed: Literal[False] = False
    schema_version: Literal["prospective_exact_final_response_grammar.v1"] = (
        FINAL_RESPONSE_GRAMMAR_VERSION
    )

    @model_validator(mode="after")
    def validate_grammar(self) -> ExactFinalResponseGrammar:
        if tuple(item.name for item in self.fields) != FINAL_FIELD_ORDER:
            raise ValueError("Final response Grammar diverged from its strong Schema")
        if tuple(item.json_type for item in self.fields) != ("object", "string"):
            raise ValueError("Final response Grammar field types changed")
        if self.grammar_id != exact_final_response_grammar_id(self):
            raise ValueError("Final response Grammar identity changed")
        return self


class FinalResponseHostEnvelope(FrozenModel):
    envelope_id: str = Field(min_length=1)
    grammar_id: str = Field(min_length=1)
    response_protocol: Literal["prospective_exact_final_response.v1"] = (
        FINAL_RESPONSE_PROTOCOL_VERSION
    )
    stage: Literal["final_answer"] = "final_answer"
    terminal_state_id: str = Field(min_length=1)
    terminal_commit_id: str = Field(min_length=1)
    model_payload_fields: tuple[str, str] = FINAL_FIELD_ORDER
    host_supplies_answer_or_rationale: Literal[False] = False
    schema_version: Literal["prospective_exact_final_response_host_envelope.v1"] = (
        "prospective_exact_final_response_host_envelope.v1"
    )

    @model_validator(mode="after")
    def validate_envelope(self) -> FinalResponseHostEnvelope:
        if self.envelope_id != _identity(
            self,
            "envelope_id",
            "prospective_exact_final_response_host_envelope:",
        ):
            raise ValueError("Final response Host Envelope identity changed")
        return self


class ExactFinalResponseRejection(ValueError):
    def __init__(self, *, family: str, subtype: str) -> None:
        super().__init__(subtype)
        self.family = family
        self.subtype = subtype


def exact_final_response_grammar_id(value: ExactFinalResponseGrammar) -> str:
    return _identity(
        value,
        "grammar_id",
        "prospective_exact_final_response_grammar:",
    )


def compile_exact_final_response_grammar() -> ExactFinalResponseGrammar:
    if tuple(ExactFinalResponsePayload.model_fields) != FINAL_FIELD_ORDER:
        raise ValueError("strong two-field Final response Schema changed")
    values = {
        "fields": (
            FinalResponseFieldGrammar(name="answer", json_type="object"),
            FinalResponseFieldGrammar(name="rationale_summary", json_type="string"),
        )
    }
    provisional = ExactFinalResponseGrammar.model_construct(grammar_id="pending", **values)
    return ExactFinalResponseGrammar(
        grammar_id=exact_final_response_grammar_id(provisional),
        **values,
    )


def make_final_response_host_envelope(
    *,
    terminal_state_id: str,
    terminal_commit_id: str,
    grammar: ExactFinalResponseGrammar | None = None,
) -> FinalResponseHostEnvelope:
    active = grammar or compile_exact_final_response_grammar()
    values = {
        "grammar_id": active.grammar_id,
        "terminal_state_id": terminal_state_id,
        "terminal_commit_id": terminal_commit_id,
    }
    provisional = FinalResponseHostEnvelope.model_construct(envelope_id="pending", **values)
    return FinalResponseHostEnvelope(
        envelope_id=_identity(
            provisional,
            "envelope_id",
            "prospective_exact_final_response_host_envelope:",
        ),
        **values,
    )


def _legacy_final_context(source_prompt: str) -> dict[str, Any]:
    header, separator, raw = source_prompt.partition("\n")
    if not separator or header != f"{FINAL_HEADER}.":
        raise ValueError("source Final Prompt is not the frozen compact Final projection")
    value = json.loads(raw)
    if not isinstance(value, Mapping):
        raise ValueError("source Final Prompt payload is not an object")
    expected = {
        "final_context",
        "public_path_condition",
        "progress",
        "history",
        "response_contract",
    }
    if set(value) != expected:
        raise ValueError("source Final Prompt public projection changed")
    return {
        "final_context": value["final_context"],
        "public_path_condition": value["public_path_condition"],
        "progress": value["progress"],
        "history": value["history"],
    }


def _model_visible_grammar(grammar: ExactFinalResponseGrammar) -> dict[str, Any]:
    return {
        "id": grammar.grammar_id,
        "fields": list(grammar.field_order),
        "types": [item.json_type for item in grammar.fields],
        "rules": [
            "exactly_one_json_object",
            "exactly_two_top_level_fields",
            "no_wrapper",
            "no_extra_fields",
        ],
        "host_metadata_not_model_fields": list(grammar.host_bound_metadata_fields),
        "private_reasoning_content": "not_allowed",
    }


def _render(
    *,
    phase: Literal["primary", "rescue"],
    context: Mapping[str, Any],
    typed_failure: Mapping[str, Any] | None,
    grammar: ExactFinalResponseGrammar,
) -> str:
    prompt_protocol = (
        FINAL_PRIMARY_PROMPT_VERSION if phase == "primary" else FINAL_RESCUE_PROMPT_VERSION
    )
    payload = {
        "prompt_protocol": prompt_protocol,
        **dict(context),
        "response_grammar": _model_visible_grammar(grammar),
        "typed_failure": dict(typed_failure) if typed_failure is not None else None,
        "previous_response_content_reused": False,
        "private_reasoning_reused": False,
    }
    prefix = (
        "Return exactly one JSON object with exactly the fields answer and rationale_summary."
        if phase == "primary"
        else (
            "Correct only the Final response grammar and return exactly one JSON object "
            "with exactly the fields answer and rationale_summary."
        )
    )
    prompt = (
        prefix
        + "\n"
        + json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    )
    if "json" not in prompt.casefold():
        raise ValueError("Final response Prompt lacks the Provider JSON-mode lexical cue")
    if len(prompt.encode("utf-8")) > MAXIMUM_FINAL_PROMPT_UTF8_BYTES:
        raise ValueError("Final response Prompt exceeds the frozen byte ceiling")
    return prompt


def render_exact_final_primary_prompt(
    source_prompt: str,
    *,
    grammar: ExactFinalResponseGrammar | None = None,
) -> str:
    active = grammar or compile_exact_final_response_grammar()
    return _render(
        phase="primary",
        context=_legacy_final_context(source_prompt),
        typed_failure=None,
        grammar=active,
    )


def render_exact_final_rescue_prompt(
    primary_prompt: str,
    *,
    failure_family: str,
    failure_subtype: str,
) -> str:
    payload = _prompt_payload(primary_prompt, expected_phase="primary")
    context = {
        key: payload[key]
        for key in ("final_context", "public_path_condition", "progress", "history")
    }
    return _render(
        phase="rescue",
        context=context,
        typed_failure={"family": failure_family, "subtype": failure_subtype},
        grammar=compile_exact_final_response_grammar(),
    )


def _prompt_payload(
    prompt: str,
    *,
    expected_phase: Literal["primary", "rescue"] | None = None,
) -> Mapping[str, Any]:
    prefix, separator, raw = prompt.partition("\n")
    if not separator:
        raise ValueError("Final response Prompt lacks its serialized payload")
    phase: Literal["primary", "rescue"]
    if prefix.startswith("Return exactly one JSON object"):
        phase = "primary"
    elif prefix.startswith("Correct only the Final response grammar"):
        phase = "rescue"
    else:
        raise ValueError("Final response Prompt envelope changed")
    if expected_phase is not None and phase != expected_phase:
        raise ValueError("Final response Prompt phase changed")
    value = json.loads(raw)
    if not isinstance(value, Mapping):
        raise ValueError("Final response Prompt payload is not an object")
    expected_protocol = (
        FINAL_PRIMARY_PROMPT_VERSION if phase == "primary" else FINAL_RESCUE_PROMPT_VERSION
    )
    if value.get("prompt_protocol") != expected_protocol:
        raise ValueError("Final response Prompt protocol changed")
    if dict(value.get("response_grammar") or {}) != _model_visible_grammar(
        compile_exact_final_response_grammar()
    ):
        raise ValueError("model-visible Final response Grammar changed")
    if "json" not in prompt.casefold():
        raise ValueError("Final response Prompt lacks a JSON lexical cue")
    return value


def final_prompt_semantic_projection(prompt: str) -> dict[str, Any]:
    payload = _prompt_payload(prompt)
    return {
        key: payload[key]
        for key in (
            "final_context",
            "public_path_condition",
            "progress",
            "history",
            "response_grammar",
        )
    }


def exact_final_response_payload(
    answer: Mapping[str, Any],
    *,
    rationale_summary: str,
) -> dict[str, Any]:
    return ExactFinalResponsePayload(
        answer=dict(answer),
        rationale_summary=rationale_summary,
    ).model_dump(mode="json")


def parse_exact_final_response_payload(
    payload: Mapping[str, Any],
    *,
    grammar: ExactFinalResponseGrammar,
    envelope: FinalResponseHostEnvelope,
) -> ExactFinalResponsePayload:
    if (
        grammar != compile_exact_final_response_grammar()
        or envelope.grammar_id != grammar.grammar_id
        or envelope.response_protocol != grammar.response_protocol
    ):
        raise ValueError("Final response Parser is not bound to its Grammar and Host Envelope")
    try:
        return ExactFinalResponsePayload.model_validate(payload)
    except ValidationError as exc:
        raise ExactFinalResponseRejection(
            family="response_serialization_failure",
            subtype="final_response_not_exact_shared_grammar",
        ) from exc


def _mapping(value: Any, *, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"Prompt-only Final fixture lacks {field}")
    return value


def _select(value: Any, selector: Sequence[Any]) -> Any:
    current = value
    for item in selector:
        if not isinstance(current, Mapping) or item not in current:
            raise ValueError("Prompt-only Final selector does not resolve public history")
        current = current[item]
    return current


def prompt_only_reference_final_payload(prompt: str) -> dict[str, Any]:
    payload = _prompt_payload(prompt)
    final_context = _mapping(payload.get("final_context"), field="final_context")
    answer_observation = _mapping(
        final_context.get("answer_observation"),
        field="answer_observation",
    )
    answer_schema = _mapping(final_context.get("answer_schema"), field="answer_schema")
    history = _mapping(payload.get("history"), field="history")
    operations = history.get("operations")
    if not isinstance(operations, Sequence) or isinstance(operations, (str, bytes)):
        raise ValueError("Prompt-only Final fixture lacks public operations")
    source_tool = answer_observation.get("source_tool_id")
    source = next(
        (
            item
            for item in reversed(operations)
            if isinstance(item, Mapping)
            and item.get("tool_id") == source_tool
            and item.get("status") == "succeeded"
        ),
        None,
    )
    if source is None:
        raise ValueError("Prompt-only Final fixture lacks a successful terminal operation")
    selector = answer_observation.get("source_result_selector")
    if not isinstance(selector, Sequence) or isinstance(selector, (str, bytes)):
        raise ValueError("Prompt-only Final fixture lacks a result selector")
    projected = _mapping(_select(source.get("result"), selector), field="projected_result")
    required = answer_schema.get("required_fields")
    if not isinstance(required, Sequence) or isinstance(required, (str, bytes)) or not required:
        raise ValueError("Prompt-only Final fixture lacks required answer fields")
    result = {str(field): projected[str(field)] for field in required}
    selected = history.get("selected_evidence_ids")
    if not isinstance(selected, Sequence) or isinstance(selected, (str, bytes)) or not selected:
        raise ValueError("Prompt-only Final fixture lacks selected public Evidence")
    answer = {
        "result": result,
        "citations": [{"evidence_id": str(item)} for item in selected],
    }
    return exact_final_response_payload(
        answer,
        rationale_summary=(
            "Projected the verified terminal public result and its selected public evidence."
        ),
    )


def parse_prompt_only_reference_final_payload(
    prompt: str,
    *,
    envelope: FinalResponseHostEnvelope,
) -> ExactFinalResponsePayload:
    return parse_exact_final_response_payload(
        prompt_only_reference_final_payload(prompt),
        grammar=compile_exact_final_response_grammar(),
        envelope=envelope,
    )
