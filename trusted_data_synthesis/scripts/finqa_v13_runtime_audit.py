#!/usr/bin/env python3
"""Read-only V13/C16 exact-roster runtime accounting; new report output only."""

import argparse
import hashlib
import json
import os
import sqlite3
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from decimal import ROUND_CEILING, Decimal
from pathlib import Path

from finqa_v12_runtime_audit import (
    TOKENS,
    aggregate,
    digest,
    encoded,
    epoch,
    file_binding,
    read_record,
    require,
    utc,
)

PROJECT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT / "trusted_data_synthesis/src"))
from trusted_synthesis.finance_research.probe_budget import _request_record_digest  # noqa: E402

DEFAULT = (
    PROJECT
    / "trusted_data_synthesis/artifacts/finance_research_20260928/finqa_v6_01/v13_material_02"
)
SQL = """
SELECT v.episode_id AS roster_episode_id,v.job_json,a.category,r.*,
 (SELECT COUNT(*) FROM events e
  WHERE e.invocation_id=r.invocation_id AND e.action='dispatched') AS dispatch_events,
 (SELECT MAX(at_unix) FROM events e
  WHERE e.invocation_id=r.invocation_id AND e.action='unknown') AS unknown_at
FROM v13_review_roster v
LEFT JOIN v10_request_allocations a ON a.episode_id=v.episode_id
LEFT JOIN requests r ON r.invocation_id=a.invocation_id
ORDER BY v.episode_id,r.invocation_id
"""


def summarize(rows, rates):
    settled = [r for r in rows if r["state"] == "SETTLED"]
    unknown = [r for r in rows if r["state"] == "UNKNOWN"]
    first = min(r["dispatched_at"] for r in rows)
    last = max(r["terminal_at"] for r in rows)
    events = sorted(
        [(r["dispatched_at"], 1) for r in rows] + [(r["terminal_at"], -1) for r in rows]
    )
    active = peak = 0
    for _, delta in events:
        active += delta
        require(active >= 0, "invalid logical in-flight timestamp sweep")
        peak = max(peak, active)
    require(active == 0, "logical in-flight must drain")
    cost = sum(r["settled_microcny"] for r in settled)
    held = sum(r["reserved_microcny"] for r in unknown)
    return dict(
        attempted=len(rows),
        actual_returns=len(settled),
        network_unknowns=len(unknown),
        by_purpose={
            p: dict(
                attempted=sum(r["purpose"] == p for r in rows),
                actual_returns=sum(r["purpose"] == p for r in settled),
                network_unknowns=sum(r["purpose"] == p for r in unknown),
            )
            for p in ("projection", "mapping")
        },
        request_models=dict(Counter(r["requested_model"] for r in rows)),
        physical_attempts=dict(Counter(str(r["coordinates"]["attempt_index"]) for r in rows)),
        dispatch_events_per_invocation=dict(Counter(str(r["dispatch_events"]) for r in rows)),
        actual_return_statistics=aggregate(settled, rates) if settled else None,
        known_settled_microcny=cost,
        known_settled_cny=f"{Decimal(cost) / 1000000:.6f}",
        permanent_unknown_hold_microcny=held,
        permanent_unknown_hold_cny=f"{Decimal(held) / 1000000:.6f}",
        incremental_exposure_microcny=cost + held,
        unknown_usage_known=False if unknown else None,
        unknown_usage_not_counted_as_zero=True,
        first_dispatch_utc=utc(first),
        last_actual_settlement_utc=utc(max(r["settled_at"] for r in settled)),
        last_request_terminal_utc=utc(last),
        first_dispatch_to_last_terminal_seconds=last - first,
        attempted_calls_per_second=len(rows) / (last - first),
        actual_returns_per_second=len(settled) / (last - first),
        logical_peak_inflight=peak,
        mean_logical_inflight=sum(r["terminal_at"] - r["dispatched_at"] for r in rows)
        / (last - first),
        inflight_semantics=(
            "DISPATCHED to SETTLED or UNKNOWN event; same-time terminal before dispatch; "
            "not packet concurrency"
        ),
        unknowns=[
            dict(
                invocation_id=r["invocation_id"],
                episode_id=r["episode_id"],
                purpose=r["purpose"],
                reserved_microcny=r["reserved_microcny"],
                max_output_tokens=r["requested_max_tokens"],
                dispatched_at_utc=utc(r["dispatched_at"]),
                unknown_at_utc=utc(r["terminal_at"]),
                exception_type=r["exception_type"],
                acknowledgement_id=r["acknowledgement_id"],
                original_row_sha256=r["original_row_sha256"],
                model_response=None,
                usage=None,
            )
            for r in unknown
        ],
    )


def run(output, destination):
    paths = dict(
        plan=output / "registration/record.json",
        deployment=output / "deployment_budget/record.json",
        initial_launch=output / "workflow_launch/record.json",
        stopped=output / "report_stop_01/record/record.json",
        c16_registration=output / "runtime_c16_01/registration/record.json",
        c16_launch=output / "runtime_c16_01/launch/record.json",
        status=output / "status.json",
        seal=output / "completion_seal/record.json",
    )
    records, refs = {}, {}
    for name, path in paths.items():
        records[name], refs[name] = read_record(path, bound=name != "status")
    plan, status, runtime, seal = (
        records[name] for name in ("plan", "status", "c16_registration", "seal")
    )
    jobs = {j["episode_id"]: j for j in plan["jobs"]}
    old = {r["episode_id"]: r for r in runtime["baseline"]["attempted"]}
    remaining = set(runtime["baseline"]["unsent_episode_ids"])
    require(
        len(jobs) == 1316
        and len(old) == 288
        and len(remaining) == 1028
        and set(old).isdisjoint(remaining)
        and set(old) | remaining == set(jobs),
        "fixed V13/C16 exact scope differs",
    )
    require(
        runtime["original_plan_id"] == plan["id"] == seal["registration_id"]
        and status["seal_id"] == seal["id"]
        and status["phase"] == "MATERIAL_ANNOTATIONS_COMPLETE",
        "final plan/runtime/seal identity differs",
    )
    source = PROJECT / "trusted_data_synthesis/src/trusted_synthesis/finance_research"
    source_refs = {
        name: file_binding(source / name)
        for name in (
            "probe_budget.py",
            "v13_budget.py",
            "v13_material_provider.py",
            "v13_material_controller.py",
            "v13_runtime_c16.py",
        )
    }
    for name, ref in source_refs.items():
        expected = (
            runtime["runtime_source"]["sha256"]
            if name == "v13_runtime_c16.py"
            else plan["source_bindings"][name]
        )
        require(ref["sha256"] == expected, "frozen source changed: " + name)
    wallet = Path(plan["budget_database"]).resolve()
    started, clock = datetime.now(timezone.utc).isoformat(), time.perf_counter()
    rows, stream = [], hashlib.sha256()
    with sqlite3.connect(wallet.as_uri() + "?mode=ro", uri=True, isolation_level=None) as db:
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA query_only=ON")
        db.execute("BEGIN")
        config = json.loads(
            db.execute("SELECT value FROM metadata WHERE key='config'").fetchone()[0]
        )
        require(digest(config) == plan["budget_config_sha256"], "wallet config changed")
        fields = [r["name"] for r in db.execute("PRAGMA table_info(requests)")]
        schema = [
            dict(r)
            for r in db.execute(
                "SELECT type,name,tbl_name,sql FROM sqlite_master ORDER BY type,name"
            )
        ]
        rates = tuple(
            Decimal(config["price_sheet"][k])
            for k in (
                "input_hit_cny_per_million",
                "input_miss_cny_per_million",
                "output_cny_per_million",
            )
        )
        for item in db.execute(SQL):
            selected = dict(item)
            raw = {k: selected[k] for k in fields}
            job = json.loads(selected["job_json"])
            require(job == jobs.get(selected["roster_episode_id"]), "roster/plan changed")
            coords = json.loads(raw["coordinates_json"])
            body = json.loads(raw["request_body"])
            row_sha = _request_record_digest(raw)
            stream.update(
                encoded(
                    dict(
                        episode_id=job["episode_id"],
                        invocation_id=raw["invocation_id"],
                        row_sha256=row_sha,
                    )
                )
                + b"\n"
            )
            require(
                coords["episode_id"] == job["episode_id"]
                and coords["invocation_id"] == raw["invocation_id"]
                and coords["run_id"] == config["run_id"]
                and coords["attempt_index"] == 1
                and coords["turn_index"] == 0
                and selected["dispatch_events"] == 1
                and selected["category"] == "review_mapping"
                and body["model"] == "deepseek-flash"
                and body["max_tokens"] == job["max_output_tokens"]
                and raw["request_sha256"] == job["request_sha256"] == digest(body)
                and hashlib.sha256(raw["request_body"]).hexdigest() == job["request_body_sha256"],
                "request/attempt/model/cap/original bytes differ",
            )
            if job["episode_id"] in old:
                require(
                    old[job["episode_id"]]["original_row_sha256"] == row_sha,
                    "one of original 288 wallet rows changed",
                )
            row = {
                k: raw[k]
                for k in (
                    "invocation_id",
                    "state",
                    "dispatched_at",
                    "settled_at",
                    "reserved_microcny",
                    "settled_microcny",
                    "http_status",
                    "response_classification",
                )
            }
            row.update(
                episode_id=job["episode_id"],
                purpose=job["kind"],
                role=job["kind"],
                coordinates=coords,
                requested_model=body["model"],
                requested_max_tokens=body["max_tokens"],
                original_row_sha256=row_sha,
                dispatch_events=selected["dispatch_events"],
            )
            if row["state"] == "SETTLED":
                usage = json.loads(raw["usage_json"])
                require(
                    row["response_classification"] == "model_response"
                    and row["http_status"] == 200
                    and all(type(usage.get(k)) is int and usage[k] >= 0 for k in TOKENS)
                    and usage["prompt_tokens"]
                    == usage["prompt_cache_hit_tokens"] + usage["prompt_cache_miss_tokens"]
                    and usage["total_tokens"] == usage["prompt_tokens"] + usage["completion_tokens"]
                    and usage["completion_tokens"] <= body["max_tokens"],
                    "usage/classification invalid",
                )
                fee = (
                    rates[0] * usage["prompt_cache_hit_tokens"]
                    + rates[1] * usage["prompt_cache_miss_tokens"]
                    + rates[2] * usage["completion_tokens"]
                )
                require(
                    int(fee.to_integral_value(rounding=ROUND_CEILING)) == row["settled_microcny"],
                    "tariff discrepancy",
                )
                row.update(usage=usage, terminal_at=row["settled_at"])
            else:
                require(
                    row["state"] == "UNKNOWN"
                    and all(
                        raw[k] is None
                        for k in (
                            "usage_json",
                            "response_body",
                            "http_status",
                            "settled_microcny",
                            "settled_at",
                        )
                    ),
                    "unreturned row cannot become billed return",
                )
                evidence = json.loads(raw["evidence_json"])
                ack = json.loads(
                    db.execute(
                        "SELECT value FROM metadata WHERE key=?",
                        ("acknowledged_unknown:" + raw["invocation_id"],),
                    ).fetchone()[0]
                )
                require(
                    ack["original_unknown_record_sha256"] == row_sha
                    and ack["permanent_reserved_microcny"] == row["reserved_microcny"]
                    and evidence["service_response_received"] is False
                    and selected["unknown_at"] is not None,
                    "unknown original bytes/hold acknowledgement differs",
                )
                row.update(
                    usage=None,
                    terminal_at=selected["unknown_at"],
                    exception_type=evidence.get("exception_type"),
                    acknowledgement_id=ack["id"],
                )
            require(row["dispatched_at"] <= row["terminal_at"], "bad terminal timestamp")
            rows.append(row)
        counters = dict(db.execute("SELECT * FROM counters WHERE singleton=1").fetchone())
        quotas = {r["category"]: dict(r) for r in db.execute("SELECT * FROM v10_quotas")}
        halt = db.execute("SELECT value FROM metadata WHERE key='halt'").fetchone()
        db.rollback()
    finished, elapsed = datetime.now(timezone.utc).isoformat(), time.perf_counter() - clock
    require(
        len(rows)
        == len({r["episode_id"] for r in rows})
        == len({r["invocation_id"] for r in rows})
        == 1316,
        "missing or duplicate original invocation",
    )
    initial = [r for r in rows if r["episode_id"] in old]
    continuation = [r for r in rows if r["episode_id"] in remaining]
    total = summarize(rows, rates)
    before, final = records["deployment"]["before"], status["budget"]
    require(
        total["actual_returns"] == seal["actual_returns"] == 1304
        and total["network_unknowns"] == seal["network_unknowns"] == 12,
        "seal terminal counts disagree with original rows",
    )
    require(
        final["requests_reserved"] - before["requests_reserved"] == 1316
        and final["settled_tariff_microcny"] - before["settled_tariff_microcny"]
        == total["known_settled_microcny"]
        and final["held_microcny"] - before["held_microcny"]
        == total["permanent_unknown_hold_microcny"]
        and final["unknown_requests"] - before["unknown_requests"] == 12,
        "new prefix accounting does not conserve",
    )
    require(
        counters["spent"] == final["settled_tariff_microcny"]
        and counters["held"] == final["held_microcny"]
        and counters["requests"] == final["requests_reserved"]
        and counters["unknown"] == final["unknown_requests"]
        and counters["pending"] == 0
        and halt is None,
        "live read snapshot differs from finalized accounting",
    )
    sub = quotas["review_mapping"]
    c16_start = epoch(records["c16_launch"]["at"])
    initial_end = max(r["terminal_at"] for r in initial)
    first = min(r["dispatched_at"] for r in rows)
    last = max(r["terminal_at"] for r in rows)
    require(
        min(r["dispatched_at"] for r in continuation) >= c16_start,
        "continuation predates registered restart",
    )
    result = dict(
        schema="v13_final_runtime_audit.v1",
        generated_at_utc=datetime.now(timezone.utc).isoformat(),
        source_records=refs,
        execution_sources=source_refs,
        audit_script=file_binding(Path(__file__).resolve()),
        helper_script=file_binding(Path(__file__).parent / "finqa_v12_runtime_audit.py"),
        wallet=dict(
            path=str(wallet),
            mode="ro",
            query_only=True,
            sqlite_version=sqlite3.sqlite_version,
            schema_sha256=digest(schema),
            config_sha256=digest(config),
            row_stream_sha256=stream.hexdigest(),
            selected_request_rows=1316,
            full_wallet_hash_performed=False,
            query=SQL.strip(),
        ),
        audit_read_started_utc=started,
        audit_read_finished_utc=finished,
        audit_read_seconds=elapsed,
        total=total,
        initial_288=summarize(initial, rates),
        c16_original_unsent_1028=summarize(continuation, rates),
        by_purpose={
            p: summarize([r for r in rows if r["purpose"] == p], rates)
            for p in ("projection", "mapping")
        },
        price_sheet=config["price_sheet"],
        cost_semantics=(
            "Known costs use the frozen peak tariff, rounded up per returned request. "
            "UNKNOWN usage and vendor charges are unverified; full reservations remain exposure. "
            "Not a provider invoice."
        ),
        original_288_row_hashes_unchanged=True,
        no_new_episode_or_attempt=True,
        one_dispatch_event_per_original_invocation=True,
        old_unknown_count_and_aggregate_holds_unchanged=True,
        old_unknown_count=before["unknown_requests"],
        old_held_microcny=before["held_microcny"],
        timing=dict(
            original_launch_utc=records["initial_launch"]["at"],
            first_dispatch_utc=utc(first),
            initial_last_terminal_utc=utc(initial_end),
            c16_registration_utc=runtime["at"],
            c16_launch_utc=records["c16_launch"]["at"],
            last_request_terminal_utc=utc(last),
            completion_status_utc=status["at"],
            launch_to_completion_status_seconds=epoch(status["at"])
            - epoch(records["initial_launch"]["at"]),
            first_dispatch_to_last_terminal_seconds=last - first,
            idle_gap_initial_terminal_to_c16_first_dispatch_seconds=min(
                r["dispatched_at"] for r in continuation
            )
            - initial_end,
            c16_launch_to_completion_status_seconds=epoch(status["at"]) - c16_start,
            last_terminal_to_completion_status_seconds=epoch(status["at"]) - last,
            independently_timestamped_seal=False,
        ),
        closing_budget=dict(
            global_cap_microcny=final["effective_hard_cap_microcny"],
            global_spent_microcny=counters["spent"],
            global_held_microcny=counters["held"],
            global_remaining_microcny=final["remaining_exposure_microcny"],
            review_mapping_cap_microcny=final["v10_partition"]["effective_limits"][
                "review_mapping"
            ]["microcny"],
            review_mapping_spent_microcny=sub["spent"],
            review_mapping_held_microcny=sub["held"],
            review_mapping_remaining_microcny=1300000000 - sub["spent"] - sub["held"],
            global_request_cap=final["request_cap"],
            global_requests=counters["requests"],
            review_request_cap=25000,
            review_requests=sub["requests"],
            review_requests_remaining=25000 - sub["requests"],
            unused_requests_authorize_further_calls=False,
            pending=0,
            halt=None,
        ),
        report_only=True,
        wallet_modified=False,
        production_code_modified=False,
        model_calls_in_audit=0,
        original_annotation_text_rejudged=False,
    )
    result["id"] = digest(result)
    destination.mkdir(parents=True, exist_ok=False)
    with (destination / "record.json").open("xb") as stream:
        stream.write(encoded(result) + b"\n")
        stream.flush()
        os.fsync(stream.fileno())
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT)
    parser.add_argument("--destination", type=Path)
    args = parser.parse_args()
    output = args.output.resolve()
    destination = (args.destination or output / "report_final_01/runtime_analysis").resolve()
    require(
        not destination.exists(), "new report directory required; never overwrite existing evidence"
    )
    result = run(output, destination)
    print(
        json.dumps(
            dict(
                id=result["id"],
                output=str(destination),
                counts={
                    k: result["total"][k]
                    for k in ("attempted", "actual_returns", "network_unknowns")
                },
                known_settled_cny=result["total"]["known_settled_cny"],
                new_held_cny=result["total"]["permanent_unknown_hold_cny"],
            ),
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
