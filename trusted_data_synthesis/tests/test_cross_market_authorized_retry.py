"""Bounded retry authorization; mocked scheduling, no model, GPU, or API work."""

import ast
import copy
import inspect
from contextlib import nullcontext
from pathlib import Path
from types import CodeType, SimpleNamespace

import pytest
import run_cross_market_authorized_retry_20260927 as m

TARGET_ID = "synthetic-authorized-job-id"
GPU_ALLOCATION = dict(
    allowed_gpu_uuids=["GPU-allowed-0", "GPU-allowed-1", "GPU-allowed-6", "GPU-allowed-7"],
    released_gpu_uuids=["GPU-released-2", "GPU-released-3", "GPU-released-4", "GPU-released-5"],
    max_GPU_workers=4,
)


def target(**changes):
    return dict(
        id=TARGET_ID,
        key=m.TARGET,
        work_kind="generate",
        **changes,
    )


def test_extra_two_attempts_apply_only_to_exact_generation_work_unit():
    job = target()
    assert m.ADDITIONAL_ATTEMPTS == 2
    assert m.attempt_cap(job, 4, TARGET_ID) == 6
    assert m.attempt_cap({**job, "key": "other"}, 4, TARGET_ID) == 4
    assert m.attempt_cap({**job, "key": "score", "work_kind": "score"}, 2, TARGET_ID) == 2
    with pytest.raises(ValueError):
        m.attempt_cap({**job, "id": "unapproved-id"}, 4, TARGET_ID)
    with pytest.raises(ValueError):
        m.attempt_cap({**job, "work_kind": "score"}, 2, TARGET_ID)
    with pytest.raises(ValueError):
        m.attempt_cap(job, 4, "different-authorization")
    with pytest.raises(ValueError):
        m.attempt_cap(job, 6, TARGET_ID)


def previous():
    return m.performance.previous


def code_identity(code):
    """Compare executable trees, ignoring filenames and source positions only."""
    return (
        code.co_code,
        code.co_names,
        code.co_varnames,
        code.co_freevars,
        code.co_cellvars,
        tuple(
            code_identity(value) if isinstance(value, CodeType) else value
            for value in code.co_consts
        ),
    )


def test_compiled_coordinator_changes_only_original_cap_assignment():
    original_tree = ast.parse(inspect.getsource(previous().coordinate))
    expected = copy.deepcopy(original_tree)
    changes = []
    for node in ast.walk(expected):
        if (
            isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
            and node.targets[0].id == "cap"
        ):
            original_value = copy.deepcopy(node.value)
            node.value = ast.Call(
                func=ast.Name(id="_authorized_attempt_cap", ctx=ast.Load()),
                args=[ast.Name(id="job", ctx=ast.Load()), node.value],
                keywords=[],
            )
            changes.append((node, original_value))
    assert len(changes) == 1
    expected_namespace = dict(vars(previous()))
    exec(
        compile(ast.fix_missing_locations(expected), "<expected-retry>", "exec"), expected_namespace
    )
    namespace = dict(vars(previous()))
    actual = m.coordinate_with_extra_attempts(namespace, TARGET_ID)
    assert actual.__globals__ is namespace
    assert actual.authorized_retry_binding["all_other_AST_unchanged"] is True
    assert (
        actual.authorized_retry_binding["original_ast_sha256"]
        != (actual.authorized_retry_binding["adapted_ast_sha256"])
    )
    assert code_identity(actual.__code__) == code_identity(
        expected_namespace["coordinate"].__code__
    )
    # Reverting the sole wrapper restores every original barrier/seal/scoring node.
    for node, original_value in changes:
        node.value = original_value
    assert ast.dump(expected, include_attributes=False) == ast.dump(
        original_tree, include_attributes=False
    )


class EndPoll(Exception):
    pass


def one_poll(tmp_path, histories, *, scores_allowed=False):
    plan = dict(
        id="unchanged-scientific-protocol",
        scheduling=dict(
            max_score_cohorts=2,
            max_GPU_workers=4,
            minimum_free_MiB=49152,
            generation_attempts_per_shard=4,
            scoring_attempts_per_cohort=2,
            polling_seconds=20,
        ),
    )
    generated = [target(), dict(id="other-id", key="other", work_kind="generate")]
    scored = dict(id="score-id", key="score", work_kind="score")
    cohorts = [dict(shards=generated, score=scored)]
    statuses, launches, sleeps = [], [], []

    class FakeContext:
        RAW = tmp_path

        def __init__(self, raw):
            assert raw == tmp_path

        def locked(self, path, blocking):
            assert blocking is False
            return nullcontext()

        def read_protocol(self, root):
            return plan

        def write(self, path, value, immutable=True):
            assert Path(path).name == "status.json"
            statuses.append(value)

    def sleep(seconds):
        sleeps.append(seconds)
        raise EndPoll

    if scores_allowed:
        (tmp_path / "generation_seal.json").touch()
    namespace = dict(vars(previous()))
    namespace.update(
        evaluation=SimpleNamespace(Context=FakeContext),
        prepare_cohorts=lambda *args: cohorts,
        attempts=lambda c, job: histories.get(job["key"], []),
        seal_cohort=lambda *args: False,
        complete_job=lambda job: False,
        available_gpus=lambda minimum: ["GPU-synthetic-0", "GPU-synthetic-1"],
        launch=lambda c, root, job, attempt, gpu: launches.append((job["key"], attempt, gpu)),
        emit=lambda *args, **kwargs: None,
        time=SimpleNamespace(sleep=sleep),
    )
    function = m.coordinate_with_extra_attempts(namespace, TARGET_ID)
    try:
        function(tmp_path, tmp_path)
    except EndPoll:
        pass
    assert len(statuses) == 1
    return statuses[0], launches, sleeps


def settled(attempt, *, alive=False):
    return [
        dict(
            attempt=attempt,
            alive=alive,
            outcome=None if alive else dict(status="RESOURCE_RETRY"),
            process=dict(pid=1234, process_identity="existing-worker"),
            reserved=dict(gpu="GPU-synthetic-0"),
        )
    ]


@pytest.mark.parametrize("previous_attempt,next_attempt", [(4, 5), (5, 6)])
def test_coordinator_grants_exactly_attempts_five_and_six(tmp_path, previous_attempt, next_attempt):
    status, launches, _ = one_poll(
        tmp_path,
        {m.TARGET: settled(previous_attempt), "other": settled(4)},
    )
    assert launches == [(m.TARGET, next_attempt, "GPU-synthetic-0")]
    assert status["blocked"] == [dict(key="other", reason="finite_attempt_budget_exhausted")]
    assert status["phase"] == "GENERATION"


def test_seventh_attempt_remains_blocked_and_other_shards_keep_original_cap(tmp_path):
    status, launches, sleeps = one_poll(tmp_path, {m.TARGET: settled(6), "other": settled(4)})
    assert launches == [] and sleeps == []
    assert status["blocked"] == [
        dict(key=key, reason="finite_attempt_budget_exhausted") for key in (m.TARGET, "other")
    ]


def test_existing_worker_is_adopted_without_launching_duplicate(tmp_path):
    status, launches, _ = one_poll(
        tmp_path, {m.TARGET: settled(5, alive=True), "other": settled(4)}
    )
    assert launches == []
    assert status["active_workers"] == 1
    assert status["blocked"] == [dict(key="other", reason="finite_attempt_budget_exhausted")]


def test_unrelated_fatal_still_blocks_target_without_consuming_authorization(tmp_path):
    fatal = settled(4)
    fatal[0]["outcome"] = dict(status="FATAL", message="unrelated-data-error")
    status, launches, _ = one_poll(tmp_path, {m.TARGET: fatal, "other": settled(4)})
    assert launches == []
    assert status["blocked"][0] == dict(key=m.TARGET, reason="unrelated-data-error")


def test_scoring_still_requires_generation_seal_and_original_two_attempt_cap(tmp_path):
    status, launches, _ = one_poll(
        tmp_path,
        {m.TARGET: settled(6), "other": settled(4), "score": settled(2)},
        scores_allowed=True,
    )
    assert launches == []
    assert status["phase"] == "SCORING"
    assert status["blocked"] == [dict(key="score", reason="finite_attempt_budget_exhausted")]


def test_adapter_retains_parent_namespace_and_original_worker(monkeypatch):
    original_namespace = dict(vars(previous()))
    inherited = dict(attempts=object(), evaluation=object(), performance_contexts=[], os=object())
    original_namespace.update(inherited)
    seen = []

    def parent(performance_plan, recovered):
        seen.append((performance_plan, recovered))
        return original_namespace

    monkeypatch.setattr(m.performance, "controller_namespace", parent)
    performance_plan, recovered = {"id": "performance"}, {"id": "cuda"}
    plan = {
        "target_job_id": TARGET_ID,
        "gpu_allocation": GPU_ALLOCATION,
        "coordinator_binding": m.coordinate_with_extra_attempts(
            dict(vars(previous())), TARGET_ID
        ).authorized_retry_binding,
    }
    namespace = m.controller_namespace(plan, performance_plan, recovered)
    assert seen == [(performance_plan, recovered)]
    assert namespace is original_namespace
    assert namespace["SCRIPT"] == m.SCRIPT
    assert namespace["worker"].__code__ is previous().worker.__code__
    for key, value in inherited.items():
        assert namespace[key] is value


def test_real_parent_overlay_retains_cuda_environment_and_performance_context():
    performance_plan = dict(id="synthetic-performance", logprob_optimization=dict(enabled=False))
    recovered = dict(id="synthetic-cuda", allowed_failures=[])
    plan = {
        "target_job_id": TARGET_ID,
        "gpu_allocation": GPU_ALLOCATION,
        "coordinator_binding": m.coordinate_with_extra_attempts(
            dict(vars(previous())), TARGET_ID
        ).authorized_retry_binding,
    }
    namespace = m.controller_namespace(plan, performance_plan, recovered)
    assert namespace["os"].environ["CUBLAS_WORKSPACE_CONFIG"] == ":4096:8"
    assert namespace["worker"].__code__ is previous().worker.__code__
    assert issubclass(namespace["evaluation"].Context, m.performance.PerformanceContext)
    assert namespace["launch"].__globals__ is namespace
    assert namespace["launch"].__globals__["SCRIPT"] == m.SCRIPT


def test_registered_failure_scope_accepts_only_exact_original_four_settled_failures(monkeypatch):
    job, context = target(), object()
    entries = [dict(attempt=value) for value in range(1, 5)]
    rows = [
        dict(
            attempt=value,
            alive=False,
            outcome=(
                dict(
                    status="FATAL",
                    exception_type="ValueError",
                    message=m.recovery.MISSING_CUBLAS_MESSAGE,
                )
                if value == 1
                else dict(status="RESOURCE_RETRY", exception_type="CapacityWait")
            ),
        )
        for value in range(1, 5)
    ]
    monkeypatch.setattr(previous(), "attempts", lambda *args: rows)
    monkeypatch.setattr(
        m.recovery, "failure_entry", lambda c, work, row: dict(attempt=row["attempt"])
    )
    m.validate_original_failures(context, job, entries)
    with pytest.raises(ValueError, match="exact_four_failures"):
        m.validate_original_failures(context, job, entries[:-1])
    rows[-1]["alive"] = True
    with pytest.raises(ValueError, match="unchanged_original_failure_artifacts"):
        m.validate_original_failures(context, job, entries)
    rows[-1]["alive"] = False
    rows[-1]["outcome"] = dict(status="FATAL", exception_type="UnexpectedError")
    with pytest.raises(ValueError, match="only_original_cublas_and_capacity_failures"):
        m.validate_original_failures(context, job, entries)


@pytest.mark.parametrize("attempt,accepted", [(5, True), (6, True), (7, False)])
def test_direct_worker_enforces_grant_before_parent_execution(
    tmp_path, monkeypatch, attempt, accepted
):
    job = m.p.record("cross_market_evaluation_work_unit", key=m.TARGET, work_kind="generate")
    plan = dict(target_job_id=job["id"], gpu_allocation=GPU_ALLOCATION)
    original = dict(scheduling=dict(generation_attempts_per_shard=4, scoring_attempts_per_cohort=2))
    context = SimpleNamespace(RAW=tmp_path, read_protocol=lambda root: original)
    monkeypatch.setattr(m.performance, "context", lambda raw: context)
    monkeypatch.setattr(m, "protocol", lambda *args: plan)
    monkeypatch.setattr(m.p, "read_json", lambda path: job)
    monkeypatch.setenv("CUDA_VISIBLE_DEVICES", GPU_ALLOCATION["allowed_gpu_uuids"][0])
    calls = []
    monkeypatch.setattr(m.performance, "execute", lambda *args: calls.append(args) or 0)
    if accepted:
        assert m.execute("worker", tmp_path, tmp_path, tmp_path / "job.json", attempt) == 0
        assert len(calls) == 1 and calls[0][-1] == attempt
    else:
        with pytest.raises(ValueError, match="bounded_worker_attempt"):
            m.execute("worker", tmp_path, tmp_path, tmp_path / "job.json", attempt)
        assert calls == []


def test_available_gpu_filter_never_reacquires_released_devices(monkeypatch):
    requests = []
    physically_available = ["GPU-released-2", "GPU-allowed-1", "GPU-released-5", "GPU-allowed-0"]

    def available(minimum):
        requests.append(minimum)
        return physically_available

    monkeypatch.setattr(previous(), "available_gpus", available)
    performance_plan = dict(id="synthetic-performance", logprob_optimization=dict(enabled=False))
    recovered = dict(id="synthetic-cuda", allowed_failures=[])
    plan = {
        "target_job_id": TARGET_ID,
        "gpu_allocation": GPU_ALLOCATION,
        "coordinator_binding": m.coordinate_with_extra_attempts(
            dict(vars(previous())), TARGET_ID
        ).authorized_retry_binding,
    }
    namespace = m.controller_namespace(plan, performance_plan, recovered)
    assert namespace["available_gpus"](49152) == ["GPU-allowed-1", "GPU-allowed-0"]
    assert requests == [49152]
    assert physically_available == [
        "GPU-released-2",
        "GPU-allowed-1",
        "GPU-released-5",
        "GPU-allowed-0",
    ]


@pytest.mark.parametrize("work_kind,accepted", [("generate", False), ("score", True)])
def test_released_gpu_worker_is_rejected_before_parent_except_cpu_scoring(
    tmp_path, monkeypatch, work_kind, accepted
):
    job = m.p.record("cross_market_evaluation_work_unit", key="other", work_kind=work_kind)
    plan = dict(target_job_id=TARGET_ID, gpu_allocation=GPU_ALLOCATION)
    original = dict(scheduling=dict(generation_attempts_per_shard=4, scoring_attempts_per_cohort=2))
    context = SimpleNamespace(RAW=tmp_path, read_protocol=lambda root: original)
    monkeypatch.setattr(m.performance, "context", lambda raw: context)
    monkeypatch.setattr(m, "protocol", lambda *args: plan)
    monkeypatch.setattr(m.p, "read_json", lambda path: job)
    monkeypatch.setenv("CUDA_VISIBLE_DEVICES", GPU_ALLOCATION["released_gpu_uuids"][0])
    calls = []
    monkeypatch.setattr(m.performance, "execute", lambda *args: calls.append(args) or 0)
    if accepted:
        assert m.execute("worker", tmp_path, tmp_path, tmp_path / "job.json", 1) == 0
        assert len(calls) == 1
    else:
        with pytest.raises(ValueError):
            m.execute("worker", tmp_path, tmp_path, tmp_path / "job.json", 1)
        assert calls == []
