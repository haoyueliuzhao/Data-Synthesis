"""Resolve concrete task-window doubts without turning locator noise into exclusion.

This bounded text-only phase runs only after complete packet review. It preserves
every initial judgment and uses the same provider, no Student/Q or visual model.
"""

import argparse
import json
import subprocess
import types
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import cross_market_text_task_adjudication_20260927 as adjudication
import run_cross_market_text_schema_recovery_20260927 as recovery

original, base = recovery.original, recovery.base
SCRIPT = "trusted_data_synthesis/scripts/run_cross_market_text_task_resolution_20260927.py"
ROOT = original.RAW / "task_adjudication_01"
RECORD = ROOT / "protocol.json"
KIND = "cross_market_text_task_adjudication_protocol"
MAX_OUTPUT = 16384
MAX_REQUEST_BYTES = 900000
CONCURRENCY = 8


def register(root):
    if RECORD.exists():
        return protocol(root)
    parent = original.protocol(root)
    repair = recovery.revision(root)
    base.require(
        not list((original.RAW / "task_reviews").glob("*.json")),
        "task_adjudication.registered_before_task_admission",
    )
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    sources = {}
    for name in (SCRIPT, adjudication.SCRIPT, recovery.SCRIPT):
        payload = (root / name).read_bytes()
        base.require(
            payload == subprocess.check_output(["git", "show", head + ":" + name], cwd=root),
            "task_adjudication.committed_code",
        )
        sources[name] = base.sha(payload)
    value = base.record(
        KIND,
        at=base.now(),
        code_commit=head,
        sources=sources,
        parent_protocol=original.ref(original.RAW / "protocol.json"),
        parent_protocol_id=parent["id"],
        schema_recovery=original.ref(recovery.RECORD),
        schema_recovery_id=repair["id"],
        eligible_candidate_task_ids=parent["eligible_candidate_task_ids"],
        maximum_tasks=len(parent["eligible_candidate_task_ids"]),
        maximum_attempts_per_task=2,
        maximum_POSTs=len(parent["eligible_candidate_task_ids"]) * 2,
        maximum_concurrent_requests=CONCURRENCY,
        maximum_output_tokens=MAX_OUTPUT,
        maximum_request_bytes=MAX_REQUEST_BYTES,
        model=original.MODEL,
        provider="DeepSeek",
        independent_of_Student_and_Q=True,
        provider_independence_not_claimed=True,
        visual_calls=0,
        original_PDF_opens=0,
        new_Student_calls=0,
        new_training_updates=0,
        saved_packet_reviews_at_registration=len(
            list((original.RAW / "packet_reviews").glob("*.json"))
        ),
        observed_before_registration="Initial 442 packet replies and one bounded schema repair "
        "have been observed; no task admission yet. Limited "
        "inspection found unknown-concept equity/remuneration amounts and segment-local missing "
        "cash-flow statements tagged as potential target ambiguities. This is an engineering "
        "clarification prompted by observed source-review noise, not an outcome-blind change.",
        policy="Already-PASS tasks require no extra call. Only complete-text semantic pending "
        "tasks receive original evidence plus the actual target metric/window. Every doubt "
        "must be explicitly adjudicated. Matching aggregates or unresolved evidence remain "
        "not admitted; provider/schema failures remain technical pending, never a replacement.",
        preserved_initial_judgments=True,
        source_selection_rule_unchanged=True,
        user_authorization="Continue the original text/table mainline; resolve concrete evidence "
        "doubts within this fixed source pool under standing API authorization.",
    )
    base.write(RECORD, value)
    base.emit(
        dict(
            event="task_adjudication_registered",
            id=value["id"],
            maximum_POSTs=value["maximum_POSTs"],
        )
    )
    return value


def protocol(root):
    value = base.checked(base.read(RECORD), KIND)
    parent = original.protocol(root)
    recovery.revision(root)
    base.require(
        value["parent_protocol_id"] == parent["id"]
        and value["parent_protocol"] == original.ref(original.RAW / "protocol.json")
        and value["schema_recovery"] == original.ref(recovery.RECORD),
        "task_adjudication.frozen_parents",
    )
    for name, digest in value["sources"].items():
        base.require(base.sha(root / name) == digest, "task_adjudication.frozen_code")
    return value


def provider_class():
    transport = original.transport
    scope = {
        **vars(transport),
        "MAX_REQUEST_BYTES": MAX_REQUEST_BYTES,
        "core": types.SimpleNamespace(MAX_OUTPUT_TOKENS=MAX_OUTPUT),
    }
    scope["request_bytes"] = types.FunctionType(transport.request_bytes.__code__, scope)
    invoke = types.FunctionType(transport.Provider.__call__.__code__, scope)
    return type("AdjudicationProvider", (transport.Provider,), {"__call__": invoke})


def resolve_one(plan, task, initial, packets, key):
    if initial["status"] not in {"PENDING_TASK_EVIDENCE", "PENDING_POTENTIAL_AGGREGATE"}:
        return initial
    tid, stem = task["task_id"], base.sha(task["task_id"])
    base.require(tid in plan["eligible_candidate_task_ids"], "task_adjudication.fixed_candidate")
    directory = ROOT / "tasks" / stem
    base.write(directory / "initial_review.json", initial)
    saved_path = directory / "resolved_review.json"
    if saved_path.exists():
        value = base.checked(base.read(saved_path), original.semantic.REVIEW_KIND)
        base.require(
            value["baseline_review_id"] == initial["id"]
            and value["adjudication_protocol_id"] == plan["id"],
            "task_adjudication.same_saved_initial_review",
        )
        return value
    request = adjudication.request_for(task, initial, packets)
    Provider = provider_class()
    request_hash = base.sha(base.encode(request))
    for attempt in (1, 2):
        attempt_root = directory / "attempts" / str(attempt)
        reservation, outcome = attempt_root / "reservation.json", attempt_root / "outcome.json"
        if outcome.exists():
            continue
        if reservation.exists():
            base.write(outcome, dict(status="INTERRUPTED_UNSETTLED_NOT_REFUNDED", at=base.now()))
            continue
        base.write(
            reservation,
            dict(
                protocol_id=plan["id"],
                task_id=tid,
                baseline_review_id=initial["id"],
                attempt=attempt,
                request_sha256=request_hash,
                at=base.now(),
            ),
        )
        try:
            response = Provider(attempt_root, key)(request)
            base.require(response["finish_reason"] == "stop", "task_adjudication.complete_reply")
            payload = json.loads(response["content"])
            physical = attempt_root / "physical_requests" / request_hash
            execution = dict(
                protocol_id=plan["id"],
                protocol_reference=original.ref(RECORD),
                task_id=tid,
                baseline_review_id=initial["id"],
                model=response["model"],
                provider="DeepSeek",
                request_reference=original.ref(physical / "request.json"),
                raw_response_reference=original.ref(physical / "raw_response.json"),
                payload_sha256=base.sha(base.encode(payload)),
                finish_reason=response["finish_reason"],
                independent_of_Student_and_Q=True,
            )
            result = adjudication.resolve_task(initial, payload, execution)
            base.write(attempt_root / "payload.json", payload)
            base.write(saved_path, result)
            base.write(
                outcome,
                dict(
                    status="TASK_EVIDENCE_ADJUDICATED",
                    at=base.now(),
                    usage=response["usage"],
                    review_id=result["id"],
                ),
            )
            return result
        except Exception as error:
            safe_reason = (
                str(error)
                if isinstance(error, ValueError) and str(error).startswith("cross_market.")
                else None
            )
            base.write(
                outcome,
                dict(
                    status="TECHNICAL_FAILURE_NOT_REFUNDED",
                    at=base.now(),
                    error_type=type(error).__name__,
                    validation_reason=safe_reason,
                ),
            )
    raise ValueError("cross_market.task_adjudication.exhausted_technical_attempts:" + tid)


def execution_namespace(plan):
    repair = base.read(recovery.RECORD)
    namespace = recovery.execution_namespace(repair, original.ref(recovery.RECORD))
    namespace["SCRIPT"] = SCRIPT
    original_semantic = original.semantic
    key = original.transport.credential()
    pool, futures = ThreadPoolExecutor(max_workers=CONCURRENCY), {}

    def assess_task(
        task,
        material_plan,
        manifest,
        packet_materials,
        packet_reviews,
        document_texts,
        *,
        review_protocol_id,
    ):
        # Schedule only fully reviewed source pairs, using the same frozen candidate
        # universe that the parent will assess. No review completion order selects tasks.
        by_doc = {}
        for row in manifest["packets"]:
            by_doc.setdefault(row["raw_object_id"], []).append(row)
        done = {
            d for d, rows in by_doc.items() if all(r["packet_id"] in packet_reviews for r in rows)
        }
        sources = {r["document"]["raw_object_id"]: r for r in material_plan["documents"]}

        def prepare(candidate):
            ids = candidate["source_exhaustion_review_raw_objects"]
            packets = {
                r["packet_id"]: namespace["packet_at"](
                    r["reference"]["path"], r["reference"]["sha256"]
                )
                for d in ids
                for r in by_doc[d]
            }
            texts = {d: original.frozen(sources[d]["page_text_reference"]) for d in ids}
            initial = original_semantic.assess_task(
                candidate,
                material_plan,
                manifest,
                packets,
                packet_reviews,
                texts,
                review_protocol_id=review_protocol_id,
            )
            return resolve_one(plan, candidate, initial, packets, key)

        for candidate in material_plan["tasks"]:
            tid = candidate["task_id"]
            if (
                tid not in futures
                and tid in plan["eligible_candidate_task_ids"]
                and set(candidate["source_exhaustion_review_raw_objects"]) <= done
            ):
                futures[tid] = pool.submit(prepare, candidate)
        return futures[task["task_id"]].result()

    namespace["semantic"] = types.SimpleNamespace(
        **{**vars(original_semantic), "assess_task": assess_task}
    )

    def record(kind, **fields):
        if kind == original_semantic.BUNDLE_KIND:
            fields["task_adjudication_protocol_reference"] = original.ref(RECORD)
            fields["task_adjudication_protocol_id"] = plan["id"]
        return base.record(kind, **fields)

    namespace["base"] = types.SimpleNamespace(**{**vars(base), "record": record})
    return namespace, pool


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("register", "run", "start", "status"))
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    root = args.root.resolve()
    if args.action == "register":
        register(root)
        return
    plan = protocol(root)
    if args.action == "status":
        base.emit(base.read(original.RAW / "status.json"))
        return
    namespace, pool = execution_namespace(plan)
    try:
        namespace[args.action](root)
    except Exception as error:
        original.status(
            state="MAINLINE_TECHNICAL_PENDING",
            error_type=type(error).__name__,
            reason=str(error) if str(error).startswith("cross_market.") else None,
        )
        raise
    finally:
        pool.shutdown(wait=True)


if __name__ == "__main__":
    main()
