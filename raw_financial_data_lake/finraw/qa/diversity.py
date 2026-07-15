from __future__ import annotations

import json
import math
from collections import Counter
from pathlib import Path
from typing import Any

from finraw.db.client import DBProtocol
from finraw.qa.schema import ensure_qa_schema
from finraw.qa.store import json_value


def build_qa_diversity_report(
    db: DBProtocol,
    qa_build_id: str,
    *,
    output_dir: str | None = None,
) -> dict[str, Any]:
    ensure_qa_schema(db)
    build_row = db.fetchone(
        "SELECT * FROM qa_builds WHERE qa_build_id = ?", (qa_build_id,)
    )
    if not build_row:
        raise RuntimeError(f"Unknown QA build: {qa_build_id}")
    build = dict(build_row)
    candidates = [
        _decode_candidate(dict(row))
        for row in db.fetchall(
            "SELECT * FROM qa_candidates WHERE qa_build_id = ?", (qa_build_id,)
        )
    ]
    plans = {
        str(row["candidate_id"]): json_value(row["operator_dag"], {})
        for row in db.fetchall(
            "SELECT candidate_id, operator_dag FROM qa_operation_plans WHERE qa_build_id = ?",
            (qa_build_id,),
        )
    }
    for candidate in candidates:
        candidate["operation_plan"] = plans.get(str(candidate["candidate_id"]), {})
    samples = [
        dict(row)
        for row in db.fetchall(
            "SELECT template_id, task_subtype, difficulty, answer_type, split FROM qa_samples WHERE qa_build_id = ?",
            (qa_build_id,),
        )
    ]
    pattern_counts = Counter(
        str(row.get("pattern_id") or "legacy_fact_or_derived") for row in candidates
    )
    operation_counts = Counter(
        _operation_signature(row.get("operation_plan")) for row in candidates
    )
    intent_counts = Counter(
        str(row.get("question_intent") or "legacy_default") for row in candidates
    )
    difficulty_counts = Counter(str(row.get("difficulty") or "unknown") for row in candidates)
    answer_type_counts = Counter(str(row.get("answer_schema", {}).get("type") or "legacy") for row in candidates)
    template_counts = Counter(str(row.get("template_id") or "none") for row in samples)
    task_counts = Counter(str(row.get("task_subtype") or "unknown") for row in samples)
    split_counts = Counter(str(row.get("split") or "unassigned") for row in samples)

    used_fact_ids = {
        str(fact_id)
        for row in candidates
        if row.get("eligibility_status") == "eligible"
        for fact_id in row.get("source_fact_ids", [])
    }
    used_derived_ids = {
        str(derived_id)
        for row in candidates
        if row.get("eligibility_status") == "eligible"
        for derived_id in row.get("source_derived_ids", [])
    }
    used_edge_types = {
        str(edge.get("relation_type") or edge.get("relation"))
        for row in candidates
        for edge in row.get("kg_path", {}).get("evidence_edges", [])
        if edge.get("relation_type") or edge.get("relation")
    }
    total_fact_nodes = _scalar(
        db,
        "SELECT COUNT(*) AS c FROM kg_nodes WHERE kg_build_id = ? AND node_type = 'Fact'",
        [build["kg_build_id"]],
    )
    total_derived_nodes = _scalar(
        db,
        "SELECT COUNT(*) AS c FROM kg_nodes WHERE kg_build_id = ? AND node_type = 'DerivedFact'",
        [build["kg_build_id"]],
    )
    total_edge_types = {
        str(row["relation_type"])
        for row in db.fetchall(
            "SELECT DISTINCT relation_type FROM kg_edges WHERE kg_build_id = ?",
            (build["kg_build_id"],),
        )
    }
    eligible = [row for row in candidates if row.get("eligibility_status") == "eligible"]
    feature_rows = [row for row in eligible if row.get("graph_features")]
    avg_nodes = _average(
        len(row.get("kg_path", {}).get("evidence_node_ids") or row.get("kg_path", {}).get("node_ids") or [])
        for row in eligible
    )
    avg_edges = _average(len(row.get("kg_path", {}).get("edge_ids") or []) for row in eligible)
    avg_hops = _average(float(row["graph_features"].get("graph_hop_depth", 0)) for row in feature_rows)
    avg_branches = _average(float(row["graph_features"].get("branch_count", 0)) for row in feature_rows)
    report = {
        "qa_build_id": qa_build_id,
        "kg_build_id": build["kg_build_id"],
        "candidate_count": len(candidates),
        "eligible_candidate_count": len(eligible),
        "sample_count": len(samples),
        "semantic_diversity": {
            "unique_graph_patterns": len(pattern_counts),
            "unique_operation_plans": len(operation_counts),
            "graph_pattern_counts": dict(sorted(pattern_counts.items())),
            "operation_plan_counts": dict(sorted(operation_counts.items())),
            "question_intent_counts": dict(sorted(intent_counts.items())),
            "difficulty_counts": dict(sorted(difficulty_counts.items())),
            "answer_type_counts": dict(sorted(answer_type_counts.items())),
            "task_counts": dict(sorted(task_counts.items())),
            "split_counts": dict(sorted(split_counts.items())),
            "task_pattern_entropy": _entropy(pattern_counts),
            "largest_pattern_share": _largest_share(pattern_counts),
            "largest_template_share": _largest_share(template_counts),
        },
        "kg_utilization": {
            "used_fact_nodes": len(used_fact_ids),
            "total_fact_nodes": total_fact_nodes,
            "fact_node_utilization": len(used_fact_ids) / total_fact_nodes if total_fact_nodes else 0.0,
            "used_derived_nodes": len(used_derived_ids),
            "total_derived_nodes": total_derived_nodes,
            "derived_node_utilization": len(used_derived_ids) / total_derived_nodes if total_derived_nodes else 0.0,
            "used_edge_types": sorted(used_edge_types),
            "total_edge_types": sorted(total_edge_types),
            "edge_type_coverage": len(used_edge_types & total_edge_types) / len(total_edge_types) if total_edge_types else 0.0,
            "average_evidence_nodes": avg_nodes,
            "average_evidence_edges": avg_edges,
            "graph_feature_candidate_count": len(feature_rows),
            "graph_feature_coverage": len(feature_rows) / len(eligible) if eligible else 0.0,
            "average_graph_hop_depth": avg_hops,
            "average_branch_count": avg_branches,
        },
    }
    if output_dir:
        report["written_files"] = _write_report(report, output_dir)
    return report


def _decode_candidate(row: dict[str, Any]) -> dict[str, Any]:
    for key, default in {
        "source_fact_ids": [],
        "source_derived_ids": [],
        "kg_path": {},
        "graph_features": {},
        "answer_schema": {},
        "operation_plan": {},
    }.items():
        row[key] = json_value(row.get(key), default)
    return row


def _operation_signature(plan: dict[str, Any] | None) -> str:
    operators = [str(step.get("operator")) for step in (plan or {}).get("operators", [])]
    return " -> ".join(operators) if operators else "legacy_direct"


def _entropy(counts: Counter[str]) -> float:
    total = sum(counts.values())
    if not total:
        return 0.0
    return round(-sum((count / total) * math.log2(count / total) for count in counts.values()), 6)


def _largest_share(counts: Counter[str]) -> float:
    total = sum(counts.values())
    return max(counts.values(), default=0) / total if total else 0.0


def _average(values: Any) -> float:
    rows = list(values)
    return sum(rows) / len(rows) if rows else 0.0


def _scalar(db: DBProtocol, sql: str, params: list[Any]) -> int:
    row = db.fetchone(sql, params)
    return int(row["c"] if row else 0)


def _write_report(report: dict[str, Any], output_dir: str) -> list[str]:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    json_path = out / "qa_diversity_report.json"
    md_path = out / "qa_diversity_report.md"
    json_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )
    semantic = report["semantic_diversity"]
    usage = report["kg_utilization"]
    lines = [
        "# QA Diversity and KG Utilization Report",
        "",
        f"- QA build: `{report['qa_build_id']}`",
        f"- KG build: `{report['kg_build_id']}`",
        f"- Candidates / eligible / samples: `{report['candidate_count']} / {report['eligible_candidate_count']} / {report['sample_count']}`",
        f"- Unique graph patterns: `{semantic['unique_graph_patterns']}`",
        f"- Unique operation plans: `{semantic['unique_operation_plans']}`",
        f"- Pattern entropy: `{semantic['task_pattern_entropy']}`",
        f"- Fact node utilization: `{usage['fact_node_utilization']:.6f}`",
        f"- Derived node utilization: `{usage['derived_node_utilization']:.6f}`",
        f"- Edge type coverage: `{usage['edge_type_coverage']:.6f}`",
        "",
        "## Graph Pattern Counts",
        "",
    ]
    lines.extend(f"- `{key}`: `{value}`" for key, value in semantic["graph_pattern_counts"].items())
    lines.extend(["", "## Difficulty Counts", ""])
    lines.extend(f"- `{key}`: `{value}`" for key, value in semantic["difficulty_counts"].items())
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return [str(json_path), str(md_path)]
