"""Execute registered public Program obligations one callback Action at a time."""

from __future__ import annotations

import itertools
from decimal import ROUND_HALF_EVEN, localcontext
from typing import Any

from trusted_synthesis.core.evaluation.answer import CandidateAnswerNormalizer
from trusted_synthesis.core.evidence.schema import EvidenceItem
from trusted_synthesis.core.operations.program import (
    ProgramExecution,
    TaskProgramOracleVerifier,
    _select_value,
)
from trusted_synthesis.core.operations.registry import (
    OperationRegistry,
    operation_semantic_contract_hash,
)
from trusted_synthesis.core.operations.schema import OperationInput
from trusted_synthesis.core.task.program import InputRefKind
from trusted_synthesis.core.task.schema import TaskPublicSpec
from trusted_synthesis.core.trajectory.public_plan_executor import (
    _matches_public_constraints,
    _project_public_result,
)

from .protocol import record, require


def public_program_answer(context: dict[str, Any], claims: list[dict[str, Any]]) -> dict[str, Any]:
    """Public answer-schema projection only; no Oracle or numerical executor."""
    public = TaskPublicSpec.model_validate(context["public_task"])
    assert public.program_skeleton is not None
    evidence = {
        item["evidence_id"]: EvidenceItem.model_validate(item) for item in context["evidence"]
    }
    outputs = {claim["obligation_id"]: claim["proposition"]["output"] for claim in claims}
    roles = {}
    for node in public.program_skeleton.nodes:
        for ref in node.inputs:
            if ref.kind == InputRefKind.EVIDENCE:
                matching = tuple(
                    key
                    for key, item in evidence.items()
                    if _matches_public_constraints(item, ref.semantic_constraints)
                )
                require(len(matching) == 1, "answer.unique_public_evidence_role")
                roles[ref.role_id] = matching
    for alias, public_roles in context["projection_role_aliases"].items():
        roles[alias] = tuple(key for role in public_roles for key in roles[role])
    execution = ProgramExecution(
        program_id="public_projection_not_execution",
        node_outputs=outputs,
        final_output=outputs[public.program_skeleton.output_node_id],
    )
    with localcontext() as numeric:
        numeric.prec = context["numeric"]["precision"]
        numeric.rounding = context["numeric"]["rounding"]
        result = _project_public_result(public.answer_schema, execution, evidence, roles)
        return CandidateAnswerNormalizer().normalize_result(public, result)


class ProgramTaskAdapter:
    def __init__(self, case: Any, registry: OperationRegistry):
        self.case, self.registry = case, registry
        self.public = case.task.public
        self.skeleton = self.public.program_skeleton
        require(self.skeleton is not None, "adapter.plan_given_required")
        self.evidence = {item.evidence_id: item for item in case.bundle.evidence}
        assert self.skeleton is not None
        visible_roles = {}
        for node in self.skeleton.nodes:
            for ref in node.inputs:
                if ref.kind == InputRefKind.EVIDENCE:
                    visible_roles[ref.role_id] = tuple(
                        key
                        for key, item in self.evidence.items()
                        if _matches_public_constraints(item, ref.semantic_constraints)
                    )
        aliases = {}
        for role, ids in case.instantiation.binding.role_bindings.items():
            mapped = []
            for key in ids:
                matches = [name for name, values in visible_roles.items() if values == (key,)]
                require(len(matches) == 1, "adapter.public_role_alias")
                mapped.append(matches[0])
            aliases[role] = mapped
        self.context = record(
            "context",
            task_id=case.task.task_id,
            task_type=case.task_type,
            adapter_id="registered_public_program_obligations.v2",
            public_task=self.public.model_dump(mode="json"),
            evidence=[item.model_dump(mode="json") for item in case.bundle.evidence],
            source_binding=case.source_binding,
            catalog_resolution=case.resolution,
            registry_hash=record("registry", members=registry.manifest())["id"],
            planning_authority="given public skeleton; not inferred from hidden Oracle",
            final_projection="public_program_answer",
            numeric={
                "arithmetic": "decimal",
                "precision": 28,
                "rounding": ROUND_HALF_EVEN,
                "applies_to": [
                    "registered_operation_execution",
                    "independent_operation_verification",
                    "public_answer_projection",
                    "final_qa",
                ],
                "share_numeric_contract_reused": False,
            },
            projection_role_aliases=aliases,
            uncertainties=[],
            accepted_claim_revision_supported=False,
        )
        assert self.skeleton is not None
        for node in self.skeleton.nodes:
            definition = registry.require(node.operator_id)
            require(
                node.output_schema == definition.output_schema
                and node.tool_capability == definition.tool_capability,
                "adapter.public_registry_contract",
            )
            require(
                tuple(
                    dict.fromkeys(
                        ref.role_id for ref in node.inputs if ref.kind == InputRefKind.OPERATION
                    )
                )
                == node.dependencies,
                "adapter.public_dependencies",
            )

    def offers(self, claims: list[dict[str, Any]]) -> list[dict[str, Any]]:
        by_goal = {claim["obligation_id"]: claim for claim in claims}
        require(len(by_goal) == len(claims), "adapter.unique_accepted_obligation")
        result = []
        assert self.skeleton is not None
        for node in self.skeleton.nodes:
            if node.public_node_id in by_goal or not set(node.dependencies) <= set(by_goal):
                continue
            columns = []
            for ref in node.inputs:
                if ref.kind == InputRefKind.EVIDENCE:
                    columns.append(
                        [
                            {
                                "kind": "evidence",
                                "ref_id": key,
                                "role": ref.role_id,
                                "selector": ref.selector,
                            }
                            for key, item in self.evidence.items()
                            if _matches_public_constraints(item, ref.semantic_constraints)
                        ]
                    )
                else:
                    columns.append(
                        [
                            {
                                "kind": "claim",
                                "ref_id": by_goal[ref.role_id]["id"],
                                "role": ref.role_id,
                                "selector": ref.selector,
                            }
                        ]
                    )
            require(
                len(list(itertools.islice(itertools.product(*columns), 33))) <= 32,
                "adapter.binding_search_bound",
            )
            definition = self.registry.require(node.operator_id)
            for selected in itertools.product(*columns):
                claim_ids = [item["ref_id"] for item in selected if item["kind"] == "claim"]
                evidence_ids = {item["ref_id"] for item in selected if item["kind"] == "evidence"}
                evidence_ids.update(
                    ref
                    for claim in claims
                    if claim["id"] in claim_ids
                    for ref in claim["proposition"]["lineage"]
                )
                subgoal = (
                    "resolve_evidence"
                    if definition.program_role == "transparent_projection"
                    else "compare_quantities"
                    if "compar" in node.operator_id
                    else "derive_quantity"
                )
                option = record(
                    "offered_action",
                    obligation_id=node.public_node_id,
                    subgoal=subgoal,
                    operation=node.operator_id,
                    operation_contract_id=operation_semantic_contract_hash(definition),
                    inputs=list(selected),
                    parameters=node.parameters,
                    basis={
                        "relation": "requires",
                        "evidence_refs": sorted(evidence_ids),
                        "claim_refs": sorted(claim_ids),
                    },
                    expected_effect={
                        "establishes_obligation": node.public_node_id,
                        "output_schema": node.output_schema,
                    },
                    selection_rules=["dependency_ready", "registered_semantic_preconditions"],
                    alternative_group=node.public_node_id,
                    semantic_choice=[
                        item["ref_id"] for item in selected if item["kind"] == "evidence"
                    ],
                    input_order_policy=definition.input_order_policy,
                )
                # Pure admission removes incompatible evidence combinations before execution.
                try:
                    self.prepare(option, claims)
                except ValueError:
                    continue
                result.append(option)
        return result

    def prepare(self, offer: dict[str, Any], claims: list[dict[str, Any]]) -> dict[str, Any]:
        by_id = {claim["id"]: claim for claim in claims}
        definition = self.registry.require(offer["operation"])
        inputs = []
        for ref in offer["inputs"]:
            if ref["kind"] == "evidence":
                value, operation_ref = self.evidence[ref["ref_id"]].payload, ref["ref_id"]
            else:
                claim = by_id[ref["ref_id"]]
                require(claim["status"] == "accepted", "adapter.accepted_input_only")
                value, operation_ref = claim["proposition"]["output"], claim["obligation_id"]
            if ref["selector"]:
                value = _select_value(value, ref["selector"], ref["ref_id"])
            inputs.append(OperationInput(ref_id=operation_ref, value=value))
        lineage = offer["basis"]["evidence_refs"]
        self.registry.validate_inputs(definition, tuple(inputs))
        # Keep operand traversal order for registered numerator/denominator pairs.
        ordered: list[str] = []
        for ref in offer["inputs"]:
            refs = (
                [ref["ref_id"]]
                if ref["kind"] == "evidence"
                else by_id[ref["ref_id"]]["proposition"]["lineage"]
            )
            ordered.extend(key for key in refs if key not in ordered)
        self.registry.validate_compatibility(
            definition, tuple(self.evidence[key] for key in ordered), offer["parameters"]
        )
        return {
            "operation": offer["operation"],
            "inputs": tuple(inputs),
            "parameters": offer["parameters"],
            "lineage": lineage,
            "slot": offer["obligation_id"],
            "operation_contract_id": offer["operation_contract_id"],
        }

    def execute(self, prepared: dict[str, Any]) -> dict[str, Any]:
        definition = self.registry.require(prepared["operation"])
        with localcontext() as context:
            context.prec = 28
            context.rounding = ROUND_HALF_EVEN
            output = definition.executor.execute(prepared["inputs"], prepared["parameters"])
        self.registry.validate_output(definition, output)
        return {
            "output": output,
            "lineage": prepared["lineage"],
            "operation": prepared["operation"],
            "operation_contract_id": prepared["operation_contract_id"],
        }

    def verify_execution(self, prepared: dict[str, Any], proposition: dict[str, Any]) -> bool:
        definition = self.registry.require(prepared["operation"])
        with localcontext() as context:
            context.prec = 28
            context.rounding = ROUND_HALF_EVEN
            result = definition.oracle_verifier.verify(
                prepared["inputs"], prepared["parameters"], proposition["output"]
            )
        return (
            result.passed
            and proposition["lineage"] == prepared["lineage"]
            and proposition["operation"] == prepared["operation"]
            and proposition["operation_contract_id"] == prepared["operation_contract_id"]
        )

    def final_claims(self, claims: list[dict[str, Any]]) -> list[str]:
        assert self.skeleton is not None
        return [
            claim["id"]
            for claim in claims
            if claim["obligation_id"] == self.skeleton.output_node_id
        ]

    def verify_final(self, final: dict[str, Any], claims: list[dict[str, Any]]) -> dict[str, Any]:
        with localcontext() as numeric:
            numeric.prec = 28
            numeric.rounding = ROUND_HALF_EVEN
            actual = public_program_answer(self.context, claims)
            normalizer = CandidateAnswerNormalizer()
            answer_valid = normalizer.equivalent(final["result"], actual)
            schema_valid, _ = normalizer.validate_schema(
                self.public, {"result": final["result"], "citations": final["citations"]}
            )
            answer_claim = next(item for item in claims if item["id"] == final["answer_claim_id"])
            citation_valid = len(final["citations"]) == len(set(final["citations"])) and set(
                final["citations"]
            ) == set(answer_claim["proposition"]["lineage"])
            # The Oracle is a post-execution QA authority, never a source for callback Actions.
            oracle = TaskProgramOracleVerifier(self.registry).derive_expected(
                self.case.task.oracle.task_program, self.evidence
            )
            if self.public.answer_schema.get("result_projection"):
                roles = {}
                assert self.skeleton is not None
                for node in self.skeleton.nodes:
                    for ref in node.inputs:
                        if ref.kind == InputRefKind.EVIDENCE:
                            roles[ref.role_id] = tuple(
                                key
                                for key, item in self.evidence.items()
                                if _matches_public_constraints(item, ref.semantic_constraints)
                            )
                for alias, public_roles in self.context["projection_role_aliases"].items():
                    roles[alias] = tuple(key for role in public_roles for key in roles[role])
                expected = normalizer.normalize_result(
                    self.public,
                    _project_public_result(self.public.answer_schema, oracle, self.evidence, roles),
                )
            else:
                expected = normalizer.normalize_oracle(
                    self.case.task,
                    oracle.final_output,
                    self.case.bundle.evidence,
                    node_outputs=oracle.node_outputs,
                )
            source_valid = self.case.source_binding["source_bindable"]
            qa_valid = (
                source_valid
                and answer_valid
                and schema_valid
                and citation_valid
                and normalizer.equivalent(actual, expected)
            )
            return record(
                "qa_validation",
                task_id=self.public.task_id,
                source_binding_id=self.case.source_binding.get("id"),
                source_valid=source_valid,
                answer_valid=answer_valid,
                schema_valid=schema_valid,
                citation_valid=citation_valid,
                qa_valid=qa_valid,
                reference_program_used_for_callback=False,
            )
