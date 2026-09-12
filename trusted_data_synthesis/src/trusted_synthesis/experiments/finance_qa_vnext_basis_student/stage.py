"""Close the existing batch, materialize once, then execute the registered study.

The monitor never restarts collection. No Student preparation or worker can run
until the original full registry and its sealed report actually close.
"""

import argparse
import json
import os
import sqlite3
import subprocess
import sys
import time
from collections import Counter
from contextlib import closing
from importlib.metadata import version
from pathlib import Path

from ..finance_qa_vnext_basis_scale_preparation import design
from ..finance_qa_vnext_catalog_bridge.catalog import Parent
from ..finance_qa_vnext_catalog_bridge.stage import seal
from ..finance_qa_vnext_eval_readiness import materials
from ..finance_qa_vnext_eval_surface import overlay
from ..finance_qa_vnext_eval_surface import stage as surface_stage
from . import protocol as p


def code_root():
    return Path(__file__).resolve().parents[5]


def collection_status(root):
    """One read-only transaction; no ledger constructor and no session selection."""
    root = Path(root).resolve()
    wallet = p.path_within(root, p.LEDGER)
    with closing(sqlite3.connect(wallet.as_uri() + "?mode=ro", uri=True)) as db:
        db.execute("PRAGMA query_only=ON")
        db.execute("BEGIN")
        states = dict(db.execute("SELECT state,COUNT(*) FROM collection_sessions GROUP BY state"))
        metadata = dict(db.execute("SELECT key,value FROM metadata"))
        prior = db.execute("SELECT COALESCE(SUM(tokens),0) FROM prior_debits").fetchone()[0]
        debits = {
            name: db.execute("SELECT COALESCE(SUM(charged_tokens),0) FROM " + name).fetchone()[0]
            for name in ("reservations", "teacher_reservations", "eval_reservations")
        }
        request_states = dict(
            db.execute("SELECT state,COUNT(*) FROM teacher_reservations GROUP BY state")
        )
        db.execute("ROLLBACK")
    count = sum(states.values())
    p.require(count == 24640, "study.original_complete_24640_registry")
    final_exists = (root / p.COLLECTION / "manifest.json").is_file()
    fatal = metadata.get("study_fatal")
    complete = False
    if final_exists:
        parent = Parent(root, p.COLLECTION)
        report = parent.read("report.json")
        materials.checked_record(report, "fixed_collection_report")
        complete = (
            report["status"] == "COMPLETE_FIXED_COLLECTION"
            and report["collection_complete"]
            and states == {"finished": 24640}
            and report["registered_session_count"] == report["finished_session_count"] == 24640
            and report["recorded_session_count"] == 24640
            and fatal is None
        )
    return p.record(
        "collection_observation",
        observed_at=p.now(),
        states=states,
        registered_sessions=count,
        teacher_request_states=request_states,
        shared_prior_debit=prior,
        shared_purpose_debits=debits,
        shared_conservative_debit=prior + sum(debits.values()),
        shared_remaining_tokens=1_000_000_000 - prior - sum(debits.values()),
        study_fatal=fatal,
        sealed_final_report=final_exists,
        status="COMPLETE_FIXED_COLLECTION"
        if complete
        else (
            "STOP_INCOMPLETE_FIXED_COLLECTION"
            if final_exists
            else ("COLLECTION_STOPPING" if fatal else "COLLECTION_RUNNING")
        ),
        read_only=True,
        collection_restarted=False,
        partial_population_selected=False,
    )


def evaluation_registry(root):
    online = overlay.PublicOverlay(root, p.SURFACES, p.SURFACE_MANIFEST_ID)
    result = {"dev": [], "confirm": []}
    for task in online.tasks.values():
        envelope = online.public_envelope(task["task_id"])
        public = overlay.public_object(envelope["messages"])
        cik = public["period_contract"].get("source_cluster")
        p.require(cik is not None, "study.public_CIK_required")
        result[task["split"]].append(
            {
                "task_id": task["task_id"],
                "group": task["family"],
                "source_cluster": str(cik),
                "surface_version_id": task["surface_version_id"],
                "public_messages_sha256": task["public_messages_sha256"],
            }
        )
    for split, count in (("dev", 60), ("confirm", 240)):
        counts = Counter(row["group"] for row in result[split])
        p.require(
            len(counts) == 3 and set(counts.values()) == {count}, "study.fixed_3_group_registry"
        )
    return result


def immutable_code():
    """New code plus inherited complete source dependency set, all committed bytes."""
    root = code_root()
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    paths = set(surface_stage.readiness_stage.code_paths(root))
    paths.update(
        str(path.relative_to(root))
        for path in (root / "trusted_data_synthesis/tests").glob(p.TEST_GLOB)
    )
    result = []
    for relative in sorted(paths):
        path = p.path_within(root, relative)
        data = path.read_bytes()
        p.require(
            data == subprocess.check_output(["git", "show", head + ":" + relative], cwd=root),
            "study.committed_dependency_bytes",
        )
        result.append({"path": relative, "sha256": p.sha(data)})
    return head, result


def verify_code(frozen):
    from . import analysis, decoder

    p.checked_record(frozen, "study_freeze")
    for row in frozen["code"]:
        p.require(
            p.sha(p.path_within(code_root(), row["path"])) == row["sha256"], "study.code_drift"
        )
    p.require(
        frozen["training_configuration"] == p.training_config()
        and frozen["execution_policy"] == p.execution_policy(),
        "study.policy_drift",
    )
    p.require(
        frozen["analysis_policy"] == analysis.policy()
        and frozen["decoder_policy"] == decoder.policy(),
        "study.analysis_and_decoder_policy_drift",
    )
    p.require(
        frozen["software_versions"]
        == {name: version(name) for name in frozen["software_versions"]},
        "study.software_drift_including_bootstrap",
    )


def freeze(root):
    """Actual bindings and pool budgets only after complete, READY original data."""
    from ..finance_qa_vnext_pq_student import model as base_model
    from . import analysis, decoder, train

    root = Path(root).resolve()
    destination = p.path_within(root, p.OUTPUT) / "preparation"
    p.require(not destination.parent.exists(), "study.no_prior_outputs_before_freeze")
    p.require(not destination.exists(), "study.one_data_bound_freeze")
    observation = collection_status(root)
    p.require(
        observation["status"] == "COMPLETE_FIXED_COLLECTION", "study.full_collection_before_Student"
    )
    _, surface, gate, _ = surface_stage.validate_surface_admission(root)
    collected, material_parent = Parent(root, p.COLLECTION), Parent(root, p.MATERIALS)
    collected.verify_all()
    material_parent.verify_all()
    manifest = material_parent.read("material_manifest.json")
    materials.checked_record(manifest, "fixed_AB_material_manifest")
    p.require(
        manifest["status"] == "FIXED_AB_MATERIALS_READY"
        and manifest["collection_id"] == collected.read("report.json")["id"],
        "study.actual_common_AB_materials_required",
    )
    incoming = collected.read("evaluation_input_binding.json")
    p.require(
        incoming["evaluation_surface_parent"] == surface.descriptor()
        and incoming["surface_gate_id"] == gate["id"],
        "study.original_collection_surface_binding",
    )
    budget = train.validate_materials(root, manifest)
    head, code = immutable_code()
    tests = sorted((code_root() / "trusted_data_synthesis/tests").glob(p.TEST_GLOB))
    p.require(tests, "study.new_executable_connection_tests")
    tested = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", *map(str, tests)],
        cwd=code_root(),
        capture_output=True,
        text=True,
    )
    p.require(tested.returncode == 0, "study.new_CPU_connection_controls")
    checkpoint = base_model.bind_checkpoint()
    tokenizer = manifest["tokenizer_binding"]
    config = decoder.bind_policy(tokenizer, checkpoint)
    registry = evaluation_registry(root)
    frozen = p.record(
        "study_freeze",
        created_at=p.now(),
        git_commit=head,
        code=code,
        software_versions={
            name: version(name)
            for name in ("numpy", "torch", "transformers", "tokenizers", "safetensors")
        },
        training_configuration=p.training_config(),
        decoder_configuration=config,
        decoder_policy=decoder.policy(),
        analysis_policy=analysis.policy(),
        execution_policy=p.execution_policy(),
        collected_parent=collected.descriptor(),
        material_parent=material_parent.descriptor(),
        materials_manifest_id=manifest["id"],
        surface_parent=surface.descriptor(),
        surface_gate_id=gate["id"],
        collection_observation=observation,
        actual_material_budget=budget,
        base_binding=checkpoint,
        tokenizer_binding=tokenizer,
        evaluation_registry=registry,
        actual_common_tasks=manifest["population_selection"]["tasks"],
        schedules={
            str(seed): design.task_batches(manifest["population_selection"], seed)
            for seed in p.SEEDS
        },
        tests={"return_code": tested.returncode, "stdout": tested.stdout, "stderr": tested.stderr},
        Student_outputs_observed=False,
        GPU_operations=0,
        tokenizer_constructions=0,
        model_shards_hashed_not_loaded=True,
        new_design_choices="2048 response cap, 10000 CIK bootstrap seed 20260912, <=8 GPU workers",
    )
    p.write_once(destination / "study_freeze.json", frozen)
    p.write_once(destination / "binding.json", binding(frozen))
    seal(destination, scope="actual complete common materials and pre-Student execution protocol")
    return frozen


def binding(frozen):
    return {
        "study_freeze_id": frozen["id"],
        "surface_manifest_id": frozen["surface_parent"]["manifest_id"],
        "materials_manifest_id": frozen["materials_manifest_id"],
        "training_config_id": frozen["training_configuration"]["id"],
        "decoder_config_id": frozen["decoder_configuration"]["id"],
    }


def available_gpus():
    raw = subprocess.check_output(
        [
            "nvidia-smi",
            "--query-gpu=index,uuid,memory.free,utilization.gpu",
            "--format=csv,noheader,nounits",
        ],
        text=True,
    )
    found = []
    for line in raw.splitlines():
        index, uuid, memory, utilization = [part.strip() for part in line.split(",")]
        if (
            int(memory) >= p.execution_policy()["minimum_free_GPU_memory_MiB"]
            and int(utilization) == 0
        ):
            found.append({"index": int(index), "uuid": uuid, "free_memory_MiB": int(memory)})
    return sorted(found, key=lambda row: row["index"])


def jobs_for(phase, *, selected=None):
    if phase == "A_train":
        return [
            {"kind": "train", "pool": "A", "arm": arm, "seed": seed}
            for seed in p.SEEDS
            for arm in p.ARMS
        ]
    if phase == "A_dev":
        return [
            {"kind": "generate", "pool": "A", "arm": arm, "seed": seed, "split": "dev"}
            for seed in p.SEEDS
            for arm in p.ARMS
        ]
    p.require(selected in p.ARMS[1:], "study.unique_positive_selected_direction")
    if phase == "B_train":
        return [
            {"kind": "train", "pool": "B", "arm": arm, "seed": seed}
            for seed in p.SEEDS
            for arm in ("alpha0", selected)
        ]
    p.require(phase == "confirm", "study.registered_execution_phase")
    return [
        {"kind": "generate", "pool": pool, "arm": arm, "seed": seed, "split": "confirm"}
        for pool in p.POOLS
        for seed in p.SEEDS
        for arm in ("alpha0", selected)
    ]


def job_name(job):
    return "_".join(str(job[key]) for key in ("kind", "pool", "arm", "seed")) + (
        "_" + job["split"] if "split" in job else ""
    )


def training_path(root, pool, arm, seed):
    return Path(root) / p.OUTPUT / "training" / f"{pool}_{arm}_{seed}"


def generation_path(root, pool, arm, seed, split):
    return Path(root) / p.OUTPUT / "generation" / split / f"{pool}_{arm}_{seed}"


def public_generation_input(root, frozen, job):
    directory = training_path(root, job["pool"], job["arm"], job["seed"])
    report = p.checked_record(p.read_json(directory / "report.json"), "training_report")
    p.require(
        report["status"] == "COMPLETE_FINAL_CHECKPOINT" and report["actual_complete"] is True,
        "study.only_real_final_adapter_before_public_worker",
    )
    p.require(
        all(report[key] == value for key, value in binding(frozen).items()),
        "study.public_worker_binding",
    )
    p.require(
        all(report[key] == job[key] for key in ("pool", "arm", "seed")),
        "study.public_worker_variant",
    )
    adapter = report["final_adapter"]
    p.require(
        p.sha(directory / adapter["path"]) == adapter["sha256"], "study.public_worker_adapter_bytes"
    )
    identity = p.record(
        "model_identity",
        **binding(frozen),
        **{key: report[key] for key in ("pool", "arm", "seed", "checkpoint_id", "final_adapter")},
        training_report_id=report["id"],
        base_binding_id=frozen["base_binding"]["id"],
        tokenizer_binding_id=frozen["tokenizer_binding"]["id"],
        adapter_directory=str(directory.relative_to(root)),
    )
    return {
        "model_identity": identity,
        "base_binding": frozen["base_binding"],
        "tokenizer_binding": frozen["tokenizer_binding"],
        "decoder_configuration": frozen["decoder_configuration"],
        "surface_directory": p.SURFACES,
        "surface_manifest_id": p.SURFACE_MANIFEST_ID,
        "split": job["split"],
        "output_directory": str(
            generation_path(root, job["pool"], job["arm"], job["seed"], job["split"]).relative_to(
                root
            )
        ),
    }


def run_jobs(root, frozen, phase, *, selected=None, poll_seconds=10):
    """Separate process per fixed job; never reuse a failed or partial output."""
    root = Path(root).resolve()
    directory = root / p.OUTPUT / "jobs" / phase
    p.require(not directory.exists(), "study.no_phase_reexecution")
    jobs = jobs_for(phase, selected=selected)
    p.write_once(
        directory / "registry.json",
        p.record("worker_registry", phase=phase, jobs=jobs, **binding(frozen)),
    )
    pending, running, finished, failures = list(jobs), {}, [], []
    while pending or running:
        for name, current in list(running.items()):
            code = current["process"].poll()
            if code is None:
                continue
            current["log"].close()
            job = current["job"]
            outcome = p.record(
                "worker_exit", job=job, return_code=code, gpu=current["gpu"], finished_at=p.now()
            )
            p.write_once(directory / (name + "_exit.json"), outcome)
            (finished if code == 0 else failures).append(outcome)
            del running[name]
        if not failures and pending:
            used = {row["gpu"]["uuid"] for row in running.values()}
            free = [row for row in available_gpus() if row["uuid"] not in used]
            while (
                pending
                and free
                and len(running) < p.execution_policy()["maximum_parallel_GPU_workers"]
            ):
                verify_code(frozen)
                job, gpu = pending.pop(0), free.pop(0)
                name = job_name(job)
                worker = directory / (name + "_job.json")
                payload = (
                    {"public_generation_input": public_generation_input(root, frozen, job)}
                    if job["kind"] == "generate"
                    else {}
                )
                p.write_once(
                    worker,
                    p.record(
                        "worker_job",
                        job=job,
                        gpu=gpu,
                        launched_at=p.now(),
                        **binding(frozen),
                        **payload,
                    ),
                )
                env = dict(os.environ)
                env.update(p.execution_policy()["worker_environment"])
                env["CUDA_VISIBLE_DEVICES"] = gpu["uuid"]
                env["PYTHONPATH"] = os.pathsep.join(
                    str(code_root() / relative)
                    for relative in ("raw_financial_data_lake", "trusted_data_synthesis/src")
                )
                log = (directory / (name + ".log")).open("xb")
                command = [
                    sys.executable,
                    "-m",
                    "trusted_synthesis.experiments.finance_qa_vnext_basis_student.worker",
                    "--root",
                    str(root),
                    "--job",
                    str(worker),
                ]
                process = subprocess.Popen(
                    command, cwd=code_root(), env=env, stdout=log, stderr=subprocess.STDOUT
                )
                running[name] = {"process": process, "log": log, "job": job, "gpu": gpu}
        if failures and not running:
            break
        if pending or running:
            time.sleep(poll_seconds)
    result = p.record(
        "worker_phase_report",
        phase=phase,
        **binding(frozen),
        status="COMPLETE_FIXED_WORKERS" if not failures and not pending else "STOP_WORKER_FAILURE",
        planned=len(jobs),
        finished=finished,
        failures=failures,
        not_started=pending,
        retries=0,
        partial_output_reused=False,
    )
    p.write_once(directory / "report.json", result)
    p.require(
        result["status"] == "COMPLETE_FIXED_WORKERS", "study.worker_failure_no_adaptive_recovery"
    )
    return result


def training_reports(root, jobs, frozen):
    reports = []
    for job in jobs:
        directory = training_path(root, job["pool"], job["arm"], job["seed"])
        report = p.checked_record(p.read_json(directory / "report.json"), "training_report")
        p.require(
            report["status"] == "COMPLETE_FINAL_CHECKPOINT" and report["actual_complete"] is True,
            "study.real_final_training_report",
        )
        p.require(
            all(report[key] == value for key, value in binding(frozen).items()),
            "study.training_binding",
        )
        p.require(
            all(report[key] == job[key] for key in ("pool", "arm", "seed")),
            "study.training_job_join",
        )
        budget = frozen["actual_material_budget"]["pool_budgets"][job["pool"]]
        p.require(
            report["target_tokens"] == budget["target_tokens_all_epochs"]
            and report["sequence_tokens"] == budget["sequence_tokens_all_epochs"]
            and report["optimizer_updates"] == 10 * frozen["actual_common_tasks"] // 5,
            "study.actual_training_token_and_update_budget",
        )
        adapter = report["final_adapter"]
        p.require(
            p.sha(directory / adapter["path"]) == adapter["sha256"], "study.final_checkpoint_bytes"
        )
        reports.append(report)
    for seed in p.SEEDS:
        paired = [row for row in reports if row["seed"] == seed]
        p.require(
            len({row["initial_adapter_digest"] for row in paired}) == 1,
            "study.paired_seed_initialization",
        )
        p.require(len({row["schedule_id"] for row in paired}) == 1, "study.paired_task_schedule")
    return reports


def score_jobs(root, jobs, frozen):
    from . import evaluation

    reports = []
    for job in jobs:
        generated = generation_path(root, job["pool"], job["arm"], job["seed"], job["split"])
        output = (
            Path(root)
            / p.OUTPUT
            / "scores"
            / job["split"]
            / f"{job['pool']}_{job['arm']}_{job['seed']}"
        )
        manifest = p.read_json(generated / "manifest.json")
        reports.append(
            evaluation.score(
                root, generated, output, expected_generation_manifest_id=manifest["id"]
            )
        )
    return reports


def run(root):
    from . import analysis

    root = Path(root).resolve()
    preparation = Parent(root, p.OUTPUT + "/preparation")
    preparation.verify_all()
    frozen = preparation.read("study_freeze.json")
    verify_code(frozen)
    p.require(
        collection_status(root)["status"] == "COMPLETE_FIXED_COLLECTION",
        "study.original_full_batch_remains_closed",
    )
    destination = root / p.OUTPUT
    p.write_once(
        destination / "execution_started.json",
        p.record("execution_started", at=p.now(), **binding(frozen)),
    )
    run_jobs(root, frozen, "A_train")
    a_training = training_reports(root, jobs_for("A_train"), frozen)
    run_jobs(root, frozen, "A_dev")
    dev = score_jobs(root, jobs_for("A_dev"), frozen)
    decision = analysis.select_actual_direction(
        a_training, dev, binding=binding(frozen), dev_tasks=frozen["evaluation_registry"]["dev"]
    )
    p.write_once(destination / "decision.json", decision)
    selected = decision["selected_arm"]
    if selected == "alpha0":
        report = p.record(
            "study_report",
            status="COMPLETE_NO_POSITIVE_DIRECTION",
            actual_complete=True,
            **binding(frozen),
            decision_id=decision["id"],
            actual_training_runs=9,
            actual_evaluation_sessions=1620,
            B_candidate_runs=0,
            independent_positive_effect_confirmed=False,
        )
    else:
        run_jobs(root, frozen, "B_train", selected=selected)
        b_training = training_reports(root, jobs_for("B_train", selected=selected), frozen)
        training_reports(root, jobs_for("A_train") + jobs_for("B_train", selected=selected), frozen)
        run_jobs(root, frozen, "confirm", selected=selected)
        confirm = score_jobs(root, jobs_for("confirm", selected=selected), frozen)
        result = analysis.confirm_actual(
            decision,
            a_training + b_training,
            confirm,
            binding=binding(frozen),
            confirm_tasks=frozen["evaluation_registry"]["confirm"],
        )
        p.write_once(destination / "confirmation.json", result)
        report = p.record(
            "study_report",
            status="COMPLETE_FIXED_CONFIRMATION",
            actual_complete=True,
            **binding(frozen),
            decision_id=decision["id"],
            confirmation_id=result["id"],
            actual_training_runs=15,
            actual_evaluation_sessions=10260,
            primary_pool="B",
            auxiliary_pool="A",
        )
    verify_code(frozen)
    p.write_once(destination / "report.json", report)
    seal(
        destination,
        scope=(
            "actual fixed-material finite distribution study; all run/failure denominators retained"
        ),
    )
    return report


def advance(root):
    """Advance only a completed parent, never create a substitute collection."""
    root = Path(root).resolve()
    observation = collection_status(root)
    if observation["status"] != "COMPLETE_FIXED_COLLECTION":
        return observation
    material_path = root / p.MATERIALS
    if not material_path.exists():
        surface_stage.materialize(root)
    material_parent = Parent(root, p.MATERIALS)
    material_parent.verify_all()
    try_publish(
        root,
        [p.COLLECTION, p.MATERIALS],
        "Publish closed fixed A/B collection and original common material outcome",
    )
    manifest = material_parent.read("material_manifest.json")
    materials.checked_record(manifest, "fixed_AB_material_manifest")
    if manifest["status"] != "FIXED_AB_MATERIALS_READY":
        p.require(
            manifest["status"] == "STOP_INSUFFICIENT_COMMON_AB_MATERIALS",
            "study.known_material_terminal",
        )
        result = p.record(
            "study_input_terminal",
            status="STOP_INSUFFICIENT_COMMON_AB_MATERIALS",
            collection=Parent(root, p.COLLECTION).descriptor(),
            material_parent=material_parent.descriptor(),
            material_manifest_id=manifest["id"],
            selection=manifest["population_selection"],
            Student_training_runs=0,
            GPU_operations=0,
            source_or_Teacher_topup=0,
        )
        p.write_once(root / p.OUTPUT / "report.json", result)
        seal(
            root / p.OUTPUT,
            scope="actual completed collection has insufficient common materials; no Student",
        )
        return result
    freeze(root)
    return run(root)


def try_publish(root, directories, message):
    """Publication cannot silently alter scientific inputs or become a new gate."""
    from . import publication

    location = (
        Path(root)
        / "trusted_data_synthesis/artifacts/qa_vnext_basis_student/runtime_20260912/publications"
    )
    index = len(list(location.glob("*.json"))) if location.exists() else 0
    try:
        result = publication.publish(root, directories, message=message)
    except Exception as error:
        result = p.record(
            "publication_failure",
            at=p.now(),
            directories=directories,
            error_type=type(error).__name__,
            reason=str(error),
            scientific_records_retained=True,
            scientific_trial_restarted=False,
        )
    p.write_once(location / f"{index:04d}.json", result)
    return result


def follow(root):
    """Durable bounded-interval monitor, followed by the same admitted pipeline."""
    root = Path(root).resolve()
    runtime = root / "trusted_data_synthesis/artifacts/qa_vnext_basis_student/runtime_20260912"
    p.write_once(
        runtime / "follow_started.json",
        p.record(
            "follow_started",
            at=p.now(),
            pid=os.getpid(),
            git_commit=subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=code_root(), text=True
            ).strip(),
            collection_directory=p.COLLECTION,
            collection_will_not_be_started_again=True,
            poll_seconds=30,
        ),
    )
    index = 0
    try:
        while True:
            state = collection_status(root)
            p.write_once(runtime / "observations" / f"{index:06d}.json", state)
            index += 1
            print(json.dumps(state, ensure_ascii=False), flush=True)
            if state["status"] not in {"COLLECTION_RUNNING", "COLLECTION_STOPPING"}:
                break
            time.sleep(30)
        result = advance(root)
        closed = [
            name
            for name in (p.COLLECTION, p.MATERIALS, p.OUTPUT)
            if (root / name / "manifest.json").is_file()
        ]
        publication = try_publish(
            root, closed, "Publish actual fixed-material Student study terminal evidence"
        )
        p.write_once(
            runtime / "follow_completed.json",
            p.record("follow_completed", at=p.now(), result=result, publication=publication),
        )
        return result
    except Exception as error:
        p.write_once(
            runtime / "follow_failed.json",
            p.record(
                "follow_failed",
                at=p.now(),
                error_type=type(error).__name__,
                reason=str(error),
                automatic_retry=False,
                original_collection_untouched=True,
            ),
        )
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("status", "advance", "follow", "freeze", "run"))
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    result = {
        "status": collection_status,
        "advance": advance,
        "freeze": freeze,
        "run": run,
        "follow": follow,
    }[args.phase](args.root)
    print(json.dumps(result, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
