"""New source-parameterized Share adapter, isolated from the old Share binding.

Numeric executors are reused; metric roles, task/source identity and dependency
admission belong to this new per-binding semantic contract.
"""

from __future__ import annotations

import copy
from decimal import ROUND_HALF_EVEN, Decimal, localcontext
from typing import Any

from trusted_synthesis.core.operations.registry import (
    OperationRegistry,
    ScalarOutput,
    make_operation_definition,
    operation_semantic_contract_hash,
)
from trusted_synthesis.core.operations.schema import OperationInput
from trusted_synthesis.experiments.finance_qa_vnext_cross_binding.source import (
    CONTEXT_FIELDS,
    FAMILY,
    BoundShareSource,
    validate_bound_source,
)

from .protocol import record, require
from .share_adapter import SHARE_OPERATIONS, ShareExecutor, ShareOracle, public_share_answer


def bound_share_registry(source: BoundShareSource) -> OperationRegistry:
    registry = OperationRegistry()
    for operation in SHARE_OPERATIONS:
        registry.register(
            make_operation_definition(
                operation,
                ShareExecutor(operation),
                ShareOracle(operation),
                "many:any",
                "scalar",
                "none",
                (
                    "bound_source_parameterized_admission_required",
                    "same_task_accepted_claim_inputs_only",
                    "precision_50",
                ),
                output_model=ScalarOutput,
                tool_capability="calculator",
                input_role_contract={
                    "relation_sum": ("member", "member", "relation"),
                    "share_ratio": ("numerator", "denominator"),
                    "scale_percent": ("ratio",),
                }[operation],
                parameter_contract=(source.semantic_contract["id"],),
                semantic_version="3.0.0",
                formula_id="bound_share." + operation + ".v3." + source.semantic_contract["id"],
            )
        )
    return registry


class BoundShareTaskAdapter:
    def __init__(self, source: BoundShareSource):
        validate_bound_source(source)
        self.source = source
        self.registry = bound_share_registry(source)
        self.semantic_contract = source.semantic_contract
        self.evidence = {item["id"]: copy.deepcopy(item) for item in source.evidence.values()}
        self.binding = record(
            "cross_binding_receipt",
            source_key=source.source_key,
            status="bound_new_share_source",
            source_bindable=True,
            source_binding_id=source.source_binding_id,
            source_group_id=source.binding_record["source_group"]["id"],
            source_record_id=source.binding_record["source_record_id"],
            semantic_contract_id=self.semantic_contract["id"],
            original_model_or_fixture_execution_reused=False,
        )
        self.adapter_registration = record(
            "cross_binding_adapter_registration",
            task_id=source.task_id,
            source_binding_id=source.source_binding_id,
            semantic_contract_id=self.semantic_contract["id"],
            adapter_family=FAMILY,
            implementation="BoundShareTaskAdapter.v1",
        )
        resolution = record(
            "cross_binding_catalog_resolution",
            task_type=FAMILY,
            task_id=source.task_id,
            adapter_id=self.adapter_registration["id"],
            source_binding_id=source.source_binding_id,
            registered=True,
            source_bindable=True,
            old_catalog_modified=False,
        )
        self.context = record(
            "context",
            task_id=source.task_id,
            task_type=FAMILY,
            adapter_id=self.adapter_registration["id"],
            task=source.task,
            evidence=source.evidence,
            numeric=self.semantic_contract["numeric"],
            semantic_contract=self.semantic_contract,
            source_binding=self.binding,
            catalog_resolution=resolution,
            registry_hash=record("registry", members=self.registry.manifest())["id"],
            final_projection="share_percent_quantized",
            uncertainties=[],
            obligations=["legitimate_total_support", "ratio", "percent"],
            accepted_claim_revision_supported=False,
            old_states_or_assignments_modified=False,
        )

    def _check_claim(self, claim: dict[str, Any]) -> None:
        require(claim["status"] == "accepted", "bound_share.accepted_input")
        proposition = claim["proposition"]
        require(
            proposition.get("task_id") == self.source.task_id
            and proposition.get("source_binding_id") == self.source.source_binding_id
            and proposition.get("semantic_contract_id") == self.semantic_contract["id"],
            "bound_share.cross_task_claim",
        )
        operation = proposition["operation"]
        require(operation in SHARE_OPERATIONS, "bound_share.claim_operation")
        require(
            proposition["operation_contract_id"]
            == operation_semantic_contract_hash(self.registry.require(operation)),
            "bound_share.claim_contract",
        )
        output = proposition["output"]
        require(
            output["lineage"] == proposition["lineage"]
            and bool(output["lineage"])
            and set(output["lineage"]) <= set(self.evidence),
            "bound_share.claim_lineage",
        )
        prepared = {
            "operation": operation,
            "lineage": output["lineage"],
            "operation_contract_id": proposition["operation_contract_id"],
        }
        require(
            proposition == self._proposition(prepared, output["value"]),
            "bound_share.claim_metadata",
        )

    def offers(self, claims: list[dict[str, Any]]) -> list[dict[str, Any]]:
        for item in claims:
            self._check_claim(item)
        by_goal = {item["obligation_id"]: item for item in claims}
        if "percent" in by_goal:
            return []
        evidence = self.source.evidence

        def ref(kind: str, role: str, key: str) -> dict[str, str]:
            return {
                "kind": kind,
                "role": role,
                "ref_id": evidence[key]["id"] if kind == "evidence" else by_goal[key]["id"],
            }

        raw: list[tuple[str, str, list[dict[str, str]], dict[str, str], str]] = []
        if "ratio" in by_goal:
            raw.append(("scale_percent", "percent", [ref("claim", "ratio", "ratio")], {}, "scale"))
        else:
            if "total" not in by_goal:
                raw.append(
                    (
                        "relation_sum",
                        "total",
                        [
                            ref("evidence", "member", "target_component"),
                            ref("evidence", "member", "other_component"),
                            ref("evidence", "relation", "composition_relation"),
                        ],
                        {"method": "sum"},
                        "reconstructed_total",
                    )
                )
            raw.append(
                (
                    "share_ratio",
                    "ratio",
                    [
                        ref("evidence", "numerator", "target_component"),
                        ref("evidence", "denominator", "disclosed_total"),
                    ],
                    {},
                    "disclosed_total",
                )
            )
            if "total" in by_goal:
                raw.append(
                    (
                        "share_ratio",
                        "ratio",
                        [
                            ref("evidence", "numerator", "target_component"),
                            ref("claim", "denominator", "total"),
                        ],
                        {},
                        "reconstructed_total",
                    )
                )
        result = []
        accepted = {item["id"]: item for item in claims}
        for operation, goal, inputs, parameters, choice in raw:
            lineage = sorted(
                {
                    eid
                    for item in inputs
                    for eid in (
                        [item["ref_id"]]
                        if item["kind"] == "evidence"
                        else accepted[item["ref_id"]]["proposition"]["lineage"]
                    )
                }
            )
            result.append(
                record(
                    "offered_action",
                    obligation_id=goal,
                    operation=operation,
                    inputs=inputs,
                    parameters=parameters,
                    operation_contract_id=operation_semantic_contract_hash(
                        self.registry.require(operation)
                    ),
                    subgoal="derive_quantity"
                    if operation == "scale_percent"
                    else "select_total_support",
                    basis={
                        "relation": "requires",
                        "evidence_refs": lineage,
                        "claim_refs": sorted(
                            item["ref_id"] for item in inputs if item["kind"] == "claim"
                        ),
                    },
                    expected_effect={"establishes_obligation": goal, "output_schema": "scalar"},
                    selection_rules=[
                        "registered_semantic_preconditions" if choice == "scale" else choice
                    ],
                    alternative_group="percent"
                    if operation == "scale_percent"
                    else "legitimate_total_support",
                    semantic_choice=choice,
                    input_order_policy="members_permutation_invariant_relation_fixed"
                    if operation == "relation_sum"
                    else "ordered",
                )
            )
        return result

    def prepare(self, offer: dict[str, Any], claims: list[dict[str, Any]]) -> dict[str, Any]:
        # Resolve from this task only. Matching numbers do not grant source authority.
        require(offer in self.offers(claims), "bound_share.offer_not_current")
        accepted = {item["id"]: item for item in claims}
        resolved = []
        for ref in offer["inputs"]:
            if ref["kind"] == "evidence":
                item = self.evidence[ref["ref_id"]]
                content = (
                    {"relation": copy.deepcopy(item), "lineage": [item["id"]]}
                    if item["kind"] == "part_whole"
                    else {
                        **{
                            key: item[key]
                            for key in ("value", "metric", "definition", *CONTEXT_FIELDS)
                        },
                        "lineage": [item["id"]],
                        "producer_operation": None,
                    }
                )
            else:
                item = accepted[ref["ref_id"]]
                self._check_claim(item)
                content = {
                    **item["proposition"]["output"],
                    "producer_operation": item["proposition"]["operation"],
                }
            resolved.append({**ref, **content})
        self._admit(offer["operation"], resolved)
        return {
            "operation": offer["operation"],
            "inputs": tuple(OperationInput(ref_id=item["ref_id"], value=item) for item in resolved),
            "parameters": offer["parameters"],
            "lineage": offer["basis"]["evidence_refs"],
            "slot": offer["obligation_id"],
            "operation_contract_id": offer["operation_contract_id"],
        }

    def _admit(self, operation: str, inputs: list[dict[str, Any]]) -> None:
        evidence = self.source.evidence
        numeric = [item for item in inputs if item["role"] != "relation"]
        for item in numeric:
            require(Decimal(item["value"]).is_finite(), "bound_share.finite_input")
            require(
                all(
                    item[key] == self.source.context[key] for key in CONTEXT_FIELDS if key != "unit"
                ),
                "bound_share.source_context",
            )
        if operation == "relation_sum":
            require(all(item["kind"] == "evidence" for item in inputs), "bound_share.raw_members")
            relation = inputs[2]["relation"]
            require(
                relation == evidence["composition_relation"]
                and relation["exhaustive"] is True
                and relation["nonoverlapping"] is True
                and set(relation["member_ids"]) == {inputs[0]["ref_id"], inputs[1]["ref_id"]},
                "bound_share.structural_members",
            )
            require(
                all(item["unit"] == self.source.context["unit"] for item in numeric),
                "bound_share.sum_unit",
            )
        elif operation == "share_ratio":
            numerator, denominator = inputs
            require(
                numerator["ref_id"] == evidence["target_component"]["id"]
                and numerator["metric"] == evidence["target_component"]["metric"]
                and denominator["metric"] == evidence["disclosed_total"]["metric"]
                and numerator["unit"] == denominator["unit"] == self.source.context["unit"],
                "bound_share.ratio_roles",
            )
            require(Decimal(denominator["value"]) != 0, "bound_share.zero_denominator")
            if denominator["kind"] == "claim":
                require(
                    denominator["producer_operation"] == "relation_sum"
                    and set(denominator["lineage"])
                    == {
                        evidence[role]["id"]
                        for role in ("target_component", "other_component", "composition_relation")
                    },
                    "bound_share.actual_reconstructed_support",
                )
            else:
                require(
                    denominator["ref_id"] == evidence["disclosed_total"]["id"],
                    "bound_share.disclosed_total",
                )
        else:
            require(
                inputs[0]["kind"] == "claim"
                and inputs[0]["producer_operation"] == "share_ratio"
                and inputs[0]["metric"] == self.semantic_contract["ratio_metric"]
                and inputs[0]["unit"] == "ratio",
                "bound_share.percent_input",
            )

    def _proposition(self, prepared: dict[str, Any], value: str) -> dict[str, Any]:
        operation = prepared["operation"]
        evidence = self.source.evidence
        metrics = {
            "relation_sum": evidence["disclosed_total"]["metric"],
            "share_ratio": self.semantic_contract["ratio_metric"],
            "scale_percent": self.semantic_contract["percent_metric"],
        }
        units = {
            "relation_sum": self.source.context["unit"],
            "share_ratio": "ratio",
            "scale_percent": "percent",
        }
        definitions = {
            "relation_sum": evidence["disclosed_total"]["definition"],
            "share_ratio": evidence["target_component"]["definition"]
            + " divided by legitimate "
            + evidence["disclosed_total"]["definition"],
            "scale_percent": evidence["target_component"]["definition"] + " share in percent",
        }
        return {
            "task_id": self.source.task_id,
            "source_binding_id": self.source.source_binding_id,
            "semantic_contract_id": self.semantic_contract["id"],
            "operation": operation,
            "operation_contract_id": prepared["operation_contract_id"],
            "lineage": prepared["lineage"],
            "output": {
                **self.source.context,
                "value": value,
                "metric": metrics[operation],
                "unit": units[operation],
                "definition": definitions[operation],
                "lineage": prepared["lineage"],
            },
        }

    def execute(self, prepared: dict[str, Any]) -> dict[str, Any]:
        definition = self.registry.require(prepared["operation"])
        output = definition.executor.execute(prepared["inputs"], prepared["parameters"])
        self.registry.validate_output(definition, output)
        return self._proposition(prepared, output["value"])

    def verify_execution(self, prepared: dict[str, Any], proposition: dict[str, Any]) -> bool:
        check = self.registry.require(prepared["operation"]).oracle_verifier.verify(
            prepared["inputs"], prepared["parameters"], {"value": proposition["output"]["value"]}
        )
        return check.passed and proposition == self._proposition(
            prepared, proposition["output"]["value"]
        )

    def final_claims(self, claims: list[dict[str, Any]]) -> list[str]:
        for claim in claims:
            self._check_claim(claim)
        return [
            claim["id"]
            for claim in claims
            if claim["obligation_id"] == "percent"
            and claim["proposition"]["operation"] == "scale_percent"
        ]

    def verify_final(self, final: dict[str, Any], claims: list[dict[str, Any]]) -> dict[str, Any]:
        require(final["answer_claim_id"] in self.final_claims(claims), "bound_share.final_claim")
        claim = next(item for item in claims if item["id"] == final["answer_claim_id"])
        expected = public_share_answer(self.context, claim)
        with localcontext() as numeric:
            numeric.prec = 50
            numeric.rounding = ROUND_HALF_EVEN
            value = (
                Decimal(self.source.evidence["target_component"]["value"])
                / Decimal(self.source.evidence["disclosed_total"]["value"])
                * 100
            )
            oracle = str(
                value.quantize(Decimal(self.semantic_contract["numeric"]["final_quantum"]))
            )
        answer_valid = final["result"] == expected and expected["value"] == oracle
        citation_valid = len(final["citations"]) == len(set(final["citations"])) and set(
            final["citations"]
        ) == set(claim["proposition"]["lineage"])
        return record(
            "qa_validation",
            task_id=self.source.task_id,
            source_binding_id=self.binding["id"],
            source_valid=True,
            answer_valid=answer_valid,
            citation_valid=citation_valid,
            qa_valid=answer_valid and citation_valid,
            reference_program_used_for_callback=False,
        )
