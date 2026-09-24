"""Approved B execution correction: compare controls in the frozen scalar domain.

The original distribution kernel converts strings with ``float(Fraction(value))``
and other values with ``float(value)``, rejecting booleans, invalid conversions,
and nonfinite results. Reusing that exact function does not introduce tolerance,
clipping, normalization, or a new distribution. This module leaves the frozen
worker unchanged; an explicitly registered execution wrapper installs this one
replacement admission function.
"""

import copy

from trusted_synthesis.experiments.finance_qa_vnext_anchored_vtdo.distribution import _scalar
from trusted_synthesis.experiments.finance_qa_vnext_fixed_kernel_value import protocol as p


def revised_distribution(c, plan, job, prefix):
    """Return the saved pi; only control representation comparison is corrected."""
    binding = plan["materials"]["binding"]
    if job["condition"] != "delayed_c":
        return copy.deepcopy(binding["prior"])
    directory = c.RAW / "outer" / job["key"]
    report = p.read_json(directory / "report.json")
    updated = p.checked(
        p.read_json(directory / "distribution_update.json"), "anchored_sources_distribution_step"
    )
    p.require(
        report["plan_id"] == plan["id"]
        and report["job_key"] == job["key"]
        and report["prefix_checkpoint_sha256"] == prefix["prefix_checkpoint_sha256"]
        and report["prefix_snapshot_id"] == prefix["prefix_snapshot_id"]
        and report["numeric_guard_passed"] is True
        and report["distribution_update_id"] == updated["id"],
        "B_training.only_bound_completed_outer_with_passed_guard",
    )
    guard_path = directory / "numeric_guard.json"
    if guard_path.exists():
        p.require(p.read_json(guard_path)["passed"] is True, "B_training.numeric_guard_failed")
    pi = updated["pi_next"]
    p.require(
        set(pi) == set(binding["prior"])
        and all(set(pi[task]) == set(states) for task, states in binding["prior"].items()),
        "B_training.updated_B_support_only",
    )
    p.require(
        all(
            _scalar(pi[task][state]) == _scalar(binding["prior"][task][state])
            for task in binding["control_tasks"]
            for state in binding["prior"][task]
        ),
        "B_training.control_prior_unchanged",
    )
    return pi
