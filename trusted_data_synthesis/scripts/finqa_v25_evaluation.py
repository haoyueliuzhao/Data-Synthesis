"""V25: post-hoc C-only extension and a separately registered training-seed block.

Public registration, per-endpoint CPU binding, local greedy generation and block
sealing precede private scoring. The original six test runs are reused verbatim.
No API, new material, dev selection, p-values, or optional stopping is permitted.
"""

from __future__ import annotations

import argparse
import asyncio
import fcntl
import hashlib
import importlib
import json
import math
import os
from collections import Counter
from pathlib import Path

import finqa_v23_test_confirmation as original
import numpy as np

OLD_SEEDS = (11, 29, 47)
NEW_SEEDS = (137, 251, 389)
ARMS = ("Static", "C-only", "Full")
ARM_DIRECTORIES = {"Static": "static", "C-only": "c_only", "Full": "full"}
COMPARISONS = (("Full", "Static"), ("Full", "C-only"), ("C-only", "Static"))
DENOMINATOR = 1147
T95_DF2 = 4.3026527299
DEFAULT_ROOT = original.V18 / "v25_training_replication_01"
OLD_TEST_ROOT = original.DEFAULT_ROOT
require = original.require
load_runtime = original.load_runtime
native_metrics = original.native_metrics


def arm_name(arm):
    aliases = {**{a: a for a in ARMS}, **{v: k for k, v in ARM_DIRECTORIES.items()}}
    require(arm in aliases, "only Static, C-only, Full are authorized")
    return aliases[arm]


def coordinate(seed, arm):
    require(
        type(seed) is int and seed in OLD_SEEDS + NEW_SEEDS, "registered training seed required"
    )
    return f"seed{seed}/{ARM_DIRECTORIES[arm_name(arm)]}"


def statistics_contract(block):
    require(block in ("A", "B"), "registered A or B block required")
    return dict(
        block=block,
        design=(
            "post-hoc original-model C-only extension"
            if block == "A"
            else "prospectively locked new training-seed replication on known benchmark"
        ),
        original_six_model_preregistered_confirmation=False,
        seeds=list(OLD_SEEDS if block == "A" else NEW_SEEDS),
        arms=list(ARMS),
        task_denominator=DENOMINATOR,
        primary="Full-Static native execution accuracy" if block == "B" else None,
        key_secondary="Full-C-only native execution accuracy" if block == "B" else None,
        extension_comparisons=["C-only-Static", "Full-C-only"] if block == "A" else [],
        reused_Full_minus_Static_reference_only=block == "A",
        other_descriptive="C-only-Static native execution accuracy",
        paired_within_seed_same1147_tasks=True,
        estimate="equal-weight mean of the three within-seed paired accuracy differences",
        seed_dispersion=[
            "sample SD (ddof=1)",
            "minimum",
            "maximum",
            "positive/zero/negative counts",
        ],
        execution_interval=(
            None
            if block == "A"
            else dict(
                unit="independent training seed; fixed known test benchmark",
                formula="mean +/- 4.3026527299 * sample_SD / sqrt(3)",
                df=2,
                critical_value=T95_DF2,
                level=0.95,
                n=3,
                assumption=(
                    "independent identically distributed approximately normal seed effects; "
                    "strong untestable assumption at n=3"
                ),
                applies_to=["Full-Static", "Full-C-only"],
                key_secondary_is_unadjusted=True,
                multiplicity_adjusted=False,
                small_sample_warning=True,
                clip_to_accuracy_bounds=False,
            )
        ),
        program_accuracy="descriptive only; no confidence interval",
        old_source_cluster_interval_reused=False,
        source_cluster_bootstrap=False,
        fixed_known_benchmark_not_unseen_source_generalization=True,
        confidence_interval_is_not_power_or_stability_confirmation=True,
        statistical_power_claimed=False,
        eighty_percent_power_claimed=False,
        stable_training_reproducibility_claimed=False,
        no_p_values=True,
        multiplicity_adjusted=False,
        no_best_seed_checkpoint_or_block_selection=True,
        no_optional_stopping=True,
        unknown_as_zero=False,
        combined_six_seeds=(
            "predefined descriptive equal weighting only; report old/new blocks first; no pooled CI"
        ),
    )


def source_binding(block):
    sources = [Path(__file__), Path(original.__file__)]
    if block == "B":
        sources.append(Path(__file__).with_name("finqa_v25_training_replication.py"))
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}


def training_module():
    return importlib.import_module("finqa_v25_training_replication")


def test_config(final):
    config = original.test_config(final)
    require(config.seed == 20260928, "original generation RNG seed required")
    return config


def model_root(root, job):
    return Path(root) / "models" / coordinate(job["seed"], job["arm"])


def generation_root(root, job):
    return model_root(root, job) / "shards/test1147/generation"


def prepare_job(root, plan, job, final):
    directory = generation_root(root, job)
    if (directory / "run.json").exists():
        run = final.read_json(directory / "run.json")
        require(
            run["tasks"] == plan["tasks"]
            and run["provider"] == job["model_identity"]
            and run["config"] == plan["config"]
            and run["role"] == "test"
            and run["id"] == final.digest({k: v for k, v in run.items() if k != "id"})
            and run["runtime_binding"] == plan["runtime_binding"]
            and run["snapshot_id"] == plan["snapshot_id"]
            and Path(run["snapshot"]).resolve() == Path(plan["snapshot"]).resolve()
            and run["role_plan"] == plan["role_plan"]
            and run["public_view_sha256"] == plan["public_view_sha256"]
            and run["registered_denominator"] == DENOMINATOR
            and len(run["episode_keys"]) == len(set(run["episode_keys"])) == DENOMINATOR,
            "existing public run differs from fixed endpoint",
        )
        return
    final.prepare_run(
        plan["snapshot"],
        plan["role_plan"],
        directory,
        role="test",
        config=final.RunConfig.model_validate(plan["config"]),
        identity=final.ModelIdentity.model_validate(job["model_identity"]),
        task_keys=plan["tasks"],
    )


def base_registration(root, block, final, dev_registration, compatibility):
    require(not Path(root).exists(), "new immutable evaluation root required")
    dev, certificate = final.read_bound(dev_registration), final.read_bound(compatibility)
    common = original.public_test_contract(final, dev, certificate)
    require(common["config"] == test_config(final).model_dump(mode="json"), "greedy config changed")
    return dev, dict(
        schema="v25_three_arm_test_evaluation.v1",
        at=final.now(),
        block=block,
        **common,
        source_binding=source_binding(block),
        runtime_binding=final.runtime_binding(),
        numpy_version=np.__version__,
        statistics=statistics_contract(block),
        original_dev_registration=final.file_binding(dev_registration),
        compatibility=final.file_binding(compatibility),
        no_resampling=True,
        references_read_at_registration=False,
        no_dev_selection=True,
        no_training_in_evaluator=True,
        new_material_count=0,
        new_feedback_count=0,
        API_calls=0,
        api_model="deepseek-flash",
        model_fallback=False,
        all_block_generation_sealed_before_private_scoring=True,
    )


def register_a(
    root=DEFAULT_ROOT / "c_only_test_extension",
    *,
    old_test_root=OLD_TEST_ROOT,
    dev_registration=original.DEV_REGISTRATION,
    compatibility=original.COMPATIBILITY,
):
    root, old_test_root, final = Path(root), Path(old_test_root), load_runtime()
    if (root / "registration/record.json").exists():
        plan = checked_plan(root, final)
        require(plan["block"] == "A", "A root required")
        for job in plan["jobs"].values():
            prepare_job(root, plan, job, final)
        return plan
    dev, fields = base_registration(root, "A", final, dev_registration, compatibility)
    old = original.checked_plan(old_test_root, final)
    require(
        all(old[k] == fields[k] for k in ("tasks", "config", "source_groups", "snapshot_id")),
        "reuse requires identical original public test1147 contract",
    )
    jobs = {}
    for seed in OLD_SEEDS:
        key = coordinate(seed, "C-only")
        job = dev["jobs"][key]
        require(
            job["seed"] == seed and job["arm"] == "C-only" and job["step"] == 1490,
            "only original step1490 C-only candidates",
        )
        state = final.read_registered_state(dev, job)
        del state
        jobs[key] = job
    plan = final.bound(
        dict(
            **fields,
            **{
                k: dev[k]
                for k in (
                    "training_protocol",
                    "training_root",
                    "training_task_ids",
                    "material_identity",
                    "device_policy",
                )
            },
            jobs=jobs,
            total_models=3,
            total_episodes=3441,
            total_provider_attempt_cap=110112,
            reused_models=6,
            reused_episodes=6882,
            old_test_registration=final.file_binding(old_test_root / "registration/record.json"),
            old_test_summary=final.file_binding(old_test_root / "summary/record.json"),
            old_all_generation_seal=final.file_binding(
                old_test_root / "all_generation_seal/record.json"
            ),
            reused_score_reports={
                key: final.file_binding(old_test_root / "models" / key / "scores/record.json")
                for key in old["jobs"]
            },
            existing_score_results_parsed_at_registration=False,
            existing_score_files_hashed_at_registration=True,
        )
    )
    final._publish(root / "registration", plan)
    for job in jobs.values():
        prepare_job(root, plan, job, final)
    return plan


def future_job(training_root, seed, arm):
    arm = arm_name(arm)
    return dict(
        seed=seed,
        arm=arm,
        step=1490,
        phase="step",
        checkpoint_path=str(
            Path(training_root).resolve()
            / f"seed{seed}/arms"
            / ARM_DIRECTORIES[arm]
            / "training/step1490_step/state.pt"
        ),
    )


def register_b(
    root=DEFAULT_ROOT / "replication_evaluation",
    *,
    training_root=DEFAULT_ROOT / "training_replication",
    dev_registration=original.DEV_REGISTRATION,
    compatibility=original.COMPATIBILITY,
):
    root, final = Path(root), load_runtime()
    if (root / "registration/record.json").exists():
        plan = checked_plan(root, final)
        require(
            plan["block"] == "B" and plan["training_root"] == str(Path(training_root).resolve()),
            "same registered new training root required",
        )
        return plan
    dev, fields = base_registration(root, "B", final, dev_registration, compatibility)
    contract = training_module().evaluation_contract(training_root)
    require(
        contract["training_root"] == str(Path(training_root).resolve()), "wrong new training root"
    )
    require(
        contract["material_identity"] == dev["material_identity"],
        "material or execution contract changed",
    )
    require(contract["assets"] == fields["assets"], "replication base assets changed")
    fields.update(
        {
            key: contract[key]
            for key in (
                "training_protocol",
                "training_root",
                "training_task_ids",
                "material_identity",
                "device_policy",
            )
        }
    )
    plan = final.bound(
        dict(
            **fields,
            training_evaluation_contract=contract,
            training_protocol_id=contract["registration_id"],
            jobs={
                coordinate(s, a): future_job(training_root, s, a) for s in NEW_SEEDS for a in ARMS
            },
            total_models=9,
            total_episodes=10323,
            total_provider_attempt_cap=330336,
            fixed_before_generation=True,
            future_endpoint_coordinates_registered=True,
            all_nine_endpoints_evaluated_no_dev_selection=True,
        )
    )
    final._publish(root / "registration", plan)
    return plan


def checked_reference(final, reference):
    require(
        final.sha(reference["path"]) == reference["sha256"],
        "bound file changed: " + reference["path"],
    )
    return final.read_bound(reference["path"])


def checked_plan(root, final=None):
    final = final or load_runtime()
    plan = final.read_bound(Path(root) / "registration/record.json")
    block = plan["block"]
    require(block in ("A", "B"), "A or B registration required")
    seeds, arms = (OLD_SEEDS, ("C-only",)) if block == "A" else (NEW_SEEDS, ARMS)
    count = len(seeds) * len(arms)
    require(
        plan["schema"] == "v25_three_arm_test_evaluation.v1"
        and plan["source_binding"] == source_binding(block)
        and plan["runtime_binding"] == final.runtime_binding()
        and plan["statistics"] == statistics_contract(block)
        and plan["numpy_version"] == np.__version__
        and plan["config"] == test_config(final).model_dump(mode="json")
        and plan["api_model"] == "deepseek-flash"
        and plan["model_fallback"] is False
        and plan["API_calls"] == 0
        and len(plan["tasks"]) == len(set(plan["tasks"])) == DENOMINATOR
        and set(plan["jobs"]) == {coordinate(s, a) for s in seeds for a in arms}
        and plan["total_models"] == count
        and plan["total_episodes"] == count * DENOMINATOR
        and plan["total_provider_attempt_cap"] == count * DENOMINATOR * 32,
        "immutable evaluation matrix/source/statistics/model policy changed",
    )
    dev = checked_reference(final, plan["original_dev_registration"])
    certificate = checked_reference(final, plan["compatibility"])
    common = original.public_test_contract(final, dev, certificate)
    require(all(plan[k] == v for k, v in common.items()), "original public test contract changed")
    checked_reference(final, plan["training_protocol"])
    if block == "A":
        require(
            all(job == dev["jobs"][key] for key, job in plan["jobs"].items()),
            "original C-only checkpoint replaced",
        )
        for key in (
            "training_root",
            "training_task_ids",
            "material_identity",
            "device_policy",
            "training_protocol",
        ):
            require(plan[key] == dev[key], "original training contract changed")
    else:
        contract = training_module().evaluation_contract(plan["training_root"])
        require(
            plan["training_evaluation_contract"] == contract
            and plan["training_protocol_id"] == contract["registration_id"]
            and all(
                plan[k] == contract[k]
                for k in (
                    "training_protocol",
                    "training_root",
                    "training_task_ids",
                    "material_identity",
                    "device_policy",
                )
            ),
            "new training contract changed",
        )
        require(
            all(
                job == future_job(plan["training_root"], job["seed"], job["arm"])
                for job in plan["jobs"].values()
            ),
            "future endpoint coordinate changed",
        )
    return plan


def job_lock(root, seed, arm):
    directory = Path(root) / "locks"
    directory.mkdir(exist_ok=True)
    lock = (directory / (coordinate(seed, arm).replace("/", "-") + ".lock")).open("a")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BaseException:
        lock.close()
        raise
    return lock


def bind_b_locked(root, plan, seed, arm, final, *, keep_state=False):
    require(plan["block"] == "B", "new training block required")
    key = coordinate(seed, arm)
    fixed = plan["jobs"][key]
    evidence, state = training_module().checked_evaluation_checkpoint(
        plan["training_root"], seed, arm_name(arm)
    )
    require(
        all(evidence[k] == fixed[k] for k in ("seed", "arm", "step", "phase"))
        and Path(evidence["checkpoint"]["path"]).resolve() == Path(fixed["checkpoint_path"]),
        "completed checkpoint is not the registered future endpoint",
    )
    dev = final.read_bound(plan["original_dev_registration"]["path"])
    codec = dev["jobs"]["seed11/static"]["model_identity"]
    identity = final.ModelIdentity(
        backend="local_torch",
        model_id=plan["assets"]["base_binding"]["id"],
        point_id="v25-final:"
        + final.digest(dict(training_id=plan["training_protocol_id"], **evidence)),
        parameter_digest=evidence["parameter_digest"],
        tokenizer_digest=codec["tokenizer_digest"],
        chat_template_digest=codec["chat_template_digest"],
    )
    job = dict(**evidence, model_identity=identity.model_dump(mode="json"))
    binding = final.bound(
        dict(
            schema="v25_registered_future_checkpoint_binding.v1",
            protocol_id=plan["id"],
            coordinate=key,
            registered_future_endpoint=fixed,
            job=job,
            checkpoint_cpu_validated=True,
            private_references_read=False,
        )
    )
    final._publish(model_root(root, job) / "checkpoint_binding", binding)
    prepare_job(root, plan, job, final)
    return (job, state) if keep_state else job


def bind_b(root, seed, arm):
    final = load_runtime()
    plan = checked_plan(root, final)
    with job_lock(root, seed, arm):
        return bind_b_locked(root, plan, seed, arm, final)


def bound_job(root, plan, key, final):
    if plan["block"] == "A":
        return plan["jobs"][key]
    fixed = plan["jobs"][key]
    binding = final.read_bound(model_root(root, fixed) / "checkpoint_binding/record.json")
    require(
        binding["protocol_id"] == plan["id"]
        and binding["coordinate"] == key
        and binding["registered_future_endpoint"] == fixed,
        "endpoint binding differs from registered coordinate",
    )
    job = binding["job"]
    require(
        all(job[k] == fixed[k] for k in ("seed", "arm", "step", "phase"))
        and job["checkpoint"]["path"] == fixed["checkpoint_path"],
        "checkpoint binding changed",
    )
    return job


def read_state(plan, job, final):
    if plan["block"] == "A":
        return final.read_registered_state(plan, job)
    evidence, state = training_module().checked_evaluation_checkpoint(
        plan["training_root"], job["seed"], job["arm"]
    )
    require(all(job[k] == v for k, v in evidence.items()), "bound endpoint content changed")
    return state


def inspect_model(root, plan, job, final):
    return final.base.inspect_shard(
        model_root(root, job),
        {**plan, "model_identity": job["model_identity"]},
        dict(key="test1147", task_keys=plan["tasks"]),
    )


def seal_model(root, plan, job, final):
    progress = inspect_model(root, plan, job, final)
    require(
        progress["sealed"] and progress["completed"] == DENOMINATOR, "complete test1147 required"
    )
    run, original_seal, episodes = final.sealed_episodes(generation_root(root, job))
    require(
        run["tasks"] == plan["tasks"]
        and len(episodes) == DENOMINATOR
        and run["provider"] == job["model_identity"]
        and run["role"] == "test",
        "entire fixed model test run required",
    )
    seal = final.bound(
        dict(
            schema="v25_model_whole_test_generation.v1",
            protocol_id=plan["id"],
            seed=job["seed"],
            arm=job["arm"],
            checkpoint_sha256=job["state_sha256"],
            denominator=DENOMINATOR,
            run_id=run["id"],
            generation_seal_id=original_seal["id"],
            generation_seal=final.file_binding(
                generation_root(root, job) / "generation_seal/seal.json"
            ),
            episode_sha256=[final.digest(e) for e in episodes],
            all_generation_complete=True,
            all_provider_calls_settled=True,
            private_references_read=False,
        )
    )
    final._publish(model_root(root, job) / "whole_test_seal", seal)
    return seal, episodes


def generate(root, seed, arm, gpu_index, *, resume=False):
    root, final = Path(root), load_runtime()
    plan = checked_plan(root, final)
    key = coordinate(seed, arm)
    require(key in plan["jobs"], "candidate outside registered block")
    with job_lock(root, seed, arm):
        state = None
        if (
            plan["block"] == "B"
            and not (
                model_root(root, plan["jobs"][key]) / "checkpoint_binding/record.json"
            ).exists()
        ):
            _, state = bind_b_locked(root, plan, seed, arm, final, keep_state=True)
        job = bound_job(root, plan, key, final)
        prepare_job(root, plan, job, final)
        directory = model_root(root, job)
        progress = inspect_model(root, plan, job, final)
        if progress["sealed"]:
            return seal_model(root, plan, job, final)[0]
        require(
            resume or not (directory / "attempts").exists(),
            "existing attempt requires explicit resume",
        )
        if state is None:
            state = read_state(plan, job, final)
        row = final.eligible_gpu(plan, gpu_index, final.gpu_inventory())
        with (root / "locks" / ("gpu-" + final.digest(row["uuid"]) + ".lock")).open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            current = final.eligible_gpu(plan, gpu_index, final.gpu_inventory())
            require(current["uuid"] == row["uuid"], "GPU identity changed")
            require(
                not final.torch.cuda.is_initialized()
                or os.environ.get("CUDA_VISIBLE_DEVICES") == row["uuid"],
                "fresh process required to map CUDA",
            )
            os.environ["CUDA_VISIBLE_DEVICES"] = row["uuid"]
            os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")
            attempt = (
                directory / "attempts" / f"{len(list((directory / 'attempts').glob('*'))) + 1:03d}"
            )
            final._publish(
                attempt / "intent",
                dict(
                    at=final.now(),
                    protocol_id=plan["id"],
                    seed=seed,
                    arm=job["arm"],
                    pid=os.getpid(),
                    gpu=current,
                    explicit_resume=resume,
                    checkpoint_sha256=job["state_sha256"],
                    private_references_read=False,
                ),
            )
            provider = None
            try:
                provider = final.load_final_provider(plan, job, state)
                asyncio.run(final.execute_run(generation_root(root, job), provider))
            except Exception as error:
                final._publish(
                    attempt / "blocked",
                    dict(
                        at=final.now(),
                        error_type=type(error).__name__,
                        error=str(error),
                        retry=False,
                        unknown_as_zero=False,
                        no_resampling=True,
                    ),
                )
                raise
            finally:
                if provider is not None:
                    del provider
                if final.torch.cuda.is_initialized():
                    final.torch.cuda.empty_cache()
        return seal_model(root, plan, job, final)[0]


def seed_effect_summary(values, *, confidence_interval=False):
    values = np.asarray(values, dtype=np.float64)
    require(
        values.ndim == 1 and len(values) >= 2 and np.isfinite(values).all(),
        "finite seed effects required",
    )
    mean, sd = float(values.mean()), float(values.std(ddof=1))
    result = dict(
        n=int(len(values)),
        mean_difference=mean,
        sample_sd=sd,
        minimum=float(values.min()),
        maximum=float(values.max()),
        signs=dict(
            positive=int((values > 0).sum()),
            zero=int((values == 0).sum()),
            negative=int((values < 0).sum()),
        ),
    )
    if confidence_interval:
        require(len(values) == 3, "only registered n=3 seed-level interval")
        half_width = T95_DF2 * sd / math.sqrt(3)
        result["seed_t95"] = dict(
            lower=mean - half_width,
            upper=mean + half_width,
            level=0.95,
            df=2,
            critical_value=T95_DF2,
            unit="training seed, conditional on fixed known benchmark",
            n=3,
            strong_approximate_normality_assumption=True,
            multiplicity_adjusted=False,
            not_power_or_stability_confirmation=True,
        )
    return result


def paired_summary(reports, tasks, block):
    seeds = OLD_SEEDS if block == "A" else NEW_SEEDS
    require(
        block in ("A", "B") and len(tasks) == len(set(tasks)) == DENOMINATOR,
        "registered complete test cohort required",
    )
    require(
        set(reports) == {coordinate(s, a) for s in seeds for a in ARMS},
        "all nine fixed models required",
    )
    for key, report in reports.items():
        require(
            coordinate(report["seed"], report["arm"]) == key
            and report["denominator"] == DENOMINATOR
            and [r["task_key"] for r in report["results"]] == tasks,
            "paired model/task coordinates changed",
        )
        actual = native_metrics(report["results"])
        require(
            actual == report["metrics"] and all(m["unknown"] == 0 for m in actual.values()),
            "unknown/incomplete native scores cannot enter statistics",
        )
    comparisons = {}
    for positive, negative in COMPARISONS:
        name = positive + "-" + negative
        comparisons[name] = {}
        for metric in ("execution_accuracy", "program_accuracy"):
            per_seed = {}
            for seed in seeds:
                plus, minus = (reports[coordinate(seed, a)] for a in (positive, negative))
                diff = [
                    a["native"]["native"][metric] - b["native"]["native"][metric]
                    for a, b in zip(plus["results"], minus["results"], strict=True)
                ]
                per_seed[str(seed)] = dict(
                    mean_difference=sum(diff) / DENOMINATOR,
                    wins=sum(v > 0 for v in diff),
                    losses=sum(v < 0 for v in diff),
                    ties=sum(v == 0 for v in diff),
                    positive_arm_accuracy=plus["metrics"][metric]["complete_dataset_mean"],
                    negative_arm_accuracy=minus["metrics"][metric]["complete_dataset_mean"],
                )
            interval = (
                block == "B"
                and metric == "execution_accuracy"
                and name in ("Full-Static", "Full-C-only")
            )
            comparisons[name][metric] = dict(
                paired_by_seed=per_seed,
                **seed_effect_summary(
                    [v["mean_difference"] for v in per_seed.values()], confidence_interval=interval
                ),
                descriptive_only=not interval,
                task_denominator=DENOMINATOR,
                no_p_values=True,
                multiplicity_adjusted=False,
            )
    return comparisons


def seal_all(root, plan, final):
    records, episodes, jobs = {}, {}, {}
    for key in plan["jobs"]:
        job = jobs[key] = bound_job(root, plan, key, final)
        seal, episodes[key] = seal_model(root, plan, job, final)
        records[key] = dict(
            id=seal["id"],
            seal=final.file_binding(model_root(root, job) / "whole_test_seal/record.json"),
        )
    barrier = final.bound(
        dict(
            schema="v25_all_block_test_generation.v1",
            protocol_id=plan["id"],
            block=plan["block"],
            models=records,
            model_count=len(records),
            task_denominator=DENOMINATOR,
            total_episodes=len(records) * DENOMINATOR,
            all_generation_complete=True,
            all_provider_calls_settled=True,
            private_references_read=False,
        )
    )
    final._publish(Path(root) / "all_generation_seal", barrier)
    return barrier, episodes, jobs


def reused_reports(plan, final):
    """Read existing six score reports only after the new A block is sealed."""
    old = checked_reference(final, plan["old_test_registration"])
    summary = checked_reference(final, plan["old_test_summary"])
    barrier = checked_reference(final, plan["old_all_generation_seal"])
    require(
        summary["protocol_id"] == barrier["protocol_id"] == old["id"]
        and summary["global_generation_seal_id"] == barrier["id"]
        and old["tasks"] == plan["tasks"]
        and old["config"] == plan["config"],
        "original six score provenance changed",
    )
    reports = {}
    expected = {coordinate(s, a) for s in OLD_SEEDS for a in ("Static", "Full")}
    require(set(plan["reused_score_reports"]) == expected, "exactly original six scores reused")
    for key, ref in plan["reused_score_reports"].items():
        report = checked_reference(final, ref)
        require(
            summary["model_reports"][key] == ref
            and report["protocol_id"] == old["id"]
            and report["global_generation_seal_id"] == barrier["id"]
            and report["checkpoint_sha256"] == old["jobs"][key]["state_sha256"]
            and report["model_identity"] == old["jobs"][key]["model_identity"],
            "original fixed-model report replaced",
        )
        reports[key] = report
    return reports


def score(root):
    root, final = Path(root), load_runtime()
    plan = checked_plan(root, final)
    with (root / "score.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        barrier, episodes, jobs = seal_all(root, plan, final)
        manifest, tasks, lineages = final.load_public_snapshot(plan["snapshot"])
        require(manifest["id"] == plan["snapshot_id"], "scoring snapshot changed")
        # The preceding immutable barrier must cover all 3 or 9 new models.
        references = final._read_snapshot_rows(
            plan["snapshot"], "private.references.jsonl", final.PrivateReference, manifest
        )
        wanted = set(plan["tasks"])
        bundles = {
            final.task_key(t): final.TaskBundle(public=t, reference=r, lineage=lineage)
            for t, r, lineage in zip(tasks, references, lineages, strict=True)
            if final.task_key(t) in wanted
        }
        require(set(bundles) == wanted, "entire private test cohort required after sealing")
        reports = reused_reports(plan, final) if plan["block"] == "A" else {}
        bindings = dict(plan.get("reused_score_reports", {}))
        for key, job in jobs.items():
            rows = [
                dict(
                    task_key=task,
                    native=final.score_public_reasoning_program(bundles[task], episode),
                    stop_reason=episode.stop_reason,
                    actual_model_calls=episode.actual_model_calls,
                    source_group=plan["source_groups"][task],
                )
                for task, episode in zip(plan["tasks"], episodes[key], strict=True)
            ]
            reports[key] = final.bound(
                dict(
                    schema="v25_fixed_model_test_native_report.v1",
                    protocol_id=plan["id"],
                    block=plan["block"],
                    seed=job["seed"],
                    arm=job["arm"],
                    checkpoint_sha256=job["state_sha256"],
                    model_identity=job["model_identity"],
                    global_generation_seal_id=barrier["id"],
                    denominator=DENOMINATOR,
                    metrics=native_metrics(rows),
                    results=rows,
                    native_status_counts=dict(Counter(r["native"]["status"] for r in rows)),
                    unknown_as_zero=False,
                    native_execution_is_not_process_reliability=True,
                )
            )
            final._publish(model_root(root, job) / "scores", reports[key])
            bindings[key] = final.file_binding(model_root(root, job) / "scores/record.json")
        summary = final.bound(
            dict(
                schema="v25_three_arm_block_summary.v1",
                protocol_id=plan["id"],
                block=plan["block"],
                statistics=plan["statistics"],
                global_generation_seal_id=barrier["id"],
                comparisons=paired_summary(reports, plan["tasks"], plan["block"]),
                model_reports=bindings,
                reported_models=9,
                new_generation_models=len(jobs),
                new_episodes=len(jobs) * DENOMINATOR,
                fixed_known_benchmark=True,
                no_candidate_replacement=True,
                no_extra_seeds_or_questions=True,
                API_calls=0,
            )
        )
        final._publish(root / "summary", summary)
        return summary


def combine_summaries(a, b):
    require(a["block"] == "A" and b["block"] == "B", "old A and new B blocks required in order")
    require(
        a["statistics"] == statistics_contract("A") and b["statistics"] == statistics_contract("B"),
        "registered statistics changed",
    )
    combined = {}
    for name in (p + "-" + n for p, n in COMPARISONS):
        combined[name] = {}
        for metric in ("execution_accuracy", "program_accuracy"):
            old = a["comparisons"][name][metric]["paired_by_seed"]
            new = b["comparisons"][name][metric]["paired_by_seed"]
            require(
                set(old) == {str(s) for s in OLD_SEEDS} and set(new) == {str(s) for s in NEW_SEEDS},
                "all three old and three new seeds required; no block selection",
            )
            per_seed = {**old, **new}
            combined[name][metric] = dict(
                paired_by_seed=per_seed,
                **seed_effect_summary([v["mean_difference"] for v in per_seed.values()]),
                descriptive_only=True,
                confidence_intervals=None,
                no_p_values=True,
            )
    return dict(
        schema="v25_predefined_six_seed_descriptive_summary.v1",
        report_order=[
            "original_three_seed_block",
            "new_three_seed_block",
            "combined_six_seed_descriptive",
        ],
        original_three_seed_block=a["comparisons"],
        new_three_seed_block=b["comparisons"],
        combined_six_seed_descriptive=combined,
        equal_weight_all_six_seeds=True,
        pooled_confidence_interval=False,
        no_selecting_better_block=True,
        known_benchmark_not_new_independent_tasks=True,
        independent_training_seed_count=6,
        no_power_or_stability_confirmation=True,
        no_p_values=True,
    )


def combine(a_root, b_root, output):
    final = load_runtime()
    a_plan, b_plan = checked_plan(a_root, final), checked_plan(b_root, final)
    require(
        a_plan["tasks"] == b_plan["tasks"] and a_plan["config"] == b_plan["config"],
        "same fixed benchmark required",
    )
    sources = [Path(a_root) / "summary/record.json", Path(b_root) / "summary/record.json"]
    a, b = (final.read_bound(p) for p in sources)
    require(
        a["protocol_id"] == a_plan["id"] and b["protocol_id"] == b_plan["id"],
        "summary registration mismatch",
    )
    result = final.bound(
        dict(**combine_summaries(a, b), summaries=[final.file_binding(p) for p in sources])
    )
    final._publish(Path(output), result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    subs = parser.add_subparsers(dest="command", required=True)
    for command in ("register-a", "register-b", "bind-b", "generate", "score"):
        p = subs.add_parser(command)
        p.add_argument("--root", type=Path, required=True)
        if command == "register-b":
            p.add_argument("--training-root", type=Path, required=True)
        if command in ("bind-b", "generate"):
            p.add_argument("--seed", type=int, required=True)
            p.add_argument("--arm", required=True)
        if command == "generate":
            p.add_argument("--gpu-index", type=int, required=True)
            p.add_argument("--resume", action="store_true")
    p = subs.add_parser("combine")
    p.add_argument("--a-root", type=Path, required=True)
    p.add_argument("--b-root", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "register-a":
        result = register_a(args.root)
    elif args.command == "register-b":
        result = register_b(args.root, training_root=args.training_root)
    elif args.command == "bind-b":
        result = bind_b(args.root, args.seed, args.arm)
    elif args.command == "generate":
        result = generate(args.root, args.seed, args.arm, args.gpu_index, resume=args.resume)
    elif args.command == "score":
        result = score(args.root)
    else:
        result = combine(args.a_root, args.b_root, args.output)
    print(
        json.dumps(dict(command=args.command, id=result.get("id"), API_calls=0), ensure_ascii=False)
    )


if __name__ == "__main__":
    main()
