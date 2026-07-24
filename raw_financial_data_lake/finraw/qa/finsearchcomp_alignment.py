from __future__ import annotations

import hashlib
import json
import math
import re
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

import pandas as pd

from finraw.db.client import DBProtocol
from finraw.qa.schema import ensure_qa_schema
from finraw.qa.store import chunks, insert_rows, json_value


FINSEARCHCOMP_REVISION = "1fd1beea75482e2dd5e2be8f618195d9c6aff176"
FINSEARCHCOMP_RAW_SHA256 = (
    "6437a6dae907ec81002bd817dafc26c3e46e6b6edfde700f22645b1e2aa208c4"
)
FINSEARCHCOMP_ALIGNMENT_VERSION = "finsearchcomp_alignment.v1.2"
FINSEARCHCOMP_TAXONOMY_VERSION = "finsearchcomp_taxonomy.v1.1"
EXPECTED_LABELS = {
    "Time-Sensitive_Data_Fetching(Global)",
    "Time-Sensitive_Data_Fetching(Greater China)",
    "Simple_Historical_Lookup(Global)",
    "Simple_Historical_Lookup(Greater China)",
    "Complex_Historical_Investigation(Global)",
    "Complex_Historical_Investigation(Greater China)",
}
OFFICIAL_REQUIRED_FIELDS = {
    "prompt_id",
    "prompt",
    "response_reference",
    "judge_prompt_template",
    "judge_system_prompt",
    "label",
}
ALIGNMENT_COLUMNS = [
    "alignment_id",
    "qa_id",
    "qa_build_id",
    "alignment_standard",
    "alignment_version",
    "benchmark_task",
    "market_subset",
    "language",
    "topic",
    "subtopic",
    "entity_type",
    "metric_families",
    "source_classes",
    "time_basis",
    "frequency",
    "period_count",
    "time_span_months",
    "answer_type",
    "operation_families",
    "primary_operation_family",
    "operation_depth",
    "scope_size",
    "rubric_type",
    "generation_pipeline",
    "structural_features",
    "completeness_checks",
    "classification_reasons",
    "label_hash",
]
JSON_ALIGNMENT_COLUMNS = {
    "metric_families",
    "source_classes",
    "operation_families",
    "structural_features",
    "completeness_checks",
    "classification_reasons",
}

_TOPIC_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "corporate_fundamentals",
        (
            "revenue",
            "income",
            "profit",
            "assets",
            "liabilities",
            "cash flow",
            "margin",
            "expense",
            "earnings per share",
            "营收",
            "收入",
            "利润",
            "资产",
            "负债",
            "现金流",
            "财报",
            "年报",
        ),
    ),
    (
        "market_data",
        (
            "stock price",
            "closing price",
            "opening price",
            "market capitalization",
            "index",
            "exchange rate",
            "bond yield",
            "股价",
            "收盘价",
            "开盘价",
            "市值",
            "指数",
            "汇率",
            "收益率",
        ),
    ),
    (
        "macroeconomics",
        (
            "gdp",
            "inflation",
            "unemployment",
            "federal funds",
            "interest rate",
            "population",
            "external debt",
            "current account",
            "money supply",
            "bank credit",
            "international investment position",
            "国内生产总值",
            "通胀",
            "失业",
            "利率",
            "人口",
            "外债",
            "经常账户",
            "货币供应",
            "外汇",
        ),
    ),
    (
        "fund_and_portfolio",
        (
            "fund nav",
            "mutual fund",
            "etf",
            "portfolio",
            "holding",
            "基金净值",
            "基金",
            "持仓",
            "组合",
        ),
    ),
    (
        "industry_and_alternative_data",
        (
            "vehicle deliveries",
            "newborn",
            "house price",
            "industry",
            "subscriber",
            "shipment",
            "deliveries",
            "房价",
            "行业",
            "销量",
            "交付量",
            "用户数",
        ),
    ),
)

_METRIC_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("revenue", ("revenue", "sales", "营收", "收入")),
    ("profitability", ("net income", "profit", "margin", "利润", "利润率")),
    ("balance_sheet", ("assets", "liabilities", "debt", "equity", "资产", "负债", "债务")),
    ("cash_flow", ("cash flow", "capital expenditure", "现金流", "资本开支")),
    ("market_price", ("price", "close", "open", "stock", "股价", "收盘", "开盘")),
    ("market_value", ("market cap", "market capitalization", "市值")),
    ("interest_rate", ("interest rate", "federal funds", "yield", "利率", "收益率")),
    ("macro_output", ("gdp", "industrial production", "国内生产总值", "工业增加值")),
    ("inflation", ("inflation", "cpi", "ppi", "通胀", "居民消费价格")),
    ("employment", ("employment", "unemployment", "payroll", "就业", "失业")),
    ("external_sector", ("external debt", "current account", "trade", "外债", "经常账户", "进出口")),
    ("money_and_credit", ("money", "credit", "loan", "货币", "信贷", "贷款")),
    ("population", ("population", "newborn", "人口", "新生儿")),
)


def freeze_finsearchcomp_dataset(
    source_path: str,
    output_dir: str,
    *,
    revision: str = FINSEARCHCOMP_REVISION,
    expected_sha256: str | None = FINSEARCHCOMP_RAW_SHA256,
) -> dict[str, Any]:
    source = Path(source_path)
    raw_bytes = source.read_bytes()
    raw_sha256 = hashlib.sha256(raw_bytes).hexdigest()
    if expected_sha256 and raw_sha256 != expected_sha256:
        raise RuntimeError(
            f"FinSearchComp checksum mismatch: {raw_sha256} != {expected_sha256}"
        )
    rows = json.loads(raw_bytes)
    _validate_official_rows(rows)
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    parquet_path = out / "finsearchcomp_v1.parquet"
    pd.DataFrame(rows).to_parquet(parquet_path, index=False)
    parquet_sha256 = _sha256_file(parquet_path)
    sums_path = out / "SHA256SUMS"
    sums_path.write_text(
        f"{raw_sha256}  finsearchcomp_data.json\n"
        f"{parquet_sha256}  finsearchcomp_v1.parquet\n",
        encoding="utf-8",
    )
    manifest = {
        "dataset_id": "ByteSeedXpert/FinSearchComp",
        "revision": revision,
        "license": "CC BY 4.0",
        "usage": "evaluation_only",
        "contamination_guard": True,
        "row_count": len(rows),
        "raw_schema": sorted({key for row in rows for key in row}),
        "required_schema": sorted(OFFICIAL_REQUIRED_FIELDS),
        "raw_sha256": raw_sha256,
        "parquet_sha256": parquet_sha256,
        "taxonomy_version": FINSEARCHCOMP_TAXONOMY_VERSION,
    }
    manifest_path = out / "official_freeze_manifest.json"
    _write_json(manifest_path, manifest)
    eval_manifest_path = out / "official_evaluation_manifest.jsonl"
    with eval_manifest_path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(
                json.dumps(
                    {
                        "official_item_id": _official_item_id(row),
                        "prompt_id": row["prompt_id"],
                        "label": row["label"],
                        "usage": "evaluation_only",
                        "contamination_guard": True,
                        "prompt_sha256": _text_hash(row.get("prompt")),
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                )
                + "\n"
            )
    manifest["written_files"] = [
        str(parquet_path),
        str(sums_path),
        str(manifest_path),
        str(eval_manifest_path),
    ]
    return manifest


def analyze_official_finsearchcomp(
    frozen_path: str,
    output_dir: str,
) -> dict[str, Any]:
    rows = _read_rows(frozen_path)
    _validate_official_rows(rows)
    annotations = [annotate_official_item(row) for row in rows]
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    taxonomy_path = out / "item_taxonomy.parquet"
    overview_path = out / "official_item_overview.xlsx"
    workbook_path = out / "official_statistics.xlsx"
    _write_taxonomy_parquet(annotations, taxonomy_path)
    pd.DataFrame(_tabular_rows(annotations)).to_excel(overview_path, index=False)
    stats = _official_statistics(rows, annotations)
    _write_official_statistics_workbook(annotations, stats, workbook_path)
    stats_path = out / "official_statistics.json"
    stats_md_path = out / "official_statistics.md"
    _write_json(stats_path, stats)
    stats_md_path.write_text(_official_statistics_markdown(stats), encoding="utf-8")
    annotation_jsonl = out / "item_taxonomy.jsonl"
    _write_jsonl(annotation_jsonl, annotations)
    stats["written_files"] = [
        str(taxonomy_path),
        str(annotation_jsonl),
        str(overview_path),
        str(workbook_path),
        str(stats_path),
        str(stats_md_path),
    ]
    return stats


def annotate_official_item(row: dict[str, Any]) -> dict[str, Any]:
    prompt = str(row.get("prompt") or "")
    reference = str(row.get("response_reference") or "")
    text = f"{prompt} {reference}".casefold()
    benchmark_task = _official_task(str(row.get("label") or ""))
    operation_families = _operation_families(prompt, benchmark_task)
    answer_type = _answer_type(prompt, reference)
    period_count, span_months = _period_features(prompt, benchmark_task)
    topic = _topic(text)
    metric_families = _metric_families(text)
    source_classes = _official_source_classes(text)
    entity_type = _entity_type(text, topic)
    frequency = _frequency(text)
    reasons = [f"official_label:{benchmark_task}"]
    if benchmark_task == "T3":
        reasons.append("official_complex_historical_investigation")
    elif benchmark_task == "T2":
        reasons.append("official_simple_historical_lookup")
    return {
        "item_id": _official_item_id(row),
        "prompt_id": str(row.get("prompt_id")),
        "benchmark_task": benchmark_task,
        "market_subset": _market_subset(str(row.get("label") or "")),
        "language": _language(prompt),
        "topic": topic,
        "subtopic": metric_families[0] if metric_families else "other",
        "entity_type": entity_type,
        "entity_count": _entity_count(prompt, benchmark_task),
        "metric_families": metric_families,
        "source_classes": source_classes,
        "source_count_required": max(len(source_classes), 1),
        "time_basis": _time_basis(text),
        "frequency": frequency,
        "period_count": period_count,
        "time_span_months": span_months,
        "time_span_bucket": _time_span_bucket(span_months),
        "answer_type": answer_type,
        "operation_families": operation_families,
        "primary_operation_family": _primary_operation(operation_families),
        "operation_count": len(operation_families),
        "operation_depth": max(len(operation_families) - 1, 0),
        "requires_unit_normalization": bool(
            re.search(r"unit|million|billion|thousand|单位|亿元|亿美元|十亿美元", text)
        ),
        "requires_currency_normalization": bool(
            re.search(r"currency|usd|dollar|rmb|cny|美元|人民币|汇率", text)
        ),
        "requires_calendar_alignment": bool(
            re.search(r"fiscal|quarter|trading day|财年|季度|交易日", text)
        ),
        "requires_scope_completeness": bool(
            benchmark_task == "T3"
            and re.search(r"among|across|top\s*\d+|which companies|在.*中|前\s*\d+", text)
        ),
        "rubric_type": _rubric_type(reference),
        "annotation_status": "rule_preannotated",
        "manual_review_status": "pending",
        "annotation_confidence": _annotation_confidence(benchmark_task, topic, answer_type),
        "classification_reasons": reasons,
        "usage": "evaluation_only",
        "contamination_guard": True,
        "prompt_sha256": _text_hash(prompt),
        "normalized_prompt_sha256": _text_hash(_normalize_question(prompt)),
        "taxonomy_version": FINSEARCHCOMP_TAXONOMY_VERSION,
    }


def align_qa_build_to_finsearchcomp(
    db: DBProtocol,
    qa_build_id: str,
    official_taxonomy_path: str,
    output_dir: str,
    *,
    target_t2_count: int = 3000,
    target_t3_count: int = 1500,
) -> dict[str, Any]:
    ensure_qa_schema(db)
    build = db.fetchone(
        "SELECT qa_build_id, kg_build_id, status FROM qa_builds WHERE qa_build_id = ?",
        (qa_build_id,),
    )
    if not build:
        raise RuntimeError(f"Unknown QA build: {qa_build_id}")
    official = _read_taxonomy(official_taxonomy_path)
    official = [row for row in official if row.get("benchmark_task") in {"T2", "T3"}]
    current = _current_qa_taxonomy(db, qa_build_id)
    _persist_current_labels(db, current)
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    current_parquet = out / "current_qa_taxonomy.parquet"
    current_jsonl = out / "current_qa_taxonomy.jsonl"
    _write_taxonomy_parquet(current, current_parquet)
    _write_jsonl(current_jsonl, current)
    matrix = _coverage_matrix(official, current)
    matrix_csv = out / "coverage_matrix.csv"
    matrix_xlsx = out / "coverage_matrix.xlsx"
    matrix.to_csv(matrix_csv, index=False)
    matrix.to_excel(matrix_xlsx, index=False)
    distances = _distribution_distances(official, current)
    contamination = _contamination_report(official, current)
    gaps = _gap_manifest(
        official,
        current,
        {"T2": target_t2_count, "T3": target_t3_count},
    )
    gap_path = out / "gap_manifest.json"
    _write_json(gap_path, gaps)
    agent_path, hidden_path = _write_agent_views(current, out)
    report = {
        "alignment_standard": "finsearchcomp",
        "alignment_version": FINSEARCHCOMP_ALIGNMENT_VERSION,
        "taxonomy_version": FINSEARCHCOMP_TAXONOMY_VERSION,
        "qa_build_id": qa_build_id,
        "kg_build_id": build["kg_build_id"],
        "official_evaluation_item_count": len(official),
        "current_passed_item_count": len(current),
        "official_task_counts": dict(sorted(Counter(row["benchmark_task"] for row in official).items())),
        "current_task_counts": dict(sorted(Counter(row["benchmark_task"] for row in current).items())),
        "current_pipeline_counts": dict(sorted(Counter(row["generation_pipeline"] for row in current).items())),
        "distribution_distances": distances,
        "coverage_summary": _coverage_summary(matrix),
        "question_completeness": _completeness_summary(current),
        "execution_quality": {
            "population": "passed_qa_samples",
            "verifier_pass_rate": 1.0 if current else 0.0,
            "operation_plan_replay_required": True,
            "official_benchmark_gain_status": "not_run",
        },
        "contamination": contamination,
        "gap_summary": gaps["summary"],
        "usage_policy": {
            "official_dataset": "evaluation_only",
            "official_prompt_rewrites_for_training": False,
            "current_qa": "training_or_internal_evaluation_according_to_split",
        },
    }
    report_path = out / "finsearchcomp_alignment_report.json"
    report_md_path = out / "finsearchcomp_alignment_report.md"
    _write_json(report_path, report)
    report_md_path.write_text(_alignment_markdown(report), encoding="utf-8")
    report["written_files"] = [
        str(current_parquet),
        str(current_jsonl),
        str(matrix_csv),
        str(matrix_xlsx),
        str(gap_path),
        str(agent_path),
        str(hidden_path),
        str(report_path),
        str(report_md_path),
    ]
    return report


def _current_qa_taxonomy(db: DBProtocol, qa_build_id: str) -> list[dict[str, Any]]:
    rows = [
        dict(row)
        for row in db.fetchall(
            """
            SELECT s.qa_id, s.qa_build_id, s.candidate_id, s.question,
                   s.language, s.answer_type AS sample_answer_type, s.unit,
                   s.currency, s.rubric, s.task_subtype, s.difficulty,
                   s.validation_status, s.split, c.pattern_id,
                   c.pattern_proposal_id, c.entity_ids, c.metric_ids,
                   c.time_scope, c.entity_scope, c.source_fact_ids,
                   c.source_derived_ids, c.source_document_ids,
                   c.canonical_semantics, c.graph_features, c.answer_schema,
                   p.operator_dag
            FROM qa_samples s
            JOIN qa_candidates c ON c.candidate_id = s.candidate_id
            LEFT JOIN qa_operation_plans p ON p.candidate_id = c.candidate_id
            WHERE s.qa_build_id = ? AND s.validation_status = 'passed'
            ORDER BY s.qa_id
            """,
            (qa_build_id,),
        )
    ]
    decoded = [_decode_current_row(row) for row in rows]
    fact_ids = sorted(
        {
            str(fact_id)
            for row in decoded
            for fact_id in row["source_fact_ids"]
        }
    )
    fact_sources: dict[str, str] = {}
    for batch in chunks(fact_ids, 1000):
        placeholders = ",".join("?" for _ in batch)
        for fact in db.fetchall(
            f"SELECT fact_id, source_id FROM standardized_facts WHERE fact_id IN ({placeholders})",
            batch,
        ):
            fact_sources[str(fact["fact_id"])] = str(fact.get("source_id") or "")
    output = []
    for row in decoded:
        source_ids = sorted(
            {
                fact_sources.get(str(fact_id), "")
                for fact_id in row["source_fact_ids"]
                if fact_sources.get(str(fact_id), "")
            }
        )
        semantics = row["canonical_semantics"]
        explicit_source = str(semantics.get("source_id") or "")
        if explicit_source:
            source_ids = sorted(set(source_ids) | {explicit_source})
        output.append(_annotate_current_item(row, source_ids))
    return output


def _annotate_current_item(row: dict[str, Any], source_ids: list[str]) -> dict[str, Any]:
    semantics = row["canonical_semantics"]
    features = row["graph_features"]
    plan = row["operator_dag"]
    operators = [
        str(step.get("operator"))
        for step in plan.get("operators", [])
        if step.get("operator")
    ] or _legacy_operations(str(row.get("task_subtype") or ""))
    operation_families = _normalize_operation_families(operators)
    entity_ids = row["entity_ids"]
    metric_ids = row["metric_ids"]
    period_count = int(features.get("period_count") or 0)
    if not period_count:
        period_count = _legacy_period_count(str(row.get("task_subtype") or ""), row)
    entity_count = int(features.get("entity_count") or len(entity_ids))
    operation_depth = int(
        row.get("operation_depth")
        or features.get("operation_depth")
        or max(len(operators), 0)
    )
    scope_size = int(features.get("scope_size") or len(entity_ids))
    answer_type = _normalize_answer_type(
        str(row["answer_schema"].get("type") or row.get("sample_answer_type") or "numeric")
    )
    source_classes = sorted({_source_class(source_id) for source_id in source_ids})
    source_count = len(source_classes)
    scope_complete = bool(
        scope_size > 1
        and (
            "rank" in operators
            or "filter" in operators
            or "multi_factor_screen" in operators
            or row.get("entity_scope")
        )
    )
    t3_reasons = []
    if period_count >= 3:
        t3_reasons.append("period_count>=3")
    if entity_count >= 2:
        t3_reasons.append("entity_count>=2")
    if operation_depth >= 2:
        t3_reasons.append("operation_depth>=2")
    if source_count >= 2:
        t3_reasons.append("source_count>=2")
    if scope_complete:
        t3_reasons.append("scope_completeness")
    if answer_type in {"list", "table", "ranking", "ranked_table", "screening_table"}:
        t3_reasons.append("structured_multi_item_answer")
    benchmark_task = "T3" if t3_reasons else "T2"
    question = str(row.get("question") or "")
    time_scope = row["time_scope"]
    span_months = _current_span_months(time_scope, period_count)
    topic = _topic(" ".join([question, *metric_ids, *source_ids]).casefold())
    metric_families = sorted(
        set(_metric_families(" ".join([question, *metric_ids]).casefold()))
    )
    if not metric_families:
        metric_families = [str(metric).replace("_", " ") for metric in metric_ids]
    rubric = dict(row.get("rubric") or {})
    requested_unit = str(rubric.get("requested_unit") or row.get("unit") or "")
    requested_currency = (
        str(rubric.get("requested_currency") or "")
        if "requested_currency" in rubric
        else str(row.get("currency") or "")
    )
    completeness = _question_completeness(
        question,
        unit=requested_unit,
        currency=requested_currency,
        time_scope=time_scope,
        benchmark_task=benchmark_task,
        precision_required=bool(rubric.get("precision_must_match")),
    )
    generation_pipeline = _generation_pipeline(row)
    payload = {
        "qa_id": str(row["qa_id"]),
        "qa_build_id": str(row["qa_build_id"]),
        "alignment_standard": "finsearchcomp",
        "alignment_version": FINSEARCHCOMP_ALIGNMENT_VERSION,
        "benchmark_task": benchmark_task,
        "market_subset": _current_market(source_ids, entity_ids),
        "language": str(row.get("language") or _language(question)),
        "topic": topic,
        "subtopic": metric_families[0] if metric_families else "other",
        "entity_type": str(semantics.get("entity_type") or ("listed_company" if any(item.endswith("_US") for item in entity_ids) else "other")),
        "metric_families": metric_families,
        "source_classes": source_classes or ["unknown"],
        "time_basis": str(time_scope.get("basis") or semantics.get("time_basis") or "unknown"),
        "frequency": str(semantics.get("frequency") or time_scope.get("frequency") or _current_frequency(time_scope)),
        "period_count": period_count,
        "time_span_months": span_months,
        "time_span_bucket": _time_span_bucket(span_months),
        "answer_type": answer_type,
        "operation_families": operation_families,
        "primary_operation_family": _primary_operation(operation_families),
        "operation_depth": operation_depth,
        "scope_size": scope_size,
        "rubric_type": _current_rubric_type(row["rubric"]),
        "generation_pipeline": generation_pipeline,
        "structural_features": {
            "entity_count": entity_count,
            "metric_count": int(features.get("metric_count") or len(metric_ids)),
            "source_count_for_answer": source_count,
            "fact_count": int(features.get("fact_count") or len(row["source_fact_ids"])),
            "derived_fact_count": int(features.get("derived_fact_count") or len(row["source_derived_ids"])),
            "requires_scope_completeness": scope_complete,
            "requires_cross_source_join": source_count >= 2,
            "requires_external_tool": True,
            "agent_view": "question_plus_tools",
            "hidden_gold_available": True,
        },
        "completeness_checks": completeness,
        "classification_reasons": t3_reasons or ["fixed_historical_low_depth"],
        "question": question,
        "normalized_question_sha256": _text_hash(_normalize_question(question)),
        "candidate_id": str(row["candidate_id"]),
        "split": row.get("split"),
        "difficulty": row.get("difficulty"),
        "source_fact_ids": row["source_fact_ids"],
        "source_derived_ids": row["source_derived_ids"],
        "source_document_ids": row["source_document_ids"],
        "source_ids": source_ids,
        "operation_plan": plan,
        "time_scope": time_scope,
        "entity_ids": entity_ids,
        "metric_ids": metric_ids,
        "quality_status": "passed",
    }
    label_material = {
        key: payload[key]
        for key in (
            "benchmark_task",
            "market_subset",
            "topic",
            "entity_type",
            "metric_families",
            "source_classes",
            "frequency",
            "period_count",
            "answer_type",
            "operation_families",
            "scope_size",
        )
    }
    payload["label_hash"] = _stable_hash(label_material)
    payload["alignment_id"] = "qaalign_" + _stable_hash(
        [payload["qa_id"], FINSEARCHCOMP_ALIGNMENT_VERSION]
    )[:24]
    return payload


def _persist_current_labels(db: DBProtocol, rows: list[dict[str, Any]]) -> None:
    insert_rows(
        db,
        "qa_distribution_labels",
        rows,
        ALIGNMENT_COLUMNS,
        JSON_ALIGNMENT_COLUMNS,
    )


def _coverage_matrix(
    official: list[dict[str, Any]], current: list[dict[str, Any]]
) -> pd.DataFrame:
    dimensions = [
        "market_subset",
        "language",
        "topic",
        "entity_type",
        "frequency",
        "answer_type",
        "primary_operation_family",
        "time_span_bucket",
        "rubric_type",
    ]
    records = []
    for dimension in dimensions:
        categories = sorted(
            {str(row.get(dimension) or "unknown") for row in official + current}
        )
        for task in ("T2", "T3"):
            official_task = [row for row in official if row["benchmark_task"] == task]
            current_task = [row for row in current if row["benchmark_task"] == task]
            for category in categories:
                official_count = sum(
                    str(row.get(dimension) or "unknown") == category
                    for row in official_task
                )
                current_count = sum(
                    str(row.get(dimension) or "unknown") == category
                    for row in current_task
                )
                if not official_count and not current_count:
                    continue
                records.append(
                    {
                        "dimension": dimension,
                        "category": category,
                        "benchmark_task": task,
                        "official_count": official_count,
                        "official_share": official_count / len(official_task) if official_task else 0.0,
                        "current_count": current_count,
                        "current_share": current_count / len(current_task) if current_task else 0.0,
                        "covered": bool(not official_count or current_count),
                    }
                )
    return pd.DataFrame(records)


def _distribution_distances(
    official: list[dict[str, Any]], current: list[dict[str, Any]]
) -> dict[str, Any]:
    dimensions = [
        "benchmark_task",
        "market_subset",
        "language",
        "topic",
        "entity_type",
        "frequency",
        "answer_type",
        "primary_operation_family",
        "time_span_bucket",
        "rubric_type",
    ]
    report: dict[str, Any] = {}
    for dimension in dimensions:
        report[dimension] = _distance_for_dimension(official, current, dimension)
    report["conditional"] = {}
    for task in ("T2", "T3"):
        left = [row for row in official if row["benchmark_task"] == task]
        right = [row for row in current if row["benchmark_task"] == task]
        report["conditional"][task] = {
            dimension: _distance_for_dimension(left, right, dimension)
            for dimension in (
                "topic",
                "answer_type",
                "primary_operation_family",
                "time_span_bucket",
                "source_class_primary",
            )
        }
    return report


def _distance_for_dimension(
    official: list[dict[str, Any]], current: list[dict[str, Any]], dimension: str
) -> dict[str, Any]:
    def value(row: dict[str, Any]) -> str:
        if dimension == "source_class_primary":
            return str(next(iter(row.get("source_classes") or []), "unknown"))
        return str(row.get(dimension) or "unknown")

    left = Counter(value(row) for row in official)
    right = Counter(value(row) for row in current)
    categories = sorted(set(left) | set(right))
    p = [left[item] / len(official) if official else 0.0 for item in categories]
    q = [right[item] / len(current) if current else 0.0 for item in categories]
    return {
        "tvd": 0.5 * sum(abs(a - b) for a, b in zip(p, q)),
        "jsd": _jensen_shannon(p, q),
        "official_category_count": len(left),
        "current_category_count": len(right),
        "category_coverage_rate": (
            len(set(left) & set(right)) / len(left) if left else 1.0
        ),
    }


def _gap_manifest(
    official: list[dict[str, Any]],
    current: list[dict[str, Any]],
    target_totals: dict[str, int],
) -> dict[str, Any]:
    dimensions = (
        "benchmark_task",
        "market_subset",
        "topic",
        "primary_operation_family",
        "frequency",
        "time_span_bucket",
        "answer_type",
    )
    official_groups = Counter(tuple(str(row.get(key) or "unknown") for key in dimensions) for row in official)
    current_groups = Counter(tuple(str(row.get(key) or "unknown") for key in dimensions) for row in current)
    task_counts = Counter(row["benchmark_task"] for row in official)
    current_topics = {str(row.get("topic")) for row in current}
    gaps = []
    for key, official_count in official_groups.items():
        values = dict(zip(dimensions, key))
        task = values["benchmark_task"]
        target = max(
            1,
            round(target_totals[task] * official_count / task_counts[task]),
        )
        current_count = current_groups.get(key, 0)
        gap = max(target - current_count, 0)
        gaps.append(
            {
                **values,
                "official_count": official_count,
                "official_share_within_task": official_count / task_counts[task],
                "target_count": target,
                "current_count": current_count,
                "gap": gap,
                "source_capability_status": (
                    "present" if values["topic"] in current_topics else "not_yet_present"
                ),
                "priority_score": gap * (1.0 + (0.5 if current_count == 0 else 0.0)),
            }
        )
    gaps.sort(key=lambda row: (-row["priority_score"], row["benchmark_task"], row["topic"]))
    return {
        "alignment_version": FINSEARCHCOMP_ALIGNMENT_VERSION,
        "target_totals": target_totals,
        "summary": {
            "group_count": len(gaps),
            "uncovered_group_count": sum(row["current_count"] == 0 for row in gaps),
            "total_requested_gap": sum(row["gap"] for row in gaps),
            "t2_requested_gap": sum(row["gap"] for row in gaps if row["benchmark_task"] == "T2"),
            "t3_requested_gap": sum(row["gap"] for row in gaps if row["benchmark_task"] == "T3"),
        },
        "gaps": gaps,
    }


def _contamination_report(
    official: list[dict[str, Any]], current: list[dict[str, Any]]
) -> dict[str, Any]:
    official_hashes = {
        str(row.get("normalized_prompt_sha256") or "")
        for row in official
        if row.get("normalized_prompt_sha256")
    }
    matches = [
        row["qa_id"]
        for row in current
        if row.get("normalized_question_sha256") in official_hashes
    ]
    return {
        "comparison": "normalized_exact_hash",
        "official_hash_count": len(official_hashes),
        "current_hash_count": len({row.get("normalized_question_sha256") for row in current}),
        "exact_match_count": len(matches),
        "matched_qa_ids": matches,
        "passed": not matches,
        "near_duplicate_review_status": "not_run",
    }


def _write_agent_views(
    rows: list[dict[str, Any]], out: Path
) -> tuple[Path, Path]:
    agent_path = out / "agent_input_manifest.jsonl"
    hidden_path = out / "hidden_gold_manifest.jsonl"
    with agent_path.open("w", encoding="utf-8") as agent, hidden_path.open(
        "w", encoding="utf-8"
    ) as hidden:
        for row in rows:
            tools = _tools_for_sources(row.get("source_ids") or [])
            agent.write(
                json.dumps(
                    {
                        "qa_id": row["qa_id"],
                        "question": row["question"],
                        "available_tools": tools,
                        "benchmark_task": row["benchmark_task"],
                        "market_subset": row["market_subset"],
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                )
                + "\n"
            )
            hidden.write(
                json.dumps(
                    {
                        "qa_id": row["qa_id"],
                        "source_fact_ids": row["source_fact_ids"],
                        "source_derived_ids": row["source_derived_ids"],
                        "source_document_ids": row["source_document_ids"],
                        "operation_plan": row["operation_plan"],
                        "entity_ids": row["entity_ids"],
                        "metric_ids": row["metric_ids"],
                        "time_scope": row["time_scope"],
                        "quality_status": row["quality_status"],
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                    default=str,
                )
                + "\n"
            )
    return agent_path, hidden_path


def _validate_official_rows(rows: Any) -> None:
    if not isinstance(rows, list) or not rows:
        raise RuntimeError("FinSearchComp source must be a non-empty JSON array")
    prompt_ids = [str(row.get("prompt_id") or "") for row in rows]
    if any(not item for item in prompt_ids):
        raise RuntimeError("FinSearchComp prompt_id values must be non-empty")
    item_ids = [_official_item_id(row) for row in rows]
    if len(set(item_ids)) != len(item_ids):
        raise RuntimeError(
            "FinSearchComp (label, prompt_id) values must form a unique item identity"
        )
    labels = {str(row.get("label") or "") for row in rows}
    if labels != EXPECTED_LABELS:
        raise RuntimeError(f"Unexpected FinSearchComp labels: {sorted(labels)}")
    present_fields = {key for row in rows for key in row}
    missing = OFFICIAL_REQUIRED_FIELDS - present_fields
    if missing:
        raise RuntimeError(f"Missing FinSearchComp fields: {sorted(missing)}")


def _official_item_id(row: dict[str, Any]) -> str:
    return f"{row.get('label', '')}::{row.get('prompt_id', '')}"


def _official_statistics(
    rows: list[dict[str, Any]], annotations: list[dict[str, Any]]
) -> dict[str, Any]:
    fields = sorted({key for row in rows for key in row})
    prompt_lengths = [len(str(row.get("prompt") or "")) for row in rows]
    answer_lengths = [len(str(row.get("response_reference") or "")) for row in rows]
    expected_viewer_fields = [
        "wind_ticker",
        "akshare_ticker",
        "yfinance_ticker",
        "ground_truth",
        "time",
        "response_reference_translate",
    ]
    return {
        "dataset_id": "ByteSeedXpert/FinSearchComp",
        "revision": FINSEARCHCOMP_REVISION,
        "license": "CC BY 4.0",
        "usage": "evaluation_only",
        "contamination_guard": True,
        "row_count": len(rows),
        "raw_fields": fields,
        "viewer_only_or_absent_fields": {
            field: "not_present_in_frozen_raw_json"
            for field in expected_viewer_fields
            if field not in fields
        },
        "label_distribution": dict(sorted(Counter(str(row.get("label")) for row in rows).items())),
        "task_distribution": dict(sorted(Counter(row["benchmark_task"] for row in annotations).items())),
        "market_distribution": dict(sorted(Counter(row["market_subset"] for row in annotations).items())),
        "task_market_distribution": _joint_counts(annotations, "benchmark_task", "market_subset"),
        "language_distribution": dict(sorted(Counter(row["language"] for row in annotations).items())),
        "topic_distribution": dict(sorted(Counter(row["topic"] for row in annotations).items())),
        "answer_type_distribution": dict(sorted(Counter(row["answer_type"] for row in annotations).items())),
        "rubric_distribution": dict(sorted(Counter(row["rubric_type"] for row in annotations).items())),
        "prompt_length": _numeric_summary(prompt_lengths),
        "answer_length": _numeric_summary(answer_lengths),
        "missing_rate": {
            field: sum(_is_missing(row.get(field)) for row in rows) / len(rows)
            for field in fields
        },
        "annotation_status": {
            "rule_preannotated": len(annotations),
            "manual_review_pending": len(annotations),
        },
    }


def _official_statistics_markdown(stats: dict[str, Any]) -> str:
    lines = [
        "# FinSearchComp Official Statistics",
        "",
        f"- Revision: `{stats['revision']}`",
        f"- Rows: `{stats['row_count']}`",
        f"- Usage: `{stats['usage']}`",
        f"- Raw fields: `{', '.join(stats['raw_fields'])}`",
        "",
        "## Task Distribution",
        "",
    ]
    lines.extend(f"- `{key}`: `{value}`" for key, value in stats["task_distribution"].items())
    lines.extend(["", "## Market Distribution", ""])
    lines.extend(f"- `{key}`: `{value}`" for key, value in stats["market_distribution"].items())
    lines.extend(["", "## Topic Distribution", ""])
    lines.extend(f"- `{key}`: `{value}`" for key, value in stats["topic_distribution"].items())
    lines.extend(
        [
            "",
            "## Annotation Status",
            "",
            "All semantic taxonomy fields are deterministic pre-annotations and remain pending human review.",
            "",
        ]
    )
    return "\n".join(lines)


def _write_official_statistics_workbook(
    annotations: list[dict[str, Any]], stats: dict[str, Any], path: Path
) -> None:
    distributions = {
        "task": stats["task_distribution"],
        "market": stats["market_distribution"],
        "language": stats["language_distribution"],
        "topic": stats["topic_distribution"],
        "answer_type": stats["answer_type_distribution"],
        "rubric": stats["rubric_distribution"],
    }
    with pd.ExcelWriter(path) as writer:
        pd.DataFrame(_tabular_rows(annotations)).to_excel(
            writer, sheet_name="items", index=False
        )
        for sheet_name, values in distributions.items():
            pd.DataFrame(
                [{"category": key, "count": value} for key, value in values.items()]
            ).to_excel(writer, sheet_name=sheet_name, index=False)
        pd.DataFrame(
            [
                {"field": field, "missing_rate": rate}
                for field, rate in stats["missing_rate"].items()
            ]
        ).to_excel(writer, sheet_name="missingness", index=False)


def _alignment_markdown(report: dict[str, Any]) -> str:
    coverage = report["coverage_summary"]
    contamination = report["contamination"]
    lines = [
        "# FinSearchComp Distribution Alignment Report",
        "",
        f"- QA build: `{report['qa_build_id']}`",
        f"- KG build: `{report['kg_build_id']}`",
        f"- Official T2/T3 items: `{report['official_evaluation_item_count']}`",
        f"- Current passed QA items: `{report['current_passed_item_count']}`",
        f"- Official tasks: `{report['official_task_counts']}`",
        f"- Current tasks: `{report['current_task_counts']}`",
        f"- Exact contamination matches: `{contamination['exact_match_count']}`",
        f"- Coverage matrix rows: `{coverage['row_count']}`",
        f"- Official categories covered: `{coverage['official_category_coverage_rate']:.2%}`",
        "",
        "## Pipeline Distribution",
        "",
    ]
    lines.extend(
        f"- `{key}`: `{value}`" for key, value in report["current_pipeline_counts"].items()
    )
    lines.extend(["", "## Distribution Distances", ""])
    for key, value in report["distribution_distances"].items():
        if key == "conditional":
            continue
        lines.append(f"- `{key}`: TVD `{value['tvd']:.4f}`, JSD `{value['jsd']:.4f}`")
    lines.extend(
        [
            "",
            "## Validation State",
            "",
            "- Structural labels and distribution gaps are complete.",
            "- Official benchmark gain is not yet measured and remains a required downstream experiment.",
            "- Official prompts remain evaluation-only and are excluded from training exports.",
            "",
        ]
    )
    return "\n".join(lines)


def _read_rows(path: str) -> list[dict[str, Any]]:
    source = Path(path)
    if source.suffix == ".parquet":
        return _records_from_frame(pd.read_parquet(source))
    data = json.loads(source.read_text(encoding="utf-8"))
    if isinstance(data, list):
        return [dict(row) for row in data]
    raise RuntimeError(f"Unsupported official dataset shape: {source}")


def _read_taxonomy(path: str) -> list[dict[str, Any]]:
    source = Path(path)
    if source.suffix == ".parquet":
        rows = _records_from_frame(pd.read_parquet(source))
    else:
        rows = [json.loads(line) for line in source.read_text(encoding="utf-8").splitlines() if line.strip()]
    for row in rows:
        for key in ("metric_families", "source_classes", "operation_families", "classification_reasons"):
            row[key] = json_value(row.get(key), [])
    return rows


def _records_from_frame(frame: pd.DataFrame) -> list[dict[str, Any]]:
    return [
        {key: None if _is_missing(value) else value for key, value in row.items()}
        for row in frame.to_dict("records")
    ]


def _is_missing(value: Any) -> bool:
    if value is None or (isinstance(value, str) and not value.strip()):
        return True
    try:
        missing = pd.isna(value)
    except (TypeError, ValueError):
        return False
    return bool(missing) if isinstance(missing, bool) else False


def _decode_current_row(row: dict[str, Any]) -> dict[str, Any]:
    for key, default in {
        "entity_ids": [],
        "metric_ids": [],
        "time_scope": {},
        "entity_scope": {},
        "source_fact_ids": [],
        "source_derived_ids": [],
        "source_document_ids": [],
        "canonical_semantics": {},
        "graph_features": {},
        "answer_schema": {},
        "operator_dag": {},
        "rubric": {},
    }.items():
        row[key] = json_value(row.get(key), default)
    return row


def _write_taxonomy_parquet(rows: list[dict[str, Any]], path: Path) -> None:
    pd.DataFrame(_tabular_rows(rows)).to_parquet(path, index=False)


def _tabular_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            key: (
                json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
                if isinstance(value, (dict, list))
                else value
            )
            for key, value in row.items()
        }
        for row in rows
    ]


def _write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, default=str)
        + "\n",
        encoding="utf-8",
    )


def _write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(
                json.dumps(row, ensure_ascii=False, sort_keys=True, default=str) + "\n"
            )


def _official_task(label: str) -> str:
    if label.startswith("Time-Sensitive"):
        return "T1"
    if label.startswith("Simple_Historical"):
        return "T2"
    if label.startswith("Complex_Historical"):
        return "T3"
    return "unknown"


def _market_subset(label: str) -> str:
    return "greater_china" if "Greater China" in label else "global"


def _language(text: str) -> str:
    chinese = len(re.findall(r"[\u4e00-\u9fff]", text))
    latin = len(re.findall(r"[A-Za-z]", text))
    if chinese and latin:
        return "mixed"
    if chinese:
        return "zh"
    return "en"


def _topic(text: str) -> str:
    scores = {
        topic: sum(term in text for term in terms) for topic, terms in _TOPIC_RULES
    }
    best = max(scores, key=scores.get)
    return best if scores[best] else "other_financial"


def _metric_families(text: str) -> list[str]:
    return [family for family, terms in _METRIC_RULES if any(term in text for term in terms)]


def _entity_type(text: str, topic: str) -> str:
    if re.search(r"country|countries|china|united states|国家|中国|美国", text):
        return "country_or_region"
    if re.search(r"index|s&p|dow jones|nasdaq|指数", text):
        return "index"
    if re.search(r"fund|etf|基金", text):
        return "fund"
    if re.search(r"company|corp|inc\.?|stock|公司|股票", text):
        return "listed_company"
    if topic == "macroeconomics":
        return "country_or_region"
    return "other"


def _entity_count(prompt: str, benchmark_task: str) -> int:
    if benchmark_task != "T3":
        return 1
    if re.search(r"among|across|which companies|between .* and |在.*中|分别|三家|前\s*\d+", prompt, re.I):
        return 2
    return 1


def _official_source_classes(text: str) -> list[str]:
    classes = []
    rules = {
        "company_filing": ("annual report", "filing", "official disclosure", "年报", "官方披露"),
        "government_or_regulator": ("federal reserve", "imf", "world bank", "united nations", "统计局", "央行", "证监会"),
        "professional_database": ("reuters", "wind", "yfinance", "akshare", "数据库", "路透"),
        "market_data": ("stock price", "closing price", "opening price", "股价", "收盘价", "开盘价"),
    }
    for source_class, terms in rules.items():
        if any(term in text for term in terms):
            classes.append(source_class)
    return classes or ["unspecified_authoritative_source"]


def _source_class(source_id: str) -> str:
    source = source_id.casefold()
    if source.startswith("sec_"):
        return "company_filing"
    if source.startswith("cninfo"):
        return "company_filing"
    if source.startswith(("fred_", "worldbank_", "imf_")):
        return "government_or_regulator"
    return "other_database"


def _frequency(text: str) -> str:
    if re.search(r"daily|trading day|day after|单日|交易日|每日", text):
        return "daily"
    if re.search(r"month|monthly|月", text):
        return "monthly"
    if re.search(r"quarter|quarterly|q[1-4]|季度", text):
        return "quarterly"
    if re.search(r"year|annual|fy\s*\d{4}|年度|全年|财年", text):
        return "annual"
    return "point_in_time"


def _time_basis(text: str) -> str:
    if re.search(r"fiscal|fy\s*\d{4}|财年", text):
        return "fiscal_period"
    if re.search(r"trading day|交易日", text):
        return "trading_calendar"
    if re.search(r"as of|截至|截止", text):
        return "as_of_date"
    return "calendar_period"


def _period_features(prompt: str, benchmark_task: str) -> tuple[int, int]:
    years = sorted({int(year) for year in re.findall(r"(?<!\d)(20\d{2}|19\d{2})(?!\d)", prompt)})
    span_months = 0
    if len(years) >= 2:
        span_months = (max(years) - min(years)) * 12
    range_match = re.search(
        r"(?:from|between|during|自|从)\D*(20\d{2}|19\d{2}).{0,40}?(?:to|through|and|至|到|-|—)\D*(20\d{2}|19\d{2})",
        prompt,
        re.I,
    )
    if range_match:
        start, end = map(int, range_match.groups())
        span_months = abs(end - start) * 12
    if benchmark_task == "T2":
        period_count = 2 if re.search(r"yoy|hoh|year.over.year|同比|环比|较.*增长", prompt, re.I) else 1
    elif span_months:
        period_count = max(span_months // 12 + 1, 2)
    else:
        period_count = max(len(years), 2)
    if re.search(r"month|monthly|月", prompt, re.I) and span_months:
        period_count = max(span_months + 1, period_count)
    return period_count, span_months


def _time_span_bucket(months: int) -> str:
    if months <= 0:
        return "single_period"
    if months <= 12:
        return "up_to_1y"
    if months <= 36:
        return "1y_to_3y"
    if months <= 120:
        return "3y_to_10y"
    return "10y_plus"


def _operation_families(prompt: str, benchmark_task: str) -> list[str]:
    text = prompt.casefold()
    operations = ["lookup"]
    rules = (
        ("temporal_extreme", r"largest|smallest|highest|lowest|maximum|minimum|fastest|最大|最小|最高|最低|最快"),
        ("filter", r"among|that had|which companies|筛选|满足|在.*中"),
        ("rank", r"top\s*\d+|rank|sorted|前\s*\d+|排名|排序"),
        ("growth", r"growth|increase|decrease|yoy|hoh|增长率|涨跌幅|同比|环比"),
        ("difference", r"difference|higher.*lower|相差|差额|差值"),
        ("ratio", r"ratio|proportion|share|percentage|占比|比例"),
        ("aggregate", r"sum|average|mean|total of|合计|总和|平均"),
        ("date_distance", r"how many days|difference.*days|相隔.*天|多少天"),
    )
    for operation, pattern in rules:
        if re.search(pattern, text, re.I):
            operations.append(operation)
    if benchmark_task == "T3" and len(operations) == 1:
        operations.append("multi_source_synthesis")
    return list(dict.fromkeys(operations))


def _legacy_operations(task_subtype: str) -> list[str]:
    mapping = {
        "single_fact": ["lookup"],
        "difference": ["lookup", "difference"],
        "yoy_growth": ["lookup", "growth"],
        "qoq_growth": ["lookup", "growth"],
        "ratio": ["lookup", "ratio"],
        "multi_period_average": ["lookup", "aggregate"],
        "pairwise_entity_comparison": ["lookup", "compare"],
        "cross_metric_comparison": ["lookup", "compare"],
        "temporal_peak_followup": ["temporal_extreme", "lookup"],
        "multi_year_argmax": ["lookup", "temporal_extreme"],
        "multi_year_argmin": ["lookup", "temporal_extreme"],
        "macro_time_series_argmax": ["lookup", "temporal_extreme"],
        "macro_time_series_argmin": ["lookup", "temporal_extreme"],
        "time_series_argmax": ["lookup", "temporal_extreme"],
        "time_series_argmin": ["lookup", "temporal_extreme"],
        "rolling_max": ["lookup", "temporal_extreme"],
        "rolling_min": ["lookup", "temporal_extreme"],
        "filter_then_rank": ["filter", "rank"],
        "rank_then_secondary_lookup": ["rank", "lookup"],
        "multi_factor_screening": ["filter", "multi_factor_screen"],
    }
    return mapping.get(task_subtype, [task_subtype or "lookup"])


def _normalize_operation_families(operators: list[str]) -> list[str]:
    mapping = {
        "argmax": "temporal_extreme",
        "argmin": "temporal_extreme",
        "select_by_period": "lookup",
        "lookup_ranked_entities": "lookup",
        "growth_by_entity": "growth",
        "ratio_by_entity": "ratio",
        "multi_factor_screen": "multi_factor_screen",
        "intersect_on_entity": "intersection",
        "mean": "aggregate",
        "compare": "compare",
    }
    return list(dict.fromkeys(mapping.get(item, item) for item in operators))


def _primary_operation(operations: list[str]) -> str:
    priority = (
        "multi_factor_screen",
        "rank",
        "temporal_extreme",
        "filter",
        "aggregate",
        "growth",
        "ratio",
        "difference",
        "compare",
        "date_distance",
        "multi_source_synthesis",
        "lookup",
    )
    return next((item for item in priority if item in operations), operations[-1] if operations else "lookup")


def _answer_type(prompt: str, reference: str) -> str:
    text = f"{prompt} {reference}".casefold()
    if re.search(r"top\s*\d+|sorted|rank|排名|排序|前\s*\d+", text):
        return "ranked_table"
    if re.search(r"which companies|哪些公司|分别|列出|summarize", text):
        return "table"
    if re.search(r"what date|which month|which year|when|哪一天|哪个月|哪一年|何时", text):
        return "period_and_value" if re.search(r"%|value|price|数值|涨幅", text) else "period"
    if re.search(r"which country|which company|which stock|哪家|哪个国家|哪只", text):
        return "entity_and_value" if re.search(r"%|how much|多少|比例", text) else "entity"
    if re.search(r"yes or no|whether|是否", text):
        return "boolean"
    return "numeric"


def _normalize_answer_type(value: str) -> str:
    text = value.casefold()
    if "rank" in text:
        return "ranked_table"
    if "table" in text or "screen" in text or "list" in text:
        return "table"
    if "comparison" in text:
        return "entity_and_value"
    if "period" in text:
        return "period_and_value"
    if "boolean" in text:
        return "boolean"
    return "numeric"


def _rubric_type(reference: str) -> str:
    text = reference.casefold()
    if re.search(r"\d+(?:\.\d+)?\s*%.*(?:error|误差)|(?:error|误差).*\d+(?:\.\d+)?\s*%", text):
        return "relative_tolerance"
    if re.search(r"±|\+/-|absolute error|边际误差", text):
        return "absolute_tolerance"
    if re.search(r"between|range|区间|范围|落在", text):
        return "range"
    if re.search(r"round|nearest|四舍五入|取整|保留", text):
        return "rounding"
    if re.search(r"table|sorted|评分要点|表格|排序", text):
        return "structured"
    return "exact_or_other"


def _current_rubric_type(rubric: dict[str, Any]) -> str:
    match_type = str(rubric.get("match_type") or rubric.get("rubric_type") or "")
    if "rank" in match_type or "table" in match_type:
        return "structured_with_tolerance"
    if rubric.get("relative_tolerance") is not None:
        return "relative_tolerance"
    if rubric.get("absolute_tolerance") is not None:
        return "absolute_tolerance"
    return match_type or "exact_or_other"


def _annotation_confidence(task: str, topic: str, answer_type: str) -> float:
    score = 0.7
    if task in {"T1", "T2", "T3"}:
        score += 0.1
    if topic != "other_financial":
        score += 0.1
    if answer_type != "numeric":
        score += 0.05
    return min(score, 0.95)


def _legacy_period_count(task_subtype: str, row: dict[str, Any]) -> int:
    if task_subtype in {"difference", "yoy_growth", "qoq_growth", "ratio", "pairwise_entity_comparison", "cross_metric_comparison"}:
        return 2
    if task_subtype in {
        "multi_period_average",
        "temporal_peak_followup",
        "multi_year_argmax",
        "multi_year_argmin",
        "macro_time_series_argmax",
        "macro_time_series_argmin",
        "time_series_argmax",
        "time_series_argmin",
        "rolling_max",
        "rolling_min",
    }:
        return max(len(row.get("source_fact_ids") or []), 3)
    return 1


def _current_span_months(time_scope: dict[str, Any], period_count: int) -> int:
    start = time_scope.get("start_year")
    end = time_scope.get("end_year")
    start_position = _period_month_position(start)
    end_position = _period_month_position(end)
    if start_position is not None and end_position is not None:
        return max(end_position - start_position, 0)
    frequency = str(time_scope.get("frequency") or "").casefold()
    if period_count > 1:
        return (period_count - 1) * (3 if frequency == "quarterly" else 1 if frequency == "monthly" else 12)
    return 0


def _period_month_position(value: Any) -> int | None:
    text = str(value or "").strip()
    if not text:
        return None
    match = re.search(r"(?P<year>\d{4})(?:[- /]?Q(?P<quarter>[1-4])|-(?P<month>\d{2}))?", text, re.I)
    if not match:
        return None
    year = int(match.group("year"))
    if match.group("quarter"):
        month_offset = (int(match.group("quarter")) - 1) * 3
    elif match.group("month"):
        month_offset = int(match.group("month")) - 1
    else:
        month_offset = 0
    return year * 12 + month_offset


def _current_frequency(time_scope: dict[str, Any]) -> str:
    if time_scope.get("fiscal_quarter"):
        return "quarterly"
    if time_scope.get("fiscal_year") or time_scope.get("calendar_year") or time_scope.get("year"):
        return "annual"
    return "point_in_time"


def _current_market(source_ids: list[str], entity_ids: list[str]) -> str:
    greater_china_source_prefixes = (
        "cninfo",
        "bse_",
        "hkex_",
        "nbs_",
        "pboc_",
        "safe_",
        "sse_",
        "szse_",
    )
    if source_ids and all(
        source.casefold().startswith(greater_china_source_prefixes)
        for source in source_ids
    ):
        return "greater_china"
    greater_china_entities = {"CHN_COUNTRY", "HKG_COUNTRY", "MAC_COUNTRY"}
    if entity_ids and all(
        item in greater_china_entities
        or item.endswith(("_CN", "_HK", "_MO", "_SSE", "_SZSE", "_BSE", "_HKEX"))
        for item in entity_ids
    ):
        return "greater_china"
    return "global"


def _generation_pipeline(row: dict[str, Any]) -> str:
    pattern = str(row.get("pattern_id") or "")
    task_subtype = str(row.get("task_subtype") or "")
    if pattern.startswith("walk_") or task_subtype.startswith("walk_"):
        return "typed_edge_walk"
    if row.get("pattern_proposal_id"):
        return "automatic_pattern_mining"
    if pattern:
        return "static_graph_pattern"
    if row.get("source_derived_ids"):
        return "derived_fact_qa"
    return "fact_qa"


def _question_completeness(
    question: str,
    *,
    unit: str,
    currency: str,
    time_scope: dict[str, Any],
    benchmark_task: str,
    precision_required: bool = True,
) -> dict[str, bool]:
    normalized = question.casefold()
    time_explicit = bool(
        re.search(r"\b(?:19|20)\d{2}\b|q[1-4]|fy\s*(?:19|20)\d{2}", normalized)
        or any(str(value) in question for value in time_scope.values() if isinstance(value, int))
    )
    return {
        "entity_explicit": True,
        "metric_explicit": True,
        "time_explicit": time_explicit,
        "unit_explicit": not unit or _alignment_unit_present(question, unit),
        "currency_explicit": not currency or _alignment_currency_present(question, currency),
        "output_format_explicit": bool(
            re.search(
                r"table|list|rank|report|列出|排序|报告|完整表格|为单位|位小数",
                normalized,
            )
        )
        or benchmark_task == "T2",
        "precision_explicit": (
            not precision_required
            or bool(
                re.search(
                    r"round|decimal|nearest|保留|取整|四舍五入|tolerance|误差",
                    normalized,
                )
            )
        ),
    }


def _alignment_unit_present(question: str, requested_unit: str) -> bool:
    aliases = {
        "million USD": ("million USD", "USD millions", "百万美元"),
        "million CNY": ("million CNY", "CNY millions", "百万元人民币"),
        "million RMB": ("million RMB", "RMB millions", "百万元人民币"),
        "million HKD": ("million HKD", "HKD millions", "百万港元"),
        "billion USD": ("billion USD", "USD billions", "十亿美元"),
        "billion CNY": ("billion CNY", "CNY billions", "十亿元人民币"),
        "billion HKD": ("billion HKD", "HKD billions", "十亿港元"),
        "USD_per_share": ("USD per share", "美元/股"),
        "CNY_per_share": ("CNY per share", "人民币元/股"),
        "HKD_per_share": ("HKD per share", "港元/股"),
        "percent": ("percent", "%", "百分比"),
        "%": ("percent", "%", "百分比"),
    }.get(requested_unit, (requested_unit,))
    compact = re.sub(r"\s+", "", question.casefold())
    if any(re.sub(r"\s+", "", alias.casefold()) in compact for alias in aliases):
        return True
    tokens = [token.casefold() for token in re.findall(r"[A-Za-z%]+", requested_unit)]
    return bool(tokens) and all(token in question.casefold() for token in tokens)


def _alignment_currency_present(question: str, requested_currency: str) -> bool:
    aliases = {
        "USD": ("USD", "US dollars", "美元"),
        "CNY": ("CNY", "RMB", "人民币"),
        "RMB": ("RMB", "CNY", "人民币"),
        "HKD": ("HKD", "Hong Kong dollars", "港元"),
    }.get(requested_currency.upper(), (requested_currency,))
    normalized = question.casefold()
    return any(alias.casefold() in normalized for alias in aliases)


def _tools_for_sources(source_ids: list[str]) -> list[str]:
    tools = {"calculator"}
    for source in source_ids:
        name = source.casefold()
        if name.startswith("sec_"):
            tools.add("sec_edgar")
        elif name.startswith("fred_"):
            tools.add("fred_api")
        elif name.startswith("worldbank_"):
            tools.add("world_bank_api")
        elif name.startswith("imf_"):
            tools.add("imf_sdmx_api")
        elif name.startswith("cninfo"):
            tools.add("cninfo_search")
    return sorted(tools | {"web_search"})


def _coverage_summary(matrix: pd.DataFrame) -> dict[str, Any]:
    official_rows = matrix[matrix["official_count"] > 0]
    return {
        "row_count": int(len(matrix)),
        "official_category_count": int(len(official_rows)),
        "covered_official_category_count": int(official_rows["covered"].sum()),
        "official_category_coverage_rate": (
            float(official_rows["covered"].mean()) if len(official_rows) else 1.0
        ),
    }


def _completeness_summary(rows: list[dict[str, Any]]) -> dict[str, float]:
    keys = sorted(
        {key for row in rows for key in row.get("completeness_checks", {})}
    )
    return {
        key: (
            sum(bool(row.get("completeness_checks", {}).get(key)) for row in rows)
            / len(rows)
            if rows
            else 0.0
        )
        for key in keys
    }


def _jensen_shannon(p: list[float], q: list[float]) -> float:
    midpoint = [(left + right) / 2 for left, right in zip(p, q)]

    def divergence(values: list[float], middle: list[float]) -> float:
        return sum(
            value * math.log2(value / center)
            for value, center in zip(values, middle)
            if value > 0 and center > 0
        )

    return 0.5 * divergence(p, midpoint) + 0.5 * divergence(q, midpoint)


def _joint_counts(rows: list[dict[str, Any]], left: str, right: str) -> dict[str, int]:
    return dict(
        sorted(
            Counter(f"{row[left]}|{row[right]}" for row in rows).items()
        )
    )


def _numeric_summary(values: list[int]) -> dict[str, float]:
    series = pd.Series(values, dtype="float64")
    return {
        "mean": float(series.mean()),
        "median": float(series.median()),
        "p90": float(series.quantile(0.9)),
        "p95": float(series.quantile(0.95)),
        "max": float(series.max()),
    }


def _normalize_question(value: str) -> str:
    return re.sub(r"[^\w\u4e00-\u9fff]+", " ", value.casefold()).strip()


def _text_hash(value: Any) -> str:
    return hashlib.sha256(str(value or "").encode("utf-8")).hexdigest()


def _stable_hash(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()
