"""Finite real text-assistance pilot, separate from the zero-API material phase.

Five deterministic original packets, both fixed models, at most ten POSTs.
No task selection, source certificate, visual claim, Student or scoring.
"""

import argparse
import json
import subprocess
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import cross_market_repaired_geometry_execution_20260926 as isolated
import cross_market_review_request_projection_20260927 as projection
import cross_market_review_transport_20260927 as transport
import cross_market_source_review_20260926 as core
import cross_market_source_review_revision_05_20260927 as materials

base = core.base
RAW = materials.RAW.parent / "source_review_assistance_pilot_01"
SCRIPT = "trusted_data_synthesis/scripts/run_cross_market_review_pilot_20260927.py"
PROJECTION_SCRIPT = (
    "trusted_data_synthesis/scripts/cross_market_review_request_projection_20260927.py"
)
KIND = "cross_market_source_review_assistance_execution_protocol"
PROVIDER_EVIDENCE = {
    "checked_on": "2026-09-27 Asia/Shanghai",
    "chat_api": "https://api-docs.deepseek.com/api/create-chat-completion/",
    "JSON_contract": "https://api-docs.deepseek.com/guides/json_mode/",
    "model_contract": "https://api-docs.deepseek.com/quick_start/pricing/",
    "release_history": "https://api-docs.deepseek.com/updates/",
    "models": transport.MODELS,
    "context_length_documented": "1M",
    "thinking_explicitly_disabled": True,
    "JSON_and_4096_output_supported": True,
    "provider_tokenizer_verified": False,
    "request_bytes_guard_not_exact_token_count": True,
}


def save(path, value):
    base.require(Path(path).resolve().is_relative_to(RAW.resolve()), "review_pilot_output_root")
    base.write(path, value)


def frozen_ref(reference):
    base.require(materials.ref(Path(reference["path"])) == reference, "review_pilot_parent_bytes")
    return base.read(reference["path"])


def select_packets(manifest):
    rows = sorted(manifest["packets"], key=lambda row: row["packet_id"])
    largest = max(rows, key=lambda row: (row["reference"]["bytes"], row["packet_id"]))
    selected = {row["packet_id"]: row for row in [*rows[:4], largest]}
    base.require(len(rows) == 6099 and len(selected) == 5, "review_pilot_fixed_five")
    return [selected[key] for key in sorted(selected)]


def request_for(packet, reference, lane):
    view = projection.project_packet(packet, reference)
    rendered = projection.render_request(
        packet,
        view,
        lane,
        transport.MODELS[lane],
        maximum_request_bytes=transport.MAX_REQUEST_BYTES,
        transport_fields={"thinking": {"type": "disabled"}, "stream": False},
    )
    body = json.loads(rendered.body)
    base.require(transport.request_bytes(body) == rendered.body, "review_pilot_exact_wire_bytes")
    return view, rendered, body


def register(root):
    if (RAW / "protocol.json").exists():
        return protocol(root)
    references = {
        "material_protocol": materials.ref(materials.RAW / "protocol.json"),
        "material_manifest": materials.ref(materials.RAW / "packet_manifest.json"),
        "financial_summary": materials.ref(materials.FINANCIAL / "summary.json"),
    }
    parent = base.checked(
        frozen_ref(references["material_protocol"]), "cross_market_source_review_protocol"
    )
    manifest = base.checked(
        frozen_ref(references["material_manifest"]), "cross_market_source_review_packet_manifest"
    )
    base.require(
        manifest["protocol_id"] == parent["id"]
        and manifest["packet_count"] == 6099
        and manifest["status"] == "PACKETS_PREPARED_NOT_SEMANTICALLY_REVIEWED"
        and manifest["API_authorized"] is False,
        "review_pilot_exact_unreviewed_parent",
    )
    selected = select_packets(manifest)
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    sources = dict(parent["sources"])
    for name in (SCRIPT, PROJECTION_SCRIPT, transport.SCRIPT):
        payload = (root / name).read_bytes()
        base.require(
            payload == subprocess.check_output(["git", "show", head + ":" + name], cwd=root),
            "review_pilot_committed_code",
        )
        sources[name] = base.sha(payload)
    for name, digest in sources.items():
        base.require(base.sha(root / name) == digest, "review_pilot_frozen_parent_code")
    requests = []
    for row in selected:
        packet = frozen_ref(row["reference"])
        for lane in core.LANES:
            view, rendered, body = request_for(packet, row["reference"], lane)
            requests.append(
                dict(
                    packet_id=packet["id"],
                    lane=lane,
                    projection_id=view["id"],
                    request_sha256=base.sha(rendered.body),
                    request_bytes=len(rendered.body),
                    original_packet_bytes=row["reference"]["bytes"],
                )
            )
    base.require(not any(RAW.glob("**/*attempt*.json")), "review_pilot_no_unregistered_attempts")
    plan = base.record(
        KIND,
        at=base.now(),
        code_commit=head,
        sources=sources,
        references=references,
        parent_material_protocol_id=parent["id"],
        parent_manifest_id=manifest["id"],
        selected_packets=selected,
        requests=requests,
        selection="Four lowest packet content IDs plus largest original packet JSON by bytes; "
        "fixed before API outputs",
        maximum_API_attempts=10,
        maximum_scheduled_attempts_per_job=1,
        maximum_concurrent_requests=2,
        model_by_lane=transport.MODELS,
        output_tokens_per_attempt=4096,
        maximum_output_tokens=40960,
        timeout_seconds=120,
        maximum_request_bytes=transport.MAX_REQUEST_BYTES,
        no_automatic_retries=True,
        no_model_discovery=True,
        no_model_fallback=True,
        provider_contract_evidence=PROVIDER_EVIDENCE,
        user_authorization="Continue and advance the overall experiment; standing project "
        "API/DeepSeek authorization. This is an explicitly separate finite execution "
        "allocation, not a mutation of the material stage's zero API budget.",
        semantic_certificates_authorized=False,
        original_PDF_opens=0,
        visual_review_calls=0,
        Student_calls=0,
        new_training_updates=0,
    )
    save(RAW / "protocol.json", plan)
    approval = base.record(
        "cross_market_source_review_budget_approval",
        protocol_id=parent["id"],
        packet_manifest_id=manifest["id"],
        execution_protocol_id=plan["id"],
        approved=True,
        approved_by="user_authorized_experiment_controller",
        approval_record=plan["user_authorization"],
        maximum_API_attempts=10,
        maximum_attempts_per_job=core.MAX_ATTEMPTS_PER_JOB,
        maximum_output_tokens_per_attempt=4096,
        model_by_lane=transport.MODELS,
        provider_contract_verified=True,
        provider_contract_evidence=PROVIDER_EVIDENCE,
    )
    core.validate_budget(parent, manifest, approval)
    save(RAW / "budget_approval.json", approval)
    base.emit(dict(event="source_review_real_pilot_registered", id=plan["id"], attempts=10))
    return plan


def protocol(root):
    plan = base.checked(base.read(RAW / "protocol.json"), KIND)
    base.require(
        plan["maximum_API_attempts"] == 10
        and len(plan["selected_packets"]) == 5
        and plan["model_by_lane"] == transport.MODELS
        and plan["maximum_scheduled_attempts_per_job"] == 1
        and plan["maximum_concurrent_requests"] == 2
        and plan["maximum_request_bytes"] == transport.MAX_REQUEST_BYTES
        and plan["output_tokens_per_attempt"] == 4096
        and plan["maximum_output_tokens"] == 40960
        and plan["timeout_seconds"] == 120,
        "review_pilot_fixed_budget",
    )
    for name, digest in plan["sources"].items():
        base.require(base.sha(root / name) == digest, "review_pilot_immutable_code")
    for reference in plan["references"].values():
        frozen_ref(reference)
    manifest = frozen_ref(plan["references"]["material_manifest"])
    base.require(
        plan["selected_packets"] == select_packets(manifest)
        and len(plan["requests"]) == 10
        and {(r["packet_id"], r["lane"]) for r in plan["requests"]}
        == {(r["packet_id"], lane) for r in plan["selected_packets"] for lane in core.LANES},
        "review_pilot_exact_fixed_jobs",
    )
    return plan


def run_job(plan, parent, manifest, approval, row, lane, key):
    packet = frozen_ref(row["reference"])
    job = core.job_key(packet["id"], lane)
    existing = sorted((RAW / "scan_results").glob(job + ".*.json"))
    if existing:
        base.require(len(existing) == 1, "review_pilot_one_result_per_job")
        result = base.checked(base.read(existing[0]), "cross_market_source_scan_result")
        base.require(
            result["protocol_id"] == parent["id"]
            and result["packet_id"] == packet["id"]
            and result["lane"] == lane
            and result["attempt"] == 1,
            "review_pilot_cached_job_identity",
        )
        return result
    base.require(
        not list((RAW / "API_attempts").glob(job + ".*.json")),
        "review_pilot_unsettled_attempt_no_replay",
    )
    view, rendered, body = request_for(packet, row["reference"], lane)
    binding = next(
        r for r in plan["requests"] if r["packet_id"] == packet["id"] and r["lane"] == lane
    )
    base.require(
        binding["projection_id"] == view["id"]
        and binding["request_sha256"] == base.sha(rendered.body),
        "review_pilot_registered_request",
    )
    save(RAW / "projections" / (packet["id"].split(":")[-1] + ".json"), view)
    ns = isolated.isolated_namespace(core, RAW=RAW)
    ns["request_payload"] = lambda packet_arg, lane_arg, model_arg: body
    result = ns["run_scan_attempt"](
        parent, manifest, packet, lane, approval, transport.Provider(RAW, key)
    )
    base.emit(
        dict(
            event="source_review_pilot_job_saved",
            packet_id=packet["id"],
            lane=lane,
            status=result["status"],
            attempt=result["attempt"],
        )
    )
    return result


def run(root):
    plan = protocol(root)
    with base.locked(RAW / "controller.lock"):
        if (RAW / "summary.json").exists():
            return base.read(RAW / "summary.json")
        parent = frozen_ref(plan["references"]["material_protocol"])
        manifest = frozen_ref(plan["references"]["material_manifest"])
        approval = base.read(RAW / "budget_approval.json")
        core.validate_budget(parent, manifest, approval)
        key = transport.credential()
        jobs = [(row, lane) for row in plan["selected_packets"] for lane in core.LANES]
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [
                executor.submit(run_job, plan, parent, manifest, approval, row, lane, key)
                for row, lane in jobs
            ]
            results = [future.result() for future in futures]
        status_counts = dict(Counter(r["status"] for r in results))
        result = base.record(
            "cross_market_source_review_assistance_pilot_completed",
            at=base.now(),
            execution_protocol_id=plan["id"],
            status="FINITE_TEXT_PILOT_COMPLETE_NOT_ADMITTED",
            jobs=len(results),
            status_counts=status_counts,
            physical_attempts=len(list((RAW / "API_attempts").glob("*.json"))),
            usage_totals={
                k: sum(
                    (r.get("provider_response") or {}).get("usage", {}).get(k, 0) for r in results
                )
                for k in ("prompt_tokens", "completion_tokens", "total_tokens")
            },
            attempts_with_unknown_token_usage=sum(
                not (r.get("provider_response") or {}).get("usage") for r in results
            ),
            usage_totals_are_reported_usage_not_proof_of_zero_cost_for_failed_calls=True,
            results=[
                dict(packet_id=r["packet_id"], lane=r["lane"], id=r["id"], status=r["status"])
                for r in results
            ],
            full_corpus_dispatched=False,
            source_certificates=0,
            independent_reviews=0,
            visual_reviews=0,
            Student_calls=0,
            new_training_updates=0,
        )
        save(RAW / "summary.json", result)
        base.emit({k: v for k, v in result.items() if k != "results"})
        return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("register", "run"))
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    {"register": register, "run": run}[args.action](args.root.resolve())


if __name__ == "__main__":
    main()
