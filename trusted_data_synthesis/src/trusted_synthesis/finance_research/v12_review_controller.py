"""One new whole V12 A/B matrix, with exact unsent recovery and no later stages.

No old valid review is reused. Only actual SETTLED responses or authorized
missing-connection terminals complete jobs. Projection failures never remove a
joint process candidate. This controller does not map, encode or train.
"""

from __future__ import annotations

import argparse
import asyncio
import fcntl
import hashlib
import json
import os
import signal
import threading
from collections import Counter, deque
from pathlib import Path

from .calibration import now, status
from .contracts import ProviderCallError, digest, invocation_identity
from .probe_budget import BudgetUnavailable, _request_record_digest
from .probe_collection import ENV_FILE
from .storage import read_json
from .v6_collection import bound, persist, require
from .v6_review_revision import _key
from .v11_process_review import resolve_candidate_pair

PAIR_COUNT = 5719
SIDE_COUNT = 11438
NETWORK_WAVE_LIMIT = 3


def _provider():
    from . import v12_review_provider

    return v12_review_provider


def _budget():
    from . import v12_budget

    return v12_budget


def _protocol():
    from . import v12_review_protocol

    return v12_review_protocol


def canonical(value):
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode()


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def checked(path):
    value = read_json(path)
    require(
        value.get("id") == digest({k: v for k, v in value.items() if k != "id"}),
        "immutable V12 record changed",
    )
    return value


def entry(path):
    path = Path(path).resolve()
    value = checked(path)
    return dict(path=str(path), id=value["id"], sha256=sha(path.read_bytes()))


def read_entry(ref):
    path = Path(ref["path"])
    require(sha(path.read_bytes()) == ref["sha256"], "V12 reference bytes changed")
    value = checked(path)
    require(value["id"] == ref["id"], "V12 reference content changed")
    return value


def job_directory(output, job):
    prefix, suffix = job["episode_id"].split(":", 1)
    require(
        prefix == "v12review"
        and len(suffix) == 64
        and all(c in "0123456789abcdef" for c in suffix),
        "only a new registered V12 episode may be used",
    )
    return Path(output) / "reviews" / suffix


def iid_for(ledger, job):
    return invocation_identity(
        dict(run_id=ledger.run_id, episode_id=job["episode_id"], attempt_index=1), turn_index=0
    )["invocation_id"]


class SavedStop(RuntimeError):
    def __init__(self, phase, reason):
        super().__init__(reason)
        self.phase = phase


def _network_candidate(row):
    """Candidate only: the budget helper also proves the exact unknown event/scope."""
    if row is None or row.get("state") != "UNKNOWN":
        return False
    evidence = json.loads(row.get("evidence_json") or "{}")
    return (
        all(
            row.get(k) is None
            for k in ("response_body", "http_status", "usage_json", "settled_microcny")
        )
        and evidence.get("service_response_received") is False
        and evidence.get("exception_type") in _budget().NETWORK_EXCEPTIONS
    )


class Context:
    def __init__(self, output, plan=None):
        from .v12_review_registration import checked_plan

        self.output = Path(output).resolve()
        self.plan = checked_plan(self.output) if plan is None else plan
        self.jobs = self.plan["jobs"]
        require(
            len(self.jobs) == SIDE_COUNT
            and len({j["episode_id"] for j in self.jobs}) == SIDE_COUNT,
            "fixed new 11438-job matrix required, never an old-success/failed-only subset",
        )
        self.pairs = []
        for a, b in zip(self.jobs[::2], self.jobs[1::2], strict=True):
            require(
                a["role"] == "A"
                and b["role"] == "B"
                and a["slot_id"] == b["slot_id"]
                and a["task_id"] == b["task_id"],
                "original paired A/B order changed",
            )
            self.pairs.append((a, b))
        require(
            len(self.pairs) == len({a["slot_id"] for a, _ in self.pairs}) == PAIR_COUNT,
            "fixed 5719 original candidate packages required",
        )
        self._lock = threading.Lock()
        self._progress = dict(
            phase="SOURCE_READ",
            processed=0,
            denominator=SIDE_COUNT,
            active=0,
            actual_returns=0,
            network_unknowns=0,
        )

    def request(self, job):
        path = self.output / "requests" / job["episode_id"].split(":", 1)[1] / "record.json"
        request = checked(path)
        _protocol().checked_request(request)
        body = _protocol().request_body(request)
        require(
            request["id"] == job["request_id"]
            and request["episode_id"] == job["episode_id"]
            and request["role"] == job["role"]
            and request["slot_id"] == job["slot_id"]
            and request["task_id"] == job["task_id"]
            and request["max_output_tokens"] == job["max_output_tokens"]
            and body["model"] == "deepseek-flash"
            and digest(body) == job["request_sha256"]
            and sha(canonical(body)) == job["request_body_sha256"],
            "pre-generated original request/body/cap differs; never regenerate after outcomes",
        )
        return request

    def update(self, **values):
        with self._lock:
            self._progress.update(values)

    def report(self, ledger):
        with self._lock:
            body = dict(self._progress)
        status(
            self.output,
            dict(
                **body,
                at=now(),
                schema="v12_review_controller_status.v1",
                protocol_id=self.plan["protocol_identity"],
                registration_id=self.plan["id"],
                budget=ledger.snapshot(),
                old_reviews_reused=False,
                mapping_started=False,
                training_started=False,
                no_automatic_retry=True,
            ),
        )


def explicit_proxy(plan):
    transport = plan["transport"]
    require(transport["mode"] == "explicit_proxy", "use only the registered V12 proxy route")
    value = os.environ.get(transport["source_env"])
    require(
        isinstance(value, str) and sha(value.encode()) == transport["proxy_url_sha256"],
        "registered proxy absent/changed; no direct or environment fallback",
    )
    return value


def ramp_limit(plan, successful_settlements):
    steps = plan["concurrency"]["ramp"]
    eligible = [s["workers"] for s in steps if successful_settlements >= s["settled_at_least"]]
    require(eligible, "registered settlement-based concurrency ramp absent")
    return min(plan["concurrency"]["max"], max(eligible))


def _terminal(ctx, job, record, kind):
    directory = job_directory(ctx.output, job)
    require(
        kind in {"paid_model_return", "acknowledged_connection_unknown"},
        "not a real terminal class",
    )
    result = bound(
        dict(
            schema="v12_review_terminal.v1",
            protocol_id=ctx.plan["protocol_identity"],
            registration_id=ctx.plan["id"],
            episode_id=job["episode_id"],
            role=job["role"],
            slot_id=job["slot_id"],
            task_id=job["task_id"],
            physical_attempt_index=1,
            terminal_kind=kind,
            record=entry(directory / "record/record.json"),
            actual_model_response_returned=kind == "paid_model_return",
            no_resend=True,
        )
    )
    require(result["record"]["id"] == record["id"], "terminal record identity differs")
    persist(directory / "terminal", result)
    return result


def _paid_record(ctx, job, request, artifact, row):
    record = _provider().paid_record(request, artifact, row)
    require(
        record["schema"] == "v12_paid_process_review.v1"
        and record["actual_model_call_receipt_verified"] is True
        and record["role"] == job["role"]
        and record["slot_id"] == job["slot_id"]
        and record["request"] == request
        and record["artifact"] == artifact
        and record["inspection"]["actual_model_call_receipt_verified"] is False
        and record["inspection"]["training_admissibility"]["production_admitted"] is False,
        "actual outer receipt must not falsify the V11 inner offline flags",
    )
    persist(job_directory(ctx.output, job) / "record", record)
    return _terminal(ctx, job, record, "paid_model_return")


def _unknown_record(ctx, job, request, row, acknowledgment):
    require(
        row["state"] == "UNKNOWN"
        and row["invocation_id"] == acknowledgment["invocation_id"]
        and row["request_sha256"]
        == job["request_sha256"]
        == acknowledgment["expected_request_sha256"]
        and acknowledgment["original_unknown_record_sha256"] == _request_record_digest(row)
        and all(
            row[k] is None
            for k in ("response_body", "http_status", "usage_json", "settled_microcny")
        ),
        "missing response must bind the actual acknowledged unchanged UNKNOWN",
    )
    record = bound(
        dict(
            schema="v12_network_unknown_review.v1",
            protocol_id=ctx.plan["protocol_identity"],
            registration_id=ctx.plan["id"],
            episode_id=job["episode_id"],
            role=job["role"],
            slot_id=job["slot_id"],
            task_id=job["task_id"],
            request_id=request["id"],
            invocation_id=row["invocation_id"],
            request_sha256=row["request_sha256"],
            original_ledger_record_sha256=_request_record_digest(row),
            acknowledgment_id=acknowledgment["id"],
            permanent_reserved_microcny=row["reserved_microcny"],
            actual_model_call_receipt_verified=False,
            original_model_response=None,
            usage=None,
            inspection=None,
            failure_codes=["TRANSPORT_UNKNOWN"],
            no_resend=True,
            not_a_semantic_verdict=True,
        )
    )
    persist(job_directory(ctx.output, job) / "record", record)
    return _terminal(ctx, job, record, "acknowledged_connection_unknown")


def recover_stage(ctx, ledger, jobs):
    """Cold recovery once, then only this wave's unfinished rows; no HTTP here."""
    rows = {j["episode_id"]: ledger.request_record(iid_for(ledger, j)) for j in jobs}
    expected = {}
    for job in jobs:
        row = rows[job["episode_id"]]
        if row is None:
            require(
                not (job_directory(ctx.output, job) / "terminal/record.json").exists(),
                "saved terminal lost its actual wallet row",
            )
        elif row["state"] == "UNKNOWN":
            if not _network_candidate(row):
                raise SavedStop(
                    "SERVICE_OR_USAGE_SAVED",
                    "non-network UNKNOWN cannot be acknowledged as connection loss",
                )
            request = ctx.request(job)
            require(
                digest(_protocol().request_body(request)) == row["request_sha256"],
                "unknown original request changed",
            )
            expected[row["invocation_id"]] = row["request_sha256"]
        elif row["state"] not in {"SETTLED", "RESERVED"} or (
            row["state"] == "RESERVED" and row["dispatched_at"] is not None
        ):
            raise SavedStop(
                "UNRESOLVED_DISPATCH_SAVED", "already dispatched unresolved call must not be resent"
            )
    acknowledgments = {}
    if expected:
        if ledger.snapshot()["pending_requests"]:
            raise SavedStop(
                "PENDING_RECONCILIATION_SAVED", "drain before acknowledging exact network unknowns"
            )
        receipt = _budget().acknowledge_connection_unknowns(
            ledger, protocol_id=ctx.plan["protocol_identity"], expected_requests=expected
        )
        persist(ctx.output / "network_acknowledgments" / receipt["id"], receipt)
        acknowledgments = {r["invocation_id"]: r for r in receipt["records"]}
    require(not ledger.snapshot()["halt"], "unrelated financial/service safety halt remains")
    completed = {}
    for index, job in enumerate(jobs):
        ctx.update(recovery_scanned=index + 1, recovery_denominator=len(jobs))
        row = rows[job["episode_id"]]
        if row is None or row["state"] == "RESERVED":
            continue
        request = ctx.request(job)
        directory = job_directory(ctx.output, job)
        if row["state"] == "UNKNOWN":
            terminal = _unknown_record(
                ctx, job, request, row, acknowledgments[row["invocation_id"]]
            )
        else:
            artifact_path = directory / "artifact/record.json"
            if artifact_path.exists():
                artifact = checked(artifact_path)
            else:
                artifact = _provider().restore_settled(row, request)
                persist(artifact_path.parent, artifact)
            terminal = _paid_record(ctx, job, request, artifact, row)
        completed[job["episode_id"]] = terminal
    return completed


def _progress(ctx, completed, **extra):
    ctx.update(
        processed=len(completed),
        denominator=len(ctx.jobs),
        actual_returns=sum(t["terminal_kind"] == "paid_model_return" for t in completed.values()),
        network_unknowns=sum(
            t["terminal_kind"] == "acknowledged_connection_unknown" for t in completed.values()
        ),
        **extra,
    )


async def execute_reviews(ctx, ledger, *, api_key, stop_requested=None):
    stop = stop_requested or asyncio.Event()
    ctx.update(phase="SOURCE_READ")
    completed = await asyncio.to_thread(recover_stage, ctx, ledger, ctx.jobs)
    pending = deque(j for j in ctx.jobs if j["episode_id"] not in completed)
    success = sum(t["terminal_kind"] == "paid_model_return" for t in completed.values())
    throttle = ctx.plan["concurrency"]["max"]
    _progress(ctx, completed, phase="RECOVERY_COMPLETE", active=0)

    async def worker(job, client, wave_stop):
        if stop.is_set() or wave_stop.is_set():
            return dict(kind="not_started", job=job)
        directory = job_directory(ctx.output, job)
        try:
            request = ctx.request(job)
            row = ledger.request_record(iid_for(ledger, job))
            require(
                row is None or row["state"] == "RESERVED" and row["dispatched_at"] is None,
                "only new or proved-unsent original requests can be sent",
            )
            if not (directory / "started/record.json").exists():
                persist(
                    directory / "started",
                    bound(
                        dict(
                            at=now(),
                            job=job,
                            registration_id=ctx.plan["id"],
                            request_id=request["id"],
                            attempt_index=1,
                            automatic_retries=0,
                        )
                    ),
                )
            artifact = await _provider().request_once(
                ledger=ledger,
                api_key=api_key,
                request=request,
                client=client,
                timeout=1200.0,
                resume_reserved=row is not None,
            )
            persist(directory / "artifact", artifact)
            terminal = _paid_record(
                ctx, job, request, artifact, ledger.request_record(iid_for(ledger, job))
            )
            return dict(kind="returned", job=job, terminal=terminal)
        except BudgetUnavailable as exc:
            row = ledger.request_record(iid_for(ledger, job))
            snapshot = ledger.snapshot()
            if row is None and not snapshot["halt"]:
                return dict(kind="budget_wait", job=job, error=str(exc))
            wave_stop.set()
            return dict(kind="safety_error", job=job, error=str(exc), error_type=type(exc).__name__)
        except Exception as exc:
            wave_stop.set()
            row = ledger.request_record(iid_for(ledger, job))
            network = isinstance(exc, ProviderCallError) and _network_candidate(row)
            ctx.update(phase="DRAINING", stop_reason="network" if network else "service_or_local")
            issue = bound(
                dict(
                    at=now(),
                    job=job,
                    error_type=type(exc).__name__,
                    error=str(exc),
                    network_only=network,
                    retry=False,
                )
            )
            persist(directory / "controller_errors" / issue["id"], issue)
            return dict(
                kind="network" if network else "safety_error",
                job=job,
                error=str(exc),
                error_type=type(exc).__name__,
            )

    async with _provider().annotation_client(
        timeout=1200, proxy=explicit_proxy(ctx.plan)
    ) as client:
        while pending:
            if stop.is_set():
                _progress(ctx, completed, phase="USER_STOPPED_SAVED", active=0)
                return None
            limit = min(ramp_limit(ctx.plan, success), throttle)
            wave = [pending.popleft() for _ in range(min(limit, len(pending)))]
            wave_stop = asyncio.Event()
            _progress(
                ctx,
                completed,
                phase="REVIEW_RUNNING",
                active=len(wave),
                registered_concurrency_ceiling=ramp_limit(ctx.plan, success),
                current_wave_limit=limit,
                successful_transport_settlements=success,
            )
            # A wave never sends additional jobs after its first transport/service error.
            # All jobs already in flight are awaited before any safety or budget decision.
            results = await asyncio.gather(*(worker(job, client, wave_stop) for job in wave))
            returned = [r for r in results if r["kind"] == "returned"]
            networks = [r for r in results if r["kind"] == "network"]
            errors = [r for r in results if r["kind"] == "safety_error"]
            deferred = [r["job"] for r in results if r["kind"] in {"not_started", "budget_wait"}]
            completed.update({r["job"]["episode_id"]: r["terminal"] for r in returned})
            success += len(returned)  # Semantics/format/length never alter this ramp counter.
            pending.extendleft(reversed(deferred))
            _progress(
                ctx, completed, phase="DRAINING_SAVED", active=0, last_wave_errors=errors + networks
            )
            if errors:
                _progress(ctx, completed, phase="SERVICE_OR_LOCAL_SAVED")
                return None
            if networks:
                ctx.update(phase="RECOVERING_NETWORK_TERMINALS")
                recovered = await asyncio.to_thread(
                    recover_stage, ctx, ledger, [r["job"] for r in networks]
                )
                completed.update(recovered)
                if len(networks) >= NETWORK_WAVE_LIMIT:
                    _progress(ctx, completed, phase="NETWORK_SAFETY_SAVED", active=0)
                    return None
            if stop.is_set():
                _progress(ctx, completed, phase="USER_STOPPED_SAVED", active=0)
                return None
            budget_blocked = any(r["kind"] == "budget_wait" for r in results)
            if budget_blocked:
                throttle = max(1, limit // 2)
                snapshot = ledger.snapshot()
                if not returned and not networks and not snapshot["pending_requests"]:
                    _progress(
                        ctx,
                        completed,
                        phase="BUDGET_SAVED",
                        active=0,
                        reason="drained wallet cannot admit even one original unsent job",
                    )
                    return None
                if not returned and snapshot["pending_requests"]:
                    before = (snapshot["pending_requests"], snapshot["exposure_microcny"])
                    _progress(ctx, completed, phase="WAITING_FOR_RESERVATION_SETTLEMENT", active=0)
                    while not stop.is_set():
                        try:
                            await asyncio.wait_for(stop.wait(), timeout=1)
                        except TimeoutError:
                            pass
                        current = ledger.snapshot()
                        if current["halt"]:
                            raise SavedStop(
                                "FINANCIAL_SAFETY_SAVED", "safety halt while waiting for funds"
                            )
                        if (current["pending_requests"], current["exposure_microcny"]) != before:
                            break
            elif returned:
                throttle = min(ctx.plan["concurrency"]["max"], max(limit, throttle) * 2)
        require(len(completed) == len(ctx.jobs), "complete new matrix cannot omit deferred jobs")
        _progress(ctx, completed, phase="REVIEW_TERMINALS_COMPLETE", active=0)
        return completed


def freeze_review_seal(ctx, terminals):
    """Complete inventory and candidate support only; never start downstream work."""
    require(set(terminals) == {j["episode_id"] for j in ctx.jobs}, "no partial matrix sealing")
    pair_refs, candidates, projection_blocked = [], [], []
    stage_counts = {r: Counter() for r in ("A", "B")}
    process_counts = {r: Counter() for r in ("A", "B")}
    return_count = unknown_count = original_hold = 0
    raw_reason_chars = positive_reason_chars = 0
    projection_counts_known = True
    for index, (a_job, b_job) in enumerate(ctx.pairs):
        sides = []
        for job in (a_job, b_job):
            terminal = terminals[job["episode_id"]]
            require(
                terminal == checked(job_directory(ctx.output, job) / "terminal/record.json")
                and terminal["episode_id"] == job["episode_id"]
                and terminal["registration_id"] == ctx.plan["id"]
                and terminal["physical_attempt_index"] == 1,
                "seal must retain every same-registration first attempt",
            )
            record = read_entry(terminal["record"])
            sides.append(record)
            if terminal["terminal_kind"] == "paid_model_return":
                require(
                    record["schema"] == "v12_paid_process_review.v1"
                    and record["actual_model_call_receipt_verified"] is True,
                    "returned side lacks its real outer receipt",
                )
                return_count += 1
                outcomes = record["new_pipeline_outcomes"]
                process_counts[job["role"]][outcomes["process_validity"]] += 1
                stage_counts[job["role"]].update(outcomes["failure_codes"])
            else:
                require(
                    terminal["terminal_kind"] == "acknowledged_connection_unknown"
                    and record["schema"] == "v12_network_unknown_review.v1"
                    and record["inspection"] is None,
                    "a missing response is not a fabricated V11 inspection",
                )
                unknown_count += 1
                original_hold += record["permanent_reserved_microcny"]
                stage_counts[job["role"]]["TRANSPORT_UNKNOWN"] += 1
                process_counts[job["role"]]["no_model_return"] += 1
        a, b = sides
        returned_pair = all(r["actual_model_call_receipt_verified"] is True for r in sides)
        inner_pair = (
            resolve_candidate_pair(a["inspection"], b["inspection"], q_native=True)
            if returned_pair
            else None
        )
        joint = (
            bool(
                inner_pair["joint_process_candidate"]
                and all(
                    r["new_pipeline_outcomes"]["process_candidate_usable"] is True for r in sides
                )
            )
            if inner_pair
            else None
        )
        a_returned = a["actual_model_call_receipt_verified"] is True
        projection = a["new_pipeline_outcomes"]["projection_usable"] if a_returned else None
        offline_reason = a["inspection"]["reason_projection"] if a_returned else None
        effective_reason = (
            dict(offline_reason)
            if projection is True
            else {
                **offline_reason,
                "positive_public_characters": None,
                "all_public_reasoning_masked": None,
            }
            if offline_reason is not None
            else None
        )
        core = bound(
            dict(
                schema="v12_paired_process_core.v1",
                protocol_id=ctx.plan["protocol_identity"],
                registration_id=ctx.plan["id"],
                slot_id=a_job["slot_id"],
                task_id=a_job["task_id"],
                Q_native_as_registered=True,
                A_terminal=entry(job_directory(ctx.output, a_job) / "terminal/record.json"),
                B_terminal=entry(job_directory(ctx.output, b_job) / "terminal/record.json"),
                both_actual_responses_returned=returned_pair,
                offline_candidate_pair_id=inner_pair["id"] if inner_pair else None,
                offline_joint_process_candidate=inner_pair["joint_process_candidate"]
                if inner_pair
                else None,
                offline_candidate_gate=inner_pair["candidate_gate"] if inner_pair else None,
                joint_process_candidate=joint,
                A_projection_usable=projection,
                offline_A_reason_projection=offline_reason,
                A_reason_projection=effective_reason,
                projection_does_not_filter_process_candidates=True,
                production_admitted=False,
                mapping_started=False,
                training_started=False,
            )
        )
        pair_path = ctx.output / "pairs" / a_job["slot_id"].split(":", 1)[-1] / "record.json"
        persist(pair_path.parent, core)
        pair_refs.append(entry(pair_path))
        if joint:
            candidates.append(a_job["slot_id"])
            if projection is not True:
                projection_blocked.append(a_job["slot_id"])
            reason = effective_reason
            raw_reason_chars += reason["raw_public_characters"]
            known = projection is True and reason["positive_public_characters"] is not None
            projection_counts_known = projection_counts_known and known
            if known:
                positive_reason_chars += reason["positive_public_characters"]
        ctx.update(phase="SEALING", paired_cores=index + 1, paired_core_denominator=len(ctx.pairs))
    require(
        return_count + unknown_count == len(ctx.jobs) == SIDE_COUNT
        and len(pair_refs) == PAIR_COUNT,
        "complete new logical matrix required",
    )
    all_reason_zero = (
        bool(candidates) and raw_reason_chars > 0 and positive_reason_chars == 0
        if projection_counts_known
        else None
    )
    seal = bound(
        dict(
            schema="v12_complete_rereview_seal.v1",
            protocol_id=ctx.plan["protocol_identity"],
            registration_id=ctx.plan["id"],
            source_root=ctx.plan["source_root"],
            source_protocol_id=ctx.plan["source_protocol_id"],
            source_batch_id=ctx.plan["source_batch_id"],
            expected_reviews=SIDE_COUNT,
            expected_pairs=PAIR_COUNT,
            terminals=[
                entry(job_directory(ctx.output, j) / "terminal/record.json") for j in ctx.jobs
            ],
            paired_cores=pair_refs,
            all_registered_jobs_have_authentic_terminals=True,
            all_model_responses_returned=unknown_count == 0,
            actual_returns=return_count,
            network_unknowns=unknown_count,
            physical_attempts=SIDE_COUNT,
            retained_unknown_reserved_microcny=original_hold,
            joint_process_candidate_slot_ids=candidates,
            joint_process_candidate_count=len(candidates),
            projection_blocked_candidate_slot_ids=projection_blocked,
            no_joint_process_candidate_dropped=True,
            no_reason0_package_dropped=True,
            candidate_raw_public_characters=raw_reason_chars,
            candidate_positive_public_characters=positive_reason_chars
            if projection_counts_known
            else None,
            all_candidate_public_reasoning_masked=all_reason_zero,
            projection_inventory_complete=bool(candidates)
            and not projection_blocked
            and all_reason_zero is False,
            process_outcome_counts=process_counts,
            layered_failure_counts=stage_counts,
            old_review_results_reused=False,
            old_records_overwritten=False,
            original_V11_offline_flags_unchanged=True,
            mapping_started=False,
            training_started=False,
            production_admitted=False,
            awaiting_complete_support_audit_before_downstream=True,
        )
    )
    persist(ctx.output / "review_seal", seal)
    return seal


async def run_reviews(output):
    from .v12_review_registration import ledger_for

    ctx = Context(output)
    ledger = ledger_for(ctx.plan)
    stop, monitor_done = asyncio.Event(), asyncio.Event()
    loop = asyncio.get_running_loop()
    with (ctx.output / "controller.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, stop.set)

        async def monitor():
            while not monitor_done.is_set():
                await asyncio.to_thread(ctx.report, ledger)
                try:
                    await asyncio.wait_for(monitor_done.wait(), 5)
                except TimeoutError:
                    pass

        watcher = asyncio.create_task(monitor())
        try:
            completed = await execute_reviews(
                ctx, ledger, api_key=_key(ENV_FILE), stop_requested=stop
            )
            if completed is None:
                return None
            ctx.update(phase="SEALING", active=0)
            seal = await asyncio.to_thread(freeze_review_seal, ctx, completed)
            ctx.update(phase="REREVIEW_COMPLETE", seal_id=seal["id"], active=0)
            return seal
        except SavedStop as exc:
            ctx.update(phase=exc.phase, error=str(exc), active=0)
            return None
        except Exception as exc:
            ctx.update(
                phase="LOCAL_OR_FINANCIAL_SAVED",
                error_type=type(exc).__name__,
                error=str(exc),
                active=0,
            )
            raise
        finally:
            monitor_done.set()
            await watcher
            await asyncio.to_thread(ctx.report, ledger)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    result = asyncio.run(run_reviews(args.output))
    print(json.dumps(dict(complete=result is not None, seal_id=result["id"] if result else None)))


if __name__ == "__main__":
    main()
