"""V6 Experiment 0: sealed real public trajectories, two reviews, one paid cap.

This is a new original-1000 inventory, not a legacy 6+2 or conditional retry.
No training, GPU hold, outcome-driven top-up, or paid request retry is performed.
"""

from __future__ import annotations

import argparse
import asyncio
import fcntl
import hashlib
import json
import math
import os
import sqlite3
import subprocess
import sys
from collections import Counter
from dataclasses import asdict
from pathlib import Path

from .calibration import CACHE, ROOT, identity, now, publish, status
from .cli import _key
from .contracts import Episode, PrivateReference, RunConfig, TaskBundle, digest, invocation_identity
from .harness import episode_tool_specs, public_initial_messages, run_episode
from .planning import task_key, verify_role_plan
from .probe_budget import V6_PURPOSE, ProbeBudget, ProbePriceSheet
from .probe_collection import ENV_FILE, existing_slots, slot_directory
from .probe_provider import BudgetedDeepSeekFlashProvider
from .probe_recovery import _validate_turn
from .providers import _api_messages, canonical_assistant_message
from .semantic_review import (
    audit_packet,
    resolve_pair,
    review_request,
    review_rubric,
    validate_review,
)
from .settlement import episode_is_complete
from .storage import EventSink, load_public_snapshot, read_json, runtime_binding
from .v6_task import PublicProgramSession, public_trajectory_view, score_public_reasoning_program

STUDY = CACHE / "finqa_v6_01"
OUTPUT = STUDY / "experiment0_01"
OFFICIAL = STUDY / "official_docs_01/snapshot.json"
AUDIT = Path(
    "/home/zhuxinrui/.codex/attachments/a8d52978-a220-40a7-abee-ae7d084d7f01/已粘贴的文本.txt"
)
LIMITS = dict(hard_cap_microcny=800_000_000, warning_microcny=700_000_000, request_cap=258000)
PAID_TRACES = (
    "slots",
    "generation_seal",
    "reviews",
    "assessment",
    "review_seal",
    "inventory_complete",
    "budget.sqlite3-wal",
    "budget.sqlite3-shm",
)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def require(value, message):
    if not value:
        raise ValueError(message)


def bound(value):
    return {**value, "id": digest(value)}


def persist(directory, value, name="record.json"):
    path = Path(directory) / name
    if path.exists():
        require(read_json(path) == value, "immutable artifact differs: " + str(path))
    else:
        publish(directory, value, name)


def build_plan(source_commit):
    previous = read_json(CACHE / "reference_revision_01/protocol.json")
    manifest, tasks, lineages = load_public_snapshot(previous["snapshot"])
    verify_role_plan(previous["role_plan"], tasks, lineages)
    roster = [
        t.task_id for t in tasks if previous["role_plan"]["assignments"][task_key(t)] == "sft"
    ]
    require(len(roster) == len(set(roster)) == 1000, "original 1000 SFT tasks required")
    require(manifest["id"] == previous["snapshot_id"], "original QA snapshot changed")
    official = read_json(OFFICIAL)
    for doc in official["documents"]:
        require(sha(OFFICIAL.parent / (doc["name"] + ".html")) == doc["sha256"], "tariff changed")
    peak = official["CNY_per_million_tokens"]["peak"]
    price = ProbePriceSheet(
        input_hit_cny_per_million=peak["input_cache_hit"],
        input_miss_cny_per_million=peak["input_cache_miss"],
        output_cny_per_million=peak["output"],
        context_input_token_ceiling=1048576,
        official_max_output_tokens=393216,
        source_url="https://api-docs.deepseek.com/zh-cn/quick_start/pricing/",
        checked_at_utc=official["checked_at_utc"],
        source_sha256=sha(OFFICIAL),
    )
    config = RunConfig(
        harness_id="bigfinance-derived-vtdo-v6",
        submission_profile="finqa-public-reasoning-v1",
        role="sft",
        temperature=1,
        max_steps=32,
        max_new_tokens=2048,
        context_limit=1048576,
    )
    scope = digest(
        dict(
            task_ids=roster,
            config=config.model_dump(mode="json"),
            audit_sha256=sha(AUDIT),
            version="V6",
        )
    )
    slots = [
        dict(
            task_id=task,
            slot_index=index,
            purpose="common_material_candidate",
            slot_id="v6-slot:" + digest(dict(scope=scope, task=task, index=index)),
        )
        for task in roster
        for index in range(8)
    ]
    task_order = {task: i for i, task in enumerate(roster)}
    return bound(
        dict(
            schema="finqa_v6_experiment0.v1",
            at=now(),
            source_commit=source_commit,
            authorization={
                "new_combined_hard_cap_CNY": 800,
                "warning_CNY": 700,
                "all_eight_slots_common_candidates": True,
                "user_confirmation": "确认，合计800元上限；8个均为共同材料候选",
            },
            audit={"path": str(AUDIT), "sha256": sha(AUDIT)},
            runtime_binding=runtime_binding(),
            snapshot=previous["snapshot"],
            snapshot_id=manifest["id"],
            role_plan=previous["role_plan"],
            assets=previous["assets"],
            task_ids=roster,
            inventory={
                "slots": slots,
                "slot_config": config.model_dump(mode="json"),
                "registered_slot_denominator": 8000,
                "task_denominator": 1000,
                "train_slots_per_task": 8,
                "sealed_diagnostic_slots_per_task": 0,
            },
            launch_order=[
                s["slot_id"]
                for s in sorted(slots, key=lambda s: (s["slot_index"], task_order[s["task_id"]]))
            ],
            price_sheet=asdict(price),
            budget_limits=LIMITS,
            budget_purpose=V6_PURPOSE,
            official_snapshot={"path": str(OFFICIAL), "sha256": sha(OFFICIAL)},
            collection={
                "model": "deepseek-flash",
                "thinking": "disabled",
                "concurrency": 16,
                "first_registered_slot_serial_transport_check": True,
                "hidden_retry_repair_topup": False,
                "slot_outcome_quality_gate": False,
                "all_8000_settled_before_private_reference_or_review": True,
            },
            review={
                "model": "deepseek-flash",
                "temperature": 0,
                "top_p": 1,
                "max_tokens": 16384,
                "response_format": "json_object",
                "thinking": "disabled",
                "concurrency": 8,
                "fixed_requests": 2000,
                "unit": "one task's eight sealed trajectories; two isolated review contexts",
                "each_original_trajectory_review_count": 2,
                "rubric_sha256": [digest(review_rubric(i)) for i in (0, 1)],
                "same_model_reviews_statistically_independent": False,
                "format_failure_or_disagreement": "unknown; no repair, retry, third review",
                "human_audit_task_ids": roster[:10],
                "human_reviewed": False,
                "consensus_is_mathematical_proof": False,
            },
            downstream={
                "five_arms": ["Static", "Manual+", "Manual-", "C-only", "Full"],
                "seeds": [11, 29, 47],
                "original_1000_full_support_required": True,
                "all_valid_originals_retained": True,
                "empirical_kernel": "1/n_xz",
                "prior": "n_xz/n_x",
                "context_limit": 24576,
                "long_package_policy": "block; never truncate or delete",
                "automatic_training_in_this_controller": False,
                "training_implementation_status": "not launched; admission pending",
                "no_GPU_reservation": True,
            },
        )
    )


def register(output):
    output = Path(output)
    if output.exists():
        return checked_plan(output)
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    for path in sorted(Path(__file__).parent.rglob("*.py")):
        relative = str(path.relative_to(ROOT))
        require(
            path.read_bytes()
            == subprocess.check_output(["git", "show", head + ":" + relative], cwd=ROOT),
            "commit frozen source before paid registration",
        )
    plan = build_plan(head)
    publish(output, plan, "protocol.json")
    return plan


def checked_plan(output):
    plan = read_json(Path(output) / "protocol.json")
    require(plan["id"] == digest({k: v for k, v in plan.items() if k != "id"}), "protocol changed")
    require(plan["runtime_binding"] == runtime_binding(), "frozen V6 runtime changed")
    return plan


def ledger_for(output, plan):
    path = Path(output) / "budget.sqlite3"
    if not path.exists():
        require(
            not any((Path(output) / n).exists() for n in PAID_TRACES),
            "original paid ledger missing; never reset the budget",
        )
    return ProbeBudget(
        path,
        run_id=plan["id"],
        price_sheet=plan["price_sheet"],
        max_output_tokens=16384,
        purpose=V6_PURPOSE,
        **plan["budget_limits"],
    )


def review_id(plan, task_id, reviewer):
    return "v6-review:" + digest(dict(run_id=plan["id"], task_id=task_id, reviewer=reviewer))


def review_directory(output, rid):
    return Path(output) / "reviews" / rid.split(":", 1)[1]


def task_directory(output, task_id):
    return Path(output) / "assessment" / digest(task_id)


def checked_prepared(output, task_id):
    prepared = read_json(task_directory(output, task_id) / "prepared/record.json")
    require(
        prepared["id"] == digest({k: v for k, v in prepared.items() if k != "id"}),
        "sealed review preparation changed",
    )
    require(prepared["bundle"]["task_id"] == task_id, "review preparation task changed")
    for reviewer, request in enumerate(prepared["requests"]):
        require(
            request["reviewer"] == reviewer
            and request["task_bundle_sha256"] == digest(prepared["bundle"])
            and request["rubric_sha256"] == digest(review_rubric(reviewer)),
            "review preparation/rubric identity changed",
        )
    return prepared


def validate_recovery(output, plan):
    """One quiescent conservation check; no retry, DB creation or cost reconstruction."""
    output = Path(output)
    completed, unfinished = existing_slots(output, plan)
    require(not unfinished, "incomplete original slots require explicit disposition; no resampling")
    database = output / "budget.sqlite3"
    if not database.exists():
        require(
            not completed and not any((output / n).exists() for n in PAID_TRACES),
            "paid evidence exists without its original ledger",
        )
        return completed, {}
    sheet = ProbePriceSheet(**plan["price_sheet"])
    seen, spent = set(), 0
    totals = Counter()
    reviews = {}
    with sqlite3.connect(database.resolve().as_uri() + "?mode=ro", uri=True) as connection:
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA query_only=ON")
        config = json.loads(
            connection.execute("SELECT value FROM metadata WHERE key='config'").fetchone()[0]
        )
        require(
            all(
                config.get(k) == v
                for k, v in dict(
                    run_id=plan["id"],
                    purpose=V6_PURPOSE,
                    price_sheet=plan["price_sheet"],
                    max_output_tokens=16384,
                    allowed_output_limits=[2048, 16384],
                    **plan["budget_limits"],
                ).items()
            ),
            "joint ledger configuration changed",
        )
        require(
            connection.execute("SELECT value FROM metadata WHERE key='halt'").fetchone() is None,
            "halted ledger cannot automatically resume",
        )
        states = list(connection.execute("SELECT invocation_id,state FROM requests"))
        require(all(r["state"] == "SETTLED" for r in states), "unsettled/unknown paid invocation")

        def tally(iid, amount, usage):
            nonlocal spent
            require(iid not in seen, "paid invocation reused")
            seen.add(iid)
            spent += amount
            totals.update(
                {
                    k: usage[k]
                    for k in (
                        "prompt_tokens",
                        "prompt_cache_hit_tokens",
                        "prompt_cache_miss_tokens",
                        "completion_tokens",
                    )
                }
            )

        for slot in plan["inventory"]["slots"]:
            if slot["slot_id"] not in completed:
                continue
            outcome = completed[slot["slot_id"]]
            path = slot_directory(output, slot) / "episode/episode.json"
            episode = Episode.model_validate_json(path.read_bytes())
            require(
                outcome["slot"] == slot
                and digest(episode) == outcome["episode_sha256"]
                and episode_is_complete(episode)
                and episode.task_id == slot["task_id"]
                and episode.config.model_dump(mode="json") == plan["inventory"]["slot_config"]
                and episode.actual_model_calls == episode.provider_attempts == len(episode.turns),
                "original slot/configuration/settlement mismatch",
            )
            for index, turn in enumerate(episode.turns):
                tally(
                    *_validate_turn(
                        connection,
                        turn=turn,
                        index=index,
                        slot_id=slot["slot_id"],
                        plan=plan,
                        sheet=sheet,
                        output_limit=2048,
                        reservation=sheet.cost_microcny(hit=0, miss=1048576, output=2048),
                    )
                )
        for task_id in plan["task_ids"]:
            for reviewer in (0, 1):
                rid = review_id(plan, task_id, reviewer)
                directory = review_directory(output, rid)
                if not directory.exists():
                    continue
                require(
                    (directory / "response/record.json").is_file(),
                    "unfinished review cannot be resent",
                )
                artifact = read_json(directory / "response/record.json")
                coordinates = invocation_identity(
                    dict(run_id=plan["id"], episode_id=rid, attempt_index=1), turn_index=0
                )
                iid = coordinates["invocation_id"]
                row = connection.execute(
                    "SELECT * FROM requests WHERE invocation_id=?", (iid,)
                ).fetchone()
                request = artifact["public_request"]
                require(
                    row is not None
                    and row["state"] == "SETTLED"
                    and row["response_classification"] == "model_response"
                    and row["dispatched_at"] is not None
                    and 200 <= row["http_status"] < 300
                    and json.loads(row["coordinates_json"])
                    == coordinates
                    == artifact["budget_coordinates"]
                    and iid == artifact["budget_invocation_id"],
                    "review ledger coordinates/settlement mismatch",
                )
                require(
                    digest(request)
                    == row["request_sha256"]
                    == artifact["request_sha256"]
                    == hashlib.sha256(row["request_body"]).hexdigest()
                    and row["response_body"] == artifact["api_response_raw"].encode()
                    and hashlib.sha256(row["response_body"]).hexdigest()
                    == row["response_sha256"]
                    == artifact["raw_api_response_sha256"],
                    "original review request/response changed",
                )
                response = json.loads(row["response_body"])
                prepared = checked_prepared(output, task_id)
                semantic_request = prepared["requests"][reviewer]
                choices = response.get("choices", [])
                require(
                    len(choices) == 1
                    and artifact["content"] == choices[0]["message"].get("content")
                    and artifact["finish_reason"] == choices[0].get("finish_reason"),
                    "review content/finish differs from paid original response",
                )
                require(
                    response == artifact["api_response"]
                    and request["model"] == response["model"] == "deepseek-flash"
                    and request["max_tokens"] == 16384
                    and request["temperature"] == 0
                    and request["top_p"] == 1
                    and request["stream"] is False
                    and request["response_format"] == {"type": "json_object"}
                    and request["thinking"] == {"type": "disabled"}
                    and artifact["reviewer"] == reviewer
                    and request["messages"] == semantic_request["messages"]
                    and artifact["semantic_review_request_sha256"] == digest(semantic_request)
                    and artifact["task_bundle_sha256"] == digest(prepared["bundle"])
                    and artifact["rubric_sha256"] == digest(review_rubric(reviewer)),
                    "review model/decoder mismatch",
                )
                usage = response["usage"]
                counters = sheet.usage(usage, output_limit=16384)
                amount = sheet.cost_microcny(
                    hit=counters["prompt_cache_hit_tokens"],
                    miss=counters["prompt_cache_miss_tokens"],
                    output=counters["completion_tokens"],
                )
                require(
                    json.loads(row["usage_json"]) == artifact["usage"] == usage
                    and row["settled_microcny"]
                    == amount
                    == artifact["peak_tariff_upper_bound_microcny"]
                    and row["reserved_microcny"]
                    == artifact["budget_reserved_microcny"]
                    == sheet.cost_microcny(hit=0, miss=1048576, output=16384)
                    and artifact["price_sheet_id"] == sheet.id,
                    "review fee mismatch",
                )
                tally(iid, amount, counters)
                reviews[rid] = artifact
        require(
            seen == {r["invocation_id"] for r in states},
            "orphan/missing paid calls; never silently repeat",
        )
        counters = connection.execute("SELECT * FROM counters WHERE singleton=1").fetchone()
        expected = dict(
            requests=len(seen),
            dispatched=len(seen),
            spent=spent,
            held=0,
            unknown=0,
            pending=0,
            prompt_tokens=totals["prompt_tokens"],
            hit_tokens=totals["prompt_cache_hit_tokens"],
            miss_tokens=totals["prompt_cache_miss_tokens"],
            completion_tokens=totals["completion_tokens"],
        )
        require(
            counters is not None and all(counters[k] == v for k, v in expected.items()),
            "joint ledger counters do not conserve evidence",
        )
        require(
            spent <= LIMITS["hard_cap_microcny"] and len(seen) <= LIMITS["request_cap"],
            "joint budget exceeded",
        )
    if (output / "generation_seal/record.json").exists():
        seal = read_json(output / "generation_seal/record.json")
        require(
            seal["id"] == digest({k: v for k, v in seal.items() if k != "id"})
            and seal["protocol_id"] == plan["id"]
            and len(completed) == seal["denominator"] == 8000
            and {r["slot"]["slot_id"]: r for r in seal["slots"]} == completed,
            "full generation seal changed",
        )
    else:
        require(not reviews, "reviews cannot precede full generation seal")
    if (output / "review_seal/record.json").exists():
        seal = read_json(output / "review_seal/record.json")
        require(
            seal["id"] == digest({k: v for k, v in seal.items() if k != "id"})
            and seal["protocol_id"] == plan["id"]
            and seal["denominator"] == len(reviews) == 2000
            and seal["reviews"] == {rid: digest(row) for rid, row in sorted(reviews.items())},
            "fixed review seal changed",
        )
    return completed, reviews


def mechanical_check(task, episode, slot, plan):
    """Replay original public inputs, actual tool events and retained failure history."""
    scope = dict(run_id=plan["id"], episode_id=slot["slot_id"], attempt_index=1)
    history = public_initial_messages(task, episode.config)
    session = PublicProgramSession(task, invocation_context=scope)
    checks = dict(
        sealed=True,
        calls_settled=episode.all_provider_calls_settled,
        history_complete=False,
        actions_observations_bound=False,
        private_reference_isolated=False,
        native_correct=None,
    )
    event_index = 0
    for index, turn in enumerate(episode.turns):
        request = turn.provider_metadata["public_request"]
        if request["messages"] != _api_messages(history) or request.get(
            "tools"
        ) != episode_tool_specs(episode.config):
            return checks
        history.append(canonical_assistant_message(turn))
        if len(turn.tool_calls) == 1:
            if event_index >= len(episode.tool_events):
                return checks
            call = turn.tool_calls[0]
            event = session.execute(
                call,
                invocation_id=invocation_identity(scope, turn_index=index, tool_index=0)[
                    "invocation_id"
                ],
            )
            if event != episode.tool_events[event_index]:
                return checks
            event_index += 1
            history.append(
                dict(role="tool", tool_call_id=call.call_id, content=event.visible_output)
            )
        elif index != len(episode.turns) - 1:
            return checks
    exact = list(episode.messages) == history and event_index == len(episode.tool_events)
    return {
        **checks,
        "history_complete": exact,
        "actions_observations_bound": exact,
        "private_reference_isolated": exact,
    }


async def collect(output, plan, ledger, key):
    import httpx

    completed, _ = validate_recovery(output, plan)
    if (output / "generation_seal/record.json").exists():
        return True
    manifest, tasks, _ = load_public_snapshot(plan["snapshot"])
    require(manifest["id"] == plan["snapshot_id"], "source changed")
    wanted = set(plan["task_ids"])
    tasks = {t.task_id: t for t in tasks if t.task_id in wanted}
    slots = {s["slot_id"]: s for s in plan["inventory"]["slots"]}
    config = RunConfig.model_validate(plan["inventory"]["slot_config"])
    active, blocked = set(), []
    halted, done = asyncio.Event(), asyncio.Event()

    def progress(phase=None):
        status(
            output,
            dict(
                at=now(),
                protocol_id=plan["id"],
                phase=phase or "GENERATING",
                completed=len(completed),
                denominator=8000,
                active=len(active),
                blocked=blocked,
                budget=ledger.snapshot(),
                private_review_started=False,
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

    async with httpx.AsyncClient(
        timeout=120,
        trust_env=False,
        follow_redirects=False,
        limits=httpx.Limits(max_connections=16, max_keepalive_connections=16),
    ) as client:

        async def one(sid):
            if halted.is_set() or ledger.snapshot()["halt"]:
                halted.set()
                return
            slot = slots[sid]
            directory = slot_directory(output, slot)
            active.add(sid)
            publish(directory / "started", dict(at=now(), slot=slot, attempt=1))
            provider = BudgetedDeepSeekFlashProvider(
                ledger=ledger, api_key=key, episode_id=sid, client=client
            )
            try:
                episode = await run_episode(
                    tasks[slot["task_id"]],
                    provider,
                    config,
                    sink=EventSink(directory / "events"),
                    invocation_context=dict(run_id=plan["id"], episode_id=sid, attempt_index=1),
                )
                publish(directory / "episode", episode.model_dump(mode="json"), "episode.json")
                complete = episode_is_complete(episode)
                row = dict(
                    status="COMPLETE" if complete else "BLOCKED",
                    at=now(),
                    slot=slot,
                    episode_sha256=digest(episode),
                    episode_file_sha256=sha(directory / "episode/episode.json"),
                    episode_path=str(directory / "episode/episode.json"),
                    actual_model_calls=episode.actual_model_calls,
                    all_provider_calls_settled=episode.all_provider_calls_settled,
                    stop_reason=episode.stop_reason,
                )
                publish(directory / "outcome", row)
                if complete:
                    completed[sid] = row
                else:
                    blocked.append(dict(slot_id=sid, reason=episode.stop_reason))
                    halted.set()
            except BaseException as error:
                row = dict(
                    status="BLOCKED",
                    at=now(),
                    slot=slot,
                    error_type=type(error).__name__,
                    automatic_retry=False,
                )
                if not (directory / "outcome").exists():
                    publish(directory / "outcome", row)
                blocked.append(dict(slot_id=sid, error_type=type(error).__name__))
                halted.set()
                if not isinstance(error, Exception):
                    raise
            finally:
                active.discard(sid)

        watcher = asyncio.create_task(monitor())
        pending = [sid for sid in plan["launch_order"] if sid not in completed]
        try:
            if not completed and pending:
                await one(pending.pop(0))
            queue = asyncio.Queue()
            for sid in pending:
                queue.put_nowait(sid)

            async def worker():
                while not halted.is_set():
                    try:
                        sid = queue.get_nowait()
                    except asyncio.QueueEmpty:
                        return
                    await one(sid)

            await asyncio.gather(*(worker() for _ in range(16)))
        finally:
            done.set()
            await watcher
    if len(completed) != 8000 or ledger.unsettled() or ledger.snapshot()["halt"]:
        progress("GENERATION_INCOMPLETE")
        return False
    validate_recovery(output, plan)
    publish(
        output / "generation_seal",
        bound(
            dict(
                schema="v6_generation_seal.v1",
                at=now(),
                protocol_id=plan["id"],
                denominator=8000,
                private_review_started=False,
                budget=ledger.snapshot(),
                slots=[completed[s["slot_id"]] for s in plan["inventory"]["slots"]],
            )
        ),
    )
    progress("GENERATION_COMPLETE")
    return True


def prepare_reviews(output, plan):
    """Private references first opened only after the full paid generation barrier."""
    completed, _ = validate_recovery(output, plan)
    require(
        len(completed) == 8000 and (output / "generation_seal/record.json").exists(),
        "full seal required",
    )
    seal = read_json(output / "generation_seal/record.json")
    manifest, tasks, lineages = load_public_snapshot(plan["snapshot"])
    wanted = set(plan["task_ids"])
    path = Path(plan["snapshot"]) / "private.references.jsonl"
    require(
        sha(path) == manifest["files"]["private.references.jsonl"]["sha256"],
        "private source changed",
    )
    # All-file hash covers source bytes; only registered SFT objects become references.
    references = {}
    for line in path.read_bytes().splitlines():
        value = json.loads(line)
        if value["task_id"] in wanted:
            references[value["task_id"]] = PrivateReference.model_validate(value)
    bundles = {
        t.task_id: TaskBundle(public=t, reference=references[t.task_id], lineage=lineage)
        for t, lineage in zip(tasks, lineages, strict=True)
        if t.task_id in wanted
    }
    grouped = {task_id: [] for task_id in plan["task_ids"]}
    for slot in plan["inventory"]["slots"]:
        grouped[slot["task_id"]].append(slot)
    for task_id in plan["task_ids"]:
        directory = task_directory(output, task_id)
        if (directory / "prepared/record.json").exists():
            checked_prepared(output, task_id)
            continue
        bundle = bundles[task_id]
        views, mechanical, scores = [], {}, {}
        for slot in grouped[task_id]:
            episode = Episode.model_validate_json(
                Path(completed[slot["slot_id"]]["episode_path"]).read_bytes()
            )
            views.append(
                dict(
                    slot_id=slot["slot_id"],
                    trajectory=public_trajectory_view(episode, slot_id=slot["slot_id"]),
                )
            )
            checks = mechanical_check(bundle.public, episode, slot, plan)
            score = score_public_reasoning_program(bundle, episode)
            value = score["native"]["execution_accuracy"]
            checks["native_correct"] = None if value is None else bool(value)
            mechanical[slot["slot_id"]], scores[slot["slot_id"]] = checks, score
        view = dict(
            schema="v6_task_review_bundle.v1", task_id=task_id, seal_id=seal["id"], slots=views
        )
        payload = bound(
            dict(
                bundle=view,
                mechanical=mechanical,
                native_scores=scores,
                requests=[review_request(view, bundle.reference, i) for i in (0, 1)],
            )
        )
        persist(directory / "prepared", payload)


def unknown_resolution(prepared, errors):
    return dict(
        schema="v6_semantic_pair_resolution.v1",
        task_mapping="incomplete",
        all_eight_candidates_retained=True,
        valid_slots_retained=[],
        human_reviewed=False,
        mathematical_proof=False,
        review_errors=errors,
        slots={
            sid: dict(
                v_trace="unknown",
                q_native=checks["native_correct"],
                mapper="unknown",
                state_id=None,
                chi=None,
                mask_status="unknown",
                encoding_manifest=None,
            )
            for sid, checks in prepared["mechanical"].items()
        },
    )


async def review_all(output, plan, ledger, key):
    import httpx

    from .v6_review_provider import request_review

    prepare_reviews(output, plan)
    _, completed = validate_recovery(output, plan)
    halted, done = asyncio.Event(), asyncio.Event()
    blocked = []

    def progress(phase="REVIEWING"):
        status(
            output,
            dict(
                at=now(),
                protocol_id=plan["id"],
                phase=phase,
                completed=8000,
                denominator=8000,
                review_completed=len(completed),
                review_denominator=2000,
                blocked=blocked,
                budget=ledger.snapshot(),
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

    queue = asyncio.Queue()
    for task_id in plan["task_ids"]:
        for reviewer in (0, 1):
            if review_id(plan, task_id, reviewer) not in completed:
                queue.put_nowait((task_id, reviewer))
    async with httpx.AsyncClient(
        timeout=240,
        trust_env=False,
        follow_redirects=False,
        limits=httpx.Limits(max_connections=8, max_keepalive_connections=8),
    ) as client:

        async def worker():
            while not halted.is_set():
                try:
                    task_id, reviewer = queue.get_nowait()
                except asyncio.QueueEmpty:
                    return
                rid = review_id(plan, task_id, reviewer)
                directory = review_directory(output, rid)
                prepared = checked_prepared(output, task_id)
                publish(
                    directory / "started",
                    dict(at=now(), review_id=rid, task_id=task_id, reviewer=reviewer),
                )
                try:
                    response = await request_review(
                        ledger=ledger,
                        api_key=key,
                        episode_id=rid,
                        request=prepared["requests"][reviewer],
                        client=client,
                        timeout=240,
                    )
                    publish(directory / "response", response)
                    completed[rid] = response
                except BaseException as error:
                    publish(
                        directory / "blocked",
                        dict(at=now(), error_type=type(error).__name__, automatic_retry=False),
                    )
                    blocked.append(dict(review_id=rid, error_type=type(error).__name__))
                    halted.set()
                    if not isinstance(error, Exception):
                        raise

        watcher = asyncio.create_task(monitor())
        try:
            await asyncio.gather(*(worker() for _ in range(8)))
        finally:
            done.set()
            await watcher
    if len(completed) != 2000 or ledger.unsettled() or ledger.snapshot()["halt"]:
        progress("REVIEW_INCOMPLETE")
        return False
    validate_recovery(output, plan)
    persist(
        output / "review_seal",
        bound(
            dict(
                protocol_id=plan["id"],
                denominator=2000,
                reviews={rid: digest(value) for rid, value in sorted(completed.items())},
                budget=ledger.snapshot(),
            )
        ),
    )
    progress("REVIEWS_COMPLETE")
    return True


def finalize(output, plan, ledger):
    """Resolve only after all fixed reviews; never select/rewrite original packages."""
    _, reviews = validate_recovery(output, plan)
    require(
        len(reviews) == 2000 and (output / "review_seal/record.json").exists(),
        "full fixed reviews required",
    )
    counts, task_rows = Counter(), []
    for task_id in plan["task_ids"]:
        prepared = checked_prepared(output, task_id)
        validated, errors = [], []
        for reviewer in (0, 1):
            request = prepared["requests"][reviewer]
            response = reviews[review_id(plan, task_id, reviewer)]
            try:
                require(response["finish_reason"] == "stop", "review output not a completed stop")
                value = validate_review(
                    response["content"],
                    request["document_index"],
                    expected_reviewer=reviewer,
                    expected_bundle_sha256=request["task_bundle_sha256"],
                )
                validated.append(value)
            except (ValueError, TypeError, KeyError) as error:
                errors.append(
                    dict(reviewer=reviewer, reason=str(error)[:1000], type=type(error).__name__)
                )
        resolution = (
            unknown_resolution(prepared, errors)
            if errors
            else resolve_pair(*validated, prepared["mechanical"])
        )
        persist(task_directory(output, task_id) / "resolution", resolution)
        if task_id in plan["review"]["human_audit_task_ids"]:
            persist(
                task_directory(output, task_id) / "pending_human_audit",
                audit_packet(prepared["bundle"], resolution),
            )
        values = list(resolution["slots"].values())
        counts.update(v["v_trace"] for v in values)
        counts["native_correct"] += sum(v["q_native"] is True for v in values)
        valid = [v for v in values if v["v_trace"] == "valid" and v["q_native"] is True]
        counts["joint_valid"] += len(valid)
        mapped = bool(valid) and resolution["task_mapping"] == "complete"
        states = Counter(v["state_id"] for v in valid) if mapped else Counter()
        n = sum(states.values())
        masks = all(v["encoding_manifest"] is not None for v in valid)
        task_rows.append(
            dict(
                task_id=task_id,
                candidates=8,
                valid=len(valid),
                process_valid=sum(v["v_trace"] == "valid" for v in values),
                mapping_complete=mapped,
                agreed_masks=masks,
                states=dict(states),
                n_x=n,
                r={s: count / n for s, count in states.items()},
                K_per_original={s: 1 / count for s, count in states.items()},
                conditional_state_entropy=(
                    -sum(count / n * math.log(count / n) for count in states.values())
                    if n
                    else None
                ),
                singleton_states=sum(count == 1 for count in states.values()),
                D_pi=max(0, len(states) - 1) if mapped else None,
            )
        )
    supported = [t for t in task_rows if t["mapping_complete"]]
    full_support = len(supported) == 1000
    summary = bound(
        dict(
            schema="v6_experiment0_inventory.v1",
            protocol_id=plan["id"],
            original_tasks=1000,
            original_slots=8000,
            completed_slots=8000,
            completed_review_requests=2000,
            counts=dict(counts),
            tasks=task_rows,
            validity_yield=counts["joint_valid"] / 8000,
            process_validity_yield=counts["valid"] / 8000,
            supported_task_count=len(supported),
            missing_or_unmapped_task_ids=[
                t["task_id"] for t in task_rows if not t["mapping_complete"]
            ],
            observed_D_pi=sum(t["D_pi"] for t in supported),
            D_pi=sum(t["D_pi"] for t in supported) if full_support else None,
            M_flex=sum(len(t["states"]) > 1 for t in supported) / 1000,
            full_original_1000_material_support=full_support,
            Student_encoding_complete=False,
            training_started=False,
            material_admission_only=full_support and all(t["agreed_masks"] for t in task_rows),
            unknown_or_invalid_positive_training=False,
            valid_originals_silently_dropped=False,
            true_Probe_probability_estimated=False,
            total_possible_state_coverage_known=False,
            human_reviewed=False,
            mathematical_proof=False,
            budget=ledger.snapshot(),
        )
    )
    persist(output / "inventory_complete", summary)
    status(
        output,
        dict(
            at=now(),
            phase="INVENTORY_COMPLETE",
            protocol_id=plan["id"],
            completed=8000,
            denominator=8000,
            review_completed=2000,
            review_denominator=2000,
            full_original_1000_material_support=full_support,
            supported_task_count=len(supported),
            counts=dict(counts),
            budget=ledger.snapshot(),
            training_started=False,
        ),
    )
    return summary


async def run(output, env_file):
    output = Path(output)
    plan = checked_plan(output)
    try:
        validate_recovery(output, plan)
        ledger = ledger_for(output, plan)
        key = _key(env_file)
        os.environ.pop("DEEPSEEK_API_KEY", None)
        if await collect(output, plan, ledger, key) and await review_all(output, plan, ledger, key):
            finalize(output, plan, ledger)
    except BaseException as error:
        status(
            output,
            dict(
                at=now(),
                phase="BLOCKED",
                protocol_id=plan["id"],
                error_type=type(error).__name__,
                automatic_retry=False,
                training_started=False,
            ),
        )
        raise


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
        with (args.output / "controller.lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            asyncio.run(run(args.output, args.env_file))
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
