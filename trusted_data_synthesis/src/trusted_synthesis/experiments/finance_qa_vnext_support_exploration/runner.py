"""Four nonadaptive N/E waves, one qualification per new session, then finite measurement."""

from __future__ import annotations

from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from trusted_synthesis.domains.finance.qa_vnext.runtime import DurableStore

from ..finance_qa_vnext_model_execution import runner as online_runner
from ..finance_qa_vnext_model_execution.models import identity, read_json, record, require
from ..finance_qa_vnext_model_execution.plan import (
    seal_directory,
    verify_directory,
    verify_source_snapshot,
)
from ..finance_qa_vnext_model_execution.qualification import qualify_session
from ..finance_qa_vnext_model_execution.representation import export_candidates
from ..finance_qa_vnext_task_panel.progress import progress
from ..finance_qa_vnext_task_panel.runner import _must_halt
from .guards import execution_guard, guard_report
from .plan import LABELS, STAGE
from .source import history_inventory
from .stage import _target, prepared


def _qualify_unfinished(preparation, registration, child, start):
    path = child.root / "qualification.json"
    if path.exists():
        return read_json(path.read_bytes())
    session_path = child.root / "runtime/session.json"
    session = read_json(session_path.read_bytes()) if session_path.exists() else None
    result = qualify_session(
        preparation["panel"].adapter("S"),
        registration,
        session,
        child.root / "runtime",
        child.root / "transport",
        start_record=start,
    )
    child.json("qualification.json", result)
    seal_directory(child, kind="online_session_manifest", registration_id=registration["id"])
    return result


def run(root: Path, output: Path):
    root, output = _target(root, output)
    # Complete all frozen input checks while Provider and Finance execution are still forbidden.
    with execution_guard(phase="preparation_readback"):
        preparation = prepared(root, output)
    directory = output / "execution"
    require(
        not directory.exists(), "support_exploration.population_already_started_no_online_resume"
    )
    registrations = preparation["registrations"]
    require(
        [r["label"] for r in registrations] == list(LABELS),
        "support_exploration.exact_eight_registrations",
    )
    with execution_guard(phase="online") as counts:
        api_key = online_runner._credential(root / "trusted_data_synthesis/.env")
        store = DurableStore(directory)
        store.json("registrations.json", registrations)
        store.json(
            "run_binding.json",
            record(
                "support_exploration_run_binding",
                condition_id=preparation["condition"]["id"],
                preparation_id=preparation["report"]["id"],
                preparation_manifest_id=preparation["manifest"]["id"],
                comparison_contract_id=preparation["comparison_contract"]["id"],
                registered_sessions=8,
                maximum_provider_attempts=256,
                maximum_reserved_token_allowance=27_525_120,
                session_replacements=0,
                automatic_retries=0,
                maximum_parallel_sessions=2,
                route_target_adaptive_sampling=False,
            ),
        )
        halt_reason, launches, results = None, [], []
        for wave in range(1, 5):
            current = [r for r in registrations if r["wave"] == wave]
            require([r["profile"] for r in current] == ["N", "E"], "support_exploration.fixed_wave")
            futures = []
            with ThreadPoolExecutor(
                max_workers=2, thread_name_prefix="share-support-explore"
            ) as executor:
                for registration in current:
                    child = DurableStore(directory / "sessions" / registration["label"])
                    child.json("registration.json", registration)
                    start = online_runner._session_start(
                        registration,
                        started=halt_reason is None,
                        reason=halt_reason or "frozen_stratified_wave",
                    )
                    child.json("start.json", start)
                    launch = record(
                        "support_exploration_launch",
                        label=registration["label"],
                        registration_id=registration["id"],
                        profile=registration["profile"],
                        wave=wave,
                        ordinal=registration["ordinal"],
                        start_id=start["id"],
                        status=start["status"],
                    )
                    launches.append(launch)
                    store.json(f"schedule/{registration['ordinal']:02d}.json", launch)
                    if halt_reason is not None:
                        result = _qualify_unfinished(preparation, registration, child, start)
                        results.append(result)
                        print(
                            f"NOT_STARTED {registration['label']} reason={halt_reason}", flush=True
                        )
                        continue
                    print(
                        f"START {registration['label']} profile={registration['profile']} "
                        f"wave={wave}",
                        flush=True,
                    )
                    future = executor.submit(
                        online_runner._run_session,
                        preparation["panel"],
                        preparation["configurations"][registration["profile"]],
                        registration,
                        child,
                        start,
                        api_key,
                    )
                    futures.append((registration, child, start, future))
                for registration, child, start, future in futures:
                    try:
                        result = future.result()
                    except Exception as error:
                        halt_reason = "prior_wave_worker_or_evidence_failure"
                        store.json(
                            f"worker_failures/{registration['label']}.json",
                            record(
                                "support_exploration_worker_failure",
                                registration_id=registration["id"],
                                exception_type=type(error).__name__,
                            ),
                        )
                        result = _qualify_unfinished(preparation, registration, child, start)
                    results.append(result)
                    print(
                        f"END {registration['label']} status={result['status']} "
                        f"attempts={result['provider_attempt_count']} "
                        f"submissions={result['runtime_submission_count']}",
                        flush=True,
                    )
                    if _must_halt(result):
                        halt_reason = "prior_wave_integrity_or_internal_failure"
            require(len(results) == wave * 2, "support_exploration.wave_denominator")
        store.json(
            "schedule.json",
            record(
                "support_exploration_schedule",
                events=launches,
                halt_reason=halt_reason,
                registered_denominator=8,
                waves=4,
                maximum_parallel_sessions=2,
                replacements=0,
                outcome_adaptive_changes=False,
            ),
        )
        store.json("qualifications.json", results)
        verify_source_snapshot(root, preparation["implementation"])
        require(
            history_inventory(root) == preparation["history_inventory"],
            "support_exploration.history_changed_during_run",
        )
        online_guards = guard_report(counts, phase="online")
        store.json("execution_guards.json", online_guards)
    # Credentials are no longer passed to any function after collection.
    api_key = None
    report = analyze_new(root, preparation, directory)
    store.json("report.json", report)
    seal_directory(
        store,
        kind="support_exploration_execution_manifest",
        condition_id=preparation["condition"]["id"],
        report_id=report["id"],
    )
    return report


def analyze_new(root, preparation, directory):
    """Reuse each new worker qualification once; do not re-audit old or new trajectories."""
    from .measurement import summarize
    from .quotient import analyze_quotient
    from .representation import analyze_representation

    with execution_guard(phase="measurement_and_representation") as counts:
        condition = preparation["condition"]
        entries, candidates, metrics_rows, progression, session_rows = [], [], [], [], []
        registrations = preparation["registrations"]
        require(
            read_json((directory / "registrations.json").read_bytes()) == registrations,
            "support_exploration.collection_registration_binding",
        )
        saved_qualifications = read_json((directory / "qualifications.json").read_bytes())
        for registration in registrations:
            child = directory / "sessions" / registration["label"]
            verify_directory(child, kind="online_session_manifest")
            qualification = read_json((child / "qualification.json").read_bytes())
            identity(qualification, "qualification")
            require(
                qualification in saved_qualifications,
                "support_exploration.saved_qualification_binding",
            )
            session_path = child / "runtime/session.json"
            session = read_json(session_path.read_bytes()) if session_path.exists() else None
            exported = export_candidates(session, qualification, child / "transport")
            entry = {
                "label": registration["label"],
                "registration": registration,
                "session": session,
                "qualification": qualification,
                "export": exported,
            }
            entries.append(entry)
            candidates.extend(exported["rows"])
            metrics = online_runner._transport_metrics(child / "transport", qualification)
            metrics_rows.extend(
                [
                    {**row, "label": registration["label"], "profile": registration["profile"]}
                    for row in metrics["rows"]
                ]
            )
            progression.append(progress(session, qualification))
            session_rows.append(
                {
                    "label": registration["label"],
                    "profile": registration["profile"],
                    "qualification_id": qualification["id"],
                    "status": qualification["status"],
                    "qualified": qualification["qualified"],
                    "qa_valid": qualification["qa_valid"],
                    "evidence_complete": qualification["evidence_complete"],
                    "attempts": qualification["provider_attempt_count"],
                    "submissions": qualification["runtime_submission_count"],
                    "depth_metrics": qualification["depth_metrics"],
                    "depth_scope": qualification["depth_scope"],
                    "reason": qualification["reason"],
                    "candidate_count": len(exported["rows"]),
                }
            )
        quotient = analyze_quotient(
            entries, condition, preparation["quotient_rule"], preparation["comparison_contract"]
        )
        measurement = summarize(registrations, entries, quotient, condition)
        represented = analyze_representation(
            candidates,
            entries,
            preparation["tokenizer_binding"],
            preparation["representation_policy"],
            condition,
        )
        output = DurableStore(directory / "analysis")
        for entry in entries:
            output.json("exports/" + entry["label"] + ".json", entry["export"])
        for name, value in (
            ("supervision_candidates", candidates),
            ("session_outcomes", session_rows),
            ("actual_progress", progression),
            ("quotient", quotient),
            ("measurement", measurement),
            ("representation_data_binding", represented["binding"]),
            ("token_representations", represented["tokens"]),
            ("session_packages", represented["packages"]),
            ("cpu_loading", represented["cpu_loading"]),
            ("exploration_representation_binding", represented["exploration_binding"]),
            ("representation_profile_checks", represented["profile_checks"]),
        ):
            output.json(name + ".json", value)
        for name, raw in represented["binary_artifacts"].items():
            output.write(name, raw)
        attempt_values = [row["attempts"] for row in session_rows]
        known_attempts = sum(value for value in attempt_values if type(value) is int)
        attempts = known_attempts if all(type(value) is int for value in attempt_values) else None
        usage = {}
        for key in (
            "prompt_tokens",
            "completion_tokens",
            "total_tokens",
            "prompt_cache_hit_tokens",
            "prompt_cache_miss_tokens",
            "reasoning_tokens",
        ):
            values = [row["usage"].get(key) for row in metrics_rows]
            complete = (
                attempts is not None
                and len(values) == attempts
                and all(type(v) is int for v in values)
            )
            subtotal = sum(v for v in values if type(v) is int)
            usage[key] = {
                "observed_total": subtotal if complete else None,
                "known_value_subtotal": subtotal,
                "complete_attempt_population_usage": complete,
                "known_rows": sum(type(v) is int for v in values),
                "unknown_rows": sum(type(v) is not int for v in values),
            }
        require(
            known_attempts <= 256
            and all(value is None or 0 <= value <= 32 for value in attempt_values),
            "support_exploration.attempt_bound",
        )
        transport = record(
            "support_exploration_transport_metrics",
            rows=metrics_rows,
            usage=usage,
            provider_attempt_count=attempts,
            verified_attempt_rows=len(metrics_rows),
            maximum_registered_attempts=256,
            known_attempt_count_lower_bound=known_attempts,
            exact_attempt_count_known=attempts is not None,
            reserved_allowance_used=attempts * 107_520 if attempts is not None else None,
            maximum_reserved_allowance=27_525_120,
            allowance_is_not_measured_usage=True,
            incomplete_attempt_metrics_preserved_as_unknown=len(metrics_rows) != attempts,
            maximum_actual_http_body_bytes=max(
                (r["body_byte_count"] for r in metrics_rows), default=None
            ),
        )
        output.json("transport_metrics.json", transport)
        require(
            history_inventory(root) == preparation["history_inventory"],
            "support_exploration.historical_bytes_changed",
        )
        verify_source_snapshot(root, preparation["implementation"])
        guards = guard_report(counts, phase="measurement_and_representation")
        report = record(
            "support_exploration_report",
            stage=STAGE,
            condition_id=condition["id"],
            source_commit=preparation["implementation"]["source_commit"],
            implementation_id=preparation["implementation"]["id"],
            preparation_manifest_id=preparation["manifest"]["id"],
            comparison_contract_id=preparation["comparison_contract"]["id"],
            rule_id=preparation["quotient_rule"]["id"],
            registrations=registrations,
            session_rows=session_rows,
            status_counts=dict(Counter(row["status"] for row in session_rows)),
            provider_attempt_count=attempts,
            transport_metrics=transport,
            quotient_id=quotient["id"],
            measurement=measurement,
            candidate_count=len(candidates),
            token_fit_count=represented["tokens"]["fit_count"],
            token_not_fit_count=represented["tokens"]["not_fit_count"],
            representation_profile_checks_id=represented["profile_checks"]["id"],
            representation_binding_id=represented["exploration_binding"]["id"],
            packages_id=represented["packages"]["id"],
            cpu_loading_id=represented["cpu_loading"]["id"],
            new_worker_qualifications_reused_without_replay=True,
            history_inventory_id=preparation["history_inventory"]["id"],
            all_historical_bytes_unchanged=True,
            execution_guards=guards,
            old_mainline="remains_paused",
            final_training_weights=None,
            limitations=[
                "eight fixed stratified development-source sessions",
                "soft-guided profile is not neutral natural preference",
                "given plan and legal candidates, not autonomous algorithm discovery",
                "finite support only; no causal prompt effect estimate",
                "no Student utility, Contribution or VTDO update",
            ],
        )
        output.json("execution_guards.json", guards)
        output.json("report.json", report)
        seal_directory(
            output,
            kind="support_exploration_analysis_manifest",
            condition_id=condition["id"],
            report_id=report["id"],
        )
        return report
