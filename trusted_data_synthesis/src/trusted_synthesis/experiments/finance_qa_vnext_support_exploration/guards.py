"""Phase-specific boundaries: new Share execution only, never Student or other tasks."""

from contextlib import ExitStack, contextmanager
from unittest.mock import patch

from trusted_synthesis.domains.finance.qa_vnext import measurement
from trusted_synthesis.domains.finance.qa_vnext.program_adapter import ProgramTaskAdapter

from ..finance_qa_vnext_model_execution import qualification
from ..finance_qa_vnext_model_execution.models import record
from ..finance_qa_vnext_task_panel.guards import execution_guard as parent_guard
from ..finance_qa_vnext_task_panel.guards import guard_report as parent_report


@contextmanager
def execution_guard(*, phase):
    with parent_guard(online=phase == "online") as counts, ExitStack() as stack:

        def blocked(name):
            counts[name] = 0

            def stop(*args, **kwargs):
                counts[name] += 1
                raise RuntimeError("support_exploration.forbidden." + name)

            return stop

        stack.enter_context(
            patch.object(ProgramTaskAdapter, "execute", blocked("other_task_operation"))
        )
        if phase != "online":
            stack.enter_context(
                patch.object(qualification, "qualify_session", blocked("qualification_replay"))
            )
            stack.enter_context(
                patch.object(measurement, "audit_session", blocked("domain_audit_replay"))
            )
            stack.enter_context(
                patch.object(measurement, "_validate", blocked("domain_validation_replay"))
            )
        yield counts


def guard_report(counts, *, phase):
    parent = parent_report(counts, phase=phase)
    return record(
        "support_exploration_execution_guards",
        phase=phase,
        forbidden_path_call_counts=dict(counts),
        all_zero=parent["all_zero"],
        cuda_initialized=False,
        student_forward_calls=0,
        student_updates=0,
        gpu_jobs=0,
        online_share_execution_authorized=phase == "online",
        new_qualification_allowed_only_in_online_worker=phase == "online",
        scope=parent["scope"],
    )
