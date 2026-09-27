"""Resume the frozen evaluation after exactly the missing-CuBLAS launch fault.

The new contract freezes old failure bytes before reclassification in memory.
Original outcomes, scientific protocol, decoder, scorer and budgets are retained.
"""

import argparse
import copy
import json
import os
import subprocess
from pathlib import Path
from types import SimpleNamespace

import cross_market_repaired_geometry_execution_20260926 as isolation
import run_fixed_kernel_cross_market_evaluation_20260926 as previous

p = previous.p
SCRIPT = "trusted_data_synthesis/scripts/run_cross_market_cuda_recovery_20260927.py"
PROTOCOL = "cross_market_cuda_launch_recovery_protocol"
DIRECTORY = "cuda_launch_recovery_01"
ENVIRONMENT = {"CUBLAS_WORKSPACE_CONFIG": ":4096:8"}
MISSING_CUBLAS_MESSAGE = (
    "fixed_kernel.feedback.decoder_fault_not_zero_reward:RuntimeError: "
    "Deterministic behavior was enabled with either `torch.use_deterministic_algorithms(True)` "
    "or `at::Context::setDeterministicAlgorithms(true)`, but this operation is not deterministic "
    "because it uses CuBLAS and you have CUDA >= 10.2. To enable deterministic behavior in this "
    "case, you must set an environment variable before running your PyTorch application: "
    "CUBLAS_WORKSPACE_CONFIG=:4096:8 or CUBLAS_WORKSPACE_CONFIG=:16:8. For more information, "
    "go to https://docs.nvidia.com/cuda/cublas/index.html#results-reproducibility"
)


def require(condition, reason):
    p.require(condition, "cross_market_cuda_recovery." + reason)


def context(raw=None):
    raw = Path(previous.RAW if raw is None else raw).resolve()
    require(raw == previous.RAW.resolve(), "fixed_existing_evaluation_root")
    return previous.evaluation.Context(raw)


def reference(path):
    path = Path(path).resolve()
    return dict(path=str(path), sha256=p.sha(path), bytes=path.stat().st_size)


def checked_reference(value):
    require(reference(value["path"]) == value, "unchanged_frozen_artifact")
    return p.read_json(value["path"])


def missing_cublas(job, outcome):
    return (
        job["work_kind"] == "generate"
        and outcome is not None
        and outcome.get("status") == "FATAL"
        and outcome.get("exception_type") == "ValueError"
        and outcome.get("message") == MISSING_CUBLAS_MESSAGE
    )


def failure_entry(c, job, row):
    directory = c.RAW / "control/attempts" / job["key"] / str(row["attempt"])
    return dict(
        job_key=job["key"],
        job_id=job["id"],
        attempt=row["attempt"],
        artifacts={
            name: reference(directory / (name + ".json"))
            for name in ("reserved", "started", "launched", "outcome")
            if (directory / (name + ".json")).exists()
        },
        job=reference(c.RAW / "jobspecs" / (job["key"] + ".json")),
    )


def register(root, raw=None):
    root, c = Path(root).resolve(), context(raw)
    output = c.RAW / DIRECTORY
    with c.locked(c.RAW / "control/coordinator.lock", blocking=False):
        if (output / "protocol.json").exists():
            return protocol(root, c.RAW)
        original = c.read_protocol(root)
        budget = c._budget_state()
        require(
            not budget.get("committed_generation")
            and budget.get("counts", {}).get("score_case", 0) == 0
            and not (c.RAW / "generation_seal.json").exists()
            and not (c.RAW / "complete.json").exists(),
            "before_any_committed_generation_or_private_scoring",
        )
        failures = []
        for path in sorted((c.RAW / "jobspecs").glob("*.json")):
            job = p.checked(p.read_json(path), "cross_market_evaluation_work_unit")
            require(job["protocol_id"] == original["id"], "same_registered_work_unit")
            for row in previous.attempts(c, job):
                process = row["process"]
                require(
                    process is not None
                    and process["process_identity"] is not None
                    and not row["alive"]
                    and row["outcome"] is not None,
                    "all_original_attempts_settled_and_workers_exited",
                )
                if missing_cublas(job, row["outcome"]):
                    failures.append(failure_entry(c, job, row))
        require(bool(failures), "explicit_existing_missing_cublas_failures")
        head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
        sources = {}
        for name in (SCRIPT, isolation.SCRIPT):
            payload = (root / name).read_bytes()
            require(
                payload == subprocess.check_output(["git", "show", head + ":" + name], cwd=root),
                "committed_recovery_before_execution",
            )
            sources[name] = p.sha(payload)
        plan = p.record(
            PROTOCOL,
            frozen=True,
            evaluation_protocol=reference(c.RAW / "protocol.json"),
            evaluation_protocol_id=original["id"],
            scientific_sources=original["scientific_sources"],
            runtime_binding=original["materials"]["runtime_binding"],
            code_commit=head,
            sources=sources,
            environment=ENVIRONMENT,
            allowed_failures=failures,
            registered_budget_snapshot=copy.deepcopy(budget),
            physical_budget=original["physical_budget"],
            scheduling=original["scheduling"],
            original_outcomes_immutable=True,
            original_budget_not_refunded=True,
            only_frozen_exact_missing_cublas_generation_failures_reclassified=True,
            no_private_scoring_failure_reclassification=True,
            new_training_updates=0,
            new_API_calls=0,
            at=p.now(),
        )
        c.write(output / "protocol.json", plan)
        return plan


def protocol(root, raw=None):
    root, c = Path(root).resolve(), context(raw)
    plan = p.checked(p.read_json(c.RAW / DIRECTORY / "protocol.json"), PROTOCOL)
    original = c.read_protocol(root)
    require(
        plan["frozen"] is True
        and plan["environment"] == ENVIRONMENT
        and checked_reference(plan["evaluation_protocol"]) == original
        and plan["evaluation_protocol_id"] == original["id"]
        and plan["physical_budget"] == original["physical_budget"]
        and plan["scheduling"] == original["scheduling"]
        and plan["scientific_sources"] == original["scientific_sources"]
        and plan["runtime_binding"] == original["materials"]["runtime_binding"],
        "same_existing_science_and_finite_budgets",
    )
    for name, digest in plan["sources"].items():
        require(p.sha(root / name) == digest, "frozen_recovery_source:" + name)
    require(bool(plan["allowed_failures"]), "nonempty_frozen_failure_scope")
    for entry in plan["allowed_failures"]:
        job = checked_reference(entry["job"])
        artifacts = {name: checked_reference(ref) for name, ref in entry["artifacts"].items()}
        process = artifacts.get("started") or artifacts.get("launched")
        require(
            job["key"] == entry["job_key"]
            and job["id"] == entry["job_id"]
            and job["protocol_id"] == original["id"]
            and missing_cublas(job, artifacts["outcome"])
            and process is not None
            and process["process_identity"] is not None
            and previous.process_identity(process["pid"]) != process["process_identity"],
            "same_settled_exact_failure",
        )
    return plan


def controller_namespace(plan):
    environment = {**os.environ, **ENVIRONMENT}
    namespace = isolation.isolated_namespace(
        previous, SCRIPT=SCRIPT, os=SimpleNamespace(**{**vars(os), "environ": environment})
    )
    allowed = {(row["job_key"], row["attempt"]): row for row in plan["allowed_failures"]}

    def attempts(c, job):
        rows = previous.attempts(c, job)
        for row in rows:
            entry = allowed.get((job["key"], row["attempt"]))
            if entry is None or not missing_cublas(job, row["outcome"]):
                continue
            require(
                job["id"] == entry["job_id"]
                and not row["alive"]
                and failure_entry(c, job, row) == entry,
                "exact_registered_failure_before_memory_only_retry",
            )
            row["outcome"] = {
                **row["outcome"],
                "status": "RESOURCE_RETRY",
                "cuda_recovery_protocol_id": plan["id"],
            }
        return rows

    namespace["attempts"] = attempts
    return namespace


def execute(action, root, raw=None, job=None, attempt=None):
    c = context(raw)
    if action == "register":
        return register(root, c.RAW)
    if action == "status":
        return previous.read(c.RAW / "control/status.json")
    if action == "worker":
        require(
            all(os.environ.get(key) == value for key, value in ENVIRONMENT.items()),
            "real_worker_environment_before_generation",
        )
    plan = protocol(root, c.RAW)
    namespace = controller_namespace(plan)
    if action == "worker":
        return namespace["worker"](Path(root).resolve(), c.RAW, job, attempt)
    return namespace[action](Path(root).resolve(), c.RAW)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("register", "start", "coordinate", "worker", "status"))
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--raw", type=Path, default=previous.RAW)
    parser.add_argument("--job", type=Path)
    parser.add_argument("--attempt", type=int)
    args = parser.parse_args()
    value = execute(args.action, args.root, args.raw, args.job, args.attempt)
    if args.action == "worker":
        return value
    if args.action == "register":
        print(
            json.dumps(
                dict(
                    event="cuda_launch_recovery_registered",
                    id=value["id"],
                    allowed_failed_attempts=len(value["allowed_failures"]),
                    environment=value["environment"],
                ),
                ensure_ascii=False,
            )
        )
    elif value is not None:
        print(json.dumps(value, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
