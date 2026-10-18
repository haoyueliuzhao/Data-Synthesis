"""V57 signal-observed entry for the unchanged V56 science/evaluation workers."""

import os
import sys

from finqa_v57_signals import install


def main():
    # Do not import argparse, the frozen worker, torch or training before this.
    directory = os.environ.get("V57_SIGNAL_LOG_DIR")
    if not directory:
        raise RuntimeError("V57 requires an independent actual-attempt signal log directory")
    install(directory, role="worker", context={
        "control_root": os.environ.get("V57_CONTROL_ROOT"),
        "job_id": os.environ.get("V54_JOB_ID"),
        "attempt_id": os.environ.get("V56_ATTEMPT_ID")})
    arguments = sys.argv[1:]
    if len(arguments) < 2 or arguments[0] != "--mode" or arguments[1] not in ("science", "evaluation"):
        raise RuntimeError("V57 worker requires --mode science|evaluation then the original worker arguments")
    mode, arguments = arguments[1], arguments[2:]
    if "--root" not in arguments or arguments.index("--root") + 1 >= len(arguments):
        raise RuntimeError("original V56 scientific root is required")
    from pathlib import Path
    import runpy

    root = Path(arguments[arguments.index("--root") + 1]).resolve()
    implementation = root / "implementation"
    entry = implementation / ("finqa_v56_worker.py" if mode == "science" else "finqa_v54_evaluation.py")
    if not entry.is_file():
        raise RuntimeError("original frozen scientific entry is missing")
    # The wrapper observes lifecycle only. Original scientific imports, payload
    # paths, probability implementation, resource gates and RNG stay frozen.
    sys.path.insert(0, str(implementation))
    sys.argv = [str(entry), *arguments]
    runpy.run_path(str(entry), run_name="__main__")


if __name__ == "__main__":
    main()
