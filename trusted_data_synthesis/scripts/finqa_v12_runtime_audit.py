#!/usr/bin/env python3
"""One read-only exact-roster V12 accounting scan; publish a new immutable summary.

No API, model, GPU, credential, review-text parsing, historical request scan, or
wallet write. The sole output is a new report_audit_01/runtime_analysis directory.
"""

import argparse
import hashlib
import json
import math
import os
import sqlite3
import time
from collections import Counter
from datetime import datetime, timezone
from decimal import ROUND_CEILING, Decimal
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[2]
DEFAULT = (
    PROJECT
    / "trusted_data_synthesis/artifacts/finance_research_20260928/finqa_v6_01/v12_rereview_02"
)
TOKENS = (
    "prompt_tokens",
    "prompt_cache_hit_tokens",
    "prompt_cache_miss_tokens",
    "completion_tokens",
    "total_tokens",
)
SQL = """
SELECT v.episode_id, v.job_json, a.category, a.invocation_id AS allocated_invocation_id,
       r.invocation_id, r.coordinates_json, r.request_sha256, r.state,
       r.created_at, r.dispatched_at, r.settled_at, r.reserved_microcny,
       r.settled_microcny, r.usage_json, r.http_status, r.response_classification,
       json_extract(r.request_body,'$.model') AS requested_model,
       json_extract(r.request_body,'$.max_tokens') AS requested_max_tokens
FROM v12_review_roster v
LEFT JOIN v10_request_allocations a ON a.episode_id=v.episode_id
LEFT JOIN requests r ON r.invocation_id=a.invocation_id
ORDER BY v.episode_id, r.invocation_id
"""


def encoded(value):
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode()


def digest(value):
    return hashlib.sha256(encoded(value)).hexdigest()


def require(value, message):
    if not value:
        raise ValueError(message)


def read_record(path, *, bound=True):
    raw = path.read_bytes()
    value = json.loads(raw)
    if bound:
        require(
            value.get("id") == digest({k: v for k, v in value.items() if k != "id"}),
            f"record digest changed: {path}",
        )
    return value, dict(
        path=str(path), bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest(), id=value.get("id")
    )


def file_binding(path):
    raw = path.read_bytes()
    return dict(path=str(path), bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())


def utc(value):
    return datetime.fromtimestamp(value, timezone.utc).isoformat()


def epoch(value):
    return datetime.fromisoformat(value).timestamp()


def quantiles(values):
    values = sorted(values)
    return dict(
        count=len(values),
        mean=sum(values) / len(values),
        minimum=values[0],
        p50_nearest_rank=values[math.ceil(len(values) * 0.5) - 1],
        p95_nearest_rank=values[math.ceil(len(values) * 0.95) - 1],
        maximum=values[-1],
    )


def aggregate(rows, rates):
    usage = {name: sum(row["usage"][name] for row in rows) for name in TOKENS}
    raw_fee = sum(
        (
            rates[0] * row["usage"]["prompt_cache_hit_tokens"]
            + rates[1] * row["usage"]["prompt_cache_miss_tokens"]
            + rates[2] * row["usage"]["completion_tokens"]
            for row in rows
        ),
        Decimal(0),
    )
    cost = sum(row["settled_microcny"] for row in rows)
    return dict(
        calls=len(rows),
        states=dict(Counter(row["state"] for row in rows)),
        physical_attempt_indices=dict(
            Counter(str(row["coordinates"]["attempt_index"]) for row in rows)
        ),
        turn_indices=dict(Counter(str(row["coordinates"]["turn_index"]) for row in rows)),
        requested_models=dict(Counter(row["requested_model"] for row in rows)),
        response_classifications=dict(Counter(row["response_classification"] for row in rows)),
        http_statuses=dict(Counter(str(row["http_status"]) for row in rows)),
        max_output_token_caps=dict(Counter(str(row["requested_max_tokens"]) for row in rows)),
        actual_usage=usage,
        mean_tokens_per_call={name: value / len(rows) for name, value in usage.items()},
        cache_hit_fraction=usage["prompt_cache_hit_tokens"] / usage["prompt_tokens"],
        actual_completion_tokens_distribution=quantiles(
            [row["usage"]["completion_tokens"] for row in rows]
        ),
        settled_microcny=cost,
        settled_cny=f"{Decimal(cost) / 1_000_000:.6f}",
        mean_settled_cny_per_call=str(Decimal(cost) / Decimal(len(rows)) / 1_000_000),
        unrounded_tariff_microcny=str(raw_fee),
        per_request_rounding_increment_microcny=str(Decimal(cost) - raw_fee),
        dispatch_to_settle_seconds=quantiles(
            [row["settled_at"] - row["dispatched_at"] for row in rows]
        ),
        first_dispatch_utc=utc(min(row["dispatched_at"] for row in rows)),
        last_settlement_utc=utc(max(row["settled_at"] for row in rows)),
    )


def inflight_profile(rows):
    events = sorted(
        [(row["dispatched_at"], 1) for row in rows] + [(row["settled_at"], -1) for row in rows]
    )
    active = peak = 0
    for _, delta in events:
        active += delta
        require(active >= 0, "in-flight sweep became negative")
        peak = max(peak, active)
    require(active == 0, "in-flight sweep did not drain")
    span = events[-1][0] - events[0][0]
    return dict(
        logical_peak_dispatched_unsettled=peak,
        same_timestamp_rule="settlement (-1) before dispatch (+1)",
        interpretation="Ledger DISPATCHED to SETTLED intervals, not packet-level connections.",
        mean_logical_inflight=sum(r["settled_at"] - r["dispatched_at"] for r in rows) / span,
        settled_calls_per_second=len(rows) / span,
        settled_calls_per_minute=len(rows) * 60 / span,
        window_seconds=span,
    )


def run(output, destination):
    paths = {
        "plan": output / "registration/record.json",
        "deployment_budget": output / "deployment_budget/record.json",
        "launch": output / "launch/record.json",
        "status": output / "status.json",
        "seal": output / "review_seal/record.json",
    }
    records, bindings = {}, {}
    for name, path in paths.items():
        records[name], bindings[name] = read_record(path, bound=name != "status")
    plan, deployment, launch, status, seal = (records[key] for key in paths)
    expected = {job["episode_id"]: job for job in plan["jobs"]}
    require(len(expected) == len(plan["jobs"]) == 11438, "full exact new A/B denominator required")
    require(
        status["phase"] == "REREVIEW_COMPLETE"
        and status["seal_id"] == seal["id"]
        and status["registration_id"] == plan["id"] == seal["registration_id"],
        "final source coordinates differ",
    )
    require(
        launch["plan_id"] == plan["id"] == deployment["plan_id"],
        "deployment/launch coordinates differ",
    )
    source = PROJECT / "trusted_data_synthesis/src/trusted_synthesis/finance_research"
    source_bindings = {
        name: file_binding(source / name)
        for name in ("probe_budget.py", "v12_review_controller.py", "v12_review_provider.py")
    }
    require(
        all(v["sha256"] == plan["source_bindings"][name] for name, v in source_bindings.items()),
        "executed accounting/controller/provider source differs from registered source",
    )
    wallet = Path(plan["budget_database"]).resolve()
    rows, selected_stream = [], hashlib.sha256()
    query_started_utc = datetime.now(timezone.utc).isoformat()
    query_clock = time.perf_counter()
    with sqlite3.connect(
        wallet.as_uri() + "?mode=ro", uri=True, isolation_level=None
    ) as connection:
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA query_only=ON")
        connection.execute("BEGIN")
        config = json.loads(
            connection.execute("SELECT value FROM metadata WHERE key='config'").fetchone()[0]
        )
        require(digest(config) == plan["budget_config_sha256"], "original wallet config differs")
        permit = json.loads(
            connection.execute(
                "SELECT value FROM metadata WHERE key='v12_review_matrix_request_transfer_01'"
            ).fetchone()[0]
        )
        require(
            permit["plan_id"] == plan["id"] and permit["id"] == deployment["permit_id"],
            "wallet matrix permit differs",
        )
        schema = [
            dict(r)
            for r in connection.execute(
                "SELECT type,name,tbl_name,sql FROM sqlite_master ORDER BY type,name"
            )
        ]
        database_binding = dict(
            path=str(wallet),
            sqlite_version=sqlite3.sqlite_version,
            open_uri_mode="ro",
            query_only=connection.execute("PRAGMA query_only").fetchone()[0],
            schema_sha256=digest(schema),
            user_version=connection.execute("PRAGMA user_version").fetchone()[0],
            metadata_config_sha256=digest(config),
            permit_id=permit["id"],
            full_wallet_hash_performed=False,
            transaction="BEGIN read snapshot; ROLLBACK after SELECTs",
        )
        rates = tuple(
            Decimal(config["price_sheet"][key])
            for key in (
                "input_hit_cny_per_million",
                "input_miss_cny_per_million",
                "output_cny_per_million",
            )
        )
        for selected in connection.execute(SQL):
            row = dict(selected)
            selected_stream.update(encoded(row) + b"\n")
            job = json.loads(row.pop("job_json"))
            require(job == expected.get(row["episode_id"]), "wallet roster and frozen plan differ")
            coords = json.loads(row.pop("coordinates_json"))
            usage = json.loads(row.pop("usage_json"))
            require(
                row["invocation_id"] == row["allocated_invocation_id"] == coords["invocation_id"]
                and coords["run_id"] == config["run_id"]
                and coords["episode_id"] == row["episode_id"]
                and coords["attempt_index"] == 1
                and coords["turn_index"] == 0,
                "missing/multiple/changed actual attempt",
            )
            require(
                row["category"] == "review_mapping"
                and row["state"] == "SETTLED"
                and row["response_classification"] == "model_response"
                and row["requested_model"] == "deepseek-flash"
                and row["request_sha256"] == job["request_sha256"]
                and row["requested_max_tokens"] == job["max_output_tokens"]
                and 200 <= row["http_status"] < 300,
                "new call is not the registered settled response",
            )
            require(
                all(type(usage.get(key)) is int and usage[key] >= 0 for key in TOKENS)
                and usage["prompt_tokens"]
                == usage["prompt_cache_hit_tokens"] + usage["prompt_cache_miss_tokens"]
                and usage["total_tokens"] == usage["prompt_tokens"] + usage["completion_tokens"]
                and usage["completion_tokens"] <= row["requested_max_tokens"],
                "usage or output cap differs",
            )
            raw_fee = (
                rates[0] * usage["prompt_cache_hit_tokens"]
                + rates[1] * usage["prompt_cache_miss_tokens"]
                + rates[2] * usage["completion_tokens"]
            )
            require(
                row["settled_microcny"] == int(raw_fee.to_integral_value(rounding=ROUND_CEILING)),
                "per-request tariff does not reconcile",
            )
            require(
                row["created_at"] <= row["dispatched_at"] <= row["settled_at"],
                "invalid timestamp order",
            )
            rows.append(dict(**row, role=job["role"], coordinates=coords, usage=usage))
        current_counters = dict(
            connection.execute("SELECT * FROM counters WHERE singleton=1").fetchone()
        )
        current_quotas = {
            r["category"]: dict(r) for r in connection.execute("SELECT * FROM v10_quotas")
        }
        connection.rollback()
    query_finished_utc = datetime.now(timezone.utc).isoformat()
    query_seconds = time.perf_counter() - query_clock
    require(
        len(rows)
        == len({r["episode_id"] for r in rows})
        == len({r["invocation_id"] for r in rows})
        == 11438,
        "new fixed matrix incomplete/duplicated",
    )
    total = aggregate(rows, rates)
    before, final = deployment["before"], status["budget"]
    require(
        final["settled_tariff_microcny"] - before["settled_tariff_microcny"]
        == total["settled_microcny"]
        and final["requests_reserved"] - before["requests_reserved"] == len(rows)
        and final["held_microcny"] == before["held_microcny"]
        and final["unknown_requests"] == before["unknown_requests"]
        and final["pending_requests"] == status["active"] == status["network_unknowns"] == 0,
        "run delta does not reconcile with frozen final snapshot",
    )
    require(
        current_counters["spent"] == final["settled_tariff_microcny"]
        and current_counters["requests"] == final["requests_reserved"]
        and current_counters["held"] == final["held_microcny"]
        and current_counters["pending"] == 0,
        "wallet changed since final status; report snapshot explicitly instead",
    )
    sub = final["v10_partition"]["consumed"]["review_mapping"]
    require(
        all(current_quotas["review_mapping"][k] == sub[k] for k in sub), "final subquota differs"
    )
    first, last = min(r["dispatched_at"] for r in rows), max(r["settled_at"] for r in rows)
    end = epoch(status["at"])
    # The control field is assigned at wave entry; no update after the final gather.
    controller = (source / "v12_review_controller.py").read_text()
    require(
        "successful_transport_settlements=success" in controller
        and "success += len(returned)" in controller,
        "counter implementation changed",
    )
    final_tail = len(rows) - status["successful_transport_settlements"]
    ordered_dispatch = sorted(rows, key=lambda r: (r["dispatched_at"], r["invocation_id"]))
    result = dict(
        schema="v12_exact_roster_runtime_audit.v1",
        generated_at_utc=datetime.now(timezone.utc).isoformat(),
        source_records=bindings,
        execution_source_bindings=source_bindings,
        audit_script=file_binding(Path(__file__).resolve()),
        wallet_binding=database_binding,
        read_snapshot_started_at_utc=query_started_utc,
        read_snapshot_finished_at_utc=query_finished_utc,
        read_snapshot_elapsed_seconds=query_seconds,
        selected_request_columns_sha256=selected_stream.hexdigest(),
        query=SQL.strip(),
        one_exact_roster_request_scan=True,
        old_request_rows_scanned=False,
        review_text_loaded_or_rejudged=False,
        wallet_mutated=False,
        model_calls=0,
        model_observation=(
            "Original HTTP request model selected in SQLite; response-model contract was "
            "verified by the hash-bound provider at settlement, not reparsed here."
        ),
        fixed_denominators=dict(
            slots=5719,
            requests=11438,
            all_authentic_terminals=seal["all_registered_jobs_have_authentic_terminals"],
            all_actual_returns=seal["all_model_responses_returned"],
            physical_attempts=seal["physical_attempts"],
        ),
        total=total,
        logical_inflight_and_throughput=inflight_profile(rows),
        by_role={
            role: aggregate([r for r in rows if r["role"] == role], rates) for role in ("A", "B")
        },
        price_sheet=config["price_sheet"],
        tariff_formula=(
            "For each request: ceil(0.04*cache_hit + 2*cache_miss + 8*completion) micro-CNY; "
            "sum per-request rounded amounts. Rates are CNY per million tokens. "
            "Not a provider invoice."
        ),
        timing=dict(
            launch_record_utc=launch["at"],
            first_dispatch_utc=utc(first),
            last_settlement_utc=utc(last),
            completion_status_utc=status["at"],
            first_dispatch_to_last_settlement_seconds=last - first,
            launch_record_to_first_dispatch_seconds=first - epoch(launch["at"]),
            last_settlement_to_completion_status_seconds=end - last,
            launch_record_to_completion_status_seconds=end - epoch(launch["at"]),
            seal_has_embedded_timestamp=False,
            seal_time_semantics=(
                "Seal persisted before REREVIEW_COMPLETE status; no exact independent seal "
                "timestamp is stored. Completion-status time is an upper bound, not last "
                "model settlement."
            ),
        ),
        final_progress_counter=dict(
            reported_successful_transport_settlements=status["successful_transport_settlements"],
            actual_settled_requests=len(rows),
            cached_counter_gap=final_tail,
            explanation=(
                "successful_transport_settlements is assigned before each wave gather; "
                "success is incremented afterward but that cached status field is not "
                "overwritten. Exact roster, authentic terminals and actual_returns "
                "include the final wave."
            ),
            last_dispatch_order_tail=aggregate(ordered_dispatch[-final_tail:], rates)
            if final_tail
            else None,
            tail_selection=(
                "Last N by actual dispatch time, N=actual_calls-cached_counter; no per-wave "
                "ID stored, so this is a mechanical dispatch-order tail, not a separately "
                "logged wave identity."
            ),
        ),
        closing_budget=dict(
            global_effective_cap_microcny=final["effective_hard_cap_microcny"],
            global_settled_microcny=final["settled_tariff_microcny"],
            global_held_microcny=final["held_microcny"],
            global_remaining_microcny=final["remaining_exposure_microcny"],
            global_original_unknowns_retained=final["unknown_requests"],
            new_unknowns=0,
            review_mapping_effective_cap_microcny=1_300_000_000,
            review_mapping_settled_microcny=sub["spent"],
            review_mapping_held_microcny=sub["held"],
            review_mapping_remaining_microcny=1_300_000_000 - sub["spent"] - sub["held"],
            global_request_cap=final["request_cap"],
            global_requests_reserved=final["requests_reserved"],
            review_mapping_effective_request_cap=25000,
            review_mapping_requests_consumed=sub["requests"],
            review_mapping_requests_remaining=25000 - sub["requests"],
            unused_requests_authorize_new_scope=False,
            mapping_authorized=False,
            training_started=status["training_started"],
        ),
        checks=dict(
            exact_roster_complete=True,
            every_usage_conserves=True,
            every_tariff_reconciles=True,
            deployment_to_final_cost_delta_reconciles=True,
            original_holds_preserved=True,
            new_unknown_zero=True,
            pending_zero=True,
        ),
    )
    result["id"] = digest(result)
    destination.mkdir(parents=True, exist_ok=False)
    path = destination / "record.json"
    with path.open("xb") as stream:
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
    destination = (args.destination or output / "report_audit_01/runtime_analysis").resolve()
    require(not destination.exists(), "audit output must be a fresh directory; never overwrite")
    result = run(output, destination)
    print(
        json.dumps(
            dict(
                id=result["id"],
                path=str(destination / "record.json"),
                calls=result["total"]["calls"],
                settled_cny=result["total"]["settled_cny"],
                timing=result["timing"],
            ),
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
