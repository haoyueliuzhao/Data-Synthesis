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
    generation_methods = Counter(str(row["generation_method"]) for row in samples)
    instruction_surfaces = Counter(
        str(
            json_value(row.get("generation_metadata"), {}).get(
                "instruction_surface_form_id"
            )
            or "unknown"
        )
        for row in samples
    )
    discourse_styles = Counter(
        str(
            (
                json_value(row.get("generation_metadata"), {}).get(
                    "discourse_plan"
                )
                or {}
            ).get("style_id")
            or "unknown"
        )
        for row in samples
    )
    transition_sequences = Counter(
        "->".join(
            str(value)
            for value in (
                (
                    json_value(row.get("generation_metadata"), {}).get(
                        "discourse_plan"
                    )
                    or {}
                ).get("transition_ids")
                or []
            )
        )
        for row in samples
    )
    numeric_mention_counts = Counter(
        sum(
            len(values or [])
            for values in (
                (
                    json_value(row.get("generation_metadata"), {}).get(
                        "discourse_plan"
                    )
                    or {}
                ).get("selected_numeric_slot_ids")
                or {}
            ).values()
        )
        for row in samples
    )
    valid_conclusion_counts = Counter(
        len(json_value(row.get("valid_conclusion_set"), [])) for row in plans
    )
    unique_text_count = len({str(row.get("analysis_text") or "") for row in samples})
    unique_instruction_count = len(
        {str(row.get("instruction") or "") for row in samples}
    )
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
        "generation_method_distribution": dict(sorted(generation_methods.items())),
        "instruction_surface_distribution": dict(sorted(instruction_surfaces.items())),
        "discourse_style_distribution": dict(sorted(discourse_styles.items())),
        "transition_sequence_distribution": dict(
            sorted(transition_sequences.items())
        ),
        "numeric_mention_count_distribution": {
            str(key): value for key, value in sorted(numeric_mention_counts.items())
        },
        "valid_conclusion_count_distribution": {
            str(key): value for key, value in sorted(valid_conclusion_counts.items())
        },
        "unique_analysis_text_count": unique_text_count,
        "analysis_text_uniqueness_rate": unique_text_count / len(samples)
        if samples
        else 0,
        "unique_instruction_count": unique_instruction_count,
        "instruction_uniqueness_rate": unique_instruction_count / len(samples)
        if samples
        else 0,
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
