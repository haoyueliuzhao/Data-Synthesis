"""Five-slot endpoint routing retaining original generation and all-nine scoring."""

from __future__ import annotations

import argparse
import importlib
import importlib.util
import json
import sys
from contextlib import contextmanager
from pathlib import Path

import finqa_v45_admission as admission


def _load():
    name = __name__ + "_sealed_v43_evaluation"
    spec = importlib.util.spec_from_file_location(
        name, Path(__file__).with_name("finqa_v43_evaluation.py")
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


original = _load()


def _controller():
    return importlib.import_module("finqa_v45_controller")


def _checked_entry(root, control):
    root = Path(root).resolve()
    for module in (
        sys.modules[__name__],
        control,
        admission,
        admission.original,
        original,
        original.policy,
        original.time_policy,
        original.stop_signals,
    ):
        path = Path(module.__file__).resolve()
        control.require(
            path == root / "implementation" / path.name,
            "V45 evaluation and every original dependency must use its actual sealed path",
        )


@contextmanager
def bound_execution(control):
    previous = {
        key: getattr(original, key) for key in ("_controller", "_checked_entry", "admission")
    }
    original._controller = lambda: control
    original._checked_entry = _checked_entry
    original.admission = admission
    try:
        yield
    finally:
        for key, value in previous.items():
            setattr(original, key, value)


def run(root, seed, arm, gpu_index, deadline_epoch=None):
    control = _controller()
    _checked_entry(root, control)
    admission.validate_plan(control.checked_protocol(root))
    with bound_execution(control):
        return original.run(root, seed, arm, gpu_index, deadline_epoch)


def score(root):
    control = _controller()
    _checked_entry(root, control)
    admission.validate_plan(control.checked_protocol(root))
    with bound_execution(control):
        return original.score(root)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    generate = sub.add_parser("generate")
    generate.add_argument("--stage", choices=("generate",), required=True)
    generate.add_argument("--root", type=Path, required=True)
    generate.add_argument("--seed", type=int, required=True)
    generate.add_argument("--arm", choices=("static", "c_only", "full"), required=True)
    generate.add_argument("--gpu-index", type=int, required=True)
    generate.add_argument("--deadline-epoch", type=float, default=None)
    sub.add_parser("score").add_argument("--root", type=Path, required=True)
    args = parser.parse_args(argv)
    result = (
        score(args.root)
        if args.command == "score"
        else run(args.root, args.seed, args.arm, args.gpu_index, args.deadline_epoch)
    )
    print(json.dumps(dict(status=result["status"], id=result["id"])))
    return result


if __name__ == "__main__":
    main()
