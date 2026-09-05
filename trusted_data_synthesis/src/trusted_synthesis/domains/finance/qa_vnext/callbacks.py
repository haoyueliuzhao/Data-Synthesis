"""Uniform public-JSON callback contract; deterministic fixtures are not model samples."""

from __future__ import annotations

import copy
import hashlib
from collections.abc import Callable
from pathlib import Path
from typing import Any

from trusted_synthesis.canonical_json import canonical_json_bytes

from .program_adapter import public_program_answer
from .protocol import record, require
from .share_adapter import public_share_answer


def action_response(request: dict[str, Any], option: dict[str, Any]) -> dict[str, Any]:
    return {
        "kind": "action",
        "state_id": request["state"]["id"],
        "operation": option["operation"],
        "inputs": copy.deepcopy(option["inputs"]),
        "parameters": copy.deepcopy(option["parameters"]),
        "decision": {
            "obligation_id": option["obligation_id"],
            "subgoal": option["subgoal"],
            "candidate_action_ids": [item["id"] for item in request["available_actions"]],
            "selected_action_id": option["id"],
            "selection_rule": option["selection_rules"][0],
            "basis": copy.deepcopy(option["basis"]),
            "unresolved_uncertainty_refs": [],
            "expected_effect": copy.deepcopy(option["expected_effect"]),
        },
    }


def update_response(request: dict[str, Any], disposition: str = "accept") -> dict[str, Any]:
    observation = request["state"]["pending_observation"]
    transition = request["update_transition_options"][disposition]
    return {
        "kind": "update",
        "state_id": request["state"]["id"],
        "observation_id": observation["id"],
        "disposition": disposition,
        "proposed_claim": copy.deepcopy(observation["proposition"])
        if disposition == "accept"
        else None,
        "assessment": {
            "relation": "accepts_observed_proposition"
            if disposition == "accept"
            else "declines_observation",
            "observation_refs": [observation["id"]],
            "evidence_refs": observation["proposition"]["lineage"],
            "fulfills_obligation": observation["obligation_id"]
            if disposition == "accept"
            else None,
        },
        "remaining_uncertainty_refs": copy.deepcopy(transition["remaining_uncertainty_refs"]),
        "newly_enabled_obligation_ids": copy.deepcopy(transition["newly_enabled_obligation_ids"]),
        "next_subgoal": "submit_final"
        if "submit_final" in transition["allowed_next_subgoals"]
        else transition["allowed_next_subgoals"][0],
    }


class PublicFixtureCallback:
    def __init__(
        self, *, support_preference: str = "disclosed_total", reverse_ready_order: bool = False
    ):
        require(
            support_preference in {"disclosed_total", "reconstructed_total"}, "fixture.preference"
        )
        self.preference, self.reverse = support_preference, reverse_ready_order
        self.binding = record(
            "callback_binding",
            origin="fixture",
            implementation="PublicFixtureCallback.generate",
            source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            support_preference=support_preference,
            reverse_ready_order=reverse_ready_order,
            only_public_request_consumed=True,
            provider_calls=0,
            model_sample=False,
        )

    def generate(self, request: dict[str, Any]) -> bytes:
        state = request["state"]
        if state["pending_observation"] is not None:
            return canonical_json_bytes(update_response(request))
        if request["final_claim_ids"]:
            claim = next(
                item
                for item in state["accepted_claims"]
                if item["id"] == request["final_claim_ids"][0]
            )
            result = (
                public_program_answer(request["context"], state["accepted_claims"])
                if request["context"]["final_projection"] == "public_program_answer"
                else public_share_answer(request["context"], claim)
            )
            return canonical_json_bytes(
                {
                    "kind": "final",
                    "state_id": state["id"],
                    "answer_claim_id": claim["id"],
                    "result": result,
                    "citations": copy.deepcopy(claim["proposition"]["lineage"]),
                }
            )
        options = request["available_actions"]
        require(bool(options), "fixture.no_legal_action")
        preferred = [item for item in options if item["semantic_choice"] == self.preference]
        option = (preferred or options)[-1 if self.reverse else 0]
        return canonical_json_bytes(action_response(request, option))


class ExternalJSONCallback:
    """Wire an existing model/other JSON client to the SAME public response language.

    Transport evidence is the caller's responsibility. This generic binding does
    not turn an arbitrary callable into a verified model sample or Provider audit.
    """

    def __init__(self, complete: Callable[[dict[str, Any]], bytes], *, client_id: str):
        require(bool(client_id), "callback.client_identity")
        self.complete = complete
        self.binding = record(
            "callback_binding",
            origin="external_callback",
            client_id=client_id,
            verified_model_origin=False,
            model_sample=False,
            only_public_request_passed=True,
            host_semantic_field_fill=False,
        )

    def generate(self, request: dict[str, Any]) -> bytes:
        result = self.complete(copy.deepcopy(request))
        require(isinstance(result, bytes), "callback.raw_response_required")
        return result
