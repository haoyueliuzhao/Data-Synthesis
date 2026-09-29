"""Independent launch of the original registered V7 1000x8 public Probe batch.

This new admission does not upgrade R6. One original wallet, exact old new-slot
IDs/configs, no resampling, and no private reference before the whole 8000 seal.
"""

from __future__ import annotations

import argparse
import asyncio
import fcntl
import os
import sqlite3
import subprocess
import sys
from collections import Counter
from pathlib import Path

from .calibration import ROOT, identity, now, publish, status
from .cli import _key
from .contracts import Episode, PrivateReference, RunConfig, TaskBundle, digest
from .harness import episode_tool_specs, run_episode, system_message
from .planning import task_key, verify_role_plan
from .probe_budget import ProbeBudget, apply_v8_request_partition, read_budget_snapshot
from .probe_collection import ENV_FILE, slot_directory
from .probe_provider import BudgetedDeepSeekFlashProvider
from .probe_recovery import _validate_turn
from .profiles import public_run_view
from .settlement import episode_is_complete
from .storage import (
    EventSink,
    _read_snapshot_rows,
    load_public_snapshot,
    read_json,
    runtime_binding,
)
from .v6_collection import STUDY, bound, mechanical_check, persist, require, sha
from .v6_review_revision import database
from .v6_task import score_public_reasoning_program
from .v8_representation import validate_material_registration

ORIGINAL = STUDY / "new_full_probe_v7_01/registration/protocol.json"
ORIGINAL_ID = "ed78f27d36129f3668f40914824178ce5604b25c60ffc030b1fbb0b90703e1bb"
OUTPUT = STUDY / "new_full_probe_v8_launch_01"
REPRESENTATION = STUDY / "audit_revision_20260929/representation_preflight/record.json"
POLICY = STUDY / "audit_revision_20260929/review_policy_01/record.json"
AUDIT = Path(
    "/home/zhuxinrui/.codex/attachments/0268220d-09d0-4453-a7d0-5703e9762d38/已粘贴的文本.txt"
)


def checked_record(path):
    record = read_json(path)
    require(
        record.get("id") == digest({k: v for k, v in record.items() if k != "id"}),
        "bound record changed: " + str(path),
    )
    return record


def public_tasks(original):
    manifest, tasks, lineages = load_public_snapshot(original["original_snapshot"])
    verify_role_plan(original["role_plan"], tasks, lineages)
    wanted = [t for t in tasks if original["role_plan"]["assignments"][task_key(t)] == "sft"]
    require(
        manifest["id"] == original["snapshot_id"]
        and [t.task_id for t in wanted] == original["task_ids"]
        and len(wanted) == 1000,
        "retain original complete 1000-task population",
    )
    require(
        len(original["slots"]) == 8000 and len({s["slot_id"] for s in original["slots"]}) == 8000,
        "retain all 8000 independent original new slots",
    )
    groups = {t.task_id: [] for t in wanted}
    for slot in original["slots"]:
        require(
            slot["task_id"] in groups and slot["slot_id"].startswith("v7-slot:"),
            "unknown generation slot/task",
        )
        groups[slot["task_id"]].append(slot["slot_index"])
    require(
        all(sorted(indices) == list(range(8)) for indices in groups.values()),
        "exactly eight original slots per task; no conditional population",
    )
    for task in wanted:
        config = RunConfig.model_validate(original["configs_by_task"][task.task_id])
        require(
            config.model_dump(mode="json") == original["configs_by_task"][task.task_id]
            and config.harness_id == "bigfinance-derived-vtdo-v7"
            and config.submission_profile == "finqa-public-reasoning-v2"
            and config.role == "sft"
            and config.api_model == "deepseek-flash"
            and (config.temperature, config.top_p, config.top_k) == (1, 1, 0)
            and config.max_steps == 32
            and config.context_limit == 1048576
            and config.max_new_tokens in (2048, 16384)
            and system_message(config) == original["public_system"]
            and episode_tool_specs(config) == original["public_tools"]
            and digest(public_run_view(task, config.submission_profile))
            == original["public_capacity_by_task"][task.task_id]["public_view_sha256"],
            "original V7 public input/configuration changed",
        )
    return {t.task_id: t for t in wanted}


def build_plan(*, policy_path, representation_path, source_commit, ledger_path=None):
    original = read_json(ORIGINAL)
    historical_identity = validate_material_registration(original)
    require(original["id"] == ORIGINAL_ID, "launch only the independently registered ed78 batch")
    public_tasks(original)
    policy_path, representation_path = Path(policy_path), Path(representation_path)
    policy, representation = checked_record(policy_path), checked_record(representation_path)
    require(
        policy["schema"] == "v8_review_policy_registration.v1"
        and policy["definition"].get("schema") == "v8_single_target_policy.v1"
        and policy["definition"].get("id")
        == digest({k: v for k, v in policy["definition"].items() if k != "id"})
        and policy["definition"]["model"] == "deepseek-flash"
        and policy["definition"]["freeze"]["before_new_generation"] is True
        and policy["definition"]["budget"]["shared_review_partition_requests"] == 18108,
        "freeze the new audit review policy first",
    )
    require(
        representation["schema"] == "v8_public_representation_preflight.v1"
        and representation["original_material_protocol_id"] == original["id"]
        and representation["initial_representation_admitted"] is True,
        "original public-prefix Student representation must pass before generation",
    )
    ledger_path = Path(ledger_path or database()).resolve()
    history = read_budget_snapshot(ledger_path)
    snapshot = history["snapshot"]
    require(
        snapshot["requests_reserved"] == 18942
        and snapshot["pending_requests"] == 0
        and snapshot["unacknowledged_unknown_requests"] == 0
        and snapshot["halt"] is None,
        "new launch requires quiescent complete historical accounting",
    )
    order = {task_id: i for i, task_id in enumerate(original["task_ids"])}
    slots = original["slots"]
    return bound(
        dict(
            schema="v8_independent_public_generation_launch.v1",
            at=now(),
            source_commit=source_commit,
            runtime_binding=runtime_binding(),
            authorization="用户授权参照20260929阶段审计修订并推进；生成与审阅准入分离",
            audit_source=dict(path=str(AUDIT), sha256=sha(AUDIT)),
            old_WAITING_FOR_AUDIT_preserved=True,
            resume_authority=(
                "latest user request plus separately frozen new audit launch; "
                "no old marker overwrite"
            ),
            original_protocol_path=str(ORIGINAL),
            original_protocol_id=original["id"],
            original_protocol_sha256=sha(ORIGINAL),
            original_registration_identity_evidence=historical_identity,
            original=original,
            snapshot=original["original_snapshot"],
            snapshot_id=original["snapshot_id"],
            task_ids=original["task_ids"],
            task_denominator=1000,
            slot_denominator=8000,
            slots=slots,
            configs_by_task=original["configs_by_task"],
            launch_order=[
                s["slot_id"]
                for s in sorted(slots, key=lambda s: (s["slot_index"], order[s["task_id"]]))
            ],
            public_inputs_configs_and_slot_ids_unchanged=True,
            review_policy=dict(
                path=str(policy_path.resolve()), id=policy["id"], sha256=sha(policy_path)
            ),
            representation_preflight=dict(
                path=str(representation_path.resolve()),
                id=representation["id"],
                sha256=sha(representation_path),
            ),
            whole_generated_package_Student_admission_claimed=False,
            budget_database=str(ledger_path),
            budget_config=history["config"],
            budget_config_sha256=history["config_sha256"],
            historical_snapshot=history,
            partition_id="v8-partition:"
            + digest(
                dict(
                    original=original["id"],
                    policy=policy["id"],
                    representation=representation["id"],
                )
            ),
            partition_limits=dict(
                generation=220000,
                technical_review=108,
                production_review=18000,
                unallocated_buffer=950,
            ),
            original_session_call_cap=32,
            generation_completion_guaranteed=False,
            concurrency=16,
            first_slot_serial_transport_settlement_only=True,
            all_generation_before_private_reference=True,
            old_R6_result_unchanged=True,
            old_R6_gate_is_not_generation_admission=True,
            no_resampling=True,
            all_8000_denominator_retained=True,
            native_false_V_trace="not_assessed_native_ineligible",
            any_native_zero_support_stops_production_review_and_training=True,
            automatic_production_review=False,
            automatic_training=False,
            GPU_reservation=False,
        )
    )


def checked_plan(output):
    plan = checked_record(Path(output) / "registration/protocol.json")
    require(plan["runtime_binding"] == runtime_binding(), "frozen generation source changed")
    require(
        sha(plan["original_protocol_path"]) == plan["original_protocol_sha256"],
        "old ed78 registration changed",
    )
    for name in ("review_policy", "representation_preflight"):
        item = plan[name]
        require(
            sha(item["path"]) == item["sha256"]
            and checked_record(item["path"])["id"] == item["id"],
            "pre-generation policy/representation binding changed",
        )
    return plan


def register(output=OUTPUT, *, policy_path, representation_path=REPRESENTATION):
    output = Path(output)
    if (output / "registration/protocol.json").exists():
        plan = checked_plan(output)
    else:
        require(not output.exists(), "partial launch registration cannot be overwritten")
        head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
        for path in Path(__file__).parent.rglob("*.py"):
            require(
                path.read_bytes()
                == subprocess.check_output(
                    ["git", "show", head + ":" + str(path.relative_to(ROOT))], cwd=ROOT
                ),
                "commit all frozen source before registering execution",
            )
        plan = build_plan(
            policy_path=policy_path, representation_path=representation_path, source_commit=head
        )
        publish(output / "registration", plan, "protocol.json")
    partition = apply_v8_request_partition(
        plan["budget_database"],
        expected_run_id=plan["budget_config"]["run_id"],
        expected_config_sha256=plan["budget_config_sha256"],
        partition_id=plan["partition_id"],
        generation_episode_ids=[s["slot_id"] for s in plan["slots"]],
        evidence=dict(
            user_authorization=plan["authorization"],
            launch_protocol_id=plan["id"],
            fixed_review_policy_id=plan["review_policy"]["id"],
        ),
    )
    persist(output / "request_partition", partition)
    return plan


def ledger_for(plan):
    saved = read_budget_snapshot(plan["budget_database"])
    require(saved["config_sha256"] == plan["budget_config_sha256"], "original wallet changed")
    require(
        saved["snapshot"].get("request_partition", {}).get("partition_id") == plan["partition_id"],
        "new partition must be registered without resetting the original wallet",
    )
    cfg = plan["budget_config"]
    return ProbeBudget(
        plan["budget_database"],
        **{
            k: cfg[k]
            for k in (
                "run_id",
                "price_sheet",
                "max_output_tokens",
                "purpose",
                "hard_cap_microcny",
                "warning_microcny",
                "request_cap",
                "amendment_id",
                "allowed_output_limits",
            )
        },
    )


def validate_recovery(output, plan, ledger, *, tasks=None):
    """One quiescent generation check; other registered review jobs may be active."""
    output = Path(output)
    tasks = tasks or public_tasks(plan["original"])
    snapshot = ledger.snapshot()
    require(
        not snapshot["halt"] and not snapshot["unacknowledged_unknown_requests"],
        "unresolved shared-ledger failure cannot silently resume generation",
    )
    complete, seen = {}, set()
    registered_dirs = {slot_directory(output, s).name for s in plan["slots"]}
    require(
        all(p.name in registered_dirs for p in (output / "slots").glob("*")),
        "unregistered slot artifacts",
    )
    with sqlite3.connect(
        Path(plan["budget_database"]).resolve().as_uri() + "?mode=ro", uri=True
    ) as con:
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA query_only=ON")
        for slot in plan["slots"]:
            directory = slot_directory(output, slot)
            if not directory.exists():
                continue
            outcome_path, episode_path = (
                directory / "outcome/record.json",
                directory / "episode/episode.json",
            )
            require(
                outcome_path.is_file() and episode_path.is_file(),
                "incomplete durable slot: never resample",
            )
            row = read_json(outcome_path)
            episode = Episode.model_validate_json(episode_path.read_bytes())
            cfg = RunConfig.model_validate(plan["configs_by_task"][slot["task_id"]])
            require(
                row["status"] == "COMPLETE"
                and row["slot"] == slot
                and sha(episode_path) == row["episode_file_sha256"]
                and digest(episode) == row["episode_sha256"]
                and episode_is_complete(episode)
                and episode.config == cfg
                and episode.task_id == slot["task_id"],
                "saved slot is incomplete or its original identity changed",
            )
            events = sorted((directory / "events").glob("*/event.json"))
            final = read_json(events[-1]) if events else {}
            require(
                final.get("kind") == "episode_completed"
                and final.get("payload") == episode.model_dump(mode="json"),
                "completed episode differs from its durable terminal event",
            )
            reservation = ledger.price_sheet.cost_microcny(
                hit=0,
                miss=ledger.price_sheet.context_input_token_ceiling,
                output=cfg.max_new_tokens,
            )
            for index, turn in enumerate(episode.turns):
                iid, _, _ = _validate_turn(
                    con,
                    turn=turn,
                    index=index,
                    slot_id=slot["slot_id"],
                    plan={"id": ledger.run_id},
                    sheet=ledger.price_sheet,
                    output_limit=cfg.max_new_tokens,
                    reservation=reservation,
                )
                require(iid not in seen, "same paid generation invocation used twice")
                seen.add(iid)
            checks = mechanical_check(tasks[slot["task_id"]], episode, slot, {"id": ledger.run_id})
            require(
                all(
                    checks[k]
                    for k in (
                        "calls_settled",
                        "history_complete",
                        "actions_observations_bound",
                        "private_reference_isolated",
                    )
                ),
                "original public history/action replay differs",
            )
            complete[slot["slot_id"]] = row
        paid = {
            r[0]
            for r in con.execute(
                "SELECT invocation_id FROM v8_request_allocations WHERE category='generation'"
            )
        }
        require(paid == seen, "paid generation row without complete original slot; no resampling")
        counted = con.execute(
            "SELECT consumed FROM v8_request_quotas WHERE category='generation'"
        ).fetchone()[0]
        require(len(paid) == counted, "generation partition/paid evidence count differs")
    return complete


def seal_generation(output, plan, ledger, complete):
    require(
        len(complete) == plan["slot_denominator"]
        and set(complete) == {s["slot_id"] for s in plan["slots"]},
        "all original 8000 slots must complete before seal/scoring",
    )
    body = bound(
        dict(
            schema="v8_whole_generation_seal.v1",
            protocol_id=plan["id"],
            denominator=plan["slot_denominator"],
            private_references_read=False,
            slots=[complete[s["slot_id"]] for s in plan["slots"]],
        )
    )
    persist(Path(output) / "generation_seal", body)
    return body


async def collect(output, plan, ledger, key, *, client=None, _validated_complete=None):
    import httpx

    output = Path(output)
    tasks = public_tasks(plan["original"])
    complete = (
        validate_recovery(output, plan, ledger, tasks=tasks)
        if _validated_complete is None
        else _validated_complete
    )
    slots = {s["slot_id"]: s for s in plan["slots"]}
    active, blocked = set(), []
    halted, done = asyncio.Event(), asyncio.Event()

    def progress(phase="GENERATING"):
        status(
            output,
            dict(
                at=now(),
                protocol_id=plan["id"],
                phase=phase,
                completed=len(complete),
                denominator=plan["slot_denominator"],
                active=len(active),
                not_completed=plan["slot_denominator"] - len(complete),
                blocked=blocked,
                budget=ledger.snapshot(),
                private_references_read=False,
                review_started_by_generation=False,
                training_started=False,
            ),
        )

    async def monitor():
        while not done.is_set():
            progress()
            try:
                await asyncio.wait_for(done.wait(), 10)
            except TimeoutError:
                pass

    async def one(sid, transport):
        if halted.is_set() or ledger.snapshot()["halt"]:
            halted.set()
            return
        slot, directory = slots[sid], slot_directory(output, slots[sid])
        active.add(sid)
        publish(directory / "started", dict(at=now(), slot=slot, attempt=1))
        try:
            provider = BudgetedDeepSeekFlashProvider(
                ledger=ledger, api_key=key, episode_id=sid, client=transport
            )
            episode = await run_episode(
                tasks[slot["task_id"]],
                provider,
                RunConfig.model_validate(plan["configs_by_task"][slot["task_id"]]),
                sink=EventSink(directory / "events"),
                invocation_context=dict(run_id=ledger.run_id, episode_id=sid, attempt_index=1),
            )
            publish(directory / "episode", episode.model_dump(mode="json"), "episode.json")
            settled = episode_is_complete(episode)
            row = dict(
                status="COMPLETE" if settled else "BLOCKED",
                at=now(),
                slot=slot,
                episode_sha256=digest(episode),
                episode_file_sha256=sha(directory / "episode/episode.json"),
                actual_model_calls=episode.actual_model_calls,
                stop_reason=episode.stop_reason,
                all_provider_calls_settled=episode.all_provider_calls_settled,
            )
            publish(directory / "outcome", row)
            if settled:
                complete[sid] = row
            else:
                blocked.append(dict(slot_id=sid, reason=episode.stop_reason))
                halted.set()
        except BaseException as error:
            if not (directory / "outcome").exists():
                publish(
                    directory / "outcome",
                    dict(
                        status="BLOCKED",
                        at=now(),
                        slot=slot,
                        error_type=type(error).__name__,
                        automatic_retry=False,
                    ),
                )
            blocked.append(dict(slot_id=sid, error_type=type(error).__name__))
            halted.set()
            if not isinstance(error, Exception):
                raise
        finally:
            active.discard(sid)

    async def dispatch(transport):
        first = plan["launch_order"][0]
        if first not in complete:
            await one(first, transport)
        if halted.is_set():
            return
        require(
            first in complete and complete[first]["actual_model_calls"] >= 1,
            "first registered slot must establish real transport/settlement, not quality",
        )
        persist(
            output / "transport_admission",
            bound(
                dict(
                    protocol_id=plan["id"],
                    slot_id=first,
                    episode_sha256=complete[first]["episode_sha256"],
                    actual_model_calls=complete[first]["actual_model_calls"],
                    quality_used=False,
                    transport_settlement_passed=True,
                )
            ),
        )
        queue = asyncio.Queue()
        for sid in plan["launch_order"]:
            if sid not in complete:
                queue.put_nowait(sid)

        async def work():
            while not halted.is_set():
                try:
                    sid = queue.get_nowait()
                except asyncio.QueueEmpty:
                    return
                await one(sid, transport)

        await asyncio.gather(*(work() for _ in range(plan["concurrency"])))

    watcher = asyncio.create_task(monitor())
    try:
        if client is not None:
            await dispatch(client)
        else:
            # Default HTTP transport has zero retries; retain the user's proxy.
            async with httpx.AsyncClient(
                timeout=120,
                follow_redirects=False,
                trust_env=False,
                limits=httpx.Limits(max_connections=16, max_keepalive_connections=16),
            ) as transport:
                await dispatch(transport)
    finally:
        done.set()
        await watcher
    if halted.is_set() or len(complete) != plan["slot_denominator"]:
        progress("GENERATION_INCOMPLETE_NO_RESAMPLING")
        return False
    complete = validate_recovery(output, plan, ledger, tasks=tasks)
    seal_generation(output, plan, ledger, complete)
    progress("GENERATION_COMPLETE")
    # Hand this same-process verification to native scoring; do not replay the
    # entire 8000 history twice consecutively. Independent entrypoints verify.
    return complete


def score_native_support(output, plan, ledger, *, _validated_complete=None):
    """Native scores only after whole generation; never dispatch a semantic review."""
    output = Path(output)
    complete = (
        validate_recovery(output, plan, ledger)
        if _validated_complete is None
        else _validated_complete
    )
    seal = seal_generation(output, plan, ledger, complete)
    if (output / "native_support/record.json").exists():
        prior = checked_record(output / "native_support/record.json")
        require(prior["generation_seal_id"] == seal["id"], "native support seal changed")
        return prior
    manifest, tasks, lineages = load_public_snapshot(plan["snapshot"])
    require(manifest["id"] == plan["snapshot_id"], "native source snapshot changed")
    refs = _read_snapshot_rows(
        plan["snapshot"], "private.references.jsonl", PrivateReference, manifest
    )
    wanted = set(plan["task_ids"])
    bundles = {
        t.task_id: TaskBundle(public=t, reference=r, lineage=lineage)
        for t, r, lineage in zip(tasks, refs, lineages, strict=True)
        if t.task_id in wanted
    }
    rows, counts, unknown = [], Counter(), Counter()
    for slot in plan["slots"]:
        episode = Episode.model_validate_json(
            (slot_directory(output, slot) / "episode/episode.json").read_bytes()
        )
        score = score_public_reasoning_program(bundles[slot["task_id"]], episode)
        value = score["native"]["execution_accuracy"]
        correct = None if value is None else bool(value)
        counts[slot["task_id"]] += correct is True
        unknown[slot["task_id"]] += correct is None
        rows.append(
            dict(
                slot=slot,
                native=score,
                Q_native=correct,
                V_trace="not_assessed_native_ineligible"
                if correct is not True
                else "not_assessed_pending_review_readiness",
                native_eligibility_reason="native_unknown"
                if correct is None
                else "native_incorrect"
                if not correct
                else "native_correct_pending_trace_review",
            )
        )
    zero = [t for t in plan["task_ids"] if counts[t] == 0 and unknown[t] == 0]
    unresolved = [t for t in plan["task_ids"] if unknown[t]]
    phase = (
        "NATIVE_SCORING_INCOMPLETE"
        if unresolved
        else "KNOWN_ZERO_NATIVE_SUPPORT"
        if zero
        else "NATIVE_COVERAGE_COMPLETE_AWAITING_REVIEW_READINESS"
    )
    report = bound(
        dict(
            schema="v8_native_full_population_support.v1",
            protocol_id=plan["id"],
            generation_seal_id=seal["id"],
            task_denominator=plan["task_denominator"],
            slot_denominator=plan["slot_denominator"],
            phase=phase,
            native_correct_slots=sum(counts.values()),
            native_unknown_slots=sum(unknown.values()),
            support_by_task={
                t: dict(native_correct=counts[t], native_unknown=unknown[t], slots=8)
                for t in plan["task_ids"]
            },
            zero_support_tasks=zero,
            unresolved_native_tasks=unresolved,
            all_1000_native_support_established=not zero and not unresolved,
            rows=rows,
            all_original_failures_retained=True,
            old_stock_spliced=False,
            production_semantic_review_started=False,
            training_admitted=False,
            training_started=False,
            model_reviewed_qualification_claimed=False,
        )
    )
    persist(output / "native_support", report)
    status(
        output,
        dict(
            at=now(),
            protocol_id=plan["id"],
            phase=phase,
            completed=plan["slot_denominator"],
            denominator=plan["slot_denominator"],
            native_support_id=report["id"],
            zero_support_tasks=len(zero),
            budget=ledger.snapshot(),
            training_started=False,
        ),
    )
    return report


async def run(output=OUTPUT, env_file=ENV_FILE):
    output = Path(output)
    plan = checked_plan(output)
    with (output / "controller.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        ledger = ledger_for(plan)
        complete = validate_recovery(output, plan, ledger)
        if len(complete) == plan["slot_denominator"]:
            return score_native_support(output, plan, ledger, _validated_complete=complete)
        key = _key(env_file)
        os.environ.pop("DEEPSEEK_API_KEY", None)
        complete = await collect(output, plan, ledger, key, _validated_complete=complete)
        if complete:
            return score_native_support(output, plan, ledger, _validated_complete=complete)
        return None


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("register", "start", "run", "status"))
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--review-policy", type=Path, default=POLICY)
    parser.add_argument("--representation-preflight", type=Path, default=REPRESENTATION)
    parser.add_argument("--env-file", type=Path, default=ENV_FILE)
    args = parser.parse_args(argv)
    if args.action == "register":
        require(args.review_policy is not None, "explicit frozen review policy file required")
        print(
            dict(
                protocol_id=register(
                    args.output,
                    policy_path=args.review_policy,
                    representation_path=args.representation_preflight,
                )["id"]
            )
        )
    elif args.action == "run":
        asyncio.run(run(args.output, args.env_file))
    elif args.action == "status":
        print(read_json(args.output / "status.json"))
    else:
        plan = checked_plan(args.output)
        validate_recovery(args.output, plan, ledger_for(plan))
        with (args.output / "controller.log").open("ab") as log:
            process = subprocess.Popen(
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
        print(dict(pid=process.pid, process_identity=identity(process.pid), at=now()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
