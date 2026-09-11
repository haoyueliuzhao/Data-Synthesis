"""Exactly 32 isolated calls-to-first-Final sessions, then terminate collection."""

import os
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from trusted_synthesis.experiments.finance_qa_vnext_harness_responsibility.audit import manifest
from trusted_synthesis.experiments.finance_qa_vnext_soft_detail_exploration.capsule import (
    capsule_files,
)
from trusted_synthesis.experiments.finance_qa_vnext_soft_detail_exploration.plan import condition
from trusted_synthesis.experiments.finance_qa_vnext_task_panel.guards import (
    execution_guard,
    guard_report,
)
from trusted_synthesis.experiments.finance_qa_vnext_thinking_comparison.online.common import (
    request_body,
    write,
)

from .core import (
    Store,
    credential,
    history_guard,
    implementation,
    pipe_credential,
    verify_preparation,
)
from .plan import (
    AUDIT,
    AUDIT_SHA,
    BINDING,
    DOCUMENT,
    LABELS,
    MODEL,
    OLD,
    OLD_LABELS,
    OLD_UTILITY,
    OUTPUT,
    SYSTEM,
    TEST,
    WORKER_PYTHON,
    WORKERS,
    encode,
    read_json,
    record,
    reference,
    registrations,
    require,
    sampling_policy,
    sha,
    target_ledger,
)


def prepare(root):
    root = Path(root)
    history_guard(root)
    frozen = implementation(root)
    require(not (root / OUTPUT).exists(), "prepare.new_fixed_batch_only")
    public_path = root / OLD / "preparation/public/X2.json"
    public = read_json(public_path)
    private = read_json(root / OLD / "preparation/private/evaluation_targets.json")["X2"]
    prototypes = read_json(root / OLD / "preparation/private/target_class_prototypes.json")[
        "tasks"
    ]["E"]["X2"]
    rows = registrations(public)
    policy = sampling_policy()
    ledger = target_ledger(public, private)
    store = Store(root / OUTPUT / "preparation")
    store.json("implementation.json", frozen)
    store.json("policy.json", policy)
    store.json("target_ledger.json", ledger)
    store.json("generative_condition.json", condition("E"))
    store.json("registrations.json", rows)
    store.json("private/evaluation_targets.json", {"X2": private})
    store.json("private/target_class_prototypes.json", prototypes)
    store.json("private/review_identity_map.json", {r["review_id"]: r for r in rows})
    store.write(
        "private/isolation_canary.txt",
        b"Private assessment only; no instructions for the Worker.\n",
    )
    store.write("public/X2.json", public_path.read_bytes())
    store.write("design_at_freeze.md", (root / DOCUMENT).read_bytes())
    audit = Path(AUDIT).read_bytes()
    require(sha(audit) == AUDIT_SHA, "prepare.exact_user_audit")
    store.write("audit.original.txt", audit)
    store.json(
        "historical_references.json",
        [
            reference(root, path)
            for path in (
                OLD + "/preparation/public/X2.json",
                OLD + "/preparation/conditions.json",
                OLD + "/preparation/private/target_class_prototypes.json",
                OLD + "/closeout/measurement.json",
                OLD_UTILITY + "/quantity_revision/report.json",
                OLD_UTILITY + "/materialization/weight_view.json",
                BINDING + "/closeout/report.json",
            )
        ],
    )
    store.json(
        "historical_candidate_order.json",
        {"labels": OLD_LABELS, "new_score_fields_not_created": True},
    )
    files = capsule_files(root, "E")
    for name, raw in files.items():
        prior = root / OLD / "preparation/worker_code/E" / name
        require(prior.read_bytes() == raw, "prepare.exact_prior_E_worker_bytes")
        store.write("worker_code/" + name, raw)
    initial = encode(
        request_body(
            [
                {"role": "system", "content": SYSTEM},
                {"role": "user", "content": encode({"task": public}).decode()},
            ],
            MODEL,
        )
    )
    old_initial = root / OLD / "online/sessions/E_X2_01/turns/000_http_request.body"
    require(initial == old_initial.read_bytes(), "prepare.byte_identical_initial_E_request")
    store.write("initial_request.body", initial)
    store.json(
        "public_identity_checks.json",
        {
            "old_public_reference": reference(root, OLD + "/preparation/public/X2.json"),
            "initial_request_sha256": sha(initial),
            "all_worker_files_byte_identical": True,
            "new_formula_or_evidence_selection_hint": False,
            "initial_history_byte_identical_to_historical_E_X2": True,
            "provider_backend_identity_across_dates_claimed": False,
        },
    )
    checks = subprocess.run(
        [
            str(root / "trusted_data_synthesis/.venv/bin/python"),
            "-B",
            "-m",
            "pytest",
            "-q",
            "--tb=short",
            TEST,
        ],
        cwd=root,
        capture_output=True,
        check=False,
    )
    store.write("controls.stdout", checks.stdout)
    store.write("controls.stderr", checks.stderr)
    store.json(
        "controls.json",
        {
            "exit_code": checks.returncode,
            "new_test_reference": reference(root, TEST),
            "old_suites_rerun": False,
            "provider_calls": 0,
        },
    )
    require(checks.returncode == 0, "prepare.new_controls_before_calls")
    report = record(
        "DR_support_preparation",
        policy_id=policy["id"],
        ledger_id=ledger["id"],
        registrations=32,
        implementation_id=frozen["id"],
        new_model_requests=0,
        new_tokenizer_calls=0,
    )
    store.json("report.json", report)
    store.json("history.json", history_guard(root))
    store.seal(report_id=report["id"])
    return report


def launch_worker(root, registration, key):
    output = root / OUTPUT
    prep = output / "preparation"
    label = registration["label"]
    require(label in LABELS and registration["requested_model"] == MODEL, "launch.registered_only")
    directory = output / "online/sessions" / label
    read_fd = pipe_credential(key)
    command = [
        WORKER_PYTHON,
        "-I",
        "-S",
        "-B",
        str(prep / "worker_code/worker.py"),
        "--public",
        str(prep / "public/X2.json"),
        "--output",
        str(directory),
        "--model",
        MODEL,
        "--key-fd",
        str(read_fd),
    ]
    for name in (
        "evaluation_targets.json",
        "target_class_prototypes.json",
        "review_identity_map.json",
        "isolation_canary.txt",
    ):
        command.extend(["--forbidden", str(prep / "private" / name)])
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
    write(output / "online/collector_logs", label + ".stdout", completed.stdout)
    write(output / "online/collector_logs", label + ".stderr", completed.stderr)
    base = {
        k: registration[k]
        for k in ("label", "arm", "task_key", "replicate", "batch", "review_id", "wave")
    }
    if completed.returncode or not (directory / "result.json").exists():
        return {**base, "terminal": "unknown_worker_failure", "exit_code": completed.returncode}
    result = read_json(directory / "result.json")
    isolation = read_json(directory / "isolation.json")
    manifest(directory)
    require(result["origin"] == "live_http", "launch.real_provider_session")
    require(
        isolation["private_read_denied_before_provider"]
        and not isolation["repository_modules_loaded"],
        "launch.public_only_isolation",
    )
    return {
        **base,
        **{
            k: result[k]
            for k in (
                "terminal",
                "model_requests",
                "model_responses",
                "tool_calls",
                "provider_attempts",
            )
        },
        "result_id": result["id"],
        "exit_code": completed.returncode,
    }


def collect(root):
    root = Path(root)
    history_guard(root)
    verify_preparation(root)
    prep = root / OUTPUT / "preparation"
    rows = read_json(prep / "registrations.json")
    require([r["label"] for r in rows] == list(LABELS), "collect.exact_32_order")
    store = Store(root / OUTPUT / "online")
    store.json(
        "launch.json",
        record(
            "DR_fixed_launch",
            registrations=rows,
            maximum_provider_requests=1024,
            no_retries_or_resampling=True,
            no_assessment_before_all_32=True,
        ),
    )
    started = time.monotonic()
    key = credential(root / "trusted_data_synthesis/.env")
    results, waves = {}, []
    with execution_guard(online=True) as counts:
        for wave, expected in ((1, 24), (2, 8)):
            selected = [r for r in rows if r["wave"] == wave]
            require(len(selected) == expected, "collect.fixed_wave_sizes")
            before = time.monotonic()
            with ThreadPoolExecutor(max_workers=WORKERS) as pool:
                futures = {pool.submit(launch_worker, root, row, key): row for row in selected}
                for future in as_completed(futures):
                    row = futures[future]
                    try:
                        value = future.result()
                    except Exception as error:
                        value = {
                            "label": row["label"],
                            "review_id": row["review_id"],
                            "terminal": "unknown_collector_failure",
                            "error_type": type(error).__name__,
                        }
                    results[row["label"]] = value
                    print(
                        row["review_id"], value["terminal"], value.get("model_requests"), flush=True
                    )
            waves.append(
                {
                    "wave": wave,
                    "submitted": [r["label"] for r in selected],
                    "wall_seconds": time.monotonic() - before,
                    "no_intermediate_review_or_adaptation": True,
                }
            )
        del key
        reservations = {
            label: len(list((store.root / "sessions" / label / "turns").glob("*_reservation.json")))
            for label in LABELS
        }
        require(
            all(n <= 32 for n in reservations.values()) and sum(reservations.values()) <= 1024,
            "collect.actual_fixed_caps",
        )
        report = record(
            "DR_32_collection_report",
            registered=32,
            rows=[results[label] for label in LABELS],
            actual_reservations_by_session=reservations,
            model_requests=sum(reservations.values()),
            wall_seconds=time.monotonic() - started,
            waves=waves,
            all_workers_terminated=True,
            old_sessions_in_this_denominator=0,
            new_model_catalog_or_calibration_calls=0,
            retries_replacements_or_topups=0,
            Student_runs=0,
            tokenizer_calls=0,
            original_responses_not_reviewed_for_adaptive_sampling=True,
        )
        store.json("report.json", report)
        store.json("execution_guards.json", guard_report(counts, phase="fixed_32_E_X2_collection"))
    verify_preparation(root)
    store.json("history.json", history_guard(root))
    store.seal(report_id=report["id"])
    return report
