"""Fixed, budgeted Flash Probe inventory; no automatic task deletion or training.

An explicitly registered task scope receives six train and two sealed slots per
task. The original 1,000 candidates and static exclusions remain visible. Only a
complete fixed-inventory generation seal permits private qualification. Incomplete
requests are never resampled on restart. API bills use a conservative peak-rate
upper bound, not a claim of observing the provider's invoice.
"""

from __future__ import annotations

import argparse
import asyncio
import fcntl
import hashlib
import json
import os
import subprocess
import sys
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict
from multiprocessing import get_context
from pathlib import Path

from .calibration import CACHE, ROOT, identity, now, publish, status
from .cli import _key
from .contracts import Episode, PrivateReference, RunConfig, TaskBundle, digest
from .harness import run_episode
from .planning import task_key, verify_role_plan
from .probe_budget import ProbeBudget, ProbePriceSheet
from .probe_inventory import (
    InventoryIndex,
    freeze_inventory,
    record_slot_result,
    register_inventory,
)
from .probe_provider import BudgetedDeepSeekFlashProvider
from .probe_recovery import ProbeRecoveryError, validate_ledger_recovery
from .probe_scope import build_conditional_scope
from .qualification import qualification_rules
from .settlement import episode_is_complete
from .state_mapping import mapper_rules
from .storage import EventSink, load_public_snapshot, read_json, runtime_binding
from .training_policy import conditional_training_interface_policy, training_interface_policy_v3

OUTPUT = CACHE / "finqa_conditional_probe_inventory_01"
PREVIOUS = CACHE / "reference_revision_01"
OFFICIAL = CACHE / "finqa_probe_preparation_20260928/official_docs_01/snapshot.json"
ENV_FILE = Path("/data1/zhuxinrui/projects/Data-Synthesis/trusted_data_synthesis/.env")
AUDIT = Path(
    "/home/zhuxinrui/.codex/attachments/2b807e15-6d3c-4394-8b79-8557224b3dcd/已粘贴的文本.txt"
)
FROZEN_H1_FILES = ("harness.py", "tools.py", "profiles.py", "providers.py", "native_metrics.py")


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def build_plan(*, source_commit, official_path=OFFICIAL, coverage_acknowledgement):
    if coverage_acknowledgement not in {"full_original_1000", "author_anchored_conditional"}:
        raise ValueError(
            "choose full_original_1000 or a registered author_anchored_conditional scope"
        )
    previous = read_json(PREVIOUS / "protocol.json")
    completion = read_json(PREVIOUS / "complete/record.json")
    if not completion["complete"] or completion["protocol_id"] != previous["id"]:
        raise ValueError("prior H2 must remain sealed complete")
    current = runtime_binding()
    if any(current[name] != previous["runtime_binding"][name] for name in FROZEN_H1_FILES):
        raise ValueError("do not change the frozen H1-R, public profile or native scoring")
    manifest, tasks, lineages = load_public_snapshot(previous["snapshot"])
    verify_role_plan(previous["role_plan"], tasks, lineages)
    roster = [
        task.task_id
        for task in tasks
        if previous["role_plan"]["assignments"][task_key(task)] == "sft"
    ]
    if len(roster) != 1000 or manifest["id"] != previous["snapshot_id"]:
        raise ValueError("preserve the original 1,000 SFT candidates and source snapshot")
    conditional_scope = (
        build_conditional_scope(previous)
        if coverage_acknowledgement == "author_anchored_conditional"
        else None
    )
    if conditional_scope is not None:
        if conditional_scope["original_task_ids"] != roster:
            raise ValueError("conditional scope lost the original task order")
        roster = conditional_scope["task_ids"]
    denominator = len(roster) * 8
    official_path = Path(official_path)
    official = read_json(official_path)
    for document in official["documents"]:
        if _sha(official_path.parent / (document["name"] + ".html")) != document["sha256"]:
            raise ValueError("official tariff evidence changed")
    peak = official["CNY_per_million_tokens"]["peak"]
    price = ProbePriceSheet(
        input_hit_cny_per_million=peak["input_cache_hit"],
        input_miss_cny_per_million=peak["input_cache_miss"],
        output_cny_per_million=peak["output"],
        context_input_token_ceiling=1048576,
        official_max_output_tokens=393216,
        source_url="https://api-docs.deepseek.com/zh-cn/quick_start/pricing/",
        checked_at_utc=official["checked_at_utc"],
        source_sha256=_sha(official_path),
    )
    config = RunConfig(
        harness_id="bigfinance-derived-vtdo-v3",
        submission_profile="finqa_program_v2",
        role="sft",
        temperature=1,
        max_steps=32,
        max_new_tokens=2048,
        context_limit=1048576,
    )
    qualification, mapper = qualification_rules(), mapper_rules()
    collection_policy = dict(
        model="deepseek-flash",
        thinking={"type": "disabled"},
        request_seed_sent=False,
        API_context_reservation=1048576,
        per_response_output_limit=2048,
        local_Student_context_limit_separately_checked=24576,
        max_concurrent_episodes=16,
        qualification_CPU_workers=8,
        request_timeout_seconds=120,
        max_episodes=denominator,
        max_requests=denominator * 32,
        hard_cap_CNY=800,
        warning_CNY=700,
        cost_is_peak_tariff_upper_bound_not_invoice=True,
        network_retries=0,
        hidden_continue_or_repair=False,
        first_registered_slot_serial_transport_admission=True,
        launch_order="slot index first, then original SFT task order; not outcome based",
        unknown_cost_reservation_retained=True,
        sealed_slots_never_enter_training=True,
    )
    collection_policy["id"] = "finqa_probe_collection:" + digest(collection_policy)
    inventory = register_inventory(
        task_ids=roster,
        source_manifest_sha256=_sha(Path(previous["snapshot"]) / "manifest.json"),
        qualification_rule_id=qualification["id"],
        mapper_rule_id=mapper["id"],
        collection_policy_id=collection_policy["id"],
        slot_config=config,
        conditional_scope=conditional_scope,
    )
    ordered = sorted(
        inventory["slots"], key=lambda s: (s["slot_index"], roster.index(s["task_id"]))
    )
    plan = dict(
        schema="finqa_fixed_probe_collection.v1",
        at=now(),
        authorization=(
            "参照审计修订并开展后续实验；API费用700到八百人民币；"
            "先对静态可支持题另行登记条件性研究范围，保留原1000题分母和排除原因"
            if conditional_scope is not None
            else "参照审计修订并开展后续实验；API费用700到八百人民币"
        ),
        audit=dict(path=str(AUDIT), sha256=_sha(AUDIT)),
        static_coverage_acknowledgement=coverage_acknowledgement,
        original_candidate_denominator=1000,
        original_slot_denominator=8000,
        original_1000_training_admitted=False,
        conditional_scope=conditional_scope,
        active_task_denominator=len(roster),
        active_slot_denominator=denominator,
        source_commit=source_commit,
        runtime_binding=current,
        previous_protocol_id=previous["id"],
        frozen_H1_files={n: current[n] for n in FROZEN_H1_FILES},
        snapshot=previous["snapshot"],
        snapshot_id=manifest["id"],
        role_plan=previous["role_plan"],
        task_ids=roster,
        inventory=inventory,
        launch_order=[s["slot_id"] for s in ordered],
        qualification_rules=qualification,
        mapper_rules=mapper,
        collection_policy=collection_policy,
        price_sheet=asdict(price),
        official_snapshot=dict(path=str(official_path), sha256=_sha(official_path)),
        future_training_proposal=(
            conditional_training_interface_policy(conditional_scope)
            if conditional_scope is not None
            else training_interface_policy_v3()
        ),
        automatic_training_authorized=False,
        qualifications_only_after_all_registered_slots_settled=True,
        task_deletion_or_probability_renormalization_allowed=False,
    )
    plan["id"] = digest(plan)
    return plan


def register(output, *, coverage_acknowledgement):
    output = Path(output).resolve()
    if output.exists():
        return checked_plan(output)
    if not coverage_acknowledgement:
        raise ValueError("record the explicit choice about incomplete static semantic coverage")
    if coverage_acknowledgement not in {"full_original_1000", "author_anchored_conditional"}:
        raise ValueError(
            "choose full_original_1000 or author_anchored_conditional with a real roster"
        )
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    for path in sorted(Path(__file__).parent.rglob("*.py")):
        if path.read_bytes() != subprocess.check_output(
            ["git", "show", head + ":" + str(path.relative_to(ROOT))], cwd=ROOT
        ):
            raise ValueError("commit the frozen rules and collector before registering paid calls")
    plan = build_plan(source_commit=head, coverage_acknowledgement=coverage_acknowledgement)
    publish(output, plan, "protocol.json")
    return plan


def _denominator(plan):
    return plan["inventory"]["registered_slot_denominator"]


def checked_plan(output):
    plan = read_json(Path(output) / "protocol.json")
    if plan["id"] != digest({k: v for k, v in plan.items() if k != "id"}):
        raise ValueError("paid collection protocol identity changed")
    if plan["runtime_binding"] != runtime_binding():
        raise ValueError("frozen collector or semantic rules changed; do not silently continue")
    return plan


def ledger_for(output, plan):
    return ProbeBudget(
        Path(output) / "budget.sqlite3",
        run_id=plan["id"],
        price_sheet=ProbePriceSheet(**plan["price_sheet"]),
        max_output_tokens=2048,
        **plan.get("budget_limits", {}),
    )


def slot_directory(output, slot):
    return Path(output) / "slots" / slot["slot_id"].split(":", 1)[1]


def existing_slots(output, plan):
    completed, incomplete = {}, []
    for slot in plan["inventory"]["slots"]:
        directory = slot_directory(output, slot)
        outcome_path = directory / "outcome/record.json"
        if outcome_path.exists():
            row = read_json(outcome_path)
            if row["status"] == "COMPLETE" and (directory / "episode/episode.json").is_file():
                if _sha(directory / "episode/episode.json") != row["episode_file_sha256"]:
                    raise ValueError("completed original Probe bytes changed")
                completed[slot["slot_id"]] = row
            else:
                incomplete.append(slot["slot_id"])
        elif directory.exists():
            incomplete.append(slot["slot_id"])
    return completed, incomplete


_QUAL_BUNDLES, _QUAL_INDEX, _QUAL_PLAN = None, None, None


def _qualification_worker_init(plan):
    """Only called after the all-slot seal; no network client or API key is passed."""
    global _QUAL_BUNDLES, _QUAL_INDEX, _QUAL_PLAN
    _QUAL_PLAN, _QUAL_INDEX = plan, InventoryIndex(plan["inventory"])
    manifest, tasks, lineages = load_public_snapshot(plan["snapshot"])
    wanted = set(plan["task_ids"])
    references = {}
    path = Path(plan["snapshot"]) / "private.references.jsonl"
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != manifest["files"]["private.references.jsonl"]["sha256"]:
        raise ValueError("private reference source changed")
    for line in raw.splitlines():
        value = json.loads(line)
        if value["task_id"] in wanted:
            reference = PrivateReference.model_validate(value)
            references[reference.task_id] = reference
    _QUAL_BUNDLES = {
        task.task_id: TaskBundle(public=task, reference=references[task.task_id], lineage=lineage)
        for task, lineage in zip(tasks, lineages, strict=True)
        if task.task_id in wanted
    }
    if set(_QUAL_BUNDLES) != wanted:
        raise ValueError("the original SFT private references are incomplete")


def _qualify_one(job):
    from .qualification import qualify_episode

    slot, episode_path, expected_sha, output = job
    raw = Path(episode_path).read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected_sha:
        raise ValueError("sealed original Probe changed before qualification")
    episode = Episode.model_validate_json(raw)
    result = qualify_episode(
        _QUAL_BUNDLES[slot["task_id"]],
        episode,
        qualification_rule_id=_QUAL_PLAN["qualification_rules"]["id"],
        mapper_rule_id=_QUAL_PLAN["mapper_rules"]["id"],
    )
    row = record_slot_result(_QUAL_INDEX, slot["slot_id"], episode, result)
    directory = Path(output) / "qualification" / slot["slot_id"].split(":", 1)[1]
    payload = dict(slot_result=row, qualification=result)
    if directory.exists():
        if read_json(directory / "record.json") != payload:
            raise ValueError("qualification reanalysis changed existing results")
    else:
        publish(directory, payload)
    return row


def qualify(output):
    output = Path(output)
    plan = checked_plan(output)
    denominator = _denominator(plan)
    seal = read_json(output / "generation_seal/record.json")
    if (
        seal["id"] != digest({k: v for k, v in seal.items() if k != "id"})
        or seal["protocol_id"] != plan["id"]
        or not seal["complete"]
        or seal["denominator"] != denominator
        or len(seal["slots"]) != denominator
    ):
        raise ValueError("all registered original episodes must be sealed before any qualification")
    validate_ledger_recovery(output, plan)
    ledger = ledger_for(output, plan)
    if ledger.unsettled() or ledger.snapshot()["halt"]:
        raise ValueError("unknown or halted cost ledger prevents qualification")
    slots = plan["inventory"]["slots"]
    completed = {row["slot"]["slot_id"]: row for row in seal["slots"]}
    if set(completed) != {slot["slot_id"] for slot in slots}:
        raise ValueError("collection seal substituted or omitted registered slots")
    jobs = [
        (
            slot,
            completed[slot["slot_id"]]["episode_path"],
            completed[slot["slot_id"]]["episode_file_sha256"],
            str(output),
        )
        for slot in slots
    ]
    status(
        output,
        dict(
            at=now(),
            phase="QUALIFYING",
            denominator=denominator,
            completed=denominator,
            assessed_slots=0,
            automatic_training=False,
            budget=ledger.snapshot(),
        ),
    )
    results = []
    # A spawned CPU verifier must not inherit an API credential from its environment.
    os.environ.pop("DEEPSEEK_API_KEY", None)
    try:
        with ProcessPoolExecutor(
            max_workers=8,
            mp_context=get_context("spawn"),
            initializer=_qualification_worker_init,
            initargs=(plan,),
        ) as pool:
            for row in pool.map(_qualify_one, jobs, chunksize=8):
                results.append(row)
                if len(results) % 100 == 0:
                    status(
                        output,
                        dict(
                            at=now(),
                            phase="QUALIFYING",
                            denominator=denominator,
                            completed=denominator,
                            assessed_slots=len(results),
                            automatic_training=False,
                            budget=ledger.snapshot(),
                        ),
                    )
        frozen = freeze_inventory(InventoryIndex(plan["inventory"]), results)
        if not (output / "inventory_complete").exists():
            publish(output / "inventory_complete", frozen)
        elif read_json(output / "inventory_complete/record.json") != frozen:
            raise ValueError("original frozen inventory changed")
        status(
            output,
            dict(
                at=now(),
                phase="INVENTORY_COMPLETE",
                denominator=denominator,
                completed=denominator,
                assessed_slots=denominator,
                admitted=frozen["admitted"],
                missing_train_task_count=frozen["missing_train_task_count"],
                budget=ledger.snapshot(),
                training_authorized=False,
                Student_encoding_admission_separate=True,
                observed_D_pi=frozen["observed_D_pi"],
                D_pi=frozen["D_pi"],
                M_flex=frozen["M_flex"],
            ),
        )
    except BaseException as error:
        status(
            output,
            dict(
                at=now(),
                phase="QUALIFICATION_BLOCKED",
                denominator=denominator,
                completed=denominator,
                assessed_slots=len(results),
                error_type=type(error).__name__,
                new_model_calls=0,
                budget=ledger.snapshot(),
                automatic_training=False,
            ),
        )
        raise


async def collect(output, env_file=ENV_FILE):
    import httpx

    output = Path(output)
    plan = checked_plan(output)
    denominator = _denominator(plan)
    if (output / "generation_seal/record.json").exists():
        qualify(output)
        return
    completed, unfinished = existing_slots(output, plan)
    try:
        validate_ledger_recovery(output, plan, completed)
    except ProbeRecoveryError as error:
        status(
            output,
            dict(
                at=now(),
                phase="BLOCKED_RECOVERY",
                denominator=denominator,
                completed=len(completed),
                reason=str(error),
                new_model_calls=0,
                automatic_retry=False,
            ),
        )
        return
    ledger = ledger_for(output, plan)
    if unfinished or ledger.unsettled() or ledger.snapshot()["halt"]:
        status(
            output,
            dict(
                at=now(),
                phase="BLOCKED_UNSETTLED",
                denominator=denominator,
                completed=len(completed),
                incomplete_slots=unfinished,
                budget=ledger.snapshot(),
                automatic_retry=False,
            ),
        )
        return
    manifest, tasks, _ = load_public_snapshot(plan["snapshot"])
    if manifest["id"] != plan["snapshot_id"]:
        raise ValueError("source snapshot changed")
    tasks = {task.task_id: task for task in tasks if task.task_id in set(plan["task_ids"])}
    slots = {slot["slot_id"]: slot for slot in plan["inventory"]["slots"]}
    config = RunConfig.model_validate(plan["inventory"]["slot_config"])
    key = _key(env_file)
    os.environ.pop("DEEPSEEK_API_KEY", None)
    halted, blocked, active = asyncio.Event(), [], set()
    monitor_done = asyncio.Event()

    def progress():
        status(
            output,
            dict(
                at=now(),
                protocol_id=plan["id"],
                phase="COLLECTING" if not halted.is_set() else "STOPPING",
                denominator=denominator,
                candidate_tasks=len(plan["task_ids"]),
                original_candidate_tasks=1000,
                scope_id=(plan.get("conditional_scope") or {}).get("scope_id"),
                completed=len(completed),
                pending=denominator - len(completed) - len(active),
                active_slots=sorted(active),
                blocked=blocked,
                budget=ledger.snapshot(),
                private_qualification_started=False,
                automatic_training=False,
            ),
        )

    async def monitor():
        while not monitor_done.is_set():
            progress()
            try:
                await asyncio.wait_for(monitor_done.wait(), 5)
            except TimeoutError:
                pass

    async with httpx.AsyncClient(
        timeout=120,
        trust_env=False,
        follow_redirects=False,
        limits=httpx.Limits(max_connections=16, max_keepalive_connections=16),
    ) as client:

        async def one(slot_id):
            if halted.is_set() or ledger.snapshot()["halt"]:
                halted.set()
                return
            slot, directory = slots[slot_id], slot_directory(output, slots[slot_id])
            active.add(slot_id)
            publish(
                directory / "started",
                dict(
                    at=now(),
                    slot=slot,
                    pid=os.getpid(),
                    process_identity=identity(os.getpid()),
                    attempt=1,
                ),
            )
            provider = BudgetedDeepSeekFlashProvider(
                ledger=ledger,
                api_key=key,
                episode_id=slot_id,
                attempt_index=1,
                client=client,
            )
            try:
                episode = await run_episode(
                    tasks[slot["task_id"]],
                    provider,
                    config,
                    sink=EventSink(directory / "events"),
                    invocation_context={
                        "run_id": plan["id"],
                        "episode_id": slot_id,
                        "attempt_index": 1,
                    },
                )
                publish(directory / "episode", episode.model_dump(mode="json"), "episode.json")
                complete = episode_is_complete(episode)
                row = dict(
                    status="COMPLETE" if complete else "BLOCKED",
                    at=now(),
                    slot=slot,
                    episode_sha256=digest(episode),
                    episode_file_sha256=_sha(directory / "episode/episode.json"),
                    episode_path=str(directory / "episode/episode.json"),
                    actual_model_calls=episode.actual_model_calls,
                    all_provider_calls_settled=episode.all_provider_calls_settled,
                    stop_reason=episode.stop_reason,
                )
                publish(directory / "outcome", row)
                if complete:
                    completed[slot_id] = row
                else:
                    blocked.append({"slot_id": slot_id, "stop_reason": episode.stop_reason})
                    halted.set()
            except BaseException as error:
                # Do not expose raw credential-bearing transport object reprs.
                row = dict(
                    status="BLOCKED",
                    at=now(),
                    slot=slot,
                    error_type=type(error).__name__,
                    automatic_retry=False,
                )
                if not (directory / "outcome").exists():
                    publish(directory / "outcome", row)
                blocked.append({"slot_id": slot_id, "error_type": type(error).__name__})
                halted.set()
            finally:
                active.discard(slot_id)

        watching = asyncio.create_task(monitor())
        pending = [s for s in plan["launch_order"] if s not in completed]
        try:
            # This is the first real registered slot, not an extra model pilot or quality gate.
            if not completed and pending:
                await one(pending.pop(0))
            queue = asyncio.Queue()
            for slot_id in pending:
                queue.put_nowait(slot_id)

            async def worker():
                while not halted.is_set() and not queue.empty():
                    try:
                        slot_id = queue.get_nowait()
                    except asyncio.QueueEmpty:
                        return
                    await one(slot_id)
                    queue.task_done()

            await asyncio.gather(*(worker() for _ in range(16)))
        finally:
            monitor_done.set()
            await watching
    budget = ledger.snapshot()
    if (
        len(completed) != denominator
        or budget["unknown_requests"]
        or budget["pending_requests"]
        or budget["halt"]
    ):
        status(
            output,
            dict(
                at=now(),
                phase="INCOMPLETE",
                denominator=denominator,
                completed=len(completed),
                not_completed=denominator - len(completed),
                blocked=blocked,
                budget=budget,
                private_qualification_started=False,
                support_freeze_performed=False,
                automatic_training=False,
            ),
        )
        return
    validate_ledger_recovery(output, plan, completed)
    seal = dict(
        schema="finqa_probe_generation_seal.v1",
        at=now(),
        protocol_id=plan["id"],
        complete=True,
        denominator=denominator,
        candidate_tasks=len(plan["task_ids"]),
        original_candidate_tasks=1000,
        scope_id=(plan.get("conditional_scope") or {}).get("scope_id"),
        all_API_requests_settled=True,
        private_qualification_started=False,
        budget=budget,
        slots=[completed[s["slot_id"]] for s in plan["inventory"]["slots"]],
    )
    seal["id"] = digest(seal)
    publish(output / "generation_seal", seal)
    status(
        output,
        dict(
            at=now(),
            phase="GENERATION_COMPLETE",
            denominator=denominator,
            completed=denominator,
            budget=budget,
            private_qualification_started=False,
            automatic_training=False,
        ),
    )
    qualify(output)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("register", "start", "run", "qualify", "status"))
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--env-file", type=Path, default=ENV_FILE)
    parser.add_argument("--coverage-acknowledgement", default="")
    args = parser.parse_args(argv)
    if args.action == "register":
        print(
            {
                "id": register(args.output, coverage_acknowledgement=args.coverage_acknowledgement)[
                    "id"
                ]
            }
        )
    elif args.action == "run":
        with (args.output / "collector.lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            asyncio.run(collect(args.output, args.env_file))
    elif args.action == "status":
        print(read_json(args.output / "status.json"))
    elif args.action == "qualify":
        with (args.output / "collector.lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            qualify(args.output)
    else:
        checked_plan(args.output)
        with (args.output / "collector.log").open("ab") as log:
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
