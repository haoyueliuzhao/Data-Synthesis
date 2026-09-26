"""Second finite real pilot: prospective line-ID output, not edited old responses."""

import argparse
import copy
import subprocess
from pathlib import Path

import cross_market_review_line_locator_20260927 as lines
import run_cross_market_review_pilot_20260927 as prior

base, core, transport = prior.base, prior.core, prior.transport
RAW = prior.RAW.parent / "source_review_line_locator_pilot_02"
SCRIPT = "trusted_data_synthesis/scripts/run_cross_market_line_locator_pilot_20260927.py"


def save(path, value):
    base.require(Path(path).resolve().is_relative_to(RAW.resolve()), "line_pilot_output_root")
    base.write(path, value)


def request_for(packet, reference, lane):
    ns = prior.isolated.isolated_namespace(prior, projection=lines)
    return ns["request_for"](packet, reference, lane)


def register(root):
    if (RAW / "protocol.json").exists():
        return protocol(root)
    base.require(
        not any((RAW / "API_attempts").glob("*.json"))
        and not any((RAW / "physical_requests").glob("*/*.json"))
        and not any((RAW / "scan_results").glob("*.json")),
        "line_pilot_no_unregistered_attempts",
    )
    previous = prior.protocol(root)
    previous_summary_ref = prior.materials.ref(prior.RAW / "summary.json")
    done = base.checked(
        prior.frozen_ref(previous_summary_ref),
        "cross_market_source_review_assistance_pilot_completed",
    )
    base.require(
        done["execution_protocol_id"] == previous["id"]
        and done["physical_attempts"] == 10
        and done["status_counts"]
        == {
            "ASSISTANCE_RESPONSE_SAVED_NOT_ADMITTED": 2,
            "SCAN_ATTEMPT_FAILED_NOT_REFUNDED": 8,
        },
        "line_pilot_preserved_previous_results",
    )
    references = dict(
        previous["references"],
        previous_pilot_protocol=prior.materials.ref(prior.RAW / "protocol.json"),
        previous_pilot_summary=previous_summary_ref,
    )
    sources = dict(previous["sources"])
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    for name in (SCRIPT, lines.SCRIPT):
        payload = (root / name).read_bytes()
        base.require(
            payload == subprocess.check_output(["git", "show", head + ":" + name], cwd=root),
            "line_pilot_committed_code",
        )
        sources[name] = base.sha(payload)
    requests = []
    for row in previous["selected_packets"]:
        packet = prior.frozen_ref(row["reference"])
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
    body = {k: copy.deepcopy(v) for k, v in previous.items() if k not in {"id", "schema_version"}}
    body.update(
        at=base.now(),
        code_commit=head,
        sources=sources,
        references=references,
        requests=requests,
        execution_revision=2,
        previous_pilot_id=previous["id"],
        locator_contract="Provider chooses exact original line-ID ranges. Deterministic original "
        "line ledger supplies Unicode offsets/quotes; no provider quote correction, fuzzy matching "
        "or semantic approval. Raw response and derived canonical locator remain distinct.",
        original_failed_responses_unchanged=True,
        inspected_before_registration="Pilot01 10 actual responses: 2 validator successes, "
        "3 truncated JSONs, 39 parsed findings with zero correct reported offsets; "
        "36 unique exact quotes and 3 absent quotes. Revision is not outcome-blind.",
    )
    plan = base.record(prior.KIND, **body)
    save(RAW / "protocol.json", plan)
    approval = base.read(prior.RAW / "budget_approval.json")
    approval_body = {
        k: copy.deepcopy(v) for k, v in approval.items() if k not in {"id", "schema_version"}
    }
    approval_body.update(
        execution_protocol_id=plan["id"],
        approval_record="Separately frozen second ten-POST engineering pilot under "
        "the user's continue-experiment and API authorization; previous ten attempts "
        "and every failure are preserved, not refunded or reused.",
    )
    approval = base.record("cross_market_source_review_budget_approval", **approval_body)
    core.validate_budget(
        prior.frozen_ref(references["material_protocol"]),
        prior.frozen_ref(references["material_manifest"]),
        approval,
    )
    save(RAW / "budget_approval.json", approval)
    base.emit(dict(event="line_locator_pilot_registered", id=plan["id"], attempts=10))
    return plan


def protocol(root):
    ns = prior.isolated.isolated_namespace(prior, RAW=RAW)
    plan = ns["protocol"](root)
    base.require(
        plan["execution_revision"] == 2 and plan["original_failed_responses_unchanged"] is True,
        "line_pilot_separate_prospective_revision",
    )
    previous = prior.frozen_ref(plan["references"]["previous_pilot_protocol"])
    done = prior.frozen_ref(plan["references"]["previous_pilot_summary"])
    base.require(
        plan["previous_pilot_id"] == previous["id"] == done["execution_protocol_id"]
        and plan["selected_packets"] == previous["selected_packets"],
        "line_pilot_preserved_parent_identity",
    )
    return plan


def run_job(plan, parent, manifest, approval, row, lane, key):
    packet = prior.frozen_ref(row["reference"])
    job = core.job_key(packet["id"], lane)
    existing = sorted((RAW / "scan_results").glob(job + ".*.json"))
    if existing:
        base.require(len(existing) == 1, "line_pilot_one_result_per_job")
        result = base.checked(base.read(existing[0]), "cross_market_source_scan_result")
        base.require(
            result["protocol_id"] == parent["id"]
            and result["packet_id"] == packet["id"]
            and result["lane"] == lane
            and result["attempt"] == 1,
            "line_pilot_cached_job_identity",
        )
        return result
    base.require(
        not list((RAW / "API_attempts").glob(job + ".*.json")),
        "line_pilot_unsettled_attempt_no_replay",
    )
    view, rendered, body = request_for(packet, row["reference"], lane)
    binding = next(
        r for r in plan["requests"] if r["packet_id"] == packet["id"] and r["lane"] == lane
    )
    base.require(
        binding["projection_id"] == view["id"]
        and binding["request_sha256"] == base.sha(rendered.body),
        "line_pilot_registered_request",
    )
    save(RAW / "projections" / (packet["id"].split(":")[-1] + ".json"), view)
    ns = prior.isolated.isolated_namespace(core, RAW=RAW)
    ns["request_payload"] = lambda packet_arg, lane_arg, model_arg: body
    ns["validate_scan"] = lambda packet_arg, payload: lines.validate_line_scan(
        packet_arg, view, payload
    )
    result = ns["run_scan_attempt"](
        parent, manifest, packet, lane, approval, transport.Provider(RAW, key)
    )
    base.emit(
        dict(
            event="line_locator_pilot_job_saved",
            packet_id=packet["id"],
            lane=lane,
            status=result["status"],
            attempt=result["attempt"],
        )
    )
    return result


def run(root):
    ns = prior.isolated.isolated_namespace(prior, RAW=RAW)
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
