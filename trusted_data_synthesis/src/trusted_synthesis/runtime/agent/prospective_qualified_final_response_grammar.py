from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Final, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.hashing import canonical_hash

QUALIFIED_FINAL_RESPONSE_PROTOCOL: Final[Literal["prospective_qualified_final_response.v1"]] = (
    "prospective_qualified_final_response.v1"
)
QUALIFIED_FINAL_RESPONSE_GRAMMAR_VERSION: Final[
    Literal["prospective_qualified_final_response_grammar.v1"]
] = "prospective_qualified_final_response_grammar.v1"


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class ModelEvidenceCitation(FrozenModel):
    evidence_id: str = Field(min_length=1)

    @model_validator(mode="before")
    @classmethod
    def validate_exact_shape(cls, value: Any) -> Any:
        if not isinstance(value, Mapping) or set(value) != {"evidence_id"}:
            raise ValueError("model Citation requires exactly evidence_id")
        return value


class ModelOwnedFinalAnswer(FrozenModel):
    result: dict[str, Any] = Field(min_length=1)
    citations: tuple[ModelEvidenceCitation, ...] = Field(min_length=1)

    @model_validator(mode="before")
    @classmethod
    def validate_exact_shape(cls, value: Any) -> Any:
        if not isinstance(value, Mapping) or set(value) != {"result", "citations"}:
            raise ValueError("model answer requires exactly result and citations")
        return value

    @model_validator(mode="after")
    def validate_citations(self) -> ModelOwnedFinalAnswer:
        ids = tuple(item.evidence_id for item in self.citations)
        if len(ids) != len(set(ids)):
            raise ValueError("model Citations must be unique")
        return self


class QualifiedFinalResponsePayload(FrozenModel):
    answer: ModelOwnedFinalAnswer
    rationale_summary: str = Field(min_length=1)

    @model_validator(mode="before")
    @classmethod
    def validate_exact_shape(cls, value: Any) -> Any:
        if not isinstance(value, Mapping) or set(value) != {"answer", "rationale_summary"}:
            raise ValueError("Final response requires exactly answer and rationale_summary")
        return value


class QualifiedFinalResponseGrammar(FrozenModel):
    grammar_id: str = Field(min_length=1)
    response_protocol: Literal["prospective_qualified_final_response.v1"] = (
        QUALIFIED_FINAL_RESPONSE_PROTOCOL
    )
    outer_field_order: tuple[str, str] = ("answer", "rationale_summary")
    answer_field_order: tuple[str, str] = ("result", "citations")
    citation_field_order: tuple[str] = ("evidence_id",)
    exact_outer_field_set_required: Literal[True] = True
    exact_answer_field_set_required: Literal[True] = True
    exact_citation_field_set_required: Literal[True] = True
    exactly_one_json_object_required: Literal[True] = True
    flat_answer_alias_allowed: Literal[False] = False
    host_answer_insertion_allowed: Literal[False] = False
    host_citation_insertion_allowed: Literal[False] = False
    host_rationale_insertion_allowed: Literal[False] = False
    runtime_support_may_satisfy_model_citation: Literal[False] = False
    model_owns_result: Literal[True] = True
    model_owns_citations: Literal[True] = True
    model_owns_rationale_summary: Literal[True] = True
    host_bound_metadata_fields: tuple[str, str, str, str] = (
        "stage",
        "protocol",
        "terminal_state_id",
        "terminal_commit_id",
    )
    schema_version: Literal["prospective_qualified_final_response_grammar.v1"] = (
        QUALIFIED_FINAL_RESPONSE_GRAMMAR_VERSION
    )

    @model_validator(mode="after")
    def validate_grammar(self) -> QualifiedFinalResponseGrammar:
        if self.grammar_id != qualified_final_response_grammar_id(self):
            raise ValueError("qualified Final Grammar identity changed")
        return self


class QualifiedFinalHostEnvelope(FrozenModel):
    envelope_id: str = Field(min_length=1)
    grammar_id: str = Field(min_length=1)
    response_protocol: Literal["prospective_qualified_final_response.v1"] = (
        QUALIFIED_FINAL_RESPONSE_PROTOCOL
    )
    stage: Literal["final_answer"] = "final_answer"
    terminal_state_id: str = Field(min_length=1)
    terminal_commit_id: str = Field(min_length=1)
    host_supplies_result: Literal[False] = False
    host_supplies_citations: Literal[False] = False
    host_supplies_rationale_summary: Literal[False] = False
    schema_version: str = "prospective_qualified_final_host_envelope.v1"

    @model_validator(mode="after")
    def validate_envelope(self) -> QualifiedFinalHostEnvelope:
        if self.envelope_id != _identity(
            self,
            "envelope_id",
            "prospective_qualified_final_host_envelope:",
        ):
            raise ValueError("qualified Final Host Envelope identity changed")
        return self


def qualified_final_response_grammar_id(value: QualifiedFinalResponseGrammar) -> str:
    return _identity(
        value,
        "grammar_id",
        "prospective_qualified_final_response_grammar:",
    )


def compile_qualified_final_response_grammar() -> QualifiedFinalResponseGrammar:
    provisional = QualifiedFinalResponseGrammar.model_construct(grammar_id="pending")
    return QualifiedFinalResponseGrammar(
        grammar_id=qualified_final_response_grammar_id(provisional)
    )


def make_qualified_final_host_envelope(
    *,
    grammar: QualifiedFinalResponseGrammar,
    terminal_state_id: str,
    terminal_commit_id: str,
) -> QualifiedFinalHostEnvelope:
    values = {
        "grammar_id": grammar.grammar_id,
        "terminal_state_id": terminal_state_id,
        "terminal_commit_id": terminal_commit_id,
    }
    provisional = QualifiedFinalHostEnvelope.model_construct(envelope_id="pending", **values)
    return QualifiedFinalHostEnvelope(
        envelope_id=_identity(
            provisional,
            "envelope_id",
            "prospective_qualified_final_host_envelope:",
        ),
        **values,
    )


def parse_qualified_final_response(
    payload: Mapping[str, Any],
    *,
    grammar: QualifiedFinalResponseGrammar,
    envelope: QualifiedFinalHostEnvelope,
) -> QualifiedFinalResponsePayload:
    if (
        envelope.grammar_id != grammar.grammar_id
        or envelope.response_protocol != grammar.response_protocol
    ):
        raise ValueError("qualified Final response is detached from its Host Envelope")
    return QualifiedFinalResponsePayload.model_validate(payload)


def _identity(value: BaseModel, field: str, prefix: str) -> str:
    return canonical_hash(value.model_dump(mode="json", exclude={field}), prefix=prefix)
