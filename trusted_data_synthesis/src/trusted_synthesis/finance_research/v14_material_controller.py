"""Fixed V14 projection completion and whole-task mapping, independently scheduled.

All fixed residual fresh calls remain in the denominator. No retries, semantic filtering,
trajectory generation, consumer encoding or training are performed by this entry.
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

MAX_CALLS = 323
PURPOSES = ("projection", "mapping")
NETWORK_WAVE_LIMIT = 3


def _provider():
    from . import v14_material_provider

    return v14_material_provider


def _budget():
    from . import v14_budget

    return v14_budget


def _protocol():
    from . import v14_material_protocol

    return v14_material_protocol


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
        "immutable V14 record changed",
    )
    return value


def entry(path):
    path = Path(path).resolve()
    value = checked(path)
    return dict(path=str(path), id=value["id"], sha256=sha(path.read_bytes()))


def read_entry(ref):
    path = Path(ref["path"])
    require(sha(path.read_bytes()) == ref["sha256"], "V14 reference bytes changed")
    value = checked(path)
    require(value["id"] == ref["id"], "V14 reference content changed")
    return value


def job_directory(output, job):
    prefix, suffix = job["episode_id"].split(":", 1)
    require(
        prefix in {"v14projection", "v14mapping"}
        and len(suffix) == 64
        and all(c in "0123456789abcdef" for c in suffix),
        "only a new registered V14 episode may be used",
    )
    return Path(output) / "annotations" / suffix


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
        from .v14_material_registration import checked_plan

        self.output = Path(output).resolve()
        self.plan = checked_plan(self.output) if plan is None else plan
        self.jobs = self.plan["jobs"]
        require(
            0 < len(self.jobs) == self.plan["expected_requests"] <= MAX_CALLS
            and len({j["episode_id"] for j in self.jobs}) == len(self.jobs),
            "fixed new fixed residual-job material matrix required",
        )
        require(
            {p: sum(j["kind"] == p for j in self.jobs) for p in PURPOSES}
            == self.plan["purpose_counts"],
            "exact projection/mapping purpose counts required",
        )
        self._lock = threading.Lock()
        self._progress = dict(
            phase="SOURCE_READ",
            processed=0,
            denominator=len(self.jobs),
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
            and request.get("slot_id") == job["slot_id"]
            and request["purpose"] == job["kind"]
            and [view["slot_id"] for view in request["views"]] == job["slot_ids"]
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
                schema="v14_material_controller_status.v1",
                protocol_id=self.plan["protocol_identity"],
                registration_id=self.plan["id"],
                budget=ledger.snapshot(),
                old_V12_process_judgments_unchanged=True,
                projection_and_mapping_independent=True,
                training_started=False,
                no_automatic_retry=True,
            ),
        )


def explicit_proxy(plan):
    transport = plan["transport"]
    require(transport["mode"] == "explicit_proxy", "use only the registered V14 proxy route")
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
            schema="v14_material_terminal.v1",
            protocol_id=ctx.plan["protocol_identity"],
            registration_id=ctx.plan["id"],
            episode_id=job["episode_id"],
            role=job["role"],
            purpose=job["kind"],
            slot_id=job["slot_id"],
            slot_ids=job["slot_ids"],
            task_id=job["task_id"],
            request_id=job["request_id"],
            request=job["request"],
            authority_reason=job["authority_reason"],
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
        record["schema"] == "v14_paid_material_annotation.v1"
        and record["actual_model_call_receipt_verified"] is True
        and record["role"] == job["role"]
        and record["slot_id"] == job["slot_id"]
        and record["request"] == request
        and record["artifact"] == artifact
        and record["inspection"]["actual_model_call_receipt_verified"] is False
        and record["inspection"]["production_admitted"] is False,
        "actual outer receipt must not falsify the inner offline flags",
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
            schema="v14_network_unknown_material.v1",
            protocol_id=ctx.plan["protocol_identity"],
            registration_id=ctx.plan["id"],
            episode_id=job["episode_id"],
            role=job["role"],
            purpose=job["kind"],
            slot_id=job["slot_id"],
            slot_ids=job["slot_ids"],
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


async def execute_material(ctx, ledger, *, api_key, stop_requested=None):
    stop = stop_requested or asyncio.Event()
    ctx.update(phase="SOURCE_READ")
    completed = await asyncio.to_thread(recover_stage, ctx, ledger, ctx.jobs)
    # Registration fixes alternating purposes before any new model outcomes.
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
                ctx,
                completed,
                phase="DRAINING_SAVED",
                active=0,
                last_wave_errors=errors + networks,
                successful_transport_settlements=success,
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


def freeze_completion_seal(ctx, terminals):
    require(
        set(terminals) == {job["episode_id"] for job in ctx.jobs}
        and len(ctx.jobs) == ctx.plan["expected_requests"] <= MAX_CALLS,
        "all fixed residual registered calls need authentic terminal records; no partial seal",
    )
    returns, unknowns = Counter(), Counter()
    usable, failures, references = Counter(), {purpose: Counter() for purpose in PURPOSES}, []
    for job in ctx.jobs:
        path = job_directory(ctx.output, job) / "terminal/record.json"
        terminal = checked(path)
        require(
            terminal == terminals[job["episode_id"]]
            and terminal["registration_id"] == ctx.plan["id"]
            and terminal["episode_id"] == job["episode_id"]
            and terminal["physical_attempt_index"] == 1,
            "terminal source/scope differs",
        )
        record = read_entry(terminal["record"])
        purpose = job["kind"]
        if terminal["terminal_kind"] == "paid_model_return":
            require(
                record["schema"] == "v14_paid_material_annotation.v1"
                and record["actual_model_call_receipt_verified"] is True,
                "paid model return lacks actual receipt",
            )
            returns[purpose] += 1
            inspection = record["inspection"]
            approved = (
                inspection.get("usable") is True
                if purpose == "projection"
                else (
                    inspection.get("mapping_status") == "complete"
                    and inspection.get("mapping_admitted") is True
                )
            )
            usable[purpose] += int(approved)
            if not approved:
                failures[purpose]["annotation_unusable"] += 1
        else:
            require(
                terminal["terminal_kind"] == "acknowledged_connection_unknown"
                and record["schema"] == "v14_network_unknown_material.v1"
                and record["inspection"] is None
                and not record["actual_model_call_receipt_verified"],
                "missing response must not be fabricated as model judgment",
            )
            unknowns[purpose] += 1
            failures[purpose]["transport_unknown"] += 1
        references.append(entry(path))
    require(
        {p: returns[p] + unknowns[p] for p in PURPOSES} == ctx.plan["purpose_counts"],
        "fixed per-purpose terminal denominator differs",
    )
    seal = bound(
        dict(
            schema="v14_material_completion_seal.v1",
            protocol_id=ctx.plan["protocol_identity"],
            registration_id=ctx.plan["id"],
            source_review_seal_id=ctx.plan["source_review_seal_id"],
            expected_calls=ctx.plan["expected_requests"],
            purpose_expected=ctx.plan["purpose_counts"],
            representation_review=ctx.plan["representation_review"],
            actual_returns=sum(returns.values()),
            network_unknowns=sum(unknowns.values()),
            actual_returns_by_purpose=dict(returns),
            network_unknowns_by_purpose=dict(unknowns),
            projection_usable_calls=usable["projection"],
            mapping_complete_calls=usable["mapping"],
            failures={p: dict(counts) for p, counts in failures.items()},
            all_registered_jobs_have_authentic_terminals=True,
            all_model_responses_returned=not sum(unknowns.values()),
            terminals=references,
            fixed_common_candidate_packages=2468,
            fixed_common_tasks=744,
            deterministic_singleton_tasks_reused=99,
            source_process_judgments_unchanged=True,
            no_candidate_dropped=True,
            no_automatic_retry=True,
            production_admitted=False,
            training_started=False,
        )
    )
    persist(ctx.output / "completion_seal", seal)
    return seal


async def run_material(output):
    from .v14_material_registration import ledger_for

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
            completed = await execute_material(
                ctx, ledger, api_key=_key(ENV_FILE), stop_requested=stop
            )
            if completed is None:
                return None
            ctx.update(phase="SEALING", active=0)
            seal = await asyncio.to_thread(freeze_completion_seal, ctx, completed)
            ctx.update(phase="MATERIAL_ANNOTATIONS_COMPLETE", seal_id=seal["id"], active=0)
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
    result = asyncio.run(run_material(args.output))
    print(json.dumps(dict(complete=result is not None, seal_id=result["id"] if result else None)))


if __name__ == "__main__":
    main()
