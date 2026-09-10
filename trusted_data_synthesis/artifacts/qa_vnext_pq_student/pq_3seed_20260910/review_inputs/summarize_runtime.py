"""Post-generation descriptive counts; does not score answers or call a model."""

from collections import Counter
from pathlib import Path

from trusted_synthesis.domains.finance.qa_vnext.runtime import DurableStore
from trusted_synthesis.experiments.finance_qa_vnext_model_execution.plan import seal_directory
from trusted_synthesis.experiments.finance_qa_vnext_pq_student import evaluate
from trusted_synthesis.experiments.finance_qa_vnext_pq_student.plan import (
    evaluation_config,
    read_json,
    record,
    sha,
)


def main():
    root = Path(__file__).resolve().parents[5]
    output, _, registrations, _ = evaluate._prepared(root)
    evaluate.manifest(output / "assessment")
    rows = []
    for variant in evaluation_config()["variants"]:
        directory = output / "evaluation" / variant
        generation = read_json(directory / "report.json")
        audits = [
            read_json(output / f"assessment/audits/{variant}/{r['task_key']}.json")
            for r in registrations
        ]
        protocol_errors, tool_error_types, tool_error_messages = Counter(), Counter(), Counter()
        event_count, pure_message_count, generated_tokens = 0, 0, 0
        for registration in registrations:
            turns = directory / "sessions" / registration["task_key"] / "turns"
            for path in turns.glob("*_event.json"):
                event = read_json(path)
                event_count += 1
                if event["protocol_error"]:
                    protocol_errors[event["protocol_error"]] += 1
                elif not event["final"] and event["tool_call"] is None:
                    pure_message_count += 1
                call = event["tool_call"]
                if call is not None and call["output"]["status"] == "error":
                    error = call["output"]["error"]
                    tool_error_types[error["type"]] += 1
                    tool_error_messages[error["message"]] += 1
            for path in turns.glob("*_outcome.json"):
                generated_tokens += read_json(path).get("generated_token_count", 0)
        row = {
            "variant": variant,
            "sessions": len(audits),
            "Final_delivered": sum(a["first_final_index"] is not None for a in audits),
            "model_requests": sum(a["model_requests"] for a in audits),
            "tool_calls": sum(a["tool_calls"] for a in audits),
            "successful_calculations": sum(len(a["calculations"]) for a in audits),
            "no_Final_tasks": [
                {
                    "task_key": r["task_key"],
                    "terminal": a["terminal"],
                    "model_requests": a["model_requests"],
                    "tool_calls": a["tool_calls"],
                }
                for r, a in zip(registrations, audits, strict=True)
                if a["first_final_index"] is None
            ],
            "event_count": event_count,
            "pure_message_events": pure_message_count,
            "protocol_errors": dict(protocol_errors),
            "tool_error_types": dict(tool_error_types),
            "tool_error_messages": dict(tool_error_messages),
            "generated_tokens_including_final_EOS": generated_tokens,
            "evaluation_seconds": generation["elapsed_seconds"],
            "all_raw_history_verified": all(a["raw_model_and_history_verified"] for a in audits),
        }
        if variant != "B0":
            training = read_json(output / f"training/{variant}/report.json")
            row["training"] = {
                key: training[key]
                for key in (
                    "optimizer_updates", "actual_supervised_tokens", "actual_sequence_tokens",
                    "elapsed_seconds", "peak_GPU_allocated_bytes", "peak_GPU_reserved_bytes",
                )
            }
            row["training"]["first_weighted_loss"] = training["records"][0]["full_pass_weighted_loss"]
            row["training"]["last_weighted_loss"] = training["records"][-1]["full_pass_weighted_loss"]
        rows.append(row)
    assert sum(r["sessions"] for r in rows) == 84
    report = record(
        "post_generation_runtime_description",
        rows=rows,
        model_calls_in_this_analysis=0,
        no_answer_scores_in_this_report=True,
        source_script_sha256=sha(Path(__file__).read_bytes()),
        actual_execution=read_json(output / "execution/process_report.json"),
        pairing_audit_id=read_json(output / "execution/pairing_audit.json")["id"],
    )
    store = DurableStore(output / "analysis")
    store.json("runtime_summary.json", report)
    seal_directory(store, kind="pq_student_descriptive_runtime_manifest", report_id=report["id"])
    print(report["id"])


if __name__ == "__main__":
    main()
