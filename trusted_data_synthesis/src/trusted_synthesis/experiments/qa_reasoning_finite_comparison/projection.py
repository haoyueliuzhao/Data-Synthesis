"""Read actual public records and apply the bounded, witnessed lookup contraction.

This module imports neither a candidate constructor nor a runtime/validator.  Its
input admission is supplied by the independently replayed frozen trajectory.
Record identities and serial bookkeeping are audited; actual semantic causes are
edges.  No operation executor or arithmetic Oracle is invoked here.
"""

from __future__ import annotations

import copy
import hashlib
import json
from collections.abc import Mapping, Sequence
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from trusted_synthesis.canonical_json import strict_canonical_hash

GRAPH_SCHEMA = "finite_public_behavior_graph.v1"
NODE_REQUIRED_FIELDS = {
    "task": ("contract", "field_origin"),
    "evidence": ("role", "record"),
    "host_comparability": ("checks", "field_origin"),
    "decision": ("relation", "expected_semantic", "field_origin"),
    "receipt": ("durable_preaction_commitment", "field_origin"),
    "operation": ("contract", "parameters", "succeeded", "field_origin"),
    "observation": ("output", "field_origin"),
    "claim": ("status", "semantic", "output", "field_origin"),
    "update": ("acceptance", "field_origin"),
    "state_effect": ("visibility_changed", "removed_claims", "modified_claims", "field_origin"),
    "obligation": ("name", "discharged", "field_origin"),
    "final": ("disposition", "answer", "field_origin"),
}
NODE_ALLOWED_FIELDS = {
    **NODE_REQUIRED_FIELDS,
    "operation": NODE_REQUIRED_FIELDS["operation"] + ("output",),
    "state_effect": NODE_REQUIRED_FIELDS["state_effect"]
    + ("available_evidence_before", "available_evidence_after"),
}
EDGE_KINDS = (
    "task_evidence",
    "host_support",
    "host_basis",
    "commitment",
    "dispatch",
    "observes",
    "grounds",
    "proposes_update",
    "accepts_claim",
    "causes_update",
    "produces_claim",
    "commits_effect",
    "adds_claim",
    "completes_operation",
    "observes_effect",
    "operand",
    "basis_evidence",
    "basis_claim",
    "claim_evidence",
    "fulfills",
    "obligation_evidence",
    "final_claim",
    "final_citation",
    "final_obligation",
)
TRANSPARENCY_CONDITIONS = (
    "registration",
    "value_and_source",
    "reference_substitution",
    "current_information",
    "no_extra_retained_effects",
)
SEMANTIC_FIELDS = {
    "evidence_scalar": ("kind", "role"),
    "growth_percent": ("kind", "metric", "earlier_role", "later_role", "unit"),
    "signed_growth_gap": ("kind", "reference_metric", "observed_metric", "unit"),
    "absolute_growth_spread": ("kind", "unit"),
}
OBLIGATIONS = (
    "comparability",
    "revenue_growth",
    "income_growth",
    "exact_absolute_growth_difference",
    "final_grounding",
)

_COMMON = {"id", "schema_version", "task_id", "candidate_id", "field_origin"}
_STEP = _COMMON | {"state_id", "sequence"}
_FIELDS = {
    "state": _COMMON
    | {
        "sequence",
        "source_scope_binding_id",
        "source_comparability",
        "available_evidence_refs",
        "verified_claims",
        "completed_node_ids",
        "observation_refs",
        "ready_node_ids",
    },
    "proposal": _STEP
    | {
        "node_id",
        "operator_id",
        "operation_contract_hash",
        "operands",
        "evidence_refs",
        "claim_refs",
        "decision_basis",
        "expected_semantic",
    },
    "receipt": _STEP
    | {
        "proposal_id",
        "proposal_path",
        "proposal_sha256",
        "proposal_byte_count",
        "proposal_file_fsync_event",
        "proposal_directory_fsync_event",
        "receipt_file_fsync_event",
        "receipt_directory_fsync_event",
        "admission_event",
        "dispatch_event",
    },
    "execution": _STEP
    | {"proposal_id", "node_id", "operator_id", "succeeded", "output", "dispatch_event"},
    "observation": _STEP | {"execution_id", "output"},
    "update": _STEP | {"proposal_id", "execution_id", "observation_id", "accepted_claim"},
    "final": _COMMON | {"state_id", "producer_claim_id", "answer", "comparability"},
    "claim": {
        "claim_id",
        "producer_node_id",
        "operator_id",
        "status",
        "output",
        "semantic",
        "evidence_refs",
        "support_observation_id",
        "field_origin",
    },
    "operand": {"kind", "ref_id", "selector", "operand_role", "producer_claim_id"},
    "decision_basis": {"relation", "evidence_refs", "claim_refs"},
    "comparability": {"checks", "evidence_refs", "field_origin"},
}


def _plain(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json", exclude_none=True)
    if isinstance(value, Mapping):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_plain(item) for item in value]
    return value


def exact_decimal(value: Any) -> dict[str, str]:
    """Normalize a finite decimal without context rounding or pairwise tolerance."""
    if isinstance(value, bool) or not isinstance(value, (str, int, Decimal)):
        raise ValueError("an exact decimal must be a string, integer, or Decimal")
    decimal = Decimal(value)
    if not decimal.is_finite():
        raise ValueError("nonfinite decimal has no finite comparison interpretation")
    sign, digits, exponent = decimal.as_tuple()
    if not isinstance(exponent, int):
        raise ValueError("a finite Decimal must have an integer exponent")
    if not any(digits):
        normalized = "0"
    else:
        coefficients = list(digits)
        while coefficients[-1] == 0:
            coefficients.pop()
            exponent += 1
        normalized = ("-" if sign else "") + "".join(map(str, coefficients)) + "e" + str(exponent)
    return {"numeric_type": "exact_decimal", "value": normalized}


def _values(value: Any) -> Any:
    """Only registered numeric output/payload value fields enter this function."""
    if isinstance(value, Mapping):
        return {
            key: exact_decimal(item) if key == "value" else _values(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_values(item) for item in value]
    return value


def _select(value: Any, selector: str | None) -> Any:
    for part in selector.split(".") if selector else ():
        value = value[part]
    return value


def _schema(value: Any, kind: str) -> bool:
    return isinstance(value, dict) and set(value) == _FIELDS[kind]


def _state_effect(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    first, second = before["verified_claims"], after["verified_claims"]
    return {
        "visibility_changed": set(before["available_evidence_refs"])
        != set(after["available_evidence_refs"]),
        "removed_claims": sorted(set(first) - set(second)),
        "modified_claims": sorted(
            key for key in first.keys() & second.keys() if first[key] != second[key]
        ),
        "field_origin": after["field_origin"],
        "available_evidence_before": sorted(before["available_evidence_refs"]),
        "available_evidence_after": sorted(after["available_evidence_refs"]),
    }


def transparent_lookup_check(facts: Mapping[str, Any]) -> dict[str, Any]:
    """Recompute five conditions from actual witnesses, never trust `passed` flags.

    The state-effect witness contains the complete before/after State and Update.
    Injecting an otherwise unrepresented field makes the result undetermined.
    Consumers carry their actual operand, selected values, and expected role.
    """
    failures: list[str] = []
    checks: dict[str, bool] = {}
    if set(facts) != set(TRANSPARENCY_CONDITIONS):
        return {
            "eligible": False,
            "status": "undetermined",
            "failures": ["condition_schema"],
            "reasons": ["condition_schema"],
            "checks": {},
        }
    try:
        registration = facts["registration"]
        contract = registration["contract"]
        checks["registration"] = (
            contract["program_role"] == "transparent_projection"
            and contract["operator_id"] == registration["operator_id"] == "lookup"
            and contract["semantic_version"] == "1.0.0"
            and contract["formula_id"] == "lookup.formula.v1"
            and contract["input_role_contract"] == ["selected_evidence"]
            and registration["actual_contract_hash"]
            == strict_canonical_hash(contract, prefix="operation_semantic_contract:")
        )
        value = facts["value_and_source"]
        evidence, operand, claim = value["evidence"], value["operand"], value["claim"]
        evidence_id = evidence["evidence_id"]
        expected_output = {"selected_ref": evidence_id, "payload": evidence["payload"]}
        checks["value_and_source"] = (
            _schema(operand, "operand")
            and operand
            == {
                "kind": "evidence",
                "ref_id": evidence_id,
                "selector": None,
                "operand_role": "selected_evidence",
                "producer_claim_id": None,
            }
            and _values(value["execution_output"])
            == _values(value["observation_output"])
            == _values(claim["output"])
            == _values(expected_output)
            and claim["semantic"] == {"kind": "evidence_scalar", "role": value["role"]}
            and claim["evidence_refs"] == [evidence_id]
            and value["decision_basis"]
            == {"relation": "requires", "evidence_refs": [evidence_id], "claim_refs": []}
            and isinstance(evidence["source"], dict)
            and bool(evidence["source_locator"])
        )
        substitution = facts["reference_substitution"]
        consumers = substitution["consumers"]
        checks["reference_substitution"] = (
            bool(consumers)
            and all(
                _schema(item["operand"], "operand")
                and item["operand"]["kind"] == "operation"
                and item["operand"]["ref_id"] == claim["producer_node_id"]
                and item["operand"]["producer_claim_id"] == claim["claim_id"]
                and item["operand"]["selector"] == "payload.value"
                and item["operand"]["operand_role"] == item["registered_operand_role"]
                and item["replacement_selector"] == "value"
                and item["replacement_evidence_id"] == evidence_id
                and item["replacement_role"] == value["role"]
                and exact_decimal(item["selected_before"])
                == exact_decimal(item["selected_after"])
                == exact_decimal(evidence["payload"]["value"])
                for item in consumers
            )
            and claim["claim_id"] not in substitution["obligation_claim_ids"]
            and (substitution["final_producer_claim_id"] != claim["claim_id"])
            and set(substitution["basis_consumer_ids"])
            == {item["consumer_proposal_id"] for item in consumers}
        )
        information = facts["current_information"]
        checks["current_information"] = (
            information["evidence_id"] == evidence_id
            and bool(information["available_evidence_snapshots"])
            and all(evidence_id in refs for refs in information["available_evidence_snapshots"])
            and all(
                binding == information["expected_scope_binding_id"]
                for binding in information["actual_scope_binding_ids"]
            )
        )
        effects = facts["no_extra_retained_effects"]
        before, after, update = effects["before_state"], effects["after_state"], effects["update"]
        proposal, execution, observation = (
            effects["proposal"],
            effects["execution"],
            effects["observation"],
        )
        delta = _state_effect(before, after)
        expected_claims = {**before["verified_claims"], claim["producer_node_id"]: claim}
        checks["no_extra_retained_effects"] = (
            set(effects)
            == {"before_state", "after_state", "update", "proposal", "execution", "observation"}
            and all(
                _schema(record, kind)
                for record, kind in (
                    (before, "state"),
                    (after, "state"),
                    (update, "update"),
                    (proposal, "proposal"),
                    (execution, "execution"),
                    (observation, "observation"),
                    (claim, "claim"),
                )
            )
            and not delta["visibility_changed"]
            and not delta["removed_claims"]
            and not delta["modified_claims"]
            and after["verified_claims"] == expected_claims
            and before["source_comparability"] == after["source_comparability"]
            and before["source_scope_binding_id"] == after["source_scope_binding_id"]
            and after["completed_node_ids"]
            == before["completed_node_ids"] + [claim["producer_node_id"]]
            and after["observation_refs"] == before["observation_refs"] + [observation["id"]]
            and claim["producer_node_id"] in before["ready_node_ids"]
            and update["accepted_claim"] == claim
            and claim["status"] == "verified"
            and claim["support_observation_id"] == observation["id"]
            and update["observation_id"] == observation["id"]
            and update["execution_id"] == observation["execution_id"] == execution["id"]
            and update["proposal_id"] == execution["proposal_id"] == proposal["id"]
            and proposal["expected_semantic"] == claim["semantic"]
            and proposal["field_origin"]
            == update["field_origin"]
            == claim["field_origin"]
            == "deterministic_fixture"
            and before["field_origin"]
            == after["field_origin"]
            == execution["field_origin"]
            == observation["field_origin"]
            == "host_derived"
            and execution["succeeded"] is True
        )
        failures = [key for key in TRANSPARENCY_CONDITIONS if not checks[key]]
    except (KeyError, TypeError, ValueError, InvalidOperation, IndexError) as error:
        failures.append("uninterpreted_witness: " + str(error))
    return {
        "eligible": not failures,
        "status": "eligible" if not failures else "undetermined",
        "failures": failures,
        "reasons": failures,
        "checks": checks,
    }


def projection_rule_contract() -> dict[str, Any]:
    return {
        "schema_version": "finite_public_projection_rules.v1",
        "graph_schema": GRAPH_SCHEMA,
        "node_required_fields": NODE_REQUIRED_FIELDS,
        "node_allowed_fields": NODE_ALLOWED_FIELDS,
        "semantic_fields": SEMANTIC_FIELDS,
        "parameter_rule": "empty parameters checked by frozen contract and own-source validation",
        "edge_kinds": EDGE_KINDS,
        "transparent_conditions": TRANSPARENCY_CONDITIONS,
        "numeric_fields": [
            "evidence.payload.value",
            "execution.output.value",
            "observation.output.value",
            "claim.output.value",
            "final.answer.result.value",
            "operand.selected_value",
        ],
        "numeric_rule": "finite exact Decimal tuple; no tolerance or context rounding",
        "semantic_references": (
            "Evidence identities/source/locator retained; "
            "runtime IDs only in node identities/edges/audit"
        ),
        "basis_rule": (
            "retain relation, intent and exact Evidence/Claim support; "
            "drop only witnessed forwarding-Claim basis edges"
        ),
        "state_rule": (
            "preserve visibility and Claim delta; "
            "encode actual production-consumption, not independent serial order"
        ),
        "host_rule": (
            "comparability remains host_derived, "
            "separate from deterministic_fixture proposals and updates"
        ),
        "unknown_rule": (
            "missing/extra runtime fields, uninterpreted effects "
            "or unsupported contraction yield undetermined"
        ),
        "raw_record_rule": (
            "original record bytes remain immutable; "
            "complete uncontracted typed graph retained in audit"
        ),
        "obligations": OBLIGATIONS,
    }


def project_runtime(
    fixture: Mapping[str, Any],
    execution: Mapping[str, Any],
    *,
    root: str | Path | None = None,
    reader: Any = None,
    validation: Mapping[str, Any] | None = None,
    operation_contracts: Mapping[str, Any] | Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Project one already admitted actual trajectory; errors explicitly stay unknown."""
    admitted = (
        validation is not None
        and all(
            validation.get(key) is True for key in ("qualified", "qa_valid", "trajectory_valid")
        )
        and (validation.get("candidate_id") == execution.get("candidate_id"))
    )
    graph: dict[str, Any] = {
        "schema": GRAPH_SCHEMA,
        "task_key": fixture.get("task_id"),
        "nodes": [],
        "edges": [],
        "admission": {
            "admitted": admitted,
            "issues": [] if admitted else ["independent_own_qualification_missing_or_failed"],
        },
        "normalization": {"complete": False, "issues": [], "reductions": []},
        "audit": {
            "candidate_id": execution.get("candidate_id"),
            "fixture_id": fixture.get("fixture_id"),
            "group": execution.get("group"),
            "execution_descriptor": _plain(execution),
            "read_files": [],
            "raw_action_count": len(execution.get("step_paths", [])),
            "operation_executor_invocations": 0,
            "operation_oracle_invocations": 0,
            "rule_evidence": projection_rule_contract(),
        },
    }
    issues = graph["normalization"]["issues"]

    def check(condition: bool, location: str) -> None:
        if not condition:
            issues.append(location)

    def read(path: str, kind: str) -> dict[str, Any]:
        if reader is not None:
            raw = reader.read_bytes(path)
        else:
            if root is None:
                raise ValueError("root or read-only reader is required")
            base = Path(root).resolve()
            member = (base / path).resolve()
            if not member.is_relative_to(base):
                raise ValueError("record path is outside the frozen runtime root")
            raw = member.read_bytes()
        value = json.loads(raw)
        graph["audit"]["read_files"].append(
            {
                "path": path,
                "sha256": hashlib.sha256(raw).hexdigest(),
                "byte_count": len(raw),
                "record_id": value.get("id"),
            }
        )
        check(_schema(value, kind), path + ":missing_or_uninterpreted_fields")
        check(value.get("schema_version") == f"typed_candidate_{kind}.v1", path + ":schema_version")
        return value

    def node(identifier: str, kind: str, **attrs: Any) -> None:
        graph["nodes"].append({"id": identifier, "kind": kind, "attrs": attrs})

    def edge(source: str, target: str, kind: str, **attrs: Any) -> None:
        graph["edges"].append({"source": source, "target": target, "kind": kind, **attrs})

    try:
        if not admitted or validation is None:
            return graph
        contracts = operation_contracts
        if contracts is None:
            raise ValueError("exact frozen operation contracts are required")
        if not isinstance(contracts, Mapping):
            contracts = {item["operator_id"]: _plain(item) for item in contracts}
        package, bundle, scope = (
            _plain(fixture["package"]),
            _plain(fixture["bundle"]),
            _plain(fixture["scope_bindings"]),
        )
        evidence = {item["evidence_id"]: item for item in bundle["evidence"]}
        role_bindings = package["binding_snapshot"]["role_bindings"]
        roles = {refs[0]: role for role, refs in role_bindings.items() if len(refs) == 1}
        check(len(roles) == 4 and set(roles) == set(evidence), "evidence:exact_role_binding")
        prefix, paths = execution["runtime_prefix"], execution["step_paths"]
        states = [read(f"{prefix}/state_{i:02d}.json", "state") for i in range(len(paths) + 1)]
        steps = [{kind: read(path, kind) for kind, path in step.items()} for step in paths]
        final = read(execution["final_path"], "final")
        host = states[0]["source_comparability"]
        check(
            not states[0]["verified_claims"]
            and not states[0]["completed_node_ids"]
            and not states[0]["observation_refs"],
            "initial_state:unexplained_prior_knowledge",
        )
        check(
            _schema(host, "comparability") and host["field_origin"] == "host_derived",
            "host:comparability_schema_origin",
        )
        check(host == final["comparability"], "host:final_comparability_binding")
        check(all(item is True for item in host["checks"].values()), "host:source_check_not_true")
        task_id, host_id = "task:" + str(fixture["task_id"]), "host:comparability"
        node(
            task_id,
            "task",
            contract={
                "task": package["task"],
                "scope_bindings": scope,
                "binding_snapshot": package["binding_snapshot"],
            },
            field_origin="frozen_task_contract",
        )
        node(
            host_id, "host_comparability", checks=host["checks"], field_origin=host["field_origin"]
        )
        for ref, record in evidence.items():
            normalized_record = copy.deepcopy(record)
            normalized_record["payload"] = _values(record["payload"])
            node(ref, "evidence", role=roles[ref], record=normalized_record)
            edge(task_id, ref, "task_evidence", role=roles[ref])
        for ref in host["evidence_refs"]:
            edge(ref, host_id, "host_support", role=roles[ref])

        by_node = {step["proposal"]["node_id"]: step for step in steps}
        by_claim = {step["update"]["accepted_claim"]["claim_id"]: step for step in steps}
        check(len(by_node) == len(steps) == len(by_claim), "runtime:unique_producers")
        all_node_ids = set(by_node)
        dependencies = {
            key: {
                operand["ref_id"]
                for operand in step["proposal"]["operands"]
                if operand["kind"] == "operation"
            }
            for key, step in by_node.items()
        }
        retained = {
            entry["node_id"]: entry for entry in validation["actual_retained_typed_structure"]
        }
        check(set(retained) == all_node_ids, "validation:actual_node_domain")
        block_ids: dict[str, set[str]] = {}
        for index, step in enumerate(steps):
            proposal, receipt, action, observation, update = (
                step[k] for k in ("proposal", "receipt", "execution", "observation", "update")
            )
            claim, before, after = update["accepted_claim"], states[index], states[index + 1]
            basis = proposal["decision_basis"]
            operator = proposal["operator_id"]
            contract = _plain(contracts[operator])
            check(
                "parameters must be empty" in contract["parameter_contract"],
                f"step:{index}:uninterpreted_parameter_contract",
            )
            semantic = claim["semantic"]
            check(
                semantic.get("kind") in SEMANTIC_FIELDS
                and set(semantic) == set(SEMANTIC_FIELDS.get(semantic.get("kind"), ())),
                f"step:{index}:uninterpreted_claim_semantic_fields",
            )
            ids = {k: step[k]["id"] for k in step}
            ids["claim"], ids["effect"] = claim["claim_id"], "effect:" + update["id"]
            block_ids[proposal["node_id"]] = set(ids.values())
            check(
                _schema(claim, "claim") and _schema(basis, "decision_basis"),
                f"step:{index}:claim_or_basis_schema",
            )
            check(basis["relation"] == "requires", f"step:{index}:uninterpreted_basis_relation")
            check(
                proposal["operation_contract_hash"]
                == strict_canonical_hash(contract, prefix="operation_semantic_contract:"),
                f"step:{index}:operation_version_binding",
            )
            check(
                contract["input_order_policy"] == "ordered",
                f"step:{index}:unsupported_input_order_policy",
            )
            check(
                len(proposal["operands"]) == len(contract["input_role_contract"]),
                f"step:{index}:ordered_arity",
            )
            check(
                action["operator_id"] == claim["operator_id"] == operator
                and action["node_id"] == claim["producer_node_id"] == proposal["node_id"],
                f"step:{index}:producer_operation",
            )
            check(
                claim["output"] == observation["output"] == action["output"]
                and claim["semantic"] == proposal["expected_semantic"],
                f"step:{index}:actual_observation_claim",
            )
            check(
                observation["execution_id"] == action["id"]
                and action["proposal_id"] == proposal["id"]
                and update["proposal_id"] == proposal["id"]
                and update["execution_id"] == action["id"]
                and update["observation_id"]
                == claim["support_observation_id"]
                == observation["id"],
                f"step:{index}:actual_causal_links",
            )
            check(
                all(
                    record["state_id"] == before["id"]
                    and record["task_id"] == fixture["task_id"]
                    and record["candidate_id"] == execution["candidate_id"]
                    for record in step.values()
                ),
                f"step:{index}:state_task_identity",
            )
            check(
                before["source_comparability"] == after["source_comparability"] == host,
                f"step:{index}:host_source_state",
            )
            check(
                before["source_scope_binding_id"]
                == after["source_scope_binding_id"]
                == scope["scope_binding_id"],
                f"step:{index}:scope_binding",
            )
            expected_ready = {
                key
                for key in all_node_ids - set(before["completed_node_ids"])
                if dependencies[key] <= set(before["completed_node_ids"])
            }
            check(
                set(before["ready_node_ids"]) == expected_ready
                and proposal["node_id"] in expected_ready,
                f"step:{index}:actual_dependency_readiness",
            )
            check(
                after["verified_claims"]
                == {**before["verified_claims"], proposal["node_id"]: claim}
                and after["completed_node_ids"]
                == before["completed_node_ids"] + [proposal["node_id"]]
                and after["observation_refs"] == before["observation_refs"] + [observation["id"]],
                f"step:{index}:uninterpreted_state_effect",
            )
            own = retained[proposal["node_id"]]
            check(
                own["claim_id"] == claim["claim_id"]
                and own["observation_id"] == observation["id"]
                and own["output"] == action["output"]
                and own["claim_semantic"] == claim["semantic"],
                f"step:{index}:independent_actual_structure_binding",
            )
            committed = (
                receipt["proposal_id"] == proposal["id"]
                and receipt["proposal_sha256"]
                == next(
                    item["sha256"]
                    for item in graph["audit"]["read_files"]
                    if item["path"] == receipt["proposal_path"]
                )
                and receipt["dispatch_event"] == action["dispatch_event"]
            )
            check(committed, f"step:{index}:durable_receipt_binding")
            node(
                ids["proposal"],
                "decision",
                relation=basis["relation"],
                expected_semantic=proposal["expected_semantic"],
                field_origin=proposal["field_origin"],
            )
            node(
                ids["receipt"],
                "receipt",
                durable_preaction_commitment=committed,
                field_origin=receipt["field_origin"],
            )
            node(
                ids["execution"],
                "operation",
                contract=contract,
                parameters={},
                succeeded=action["succeeded"],
                output=_values(action["output"]),
                field_origin=action["field_origin"],
            )
            node(
                ids["observation"],
                "observation",
                output=_values(observation["output"]),
                field_origin=observation["field_origin"],
            )
            node(
                ids["claim"],
                "claim",
                status=claim["status"],
                semantic=claim["semantic"],
                output=_values(claim["output"]),
                field_origin=claim["field_origin"],
            )
            node(
                ids["update"],
                "update",
                acceptance=claim["status"],
                field_origin=update["field_origin"],
            )
            node(ids["effect"], "state_effect", **_state_effect(before, after))
            for source, target, kind in (
                (host_id, ids["proposal"], "host_basis"),
                (ids["proposal"], ids["receipt"], "commitment"),
                (ids["receipt"], ids["execution"], "dispatch"),
                (ids["execution"], ids["observation"], "observes"),
                (ids["execution"], ids["claim"], "produces_claim"),
                (ids["observation"], ids["claim"], "grounds"),
                (ids["proposal"], ids["update"], "proposes_update"),
                (ids["observation"], ids["update"], "causes_update"),
                (ids["update"], ids["claim"], "accepts_claim"),
                (ids["update"], ids["effect"], "commits_effect"),
                (ids["effect"], ids["claim"], "adds_claim"),
                (ids["effect"], ids["execution"], "completes_operation"),
                (ids["effect"], ids["observation"], "observes_effect"),
            ):
                edge(source, target, kind)
            check(
                basis["evidence_refs"] == proposal["evidence_refs"] == claim["evidence_refs"]
                and basis["claim_refs"] == proposal["claim_refs"],
                f"step:{index}:basis_support_binding",
            )
            for ref in basis["evidence_refs"]:
                edge(ref, ids["proposal"], "basis_evidence", role=roles[ref])
            for ref in basis["claim_refs"]:
                check(ref in by_claim, f"step:{index}:basis_claim_missing")
                edge(ref, ids["proposal"], "basis_claim")
            for ref in claim["evidence_refs"]:
                edge(ref, ids["claim"], "claim_evidence", role=roles[ref])
            for position, operand in enumerate(proposal["operands"]):
                check(_schema(operand, "operand"), f"step:{index}:operand:{position}:schema")
                check(
                    operand["operand_role"] == contract["input_role_contract"][position],
                    f"step:{index}:operand:{position}:ordered_role",
                )
                if operand["kind"] == "evidence":
                    ref = operand["ref_id"]
                    check(
                        ref in before["available_evidence_refs"]
                        and operand["producer_claim_id"] is None,
                        f"step:{index}:operand:{position}:visibility",
                    )
                    selected = _select(evidence[ref]["payload"], operand["selector"])
                    semantic = {"kind": "evidence_scalar", "role": roles[ref]}
                elif operand["kind"] == "operation":
                    parent = by_node[operand["ref_id"]]["update"]["accepted_claim"]
                    ref = parent["claim_id"]
                    check(
                        operand["producer_claim_id"] == ref
                        and before["verified_claims"].get(operand["ref_id"]) == parent,
                        f"step:{index}:operand:{position}:verified_producer",
                    )
                    selected, semantic = (
                        _select(parent["output"], operand["selector"]),
                        parent["semantic"],
                    )
                else:
                    raise ValueError("uninterpreted operand kind")
                edge(
                    ref,
                    ids["execution"],
                    "operand",
                    position=position,
                    role=operand["operand_role"],
                    attrs={
                        "selector": operand["selector"],
                        "selected_value": _values(selected)
                        if isinstance(selected, dict)
                        else exact_decimal(selected),
                        "semantic": semantic,
                    },
                )

        check(
            states[-1]["ready_node_ids"] == []
            and len(states[-1]["completed_node_ids"]) == len(steps),
            "terminal:unresolved_actions",
        )
        check(
            final["state_id"] == states[-1]["id"] and final["producer_claim_id"] in by_claim,
            "final:actual_terminal_producer",
        )
        check(set(final["answer"]) == {"result", "citations"}, "final:uninterpreted_answer_fields")
        final_claim = by_claim[final["producer_claim_id"]]["update"]["accepted_claim"]
        check(
            final_claim["status"] == "verified"
            and final_claim["semantic"]
            == {"kind": "absolute_growth_spread", "unit": "percentage_points"}
            and final["answer"]["result"] == final_claim["output"],
            "final:actual_answer_disposition",
        )
        node(
            final["id"],
            "final",
            disposition="answer_from_verified_claim",
            answer={"result": _values(final["answer"]["result"])},
            field_origin=final["field_origin"],
        )
        edge(final["producer_claim_id"], final["id"], "final_claim")
        for citation in final["answer"]["citations"]:
            check(
                set(citation) == {"evidence_id", "source_id", "source_locator"},
                "final:citation_schema",
            )
            ref = citation["evidence_id"]
            check(
                citation["source_id"] == evidence[ref]["source"]["source_id"]
                and citation["source_locator"] == evidence[ref]["source_locator"],
                "final:citation_exact_source",
            )
            edge(
                ref,
                final["id"],
                "final_citation",
                attrs={key: value for key, value in citation.items() if key != "evidence_id"},
            )
        obligations = validation["evidence_to_obligation_discharge"]
        check(
            len(obligations) == 5
            and {item["obligation"] for item in obligations} == set(OBLIGATIONS),
            "obligations:exact_five_actual_witnesses",
        )
        obligation_claims: list[str] = []
        for obligation in obligations:
            name, identifier = obligation["obligation"], "obligation:" + obligation["obligation"]
            expected_fields = (
                {
                    "obligation",
                    "discharged",
                    "host_source_checks",
                    "not_a_registered_candidate_operation",
                }
                if name == "comparability"
                else {"obligation", "discharged", "claim_ids", "evidence_refs"}
            )
            if name == "final_grounding":
                expected_fields.add("final_id")
            check(
                set(obligation) == expected_fields, "obligation:" + name + ":uninterpreted_fields"
            )
            check(obligation["discharged"] is True, "obligation:" + name + ":not_discharged")
            node(
                identifier,
                "obligation",
                name=name,
                discharged=obligation["discharged"],
                field_origin="host_derived",
            )
            if name == "comparability":
                check(
                    obligation["host_source_checks"] == host
                    and obligation["not_a_registered_candidate_operation"] is True,
                    "obligation:host_source_binding",
                )
                edge(host_id, identifier, "fulfills")
                refs = host["evidence_refs"]
            else:
                refs = obligation["evidence_refs"]
                actual_claims = [
                    by_claim[ref]["update"]["accepted_claim"] for ref in obligation["claim_ids"]
                ]
                actual_support = {ref for claim in actual_claims for ref in claim["evidence_refs"]}
                check(set(refs) == actual_support, "obligation:" + name + ":actual_support")
                if name in {"revenue_growth", "income_growth"}:
                    metric = name.removesuffix("_growth")
                    check(
                        len(actual_claims) == 1
                        and actual_claims[0]["semantic"].get("kind") == "growth_percent"
                        and actual_claims[0]["semantic"].get("metric") == metric,
                        "obligation:" + name + ":actual_growth_claim",
                    )
                elif name == "exact_absolute_growth_difference":
                    check(
                        [claim["semantic"]["kind"] for claim in actual_claims]
                        == ["signed_growth_gap", "absolute_growth_spread"],
                        "obligation:" + name + ":actual_merge_claims",
                    )
                elif name == "final_grounding":
                    check(
                        obligation["claim_ids"] == [final["producer_claim_id"]],
                        "obligation:" + name + ":actual_terminal_claim",
                    )
                for claim_id in obligation["claim_ids"]:
                    check(claim_id in by_claim, "obligation:" + name + ":actual_claim_missing")
                    obligation_claims.append(claim_id)
                    edge(claim_id, identifier, "fulfills")
                if name == "final_grounding":
                    check(obligation["final_id"] == final["id"], "obligation:final_actual_binding")
                    edge(final["id"], identifier, "fulfills")
            for ref in refs:
                edge(ref, identifier, "obligation_evidence", role=roles[ref])
            edge(identifier, final["id"], "final_obligation")

        graph["audit"]["uncontracted_graph"] = {
            "nodes": copy.deepcopy(graph["nodes"]),
            "edges": copy.deepcopy(graph["edges"]),
        }
        graph["audit"]["state_snapshots"] = states
        graph["audit"]["raw_record_ids"] = [step["proposal"]["id"] for step in steps]
        removed: set[str] = set()
        replacements: dict[str, tuple[str, dict[str, Any]]] = {}
        for index, step in enumerate(steps):
            proposal = step["proposal"]
            contract = _plain(contracts[proposal["operator_id"]])
            if contract["program_role"] != "transparent_projection":
                continue
            claim = step["update"]["accepted_claim"]
            operand = proposal["operands"][0]
            ref = operand["ref_id"]
            consumers, consumer_indices, basis_consumer_ids = [], [], []
            for consumer_index, consumer in enumerate(steps):
                submitted = consumer["proposal"]
                if claim["claim_id"] in submitted["decision_basis"]["claim_refs"]:
                    basis_consumer_ids.append(submitted["id"])
                for position, actual_operand in enumerate(submitted["operands"]):
                    if actual_operand["producer_claim_id"] != claim["claim_id"]:
                        continue
                    consumers.append(
                        {
                            "consumer_proposal_id": submitted["id"],
                            "consumer_operation_id": consumer["execution"]["id"],
                            "operand_position": position,
                            "operand": actual_operand,
                            "registered_operand_role": contracts[submitted["operator_id"]][
                                "input_role_contract"
                            ][position],
                            "selected_before": _select(claim["output"], actual_operand["selector"]),
                            "selected_after": evidence[ref]["payload"]["value"],
                            "replacement_selector": "value",
                            "replacement_evidence_id": ref,
                            "replacement_role": roles[ref],
                        }
                    )
                    consumer_indices.append(consumer_index)
            facts = {
                "registration": {
                    "contract": contract,
                    "operator_id": proposal["operator_id"],
                    "actual_contract_hash": proposal["operation_contract_hash"],
                },
                "value_and_source": {
                    "evidence": evidence[ref],
                    "role": roles[ref],
                    "operand": operand,
                    "execution_output": step["execution"]["output"],
                    "observation_output": step["observation"]["output"],
                    "claim": claim,
                    "decision_basis": proposal["decision_basis"],
                },
                "reference_substitution": {
                    "consumers": consumers,
                    "basis_consumer_ids": basis_consumer_ids,
                    "obligation_claim_ids": obligation_claims,
                    "final_producer_claim_id": final["producer_claim_id"],
                },
                "current_information": {
                    "evidence_id": ref,
                    "available_evidence_snapshots": [
                        states[i]["available_evidence_refs"] for i in [index, *consumer_indices]
                    ],
                    "actual_scope_binding_ids": [
                        states[i]["source_scope_binding_id"] for i in [index, *consumer_indices]
                    ],
                    "expected_scope_binding_id": scope["scope_binding_id"],
                },
                "no_extra_retained_effects": {
                    "before_state": states[index],
                    "after_state": states[index + 1],
                    **{
                        key: step[key] for key in ("update", "proposal", "execution", "observation")
                    },
                },
            }
            checked = transparent_lookup_check(facts)
            reduction = {
                "rule": "witnessed_transparent_lookup_forwarding.v1",
                "actual_node_id": proposal["node_id"],
                "actual_claim_id": claim["claim_id"],
                "facts": facts,
                **checked,
                "removed_projection_node_ids": sorted(block_ids[proposal["node_id"]])
                if checked["eligible"]
                else [],
                "retained_evidence_id": ref,
                "historical_records_modified": False,
            }
            graph["normalization"]["reductions"].append(reduction)
            if checked["eligible"]:
                removed.update(block_ids[proposal["node_id"]])
                replacements[claim["claim_id"]] = (
                    ref,
                    {"kind": "evidence_scalar", "role": roles[ref]},
                )
            else:
                issues.append("lookup:" + proposal["node_id"] + ":" + ",".join(checked["failures"]))
        normalized_edges = []
        for item in graph["edges"]:
            if (
                item["kind"] == "operand"
                and item["source"] in replacements
                and item["target"] not in removed
            ):
                ref, semantic = replacements[item["source"]]
                item = {
                    **item,
                    "source": ref,
                    "attrs": {**item["attrs"], "selector": "value", "semantic": semantic},
                }
            if item["source"] in removed or item["target"] in removed:
                continue
            normalized_edges.append(item)
        graph["nodes"] = [item for item in graph["nodes"] if item["id"] not in removed]
        graph["edges"] = normalized_edges
        graph["normalization"]["complete"] = not issues
        graph["audit"]["normalized_operation_count"] = sum(
            item["kind"] == "operation" for item in graph["nodes"]
        )
    except (
        OSError,
        KeyError,
        TypeError,
        ValueError,
        InvalidOperation,
        IndexError,
        StopIteration,
    ) as error:
        issues.append("uninterpreted_runtime_field: " + str(error))
    return graph
