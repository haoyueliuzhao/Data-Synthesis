from __future__ import annotations

import inspect
from copy import deepcopy
from decimal import Decimal, InvalidOperation
from typing import Any, Protocol

from trusted_synthesis.core.evaluation.contracts.schema import (
    ClauseMutationSpec,
    QualityClause,
)
from trusted_synthesis.core.evaluation.counterfactual.context import CounterfactualContext
from trusted_synthesis.core.evaluation.counterfactual.registry import (
    CounterfactualOperatorRegistry,
)
from trusted_synthesis.core.evaluation.counterfactual.schema import (
    CounterfactualMutationDraft,
    CounterfactualOpportunity,
)
from trusted_synthesis.core.evidence.schema import EvidenceItem
from trusted_synthesis.core.trajectory.schema import (
    ActionType,
    StepStatus,
    Trajectory,
)
from trusted_synthesis.hashing import canonical_hash

COUNTERFACTUAL_OPERATOR_VERSION = "1.0.0"


class _UniversalOperator:
    operator_version = COUNTERFACTUAL_OPERATOR_VERSION
    provider_id = "universal_counterfactual_operators.v1"

    def manifest_parameters(self) -> dict[str, object]:
        return {}


class RemoveSelectedEvidenceOperator(_UniversalOperator):
    operator_id = "remove_selected_evidence"

    def plan(
        self,
        context: CounterfactualContext,
        clause: QualityClause,
        spec: ClauseMutationSpec,
    ) -> tuple[CounterfactualMutationDraft, ...]:
        target = clause.target.target_ref
        indexes = tuple(
            index
            for index, step in enumerate(context.source_trajectory.steps)
            if step.action == ActionType.SELECT_EVIDENCE and target in step.evidence_ids
        )
        if not indexes:
            return ()
        return (
            CounterfactualMutationDraft(
                parameters={"target_evidence_id": target, "step_indexes": indexes},
                allowed_json_path_prefixes=tuple(
                    f"steps[{index}].evidence_ids" for index in indexes
                ),
            ),
        )

    def apply(
        self,
        context: CounterfactualContext,
        opportunity: CounterfactualOpportunity,
    ) -> Trajectory:
        target = str(opportunity.parameters["target_evidence_id"])
        steps = tuple(
            step.model_copy(
                update={
                    "evidence_ids": tuple(
                        item for item in step.evidence_ids if item != target
                    )
                }
            )
            if step.action == ActionType.SELECT_EVIDENCE and target in step.evidence_ids
            else step
            for step in context.source_trajectory.steps
        )
        return context.source_trajectory.model_copy(update={"steps": steps})


class SetStepFailedOperator(_UniversalOperator):
    operator_id = "set_step_failed"

    def plan(
        self,
        context: CounterfactualContext,
        clause: QualityClause,
        spec: ClauseMutationSpec,
    ) -> tuple[CounterfactualMutationDraft, ...]:
        candidates = tuple(
            (index, step)
            for index, step in enumerate(context.source_trajectory.steps)
            if step.status == StepStatus.SUCCEEDED and step.action != ActionType.ANSWER
        )
        if not candidates:
            return ()
        index, step = candidates[-1]
        return (
            CounterfactualMutationDraft(
                parameters={"step_index": index, "action": step.action.value},
                allowed_json_path_prefixes=(f"steps[{index}].status",),
            ),
        )

    def apply(
        self,
        context: CounterfactualContext,
        opportunity: CounterfactualOpportunity,
    ) -> Trajectory:
        target_index = int(opportunity.parameters["step_index"])
        steps = tuple(
            step.model_copy(update={"status": StepStatus.FAILED})
            if index == target_index
            else step
            for index, step in enumerate(context.source_trajectory.steps)
        )
        return context.source_trajectory.model_copy(update={"steps": steps})


class InjectOracleReferenceOperator(_UniversalOperator):
    operator_id = "inject_oracle_reference"

    def plan(
        self,
        context: CounterfactualContext,
        clause: QualityClause,
        spec: ClauseMutationSpec,
    ) -> tuple[CounterfactualMutationDraft, ...]:
        plan_index = next(
            (
                index
                for index, step in enumerate(context.source_trajectory.steps)
                if step.action == ActionType.PLAN
            ),
            None,
        )
        if plan_index is None:
            return ()
        return (
            CounterfactualMutationDraft(
                parameters={
                    "step_index": plan_index,
                    "gold_evidence_ids": context.task.oracle.gold_evidence_ids,
                },
                allowed_json_path_prefixes=(
                    f"steps[{plan_index}].tool_input.gold_evidence_ids",
                ),
            ),
        )

    def apply(
        self,
        context: CounterfactualContext,
        opportunity: CounterfactualOpportunity,
    ) -> Trajectory:
        target_index = int(opportunity.parameters["step_index"])
        steps = []
        for index, step in enumerate(context.source_trajectory.steps):
            if index != target_index:
                steps.append(step)
                continue
            tool_input = deepcopy(step.tool_input)
            tool_input["gold_evidence_ids"] = list(
                opportunity.parameters["gold_evidence_ids"]
            )
            steps.append(step.model_copy(update={"tool_input": tool_input}))
        return context.source_trajectory.model_copy(update={"steps": tuple(steps)})


class ReplaceToolOperator(_UniversalOperator):
    operator_id = "replace_tool"

    def plan(
        self,
        context: CounterfactualContext,
        clause: QualityClause,
        spec: ClauseMutationSpec,
    ) -> tuple[CounterfactualMutationDraft, ...]:
        target = next(
            (
                (index, step)
                for index, step in enumerate(context.source_trajectory.steps)
                if step.tool_name is not None
            ),
            None,
        )
        if target is None:
            return ()
        index, step = target
        return (
            CounterfactualMutationDraft(
                parameters={
                    "step_index": index,
                    "original_tool": step.tool_name,
                    "replacement_tool": "counterfactual.disallowed_tool",
                },
                allowed_json_path_prefixes=(f"steps[{index}].tool_name",),
            ),
        )

    def apply(
        self,
        context: CounterfactualContext,
        opportunity: CounterfactualOpportunity,
    ) -> Trajectory:
        target_index = int(opportunity.parameters["step_index"])
        replacement = str(opportunity.parameters["replacement_tool"])
        steps = tuple(
            step.model_copy(update={"tool_name": replacement})
            if index == target_index
            else step
            for index, step in enumerate(context.source_trajectory.steps)
        )
        return context.source_trajectory.model_copy(update={"steps": steps})


class PerturbProgramOutputOperator(_UniversalOperator):
    operator_id = "perturb_program_output"

    def plan(
        self,
        context: CounterfactualContext,
        clause: QualityClause,
        spec: ClauseMutationSpec,
    ) -> tuple[CounterfactualMutationDraft, ...]:
        target_node = clause.target.target_ref
        target = next(
            (
                (index, step)
                for index, step in enumerate(context.source_trajectory.steps)
                if step.program_node_id == target_node
                and isinstance(step.observation.get("result"), dict)
            ),
            None,
        )
        if target is None:
            return ()
        index, _ = target
        return (
            CounterfactualMutationDraft(
                parameters={"step_index": index, "program_node_id": target_node},
                allowed_json_path_prefixes=(f"steps[{index}].observation.result",),
            ),
        )

    def apply(
        self,
        context: CounterfactualContext,
        opportunity: CounterfactualOpportunity,
    ) -> Trajectory:
        target_index = int(opportunity.parameters["step_index"])
        steps = []
        for index, step in enumerate(context.source_trajectory.steps):
            if index != target_index:
                steps.append(step)
                continue
            observation = deepcopy(step.observation)
            observation["result"] = _perturb_value(observation["result"])
            steps.append(step.model_copy(update={"observation": observation}))
        return context.source_trajectory.model_copy(update={"steps": tuple(steps)})


class ReplaceProgramOperatorOperator(_UniversalOperator):
    operator_id = "replace_program_operator"

    def plan(
        self,
        context: CounterfactualContext,
        clause: QualityClause,
        spec: ClauseMutationSpec,
    ) -> tuple[CounterfactualMutationDraft, ...]:
        target_node = clause.target.target_ref
        target = next(
            (
                (index, step)
                for index, step in enumerate(context.source_trajectory.steps)
                if step.program_node_id == target_node and step.operator_id is not None
            ),
            None,
        )
        if target is None:
            return ()
        index, step = target
        return (
            CounterfactualMutationDraft(
                parameters={
                    "step_index": index,
                    "original_operator_id": step.operator_id,
                    "replacement_operator_id": "counterfactual.invalid_operator",
                },
                allowed_json_path_prefixes=(f"steps[{index}].operator_id",),
            ),
        )

    def apply(
        self,
        context: CounterfactualContext,
        opportunity: CounterfactualOpportunity,
    ) -> Trajectory:
        target_index = int(opportunity.parameters["step_index"])
        replacement = str(opportunity.parameters["replacement_operator_id"])
        steps = tuple(
            step.model_copy(update={"operator_id": replacement})
            if index == target_index
            else step
            for index, step in enumerate(context.source_trajectory.steps)
        )
        return context.source_trajectory.model_copy(update={"steps": steps})


class BreakProgramDependencyOperator(_UniversalOperator):
    operator_id = "break_program_dependency"

    def plan(
        self,
        context: CounterfactualContext,
        clause: QualityClause,
        spec: ClauseMutationSpec,
    ) -> tuple[CounterfactualMutationDraft, ...]:
        target_node = clause.target.target_ref
        target = next(
            (
                (index, step)
                for index, step in enumerate(context.source_trajectory.steps)
                if step.program_node_id == target_node and step.input_refs
            ),
            None,
        )
        if target is None:
            return ()
        index, step = target
        return (
            CounterfactualMutationDraft(
                parameters={
                    "step_index": index,
                    "original_input_ref": step.input_refs[0],
                    "replacement_input_ref": "operation:counterfactual_missing_dependency",
                },
                allowed_json_path_prefixes=(f"steps[{index}].input_refs[0]",),
            ),
        )

    def apply(
        self,
        context: CounterfactualContext,
        opportunity: CounterfactualOpportunity,
    ) -> Trajectory:
        target_index = int(opportunity.parameters["step_index"])
        replacement = str(opportunity.parameters["replacement_input_ref"])
        steps = []
        for index, step in enumerate(context.source_trajectory.steps):
            if index != target_index:
                steps.append(step)
                continue
            input_refs = (replacement, *step.input_refs[1:])
            steps.append(step.model_copy(update={"input_refs": input_refs}))
        return context.source_trajectory.model_copy(update={"steps": tuple(steps)})


class PerturbAnswerResultOperator(_UniversalOperator):
    operator_id = "perturb_answer_result"

    def plan(
        self,
        context: CounterfactualContext,
        clause: QualityClause,
        spec: ClauseMutationSpec,
    ) -> tuple[CounterfactualMutationDraft, ...]:
        if not isinstance(context.source_trajectory.final_answer.get("result"), dict):
            return ()
        return (
            CounterfactualMutationDraft(
                allowed_json_path_prefixes=("final_answer.result",),
            ),
        )

    def apply(
        self,
        context: CounterfactualContext,
        opportunity: CounterfactualOpportunity,
    ) -> Trajectory:
        answer = deepcopy(context.source_trajectory.final_answer)
        answer["result"] = _perturb_value(answer["result"])
        return context.source_trajectory.model_copy(update={"final_answer": answer})


class ReplaceCitationSourceOperator(_UniversalOperator):
    operator_id = "replace_citation_source"

    def plan(
        self,
        context: CounterfactualContext,
        clause: QualityClause,
        spec: ClauseMutationSpec,
    ) -> tuple[CounterfactualMutationDraft, ...]:
        citations = context.source_trajectory.final_answer.get("citations")
        if not isinstance(citations, list) or not citations:
            return ()
        return (
            CounterfactualMutationDraft(
                parameters={"citation_index": 0},
                allowed_json_path_prefixes=("final_answer.citations[0].source_id",),
            ),
        )

    def apply(
        self,
        context: CounterfactualContext,
        opportunity: CounterfactualOpportunity,
    ) -> Trajectory:
        answer = deepcopy(context.source_trajectory.final_answer)
        answer["citations"][0]["source_id"] = "counterfactual_unrelated_source"
        return context.source_trajectory.model_copy(update={"final_answer": answer})


class AppendUnsupportedClaimOperator(_UniversalOperator):
    operator_id = "append_unsupported_claim"

    def plan(
        self,
        context: CounterfactualContext,
        clause: QualityClause,
        spec: ClauseMutationSpec,
    ) -> tuple[CounterfactualMutationDraft, ...]:
        return (
            CounterfactualMutationDraft(
                allowed_json_path_prefixes=("final_answer.claims",),
            ),
        )

    def apply(
        self,
        context: CounterfactualContext,
        opportunity: CounterfactualOpportunity,
    ) -> Trajectory:
        answer = deepcopy(context.source_trajectory.final_answer)
        claims = list(answer.get("claims") or ())
        claims.append(
            {
                "claim_id": "counterfactual_unsupported_claim",
                "claim_type": "causal_claim",
                "evidence_ids": list(context.task.oracle.gold_evidence_ids),
            }
        )
        answer["claims"] = claims
        return context.source_trajectory.model_copy(update={"final_answer": answer})


class EvidenceReplacementSelector(Protocol):
    selector_id: str
    selector_version: str

    def __call__(self, target: EvidenceItem, candidate: EvidenceItem) -> bool: ...


class ReplaceSelectedEvidenceOperator:
    """Domain-configured evidence swap; Core only applies a typed selector callback."""

    operator_version = COUNTERFACTUAL_OPERATOR_VERSION

    def __init__(
        self,
        *,
        operator_id: str,
        provider_id: str,
        selector: EvidenceReplacementSelector,
    ) -> None:
        self.operator_id = operator_id
        self.provider_id = provider_id
        self._selector = selector

    def manifest_parameters(self) -> dict[str, object]:
        return {
            "selector_id": self._selector.selector_id,
            "selector_version": self._selector.selector_version,
            "selector_implementation_hash": canonical_hash(
                inspect.getsource(type(self._selector)),
                prefix="counterfactual_selector_impl:",
            ),
        }

    def plan(
        self,
        context: CounterfactualContext,
        clause: QualityClause,
        spec: ClauseMutationSpec,
    ) -> tuple[CounterfactualMutationDraft, ...]:
        target_id = clause.target.target_ref
        target = context.corpus.by_id().get(target_id)
        if target is None:
            return ()
        candidates = tuple(
            sorted(
                (
                    item
                    for item in context.corpus.evidence
                    if item.evidence_id != target_id and self._selector(target, item)
                ),
                key=lambda item: item.evidence_id,
            )
        )
        if not candidates:
            return ()
        replacement = candidates[0]
        search_indexes = tuple(
            index
            for index, step in enumerate(context.source_trajectory.steps)
            if step.action == ActionType.SEARCH
        )
        selection_indexes = tuple(
            index
            for index, step in enumerate(context.source_trajectory.steps)
            if step.action == ActionType.SELECT_EVIDENCE and target_id in step.evidence_ids
        )
        if not search_indexes or not selection_indexes:
            return ()
        paths = (
            *(f"steps[{index}].evidence_ids" for index in search_indexes),
            *(f"steps[{index}].evidence_ids" for index in selection_indexes),
        )
        return (
            CounterfactualMutationDraft(
                parameters={
                    "target_evidence_id": target_id,
                    "replacement_evidence_id": replacement.evidence_id,
                    "search_step_indexes": search_indexes,
                    "selection_step_indexes": selection_indexes,
                },
                allowed_json_path_prefixes=paths,
            ),
        )

    def apply(
        self,
        context: CounterfactualContext,
        opportunity: CounterfactualOpportunity,
    ) -> Trajectory:
        target = str(opportunity.parameters["target_evidence_id"])
        replacement = str(opportunity.parameters["replacement_evidence_id"])
        steps = []
        for step in context.source_trajectory.steps:
            evidence_ids = step.evidence_ids
            if step.action == ActionType.SEARCH:
                evidence_ids = tuple(dict.fromkeys((*evidence_ids, replacement)))
            elif step.action == ActionType.SELECT_EVIDENCE and target in evidence_ids:
                evidence_ids = tuple(
                    replacement if item == target else item for item in evidence_ids
                )
            steps.append(step.model_copy(update={"evidence_ids": evidence_ids}))
        return context.source_trajectory.model_copy(update={"steps": tuple(steps)})


def universal_counterfactual_registry(
    *extra_operators,
) -> CounterfactualOperatorRegistry:
    return CounterfactualOperatorRegistry(
        (
            RemoveSelectedEvidenceOperator(),
            SetStepFailedOperator(),
            InjectOracleReferenceOperator(),
            ReplaceToolOperator(),
            PerturbProgramOutputOperator(),
            ReplaceProgramOperatorOperator(),
            BreakProgramDependencyOperator(),
            PerturbAnswerResultOperator(),
            ReplaceCitationSourceOperator(),
            AppendUnsupportedClaimOperator(),
            *extra_operators,
        )
    )


def _perturb_value(value: Any) -> Any:
    if isinstance(value, dict):
        dict_output: dict[Any, Any] = deepcopy(value)
        if not dict_output:
            dict_output["counterfactual"] = True
            return dict_output
        key = sorted(dict_output)[0]
        dict_output[key] = _perturb_value(dict_output[key])
        return dict_output
    if isinstance(value, list):
        list_output: list[Any] = deepcopy(value)
        if list_output:
            list_output[0] = _perturb_value(list_output[0])
        else:
            list_output.append("counterfactual")
        return list_output
    if isinstance(value, bool):
        return not value
    if isinstance(value, (int, float, Decimal)):
        return value + 1
    if isinstance(value, str):
        try:
            return str(Decimal(value) + Decimal("1"))
        except (InvalidOperation, ValueError):
            return f"counterfactual:{value}"
    if value is None:
        return "counterfactual"
    return f"counterfactual:{value}"
