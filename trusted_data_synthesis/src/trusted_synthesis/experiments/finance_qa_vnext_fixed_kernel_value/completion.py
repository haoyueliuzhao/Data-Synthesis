"""Prospective budget amendment: complete only unfinished original slots.

The original registry, completed sessions, qualifications and STOP reports are
immutable. This module records a distinct user-authorized budget amendment and
composes a closed collection without treating its stopped parent as a PASS.
"""

import argparse
import copy
import fcntl
import functools
import json
import os
import subprocess
import sys
import threading
import time
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
from multiprocessing import get_context
from pathlib import Path

from . import completion_budget as budget
from . import completion_transport as continued
from . import distribution, execution, materials, preflight, publish, study, transport
from . import protocol as p

BRANCH = "codex/fixed-kernel-completion-20260914"
PARENT_COMMIT = "ce53a4bcf0b6668d8978b30eb40d1db88f3de930"
PARENT_ROOT = Path("/tmp/data-synthesis-fixed-kernel-recovery-SQLwriter-20260913")
OUTPUT = (
    "trusted_data_synthesis/artifacts/qa_vnext_fixed_kernel_value/study_20260914_budget_completion"
)
RUNTIME = "trusted_data_synthesis/runtime/fixed_kernel_completion_20260914"
DATA_ROOT = Path("/data1/zhuxinrui/projects/Data-Synthesis")
PARENT_OUTPUT = PARENT_ROOT / p.OUTPUT
ORIGINAL_FREEZE = "study_freeze:f4eb84ee8adacce1d4253086e8fc6443e882dc5ff6dc192b8c02b0a6e2475084"
PARENT_GENERATION = (
    "material_generation_report:a1f920300adbc613dfeb026cd9600a679eadee7dfcdc55476191caef5ec71f1f"
)
PARENT_CODE = "study_code_snapshot:db0d0430c73eb8ebf59b864ea5c81d6b3c4533fff4734fbef2ec8035842caf3e"
TOTAL_TOKEN_CAP = 350000000
TOKEN_CAP = 109024251
REQUEST_CAP = 8300
EXPECTED_FINISHED = 9968
EXPECTED_SLOTS = 272
EXPECTED_PREFIXES = 404
_ASSESS = None


def root_path():
    return Path(__file__).resolve().parents[5]


def descriptor(path, base):
    path = Path(path)
    p.require(path.is_file() and not path.is_symlink(), "completion.regular_evidence")
    return {
        "path": str(path.relative_to(base)),
        "sha256": p.sha(path),
        "bytes": path.stat().st_size,
    }


def read_reference(reference, base):
    relative = Path(reference["path"])
    p.require(
        not relative.is_absolute() and ".." not in relative.parts, "completion.relative_original"
    )
    path = Path(base) / relative
    p.require(path.is_file() and not path.is_symlink(), "completion.regular_original")
    raw = path.read_bytes()
    p.require(p.sha(raw) == reference["sha256"], "completion.original_SHA")
    value = json.loads(raw)
    p.require(value["id"] == reference["id"], "completion.original_identity")
    return value


def reference(value, path, base):
    return {
        "path": str(path.relative_to(base)),
        "sha256": p.sha(p.encode(value)),
        "id": value["id"],
    }


def lineage_bindings(results, code_id):
    """Preserve assessor identities; this neither regrades nor rewrites them."""
    return {
        row["session_id"]: p.record(
            "material_qualification_lineage_binding",
            registered_session_id=row["session_id"],
            material_session_id=row["session"]["id"],
            qualification_id=row["qualification"]["id"],
            code_snapshot_id=code_id,
        )
        for row in results
        if row["status"] == "finished"
    }


def select_slots(registry, results, journal):
    """Selection depends only on closure, never correctness, method or role."""
    by_id = {row["session_id"]: row for row in results}
    requests = defaultdict(list)
    for row in journal:
        requests[row["session_id"]].append(row)
    slots = []
    for reg in registry["sessions"]:
        result = by_id[reg["session_id"]]
        if result["status"] == "finished":
            continue
        p.require(
            result["status"] in {"budget_aborted", "not_run"}, "completion.only_unfinished_slots"
        )
        prefix = sorted(requests[reg["session_id"]], key=lambda row: row["attempt"])
        p.require(
            all(
                row["state"] == "settled"
                and row["http_success"] == 1
                and row["outcome"] == "public_response_received"
                and row["response_model"] == p.MODEL
                and row["attempt"] == index + 1
                for index, row in enumerate(prefix)
            ),
            "completion.no_retry_of_failed_unknown_or_inflight_prefix",
        )
        p.require(len(prefix) < p.MAX_RESPONSES, "completion.original_response_limit")
        slots.append(
            {
                "registered_session": reg,
                "parent_status": result["status"],
                "parent_session": result.get("session"),
                "parent_qualification": result.get("qualification"),
                "prefix_count": len(prefix),
                "prefix_request_ids": [row["request_id"] for row in prefix],
            }
        )
    return slots


def _guard_root(root):
    root = Path(root).resolve()
    p.require(
        root == root_path() and root != PARENT_ROOT and root != DATA_ROOT,
        "completion.isolated_root",
    )
    branch = subprocess.check_output(
        ["git", "branch", "--show-current"], cwd=root, text=True
    ).strip()
    p.require(branch == BRANCH, "completion.successor_branch")
    return root


def prepare(root):
    root = _guard_root(root)
    output = root / OUTPUT
    p.require(not output.exists(), "completion.one_prospective_prepare")
    parent_generation = p.checked(
        p.read_json(PARENT_OUTPUT / "generation_report.json"), "material_generation_report"
    )
    parent_final = p.checked(
        p.read_json(PARENT_OUTPUT / "budget_finalization.json"), "kernel_budget_finalization"
    )
    p.require(
        parent_generation["id"] == PARENT_GENERATION
        and parent_generation["generation_closed"]
        and parent_generation["no_inflight_requests"]
        and parent_final["purpose_closed"]
        and parent_final["report_id"] == PARENT_GENERATION,
        "completion.closed_stopped_parent",
    )
    registry = p.read_json(PARENT_OUTPUT / "registry.json")
    selected = p.read_json(PARENT_OUTPUT / "population.json")
    p.validate_registry(registry, selected, ORIGINAL_FREEZE)
    results = p.read_json(PARENT_OUTPUT / "session_results.json")
    journal = p.read_json(PARENT_OUTPUT / "material_request_journal.json")
    slots = select_slots(registry, results, journal)
    bindings = lineage_bindings(results, PARENT_CODE)
    p.require(
        len(bindings) == EXPECTED_FINISHED
        and len(slots) == EXPECTED_SLOTS
        and sum(row["prefix_count"] for row in slots) == EXPECTED_PREFIXES
        and sum(p.MAX_RESPONSES - row["prefix_count"] for row in slots) == REQUEST_CAP,
        "completion.exact_non_outcome_selected_remaining_matrix",
    )
    authorization = p.record(
        "kernel_completion_authorization",
        user_directive="提高预算，完成完整采集，进行正式训练",
        followup_directive="减少冗余校验，尽快实验",
        original_combined_token_cap=250000000,
        amended_combined_token_cap=TOTAL_TOKEN_CAP,
        prior_first_batch_charge=1269703,
        prior_recovery_conservative_charge=239706046,
        prior_recovery_unknown_charge_retained=578560,
        new_purpose_token_cap=TOKEN_CAP,
        new_HTTP_request_cap=REQUEST_CAP,
        common_token_cap=p.COMMON_CAP,
        already_finished_retained=EXPECTED_FINISHED,
        unfinished_slots=EXPECTED_SLOTS,
        authenticated_prefix_responses=EXPECTED_PREFIXES,
        old_requests_resent=0,
        scientific_tasks_roles_marginals_and_training_parameters_changed=False,
        amendment_after_parent_budget_stop=True,
        unamended_preregistration_claimed=False,
        original_STOP_reports_or_closed_purposes_reopened=False,
        GPU_engineering_checks_reused_not_repeated=True,
        time=p.now(),
    )
    manifest = p.record(
        "kernel_completion_manifest",
        original_freeze_id=ORIGINAL_FREEZE,
        parent_report_id=PARENT_GENERATION,
        parent_registry_id=registry["id"],
        authorization_id=authorization["id"],
        slots=slots,
        token_cap=TOKEN_CAP,
        request_cap=REQUEST_CAP,
        common_cap=p.COMMON_CAP,
        selected_only_by_original_terminal_status=True,
    )
    files = (
        "freeze.json",
        "registry.json",
        "population.json",
        "policy.json",
        "checkpoint_binding.json",
        "tokenizer_binding_preflight.json",
    )
    parent_files = files + (
        "session_results.json",
        "material_request_journal.json",
        "generation_report.json",
        "budget_finalization.json",
        "code_snapshot.json",
        "wallet_after_generation.json",
    )
    parent_binding = p.record(
        "completion_parent_binding",
        root=str(PARENT_ROOT),
        raw_directory=str(PARENT_OUTPUT),
        commit=PARENT_COMMIT,
        original_freeze_id=ORIGINAL_FREEZE,
        generation_report_id=PARENT_GENERATION,
        files=[descriptor(PARENT_OUTPUT / name, PARENT_OUTPUT) for name in parent_files],
        original_failure_retained=True,
        parent_transport_originals_publication_id=p.read_json(
            PARENT_ROOT / (p.OUTPUT + "_publication") / "materials/publication_manifest.json"
        )["id"],
        parent_transport_originals_rearchived_or_regenerated=False,
    )
    code = study.code_snapshot(root)
    scientific = (
        "protocol.py",
        "runtime.py",
        "transport.py",
        "semantic_mapping.py",
        "source_boundary.py",
        "population.py",
        "distribution.py",
        "consumer.py",
        "training.py",
        "evaluation.py",
        "execution.py",
    )
    scientific_binding = []
    for name in scientific:
        old, new = PARENT_ROOT / p.PACKAGE / name, root / p.PACKAGE / name
        p.require(p.sha(old) == p.sha(new), "completion.unchanged_scientific_rule:" + name)
        scientific_binding.append({"path": p.PACKAGE + "/" + name, "sha256": p.sha(new)})
    lineage_record = p.record("completion_qualification_lineage", bindings=bindings)
    freeze = p.record(
        "kernel_completion_freeze",
        original_freeze_id=ORIGINAL_FREEZE,
        registry_id=registry["id"],
        population_id=selected["id"],
        parent_binding_id=parent_binding["id"],
        authorization_id=authorization["id"],
        manifest_id=manifest["id"],
        code_snapshot_id=code["id"],
        qualification_lineage_id=lineage_record["id"],
        scientific_binding=scientific_binding,
        output_directory=OUTPUT,
        parent_commit=PARENT_COMMIT,
        registered_before_new_HTTP=True,
        old_assessments_recomputed=False,
        created_at=p.now(),
    )
    for name in files:
        p.write_once(output / name, p.read_json(PARENT_OUTPUT / name))
    p.write_once(
        output / "parent_publication_manifest.json",
        p.read_json(
            PARENT_ROOT / (p.OUTPUT + "_publication") / "materials/publication_manifest.json"
        ),
    )
    for name, value in {
        "authorization.json": authorization,
        "completion_manifest.json": manifest,
        "parent_binding.json": parent_binding,
        "completion_code_snapshot.json": code,
        "qualification_lineage.json": lineage_record,
        "completion_freeze.json": freeze,
    }.items():
        p.write_once(output / name, value)
    return freeze


def prepared(root, *, committed=False):
    root = _guard_root(root)
    output = root / OUTPUT
    frozen = p.checked(p.read_json(output / "completion_freeze.json"), "kernel_completion_freeze")
    code = p.checked(p.read_json(output / "completion_code_snapshot.json"), "study_code_snapshot")
    p.require(
        code["id"] == frozen["code_snapshot_id"] and study.code_snapshot(root) == code,
        "completion.frozen_new_code",
    )
    parent = p.checked(p.read_json(output / "parent_binding.json"), "completion_parent_binding")
    p.require(parent["id"] == frozen["parent_binding_id"], "completion.parent_identity")
    for row in parent["files"]:
        p.require(
            descriptor(PARENT_OUTPUT / row["path"], PARENT_OUTPUT) == row,
            "completion.parent_bytes_unchanged",
        )
    manifest = p.checked(
        p.read_json(output / "completion_manifest.json"), "kernel_completion_manifest"
    )
    p.require(manifest["id"] == frozen["manifest_id"], "completion.prospective_manifest")
    if committed:
        for path in [
            output / "completion_freeze.json",
            output / "completion_manifest.json",
            output / "authorization.json",
            output / "qualification_lineage.json",
        ]:
            relative = str(path.relative_to(root))
            p.require(
                path.read_bytes()
                == subprocess.check_output(["git", "show", "HEAD:" + relative], cwd=root),
                "completion.authority_committed_before_HTTP",
            )
        for row in code["members"]:
            p.require(
                p.sha(subprocess.check_output(["git", "show", "HEAD:" + row["path"]], cwd=root))
                == row["sha256"],
                "completion.current_code_committed",
            )
    return frozen, manifest


def _initialize_assessment(fixtures, wallet, completion_id, parent_policy, requests_directory):
    global _ASSESS
    _ASSESS = (
        fixtures,
        budget.CompletionLedger(wallet, completion_id, readonly=True),
        parent_policy,
        Path(requests_directory),
    )


def _assess(path, registered, lineage_path, code_id):
    fixtures, ledger, policy, directory = _ASSESS
    lineage = p.read_json(lineage_path)
    return materials.assess_material(
        p.read_json(path),
        registered,
        fixtures[registered["task_id"]],
        ledger=ledger,
        transport_directory=directory,
        code_snapshot_id=code_id,
        origin_verifier=functools.partial(
            continued.verify_origin,
            parent_output=PARENT_OUTPUT / "requests",
            parent_policy=policy,
            lineage=lineage,
        ),
    )


def _copy_finished(results, output):
    def copy_one(reference_row):
        value = read_reference(reference_row, PARENT_OUTPUT)
        p.write_once(output / reference_row["path"], value)
        return reference_row

    references = [
        row[key]
        for row in results
        if row["status"] == "finished"
        for key in ("session", "qualification")
    ]
    with ThreadPoolExecutor(max_workers=p.CPU_WORKERS) as pool:
        for _ in pool.map(copy_one, references):
            pass


def run(root, *, with_training=True):
    root = _guard_root(root)
    output, work = root / OUTPUT, root / RUNTIME
    frozen, manifest = prepared(root, committed=True)
    work.mkdir(parents=True, exist_ok=True)
    with (work / "owner.lock").open("a+b") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        p.require(
            not (output / "execution_started.json").exists(), "completion.one_shot_no_restart"
        )
        p.write_once(
            output / "execution_started.json",
            p.record(
                "completion_execution_started",
                completion_freeze_id=frozen["id"],
                original_freeze_id=ORIGINAL_FREEZE,
                new_slots=EXPECTED_SLOTS,
                inherited_finished=EXPECTED_FINISHED,
                pid=os.getpid(),
                started_at=p.now(),
                generation_workers=p.WORKERS,
                assessment_workers=p.CPU_WORKERS,
                automatic_retry=False,
            ),
        )
        inputs = preflight.load_inputs(DATA_ROOT)
        p.require(
            inputs["population"] == p.read_json(output / "population.json"),
            "completion.same_original_tasks",
        )
        ledger = budget.CompletionLedger(DATA_ROOT / p.WALLET, frozen["id"], manifest=manifest)
        with ledger.connection(readonly=True) as db:
            before = budget.legacy_snapshot(db)
        p.write_once(output / "legacy_wallet_before.json", before)
        p.write_once(
            output / "budget_registration.json", ledger.register(manifest, legacy_before=before)
        )
        original_results = p.read_json(PARENT_OUTPUT / "session_results.json")
        results = {row["session_id"]: copy.deepcopy(row) for row in original_results}
        parent_journal = p.read_json(PARENT_OUTPUT / "material_request_journal.json")
        parent_requests = defaultdict(list)
        for row in parent_journal:
            parent_requests[row["session_id"]].append(row)
        for values in parent_requests.values():
            values.sort(key=lambda row: row["attempt"])
        stop, monitor_done = threading.Event(), threading.Event()
        mutex, counts, errors = threading.Lock(), Counter(), []
        started = time.monotonic()
        credential = study._credential(DATA_ROOT).decode()

        def progress():
            with mutex:
                current = dict(counts)
            study._progress(
                work / "progress.json",
                {
                    "status": "COMPLETING_ORIGINAL_SLOTS",
                    "inherited_finished": EXPECTED_FINISHED,
                    "registered_total": p.SESSION_CAP,
                    "completion_slots": EXPECTED_SLOTS,
                    "counts": current,
                    "wallet": ledger.snapshot(),
                    "global_stop": stop.is_set(),
                    "elapsed_seconds": time.monotonic() - started,
                    "updated_utc": p.now(),
                },
            )

        def watch():
            while not monitor_done.wait(10):
                progress()

        def generate(slot):
            reg = slot["registered_session"]
            if stop.is_set():
                return None
            parent = (
                read_reference(slot["parent_session"], PARENT_OUTPUT)
                if slot["parent_session"]
                else None
            )
            live = transport.Provider(ledger, reg, output / "requests", credential)

            def provider(messages, context):
                if stop.is_set():
                    raise transport.FatalMaterialError("completion.stopped_before_next_new_HTTP")
                return live(messages, context)

            value = continued.generate(
                reg,
                inputs["fixtures"][reg["task_id"]],
                provider=provider,
                parent_session=parent,
                parent_journal=parent_requests[reg["session_id"]],
                completion_freeze_id=frozen["id"],
                slot_manifest=slot,
            )
            session, lineage = value["session"], value["lineage"]
            if session["global_fatal"]:
                stop.set()
                ledger.halt("completion_runtime_global_fatal:" + reg["session_id"])
            path = output / "sessions" / reg["session_id"] / "session.json"
            lineage_path = path.with_name("completion_lineage.json")
            p.write_once(path, session)
            p.write_once(lineage_path, lineage)
            ledger.finish(reg["session_id"], session["terminal"])
            return reg, session, path, lineage_path

        watcher = threading.Thread(target=watch, daemon=True)
        watcher.start()
        scoring = []
        try:
            with ThreadPoolExecutor(max_workers=1) as inheritance:
                inherited = inheritance.submit(_copy_finished, original_results, output)
                with ProcessPoolExecutor(
                    max_workers=p.CPU_WORKERS,
                    mp_context=get_context("spawn"),
                    initializer=_initialize_assessment,
                    initargs=(
                        inputs["fixtures"],
                        str(ledger.path),
                        frozen["id"],
                        p.read_json(output / "policy.json"),
                        str(output / "requests"),
                    ),
                ) as assessors:
                    with ThreadPoolExecutor(max_workers=p.WORKERS) as generators:
                        futures = {
                            generators.submit(generate, slot): slot for slot in manifest["slots"]
                        }
                        for future in as_completed(futures):
                            slot = futures[future]
                            reg = slot["registered_session"]
                            try:
                                value = future.result()
                                if value is None:
                                    counts["not_requested_after_stop"] += 1
                                    continue
                                _, session, path, lineage_path = value
                                results[reg["session_id"]] = {
                                    "session_id": reg["session_id"],
                                    "status": "budget_aborted"
                                    if session["global_fatal"]
                                    else "finished",
                                    "session": reference(session, path, output),
                                    "qualification": None,
                                    "reason": None,
                                }
                                job = assessors.submit(
                                    _assess,
                                    str(path),
                                    reg,
                                    str(lineage_path),
                                    frozen["code_snapshot_id"],
                                )
                                scoring.append((job, reg))
                                with mutex:
                                    counts["new_session_records"] += 1
                                    counts[session["terminal"]] += 1
                            except Exception as error:
                                stop.set()
                                ledger.halt("completion_worker_failure:" + type(error).__name__)
                                message = str(error).replace(credential, "[REDACTED]")
                                errors.append(
                                    {
                                        "session_id": reg["session_id"],
                                        "type": type(error).__name__,
                                        "message": message[:2000],
                                    }
                                )
                    for job, reg in scoring:
                        try:
                            qualification = job.result()
                            path = output / "sessions" / reg["session_id"] / "qualification.json"
                            p.write_once(path, qualification)
                            results[reg["session_id"]]["qualification"] = reference(
                                qualification, path, output
                            )
                            counts["new_qualification_records"] += 1
                        except Exception as error:
                            stop.set()
                            ledger.halt("completion_assessment_failure:" + type(error).__name__)
                            errors.append(
                                {
                                    "session_id": reg["session_id"],
                                    "type": type(error).__name__,
                                    "message": str(error)[:2000],
                                }
                            )
                inherited.result()
        finally:
            monitor_done.set()
            watcher.join()
            del credential
        for request in ledger.new_requests():
            if request["state"] == "reserved":
                ledger.cancel_unsent(request["request_id"], "all_completion_workers_closed")
                stop.set()
            elif request["state"] == "sent":
                ledger.settle(
                    request["request_id"], outcome="closed_completion_worker_usage_unknown"
                )
                stop.set()
        for slot in ledger.sessions():
            if slot["state"] != "finished":
                ledger.finish(slot["session_id"], "completion_workers_closed")
        with ledger.connection(readonly=True) as db:
            after = budget.legacy_snapshot(db, before)
        unchanged = before == after
        p.require(unchanged, "completion.old_six_purposes_unchanged")
        prepared(root)
        registry = p.read_json(output / "registry.json")
        ordered = [results[reg["session_id"]] for reg in registry["sessions"]]
        # Parent references for slots not resumed remain explicit old records,
        # copied here only when necessary for a truthful closed failure report.
        for row in ordered:
            for key in ("session", "qualification"):
                ref = row.get(key)
                if ref and not (output / ref["path"]).exists():
                    p.write_once(output / ref["path"], read_reference(ref, PARENT_OUTPUT))
        journal, wallet = ledger.new_requests(), ledger.snapshot()
        p.require(
            not any(row["state"] in {"reserved", "sent"} for row in journal),
            "completion.no_inflight",
        )
        complete = all(
            row["status"] == "finished" and row["session"] and row["qualification"]
            for row in ordered
        )
        contract = unchanged and not errors and not stop.is_set() and not wallet["persisted_stops"]
        files = {
            "session_results.json": ordered,
            "completion_request_journal.json": journal,
            "legacy_wallet_after.json": after,
            "wallet_after_generation.json": wallet,
            "completion_errors.json": errors,
        }
        artifacts = {}
        for name, value in files.items():
            p.write_once(output / name, value)
            artifacts[name] = descriptor(output / name, output)
        report = p.record(
            "material_generation_report",
            freeze_id=ORIGINAL_FREEZE,
            completion_freeze_id=frozen["id"],
            registry_id=registry["id"],
            code_snapshot_id=frozen["code_snapshot_id"],
            parent_generation_report_id=PARENT_GENERATION,
            budget_amendment_id=manifest["authorization_id"],
            generation_closed=True,
            no_inflight_requests=True,
            registered_sessions=p.SESSION_CAP,
            finished_sessions=sum(row["status"] == "finished" for row in ordered),
            unrequested_sessions=sum(row["status"] == "not_run" for row in ordered),
            raw_registry_complete=complete,
            generation_contract_passed=contract,
            status="COMPLETE_FIXED_COLLECTION"
            if complete and contract
            else "STOP_INCOMPLETE_OR_CONTRACT",
            inherited_finished_sessions=EXPECTED_FINISHED,
            newly_generated_session_records=counts["new_session_records"],
            original_session_results_statuses=dict(
                Counter(row["status"] for row in original_results)
            ),
            session_results_statuses=dict(Counter(row["status"] for row in ordered)),
            new_HTTP_request_count=sum(row["state"] != "not_sent" for row in journal),
            actual_HTTP_request_count=len(parent_journal)
            + sum(row["state"] != "not_sent" for row in journal),
            parent_HTTP_not_resent=True,
            parent_usage_unknown_not_retried=True,
            completion_conservative_debit=wallet["completion_conservative_debit"],
            kernel_conservative_debit=239706046 + wallet["completion_conservative_debit"],
            common_conservative_debit=wallet["common_conservative_debit"],
            completion_wallet_snapshot_id=wallet["id"],
            artifacts=artifacts,
            errors=errors,
            counts=dict(counts),
            amended_budget_not_original_preregistration=True,
            old_qualifications_rewritten=False,
            old_reports_relabelled=False,
            GPU_operations=0,
            Student_training_runs=0,
            elapsed_seconds=time.monotonic() - started,
            finished_utc=p.now(),
        )
        p.write_once(output / "generation_report.json", report)
        p.write_once(output / "budget_finalization.json", ledger.finalize(report_id=report["id"]))
    gate = materialize(root)
    if with_training:
        return followthrough(root, gate)
    return gate


def materialize(root):
    root = _guard_root(root)
    output = root / OUTPUT
    frozen, _ = prepared(root)
    generation = p.read_json(output / "generation_report.json")
    final = p.read_json(output / "budget_finalization.json")
    p.require(
        final["purpose_closed"]
        and final["report_id"] == generation["id"]
        and final["completion_freeze_id"] == frozen["id"],
        "completion.closed_budget_before_materialization",
    )
    p.write_once(
        output / "materialization_started.json",
        p.record(
            "completion_materialization_started",
            generation_report_id=generation["id"],
            completion_freeze_id=frozen["id"],
            old_assessments_recomputed=False,
            started_at=p.now(),
        ),
    )
    lineage = p.checked(
        p.read_json(output / "qualification_lineage.json"), "completion_qualification_lineage"
    )
    p.require(
        lineage["id"] == frozen["qualification_lineage_id"],
        "completion.frozen_qualification_lineage",
    )

    registry = p.read_json(output / "registry.json")
    from . import completion_materialize

    index = completion_materialize.materialize_all(
        registry,
        p.read_json(output / "session_results.json"),
        DATA_ROOT,
        output,
        code_snapshot_id=frozen["code_snapshot_id"],
        qualification_lineage_bindings=lineage["bindings"],
        workers=p.CPU_WORKERS,
        collection_gate_passed=generation["status"] == "COMPLETE_FIXED_COLLECTION",
        collection_gate_reason=None
        if generation["status"] == "COMPLETE_FIXED_COLLECTION"
        else "completion_not_closed_successfully",
    )
    outcomes = materials.hydrate_outcomes(index, output)
    kernel = distribution.build_kernel(p.read_json(output / "population.json"), registry, outcomes)
    gate = study._materialization_gate(index, kernel, generation)
    p.write_once(output / "material_gate.json", gate)
    study._progress(
        root / RUNTIME / "progress.json",
        {
            "status": "MATERIAL_GATE_" + gate["training_gate"],
            "gate_id": gate["id"],
            "registered": p.SESSION_CAP,
            "updated_utc": p.now(),
        },
    )
    return gate


def train(root):
    root = _guard_root(root)
    output = root / OUTPUT
    frozen, _ = prepared(root)
    gate = p.checked(p.read_json(output / "material_gate.json"), "material_gate")
    p.require(gate["training_gate"] == "PASS", "completion.original_training_gate_required")
    student = output / "student_execution"
    release = execution.prepare(
        root,
        student,
        source_root=DATA_ROOT,
        study_freeze_id=ORIGINAL_FREEZE,
        population_path=output / "population.json",
        registry_path=output / "registry.json",
        materialization_index_path=output / "materialization_index.json",
        base_binding=p.read_json(output / "checkpoint_binding.json"),
        tokenizer_binding=p.read_json(output / "tokenizer_binding.json"),
    )
    p.write_once(
        student / "preparation/completion_authority.json",
        p.record(
            "completion_formal_training_authority",
            completion_freeze_id=frozen["id"],
            execution_freeze_id=release["id"],
            original_registry_freeze_id=ORIGINAL_FREEZE,
            material_gate_id=gate["id"],
            formal_amended_budget_experiment=True,
            unamended_preregistration_claimed=False,
            engineering_check_repeated=False,
            created_at=p.now(),
        ),
    )
    study._progress(
        root / RUNTIME / "progress.json",
        {
            "status": "FORMAL_STUDENT_EXECUTION",
            "execution_freeze_id": release["id"],
            "updated_utc": p.now(),
        },
    )
    result = execution.run(root, student / "preparation/execution_freeze.json")
    study._progress(
        root / RUNTIME / "progress.json",
        {"status": result["status"], "execution_report_id": result["id"], "updated_utc": p.now()},
    )
    return result


def seal(root, stage):
    root = _guard_root(root)
    output = root / OUTPUT
    if stage == "materials":
        return publish.seal_stage(root, DATA_ROOT, stage, source_output=OUTPUT)
    report = p.checked(p.read_json(output / "student_execution/report.json"), "execution_report")
    p.require(report["actual_complete"] is True, "completion.only_actual_Student_results_sealed")
    decision = p.read_json(output / "student_execution/decision.json")
    jobs = execution.jobs_for("A_train")
    if report["status"] == "COMPLETE_FIXED_CONFIRMATION":
        jobs += execution.jobs_for("B_train", decision["selected_arm"])
    adapters = [
        f"student_execution/training/{job['pool']}_{job['arm']}_{job['seed']}/final_adapter.safetensors"
        for job in jobs
    ]
    return publish.seal_stage(
        root,
        DATA_ROOT,
        "results",
        source_output=OUTPUT,
        allowlist=["student_execution"],
        report_path="student_execution/report.json",
        approved_adapter_paths=adapters,
    )


def followthrough(root, gate):
    """Publication runs beside preparation/training, not as an additional gate."""
    root = _guard_root(root)
    workflow = root / (OUTPUT + "_workflow")
    frozen = p.read_json(root / OUTPUT / "completion_freeze.json")
    started = p.record(
        "completion_workflow_started",
        completion_freeze_id=frozen["id"],
        material_gate_id=gate["id"],
        started_at=p.now(),
        pid=os.getpid(),
        code_snapshot_id=frozen["code_snapshot_id"],
        completion_source_sha256=p.sha(Path(__file__)),
        process_launcher_injected=False,
        automatic_retry=False,
    )
    p.write_once(workflow / "started.json", started)
    jobs, codes, report = {}, {}, None

    def start(stage):
        directory = workflow / "stages" / (stage + "_seal")
        command = [
            sys.executable,
            "-u",
            "-m",
            __package__ + ".completion",
            "--code-root",
            str(root),
            "--phase",
            "seal_" + stage,
        ]
        p.write_once(
            directory / "command.json",
            p.record("completion_stage_command", argv=command, stage=stage),
        )
        stream = (directory / "console.log").open("xb")
        try:
            child = subprocess.Popen(
                command,
                cwd=root,
                stdout=stream,
                stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL,
                start_new_session=True,
            )
        except Exception:
            stream.close()
            codes[stage + "_seal"] = -1
            return
        jobs[stage + "_seal"] = child, stream
        p.write_once(
            directory / "started.json",
            p.record("completion_stage_started", pid=child.pid, started_at=p.now(), stage=stage),
        )

    def finish():
        for stage, (child, stream) in jobs.items():
            code = child.wait()
            stream.close()
            codes[stage] = code
            p.write_once(
                workflow / "stages" / stage / "exit.json",
                p.record("completion_stage_exit", stage=stage, return_code=code, ended_at=p.now()),
            )

    try:
        start("materials")
        if gate["training_gate"] == "PASS":
            report = train(root)
            p.require(
                report["actual_complete"] is True, "completion.actual_formal_execution_required"
            )
            start("results")
        finish()
        status = (
            "STOP_EXISTING_MATERIAL_GATE_FAIL"
            if gate["training_gate"] == "FAIL"
            else (
                "COMPLETE_ACTUAL_EXECUTION_AND_SEALS"
                if all(code == 0 for code in codes.values())
                else "COMPLETE_ACTUAL_EXECUTION_PUBLICATION_FAILED"
            )
        )
        terminal = p.record(
            "completion_workflow_terminal",
            status=status,
            completion_freeze_id=frozen["id"],
            started_id=started["id"],
            code_snapshot_id=frozen["code_snapshot_id"],
            completion_source_sha256=started["completion_source_sha256"],
            material_gate_id=gate["id"],
            actual_execution_complete=bool(report and report["actual_complete"]),
            actual_execution_report_id=report["id"] if report else None,
            child_exit_codes=codes,
            active_child_pids={},
            process_launcher_injected=False,
            ended_at=p.now(),
            automatic_retry=False,
        )
        p.write_once(workflow / "terminal.json", terminal)
        return terminal
    except BaseException as error:
        terminal = p.record(
            "completion_workflow_terminal",
            status="STOP_OPERATOR_OR_CHILD_FAILURE",
            started_id=started["id"],
            code_snapshot_id=frozen["code_snapshot_id"],
            completion_source_sha256=started["completion_source_sha256"],
            completion_freeze_id=frozen["id"],
            material_gate_id=gate["id"],
            actual_execution_complete=bool(report and report["actual_complete"]),
            actual_execution_report_id=report["id"] if report else None,
            child_exit_codes=codes,
            active_child_pids={
                stage: child.pid for stage, (child, _) in jobs.items() if child.poll() is None
            },
            process_launcher_injected=False,
            error_type=type(error).__name__,
            ended_at=p.now(),
            automatic_retry=False,
        )
        p.write_once(workflow / "terminal.json", terminal)
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--code-root", type=Path, default=root_path())
    parser.add_argument(
        "--phase",
        choices=("prepare", "run", "materialize", "train", "seal_materials", "seal_results"),
        required=True,
    )
    parser.add_argument("--collection-only", action="store_true")
    args = parser.parse_args()
    if args.phase.startswith("seal_"):
        result = seal(args.code_root, args.phase.removeprefix("seal_"))
    else:
        function = {"prepare": prepare, "run": run, "materialize": materialize, "train": train}[
            args.phase
        ]
        result = (
            function(args.code_root, with_training=not args.collection_only)
            if args.phase == "run"
            else function(args.code_root)
        )
    print(p.encode(result).decode(), flush=True)


if __name__ == "__main__":
    main()
