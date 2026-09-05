"""The existing source-explicit Share task implemented by the common v2 runtime."""

from __future__ import annotations

import copy
import hashlib
import json
from decimal import ROUND_HALF_EVEN, Decimal, localcontext
from pathlib import Path
from typing import Any

from trusted_synthesis.core.operations.registry import (
    OperationRegistry,
    ScalarOutput,
    make_operation_definition,
    operation_semantic_contract_hash,
)
from trusted_synthesis.core.operations.schema import OperationInput, OperationVerification
from trusted_synthesis.experiments.qa_reasoning_finite_comparison.inputs import (
    files_at,
    validate_manifest,
)
from trusted_synthesis.experiments.qa_reasoning_part_whole_share.models import (
    CONTEXT_FIELDS,
    admit_inputs,
)
from trusted_synthesis.experiments.qa_reasoning_share_public_protocol.models import (
    PARENT,
    PARENT_MANIFEST,
    PARENT_ROOT,
)

from .protocol import record, require

SHARE_FAMILY = "source_explicit_part_whole_share"
SHARE_OPERATIONS = ("relation_sum", "share_ratio", "scale_percent")


class ShareExecutor:
    def __init__(self, operation: str):
        self.operation = operation

    def execute(
        self, inputs: tuple[OperationInput, ...], parameters: dict[str, Any]
    ) -> dict[str, Any]:
        with localcontext() as context:
            context.prec = 50
            context.rounding = ROUND_HALF_EVEN
            left = Decimal(inputs[0].value["value"])
            if self.operation == "relation_sum":
                value = left + Decimal(inputs[1].value["value"])
            elif self.operation == "share_ratio":
                value = left / Decimal(inputs[1].value["value"])
            else:
                value = left * 100
        return {"value": str(value)}


class ShareOracle:
    def __init__(self, operation: str):
        self.operation = operation

    def verify(
        self,
        inputs: tuple[OperationInput, ...],
        parameters: dict[str, Any],
        observed_output: dict[str, Any],
    ) -> OperationVerification:
        with localcontext() as context:
            context.prec = 50
            context.rounding = ROUND_HALF_EVEN
            numbers = [Decimal(item.value["value"]) for item in inputs if "value" in item.value]
            if self.operation == "relation_sum":
                expected = sum(numbers, Decimal(0))
            elif self.operation == "share_ratio":
                expected = numbers[0] / numbers[1]
            else:
                expected = numbers[0] * Decimal("100")
        output = {"value": str(expected)}
        passed = output == observed_output
        return OperationVerification(
            passed=passed,
            expected_output=output,
            invariant_failures=() if passed else ("share_numeric_output",),
            message="independent Decimal formula",
        )


def add_share_operations(registry: OperationRegistry) -> None:
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
                    "source_explicit_share_admission_required",
                    "accepted_claim_inputs_only",
                    "precision_50",
                ),
                output_model=ScalarOutput,
                tool_capability="calculator",
                input_role_contract={
                    "relation_sum": ("member", "member", "relation"),
                    "share_ratio": ("numerator", "denominator"),
                    "scale_percent": ("ratio",),
                }[operation],
                parameter_contract=("validated by bound Share source/semantic contract",),
                semantic_version="2.0.0",
                formula_id="share.public_protocol." + operation + ".v2",
            )
        )


def load_share_source(repo_root: Path) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    files = files_at(repo_root / PARENT)
    validate_manifest(files, PARENT_MANIFEST, PARENT_ROOT)
    source, legacy = (json.loads(files[name]) for name in ("source_binding.json", "contract.json"))
    require(source["id"] == legacy["source_binding_id"], "share.source_contract")
    binding = record(
        "source_binding",
        status="bound_original_share_source",
        source_bindable=True,
        parent_directory=PARENT,
        parent_manifest_id=PARENT_MANIFEST,
        parent_root=PARENT_ROOT,
        source_binding_id=source["id"],
        legacy_semantic_contract_id=legacy["id"],
        source_sha256=hashlib.sha256(files["source_binding.json"]).hexdigest(),
        source_bytes=len(files["source_binding.json"]),
        original_model_or_fixture_execution_reused=False,
    )
    return source, legacy, binding


def public_share_answer(context: dict[str, Any], claim: dict[str, Any]) -> dict[str, Any]:
    with localcontext() as numeric:
        numeric.prec = context["numeric"]["precision"]
        numeric.rounding = context["numeric"]["rounding"]
        value = Decimal(claim["proposition"]["output"]["value"]).quantize(
            Decimal(context["numeric"]["final_quantum"])
        )
    return {"value": str(value), "unit": "percent"}


class ShareTaskAdapter:
    def __init__(self, repo_root: Path, registry: OperationRegistry, resolution: dict[str, Any]):
        self.source, self.legacy, self.binding = load_share_source(repo_root)
        self.registry = registry
        self.evidence = {item["id"]: item for item in self.source["evidence"].values()}
        self.context = record(
            "context",
            task_id=self.legacy["task"]["id"],
            task_type=SHARE_FAMILY,
            adapter_id="source_explicit_share_obligations.v2",
            task=self.legacy["task"],
            evidence=self.source["evidence"],
            numeric=self.legacy["numeric"],
            source_binding=self.binding,
            catalog_resolution=resolution,
            registry_hash=record("registry", members=registry.manifest())["id"],
            final_projection="share_percent_quantized",
            uncertainties=[],
            obligations=["legitimate_total_support", "ratio", "percent"],
            accepted_claim_revision_supported=False,
            old_states_or_assignments_modified=False,
        )

    def offers(self, claims: list[dict[str, Any]]) -> list[dict[str, Any]]:
        by_goal = {claim["obligation_id"]: claim for claim in claims}
        if "percent" in by_goal:
            return []
        visible = self.source["evidence"]

        def evidence(role: str, name: str) -> dict[str, str]:
            return {"kind": "evidence", "ref_id": visible[name]["id"], "role": role}

        def claim(role: str, goal: str) -> dict[str, str]:
            return {"kind": "claim", "ref_id": by_goal[goal]["id"], "role": role}

        raw: list[tuple[str, str, list[dict[str, str]], dict[str, str], str, list[str]]] = []
        if "ratio" in by_goal:
            raw.append(
                (
                    "scale_percent",
                    "percent",
                    [claim("ratio", "ratio")],
                    {},
                    "scale",
                    ["registered_semantic_preconditions"],
                )
            )
        else:
            if "total" not in by_goal:
                raw.append(
                    (
                        "relation_sum",
                        "total",
                        [
                            evidence("member", "freight"),
                            evidence("member", "other"),
                            evidence("relation", "part_whole"),
                        ],
                        {"method": "sum"},
                        "reconstructed_total",
                        ["reconstructed_total"],
                    )
                )
            raw.append(
                (
                    "share_ratio",
                    "ratio",
                    [evidence("numerator", "freight"), evidence("denominator", "total")],
                    {},
                    "disclosed_total",
                    ["disclosed_total"],
                )
            )
            if "total" in by_goal:
                raw.append(
                    (
                        "share_ratio",
                        "ratio",
                        [evidence("numerator", "freight"), claim("denominator", "total")],
                        {},
                        "reconstructed_total",
                        ["reconstructed_total"],
                    )
                )
        result = []
        by_id = {item["id"]: item for item in claims}
        for operation, goal, inputs, parameters, choice, rules in raw:
            lineage = sorted(
                {
                    key
                    for ref in inputs
                    for key in (
                        [ref["ref_id"]]
                        if ref["kind"] == "evidence"
                        else by_id[ref["ref_id"]]["proposition"]["lineage"]
                    )
                }
            )
            result.append(
                record(
                    "offered_action",
                    obligation_id=goal,
                    subgoal="select_total_support"
                    if operation in {"relation_sum", "share_ratio"}
                    else "derive_quantity",
                    operation=operation,
                    operation_contract_id=operation_semantic_contract_hash(
                        self.registry.require(operation)
                    ),
                    inputs=inputs,
                    parameters=parameters,
                    basis={
                        "relation": "requires",
                        "evidence_refs": lineage,
                        "claim_refs": sorted(
                            ref["ref_id"] for ref in inputs if ref["kind"] == "claim"
                        ),
                    },
                    expected_effect={"establishes_obligation": goal, "output_schema": "scalar"},
                    selection_rules=rules,
                    alternative_group="legitimate_total_support"
                    if operation != "scale_percent"
                    else "percent",
                    semantic_choice=choice,
                    input_order_policy=self.legacy["operations"][operation]["input_order_policy"],
                )
            )
        return result

    def prepare(self, offer: dict[str, Any], claims: list[dict[str, Any]]) -> dict[str, Any]:
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
                require(item["status"] == "accepted", "share.accepted_input")
                content = {
                    **item["proposition"]["output"],
                    "producer_operation": item["proposition"]["operation"],
                }
            resolved.append({**ref, **content})
        admit_inputs(offer["operation"], resolved, offer["parameters"], self.legacy, self.source)
        return {
            "operation": offer["operation"],
            "inputs": tuple(OperationInput(ref_id=item["ref_id"], value=item) for item in resolved),
            "parameters": offer["parameters"],
            "lineage": offer["basis"]["evidence_refs"],
            "slot": offer["obligation_id"],
            "operation_contract_id": offer["operation_contract_id"],
        }

    def _proposition(self, prepared: dict[str, Any], value: str) -> dict[str, Any]:
        operation = prepared["operation"]
        legacy_op = self.legacy["operations"][operation]
        definitions = {
            "relation_sum": self.source["evidence"]["total"]["definition"],
            "share_ratio": "freight divided by legitimate operating revenue total",
            "scale_percent": "freight share in percent",
        }
        output = {
            **{key: self.source["evidence"]["freight"][key] for key in CONTEXT_FIELDS},
            "value": value,
            "metric": legacy_op["output_metric"],
            "unit": legacy_op["output_unit"],
            "definition": definitions[operation],
            "lineage": prepared["lineage"],
        }
        return {
            "output": output,
            "lineage": prepared["lineage"],
            "operation": operation,
            "operation_contract_id": prepared["operation_contract_id"],
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
        return [
            claim["id"]
            for claim in claims
            if claim["obligation_id"] == "percent"
            and claim["proposition"]["operation"] == "scale_percent"
        ]

    def verify_final(self, final: dict[str, Any], claims: list[dict[str, Any]]) -> dict[str, Any]:
        claim = next(item for item in claims if item["id"] == final["answer_claim_id"])
        expected = public_share_answer(self.context, claim)
        with localcontext() as numeric:
            numeric.prec = 50
            numeric.rounding = ROUND_HALF_EVEN
            disclosed = (
                Decimal(self.source["evidence"]["freight"]["value"])
                / Decimal(self.source["evidence"]["total"]["value"])
                * 100
            )
            oracle = str(disclosed.quantize(Decimal(self.legacy["numeric"]["final_quantum"])))
        answer_valid = final["result"] == expected and expected["value"] == oracle
        citation_valid = len(final["citations"]) == len(set(final["citations"])) and set(
            final["citations"]
        ) == set(claim["proposition"]["lineage"])
        return record(
            "qa_validation",
            task_id=self.context["task_id"],
            source_binding_id=self.binding["id"],
            source_valid=True,
            answer_valid=answer_valid,
            citation_valid=citation_valid,
            qa_valid=answer_valid and citation_valid,
            reference_program_used_for_callback=False,
        )
