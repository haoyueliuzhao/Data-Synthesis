"""Two registered local adapter sessions and two one-turn failure seam controls."""

from __future__ import annotations

import copy
import json
from decimal import Decimal, localcontext
from typing import Any

from trusted_synthesis.canonical_json import canonical_json_bytes
from trusted_synthesis.experiments.qa_reasoning_share_public_protocol.fixture import (
    action_payload,
    update_payload,
)

from .adapter import TransportFailure
from .models import record, require

CONTROL_NAMES = ("direct", "reject_then_direct", "invalid_json", "transport_failure")


def control_declaration(
    name: str, protocol: dict[str, Any], config: dict[str, Any]
) -> dict[str, Any]:
    require(name in CONTROL_NAMES, "controls.unknown_control")
    return record(
        "session_declaration",
        label="C_" + name.upper(),
        ordinal=CONTROL_NAMES.index(name),
        protocol_id=protocol["id"],
        model_configuration_id=config["id"],
        generator_origin="adapter_mock",
        neutral_prompt=False,
        reference_route=name,
        independent_initial_state=True,
        reads_other_session_responses=False,
        maximum_provider_attempts=0,
        replacement_allowed=False,
        control_only=True,
        complete_session_control=name in {"direct", "reject_then_direct"},
        maximum_mock_callbacks={
            "direct": 5,
            "reject_then_direct": 7,
            "invalid_json": 1,
            "transport_failure": 1,
        }[name],
        maximum_action_dispatches={
            "direct": 2,
            "reject_then_direct": 3,
            "invalid_json": 0,
            "transport_failure": 0,
        }[name],
    )


class Scenario:
    """Explicit mock endpoint strategy, never an online model substitute."""

    def __init__(self, name: str) -> None:
        require(name in CONTROL_NAMES, "controls.unknown_control")
        self.name = name
        self.calls = 0

    def public_response(self, request: dict[str, Any]) -> bytes:
        state = request["state"]
        if self.name == "invalid_json":
            return b"not a JSON submission"
        if state["phase"] == "update":
            disposition = (
                "reject"
                if self.name == "reject_then_direct"
                and state["pending_observation"]["operation"] == "relation_sum"
                else "accept"
            )
            return canonical_json_bytes(update_payload(state, disposition))
        claims = {c["proposition"]["metric"]: c for c in state["accepted_claims"]}
        if "freight_share_percent" in claims:
            claim = claims["freight_share_percent"]
            with localcontext() as numeric_context:
                numeric_context.prec = state["numeric"]["precision"]
                numeric_context.rounding = state["numeric"]["rounding"]
                value = str(
                    Decimal(claim["proposition"]["value"]).quantize(
                        Decimal(state["numeric"]["final_quantum"])
                    )
                )
            return canonical_json_bytes(
                {
                    "kind": "final",
                    "state_id": state["id"],
                    "answer_claim_id": claim["id"],
                    "answer": {"value": value, "unit": "percent"},
                    "citations": copy.deepcopy(claim["grounding"]),
                    "public_basis": {
                        "relation": "supports",
                        "claim_refs": [claim["id"]],
                        "evidence_refs": copy.deepcopy(claim["grounding"]),
                    },
                }
            )

        def ref(role: str, kind: str, obj: dict[str, Any]) -> dict[str, str]:
            return {"role": role, "kind": kind, "ref_id": obj["id"]}

        if "freight_share_ratio" in claims:
            return canonical_json_bytes(
                action_payload(
                    state,
                    "scale_percent",
                    [ref("ratio", "claim", claims["freight_share_ratio"])],
                    {},
                )
            )
        if self.name == "reject_then_direct" and state["action_count"] == 0:
            evidence = state["evidence"]
            return canonical_json_bytes(
                action_payload(
                    state,
                    "relation_sum",
                    [
                        ref("member", "evidence", evidence["freight"]),
                        ref("member", "evidence", evidence["other"]),
                        ref("relation", "evidence", evidence["part_whole"]),
                    ],
                    {"method": "sum"},
                )
            )
        return canonical_json_bytes(
            action_payload(
                state,
                "share_ratio",
                [
                    ref("numerator", "evidence", state["evidence"]["freight"]),
                    ref("denominator", "evidence", state["evidence"]["total"]),
                ],
                {},
            )
        )

    def handle(self, request_record: dict[str, Any]) -> dict[str, Any]:
        """Return a raw transport fixture; adapter extracts the same public message field."""
        self.calls += 1
        if self.name == "transport_failure":
            raise TransportFailure("transport.timeout")
        body = json.loads(request_record["body_json"])
        public_request = json.loads(body["messages"][1]["content"])
        response = {
            "id": "mock-" + request_record["call_id"].split(":")[-1],
            "model": body["model"],
            "object": "chat.completion",
            "choices": [
                {
                    "index": 0,
                    "finish_reason": "stop",
                    "message": {
                        "role": "assistant",
                        "content": self.public_response(public_request).decode("utf-8"),
                    },
                }
            ],
            "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        }
        return {"http_status": 200, "body": canonical_json_bytes(response)}
