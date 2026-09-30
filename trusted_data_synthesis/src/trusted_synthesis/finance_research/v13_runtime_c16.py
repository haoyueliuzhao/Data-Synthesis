"""Explicit concurrency-16 continuation; frozen V13 source/plan/permit stay unchanged."""

import argparse
import asyncio
import fcntl
import json
import re
import signal
import sqlite3
from collections import deque
from contextlib import ExitStack, contextmanager
from pathlib import Path

from .calibration import now
from .contracts import ProviderCallError, digest
from .probe_budget import BudgetUnavailable, _request_record_digest
from .probe_collection import ENV_FILE
from .v6_collection import bound, persist, require, sha
from .v6_review_revision import _key
from .v13_material_controller import (
    NETWORK_WAVE_LIMIT,
    Context,
    SavedStop,
    _network_candidate,
    _paid_record,
    _progress,
    _provider,
    explicit_proxy,
    freeze_completion_seal,
    iid_for,
    job_directory,
    recover_stage,
)
from .v13_material_registration import OUTPUT, checked, checked_plan, entry, ledger_for, read_ref
from .v13_workflow import Supervisor as OriginalSupervisor

CAP = 16
USER_REPLY = "降至16，继续未发送项"
STOP_ID = "02b5fba4eb6b3aac61c2fcf689f4b2ae64510e3f74f8fe3aa624612ab98d038d"


def runtime_root(output):
    return Path(output).resolve() / "runtime_c16_01"


def runtime_source():
    return dict(path=str(Path(__file__).resolve()), sha256=sha(Path(__file__)))


def cause_diagnostic(error, api_key):
    cause = error.__cause__
    if cause is None:
        return None
    message = str(cause).replace(api_key, "<REDACTED>") if api_key else str(cause)
    message = re.sub(r"(https?://)[^\s/@]+@", r"\1<REDACTED>@", message)
    return dict(type=type(cause).__name__, message=message[:512], truncated=len(message) > 512)


@contextmanager
def exclusive(path):
    with Path(path).open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield


def observe_wallet(plan, *, allow_reserved=False):
    """Read only exact original 1316 coordinates, no ledger constructor/migration."""
    from types import SimpleNamespace

    path = Path(plan["budget_database"]).resolve()
    require(path.is_file(), "original wallet missing")
    found, unsent, unknown = [], [], []
    with sqlite3.connect(path.as_uri() + "?mode=ro", uri=True) as db:
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA query_only=ON")
        db.execute("BEGIN")
        config = json.loads(
            db.execute("SELECT value FROM metadata WHERE key='config'").fetchone()[0]
        )
        require(digest(config) == plan["budget_config_sha256"], "original wallet config differs")
        counter = dict(db.execute("SELECT * FROM counters WHERE singleton=1").fetchone())
        halt = db.execute("SELECT value FROM metadata WHERE key='halt'").fetchone()
        require(
            (allow_reserved or counter["pending"] == 0) and halt is None,
            "runtime change requires drained unhalted wallet",
        )
        identity = SimpleNamespace(run_id=config["run_id"])
        for job in plan["jobs"]:
            iid = iid_for(identity, job)
            row = db.execute("SELECT * FROM requests WHERE invocation_id=?", (iid,)).fetchone()
            if row is None:
                unsent.append(job["episode_id"])
                continue
            row = dict(row)
            coords = json.loads(row["coordinates_json"])
            terminal = row["state"] in {"SETTLED", "UNKNOWN"} and row["dispatched_at"] is not None
            reserved = (
                allow_reserved and row["state"] == "RESERVED" and row["dispatched_at"] is None
            )
            require(
                (terminal or reserved)
                and row["request_sha256"] == job["request_sha256"]
                and coords["episode_id"] == job["episode_id"]
                and coords["attempt_index"] == 1
                and coords["turn_index"] == 0,
                "unresolved/changed original call cannot be resent",
            )
            record = dict(
                episode_id=job["episode_id"],
                invocation_id=iid,
                kind=job["kind"],
                state=row["state"],
                original_row_sha256=_request_record_digest(row),
            )
            if row["state"] == "UNKNOWN":
                require(
                    _network_candidate(row),
                    "only recorded no-response network terminal belongs to baseline",
                )
                ack = db.execute(
                    "SELECT value FROM metadata WHERE key=?", ("acknowledged_unknown:" + iid,)
                ).fetchone()
                require(ack is not None, "original UNKNOWN lacks its retained-hold acknowledgement")
                acknowledgement = json.loads(ack[0])
                require(
                    acknowledgement["original_unknown_record_sha256"]
                    == record["original_row_sha256"]
                    and acknowledgement["permanent_reserved_microcny"] == row["reserved_microcny"],
                    "original UNKNOWN/hold binding differs",
                )
                record.update(permanent_reserved_microcny=row["reserved_microcny"])
                unknown.append(record)
            elif row["state"] == "SETTLED":
                require(
                    row["response_classification"] == "model_response",
                    "service failure is not a model return",
                )
            found.append(record)
        db.rollback()
    return dict(
        attempted=found,
        unsent_episode_ids=unsent,
        unknowns=unknown,
        wallet_counters=counter,
        ledger_open_mode="ro/query_only",
        wallet_modified=False,
    )


def checked_runtime(output, *, inspect_wallet=False):
    output = Path(output).resolve()
    plan = checked_plan(output)  # Original source/model/cap/request guards remain intact.
    record = checked(runtime_root(output) / "registration/record.json")
    require(
        record["schema"] == "v13_runtime_c16_authorization.v1"
        and record["original_plan"] == entry(output / "registration/record.json")
        and record["original_plan_id"] == plan["id"]
        and record["source_bindings"] == plan["source_bindings"]
        and record["runtime_source"] == runtime_source()
        and record["user_reply"] == USER_REPLY
        and record["effective_max_concurrency"] == CAP
        and record["stop_observation"]["id"] == STOP_ID,
        "immutable runtime/source/user authority binding differs",
    )
    read_ref(record["stop_observation"])
    if inspect_wallet:
        current = observe_wallet(plan, allow_reserved=True)
        by_episode = {r["episode_id"]: r for r in current["attempted"]}
        require(
            all(by_episode.get(r["episode_id"]) == r for r in record["baseline"]["attempted"]),
            "original 288 terminal records/holds changed",
        )
        allowed = set(record["baseline"]["unsent_episode_ids"])
        old = {r["episode_id"] for r in record["baseline"]["attempted"]}
        require(
            set(by_episode) <= old | allowed and set(current["unsent_episode_ids"]) <= allowed,
            "runtime cannot expand the original unsent roster",
        )
    return plan, record


def register_runtime(output=OUTPUT):
    output = Path(output).resolve()
    with ExitStack() as locks:
        locks.enter_context(exclusive(output / "workflow/controller.lock"))
        locks.enter_context(exclusive(output / "controller.lock"))
        if (runtime_root(output) / "registration/record.json").exists():
            return checked_runtime(output, inspect_wallet=True)[1]
        plan = checked_plan(output)
        stop = checked(output / "report_stop_01/record/record.json")
        baseline = observe_wallet(plan)
        require(
            stop["id"] == STOP_ID
            and stop["source_plan"]["id"] == plan["id"]
            and not stop["original_workflow_alive"]
            and not stop["financial_halt"]
            and len(baseline["attempted"]) == stop["attempted"] == 288
            and len(baseline["unknowns"]) == stop["network_unknowns"] == 8
            and len(baseline["unsent_episode_ids"]) == stop["unsent"] == 1028
            and sum(r["state"] == "SETTLED" for r in baseline["attempted"])
            == stop["returned"]
            == 280
            and all(r["kind"] == "mapping" for r in baseline["unknowns"]),
            "exact stopped 288/280/8 plus 1028 unsent baseline required",
        )
        record = bound(
            dict(
                schema="v13_runtime_c16_authorization.v1",
                at=now(),
                user_reply=USER_REPLY,
                original_plan=entry(output / "registration/record.json"),
                original_plan_id=plan["id"],
                protocol_id=plan["protocol_identity"],
                stop_observation=entry(output / "report_stop_01/record/record.json"),
                source_bindings=plan["source_bindings"],
                runtime_source=runtime_source(),
                baseline=baseline,
                original_registered_concurrency=plan["concurrency"],
                effective_max_concurrency=CAP,
                applies_only_to_original_unsent=True,
                original_total_calls=1316,
                new_calls_authorized_max=1028,
                new_budget_permit=False,
                money_and_request_caps_unchanged=True,
                request_bytes_unchanged=True,
                original_UNKNOWN_holds_preserved=True,
                no_retry=True,
                same_wave_network_stop_threshold=3,
                downstream_workflow_unchanged=True,
            )
        )
        persist(runtime_root(output) / "registration", record)
        return record


async def run_api(output=OUTPUT):
    output = Path(output).resolve()
    with exclusive(output / "controller.lock"):
        plan, runtime = checked_runtime(output, inspect_wallet=True)
        ctx = Context(output)
        require(ctx.plan == plan, "old Context plan must remain unchanged")
        ctx.update(
            runtime_registration_id=runtime["id"],
            effective_max_concurrency=CAP,
            original_registered_concurrency=plan["concurrency"],
        )
        ledger = ledger_for(plan)
        stop, done = asyncio.Event(), asyncio.Event()
        for sig in (signal.SIGTERM, signal.SIGINT):
            asyncio.get_running_loop().add_signal_handler(sig, stop.set)

        async def monitor():
            while not done.is_set():
                await asyncio.to_thread(ctx.report, ledger)
                try:
                    await asyncio.wait_for(done.wait(), 5)
                except TimeoutError:
                    pass

        watcher = asyncio.create_task(monitor())
        try:
            completed = await execute_c16(
                ctx, ledger, runtime=runtime, api_key=_key(ENV_FILE), stop_requested=stop
            )
            if completed is None:
                return None
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
            done.set()
            await watcher
            await asyncio.to_thread(ctx.report, ledger)


class Supervisor(OriginalSupervisor):
    def __init__(self, output):
        _, self.runtime = checked_runtime(output)
        super().__init__(output)

    def plain_job(self, job, phase):
        if job["key"] == "fixed-material-measurements":
            job = {**job, "module": "v13_runtime_c16", "args": ["api", "--output", self.output]}
        return super().plain_job(job, phase)


def run_workflow(output=OUTPUT):
    output = Path(output).resolve()
    with exclusive(output / "workflow/controller.lock"):
        supervisor = Supervisor(output)

        def stop(signum, frame):
            supervisor.stop = True

        for sig in (signal.SIGTERM, signal.SIGINT):
            signal.signal(sig, stop)
        return supervisor.run()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["register", "api", "run"])
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    result = (
        register_runtime(args.output)
        if args.action == "register"
        else (
            asyncio.run(run_api(args.output)) if args.action == "api" else run_workflow(args.output)
        )
    )
    print(
        json.dumps(
            dict(
                complete=result is not None,
                id=result.get("id") if isinstance(result, dict) else None,
            )
        )
    )


async def execute_c16(ctx, ledger, *, runtime, api_key, stop_requested=None):
    require(
        runtime["effective_max_concurrency"] == CAP
        and runtime["original_plan_id"] == ctx.plan["id"],
        "explicit concurrency-16 runtime binding required",
    )
    stop = stop_requested or asyncio.Event()
    ctx.update(phase="SOURCE_READ")
    completed = await asyncio.to_thread(recover_stage, ctx, ledger, ctx.jobs)
    baseline_ids = {r["episode_id"] for r in runtime["baseline"]["attempted"]}
    allowed = set(runtime["baseline"]["unsent_episode_ids"])
    require(
        baseline_ids <= set(completed)
        and {j["episode_id"] for j in ctx.jobs if j["episode_id"] not in completed} <= allowed,
        "only originally unsent runtime whitelist may dispatch; old terminals never resend",
    )
    # Registration fixes alternating purposes before any new model outcomes.
    pending = deque(j for j in ctx.jobs if j["episode_id"] not in completed)
    success = sum(t["terminal_kind"] == "paid_model_return" for t in completed.values())
    throttle = CAP
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
                    transport_cause=cause_diagnostic(exc, api_key),
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
            limit = min(CAP, throttle)
            wave = [pending.popleft() for _ in range(min(limit, len(pending)))]
            wave_stop = asyncio.Event()
            _progress(
                ctx,
                completed,
                phase="REVIEW_RUNNING",
                active=len(wave),
                registered_concurrency_ceiling=CAP,
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
                throttle = min(CAP, max(limit, throttle) * 2)
        require(len(completed) == len(ctx.jobs), "complete new matrix cannot omit deferred jobs")
        _progress(ctx, completed, phase="REVIEW_TERMINALS_COMPLETE", active=0)
        return completed


if __name__ == "__main__":
    main()
