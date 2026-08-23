from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from itertools import combinations
from typing import Any, Final, Literal, cast

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from trusted_synthesis.hashing import canonical_hash
from trusted_synthesis.runtime.agent.prospective_semantic_action_protocol import (
    CANONICAL_ACTION_VERSION,
    SEMANTIC_ACTION_PROTOCOL_VERSION,
    CanonicalActionProposal,
    CanonicalPublicAction,
    DecisionKind,
    SemanticActionState,
    make_canonical_action_proposal,
    prompt_only_reference_proposal,
    render_semantic_action_prompt,
)

RESPONSE_PROTOCOL_VERSION: Final = "prospective_semantic_action_exact_response.v1"
RESPONSE_GRAMMAR_VERSION: Final = "prospective_semantic_action_response_grammar.v1"
PRIMARY_PROMPT_VERSION: Final = "prospective_semantic_action_primary_prompt.v1"
ABI_RESCUE_PROMPT_VERSION: Final = "prospective_semantic_action_abi_rescue_prompt.v1"
SEMANTIC_RECOVERY_PROMPT_VERSION: Final = "prospective_semantic_action_semantic_recovery_prompt.v1"
MAXIMUM_PROMPT_UTF8_BYTES: Final = 60_000
FIELD_ORDER: Final = ("state_id", "action_id", "decision_kind", "protocol")


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class ExactCanonicalActionPayload(FrozenModel):
    state_id: str = Field(min_length=1)
    action_id: str = Field(min_length=1)
    decision_kind: DecisionKind
    protocol: Literal["prospective_semantic_action_exact_response.v1"] = RESPONSE_PROTOCOL_VERSION

    @model_validator(mode="before")
    @classmethod
    def validate_exact_shape(cls, value: Any) -> Any:
        if not isinstance(value, Mapping) or set(value) != set(FIELD_ORDER):
            raise ValueError("semantic action response requires exactly four top-level fields")
        return value


class ResponseFieldGrammar(FrozenModel):
    name: str = Field(min_length=1)
    json_type: Literal["string"] = "string"
    always_present: Literal[True] = True


class SemanticActionResponseGrammar(FrozenModel):
    grammar_id: str = Field(min_length=1)
    response_protocol: Literal["prospective_semantic_action_exact_response.v1"] = (
        RESPONSE_PROTOCOL_VERSION
    )
    semantic_action_protocol: Literal["prospective_semantic_action_selection.v1"] = (
        SEMANTIC_ACTION_PROTOCOL_VERSION
    )
    field_order: tuple[str, str, str, str] = FIELD_ORDER
    fields: tuple[ResponseFieldGrammar, ...] = Field(min_length=4, max_length=4)
    exact_top_level_field_set_required: Literal[True] = True
    extra_fields_allowed: Literal[False] = False
    wrapper_allowed: Literal[False] = False
    exactly_one_object_required: Literal[True] = True
    fixed_stage_is_host_bound_metadata: Literal[True] = True
    model_generates_stage_metadata: Literal[False] = False
    state_id_rule: Literal["copy_current_state_id"] = "copy_current_state_id"
    action_id_rule: Literal["select_one_visible_action_id"] = "select_one_visible_action_id"
    decision_kind_rule: Literal["copy_selected_action_decision_kind"] = (
        "copy_selected_action_decision_kind"
    )
    host_alias_normalization_allowed: Literal[False] = False
    host_missing_semantic_field_insertion_allowed: Literal[False] = False
    host_action_selection_allowed: Literal[False] = False
    private_reasoning_content_allowed: Literal[False] = False
    schema_version: Literal["prospective_semantic_action_response_grammar.v1"] = (
        RESPONSE_GRAMMAR_VERSION
    )

    @model_validator(mode="after")
    def validate_grammar(self) -> SemanticActionResponseGrammar:
        if tuple(item.name for item in self.fields) != FIELD_ORDER:
            raise ValueError("four-field response Grammar diverged from its strong Schema")
        if self.grammar_id != response_grammar_id(self):
            raise ValueError("semantic action response-Grammar identity changed")
        return self


class SemanticActionResponseRejection(ValueError):
    def __init__(self, *, family: str, subtype: str) -> None:
        super().__init__(subtype)
        self.family = family
        self.subtype = subtype


def response_grammar_id(value: SemanticActionResponseGrammar) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"grammar_id"}),
        prefix="prospective_semantic_action_response_grammar:",
    )


def compile_semantic_action_response_grammar() -> SemanticActionResponseGrammar:
    if tuple(ExactCanonicalActionPayload.model_fields) != FIELD_ORDER:
        raise ValueError("strong four-field response Schema changed")
    values = {"fields": tuple(ResponseFieldGrammar(name=name) for name in FIELD_ORDER)}
    provisional = SemanticActionResponseGrammar.model_construct(grammar_id="pending", **values)
    return SemanticActionResponseGrammar(
        grammar_id=response_grammar_id(provisional),
        **values,
    )


def _make_action(**values: Any) -> CanonicalPublicAction:
    provisional = CanonicalPublicAction.model_construct(action_id="pending", **values)
    return CanonicalPublicAction(
        action_id=canonical_hash(
            provisional.model_dump(mode="json", exclude={"action_id"}),
            prefix="prospective_canonical_public_action:",
        ),
        **values,
    )


def independently_enumerate_visible_actions(
    state: SemanticActionState,
) -> tuple[CanonicalPublicAction, ...]:
    """Rebuild the selectable action set from public state fields, not its candidate list."""

    grammar_ids = {item.tool_id for item in state.tool_grammars}
    unresolved = set(state.unresolved_symbols)
    actions: dict[str, CanonicalPublicAction] = {}
    for affordance in state.variable_affordances:
        if affordance.symbol not in unresolved:
            continue
        if "search_archive" in grammar_ids:
            action = _make_action(
                decision_kind="acquire_public_input",
                tool_id="search_archive",
                target_source_symbols=(affordance.symbol,),
                acquisition_mode="search_public_record",
                acquisition_record=dict(affordance.public_record),
                wire_argument_fields=(
                    "limit",
                    "period_labels",
                    "query",
                    "source_filters",
                    "subject_aliases",
                ),
            )
            actions[action.action_id] = action
        if "query_structured_fact" in affordance.acquisition_tool_ids:
            for mode in ("query_source_scoped", "query_fully_qualified"):
                action = _make_action(
                    decision_kind="acquire_public_input",
                    tool_id="query_structured_fact",
                    target_source_symbols=(affordance.symbol,),
                    acquisition_mode=mode,
                    acquisition_record=dict(affordance.public_record),
                    wire_argument_fields=(
                        "metric_alias",
                        "period_label",
                        "public_filters",
                        "subject_alias",
                    ),
                )
                actions[action.action_id] = action
        if "open_document" in affordance.acquisition_tool_ids:
            for document in state.document_references:
                if affordance.symbol not in document.matching_source_symbols:
                    continue
                action = _make_action(
                    decision_kind="acquire_public_input",
                    tool_id="open_document",
                    target_source_symbols=(affordance.symbol,),
                    acquisition_mode="open_public_document",
                    document_reference_id=document.reference_id,
                    wire_argument_fields=("public_locator",),
                )
                actions[action.action_id] = action
    for frontier in state.operation_frontier:
        if frontier.frontier_status != "executable":
            continue
        operators: tuple[str | None, ...] = (
            tuple(frontier.allowed_operator_ids) if frontier.allowed_operator_ids else (None,)
        )
        for operator_id in operators:
            action = _make_action(
                decision_kind="execute_public_operation",
                tool_id=frontier.tool_id,
                node_id=frontier.node_id,
                operator_id=operator_id,
                source_reference_ids=frontier.source_reference_ids,
                wire_argument_fields=(
                    ("evidence_ids", "target_definition")
                    if frontier.node_kind == "normalization"
                    else ("operands", "operator", "parameters")
                ),
            )
            actions[action.action_id] = action
    terminal_verifiable = any(
        item.frontier_status == "terminal_verifiable" for item in state.operation_frontier
    )
    evidence_references = tuple(
        sorted(
            (item for item in state.source_references if item.reference_kind == "public_evidence"),
            key=lambda item: str(item.evidence_id),
        )
    )
    if terminal_verifiable:
        if len(evidence_references) > 8:
            raise ValueError("independent verification candidate set exceeds its static bound")
        verification_tools = tuple(
            item.tool_id for item in state.tool_grammars if item.semantic_role == "verify"
        )
        if len(verification_tools) != 1:
            raise ValueError("independent candidate audit requires one verification Tool")
        for count in range(1, len(evidence_references) + 1):
            for selected in combinations(evidence_references, count):
                action = _make_action(
                    decision_kind="verify_terminal_operation",
                    tool_id=verification_tools[0],
                    evidence_reference_ids=tuple(item.reference_id for item in selected),
                    wire_argument_fields=("claim_or_result", "evidence_ids"),
                )
                actions[action.action_id] = action
    if state.final_answer_allowed:
        action = _make_action(decision_kind="emit_final_answer")
        actions[action.action_id] = action
    blocked = {item.action_id for item in state.blocked_actions}
    return tuple(actions[key] for key in sorted(actions) if key not in blocked)


def validate_candidate_space_completeness(state: SemanticActionState) -> None:
    observed = tuple(item.model_dump(mode="json") for item in state.action_candidates)
    expected = tuple(
        item.model_dump(mode="json") for item in independently_enumerate_visible_actions(state)
    )
    if observed != expected:
        raise ValueError("visible candidate set is not the complete public legal-action set")


def _model_visible_grammar(grammar: SemanticActionResponseGrammar) -> dict[str, Any]:
    return {
        "id": grammar.grammar_id,
        "fields": list(grammar.field_order),
        "types": [item.json_type for item in grammar.fields],
        "shape_rules": [
            "exactly_one_json_object",
            "exactly_four_top_level_fields",
            "no_wrapper",
            "no_extra_fields",
            "field_order_not_semantic",
        ],
        "state_id_rule": grammar.state_id_rule,
        "action_id_rule": grammar.action_id_rule,
        "decision_kind_rule": grammar.decision_kind_rule,
        "protocol_constant": grammar.response_protocol,
        "fixed_stage": "host_bound_not_model_generated",
        "host_rules": [
            "no_alias_normalization",
            "no_missing_semantic_field_insertion",
            "no_action_selection",
        ],
        "private_reasoning_content": "not_allowed",
    }


def _presentation_order(
    candidates: Sequence[CanonicalPublicAction], presentation_salt: str
) -> tuple[CanonicalPublicAction, ...]:
    if not presentation_salt:
        raise ValueError("candidate presentation salt must be non-empty")
    return tuple(
        sorted(
            candidates,
            key=lambda item: hashlib.sha256(
                f"{presentation_salt}|{item.action_id}".encode()
            ).hexdigest(),
        )
    )


def _state_projection(state: SemanticActionState) -> dict[str, Any]:
    return state.model_dump(mode="json", exclude={"action_candidates"})


def _render(
    *,
    phase: Literal["primary", "abi_rescue", "semantic_recovery"],
    instruction: str,
    state: SemanticActionState,
    public_path_condition: str | None,
    presentation_salt: str,
    typed_failure: Mapping[str, Any] | None,
    grammar: SemanticActionResponseGrammar,
) -> str:
    validate_candidate_space_completeness(state)
    candidates = _presentation_order(state.action_candidates, presentation_salt)
    prompt_protocol = {
        "primary": PRIMARY_PROMPT_VERSION,
        "abi_rescue": ABI_RESCUE_PROMPT_VERSION,
        "semantic_recovery": SEMANTIC_RECOVERY_PROMPT_VERSION,
    }[phase]
    payload = {
        "prompt_protocol": prompt_protocol,
        "semantic_action_protocol": SEMANTIC_ACTION_PROTOCOL_VERSION,
        "instruction": instruction,
        "public_path_condition": public_path_condition,
        "public_state_without_candidate_order": _state_projection(state),
        "visible_action_candidates": [item.model_dump(mode="json") for item in candidates],
        "candidate_presentation": {
            "order_is_semantically_neutral": True,
            "presentation_salt_sha256": hashlib.sha256(
                presentation_salt.encode("utf-8")
            ).hexdigest(),
        },
        "typed_failure": dict(typed_failure) if typed_failure is not None else None,
        "response_grammar": _model_visible_grammar(grammar),
        "previous_response_content_reused": False,
        "private_reasoning_reused": False,
    }
    prefix = {
        "primary": "Select one visible action and return exactly one four-field JSON object.",
        "abi_rescue": (
            "Correct only the response ABI and return exactly one four-field JSON object."
        ),
        "semantic_recovery": (
            "Use the public rejection and select one visible action as a four-field JSON object."
        ),
    }[phase]
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
    if len(prompt.encode("utf-8")) > MAXIMUM_PROMPT_UTF8_BYTES:
        raise ValueError("semantic action response Prompt exceeds its frozen byte ceiling")
    return prompt


def render_exact_canonical_action_prompt(
    *,
    instruction: str,
    state: SemanticActionState,
    public_path_condition: str | None,
    presentation_salt: str,
    grammar: SemanticActionResponseGrammar | None = None,
) -> str:
    return _render(
        phase="primary",
        instruction=instruction,
        state=state,
        public_path_condition=public_path_condition,
        presentation_salt=presentation_salt,
        typed_failure=None,
        grammar=grammar or compile_semantic_action_response_grammar(),
    )


def render_exact_canonical_action_abi_rescue_prompt(
    source_prompt: str,
    *,
    failure_family: str,
    failure_subtype: str,
) -> str:
    source = semantic_action_state_from_response_prompt(source_prompt)
    instruction, condition, salt = _prompt_context(source_prompt)
    return _render(
        phase="abi_rescue",
        instruction=instruction,
        state=source,
        public_path_condition=condition,
        presentation_salt=salt,
        typed_failure={"family": failure_family, "subtype": failure_subtype},
        grammar=compile_semantic_action_response_grammar(),
    )


def render_exact_canonical_action_semantic_recovery_prompt(
    *,
    instruction: str,
    state: SemanticActionState,
    public_path_condition: str | None,
    presentation_salt: str,
) -> str:
    if not state.semantic_rejections:
        raise ValueError("semantic recovery Prompt lacks a public semantic rejection")
    rejection = state.semantic_rejections[-1]
    return _render(
        phase="semantic_recovery",
        instruction=instruction,
        state=state,
        public_path_condition=public_path_condition,
        presentation_salt=presentation_salt,
        typed_failure={
            "family": "semantic_action_rejection",
            "subtype": rejection.error_category,
            "rejection_id": rejection.rejection_id,
        },
        grammar=compile_semantic_action_response_grammar(),
    )


def _phase(prompt: str) -> Literal["primary", "abi_rescue", "semantic_recovery"]:
    prefix = prompt.partition("\n")[0]
    values = {
        "Select one visible action and return exactly one four-field JSON object.": "primary",
        "Correct only the response ABI and return exactly one four-field JSON object.": (
            "abi_rescue"
        ),
        "Use the public rejection and select one visible action as a four-field JSON object.": (
            "semantic_recovery"
        ),
    }
    try:
        return cast(
            Literal["primary", "abi_rescue", "semantic_recovery"],
            values[prefix],
        )
    except KeyError as exc:
        raise ValueError("semantic action response Prompt envelope changed") from exc


def _payload(prompt: str) -> Mapping[str, Any]:
    phase = _phase(prompt)
    _, separator, raw = prompt.partition("\n")
    if not separator:
        raise ValueError("semantic action response Prompt lacks its payload")
    payload = json.loads(raw)
    if not isinstance(payload, Mapping):
        raise ValueError("semantic action response Prompt payload is not an object")
    expected = {
        "primary": PRIMARY_PROMPT_VERSION,
        "abi_rescue": ABI_RESCUE_PROMPT_VERSION,
        "semantic_recovery": SEMANTIC_RECOVERY_PROMPT_VERSION,
    }[phase]
    if payload.get("prompt_protocol") != expected:
        raise ValueError("semantic action response Prompt protocol changed")
    _grammar_from_visible(payload.get("response_grammar"))
    return payload


def _grammar_from_visible(value: Any) -> SemanticActionResponseGrammar:
    if not isinstance(value, Mapping):
        raise ValueError("model-visible four-field Grammar is not an object")
    expected = _model_visible_grammar(compile_semantic_action_response_grammar())
    if dict(value) != expected:
        raise ValueError("model-visible four-field Grammar changed")
    return compile_semantic_action_response_grammar()


def semantic_action_state_from_response_prompt(prompt: str) -> SemanticActionState:
    payload = _payload(prompt)
    raw_state = payload.get("public_state_without_candidate_order")
    raw_candidates = payload.get("visible_action_candidates")
    if (
        not isinstance(raw_state, Mapping)
        or not isinstance(raw_candidates, Sequence)
        or isinstance(raw_candidates, (str, bytes))
    ):
        raise ValueError("semantic action response Prompt omits state or candidates")
    candidates = tuple(
        sorted(
            (CanonicalPublicAction.model_validate(item) for item in raw_candidates),
            key=lambda item: item.action_id,
        )
    )
    state = SemanticActionState.model_validate(
        {
            **dict(raw_state),
            "action_candidates": [item.model_dump(mode="json") for item in candidates],
        }
    )
    validate_candidate_space_completeness(state)
    if len(candidates) != len(raw_candidates):
        raise ValueError("candidate presentation contains duplicates")
    return state


def _prompt_context(prompt: str) -> tuple[str, str | None, str]:
    payload = _payload(prompt)
    instruction = payload.get("instruction")
    condition = payload.get("public_path_condition")
    presentation = payload.get("candidate_presentation")
    if (
        not isinstance(instruction, str)
        or (condition is not None and not isinstance(condition, str))
        or not isinstance(presentation, Mapping)
    ):
        raise ValueError("semantic action response Prompt context is malformed")
    digest = presentation.get("presentation_salt_sha256")
    if not isinstance(digest, str) or len(digest) != 64:
        raise ValueError("candidate presentation commitment is malformed")
    return instruction, condition, digest


def exact_canonical_action_payload(proposal: CanonicalActionProposal) -> dict[str, Any]:
    return {
        "state_id": proposal.state_id,
        "action_id": proposal.action_id,
        "decision_kind": proposal.decision_kind,
        "protocol": RESPONSE_PROTOCOL_VERSION,
    }


def parse_exact_canonical_action_payload(payload: Mapping[str, Any]) -> CanonicalActionProposal:
    try:
        parsed = ExactCanonicalActionPayload.model_validate(payload)
    except ValidationError as exc:
        raise SemanticActionResponseRejection(
            family="response_serialization_failure",
            subtype="canonical_action_not_exact_four_field_grammar",
        ) from exc
    return make_canonical_action_proposal(
        state_id=parsed.state_id,
        action_id=parsed.action_id,
        decision_kind=parsed.decision_kind,
    )


def prompt_only_reference_payload(prompt: str) -> dict[str, Any]:
    payload = _payload(prompt)
    state = semantic_action_state_from_response_prompt(prompt)
    instruction = payload.get("instruction")
    condition = payload.get("public_path_condition")
    if not isinstance(instruction, str) or (
        condition is not None and not isinstance(condition, str)
    ):
        raise ValueError("Prompt-only reference lacks public context")
    semantic_prompt = render_semantic_action_prompt(
        instruction=instruction,
        state=state,
        public_path_condition=condition,
    )
    proposal = prompt_only_reference_proposal(semantic_prompt)
    return exact_canonical_action_payload(proposal)


def parse_prompt_only_reference_payload(prompt: str) -> CanonicalActionProposal:
    state = semantic_action_state_from_response_prompt(prompt)
    proposal = parse_exact_canonical_action_payload(prompt_only_reference_payload(prompt))
    if proposal.state_id != state.state_id:
        raise ValueError("Prompt-only response does not bind the visible public state")
    if proposal.action_id not in {item.action_id for item in state.action_candidates}:
        raise ValueError("Prompt-only response selects an invisible action")
    return proposal


def candidate_prompt_utf8_bytes(prompt: str) -> int:
    payload = _payload(prompt)
    candidates = payload.get("visible_action_candidates")
    return len(
        json.dumps(
            candidates,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    )


def opaque_action_id(action_id: str, *, salt: str) -> str:
    digest = hashlib.sha256(f"{salt}|{action_id}".encode()).hexdigest()
    if len(action_id) < len(digest):
        raise ValueError("canonical action ID is shorter than its opaque digest")
    return "x" * (len(action_id) - len(digest)) + digest


def assert_action_id_shape(action_id: str) -> None:
    prefix = "prospective_canonical_public_action:"
    if (
        not action_id.startswith(prefix)
        or len(action_id) != len(prefix) + 64
        or any(character not in "0123456789abcdef" for character in action_id[len(prefix) :])
    ):
        raise ValueError("canonical action ID is not a uniform opaque content address")
    if CANONICAL_ACTION_VERSION != "prospective_canonical_public_action.v1":
        raise ValueError("canonical action version changed")
