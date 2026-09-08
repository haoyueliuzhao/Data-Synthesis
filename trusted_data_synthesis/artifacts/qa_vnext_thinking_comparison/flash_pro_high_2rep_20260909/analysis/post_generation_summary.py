"""Zero-Provider, post-unmasking summaries/checks; never revises frozen scores or reviews.

Emits a new artifact via apply_patch. The frozen evaluator remains unchanged.
Reads a credential only to assert its bytes are absent; never prints or hashes it.
"""

import datetime as dt
import hashlib
import json
import statistics
import subprocess
from collections import Counter
from decimal import Decimal
from pathlib import Path

from trusted_synthesis.experiments.finance_qa_vnext_autonomous_formula.online.common import SYSTEM as OLD_SYSTEM
from trusted_synthesis.experiments.finance_qa_vnext_harness_responsibility.audit import manifest
from trusted_synthesis.experiments.finance_qa_vnext_model_execution.plan import verify_source_snapshot
from trusted_synthesis.experiments.finance_qa_vnext_model_execution.runner import _credential
from trusted_synthesis.experiments.finance_qa_vnext_thinking_comparison.evaluate import REVIEW_FIELDS
from trusted_synthesis.experiments.finance_qa_vnext_thinking_comparison.online.common import SYSTEM
from trusted_synthesis.experiments.finance_qa_vnext_thinking_comparison.plan import PACKAGE, TEST, history_guard

OUT = Path(__file__).resolve().parents[1]
REPO = OUT.parents[3]


def read(relative):
    return json.loads((OUT / relative).read_text())


def main():
    lock = read("review/review_lock.json")
    for name, member in lock["files"].items():
        data = (OUT / "review" / name).read_bytes()
        assert len(data) == member["bytes"] and hashlib.sha256(data).hexdigest() == member["sha256"]
    assert (OUT / "closeout/posthoc_reviews.json").read_bytes() == (OUT / "review/masked_reviews.json").read_bytes()
    manifests = {name: manifest(OUT / name)["id"] for name in ("preparation", "online", "assessment", "closeout")}
    implementation = read("preparation/implementation.json")
    verify_source_snapshot(REPO, implementation)
    historical = history_guard(REPO)
    assert SYSTEM == OLD_SYSTEM
    old_package = PACKAGE.replace("thinking_comparison", "autonomous_formula")
    for name in ("calculator.py", "isolate.py"):
        assert (REPO / PACKAGE / "online" / name).read_bytes() == (REPO / old_package / "online" / name).read_bytes()
    frozen_test = subprocess.check_output(["git", "show", implementation["source_commit"] + ":" + TEST], cwd=REPO)
    assert frozen_test == (REPO / TEST).read_bytes()
    assert not list(OUT.rglob("*_http_response.body"))
    credential = _credential(REPO / "trusted_data_synthesis/.env").encode()
    files_checked = [p for p in OUT.rglob("*") if p.is_file()]
    assert not any(credential in p.read_bytes() for p in files_checked), "credential_presence_detected"
    del credential

    report = read("closeout/report.json")
    audits = read("assessment/report.json")["rows"]
    attempts, isolations = [], []
    for directory in sorted((OUT / "online/sessions").iterdir()):
        isolation = json.loads((directory / "isolation.json").read_text())
        assert isolation["private_read_denied_before_provider"] is True
        assert len(isolation["private_read_probes"]) == 2
        assert all(p["read_denied"] for p in isolation["private_read_probes"])
        assert isolation["core_dumps_disabled"] is True
        assert isolation["repository_modules_loaded"] == []
        assert isolation["isolated_mode"] == isolation["no_site"] == 1
        isolations.append(isolation)
        for path in sorted(directory.glob("turns/*_outcome.json")):
            prefix = path.name[:3]
            outcome = json.loads(path.read_text())
            projection = json.loads((directory / f"turns/{prefix}_response_projection.json").read_text())
            reservation = json.loads((directory / f"turns/{prefix}_reservation.json").read_text())
            assert outcome["origin"] == "live_http"
            assert projection["is_original_http_response"] is False
            assert set(projection) == {"projection_version", "is_original_http_response", "transport_body_bytes", "parse_error", "id", "model", "object", "created", "system_fingerprint", "choices", "usage", "reasoning_telemetry"}
            assert set(projection["choices"][0]["message"]) == {"role", "content", "native_tool_calls_present"}
            content = projection["choices"][0]["message"]["content"]
            assert content.encode() == (directory / f"turns/{prefix}_assistant.raw").read_bytes()
            usage = outcome["usage"]
            assert usage["prompt_cache_hit_tokens"] + usage["prompt_cache_miss_tokens"] == usage["prompt_tokens"]
            assert usage["prompt_tokens"] + usage["completion_tokens"] == usage["total_tokens"]
            assert 0 <= usage["completion_tokens_details"]["reasoning_tokens"] <= usage["completion_tokens"] <= 16384
            start = dt.datetime.fromisoformat(reservation["started_utc"])
            end = start + dt.timedelta(microseconds=outcome["elapsed_ns"] / 1000)
            attempts.append({"arm": directory.name[0], "label": directory.name, "index": outcome["index"], "start": start, "end": end, "outcome": outcome, "fingerprint": projection["system_fingerprint"], "content_nonempty": bool(content)})
    assert len(attempts) == 44 and len(isolations) == 24
    by_model = {}
    for arm in ("F", "P"):
        rows = [r for r in report["rows"] if r["arm"] == arm]
        costs = [r for r in report["costs"]["rows"] if r["arm"] == arm]
        selected = [a for a in attempts if a["arm"] == arm]
        calculations = [c for a in audits if a["label"].startswith(arm + "_") for c in a["calculations"]]
        durations = [a["outcome"]["elapsed_ns"] / 1e9 for a in selected]
        price = {period: sum(Decimal(c["published_rate_estimate_cny"][period]) for c in costs) for period in ("offpeak", "peak")}
        passed = sum(r["answer"]["task_answer_status"] == "PASS" for r in rows)
        traces = sum(r["formula_driven_trace_verified"] for r in rows)
        by_model[arm] = {
            **report["by_model"][arm],
            "by_task_formula_driven_verified": {k: sum(r["task_key"] == k and r["formula_driven_trace_verified"] for r in rows) for k in report["task_weights"]},
            "usage": {key: sum(c["provider_usage"][key]["complete_sum"] for c in costs) for key in costs[0]["provider_usage"]},
            "additive_cost_metrics": {key: sum(c[key] for c in costs) for key in ("reserved_attempts", "recorded_outcomes", "http_request_bytes", "http_response_bytes", "raw_assistant_bytes", "response_projection_bytes", "successful_calculations", "successful_expression_operations", "summed_request_elapsed_ns", "tool_errors", "reasoning_nonempty_responses", "reasoning_characters_observed")},
            "request_latency_seconds": {"mean": statistics.mean(durations), "median": statistics.median(durations), "minimum": min(durations), "maximum": max(durations), "sum": sum(durations)},
            "maximum_single_completion_tokens": max(a["outcome"]["usage"]["completion_tokens"] for a in selected),
            "finish_reason_counts": dict(Counter(a["outcome"]["finish_reason"] for a in selected)),
            "actual_response_model_counts": dict(Counter(a["outcome"]["model"] for a in selected)),
            "response_fingerprint_counts": dict(Counter(a["fingerprint"] for a in selected)),
            "nonempty_public_contents": sum(a["content_nonempty"] for a in selected),
            "source_symbolic_target_match_count": sum(c["source_symbolic_target_match"] for c in calculations),
            "independent_calculation_pass_count": sum(c["independent_execution_verified"] for c in calculations),
            "actual_cross_calculation_reuse_count": sum(bool(c["used_result_ids"]) for c in calculations),
            "semantic_review_counts": {field: dict(Counter(r["semantic_review"][field]["status"] for r in rows)) for field in (*REVIEW_FIELDS, "final_answer_consistency")},
            "price_estimate_cny": {period: str(value) for period, value in price.items()},
            "offpeak_cny_per_registered_session": str(price["offpeak"] / len(rows)),
            "offpeak_cny_per_passing_answer": str(price["offpeak"] / passed),
            "offpeak_cny_per_verified_trace": str(price["offpeak"] / traces),
            "unit_costs_include_all_failed_unknown_and_nontrace_sessions": True,
            "actual_billed_cost": None,
        }
    waves = {}
    for repetition in (1, 2):
        selected = [a for a in attempts if a["label"].endswith(f"_{repetition:02d}")]
        start, end = min(a["start"] for a in selected), max(a["end"] for a in selected)
        waves[str(repetition)] = {"first_request_start_utc": start.isoformat(), "last_request_end_utc_derived": end.isoformat(), "request_window_seconds": (end-start).total_seconds()}
    assert waves["1"]["last_request_end_utc_derived"] < waves["2"]["first_request_start_utc"]
    result = {
        "kind": "post_generation_descriptive_summary_not_new_evaluation",
        "closeout_report_id": report["id"],
        "frozen_source_commit": implementation["source_commit"],
        "review_input_sha256": lock["files"]["masked_reviews.json"]["sha256"],
        "provider_calls": 0,
        "by_model": by_model,
        "request_waves": waves,
        "overall_request_window_seconds": (max(a["end"] for a in attempts)-min(a["start"] for a in attempts)).total_seconds(),
        "request_window_excludes_preparation_scoring_and_commit_time": True,
        "request_end_times_derived_from_utc_start_plus_monotonic_duration": True,
        "historical_side_table": {k: v for k, v in read("preparation/historical_evaluation_side_table.json").items() if k != "rows"},
        "verification": {
            "manifest_ids": manifests,
            "all_frozen_source_bytes_and_test_unchanged": True,
            "old_system_calculator_isolate_byte_identical": True,
            "historical": historical,
            "review_input_and_authoring_hashes_unchanged": True,
            "closeout_review_copy_byte_identical": True,
            "all_24_isolation_records_and_48_read_denials_checked": True,
            "raw_http_response_body_file_count": 0,
            "all_44_projection_allowlists_and_exact_public_bytes_checked": True,
            "all_44_usage_arithmetic_and_completion_limits_checked": True,
            "credential_bytes_absent_from_scanned_artifacts": True,
            "artifact_files_scanned_before_summary_creation": len(files_checked),
        },
        "interpretation": {
            "six_known_tasks_two_repeats_not_statistical_noninferiority": True,
            "no_thinking_on_off_effect_estimated": True,
            "flash_remains_primary_research_candidate": True,
            "unfiltered_flash_high_default_readiness_not_established": True,
            "pro_not_automatically_promoted_to_default": True,
            "no_new_sampling_or_pro_answer_rescue": True,
        },
    }
    target = OUT / "analysis/summary.json"
    assert not target.exists(), "Do not overwrite post-unmasking evidence"
    print("*** Begin Patch\n*** Add File: " + str(target))
    for line in json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True).splitlines():
        print("+" + line)
    print("*** End Patch")


if __name__ == "__main__":
    main()
