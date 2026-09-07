"""Finite semantic composition independent of reference-node membership.

H0/H1 keep their original adapters. H2 uses original source objects and numeric
executors/verifiers, but never calls offers() or traverses a reference graph to
admit a proposal. Reference execution is restricted to post-execution Final QA.
"""

from __future__ import annotations

import copy
from decimal import ROUND_HALF_EVEN, Decimal, localcontext
from typing import Any

from trusted_synthesis.core.evaluation.answer import CandidateAnswerNormalizer
from trusted_synthesis.core.operations.program import TaskProgramOracleVerifier
from trusted_synthesis.core.operations.registry import operation_semantic_contract_hash
from trusted_synthesis.core.operations.schema import OperationInput
from trusted_synthesis.domains.finance.qa_vnext.protocol import record, require

TOOLS = {
    "S": {
        "relation_sum": {
            "roles": ["member", "member", "relation"],
            "parameters": {"method": "sum"},
            "rule": "Two nonoverlapping exhaustive members of the supplied part-whole "
            "relation, in either order, with identical subject/period/scope/currency/unit. "
            "Produces their total. Relation evidence must be explicitly selected.",
        },
        "share_ratio": {
            "roles": ["numerator", "denominator"],
            "parameters": {},
            "rule": "A source member divided by its legitimate total, disclosed or "
            "previously accepted relation_sum; matching contextual units, nonzero denominator.",
        },
        "scale_percent": {
            "roles": ["ratio"],
            "parameters": {},
            "rule": "One previously accepted share_ratio, multiply by 100; output percent.",
        },
    },
    "B": {
        "lookup": {
            "roles": ["selected_evidence"],
            "parameters": {},
            "rule": "One raw numeric evidence item; copy its payload with its source identity.",
        },
        "growth": {
            "roles": ["earlier", "later"],
            "parameters": {},
            "rule": "Two raw monetary evidence items or accepted lookup results; same "
            "metric/definition/subject/scope/unit/currency/source and strictly increasing "
            "periods. (later-earlier)/abs(earlier)*100, nonzero base; output percent.",
        },
        "signed_percentage_point_gap": {
            "roles": ["reference_percent", "observed_percent"],
            "parameters": {},
            "rule": "Two accepted percent results with matching subject/scope/period interval; "
            "observed minus reference, output percentage_points. Either metric order is legal.",
        },
        "absolute_percentage_point_gap": {
            "roles": ["signed_gap"],
            "parameters": {},
            "rule": "One accepted percentage_points result; absolute value, same unit.",
        },
    },
}


def evidence_ids(base, group):
    if group == "S":
        return [item["id"] for item in base.context["evidence"].values()]
    return [item["evidence_id"] for item in base.context["evidence"]]


class OpenAdapter:
    """Bounded source/type checked composition, not an arbitrary-code calculator."""

    def __init__(self, base, group: str):
        self.base, self.group, self.registry = base, group, base.registry
        self.context = record(
            "context",
            adapter_id="finite_semantic_composition.v1",
            task_id=base.context["task_id"],
            task_type=base.context["task_type"],
            question=(
                base.context["task"]["question"]
                if group == "S"
                else base.context["public_task"]["instruction"]
            ),
            evidence=copy.deepcopy(base.context["evidence"]),
            numeric=copy.deepcopy(base.context["numeric"]),
            source_binding_id=base.context["source_binding"]["id"],
            tools=TOOLS[group],
            planning_authority="model proposes subgoal, operation and ordered inputs",
            finite_composition_only=True,
            accepted_claim_revision_supported=False,
        )

    def offers(self, claims):
        return []

    def proposal(self, submitted: dict[str, Any], claims: list[dict[str, Any]]):
        operation = submitted["operation"]
        require(operation in TOOLS[self.group], "semantic.unsupported_operation")
        tool = TOOLS[self.group][operation]
        require(len(submitted["inputs"]) == len(tool["roles"]), "semantic.arity")
        require(submitted["parameters"] == tool["parameters"], "semantic.parameters")
        accepted = {claim["id"]: claim for claim in claims}
        available_evidence = set(evidence_ids(self.base, self.group))
        refs, lineage = [], set()
        for key, role in zip(submitted["inputs"], tool["roles"], strict=True):
            if key in available_evidence:
                kind = "evidence"
                lineage.add(key)
            else:
                require(
                    key in accepted and accepted[key]["status"] == "accepted",
                    "semantic.current_session_accepted_input_only",
                )
                kind = "claim"
                lineage.update(accepted[key]["proposition"]["lineage"])
            refs.append({"kind": kind, "ref_id": key, "role": role})
        return record(
            "open_action",
            operation=operation,
            operation_contract_id=operation_semantic_contract_hash(
                self.registry.require(operation)
            ),
            inputs=refs,
            parameters=submitted["parameters"],
            obligation_id=submitted["subgoal"],
            subgoal=submitted["subgoal"],
            reason=submitted["reason"],
            basis={
                "relation": "requires",
                "evidence_refs": sorted(lineage),
                "claim_refs": sorted({r["ref_id"] for r in refs if r["kind"] == "claim"}),
            },
            decision_origin="model_before_execution",
            reference_node_membership_checked=False,
        )

    def prepare(self, offer, claims):
        require(offer["operation"] in TOOLS[self.group], "semantic.unsupported_operation")
        # Reconstruct the offered semantics independently, not just its numeric inputs.
        submitted = {
            "operation": offer["operation"],
            "inputs": [r["ref_id"] for r in offer["inputs"]],
            "parameters": offer["parameters"],
            "subgoal": offer["subgoal"],
            "reason": offer["reason"],
        }
        require(self.proposal(submitted, claims) == offer, "semantic.proposal_binding")
        if self.group == "S":
            return self.base.prepare(offer, claims)
        return self._prepare_b(offer, claims)

    def _prepare_b(self, offer, claims):
        accepted = {claim["id"]: claim for claim in claims}
        values, semantics = [], []
        for ref in offer["inputs"]:
            key = ref["ref_id"]
            if ref["kind"] == "evidence":
                item = self.base.evidence[key]
                value = item.payload.model_dump(mode="json")
                semantics.append(
                    {
                        "kind": "money",
                        "metric": item.predicate,
                        "definition": item.definition.definition_id,
                        "subject": item.subject.subject_id,
                        "scope": item.scope.model_dump(mode="json"),
                        "period": item.temporal_context.model_dump(mode="json"),
                        "sort_key": item.domain_context["economic_period_sort_key"],
                        "source": item.source.source_id,
                        "unit": value["unit"],
                        "currency": value["currency"],
                    }
                )
            else:
                claim = accepted[key]
                require(claim["status"] == "accepted", "semantic.accepted_only")
                proposition = claim["proposition"]
                semantics.append(proposition["semantic_type"])
                value = proposition["output"]
                if proposition["operation"] == "lookup":
                    value = value["payload"]
            values.append(value)
        op = offer["operation"]
        definition = self.registry.require(op)
        require(all(isinstance(s, dict) for s in semantics), "semantic.type_required")
        if op == "lookup":
            require(offer["inputs"][0]["kind"] == "evidence", "semantic.lookup_evidence")
            output_type = semantics[0]
            numeric_values = values
        elif op == "growth":
            left, right = semantics
            require(left["kind"] == right["kind"] == "money", "semantic.money_units")
            require(
                all(
                    left[k] == right[k]
                    for k in (
                        "metric",
                        "definition",
                        "subject",
                        "scope",
                        "source",
                        "unit",
                        "currency",
                    )
                ),
                "semantic.growth_context",
            )
            require(left["sort_key"] < right["sort_key"], "semantic.period_order")
            require(Decimal(values[0]["value"]) != 0, "semantic.nonzero_base")
            output_type = {
                "kind": "percent",
                "unit": "percent",
                "metric": left["metric"],
                "subject": left["subject"],
                "scope": left["scope"],
                "interval": [left["period"], right["period"]],
            }
            numeric_values = [v["value"] for v in values]
        elif op == "signed_percentage_point_gap":
            left, right = semantics
            require(left["kind"] == right["kind"] == "percent", "semantic.percent_units")
            require(
                all(left[k] == right[k] for k in ("subject", "scope", "interval")),
                "semantic.gap_context",
            )
            output_type = {
                "kind": "percentage_points",
                "unit": "percentage_points",
                "subject": left["subject"],
                "scope": left["scope"],
                "interval": left["interval"],
                "metrics": [left["metric"], right["metric"]],
            }
            numeric_values = [v["value"] for v in values]
        else:
            require(semantics[0]["kind"] == "percentage_points", "semantic.percentage_point_units")
            output_type = semantics[0]
            numeric_values = [values[0]["value"]]
        inputs = tuple(
            OperationInput(ref_id=ref["ref_id"], value=value)
            for ref, value in zip(offer["inputs"], numeric_values, strict=True)
        )
        self.registry.validate_inputs(definition, inputs)
        return {
            "operation": op,
            "inputs": inputs,
            "parameters": offer["parameters"],
            "lineage": offer["basis"]["evidence_refs"],
            "slot": offer["obligation_id"],
            "operation_contract_id": offer["operation_contract_id"],
            "semantic_type": copy.deepcopy(output_type),
        }

    def execute(self, prepared):
        if self.group == "S":
            return self.base.execute(prepared)
        proposition = self.base.execute(prepared)
        proposition["semantic_type"] = copy.deepcopy(prepared["semantic_type"])
        return proposition

    def verify_execution(self, prepared, proposition):
        if self.group == "S":
            return self.base.verify_execution(prepared, proposition)
        return (
            self.base.verify_execution(prepared, proposition)
            and proposition.get("semantic_type") == prepared["semantic_type"]
        )

    def final_claims(self, claims):
        operation = "scale_percent" if self.group == "S" else "absolute_percentage_point_gap"
        return [
            c["id"]
            for c in claims
            if c["status"] == "accepted" and c["proposition"]["operation"] == operation
        ]

    def verify_final(self, final, claims):
        require(final["answer_claim_id"] in self.final_claims(claims), "semantic.final_accepted")
        if self.group == "S":
            return self.base.verify_final(final, claims)
        claim = next(c for c in claims if c["id"] == final["answer_claim_id"])
        normalizer = CandidateAnswerNormalizer()
        with localcontext() as numeric:
            numeric.prec, numeric.rounding = 28, ROUND_HALF_EVEN
            expected = TaskProgramOracleVerifier(self.registry).derive_expected(
                self.base.case.task.oracle.task_program, self.base.evidence
            )
            oracle = normalizer.normalize_oracle(
                self.base.case.task,
                expected.final_output,
                self.base.case.bundle.evidence,
                node_outputs=expected.node_outputs,
            )
            actual = normalizer.normalize_result(self.base.public, claim["proposition"]["output"])
            schema, _ = normalizer.validate_schema(
                self.base.public, {"result": final["result"], "citations": final["citations"]}
            )
            answer = normalizer.equivalent(final["result"], actual) and normalizer.equivalent(
                actual, oracle
            )
        citations = len(final["citations"]) == len(set(final["citations"])) and set(
            final["citations"]
        ) == set(claim["proposition"]["lineage"])
        source = self.base.case.source_binding["source_bindable"]
        return record(
            "qa_validation",
            source_valid=source,
            answer_valid=answer,
            schema_valid=schema,
            citation_valid=citations,
            qa_valid=source and answer and schema and citations,
            reference_program_used_for_callback=False,
            reference_program_used_only_for_final_oracle=True,
        )
