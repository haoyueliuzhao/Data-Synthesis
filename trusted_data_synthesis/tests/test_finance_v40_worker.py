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
worker = importlib.import_module("finqa_v40_worker")
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
    root = parent / "recovery_02"
    origin = parent / "contexts/seed389/full/step0298_outer"
    new_context = root / "contexts/seed389/full/step0298_outer"
    origin.mkdir(parents=True)
    marker = origin / "parent_evidence.json"
    marker.write_text('{"status":"PARENT_EVIDENCE_ONLY"}\n')
    original_bytes = marker.read_bytes()
    state = dict(
        seed=389,
        arm="Full",
        step=298,
        outer_done=[],
        pi={"t": {"a": 0.4, "b": 0.6}},
        prior={"t": {"a": 0.5, "b": 0.5}},
        parameters={"w": [1.0]},
        optimizer={"step": 298},
        rng={"python": 123},
        buffers={},
        schedule={"id": "actual-schedule"},
    )
    training_root = tmp_path / "original_training"
    arm_root = training_root / "seed389/arms/full"
    context = dict(
        id="unchanged-parent-context",
        seed=389,
        arm="Full",
        step=298,
        due_outer=True,
        training_root=str(training_root),
        arm_root=str(arm_root),
        checkpoint={"path": str(arm_root / "training/step0298_step")},
        pre_state_digest=digest(state),
        branch=dict(contribution_only=False, b_N=0.2, parameters={"original": 1}),
        feedback=dict(mode="sealed_existing", expected_point_id="actual-point"),
    )
    plan = dict(
        id="new-protocol",
        allowed_gpu_indices=list(worker.admission.ALLOWED_GPUS),
        gpu_uuids=dict(worker.admission.GPU_UUIDS),
        recovery_pilot=dict(seed=389, arm="Full", step=298, training_stop_step=299),
    )
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

        def signal_handler(self, signum, _frame):
            self.requested = True
            self.reason = f"signal:{signum}"

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
            self.root, self.seed, self.arm = Path(kwargs["root"]), 389, "Full"
            self.step_index, self.final_step = 298, 1490
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
        assert cuda.initialized and seed == 389
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
        if flags.inherited and stage not in {"replay_R3", "distribution", "train"}:
            return origin / stage
        return directory / stage

    def require_upstream(directory, actual_context, actual_plan, stage, actual_control):
        assert directory == new_context and actual_context is context and actual_plan is plan
        assert actual_control is worker.control and not cuda.initialized
        calls.append(("checked_upstream", stage))
        if flags.upstream_failure:
            raise ValueError("parent result or real exit invalid")

    def admit(actual_plan, stage, gpu, directory, deadline, torch, stop, *, context_id, **readers):
        assert actual_plan is plan and gpu == 4 and torch.cuda is cuda
        assert readers == {
            key: getattr(worker.control, key)
            for key in ("inventory", "host_memory", "process_memory", "birth")
        }
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
    payloads[new_context / "replay_R3/payload"] = replay

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
    monkeypatch.setattr(worker, "__file__", str(root / "implementation/finqa_v40_worker.py"))
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
    monkeypatch.setattr(worker.inheritance, "task_cache_overlay_binding", lambda *_args: None)
    monkeypatch.setattr(worker.inheritance, "replay_resume_binding", lambda *_args: {"cursor": 261})
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
        bundle=bundle,
        run=lambda stage: worker.run(root, new_context, stage, 4, time.time() + 3600),
    )


def test_pending_distribution_keeps_full_point_parent_files_and_new_protocol(episode):
    original_context = copy.deepcopy(episode.context)
    result = episode.run("distribution")
    assert result["protocol_id"] == "new-protocol"
    assert result["context_id"] == episode.context["id"]
    assert result["model_optimizer_rng_buffers_unchanged"] is True
    assert result["optimizer_steps"] == result["replayed_responses"] == 0
    assert result["resources"]["maximum_allocated_bytes"] == 76 * 1024**3
    assert result["resources"]["minimum_device_free_bytes"] == 2 * 1024**3
    assert result["resources"]["peak_resets_after_model_loading_begins"] == 0
    assert episode.context == original_context
    assert episode.marker.read_bytes() == episode.original_bytes
    assert list(episode.origin.iterdir()) == [episode.marker]


def test_full389_outer_once_and_one_sft_step299_without_rewriting_context(episode):
    original_context = copy.deepcopy(episode.context)
    episode.run("distribution")
    episode.cuda.initialized = False
    result = episode.run("train")
    driver = episode.drivers[-1]
    assert result["committed_step"] == 299
    assert result["actual_optimizer_steps"] == driver.steps == 1
    assert result["outer_done"] == [298]
    assert result["registered_training_stop_step"] == 299
    assert len(driver.commits) == 1 and driver.commits[0][0] == "outer"
    assert episode.context == original_context and "training_stop_step" not in episode.context
    assert result["execution_boundary_policy_protocol_id"] == episode.plan["id"]
    assert episode.marker.read_bytes() == episode.original_bytes


def test_failed_replay_gets_only_the_registered_resume_adapter(episode, monkeypatch):
    calls = []

    def resumed(*args, **kwargs):
        calls.append((args, kwargs))
        assert kwargs["resume"] == {"cursor": 261}
        assert kwargs["control"] is worker.control and kwargs["original_worker"] is worker.base
        assert kwargs["protocol_id"] == episode.plan["id"]
        assert args[1] is episode.context
        return dict(
            complete_replay=True,
            response_count=447,
            restored_completed_responses=261,
            replayed_responses=186,
            actual_new_response_calls=186,
            inherited_response_count=261,
            cumulative_complete_response_count=447,
        )

    monkeypatch.setattr(worker.resumed_replay, "execute_replay", resumed)
    result = episode.run("replay_R3")
    assert len(calls) == 1
    assert result["replayed_responses"] == 186 and result["restored_completed_responses"] == 261
    assert result["response_count"] == 447 and result["new_sampling_calls"] == 0


def test_sigterm_pause_records_receipt_boundary_and_never_retries(episode, monkeypatch):
    class ReplayPaused(RuntimeError):
        checkpoint_record = {"cursor": 263, "response_prefix_complete": True}
        report = {"pause_reason": "signal:15", "completed_responses": 263}

    def pause(*args, **_kwargs):
        stop = args[-1]
        stop.request.signal_handler(15, None)
        raise ReplayPaused("complete response 263")

    monkeypatch.setattr(worker.resumed_replay, "execute_replay", pause)
    with pytest.raises(ReplayPaused):
        episode.run("replay_R3")
    failure = json.loads((episode.directory / "replay_R3/failure/record.json").read_text())
    assert failure["failure_classification"] == "COOPERATIVE_RESPONSE_BOUNDARY_PAUSE"
    assert failure["stop_evidence"]["stop_reason"] == "signal:15"
    assert failure["stop_evidence"]["received_signals"][0]["signal_number"] == 15
    assert failure["stop_evidence"]["sender_attribution"] == "unknown"
    assert failure["durable_replay_checkpoint"]["cursor"] == 263
    assert failure["automatic_retry"] is False
    with pytest.raises(ValueError, match="no automatic retry"):
        episode.run("replay_R3")


def test_numerical_failure_is_not_mislabeled_as_cooperative_pause(episode, monkeypatch):
    def fail(*_args, **_kwargs):
        raise ValueError("nonfinite original response gradient")

    monkeypatch.setattr(worker.resumed_replay, "execute_replay", fail)
    with pytest.raises(ValueError, match="nonfinite"):
        episode.run("replay_R3")
    failure = json.loads((episode.directory / "replay_R3/failure/record.json").read_text())
    assert failure["failure_classification"] == "STAGE_FAILURE_NO_RETRY"
    assert failure["stop_evidence"]["received_signals"] == []
    assert failure["durable_replay_checkpoint"] is None


@pytest.mark.parametrize("stage", ["shard00", "shard03", "virtual_point"])
def test_completed_parent_phase_cannot_be_dispatched(episode, stage):
    with pytest.raises(ValueError, match="completed parent stages"):
        episode.run(stage)
    assert not episode.calls and not episode.cuda.initialized


def test_pilot_cannot_expand_registered_training_boundary(episode):
    episode.plan["recovery_pilot"]["training_stop_step"] = 596
    with pytest.raises(ValueError, match="boundary changed"):
        episode.run("distribution")
    assert not episode.cuda.initialized


def test_other_context_has_no_pilot_boundary_override(episode):
    other = dict(episode.context, seed=251, step=596)
    assert worker.execution_context(other, episode.plan) is other


def test_frozen_shell_keeps_one_preload_peak_reset_and_original_mathematical_calls():
    source = Path(__file__).parents[1] / "scripts/finqa_v40_worker.py"
    attrs = [
        node.func.attr
        for node in ast.walk(ast.parse(source.read_text()))
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    ]
    assert attrs.count("reset_peak_memory_stats") == 1
    for phase in ("execute_shard", "execute_virtual", "execute_replay", "execute_distribution"):
        assert attrs.count(phase) == 1
    assert not {"outer_update", "run_until", "load_saved_gradient"}.intersection(attrs)
