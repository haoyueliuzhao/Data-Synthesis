"""Admitted cold fixed-pi training only; no feedback, class, VJP or outer path."""
from __future__ import annotations

import gc
from pathlib import Path

import finqa_v71_binding as binding
import finqa_v71_training as training_api

binding.install_scientific_paths()
original = binding.old_module("finqa_v54_worker")
ROOT, SEED = binding.ROOT, 137
require, checked = binding.require, binding.checked


class ScientificMonitor(original.ScientificMonitor):
    def clear_unused(self, label):
        before = self.snapshot(label + ".before_cleanup", boundary=False)
        gc.collect()
        after = self.snapshot(label + ".after_cleanup", boundary=True)
        return dict(before=before, after=after, routine_allocator_cache_retained=True)


def stage_root(root, step, stage):
    require(stage == "train" and step in training_api.WINDOWS,
            "V71 registers only fixed-distribution training")
    return training_api.point_root(root, step) / stage


def job_spec(step, stage="train"):
    stage_root(ROOT, step, stage)
    return dict(id=f"step{step}.train", job_id=f"step{step}.train", seed=SEED,
        step=step, stage="train", kind="train", memory_phase="train",
        arm=training_api.ARM, condition=training_api.CONDITION,
        fixed_distribution=True, outer_updates=0)


def execute(root, job, attempt_root, guard):
    expected = job_spec(job["step"], job["stage"])
    require(all(job.get(key) == value for key, value in expected.items()
                if key not in ("id", "job_id")), "job differs from the sole fixed894 branch")
    step = job["step"]
    directory = stage_root(root, step, "train")
    training, rt = training_api.runtime()
    context, state = training_api.load_window(root, step, rt)
    _science, pool, _prefix, assets = training.checked_launch(Path(context["training_root"]))
    require(context["protocol_id"] == guard.protocol["id"], "resource/scientific protocol differs")
    monitor = ScientificMonitor(guard, cooperative_replay=False)
    monitor.check_stop("before_actual_model_load")
    model, tokenizer, optimizer, scope, _fresh = rt.launcher._load_components(assets, SEED)
    driver = training.adapters().TrainingDriver(model, optimizer, pool,
        root=Path(root) / "training", seed=SEED, arm="C-only", device="cuda:0",
        tokenizer=tokenizer, adapter_scope=scope, feedback_collector=None)
    # All construction/import/RNG-consuming initialization precedes restoration.
    training_api.configure_fixed_window(driver, step)
    driver.restore(context["parent_checkpoint"]["path"])
    require(rt.v8._tree_digest(driver._payload()) == context["parent_state_digest"],
            "complete actual parent theta/Adam/RNG/pi restore failed")
    monitor.clear_unused("after_exact_fixed_parent_model_Adam_RNG_pi_restore")
    completed = directory / "completed/record.json"
    if completed.exists():
        result = training_api.restore_completed_window(context, checked(completed), driver, rt)
    else:
        result = training_api.execute_training(root, context, state, driver,
            rt=rt, monitor=monitor, resource_report=guard.report)
    body = dict(branch_result=binding.entry(completed), initial_step=step,
        final_step=result["final_step"], optimizer_updates=298, new_optimizer_updates=298,
        outer_updates=0, applied=False, fixed_distribution=True,
        fixed_distribution_digest=context["fixed_pi_digest"],
        final_checkpoint=result["final_checkpoint"],
        new_feedback_sessions=0, new_class_passes=0, new_response_replay=0, new_VJP=0)
    monitor.clear_unused("fixed_training_window_complete")
    del driver, model, tokenizer, optimizer, pool, state
    gc.collect()
    rt.torch.cuda.empty_cache()
    monitor.snapshot("after_model_release", boundary=True)
    return dict(body, point_context_id=context["id"],
        parent_state_digest=context["parent_state_digest"], seed=SEED, step=step, stage="train",
        arm=training_api.ARM, condition=training_api.CONDITION, model_released=True)
