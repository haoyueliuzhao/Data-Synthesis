"""R6: prospective flat wire + unchanged finite qualification, twelve calls only."""

from __future__ import annotations

import argparse
import asyncio
import fcntl
import subprocess
import sys
from pathlib import Path

from .calibration import ROOT, identity, now, publish
from .contracts import digest
from .probe_budget import ProbePriceSheet, read_budget_snapshot
from .storage import read_json, runtime_binding
from .v6_collection import ENV_FILE, STUDY, bound, require, sha
from .v6_review_revision import ORIGINAL, database
from .v7_full_probe import historical_prefix
from .v7_review_mask_trial import run as fixed_run

OUTPUT = STUDY / "review_revision_06"
PARENT = STUDY / "review_revision_05"


def checked_plan(output):
    from .v7_flat_review import WIRE_PROTOCOL

    plan = read_json(Path(output) / "registration/protocol.json")
    require(plan["id"] == digest({k: v for k, v in plan.items() if k != "id"}), "R6 plan changed")
    require(plan["runtime_binding"] == runtime_binding(), "R6 runtime changed")
    require(
        plan["wire_protocol"] == WIRE_PROTOCOL and plan["maximum_calls"] == len(plan["jobs"]) == 12,
        "R6 registered wire and fixed twelve calls required",
    )
    return plan


def register(output=OUTPUT):
    from .v7_flat_review import WIRE_PROTOCOL, flat_request

    output = Path(output)
    require(not output.exists(), "never overwrite existing R6 registration or raw outcomes")
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    for path in Path(__file__).parent.rglob("*.py"):
        require(
            path.read_bytes()
            == subprocess.check_output(
                ["git", "show", commit + ":" + str(path.relative_to(ROOT))], cwd=ROOT
            ),
            "freeze all R6 source before registration",
        )
    parent = read_json(PARENT / "registration/protocol.json")
    outcome = read_json(PARENT / "result/record.json")
    require(
        parent["id"] == digest({k: v for k, v in parent.items() if k != "id"})
        and outcome["id"] == digest({k: v for k, v in outcome.items() if k != "id"})
        and outcome["protocol_id"] == parent["id"]
        and outcome["technical_trial_admitted"] is False,
        "preserved failed R5 outcome must remain bound",
    )
    history = historical_prefix(STUDY / "review_revision_04")
    budget_state = read_budget_snapshot(database())
    snapshot = budget_state["snapshot"]
    require(
        not snapshot["halt"]
        and not snapshot["pending_requests"]
        and not snapshot["unacknowledged_unknown_requests"],
        "unclear new costs block R6",
    )
    jobs = []
    for old in parent["jobs"]:
        request = flat_request(old["request"])
        jobs.append({**old, "request": request, "request_sha256": digest(request)})
    cohort = parent["task_ids"]
    require(
        len(jobs) == 12
        and len(set(cohort)) == 6
        and {(j["task_id"], j["reviewer"], j["slot_index"]) for j in jobs}
        == {(t, r, 0) for t in cohort for r in (0, 1)},
        "same predetermined six task-slot0 pairs, never score-based selection",
    )
    cfg = history["ledger_config"]
    price = ProbePriceSheet(**cfg["price_sheet"])
    worst = sum(
        price.cost_microcny(
            hit=0, miss=price.context_input_token_ceiling, output=j["request"]["max_output_tokens"]
        )
        for j in jobs
    )
    require(
        worst <= snapshot["remaining_exposure_microcny"],
        "whole twelve-call exposure exceeds budget",
    )
    plan = bound(
        dict(
            schema="v7_flat_review_technical_trial.v1",
            at=now(),
            source_commit=commit,
            runtime_binding=runtime_binding(),
            wire_protocol=WIRE_PROTOCOL,
            authorization="查看实验。继续推进",
            model="deepseek-flash",
            thinking="disabled",
            parent_protocol_id=parent["id"],
            parent_result_id=outcome["id"],
            parent_result_sha256=sha(PARENT / "result/record.json"),
            historical_audit_id=history["id"],
            budget_snapshot_at_registration=snapshot,
            task_ids=cohort,
            jobs=jobs,
            maximum_calls=12,
            concurrency=4,
            retries=0,
            selection=parent["selection"],
            exact_original_twelve_coordinates_retained=True,
            change=(
                "root terms/nodes/edges; complete ID record arrays; "
                "existing update coherence rules explicit"
            ),
            host_JSON_repair=False,
            old_failed_returns_reclassified=False,
            substantive_semantic_rules_relaxed=False,
            previous_passes_reused=False,
            reference_from_Base_dev_used=False,
            public_Probe_prompt_changed=False,
            interface_gate="12/12 actual strict responses, no length, no new unknown usage",
            semantic_positive_yield_required=False,
            original_96_plus12_gate_not_replaced=True,
            no_automatic_full_generation_or_review=True,
            no_automatic_training=True,
            maximum_trial_exposure_microcny=worst,
            budget={**cfg, "path": str(database())},
            allowed_output_limits=cfg["allowed_output_limits"],
            GPU_reservation=False,
        )
    )
    publish(output / "historical_audit", history)
    publish(output / "budget_at_registration", budget_state)
    publish(output / "registration", plan, "protocol.json")
    return plan


async def run(output, env_file):
    from .v7_flat_review import inspect_slot_review

    return await fixed_run(
        output,
        env_file,
        plan_loader=checked_plan,
        review_inspector=inspect_slot_review,
        episode_prefix="v7flat6:",
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("register", "start", "run", "status"))
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--env-file", type=Path, default=ENV_FILE)
    args = parser.parse_args(argv)
    if args.action == "register":
        print(dict(protocol_id=register(args.output)["id"], maximum_calls=12))
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
