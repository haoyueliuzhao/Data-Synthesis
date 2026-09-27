"""Two extra bounded, newly prompted reviews only after both original attempts fail.

No old response repair, validator relaxation, sample replacement or hidden retry.
Completed reviews remain in the original parent namespace; every recovery POST
has its own additional-budget reservation and revision-bound execution lineage.
"""

import argparse
import copy
import json
import subprocess
from pathlib import Path

import run_cross_market_text_capacity_revision_20260927 as capacity

original, base = capacity.original, capacity.base
SCRIPT = "trusted_data_synthesis/scripts/run_cross_market_text_schema_recovery_20260927.py"
RECORD = original.RAW / "schema_recovery_revision_01.json"
KIND = "cross_market_text_schema_recovery_revision"
EXTRA_ATTEMPTS_PER_PACKET = 2
MAX_EXTRA_POSTS = 128
EXPECTED_PACKET_UNIVERSE = 5663
EXPECTED_INITIAL_SAVED_REVIEWS = 442
EXHAUSTED_STATUSES = {"TECHNICAL_FAILURE_NOT_REFUNDED", "INTERRUPTED_UNSETTLED_NOT_REFUNDED"}
CLARIFICATION = (
    "Additional schema precision for this NEW complete-source review: every finding id must be "
    "unique within this response (for example f1, f2, f3); never reuse an id. Dates must be null "
    "when the actual source interval is unknown; when both dates are given, period_start MUST "
    "be strictly earlier than period_end. Do not reverse dates or invent an interval. Review "
    "only true multi-year total/cumulative/mean amounts for the four registered flow metrics "
    "or a specific source-grounded uncertainty affecting such a determination. An equity, "
    "retained-earnings, reserve, balance-sheet or dividend balance/rollforward is not a "
    "revenue, net-income, operating-income or operating-cash-flow aggregate. Ordinary annual "
    "amounts displayed in adjacent year columns are separate annual observations, not a "
    "single multi-year total or mean; do not list them as aggregate findings. Do not omit a "
    "genuine relevant ambiguity or aggregate merely to obtain an empty response. All original "
    "text remains supplied and the original exact schema and source-span rules still apply."
)


def require(condition, reason):
    base.require(condition, "text_schema_recovery." + reason)


def exhausted_original(plan, row):
    """Return exact old reservations/outcomes, or None; never write old attempts."""
    paths = []
    for attempt in (1, 2):
        directory = original.RAW / "attempts" / original.key_for(row["packet_id"]) / str(attempt)
        reserved, outcome = directory / "reservation.json", directory / "outcome.json"
        if not reserved.exists() or not outcome.exists():
            return None
        reservation, result = base.read(reserved), base.read(outcome)
        require(
            reservation["protocol_id"] == plan["id"]
            and reservation["packet_id"] == row["packet_id"]
            and reservation["attempt"] == attempt,
            "original_attempt_identity",
        )
        if result["status"] not in EXHAUSTED_STATUSES:
            return None
        paths.append(
            dict(attempt=attempt, reservation=original.ref(reserved), outcome=original.ref(outcome))
        )
    return paths


def register(root):
    root = Path(root)
    if RECORD.exists():
        return revision(root)
    parent = original.protocol(root)
    capacity_record = capacity.revision(root)
    require(
        len(parent["packet_universe"])
        == parent["maximum_unique_packets"]
        == EXPECTED_PACKET_UNIVERSE
        and parent["maximum_attempts_per_packet"] == 2,
        "fixed_parent_packet_and_attempt_scope",
    )
    require(
        not any((original.RAW / "recovery_attempts").glob("*/*/reservation.json")),
        "no_unregistered_recovery_POSTs",
    )
    stop = base.read(original.RAW / "status.json")
    saved = sorted((original.RAW / "packet_reviews").glob("*.json"))
    require(
        stop["state"] == "TEXT_REVIEW_TECHNICAL_PENDING"
        and stop["saved_packet_reviews"] == len(saved) == EXPECTED_INITIAL_SAVED_REVIEWS
        and len(stop["failed_packet_ids"]) == 1,
        "exact_preserved_schema_failure_stop",
    )
    rows = {row["packet_id"]: row for row in parent["packet_universe"]}
    initial_evidence = {}
    for packet_id in stop["failed_packet_ids"]:
        require(packet_id in rows, "failed_packet_is_registered")
        evidence = exhausted_original(parent, rows[packet_id])
        require(evidence is not None, "original_two_attempts_really_exhausted")
        require(
            not (
                original.RAW / "packet_reviews" / (original.key_for(packet_id) + ".json")
            ).exists(),
            "no_recovery_for_settled_packet",
        )
        initial_evidence[packet_id] = evidence
    stop_path = original.RAW / "schema_recovery_prior_stop_01.json"
    base.write(stop_path, stop)
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    content = (root / SCRIPT).read_bytes()
    require(
        content == subprocess.check_output(["git", "show", head + ":" + SCRIPT], cwd=root),
        "committed_recovery_before_registration",
    )
    value = base.record(
        KIND,
        at=base.now(),
        code_commit=head,
        sources={SCRIPT: base.sha(content)},
        parent_protocol=original.ref(original.RAW / "protocol.json"),
        parent_protocol_id=parent["id"],
        capacity_revision=original.ref(capacity.RECORD),
        capacity_revision_id=capacity_record["id"],
        prior_stop=original.ref(stop_path),
        initial_exhausted_packets=initial_evidence,
        preserved_packet_reviews=[original.ref(path) for path in saved],
        maximum_original_packets=EXPECTED_PACKET_UNIVERSE,
        maximum_extra_attempts_per_packet=EXTRA_ATTEMPTS_PER_PACKET,
        maximum_additional_POSTs=MAX_EXTRA_POSTS,
        parent_attempt_budget_unchanged=parent["maximum_API_attempts"],
        combined_maximum_POSTs=parent["maximum_API_attempts"] + MAX_EXTRA_POSTS,
        maximum_request_bytes=capacity.MAX_REQUEST_BYTES,
        model=original.MODEL,
        maximum_output_tokens_per_attempt=4096,
        clarification=CLARIFICATION,
        clarification_sha256=base.sha(CLARIFICATION),
        refunded_attempts=0,
        old_responses_modified=False,
        validator_relaxed=False,
        source_text_changed=False,
        selection_changed=False,
        automatic_budget_extension=False,
        technical_failure_excludes_candidate=False,
        original_protocol_for_review_identity=True,
        execution_adds_recovery_revision_reference=True,
        authority="User requested mainline completion; explicitly bounded schema-recovery "
        "allocation: at most128 additional POSTs, at most2 per originally exhausted packet. "
        "Future qualifying packets use this same fixed allocation, never a refreshed budget.",
    )
    base.write(RECORD, value)
    base.emit(
        dict(
            event="text_schema_recovery_registered",
            revision_id=value["id"],
            preserved_reviews=len(saved),
            extra_POST_cap=MAX_EXTRA_POSTS,
        )
    )
    return value


def revision(root):
    value = base.checked(base.read(RECORD), KIND)
    parent, capacity_record = original.protocol(root), capacity.revision(root)
    require(
        value["parent_protocol_id"] == parent["id"]
        and value["parent_protocol"] == original.ref(original.RAW / "protocol.json")
        and value["capacity_revision"] == original.ref(capacity.RECORD)
        and value["capacity_revision_id"] == capacity_record["id"]
        and value["maximum_request_bytes"] == capacity.MAX_REQUEST_BYTES == 262144
        and value["maximum_original_packets"]
        == len(parent["packet_universe"])
        == EXPECTED_PACKET_UNIVERSE
        and value["maximum_extra_attempts_per_packet"] == EXTRA_ATTEMPTS_PER_PACKET == 2
        and value["maximum_additional_POSTs"] == MAX_EXTRA_POSTS == 128
        and value["model"] == original.MODEL
        and value["maximum_output_tokens_per_attempt"] == 4096
        and value["clarification"] == CLARIFICATION
        and value["clarification_sha256"] == base.sha(CLARIFICATION),
        "frozen_parent_model_clarification_and_extra_budget",
    )
    for name, digest in value["sources"].items():
        require(base.sha(Path(root) / name) == digest, "frozen_recovery_code")
    require(
        original.ref(value["prior_stop"]["path"]) == value["prior_stop"], "preserved_stop_bytes"
    )
    return value


def clarified_request(namespace, packet, reference):
    projection, inherited = namespace["request_for"](packet, reference)
    request = copy.deepcopy(inherited)
    request["messages"][0]["content"] += "\n" + CLARIFICATION
    namespace["transport"].request_bytes(request)
    require(
        request["messages"][1] == inherited["messages"][1], "complete_original_payload_unchanged"
    )
    return projection, request


def recover_packet(namespace, value, revision_reference, plan, row, key):
    require(
        plan["id"] == value["parent_protocol_id"] and row in plan["packet_universe"],
        "registered_parent_packet_only",
    )
    packet_id, stem = row["packet_id"], original.key_for(row["packet_id"])
    result_path = original.RAW / "packet_reviews" / (stem + ".json")
    with base.locked(
        original.RAW / "schema_recovery_packet_locks" / (stem + ".lock"), blocking=True
    ):
        if result_path.exists():
            result = base.checked(base.read(result_path), original.semantic.PACKET_KIND)
            require(
                result["protocol_id"] == plan["id"]
                and result["packet_id"] == packet_id
                and result["packet_sha256"] == row["reference"]["sha256"],
                "settled_review_identity",
            )
            return result
        old_attempts = exhausted_original(plan, row)
        if old_attempts is None:
            return None
        packet = namespace["packet_at"](row["reference"]["path"], row["reference"]["sha256"])
        projection, request = clarified_request(namespace, packet, row["reference"])
        request_hash = base.sha(base.encode(request))
        for attempt in range(1, EXTRA_ATTEMPTS_PER_PACKET + 1):
            directory = original.RAW / "recovery_attempts" / stem / str(attempt)
            outcome, reserved = directory / "outcome.json", directory / "reservation.json"
            if outcome.exists():
                require(
                    base.read(outcome)["recovery_revision_id"] == value["id"],
                    "same_recovery_outcome",
                )
                continue
            if reserved.exists():
                previous = base.read(reserved)
                require(
                    previous["recovery_revision_id"] == value["id"]
                    and previous["protocol_id"] == plan["id"]
                    and previous["packet_id"] == packet_id
                    and previous["request_sha256"] == request_hash,
                    "same_unsettled_recovery",
                )
                base.write(
                    outcome,
                    dict(
                        status="INTERRUPTED_UNSETTLED_NOT_REFUNDED",
                        at=base.now(),
                        recovery_revision_id=value["id"],
                    ),
                )
                continue
            with base.locked(original.RAW / "schema_recovery_budget.lock", blocking=True):
                used = len(list((original.RAW / "recovery_attempts").glob("*/*/reservation.json")))
                if used >= MAX_EXTRA_POSTS:
                    return None
                base.write(
                    reserved,
                    dict(
                        protocol_id=plan["id"],
                        packet_id=packet_id,
                        extra_attempt=attempt,
                        recovery_revision_id=value["id"],
                        recovery_revision_reference=revision_reference,
                        original_exhausted_attempts=old_attempts,
                        request_sha256=request_hash,
                        at=base.now(),
                    ),
                )
            try:
                response = namespace["transport"].Provider(directory, key)(request)
                require(response["finish_reason"] == "stop", "complete_new_response_required")
                payload = json.loads(response["content"])
                physical = directory / "physical_requests" / request_hash
                execution = dict(
                    protocol_id=plan["id"],
                    packet_id=packet_id,
                    packet_sha256=row["reference"]["sha256"],
                    model=response["model"],
                    provider="DeepSeek",
                    request_reference=original.ref(physical / "request.json"),
                    raw_response_reference=original.ref(physical / "raw_response.json"),
                    payload_sha256=base.sha(base.encode(payload)),
                    finish_reason=response["finish_reason"],
                    independent_of_Student_and_Q=True,
                    schema_recovery_revision_id=value["id"],
                    schema_recovery_revision_reference=revision_reference,
                    schema_recovery_extra_attempt=attempt,
                    original_exhausted_attempts=old_attempts,
                )
                reviewed = original.semantic.build_packet_review(
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
                        recovery_revision_id=value["id"],
                        usage=response["usage"],
                        packet_review_id=reviewed["id"],
                    ),
                )
                return reviewed
            except Exception as error:
                reason = (
                    str(error)
                    if isinstance(error, ValueError)
                    and str(error).startswith(
                        ("cross_market.", "review_spans.", "text_table_review.")
                    )
                    else None
                )
                base.write(
                    outcome,
                    dict(
                        status="TECHNICAL_FAILURE_NOT_REFUNDED",
                        at=base.now(),
                        recovery_revision_id=value["id"],
                        error_type=type(error).__name__,
                        validation_reason=reason,
                    ),
                )
        return None


def execution_namespace(value, revision_reference):
    namespace = capacity.isolation.isolated_namespace(
        original,
        transport=capacity.transport_namespace(original.ref(capacity.RECORD)),
        SCRIPT=SCRIPT,
    )
    parent_review = namespace["review_packet"]

    def review_packet(plan, row, key):
        result = parent_review(plan, row, key)
        if result is not None:
            return result
        return recover_packet(namespace, value, revision_reference, plan, row, key)

    namespace["review_packet"] = review_packet
    return namespace


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("register", "run", "start", "status"))
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    root = args.root.resolve()
    if args.action == "register":
        register(root)
        return
    value = revision(root)
    namespace = execution_namespace(value, original.ref(RECORD))
    if args.action == "status":
        base.emit(
            dict(
                parent=base.read(original.RAW / "status.json"),
                recovery_reserved_POSTs=len(
                    list((original.RAW / "recovery_attempts").glob("*/*/reservation.json"))
                ),
                recovery_POST_cap=MAX_EXTRA_POSTS,
            )
        )
    else:
        namespace[args.action](root)


if __name__ == "__main__":
    main()
