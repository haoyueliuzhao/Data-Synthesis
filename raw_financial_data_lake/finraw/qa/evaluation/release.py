from __future__ import annotations

import hashlib
import json
import uuid
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from finraw.db.client import DBProtocol
from finraw.qa.evaluation.dataset_metrics import dataset_role_features
from finraw.qa.evaluation.input_views import load_evaluation_bundles
from finraw.qa.evaluation.schema import ensure_evaluation_schema
from finraw.qa.schema import ensure_qa_schema
from finraw.qa.store import insert_rows, json_value


SELECTION_POLICY_VERSION = "qa_quality_release_selection.v2"
RELEASE_DECISIONS = frozenset({"accepted", "accepted_for_coverage"})
TRAINING_SPLITS = frozenset({"train", "train_complex"})

RELEASE_COLUMNS = [
    "quality_release_id",
    "qa_build_id",
    "evaluation_run_id",
    "selection_policy_version",
    "target_size",
    "distribution_contract",
    "quality_thresholds",
    "member_manifest_hash",
    "status",
    "created_at",
]

MEMBER_COLUMNS = [
    "release_member_id",
    "quality_release_id",
    "qa_id",
    "selection_score",
    "subjective_score",
    "dataset_role_score",
    "novelty_score",
    "selection_stratum",
    "selection_reason",
    "is_selected",
]


def build_quality_release(
    db: DBProtocol,
    evaluation_run_id: str,
    *,
    target_size: int | None = None,
    output_dir: str | None = None,
) -> dict[str, Any]:
    """Build a fail-closed training release from one pinned evaluation run."""
    ensure_qa_schema(db)
    ensure_evaluation_schema(db)
    run = _load_run(db, evaluation_run_id)
    if run["status"] not in {"completed", "partial"}:
        raise RuntimeError(
            f"Evaluation run {evaluation_run_id} is not complete: {run['status']}"
        )
    _assert_immutable_sample_manifest(db, run)

    quality_config = dict((run.get("notes") or {}).get("quality_config") or {})
    calibration = dict(quality_config.get("calibration") or {})
    calibrated = bool(
        calibration.get("thresholds_are_calibrated")
        or (run.get("notes") or {}).get("thresholds_are_calibrated")
    )
    if run["evaluation_mode"] == "release_gate" and not calibrated:
        raise RuntimeError(
            "release_gate requires frozen human-calibrated thresholds"
        )

    selection = dict(quality_config.get("release_selection") or {})
    weights = _normalized_weights(selection)
    minimum_subjective = float(selection.get("minimum_subjective_score", 70))
    no_confirmed_fatal = bool(selection.get("no_confirmed_fatal_flags", True))
    items = _load_items(db, evaluation_run_id)
    bundles = {
        str(row["qa_id"]): row
        for row in load_evaluation_bundles(
            db,
            run["qa_build_id"],
            qa_ids=run["sample_manifest"].get("qa_ids") or [],
        )
    }

    assessed: list[dict[str, Any]] = []
    for item in items:
        qa_id = str(item["qa_id"])
        bundle = bundles.get(qa_id) or {}
        split = str((bundle.get("sample") or {}).get("split") or "")
        components = item.get("dataset_role_components") or {}
        subjective = float(item.get("subjective_quality_score") or 0)
        dataset_role = float(item.get("dataset_role_value_score") or 0)
        novelty = float(components.get("signature_capacity_value") or 0)
        reasons: list[str] = []
        if item.get("deterministic_gate_status") != "passed":
            reasons.append("deterministic_gate_not_passed")
        if item.get("decision") not in RELEASE_DECISIONS:
            reasons.append(f"decision_not_release_eligible:{item.get('decision')}")
        if split not in TRAINING_SPLITS:
            reasons.append(f"evaluation_holdout_split:{split or 'unknown'}")
        if not _training_release_eligible(item):
            reasons.append("dataset_role_training_release_ineligible")
        if subjective < minimum_subjective:
            reasons.append("subjective_score_below_release_minimum")
        if no_confirmed_fatal and item.get("confirmed_fatal_flags"):
            reasons.append("confirmed_fatal_flags_present")
        selection_score = (
            weights["subjective"] * subjective
            + weights["dataset_role"] * dataset_role
            + weights["novelty"] * novelty
        )
        assessed.append(
            {
                "qa_id": qa_id,
                "selection_score": round(selection_score, 6),
                "subjective_score": subjective,
                "dataset_role_score": dataset_role,
                "novelty_score": novelty,
                "selection_stratum": _selection_stratum(bundle),
                "distribution_features": dataset_role_features(bundle),
                "eligible": not reasons,
                "reasons": reasons or ["all_release_gates_passed"],
            }
        )

    eligible = sorted(
        (row for row in assessed if row["eligible"]),
        key=lambda row: (-row["selection_score"], row["qa_id"]),
    )
    configured_target = int(
        (run.get("notes") or {})
        .get("dataset_role_contract", {})
        .get("target_release_count", 0)
        or 0
    )
    requested_target = target_size if target_size is not None else configured_target
    if requested_target is not None and requested_target < 0:
        raise ValueError("target_size must be zero or positive")
    effective_target = int(requested_target or len(eligible))
    distribution_contract = (run.get("notes") or {}).get(
        "dataset_role_contract", {}
    )
    quota_result = _select_with_distribution_quotas(
        eligible,
        distribution_contract,
        effective_target,
        selection,
    )
    selected = quota_result["selected"]
    selected_ids = {row["qa_id"] for row in selected}
    selection_ranks = {
        row["qa_id"]: rank for rank, row in enumerate(selected, start=1)
    }

    quality_release_id = _release_id()
    members = []
    for row in sorted(assessed, key=lambda value: value["qa_id"]):
        is_selected = row["qa_id"] in selected_ids
        members.append(
            {
                "release_member_id": _stable_id(
                    "qarelease_member", quality_release_id, row["qa_id"]
                ),
                "quality_release_id": quality_release_id,
                "qa_id": row["qa_id"],
                "selection_score": row["selection_score"],
                "subjective_score": row["subjective_score"],
                "dataset_role_score": row["dataset_role_score"],
                "novelty_score": row["novelty_score"],
                "selection_stratum": row["selection_stratum"],
                "selection_reason": {
                    "eligible": row["eligible"],
                    "selected": is_selected,
                    "gate_reasons": row["reasons"],
                    "selection_rank": selection_ranks.get(row["qa_id"]),
                    "quota_selection_status": (
                        "selected"
                        if is_selected
                        else "eligible_not_selected_by_quota"
                        if row["eligible"]
                        else "ineligible"
                    ),
                    "distribution_features": row["distribution_features"],
                },
                "is_selected": is_selected,
            }
        )

    selected_manifest = [
        {
            "qa_id": row["qa_id"],
            "selection_score": row["selection_score"],
            "selection_stratum": row["selection_stratum"],
            "distribution_features": row["distribution_features"],
        }
        for row in selected
    ]
    release_status = _release_status(
        str(run["evaluation_mode"]),
        calibrated,
        len(selected_ids),
        effective_target,
        quota_satisfied=bool(quota_result["quota_satisfied"]),
        supply_preflight_passed=bool(quota_result["supply_preflight_passed"]),
    )
    release_row = {
        "quality_release_id": quality_release_id,
        "qa_build_id": run["qa_build_id"],
        "evaluation_run_id": evaluation_run_id,
        "selection_policy_version": SELECTION_POLICY_VERSION,
        "target_size": effective_target,
        "distribution_contract": distribution_contract,
        "quality_thresholds": {
            "decision_thresholds": quality_config.get("decision_thresholds") or {},
            "release_selection": selection,
            "weights": weights,
            "calibrated": calibrated,
        },
        "member_manifest_hash": _hash(selected_manifest),
        "status": release_status,
        "created_at": _now(),
    }
    with db.transaction():
        insert_rows(
            db,
            "qa_quality_releases",
            [release_row],
            RELEASE_COLUMNS,
            {"distribution_contract", "quality_thresholds"},
        )
        insert_rows(
            db,
            "qa_quality_release_members",
            members,
            MEMBER_COLUMNS,
            {"selection_reason"},
        )

    report = {
        **release_row,
        "evaluated_count": len(assessed),
        "eligible_count": len(eligible),
        "selected_count": len(selected_ids),
        "excluded_count": len(assessed) - len(selected_ids),
        "decision_counts": _counts(items, "decision"),
        "selected_split_counts": _selected_split_counts(selected_ids, bundles),
        "exclusion_reason_counts": _reason_counts(assessed),
        "distribution_quota_audit": {
            key: value
            for key, value in quota_result.items()
            if key != "selected"
        },
        "selection_policy": {
            "release_decisions": sorted(RELEASE_DECISIONS),
            "training_splits": sorted(TRAINING_SPLITS),
            "minimum_subjective_score": minimum_subjective,
            "weights": weights,
            "distribution_quota_enforced": bool(
                selection.get("enforce_distribution_quotas", False)
            ),
            "hard_distribution_names": quota_result["hard_distribution_names"],
            "minimum_candidate_multiplier": selection.get(
                "minimum_candidate_multiplier"
            ) or {"typed_edge_walk": 1.3},
            "fail_closed": True,
        },
    }
    if output_dir:
        report["written_files"] = _write_report(
            report, selected_manifest, output_dir
        )
    return report


def _load_run(db: DBProtocol, evaluation_run_id: str) -> dict[str, Any]:
    row = db.fetchone(
        "SELECT * FROM qa_evaluation_runs WHERE evaluation_run_id = ?",
        (evaluation_run_id,),
    )
    if not row:
        raise RuntimeError(f"Unknown QA evaluation run: {evaluation_run_id}")
    out = dict(row)
    for key, default in {"sample_manifest": {}, "notes": {}}.items():
        out[key] = json_value(out.get(key), default)
    return out


def _load_items(db: DBProtocol, evaluation_run_id: str) -> list[dict[str, Any]]:
    rows = []
    for raw in db.fetchall(
        "SELECT * FROM qa_evaluation_items WHERE evaluation_run_id = ? "
        "ORDER BY qa_id",
        (evaluation_run_id,),
    ):
        row = dict(raw)
        for key, default in {
            "dataset_role_components": {},
            "confirmed_fatal_flags": [],
        }.items():
            row[key] = json_value(row.get(key), default)
        rows.append(row)
    if not rows:
        raise RuntimeError(
            f"Evaluation run {evaluation_run_id} has no aggregated items"
        )
    return rows


def _assert_immutable_sample_manifest(
    db: DBProtocol, run: dict[str, Any]
) -> None:
    manifest = run.get("sample_manifest") or {}
    qa_ids = [str(value) for value in manifest.get("qa_ids") or []]
    stable_ids = [str(value) for value in manifest.get("stable_qa_ids") or []]
    if len(qa_ids) != len(stable_ids):
        raise RuntimeError(
            "Pinned sample manifest has mismatched QA and stable ID counts"
        )
    selected = set(qa_ids)
    observed = {
        str(row["qa_id"]): str(row["stable_qa_id"])
        for row in db.fetchall(
            "SELECT qa_id, stable_qa_id FROM qa_samples WHERE qa_build_id = ?",
            (run["qa_build_id"],),
        )
        if str(row["qa_id"]) in selected
    }
    expected = dict(zip(qa_ids, stable_ids, strict=True))
    if observed != expected:
        raise RuntimeError(
            "Immutable QA sample manifest no longer matches the pinned QA build"
        )


def _training_release_eligible(item: dict[str, Any]) -> bool:
    return float(
        (item.get("dataset_role_components") or {}).get(
            "training_release_eligible", 0
        )
    ) == 100.0


def _normalized_weights(selection: dict[str, Any]) -> dict[str, float]:
    weights = {
        "subjective": float(selection.get("subjective_weight", 0.7)),
        "dataset_role": float(selection.get("dataset_role_weight", 0.2)),
        "novelty": float(selection.get("novelty_weight", 0.1)),
    }
    total = sum(weights.values())
    if total <= 0:
        raise ValueError(
            "Quality release selection weights must sum to a positive value"
        )
    return {key: value / total for key, value in weights.items()}


def _selection_stratum(bundle: dict[str, Any]) -> str:
    label = bundle.get("distribution_label") or {}
    return "|".join(
        str(value or "unknown")
        for value in (
            label.get("benchmark_task"),
            label.get("market_subset"),
            bundle.get("generation_pipeline"),
        )
    )


def _select_with_distribution_quotas(
    eligible: list[dict[str, Any]],
    contract: dict[str, Any],
    target_size: int,
    selection: dict[str, Any],
) -> dict[str, Any]:
    enforce = bool(selection.get("enforce_distribution_quotas", False))
    distributions_by_name = {
        str(row.get("name")): row
        for row in contract.get("target_distributions") or []
    }
    hard_names = [
        str(value)
        for value in contract.get("release_hard_distributions") or []
    ]
    unknown = sorted(set(hard_names) - set(distributions_by_name))
    if unknown:
        raise ValueError("Unknown hard release distributions: " + ",".join(unknown))
    hard = [distributions_by_name[name] for name in hard_names]
    quotas = {
        str(row["name"]): _largest_remainder_counts(
            {str(key): float(value) for key, value in row["shares"].items()},
            target_size,
        )
        for row in hard
    }
    supply = {
        str(row["name"]): Counter(
            _feature_key(candidate["distribution_features"], row["fields"])
            for candidate in eligible
        )
        for row in hard
    }
    preflight = _pipeline_supply_preflight(
        quotas,
        supply,
        selection.get("minimum_candidate_multiplier") or {
            "typed_edge_walk": 1.3
        },
    )

    if not enforce or not hard:
        selected = eligible[:target_size]
    else:
        remaining = {
            name: dict(values) for name, values in quotas.items()
        }
        pool = list(eligible)
        selected = []
        while pool and len(selected) < target_size:
            feasible = [
                row
                for row in pool
                if all(
                    remaining[str(distribution["name"])].get(
                        _feature_key(
                            row["distribution_features"],
                            distribution["fields"],
                        ),
                        0,
                    )
                    > 0
                    for distribution in hard
                )
            ]
            if not feasible:
                break
            availability = {
                str(distribution["name"]): Counter(
                    _feature_key(row["distribution_features"], distribution["fields"])
                    for row in feasible
                )
                for distribution in hard
            }

            def priority(row: dict[str, Any]) -> tuple[float, float, str]:
                pressure = 0.0
                for distribution in hard:
                    name = str(distribution["name"])
                    key = _feature_key(
                        row["distribution_features"], distribution["fields"]
                    )
                    pressure += remaining[name].get(key, 0) / max(
                        availability[name].get(key, 0), 1
                    )
                return (-pressure, -float(row["selection_score"]), row["qa_id"])

            chosen = min(feasible, key=priority)
            selected.append(chosen)
            pool.remove(chosen)
            for distribution in hard:
                name = str(distribution["name"])
                key = _feature_key(
                    chosen["distribution_features"], distribution["fields"]
                )
                remaining[name][key] -= 1

    selected_counts = {
        str(row["name"]): dict(
            sorted(
                Counter(
                    _feature_key(candidate["distribution_features"], row["fields"])
                    for candidate in selected
                ).items()
            )
        )
        for row in hard
    }
    unmet: dict[str, dict[str, int]] = {}
    for name, target_counts in quotas.items():
        gaps = {
            key: count - int(selected_counts.get(name, {}).get(key, 0))
            for key, count in target_counts.items()
            if int(selected_counts.get(name, {}).get(key, 0)) != count
        }
        if gaps:
            unmet[name] = gaps
    quota_satisfied = len(selected) >= target_size and (not enforce or not unmet)
    return {
        "selected": selected,
        "enforced": enforce,
        "hard_distribution_names": hard_names,
        "target_counts": quotas,
        "eligible_supply_counts": {
            name: dict(sorted(values.items())) for name, values in supply.items()
        },
        "selected_counts": selected_counts,
        "unmet_counts": unmet,
        "quota_satisfied": quota_satisfied,
        "supply_preflight": preflight,
        "supply_preflight_passed": all(
            row["passed"] for row in preflight.values()
        ),
    }


def _largest_remainder_counts(
    shares: dict[str, float], target_size: int
) -> dict[str, int]:
    raw = {key: value * target_size for key, value in shares.items()}
    counts = {key: int(value) for key, value in raw.items()}
    remainder = target_size - sum(counts.values())
    order = sorted(shares, key=lambda key: (-(raw[key] - counts[key]), key))
    for key in order[:remainder]:
        counts[key] += 1
    return dict(sorted(counts.items()))


def _pipeline_supply_preflight(
    quotas: dict[str, dict[str, int]],
    supply: dict[str, Counter[str]],
    minimum_multipliers: dict[str, Any],
) -> dict[str, Any]:
    output = {}
    pipeline_quotas = quotas.get("generation_pipeline") or {}
    pipeline_supply = supply.get("generation_pipeline") or Counter()
    for pipeline, raw_multiplier in sorted(minimum_multipliers.items()):
        target = int(pipeline_quotas.get(str(pipeline), 0))
        available = int(pipeline_supply.get(str(pipeline), 0))
        multiplier = max(float(raw_multiplier), 1.0)
        observed = available / target if target else None
        output[str(pipeline)] = {
            "target_count": target,
            "eligible_count": available,
            "minimum_candidate_multiplier": multiplier,
            "observed_candidate_multiplier": (
                round(observed, 6) if observed is not None else None
            ),
            "passed": target == 0 or available >= target * multiplier,
        }
    return output


def _feature_key(features: dict[str, str], fields: list[str]) -> str:
    return "|".join(str(features.get(str(field)) or "unknown") for field in fields)


def _release_status(
    mode: str,
    calibrated: bool,
    selected_count: int,
    target_size: int,
    *,
    quota_satisfied: bool,
    supply_preflight_passed: bool,
) -> str:
    complete = (
        selected_count >= target_size
        and quota_satisfied
        and supply_preflight_passed
    )
    if mode != "release_gate" or not calibrated:
        return "draft_advisory" if complete else "draft_partial"
    return "ready" if complete else "partial"


def _selected_split_counts(
    selected_ids: set[str], bundles: dict[str, dict[str, Any]]
) -> dict[str, int]:
    counts: dict[str, int] = {}
    for qa_id in selected_ids:
        split = str(
            (bundles.get(qa_id, {}).get("sample") or {}).get("split")
            or "unknown"
        )
        counts[split] = counts.get(split, 0) + 1
    return dict(sorted(counts.items()))


def _reason_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        if row["eligible"]:
            continue
        for reason in row["reasons"]:
            counts[reason] = counts.get(reason, 0) + 1
    return dict(sorted(counts.items()))


def _counts(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        value = str(row.get(key) or "unknown")
        counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items()))


def _write_report(
    report: dict[str, Any],
    selected: list[dict[str, Any]],
    output_dir: str,
) -> list[str]:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    json_path = out / "qa_quality_release_report.json"
    md_path = out / "qa_quality_release_report.md"
    members_path = out / "selected_members.jsonl"
    json_path.write_text(_pretty(report) + "\n", encoding="utf-8")
    members_path.write_text(
        "".join(_compact(row) + "\n" for row in selected),
        encoding="utf-8",
    )
    md_path.write_text(
        "\n".join(
            [
                "# QA Quality-aware Release",
                "",
                f"- Release: {report['quality_release_id']}",
                f"- Evaluation run: {report['evaluation_run_id']}",
                f"- Status: {report['status']}",
                f"- Evaluated: {report['evaluated_count']}",
                f"- Eligible: {report['eligible_count']}",
                f"- Selected: {report['selected_count']} / "
                f"{report['target_size']}",
                f"- Manifest hash: {report['member_manifest_hash']}",
                f"- Distribution quota satisfied: {report['distribution_quota_audit']['quota_satisfied']}",
                f"- Candidate supply preflight: {report['distribution_quota_audit']['supply_preflight_passed']}",
                "",
                "Only accepted training samples that pass all deterministic, "
                "fatal-flag, subjective-score, and Dataset Role gates are selected.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return [str(json_path), str(md_path), str(members_path)]


def _release_id() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    return f"qarelease_{stamp}_{uuid.uuid4().hex[:8]}"


def _stable_id(prefix: str, *values: str) -> str:
    return f"{prefix}_{_hash(list(values))[:24]}"


def _hash(value: Any) -> str:
    return hashlib.sha256(_compact(value).encode("utf-8")).hexdigest()


def _compact(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)


def _pretty(value: Any) -> str:
    return json.dumps(
        value, ensure_ascii=False, indent=2, sort_keys=True, default=str
    )


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
