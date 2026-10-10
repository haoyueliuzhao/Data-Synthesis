"""Bounded pre-CUDA admission around the unchanged sealed V37 evaluator.

Generation, provider observation, all-nine-model scoring and the original V25
math remain the V37 functions. Only their control interface gains resource wait
handling before the first model load; no old result or implementation is edited.
"""

from __future__ import annotations

import argparse
import importlib
import os
import signal
from contextlib import contextmanager
from pathlib import Path

from finqa_v38_admission import AdmissionStopped, wait_for_pre_cuda_admission


def _controller():
    return importlib.import_module("finqa_v38_controller")


def _torch():
    # V37 has already loaded its real runtime when its inventory seam is called.
    # Importing the existing module does not initialize a device or reset a peak.
    return importlib.import_module("torch")


def _parent_module(root, control):
    module = importlib.import_module("finqa_v37_evaluation")
    control.require(
        Path(module.__file__).resolve() == root / "implementation/finqa_v37_evaluation.py",
        "the unchanged sealed V37 evaluation shell is required",
    )
    return module


class _PreCudaStop:
    def __init__(self):
        self.requested = False

    @contextmanager
    def signals(self):
        def request(_signum, _frame):
            self.requested = True

        previous = {number: signal.getsignal(number) for number in (signal.SIGINT, signal.SIGTERM)}
        try:
            for number in previous:
                signal.signal(number, request)
            yield self
        finally:
            for number, handler in previous.items():
                signal.signal(number, handler)


class _AdmissionControl:
    def __init__(self, control, protocol, directory, context_id, gpu_index, deadline_epoch, stop):
        self.control = control
        self.protocol = protocol
        self.directory, self.context_id = directory, context_id
        self.gpu_index, self.deadline_epoch, self.stop = gpu_index, deadline_epoch, stop
        self.admission_calls = 0

    def __getattr__(self, name):
        return getattr(self.control, name)

    def inventory(self):
        self.control.require(self.admission_calls == 0, "one endpoint CUDA admission only")
        self.admission_calls += 1
        row = wait_for_pre_cuda_admission(
            self.protocol,
            "generate",
            self.gpu_index,
            self.directory,
            self.deadline_epoch,
            _torch(),
            lambda: self.stop.requested,
            context_id=self.context_id,
            inventory=self.control.inventory,
            host_memory=self.control.host_memory,
            process_memory=self.control.process_memory,
            birth=self.control.birth,
        )
        return [row]


def _observation_bridge(original_hook, stop):
    """Preserve V37 observation and catch a stop between admission and model load."""

    def install(final, monitor_factory, stop_requested):
        state, original_loader = original_hook(
            final, monitor_factory, lambda: stop.requested or stop_requested()
        )
        observed_loader = final.load_final_provider

        def load(*args, **kwargs):
            if stop.requested:
                raise AdmissionStopped("safe stop requested before endpoint model load")
            return observed_loader(*args, **kwargs)

        final.load_final_provider = load
        return state, original_loader

    return install


def run(root, seed, arm, gpu_index, deadline_epoch):
    root = Path(root).resolve()
    control = _controller()
    protocol = control.checked_protocol(root)
    control.require(
        Path(__file__).resolve() == root / "implementation/finqa_v38_evaluation.py",
        "sealed V38 evaluation admission shell required",
    )
    parent = _parent_module(root, control)
    directory = root / "evaluations" / f"seed{seed}_{arm}" / "generate"
    context_id, stop = f"evaluation:{seed}:{arm}", _PreCudaStop()
    proxy = _AdmissionControl(
        control, protocol, directory, context_id, gpu_index, deadline_epoch, stop
    )
    original_control, original_hook = parent.control, parent.install_observation_hook
    parent.control = proxy
    parent.install_observation_hook = _observation_bridge(original_hook, stop)
    try:
        with stop.signals():
            return parent.run(root, seed, arm, gpu_index, deadline_epoch)
    except BaseException as error:
        # V37's own try/failure block starts after its original idle gate. Bind
        # an admission/setup failure too, while leaving any original failure intact.
        if not (directory / "failure/record.json").exists():
            control.publish(
                directory / "failure/record.json",
                dict(
                    schema="v38_endpoint_pre_cuda_failure.v1",
                    at=control.now(),
                    protocol_id=protocol["id"],
                    context_id=context_id,
                    stage="generate",
                    status="STOPPED_FAILURE_NO_RETRY",
                    error_type=type(error).__name__,
                    error=str(error),
                    retry=False,
                    pid=os.getpid(),
                    birth=control.birth(os.getpid()),
                    gpu_index=gpu_index,
                    deadline_epoch=deadline_epoch,
                    API_calls=0,
                    scoring_calls=0,
                    actual_response_calls=0,
                    original_evaluation_source_unchanged=True,
                ),
            )
        raise
    finally:
        parent.control = original_control
        parent.install_observation_hook = original_hook


def score(root):
    """Delegate the original nine-seal barrier and actual scoring without a GPU wait."""
    root = Path(root).resolve()
    control = _controller()
    control.checked_protocol(root)
    parent = _parent_module(root, control)
    original_control = parent.control
    parent.control = control
    try:
        return parent.score(root)
    finally:
        parent.control = original_control


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
