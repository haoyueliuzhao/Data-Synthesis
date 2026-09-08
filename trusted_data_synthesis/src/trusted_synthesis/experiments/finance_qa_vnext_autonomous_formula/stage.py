"""Prepare public-only capsules, collect twelve fresh sessions, then independently evaluate."""

import argparse
import os
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from trusted_synthesis.domains.finance.qa_vnext.runtime import DurableStore
from trusted_synthesis.experiments.finance_qa_vnext_finqa_difficulty.panel import Panel
from trusted_synthesis.experiments.finance_qa_vnext_finqa_difficulty.sources import catalog
from trusted_synthesis.experiments.finance_qa_vnext_harness_responsibility.audit import manifest
from trusted_synthesis.experiments.finance_qa_vnext_model_execution.plan import (
    seal_directory,
    source_snapshot,
    verify_source_snapshot,
)
from trusted_synthesis.experiments.finance_qa_vnext_model_execution.runner import _credential

from .online.common import record, sha
from .plan import (
    DOCUMENT,
    LABELS,
    OUTPUT,
    PACKAGE,
    TASKS,
    TEST,
    WORKER_PYTHON,
    condition,
    history_guard,
    read_json,
    registrations,
    require,
)

FORBIDDEN_PUBLIC_KEYS = {
    "program",
    "exe_ans",
    "target",
    "selected",
    "selected_facts",
    "answer_unit",
    "independently_reviewed_target",
    "reference_roles",
    "interpretation",
}


def assert_public(value):
    if isinstance(value, dict):
        require(not FORBIDDEN_PUBLIC_KEYS.intersection(value), "public.hidden_field")
        for child in value.values():
            assert_public(child)
    elif isinstance(value, list):
        for child in value:
            assert_public(child)


def public_document(task):
    entry = task["entry"]
    segments, facts = catalog(entry)
    result = record(
        "public_document",
        task_id=task["qa_id"],
        question=entry["qa"]["question"],
        filename=entry["filename"],
        source={k: entry[k] for k in ("table", "pre_text", "post_text")},
        segments=segments,
        numeric_catalog=list(facts.values()),
        indexing="Uniform zero-based table tROWcCOL / pre_text pN / post_text qN segments. "
        "All numeric spans are indexed, including years and OCR artifacts; no relevance or "
        "financial-role certification. source:SEGMENTnINDEX names a literal numeric span. "
        "value is its exact rational value; percent tokens are fractions, "
        "accounting negatives retained.",
    )
    assert_public(result)
    require(
        len(result["numeric_catalog"]) == len(task["facts"]), "public.all_facts_not_selected_subset"
    )
    return result


def prepare(root):
    implementation = source_snapshot(root)
    history_guard(root)
    output = root / OUTPUT
    require(not output.exists(), "stage.existing_output")
    store = DurableStore(output / "preparation")
    panel = Panel(root)
    public, private = {}, {}
    for key in TASKS:
        task = panel.tasks[key]
        public[key] = public_document(task)
        private[key] = {
            k: task[k] for k in ("key", "qa_id", "unit", "facts", "target", "relations")
        }
        private[key]["public_document_id"] = public[key]["id"]
        store.json(f"public/{key}.json", public[key])
    store.json("private/evaluation_targets.json", private)
    store.write(
        "private/isolation_canary.txt", b"Synthetic inaccessible canary; no formula or answer.\n"
    )
    store.json("implementation.json", implementation)
    store.json("condition.json", condition())
    store.json("history_guard.json", history_guard(root))
    store.json("registrations.json", registrations(public))
    store.write("design_at_freeze.md", (root / DOCUMENT).read_bytes())
    bundle_members = []
    for path in sorted((root / PACKAGE / "online").glob("*.py")):
        data = path.read_bytes()
        store.write("worker_code/" + path.name, data)
        bundle_members.append({"path": path.name, "sha256": sha(data), "bytes": len(data)})
    store.json(
        "worker_bundle.json",
        {
            "python": WORKER_PYTHON,
            "flags": ["-I", "-S", "-B"],
            "members": bundle_members,
            "private_evaluator_bundled": False,
        },
    )
    check = subprocess.run(
        [
            str(root / "trusted_data_synthesis/.venv/bin/python"),
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
    store.write("tests_stdout.txt", check.stdout)
    store.write("tests_stderr.txt", check.stderr)
    store.json(
        "tests.json",
        {
            "exit_code": check.returncode,
            "new_controls_only": True,
            "test_sha256": sha((root / TEST).read_bytes()),
            "provider_calls": 0,
        },
    )
    require(check.returncode == 0, "stage.controls_failed")
    seal_directory(store, kind="autonomous_preparation_manifest", condition_id=condition()["id"])
    return registrations(public)


def launch_worker(root, registration, credential):
    output = root / OUTPUT
    prep = output / "preparation"
    session = output / "online/sessions" / registration["label"]
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
        "--key-fd",
        str(read_fd),
    ]
    environment = {"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8"}
    try:
        completed = subprocess.run(
            command,
            cwd=prep / "worker_code",
            env=environment,
            pass_fds=(read_fd,),
            capture_output=True,
            check=False,
            timeout=32 * 190 + 60,
        )
    finally:
        os.close(read_fd)
    # These are collector-only records. No response is injected into a worker.
    logs = output / "online/collector_logs"
    logs.mkdir(parents=True, exist_ok=True)
    for suffix, content in (("stdout", completed.stdout), ("stderr", completed.stderr)):
        with (logs / f"{registration['label']}.{suffix}").open("xb") as handle:
            handle.write(content)
    if completed.returncode != 0 or not (session / "result.json").exists():
        return {
            "label": registration["label"],
            "task_key": registration["task_key"],
            "terminal": "unknown_worker_failure",
            "exit_code": completed.returncode,
            "model_requests": len(list((session / "turns").glob("*_reservation.json"))),
            "model_responses": len(list((session / "turns").glob("*_assistant.raw"))),
            "tool_calls": None,
        }
    result = read_json(session / "result.json")
    require(result["origin"] == "live_http", "stage.no_scripted_model_population")
    manifest(session)
    isolation = read_json(session / "isolation.json")
    require(
        isolation["private_read_denied_before_provider"]
        and not isolation["repository_modules_loaded"],
        "stage.actual_public_only_process",
    )
    return {
        "label": registration["label"],
        "task_key": registration["task_key"],
        "terminal": result["terminal"],
        "exit_code": completed.returncode,
        "result_id": result["id"],
        **{
            k: result[k]
            for k in ("model_requests", "model_responses", "tool_calls", "provider_attempts")
        },
    }


def collect(root):
    rows = prepare(root)
    output = root / OUTPUT
    store = DurableStore(output / "online")
    store.json(
        "launch.json",
        record(
            "launch",
            registrations=rows,
            condition_id=condition()["id"],
            worker_interpreter=WORKER_PYTHON,
            independent_exec_processes=True,
            evaluator_started=False,
            fixed_workers=12,
        ),
    )
    credential = _credential(root / "trusted_data_synthesis/.env")
    results = {}
    with ThreadPoolExecutor(max_workers=12) as pool:
        futures = {pool.submit(launch_worker, root, r, credential): r for r in rows}
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
    ordered = [results[label] for label in LABELS]
    known_count = sum(r.get("model_requests", 0) for r in ordered)
    require(known_count <= 384, "stage.attempt_cap")
    result = record(
        "collection_summary",
        registrations=12,
        rows=ordered,
        all_workers_terminated=True,
        fixed_task_weights={key: "1/6" for key in TASKS},
        known_model_requests=known_count,
        no_offline_evaluation_feedback=True,
        no_resampling=True,
        no_student=True,
    )
    store.json("summary.json", result)
    verify_source_snapshot(root, read_json(output / "preparation/implementation.json"))
    history_guard(root)
    seal_directory(store, kind="autonomous_online_manifest", summary_id=result["id"])
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["collect", "assess", "closeout", "verify"])
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--reviews", type=Path)
    args = parser.parse_args()
    if args.mode == "collect":
        result = collect(args.root)
    elif args.mode in {"assess", "closeout"}:
        from .evaluate import assess, closeout

        result = assess(args.root) if args.mode == "assess" else closeout(args.root, args.reviews)
    else:
        result = {
            name: manifest(args.root / OUTPUT / name)["id"]
            for name in ("preparation", "online", "assessment", "closeout")
        }
    print(result.get("id", result), flush=True)


if __name__ == "__main__":
    main()
