#!/usr/bin/env python3
"""Read-only completed V15 mapping accounting; never read Student artifacts."""

import argparse
import hashlib
import json
import os
import sqlite3
import time
from datetime import datetime, timezone
from decimal import ROUND_CEILING, Decimal
from pathlib import Path

from finqa_v12_runtime_audit import (
    TOKENS,
    digest,
    encoded,
    epoch,
    file_binding,
    read_record,
    require,
)
from finqa_v13_runtime_audit import PROJECT, _request_record_digest, summarize

DEFAULT = (
    PROJECT
    / "trusted_data_synthesis/artifacts/finance_research_20260928/finqa_v6_01"
    / "v15_prefix_completion_01"
)
SQL = """
SELECT v.episode_id AS roster_episode_id,v.job_json,a.category,r.*,
 (SELECT COUNT(*) FROM events e
  WHERE e.invocation_id=r.invocation_id AND e.action='dispatched') AS dispatch_events
FROM v15_review_roster v
LEFT JOIN v10_request_allocations a ON a.episode_id=v.episode_id
LEFT JOIN requests r ON r.invocation_id=a.invocation_id
ORDER BY v.episode_id,r.invocation_id
"""


def run(output, destination):
    paths = dict(
        plan=output / "registration/record.json",
        deployment=output / "deployment_budget/record.json",
        permit=output / "wallet_registration/record.json",
        launch=output / "workflow_launch/record.json",
        status=output / "status.json",
        seal=output / "completion_seal/record.json",
    )
    records, refs = {}, {}
    for name, path in paths.items():
        records[name], refs[name] = read_record(path, bound=name != "status")
    plan, status, seal, permit = (records[k] for k in ("plan", "status", "seal", "permit"))
    require(
        plan["expected_requests"] == len(plan["jobs"]) == 36
        and plan["purpose_counts"] == {"mapping": 36}
        and seal["registration_id"] == plan["id"] == permit["plan_id"]
        and status["phase"] == "MATERIAL_ANNOTATIONS_COMPLETE"
        and status["seal_id"] == seal["id"]
        and seal["actual_returns"] == 36
        and seal["network_unknowns"] == 0,
        "only audit this sealed, all-returned 36-job mapping matrix",
    )
    before, after = records["deployment"]["before"], records["deployment"]["after"]
    before_review = before["v10_partition"]["consumed"]["review_mapping"]
    require(
        before == after
        and before["settled_tariff_microcny"] == 1265076387
        and before["held_microcny"] == 332464128
        and before["unknown_requests"] == 152
        and before_review["spent"] == 905139184
        and before_review["held"] == 187629568,
        "deployment baseline differs from finalized V14 accounting",
    )
    jobs = {j["episode_id"]: j for j in plan["jobs"]}
    source = PROJECT / "trusted_data_synthesis/src/trusted_synthesis/finance_research"
    source_refs = {
        name: file_binding(source / name)
        for name in (
            "probe_budget.py",
            "v15_budget.py",
            "v15_mapping_provider.py",
            "v15_mapping_controller.py",
        )
    }
    require(
        all(ref["sha256"] == plan["source_bindings"][name] for name, ref in source_refs.items()),
        "frozen provider/controller/tariff source differs",
    )
    wallet = Path(plan["budget_database"]).resolve()
    began, clock = datetime.now(timezone.utc).isoformat(), time.perf_counter()
    rows, row_stream = [], hashlib.sha256()
    with sqlite3.connect(wallet.as_uri() + "?mode=ro", uri=True, isolation_level=None) as db:
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA query_only=ON")
        db.execute("BEGIN")
        config = json.loads(
            db.execute("SELECT value FROM metadata WHERE key='config'").fetchone()[0]
        )
        require(digest(config) == plan["budget_config_sha256"], "original wallet config changed")
        recorded = json.loads(
            db.execute(
                "SELECT value FROM metadata WHERE key='v15_fixed_residual_material_matrix_01'"
            ).fetchone()[0]
        )
        require(recorded == permit, "wallet permit differs from deployment receipt")
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
            require(job == jobs.get(selected["roster_episode_id"]), "exact new roster differs")
            coords, body = json.loads(raw["coordinates_json"]), json.loads(raw["request_body"])
            row_sha = _request_record_digest(raw)
            row_stream.update(
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
                and job["kind"] == job["purpose"] == "mapping"
                and body["model"] == "deepseek-flash"
                and body["max_tokens"] == job["max_output_tokens"]
                and raw["request_sha256"] == job["request_sha256"] == digest(body)
                and hashlib.sha256(raw["request_body"]).hexdigest() == job["request_body_sha256"],
                "request coordinates, model, capacity, or exact HTTP bytes differ",
            )
            require(
                raw["state"] == "SETTLED"
                and raw["response_classification"] == "model_response"
                and raw["http_status"] == 200,
                "sealed real return missing; never treat UNKNOWN as zero usage",
            )
            usage = json.loads(raw["usage_json"])
            require(
                all(type(usage.get(k)) is int and usage[k] >= 0 for k in TOKENS)
                and usage["prompt_tokens"]
                == usage["prompt_cache_hit_tokens"] + usage["prompt_cache_miss_tokens"]
                and usage["total_tokens"] == usage["prompt_tokens"] + usage["completion_tokens"]
                and usage["completion_tokens"] <= body["max_tokens"],
                "actual usage does not conserve",
            )
            fee = (
                rates[0] * usage["prompt_cache_hit_tokens"]
                + rates[1] * usage["prompt_cache_miss_tokens"]
                + rates[2] * usage["completion_tokens"]
            )
            require(
                int(fee.to_integral_value(rounding=ROUND_CEILING)) == raw["settled_microcny"],
                "per-request frozen tariff settlement differs",
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
                purpose="mapping",
                coordinates=coords,
                requested_model=body["model"],
                requested_max_tokens=body["max_tokens"],
                original_row_sha256=row_sha,
                dispatch_events=selected["dispatch_events"],
                usage=usage,
                terminal_at=raw["settled_at"],
            )
            rows.append(row)
        counters = dict(db.execute("SELECT * FROM counters WHERE singleton=1").fetchone())
        review = dict(
            db.execute("SELECT * FROM v10_quotas WHERE category='review_mapping'").fetchone()
        )
        halt = db.execute("SELECT value FROM metadata WHERE key='halt'").fetchone()
        db.rollback()
    ended, seconds = datetime.now(timezone.utc).isoformat(), time.perf_counter() - clock
    require(
        len(rows)
        == len({r["episode_id"] for r in rows})
        == len({r["invocation_id"] for r in rows})
        == 36,
        "incomplete or duplicate matrix",
    )
    total, final = summarize(rows, rates), status["budget"]
    final_review = final["v10_partition"]["consumed"]["review_mapping"]
    require(
        final["requests_reserved"] - before["requests_reserved"] == 36
        and final_review["requests"] - before_review["requests"] == 36
        and final["settled_tariff_microcny"] - before["settled_tariff_microcny"]
        == final_review["spent"] - before_review["spent"]
        == total["known_settled_microcny"]
        and final["held_microcny"] == before["held_microcny"] == counters["held"]
        and final["unknown_requests"] == before["unknown_requests"] == counters["unknown"] == 152
        and final_review["held"] == before_review["held"] == review["held"]
        and final_review["unknown"] == before_review["unknown"] == review["unknown"]
        and counters["requests"] == final["requests_reserved"]
        and counters["spent"] == final["settled_tariff_microcny"]
        and review["spent"] == final_review["spent"]
        and review["requests"] == final_review["requests"]
        and counters["pending"] == review["pending"] == 0
        and halt is None,
        "baseline/final/readonly counters do not reconcile",
    )
    limits = final["v10_partition"]["effective_limits"]["review_mapping"]
    require(
        final["effective_hard_cap_microcny"] == 2000000000
        and final["request_cap"] == 258000
        and limits == {"microcny": 1300000000, "requests": 25000},
        "effective caps changed",
    )
    result = dict(
        schema="v15_completed_mapping_runtime_audit.v1",
        at=datetime.now(timezone.utc).isoformat(),
        source_records=refs,
        source_bindings=source_refs,
        audit_script=file_binding(Path(__file__).resolve()),
        helper_sources={
            name: file_binding(Path(__file__).parent / name)
            for name in ("finqa_v12_runtime_audit.py", "finqa_v13_runtime_audit.py")
        },
        wallet=dict(
            path=str(wallet),
            mode="ro",
            query_only=True,
            config_sha256=digest(config),
            schema_sha256=digest(schema),
            row_stream_sha256=row_stream.hexdigest(),
            query=SQL.strip(),
            new_exact_rows=36,
            historical_rows_individually_rehashed=False,
        ),
        read_started_utc=began,
        read_finished_utc=ended,
        read_seconds=seconds,
        total=total,
        original_UNKNOWN_preservation=dict(
            verification=(
                "Before/final/read-only counter and held-amount conservation; "
                "not individual historical-row rehash"
            ),
            global_count_before=152,
            global_count_after=counters["unknown"],
            global_held_before_microcny=before["held_microcny"],
            global_held_after_microcny=counters["held"],
            review_count_before=before_review["unknown"],
            review_count_after=review["unknown"],
            review_held_before_microcny=before_review["held"],
            review_held_after_microcny=review["held"],
            new_unknowns=0,
        ),
        price_sheet=config["price_sheet"],
        cost_semantics=(
            "Frozen peak tariff, ceil per request in micro-CNY applied to actual usage; "
            "not a supplier invoice. Old UNKNOWN holds remain exposure."
        ),
        timing=dict(
            launch_record_utc=records["launch"]["at"],
            first_dispatch_utc=total["first_dispatch_utc"],
            last_terminal_utc=total["last_request_terminal_utc"],
            completion_status_utc=status["at"],
            launch_to_completion_status_seconds=epoch(status["at"])
            - epoch(records["launch"]["at"]),
            last_terminal_to_completion_status_seconds=epoch(status["at"])
            - epoch(total["last_request_terminal_utc"]),
            independently_timestamped_seal=False,
        ),
        closing_budget=dict(
            global_cap_microcny=2000000000,
            global_spent_microcny=counters["spent"],
            global_held_microcny=counters["held"],
            global_remaining_microcny=2000000000 - counters["spent"] - counters["held"],
            review_cap_microcny=1300000000,
            review_spent_microcny=review["spent"],
            review_held_microcny=review["held"],
            review_remaining_microcny=1300000000 - review["spent"] - review["held"],
            global_request_cap=258000,
            global_requests=counters["requests"],
            review_request_cap=25000,
            review_requests=review["requests"],
            review_requests_remaining=25000 - review["requests"],
            unknown_count=152,
            pending=0,
            halt=None,
            remaining_is_not_new_scope_authorization=True,
        ),
        no_resend_observed=True,
        original_provider_or_controller_changed=False,
        student_loss_grad_or_checkpoint_read=False,
        wallet_written=False,
        model_calls_by_audit=0,
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
    destination = (args.destination or output / "report_run_01/mapping_runtime").resolve()
    require(not destination.exists(), "new report directory required; never overwrite")
    result = run(output, destination)
    print(
        json.dumps(
            dict(
                id=result["id"],
                output=str(destination),
                settled_cny=result["total"]["known_settled_cny"],
                returns=result["total"]["actual_returns"],
                unknowns=result["total"]["network_unknowns"],
            )
        )
    )


if __name__ == "__main__":
    main()
