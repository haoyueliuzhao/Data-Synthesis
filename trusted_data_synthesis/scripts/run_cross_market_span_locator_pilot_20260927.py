"""Third bounded pilot: declared page-coordinate span selection, not old reply repair."""

import argparse
import copy
import subprocess
from pathlib import Path

import cross_market_review_span_locator_20260927 as spans
import run_cross_market_line_locator_pilot_20260927 as previous

origin = previous.prior
base, core, transport = origin.base, origin.core, origin.transport
RAW = previous.RAW.parent / "source_review_span_locator_pilot_03"
SCRIPT = "trusted_data_synthesis/scripts/run_cross_market_span_locator_pilot_20260927.py"


def save(path, value):
    base.require(Path(path).resolve().is_relative_to(RAW.resolve()), "span_pilot_output_root")
    base.write(path, value)


def request_for(packet, reference, lane):
    ns = origin.isolated.isolated_namespace(origin, projection=spans)
    return ns["request_for"](packet, reference, lane)


def register(root):
    if (RAW / "protocol.json").exists():
        return protocol(root)
    base.require(
        not any((RAW / "API_attempts").glob("*.json"))
        and not any((RAW / "physical_requests").glob("*/*.json"))
        and not any((RAW / "scan_results").glob("*.json")),
        "span_pilot_no_unregistered_attempts",
    )
    parent = previous.protocol(root)
    completion_ref = origin.materials.ref(previous.RAW / "summary.json")
    done = base.checked(
        origin.frozen_ref(completion_ref), "cross_market_source_review_assistance_pilot_completed"
    )
    base.require(
        done["execution_protocol_id"] == parent["id"]
        and done["physical_attempts"] == 10
        and done["status_counts"]
        == {
            "ASSISTANCE_RESPONSE_SAVED_NOT_ADMITTED": 6,
            "SCAN_ATTEMPT_FAILED_NOT_REFUNDED": 4,
        },
        "span_pilot_preserved_second_results",
    )
    references = dict(
        parent["references"],
        previous_pilot_protocol=origin.materials.ref(previous.RAW / "protocol.json"),
        previous_pilot_summary=completion_ref,
    )
    sources = dict(parent["sources"])
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    for name in (SCRIPT, spans.SCRIPT):
        payload = (root / name).read_bytes()
        base.require(
            payload == subprocess.check_output(["git", "show", head + ":" + name], cwd=root),
            "span_pilot_committed_code",
        )
        sources[name] = base.sha(payload)
    requests = []
    for row in parent["selected_packets"]:
        packet = origin.frozen_ref(row["reference"])
        for lane in core.LANES:
            view, rendered, _ = request_for(packet, row["reference"], lane)
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
    body = {k: copy.deepcopy(v) for k, v in parent.items() if k not in {"id", "schema_version"}}
    body.update(
        at=base.now(),
        code_commit=head,
        sources=sources,
        references=references,
        requests=requests,
        execution_revision=3,
        previous_pilot_id=parent["id"],
        locator_contract="Two declared unordered real-line boundaries define the smallest original "
        "page-coordinate interval containing both. Every supplied segment intersection is retained "
        "as exact evidence with range-group and overlap lineage. Missing coverage rejects. "
        "Fragments are not independent financial observations. Strict JSON, no old-reply repair.",
        inspected_before_registration="Both earlier pilots observed. Pilot02 has six valid "
        "nonempty locator responses and four failures: one invalid JSON and three with reversed "
        "or cross-segment ranges. This broadens locator representation prospectively, not source "
        "semantics or financial admission. Not outcome-blind; same five packets and both models.",
    )
    plan = base.record(origin.KIND, **body)
    approval = base.read(previous.RAW / "budget_approval.json")
    approval_body = {
        k: copy.deepcopy(v) for k, v in approval.items() if k not in {"id", "schema_version"}
    }
    approval_body.update(
        execution_protocol_id=plan["id"],
        approval_record="Separate third ten-POST prospective engineering allocation under user's "
        "continue-overall-experiment and API authorization. Earlier twenty calls are not refunded.",
    )
    approval = base.record("cross_market_source_review_budget_approval", **approval_body)
    core.validate_budget(
        origin.frozen_ref(references["material_protocol"]),
        origin.frozen_ref(references["material_manifest"]),
        approval,
    )
    save(RAW / "protocol.json", plan)
    save(RAW / "budget_approval.json", approval)
    base.emit(dict(event="span_locator_pilot_registered", id=plan["id"], attempts=10))
    return plan


def protocol(root):
    ns = origin.isolated.isolated_namespace(origin, RAW=RAW)
    plan = ns["protocol"](root)
    parent = origin.frozen_ref(plan["references"]["previous_pilot_protocol"])
    done = origin.frozen_ref(plan["references"]["previous_pilot_summary"])
    base.require(
        plan["execution_revision"] == 3
        and plan["previous_pilot_id"] == parent["id"] == done["execution_protocol_id"]
        and plan["selected_packets"] == parent["selected_packets"]
        and plan["original_failed_responses_unchanged"] is True,
        "span_pilot_unchanged_parent_and_separate_revision",
    )
    return plan


def run_job(plan, parent, manifest, approval, row, lane, key):
    packet = origin.frozen_ref(row["reference"])
    job = core.job_key(packet["id"], lane)
    existing = sorted((RAW / "scan_results").glob(job + ".*.json"))
    if existing:
        base.require(len(existing) == 1, "span_pilot_one_result_per_job")
        result = base.checked(base.read(existing[0]), "cross_market_source_scan_result")
        base.require(
            result["protocol_id"] == parent["id"]
            and result["packet_id"] == packet["id"]
            and result["lane"] == lane
            and result["attempt"] == 1,
            "span_pilot_cached_identity",
        )
        return result
    base.require(
        not list((RAW / "API_attempts").glob(job + ".*.json")),
        "span_pilot_unsettled_attempt_no_replay",
    )
    view, rendered, body = request_for(packet, row["reference"], lane)
    binding = next(
        r for r in plan["requests"] if r["packet_id"] == packet["id"] and r["lane"] == lane
    )
    base.require(
        binding["projection_id"] == view["id"]
        and binding["request_sha256"] == base.sha(rendered.body),
        "span_pilot_bound_request",
    )
    save(RAW / "projections" / (packet["id"].split(":")[-1] + ".json"), view)
    ns = origin.isolated.isolated_namespace(core, RAW=RAW)
    ns["request_payload"] = lambda packet_arg, lane_arg, model_arg: body
    ns["validate_scan"] = lambda packet_arg, payload: spans.validate_span_scan(
        packet_arg, view, payload
    )
    result = ns["run_scan_attempt"](
        parent, manifest, packet, lane, approval, transport.Provider(RAW, key)
    )
    base.emit(
        dict(
            event="span_locator_pilot_job_saved",
            packet_id=packet["id"],
            lane=lane,
            status=result["status"],
            attempt=result["attempt"],
        )
    )
    return result


def run(root):
    ns = origin.isolated.isolated_namespace(origin, RAW=RAW)
    ns["protocol"], ns["run_job"] = protocol, run_job
    return ns["run"](root)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("register", "run"))
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    {"register": register, "run": run}[args.action](args.root.resolve())


if __name__ == "__main__":
    main()
