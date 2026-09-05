"""Actual finite execution; admitted heterogeneous source sums are not raw Evidence."""

from __future__ import annotations

import hashlib
from decimal import Decimal, localcontext
from pathlib import Path
from typing import Any

from trusted_synthesis.canonical_json import canonical_json_bytes
from trusted_synthesis.experiments.qa_reasoning_fixed_fixture.runtime import DurableArtifactWriter

from .models import CONTEXT_FIELDS, admit_inputs, record, require, validate_record


class RelationSumExecutor:
    """Only actual member scalars enter the arithmetic kernel; no total operand."""

    def execute(self, inputs: list[dict[str, Any]]) -> Decimal:
        return sum((Decimal(item["value"]) for item in inputs[:2]), Decimal(0))


class ShareRatioExecutor:
    def execute(self, inputs: list[dict[str, Any]]) -> Decimal:
        return Decimal(inputs[0]["value"]) / Decimal(inputs[1]["value"])


class ScalePercentExecutor:
    def execute(self, inputs: list[dict[str, Any]]) -> Decimal:
        return Decimal(inputs[0]["value"]) * Decimal(100)


def resolve_inputs(
    node: dict[str, Any], source: dict[str, Any], claims: dict[str, Any], producers: dict[str, str]
) -> list[dict[str, Any]]:
    by_id = {x["id"]: x for x in source["evidence"].values()}
    result = []
    for ref in node["inputs"]:
        if ref["kind"] == "evidence":
            require(ref["ref"] in by_id, "admission.visible_evidence", "unavailable Evidence")
            obj = by_id[ref["ref"]]
            if obj["kind"] == "part_whole":
                result.append(
                    {
                        "role": ref["role"],
                        "kind": "evidence",
                        "ref_id": obj["id"],
                        "relation": obj,
                        "lineage": [obj["id"]],
                    }
                )
                continue
            result.append(
                {
                    "role": ref["role"],
                    "kind": "evidence",
                    "ref_id": obj["id"],
                    **{key: obj[key] for key in ("value", "metric", "definition", *CONTEXT_FIELDS)},
                    "lineage": [obj["id"]],
                    "producer_operation": None,
                }
            )
        else:
            require(
                ref["kind"] == "claim" and ref["ref"] in claims,
                "admission.claim",
                "future or unavailable Claim",
            )
            claim = claims[ref["ref"]]
            require(claim["status"] == "accepted", "admission.claim", "unaccepted Claim")
            result.append(
                {
                    "role": ref["role"],
                    "kind": "claim",
                    "ref_id": claim["id"],
                    **claim["proposition"],
                    "producer_operation": producers[ref["ref"]],
                }
            )
    return result


def _state(
    contract: dict[str, Any],
    candidate: dict[str, Any],
    claims: dict[str, Any],
    observations: list[str],
) -> dict[str, Any]:
    return record(
        "state",
        task_id=contract["task"]["id"],
        candidate_id=candidate["id"],
        visible_evidence_ids=contract["task"]["evidence_universe_ids"],
        accepted_claims=[c["id"] for c in claims.values()],
        completed_nodes=list(claims),
        observations=list(observations),
    )


def run_candidate(
    contract: dict[str, Any],
    source: dict[str, Any],
    candidate: dict[str, Any],
    output_directory: Path,
) -> dict[str, Any]:
    """One positive route, with durable proposal/receipt before every dispatch."""
    for obj in (contract, source, candidate):
        validate_record(obj)
    require(
        source["id"] == contract["source_binding_id"] == contract["task"]["source_binding_id"]
        and candidate["task_id"] == contract["task"]["id"]
        and candidate["contract_id"] == contract["id"]
        and candidate["controller"] == "deterministic_fixture"
        and 1 <= len(candidate["nodes"]) <= contract["runtime_action_bound"],
        "runtime.registration",
        "candidate not registered for this Task/contract",
    )
    writer = DurableArtifactWriter(output_directory)
    writer.create_root()
    paths: dict[str, Any] = {
        "candidate": "candidate.json",
        "initial_state": "initial_state.json",
        "steps": [],
    }
    writer.write_json(paths["candidate"], candidate)
    claims: dict[str, Any] = {}
    producers: dict[str, str] = {}
    observation_ids: list[str] = []
    state = _state(contract, candidate, claims, observation_ids)
    writer.write_json(paths["initial_state"], state)
    records: dict[str, Any] = {"candidate": candidate, "initial_state": state, "steps": []}
    kernels: dict[str, RelationSumExecutor | ShareRatioExecutor | ScalePercentExecutor] = {
        "relation_sum": RelationSumExecutor(),
        "share_ratio": ShareRatioExecutor(),
        "scale_percent": ScalePercentExecutor(),
    }
    numeric = contract["numeric"]
    with localcontext() as context:
        context.prec = numeric["precision"]
        context.rounding = numeric["rounding"]
        for index, node in enumerate(candidate["nodes"]):
            require(node["name"] not in claims, "runtime.node", "duplicate node")
            inputs = resolve_inputs(node, source, claims, producers)
            step_paths: dict[str, str] = {}
            step: dict[str, Any] = {}

            def persist(
                kind: str,
                obj: dict[str, Any],
                sequence: int = index,
                destinations: dict[str, str] = step_paths,
                objects: dict[str, Any] = step,
            ) -> bytes:
                relative = f"steps/{sequence:02d}_{kind}.json"
                destinations[kind] = relative
                objects[kind] = obj
                return writer.write_json(relative, obj)

            proposal = record(
                "proposal",
                task_id=contract["task"]["id"],
                candidate_id=candidate["id"],
                node=node["name"],
                operation=node["operation"],
                operation_contract_id=contract["operations"][node["operation"]]["id"],
                parameters=node["parameters"],
                inputs=[{k: x[k] for k in ("role", "kind", "ref_id")} for x in inputs],
                requires_basis=sorted({ref for x in inputs for ref in x["lineage"]}),
                pre_state_id=state["id"],
                owner="deterministic_fixture",
            )
            proposal_bytes = persist("proposal", proposal)
            checks = admit_inputs(node["operation"], inputs, node["parameters"], contract, source)
            receipt = record(
                "receipt",
                proposal_id=proposal["id"],
                pre_state_id=state["id"],
                admitted=True,
                checks=checks,
                proposal_sha256=hashlib.sha256(proposal_bytes).hexdigest(),
                proposal_byte_count=len(proposal_bytes),
                no_replace=True,
                proposal_file_and_directory_fsynced=True,
            )
            receipt_bytes = persist("receipt", receipt)
            require(
                writer.read_bytes(step_paths["proposal"]) == proposal_bytes
                and writer.read_bytes(step_paths["receipt"]) == receipt_bytes,
                "runtime.pre_dispatch_bytes",
                "durable pre-action objects changed",
            )
            value = kernels[node["operation"]].execute(inputs)
            require(value.is_finite(), "runtime.finite", "nonfinite output")
            op = contract["operations"][node["operation"]]
            definitions = {
                "relation_sum": source["evidence"]["total"]["definition"],
                "share_ratio": "freight divided by legitimate operating revenue total",
                "scale_percent": "freight share in percent",
            }
            output = {
                **{key: source["evidence"]["freight"][key] for key in CONTEXT_FIELDS},
                "value": str(value),
                "metric": op["output_metric"],
                "unit": op["output_unit"],
                "definition": definitions[node["operation"]],
                "lineage": sorted({ref for x in inputs for ref in x["lineage"]}),
            }
            execution = record(
                "execution",
                proposal_id=proposal["id"],
                receipt_id=receipt["id"],
                operation=node["operation"],
                parameters=node["parameters"],
                inputs=inputs,
                output=output,
            )
            persist("execution", execution)
            observation = record(
                "observation", execution_id=execution["id"], output=output, success=True
            )
            persist("observation", observation)
            claim = record(
                "claim",
                task_id=contract["task"]["id"],
                node=node["name"],
                proposition=output,
                observation_id=observation["id"],
                status="accepted",
                grounding=output["lineage"],
                owner="deterministic_fixture",
            )
            persist("claim", claim)
            update = record(
                "update",
                pre_state_id=state["id"],
                observation_id=observation["id"],
                accepted_claim_id=claim["id"],
                decision="accept_observed_claim",
                owner="deterministic_fixture",
            )
            persist("update", update)
            claims[node["name"]] = claim
            producers[node["name"]] = node["operation"]
            observation_ids.append(observation["id"])
            state = _state(contract, candidate, claims, list(observation_ids))
            persist("state", state)
            paths["steps"].append(step_paths)
            records["steps"].append(step)
        claim = claims[candidate["output_node"]]
        final = record(
            "final",
            task_id=contract["task"]["id"],
            candidate_id=candidate["id"],
            pre_state_id=state["id"],
            answer={
                "value": str(
                    Decimal(claim["proposition"]["value"]).quantize(
                        Decimal(numeric["final_quantum"])
                    )
                ),
                "unit": "percent",
            },
            answer_claim_id=claim["id"],
            citations=claim["grounding"],
            owner="deterministic_fixture",
        )
    writer.write_json("final.json", final)
    paths["final"] = "final.json"
    records["final"] = final
    members = []
    for path in sorted(writer.root.rglob("*.json")):
        data = path.read_bytes()
        members.append(
            {
                "relative_path": path.relative_to(writer.root).as_posix(),
                "sha256": hashlib.sha256(data).hexdigest(),
                "byte_count": len(data),
            }
        )
    manifest = record(
        "execution_manifest",
        task_id=contract["task"]["id"],
        candidate_id=candidate["id"],
        contract_id=contract["id"],
        records=paths,
        members=members,
        action_count=len(records["steps"]),
        actual_executor_calls=len(records["steps"]),
        oracle_calls=0,
        write_events=list(writer.events),
    )
    writer.write_json("execution_manifest.json", manifest)
    require(
        canonical_json_bytes(records["final"]) == writer.read_bytes("final.json"),
        "runtime.final_bytes",
        "Final persisted bytes differ",
    )
    return {"records": records, "manifest": manifest}
