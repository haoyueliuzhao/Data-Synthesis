"""Precall preparation and exactly 32 isolated first-Final sessions, without review."""

import os
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from unittest.mock import patch

from trusted_synthesis.experiments.finance_qa_vnext_harness_responsibility.audit import manifest
from trusted_synthesis.experiments.finance_qa_vnext_soft_detail_exploration.capsule import (
    capsule_files as prior_capsule_files,
)
from trusted_synthesis.experiments.finance_qa_vnext_soft_detail_exploration.model_contract import (
    ACCEPTED_RESPONSE_MODELS,
)
from trusted_synthesis.experiments.finance_qa_vnext_task_panel.guards import (
    execution_guard,
    guard_report,
)
from trusted_synthesis.experiments.finance_qa_vnext_thinking_comparison.online.common import (
    LIMITS,
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
    BASIS_INSTRUCTIONS,
    COMMON_SYSTEM,
    DOCUMENT,
    GENERATION_CONDITIONS,
    LABELS,
    MODEL,
    OUTPUT,
    PREVIOUS,
    SOURCE,
    SYSTEMS,
    TASKS,
    TESTS,
    WORKER_PYTHON,
    WORKERS,
    condition,
    encode,
    policy,
    read_json,
    record,
    reference,
    registrations,
    require,
    sha,
    target_ledgers,
)
from .projection import x2_cross_quantity_context
from .tokens import BINDING_PATH, PARENT_POLICY_PATH, assets, read_bound_metadata

PRIVATE_FILES = (
    "evaluation_targets.json",
    "target_class_prototypes.json",
    "review_identity_map.json",
    "x2_cross_quantity_context.json",
    "isolation_canary.txt",
)
SIGNATURE_CONTENT_FIELDS = (
    "task_version",
    "source_document_id",
    "goal_scope",
    "answer_source_normal_form",
    "active_support",
)


def capsule_files(root, guidance):
    """Only append the new public condition to the byte-identical previous N capsule."""
    root = Path(root)
    require(guidance in GENERATION_CONDITIONS, "capsule.registered_guidance")
    files = prior_capsule_files(root, "N")
    for name, raw in files.items():
        require(
            raw == (root / SOURCE / "preparation/worker_code/N" / name).read_bytes(),
            "capsule.exact_previous_N_worker",
        )
    suffix = "\n\n" + BASIS_INSTRUCTIONS[guidance]
    require(SYSTEMS[guidance] == COMMON_SYSTEM + suffix, "capsule.only_guidance_append")
    files["common.py"] += ("\n\nSYSTEM = SYSTEM + " + repr(suffix) + "\n").encode()
    return files


def financial_prototypes(public, private, original):
    """Keep financial source forms, never old condition or complete-class identities."""
    result = {}
    for task in TASKS:
        result[task] = {}
        for route in ("D", "R"):
            signature = original["tasks"]["N"][task][route]["signature"]
            content = {key: signature[key] for key in SIGNATURE_CONTENT_FIELDS}
            require(
                content
                == {
                    key: original["tasks"]["E"][task][route]["signature"][key]
                    for key in SIGNATURE_CONTENT_FIELDS
                }
                and content["task_version"] == public[task]["task_id"]
                and content["source_document_id"] == public[task]["id"]
                and content["goal_scope"] == private[task]["goal_scope"],
                "prepare.same_financial_content_not_old_class_identity",
            )
            result[task][route] = {"signature": content}
    return result


def validate_registrations(rows, public):
    require(rows == registrations(public), "collect.exact_new_registrations_and_metadata")
    require(
        len(rows) == 32
        and [row["label"] for row in rows] == list(LABELS)
        and LIMITS["model_responses"] == LIMITS["tool_calls"] == 32,
        "collect.exact_32_order_and_worker_caps",
    )
    return rows


def prepare(root):
    """Freeze this new support stage and run its controls; no credential/model/tokenizer."""
    root = Path(root)
    history_guard(root)
    frozen = implementation(root)
    require(not (root / OUTPUT).exists(), "prepare.new_fixed_batch_only")
    audit = Path(AUDIT).read_bytes()
    require(sha(audit) == AUDIT_SHA, "prepare.exact_user_audit")
    with execution_guard(online=False) as counts:
        counts["tokenizer_load"] = 0

        def forbidden_tokenizer(*args, **kwargs):
            counts["tokenizer_load"] += 1
            raise RuntimeError("prepare.tokenizer_loading_forbidden")

        with patch.object(assets, "load_tokenizer", forbidden_tokenizer):
            public = {
                task: read_json(root / SOURCE / f"preparation/public/{task}.json") for task in TASKS
            }
            original_private = read_json(
                root / SOURCE / "preparation/private/evaluation_targets.json"
            )
            private = {task: original_private[task] for task in TASKS}
            original_prototypes = read_json(
                root / SOURCE / "preparation/private/target_class_prototypes.json"
            )
            prototypes = financial_prototypes(public, private, original_prototypes)
            prior_conditions = read_json(root / SOURCE / "preparation/conditions.json")
            require(prior_conditions["N"]["system"] == COMMON_SYSTEM, "prepare.same_common_N")
            previous = read_json(root / PREVIOUS / "closeout/support_selection.json")
            require(
                previous["status"] == "INPUT_INADEQUATE" and previous["training_allowed"] is False,
                "prepare.previous_batch_closed_not_resumed",
            )
            rows = validate_registrations(registrations(public), public)
            sampling = policy()
            ledgers = target_ledgers(public, private)
            context = x2_cross_quantity_context(public["X2"], private["X2"]["goal_scope"])
            binding, representation = read_bound_metadata(root)
            store = Store(root / OUTPUT / "preparation")
            for name, value in (
                ("implementation.json", frozen),
                ("policy.json", sampling),
                ("target_ledgers.json", ledgers),
                ("conditions.json", {g: condition(g) for g in GENERATION_CONDITIONS}),
                ("registrations.json", rows),
                ("private/evaluation_targets.json", private),
                ("private/target_class_prototypes.json", prototypes),
                ("private/review_identity_map.json", {r["review_id"]: r for r in rows}),
                ("private/x2_cross_quantity_context.json", context),
                ("tokenizer_binding.json", binding),
                ("representation_policy.json", representation),
            ):
                store.json(name, value)
            store.write(
                "private/isolation_canary.txt",
                b"Private assessment only; no instructions for the Worker.\n",
            )
            store.write("design_at_freeze.md", (root / DOCUMENT).read_bytes())
            store.write("audit.original.txt", audit)
            for task in TASKS:
                store.write(
                    f"public/{task}.json",
                    (root / SOURCE / f"preparation/public/{task}.json").read_bytes(),
                )
            references = [SOURCE + f"/preparation/public/{task}.json" for task in TASKS] + [
                SOURCE + "/preparation/conditions.json",
                SOURCE + "/preparation/private/evaluation_targets.json",
                SOURCE + "/preparation/private/target_class_prototypes.json",
                PREVIOUS + "/closeout/support_selection.json",
                BINDING_PATH,
                PARENT_POLICY_PATH,
            ]
            identities, bundles = [], {}
            for guidance in GENERATION_CONDITIONS:
                files = capsule_files(root, guidance)
                bundles[guidance] = {name: sha(raw) for name, raw in files.items()}
                for name, raw in files.items():
                    store.write(f"worker_code/{guidance}/{name}", raw)
                    references.append(SOURCE + "/preparation/worker_code/N/" + name)
                for task in TASKS:
                    initial = encode(
                        request_body(
                            [
                                {"role": "system", "content": SYSTEMS[guidance]},
                                {
                                    "role": "user",
                                    "content": encode({"task": public[task]}).decode(),
                                },
                            ],
                            MODEL,
                        )
                    )
                    require(len(initial) <= LIMITS["request_bytes"], "prepare.initial_request_fits")
                    store.write(f"initial_requests/{guidance}_{task}.body", initial)
                    identities.append(
                        {
                            "requested_basis": guidance,
                            "task_key": task,
                            "public_reference": reference(
                                root, SOURCE + f"/preparation/public/{task}.json"
                            ),
                            "condition_id": condition(guidance)["id"],
                            "initial_request_sha256": sha(initial),
                            "complete_public_source_bytes_unchanged": True,
                            "only_new_system_suffix_changes_generation_condition": True,
                        }
                    )
            store.json(
                "historical_references.json", [reference(root, p) for p in sorted(set(references))]
            )
            store.json("public_identity_checks.json", identities)
            store.json("worker_bundles.json", bundles)
            store.json(
                "model_contract.json",
                record(
                    "basis_inherited_model_contract",
                    requested_model=MODEL,
                    accepted_response_models=list(ACCEPTED_RESPONSE_MODELS),
                    thinking="enabled",
                    reasoning_effort="high",
                    temperature_top_p="omitted",
                    model_catalog_or_calibration_requests=0,
                    provider_backend_identity_across_dates_claimed=False,
                ),
            )
            checks = subprocess.run(
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
            store.write("controls.stdout", checks.stdout)
            store.write("controls.stderr", checks.stderr)
            store.json(
                "controls.json",
                {
                    "exit_code": checks.returncode,
                    "test_references": [reference(root, path) for path in TESTS],
                    "old_suites_rerun": False,
                    "provider_calls": 0,
                    "real_tokenizer_loads": 0,
                    "Student_runs": 0,
                },
            )
            require(checks.returncode == 0, "prepare.new_controls_before_calls")
            report = record(
                "basis_support_preparation",
                policy_id=sampling["id"],
                target_ledger_ids={task: ledgers[task]["id"] for task in TASKS},
                cross_quantity_context_id=context["id"],
                tokenizer_binding_id=binding["id"],
                representation_policy_id=representation["id"],
                registrations=32,
                implementation_id=frozen["id"],
                old_model_packages_in_new_material=0,
                new_model_requests=0,
                new_tokenizer_calls=0,
                Student_runs=0,
                training_allowed=False,
            )
            store.json("report.json", report)
            store.json("history.json", history_guard(root))
            store.json("execution_guards.json", guard_report(counts, phase="basis_preparation"))
            store.seal(report_id=report["id"])
    return report


def _base(registration):
    return {
        key: registration[key]
        for key in (
            "label",
            "arm",
            "requested_basis",
            "task_key",
            "replicate",
            "review_id",
            "wave",
            "ordinal",
            "condition_id",
        )
    }


def launch_worker(root, registration, key):
    """Run one sealed public capsule; the credential enters only through its inherited FD."""
    root = Path(root)
    output = root / OUTPUT
    prep = output / "preparation"
    frozen = read_json(prep / "registrations.json")
    public = {task: read_json(prep / f"public/{task}.json") for task in TASKS}
    validate_registrations(frozen, public)
    require(registration in frozen, "launch.registered_original_metadata_only")
    label, guidance, task = registration["label"], registration["arm"], registration["task_key"]
    directory = output / "online/sessions" / label
    require(not directory.exists(), "launch.no_session_retry_or_resume")
    read_fd = pipe_credential(key)
    command = [
        WORKER_PYTHON,
        "-I",
        "-S",
        "-B",
        str(prep / f"worker_code/{guidance}/worker.py"),
        "--public",
        str(prep / f"public/{task}.json"),
        "--output",
        str(directory),
        "--model",
        MODEL,
        "--key-fd",
        str(read_fd),
    ]
    for name in PRIVATE_FILES:
        command.extend(["--forbidden", str(prep / "private" / name)])
    try:
        try:
            completed = subprocess.run(
                command,
                cwd=prep / "worker_code" / guidance,
                env={"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8"},
                pass_fds=(read_fd,),
                capture_output=True,
                check=False,
                timeout=32 * 190 + 60,
            )
        except subprocess.TimeoutExpired as error:
            write(output / "online/collector_logs", label + ".stdout", error.stdout or b"")
            write(output / "online/collector_logs", label + ".stderr", error.stderr or b"")
            return {**_base(registration), "terminal": "unknown_worker_timeout", "exit_code": None}
    finally:
        os.close(read_fd)
    write(output / "online/collector_logs", label + ".stdout", completed.stdout)
    write(output / "online/collector_logs", label + ".stderr", completed.stderr)
    if completed.returncode or not (directory / "result.json").exists():
        return {
            **_base(registration),
            "terminal": "unknown_worker_failure",
            "exit_code": completed.returncode,
        }
    result = read_json(directory / "result.json")
    isolation = read_json(directory / "isolation.json")
    sealed = manifest(directory)
    require(
        result["origin"] == "live_http"
        and result["requested_model"] == MODEL
        and result["source_document_sha256"] == sha(encode(public[task]))
        and result["first_final_stops"]
        and not result["history_truncated"]
        and not result["online_answer_feedback"]
        and not result["hidden_evaluator_loaded"]
        and sealed["result_id"] == result["id"],
        "launch.real_frozen_provider_session",
    )
    require(
        isolation["private_read_denied_before_provider"]
        and not isolation["repository_modules_loaded"]
        and isolation["isolated_mode"] == isolation["no_site"] == 1
        and {item["path"] for item in isolation["private_read_probes"]}
        == {str(prep / "private" / name) for name in PRIVATE_FILES}
        and all(item["read_denied"] for item in isolation["private_read_probes"]),
        "launch.public_only_isolation",
    )
    return {
        **_base(registration),
        **{
            field: result[field]
            for field in (
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


def reservation_counts(directory):
    """Count all reserved live requests, including any worker that failed before Final."""
    directory = Path(directory)
    counts, tools = {}, {}
    sessions = directory / "sessions"
    require(
        not sessions.exists() or {path.name for path in sessions.iterdir()} <= set(LABELS),
        "collect.only_registered_session_directories",
    )
    for label in LABELS:
        turns = sessions / label / "turns"
        paths = sorted(turns.glob("*_reservation.json"))
        require(len(paths) <= 32, "collect.session_request_cap")
        for index, path in enumerate(paths):
            value = read_json(path)
            require(
                path.name == f"{index:03d}_reservation.json"
                and value["index"] == index
                and value["provider_call"] is True
                and value["requested_model"] == MODEL,
                "collect.actual_live_contiguous_reservations",
            )
        counts[label] = len(paths)
        tools[label] = len(list(turns.glob("*_tool.json")))
        require(tools[label] <= counts[label] <= 32, "collect.actual_fixed_tool_cap")
    require(sum(counts.values()) <= 1024, "collect.actual_global_request_cap")
    return counts, tools


def collect(root):
    """Two frozen balanced waves; every original outcome remains in the 32 denominator."""
    root = Path(root)
    history_guard(root)
    verify_preparation(root)
    prep = root / OUTPUT / "preparation"
    public = {task: read_json(prep / f"public/{task}.json") for task in TASKS}
    rows = validate_registrations(read_json(prep / "registrations.json"), public)
    store = Store(root / OUTPUT / "online")
    store.json(
        "launch.json",
        record(
            "basis_fixed_launch",
            registrations=rows,
            maximum_provider_requests=1024,
            no_retries_or_resampling=True,
            no_assessment_before_all_32=True,
            old_model_sessions_in_this_batch=0,
            training_allowed=False,
        ),
    )
    started = time.monotonic()
    results, waves = {}, []
    key = credential(root / "trusted_data_synthesis/.env")
    with execution_guard(online=True) as counts:
        try:
            for wave, start, end in ((1, 0, 24), (2, 24, 32)):
                selected = rows[start:end]
                require(all(row["wave"] == wave for row in selected), "collect.fixed_balanced_wave")
                before = time.monotonic()
                with ThreadPoolExecutor(max_workers=WORKERS) as pool:
                    futures = {pool.submit(launch_worker, root, row, key): row for row in selected}
                    for future in as_completed(futures):
                        row = futures[future]
                        try:
                            value = future.result()
                        except Exception as error:
                            value = {
                                **_base(row),
                                "terminal": "unknown_collector_failure",
                                "error_type": type(error).__name__,
                            }
                        require(value["label"] == row["label"], "collect.result_registration_join")
                        results[row["label"]] = value
                        print(
                            row["review_id"],
                            value["terminal"],
                            value.get("model_requests"),
                            flush=True,
                        )
                waves.append(
                    {
                        "wave": wave,
                        "submitted": [row["label"] for row in selected],
                        "wall_seconds": time.monotonic() - before,
                        "no_intermediate_review_or_adaptation": True,
                    }
                )
        finally:
            del key
        require(set(results) == set(LABELS), "collect.all_32_terminal_records")
        reservations, tool_calls = reservation_counts(store.root)
        for label, value in results.items():
            if value.get("result_id"):
                require(
                    value["model_requests"] == value["provider_attempts"] == reservations[label]
                    and value["tool_calls"] == tool_calls[label]
                    and 0 <= value["model_responses"] <= reservations[label],
                    "collect.result_actual_reservation_tool_counts",
                )
        report = record(
            "basis_32_collection_report",
            registered=32,
            rows=[results[label] for label in LABELS],
            actual_reservations_by_session=reservations,
            actual_tool_calls_by_session=tool_calls,
            model_requests=sum(reservations.values()),
            wall_seconds=time.monotonic() - started,
            waves=waves,
            all_workers_terminated=True,
            old_sessions_in_this_denominator=0,
            new_model_catalog_or_calibration_calls=0,
            retries_replacements_or_topups=0,
            Student_runs=0,
            tokenizer_calls=0,
            training_allowed=False,
            original_responses_not_reviewed_for_adaptive_sampling=True,
        )
        store.json("report.json", report)
        store.json("execution_guards.json", guard_report(counts, phase="fixed_32_basis_collection"))
    verify_preparation(root)
    store.json("history.json", history_guard(root))
    store.seal(report_id=report["id"])
    return report
