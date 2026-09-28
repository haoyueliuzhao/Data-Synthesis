"""New typed-locator engineering cohort; retain the failed v3 cohort and spend."""

from __future__ import annotations

import argparse
import asyncio
import fcntl
import json
import subprocess
import sys
from pathlib import Path

from .calibration import ROOT, identity, now, publish
from .contracts import digest
from .probe_budget import ProbePriceSheet
from .storage import read_json, runtime_binding
from .v6_collection import ENV_FILE, STUDY, bound, checked_prepared, require, sha
from .v6_decomposed_review import (
    Context,
    bind_capacity,
    job_key,
    recover,
    run,
    task_inputs,
)
from .v6_review_revision import ALLOWED_OUTPUTS, ORIGINAL, connect, original_protocol, paid_row
from .v7_slot_review import capacity_features, slot_review_request

OUTPUT = STUDY / "review_revision_04"
PARENT = STUDY / "review_revision_03"


def history():
    parent = read_json(PARENT / "registration/protocol.json")
    require(
        parent["id"] == digest({k: v for k, v in parent.items() if k != "id"}),
        "parent protocol changed",
    )
    actual = recover(Context(PARENT, parent))
    gate = read_json(PARENT / "technical_gate/record.json")
    require(
        gate["id"] == digest({k: v for k, v in gate.items() if k != "id"})
        and gate["protocol_id"] == parent["id"]
        and not gate["admitted"],
        "failed parent cohort must remain explicit",
    )
    price = ProbePriceSheet(**parent["budget"]["price_sheet"])
    with connect() as con:
        require(
            con.execute("SELECT value FROM metadata WHERE key='halt'").fetchone() is None,
            "cannot bypass any shared paid halt",
        )
        config = json.loads(
            con.execute("SELECT value FROM metadata WHERE key='config'").fetchone()[0]
        )
        entries = [
            paid_row(row, price)[0]
            for row in con.execute("SELECT * FROM requests ORDER BY invocation_id")
        ]
        counters = dict(con.execute("SELECT * FROM counters WHERE singleton=1").fetchone())
    require(
        all(
            config.get(k) == parent["budget"].get(k)
            for k in (
                "run_id",
                "purpose",
                "price_sheet",
                "hard_cap_microcny",
                "warning_microcny",
                "request_cap",
            )
        )
        and config["hard_cap_microcny"] == 800_000_000
        and config["warning_microcny"] == 700_000_000
        and config["request_cap"] == 258000
        and config["amendment_id"] == parent["budget"]["amendment_id"],
        "typed trial must inherit exact original budget, not a larger replacement",
    )
    require(
        counters["held"] == counters["unknown"] == counters["pending"] == 0
        and counters["spent"] == sum(r["settled_microcny"] for r in entries),
        "prior spend unsettled",
    )
    return parent, bound(
        dict(
            at=now(),
            parent_protocol_id=parent["id"],
            parent_gate_sha256=sha(PARENT / "technical_gate/record.json"),
            parent_actual_calls=len(actual),
            ledger_config=config,
            budget_counters=counters,
            paid_entries=entries,
            no_prior_failures_or_costs_removed=True,
        )
    )


def register(output=OUTPUT):
    output = Path(output)
    if (output / "registration/protocol.json").exists():
        return read_json(output / "registration/protocol.json")
    require(not output.exists(), "never overwrite a partial registration")
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    for path in Path(__file__).parent.rglob("*.py"):
        require(
            path.read_bytes()
            == subprocess.check_output(
                ["git", "show", head + ":" + str(path.relative_to(ROOT))], cwd=ROOT
            ),
            "commit typed locator revision before paid registration",
        )
    parent, historical = history()
    original = original_protocol()
    cohort = parent["technical_gate"]["task_ids"]
    require(len(cohort) == len(set(cohort)) == 6, "same predetermined six tasks required")
    generation = {
        r["slot"]["slot_id"]: r
        for r in read_json(ORIGINAL / "generation_seal/record.json")["slots"]
    }
    selected = [s for s in original["inventory"]["slots"] if s["task_id"] in set(cohort)]
    jobs = []
    inputs = {}
    align_caps = {}
    publish(output / "historical_audit", historical)
    for task_id in cohort:
        prepared = checked_prepared(ORIGINAL, task_id)
        reference = json.loads(prepared["requests"][0]["messages"][1]["content"])[
            "review_only_private_reference"
        ]
        requests = {}
        capacities = []
        for slot in [s for s in selected if s["task_id"] == task_id]:
            sid = slot["slot_id"]
            path = Path(generation[sid]["episode_path"])
            require(sha(path) == generation[sid]["episode_file_sha256"], "original episode changed")
            episode = read_json(path)
            tokens = sum(t["usage"]["completion_tokens"] for t in episode["turns"])
            for reviewer in (0, 1):
                request = slot_review_request(prepared, sid, reference, reviewer)
                f = capacity_features(request)
                capacity = bind_capacity(
                    request,
                    generation_tokens=tokens,
                    fragments=f["target_fragment_count"],
                    actions=f["action_count"],
                )
                key = job_key("slot", task_id, reviewer, sid)
                requests[key] = request
                jobs.append(
                    dict(
                        key=key,
                        stage="slot",
                        task_id=task_id,
                        slot_id=sid,
                        slot_index=slot["slot_index"],
                        reviewer=reviewer,
                        request_sha256=digest(request),
                        capacity=capacity,
                    )
                )
                if reviewer == 0:
                    capacities.append(capacity)
        payload = bound(
            dict(task_id=task_id, requests=requests, original_prepared_id=prepared["id"])
        )
        publish(task_inputs(output, task_id), payload)
        inputs[task_id] = dict(
            id=payload["id"], sha256=sha(task_inputs(output, task_id) / "record.json")
        )
        align_caps[task_id] = bind_capacity(
            None,
            generation_tokens=sum(c["generation_tokens"] for c in capacities),
            fragments=sum(c["target_fragments"] for c in capacities),
            actions=sum(c["actions"] for c in capacities),
            alignment=True,
        )
    order = {t: i for i, t in enumerate(cohort)}
    jobs.sort(key=lambda j: (j["slot_index"], order[j["task_id"]], j["reviewer"]))
    for task_id in cohort:
        for reviewer in (0, 1):
            jobs.append(
                dict(
                    key=job_key("alignment", task_id, reviewer),
                    stage="alignment",
                    task_id=task_id,
                    slot_id=None,
                    reviewer=reviewer,
                    capacity=align_caps[task_id],
                )
            )
    require(len(jobs) == 108, "fixed engineering cohort changed")
    plan = bound(
        dict(
            schema="v7_typed_locator_engineering.v1",
            at=now(),
            source_commit=head,
            runtime_binding=runtime_binding(),
            authorization="继续实验；设计并登记新一整批轨迹，保留旧批，不按成绩拼接",
            parent_revision=str(PARENT),
            parent_protocol_id=parent["id"],
            historical_audit_id=historical["id"],
            original_task_ids=original["task_ids"],
            original_task_denominator=1000,
            original_slots=8000,
            task_ids=cohort,
            engineering_tasks=6,
            slot_inputs=inputs,
            jobs=jobs,
            slot_review_denominator=96,
            alignment_denominator=12,
            total_review_denominator=108,
            authorized_paid_jobs_this_registration=108,
            new_generation_calls=0,
            all_eight_common_candidates=True,
            only_field_locator_naming_changed=True,
            old_source_kind_and_semantic_checks_unchanged=True,
            old_reviewer_outputs_visible_to_new_reviews=False,
            no_previous_pass_reused=True,
            technical_gate=parent["technical_gate"],
            allowed_output_limits=ALLOWED_OUTPUTS,
            budget={
                **parent["budget"],
                "historical_spent_microcny": historical["budget_counters"]["spent"],
            },
            automatic_full_inventory_expansion=False,
            next_route="new_full_probe_authorized",
            native_zero_support_task_ids=parent["native_zero_support_task_ids"],
            model="deepseek-flash",
            thinking="disabled",
            temperature=0,
            automatic_training=False,
            GPU_reservation=False,
            concurrency=dict(pilot_slot=8, pilot_alignment=4),
            retry_count=0,
            format_repair=False,
        )
    )
    publish(output / "registration", plan, "protocol.json")
    return plan


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("register", "start", "run", "status"))
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--env-file", type=Path, default=ENV_FILE)
    args = parser.parse_args(argv)
    if args.action == "register":
        print(dict(protocol_id=register(args.output)["id"]))
    elif args.action == "status":
        print(read_json(args.output / "status.json"))
    elif args.action == "run":
        with (ORIGINAL / "controller.lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            asyncio.run(run(args.output, args.env_file))
    else:
        from .v6_decomposed_review import checked_plan

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
