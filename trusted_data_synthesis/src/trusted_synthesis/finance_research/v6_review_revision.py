"""Explicit capacity amendment: retain all 8000 originals and one 800-CNY ledger.

Twelve registered reviews first establish format/capacity (not answer quality).
No old failed review is erased, no generation slot is topped up, no automatic retry.
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
from pathlib import Path

from .calibration import ROOT, identity, now, publish, status
from .cli import _key
from .contracts import digest, invocation_identity
from .probe_budget import V6_PURPOSE, ProbeBudget, ProbePriceSheet, apply_v6_review_amendment
from .semantic_review import audit_packet, resolve_pair
from .storage import read_json, runtime_binding
from .v6_collection import (
    ENV_FILE,
    STUDY,
    bound,
    checked_prepared,
    persist,
    require,
    sha,
    unknown_resolution,
)
from .v6_collection import (
    OUTPUT as ORIGINAL,
)
from .v6_collection import (
    review_directory as old_review_directory,
)
from .v6_collection import (
    review_id as old_review_id,
)
from .v6_review_provider import request_review

OUTPUT = STUDY / "review_revision_01"
ALLOWED_OUTPUTS = [2048, 16384, 32768, 65536, 131072]
CAPACITY_POLICY = bound(
    dict(
        version="v6_observed_input_capacity.v1",
        formula=(
            "ceil(1.5 * (4096 + 3*actual_generation_output_tokens "
            "+ 64*target_span_count + 128*action_count))"
        ),
        allocation="smallest registered review cap >= estimate; never clip a larger requirement",
        review_caps=ALLOWED_OUTPUTS[1:],
        actual_DeepSeek_review_token_prediction=False,
        meaning="conservative engineering estimate; registered cohort validates capacity",
    )
)


def capacity_for(*, generation_output_tokens, target_span_count, action_count):
    for value in (generation_output_tokens, target_span_count, action_count):
        require(type(value) is int and value >= 0, "capacity features must be actual counts")
    estimate = math.ceil(
        1.5 * (4096 + 3 * generation_output_tokens + 64 * target_span_count + 128 * action_count)
    )
    cap = next((cap for cap in ALLOWED_OUTPUTS[1:] if cap >= estimate), None)
    require(
        cap is not None, "actual task needs a separately registered larger capacity; no truncation"
    )
    return dict(
        generation_output_tokens=generation_output_tokens,
        target_span_count=target_span_count,
        action_count=action_count,
        estimated_requirement=estimate,
        max_output_tokens=cap,
        capacity_policy_id=CAPACITY_POLICY["id"],
    )


def database():
    return ORIGINAL / "budget.sqlite3"


def connect():
    require(database().is_file(), "original paid ledger missing; cannot reset spending")
    connection = sqlite3.connect(database().as_uri() + "?mode=ro", uri=True, timeout=30)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA query_only=ON")
    return connection


def original_protocol():
    plan = read_json(ORIGINAL / "protocol.json")
    require(
        plan["id"] == digest({k: v for k, v in plan.items() if k != "id"}),
        "original protocol changed",
    )
    return plan


def paid_row(row, price):
    require(
        row["state"] == "SETTLED" and row["dispatched_at"] is not None,
        "inflight/unknown call blocks amendment or recovery",
    )
    require(
        hashlib.sha256(row["request_body"]).hexdigest() == row["request_sha256"]
        and hashlib.sha256(row["response_body"]).hexdigest() == row["response_sha256"],
        "paid original request/response bytes changed",
    )
    request = json.loads(row["request_body"])
    response = json.loads(row["response_body"])
    require(
        request["model"] == response.get("model") == "deepseek-flash"
        and request["thinking"] == {"type": "disabled"},
        "frozen model/thinking changed",
    )
    usage = json.loads(row["usage_json"])
    require(response["usage"] == usage, "usage differs from raw paid response")
    checked = price.usage(usage, output_limit=request["max_tokens"])
    amount = price.cost_microcny(
        hit=checked["prompt_cache_hit_tokens"],
        miss=checked["prompt_cache_miss_tokens"],
        output=checked["completion_tokens"],
    )
    require(amount == row["settled_microcny"], "paid cost does not conserve original usage")
    coordinates = json.loads(row["coordinates_json"])
    require(
        coordinates["invocation_id"] == row["invocation_id"]
        and invocation_identity(coordinates, turn_index=coordinates["turn_index"]) == coordinates,
        "paid coordinate mismatch",
    )
    return (
        dict(
            invocation_id=row["invocation_id"],
            episode_id=coordinates["episode_id"],
            request_sha256=row["request_sha256"],
            response_sha256=row["response_sha256"],
            settled_microcny=amount,
        ),
        request,
        response,
        checked,
    )


def historical_audit(parent_revision=None):
    """One byte-level, quiescent audit; permits only the recorded intentional pause."""
    if parent_revision is not None:
        parent_revision = Path(parent_revision)
        parent = read_json(protocol_path(parent_revision))
        require(
            parent["id"] == digest({k: v for k, v in parent.items() if k != "id"}),
            "parent revision registration changed",
        )
        completed = recover(parent_revision, parent)
        gate = read_json(parent_revision / "capacity_gate/record.json")
        fixed_ids = {
            review_id(parent, t, i) for t in parent["calibration"]["task_ids"] for i in (0, 1)
        }
        require(
            gate["id"] == digest({k: v for k, v in gate.items() if k != "id"})
            and gate["protocol_id"] == parent["id"]
            and gate["admitted"] is False
            and len(set(parent["calibration"]["task_ids"])) == 6
            and len(completed) == 12
            and set(completed) == fixed_ids,
            "only the settled failed fixed cohort may seed this revision",
        )
        old_history = read_json(parent_revision / "historical_audit/record.json")
        price = ProbePriceSheet(**parent["budget"]["price_sheet"])
        with connect() as con:
            require(
                con.execute("SELECT value FROM metadata WHERE key='halt'").fetchone() is None,
                "other budget halt cannot be bypassed by a format revision",
            )
            cfg = json.loads(
                con.execute("SELECT value FROM metadata WHERE key='config'").fetchone()[0]
            )
            entries = [
                paid_row(row, price)[0]
                for row in con.execute("SELECT * FROM requests ORDER BY invocation_id")
            ]
            counters = dict(con.execute("SELECT * FROM counters WHERE singleton=1").fetchone())
        require(
            cfg["amendment_id"] == parent["budget"].get("amendment_id", parent["id"]),
            "shared budget amendment changed",
        )
        return bound(
            dict(
                at=now(),
                original_protocol_id=parent["original_protocol_id"],
                original_protocol_sha256=old_history["original_protocol_sha256"],
                generation_seal_sha256=old_history["generation_seal_sha256"],
                parent_revision=str(parent_revision),
                parent_revision_id=parent["id"],
                parent_gate_sha256=sha(parent_revision / "capacity_gate/record.json"),
                parent_calibration_task_ids=parent["calibration"]["task_ids"],
                budget_config=cfg,
                budget_config_sha256=digest(cfg),
                budget_counters=counters,
                paid_entries=entries,
                generation_output_tokens_by_task=old_history["generation_output_tokens_by_task"],
                old_review_finish_reasons=old_history["old_review_finish_reasons"],
                previous_capacity_reviews_retained=12,
                no_old_artifacts_replaced=True,
                original_generation_reused=8000,
                new_generation_calls=0,
            )
        )
    plan = original_protocol()
    seal = read_json(ORIGINAL / "generation_seal/record.json")
    require(
        seal["id"] == digest({k: v for k, v in seal.items() if k != "id"})
        and seal["denominator"] == len(seal["slots"]) == 8000
        and seal["protocol_id"] == plan["id"],
        "full original generation seal required",
    )
    slots = {s["slot_id"]: s for s in plan["inventory"]["slots"]}
    require(
        {r["slot"]["slot_id"] for r in seal["slots"]} == set(slots),
        "registered slot population changed",
    )
    original_reviews = {old_review_id(plan, t, i): (t, i) for t in plan["task_ids"] for i in (0, 1)}
    expected_ids = set()
    for outcome in seal["slots"]:
        path = Path(outcome["episode_path"])
        require(sha(path) == outcome["episode_file_sha256"], "sealed original trajectory changed")
        episode = read_json(path)
        for turn in episode["turns"]:
            expected_ids.add(turn["provider_metadata"]["budget_invocation_id"])
    price = ProbePriceSheet(**plan["price_sheet"])
    entries, output_tokens, finishes = [], Counter(), Counter()
    totals = Counter()
    with connect() as con:
        cfg = json.loads(con.execute("SELECT value FROM metadata WHERE key='config'").fetchone()[0])
        halt = json.loads(con.execute("SELECT value FROM metadata WHERE key='halt'").fetchone()[0])
        require(
            cfg["run_id"] == plan["id"]
            and cfg["purpose"] == V6_PURPOSE
            and halt["reason"] == "user_authorized_review_capacity_audit",
            "wrong historical budget/pause",
        )
        for row in con.execute("SELECT * FROM requests ORDER BY invocation_id"):
            evidence, request, response, usage = paid_row(row, price)
            require(
                json.loads(row["coordinates_json"])["run_id"] == plan["id"],
                "historical run mismatch",
            )
            epi = evidence["episode_id"]
            if epi in slots:
                output_tokens[slots[epi]["task_id"]] += usage["completion_tokens"]
                require(
                    evidence["invocation_id"] in expected_ids, "orphan historical generation call"
                )
            else:
                require(epi in original_reviews, "unknown historical paid purpose")
                artifact = read_json(old_review_directory(ORIGINAL, epi) / "response/record.json")
                require(
                    artifact["api_response_raw"].encode() == row["response_body"]
                    and artifact["public_request"] == request,
                    "old review and paid evidence differ",
                )
                expected_ids.add(evidence["invocation_id"])
                finishes[response["choices"][0]["finish_reason"]] += 1
            entries.append(evidence)
            totals.update(usage)
        require(
            {r["invocation_id"] for r in entries} == expected_ids,
            "historical calls are not conserved",
        )
        counter = dict(con.execute("SELECT * FROM counters WHERE singleton=1").fetchone())
        require(
            counter["pending"] == counter["held"] == counter["unknown"] == 0
            and counter["requests"] == counter["dispatched"] == len(entries)
            and counter["spent"] == sum(r["settled_microcny"] for r in entries),
            "historical budget not settled",
        )
    return bound(
        dict(
            at=now(),
            original_protocol_id=plan["id"],
            original_protocol_sha256=sha(ORIGINAL / "protocol.json"),
            generation_seal_sha256=sha(ORIGINAL / "generation_seal/record.json"),
            budget_config=cfg,
            budget_config_sha256=digest(cfg),
            budget_counters=counter,
            paid_entries=entries,
            generation_output_tokens_by_task=dict(output_tokens),
            old_review_finish_reasons=dict(finishes),
            no_old_artifacts_replaced=True,
            original_generation_reused=8000,
            new_generation_calls=0,
        )
    )


def input_directory(output, task_id):
    return Path(output) / "inputs" / digest(task_id)


def build_inputs(output, historical, *, strict=False):
    from .v6_compact_review import capacity_features, compact_review_request

    if strict:
        from .v6_strict_review import capacity_features, strict_review_request

        compact_review_request = strict_review_request

    old = original_protocol()
    rows = []
    for task_id in old["task_ids"]:
        original = checked_prepared(ORIGINAL, task_id)
        reference = json.loads(original["requests"][0]["messages"][1]["content"])[
            "review_only_private_reference"
        ]
        requests = [compact_review_request(original["bundle"], reference, i) for i in (0, 1)]
        features = capacity_features(requests[0])
        capacity = capacity_for(
            generation_output_tokens=historical["generation_output_tokens_by_task"][task_id],
            target_span_count=features["target_fragment_count"],
            action_count=features["action_count"],
        )
        for request in requests:
            request.update(
                max_output_tokens=capacity["max_output_tokens"],
                capacity_policy_id=CAPACITY_POLICY["id"],
            )
            wire_bytes = sum(len(m["content"].encode()) for m in request["messages"])
            if strict:
                wire_bytes += len(json.dumps(request["strict_tool"], ensure_ascii=False).encode())
            require(
                wire_bytes + capacity["max_output_tokens"] < 1048576,
                "conservative request-byte/context capacity check failed; no silent truncation",
            )
        payload = bound(
            dict(
                task_id=task_id,
                original_prepared_id=original["id"],
                original_bundle_sha256=digest(original["bundle"]),
                requests=requests,
                capacity=capacity,
                features=features,
            )
        )
        persist(input_directory(output, task_id), payload)
        rows.append(
            dict(
                task_id=task_id,
                input_id=payload["id"],
                capacity=capacity,
                input_sha256=sha(input_directory(output, task_id) / "record.json"),
            )
        )
    return rows


def register(output, *, parent_revision=None):
    output = Path(output)
    if protocol_path(output).exists():
        return checked_plan(output)
    require(
        not output.exists(), "partial registration must be explicitly inspected; never overwrite"
    )
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    for path in Path(__file__).parent.rglob("*.py"):
        require(
            path.read_bytes()
            == subprocess.check_output(
                ["git", "show", head + ":" + str(path.relative_to(ROOT))], cwd=ROOT
            ),
            "commit capacity revision before registration",
        )
    strict = parent_revision is not None
    historical = historical_audit(parent_revision) if strict else historical_audit()
    publish(output / "historical_audit", historical)
    rows = (
        build_inputs(output, historical, strict=True)
        if strict
        else build_inputs(output, historical)
    )
    old = original_protocol()
    order = {task: i for i, task in enumerate(old["task_ids"])}
    by_load = sorted(
        rows, key=lambda r: (r["capacity"]["estimated_requirement"], order[r["task_id"]])
    )
    positions = [0, 250, 500, 900, 990, 999]
    selected = [by_load[i]["task_id"] for i in positions]
    if strict:
        require(
            selected == historical["parent_calibration_task_ids"],
            "technical revision must keep the same six preselected capacity tasks",
        )
    body = dict(
        schema="v6_review_capacity_revision.v1",
        wire_protocol="v6_strict_review.v2" if strict else "v6_compact_review.v1",
        at=now(),
        source_commit=head,
        runtime_binding=runtime_binding(),
        original_directory=str(ORIGINAL),
        original_protocol_id=old["id"],
        historical_audit_id=historical["id"],
        original_budget_config_sha256=historical["budget_config_sha256"],
        parent_revision=historical.get("parent_revision"),
        authorization="上限应该根据实际问题调整，审计问题，做调整，可以重新采集轨迹",
        original_generation_retained=8000,
        original_task_denominator=1000,
        original_slots_per_task=8,
        all_eight_common_candidates=True,
        generation_recollection=False,
        old_reviews_retained_but_not_mixed_into_revised_pair=True,
        task_ids=old["task_ids"],
        inputs=rows,
        review_denominator=2000,
        model="deepseek-flash",
        thinking="disabled",
        temperature=0,
        max_concurrent_reviews=8,
        request_timeout_policy="max(180, ceil(90 + per_task_output_cap / 128)) seconds",
        allowed_output_limits=ALLOWED_OUTPUTS,
        capacity_policy=CAPACITY_POLICY,
        budget=dict(
            path=str(database()),
            run_id=old["id"],
            purpose=V6_PURPOSE,
            hard_cap_microcny=800_000_000,
            warning_microcny=700_000_000,
            request_cap=258000,
            historical_spent_microcny=historical["budget_counters"]["spent"],
            price_sheet=old["price_sheet"],
        ),
        calibration=dict(
            task_ids=selected,
            sorted_load_positions=positions,
            requests=12,
            selection="pre-review load quantiles, never native score or semantic verdict",
            part_of_fixed_2000=True,
            extra_pilot_requests=0,
            criterion=(
                "12 complete named strict tool submissions and validate; no positivity requirement"
                if strict
                else "all 12 finish stop and validate binding; no positivity requirement"
            ),
            automatic_expansion_on_failure=False,
        ),
        stop_new_dispatch_on_format_capacity_failure=True,
        silent_retry_repair_third_review=False,
        automatic_training=False,
        GPU_reservation=False,
    )
    if strict:
        body["budget"]["amendment_id"] = historical["budget_config"]["amendment_id"]
        body["budget"]["reuse_existing_amendment"] = True
    plan = bound(body)
    persist(output / "registration", plan, "protocol.json")
    # Input preparation already occupies the root; use its own immutable registration directory.
    return plan


def protocol_path(output):
    direct = Path(output) / "protocol.json"
    return direct if direct.exists() else Path(output) / "registration/protocol.json"


def checked_plan(output):
    plan = read_json(protocol_path(output))
    require(
        plan["id"] == digest({k: v for k, v in plan.items() if k != "id"}),
        "revision protocol changed",
    )
    require(plan["runtime_binding"] == runtime_binding(), "frozen capacity revision source changed")
    return plan


def ledger_for(plan):
    args = plan["budget"]
    return ProbeBudget(
        args["path"],
        run_id=args["run_id"],
        purpose=V6_PURPOSE,
        price_sheet=args["price_sheet"],
        hard_cap_microcny=args["hard_cap_microcny"],
        warning_microcny=args["warning_microcny"],
        request_cap=args["request_cap"],
        max_output_tokens=max(plan["allowed_output_limits"]),
        allowed_output_limits=plan["allowed_output_limits"],
        amendment_id=args.get("amendment_id", plan["id"]),
    )


def activate(output, plan):
    path = Path(output) / "budget_amendment/record.json"
    if not path.exists():
        if plan["budget"].get("reuse_existing_amendment"):
            ledger = ledger_for(plan)
            require(
                digest(ledger.config) == plan["original_budget_config_sha256"],
                "existing shared capacity amendment changed",
            )
            publish(
                path.parent,
                dict(
                    amendment_id=plan["budget"]["amendment_id"],
                    reused=True,
                    new_monetary_authorization=False,
                    counters_at_reuse=ledger.snapshot(),
                    all_old_spending_preserved=True,
                ),
            )
            return ledger
        result = apply_v6_review_amendment(
            database(),
            expected_run_id=plan["budget"]["run_id"],
            expected_config_sha256=plan["original_budget_config_sha256"],
            amendment_id=plan["id"],
            allowed_review_output_limits=plan["allowed_output_limits"],
            evidence=dict(
                protocol_path=str(protocol_path(output)),
                protocol_sha256=sha(protocol_path(output)),
                authorization=plan["authorization"],
                historical_spend_counted=True,
            ),
        )
        publish(path.parent, result)
    return ledger_for(plan)


def review_id(plan, task_id, reviewer):
    return "v6r1-review:" + digest(dict(revision_id=plan["id"], task_id=task_id, reviewer=reviewer))


def review_directory(output, rid):
    return Path(output) / "reviews" / rid.split(":", 1)[1]


def checked_input(output, plan, task_id):
    row = next(row for row in plan["inputs"] if row["task_id"] == task_id)
    path = input_directory(output, task_id) / "record.json"
    require(sha(path) == row["input_sha256"], "registered compact request changed")
    payload = read_json(path)
    require(
        payload["id"] == row["input_id"] == digest({k: v for k, v in payload.items() if k != "id"}),
        "request identity changed",
    )
    return payload


def response_binding(artifact, request, row):
    expected_body = dict(
        model="deepseek-flash",
        messages=request["messages"],
        temperature=0,
        top_p=1,
        max_tokens=request["max_output_tokens"],
        stream=False,
        thinking={"type": "disabled"},
        response_format={"type": "json_object"},
    )
    strict = request.get("wire_protocol") == "v6_strict_review.v2"
    if strict:
        expected_body.pop("response_format")
        expected_body.update(
            tools=[request["strict_tool"]],
            tool_choice={"type": "function", "function": {"name": "submit_review"}},
        )
    require(
        artifact["public_request"] == json.loads(row["request_body"]) == expected_body
        and artifact["api_response_raw"].encode() == row["response_body"]
        and artifact["semantic_review_request_sha256"] == digest(request),
        "revised response/request mismatch",
    )
    response = json.loads(row["response_body"])
    choice = response["choices"][0]
    require(
        len(response["choices"]) == 1
        and artifact["content"] == choice["message"].get("content")
        and artifact["finish_reason"] == choice["finish_reason"],
        "derived review differs from raw paid response",
    )
    if strict:
        from .v6_review_provider import STRICT_ENDPOINT, _strict_review_payload

        actual = _strict_review_payload(choice["message"], choice["finish_reason"])
        require(
            all(artifact.get(k) == v for k, v in actual.items())
            and artifact.get("endpoint") == STRICT_ENDPOINT
            and artifact.get("strict_tool_sha256") == digest(request["strict_tool"]),
            "review arguments differ from actual strict tool response",
        )
    require(
        artifact["public_request"]["max_tokens"] == request["max_output_tokens"],
        "actual per-task output capacity changed",
    )


def recover(output, plan):
    """Old paid prefix cannot disappear; every new settled request has its raw artifact."""
    historical = read_json(Path(output) / "historical_audit/record.json")
    require(
        historical["id"]
        == plan["historical_audit_id"]
        == digest({k: v for k, v in historical.items() if k != "id"}),
        "historical audit changed",
    )
    old = {row["invocation_id"]: row for row in historical["paid_entries"]}
    expected = {review_id(plan, t, i): (t, i) for t in plan["task_ids"] for i in (0, 1)}
    completed, seen_old = {}, set()
    amounts, tokens = [], Counter()
    price = ProbePriceSheet(**plan["budget"]["price_sheet"])
    with connect() as con:
        for row in con.execute("SELECT * FROM requests"):
            evidence, _, _, usage = paid_row(row, price)
            amounts.append(evidence["settled_microcny"])
            tokens.update(usage)
            iid = evidence["invocation_id"]
            if iid in old:
                require(evidence == old[iid], "historical paid evidence changed or spending lost")
                seen_old.add(iid)
                continue
            rid = evidence["episode_id"]
            require(rid in expected, "unregistered revised review cannot consume joint budget")
            task_id, reviewer = expected[rid]
            coordinates = invocation_identity(
                dict(run_id=plan["budget"]["run_id"], episode_id=rid, attempt_index=1), turn_index=0
            )
            require(
                json.loads(row["coordinates_json"]) == coordinates,
                "revised review invocation changed",
            )
            directory = review_directory(output, rid)
            require(
                (directory / "response/record.json").exists(),
                "interrupted revised review cannot be resent",
            )
            artifact = read_json(directory / "response/record.json")
            request = checked_input(output, plan, task_id)["requests"][reviewer]
            response_binding(artifact, request, row)
            validation_path = directory / "validation/record.json"
            require(validation_path.exists(), "paid review needs durable validation; no resend")
            require(
                read_json(validation_path) == assess(artifact, request),
                "derived validation differs from its paid original content",
            )
            completed[rid] = artifact
        require(seen_old == set(old), "old spending/calls cannot be dropped")
        counter = dict(con.execute("SELECT * FROM counters WHERE singleton=1").fetchone())
        require(
            counter["spent"] == sum(amounts)
            and counter["requests"] == counter["dispatched"] == len(amounts)
            and counter["pending"] == counter["unknown"] == counter["held"] == 0
            and counter["prompt_tokens"] == tokens["prompt_tokens"]
            and counter["hit_tokens"] == tokens["prompt_cache_hit_tokens"]
            and counter["miss_tokens"] == tokens["prompt_cache_miss_tokens"]
            and counter["completion_tokens"] == tokens["completion_tokens"],
            "joint counters not conserved",
        )
    for rid in expected:
        require(
            not review_directory(output, rid).exists() or rid in completed,
            "uncompleted revised request is not automatically retried",
        )
    return completed


def assess(artifact, request):
    from .v6_compact_review import validate_compact_review

    try:
        if request.get("wire_protocol") == "v6_strict_review.v2":
            from .v6_strict_review import validate_strict_review

            require(
                artifact["finish_reason"] == "tool_calls"
                and not artifact.get("review_format_error"),
                "strict review stopped at capacity or lacks a valid tool submission",
            )
            validated = validate_strict_review(artifact["review_text"], request)
        else:
            require(
                artifact["finish_reason"] == "stop",
                "review stopped at capacity or non-normal finish",
            )
            validated = validate_compact_review(artifact["content"], request)
        return dict(format_capacity_admitted=True, validated=validated, error=None)
    except (ValueError, TypeError, KeyError, IndexError) as error:
        return dict(
            format_capacity_admitted=False,
            validated=None,
            error=dict(type=type(error).__name__, reason=str(error)[:1500]),
        )


async def run_batch(output, plan, ledger, key, completed, jobs, phase):
    import httpx

    halted, done = asyncio.Event(), asyncio.Event()
    blocked = []
    queue = asyncio.Queue()
    for task_id, reviewer in jobs:
        if review_id(plan, task_id, reviewer) not in completed:
            queue.put_nowait((task_id, reviewer))

    def progress():
        status(
            output,
            dict(
                at=now(),
                phase=phase if not halted.is_set() else "STOPPING_FORMAT_CAPACITY",
                original_generation_completed=8000,
                review_completed=len(completed),
                review_denominator=2000,
                blocked=blocked,
                budget=ledger.snapshot(),
                training_started=False,
                original_generation_reused=True,
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
        timeout=300,
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
                request = checked_input(output, plan, task_id)["requests"][reviewer]
                publish(
                    directory / "started",
                    dict(
                        at=now(),
                        task_id=task_id,
                        reviewer=reviewer,
                        review_id=rid,
                        max_output_tokens=request["max_output_tokens"],
                    ),
                )
                try:
                    artifact = await request_review(
                        ledger=ledger,
                        api_key=key,
                        episode_id=rid,
                        request=request,
                        client=client,
                        timeout=max(180, math.ceil(90 + request["max_output_tokens"] / 128)),
                    )
                    publish(directory / "response", artifact)
                    completed[rid] = artifact
                    assessment = assess(artifact, request)
                    publish(directory / "validation", assessment)
                    if not assessment["format_capacity_admitted"]:
                        blocked.append(dict(review_id=rid, reason=assessment["error"]))
                        # Complete the fixed calibration cohort, but never expand it on failure.
                        if phase != "CAPACITY_CALIBRATION":
                            halted.set()
                except BaseException as error:
                    publish(
                        directory / "blocked",
                        dict(at=now(), error_type=type(error).__name__, retry=False),
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
    return blocked


def final_inventory(output, plan, ledger, completed):
    require(len(completed) == 2000, "fixed dual reviews not complete")
    counts, tasks = Counter(), []
    for task_id in plan["task_ids"]:
        prepared = checked_prepared(ORIGINAL, task_id)
        checks = [
            read_json(
                review_directory(output, review_id(plan, task_id, i)) / "validation/record.json"
            )
            for i in (0, 1)
        ]
        errors = [v["error"] for v in checks if not v["format_capacity_admitted"]]
        resolution = (
            unknown_resolution(prepared, errors)
            if errors
            else resolve_pair(
                checks[0]["validated"], checks[1]["validated"], prepared["mechanical"]
            )
        )
        persist(Path(output) / "resolution" / digest(task_id), resolution)
        if task_id in plan["task_ids"][:10]:
            persist(
                Path(output) / "pending_human_audit" / digest(task_id),
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
        tasks.append(
            dict(
                task_id=task_id,
                candidates=8,
                joint_valid=len(valid),
                mapping_complete=mapped,
                states=dict(states),
                n_x=n,
                agreed_masks=all(v["encoding_manifest"] is not None for v in valid),
                prior={s: c / n for s, c in states.items()},
                empirical_K_per_original={s: 1 / c for s, c in states.items()},
                conditional_state_entropy=-sum(c / n * math.log(c / n) for c in states.values())
                if n
                else None,
                singleton_states=sum(c == 1 for c in states.values()),
                D_pi=len(states) - 1 if states else None,
            )
        )
    supported = [t for t in tasks if t["mapping_complete"]]
    complete = len(supported) == 1000 and all(t["agreed_masks"] for t in tasks)
    result = bound(
        dict(
            protocol_id=plan["id"],
            original_tasks=1000,
            original_slots=8000,
            counts=dict(counts),
            tasks=tasks,
            material_admission_only=complete,
            Student_encoding_complete=False,
            supported_task_count=len(supported),
            observed_D_pi=sum(t["D_pi"] for t in supported),
            D_pi=sum(t["D_pi"] for t in supported) if len(supported) == 1000 else None,
            M_flex=sum(len(t["states"]) > 1 for t in supported) / 1000,
            validity_yield=counts["joint_valid"] / 8000,
            training_started=False,
            budget=ledger.snapshot(),
            original_generation_reused=True,
            historical_failure_artifacts_retained=True,
        )
    )
    persist(Path(output) / "inventory_complete", result)
    return result


async def run(output, env_file):
    output = Path(output)
    plan = checked_plan(output)
    ledger = activate(output, plan)
    completed = recover(output, plan)
    failed = [
        rid
        for rid in completed
        if not read_json(review_directory(output, rid) / "validation/record.json")[
            "format_capacity_admitted"
        ]
    ]
    if failed:
        status(
            output,
            dict(
                at=now(),
                phase="BLOCKED_EXISTING_FORMAT_CAPACITY_FAILURE",
                review_completed=len(completed),
                review_denominator=2000,
                blocked=failed,
                budget=ledger.snapshot(),
                new_calls=0,
                training_started=False,
            ),
        )
        return
    key = _key(env_file)
    os.environ.pop("DEEPSEEK_API_KEY", None)
    jobs = [(t, i) for t in plan["calibration"]["task_ids"] for i in (0, 1)]
    await run_batch(output, plan, ledger, key, completed, jobs, "CAPACITY_CALIBRATION")
    checks = {}
    for task_id, reviewer in jobs:
        rid = review_id(plan, task_id, reviewer)
        path = review_directory(output, rid) / "validation/record.json"
        checks[rid] = read_json(path)["format_capacity_admitted"] if path.exists() else False
    admitted = all(checks.values()) and not ledger.unsettled() and not ledger.snapshot()["halt"]
    if (output / "capacity_gate/record.json").exists():
        gate = read_json(output / "capacity_gate/record.json")
        require(
            gate["id"] == digest({k: v for k, v in gate.items() if k != "id"})
            and gate["protocol_id"] == plan["id"]
            and gate["checks"] == checks
            and gate["admitted"] == admitted,
            "capacity admission cannot change on restart",
        )
    else:
        gate = bound(
            dict(
                at=now(),
                protocol_id=plan["id"],
                checks=checks,
                admitted=admitted,
                uses_native_score_or_positive_V_trace=False,
                budget=ledger.snapshot(),
            )
        )
        persist(output / "capacity_gate", gate)
    if not admitted:
        status(
            output,
            dict(
                at=now(),
                phase="CAPACITY_FORMAT_BLOCKED",
                review_completed=len(completed),
                review_denominator=2000,
                expanded_beyond_12=False,
                budget=ledger.snapshot(),
                training_started=False,
            ),
        )
        return
    remaining = [(t, i) for t in plan["task_ids"] for i in (0, 1)]
    blocked = await run_batch(output, plan, ledger, key, completed, remaining, "REVIEWING")
    if blocked or len(completed) != 2000:
        status(
            output,
            dict(
                at=now(),
                phase="REVIEW_INCOMPLETE",
                review_completed=len(completed),
                review_denominator=2000,
                blocked=blocked,
                budget=ledger.snapshot(),
                training_started=False,
            ),
        )
        return
    completed = recover(output, plan)
    result = final_inventory(output, plan, ledger, completed)
    status(
        output,
        dict(
            at=now(),
            phase="INVENTORY_COMPLETE",
            review_completed=2000,
            review_denominator=2000,
            supported_task_count=result["supported_task_count"],
            material_admission_only=result["material_admission_only"],
            budget=ledger.snapshot(),
            training_started=False,
        ),
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("register", "start", "run", "status"))
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--env-file", type=Path, default=ENV_FILE)
    parser.add_argument("--parent-revision", type=Path)
    args = parser.parse_args(argv)
    if args.action == "register":
        print(dict(protocol_id=register(args.output, parent_revision=args.parent_revision)["id"]))
    elif args.action == "status":
        print(read_json(args.output / "status.json"))
    elif args.action == "run":
        # Same lock as the former controller: the joint budget never has two controllers.
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
