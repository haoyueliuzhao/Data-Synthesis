"""Device-leased V47 routing to early reservation and unchanged scientific functions."""

from __future__ import annotations

import argparse
import importlib
import importlib.util
import json
import sys
from contextlib import contextmanager
from pathlib import Path

import finqa_v47_admission as admission
import finqa_v47_inheritance as inheritance
import finqa_v47_reservation as reservation


def _load():
    name = __name__ + "_sealed_v43_worker"
    spec = importlib.util.spec_from_file_location(
        name, Path(__file__).with_name("finqa_v43_worker.py")
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


original = _load()
_cold_spec = importlib.util.spec_from_file_location(
    __name__ + "_reserved_cold_worker", Path(__file__).with_name("finqa_v47_cold_worker.py")
)
cold = importlib.util.module_from_spec(_cold_spec)
sys.modules[_cold_spec.name] = cold
_cold_spec.loader.exec_module(cold)
original.original = cold
STAGES = original.STAGES
DeadlineStop, ResourceEvents = original.DeadlineStop, original.ResourceEvents


def _controller():
    return importlib.import_module("finqa_v47_controller")


def _checked_entry(root, control):
    root = Path(root).resolve()
    for module in (
        sys.modules[__name__],
        control,
        inheritance,
        admission,
        admission.host_policy,
        admission.host_policy.original,
        admission.legacy_policy,
        reservation,
        original,
        original.original,
        original.task_overlay,
        original.replay_resume,
        original.feedback_resume,
        original.policy,
        original.time_policy,
    ):
        path = Path(module.__file__).resolve()
        control.require(
            path == root / "implementation" / path.name,
            "V47 entry and every consumed shell must come from its actual new seal",
        )


@contextmanager
def bound_execution(control):
    old = {
        key: getattr(original, key)
        for key in ("_controller", "inheritance", "admission", "policy", "task_overlay")
    }

    def validate_class(directory, context, plan, stage, deadline_epoch, *, control):
        original.time_policy.validate(plan)
        original.time_policy.require_no_deadline(deadline_epoch)
        binding = inheritance.task_cache_overlay_binding(directory, plan)
        control.require(
            old["task_overlay"].allows_new_shard(binding, stage)
            and binding["original_context_id"] == context["id"],
            "remaining class tasks must retain exact same-point ownership",
        )
        return binding

    original._controller = lambda: control
    original.inheritance, original.admission, original.policy = inheritance, admission, admission
    original.task_overlay = original._Proxy(
        old["task_overlay"], validate_class_window=validate_class
    )
    try:
        yield
    finally:
        for key, value in old.items():
            setattr(original, key, value)


def run(root, context_directory, stage, gpu_index, deadline_epoch=None):
    control = _controller()
    _checked_entry(root, control)
    admission.validate_plan(control.checked_protocol(root))
    with bound_execution(control):
        return original.run(root, context_directory, stage, gpu_index, deadline_epoch)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--context", type=Path, required=True)
    parser.add_argument("--stage", choices=STAGES, required=True)
    parser.add_argument("--gpu-index", type=int, required=True)
    parser.add_argument("--deadline-epoch", type=float, default=None)
    args = parser.parse_args()
    result = run(args.root, args.context, args.stage, args.gpu_index, args.deadline_epoch)
    print(json.dumps(dict(status=result["status"], id=result["id"])))
