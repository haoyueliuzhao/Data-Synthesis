from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path
from typing import Any

from finraw.db.client import DBProtocol
from finraw.kg_query import resolve_kg_build_id
from finraw.qa.graph_matcher import discover_pattern_matches
from finraw.qa.graph_patterns import get_pattern


def profile_graph_patterns(
    db: DBProtocol,
    config: dict[str, Any],
    *,
    kg_build_id: str | None = None,
    limit_per_pattern: int = 500,
    output_dir: str | None = None,
) -> dict[str, Any]:
    resolved = resolve_kg_build_id(db, kg_build_id)
    kg_row = db.fetchone(
        "SELECT * FROM kg_builds WHERE kg_build_id = ?", (resolved,)
    )
    if not kg_row:
        raise RuntimeError(f"Unknown KG build: {resolved}")
    kg = dict(kg_row)
    graph_config = config.get("qa", {}).get("graph_patterns", {})
    configured_quotas = graph_config.get("quotas", {})
    results = []
    total_matches = 0
    for pattern_id in sorted(configured_quotas):
        pattern = get_pattern(pattern_id)
        if not pattern.is_active or not pattern.matcher:
            continue
        requested = min(
            max(int(configured_quotas.get(pattern_id) or 0), 0),
            max(int(limit_per_pattern), 0),
        )
        if requested <= 0:
            continue
        started = time.perf_counter()
        status = "passed"
        error = None
        try:
            matches = discover_pattern_matches(
                db,
                kg,
                pattern_id,
                limit=requested,
                policy=graph_config.get("comparability"),
            )
        except Exception as exc:
            matches = []
            status = "failed"
            error = f"{type(exc).__name__}: {exc}"
        elapsed = time.perf_counter() - started
        total_matches += len(matches)
        results.append(
            {
                "pattern_id": pattern_id,
                "pattern_version": pattern.pattern_version,
                "matcher": pattern.matcher,
                "requested_limit": requested,
                "match_count": len(matches),
                "fill_rate": len(matches) / requested if requested else 0.0,
                "elapsed_seconds": round(elapsed, 6),
                "matches_per_second": round(len(matches) / elapsed, 3)
                if elapsed
                else None,
                "status": status,
                "error": error,
                "entity_type_count": len(
                    {
                        str(match.get("comparability", {}).get("entity_type"))
                        for match in matches
                        if match.get("comparability", {}).get("entity_type")
                    }
                ),
                "metric_counts": dict(
                    sorted(
                        Counter(
                            metric_id
                            for match in matches
                            for metric_id in match.get("metric_ids", [])
                        ).items()
                    )
                ),
                "scope_type_counts": dict(
                    sorted(
                        Counter(
                            str(match.get("scope_type") or "unspecified")
                            for match in matches
                        ).items()
                    )
                ),
                "frequency_counts": dict(
                    sorted(
                        Counter(
                            str(match.get("frequency") or "unspecified")
                            for match in matches
                        ).items()
                    )
                ),
            }
        )
    report = {
        "kg_build_id": resolved,
        "fact_build_id": kg.get("input_fact_build_id"),
        "pattern_count": len(results),
        "total_match_count": total_matches,
        "failed_pattern_count": sum(row["status"] == "failed" for row in results),
        "patterns": results,
    }
    if output_dir:
        report["written_files"] = _write_report(report, output_dir)
    return report


def _write_report(report: dict[str, Any], output_dir: str) -> list[str]:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    json_path = out / "qa_graph_pattern_preflight.json"
    md_path = out / "qa_graph_pattern_preflight.md"
    json_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    lines = [
        "# QA Graph Pattern Preflight",
        "",
        f"- KG build: `{report['kg_build_id']}`",
        f"- Fact build: `{report['fact_build_id']}`",
        f"- Patterns / matches / failures: `{report['pattern_count']} / {report['total_match_count']} / {report['failed_pattern_count']}`",
        "",
        "| Pattern | Version | Matches | Fill rate | Seconds | Status |",
        "| --- | ---: | ---: | ---: | ---: | --- |",
    ]
    for row in report["patterns"]:
        lines.append(
            f"| {row['pattern_id']} | {row['pattern_version']} | {row['match_count']} | "
            f"{row['fill_rate']:.3f} | {row['elapsed_seconds']:.3f} | {row['status']} |"
        )
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return [str(json_path), str(md_path)]
