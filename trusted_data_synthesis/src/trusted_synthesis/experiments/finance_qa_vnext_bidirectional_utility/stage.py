"""One bounded experiment: fixed new collection, offline review, measurement and export."""

import argparse
import os
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from trusted_synthesis.domains.finance.qa_vnext.runtime import DurableStore
from trusted_synthesis.experiments.finance_qa_vnext_harness_responsibility.audit import manifest
from trusted_synthesis.experiments.finance_qa_vnext_model_execution.plan import (
    seal_directory,
    source_snapshot,
    verify_source_snapshot,
)
from trusted_synthesis.experiments.finance_qa_vnext_model_execution.runner import _credential
from trusted_synthesis.experiments.finance_qa_vnext_task_panel.guards import (
    execution_guard,
    guard_report,
)
from trusted_synthesis.experiments.finance_qa_vnext_thinking_comparison.online.common import write
from trusted_synthesis.experiments.finance_qa_vnext_trace_delivery.instructions import capsule_files
from trusted_synthesis.experiments.finance_qa_vnext_trace_delivery.stage import public_document

from .panel import Panel
from .plan import (
    AUDIT_PATH,
    AUDIT_SHA256,
    CONTROL_INDEX_SHA256,
    CONTROL_LABELS,
    DOCUMENT,
    LABELS,
    MODEL,
    OUTPUT,
    PACKAGE,
    PARENT,
    SYSTEM,
    TASKS,
    TESTS,
    TRAIN_TASKS,
    WORKER_PYTHON,
    condition,
    downstream_plan,
    history_guard,
    policy,
    read_json,
    record,
    registrations,
    require,
    sha,
)


def prepare(root):
    history_guard(root)
    implementation = source_snapshot(root)
    require(
        not subprocess.check_output(
            ["git", "status", "--porcelain", "--", PACKAGE, DOCUMENT, *TESTS], cwd=root
        ),
        "prepare.all_rules_committed",
    )
    require(
        subprocess.check_output(["git", "rev-parse", "refs/remotes/origin/main"], cwd=root)
        .decode()
        .strip()
        == implementation["source_commit"],
        "prepare.freeze_pushed_before_generation",
    )
    output = root / OUTPUT
    require(not output.exists(), "prepare.no_overwrite_or_repeat_sampling")
    panel = Panel(root)
    store = DurableStore(output / "preparation")
    store.json("implementation.json", implementation)
    store.json("condition.json", condition())
    store.json("finite_policy.json", policy())
    store.json("panel_selection.json", panel.design())
    store.json("downstream_plan.json", downstream_plan())
    control_path = root / PARENT / "closeout/materialization/index.json"
    require(
        sha(control_path.read_bytes()) == CONTROL_INDEX_SHA256, "prepare.accepted_control_index"
    )
    control_index = read_json(control_path)
    controls = [p for p in control_index["packages"] if p["session_label"] in CONTROL_LABELS]
    require(
        len(controls) == 9 and all(p["whole_package_token_consumable"] for p in controls),
        "prepare.nine_accepted_controls",
    )
    store.json(
        "old_control_references.json",
        {
            "index_sha256": CONTROL_INDEX_SHA256,
            "packages": controls,
            "requalified": False,
            "retokenized": False,
        },
    )
    store.json("history_guard.json", history_guard(root))
    store.write("design_at_freeze.md", (root / DOCUMENT).read_bytes())
    audit = Path(AUDIT_PATH).read_bytes()
    require(sha(audit) == AUDIT_SHA256, "prepare.original_audit")
    store.write("external_review.original.txt", audit)
    public, private = {}, {}
    for key, task in panel.tasks.items():
        public[key] = public_document(task)
        private[key] = {
            k: task[k]
            for k in (
                "key",
                "qa_id",
                "unit",
                "facts",
                "target",
                "relations",
                "sufficient_routes",
                "goal_scope",
                "interpretation",
                "precision_policy",
                "structure",
                "panel",
                "group",
                "company_cluster",
                "report_cluster",
            )
        }
        private[key]["public_document_id"] = public[key]["id"]
        store.json(f"public/{key}.json", public[key])
    store.json("private/evaluation_targets.json", private)
    from .study import target_prototypes

    store.json("private/target_class_prototypes.json", target_prototypes(panel, public))
    store.write(
        "private/isolation_canary.txt", b"Private evaluator canary; no model route hints.\n"
    )
    rows = registrations(public)
    require(len(rows) == 72 and len({r["label"] for r in rows}) == 72, "prepare.all_registrations")
    store.json("registrations.json", rows)
    files = capsule_files(root, "T")
    members = []
    for name, raw in files.items():
        store.write("worker_code/" + name, raw)
        members.append({"path": name, "sha256": sha(raw), "bytes": len(raw)})
    store.json(
        "worker_bundle.json",
        record(
            "unchanged_T_worker_bundle",
            members=members,
            system_sha256=sha(SYSTEM.encode()),
            interpreter=WORKER_PYTHON,
            flags=["-I", "-S", "-B"],
            same_parent_worker_calculator_isolate_projection_and_T_common_bytes=True,
            private_targets_or_route_menu_bundled=False,
        ),
    )
    tests = subprocess.run(
        [
            str(root / "trusted_data_synthesis/.venv/bin/python"),
            "-m",
            "pytest",
            "-q",
            "--tb=short",
            *TESTS,
        ],
        cwd=root,
        capture_output=True,
        check=False,
    )
    store.write("new_controls_stdout.txt", tests.stdout)
    store.write("new_controls_stderr.txt", tests.stderr)
    store.json(
        "new_controls.json",
        {
            "exit_code": tests.returncode,
            "test_files": list(TESTS),
            "test_sha256": {name: sha((root / name).read_bytes()) for name in TESTS},
            "old_64_controls_repeated": False,
            "old_24_token_rows_reencoded": False,
            "provider_calls": 0,
        },
    )
    require(tests.returncode == 0, "prepare.new_controls_failed")
    seal_directory(store, kind="open_support_preparation_manifest", condition_id=condition()["id"])
    return rows


def launch_worker(root, registration, credential):
    output = root / OUTPUT
    prep = output / "preparation"
    session = output / "online/sessions" / registration["label"]
    require(
        registration["requested_model"] == MODEL and registration["arm"] == "T",
        "collect.fixed_condition",
    )
    read_fd, write_fd = os.pipe()
    try:
        os.write(write_fd, credential.encode())
    finally:
        os.close(write_fd)
    command = [
        WORKER_PYTHON,
        "-I",
        "-S",
        "-B",
        str(prep / "worker_code/worker.py"),
        "--public",
        str(prep / f"public/{registration['task_key']}.json"),
        "--output",
        str(session),
        "--forbidden",
        str(prep / "private/evaluation_targets.json"),
        "--forbidden",
        str(prep / "private/isolation_canary.txt"),
        "--model",
        MODEL,
        "--key-fd",
        str(read_fd),
    ]
    try:
        completed = subprocess.run(
            command,
            cwd=prep / "worker_code",
            env={"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8"},
            pass_fds=(read_fd,),
            capture_output=True,
            check=False,
            timeout=32 * 190 + 60,
        )
    finally:
        os.close(read_fd)
    logs = output / "online/collector_logs"
    write(logs, registration["label"] + ".stdout", completed.stdout)
    write(logs, registration["label"] + ".stderr", completed.stderr)
    if completed.returncode != 0 or not (session / "result.json").exists():
        return {
            "label": registration["label"],
            "task_key": registration["task_key"],
            "terminal": "unknown_worker_failure",
            "exit_code": completed.returncode,
        }
    result = read_json(session / "result.json")
    require(result["origin"] == "live_http", "collect.live_model_only")
    manifest(session)
    isolation = read_json(session / "isolation.json")
    require(
        isolation["private_read_denied_before_provider"]
        and not isolation["repository_modules_loaded"],
        "collect.actual_public_only_process",
    )
    return {
        "label": registration["label"],
        "task_key": registration["task_key"],
        "terminal": result["terminal"],
        "exit_code": completed.returncode,
        "result_id": result["id"],
        **{
            key: result[key]
            for key in ("model_requests", "model_responses", "tool_calls", "provider_attempts")
        },
    }


def collect(root):
    with execution_guard(online=True) as counts:
        rows = prepare(root)
        output = root / OUTPUT
        store = DurableStore(output / "online")
        store.json(
            "launch.json",
            record(
                "new_support_launch",
                registrations=rows,
                condition_id=condition()["id"],
                fixed_workers=24,
                total_workers=72,
                independent_processes_and_histories=True,
                no_evaluation_before_all_workers_finish=True,
                model=MODEL,
                arm="T",
            ),
        )
        credential = _credential(root / "trusted_data_synthesis/.env")
        started = time.monotonic()
        results = {}
        with ThreadPoolExecutor(max_workers=24) as pool:
            futures = {pool.submit(launch_worker, root, row, credential): row for row in rows}
            for future in as_completed(futures):
                row = futures[future]
                try:
                    result = future.result()
                except Exception as error:
                    result = {
                        "label": row["label"],
                        "task_key": row["task_key"],
                        "terminal": "unknown_collector_failure",
                        "error_type": type(error).__name__,
                    }
                results[row["label"]] = result
                print(row["label"], result["terminal"], result.get("model_requests"), flush=True)
        del credential
        ordered = [results[label] for label in LABELS]
        attempts = {
            label: len(
                list((output / "online/sessions" / label / "turns").glob("*_reservation.json"))
            )
            for label in LABELS
        }
        require(
            all(n <= 32 for n in attempts.values()) and sum(attempts.values()) <= 2304,
            "collect.frozen_request_caps",
        )
        summary = record(
            "new_support_collection_summary",
            registered=72,
            rows=ordered,
            actual_reservations_by_session=attempts,
            model_requests=sum(attempts.values()),
            parallel_collection_wall_seconds=time.monotonic() - started,
            all_workers_terminated=True,
            no_retries=True,
            no_resampling=True,
            eventual_training_task_marginal={key: "1/6" for key in TRAIN_TASKS},
            collection_task_allocation={key: "1/3" for key in TASKS},
            no_old_trajectories_in_denominators=True,
            no_online_evaluation_feedback=True,
        )
        store.json("summary.json", summary)
        verify_source_snapshot(root, read_json(output / "preparation/implementation.json"))
        store.json("history_after.json", history_guard(root))
        store.json(
            "execution_guards.json", guard_report(counts, phase="fixed_72_new_open_sessions")
        )
        seal_directory(store, kind="open_support_online_manifest", summary_id=summary["id"])
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("collect", "assess", "finalize", "verify"))
    parser.add_argument("--reviews", type=Path)
    args = parser.parse_args()
    root = Path(subprocess.check_output(["git", "rev-parse", "--show-toplevel"]).decode().strip())
    if args.mode == "collect":
        result = collect(root)
    elif args.mode == "assess":
        from .evaluate import assess

        result = assess(root)
    elif args.mode == "finalize":
        from .evaluate import finalize

        require(args.reviews is not None, "finalize.reviews_required")
        result = finalize(root, args.reviews)
    else:
        result = {
            name: manifest(root / OUTPUT / name)["id"]
            for name in ("preparation", "online", "assessment", "closeout")
        }
    print(result.get("id", result), flush=True)


if __name__ == "__main__":
    main()
