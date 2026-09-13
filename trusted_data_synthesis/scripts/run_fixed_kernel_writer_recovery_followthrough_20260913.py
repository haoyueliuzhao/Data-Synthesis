"""One-shot external operator for the already-running fixed-kernel recovery.

This file is intentionally outside the frozen scientific package/test glob.
It polls immutable producer records, delegates to the frozen prepare/run/seal
entry points, and never changes scientific tasks, sampling, parameters or gates.
The operator itself neither opens a wallet nor reads credentials. The existing
publisher, in its separately launched seal process, retains its own secret-scan
contract. Running this module is an explicit authorization to launch the already
registered Student workflow after its existing material gate passes.
"""

import argparse
import fcntl
import hashlib
import importlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

PACKAGE = "trusted_synthesis.experiments.finance_qa_vnext_fixed_kernel_value"
STUDENT_DIRECTORY = "student_execution"
STAGES = ("materials_seal", "prepare", "execute", "results_seal")


def load_protocol(code_root):
    code_root = Path(code_root).resolve()
    sys.path.insert(0, str(code_root / "trusted_data_synthesis/src"))
    sys.path.insert(0, str(code_root / "raw_financial_data_lake"))
    protocol = importlib.import_module(PACKAGE + ".protocol")
    protocol.require(
        Path(protocol.__file__).resolve().is_relative_to(code_root),
        "operator.correct_frozen_package_location",
    )
    return protocol


def script_sha():
    return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def verify_operator_source(workflow, p):
    """Operator provenance only; do not re-evaluate any scientific input."""
    started = p.checked(p.read_json(workflow / "started.json"), "operator_workflow_started")
    p.require(
        started["operator_source_path"] == str(Path(__file__).resolve())
        and started["operator_source_sha256"] == script_sha(),
        "operator.source_changed_after_start",
    )
    return started


def read_closed_gate(raw, p):
    """Only closure/identity joins; financial qualification remains upstream."""
    names = ("material_gate.json", "generation_report.json", "budget_finalization.json")
    if not all((raw / name).is_file() for name in names):
        return None
    try:
        gate, generation, finalization = [p.read_json(raw / name) for name in names]
    except (FileNotFoundError, json.JSONDecodeError, UnicodeDecodeError):
        # A write-once file may be visible just before its final flush/fsync.
        return None
    p.checked(gate, "material_gate")
    p.checked(generation, "material_generation_report")
    p.checked(finalization, "kernel_budget_finalization")
    p.require(
        generation["generation_closed"] is True
        and generation["no_inflight_requests"] is True
        and finalization["purpose_closed"] is True,
        "operator.existing_generation_and_budget_closure",
    )
    p.require(
        gate["generation_report_id"] == generation["id"] == finalization["report_id"]
        and gate["registry_id"] == generation["registry_id"]
        and generation["freeze_id"] == finalization["freeze_id"],
        "operator.original_producer_identity_join",
    )
    p.require(gate["training_gate"] in ("PASS", "FAIL"), "operator.existing_terminal_gate")
    return dict(gate=gate, generation=generation, finalization=finalization)


def execution_report(raw, p):
    report = p.checked(p.read_json(raw / STUDENT_DIRECTORY / "report.json"), "execution_report")
    p.require(
        report["actual_complete"] is True
        and report["status"] in {"COMPLETE_NO_POSITIVE_DIRECTION", "COMPLETE_FIXED_CONFIRMATION"},
        "operator.existing_actual_execution_terminal",
    )
    return report


def internal_stage(stage, code_root, data_root, p):
    """Fresh process; call frozen producers without modifying their globals."""
    operator_start = verify_operator_source(code_root / (p.OUTPUT + "_workflow"), p)
    raw = code_root / p.OUTPUT
    student = raw / STUDENT_DIRECTORY
    if stage in ("prepare", "execute"):
        execution = importlib.import_module(PACKAGE + ".execution")
        if stage == "prepare":
            result = execution.prepare(
                code_root,
                student,
                source_root=data_root,
                study_freeze_id=p.read_json(raw / "freeze.json")["id"],
                population_path=raw / "population.json",
                registry_path=raw / "registry.json",
                materialization_index_path=raw / "materialization_index.json",
                base_binding=p.read_json(raw / "checkpoint_binding.json"),
                tokenizer_binding=p.read_json(raw / "tokenizer_binding.json"),
            )
        else:
            result = execution.run(code_root, student / "preparation/execution_freeze.json")
    else:
        publication = importlib.import_module(PACKAGE + ".publish")
        p.require(
            STUDENT_DIRECTORY in publication.STUDENT_PARTS,
            "operator.existing_material_seal_excludes_student_directory",
        )
        if stage == "materials_seal":
            result = publication.seal_stage(code_root, data_root, "materials")
        else:
            report = execution_report(raw, p)
            decision = p.checked(
                p.read_json(student / "decision.json"), "actual_direction_decision"
            )
            execution = importlib.import_module(PACKAGE + ".execution")
            jobs = execution.jobs_for("A_train")
            if report["status"] == "COMPLETE_FIXED_CONFIRMATION":
                jobs += execution.jobs_for("B_train", decision["selected_arm"])
            approved = [
                str(
                    Path(STUDENT_DIRECTORY)
                    / "training"
                    / f"{job['pool']}_{job['arm']}_{job['seed']}"
                    / "final_adapter.safetensors"
                )
                for job in jobs
            ]
            result = publication.seal_stage(
                code_root,
                data_root,
                "results",
                allowlist=[STUDENT_DIRECTORY],
                report_path=STUDENT_DIRECTORY + "/report.json",
                approved_adapter_paths=approved,
            )
    workflow = code_root / (p.OUTPUT + "_workflow")
    receipt = p.record(
        "operator_stage_result",
        stage=stage,
        result_id=result["id"],
        result_status=result.get("status"),
        actual_complete=result.get("actual_complete"),
        operator_source_sha256=operator_start["operator_source_sha256"],
        operator_started_id=operator_start["id"],
        ended_at=p.now(),
        delegated_to_frozen_producer=True,
        producer_result_relabelled=False,
    )
    p.write_once(workflow / "stages" / stage / "result.json", receipt)
    print(p.encode(receipt).decode(), flush=True)
    return receipt


class Launcher:
    def __init__(self, code_root, data_root, workflow, p, emit):
        self.code_root, self.data_root, self.workflow = code_root, data_root, workflow
        self.p, self.emit = p, emit
        self.jobs = {}

    def start(self, stage):
        p = self.p
        verify_operator_source(self.workflow, p)
        p.require(stage not in self.jobs, "operator.stage_launched_once")
        directory = self.workflow / "stages" / stage
        command = [
            sys.executable,
            str(Path(__file__).resolve()),
            "--code-root",
            str(self.code_root),
            "--data-root",
            str(self.data_root),
            "--internal-stage",
            stage,
        ]
        p.write_once(
            directory / "command.json",
            p.record(
                "operator_stage_command",
                stage=stage,
                argv=command,
                cwd=str(self.code_root),
                operator_source_sha256=script_sha(),
                automatic_retry=False,
                inherited_environment_dumped=False,
                GPU_allocation_delegated_to_frozen_execution=True,
            ),
        )
        stream = (directory / "console.log").open("xb")
        try:
            process = subprocess.Popen(
                command,
                cwd=self.code_root,
                stdout=stream,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
        except BaseException:
            stream.close()
            raise
        self.jobs[stage] = dict(process=process, stream=stream, exit=None)
        p.write_once(
            directory / "started.json",
            p.record(
                "operator_stage_started",
                stage=stage,
                pid=process.pid,
                started_at=p.now(),
                command_path=str(directory / "command.json"),
                log_path=str(directory / "console.log"),
            ),
        )
        self.emit("stage_started", stage=stage, pid=process.pid, log=str(directory / "console.log"))

    def poll(self, stage):
        job = self.jobs[stage]
        if job["exit"] is not None:
            return job["exit"]
        code = job["process"].poll()
        if code is None:
            return None
        job["stream"].close()
        job["exit"] = code
        self.p.write_once(
            self.workflow / "stages" / stage / "exit.json",
            self.p.record(
                "operator_stage_exit",
                stage=stage,
                pid=job["process"].pid,
                return_code=code,
                ended_at=self.p.now(),
                automatic_retry=False,
            ),
        )
        self.emit("stage_exited", stage=stage, return_code=code)
        return code

    def active_pids(self):
        return {
            stage: job["process"].pid
            for stage, job in self.jobs.items()
            if job["process"].poll() is None
        }


def supervise(
    code_root,
    data_root,
    *,
    poll_seconds=10,
    p=None,
    launcher_factory=Launcher,
    sleeper=time.sleep,
    gate_reader=read_closed_gate,
    report_reader=execution_report,
):
    code_root, data_root = Path(code_root).resolve(), Path(data_root).resolve()
    p = load_protocol(code_root) if p is None else p
    p.require(0 < poll_seconds <= 60, "operator.bounded_poll_interval")
    raw = code_root / p.OUTPUT
    workflow = code_root / (p.OUTPUT + "_workflow")
    runtime = code_root / p.RUNTIME
    p.require(
        not workflow.is_relative_to(raw) and not runtime.is_relative_to(raw),
        "operator.audit_and_lock_outside_raw",
    )
    runtime.mkdir(parents=True, exist_ok=True)
    with (runtime / "followthrough_operator.lock").open("a+b") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        p.require(not (workflow / "started.json").exists(), "operator.one_shot_no_resume_or_retry")
        started = p.record(
            "operator_workflow_started",
            pid=os.getpid(),
            started_at=p.now(),
            code_root=str(code_root),
            data_root=str(data_root),
            raw_directory=str(raw),
            operator_source_path=str(Path(__file__).resolve()),
            operator_source_sha256=script_sha(),
            argv=list(sys.argv),
            scientific_gate_reimplemented=False,
            new_sampling=False,
            scientific_parameters_changed=False,
            Git_operations=0,
            process_launcher_injected=launcher_factory is not Launcher,
        )
        p.write_once(workflow / "started.json", started)
        with (workflow / "events.jsonl").open("xb") as events:
            index = 0

            def emit(event, **fields):
                nonlocal index
                index += 1
                value = p.record(
                    "operator_workflow_event", index=index, event=event, time=p.now(), **fields
                )
                events.write(p.encode(value) + b"\n")
                events.flush()
                os.fsync(events.fileno())
                print(p.encode(value).decode(), flush=True)

            launcher = launcher_factory(code_root, data_root, workflow, p, emit)
            phase, codes, report, closed = "wait_material_gate", {}, None, None

            def start_publication(stage):
                try:
                    launcher.start(stage)
                except Exception as error:
                    codes[stage] = -1
                    emit(
                        "publication_spawn_failed",
                        stage=stage,
                        error_type=type(error).__name__,
                        automatic_retry=False,
                    )

            def poll_stage(stage):
                return codes[stage] if stage in codes else launcher.poll(stage)

            try:
                while closed is None:
                    closed = gate_reader(raw, p)
                    if closed is None:
                        emit("waiting_existing_material_gate", raw_directory=str(raw))
                        sleeper(poll_seconds)
                gate = closed["gate"]
                p.write_once(
                    workflow / "observed_closure.json",
                    p.record(
                        "operator_observed_closure",
                        observed_at=p.now(),
                        gate=gate,
                        generation_report_id=closed["generation"]["id"],
                        budget_finalization_id=closed["finalization"]["id"],
                        original_records_modified=False,
                    ),
                )
                emit(
                    "existing_material_gate_closed",
                    gate_id=gate["id"],
                    training_gate=gate["training_gate"],
                )
                phase = "materials_seal"
                # The independent publication must not become a training gate.
                start_publication("materials_seal")
                if gate["training_gate"] == "FAIL":
                    while (code := poll_stage("materials_seal")) is None:
                        sleeper(poll_seconds)
                    codes["materials_seal"] = code
                    status = "STOP_EXISTING_MATERIAL_GATE_FAIL"
                else:
                    phase = "prepare"
                    launcher.start("prepare")
                    while (code := launcher.poll("prepare")) is None:
                        poll_stage("materials_seal")
                        sleeper(poll_seconds)
                    codes["prepare"] = code
                    if code != 0:
                        raise RuntimeError("existing_execution_prepare_failed_no_retry")
                    phase = "execute"
                    launcher.start("execute")
                    while (code := launcher.poll("execute")) is None:
                        poll_stage("materials_seal")
                        sleeper(poll_seconds)
                    codes["execute"] = code
                    if code != 0:
                        raise RuntimeError("existing_execution_failed_no_retry")
                    report = report_reader(raw, p)
                    # Never seal synthetic or partial Student results.
                    p.require(report["actual_complete"] is True, "operator.actual_result_required")
                    phase = "results_seal"
                    start_publication("results_seal")
                    while (code := poll_stage("results_seal")) is None:
                        poll_stage("materials_seal")
                        sleeper(poll_seconds)
                    codes["results_seal"] = code
                    while (code := poll_stage("materials_seal")) is None:
                        sleeper(poll_seconds)
                    codes["materials_seal"] = code
                    status = (
                        "COMPLETE_ACTUAL_EXECUTION_AND_SEALS"
                        if all(value == 0 for value in codes.values())
                        else "COMPLETE_ACTUAL_EXECUTION_PUBLICATION_FAILED"
                    )
                terminal = p.record(
                    "operator_workflow_terminal",
                    status=status,
                    ended_at=p.now(),
                    started_id=started["id"],
                    material_gate_id=gate["id"],
                    child_exit_codes=codes,
                    actual_execution_report_id=report["id"] if report else None,
                    actual_execution_complete=bool(report and report["actual_complete"]),
                    source_script_sha256=started["operator_source_sha256"],
                    active_child_pids=launcher.active_pids(),
                    automatic_retry=False,
                    operator_added_scientific_gate=False,
                    process_launcher_injected=started["process_launcher_injected"],
                    Git_operations=0,
                )
                p.write_once(workflow / "terminal.json", terminal)
                emit("workflow_terminal", status=status, terminal_id=terminal["id"])
                return terminal
            except BaseException as error:
                # Preserve independent in-flight work. Never restart a scientific
                # phase or terminate somebody else's GPU worker as compensation.
                terminal = p.record(
                    "operator_workflow_terminal",
                    status="STOP_OPERATOR_OR_CHILD_FAILURE",
                    phase=phase,
                    ended_at=p.now(),
                    started_id=started["id"],
                    child_exit_codes=codes,
                    active_child_pids=launcher.active_pids(),
                    material_gate_id=closed["gate"]["id"] if closed else None,
                    source_script_sha256=started["operator_source_sha256"],
                    operator_added_scientific_gate=False,
                    process_launcher_injected=started["process_launcher_injected"],
                    error_type=type(error).__name__,
                    error=str(error)[:2000],
                    actual_execution_report_id=report["id"] if report else None,
                    actual_execution_complete=bool(report and report["actual_complete"]),
                    automatic_retry=False,
                    in_flight_children_not_killed=True,
                    Git_operations=0,
                )
                if not (workflow / "terminal.json").exists():
                    p.write_once(workflow / "terminal.json", terminal)
                emit("workflow_failed", phase=phase, error_type=type(error).__name__)
                raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--code-root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument(
        "--data-root", type=Path, default=Path("/data1/zhuxinrui/projects/Data-Synthesis")
    )
    parser.add_argument("--poll-seconds", type=float, default=10)
    parser.add_argument("--internal-stage", choices=STAGES, help=argparse.SUPPRESS)
    args = parser.parse_args()
    code_root, data_root = args.code_root.resolve(), args.data_root.resolve()
    p = load_protocol(code_root)
    if args.internal_stage:
        internal_stage(args.internal_stage, code_root, data_root, p)
    else:
        supervise(code_root, data_root, poll_seconds=args.poll_seconds, p=p)


if __name__ == "__main__":
    main()
