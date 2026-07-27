from __future__ import annotations

from trusted_synthesis.core.evidence.payloads import EvidenceKind
from trusted_synthesis.core.task.pattern import (
    EvidenceRoleSpec,
    PatternInputKind,
    PatternInputRef,
    ProgramNodeTemplate,
    TaskPatternSpec,
)
from trusted_synthesis.core.task.schema import RetrievalTrack, TaskLevel

SCIENCE_PROTOCOL_COMPATIBILITY_PATTERN = TaskPatternSpec(
    pattern_id="science.protocol_compatibility",
    pattern_version="1.0.0",
    domain="science",
    task_type="science_protocol_compatibility",
    level=TaskLevel.EVIDENCE_INTEGRATION,
    retrieval_track=RetrievalTrack.SEMI_OPEN,
    evidence_roles=(
        EvidenceRoleSpec(
            role_id="experiments",
            accepted_kinds=(EvidenceKind.EXPERIMENTAL_RESULT,),
            min_count=2,
            max_count=2,
            semantic_constraints=(
                "science_evidence_valid",
                "same_metric_definition",
                "uncertainty_present",
            ),
            scope_constraints=("same_dataset_population",),
        ),
    ),
    program_template=(
        ProgramNodeTemplate(
            node_role_id="result",
            operator_id="science_align_protocol",
            input_refs=(
                PatternInputRef(
                    kind=PatternInputKind.EVIDENCE_ROLE,
                    ref_id="experiments",
                ),
            ),
            output_schema="structured",
        ),
    ),
    output_node_role_id="result",
    answer_schema={
        "type": "science_protocol_alignment",
        "required_fields": ["comparable", "mismatches"],
    },
    instruction_renderer_id="science.protocol_compatibility.v1",
    quality_profile_id="science.protocol_compatibility.quality.v1",
    cross_role_constraints=("protocol_difference_reported",),
    difficulty_base="hard",
    difficulty_base_cost=4.0,
    metadata={"pattern_catalog": "science_contract_patterns.v2"},
)

SCIENCE_PROTOCOL_COMPARISON_PATTERN = TaskPatternSpec(
    pattern_id="science.protocol_effect_comparison",
    pattern_version="1.0.0",
    domain="science",
    task_type="science_protocol_effect_comparison",
    level=TaskLevel.RESEARCH_WORKFLOW,
    retrieval_track=RetrievalTrack.SEMI_OPEN,
    evidence_roles=(
        EvidenceRoleSpec(
            role_id="experiments",
            accepted_kinds=(EvidenceKind.EXPERIMENTAL_RESULT,),
            min_count=2,
            max_count=2,
            semantic_constraints=(
                "science_evidence_valid",
                "same_metric_definition",
                "protocol_comparable",
                "uncertainty_present",
            ),
            scope_constraints=("same_dataset_population",),
        ),
    ),
    program_template=(
        ProgramNodeTemplate(
            node_role_id="align_protocol",
            operator_id="science_align_protocol",
            input_refs=(
                PatternInputRef(
                    kind=PatternInputKind.EVIDENCE_ROLE,
                    ref_id="experiments",
                ),
            ),
            output_schema="structured",
        ),
        ProgramNodeTemplate(
            node_role_id="result",
            operator_id="science_compare_effect",
            input_refs=(
                PatternInputRef(
                    kind=PatternInputKind.OPERATION_NODE,
                    ref_id="align_protocol",
                ),
                PatternInputRef(
                    kind=PatternInputKind.EVIDENCE_ROLE,
                    ref_id="experiments",
                ),
            ),
            output_schema="structured",
        ),
    ),
    output_node_role_id="result",
    answer_schema={
        "type": "science_effect_comparison",
        "required_fields": [
            "higher_ref",
            "difference",
            "uncertainty_intervals_overlap",
            "qualified_conclusion",
        ],
    },
    instruction_renderer_id="science.protocol_effect_comparison.v1",
    quality_profile_id="science.protocol_effect_comparison.quality.v1",
    cross_role_constraints=("uncertainty_preserved",),
    difficulty_base="expert",
    difficulty_base_cost=6.0,
    metadata={"pattern_catalog": "science_contract_patterns.v2"},
)


SCIENCE_DESCRIPTIVE_SYNTHESIS_PATTERN = TaskPatternSpec(
    pattern_id="science.descriptive_effect_synthesis",
    pattern_version="1.0.0",
    domain="science",
    task_type="science_descriptive_effect_synthesis",
    level=TaskLevel.RESEARCH_WORKFLOW,
    retrieval_track=RetrievalTrack.SEMI_OPEN,
    evidence_roles=(
        EvidenceRoleSpec(
            role_id="experiments",
            accepted_kinds=(EvidenceKind.EXPERIMENTAL_RESULT,),
            min_count=3,
            max_count=None,
            semantic_constraints=(
                "science_evidence_valid",
                "same_metric_definition",
                "protocol_comparable",
                "uncertainty_present",
                "sample_size_present",
            ),
            scope_constraints=("same_dataset_population",),
        ),
    ),
    program_template=(
        ProgramNodeTemplate(
            node_role_id="result",
            operator_id="science_summarize_effects",
            input_refs=(
                PatternInputRef(
                    kind=PatternInputKind.EVIDENCE_ROLE,
                    ref_id="experiments",
                ),
            ),
            output_schema="structured",
        ),
    ),
    output_node_role_id="result",
    answer_schema={
        "type": "science_descriptive_effect_synthesis",
        "required_fields": [
            "weighted_value",
            "total_sample_size",
            "uncertainty_lower",
            "uncertainty_upper",
            "qualified_conclusion",
        ],
    },
    instruction_renderer_id="science.descriptive_effect_synthesis.v1",
    quality_profile_id="science.descriptive_effect_synthesis.quality.v1",
    cross_role_constraints=(
        "uncertainty_preserved",
        "descriptive_not_meta_analysis",
    ),
    difficulty_base="research",
    difficulty_base_cost=7.0,
    metadata={"pattern_catalog": "science_contract_patterns.v2"},
)


SCIENCE_TASK_PATTERNS = (
    SCIENCE_PROTOCOL_COMPATIBILITY_PATTERN,
    SCIENCE_PROTOCOL_COMPARISON_PATTERN,
    SCIENCE_DESCRIPTIVE_SYNTHESIS_PATTERN,
)
