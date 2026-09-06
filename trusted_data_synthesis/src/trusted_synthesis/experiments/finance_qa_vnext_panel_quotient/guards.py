"""Instrumented zero-generation, zero-qualification and zero-representation boundary."""

from contextlib import ExitStack, contextmanager
from unittest.mock import patch

from trusted_synthesis.domains.finance.qa_vnext import measurement

from ..finance_qa_vnext_model_execution import qualification, representation
from ..finance_qa_vnext_model_execution.models import record, require
from ..finance_qa_vnext_task_panel.guards import execution_guard as parent_guard
from ..finance_qa_vnext_task_panel.guards import guard_report as parent_report


@contextmanager
def measurement_guard():
    with parent_guard(online=False) as counts, ExitStack() as stack:

        def blocked(name):
            counts[name] = 0

            def stop(*args, **kwargs):
                counts[name] += 1
                raise RuntimeError("panel_quotient.forbidden." + name)

            return stop

        for owner, attr, name in (
            (qualification, "qualify_session", "session_requalification"),
            (measurement, "audit_session", "domain_reaudit"),
            (measurement, "_validate", "domain_revalidation"),
            (representation, "register_tokenizer", "tokenizer_registration"),
            (representation, "encode_original_candidate", "candidate_reencoding"),
        ):
            stack.enter_context(patch.object(owner, attr, blocked(name)))
        # Local tokenizer entry points are also forbidden: reading already saved arrays is enough.
        for attr in ("tokenize_candidates", "_tokenize_candidate"):
            stack.enter_context(patch.object(representation, attr, blocked(attr)))
        assets = representation.frozen_tokenizer_assets
        for attr in (
            "load_tokenizer",
            "_load_local",
            "register_tokenizer",
            "tokenize_rows",
            "_tokenize_row",
        ):
            stack.enter_context(patch.object(assets, attr, blocked(attr)))
        yield counts


def guard_report(counts, phase):
    parent = parent_report(counts, phase=phase)
    require(parent["all_zero"], "panel_quotient.guard_failure")
    return record(
        "panel_quotient_execution_guards",
        phase=phase,
        forbidden_path_call_counts=dict(counts),
        all_zero=True,
        provider_calls=0,
        new_model_sessions=0,
        finance_runtime_executions=0,
        qualifications_recomputed=0,
        tokenization_runs=0,
        student_forward_or_update=0,
        cuda_initialized=False,
        scope=parent["scope"],
    )
