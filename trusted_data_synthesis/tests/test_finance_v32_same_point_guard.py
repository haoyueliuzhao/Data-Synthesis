"""CPU/mock-only fail-closed checks; no real feedback, GPU, API or scoring."""

import copy
import importlib
import json
import pickle
import sys
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
guard = importlib.import_module("finqa_v32_same_point_guard")


class Identity:
    def __init__(self, value):
        self.value = value

    def model_dump(self, **_):
        return self.value


class Cohort:
    def __init__(
        self, episodes, identity, denominator, source_manifest_sha256, registered_episode_keys
    ):
        self.episodes, self.identity, self.denominator = episodes, identity, denominator
        self.registered_episode_keys = registered_episode_keys
        self.body = dict(
            identity=identity.model_dump(),
            denominator=denominator,
            source_manifest_sha256=source_manifest_sha256,
            registered_episode_keys=registered_episode_keys,
        )
        self.seal_sha256 = guard._digest(self.body)

    def model_dump(self, **kwargs):
        result = self.body | dict(seal_sha256=self.seal_sha256)
        if "episodes" not in kwargs.get("exclude", ()):
            result["episodes"] = [ep.task_id for ep in self.episodes]
        return result


def put(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def rebind(manifest):
    manifest["id"] = guard._digest({k: v for k, v in manifest.items() if k != "id"})
    return manifest


@pytest.fixture
def fixture(tmp_path, monkeypatch):
    state = dict(
        seed=137,
        arm="C-only",
        step=1192,
        pool_id="pool",
        outer_done=[298, 596, 894],
        parameters={"p": [1]},
        buffers={"b": [2]},
        optimizer={"Adam": [3]},
        rng={"torch": [4]},
        schedule={"schedule_sha256": "schedule"},
        pi={"task": [0.5, 0.5]},
        adapter_binding={"kind": "adapter"},
        frozen_base_digest="base",
        execution_plan={"sharing_split_step": 596},
    )
    theta, G = {"p": [5]}, {"p": [6]}
    calls = dict(installs=0, reads=0)

    class Original:
        def collect(self, *_args, **_kwargs):
            pytest.fail("original collector/publisher/provider must never be called")

    @contextmanager
    def install(_model, value):
        calls["installs"] += 1
        yield value

    v8 = SimpleNamespace(
        digest=guard._digest,
        parameter_digest=guard._digest,
        _tree_digest=guard._digest,
        LocalFeedbackCollector=Original,
        installed_point=install,
        _json=lambda value: json.dumps(value).encode(),
        episode_key=lambda ep: str(ep.config.seed) + ":" + ep.task_id,
        seal_feedback_cohort=lambda episodes, **kwargs: Cohort(episodes, **kwargs),
    )
    rt = SimpleNamespace(
        v8=v8,
        torch=SimpleNamespace(load=lambda path, **_kwargs: pickle.loads(Path(path).read_bytes())),
    )
    monkeypatch.setattr(guard, "_runtime", lambda _rt=None: rt)
    point = guard.recompute_point_id(state, theta_bar=theta, G=G)
    monkeypatch.setattr(guard, "TARGETS", ((137, "c_only", 1192, "step", point),))
    branch = tmp_path / "seed137/arms/c_only"
    root, checkpoint = branch / "feedback" / guard._digest(point), branch / "training/step1192_step"
    identity = Identity(
        dict(point_id=point, parameter_digest=guard._digest(theta), model_id="model")
    )
    original = Original()
    original.root, original.manifest = root.parent, {"dataset": "CPU-mock"}
    original.role_plan, original.seeds = {"id": "roles"}, (11, 29)
    original.model_id = "model"
    original.tasks = [SimpleNamespace(task_id=f"t{i}") for i in range(350)]
    intent = dict(
        point_id=point,
        identity=identity.model_dump(),
        source_manifest_sha256=guard._digest(original.manifest),
        role_plan_id="roles",
        seeds=[11, 29],
        task_ids=[t.task_id for t in original.tasks],
        denominator=700,
    )
    put(root / "intent/record.json", intent)
    episode_parts = []
    for index, seed in enumerate(original.seeds):
        part = [
            SimpleNamespace(task_id=t.task_id, config=SimpleNamespace(seed=seed), provider=identity)
            for t in original.tasks
        ]
        episode_parts.append(part)
        put(
            root / f"draw{index}/run.json",
            dict(
                registered_denominator=350,
                config={"seed": seed},
                provider=intent["identity"],
                source_manifest_sha256=intent["source_manifest_sha256"],
                role_plan_id="roles",
            ),
        )
        put(root / f"draw{index}/generation_seal/seal.json", dict(registered_denominator=350))

    def sealed(draw):
        calls["reads"] += 1
        return (
            json.loads((draw / "run.json").read_text()),
            json.loads((draw / "generation_seal/seal.json").read_text()),
            episode_parts[int(draw.name[-1])],
        )

    rt.storage = SimpleNamespace(sealed_episodes=sealed)
    v8.local_model_identity = lambda _model, _tokenizer, **kw: Identity(
        identity.value
        | dict(parameter_digest=guard._digest(kw["parameter_tensors"]), point_id=kw["point_id"])
    )
    cohort = Cohort(
        episode_parts[0] + episode_parts[1],
        identity,
        700,
        intent["source_manifest_sha256"],
        [v8.episode_key(ep) for part in episode_parts for ep in part],
    )
    put(root / "cohort_seal/record.json", cohort.model_dump())
    rewards = [i % 2 for i in range(700)]
    put(
        root / "native_rewards/record.json",
        dict(
            cohort_seal_sha256=cohort.seal_sha256,
            rewards=rewards,
            scores=[{"native": {"execution_accuracy": r}} for r in rewards],
        ),
    )
    checkpoint.mkdir(parents=True)
    (checkpoint / "state.pt").write_bytes(pickle.dumps(state))
    put(
        checkpoint / "record.json",
        dict(
            seed=137,
            arm="C-only",
            step=1192,
            phase="step",
            pool_id="pool",
            schedule_sha256="schedule",
            actual_state_digest=guard._digest(state),
            state_sha256=guard._file_ref(checkpoint / "state.pt")["sha256"],
        ),
    )
    manifest = guard.build_manifest(checkpoint, root, expected_point_id=point)
    calls.update(installs=0, reads=0)
    return SimpleNamespace(
        root=root,
        checkpoint=checkpoint,
        point=point,
        state=state,
        theta=theta,
        G=G,
        rt=rt,
        original=original,
        manifest=manifest,
        calls=calls,
        episodes=episode_parts,
        rewards=rewards,
    )


def test_four_fixed_targets_have_exact_three_pending_and_one_completed():
    targets = guard.registered_targets()
    assert len(targets) == 4
    assert [x["purpose"] for x in targets].count("pending_outer_binding_only") == 3
    assert targets[-1]["name"] == "seed137_c_only_outer298"
    assert all(
        Path(x["feedback_root"]).name == guard._digest(x["expected_point_id"]) for x in targets
    )


def test_manifest_and_read_only_adapter_never_publish_or_rescore(fixture):
    f = fixture
    before = {str(p): p.read_bytes() for p in f.root.rglob("*") if p.is_file()}
    collector = guard.ReadOnlySamePointCollector(f.original, f.manifest, pre_state=f.state, G=f.G)
    cohort, rewards = collector.collect(object(), object(), f.theta, point_id=f.point)
    assert cohort.denominator == len(rewards) == 700 and rewards == f.rewards
    assert f.calls == dict(installs=1, reads=2)
    assert f.manifest["pending_point_recomputation_required"]
    assert f.manifest["new_sampling_allowed"] is False
    assert before == {str(p): p.read_bytes() for p in f.root.rglob("*") if p.is_file()}


@pytest.mark.parametrize(
    "relative",
    [
        "intent/record.json",
        "draw0/generation_seal/seal.json",
        "draw1/generation_seal/seal.json",
        "cohort_seal/record.json",
        "native_rewards/record.json",
    ],
)
def test_missing_seal_cannot_create_or_sample(fixture, relative):
    f = fixture
    (f.root / relative).unlink()
    with pytest.raises(ValueError, match="required sealed file is missing"):
        guard.check_recomputed_point(f.manifest, f.point)
    assert f.calls == dict(installs=0, reads=0)
    assert not (f.root / relative).exists()


def test_point_drift_rejected_before_install_or_feedback_read(fixture):
    f = fixture
    collector = guard.ReadOnlySamePointCollector(f.original, f.manifest, pre_state=f.state, G=f.G)
    with pytest.raises(ValueError, match="caller point_id differs"):
        collector.collect(None, None, {"p": [999]}, point_id=f.point)
    assert f.calls == dict(installs=0, reads=0)


def test_actual_new_point_not_admitted_even_when_caller_matches(fixture):
    f = fixture
    collector = guard.ReadOnlySamePointCollector(f.original, f.manifest, pre_state=f.state, G=f.G)
    changed = {"p": [999]}
    point = guard.recompute_point_id(f.state, theta_bar=changed, G=f.G)
    with pytest.raises(ValueError, match="point_id drift"):
        collector.collect(None, None, changed, point_id=point)
    assert f.calls == dict(installs=0, reads=0)
    assert not (f.root.parent / guard._digest(point)).exists()


def test_new_root_forbidden_without_creation(fixture):
    f = fixture
    new = f.root.parent / "new"
    with pytest.raises(ValueError, match="new feedback root forbidden"):
        guard.check_recomputed_point(f.manifest, f.point, new)
    assert not new.exists()


@pytest.mark.parametrize("field", ["rng", "optimizer", "pi", "buffers", "schedule", "parameters"])
def test_full_state_drift_detected_before_install(fixture, field):
    f = fixture
    collector = guard.ReadOnlySamePointCollector(f.original, f.manifest, pre_state=f.state, G=f.G)
    f.state[field] = {"changed": True}
    with pytest.raises(ValueError, match="pre-outer state mutated"):
        collector.collect(None, None, f.theta, point_id=f.point)
    assert f.calls == dict(installs=0, reads=0)


def test_G_drift_not_hidden_by_original_point_string(fixture):
    f = fixture
    collector = guard.ReadOnlySamePointCollector(f.original, f.manifest, pre_state=f.state, G=f.G)
    f.G["p"][0] += 1
    with pytest.raises(ValueError, match="caller point_id differs"):
        collector.collect(None, None, f.theta, point_id=f.point)
    assert f.calls == dict(installs=0, reads=0)


def test_exact_frozen_intent_comparison(fixture):
    f = fixture
    collector = guard.ReadOnlySamePointCollector(f.original, f.manifest, pre_state=f.state, G=f.G)
    f.original.seeds = (29, 11)
    with pytest.raises(ValueError, match="feedback intent changed"):
        collector.collect(None, None, f.theta, point_id=f.point)
    assert f.calls["reads"] == 0


@pytest.mark.parametrize("mutation", ["reward", "score", "cohort", "intent", "order"])
def test_sealed_content_or_order_mutation_rejected(fixture, mutation):
    f = fixture
    if mutation in ("reward", "score"):
        path = f.root / "native_rewards/record.json"
        data = json.loads(path.read_text())
        if mutation == "reward":
            data["rewards"][0] = True
        else:
            data["scores"][0]["native"]["execution_accuracy"] = 1
        put(path, data)
    elif mutation == "cohort":
        path = f.root / "cohort_seal/record.json"
        data = json.loads(path.read_text())
        data["seal_sha256"] = "changed"
        put(path, data)
    elif mutation == "intent":
        path = f.root / "intent/record.json"
        data = json.loads(path.read_text())
        data["role_plan_id"] = "changed"
        put(path, data)
    else:
        f.episodes[0].reverse()
    with pytest.raises(ValueError):
        guard.read_sealed_feedback(f.manifest)


def test_manifest_tampering_is_not_new_authorization(fixture):
    manifest = copy.deepcopy(fixture.manifest)
    manifest["point_id"] = "new"
    with pytest.raises(ValueError, match="manifest identity changed"):
        guard.check_recomputed_point(manifest, "new")
    manifest = copy.deepcopy(fixture.manifest)
    manifest["new_sampling_allowed"] = True
    with pytest.raises(ValueError, match="cannot authorize"):
        guard.check_recomputed_point(rebind(manifest), fixture.point)


def test_checkpoint_byte_change_rejected_before_sealed_read(fixture):
    f = fixture
    (f.checkpoint / "state.pt").write_bytes(b"corrupt CPU mock")
    with pytest.raises(ValueError, match="checkpoint bytes changed"):
        guard.build_manifest(f.checkpoint, f.root, expected_point_id=f.point)
    assert f.calls == dict(installs=0, reads=0)
