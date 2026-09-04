from __future__ import annotations

from decimal import Decimal

from trusted_synthesis.core.evidence.payloads import EvidenceKind, ScalarObservation
from trusted_synthesis.core.evidence.schema import EvidenceBundle, EvidenceItem
from trusted_synthesis.core.graph.schema import ProofGraph
from trusted_synthesis.core.task.binding import EvidenceBinding
from trusted_synthesis.core.task.materialization import (
    oracle_selection_contract,
    resolved_retrieval_scope,
    temporal_sort_key,
)
from trusted_synthesis.core.task.pattern import (
    EvidenceRoleSpec,
    PatternBindingValidationReport,
    PatternInputKind,
    PatternInputRef,
    ProgramNodeTemplate,
    TaskPatternMaterialization,
    TaskPatternSpec,
)
from trusted_synthesis.core.task.realization import (
    QuestionRendererProfile,
    render_protected_template,
)
from trusted_synthesis.core.task.schema import TaskLevel
from trusted_synthesis.domains.finance.patterns import REGISTERED_FINANCIAL_RATIO_PAIRS
from trusted_synthesis.domains.finance.policy import FinanceSemanticPolicy

SERIAL_TASK_TYPE = "registered_margin_target_gap"
BRANCH_TASK_TYPE = "derived_growth_absolute_spread"
SERIAL_RENDERER_ID = "finance.experimental.registered_margin_target_gap.v1"
BRANCH_RENDERER_ID = "finance.experimental.derived_growth_absolute_spread.v1"


def depth_three_patterns() -> tuple[TaskPatternSpec, ...]:
    scalar = (EvidenceKind.SCALAR,)
    common_answer = {
        "type": "percentage_point_scalar",
        "required_fields": ["value", "unit"],
    }
    serial = TaskPatternSpec(
        pattern_id="finance.experimental.registered_margin_target_gap",
        pattern_version="1.0.0",
        domain="finance",
        task_type=SERIAL_TASK_TYPE,
        level=TaskLevel.RESEARCH_WORKFLOW,
        evidence_roles=(
            EvidenceRoleSpec(
                role_id="numerator",
                accepted_kinds=scalar,
                semantic_constraints=("registered_ratio_numerator",),
            ),
            EvidenceRoleSpec(
                role_id="denominator",
                accepted_kinds=scalar,
                semantic_constraints=("registered_ratio_denominator",),
            ),
            EvidenceRoleSpec(
                role_id="target",
                accepted_kinds=scalar,
                semantic_constraints=("percentage_point_target",),
            ),
        ),
        program_template=(
            _lookup("numerator_value", "numerator"),
            _lookup("denominator_value", "denominator"),
            _lookup("target_value", "target"),
            ProgramNodeTemplate(
                node_role_id="margin_ratio",
                operator_id="ratio",
                input_refs=(
                    _operation("numerator_value", "payload.value"),
                    _operation("denominator_value", "payload.value"),
                ),
                parameters={"registered_pair": "gross_profit/revenue"},
                output_schema="scalar",
            ),
            ProgramNodeTemplate(
                node_role_id="margin_percent",
                operator_id="scale_ratio_percent",
                input_refs=(_operation("margin_ratio", "value"),),
                output_schema="percentage",
            ),
            ProgramNodeTemplate(
                node_role_id="result",
                operator_id="signed_percentage_point_gap",
                input_refs=(
                    _operation("target_value", "payload.value"),
                    _operation("margin_percent", "value"),
                ),
                output_schema="scalar",
            ),
        ),
        output_node_role_id="result",
        answer_schema=common_answer,
        instruction_renderer_id=SERIAL_RENDERER_ID,
        quality_profile_id="finance.experimental.depth_three.serial.quality.v1",
        cross_role_constraints=(
            "registered_gross_margin_pair",
            "same_subject_period",
            "target_in_percentage_points",
        ),
        difficulty_base="expert",
        difficulty_base_cost=8.0,
        metadata={
            "pattern_catalog": "finance_semantic_depth_three_constructibility.v1",
            "experimental_only": True,
            "topology_kind": "serial_chain",
        },
    )
    branch = TaskPatternSpec(
        pattern_id="finance.experimental.derived_growth_absolute_spread",
        pattern_version="1.0.0",
        domain="finance",
        task_type=BRANCH_TASK_TYPE,
        level=TaskLevel.RESEARCH_WORKFLOW,
        evidence_roles=(
            EvidenceRoleSpec(
                role_id="revenue_earlier",
                accepted_kinds=scalar,
                temporal_constraints=("strictly_before_revenue_later",),
            ),
            EvidenceRoleSpec(
                role_id="revenue_later",
                accepted_kinds=scalar,
            ),
            EvidenceRoleSpec(
                role_id="income_earlier",
                accepted_kinds=scalar,
                temporal_constraints=("strictly_before_income_later",),
            ),
            EvidenceRoleSpec(
                role_id="income_later",
                accepted_kinds=scalar,
            ),
        ),
        program_template=(
            _lookup("revenue_earlier_value", "revenue_earlier"),
            _lookup("revenue_later_value", "revenue_later"),
            _lookup("income_earlier_value", "income_earlier"),
            _lookup("income_later_value", "income_later"),
            ProgramNodeTemplate(
                node_role_id="revenue_growth",
                operator_id="growth",
                input_refs=(
                    _operation("revenue_earlier_value", "payload.value"),
                    _operation("revenue_later_value", "payload.value"),
                ),
                output_schema="percentage",
            ),
            ProgramNodeTemplate(
                node_role_id="income_growth",
                operator_id="growth",
                input_refs=(
                    _operation("income_earlier_value", "payload.value"),
                    _operation("income_later_value", "payload.value"),
                ),
                output_schema="percentage",
            ),
            ProgramNodeTemplate(
                node_role_id="signed_gap",
                operator_id="signed_percentage_point_gap",
                input_refs=(
                    _operation("income_growth", "value"),
                    _operation("revenue_growth", "value"),
                ),
                output_schema="scalar",
            ),
            ProgramNodeTemplate(
                node_role_id="result",
                operator_id="absolute_percentage_point_gap",
                input_refs=(_operation("signed_gap", "value"),),
                output_schema="scalar",
            ),
        ),
        output_node_role_id="result",
        answer_schema=common_answer,
        instruction_renderer_id=BRANCH_RENDERER_ID,
        quality_profile_id="finance.experimental.depth_three.branch.quality.v1",
        cross_role_constraints=(
            "same_subject",
            "aligned_growth_window",
            "revenue_and_operating_income",
        ),
        difficulty_base="expert",
        difficulty_base_cost=9.0,
        metadata={
            "pattern_catalog": "finance_semantic_depth_three_constructibility.v1",
            "experimental_only": True,
            "topology_kind": "branch_and_merge",
        },
    )
    return serial, branch


def depth_three_renderer_profiles() -> tuple[QuestionRendererProfile, ...]:
    return (
        QuestionRendererProfile(
            profile_id=SERIAL_RENDERER_ID,
            task_type=SERIAL_TASK_TYPE,
            intent="registered_margin_target_gap",
            language="en",
            style="canonical",
            protected_template=(
                "For <slot_period>, what is <slot_subject>'s gross-margin percentage-point "
                "gap from the <slot_target_percent> target after computing gross profit "
                "divided by revenue and converting the ratio to percent?"
            ),
            required_slots=("period", "subject", "target_percent"),
            required_operator_cues=(
                "gap",
                "gross profit divided by revenue",
                "converting the ratio to percent",
            ),
            source_requirement="explicit",
        ),
        QuestionRendererProfile(
            profile_id=BRANCH_RENDERER_ID,
            task_type=BRANCH_TASK_TYPE,
            intent="derived_growth_absolute_spread",
            language="en",
            style="canonical",
            protected_template=(
                "Across <slot_time_range>, what is the absolute percentage-point spread "
                "between <slot_subject>'s revenue growth and operating-income growth after "
                "calculating both growth rates?"
            ),
            required_slots=("time_range", "subject"),
            required_operator_cues=(
                "absolute percentage-point spread",
                "revenue growth",
                "operating-income growth",
            ),
            source_requirement="explicit",
        ),
    )


class DepthThreePatternRuntime:
    runtime_id = "finance_semantic_depth_three_pattern_runtime.v1"
    runtime_version = "1.0.0"
    domain = "finance"
    renderer_ids = (SERIAL_RENDERER_ID, BRANCH_RENDERER_ID)

    def __init__(self) -> None:
        self._policy = FinanceSemanticPolicy()
        self._profiles = {profile.task_type: profile for profile in depth_three_renderer_profiles()}

    def validate_binding(
        self,
        pattern: TaskPatternSpec,
        binding: EvidenceBinding,
        evidence_by_role: dict[str, tuple[EvidenceItem, ...]],
    ) -> PatternBindingValidationReport:
        del binding
        evidence = tuple(
            item for role in pattern.evidence_roles for item in evidence_by_role[role.role_id]
        )
        checks: dict[str, bool] = {
            "all_evidence_valid": all(
                self._policy.validate_evidence(item).passed for item in evidence
            )
        }
        if pattern.task_type == SERIAL_TASK_TYPE:
            numerator = evidence_by_role["numerator"][0]
            denominator = evidence_by_role["denominator"][0]
            target = evidence_by_role["target"][0]
            pair = (numerator.predicate, denominator.predicate)
            checks.update(
                {
                    "registered_gross_margin_pair": pair == ("gross_profit", "revenue")
                    and pair in REGISTERED_FINANCIAL_RATIO_PAIRS,
                    "same_subject_period": (
                        len({item.subject.subject_id for item in evidence}) == 1
                        and len({item.temporal_context.label for item in evidence}) == 1
                    ),
                    "denominator_nonzero": _scalar(denominator) != 0,
                    "target_in_percentage_points": (
                        target.predicate == "gross_margin_target"
                        and isinstance(target.payload, ScalarObservation)
                        and target.payload.unit == "percent"
                    ),
                }
            )
        elif pattern.task_type == BRANCH_TASK_TYPE:
            re = evidence_by_role["revenue_earlier"][0]
            rl = evidence_by_role["revenue_later"][0]
            ie = evidence_by_role["income_earlier"][0]
            il = evidence_by_role["income_later"][0]
            checks.update(
                {
                    "same_subject": len({item.subject.subject_id for item in evidence}) == 1,
                    "revenue_and_operating_income": (
                        (re.predicate, rl.predicate) == ("revenue", "revenue")
                        and (ie.predicate, il.predicate) == ("operating_income", "operating_income")
                    ),
                    "aligned_growth_window": (
                        temporal_sort_key(re) == temporal_sort_key(ie)
                        and temporal_sort_key(rl) == temporal_sort_key(il)
                        and temporal_sort_key(re) is not None
                        and temporal_sort_key(rl) is not None
                        and temporal_sort_key(re) < temporal_sort_key(rl)
                    ),
                    "positive_growth_bases": _scalar(re) > 0 and _scalar(ie) > 0,
                }
            )
        else:
            raise ValueError(f"unsupported depth-three pattern: {pattern.task_type}")
        issues = tuple(check_id for check_id, passed in checks.items() if not passed)
        return PatternBindingValidationReport(
            passed=not issues,
            checks=checks,
            issues=issues,
            semantic_alignment_cost=float(max(len(checks) - 1, 0)),
        )

    def materialize(
        self,
        pattern: TaskPatternSpec,
        binding: EvidenceBinding,
        evidence_by_role: dict[str, tuple[EvidenceItem, ...]],
        bundle: EvidenceBundle,
        proof_graph: ProofGraph,
    ) -> TaskPatternMaterialization:
        del binding, bundle, proof_graph
        evidence = tuple(
            item for role in pattern.evidence_roles for item in evidence_by_role[role.role_id]
        )
        profile = self._profiles[pattern.task_type]
        if pattern.task_type == SERIAL_TASK_TYPE:
            target = evidence_by_role["target"][0]
            slots = {
                "period": str(target.temporal_context.label),
                "subject": target.subject.name,
                "target_percent": f"{_scalar(target)}%",
            }
        else:
            earlier = evidence_by_role["revenue_earlier"][0]
            later = evidence_by_role["revenue_later"][0]
            slots = {
                "time_range": (
                    f"{earlier.temporal_context.label} to {later.temporal_context.label}"
                ),
                "subject": earlier.subject.name,
            }
        return TaskPatternMaterialization(
            instruction=render_protected_template(profile.protected_template, slots),
            retrieval_scope=resolved_retrieval_scope(evidence),
            answer_schema={},
            oracle_selection_contract=oracle_selection_contract(evidence),
            metadata={
                "domain_plugin_id": "finance_semantic_depth_three_experiment.v1",
                "experimental_only": True,
                "topology_kind": pattern.metadata["topology_kind"],
            },
        )

    def slot_values(
        self,
        task_type: str,
        evidence_by_role: dict[str, tuple[EvidenceItem, ...]],
    ) -> dict[str, str]:
        if task_type == SERIAL_TASK_TYPE:
            target = evidence_by_role["target"][0]
            return {
                "period": str(target.temporal_context.label),
                "subject": target.subject.name,
                "target_percent": f"{_scalar(target)}%",
            }
        earlier = evidence_by_role["revenue_earlier"][0]
        later = evidence_by_role["revenue_later"][0]
        return {
            "time_range": f"{earlier.temporal_context.label} to {later.temporal_context.label}",
            "subject": earlier.subject.name,
        }


def _lookup(node_id: str, role_id: str) -> ProgramNodeTemplate:
    return ProgramNodeTemplate(
        node_role_id=node_id,
        operator_id="lookup",
        input_refs=(PatternInputRef(kind=PatternInputKind.EVIDENCE_ROLE, ref_id=role_id),),
        output_schema="payload",
    )


def _operation(node_id: str, selector: str) -> PatternInputRef:
    return PatternInputRef(
        kind=PatternInputKind.OPERATION_NODE,
        ref_id=node_id,
        selector=selector,
    )


def _scalar(item: EvidenceItem) -> Decimal:
    if not isinstance(item.payload, ScalarObservation):
        raise ValueError("depth-three pattern requires scalar evidence")
    return Decimal(str(item.payload.value))
