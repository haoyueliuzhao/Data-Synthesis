"""One fixed wave of six fresh sessions; saved qualifications are never recomputed."""

from __future__ import annotations

from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

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
from .preservation import history_inventory


def _qualify_unfinished(preparation, registration, child, start):
    path = child.root / "qualification.json"
    if path.exists():
        result = read_json(path.read_bytes())
        identity(result, "qualification")
        require(
            result["registration_id"] == registration["id"],
            "final_publication.unfinished_qualification_parent",
        )
    else:
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
        child.json("qualification.json", result)
    if not (child.root / "manifest.json").exists():
        seal_directory(child, kind="online_session_manifest", registration_id=registration["id"])
    return result


def run(root: Path, output: Path):
    """No online resume, retries, replacement or task/profile-adaptive scheduling."""
    from .stage import _target, prepared

    root, output = _target(root, output)
    with execution_guard(phase="preparation_readback"):
        preparation = prepared(root, output)
    directory = output / "execution"
    require(not directory.exists(), "final_publication.population_already_started_no_online_resume")
    registrations, condition = preparation["registrations"], preparation["condition"]
    require(
        [item["label"] for item in registrations] == list(LABELS)
        and condition["registered_labels"] == list(LABELS)
        and len(registrations) == 6
        and condition["maximum_parallel_sessions"] == 6
        and len(condition["waves"]) == 1
        and [label for wave in condition["waves"] for label in wave] == list(LABELS),
        "final_publication.exact_frozen_six_registration_schedule",
    )
    with execution_guard(phase="online") as counts:
        api_key = online_runner._credential(root / "trusted_data_synthesis/.env")
        store = DurableStore(directory)
        store.json("registrations.json", registrations)
        store.json(
            "run_binding.json",
            record(
                "final_publication_run_binding",
                condition_id=condition["id"],
                preparation_id=preparation["report"]["id"],
                preparation_manifest_id=preparation["manifest"]["id"],
                comparison_contract_id=preparation["comparison_contract"]["id"],
                final_public_contract_id=condition["final_public_contract_id"],
                measurement_application_id=condition["measurement_application_id"],
                source_commit=condition["source_commit"],
                registered_tasks=3,
                registered_sessions=6,
                maximum_provider_attempts=192,
                maximum_reserved_token_allowance=20_643_840,
                maximum_parallel_sessions=6,
                automatic_retries=0,
                model_fallbacks=0,
                session_replacements=0,
                route_target_adaptive_sampling=False,
            ),
        )
        halt_reason, launches, results = None, [], []
        for wave_index, frozen_labels in enumerate(condition["waves"], start=1):
            current = [item for item in registrations if item["wave"] == wave_index]
            require(
                [item["label"] for item in current] == frozen_labels and len(current) == 6,
                "final_publication.fixed_wave_members",
            )
            futures = []
            with ThreadPoolExecutor(
                max_workers=6, thread_name_prefix="final-publication-share"
            ) as executor:
                for registration in current:
                    child = DurableStore(directory / "sessions" / registration["label"])
                    child.json("registration.json", registration)
                    start = online_runner._session_start(
                        registration,
                        started=halt_reason is None,
                        reason=halt_reason or "frozen_final_publication_wave",
                    )
                    child.json("start.json", start)
                    launch = record(
                        "final_publication_launch",
                        label=registration["label"],
                        task_key=registration["task_key"],
                        registration_id=registration["id"],
                        profile=registration["profile"],
                        wave=wave_index,
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
                        f"START {registration['label']} task={registration['task_key']} "
                        f"profile={registration['profile']} wave={wave_index}",
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
                        halt_reason = "fixed_wave_worker_or_evidence_failure"
                        store.json(
                            f"worker_failures/{registration['label']}.json",
                            record(
                                "final_publication_worker_failure",
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
                        halt_reason = "fixed_wave_integrity_or_internal_failure"
            require(len(results) == wave_index * 6, "final_publication.wave_denominator")
        store.json(
            "schedule.json",
            record(
                "final_publication_schedule",
                events=launches,
                halt_reason=halt_reason,
                registered_denominator=6,
                task_denominator=3,
                waves=1,
                maximum_parallel_sessions=6,
                replacements=0,
                outcome_adaptive_changes=False,
            ),
        )
        store.json("qualifications.json", results)
        verify_source_snapshot(root, preparation["implementation"])
        require(
            history_inventory(root) == preparation["history_inventory"],
            "final_publication.history_changed_during_run",
        )
        store.json("execution_guards.json", guard_report(counts, phase="online"))
    api_key = None
    report = analyze_new(root, preparation, directory)
    store.json("report.json", report)
    seal_directory(
        store,
        kind="final_publication_execution_manifest",
        condition_id=condition["id"],
        report_id=report["id"],
    )
    return report


def _transport_report(session_rows, metric_rows):
    values = [row["attempts"] for row in session_rows]
    require(
        all(value is None or type(value) is int and 0 <= value <= 32 for value in values),
        "final_publication.session_attempt_bound",
    )
    lower = sum(value for value in values if type(value) is int)
    require(lower <= 192, "final_publication.total_attempt_bound")
    attempts = lower if all(type(value) is int for value in values) else None
    usage = {}
    for key in (
        "prompt_tokens",
        "completion_tokens",
        "total_tokens",
        "prompt_cache_hit_tokens",
        "prompt_cache_miss_tokens",
        "reasoning_tokens",
    ):
        observed = [row["usage"].get(key) for row in metric_rows]
        complete = (
            attempts is not None
            and len(observed) == attempts
            and all(type(value) is int for value in observed)
        )
        subtotal = sum(value for value in observed if type(value) is int)
        usage[key] = {
            "observed_total": subtotal if complete else None,
            "known_value_subtotal": subtotal,
            "complete_attempt_population_usage": complete,
            "known_rows": sum(type(value) is int for value in observed),
            "unknown_rows": sum(type(value) is not int for value in observed),
        }
    return record(
        "final_publication_transport_metrics",
        rows=metric_rows,
        usage=usage,
        provider_attempt_count=attempts,
        known_attempt_count_lower_bound=lower,
        exact_attempt_count_known=attempts is not None,
        verified_attempt_rows=len(metric_rows),
        maximum_registered_attempts=192,
        reserved_allowance_used=attempts * 107_520 if attempts is not None else None,
        maximum_reserved_allowance=20_643_840,
        allowance_is_not_measured_usage=True,
        incomplete_attempt_metrics_preserved_as_unknown=len(metric_rows) != attempts,
        maximum_actual_http_body_bytes=max(
            (row["body_byte_count"] for row in metric_rows), default=None
        ),
    )


def _final_progress(
    session: dict[str, Any] | None,
    qualification: dict[str, Any],
    runtime_directory: Path | None = None,
) -> dict[str, Any]:
    """Describe saved events; never judge Final again or turn a prefix into Qualified.

    Raw JSON objects with kind=final are retained even when protocol parsing
    rejected them. Malformed/non-object JSON remains explicitly unclassified;
    this helper does not infer the intended submission kind from text.
    """
    from trusted_synthesis.domains.finance.qa_vnext.final_public_contract import (
        public_final_contract,
    )

    accepted, finals, unclassified, publication_checks = [], [], [], []
    events = session.get("events", []) if session is not None else []
    for event in events:
        parsed, receipt = event.get("parsed"), event["receipt"]
        marker = {
            "sequence": event["sequence"],
            "turn_number": event["sequence"] + 1,
            "request_id": event["request"]["id"],
            "state_id": event["request"]["state"]["id"],
            "submission_id": event["submission"]["id"],
            "receipt_id": receipt["id"],
        }
        publication_checks.append(
            event["request"].get("public_final_contract") == public_final_contract()
        )
        claim = event.get("claim")
        if (
            isinstance(parsed, dict)
            and parsed.get("kind") == "update"
            and parsed.get("disposition") == "accept"
            and receipt["admitted"] is True
            and isinstance(claim, dict)
            and claim.get("status") == "accepted"
            and claim.get("obligation_id") == "percent"
            and claim.get("proposition", {}).get("operation") == "scale_percent"
        ):
            accepted.append(
                {
                    **marker,
                    "claim_id": claim["id"],
                    "observation_id": claim["observation_id"],
                    "accepted_percent_claim": claim,
                    "source": "saved admitted model Update and its accepted Claim",
                }
            )
        submitted = parsed
        detection = "saved_protocol_parsed_kind"
        if not isinstance(submitted, dict) and runtime_directory is not None:
            raw_path = runtime_directory / f"turns/{event['sequence']:03d}_response.txt"
            if raw_path.is_file():
                try:
                    submitted = read_json(raw_path.read_bytes())
                except (ValueError, TypeError):
                    submitted = None
                detection = "saved_raw_json_kind_without_protocol_reparse"
        if not isinstance(submitted, dict):
            unclassified.append(marker)
            continue
        if submitted.get("kind") != "final":
            continue
        feedback = event.get("post_state", {}).get("last_feedback")
        finals.append(
            {
                **marker,
                "admitted": receipt["admitted"],
                "error_code": receipt["error_code"],
                "kind_detection": detection,
                "protocol_parsed": isinstance(parsed, dict),
                "submitted_final": submitted,
                "feedback": feedback,
                "public_diagnostic": (
                    feedback.get("public_diagnostic") if isinstance(feedback, dict) else None
                ),
            }
        )
    first = finals[0] if finals else None
    first_kind_certain = first is not None and not any(
        row["sequence"] < first["sequence"] for row in unclassified
    )
    return record(
        "final_publication_progress",
        session_id=session.get("id") if session is not None else None,
        qualification_id=qualification["id"],
        evidence_complete=qualification.get("evidence_complete") is True,
        observation_scope="saved observed events only; not independent qualification",
        first_accepted_percent_claim=accepted[0] if accepted else None,
        accepted_percent_claim_events=accepted,
        accepted_percent_claim_present=bool(accepted),
        first_final=first,
        first_final_admitted=first["admitted"]
        if first is not None and first_kind_certain
        else None,
        first_final_kind_certain=first_kind_certain,
        first_final_scope="earliest saved JSON object declaring kind=final",
        final_submission_count=len(finals),
        final_submissions=finals,
        final_public_diagnostics=[
            {"sequence": row["sequence"], "public_diagnostic": row["public_diagnostic"]}
            for row in finals
            if row["public_diagnostic"] is not None
        ],
        unclassified_raw_submission_count=len(unclassified),
        unclassified_raw_submissions=unclassified,
        all_observed_requests_publish_final_contract=(
            all(publication_checks) if publication_checks else None
        ),
        final_qualification_status=qualification["status"],
        final_qualified=qualification.get("qualified"),
        final_qa_valid=qualification.get("qa_valid"),
        qualification_recomputed=False,
        final_verification_recomputed=False,
        subsequent_correction_is_not_first_final_success=True,
        field_diagnostics_replace_complete_success=False,
        provider_calls=0,
        financial_operation_executions=0,
    )


def analyze_new(root: Path, preparation: dict[str, Any], directory: Path):
    """Reuse saved worker qualifications and new representation; no qualification replay."""
    from .measurement import analyze
    from .projection import project_entry
    from .representation import analyze_representation

    with execution_guard(phase="measurement_and_representation") as counts:
        condition, registrations = preparation["condition"], preparation["registrations"]
        require(
            read_json((directory / "registrations.json").read_bytes()) == registrations,
            "final_publication.collection_registration_binding",
        )
        saved = read_json((directory / "qualifications.json").read_bytes())
        require(
            len(saved) == len({value["registration_id"] for value in saved}) == 6
            and {value["registration_id"] for value in saved}
            == {value["id"] for value in registrations},
            "final_publication.saved_qualification_inventory",
        )
        entries, candidates, metric_rows, progression, session_rows = [], [], [], [], []
        by_registration = {value["registration_id"]: value for value in saved}
        for registration in registrations:
            child = directory / "sessions" / registration["label"]
            verify_directory(child, kind="online_session_manifest")
            qualification = read_json((child / "qualification.json").read_bytes())
            identity(qualification, "qualification")
            require(
                qualification == by_registration[registration["id"]],
                "final_publication.saved_qualification_binding",
            )
            path = child / "runtime/session.json"
            session = read_json(path.read_bytes()) if path.exists() else None
            exported = export_candidates(session, qualification, child / "transport")
            entries.append(
                {
                    "label": registration["label"],
                    "registration": registration,
                    "session": session,
                    "qualification": qualification,
                    "export": exported,
                }
            )
            candidates.extend(exported["rows"])
            metrics = online_runner._transport_metrics(child / "transport", qualification)
            metric_rows.extend(
                [
                    {
                        **row,
                        "label": registration["label"],
                        "task_key": registration["task_key"],
                        "profile": registration["profile"],
                    }
                    for row in metrics["rows"]
                ]
            )
            final_progress = _final_progress(session, qualification, child / "runtime")
            require(
                final_progress["all_observed_requests_publish_final_contract"] is not False,
                "final_publication.missing_contract_in_saved_runtime_request",
            )
            progression.append(
                {
                    "actual_calculation": progress(session, qualification),
                    "final_publication": final_progress,
                }
            )
            session_rows.append(
                {
                    "label": registration["label"],
                    "task_key": registration["task_key"],
                    "task_id": registration["task_id"],
                    "context_id": registration["context_id"],
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
                    "accepted_percent_claim": final_progress["first_accepted_percent_claim"],
                    "first_final": final_progress["first_final"],
                    "first_final_admitted": final_progress["first_final_admitted"],
                    "final_submission_count": final_progress["final_submission_count"],
                    "final_public_diagnostics": final_progress["final_public_diagnostics"],
                    "final_progress_id": final_progress["id"],
                }
            )
        represented = analyze_representation(
            candidates,
            entries,
            preparation["tokenizer_binding"],
            preparation["representation_policy"],
            condition,
        )
        packages = {value["qualification_id"]: value for value in represented["packages"]["rows"]}
        require(
            len(packages) == len(represented["packages"]["rows"]) == 6,
            "final_publication.complete_package_inventory",
        )
        for entry in entries:
            qid = entry["qualification"]["id"]
            tokens = [
                value
                for value in represented["tokens"]["records"]
                if value["qualification_id"] == qid
            ]
            entry["package"] = packages[qid]
            entry["target_token_count"] = sum(value["target_token_count"] for value in tokens)
            entry["consumable_target_token_count"] = sum(
                value["target_token_count"]
                for value in tokens
                if value["consumable_token_representation"]
            )
        projections = [
            project_entry(
                entry, condition, preparation["quotient_rule"], preparation["comparison_contract"]
            )
            for entry in entries
        ]
        measurement = analyze(
            entries,
            projections,
            condition,
            preparation["quotient_rule"],
            preparation["comparison_contract"],
        )
        transport = _transport_report(session_rows, metric_rows)
        output = DurableStore(directory / "analysis")
        for entry in entries:
            output.json(f"exports/{entry['label']}.json", entry["export"])
        for name, value in (
            ("supervision_candidates", candidates),
            ("session_outcomes", session_rows),
            ("actual_progress", progression),
            ("projections", projections),
            ("measurement", measurement),
            ("representation_data_binding", represented["binding"]),
            ("token_representations", represented["tokens"]),
            ("session_packages", represented["packages"]),
            ("cpu_loading", represented["cpu_loading"]),
            ("final_publication_representation_binding", represented["final_publication"]),
            ("representation_profile_checks", represented["profile_checks"]),
            ("transport_metrics", transport),
        ):
            output.json(name + ".json", value)
        for name, binary in represented["binary_artifacts"].items():
            output.write(name, binary)
        require(
            history_inventory(root) == preparation["history_inventory"],
            "final_publication.historical_bytes_changed",
        )
        verify_source_snapshot(root, preparation["implementation"])
        guards = guard_report(counts, phase="measurement_and_representation")
        report = record(
            "final_publication_report",
            stage=STAGE,
            condition_id=condition["id"],
            source_commit=preparation["implementation"]["source_commit"],
            implementation_id=preparation["implementation"]["id"],
            preparation_manifest_id=preparation["manifest"]["id"],
            comparison_contract_id=preparation["comparison_contract"]["id"],
            rule_id=preparation["quotient_rule"]["id"],
            final_public_contract_id=condition["final_public_contract_id"],
            measurement_application_id=condition["measurement_application_id"],
            task_count=3,
            registered_session_count=6,
            registrations=registrations,
            session_rows=session_rows,
            final_progression=[row["final_publication"] for row in progression],
            first_final_admitted_count=sum(
                row["first_final_admitted"] is True for row in session_rows
            ),
            accepted_percent_claim_session_count=sum(
                row["accepted_percent_claim"] is not None for row in session_rows
            ),
            old_twelve_and_local_controls_in_denominator=False,
            subsequent_final_correction_is_not_first_final_success=True,
            status_counts=dict(Counter(row["status"] for row in session_rows)),
            provider_attempt_count=transport["provider_attempt_count"],
            transport_metrics=transport,
            measurement=measurement,
            candidate_count=len(candidates),
            token_fit_count=represented["tokens"]["fit_count"],
            token_not_fit_count=represented["tokens"]["not_fit_count"],
            complete_session_packages=represented["packages"]["complete_session_packages"],
            representation_profile_checks_id=represented["profile_checks"]["id"],
            representation_binding_id=represented["final_publication"]["id"],
            packages_id=represented["packages"]["id"],
            cpu_loading_id=represented["cpu_loading"]["id"],
            new_worker_qualifications_reused_without_replay=True,
            class_materialization_provenance_recorded_without_training_weights=True,
            history_inventory_id=preparation["history_inventory"]["id"],
            all_historical_bytes_unchanged=True,
            execution_guards=guards,
            old_mainline="remains_paused",
            final_training_weights=None,
            independent_evaluation_bound_and_ready=False,
            limitations=[
                "same three development tasks, one fresh sample per profile and task",
                "no concurrent old-presentation control or precise causal effect estimate",
                "six fresh sessions only; old twelve and local controls excluded",
                "mechanism observations are not general financial ability or blind evaluation",
                "profile and correction-history composition remain tied to class members",
                "finite same-task comparisons only; no cross-task quotient identity",
                "no Student utility, Contribution or VTDO update",
            ],
        )
        output.json("execution_guards.json", guards)
        output.json("report.json", report)
        seal_directory(
            output,
            kind="final_publication_analysis_manifest",
            condition_id=condition["id"],
            report_id=report["id"],
        )
        return report
