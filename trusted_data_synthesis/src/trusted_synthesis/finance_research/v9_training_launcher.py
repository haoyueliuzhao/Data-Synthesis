"""Conditional five-arm production entrypoint; no resources are held on import.

Registration requires complete, frozen production material and an explicit
pre-Student scale decision. Execution uses the existing Qwen/LowRankLinear
loader, AdamW driver and real fixed-700 local feedback collector. No API,
generation, qualification, evaluation, or old material repair is launched here.
"""

from __future__ import annotations

import argparse
import copy
import fcntl
import hashlib
import json
import os
import re
from pathlib import Path

import torch

from trusted_synthesis.experiments.finance_qa_vnext_pq_student.model import (
    adapter_digest,
    load_student,
)

from .calibration import gpu_inventory, now
from .contracts import RunConfig, digest
from .storage import runtime_binding
from .v6_distribution import ARMS
from .v7_base_evaluation import ORIGIN, evaluation_config, load_tokenizer
from .v8_training_driver import LocalFeedbackCollector, _publish, validate_student_adapters
from .v9_conditional_training import ConditionalTrainingDriver
from .v10_training import load_training_pool

SEEDS = (11, 29, 47)
ARM_DIRECTORIES = dict(
    zip(ARMS, ("static", "manual_plus", "manual_minus", "c_only", "full"), strict=True)
)
MINIMUM_FREE_MIB = 24576
PHASE_ORDER = {"initial": 0, "step": 1, "branch": 2, "outer": 3}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def bound(value):
    return {**value, "id": digest(value)}


def read_bound(path):
    value = json.loads(Path(path).read_bytes())
    require(
        value.get("id") == digest({k: v for k, v in value.items() if k != "id"}),
        "bound launcher record changed",
    )
    return value


def file_binding(path):
    path = Path(path).resolve()
    return dict(path=str(path), sha256=sha(path))


def material_identity(pool, *, require_nontrivial=True):
    """Cheap finite identification, not a replacement for the production loader."""
    require(
        pool.production_verified and pool.conditional_scope_verified,
        "complete verified conditional material required before any Student/device use",
    )
    profile = pool.capability_profile
    n = len(pool.task_ids)
    prior = pool._manifest.registration.pi0
    degrees = sum(len(prior[t]) - 1 for t in pool.task_ids)
    flexible = sum(len(prior[t]) > 1 for t in pool.task_ids)
    mixed = sum(set(pool.chi[t].values()) == {0, 1} for t in pool.task_ids)
    require(n > 0, "nonempty actual conditional support required")
    if require_nontrivial:
        require(
            degrees > 0 and mixed > 0,
            "nontrivial pi AND within-task chi0/1 support required for five distinct arms",
        )
    require(
        profile["D_pi"] == degrees
        and profile["multi_state_tasks"] == flexible
        and profile["chi_flexible_tasks"] == mixed
        and pool.execution_plan["N"] == n,
        "actual frozen material profile/schedule differs",
    )
    return dict(
        pool_id=pool.cache_id,
        support_manifest_id=pool.support_manifest["id"],
        N=n,
        capability_profile_sha256=digest(profile),
        capability_profile=copy.deepcopy(profile),
        execution_plan=copy.deepcopy(pool.execution_plan),
    )


def scale_decision(material_binding, output, *, decision, rationale, scope_confirmed):
    """Explicit investigator decision, based on actual material BEFORE any Student.

    This does not infer statistical power, choose a favourable subset, or grant
    the original 1000-task protocol admission. N is never supplied by the caller.
    """
    require(
        decision in ("proceed_exploratory", "stop") and rationale.strip(),
        "explicit prospective scale decision and rationale required",
    )
    require(scope_confirmed is True, "conditional inference scope must be explicitly confirmed")
    pool = load_training_pool(material_binding)
    identity = material_identity(pool, require_nontrivial=decision != "stop")
    output = Path(output)
    require(not output.exists(), "scale decision is immutable; never overwrite after results")
    value = bound(
        dict(
            schema="v9_pre_student_scale_decision.v1",
            at=now(),
            material_binding=file_binding(material_binding),
            material_identity=identity,
            decision=decision,
            rationale=rationale,
            conditional_scope_confirmed=True,
            interpretation="exploratory_fixed_empirical_support",
            statistical_power_claimed=False,
            student_results_used=False,
            task_or_package_selection_performed=False,
            original1000_protocol_admitted=False,
        )
    )
    _publish(output, value)
    return value


def feedback_config():
    return RunConfig(
        harness_id="bigfinance-derived-vtdo-v7",
        submission_profile="finqa-public-reasoning-v2",
        role="feedback",
        tier="VTDO_FEEDBACK",
        local_tool_protocol="qwen2.5-native-tool-call-v1",
        seed=11,
        temperature=1,
        top_p=1,
        top_k=0,
        max_steps=32,
        max_new_tokens=2048,
        context_limit=24576,
    )


def register(
    material_binding,
    scale_record,
    output,
    *,
    assets_protocol=ORIGIN,
    allowed_gpu_indices=(0,),
    minimum_free_mib=MINIMUM_FREE_MIB,
):
    """No model/GPU inspection or allocation; full material loader runs first."""
    output = Path(output)
    require(not output.exists(), "production launch registration must be new and immutable")
    pool = load_training_pool(material_binding)
    identity = material_identity(pool)
    scale = read_bound(scale_record)
    if scale.get("schema") == "v15_prospective_condition_realization.v1":
        from .v15_continuation import validate_condition_realization

        validate_condition_realization(scale, material_binding, identity)
    if scale.get("schema") == "v16_six_task_condition_realization.v1":
        from .v16_continuation import validate_condition_realization

        validate_condition_realization(scale, material_binding, identity)
    if scale.get("schema") == "v17_three_task_condition_realization.v1":
        from .v17_continuation import validate_condition_realization

        validate_condition_realization(scale, material_binding, identity)
    if scale.get("schema") == "v18_researcher_condition_realization.v1":
        from .v18_continuation import validate_condition_realization

        validate_condition_realization(scale, material_binding, identity)
    require(
        scale["schema"]
        in {
            "v9_pre_student_scale_decision.v1",
            "v15_prospective_condition_realization.v1",
            "v16_six_task_condition_realization.v1",
            "v17_three_task_condition_realization.v1",
            "v18_researcher_condition_realization.v1",
        }
        and scale["material_identity"] == identity
        and scale["material_binding"] == file_binding(material_binding)
        and scale["decision"] == "proceed_exploratory"
        and scale["conditional_scope_confirmed"] is True
        and scale["student_results_used"] is False
        and scale["statistical_power_claimed"] is False,
        "actual-profile prospective scale decision required; never assume power from N",
    )
    assets_source = read_bound(assets_protocol)
    require(
        assets_source["assets"]["base_binding"]["config"]["model_type"] == "qwen2",
        "original Qwen2.5-7B-Instruct assets required",
    )
    # Source role identity, not any Base/dev results. Collector enforces350x2 at runtime.
    roles = assets_source["role_plan"]
    require(
        sum(v == "feedback" for v in roles["assignments"].values()) == 350
        and sum(v == "development" for v in roles["assignments"].values()) == 883,
        "feedback350 and complete V7 dev883 roles unchanged",
    )
    indices = list(allowed_gpu_indices)
    require(
        indices
        and len(indices) == len(set(indices))
        and all(type(i) is int and i >= 0 for i in indices),
        "explicit allowed GPU indices",
    )
    require(
        type(minimum_free_mib) is int and minimum_free_mib >= 16384,
        "finite realistic free-memory admission floor required",
    )
    plan = bound(
        dict(
            schema="v9_conditional_five_arm_launcher.v1",
            at=now(),
            runtime_binding=runtime_binding(),
            material_binding=file_binding(material_binding),
            material_identity=identity,
            scale_decision=file_binding(scale_record),
            scale_decision_id=scale["id"],
            assets_protocol=file_binding(assets_protocol),
            assets_protocol_id=assets_source["id"],
            seeds=list(SEEDS),
            arms=list(ARMS),
            student=dict(
                model="Qwen2.5-7B-Instruct",
                base_dtype="bfloat16",
                base_frozen=True,
                adapter="repository.LowRankLinear",
                targets=["q_proj", "v_proj"],
                rank=8,
                alpha=16,
                dropout=0.05,
                adapter_dtype="float32",
                old_adapter_loaded=False,
            ),
            optimizer=dict(name="AdamW", lr=1e-4, betas=[0.9, 0.999], eps=1e-8, weight_decay=0),
            feedback_config=feedback_config().model_dump(mode="json"),
            feedback_seeds=[11, 29],
            feedback_denominator=700,
            feedback_root_separate_per_arm=True,
            same_point_savings_assumed=False,
            full_dev_config=evaluation_config().model_dump(mode="json"),
            dev_denominator=883,
            Base_rerun=False,
            automatic_evaluation=False,
            test_denominator=1147,
            device_policy=dict(
                allowed_gpu_indices=indices,
                minimum_free_mib=minimum_free_mib,
                allow_other_processes_if_memory_available=True,
                free_memory_is_heuristic_not_cuda_acceptance=True,
                no_placeholder=True,
                no_waiting_with_loaded_model=True,
            ),
            explicit_resume_required=True,
            partial_feedback_resampled=False,
            API_calls=0,
            CUDA_acceptance_completed=False,
            original1000_protocol_admitted=False,
        )
    )
    _publish(output / "registration", plan)
    return plan


def checked_launch(output):
    plan = read_bound(Path(output) / "registration/record.json")
    require(
        plan["schema"] == "v9_conditional_five_arm_launcher.v1"
        and plan["runtime_binding"] == runtime_binding(),
        "frozen launcher source changed",
    )
    for key in ("material_binding", "scale_decision", "assets_protocol"):
        require(sha(plan[key]["path"]) == plan[key]["sha256"], key + " bytes changed")
    pool = load_training_pool(plan["material_binding"]["path"])
    require(
        material_identity(pool) == plan["material_identity"],
        "frozen X* or all-package kernel changed",
    )
    scale = read_bound(plan["scale_decision"]["path"])
    if scale.get("schema") == "v15_prospective_condition_realization.v1":
        from .v15_continuation import validate_condition_realization

        validate_condition_realization(
            scale, plan["material_binding"]["path"], plan["material_identity"]
        )
    if scale.get("schema") == "v16_six_task_condition_realization.v1":
        from .v16_continuation import validate_condition_realization

        validate_condition_realization(
            scale, plan["material_binding"]["path"], plan["material_identity"]
        )
    if scale.get("schema") == "v17_three_task_condition_realization.v1":
        from .v17_continuation import validate_condition_realization

        validate_condition_realization(
            scale, plan["material_binding"]["path"], plan["material_identity"]
        )
    if scale.get("schema") == "v18_researcher_condition_realization.v1":
        from .v18_continuation import validate_condition_realization

        validate_condition_realization(scale, plan["material_binding"]["path"], plan["material_identity"])
    require(
        scale["id"] == plan["scale_decision_id"] and scale["decision"] == "proceed_exploratory",
        "prospective scale decision changed",
    )
    assets = read_bound(plan["assets_protocol"]["path"])
    require(assets["id"] == plan["assets_protocol_id"], "original assets/role contract changed")
    return plan, pool, assets


def latest_checkpoint(directory):
    """Select only a durable actual commit; an outer commit wins at the same step."""
    directory = Path(directory)
    found = []
    for path in directory.glob("step*_*"):
        match = re.fullmatch(r"step([0-9]+)_(initial|step|branch|outer)", path.name)
        require(
            match is not None and path.is_dir(), "unknown checkpoint entry; explicit audit required"
        )
        found.append((int(match[1]), PHASE_ORDER[match[2]], path))
    if not found:
        return None
    step, _, path = max(found, key=lambda value: value[:2])
    record = json.loads((path / "record.json").read_bytes())
    require(sha(path / "state.pt") == record["state_sha256"], "committed state bytes changed")
    require(
        record["step"] == step and path.name.endswith("_" + record["phase"]),
        "checkpoint coordinate differs",
    )
    return path


def no_partial_feedback(seed_root):
    for intent in Path(seed_root).glob("arms/*/feedback/*/intent/record.json"):
        point = intent.parent.parent
        require(
            all((point / f"draw{i}/generation_seal/seal.json").is_file() for i in range(2)),
            "partial fixed700 retained; no automatic resampling or fresh feedback root",
        )


def eligible_gpu(plan, index, inventory):
    policy = plan["device_policy"]
    require(index in policy["allowed_gpu_indices"], "GPU outside registered allowed scope")
    rows = [r for r in inventory if r["index"] == index]
    require(
        len(rows) == 1 and rows[0]["free"] >= policy["minimum_free_mib"],
        "insufficient GPU margin; no allocation/placeholder/wait",
    )
    return rows[0]


def fresh_student_evidence(model, optimizer, scope, seed):
    architecture = validate_student_adapters(model, scope)
    named = {n: p for n, p in model.named_parameters() if p.requires_grad}
    require(not optimizer.state, "fresh optimizer must not contain previous moments")
    require(all(torch.isfinite(p).all().item() for p in named.values()), "nonfinite fresh adapter")
    require(
        all(torch.count_nonzero(p).item() == 0 for n, p in named.items() if n.endswith(".lora_B")),
        "fresh LoRA B must be zero, never load an old trained adapter",
    )
    require(
        all(torch.count_nonzero(p).item() > 0 for n, p in named.items() if n.endswith(".lora_A")),
        "fresh seeded LoRA A initialization missing",
    )
    return dict(
        seed=seed,
        architecture=architecture,
        adapter_digest=adapter_digest(model),
        actual_Adam_state_empty=True,
        actual_B_zero=True,
        loaded_old_adapter=False,
        initialization="original load_student seeded fresh q/v",
    )


def _load_components(assets, seed):
    tokenizer = load_tokenizer(assets["assets"])
    model, scope = load_student(assets["assets"]["base_binding"], seed, trainable=True)
    optimizer = torch.optim.AdamW(
        [p for p in model.parameters() if p.requires_grad],
        lr=1e-4,
        betas=(0.9, 0.999),
        eps=1e-8,
        weight_decay=0,
        amsgrad=False,
        maximize=False,
        foreach=False,
        fused=False,
    )
    fresh = fresh_student_evidence(model, optimizer, scope, seed)
    return model, tokenizer, optimizer, scope, fresh


def _checkpoint_ref(path):
    record = json.loads((Path(path) / "record.json").read_bytes())
    return dict(
        path=str(Path(path).resolve()),
        state_sha256=record["state_sha256"],
        actual_state_digest=record["actual_state_digest"],
        step=record["step"],
        phase=record["phase"],
        arm=record["arm"],
    )


def _execute_loaded_seed(output, plan, pool, assets, seed, components, *, resume):
    model, tokenizer, optimizer, scope, fresh = components
    seed_root = Path(output) / f"seed{seed}"
    shared_root = seed_root / "shared"
    shared_checkpoint = latest_checkpoint(shared_root)
    if shared_checkpoint is None:
        _publish(seed_root / "fresh_initialization", fresh)
    driver_args = dict(device="cuda:0", tokenizer=tokenizer, adapter_scope=scope)
    shared = ConditionalTrainingDriver(
        model, optimizer, pool, root=shared_root, seed=seed, arm="shared", **driver_args
    )
    if shared_checkpoint is not None:
        require(resume, "existing commit requires explicit resume")
        shared.restore(shared_checkpoint)
    shared.run_until(shared.shared_step)
    shared_checkpoint = latest_checkpoint(shared_root)
    require(shared_checkpoint is not None, "shared actual checkpoint missing")
    results = {}
    for arm in ARMS:
        arm_root = seed_root / "arms" / ARM_DIRECTORIES[arm]
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
            feedback_collector=collector,
            **driver_args,
        )
        committed = latest_checkpoint(driver.root)
        if committed is None:
            driver.restore(shared_checkpoint, branch=True)
        else:
            require(resume, "existing arm commit requires explicit resume")
            driver.restore(committed)
        result = driver.run_until(driver.final_step)
        expected_outer = list(driver.outer_steps) if arm in ("C-only", "Full") else []
        require(
            driver.step_index == driver.final_step and driver.outer_done == expected_outer,
            "final arm requires every real scheduled outer update",
        )
        results[arm] = dict(
            result=result, final_checkpoint=_checkpoint_ref(latest_checkpoint(driver.root))
        )
    value = bound(
        dict(
            schema="v9_conditional_five_arm_seed_result.v1",
            protocol_id=plan["id"],
            pool_id=pool.cache_id,
            seed=seed,
            shared_checkpoint=_checkpoint_ref(shared_checkpoint),
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
    _publish(seed_root / "result", value)
    return value


def run_seed(output, seed, gpu_index, *, resume=False):
    """One process, one real Student, shared prefix then five sequential arms."""
    require(seed in SEEDS, "registered seeds11/29/47 only")
    output = Path(output)
    plan, pool, assets = checked_launch(output)  # BEFORE any GPU query/allocation.
    seed_root = output / f"seed{seed}"
    require(resume or not seed_root.exists(), "existing seed requires explicit resume")
    no_partial_feedback(seed_root)
    locks = output / "locks"
    locks.mkdir(exist_ok=True)
    with (locks / f"seed{seed}.lock").open("a") as seed_lock:
        fcntl.flock(seed_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
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
            attempt_root = seed_root / "launch_attempts"
            number = len(list(attempt_root.glob("attempt*"))) + 1
            attempt = attempt_root / f"attempt{number:03d}"
            _publish(
                attempt / "intent",
                dict(
                    at=now(),
                    protocol_id=plan["id"],
                    seed=seed,
                    explicit_resume=resume,
                    pid=os.getpid(),
                    gpu_observed=current,
                    no_GPU_placeholder=True,
                ),
            )
            components = None
            try:
                components = _load_components(assets, seed)
                return _execute_loaded_seed(
                    output, plan, pool, assets, seed, components, resume=resume
                )
            except Exception as failure:
                _publish(
                    attempt / "stopped",
                    dict(
                        at=now(),
                        error_type=type(failure).__name__,
                        error=str(failure),
                        retry_performed=False,
                        partial_feedback_resampled=False,
                        recovery="explicit resume restores committed model/Adam/RNG/pi",
                        CUDA_acceptance_not_assumed=True,
                    ),
                )
                raise
            finally:
                if components is not None:
                    del components
                if torch.cuda.is_initialized():
                    torch.cuda.empty_cache()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("scale-decision", "register", "run-seed", "resume-seed"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--material-binding", type=Path)
    parser.add_argument("--scale-record", type=Path)
    parser.add_argument("--assets-protocol", type=Path, default=ORIGIN)
    parser.add_argument("--gpus", default="0")
    parser.add_argument("--minimum-free-mib", type=int, default=MINIMUM_FREE_MIB)
    parser.add_argument("--decision", choices=("proceed_exploratory", "stop"))
    parser.add_argument("--rationale", default="")
    parser.add_argument("--scope-confirmed", action="store_true")
    parser.add_argument("--seed", type=int, choices=SEEDS)
    parser.add_argument("--gpu", type=int)
    args = parser.parse_args(argv)
    if args.action == "scale-decision":
        require(args.material_binding is not None, "--material-binding required")
        value = scale_decision(
            args.material_binding,
            args.output,
            decision=args.decision,
            rationale=args.rationale,
            scope_confirmed=args.scope_confirmed,
        )
    elif args.action == "register":
        require(
            args.material_binding is not None and args.scale_record is not None,
            "--material-binding and --scale-record required",
        )
        value = register(
            args.material_binding,
            args.scale_record,
            args.output,
            assets_protocol=args.assets_protocol,
            allowed_gpu_indices=tuple(int(i) for i in args.gpus.split(",")),
            minimum_free_mib=args.minimum_free_mib,
        )
    else:
        require(args.seed is not None and args.gpu is not None, "--seed and --gpu required")
        value = run_seed(args.output, args.seed, args.gpu, resume=args.action == "resume-seed")
    print(dict(schema=value["schema"], id=value["id"]))


if __name__ == "__main__":
    main()
