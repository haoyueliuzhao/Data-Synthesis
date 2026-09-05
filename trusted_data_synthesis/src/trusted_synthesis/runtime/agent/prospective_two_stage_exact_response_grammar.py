from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any, Final, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from trusted_synthesis.hashing import canonical_hash
from trusted_synthesis.runtime.agent.prospective_action_constructibility import (
    ACTION_CONSTRUCTIBILITY_PROTOCOL_VERSION,
    ProspectiveFailureClassification,
    PublicActionState,
    SemanticDecisionProposal,
    make_semantic_decision_proposal,
    public_reference_policy_proposal,
)

EXACT_RESPONSE_PROTOCOL_VERSION: Final = "prospective_two_stage_stage_one_exact_response.v2"
EXACT_RESPONSE_GRAMMAR_VERSION: Final = "prospective_two_stage_stage_one_response_grammar.v1"
EXACT_PRIMARY_PROMPT_VERSION: Final = "prospective_two_stage_exact_response_primary_prompt.v1"
EXACT_RESCUE_PROMPT_VERSION: Final = "prospective_two_stage_exact_response_rescue_prompt.v1"
EXACT_STAGE: Final = "semantic_decision_proposal"
MAXIMUM_PRIMARY_PROMPT_UTF8_BYTES: Final = 60_000
MAXIMUM_RESCUE_PROMPT_UTF8_BYTES: Final = 6_144

DecisionKind = Literal[
    "acquire_public_input",
    "execute_public_operation",
    "verify_terminal_operation",
    "emit_final_answer",
]

FIELD_ORDER: Final = (
    "stage",
    "state_id",
    "decision_kind",
    "tool_id",
    "node_id",
    "operator_id",
    "operand_sources",
    "direct_arguments",
    "evidence_ids",
    "protocol",
)

# The parser validator and model-visible Grammar compiler consume this same table.
DECISION_FIELD_RULES: Final[dict[str, dict[str, tuple[str, ...]]]] = {
    "acquire_public_input": {
        "required_non_null": ("tool_id", "direct_arguments"),
        "required_null": ("node_id", "operator_id"),
        "required_non_empty": (),
        "required_empty": ("operand_sources", "evidence_ids"),
    },
    "execute_public_operation": {
        "required_non_null": ("tool_id", "node_id"),
        "required_null": ("direct_arguments",),
        "required_non_empty": ("operand_sources",),
        "required_empty": ("evidence_ids",),
    },
    "verify_terminal_operation": {
        "required_non_null": ("tool_id",),
        "required_null": ("node_id", "operator_id", "direct_arguments"),
        "required_non_empty": ("evidence_ids",),
        "required_empty": ("operand_sources",),
    },
    "emit_final_answer": {
        "required_non_null": (),
        "required_null": ("tool_id", "node_id", "operator_id", "direct_arguments"),
        "required_non_empty": (),
        "required_empty": ("operand_sources", "evidence_ids"),
    },
}


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class ExactStageOneSemanticProposalPayload(FrozenModel):
    stage: Literal["semantic_decision_proposal"]
    state_id: str = Field(min_length=1)
    decision_kind: DecisionKind
    tool_id: str | None
    node_id: str | None
    operator_id: str | None
    operand_sources: tuple[str, ...]
    direct_arguments: dict[str, Any] | None
    evidence_ids: tuple[str, ...]
    protocol: Literal["prospective_two_stage_stage_one_exact_response.v2"]

    @model_validator(mode="before")
    @classmethod
    def validate_exact_top_level_shape(cls, value: Any) -> Any:
        if not isinstance(value, Mapping) or set(value) != set(FIELD_ORDER):
            raise ValueError("exact Stage 1 response requires the registered ten fields")
        return value

    @model_validator(mode="after")
    def validate_conditional_fields(self) -> ExactStageOneSemanticProposalPayload:
        rule = DECISION_FIELD_RULES[self.decision_kind]
        values = self.model_dump(mode="python")
        for field in rule["required_non_null"]:
            if values[field] is None or values[field] == "":
                raise ValueError(f"{field} must be non-null for {self.decision_kind}")
        for field in rule["required_null"]:
            if values[field] is not None:
                raise ValueError(f"{field} must be null for {self.decision_kind}")
        for field in rule["required_non_empty"]:
            if not values[field]:
                raise ValueError(f"{field} must be non-empty for {self.decision_kind}")
        for field in rule["required_empty"]:
            if values[field]:
                raise ValueError(f"{field} must be empty for {self.decision_kind}")
        make_semantic_decision_proposal(
            state_id=self.state_id,
            decision_kind=self.decision_kind,
            tool_id=self.tool_id,
            node_id=self.node_id,
            operator_id=self.operator_id,
            operand_sources=self.operand_sources,
            direct_arguments=self.direct_arguments,
            evidence_ids=self.evidence_ids,
        )
        return self


class ResponseFieldGrammar(FrozenModel):
    name: str = Field(min_length=1)
    json_type: tuple[str, ...] = Field(min_length=1)
    always_present: Literal[True] = True
    default_when_not_applicable: Any


class DecisionKindGrammar(FrozenModel):
    decision_kind: DecisionKind
    required_non_null: tuple[str, ...]
    required_null: tuple[str, ...]
    required_non_empty: tuple[str, ...]
    required_empty: tuple[str, ...]


class StageOneResponseGrammarArtifact(FrozenModel):
    grammar_id: str = Field(min_length=1)
    response_protocol: Literal["prospective_two_stage_stage_one_exact_response.v2"] = (
        EXACT_RESPONSE_PROTOCOL_VERSION
    )
    stage_constant: Literal["semantic_decision_proposal"] = EXACT_STAGE
    field_order: tuple[str, ...] = FIELD_ORDER
    field_order_semantic: Literal[False] = False
    exact_top_level_field_set_required: Literal[True] = True
    extra_fields_allowed: Literal[False] = False
    top_level_wrapper_allowed: Literal[False] = False
    exactly_one_proposal_required: Literal[True] = True
    state_id_rule: Literal["copy_current_public_action_state_id_exactly"] = (
        "copy_current_public_action_state_id_exactly"
    )
    fields: tuple[ResponseFieldGrammar, ...] = Field(min_length=10, max_length=10)
    decision_rules: tuple[DecisionKindGrammar, ...] = Field(min_length=4, max_length=4)
    json_skeleton: dict[str, Any]
    host_alias_normalization_allowed: Literal[False] = False
    host_missing_field_insertion_allowed: Literal[False] = False
    host_semantic_field_selection_allowed: Literal[False] = False
    private_reasoning_content_allowed: Literal[False] = False
    source_schema_qualified_name: Literal["ExactStageOneSemanticProposalPayload"] = (
        "ExactStageOneSemanticProposalPayload"
    )
    schema_version: Literal["prospective_two_stage_stage_one_response_grammar.v1"] = (
        EXACT_RESPONSE_GRAMMAR_VERSION
    )

    @model_validator(mode="after")
    def validate_artifact(self) -> StageOneResponseGrammarArtifact:
        if tuple(item.name for item in self.fields) != FIELD_ORDER:
            raise ValueError("response Grammar fields diverged from the strong Schema")
        if tuple(item.decision_kind for item in self.decision_rules) != tuple(DECISION_FIELD_RULES):
            raise ValueError("response Grammar conditional rules diverged")
        if set(self.json_skeleton) != set(FIELD_ORDER):
            raise ValueError("response Grammar skeleton omits an exact field")
        if self.grammar_id != response_grammar_id(self):
            raise ValueError("response Grammar identity changed")
        return self


class ExactResponseModelRejection(ValueError):
    def __init__(self, classification: ProspectiveFailureClassification) -> None:
        super().__init__(classification.subtype)
        self.classification = classification


def response_grammar_id(value: StageOneResponseGrammarArtifact) -> str:
    payload = value.model_dump(mode="json")
    payload.pop("grammar_id", None)
    return canonical_hash(payload, prefix="prospective_stage_one_response_grammar:")


def compile_stage_one_response_grammar() -> StageOneResponseGrammarArtifact:
    model_fields = ExactStageOneSemanticProposalPayload.model_fields
    if tuple(model_fields) != FIELD_ORDER:
        raise ValueError("strong Stage 1 Schema field order changed")
    field_types: dict[str, tuple[str, ...]] = {
        "stage": ("string",),
        "state_id": ("string",),
        "decision_kind": ("string",),
        "tool_id": ("string", "null"),
        "node_id": ("string", "null"),
        "operator_id": ("string", "null"),
        "operand_sources": ("array[string]",),
        "direct_arguments": ("object", "null"),
        "evidence_ids": ("array[string]",),
        "protocol": ("string",),
    }
    skeleton: dict[str, Any] = {
        "stage": EXACT_STAGE,
        "state_id": "<COPY_CURRENT_PUBLIC_ACTION_STATE_ID_EXACTLY>",
        "decision_kind": "<ONE_REGISTERED_DECISION_KIND>",
        "tool_id": None,
        "node_id": None,
        "operator_id": None,
        "operand_sources": [],
        "direct_arguments": None,
        "evidence_ids": [],
        "protocol": EXACT_RESPONSE_PROTOCOL_VERSION,
    }
    fields = tuple(
        ResponseFieldGrammar(
            name=name,
            json_type=field_types[name],
            default_when_not_applicable=skeleton[name],
        )
        for name in model_fields
    )
    rules = tuple(
        DecisionKindGrammar(decision_kind=decision_kind, **rule)
        for decision_kind, rule in DECISION_FIELD_RULES.items()
    )
    values = {"fields": fields, "decision_rules": rules, "json_skeleton": skeleton}
    provisional = StageOneResponseGrammarArtifact.model_construct(grammar_id="pending", **values)
    return StageOneResponseGrammarArtifact(grammar_id=response_grammar_id(provisional), **values)


def _model_visible_grammar(grammar: StageOneResponseGrammarArtifact) -> dict[str, Any]:
    return {
        "id": grammar.grammar_id,
        "fields": list(grammar.field_order),
        "types_aligned_to_fields": ["|".join(item.json_type) for item in grammar.fields],
        "defaults_aligned_to_fields": [item.default_when_not_applicable for item in grammar.fields],
        "rule_columns": (
            "decision_kind",
            "non_null",
            "null",
            "non_empty",
            "empty",
        ),
        "rules": [
            (
                item.decision_kind,
                item.required_non_null,
                item.required_null,
                item.required_non_empty,
                item.required_empty,
            )
            for item in grammar.decision_rules
        ],
        "shape_rules": (
            "exactly_these_ten_top_level_fields",
            "exactly_one_json_object",
            "no_wrapper",
            "no_extra_fields",
            "field_order_not_semantic",
        ),
        "state_id_rule": "copy_current_public_action_state_id_exactly",
        "host_rules": (
            "no_alias_normalization",
            "no_missing_field_insertion",
            "no_semantic_field_selection",
        ),
        "private_reasoning_content": "not_allowed",
    }


def _render_prompt(prefix: str, payload: Mapping[str, Any], *, ceiling: int) -> str:
    prompt = (
        prefix
        + "\n"
        + json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    )
    if len(prompt.encode("utf-8")) > ceiling:
        raise ValueError("exact response Grammar Prompt exceeds its frozen byte ceiling")
    return prompt


def render_exact_semantic_proposal_prompt(
    *,
    instruction: str,
    state: PublicActionState,
    public_path_condition: str | None,
    grammar: StageOneResponseGrammarArtifact | None = None,
) -> str:
    exact_grammar = grammar or compile_stage_one_response_grammar()
    payload = {
        "prompt_protocol": EXACT_PRIMARY_PROMPT_VERSION,
        "action_constructibility_protocol": ACTION_CONSTRUCTIBILITY_PROTOCOL_VERSION,
        "instruction": instruction,
        "public_path_condition": public_path_condition,
        "public_action_state": state.model_dump(mode="json"),
        "response_grammar": _model_visible_grammar(exact_grammar),
    }
    return _render_prompt(
        "Return exactly one Stage 1 semantic proposal JSON object and no wrapper.",
        payload,
        ceiling=MAXIMUM_PRIMARY_PROMPT_UTF8_BYTES,
    )


def render_exact_semantic_proposal_rescue_prompt(
    source_prompt: str,
    *,
    failure_family: str,
    failure_subtype: str,
) -> str:
    source = _prompt_payload(source_prompt, expected_phase="primary")
    state = PublicActionState.model_validate(source["public_action_state"])
    grammar = _grammar_from_model_visible(source["response_grammar"])
    payload = {
        "prompt_protocol": EXACT_RESCUE_PROMPT_VERSION,
        "public_action_state_projection": _rescue_public_state_projection(state),
        "typed_failure": {"family": failure_family, "subtype": failure_subtype},
        "response_grammar": _model_visible_grammar(grammar),
        "previous_public_response_reused": False,
        "private_reasoning_reused": False,
    }
    return _render_prompt(
        "Return exactly one corrected Stage 1 semantic proposal JSON object and no wrapper.",
        payload,
        ceiling=MAXIMUM_RESCUE_PROMPT_UTF8_BYTES,
    )


def _rescue_public_state_projection(state: PublicActionState) -> dict[str, Any]:
    """Retain every currently selectable semantic affordance without wire details."""

    return {
        "state_id": state.state_id,
        "unresolved_symbols": list(state.unresolved_symbols),
        "variable_affordances": [
            item.model_dump(mode="json") for item in state.variable_affordances
        ],
        "ready_operations": [item.model_dump(mode="json") for item in state.ready_operations],
        "bounded_failure_history": [
            item.model_dump(mode="json") for item in state.bounded_failure_history
        ],
        "terminal_operation_ref": state.terminal_operation_ref,
        "terminal_verification_completed": state.terminal_verification_completed,
        "verification_tool_ids": [
            item.tool_id for item in state.tool_grammars if item.semantic_role == "verify"
        ],
        "selected_evidence_ids": list(state.selected_evidence_ids),
        "final_answer_allowed": state.final_answer_allowed,
        "semantic_choice_still_model_owned": True,
    }


def _prompt_payload(
    prompt: str, *, expected_phase: Literal["primary", "rescue"]
) -> Mapping[str, Any]:
    prefix, separator, raw = prompt.partition("\n")
    expected_prefix = (
        "Return exactly one Stage 1 semantic proposal JSON object and no wrapper."
        if expected_phase == "primary"
        else "Return exactly one corrected Stage 1 semantic proposal JSON object and no wrapper."
    )
    if prefix != expected_prefix or not separator:
        raise ValueError("exact response Grammar Prompt envelope changed")
    payload = json.loads(raw)
    if not isinstance(payload, Mapping):
        raise ValueError("exact response Grammar Prompt payload is not an object")
    expected_protocol = (
        EXACT_PRIMARY_PROMPT_VERSION if expected_phase == "primary" else EXACT_RESCUE_PROMPT_VERSION
    )
    if payload.get("prompt_protocol") != expected_protocol:
        raise ValueError("exact response Grammar Prompt protocol changed")
    return payload


def public_action_state_from_exact_prompt(prompt: str) -> PublicActionState:
    source = _prompt_payload(prompt, expected_phase="primary")
    _grammar_from_model_visible(source["response_grammar"])
    return PublicActionState.model_validate(source["public_action_state"])


def _grammar_from_model_visible(value: Any) -> StageOneResponseGrammarArtifact:
    if not isinstance(value, Mapping):
        raise ValueError("model-visible response Grammar is not an object")
    fields = tuple(value["fields"])
    field_types = tuple(value["types_aligned_to_fields"])
    defaults = tuple(value["defaults_aligned_to_fields"])
    if fields != FIELD_ORDER or len(field_types) != 10 or len(defaults) != 10:
        raise ValueError("model-visible field Grammar is malformed")
    columns = tuple(value["rule_columns"])
    if columns != (
        "decision_kind",
        "non_null",
        "null",
        "non_empty",
        "empty",
    ):
        raise ValueError("model-visible conditional rule columns changed")
    if tuple(value["shape_rules"]) != (
        "exactly_these_ten_top_level_fields",
        "exactly_one_json_object",
        "no_wrapper",
        "no_extra_fields",
        "field_order_not_semantic",
    ) or tuple(value["host_rules"]) != (
        "no_alias_normalization",
        "no_missing_field_insertion",
        "no_semantic_field_selection",
    ):
        raise ValueError("model-visible shape or Host rules changed")
    # Decode the registered aligned wire columns, not an Evidence domain field.
    # FIELD_ORDER is checked above; its first/last columns are stage/protocol.
    stage_constant, *_, response_protocol = defaults
    skeleton = dict(zip(fields, defaults, strict=True))
    artifact = StageOneResponseGrammarArtifact(
        grammar_id=str(value["id"]),
        response_protocol=response_protocol,
        stage_constant=stage_constant,
        field_order=fields,
        state_id_rule=value["state_id_rule"],
        fields=tuple(
            ResponseFieldGrammar(
                name=name,
                json_type=tuple(field_type.split("|")),
                default_when_not_applicable=default,
            )
            for name, field_type, default in zip(fields, field_types, defaults, strict=True)
        ),
        decision_rules=tuple(
            DecisionKindGrammar(
                decision_kind=item[0],
                required_non_null=tuple(item[1]),
                required_null=tuple(item[2]),
                required_non_empty=tuple(item[3]),
                required_empty=tuple(item[4]),
            )
            for item in value["rules"]
        ),
        json_skeleton=skeleton,
    )
    if value["private_reasoning_content"] != "not_allowed":
        raise ValueError("model-visible private-reasoning rule changed")
    if artifact != compile_stage_one_response_grammar():
        raise ValueError("model-visible response Grammar differs from the strong Schema")
    return artifact


def exact_semantic_proposal_payload(
    proposal: SemanticDecisionProposal,
) -> dict[str, Any]:
    return {
        "stage": EXACT_STAGE,
        "state_id": proposal.state_id,
        "decision_kind": proposal.decision_kind,
        "tool_id": proposal.tool_id,
        "node_id": proposal.node_id,
        "operator_id": proposal.operator_id,
        "operand_sources": list(proposal.operand_sources),
        "direct_arguments": proposal.direct_arguments,
        "evidence_ids": list(proposal.evidence_ids),
        "protocol": EXACT_RESPONSE_PROTOCOL_VERSION,
    }


def parse_exact_semantic_proposal_payload(
    payload: Mapping[str, Any],
    *,
    expected_state: PublicActionState | None = None,
    expected_state_id: str | None = None,
) -> SemanticDecisionProposal:
    if (expected_state is None) == (expected_state_id is None):
        raise ValueError("exactly one expected public-state binding is required")
    try:
        parsed = ExactStageOneSemanticProposalPayload.model_validate(payload)
    except ValidationError as exc:
        raise ExactResponseModelRejection(
            ProspectiveFailureClassification(
                family="response_serialization_failure",
                subtype="semantic_proposal_not_exact_response_grammar",
            )
        ) from exc
    bound_state_id = expected_state.state_id if expected_state is not None else expected_state_id
    if parsed.state_id != bound_state_id:
        raise ExactResponseModelRejection(
            ProspectiveFailureClassification(
                family="semantic_tool_argument_failure",
                subtype="semantic_proposal_binds_wrong_public_state",
            )
        )
    return make_semantic_decision_proposal(
        state_id=parsed.state_id,
        decision_kind=parsed.decision_kind,
        tool_id=parsed.tool_id,
        node_id=parsed.node_id,
        operator_id=parsed.operator_id,
        operand_sources=parsed.operand_sources,
        direct_arguments=parsed.direct_arguments,
        evidence_ids=parsed.evidence_ids,
    )


def prompt_only_reference_payload(prompt: str) -> dict[str, Any]:
    """Generate an accepted payload from the serialized public Prompt only."""

    phase: Literal["primary", "rescue"] = (
        "rescue" if prompt.startswith("Return exactly one corrected") else "primary"
    )
    source = _prompt_payload(prompt, expected_phase=phase)
    grammar = _grammar_from_model_visible(source["response_grammar"])
    if phase == "primary":
        state = PublicActionState.model_validate(source["public_action_state"])
        proposal = public_reference_policy_proposal(state)
    else:
        proposal = _reference_proposal_from_rescue_projection(
            source["public_action_state_projection"]
        )
    selected = exact_semantic_proposal_payload(proposal)
    payload = dict(grammar.json_skeleton)
    for field_name in grammar.field_order:
        payload[field_name] = selected[field_name]
    return payload


def parse_prompt_only_reference_payload(prompt: str) -> SemanticDecisionProposal:
    phase: Literal["primary", "rescue"] = (
        "rescue" if prompt.startswith("Return exactly one corrected") else "primary"
    )
    source = _prompt_payload(prompt, expected_phase=phase)
    if phase == "primary":
        state = PublicActionState.model_validate(source["public_action_state"])
        return parse_exact_semantic_proposal_payload(
            prompt_only_reference_payload(prompt), expected_state=state
        )
    projection = source["public_action_state_projection"]
    if not isinstance(projection, Mapping):
        raise ValueError("Rescue public-state projection is not an object")
    return parse_exact_semantic_proposal_payload(
        prompt_only_reference_payload(prompt),
        expected_state_id=str(projection["state_id"]),
    )


def _reference_proposal_from_rescue_projection(value: Any) -> SemanticDecisionProposal:
    if not isinstance(value, Mapping):
        raise ValueError("Rescue public-state projection is not an object")
    state_id = str(value["state_id"])
    unresolved = tuple(str(item) for item in value["unresolved_symbols"])
    variable_affordances = tuple(value["variable_affordances"])
    if unresolved:
        variable = next(item for item in variable_affordances if item["symbol"] == unresolved[0])
        record = variable["public_record"]
        refinement_requested = any(
            item["failed_tool_id"] == "query_structured_fact"
            and item["error_category"] == "typed_selector_requires_refinement"
            for item in value["bounded_failure_history"]
        )
        filter_fields = (
            (
                "source_id",
                "source_authority",
                "unit",
                "currency",
                "definition_id",
                "time_basis",
                "frequency",
                "subject_type",
            )
            if refinement_requested
            else ("source_id",)
        )
        return make_semantic_decision_proposal(
            state_id=state_id,
            decision_kind="acquire_public_input",
            tool_id="query_structured_fact",
            direct_arguments={
                "subject_alias": record.get("subject_name") or record.get("subject_id"),
                "metric_alias": record["metric"],
                "period_label": record["period"],
                "public_filters": {key: record[key] for key in filter_fields if key in record},
            },
        )
    executable = tuple(item for item in value["ready_operations"] if not item["unresolved_symbols"])
    if executable:
        operation = executable[0]
        return make_semantic_decision_proposal(
            state_id=state_id,
            decision_kind="execute_public_operation",
            tool_id=operation["tool_id"],
            node_id=operation["node_id"],
            operator_id=(
                operation["allowed_operator_ids"][0] if operation["allowed_operator_ids"] else None
            ),
            operand_sources=tuple(item["source_symbol"] for item in operation["operand_slots"]),
        )
    if value["terminal_operation_ref"] and not value["terminal_verification_completed"]:
        verification_tools = tuple(value["verification_tool_ids"])
        if len(verification_tools) != 1:
            raise ValueError("Rescue projection requires one public verification tool")
        return make_semantic_decision_proposal(
            state_id=state_id,
            decision_kind="verify_terminal_operation",
            tool_id=verification_tools[0],
            evidence_ids=tuple(value["selected_evidence_ids"]),
        )
    if value["final_answer_allowed"]:
        return make_semantic_decision_proposal(
            state_id=state_id,
            decision_kind="emit_final_answer",
        )
    raise ValueError("Rescue public-state projection has no constructible decision")
