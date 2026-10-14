"""V41 shared-device endpoint shell; frozen generation and all-nine scoring stay.

The two original evaluator device predicates are replaced, not tricked using an
empty process list or a rewritten science plan. Each gets a fresh real inventory
and bounded CPU-only admission under the same phase deadline and worker lease.
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
import finqa_v41_memory_policy as policy


def _load_shell():
    name = __name__ + "_unchanged_v40_endpoint"
    spec = importlib.util.spec_from_file_location(
        name, Path(__file__).with_name("finqa_v40_evaluation.py")
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


original = _load_shell()


class _ControlProxy:
    def __init__(self, control):
        self.original = control

    def __getattr__(self, name):
        return getattr(self.original, name)

    def publish(self, path, body):
        value = dict(body)
        if isinstance(value.get("schema"), str) and value["schema"].startswith("v40_"):
            value["schema"] = "v41_" + value["schema"][4:]
        if value.get("stage") == "generate":
            value.update(
                memory_phase=policy.phase_key("generate", None),
                minimum_free_mib=policy.minimum_free_mib("generate", None),
                gpu_admission_policy_schema=admission.POLICY_SCHEMA,
                original_evaluation_registration_unchanged=True,
            )
        return self.original.publish(path, value)


def _controller():
    return importlib.import_module("finqa_v41_controller")


def _checked_entry(root, control):
    root = Path(root).resolve()
    for path in (
        Path(__file__),
        Path(original.__file__),
        Path(control.__file__),
        Path(admission.__file__),
        Path(policy.__file__),
    ):
        control.require(
            path.resolve() == root / "implementation" / path.name,
            "V41 endpoint and unchanged generator shell must come from the new seal",
        )


@contextmanager
def endpoint_gpu_policy(
    final,
    protocol,
    gpu_index,
    control,
    stop,
    deadline_epoch,
    *,
    directory,
    context_id,
    extra_stop_requested=lambda: False,
):
    """Replace both old idle predicates with bounded shared-memory admission.

    Nested heartbeat paths are part of the controller's same global wait ledger;
    these are resource rechecks in one attempt, not a generation retry. Their
    original phase deadline is retained and no model exists before acceptance.
    """
    admission.validate_plan(protocol)
    control.require(gpu_index in admission.ALLOWED_GPUS, "GPU outside registered host scope")
    previous = final.eligible_gpu
    count = 0

    def eligible(_scientific_plan, index, _provided_inventory):
        nonlocal count
        control.require(index == gpu_index, "endpoint changed its dispatched physical GPU")
        count += 1
        control.require(count <= 2, "unexpected extra original endpoint GPU admission predicate")
        return admission.wait_for_pre_cuda_admission(
            protocol,
            "generate",
            gpu_index,
            Path(directory) / "pre_cuda_rechecks" / f"check{count:04d}",
            deadline_epoch,
            final.torch,
            lambda: stop.requested or extra_stop_requested(),
            context_id=context_id,
            inventory=control.inventory,
            host_memory=control.host_memory,
            process_memory=control.process_memory,
            birth=control.birth,
        )

    final.eligible_gpu = eligible
    try:
        yield
    finally:
        final.eligible_gpu = previous


@contextmanager
def bound_execution(
    control, *, directory=None, context_id=None, extra_stop_requested=lambda: False
):
    proxy = _ControlProxy(control)

    @contextmanager
    def bound_gpu_policy(final, protocol, gpu_index, scoped_control, stop, deadline_epoch):
        control.require(
            directory is not None and context_id is not None, "endpoint identity required"
        )
        with endpoint_gpu_policy(
            final,
            protocol,
            gpu_index,
            scoped_control,
            stop,
            deadline_epoch,
            directory=directory,
            context_id=context_id,
            extra_stop_requested=extra_stop_requested,
        ):
            yield

    replacements = {
        "_controller": lambda: proxy,
        "admission": admission,
        "_checked_entry": _checked_entry,
        "endpoint_gpu_policy": bound_gpu_policy,
    }
    previous = {name: getattr(original, name) for name in replacements}
    try:
        for name, value in replacements.items():
            setattr(original, name, value)
        yield
    finally:
        for name, value in previous.items():
            setattr(original, name, value)


def run(root, seed, arm, gpu_index, deadline_epoch):
    control = _controller()
    _checked_entry(root, control)
    directory = Path(root).resolve() / "evaluations" / f"seed{seed}_{arm}" / "generate"
    # The inherited generator installs its own legitimate PauseRequest handler
    # after the first admission. Its receipt must also stop subsequent CPU waits;
    # observe it without replacing, ignoring, or doing IO inside that handler.
    with original.stop_signals.audit_signal_installations() as receipts:
        with bound_execution(
            control,
            directory=directory,
            context_id=f"evaluation:{seed}:{arm}",
            extra_stop_requested=lambda: bool(receipts.receipts),
        ):
            return original.run(root, seed, arm, gpu_index, deadline_epoch)


def score(root):
    """Delegate without moving or weakening the original all-nine-seal barrier."""
    control = _controller()
    _checked_entry(root, control)
    with bound_execution(control):
        return original.score(root)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    generate = sub.add_parser("generate")
    generate.add_argument("--stage", choices=("generate",), required=True)
    generate.add_argument("--root", type=Path, required=True)
    generate.add_argument("--seed", type=int, required=True)
    generate.add_argument("--arm", choices=("static", "c_only", "full"), required=True)
    generate.add_argument("--gpu-index", type=int, required=True)
    generate.add_argument("--deadline-epoch", type=float, required=True)
    sub.add_parser("score").add_argument("--root", type=Path, required=True)
    args = parser.parse_args()
    result = (
        score(args.root)
        if args.command == "score"
        else run(args.root, args.seed, args.arm, args.gpu_index, args.deadline_epoch)
    )
    print(json.dumps(dict(status=result["status"], id=result["id"])))
