"""Zero Provider/Finance/qualification/support replay/representation/Student boundary."""

from contextlib import ExitStack, contextmanager
from unittest.mock import patch

from ..finance_qa_vnext_model_execution import representation as original_representation
from ..finance_qa_vnext_model_execution.models import record
from ..finance_qa_vnext_panel_quotient import projection as prior_projection
from ..finance_qa_vnext_panel_quotient.guards import guard_report as prior_report
from ..finance_qa_vnext_panel_quotient.guards import measurement_guard as prior_guard
from ..finance_qa_vnext_support_exploration import quotient as exploration_quotient
from ..finance_qa_vnext_support_exploration import representation as exploration_representation


@contextmanager
def measurement_guard():
    with prior_guard() as counts, ExitStack() as stack:

        def forbidden(name):
            counts[name] = 0

            def stop(*args, **kwargs):
                counts[name] += 1
                raise RuntimeError("support_transition.forbidden." + name)

            return stop

        for owner, attribute, name in (
            (exploration_quotient, "actual_support", "old_support_proof_reclassification"),
            (exploration_quotient, "analyze_quotient", "old_quotient_reanalysis"),
            (prior_projection, "project_entry", "old_projection_recomputation"),
            (original_representation, "export_candidates", "old_candidate_reexport"),
            (exploration_representation, "analyze_representation", "representation_reanalysis"),
        ):
            stack.enter_context(patch.object(owner, attribute, forbidden(name)))
        yield counts


def guard_report(counts, phase):
    parent = prior_report(counts, phase)
    return record(
        "support_transition_execution_guards",
        phase=phase,
        forbidden_path_call_counts=dict(counts),
        all_zero=parent["all_zero"],
        provider_calls=0,
        new_model_sessions=0,
        runtime_executions=0,
        operation_executions=0,
        qualification_replays=0,
        tokenizer_loads=0,
        tokenizations=0,
        candidate_reexports=0,
        old_support_classifications_replayed=0,
        student_forward_calls=0,
        student_updates=0,
        gpu_jobs=0,
        cuda_initialized=False,
        scope=parent["scope"],
    )
