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
from threading import Lock
from typing import Any, Callable

from finraw.db.client import DBProtocol
from finraw.llm_client import OpenAICompatibleJsonClient
from finraw.qa.answer_schema_registry import (
    SUPPORTED_ANSWER_TYPES,
    canonical_gold,
    answer_schema_manifest,
    match_answer as registry_match_answer,
    model_contract as registry_model_contract,
    normalize_model_answer as registry_normalize_model_answer,
    resolve_answer_schema,
    rubric_contract as registry_rubric_contract,
)
from finraw.qa.evaluation.input_views import load_evaluation_bundles
from finraw.qa.evaluation.schema import ensure_evaluation_schema
from finraw.qa.store import insert_rows, json_value


EMPIRICAL_SYSTEM_VERSION = "financial_qa_empirical.v3.0"

EMPIRICAL_MODES = frozenset({
    "gold_plan_given",
    "evidence_only",
    "evidence_pool",
    "retrieval_tool",
})
MODE_ALIASES = {"evidence_given": "gold_plan_given"}

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
    "trial_mode",
    "selected_evidence_ids",
    "tool_trace",
    "answer_text",
    "answer_payload",
    "match_status",
    "match_details",
    "api_call_success",
    "json_contract_success",
    "semantic_answer_correct",
    "unit_currency_correct",
    "row_completeness",
    "order_correct",
    "evidence_selection_correct",
    "end_to_end_correct",
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
    mode: str | None = None,
    output_dir: str | None = None,
    client_factory: ClientFactory | None = None,
) -> dict[str, Any]:
    """Run one pinned L3 evaluation mode without model-as-judge scoring."""
    ensure_evaluation_schema(db)
    quality = dict((config.get("qa") or {}).get("quality_evaluation") or {})
    empirical = dict(quality.get("empirical_evaluation") or {})
    if not empirical.get("enabled", False):
        raise RuntimeError(
            "qa.quality_evaluation.empirical_evaluation.enabled is false"
        )
    trial_mode = _normalize_mode(mode or empirical.get("mode"))
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
        raise RuntimeError(
            "No supported deterministic QA samples are available for L3"
        )

    run_id = _new_run_id()
    model_manifest = {
        "models": [_redact_model_spec(item) for item in model_specs],
        "minimum_model_count": int(empirical.get("minimum_model_count") or 2),
    }
    sample_manifest = {
        "sample_count": len(selected),
        "qa_ids": [str(bundle["qa_id"]) for bundle in selected],
        "strata": dict(
            sorted(Counter(_stratum(bundle) for bundle in selected).items())
        ),
    }
    gold_evidence = {
        str(bundle["qa_id"]): _load_evidence_facts(
            db,
            str(bundle["qa_build_id"]),
            bundle["candidate"].get("source_fact_ids") or [],
        )
        for bundle in selected
    }
    prompt_evidence = {}
    for bundle in selected:
        qa_id = str(bundle["qa_id"])
        rows = list(gold_evidence[qa_id])
        if trial_mode == "evidence_pool":
            rows.extend(
                _load_distractor_facts(
                    db,
                    bundle,
                    {str(row["fact_id"]) for row in rows},
                    int(empirical.get("distractor_count") or 8),
                    str(empirical.get("sample_seed") or "qa-l3-v1"),
                )
            )
            rows.sort(
                key=lambda row: _hash(
                    (
                        empirical.get("sample_seed") or "qa-l3-v1",
                        qa_id,
                        row.get("fact_id"),
                    )
                )
            )
        prompt_evidence[qa_id] = rows

    insert_rows(
        db,
        "qa_empirical_runs",
        [
            {
                "empirical_run_id": run_id,
                "qa_build_ids": qa_build_ids,
                "evaluation_mode": trial_mode,
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
                    "answer_schema_manifest": answer_schema_manifest(),
                    "mode_contract": _mode_contract(trial_mode),
                },
            }
        ],
        RUN_COLUMNS,
        {"qa_build_ids", "model_manifest", "sample_manifest", "notes"},
    )

    tasks = [(bundle, spec) for bundle in selected for spec in model_specs]
    max_workers = max(int(empirical.get("maximum_concurrency") or 2), 1)
    factory = client_factory or OpenAICompatibleJsonClient
    retrieval_db_lock = Lock()

    def invoke(
        bundle: dict[str, Any], spec: dict[str, Any]
    ) -> dict[str, Any]:
        qa_id = str(bundle["qa_id"])
        role = str(spec.get("model_role") or spec.get("model") or "model")
        model_config = {**dict(quality.get("llm") or {}), **spec}
        model_config["auto_select_model"] = False
        model_config["fallback_models"] = []
        model_config["maximum_model_attempts"] = 1
        prompt = _build_empirical_prompt(
            bundle,
            prompt_evidence[qa_id],
            trial_mode,
        )
        trial_id = "qaempiricaltrial_" + _hash(
            (run_id, qa_id, role, trial_mode)
        )[:24]
        state: dict[str, Any] = {
            "api_call_success": False,
            "json_contract_success": False,
            "selected_evidence_ids": [],
            "tool_trace": [],
            "telemetry": {},
        }
        try:
            client = factory(model_config)
            answer_schema = _resolved_answer_schema(bundle)
            if trial_mode == "retrieval_tool":
                completion_payload, telemetry = _run_retrieval_tool_loop(
                    db,
                    client,
                    bundle,
                    prompt,
                    empirical,
                    state,
                    tool_db_lock=retrieval_db_lock,
                )
            else:
                completion_payload, telemetry = _complete_answer_contract(
                    client,
                    prompt,
                    max(int(empirical.get("max_contract_attempts") or 2), 1),
                    state,
                    answer_schema,
                    trial_mode == "evidence_pool",
                )
            state["telemetry"] = telemetry
            selected_evidence_ids = _selected_evidence_ids(
                completion_payload,
                required=trial_mode in {"evidence_pool", "retrieval_tool"},
            )
            answer_text, answer_payload = registry_normalize_model_answer(
                completion_payload,
                answer_schema,
            )
            state["json_contract_success"] = True
            state["selected_evidence_ids"] = selected_evidence_ids
            rubric = bundle["sample"].get("rubric") or {}
            expected = bundle["sample"].get("answer_value") or {}
            matched, details = registry_match_answer(
                answer_schema,
                expected,
                answer_payload,
                rubric,
            )
            component_scores = _component_scores(
                answer_schema,
                expected,
                answer_payload,
                rubric,
                details,
                trial_mode,
                set(
                    str(item)
                    for item in bundle["candidate"].get("source_fact_ids") or []
                ),
                set(selected_evidence_ids),
                api_call_success=True,
                json_contract_success=True,
            )
            details = {
                **dict(details),
                "component_scores": component_scores,
            }
            return {
                "trial_id": trial_id,
                "empirical_run_id": run_id,
                "qa_build_id": bundle["qa_build_id"],
                "qa_id": qa_id,
                "model_role": role,
                "provider": telemetry.get("provider")
                or model_config.get("provider"),
                "requested_model": model_config.get("model"),
                "response_model": telemetry.get("response_model")
                or telemetry.get("model_selected"),
                "trial_mode": trial_mode,
                "selected_evidence_ids": selected_evidence_ids,
                "tool_trace": state["tool_trace"],
                "answer_text": answer_text,
                "answer_payload": answer_payload,
                "match_status": "passed" if matched else "failed",
                "match_details": details,
                **component_scores,
                "prompt_hash": _hash(prompt),
                "response_hash": telemetry.get("response_hash"),
                "telemetry": telemetry,
                "status": "succeeded",
                "error_message": None,
                "created_at": _now(),
            }
        except Exception as exc:
            telemetry = {
                **dict(state.get("telemetry") or {}),
                **dict(getattr(exc, "telemetry", {}) or {}),
            }
            state["api_call_success"] = bool(
                state["api_call_success"] or telemetry.get("http_success")
            )
            component_scores = _failed_component_scores(
                trial_mode,
                bool(state["api_call_success"]),
                bool(state["json_contract_success"]),
            )
            return {
                "trial_id": trial_id,
                "empirical_run_id": run_id,
                "qa_build_id": bundle["qa_build_id"],
                "qa_id": qa_id,
                "model_role": role,
                "provider": telemetry.get("provider")
                or model_config.get("provider"),
                "requested_model": model_config.get("model"),
                "response_model": telemetry.get("response_model"),
                "trial_mode": trial_mode,
                "selected_evidence_ids": state["selected_evidence_ids"],
                "tool_trace": state["tool_trace"],
                "answer_text": "",
                "answer_payload": {},
                "match_status": "not_scored",
                "match_details": {
                    "contract_error": str(exc)[:500],
                    "component_scores": component_scores,
                },
                **component_scores,
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
            futures = [
                executor.submit(invoke, bundle, spec)
                for bundle, spec in tasks
            ]
            for future in as_completed(futures):
                trials.append(future.result())
    insert_rows(
        db,
        "qa_empirical_model_trials",
        trials,
        TRIAL_COLUMNS,
        {
            "selected_evidence_ids",
            "tool_trace",
            "answer_payload",
            "match_details",
            "telemetry",
        },
    )
    failed_trials = sum(
        not row["json_contract_success"] for row in trials
    )
    db.execute(
        "UPDATE qa_empirical_runs SET status = ?, completed_at = ? "
        "WHERE empirical_run_id = ?",
        (
            "completed" if failed_trials == 0 else "partial",
            _now(),
            run_id,
        ),
    )
    return build_empirical_report(db, run_id, output_dir=output_dir)


def build_empirical_report(
    db: DBProtocol,
    empirical_run_id: str,
    *,
    output_dir: str | None = None,
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
    run_version = str(
        (run.get("notes") or {}).get("empirical_system_version") or "legacy"
    )
    trials = []
    for raw in db.fetchall(
        "SELECT * FROM qa_empirical_model_trials WHERE empirical_run_id = ? "
        "ORDER BY model_role, qa_id",
        (empirical_run_id,),
    ):
        row = dict(raw)
        for key, default in {
            "selected_evidence_ids": [],
            "tool_trace": [],
            "answer_payload": {},
            "match_details": {},
            "telemetry": {},
        }.items():
            row[key] = json_value(row.get(key), default)
        if run_version != EMPIRICAL_SYSTEM_VERSION:
            row = _infer_legacy_trial_metrics(row, run["evaluation_mode"])
        trials.append(row)

    dimensions = _trial_dimensions(db, trials)
    per_model: dict[str, dict[str, Any]] = {}
    for role in sorted({str(row["model_role"]) for row in trials}):
        rows = [row for row in trials if str(row["model_role"]) == role]
        per_model[role] = {
            "requested_model": rows[0].get("requested_model") if rows else None,
            **_trial_metric_summary(rows),
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
        len(
            {
                bool(row.get("end_to_end_correct"))
                for row in rows
                if row.get("api_call_success")
            }
        )
        > 1
        for rows in by_qa.values()
    )
    mode = _normalize_mode(run["evaluation_mode"])
    report = {
        "empirical_run_id": empirical_run_id,
        "qa_build_ids": run["qa_build_ids"],
        "evaluation_mode": mode,
        "empirical_system_version": run_version,
        "legacy_metric_inference": run_version != EMPIRICAL_SYSTEM_VERSION,
        "mode_contract": _mode_contract(mode),
        "status": run["status"],
        "sample_count": int(run["sample_manifest"].get("sample_count") or 0),
        "trial_count": len(trials),
        "overall": _trial_metric_summary(trials),
        "model_results": per_model,
        "model_disagreement_count": disagreement_count,
        "model_disagreement_rate": _rate(
            disagreement_count,
            int(run["sample_manifest"].get("sample_count") or 0),
        ),
        "scoring_policy": {
            "owner": "deterministic_gold_rubric",
            "model_as_judge": False,
            "gold_plan_given": mode == "gold_plan_given",
            "evidence_given": mode
            in {"gold_plan_given", "evidence_only", "evidence_pool"},
            "distractors_given": mode == "evidence_pool",
            "tools_enabled": mode == "retrieval_tool",
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
            "".join(_compact(row) + "\n" for row in trials),
            encoding="utf-8",
        )
        lines = [
            "# Financial QA L3 Empirical Evaluation",
            "",
            f"- Run: {empirical_run_id}",
            f"- Mode: {mode}",
            f"- Samples: {report['sample_count']}",
            f"- Trials: {report['trial_count']}",
            f"- Contract success: "
            f"{report['overall']['contract_success_rate']}",
            f"- Semantic accuracy given valid contract: "
            f"{report['overall']['semantic_accuracy_given_valid_contract']}",
            f"- End-to-end accuracy: "
            f"{report['overall']['end_to_end_accuracy']}",
            f"- Model disagreements: {disagreement_count}",
            "",
            "## Models",
            "",
        ]
        for role, values in per_model.items():
            lines.append(
                f"- {role}: contract={values['contract_success_rate']}, "
                f"semantic|valid={values['semantic_accuracy_given_valid_contract']}, "
                f"end_to_end={values['end_to_end_accuracy']}, "
                f"tokens={values['total_tokens']}"
            )
        md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        report["written_files"] = [
            str(json_path),
            str(md_path),
            str(trials_path),
        ]
    return report


def match_numeric_answer(
    expected: dict[str, Any], observed: dict[str, Any], rubric: dict[str, Any]
) -> tuple[bool, dict[str, Any]]:
    schema = resolve_answer_schema("numeric", {"type": "numeric"}, rubric)
    return registry_match_answer(schema, expected, observed, rubric)


def _resolved_answer_schema(bundle: dict[str, Any]) -> dict[str, Any]:
    sample = bundle["sample"]
    candidate = bundle["candidate"]
    return resolve_answer_schema(
        str(sample.get("answer_type") or ""),
        candidate.get("answer_schema") or {},
        sample.get("rubric") or {},
        candidate.get("canonical_semantics") or {},
    )


def _build_empirical_prompt(
    bundle: dict[str, Any],
    evidence_facts: list[dict[str, Any]],
    mode: str = "gold_plan_given",
) -> str:
    mode = _normalize_mode(mode)
    sample = bundle["sample"]
    candidate = bundle["candidate"]
    plan = bundle["operation_plan"]
    rubric = sample.get("rubric") or {}
    answer_type = str(sample.get("answer_type") or "")
    answer_schema = _resolved_answer_schema(bundle)
    output_contract = registry_model_contract(answer_schema)
    if mode in {"evidence_pool", "retrieval_tool"}:
        output_contract = {
            **output_contract,
            "selected_evidence_ids": [
                "exact fact_id values actually used in the answer"
            ],
        }
    request: dict[str, Any] = {
        "task": _mode_contract(mode)["task"],
        "evaluation_mode": mode,
        "question": sample.get("question"),
        "answer_type": answer_type,
        "answer_schema": answer_schema,
        "output_contract": output_contract,
        "rubric_contract": registry_rubric_contract(answer_schema, rubric),
        "rules": [
            "Return one JSON object only.",
            "Follow the requested precision in answer_text and answer_payload.",
            "Keep numeric values as strings without thousands separators.",
            "Use exact identifiers returned in evidence or tool results.",
            "Do not return internal reasoning text.",
        ],
    }
    if mode in {"gold_plan_given", "evidence_only", "evidence_pool"}:
        request["evidence_facts"] = evidence_facts
        request["provenance_context"] = {
            "raw_object_ids": candidate.get("raw_object_ids") or [],
            "source_document_ids": candidate.get("source_document_ids") or [],
        }
        request["rules"].append(
            "Do not introduce facts not present in the supplied evidence."
        )
    if mode == "gold_plan_given":
        request["operation_plan"] = [
            {
                "operator": step.get("operator"),
                "params": step.get("params") or {},
            }
            for step in (plan.get("operator_dag") or {}).get("operators", [])
        ]
    elif mode == "evidence_only":
        request["rules"].append(
            "Choose and execute the required calculation method yourself."
        )
    elif mode == "evidence_pool":
        request["rules"].extend(
            [
                "The evidence pool contains distractors.",
                "Select only evidence needed for the answer.",
                "selected_evidence_ids must exactly list the facts used.",
            ]
        )
    elif mode == "retrieval_tool":
        request["available_tools"] = _tool_contracts()
        request["rules"].extend(
            [
                "No evidence is supplied initially.",
                "Use registered tools to retrieve evidence before answering.",
                "Return a tool call as action=tool_call, tool, and arguments.",
                "Return the final answer with action=final and "
                "selected_evidence_ids.",
            ]
        )
    return "Solve this financial QA trial.\n" + json.dumps(
        request,
        ensure_ascii=False,
        sort_keys=True,
        default=str,
    )


def _answer_payload_contract(
    answer_type: str, rubric: dict[str, Any]
) -> dict[str, Any]:
    schema = resolve_answer_schema(
        answer_type, {"type": answer_type}, rubric
    )
    return registry_model_contract(schema)["answer_payload"]


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
    schema = resolve_answer_schema(answer_type, {"type": answer_type}, {})
    return registry_normalize_model_answer(payload, schema)


def match_empirical_answer(
    answer_type: str,
    expected: dict[str, Any],
    observed: dict[str, Any],
    rubric: dict[str, Any],
) -> tuple[bool, dict[str, Any]]:
    schema = resolve_answer_schema(
        answer_type, {"type": answer_type}, rubric
    )
    return registry_match_answer(schema, expected, observed, rubric)


def _answer_contract_supported(sample: dict[str, Any]) -> bool:
    answer_type = str(sample.get("answer_type") or "")
    return answer_type in SUPPORTED_ANSWER_TYPES


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


def _load_evidence_facts(
    db: DBProtocol, qa_build_id: str, fact_ids: list[str]
) -> list[dict[str, Any]]:
    if not fact_ids:
        return []
    build_raw = db.fetchone(
        "SELECT fact_build_id, entity_build_id, metric_build_id, "
        "source_definition_build_id FROM qa_builds WHERE qa_build_id = ?",
        (qa_build_id,),
    )
    if not build_raw:
        raise RuntimeError(f"Unknown QA build for evidence loading: {qa_build_id}")
    build = dict(build_raw)
    required = (
        "fact_build_id",
        "entity_build_id",
        "metric_build_id",
        "source_definition_build_id",
    )
    missing = [key for key in required if not build.get(key)]
    if missing:
        raise RuntimeError(
            f"QA build {qa_build_id} is missing pinned evidence builds: {missing}"
        )
    placeholders = ",".join("?" for _ in fact_ids)
    rows = db.fetchall(
        "SELECT facts.fact_id, facts.entity_id, "
        "entities.canonical_name AS entity_name, facts.metric_id, "
        "metrics.canonical_name AS metric_name, facts.normalized_value, "
        "facts.normalized_unit, facts.normalized_currency, facts.period_start, "
        "facts.period_end, facts.fiscal_year, facts.fiscal_quarter, "
        "facts.as_of_date, facts.source_id, facts.source_definition_id, "
        "definitions.definition_text AS source_definition_text, "
        "definitions.comparability_level AS source_definition_comparability, "
        "facts.raw_object_id, facts.build_id AS fact_build_id, "
        "entities.build_id AS entity_build_id, metrics.build_id AS metric_build_id, "
        "definitions.build_id AS source_definition_build_id "
        "FROM standardized_facts facts "
        "LEFT JOIN canonical_entities entities "
        "ON entities.entity_id = facts.entity_id AND entities.build_id = ? "
        "LEFT JOIN metrics "
        "ON metrics.metric_id = facts.metric_id AND metrics.build_id = ? "
        "LEFT JOIN source_metric_definitions definitions "
        "ON definitions.definition_id = facts.source_definition_id "
        "AND definitions.build_id = ? "
        f"WHERE facts.fact_id IN ({placeholders}) AND facts.build_id = ? "
        "ORDER BY facts.entity_id, facts.metric_id, facts.period_end, facts.fact_id",
        (
            build["entity_build_id"],
            build["metric_build_id"],
            build["source_definition_build_id"],
            *fact_ids,
            build["fact_build_id"],
        ),
    )
    result = [dict(row) for row in rows]
    observed = {str(row["fact_id"]) for row in result}
    missing_facts = sorted(set(str(item) for item in fact_ids) - observed)
    if missing_facts:
        raise RuntimeError(
            f"Pinned evidence facts not found in QA build {qa_build_id}: "
            + ",".join(missing_facts[:20])
        )
    return result



def _infer_legacy_trial_metrics(
    row: dict[str, Any],
    evaluation_mode: str,
) -> dict[str, Any]:
    api_success = str(row.get("status") or "") == "succeeded"
    contract_success = api_success
    semantic_correct = str(row.get("match_status") or "") == "passed"
    return {
        **row,
        "trial_mode": _normalize_mode(evaluation_mode),
        "selected_evidence_ids": row.get("selected_evidence_ids") or [],
        "tool_trace": row.get("tool_trace") or [],
        "api_call_success": api_success,
        "json_contract_success": contract_success,
        "semantic_answer_correct": semantic_correct,
        "unit_currency_correct": semantic_correct,
        "row_completeness": semantic_correct,
        "order_correct": semantic_correct,
        "evidence_selection_correct": None,
        "end_to_end_correct": semantic_correct,
    }


def _normalize_mode(value: Any) -> str:
    mode = str(value or "gold_plan_given").strip().casefold()
    mode = MODE_ALIASES.get(mode, mode)
    if mode not in EMPIRICAL_MODES:
        raise ValueError(
            f"Unsupported empirical evaluation mode: {mode}; "
            f"expected one of {sorted(EMPIRICAL_MODES)}"
        )
    return mode


def _mode_contract(mode: str) -> dict[str, Any]:
    mode = _normalize_mode(mode)
    contracts = {
        "gold_plan_given": {
            "label": "Mode A: Gold Plan Given",
            "task": "Execute the supplied operation plan over the supplied evidence.",
            "measures": ["plan_execution", "answer_contract"],
        },
        "evidence_only": {
            "label": "Mode B: Evidence Only",
            "task": "Infer the calculation method from the question and evidence.",
            "measures": ["reasoning_program_formation", "answer_contract"],
        },
        "evidence_pool": {
            "label": "Mode C: Evidence Pool",
            "task": "Select relevant evidence from a pool with distractors and answer.",
            "measures": [
                "evidence_selection",
                "reasoning_program_formation",
                "answer_contract",
            ],
        },
        "retrieval_tool": {
            "label": "Mode D: Retrieval / Tool",
            "task": "Use registered tools to retrieve evidence and answer the question.",
            "measures": [
                "tool_use",
                "evidence_retrieval",
                "reasoning_program_formation",
                "answer_contract",
            ],
        },
    }
    return contracts[mode]


def _complete_answer_contract(
    client: OpenAICompatibleJsonClient,
    prompt: str,
    maximum_attempts: int,
    state: dict[str, Any],
    answer_schema: dict[str, Any] | None = None,
    require_evidence_selection: bool = False,
) -> tuple[dict[str, Any], dict[str, Any]]:
    failures = []
    schema = answer_schema
    for attempt in range(1, maximum_attempts + 1):
        try:
            attempt_prompt = _contract_repair_prompt(prompt, failures)
            completion = client.complete_json(attempt_prompt, temperature=0.0)
            state["api_call_success"] = True
            state["telemetry"] = dict(completion.telemetry)
            if schema is not None:
                registry_normalize_model_answer(completion.payload, schema)
            _selected_evidence_ids(
                completion.payload,
                required=require_evidence_selection,
            )
            telemetry = {
                **dict(completion.telemetry),
                "contract_attempt": attempt,
                "contract_failure_count": len(failures),
            }
            return completion.payload, telemetry
        except Exception as exc:
            failure_telemetry = dict(
                getattr(exc, "telemetry", {}) or {}
            )
            state["telemetry"] = {
                **dict(state.get("telemetry") or {}),
                **failure_telemetry,
            }
            state["api_call_success"] = bool(
                state["api_call_success"]
                or failure_telemetry.get("http_success")
            )
            failures.append(
                {
                    "attempt": attempt,
                    "error_type": type(exc).__name__,
                    "message": str(exc)[:300],
                }
            )
            if attempt >= maximum_attempts:
                raise
    raise RuntimeError("Unreachable empirical contract retry state")


def _selected_evidence_ids(
    payload: dict[str, Any],
    *,
    required: bool,
) -> list[str]:
    values = payload.get("selected_evidence_ids")
    if values is None and not required:
        return []
    if not isinstance(values, list):
        raise ValueError("selected_evidence_ids must be a JSON list")
    selected = [str(item).strip() for item in values if str(item).strip()]
    if required and not selected:
        raise ValueError("selected_evidence_ids must be non-empty in this mode")
    if len(selected) != len(set(selected)):
        raise ValueError("selected_evidence_ids must not contain duplicates")
    return selected


def _component_scores(
    schema: dict[str, Any],
    expected: dict[str, Any],
    observed: dict[str, Any],
    rubric: dict[str, Any],
    match_details: dict[str, Any],
    mode: str,
    expected_evidence_ids: set[str],
    selected_evidence_ids: set[str],
    *,
    api_call_success: bool,
    json_contract_success: bool,
) -> dict[str, Any]:
    semantic = _semantic_answer_correct(match_details)
    unit_currency = _unit_currency_correct(
        schema,
        expected,
        observed,
        rubric,
    )
    row_complete = _row_completeness(schema, expected, observed, rubric)
    order = _order_correct(schema, expected, observed, rubric)
    evidence: bool | None = None
    if mode in {"evidence_pool", "retrieval_tool"}:
        evidence = bool(expected_evidence_ids) and (
            selected_evidence_ids == expected_evidence_ids
        )
    end_to_end = all(
        (
            api_call_success,
            json_contract_success,
            semantic,
            unit_currency,
            row_complete,
            order,
            evidence is not False,
        )
    )
    return {
        "api_call_success": api_call_success,
        "json_contract_success": json_contract_success,
        "semantic_answer_correct": semantic,
        "unit_currency_correct": unit_currency,
        "row_completeness": row_complete,
        "order_correct": order,
        "evidence_selection_correct": evidence,
        "end_to_end_correct": end_to_end,
    }


def _failed_component_scores(
    mode: str,
    api_call_success: bool,
    json_contract_success: bool,
) -> dict[str, Any]:
    return {
        "api_call_success": api_call_success,
        "json_contract_success": json_contract_success,
        "semantic_answer_correct": False,
        "unit_currency_correct": False,
        "row_completeness": False,
        "order_correct": False,
        "evidence_selection_correct": (
            False if mode in {"evidence_pool", "retrieval_tool"} else None
        ),
        "end_to_end_correct": False,
    }


def _semantic_answer_correct(details: dict[str, Any]) -> bool:
    if "numeric_error" in details and "tolerance" in details:
        error = _decimal(details.get("numeric_error"))
        tolerance = _decimal(details.get("tolerance"))
        return bool(
            error is not None
            and tolerance is not None
            and error <= tolerance
        )
    checks = details.get("checks")
    if isinstance(checks, dict):
        semantic_checks = [
            bool(value)
            for key, value in checks.items()
            if key not in {"unit", "currency"}
        ]
        return bool(semantic_checks) and all(semantic_checks)
    return False


def _unit_currency_correct(
    schema: dict[str, Any],
    expected: dict[str, Any],
    observed: dict[str, Any],
    rubric: dict[str, Any],
) -> bool:
    gold = canonical_gold(schema, expected, rubric)
    requested_unit = str(
        rubric.get("requested_unit")
        or schema.get("requested_unit")
        or gold.get("unit")
        or ""
    )
    requested_currency = str(
        rubric.get("requested_currency")
        or schema.get("requested_currency")
        or gold.get("currency")
        or ""
    )
    observed_units = [
        str(observed.get(key) or "")
        for key in ("unit", "primary_unit", "secondary_unit")
        if observed.get(key) is not None
    ]
    observed_currencies = [
        str(observed.get(key) or "")
        for key in ("currency", "primary_currency", "secondary_currency")
        if observed.get(key) is not None
    ]
    unit_ok = (
        True
        if not rubric.get("unit_must_match")
        else bool(observed_units)
        and any(_same_token(requested_unit, item) for item in observed_units)
    )
    currency_ok = (
        True
        if not requested_currency
        else bool(observed_currencies)
        and any(
            _same_token(requested_currency, item)
            for item in observed_currencies
        )
    )
    return unit_ok and currency_ok


def _table_fields(answer_type: str) -> tuple[str, ...]:
    return {
        "comparison": ("rows",),
        "ranked_table": ("ranking_table",),
        "multi_metric_ranked_table": (
            "ranking_table",
            "secondary_metric_table",
        ),
        "filtered_rank_followup": (
            "ranking_table",
            "followup_table",
        ),
        "screening_table": ("screening_table",),
    }.get(answer_type, ())


def _row_completeness(
    schema: dict[str, Any],
    expected: dict[str, Any],
    observed: dict[str, Any],
    rubric: dict[str, Any],
) -> bool:
    gold = canonical_gold(schema, expected, rubric)
    fields = _table_fields(str(schema["type"]))
    if not fields:
        return True
    for field in fields:
        expected_rows = gold.get(field) or []
        observed_rows = observed.get(field)
        if not isinstance(observed_rows, list):
            return False
        if len(expected_rows) != len(observed_rows):
            return False
        for expected_row, observed_row in zip(expected_rows, observed_rows):
            if not isinstance(observed_row, dict):
                return False
            if not set(expected_row).issubset(observed_row):
                return False
    return True


def _order_correct(
    schema: dict[str, Any],
    expected: dict[str, Any],
    observed: dict[str, Any],
    rubric: dict[str, Any],
) -> bool:
    if not bool(rubric.get("order_required") or schema.get("order_required")):
        return True
    gold = canonical_gold(schema, expected, rubric)
    for field in _table_fields(str(schema["type"])):
        expected_rows = gold.get(field) or []
        observed_rows = observed.get(field) or []
        if len(expected_rows) != len(observed_rows):
            return False
        expected_order = [_row_identity(row) for row in expected_rows]
        observed_order = [_row_identity(row) for row in observed_rows]
        if expected_order != observed_order:
            return False
    return True


def _row_identity(row: Any) -> tuple[str, ...]:
    if not isinstance(row, dict):
        return ("invalid",)
    keys = [
        key
        for key in ("rank", "entity_id", "id", "period", "result_period")
        if key in row
    ]
    return tuple(str(row.get(key)) for key in keys)


def _trial_metric_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    count = len(rows)
    api_count = sum(bool(row.get("api_call_success")) for row in rows)
    contract_count = sum(
        bool(row.get("json_contract_success")) for row in rows
    )
    semantic_count = sum(
        bool(row.get("semantic_answer_correct")) for row in rows
    )
    end_to_end_count = sum(
        bool(row.get("end_to_end_correct")) for row in rows
    )
    evidence_rows = [
        row
        for row in rows
        if row.get("evidence_selection_correct") is not None
    ]
    evidence_count = sum(
        bool(row.get("evidence_selection_correct")) for row in evidence_rows
    )
    return {
        "trial_count": count,
        "api_call_success_count": api_count,
        "api_call_success_rate": _rate(api_count, count),
        "json_contract_success_count": contract_count,
        "contract_success_rate": _rate(contract_count, count),
        "contract_success_given_api_rate": _rate(
            contract_count,
            api_count,
        ),
        "semantic_answer_correct_count": semantic_count,
        "semantic_accuracy_given_valid_contract": _rate(
            semantic_count,
            contract_count,
        ),
        "unit_currency_correct_rate": _rate(
            sum(bool(row.get("unit_currency_correct")) for row in rows),
            contract_count,
        ),
        "row_completeness_rate": _rate(
            sum(bool(row.get("row_completeness")) for row in rows),
            contract_count,
        ),
        "order_correct_rate": _rate(
            sum(bool(row.get("order_correct")) for row in rows),
            contract_count,
        ),
        "evidence_selection_applicable_count": len(evidence_rows),
        "evidence_selection_correct_rate": (
            _rate(evidence_count, len(evidence_rows))
            if evidence_rows
            else None
        ),
        "end_to_end_correct_count": end_to_end_count,
        "end_to_end_accuracy": _rate(end_to_end_count, count),
        "answer_pass_count": sum(
            row.get("match_status") == "passed" for row in rows
        ),
        "answer_pass_rate": _rate(
            sum(row.get("match_status") == "passed" for row in rows),
            contract_count,
        ),
    }


def _load_distractor_facts(
    db: DBProtocol,
    bundle: dict[str, Any],
    excluded_fact_ids: set[str],
    limit: int,
    seed: str,
) -> list[dict[str, Any]]:
    if limit <= 0:
        return []
    build = _pinned_builds(db, str(bundle["qa_build_id"]))
    candidates = [
        str(row["fact_id"])
        for row in db.fetchall(
            "SELECT fact_id FROM standardized_facts "
            "WHERE build_id = ? AND graph_ready = ? ORDER BY fact_id LIMIT ?",
            (
                build["fact_build_id"],
                1,
                max(limit * 20, limit + len(excluded_fact_ids)),
            ),
        )
        if str(row["fact_id"]) not in excluded_fact_ids
    ]
    candidates.sort(
        key=lambda fact_id: _hash(
            (seed, bundle["qa_id"], "distractor", fact_id)
        )
    )
    return _load_evidence_facts(
        db,
        str(bundle["qa_build_id"]),
        candidates[:limit],
    )


def _pinned_builds(db: DBProtocol, qa_build_id: str) -> dict[str, Any]:
    row = db.fetchone(
        "SELECT fact_build_id, entity_build_id, metric_build_id, "
        "source_definition_build_id FROM qa_builds WHERE qa_build_id = ?",
        (qa_build_id,),
    )
    if not row:
        raise RuntimeError(f"Unknown QA build: {qa_build_id}")
    return dict(row)


def _tool_contracts() -> list[dict[str, Any]]:
    return [
        {
            "name": "search_entities",
            "arguments": {"query": "company or country name"},
        },
        {
            "name": "search_metrics",
            "arguments": {"query": "financial metric name"},
        },
        {
            "name": "search_facts",
            "arguments": {
                "entity_id": "exact entity_id",
                "metric_id": "exact metric_id",
                "fiscal_year": "optional integer",
                "period_start": "optional YYYY-MM-DD",
                "period_end": "optional YYYY-MM-DD",
            },
        },
        {
            "name": "calculator",
            "arguments": {
                "operation": "difference, ratio, percent_change, or mean",
                "values": ["numeric strings"],
            },
        },
    ]


def _run_retrieval_tool_loop(
    db: DBProtocol,
    client: OpenAICompatibleJsonClient,
    bundle: dict[str, Any],
    prompt: str,
    empirical: dict[str, Any],
    state: dict[str, Any],
    *,
    tool_db_lock: Any | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    maximum_rounds = max(int(empirical.get("maximum_tool_rounds") or 8), 1)
    answer_schema = _resolved_answer_schema(bundle)
    telemetry_totals: dict[str, Any] = {}
    for round_number in range(1, maximum_rounds + 1):
        round_prompt = prompt
        if state["tool_trace"]:
            round_prompt += "\n\nTOOL TRANSCRIPT:\n" + json.dumps(
                state["tool_trace"],
                ensure_ascii=False,
                sort_keys=True,
                default=str,
            )
            round_prompt += (
                "\nContinue with another registered tool call or return action=final."
            )
        completion = client.complete_json(round_prompt, temperature=0.0)
        state["api_call_success"] = True
        telemetry_totals = _merge_telemetry(
            telemetry_totals,
            dict(completion.telemetry),
        )
        state["telemetry"] = telemetry_totals
        payload = completion.payload
        action = str(payload.get("action") or "").strip().casefold()
        if action == "final" or (
            payload.get("answer_text") and payload.get("answer_payload")
        ):
            if not state["tool_trace"]:
                raise ValueError(
                    "retrieval_tool mode requires at least one executed tool call"
                )
            _selected_evidence_ids(payload, required=True)
            registry_normalize_model_answer(payload, answer_schema)
            telemetry_totals["tool_round_count"] = round_number
            return payload, telemetry_totals
        if action != "tool_call":
            raise ValueError(
                "retrieval_tool response must use action=tool_call or action=final"
            )
        tool_name = str(payload.get("tool") or "")
        arguments = payload.get("arguments")
        if not isinstance(arguments, dict):
            raise ValueError("tool call arguments must be a JSON object")
        if tool_db_lock is None:
            result = _execute_registered_tool(
                db,
                str(bundle["qa_build_id"]),
                tool_name,
                arguments,
            )
        else:
            with tool_db_lock:
                result = _execute_registered_tool(
                    db,
                    str(bundle["qa_build_id"]),
                    tool_name,
                    arguments,
                )
        state["tool_trace"].append(
            {
                "round": round_number,
                "tool": tool_name,
                "arguments": arguments,
                "result": result,
            }
        )
    raise RuntimeError("retrieval_tool exceeded maximum_tool_rounds")


def _execute_registered_tool(
    db: DBProtocol,
    qa_build_id: str,
    tool_name: str,
    arguments: dict[str, Any],
) -> Any:
    build = _pinned_builds(db, qa_build_id)
    if tool_name == "search_entities":
        query = str(arguments.get("query") or "").strip()
        if not query:
            raise ValueError("search_entities.query is required")
        return [
            dict(row)
            for row in db.fetchall(
                "SELECT entity_id, canonical_name, entity_type, market, ticker "
                "FROM canonical_entities WHERE build_id = ? "
                "AND LOWER(canonical_name) LIKE ? "
                "ORDER BY canonical_name, entity_id LIMIT 20",
                (build["entity_build_id"], f"%{query.casefold()}%"),
            )
        ]
    if tool_name == "search_metrics":
        query = str(arguments.get("query") or "").strip()
        if not query:
            raise ValueError("search_metrics.query is required")
        return [
            dict(row)
            for row in db.fetchall(
                "SELECT metric_id, canonical_name, statement_type, period_type "
                "FROM metrics WHERE build_id = ? "
                "AND LOWER(canonical_name) LIKE ? "
                "ORDER BY canonical_name, metric_id LIMIT 20",
                (build["metric_build_id"], f"%{query.casefold()}%"),
            )
        ]
    if tool_name == "search_facts":
        entity_id = str(arguments.get("entity_id") or "").strip()
        metric_id = str(arguments.get("metric_id") or "").strip()
        if not entity_id or not metric_id:
            raise ValueError(
                "search_facts requires entity_id and metric_id"
            )
        conditions = [
            "build_id = ?",
            "entity_id = ?",
            "metric_id = ?",
            "graph_ready = ?",
            "(is_forecast = ? OR is_forecast IS NULL)",
        ]
        params: list[Any] = [
            build["fact_build_id"],
            entity_id,
            metric_id,
            1,
            0,
        ]
        for field in ("fiscal_year", "period_start", "period_end"):
            value = arguments.get(field)
            if value is not None and str(value).strip():
                conditions.append(f"{field} = ?")
                params.append(value)
        rows = db.fetchall(
            "SELECT fact_id FROM standardized_facts WHERE "
            + " AND ".join(conditions)
            + " ORDER BY period_end, fact_id LIMIT 100",
            params,
        )
        return _load_evidence_facts(
            db,
            qa_build_id,
            [str(row["fact_id"]) for row in rows],
        )
    if tool_name == "calculator":
        return _calculator(arguments)
    raise ValueError(f"Unknown retrieval tool: {tool_name}")


def _calculator(arguments: dict[str, Any]) -> dict[str, str]:
    operation = str(arguments.get("operation") or "").strip().casefold()
    raw_values = arguments.get("values")
    if not isinstance(raw_values, list) or not raw_values:
        raise ValueError("calculator.values must be a non-empty list")
    values = [_decimal(item) for item in raw_values]
    if any(item is None for item in values):
        raise ValueError("calculator.values must all be numeric")
    numbers = [item for item in values if item is not None]
    if operation == "difference" and len(numbers) == 2:
        result = numbers[0] - numbers[1]
    elif operation == "ratio" and len(numbers) == 2:
        if numbers[1] == 0:
            raise ValueError("calculator ratio denominator is zero")
        result = numbers[0] / numbers[1]
    elif operation == "percent_change" and len(numbers) == 2:
        if numbers[0] == 0:
            raise ValueError("calculator percent_change base is zero")
        result = (numbers[1] - numbers[0]) / abs(numbers[0]) * Decimal("100")
    elif operation == "mean":
        result = sum(numbers, Decimal("0")) / Decimal(len(numbers))
    else:
        raise ValueError(
            "Unsupported calculator operation or argument cardinality"
        )
    return {"value": format(result, "f")}


def _merge_telemetry(
    accumulated: dict[str, Any],
    current: dict[str, Any],
) -> dict[str, Any]:
    out = {**accumulated, **current}
    for key in (
        "prompt_tokens",
        "completion_tokens",
        "total_tokens",
        "estimated_cost",
    ):
        if accumulated.get(key) is not None or current.get(key) is not None:
            out[key] = float(accumulated.get(key) or 0) + float(
                current.get(key) or 0
            )
    return out


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
    rows: list[dict[str, Any]],
    dimensions: dict[str, dict[str, str]],
) -> dict[str, dict[str, dict[str, Any]]]:
    output: dict[str, dict[str, dict[str, Any]]] = {}
    for field in (
        "market_subset",
        "benchmark_task",
        "language",
        "answer_type",
        "task_subtype",
    ):
        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in rows:
            value = dimensions.get(str(row["qa_id"]), {}).get(
                field,
                "unknown",
            )
            grouped[value].append(row)
        output[field] = {
            value: _trial_metric_summary(grouped_rows)
            for value, grouped_rows in sorted(grouped.items())
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
