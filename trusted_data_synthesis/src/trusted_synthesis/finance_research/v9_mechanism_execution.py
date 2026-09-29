"""Real registered 3s C / 5s same-point N short-training, using existing drivers.

No API or feedback is sampled by this module. Production GPU loading is explicit.
The five main arms and their checkpoints are never rewritten.
"""

from __future__ import annotations

import argparse
import asyncio
import copy
import fcntl
import io
import json
import os
from pathlib import Path

import torch

from .contracts import digest
from .providers import parameter_digest
from .v6_distribution import PARAMETERS, automatic_update, first_direction_reverse
from .v6_distribution import kernel as distribution_kernel
from .v6_mechanism_diagnostics import distribution_change
from .v8_training_driver import _publish, _require, _sha, _tree_digest
from .v9_conditional_training import ConditionalTrainingDriver


def evaluation_configs():
    from .v7_base_evaluation import evaluation_config

    original = evaluation_config()
    return [
        original.model_copy(update={"role": "calibration", "temperature": 1.0, "seed": seed})
        for seed in (11, 29)
    ] + [original.model_copy(update={"role": "calibration"})]


def _bound(body):
    return {**body, "id": digest(body)}


def _registered_update(actual, arm):
    """Same singleton controls/RMS and fixed prior as actual TrainingDriver.outer_update."""
    before = actual["pre_state"]
    if not any(actual["rewards"]):
        return automatic_update(
            before["pi"],
            before["prior"],
            actual["C"],
            actual["mu"],
            arm=arm,
            feedback_all_zero=True,
        )
    return distribution_kernel.anchored_update(
        before["pi"],
        before["prior"],
        actual["C"],
        actual["mu"],
        control_tasks=[task for task, states in before["prior"].items() if len(states) == 1],
        contribution_only=arm == "C-only",
        **PARAMETERS,
    )


def checkpoint(path):
    path = Path(path)
    record = json.loads((path / "record.json").read_bytes())
    raw = (path / "state.pt").read_bytes()
    _require(_sha(raw) == record["state_sha256"], "checkpoint bytes changed")
    state = torch.load(io.BytesIO(raw), map_location="cpu", weights_only=False)
    _require(_tree_digest(state) == record["actual_state_digest"], "checkpoint state changed")
    _require(
        state["step"] == record["step"] and state["arm"] == record["arm"],
        "checkpoint coordinate changed",
    )
    return record, state


def checkpoint_ref(path):
    record, _ = checkpoint(path)
    return dict(
        path=str(Path(path).resolve()),
        state_sha256=record["state_sha256"],
        actual_state_digest=record["actual_state_digest"],
        step=record["step"],
        arm=record["arm"],
        phase=record["phase"],
    )


def _computation_state(state):
    return {k: v for k, v in state.items() if k != "arm"}


def checked_outer(path, *, production=True):
    """Load actual tensors, not a statement that two outer points were identical."""
    path = Path(path)
    record, state = checkpoint(path)
    _require(
        record["phase"] == "outer" and state["arm"] in ("C-only", "Full"),
        "actual automatic outer checkpoint required",
    )
    raw = (path / "outer_inputs.pt").read_bytes()
    _require(_sha(raw) == record["outer_inputs_sha256"], "outer tensor evidence bytes changed")
    actual = torch.load(io.BytesIO(raw), map_location="cpu", weights_only=False)
    _require(
        actual.get("schema") == "v9_real_outer_inputs.v1"
        and _tree_digest(actual) == record["outer_inputs_digest"],
        "outer tensors changed",
    )
    before, evidence = actual["pre_state"], record["evidence"]
    _require(
        before["step"] == state["step"]
        and before["seed"] == state["seed"]
        and before["arm"] == state["arm"]
        and before["pool_id"] == state["pool_id"]
        and before["prior"] == state["prior"]
        and before["schedule"] == state["schedule"],
        "outer pre-state changed",
    )
    for key in (
        "parameters",
        "buffers",
        "optimizer",
        "rng",
        "frozen_base_digest",
        "adapter_binding",
    ):
        _require(
            _tree_digest(before[key]) == _tree_digest(state[key]),
            "outer update must not advance actual training state: " + key,
        )
    for field, evidence_key in (
        ("G", "population_gradient_digest"),
        ("gJ", "feedback_gradient_digest"),
        ("theta_bar", "actual_virtual_theta_digest"),
        ("pullback", "pullback_digest"),
    ):
        _require(
            parameter_digest(actual[field]) == evidence[evidence_key],
            "actual outer tensor binding mismatch",
        )
    seal = actual["feedback_seal"]
    _require(
        seal["seal_sha256"]
        == digest({k: v for k, v in seal.items() if k != "seal_sha256"})
        == evidence["feedback_seal_sha256"]
        and seal["denominator"] == evidence["actual_feedback_denominator"]
        and seal["identity"]["point_id"] == actual["point_id"]
        and seal["identity"]["parameter_digest"] == parameter_digest(actual["theta_bar"]),
        "actual complete feedback point/seal mismatch",
    )
    _require(not production or seal["denominator"] == 700, "production feedback remains 700")
    rewards, report = actual["rewards"], actual["feedback_report"]
    _require(
        len(rewards) == seal["denominator"] == report["denominator"]
        and all(type(r) in (int, float) and r in (0, 1) for r in rewards)
        and sum(r == 0 for r in rewards) == report["accounting"]["zero_reward_trajectories_skipped"]
        and report["all_receipts_validated"] is True
        and actual["C"] == evidence["C"]
        and actual["q_next"] == state["pi"],
        "fixed-denominator reward/C/q evidence mismatch",
    )
    expected = _registered_update(actual, state["arm"])
    _require(expected["pi_next"] == state["pi"], "saved real outer q differs from the fixed kernel")
    _require(state["outer_done"] == before["outer_done"] + [state["step"]], "outer history changed")
    return record, state, actual


def same_N_point(left, right, *, production=True):
    _, _, a = checked_outer(left, production=production)
    _, _, b = checked_outer(right, production=production)
    _require(
        {a["pre_state"]["arm"], b["pre_state"]["arm"]} == {"C-only", "Full"},
        "paired automatic arm evidence required",
    )
    fields = ("G", "gJ", "C", "theta_bar", "pullback", "mu", "feedback_seal", "rewards")
    matches = {key: _tree_digest(a[key]) == _tree_digest(b[key]) for key in fields}
    matches["theta_Adam_RNG_pi_prior_schedule"] = _tree_digest(
        _computation_state(a["pre_state"])
    ) == _tree_digest(_computation_state(b["pre_state"]))
    return dict(
        same_point=all(matches.values()),
        exact_evidence=matches,
        reward_count_alone_sufficient=False,
    )


def _validate_interval(root, start, stop, expected_pi, reference_state):
    """Inspect durable real update records; does not claim a CPU replay of Qwen."""
    final = None
    for step in range(start + 1, stop + 1):
        path = Path(root) / f"step{step:04d}_step"
        record, state = checkpoint(path)
        _require(
            state["step"] == step
            and state["pi"] == expected_pi
            and state["prior"] == reference_state["prior"]
            and state["schedule"] == reference_state["schedule"]
            and state["pool_id"] == reference_state["pool_id"]
            and state["seed"] == reference_state["seed"]
            and record["evidence"]["actual_parameter_update"] is True
            and record["evidence"]["task_batch"]["task_ids"]
            == state["schedule"]["batches"][step - 1]["task_ids"],
            "mechanism interval must preserve real task schedule, prior and fixed pi",
        )
        final = path
    _require(final is not None, "one full positive-length epoch required")
    return checkpoint_ref(final)


def execute_C_reverse(*, factory, shared, positive_outer, static_root, positive_root, output):
    """Use actual C-only first q+, not a Manual tilt or a newly estimated direction."""
    output = Path(output)
    _require(not output.exists(), "mechanism run exists; never implicitly repeat training")
    source_record, source = checkpoint(shared)
    trial = factory(output / "training", "Static")
    _, positive, actual = checked_outer(positive_outer, production=trial.pool.production_verified)
    s = trial.execution_plan["steps_per_epoch"]
    _require(
        source["arm"] == "shared"
        and source["step"] == positive["step"] == 2 * s
        and positive["arm"] == "C-only"
        and source["pool_id"] == positive["pool_id"] == trial.pool.cache_id
        and _tree_digest(_computation_state(source))
        == _tree_digest(_computation_state(actual["pre_state"]))
        and actual["pre_state"]["pi"] == source["prior"],
        "first C direction requires identical real shared theta/Adam/RNG/current=prior",
    )
    q_plus = positive["pi"]
    q_minus = first_direction_reverse(source["prior"], q_plus)
    _, static_start = checkpoint(Path(static_root) / f"step{2 * s:04d}_branch")
    _require(
        _tree_digest(_computation_state(static_start)) == _tree_digest(_computation_state(source))
        and Path(positive_outer).resolve().parent == Path(positive_root).resolve(),
        "Static and positive intervals must begin at the actual bound shared point",
    )
    static = _validate_interval(static_root, 2 * s, 3 * s, source["prior"], source)
    positive_ref = _validate_interval(positive_root, 2 * s, 3 * s, q_plus, source)
    trial.restore(shared, branch=True)
    trial.pi = copy.deepcopy(q_minus)
    trial.commit(
        "mechanism_branch",
        dict(
            mechanism="C_reverse",
            q_plus=q_plus,
            q_minus=q_minus,
            actual_shared_state=source_record["actual_state_digest"],
            main_Static=False,
            no_new_feedback=True,
        ),
    )
    trial.run_until(3 * s)
    reverse = _validate_interval(trial.root, 2 * s, 3 * s, q_minus, source)
    result = _bound(
        dict(
            schema="v9_actual_C_direction_short_training.v1",
            seed=trial.seed,
            pool_id=trial.pool.cache_id,
            start_step=2 * s,
            end_step=3 * s,
            actual_extra_training_steps=s,
            source_shared=checkpoint_ref(shared),
            source_outer=checkpoint_ref(positive_outer),
            directions={"Static": static, "positive": positive_ref, "reverse": reverse},
            q_plus=q_plus,
            q_minus=q_minus,
            prior=source["prior"],
            positive_change=distribution_change(source["prior"], q_plus, actual["mu"]),
            reverse_change=distribution_change(source["prior"], q_minus, actual["mu"]),
            internal_reverse_consumer_arm="Static",
            reverse_is_not_main_Static_or_Manual_minus=True,
            new_feedback_sessions=0,
            API_calls=0,
            mechanism_evaluation_complete=False,
            actual_production_training=trial.pool.production_verified,
            actual_GPU_training=trial.pool.production_verified
            and str(trial.device).startswith("cuda"),
        )
    )
    _publish(output / "result", result)
    return result


def execute_N_control(*, factory, C_outer, Full_outer, C_root, Full_root, output):
    """Try exact same-point reuse, else fixed C-only 4s with the same saved feedback/C."""
    output = Path(output)
    _require(not output.exists(), "mechanism run exists; never implicitly repeat training")
    trial = factory(output / "training", "C-only")
    _, c_state, actual = checked_outer(C_outer, production=trial.pool.production_verified)
    s, before = trial.execution_plan["steps_per_epoch"], actual["pre_state"]
    _require(
        c_state["arm"] == "C-only"
        and c_state["step"] == 4 * s
        and c_state["pool_id"] == trial.pool.cache_id
        and trial.seed == c_state["seed"],
        "fixed C-only 4s anchor required",
    )
    _, paired_full, _ = checked_outer(Full_outer, production=trial.pool.production_verified)
    _require(
        paired_full["arm"] == "Full"
        and paired_full["step"] == 4 * s
        and paired_full["seed"] == trial.seed
        and paired_full["pool_id"] == trial.pool.cache_id,
        "registered paired Full 4s point required, not another seed/step",
    )
    compare = same_N_point(C_outer, Full_outer, production=trial.pool.production_verified)
    _require(
        Path(C_outer).resolve().parent == Path(C_root).resolve()
        and Path(Full_outer).resolve().parent == Path(Full_root).resolve(),
        "N interval roots differ from the actual compared outer points",
    )
    c_q, full_q = (_registered_update(actual, arm)["pi_next"] for arm in ("C-only", "Full"))
    difference = distribution_change(c_q, full_q, actual["mu"])
    arithmetic = dict(
        schema="v9_same_registered_point_N_arithmetic.v1",
        C_only=c_q,
        Full=full_q,
        difference=difference,
        N_distribution_effect_nonzero=difference["mu_weighted"]["TV"] > 1e-12,
        same_original_singleton_RMS_controls=True,
        prior_changed=False,
        genuine_theta_Adam_RNG_G_feedback_identity_verified=True,
        actual_outer_inputs_digest=_tree_digest(actual),
    )
    _require(arithmetic["C_only"] == c_state["pi"], "fixed C-only update differs")
    c_ref = _validate_interval(C_root, 4 * s, 5 * s, c_state["pi"], before)
    if compare["same_point"]:
        _, full_state, _ = checked_outer(Full_outer, production=trial.pool.production_verified)
        _require(full_state["pi"] == arithmetic["Full"], "matched Full update differs")
        full_ref = _validate_interval(Full_root, 4 * s, 5 * s, full_state["pi"], before)
        extra = 0
    else:
        trial.restore(C_outer)
        trial.pi = copy.deepcopy(arithmetic["Full"])
        trial.commit(
            "mechanism_branch",
            dict(
                mechanism="N_only_from_fixed_C4s",
                no_new_feedback=True,
                source_outer=checkpoint_ref(C_outer),
                original_current=before["pi"],
                unchanged_prior=before["prior"],
                full_q=arithmetic["Full"],
                main_C_only=False,
            ),
        )
        trial.run_until(5 * s)
        full_ref = _validate_interval(trial.root, 4 * s, 5 * s, arithmetic["Full"], before)
        extra = s
    result = _bound(
        dict(
            schema="v9_actual_same_point_N_short_training.v1",
            seed=trial.seed,
            pool_id=trial.pool.cache_id,
            start_step=4 * s,
            end_step=5 * s,
            anchor_arm="C-only",
            same_point_check=compare,
            source_outer=checkpoint_ref(C_outer),
            actual_extra_training_steps=extra,
            conditions={"C-only": c_ref, "Full": full_ref},
            arithmetic=arithmetic,
            N_activated=arithmetic["N_distribution_effect_nonzero"],
            actual_G_gJ_C_reused=True,
            prior_changed=False,
            new_feedback_sessions=0,
            API_calls=0,
            internal_fallback_consumer_arm="C-only" if extra else None,
            fallback_is_not_main_C_only=True,
            mechanism_evaluation_complete=False,
            actual_production_training=trial.pool.production_verified,
            actual_GPU_training=trial.pool.production_verified
            and str(trial.device).startswith("cuda"),
        )
    )
    _publish(output / "result", result)
    return result


def register(launcher, output):
    """Pre-Student implementation registration: original calibration120 and 5400 sessions."""
    from .planning import task_key
    from .storage import load_public_snapshot, runtime_binding
    from .v9_training_launcher import checked_launch

    launcher, output = Path(launcher).resolve(), Path(output).resolve()
    plan, pool, assets = checked_launch(launcher)
    _require(
        not list(launcher.glob("seed*/**/state.pt")),
        "mechanism implementation choices must freeze before actual Student results",
    )
    _require(not output.exists(), "mechanism registration is immutable")
    _, public, _ = load_public_snapshot(assets["snapshot"])
    tasks = [t for t in public if assets["role_plan"]["assignments"][task_key(t)] == "calibration"]
    _require(len(tasks) == 120, "original exposed calibration120 must remain unchanged")
    body = _bound(
        dict(
            schema="v9_registered_actual_mechanisms.v1",
            launcher=str(launcher),
            launcher_id=plan["id"],
            runtime_binding=runtime_binding(),
            pool_id=pool.cache_id,
            execution_plan=pool.execution_plan,
            seeds=[11, 29, 47],
            C_positive_reference="C-only",
            N_fallback_anchor="C-only at 4s",
            calibration_task_keys=[task_key(t) for t in tasks],
            calibration_task_ids=[t.task_id for t in tasks],
            stochastic_seeds=[11, 29],
            greedy_seed=20260928,
            seed_values_are_this_prospective_implementation_choice=True,
            stochastic_repeats=2,
            greedy_repeats=1,
            evaluation_configs=[cfg.model_dump(mode="json") for cfg in evaluation_configs()],
            C_sessions=3240,
            N_sessions=2160,
            total_sessions=5400,
            C_extra_steps_all_seeds=3 * pool.execution_plan["steps_per_epoch"],
            N_max_extra_steps_all_seeds=3 * pool.execution_plan["steps_per_epoch"],
            extra_feedback_sessions=0,
            checkpoint_selection_allowed=False,
            Student_scores_used=False,
            original_diagnostic_source=(
                "v6_training_plan.mechanism; original a8 audit sections 7.2/7.3"
            ),
            no_new_API=True,
            no_new_Probe_generation_or_review=True,
        )
    )
    _publish(output / "registration", body)
    return body


def _run_seed(output, seed, gpu_index):
    """Explicit GPU execution using existing loader/device checks; no waiting holder."""
    from .storage import runtime_binding
    from .v9_training_launcher import (
        _load_components,
        checked_launch,
        eligible_gpu,
        gpu_inventory,
        read_bound,
    )

    output = Path(output).resolve()
    registration = read_bound(output / "registration/record.json")
    _require(
        registration["runtime_binding"] == runtime_binding() and seed in registration["seeds"],
        "frozen mechanism source/seed changed",
    )
    launcher = Path(registration["launcher"])
    plan, pool, assets = checked_launch(launcher)
    _require(
        plan["id"] == registration["launcher_id"] and pool.cache_id == registration["pool_id"],
        "frozen launcher/material changed",
    )
    root, target = launcher / f"seed{seed}", output / f"seed{seed}"
    s = pool.execution_plan["steps_per_epoch"]
    static, c_only, full = (root / f"arms/{arm}/training" for arm in ("static", "c_only", "full"))
    _require(
        not target.exists(), "existing mechanism seed requires explicit recovery, no reload/retry"
    )
    required = [
        root / f"shared/step{2 * s:04d}_step",
        static / f"step{3 * s:04d}_step",
        c_only / f"step{3 * s:04d}_step",
        c_only / f"step{5 * s:04d}_step",
        full / f"step{5 * s:04d}_step",
    ]
    _require(
        all((path / "state.pt").is_file() for path in required),
        "actual registered main intermediate checkpoints required before GPU allocation",
    )
    for path in (
        c_only / f"step{2 * s:04d}_outer",
        c_only / f"step{4 * s:04d}_outer",
        full / f"step{4 * s:04d}_outer",
    ):
        checked_outer(path)
    row = eligible_gpu(plan, gpu_index, gpu_inventory())
    _require(
        not torch.cuda.is_initialized(), "fresh mechanism process required for explicit GPU mapping"
    )
    os.environ["CUDA_VISIBLE_DEVICES"] = row["uuid"]
    os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")
    model, tokenizer, optimizer, scope, _ = _load_components(assets, seed)

    def factory(root, arm):
        return ConditionalTrainingDriver(
            model,
            optimizer,
            pool,
            root=root,
            seed=seed,
            arm=arm,
            device="cuda:0",
            tokenizer=tokenizer,
            adapter_scope=scope,
        )

    C = execute_C_reverse(
        factory=factory,
        shared=root / f"shared/step{2 * s:04d}_step",
        positive_outer=c_only / f"step{2 * s:04d}_outer",
        static_root=static,
        positive_root=c_only,
        output=target / "C_direction",
    )
    N = execute_N_control(
        factory=factory,
        C_outer=c_only / f"step{4 * s:04d}_outer",
        Full_outer=full / f"step{4 * s:04d}_outer",
        C_root=c_only,
        Full_root=full,
        output=target / "N_same_point",
    )
    result = _bound(
        dict(
            schema="v9_mechanism_seed_training_result.v1",
            seed=seed,
            registration_id=registration["id"],
            C=C,
            N=N,
            actual_extra_training_steps=C["actual_extra_training_steps"]
            + N["actual_extra_training_steps"],
            new_feedback_sessions=0,
            evaluation_sessions_planned=1800,
            mechanism_evaluation_complete=False,
        )
    )
    _publish(target / "result", result)
    return result


def run_seed(output, seed, gpu_index):
    lock_root = Path(output) / "locks"
    lock_root.mkdir(exist_ok=True)
    with (lock_root / f"training-seed{seed}.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return _run_seed(output, seed, gpu_index)


def _point(output, seed, mechanism, condition):
    from .storage import runtime_binding
    from .v9_training_launcher import read_bound, sha

    output = Path(output).resolve()
    registration = read_bound(output / "registration/record.json")
    _require(
        registration["runtime_binding"] == runtime_binding() and seed in registration["seeds"],
        "frozen mechanism source/seed changed",
    )
    _require(mechanism in ("C_direction", "N_same_point"), "unknown mechanism")
    result = read_bound(output / f"seed{seed}" / mechanism / "result/record.json")
    refs = result["directions"] if mechanism == "C_direction" else result["conditions"]
    _require(
        condition in refs
        and result["seed"] == seed
        and result["pool_id"] == registration["pool_id"],
        "foreign mechanism result",
    )
    reference = refs[condition]
    _require(checkpoint_ref(reference["path"]) == reference, "mechanism checkpoint changed")
    _, state = checkpoint(reference["path"])
    expected = registration["execution_plan"]["mechanism_steps"][
        "C_direction" if mechanism == "C_direction" else "N_local"
    ]
    _require(
        state["step"] == expected and state["pool_id"] == registration["pool_id"],
        "wrong intermediate checkpoint",
    )
    # Registration and actual short-training already verified the full material.
    # Evaluation only rebinds immutable parent identities, not all13022 reviews.
    plan = read_bound(Path(registration["launcher"]) / "registration/record.json")
    _require(
        plan["id"] == registration["launcher_id"]
        and plan["material_identity"]["pool_id"] == registration["pool_id"]
        and plan["runtime_binding"] == registration["runtime_binding"],
        "parent launcher/material changed",
    )
    _require(
        sha(plan["assets_protocol"]["path"]) == plan["assets_protocol"]["sha256"],
        "registered source/role assets changed",
    )
    assets = read_bound(plan["assets_protocol"]["path"])
    root = output / f"seed{seed}" / "evaluation" / mechanism / condition
    return registration, plan, None, assets, result, reference, state, root


def _evaluate_point(output, seed, mechanism, condition, gpu_index):
    """Exactly original calibration120 × (two sampled + one greedy); no private reads."""
    from .providers import LocalTorchProvider, local_model_identity
    from .storage import execute_run, prepare_run
    from .v9_final_evaluation import install_checkpoint_state
    from .v9_training_launcher import _load_components, eligible_gpu, gpu_inventory

    reg, plan, _, assets, result, ref, state, root = _point(output, seed, mechanism, condition)
    _require(not root.exists(), "existing mechanism evaluation must not be implicitly resampled")
    row = eligible_gpu(plan, gpu_index, gpu_inventory())
    _require(not torch.cuda.is_initialized(), "fresh mechanism evaluation process required")
    os.environ["CUDA_VISIBLE_DEVICES"] = row["uuid"]
    os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")
    model, tokenizer, _, scope, _ = _load_components(assets, seed)
    parameters = install_checkpoint_state(model, state, scope)
    identity = local_model_identity(
        model,
        tokenizer,
        model_id=assets["assets"]["base_binding"]["id"],
        point_id="v9-mechanism:" + digest(dict(registration=reg["id"], reference=ref)),
        parameter_tensors=parameters,
    )
    provider = LocalTorchProvider(model, tokenizer, identity, parameter_tensors=parameters)
    _publish(
        root / "intent",
        _bound(
            dict(
                registration_id=reg["id"],
                mechanism_result_id=result["id"],
                checkpoint=ref,
                identity=identity.model_dump(mode="json"),
                seed=seed,
                mechanism=mechanism,
                condition=condition,
                denominator=360,
                private_references_read=False,
            )
        ),
    )
    for index, config in enumerate(evaluation_configs()):
        path = root / f"draw{index}"
        prepare_run(
            assets["snapshot"],
            assets["role_plan"],
            path,
            role="calibration",
            config=config,
            identity=identity,
            task_keys=reg["calibration_task_keys"],
        )
        asyncio.run(execute_run(path, provider))
    return seal_point(output, seed, mechanism, condition)


def evaluate_point(output, seed, mechanism, condition, gpu_index):
    lock_root = Path(output) / "locks"
    lock_root.mkdir(exist_ok=True)
    name = digest(dict(seed=seed, mechanism=mechanism, condition=condition))
    with (lock_root / f"evaluation-{name}.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return _evaluate_point(output, seed, mechanism, condition, gpu_index)


def seal_point(output, seed, mechanism, condition):
    from .storage import sealed_episodes
    from .v9_training_launcher import read_bound

    reg, _, _, _, result, reference, _, root = _point(output, seed, mechanism, condition)
    intent = read_bound(root / "intent/record.json")
    _require(
        intent["checkpoint"] == reference and intent["mechanism_result_id"] == result["id"],
        "mechanism generation intent changed",
    )
    episodes, seals = [], []
    for index, config in enumerate(evaluation_configs()):
        run, seal, part = sealed_episodes(root / f"draw{index}")
        _require(
            run["tasks"] == reg["calibration_task_keys"]
            and run["config"] == config.model_dump(mode="json")
            and run["provider"] == intent["identity"]
            and [e.task_id for e in part] == reg["calibration_task_ids"]
            and all(e.all_provider_calls_settled for e in part),
            "all three complete original calibration draws must be sealed",
        )
        episodes.extend(part)
        seals.append(seal["id"])
    _require(len(episodes) == 360, "complete360 before private references")
    value = _bound(
        dict(
            schema="v9_mechanism_whole_point_seal.v1",
            registration_id=reg["id"],
            mechanism_result_id=result["id"],
            checkpoint=reference,
            denominator=360,
            seed=seed,
            mechanism=mechanism,
            condition=condition,
            draw_seal_ids=seals,
            episode_sha256=[digest(e) for e in episodes],
            private_references_read=False,
        )
    )
    _publish(root / "whole_seal", value)
    return value


def score_point(output, seed, mechanism, condition):
    from .contracts import PrivateReference, TaskBundle
    from .storage import _read_snapshot_rows, load_public_snapshot, sealed_episodes
    from .v6_task import score_public_reasoning_program

    seal = seal_point(output, seed, mechanism, condition)  # All360 before reference access.
    reg, _, _, assets, _, _, _, root = _point(output, seed, mechanism, condition)
    manifest, public, lineages = load_public_snapshot(assets["snapshot"])
    references = _read_snapshot_rows(
        assets["snapshot"], "private.references.jsonl", PrivateReference, manifest
    )
    bundles = {
        t.task_id: TaskBundle(public=t, reference=r, lineage=lineage)
        for t, r, lineage in zip(public, references, lineages, strict=True)
    }
    rows = []
    for index in range(3):
        _, _, episodes = sealed_episodes(root / f"draw{index}")
        for episode in episodes:
            score = score_public_reasoning_program(bundles[episode.task_id], episode)
            rows.append(
                dict(
                    coordinate=f"draw{index}/{episode.task_id}",
                    task_id=episode.task_id,
                    draw=index,
                    episode_sha256=digest(episode),
                    native=score,
                )
            )
    values = [row["native"]["native"]["execution_accuracy"] for row in rows]
    _require(
        all(v is None or type(v) in (int, float) and v in (0, 1) for v in values),
        "unknown native metrics cannot become numeric failure",
    )
    unknown = sum(v is None for v in values)
    result = _bound(
        dict(
            schema="v9_mechanism_point_native_scores.v1",
            registration_id=reg["id"],
            seal_id=seal["id"],
            checkpoint=seal["checkpoint"],
            denominator=360,
            seed=seed,
            mechanism=mechanism,
            condition=condition,
            rows=rows,
            unknown=unknown,
            mean=None if unknown else sum(values) / 360,
            unknown_as_zero=False,
            native_correctness_is_not_process_reliability=True,
        )
    )
    _publish(root / "scores", result)
    return result


def aggregate(output):
    from .v6_mechanism_diagnostics import direction_utility_report
    from .v9_training_launcher import read_bound

    output = Path(output)
    registration = read_bound(output / "registration/record.json")
    seeds = {}
    for seed in registration["seeds"]:
        values = {}
        for mechanism, conditions in (
            ("C_direction", ("Static", "positive", "reverse")),
            ("N_same_point", ("C-only", "Full")),
        ):
            values[mechanism] = {}
            for condition in conditions:
                path = (
                    output / f"seed{seed}/evaluation" / mechanism / condition / "scores/record.json"
                )
                report = read_bound(path)
                _require(
                    report["registration_id"] == registration["id"]
                    and report["seed"] == seed
                    and report["mechanism"] == mechanism
                    and report["condition"] == condition
                    and report["denominator"] == 360
                    and len(report["rows"]) == 360
                    and report["unknown"] == 0,
                    "all5400 known original mechanism outcomes required",
                )
                _, _, _, _, _, reference, _, _ = _point(output, seed, mechanism, condition)
                _require(report["checkpoint"] == reference, "mechanism scored another checkpoint")
                values[mechanism][condition] = {
                    row["coordinate"]: row["native"]["native"]["execution_accuracy"]
                    for row in report["rows"]
                }
        coordinates = [
            f"draw{i}/{t}" for i in range(3) for t in registration["calibration_task_ids"]
        ]
        C = direction_utility_report(values["C_direction"], registered_keys=coordinates)
        _require(
            all(set(v) == set(coordinates) for v in values["N_same_point"].values()),
            "complete paired N calibration coordinates required",
        )
        N_means = {arm: sum(v.values()) / 360 for arm, v in values["N_same_point"].items()}
        seeds[str(seed)] = dict(
            C=C, N_means=N_means, N_Full_minus_C_only=N_means["Full"] - N_means["C-only"]
        )
    value = _bound(
        dict(
            schema="v9_complete_mechanism_evaluation.v1",
            registration_id=registration["id"],
            denominator=5400,
            seeds=seeds,
            original_calibration_tasks=120,
            exposed_diagnostic_not_blind_test=True,
            intermediate_checkpoint_selection=False,
            API_calls=0,
            extra_feedback_sessions=0,
            statistical_significance_claimed=False,
        )
    )
    _publish(output / "evaluation_result", value)
    return value


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "action", choices=("register", "run-seed", "evaluate-point", "score-point", "aggregate")
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--launcher", type=Path)
    parser.add_argument("--seed", type=int, choices=(11, 29, 47))
    parser.add_argument("--gpu-index", type=int)
    parser.add_argument("--mechanism", choices=("C_direction", "N_same_point"))
    parser.add_argument("--condition")
    args = parser.parse_args(argv)
    if args.action == "register":
        value = register(args.launcher, args.output)
    elif args.action == "run-seed":
        value = run_seed(args.output, args.seed, args.gpu_index)
    elif args.action == "evaluate-point":
        value = evaluate_point(
            args.output, args.seed, args.mechanism, args.condition, args.gpu_index
        )
    elif args.action == "score-point":
        value = score_point(args.output, args.seed, args.mechanism, args.condition)
    else:
        value = aggregate(args.output)
    print(json.dumps(value, ensure_ascii=False))


if __name__ == "__main__":
    main()
