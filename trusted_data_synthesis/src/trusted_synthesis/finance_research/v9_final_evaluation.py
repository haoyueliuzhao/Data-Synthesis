"""Actual final checkpoints -> full sealed dev883 -> native paired summaries.

No model is loaded at import or registration. This is not a new harness, Base
rerun, mechanism evaluator, API collector, or a statistical-power claim.
"""

from __future__ import annotations

import argparse
import asyncio
import fcntl
import io
import math
import os
from collections import Counter, defaultdict
from pathlib import Path

import torch

from trusted_synthesis.experiments.finance_qa_vnext_pq_student.model import load_student

from . import v7_base_evaluation as base
from .calibration import gpu_inventory, now
from .contracts import ModelIdentity, PrivateReference, RunConfig, TaskBundle, digest
from .harness import episode_tool_specs, system_message
from .planning import task_key, verify_role_plan
from .providers import LocalTorchProvider, local_model_identity, parameter_digest
from .storage import (
    _read_snapshot_rows,
    execute_run,
    load_public_snapshot,
    prepare_run,
    read_json,
    runtime_binding,
    runtime_task_view,
    sealed_episodes,
)
from .v6_distribution import ARMS
from .v6_task import score_public_reasoning_program
from .v8_training_driver import _publish, _tree_digest, validate_student_adapters
from .v9_conditional_training import build_task_schedule
from .v9_training_launcher import (
    ARM_DIRECTORIES,
    SEEDS,
    bound,
    checked_launch,
    eligible_gpu,
    file_binding,
    read_bound,
    require,
    sha,
)

DENOMINATOR = 883
COMPARISONS = (
    ("Full", "Static"),
    ("Full", "C-only"),
    ("Manual+", "Static"),
    ("Manual-", "Static"),
)
EVALUATION_SOURCES = (
    "contracts.py",
    "harness.py",
    "profiles.py",
    "providers.py",
    "tools.py",
    "v6_task.py",
    "native_metrics.py",
    "settlement.py",
    "storage.py",
)


def coordinate(seed, arm):
    require(seed in SEEDS and arm in ARMS, "one of the original fifteen final models required")
    return f"seed{seed}/{ARM_DIRECTORIES[arm]}"


def statistics_contract():
    return dict(
        primary="Full-Static native execution accuracy",
        secondary=["Full-C-only", "Manual+-Static", "Manual--Static"],
        seeds=list(SEEDS),
        task_denominator=DENOMINATOR,
        model_count=15,
        same_tasks_paired_within_seed=True,
        main_estimate="mean of three within-seed mean paired differences over the same883 tasks",
        repeated_seeds_do_not_make_2649_independent_questions=True,
        source_groups="fixed original lineage.source_group; descriptive within-cluster means",
        confidence_intervals=None,
        p_values=None,
        statistical_power_claimed=False,
        seed_spread_is_descriptive_not_confidence_interval=True,
        Static_minus_Base="ordinary learning effect, never the VTDO increment",
        native_execution_is_not_process_reliability=True,
        no_selecting_best_seed_or_endpoint=True,
    )


def checked_final_checkpoint(training_root, training_plan, task_ids, seed, arm):
    """Validate actual endpoint bytes and coordinates, not a readiness flag."""
    root = Path(training_root)
    result_path = root / f"seed{seed}/result/record.json"
    result = read_bound(result_path)
    require(
        result["schema"] == "v9_conditional_five_arm_seed_result.v1"
        and result["protocol_id"] == training_plan["id"]
        and result["pool_id"] == training_plan["material_identity"]["pool_id"]
        and result["seed"] == seed
        and result["all_five_actual_training_histories_complete"] is True
        and set(result["arms"]) == set(ARMS),
        "complete original five-arm seed result required",
    )
    execution = training_plan["material_identity"]["execution_plan"]
    step = execution["final_step"]
    path = root / f"seed{seed}/arms" / ARM_DIRECTORIES[arm] / "training" / f"step{step:04d}_step"
    reference = result["arms"][arm]["final_checkpoint"]
    require(Path(reference["path"]).resolve() == path.resolve(), "wrong final arm/step directory")
    summary = read_json(path / "record.json")
    raw = (path / "state.pt").read_bytes()
    require(
        sha(path / "state.pt") == reference["state_sha256"] == summary["state_sha256"],
        "final checkpoint bytes differ from training result",
    )
    state = torch.load(io.BytesIO(raw), map_location="cpu", weights_only=False)
    require(
        _tree_digest(state) == reference["actual_state_digest"] == summary["actual_state_digest"],
        "actual final state content changed",
    )
    require(
        state["schema"] == "v8_committed_training_state.v1"
        and state["seed"] == summary["seed"] == seed
        and state["arm"] == summary["arm"] == reference["arm"] == arm
        and state["step"] == summary["step"] == reference["step"] == step
        and summary["phase"] == reference["phase"] == "step"
        and state["pool_id"] == summary["pool_id"] == training_plan["material_identity"]["pool_id"]
        and state.get("execution_plan") == execution
        and state["schedule"] == build_task_schedule(task_ids, seed)
        and summary["schedule_sha256"] == state["schedule"]["schedule_sha256"]
        and state["outer_done"] == (execution["outer_steps"] if arm in ("C-only", "Full") else []),
        "wrong seed/arm/final step/phase/pool/schedule/outer history",
    )
    require(
        state["parameters"]
        and all(
            n.endswith((".lora_A", ".lora_B"))
            and p.dtype == torch.float32
            and torch.isfinite(p).all().item()
            for n, p in state["parameters"].items()
        ),
        "actual finite FP32 final LoRA coordinates required",
    )
    evidence = dict(
        seed=seed,
        arm=arm,
        step=step,
        phase="step",
        checkpoint=file_binding(path / "state.pt"),
        checkpoint_summary=file_binding(path / "record.json"),
        seed_result=file_binding(result_path),
        state_sha256=summary["state_sha256"],
        actual_state_digest=summary["actual_state_digest"],
        parameter_digest=parameter_digest(state["parameters"]),
        buffers_digest=_tree_digest(state["buffers"]),
        frozen_base_digest=state["frozen_base_digest"],
        adapter_binding=state["adapter_binding"],
        pool_id=state["pool_id"],
        schedule_sha256=state["schedule"]["schedule_sha256"],
    )
    return evidence, state


def public_evaluation_contract(assets_source, base_plan):
    """Compare public inputs/runtime, never inspect Base mistakes to tune a prompt."""
    config = base.evaluation_config()
    manifest, tasks, lineages = load_public_snapshot(assets_source["snapshot"])
    verify_role_plan(assets_source["role_plan"], tasks, lineages)
    chosen = [
        (t, lineage)
        for t, lineage in zip(tasks, lineages, strict=True)
        if assets_source["role_plan"]["assignments"][task_key(t)] == "development"
    ]
    require(
        len(chosen) == DENOMINATOR
        and all(t.dataset == "finqa" and lineage.original_split == "dev" for t, lineage in chosen),
        "complete original official FinQA dev883 required",
    )
    keys = [task_key(t) for t, _ in chosen]
    views = {task_key(t): digest(runtime_task_view(t, config)) for t, _ in chosen}
    require(
        base_plan["schema"] == "finqa_five_arm_base_dev883.v1"
        and base_plan["denominator"] == DENOMINATOR
        and base_plan["adapter"] is None
        and base_plan["assets"] == assets_source["assets"]
        and base_plan["snapshot"] == assets_source["snapshot"]
        and base_plan["snapshot_id"] == manifest["id"]
        and base_plan["role_plan"] == assets_source["role_plan"]
        and base_plan["config"] == config.model_dump(mode="json")
        and base_plan["tasks"] == keys
        and base_plan["public_view_sha256"] == views
        and base_plan["public_system"] == system_message(config)
        and base_plan["public_tools"] == episode_tool_specs(config),
        "cannot reuse Base under a different public evaluation contract",
    )
    current = runtime_binding()
    sources = [*EVALUATION_SOURCES, *(k for k in current if k.startswith("metric_vendor/"))]
    require(
        all(current[k] == base_plan["runtime_binding"].get(k) for k in sources),
        "public execution/scorer source differs from frozen Base; no silent comparability claim",
    )
    return dict(
        snapshot=assets_source["snapshot"],
        snapshot_id=manifest["id"],
        role_plan=assets_source["role_plan"],
        assets=assets_source["assets"],
        config=config.model_dump(mode="json"),
        tasks=keys,
        denominator=DENOMINATOR,
        public_view_sha256=views,
        public_system=system_message(config),
        public_tools=episode_tool_specs(config),
        source_groups={
            task_key(t): dict(group=lineage.source_group, level=lineage.source_group_level)
            for t, lineage in chosen
        },
        evaluation_source_sha256={k: current[k] for k in sources},
    )


def register(training_root, output, *, base_output=base.OUTPUT):
    """Bind all fifteen already-real endpoints before any final dev generation."""
    output, training_root, base_output = Path(output), Path(training_root), Path(base_output)
    require(not output.exists(), "new immutable final evaluation registration required")
    training, pool, assets_source = checked_launch(training_root)
    base_plan = read_bound(base_output / "protocol.json")
    common = public_evaluation_contract(assets_source, base_plan)
    # Only frozen aggregate Base metrics are consumed; no item error analysis or rerun.
    baseline = read_bound(base_output / "scores/record.json")
    require(
        baseline["schema"] == "finqa_five_arm_base_dev_report.v1"
        and baseline["protocol_id"] == base_plan["id"]
        and baseline["denominator"] == DENOMINATOR
        and baseline["original_base_no_adapter"] is True
        and all(
            baseline["metrics"][k]["unknown"] == 0
            and baseline["metrics"][k]["scored"] == DENOMINATOR
            and baseline["metrics"][k]["complete_dataset_mean"] is not None
            for k in ("execution_accuracy", "program_accuracy")
        ),
        "complete original Base aggregate required, not an estimated replacement",
    )
    jobs = {}
    codec, template = pool.tokenizer_binding
    require(
        (codec, template)
        == (
            base_plan["model_identity"]["tokenizer_digest"],
            base_plan["model_identity"]["chat_template_digest"],
        ),
        "training encoding and frozen Base tokenizer/template differ",
    )
    for seed in SEEDS:
        for arm in ARMS:
            evidence, state = checked_final_checkpoint(
                training_root, training, pool.task_ids, seed, arm
            )
            point = "v9-final:" + digest(dict(training_id=training["id"], **evidence))
            identity = ModelIdentity(
                backend="local_torch",
                model_id=common["assets"]["base_binding"]["id"],
                point_id=point,
                parameter_digest=evidence["parameter_digest"],
                tokenizer_digest=codec,
                chat_template_digest=template,
            )
            jobs[coordinate(seed, arm)] = dict(
                **evidence, model_identity=identity.model_dump(mode="json")
            )
            del state
    plan = bound(
        dict(
            schema="v9_fifteen_final_dev_evaluation.v1",
            at=now(),
            **common,
            training_protocol=file_binding(training_root / "registration/record.json"),
            training_protocol_id=training["id"],
            training_root=str(training_root.resolve()),
            material_identity=training["material_identity"],
            training_task_ids=list(pool.task_ids),
            jobs=jobs,
            runtime_binding=runtime_binding(),
            statistics=statistics_contract(),
            Base_protocol=file_binding(base_output / "protocol.json"),
            Base_score_report=file_binding(base_output / "scores/record.json"),
            Base_score_id=baseline["id"],
            Base_aggregate_metrics=baseline["metrics"],
            Base_rerun=False,
            Base_item_results_used_for_design=False,
            device_policy=training["device_policy"],
            total_models=15,
            total_episodes=13245,
            all_fifteen_endpoints_fixed_before_evaluation=True,
            all883_generation_before_private_scoring=True,
            unknown_as_zero=False,
            no_endpoint_selection=True,
            API_calls=0,
            automatic_training=False,
            public_test_launched=False,
            CUDA_acceptance_completed=False,
        )
    )
    _publish(output / "registration", plan)
    for job in jobs.values():
        prepare_run(
            plan["snapshot"],
            plan["role_plan"],
            generation_root(output, job),
            role="development",
            config=RunConfig.model_validate(plan["config"]),
            identity=ModelIdentity.model_validate(job["model_identity"]),
            task_keys=plan["tasks"],
        )
    return plan


def checked_plan(output):
    plan = read_bound(Path(output) / "registration/record.json")
    require(
        plan["schema"] == "v9_fifteen_final_dev_evaluation.v1"
        and plan["runtime_binding"] == runtime_binding()
        and plan["statistics"] == statistics_contract()
        and plan["config"] == base.evaluation_config().model_dump(mode="json")
        and len(plan["tasks"]) == len(set(plan["tasks"])) == DENOMINATOR
        and set(plan["jobs"]) == {coordinate(s, a) for s in SEEDS for a in ARMS},
        "frozen full final-evaluation matrix/contract changed",
    )
    for key in ("training_protocol", "Base_protocol", "Base_score_report"):
        require(sha(plan[key]["path"]) == plan[key]["sha256"], key + " bytes changed")
    return plan


def model_root(output, job):
    return Path(output) / "models" / coordinate(job["seed"], job["arm"])


def generation_root(output, job):
    return model_root(output, job) / "shards/dev883/generation"


def model_plan(plan, job):
    return {**plan, "model_identity": job["model_identity"]}


def inspect_model(output, plan, job):
    return base.inspect_shard(
        model_root(output, job),
        model_plan(plan, job),
        dict(key="dev883", task_keys=plan["tasks"]),
    )


def read_registered_state(plan, job):
    training = read_bound(plan["training_protocol"]["path"])
    evidence, state = checked_final_checkpoint(
        plan["training_root"], training, plan["training_task_ids"], job["seed"], job["arm"]
    )
    require(all(job[k] == value for k, value in evidence.items()), "registered final model changed")
    return state


def install_checkpoint_state(model, state, scope):
    """Mechanical parameter/buffer installation after caller verifies the point coordinates."""
    architecture = validate_student_adapters(model, scope)
    require(architecture == state["adapter_binding"], "final custom adapter architecture changed")
    named = dict(model.named_parameters())
    trainable = {n: p for n, p in named.items() if p.requires_grad}
    frozen = {n: p for n, p in named.items() if not p.requires_grad}
    require(
        parameter_digest(frozen) == state["frozen_base_digest"], "loaded Base tensor bytes differ"
    )
    buffers = dict(model.named_buffers())
    require(
        set(trainable) == set(state["parameters"]) and set(buffers) == set(state["buffers"]),
        "final parameters or buffers missing/invented",
    )
    with torch.no_grad():
        for actual, saved in ((trainable, state["parameters"]), (buffers, state["buffers"])):
            for name, value in saved.items():
                require(
                    actual[name].shape == value.shape and actual[name].dtype == value.dtype,
                    "actual final tensor shape/dtype changed",
                )
                actual[name].copy_(value.to(actual[name].device))
    require(
        parameter_digest(trainable) == parameter_digest(state["parameters"])
        and _tree_digest(buffers) == _tree_digest(state["buffers"]),
        "actual installed final tensor bytes differ",
    )
    model.requires_grad_(False)
    model.eval()
    if hasattr(model, "gradient_checkpointing_disable"):
        model.gradient_checkpointing_disable()
    model.config.use_cache = True
    return trainable


def load_final_provider(plan, job, state):
    tokenizer = base.load_tokenizer(plan["assets"])
    model, scope = load_student(
        plan["assets"]["base_binding"], plan["config"]["seed"], trainable=True
    )
    parameters = install_checkpoint_state(model, state, scope)
    identity = local_model_identity(
        model,
        tokenizer,
        model_id=job["model_identity"]["model_id"],
        point_id=job["model_identity"]["point_id"],
        parameter_tensors=parameters,
    )
    require(
        identity.model_dump(mode="json") == job["model_identity"], "wrong installed final point"
    )
    return LocalTorchProvider(model, tokenizer, identity, parameter_tensors=parameters)


def seal_model(output, plan, job):
    inspected = inspect_model(output, plan, job)
    require(
        inspected["sealed"] and inspected["completed"] == DENOMINATOR,
        "all883 must be sealed before opening private references",
    )
    run, original, episodes = sealed_episodes(generation_root(output, job))
    require(
        run["tasks"] == plan["tasks"]
        and len(episodes) == DENOMINATOR
        and run["provider"] == job["model_identity"],
        "whole registered final cohort required",
    )
    seal = bound(
        dict(
            schema="v9_final_model_whole_dev_generation.v1",
            protocol_id=plan["id"],
            seed=job["seed"],
            arm=job["arm"],
            checkpoint_sha256=job["state_sha256"],
            denominator=DENOMINATOR,
            run_id=run["id"],
            generation_seal_id=original["id"],
            generation_seal=file_binding(
                generation_root(output, job) / "generation_seal/seal.json"
            ),
            episode_sha256=[digest(e) for e in episodes],
            all_generation_complete=True,
            all_provider_calls_settled=True,
            private_references_read=False,
        )
    )
    _publish(model_root(output, job) / "whole_dev_seal", seal)
    return seal, episodes


def native_metrics(results):
    require(len(results) == DENOMINATOR, "complete883 native result rows required")
    metrics = {}
    for name in ("execution_accuracy", "program_accuracy"):
        values = [r["native"]["native"][name] for r in results]
        require(
            all(v is None or type(v) in (int, float) and v in (0, 1) for v in values),
            "native result must be a known binary score or explicit unknown",
        )
        known = [v for v in values if v is not None]
        metrics[name] = dict(
            denominator=DENOMINATOR,
            scored=len(known),
            unknown=len(values) - len(known),
            correct=sum(known),
            complete_dataset_mean=sum(known) / DENOMINATOR if len(known) == DENOMINATOR else None,
        )
    return metrics


def score_model(output, seed, arm):
    plan = checked_plan(output)
    job = plan["jobs"][coordinate(seed, arm)]
    seal, episodes = seal_model(output, plan, job)  # No private reference read before this.
    manifest, tasks, lineages = load_public_snapshot(plan["snapshot"])
    require(manifest["id"] == plan["snapshot_id"], "score source changed")
    references = _read_snapshot_rows(
        plan["snapshot"], "private.references.jsonl", PrivateReference, manifest
    )
    wanted = set(plan["tasks"])
    bundles = {
        task_key(t): TaskBundle(public=t, reference=r, lineage=lineage)
        for t, r, lineage in zip(tasks, references, lineages, strict=True)
        if task_key(t) in wanted
    }
    results = [
        dict(
            task_key=key,
            native=score_public_reasoning_program(bundles[key], ep),
            stop_reason=ep.stop_reason,
            actual_model_calls=ep.actual_model_calls,
            source_group=plan["source_groups"][key],
        )
        for key, ep in zip(plan["tasks"], episodes, strict=True)
    ]
    metrics = native_metrics(results)
    report = bound(
        dict(
            schema="v9_final_model_dev_report.v1",
            protocol_id=plan["id"],
            seed=seed,
            arm=arm,
            checkpoint_sha256=job["state_sha256"],
            model_identity=job["model_identity"],
            generation_seal_id=seal["id"],
            denominator=DENOMINATOR,
            metrics=metrics,
            results=results,
            native_status_counts=dict(Counter(r["native"]["status"] for r in results)),
            paired_statistics_admitted=all(v["unknown"] == 0 for v in metrics.values()),
            unknown_as_zero=False,
            trajectory_CompletePass_claimed=False,
            trained_Student_count=1,
            automatic_other_model_launch=False,
        )
    )
    _publish(model_root(output, job) / "scores", report)
    return report


def run_model(output, seed, arm, gpu_index, *, resume=False):
    output = Path(output)
    plan = checked_plan(output)
    job = plan["jobs"][coordinate(seed, arm)]
    root = model_root(output, job)
    require(
        resume or not (root / "attempts").exists(),
        "existing model attempt requires explicit resume",
    )
    progress = inspect_model(output, plan, job)  # Incomplete event intent blocks BEFORE GPU.
    if progress["sealed"]:
        return score_model(output, seed, arm)
    state = read_registered_state(plan, job)  # Wrong point blocks BEFORE GPU.
    locks = output / "locks"
    locks.mkdir(exist_ok=True)
    with (locks / (digest(coordinate(seed, arm)) + ".lock")).open("a") as model_lock:
        fcntl.flock(model_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        row = eligible_gpu(plan, gpu_index, gpu_inventory())
        with (locks / ("gpu-" + digest(row["uuid"]) + ".lock")).open("a") as gpu_lock:
            fcntl.flock(gpu_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            current = eligible_gpu(plan, gpu_index, gpu_inventory())
            require(current["uuid"] == row["uuid"], "GPU identity changed")
            require(
                not torch.cuda.is_initialized()
                or os.environ.get("CUDA_VISIBLE_DEVICES") == row["uuid"],
                "new process required to remap initialized CUDA",
            )
            os.environ["CUDA_VISIBLE_DEVICES"] = row["uuid"]
            os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")
            attempt = root / "attempts" / f"{len(list((root / 'attempts').glob('*'))) + 1:03d}"
            _publish(
                attempt / "intent",
                dict(
                    at=now(),
                    protocol_id=plan["id"],
                    seed=seed,
                    arm=arm,
                    pid=os.getpid(),
                    gpu=current,
                    explicit_resume=resume,
                    checkpoint_sha256=job["state_sha256"],
                ),
            )
            provider = None
            try:
                provider = load_final_provider(plan, job, state)
                asyncio.run(execute_run(generation_root(output, job), provider))
            except Exception as failure:
                _publish(
                    attempt / "blocked",
                    dict(
                        at=now(),
                        error_type=type(failure).__name__,
                        error=str(failure),
                        retry=False,
                        unknown_as_zero=False,
                        recovery="explicit resume; keep originals; never resample existing intent",
                    ),
                )
                raise
            finally:
                if provider is not None:
                    del provider
                if torch.cuda.is_initialized():
                    torch.cuda.empty_cache()
    return score_model(output, seed, arm)


def paired_summary(reports, tasks, groups, base_metrics):
    """Descriptive paired effects with distinct seed/question/source-cluster layers."""
    require(
        len(tasks) == len(set(tasks)) == DENOMINATOR and set(groups) == set(tasks),
        "same883 tasks and their original sources required",
    )
    require(
        set(reports) == {coordinate(s, a) for s in SEEDS for a in ARMS},
        "all fifteen final models required; no successful prefix statistics",
    )
    values = {}
    for seed in SEEDS:
        for arm in ARMS:
            report = reports[coordinate(seed, arm)]
            require(
                report["seed"] == seed
                and report["arm"] == arm
                and report["denominator"] == DENOMINATOR
                and [r["task_key"] for r in report["results"]] == tasks,
                "paired report coordinate/task denominator changed",
            )
            metrics = native_metrics(report["results"])
            require(
                metrics == report["metrics"] and all(m["unknown"] == 0 for m in metrics.values()),
                "unknown or incomplete native scoring cannot enter paired statistics",
            )
            for metric in metrics:
                values[seed, arm, metric] = [
                    r["native"]["native"][metric] for r in report["results"]
                ]
    comparisons = {}
    for metric in ("execution_accuracy", "program_accuracy"):
        comparisons[metric] = {}
        for candidate, control in COMPARISONS:
            per_seed, differences = {}, []
            for seed in SEEDS:
                diff = [
                    a - b
                    for a, b in zip(
                        values[seed, candidate, metric], values[seed, control, metric], strict=True
                    )
                ]
                differences.append(diff)
                per_seed[str(seed)] = dict(
                    task_denominator=DENOMINATOR,
                    mean_difference=sum(diff) / DENOMINATOR,
                    wins=sum(d > 0 for d in diff),
                    losses=sum(d < 0 for d in diff),
                    ties=sum(d == 0 for d in diff),
                )
            by_question = [
                sum(ds[i] for ds in differences) / len(SEEDS) for i in range(DENOMINATOR)
            ]
            clusters = defaultdict(list)
            for key, difference in zip(tasks, by_question, strict=True):
                clusters[groups[key]["group"]].append(difference)
            means = [v["mean_difference"] for v in per_seed.values()]
            comparisons[metric][candidate + "-" + control] = dict(
                paired_by_seed=per_seed,
                mean_difference=sum(means) / len(SEEDS),
                descriptive_seed_range=[min(means), max(means)],
                descriptive_seed_sample_sd=math.sqrt(
                    sum((m - sum(means) / 3) ** 2 for m in means) / 2
                ),
                repeated_task_count=DENOMINATOR,
                training_seed_count=3,
                per_question_mean_difference=dict(zip(tasks, by_question, strict=True)),
                source_cluster_summaries={
                    key: dict(task_count=len(ds), mean_difference=sum(ds) / len(ds))
                    for key, ds in sorted(clusters.items())
                },
                source_cluster_count=len(clusters),
                confidence_interval=None,
                p_value=None,
            )
    ordinary = {}
    for metric in ("execution_accuracy", "program_accuracy"):
        baseline = base_metrics[metric]
        require(
            baseline["denominator"] == DENOMINATOR
            and baseline["unknown"] == 0
            and baseline["complete_dataset_mean"] is not None,
            "unknown Base aggregate",
        )
        ordinary[metric] = {
            str(seed): sum(values[seed, "Static", metric]) / DENOMINATOR
            - baseline["complete_dataset_mean"]
            for seed in SEEDS
        }
    return dict(
        comparisons=comparisons,
        Static_minus_Base_ordinary_learning=ordinary,
        statistics_contract=statistics_contract(),
        full_task_denominator=DENOMINATOR,
        source_group_count=len({g["group"] for g in groups.values()}),
        distinct_question_count=DENOMINATOR,
        question_independence_assumed=False,
        total_repeated_model_episodes=13245,
        process_reliability_improvement_claimed=False,
        effects_are_measured_only_after_all_returns=True,
    )


def aggregate(output):
    output = Path(output)
    plan = checked_plan(output)
    reports, bindings = {}, {}
    for key, job in plan["jobs"].items():
        seal, _ = seal_model(output, plan, job)
        path = model_root(output, job) / "scores/record.json"
        report = read_bound(path)
        require(
            report["schema"] == "v9_final_model_dev_report.v1"
            and report["protocol_id"] == plan["id"]
            and report["generation_seal_id"] == seal["id"]
            and report["checkpoint_sha256"] == job["state_sha256"]
            and report["model_identity"] == job["model_identity"],
            "final report is not this sealed actual endpoint",
        )
        reports[key], bindings[key] = report, file_binding(path)
    result = bound(
        dict(
            schema="v9_fifteen_final_dev_paired_summary.v1",
            protocol_id=plan["id"],
            report_bindings=bindings,
            Base_score_id=plan["Base_score_id"],
            Base_score_report=plan["Base_score_report"],
            Base_rerun=False,
            **paired_summary(
                reports, plan["tasks"], plan["source_groups"], plan["Base_aggregate_metrics"]
            ),
            main_effect="comparisons.execution_accuracy.Full-Static",
            inference_scope="fixed conditional training material; unchanged full dev883",
            no_best_seed_selection=True,
            public_test_evaluated=False,
            API_calls_added=0,
        )
    )
    _publish(output / "paired_summary", result)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "action",
        choices=(
            "register",
            "run-model",
            "resume-model",
            "run-seed",
            "resume-seed",
            "score-model",
            "aggregate",
        ),
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--training-root", type=Path)
    parser.add_argument("--base-output", type=Path, default=base.OUTPUT)
    parser.add_argument("--seed", type=int, choices=SEEDS)
    parser.add_argument("--arm", choices=ARMS)
    parser.add_argument("--gpu", type=int)
    args = parser.parse_args(argv)
    if args.action == "register":
        require(args.training_root is not None, "--training-root required")
        result = register(args.training_root, args.output, base_output=args.base_output)
    elif args.action == "aggregate":
        result = aggregate(args.output)
    elif args.action == "score-model":
        result = score_model(args.output, args.seed, args.arm)
    else:
        require(args.seed is not None and args.gpu is not None, "--seed and --gpu required")
        arms = ARMS if args.action.endswith("seed") else (args.arm,)
        for arm in arms:
            result = run_model(
                args.output, args.seed, arm, args.gpu, resume=args.action.startswith("resume")
            )
    print(dict(schema=result["schema"], id=result["id"]))


if __name__ == "__main__":
    main()
