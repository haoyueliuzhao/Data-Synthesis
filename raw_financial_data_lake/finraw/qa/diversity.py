from __future__ import annotations

import hashlib
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
            """
            SELECT candidate_id, template_id, task_subtype, difficulty, answer_type,
                   validation_status, split
            FROM qa_samples WHERE qa_build_id = ?
            """,
            (qa_build_id,),
        )
    ]
    by_candidate = {str(row["candidate_id"]): row for row in candidates}
    eligible = [row for row in candidates if row.get("eligibility_status") == "eligible"]
    validated_samples = [
        row for row in samples if row.get("validation_status") == "passed"
    ]
    exported_samples = [row for row in validated_samples if row.get("split")]
    validated_candidates = _candidates_for_samples(validated_samples, by_candidate)
    exported_candidates = _candidates_for_samples(exported_samples, by_candidate)
    funnels = {
        "all_candidates": _funnel(candidates, []),
        "eligible_candidates": _funnel(eligible, []),
        "validated_samples": _funnel(validated_candidates, validated_samples),
        "exported_samples": _funnel(exported_candidates, exported_samples),
    }

    semantic = funnels["eligible_candidates"]
    template_counts = Counter(
        str(row.get("template_id") or "none") for row in exported_samples or samples
    )
    used_fact_ids = {
        str(fact_id) for row in eligible for fact_id in row.get("source_fact_ids", [])
    }
    used_derived_ids = {
        str(derived_id)
        for row in eligible
        for derived_id in row.get("source_derived_ids", [])
    }
    used_edge_types = {
        str(edge.get("relation_type") or edge.get("relation"))
        for row in eligible
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
    feature_rows = [row for row in eligible if row.get("graph_features")]
    avg_nodes = _average(
        len(
            row.get("kg_path", {}).get("evidence_node_ids")
            or row.get("kg_path", {}).get("node_ids")
            or []
        )
        for row in eligible
    )
    avg_edges = _average(
        len(row.get("kg_path", {}).get("edge_ids") or []) for row in eligible
    )
    report = {
        "qa_build_id": qa_build_id,
        "kg_build_id": build["kg_build_id"],
        "candidate_count": len(candidates),
        "eligible_candidate_count": len(eligible),
        "sample_count": len(samples),
        "validated_sample_count": len(validated_samples),
        "exported_sample_count": len(exported_samples),
        "funnels": funnels,
        "semantic_diversity": {
            "unique_graph_patterns": semantic["unique_graph_patterns"],
            "unique_operation_plans": semantic["unique_operator_sequences"],
            "unique_normalized_plans": semantic["unique_normalized_plan_hashes"],
            "unique_operator_dags": semantic["unique_operator_dag_hashes"],
            "graph_pattern_counts": semantic["graph_pattern_counts"],
            "operation_plan_counts": semantic["operator_sequence_counts"],
            "question_intent_counts": semantic["question_intent_counts"],
            "difficulty_counts": semantic["difficulty_counts"],
            "answer_type_counts": semantic["answer_type_counts"],
            "task_counts": funnels["exported_samples"]["task_counts"],
            "split_counts": funnels["exported_samples"]["split_counts"],
            "task_pattern_entropy": semantic["pattern_entropy"],
            "largest_pattern_share": semantic["largest_pattern_share"],
            "largest_template_share": _largest_share(template_counts),
        },
        "kg_utilization": {
            "population": "eligible_candidates",
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
            "average_reasoning_graph_hop_depth": _average(
                float(row["graph_features"].get("reasoning_graph_hop_depth", 0))
                for row in feature_rows
            ),
            "average_provenance_graph_depth": _average(
                float(row["graph_features"].get("provenance_graph_depth", 0))
                for row in feature_rows
            ),
            "average_branch_count": _average(
                float(row["graph_features"].get("reasoning_branch_count", 0))
                for row in feature_rows
            ),
        },
    }
    if output_dir:
        report["written_files"] = _write_report(report, output_dir)
    return report


def _funnel(
    candidates: list[dict[str, Any]], samples: list[dict[str, Any]]
) -> dict[str, Any]:
    pattern_counts = Counter(
        str(row.get("pattern_id") or "legacy_fact_or_derived") for row in candidates
    )
    sequences = Counter(_operation_signature(row.get("operation_plan")) for row in candidates)
    normalized_hashes = Counter(
        _plan_hash(row.get("operation_plan"), include_params=False) for row in candidates
    )
    dag_hashes = Counter(
        _plan_hash(row.get("operation_plan"), include_params=True) for row in candidates
    )
    return {
        "candidate_count": len(candidates),
        "sample_count": len(samples),
        "unique_graph_patterns": len(pattern_counts),
        "unique_operator_sequences": len(sequences),
        "unique_normalized_plan_hashes": len(normalized_hashes),
        "unique_operator_dag_hashes": len(dag_hashes),
        "graph_pattern_counts": dict(sorted(pattern_counts.items())),
        "operator_sequence_counts": dict(sorted(sequences.items())),
        "question_intent_counts": dict(
            sorted(Counter(str(row.get("question_intent") or "legacy_default") for row in candidates).items())
        ),
        "difficulty_counts": dict(
            sorted(Counter(str(row.get("difficulty") or "unknown") for row in candidates).items())
        ),
        "answer_type_counts": dict(
            sorted(
                Counter(
                    str(row.get("answer_schema", {}).get("type") or "legacy")
                    for row in candidates
                ).items()
            )
        ),
        "task_counts": dict(
            sorted(Counter(str(row.get("task_subtype") or "unknown") for row in samples).items())
        ),
        "split_counts": dict(
            sorted(Counter(str(row.get("split") or "unassigned") for row in samples).items())
        ),
        "pattern_entropy": _entropy(pattern_counts),
        "largest_pattern_share": _largest_share(pattern_counts),
    }


def _candidates_for_samples(
    samples: list[dict[str, Any]], by_candidate: dict[str, dict[str, Any]]
) -> list[dict[str, Any]]:
    ids = {str(row["candidate_id"]) for row in samples}
    return [by_candidate[candidate_id] for candidate_id in sorted(ids) if candidate_id in by_candidate]


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


def _plan_hash(plan: dict[str, Any] | None, *, include_params: bool) -> str:
    if not plan:
        return "legacy_direct"
    normalized = {
        "operators": [
            {
                "step_id": step.get("step_id"),
                "operator": step.get("operator"),
                "inputs": step.get("inputs") or [],
                **({"params": step.get("params") or {}} if include_params else {}),
            }
            for step in plan.get("operators", [])
        ],
        "output_step": plan.get("output_step"),
    }
    payload = json.dumps(normalized, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


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
        f"- Candidates / eligible / validated / exported: `{report['candidate_count']} / {report['eligible_candidate_count']} / {report['validated_sample_count']} / {report['exported_sample_count']}`",
        f"- Unique graph patterns: `{semantic['unique_graph_patterns']}`",
        f"- Operator sequences / normalized plans / DAGs: `{semantic['unique_operation_plans']} / {semantic['unique_normalized_plans']} / {semantic['unique_operator_dags']}`",
        f"- Pattern entropy: `{semantic['task_pattern_entropy']}`",
        f"- Fact node utilization: `{usage['fact_node_utilization']:.6f}`",
        f"- Derived node utilization: `{usage['derived_node_utilization']:.6f}`",
        f"- Edge type coverage: `{usage['edge_type_coverage']:.6f}`",
        "",
        "## Funnel",
        "",
    ]
    for name, funnel in report["funnels"].items():
        lines.append(
            f"- `{name}`: candidates={funnel['candidate_count']}, samples={funnel['sample_count']}, patterns={funnel['unique_graph_patterns']}"
        )
    lines.extend(["", "## Graph Pattern Counts", ""])
    lines.extend(f"- `{key}`: `{value}`" for key, value in semantic["graph_pattern_counts"].items())
    lines.extend(["", "## Difficulty Counts", ""])
    lines.extend(f"- `{key}`: `{value}`" for key, value in semantic["difficulty_counts"].items())
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return [str(json_path), str(md_path)]
