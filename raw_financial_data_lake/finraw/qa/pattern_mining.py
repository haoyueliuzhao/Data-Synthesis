from __future__ import annotations

import hashlib
import json
import math
import uuid
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from finraw.db.client import DBProtocol
from finraw.kg_query import resolve_kg_build_id
from finraw.qa.comparability import (
    annual_duration_valid,
    fact_frequency,
    latest_contiguous_window,
    period_index,
    period_label,
)
from finraw.qa.schema import ensure_qa_schema
from finraw.qa.store import insert_rows, json_value


MINING_VERSION = "1.0.0"


@dataclass(frozen=True)
class PatternProposal:
    proposal_id: str
    mining_run_id: str
    kg_build_id: str
    motif_family: str
    motif_signature: str
    pattern_spec: dict[str, Any]
    operator_dag_template: dict[str, Any]
    answer_schema: dict[str, Any]
    binding_examples: list[dict[str, Any]]
    support_count: int
    entity_count: int
    metric_count: int
    period_count: int
    support_score: float
    completeness_score: float
    financial_value_score: float
    complexity_score: float
    novelty_score: float
    total_score: float
    status: str
    rejection_reasons: list[str]
    proposal_hash: str
    created_at: str

    def as_row(self) -> dict[str, Any]:
        return asdict(self)


def mining_policy(config: dict[str, Any]) -> dict[str, Any]:
    qa = config.get("qa", {})
    raw = qa.get("pattern_mining", {})
    return {
        "enabled": bool(raw.get("enabled", False)),
        "auto_run": bool(raw.get("auto_run", False)),
        "families": tuple(
            raw.get(
                "families",
                [
                    "cross_metric_comparison",
                    "temporal_aggregation",
                    "temporal_extrema_followup",
                    "scope_rank_followup",
                ],
            )
        ),
        "max_metrics": max(int(raw.get("max_metrics", 24)), 2),
        "rows_per_metric": max(int(raw.get("rows_per_metric", 3000)), 100),
        "max_proposals": max(int(raw.get("max_proposals", 100)), 1),
        "max_bindings_per_proposal": max(
            int(raw.get("max_bindings_per_proposal", 20)), 1
        ),
        "max_candidates_per_proposal": max(
            int(raw.get("max_candidates_per_proposal", 10)), 1
        ),
        "min_support": max(int(raw.get("min_support", 3)), 1),
        "target_support": max(int(raw.get("target_support", 20)), 2),
        "min_total_score": float(raw.get("min_total_score", 0.62)),
        "minimum_temporal_observations": max(
            int(raw.get("minimum_temporal_observations", 3)), 2
        ),
        "maximum_temporal_observations": max(
            int(raw.get("maximum_temporal_observations", 5)), 3
        ),
        "minimum_scope_entities": max(
            int(raw.get("minimum_scope_entities", 3)), 2
        ),
        "top_k": max(int(raw.get("top_k", 3)), 1),
        "require_contiguous_periods": bool(
            raw.get("require_contiguous_periods", True)
        ),
    }


def mine_qa_patterns(
    db: DBProtocol,
    config: dict[str, Any],
    *,
    kg_build_id: str | None = None,
    output_dir: str | None = None,
) -> dict[str, Any]:
    ensure_qa_schema(db)
    policy = mining_policy(config)
    kg_build_id = resolve_kg_build_id(db, kg_build_id)
    kg_row = db.fetchone(
        "SELECT * FROM kg_builds WHERE kg_build_id = ?", (kg_build_id,)
    )
    if not kg_row:
        raise ValueError(f"Unknown KG build: {kg_build_id}")
    kg = dict(kg_row)
    if kg.get("status") != "success" or kg.get("quality_status") != "passed":
        raise RuntimeError(f"KG build is not pattern-mining eligible: {kg_build_id}")

    run_id = "qamining_" + datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_") + uuid.uuid4().hex[:8]
    started_at = _now()
    run = {
        "mining_run_id": run_id,
        "kg_build_id": kg_build_id,
        "mining_version": MINING_VERSION,
        "config_hash": _digest(policy),
        "status": "running",
        "started_at": started_at,
        "completed_at": None,
        "scanned_fact_count": 0,
        "proposal_count": 0,
        "approved_count": 0,
        "notes": {"policy": policy},
    }
    insert_rows(
        db,
        "qa_pattern_mining_runs",
        [run],
        list(run),
        {"notes"},
    )
    try:
        facts, metrics = _load_mining_pool(db, kg, policy)
        proposals = _discover_proposals(facts, metrics, run_id, kg_build_id, policy)
        rows = [proposal.as_row() for proposal in proposals]
        if rows:
            insert_rows(
                db,
                "qa_pattern_proposals",
                rows,
                list(rows[0]),
                {
                    "pattern_spec",
                    "operator_dag_template",
                    "answer_schema",
                    "binding_examples",
                    "rejection_reasons",
                },
            )
        approved = sum(proposal.status == "approved" for proposal in proposals)
        db.execute(
            "UPDATE qa_pattern_mining_runs SET status = ?, completed_at = ?, "
            "scanned_fact_count = ?, proposal_count = ?, approved_count = ? "
            "WHERE mining_run_id = ?",
            ("success", _now(), len(facts), len(proposals), approved, run_id),
        )
    except Exception as exc:
        db.execute(
            "UPDATE qa_pattern_mining_runs SET status = ?, completed_at = ?, notes = ? "
            "WHERE mining_run_id = ?",
            (
                "failed",
                _now(),
                _db_json(db, {"policy": policy, "error": str(exc)}),
                run_id,
            ),
        )
        raise

    family_counts: dict[str, int] = defaultdict(int)
    approved_family_counts: dict[str, int] = defaultdict(int)
    for proposal in proposals:
        family_counts[proposal.motif_family] += 1
        if proposal.status == "approved":
            approved_family_counts[proposal.motif_family] += 1
    report = {
        "mining_run_id": run_id,
        "kg_build_id": kg_build_id,
        "mining_version": MINING_VERSION,
        "scanned_fact_count": len(facts),
        "scanned_metric_count": len(metrics),
        "proposal_count": len(proposals),
        "approved_count": approved,
        "proposal_family_counts": dict(sorted(family_counts.items())),
        "approved_family_counts": dict(sorted(approved_family_counts.items())),
        "top_proposals": [
            {
                "proposal_id": item.proposal_id,
                "motif_family": item.motif_family,
                "motif_signature": item.motif_signature,
                "support_count": item.support_count,
                "total_score": item.total_score,
                "status": item.status,
            }
            for family in sorted({item.motif_family for item in proposals})
            for item in [
                value for value in proposals if value.motif_family == family
            ][:5]
        ],
    }
    _write_report(report, output_dir)
    return report


def load_approved_proposals(
    db: DBProtocol,
    kg_build_id: str,
    *,
    limit: int = 100,
) -> list[dict[str, Any]]:
    rows = db.fetchall(
        """
        SELECT p.* FROM qa_pattern_proposals p
        JOIN qa_pattern_mining_runs r ON r.mining_run_id = p.mining_run_id
        WHERE p.kg_build_id = ? AND p.status = 'approved' AND r.status = 'success'
          AND p.mining_run_id = (
              SELECT mining_run_id FROM qa_pattern_mining_runs
              WHERE kg_build_id = ? AND status = 'success'
              ORDER BY completed_at DESC, mining_run_id DESC
              LIMIT 1
          )
        ORDER BY p.total_score DESC, p.support_count DESC, p.proposal_id
        LIMIT ?
        """,
        (kg_build_id, kg_build_id, limit),
    )
    json_columns = {
        "pattern_spec",
        "operator_dag_template",
        "answer_schema",
        "binding_examples",
        "rejection_reasons",
    }
    return [
        {
            **dict(row),
            **{
                column: json_value(dict(row).get(column), [] if column.endswith("s") else {})
                for column in json_columns
            },
        }
        for row in rows
    ]


def _load_mining_pool(
    db: DBProtocol, kg: dict[str, Any], policy: dict[str, Any]
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    metric_rows = db.fetchall(
        """
        SELECT sf.metric_id, COUNT(*) AS fact_count
        FROM standardized_facts sf
        JOIN kg_nodes n ON n.kg_build_id = ? AND n.node_type = 'Fact'
                       AND n.source_pk = sf.fact_id
        WHERE sf.build_id = ? AND sf.graph_ready = 1
          AND sf.normalized_value IS NOT NULL AND sf.normalized_unit IS NOT NULL
          AND COALESCE(sf.is_forecast, 0) = 0
          AND LOWER(COALESCE(sf.comparability_level, 'comparable'))
              NOT IN ('blocked', 'incomparable', 'not_comparable',
                      'source_definition_mismatch')
        GROUP BY sf.metric_id
        ORDER BY fact_count DESC, sf.metric_id
        LIMIT ?
        """,
        (
            kg["kg_build_id"],
            kg["input_fact_build_id"],
            policy["max_metrics"],
        ),
    )
    metric_ids = [str(row["metric_id"]) for row in metric_rows]
    if not metric_ids:
        return [], {}
    placeholders = ",".join("?" for _ in metric_ids)
    ontology_rows = db.fetchall(
        f"""
        SELECT metric_id, canonical_name, metric_category, statement_type,
               period_type, aggregation_rule, revision_risk, ambiguity_notes
        FROM metrics
        WHERE build_id = ? AND metric_id IN ({placeholders})
        """,
        (kg["input_metric_build_id"], *metric_ids),
    )
    metrics = {str(row["metric_id"]): dict(row) for row in ontology_rows}
    facts: list[dict[str, Any]] = []
    for metric_id in metric_ids:
        rows = db.fetchall(
            """
            SELECT sf.*, ce.entity_type, ce.market, ce.country, ce.industry,
                   m.canonical_name AS metric_name, m.metric_category,
                   m.statement_type, m.period_type AS ontology_period_type,
                   m.aggregation_rule, m.revision_risk
            FROM standardized_facts sf
            JOIN kg_nodes n ON n.kg_build_id = ? AND n.node_type = 'Fact'
                           AND n.source_pk = sf.fact_id
            JOIN canonical_entities ce ON ce.build_id = ?
                                      AND ce.entity_id = sf.entity_id
            JOIN metrics m ON m.build_id = ? AND m.metric_id = sf.metric_id
            WHERE sf.build_id = ? AND sf.metric_id = ? AND sf.graph_ready = 1
              AND sf.normalized_value IS NOT NULL
              AND sf.normalized_unit IS NOT NULL
              AND COALESCE(sf.is_forecast, 0) = 0
              AND LOWER(COALESCE(sf.comparability_level, 'comparable'))
                  NOT IN ('blocked', 'incomparable', 'not_comparable',
                          'source_definition_mismatch')
            ORDER BY sf.entity_id, sf.period_end DESC, sf.fact_id
            LIMIT ?
            """,
            (
                kg["kg_build_id"],
                kg["input_entity_build_id"],
                kg["input_metric_build_id"],
                kg["input_fact_build_id"],
                metric_id,
                policy["rows_per_metric"],
            ),
        )
        facts.extend(_deduplicate_facts(dict(row) for row in rows))
    return facts, metrics


def _discover_proposals(
    facts: list[dict[str, Any]],
    metrics: dict[str, dict[str, Any]],
    run_id: str,
    kg_build_id: str,
    policy: dict[str, Any],
) -> list[PatternProposal]:
    raw: list[dict[str, Any]] = []
    families = set(policy["families"])
    if "cross_metric_comparison" in families:
        raw.extend(_mine_cross_metric_comparison(facts, metrics, policy))
    if "temporal_aggregation" in families:
        raw.extend(_mine_temporal_aggregation(facts, policy))
    if "temporal_extrema_followup" in families:
        raw.extend(_mine_temporal_followup(facts, metrics, policy))
    if "scope_rank_followup" in families:
        raw.extend(_mine_scope_rank_followup(facts, metrics, policy))
    proposals = [
        _proposal_from_raw(item, run_id, kg_build_id, policy) for item in raw
    ]
    proposals.sort(
        key=lambda item: (-item.total_score, -item.support_count, item.proposal_id)
    )
    return _balanced_select(proposals, policy["max_proposals"])


def _mine_cross_metric_comparison(
    facts: list[dict[str, Any]],
    metrics: dict[str, dict[str, Any]],
    policy: dict[str, Any],
) -> list[dict[str, Any]]:
    groups: dict[tuple[Any, ...], dict[str, dict[str, Any]]] = defaultdict(dict)
    for fact in facts:
        metric = metrics.get(str(fact["metric_id"]), {})
        key = (
            fact["entity_id"],
            _period_key(fact),
            fact.get("source_id"),
            fact_frequency(fact),
            fact.get("time_basis"),
            fact.get("metric_period_type"),
            metric.get("statement_type"),
            _financial_scope(fact),
            fact.get("normalized_unit"),
            fact.get("normalized_currency"),
        )
        groups[key][str(fact["metric_id"])] = fact
    found: dict[tuple[Any, ...], dict[str, Any]] = {}
    for key, by_metric in groups.items():
        metric_ids = sorted(by_metric)
        for left_index, left_metric in enumerate(metric_ids):
            for right_metric in metric_ids[left_index + 1 :]:
                pair_key = (left_metric, right_metric)
                entry = found.setdefault(
                    pair_key,
                    _raw_proposal(
                        "cross_metric_comparison",
                        [left_metric, right_metric],
                        _cross_metric_spec(left_metric, right_metric),
                    ),
                )
                left, right = by_metric[left_metric], by_metric[right_metric]
                _append_binding(
                    entry,
                    {
                        "input_bindings": {
                            "left": left["fact_id"],
                            "right": right["fact_id"],
                        },
                        "fact_ids": [left["fact_id"], right["fact_id"]],
                        "entity_ids": [left["entity_id"]],
                        "metric_ids": [left_metric, right_metric],
                        "period": period_label(left),
                        "frequency": fact_frequency(left),
                        "operator_params": {"id_field": "metric_id"},
                        "scope_type": "single_entity",
                        "scope_definition": str(left["entity_id"]),
                    },
                    policy,
                )
    return list(found.values())


def _mine_temporal_aggregation(
    facts: list[dict[str, Any]],
    policy: dict[str, Any],
) -> list[dict[str, Any]]:
    series = _series_groups(facts)
    found: dict[tuple[Any, ...], dict[str, Any]] = {}
    for key, rows in series.items():
        frequency = str(key[3])
        window = latest_contiguous_window(
            rows,
            frequency=frequency,
            minimum=policy["minimum_temporal_observations"],
            maximum=policy["maximum_temporal_observations"],
            require_contiguous=policy["require_contiguous_periods"],
        )
        if not window or any(not annual_duration_valid(row) for row in window):
            continue
        metric_id = str(key[1])
        proposal_key = (metric_id,)
        entry = found.setdefault(
            proposal_key,
            _raw_proposal(
                "temporal_aggregation",
                [metric_id],
                _temporal_average_spec(metric_id),
            ),
        )
        _append_binding(
            entry,
            {
                "input_bindings": {"series": [row["fact_id"] for row in window]},
                "fact_ids": [row["fact_id"] for row in window],
                "entity_ids": [window[0]["entity_id"]],
                "metric_ids": [metric_id],
                "start_period": period_label(window[0]),
                "end_period": period_label(window[-1]),
                "observation_count": len(window),
                "frequency": frequency,
                "scope_type": "single_entity_series",
                "scope_definition": str(window[0]["entity_id"]),
            },
            policy,
        )
    return list(found.values())


def _mine_temporal_followup(
    facts: list[dict[str, Any]],
    metrics: dict[str, dict[str, Any]],
    policy: dict[str, Any],
) -> list[dict[str, Any]]:
    series = _series_groups(facts)
    by_context: dict[tuple[Any, ...], dict[str, list[dict[str, Any]]]] = defaultdict(dict)
    for key, rows in series.items():
        entity_id, metric_id, source_id, frequency, time_basis, scope = key
        window = latest_contiguous_window(
            rows,
            frequency=str(frequency),
            minimum=policy["minimum_temporal_observations"],
            maximum=policy["maximum_temporal_observations"],
            require_contiguous=policy["require_contiguous_periods"],
        )
        if window and all(annual_duration_valid(row) for row in window):
            by_context[(entity_id, source_id, frequency, time_basis, scope)][
                str(metric_id)
            ] = window
    found: dict[tuple[Any, ...], dict[str, Any]] = {}
    for context, by_metric in by_context.items():
        metric_ids = sorted(by_metric)
        for primary_metric in metric_ids:
            primary = by_metric[primary_metric]
            primary_indices = {
                period_index(row, str(context[2])) for row in primary
            }
            for secondary_metric in metric_ids:
                if secondary_metric == primary_metric:
                    continue
                secondary_by_period = {
                    period_index(row, str(context[2])): row
                    for row in by_metric[secondary_metric]
                }
                if None in primary_indices or not primary_indices.issubset(
                    secondary_by_period
                ):
                    continue
                secondary = [
                    secondary_by_period[period_index(row, str(context[2]))]
                    for row in primary
                ]
                proposal_key = (primary_metric, secondary_metric)
                entry = found.setdefault(
                    proposal_key,
                    _raw_proposal(
                        "temporal_extrema_followup",
                        [primary_metric, secondary_metric],
                        _temporal_followup_spec(primary_metric, secondary_metric),
                    ),
                )
                _append_binding(
                    entry,
                    {
                        "input_bindings": {
                            "primary_series": [row["fact_id"] for row in primary],
                            "secondary_series": [row["fact_id"] for row in secondary],
                        },
                        "fact_ids": [
                            *[row["fact_id"] for row in primary],
                            *[row["fact_id"] for row in secondary],
                        ],
                        "entity_ids": [context[0]],
                        "metric_ids": [primary_metric, secondary_metric],
                        "primary_metric_id": primary_metric,
                        "secondary_metric_id": secondary_metric,
                        "start_period": period_label(primary[0]),
                        "end_period": period_label(primary[-1]),
                        "observation_count": len(primary),
                        "frequency": context[2],
                        "scope_type": "single_entity_series",
                        "scope_definition": str(context[0]),
                        "financial_scope": {
                            "entity_scope_id": context[4][0],
                            "financial_scope_type": context[4][1],
                        },
                    },
                    policy,
                )
    return list(found.values())


def _mine_scope_rank_followup(
    facts: list[dict[str, Any]],
    metrics: dict[str, dict[str, Any]],
    policy: dict[str, Any],
) -> list[dict[str, Any]]:
    groups: dict[tuple[Any, ...], dict[str, dict[str, dict[str, Any]]]] = defaultdict(
        lambda: defaultdict(dict)
    )
    for fact in facts:
        if str(fact.get("entity_type")) != "company" or not fact.get("industry"):
            continue
        key = (
            fact["industry"],
            _period_key(fact),
            fact.get("source_id"),
            fact_frequency(fact),
            fact.get("time_basis"),
            _financial_scope(fact)[1],
        )
        groups[key][str(fact["metric_id"])][str(fact["entity_id"])] = fact
    found: dict[tuple[Any, ...], dict[str, Any]] = {}
    for context, by_metric in groups.items():
        metric_ids = sorted(by_metric)
        for primary_metric in metric_ids:
            for secondary_metric in metric_ids:
                if primary_metric == secondary_metric:
                    continue
                common = sorted(
                    set(by_metric[primary_metric]) & set(by_metric[secondary_metric])
                )
                if len(common) < policy["minimum_scope_entities"]:
                    continue
                primary = [by_metric[primary_metric][entity] for entity in common]
                secondary = [by_metric[secondary_metric][entity] for entity in common]
                proposal_key = (primary_metric, secondary_metric)
                entry = found.setdefault(
                    proposal_key,
                    _raw_proposal(
                        "scope_rank_followup",
                        [primary_metric, secondary_metric],
                        _scope_rank_spec(primary_metric, secondary_metric),
                    ),
                )
                _append_binding(
                    entry,
                    {
                        "input_bindings": {
                            "primary": [row["fact_id"] for row in primary],
                            "secondary": [row["fact_id"] for row in secondary],
                        },
                        "fact_ids": [
                            *[row["fact_id"] for row in primary],
                            *[row["fact_id"] for row in secondary],
                        ],
                        "entity_ids": common,
                        "metric_ids": [primary_metric, secondary_metric],
                        "primary_metric_id": primary_metric,
                        "secondary_metric_id": secondary_metric,
                        "period": period_label(primary[0]),
                        "frequency": context[3],
                        "scope_type": "industry",
                        "scope_definition": str(context[0]),
                        "industry": str(context[0]),
                        "operator_step_params": {
                            "rank_primary": {
                                "top_k": min(policy["top_k"], len(common)),
                                "direction": "desc",
                            }
                        },
                    },
                    policy,
                )
    return list(found.values())


def _proposal_from_raw(
    raw: dict[str, Any],
    run_id: str,
    kg_build_id: str,
    policy: dict[str, Any],
) -> PatternProposal:
    bindings = raw["bindings"]
    support = int(raw["support_count"])
    entity_ids = {
        str(entity)
        for binding in bindings
        for entity in binding.get("entity_ids", [])
    }
    metric_ids = set(raw["metric_ids"])
    periods = {
        str(value)
        for binding in bindings
        for value in [
            binding.get("period"),
            binding.get("start_period"),
            binding.get("end_period"),
        ]
        if value is not None
    }
    support_score = min(
        1.0,
        math.log1p(support) / math.log1p(policy["target_support"]),
    )
    completeness_score = (
        sum(
            bool(binding.get("fact_ids"))
            and bool(binding.get("input_bindings"))
            and len(
                {
                    str(fact_id)
                    for value in binding["input_bindings"].values()
                    for fact_id in (value if isinstance(value, list) else [value])
                }
            )
            == len(set(str(value) for value in binding["fact_ids"]))
            for binding in bindings
        )
        / len(bindings)
        if bindings
        else 0.0
    )
    family_value = {
        "cross_metric_comparison": 0.68,
        "temporal_aggregation": 0.78,
        "temporal_extrema_followup": 0.94,
        "scope_rank_followup": 0.92,
    }
    financial_value_score = family_value.get(raw["motif_family"], 0.5)
    operation_count = len(raw["pattern_spec"]["operator_template"]["operators"])
    complexity_score = min(operation_count / 3.0, 1.0)
    novelty_score = min(0.65 + 0.1 * len(metric_ids), 1.0)
    total = round(
        0.28 * support_score
        + 0.22 * completeness_score
        + 0.25 * financial_value_score
        + 0.15 * complexity_score
        + 0.10 * novelty_score,
        6,
    )
    reasons = []
    if support < policy["min_support"]:
        reasons.append("insufficient_support")
    if completeness_score < 1.0:
        reasons.append("incomplete_operation_bindings")
    if total < policy["min_total_score"]:
        reasons.append("below_value_score_threshold")
    status = "approved" if not reasons else "rejected"
    signature = _digest(
        raw["motif_family"], raw["metric_ids"], raw["pattern_spec"]["semantic_constraints"]
    )
    proposal_hash = _digest(
        signature,
        raw["pattern_spec"],
        raw["pattern_spec"]["operator_template"],
        raw["pattern_spec"]["answer_schema"],
        bindings,
    )
    proposal_id = "qaprop_" + _digest(kg_build_id, proposal_hash)[:24]
    return PatternProposal(
        proposal_id=proposal_id,
        mining_run_id=run_id,
        kg_build_id=kg_build_id,
        motif_family=raw["motif_family"],
        motif_signature=signature,
        pattern_spec=raw["pattern_spec"],
        operator_dag_template=raw["pattern_spec"]["operator_template"],
        answer_schema=raw["pattern_spec"]["answer_schema"],
        binding_examples=bindings,
        support_count=support,
        entity_count=len(entity_ids),
        metric_count=len(metric_ids),
        period_count=len(periods),
        support_score=round(support_score, 6),
        completeness_score=round(completeness_score, 6),
        financial_value_score=financial_value_score,
        complexity_score=round(complexity_score, 6),
        novelty_score=round(novelty_score, 6),
        total_score=total,
        status=status,
        rejection_reasons=reasons,
        proposal_hash=proposal_hash,
        created_at=_now(),
    )


def _balanced_select(
    proposals: list[PatternProposal], limit: int
) -> list[PatternProposal]:
    if len(proposals) <= limit:
        return proposals
    by_family: dict[str, list[PatternProposal]] = defaultdict(list)
    for proposal in proposals:
        by_family[proposal.motif_family].append(proposal)
    selected: list[PatternProposal] = []
    family_names = sorted(by_family)
    family_quota = max(limit // len(family_names), 1)
    for family in family_names:
        selected.extend(by_family[family][:family_quota])
        by_family[family] = by_family[family][family_quota:]
    remaining = sorted(
        (item for values in by_family.values() for item in values),
        key=lambda item: (-item.total_score, -item.support_count, item.proposal_id),
    )
    selected.extend(remaining[: max(limit - len(selected), 0)])
    return sorted(
        selected[:limit],
        key=lambda item: (-item.total_score, -item.support_count, item.proposal_id),
    )


def _raw_proposal(
    family: str, metric_ids: list[str], pattern_spec: dict[str, Any]
) -> dict[str, Any]:
    return {
        "motif_family": family,
        "metric_ids": metric_ids,
        "pattern_spec": pattern_spec,
        "bindings": [],
        "support_count": 0,
    }


def _append_binding(
    proposal: dict[str, Any], binding: dict[str, Any], policy: dict[str, Any]
) -> None:
    proposal["support_count"] += 1
    if len(proposal["bindings"]) < policy["max_bindings_per_proposal"]:
        proposal["bindings"].append(binding)


def _base_spec(
    *,
    task_subtype: str,
    pattern_family: str,
    difficulty_base: str,
    metrics: list[str],
    operators: list[dict[str, Any]],
    output_step: str,
    answer_schema: dict[str, Any],
) -> dict[str, Any]:
    return {
        "pattern_version": 1,
        "pattern_family": pattern_family,
        "task_subtype": task_subtype,
        "node_constraints": [
            {"variable": "entity", "type": "Entity"},
            {"variable": "facts", "type": "Fact", "cardinality": "many"},
            {"variable": "metrics", "type": "Metric", "values": metrics},
            {"variable": "periods", "type": "TimePeriod", "cardinality": "many"},
        ],
        "edge_constraints": [
            {"src": "entity", "relation": "HAS_FACT", "dst": "facts"},
            {"src": "facts", "relation": "MEASURES", "dst": "metrics"},
            {"src": "facts", "relation": "IN_PERIOD", "dst": "periods"},
        ],
        "semantic_constraints": [
            {"field": "graph_ready", "operator": "eq", "value": True},
            {"field": "is_forecast", "operator": "eq", "value": False},
            {"field": "source_definition", "operator": "compatible"},
            {"field": "financial_scope", "operator": "same"},
        ],
        "operator_template": {"operators": operators, "output_step": output_step},
        "answer_schema": answer_schema,
        "difficulty_base": difficulty_base,
        "question_intents": ["mined_financial_analysis", "analyst_investigation"],
    }


def _cross_metric_spec(left: str, right: str) -> dict[str, Any]:
    return _base_spec(
        task_subtype="cross_metric_comparison",
        pattern_family="mined_comparison",
        difficulty_base="medium",
        metrics=[left, right],
        operators=[
            {
                "step_id": "answer",
                "operator": "compare",
                "inputs": [{"binding": "left"}, {"binding": "right"}],
                "params": {"id_field": "metric_id"},
            }
        ],
        output_step="answer",
        answer_schema={"type": "comparison"},
    )


def _temporal_average_spec(metric: str) -> dict[str, Any]:
    return _base_spec(
        task_subtype="multi_period_average",
        pattern_family="mined_temporal",
        difficulty_base="hard",
        metrics=[metric],
        operators=[
            {
                "step_id": "answer",
                "operator": "mean",
                "inputs": [{"binding": "series"}],
            }
        ],
        output_step="answer",
        answer_schema={"type": "numeric", "aggregation": "arithmetic_mean"},
    )


def _temporal_followup_spec(primary: str, secondary: str) -> dict[str, Any]:
    return _base_spec(
        task_subtype="temporal_peak_followup",
        pattern_family="mined_multi_stage",
        difficulty_base="expert",
        metrics=[primary, secondary],
        operators=[
            {
                "step_id": "find_peak",
                "operator": "argmax",
                "inputs": [{"binding": "primary_series"}],
                "params": {"selection_key": "period"},
            },
            {
                "step_id": "answer",
                "operator": "select_by_period",
                "inputs": [
                    {"step": "find_peak"},
                    {"binding": "secondary_series"},
                ],
            },
        ],
        output_step="answer",
        answer_schema={"type": "period_metric_lookup"},
    )


def _scope_rank_spec(primary: str, secondary: str) -> dict[str, Any]:
    return _base_spec(
        task_subtype="rank_then_secondary_lookup",
        pattern_family="mined_multi_stage_scope",
        difficulty_base="expert",
        metrics=[primary, secondary],
        operators=[
            {
                "step_id": "rank_primary",
                "operator": "rank",
                "inputs": [{"binding": "primary"}],
                "params": {"direction": "desc", "top_k": 3},
            },
            {
                "step_id": "answer",
                "operator": "lookup_ranked_entities",
                "inputs": [
                    {"step": "rank_primary"},
                    {"binding": "secondary"},
                ],
            },
        ],
        output_step="answer",
        answer_schema={"type": "multi_metric_ranked_table"},
    )


def _series_groups(
    facts: list[dict[str, Any]],
) -> dict[tuple[Any, ...], list[dict[str, Any]]]:
    output: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    for fact in facts:
        output[
            (
                fact["entity_id"],
                fact["metric_id"],
                fact.get("source_id"),
                fact_frequency(fact),
                fact.get("time_basis"),
                _financial_scope(fact),
            )
        ].append(fact)
    return output


def _deduplicate_facts(rows: Any) -> list[dict[str, Any]]:
    output: dict[tuple[Any, ...], dict[str, Any]] = {}
    for row in rows:
        key = (
            row.get("entity_id"),
            row.get("metric_id"),
            _period_key(row),
            row.get("source_id"),
            row.get("source_definition_id"),
            fact_frequency(row),
            _financial_scope(row),
        )
        current = output.get(key)
        if current is None or str(row.get("fact_id")) < str(current.get("fact_id")):
            output[key] = row
    return list(output.values())


def _period_key(row: dict[str, Any]) -> tuple[Any, ...]:
    return (
        row.get("fiscal_year"),
        row.get("fiscal_quarter"),
        row.get("calendar_year"),
        str(row.get("period_end") or row.get("as_of_date") or ""),
    )


def _financial_scope(row: dict[str, Any]) -> tuple[str, str]:
    return (
        str(row.get("entity_scope_id") or row.get("entity_id") or ""),
        str(row.get("financial_scope_type") or "consolidated_entity"),
    )


def _digest(*values: Any) -> str:
    payload = json.dumps(
        values, ensure_ascii=True, sort_keys=True, separators=(",", ":"), default=str
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _db_json(db: DBProtocol, value: Any) -> Any:
    if db.__class__.__name__ == "PostgresMetadataDB":
        from psycopg.types.json import Jsonb

        return Jsonb(value)
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)


def _write_report(report: dict[str, Any], output_dir: str | None) -> None:
    if not output_dir:
        return
    target = Path(output_dir)
    target.mkdir(parents=True, exist_ok=True)
    (target / "qa_pattern_mining_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    lines = [
        "# QA Pattern Mining Report",
        "",
        f"- Mining run: `{report['mining_run_id']}`",
        f"- KG build: `{report['kg_build_id']}`",
        f"- Scanned facts / metrics: `{report['scanned_fact_count']}` / `{report['scanned_metric_count']}`",
        f"- Proposals / approved: `{report['proposal_count']}` / `{report['approved_count']}`",
        "",
        "## Approved Families",
        "",
    ]
    lines.extend(
        f"- `{family}`: {count}"
        for family, count in report["approved_family_counts"].items()
    )
    (target / "qa_pattern_mining_report.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )
