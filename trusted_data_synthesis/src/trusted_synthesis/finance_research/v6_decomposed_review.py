"""Registered v3: 16000 single-trajectory reviews plus 2000 task alignments.

Two isolated review chains, unchanged originals, inherited paid history and cap.
Technical admission is not positive-material selection. No retries or GPU work.
"""

from __future__ import annotations

import argparse
import asyncio
import fcntl
import json
import math
import os
import statistics
import subprocess
import sys
from collections import Counter, OrderedDict
from pathlib import Path

from .calibration import ROOT, identity, now, publish, status
from .cli import _key
from .contracts import digest, invocation_identity
from .probe_budget import ProbePriceSheet
from .storage import read_json, runtime_binding
from .v6_collection import ENV_FILE, STUDY, bound, checked_prepared, persist, require, sha
from .v6_review_provider import request_review
from .v6_review_revision import (
    ALLOWED_OUTPUTS,
    ORIGINAL,
    capacity_for,
    connect,
    historical_audit,
    ledger_for,
    original_protocol,
    paid_row,
    response_binding,
)
from .v6_review_revision import (
    protocol_path as parent_protocol_path,
)
from .v6_slot_review import capacity_features, inspect_slot_review, slot_review_request

OUTPUT = STUDY / "review_revision_03"
PARENT = STUDY / "review_revision_02"
CAPACITY_ID = "v6_decomposed_actual_load.v1"
SLOT_DENOMINATOR, ALIGNMENT_DENOMINATOR = 16000, 2000


def job_key(stage, task_id, reviewer, slot_id=None):
    return stage + ":" + digest(dict(task_id=task_id, reviewer=reviewer, slot_id=slot_id))


def episode_id(plan, job):
    return "v6d3-" + job["stage"] + ":" + digest(dict(protocol_id=plan["id"], job_key=job["key"]))


def job_directory(output, job):
    return Path(output) / "jobs" / job["key"].replace(":", "_")


def task_inputs(output, task_id):
    return Path(output) / "slot_inputs" / digest(task_id)


def bind_capacity(request, *, generation_tokens, fragments, actions, alignment=False):
    if alignment:
        estimate = math.ceil(1.5 * (4096 + 2 * generation_tokens + 48 * fragments + 64 * actions))
        cap = next((n for n in ALLOWED_OUTPUTS[1:] if n >= estimate), None)
        require(cap is not None, "alignment capacity exceeds registered maximum; no clipping")
    else:
        values = capacity_for(
            generation_output_tokens=generation_tokens,
            target_span_count=fragments,
            action_count=actions,
        )
        estimate, cap = values["estimated_requirement"], values["max_output_tokens"]
    if request is not None:
        request.update(max_output_tokens=cap, capacity_policy_id=CAPACITY_ID)
        size = sum(len(m["content"].encode()) for m in request["messages"])
        size += len(json.dumps(request["strict_tool"], ensure_ascii=False).encode())
        require(size + cap < 1048576, "full request/context bound exceeded; no truncation")
    return dict(
        max_output_tokens=cap,
        estimated_requirement=estimate,
        generation_tokens=generation_tokens,
        target_fragments=fragments,
        actions=actions,
        workload=estimate / 1.5,
        exact_API_token_forecast=False,
    )


def build_registration(output, source_commit):
    history = historical_audit(PARENT)
    old = original_protocol()
    parent = read_json(parent_protocol_path(PARENT))
    require(
        len(history["paid_entries"]) == 18888 and history["budget_counters"]["spent"] == 117783069,
        "new run must preserve the audited full historical spend and request population",
    )
    publish(Path(output) / "historical_audit", history)
    outcomes = read_json(ORIGINAL / "generation_seal/record.json")["slots"]
    generation = {r["slot"]["slot_id"]: r for r in outcomes}
    grouped = {t: [] for t in old["task_ids"]}
    for slot in old["inventory"]["slots"]:
        grouped[slot["task_id"]].append(slot)
    jobs, inputs, task_capacities = [], {}, {}
    native_support = {}
    for task_id in old["task_ids"]:
        prepared = checked_prepared(ORIGINAL, task_id)
        native_support[task_id] = sum(
            v["native_correct"] is True for v in prepared["mechanical"].values()
        )
        reference = json.loads(prepared["requests"][0]["messages"][1]["content"])[
            "review_only_private_reference"
        ]
        requests, features = {}, []
        for slot in grouped[task_id]:
            sid = slot["slot_id"]
            path = Path(generation[sid]["episode_path"])
            require(
                sha(path) == generation[sid]["episode_file_sha256"], "original trajectory changed"
            )
            original_episode = read_json(path)
            tokens = sum(turn["usage"]["completion_tokens"] for turn in original_episode["turns"])
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
                    features.append(capacity)
        payload = bound(
            dict(task_id=task_id, original_prepared_id=prepared["id"], requests=requests)
        )
        persist(task_inputs(output, task_id), payload)
        inputs[task_id] = dict(
            id=payload["id"], sha256=sha(task_inputs(output, task_id) / "record.json")
        )
        task_capacities[task_id] = bind_capacity(
            None,
            generation_tokens=sum(f["generation_tokens"] for f in features),
            fragments=sum(f["target_fragments"] for f in features),
            actions=sum(f["actions"] for f in features),
            alignment=True,
        )
    task_order = {t: i for i, t in enumerate(old["task_ids"])}
    jobs.sort(key=lambda j: (j["slot_index"], task_order[j["task_id"]], j["reviewer"]))
    for task_id in old["task_ids"]:
        for reviewer in (0, 1):
            jobs.append(
                dict(
                    key=job_key("alignment", task_id, reviewer),
                    stage="alignment",
                    task_id=task_id,
                    slot_id=None,
                    reviewer=reviewer,
                    capacity=task_capacities[task_id],
                )
            )
    require(
        Counter(j["stage"] for j in jobs) == dict(slot=16000, alignment=2000),
        "fixed stage counts changed",
    )
    return bound(
        dict(
            schema="v6_decomposed_review.v1",
            at=now(),
            source_commit=source_commit,
            runtime_binding=runtime_binding(),
            authorization="继续实验；逐轨迹审阅＋任务内状态对齐",
            parent_revision=str(PARENT),
            parent_protocol_id=parent["id"],
            historical_audit_id=history["id"],
            original_protocol_id=old["id"],
            task_ids=old["task_ids"],
            slot_inputs=inputs,
            jobs=jobs,
            original_slots=8000,
            all_eight_common_candidates=True,
            new_generation_calls=0,
            native_support_by_task=native_support,
            native_zero_support_task_ids=[t for t, n in native_support.items() if n == 0],
            original_1000_training_possible_from_this_inventory=all(native_support.values()),
            automatic_full_inventory_expansion=False,
            next_route="new_full_probe_authorized",
            expansion_decision="用户选择设计并登记新一整批轨迹，保留旧批，不按成绩拼接",
            authorized_paid_jobs_this_registration=108,
            full_old_review_matrix_is_design_only=True,
            slot_review_denominator=16000,
            alignment_denominator=2000,
            total_review_denominator=18000,
            all_original_generation_before_review=True,
            alignment_sees_only_own_eight_slot_reviews=True,
            two_chains_statistically_independent=False,
            model="deepseek-flash",
            thinking="disabled",
            temperature=0,
            technical_gate=dict(
                task_ids=parent["calibration"]["task_ids"],
                slot_requests=96,
                alignment_requests=12,
                included_in_formal_matrix=False,
                cohort_type="engineering validation on old material; not new training data",
                requires_positive_v_trace=False,
                minimum_interface_fraction=0.95,
                no_output_truncation=True,
                no_unknown_billing=True,
                early_guard="after 8 returns, >=75% of last min(16,n) mechanically admissible",
                semantic_inconsistency="retained unknown, never positive material or fake pass",
            ),
            budget={
                **parent["budget"],
                "historical_spent_microcny": history["budget_counters"]["spent"],
            },
            allowed_output_limits=ALLOWED_OUTPUTS,
            capacity_policy=dict(
                id=CAPACITY_ID,
                slot="ceil(1.5*(4096+3*actual_generation_tokens+64*target_fragments+128*actions))",
                alignment="ceil(1.5*(4096+2*task_generation_tokens+48*task_target_fragments+64*actions))",
                allocation="smallest allowed cap >= estimate; above 131072 blocks, no truncation",
                exact_token_prediction=False,
            ),
            concurrency=dict(pilot_slot=8, pilot_alignment=4, slot=32, alignment=16),
            retry_count=0,
            format_repair=False,
            automatic_training=False,
            GPU_reservation=False,
            forecast_policy=(
                "stage median paid cost/workload scaled to remaining jobs; "
                "central estimate above remaining cap stops expansion"
            ),
        )
    )


def register(output):
    output = Path(output)
    if (output / "registration/protocol.json").exists():
        return checked_plan(output)
    require(
        not output.exists(), "partial registration requires explicit inspection; never overwrite"
    )
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    for path in Path(__file__).parent.rglob("*.py"):
        require(
            path.read_bytes()
            == subprocess.check_output(
                ["git", "show", head + ":" + str(path.relative_to(ROOT))], cwd=ROOT
            ),
            "commit frozen decomposition before paid registration",
        )
    plan = build_registration(output, head)
    publish(output / "registration", plan, "protocol.json")
    return plan


def checked_plan(output):
    plan = read_json(Path(output) / "registration/protocol.json")
    require(
        plan["id"] == digest({k: v for k, v in plan.items() if k != "id"}),
        "decomposition protocol changed",
    )
    require(plan["runtime_binding"] == runtime_binding(), "frozen decomposition runtime changed")
    return plan


class Context:
    def __init__(self, output, plan):
        self.output, self.plan = Path(output), plan
        self.jobs = {j["key"]: j for j in plan["jobs"]}
        self.ids = {episode_id(plan, j): j for j in plan["jobs"]}
        self._input_cache = OrderedDict()
        self.slot_jobs = {t: [] for t in plan["task_ids"]}
        for j in plan["jobs"]:
            if j["stage"] == "slot":
                self.slot_jobs[j["task_id"]].append(j)

    def slots_input(self, task_id):
        if task_id in self._input_cache:
            self._input_cache.move_to_end(task_id)
            return self._input_cache[task_id]
        path = task_inputs(self.output, task_id) / "record.json"
        expected = self.plan["slot_inputs"][task_id]
        require(sha(path) == expected["sha256"], "registered per-slot request bytes changed")
        value = read_json(path)
        require(
            value["id"] == expected["id"] == digest({k: v for k, v in value.items() if k != "id"}),
            "slot input binding changed",
        )
        self._input_cache[task_id] = value
        if len(self._input_cache) > 32:
            self._input_cache.popitem(last=False)
        return value

    def request(self, job):
        if job["stage"] == "slot":
            request = self.slots_input(job["task_id"])["requests"][job["key"]]
            require(digest(request) == job["request_sha256"], "frozen slot request changed")
            return request
        path = job_directory(self.output, job) / "request/record.json"
        value = read_json(path)
        require(
            value["id"] == digest({k: v for k, v in value.items() if k != "id"}),
            "alignment input binding changed",
        )
        require(
            value["protocol_id"] == self.plan["id"] and value["job_key"] == job["key"],
            "alignment wrong registered scope",
        )
        require(
            value["slot_review_hashes"] == self.slot_review_hashes(job["task_id"], job["reviewer"]),
            "alignment own-chain results changed",
        )
        return value["request"]

    def slot_review_hashes(self, task_id, reviewer):
        return {
            j["slot_id"]: sha(job_directory(self.output, j) / "assessment/record.json")
            for j in self.slot_jobs[task_id]
            if j["reviewer"] == reviewer
        }

    def slot_reviews(self, task_id, reviewer):
        values = {}
        for j in self.slot_jobs[task_id]:
            if j["reviewer"] != reviewer:
                continue
            assessment = read_json(job_directory(self.output, j) / "assessment/record.json")
            values[j["slot_id"]] = assessment.get("validation") or assessment
        require(len(values) == 8, "all original eight reviews per chain are required")
        return values

    def prepare_alignment(self, task_id):
        from .v6_state_alignment import alignment_request

        prepared = checked_prepared(ORIGINAL, task_id)
        # Both chains are sealed locally, but each request sees only its own side.
        require(
            all(
                (job_directory(self.output, j) / "assessment/record.json").exists()
                for j in self.slot_jobs[task_id]
            ),
            "alignment before complete per-task slot barrier",
        )
        for reviewer in (0, 1):
            job = self.jobs[job_key("alignment", task_id, reviewer)]
            request = alignment_request(prepared, self.slot_reviews(task_id, reviewer), reviewer)
            cap = job["capacity"]
            actual = bind_capacity(
                request,
                generation_tokens=cap["generation_tokens"],
                fragments=cap["target_fragments"],
                actions=cap["actions"],
                alignment=True,
            )
            require(actual == cap, "registered alignment capacity changed after outcomes")
            value = bound(
                dict(
                    protocol_id=self.plan["id"],
                    job_key=job["key"],
                    slot_review_hashes=self.slot_review_hashes(task_id, reviewer),
                    request=request,
                )
            )
            persist(job_directory(self.output, job) / "request", value)


def assess(job, artifact, request):
    coordinates = dict(
        reviewer=job["reviewer"],
        task_id=job["task_id"],
        slot_id=job.get("slot_id"),
        task_bundle_sha256=request["task_bundle_sha256"],
        raw_review_sha256=digest(artifact.get("review_text")),
    )
    if artifact["finish_reason"] != "tool_calls" or artifact.get("review_format_error"):
        return dict(
            **coordinates,
            interface_admitted=False,
            semantic_consistent=False,
            validation=None,
            v_trace="unknown",
            parsed=None,
            derived=None,
            error=artifact.get("review_format_error") or "non-normal finish",
            error_kind="mechanical_interface",
            output_truncated=artifact["finish_reason"] == "length",
        )
    if job["stage"] == "slot":
        if request.get("wire_protocol") == "v6_slot_review.v4":
            from .v7_slot_review import inspect_slot_review as inspect_typed_slot

            result = inspect_typed_slot(artifact["review_text"], request)
        else:
            result = inspect_slot_review(artifact["review_text"], request)
    else:
        from .v6_state_alignment import inspect_alignment

        result = inspect_alignment(artifact["review_text"], request)
    return {**coordinates, **result, "output_truncated": False}


def recover(context):
    history = read_json(context.output / "historical_audit/record.json")
    require(
        history["id"]
        == context.plan["historical_audit_id"]
        == digest({k: v for k, v in history.items() if k != "id"}),
        "historical paid prefix changed",
    )
    old = {r["invocation_id"]: r for r in history["paid_entries"]}
    price = ProbePriceSheet(**context.plan["budget"]["price_sheet"])
    seen, completed = set(), {}
    amounts = []
    tokens = Counter()
    with connect() as con:
        require(
            con.execute("SELECT value FROM metadata WHERE key='halt'").fetchone() is None,
            "halted joint budget cannot resume",
        )
        for row in con.execute("SELECT * FROM requests"):
            evidence, _, _, usage = paid_row(row, price)
            amounts.append(evidence["settled_microcny"])
            tokens.update(usage)
            iid = evidence["invocation_id"]
            if iid in old:
                require(evidence == old[iid], "historical call/cost changed")
                seen.add(iid)
                continue
            require(evidence["episode_id"] in context.ids, "unregistered decomposition call")
            job = context.ids[evidence["episode_id"]]
            coordinates = invocation_identity(
                dict(
                    run_id=context.plan["budget"]["run_id"],
                    episode_id=evidence["episode_id"],
                    attempt_index=1,
                ),
                turn_index=0,
            )
            require(
                json.loads(row["coordinates_json"]) == coordinates,
                "stage/reviewer/slot invocation changed",
            )
            directory = job_directory(context.output, job)
            require(
                (directory / "response/record.json").exists()
                and (directory / "assessment/record.json").exists(),
                "incomplete paid job cannot be resent",
            )
            artifact = read_json(directory / "response/record.json")
            request = context.request(job)
            response_binding(artifact, request, row)
            assessment = read_json(directory / "assessment/record.json")
            require(
                assessment == assess(job, artifact, request),
                "assessment changed from actual raw review",
            )
            completed[job["key"]] = dict(artifact=artifact, assessment=assessment)
        counters = dict(con.execute("SELECT * FROM counters WHERE singleton=1").fetchone())
        require(seen == set(old), "old paid calls or charges disappeared")
        require(
            counters["spent"] == sum(amounts)
            and counters["requests"] == counters["dispatched"] == len(amounts)
            and counters["pending"] == counters["unknown"] == counters["held"] == 0
            and counters["prompt_tokens"] == tokens["prompt_tokens"]
            and counters["completion_tokens"] == tokens["completion_tokens"]
            and counters["hit_tokens"] == tokens["prompt_cache_hit_tokens"]
            and counters["miss_tokens"] == tokens["prompt_cache_miss_tokens"],
            "joint paid counters not conserved",
        )
    for key, job in context.jobs.items():
        directory = job_directory(context.output, job)
        require(
            not (directory / "started").exists() or key in completed,
            "unfinished dispatched/started job needs disposition, not retry",
        )
    return completed


def interface_gate(jobs, completed):
    done = [completed[j["key"]] for j in jobs if j["key"] in completed]
    passed = sum(bool(v["assessment"]["interface_admitted"]) for v in done)
    truncated = sum(bool(v["assessment"].get("output_truncated")) for v in done)
    return dict(
        denominator=len(jobs),
        completed=len(done),
        interface_passed=passed,
        required_passes=math.ceil(0.95 * len(jobs)),
        output_truncated=truncated,
        admitted=len(done) == len(jobs) and passed >= math.ceil(0.95 * len(jobs)) and not truncated,
        semantic_consistency_count=sum(
            bool(v["assessment"].get("semantic_consistent")) for v in done
        ),
        positive_verdict_required=False,
    )


def budget_forecast(context, completed, ledger):
    stages = {}
    remaining = ledger.snapshot()["remaining_exposure_microcny"]
    for stage in ("slot", "alignment"):
        jobs = [j for j in context.plan["jobs"] if j["stage"] == stage]
        ratios = [
            completed[j["key"]]["artifact"]["peak_tariff_upper_bound_microcny"]
            / j["capacity"]["workload"]
            for j in jobs
            if j["key"] in completed
        ]
        require(ratios, "paid calibration evidence required for both stage forecasts")
        load = sum(j["capacity"]["workload"] for j in jobs if j["key"] not in completed)
        stages[stage] = dict(
            observed_requests=len(ratios),
            remaining_workload=load,
            central_remaining_microcny=math.ceil(statistics.median(ratios) * load),
            observed_ratio_high_scenario_microcny=math.ceil(max(ratios) * load),
        )
    predicted = sum(v["central_remaining_microcny"] for v in stages.values())
    return dict(
        stages=stages,
        remaining_joint_budget_microcny=remaining,
        central_remaining_microcny=predicted,
        admitted=predicted <= remaining,
        statistical_confidence_interval=False,
        guarantee_of_completion=False,
        true_hard_guard="settled cost plus pending/unknown reservations <= original 800 CNY",
    )


async def run_batch(context, ledger, key, completed, jobs, phase, concurrency):
    import httpx

    if not context.plan.get("automatic_full_inventory_expansion", False):
        cohort = set(context.plan["technical_gate"]["task_ids"])
        require(
            all(j["task_id"] in cohort for j in jobs),
            "only the registered engineering cohort is authorized on old material",
        )

    queue = asyncio.Queue()
    halted = asyncio.Event()
    done = asyncio.Event()
    failures = []
    if (context.output / "dispatch_stop/record.json").exists():
        return [dict(reason="immutable prior stop prevents new dispatch")]
    for job in jobs:
        if job["key"] not in completed:
            queue.put_nowait(job)
    # Restart preserves the same preceding interface outcomes; no free clean slate.
    recent = [completed[j["key"]]["assessment"] for j in jobs if j["key"] in completed][-16:]

    def save_stop(trigger):
        directory = context.output / "dispatch_stop"
        if not (directory / "record.json").exists():
            publish(
                directory,
                bound(
                    dict(
                        protocol_id=context.plan["id"],
                        phase=phase,
                        trigger=trigger,
                        at=now(),
                        recent_assessments=recent.copy(),
                        recent_assessment_hashes=[digest(r) for r in recent],
                        automatic_resume=False,
                    )
                ),
            )

    def must_stop():
        return any(r.get("output_truncated") for r in recent) or (
            len(recent) >= 8
            and sum(bool(r["interface_admitted"]) for r in recent) < math.ceil(0.75 * len(recent))
        )

    def progress():
        counts = Counter(context.jobs[k]["stage"] for k in completed)
        status(
            context.output,
            dict(
                at=now(),
                protocol_id=context.plan["id"],
                phase=phase if not halted.is_set() else "STOPPING",
                slot_reviews_completed=counts["slot"],
                slot_review_denominator=context.plan.get("slot_review_denominator", 16000),
                alignments_completed=counts["alignment"],
                alignment_denominator=context.plan.get("alignment_denominator", 2000),
                original_generation_completed=8000,
                blocked=failures,
                budget=ledger.snapshot(),
                training_started=False,
            ),
        )

    async def monitor():
        while not done.is_set():
            progress()
            try:
                await asyncio.wait_for(done.wait(), 15)
            except TimeoutError:
                pass

    if must_stop():
        save_stop("recovered preceding failure window")
        return [dict(reason="existing failure window prevents further dispatch")]
    async with httpx.AsyncClient(
        trust_env=False,
        timeout=1200,
        follow_redirects=False,
        limits=httpx.Limits(max_connections=concurrency, max_keepalive_connections=concurrency),
    ) as client:

        async def worker():
            while not halted.is_set():
                try:
                    job = queue.get_nowait()
                except asyncio.QueueEmpty:
                    return
                directory = job_directory(context.output, job)
                request = context.request(job)
                publish(
                    directory / "started",
                    dict(
                        at=now(),
                        job_key=job["key"],
                        episode_id=episode_id(context.plan, job),
                        max_output_tokens=request["max_output_tokens"],
                    ),
                )
                try:
                    artifact = await request_review(
                        ledger=ledger,
                        api_key=key,
                        episode_id=episode_id(context.plan, job),
                        request=request,
                        client=client,
                        timeout=max(180, math.ceil(90 + request["max_output_tokens"] / 128)),
                    )
                    publish(directory / "response", artifact)
                    assessment = assess(job, artifact, request)
                    publish(directory / "assessment", assessment)
                    completed[job["key"]] = dict(artifact=artifact, assessment=assessment)
                    recent.append(assessment)
                    recent[:] = recent[-16:]
                    if must_stop():
                        save_stop(job["key"])
                        failures.append(
                            dict(
                                job_key=job["key"], reason="registered interface/capacity stop rule"
                            )
                        )
                        halted.set()
                except BaseException as error:
                    publish(
                        directory / "blocked",
                        dict(at=now(), error_type=type(error).__name__, retry=False),
                    )
                    failures.append(dict(job_key=job["key"], error_type=type(error).__name__))
                    halted.set()
                    if not isinstance(error, Exception):
                        raise

        watcher = asyncio.create_task(monitor())
        try:
            await asyncio.gather(*(worker() for _ in range(concurrency)))
        finally:
            done.set()
            await watcher
    return failures


def inventory(context, completed, ledger):
    from .v6_state_alignment import resolve_decomposed_pair

    require(
        len(completed) == 18000,
        "all registered slot reviews and alignments must settle before inventory",
    )
    counts = Counter()
    tasks = []
    for task_id in context.plan["task_ids"]:
        prepared = checked_prepared(ORIGINAL, task_id)
        sides = [context.slot_reviews(task_id, i) for i in (0, 1)]
        alignments = []
        for i in (0, 1):
            a = completed[job_key("alignment", task_id, i)]["assessment"]
            alignments.append(a.get("validation") or a)
        resolution = resolve_decomposed_pair(prepared, *sides, *alignments)
        persist(context.output / "resolution" / digest(task_id), resolution)
        values = list(resolution["slots"].values())
        counts.update(v["v_trace"] for v in values)
        counts["native_correct"] += sum(v["q_native"] is True for v in values)
        valid = [v for v in values if v["v_trace"] == "valid" and v["q_native"] is True]
        counts["joint_valid"] += len(valid)
        mapped = bool(valid) and resolution["task_mapping"] == "complete"
        states = Counter(v["state_id"] for v in valid) if mapped else Counter()
        n = sum(states.values())
        tasks.append(
            dict(
                task_id=task_id,
                joint_valid=len(valid),
                mapping_complete=mapped,
                n_x=n,
                states=dict(states),
                masks_complete=all(v["encoding_manifest"] is not None for v in valid),
                r={z: c / n for z, c in states.items()},
                K_per_original={z: 1 / c for z, c in states.items()},
                conditional_state_entropy=-sum(c / n * math.log(c / n) for c in states.values())
                if n
                else None,
                singleton_states=sum(c == 1 for c in states.values()),
                D_pi=len(states) - 1 if states else None,
            )
        )
    supported = [t for t in tasks if t["mapping_complete"]]
    result = bound(
        dict(
            protocol_id=context.plan["id"],
            original_tasks=1000,
            original_slots=8000,
            slot_review_denominator=16000,
            alignment_denominator=2000,
            completed_calls=18000,
            counts=dict(counts),
            validity_yield=counts["joint_valid"] / 8000,
            tasks=tasks,
            supported_tasks=len(supported),
            observed_D_pi=sum(t["D_pi"] for t in supported),
            D_pi=sum(t["D_pi"] for t in supported) if len(supported) == 1000 else None,
            M_flex=sum(len(t["states"]) > 1 for t in supported) / 1000,
            material_admission_only=len(supported) == 1000
            and all(t["masks_complete"] for t in tasks),
            Student_encoding_complete=False,
            training_started=False,
            human_reviewed=False,
            all_originals_retained=True,
            old_paid_failures_retained=True,
            budget=ledger.snapshot(),
        )
    )
    persist(context.output / "inventory_complete", result)
    return result


async def run(output, env_file):
    output = Path(output)
    plan = checked_plan(output)
    context = Context(output, plan)
    ledger = ledger_for(plan)
    completed = recover(context)
    if (output / "dispatch_stop/record.json").exists():
        stop = read_json(output / "dispatch_stop/record.json")
        require(
            stop["id"] == digest({k: v for k, v in stop.items() if k != "id"})
            and stop["protocol_id"] == plan["id"],
            "dispatch stop record changed",
        )
        status(
            output,
            dict(
                at=now(),
                phase="BLOCKED_PRIOR_DISPATCH_STOP",
                new_calls=0,
                budget=ledger.snapshot(),
                training_started=False,
            ),
        )
        return
    if (output / "technical_gate/record.json").exists():
        gate = read_json(output / "technical_gate/record.json")
        require(
            gate["id"] == digest({k: v for k, v in gate.items() if k != "id"}),
            "technical gate changed",
        )
        if not gate["admitted"]:
            status(
                output,
                dict(
                    at=now(),
                    phase="TECHNICAL_GATE_BLOCKED",
                    new_calls=0,
                    budget=ledger.snapshot(),
                    training_started=False,
                ),
            )
            return
    key = _key(env_file)
    os.environ.pop("DEEPSEEK_API_KEY", None)
    cohort = set(plan["technical_gate"]["task_ids"])
    slot_jobs = [j for j in plan["jobs"] if j["stage"] == "slot"]
    alignment_jobs = [j for j in plan["jobs"] if j["stage"] == "alignment"]
    pilot_slot = [j for j in slot_jobs if j["task_id"] in cohort]
    pilot_alignment = [j for j in alignment_jobs if j["task_id"] in cohort]
    blocked = await run_batch(context, ledger, key, completed, pilot_slot, "PILOT_SLOT_REVIEW", 8)
    slot_gate = interface_gate(pilot_slot, completed)
    alignment_gate = None
    if not blocked and slot_gate["admitted"]:
        for t in plan["technical_gate"]["task_ids"]:
            context.prepare_alignment(t)
        blocked = await run_batch(
            context, ledger, key, completed, pilot_alignment, "PILOT_ALIGNMENT", 4
        )
        alignment_gate = interface_gate(pilot_alignment, completed)
    admitted = (
        not blocked
        and slot_gate["admitted"]
        and alignment_gate is not None
        and alignment_gate["admitted"]
    )
    gate_path = output / "technical_gate/record.json"
    gate = bound(
        dict(
            protocol_id=plan["id"],
            slot=slot_gate,
            alignment=alignment_gate,
            admitted=bool(admitted),
            actual_review_hashes={
                j["key"]: digest(completed[j["key"]]["artifact"])
                for j in pilot_slot + pilot_alignment
                if j["key"] in completed
            },
            positive_material_yield_not_used=True,
        )
    )
    persist(gate_path.parent, gate)
    if not admitted:
        status(
            output,
            dict(
                at=now(),
                phase="TECHNICAL_GATE_BLOCKED",
                slot_gate=slot_gate,
                alignment_gate=alignment_gate,
                blocked=blocked,
                budget=ledger.snapshot(),
                training_started=False,
            ),
        )
        return
    forecast_path = output / "budget_forecast/record.json"
    if forecast_path.exists():
        forecast = read_json(forecast_path)
        require(
            forecast["id"] == digest({k: v for k, v in forecast.items() if k != "id"})
            and forecast["protocol_id"] == plan["id"]
            and forecast["pilot_review_hashes"] == gate["actual_review_hashes"],
            "frozen forecast cannot change with later outcomes",
        )
    else:
        forecast = bound(
            dict(
                **budget_forecast(context, completed, ledger),
                protocol_id=plan["id"],
                pilot_review_hashes=gate["actual_review_hashes"],
            )
        )
        persist(output / "budget_forecast", forecast)
    if not forecast["admitted"] and plan["automatic_full_inventory_expansion"]:
        status(
            output,
            dict(
                at=now(),
                phase="BUDGET_FORECAST_BLOCKED",
                forecast=forecast,
                budget=ledger.snapshot(),
                training_started=False,
            ),
        )
        return
    if not plan["automatic_full_inventory_expansion"]:
        status(
            output,
            dict(
                at=now(),
                phase=(
                    "TECHNICAL_COHORT_COMPLETE_NEW_BATCH_NEXT"
                    if plan.get("next_route") == "new_full_probe_authorized"
                    else "TECHNICAL_COHORT_COMPLETE_AWAITING_SCOPE"
                ),
                slot_gate=slot_gate,
                alignment_gate=alignment_gate,
                forecast=forecast,
                native_zero_support_tasks=len(plan["native_zero_support_task_ids"]),
                original_1000_training_possible=False,
                budget=ledger.snapshot(),
                training_started=False,
            ),
        )
        return
    blocked = await run_batch(context, ledger, key, completed, slot_jobs, "SLOT_REVIEWING", 32)
    if blocked or any(j["key"] not in completed for j in slot_jobs):
        status(
            output,
            dict(
                at=now(),
                phase="SLOT_REVIEW_INCOMPLETE",
                blocked=blocked,
                completed=sum(j["key"] in completed for j in slot_jobs),
                denominator=16000,
                budget=ledger.snapshot(),
                training_started=False,
            ),
        )
        return
    completed = recover(context)
    persist(
        output / "slot_review_seal",
        bound(
            dict(
                protocol_id=plan["id"],
                denominator=16000,
                reviews={j["key"]: digest(completed[j["key"]]["artifact"]) for j in slot_jobs},
            )
        ),
    )
    for task_id in plan["task_ids"]:
        context.prepare_alignment(task_id)
    blocked = await run_batch(
        context, ledger, key, completed, alignment_jobs, "STATE_ALIGNMENT", 16
    )
    if blocked or len(completed) != 18000:
        status(
            output,
            dict(
                at=now(),
                phase="ALIGNMENT_INCOMPLETE",
                completed=len(completed),
                denominator=18000,
                blocked=blocked,
                budget=ledger.snapshot(),
                training_started=False,
            ),
        )
        return
    completed = recover(context)
    result = inventory(context, completed, ledger)
    status(
        output,
        dict(
            at=now(),
            phase="INVENTORY_COMPLETE",
            completed=18000,
            denominator=18000,
            supported_tasks=result["supported_tasks"],
            material_admission_only=result["material_admission_only"],
            budget=ledger.snapshot(),
            training_started=False,
        ),
    )


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("action", choices=("register", "start", "run", "status"))
    p.add_argument("--output", type=Path, default=OUTPUT)
    p.add_argument("--env-file", type=Path, default=ENV_FILE)
    args = p.parse_args(argv)
    if args.action == "register":
        print(dict(protocol_id=register(args.output)["id"]))
    elif args.action == "status":
        print(read_json(args.output / "status.json"))
    elif args.action == "run":
        with (ORIGINAL / "controller.lock").open("a") as lock:
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
