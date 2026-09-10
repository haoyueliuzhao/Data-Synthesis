"""One 48-session N/E collection, offline assessment and closeout; no Student mode."""

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

from .capsule import capsule_files
from .panel import Panel
from .plan import (
    ARMS,
    AUDIT_PATH,
    AUDIT_SHA256,
    DOCUMENT,
    LABELS,
    MODEL,
    OUTPUT,
    PACKAGE,
    PARENT,
    SYSTEMS_NEW,
    TASKS,
    TESTS,
    WORKER_PYTHON,
    WORKERS,
    condition,
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
        "prepare.all_new_rules_committed",
    )
    remote = (
        subprocess.check_output(["git", "rev-parse", "refs/remotes/origin/main"], cwd=root)
        .decode()
        .strip()
    )
    require(remote == implementation["source_commit"], "prepare.freeze_pushed_before_calls")
    output = root / OUTPUT
    require(not output.exists(), "prepare.no_overwrite_or_repeat")
    panel = Panel(root)
    rows = registrations(panel.public)
    require(len(rows) == len({r["label"] for r in rows}) == 48, "prepare.fixed_48")
    store = DurableStore(output / "preparation")
    store.json("implementation.json", implementation)
    store.json("conditions.json", {arm: condition(arm) for arm in ARMS})
    store.json("policy.json", policy())
    store.json("source_design.json", panel.design())
    store.json("private/evaluation_targets.json", panel.private)
    store.json("registrations.json", rows)
    store.json("private/review_identity_map.json", {r["review_id"]: r for r in rows})
    store.json("history_guard.json", history_guard(root))
    store.write("design_at_freeze.md", (root / DOCUMENT).read_bytes())
    audit = Path(AUDIT_PATH).read_bytes()
    require(sha(audit) == AUDIT_SHA256, "prepare.exact_current_user_audit")
    store.write("audit.original.txt", audit)
    prior_identity = root / PARENT / "preparation/model_catalog_snapshot.json"
    store.json(
        "prior_Flash_contract_reference.json",
        {
            "path": str(prior_identity.relative_to(root)),
            "sha256": sha(prior_identity.read_bytes()),
            "new_model_catalog_requests": 0,
            "new_model_calibration_requests": 0,
            "prior_live_167_response_contract_already_accepted": True,
        },
    )
    for key in TASKS:
        store.json(f"public/{key}.json", panel.public[key])
    from .exploration import target_prototypes

    store.json("private/target_class_prototypes.json", target_prototypes(panel))
    store.write("private/isolation_canary.txt", b"Private evaluator only; no route menu.\n")
    bundles = {}
    for arm in ARMS:
        files = capsule_files(root, arm)
        for name, raw in files.items():
            store.write(f"worker_code/{arm}/{name}", raw)
        bundles[arm] = {
            "system_sha256": sha(SYSTEMS_NEW[arm].encode()),
            "members": [
                {"path": name, "bytes": len(raw), "sha256": sha(raw)} for name, raw in files.items()
            ],
            "Worker_calculator_isolate_projection_model_contract_unchanged": True,
            "only_common_public_SYSTEM_constant_appended": True,
            "private_targets_or_route_menu_bundled": False,
        }
    store.json("worker_bundles.json", bundles)
    tests = subprocess.run(
        [
            str(root / "trusted_data_synthesis/.venv/bin/python"),
            "-B",
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
            "provider_calls": 0,
            "old_test_suites_repeated": False,
            "old_scores_recomputed": False,
        },
    )
    require(tests.returncode == 0, "prepare.new_controls_failed_before_generation")
    seal_directory(
        store,
        kind="soft_detail_preparation_manifest",
        condition_ids={arm: condition(arm)["id"] for arm in ARMS},
    )
    return rows


def launch_worker(root, registration, credential):
    output = root / OUTPUT
    prep = output / "preparation"
    arm, key, label = registration["arm"], registration["task_key"], registration["label"]
    require(
        arm in ARMS and registration["requested_model"] == MODEL,
        "collect.frozen_condition_and_model",
    )
    session = output / "online/sessions" / label
    code = prep / "worker_code" / arm
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
        str(code / "worker.py"),
        "--public",
        str(prep / f"public/{key}.json"),
        "--output",
        str(session),
        "--forbidden",
        str(prep / "private/evaluation_targets.json"),
        "--forbidden",
        str(prep / "private/isolation_canary.txt"),
        "--forbidden",
        str(prep / "private/target_class_prototypes.json"),
        "--forbidden",
        str(prep / "private/review_identity_map.json"),
        "--model",
        MODEL,
        "--key-fd",
        str(read_fd),
    ]
    try:
        completed = subprocess.run(
            command,
            cwd=code,
            env={"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8"},
            pass_fds=(read_fd,),
            capture_output=True,
            check=False,
            timeout=32 * 190 + 60,
        )
    finally:
        os.close(read_fd)
    logs = output / "online/collector_logs"
    write(logs, label + ".stdout", completed.stdout)
    write(logs, label + ".stderr", completed.stderr)
    base = {k: registration[k] for k in ("label", "arm", "task_key", "review_id", "wave")}
    if completed.returncode != 0 or not (session / "result.json").exists():
        return {**base, "terminal": "unknown_worker_failure", "exit_code": completed.returncode}
    result = read_json(session / "result.json")
    require(result["origin"] == "live_http", "collect.only_live_new_sessions")
    manifest(session)
    isolation = read_json(session / "isolation.json")
    require(
        isolation["private_read_denied_before_provider"]
        and not isolation["repository_modules_loaded"],
        "collect.actual_public_only_process",
    )
    return {
        **base,
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
                "fixed_NE_launch",
                registrations=rows,
                model=MODEL,
                fixed_workers=WORKERS,
                total_workers=48,
                waves=2,
                all_registration_submission_ordinals_frozen=True,
                within_wave_N_E_interleaved_submission=True,
                provider_scheduling_and_random_state_not_controlled=True,
                independent_processes_and_empty_histories=True,
                no_evaluation_before_all_48_finish=True,
            ),
        )
        credential = _credential(root / "trusted_data_synthesis/.env")
        started = time.monotonic()
        results, waves = {}, []
        for wave in (1, 2):
            wave_rows = [row for row in rows if row["wave"] == wave]
            require(len(wave_rows) == 24, "collect.balanced_fixed_wave")
            wave_started = time.monotonic()
            with ThreadPoolExecutor(max_workers=WORKERS) as pool:
                futures = {
                    pool.submit(launch_worker, root, row, credential): row for row in wave_rows
                }
                for future in as_completed(futures):
                    row = futures[future]
                    try:
                        result = future.result()
                    except Exception as error:
                        result = {
                            **{
                                k: row[k] for k in ("label", "arm", "task_key", "review_id", "wave")
                            },
                            "terminal": "unknown_collector_failure",
                            "error_type": type(error).__name__,
                        }
                    results[row["label"]] = result
                    print(
                        row["review_id"],
                        row["task_key"],
                        result["terminal"],
                        result.get("model_requests"),
                        flush=True,
                    )
            waves.append(
                {
                    "wave": wave,
                    "submitted_labels": [r["label"] for r in wave_rows],
                    "wall_seconds": time.monotonic() - wave_started,
                    "no_review_or_adaptation_between_waves": True,
                }
            )
        del credential
        ordered = [results[label] for label in LABELS]
        attempts = {
            label: len(
                list((output / "online/sessions" / label / "turns").glob("*_reservation.json"))
            )
            for label in LABELS
        }
        require(
            all(n <= 32 for n in attempts.values()) and sum(attempts.values()) <= 1536,
            "collect.registered_caps",
        )
        summary = record(
            "NE_collection_summary",
            registered=48,
            rows=ordered,
            actual_reservations_by_session=attempts,
            model_requests=sum(attempts.values()),
            parallel_collection_wall_seconds=time.monotonic() - started,
            wave_records=waves,
            all_workers_terminated=True,
            no_retries=True,
            no_resampling=True,
            old_sessions_in_new_denominators=0,
            no_online_evaluation_feedback=True,
            Student_training_and_evaluation_authorized_or_run=False,
        )
        store.json("summary.json", summary)
        verify_source_snapshot(root, read_json(output / "preparation/implementation.json"))
        store.json("history_after.json", history_guard(root))
        store.json("execution_guards.json", guard_report(counts, phase="fixed_48_NE_collection"))
        seal_directory(store, kind="soft_detail_online_manifest", summary_id=summary["id"])
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
        verify_source_snapshot(root, read_json(root / OUTPUT / "preparation/implementation.json"))
        history_guard(root)
    print(result.get("id", result), flush=True)


if __name__ == "__main__":
    main()
