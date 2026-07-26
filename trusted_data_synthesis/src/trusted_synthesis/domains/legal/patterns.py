from __future__ import annotations

from trusted_synthesis.core.evidence.payloads import EvidenceKind
from trusted_synthesis.core.task.pattern import (
    EvidenceRoleSpec,
    PatternInputKind,
    PatternInputRef,
    ProgramNodeTemplate,
    TaskPatternSpec,
)
from trusted_synthesis.core.task.schema import TaskLevel

LEGAL_RULE_APPLICATION_PATTERN = TaskPatternSpec(
    pattern_id="legal.rule_application",
    pattern_version="1.0.0",
    domain="legal",
    task_type="legal_rule_application",
    level=TaskLevel.RESEARCH_WORKFLOW,
    evidence_roles=(
        EvidenceRoleSpec(
            role_id="rules",
            accepted_kinds=(EvidenceKind.RULE,),
            min_count=2,
            max_count=None,
            semantic_constraints=("legal_evidence_valid", "same_legal_question"),
            temporal_constraints=("effective_time_present",),
            scope_constraints=("same_jurisdiction_scope",),
        ),
    ),
    program_template=(
        ProgramNodeTemplate(
            node_role_id="apply",
            operator_id="legal_apply_rule",
            input_refs=(
                PatternInputRef(
                    kind=PatternInputKind.CURRENT_EVIDENCE,
                    ref_id="rules",
                ),
            ),
            output_schema="structured",
            foreach_evidence_role="rules",
        ),
        ProgramNodeTemplate(
            node_role_id="result",
            operator_id="legal_resolve_authority",
            input_refs=(
                PatternInputRef(
                    kind=PatternInputKind.OPERATION_GROUP,
                    ref_id="apply",
                ),
            ),
            output_schema="structured",
        ),
    ),
    output_node_role_id="result",
    answer_schema={
        "type": "legal_rule_decision",
        "required_fields": [
            "applicable",
            "selected_ref",
            "authority",
            "legal_effect",
        ],
    },
    instruction_renderer_id="legal.rule_application.v1",
    quality_profile_id="legal.rule_application.quality.v1",
    cross_role_constraints=(
        "authority_priority_complete",
        "conditions_and_exceptions_explicit",
    ),
    difficulty_base="expert",
    difficulty_base_cost=6.0,
    metadata={"pattern_catalog": "legal_contract_patterns.v1"},
)

