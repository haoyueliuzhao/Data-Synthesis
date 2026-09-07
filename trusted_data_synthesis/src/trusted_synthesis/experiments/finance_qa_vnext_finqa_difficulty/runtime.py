"""Compact v2 numeric-claim lifecycle, source selection and target-level Final QA."""

from __future__ import annotations

import copy
import hashlib
import json
from fractions import Fraction
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from trusted_synthesis.domains.finance.qa_vnext.protocol import ProtocolError, record, require
from trusted_synthesis.domains.finance.qa_vnext.runtime import DurableStore
from trusted_synthesis.experiments.finance_qa_vnext_model_execution.transport import (
    OnlineTransportError,
)

from .semantics import CONSTANTS, TOOLS, calculate, decimal, equivalent, evaluate, lineage

VERSION = "finqa_source_numeric_h2.v2"


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class Action(Strict):
    kind: Literal["action"]
    state_id: str
    subgoal: str = Field(min_length=1, max_length=240)
    reason: str = Field(min_length=1, max_length=480)
    operation: str
    inputs: list[str] = Field(min_length=1, max_length=8)
    parameters: dict[str, Any]


class Update(Strict):
    kind: Literal["update"]
    state_id: str
    observation: str
    disposition: Literal["accept", "reject"]


class Result(Strict):
    value: str = Field(
        max_length=256, pattern=r"^-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][+-]?[0-9]{1,3})?$"
    )
    unit: Literal["percent", "USD", "USD_million", "USD_thousand"]


class Final(Strict):
    kind: Literal["final"]
    state_id: str
    answer_claim: str
    result: Result
    citations: list[str] = Field(max_length=12)


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, "schema.duplicate_key")
        result[key] = value
    return result


def parse(raw):
    try:
        value = json.loads(raw, object_pairs_hook=_pairs)
        require(isinstance(value, dict), "schema.object")
        cls = {"action": Action, "update": Update, "final": Final}.get(value.get("kind"))
        require(cls is not None, "schema.kind")
        return cls.model_validate(value).model_dump(mode="json")
    except (ValidationError, json.JSONDecodeError, UnicodeError) as error:
        raise ValueError("schema.invalid_submission") from error


class Runtime:
    def __init__(
        self, panel, key, condition, session_id, callback=None, output_directory: Path | None = None
    ):
        self.task, self.context = panel.tasks[key], panel.public(key, condition)
        self.session_id, self.callback = session_id, callback
        self.store = DurableStore(output_directory) if output_directory is not None else None
        self.claims, self.pending = [], None
        self.submissions = self.actions = 0
        self.terminal, self.feedback = False, None
        self.events = []
        self.allowed_sources = {fact["id"] for fact in self.context["numeric_catalog"]}
        self.protocol = record(
            "protocol",
            version=VERSION,
            maximum_actions=12,
            maximum_submissions=32,
            operations=TOOLS,
            constants=["constant:" + v for v in CONSTANTS],
            claim_type="verified_numeric_derivation_not_financial_role_certification",
            action_admission_uses_reference_plan=False,
            final_semantics=(
                "source-symbolic equivalence and exact source arithmetic, "
                "numeric publication and unit/citations"
            ),
            automatic_execution_or_final_repair=False,
        )

    def request(self):
        state = record(
            "state",
            context_id=self.context["id"],
            protocol_id=self.protocol["id"],
            session_id=self.session_id,
            submission_count=self.submissions,
            action_count=self.actions,
            remaining_actions=12 - self.actions,
            remaining_submissions=32 - self.submissions,
            claims=copy.deepcopy(self.claims),
            pending_observation=copy.deepcopy(self.pending),
            terminal=self.terminal,
            feedback=self.feedback,
        )
        return record(
            "public_request",
            protocol_id=self.protocol["id"],
            protocol=self.protocol,
            context=self.context,
            state=state,
            response_schemas={
                "action": Action.model_json_schema(),
                "update": Update.model_json_schema(),
                "final": Final.model_json_schema(),
            },
            rules={
                "state_id": "Copy state.id exactly for every submission.",
                "actions": (
                    "Propose your own subgoal, operation and ordered inputs. No plan or "
                    "next-step candidates are supplied. parameters must be {}. All outputs "
                    "are scalar numeric derivations with source provenance; you must decide "
                    "financial relevance, periods, signs and scales."
                ),
                "pending": (
                    "Only Update accept/reject is legal while an observation is pending. A "
                    "read or computation is not usable until YOU accept it. Accepted claims "
                    "are immutable."
                ),
                "inputs": (
                    "read takes one source: ID from numeric_catalog. Other operations take "
                    "accepted Claim IDs or listed constant: IDs, never raw source IDs, bare "
                    "numbers, observations or subgoal names."
                ),
                "publication": (
                    "Final requires no pending observation and one accepted answer Claim. "
                    "result has exactly value (decimal string, no % sign, within 0.00001 of "
                    "that Claim) and unit (context.answer_unit). Ratios answering a "
                    "percentage question must actually be multiplied by 100 before Final; "
                    "changing the printed value/unit is not an executed conversion. citations "
                    "must be unique and exactly the answer Claim's lineage. No host "
                    "arithmetic repair."
                ),
                "verification_scope": (
                    "Intermediate validity is numeric and source-lexical, not correct "
                    "financial use. Final must establish the original question's financial "
                    "target with source-anchored algebra, not just coincidentally match its "
                    "number. Alternative arithmetic grouping is permitted. Unsupported "
                    "alternative evidence equivalences can remain outside this bounded "
                    "oracle."
                ),
                "reason_limit": (
                    "Action reason: at most 480 characters; subgoal: at most 240 characters."
                ),
            },
        )

    def transition(self, raw, request):
        require(request == self.request(), "integrity.current_request_binding")
        require(not self.terminal and self.submissions < 32, "lifecycle.closed")
        before = request["state"]["id"]
        submitted, error, observation, claim = None, None, None, None
        try:
            submitted = parse(raw)
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

    def run(self):
        termination = None
        require(self.callback is not None and self.store is not None, "runtime.live_bindings")
        self.store.json("binding.json", self.callback.binding)
        while not self.terminal and self.submissions < 32:
            request = self.request()
            prefix = f"turns/{self.submissions:03d}"
            self.store.json(prefix + "_request.json", request)
            try:
                raw = self.callback.generate(request)
            except OnlineTransportError as exc:
                termination = {"code": exc.code, "evidence_id": exc.evidence_id}
                break
            self.store.write(prefix + "_response.raw", raw)
            event = self.transition(raw, request)
            self.store.json(prefix + "_transition.json", event)
            if event["error"] and event["error"].startswith("integrity."):
                termination = {"code": event["error"]}
                break
        result = record(
            "session_result",
            session_id=self.session_id,
            task_id=self.task["qa_id"],
            condition=self.context["information_condition"],
            terminal=self.terminal,
            actions=self.actions,
            submissions=self.submissions,
            rejected=sum(not e["admitted"] for e in self.events),
            termination=termination,
            status="complete"
            if self.terminal
            else "unknown"
            if termination
            else "budget_exhausted",
            final_state=self.request()["state"],
        )
        self.store.json("result.json", result)
        return result
