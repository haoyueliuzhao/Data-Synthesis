"""Extract V72's sealed JSON summaries; never run training, generation or scoring.

Writes a new report JSON with source byte hashes. Raw episodes, tensors and step
receipts are deliberately outside this extractor's input set.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path


def extract(repo: Path) -> dict:
    root = repo / "trusted_data_synthesis/artifacts/finance_research_20260928/finqa_v6_01/v18_researcher_continuation_01/v72_low_lr_continuation_01"
    sources, cache = {}, {}

    def read(path_or_ref):
        ref = path_or_ref if isinstance(path_or_ref, dict) else None
        path = Path(ref["path"] if ref else path_or_ref).resolve()
        if path not in cache:
            raw = path.read_bytes()
            value = json.loads(raw)
            sources[str(path)] = {"path": str(path), "sha256": hashlib.sha256(raw).hexdigest(), "id": value.get("id")}
            cache[path] = value
        source = sources[str(path)]
        if ref:
            assert source["sha256"] == ref["sha256"], str(path)
            assert source["id"] == ref["id"], str(path)
        return cache[path]

    final = read(root / "evaluations/final_summary/record.json")
    closeout = read(root / "closeout/record.json")
    protocol = read(root / "protocol/record.json")
    assert final["status"] == closeout["status"] == "COMPLETE"
    assert final["optimizer_updates"] == 298 and final["task_exposures"] == 1488
    assert final["new_evaluation_sessions"] == 1886
    assert not any(final[k] for k in ("new_outer_updates", "feedback_sessions", "class_passes", "replay_responses", "VJP", "automatic_followup"))

    # Validate only the report arithmetic and orientation, not the old scorer.
    for panel in final["comparisons"].values():
        metrics, n = panel["native_metrics"], panel["denominator"]
        for m in metrics.values():
            assert sum(m["states"].values()) == n and m["states"]["UNKNOWN"] == 0
            assert m["states"]["R"] == m["execution_accuracy"]["correct"]
            for key in ("execution_accuracy", "program_accuracy"):
                assert m[key]["denominator"] == n and m[key]["unknown"] == 0
        for name, paired in panel["paired_execution"].items():
            candidate, reference = name.split("_minus_")
            t = paired["transitions"]
            assert sum(t.values()) == n and paired["unknown_pair_count"] == 0
            for state in ("I", "W", "R", "UNKNOWN"):
                assert sum(v for k, v in t.items() if k.split("->")[0] == state) == metrics[reference]["states"][state]
                assert sum(v for k, v in t.items() if k.split("->")[1] == state) == metrics[candidate]["states"][state]
            net = metrics[candidate]["execution_accuracy"]["correct"] - metrics[reference]["execution_accuracy"]["correct"]
            assert paired["new_correct"] - paired["lost_correct"] == paired["net_correct"] == net
            assert paired["decomposition"]["invalid_correct_net_count"] + paired["decomposition"]["wrong_correct_net_count"] == net
        for name, paired in panel["paired_program_accuracy"].items():
            candidate, reference = name.split("_minus_")
            assert sum(paired["transitions"].values()) == n
            net = metrics[candidate]["program_accuracy"]["correct"] - metrics[reference]["program_accuracy"]["correct"]
            assert paired["new_correct"] - paired["lost_correct"] == paired["numerator"] == net

    invalid = read(final["failure_mechanisms"])
    mechanisms = {k: v for k, v in invalid.items() if not k.endswith("_rows")}
    mechanisms["endpoint_invalid_overlap"] = {k: v for k, v in invalid["endpoint_invalid_overlap"].items() if k != "both_task_keys"}
    mechanisms["terminal_stop_counts"] = {}
    mechanisms["missing_submission_stop_counts"] = {}
    for condition in ("parent", "high_lr", "low_lr"):
        rows = invalid[f"{condition}_rows"]
        assert len(rows) == invalid[f"{condition}_summary"]["invalid_count"]
        # Only saved labels; no episode reopening or reclassification.
        mechanisms["terminal_stop_counts"][condition] = dict(Counter(row.get("stop_reason") for row in rows))
        mechanisms["missing_submission_stop_counts"][condition] = dict(Counter(row["stop_reason"] for row in rows if row["terminal_category"] == "missing_terminal_submission"))

    static = read(final["static_supervision_gate"])
    static = {k: v for k, v in static.items() if k not in ("packages", "sources")}
    existing = read(final["existing_analysis"])
    existing = {k: v for k, v in existing.items() if k != "sources"}
    existing["aligned_online_package_NLL"] = {k: v for k, v in existing["aligned_online_package_NLL"].items() if k != "packages"}
    existing["triple_development"] = {k: v for k, v in existing["triple_development"].items() if k != "rows"}
    dynamics = read(final["low_lr_training_dynamics"])
    dynamics = {k: v for k, v in dynamics.items() if k != "source_receipts"}
    dynamics["window"] = dict(dynamics["window"])
    steps = dynamics["window"].pop("steps")
    dynamics["saved_step_summary_count"] = len(steps)
    previous = read(repo / "trusted_data_synthesis/docs/report_data/finqa_v71_report_summary_20261025.json")
    high_dynamics = previous["mechanisms"]["saved_training_dynamics"]["Fixed894"]["1192"]
    training = read(root / "points/step1192/train/completed/record.json")
    training = {k: v for k, v in training.items() if k not in ("update_receipts", "resources")}
    intervention = read(root / "points/step1192/train/lr_intervention/record.json")
    assert training["outer_done"] == [298] and training["learning_rate"] == 1e-5
    assert intervention["optimizer_updates"] == 0

    resource_fields = ("all_gates_passed", "peak_allocated_bytes", "peak_rss_bytes", "minimum_boundary_free_bytes", "minimum_host_available_bytes", "actual_boundary_observations", "resource_wait_seconds", "received_signals", "observed_violation", "single_process_lifetime_includes_loading", "peak_resets_after_loading")
    jobs = {}
    for job in closeout["actual_attempts"]:
        job_id = job["job_id"]
        accepted_path = root / ("points/step1192/train" if job_id == "step1192.train" else f"evaluations/jobs/{job_id}") / "accepted/record.json"
        accepted = read(accepted_path)
        result, actual_exit = read(accepted["result"]), read(accepted["actual_exit"])
        assert actual_exit["returncode"] == 0 and actual_exit["actual_waitpid_observed"]
        assert result["resources"]["all_gates_passed"] and accepted["attempt"] == 1
        jobs[job_id] = {
            "accepted": sources[str(accepted_path.resolve())],
            "actual_exit": actual_exit,
            "result": accepted["result"],
            "attempt": accepted["attempt"],
            "gpu_index": result["gpu_index"],
            "started_epoch": result["started_epoch"],
            "finished_epoch": result["finished_epoch"],
            "resources": {k: result["resources"].get(k) for k in resource_fields},
            "actual_new_response_calls": result.get("actual_new_response_calls", 0),
            "new_API_calls": result.get("new_API_calls", 0),
        }
    cpu_accepted = read(root / "final_analysis/accepted/record.json")
    cpu_exit = read(cpu_accepted["actual_exit"])
    cpu_resources = read(cpu_accepted["resources"])
    assert cpu_exit["returncode"] == 0 and cpu_exit["actual_waitpid_observed"]
    assert cpu_resources["all_gates_passed"] and not cpu_resources["CUDA_initialized"]
    cpu = {k: v for k, v in cpu_resources.items() if k != "observations"}
    cpu["peak_rss_bytes"] = max(o["process"]["peak_rss_bytes"] for o in cpu_resources["observations"])
    cpu["minimum_host_available_bytes"] = min(o["host"]["available_bytes"] for o in cpu_resources["observations"])
    cpu["actual_exit"] = cpu_exit
    controller_exit = read(root / "supervisor/attempts/attempt0001/actual_exit/record.json")
    supervisor = read(root / "supervisor/closeout/record.json")
    assert controller_exit["returncode"] == 0 and controller_exit["actual_waitpid_observed"]
    assert supervisor["status"] == "COMPLETE" and supervisor["automatic_restart_stopped"]
    script = Path(__file__).resolve()
    output = {
        "schema": "finqa_v72_final_report_summary.v1",
        "status": "COMPLETE",
        "scientific_protocol_id": protocol["id"],
        "source_commit": protocol["source_commit"],
        "analysis_script": {"path": str(script), "sha256": hashlib.sha256(script.read_bytes()).hexdigest()},
        "report_scope": {"original_scientific_records_written": 0, "new_model_or_GPU_or_API_calls": 0, "new_native_scores": 0, "new_optimizer_updates": 0, "raw_episodes_or_Tensors_or_step_receipts_opened": False, "new_statistics_or_significance_thresholds": False, "automatic_followup_authorized": False},
        "final_summary": final,
        "training": training,
        "learning_rate_intervention": intervention,
        "training_dynamics": {"LowLR1192": dynamics, "HighLR1192": high_dynamics},
        "failure_mechanisms": mechanisms,
        "static_supervision_audit": static,
        "existing_analysis": existing,
        "execution": {"closeout": closeout, "jobs": jobs, "final_CPU": cpu, "controller_actual_exit": controller_exit, "supervisor_closeout": supervisor, "supervisor_own_waitpid_exit_code_available": False},
        "resource_policy": protocol["resource_policy"],
        "scientific_contract": protocol["scientific_contract"],
        "source_JSON_count": len(sources),
        "sources": list(sources.values()),
    }
    output["id"] = hashlib.sha256(json.dumps(output, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    summary = extract(Path(__file__).resolve().parents[2])
    # Refuse overwriting a report or an experiment record.
    with args.output.open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(summary, ensure_ascii=False, sort_keys=True, indent=2) + "\n")
    print(json.dumps({"id": summary["id"], "source_JSON_count": summary["source_JSON_count"], "output": str(args.output)}))
