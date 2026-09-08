"""Reason-length contract: exact C baseline, disclosed P parser and public schema.

No global parser monkeypatch. The transition body is the original numeric runtime
body with exactly one seam: condition-aware parse(raw, self.expression_condition).
"""

import hashlib
import json
from fractions import Fraction

from pydantic import ConfigDict, Field, ValidationError

from trusted_synthesis.domains.finance.qa_vnext.protocol import ProtocolError, record, require
from trusted_synthesis.experiments.finance_qa_vnext_finqa_difficulty.runtime import (
    Action,
    Final,
    Update,
    _pairs,
)
from trusted_synthesis.experiments.finance_qa_vnext_finqa_difficulty.semantics import (
    CONSTANTS,
    TOOLS,
    calculate,
    decimal,
    equivalent,
    evaluate,
    lineage,
)
from trusted_synthesis.experiments.finance_qa_vnext_finqa_final_recovery.runtime import (
    FinalRecoveryRuntime,
    verify_feedback,
)

VERSION = "finqa_reason_length_decoupling.v1"
P_PROTOCOL_VERSION = "finqa_source_numeric_h2.v2.2.reason_policy"
P_REASON_RULE = (
    "Keep Action reason concise and nonempty; there is no per-reason character cap. "
    "Existing response-size and session resource limits still apply. "
    "subgoal: at most 240 characters."
)


class ResourceBoundedReasonAction(Action):
    model_config = ConfigDict(extra="forbid", strict=True, title="Action")
    reason: str = Field(min_length=1)


def action_schema(expression_condition):
    require(expression_condition in {"C", "P"}, "reason_policy.condition")
    return Action if expression_condition == "C" else ResourceBoundedReasonAction


def decode(raw):
    """Same duplicate-key/object contract; non-JSON constants are not valid JSON."""

    def invalid_constant(_):
        raise ValueError("schema.invalid_submission")

    try:
        value = json.loads(raw, object_pairs_hook=_pairs, parse_constant=invalid_constant)
        require(isinstance(value, dict), "schema.object")
        return value
    except (json.JSONDecodeError, UnicodeError) as error:
        raise ValueError("schema.invalid_submission") from error


def parse(raw, expression_condition):
    value = decode(raw)
    cls = {"action": action_schema(expression_condition), "update": Update, "final": Final}.get(
        value.get("kind")
    )
    require(cls is not None, "schema.kind")
    try:
        return cls.model_validate(value).model_dump(mode="json")
    except ValidationError as error:
        raise ValueError("schema.invalid_submission") from error


def verify_reason_policy(request, expression_condition):
    require(
        request["response_schemas"]["action"]
        == action_schema(expression_condition).model_json_schema(),
        "audit.reason_schema_matches_parser",
    )
    if expression_condition == "P":
        require(request["rules"]["reason_limit"] == P_REASON_RULE, "audit.P_reason_rule")
        require(request["protocol"]["version"] == P_PROTOCOL_VERSION, "audit.P_protocol_version")
    else:
        require(
            request["rules"]["reason_limit"]
            == "Action reason: at most 480 characters; subgoal: at most 240 characters.",
            "audit.C_reason_rule",
        )
        require(
            request["protocol"]["version"] == "finqa_source_numeric_h2.v2.1",
            "audit.C_protocol_version",
        )
    verify_feedback(request, "R")


class ReasonPolicyRuntime(FinalRecoveryRuntime):
    def __init__(self, *args, expression_condition, **kwargs):
        action_schema(expression_condition)
        self.expression_condition = expression_condition
        super().__init__(*args, feedback_condition="R", **kwargs)
        if expression_condition == "P":
            self.protocol = record(
                "protocol",
                version=P_PROTOCOL_VERSION,
                **{
                    k: v
                    for k, v in self.protocol.items()
                    if k not in {"id", "schema_version", "version"}
                },
            )

    def request(self):
        request = super().request()
        if self.expression_condition == "P":
            request["response_schemas"]["action"] = ResourceBoundedReasonAction.model_json_schema()
            request["rules"]["reason_limit"] = P_REASON_RULE
            return record(
                "public_request",
                **{k: v for k, v in request.items() if k not in {"id", "schema_version"}},
            )
        return request

    def transition(self, raw, request):
        require(request == self.request(), "integrity.current_request_binding")
        require(not self.terminal and self.submissions < 32, "lifecycle.closed")
        before = request["state"]["id"]
        submitted, error, observation, claim = None, None, None, None
        try:
            submitted = parse(raw, self.expression_condition)
            require(submitted["state_id"] == before, "lifecycle.state_binding")
            if self.pending is not None:
                require(submitted["kind"] == "update", "lifecycle.pending_requires_update")
            if submitted["kind"] == "action":
                require(self.actions < 12, "resource.action_budget")
                op, inputs = submitted["operation"], submitted["inputs"]
                require(op in TOOLS, "numeric.unsupported_operation")
                require(submitted["parameters"] == {}, "numeric.parameters")
                required = 1 if op in {"read", "absolute"} else 2
                require(
                    len(inputs) == required
                    if op in {"read", "absolute", "add", "subtract", "multiply", "divide"}
                    else 2 <= len(inputs) <= 8,
                    "numeric.arity",
                )
                accepted = {c["id"]: c for c in self.claims}
                if op == "read":
                    require(inputs[0] in self.allowed_sources, "source.visible_numeric_id")
                    tree = inputs[0]
                    value = evaluate(tree, self.task["facts"])
                else:
                    trees, values = [], []
                    for ref in inputs:
                        if ref in {"constant:" + v for v in CONSTANTS}:
                            trees.append(ref)
                            values.append(Fraction(ref.split(":")[1]))
                        else:
                            require(ref in accepted, "lifecycle.accepted_claim_input_only")
                            trees.append(accepted[ref]["expression"])
                            values.append(Fraction(accepted[ref]["exact_value"]))
                    tree = {"op": op, "args": trees}
                    value = calculate(op, values)
                # An independent recursive source evaluation verifies the actual result.
                require(
                    value == evaluate(tree, self.task["facts"]), "integrity.execution_verification"
                )
                require(
                    len(str(value.numerator)) <= 4096 and len(str(value.denominator)) <= 4096,
                    "resource.numeric_size",
                )
                observation = record(
                    "observation",
                    session_id=self.session_id,
                    context_id=self.context["id"],
                    request_id=request["id"],
                    action_ordinal=self.actions + 1,
                    model_action=submitted,
                    expression=tree,
                    exact_value=str(value),
                    value=decimal(value),
                    lineage=sorted(lineage(tree)),
                    claim_type="numeric_derivation",
                    numeric_and_source_verified=True,
                    financial_target_certified=False,
                )
                self.pending = observation
                self.actions += 1
            elif submitted["kind"] == "update":
                require(self.pending is not None, "lifecycle.no_pending_observation")
                require(
                    submitted["observation"] == self.pending["id"], "lifecycle.observation_binding"
                )
                if submitted["disposition"] == "accept":
                    claim = record(
                        "claim",
                        session_id=self.session_id,
                        observation_id=self.pending["id"],
                        accepted_by_request_id=request["id"],
                        status="accepted",
                        **{
                            k: self.pending[k]
                            for k in (
                                "expression",
                                "exact_value",
                                "value",
                                "lineage",
                                "claim_type",
                                "financial_target_certified",
                            )
                        },
                    )
                    self.claims.append(claim)
                self.pending = None
            else:
                accepted = {c["id"]: c for c in self.claims}
                require(submitted["answer_claim"] in accepted, "final.accepted_answer_required")
                answer = accepted[submitted["answer_claim"]]
                require(set(submitted["result"]) == {"value", "unit"}, "final.result_schema")
                require(submitted["result"]["unit"] == self.task["unit"], "final.unit")
                require(len(submitted["result"]["value"]) <= 256, "final.value_length")
                require(
                    abs(Fraction(submitted["result"]["value"]) - Fraction(answer["exact_value"]))
                    <= Fraction("0.00001"),
                    "final.unexecuted_value_change",
                )
                require(
                    len(submitted["citations"]) == len(set(submitted["citations"]))
                    and set(submitted["citations"]) == set(answer["lineage"]),
                    "final.citations",
                )
                require(
                    equivalent(
                        answer["expression"],
                        self.task["target"],
                        self.task["facts"],
                        self.task["relations"],
                    ),
                    "final.target_not_established",
                )
                require(
                    Fraction(answer["exact_value"])
                    == evaluate(self.task["target"], self.task["facts"]),
                    "integrity.final_arithmetic",
                )
                self.terminal = True
        except (ProtocolError, ValueError, TypeError, KeyError, ZeroDivisionError) as exc:
            error = (
                str(exc)
                if isinstance(exc, (ProtocolError, ValueError))
                else "submission.invalid_reference_or_value"
            )
            # Do not reveal interpreter internals or private task oracle values.
            if not error.startswith(
                (
                    "schema.",
                    "numeric.",
                    "lifecycle.",
                    "source.",
                    "final.",
                    "resource.",
                    "integrity.",
                )
            ):
                error = "schema.invalid_submission"
        self.submissions += 1
        self.feedback = error
        event = record(
            "transition",
            request_id=request["id"],
            before_state_id=before,
            raw_sha256=hashlib.sha256(raw).hexdigest(),
            model_submission=submitted,
            admitted=error is None,
            error=error,
            observation=observation,
            claim=claim,
            terminal=self.terminal,
            action_count=self.actions,
            submission_count=self.submissions,
            system_binding={
                "session_id": self.session_id,
                "context_id": self.context["id"],
                "semantic_fields_filled": False,
                "raw_response_rewritten": False,
            },
        )
        self.events.append(event)
        return event
