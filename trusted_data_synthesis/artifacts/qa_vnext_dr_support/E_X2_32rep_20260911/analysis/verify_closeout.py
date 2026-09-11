"""Read saved outcomes and byte seals; do not rejudge or re-run any experiment."""

from collections import Counter
from pathlib import Path

from trusted_synthesis.experiments.finance_qa_vnext_dr_support.core import (
    Store,
    history_guard,
    verify_preparation,
)
from trusted_synthesis.experiments.finance_qa_vnext_dr_support.plan import (
    LABELS,
    OLD,
    OLD_LABELS,
    OLD_UTILITY,
    OUTPUT,
    read_json,
    record,
    reference,
    require,
)
from trusted_synthesis.experiments.finance_qa_vnext_harness_responsibility.audit import manifest
from trusted_synthesis.experiments.finance_qa_vnext_task_panel.guards import (
    execution_guard,
    guard_report,
)


def main():
    root = Path("/data1/zhuxinrui/projects/Data-Synthesis")
    output = root / OUTPUT
    history = history_guard(root)
    verify_preparation(root)
    seals = {
        name: manifest(output / name)["id"]
        for name in ("preparation", "online", "assessment", "manual_reviews", "closeout")
    }
    transcription = read_json(output / "manual_reviews/report.json")
    bound_builder = transcription["builder_reference"]
    require(
        reference(root, bound_builder["path"]) == bound_builder,
        "verify.transcription_code_unchanged",
    )
    report = read_json(output / "closeout/report.json")
    selection = read_json(output / "closeout/support_selection.json")
    rows = report["rows"]
    require({r["label"] for r in rows} == set(OLD_LABELS) | set(LABELS), "verify.fixed_population")
    old_classes = read_json(root / OLD / "closeout/measurement.json")["session_class_ids"]
    old_checks, admitted, nonempty, stored_public_files = [], {}, {}, {}
    with execution_guard(online=False) as counts:
        for batch, labels, base in (("historical_8", OLD_LABELS, OLD), ("new_32", LABELS, OUTPUT)):
            admitted[batch] = 0
            nonempty[batch] = 0
            stored_public_files[batch] = 0
            for label in labels:
                directory = root / base / "online/sessions" / label
                actual = read_json(directory / "result.json")
                admitted[batch] += len(actual["events"])
                files = list((directory / "turns").glob("*_assistant.raw"))
                stored_public_files[batch] += len(files)
                nonempty[batch] += sum(p.stat().st_size > 0 for p in files)
                if batch == "historical_8":
                    row = next(r for r in rows if r["label"] == label)
                    old = read_json(root / OLD_UTILITY / f"quantity_revision/sessions/{label}.json")
                    checks = {
                        "class_ID_equal": row["class_id"] == old_classes[label],
                        "quantity_status_equal": row["answer"]["V_quantity"]
                        == old["answer"]["V_quantity"],
                        "complete_indicator_equal": row["formula_driven_trace_verified"]
                        == old["formula_driven_trace_verified"],
                        "original_qualification_link": row["historical_qualification_id"]
                        == old["id"],
                    }
                    require(all(checks.values()), "verify.old_eight_saved_outcomes_unchanged")
                    old_checks.append({"label": label, **checks})
        require(selection["status"] == "INPUT_INADEQUATE", "verify.actual_stop_condition")
        require(
            {k: len(v) for k, v in selection["eligible"].items()} == {"D": 35, "R": 1},
            "verify.actual_counts_not_new_scores",
        )
        require(
            not any(selection[k] for k in ("train", "heldout", "token_check")),
            "verify.no_partial_training_selection",
        )
        require(not selection["training_allowed"], "verify.training_not_activated")
        absent = {
            name: not (output / name).exists()
            for name in (
                "materialization",
                "training",
                "development",
                "confirmation",
                "student",
                "selection",
            )
        }
        require(all(absent.values()), "verify.conditional_phases_not_started")
        costs = report["new_costs"]["aggregate"]
        require(
            costs["reserved_attempts"] == 69 and costs["tool_calls"] == 36,
            "verify.saved_resource_totals",
        )
        require(
            costs["successful_calculations"] == 33 and costs["tool_errors"] == 3,
            "verify.call_not_session_counts",
        )
        claims = [
            c["interpretation"]
            for r in rows
            for c in r["current_source_claim_certification"]["claims"]
        ]
        evidence = record(
            "DR_closeout_integrity",
            phase_manifest_ids=seals,
            report_reference=reference(root, OUTPUT + "/closeout/report.json"),
            selection_reference=reference(root, OUTPUT + "/closeout/support_selection.json"),
            historical_eight_checks=old_checks,
            actual_admitted_response_counts=admitted,
            actual_nonempty_public_response_counts=nonempty,
            stored_assistant_file_counts_including_empty=stored_public_files,
            original_claim_roles=dict(Counter(c["role"] for c in claims)),
            original_claim_statuses=dict(Counter(c["status"] for c in claims)),
            conditional_phase_directories_absent=absent,
            original_frozen_results_only_no_requalification=True,
            new_model_calls=0,
            new_tokenizer_calls=0,
            new_training_runs=0,
            unknown_states_not_replaced=True,
            historical_files_guard=history,
            executing_assistant_not_independent_reproduction=True,
        )
        store = Store(output / "verification")
        store.json("report.json", evidence)
        table = [
            "# 已封存四十候选的字段对照（仅派生展示）",
            "",
            "P = PASS，F = FAIL，U = UNDETERMINED；类别 NOT_JOINT_VALID 不等于新增财务错误。",
            "",
            "| 会话 | 评审编号 | 数量 | 公共目标 | 当前来源声明 | 完整财务/交付 | 完整类 |",
            "| --- | --- | --- | --- | --- | --- | --- |",
        ]
        codes = {"PASS": "P", "FAIL": "F", "UNDETERMINED": "U"}
        for row in rows:
            packet = f"../assessment/packets/{row['review_id']}.json"
            values = [
                row["label"],
                f"[{row['review_id']}]({packet})",
                codes[row["answer"]["V_quantity"]],
                codes[row["public_target_binding"]["public_task_applicability"]],
                codes[row["current_source_claim_certification"]["status"]],
                codes[row["trace_status"]],
                row["behavior"],
            ]
            table.append("| " + " | ".join(values) + " |")
        store.write("case_table.md", ("\n".join(table) + "\n").encode())
        store.json(
            "execution_guards.json", guard_report(counts, phase="DR_read_only_closeout_integrity")
        )
        store.seal(report_id=evidence["id"])
    print(evidence["id"], flush=True)


if __name__ == "__main__":
    main()
