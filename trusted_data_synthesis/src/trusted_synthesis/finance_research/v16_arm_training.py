"""Independent original-arm tails from an already migrated real step298.

This execution-only entrypoint never trains a shared prefix, changes the five
arms, shares feedback, or opens evaluation data. Registration/source admission,
the actual driver and fixed700 collector remain the existing production ones.
"""

from __future__ import annotations

import argparse
import fcntl
import json
import os
from pathlib import Path

import torch

from .calibration import gpu_inventory, now
from .contracts import digest
from .v6_distribution import ARMS
from .v8_training_driver import LocalFeedbackCollector, _publish
from .v9_conditional_training import ConditionalTrainingDriver
from .v9_training_launcher import (
    ARM_DIRECTORIES,
    SEEDS,
    _checkpoint_ref,
    _load_components,
    bound,
    checked_launch,
    eligible_gpu,
    latest_checkpoint,
    read_bound,
    require,
)


def shared_checkpoint(output, plan, pool, seed):
    """Only the completed zero-update V15 migration is a valid branch source."""
    execution = plan["material_identity"]["execution_plan"]
    require(
        execution["N"] == 744
        and execution["shared_step"] == 298
        and execution["outer_steps"] == [298, 596, 894, 1192]
        and execution["final_step"] == 1490,
        "original fixed744/step298/five-arm coordinates required",
    )
    path = latest_checkpoint(Path(output) / f"seed{seed}/shared")
    require(path is not None, "actual migrated shared step298 required; prefix training forbidden")
    record = json.loads((path / "record.json").read_bytes())
    proof = record.get("evidence", {})
    require(
        record["step"] == 298
        and record["phase"] == "step"
        and record["arm"] == "shared"
        and record["seed"] == seed
        and record["pool_id"] == pool.cache_id
        and proof.get("schema") == "v15_completed_prefix_migration.v1"
        and proof.get("id") == digest({k: v for k, v in proof.items() if k != "id"})
        and proof.get("full_pool_id") == pool.cache_id
        and proof.get("optimizer_steps_performed") == 0
        and proof.get("prefix_retrained") is False
        and proof.get("first_outer_not_executed") is True,
        "branch source must be the bound zero-update completed-prefix migration",
    )
    return path


def no_partial_arm_feedback(arm_root):
    """An unrelated arm's failed cohort does not cancel other original arms."""
    for intent in Path(arm_root).glob("feedback/*/intent/record.json"):
        point = intent.parent.parent
        require(
            all((point / f"draw{i}/generation_seal/seal.json").is_file() for i in range(2)),
            "partial fixed700 retained; no automatic resampling or fresh feedback root",
        )


def _execute_loaded_arm(output, plan, pool, assets, seed, arm, components, *, resume, shared):
    model, tokenizer, optimizer, scope, _fresh = components
    arm_root = Path(output) / f"seed{seed}/arms" / ARM_DIRECTORIES[arm]
    collector = None
    if arm in ("C-only", "Full"):
        collector = LocalFeedbackCollector(
            snapshot=assets["snapshot"],
            role_plan=assets["role_plan"],
            root=arm_root / "feedback",
            config=plan["feedback_config"],
            model_id=assets["assets"]["base_binding"]["id"],
            seeds=tuple(plan["feedback_seeds"]),
        )
    driver = ConditionalTrainingDriver(
        model,
        optimizer,
        pool,
        root=arm_root / "training",
        seed=seed,
        arm=arm,
        device="cuda:0",
        tokenizer=tokenizer,
        adapter_scope=scope,
        feedback_collector=collector,
    )
    committed = latest_checkpoint(driver.root)
    if committed is None:
        driver.restore(shared, branch=True)
    else:
        require(resume, "existing arm commit requires explicit resume")
        driver.restore(committed)
    # run_until executes a due outer BEFORE departing298, including resume.
    result = driver.run_until(driver.final_step)
    expected_outer = list(driver.outer_steps) if arm in ("C-only", "Full") else []
    require(
        driver.step_index == driver.final_step and driver.outer_done == expected_outer,
        "final arm requires every actual scheduled outer update",
    )
    value = bound(
        dict(
            schema="v16_independent_original_arm_result.v1",
            protocol_id=plan["id"],
            pool_id=pool.cache_id,
            seed=seed,
            arm=arm,
            shared_checkpoint=_checkpoint_ref(shared),
            result=result,
            final_checkpoint=_checkpoint_ref(latest_checkpoint(driver.root)),
            actual_student_training=True,
            actual_feedback_denominator=700 if collector is not None else 0,
            prefix_retrained=False,
            cross_arm_feedback_shared=False,
            automatic_evaluation=False,
            evaluation_dev883_completed=False,
            test_opened=False,
        )
    )
    _publish(arm_root / "result", value)
    return value


def run_arm(output, seed, arm, gpu_index, *, resume=False):
    """One original tail per process; do not reserve or wait with a loaded model."""
    require(seed in SEEDS and arm in ARMS, "original fifteen seed/arm coordinates only")
    output = Path(output).resolve()
    plan, pool, assets = checked_launch(output)  # Complete source/material gate before GPU.
    shared = shared_checkpoint(output, plan, pool, seed)
    arm_root = output / f"seed{seed}/arms" / ARM_DIRECTORIES[arm]
    require(resume or not arm_root.exists(), "existing arm requires explicit resume")
    no_partial_arm_feedback(arm_root)
    require(not (arm_root / "result/record.json").exists(), "completed arm must not be rerun")
    locks = output / "locks"
    locks.mkdir(exist_ok=True)
    # Shared seed lock allows independent arms but excludes the old run-seed
    # entrypoint, which holds this exact file exclusively while looping all arms.
    with (
        (locks / f"seed{seed}.lock").open("a") as seed_lock,
        (locks / f"seed{seed}-{ARM_DIRECTORIES[arm]}.lock").open("a") as arm_lock,
    ):
        fcntl.flock(seed_lock, fcntl.LOCK_SH | fcntl.LOCK_NB)
        fcntl.flock(arm_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        no_partial_arm_feedback(arm_root)
        row = eligible_gpu(plan, gpu_index, gpu_inventory())
        with (locks / ("gpu-" + digest(row["uuid"]) + ".lock")).open("a") as gpu_lock:
            fcntl.flock(gpu_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            current = eligible_gpu(plan, gpu_index, gpu_inventory())
            require(current["uuid"] == row["uuid"], "GPU identity changed before loading")
            require(
                not torch.cuda.is_initialized()
                or os.environ.get("CUDA_VISIBLE_DEVICES") == row["uuid"],
                "initialized CUDA process cannot remap to another GPU",
            )
            os.environ["CUDA_VISIBLE_DEVICES"] = row["uuid"]
            os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")
            attempts = arm_root / "launch_attempts"
            attempt = attempts / f"attempt{len(list(attempts.glob('attempt*'))) + 1:03d}"
            _publish(
                attempt / "intent",
                bound(
                    dict(
                        schema="v16_independent_arm_attempt.v1",
                        at=now(),
                        protocol_id=plan["id"],
                        seed=seed,
                        arm=arm,
                        explicit_resume=resume,
                        shared_checkpoint=_checkpoint_ref(shared),
                        pid=os.getpid(),
                        gpu_observed=current,
                        no_GPU_placeholder=True,
                        prefix_retrained=False,
                    )
                ),
            )
            components = None
            try:
                components = _load_components(assets, seed)
                return _execute_loaded_arm(
                    output,
                    plan,
                    pool,
                    assets,
                    seed,
                    arm,
                    components,
                    resume=resume,
                    shared=shared,
                )
            except Exception as failure:
                _publish(
                    attempt / "stopped",
                    bound(
                        dict(
                            at=now(),
                            error_type=type(failure).__name__,
                            error=str(failure),
                            retry_performed=False,
                            partial_feedback_resampled=False,
                            recovery="explicit resume restores committed model/Adam/RNG/pi",
                            CUDA_acceptance_not_assumed=True,
                        )
                    ),
                )
                raise
            finally:
                if components is not None:
                    del components
                if torch.cuda.is_initialized():
                    torch.cuda.empty_cache()


def aggregate_seed(output, seed):
    """CPU-only closure into the existing final/mechanism consumer's seed schema."""
    require(seed in SEEDS, "original seed required")
    output = Path(output).resolve()
    plan, pool, _assets = checked_launch(output)
    shared = shared_checkpoint(output, plan, pool, seed)
    locks = output / "locks"
    locks.mkdir(exist_ok=True)
    with (locks / f"seed{seed}-result.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        results = {}
        for arm in ARMS:
            arm_root = output / f"seed{seed}/arms" / ARM_DIRECTORIES[arm]
            result_path = arm_root / "result/record.json"
            require(
                result_path.is_file(), "all five actual arm results required before seed closure"
            )
            record = read_bound(result_path)
            latest = latest_checkpoint(arm_root / "training")
            expected_outer = pool.execution_plan["outer_steps"] if arm in ("C-only", "Full") else []
            require(
                record["schema"] == "v16_independent_original_arm_result.v1"
                and record["protocol_id"] == plan["id"]
                and record["pool_id"] == pool.cache_id
                and record["seed"] == seed
                and record["arm"] == arm
                and record["shared_checkpoint"] == _checkpoint_ref(shared)
                and record["result"]["committed_step"] == pool.execution_plan["final_step"]
                and record["result"]["outer_done"] == expected_outer
                and record["prefix_retrained"] is False
                and record["cross_arm_feedback_shared"] is False
                and latest is not None
                and record["final_checkpoint"] == _checkpoint_ref(latest)
                and record["final_checkpoint"]["step"] == pool.execution_plan["final_step"]
                and record["final_checkpoint"]["phase"] == "step",
                "actual original final arm result/checkpoint mismatch",
            )
            results[arm] = dict(
                result=record["result"], final_checkpoint=record["final_checkpoint"]
            )
        value = bound(
            dict(
                schema="v9_conditional_five_arm_seed_result.v1",
                protocol_id=plan["id"],
                pool_id=pool.cache_id,
                seed=seed,
                shared_checkpoint=_checkpoint_ref(shared),
                arms=results,
                all_five_actual_training_histories_complete=True,
                actual_student_training=True,
                actual_feedback_denominator=700,
                comparison_with_Static_measured=False,
                automatic_evaluation=False,
                evaluation_dev883_completed=False,
                Base_rerun=False,
                same_point_savings_assumed=False,
                original1000_protocol_admitted=False,
            )
        )
        _publish(output / f"seed{seed}/result", value)
        return value


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("run-arm", "resume-arm", "aggregate-seed"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--seed", type=int, choices=SEEDS, required=True)
    parser.add_argument("--arm", choices=ARMS)
    parser.add_argument("--gpu-index", type=int)
    args = parser.parse_args(argv)
    if args.action == "aggregate-seed":
        result = aggregate_seed(args.output, args.seed)
    else:
        require(args.arm is not None and args.gpu_index is not None, "--arm/--gpu-index required")
        result = run_arm(
            args.output, args.seed, args.arm, args.gpu_index, resume=args.action == "resume-arm"
        )
    print(dict(schema=result["schema"], id=result["id"]))


if __name__ == "__main__":
    main()
