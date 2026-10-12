"""Real CPU tensor/checkpoint continuation; no GPU, model generation or API calls."""

import copy
import hashlib
import importlib
import json
import shutil
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
import torch
from test_finance_v19_replay_state import Backend, fixture

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
subject = importlib.import_module("finqa_v40_replay")
v32 = importlib.import_module("finqa_v32_replay_variants")
optimized = importlib.import_module("finqa_v19_optimized_replay")
state_module = importlib.import_module("finqa_v19_replay_state")
R3_VERSION = "v33_r2_independent_nonkv_activation_residency.v1"
PROFILE = "cpu-original-context-identity"


def require(condition, message):
    if not condition:
        raise ValueError(message)


def entry(path):
    raw = Path(path).read_bytes()
    return dict(path=str(path), sha256=hashlib.sha256(raw).hexdigest(), id=json.loads(raw)["id"])


def publish(path, body):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    body = dict(body, id="cpu-only-audit")
    with path.open("x") as stream:
        json.dump(body, stream)
    return body


CONTROL = SimpleNamespace(require=require, entry=entry, publish=publish, now=lambda: "CPU_TEST")


def run(f, root, backend, *, function=None, rewards=None, **kwargs):
    if function is None:
        function = optimized.bind_dependencies(v32.feedback_gradient, BACKEND_VERSION=R3_VERSION)
    return function(
        f.cohort,
        f.rewards if rewards is None else rewards,
        f.local.model,
        f.local.parameters,
        root=root,
        profile_id=PROFILE,
        backend_factory=lambda *_args: backend,
        backend_identity={"variant": "R3", "version": R3_VERSION, "cpu_test_backend": True},
        rng_restore_source={"kind": "cpu_fixture", "id": "original-rng-state"},
        cpu_test=True,
        **kwargs,
    )


@pytest.fixture(scope="module")
def prefix(tmp_path_factory):
    root = tmp_path_factory.mktemp("v40-real-tensor-prefix")
    local, cohort, _ = fixture(700)
    f = SimpleNamespace(local=local, cohort=cohort, rewards=[1] * 447 + [0] * 253, root=root)
    baseline_backend = Backend()
    f.expected, f.baseline = run(f, root / "baseline", baseline_backend)
    assert baseline_backend.calls == 447
    first = Backend()
    with pytest.raises(v32.ReplayPaused):
        run(f, root / "parent", first, pause_after_response=261)
    assert first.calls == 261
    f.source = root / "parent/response000261"
    f.record = json.loads((f.source / "record.json").read_text())
    f.saved_state = torch.load(f.source / "state.pt", map_location="cpu", weights_only=False)
    return f


@pytest.fixture
def continuation(prefix, tmp_path):
    source = tmp_path / "read_only_parent/response000261"
    shutil.copytree(prefix.source, source)
    resume = dict(
        checkpoint_directory=str(source),
        checkpoint=entry(source / "record.json"),
        state=dict(path=str(source / "state.pt"), sha256=prefix.record["state_sha256"]),
        inherited_response_count=261,
        total_response_count=447,
        remaining_response_count=186,
        binding=copy.deepcopy(prefix.record["binding"]),
    )
    destination = tmp_path / "new_stage/checkpoints"
    return SimpleNamespace(
        fixture=prefix,
        source=source,
        resume=resume,
        destination=destination,
        parent_before={
            p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in source.iterdir()
        },
    )


def resumed(f, backend, *, rewards=None):
    storage = subject.checkpoint_storage(
        state_module,
        f.resume,
        f.destination,
        control=CONTROL,
        context_id=PROFILE,
        protocol_id="new-cpu-protocol",
    )
    function = optimized.bind_dependencies(
        v32.feedback_gradient, BACKEND_VERSION=R3_VERSION, state=storage
    )
    assert function.__code__ is v32.feedback_gradient.__code__
    return run(f.fixture, f.destination, backend, function=function, rewards=rewards)


def test_261_real_tensor_prefix_plus_186_calls_is_bitwise_full447(continuation):
    f = continuation
    backend = Backend()
    actual, report = resumed(f, backend)
    assert backend.calls == 186
    assert report["restored_completed_responses"] == 261
    assert report["accounting"]["responses_replayed"] == 447
    assert report["response_checkpoint_binding"]["response_count"] == 447
    assert report["denominator"] == 700
    assert report["new_sampling_calls"] == report["optimizer_steps_performed"] == 0
    assert all(torch.equal(actual[name], value) for name, value in f.fixture.expected.items())
    complete = json.loads((f.destination / "response000447/record.json").read_text())
    assert complete["full_replay_complete"] is True
    assert complete["binding"] == f.resume["binding"]
    actual_state = torch.load(
        f.destination / "response000447/state.pt", map_location="cpu", weights_only=False
    )
    assert all(torch.equal(actual_state["total"][name], value) for name, value in actual.items())
    assert {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in f.source.iterdir()} == (
        f.parent_before
    )
    audit = json.loads((f.destination.parent / "inherited_prefix/record.json").read_text())
    assert audit["actual_tensor_bytes_and_state_digest_verified"] is True
    assert audit["restored_runtime_rng_verified"] is True
    assert audit["next_response_ordinal"] == 262
    assert audit["parent_files_written"] is False


@pytest.mark.parametrize("field", ["reward_sha256", "response_order_sha256", "point_id"])
def test_changed_registered_binding_is_rejected_before_backend(continuation, field):
    f, backend = continuation, Backend()
    f.resume["binding"][field] = "changed"
    with pytest.raises(ValueError, match="binding"):
        resumed(f, backend)
    assert backend.calls == 0


def test_changed_current_rewards_cannot_use_old_prefix(continuation):
    f, backend = continuation, Backend()
    rewards = list(f.fixture.rewards)
    rewards[0], rewards[-1] = 0, 1
    with pytest.raises(ValueError, match="binding"):
        resumed(f, backend, rewards=rewards)
    assert backend.calls == 0


def test_changed_actual_tensor_bytes_are_rejected_before_backend(continuation):
    f, backend = continuation, Backend()
    with (f.source / "state.pt").open("ab") as stream:
        stream.write(b"tamper")
    with pytest.raises(ValueError, match="bytes changed"):
        resumed(f, backend)
    assert backend.calls == 0


def test_changed_restored_rng_is_rejected_before_backend(continuation):
    f, backend = continuation, Backend()
    original = torch.get_rng_state().clone()
    try:
        torch.rand(1)
        with pytest.raises(ValueError, match="RNG differs"):
            resumed(f, backend)
        assert backend.calls == 0
    finally:
        torch.set_rng_state(original)


def test_existing_new_response_cannot_be_used_for_automatic_retry(continuation):
    f, backend = continuation, Backend()
    (f.destination / "response000262").mkdir(parents=True)
    with pytest.raises(ValueError, match="no automatic retry"):
        resumed(f, backend)
    assert backend.calls == 0


def test_parent_reader_cannot_be_redirected_to_a_new_context(continuation):
    f = continuation
    storage = subject.checkpoint_storage(
        state_module,
        f.resume,
        f.destination,
        control=CONTROL,
        context_id="different-context",
        protocol_id="new-cpu-protocol",
    )
    with pytest.raises(ValueError, match="binding"):
        storage.ReplayCheckpoints(f.destination, f.resume["binding"], f.fixture.local.parameters)


def test_registered_resume_does_not_allow_other_cursor_or_dose(continuation):
    f = continuation
    f.resume["inherited_response_count"] = 260
    with pytest.raises(ValueError, match="only the registered"):
        subject.checkpoint_storage(
            state_module,
            f.resume,
            f.destination,
            control=CONTROL,
            context_id=PROFILE,
            protocol_id="new-cpu-protocol",
        )
