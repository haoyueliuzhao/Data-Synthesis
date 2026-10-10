"""Commit one actual production outer, then run only the original SFT steps.

This adapter cannot collect feedback or call the old monolithic outer method.
Cold stages supply actual tensors; the frozen driver's commit/step methods keep
the original full model, Adam, RNG, distribution, schedule and package semantics.
"""

from __future__ import annotations

import copy
from pathlib import Path


def require(condition, message):
    if not condition:
        raise ValueError(message)


def next_training_boundary(driver):
    """Arrival at the next outer is a pre-outer commit, never an implicit update."""
    require(driver.arm in ("Static", "C-only", "Full"), "unregistered production arm")
    require(driver.step_index < driver.final_step, "completed endpoint cannot be retrained")
    candidates = [driver.final_step]
    if driver.arm != "Static":
        candidates.extend(step for step in driver.outer_steps if step > driver.step_index)
    return min(candidates)


def validate_outer_payload(context, driver, rt, outer_inputs, evidence):
    """Validate the actual staged values against the live restored real state."""
    pre_state = outer_inputs["pre_state"]
    require(
        context["due_outer"] is True
        and driver.arm in ("C-only", "Full")
        and driver.step_index in driver.outer_steps
        and driver.step_index not in driver.outer_done,
        "a single uncommitted scheduled production outer is required",
    )
    require(
        (driver.seed, driver.arm, driver.step_index)
        == (context["seed"], context["arm"], context["step"])
        == (pre_state["seed"], pre_state["arm"], pre_state["step"]),
        "staged outer coordinate differs from real trainer",
    )
    require(
        rt.v8._tree_digest(pre_state)
        == rt.v8._tree_digest(driver._payload())
        == context["pre_state_digest"],
        "model/Adam/RNG/pi/prior/buffer/schedule differs before outer commit",
    )
    require(
        context["branch"]["contribution_only"] is (driver.arm == "C-only")
        and context["branch"]["b_N"] == (0 if driver.arm == "C-only" else 0.2)
        and context["branch"]["parameters"] == rt.v8.PARAMETERS,
        "registered C-only/Full coefficients changed",
    )
    require(
        outer_inputs["schema"] == "v9_real_outer_inputs.v1"
        and outer_inputs["actual_tensors_saved"] is True
        and outer_inputs["mu"] == driver.pool._manifest.registration.mu
        and outer_inputs["q_next"] == evidence["distribution"]["pi_next"]
        and outer_inputs["C"] == evidence["C"],
        "staged outer mathematical payload is incomplete or inconsistent",
    )
    for key, evidence_key in (
        ("G", "population_gradient_digest"),
        ("theta_bar", "actual_virtual_theta_digest"),
        ("gJ", "feedback_gradient_digest"),
        ("pullback", "pullback_digest"),
    ):
        require(
            rt.v8.parameter_digest(outer_inputs[key]) == evidence[evidence_key],
            "staged tensor/evidence mismatch: " + key,
        )
    require(
        evidence["actual_feedback_denominator"] == 700
        and outer_inputs["feedback_seal"]["denominator"] == 700
        and len(outer_inputs["rewards"]) == 700
        and all(type(r) in (int, float) and r in (0, 1) for r in outer_inputs["rewards"])
        and evidence["feedback_seal_sha256"] == outer_inputs["feedback_seal"]["seal_sha256"],
        "complete original 700-cohort and frozen rewards required",
    )
    if context["feedback"]["mode"] == "sealed_existing":
        require(
            outer_inputs["point_id"] == context["feedback"]["expected_point_id"],
            "original pending sampling point changed",
        )
    destination = driver.root / f"step{driver.step_index:04d}_outer"
    require(not destination.exists(), "outer destination exists; duplicate commit forbidden")
    return destination


def commit_actual_outer(context, driver, rt, outer_inputs, evidence):
    destination = validate_outer_payload(context, driver, rt, outer_inputs, evidence)
    before = driver._payload()
    driver.tainted = True
    driver.pi = copy.deepcopy(outer_inputs["q_next"])
    driver.outer_done.append(driver.step_index)
    after = driver._payload()
    stable_fields = set(before) - {"pi", "outer_done"}
    require(
        all(rt.v8._tree_digest(before[k]) == rt.v8._tree_digest(after[k]) for k in stable_fields),
        "outer must not change actual Student/Adam/RNG/prior or other training state",
    )
    checkpoint = driver.commit("outer", evidence, outer_inputs=outer_inputs)
    require(Path(checkpoint) == destination, "frozen commit returned another checkpoint")
    driver.tainted = False
    return checkpoint


def publish_endpoint(context, driver, rt, training):
    """Produce the original V25 endpoint contract for its unchanged evaluator."""
    expected = list(driver.outer_steps) if driver.arm != "Static" else []
    require(driver.step_index == 1490 and driver.outer_done == expected, "endpoint dose incomplete")
    training_root = Path(context["arm_root"]).parents[2]
    plan = training.checked_plan(training_root)
    shared = training._shared_checkpoint(training_root, plan, driver.seed)
    actual = dict(
        arm=driver.arm,
        seed=driver.seed,
        committed_step=driver.step_index,
        outer_done=list(driver.outer_done),
        production=driver.pool.production_verified,
    )
    gradient_arm = driver.arm != "Static"
    result = rt.launcher.bound(
        dict(
            schema="v25_new_arm_result.v1",
            protocol_id=plan["id"],
            seed=driver.seed,
            arm=driver.arm,
            pool_id=driver.pool.cache_id,
            shared_checkpoint=rt.launcher._checkpoint_ref(shared),
            final_checkpoint=rt.launcher._checkpoint_ref(driver.root / "step1490_step"),
            result=actual,
            actual_student_training=True,
            actual_tail_updates=1192,
            actual_feedback_denominator=700 if gradient_arm else 0,
            actual_outer_updates=4 if gradient_arm else 0,
            new_feedback_episodes=2800 if gradient_arm else 0,
            old_checkpoint_or_feedback_reused=False,
            cross_arm_feedback_shared=False,
            cross_arm_outer_shared=False,
            dev_evaluated=False,
            test_opened=False,
            execution_backend="v37_staged_production_continuation",
            resumed_same_B_state_and_feedback=True,
            old_checkpoint_means_old_scientific_seeds_not_same_B_resume=True,
            feedback_count_is_total_for_this_B_arm_not_new_calls_in_V37=True,
        )
    )
    path = Path(context["arm_root"]) / "result"
    require(not path.exists(), "completed arm result already exists")
    rt.v8._publish(path, result)
    return str(path / "record.json")


def execute_training(
    context,
    directory,
    driver,
    rt,
    monitor,
    stop_requested,
    *,
    training=None,
    outer_inputs=None,
    evidence=None,
):
    """Production worker owns loading, admission, lifetime resources and exit."""
    require(Path(driver.root) == Path(context["arm_root"]) / "training", "foreign trainer root")
    require(
        rt.v8._tree_digest(driver._payload()) == context["pre_state_digest"],
        "restored full state differs from registered continuation",
    )
    initial_step, committed_outer = driver.step_index, None
    scientific_boundary = next_training_boundary(driver)
    boundary = context.get("training_stop_step", min(scientific_boundary, initial_step + 298))
    require(
        type(boundary) is int and initial_step < boundary <= scientific_boundary,
        "training segment must stop before the next original outer or endpoint",
    )
    if context["due_outer"]:
        require(
            outer_inputs is not None and evidence is not None, "actual distribution payload needed"
        )
        monitor.check_stop("before_actual_outer_commit")
        require(not stop_requested(), "safe stop requested before outer commit")
        committed_outer = commit_actual_outer(context, driver, rt, outer_inputs, evidence)
        monitor.clear_unused("after_actual_outer_commit")
    else:
        require(outer_inputs is None and evidence is None, "unexpected outer for plain SFT stage")
    first_step = None
    while driver.step_index < boundary:
        monitor.check_stop("before_real_optimizer_step", step=driver.step_index + 1)
        require(not stop_requested(), "safe stop requested at full committed SFT boundary")
        driver.step()  # Original full-package loss, clip, AdamW and immutable commit.
        if first_step is None:
            first_step = str(driver.root / f"step{driver.step_index:04d}_step")
        monitor.clear_unused("after_real_optimizer_step")
    endpoint = None
    if driver.step_index == driver.final_step:
        require(training is not None, "frozen training module needed for endpoint contract")
        endpoint = publish_endpoint(context, driver, rt, training)
    return dict(
        context_id=context["id"],
        seed=driver.seed,
        arm=driver.arm,
        initial_step=initial_step,
        committed_step=driver.step_index,
        actual_optimizer_steps=driver.step_index - initial_step,
        outer_committed=committed_outer is not None,
        outer_checkpoint=str(committed_outer) if committed_outer else None,
        outer_done=list(driver.outer_done),
        first_sft_after_outer=first_step if committed_outer else None,
        next_checkpoint=str(driver.root / f"step{driver.step_index:04d}_step"),
        next_due_outer=driver.step_index
        if driver.arm != "Static" and driver.step_index in driver.outer_steps
        else None,
        endpoint_complete=endpoint is not None,
        endpoint_result=endpoint,
        feedback_calls=0,
        scoring_calls=0,
        original_step_method_used=True,
        old_monolithic_outer_called=False,
    )
