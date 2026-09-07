"""Boundaries for read-only Final controls and six new complete sessions."""

from contextlib import ExitStack, contextmanager
from unittest.mock import patch

from ..finance_qa_vnext_cross_binding import source as old_source
from ..finance_qa_vnext_cross_binding.guards import execution_guard as prior_guard
from ..finance_qa_vnext_cross_binding.guards import guard_report as prior_report
from ..finance_qa_vnext_model_execution.models import record


@contextmanager
def execution_guard(*, phase):
    with prior_guard(phase=phase) as counts, ExitStack() as stack:
        counts["new_source_archive_scan"] = 0

        def blocked(*args, **kwargs):
            counts["new_source_archive_scan"] += 1
            raise RuntimeError("final_publication.forbidden.new_source_archive_scan")

        stack.enter_context(patch.object(old_source, "load_sources", blocked))
        yield counts


def guard_report(counts, *, phase):
    old = prior_report(counts, phase=phase)
    return record(
        "final_publication_execution_guards",
        phase=phase,
        forbidden_path_call_counts=dict(counts),
        all_zero=old["all_zero"],
        new_full_sessions_authorized=phase == "online",
        readonly_original_final_verifier_controls_allowed=phase == "preparation",
        old_qualification_or_financial_operation_replay_allowed=False,
        readonly_final_controls_are_model_samples=False,
        student_forward_calls=0,
        student_updates=0,
        gpu_jobs=0,
        cuda_initialized=False,
        scope=old["scope"],
    )
