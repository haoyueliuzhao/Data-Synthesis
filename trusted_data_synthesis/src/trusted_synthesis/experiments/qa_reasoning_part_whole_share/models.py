"""Finite contracts, identity checking and genuine heterogeneous input admission."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from trusted_synthesis.canonical_json import strict_canonical_hash

STAGE = "finance_qa_vnext_part_whole_share_dual_support_preflight_only"
REVIEW_BYTES = 22_925
REVIEW_SHA256 = "91ed0480d5e235c0438c01a89a8ea58add7a03fe6872523ce4f6b2d6b4837125"
DIRECTIVE = "参照审计继续实验"
DIRECTIVE_SHA256 = "b2dc80634c27edf4db128ad352e77776e2dfe3242a450bfa62783d426b298fcb"
PARENT = (
    "trusted_data_synthesis/artifacts/qa_reasoning_source_distinct_support/"
    "finance_qa_vnext_source_distinct_support_route_constructibility_"
    "and_finite_separation_preflight_v1_20260905"
)
PARENT_MANIFEST = (
    "qa_source_distinct_support_manifest:"
    "7d1f92e85a9cfaadbde5f3774a5898283270d1bf7d4a75409513bbff3e790f3c"
)
PARENT_ROOT = (
    "qa_source_distinct_support_root:"
    "27047db451b404e972da64ca7b61902cdf79db05bdae129aa3a260d2946e4e60"
)
REFERENCE_COMMIT = "595ff258a67f78ecd1779df0cda7fa7d8e1611a9"
CONTEXT_FIELDS = ("subject", "scope", "period", "unit", "currency")


class ShareError(ValueError):
    def __init__(self, stage: str, message: str) -> None:
        super().__init__(message)
        self.stage = stage


def require(condition: bool, stage: str, message: str) -> None:
    if not condition:
        raise ShareError(stage, message)


def record(record_type: str, **values: Any) -> dict[str, Any]:
    require("id" not in values and "schema_version" not in values, "identity.input", "caller ID")
    body = {"schema_version": f"part_whole_share_{record_type}.v1", **values}
    return {**body, "id": strict_canonical_hash(body, prefix=f"part_whole_share_{record_type}:")}


def validate_record(obj: dict[str, Any]) -> None:
    kind = obj["schema_version"].removeprefix("part_whole_share_").removesuffix(".v1")
    body = {k: v for k, v in obj.items() if k != "id"}
    require(
        obj["id"] == strict_canonical_hash(body, prefix=f"part_whole_share_{kind}:"),
        "identity.content",
        "object identity differs from actual contents",
    )


def contract_for(source: dict[str, Any], measurement: dict[str, Any]) -> dict[str, Any]:
    evidence = source["evidence"]
    f = evidence["freight"]
    task = record(
        "task",
        source_binding_id=source["id"],
        question=(
            f"For {f['subject']} in fiscal year {f['period']}, what percentage of "
            "total operating revenues was total freight revenues? Report to six "
            "decimal places and cite the actual calculation support."
        ),
        evidence_universe_ids=sorted(e["id"] for e in evidence.values()),
        **{key: f[key] for key in CONTEXT_FIELDS},
        target="100 * total_freight_revenues / total_operating_revenues",
        original_compound_task_changed=False,
        is_new_task=True,
    )
    operations = {
        "relation_sum": record(
            "operation_contract",
            operation="relation_sum",
            version="1.0.0",
            parameters={"method": "sum"},
            input_roles=["member", "member", "relation"],
            input_order_policy="members_permutation_invariant_relation_fixed",
            output_metric=evidence["total"]["metric"],
            output_unit=f["unit"],
            program_role="semantic",
            semantics="source-explicit exhaustive disjoint members -> derived total Claim",
            raw_evidence_metadata_rewriting_permitted=False,
            disclosed_total_value_read_by_executor=False,
        ),
        "share_ratio": record(
            "operation_contract",
            operation="share_ratio",
            version="1.0.0",
            parameters={},
            input_roles=["numerator", "denominator"],
            input_order_policy="ordered",
            output_metric="freight_share_ratio",
            output_unit="ratio",
            program_role="semantic",
            numerator_metric=evidence["freight"]["metric"],
            denominator_metric=evidence["total"]["metric"],
            semantics="same-period freight / legitimate disclosed-or-derived operating total",
        ),
        "scale_percent": record(
            "operation_contract",
            operation="scale_percent",
            version="1.0.0",
            parameters={},
            input_roles=["ratio"],
            input_order_policy="ordered",
            output_metric="freight_share_percent",
            output_unit="percent",
            program_role="semantic",
            semantics="exact ratio scalar multiplied by 100",
        ),
    }
    return record(
        "contract",
        stage=STAGE,
        task=task,
        source_binding_id=source["id"],
        operations=operations,
        numeric={
            "precision": 50,
            "rounding": "ROUND_HALF_EVEN",
            "final_quantum": "0.000001",
            "source_reconciliation_tolerance": "0",
            "answer_tolerance": "0",
        },
        shared_obligations=[
            "period_scope",
            "numerator_denominator",
            "percent_unit",
            "final_grounding",
        ],
        route_specific_preconditions={
            "D": [],
            "S": ["complete_disjoint_relation", "actual_sum_claim_consumed"],
        },
        answer_schema={"value": "finite decimal string quantized to six places", "unit": "percent"},
        actual_support_citations_required=True,
        all_visible_evidence_citations_required=False,
        runtime_action_bound=3,
        maximum_candidate_executions=2,
        maximum_same_task_pairs=1,
        old_registry_modified=False,
        catalog_promotion=False,
        new_relation_and_ratio_interfaces="local finite contracts, not old aggregate compatibility",
        measurement=measurement,
        source_selection_is_known_target_not_blind=True,
    )


def candidates_for(contract: dict[str, Any], source: dict[str, Any]) -> list[dict[str, Any]]:
    e = source["evidence"]

    def ref(role: str, kind: str, value: str) -> dict[str, str]:
        return {"role": role, "kind": kind, "ref": value}

    result = []
    for route in ("D", "S"):
        nodes = []
        if route == "S":
            nodes.append(
                {
                    "name": "sum",
                    "operation": "relation_sum",
                    "parameters": {"method": "sum"},
                    "inputs": [
                        ref("member", "evidence", e["freight"]["id"]),
                        ref("member", "evidence", e["other"]["id"]),
                        ref("relation", "evidence", e["part_whole"]["id"]),
                    ],
                }
            )
        nodes.extend(
            [
                {
                    "name": "ratio",
                    "operation": "share_ratio",
                    "parameters": {},
                    "inputs": [
                        ref("numerator", "evidence", e["freight"]["id"]),
                        ref(
                            "denominator",
                            "evidence" if route == "D" else "claim",
                            e["total"]["id"] if route == "D" else "sum",
                        ),
                    ],
                },
                {
                    "name": "percent",
                    "operation": "scale_percent",
                    "parameters": {},
                    "inputs": [ref("ratio", "claim", "ratio")],
                },
            ]
        )
        result.append(
            record(
                "candidate",
                task_id=contract["task"]["id"],
                contract_id=contract["id"],
                route=route,
                controller="deterministic_fixture",
                nodes=nodes,
                output_node="percent",
            )
        )
    return result


def admit_inputs(
    operation: str,
    inputs: list[dict[str, Any]],
    parameters: dict[str, Any],
    contract: dict[str, Any],
    source: dict[str, Any],
) -> dict[str, bool]:
    """Check real members and roles before arithmetic. Never rewrite Evidence."""
    require(operation in contract["operations"], "admission.operation", "unknown operation")
    op = contract["operations"][operation]
    require(parameters == op["parameters"], "admission.parameters", "exact parameters differ")
    require(
        [x["role"] for x in inputs] == op["input_roles"], "admission.roles", "operand roles differ"
    )
    e = source["evidence"]
    context = {k: e["freight"][k] for k in CONTEXT_FIELDS}
    numeric = [x for x in inputs if x["role"] != "relation"]
    for item in numeric:
        require(Decimal(item["value"]).is_finite(), "admission.numeric", "nonfinite input")
        fields = (
            CONTEXT_FIELDS
            if operation != "scale_percent"
            else ("subject", "scope", "period", "currency")
        )
        for field in fields:
            require(item[field] == context[field], "admission." + field, "source context differs")
    if operation == "relation_sum":
        members, relation = inputs[:2], inputs[2]
        expected = e["part_whole"]
        require(
            len({m["ref_id"] for m in members}) == 2
            and sorted(m["ref_id"] for m in members) == sorted(expected["member_ids"]),
            "admission.complete_members",
            "missing, duplicated or substituted component",
        )
        require(
            relation["ref_id"] == expected["id"]
            and relation["relation"] == expected
            and expected["exhaustive"]
            and expected["nonoverlapping"],
            "admission.source_relation",
            "unbound total/component relation",
        )
        by_id = {x["id"]: x for x in (e["freight"], e["other"])}
        for member in members:
            original = by_id[member["ref_id"]]
            require(
                member["kind"] == "evidence"
                and all(
                    member[k] == original[k]
                    for k in ("value", "metric", "definition", *CONTEXT_FIELDS)
                ),
                "admission.raw_component",
                "component metadata or value was rewritten",
            )
    elif operation == "share_ratio":
        numerator, denominator = inputs
        require(
            numerator["kind"] == "evidence"
            and numerator["ref_id"] == e["freight"]["id"]
            and numerator["metric"] == e["freight"]["metric"]
            and denominator["metric"] == e["total"]["metric"],
            "admission.ratio_metrics",
            "numerator/denominator metric roles differ",
        )
        require(Decimal(denominator["value"]) != 0, "admission.denominator", "zero denominator")
        if denominator["kind"] == "evidence":
            require(
                denominator["ref_id"] == e["total"]["id"],
                "admission.total",
                "wrong disclosed total",
            )
        else:
            require(
                denominator["producer_operation"] == "relation_sum"
                and sorted(denominator["lineage"])
                == sorted([e["freight"]["id"], e["other"]["id"], e["part_whole"]["id"]]),
                "admission.derived_total",
                "derived denominator lacks actual component lineage",
            )
    else:
        require(
            inputs[0]["kind"] == "claim"
            and inputs[0]["metric"] == "freight_share_ratio"
            and inputs[0]["unit"] == "ratio",
            "admission.percent",
            "wrong percent input",
        )
    return {
        "exact_parameters": True,
        "actual_roles": True,
        "source_context": True,
        "local_relation_or_ratio_semantics": True,
    }
