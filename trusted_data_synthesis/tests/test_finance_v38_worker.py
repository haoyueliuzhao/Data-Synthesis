"""CPU/mock recovery orchestration; no CUDA, API, or scientific experiment."""

import ast
import copy
import fcntl
import hashlib
import importlib
import json
import sys
import time
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
worker = importlib.import_module("finqa_v38_worker")
trainer = importlib.import_module("finqa_v37_training")


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def publish(path, body):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    result = dict(body, id=digest(body))
    with path.open("x") as stream:
        json.dump(result, stream)
    return result


def entry(path):
    path = Path(path)
    return dict(path=str(path), id=json.loads(path.read_text())["id"])


@pytest.fixture
def episode(tmp_path, monkeypatch):
    parent = tmp_path / "production_resume_01"
    root = parent / "recovery_01"
    origin = parent / "contexts/seed137/c_only/step1192_outer"
    new_context = root / "contexts/seed137/c_only/step1192_outer"
    origin.mkdir(parents=True)
    marker = origin / "parent_evidence.json"
    marker.write_text('{"status":"PARENT_EVIDENCE_ONLY"}\n')
    original_bytes = marker.read_bytes()
    state = dict(
        seed=137,
        arm="C-only",
        step=1192,
        outer_done=[298, 596, 894],
        pi={"t": {"a": 0.4, "b": 0.6}},
        prior={"t": {"a": 0.5, "b": 0.5}},
        parameters={"w": [1.0]},
        optimizer={"step": 1192},
        rng={"python": 123},
        buffers={},
        schedule={"id": "actual-schedule"},
    )
    training_root = tmp_path / "original_training"
    arm_root = training_root / "seed137/arms/c_only"
    context = dict(
        id="unchanged-parent-context",
        seed=137,
        arm="C-only",
        step=1192,
        due_outer=True,
        training_stop_step=1193,
        training_root=str(training_root),
        arm_root=str(arm_root),
        checkpoint={"path": str(arm_root / "training/step1192_step")},
        pre_state_digest=digest(state),
        branch=dict(contribution_only=True, b_N=0, parameters={"original": 1}),
        feedback=dict(mode="sealed_existing", expected_point_id="actual-point"),
    )
    plan = dict(id="new-protocol", gpu_uuids={"4": "GPU-fixed"})
    calls, drivers, payloads = [], [], {}
    flags = SimpleNamespace(
        inherited=True,
        upstream_failure=False,
        admission_failure=None,
        mutate_model=False,
        resource_failure=None,
    )

    class Cuda:
        initialized = False
        resets = 0

        def is_initialized(self):
            return self.initialized

        def reset_peak_memory_stats(self):
            assert calls[-1][0] == "admission"
            calls.append(("cuda_initialized",))
            self.initialized = True
            self.resets += 1

    cuda = Cuda()

    class Pause:
        requested = False
        reason = None

        def signals(self):
            return nullcontext()

    class Samples:
        def __init__(self, gpu_uuid):
            assert gpu_uuid == "GPU-fixed"

        def __enter__(self):
            return self

        def __exit__(self, *_error):
            return False

        def report(self):
            return dict(mock_only=True)

    class Monitor:
        def __init__(self, torch, *, event_sink, stop_requested):
            assert torch.cuda is cuda
            self.sink, self.stop_requested = event_sink, stop_requested

        def snapshot(self, label, **_kwargs):
            self.sink(dict(label=label, passed=label != flags.resource_failure))

        def clear_unused(self, label):
            self.snapshot(label + ".after_cleanup")

        def check_stop(self, label, **_kwargs):
            assert not self.stop_requested(), label

        def report(self):
            return dict(
                peak_reset_calls=0,
                max_observed_peak_allocated_bytes=1024,
                min_boundary_free_bytes=4 * 1024**3,
            )

    class Cache:
        def assemble(self, device):
            assert device == "cuda:0" and not cuda.initialized
            calls.append(("assemble_parent_tasks",))
            return dict(task="CPU-backed")

        def verification_summary(self):
            return dict(verified_task_count=744, strict_payload_file_reads=744)

    cache = Cache()
    pool = SimpleNamespace(_manifest=SimpleNamespace(registration=SimpleNamespace(mu={"t": 1})))

    class Driver:
        def __init__(self, model, optimizer, actual_pool, **kwargs):
            assert actual_pool is pool and kwargs["feedback_collector"] is None
            self.model, self.optimizer, self.pool = model, optimizer, pool
            self.root, self.seed, self.arm = Path(kwargs["root"]), 137, "C-only"
            self.step_index, self.final_step = 1192, 1490
            self.outer_steps = (298, 596, 894, 1192)
            self.pi, self.outer_done = copy.deepcopy(state["pi"]), list(state["outer_done"])
            self.steps, self.commits, self.tainted = 0, [], False
            drivers.append(self)

        def restore(self, checkpoint):
            assert checkpoint == context["checkpoint"]["path"]
            calls.append(("restore_actual_state", checkpoint))

        def _payload(self):
            return copy.deepcopy(
                state | dict(step=self.step_index, pi=self.pi, outer_done=self.outer_done)
            )

        def commit(self, phase, evidence, *, outer_inputs):
            destination = self.root / f"step{self.step_index:04d}_{phase}"
            destination.mkdir(parents=True, exist_ok=False)
            self.commits.append((phase, evidence, outer_inputs))
            return destination

        def step(self):
            assert self.step_index in self.outer_done
            self.step_index += 1
            self.steps += 1

    def load_components(_assets, seed):
        assert cuda.initialized and seed == 137
        calls.append(("model_load",))
        return SimpleNamespace(value=1), object(), SimpleNamespace(value=1), object(), object()

    def peek(directory):
        expected = origin if flags.inherited else new_context
        assert directory == expected
        calls.append(("peek", directory))
        return context

    def load(directory, **_kwargs):
        assert directory == (origin if flags.inherited else new_context)
        calls.append(("load", directory))
        return context, copy.deepcopy(state), pool, cache

    def stage_directory(directory, _plan, stage):
        assert directory == new_context
        if flags.inherited and stage not in {"distribution", "train"}:
            return origin / stage
        return directory / stage

    def require_upstream(directory, actual_context, actual_plan, stage, actual_control):
        assert directory == new_context and actual_context is context and actual_plan is plan
        assert actual_control is worker.control and not cuda.initialized
        calls.append(("checked_upstream", stage))
        if flags.upstream_failure:
            raise ValueError("parent result or real exit invalid")

    def admit(actual_plan, stage, gpu, directory, deadline, torch, stop, *, context_id):
        assert actual_plan is plan and gpu == 4 and torch.cuda is cuda
        assert not cuda.initialized and not stop() and time.time() < deadline
        assert directory == new_context / stage and context_id == context["id"]
        assert (directory / "attempt/record.json").is_file()
        # CPU preparation/wait retains both worker and original training locks.
        with (directory / "worker.lock").open("a") as locked:
            with pytest.raises(BlockingIOError):
                fcntl.flock(locked, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with pytest.raises(BlockingIOError):
            with worker.base.training_point_locks(context, "train"):
                pytest.fail("arm lock must be retained through admission")
        calls.append(("admission", stage))
        if flags.admission_failure is not None:
            raise flags.admission_failure
        return dict(index=4, uuid="GPU-fixed")

    point = dict(G={"w": 2}, theta_bar={"w": 3}, point_id="actual-point")
    replay = dict(gJ={"w": 4}, point_id="actual-point")
    payloads[origin / "virtual_point/payload"] = point
    payloads[origin / "replay_R3/payload"] = replay

    def read_payload(directory, _rt, *, context: dict, phase):
        assert context["id"] == "unchanged-parent-context"
        calls.append(("read_payload", directory, phase))
        return copy.deepcopy(payloads[directory])

    def distribution(
        directory, actual_context, before, actual_point, actual_replay, driver, *_args
    ):
        assert actual_context is context and actual_point == point and actual_replay == replay
        calls.append(("distribution", directory))
        if flags.mutate_model:
            driver.model.value += 1
        values = dict(
            schema="v9_real_outer_inputs.v1",
            pre_state=before,
            actual_tensors_saved=True,
            mu={"t": 1},
            q_next={"t": {"a": 0.3, "b": 0.7}},
            C={"t": {"a": 0.1, "b": -0.1}},
            feedback_seal=dict(denominator=700, seal_sha256="same-seal"),
            rewards=[1] * 700,
            point_id="actual-point",
            **copy.deepcopy({k: point[k] for k in ("G", "theta_bar")}),
            gJ=replay["gJ"],
            pullback={"w": 5},
        )
        evidence = dict(
            distribution=dict(pi_next=copy.deepcopy(values["q_next"])),
            C=values["C"],
            actual_feedback_denominator=700,
            feedback_seal_sha256="same-seal",
            **{
                label: digest(values[key])
                for key, label in (
                    ("G", "population_gradient_digest"),
                    ("theta_bar", "actual_virtual_theta_digest"),
                    ("gJ", "feedback_gradient_digest"),
                    ("pullback", "pullback_digest"),
                )
            },
        )
        payloads[directory / "payload"] = dict(outer_inputs=values, evidence=evidence)
        publish(directory / "payload/record.json", dict(context_id=context["id"]))
        return dict(payload=entry(directory / "payload/record.json"), denominator=700)

    training = SimpleNamespace(
        checked_plan=lambda _root: dict(assets_protocol={"path": "original-assets"}),
        adapters=lambda: SimpleNamespace(TrainingDriver=Driver),
    )
    rt = SimpleNamespace(
        torch=SimpleNamespace(cuda=cuda, __version__="CPU_MOCK"),
        launcher=SimpleNamespace(read_bound=lambda _path: {}, _load_components=load_components),
        v8=SimpleNamespace(
            _tree_digest=digest,
            parameter_digest=digest,
            PARAMETERS=context["branch"]["parameters"],
        ),
    )
    bundle = SimpleNamespace(
        rt=rt,
        training=training,
        replay=SimpleNamespace(PauseRequest=Pause),
        context=SimpleNamespace(peek_context=peek, load_context=load),
        original_cache=object(),
        guard=SimpleNamespace(recompute_point_id=lambda *_a, **_k: "actual-point"),
        inherited=SimpleNamespace(DeviceSamples=Samples),
        memory=SimpleNamespace(TailMemoryMonitor=Monitor),
        trainer=trainer,
    )
    monkeypatch.setattr(worker, "__file__", str(root / "implementation/finqa_v38_worker.py"))
    monkeypatch.setattr(worker, "dependencies", lambda _root: bundle)
    monkeypatch.setattr(worker.control, "checked_protocol", lambda _root: plan)
    monkeypatch.setattr(worker.control, "checked_implementation", lambda _root: {})
    monkeypatch.setattr(worker.control, "publish", publish)
    monkeypatch.setattr(worker.control, "entry", entry)
    monkeypatch.setattr(
        worker.inheritance,
        "resolve_origin_context",
        lambda directory, _plan: origin if flags.inherited else directory,
    )
    monkeypatch.setattr(worker.inheritance, "stage_directory", stage_directory)
    monkeypatch.setattr(worker.inheritance, "require_upstream", require_upstream)
    monkeypatch.setattr(worker.admission, "wait_for_pre_cuda_admission", admit)
    monkeypatch.setattr(worker.base, "read_payload", read_payload)
    monkeypatch.setattr(worker.base, "load_feedback", lambda *_a: ("sealed-cohort", [1] * 700))
    monkeypatch.setattr(worker.base, "execute_distribution", distribution)
    monkeypatch.setattr(
        worker.base,
        "state_identity",
        lambda _bundle, model, optimizer: (model.value, optimizer.value),
    )
    monkeypatch.setattr(
        worker.base,
        "host_memory",
        lambda: dict(rss_bytes=1024, peak_rss_bytes=2048, available_bytes=512 * 1024**3),
    )
    return SimpleNamespace(
        root=root,
        origin=origin,
        directory=new_context,
        context=context,
        calls=calls,
        cuda=cuda,
        flags=flags,
        drivers=drivers,
        marker=marker,
        original_bytes=original_bytes,
        plan=plan,
        payloads=payloads,
        run=lambda stage: worker.run(root, new_context, stage, 4, time.time() + 3600),
    )


def test_parent_reads_new_protocol_outputs_and_original_state_resource_checks(episode):
    previous = worker.base.control
    result = episode.run("distribution")
    assert worker.base.control is previous
    assert result["protocol_id"] == "new-protocol"
    assert result["context_id"] == "unchanged-parent-context"
    assert result["model_optimizer_rng_buffers_unchanged"] is True
    assert result["optimizer_steps"] == result["replayed_responses"] == 0
    assert result["resources"]["maximum_allocated_bytes"] == 76 * 1024**3
    assert result["resources"]["minimum_device_free_bytes"] == 2 * 1024**3
    assert result["resources"]["peak_resets_after_model_loading_begins"] == 0
    assert result["resources"]["host"]["rss_limit_bytes"] == 192 * 1024**3
    assert episode.cuda.resets == 1
    assert [row[1] for row in episode.calls if row[0] == "read_payload"] == [
        episode.origin / "virtual_point/payload",
        episode.origin / "replay_R3/payload",
    ]
    assert episode.marker.read_bytes() == episode.original_bytes
    assert list(episode.origin.iterdir()) == [episode.marker]
    attempt = json.loads((episode.directory / "distribution/attempt/record.json").read_text())
    assert attempt["protocol_id"] == result["protocol_id"]
    assert attempt["context_id"] == result["context_id"]
    assert attempt["automatic_retry"] is False


def test_inherited_training_reads_new_distribution_and_commits_one_outer_and_one_step(episode):
    episode.run("distribution")
    episode.cuda.initialized = False  # A distinct cold worker process is simulated.
    result = episode.run("train")
    driver = episode.drivers[-1]
    assert result["protocol_id"] == "new-protocol"
    assert result["context_id"] == "unchanged-parent-context"
    assert result["committed_step"] == 1193
    assert result["actual_optimizer_steps"] == driver.steps == 1
    assert len(driver.commits) == 1 and driver.commits[0][0] == "outer"
    assert driver.outer_done == [298, 596, 894, 1192]
    assert ("read_payload", episode.directory / "distribution/payload", "distribution") in (
        episode.calls
    )
    assert episode.marker.read_bytes() == episode.original_bytes


@pytest.mark.parametrize("stage", ["shard00", "shard03", "virtual_point", "replay_R3"])
def test_inherited_completed_stages_cannot_be_redispatched(episode, stage):
    with pytest.raises(ValueError, match="completed parent stages"):
        episode.run(stage)
    assert not episode.cuda.initialized and not episode.calls
    assert not (episode.directory / stage).exists()


def test_invalid_upstream_stops_before_admission_or_cuda(episode):
    episode.flags.upstream_failure = True
    with pytest.raises(ValueError, match="parent result or real exit invalid"):
        episode.run("distribution")
    assert not episode.cuda.initialized
    assert not any(row[0] == "admission" for row in episode.calls)
    failure = json.loads((episode.directory / "distribution/failure/record.json").read_text())
    assert failure["protocol_id"] == "new-protocol"
    assert failure["context_id"] == "unchanged-parent-context"
    with pytest.raises(ValueError, match="no automatic retry"):
        episode.run("distribution")


@pytest.mark.parametrize("reason", ["UUID changed", "deadline", "stop requested"])
def test_admission_failure_has_no_cuda_model_or_result_and_preserves_parent(episode, reason):
    previous = worker.base.control
    episode.flags.admission_failure = RuntimeError(reason)
    with pytest.raises(RuntimeError, match=reason):
        episode.run("distribution")
    assert worker.base.control is previous
    assert not episode.cuda.initialized and episode.cuda.resets == 0
    assert not any(row[0] == "model_load" for row in episode.calls)
    assert not (episode.directory / "distribution/result/record.json").exists()
    failure = json.loads((episode.directory / "distribution/failure/record.json").read_text())
    assert failure["protocol_id"] == "new-protocol"
    assert failure["context_id"] == "unchanged-parent-context"
    assert failure["resources"] is None and failure["automatic_retry"] is False
    assert episode.marker.read_bytes() == episode.original_bytes


def test_student_mutation_cannot_be_accepted_as_completed(episode):
    episode.flags.mutate_model = True
    with pytest.raises(ValueError, match="mutated real Student"):
        episode.run("distribution")
    assert not (episode.directory / "distribution/result/record.json").exists()


def test_final_resource_gate_is_not_relaxed(episode):
    episode.flags.resource_failure = "model_released.after_cleanup"
    with pytest.raises(ValueError, match="final resource"):
        episode.run("distribution")
    assert not (episode.directory / "distribution/result/record.json").exists()
    failure = json.loads((episode.directory / "distribution/failure/record.json").read_text())
    assert failure["resources"]["all_gates_passed"] is False


def test_first_pilot_boundary_cannot_be_expanded(episode):
    episode.context["training_stop_step"] = 1490
    with pytest.raises(ValueError, match="one-step SFT boundary"):
        episode.run("train")
    assert not episode.cuda.initialized


def test_future_context_uses_its_own_payloads_without_parent_alias(episode):
    episode.flags.inherited = False
    for stage in ("virtual_point", "replay_R3"):
        episode.payloads[episode.directory / stage / "payload"] = episode.payloads[
            episode.origin / stage / "payload"
        ]
    result = episode.run("distribution")
    assert result["inherited_context"] is False
    assert all(
        row[1].is_relative_to(episode.directory)
        for row in episode.calls
        if row[0] == "read_payload"
    )


def test_worker_rejects_unsealed_entry_file_before_loading_sources(episode, monkeypatch):
    monkeypatch.setattr(worker, "__file__", str(episode.root / "unsealed.py"))
    with pytest.raises(ValueError, match="frozen recovery worker"):
        episode.run("distribution")
    assert not episode.calls and not episode.cuda.initialized


def test_recovery_entry_has_one_peak_reset_and_reuses_all_parent_math_phases():
    source = Path(__file__).parents[1] / "scripts/finqa_v38_worker.py"
    tree = ast.parse(source.read_text())
    attrs = [
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    ]
    assert attrs.count("reset_peak_memory_stats") == 1
    for phase in ("execute_shard", "execute_virtual", "execute_replay", "execute_distribution"):
        assert attrs.count(phase) == 1
    assert not {"outer_update", "run_until", "load_saved_gradient"}.intersection(attrs)
