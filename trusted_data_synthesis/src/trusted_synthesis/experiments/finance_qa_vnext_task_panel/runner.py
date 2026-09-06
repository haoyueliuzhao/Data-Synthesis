"""Sixteen fresh sessions, immutable two-round waves, and layered read-only measurement."""

from __future__ import annotations

from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from trusted_synthesis.domains.finance.qa_vnext.runtime import DurableStore

from ..finance_qa_vnext_action_branch.measurement import request_presentation
from ..finance_qa_vnext_model_execution import runner as online_runner
from ..finance_qa_vnext_model_execution.models import read_json, record, require
from ..finance_qa_vnext_model_execution.plan import (
    seal_directory,
    verify_directory,
    verify_source_snapshot,
)
from ..finance_qa_vnext_model_execution.qualification import qualify_session
from ..finance_qa_vnext_model_execution.representation import export_candidates
from .guards import execution_guard, guard_report
from .measurement import finite_comparisons, summarize
from .plan import STAGE, TASK_GROUPS
from .progress import progress
from .representation import analyze_representation
from .stage import history_inventory, prepared


def _qualification_without_worker(preparation, registration, child, start):
    session_path = child.root / "runtime/session.json"
    session = read_json(session_path.read_bytes()) if session_path.exists() else None
    result = qualify_session(
        preparation["panel"].adapter(registration["task_group"]),
        registration,
        session,
        child.root / "runtime",
        child.root / "transport",
        start_record=start,
    )
    if not (child.root / "qualification.json").exists():
        child.json("qualification.json", result)
    if not (child.root / "manifest.json").exists():
        seal_directory(child, kind="online_session_manifest", registration_id=registration["id"])
    return result


def _must_halt(result: dict[str, Any]) -> bool:
    return result["status"] == "unknown" or result["reason"] in {
        "transport.unclassified_failure",
        "callback.untyped_failure",
        "transport.credential_unavailable",
    }


def run(root: Path, preparation_directory: Path) -> dict[str, Any]:
    """No retries/resume/replacements: future waves halt only on integrity/internal faults."""
    root, preparation_directory = root.resolve(), preparation_directory.resolve()
    with execution_guard(online=True) as counts:
        preparation = prepared(root, preparation_directory)
        directory = Path(preparation["report"]["execution_directory"])
        require(not directory.exists(), "task_panel.population_already_started")
        api_key = online_runner._credential(root / "trusted_data_synthesis/.env")
        store = DurableStore(directory)
        registrations = preparation["registrations"]
        store.json("registrations.json", registrations)
        store.json(
            "run_binding.json",
            record(
                "task_panel_run_binding",
                preparation_id=preparation["report"]["id"],
                preparation_manifest_id=preparation["manifest"]["id"],
                condition_id=preparation["condition"]["id"],
                implementation_id=preparation["implementation"]["id"],
                registered_sessions=16,
                maximum_provider_attempts=512,
                maximum_reserved_token_allowance=55_050_240,
                retries=0,
                replacements=0,
                fallback_callbacks=0,
            ),
        )
        halt_reason, launches = None, []
        groups = tuple(TASK_GROUPS)
        for round_number in (1, 2):
            for wave_index in range(4):
                wave_groups = groups[2 * wave_index : 2 * wave_index + 2]
                current = [
                    r
                    for r in registrations
                    if r["round"] == round_number and r["task_group"] in wave_groups
                ]
                require(len(current) == 2, "task_panel.fixed_wave_population")
                futures = []
                with ThreadPoolExecutor(
                    max_workers=2, thread_name_prefix="qa-fixed-panel"
                ) as executor:
                    for registration in current:
                        child = DurableStore(directory / "sessions" / registration["label"])
                        child.json("registration.json", registration)
                        start = online_runner._session_start(
                            registration,
                            started=halt_reason is None,
                            reason=halt_reason or "scheduled_in_frozen_round_and_wave",
                        )
                        child.json("start.json", start)
                        launch = record(
                            "task_panel_launch_event",
                            ordinal=registration["ordinal"],
                            round=round_number,
                            wave=wave_index + 1,
                            registration_id=registration["id"],
                            start_id=start["id"],
                            status=start["status"],
                        )
                        store.json(f"schedule/{registration['ordinal']:02d}.json", launch)
                        launches.append(launch)
                        if halt_reason is not None:
                            _qualification_without_worker(preparation, registration, child, start)
                            print(
                                f"NOT_STARTED {registration['label']} reason={halt_reason}",
                                flush=True,
                            )
                            continue
                        print(
                            f"START {registration['label']} round={round_number} "
                            f"wave={wave_index + 1}",
                            flush=True,
                        )
                        future = executor.submit(
                            online_runner._run_session,
                            preparation["panel"],
                            preparation["config"],
                            registration,
                            child,
                            start,
                            api_key,
                        )
                        futures.append((registration, child, start, future))
                    # Pair order is fixed; completion speed never changes the next wave's order.
                    for registration, child, start, future in futures:
                        try:
                            result = future.result()
                        except Exception as error:
                            halt_reason = "prior_wave_worker_or_evidence_failure"
                            store.json(
                                f"worker_failures/{registration['label']}.json",
                                record(
                                    "task_panel_orchestration_failure",
                                    registration_id=registration["id"],
                                    exception_type=type(error).__name__,
                                ),
                            )
                            result = _qualification_without_worker(
                                preparation, registration, child, start
                            )
                        print(
                            f"END {registration['label']} status={result['status']} "
                            f"attempts={result['provider_attempt_count']} "
                            f"submissions={result['runtime_submission_count']}",
                            flush=True,
                        )
                        if _must_halt(result):
                            halt_reason = "prior_wave_integrity_or_internal_execution_failure"
        store.json(
            "schedule.json",
            record(
                "task_panel_schedule",
                events=launches,
                halt_reason=halt_reason,
                registered_denominator=16,
                rounds=2,
                waves_per_round=4,
                maximum_parallel_sessions=2,
                fixed_task_order=list(groups),
                session_replacements=0,
                outcome_adaptive_reordering=False,
            ),
        )
        verify_source_snapshot(root, preparation["implementation"])
        require(
            history_inventory(root) == preparation["history_inventory"],
            "task_panel.history_changed_during_run",
        )
    store.json("execution_guards.json", guard_report(counts, phase="online_collection"))
    report = analyze(root, preparation_directory, directory, directory / "analysis")
    store.json("report.json", report)
    seal_directory(
        store,
        kind="execution_manifest",
        report_id=report["id"],
        condition_id=preparation["condition"]["id"],
    )
    return report


def analyze(
    root: Path, preparation_directory: Path, execution_directory: Path, output_directory: Path
) -> dict[str, Any]:
    """Qualify/read exact persisted new evidence, without Provider or operation execution."""
    root = root.resolve()
    preparation_directory, execution_directory = (
        preparation_directory.resolve(),
        execution_directory.resolve(),
    )
    with execution_guard(online=False) as counts:
        preparation = prepared(root, preparation_directory)
        require(
            execution_directory == Path(preparation["report"]["execution_directory"]),
            "task_panel.analysis_execution_binding",
        )
        require(
            read_json((execution_directory / "registrations.json").read_bytes())
            == preparation["registrations"],
            "task_panel.analysis_registration_inventory",
        )
        if (execution_directory / "manifest.json").exists():
            verify_directory(execution_directory, kind="execution_manifest")
            require(
                not output_directory.resolve().is_relative_to(execution_directory),
                "task_panel.immutable_execution",
            )
        store = DurableStore(output_directory.resolve())
        qualifications, candidates, session_rows, entries, usage_rows = [], [], [], [], []
        for registration in preparation["registrations"]:
            directory = execution_directory / "sessions" / registration["label"]
            start_path, session_path = directory / "start.json", directory / "runtime/session.json"
            start = read_json(start_path.read_bytes()) if start_path.exists() else None
            session = read_json(session_path.read_bytes()) if session_path.exists() else None
            qualification = qualify_session(
                preparation["panel"].adapter(registration["task_group"]),
                registration,
                session,
                directory / "runtime",
                directory / "transport",
                start_record=start,
            )
            if (directory / "qualification.json").exists():
                require(
                    qualification == read_json((directory / "qualification.json").read_bytes()),
                    "task_panel.qualification_not_reproducible",
                )
            qualifications.append(qualification)
            store.json(f"qualifications/{registration['label']}.json", qualification)
            exported = export_candidates(session, qualification, directory / "transport")
            candidates.extend(exported["rows"])
            store.json(f"exports/{registration['label']}.json", exported)
            entries.append(
                {
                    "label": registration["label"],
                    "registration": registration,
                    "qualification": qualification,
                    "session": session,
                    "export": exported,
                }
            )
            metrics = online_runner._transport_metrics(directory / "transport", qualification)
            store.json(f"transport_metrics/{registration['label']}.json", metrics)
            usage_rows.extend(metrics["rows"])
            progression = progress(session, qualification)
            presentation = request_presentation(
                directory / "transport",
                read_json(
                    (
                        preparation_directory / f"initial/{registration['label']}_request.json"
                    ).read_bytes()
                ),
                qualification,
            )
            store.json(f"progress/{registration['label']}.json", progression)
            store.json(f"request_presentation/{registration['label']}.json", presentation)
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
                    "task_group": registration["task_group"],
                    "task_type": registration["task_type"],
                    "task_id": registration["task_id"],
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
                    "progress": progression,
                    "request_presentation": presentation,
                    "unadmitted_submission_reasons": dict(sorted(failures.items())),
                    "exported_candidates": exported["candidate_count"],
                    "share_support": online_runner._share_support(session, qualification)
                    if registration["task_group"] == "S"
                    else None,
                }
            )
        raw = record(
            "supervision_dataset",
            rows=candidates,
            candidate_count=len(candidates),
            generation_condition_id=preparation["condition"]["id"],
            registered_session_ids=[r["session_id"] for r in preparation["registrations"]],
            quotient_assignments=[],
            class_weights_assigned=False,
        )
        store.json("supervision_candidates.json", raw)
        represented = analyze_representation(
            candidates,
            entries,
            preparation["tokenizer_binding"],
            preparation["representation_policy"],
            preparation["condition"]["id"],
        )
        for name, value in {
            "representation_binding": represented["binding"],
            "token_representations": represented["tokens"],
            "session_packages": represented["packages"],
            "cpu_loading": represented["cpu_loading"],
        }.items():
            store.json(name + ".json", value)
        for name, binary in represented["binary_artifacts"].items():
            store.write(name, binary)
        pairs = finite_comparisons(qualifications)
        store.json(
            "finite_comparisons.json",
            record(
                "task_panel_finite_comparisons",
                pairs=pairs,
                maximum_pairs=8,
                unsupported_qualified_not_compared=True,
                quotient_assignments=[],
                class_weights_assigned=False,
                all_possible_classes_enumerated=False,
            ),
        )
        measurement = summarize(
            qualifications,
            preparation["registrations"],
            preparation["coverage"],
            represented["packages"],
            represented["tokens"],
            pairs,
        )
        store.json("measurement.json", measurement)
        store.json(
            "session_outcomes.json", record("task_panel_session_outcomes", rows=session_rows)
        )
        counts_known = [item["provider_attempt_count"] for item in qualifications]
        total_attempts = sum(counts_known) if all(type(n) is int for n in counts_known) else None
        require(total_attempts is None or total_attempts <= 512, "task_panel.total_attempt_budget")
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
            complete_usage = len(usage_rows) == total_attempts and all(
                type(n) is int for n in observed
            )
            actual_usage[key] = {
                "total": sum(observed) if complete_usage else None,
                "observed_subtotal": sum(n for n in observed if type(n) is int),
                "missing_count_in_verified_attempts": sum(n is None for n in observed),
                "all_registered_attempts_observed": complete_usage,
            }
        require(
            history_inventory(root) == preparation["history_inventory"],
            "task_panel.analysis_history_changed",
        )
        verify_source_snapshot(root, preparation["implementation"])
        tokens = represented["tokens"]
        fields = dict(
            stage=STAGE,
            condition_id=preparation["condition"]["id"],
            implementation_id=preparation["implementation"]["id"],
            preparation_id=preparation["report"]["id"],
            representation_policy_id=preparation["representation_policy"]["id"],
            representation_data_binding_id=represented["binding"]["id"],
            measurement=measurement,
            session_rows=session_rows,
            qualification_ids=[q["id"] for q in qualifications],
            provider_attempt_count=total_attempts,
            observed_verified_attempt_count=len(usage_rows),
            maximum_provider_attempts=512,
            reserved_token_allowance=total_attempts * 107520
            if total_attempts is not None
            else None,
            maximum_reserved_token_allowance=55_050_240,
            actual_response_models=sorted(
                {model for q in qualifications for model in q["actual_response_models"]}
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
            candidate_count=len(candidates),
            token_dataset_id=tokens["id"],
            token_fit_count=tokens["fit_count"],
            token_not_fit_count=tokens["not_fit_count"],
            maximum_token_sequence_length=32_768,
            token_sequence_length_min=min(
                (item["sequence_length"] for item in tokens["records"]), default=None
            ),
            token_sequence_length_max=max(
                (item["sequence_length"] for item in tokens["records"]), default=None
            ),
            complete_session_packages=represented["packages"]["complete_session_packages"],
            cpu_loading_id=represented["cpu_loading"]["id"],
            finite_comparison_count=len(pairs),
            finite_comparison_status_counts=dict(
                Counter(item["comparison"]["relation"] for item in pairs)
            ),
            workflow_accounting_complete=len(qualifications)
            == len(represented["packages"]["rows"])
            == 16,
            all_registered_evidence_complete=all(q["evidence_complete"] for q in qualifications),
            all_registered_outcomes_decidable=measurement["complete_decidable_population"],
            all_eight_tasks_have_complete_success_witness=measurement[
                "all_selected_tasks_have_success_witness"
            ],
            full_support_training_support_available=measurement[
                "full_support_training_support_available"
            ],
            full_support_training_materialized=False,
            scientific_success_is_not_workflow_gate=True,
            provider_calls_by_analysis=0,
            task_operation_executions_by_analysis=0,
            historical_files_unchanged=True,
            historical_inventory_id=preparation["history_inventory"]["id"],
            historical_file_count=preparation["history_inventory"]["file_count"],
            historical_byte_count=preparation["history_inventory"]["byte_count"],
            all_predecessor_sources_byte_identical=True,
            student_parameter_loads=0,
            student_forward_calls=0,
            student_updates=0,
            gpu_jobs=0,
            class_weights_assigned=False,
            Contribution_estimated=False,
            blind_evaluation_claimed=False,
            old_results_pooled=False,
            old_mainline="remains_paused",
        )
    guards = guard_report(counts, phase="read_only_analysis")
    store.json("execution_guards.json", guards)
    report = record("task_panel_report", **fields, execution_guard_report_id=guards["id"])
    store.json("report.json", report)
    seal_directory(store, kind="analysis_manifest", report_id=report["id"])
    return report
