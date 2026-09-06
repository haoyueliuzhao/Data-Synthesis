"""One preregistered online population, followed by zero-call evidence analysis."""

from __future__ import annotations

import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from importlib.metadata import version
from itertools import combinations
from pathlib import Path
from typing import Any

from trusted_synthesis.domains.finance.qa_vnext.protocol import contract
from trusted_synthesis.domains.finance.qa_vnext.runtime import DurableStore, PublicQARuntime

from .models import STAGE, TASK_GROUPS, identity, read_json, record, require, sha
from .plan import (
    DESIGN_BYTES,
    DESIGN_SHA256,
    TaskPanel,
    freeze_condition,
    seal_directory,
    source_snapshot,
    verify_directory,
    verify_source_snapshot,
)
from .qualification import compare_qualified_sessions, qualify_session
from .representation import export_candidates, register_tokenizer, tokenize_candidates
from .transport import OnlineModelCallback, TransportConfig


def _software() -> dict[str, Any]:
    require(sys.version_info >= (3, 11), "run.python_total_deadline_support")
    return record(
        "software",
        python_version=sys.version,
        packages={
            name: version(name)
            for name in (
                "httpx",
                "pydantic",
                "transformers",
                "tokenizers",
                "jinja2",
                "huggingface-hub",
            )
        },
    )


def prepare(root: Path, directory: Path, design_path: Path, *, run_tag: str) -> dict[str, Any]:
    """Zero Provider calls. Source must already be committed, and output must not exist."""
    from .controls import run_controls

    root, directory = root.resolve(), directory.resolve()
    require(directory.name == "preparation", "prepare.directory_name")
    design = design_path.read_bytes()
    require(len(design) == DESIGN_BYTES and sha(design) == DESIGN_SHA256, "prepare.design_bytes")
    implementation = source_snapshot(root)
    config = TransportConfig()
    condition, registrations, panel = freeze_condition(
        root, config.as_record(), implementation, run_tag=run_tag
    )
    store = DurableStore(directory)
    store.write("experiment_design.txt", design)
    store.json("implementation.json", implementation)
    store.json("configuration.json", config.as_record())
    store.json("software.json", _software())
    store.json("condition.json", condition)
    store.json("registrations.json", registrations)
    store.json("catalog.json", panel.catalog.descriptor)
    store.json("protocol.json", contract())
    store.json("coverage.json", panel.coverage)
    tokenizer = register_tokenizer(root)
    store.json("tokenizer_binding.json", tokenizer)
    controls = run_controls(panel, directory / "controls", config)
    require(controls["passed"] is True, "prepare.offline_controls")
    report = record(
        "preparation",
        stage=STAGE,
        condition_id=condition["id"],
        implementation_id=implementation["id"],
        controls_id=controls["id"],
        tokenizer_binding_id=tokenizer["id"],
        session_registration_ids=[item["id"] for item in registrations],
        execution_directory=str(directory.parent / "execution"),
        provider_attempts=0,
        student_parameter_loads=0,
        prepared=True,
    )
    store.json("report.json", report)
    seal_directory(store, kind="preparation_manifest", preparation_id=report["id"])
    return report


def _prepared(root: Path, directory: Path) -> dict[str, Any]:
    manifest = verify_directory(directory, kind="preparation_manifest")
    values = {
        key: read_json((directory / (key + ".json")).read_bytes())
        for key in (
            "report",
            "condition",
            "implementation",
            "configuration",
            "registrations",
            "tokenizer_binding",
            "coverage",
            "software",
        )
    }
    identity(values["report"], "preparation")
    verify_source_snapshot(root, values["implementation"])
    config = TransportConfig()
    require(_software() == values["software"], "run.frozen_software")
    require(config.as_record() == values["configuration"], "run.frozen_configuration")
    condition, registrations, panel = freeze_condition(
        root, config.as_record(), values["implementation"], run_tag=values["condition"]["run_tag"]
    )
    require(
        condition == values["condition"]
        and registrations == values["registrations"]
        and panel.coverage == values["coverage"],
        "run.frozen_population",
    )
    require(register_tokenizer(root) == values["tokenizer_binding"], "run.frozen_tokenizer_assets")
    require(
        values["report"]["condition_id"] == condition["id"]
        and values["report"]["execution_directory"] == str(directory.parent / "execution")
        and manifest["preparation_id"] == values["report"]["id"],
        "run.preparation_binding",
    )
    return {**values, "manifest": manifest, "config": config, "panel": panel}


def _session_start(registration: dict[str, Any], *, started: bool, reason: str) -> dict[str, Any]:
    return record(
        "session_start",
        status="started" if started else "not_started",
        reason=reason,
        session_id=registration["session_id"],
        registered_id=registration["id"],
    )


def _run_session(
    panel: TaskPanel,
    config: TransportConfig,
    registration: dict[str, Any],
    store: DurableStore,
    start: dict[str, Any],
    api_key: str,
) -> dict[str, Any]:
    callback: OnlineModelCallback | None = None
    session = None
    try:
        adapter = panel.adapter(registration["task_group"])
        callback = OnlineModelCallback(
            config,
            session_id=registration["session_id"],
            evidence_directory=store.root / "transport",
            api_key=api_key,
        )
        session = PublicQARuntime(
            adapter, callback, store.root / "runtime", max_actions=12, max_submissions=32
        ).run()
    except Exception as error:
        # Do not persist arbitrary exception messages, which might contain credentials.
        store.json(
            "worker_error.json",
            record(
                "worker_error",
                registration_id=registration["id"],
                exception_type=type(error).__name__,
                complete_runtime_session=session is not None,
            ),
        )
    finally:
        if callback is not None:
            try:
                callback.finalize()
            except Exception as error:
                store.json(
                    "finalization_error.json",
                    record(
                        "finalization_error",
                        registration_id=registration["id"],
                        exception_type=type(error).__name__,
                    ),
                )
    qualification = qualify_session(
        panel.adapter(registration["task_group"]),
        registration,
        session,
        store.root / "runtime",
        store.root / "transport",
        start_record=start,
    )
    store.json("qualification.json", qualification)
    seal_directory(store, kind="online_session_manifest", registration_id=registration["id"])
    return qualification


def _credential(path: Path) -> str:
    """Read one literal key, never source a shell file or interpolate its contents."""
    values = []
    for raw in path.read_text(encoding="utf-8").split("\n"):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        key, separator, value = line.partition("=")
        if separator and key.strip() == "DEEPSEEK_API_KEY":
            value = value.strip()
            if value.startswith(("'", '"')):
                require(len(value) >= 2 and value[-1] == value[0], "run.credential_unavailable")
            if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
                value = value[1:-1]
            values.append(value)
    require(
        len(values) == 1
        and 0 < len(values[0]) <= 2048
        and all(32 < ord(char) != 127 for char in values[0]),
        "run.credential_unavailable",
    )
    return values[0]


def run(root: Path, preparation_directory: Path) -> dict[str, Any]:
    """Start each registration at most once; no resume, retry, fallback, or replacement."""

    root, preparation_directory = root.resolve(), preparation_directory.resolve()
    prepared = _prepared(root, preparation_directory)
    directory = Path(prepared["report"]["execution_directory"])
    require(not directory.exists(), "run.population_already_started")
    api_key = _credential(root / ".env")
    store = DurableStore(directory)
    registrations = prepared["registrations"]
    store.json("registrations.json", registrations)
    store.json(
        "run_binding.json",
        record(
            "run_binding",
            preparation_id=prepared["report"]["id"],
            preparation_manifest_id=prepared["manifest"]["id"],
            condition_id=prepared["condition"]["id"],
            implementation_id=prepared["implementation"]["id"],
            registered_sessions=12,
            retries=0,
            replacements=0,
            fallback_callbacks=0,
        ),
    )
    halt_reason = None
    launch_events = []
    for round_number in range(1, 5):
        current = [item for item in registrations if item["round"] == round_number]
        futures = []
        with ThreadPoolExecutor(max_workers=3, thread_name_prefix="qa-vnext") as executor:
            for registration in current:
                child = DurableStore(directory / "sessions" / registration["label"])
                child.json("registration.json", registration)
                start = _session_start(
                    registration,
                    started=halt_reason is None,
                    reason=halt_reason or "scheduled_in_frozen_round",
                )
                child.json("start.json", start)
                launch = record(
                    "launch_event",
                    ordinal=registration["ordinal"],
                    round=round_number,
                    registration_id=registration["id"],
                    start_id=start["id"],
                    status=start["status"],
                )
                store.json(f"schedule/{registration['ordinal']:02d}.json", launch)
                launch_events.append(launch)
                if halt_reason is not None:
                    qualification = qualify_session(
                        prepared["panel"].adapter(registration["task_group"]),
                        registration,
                        None,
                        child.root / "runtime",
                        child.root / "transport",
                        start_record=start,
                    )
                    child.json("qualification.json", qualification)
                    seal_directory(
                        child, kind="online_session_manifest", registration_id=registration["id"]
                    )
                    continue
                print(f"START {registration['label']} round={round_number}", flush=True)
                futures.append(
                    (
                        registration,
                        executor.submit(
                            _run_session,
                            prepared["panel"],
                            prepared["config"],
                            registration,
                            child,
                            start,
                            api_key,
                        ),
                    )
                )
            for registration, future in futures:
                try:
                    result = future.result()
                    print(
                        f"END {registration['label']} status={result['status']} "
                        f"attempts={result['provider_attempt_count']} "
                        f"submissions={result['runtime_submission_count']}",
                        flush=True,
                    )
                    if result["status"] == "unknown" or result["reason"] in {
                        "transport.unclassified_failure",
                        "callback.untyped_failure",
                        "transport.credential_unavailable",
                    }:
                        halt_reason = "prior_round_integrity_or_internal_execution_failure"
                except Exception as error:
                    halt_reason = "prior_round_worker_or_evidence_failure"
                    store.json(
                        f"worker_failures/{registration['label']}.json",
                        record(
                            "orchestration_failure",
                            registration_id=registration["id"],
                            exception_type=type(error).__name__,
                        ),
                    )
    store.json(
        "schedule.json",
        record(
            "schedule",
            events=launch_events,
            halt_reason=halt_reason,
            registered_denominator=12,
            session_replacements=0,
        ),
    )
    verify_source_snapshot(root, prepared["implementation"])
    report = analyze(root, preparation_directory, directory, directory / "analysis")
    store.json("report.json", report)
    seal_directory(
        store,
        kind="execution_manifest",
        report_id=report["id"],
        condition_id=prepared["condition"]["id"],
    )
    return report


def _share_support(session: dict[str, Any] | None, qualification: dict[str, Any]) -> Any:
    if session is None or qualification["qualified"] is not True:
        return None
    claims = {item["id"]: item for item in session["claims"]}
    producers = {
        item["observation"]["id"]: item["observation"]["selected_action"]
        for item in session["events"]
        if item.get("observation") is not None
    }
    final_claim = claims[session["final"]["answer"]["answer_claim_id"]]
    scale = producers[final_claim["observation_id"]]
    require(scale["operation"] == "scale_percent", "measurement.share_final_scale")
    ratio_ref = next(item for item in scale["inputs"] if item["role"] == "ratio")
    ratio_claim = claims[ratio_ref["ref_id"]]
    ratio = producers[ratio_claim["observation_id"]]
    denominator = next(item for item in ratio["inputs"] if item["role"] == "denominator")
    if denominator["kind"] == "claim":
        total = claims[denominator["ref_id"]]
        sum_option = producers[total["observation_id"]]
        require(sum_option["operation"] == "relation_sum", "measurement.share_total_producer")
        route = "reconstructed_total"
    else:
        require(denominator["kind"] == "evidence", "measurement.share_denominator")
        route = "disclosed_total"
    return record(
        "share_support_witness",
        session_id=session["id"],
        route=route,
        final_claim_id=final_claim["id"],
        ratio_claim_id=ratio_claim["id"],
        denominator=denominator,
        final_dependency_chain_inspected=True,
        calling_relation_sum_alone_is_not_a_route_witness=True,
    )


def summarize(
    qualifications: list[dict[str, Any]],
    coverage: list[dict[str, Any]],
) -> dict[str, Any]:
    require(len(qualifications) == 12, "summary.registered_denominator")
    task_rows: list[dict[str, Any]] = []
    for group, task_type in TASK_GROUPS.items():
        values = [item for item in qualifications if item["task_group"] == group]
        require(len(values) == 4, "summary.task_denominator")
        counts = Counter(item["status"] for item in values)
        decidable = all(type(item["end_to_end_success"]) is bool for item in values)
        successes = sum(item["end_to_end_success"] is True for item in values)
        task_rows.append(
            {
                "task_group": group,
                "task_type": task_type,
                "registered_denominator": 4,
                **{
                    name: counts[name]
                    for name in ("success", "known_failure", "unknown", "not_started")
                },
                "success_numerator": successes,
                "complete_success_proportion": successes / 4 if decidable else None,
                "complete_decidable_population": decidable,
            }
        )
    complete = all(item["complete_decidable_population"] for item in task_rows)
    measured_coverage = []
    for source in coverage:
        values = [item for item in qualifications if item["task_type"] == source["task_type"]]
        measured_coverage.append(
            record(
                "measured_coverage",
                source_coverage_id=source["id"],
                **{
                    key: value
                    for key, value in source.items()
                    if key not in {"id", "schema_version"}
                },
                executed_sessions=sum(item["execution_started"] is True for item in values),
                complete_success_sessions=sum(
                    item["end_to_end_success"] is True for item in values
                ),
                success_witness=any(item["end_to_end_success"] is True for item in values),
            )
        )
    return record(
        "measurement_summary",
        task_rows=task_rows,
        coverage_rows=measured_coverage,
        registered_session_denominator=12,
        fixed_task_denominator=3,
        equal_task_weight_mean=sum(item["success_numerator"] for item in task_rows) / 12
        if complete
        else None,
        complete_decidable_population=complete,
        selected_tasks_with_success_witness=sum(
            item["success_numerator"] > 0 for item in task_rows
        ),
        entire_finance_model_coverage_claimed=False,
        causal_depth_effect_claimed=False,
        model_critical_reasoning_depth_claimed=False,
    )


def _transport_metrics(directory: Path, qualification: dict[str, Any]) -> dict[str, Any]:
    """Summarize already qualified raw ledgers; unavailable usage never becomes zero."""
    rows = []
    if qualification["transport_ledger_id"] is not None and qualification["evidence_complete"]:
        ledger = read_json((directory / "ledger.json").read_bytes())
        require(ledger["id"] == qualification["transport_ledger_id"], "metrics.qualified_ledger")
        for item in ledger["attempts"]:
            outcome = read_json((directory / item["paths"]["outcome"]).read_bytes())
            request = read_json((directory / item["paths"]["http_request"]).read_bytes())
            rows.append(
                {
                    "outcome_id": outcome["id"],
                    "attempt_index": outcome["attempt_index"],
                    "body_byte_count": request["body_byte_count"],
                    "input_admission_proxy": request["input_admission_upper_bound"],
                    "usage": outcome["usage"],
                    "finish_reason": outcome["finish_reason"],
                    "condition_flags": outcome["condition_flags"],
                }
            )
    return record(
        "observed_transport_metrics",
        qualification_id=qualification["id"],
        rows=rows,
        verified_attempt_rows=len(rows),
        usage_is_observed_not_allowance=True,
        unavailable_usage_is_unknown_not_zero=True,
    )


def analyze(
    root: Path,
    preparation_directory: Path,
    execution_directory: Path,
    output_directory: Path,
) -> dict[str, Any]:
    """Read persisted evidence only. Does not call callbacks or execute task Operations."""
    root = root.resolve()
    prepared = _prepared(root, preparation_directory.resolve())
    execution_directory = execution_directory.resolve()
    require(
        execution_directory == Path(prepared["report"]["execution_directory"]),
        "analysis.registered_execution_directory",
    )
    require(
        read_json((execution_directory / "registrations.json").read_bytes())
        == prepared["registrations"],
        "analysis.registration_inventory",
    )
    if (execution_directory / "manifest.json").exists():
        verify_directory(execution_directory, kind="execution_manifest")
        require(
            not output_directory.resolve().is_relative_to(execution_directory),
            "analysis.immutable_execution",
        )
    store = DurableStore(output_directory.resolve())
    qualifications, candidates, session_rows, usage_rows = [], [], [], []
    for registration in prepared["registrations"]:
        directory = execution_directory / "sessions" / registration["label"]
        start_path, session_path = directory / "start.json", directory / "runtime/session.json"
        start = read_json(start_path.read_bytes()) if start_path.exists() else None
        session = read_json(session_path.read_bytes()) if session_path.exists() else None
        adapter = prepared["panel"].adapter(registration["task_group"])
        qualification = qualify_session(
            adapter,
            registration,
            session,
            directory / "runtime",
            directory / "transport",
            start_record=start,
        )
        # Re-analysis must exactly reproduce the qualification saved before aggregation.
        if (directory / "qualification.json").exists():
            require(
                qualification == read_json((directory / "qualification.json").read_bytes()),
                "analysis.qualification_not_reproducible",
            )
        qualifications.append(qualification)
        store.json(f"qualifications/{registration['label']}.json", qualification)
        exported = export_candidates(session, qualification, directory / "transport")
        store.json(f"exports/{registration['label']}.json", exported)
        candidates.extend(exported["rows"])
        transport_metrics = _transport_metrics(directory / "transport", qualification)
        store.json(f"transport_metrics/{registration['label']}.json", transport_metrics)
        usage_rows.extend(transport_metrics["rows"])
        failures = (
            Counter(
                event["receipt"].get("error_code") or "unspecified"
                for event in session["events"]
                if not event["receipt"]["admitted"]
            )
            if session
            else Counter()
        )
        session_rows.append(
            {
                "label": registration["label"],
                "registration_id": registration["id"],
                "qualification_id": qualification["id"],
                "status": qualification["status"],
                "termination_reason": qualification["reason"],
                "qa_valid": qualification["qa_valid"],
                "qualified": qualification["qualified"],
                "provider_attempts": qualification["provider_attempt_count"],
                "submissions": qualification["runtime_submission_count"],
                "depth_metrics": qualification["depth_metrics"],
                "depth_scope": qualification["depth_scope"],
                "projection_status": qualification["projection_status"],
                "unadmitted_submission_reasons": dict(sorted(failures.items())),
                "unadmitted_events": [
                    {
                        "turn_index": event["sequence"],
                        "public_runtime_state_id": event["request"]["state"]["id"],
                        "submission_kind": event["parsed"]["kind"] if event["parsed"] else None,
                        "error_code": event["receipt"]["error_code"],
                        "phase": event["request"]["state"]["phase"],
                        "pending_obligation": (
                            event["request"]["state"]["pending_observation"] or {}
                        ).get("obligation_id"),
                    }
                    for event in session["events"]
                    if not event["receipt"]["admitted"]
                ]
                if session
                else [],
                "exported_candidates": exported["candidate_count"],
                "share_support": _share_support(session, qualification)
                if registration["task_group"] == "S"
                else None,
            }
        )
    summary = summarize(qualifications, prepared["coverage"])
    store.json("measurement.json", summary)
    store.json("session_outcomes.json", record("session_outcomes", rows=session_rows))
    pairs = []
    for group in TASK_GROUPS:
        eligible = [
            item
            for item in qualifications
            if item["task_group"] == group and item["qualified"] is True
        ]
        for left, right in combinations(eligible, 2):
            comparison = compare_qualified_sessions(left, right)
            pairs.append(
                record(
                    "finite_pair",
                    task_group=group,
                    left_qualification_id=left["id"],
                    right_qualification_id=right["id"],
                    comparison=comparison,
                )
            )
    require(len(pairs) <= 18, "analysis.same_task_pair_budget")
    store.json(
        "finite_comparisons.json",
        record(
            "finite_comparisons",
            pairs=pairs,
            maximum_pairs=18,
            quotient_assignments=[],
            full_distribution_materialized=False,
            class_weights_assigned=False,
        ),
    )
    raw_dataset = record(
        "supervision_dataset",
        rows=candidates,
        candidate_count=len(candidates),
        quotient_assignments=[],
        class_weights_assigned=False,
    )
    store.json("supervision_candidates.json", raw_dataset)
    tokens = tokenize_candidates(candidates, prepared["tokenizer_binding"])
    store.json("token_representations.json", tokens)
    known_counts = [item["provider_attempt_count"] for item in qualifications]
    total_attempts = sum(known_counts) if all(type(n) is int for n in known_counts) else None
    require(total_attempts is None or total_attempts <= 384, "analysis.total_attempt_budget")
    actual_usage = {}
    for key in (
        "prompt_tokens",
        "completion_tokens",
        "total_tokens",
        "prompt_cache_hit_tokens",
        "prompt_cache_miss_tokens",
        "reasoning_tokens",
    ):
        observed = [item["usage"][key] for item in usage_rows]
        complete_usage = len(usage_rows) == total_attempts and all(type(n) is int for n in observed)
        actual_usage[key] = {
            "total": sum(observed) if complete_usage else None,
            "observed_subtotal": sum(n for n in observed if type(n) is int),
            "missing_count_in_verified_attempts": sum(n is None for n in observed),
            "all_registered_attempts_observed": complete_usage,
        }
    all_evidence = all(item["evidence_complete"] for item in qualifications)
    scientific = {
        "selected_task_model_execution_witness_count": summary[
            "selected_tasks_with_success_witness"
        ],
        "positive_raw_supervision_export_witness": bool(candidates),
        "positive_token_representation_validated": tokens["positive_representation_validated"],
        "at_least_one_consumable_token_candidate": tokens["fit_count"] > 0,
        "all_positive_candidates_fit": bool(candidates) and tokens["not_fit_count"] == 0,
        "student_training_effect_claimed": False,
    }
    report = record(
        "pilot_report",
        stage=STAGE,
        condition_id=prepared["condition"]["id"],
        implementation_id=prepared["implementation"]["id"],
        preparation_id=prepared["report"]["id"],
        qualification_ids=[item["id"] for item in qualifications],
        measurement=summary,
        session_rows=session_rows,
        provider_attempt_count=total_attempts,
        reserved_token_allowance=total_attempts * 107520 if total_attempts is not None else None,
        maximum_reserved_token_allowance=41_287_680,
        actual_response_models=sorted(
            {model for item in qualifications for model in item["actual_response_models"]}
        ),
        actual_usage=actual_usage,
        maximum_observed_http_body_bytes=max(
            (item["body_byte_count"] for item in usage_rows), default=None
        ),
        maximum_observed_input_admission_proxy=max(
            (item["input_admission_proxy"] for item in usage_rows), default=None
        ),
        condition_flag_counts=dict(
            Counter(flag for item in usage_rows for flag in item["condition_flags"])
        ),
        token_sequence_length_min=min(
            (item["sequence_length"] for item in tokens["records"]), default=None
        ),
        token_sequence_length_max=max(
            (item["sequence_length"] for item in tokens["records"]), default=None
        ),
        candidate_count=len(candidates),
        token_fit_count=tokens["fit_count"],
        token_not_fit_count=tokens["not_fit_count"],
        token_dataset_id=tokens["id"],
        finite_comparison_count=len(pairs),
        finite_comparison_status_counts=dict(
            Counter(item["comparison"]["relation"] for item in pairs)
        ),
        scientific_objects=scientific,
        observed_generation_condition_counts=dict(
            Counter(
                "valid"
                if item["condition_valid"] is True
                else "invalid"
                if item["condition_valid"] is False
                else "unknown_or_not_started"
                for item in qualifications
            )
        ),
        gate_scope=(
            "workflow freezing, binding and evidence accounting; "
            "not all-model-success or all-generation-conformance"
        ),
        gates={
            "G0_condition_and_binding": all_evidence,
            "G1_evidence_accounting": all_evidence,
            "G2_independent_qualification_and_measurement": all_evidence,
            "G3_original_export_and_representation_accounting": True,
        },
        workflow_evidence_complete=all_evidence,
        full_twelve_session_execution_complete=summary["complete_decidable_population"],
        provider_calls_by_analysis=0,
        task_operation_executions_by_analysis=0,
        student_parameter_loads=0,
        student_forward_calls=0,
        student_updates=0,
        gpu_jobs=0,
        no_hidden_reasoning_quality_claim=True,
        old_mainline="remains_paused",
    )
    store.json("report.json", report)
    seal_directory(store, kind="analysis_manifest", report_id=report["id"])
    return report
