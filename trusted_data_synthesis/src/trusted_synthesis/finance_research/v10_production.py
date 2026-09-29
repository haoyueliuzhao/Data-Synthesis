"""Fixed new-batch A/B process review, one task mapping, and material handoff.

No paid pilot, result-driven prompt change, third review, old-side splicing or
prefix training. Every registered job is either a real return or a bound missing
connection response; budget and non-network failures save and stop this cohort.
"""

from __future__ import annotations

import argparse
import asyncio
import fcntl
import json
import math
import signal
from collections import Counter
from pathlib import Path

from .calibration import now, publish, status
from .contracts import Episode, ProviderCallError, digest, invocation_identity
from .probe_collection import ENV_FILE, slot_directory
from .storage import read_json
from .v6_collection import bound, persist, require, sha
from .v6_review_revision import _key
from .v10_budget import (
    BATCH_ID,
    NETWORK_POLICY,
    acknowledge_connection_unknowns,
    map_episode_id,
    review_episode_id,
)
from .v10_generation import OUTPUT, checked, checked_plan, ledger_for
from .v10_review_protocol import (
    mapping_record,
    prepare_mapping_request,
    prepare_review_request,
    resolve_joint_review,
    review_policy_definition,
    review_record,
)
from .v10_review_provider import direct_client, request_body, request_review, restore_artifact

RUNTIME_PATH = Path("runtime/concurrency_revision_01/record.json")
CONCURRENCY_AUTHORIZATION = dict(
    date="2026-09-29",
    question=(
        "是否将尚未启动的审阅／任务映射并发从 8 提高到 16，并在派发前单独登记这项运行修订？"
        "样本、判定规则、零重试和费用硬上限均不变；遇到限流或异常仍保存并停止。"
    ),
    user_reply="批准后续审阅／映射并发 16",
)


def register_runtime(output, plan, ledger):
    """One explicitly authorized sending-resource revision for this batch only."""
    require(
        plan["batch_id"] == BATCH_ID
        and plan["concurrency"] == plan["policy"]["concurrency"] == 8
        and plan["review_policy_id"] == plan["policy"]["id"],
        "runtime authorization covers only this original batch and unchanged eight-worker policy",
    )
    expected = dict(
        schema="v10_annotation_concurrency_runtime.v1",
        protocol_id=plan["id"],
        batch_id=BATCH_ID,
        policy_id=plan["review_policy_id"],
        original_policy_sha256=digest(plan["policy"]),
        authorization=CONCURRENCY_AUTHORIZATION,
        original_policy_concurrency=8,
        effective_concurrency=dict(generation=8, review=16, mapping=16),
        override_scope="prospective review/mapping sending resources only",
        generation_unchanged=True,
        samples_semantics_masks_model_budget_and_zero_retries_unchanged=True,
        existing_bounded_connection_terminal_policy_unchanged=True,
        old_dispatched_configuration_rewritten=False,
        budget_run_id=ledger.run_id,
        budget_config_sha256=digest(ledger.config),
        source_bindings=phase_sources(),
    )
    path = Path(output) / RUNTIME_PATH
    if path.exists():
        prior = checked(path)
        require(
            all(prior.get(k) == v for k, v in expected.items())
            and prior.get("annotation_requests_before_registration") == 0,
            "registered annotation runtime differs; never overwrite or silently change dispatch",
        )
        return prior
    snapshot = ledger.snapshot()
    partition = snapshot.get("v10_partition", {})
    quota = partition.get("consumed", {}).get("review_mapping", {})
    require(
        partition.get("batch_id") == BATCH_ID
        and all(
            quota.get(k) == 0
            for k in ("requests", "dispatched", "spent", "held", "pending", "unknown")
        ),
        "runtime must be registered before the first annotation reservation or dispatch",
    )
    record = bound(dict(**expected, at=now(), annotation_requests_before_registration=0))
    persist(path.parent, record)
    return record


def entry(path):
    path = Path(path).resolve()
    value = checked(path)
    return dict(path=str(path), id=value["id"], sha256=sha(path))


def read_entry(item):
    require(sha(item["path"]) == item["sha256"], "bound artifact bytes changed")
    value = checked(item["path"])
    require(value["id"] == item["id"], "bound artifact identity changed")
    return value


def job_directory(output, job):
    if job["kind"] == "review":
        return Path(output) / "reviews" / job["slot_id"].split(":", 1)[1] / job["role"]
    return Path(output) / "mapping" / digest(job["task_id"])


def joint_path(output, sid):
    return Path(output) / "joint" / sid.split(":", 1)[1] / "record.json"


def phase_sources():
    root = Path(__file__).parent
    return {
        name: sha(root / name)
        for name in (
            "v10_production.py",
            "v10_review_protocol.py",
            "v10_review_provider.py",
            "v10_budget.py",
            "probe_budget.py",
            "v10_process_review.py",
            "v10_student_encoding.py",
        )
    }


def register_review_phase(output, plan):
    output = Path(output)
    target = output / "review_registration/record.json"
    if target.exists():
        phase = checked(target)
        require(
            phase["protocol_id"] == plan["id"] and phase["source_bindings"] == phase_sources(),
            "registered production implementation changed",
        )
        return phase
    generation = entry(output / "generation_seal/record.json")
    native = entry(output / "native_support/record.json")
    g, n = read_entry(generation), read_entry(native)
    require(
        g["protocol_id"] == n["protocol_id"] == plan["id"]
        and n["generation_seal_id"] == g["id"]
        and len(g["slots"]) == len(n["rows"]) == 8000,
        "whole new batch before process review",
    )
    require(
        [r["slot"] for r in g["slots"]] == [r["slot"] for r in n["rows"]] == plan["slots"],
        "native/generation roster changed",
    )
    require(
        plan["policy"] == review_policy_definition(),
        "process/state/capacity rules must be frozen before generation",
    )
    eligible = [r["slot"] for r in n["rows"] if r["Q_native"] is True]
    require(len(eligible) == n["M"], "actual new M differs; never prefill old 5691")
    jobs = [
        dict(
            kind="review",
            slot_id=s["slot_id"],
            task_id=s["task_id"],
            role=role,
            episode_id=review_episode_id(plan["batch_id"], s["slot_id"], role),
        )
        for s in eligible
        for role in ("A", "B")
    ]
    phase = bound(
        dict(
            schema="v10_process_review_registration.v1",
            at=now(),
            protocol_id=plan["id"],
            batch_id=plan["batch_id"],
            policy_id=plan["review_policy_id"],
            source_bindings=phase_sources(),
            generation_seal=generation,
            native_support=native,
            eligible_slots=eligible,
            M=len(eligible),
            jobs=jobs,
            maximum_calls=len(jobs),
            primary_supervision_authority="A",
            third_review=False,
            old_review_reuse=False,
            no_prefix_training=True,
        )
    )
    publish(target.parent, phase)
    return phase


class Context:
    def __init__(self, output, plan, phase):
        self.output, self.plan, self.phase = Path(output), plan, phase
        self.native = {r["slot"]["slot_id"]: r for r in read_entry(phase["native_support"])["rows"]}
        self.slots = {s["slot_id"]: s for s in plan["slots"]}

    def request(self, job):
        directory = job_directory(self.output, job)
        path = directory / "request/record.json"
        if path.exists():
            request = checked(path)
            require(
                request["episode_id"] == job["episode_id"]
                and request["protocol_id"] == self.plan["batch_id"]
                and request["policy_id"] == self.plan["review_policy_id"],
                "saved request belongs to a different fixed job",
            )
            return request
        if job["kind"] == "review":
            slot = self.slots[job["slot_id"]]
            original = slot_directory(self.output, slot)
            outcome = checked(original / "outcome/record.json")
            require(
                outcome["status"] == "COMPLETE"
                and outcome["protocol_id"] == self.plan["id"]
                and sha(outcome["episode_path"]) == outcome["episode_file_sha256"],
                "review requires the original complete new episode",
            )
            episode = Episode.model_validate_json(Path(outcome["episode_path"]).read_bytes())
            integrity = checked(outcome["integrity_path"])
            require(
                integrity["episode_sha256"] == digest(episode) == outcome["episode_sha256"]
                and integrity["id"] == outcome["integrity_id"]
                and all(integrity["checks"].values()),
                "mechanical input is not fully bound; not a financial invalid judgment",
            )
            native = self.native[slot["slot_id"]]
            require(native["Q_native"] is True, "only new native-correct candidates are scheduled")
            request = prepare_review_request(
                episode,
                slot_id=slot["slot_id"],
                role=job["role"],
                native_result=native["native"],
                integrity=integrity["checks"],
                protocol_id=self.plan["batch_id"],
            )
        else:
            joints = [checked(joint_path(self.output, sid)) for sid in job["slot_ids"]]
            request = prepare_mapping_request(
                task_id=job["task_id"], joint_records=joints, protocol_id=self.plan["batch_id"]
            )
        publish(path.parent, request)
        return request


def iid_for(ledger, job):
    return invocation_identity(
        dict(run_id=ledger.run_id, episode_id=job["episode_id"], attempt_index=1), turn_index=0
    )["invocation_id"]


def terminal_record(output, plan, job, request, row, acknowledgment):
    require(
        row["state"] == "UNKNOWN"
        and row["invocation_id"] == acknowledgment["invocation_id"]
        and row["request_sha256"]
        == digest(request_body(request))
        == acknowledgment["expected_request_sha256"],
        "missing-response terminal must bind the exact acknowledged original",
    )
    body = dict(
        schema="v10_network_unknown_review.v1"
        if job["kind"] == "review"
        else "v10_network_unknown_mapping.v1",
        protocol_id=plan["batch_id"],
        registration_id=plan["id"],
        policy_id=plan["review_policy_id"],
        role=job.get("role", "mapping"),
        task_id=job["task_id"],
        slot_id=job.get("slot_id"),
        episode_id=job["episode_id"],
        episode_sha256=request.get("episode_sha256"),
        invocation_id=row["invocation_id"],
        request_sha256=row["request_sha256"],
        request_id=request["id"],
        ack_id=acknowledgment["id"],
        permanent_reserved_microcny=row["reserved_microcny"],
        terminal_kind="acknowledged_connection_unknown",
        actual_model_call_receipt_verified=False,
        original_response=None,
        usage=None,
        review_status="network_unknown",
        process_validity="unknown",
        material_eligible=False,
        mapping_status="unknown" if job["kind"] == "mapping" else None,
        states=[],
        no_resend=True,
    )
    value = bound(body)
    persist(job_directory(output, job) / "record", value)
    return value


def gather_terminals(output, jobs):
    result = {}
    for job in jobs:
        path = job_directory(output, job) / "record/record.json"
        if path.exists():
            record = checked(path)
            require(
                record.get("request", {}).get("episode_id", record.get("episode_id"))
                == job["episode_id"],
                "terminal job identity differs",
            )
            result[job["episode_id"]] = record
    return result


def recover_stage(output, plan, ledger, context, jobs):
    """Restore exact SETTLED envelopes; acknowledge only drained network unknowns."""
    from .probe_budget import read_budget_snapshot

    rows = {j["episode_id"]: ledger.request_record(iid_for(ledger, j)) for j in jobs}
    snapshot = read_budget_snapshot(plan["budget_database"])
    ack = {r["invocation_id"]: r for r in snapshot["acknowledged_unknowns"]}
    expected = {}
    for job in jobs:
        row = rows[job["episode_id"]]
        if row is not None and row["state"] == "UNKNOWN" and row["invocation_id"] not in ack:
            request = context.request(job)
            expected[row["invocation_id"]] = digest(request_body(request))
    if expected:
        receipt = acknowledge_connection_unknowns(
            ledger, batch_id=plan["batch_id"], expected_requests=expected
        )
        persist(Path(output) / "network_terminal_acknowledgements" / receipt["id"], receipt)
        ack.update({r["invocation_id"]: r for r in receipt["records"]})
    require(
        not ledger.snapshot()["halt"] and not ledger.snapshot()["unacknowledged_unknown_requests"],
        "non-network safety stop must not be cleared automatically",
    )
    for job in jobs:
        row = rows[job["episode_id"]]
        if row is None:
            continue
        directory = job_directory(output, job)
        request = context.request(job)
        if row["state"] == "UNKNOWN":
            require(row["invocation_id"] in ack, "unacknowledged unknown")
            terminal_record(output, plan, job, request, row, ack[row["invocation_id"]])
        elif row["state"] == "SETTLED":
            artifact = restore_artifact(row, request)
            artifact_path = directory / "artifact/record.json"
            if artifact_path.exists():
                artifact = read_json(artifact_path)
            else:
                publish(artifact_path.parent, artifact)
            record = (
                review_record(request, artifact, row)
                if job["kind"] == "review"
                else mapping_record(request, artifact, row)
            )
            persist(directory / "record", record)
        else:
            require(
                row["state"] == "RESERVED" and row["dispatched_at"] is None,
                "already dispatched unresolved call cannot be retried",
            )
    return gather_terminals(output, jobs)


async def execute_stage(output, plan, ledger, context, jobs, *, stop_requested=None):
    output = Path(output)
    stop_requested = stop_requested or asyncio.Event()
    stage = jobs[0]["kind"] if jobs else "review"
    runtime = register_runtime(output, plan, ledger)
    concurrency = runtime["effective_concurrency"][stage]
    key = _key(ENV_FILE)
    completed = recover_stage(output, plan, ledger, context, jobs)
    while len(completed) < len(jobs):
        stopped, done = asyncio.Event(), asyncio.Event()
        errors, active = [], set()
        queue = asyncio.Queue()
        for job in jobs:
            if job["episode_id"] not in completed:
                queue.put_nowait(job)

        def progress(phase=None, completed=completed, active=active, errors=errors):
            status(
                output,
                dict(
                    at=now(),
                    phase=phase or "V10_" + stage.upper() + "_RUNNING",
                    protocol_id=plan["id"],
                    processed=len(completed),
                    denominator=len(jobs),
                    runtime_revision_id=runtime["id"],
                    registered_stage_concurrency=concurrency,
                    effective_concurrency=runtime["effective_concurrency"],
                    actual_returns=sum(
                        r.get("actual_model_call_receipt_verified") is True
                        for r in completed.values()
                    ),
                    network_unknowns=sum(
                        r.get("terminal_kind") == "acknowledged_connection_unknown"
                        for r in completed.values()
                    ),
                    active=len(active),
                    errors=errors[-16:],
                    budget=ledger.snapshot(),
                    no_prefix_training=True,
                    training_started=False,
                ),
            )

        async def monitor(done=done, progress=progress):
            while not done.is_set():
                progress()
                try:
                    await asyncio.wait_for(done.wait(), 10)
                except TimeoutError:
                    pass

        async def worker(
            client,
            stopped=stopped,
            queue=queue,
            active=active,
            completed=completed,
            errors=errors,
        ):
            while not stopped.is_set() and not stop_requested.is_set():
                try:
                    job = queue.get_nowait()
                except asyncio.QueueEmpty:
                    return
                eid = job["episode_id"]
                active.add(eid)
                directory = job_directory(output, job)
                try:
                    request = context.request(job)
                    row = ledger.request_record(iid_for(ledger, job))
                    require(
                        row is None or row["state"] == "RESERVED",
                        "no re-dispatch of an existing sent job",
                    )
                    if not (directory / "started/record.json").exists():
                        publish(
                            directory / "started",
                            bound(
                                dict(
                                    at=now(),
                                    job=job,
                                    protocol_id=plan["id"],
                                    request_id=request["id"],
                                    retries=0,
                                )
                            ),
                        )
                    artifact = await request_review(
                        ledger=ledger,
                        api_key=key,
                        request=request,
                        client=client,
                        timeout=max(180, math.ceil(90 + request["max_output_tokens"] / 128)),
                        resume_reserved=row is not None,
                    )
                    publish(directory / "artifact", artifact)
                    row = ledger.request_record(iid_for(ledger, job))
                    record = (
                        review_record(request, artifact, row)
                        if job["kind"] == "review"
                        else mapping_record(request, artifact, row)
                    )
                    publish(directory / "record", record)
                    completed[eid] = record
                except Exception as exc:
                    row = ledger.request_record(iid_for(ledger, job))
                    evidence = json.loads(row["evidence_json"] or "{}") if row else {}
                    network_candidate = (
                        isinstance(exc, ProviderCallError)
                        and row is not None
                        and row["state"] == "UNKNOWN"
                        and all(
                            row[k] is None for k in ("http_status", "response_body", "usage_json")
                        )
                        and evidence.get("service_response_received") is False
                        and evidence.get("exception_type") in NETWORK_POLICY["exception_types"]
                    )
                    issue = dict(
                        at=now(),
                        job=job,
                        error_type=type(exc).__name__,
                        error=str(exc),
                        retry=False,
                        network_only_continuation_candidate=network_candidate,
                    )
                    publish(directory / "controller_errors" / digest(issue), bound(issue))
                    errors.append(issue)
                    stopped.set()
                finally:
                    active.discard(eid)

        watcher = asyncio.create_task(monitor())
        try:
            async with direct_client(timeout=1200) as client:
                await asyncio.gather(*(worker(client) for _ in range(concurrency)))
        finally:
            done.set()
            await watcher
        progress("V10_" + stage.upper() + "_SAVED")
        if stop_requested.is_set():
            return None
        if any(not item["network_only_continuation_candidate"] for item in errors):
            # An unrelated local/budget/service failure cannot acquire automatic
            # continuation merely because another in-flight call lost its connection.
            return None
        if len(completed) == len(jobs):
            break
        snapshot = ledger.snapshot()
        if not snapshot["unacknowledged_unknown_requests"]:
            return None
        before = len(completed)
        completed = recover_stage(output, plan, ledger, context, jobs)
        require(
            len(completed) > before,
            "network continuation must add real terminals; not a retry loop",
        )
    return completed


def complete_review_seal(output, plan, phase, completed):
    output = Path(output)
    expected = {
        review_episode_id(plan["batch_id"], s["slot_id"], role)
        for s in phase["eligible_slots"]
        for role in ("A", "B")
    }
    require(
        len(phase["eligible_slots"]) == phase["M"]
        and len(phase["jobs"]) == len(expected) == 2 * phase["M"]
        and {j["episode_id"] for j in phase["jobs"]} == expected,
        "fixed complete 2M registration required",
    )
    require(
        set(completed) == {j["episode_id"] for j in phase["jobs"]},
        "all 2M jobs must have real terminals; no prefix",
    )
    joint_refs, joint_by_task, joint_slots = {}, {}, []
    for slot in phase["eligible_slots"]:
        sid = slot["slot_id"]
        a, b = [completed[review_episode_id(plan["batch_id"], sid, role)] for role in ("A", "B")]
        if all(r.get("actual_model_call_receipt_verified") is True for r in (a, b)):
            joint = resolve_joint_review(a, b, q_native=True)
        else:
            joint = bound(
                dict(
                    schema="v10_joint_process_unknown.v1",
                    protocol_id=plan["batch_id"],
                    policy_id=plan["review_policy_id"],
                    slot_id=sid,
                    task_id=slot["task_id"],
                    q_native=True,
                    joint_valid=False,
                    A_record_id=a["id"],
                    B_record_id=b["id"],
                    A=a,
                    B=b,
                    why_unknown="a fixed process review has an acknowledged missing response",
                    supervision_authority="A",
                )
            )
        persist(joint_path(output, sid).parent, joint)
        joint_refs[sid] = entry(joint_path(output, sid))
        if joint["joint_valid"]:
            joint_slots.append(sid)
            joint_by_task.setdefault(slot["task_id"], []).append(sid)
    terminal = []
    for job in phase["jobs"]:
        r = completed[job["episode_id"]]
        terminal.append(
            dict(
                slot_id=job["slot_id"],
                role=job["role"],
                episode_id=job["episode_id"],
                terminal_kind="paid_model_return"
                if r.get("actual_model_call_receipt_verified") is True
                else "acknowledged_connection_unknown",
                record=entry(job_directory(output, job) / "record/record.json"),
            )
        )
    body = bound(
        dict(
            schema="v10_complete_process_review_seal.v1",
            protocol_id=plan["id"],
            batch_id=plan["batch_id"],
            generation_seal_id=phase["generation_seal"]["id"],
            native_support_id=phase["native_support"]["id"],
            M=phase["M"],
            expected_reviews=2 * phase["M"],
            terminals=terminal,
            returned=sum(t["terminal_kind"] == "paid_model_return" for t in terminal),
            network_unknowns=sum(
                t["terminal_kind"] == "acknowledged_connection_unknown" for t in terminal
            ),
            all_registered_jobs_terminal=True,
            joint_records=joint_refs,
            joint_slot_ids=joint_slots,
            joint_by_task=joint_by_task,
            N=len(joint_by_task),
            mapping_expected_tasks=[t for t in plan["task_ids"] if t in joint_by_task],
            no_prefix_training=True,
        )
    )
    persist(output / "review_seal", body)
    return body


def mapping_jobs(plan, seal):
    return [
        dict(
            kind="mapping",
            task_id=task,
            slot_ids=seal["joint_by_task"][task],
            episode_id=map_episode_id(plan["batch_id"], task),
        )
        for task in seal["mapping_expected_tasks"]
    ]


def complete_mapping_seal(output, plan, review_seal, jobs, completed):
    require(
        jobs == mapping_jobs(plan, review_seal),
        "once-task mapping must retain the entire jointly valid collection",
    )
    require(
        set(completed) == {j["episode_id"] for j in jobs},
        "all once-task mappings require real terminal records",
    )
    terms = [
        dict(
            task_id=j["task_id"],
            episode_id=j["episode_id"],
            terminal_kind="paid_model_return"
            if completed[j["episode_id"]].get("actual_model_call_receipt_verified") is True
            else "acknowledged_connection_unknown",
            record=entry(job_directory(output, j) / "record/record.json"),
        )
        for j in jobs
    ]
    body = bound(
        dict(
            schema="v10_complete_task_mapping_seal.v1",
            protocol_id=plan["id"],
            batch_id=plan["batch_id"],
            review_seal_id=review_seal["id"],
            expected_tasks=len(jobs),
            terminals=terms,
            all_registered_jobs_terminal=True,
            all_joint_states_resolved=all(
                r.get("mapping_status") == "complete" for r in completed.values()
            ),
            mapping_status_counts=dict(
                Counter(r.get("mapping_status", "unknown") for r in completed.values())
            ),
            hard_packages_deleted=False,
        )
    )
    persist(Path(output) / "mapping_seal", body)
    return body


async def run(output=OUTPUT):
    output = Path(output)
    plan = checked_plan(output)
    require(
        (output / "native_support/record.json").is_file(),
        "new complete generation/native seal required",
    )
    with (output / "production_controller.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        stop = asyncio.Event()
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, stop.set)
        ledger = ledger_for(plan)
        runtime = register_runtime(output, plan, ledger)
        phase = register_review_phase(output, plan)
        context = Context(output, plan, phase)
        completed = await execute_stage(
            output, plan, ledger, context, phase["jobs"], stop_requested=stop
        )
        if completed is None:
            return None
        review_seal = complete_review_seal(output, plan, phase, completed)
        jobs = mapping_jobs(plan, review_seal)
        persist(
            output / "mapping_registration",
            bound(
                dict(
                    schema="v10_once_mapping_registration.v1",
                    protocol_id=plan["id"],
                    review_seal_id=review_seal["id"],
                    jobs=jobs,
                    expected_calls=len(jobs),
                )
            ),
        )
        mapped = await execute_stage(output, plan, ledger, context, jobs, stop_requested=stop)
        if mapped is None:
            return None
        mapping_seal = complete_mapping_seal(output, plan, review_seal, jobs, mapped)
        from .v10_material import freeze_material

        material = freeze_material(output, plan, review_seal)
        status(
            output,
            dict(
                at=now(),
                phase="V10_MATERIAL_HANDOFF",
                protocol_id=plan["id"],
                M=phase["M"],
                N=review_seal["N"],
                review_seal_id=review_seal["id"],
                mapping_seal_id=mapping_seal["id"],
                material=material,
                runtime_revision_id=runtime["id"],
                effective_concurrency=runtime["effective_concurrency"],
                budget=ledger.snapshot(),
                training_started=False,
            ),
        )
        return material


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args(argv)
    print(asyncio.run(run(args.output)))


if __name__ == "__main__":
    main()
