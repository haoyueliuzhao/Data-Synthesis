"""Independent replay of the one source-bound part/whole share experiment.

No controller, admission helper, source parser or Runtime kernel is imported.
The disclosed-total answer oracle and actual-operation replay are separate:
the latter follows persisted input references and never substitutes the oracle
total for a derived Claim.  Missing artifacts fail closed.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from collections.abc import Mapping
from decimal import ROUND_HALF_EVEN, Decimal, InvalidOperation, localcontext
from pathlib import Path
from typing import Any

from trusted_synthesis.canonical_json import canonical_json_bytes, strict_canonical_hash

CONTEXT = ("subject", "scope", "period", "unit", "currency")
OBLIGATIONS = ["period_scope", "numerator_denominator", "percent_unit", "final_grounding"]
NUMERIC: dict[str, Any] = {
    "precision": 50,
    "rounding": "ROUND_HALF_EVEN",
    "final_quantum": "0.000001",
    "source_reconciliation_tolerance": "0",
    "answer_tolerance": "0",
}
ROWS = {
    "freight": (7, "Total freight revenues", "total_freight_revenues"),
    "other": (8, "Other revenues", "other_revenues"),
    "total": (9, "Total operating revenues", "total_operating_revenues"),
}
RECORD_FIELDS = {
    "candidate": {"task_id", "contract_id", "route", "controller", "nodes", "output_node"},
    "state": {
        "task_id",
        "candidate_id",
        "visible_evidence_ids",
        "accepted_claims",
        "completed_nodes",
        "observations",
    },
    "proposal": {
        "task_id",
        "candidate_id",
        "node",
        "operation",
        "operation_contract_id",
        "parameters",
        "inputs",
        "requires_basis",
        "pre_state_id",
        "owner",
    },
    "receipt": {
        "proposal_id",
        "pre_state_id",
        "admitted",
        "checks",
        "proposal_sha256",
        "proposal_byte_count",
        "no_replace",
        "proposal_file_and_directory_fsynced",
    },
    "execution": {"proposal_id", "receipt_id", "operation", "parameters", "inputs", "output"},
    "observation": {"execution_id", "output", "success"},
    "claim": {"task_id", "node", "proposition", "observation_id", "status", "grounding", "owner"},
    "update": {"pre_state_id", "observation_id", "accepted_claim_id", "decision", "owner"},
    "final": {
        "task_id",
        "candidate_id",
        "pre_state_id",
        "answer",
        "answer_claim_id",
        "citations",
        "owner",
    },
}
STEP_FIELDS = {"proposal", "receipt", "execution", "observation", "claim", "update", "state"}


class ReplayError(ValueError):
    def __init__(self, stage: str, message: str) -> None:
        super().__init__(message)
        self.stage = stage


def _check(condition: bool, stage: str, message: str) -> None:
    if not condition:
        raise ReplayError(stage, message)


def _decimal(value: Any) -> Decimal:
    _check(isinstance(value, str), "replay.numeric", "exact scalar must be a decimal string")
    try:
        number = Decimal(value)
    except InvalidOperation as error:
        raise ReplayError("replay.numeric", "invalid decimal scalar") from error
    _check(number.is_finite(), "replay.numeric", "nonfinite scalar")
    return number


def _identity(obj: Mapping[str, Any], kind: str, strict: bool = False) -> None:
    _check(isinstance(obj, Mapping), "replay.record_schema", "record is not an object")
    if strict:
        _check(
            set(obj) == RECORD_FIELDS[kind] | {"id", "schema_version"},
            "replay.record_schema",
            f"{kind} contains missing or unsupported fields",
        )
    _check(
        obj["schema_version"] == f"part_whole_share_{kind}.v1",
        "replay.record_schema",
        f"unsupported {kind} schema",
    )
    _check(
        obj["id"]
        == strict_canonical_hash(
            {k: v for k, v in obj.items() if k != "id"}, prefix=f"part_whole_share_{kind}:"
        ),
        "replay.record_identity",
        f"{kind} content identity differs",
    )


def _source_cell(value: Any) -> str:
    _check(isinstance(value, str), "replay.source_cell", "source cell is not text")
    token = value.strip().removeprefix("$").strip().replace(",", "")
    _check(
        bool(re.fullmatch(r"[+-]?\d+(?:\.\d+)?", token)),
        "replay.source_cell",
        "unsupported source numeric cell",
    )
    return str(_decimal(token))


def _check_reference(ref: Mapping[str, Any], raw: Mapping[int, Any]) -> None:
    parts = ref["json_pointer"].split("/")
    _check(parts[0] == "" and len(parts) >= 3, "replay.source_reference", "invalid pointer")
    index = int(parts[1])
    source = raw[index]
    value: Any = source
    for part in parts[2:]:
        part = part.replace("~1", "/").replace("~0", "~")
        value = value[int(part)] if isinstance(value, list) else value[part]
    _check(
        ref["source_record_id"] == source["id"]
        and ref["source_document_id"] == source["filename"]
        and ref["source_value"] == value
        and ref["source_value_sha256"] == hashlib.sha256(canonical_json_bytes(value)).hexdigest(),
        "replay.source_reference",
        "source reference does not resolve to its actual excerpt",
    )


def _source_and_contract(contract: Mapping[str, Any], source: Mapping[str, Any]) -> dict[str, Any]:
    """Rebuild the finite source facts without using admission verdicts or sums."""
    _identity(source, "source_binding")
    _identity(contract, "contract")
    task = contract["task"]
    _identity(task, "task")
    _check(
        contract["numeric"] == NUMERIC and contract["shared_obligations"] == OBLIGATIONS,
        "replay.task_contract",
        "unsupported or changed numeric/common obligation contract",
    )
    _check(
        contract["source_binding_id"] == task["source_binding_id"] == source["id"],
        "replay.task_contract",
        "task and source binding are disconnected",
    )
    _check(
        set(source["evidence"]) == {"freight", "other", "total", "part_whole"},
        "replay.source_domain",
        "the four-object visible Evidence universe is incomplete",
    )
    evidence = source["evidence"]
    raw: dict[int, Any] = {}
    for item in source["raw_source_records"]:
        index, fields = item["archive_record_index"], item["source_fields"]
        _check(
            index not in raw
            and set(fields) == {"id", "filename", "table_ori", "pre_text", "post_text"},
            "replay.source_domain",
            "source excerpt domain changed or contains QA fields",
        )
        _check(
            item["source_fields_sha256"]
            == hashlib.sha256(canonical_json_bytes(fields)).hexdigest(),
            "replay.source_bytes",
            "source excerpt hash differs",
        )
        raw[index] = fields
    _check(set(raw) == {30, 981, 1065, 1099}, "replay.source_domain", "fixed alias group changed")
    target = raw[30]
    _check(
        target["id"] == source["source_record_id"] == "UNP/2015/page_56.pdf-1"
        and target["filename"] == source["source_document_id"] == "UNP/2015/page_56.pdf",
        "replay.source_domain",
        "source moved outside the single fixed page",
    )
    table = target["table_ori"]
    _check(
        len(table) == 10 and table[0][0] == "Millions",
        "replay.source_structure",
        "finite revenue table shape/unit changed",
    )
    _check(
        [row[0] for row in table[1:7]]
        == [
            "Agricultural Products",
            "Automotive",
            "Chemicals",
            "Coal",
            "Industrial Products",
            "Intermodal",
        ],
        "replay.source_structure",
        "freight subtotal member rows differ",
    )
    for fields in raw.values():
        _check(
            fields["filename"] == target["filename"]
            and [fields["table_ori"][i] for i in (0, 7, 8, 9)] == [table[i] for i in (0, 7, 8, 9)],
            "replay.source_alias",
            "same-page used rows are not actual source aliases",
        )
    _check(
        "union pacific corporation and its subsidiaries" in target["pre_text"][0]
        and "the following table provides freight revenue by commodity group"
        in target["pre_text"][10]
        and (
            "consolidated financial statements include the accounts of union pacific "
            "corporation and all of its subsidiaries"
        )
        in target["post_text"][7]
        and "all intercompany transactions are eliminated" in target["post_text"][9],
        "replay.source_scope",
        "consolidated issuer/partition context is missing",
    )
    eligible = []
    for column, header in enumerate(table[0][1:], 1):
        if isinstance(header, str) and re.fullmatch(r"(?:19|20)\d{2}", header.strip()):
            try:
                values = {
                    role: _source_cell(table[row][column]) for role, (row, _, _) in ROWS.items()
                }
                if table[7][column].strip().startswith("$") and table[9][column].strip().startswith(
                    "$"
                ):
                    eligible.append((int(header), column, values))
            except (ReplayError, IndexError):
                continue
    _check(bool(eligible), "replay.source_period", "no complete annual column")
    year, column, values = sorted(eligible, key=lambda item: (-item[0], item[1]))[0]
    common = {
        "subject": "Union Pacific Corporation and subsidiaries",
        "scope": "consolidated_issuer",
        "period": str(year),
        "unit": "millions",
        "currency": "dollar_as_disclosed",
    }
    _check(
        source["selected_column"]["index"] == column
        and source["selected_column"]["label"] == str(year)
        and source["selected_raw_header"] == table[0]
        and bool(re.search(rf"\b{year}\b", target["post_text"][2])),
        "replay.source_period",
        "selected actual annual column differs",
    )
    for key, expected in common.items():
        _check(
            source[key] == task[key] == expected,
            "replay.source_" + key,
            "task/source context differs",
        )
    for role, (row, label, metric) in ROWS.items():
        item = evidence[role]
        _identity(item, "numeric_evidence")
        _check(
            table[row][0] == label
            and item["kind"] == "numeric"
            and item["metric"] == metric
            and item["definition"] == label
            and _decimal(item["value"]) == _decimal(values[role]),
            "replay.source_metric",
            "raw member identity, label or value was rewritten",
        )
        selected = source["selected_raw_cells"][role]
        _check(
            selected["row_index"] == row
            and selected["column_index"] == column
            and selected["raw_value"] == table[row][column]
            and _decimal(selected["value"]) == _decimal(values[role]),
            "replay.source_cell",
            "selected raw cell does not bind the scalar",
        )
        _check(
            any(
                ref["json_pointer"] == f"/30/table_ori/{row}/{column}"
                for ref in item["source_references"]
            ),
            "replay.source_reference",
            "numeric Evidence has no exact selected-cell citation",
        )
    relation = evidence["part_whole"]
    _identity(relation, "relation_evidence")
    _check(
        relation["kind"] == "part_whole"
        and Counter(relation["member_ids"])
        == Counter([evidence["freight"]["id"], evidence["other"]["id"]])
        and relation["total_id"] == evidence["total"]["id"]
        and relation["member_metrics"] == [ROWS["freight"][2], ROWS["other"][2]]
        and relation["total_metric"] == ROWS["total"][2]
        and relation["exhaustive"] is True
        and relation["nonoverlapping"] is True
        and relation["numeric_value_cell_exists"] is False
        and relation["numeric_sum_computed_for_admission"] is False
        and relation["interpretation_status"] == "known_source_host_annotation_not_data_blind"
        and bool(relation["interpretation"]),
        "replay.source_relation",
        "source relation is not the exact explicit complete partition",
    )
    _check(
        {f"/30/table_ori/{i}" for i in range(10)}.issubset(
            {ref["json_pointer"] for ref in relation["source_references"]}
        ),
        "replay.source_relation",
        "relation omits complete table structure citations",
    )
    for item in evidence.values():
        _check(
            all(item[k] == v for k, v in common.items()),
            "replay.source_context",
            "Evidence context differs",
        )
        _check(
            item["source_record_id"] == target["id"]
            and item["source_document_id"] == target["filename"]
            and item["source_authority"] == "curated_database"
            and item["provider"] == "FinQA",
            "replay.source_authority",
            "source authority or record binding differs",
        )
        for ref in item["source_references"]:
            _check_reference(ref, raw)
    for ref in source["source_references"]:
        _check_reference(ref, raw)
    by_id = {item["id"]: item for item in evidence.values()}
    _check(
        len(by_id) == 4 and task["evidence_universe_ids"] == sorted(by_id),
        "replay.source_domain",
        "task visible universe differs",
    )
    expected_operations = {
        "relation_sum": (
            {"method": "sum"},
            ["member", "member", "relation"],
            "total_operating_revenues",
            "millions",
        ),
        "share_ratio": ({}, ["numerator", "denominator"], "freight_share_ratio", "ratio"),
        "scale_percent": ({}, ["ratio"], "freight_share_percent", "percent"),
    }
    _check(
        set(contract["operations"]) == set(expected_operations),
        "replay.operation_contract",
        "unsupported operation domain",
    )
    for name, (params, roles, metric, unit) in expected_operations.items():
        op = contract["operations"][name]
        _identity(op, "operation_contract")
        _check(
            op["operation"] == name
            and op["version"] == "1.0.0"
            and op["parameters"] == params
            and op["input_roles"] == roles
            and op["output_metric"] == metric
            and op["output_unit"] == unit
            and op["program_role"] == "semantic"
            and op["input_order_policy"]
            == (
                "members_permutation_invariant_relation_fixed"
                if name == "relation_sum"
                else "ordered"
            ),
            "replay.operation_contract",
            "operation semantic signature differs",
        )
    _check(
        contract["operations"]["relation_sum"]["raw_evidence_metadata_rewriting_permitted"] is False
        and contract["operations"]["relation_sum"]["disclosed_total_value_read_by_executor"]
        is False
        and contract["operations"]["share_ratio"]["numerator_metric"]
        == evidence["freight"]["metric"]
        and contract["operations"]["share_ratio"]["denominator_metric"]
        == evidence["total"]["metric"],
        "replay.operation_contract",
        "relation/ratio role contract differs",
    )
    return {"evidence": evidence, "by_id": by_id, "common": common, "values": values}


def _source_input(item: Mapping[str, Any], operand: Mapping[str, Any]) -> dict[str, Any]:
    base = {"role": operand["role"], "kind": "evidence", "ref_id": item["id"]}
    if item["kind"] == "part_whole":
        return {**base, "relation": dict(item), "lineage": [item["id"]]}
    return {
        **base,
        **{k: item[k] for k in ("value", "metric", "definition", *CONTEXT)},
        "lineage": [item["id"]],
        "producer_operation": None,
    }


def _recompute(
    operation: str,
    inputs: list[dict[str, Any]],
    parameters: Mapping[str, Any],
    contract: Mapping[str, Any],
    bound: Mapping[str, Any],
) -> dict[str, Any]:
    """Independent operation semantics; only actual resolved inputs supply values."""
    evidence, common = bound["evidence"], bound["common"]
    op = contract["operations"][operation]
    _check(
        parameters == op["parameters"], "replay.parameters", "actual operation parameters differ"
    )
    _check(
        [item["role"] for item in inputs] == op["input_roles"],
        "replay.input_roles",
        "actual roles differ",
    )
    numeric = [item for item in inputs if item["role"] != "relation"]
    for item in numeric:
        _decimal(item["value"])
        fields = (
            CONTEXT if operation != "scale_percent" else ("subject", "scope", "period", "currency")
        )
        _check(
            all(item[k] == common[k] for k in fields),
            "replay.input_context",
            "actual input context differs",
        )
    lineage = sorted({ref for item in inputs for ref in item["lineage"]})
    if operation == "relation_sum":
        members, relation = inputs[:2], inputs[2]
        _check(
            Counter(item["ref_id"] for item in members)
            == Counter(evidence["part_whole"]["member_ids"])
            and all(item["kind"] == "evidence" for item in members),
            "replay.complete_members",
            "missing, repeated or substituted component identity",
        )
        _check(
            relation["kind"] == "evidence"
            and relation["ref_id"] == evidence["part_whole"]["id"]
            and relation["relation"] == evidence["part_whole"],
            "replay.source_relation",
            "actual operation lacks source relation",
        )
        value = sum((_decimal(item["value"]) for item in members), Decimal(0))
        definition = evidence["total"]["definition"]
    elif operation == "share_ratio":
        numerator, denominator = inputs
        _check(
            numerator["kind"] == "evidence"
            and numerator["ref_id"] == evidence["freight"]["id"]
            and numerator["metric"] == evidence["freight"]["metric"]
            and denominator["metric"] == evidence["total"]["metric"],
            "replay.ratio_roles",
            "illegal numerator or denominator metric",
        )
        _check(_decimal(denominator["value"]) != 0, "replay.denominator", "zero denominator")
        if denominator["kind"] == "evidence":
            _check(
                denominator["ref_id"] == evidence["total"]["id"],
                "replay.denominator",
                "wrong disclosed total",
            )
        else:
            _check(
                denominator["producer_operation"] == "relation_sum"
                and denominator["lineage"]
                == sorted([evidence[r]["id"] for r in ("freight", "other", "part_whole")]),
                "replay.derived_denominator",
                "ratio does not consume the accepted reconstructed total",
            )
        value = _decimal(numerator["value"]) / _decimal(denominator["value"])
        definition = "freight divided by legitimate operating revenue total"
    elif operation == "scale_percent":
        ratio = inputs[0]
        _check(
            ratio["kind"] == "claim"
            and ratio["producer_operation"] == "share_ratio"
            and ratio["metric"] == "freight_share_ratio"
            and ratio["unit"] == "ratio",
            "replay.percent",
            "percentage must consume an accepted actual ratio Claim",
        )
        value = _decimal(ratio["value"]) * Decimal(100)
        definition = "freight share in percent"
    else:
        raise ReplayError("replay.operation", "unsupported operation")
    return {
        "value": str(value),
        "metric": op["output_metric"],
        "definition": definition,
        **common,
        "unit": op["output_unit"],
        "lineage": lineage,
    }


def _answer_oracle(
    contract: Mapping[str, Any], bound: Mapping[str, Any], final: Mapping[str, Any]
) -> dict[str, Any]:
    f, t = (_decimal(bound["values"][key]) for key in ("freight", "total"))
    _check(t != 0, "qa.denominator", "disclosed total is zero")
    oracle = (f / t * Decimal(100)).quantize(Decimal(contract["numeric"]["final_quantum"]))
    answer = final["answer"]
    schema_ok = isinstance(answer, Mapping) and set(answer) == {"value", "unit"}
    actual = _decimal(answer["value"])
    qa_valid = (
        schema_ok
        and answer["unit"] == "percent"
        and bool(re.fullmatch(r"-?\d+\.\d{6}", answer["value"]))
        and abs(actual - oracle) <= Decimal(contract["numeric"]["answer_tolerance"])
        and final["task_id"] == contract["task"]["id"]
        and bool(final["citations"])
        and len(set(final["citations"])) == len(final["citations"])
        and set(final["citations"]).issubset(bound["by_id"])
    )
    return {
        "qa_valid": qa_valid,
        "answer_oracle": {
            "formula": "100 * disclosed_freight / disclosed_operating_total",
            "freight_value": str(f),
            "disclosed_total_value": str(t),
            "expected_answer": str(oracle),
            "actual_answer": answer,
            "numeric_contract": dict(contract["numeric"]),
            "candidate_execution": False,
            "oracle_result_inserted_into_trajectory": False,
        },
    }


def _trajectory(
    contract: Mapping[str, Any],
    source: Mapping[str, Any],
    records: Mapping[str, Any],
    bound: Mapping[str, Any],
) -> dict[str, Any]:
    _check(
        set(records) == {"candidate", "initial_state", "steps", "final"},
        "replay.record_schema",
        "trajectory envelope is incomplete or unsupported",
    )
    candidate, state = records["candidate"], records["initial_state"]
    _identity(candidate, "candidate", True)
    _identity(state, "state", True)
    _check(
        candidate["contract_id"] == contract["id"]
        and candidate["task_id"] == contract["task"]["id"]
        and candidate["controller"] == "deterministic_fixture"
        and candidate["route"] in {"D", "S"},
        "replay.candidate_contract",
        "candidate is outside frozen task/controller domain",
    )
    _check(
        len(candidate["nodes"]) == len(records["steps"])
        and 1 <= len(records["steps"]) <= contract["runtime_action_bound"],
        "replay.plan",
        "persisted execution does not cover exact bounded proposal plan",
    )
    nodes = [node["name"] for node in candidate["nodes"]]
    _check(
        len(set(nodes)) == len(nodes) and candidate["output_node"] in nodes,
        "replay.plan",
        "duplicate node name or missing final producer",
    )
    claims: dict[str, Any] = {}
    names: dict[str, str] = {}
    operations: dict[str, str] = {}
    accepted: list[str] = []
    completed: list[str] = []
    observations: list[str] = []

    def check_state(obj: Mapping[str, Any]) -> None:
        _identity(obj, "state", True)
        _check(
            obj["task_id"] == contract["task"]["id"]
            and obj["candidate_id"] == candidate["id"]
            and obj["visible_evidence_ids"] == sorted(bound["by_id"])
            and obj["accepted_claims"] == accepted
            and obj["completed_nodes"] == completed
            and obj["observations"] == observations,
            "replay.state",
            "state does not reflect actual accepted observations and claims",
        )

    check_state(state)
    replayed = []
    ratio_inputs = None
    for node, step in zip(candidate["nodes"], records["steps"], strict=True):
        _check(
            set(node) == {"name", "operation", "parameters", "inputs"} and set(step) == STEP_FIELDS,
            "replay.record_schema",
            "plan or step fields differ",
        )
        for kind in STEP_FIELDS:
            _identity(step[kind], kind, True)
        p, receipt, execution, observation, claim, update = (
            step[k] for k in ("proposal", "receipt", "execution", "observation", "claim", "update")
        )
        operation = node["operation"]
        _check(operation in contract["operations"], "replay.operation", "unregistered operation")
        expected_refs = []
        for operand in node["inputs"]:
            _check(
                set(operand) == {"role", "kind", "ref"}
                and operand["kind"] in {"evidence", "claim"},
                "replay.input_reference",
                "invalid candidate input reference",
            )
            actual_ref = operand["ref"] if operand["kind"] == "evidence" else names[operand["ref"]]
            expected_refs.append(
                {"role": operand["role"], "kind": operand["kind"], "ref_id": actual_ref}
            )
        _check(
            p["task_id"] == contract["task"]["id"]
            and p["candidate_id"] == candidate["id"]
            and p["node"] == node["name"]
            and p["operation"] == operation
            and p["operation_contract_id"] == contract["operations"][operation]["id"]
            and p["parameters"] == node["parameters"]
            and p["inputs"] == expected_refs
            and p["pre_state_id"] == state["id"]
            and p["owner"] == "deterministic_fixture",
            "replay.proposal",
            "proposal is not grounded in the actual prior state and frozen plan",
        )
        _check(
            receipt["proposal_id"] == p["id"]
            and receipt["pre_state_id"] == state["id"]
            and receipt["admitted"] is True
            and receipt["checks"]
            == {
                "exact_parameters": True,
                "actual_roles": True,
                "source_context": True,
                "local_relation_or_ratio_semantics": True,
            }
            and receipt["proposal_sha256"] == hashlib.sha256(canonical_json_bytes(p)).hexdigest()
            and receipt["proposal_byte_count"] == len(canonical_json_bytes(p))
            and receipt["no_replace"] is True
            and receipt["proposal_file_and_directory_fsynced"] is True,
            "replay.receipt",
            "admission receipt does not bind the persisted proposal",
        )
        resolved = []
        for operand in expected_refs:
            if operand["kind"] == "evidence":
                resolved.append(_source_input(bound["by_id"][operand["ref_id"]], operand))
            else:
                previous = claims[operand["ref_id"]]
                resolved.append(
                    {
                        **operand,
                        **previous["proposition"],
                        "producer_operation": operations[previous["id"]],
                    }
                )
        _check(
            p["requires_basis"] == sorted({ref for item in resolved for ref in item["lineage"]}),
            "replay.proposal_basis",
            "proposal support does not match actual visible/accepted lineage",
        )
        expected = _recompute(operation, resolved, p["parameters"], contract, bound)
        _check(
            execution["proposal_id"] == p["id"]
            and execution["receipt_id"] == receipt["id"]
            and execution["operation"] == operation
            and execution["parameters"] == p["parameters"]
            and execution["inputs"] == resolved,
            "replay.actual_inputs",
            "execution did not consume actual referenced objects",
        )
        _check(
            execution["output"] == expected,
            "replay.operation_output",
            "actual operation output differs from independent arithmetic/lineage",
        )
        _check(
            observation["execution_id"] == execution["id"]
            and observation["success"] is True
            and observation["output"] == expected,
            "replay.observation",
            "Observation is not the actual execution result",
        )
        _check(
            claim["task_id"] == contract["task"]["id"]
            and claim["node"] == node["name"]
            and claim["proposition"] == expected
            and claim["observation_id"] == observation["id"]
            and claim["status"] == "accepted"
            and claim["grounding"] == expected["lineage"]
            and claim["owner"] == "deterministic_fixture",
            "replay.claim",
            "accepted Claim is not grounded in the observed result",
        )
        _check(
            update["pre_state_id"] == state["id"]
            and update["observation_id"] == observation["id"]
            and update["accepted_claim_id"] == claim["id"]
            and update["decision"] == "accept_observed_claim"
            and update["owner"] == "deterministic_fixture",
            "replay.update",
            "actual update did not accept this observed Claim",
        )
        if operation == "share_ratio":
            _check(
                ratio_inputs is None, "replay.plan", "multiple share-ratio goals are unsupported"
            )
            ratio_inputs = resolved
        if operation == "relation_sum":
            difference = abs(_decimal(expected["value"]) - _decimal(bound["values"]["total"]))
            _check(
                difference <= Decimal(contract["numeric"]["source_reconciliation_tolerance"]),
                "replay.source_reconciliation",
                "actual reconstructed sum exceeds frozen disclosed-total reconciliation tolerance",
            )
        claims[claim["id"]] = claim
        operations[claim["id"]] = operation
        names[node["name"]] = claim["id"]
        accepted.append(claim["id"])
        completed.append(node["name"])
        observations.append(observation["id"])
        check_state(step["state"])
        state = step["state"]
        replayed.append(
            {
                "operation": operation,
                "actual_inputs": resolved,
                "independent_output": expected,
                "claim_id": claim["id"],
                "observation_id": observation["id"],
                "oracle_output_substituted": False,
            }
        )
    final = records["final"]
    _identity(final, "final", True)
    producer = claims[names[candidate["output_node"]]]
    _check(
        final["task_id"] == contract["task"]["id"]
        and final["candidate_id"] == candidate["id"]
        and final["pre_state_id"] == state["id"]
        and final["answer_claim_id"] == producer["id"]
        and operations[producer["id"]] == "scale_percent"
        and final["owner"] == "deterministic_fixture",
        "replay.final_grounding",
        "Final does not consume the actual accepted percentage Claim",
    )
    expected_answer = str(
        _decimal(producer["proposition"]["value"]).quantize(Decimal(NUMERIC["final_quantum"]))
    )
    _check(
        final["answer"] == {"value": expected_answer, "unit": "percent"}
        and final["citations"] == producer["grounding"],
        "replay.final_grounding",
        "Final answer or citations do not reflect actual producing Claim",
    )
    _check(ratio_inputs is not None, "replay.ratio_roles", "no actual share ratio")
    if ratio_inputs is None:
        raise ReplayError("replay.ratio_roles", "no actual share ratio")
    denominator = ratio_inputs[1]
    derived = denominator["kind"] == "claim" and denominator["producer_operation"] == "relation_sum"
    _check(
        (candidate["route"] == "S" and derived) or (candidate["route"] == "D" and not derived),
        "replay.claimed_denominator_support",
        "declared denominator support is contradicted by the actual consumed input",
    )
    return {
        "trajectory_valid": True,
        "trajectory_operation_replay_count": len(replayed),
        "actual_operation_replay": replayed,
        "actual_denominator": {
            "kind": denominator["kind"],
            "ref_id": denominator["ref_id"],
            "value": denominator["value"],
            "lineage": denominator["lineage"],
            "producer_operation": denominator["producer_operation"],
            "mechanism": "reconstructed_members" if derived else "disclosed_total",
        },
        "actual_support_evidence_ids": producer["grounding"],
        "source_relation_preconditions_required_by_actual_path": derived,
        "common_obligations": {name: True for name in OBLIGATIONS},
        "coverage": {"numerator": 4, "denominator": 4, "obligations": OBLIGATIONS},
        "source_reconciliation_is_validator_check_not_candidate_operation": True,
    }


def validate_records(
    contract: Mapping[str, Any], source: Mapping[str, Any], records: Mapping[str, Any]
) -> dict[str, Any]:
    """Validate decoded actual objects; no supplied success label is authoritative."""
    report: dict[str, Any] = {
        "schema_version": "part_whole_share_own_validation.v1",
        "qa_valid": False,
        "trajectory_valid": False,
        "qualified": False,
        "first_failure": None,
        "failures": [],
        "field_origin": "host_derived",
        "common_obligations": {name: False for name in OBLIGATIONS},
        "coverage": {"numerator": 0, "denominator": 4, "obligations": OBLIGATIONS},
        "candidate_runtime_executions": 0,
        "provider_calls": 0,
        "credential_reads": 0,
        "gpu_calls": 0,
        "validator_imports_runtime_or_admission": False,
        "source_task_replay_valid": False,
    }
    with localcontext() as context:
        context.prec = 50
        context.rounding = ROUND_HALF_EVEN
        try:
            bound = _source_and_contract(contract, source)
            report["source_task_replay_valid"] = True
            _identity(records["final"], "final", True)
        except (OSError, ValueError, KeyError, TypeError, IndexError, ArithmeticError) as error:
            report["failures"].append(
                {
                    "stage": getattr(error, "stage", "replay.missing_or_invalid_object"),
                    "reason": str(error),
                }
            )
        else:
            for validator, args in (
                (_answer_oracle, (contract, bound, records["final"])),
                (_trajectory, (contract, source, records, bound)),
            ):
                try:
                    report.update(validator(*args))
                except (
                    OSError,
                    ValueError,
                    KeyError,
                    TypeError,
                    IndexError,
                    ArithmeticError,
                ) as error:
                    report["failures"].append(
                        {
                            "stage": getattr(error, "stage", "replay.missing_or_invalid_object"),
                            "reason": str(error),
                        }
                    )
            if not report["qa_valid"] and not report["failures"]:
                report["failures"].append(
                    {
                        "stage": "qa.answer_or_citations",
                        "reason": "Final differs from frozen answer/citation contract",
                    }
                )
    report["qualified"] = report["qa_valid"] and report["trajectory_valid"]
    report["V_QA"], report["V_trajectory"], report["V_Q"] = (
        report["qa_valid"],
        report["trajectory_valid"],
        report["qualified"],
    )
    report["first_failure"] = report["failures"][0] if report["failures"] else None
    return report


def read_trajectory_records(artifact_root: str | Path) -> dict[str, Any]:
    """Authenticate bytes, complete file inventory and durable pre-action order."""
    requested = Path(artifact_root)
    _check(not requested.is_symlink(), "replay.artifact_path", "artifact root is a symlink")
    root = requested.resolve()
    inventory = list(root.rglob("*"))
    _check(
        not any(path.is_symlink() for path in inventory),
        "replay.artifact_path",
        "symlink in actual trajectory artifact tree",
    )
    manifest_path = root / "execution_manifest.json"
    manifest_bytes = manifest_path.read_bytes()
    manifest = json.loads(manifest_bytes)
    _check(
        manifest_bytes == canonical_json_bytes(manifest),
        "replay.canonical_bytes",
        "manifest bytes are not canonical",
    )
    _identity(manifest, "execution_manifest")
    _check(
        set(manifest)
        == {
            "id",
            "schema_version",
            "task_id",
            "candidate_id",
            "contract_id",
            "records",
            "members",
            "action_count",
            "actual_executor_calls",
            "oracle_calls",
            "write_events",
        },
        "replay.manifest",
        "manifest schema contains missing or unsupported fields",
    )
    members: dict[str, Any] = {}
    for entry in manifest["members"]:
        _check(
            set(entry) == {"relative_path", "sha256", "byte_count"},
            "replay.manifest",
            "unsupported member declaration",
        )
        relative = entry["relative_path"]
        path = (root / relative).resolve()
        _check(
            not Path(relative).is_absolute()
            and ".." not in Path(relative).parts
            and path.is_relative_to(root)
            and relative not in members
            and relative != "execution_manifest.json",
            "replay.artifact_path",
            "unsafe or duplicate manifest member",
        )
        payload = path.read_bytes()
        _check(
            len(payload) == entry["byte_count"]
            and hashlib.sha256(payload).hexdigest() == entry["sha256"],
            "replay.artifact_bytes",
            "persisted trajectory bytes differ from manifest",
        )
        value = json.loads(payload)
        _check(
            payload == canonical_json_bytes(value),
            "replay.canonical_bytes",
            "trajectory member is not canonical",
        )
        members[relative] = value
    actual_files = {path.relative_to(root).as_posix() for path in inventory if path.is_file()}
    _check(
        actual_files == set(members) | {"execution_manifest.json"},
        "replay.artifact_inventory",
        "actual files differ from complete manifest membership",
    )
    used: list[str] = []

    def resolve(value: Any) -> Any:
        if isinstance(value, str):
            used.append(value)
            return members[value]
        if isinstance(value, list):
            return [resolve(item) for item in value]
        if isinstance(value, Mapping):
            return {key: resolve(item) for key, item in value.items()}
        raise ReplayError("replay.manifest", "unsupported manifest reference object")

    paths = manifest["records"]
    _check(
        set(paths) == {"candidate", "initial_state", "steps", "final"}
        and all(set(step) == STEP_FIELDS for step in paths["steps"]),
        "replay.manifest",
        "missing actual object path mapping",
    )
    records = resolve(paths)
    _check(
        len(used) == len(set(used)) and set(used) == set(members),
        "replay.manifest",
        "manifest has duplicate uses, missing objects or unaccounted members",
    )
    candidate = records["candidate"]
    _check(
        manifest["candidate_id"] == candidate["id"]
        and manifest["task_id"] == candidate["task_id"]
        and manifest["contract_id"] == candidate["contract_id"]
        and manifest["action_count"] == manifest["actual_executor_calls"] == len(records["steps"])
        and manifest["oracle_calls"] == 0,
        "replay.manifest",
        "manifest identities or execution/oracle counters differ from actual objects",
    )
    ordered_paths = [paths["candidate"], paths["initial_state"]]
    for step in paths["steps"]:
        ordered_paths.extend(
            step[kind]
            for kind in (
                "proposal",
                "receipt",
                "execution",
                "observation",
                "claim",
                "update",
                "state",
            )
        )
    ordered_paths.append(paths["final"])
    expected_events: list[dict[str, Any]] = []
    for path in ordered_paths:
        for kind in ("file_fsync", "directory_fsync"):
            expected_events.append(
                {"event_ordinal": len(expected_events) + 1, "kind": kind, "relative_path": path}
            )
    _check(
        manifest["write_events"] == expected_events,
        "replay.preaction_order",
        (
            "actual file/directory sync log does not establish proposal < receipt < execution "
            "< Observation < Claim < update < state < Final"
        ),
    )
    return records


def validate_trajectory(
    contract: Mapping[str, Any], source: Mapping[str, Any], artifact_root: str | Path
) -> dict[str, Any]:
    """Validate actual persisted files, including byte-level manifest binding."""
    try:
        records = read_trajectory_records(artifact_root)
    except (OSError, ValueError, KeyError, TypeError, IndexError) as error:
        return {
            "schema_version": "part_whole_share_own_validation.v1",
            "qa_valid": False,
            "trajectory_valid": False,
            "qualified": False,
            "V_QA": False,
            "V_trajectory": False,
            "V_Q": False,
            "first_failure": {
                "stage": getattr(error, "stage", "replay.missing_or_invalid_artifact"),
                "reason": str(error),
            },
            "persisted_artifact_validation": False,
        }
    result = validate_records(contract, source, records)
    result["persisted_artifact_validation"] = True
    return result
