"""Preregister, then execute the bounded Probe matrix; no Student entry point."""

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
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
from contextlib import ExitStack
from importlib import metadata
from multiprocessing import get_context
from pathlib import Path

from ..finance_qa_vnext_basis_student.publication import _credential
from ..finance_qa_vnext_catalog_bridge.controls import script_for_witness
from ..finance_qa_vnext_linear_postprocess.manifest import LinearParent
from ..finance_qa_vnext_movement_support.protocol import checked_record as checked_phase_zero
from ..finance_qa_vnext_movement_support.run import load_fixtures, source_snapshot
from ..finance_qa_vnext_task_build.archive import validate_record
from ..qa_reasoning_share_training_preflight import tokenization as tokenizer_assets
from . import assessment, budget, metrics, runtime, transport
from . import protocol as p

PROTECTED = (
    "/data1/zhuxinrui/projects/Data-Synthesis",
    "/tmp/data-synthesis-anchored-vtdo-MaNMFd",
    "/tmp/data-synthesis-hierarchical-loss-yvab69o2",
    "/tmp/data-synthesis-movement-support-se2ytr1a",
)


def git(root, *args):
    return subprocess.check_output(["git", "-C", str(root), *args])


def guarded_roots(code_root, data_root):
    code_root, data_root = Path(code_root).resolve(), Path(data_root).resolve()
    p.require(
        code_root != data_root and Path(__file__).resolve().is_relative_to(code_root),
        "independent_actual_code_root",
    )
    p.require(
        git(code_root, "branch", "--show-current").decode().strip() == p.BRANCH,
        "independent_branch",
    )
    p.require(
        git(data_root, "branch", "--show-current").decode().strip() == "main"
        and git(data_root, "rev-parse", "HEAD").decode().strip() == p.MAIN_COMMIT,
        "unchanged_main",
    )
    p.require(
        git(code_root, "rev-parse", "--path-format=absolute", "--git-common-dir")
        == git(data_root, "rev-parse", "--path-format=absolute", "--git-common-dir"),
        "same_project_common_Git",
    )
    output, work = code_root / p.OUTPUT, code_root / p.RUNTIME
    for path in (output, work):
        p.require(
            not any(x.is_symlink() for x in (path, *path.parents))
            and path.resolve().is_relative_to(code_root),
            "isolated_regular_output",
        )
    return code_root, data_root, output, work


def code_snapshot(root):
    root = Path(root)
    files = sorted((root / p.PACKAGE).glob("*.py"))
    files += sorted(
        (root / "trusted_data_synthesis/tests").glob("test_qa_vnext_probe_coverage_*.py")
    )
    p.require(files and all(x.is_file() and not x.is_symlink() for x in files), "regular_new_code")
    # The parent is fixed; byte identities remain valid after a preregistration commit.
    return p.record(
        "probe_code_snapshot",
        parent_commit=p.BASE_COMMIT,
        members=[{"path": str(x.relative_to(root)), "sha256": p.sha(x)} for x in files],
    )


def base_dependencies(root):
    prefixes = (
        "trusted_data_synthesis/src",
        "trusted_data_synthesis/tests",
        "trusted_data_synthesis/config",
        "raw_financial_data_lake/finraw",
        "trusted_data_synthesis/pyproject.toml",
    )
    names = (
        git(root, "ls-tree", "-r", "--name-only", "-z", p.BASE_COMMIT, "--", *prefixes)
        .decode()
        .split("\0")
    )
    names = [name for name in names if name]
    batch = subprocess.run(
        ["git", "-C", str(root), "cat-file", "--batch"],
        input="".join(p.BASE_COMMIT + ":" + name + "\n" for name in names).encode(),
        capture_output=True,
        check=True,
    ).stdout
    rows, offset = [], 0
    for name in names:
        path = Path(root) / name
        p.require(path.is_file() and not path.is_symlink(), "materialized_original_code_dependency")
        end = batch.index(b"\n", offset)
        _, kind, size = batch[offset:end].decode().split()
        p.require(kind == "blob", "original_dependency_blob")
        size = int(size)
        raw = batch[end + 1 : end + 1 + size]
        offset = end + size + 2
        p.require(
            len(raw) == size and batch[offset - 1 : offset] == b"\n", "complete_original_blob_bytes"
        )
        p.require(raw == path.read_bytes(), "old_dependency_code_not_modified:" + name)
        rows.append({"path": name, "sha256": p.sha(raw)})
    p.require(offset == len(batch), "complete_dependency_batch")
    return p.record("original_code_dependencies", parent_commit=p.BASE_COMMIT, members=rows)


def verify_code(root, code, base):
    p.require(code_snapshot(root) == code, "frozen_new_code_bytes")
    p.require(
        all(p.sha(Path(root) / r["path"]) == r["sha256"] for r in base["members"]),
        "frozen_original_dependency_bytes",
    )


def _tokenizer_asset_check(data_root):
    rows = []
    for name, size, digest in tokenizer_assets.TOKENIZER_MEMBERS:
        path = tokenizer_assets.MODEL_DIRECTORY / name
        p.require(
            path.is_file()
            and not path.is_symlink()
            and path.stat().st_size == size
            and p.sha(path) == digest,
            "frozen_CPU_tokenizer_assets",
        )
        rows.append({"path": str(path), "bytes": size, "sha256": digest})
    path = Path(data_root) / tokenizer_assets.SOURCE_CONFIGURATION
    p.require(
        p.sha(path) == tokenizer_assets.SOURCE_CONFIGURATION_SHA256,
        "original_tokenizer_configuration",
    )
    return p.record(
        "CPU_tokenizer_asset_check",
        members=rows,
        source_configuration_sha256=p.sha(path),
        tokenizer_constructions=0,
        Student_weight_loads=0,
        GPU_operations=0,
    )


def _fixtures(stack, data_root):
    parent = LinearParent(data_root, p.REVISION, p.REVISION_MANIFEST)
    stack.callback(parent.close)
    catalog = parent.read("catalog.json")
    validate_record(catalog, "composed_task_catalog")
    selected = p.select_tasks(catalog)
    all_fixtures, dependencies = load_fixtures(stack, data_root)
    by_task = {x["identity"]["task_id"]: x for x in all_fixtures}
    fixtures = {r["task_id"]: by_task[r["task_id"]] for r in selected}
    for row in selected:
        p.require(
            fixtures[row["task_id"]]["bundle"]["id"] == row["bundle_id"],
            "selected_private_bundle_identity",
        )
    return selected, fixtures, dependencies


def _control(job):
    fixture, profile, guidance, actual = job
    identity = fixture["identity"]
    reg = {
        "session_id": "probe01_script_" + p.sha(p.encode([identity, profile, guidance, actual])),
        "identity": identity,
        "profile": profile,
        "basis": guidance,
        "system_prompt_sha256": p.sha(p.system_prompt(profile, guidance)),
    }
    script = script_for_witness(fixture["bundle"], fixture["native_bindings"], actual)
    queue = iter(script)
    session = runtime.generate(
        fixture["messages"],
        identity,
        registered=reg,
        provider=lambda *_: p.encode(next(queue)).decode(),
    )
    origin = {"session_id": session["id"], "status": "ORIGIN_NOT_VERIFIED_SCRIPTED_REFERENCE_ONLY"}
    qualification = assessment.assess(session, fixture, origin)
    bodies = [transport.render(turn["input_messages"])[1] for turn in session["turns"]]
    return p.record(
        "public_interface_control",
        task_id=identity["task_id"],
        profile=profile,
        requested_guidance=guidance,
        scripted_actual_basis=actual,
        passed=bool(
            qualification["financial_valid"]
            and qualification["actual_method"] == actual
            and qualification["full_mapping_status"] == "MAPPED"
        ),
        original_semantic_assessment_id=qualification["original_semantic_assessment"]["id"],
        actual_method=qualification["actual_method"],
        reason=qualification["reason"],
        responses=len(session["turns"]),
        maximum_serialized_request_bytes=max(map(len, bodies)),
        original_public_messages_unchanged=session["public_messages"] == fixture["messages"],
        raw_history_and_tools_replayed=True,
        wire_body_rendered_but_HTTP_not_called=True,
        authentic_Probe_data=False,
        training_samples=0,
        scripted_private_reference_never_sent_to_model=True,
    )


def _junit(path):
    suites = list(ET.parse(path).iter("testsuite"))
    counts = {
        key: sum(int(x.attrib.get(key, 0)) for x in suites)
        for key in ("tests", "failures", "errors", "skipped")
    }
    p.require(
        counts["tests"] > 0 and all(counts[k] == 0 for k in ("failures", "errors", "skipped")),
        "CPU_controls_must_all_pass",
    )
    return {
        "sha256": p.sha(Path(path)),
        **counts,
        "seconds": sum(float(x.attrib.get("time", 0)) for x in suites),
    }


def _shadow_budget_check(source_path, work, selected, before):
    """Exercise the real old schema in a disposable copy, never a live wallet."""
    work.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="wallet_guard_", dir=work) as temporary:
        copy_path = Path(temporary) / "shadow.sqlite3"
        with sqlite3.connect(Path(source_path).as_uri() + "?mode=ro", uri=True) as source:
            with sqlite3.connect(copy_path) as target:
                source.backup(target)
        shadow = budget.CoverageLedger(copy_path, "offline_shadow_only")
        with shadow.connection(readonly=True) as db:
            cloned = budget.legacy_snapshot(db)
        p.require(cloned == before, "shadow_is_exact_old_logical_wallet")
        registry = p.make_registry(selected, "offline_shadow_only")
        shadow.register(registry, selected, legacy_before=cloned)
        lease = shadow.reserve(registry[0]["session_id"])
        shadow.mark_sent(lease["request_id"])
        p.require(
            shadow.settle(
                lease["request_id"],
                usage={"prompt_tokens": 2, "completion_tokens": 1, "total_tokens": 3},
                http_success=True,
                response_model=p.MODEL,
                outcome="public_response_received",
            ),
            "real_schema_simulated_settlement",
        )
        with shadow.connection(readonly=True) as db:
            p.require(
                budget.legacy_snapshot(db, before) == before, "shadow_does_not_rewrite_old_rows"
            )
        return p.record(
            "real_schema_shadow_control",
            legacy_snapshot_id=before["id"],
            simulated_probe_debit=shadow.snapshot()["probe_conservative_debit"],
            real_wallet_mutations=0,
            HTTP_calls=0,
            shadow_never_used_for_network=True,
            copied_original_unknown_charges_not_reclaimed=True,
            passed=True,
        )


def prepare(code_root, data_root):
    code_root, data_root, output, work = guarded_roots(code_root, data_root)
    p.require(not (output / "freeze.json").exists(), "new_prospective_freeze_only")
    tests = _junit(output / "cpu_tests.xml")
    code, base = code_snapshot(code_root), base_dependencies(code_root)
    phase_zero_raw = git(
        code_root, "show", p.BASE_COMMIT + ":" + p.PHASE_ZERO + "/cohort_report.json"
    )
    phase_zero = checked_phase_zero(json.loads(phase_zero_raw), "cohort_report")
    p.require(phase_zero["id"] == p.PHASE_ZERO_REPORT, "actual_committed_Phase0_parent")
    protected = [source_snapshot(Path(root)) for root in PROTECTED]
    with ExitStack() as stack:
        selected, fixtures, dependencies = _fixtures(stack, data_root)
        # A read-only temporary handle does not initialize or change the old wallet.
        pending = budget.CoverageLedger(data_root / p.WALLET, "not_yet_registered")
        with pending.connection(readonly=True) as db:
            db.execute("BEGIN")
            before = budget.legacy_snapshot(db)
            baseline = db.execute("SELECT COALESCE(SUM(tokens),0) FROM prior_debits").fetchone()[0]
            baseline += sum(
                db.execute(f"SELECT COALESCE(SUM(charged_tokens),0) FROM {t}").fetchone()[0]
                for t in budget.OLD_RESERVATIONS
            )
            p.require(
                not db.execute("SELECT 1 FROM metadata WHERE key='study_fatal'").fetchone(),
                "common_wallet_not_halted",
            )
            db.execute("COMMIT")
        asset_check = _tokenizer_asset_check(data_root)
        shadow = _shadow_budget_check(data_root / p.WALLET, work, selected, before)
        jobs = [
            (fixtures[row["task_id"]], profile, guidance, actual)
            for row in selected
            for profile in p.PROFILES
            for guidance in p.BASES
            for actual in p.BASES
        ]
        with ProcessPoolExecutor(max_workers=4, mp_context=get_context("spawn")) as pool:
            controls = list(pool.map(_control, jobs))
        p.require(
            len(controls) == 144 and all(x["passed"] for x in controls),
            "all_selected_interface_controls",
        )
        verify_code(code_root, code, base)
    api = p.record(
        "official_API_preflight",
        models_get_URL="https://api.deepseek.com/models",
        models_GET_status=200,
        observed_model_IDs=["deepseek-flash", "deepseek-v4-pro"],
        observed_models_response_sha256=(
            "0c5d2ba6ebb791e893b0e7efed32c64415a633ed774e8d89dad8e33c4d69ae77"
        ),
        model_inventory_observation=(
            "read-only GET in this preparation turn; parsed IDs/hash retained, "
            "raw body not retained"
        ),
        model_catalog_GET_requests=1,
        model_generation_requests=0,
        official_sources=[
            "https://api-docs.deepseek.com/quick_start/rate_limit/",
            "https://api-docs.deepseek.com/guides/json_mode/",
            "https://api-docs.deepseek.com/api/list-models/",
        ],
        documented_Flash_account_concurrency_limit=2500,
        registered_probe_concurrency=p.WORKERS,
        rate_limit_is_shared_with_other_account_users=True,
        JSON_mode_can_return_empty_content=True,
        model_or_transport_fallback=False,
    )
    control_record = p.record(
        "scripted_preflight",
        cases=controls,
        scripted_cases=len(controls),
        passed=True,
        API_requests=0,
        training_samples=0,
    )
    freeze = p.record(
        "coverage_freeze",
        policy_id=p.policy()["id"],
        selected_tasks=selected,
        parent_catalog_dependencies_id=dependencies["id"],
        Phase0_parent_report_id=phase_zero["id"],
        new_code_snapshot_id=code["id"],
        original_code_dependencies_id=base["id"],
        legacy_wallet_before_id=before["id"],
        baseline_common_conservative_debit=baseline,
        remaining_common_before=p.COMMON_CAP - baseline,
        tokenizer_asset_check_id=asset_check["id"],
        official_API_preflight_id=api["id"],
        scripted_preflight_id=control_record["id"],
        real_schema_shadow_control_id=shadow["id"],
        CPU_test_result=tests,
        software={
            "python": sys.version,
            **{x: metadata.version(x) for x in ("sympy", "httpx", "transformers", "tokenizers")},
        },
        frozen_before_any_live_Probe_response=True,
        Teacher_or_Probe_generation_requests_before_freeze=0,
    )
    registry = p.make_registry(selected, freeze["id"])
    p.require(
        baseline + p.REQUEST_RESERVATION * p.WORKERS <= p.COMMON_CAP,
        "common_budget_room_for_initial_concurrency",
    )
    artifacts = {
        "policy.json": p.policy(),
        "code_snapshot.json": code,
        "original_code_dependencies.json": base,
        "protected_sources_before.json": protected,
        "source_dependencies.json": dependencies,
        "legacy_wallet_before.json": before,
        "official_API_preflight.json": api,
        "tokenizer_asset_check.json": asset_check,
        "real_schema_shadow_control.json": shadow,
        "scripted_preflight.json": control_record,
        "selected_tasks.json": selected,
        "registry.json": registry,
        "freeze.json": freeze,
    }
    for name, value in artifacts.items():
        p.write_once(output / name, value)
    return freeze


def _runtime_progress(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix="probe_progress_", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(p.encode(value))
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if Path(temporary).exists():
            Path(temporary).unlink()


def _assess_job(session, fixture, origin):
    return assessment.assess(session, fixture, origin)


def run(code_root, data_root):
    code_root, data_root, output, work = guarded_roots(code_root, data_root)
    freeze = p.checked(json.loads((output / "freeze.json").read_bytes()), "coverage_freeze")
    p.require(freeze["policy_id"] == p.policy()["id"], "same_preregistered_policy")
    registry = json.loads((output / "registry.json").read_bytes())
    p.validate_registry(registry, freeze["selected_tasks"], freeze["id"])
    code = p.checked(
        json.loads((output / "code_snapshot.json").read_bytes()), "probe_code_snapshot"
    )
    base = p.checked(
        json.loads((output / "original_code_dependencies.json").read_bytes()),
        "original_code_dependencies",
    )
    verify_code(code_root, code, base)
    p.require(
        freeze["new_code_snapshot_id"] == code["id"]
        and freeze["original_code_dependencies_id"] == base["id"],
        "freeze_binds_all_actual_code_snapshots",
    )
    p.require(
        git(code_root, "show", "HEAD:" + p.OUTPUT + "/freeze.json") == p.encode(freeze),
        "preregistration_committed_before_live_requests",
    )
    for member in code["members"]:
        p.require(
            p.sha(git(code_root, "show", "HEAD:" + member["path"])) == member["sha256"],
            "executed_source_committed_with_preregistration",
        )
    with ExitStack() as precheck:
        checked_tasks, _, checked_dependencies = _fixtures(precheck, data_root)
        p.require(
            checked_tasks == freeze["selected_tasks"]
            and checked_dependencies["id"] == freeze["parent_catalog_dependencies_id"],
            "full_input_admission_before_wallet_migration",
        )
    work.mkdir(parents=True, exist_ok=True)
    lock = (work / "owner.lock").open("a+b")
    fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    p.require(not (output / "execution_started.json").exists(), "no_live_restart_or_resampling")
    started = time.monotonic()
    secret = _credential(data_root).decode()
    ledger = budget.CoverageLedger(data_root / p.WALLET, freeze["id"])
    before = p.checked(
        json.loads((output / "legacy_wallet_before.json").read_bytes()), "legacy_wallet_snapshot"
    )
    p.require(
        before["id"] == freeze["legacy_wallet_before_id"], "freeze_binds_original_wallet_snapshot"
    )
    registration = ledger.register(registry, freeze["selected_tasks"], legacy_before=before)
    p.write_once(output / "budget_registration.json", registration)
    p.write_once(
        output / "execution_started.json",
        p.record(
            "execution_started",
            freeze_id=freeze["id"],
            code_snapshot_id=code["id"],
            source_commit_at_launch=git(code_root, "rev-parse", "HEAD").decode().strip(),
            registered_rollouts=len(registry),
            model=p.MODEL,
            workers=p.WORKERS,
            started_utc=p.now(),
            old_training_jobs_not_started=True,
            Student_or_GPU_calls=0,
        ),
    )
    stop = threading.Event()
    results = [
        {
            "registered_session_id": r["session_id"],
            "session": None,
            "qualification": None,
            "status": "not_requested_after_global_stop",
        }
        for r in registry
    ]
    counts = Counter()
    with ExitStack() as stack:
        selected, fixtures, dependencies = _fixtures(stack, data_root)
        p.require(
            selected == freeze["selected_tasks"]
            and dependencies["id"] == freeze["parent_catalog_dependencies_id"],
            "unchanged_source_catalog_and_private_bundles",
        )

        def one(reg):
            if stop.is_set():
                return None
            f = fixtures[reg["task_id"]]
            actual_provider = transport.Provider(ledger, reg, output / "requests", secret)

            def provider(messages, context):
                if stop.is_set():
                    raise transport.FatalProbeError("probe01.stopped_before_next_request")
                try:
                    return actual_provider(messages, context)
                except Exception as error:
                    if getattr(error, "global_fatal", False):
                        stop.set()
                    raise

            session = runtime.generate(
                f["messages"], f["identity"], provider=provider, registered=reg
            )
            if session["global_fatal"]:
                stop.set()
            p.write_once(output / "sessions" / reg["session_id"] / "session.json", session)
            try:
                origin = transport.verify_origin(session, ledger, output / "requests")
            except (ValueError, KeyError, TypeError, OSError) as error:
                origin = p.record(
                    "probe_origin_failure",
                    session_id=session["id"],
                    status="ORIGIN_NOT_VERIFIED",
                    reason=str(error),
                    training_eligible=False,
                )
            ledger.finish(reg["session_id"], session["terminal"])
            return session, origin

        with ProcessPoolExecutor(max_workers=4, mp_context=get_context("spawn")) as scoring:
            scoring_jobs = {}
            with ThreadPoolExecutor(max_workers=p.WORKERS) as generation:
                jobs = {generation.submit(one, reg): reg for reg in registry}
                for future in as_completed(jobs):
                    reg = jobs[future]
                    try:
                        value = future.result()
                    except Exception as error:
                        stop.set()
                        ledger.halt("collection_internal_error:" + type(error).__name__)
                        raise
                    if value is not None:
                        session, origin = value
                        results[reg["ordinal"]].update(session=session, status="recorded")
                        scoring_jobs[
                            scoring.submit(_assess_job, session, fixtures[reg["task_id"]], origin)
                        ] = reg
                        counts["recorded"] += 1
                        counts[session["terminal"]] += 1
                    else:
                        counts["not_requested"] += 1
                    _runtime_progress(
                        work / "progress.json",
                        {
                            "counts": dict(counts),
                            "registered": p.SESSION_CAP,
                            "elapsed_seconds": time.monotonic() - started,
                            "wallet": ledger.snapshot(),
                            "updated_utc": p.now(),
                        },
                    )
                    print(
                        json.dumps(
                            {
                                "recorded": counts["recorded"],
                                "not_requested": counts["not_requested"],
                                "registered": p.SESSION_CAP,
                                "elapsed_seconds": round(time.monotonic() - started, 2),
                            }
                        ),
                        flush=True,
                    )
            for future in as_completed(scoring_jobs):
                reg = scoring_jobs[future]
                qualification = future.result()
                p.write_once(
                    output / "sessions" / reg["session_id"] / "qualification.json", qualification
                )
                results[reg["ordinal"]]["qualification"] = qualification
    complete = all(r["session"] is not None and r["qualification"] is not None for r in results)
    pairs = [(r["session"], r["qualification"]) for r in results if r["qualification"] is not None]
    tokens = assessment.token_diagnostics(pairs, data_root, complete_registry=complete)
    p.write_once(output / "token_diagnostics.json", tokens)
    summary = metrics.summarize(registry, results, tokens)
    p.write_once(output / "coverage_metrics.json", summary)
    p.write_once(
        output / "session_results.json",
        [
            {
                "registered_session_id": r["registered_session_id"],
                "status": r["status"],
                "session_id": r["session"]["id"] if r["session"] else None,
                "qualification_id": r["qualification"]["id"] if r["qualification"] else None,
            }
            for r in results
        ],
    )
    p.write_once(output / "terminal_registry.json", ledger.sessions())
    p.write_once(output / "probe_request_journal.json", ledger.requests())
    with ledger.connection(readonly=True) as db:
        db.execute("BEGIN")
        after = budget.legacy_snapshot(db, before)
        db.execute("COMMIT")
    p.require(after == before, "all_original_wallet_rows_and_guards_unchanged")
    p.write_once(output / "legacy_wallet_after.json", after)
    verify_code(code_root, code, base)
    protected = [source_snapshot(Path(root)) for root in PROTECTED]
    p.require(
        protected == json.loads((output / "protected_sources_before.json").read_bytes()),
        "old_branches_unchanged",
    )
    p.write_once(output / "protected_sources_after.json", protected)
    wallet = ledger.snapshot()
    p.write_once(output / "wallet_after_generation.json", wallet)
    report = p.record(
        "probe_coverage_report",
        freeze_id=freeze["id"],
        metrics_id=summary["id"],
        token_diagnostics_id=tokens["id"],
        registered_rollouts=p.SESSION_CAP,
        recorded_rollouts=counts["recorded"],
        unrequested_rollouts=counts["not_requested"],
        complete_registered_collection=complete,
        status="COMPLETE_PROBE_COVERAGE"
        if complete and not wallet["persisted_stops"]
        else "STOP_INCOMPLETE_OR_CONTRACT",
        elapsed_seconds=time.monotonic() - started,
        finished_utc=p.now(),
        wallet_snapshot_id=wallet["id"],
        new_code_snapshot_id=code["id"],
        old_source_branches_unchanged=True,
        original_budget_rows_unchanged=True,
        common_wallet_schema_extended_with_fourth_purpose=True,
        new_probe_requests=len(ledger.requests()),
        model_catalog_GET_requests=1,
        Student_runs=0,
        Student_weight_loads=0,
        GPU_operations=0,
        training_admitted=False,
        original_AB_materials_modified=False,
        old_qualification_or_mapper_modified=False,
        source_acquisition_or_question_rewrite_requests=0,
    )
    p.write_once(output / "report.json", report)
    finalization = ledger.finalize(report_id=report["id"])
    p.write_once(output / "budget_finalization.json", finalization)
    _runtime_progress(
        work / "progress.json",
        {
            "status": report["status"],
            "report_id": report["id"],
            "wallet": ledger.snapshot(),
            "elapsed_seconds": report["elapsed_seconds"],
            "updated_utc": p.now(),
        },
    )
    fcntl.flock(lock.fileno(), fcntl.LOCK_UN)
    lock.close()
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--code-root", type=Path, required=True)
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--phase", choices=["prepare", "run"], required=True)
    args = parser.parse_args()
    result = {"prepare": prepare, "run": run}[args.phase](args.code_root, args.data_root)
    print(json.dumps({"id": result["id"], "phase": args.phase, "status": "COMPLETE"}), flush=True)


if __name__ == "__main__":
    main()
