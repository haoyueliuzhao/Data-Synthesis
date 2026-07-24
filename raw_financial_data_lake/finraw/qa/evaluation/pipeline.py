from __future__ import annotations

import hashlib
import json
import subprocess
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from finraw.db.client import DBProtocol
from finraw.qa.evaluation.aggregation import (
    adjudication_dimensions,
    aggregate_judgments,
    needs_adjudication,
)
from finraw.qa.evaluation.contracts import EVALUATION_SYSTEM_VERSION, RUBRIC_VERSION
from finraw.qa.evaluation.dataset_metrics import (
    compute_dataset_role_values,
    resolve_dataset_role_contract,
)
from finraw.qa.evaluation.input_views import load_evaluation_bundles
from finraw.qa.evaluation.judge import (
    FinancialQualityJudge,
    JudgeFunction,
)
from finraw.qa.evaluation.reports import build_quality_report
from finraw.qa.evaluation.required_checks import (
    required_check_manifest,
    required_check_manifest_hash,
)
from finraw.qa.evaluation.rubrics import rubric_for_task, rubric_hash
from finraw.qa.evaluation.schema import ensure_evaluation_schema
from finraw.qa.schema import ensure_qa_schema
from finraw.qa.store import insert_rows, json_value


RUN_COLUMNS = [
    "evaluation_run_id",
    "qa_build_id",
    "rubric_version",
    "rubric_hash",
    "evaluation_config_hash",
    "judge_config_hash",
    "judge_manifest",
    "sample_manifest",
    "sample_manifest_hash",
    "calibration_version",
    "evaluation_mode",
    "status",
    "started_at",
    "completed_at",
    "git_commit_sha",
    "notes",
]

CALL_COLUMNS = [
    "judge_call_id",
    "evaluation_run_id",
    "qa_id",
    "judge_role",
    "provider",
    "requested_model",
    "response_model",
    "prompt_hash",
    "response_hash",
    "input_view_hash",
    "scores",
    "reviewed_dimensions",
    "resolutions",
    "fatal_flags",
    "issue_codes",
    "confidence",
    "escalate_to_human",
    "brief_justification",
    "telemetry",
    "status",
    "error_message",
    "created_at",
]

ITEM_COLUMNS = [
    "evaluation_item_id",
    "evaluation_run_id",
    "qa_id",
    "deterministic_gate_status",
    "deterministic_gate_reasons",
    "dimension_scores",
    "subjective_quality_score",
    "standalone_financial_value_score",
    "dataset_role_value_score",
    "coverage_contributions",
    "dataset_role_components",
    "judge_disagreement",
    "judge_confidence",
    "fatal_flags",
    "confirmed_fatal_flags",
    "issue_codes",
    "decision",
    "decision_reasons",
    "created_at",
]


def init_quality_evaluation(
    db: DBProtocol,
    config: dict[str, Any],
    qa_build_id: str,
    *,
    limit: int | None = None,
    evaluation_mode: str | None = None,
) -> dict[str, Any]:
    ensure_qa_schema(db)
    ensure_evaluation_schema(db)
    build_row = db.fetchone(
        "SELECT * FROM qa_builds WHERE qa_build_id = ?", (qa_build_id,)
    )
    if not build_row:
        raise RuntimeError(f"Unknown QA build: {qa_build_id}")
    quality_config = _quality_config(config)
    mode = str(evaluation_mode or quality_config.get("evaluation_mode") or "advisory")
    if mode not in {"advisory", "calibration", "release_gate", "retrospective"}:
        raise ValueError(f"Unsupported evaluation mode: {mode}")
    statuses = tuple(
        str(item)
        for item in quality_config.get("sample_validation_statuses") or ["passed"]
    )
    placeholders = ",".join("?" for _ in statuses)
    rows = db.fetchall(
        f"SELECT qa_id, stable_qa_id, validation_status FROM qa_samples "
        f"WHERE qa_build_id = ? AND validation_status IN ({placeholders}) "
        "ORDER BY qa_id",
        (qa_build_id, *statuses),
    )
    sample_rows = [dict(row) for row in rows]
    if limit is not None and limit > 0 and len(sample_rows) > limit:
        seed = str(quality_config.get("sample_seed") or "qa-quality-v1")
        sample_rows = sorted(
            sample_rows,
            key=lambda row: _hash((qa_build_id, seed, row["qa_id"])),
        )[:limit]
        sample_rows.sort(key=lambda row: str(row["qa_id"]))
    if not sample_rows:
        raise RuntimeError(f"QA build {qa_build_id} has no eligible samples to evaluate")

    evaluation_run_id = _new_run_id()
    dataset_role_contract = resolve_dataset_role_contract(
        quality_config.get("dataset_role_contract") or {}
    )
    dataset_role_contract_hash = _hash(dataset_role_contract)
    sample_manifest = {
        "population": "qa_samples",
        "validation_statuses": list(statuses),
        "sample_count": len(sample_rows),
        "qa_ids": [str(row["qa_id"]) for row in sample_rows],
        "stable_qa_ids": [str(row["stable_qa_id"]) for row in sample_rows],
        "required_check_manifest_hash": required_check_manifest_hash(),
        "dataset_role_contract_hash": dataset_role_contract_hash,
    }
    judge_manifest = _judge_manifest(quality_config)
    run = {
        "evaluation_run_id": evaluation_run_id,
        "qa_build_id": qa_build_id,
        "rubric_version": str(quality_config.get("rubric_version") or RUBRIC_VERSION),
        "rubric_hash": rubric_hash(),
        "evaluation_config_hash": _hash(_redact_config(quality_config)),
        "judge_config_hash": _hash(judge_manifest),
        "judge_manifest": judge_manifest,
        "sample_manifest": sample_manifest,
        "sample_manifest_hash": _hash(sample_manifest),
        "calibration_version": quality_config.get("calibration", {}).get(
            "calibration_set_version"
        ),
        "evaluation_mode": mode,
        "status": "initialized",
        "started_at": _now(),
        "completed_at": None,
        "git_commit_sha": _git_commit_sha(),
        "notes": {
            "evaluation_system_version": EVALUATION_SYSTEM_VERSION,
            "required_check_manifest": required_check_manifest(),
            "dataset_role_contract": dataset_role_contract,
            "dataset_role_contract_hash": dataset_role_contract_hash,
            "quality_config": _redact_config(quality_config),
            "qa_build_status": dict(build_row).get("status"),
            "thresholds_are_calibrated": bool(
                quality_config.get("calibration", {}).get("thresholds_are_calibrated")
            ),
        },
    }
    insert_rows(
        db,
        "qa_evaluation_runs",
        [run],
        RUN_COLUMNS,
        {"judge_manifest", "sample_manifest", "notes"},
    )
    return {
        "evaluation_run_id": evaluation_run_id,
        "qa_build_id": qa_build_id,
        "evaluation_mode": mode,
        "sample_count": len(sample_rows),
        "sample_manifest_hash": run["sample_manifest_hash"],
        "rubric_hash": run["rubric_hash"],
        "judge_config_hash": run["judge_config_hash"],
        "status": "initialized",
    }


def run_quality_evaluation(
    db: DBProtocol,
    evaluation_run_id: str,
    *,
    output_dir: str | None = None,
    judge_function: JudgeFunction | None = None,
) -> dict[str, Any]:
    run = _evaluation_run(db, evaluation_run_id)
    _assert_run_system_version(run)
    config = dict(run["notes"].get("quality_config") or {})
    base_roles = tuple(
        str(role)
        for role in (config.get("judge_routing") or {}).get("base_judges")
        or ("surface_financial_analyst", "grounded_qa_auditor")
    )
    result = _evaluate_roles(
        db,
        run,
        base_roles,
        config,
        judge_function=judge_function,
        only_qa_ids=None,
    )
    completed_status = "completed" if result["failed_call_count"] == 0 else "partial"
    db.execute(
        "UPDATE qa_evaluation_runs SET status = ?, completed_at = ? "
        "WHERE evaluation_run_id = ?",
        (completed_status, _now(), evaluation_run_id),
    )
    return quality_evaluation_report(db, evaluation_run_id, output_dir=output_dir)


def adjudicate_quality_run(
    db: DBProtocol,
    evaluation_run_id: str,
    *,
    output_dir: str | None = None,
    judge_function: JudgeFunction | None = None,
) -> dict[str, Any]:
    run = _evaluation_run(db, evaluation_run_id)
    _assert_run_system_version(run)
    config = dict(run["notes"].get("quality_config") or {})
    items = _evaluation_items(db, evaluation_run_id)
    qa_ids = [
        str(item["qa_id"])
        for item in items
        if item.get("deterministic_gate_status") == "passed"
        and needs_adjudication(item)
        and adjudication_dimensions(item)
    ]
    if qa_ids:
        role = str(
            (config.get("judge_routing") or {}).get("adjudicator")
            or "adversarial_reviewer"
        )
        _evaluate_roles(
            db,
            run,
            (role,),
            config,
            judge_function=judge_function,
            only_qa_ids=set(qa_ids),
        )
    return quality_evaluation_report(db, evaluation_run_id, output_dir=output_dir)


def export_manual_review_queue(
    db: DBProtocol,
    evaluation_run_id: str,
    output_dir: str,
) -> dict[str, Any]:
    report = quality_evaluation_report(db, evaluation_run_id, output_dir=output_dir)
    queue_path = next(
        path
        for path in report.get("written_files", [])
        if path.endswith(("manual_review_queue.jsonl", "llm_secondary_review_queue.jsonl"))
    )
    return {
        "evaluation_run_id": evaluation_run_id,
        "manual_review_count": report["decision_counts"].get("manual_review", 0),
        "output": queue_path,
    }


def quality_evaluation_report(
    db: DBProtocol,
    evaluation_run_id: str,
    *,
    output_dir: str | None = None,
) -> dict[str, Any]:
    run = _evaluation_run(db, evaluation_run_id)
    qa_ids = list(run["sample_manifest"].get("qa_ids") or [])
    bundles = load_evaluation_bundles(db, run["qa_build_id"], qa_ids=qa_ids)
    items = _evaluation_items(db, evaluation_run_id)
    calls = _judge_calls(db, evaluation_run_id)
    return build_quality_report(run, bundles, items, calls, output_dir=output_dir)


def _evaluate_roles(
    db: DBProtocol,
    run: dict[str, Any],
    roles: tuple[str, ...],
    config: dict[str, Any],
    *,
    judge_function: JudgeFunction | None,
    only_qa_ids: set[str] | None,
) -> dict[str, int]:
    qa_ids = list(run["sample_manifest"].get("qa_ids") or [])
    if only_qa_ids is not None:
        qa_ids = [qa_id for qa_id in qa_ids if qa_id in only_qa_ids]
    bundles = load_evaluation_bundles(db, run["qa_build_id"], qa_ids=qa_ids)
    dataset_roles = compute_dataset_role_values(
        load_evaluation_bundles(
            db,
            run["qa_build_id"],
            qa_ids=run["sample_manifest"].get("qa_ids") or [],
        ),
        contract=(run.get("notes") or {}).get("dataset_role_contract")
        or config.get("dataset_role_contract")
        or {},
    )
    existing = {
        (str(row["qa_id"]), str(row["judge_role"]))
        for row in db.fetchall(
            "SELECT qa_id, judge_role FROM qa_judge_calls "
            "WHERE evaluation_run_id = ? AND status = 'succeeded'",
            (run["evaluation_run_id"],),
        )
    }
    judge = FinancialQualityJudge(config)
    current_items = {
        str(item["qa_id"]): item
        for item in _evaluation_items(db, run["evaluation_run_id"])
    }
    tasks = []
    for bundle in bundles:
        if bundle["deterministic_gate_status"] != "passed":
            continue
        for role in roles:
            if (bundle["qa_id"], role) not in existing:
                tasks.append((bundle, role))

    max_workers = max(int(config.get("maximum_concurrency", 4)), 1)

    def invoke(bundle: dict[str, Any], role: str) -> dict[str, Any]:
        if role == "surface_financial_analyst":
            view = bundle["surface_view"]
        elif role == "adversarial_reviewer":
            provisional = current_items.get(str(bundle["qa_id"])) or {}
            reviewed_dimensions = adjudication_dimensions(provisional)
            view = {
                **bundle["grounded_view"],
                "reviewed_dimensions": reviewed_dimensions,
                "provisional_evaluation": {
                    "dimension_scores": {
                        dimension: (provisional.get("dimension_scores") or {}).get(
                            dimension
                        )
                        for dimension in reviewed_dimensions
                    },
                    "fatal_flags": provisional.get("fatal_flags") or [],
                    "issue_codes": provisional.get("issue_codes") or [],
                    "decision_reasons": provisional.get("decision_reasons") or [],
                },
            }
        else:
            view = bundle["grounded_view"]
        rubric = rubric_for_task(
            bundle["distribution_label"].get("benchmark_task") or "T2"
        )
        call_id = "qajudge_" + _hash(
            (run["evaluation_run_id"], bundle["qa_id"], role)
        )[:24]
        try:
            if judge_function:
                payload, telemetry = judge_function(role, view, rubric)
                from finraw.qa.evaluation.contracts import (
                    normalize_adversarial_payload,
                    normalize_judge_payload,
                )

                payload = (
                    normalize_adversarial_payload(
                        payload, list(view.get("reviewed_dimensions") or [])
                    )
                    if role == "adversarial_reviewer"
                    else normalize_judge_payload(payload, role)
                )
            else:
                payload, telemetry = judge.evaluate(role, view, rubric)
            return _call_row(
                run, bundle["qa_id"], role, call_id, payload, telemetry, "succeeded", None
            )
        except Exception as exc:
            telemetry = getattr(exc, "telemetry", {})
            return _call_row(
                run,
                bundle["qa_id"],
                role,
                call_id,
                {},
                telemetry,
                "failed",
                str(exc)[:1000],
            )

    call_rows = []
    if max_workers == 1 or len(tasks) <= 1:
        call_rows = [invoke(bundle, role) for bundle, role in tasks]
    else:
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(invoke, bundle, role): (bundle["qa_id"], role)
                for bundle, role in tasks
            }
            for future in as_completed(futures):
                call_rows.append(future.result())
    insert_rows(
        db,
        "qa_judge_calls",
        call_rows,
        CALL_COLUMNS,
        {
            "scores",
            "reviewed_dimensions",
            "resolutions",
            "fatal_flags",
            "issue_codes",
            "brief_justification",
            "telemetry",
        },
    )

    all_calls = _judge_calls(db, run["evaluation_run_id"])
    calls_by_qa: dict[str, list[dict[str, Any]]] = {}
    for row in all_calls:
        calls_by_qa.setdefault(str(row["qa_id"]), []).append(row)
    item_rows = []
    for bundle in bundles:
        aggregated = aggregate_judgments(
            bundle,
            calls_by_qa.get(str(bundle["qa_id"]), []),
            dataset_roles.get(str(bundle["qa_id"]), {}),
            config,
        )
        item_rows.append(
            {
                "evaluation_item_id": "qaevalitem_"
                + _hash((run["evaluation_run_id"], bundle["qa_id"]))[:24],
                "evaluation_run_id": run["evaluation_run_id"],
                **aggregated,
                "created_at": _now(),
            }
        )
    insert_rows(
        db,
        "qa_evaluation_items",
        item_rows,
        ITEM_COLUMNS,
        {
            "deterministic_gate_reasons",
            "dimension_scores",
            "coverage_contributions",
            "dataset_role_components",
            "judge_disagreement",
            "fatal_flags",
            "confirmed_fatal_flags",
            "issue_codes",
            "decision_reasons",
        },
    )
    return {
        "attempted_call_count": len(call_rows),
        "failed_call_count": sum(row["status"] != "succeeded" for row in call_rows),
        "item_count": len(item_rows),
    }


def _call_row(
    run: dict[str, Any],
    qa_id: str,
    role: str,
    call_id: str,
    payload: dict[str, Any],
    telemetry: dict[str, Any],
    status: str,
    error_message: str | None,
) -> dict[str, Any]:
    manifest = run.get("judge_manifest") or {}
    role_manifest = dict((manifest.get("roles") or {}).get(role) or {})
    return {
        "judge_call_id": call_id,
        "evaluation_run_id": run["evaluation_run_id"],
        "qa_id": qa_id,
        "judge_role": role,
        "provider": telemetry.get("provider") or role_manifest.get("provider"),
        "requested_model": telemetry.get("model_requested")
        or role_manifest.get("requested_model"),
        "response_model": telemetry.get("response_model")
        or telemetry.get("model_selected"),
        "prompt_hash": telemetry.get("prompt_hash") or telemetry.get("request_hash"),
        "response_hash": telemetry.get("response_hash"),
        "input_view_hash": telemetry.get("input_view_hash") or "unknown",
        "scores": payload.get("scores") or {},
        "reviewed_dimensions": payload.get("reviewed_dimensions") or [],
        "resolutions": payload.get("resolutions") or {},
        "fatal_flags": payload.get("fatal_flags") or [],
        "issue_codes": payload.get("issue_codes") or [],
        "confidence": payload.get("confidence"),
        "escalate_to_human": bool(payload.get("escalate_to_human")),
        "brief_justification": payload.get("brief_justification") or {},
        "telemetry": telemetry,
        "status": status,
        "error_message": error_message,
        "created_at": _now(),
    }


def _assert_run_system_version(run: dict[str, Any]) -> None:
    observed = str(
        (run.get("notes") or {}).get("evaluation_system_version") or ""
    )
    if observed != EVALUATION_SYSTEM_VERSION:
        raise RuntimeError(
            "Evaluation run contract mismatch: "
            f"run={observed or 'unknown'}, current={EVALUATION_SYSTEM_VERSION}. "
            "Initialize a new evaluation run instead of mixing judge contracts."
        )


def _evaluation_run(db: DBProtocol, evaluation_run_id: str) -> dict[str, Any]:
    ensure_evaluation_schema(db)
    row = db.fetchone(
        "SELECT * FROM qa_evaluation_runs WHERE evaluation_run_id = ?",
        (evaluation_run_id,),
    )
    if not row:
        raise RuntimeError(f"Unknown QA evaluation run: {evaluation_run_id}")
    out = dict(row)
    for key, default in {
        "judge_manifest": {},
        "sample_manifest": {},
        "notes": {},
    }.items():
        out[key] = json_value(out.get(key), default)
    return out


def _judge_calls(db: DBProtocol, evaluation_run_id: str) -> list[dict[str, Any]]:
    rows = []
    for raw in db.fetchall(
        "SELECT * FROM qa_judge_calls WHERE evaluation_run_id = ? "
        "ORDER BY qa_id, judge_role",
        (evaluation_run_id,),
    ):
        row = dict(raw)
        for key, default in {
            "scores": {},
            "reviewed_dimensions": [],
            "resolutions": {},
            "fatal_flags": [],
            "issue_codes": [],
            "brief_justification": {},
            "telemetry": {},
        }.items():
            row[key] = json_value(row.get(key), default)
        rows.append(row)
    return rows


def _evaluation_items(db: DBProtocol, evaluation_run_id: str) -> list[dict[str, Any]]:
    rows = []
    for raw in db.fetchall(
        "SELECT * FROM qa_evaluation_items WHERE evaluation_run_id = ? ORDER BY qa_id",
        (evaluation_run_id,),
    ):
        row = dict(raw)
        for key, default in {
            "deterministic_gate_reasons": [],
            "dimension_scores": {},
            "coverage_contributions": [],
            "dataset_role_components": {},
            "judge_disagreement": {},
            "fatal_flags": [],
            "confirmed_fatal_flags": [],
            "issue_codes": [],
            "decision_reasons": [],
        }.items():
            row[key] = json_value(row.get(key), default)
        rows.append(row)
    return rows


def _quality_config(config: dict[str, Any]) -> dict[str, Any]:
    quality = dict((config.get("qa") or {}).get("quality_evaluation") or {})
    if not quality:
        raise RuntimeError("qa.quality_evaluation configuration is required")
    return quality


def _judge_manifest(config: dict[str, Any]) -> dict[str, Any]:
    shared = dict(config.get("llm") or {})
    roles = {}
    for role in (
        "surface_financial_analyst",
        "grounded_qa_auditor",
        "adversarial_reviewer",
    ):
        role_config = {**shared, **dict((config.get("judges") or {}).get(role) or {})}
        endpoint = str(role_config.get("endpoint") or "")
        roles[role] = {
            "provider": role_config.get("provider") or "openai_compatible",
            "requested_model": role_config.get("model"),
            "endpoint_host": urlparse(endpoint).netloc if endpoint else None,
            "api_key_env": role_config.get("api_key_env"),
            "auto_select_model": bool(role_config.get("auto_select_model")),
            "fallback_models": list(role_config.get("fallback_models") or []),
        }
    return {"roles": roles, "routing": config.get("judge_routing") or {}}


def _redact_config(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            str(key): (
                "<redacted>"
                if str(key).casefold() in {"api_key", "authorization", "token"}
                else _redact_config(item)
            )
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_redact_config(item) for item in value]
    return value


def _new_run_id() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    return f"qaeval_{stamp}_{uuid.uuid4().hex[:8]}"


def _git_commit_sha() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=Path(__file__).resolve().parents[3],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except Exception:
        return "unknown"


def _hash(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
