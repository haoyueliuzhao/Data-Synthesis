"""One prospective 12-call engineering test; never launches the full inventory."""

from __future__ import annotations

import argparse
import asyncio
import fcntl
import math
import os
import subprocess
import sys
from pathlib import Path

import httpx

from .calibration import ROOT, identity, now, publish, status
from .contracts import digest
from .probe_budget import ProbePriceSheet
from .storage import read_json, runtime_binding
from .v6_collection import ENV_FILE, STUDY, bound, require
from .v6_decomposed_review import Context
from .v6_review_provider import request_review
from .v6_review_revision import ORIGINAL, _key, database, ledger_for
from .v7_full_probe import historical_prefix
from .v7_mask_review import _request, inspect_slot_review

OUTPUT = STUDY / "review_revision_05"
PARENT = STUDY / "review_revision_04"


def checked_plan(output):
    plan = read_json(Path(output) / "registration/protocol.json")
    require(plan["id"] == digest({k: v for k, v in plan.items() if k != "id"}), "R5 plan changed")
    require(plan["runtime_binding"] == runtime_binding(), "R5 runtime changed")
    require(len(plan["jobs"]) == 12 and plan["maximum_calls"] == 12, "R5 fixed denominator changed")
    return plan


def register(output=OUTPUT):
    output = Path(output)
    require(not output.exists(), "R5 registration never overwrites existing records")
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    for path in Path(__file__).parent.rglob("*.py"):
        require(
            path.read_bytes()
            == subprocess.check_output(
                ["git", "show", commit + ":" + str(path.relative_to(ROOT))], cwd=ROOT
            ),
            "commit R5 source before registration",
        )
    history = historical_prefix(PARENT)
    parent = read_json(PARENT / "registration/protocol.json")
    context = Context(PARENT, parent)
    jobs = []
    for job in parent["jobs"]:
        if job["stage"] == "slot" and job["slot_index"] == 0:
            request = _request(context.request(job))
            jobs.append({**job, "request": request, "request_sha256": digest(request)})
    cohort = parent["technical_gate"]["task_ids"]
    require(
        len(jobs) == 12
        and len(cohort) == 6
        and {(j["task_id"], j["reviewer"]) for j in jobs}
        == {(t, r) for t in cohort for r in (0, 1)},
        "same six tasks, fixed slot0, both reviewers required",
    )
    cfg = history["ledger_config"]
    price = ProbePriceSheet(**cfg["price_sheet"])
    reserve_upper = sum(
        price.cost_microcny(
            hit=0, miss=price.context_input_token_ceiling, output=j["request"]["max_output_tokens"]
        )
        for j in jobs
    )
    require(
        history["counters"]["spent"] + history["counters"]["held"] + reserve_upper
        <= cfg["hard_cap_microcny"],
        "whole bounded pilot must fit remaining shared worst-case exposure",
    )
    plan = bound(
        dict(
            schema="v7_empty_optional_field_technical_trial.v1",
            at=now(),
            source_commit=commit,
            runtime_binding=runtime_binding(),
            model="deepseek-flash",
            authorization="继续实验；预算充足，整体仍有七百左右的预算",
            parent_protocol_id=parent["id"],
            historical_audit_id=history["id"],
            task_ids=cohort,
            jobs=jobs,
            maximum_calls=12,
            concurrency=4,
            selection=(
                "same six preselected capacity tasks; original slot index0; "
                "both reviewers; no grade selection"
            ),
            finite_amendment=(
                "only model-labelled whole empty Q fields may be zero-loss nonassertive_context"
            ),
            no_original_review_reclassification=True,
            no_old_new_success_splicing=True,
            retries=0,
            all_original_failures_retained=True,
            interface_gate="12/12 actual strict responses; zero length; all new usage known",
            semantic_positive_yield_required=False,
            original_96_plus12_gate_not_replaced=True,
            no_automatic_full_generation_or_review=True,
            no_automatic_training=True,
            GPU_reservation=False,
            maximum_trial_exposure_microcny=reserve_upper,
            budget={**cfg, "path": str(database())},
            allowed_output_limits=cfg["allowed_output_limits"],
        )
    )
    publish(output / "historical_audit", history)
    publish(output / "registration", plan, "protocol.json")
    return plan


async def run(
    output,
    env_file,
    *,
    plan_loader=None,
    review_inspector=None,
    episode_prefix="v7m5:",
):
    """Shared fixed-12 executor; each prospective caller binds its own plan/wire.

    Historical CLI defaults remain v5. This does not resume or relabel a prior
    started trial; the immutable started barrier applies to every caller.
    """
    output = Path(output)
    plan = (plan_loader or checked_plan)(output)
    require(
        plan.get("maximum_calls") == 12 and len(plan.get("jobs", [])) == 12,
        "fixed executor requires exactly twelve independently registered calls",
    )
    inspector = review_inspector or inspect_slot_review
    require(
        not (output / "started").exists(),
        "started R5 requires explicit audit, never implicit resend",
    )
    ledger = ledger_for(plan)
    before = ledger.snapshot()
    require(
        not before["halt"]
        and not before["pending_requests"]
        and not before["unacknowledged_unknown_requests"],
        "unacknowledged or inflight cost blocks R5",
    )
    key = _key(env_file)
    os.environ.pop("DEEPSEEK_API_KEY", None)
    publish(output / "started", bound(dict(at=now(), protocol_id=plan["id"], budget=before)))
    completed, errors = {}, []
    stop = asyncio.Event()
    queue = asyncio.Queue()
    for job in plan["jobs"]:
        queue.put_nowait(job)

    def progress(phase="FIXED_12_REVIEW_RUNNING"):
        status(
            output,
            dict(
                at=now(),
                protocol_id=plan["id"],
                phase=phase,
                completed=len(completed),
                denominator=12,
                errors=errors,
                budget=ledger.snapshot(),
                training_started=False,
                full_generation_started=False,
                automatic_expansion=False,
            ),
        )

    progress()
    async with httpx.AsyncClient(
        follow_redirects=False,
        timeout=1200,
        limits=httpx.Limits(max_connections=4, max_keepalive_connections=4),
    ) as client:

        async def worker():
            while not stop.is_set():
                try:
                    job = queue.get_nowait()
                except asyncio.QueueEmpty:
                    return
                directory = output / "jobs" / digest(job["key"])
                episode = episode_prefix + digest(dict(protocol_id=plan["id"], job_key=job["key"]))
                request = job["request"]
                require(digest(request) == job["request_sha256"], "registered R5 request changed")
                publish(
                    directory / "started", dict(at=now(), episode_id=episode, job_key=job["key"])
                )
                try:
                    artifact = await request_review(
                        ledger=ledger,
                        api_key=key,
                        episode_id=episode,
                        request=request,
                        client=client,
                        timeout=max(180, math.ceil(90 + request["max_output_tokens"] / 128)),
                    )
                    publish(directory / "response", artifact)
                    if artifact["finish_reason"] != "tool_calls" or artifact.get(
                        "review_format_error"
                    ):
                        assessment = dict(
                            interface_admitted=False,
                            semantic_consistent=False,
                            validation=None,
                            error=artifact.get("review_format_error") or "non-normal finish",
                        )
                    else:
                        assessment = inspector(artifact["review_text"], request)
                    publish(directory / "assessment", assessment)
                    completed[job["key"]] = dict(artifact=artifact, assessment=assessment)
                except Exception as error:
                    blocked = dict(job_key=job["key"], error_type=type(error).__name__, retry=False)
                    publish(directory / "blocked", blocked)
                    errors.append(blocked)
                    stop.set()
                progress()

        await asyncio.gather(*(worker() for _ in range(4)))
    final = ledger.snapshot()
    passed = sum(v["assessment"]["interface_admitted"] for v in completed.values())
    semantic = sum(v["assessment"]["semantic_consistent"] for v in completed.values())
    truncated = sum(v["artifact"]["finish_reason"] == "length" for v in completed.values())
    result = bound(
        dict(
            at=now(),
            protocol_id=plan["id"],
            denominator=12,
            returned=len(completed),
            interface_passed=passed,
            semantic_consistent=semantic,
            length_count=truncated,
            errors=errors,
            technical_trial_admitted=len(completed) == passed == 12
            and not truncated
            and not errors
            and final["unknown_requests"] == before["unknown_requests"],
            original_full_review_gate_admitted=False,
            full_generation_started=False,
            automatic_expansion=False,
            training_started=False,
            actual_response_hashes={k: digest(v["artifact"]) for k, v in completed.items()},
            extra_settled_microcny=final["settled_tariff_microcny"]
            - before["settled_tariff_microcny"],
            budget=final,
        )
    )
    publish(output / "result", result)
    progress("FIXED_12_TRIAL_COMPLETE" if not errors else "FIXED_12_TRIAL_BLOCKED")
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("register", "run", "start", "status"))
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--env-file", type=Path, default=ENV_FILE)
    args = parser.parse_args(argv)
    if args.action == "register":
        plan = register(args.output)
        print(dict(protocol_id=plan["id"], maximum_calls=plan["maximum_calls"]))
    elif args.action == "status":
        print(read_json(args.output / "status.json"))
    elif args.action == "run":
        with (ORIGINAL / "controller.lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            print(asyncio.run(run(args.output, args.env_file)))
    else:
        checked_plan(args.output)
        with (args.output / "controller.log").open("ab") as log:
            proc = subprocess.Popen(
                [
                    sys.executable,
                    "-m",
                    __spec__.name,
                    "run",
                    "--output",
                    str(args.output),
                    "--env-file",
                    str(args.env_file),
                ],
                cwd=ROOT,
                stdin=subprocess.DEVNULL,
                stdout=log,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
        print(dict(pid=proc.pid, process_identity=identity(proc.pid), at=now()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
