from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from finraw.analysis.claims import (
    CLAIM_PLANNER_VERSION,
    build_claim_plan,
)
from finraw.analysis.generator import ANALYSIS_GENERATOR_VERSION, generate_analysis
from finraw.analysis.registry import (
    ANALYSIS_PATTERNS,
    CLAIM_SCHEMA_VERSION,
    CONCLUSION_POLICY_VERSION,
    SIGNAL_SPECS,
    analysis_pattern_manifest,
    analysis_pattern_registry,
    signal_registry_manifest,
    stable_hash,
)
from finraw.analysis.schema import ensure_analysis_schema
from finraw.analysis.semantic_constraints import ANALYSIS_SEMANTIC_GATE_VERSION
from finraw.analysis.split import split_analysis_samples
from finraw.analysis.signals import (
    SIGNAL_EXECUTOR_VERSION,
    SignalExecutionError,
    execute_signal,
    signal_result_hash,
)
from finraw.analysis.text_semantics import ANALYSIS_TEXT_PARSER_VERSION
from finraw.analysis.verifier import (
    ANALYSIS_VERIFIER_VERSION,
    validate_analysis_samples,
)
from finraw.db.client import DBProtocol
from finraw.qa.comparability import (
    annual_duration_valid,
    fact_frequency,
    financial_scope_key,
)
from finraw.qa.pipeline import _kg_path_from_graph
from finraw.qa.store import insert_rows

ANALYSIS_COMPILER_VERSION = "1.2.0"
_CASH_FLOW = "net_cash_provided_by_used_in_operating_activities"
_REQUIRED_METRICS = (
    "revenue",
    "net_income",
    _CASH_FLOW,
    "total_assets",
    "total_liabilities",
)

_SIGNAL_COLUMNS = [
    "signal_id",
    "signal_spec_id",
    "analysis_build_id",
    "entity_ids",
    "metric_ids",
    "period_scope",
    "scope_definition",
    "input_fact_ids",
    "input_derived_ids",
    "operator_plan",
    "intermediate_results",
    "signal_payload",
    "direction",
    "strength",
    "confidence",
    "supporting_evidence_ids",
    "counter_evidence_ids",
    "recompute_status",
    "signal_hash",
]
_CANDIDATE_COLUMNS = [
    "candidate_id",
    "stable_candidate_id",
    "analysis_build_id",
    "analysis_pattern_id",
    "pattern_version",
    "pattern_hash",
    "entity_ids",
    "metric_ids",
    "period_scope",
    "scope_definition",
    "signal_ids",
    "evidence_bundle_id",
    "claim_plan_id",
    "instruction",
    "difficulty",
    "difficulty_features",
    "eligibility_status",
    "rejection_reasons",
    "candidate_hash",
]
_BUNDLE_COLUMNS = [
    "evidence_bundle_id",
    "analysis_build_id",
    "kg_build_id",
    "entity_ids",
    "metric_ids",
    "period_scope",
    "scope_definition",
    "fact_ids",
    "derived_fact_ids",
    "signal_ids",
    "source_document_ids",
    "raw_object_ids",
    "evidence_node_ids",
    "evidence_edges",
    "evidence_components",
    "supporting_evidence",
    "counter_evidence",
    "coverage_report",
    "bundle_hash",
]
_PLAN_COLUMNS = [
    "claim_plan_id",
    "analysis_build_id",
    "candidate_id",
    "claim_graph",
    "valid_conclusion_set",
    "invalid_conclusions",
    "mandatory_claim_ids",
    "optional_claim_ids",
    "forbidden_claim_types",
    "selected_conclusion_id",
    "plan_hash",
    "validation_status",
]
_SAMPLE_COLUMNS = [
    "analysis_sample_id",
    "stable_analysis_sample_id",
    "analysis_semantic_cluster_id",
    "evidence_bundle_cluster_id",
    "signal_composition_id",
    "claim_schema_id",
    "conclusion_family_id",
    "analysis_build_id",
    "candidate_id",
    "instruction",
    "analysis_text",
    "selected_conclusion_id",
    "conclusion_text",
    "claim_alignment",
    "numeric_slots",
    "caveats",
    "rubric",
    "generation_metadata",
    "generation_method",
    "validation_status",
    "split",
]
_LLM_CALL_COLUMNS = [
    "llm_call_id",
    "analysis_build_id",
    "attempt_index",
    "is_final_attempt",
    "candidate_id",
    "analysis_sample_id",
    "provider",
    "endpoint_host",
    "model_requested",
    "response_model",
    "response_id",
    "request_hash",
    "response_hash",
    "http_status",
    "http_success",
    "json_valid",
    "structured_response_valid",
    "controlled_generation",
    "latency_ms",
    "prompt_tokens",
    "completion_tokens",
    "total_tokens",
    "estimated_cost",
    "fallback_reason",
    "error_type",
    "validation_errors",
]


def build_financial_analysis(
    db: DBProtocol,
    config: dict[str, Any],
    *,
    kg_build_id: str | None = None,
    output_dir: str = "data/audit/analysis_build",
    limit_per_pattern: int | None = None,
    activate: bool = False,
) -> dict[str, Any]:
    ensure_analysis_schema(db)
    policy = _analysis_policy(config, limit_per_pattern)
    kg = _load_kg_build(db, kg_build_id)
    _seed_registries(db)
    analysis_build_id = _new_id("analysis_build", [_now(), kg["kg_build_id"], policy])
    started_at = _now()
    manifests = _manifests()
    build_row = {
        "analysis_build_id": analysis_build_id,
        "kg_build_id": kg["kg_build_id"],
        "graph_schema_version": kg["graph_schema_version"],
        "fact_build_id": kg["input_fact_build_id"],
        "entity_build_id": kg["input_entity_build_id"],
        "metric_build_id": kg["input_metric_build_id"],
        **manifests,
        "config_hash": stable_hash(policy),
        "status": "running",
        "started_at": started_at,
        "completed_at": None,
        "candidate_count": 0,
        "signal_count": 0,
        "sample_count": 0,
        "passed_count": 0,
        "quality_status": None,
        "is_active": False,
        "superseded_by": None,
        "notes": {
            "compiler_version": ANALYSIS_COMPILER_VERSION,
            "signal_executor_version": SIGNAL_EXECUTOR_VERSION,
            "claim_planner_version": CLAIM_PLANNER_VERSION,
            "analysis_generator_version": ANALYSIS_GENERATOR_VERSION,
            "policy": policy,
            "generation_boundary": (
                "bounded_claim_grounded_llm"
                if policy["generation"]["mode"] == "controlled_llm"
                else "deterministic_evidence_given_mvp"
            ),
        },
    }
    insert_rows(
        db,
        "analysis_builds",
        [build_row],
        list(build_row),
        {"notes"},
    )
    fact_rows = _load_fact_rows(db, kg, policy["fact_scan_limit"])
    sic_major_groups = _load_sec_sic_major_groups(db)
    contexts = _series_contexts(fact_rows, sic_major_groups)
    bindings = _discover_bindings(contexts, policy)
    signal_rows: dict[str, dict[str, Any]] = {}
    candidate_rows: list[dict[str, Any]] = []
    bundle_rows: list[dict[str, Any]] = []
    plan_rows: list[dict[str, Any]] = []
    sample_rows: list[dict[str, Any]] = []
    llm_call_rows: list[dict[str, Any]] = []
    rejection_counts: Counter[str] = Counter()
    for binding in bindings:
        try:
            compiled = _compile_binding(
                db,
                kg,
                analysis_build_id,
                binding,
                signal_rows,
                policy["generation"],
            )
        except (SignalExecutionError, ValueError, KeyError) as exc:
            rejection_counts[type(exc).__name__] += 1
            continue
        candidate_rows.append(compiled["candidate"])
        bundle_rows.append(compiled["bundle"])
        plan_rows.append(compiled["claim_plan"])
        sample_rows.append(compiled["sample"])
        llm_call_rows.extend(compiled.get("llm_calls") or [])
    insert_rows(
        db,
        "financial_signal_instances",
        list(signal_rows.values()),
        _SIGNAL_COLUMNS,
        {
            "entity_ids",
            "metric_ids",
            "period_scope",
            "input_fact_ids",
            "input_derived_ids",
            "operator_plan",
            "intermediate_results",
            "signal_payload",
            "supporting_evidence_ids",
            "counter_evidence_ids",
        },
    )
    insert_rows(
        db,
        "analysis_candidates",
        candidate_rows,
        _CANDIDATE_COLUMNS,
        {
            "entity_ids",
            "metric_ids",
            "period_scope",
            "signal_ids",
            "difficulty_features",
            "rejection_reasons",
        },
    )
    insert_rows(
        db,
        "analysis_evidence_bundles",
        bundle_rows,
        _BUNDLE_COLUMNS,
        {
            "entity_ids",
            "metric_ids",
            "period_scope",
            "fact_ids",
            "derived_fact_ids",
            "signal_ids",
            "source_document_ids",
            "raw_object_ids",
            "evidence_node_ids",
            "evidence_edges",
            "evidence_components",
            "supporting_evidence",
            "counter_evidence",
            "coverage_report",
        },
    )
    insert_rows(
        db,
        "analysis_claim_plans",
        plan_rows,
        _PLAN_COLUMNS,
        {
            "claim_graph",
            "valid_conclusion_set",
            "invalid_conclusions",
            "mandatory_claim_ids",
            "optional_claim_ids",
            "forbidden_claim_types",
        },
    )
    insert_rows(
        db,
        "analysis_samples",
        sample_rows,
        _SAMPLE_COLUMNS,
        {
            "claim_alignment",
            "numeric_slots",
            "caveats",
            "rubric",
            "generation_metadata",
        },
    )
    insert_rows(
        db,
        "analysis_llm_calls",
        llm_call_rows,
        _LLM_CALL_COLUMNS,
        {"validation_errors"},
    )
    quality = validate_analysis_samples(db, analysis_build_id)
    split_report = split_analysis_samples(db, analysis_build_id, policy["split_policy"])
    split_counts = split_report["split_counts"]
    pattern_counts = Counter(row["analysis_pattern_id"] for row in candidate_rows)
    llm_stats = _analysis_llm_stats(sample_rows, llm_call_rows, policy)
    gate_failures = _build_gate_failures(quality, pattern_counts, policy, llm_stats)
    gate_status = "passed" if not gate_failures else "failed"
    status = "ready" if gate_status == "passed" else "failed"
    if activate and gate_status == "passed":
        db.execute(
            "UPDATE analysis_builds SET is_active = ? WHERE is_active = ?",
            (False, True),
        )
    db.execute(
        "UPDATE analysis_builds SET status = ?, completed_at = ?, candidate_count = ?, "
        "signal_count = ?, sample_count = ?, passed_count = ?, quality_status = ?, is_active = ?, notes = ? "
        "WHERE analysis_build_id = ?",
        (
            status,
            _now(),
            len(candidate_rows),
            len(signal_rows),
            len(sample_rows),
            quality["passed_count"],
            gate_status,
            bool(activate and gate_status == "passed"),
            _db_json(
                db,
                {
                    **build_row["notes"],
                    "pattern_counts": dict(sorted(pattern_counts.items())),
                    "rejection_counts": dict(sorted(rejection_counts.items())),
                    "split_counts": split_counts,
                    "split_audit": split_report,
                    "llm_generation": llm_stats,
                    "build_gate_failures": gate_failures,
                },
            ),
            analysis_build_id,
        ),
    )
    report = {
        "analysis_build_id": analysis_build_id,
        "kg_build_id": kg["kg_build_id"],
        "candidate_count": len(candidate_rows),
        "signal_count": len(signal_rows),
        "sample_count": len(sample_rows),
        "pattern_counts": dict(sorted(pattern_counts.items())),
        "rejection_counts": dict(sorted(rejection_counts.items())),
        "quality": quality,
        "split_counts": split_counts,
        "split_audit": split_report,
        "llm_generation": llm_stats,
        "build_gate_status": gate_status,
        "build_gate_failures": gate_failures,
        "activated": bool(activate and gate_status == "passed"),
        "manifests": manifests,
    }
    report["written_files"] = [str(path) for path in _write_report(report, output_dir)]
    return report


def _seed_registries(db: DBProtocol) -> None:
    signal_rows = [spec.row() for spec in SIGNAL_SPECS]
    insert_rows(
        db,
        "financial_signal_specs",
        signal_rows,
        list(signal_rows[0]),
        {
            "input_roles",
            "required_metrics",
            "required_scope",
            "semantic_constraints",
            "operator_dag",
            "output_schema",
            "direction_policy",
            "strength_policy",
            "caveat_policy",
        },
    )
    pattern_rows = [pattern.row() for pattern in ANALYSIS_PATTERNS]
    insert_rows(
        db,
        "analysis_patterns",
        pattern_rows,
        list(pattern_rows[0]),
        {
            "question_intents",
            "required_signal_roles",
            "optional_signal_roles",
            "counter_signal_roles",
            "evidence_constraints",
            "claim_schema",
            "conclusion_policy",
            "forbidden_claim_types",
        },
    )


def _load_kg_build(db: DBProtocol, kg_build_id: str | None) -> dict[str, Any]:
    if kg_build_id:
        row = db.fetchone(
            "SELECT * FROM kg_builds WHERE kg_build_id = ?", (kg_build_id,)
        )
    else:
        row = db.fetchone(
            "SELECT * FROM kg_builds "
            "WHERE LOWER(CAST(is_active AS TEXT)) IN ('1', 'true', 't') "
            "AND status = 'success' ORDER BY completed_at DESC LIMIT 1"
        )
    if not row:
        raise ValueError("No selected or active successful KG build is available")
    kg = dict(row)
    if str(kg.get("quality_status")) != "passed":
        raise ValueError("Financial analysis requires a quality-passed KG build")
    return kg


def _load_fact_rows(
    db: DBProtocol, kg: dict[str, Any], limit: int
) -> list[dict[str, Any]]:
    placeholders = ",".join("?" for _ in _REQUIRED_METRICS)
    rows = db.fetchall(
        f"""
        SELECT sf.*, ce.canonical_name AS entity_name, ce.entity_type,
               ce.industry, ce.market, ce.country, ce.cik,
               smd.metric_id AS source_definition_metric_id,
               smd.comparable_to_metric_id AS source_definition_comparable_metric_id,
               smd.comparability_level AS source_definition_comparability_level,
               smd.frequency AS source_definition_frequency,
               smd.vintage_policy AS source_definition_vintage_policy
        FROM standardized_facts sf
        JOIN kg_nodes fact_node
          ON fact_node.kg_build_id = ? AND fact_node.node_type = 'Fact'
         AND fact_node.source_pk = sf.fact_id
        JOIN canonical_entities ce
          ON ce.build_id = ? AND ce.entity_id = sf.entity_id
        LEFT JOIN source_metric_definitions smd
          ON smd.definition_id = sf.source_definition_id
        WHERE sf.build_id = ? AND sf.metric_id IN ({placeholders})
          AND sf.graph_ready = 1 AND COALESCE(sf.is_forecast, 0) = 0
          AND sf.normalized_value IS NOT NULL AND sf.normalized_unit IS NOT NULL
          AND sf.fiscal_year IS NOT NULL AND UPPER(COALESCE(sf.fiscal_quarter, '')) = 'FY'
          AND ce.entity_type = 'company'
        ORDER BY sf.entity_id, sf.metric_id, sf.fiscal_year, sf.fact_id
        LIMIT ?
        """,
        [
            kg["kg_build_id"],
            kg["input_entity_build_id"],
            kg["input_fact_build_id"],
            *_REQUIRED_METRICS,
            limit,
        ],
    )
    return [dict(row) for row in rows]


def _load_sec_sic_major_groups(db: DBProtocol) -> dict[str, str]:
    rows = db.fetchall(
        "SELECT record_json FROM raw_records WHERE source_id = ? AND record_type = ?",
        ("sec_submissions", "sec_submissions_json"),
    )
    groups: dict[str, str] = {}
    for row in rows:
        payload = row.get("record_json") or {}
        if isinstance(payload, str):
            try:
                payload = json.loads(payload)
            except json.JSONDecodeError:
                continue
        cik = str(payload.get("cik") or "").strip()
        sic = str(payload.get("sic") or "").strip().zfill(4)
        if cik and len(sic) == 4 and sic.isdigit():
            groups[cik.zfill(10)] = sic[:2]
    return groups


def _series_contexts(
    rows: list[dict[str, Any]],
    sic_major_groups: dict[str, str] | None = None,
) -> dict[tuple[str, str, str, str], dict[str, Any]]:
    grouped: dict[tuple[Any, ...], dict[int, dict[str, Any]]] = defaultdict(dict)
    metadata: dict[str, dict[str, Any]] = {}
    for row in rows:
        if fact_frequency(row) != "annual" or not annual_duration_valid(row):
            continue
        if financial_scope_key(row) != (
            str(row.get("entity_id")),
            "consolidated_entity",
        ):
            continue
        definition = str(row.get("source_definition_id") or "")
        if not definition:
            continue
        entity_id = str(row["entity_id"])
        industry = str(row.get("industry") or "").strip()
        cik = str(row.get("cik") or "").strip().zfill(10)
        sic_major_group = (sic_major_groups or {}).get(cik)
        if sic_major_group:
            peer_scope_type = "sec_sic_major_group"
            peer_scope_id = f"SEC_SIC_MAJOR_{sic_major_group}"
            peer_scope_name = f"SEC SIC major group {sic_major_group}"
        else:
            peer_scope_type = "canonical_industry"
            peer_scope_id = industry
            peer_scope_name = industry
        metadata[entity_id] = {
            "entity_id": entity_id,
            "entity_name": row.get("entity_name") or entity_id,
            "industry": industry,
            "market": row.get("market"),
            "country": row.get("country"),
            "peer_scope_type": peer_scope_type,
            "peer_scope_id": peer_scope_id,
            "peer_scope_name": peer_scope_name,
        }
        key = (
            entity_id,
            str(row.get("source_id") or ""),
            str(row.get("normalized_unit") or ""),
            str(row.get("normalized_currency") or ""),
            str(row["metric_id"]),
            definition,
        )
        year = int(row["fiscal_year"])
        current = grouped[key].get(year)
        if current is None or _fact_score(row) > _fact_score(current):
            grouped[key][year] = row
    alternatives: dict[
        tuple[str, str, str, str], dict[str, list[list[dict[str, Any]]]]
    ] = defaultdict(lambda: defaultdict(list))
    for key, by_year in grouped.items():
        entity_id, source_id, unit, currency, metric_id, _ = key
        alternatives[(entity_id, source_id, unit, currency)][metric_id].append(
            [by_year[year] for year in sorted(by_year)]
        )
    contexts: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    for key, metrics in alternatives.items():
        chosen = {
            metric_id: max(series, key=_series_score)
            for metric_id, series in metrics.items()
        }
        contexts[key] = {
            **metadata[key[0]],
            "source_id": key[1],
            "unit": key[2],
            "currency": key[3],
            "series": chosen,
        }
    return contexts


def _discover_bindings(
    contexts: dict[tuple[str, str, str, str], dict[str, Any]],
    policy: dict[str, Any],
) -> list[dict[str, Any]]:
    by_pattern: dict[str, list[dict[str, Any]]] = {
        pattern_id: [] for pattern_id in analysis_pattern_registry()
    }
    window = policy["window_years"]
    best_by_entity_pattern: dict[tuple[str, str], dict[str, Any]] = {}
    for context in contexts.values():
        for pattern_id, metrics in (
            ("operating_trend_summary_v1", ("revenue", "net_income", _CASH_FLOW)),
            (
                "growth_quality_diagnosis_v1",
                ("revenue", "net_income", _CASH_FLOW, "total_assets"),
            ),
        ):
            selected = _aligned_window(context["series"], metrics, window)
            if not selected:
                continue
            binding = _temporal_binding(pattern_id, context, selected)
            key = (pattern_id, context["entity_id"])
            current = best_by_entity_pattern.get(key)
            if current is None or _binding_score(binding) > _binding_score(current):
                best_by_entity_pattern[key] = binding
    for (pattern_id, _), binding in best_by_entity_pattern.items():
        by_pattern[pattern_id].append(binding)
    by_pattern["peer_positioning_v1"] = _peer_bindings(contexts, policy)
    output: list[dict[str, Any]] = []
    for pattern_id, values in by_pattern.items():
        quota = int(policy["pattern_quotas"].get(pattern_id, 0))
        values.sort(key=lambda item: stable_hash(_binding_identity(item)))
        output.extend(values[:quota])
    return output


def _temporal_binding(
    pattern_id: str,
    context: dict[str, Any],
    selected: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    years = sorted(
        {int(row["fiscal_year"]) for rows in selected.values() for row in rows}
    )
    signal_inputs: list[dict[str, Any]] = [
        {
            "signal_spec_id": "revenue_growth_v1",
            "roles": {"series": selected["revenue"]},
        },
        {
            "signal_spec_id": "profit_growth_v1",
            "roles": {"series": selected["net_income"]},
        },
        {
            "signal_spec_id": "operating_cash_flow_growth_v1",
            "roles": {"series": selected[_CASH_FLOW]},
        },
    ]
    if pattern_id == "operating_trend_summary_v1":
        signal_inputs.append(
            {
                "signal_spec_id": "trend_consistency_v1",
                "roles": {"series": selected["revenue"]},
            }
        )
    else:
        signal_inputs.extend(
            [
                {
                    "signal_spec_id": "earnings_cash_divergence_v1",
                    "roles": {
                        "profit_series": selected["net_income"],
                        "cash_series": selected[_CASH_FLOW],
                    },
                },
                {
                    "signal_spec_id": "margin_change_v1",
                    "roles": {
                        "profit_series": selected["net_income"],
                        "revenue_series": selected["revenue"],
                    },
                },
                {
                    "signal_spec_id": "asset_efficiency_change_v1",
                    "roles": {
                        "revenue_series": selected["revenue"],
                        "asset_series": selected["total_assets"],
                    },
                },
            ]
        )
    return {
        "analysis_pattern_id": pattern_id,
        "entity_ids": [context["entity_id"]],
        "target_entity_id": context["entity_id"],
        "entity_name": context["entity_name"],
        "metric_ids": sorted(selected),
        "period_scope": {"basis": "fiscal_year", "frequency": "annual", "years": years},
        "scope_definition": f"{context['entity_name']} consolidated entity",
        "signal_inputs": signal_inputs,
        "industry": context.get("industry"),
    }


def _peer_bindings(
    contexts: dict[tuple[str, str, str, str], dict[str, Any]],
    policy: dict[str, Any],
) -> list[dict[str, Any]]:
    scopes: dict[
        tuple[str, str, str, int, str, str, str],
        dict[str, dict[str, dict[str, Any]]],
    ] = defaultdict(dict)
    for context in contexts.values():
        scope_type = str(context.get("peer_scope_type") or "")
        scope_id = str(context.get("peer_scope_id") or "")
        scope_name = str(context.get("peer_scope_name") or "")
        if not scope_type or not scope_id or not scope_name:
            continue
        series = context["series"]
        if not {"revenue", "net_income", "total_assets", "total_liabilities"}.issubset(
            series
        ):
            continue
        by_metric_year = {
            metric: {int(row["fiscal_year"]): row for row in rows}
            for metric, rows in series.items()
        }
        years = sorted(
            set(by_metric_year["revenue"])
            & set(by_metric_year["net_income"])
            & set(by_metric_year["total_assets"])
            & set(by_metric_year["total_liabilities"])
        )
        for year in years:
            if year - 1 not in by_metric_year["revenue"]:
                continue
            scope_key = (
                scope_type,
                scope_id,
                scope_name,
                year,
                context["source_id"],
                context["unit"],
                context["currency"],
            )
            scopes[scope_key][context["entity_id"]] = {
                "current_revenue": by_metric_year["revenue"][year],
                "previous_revenue": by_metric_year["revenue"][year - 1],
                "net_income": by_metric_year["net_income"][year],
                "total_assets": by_metric_year["total_assets"][year],
                "total_liabilities": by_metric_year["total_liabilities"][year],
                "entity_name": context["entity_name"],
            }
    bindings: list[dict[str, Any]] = []
    min_entities = policy["peer_min_entities"]
    max_entities = policy["peer_max_entities"]
    for key, entities in sorted(scopes.items(), key=lambda item: str(item[0])):
        if not min_entities <= len(entities) <= max_entities:
            continue
        scope_type, scope_id, scope_name, year, _, _, _ = key
        entity_ids = sorted(entities)
        current = [entities[entity_id]["current_revenue"] for entity_id in entity_ids]
        previous = [entities[entity_id]["previous_revenue"] for entity_id in entity_ids]
        profits = [entities[entity_id]["net_income"] for entity_id in entity_ids]
        assets = [entities[entity_id]["total_assets"] for entity_id in entity_ids]
        liabilities = [
            entities[entity_id]["total_liabilities"] for entity_id in entity_ids
        ]
        for target in entity_ids:
            bindings.append(
                {
                    "analysis_pattern_id": "peer_positioning_v1",
                    "entity_ids": entity_ids,
                    "target_entity_id": target,
                    "entity_name": entities[target]["entity_name"],
                    "metric_ids": [
                        "revenue",
                        "net_income",
                        "total_assets",
                        "total_liabilities",
                    ],
                    "period_scope": {
                        "basis": "fiscal_year",
                        "frequency": "annual",
                        "years": [year - 1, year],
                    },
                    "scope_definition": (
                        f"Complete covered {scope_name} peer set for fiscal year {year}; "
                        f"scope_id={scope_id}; scope_type={scope_type}"
                    ),
                    "industry": scope_name,
                    "peer_scope_type": scope_type,
                    "peer_scope_id": scope_id,
                    "signal_inputs": [
                        {
                            "signal_spec_id": "peer_growth_percentile_v1",
                            "roles": {"current": current, "previous": previous},
                        },
                        {
                            "signal_spec_id": "peer_margin_percentile_v1",
                            "roles": {"profit": profits, "revenue": current},
                        },
                        {
                            "signal_spec_id": "peer_leverage_percentile_v1",
                            "roles": {"liabilities": liabilities, "assets": assets},
                        },
                    ],
                }
            )
    return bindings


def _compile_binding(
    db: DBProtocol,
    kg: dict[str, Any],
    analysis_build_id: str,
    binding: dict[str, Any],
    signal_rows: dict[str, dict[str, Any]],
    generation_policy: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    pattern = analysis_pattern_registry()[binding["analysis_pattern_id"]]
    pattern_row = pattern.row()
    stable_candidate_id = _new_id(
        "analysis_candidate_stable", _binding_identity(binding)
    )
    candidate_id = _new_id(
        "analysis_candidate", [analysis_build_id, stable_candidate_id]
    )
    compiled_signals = []
    all_facts: dict[str, dict[str, Any]] = {}
    for signal_binding in binding["signal_inputs"]:
        spec_id = signal_binding["signal_spec_id"]
        roles = signal_binding["roles"]
        input_fact_ids = sorted(
            {str(row["fact_id"]) for rows in roles.values() for row in rows}
        )
        result = execute_signal(
            spec_id, roles, target_entity_id=binding["target_entity_id"]
        )
        signal_hash = signal_result_hash(
            spec_id, input_fact_ids, result.payload, result.direction, result.strength
        )
        signal_id = _new_id("signal", [analysis_build_id, signal_hash])
        for rows in roles.values():
            for row in rows:
                all_facts[str(row["fact_id"])] = row
        row = {
            "signal_id": signal_id,
            "signal_spec_id": spec_id,
            "analysis_build_id": analysis_build_id,
            "entity_ids": binding["entity_ids"],
            "metric_ids": sorted(
                {str(row["metric_id"]) for rows in roles.values() for row in rows}
            ),
            "period_scope": binding["period_scope"],
            "scope_definition": binding["scope_definition"],
            "input_fact_ids": input_fact_ids,
            "input_derived_ids": [],
            "operator_plan": {
                "role_fact_ids": {
                    role: [str(row["fact_id"]) for row in rows]
                    for role, rows in roles.items()
                },
                "target_entity_id": binding["target_entity_id"],
                "signal_executor_version": SIGNAL_EXECUTOR_VERSION,
            },
            "intermediate_results": result.intermediate_results,
            "signal_payload": result.payload,
            "direction": result.direction,
            "strength": result.strength,
            "confidence": result.confidence,
            "supporting_evidence_ids": input_fact_ids
            if result.direction != "negative"
            else [],
            "counter_evidence_ids": input_fact_ids
            if result.direction == "negative"
            else [],
            "recompute_status": "passed",
            "signal_hash": signal_hash,
        }
        signal_rows[signal_id] = row
        compiled_signals.append(row)
    fact_ids = sorted(all_facts)
    signal_ids = sorted(row["signal_id"] for row in compiled_signals)
    path = _kg_path_from_graph(db, kg["kg_build_id"], fact_ids=fact_ids)
    evidence_bundle_id = _new_id(
        "analysis_bundle", [analysis_build_id, fact_ids, signal_ids]
    )
    expected_nodes = {f"fact:{fact_id}@@{kg['kg_build_id']}" for fact_id in fact_ids}
    observed_nodes = set(path["evidence_node_ids"])
    bundle = {
        "evidence_bundle_id": evidence_bundle_id,
        "analysis_build_id": analysis_build_id,
        "kg_build_id": kg["kg_build_id"],
        "entity_ids": binding["entity_ids"],
        "metric_ids": binding["metric_ids"],
        "period_scope": binding["period_scope"],
        "scope_definition": binding["scope_definition"],
        "fact_ids": fact_ids,
        "derived_fact_ids": [],
        "signal_ids": signal_ids,
        "source_document_ids": [],
        "raw_object_ids": sorted(
            {
                str(row["raw_object_id"])
                for row in all_facts.values()
                if row.get("raw_object_id")
            }
        ),
        "evidence_node_ids": path["evidence_node_ids"],
        "evidence_edges": path["evidence_edges"],
        "evidence_components": path["evidence_components"],
        "supporting_evidence": [
            {"signal_id": row["signal_id"], "fact_ids": row["supporting_evidence_ids"]}
            for row in compiled_signals
            if row["supporting_evidence_ids"]
        ],
        "counter_evidence": [
            {"signal_id": row["signal_id"], "fact_ids": row["counter_evidence_ids"]}
            for row in compiled_signals
            if row["counter_evidence_ids"]
        ],
        "coverage_report": {
            "fact_node_coverage": len(expected_nodes & observed_nodes)
            / len(expected_nodes)
            if expected_nodes
            else 0,
            "expected_fact_node_count": len(expected_nodes),
            "observed_fact_node_count": len(expected_nodes & observed_nodes),
            "component_count": len(path["evidence_components"]),
            "scope_entity_count": len(binding["entity_ids"]),
        },
        "bundle_hash": stable_hash(
            [kg["kg_build_id"], fact_ids, signal_ids, path["evidence_edges"]]
        ),
    }
    claim_result = build_claim_plan(
        pattern,
        compiled_signals,
        entity_name=binding["entity_name"],
        scope_definition=binding["scope_definition"],
    )
    claim_plan_id = _new_id(
        "claim_plan", [analysis_build_id, candidate_id, claim_result.claims]
    )
    claim_plan = {
        "claim_plan_id": claim_plan_id,
        "analysis_build_id": analysis_build_id,
        "candidate_id": candidate_id,
        "claim_graph": claim_result.claims,
        "valid_conclusion_set": claim_result.valid_conclusions,
        "invalid_conclusions": claim_result.invalid_conclusions,
        "mandatory_claim_ids": [
            claim["claim_id"] for claim in claim_result.claims if claim["is_required"]
        ],
        "optional_claim_ids": [
            claim["claim_id"] for claim in claim_result.claims if claim["is_optional"]
        ],
        "forbidden_claim_types": list(pattern.forbidden_claim_types),
        "selected_conclusion_id": claim_result.selected_conclusion_id,
        "plan_hash": stable_hash(
            [
                claim_result.claims,
                claim_result.valid_conclusions,
                claim_result.selected_conclusion_id,
            ]
        ),
        "validation_status": "planned",
    }
    generation = generate_analysis(
        pattern,
        claim_result,
        compiled_signals,
        config=generation_policy,
    )
    conflict_count = sum(row["direction"] == "negative" for row in compiled_signals)
    difficulty_features = {
        "signal_count": len(compiled_signals),
        "signal_category_count": len(
            {row["signal_spec_id"].split("_")[0] for row in compiled_signals}
        ),
        "claim_count": len(claim_result.claims),
        "counter_claim_count": sum(
            claim["claim_role"] == "risk" for claim in claim_result.claims
        ),
        "valid_conclusion_count": len(claim_result.valid_conclusions),
        "evidence_conflict_score": conflict_count / len(compiled_signals),
        "entity_count": len(binding["entity_ids"]),
        "period_count": len(binding["period_scope"]["years"]),
        "metric_count": len(binding["metric_ids"]),
        "required_caveat_count": len(claim_result.caveats),
    }
    difficulty = _analysis_difficulty(pattern.difficulty_base, difficulty_features)
    candidate_hash = stable_hash(
        [
            stable_candidate_id,
            signal_ids,
            bundle["bundle_hash"],
            claim_plan["plan_hash"],
        ]
    )
    candidate = {
        "candidate_id": candidate_id,
        "stable_candidate_id": stable_candidate_id,
        "analysis_build_id": analysis_build_id,
        "analysis_pattern_id": pattern.analysis_pattern_id,
        "pattern_version": pattern.pattern_version,
        "pattern_hash": pattern_row["pattern_hash"],
        "entity_ids": binding["entity_ids"],
        "metric_ids": binding["metric_ids"],
        "period_scope": binding["period_scope"],
        "scope_definition": binding["scope_definition"],
        "signal_ids": signal_ids,
        "evidence_bundle_id": evidence_bundle_id,
        "claim_plan_id": claim_plan_id,
        "instruction": pattern.instruction_template,
        "difficulty": difficulty,
        "difficulty_features": difficulty_features,
        "eligibility_status": "eligible",
        "rejection_reasons": [],
        "candidate_hash": candidate_hash,
    }
    stable_sample_id = _new_id(
        "analysis_sample_stable",
        [stable_candidate_id, generation.selected_conclusion_id],
    )
    sample_id = _new_id("analysis_sample", [analysis_build_id, stable_sample_id])
    cluster_id = _new_id(
        "analysis_cluster",
        [pattern.analysis_pattern_id, sorted(binding["entity_ids"]), fact_ids],
    )
    sample = {
        "analysis_sample_id": sample_id,
        "stable_analysis_sample_id": stable_sample_id,
        "analysis_semantic_cluster_id": cluster_id,
        "evidence_bundle_cluster_id": _new_id("bundle_cluster", fact_ids),
        "signal_composition_id": _new_id(
            "signal_composition",
            sorted(row["signal_spec_id"] for row in compiled_signals),
        ),
        "claim_schema_id": f"{pattern.analysis_pattern_id}@{pattern.pattern_version}",
        "conclusion_family_id": generation.selected_conclusion_id,
        "analysis_build_id": analysis_build_id,
        "candidate_id": candidate_id,
        "instruction": pattern.instruction_template,
        "analysis_text": generation.analysis_text,
        "selected_conclusion_id": generation.selected_conclusion_id,
        "conclusion_text": generation.conclusion_text,
        "claim_alignment": generation.claim_alignment,
        "numeric_slots": generation.numeric_slots,
        "caveats": generation.caveats,
        "rubric": claim_result.rubric,
        "generation_metadata": generation.generation_metadata,
        "generation_method": generation.generation_method,
        "validation_status": "pending",
        "split": None,
    }
    llm_calls = []
    if generation_policy.get("mode") == "controlled_llm":
        attempts = list(generation.generation_metadata.get("llm_attempts") or [])
        final_index = len(attempts)
        for telemetry in attempts:
            attempt_index = int(telemetry.get("attempt_index") or 1)
            is_final = attempt_index == final_index
            llm_calls.append(
                {
                    "llm_call_id": _new_id(
                        "analysis_llm_call",
                        [analysis_build_id, candidate_id, attempt_index],
                    ),
                    "analysis_build_id": analysis_build_id,
                    "attempt_index": attempt_index,
                    "is_final_attempt": is_final,
                    "candidate_id": candidate_id,
                    "analysis_sample_id": sample_id,
                    "provider": telemetry.get("provider"),
                    "endpoint_host": telemetry.get("endpoint_host"),
                    "model_requested": telemetry.get("model_requested"),
                    "response_model": telemetry.get("response_model"),
                    "response_id": telemetry.get("response_id"),
                    "request_hash": telemetry.get("request_hash"),
                    "response_hash": telemetry.get("response_hash"),
                    "http_status": telemetry.get("http_status"),
                    "http_success": bool(telemetry.get("http_success")),
                    "json_valid": bool(telemetry.get("json_valid")),
                    "structured_response_valid": bool(
                        telemetry.get("structured_response_valid")
                    ),
                    "controlled_generation": bool(
                        is_final
                        and generation.generation_method
                        == "controlled_llm_claim_generation"
                    ),
                    "latency_ms": telemetry.get("latency_ms"),
                    "prompt_tokens": telemetry.get("prompt_tokens"),
                    "completion_tokens": telemetry.get("completion_tokens"),
                    "total_tokens": telemetry.get("total_tokens"),
                    "estimated_cost": telemetry.get("estimated_cost"),
                    "fallback_reason": (
                        generation.generation_metadata.get("fallback_reason")
                        if is_final
                        else None
                    ),
                    "error_type": telemetry.get("error_type"),
                    "validation_errors": list(telemetry.get("validation_errors") or []),
                }
            )
    return {
        "candidate": candidate,
        "bundle": bundle,
        "claim_plan": claim_plan,
        "sample": sample,
        "llm_calls": llm_calls,
    }


def _aligned_window(
    series: dict[str, list[dict[str, Any]]],
    metrics: Iterable[str],
    window: int,
) -> dict[str, list[dict[str, Any]]] | None:
    metric_list = list(metrics)
    if not set(metric_list).issubset(series):
        return None
    by_metric = {
        metric: {int(row["fiscal_year"]): row for row in series[metric]}
        for metric in metric_list
    }
    common = sorted(set.intersection(*(set(values) for values in by_metric.values())))
    runs: list[list[int]] = []
    current: list[int] = []
    for year in common:
        if current and year != current[-1] + 1:
            runs.append(current)
            current = []
        current.append(year)
    if current:
        runs.append(current)
    eligible = [run for run in runs if len(run) >= window]
    if not eligible:
        return None
    years = max(eligible, key=lambda values: values[-1])[-window:]
    return {
        metric: [by_metric[metric][year] for year in years] for metric in metric_list
    }


def _fact_score(row: dict[str, Any]) -> tuple[Any, ...]:
    return (
        1 if row.get("verification_status") == "cross_verified" else 0,
        float(row.get("confidence_score") or 0),
        str(row.get("report_date") or ""),
        str(row.get("fact_id") or ""),
    )


def _series_score(rows: list[dict[str, Any]]) -> tuple[Any, ...]:
    return (
        len(rows),
        max(int(row["fiscal_year"]) for row in rows),
        min(float(row.get("confidence_score") or 0) for row in rows),
        str(rows[0].get("source_definition_id") or ""),
    )


def _binding_score(binding: dict[str, Any]) -> tuple[Any, ...]:
    return (
        max(binding["period_scope"]["years"]),
        len(binding["period_scope"]["years"]),
        stable_hash(_binding_identity(binding)),
    )


def _binding_identity(binding: dict[str, Any]) -> Any:
    return {
        "pattern": binding["analysis_pattern_id"],
        "target": binding["target_entity_id"],
        "entities": binding["entity_ids"],
        "period": binding["period_scope"],
        "facts": sorted(
            {
                str(row["fact_id"])
                for signal in binding["signal_inputs"]
                for rows in signal["roles"].values()
                for row in rows
            }
        ),
        "signal_specs": sorted(
            signal["signal_spec_id"] for signal in binding["signal_inputs"]
        ),
    }


def _analysis_difficulty(base: str, features: dict[str, Any]) -> str:
    if base == "hard" and (
        features["counter_claim_count"] >= 2 or features["signal_count"] >= 6
    ):
        return "expert"
    if base == "expert" and (
        features["entity_count"] >= 10
        or features["counter_claim_count"] >= 2
        or features["valid_conclusion_count"] >= 2
    ):
        return "research"
    return base


def _analysis_llm_stats(
    sample_rows: list[dict[str, Any]],
    llm_call_rows: list[dict[str, Any]],
    policy: dict[str, Any],
) -> dict[str, Any]:
    if policy["generation"]["mode"] != "controlled_llm":
        return {
            "mode": policy["generation"]["mode"],
            "request_count": 0,
            "expected_sample_count": len(sample_rows),
            "retry_count": 0,
            "http_success_count": 0,
            "structured_response_pass_count": 0,
            "controlled_generation_count": 0,
            "fallback_count": 0,
            "http_success_rate": 1.0,
            "structured_response_pass_rate": 1.0,
            "controlled_generation_rate": 1.0,
            "fallback_rate": 0.0,
            "retry_rate": 0.0,
            "unknown_fallback_reason_count": 0,
            "fallback_reason_distribution": {},
            "average_latency_ms": None,
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
            "estimated_cost": None,
            "estimated_cost_available_count": 0,
        }
    request_count = len(llm_call_rows)
    sample_count = len(sample_rows)
    fallback_reasons = Counter(
        str((row.get("generation_metadata") or {}).get("fallback_reason"))
        for row in sample_rows
        if (row.get("generation_metadata") or {}).get("fallback_reason")
    )
    fallback_count = sum(fallback_reasons.values())
    latencies = [
        float(row["latency_ms"])
        for row in llm_call_rows
        if row.get("latency_ms") is not None
    ]
    cost_values = [
        float(row["estimated_cost"])
        for row in llm_call_rows
        if row.get("estimated_cost") is not None
    ]
    controlled_samples = sum(
        row.get("generation_method") == "controlled_llm_claim_generation"
        for row in sample_rows
    )
    return {
        "mode": "controlled_llm",
        "request_count": request_count,
        "expected_sample_count": sample_count,
        "retry_count": max(0, request_count - sample_count),
        "http_success_count": sum(
            bool(row.get("http_success")) for row in llm_call_rows
        ),
        "structured_response_pass_count": sum(
            bool(row.get("structured_response_valid")) for row in llm_call_rows
        ),
        "controlled_generation_count": controlled_samples,
        "fallback_count": fallback_count,
        "http_success_rate": sum(bool(row.get("http_success")) for row in llm_call_rows)
        / request_count
        if request_count
        else 0.0,
        "structured_response_pass_rate": sum(
            bool(row.get("structured_response_valid")) for row in llm_call_rows
        )
        / request_count
        if request_count
        else 0.0,
        "controlled_generation_rate": controlled_samples / sample_count
        if sample_count
        else 0.0,
        "fallback_rate": fallback_count / sample_count if sample_count else 1.0,
        "retry_rate": max(0, request_count - sample_count) / sample_count
        if sample_count
        else 0.0,
        "unknown_fallback_reason_count": sum(
            1
            for row in sample_rows
            if row.get("generation_method") != "controlled_llm_claim_generation"
            and not (row.get("generation_metadata") or {}).get("fallback_reason")
        ),
        "fallback_reason_distribution": dict(sorted(fallback_reasons.items())),
        "average_latency_ms": sum(latencies) / len(latencies) if latencies else None,
        "prompt_tokens": sum(
            int(row.get("prompt_tokens") or 0) for row in llm_call_rows
        ),
        "completion_tokens": sum(
            int(row.get("completion_tokens") or 0) for row in llm_call_rows
        ),
        "total_tokens": sum(int(row.get("total_tokens") or 0) for row in llm_call_rows),
        "estimated_cost": sum(cost_values) if cost_values else None,
        "estimated_cost_available_count": len(cost_values),
    }


def _build_gate_failures(
    quality: dict[str, Any],
    pattern_counts: Counter[str],
    policy: dict[str, Any],
    llm_stats: dict[str, Any],
) -> list[str]:
    failures = []
    if quality["pass_rate"] < policy["minimum_pass_rate"]:
        failures.append(
            f"analysis_pass_rate={quality['pass_rate']:.6f} < {policy['minimum_pass_rate']:.6f}"
        )
    for pattern_id, minimum in policy["minimum_pattern_samples"].items():
        if pattern_counts.get(pattern_id, 0) < minimum:
            failures.append(
                f"pattern_{pattern_id}={pattern_counts.get(pattern_id, 0)} < {minimum}"
            )
    if quality["failure_counts"].get("unsupported_numeric_count", 0):
        failures.append("unsupported_numeric_rate must be zero")
    if quality["failure_counts"].get("forbidden_claim_count", 0):
        failures.append("forbidden_claim_rate must be zero")
    if quality["failure_counts"].get("valid_conclusion", 0):
        failures.append("valid_conclusion_rate must be 100%")
    if policy["generation"]["mode"] == "controlled_llm":
        gate = policy["generation"]["api_quality_gate"]
        if llm_stats["request_count"] < llm_stats["expected_sample_count"]:
            failures.append(
                f"analysis_llm_request_count={llm_stats['request_count']} < "
                f"sample_count={llm_stats['expected_sample_count']}"
            )
        maximum_retry_rate = float(gate.get("maximum_retry_rate", 0.05))
        if llm_stats["retry_rate"] > maximum_retry_rate:
            failures.append(
                f"analysis_llm_retry_rate={llm_stats['retry_rate']:.6f} > "
                f"{maximum_retry_rate:.6f}"
            )
        for key, minimum in (
            ("http_success_rate", gate["minimum_http_success_rate"]),
            (
                "structured_response_pass_rate",
                gate["minimum_structured_response_pass_rate"],
            ),
            ("controlled_generation_rate", gate["minimum_controlled_generation_rate"]),
        ):
            if llm_stats[key] < minimum:
                failures.append(
                    f"analysis_llm_{key}={llm_stats[key]:.6f} < {minimum:.6f}"
                )
        if llm_stats["fallback_rate"] > gate["maximum_fallback_rate"]:
            failures.append(
                f"analysis_llm_fallback_rate={llm_stats['fallback_rate']:.6f} > {gate['maximum_fallback_rate']:.6f}"
            )
        if llm_stats["unknown_fallback_reason_count"]:
            failures.append("analysis_llm_unknown_fallback_reason_count must be zero")
    return failures


def _analysis_policy(
    config: dict[str, Any], limit_per_pattern: int | None
) -> dict[str, Any]:
    configured = dict(config.get("analysis") or {})
    quotas = {
        "operating_trend_summary_v1": 500,
        "growth_quality_diagnosis_v1": 500,
        "peer_positioning_v1": 500,
        **dict(configured.get("pattern_quotas") or {}),
    }
    if limit_per_pattern is not None:
        quotas = {
            key: min(int(value), limit_per_pattern) for key, value in quotas.items()
        }
    generation = dict(configured.get("generation") or {})
    generation_mode = str(
        generation.get("mode")
        or configured.get("generation_mode")
        or "deterministic_claim_plan"
    )
    llm_config = dict(generation.get("llm") or configured.get("llm") or {})
    api_gate = dict(generation.get("api_quality_gate") or {})
    generation_policy = {
        "mode": generation_mode,
        "allow_numeric_slots": bool(generation.get("allow_numeric_slots", True)),
        "max_attempts": max(1, min(3, int(generation.get("max_attempts", 2)))),
        "llm": llm_config,
        "api_quality_gate": {
            "minimum_http_success_rate": float(
                api_gate.get("minimum_http_success_rate", 0.98)
            ),
            "minimum_structured_response_pass_rate": float(
                api_gate.get("minimum_structured_response_pass_rate", 0.98)
            ),
            "minimum_controlled_generation_rate": float(
                api_gate.get("minimum_controlled_generation_rate", 0.98)
            ),
            "maximum_fallback_rate": float(api_gate.get("maximum_fallback_rate", 0.02)),
            "maximum_retry_rate": float(api_gate.get("maximum_retry_rate", 0.05)),
        },
    }
    return {
        "window_years": max(int(configured.get("window_years", 3)), 3),
        "peer_min_entities": max(int(configured.get("peer_min_entities", 5)), 2),
        "peer_max_entities": max(int(configured.get("peer_max_entities", 30)), 5),
        "fact_scan_limit": max(int(configured.get("fact_scan_limit", 100000)), 1000),
        "pattern_quotas": quotas,
        "generation": generation_policy,
        "split_policy": {
            "strategy": "entity_scope_component_holdout_v1",
            "train_pct": 70,
            "dev_pct": 10,
            "test_standard_pct": 20,
            "entity_holdout_pct": 10,
            "temporal_holdout_pct": 10,
            "peer_scope_holdout_pct": 10,
            "signal_composition_holdout_pct": 10,
            "conflicting_evidence_holdout_pct": 10,
            **dict(configured.get("split_policy") or {}),
        },
        "minimum_pass_rate": float(configured.get("minimum_pass_rate", 1.0)),
        "minimum_pattern_samples": {
            "operating_trend_summary_v1": 1,
            "growth_quality_diagnosis_v1": 1,
            "peer_positioning_v1": 1,
            **dict(configured.get("minimum_pattern_samples") or {}),
        },
    }


def _manifests() -> dict[str, str]:
    return {
        "signal_registry_manifest_hash": stable_hash(
            {
                "registry": signal_registry_manifest(),
                "signal_executor_version": SIGNAL_EXECUTOR_VERSION,
                "semantic_gate_version": ANALYSIS_SEMANTIC_GATE_VERSION,
            }
        ),
        "analysis_pattern_manifest_hash": stable_hash(analysis_pattern_manifest()),
        "claim_schema_manifest_hash": stable_hash(
            {
                "version": CLAIM_SCHEMA_VERSION,
                "claim_planner_version": CLAIM_PLANNER_VERSION,
                "analysis_generator_version": ANALYSIS_GENERATOR_VERSION,
            }
        ),
        "conclusion_policy_manifest_hash": stable_hash(
            {"version": CONCLUSION_POLICY_VERSION}
        ),
        "analysis_verifier_manifest_hash": stable_hash(
            {
                "version": ANALYSIS_VERIFIER_VERSION,
                "text_parser_version": ANALYSIS_TEXT_PARSER_VERSION,
            }
        ),
    }


def _write_report(report: dict[str, Any], output_dir: str) -> list[Path]:
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    json_path = directory / "financial_analysis_build_report.json"
    md_path = directory / "financial_analysis_build_report.md"
    json_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, default=str) + "\n"
    )
    lines = ["# Financial Analysis Build Report", ""]
    for key in (
        "analysis_build_id",
        "kg_build_id",
        "candidate_count",
        "signal_count",
        "sample_count",
        "pattern_counts",
        "split_counts",
        "build_gate_status",
        "build_gate_failures",
        "activated",
    ):
        lines.append(
            f"- **{key}**: `{json.dumps(report.get(key), ensure_ascii=False, default=str)}`"
        )
    md_path.write_text("\n".join(lines) + "\n")
    return [json_path, md_path]


def _new_id(prefix: str, payload: Any) -> str:
    return f"{prefix}_{stable_hash(payload)[:24]}"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _db_json(db: DBProtocol, value: Any) -> Any:
    if db.__class__.__name__ == "PostgresMetadataDB":
        from psycopg.types.json import Jsonb

        return Jsonb(value)
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
