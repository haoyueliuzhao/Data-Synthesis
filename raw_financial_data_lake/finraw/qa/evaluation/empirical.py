from __future__ import annotations

import hashlib
import json
import re
import uuid
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Callable

from finraw.db.client import DBProtocol
from finraw.llm_client import OpenAICompatibleJsonClient
from finraw.qa.evaluation.input_views import load_evaluation_bundles
from finraw.qa.evaluation.schema import ensure_evaluation_schema
from finraw.qa.store import insert_rows, json_value


EMPIRICAL_SYSTEM_VERSION = "financial_qa_empirical.v1.0"

RUN_COLUMNS = [
    "empirical_run_id",
    "qa_build_ids",
    "evaluation_mode",
    "model_manifest",
    "sample_manifest",
    "config_hash",
    "status",
    "started_at",
    "completed_at",
    "notes",
]

TRIAL_COLUMNS = [
    "trial_id",
    "empirical_run_id",
    "qa_build_id",
    "qa_id",
    "model_role",
    "provider",
    "requested_model",
    "response_model",
    "answer_text",
    "answer_payload",
    "match_status",
    "match_details",
    "prompt_hash",
    "response_hash",
    "telemetry",
    "status",
    "error_message",
    "created_at",
]


ClientFactory = Callable[[dict[str, Any]], OpenAICompatibleJsonClient]


def run_empirical_model_evaluation(
    db: DBProtocol,
    config: dict[str, Any],
    qa_build_ids: list[str],
    *,
    limit: int = 12,
    output_dir: str | None = None,
    client_factory: ClientFactory | None = None,
) -> dict[str, Any]:
    """Run L3 model trials without letting one model judge another."""
    ensure_evaluation_schema(db)
    quality = dict((config.get("qa") or {}).get("quality_evaluation") or {})
    empirical = dict(quality.get("empirical_evaluation") or {})
    if not empirical.get("enabled", False):
        raise RuntimeError("qa.quality_evaluation.empirical_evaluation.enabled is false")
    mode = str(empirical.get("mode") or "evidence_given")
    if mode != "evidence_given":
        raise ValueError(f"Unsupported empirical evaluation mode: {mode}")
    model_specs = [dict(item) for item in empirical.get("models") or []]
    if len(model_specs) < 2:
        raise RuntimeError("L3 empirical evaluation requires at least two models")

    bundles: list[dict[str, Any]] = []
    for build_id in qa_build_ids:
        bundles.extend(load_evaluation_bundles(db, build_id))
    supported = set(empirical.get("supported_answer_types") or ["numeric"])
    eligible = [
        bundle
        for bundle in bundles
        if bundle.get("deterministic_gate_status") == "passed"
        and (
            "*" in supported
            or str(bundle["sample"].get("answer_type")) in supported
        )
        and _answer_contract_supported(bundle["sample"])
    ]
    selected = _stratified_sample(
        eligible,
        max(int(limit), 1),
        str(empirical.get("sample_seed") or "qa-l3-v1"),
    )
    if not selected:
        raise RuntimeError("No supported deterministic QA samples are available for L3")

    run_id = _new_run_id()
    model_manifest = {
        "models": [_redact_model_spec(item) for item in model_specs],
        "minimum_model_count": int(empirical.get("minimum_model_count") or 2),
    }
    sample_manifest = {
        "sample_count": len(selected),
        "qa_ids": [str(bundle["qa_id"]) for bundle in selected],
        "strata": dict(sorted(Counter(_stratum(bundle) for bundle in selected).items())),
    }
    insert_rows(
        db,
        "qa_empirical_runs",
        [
            {
                "empirical_run_id": run_id,
                "qa_build_ids": qa_build_ids,
                "evaluation_mode": mode,
                "model_manifest": model_manifest,
                "sample_manifest": sample_manifest,
                "config_hash": _hash(_redact_model_spec(empirical)),
                "status": "running",
                "started_at": _now(),
                "completed_at": None,
                "notes": {
                    "empirical_system_version": EMPIRICAL_SYSTEM_VERSION,
                    "scoring_owner": "deterministic_gold_rubric",
                    "model_as_judge": False,
                },
            }
        ],
        RUN_COLUMNS,
        {"qa_build_ids", "model_manifest", "sample_manifest", "notes"},
    )

    evidence_by_qa = {
        str(bundle["qa_id"]): _load_evidence_facts(
            db, bundle["candidate"].get("source_fact_ids") or []
        )
        for bundle in selected
    }
    tasks = [(bundle, spec) for bundle in selected for spec in model_specs]
    max_workers = max(int(empirical.get("maximum_concurrency") or 2), 1)
    factory = client_factory or OpenAICompatibleJsonClient

    def invoke(bundle: dict[str, Any], spec: dict[str, Any]) -> dict[str, Any]:
        role = str(spec.get("model_role") or spec.get("model") or "model")
        model_config = {**dict(quality.get("llm") or {}), **spec}
        model_config["auto_select_model"] = False
        model_config["fallback_models"] = []
        model_config["maximum_model_attempts"] = 1
        prompt = _build_empirical_prompt(
            bundle, evidence_by_qa[str(bundle["qa_id"])]
        )
        trial_id = "qaempiricaltrial_" + _hash(
            (run_id, bundle["qa_id"], role)
        )[:24]
        try:
            maximum_attempts = max(
                int(empirical.get("max_contract_attempts") or 2), 1
            )
            client = factory(model_config)
            failures = []
            for attempt in range(1, maximum_attempts + 1):
                try:
                    attempt_prompt = _contract_repair_prompt(prompt, failures)
                    completion = client.complete_json(attempt_prompt, temperature=0.0)
                    answer_type = str(bundle["sample"].get("answer_type") or "")
                    answer_text, answer_payload = _normalize_model_answer(
                        completion.payload, answer_type
                    )
                    telemetry = {
                        **dict(completion.telemetry),
                        "contract_attempt": attempt,
                        "contract_failure_count": len(failures),
                    }
                    break
                except Exception as exc:
                    failures.append(
                        {
                            "attempt": attempt,
                            "error_type": type(exc).__name__,
                            "message": str(exc)[:300],
                        }
                    )
                    if attempt >= maximum_attempts:
                        raise
            matched, details = match_empirical_answer(
                answer_type,
                bundle["sample"].get("answer_value") or {},
                answer_payload,
                bundle["sample"].get("rubric") or {},
            )
            return {
                "trial_id": trial_id,
                "empirical_run_id": run_id,
                "qa_build_id": bundle["qa_build_id"],
                "qa_id": bundle["qa_id"],
                "model_role": role,
                "provider": telemetry.get("provider") or model_config.get("provider"),
                "requested_model": model_config.get("model"),
                "response_model": telemetry.get("response_model")
                or telemetry.get("model_selected"),
                "answer_text": answer_text,
                "answer_payload": answer_payload,
                "match_status": "passed" if matched else "failed",
                "match_details": details,
                "prompt_hash": _hash(prompt),
                "response_hash": telemetry.get("response_hash"),
                "telemetry": telemetry,
                "status": "succeeded",
                "error_message": None,
                "created_at": _now(),
            }
        except Exception as exc:
            telemetry = dict(getattr(exc, "telemetry", {}) or {})
            return {
                "trial_id": trial_id,
                "empirical_run_id": run_id,
                "qa_build_id": bundle["qa_build_id"],
                "qa_id": bundle["qa_id"],
                "model_role": role,
                "provider": telemetry.get("provider") or model_config.get("provider"),
                "requested_model": model_config.get("model"),
                "response_model": telemetry.get("response_model"),
                "answer_text": "",
                "answer_payload": {},
                "match_status": "not_scored",
                "match_details": {},
                "prompt_hash": _hash(prompt),
                "response_hash": telemetry.get("response_hash"),
                "telemetry": telemetry,
                "status": "failed",
                "error_message": str(exc)[:1000],
                "created_at": _now(),
            }

    trials: list[dict[str, Any]] = []
    if max_workers == 1:
        trials = [invoke(bundle, spec) for bundle, spec in tasks]
    else:
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(invoke, bundle, spec) for bundle, spec in tasks]
            for future in as_completed(futures):
                trials.append(future.result())
    insert_rows(
        db,
        "qa_empirical_model_trials",
        trials,
        TRIAL_COLUMNS,
        {"answer_payload", "match_details", "telemetry"},
    )
    failed_calls = sum(row["status"] != "succeeded" for row in trials)
    db.execute(
        "UPDATE qa_empirical_runs SET status = ?, completed_at = ? "
        "WHERE empirical_run_id = ?",
        ("completed" if failed_calls == 0 else "partial", _now(), run_id),
    )
    return build_empirical_report(db, run_id, output_dir=output_dir)


def build_empirical_report(
    db: DBProtocol, empirical_run_id: str, *, output_dir: str | None = None
) -> dict[str, Any]:
    ensure_evaluation_schema(db)
    run_raw = db.fetchone(
        "SELECT * FROM qa_empirical_runs WHERE empirical_run_id = ?",
        (empirical_run_id,),
    )
    if not run_raw:
        raise RuntimeError(f"Unknown empirical run: {empirical_run_id}")
    run = dict(run_raw)
    for key, default in {
        "qa_build_ids": [],
        "model_manifest": {},
        "sample_manifest": {},
        "notes": {},
    }.items():
        run[key] = json_value(run.get(key), default)
    trials = []
    for raw in db.fetchall(
        "SELECT * FROM qa_empirical_model_trials WHERE empirical_run_id = ? "
        "ORDER BY model_role, qa_id",
        (empirical_run_id,),
    ):
        row = dict(raw)
        for key, default in {
            "answer_payload": {},
            "match_details": {},
            "telemetry": {},
        }.items():
            row[key] = json_value(row.get(key), default)
        trials.append(row)
    dimensions = _trial_dimensions(db, trials)
    per_model: dict[str, dict[str, Any]] = {}
    for role in sorted({str(row["model_role"]) for row in trials}):
        rows = [row for row in trials if str(row["model_role"]) == role]
        succeeded = [row for row in rows if row["status"] == "succeeded"]
        per_model[role] = {
            "requested_model": rows[0].get("requested_model") if rows else None,
            "trial_count": len(rows),
            "call_success_count": len(succeeded),
            "call_success_rate": _rate(len(succeeded), len(rows)),
            "answer_pass_count": sum(row["match_status"] == "passed" for row in rows),
            "answer_pass_rate": _rate(
                sum(row["match_status"] == "passed" for row in rows), len(succeeded)
            ),
            "total_tokens": _sum_telemetry(rows, "total_tokens"),
            "estimated_cost": _sum_telemetry(rows, "estimated_cost"),
            "fallback_count": sum(
                bool((row.get("telemetry") or {}).get("model_fallback_used"))
                for row in rows
            ),
            "accuracy_slices": _accuracy_slices(rows, dimensions),
        }
    by_qa: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in trials:
        by_qa[str(row["qa_id"])].append(row)
    disagreement_count = sum(
        len({row["match_status"] for row in rows if row["status"] == "succeeded"}) > 1
        for rows in by_qa.values()
    )
    report = {
        "empirical_run_id": empirical_run_id,
        "qa_build_ids": run["qa_build_ids"],
        "evaluation_mode": run["evaluation_mode"],
        "status": run["status"],
        "sample_count": int(run["sample_manifest"].get("sample_count") or 0),
        "trial_count": len(trials),
        "model_results": per_model,
        "model_disagreement_count": disagreement_count,
        "model_disagreement_rate": _rate(
            disagreement_count, int(run["sample_manifest"].get("sample_count") or 0)
        ),
        "scoring_policy": {
            "owner": "deterministic_gold_rubric",
            "model_as_judge": False,
            "evidence_given": True,
            "human_calibration_replacement": False,
        },
    }
    if output_dir:
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        json_path = out / "qa_empirical_report.json"
        trials_path = out / "qa_empirical_trials.jsonl"
        md_path = out / "qa_empirical_report.md"
        json_path.write_text(_pretty(report) + "\n", encoding="utf-8")
        trials_path.write_text(
            "".join(_compact(row) + "\n" for row in trials), encoding="utf-8"
        )
        lines = [
            "# Financial QA L3 Empirical Evaluation",
            "",
            f"- Run: `{empirical_run_id}`",
            f"- Mode: `{run['evaluation_mode']}`",
            f"- Samples: `{report['sample_count']}`",
            f"- Trials: `{report['trial_count']}`",
            f"- Model disagreements: `{disagreement_count}`",
            "",
            "## Models",
            "",
        ]
        for role, values in per_model.items():
            lines.append(
                f"- `{role}`: answers `{values['answer_pass_count']} / "
                f"{values['call_success_count']}`, tokens `{values['total_tokens']}`"
            )
        md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        report["written_files"] = [str(json_path), str(md_path), str(trials_path)]
    return report


def match_numeric_answer(
    expected: dict[str, Any], observed: dict[str, Any], rubric: dict[str, Any]
) -> tuple[bool, dict[str, Any]]:
    target = _decimal(rubric.get("target_value")) or _decimal(expected.get("value"))
    value = _decimal(observed.get("value"))
    if target is None or value is None:
        return False, {"reason": "missing_numeric_value"}
    absolute = max(
        (_decimal(rubric.get(key)) or Decimal("0"))
        for key in ("absolute_tolerance", "value_tolerance", "display_absolute_tolerance")
    )
    if rubric.get("precision_must_match") and rubric.get(
        "requested_decimal_places"
    ) is not None:
        display_tolerance = Decimal("0.5") * Decimal("1").scaleb(
            -int(rubric["requested_decimal_places"])
        )
        absolute = max(absolute, display_tolerance)
    relative = _decimal(rubric.get("relative_tolerance")) or Decimal("0")
    tolerance = max(absolute, abs(target) * relative, Decimal("0.000001"))
    candidates = [value]
    if rubric.get("accept_percent_decimal_equivalence"):
        candidates.extend([value * Decimal("100"), value / Decimal("100")])
    error = min(abs(target - candidate) for candidate in candidates)
    unit_expected = str(
        rubric.get("requested_unit") or expected.get("unit") or ""
    ).strip()
    unit_observed = str(observed.get("unit") or "").strip()
    currency_expected = str(
        rubric.get("requested_currency") or expected.get("currency") or ""
    ).strip()
    currency_observed = str(observed.get("currency") or "").strip()
    unit_ok = not rubric.get("unit_must_match") or _same_token(
        unit_expected, unit_observed
    )
    currency_ok = not currency_expected or _same_token(
        currency_expected, currency_observed
    )
    matched = error <= tolerance and unit_ok and currency_ok
    return matched, {
        "numeric_error": str(error),
        "tolerance": str(tolerance),
        "unit_match": unit_ok,
        "currency_match": currency_ok,
    }


def _build_empirical_prompt(
    bundle: dict[str, Any], evidence_facts: list[dict[str, Any]]
) -> str:
    sample = bundle["sample"]
    candidate = bundle["candidate"]
    plan = bundle["operation_plan"]
    rubric = sample.get("rubric") or {}
    answer_type = str(sample.get("answer_type") or "")
    request = {
        "task": "Answer the financial question using only the supplied evidence.",
        "question": sample.get("question"),
        "answer_type": answer_type,
        "evidence_facts": evidence_facts,
        "provenance_context": {
            "raw_object_ids": candidate.get("raw_object_ids") or [],
            "source_document_ids": candidate.get("source_document_ids") or [],
        },
        "operation_plan": [
            {
                "operator": step.get("operator"),
                "params": step.get("params") or {},
            }
            for step in (plan.get("operator_dag") or {}).get("operators", [])
        ],
        "output_contract": {
            "answer_text": "brief final answer in the question language",
            "answer_payload": _answer_payload_contract(answer_type, rubric),
        },
        "rules": [
            "Return one JSON object only.",
            "Do not introduce facts not present in evidence_facts or provenance_context.",
            "Follow the requested precision in answer_text and answer_payload.",
            "Keep numeric values as strings without thousands separators.",
            "Use exact entity_id and raw_object_id identifiers from the evidence.",
            "Do not return internal lineage, input fact IDs, or reasoning text.",
        ],
    }
    return "Solve this evidence-given financial QA item.\n" + json.dumps(
        request, ensure_ascii=False, sort_keys=True, default=str
    )


def _answer_payload_contract(
    answer_type: str, rubric: dict[str, Any]
) -> dict[str, Any]:
    unit = rubric.get("requested_unit") or "unit stated in question"
    currency = rubric.get("requested_currency") or None
    if answer_type == "numeric":
        return {"value": "numeric string", "unit": unit, "currency": currency}
    if answer_type == "comparison":
        return {
            "winner_id": "exact evidence entity_id or metric_id",
            "relation": "greater, less, or equal",
            "difference": "non-negative numeric string",
            "rows": [{"id": "entity_id or metric_id", "value": "numeric string"}],
            "unit": unit,
            "currency": currency,
        }
    if answer_type == "period_and_value":
        return {
            "result_period": "year, quarter, month, or date",
            "value": "numeric string",
            "unit": unit,
            "currency": currency,
        }
    if answer_type in {"period_metric_lookup", "period_metric_provenance"}:
        contract = {
            "result_period": "selected period",
            "primary_value": "numeric string",
            "secondary_value": "numeric string",
            "primary_unit": unit,
            "secondary_unit": unit,
            "currency": currency,
        }
        if answer_type == "period_metric_provenance":
            contract["raw_object_ids"] = ["exact raw_object_id"]
        return contract
    if answer_type == "ranked_table":
        row = {"rank": "integer", "entity_id": "exact entity_id", "value": "numeric string"}
    elif answer_type in {"multi_metric_ranked_table", "filtered_rank_followup"}:
        row = {
            "rank": "integer",
            "entity_id": "exact entity_id",
            "primary_value": "numeric string",
            "secondary_value": "numeric string",
        }
    elif answer_type == "screening_table":
        row = {
            "entity_id": "exact entity_id",
            "revenue_growth_pct": "numeric string",
            "net_margin_pct": "numeric string",
            "debt_ratio_pct": "numeric string",
        }
    else:
        return {"value": "answer value", "unit": unit, "currency": currency}
    return {"table": [row], "unit": unit, "currency": currency}


def _contract_repair_prompt(
    prompt: str, failures: list[dict[str, Any]]
) -> str:
    if not failures:
        return prompt
    failure = failures[-1]
    return (
        prompt
        + "\n\nCONTRACT REPAIR REQUIRED. The previous response was rejected: "
        + str(failure.get("message") or failure.get("error_type") or "invalid JSON contract")
        + ". Return exactly one JSON object with both non-empty answer_text and "
        + "answer_payload fields. Do not use a flat answer object, markdown, or commentary."
    )


def _normalize_model_answer(
    payload: dict[str, Any], answer_type: str
) -> tuple[str, dict[str, Any]]:
    if not isinstance(payload, dict):
        raise ValueError("Model answer must be a JSON object")
    answer_text = str(payload.get("answer_text") or "").strip()
    answer_payload = payload.get("answer_payload")
    if not answer_text or not isinstance(answer_payload, dict):
        raise ValueError("Model answer requires answer_text and answer_payload")
    if answer_type == "numeric" and _decimal(answer_payload.get("value")) is None:
        raise ValueError("numeric answer_payload.value must be numeric")
    if answer_type in {
        "ranked_table",
        "multi_metric_ranked_table",
        "screening_table",
        "filtered_rank_followup",
    } and not isinstance(answer_payload.get("table"), list):
        raise ValueError("table answer requires answer_payload.table")
    return answer_text, answer_payload


def match_empirical_answer(
    answer_type: str,
    expected: dict[str, Any],
    observed: dict[str, Any],
    rubric: dict[str, Any],
) -> tuple[bool, dict[str, Any]]:
    if answer_type == "numeric":
        return match_numeric_answer(expected, observed, rubric)
    checks: dict[str, bool] = {}
    if answer_type == "comparison":
        checks["winner"] = str(observed.get("winner_id")) == str(
            rubric.get("winner_id") or expected.get("winner_id")
        )
        checks["relation"] = str(observed.get("relation")) == str(
            rubric.get("relation") or expected.get("relation")
        )
        checks["difference"] = _numeric_field_match(
            rubric.get("difference") or expected.get("difference"),
            observed.get("difference"),
            rubric,
        )
        checks["rows"] = _table_match(
            rubric.get("target_rows") or expected.get("rows") or [],
            observed.get("rows") or [],
            rubric,
        )
    elif answer_type == "period_and_value":
        checks["period"] = _period_match(
            rubric.get("target_period") or expected.get("result_period"), observed
        )
        checks["value"] = _numeric_field_match(
            rubric.get("target_value") or expected.get("value"),
            observed.get("value"),
            rubric,
        )
    elif answer_type in {"period_metric_lookup", "period_metric_provenance"}:
        checks["period"] = _period_match(
            rubric.get("target_period")
            or expected.get("result_period")
            or expected.get("period"),
            observed,
        )
        checks["primary_value"] = _numeric_field_match(
            rubric.get("primary_value") or expected.get("primary_value"),
            observed.get("primary_value"),
            rubric,
        )
        checks["secondary_value"] = _numeric_field_match(
            rubric.get("secondary_value")
            or expected.get("secondary_value")
            or expected.get("value"),
            observed.get("secondary_value")
            if observed.get("secondary_value") is not None
            else observed.get("value"),
            rubric,
        )
        if answer_type == "period_metric_provenance":
            checks["raw_object_ids"] = set(
                str(item) for item in expected.get("raw_object_ids") or []
            ) == set(str(item) for item in observed.get("raw_object_ids") or [])
    elif answer_type in {
        "ranked_table",
        "multi_metric_ranked_table",
        "screening_table",
        "filtered_rank_followup",
    }:
        target = rubric.get("target_rows")
        if target is None:
            target = (rubric.get("target_answer") or {}).get("table")
        if target is None:
            target = expected.get("table") or []
        checks["table"] = _table_match(
            target, observed.get("table") or [], rubric
        )
    else:
        return False, {"reason": f"unsupported_answer_type:{answer_type}"}
    checks["unit"] = _unit_contract_match(expected, observed, rubric)
    passed = all(checks.values())
    return passed, {"checks": checks}


def _answer_contract_supported(sample: dict[str, Any]) -> bool:
    answer_type = str(sample.get("answer_type") or "")
    return answer_type in {
        "numeric",
        "comparison",
        "period_and_value",
        "period_metric_lookup",
        "period_metric_provenance",
        "ranked_table",
        "multi_metric_ranked_table",
        "screening_table",
        "filtered_rank_followup",
    }


def _numeric_tolerance(target: Decimal, rubric: dict[str, Any]) -> Decimal:
    absolute = max(
        (_decimal(rubric.get(key)) or Decimal("0"))
        for key in (
            "absolute_tolerance",
            "value_tolerance",
            "display_absolute_tolerance",
        )
    )
    places = rubric.get("requested_decimal_places")
    if places is not None:
        absolute = max(
            absolute, Decimal("0.5") * Decimal("1").scaleb(-int(places))
        )
    relative = _decimal(rubric.get("relative_tolerance")) or Decimal("0")
    return max(absolute, abs(target) * relative, Decimal("0.000001"))


def _numeric_field_match(
    expected: Any, observed: Any, rubric: dict[str, Any]
) -> bool:
    target = _decimal(expected)
    value = _decimal(observed)
    if target is None or value is None:
        return False
    candidates = [value]
    if rubric.get("accept_percent_decimal_equivalence"):
        candidates.extend([value * Decimal("100"), value / Decimal("100")])
    return min(abs(target - item) for item in candidates) <= _numeric_tolerance(
        target, rubric
    )


def _table_match(
    expected_rows: list[dict[str, Any]],
    observed_rows: list[dict[str, Any]],
    rubric: dict[str, Any],
) -> bool:
    if len(expected_rows) != len(observed_rows):
        return False

    def row_matches(
        expected_row: dict[str, Any], observed_row: dict[str, Any]
    ) -> bool:
        if not isinstance(observed_row, dict):
            return False
        for key, expected_value in expected_row.items():
            observed_value = observed_row.get(key)
            if _decimal(expected_value) is not None:
                if not _numeric_field_match(expected_value, observed_value, rubric):
                    return False
            elif str(expected_value) != str(observed_value):
                return False
        return True

    if rubric.get("order_required"):
        return all(
            row_matches(expected_row, observed_row)
            for expected_row, observed_row in zip(expected_rows, observed_rows)
        )

    unmatched = list(observed_rows)
    for expected_row in expected_rows:
        match_index = next(
            (
                index
                for index, observed_row in enumerate(unmatched)
                if row_matches(expected_row, observed_row)
            ),
            None,
        )
        if match_index is None:
            return False
        unmatched.pop(match_index)
    return not unmatched


def _period_match(expected: Any, observed: dict[str, Any]) -> bool:
    actual = observed.get("result_period")
    if actual is None:
        actual = observed.get("period")
    expected_text = str(expected).strip()
    actual_text = str(actual).strip()
    if expected_text == actual_text:
        return True
    if re.fullmatch(r"(?:19|20)\d{2}", expected_text):
        years = re.findall(r"(?<!\d)(?:19|20)\d{2}(?!\d)", actual_text)
        return years == [expected_text]
    return False


def _unit_contract_match(
    expected: dict[str, Any], observed: dict[str, Any], rubric: dict[str, Any]
) -> bool:
    if not rubric.get("unit_must_match"):
        return True
    requested = str(rubric.get("requested_unit") or expected.get("unit") or "")
    candidates = [
        observed.get("unit"),
        observed.get("primary_unit"),
        observed.get("secondary_unit"),
    ]
    return any(_same_token(requested, str(item or "")) for item in candidates)


def _load_evidence_facts(db: DBProtocol, fact_ids: list[str]) -> list[dict[str, Any]]:
    if not fact_ids:
        return []
    placeholders = ",".join("?" for _ in fact_ids)
    rows = db.fetchall(
        "SELECT facts.fact_id, facts.entity_id, entities.canonical_name AS entity_name, "
        "facts.metric_id, metrics.canonical_name AS metric_name, facts.normalized_value, "
        "facts.normalized_unit, facts.normalized_currency, facts.period_start, "
        "facts.period_end, facts.fiscal_year, facts.fiscal_quarter, facts.as_of_date, "
        "facts.source_id, facts.source_definition_id, facts.raw_object_id FROM standardized_facts facts "
        "LEFT JOIN canonical_entities entities ON entities.entity_id = facts.entity_id "
        "LEFT JOIN metrics ON metrics.metric_id = facts.metric_id "
        f"WHERE facts.fact_id IN ({placeholders}) "
        "ORDER BY facts.entity_id, facts.metric_id, facts.period_end, facts.fact_id",
        tuple(fact_ids),
    )
    return [dict(row) for row in rows]



def _trial_dimensions(
    db: DBProtocol, trials: list[dict[str, Any]]
) -> dict[str, dict[str, str]]:
    qa_ids = sorted({str(row["qa_id"]) for row in trials})
    dimensions: dict[str, dict[str, str]] = {}
    for offset in range(0, len(qa_ids), 400):
        chunk = qa_ids[offset : offset + 400]
        placeholders = ",".join("?" for _ in chunk)
        for raw in db.fetchall(
            "SELECT qa_id, task_subtype, answer_type, language FROM qa_samples "
            f"WHERE qa_id IN ({placeholders})",
            tuple(chunk),
        ):
            row = dict(raw)
            dimensions[str(row["qa_id"])] = {
                "task_subtype": str(row.get("task_subtype") or "unknown"),
                "answer_type": str(row.get("answer_type") or "unknown"),
                "language": str(row.get("language") or "unknown"),
            }
        for raw in db.fetchall(
            "SELECT qa_id, market_subset, benchmark_task, alignment_id, created_at "
            "FROM qa_distribution_labels "
            f"WHERE qa_id IN ({placeholders}) ORDER BY created_at, alignment_id",
            tuple(chunk),
        ):
            row = dict(raw)
            dimensions.setdefault(str(row["qa_id"]), {}).update(
                {
                    "market_subset": str(row.get("market_subset") or "unknown"),
                    "benchmark_task": str(row.get("benchmark_task") or "unknown"),
                }
            )
    return dimensions


def _accuracy_slices(
    rows: list[dict[str, Any]], dimensions: dict[str, dict[str, str]]
) -> dict[str, dict[str, dict[str, float | int]]]:
    output: dict[str, dict[str, dict[str, float | int]]] = {}
    for field in (
        "market_subset",
        "benchmark_task",
        "language",
        "answer_type",
        "task_subtype",
    ):
        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in rows:
            value = dimensions.get(str(row["qa_id"]), {}).get(field, "unknown")
            grouped[value].append(row)
        output[field] = {}
        for value, grouped_rows in sorted(grouped.items()):
            succeeded = [item for item in grouped_rows if item["status"] == "succeeded"]
            passed = sum(item["match_status"] == "passed" for item in grouped_rows)
            output[field][value] = {
                "sample_count": len(grouped_rows),
                "call_success_count": len(succeeded),
                "answer_pass_count": passed,
                "answer_accuracy": _rate(passed, len(succeeded)),
            }
    return output

def _stratified_sample(
    bundles: list[dict[str, Any]], limit: int, seed: str
) -> list[dict[str, Any]]:
    markets: dict[str, dict[str, dict[str, list[dict[str, Any]]]]] = (
        defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    )
    for bundle in bundles:
        label = bundle.get("distribution_label") or {}
        market = str(label.get("market_subset") or "unknown")
        benchmark_task = str(label.get("benchmark_task") or "unknown")
        markets[market][benchmark_task][_stratum(bundle)].append(bundle)

    task_order: dict[str, list[str]] = {}
    task_cursor: dict[str, int] = {}
    stratum_order: dict[tuple[str, str], list[str]] = {}
    stratum_cursor: dict[tuple[str, str], int] = {}
    for market, task_groups in markets.items():
        task_order[market] = sorted(
            task_groups, key=lambda task: _hash((seed, market, task))
        )
        task_cursor[market] = 0
        for task, groups in task_groups.items():
            for key in groups:
                groups[key].sort(key=lambda row: _hash((seed, row["qa_id"])))
            pair = (market, task)
            stratum_order[pair] = sorted(
                groups, key=lambda key: _hash((seed, market, task, key))
            )
            stratum_cursor[pair] = 0

    selected: list[dict[str, Any]] = []
    market_order = sorted(markets, key=lambda key: _hash((seed, key)))
    target = min(limit, len(bundles))
    while len(selected) < target:
        progressed = False
        for market in market_order:
            tasks = task_order[market]
            chosen_task = None
            for _ in tasks:
                task_index = task_cursor[market] % len(tasks)
                task_cursor[market] += 1
                task = tasks[task_index]
                if any(markets[market][task][key] for key in stratum_order[(market, task)]):
                    chosen_task = task
                    break
            if chosen_task is None:
                continue
            pair = (market, chosen_task)
            keys = stratum_order[pair]
            for _ in keys:
                index = stratum_cursor[pair] % len(keys)
                stratum_cursor[pair] += 1
                key = keys[index]
                if markets[market][chosen_task][key]:
                    selected.append(markets[market][chosen_task][key].pop(0))
                    progressed = True
                    break
            if len(selected) >= target:
                break
        if not progressed:
            break
    return selected


def _stratum(bundle: dict[str, Any]) -> str:
    label = bundle.get("distribution_label") or {}
    sample = bundle.get("sample") or {}
    return "|".join(
        (
            str(label.get("market_subset") or "unknown"),
            str(label.get("benchmark_task") or "unknown"),
            str(sample.get("task_subtype") or "unknown"),
            str(sample.get("language") or "unknown"),
        )
    )


def _redact_model_spec(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            str(key): (
                "<redacted>"
                if str(key).casefold() in {"api_key", "authorization", "token"}
                else _redact_model_spec(item)
            )
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_redact_model_spec(item) for item in value]
    return value


def _same_token(left: str, right: str) -> bool:
    return "".join(left.casefold().split()) == "".join(right.casefold().split())


def _decimal(value: Any) -> Decimal | None:
    try:
        if value is None or isinstance(value, bool):
            return None
        return Decimal(str(value).replace(",", "").strip())
    except (InvalidOperation, ValueError):
        return None


def _sum_telemetry(rows: list[dict[str, Any]], key: str) -> float | int | None:
    values = [
        (row.get("telemetry") or {}).get(key)
        for row in rows
        if (row.get("telemetry") or {}).get(key) is not None
    ]
    if not values:
        return None
    total = sum(float(item) for item in values)
    return round(total, 8) if any(isinstance(item, float) for item in values) else int(total)


def _rate(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 6) if denominator else 0.0


def _new_run_id() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    return f"qaempirical_{stamp}_{uuid.uuid4().hex[:8]}"


def _hash(value: Any) -> str:
    payload = value if isinstance(value, str) else json.dumps(
        value, ensure_ascii=False, sort_keys=True, default=str
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _pretty(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, default=str)


def _compact(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
