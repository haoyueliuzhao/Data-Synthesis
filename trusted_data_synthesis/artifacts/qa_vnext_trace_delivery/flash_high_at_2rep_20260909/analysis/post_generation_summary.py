"""Post-unmasking, zero-Provider arithmetic/manifest summaries; no rescoring or overwrites."""

import datetime as dt
import hashlib
import json
import statistics
import subprocess
from collections import Counter
from decimal import Decimal
from pathlib import Path

from trusted_synthesis.experiments.finance_qa_vnext_harness_responsibility.audit import manifest
from trusted_synthesis.experiments.finance_qa_vnext_model_execution.plan import verify_source_snapshot
from trusted_synthesis.experiments.finance_qa_vnext_model_execution.runner import _credential
from trusted_synthesis.experiments.finance_qa_vnext_trace_delivery.evaluate import REVIEW_FIELDS
from trusted_synthesis.experiments.finance_qa_vnext_trace_delivery.instructions import capsule_files
from trusted_synthesis.experiments.finance_qa_vnext_trace_delivery.plan import TEST, history_guard

OUT = Path(__file__).resolve().parents[1]
REPO = OUT.parents[3]


def read(relative):
    return json.loads((OUT / relative).read_text())


def main():
    lock = read("review/review_lock.json")
    for name, item in lock["files"].items():
        data = (OUT / "review" / name).read_bytes()
        assert len(data) == item["bytes"] and hashlib.sha256(data).hexdigest() == item["sha256"]
    assert (OUT / "review/masked_reviews.json").read_bytes() == (OUT / "closeout/posthoc_reviews.json").read_bytes()
    manifests = {name: manifest(OUT / name)["id"] for name in ("preparation", "online", "assessment", "closeout")}
    implementation = read("preparation/implementation.json")
    verify_source_snapshot(REPO, implementation)
    history = history_guard(REPO)
    assert (REPO / TEST).read_bytes() == subprocess.check_output(["git", "show", implementation["source_commit"] + ":" + TEST], cwd=REPO)
    for arm in ("A", "T"):
        for name, data in capsule_files(REPO, arm).items():
            assert data == (OUT / f"preparation/worker_code/{arm}/{name}").read_bytes()
    assert not list(OUT.rglob("*_http_response.body"))
    scanned = [p for p in OUT.rglob("*") if p.is_file()]
    credential = _credential(REPO / "trusted_data_synthesis/.env").encode()
    assert not any(credential in p.read_bytes() for p in scanned), "credential_presence_detected"
    del credential

    report = read("closeout/report.json")
    audits = read("assessment/report.json")["rows"]
    attempts, sessions = [], {}
    for directory in sorted((OUT / "online/sessions").iterdir()):
        manifest(directory)
        isolation = json.loads((directory / "isolation.json").read_text())
        assert isolation["private_read_denied_before_provider"] is True
        assert isolation["repository_modules_loaded"] == [] and isolation["core_dumps_disabled"]
        assert isolation["isolated_mode"] == isolation["no_site"] == 1
        assert len(isolation["private_read_probes"]) == 2 and all(p["read_denied"] for p in isolation["private_read_probes"])
        result = json.loads((directory / "result.json").read_text())
        assert result["origin"] == "live_http" and result["requested_model"] == "deepseek-v4-flash"
        assert not result["history_truncated"] and not result["online_answer_feedback"]
        sessions[directory.name] = result
        for file in sorted(directory.glob("turns/*_outcome.json")):
            prefix = file.name[:3]
            outcome = json.loads(file.read_text())
            projection = json.loads((directory / f"turns/{prefix}_response_projection.json").read_text())
            reservation = json.loads((directory / f"turns/{prefix}_reservation.json").read_text())
            assert projection["is_original_http_response"] is False
            assert set(projection) == {"projection_version", "is_original_http_response", "transport_body_bytes", "parse_error", "id", "model", "object", "created", "system_fingerprint", "choices", "usage", "reasoning_telemetry"}
            message = projection["choices"][0]["message"]
            assert set(message) == {"role", "content", "native_tool_calls_present"}
            assert message["content"].encode() == (directory / f"turns/{prefix}_assistant.raw").read_bytes()
            usage = outcome["usage"]
            assert usage["prompt_cache_hit_tokens"] + usage["prompt_cache_miss_tokens"] == usage["prompt_tokens"]
            assert usage["prompt_tokens"] + usage["completion_tokens"] == usage["total_tokens"]
            assert 0 <= usage["completion_tokens_details"]["reasoning_tokens"] <= usage["completion_tokens"] <= 16384
            assert outcome["origin"] == "live_http" and outcome["http_status"] == 200
            assert outcome["finish_reason"] == "stop" and not outcome["error"]
            start = dt.datetime.fromisoformat(reservation["started_utc"])
            end = start + dt.timedelta(microseconds=outcome["elapsed_ns"] / 1000)
            attempts.append({"arm": directory.name[0], "label": directory.name, "start": start, "end": end, "outcome": outcome, "fingerprint": projection["system_fingerprint"], "public_nonempty": bool(message["content"])})
    assert len(attempts) == 44 and len(sessions) == 24
    condition_metrics = {}
    all_interfaces = []
    for arm in ("A", "T"):
        rows = [r for r in report["rows"] if r["arm"] == arm]
        arm_audits = [a for a in audits if a["label"].startswith(arm + "_")]
        expenses = [c for c in report["costs"]["rows"] if c["arm"] == arm]
        selected = [a for a in attempts if a["arm"] == arm]
        calculations = [c for a in arm_audits for c in a["calculations"]]
        events = [(label, e) for label, result in sessions.items() if label.startswith(arm + "_") for e in result["events"]]
        interfaces = [{"label": label, "response_index": e["response_index"], "error": e["protocol_error"]} for label, e in events if e["protocol_error"]]
        assert all(e["tool_call"] is None for _, e in events if e["protocol_error"])
        all_interfaces += interfaces
        durations = [a["outcome"]["elapsed_ns"] / 1e9 for a in selected]
        condition_metrics[arm] = {
            **report["by_condition"][arm],
            "first_response_final_count": sum(a["first_final_index"] == 0 for a in arm_audits),
            "final_without_actual_calculation_count": sum(not a["calculations"] for a in arm_audits),
            "warning_direct_final_field_in_frozen_report_includes_later_Final_without_calculation": True,
            "interface_error_count": len(interfaces),
            "message_only_nonfinal_count": sum(not e["final"] and not e["protocol_error"] and e["tool_call"] is None for _, e in events),
            "interface_errors": interfaces,
            "independently_verified_calculations": sum(c["independent_execution_verified"] for c in calculations),
            "source_symbolic_target_matches": sum(c["source_symbolic_target_match"] for c in calculations),
            "named_variable_calculations": sum(bool(c["variable_bindings"]) for c in calculations),
            "actual_cross_calculation_reuse": sum(bool(c["used_result_ids"]) for c in calculations),
            "maximum_single_completion_tokens": max(a["outcome"]["usage"]["completion_tokens"] for a in selected),
            "public_nonempty_responses": sum(a["public_nonempty"] for a in selected),
            "actual_model_counts": dict(Counter(a["outcome"]["model"] for a in selected)),
            "fingerprint_counts": dict(Counter(a["fingerprint"] for a in selected)),
            "finish_reason_counts": dict(Counter(a["outcome"]["finish_reason"] for a in selected)),
            "request_latency_seconds": {"mean": statistics.mean(durations), "median": statistics.median(durations), "minimum": min(durations), "maximum": max(durations), "sum": sum(durations)},
            "additive_metrics": {key: sum(c[key] for c in expenses) for key in ("http_request_bytes", "http_response_bytes", "raw_assistant_bytes", "response_projection_bytes", "reasoning_nonempty_responses", "reasoning_characters_observed", "reasoning_length_unknown_responses", "successful_expression_operations", "tool_errors")},
            "semantic_review_counts": {field: dict(Counter(r["semantic_review"][field]["status"] for r in rows)) for field in (*REVIEW_FIELDS, "final_answer_consistency")},
        }
    assert len(all_interfaces) == 3
    waves = {}
    for rep in (1, 2):
        selected = [a for a in attempts if a["label"].endswith(f"_{rep:02d}")]
        start, end = min(a["start"] for a in selected), max(a["end"] for a in selected)
        waves[str(rep)] = {"first_request_start_utc": start.isoformat(), "last_request_end_utc_derived": end.isoformat(), "request_window_seconds": (end-start).total_seconds()}
    assert waves["1"]["last_request_end_utc_derived"] < waves["2"]["first_request_start_utc"]
    a_cost = Decimal(report["by_condition"]["A"]["costs"]["published_rate_estimate_cny"]["offpeak"])
    t_cost = Decimal(report["by_condition"]["T"]["costs"]["published_rate_estimate_cny"]["offpeak"])
    result = {
        "kind": "post_unmasking_descriptive_summary_not_new_evaluation",
        "provider_calls": 0,
        "frozen_source_commit": implementation["source_commit"],
        "closeout_report_id": report["id"],
        "review_input_sha256": lock["files"]["masked_reviews.json"]["sha256"],
        "by_condition": condition_metrics,
        "request_waves": waves,
        "overall_request_window_seconds": (max(a["end"] for a in attempts)-min(a["start"] for a in attempts)).total_seconds(),
        "request_end_times_derived_from_utc_start_plus_monotonic_duration": True,
        "request_window_excludes_preparation_review_and_commit_time": True,
        "request_accounting": {"actual_calculate_requests": 16, "JSON_interface_errors_before_tool_execution": 3, "public_nonfinal_without_tool": 1, "model_Final": 24, "total": 44},
        "cost_comparison": {"offpeak_total_cny": str(a_cost+t_cost), "T_to_A_total_cost_ratio": str(t_cost/a_cost), "T_unit_trace_cost_reduction_percent": str((1-(t_cost/10)/(a_cost/2))*100), "all_registered_expenses_included": True, "actual_billed_cost": None},
        "verification": {"stage_manifest_ids": manifests, "frozen_source_members_checked": len(implementation["members"]), "all_source_test_and_capsule_bytes_unchanged": True, "history_guard": history, "review_lock_and_closeout_copy_unchanged": True, "all_24_isolations_and_48_denied_reads_checked": True, "all_44_projection_allowlists_public_bytes_and_usage_checked": True, "raw_HTTP_response_body_file_count": 0, "credential_bytes_absent_from_scanned_artifacts": True, "scanned_artifact_files_before_this_summary": len(scanned)},
        "next_condition_decision": {"selected_candidate": "T", "model": "deepseek-v4-flash", "thinking": "enabled", "reasoning_effort": "high", "scope": "Subsequent public-trace synthesis research candidate; not a silent global adapter change or unfiltered production-readiness claim", "reason": "Within this fixed panel, verified yield is 10/12 versus 2/12, answer PASS is 10/12 versus 9/12, and all-cost unit-trace estimate is lower", "offline_validity_filter_required": True, "N3_registered_target_support_still_zero": True, "cannot_drop_N3_and_claim_original_six_task_effective_marginal": True, "no_intrinsic_reasoning_or_statistical_superiority_claim": True, "A_T_populations_not_pooled": True, "no_Student_quotient_Token_export_or_VTDO": True},
    }
    target = OUT / "analysis/summary.json"
    assert not target.exists(), "Never overwrite closed evidence"
    print("*** Begin Patch\n*** Add File: " + str(target))
    for line in json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2).splitlines():
        print("+" + line)
    print("*** End Patch")


if __name__ == "__main__":
    main()
