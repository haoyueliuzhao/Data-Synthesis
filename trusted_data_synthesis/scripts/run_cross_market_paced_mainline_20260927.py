"""Respect provider 429 backoff while resuming the same text-only experiment.

No proxy, account, user_id, endpoint or model switch. A separate finite allocation
may revisit only exhausted packets whose latest real response was HTTP429.
"""

import argparse
import json
import subprocess
import types
from datetime import datetime, timedelta
from pathlib import Path

import cross_market_review_pacing_20260927 as pacing
import run_cross_market_text_task_resolution_20260927 as resolution

original, base, recovery = resolution.original, resolution.base, resolution.recovery
ROOT = original.RAW / "paced_recovery_01"
RECORD = ROOT / "protocol.json"
SCRIPT = "trusted_data_synthesis/scripts/run_cross_market_paced_mainline_20260927.py"
KIND = "cross_market_paced_mainline_protocol"
MAX_POSTS = 64
ATTEMPTS = 3


def rate_evidence(packet_id):
    rows = []
    for branch in ("attempts", "recovery_attempts"):
        folder = original.RAW / branch / original.key_for(packet_id)
        for path in folder.glob("*/physical_requests/*/receipt.json"):
            value = base.read(path)
            rows.append((value["at"], value, original.ref(path)))
    if not rows:
        return None
    _, latest, reference = max(rows, key=lambda row: row[0])
    return reference if latest.get("http_status") == 429 else None


def register(root):
    if RECORD.exists():
        return protocol(root)
    parent = original.protocol(root)
    resolution.protocol(root)
    stopped = base.read(original.RAW / "status.json")
    base.require(
        stopped["state"] == "TEXT_REVIEW_TECHNICAL_PENDING"
        and stopped["saved_packet_reviews"] == 2042
        and len(stopped["failed_packet_ids"]) == 3,
        "paced_mainline.exact_rate_stop",
    )
    evidence = {key: rate_evidence(key) for key in stopped["failed_packet_ids"]}
    base.require(all(evidence.values()), "paced_mainline.only_actual429_not_semantic_failure")
    latest = max(datetime.fromisoformat(base.read(r["path"])["at"]) for r in evidence.values())
    not_before = (latest + timedelta(seconds=300)).isoformat()
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    sources = {}
    for name in (SCRIPT, pacing.SCRIPT):
        payload = (root / name).read_bytes()
        base.require(
            payload == subprocess.check_output(["git", "show", head + ":" + name], cwd=root),
            "paced_mainline.committed_revision",
        )
        sources[name] = base.sha(payload)
    base.write(ROOT / "prior_stop.json", stopped)
    value = base.record(
        KIND,
        at=base.now(),
        code_commit=head,
        sources=sources,
        parent_protocol=original.ref(original.RAW / "protocol.json"),
        parent_protocol_id=parent["id"],
        task_adjudication=original.ref(resolution.RECORD),
        prior_stop=original.ref(ROOT / "prior_stop.json"),
        original429_evidence=evidence,
        pacing=pacing.expected_pacing(not_before),
        maximum_additional_POSTs=MAX_POSTS,
        maximum_extra_attempts_per_rate_packet=ATTEMPTS,
        maximum_original_packets=len(parent["packet_universe"]),
        model=original.MODEL,
        provider="DeepSeek",
        new_source_or_visual_calls=0,
        key_proxy_endpoint_user_id_or_model_changed=False,
        official_policy_sources=[
            "https://api-docs.deepseek.com/quick_start/error_codes/",
            "https://api-docs.deepseek.com/zh-cn/quick_start/rate_limit/",
        ],
        policy_checked_on="2026-09-27",
        official_recommendation="Pace requests; concurrency is "
        "account-wide, so this process alone does not establish total account concurrency.",
        preserved_packet_reviews=2042,
        old_attempts_refunded=0,
        old_budgets_unchanged=True,
        authority="User requested continued completion and authorized API resources. New finite "
        "rate-only retries; no response repair, semantic relaxation or sample replacement.",
        physical_attempt_authority="New pacing wire ledger counts actual network starts; local "
        "circuit rejections are not additional HTTP requests.",
    )
    base.write(RECORD, value)
    base.emit(
        dict(
            event="paced_mainline_registered",
            id=value["id"],
            not_before=not_before,
            preserved_reviews=2042,
            additional_POST_cap=MAX_POSTS,
        )
    )
    return value


def protocol(root):
    value = base.checked(base.read(RECORD), KIND)
    parent = original.protocol(root)
    resolution.protocol(root)
    base.require(
        value["parent_protocol_id"] == parent["id"]
        and value["task_adjudication"] == original.ref(resolution.RECORD),
        "paced_mainline.same_frozen_scientific_parent",
    )
    for name, digest in value["sources"].items():
        base.require(base.sha(root / name) == digest, "paced_mainline.frozen_code")
    return value


def rate_recover(namespace, plan, row, key, rate_plan):
    base.require(
        rate_plan["parent_protocol_id"] == plan["id"] and row in plan["packet_universe"],
        "paced_mainline.registered_parent_packet_only",
    )
    evidence = rate_evidence(row["packet_id"])
    if evidence is None:
        return None
    packet = namespace["packet_at"](row["reference"]["path"], row["reference"]["sha256"])
    projection, request = recovery.clarified_request(namespace, packet, row["reference"])
    request_hash = base.sha(base.encode(request))
    for attempt in range(1, ATTEMPTS + 1):
        folder = ROOT / "attempts" / original.key_for(row["packet_id"]) / str(attempt)
        reservation, outcome = folder / "reservation.json", folder / "outcome.json"
        if outcome.exists():
            continue
        if reservation.exists():
            base.write(outcome, dict(status="INTERRUPTED_UNSETTLED_NOT_REFUNDED", at=base.now()))
            continue
        with base.locked(ROOT / "budget.lock", blocking=True):
            if len(list((ROOT / "attempts").glob("*/*/reservation.json"))) >= MAX_POSTS:
                return None
            base.write(
                reservation,
                dict(
                    protocol_id=rate_plan["id"],
                    packet_id=row["packet_id"],
                    parent_protocol_id=plan["id"],
                    prior429=evidence,
                    attempt=attempt,
                    request_sha256=request_hash,
                    at=base.now(),
                ),
            )
        try:
            response = namespace["transport"].Provider(folder, key)(request)
            base.require(response["finish_reason"] == "stop", "paced_mainline.complete_reply")
            payload = json.loads(response["content"])
            physical = folder / "physical_requests" / request_hash
            execution = dict(
                protocol_id=plan["id"],
                packet_id=row["packet_id"],
                packet_sha256=row["reference"]["sha256"],
                model=response["model"],
                provider="DeepSeek",
                request_reference=original.ref(physical / "request.json"),
                raw_response_reference=original.ref(physical / "raw_response.json"),
                payload_sha256=base.sha(base.encode(payload)),
                finish_reason=response["finish_reason"],
                independent_of_Student_and_Q=True,
                pacing_protocol_id=rate_plan["id"],
                pacing_protocol_reference=original.ref(RECORD),
                rate_recovery_attempt=attempt,
                exhausted429_reference=evidence,
            )
            result = original.semantic.build_packet_review(
                review_protocol_id=plan["id"],
                packet=packet,
                projection=projection,
                payload=payload,
                execution=execution,
            )
            base.write(folder / "payload.json", payload)
            base.write(
                original.RAW / "packet_reviews" / (original.key_for(row["packet_id"]) + ".json"),
                result,
            )
            base.write(
                outcome,
                dict(
                    status="RATE_RECOVERY_RESPONSE_SAVED",
                    at=base.now(),
                    usage=response["usage"],
                    review_id=result["id"],
                ),
            )
            return result
        except Exception as error:
            base.write(
                outcome,
                dict(status="FAILED_NOT_REFUNDED", at=base.now(), error_type=type(error).__name__),
            )
    return None


def execution_namespace(root, rate_plan):
    sender = pacing.make_sender(ROOT / "pacing", original.ref(RECORD))
    isolated = recovery.capacity.isolation.isolated_namespace(resolution, SCRIPT=SCRIPT)
    isolated["provider_class"] = lambda: pacing.paced_provider_class(
        resolution.provider_class(), sender
    )
    namespace, pool = isolated["execution_namespace"](resolution.protocol(root))
    namespace["SCRIPT"], namespace["CONCURRENCY"] = SCRIPT, 4
    transport = namespace["transport"]
    namespace["transport"] = types.SimpleNamespace(
        **{**vars(transport), "Provider": pacing.paced_provider_class(transport.Provider, sender)}
    )
    parent_review = namespace["review_packet"]

    def review_packet(plan, row, key):
        result = parent_review(plan, row, key)
        return result if result is not None else rate_recover(namespace, plan, row, key, rate_plan)

    namespace["review_packet"] = review_packet
    return namespace, pool


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("register", "start", "run", "status"))
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    root = args.root.resolve()
    if args.action == "register":
        register(root)
        return
    value = protocol(root)
    if args.action == "status":
        base.emit(base.read(original.RAW / "status.json"))
        return
    namespace, pool = execution_namespace(root, value)
    try:
        namespace[args.action](root)
    except Exception as error:
        original.status(state="PACED_MAINLINE_TECHNICAL_PENDING", error_type=type(error).__name__)
        raise
    finally:
        pool.shutdown(wait=True)


if __name__ == "__main__":
    main()
