"""V43 deadline-free checkpoint recovery shell over unchanged V40/V37 mathematical functions.

Only admission, registered task/feedback continuation, path routing and audit
fields change. The already accepted V40 response recovery is never repeated.
All bindings below are process-local and restored on exit; frozen files remain
unchanged, and each actual phase still has its original one-attempt guard.
"""

from __future__ import annotations

import argparse
import importlib
import importlib.util
import json
import sys
from contextlib import contextmanager
from pathlib import Path

import finqa_v41_memory_policy as policy
import finqa_v42_feedback_resume as feedback_resume
import finqa_v43_admission as admission
import finqa_v43_inheritance as inheritance
import finqa_v43_replay as replay_resume
import finqa_v43_task_overlay as task_overlay
import finqa_v43_time_policy as time_policy


def _load_shell():
    name = __name__ + "_unchanged_v40_worker"
    spec = importlib.util.spec_from_file_location(
        name, Path(__file__).with_name("finqa_v43_cold_worker.py")
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


original = _load_shell()
STAGES = original.STAGES
GIB = 1024**3


class DeadlineStop:
    """Real stop signals remain effective; there is no phase wallclock limit."""

    def __init__(self, request, deadline_epoch):
        time_policy.require_no_deadline(deadline_epoch)
        self.request, self.deadline_epoch = request, None

    @property
    def requested(self):
        return self.request.requested

    @property
    def reason(self):
        return self.request.reason

    def signals(self):
        return self.request.signals()


class ResourceEvents(original.base.ResourceEvents):
    """Keep original host/GPU gates and reporting, with a literal null deadline."""

    def __call__(self, gpu):
        time_policy.require_no_deadline(self.stop.deadline_epoch)
        host = original.base.host_memory()
        host.update(rss_limit_bytes=self.limit, available_reserve_bytes=96 * GIB)
        host["rss_pass"] = host["peak_rss_bytes"] <= self.limit
        host["available_pass"] = host["available_bytes"] >= 96 * GIB
        host["passed"] = host["rss_pass"] and host["available_pass"]
        row = dict(
            gpu,
            host=host,
            deadline_epoch=None,
            deadline_pass=True,
            deadline_limit_enforced=False,
            wallclock_limits_removed=True,
        )
        row["passed"] = bool(gpu["passed"] and host["passed"])
        self.observations.append(row)
        self.sink(row)
        original.base.control.require(host["passed"], "production host RAM envelope failed")


class _Proxy:
    def __init__(self, module, **overrides):
        self._module, self._overrides = module, overrides

    def __getattr__(self, name):
        return self._overrides[name] if name in self._overrides else getattr(self._module, name)


def execution_context(context, _plan):
    """The original matrix now runs normally; do not repeat the old pilot stop."""
    return context


def _controller():
    return importlib.import_module("finqa_v43_controller")


def _checked_entry(root, control):
    root = Path(root).resolve()
    for path in (
        Path(__file__),
        Path(original.__file__),
        Path(control.__file__),
        Path(admission.__file__),
        Path(inheritance.__file__),
        Path(policy.__file__),
        Path(task_overlay.__file__),
        Path(feedback_resume.__file__),
        Path(replay_resume.__file__),
        Path(time_policy.__file__),
    ):
        control.require(
            path.resolve() == root / "implementation" / path.name,
            "V43 worker and its unchanged execution shell must come from the new seal",
        )


@contextmanager
def bound_execution(control, *, feedback_binding=None):
    """Bind routing in this isolated shell, retaining the original actual maths."""
    state = {"context": None}

    def context_view(context, plan):
        state["context"] = context
        return execution_context(context, plan)

    def wait(*args, **kwargs):
        control.require(state["context"] is not None, "actual context must precede CUDA admission")
        control.require("context" not in kwargs, "duplicate admission context override")
        return admission.wait_for_pre_cuda_admission(*args, context=state["context"], **kwargs)

    def publish(path, body):
        value = dict(body)
        if isinstance(value.get("schema"), str) and value["schema"].startswith("v40_"):
            value["schema"] = "v43_" + value["schema"][4:]
        if value.get("stage") in STAGES and state["context"] is not None:
            value.update(
                memory_phase=policy.phase_key(value["stage"], state["context"]),
                minimum_free_mib=policy.minimum_free_mib(value["stage"], state["context"]),
                gpu_admission_policy_schema=admission.POLICY_SCHEMA,
                original_mathematical_functions_unchanged=True,
                accepted_V40_pilot_repeated=False,
            )
        return control.publish(path, value)

    def replay_binding(directory, plan):
        return inheritance.replay_resume_binding(directory, plan)

    def overlay(parent_cache, context, directory, stage, binding, bundle, *, control):
        cache = task_overlay.build_overlay(
            parent_cache, context, directory, stage, binding, bundle, control=control
        )
        if (
            feedback_binding is not None
            and stage == "virtual_point"
            and context["id"] == feedback_binding["original_context_id"]
        ):
            # The actual virtual tensors were saved before feedback. Preserve
            # verification statistics honestly and avoid reading unused class tensors.
            return _Proxy(cache, assemble=lambda device="cpu": None)
        return cache

    previous_virtual = original.base.execute_virtual
    previous_feedback = original.base.load_feedback
    previous_deadline = original.base.DeadlineStop
    previous_events = original.base.ResourceEvents

    def virtual(*args, **kwargs):
        context = args[1]
        if (
            feedback_binding is not None
            and context["id"] == feedback_binding["original_context_id"]
        ):
            return feedback_resume.execute_virtual(
                *args,
                **kwargs,
                binding=feedback_binding,
                control=control,
                original_worker=original.base,
            )
        return previous_virtual(*args, **kwargs)

    def load_feedback(point, context, bundle):
        if (
            feedback_binding is not None
            and context["id"] == feedback_binding["original_context_id"]
        ):
            return feedback_resume.load_feedback(
                point,
                context,
                bundle,
                binding=feedback_binding,
                control=control,
                original_loader=previous_feedback,
            )
        return previous_feedback(point, context, bundle)

    replacements = {
        "control": _Proxy(control, publish=publish),
        "admission": _Proxy(admission, wait_for_pre_cuda_admission=wait),
        "inheritance": _Proxy(
            inheritance,
            task_cache_overlay_binding=inheritance.task_cache_overlay_binding,
            replay_resume_binding=replay_binding,
        ),
        "task_overlay": _Proxy(
            task_overlay,
            build_overlay=overlay,
        ),
        "execution_context": context_view,
        "resumed_replay": replay_resume,
    }
    previous = {name: getattr(original, name) for name in replacements}
    try:
        for name, value in replacements.items():
            setattr(original, name, value)
        original.base.DeadlineStop = DeadlineStop
        original.base.ResourceEvents = ResourceEvents
        original.base.execute_virtual = virtual
        original.base.load_feedback = load_feedback
        yield
    finally:
        original.base.DeadlineStop = previous_deadline
        original.base.ResourceEvents = previous_events
        original.base.execute_virtual = previous_virtual
        original.base.load_feedback = previous_feedback
        for name, value in previous.items():
            setattr(original, name, value)


def run(root, context_directory, stage, gpu_index, deadline_epoch=None):
    control = _controller()
    _checked_entry(root, control)
    plan = control.checked_protocol(root)
    binding = inheritance.feedback_resume_binding(context_directory, plan)
    time_policy.validate(plan)
    time_policy.require_no_deadline(deadline_epoch)
    with bound_execution(control, feedback_binding=binding):
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
