"""Independent persisted-trajectory replay for the finite typed candidate family.

This module does not import the controller, its admission helper, a historical
trajectory validator, or a candidate executor.  It rebuilds arithmetic through
registered Oracle implementations and rebuilds obligation witnesses from actual
producer/consumer references.  Oracle work is never attributed to the candidate.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from collections.abc import Mapping
from decimal import Decimal
from typing import Any

from trusted_synthesis.canonical_json import canonical_json_bytes, strict_canonical_hash
from trusted_synthesis.core.evaluation.answer import CandidateAnswerNormalizer
from trusted_synthesis.core.operations.program import TaskProgramOracleVerifier
from trusted_synthesis.core.operations.registry import operation_semantic_contract_hash
from trusted_synthesis.core.operations.schema import OperationInput
from trusted_synthesis.experiments.qa_semantic_depth_three_catalog_integration.catalog import (
    catalog_operation_registry,
)


class CandidateReplayError(ValueError):
    def __init__(self, stage: str, message: str) -> None:
        super().__init__(message)
        self.stage = stage


def _check(condition: bool, stage: str, message: str) -> None:
    if not condition:
        raise CandidateReplayError(stage, message)


_FIELDS = {
    "state": {
        "task_id",
        "candidate_id",
        "sequence",
        "available_evidence_refs",
        "source_scope_binding_id",
        "source_comparability",
        "verified_claims",
        "completed_node_ids",
        "observation_refs",
        "ready_node_ids",
        "field_origin",
    },
    "proposal": {
        "task_id",
        "candidate_id",
        "state_id",
        "sequence",
        "node_id",
        "operator_id",
        "operation_contract_hash",
        "operands",
        "evidence_refs",
        "claim_refs",
        "decision_basis",
        "expected_semantic",
        "field_origin",
    },
    "receipt": {
        "task_id",
        "candidate_id",
        "state_id",
        "proposal_id",
        "sequence",
        "proposal_path",
        "proposal_sha256",
        "proposal_byte_count",
        "proposal_file_fsync_event",
        "proposal_directory_fsync_event",
        "receipt_file_fsync_event",
        "receipt_directory_fsync_event",
        "admission_event",
        "dispatch_event",
        "field_origin",
    },
    "execution": {
        "task_id",
        "candidate_id",
        "proposal_id",
        "state_id",
        "node_id",
        "sequence",
        "operator_id",
        "succeeded",
        "output",
        "dispatch_event",
        "field_origin",
    },
    "observation": {
        "task_id",
        "candidate_id",
        "execution_id",
        "state_id",
        "sequence",
        "output",
        "field_origin",
    },
    "update": {
        "task_id",
        "candidate_id",
        "proposal_id",
        "execution_id",
        "observation_id",
        "state_id",
        "sequence",
        "accepted_claim",
        "field_origin",
    },
    "final": {
        "task_id",
        "candidate_id",
        "state_id",
        "producer_claim_id",
        "answer",
        "comparability",
        "field_origin",
    },
}


def _read(writer: Any, path: str, kind: str) -> dict[str, Any]:
    raw = writer.read_bytes(path)
    value = json.loads(raw)
    _check(
        isinstance(value, dict) and set(value) == _FIELDS[kind] | {"id", "schema_version"},
        "replay.record_schema",
        f"{kind} has missing or injected fields",
    )
    _check(
        raw == canonical_json_bytes(value),
        "replay.canonical_bytes",
        "record bytes are not canonical",
    )
    _check(
        value["schema_version"] == f"typed_candidate_{kind}.v1"
        and value["id"]
        == strict_canonical_hash(
            {key: item for key, item in value.items() if key != "id"},
            prefix=f"typed_candidate_{kind}:",
        ),
        "replay.record_identity",
        f"{kind} identity differs",
    )
    expected_origin = (
        "deterministic_fixture" if kind in {"proposal", "update", "final"} else "host_derived"
    )
    _check(
        value["field_origin"] == expected_origin,
        "replay.field_provenance",
        "fabricated field ownership",
    )
    return value


def _source(fixture: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    package, bundle = fixture["package"], fixture["bundle"]
    scope = fixture["scope_bindings"]
    for field, value in (
        ("row_bytes", fixture["row"]),
        ("package_bytes", package),
        ("task_bytes", package.task),
        ("evidence_universe_bytes", bundle),
        ("answer_oracle_bytes", package.task.oracle),
    ):
        payload = canonical_json_bytes(value)
        _check(
            scope[field]
            == {"sha256": hashlib.sha256(payload).hexdigest(), "byte_count": len(payload)},
            "replay.frozen_source_bytes",
            "original question, package, Evidence, or answer Oracle bytes changed",
        )
    _check(
        scope["question"] == package.task.public.instruction
        and scope["answer_schema"] == package.semantic_plan.answer_schema
        and scope["role_bindings"] == package.binding_snapshot.role_bindings,
        "replay.frozen_task_contract",
        "question, answer schema, or role bindings differ from frozen scope",
    )
    evidence = {item.evidence_id: item for item in bundle.evidence}
    snapshot = package.binding_snapshot
    _check(
        package.task.task_id == fixture["task_id"]
        and snapshot.bundle_id == bundle.bundle_id
        and set(snapshot.evidence_ids) == set(evidence)
        and set(package.task.oracle.gold_evidence_ids) == set(evidence),
        "replay.frozen_task_source",
        "fixed task, binding, or Evidence universe differs",
    )
    _check(
        tuple(evidence[ref].evidence_version_id for ref in snapshot.evidence_ids)
        == snapshot.evidence_version_ids
        and tuple(evidence[ref].provenance.source_record_id for ref in snapshot.evidence_ids)
        == snapshot.source_record_ids,
        "replay.evidence_versions",
        "Evidence version or source record binding differs",
    )
    required = {"revenue_earlier", "revenue_later", "income_earlier", "income_later"}
    _check(
        set(snapshot.role_bindings) == required
        and all(len(refs) == 1 and refs[0] in evidence for refs in snapshot.role_bindings.values()),
        "replay.role_binding",
        "task role binding is not total and exact",
    )
    roles = {role: evidence[refs[0]] for role, refs in snapshot.role_bindings.items()}
    _check(
        len({item.evidence_id for item in roles.values()}) == 4,
        "replay.role_binding",
        "different task roles share an Evidence object",
    )
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
    for metric, predicate in (("revenue", "revenue"), ("income", "operating_income")):
        first, second = roles[metric + "_earlier"], roles[metric + "_later"]
        checks[metric + "_metric"] = first.predicate == second.predicate == predicate
        checks[metric + "_definition"] = first.definition == second.definition
        checks[metric + "_period_order"] = (
            first.domain_context["economic_period_sort_key"]
            < second.domain_context["economic_period_sort_key"]
        )
        _check(
            Decimal(str(first.payload.value)) > 0,
            "replay.growth_precondition",
            "frozen growth base is not positive",
        )
    _check(
        all(checks.values()),
        "replay.comparability",
        "source entity, period, metric, definition, or unit differs",
    )
    return (
        evidence,
        roles,
        {
            "checks": checks,
            "evidence_refs": [item.evidence_id for item in items],
            "field_origin": "host_derived",
        },
    )


def admit_candidate_source(
    *, fixture: Mapping[str, Any], candidate: Mapping[str, Any], registry: Any = None
) -> dict[str, Any]:
    """Independently check source types, without executing or choosing by outcomes."""
    registry = registry or catalog_operation_registry()
    evidence, roles, _ = _source(fixture)
    role_by_ref = {item.evidence_id: role for role, item in roles.items()}
    inferred: dict[str, tuple[str, str]] = {}
    lineage: dict[str, set[str]] = {}
    nodes = candidate["program"].nodes
    counts = Counter(node.operator_id for node in nodes)
    _check(
        counts["growth"] == 2
        and counts["signed_percentage_point_gap"] == counts["absolute_percentage_point_gap"] == 1
        and counts["lookup"] in {0, 4}
        and len(nodes) == 4 + counts["lookup"],
        "replay.finite_language",
        "candidate is outside the preregistered four/eight-node source forms",
    )
    for node in nodes:
        definition = registry.validate_node_contract(node)
        _check(
            not node.parameters and len(node.input_refs) == len(definition.input_role_contract),
            "replay.source_input_contract",
            "source arity or parameters differ",
        )
        input_types, support = [], set()
        for ref in node.input_refs:
            if ref.kind.value == "evidence":
                _check(
                    ref.ref_id in evidence and ref.ref_id in role_by_ref,
                    "replay.visible_evidence",
                    "future or cross-task Evidence in candidate source",
                )
                input_types.append(("evidence_scalar", role_by_ref[ref.ref_id]))
                support.add(ref.ref_id)
                expected_selector = None if node.operator_id == "lookup" else "value"
            else:
                _check(
                    ref.ref_id in inferred,
                    "replay.verified_claim",
                    "future or absent candidate producer",
                )
                input_types.append(inferred[ref.ref_id])
                support.update(lineage[ref.ref_id])
                expected_selector = (
                    "payload.value" if inferred[ref.ref_id][0] == "evidence_scalar" else "value"
                )
            _check(
                ref.selector == expected_selector,
                "replay.source_selector",
                "candidate selector changes source meaning",
            )
        if node.operator_id == "lookup":
            _check(
                node.input_refs[0].kind.value == "evidence",
                "replay.lookup",
                "lookup is not source-backed",
            )
            inferred[node.node_id] = input_types[0]
        elif node.operator_id == "growth":
            pairs: dict[tuple[tuple[str, str], ...], str] = {
                (
                    ("evidence_scalar", "revenue_earlier"),
                    ("evidence_scalar", "revenue_later"),
                ): "revenue",
                (
                    ("evidence_scalar", "income_earlier"),
                    ("evidence_scalar", "income_later"),
                ): "income",
            }
            _check(
                tuple(input_types) in pairs,
                "replay.growth_roles",
                "reidentified growth changes period/metric roles",
            )
            inferred[node.node_id] = ("growth_percent", pairs[tuple(input_types)])
        elif node.operator_id == "signed_percentage_point_gap":
            _check(
                input_types == [("growth_percent", "income"), ("growth_percent", "revenue")],
                "replay.signed_operand_roles",
                "reidentified signed operands reverse reference/observed roles",
            )
            inferred[node.node_id] = ("signed_growth_gap", "revenue_minus_income")
        else:
            _check(
                input_types == [("signed_growth_gap", "revenue_minus_income")],
                "replay.absolute_input",
                "absolute input is not the typed signed gap",
            )
            inferred[node.node_id] = ("absolute_growth_spread", "percentage_points")
        lineage[node.node_id] = support
    output_id = candidate["program"].output_node_id
    _check(
        inferred[output_id] == ("absolute_growth_spread", "percentage_points")
        and lineage[output_id] == set(evidence),
        "replay.source_final",
        "source route does not discharge exact task",
    )
    _check(
        candidate["scope_binding_id"] == fixture["scope_bindings"]["scope_binding_id"]
        and candidate["field_provenance"]["program"] == "deterministic_fixture"
        and not candidate["field_provenance"]["model_proposed_fields"]
        and "qualified" not in candidate,
        "replay.source_provenance",
        "source scope or controller ownership differs",
    )
    return {
        "source_admissible": True,
        "typed_construction_status": "constructed",
        "operation_executor_invocations": 0,
        "operation_oracle_invocations": 0,
    }


def _pick(value: Any, selector: str | None) -> Any:
    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="json", exclude_none=True)
    if selector is not None:
        for segment in selector.split("."):
            _check(
                isinstance(value, dict) and segment in value,
                "replay.selector",
                "input selector does not resolve",
            )
            value = value[segment]
    return value


def _inputs_and_semantics(
    node: Any,
    proposal: Mapping[str, Any],
    evidence: Mapping[str, Any],
    roles: Mapping[str, Any],
    verified: Mapping[str, Any],
    registry: Any,
) -> tuple[tuple[OperationInput, ...], list[str], dict[str, Any], list[dict[str, Any]]]:
    definition = registry.validate_node_contract(node)
    _check(
        not node.parameters, "replay.parameters", "parameters outside the finite source language"
    )
    _check(
        len(proposal["operands"]) == len(node.input_refs) == len(definition.input_role_contract),
        "replay.operand_arity",
        "registered operand cardinality differs",
    )
    role_by_ref = {item.evidence_id: role for role, item in roles.items()}
    operation_inputs, input_types, lineage, edges = [], [], [], []
    for position, (ref, operand) in enumerate(
        zip(node.input_refs, proposal["operands"], strict=True)
    ):
        _check(
            set(operand) == {"kind", "ref_id", "selector", "operand_role", "producer_claim_id"},
            "replay.operand_schema",
            "operand has extra or missing fields",
        )
        _check(
            (operand["kind"], operand["ref_id"], operand["selector"], operand["operand_role"])
            == (ref.kind.value, ref.ref_id, ref.selector, definition.input_role_contract[position]),
            "replay.operand_source_binding",
            "submitted operand differs from frozen candidate operation",
        )
        if ref.kind.value == "evidence":
            _check(
                ref.ref_id in evidence and ref.ref_id in role_by_ref,
                "replay.visible_evidence",
                "future or cross-task Evidence",
            )
            value = _pick(evidence[ref.ref_id].payload, ref.selector)
            input_type = {"kind": "evidence_scalar", "role": role_by_ref[ref.ref_id]}
            input_lineage, producer = [ref.ref_id], None
        else:
            _check(
                ref.ref_id in verified and verified[ref.ref_id]["status"] == "verified",
                "replay.verified_claim",
                "future, tentative, rejected, or invalidated Claim",
            )
            parent = verified[ref.ref_id]
            value = _pick(parent["output"], ref.selector)
            input_type, input_lineage, producer = (
                parent["semantic"],
                parent["evidence_refs"],
                parent["claim_id"],
            )
        _check(
            operand["producer_claim_id"] == producer,
            "replay.producer_binding",
            "operand names a false producer",
        )
        operation_inputs.append(OperationInput(ref_id=ref.ref_id, value=value))
        input_types.append(input_type)
        lineage.extend(input_lineage)
        edges.append(
            {
                "operand_position": position,
                "operand_role": operand["operand_role"],
                "input_kind": ref.kind.value,
                "input_ref": ref.ref_id,
                "selector": ref.selector,
                "producer_claim_id": producer,
                "evidence_refs": list(input_lineage),
            }
        )
    if node.operator_id == "lookup":
        _check(
            node.input_refs[0].kind.value == "evidence" and node.input_refs[0].selector is None,
            "replay.lookup",
            "lookup is not an Evidence payload projection",
        )
        semantic = input_types[0]
    elif node.operator_id == "growth":
        _check(
            all(value.get("kind") == "evidence_scalar" for value in input_types),
            "replay.growth_roles",
            "growth lacks scalar Evidence lineage",
        )
        earlier, later = (value["role"] for value in input_types)
        accepted_pairs = {
            ("revenue_earlier", "revenue_later"): "revenue",
            ("income_earlier", "income_later"): "income",
        }
        _check(
            (earlier, later) in accepted_pairs,
            "replay.growth_roles",
            "growth periods or metrics were reversed/substituted",
        )
        _check(
            all(
                ref.selector == ("value" if ref.kind.value == "evidence" else "payload.value")
                for ref in node.input_refs
            ),
            "replay.growth_selector",
            "growth does not select source scalar values",
        )
        semantic = {
            "kind": "growth_percent",
            "metric": accepted_pairs[(earlier, later)],
            "earlier_role": earlier,
            "later_role": later,
            "unit": "percent",
        }
    elif node.operator_id == "signed_percentage_point_gap":
        _check(
            [value.get("kind") for value in input_types] == ["growth_percent", "growth_percent"]
            and [value.get("metric") for value in input_types] == ["income", "revenue"],
            "replay.signed_operand_roles",
            "signed gap reference and observed metric roles differ",
        )
        _check(
            all(ref.selector == "value" for ref in node.input_refs),
            "replay.gap_selector",
            "gap selector differs",
        )
        semantic = {
            "kind": "signed_growth_gap",
            "reference_metric": "income",
            "observed_metric": "revenue",
            "unit": "percentage_points",
        }
    elif node.operator_id == "absolute_percentage_point_gap":
        _check(
            input_types[0].get("kind") == "signed_growth_gap"
            and node.input_refs[0].selector == "value",
            "replay.absolute_input",
            "absolute spread lacks a verified signed gap",
        )
        semantic = {"kind": "absolute_growth_spread", "unit": "percentage_points"}
    else:
        raise CandidateReplayError(
            "replay.finite_language", "operation is outside the frozen source family"
        )
    unique = list(dict.fromkeys(lineage))
    registry.validate_inputs(definition, tuple(operation_inputs))
    registry.validate_compatibility(
        definition, tuple(evidence[ref] for ref in unique), node.parameters
    )
    _check(
        proposal["expected_semantic"] == semantic and proposal["evidence_refs"] == unique,
        "replay.typed_claim_intent",
        "proposed semantics or evidence support differs",
    )
    return tuple(operation_inputs), unique, semantic, edges


def _qa(
    fixture: Mapping[str, Any], final: Mapping[str, Any], evidence: Mapping[str, Any], registry: Any
) -> dict[str, Any]:
    package = fixture["package"]
    normalizer = CandidateAnswerNormalizer()
    schema_valid, schema_failures = normalizer.validate_schema(package.task.public, final["answer"])
    oracle = TaskProgramOracleVerifier(registry).derive_expected(
        package.task.oracle.task_program, dict(evidence)
    )
    expected = normalizer.normalize_oracle(
        package.task,
        oracle.final_output,
        tuple(evidence[ref] for ref in package.task.oracle.gold_evidence_ids),
        node_outputs=oracle.node_outputs,
    )
    actual = normalizer.normalize_candidate(package.task.public, final["answer"])
    answer_valid = schema_valid and normalizer.equivalent(actual, expected)
    citations = final["answer"].get("citations", [])
    expected_citations = {
        ref: {
            "evidence_id": ref,
            "source_id": item.source.source_id,
            "source_locator": item.source_locator.model_dump(mode="json", exclude_none=True),
        }
        for ref, item in evidence.items()
    }
    citation_valid = isinstance(citations, list) and len(citations) == len(expected_citations)
    if citation_valid:
        ids = [item.get("evidence_id") if isinstance(item, dict) else None for item in citations]
        citation_valid = len(set(ids)) == len(ids) and set(ids) == set(expected_citations)
        citation_valid = citation_valid and all(
            item == expected_citations[item["evidence_id"]] for item in citations
        )
    return {
        "qa_valid": bool(answer_valid and citation_valid),
        "answer_schema_valid": schema_valid,
        "answer_valid": answer_valid,
        "citation_valid": bool(citation_valid),
        "answer_schema_failures": schema_failures,
        "independent_oracle_result": oracle.final_output,
        "answer_oracle_node_replay_count": len(oracle.node_outputs),
    }


def _trajectory(
    *,
    writer: Any,
    fixture: Mapping[str, Any],
    candidate: Mapping[str, Any],
    result: Mapping[str, Any],
    registry: Any,
    evidence: Mapping[str, Any],
    roles: Mapping[str, Any],
    comparability: Mapping[str, Any],
    final: Mapping[str, Any],
) -> dict[str, Any]:
    _check(
        "qualified" not in result
        and result.get("field_origin") == "host_derived"
        and not result.get("model_proposed_fields"),
        "replay.caller_authority",
        "caller-supplied qualification or model ownership",
    )
    prefix, schedule = str(result["runtime_prefix"]), tuple(result["schedule"])
    program = candidate["program"]
    nodes = {node.node_id: node for node in program.nodes}
    _check(
        result["candidate_id"] == candidate["candidate_id"]
        and result["task_id"] == fixture["task_id"]
        and tuple(candidate["schedule"]) == schedule
        and 0 < len(schedule) <= 10
        and len(schedule) == len(set(schedule))
        and set(schedule) == set(nodes)
        and len(result["step_paths"]) == len(schedule),
        "replay.candidate_bound",
        "candidate or finite schedule differs",
    )
    _check(
        result["events_path"] == f"{prefix}/events.json"
        and result["final_path"] == f"{prefix}/final.json",
        "replay.path_domain",
        "Final or event log crosses its own candidate domain",
    )
    event_bytes = writer.read_bytes(result["events_path"])
    event_payload = json.loads(event_bytes)
    _check(
        event_bytes == canonical_json_bytes(event_payload)
        and set(event_payload) == {"events", "field_origin"},
        "replay.event_log",
        "event log schema or bytes differ",
    )
    events = event_payload["events"]
    _check(
        event_payload.get("field_origin") == "host_derived"
        and [event["event_ordinal"] for event in events] == list(range(1, len(events) + 1)),
        "replay.event_log",
        "event log ordinals or origin differ",
    )
    by_ordinal = {event["event_ordinal"]: event for event in events}
    verified: dict[str, Any] = {}
    completed: list[str] = []
    observations: list[str] = []
    retained = []
    states = [
        _read(writer, f"{prefix}/state_{index:02d}.json", "state")
        for index in range(len(schedule) + 1)
    ]
    for index, node_id in enumerate(schedule):
        state, next_state, node = states[index], states[index + 1], nodes[node_id]
        ready = [
            item.node_id
            for item in program.nodes
            if item.node_id not in completed and set(item.dependencies) <= set(completed)
        ]
        _check(
            state["task_id"] == fixture["task_id"]
            and state["candidate_id"] == candidate["candidate_id"]
            and state["sequence"] == index
            and state["source_scope_binding_id"] == fixture["scope_bindings"]["scope_binding_id"]
            and state["source_comparability"] == comparability
            and state["verified_claims"] == verified
            and state["completed_node_ids"] == completed
            and state["observation_refs"] == observations
            and state["ready_node_ids"] == ready
            and state["available_evidence_refs"]
            == [item.evidence_id for item in fixture["bundle"].evidence],
            "replay.current_state",
            "current State is not derived from prior admitted updates",
        )
        _check(
            node_id in ready,
            "replay.dependency_ready",
            "selected action has unresolved dependencies",
        )
        paths = result["step_paths"][index]
        _check(
            set(paths) == {"proposal", "receipt", "execution", "observation", "update"}
            and all(path == f"{prefix}/{kind}_{index:02d}.json" for kind, path in paths.items()),
            "replay.path_domain",
            "step references another candidate or sequence",
        )
        records = {kind: _read(writer, path, kind) for kind, path in paths.items()}
        proposal, receipt, execution, observation, update = (
            records[kind] for kind in ("proposal", "receipt", "execution", "observation", "update")
        )
        for value in records.values():
            _check(
                value["task_id"] == fixture["task_id"]
                and value["candidate_id"] == candidate["candidate_id"]
                and value["state_id"] == state["id"]
                and value["sequence"] == index,
                "replay.record_lineage",
                "step does not bind its current State/task",
            )
        definition = registry.validate_node_contract(node)
        _check(
            proposal["node_id"] == execution["node_id"] == node_id
            and proposal["operator_id"] == execution["operator_id"] == node.operator_id
            and proposal["operation_contract_hash"] == operation_semantic_contract_hash(definition),
            "replay.operation_binding",
            "actual operation differs from its registered contract",
        )
        inputs, lineage, semantic, edges = _inputs_and_semantics(
            node, proposal, evidence, roles, verified, registry
        )
        claims_used = [verified[ref]["claim_id"] for ref in node.dependencies]
        _check(
            proposal["claim_refs"] == claims_used
            and proposal["decision_basis"]
            == {"relation": "requires", "evidence_refs": lineage, "claim_refs": claims_used},
            "replay.decision_basis",
            "decision basis does not describe actual dependencies",
        )
        committed_bytes = writer.read_bytes(paths["proposal"])
        _check(
            receipt["proposal_id"] == proposal["id"]
            and receipt["proposal_path"] == paths["proposal"]
            and receipt["proposal_sha256"] == hashlib.sha256(committed_bytes).hexdigest()
            and receipt["proposal_byte_count"] == len(committed_bytes),
            "replay.preaction_commitment",
            "receipt does not bind actual persisted proposal",
        )
        expected_events = [
            (receipt["proposal_file_fsync_event"], "file_fsync", paths["proposal"]),
            (receipt["proposal_directory_fsync_event"], "directory_fsync", paths["proposal"]),
            (receipt["receipt_file_fsync_event"], "file_fsync", paths["receipt"]),
            (receipt["receipt_directory_fsync_event"], "directory_fsync", paths["receipt"]),
            (receipt["admission_event"], "typed_admission", paths["receipt"]),
            (receipt["dispatch_event"], "action_dispatch", paths["receipt"]),
        ]
        state_events = [
            event
            for event in events
            if event["relative_path"] == f"{prefix}/state_{index:02d}.json"
        ]
        _check(
            len(state_events) == 2
            and [event["kind"] for event in state_events] == ["file_fsync", "directory_fsync"]
            and state_events[1]["event_ordinal"] < receipt["proposal_file_fsync_event"],
            "replay.state_precedes_action",
            "current public State was not durable before commitment",
        )
        ordinals = [ordinal for ordinal, _, _ in expected_events]
        _check(
            ordinals == list(range(ordinals[0], ordinals[0] + 6)),
            "replay.preaction_order",
            "fsync, admission and dispatch are out of order",
        )
        for ordinal, kind, path in expected_events:
            _check(
                by_ordinal.get(ordinal)
                == {"event_ordinal": ordinal, "kind": kind, "relative_path": path},
                "replay.actual_preaction_events",
                "persisted fsync/admission/dispatch event is missing",
            )
        _check(
            execution["proposal_id"] == proposal["id"]
            and execution["dispatch_event"] == receipt["dispatch_event"]
            and execution["succeeded"] is True
            and observation["execution_id"] == execution["id"]
            and update["proposal_id"] == proposal["id"]
            and update["execution_id"] == execution["id"]
            and update["observation_id"] == observation["id"],
            "replay.execution_observation_chain",
            "execution, Observation or update lacks its actual parent",
        )
        replay = definition.oracle_verifier.verify(inputs, node.parameters, execution["output"])
        _check(
            replay.passed and replay.expected_output is not None,
            "replay.registered_oracle",
            "registered independent Oracle rejected actual output",
        )
        registry.validate_output(definition, replay.expected_output)
        _check(
            observation["output"] == replay.expected_output,
            "replay.observation_output",
            "Observation does not match actual output",
        )
        claim = update["accepted_claim"]
        expected_claim_id = strict_canonical_hash(
            {"candidate_id": candidate["candidate_id"], "node_id": node_id},
            prefix="typed_candidate_claim:",
        )
        expected_claim = {
            "claim_id": expected_claim_id,
            "producer_node_id": node_id,
            "operator_id": node.operator_id,
            "status": "verified",
            "output": replay.expected_output,
            "semantic": semantic,
            "evidence_refs": lineage,
            "support_observation_id": observation["id"],
            "field_origin": "deterministic_fixture",
        }
        _check(
            claim == expected_claim,
            "replay.observation_update",
            "Claim status, semantics, output or Observation support differs",
        )
        # Prove durable actual output/Observation precedes update and next State.
        last = receipt["dispatch_event"]
        for path in (
            paths["execution"],
            paths["observation"],
            paths["update"],
            f"{prefix}/state_{index + 1:02d}.json",
        ):
            event_ids = [
                event["event_ordinal"]
                for event in events
                if event["relative_path"] == path
                and event["kind"] in {"file_fsync", "directory_fsync"}
            ]
            _check(
                len(event_ids) == 2 and event_ids[0] > last and event_ids[1] == event_ids[0] + 1,
                "replay.observation_update_order",
                "actual durable execution/Observation/update/State order differs",
            )
            last = event_ids[1]
        verified[node_id] = expected_claim
        completed.append(node_id)
        observations.append(observation["id"])
        _check(
            next_state["verified_claims"] == verified,
            "replay.next_state",
            "next State does not commit exactly the admitted Claim",
        )
        retained.append(
            {
                "node_id": node_id,
                "operator_id": node.operator_id,
                "operation_contract_hash": operation_semantic_contract_hash(definition),
                "semantic_version": definition.semantic_version,
                "formula_id": definition.formula_id,
                "claim_id": expected_claim_id,
                "claim_semantic": semantic,
                "output": replay.expected_output,
                "input_edges": edges,
                "evidence_refs": lineage,
                "observation_id": observation["id"],
            }
        )
    terminal = states[-1]
    _check(
        terminal["sequence"] == len(schedule)
        and terminal["ready_node_ids"] == []
        and terminal["completed_node_ids"] == completed
        and terminal["observation_refs"] == observations,
        "replay.terminal_state",
        "terminal State has unresolved work",
    )
    output = verified[program.output_node_id]
    _check(
        final["task_id"] == fixture["task_id"]
        and final["candidate_id"] == candidate["candidate_id"]
        and final["state_id"] == terminal["id"]
        and final["producer_claim_id"] == output["claim_id"]
        and output["semantic"] == {"kind": "absolute_growth_spread", "unit": "percentage_points"}
        and final["answer"]["result"] == output["output"]
        and set(output["evidence_refs"]) == set(evidence),
        "replay.final_grounding",
        "Final does not use its own fully grounded absolute-spread Claim",
    )
    _check(
        final["comparability"] == comparability,
        "replay.comparability_witness",
        "comparability evidence differs",
    )
    growth = {
        entry["claim_semantic"]["metric"]: entry
        for entry in retained
        if entry["claim_semantic"]["kind"] == "growth_percent"
    }
    signed = [entry for entry in retained if entry["claim_semantic"]["kind"] == "signed_growth_gap"]
    absolute = [
        entry for entry in retained if entry["claim_semantic"]["kind"] == "absolute_growth_spread"
    ]
    _check(
        set(growth) == {"income", "revenue"} and len(signed) == len(absolute) == 1,
        "replay.obligation_coverage",
        "required typed growth and exact merge obligations are missing",
    )
    mapping = [
        {
            "obligation": "comparability",
            "discharged": True,
            "host_source_checks": comparability,
            "not_a_registered_candidate_operation": True,
        },
        *[
            {
                "obligation": metric + "_growth",
                "discharged": True,
                "claim_ids": [growth[metric]["claim_id"]],
                "evidence_refs": growth[metric]["evidence_refs"],
            }
            for metric in ("revenue", "income")
        ],
        {
            "obligation": "exact_absolute_growth_difference",
            "discharged": True,
            "claim_ids": [signed[0]["claim_id"], absolute[0]["claim_id"]],
            "evidence_refs": output["evidence_refs"],
        },
        {
            "obligation": "final_grounding",
            "discharged": True,
            "claim_ids": [output["claim_id"]],
            "final_id": final["id"],
            "evidence_refs": output["evidence_refs"],
        },
    ]
    return {
        "trajectory_valid": True,
        "actual_retained_typed_structure": retained,
        "evidence_to_obligation_discharge": mapping,
        "trajectory_oracle_node_replay_count": len(retained),
        "formal_projection_created": False,
        "quotient_class_count": None,
    }


def validate_candidate(
    *,
    writer: Any,
    fixture: Mapping[str, Any],
    candidate: Mapping[str, Any],
    result: Mapping[str, Any],
    registry: Any = None,
) -> dict[str, Any]:
    """Return separate QA/trajectory validity; caller truth labels confer no authority."""
    registry = registry or catalog_operation_registry()
    report: dict[str, Any] = {
        "candidate_id": candidate["candidate_id"],
        "fixture_id": fixture["fixture_id"],
        "qa_valid": False,
        "trajectory_valid": False,
        "qualified": False,
        "first_failure": None,
        "validator_implementation_status": "implemented",
        "field_origin": "host_derived",
        "answer_oracle_node_replay_count": 0,
        "trajectory_oracle_node_replay_count": 0,
        "actual_retained_typed_structure": [],
        "evidence_to_obligation_discharge": [],
        "formal_projection_created": False,
        "quotient_class_count": None,
    }
    try:
        evidence, roles, comparability = _source(fixture)
        final = _read(writer, result["final_path"], "final")
        report.update(_qa(fixture, final, evidence, registry))
        report.update(
            admit_candidate_source(fixture=fixture, candidate=candidate, registry=registry)
        )
        report.update(
            _trajectory(
                writer=writer,
                fixture=fixture,
                candidate=candidate,
                result=result,
                registry=registry,
                evidence=evidence,
                roles=roles,
                comparability=comparability,
                final=final,
            )
        )
        if not report["qa_valid"]:
            report["first_failure"] = {
                "stage": "qa.answer_or_citations",
                "reason": "frozen answer or citation contract failed",
            }
    except (OSError, ValueError, KeyError, TypeError, IndexError) as error:
        report["first_failure"] = {
            "stage": getattr(error, "stage", "replay.missing_or_invalid_artifact"),
            "reason": str(error),
        }
    report["qualified"] = report["qa_valid"] and report["trajectory_valid"]
    return report
