"""New-bound-task execution only in online workers; no Student/GPU in any phase."""

from contextlib import ExitStack, contextmanager
from unittest.mock import patch

from trusted_synthesis.domains.finance.qa_vnext import measurement
from trusted_synthesis.domains.finance.qa_vnext.bound_share_adapter import BoundShareTaskAdapter
from trusted_synthesis.domains.finance.qa_vnext.program_adapter import ProgramTaskAdapter
from trusted_synthesis.domains.finance.qa_vnext.share_adapter import ShareTaskAdapter

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
                raise RuntimeError("cross_binding.forbidden." + name)

            return stop

        paths = [
            (ShareTaskAdapter, "__init__", "old_fixed_share_adapter"),
            (ShareTaskAdapter, "execute", "old_fixed_share_execution"),
            (ProgramTaskAdapter, "execute", "other_task_execution"),
        ]
        if phase != "online":
            paths += [
                (BoundShareTaskAdapter, "execute", "new_task_execution_outside_online"),
                (qualification, "qualify_session", "qualification_replay"),
                (measurement, "audit_session", "domain_audit_replay"),
                (measurement, "_validate", "domain_validation_replay"),
            ]
        for owner, attribute, name in paths:
            stack.enter_context(patch.object(owner, attribute, blocked(name)))
        yield counts


def guard_report(counts, *, phase):
    parent = parent_report(counts, phase=phase)
    return record(
        "cross_binding_execution_guards",
        phase=phase,
        forbidden_path_call_counts=dict(counts),
        all_zero=parent["all_zero"],
        new_bound_task_execution_authorized=phase == "online",
        qualification_allowed_only_in_online_worker=phase == "online",
        student_forward_calls=0,
        student_updates=0,
        gpu_jobs=0,
        cuda_initialized=False,
        scope=parent["scope"],
    )
