"""V41 consumption shell over unchanged V40/V37 mathematical worker functions.

Only admission, inherited path routing, read-only task ownership and audit fields
change. There is no response-prefix retry or replay of the accepted V40 pilot.
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

import finqa_v41_admission as admission
import finqa_v41_inheritance as inheritance
import finqa_v41_memory_policy as policy
import finqa_v41_task_view as task_view


def _load_shell():
    name = __name__ + "_unchanged_v40_worker"
    spec = importlib.util.spec_from_file_location(
        name, Path(__file__).with_name("finqa_v40_worker.py")
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


original = _load_shell()
STAGES = original.STAGES


class _Proxy:
    def __init__(self, module, **overrides):
        self._module, self._overrides = module, overrides

    def __getattr__(self, name):
        return self._overrides[name] if name in self._overrides else getattr(self._module, name)


def execution_context(context, _plan):
    """The original matrix now runs normally; do not repeat the old pilot stop."""
    return context


def _controller():
    return importlib.import_module("finqa_v41_controller")


def _checked_entry(root, control):
    root = Path(root).resolve()
    for path in (
        Path(__file__),
        Path(original.__file__),
        Path(control.__file__),
        Path(admission.__file__),
        Path(inheritance.__file__),
        Path(policy.__file__),
        Path(task_view.__file__),
    ):
        control.require(
            path.resolve() == root / "implementation" / path.name,
            "V41 worker and its unchanged execution shell must come from the new seal",
        )


@contextmanager
def bound_execution(control):
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
            value["schema"] = "v41_" + value["schema"][4:]
        if value.get("stage") in STAGES and state["context"] is not None:
            value.update(
                memory_phase=policy.phase_key(value["stage"], state["context"]),
                minimum_free_mib=policy.minimum_free_mib(value["stage"], state["context"]),
                gpu_admission_policy_schema=admission.POLICY_SCHEMA,
                original_mathematical_functions_unchanged=True,
                accepted_V40_pilot_repeated=False,
            )
        return control.publish(path, value)

    def no_replay_resume(_directory, _plan):
        # Any inherited replay had to finish and physically exit successfully.
        # Fresh future R3 phases retain the original complete-response algorithm.
        return None

    replacements = {
        "control": _Proxy(control, publish=publish),
        "admission": _Proxy(admission, wait_for_pre_cuda_admission=wait),
        "inheritance": _Proxy(
            inheritance,
            task_cache_overlay_binding=inheritance.task_cache_view_binding,
            replay_resume_binding=no_replay_resume,
        ),
        "task_overlay": _Proxy(
            task_view,
            allows_new_shard=lambda _binding, _stage: False,
            build_overlay=task_view.build_view,
        ),
        "execution_context": context_view,
    }
    previous = {name: getattr(original, name) for name in replacements}
    try:
        for name, value in replacements.items():
            setattr(original, name, value)
        yield
    finally:
        for name, value in previous.items():
            setattr(original, name, value)


def run(root, context_directory, stage, gpu_index, deadline_epoch):
    control = _controller()
    _checked_entry(root, control)
    with bound_execution(control):
        return original.run(root, context_directory, stage, gpu_index, deadline_epoch)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--context", type=Path, required=True)
    parser.add_argument("--stage", choices=STAGES, required=True)
    parser.add_argument("--gpu-index", type=int, required=True)
    parser.add_argument("--deadline-epoch", type=float, required=True)
    args = parser.parse_args()
    result = run(args.root, args.context, args.stage, args.gpu_index, args.deadline_epoch)
    print(json.dumps(dict(status=result["status"], id=result["id"])))
