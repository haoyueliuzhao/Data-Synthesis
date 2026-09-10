"""N/E append public constants only; Worker, calculator and transport remain byte-identical."""

from trusted_synthesis.experiments.finance_qa_vnext_bidirectional_utility.capsule import (
    capsule_files as parent_capsule_files,
)
from trusted_synthesis.experiments.finance_qa_vnext_trace_delivery.instructions import SYSTEMS

from .plan import SYSTEMS_NEW, require


def capsule_files(root, arm):
    require(arm in SYSTEMS_NEW, "capsule.registered_arm")
    files = parent_capsule_files(root)
    suffix = SYSTEMS_NEW[arm][len(SYSTEMS["T"]) :]
    require(SYSTEMS_NEW[arm] == SYSTEMS["T"] + suffix, "capsule.shared_parent_T")
    files["common.py"] += ("\n\nSYSTEM = SYSTEM + " + repr(suffix) + "\n").encode()
    return files
