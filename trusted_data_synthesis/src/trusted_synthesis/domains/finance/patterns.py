from __future__ import annotations

from trusted_synthesis.core.evidence.payloads import EvidenceKind
from trusted_synthesis.core.task.pattern import (
    EvidenceRoleSpec,
    PatternInputKind,
    PatternInputRef,
    ProgramNodeTemplate,
    TaskPatternSpec,
)
from trusted_synthesis.core.task.schema import TaskLevel, VerifierRequirement


def finance_task_patterns(
    *,
    allow_structured_claims: bool = False,
    source_grounding_requirement: VerifierRequirement = VerifierRequirement.NOT_APPLICABLE,
) -> tuple[TaskPatternSpec, ...]:
    scalar = (EvidenceKind.SCALAR,)
    return (
        TaskPatternSpec(
            pattern_id="finance.fact_retrieval",
            task_type="fact_retrieval",
            level=TaskLevel.FACT_RETRIEVAL,
            evidence_roles=(
                EvidenceRoleSpec(
                    role_id="fact",
                    accepted_kinds=scalar,
                    semantic_constraints=("finance_evidence_valid",),
                ),
            ),
            program_template=(
                ProgramNodeTemplate(
                    node_role_id="result",
                    operator_id="lookup",
                    input_refs=(
                        PatternInputRef(
                            kind=PatternInputKind.EVIDENCE_ROLE,
                            ref_id="fact",
                        ),
                    ),
                    output_schema="payload",
                ),
            ),
            output_node_role_id="result",
            answer_schema={"type": "payload_with_source"},
            instruction_renderer_id="finance.fact_retrieval.v1",
            quality_profile_id="finance.fact_retrieval.quality.v1",
            difficulty_base="easy",
            difficulty_base_cost=0.5,
            domain="finance",
            pattern_version="1.0.0",
            allow_structured_claims=allow_structured_claims,
            source_grounding_requirement=source_grounding_requirement,
            metadata={"pattern_catalog": "finance_reference_patterns.v1"},
        ),
        TaskPatternSpec(
            pattern_id="finance.comparison",
            task_type="comparison",
            level=TaskLevel.EVIDENCE_INTEGRATION,
            evidence_roles=(
                EvidenceRoleSpec(
                    role_id="left",
                    accepted_kinds=scalar,
                    semantic_constraints=("finance_evidence_valid",),
                ),
                EvidenceRoleSpec(
                    role_id="right",
                    accepted_kinds=scalar,
                    semantic_constraints=("finance_evidence_valid",),
                ),
            ),
            program_template=(
                ProgramNodeTemplate(
                    node_role_id="result",
                    operator_id="compare",
                    input_refs=(
                        PatternInputRef(kind=PatternInputKind.EVIDENCE_ROLE, ref_id="left"),
                        PatternInputRef(kind=PatternInputKind.EVIDENCE_ROLE, ref_id="right"),
                    ),
                    output_schema="comparison",
                ),
            ),
            output_node_role_id="result",
            answer_schema={
                "type": "comparison",
                "required_fields": ["higher_ref", "difference"],
            },
            instruction_renderer_id="finance.comparison.v1",
            quality_profile_id="finance.comparison.quality.v1",
            cross_role_constraints=("finance_metric_comparable",),
            difficulty_base="medium",
            difficulty_base_cost=2.0,
            domain="finance",
            pattern_version="1.0.0",
            allow_structured_claims=allow_structured_claims,
            source_grounding_requirement=source_grounding_requirement,
            metadata={"pattern_catalog": "finance_reference_patterns.v1"},
        ),
        TaskPatternSpec(
            pattern_id="finance.temporal_growth",
            task_type="temporal_growth",
            level=TaskLevel.RESEARCH_WORKFLOW,
            evidence_roles=(
                EvidenceRoleSpec(
                    role_id="earlier",
                    accepted_kinds=scalar,
                    semantic_constraints=("finance_evidence_valid",),
                    temporal_constraints=("strictly_before_later",),
                ),
                EvidenceRoleSpec(
                    role_id="later",
                    accepted_kinds=scalar,
                    semantic_constraints=("finance_evidence_valid",),
                ),
            ),
            program_template=(
                ProgramNodeTemplate(
                    node_role_id="earlier_value",
                    operator_id="lookup",
                    input_refs=(
                        PatternInputRef(kind=PatternInputKind.EVIDENCE_ROLE, ref_id="earlier"),
                    ),
                    output_schema="payload",
                ),
                ProgramNodeTemplate(
                    node_role_id="later_value",
                    operator_id="lookup",
                    input_refs=(
                        PatternInputRef(kind=PatternInputKind.EVIDENCE_ROLE, ref_id="later"),
                    ),
                    output_schema="payload",
                ),
                ProgramNodeTemplate(
                    node_role_id="result",
                    operator_id="growth",
                    input_refs=(
                        PatternInputRef(
                            kind=PatternInputKind.OPERATION_NODE,
                            ref_id="earlier_value",
                            selector="payload.value",
                        ),
                        PatternInputRef(
                            kind=PatternInputKind.OPERATION_NODE,
                            ref_id="later_value",
                            selector="payload.value",
                        ),
                    ),
                    output_schema="percentage",
                ),
            ),
            output_node_role_id="result",
            answer_schema={"type": "percentage", "unit": "percent"},
            instruction_renderer_id="finance.temporal_growth.v1",
            quality_profile_id="finance.temporal_growth.quality.v1",
            cross_role_constraints=(
                "same_financial_series",
                "positive_growth_base",
                "strict_temporal_order",
            ),
            difficulty_base="hard",
            difficulty_base_cost=4.0,
            domain="finance",
            pattern_version="1.0.0",
            allow_structured_claims=allow_structured_claims,
            source_grounding_requirement=source_grounding_requirement,
            metadata={"pattern_catalog": "finance_reference_patterns.v1"},
        ),
        TaskPatternSpec(
            pattern_id="finance.temporal_average",
            task_type="temporal_average",
            level=TaskLevel.RESEARCH_WORKFLOW,
            evidence_roles=(
                EvidenceRoleSpec(
                    role_id="series",
                    accepted_kinds=scalar,
                    min_count=3,
                    max_count=None,
                    semantic_constraints=("same_financial_series",),
                    temporal_constraints=("strictly_ordered_unique_periods",),
                ),
            ),
            program_template=(
                ProgramNodeTemplate(
                    node_role_id="value",
                    operator_id="lookup",
                    input_refs=(
                        PatternInputRef(kind=PatternInputKind.CURRENT_EVIDENCE, ref_id="series"),
                    ),
                    output_schema="payload",
                    foreach_evidence_role="series",
                ),
                ProgramNodeTemplate(
                    node_role_id="result",
                    operator_id="aggregate",
                    input_refs=(
                        PatternInputRef(
                            kind=PatternInputKind.OPERATION_GROUP,
                            ref_id="value",
                            selector="payload.value",
                        ),
                    ),
                    parameters={"method": "mean"},
                    output_schema="scalar",
                ),
            ),
            output_node_role_id="result",
            answer_schema={
                "type": "aggregate",
                "method": "mean",
                "required_fields": ["method", "value"],
            },
            instruction_renderer_id="finance.temporal_average.v1",
            quality_profile_id="finance.temporal_average.quality.v1",
            cross_role_constraints=("same_subject", "same_financial_definition"),
            difficulty_base="hard",
            difficulty_base_cost=4.0,
            domain="finance",
            pattern_version="1.0.0",
            allow_structured_claims=allow_structured_claims,
            source_grounding_requirement=source_grounding_requirement,
            metadata={"pattern_catalog": "finance_reference_patterns.v1"},
        ),
    )
