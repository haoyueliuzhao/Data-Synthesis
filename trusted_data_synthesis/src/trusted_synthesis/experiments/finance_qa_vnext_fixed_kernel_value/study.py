"""Freeze, close one 10,240-session collection, then materialize without training.

Preparation has no generation or live-wallet mutation. A committed prospective
freeze precedes the fifth-purpose registration, credential read and first HTTP.
Every original session is retained; stopping never permits a successful prefix
to become a scientific training pool. This module has no Student/GPU entry point.
"""

import argparse
import fcntl
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
from importlib import metadata
from multiprocessing import get_context
from pathlib import Path

from ..finance_qa_vnext_basis_student.publication import _credential
from ..finance_qa_vnext_movement_support.run import source_snapshot
from ..finance_qa_vnext_pq_student import model as model_components
from ..qa_reasoning_share_training_preflight import tokenization as tokenizer_assets
from . import budget, distribution, materials, population, preflight, runtime, transport
from . import protocol as p

PROTECTED = (
    "/data1/zhuxinrui/projects/Data-Synthesis",
    "/tmp/data-synthesis-anchored-vtdo-MaNMFd",
    "/tmp/data-synthesis-hierarchical-loss-yvab69o2",
    "/tmp/data-synthesis-movement-support-se2ytr1a",
    "/tmp/data-synthesis-probe-coverage-uPr3h7",
)
BASE_PREFIXES = (
    "trusted_data_synthesis/src",
    "trusted_data_synthesis/tests",
    "trusted_data_synthesis/config",
    "trusted_data_synthesis/scripts",
    "trusted_data_synthesis/pyproject.toml",
    "raw_financial_data_lake/finraw",
)
_ASSESS_FIXTURES = None


def git(root, *arguments):
    return subprocess.check_output(["git", "-C", str(root), *arguments])


def guarded_roots(code_root, data_root):
    code_root, data_root = Path(code_root).resolve(), Path(data_root).resolve()
    p.require(
        code_root != data_root and Path(__file__).resolve().is_relative_to(code_root),
        "study.independent_code_worktree",
    )
    p.require(
        git(code_root, "branch", "--show-current").decode().strip() == p.BRANCH,
        "study.dedicated_branch",
    )
    p.require(
        git(data_root, "branch", "--show-current").decode().strip() == "main"
        and git(data_root, "rev-parse", "HEAD").decode().strip() == p.MAIN_COMMIT,
        "study.main_not_changed",
    )
    p.require(
        git(code_root, "rev-parse", "--path-format=absolute", "--git-common-dir")
        == git(data_root, "rev-parse", "--path-format=absolute", "--git-common-dir"),
        "study.same_project_common_git",
    )
    output, work = code_root / p.OUTPUT, code_root / p.RUNTIME
    for path in (output, work):
        p.require(
            path.resolve().is_relative_to(code_root)
            and not any(item.is_symlink() for item in (path, *path.parents)),
            "study.isolated_regular_output",
        )
    return code_root, data_root, output, work


def code_snapshot(root):
    root = Path(root)
    paths = sorted((root / p.PACKAGE).glob("*.py"))
    paths += sorted((root / "trusted_data_synthesis/tests").glob("test_qa_vnext_fixed_kernel*.py"))
    p.require(
        paths and all(path.is_file() and not path.is_symlink() for path in paths),
        "study.regular_complete_new_code",
    )
    return p.record(
        "study_code_snapshot",
        parent_commit=p.BASE_COMMIT,
        members=[{"path": str(path.relative_to(root)), "sha256": p.sha(path)} for path in paths],
    )


def base_dependencies(root):
    names = [
        name
        for name in git(
            root, "ls-tree", "-r", "--name-only", "-z", p.BASE_COMMIT, "--", *BASE_PREFIXES
        )
        .decode()
        .split("\0")
        if name
    ]
    p.require(names, "study.original_dependencies_present")
    raw = subprocess.run(
        ["git", "-C", str(root), "cat-file", "--batch"],
        input="".join(p.BASE_COMMIT + ":" + name + "\n" for name in names).encode(),
        capture_output=True,
        check=True,
    ).stdout
    members, offset = [], 0
    for name in names:
        end = raw.index(b"\n", offset)
        _, kind, size = raw[offset:end].decode().split()
        p.require(kind == "blob", "study.original_git_blob")
        size = int(size)
        body = raw[end + 1 : end + 1 + size]
        offset = end + size + 2
        path = Path(root) / name
        p.require(
            len(body) == size
            and raw[offset - 1 : offset] == b"\n"
            and path.is_file()
            and not path.is_symlink()
            and path.read_bytes() == body,
            "study.original_dependency_unchanged:" + name,
        )
        members.append({"path": name, "sha256": p.sha(body)})
    p.require(offset == len(raw), "study.complete_original_git_batch")
    return p.record("original_code_dependencies", parent_commit=p.BASE_COMMIT, members=members)


def verify_code(root, code, original):
    p.checked(code, "study_code_snapshot")
    p.checked(original, "original_code_dependencies")
    p.require(code_snapshot(root) == code, "study.frozen_new_code_bytes")
    p.require(
        all(p.sha(Path(root) / row["path"]) == row["sha256"] for row in original["members"]),
        "study.frozen_original_code_bytes",
    )


def _junit(path):
    path = Path(path)
    suites = list(ET.parse(path).iter("testsuite"))
    counts = {
        key: sum(int(suite.attrib.get(key, 0)) for suite in suites)
        for key in ("tests", "failures", "errors", "skipped")
    }
    p.require(
        counts["tests"] > 0 and not any(counts[key] for key in ("failures", "errors", "skipped")),
        "study.all_CPU_controls_passed_without_skips",
    )
    return p.record(
        "CPU_test_evidence",
        source_path=str(path.resolve()),
        sha256=p.sha(path),
        **counts,
        seconds=sum(float(s.attrib.get("time", 0)) for s in suites),
        tests_reexecuted_by_prepare=False,
    )


def _wallet_before(data_root):
    ledger = budget.KernelLedger(Path(data_root) / p.WALLET, "unregistered_read_only_preparation")
    with ledger.connection(readonly=True) as db:
        db.execute("BEGIN")
        before = budget.legacy_snapshot(db)
        p.require(
            not db.execute(
                "SELECT 1 FROM metadata WHERE key IN ('study_fatal',?)", (budget.PURPOSE,)
            ).fetchone(),
            "study.fresh_open_common_wallet",
        )
        for table in budget.OLD_RESERVATIONS:
            p.require(
                not db.execute(
                    f"SELECT 1 FROM {table} WHERE state IN ('reserved','sent')"
                ).fetchone(),
                "study.no_old_inflight_requests",
            )
        common = db.execute("SELECT COALESCE(SUM(tokens),0) FROM prior_debits").fetchone()[0]
        common += sum(
            db.execute(f"SELECT COALESCE(SUM(charged_tokens),0) FROM {table}").fetchone()[0]
            for table in budget.OLD_RESERVATIONS
        )
        db.execute("ROLLBACK")
    p.require(
        common + p.REQUEST_RESERVATION * p.WORKERS <= p.COMMON_CAP,
        "study.remaining_common_room_for_registered_initial_concurrency",
    )
    return before, common


def _shadow_evidence(path, before):
    value = p.checked(p.read_json(path), "wallet_shadow_control")
    p.require(
        value["status"] == "PASS_SYNTHETIC_SHADOW_ONLY"
        and value["source_legacy_snapshot_before"] == before
        and value["source_legacy_snapshot_after"] == before
        and value["source_wallet_modified"] is False
        and value["source_new_purpose_registered"] is False
        and value["live_API_calls"] == value["live_new_tokens"] == 0,
        "study.exact_real_wallet_shadow_only_evidence",
    )
    shadow = Path(value["shadow_wallet"])
    with sqlite3.connect(shadow.as_uri() + "?mode=ro", uri=True) as db:
        registration = p.checked(
            json.loads(
                db.execute("SELECT value FROM metadata WHERE key=?", (budget.PURPOSE,)).fetchone()[
                    0
                ]
            ),
            "kernel_budget_registration",
        )
    p.require(
        registration["policy_id"] == p.policy()["id"]
        and registration["legacy_snapshot_id"] == before["id"],
        "study.shadow_matches_current_policy_and_prior",
    )
    return p.record(
        "shadow_evidence_import",
        source_path=str(Path(path).resolve()),
        source_sha256=p.sha(Path(path)),
        evidence=value,
        shadow_registration=registration,
        real_API_calls=0,
    )


def _gpu_evidence(paths, code_root):
    p.require(paths, "study.real_GPU_engineering_evidence_required")
    values = []
    for path in paths:
        path = Path(path)
        report = p.checked(p.read_json(path), "gpu_engineering_report")
        started = p.checked(p.read_json(path.parent / "started.json"), "gpu_engineering_started")
        p.require(
            report["status"] == "PASS_ENGINEERING_ONLY"
            and report["scientific_training"] is False
            and report["formal_materials_consumed"] == report["scientific_student_updates"] == 0
            and report["adapter_or_optimizer_checkpoint_saved"] is False
            and report["production_initialization_reused"] is False,
            "study.engineering_not_formal_training",
        )
        p.require(
            all(
                p.sha(Path(code_root) / p.PACKAGE / name) == digest
                for name, digest in started["source_code_sha256"].items()
            ),
            "study.engineering_bound_current_consumer_code",
        )
        values.append(
            {
                "source_path": str(path.resolve()),
                "sha256": p.sha(path),
                "report": report,
                "started": started,
            }
        )
    return p.record(
        "GPU_engineering_evidence",
        reports=values,
        formal_model_state_reused=False,
        GPU_operations_by_prepare=0,
    )


def _assets(data_root):
    checkpoint = model_components.bind_checkpoint()
    tokenizer, unused = materials.load_local_tokenizer(data_root)
    del unused
    return checkpoint, tokenizer


def _verify_assets(checkpoint, tokenizer, data_root):
    model_components.verify_checkpoint(checkpoint)
    members, _ = tokenizer_assets._read_members(Path(tokenizer["directory"]))
    p.require(
        members == tokenizer["members"]
        and tokenizer_assets._configuration_reference(Path(data_root).resolve())
        == tokenizer["source_configuration"],
        "study.frozen_tokenizer_assets",
    )


def _write_bytes(path, raw):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())


def prepare(
    code_root,
    data_root,
    *,
    junit_path,
    shadow_path,
    gpu_reports,
    model_preflight_path=None,
    control_workers=p.CPU_WORKERS,
):
    code_root, data_root, output, work = guarded_roots(code_root, data_root)
    p.require(not (output / "freeze.json").exists(), "study.new_prospective_freeze_only")
    tests = _junit(junit_path)
    code, original = code_snapshot(code_root), base_dependencies(code_root)
    inputs = preflight.load_inputs(data_root)
    controls = preflight.scripted_controls(inputs, workers=control_workers)
    p.require(
        controls["status"] == "PASS" and controls["passed_control_count"] == 560,
        "study.complete_560_scripted_controls",
    )
    protected = [source_snapshot(Path(root)) for root in PROTECTED]
    before, common = _wallet_before(data_root)
    shadow = _shadow_evidence(shadow_path, before)
    gpu = _gpu_evidence(gpu_reports, code_root)
    api_path = (
        Path(model_preflight_path)
        if model_preflight_path
        else work / "official_model_preflight.json"
    )
    api = p.checked(p.read_json(api_path), "official_model_preflight")
    p.require(
        api["HTTP_status"] == 200
        and api["administrative_GET_requests"] == 1
        and api["model_generation_requests"] == 0
        and p.MODEL in api["model_ids"]
        and api["credential_saved"] is False,
        "study.one_saved_official_model_GET",
    )
    audit_bytes = Path(p.AUDIT_PATH).read_bytes()
    audit = p.record(
        "audit_directive",
        attachment_path=p.AUDIT_PATH,
        original_bytes_sha256=p.sha(audit_bytes),
        complete_text=audit_bytes.decode("utf-8"),
        current_user_directive=p.DIRECTIVE,
        linked_audit_artifacts_replayed=False,
        external_59_controls_rerun=False,
    )
    checkpoint, tokenizer = _assets(data_root)
    p.require(
        all(row["report"]["checkpoint_binding_id"] == checkpoint["id"] for row in gpu["reports"]),
        "study.GPU_and_future_Student_same_base",
    )
    verify_code(code_root, code, original)
    p.require(
        [source_snapshot(Path(root)) for root in PROTECTED] == protected,
        "study.protected_sources_unchanged_during_preparation",
    )
    artifacts = {
        "policy.json": p.policy(),
        "population.json": inputs["population"],
        "source_dependencies.json": inputs["source_dependencies"],
        "source_evidence.json": inputs["source_evidence"],
        "input_boundary_manifest.json": inputs["boundary_manifest"],
        "code_snapshot.json": code,
        "original_code_dependencies.json": original,
        "protected_sources_before.json": protected,
        "legacy_wallet_before.json": before,
        "budget_shadow_evidence.json": shadow,
        "GPU_engineering_evidence.json": gpu,
        "official_model_preflight.json": api,
        "audit_directive.json": audit,
        "CPU_test_evidence.json": tests,
        "scripted_preflight.json": controls,
        "checkpoint_binding.json": checkpoint,
        "tokenizer_binding_preflight.json": tokenizer,
    }
    members = {
        name: {
            "sha256": p.sha(p.encode(value)),
            "id": value.get("id") if isinstance(value, dict) else None,
        }
        for name, value in artifacts.items()
    }
    members["cpu_tests.xml"] = {"sha256": tests["sha256"], "id": None}
    freeze = p.record(
        "study_freeze",
        policy_id=p.policy()["id"],
        population_id=inputs["population"]["id"],
        code_snapshot_id=code["id"],
        original_code_dependencies_id=original["id"],
        source_dependencies_id=inputs["source_dependencies"]["id"],
        boundary_manifest_id=inputs["boundary_manifest"]["id"],
        source_evidence_id=inputs["source_evidence"]["id"],
        legacy_wallet_before_id=before["id"],
        common_conservative_debit_before=common,
        remaining_common_allowance_before=p.COMMON_CAP - common,
        material_token_cap=p.TOKEN_CAP,
        registered_sessions=p.SESSION_CAP,
        model=p.MODEL,
        assignment_order_seed=p.ORDER_SEED,
        artifacts=members,
        software={
            "python": sys.version,
            **{
                name: metadata.version(name)
                for name in (
                    "sympy",
                    "httpx",
                    "transformers",
                    "tokenizers",
                    "torch",
                    "pyarrow",
                    "safetensors",
                )
            },
        },
        generation_requests_before_freeze=0,
        live_wallet_mutations_by_prepare=0,
        Student_or_GPU_operations_by_prepare=0,
        new_independent_population_not_old_AB=True,
        registry_roles_precede_all_outputs=True,
    )
    registry = population.make_registry(inputs["population"], freeze["id"], p.ORDER_SEED)
    for name, value in artifacts.items():
        p.write_once(output / name, value)
    xml = Path(junit_path).read_bytes()
    if Path(junit_path).resolve() != (output / "cpu_tests.xml").resolve():
        _write_bytes(output / "cpu_tests.xml", xml)
    p.write_once(output / "freeze.json", freeze)
    p.write_once(output / "registry.json", registry)
    return freeze


def _load_prepared(output):
    freeze = p.checked(p.read_json(output / "freeze.json"), "study_freeze")
    p.require(freeze["policy_id"] == p.policy()["id"], "study.same_frozen_policy")
    for name, descriptor in freeze["artifacts"].items():
        path = output / name
        p.require(
            path.is_file() and not path.is_symlink() and p.sha(path) == descriptor["sha256"],
            "study.frozen_preparation_artifact:" + name,
        )
    selected = p.read_json(output / "population.json")
    registry = p.read_json(output / "registry.json")
    p.validate_registry(registry, selected, freeze["id"])
    p.require(selected["id"] == freeze["population_id"], "study.frozen_population_join")
    return freeze, selected, registry


def _verify_launch(code_root, data_root, output, *, require_unregistered_wallet):
    freeze, selected, registry = _load_prepared(output)
    code = p.read_json(output / "code_snapshot.json")
    original = p.read_json(output / "original_code_dependencies.json")
    verify_code(code_root, code, original)
    p.require(
        code["id"] == freeze["code_snapshot_id"]
        and original["id"] == freeze["original_code_dependencies_id"],
        "study.freeze_code_join",
    )
    names = [*freeze["artifacts"], "freeze.json", "registry.json"]
    for name in names:
        p.require(
            git(code_root, "show", "HEAD:" + p.OUTPUT + "/" + name) == (output / name).read_bytes(),
            "study.preparation_committed_before_HTTP:" + name,
        )
    for row in code["members"]:
        p.require(
            p.sha(git(code_root, "show", "HEAD:" + row["path"])) == row["sha256"],
            "study.executed_new_code_committed_before_HTTP",
        )
    protected = [source_snapshot(Path(root)) for root in PROTECTED]
    p.require(
        protected == p.read_json(output / "protected_sources_before.json"),
        "study.five_protected_worktrees_unchanged",
    )
    inputs = preflight.load_inputs(data_root)
    p.require(
        inputs["population"] == selected
        and inputs["source_dependencies"]["id"] == freeze["source_dependencies_id"]
        and inputs["source_evidence"]["id"] == freeze["source_evidence_id"]
        and inputs["boundary_manifest"]["id"] == freeze["boundary_manifest_id"],
        "study.revalidated_original_and_enriched_source_inputs",
    )
    _verify_assets(
        p.read_json(output / "checkpoint_binding.json"),
        p.read_json(output / "tokenizer_binding_preflight.json"),
        data_root,
    )
    if require_unregistered_wallet:
        before, common = _wallet_before(data_root)
        p.require(
            before == p.read_json(output / "legacy_wallet_before.json")
            and common == freeze["common_conservative_debit_before"],
            "study.real_wallet_still_matches_prospective_snapshot",
        )
    return freeze, selected, registry, inputs, code, original


def _progress(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix="kernel_progress_", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(p.encode(value))
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if Path(temporary).exists():
            Path(temporary).unlink()


def _reference(path, output, identifier=None):
    return {"path": str(path.relative_to(output)), "sha256": p.sha(path), "id": identifier}


def _read_reference(reference, output):
    path = output / reference["path"]
    p.require(
        not Path(reference["path"]).is_absolute()
        and ".." not in Path(reference["path"]).parts
        and path.is_file()
        and not any(item.is_symlink() for item in (path, *path.parents))
        and p.sha(path) == reference["sha256"],
        "study.exact_original_session_artifact",
    )
    value = p.read_json(path)
    p.require(reference["id"] == value["id"], "study.referenced_original_identity")
    return value


def _initialize_assessment(fixtures):
    global _ASSESS_FIXTURES
    _ASSESS_FIXTURES = fixtures


def _assess_job(session_path, registered, ledger_path, freeze_id, requests_directory, code_id):
    ledger = budget.KernelLedger(ledger_path, freeze_id)
    session = p.read_json(session_path)
    return materials.assess_material(
        session,
        registered,
        _ASSESS_FIXTURES[registered["task_id"]],
        ledger=ledger,
        transport_directory=requests_directory,
        code_snapshot_id=code_id,
    )


def collect_registered(
    ledger,
    registry,
    fixtures,
    output,
    work,
    code_id,
    credential,
    *,
    generation_workers=p.WORKERS,
    assessment_workers=p.CPU_WORKERS,
    provider_factory=None,
    generator=None,
    assessor=None,
    processes=True,
):
    """Bounded core, injectable only for explicitly synthetic CPU controls."""
    synthetic = provider_factory is not None or generator is not None or assessor is not None
    provider_factory = transport.Provider if provider_factory is None else provider_factory
    generator = runtime.generate if generator is None else generator
    assessor = _assess_job if assessor is None else assessor
    registrations = registry["sessions"]
    p.require(len(registrations) == p.SESSION_CAP, "study.full_generation_denominator")
    stop, progress_done, mutex, progress_mutex = (
        threading.Event(),
        threading.Event(),
        threading.Lock(),
        threading.Lock(),
    )
    started, counts, errors = time.monotonic(), Counter(), []
    results = [
        {
            "session_id": row["session_id"],
            "status": "not_run",
            "session": None,
            "qualification": None,
            "reason": "not_requested_after_global_stop",
        }
        for row in registrations
    ]

    def fail(reg, error, scope):
        stop.set()
        message = str(error).replace(credential, "[REDACTED]") if credential else str(error)
        failure = p.record(
            "collection_failure",
            scope=scope,
            session_id=reg["session_id"] if reg else None,
            error_type=type(error).__name__,
            reason=message[:4000],
            raw_originals_not_discarded=True,
            automatic_retry=False,
        )
        ledger.halt(scope + ":" + type(error).__name__)
        with mutex:
            errors.append(failure)
            if reg is not None:
                results[reg["ordinal"]].update(
                    status="failed", reason=scope + ":" + type(error).__name__
                )
        if reg is not None:
            path = output / "sessions" / reg["session_id"] / (scope + "_failure.json")
            p.write_once(path, failure)

    def progress():
        with mutex:
            current = dict(counts)
        with progress_mutex:
            _progress(
                work / "progress.json",
                {
                    "registered": len(registrations),
                    "counts": current,
                    "elapsed_seconds": time.monotonic() - started,
                    "wallet": ledger.snapshot(),
                    "global_stop": stop.is_set(),
                    "updated_utc": p.now(),
                },
            )

    def monitor():
        while not progress_done.wait(10):
            try:
                progress()
            except Exception as error:
                fail(None, error, "progress")
                return

    def generate_one(reg):
        if stop.is_set():
            return None
        fixture = fixtures[reg["task_id"]]
        actual = provider_factory(ledger, reg, output / "requests", credential)

        def provider(messages, context):
            if stop.is_set():
                raise transport.FatalMaterialError("study.stopped_before_next_HTTP_request")
            try:
                return actual(messages, context)
            except Exception as error:
                if runtime.global_failure(error):
                    stop.set()
                raise

        session = generator(
            fixture["messages"], fixture["identity"], provider=provider, registered=reg
        )
        if session["global_fatal"]:
            stop.set()
            ledger.halt("runtime_global_fatal:" + reg["session_id"])
        path = output / "sessions" / reg["session_id"] / "session.json"
        p.write_once(path, session)
        ledger.finish(reg["session_id"], session["terminal"])
        return session, path

    scoring_jobs = []
    if processes:
        scoring_pool = ProcessPoolExecutor(
            max_workers=assessment_workers,
            mp_context=get_context("spawn"),
            initializer=_initialize_assessment,
            initargs=(fixtures,),
        )
    else:
        _initialize_assessment(fixtures)
        scoring_pool = ThreadPoolExecutor(max_workers=assessment_workers)
    watcher = threading.Thread(target=monitor, daemon=True)
    watcher.start()
    try:
        with scoring_pool as scoring:
            with ThreadPoolExecutor(max_workers=generation_workers) as generation:
                jobs = {generation.submit(generate_one, reg): reg for reg in registrations}
                for future in as_completed(jobs):
                    reg = jobs[future]
                    try:
                        value = future.result()
                        if value is None:
                            with mutex:
                                counts["not_run"] += 1
                        else:
                            session, path = value
                            with mutex:
                                results[reg["ordinal"]].update(
                                    status="budget_aborted"
                                    if session["global_fatal"]
                                    else "finished",
                                    session=_reference(path, output, session["id"]),
                                    reason=None,
                                )
                                counts["session_records"] += 1
                                counts[session["terminal"]] += 1
                            scored = scoring.submit(
                                assessor,
                                str(path),
                                reg,
                                str(ledger.path),
                                registry["freeze_id"],
                                str(output / "requests"),
                                code_id,
                            )
                            completed = threading.Event()

                            def accept(done, registration=reg, completion=completed):
                                try:
                                    qualification = done.result()
                                    p.checked(qualification, "material_qualification")
                                    qpath = (
                                        output
                                        / "sessions"
                                        / registration["session_id"]
                                        / "qualification.json"
                                    )
                                    p.write_once(qpath, qualification)
                                    with mutex:
                                        results[registration["ordinal"]]["qualification"] = (
                                            _reference(qpath, output, qualification["id"])
                                        )
                                        counts["qualification_records"] += 1
                                except Exception as error:
                                    fail(registration, error, "assessment")
                                finally:
                                    completion.set()

                            scored.add_done_callback(accept)
                            scoring_jobs.append((scored, completed))
                    except Exception as error:
                        fail(reg, error, "generation")
                    with mutex:
                        counts["generator_futures_closed"] += 1
                        checkpoint = counts["generator_futures_closed"] % 32 == 0
                    if checkpoint:
                        progress()
            for future, completion in scoring_jobs:
                try:
                    future.result()
                except Exception:
                    pass  # The callback records the typed error and stops collection.
                completion.wait()
    finally:
        progress_done.set()
        watcher.join()
    # Once all send-capable threads have joined, an orphan reserved lease is
    # proven unsent; an orphan sent lease is unknown and remains fully charged.
    by_id = {row["session_id"]: row for row in registrations}
    for request in ledger.requests():
        if request["state"] in {"reserved", "sent"}:
            reg = by_id[request["session_id"]]
            fail(reg, RuntimeError("orphan_" + request["state"]), "closed_worker_orphan")
            if request["state"] == "reserved":
                ledger.cancel_unsent(request["request_id"], "all_generation_threads_closed")
            else:
                ledger.settle(request["request_id"], outcome="closed_worker_sent_usage_unknown")
    for row in ledger.sessions():
        if row["state"] != "finished":
            ledger.finish(row["session_id"], "not_requested_or_failed_after_global_stop")
    p.require(
        not any(row["state"] in {"reserved", "sent"} for row in ledger.requests()),
        "study.all_workers_closed_and_no_inflight",
    )
    progress()
    return {
        "results": results,
        "counts": dict(counts),
        "errors": errors,
        "global_stop": stop.is_set(),
        "elapsed_seconds": time.monotonic() - started,
        "synthetic_injection": synthetic,
        "all_generation_and_assessment_workers_closed": True,
    }


def _generation_report(
    freeze, registry, collected, wallet, journal, *, contracts_passed, references
):
    results = collected["results"]
    raw_complete = all(
        row["status"] == "finished" and row["session"] and row["qualification"] for row in results
    )
    contract = bool(
        contracts_passed
        and not collected["errors"]
        and not collected["global_stop"]
        and not wallet["persisted_stops"]
        and not collected["synthetic_injection"]
    )
    requested = {row["session_id"] for row in journal if row["state"] != "not_sent"}
    p.require(
        len(results) == len(registry["sessions"]) == p.SESSION_CAP
        and collected["all_generation_and_assessment_workers_closed"]
        and not any(row["state"] in {"reserved", "sent"} for row in journal),
        "study.complete_closed_generation_denominator",
    )
    return p.record(
        "material_generation_report",
        freeze_id=freeze["id"],
        registry_id=registry["id"],
        code_snapshot_id=freeze["code_snapshot_id"],
        generation_closed=True,
        no_inflight_requests=True,
        raw_registry_complete=bool(raw_complete),
        generation_contract_passed=contract,
        registered_sessions=len(results),
        finished_sessions=sum(row["status"] == "finished" for row in results),
        unrequested_sessions=len(results) - len(requested),
        session_results_statuses=dict(Counter(row["status"] for row in results)),
        status="COMPLETE_FIXED_COLLECTION"
        if raw_complete and contract
        else "STOP_INCOMPLETE_OR_CONTRACT",
        counts=collected["counts"],
        failure_records=collected["errors"],
        request_count=len(journal),
        actual_HTTP_request_count=sum(row["state"] != "not_sent" for row in journal),
        wallet_snapshot_id=wallet["id"],
        kernel_conservative_debit=wallet["kernel_conservative_debit"],
        common_conservative_debit=wallet["common_conservative_debit"],
        artifacts=references,
        elapsed_seconds=collected["elapsed_seconds"],
        GPU_operations=0,
        Student_training_runs=0,
        original_qualifications_rewritten=False,
        sources_or_tasks_replaced=False,
        fixed_registration_retained=True,
        finished_utc=p.now(),
    )


def run(code_root, data_root, *, materialize_after=True):
    code_root, data_root, output, work = guarded_roots(code_root, data_root)
    freeze, selected, registry, inputs, code, original = _verify_launch(
        code_root, data_root, output, require_unregistered_wallet=True
    )
    work.mkdir(parents=True, exist_ok=True)
    with (work / "owner.lock").open("a+b") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        p.require(
            not (output / "execution_started.json").exists(), "study.no_restart_or_resampling"
        )
        p.write_once(
            output / "execution_started.json",
            p.record(
                "execution_started",
                freeze_id=freeze["id"],
                code_snapshot_id=code["id"],
                source_commit_at_launch=git(code_root, "rev-parse", "HEAD").decode().strip(),
                registered_sessions=p.SESSION_CAP,
                generation_workers=p.WORKERS,
                assessment_workers=p.CPU_WORKERS,
                started_utc=p.now(),
                automatic_retry=False,
            ),
        )
        ledger = budget.KernelLedger(data_root / p.WALLET, freeze["id"])
        before = p.read_json(output / "legacy_wallet_before.json")
        registered = ledger.register(registry, selected, legacy_before=before)
        p.write_once(output / "budget_registration.json", registered)
        # This is deliberately after prospective registration, never prepare.
        credential = _credential(data_root).decode()
        collected = collect_registered(
            ledger, registry, inputs["fixtures"], output, work, code["id"], credential
        )
        del credential
        with ledger.connection(readonly=True) as db:
            after = budget.legacy_snapshot(db, before)
        protected_after = [source_snapshot(Path(root)) for root in PROTECTED]
        contracts = after == before and protected_after == p.read_json(
            output / "protected_sources_before.json"
        )
        try:
            verify_code(code_root, code, original)
        except (ValueError, OSError):
            contracts = False
        if not contracts:
            ledger.halt("post_generation_original_contract_changed")
        journal, wallet = ledger.requests(), ledger.snapshot()
        artifacts = {
            "session_results.json": collected["results"],
            "terminal_registry.json": ledger.sessions(),
            "material_request_journal.json": journal,
            "legacy_wallet_after.json": after,
            "protected_sources_after.json": protected_after,
            "wallet_after_generation.json": wallet,
        }
        references = {}
        for name, value in artifacts.items():
            p.write_once(output / name, value)
            references[name] = _reference(
                output / name, output, value.get("id") if isinstance(value, dict) else None
            )
        report = _generation_report(
            freeze,
            registry,
            collected,
            wallet,
            journal,
            contracts_passed=contracts,
            references=references,
        )
        p.write_once(output / "generation_report.json", report)
        finalization = ledger.finalize(report_id=report["id"])
        p.write_once(output / "budget_finalization.json", finalization)
        _progress(
            work / "progress.json",
            {
                "status": report["status"],
                "report_id": report["id"],
                "wallet": ledger.snapshot(),
                "updated_utc": p.now(),
            },
        )
    if materialize_after:
        return materialize(code_root, data_root)
    return report


def _materialization_gate(index, kernel, generation):
    measured = bool(index.get("materialization_permitted", index["collection_complete"]))
    groups = {row["task_id"]: row["family"] for row in kernel["tasks"]}
    supports = defaultdict(Counter)
    physical = {pool: Counter() for pool in p.POOLS}
    for package in kernel["train_packages"]:
        supports[(package["pool"], package["task_id"])][package["method"]] += 1
        physical[package["pool"]]["packages_per_epoch"] += 1
        physical[package["pool"]]["target_tokens_per_epoch"] += package[
            "whole_package_target_tokens"
        ]
        rows = package["original_package"]["rows"]
        physical[package["pool"]]["rows_per_epoch"] += len(rows)
        physical[package["pool"]]["sequence_tokens_per_epoch"] += sum(
            row["representation"]["sequence_length"] for row in rows
        )
    return p.record(
        "material_gate",
        generation_report_id=generation["id"],
        materialization_index_id=index["id"],
        kernel_id=kernel["id"],
        population_id=kernel["population_id"],
        registry_id=kernel["registry_id"],
        raw_registry_complete=generation["raw_registry_complete"],
        generation_contract_passed=generation["generation_contract_passed"],
        materialization_permitted=measured,
        token_support_measurement="MEASURED" if measured else "NOT_MEASURED_GLOBAL_GATE",
        material_gate=kernel["material_gate"] if measured else "NOT_MEASURED_GLOBAL_GATE",
        dose_gate=kernel["dose_gate"] if measured else "NOT_MEASURED_GLOBAL_GATE",
        training_gate=kernel["training_gate"] if measured else "FAIL",
        common_intervention_task_ids=kernel["common_intervention_task_ids"] if measured else None,
        common_intervention_task_count=len(kernel["common_intervention_task_ids"])
        if measured
        else None,
        global_mass_movement=kernel["global_mass_movement"] if measured else None,
        minimum_mass_movement=distribution.rational(distribution.MINIMUM_MASS_MOVEMENT),
        empty_pool_task_support=kernel["empty_pool_task_support"] if measured else None,
        per_pool_task_actual_support=[
            {
                "pool": pool,
                "task_id": task,
                "family": groups[task],
                "actual_method_package_counts": dict(supports[(pool, task)]),
            }
            for pool in p.POOLS
            for task in sorted(groups)
        ]
        if measured
        else None,
        physical_budgets={
            pool: {
                **dict(counts),
                **{
                    key.replace("per_epoch", "all_epochs"): value * 10
                    for key, value in counts.items()
                },
            }
            for pool, counts in physical.items()
        }
        if measured
        else None,
        physical_originals_sha256=kernel["physical_originals_sha256"],
        all_valid_train_originals_retained=True,
        sealed_promoted=False,
        original_package_arrays_repeated_in_gate=False,
        full_kernel_or_outcomes_JSON_written=False,
        GPU_operations=0,
        Student_training_runs=0,
        next_stage="separate_execution_release_required"
        if measured and kernel["training_gate"] == "PASS"
        else "STOP_NO_SCIENTIFIC_TRAINING",
    )


def materialize(code_root, data_root):
    code_root, data_root, output, work = guarded_roots(code_root, data_root)
    freeze, _, registry = _load_prepared(output)
    p.require(
        not (output / "materialization_started.json").exists(), "study.materialize_once_no_refill"
    )
    generation = p.checked(
        p.read_json(output / "generation_report.json"), "material_generation_report"
    )
    finalization = p.checked(
        p.read_json(output / "budget_finalization.json"), "kernel_budget_finalization"
    )
    p.require(
        generation["generation_closed"] is True
        and generation["no_inflight_requests"] is True
        and generation["registered_sessions"] == p.SESSION_CAP
        and generation["freeze_id"] == finalization["freeze_id"] == freeze["id"]
        and generation["code_snapshot_id"] == freeze["code_snapshot_id"]
        and generation["registry_id"] == registry["id"]
        and finalization["purpose_closed"] is True
        and finalization["report_id"] == generation["id"],
        "study.generation_and_budget_closed_before_materialization",
    )
    ledger = budget.KernelLedger(data_root / p.WALLET, freeze["id"])
    with ledger.connection(readonly=True) as db:
        persisted = db.execute("SELECT value FROM metadata WHERE key=?", (budget.FINAL,)).fetchone()
    p.require(
        persisted is not None
        and json.loads(persisted[0]) == finalization
        and not any(row["state"] in {"reserved", "sent"} for row in ledger.requests()),
        "study.actual_wallet_finalized_no_inflight",
    )
    for name, reference in generation["artifacts"].items():
        p.require(
            reference["path"] == name and p.sha(output / name) == reference["sha256"],
            "study.frozen_generation_artifact",
        )
    verify_code(
        code_root,
        p.read_json(output / "code_snapshot.json"),
        p.read_json(output / "original_code_dependencies.json"),
    )
    results = p.read_json(output / "session_results.json")
    selected = p.read_json(output / "population.json")
    p.write_once(
        output / "materialization_started.json",
        p.record(
            "materialization_started",
            generation_report_id=generation["id"],
            budget_finalization_id=finalization["id"],
            before_any_token_encoding=True,
            generation_contract_passed=generation["generation_contract_passed"],
            time=p.now(),
        ),
    )

    def load_item(row):
        return {
            key: _read_reference(row[key], output) if row.get(key) else None
            for key in ("session", "qualification")
        }

    def frozen_tokenizer(root):
        binding, tokenizer = materials.load_local_tokenizer(root)
        p.require(
            binding == p.read_json(output / "tokenizer_binding_preflight.json"),
            "study.formal_tokenizer_matches_preflight_binding",
        )
        return binding, tokenizer

    index = materials.materialize_all(
        registry,
        results,
        data_root,
        output,
        code_snapshot_id=freeze["code_snapshot_id"],
        item_loader=load_item,
        loader=frozen_tokenizer,
        collection_gate_passed=generation["status"] == "COMPLETE_FIXED_COLLECTION",
        collection_gate_reason=None
        if generation["status"] == "COMPLETE_FIXED_COLLECTION"
        else "generation_global_contract_or_registry_incomplete",
    )
    outcomes = materials.hydrate_outcomes(index, output)
    kernel = distribution.build_kernel(selected, registry, outcomes)
    gate = _materialization_gate(index, kernel, generation)
    p.write_once(output / "material_gate.json", gate)
    _progress(
        work / "progress.json",
        {
            "status": "MATERIAL_GATE_" + gate["training_gate"],
            "gate_id": gate["id"],
            "generation_report_id": generation["id"],
            "updated_utc": p.now(),
        },
    )
    return gate


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--code-root", type=Path, required=True)
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--phase", choices=("prepare", "run", "materialize"), required=True)
    parser.add_argument("--junit", type=Path)
    parser.add_argument("--shadow-control", type=Path)
    parser.add_argument("--gpu-report", type=Path, action="append")
    parser.add_argument("--model-preflight", type=Path)
    parser.add_argument("--control-workers", type=int, default=p.CPU_WORKERS)
    parser.add_argument("--generation-only", action="store_true")
    args = parser.parse_args()
    if args.phase == "prepare":
        p.require(
            args.junit and args.shadow_control and args.gpu_report,
            "study.prepare_requires_existing_CPU_shadow_GPU_evidence",
        )
        result = prepare(
            args.code_root,
            args.data_root,
            junit_path=args.junit,
            shadow_path=args.shadow_control,
            gpu_reports=args.gpu_report,
            model_preflight_path=args.model_preflight,
            control_workers=args.control_workers,
        )
    elif args.phase == "run":
        result = run(args.code_root, args.data_root, materialize_after=not args.generation_only)
    else:
        result = materialize(args.code_root, args.data_root)
    print(
        json.dumps(
            {
                "phase": args.phase,
                "id": result["id"],
                "status": result.get("status", result.get("training_gate", "PREPARED")),
            }
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
