"""Resume the text/table experiment with a deterministic, checkpointed source frontier.

No vision dependency, no new training, no selection on Student outcomes. Technical
failures are not financial exclusions. Each physical POST is reserved and saved.
"""

import argparse
import json
import subprocess
import sys
import time
from collections import Counter, defaultdict
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from functools import lru_cache
from pathlib import Path

import cross_market_panel_20260926 as panel
import cross_market_review_transport_20260927 as transport
import cross_market_source_review_revision_05_20260927 as materials
import cross_market_text_frontier_20260927 as frontier
import cross_market_text_table_review_revision_20260927 as semantic

base = materials.base
RAW = materials.RAW.parent / "text_table_mainline_01"
SCRIPT = "trusted_data_synthesis/scripts/run_cross_market_text_mainline_20260927.py"
KIND = "cross_market_text_mainline_protocol"
MODEL = "deepseek-v4-pro"
CONCURRENCY = 16
ATTEMPTS = 2
ISSUER = base.RAW / "issuer_admission_01/admission.json"


def ref(path):
    path = Path(path)
    return dict(path=str(path), sha256=base.sha(path), bytes=path.stat().st_size)


def frozen(reference):
    base.require(ref(reference["path"]) == reference, "text_mainline.frozen_reference")
    return base.read(reference["path"])


def load_inputs():
    financial = base.read(materials.FINANCIAL / "protocol.json")
    candidates = base.read(materials.FINANCIAL / "candidate_tasks.json")
    documents = {
        row["document"]["raw_object_id"]: row
        for path in sorted((materials.FINANCIAL / "documents").glob("*.json"))
        for row in [base.read(path)]
    }
    issuer = base.read(ISSUER)
    items, rejected = frontier.eligible_items(
        candidates["candidates"],
        documents,
        panel.statistics.admission_mapping(issuer),
        financial["public_metric_universe"],
    )
    return financial, documents, items, rejected


def register(root):
    if (RAW / "protocol.json").exists():
        return protocol(root)
    financial, _, items, rejected = load_inputs()
    material_plan = base.read(materials.RAW / "protocol.json")
    manifest = base.read(materials.RAW / "packet_manifest.json")
    composition = [r for r in items if r["task"]["group"] == "composition_required"]
    wanted = {d for r in composition for d in r["task"]["source_exhaustion_review_raw_objects"]}
    packet_rows = [r for r in manifest["packets"] if r["raw_object_id"] in wanted]
    base.require(len(composition) >= 60, "text_mainline.composition_capacity")
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    names = [
        SCRIPT,
        semantic.SCRIPT,
        frontier.SCRIPT,
        "trusted_data_synthesis/scripts/cross_market_panel_revision_05_20260927.py",
        transport.SCRIPT,
        semantic.spans.SCRIPT,
        semantic.spans.line_protocol.SCRIPT,
        semantic.spans.line_protocol.text_projection.SCRIPT,
        panel.SCRIPT,
    ]
    sources = dict(material_plan["sources"])
    for name, digest in financial["sources"].items():
        base.require(
            name not in sources or sources[name] == digest,
            "text_mainline.same_frozen_parent_sources",
        )
        sources[name] = digest
    for name in sorted(set(names) | set(sources)):
        payload = (root / name).read_bytes()
        base.require(
            payload == subprocess.check_output(["git", "show", head + ":" + name], cwd=root),
            "text_mainline.committed_code",
        )
        base.require(
            name not in sources or sources[name] == base.sha(payload),
            "text_mainline.unchanged_parent_code",
        )
        sources[name] = base.sha(payload)
    plan = base.record(
        KIND,
        at=base.now(),
        code_commit=head,
        sources=sources,
        authorization="User explicitly requested return to the original nonvisual mainline and "
        "completion; standing DeepSeek/API/GPU and git-push authorization.",
        correction="Withdraw assistant-added universal visual, separate-provider, two-locator-lane "
        "and mandatory-human gates prospectively. Preserve every prior record and expenditure.",
        references={
            "material_protocol": ref(materials.RAW / "protocol.json"),
            "material_manifest": ref(materials.RAW / "packet_manifest.json"),
            "financial_protocol": ref(materials.FINANCIAL / "protocol.json"),
            "financial_candidates": ref(materials.FINANCIAL / "candidate_tasks.json"),
            "financial_summary": ref(materials.FINANCIAL / "summary.json"),
            "issuer_admission": ref(ISSUER),
        },
        financial_protocol_id=financial["id"],
        material_protocol_id=material_plan["id"],
        review_scope=semantic.REVIEW_SCOPE,
        model=MODEL,
        provider="DeepSeek",
        independent_of_Student_and_Q=True,
        provider_independence_not_claimed=True,
        eligible_candidate_task_ids=sorted(r["task"]["task_id"] for r in composition),
        preflight_counts=dict(Counter(r["task"]["group"] for r in items)),
        preflight_rejections=rejected,
        source_universe=sorted(wanted),
        packet_universe=packet_rows,
        maximum_unique_packets=len(packet_rows),
        maximum_API_attempts=len(packet_rows) * ATTEMPTS,
        maximum_attempts_per_packet=ATTEMPTS,
        maximum_concurrent_requests=CONCURRENCY,
        output_tokens_per_attempt=4096,
        automatic_transport_retries=0,
        technical_failure_policy="At most two recorded attempts, then stop pending; never exclude "
        "a candidate because HTTP/JSON/identity/locator validation failed.",
        semantic_eligibility_policy="Specific unresolved evidence or possible matching aggregate "
        "makes the task not admitted; does not assert an aggregate exists. All decisions retained.",
        selection="Frozen issuer hash roundrobin and endperiod/taskid ordering. Optimistically "
        "keep unreviewed candidates; review whole source reports needed for the first 60. "
        "Close only when those 60 all pass. No first-finished selection or substitution "
        "after panel control failure.",
        empty_text_policy="Record unavailable original content as a text-domain limitation, not "
        "evidence of absence or a universal requirement for image/VLM inspection.",
        quotas=dict.fromkeys(panel.GROUPS, 60),
        old_training_reused=True,
        new_training_updates=0,
        visual_model_calls=0,
        original_PDF_opens=0,
        downstream_evaluation_sessions=4860,
        all_generation_before_private_scoring=True,
        automatic_panel_and_evaluation_handoff=True,
    )
    base.write(RAW / "protocol.json", plan)
    base.emit(
        dict(
            event="text_mainline_registered",
            protocol_id=plan["id"],
            packets_ceiling=len(packet_rows),
            model=MODEL,
        )
    )
    return plan


def protocol(root):
    plan = base.checked(base.read(RAW / "protocol.json"), KIND)
    for name, digest in plan["sources"].items():
        base.require(base.sha(root / name) == digest, "text_mainline.code_unchanged:" + name)
    for reference in plan["references"].values():
        frozen(reference)
    return plan


@lru_cache(maxsize=640)
def packet_at(path, digest):
    packet = base.read(path)
    base.require(base.sha(base.encode(packet)) == digest, "text_mainline.packet_bytes")
    return packet


def request_for(packet, reference):
    projection = semantic.project_packet(packet, reference)
    request = dict(
        model=MODEL,
        response_format={"type": "json_object"},
        max_tokens=4096,
        thinking={"type": "disabled"},
        stream=False,
        messages=[
            dict(role="system", content=semantic.request_instruction()),
            dict(role="user", content=json.dumps(projection["payload"], ensure_ascii=False)),
        ],
    )
    transport.request_bytes(request)
    return projection, request


def key_for(packet_id):
    return base.sha(packet_id)


def review_packet(plan, row, key):
    packet_id = row["packet_id"]
    stem = key_for(packet_id)
    result_path = RAW / "packet_reviews" / (stem + ".json")
    if result_path.exists():
        result = base.checked(base.read(result_path), semantic.PACKET_KIND)
        base.require(
            result["protocol_id"] == plan["id"]
            and result["packet_id"] == packet_id
            and result["packet_sha256"] == row["reference"]["sha256"],
            "text_mainline.cached_packet_identity",
        )
        return result
    packet = packet_at(row["reference"]["path"], row["reference"]["sha256"])
    projection, request = request_for(packet, row["reference"])
    for attempt in range(1, ATTEMPTS + 1):
        directory = RAW / "attempts" / stem / str(attempt)
        outcome = directory / "outcome.json"
        if outcome.exists():
            continue
        if (directory / "reservation.json").exists():
            # An interrupted request may have been billed. Preserve it; the second
            # bounded attempt remains available without pretending the first failed.
            base.write(outcome, dict(status="INTERRUPTED_UNSETTLED_NOT_REFUNDED", at=base.now()))
            continue
        base.write(
            directory / "reservation.json",
            dict(
                protocol_id=plan["id"],
                packet_id=packet_id,
                attempt=attempt,
                request_sha256=base.sha(base.encode(request)),
                at=base.now(),
            ),
        )
        try:
            response = transport.Provider(directory, key)(request)
            base.require(response["finish_reason"] == "stop", "text_mainline.complete_reply")
            payload = json.loads(response["content"])
            semantic.validate_semantic_response(packet, projection, payload)
            physical = directory / "physical_requests" / base.sha(base.encode(request))
            execution = dict(
                protocol_id=plan["id"],
                packet_id=packet_id,
                packet_sha256=row["reference"]["sha256"],
                model=response["model"],
                provider="DeepSeek",
                request_reference=ref(physical / "request.json"),
                raw_response_reference=ref(physical / "raw_response.json"),
                payload_sha256=base.sha(base.encode(payload)),
                finish_reason=response["finish_reason"],
                independent_of_Student_and_Q=True,
            )
            reviewed = semantic.build_packet_review(
                review_protocol_id=plan["id"],
                packet=packet,
                projection=projection,
                payload=payload,
                execution=execution,
            )
            base.write(directory / "payload.json", payload)
            base.write(result_path, reviewed)
            base.write(
                outcome,
                dict(
                    status="TEXT_SEMANTIC_RESPONSE_RECORDED",
                    at=base.now(),
                    usage=response["usage"],
                    packet_review_id=reviewed["id"],
                ),
            )
            return reviewed
        except Exception as error:
            # No provider error text or credential is printed/persisted here.
            safe_reason = (
                str(error)
                if isinstance(error, ValueError)
                and str(error).startswith(("cross_market.", "review_spans.", "text_table_review."))
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
    return None


def status(**fields):
    value = dict(at=base.now(), **fields)
    base.write(RAW / "status.json", value, immutable=False)
    base.emit(value)
    return value


def run(root):
    plan = protocol(root)
    with base.locked(RAW / "run.lock"):
        return _run(root, plan)


def _run(root, plan):
    material_plan = frozen(plan["references"]["material_protocol"])
    manifest = frozen(plan["references"]["material_manifest"])
    _, _, items, _ = load_inputs()
    composition = [r for r in items if r["task"]["group"] == "composition_required"]
    base.require(
        sorted(r["task"]["task_id"] for r in composition) == plan["eligible_candidate_task_ids"],
        "text_mainline.frozen_candidate_order",
    )
    packets_by_doc = defaultdict(list)
    for row in plan["packet_universe"]:
        packets_by_doc[row["raw_object_id"]].append(row)
    sources = {r["document"]["raw_object_id"]: r for r in material_plan["documents"]}
    reviews = {
        r["task_id"]: base.checked(r, semantic.REVIEW_KIND)
        for path in (RAW / "task_reviews").glob("*.json")
        for r in [base.read(path)]
    }
    completed = {
        r["packet_id"]: base.checked(r, semantic.PACKET_KIND)
        for path in (RAW / "packet_reviews").glob("*.json")
        for r in [base.read(path)]
    }
    base.require(
        all(r["protocol_id"] == plan["id"] for r in reviews.values())
        and all(r["protocol_id"] == plan["id"] for r in completed.values()),
        "text_mainline.resumed_records_same_protocol",
    )
    technical_tasks = [
        tid for tid, r in reviews.items() if r["status"] == "PENDING_TECHNICAL_REVIEW"
    ]
    if technical_tasks:
        return status(
            state="TASK_REVIEW_TECHNICAL_PENDING",
            task_ids=technical_tasks,
            saved_packet_reviews=len(completed),
        )
    key = transport.credential()
    wave = len(list((RAW / "waves").glob("*.json")))
    while True:
        rejected = {
            tid
            for tid, r in reviews.items()
            if not r["passed"] and r["status"] != "PENDING_TECHNICAL_REVIEW"
        }
        selected = frontier.next_selected(composition, rejected)
        base.require(len(selected) == 60, "text_mainline.insufficient_semantically_eligible_tasks")
        if all(reviews.get(r["task"]["task_id"], {}).get("passed") is True for r in selected):
            break
        wanted = {d for r in selected for d in r["task"]["source_exhaustion_review_raw_objects"]}
        pending = sorted(
            (r for d in wanted for r in packets_by_doc[d] if r["packet_id"] not in completed),
            key=lambda r: r["packet_id"],
        )
        wave += 1
        base.write(
            RAW / "waves" / f"{wave:03d}.json",
            dict(
                at=base.now(),
                selected_candidate_task_ids=[r["task"]["task_id"] for r in selected],
                raw_object_ids=sorted(wanted),
                packet_ids=[r["packet_id"] for r in pending],
                previous_semantically_ineligible=sorted(rejected),
            ),
        )
        failures = []
        started = time.monotonic()
        status(
            state="TEXT_REVIEW_RUNNING",
            wave=wave,
            wave_packets=len(pending),
            wave_packets_completed=0,
            saved_packet_reviews=len(completed),
            selected_source_documents=len(wanted),
            GPU_processes=0,
        )
        with ThreadPoolExecutor(max_workers=CONCURRENCY) as pool:
            remaining = iter(pending)
            futures, count = {}, 0
            for row in remaining:
                futures[pool.submit(review_packet, plan, row, key)] = row
                if len(futures) == CONCURRENCY:
                    break
            while futures:
                ready, _ = wait(futures, return_when=FIRST_COMPLETED)
                for future in ready:
                    row = futures.pop(future)
                    count += 1
                    try:
                        result = future.result()
                    except Exception as error:
                        result = None
                        base.emit(
                            dict(
                                event="packet_execution_error",
                                packet_id=row["packet_id"],
                                error_type=type(error).__name__,
                            )
                        )
                    if result is None:
                        failures.append(row["packet_id"])
                    else:
                        completed[row["packet_id"]] = result
                    if count % 16 == 0 or count == len(pending):
                        elapsed = time.monotonic() - started
                        status(
                            state="TEXT_REVIEW_RUNNING",
                            wave=wave,
                            wave_packets=len(pending),
                            wave_packets_completed=count,
                            saved_packet_reviews=len(completed),
                            technical_failed_packets=len(failures),
                            elapsed_seconds=elapsed,
                            observed_remaining_seconds=elapsed / count * (len(pending) - count),
                            remaining_estimate_is_wave_only=True,
                            GPU_processes=0,
                        )
                # Stop dispatching on the first exhausted/structural technical failure.
                # Already in-flight requests settle and are saved, not abandoned.
                if not failures:
                    while len(futures) < CONCURRENCY:
                        row = next(remaining, None)
                        if row is None:
                            break
                        futures[pool.submit(review_packet, plan, row, key)] = row
        if failures:
            return status(
                state="TEXT_REVIEW_TECHNICAL_PENDING",
                failed_packet_ids=failures,
                saved_packet_reviews=len(completed),
                candidate_exclusions_from_technical_failure=0,
            )
        done_docs = {
            d
            for d, rows in packets_by_doc.items()
            if all(r["packet_id"] in completed for r in rows)
        }
        for item in composition:
            task = item["task"]
            tid = task["task_id"]
            if tid in reviews or not set(task["source_exhaustion_review_raw_objects"]) <= done_docs:
                continue
            task_docs = task["source_exhaustion_review_raw_objects"]
            packet_materials = {
                r["packet_id"]: packet_at(r["reference"]["path"], r["reference"]["sha256"])
                for d in task_docs
                for r in packets_by_doc[d]
            }
            document_texts = {d: frozen(sources[d]["page_text_reference"]) for d in task_docs}
            result = semantic.assess_task(
                task,
                material_plan,
                manifest,
                packet_materials,
                completed,
                document_texts,
                review_protocol_id=plan["id"],
            )
            base.write(RAW / "task_reviews" / (base.sha(tid) + ".json"), result)
            reviews[tid] = result
            if result["status"] == "PENDING_TECHNICAL_REVIEW":
                return status(
                    state="TASK_REVIEW_TECHNICAL_PENDING",
                    task_id=tid,
                    saved_packet_reviews=len(completed),
                )
        status(
            state="TEXT_REVIEW_WAVE_ASSESSED",
            wave=wave,
            saved_packet_reviews=len(completed),
            task_status_counts=dict(Counter(r["status"] for r in reviews.values())),
        )
    closure = dict(
        complete=True,
        selected_candidate_task_ids=[r["task"]["task_id"] for r in selected],
        eligible_candidate_task_ids=plan["eligible_candidate_task_ids"],
        semantically_rejected_candidate_task_ids=sorted(rejected),
        reviewed_candidate_task_ids=sorted(reviews),
        selection_method="optimistic_pending_frontier_closed_under_original_issuer_roundrobin",
    )
    bundle = base.record(
        semantic.BUNDLE_KIND,
        at=base.now(),
        review_protocol_id=plan["id"],
        review_protocol_reference=ref(RAW / "protocol.json"),
        financial_protocol_id=plan["financial_protocol_id"],
        review_scope=semantic.REVIEW_SCOPE,
        selection_closure=closure,
        reviews=[reviews[k] for k in sorted(reviews)],
        independent_of_Student_and_Q=True,
        provider_independence_not_claimed=True,
    )
    bundle_path = RAW / "composition_reviews.json"
    if bundle_path.exists():
        existing = base.read(bundle_path)
        semantic.validate_bundle(existing, plan["financial_protocol_id"])
        base.require(
            existing["review_protocol_id"] == plan["id"]
            and existing["selection_closure"] == closure
            and existing["reviews"] == bundle["reviews"],
            "text_mainline.resumed_bundle_same_evidence_and_closure",
        )
    else:
        semantic.validate_bundle(bundle, plan["financial_protocol_id"])
        base.write(bundle_path, bundle)
    status(
        state="TEXT_REVIEW_FRONTIER_COMPLETE",
        saved_packet_reviews=len(completed),
        task_status_counts=dict(Counter(r["status"] for r in reviews.values())),
        selected_composition_tasks=60,
    )
    import cross_market_panel_revision_05_20260927 as compiler

    compiler.register(root, bundle_path)
    report = compiler.run(root)
    if report.get("passed") is not True:
        return status(state="PANEL_NOT_ADMITTED", panel_summary=report)
    import run_fixed_kernel_cross_market_evaluation_20260926 as evaluator

    refs_path = compiler.RAW / "evaluation_panel_references.json"
    evaluator.register(root, refs_path)
    evaluator.start(root)
    return status(
        state="EVALUATION_LAUNCHED",
        panel_references=ref(refs_path),
        evaluation_root=str(evaluator.RAW),
        evaluation_sessions=4860,
    )


def start(root):
    protocol(root)
    path = RAW / "coordinator.log"
    with path.open("ab") as log:
        process = subprocess.Popen(
            [sys.executable, str(root / SCRIPT), "run", "--root", str(root)],
            cwd=root,
            stdout=log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
    base.emit(dict(event="text_mainline_started", pid=process.pid, log=str(path)))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("register", "run", "start", "status"))
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    if args.action == "status":
        print(json.dumps(base.read(RAW / "status.json"), ensure_ascii=False, indent=2))
    else:
        globals()[args.action](args.root.resolve())


if __name__ == "__main__":
    main()
