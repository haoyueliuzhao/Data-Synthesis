"""A registered local generator fixture consuming only the public request.

This client strategy is not a model policy. The Host receives no route label,
node plan or next-operation vector; each response independently crosses the
same public callback and submission grammar as a prospective generator would.
"""

from __future__ import annotations

import copy
import hashlib
from decimal import Decimal, localcontext
from pathlib import Path
from typing import Any

from trusted_synthesis.canonical_json import canonical_json_bytes

from .models import record, require


def fixture_binding() -> dict[str, Any]:
    return record(
        "generator_binding",
        kind="deterministic_fixture",
        implementation="PublicRequestFixture.generate",
        module="trusted_synthesis.experiments.qa_reasoning_share_public_protocol.fixture",
        class_name="PublicRequestFixture",
        method_name="generate",
        source_path="trusted_data_synthesis/src/trusted_synthesis/experiments/qa_reasoning_share_public_protocol/fixture.py",
        source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        inputs="one actual public generator_request object only",
        semantic_choices_owned_by="deterministic_fixture_not_model",
        strategy="reconstruct total; use accepted Claims to complete the public share goal",
        host_route_or_plan_argument=False,
        Provider_calls=0,
        credentials=0,
        callback_response_is_authority_for_submission=True,
    )


def action_payload(
    state: dict[str, Any],
    operation: str,
    operands: list[dict[str, str]],
    parameters: dict[str, str],
) -> dict[str, Any]:
    evidence = {e["id"]: e for e in state["evidence"].values()}
    claims = {c["id"]: c for c in state["accepted_claims"]}
    refs = []
    used_claims = []
    for operand in operands:
        if operand["kind"] == "evidence":
            require(operand["ref_id"] in evidence, "fixture.visible_evidence")
            refs.append(operand["ref_id"])
        else:
            claim = claims[operand["ref_id"]]
            used_claims.append(claim["id"])
            refs.extend(claim["grounding"])
    return {
        "kind": "action",
        "state_id": state["id"],
        "operation": operation,
        "inputs": copy.deepcopy(operands),
        "parameters": copy.deepcopy(parameters),
        "public_basis": {
            "relation": "requires",
            "evidence_refs": sorted(set(refs)),
            "claim_refs": sorted(set(used_claims)),
            "intended_metric": state["operations"][operation]["output_metric"],
        },
    }


def update_payload(state: dict[str, Any], disposition: str) -> dict[str, Any]:
    observation = state["pending_observation"]
    require(observation is not None, "fixture.pending_observation")
    return {
        "kind": "update",
        "state_id": state["id"],
        "observation_id": observation["id"],
        "disposition": disposition,
        "proposed_claim": copy.deepcopy(observation["output"]) if disposition == "accept" else None,
        "public_basis": {
            "relation": "supports" if disposition == "accept" else "declines",
            "observation_refs": [observation["id"]],
            "evidence_refs": copy.deepcopy(observation["output"]["lineage"]),
        },
    }


class PublicRequestFixture:
    def __init__(self) -> None:
        self.binding = fixture_binding()
        self.calls = 0

    def generate(self, request: dict[str, Any]) -> bytes:
        self.calls += 1
        state = request["state"]
        if state["phase"] == "update":
            # Explicit independent generator response, not Host auto-acceptance.
            return canonical_json_bytes(update_payload(state, "accept"))
        require(state["phase"] == "action", "fixture.phase")
        claims = {c["proposition"]["metric"]: c for c in state["accepted_claims"]}
        if "freight_share_percent" in claims:
            claim = claims["freight_share_percent"]
            with localcontext() as context:
                context.prec = state["numeric"]["precision"]
                context.rounding = state["numeric"]["rounding"]
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
            payload = action_payload(
                state, "scale_percent", [ref("ratio", "claim", claims["freight_share_ratio"])], {}
            )
        elif "total_operating_revenues" in claims:
            payload = action_payload(
                state,
                "share_ratio",
                [
                    ref("numerator", "evidence", state["evidence"]["freight"]),
                    ref("denominator", "claim", claims["total_operating_revenues"]),
                ],
                {},
            )
        else:
            payload = action_payload(
                state,
                "relation_sum",
                [
                    ref("member", "evidence", state["evidence"]["freight"]),
                    ref("member", "evidence", state["evidence"]["other"]),
                    ref("relation", "evidence", state["evidence"]["part_whole"]),
                ],
                {"method": "sum"},
            )
        return canonical_json_bytes(payload)
