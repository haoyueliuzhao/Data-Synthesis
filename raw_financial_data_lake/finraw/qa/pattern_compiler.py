from __future__ import annotations

from typing import Any

from finraw.qa.graph_patterns import GraphPattern
from finraw.qa.store import json_value


def compile_pattern_proposal(proposal: dict[str, Any]) -> GraphPattern:
    if proposal.get("status") != "approved":
        raise ValueError(
            f"Only approved pattern proposals can be compiled: {proposal.get('proposal_id')}"
        )
    spec = json_value(proposal.get("pattern_spec"), {})
    if not spec.get("operator_template"):
        raise ValueError("Pattern proposal has no executable operator template")
    pattern_id = "mined_" + str(proposal["motif_signature"])[:20]
    return GraphPattern(
        pattern_id=pattern_id,
        pattern_version=int(spec.get("pattern_version", 1)),
        pattern_family=str(spec["pattern_family"]),
        task_subtype=str(spec["task_subtype"]),
        matcher=None,
        node_constraints=list(spec.get("node_constraints") or []),
        edge_constraints=list(spec.get("edge_constraints") or []),
        semantic_constraints=list(spec.get("semantic_constraints") or []),
        operator_template=dict(spec["operator_template"]),
        answer_schema=dict(spec.get("answer_schema") or {}),
        difficulty_base=str(spec.get("difficulty_base") or "hard"),
        question_intents=tuple(
            spec.get("question_intents") or ["mined_financial_analysis"]
        ),
        is_active=True,
    )


def compile_proposal_matches(
    proposal: dict[str, Any], *, limit: int
) -> list[dict[str, Any]]:
    pattern = compile_pattern_proposal(proposal)
    examples = json_value(proposal.get("binding_examples"), [])
    output = []
    for example in examples[: max(limit, 0)]:
        row = dict(example)
        row["pattern_id"] = pattern.pattern_id
        row["pattern_proposal_id"] = proposal["proposal_id"]
        row["mining_run_id"] = proposal["mining_run_id"]
        row["pattern_proposal_hash"] = proposal["proposal_hash"]
        row["pattern_score"] = float(proposal["total_score"])
        output.append(row)
    return output
