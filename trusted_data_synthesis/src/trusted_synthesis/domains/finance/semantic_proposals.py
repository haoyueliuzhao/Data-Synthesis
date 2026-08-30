from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.core.evidence.payloads import EvidenceKind
from trusted_synthesis.core.operations.registry import OperationRegistry
from trusted_synthesis.core.task.pattern import TaskPatternSpec
from trusted_synthesis.core.task.schema import PlanningTrack, RetrievalTrack
from trusted_synthesis.core.task.semantic import (
    ProposalEvidenceRole,
    ProposalInput,
    ProposalOperation,
    ProposalSource,
    SemanticTaskProposal,
    make_semantic_task_proposal,
)
from trusted_synthesis.domains.finance.operations import finance_vnext_operation_registry
from trusted_synthesis.domains.finance.patterns import finance_task_patterns
from trusted_synthesis.domains.finance.question_rendering import finance_renderer_registry
from trusted_synthesis.hashing import canonical_hash

RAW_GRAPH_PATTERNS_SHA256 = "763f52bcb391b1678f8833fda8662f20f08c3abf549550f07f2e3cb48bd007c7"


class ProposalAuthorization(str, Enum):
    AUTHORIZED = "authorized_for_current_compiler"
    BLOCKED = "blocked_fail_closed"


class ProposalCompatibilityRow(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    row_id: str = Field(min_length=1)
    proposal_id: str = Field(min_length=1)
    task_type: str = Field(min_length=1)
    required_operator_ids: tuple[str, ...] = Field(min_length=1)
    available_operator_ids: tuple[str, ...]
    missing_operator_ids: tuple[str, ...]
    task_pattern_id: str | None = None
    renderer_profile_count: int = Field(ge=0)
    policy_contract_available: bool
    operation_output_schema_match: bool
    evidence_role_contract_match: bool
    operation_dag_contract_match: bool
    parameter_contract_match: bool
    answer_schema_contract_match: bool
    semantic_constraint_contract_match: bool
    renderer_intent_contract_match: bool
    quality_profile_contract_match: bool
    authorization: ProposalAuthorization
    reason: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_row(self) -> ProposalCompatibilityRow:
        complete = (
            not self.missing_operator_ids
            and self.task_pattern_id is not None
            and self.renderer_profile_count >= 4
            and self.policy_contract_available
            and self.operation_output_schema_match
            and self.evidence_role_contract_match
            and self.operation_dag_contract_match
            and self.parameter_contract_match
            and self.answer_schema_contract_match
            and self.semantic_constraint_contract_match
            and self.renderer_intent_contract_match
            and self.quality_profile_contract_match
        )
        if (self.authorization == ProposalAuthorization.AUTHORIZED) != complete:
            raise ValueError("proposal authorization does not match noncompensatory checks")
        expected = canonical_hash(
            self.model_dump(mode="json", exclude={"row_id"}),
            prefix="finance_proposal_compatibility:",
        )
        if self.row_id != expected:
            raise ValueError("proposal compatibility row identity is invalid")
        return self


class RawProposalMigrationAudit(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    audit_id: str = Field(min_length=1)
    source_module_sha256: str = Field(min_length=64, max_length=64)
    proposal_ids: tuple[str, ...] = Field(min_length=1)
    rows: tuple[ProposalCompatibilityRow, ...] = Field(min_length=1)
    authorized_count: int = Field(ge=0)
    blocked_count: int = Field(ge=0)
    imported_qa_row_count: int = Field(default=0, ge=0)
    gates: dict[str, bool]
    schema_version: str = "raw_proposal_migration_audit.v1"

    @model_validator(mode="after")
    def validate_audit(self) -> RawProposalMigrationAudit:
        if any(not passed for passed in self.gates.values()):
            raise ValueError("raw proposal migration audit failed a hard gate")
        authorized = sum(row.authorization == ProposalAuthorization.AUTHORIZED for row in self.rows)
        if authorized != self.authorized_count:
            raise ValueError("raw proposal authorized count mismatch")
        if len(self.rows) - authorized != self.blocked_count:
            raise ValueError("raw proposal blocked count mismatch")
        expected = canonical_hash(
            self.model_dump(mode="json", exclude={"audit_id"}),
            prefix="raw_proposal_migration_audit:",
        )
        if self.audit_id != expected:
            raise ValueError("raw proposal migration audit identity is invalid")
        return self


def raw_finance_semantic_proposals() -> tuple[SemanticTaskProposal, ...]:
    scalar = (EvidenceKind.SCALAR.value,)
    provenance = {
        "source_repository": "raw_financial_data_lake",
        "source_path": "finraw/qa/graph_patterns.py",
        "source_sha256": RAW_GRAPH_PATTERNS_SHA256,
        "raw_qa_rows_imported": False,
        "migration_mode": "semantic_proposal_translation_only",
    }
    return (
        make_semantic_task_proposal(
            source=ProposalSource.RAW_STATIC_GRAPH_PATTERN,
            source_artifact_id="raw_graph_pattern:entity_cross_metric_comparison:v3",
            domain="finance",
            task_family="comparison",
            task_type="registered_cross_metric_comparison",
            evidence_roles=(
                _role("left_metric", scalar),
                _role("right_metric", scalar),
            ),
            operations=(
                ProposalOperation(
                    node_role_id="result",
                    operator_id="registered_compare",
                    inputs=(
                        ProposalInput(kind="evidence_role", ref_id="left_metric"),
                        ProposalInput(kind="evidence_role", ref_id="right_metric"),
                    ),
                    parameters={"registered_pair_from_binding": True},
                    output_schema="comparison",
                ),
            ),
            output_node_role_id="result",
            answer_schema={
                "type": "comparison",
                "required_fields": ["higher_ref", "difference"],
            },
            retrieval_track=RetrievalTrack.RESOLVED,
            planning_track=PlanningTrack.PLAN_GIVEN,
            semantic_constraints=(
                "registered_financial_comparison_pair",
                "same_subject_period_scope_source_and_payload_context",
                "same_statement_type",
                "same_metric_period_type",
                "compatible_source_definition",
                "historical_non_forecast",
            ),
            question_intents=("which_metric_is_higher", "metric_difference"),
            mechanism_contract={
                "finance_policy": "finance_semantics.v2",
                "quality_profile": "finance.registered_cross_metric_comparison.quality.v1",
            },
            migration_provenance={
                **provenance,
                "raw_pattern_id": "entity_cross_metric_comparison",
                "raw_pattern_version": 3,
            },
        ),
        make_semantic_task_proposal(
            source=ProposalSource.RAW_STATIC_GRAPH_PATTERN,
            source_artifact_id="raw_graph_pattern:temporal_argmax_then_metric_lookup:v4",
            domain="finance",
            task_family="multi_stage_temporal_join",
            task_type="temporal_peak_secondary_lookup",
            evidence_roles=(
                _role("primary_series", scalar, min_count=3, max_count=None),
                _role("secondary_series", scalar, min_count=3, max_count=None),
            ),
            operations=(
                ProposalOperation(
                    node_role_id="find_peak",
                    operator_id="argmax",
                    inputs=(ProposalInput(kind="evidence_role", ref_id="primary_series"),),
                    parameters={"selection_key": "period"},
                    output_schema="ranked_selection",
                ),
                ProposalOperation(
                    node_role_id="result",
                    operator_id="select_by_period",
                    inputs=(
                        ProposalInput(kind="operation_node", ref_id="find_peak"),
                        ProposalInput(kind="evidence_role", ref_id="secondary_series"),
                    ),
                    output_schema="period_metric_lookup",
                ),
            ),
            output_node_role_id="result",
            answer_schema={
                "type": "period_metric_lookup",
                "required_fields": [
                    "period",
                    "primary_value",
                    "secondary_value",
                    "unit",
                    "currency",
                ],
            },
            retrieval_track=RetrievalTrack.RESOLVED,
            planning_track=PlanningTrack.PLAN_GIVEN,
            semantic_constraints=(
                "registered_followup_pair",
                "contiguous_periods",
                "complete_secondary_period_coverage",
            ),
            question_intents=("peak_then_lookup", "temporal_followup"),
            mechanism_contract={"authorization_required": True},
            migration_provenance={
                **provenance,
                "raw_pattern_id": "temporal_argmax_then_metric_lookup",
                "raw_pattern_version": 4,
            },
        ),
        make_semantic_task_proposal(
            source=ProposalSource.RAW_STATIC_GRAPH_PATTERN,
            source_artifact_id="raw_graph_pattern:industry_growth_filter_then_margin_rank:v2",
            domain="finance",
            task_family="multi_stage_scope_analysis",
            task_type="growth_filter_margin_rank",
            evidence_roles=(
                _role("current_revenue", scalar, min_count=2, max_count=None),
                _role("previous_revenue", scalar, min_count=2, max_count=None),
                _role("net_income", scalar, min_count=2, max_count=None),
            ),
            operations=(
                _operation(
                    "growth",
                    "growth_by_entity",
                    ("current_revenue", "previous_revenue"),
                    "entity_numeric_table",
                    {"output_metric_id": "revenue_yoy_growth"},
                ),
                ProposalOperation(
                    node_role_id="growth_filter",
                    operator_id="filter",
                    inputs=(ProposalInput(kind="operation_node", ref_id="growth"),),
                    parameters={
                        "comparison": "gt",
                        "field": "normalized_value",
                        "value": "10",
                    },
                    output_schema="entity_numeric_table",
                ),
                _operation(
                    "margin",
                    "ratio_by_entity",
                    ("net_income", "current_revenue"),
                    "entity_numeric_table",
                    {"output_metric_id": "net_margin"},
                ),
                ProposalOperation(
                    node_role_id="eligible_margins",
                    operator_id="intersect_on_entity",
                    inputs=(
                        ProposalInput(kind="operation_node", ref_id="growth_filter"),
                        ProposalInput(kind="operation_node", ref_id="margin"),
                    ),
                    output_schema="entity_numeric_table",
                ),
                ProposalOperation(
                    node_role_id="result",
                    operator_id="rank",
                    inputs=(ProposalInput(kind="operation_node", ref_id="eligible_margins"),),
                    parameters={"direction": "desc", "top_k": 3},
                    output_schema="ranked_table",
                ),
            ),
            output_node_role_id="result",
            answer_schema={"type": "ranked_table", "value_metric": "net_margin"},
            retrieval_track=RetrievalTrack.RESOLVED,
            planning_track=PlanningTrack.PLAN_GIVEN,
            semantic_constraints=(
                "same_industry",
                "consolidated_entity_scope",
                "complete_scope_input_coverage",
            ),
            question_intents=("growth_screen_then_margin_rank", "analyst_filter_rank"),
            mechanism_contract={"authorization_required": True},
            migration_provenance={
                **provenance,
                "raw_pattern_id": "industry_growth_filter_then_margin_rank",
                "raw_pattern_version": 2,
            },
        ),
    )


def audit_raw_proposal_compatibility(
    registry: OperationRegistry | None = None,
) -> RawProposalMigrationAudit:
    resolved_registry = registry or finance_vnext_operation_registry()
    proposals = raw_finance_semantic_proposals()
    patterns = {pattern.task_type: pattern for pattern in finance_task_patterns()}
    renderer_registry = finance_renderer_registry()
    rows = []
    for proposal in proposals:
        required = tuple(dict.fromkeys(node.operator_id for node in proposal.operations))
        available = []
        missing = []
        output_match = True
        for node in proposal.operations:
            try:
                definition = resolved_registry.require(node.operator_id)
            except ValueError:
                missing.append(node.operator_id)
                output_match = False
                continue
            available.append(node.operator_id)
            output_match = output_match and definition.output_schema == node.output_schema
        pattern = patterns.get(proposal.task_type)
        profiles = renderer_registry.for_task_type(proposal.task_type)
        profile_count = len(profiles)
        policy_available = proposal.task_type == "registered_cross_metric_comparison"
        role_match = pattern is not None and _evidence_role_contract_matches(proposal, pattern)
        operation_match = pattern is not None and _operation_dag_contract_matches(proposal, pattern)
        parameter_match = pattern is not None and _parameter_contract_matches(proposal, pattern)
        answer_match = pattern is not None and proposal.answer_schema == pattern.answer_schema
        semantic_match = pattern is not None and (
            proposal.semantic_constraints == pattern.cross_role_constraints
        )
        renderer_intent_match = bool(profiles) and {
            profile.intent for profile in profiles
        }.issubset(set(proposal.question_intents))
        quality_match = pattern is not None and (
            proposal.mechanism_contract.get("quality_profile") == pattern.quality_profile_id
        )
        complete = (
            not missing
            and pattern is not None
            and profile_count >= 4
            and policy_available
            and output_match
            and role_match
            and operation_match
            and parameter_match
            and answer_match
            and semantic_match
            and renderer_intent_match
            and quality_match
        )
        payload = {
            "proposal_id": proposal.proposal_id,
            "task_type": proposal.task_type,
            "required_operator_ids": required,
            "available_operator_ids": tuple(dict.fromkeys(available)),
            "missing_operator_ids": tuple(dict.fromkeys(missing)),
            "task_pattern_id": pattern.pattern_id if pattern is not None else None,
            "renderer_profile_count": profile_count,
            "policy_contract_available": policy_available,
            "operation_output_schema_match": output_match,
            "evidence_role_contract_match": role_match,
            "operation_dag_contract_match": operation_match,
            "parameter_contract_match": parameter_match,
            "answer_schema_contract_match": answer_match,
            "semantic_constraint_contract_match": semantic_match,
            "renderer_intent_contract_match": renderer_intent_match,
            "quality_profile_contract_match": quality_match,
            "authorization": (
                ProposalAuthorization.AUTHORIZED if complete else ProposalAuthorization.BLOCKED
            ),
            "reason": (
                "all_current_noncompensatory_contracts_available"
                if complete
                else "missing_current_operation_policy_pattern_or_renderer_contract"
            ),
        }
        row_id = canonical_hash(payload, prefix="finance_proposal_compatibility:")
        rows.append(ProposalCompatibilityRow(row_id=row_id, **payload))
    rows_tuple = tuple(rows)
    authorized = sum(row.authorization == ProposalAuthorization.AUTHORIZED for row in rows_tuple)
    gates = {
        "priority_proposal_count_exact": len(proposals) == 3,
        "proposal_identity_unique": len({item.proposal_id for item in proposals}) == len(proposals),
        "source_sha256_bound": all(
            item.migration_provenance.get("source_sha256") == RAW_GRAPH_PATTERNS_SHA256
            for item in proposals
        ),
        "raw_qa_rows_imported_zero": all(
            item.migration_provenance.get("raw_qa_rows_imported") is False for item in proposals
        ),
        "authorized_rows_complete": all(
            row.authorization != ProposalAuthorization.AUTHORIZED
            or (
                not row.missing_operator_ids
                and row.task_pattern_id is not None
                and row.renderer_profile_count >= 4
                and row.policy_contract_available
                and row.operation_output_schema_match
                and row.evidence_role_contract_match
                and row.operation_dag_contract_match
                and row.parameter_contract_match
                and row.answer_schema_contract_match
                and row.semantic_constraint_contract_match
                and row.renderer_intent_contract_match
                and row.quality_profile_contract_match
            )
            for row in rows_tuple
        ),
        "blocked_rows_retain_reason": all(
            row.authorization != ProposalAuthorization.BLOCKED
            or bool(row.missing_operator_ids)
            or row.task_pattern_id is None
            or not row.policy_contract_available
            or row.renderer_profile_count < 4
            or not row.evidence_role_contract_match
            or not row.operation_dag_contract_match
            or not row.parameter_contract_match
            or not row.answer_schema_contract_match
            or not row.semantic_constraint_contract_match
            or not row.renderer_intent_contract_match
            or not row.quality_profile_contract_match
            for row in rows_tuple
        ),
    }
    audit_payload: dict[str, Any] = {
        "source_module_sha256": RAW_GRAPH_PATTERNS_SHA256,
        "proposal_ids": tuple(item.proposal_id for item in proposals),
        "rows": rows_tuple,
        "authorized_count": authorized,
        "blocked_count": len(rows_tuple) - authorized,
        "imported_qa_row_count": 0,
        "gates": gates,
        "schema_version": "raw_proposal_migration_audit.v1",
    }
    audit_id = canonical_hash(
        {
            **audit_payload,
            "rows": [row.model_dump(mode="json") for row in rows_tuple],
        },
        prefix="raw_proposal_migration_audit:",
    )
    return RawProposalMigrationAudit(audit_id=audit_id, **audit_payload)


def _evidence_role_contract_matches(
    proposal: SemanticTaskProposal,
    pattern: TaskPatternSpec,
) -> bool:
    proposal_roles = tuple(
        (
            role.role_id,
            role.accepted_kinds,
            role.min_count,
            role.max_count,
            role.semantic_constraints,
            role.temporal_constraints,
            role.scope_constraints,
        )
        for role in proposal.evidence_roles
    )
    pattern_roles = tuple(
        (
            role.role_id,
            tuple(kind.value for kind in role.accepted_kinds),
            role.min_count,
            role.max_count,
            role.semantic_constraints,
            role.temporal_constraints,
            role.scope_constraints,
        )
        for role in pattern.evidence_roles
    )
    return proposal_roles == pattern_roles


def _operation_dag_contract_matches(
    proposal: SemanticTaskProposal,
    pattern: TaskPatternSpec,
) -> bool:
    proposal_nodes = tuple(
        {
            "node_role_id": node.node_role_id,
            "operator_id": node.operator_id,
            "inputs": tuple((item.kind, item.ref_id, item.selector) for item in node.inputs),
            "output_schema": node.output_schema,
            "foreach_evidence_role": node.foreach_evidence_role,
        }
        for node in proposal.operations
    )
    pattern_nodes = tuple(
        {
            "node_role_id": node.node_role_id,
            "operator_id": node.operator_id,
            "inputs": tuple(
                (item.kind.value, item.ref_id, item.selector) for item in node.input_refs
            ),
            "output_schema": node.output_schema,
            "foreach_evidence_role": node.foreach_evidence_role,
        }
        for node in pattern.program_template
    )
    return proposal.output_node_role_id == pattern.output_node_role_id and (
        proposal_nodes == pattern_nodes
    )


def _parameter_contract_matches(
    proposal: SemanticTaskProposal,
    pattern: TaskPatternSpec,
) -> bool:
    proposal_parameters = {
        node.node_role_id: node.parameters for node in proposal.operations if node.parameters
    }
    pattern_parameters = {
        node.node_role_id: node.parameters for node in pattern.program_template if node.parameters
    }
    if proposal_parameters == pattern_parameters:
        return True
    dynamic = pattern.metadata.get("dynamic_node_parameters")
    return (
        proposal_parameters == {"result": {"registered_pair_from_binding": True}}
        and isinstance(dynamic, dict)
        and set(dynamic) == {"result"}
        and tuple(dynamic["result"]) == ("registered_pair",)
    )


def _role(
    role_id: str,
    accepted_kinds: tuple[str, ...],
    *,
    min_count: int = 1,
    max_count: int | None = 1,
) -> ProposalEvidenceRole:
    return ProposalEvidenceRole(
        role_id=role_id,
        accepted_kinds=accepted_kinds,
        min_count=min_count,
        max_count=max_count,
        semantic_constraints=("finance_evidence_valid",),
    )


def _operation(
    node_role_id: str,
    operator_id: str,
    evidence_roles: tuple[str, ...],
    output_schema: str,
    parameters: dict[str, object],
) -> ProposalOperation:
    return ProposalOperation(
        node_role_id=node_role_id,
        operator_id=operator_id,
        inputs=tuple(
            ProposalInput(kind="evidence_role", ref_id=role_id) for role_id in evidence_roles
        ),
        parameters=parameters,
        output_schema=output_schema,
    )
