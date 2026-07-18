from __future__ import annotations

import json
import math
from collections import Counter
from pathlib import Path
from typing import Any

from finraw.db.client import DBProtocol
from finraw.qa.store import json_value


def build_analysis_diversity_report(
    db: DBProtocol,
    analysis_build_id: str,
    *,
    output_dir: str | None = None,
) -> dict[str, Any]:
    candidates = [
        dict(row)
        for row in db.fetchall(
            "SELECT * FROM analysis_candidates WHERE analysis_build_id = ?",
            (analysis_build_id,),
        )
    ]
    signals = [
        dict(row)
        for row in db.fetchall(
            "SELECT * FROM financial_signal_instances WHERE analysis_build_id = ?",
            (analysis_build_id,),
        )
    ]
    plans = [
        dict(row)
        for row in db.fetchall(
            "SELECT * FROM analysis_claim_plans WHERE analysis_build_id = ?",
            (analysis_build_id,),
        )
    ]
    samples = [
        dict(row)
        for row in db.fetchall(
            "SELECT * FROM analysis_samples WHERE analysis_build_id = ? AND validation_status = 'passed'",
            (analysis_build_id,),
        )
    ]
    pattern_counts = Counter(str(row["analysis_pattern_id"]) for row in candidates)
    signal_counts = Counter(str(row["signal_spec_id"]) for row in signals)
    direction_counts = Counter(str(row["direction"]) for row in signals)
    strength_counts = Counter(str(row["strength"]) for row in signals)
    claim_types = Counter(
        str(claim.get("claim_type"))
        for row in plans
        for claim in json_value(row["claim_graph"], [])
    )
    conclusions = Counter(str(row["selected_conclusion_id"]) for row in samples)
    splits = Counter(str(row["split"]) for row in samples)
    signal_compositions = Counter(str(row["signal_composition_id"]) for row in samples)
    report = {
        "analysis_build_id": analysis_build_id,
        "candidate_count": len(candidates),
        "signal_count": len(signals),
        "sample_count": len(samples),
        "analysis_pattern_distribution": dict(sorted(pattern_counts.items())),
        "signal_type_distribution": dict(sorted(signal_counts.items())),
        "signal_direction_distribution": dict(sorted(direction_counts.items())),
        "signal_strength_distribution": dict(sorted(strength_counts.items())),
        "signal_composition_count": len(signal_compositions),
        "signal_composition_entropy": _entropy(signal_compositions),
        "claim_type_distribution": dict(sorted(claim_types.items())),
        "conclusion_distribution": dict(sorted(conclusions.items())),
        "split_distribution": dict(sorted(splits.items())),
        "largest_pattern_share": max(pattern_counts.values(), default=0) / len(candidates) if candidates else 0,
    }
    if output_dir:
        directory = Path(output_dir)
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / "financial_analysis_diversity_report.json"
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
        report["written_file"] = str(path)
    return report


def _entropy(counter: Counter[str]) -> float:
    total = sum(counter.values())
    if not total:
        return 0.0
    return round(-sum((count / total) * math.log2(count / total) for count in counter.values()), 6)
