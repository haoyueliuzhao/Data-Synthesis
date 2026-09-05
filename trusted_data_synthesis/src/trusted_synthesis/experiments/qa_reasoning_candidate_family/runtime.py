"""Bounded, source-grounded operation execution with durable public commitments.

The controller is a deterministic fixture.  No answer Oracle is consulted by
this runtime, and each persisted operation is actually dispatched exactly once.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from trusted_synthesis.canonical_json import canonical_json_bytes, strict_canonical_hash
from trusted_synthesis.core.operations.registry import operation_semantic_contract_hash
from trusted_synthesis.core.operations.schema import OperationInput
from trusted_synthesis.experiments.qa_reasoning_fixed_fixture.runtime import DurableArtifactWriter
from trusted_synthesis.experiments.qa_semantic_depth_three_catalog_integration.catalog import (
    catalog_operation_registry,
)


class CandidateRuntimeError(ValueError):
    def __init__(self, stage: str, message: str) -> None:
        super().__init__(message)
        self.stage = stage


def _require(condition: bool, stage: str, message: str) -> None:
    if not condition:
        raise CandidateRuntimeError(stage, message)


def _record(kind: str, **values: Any) -> dict[str, Any]:
    payload = {"schema_version": f"typed_candidate_{kind}.v1", **values}
    return {"id": strict_canonical_hash(payload, prefix=f"typed_candidate_{kind}:"), **payload}


def _claim_id(candidate: Mapping[str, Any], node_id: str) -> str:
    return strict_canonical_hash(
        {"candidate_id": candidate["candidate_id"], "node_id": node_id},
        prefix="typed_candidate_claim:",
    )


def _select(value: Any, selector: str | None) -> Any:
    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="json", exclude_none=True)
    for part in selector.split(".") if selector else ():
        _require(
            isinstance(value, dict) and part in value, "admission.selector", "invalid selector"
        )
        value = value[part]
    return value


def _roles(fixture: Mapping[str, Any]) -> dict[str, Any]:
    bundle, package = fixture["bundle"], fixture["package"]
    evidence = {item.evidence_id: item for item in bundle.evidence}
    bindings = package.binding_snapshot.role_bindings
    required = {"revenue_earlier", "revenue_later", "income_earlier", "income_later"}
    _require(set(bindings) == required, "admission.role_domain", "frozen role domain differs")
    _require(
        all(len(refs) == 1 and refs[0] in evidence for refs in bindings.values()),
        "admission.role_binding",
        "Evidence role does not resolve exactly once",
    )
    return {role: evidence[refs[0]] for role, refs in bindings.items()}


def _comparability(roles: Mapping[str, Any]) -> dict[str, Any]:
    items = tuple(roles.values())
    checks = {
        "same_subject": len({item.subject.subject_id for item in items}) == 1,
        "same_source": len({item.source.source_id for item in items}) == 1,
        "same_unit": len({item.payload.unit for item in items}) == 1,
        "same_currency": len({item.payload.currency for item in items}) == 1,
        "same_windows": all(
            roles[f"revenue_{period}"].temporal_context
            == roles[f"income_{period}"].temporal_context
            for period in ("earlier", "later")
        ),
    }
    for prefix, predicate in (("revenue", "revenue"), ("income", "operating_income")):
        early, late = roles[f"{prefix}_earlier"], roles[f"{prefix}_later"]
        checks[prefix + "_metric"] = early.predicate == late.predicate == predicate
        checks[prefix + "_definition"] = early.definition == late.definition
        checks[prefix + "_period_order"] = (
            early.domain_context["economic_period_sort_key"]
            < late.domain_context["economic_period_sort_key"]
        )
    _require(all(checks.values()), "admission.comparability", "frozen Evidence is not comparable")
    return {
        "checks": checks,
        "evidence_refs": tuple(item.evidence_id for item in items),
        "field_origin": "host_derived",
    }


def _typed_inputs(
    *,
    fixture: Mapping[str, Any],
    node: Any,
    claims: Mapping[str, Any],
    available_evidence: tuple[str, ...],
    registry: Any,
) -> tuple[tuple[OperationInput, ...], tuple[str, ...], dict[str, Any], tuple[dict[str, Any], ...]]:
    roles = _roles(fixture)
    evidence = {item.evidence_id: item for item in fixture["bundle"].evidence}
    evidence_roles = {item.evidence_id: role for role, item in roles.items()}
    definition = registry.validate_node_contract(node)
    _require(
        not node.parameters, "admission.parameters", "this finite family requires empty parameters"
    )
    values, semantics, operands = [], [], []
    lineage: list[str] = []
    for index, ref in enumerate(node.input_refs):
        if ref.kind.value == "evidence":
            _require(
                ref.ref_id in evidence and ref.ref_id in available_evidence,
                "admission.visible_evidence",
                "Evidence is outside this task or current State",
            )
            item = evidence[ref.ref_id]
            value = _select(item.payload, ref.selector)
            semantic = {"kind": "evidence_scalar", "role": evidence_roles[ref.ref_id]}
            refs = (ref.ref_id,)
            producer = None
        else:
            _require(
                ref.ref_id in claims, "admission.verified_claim", "Claim is unavailable or future"
            )
            claim = claims[ref.ref_id]
            _require(
                claim["status"] == "verified", "admission.verified_claim", "Claim is not verified"
            )
            value = _select(claim["output"], ref.selector)
            semantic, refs, producer = claim["semantic"], claim["evidence_refs"], claim["claim_id"]
        values.append(OperationInput(ref_id=ref.ref_id, value=value))
        semantics.append(semantic)
        lineage.extend(refs)
        operands.append(
            {
                "kind": ref.kind.value,
                "ref_id": ref.ref_id,
                "selector": ref.selector,
                "operand_role": definition.input_role_contract[index],
                "producer_claim_id": producer,
            }
        )
    operation = node.operator_id
    if operation == "lookup":
        _require(
            len(semantics) == 1
            and node.input_refs[0].kind.value == "evidence"
            and node.input_refs[0].selector is None,
            "admission.lookup",
            "lookup must preserve an actual Evidence payload",
        )
        output_semantic = semantics[0]
    elif operation == "growth":
        _require(
            len(semantics) == 2 and all(s["kind"] == "evidence_scalar" for s in semantics),
            "admission.growth_roles",
            "growth needs two source scalar roles",
        )
        early_role, later_role = (s["role"] for s in semantics)
        prefix = early_role.removesuffix("_earlier")
        _require(
            prefix in {"revenue", "income"}
            and early_role == prefix + "_earlier"
            and later_role == prefix + "_later",
            "admission.growth_roles",
            "growth period or metric roles differ",
        )
        _require(
            all(
                ref.selector == ("value" if ref.kind.value == "evidence" else "payload.value")
                for ref in node.input_refs
            ),
            "admission.growth_selector",
            "growth scalar selector differs",
        )
        output_semantic = {
            "kind": "growth_percent",
            "metric": prefix,
            "earlier_role": early_role,
            "later_role": later_role,
            "unit": "percent",
        }
    elif operation == "signed_percentage_point_gap":
        _require(
            semantics
            == [
                {
                    "kind": "growth_percent",
                    "metric": "income",
                    "earlier_role": "income_earlier",
                    "later_role": "income_later",
                    "unit": "percent",
                },
                {
                    "kind": "growth_percent",
                    "metric": "revenue",
                    "earlier_role": "revenue_earlier",
                    "later_role": "revenue_later",
                    "unit": "percent",
                },
            ],
            "admission.signed_operand_roles",
            "signed gap reference/observed metric roles differ",
        )
        _require(
            all(ref.selector == "value" for ref in node.input_refs),
            "admission.gap_selector",
            "gap scalar selector differs",
        )
        output_semantic = {
            "kind": "signed_growth_gap",
            "reference_metric": "income",
            "observed_metric": "revenue",
            "unit": "percentage_points",
        }
    elif operation == "absolute_percentage_point_gap":
        _require(
            len(semantics) == 1
            and semantics[0]["kind"] == "signed_growth_gap"
            and node.input_refs[0].selector == "value",
            "admission.absolute_input",
            "absolute operation lacks the signed growth gap",
        )
        output_semantic = {"kind": "absolute_growth_spread", "unit": "percentage_points"}
    else:
        raise CandidateRuntimeError(
            "admission.finite_language", "operation is outside the frozen family"
        )
    unique_lineage = tuple(dict.fromkeys(lineage))
    registry.validate_inputs(definition, tuple(values))
    registry.validate_compatibility(
        definition, tuple(evidence[ref] for ref in unique_lineage), node.parameters
    )
    return tuple(values), unique_lineage, output_semantic, tuple(operands)


def _state(
    fixture: Mapping[str, Any],
    candidate: Mapping[str, Any],
    claims: Mapping[str, Any],
    completed: list[str],
    observations: list[str],
) -> dict[str, Any]:
    ready = tuple(
        node.node_id
        for node in candidate["program"].nodes
        if node.node_id not in completed and set(node.dependencies) <= set(completed)
    )
    return _record(
        "state",
        task_id=fixture["task_id"],
        candidate_id=candidate["candidate_id"],
        sequence=len(completed),
        source_scope_binding_id=fixture["scope_bindings"]["scope_binding_id"],
        source_comparability=_comparability(_roles(fixture)),
        available_evidence_refs=tuple(item.evidence_id for item in fixture["bundle"].evidence),
        verified_claims=dict(claims),
        completed_node_ids=tuple(completed),
        observation_refs=tuple(observations),
        ready_node_ids=ready,
        field_origin="host_derived",
    )


def admit_proposal(
    *,
    fixture: Mapping[str, Any],
    candidate: Mapping[str, Any],
    state: Mapping[str, Any],
    proposal: Mapping[str, Any],
    registry: Any = None,
) -> tuple[Any, ...]:
    """Validate submitted semantic fields, not a generator's expected Envelope."""
    registry = registry or catalog_operation_registry()
    _require(
        proposal.get("field_origin") == "deterministic_fixture" and "qualified" not in proposal,
        "admission.provenance",
        "caller qualification or fabricated model ownership",
    )
    _require(
        proposal["task_id"] == fixture["task_id"]
        and proposal["candidate_id"] == candidate["candidate_id"]
        and proposal["state_id"] == state["id"]
        and proposal["sequence"] == state["sequence"],
        "admission.current_state",
        "proposal does not bind current State",
    )
    _require(
        proposal["node_id"] in state["ready_node_ids"], "admission.readiness", "node is not ready"
    )
    nodes = {node.node_id: node for node in candidate["program"].nodes}
    node = nodes[proposal["node_id"]]
    definition = registry.validate_node_contract(node)
    inputs, lineage, semantic, operands = _typed_inputs(
        fixture=fixture,
        node=node,
        claims=state["verified_claims"],
        available_evidence=tuple(state["available_evidence_refs"]),
        registry=registry,
    )
    _require(
        proposal["operator_id"] == node.operator_id
        and proposal["operation_contract_hash"] == operation_semantic_contract_hash(definition),
        "admission.registered_operation",
        "operation semantic binding differs",
    )
    _require(
        canonical_json_bytes(proposal["operands"]) == canonical_json_bytes(operands)
        and tuple(proposal["evidence_refs"]) == lineage
        and proposal["expected_semantic"] == semantic,
        "admission.typed_semantics",
        "submitted operands, support, or intended Claim semantics differ",
    )
    expected_claims = tuple(state["verified_claims"][ref]["claim_id"] for ref in node.dependencies)
    _require(
        tuple(proposal["claim_refs"]) == expected_claims
        and proposal["decision_basis"]
        == {
            "relation": "requires",
            "evidence_refs": list(lineage),
            "claim_refs": list(expected_claims),
        },
        "admission.decision_basis",
        "decision basis does not bind actual inputs",
    )
    return node, definition, inputs, lineage, semantic


def run_candidate(
    *,
    fixture: Mapping[str, Any],
    candidate: Mapping[str, Any],
    writer: DurableArtifactWriter | None = None,
    output_root: str | Path | None = None,
    registry: Any = None,
) -> dict[str, Any]:
    registry = registry or catalog_operation_registry()
    if writer is None:
        _require(
            output_root is not None, "runtime.output_root", "output_root or writer is required"
        )
        writer = DurableArtifactWriter(output_root)
        writer.create_root()
    program, schedule = candidate["program"], tuple(candidate["schedule"])
    _require(
        0 < len(schedule) <= 10
        and len(schedule) == len(set(schedule))
        and set(schedule) == {node.node_id for node in program.nodes},
        "runtime.bound",
        "schedule is outside the predeclared finite bound",
    )
    _require(
        candidate["task_id"] == fixture["task_id"],
        "runtime.task",
        "candidate belongs to another task",
    )
    _require(
        candidate["scope_binding_id"] == fixture["scope_bindings"]["scope_binding_id"]
        and candidate["field_provenance"]["program"] == "deterministic_fixture"
        and not candidate["field_provenance"]["model_proposed_fields"]
        and "qualified" not in candidate,
        "runtime.source_binding",
        "candidate source scope or field ownership differs",
    )
    comparability = _comparability(_roles(fixture))
    prefix = f"runtime/{fixture['fixture_id']}/{candidate['group']}"
    writer.ensure_directory(prefix)
    claims: dict[str, Any] = {}
    completed: list[str] = []
    observations: list[str] = []
    step_paths: list[dict[str, str]] = []
    state = _state(fixture, candidate, claims, completed, observations)
    writer.write_json(f"{prefix}/state_00.json", state)
    for index, node_id in enumerate(schedule):
        node = next(node for node in program.nodes if node.node_id == node_id)
        inputs, lineage, semantic, operands = _typed_inputs(
            fixture=fixture,
            node=node,
            claims=claims,
            available_evidence=tuple(state["available_evidence_refs"]),
            registry=registry,
        )
        claim_refs = tuple(claims[ref]["claim_id"] for ref in node.dependencies)
        proposal = _record(
            "proposal",
            task_id=fixture["task_id"],
            candidate_id=candidate["candidate_id"],
            state_id=state["id"],
            sequence=index,
            node_id=node_id,
            operator_id=node.operator_id,
            operation_contract_hash=operation_semantic_contract_hash(
                registry.require(node.operator_id)
            ),
            operands=operands,
            evidence_refs=lineage,
            claim_refs=claim_refs,
            decision_basis={
                "relation": "requires",
                "evidence_refs": list(lineage),
                "claim_refs": list(claim_refs),
            },
            expected_semantic=semantic,
            field_origin="deterministic_fixture",
        )
        paths = {
            name: f"{prefix}/{name}_{index:02d}.json"
            for name in ("proposal", "receipt", "execution", "observation", "update")
        }
        proposal_bytes = canonical_json_bytes(proposal)
        file_event, directory_event = writer.write_bytes(paths["proposal"], proposal_bytes)
        receipt = _record(
            "receipt",
            task_id=fixture["task_id"],
            candidate_id=candidate["candidate_id"],
            state_id=state["id"],
            proposal_id=proposal["id"],
            sequence=index,
            proposal_path=paths["proposal"],
            proposal_sha256=hashlib.sha256(proposal_bytes).hexdigest(),
            proposal_byte_count=len(proposal_bytes),
            proposal_file_fsync_event=file_event,
            proposal_directory_fsync_event=directory_event,
            receipt_file_fsync_event=len(writer.events) + 1,
            receipt_directory_fsync_event=len(writer.events) + 2,
            admission_event=len(writer.events) + 3,
            dispatch_event=len(writer.events) + 4,
            field_origin="host_derived",
        )
        writer.write_json(paths["receipt"], receipt)
        _require(
            writer.read_bytes(paths["proposal"]) == proposal_bytes
            and writer.read_bytes(paths["receipt"]) == canonical_json_bytes(receipt),
            "runtime.durable_commitment",
            "committed bytes changed before admission",
        )
        persisted_proposal = json.loads(writer.read_bytes(paths["proposal"]))
        node, definition, inputs, lineage, semantic = admit_proposal(
            fixture=fixture,
            candidate=candidate,
            state=state,
            proposal=persisted_proposal,
            registry=registry,
        )
        _require(
            writer._event("typed_admission", paths["receipt"]) == receipt["admission_event"],
            "runtime.admission_order",
            "admission did not follow durable receipt",
        )
        _require(
            writer._event("action_dispatch", paths["receipt"]) == receipt["dispatch_event"],
            "runtime.dispatch_order",
            "dispatch did not follow admission",
        )
        output = definition.executor.execute(inputs, node.parameters)
        registry.validate_output(definition, output)
        execution = _record(
            "execution",
            task_id=fixture["task_id"],
            candidate_id=candidate["candidate_id"],
            proposal_id=proposal["id"],
            state_id=state["id"],
            node_id=node_id,
            sequence=index,
            operator_id=node.operator_id,
            succeeded=True,
            output=output,
            dispatch_event=receipt["dispatch_event"],
            field_origin="host_derived",
        )
        writer.write_json(paths["execution"], execution)
        observation = _record(
            "observation",
            task_id=fixture["task_id"],
            candidate_id=candidate["candidate_id"],
            execution_id=execution["id"],
            state_id=state["id"],
            sequence=index,
            output=output,
            field_origin="host_derived",
        )
        writer.write_json(paths["observation"], observation)
        claim = {
            "claim_id": _claim_id(candidate, node_id),
            "producer_node_id": node_id,
            "operator_id": node.operator_id,
            "status": "verified",
            "output": output,
            "semantic": semantic,
            "evidence_refs": lineage,
            "support_observation_id": observation["id"],
            "field_origin": "deterministic_fixture",
        }
        update = _record(
            "update",
            task_id=fixture["task_id"],
            candidate_id=candidate["candidate_id"],
            proposal_id=proposal["id"],
            execution_id=execution["id"],
            observation_id=observation["id"],
            state_id=state["id"],
            sequence=index,
            accepted_claim=claim,
            field_origin="deterministic_fixture",
        )
        # The proposed update is admitted only after the actual persisted Observation.
        actual_observation = json.loads(writer.read_bytes(paths["observation"]))
        _require(
            claim["output"] == actual_observation["output"]
            and claim["support_observation_id"] == actual_observation["id"]
            and claim["status"] == "verified",
            "runtime.update_admission",
            "unsupported Claim update",
        )
        writer.write_json(paths["update"], update)
        claims[node_id] = claim
        completed.append(node_id)
        observations.append(observation["id"])
        state = _state(fixture, candidate, claims, completed, observations)
        writer.write_json(f"{prefix}/state_{index + 1:02d}.json", state)
        step_paths.append(paths)
    final_claim = claims[program.output_node_id]
    _require(
        final_claim["semantic"]["kind"] == "absolute_growth_spread",
        "runtime.final_claim",
        "missing absolute spread",
    )
    evidence = {item.evidence_id: item for item in fixture["bundle"].evidence}
    final = _record(
        "final",
        task_id=fixture["task_id"],
        candidate_id=candidate["candidate_id"],
        state_id=state["id"],
        producer_claim_id=final_claim["claim_id"],
        answer={
            "result": final_claim["output"],
            "citations": [
                {
                    "evidence_id": ref,
                    "source_id": evidence[ref].source.source_id,
                    "source_locator": evidence[ref].source_locator.model_dump(
                        mode="json", exclude_none=True
                    ),
                }
                for ref in fixture["package"].binding_snapshot.evidence_ids
            ],
        },
        comparability=comparability,
        field_origin="deterministic_fixture",
    )
    final_path, events_path = f"{prefix}/final.json", f"{prefix}/events.json"
    writer.write_json(final_path, final)
    writer.write_json(events_path, {"events": tuple(writer.events), "field_origin": "host_derived"})
    return {
        "candidate_id": candidate["candidate_id"],
        "fixture_id": fixture["fixture_id"],
        "task_id": fixture["task_id"],
        "group": candidate["group"],
        "runtime_prefix": prefix,
        "schedule": schedule,
        "step_paths": tuple(step_paths),
        "final_path": final_path,
        "events_path": events_path,
        "actual_registered_action_count": len(schedule),
        "execution_status": "completed",
        "field_origin": "host_derived",
    }
