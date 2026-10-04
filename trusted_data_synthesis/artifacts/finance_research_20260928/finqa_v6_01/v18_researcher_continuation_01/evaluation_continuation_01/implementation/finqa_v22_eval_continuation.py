"""Resume the frozen evaluation tail on eight GPUs after an exact API-only source proof."""

from __future__ import annotations

import argparse
import contextlib
import fcntl
import hashlib
import importlib
import json
import signal
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import finqa_v22_provider_compat as provider_compat

REPO = Path("/data1/zhuxinrui/projects/Data-Synthesis")
V18 = (
    REPO
    / "trusted_data_synthesis/artifacts/finance_research_20260928/finqa_v6_01"
    / "v18_researcher_continuation_01"
)
OLD_ROOT = V18 / "six_gpu_queue_01"
ROOT = V18 / "evaluation_continuation_01"
FROZEN = REPO / ".codex-worktrees/finqa-v18-researcher-continuation-20260930"
FROZEN_SCRIPTS = REPO / ".codex-worktrees/finqa-v21-six-gpu-20261001/trusted_data_synthesis/scripts"
GPUS = list(range(8))


def require(condition, message):
    if not condition:
        raise ValueError(message)


def eight_gpu_require(condition, message):
    require(
        condition,
        message.replace("five-GPU", "eight-GPU")
        .replace("six-GPU", "eight-GPU")
        .replace("five GPUs", "eight GPUs")
        .replace("six GPUs", "eight GPUs"),
    )


def observed_cpu_affinity():
    rows = subprocess.check_output(
        ["nvidia-smi", "--query-gpu=index,pci.bus_id", "--format=csv,noheader"], text=True
    )
    result = {}
    for line in rows.splitlines():
        index, pci = line.split(",")
        gpu = int(index.strip())
        if gpu not in GPUS:
            continue
        domain, bus, slot = pci.strip().lower().split(":")
        device = Path("/sys/bus/pci/devices") / f"{domain[-4:]}:{bus}:{slot}"
        node = int((device / "numa_node").read_text().strip())
        require(node >= 0, "observed NUMA placement required for each authorized GPU")
        result[str(gpu)] = Path(f"/sys/devices/system/node/node{node}/cpulist").read_text().strip()
    require(set(result) == {str(g) for g in GPUS}, "all eight GPUs must be observed")
    return result


def evaluation_resource_profile(rt, root, training_profile):
    path = root / "resource_profile/record.json"
    affinity = observed_cpu_affinity()
    require(
        all(affinity[g] == cpus for g, cpus in training_profile["cpu_affinity"].items()),
        "existing six GPU CPU affinity must remain unchanged",
    )
    fixed = dict(
        schema="v22_eight_gpu_evaluation_resources.v1",
        parent_training_execution_profile=rt.entry(OLD_ROOT / "registration/record.json"),
        allowed_gpu_indices=GPUS,
        max_gpu_workers=len(GPUS),
        cpu_affinity=affinity,
        minimum_free_mib=training_profile["minimum_free_mib"],
        taskset=training_profile["taskset"],
        source_bindings=source_bindings(),
        no_training_launch=True,
        no_other_process_signal=True,
        headroom_is_not_an_OOM_guarantee=True,
    )
    require(fixed["minimum_free_mib"] == 24576, "original 24 GiB headroom required")
    if path.exists():
        value = rt.checked(path)
        require(all(value.get(k) == v for k, v in fixed.items()), "evaluation resources changed")
    else:
        value = rt.bound(dict(**fixed, at=rt.now(), user_request="八卡全部纳入可用范围"))
        rt.persist(path.parent, value)
    return value, rt.entry(path)


def source_bindings():
    return {
        p.name: hashlib.sha256(p.read_bytes()).hexdigest()
        for p in (Path(__file__), Path(provider_compat.__file__))
    }


def load_runtime():
    """New control code is external; all scientific modules remain the V18 checkout."""
    sys.path.insert(0, str(FROZEN_SCRIPTS))
    previous = importlib.import_module("finqa_v21_six_gpu_queue")
    package = importlib.import_module("trusted_synthesis.finance_research")
    require(
        Path(package.__file__).resolve().parent
        == FROZEN / "trusted_data_synthesis/src/trusted_synthesis/finance_research"
        and Path(previous.__file__).resolve() == FROZEN_SCRIPTS / "finqa_v21_six_gpu_queue.py",
        "use the original frozen V18 PYTHONPATH and V21 queue implementation",
    )
    final = importlib.import_module("trusted_synthesis.finance_research.v9_final_evaluation")
    mechanism = importlib.import_module("trusted_synthesis.finance_research.v9_mechanism_execution")
    return SimpleNamespace(
        previous=previous,
        final=final,
        mechanism=mechanism,
        checked=previous.checked,
        entry=previous.entry,
        persist=previous.persist,
        bound=previous.bound,
        now=previous.now,
        bind=previous.bind_dependencies,
    )


def require_tail_job(job):
    allowed = {
        "v9_final_evaluation": {"run-model", "resume-model"},
        "v9_mechanism_execution": {"run-seed", "evaluate-point"},
    }
    require(
        job.get("module") in allowed
        and job.get("args")
        and job["args"][0] in allowed[job["module"]]
        and not job.get("script")
        and not job["key"].startswith("arm-"),
        "evaluation continuation must never launch training or an unregistered command",
    )


def require_completed_matrix(jobs, is_complete):
    expected = {
        f"arm-{seed}-{arm}"
        for seed in (11, 29, 47)
        for arm in ("static", "c_only", "full", "manual_plus", "manual_minus")
    }
    require(
        len(jobs) == 15 and {j["key"] for j in jobs} == expected,
        "all fifteen original training results are required",
    )
    require(
        all(is_complete(j) for j in jobs),
        "an incomplete arm blocks evaluation; it must never be retrained here",
    )


def make_public_contract(rt, certificate, certificate_ref):
    """Keep original input/scorer checks and separately prove the exact provider edit."""
    original = rt.final.public_evaluation_contract
    sources = rt.final.EVALUATION_SOURCES
    require(sources.count("providers.py") == 1, "original provider guard must be present")
    strict_rest = rt.bind(
        original, EVALUATION_SOURCES=tuple(k for k in sources if k != "providers.py")
    )

    def compatible(assets_source, base_plan):
        current = rt.final.runtime_binding()
        require(current == certificate["actual_runtime_binding"], "frozen runtime changed")
        provider_path = Path(rt.final.__file__).with_name("providers.py")
        proof = provider_compat.prove_provider_compatibility(
            provider_path.read_bytes(),
            base_sha256=base_plan["runtime_binding"]["providers.py"],
            current_sha256=current["providers.py"],
        )
        require(proof == certificate["provider_proof"], "provider compatibility proof changed")
        common = strict_rest(assets_source, base_plan)
        common["evaluation_source_sha256"]["providers.py"] = current["providers.py"]
        require(
            common["evaluation_source_sha256"] == certificate["actual_evaluation_sources"],
            "report actual evaluation sources, never substitute the Base provider hash",
        )
        common["Base_source_compatibility"] = dict(
            certificate=certificate,
            certificate_ref=certificate_ref,
            original_public_contract_code_reused=True,
            all_other_public_input_and_scorer_checks_unchanged=True,
        )
        return common

    return compatible


def mechanism_inputs(rt, launcher):
    path = V18 / "mechanisms/registration/record.json"
    require(path.is_file(), "preserve the original pre-Student mechanism registration")
    plan = rt.checked(path)
    require(
        plan["runtime_binding"] == rt.final.runtime_binding()
        and Path(plan["launcher"]).resolve() == launcher.resolve(),
        "original mechanism runtime and launcher must remain unchanged",
    )
    s = plan["execution_plan"]["steps_per_epoch"]
    paths = []
    for seed in (11, 29, 47):
        root = launcher / f"seed{seed}"
        paths.extend(
            [
                root / f"shared/step{2 * s:04d}_step/state.pt",
                root / f"arms/static/training/step{3 * s:04d}_step/state.pt",
                root / f"arms/c_only/training/step{3 * s:04d}_step/state.pt",
                root / f"arms/c_only/training/step{5 * s:04d}_step/state.pt",
                root / f"arms/full/training/step{5 * s:04d}_step/state.pt",
            ]
        )
        for arm, step in (("c_only", 2 * s), ("c_only", 4 * s), ("full", 4 * s)):
            outer = root / f"arms/{arm}/training/step{step:04d}_outer"
            paths.extend([outer / "record.json", outer / "outer_inputs.pt"])
    require(all(p.is_file() for p in paths), "registered mechanism checkpoint input missing")
    return rt.entry(path), [str(p) for p in paths]


def compatibility_certificate(rt, root):
    path = root / "compatibility/record.json"
    base_file = rt.final.base.OUTPUT / "protocol.json"
    base_plan = rt.final.read_bound(base_file)
    current = rt.final.runtime_binding()
    sources = [
        *rt.final.EVALUATION_SOURCES,
        *(k for k in current if k.startswith("metric_vendor/")),
    ]
    require(len(sources) == len(set(sources)) == 13, "original thirteen-source gate required")
    require(
        all(
            current[k] == base_plan["runtime_binding"].get(k)
            for k in sources
            if k != "providers.py"
        ),
        "other public/scorer source changed",
    )
    provider_path = Path(rt.final.__file__).with_name("providers.py")
    proof = provider_compat.prove_provider_compatibility(
        provider_path.read_bytes(),
        base_sha256=base_plan["runtime_binding"]["providers.py"],
        current_sha256=current["providers.py"],
    )
    fixed = dict(
        schema="v22_exact_provider_compatibility_certificate.v1",
        Base_protocol=rt.entry(base_file),
        provider_proof=proof,
        actual_provider_source=rt.final.file_binding(provider_path),
        actual_runtime_binding=current,
        actual_evaluation_sources={k: current[k] for k in sources},
        Base_evaluation_sources={k: base_plan["runtime_binding"][k] for k in sources},
        source_bindings=source_bindings(),
        original_Base_modified=False,
        Base_rerun=False,
        API_calls=0,
        numerical_equivalence_measurement_claimed=False,
    )
    if path.exists():
        value = rt.checked(path)
        require(
            all(value.get(k) == v for k, v in fixed.items()), "compatibility certificate changed"
        )
    else:
        value = rt.bound(dict(**fixed, at=rt.now()))
        rt.persist(path.parent, value)
    return value, rt.entry(path)


def prepare_evaluation(rt, supervisor):
    root = supervisor.continuation_root
    launcher = Path(supervisor.handoff["launcher"])
    jobs = supervisor.arm_jobs(launcher)
    require_completed_matrix(jobs, supervisor.job_complete)
    resource, resource_ref = evaluation_resource_profile(rt, root, supervisor.profile)
    # Historical fields are needed by the original parent/reaper guards. The
    # new resource policy owns only subsequent evaluation/mechanism launches;
    # profile_ref remains the original training profile for completed arms.
    supervisor.profile = {**supervisor.profile, **resource}
    supervisor.workflow = {
        **supervisor.workflow,
        "allowed_gpu_indices": GPUS,
        "max_gpu_workers": len(GPUS),
    }
    supervisor.max_gpu_workers = len(GPUS)
    mechanism_ref, required = mechanism_inputs(rt, launcher)
    certificate, cert_ref = compatibility_certificate(rt, root)
    fixed = dict(
        schema="v22_evaluation_tail_continuation.v1",
        previous_execution_profile=rt.entry(OLD_ROOT / "registration/record.json"),
        previous_blocked_records=[
            rt.entry(p) for p in sorted((OLD_ROOT / "queue/blocked").glob("*/record.json"))
        ],
        compatibility=cert_ref,
        evaluation_resource_profile=resource_ref,
        completed_training=[rt.entry(j["result"]) for j in jobs],
        mechanism_registration=mechanism_ref,
        required_mechanism_inputs=required,
        evaluation_output=str(V18 / "final_evaluation"),
        source_bindings=source_bindings(),
        frozen_runtime_worktree=str(FROZEN),
        frozen_queue_scripts=str(FROZEN_SCRIPTS),
        allowed_gpu_indices=GPUS,
        max_gpu_workers=len(GPUS),
        minimum_free_mib=24576,
        no_training_launch=True,
        no_Base_rerun=True,
        no_feedback_resampling=True,
        automatic_numerical_failure_retry=False,
        API_calls=0,
        api_model_policy="deepseek-flash",
    )
    registration = root / "registration/record.json"
    if registration.exists():
        value = rt.checked(registration)
        require(
            all(value.get(k) == v for k, v in fixed.items()), "continuation registration changed"
        )
    else:
        value = rt.bound(dict(**fixed, at=rt.now(), user_request="处理问题恢复评测"))
        rt.persist(registration.parent, value)
    supervisor.continuation = value
    output = V18 / "final_evaluation"
    supervisor.update("V22_VERIFYING_FINAL_CHECKPOINTS")
    if not (output / "registration/record.json").exists():
        require(not output.exists(), "partial evaluation registration requires inspection")
        register = rt.bind(
            rt.final.register,
            public_evaluation_contract=make_public_contract(rt, certificate, cert_ref),
        )
        register(launcher, output)
    plan = rt.final.checked_plan(output)
    require(
        plan["Base_source_compatibility"]["certificate"] == certificate
        and plan["Base_source_compatibility"]["certificate_ref"] == cert_ref,
        "final evaluation must retain the actual compatibility evidence",
    )
    require(
        plan["total_models"] == 15
        and plan["total_episodes"] == 13245
        and plan["Base_rerun"] is False
        and plan["API_calls"] == 0,
        "unchanged fifteen-model full-dev contract required",
    )
    marker = root / "evaluation_registration/record.json"
    expected = rt.bound(
        dict(
            schema="v22_final_registration_binding.v1",
            compatibility=cert_ref,
            final_registration=rt.entry(output / "registration/record.json"),
        )
    )
    if marker.exists():
        require(rt.checked(marker) == expected, "registered evaluation binding changed")
    else:
        rt.persist(marker.parent, expected)
    return plan


def create_supervisor(rt, root, *, resume):
    class Supervisor(rt.previous.Supervisor):
        mainline_schema = "v22_evaluation_tail_complete_mainline.v1"

        def __init__(self):
            self.stage = "PREPARING"
            self.continuation_root = root
            self.continuation = None
            super().__init__(OLD_ROOT, resume=True)
            self.root = root / "queue"
            self.history_root = self.root / "jobs"
            require(
                resume or not self.history_root.exists(),
                "existing evaluation attempts require resume",
            )
            self.resume = resume

        def update(self, phase, **details):
            if phase in ("V20_FIVE_GPU_QUEUE_RUNNING", "V21_SIX_GPU_QUEUE_RUNNING"):
                phase = "V22_" + self.stage + "_RUNNING"
            return super().update(
                phase,
                **dict(
                    details,
                    continuation_id=self.continuation["id"] if self.continuation else None,
                    evaluation_only_continuation=True,
                    no_training_launch=True,
                ),
            )

        def launch(self, job, *, gpu=None):
            require_tail_job(job)
            require(
                gpu in GPUS and len(self.children) < len(GPUS),
                "at most eight authorized evaluation workers",
            )

            def launch_record(value):
                return rt.bound(
                    dict(
                        value,
                        schema="v22_eight_gpu_evaluation_worker_launch.v1",
                        continuation_id=self.continuation["id"],
                        evaluation_resource_profile=rt.entry(
                            self.continuation_root / "resource_profile/record.json"
                        ),
                        original_training_execution_profile=self.profile_ref,
                        no_training_launch=True,
                    )
                )

            execute = rt.bind(
                rt.previous.Supervisor.launch,
                GPUS=GPUS,
                six_gpu_require=eight_gpu_require,
                bound=launch_record,
            )
            return execute(self, job, gpu=gpu)

        def eligible_job(self, job):
            require_tail_job(job)
            return super().eligible_job(job)

        def gpu_queue(self, jobs, allowed):
            require(list(allowed) == GPUS, "only the authorized eight GPUs may be used")
            if any(j["key"].startswith("arm-") for j in jobs):
                require_completed_matrix(jobs, self.job_complete)
                self.update("V22_TRAINING_ALREADY_COMPLETE", completed_arms=15)
                return True
            for job in jobs:
                require_tail_job(job)
            self.stage = (
                "DEV_EVALUATION"
                if all(j["module"] == "v9_final_evaluation" for j in jobs)
                else "MECHANISM_BUILD"
                if all(j["args"][0] == "run-seed" for j in jobs)
                else "MECHANISM_EVALUATION"
            )
            execute = rt.bind(
                rt.previous.Supervisor.gpu_queue, GPUS=GPUS, six_gpu_require=eight_gpu_require
            )
            return execute(self, jobs, allowed)

        def run_remaining_mainline(self, handoff):
            prepare_evaluation(rt, self)
            return super().run_remaining_mainline(handoff)

    return Supervisor()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("run", "resume"))
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()
    root = args.root.resolve()
    require(root.parent == V18 and root != OLD_ROOT, "separate continuation directory required")
    rt = load_runtime()
    (root / "queue").mkdir(parents=True, exist_ok=True)
    with contextlib.ExitStack() as stack:
        for path in (OLD_ROOT / "queue/controller.lock", root / "queue/controller.lock"):
            lock = stack.enter_context(path.open("a"))
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        supervisor = create_supervisor(rt, root, resume=args.action == "resume")

        def stop_requested(signum, frame):
            supervisor.stop = True  # Drain owned children; never signal them.

        signal.signal(signal.SIGTERM, stop_requested)
        signal.signal(signal.SIGINT, stop_requested)
        try:
            result = supervisor.run()
        except Exception as error:
            issue = rt.bound(
                dict(
                    at=rt.now(),
                    error_type=type(error).__name__,
                    error=str(error),
                    no_Student_signal_sent=True,
                    no_implicit_retry=True,
                )
            )
            rt.persist(supervisor.root / "blocked" / issue["id"], issue)
            supervisor.update("BLOCKED_SAVED", issue=issue)
            raise
    if result is not None:
        print(json.dumps(dict(id=result["id"])))


if __name__ == "__main__":
    main()
