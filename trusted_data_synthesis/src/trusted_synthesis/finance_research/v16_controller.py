"""One bounded six-request wave, with exact receipt replay and no automatic retry."""

from __future__ import annotations

import argparse
import asyncio
import fcntl
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

from . import v16_adjudication_protocol as protocol
from . import v16_budget as budget
from . import v16_provider as provider
from .calibration import now
from .contracts import digest, invocation_identity
from .probe_collection import ENV_FILE
from .v6_collection import bound, persist, require
from .v6_review_revision import _key
from .v13_material_registration import checked, entry, read_ref
from .v16_registration import OUTPUT, checked_plan, ledger_for, resolve_proxy


def _runtime(runtime=None):
    if runtime is not None:
        require(
            (runtime.version, runtime.scope, runtime.count)
            in {("v16", "six", 6), ("v17", "three", 3)},
            "fixed authorized wave only",
        )
        require(runtime.protocol.MODEL == "deepseek-flash", "fixed flash API model required")
        return runtime
    return SimpleNamespace(
        version="v16",
        scope="six",
        count=6,
        protocol=protocol,
        budget=budget,
        provider=provider,
        checked_plan=checked_plan,
        ledger_for=ledger_for,
        resolve_proxy=resolve_proxy,
    )


def request_for(job, plan, *, runtime=None):
    rt = _runtime(runtime)
    request = rt.protocol.checked_request(read_ref(job["request"]))
    # The checker may return the validated request or merely its truth value.
    if not isinstance(request, dict):
        request = read_ref(job["request"])
    body = rt.protocol.request_body(request)
    wire = json.dumps(
        body, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode()
    require(
        request["id"] == job["request_id"]
        and request["episode_id"] == job["episode_id"]
        and request["protocol_id"] == plan["protocol_identity"]
        and request["task_id"] == job["task_id"]
        and request["slot_ids"] == job["slot_ids"]
        and request["max_output_tokens"] == job["max_output_tokens"]
        and body["model"] == "deepseek-flash"
        and digest(body) == job["request_sha256"]
        and hashlib.sha256(wire).hexdigest() == job["request_body_sha256"],
        "only exact pre-registered request bytes may be sent",
    )
    return request


def iid_for(ledger, job):
    return invocation_identity(
        dict(run_id=ledger.run_id, episode_id=job["episode_id"], attempt_index=1), turn_index=0
    )["invocation_id"]


def save_paid(output, plan, job, request, row, *, runtime=None):
    rt = _runtime(runtime)
    directory = Path(output) / "annotations" / job["episode_id"].split(":", 1)[1]
    artifact = rt.provider.restore_settled(row, request)
    record = rt.provider.paid_record(request, artifact, row)
    persist(directory / "artifact", artifact)
    persist(directory / "record", record)
    terminal = bound(
        dict(
            schema=f"{rt.version}_adjudication_terminal.v1",
            registration_id=plan["id"],
            protocol_id=plan["protocol_identity"],
            task_id=job["task_id"],
            episode_id=job["episode_id"],
            role="mapping",
            purpose="mapping",
            slot_ids=job["slot_ids"],
            request=job["request"],
            terminal_kind="paid_model_return",
            record=entry(directory / "record/record.json"),
            physical_attempt_index=1,
            no_resend=True,
        )
    )
    persist(directory / "terminal", terminal)
    return entry(directory / "terminal/record.json")


async def execute(output, plan, ledger, *, api_key, client, runtime=None):
    rt = _runtime(runtime)
    require(plan["expected_requests"] == len(plan["jobs"]) == rt.count, "exact wave size required")
    output = Path(output).resolve()
    requests = {j["episode_id"]: request_for(j, plan, runtime=rt) for j in plan["jobs"]}
    before = ledger.snapshot()
    stop = asyncio.Event()

    async def worker(job):
        request = requests[job["episode_id"]]
        row = ledger.request_record(iid_for(ledger, job))
        try:
            if row is not None and row["state"] == "SETTLED":
                return dict(
                    terminal=save_paid(output, plan, job, request, row, runtime=rt), error=None
                )
            require(
                row is None or row["state"] == "RESERVED" and row["dispatched_at"] is None,
                "already dispatched unresolved requests must never be resent",
            )
            require(not stop.is_set(), "wave stopped before request dispatch")
            await rt.provider.request_once(
                ledger=ledger,
                api_key=api_key,
                request=request,
                client=client,
                timeout=1200.0,
                resume_reserved=row is not None,
            )
            row = ledger.request_record(iid_for(ledger, job))
            return dict(terminal=save_paid(output, plan, job, request, row, runtime=rt), error=None)
        except Exception as exc:
            stop.set()
            row = ledger.request_record(iid_for(ledger, job))
            issue = bound(
                dict(
                    schema=f"{rt.version}_adjudication_saved_failure.v1",
                    at=now(),
                    registration_id=plan["id"],
                    task_id=job["task_id"],
                    episode_id=job["episode_id"],
                    request=job["request"],
                    error_type=type(exc).__name__,
                    error=str(exc),
                    ledger_state=None if row is None else row["state"],
                    dispatched=False if row is None else row["dispatched_at"] is not None,
                    semantic_judgment=None,
                    unknown_hold_released=False,
                    automatic_retry=False,
                )
            )
            path = output / "failures" / issue["id"]
            persist(path, issue)
            return dict(terminal=None, error=entry(path / "record.json"))

    started = now()
    outcomes = await asyncio.gather(*(worker(j) for j in plan["jobs"]))
    terminals = [o["terminal"] for o in outcomes if o["terminal"] is not None]
    errors = [o["error"] for o in outcomes if o["error"] is not None]
    after = ledger.snapshot()
    usable = sum(
        read_ref(read_ref(t)["record"])["inspection"].get("mapping_admitted") is True
        for t in terminals
    )
    seal_ref, existing_seal_reused = None, False
    if len(terminals) == rt.count and not errors:
        seal_fields = dict(
            schema=f"{rt.version}_{rt.scope}_adjudication_completion_seal.v1",
            registration_id=plan["id"],
            protocol_id=plan["protocol_identity"],
            expected_calls=rt.count,
            actual_returns=rt.count,
            usable_returns=usable,
            network_unknowns=0,
            all_registered_jobs_have_authentic_terminals=True,
            terminals=terminals,
            no_automatic_retry=True,
            Student_observations_not_consumed=True,
        )
        seal_path = output / "completion_seal/record.json"
        if seal_path.exists():
            seal = checked(seal_path)
            require(
                all(seal.get(key) == value for key, value in seal_fields.items()),
                "existing completion seal differs from the exact six settled terminals",
            )
            existing_seal_reused = True
        else:
            seal = bound(dict(at=now(), started_at=started, **seal_fields))
            persist(output / "completion_seal", seal)
        seal_ref = entry(output / "completion_seal/record.json")
    result = bound(
        dict(
            schema=f"{rt.version}_{rt.scope}_adjudication_controller_result.v1",
            started_at=started,
            at=now(),
            registration_id=plan["id"],
            expected_calls=rt.count,
            actual_returns=len(terminals),
            usable_returns=usable,
            errors=errors,
            completion_seal=seal_ref,
            existing_completion_seal_reused=existing_seal_reused,
            phase="COMPLETE" if len(terminals) == rt.count else "SAVED_FAILURE_NO_RETRY",
            before_budget=before,
            after_budget=after,
            no_automatic_retry=True,
            historical_UNKNOWN_holds_not_modified=True,
        )
    )
    persist(output / "controller_result", result)
    return result


def deploy(output=OUTPUT, *, runtime=None):
    rt = _runtime(runtime)
    output = Path(output).resolve()
    plan = rt.checked_plan(output)
    ledger = rt.ledger_for(plan)
    permit = rt.budget.register_matrix(
        ledger,
        plan,
        rt.budget.authorization_definition(plan),
        backup_path=output / f"wallet_before_{rt.version}.sqlite3",
    )
    saved_path = output / "deployment/record.json"
    if saved_path.exists():
        saved = checked(saved_path)
        require(
            saved["schema"] == f"{rt.version}_{rt.scope}_deployment.v1"
            and saved["registration_id"] == plan["id"]
            and saved["permit"] == permit
            and saved["no_API_calls"] is True,
            "existing deployment must retain this exact six-task registration and permit",
        )
        return saved
    result = bound(
        dict(
            schema=f"{rt.version}_{rt.scope}_deployment.v1",
            at=now(),
            registration_id=plan["id"],
            permit=permit,
            no_API_calls=True,
            budget=ledger.snapshot(),
        )
    )
    persist(output / "deployment", result)
    return result


def run(output=OUTPUT, *, runtime=None):
    rt = _runtime(runtime)
    output = Path(output).resolve()
    plan = rt.checked_plan(output)
    with (output / "controller.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if (output / "controller_result/record.json").exists():
            result = checked(output / "controller_result/record.json")
            require(
                result["schema"] == f"{rt.version}_{rt.scope}_adjudication_controller_result.v1"
                and result["registration_id"] == plan["id"]
                and result["expected_calls"] == rt.count
                and result["no_automatic_retry"] is True,
                "saved wave belongs to this exact six-task plan",
            )
            if result["completion_seal"] is not None:
                seal = read_ref(result["completion_seal"])
                require(
                    result["completion_seal"] == entry(output / "completion_seal/record.json")
                    and seal["registration_id"] == plan["id"]
                    and seal["protocol_id"] == plan["protocol_identity"]
                    and seal["expected_calls"] == seal["actual_returns"] == rt.count
                    and seal["usable_returns"] == result["usable_returns"]
                    and result["actual_returns"] == rt.count
                    and result["phase"] == "COMPLETE"
                    and not result["errors"],
                    "saved completed wave requires its original bound completion seal",
                )
            else:
                require(
                    result["phase"] == "SAVED_FAILURE_NO_RETRY"
                    and result["actual_returns"] < rt.count
                    and result["errors"],
                    "saved incomplete wave cannot become a new request wave",
                )
            return result
        ledger = rt.ledger_for(plan)
        deployment = checked(output / "deployment/record.json")
        require(
            deployment["registration_id"] == plan["id"], "specific deployment must precede dispatch"
        )
        proxy = rt.resolve_proxy(plan)

        async def invoke():
            async with rt.provider.annotation_client(timeout=1200.0, proxy=proxy) as client:
                return await execute(
                    output, plan, ledger, api_key=_key(ENV_FILE), client=client, runtime=rt
                )

        return asyncio.run(invoke())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("deploy", "run"))
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    result = deploy(args.output) if args.action == "deploy" else run(args.output)
    print(
        json.dumps(
            dict(
                id=result["id"],
                phase=result.get("phase"),
                actual_returns=result.get("actual_returns"),
                usable_returns=result.get("usable_returns"),
            )
        )
    )


if __name__ == "__main__":
    main()
