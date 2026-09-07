"""A declared compact language; raw model bytes are never rewritten or repaired."""

from __future__ import annotations

import copy
import json
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from trusted_synthesis.domains.finance.qa_vnext.protocol import Final, record, require

from .adapters import evidence_ids

VERSION = "harness_responsibility_compact.v1"


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class Selection(Strict):
    kind: Literal["action"]
    state_id: str
    action: str


class Proposal(Strict):
    kind: Literal["action"]
    state_id: str
    subgoal: str = Field(min_length=1, max_length=240)
    reason: str = Field(min_length=1, max_length=480)
    operation: str
    inputs: list[str] = Field(min_length=1, max_length=3)
    parameters: dict[str, Any]


class Acceptance(Strict):
    kind: Literal["update"]
    state_id: str
    observation: str
    disposition: Literal["accept", "reject"]


def result_schema(group):
    return {
        "type": "object",
        "required": ["value", "unit"],
        "additionalProperties": False,
        "properties": {
            "value": {
                "type": "string",
                "pattern": r"^-?(?:0|[1-9][0-9]*)\.[0-9]{6}$"
                if group == "S"
                else r"^-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?$",
            },
            "unit": {"const": "percent" if group == "S" else "percentage_points"},
        },
    }


def final_rules(group, compact):
    return {
        "version": "harness_common_final_publication.v1",
        "schema": result_schema(group),
        "state": "Copy response_state_id exactly." if compact else "Copy state.id exactly.",
        "answer": "Select one final_claim_ids entry, an accepted answer Claim; "
        "no pending observation.",
        "value": (
            "Use the selected Claim output.value, Decimal precision 50, ROUND_HALF_EVEN, "
            "quantize 0.000001; exactly six decimal places, no percent sign."
            if group == "S"
            else "Use the selected Claim output.value at original Decimal precision 28, "
            "ROUND_HALF_EVEN; retain its full precision, no additional six-place rounding."
        ),
        "fields": "result has exactly value and unit; do not copy any other proposition metadata.",
        "citations": "Unique Evidence references, set exactly equal to selected answer Claim "
        "proposition.lineage; actual support, not all visible evidence or intermediate Claim ids.",
        "unit": "percent" if group == "S" else "percentage_points",
        "verification": "Strict original task numeric/unit/schema/citation and independent "
        "source answer checks. The host never supplies or corrects the submitted result.",
    }


def schemas(group, condition):
    result = {
        "action": (Selection if condition == "H1" else Proposal).model_json_schema(),
        "update": Acceptance.model_json_schema(),
        "final": Final.model_json_schema(),
    }
    result["final"]["properties"]["result"] = result_schema(group)
    return result


def strict_load(raw):
    require(len(raw) <= 1_048_576, "submission.byte_bound")

    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, "json.duplicate_key")
            result[key] = value
        return result

    def invalid(value):
        raise ValueError("json.non_finite_number")

    try:
        value = json.loads(raw, object_pairs_hook=pairs, parse_constant=invalid)
        require(isinstance(value, dict), "submission.object")
        return value
    except (UnicodeError, json.JSONDecodeError) as error:
        raise ValueError("submission.schema") from error


def parse_compact(raw, condition):
    value = strict_load(raw)
    models = {
        "action": Selection if condition == "H1" else Proposal,
        "update": Acceptance,
        "final": Final,
    }
    require(value.get("kind") in models, "submission.kind")
    try:
        return models[value["kind"]].model_validate(value).model_dump(mode="json")
    except ValidationError as error:
        raise ValueError("submission.schema") from error


class References:
    def __init__(self, base, group):
        self.forward, self.reverse = {}, {}
        for key in evidence_ids(base, group):
            self.add(key, "E")

    def add(self, key, prefix):
        if key not in self.forward:
            number = sum(value.startswith(prefix) for value in self.forward.values()) + 1
            alias = f"{prefix}{number}"
            require(alias not in self.reverse, "reference.bijection")
            self.forward[key], self.reverse[alias] = alias, key
        return self.forward[key]

    def decode(self, value, prefix):
        require(
            isinstance(value, str) and value in self.reverse and value.startswith(prefix),
            "reference.exact_current_session_ref",
        )
        return self.reverse[value]

    def render(self, value):
        if isinstance(value, dict):
            return {key: self.render(item) for key, item in value.items()}
        if isinstance(value, list):
            return [self.render(item) for item in value]
        if isinstance(value, str):
            return self.forward.get(value, value)
        return value


def expand_selection(selected, request):
    options = {option["id"]: option for option in request["available_actions"]}
    require(selected in options, "admission.selected_action")
    option = options[selected]
    return {
        "kind": "action",
        "state_id": request["state"]["id"],
        "operation": option["operation"],
        "inputs": copy.deepcopy(option["inputs"]),
        "parameters": copy.deepcopy(option["parameters"]),
        "decision": {
            "obligation_id": option["obligation_id"],
            "subgoal": option["subgoal"],
            "candidate_action_ids": list(options),
            "selected_action_id": selected,
            "selection_rule": option["selection_rules"][0],
            "basis": copy.deepcopy(option["basis"]),
            "unresolved_uncertainty_refs": [],
            "expected_effect": copy.deepcopy(option["expected_effect"]),
        },
    }


def expand_acceptance(observation, disposition, request):
    require(observation is not None, "admission.pending_observation")
    accepted = disposition == "accept"
    transition = request["update_transition_options"][disposition]
    # A declared SYSTEM-derived scheduling placeholder, NOT a model-selected subgoal.
    # No execution occurs here and the next Action still requires a separate model choice.
    next_options = transition["allowed_next_subgoals"]
    require(bool(next_options), "compact.no_declared_transition")
    return {
        "kind": "update",
        "state_id": request["state"]["id"],
        "observation_id": observation["id"],
        "disposition": disposition,
        "proposed_claim": copy.deepcopy(observation["proposition"]) if accepted else None,
        "assessment": {
            "relation": "accepts_observed_proposition" if accepted else "declines_observation",
            "observation_refs": [observation["id"]],
            "evidence_refs": observation["proposition"]["lineage"],
            "fulfills_obligation": observation["obligation_id"] if accepted else None,
        },
        "remaining_uncertainty_refs": transition["remaining_uncertainty_refs"],
        "newly_enabled_obligation_ids": transition["newly_enabled_obligation_ids"],
        "next_subgoal": next_options[0],
    }


def binding_record(condition, raw, submitted, expanded, refs):
    import hashlib

    return record(
        "language_binding",
        version=VERSION,
        condition=condition,
        raw_sha256=hashlib.sha256(raw).hexdigest(),
        model_submission=submitted,
        expanded=expanded,
        reference_map=copy.deepcopy(refs.reverse),
        model_responsibility=(
            "full original submission"
            if condition == "H0"
            else "explicit action selection/proposal, observation acceptance, "
            "Final result and citations"
        ),
        system_responsibility=(
            []
            if condition == "H0"
            else [
                "exact alias resolution",
                "binding to current state",
                "H1 selected offered content and displayed candidate set",
                "entire explicitly selected observation binding",
                "H1 derived obligation fields and scheduling placeholder; not model judgments",
                "H2 operation input roles and actual dependency lineage; no reference plan",
            ]
        ),
        host_error_repair=False,
        expanded_fields_are_independent_model_generation=False,
    )


def feedback(code, request, submitted, group, condition):
    """Same Final diagnostics in all conditions; public Claim comparison only, no repair."""
    from decimal import ROUND_HALF_EVEN, Decimal, InvalidOperation, localcontext

    if (submitted and submitted["kind"] == "final") or (
        submitted is None and request.get("final_claim_ids")
    ):
        failures = []
        if submitted:
            matches = [
                c
                for c in request["state"]["accepted_claims"]
                if c["id"] == submitted["answer_claim_id"]
            ]
            result = submitted["result"]
            if set(result) != {"value", "unit"}:
                failures.append("result_exactly_value_and_unit")
            if result.get("unit") != ("percent" if group == "S" else "percentage_points"):
                failures.append("result_unit")
            if len(matches) != 1 or submitted["answer_claim_id"] not in request["final_claim_ids"]:
                failures.append("accepted_answer_reference")
            else:
                claim = matches[0]
                if len(submitted["citations"]) != len(set(submitted["citations"])) or set(
                    submitted["citations"]
                ) != set(claim["proposition"]["lineage"]):
                    failures.append("actual_lineage_exact_unique_set")
                try:
                    with localcontext() as numeric:
                        numeric.prec, numeric.rounding = (
                            (50 if group == "S" else 28),
                            ROUND_HALF_EVEN,
                        )
                        expected = Decimal(claim["proposition"]["output"]["value"])
                        if group == "S":
                            expected = expected.quantize(Decimal("0.000001"))
                        value = result.get("value")
                        valid = isinstance(value, str) and Decimal(value).is_finite()
                        valid = valid and (
                            value == str(expected) if group == "S" else Decimal(value) == expected
                        )
                    if not valid:
                        failures.append("selected_claim_value_projection")
                except (InvalidOperation, TypeError, ValueError, KeyError):
                    failures.append("selected_claim_value_projection")
        return {
            "code": code,
            "admitted": False,
            "final_diagnostics": failures,
            "final_requirements": final_rules(group, condition != "H0"),
            "diagnostics_are_not_an_answer_or_host_repair": True,
        }
    if condition == "H0":
        from trusted_synthesis.domains.finance.qa_vnext.action_public_contract import (
            rejection_feedback,
        )

        stripped = {k: v for k, v in request.items() if k != "public_final_contract"}
        return rejection_feedback(code, stripped, submitted)
    return {"code": code, "admitted": False, "schema_location": "/response_schemas"}
