from __future__ import annotations

from trusted_synthesis.core.trajectory.schema import ActionType
from trusted_synthesis.runtime.tools import (
    AgentToolEnvironmentManifest,
    AgentToolSpec,
    make_agent_tool_environment_manifest,
)

FINANCE_ARCHIVE_AGENT_TOOLSET_VERSION = "finance_archive_agent_toolset.v1"


def finance_archive_agent_tool_specs() -> tuple[AgentToolSpec, ...]:
    """Public tool contracts; Finance implementations remain Host-owned and snapshot-bound."""

    return (
        AgentToolSpec(
            tool_id="search_archive",
            tool_version=FINANCE_ARCHIVE_AGENT_TOOLSET_VERSION,
            semantic_role="acquire",
            trajectory_action=ActionType.SEARCH,
            description="Search the frozen financial Archive using public text and typed filters.",
            input_contract={
                "query": "string",
                "subject_aliases": "array[string]",
                "period_labels": "array[string]",
                "source_filters": "array[string]",
                "limit": "integer",
            },
            output_contract={
                "matches": "array[public evidence summary]",
                "query_hash": "string",
                "snapshot_hash": "string",
            },
            required_input_fields=("query", "limit"),
            required_output_fields=("matches", "query_hash", "snapshot_hash"),
        ),
        AgentToolSpec(
            tool_id="open_document",
            tool_version=FINANCE_ARCHIVE_AGENT_TOOLSET_VERSION,
            semantic_role="inspect",
            trajectory_action=ActionType.SELECT_EVIDENCE,
            description="Open a document or Evidence item returned by the frozen Archive search.",
            input_contract={
                "public_locator": "string",
                "section_or_page": "string|null",
            },
            output_contract={
                "content": "typed public content",
                "evidence_ids": "array[string]",
                "source_locator_hash": "string",
            },
            required_input_fields=("public_locator",),
            required_output_fields=("content", "evidence_ids", "source_locator_hash"),
        ),
        AgentToolSpec(
            tool_id="query_structured_fact",
            tool_version=FINANCE_ARCHIVE_AGENT_TOOLSET_VERSION,
            semantic_role="query",
            trajectory_action=ActionType.SELECT_EVIDENCE,
            description="Query frozen structured facts without accepting hidden Gold identifiers.",
            input_contract={
                "subject_alias": "string",
                "metric_alias": "string",
                "period_label": "string",
                "public_filters": "object",
            },
            output_contract={
                "facts": "array[typed public fact]",
                "evidence_ids": "array[string]",
                "query_hash": "string",
            },
            required_input_fields=(
                "subject_alias",
                "metric_alias",
                "period_label",
                "public_filters",
            ),
            required_output_fields=("facts", "evidence_ids", "query_hash"),
        ),
        AgentToolSpec(
            tool_id="calculator",
            tool_version=FINANCE_ARCHIVE_AGENT_TOOLSET_VERSION,
            semantic_role="calculate",
            trajectory_action=ActionType.CALCULATE,
            description="Execute a registered deterministic arithmetic operation on public inputs.",
            input_contract={
                "operator": "registered operator ID",
                "operands": "array[number or public step reference]",
                "parameters": "object",
            },
            output_contract={
                "result": "typed numeric result",
                "operation_hash": "string",
            },
            required_input_fields=("operator", "operands", "parameters"),
            required_output_fields=("result", "operation_hash"),
        ),
        AgentToolSpec(
            tool_id="normalize_metric_unit_period",
            tool_version=FINANCE_ARCHIVE_AGENT_TOOLSET_VERSION,
            semantic_role="normalize",
            trajectory_action=ActionType.CALCULATE,
            description=(
                "Apply the frozen Finance policy for metric definition, unit, currency, and "
                "period alignment."
            ),
            input_contract={
                "evidence_ids": "array[string]",
                "target_definition": "object",
            },
            output_contract={
                "normalized_values": "array[typed value]",
                "compatibility_report": "object",
                "policy_hash": "string",
            },
            required_input_fields=("evidence_ids", "target_definition"),
            required_output_fields=(
                "normalized_values",
                "compatibility_report",
                "policy_hash",
            ),
        ),
        AgentToolSpec(
            tool_id="cross_check_evidence",
            tool_version=FINANCE_ARCHIVE_AGENT_TOOLSET_VERSION,
            semantic_role="verify",
            trajectory_action=ActionType.VERIFY,
            description=(
                "Cross-check selected Evidence and return a replayable verification report."
            ),
            input_contract={
                "evidence_ids": "array[string]",
                "claim_or_result": "object",
            },
            output_contract={
                "verified": "boolean",
                "support": "array[string]",
                "conflicts": "array[object]",
                "verification_hash": "string",
            },
            required_input_fields=("evidence_ids", "claim_or_result"),
            required_output_fields=(
                "verified",
                "support",
                "conflicts",
                "verification_hash",
            ),
        ),
    )


def make_finance_archive_agent_tool_manifest(
    *,
    environment_id: str,
    corpus_id: str,
    corpus_hash: str,
    archive_snapshot_id: str,
    archive_snapshot_hash: str,
    maximum_tool_calls: int = 12,
    maximum_failed_tool_calls: int = 3,
    maximum_total_observation_bytes: int = 1_000_000,
    tool_timeout_seconds: float = 30.0,
) -> AgentToolEnvironmentManifest:
    return make_agent_tool_environment_manifest(
        environment_id=environment_id,
        corpus_id=corpus_id,
        corpus_hash=corpus_hash,
        snapshot_id=archive_snapshot_id,
        snapshot_hash=archive_snapshot_hash,
        network_policy="forbidden",
        tools=finance_archive_agent_tool_specs(),
        maximum_tool_calls=maximum_tool_calls,
        maximum_failed_tool_calls=maximum_failed_tool_calls,
        maximum_total_observation_bytes=maximum_total_observation_bytes,
        tool_timeout_seconds=tool_timeout_seconds,
    )
