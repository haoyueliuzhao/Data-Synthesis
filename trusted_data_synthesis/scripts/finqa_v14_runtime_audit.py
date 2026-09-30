#!/usr/bin/env python3
"""One read-only exact V14 roster audit after completion; never resume or resend."""

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
    / "trusted_data_synthesis/artifacts/finance_research_20260928/finqa_v6_01/v14_representation_01"
)
SQL = """
SELECT v.episode_id AS roster_episode_id,v.job_json,a.category,r.*,
 (SELECT COUNT(*) FROM events e
  WHERE e.invocation_id=r.invocation_id AND e.action='dispatched') AS dispatch_events,
 (SELECT MAX(at_unix) FROM events e
  WHERE e.invocation_id=r.invocation_id AND e.action='unknown') AS unknown_at
FROM v14_review_roster v
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
        plan["expected_requests"] == len(plan["jobs"]) == 309
        and seal["registration_id"] == plan["id"] == permit["plan_id"]
        and status["phase"] == "MATERIAL_ANNOTATIONS_COMPLETE"
        and status["seal_id"] == seal["id"],
        "wait for the original complete 309-job seal/status; never dispatch from this script",
    )
    before, after = records["deployment"]["before"], records["deployment"]["after"]
    require(
        before == after
        and before["settled_tariff_microcny"] == 1236352110
        and before["held_microcny"] == 332464128
        and before["v10_partition"]["consumed"]["review_mapping"]["spent"] == 876414907
        and before["v10_partition"]["consumed"]["review_mapping"]["held"] == 187629568,
        "deployment before/after and finalized parent accounting differ",
    )
    jobs = {j["episode_id"]: j for j in plan["jobs"]}
    source = PROJECT / "trusted_data_synthesis/src/trusted_synthesis/finance_research"
    source_refs = {
        name: file_binding(source / name)
        for name in (
            "probe_budget.py",
            "v14_budget.py",
            "v14_material_provider.py",
            "v14_material_controller.py",
        )
    }
    require(
        all(ref["sha256"] == plan["source_bindings"][name] for name, ref in source_refs.items()),
        "executed immutable tariff/provider/controller source differs",
    )
    wallet = Path(plan["budget_database"]).resolve()
    began, clock = datetime.now(timezone.utc).isoformat(), time.perf_counter()
    rows, stream, old_proofs = [], hashlib.sha256(), []
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
                "SELECT value FROM metadata WHERE key='v14_fixed_residual_material_matrix_01'"
            ).fetchone()[0]
        )
        require(recorded == permit, "wallet permit and deployment artifact differ")
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
            require(job == jobs.get(selected["roster_episode_id"]), "new exact roster changed")
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
                "request/attempt/model/cap/HTTP bytes differ",
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
                authority_reason=job["authority_reason"],
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
                    "invalid actual usage",
                )
                fee = (
                    rates[0] * usage["prompt_cache_hit_tokens"]
                    + rates[1] * usage["prompt_cache_miss_tokens"]
                    + rates[2] * usage["completion_tokens"]
                )
                require(
                    int(fee.to_integral_value(rounding=ROUND_CEILING)) == row["settled_microcny"],
                    "tariff mismatch",
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
                    "missing response cannot become a model judgment",
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
                    "new UNKNOWN/hold acknowledgement differs",
                )
                row.update(
                    usage=None,
                    terminal_at=selected["unknown_at"],
                    exception_type=evidence.get("exception_type"),
                    acknowledgement_id=ack["id"],
                )
            rows.append(row)
        require(
            len(permit["original_network_unknowns"]) == 12, "exact original twelve sources required"
        )
        for task, witness in permit["original_network_unknowns"].items():
            original = db.execute(
                "SELECT * FROM requests WHERE invocation_id=?", (witness["invocation_id"],)
            ).fetchone()
            require(
                original is not None
                and original["state"] == "UNKNOWN"
                and original["usage_json"] is None
                and original["settled_microcny"] is None
                and original["reserved_microcny"] == witness["permanent_reserved_microcny"]
                and _request_record_digest(original) == witness["original_row_sha256"],
                "original V13 network UNKNOWN/hold was changed",
            )
            old_proofs.append(
                dict(task_id=task, **witness, still_UNKNOWN=True, hold_preserved=True)
            )
        counters = dict(db.execute("SELECT * FROM counters WHERE singleton=1").fetchone())
        quotas = {r["category"]: dict(r) for r in db.execute("SELECT * FROM v10_quotas")}
        halt = db.execute("SELECT value FROM metadata WHERE key='halt'").fetchone()
        db.rollback()
    ended, seconds = datetime.now(timezone.utc).isoformat(), time.perf_counter() - clock
    require(
        len(rows)
        == len({r["episode_id"] for r in rows})
        == len({r["invocation_id"] for r in rows})
        == 309,
        "new matrix incomplete or duplicate",
    )
    total = summarize(rows, rates)
    final = status["budget"]
    require(
        total["actual_returns"] == seal["actual_returns"]
        and total["network_unknowns"] == seal["network_unknowns"]
        and final["requests_reserved"] - before["requests_reserved"] == 309
        and final["settled_tariff_microcny"] - before["settled_tariff_microcny"]
        == total["known_settled_microcny"]
        and final["held_microcny"] - before["held_microcny"]
        == total["permanent_unknown_hold_microcny"],
        "deployment/final source accounting delta mismatch",
    )
    require(
        counters["requests"] == final["requests_reserved"]
        and counters["spent"] == final["settled_tariff_microcny"]
        and counters["held"] == final["held_microcny"]
        and counters["pending"] == 0
        and halt is None,
        "live read differs from sealed financial snapshot",
    )
    review = quotas["review_mapping"]
    result = dict(
        schema="v14_completed_runtime_audit.v1",
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
            row_stream_sha256=stream.hexdigest(),
            query=SQL.strip(),
            new_exact_rows=309,
            extra_parent_UNKNOWN_rows=12,
        ),
        read_started_utc=began,
        read_finished_utc=ended,
        read_seconds=seconds,
        total=total,
        by_purpose={
            p: summarize([r for r in rows if r["purpose"] == p], rates)
            for p in ("projection", "mapping")
        },
        by_authority_reason={
            reason: summarize([r for r in rows if r["authority_reason"] == reason], rates)
            for reason in sorted({r["authority_reason"] for r in rows})
        },
        original_twelve_UNKNOWN_proofs=old_proofs,
        original_twelve_hold_microcny=sum(r["permanent_reserved_microcny"] for r in old_proofs),
        price_sheet=config["price_sheet"],
        cost_semantics=(
            "Frozen peak tariff, ceil per request in micro-CNY. "
            "Original UNKNOWN holds remain exposure, not a proved vendor bill."
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
            global_cap_microcny=final["effective_hard_cap_microcny"],
            global_spent_microcny=counters["spent"],
            global_held_microcny=counters["held"],
            global_remaining_microcny=final["remaining_exposure_microcny"],
            review_cap_microcny=1300000000,
            review_spent_microcny=review["spent"],
            review_held_microcny=review["held"],
            review_remaining_microcny=1300000000 - review["spent"] - review["held"],
            global_request_cap=final["request_cap"],
            global_requests=counters["requests"],
            review_request_cap=25000,
            review_requests=review["requests"],
            review_requests_remaining=25000 - review["requests"],
            unknown_count=counters["unknown"],
            pending=0,
            halt=None,
            remaining_is_not_new_scope_authorization=True,
        ),
        no_resend_observed=True,
        original_twelve_rows_byte_bound_and_unchanged=True,
        original_provider_or_controller_changed=False,
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
    destination = (args.destination or output / "report_run_01/runtime").resolve()
    require(not destination.exists(), "new audit directory required; never overwrite")
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
