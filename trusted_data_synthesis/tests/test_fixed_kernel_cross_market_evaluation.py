"""CPU-only durable bridge/budget/isolation tests; never loads a Student."""

from types import SimpleNamespace

import fixed_kernel_cross_market_evaluation_20260926 as m
import pytest


@pytest.fixture
def context(tmp_path):
    value = m.Context(tmp_path)
    plan = m.p.record(
        m.PROTOCOL_KIND,
        frozen=True,
        materials={"runtime_binding": m.views.binding()},
        scientific_sources={},
        physical_budget={
            "generate_call_cap": 4,
            "incomplete_generate_call_cap": 3,
            "score_case_cap": 2,
            "worker_start_cap": 2,
        },
    )
    value.write(tmp_path / "protocol.json", plan)
    return value


def generated(point, index, repeat, calls=1):
    return m.p.record(
        "anchored_generated_trajectory",
        point_id=point,
        job={"index": index, "repeat": repeat},
        actual_generate_calls=calls,
    )


def test_adapted_namespace_does_not_mutate_frozen_legacy():
    original = m.legacy.old.feedback.generate_jobs
    adapted = m.adapted_old()
    assert adapted.views is m.views
    assert adapted.feedback.generate_jobs.__globals__["views"] is m.views
    assert original.__globals__["views"] is not m.views
    assert m.legacy.old.feedback.generate_jobs is original


def test_same_model_mode_indices_get_distinct_credits(context):
    context.reserve("generate_call", "greedy", 1, "0_1")
    context.generation_committed("point", 0, generated("point", 0, 0))
    context.reserve("generate_call", "stochastic", 1, "0_1")
    context.generation_committed("point", 0, generated("point", 0, 1))
    state = context._budget_state()
    assert len(state["committed_generation"]) == 2
    assert sum(row["calls"] for row in state["committed_generation"].values()) == 2


def test_duplicate_commit_is_idempotent_but_conflicting_commit_fails(context):
    context.reserve("generate_call", "g", 1, "0_1")
    row = generated("point", 0, 0)
    context.generation_committed("point", 0, row)
    context.generation_committed("point", 0, row)
    with pytest.raises(ValueError, match="one_commit"):
        context.generation_committed("point", 0, generated("point", 0, 0, 0))


def test_no_refund_or_duplicate_physical_attempt(context):
    context.reserve("generate_call", "g", 1, "0_1")
    with pytest.raises(ValueError, match="no_same_attempt_retry"):
        context.reserve("generate_call", "g", 1, "0_1")
    context.reserve("generate_call", "g", 2, "0_1")
    context.reserve("generate_call", "g", 3, "0_1")
    with pytest.raises(ValueError, match="incomplete_call_budget"):
        context.reserve("generate_call", "g", 4, "0_1")
    assert context._budget_state()["counts"]["generate_call"] == 3


def test_unreserved_commit_cannot_create_credit(context):
    with pytest.raises(ValueError, match="calls_precharged"):
        context.generation_committed("point", 0, generated("point", 0, 0))


def test_artifact_writes_confined(context, tmp_path):
    with pytest.raises(ValueError, match="confined_write"):
        context.write(tmp_path.parent / "escaped.json", {})


def test_private_assets_not_opened_before_global_seal(context, monkeypatch):
    directory = context.RAW / "cohort"
    directory.mkdir()
    job = dict(
        key="score",
        seed=11,
        condition="positive",
        phase="greedy",
        directory=str(directory),
        seal_path="notsealed",
    )
    monkeypatch.setattr(m.prior, "public_manifest", lambda plan: {})
    monkeypatch.setattr(
        m.prior, "_helpers", lambda c: SimpleNamespace(_inside_raw=lambda path, **kw: directory)
    )
    monkeypatch.setattr(m.prior, "_sealed_cohort", lambda *args: {})
    opened = []
    monkeypatch.setattr(m.prior, "_private_assets", lambda *args: opened.append(True))

    def no_seal(*args):
        raise ValueError("not_all4860")

    monkeypatch.setattr(m.prior, "require_generation_seal", no_seal)
    with pytest.raises(ValueError, match="not_all4860"):
        m.run_scoring(context, context.RAW, job, 1)
    assert not opened
