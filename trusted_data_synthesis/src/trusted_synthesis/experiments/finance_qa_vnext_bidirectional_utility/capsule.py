"""Isolated T worker with only the current Flash identity contract changed."""

from trusted_synthesis.experiments.finance_qa_vnext_trace_delivery.instructions import (
    capsule_files as parent_capsule_files,
)

from .plan import PACKAGE


def capsule_files(root):
    files = parent_capsule_files(root, "T")
    files["worker.py"] = (root / PACKAGE / "online_worker.py").read_bytes()
    files["model_contract.py"] = (root / PACKAGE / "model_contract.py").read_bytes()
    return files
