"""Once-only confirmation of the six original Static/Full step1490 models.

This external coordinator reuses the frozen scientific runtime. It changes only
the registered role from development to test; no Base/dev comparability record
is rewritten. Register is CPU/public-only. Generate never reads references or
scores. Score opens references only after all six full test1147 runs are sealed.
"""

from __future__ import annotations

import argparse
import asyncio
import fcntl
import hashlib
import importlib
import json
import os
import sys
from collections import Counter
from pathlib import Path

import numpy as np

REPO = Path("/data1/zhuxinrui/projects/Data-Synthesis")
V18 = REPO / (
    "trusted_data_synthesis/artifacts/finance_research_20260928/finqa_v6_01/"
    "v18_researcher_continuation_01"
)
FROZEN = REPO / ".codex-worktrees/finqa-v18-researcher-continuation-20260930"
DEFAULT_ROOT = V18 / "v23_confirmation_shrink_01/test_confirmation"
DEV_REGISTRATION = V18 / "final_evaluation/registration/record.json"
COMPATIBILITY = V18 / "evaluation_continuation_01/compatibility/record.json"
SEEDS = (11, 29, 47)
ARMS = ("Static", "Full")
DENOMINATOR = 1147
BOOTSTRAP_REPLICATES = 20000
BOOTSTRAP_SEED = 20261005


def require(condition, message):
    if not condition:
        raise ValueError(message)


def load_runtime():
    source = FROZEN / "trusted_data_synthesis/src"
    sys.path.insert(0, str(source))
    final = importlib.import_module("trusted_synthesis.finance_research.v9_final_evaluation")
    require(
        Path(final.__file__).resolve()
        == source / "trusted_synthesis/finance_research/v9_final_evaluation.py",
        "only the original frozen V18 scientific runtime is admitted",
    )
    return final


def source_binding():
    return dict(script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())


def arm_name(arm):
    mapping = {"static": "Static", "Static": "Static", "full": "Full", "Full": "Full"}
    require(arm in mapping, "only the original Static/Full candidates are authorized")
    return mapping[arm]


def coordinate(seed, arm):
    require(type(seed) is int and seed in SEEDS, "only the three original training seeds")
    return f"seed{seed}/{arm_name(arm).lower()}"


def statistics_contract():
    return dict(
        primary="Full-Static native execution accuracy",
        secondary="program accuracy, descriptive only",
        seeds=list(SEEDS),
        arms=list(ARMS),
        task_denominator=DENOMINATOR,
        fixed_model_count=6,
        per_question_estimate="mean of paired Full-Static differences across three fixed seeds",
        point_estimate="unweighted mean of the 1147 per-question estimates",
        bootstrap=dict(
            unit="original lineage.source_group",
            ordered_clusters="lexicographically sorted original source_group strings",
            replicates=BOOTSTRAP_REPLICATES,
            rng="numpy.random.Generator(numpy.random.PCG64(seed))",
            seed=BOOTSTRAP_SEED,
            draw="G iid uniform cluster indices with replacement, one vector per replicate",
            shared_cluster_multiplicity_applies_to_all_six_models=True,
            statistic=(
                "sum(sampled cluster sums of per-question differences) / "
                "sum(sampled cluster task counts)"
            ),
            task_weighted_not_company_equal_weighted=True,
            percentile_interval=[0.025, 0.975],
            quantile_method="linear",
            primary_execution_only=True,
        ),
        uncertainty_scope=(
            "task-source uncertainty conditional on six fixed trained models; "
            "not training-randomness uncertainty"
        ),
        per_seed_differences_always_reported=True,
        positive_confirmation_rule="primary 95% interval lower endpoint strictly greater than zero",
        zero_in_interval="not confirmed; not equivalent; no extra seeds/tasks/candidate switching",
        source_disjointness_or_no_pretraining_exposure_claimed=False,
        Full_better_than_C_only_claimed=False,
        no_p_values=True,
        no_best_seed_or_checkpoint_selection=True,
        no_optional_stopping=True,
        unknown_as_zero=False,
    )


def test_config(final):
    original = final.base.evaluation_config().model_dump(mode="json")
    require(original["api_model"] == "deepseek-flash", "API model policy changed")
    original["role"] = "test"
    config = final.RunConfig.model_validate(original)
    require(
        config.temperature == 0
        and config.top_p == 1
        and config.top_k == 0
        and config.max_steps == 32
        and config.max_new_tokens == 2048
        and config.context_limit == 24576,
        "original greedy decoding and output/context/call budgets required",
    )
    return config


def public_test_contract(final, dev, certificate):
    """New test-role contract; neither read references nor imitate a Base record."""
    current = final.runtime_binding()
    require(
        dev["schema"] == "v9_fifteen_final_dev_evaluation.v1"
        and certificate["schema"] == "v22_exact_provider_compatibility_certificate.v1"
        and current == dev["runtime_binding"] == certificate["actual_runtime_binding"]
        and dev["evaluation_source_sha256"] == certificate["actual_evaluation_sources"],
        "original real evaluation sources and registered V22 compatibility must match",
    )
    require(
        dev["config"] == final.base.evaluation_config().model_dump(mode="json"),
        "original public harness configuration changed",
    )
    config = test_config(final)
    manifest, tasks, lineages = final.load_public_snapshot(dev["snapshot"])
    final.verify_role_plan(dev["role_plan"], tasks, lineages)
    require(manifest["id"] == dev["snapshot_id"], "original snapshot changed")
    chosen = [
        (task, lineage)
        for task, lineage in zip(tasks, lineages, strict=True)
        if dev["role_plan"]["assignments"][final.task_key(task)] == "test"
    ]
    require(
        len(chosen) == DENOMINATOR
        and all(
            task.dataset == "finqa" and lineage.original_split == "test" for task, lineage in chosen
        ),
        "complete original official FinQA public_test1147 required",
    )
    keys = [final.task_key(task) for task, _ in chosen]
    require(len(set(keys)) == DENOMINATOR, "test task identities must be unique")
    groups = {
        final.task_key(task): dict(group=lineage.source_group, level=lineage.source_group_level)
        for task, lineage in chosen
    }
    require(
        all(isinstance(v["group"], str) and v["group"] for v in groups.values()),
        "every public test task requires its original nonempty source group",
    )
    return dict(
        snapshot=dev["snapshot"],
        snapshot_id=manifest["id"],
        role_plan=dev["role_plan"],
        assets=dev["assets"],
        config=config.model_dump(mode="json"),
        tasks=keys,
        denominator=DENOMINATOR,
        role="test",
        original_split="test",
        public_view_sha256={
            final.task_key(t): final.digest(final.runtime_task_view(t, config)) for t, _ in chosen
        },
        public_system=final.system_message(config),
        public_tools=final.episode_tool_specs(config),
        source_groups=groups,
        evaluation_source_sha256=certificate["actual_evaluation_sources"],
        role_change_from_dev_is_explicit=True,
        Base_or_dev_contract_rewritten=False,
    )


def model_root(root, job):
    return Path(root) / "models" / coordinate(job["seed"], job["arm"])


def generation_root(root, job):
    return model_root(root, job) / "shards/test1147/generation"


def register(root=DEFAULT_ROOT, *, dev_registration=DEV_REGISTRATION, compatibility=COMPATIBILITY):
    root = Path(root)
    require(not root.exists(), "new immutable confirmation root required")
    final = load_runtime()
    dev, certificate = final.read_bound(dev_registration), final.read_bound(compatibility)
    common = public_test_contract(final, dev, certificate)
    jobs = {}
    for seed in SEEDS:
        for arm in ARMS:
            job = dev["jobs"][coordinate(seed, arm)]
            require(
                job["step"] == 1490 and job["seed"] == seed and job["arm"] == arm,
                "only original six step1490 checkpoints admitted",
            )
            state = final.read_registered_state(dev, job)
            del state
            require(job["model_identity"]["backend"] == "local_torch", "local-only inference")
            jobs[coordinate(seed, arm)] = job
    plan = final.bound(
        dict(
            schema="v23_fixed_six_model_public_test_confirmation.v1",
            at=final.now(),
            **common,
            **source_binding(),
            runtime_binding=final.runtime_binding(),
            jobs=jobs,
            statistics=statistics_contract(),
            numpy_version=np.__version__,
            original_dev_registration=final.file_binding(dev_registration),
            compatibility=final.file_binding(compatibility),
            training_protocol=dev["training_protocol"],
            training_root=dev["training_root"],
            training_task_ids=dev["training_task_ids"],
            material_identity=dev["material_identity"],
            device_policy=dev["device_policy"],
            total_models=6,
            total_episodes=6882,
            total_provider_attempt_cap=220224,
            all_six_generation_sealed_before_private_scoring=True,
            references_read_at_registration=False,
            no_resampling=True,
            no_training=True,
            no_probe=True,
            new_material_count=0,
            new_feedback_count=0,
            API_calls=0,
            api_model="deepseek-flash",
            model_fallback=False,
        )
    )
    final._publish(root / "registration", plan)
    for job in jobs.values():
        final.prepare_run(
            plan["snapshot"],
            plan["role_plan"],
            generation_root(root, job),
            role="test",
            config=final.RunConfig.model_validate(plan["config"]),
            identity=final.ModelIdentity.model_validate(job["model_identity"]),
            task_keys=plan["tasks"],
        )
    return plan


def checked_plan(root, final=None):
    final = final or load_runtime()
    plan = final.read_bound(Path(root) / "registration/record.json")
    require(
        plan["schema"] == "v23_fixed_six_model_public_test_confirmation.v1"
        and plan["script_sha256"] == source_binding()["script_sha256"]
        and plan["runtime_binding"] == final.runtime_binding()
        and plan["statistics"] == statistics_contract()
        and plan["numpy_version"] == np.__version__
        and plan["config"] == test_config(final).model_dump(mode="json")
        and plan["api_model"] == "deepseek-flash"
        and plan["model_fallback"] is False
        and plan["API_calls"] == 0
        and len(plan["tasks"]) == len(set(plan["tasks"])) == DENOMINATOR
        and set(plan["jobs"]) == {coordinate(s, a) for s in SEEDS for a in ARMS}
        and plan["total_episodes"] == 6882
        and plan["total_provider_attempt_cap"] == 220224,
        "immutable six-model test contract/source/statistics changed",
    )
    for name in ("original_dev_registration", "compatibility", "training_protocol"):
        require(final.sha(plan[name]["path"]) == plan[name]["sha256"], name + " changed")
    dev = final.read_bound(plan["original_dev_registration"]["path"])
    certificate = final.read_bound(plan["compatibility"]["path"])
    common = public_test_contract(final, dev, certificate)
    require(all(plan[k] == v for k, v in common.items()), "registered public test input changed")
    for name in (
        "training_protocol",
        "training_root",
        "training_task_ids",
        "material_identity",
        "device_policy",
    ):
        require(plan[name] == dev[name], "original training identity changed: " + name)
    for key, job in plan["jobs"].items():
        require(
            job == dev["jobs"][key]
            and job["step"] == 1490
            and job["model_identity"]["backend"] == "local_torch",
            "test candidates cannot be replaced or re-trained",
        )
    return plan


def inspect_model(root, plan, job, final=None):
    final = final or load_runtime()
    return final.base.inspect_shard(
        model_root(root, job),
        {**plan, "model_identity": job["model_identity"]},
        dict(key="test1147", task_keys=plan["tasks"]),
    )


def seal_model(root, plan, job, final=None):
    final = final or load_runtime()
    progress = inspect_model(root, plan, job, final)
    require(
        progress["sealed"] and progress["completed"] == DENOMINATOR,
        "complete test1147 generation required before sealing",
    )
    run, original, episodes = final.sealed_episodes(generation_root(root, job))
    require(
        run["tasks"] == plan["tasks"]
        and len(episodes) == DENOMINATOR
        and run["provider"] == job["model_identity"]
        and run["role"] == "test",
        "entire registered test model run required",
    )
    seal = final.bound(
        dict(
            schema="v23_original_model_whole_test_generation.v1",
            protocol_id=plan["id"],
            seed=job["seed"],
            arm=job["arm"],
            checkpoint_sha256=job["state_sha256"],
            denominator=DENOMINATOR,
            run_id=run["id"],
            generation_seal_id=original["id"],
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
    """One original candidate; explicit safe resume never retries unresolved intent."""
    root, final = Path(root), load_runtime()
    plan = checked_plan(root, final)
    job = plan["jobs"][coordinate(seed, arm)]
    directory = model_root(root, job)
    locks = root / "locks"
    locks.mkdir(exist_ok=True)
    with (locks / (coordinate(seed, arm).replace("/", "-") + ".lock")).open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        progress = inspect_model(root, plan, job, final)
        if progress["sealed"]:
            return seal_model(root, plan, job, final)[0]
        require(
            resume or not (directory / "attempts").exists(),
            "existing attempt requires explicit resume; no automatic replay",
        )
        state = final.read_registered_state(plan, job)
        row = final.eligible_gpu(plan, gpu_index, final.gpu_inventory())
        with (locks / ("gpu-" + final.digest(row["uuid"]) + ".lock")).open("a") as gpu_lock:
            fcntl.flock(gpu_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            current = final.eligible_gpu(plan, gpu_index, final.gpu_inventory())
            require(current["uuid"] == row["uuid"], "GPU identity changed")
            require(
                not final.torch.cuda.is_initialized()
                or os.environ.get("CUDA_VISIBLE_DEVICES") == row["uuid"],
                "fresh process required to map CUDA",
            )
            os.environ["CUDA_VISIBLE_DEVICES"] = row["uuid"]
            os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")
            number = len(list((directory / "attempts").glob("*"))) + 1
            attempt = directory / "attempts" / f"{number:03d}"
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


def native_metrics(results):
    require(len(results) == DENOMINATOR, "full1147 native result rows required")
    metrics = {}
    for metric in ("execution_accuracy", "program_accuracy"):
        values = [r["native"]["native"][metric] for r in results]
        require(
            all(v is None or type(v) in (int, float) and v in (0, 1) for v in values),
            "native scores must be binary or explicit unknown",
        )
        known = [v for v in values if v is not None]
        metrics[metric] = dict(
            denominator=DENOMINATOR,
            scored=len(known),
            unknown=DENOMINATOR - len(known),
            correct=sum(known),
            complete_dataset_mean=sum(known) / DENOMINATOR if len(known) == DENOMINATOR else None,
        )
    return metrics


def source_cluster_bootstrap(per_question, groups):
    """Task-weighted ratio with identical cluster multiplicities for all seeds/arms."""
    values = np.asarray(per_question, dtype=np.float64)
    require(
        values.ndim == 1
        and len(values) == len(groups)
        and len(values) > 0
        and np.isfinite(values).all(),
        "finite paired questions and groups required",
    )
    require(all(isinstance(g, str) and g for g in groups), "nonempty source groups required")
    labels = sorted(set(groups))
    index = {group: i for i, group in enumerate(labels)}
    codes = np.asarray([index[g] for g in groups], dtype=np.int64)
    counts = np.bincount(codes, minlength=len(labels))
    sums = np.bincount(codes, weights=values, minlength=len(labels))
    rng = np.random.Generator(np.random.PCG64(BOOTSTRAP_SEED))
    draws = np.empty(BOOTSTRAP_REPLICATES, dtype=np.float64)
    for i in range(BOOTSTRAP_REPLICATES):
        sampled = rng.integers(0, len(labels), size=len(labels))
        draws[i] = sums[sampled].sum() / counts[sampled].sum()
    interval = np.quantile(draws, [0.025, 0.975], method="linear")
    return dict(
        mean_difference=float(values.mean()),
        lower=float(interval[0]),
        upper=float(interval[1]),
        level=0.95,
        cluster_count=len(labels),
        question_count=len(values),
        replicates=BOOTSTRAP_REPLICATES,
        seed=BOOTSTRAP_SEED,
        quantile_method="linear",
        cluster_task_counts=dict(zip(labels, counts.tolist(), strict=True)),
        bootstrap_values_sha256=hashlib.sha256(draws.astype("<f8").tobytes()).hexdigest(),
        task_weighted_not_company_equal_weighted=True,
        uncertainty_scope=statistics_contract()["uncertainty_scope"],
        confirmed_positive_effect=bool(interval[0] > 0),
        interpretation=(
            "positive confirmation for these fixed models"
            if interval[0] > 0
            else "not positively confirmed; not an equivalence finding"
        ),
    )


def paired_summary(reports, tasks, groups):
    require(
        len(tasks) == len(set(tasks)) == DENOMINATOR and set(groups) == set(tasks),
        "all identical1147 questions and original source groups required",
    )
    require(
        set(reports) == {coordinate(s, a) for s in SEEDS for a in ARMS},
        "all six original models required; no successful prefix analysis",
    )
    for key, report in reports.items():
        require(
            coordinate(report["seed"], report["arm"]) == key
            and report["denominator"] == DENOMINATOR
            and [r["task_key"] for r in report["results"]] == tasks,
            "paired model coordinates or question ordering changed",
        )
        actual = native_metrics(report["results"])
        require(
            actual == report["metrics"] and all(m["unknown"] == 0 for m in actual.values()),
            "unknown/incomplete native scoring cannot enter paired statistics",
        )
    output = {}
    for metric in ("execution_accuracy", "program_accuracy"):
        differences, per_seed = [], {}
        for seed in SEEDS:
            full = reports[coordinate(seed, "Full")]["results"]
            static = reports[coordinate(seed, "Static")]["results"]
            diff = [
                a["native"]["native"][metric] - b["native"]["native"][metric]
                for a, b in zip(full, static, strict=True)
            ]
            differences.append(diff)
            per_seed[str(seed)] = dict(
                mean_difference=sum(diff) / DENOMINATOR,
                wins=sum(d > 0 for d in diff),
                losses=sum(d < 0 for d in diff),
                ties=sum(d == 0 for d in diff),
                Full_accuracy=reports[coordinate(seed, "Full")]["metrics"][metric][
                    "complete_dataset_mean"
                ],
                Static_accuracy=reports[coordinate(seed, "Static")]["metrics"][metric][
                    "complete_dataset_mean"
                ],
            )
        by_question = np.asarray(differences, dtype=np.float64).mean(axis=0).tolist()
        output[metric] = dict(
            paired_by_seed=per_seed,
            mean_difference=sum(by_question) / DENOMINATOR,
            per_question_mean_difference=dict(zip(tasks, by_question, strict=True)),
            original_task_denominator=DENOMINATOR,
            fixed_training_seeds=len(SEEDS),
            descriptive_only=(metric != "execution_accuracy"),
        )
        if metric == "execution_accuracy":
            output[metric]["source_cluster_bootstrap"] = source_cluster_bootstrap(
                by_question, [groups[key]["group"] for key in tasks]
            )
    return output


def seal_all(root, plan, final):
    """Must finish this barrier before any private references are opened."""
    episodes, records = {}, {}
    for seed in SEEDS:
        for arm in ARMS:
            key = coordinate(seed, arm)
            seal, episodes[key] = seal_model(root, plan, plan["jobs"][key], final)
            records[key] = dict(
                id=seal["id"],
                seal=final.file_binding(
                    model_root(root, plan["jobs"][key]) / "whole_test_seal/record.json"
                ),
            )
    barrier = final.bound(
        dict(
            schema="v23_all_six_complete_test_generation.v1",
            protocol_id=plan["id"],
            models=records,
            model_count=6,
            task_denominator=DENOMINATOR,
            total_episodes=6882,
            all_generation_complete=True,
            all_provider_calls_settled=True,
            private_references_read=False,
        )
    )
    final._publish(Path(root) / "all_generation_seal", barrier)
    return barrier, episodes


def score(root=DEFAULT_ROOT):
    root, final = Path(root), load_runtime()
    plan = checked_plan(root, final)
    with (root / "score.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        barrier, episodes = seal_all(root, plan, final)
        manifest, tasks, lineages = final.load_public_snapshot(plan["snapshot"])
        require(manifest["id"] == plan["snapshot_id"], "scoring snapshot changed")
        # This is the only private-reference read in the new module. The global
        # immutable barrier above already bound all 6 x 1147 finished episodes.
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
        reports = {}
        for key, job in plan["jobs"].items():
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
                    schema="v23_fixed_model_test_native_report.v1",
                    protocol_id=plan["id"],
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
        summary = final.bound(
            dict(
                schema="v23_fixed_six_model_test_confirmation_summary.v1",
                protocol_id=plan["id"],
                statistics=plan["statistics"],
                global_generation_seal_id=barrier["id"],
                comparisons=paired_summary(reports, plan["tasks"], plan["source_groups"]),
                model_reports={
                    key: final.file_binding(model_root(root, job) / "scores/record.json")
                    for key, job in plan["jobs"].items()
                },
                total_models=6,
                total_episodes=6882,
                no_candidate_replacement=True,
                no_extra_seeds_or_questions=True,
                API_calls=0,
            )
        )
        final._publish(root / "summary", summary)
        return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for command in ("register", "generate", "score"):
        item = sub.add_parser(command)
        item.add_argument("--root", type=Path, default=DEFAULT_ROOT)
        if command == "generate":
            item.add_argument("--seed", type=int, choices=SEEDS, required=True)
            item.add_argument("--arm", choices=("static", "full"), required=True)
            item.add_argument("--gpu-index", type=int, choices=range(8), required=True)
            item.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    if args.command == "register":
        result = register(args.root)
    elif args.command == "generate":
        result = generate(args.root, args.seed, args.arm, args.gpu_index, resume=args.resume)
    else:
        result = score(args.root)
    print(json.dumps(dict(command=args.command, id=result["id"], root=str(args.root))))


if __name__ == "__main__":
    main()
