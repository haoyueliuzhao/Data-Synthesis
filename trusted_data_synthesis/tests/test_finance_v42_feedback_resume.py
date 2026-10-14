"""CPU-only original harness/provider recovery; no research responses or GPU."""

import asyncio
import copy
import importlib
import io
import json
import shutil
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
import torch
from test_finance_research_providers import Model, Tokenizer

from trusted_synthesis.core import immutable_artifacts as immutable
from trusted_synthesis.finance_research import contracts, harness, storage
from trusted_synthesis.finance_research import v8_training_driver as v8
from trusted_synthesis.finance_research.contracts import ModelIdentity, RunConfig
from trusted_synthesis.finance_research.datasets import adapt_finqa
from trusted_synthesis.finance_research.planning import build_role_plan
from trusted_synthesis.finance_research.providers import LocalTorchProvider, local_model_identity

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
f = importlib.import_module("finqa_v42_feedback_resume")


def put(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True))


def signed(value):
    return dict(value, id=f.digest(value))


@pytest.fixture
def meta(tmp_path):
    context_dir = tmp_path / "parent_context"
    root = tmp_path / "feedback" / f.digest(f.POINT_ID)
    context = dict(
        id=f.CONTEXT_ID,
        seed=389,
        arm="C-only",
        step=894,
        feedback=dict(mode="first_sampling", base_root=str(root.parent)),
    )
    put(context_dir / "context/record.json", context)
    payload_dir = context_dir / "virtual_point/computed_point/payload"
    put(
        payload_dir / "record.json",
        dict(
            context_id=f.CONTEXT_ID,
            phase="virtual_point_values",
            actual_tensors_saved=True,
            state_sha256="CPU_FIXTURE_ONLY",
        ),
    )
    provider = dict(point_id=f.POINT_ID, parameter_digest="CPU_FIXTURE_ONLY")
    intent = dict(
        point_id=f.POINT_ID,
        denominator=700,
        seeds=[11, 29],
        task_ids=list(range(350)),
        identity=provider,
        role_plan_id="CPU_ROLE",
        source_manifest_sha256="CPU_SNAPSHOT",
    )
    put(root / "intent/record.json", intent)
    for draw, count in ((0, 350), (1, 100)):
        keys = [f"draw{draw}episode{i}" for i in range(350)]
        if draw == 1:
            keys[100] = f.UNKNOWN_KEY
        config = dict(seed=[11, 29][draw], tier="VTDO_FEEDBACK", role="feedback")
        run = signed(
            dict(
                provider=provider,
                config=config,
                registered_denominator=350,
                episode_keys=keys,
                tasks=[f"task{i}" for i in range(350)],
                role_plan_id="CPU_ROLE",
                source_manifest_sha256="CPU_SNAPSHOT",
            )
        )
        put(root / f"draw{draw}/run.json", run)
        rows = []
        for key in keys[:count]:
            episode = dict(
                provider=provider,
                config=config,
                all_provider_calls_settled=True,
                actual_model_calls=1,
                turns=[
                    dict(
                        receipt=dict(
                            identity=provider,
                            raw_generated_token_ids=[1, 2],
                            sampled_token_logprobs=[-1.0, -2.0],
                        )
                    )
                ],
            )
            path = root / f"draw{draw}/episodes/{key}/episode.json"
            put(path, episode)
            put(
                root / f"draw{draw}/events/{key}/000000/event.json",
                dict(kind="episode_started", step=None, payload={}),
            )
            put(
                root / f"draw{draw}/events/{key}/000001/event.json",
                dict(kind="episode_completed", step=None, payload=episode),
            )
            rows.append(
                dict(
                    key=key, path=f"episodes/{key}/episode.json", sha256=f.file_ref(path)["sha256"]
                )
            )
        if draw == 0:
            put(
                root / "draw0/generation_seal/seal.json",
                signed(
                    dict(
                        run_id=run["id"],
                        complete=True,
                        all_provider_calls_settled=True,
                        registered_denominator=350,
                        episodes=rows,
                    )
                ),
            )
        else:
            put(
                root / f"draw1/events/{f.UNKNOWN_KEY}/000000/event.json",
                dict(kind="episode_started", step=None, payload={}),
            )
            request = dict(
                messages=[dict(role="user", content="CPU request")], tools=[], config=config
            )
            put(
                root / f"draw1/events/{f.UNKNOWN_KEY}/000001/event.json",
                dict(
                    kind="model_call_intent",
                    step=0,
                    payload=dict(request, request_sha256=f.digest(request)),
                ),
            )
    return SimpleNamespace(
        context=context, directory=context_dir, root=root, output=tmp_path / "newview"
    )


def test_inspect_exact450_one_unknown249_and_overlay_preserves_parent(meta):
    binding = f.inspect_partial_feedback(meta.directory)
    assert binding["inherited_episode_count"] == len(binding["inherited_episodes"]) == 450
    assert len(binding["first_time_episode_keys"]) == 249
    assert binding["unknown_request"]["index"] == 100
    binding["new_feedback_base_root"] = str(meta.output)
    target = f.prepare_feedback_overlay(binding, meta.context, immutable=immutable)
    assert len(list(target.glob("draw*/episodes/*/episode.json"))) == 450
    assert not (target / f"draw1/events/{f.UNKNOWN_KEY}").exists()
    assert (meta.root / f"draw1/events/{f.UNKNOWN_KEY}/000001/event.json").is_file()
    for reference in binding["inherited_files"]:
        assert f.read_ref(reference) == (target / reference["relative"]).read_bytes()
    assert (
        f.read(meta.output / "unreturned_request_disposition/record.json")["maximum_reexecutions"]
        == 1
    )
    with pytest.raises(ValueError, match="already exists"):
        f.prepare_feedback_overlay(binding, meta.context, immutable=immutable)


@pytest.mark.parametrize(
    "mutation", ["extra_episode", "extra_event", "missing_episode", "reward", "receipt", "seal"]
)
def test_inspection_rejects_changed_coverage_or_settlement(meta, mutation):
    if mutation == "extra_episode":
        put(meta.root / "draw1/episodes/extra/episode.json", {})
    elif mutation == "extra_event":
        put(meta.root / f"draw1/events/{f.UNKNOWN_KEY}/000002/event.json", {})
    elif mutation == "missing_episode":
        (meta.root / "draw1/episodes/draw1episode0/episode.json").unlink()
    elif mutation == "reward":
        put(meta.root / "native_rewards/record.json", {})
    elif mutation == "receipt":
        path = meta.root / "draw1/episodes/draw1episode0/episode.json"
        value = f.read(path)
        value["all_provider_calls_settled"] = False
        put(path, value)
    else:
        path = meta.root / "draw0/generation_seal/seal.json"
        value = f.read(path)
        value["complete"] = False
        put(path, value)
    with pytest.raises((ValueError, KeyError)):
        f.inspect_partial_feedback(meta.directory)


@pytest.mark.parametrize("mutation", ["coordinate", "dose", "source", "overlap"])
def test_binding_rejects_alias_dose_or_source_mutation(meta, mutation):
    binding = f.inspect_partial_feedback(meta.directory)
    binding["new_feedback_base_root"] = str(meta.output)
    if mutation == "coordinate":
        binding["point_id"] = "other"
    elif mutation == "dose":
        binding["new_completed_episodes"] = 700
    elif mutation == "source":
        reference = binding["inherited_files"][1]
        Path(reference["path"]).write_text("changed")
    else:
        binding["new_feedback_base_root"] = str(meta.root)
    with pytest.raises(ValueError):
        f.prepare_feedback_overlay(binding, meta.context, immutable=immutable)


@pytest.fixture
def execution(tmp_path, monkeypatch):
    records = [
        dict(
            id=f"V42_CPU_{i}/2020/page_1.pdf-1",
            filename=f"V42_CPU_{i}/2020/page_1.pdf",
            pre_text=["USD"],
            post_text=[],
            table=[["Year", "Revenue"], ["2020", "8"], ["2019", "2"]],
            qa=dict(question="Increase?", exe_ans=6, program="subtract(8, 2)", gold_inds={}),
        )
        for i in range(3)
    ]
    bundles = adapt_finqa(records, split="test", revision="v42-CPU-only")
    snapshot, old, new = tmp_path / "snapshot", tmp_path / "old", tmp_path / "new"
    storage.import_snapshot(bundles, snapshot, source={"CPU_TEST_ONLY": True})
    plan = build_role_plan([b.public for b in bundles], [b.lineage for b in bundles])
    model, tokenizer = Model(), Tokenizer()
    # Plain text ends the fixture in one original harness turn, without scoring.
    tokenizer.decode = lambda *a, **k: "CPU fixture plain response"
    identity = local_model_identity(model, tokenizer, model_id="V42_CPU_ONLY", point_id="CPU_POINT")
    provider = LocalTorchProvider(model, tokenizer, identity)
    run = storage.prepare_run(
        snapshot,
        plan,
        old,
        role="test",
        config=RunConfig(
            role="test",
            seed=29,
            max_steps=2,
            max_new_tokens=8,
            temperature=1.0,
            harness_id="bigfinance-derived-vtdo-v7",
            submission_profile="finqa-public-reasoning-v2",
        ),
        identity=identity,
    )
    real_sink = storage.EventSink
    unknown = run["episode_keys"][1]
    monkeypatch.setattr(f, "UNKNOWN_KEY", unknown)

    class KillBeforeSecondCall(real_sink):
        def __call__(self, event):
            super().__call__(event)
            if self.directory.name == unknown and event["kind"] == "model_call_intent":
                raise InterruptedError("CPU simulated hard interruption after durable intent")

    with monkeypatch.context() as patch:
        patch.setattr(storage, "EventSink", KillBeforeSecondCall)
        with pytest.raises(InterruptedError):
            asyncio.run(storage.execute_run(old, provider))
    assert provider.actual_model_calls == 1
    new.mkdir()
    shutil.copy2(old / "run.json", new / "run.json")
    for part in ("events", "episodes"):
        shutil.copytree(old / part / run["episode_keys"][0], new / part / run["episode_keys"][0])
    events = sorted((old / "events" / unknown).glob("*/event.json"))
    binding = dict(
        unknown_request=dict(episode_key=unknown, old_intent=f.file_ref(events[-1])),
        first_time_episode_keys=run["episode_keys"][2:],
        registered_provider=identity.model_dump(mode="json"),
    )
    return SimpleNamespace(
        old=old,
        new=new,
        provider=provider,
        run=run,
        binding=binding,
        private=snapshot / "private.references.jsonl",
    )


def run_remaining(e, *, stop=lambda: False, boundary=lambda: None, record_reexecution=None):
    return asyncio.run(
        f.execute_remaining_draw(
            e.new,
            e.provider,
            e.binding,
            storage=storage,
            stop_requested=stop,
            boundary=boundary,
            record_reexecution=record_reexecution,
        )
    )


def test_original_harness_local_provider_only_remaining_requests_no_private_read(
    execution, monkeypatch
):
    e = execution
    before = torch.get_rng_state().clone()
    original_read = Path.read_bytes

    def guarded(path):
        assert path != e.private, "generation must not read private references"
        return original_read(path)

    monkeypatch.setattr(Path, "read_bytes", guarded)
    seal = run_remaining(e)
    assert seal["complete"] and seal["registered_denominator"] == 3
    assert e.provider.actual_model_calls == 3  # one inherited, exactly two new
    assert torch.equal(before, torch.get_rng_state())
    assert len(list((e.old / "episodes").glob("*/episode.json"))) == 1
    assert len(list((e.new / "episodes").glob("*/episode.json"))) == 3
    with pytest.raises(ValueError, match="coverage differs"):
        run_remaining(e)
    assert e.provider.actual_model_calls == 3


def test_unknown_request_change_rejected_before_provider_call(execution):
    e = execution
    intent = f.read(e.binding["unknown_request"]["old_intent"]["path"])
    intent["payload"]["request_sha256"] = "wrong"
    path = e.old.parent / "tampered_intent.json"
    put(path, intent)
    e.binding["unknown_request"]["old_intent"] = f.file_ref(path)
    with pytest.raises(ValueError, match="exact original request"):
        run_remaining(e)
    assert e.provider.actual_model_calls == 1


def test_stop_is_checked_before_starting_new_episode(execution):
    with pytest.raises(ValueError, match="complete episode boundary"):
        run_remaining(execution, stop=lambda: True)
    assert execution.provider.actual_model_calls == 1
    assert not (execution.new / "events" / execution.run["episode_keys"][1]).exists()


def test_new_episode_order_is_fixed(execution):
    execution.binding["first_time_episode_keys"] = ["not-the-registered-next-episode"]
    with pytest.raises(ValueError, match="out-of-order"):
        run_remaining(execution)
    assert execution.provider.actual_model_calls == 2


def test_unrelated_point_load_delegates_without_alias():
    marker = object()
    assert (
        f.load_feedback({}, {}, None, binding=None, control=None, original_loader=lambda *a: marker)
        is marker
    )


@pytest.mark.parametrize("mutation", [None, "pre_state", "theta", "shape", "bytes"])
def test_saved_cpu_tensor_restore_not_virtual_recomputation(meta, mutation):
    worker = importlib.import_module("finqa_v37_worker")
    context = meta.context
    pre_state = {"actual_pre_state": torch.tensor([3.0])}
    context.update(
        pre_state_digest=v8._tree_digest(pre_state),
        branch={"b_N": 0},
        parameter_spec=[dict(name="weight", shape=[1], dtype="torch.float32")],
    )
    put(meta.directory / "context/record.json", context)
    binding = f.inspect_partial_feedback(meta.directory)
    point = dict(
        G={"weight": torch.tensor([0.25])},
        theta_bar={"weight": torch.tensor([0.5])},
        update={"weight": torch.tensor([-0.5])},
        point_id=f.POINT_ID,
        pre_state_digest=context["pre_state_digest"],
        branch=context["branch"],
    )
    binding["registered_provider"]["parameter_digest"] = v8.parameter_digest(point["theta_bar"])
    if mutation == "pre_state":
        point["pre_state_digest"] = "another"
    elif mutation == "theta":
        point["theta_bar"]["weight"].add_(1)
    elif mutation == "shape":
        point["G"]["weight"] = torch.tensor([1.0, 2.0])
    payload_dir = Path(binding["computed_point_payload"])
    stream = io.BytesIO()
    torch.save(point, stream)
    state = payload_dir / "state.pt"
    state.write_bytes(stream.getvalue())
    record = signed(
        dict(
            schema="v37_actual_stage_payload.v1",
            context_id=context["id"],
            actual_tensors_saved=True,
            phase="virtual_point_values",
            state_bytes=state.stat().st_size,
            state_sha256=f.file_ref(state)["sha256"],
            state_digest=v8._tree_digest(point),
        )
    )
    put(payload_dir / "record.json", record)
    binding["computed_point_ref"] = f.file_ref(payload_dir / "record.json")
    binding["computed_point_state"] = f.file_ref(state)
    binding["id"] = f.digest({k: v for k, v in binding.items() if k != "id"})
    if mutation == "bytes":
        state.write_bytes(b"bad actual tensor bytes")
    bundle = SimpleNamespace(
        rt=SimpleNamespace(torch=torch, v8=v8),
        guard=SimpleNamespace(recompute_point_id=lambda *a, **k: f.POINT_ID),
    )
    if mutation:
        with pytest.raises(ValueError):
            f.restore_saved_point(binding, context, pre_state, bundle, original_worker=worker)
    else:
        restored = f.restore_saved_point(
            binding, context, pre_state, bundle, original_worker=worker
        )
        assert torch.equal(restored["theta_bar"]["weight"], torch.tensor([0.5]))
        assert all(t.device.type == "cpu" for t in restored["theta_bar"].values())


def test_unregistered_feedback_alias_cannot_bypass_original_root(meta):
    binding = f.inspect_partial_feedback(meta.directory)
    binding["new_feedback_base_root"] = str(meta.output)
    point = dict(
        feedback_root=str(meta.root), feedback_resume_binding_id=binding["id"], point_id=f.POINT_ID
    )
    with pytest.raises(ValueError, match="unregistered feedback path alias"):
        f.load_feedback(
            point,
            meta.context,
            None,
            binding=binding,
            control=None,
            original_loader=lambda *a: pytest.fail("must not waive original root gate"),
        )


@pytest.fixture
def production_v7_intents():
    """Exact production harness/profile/sampling knobs, zero provider calls."""
    public = adapt_finqa(
        [
            dict(
                id="V42_V7_CPU/2020/page_1.pdf-1",
                filename="V42_V7_CPU/2020/page_1.pdf",
                pre_text=["Synthetic CPU public input."],
                post_text=[],
                table=[["Year", "Revenue"], ["2020", "8"], ["2019", "2"]],
                qa=dict(question="Increase?", exe_ans=6, program="subtract(8, 2)", gold_inds={}),
            )
        ],
        split="test",
        revision="V42-v7-CPU-pre-call-only",
    )[0].public
    config = RunConfig(
        tier="VTDO_FEEDBACK",
        role="feedback",
        seed=29,
        max_steps=32,
        max_new_tokens=2048,
        context_limit=24576,
        temperature=1.0,
        top_p=1.0,
        top_k=0,
        harness_id="bigfinance-derived-vtdo-v7",
        submission_profile="finqa-public-reasoning-v2",
        local_tool_protocol="qwen2.5-native-tool-call-v1",
    )
    identity = ModelIdentity(
        backend="local_torch",
        model_id="CPU_NO_MODEL",
        point_id="CPU_ORIGINAL_POINT",
        parameter_digest="a" * 64,
        tokenizer_digest="b" * 64,
        chat_template_digest="c" * 64,
    )

    class HaltBeforeProvider(BaseException):
        pass

    class ProviderMustNotRun:
        actual_model_calls = 0
        calls = 0

        async def chat(self, *args, **kwargs):
            self.calls += 1
            raise BaseException("CPU pre-call test must never invoke a provider")

    provider = ProviderMustNotRun()
    provider.identity = identity

    def capture(validator=None):
        captured = []

        def sink(event):
            if event["kind"] == "model_call_intent":
                captured.append(event)
                if validator:
                    validator(event)
                raise HaltBeforeProvider()

        try:
            asyncio.run(harness.run_episode(public, provider, config, sink=sink))
        except HaltBeforeProvider:
            pass
        assert provider.calls == provider.actual_model_calls == 0
        assert len(captured) == 1
        return captured[0]

    return SimpleNamespace(old=capture(), capture=capture, identity=identity, provider=provider)


def test_actual_v7_production_intent_allows_fresh_audit_ids_before_provider(production_v7_intents):
    e = production_v7_intents
    mappings = []
    new = e.capture(
        lambda event: mappings.append(
            f.validate_reexecution_intent(
                e.old,
                event,
                contracts=contracts,
                registered_provider=e.identity.model_dump(mode="json"),
            )
        )
    )
    assert (
        new["payload"] != e.old["payload"]
    )  # Regression: the old whole-payload guard rejected this.
    assert new["payload"]["request_sha256"] == e.old["payload"]["request_sha256"]
    assert mappings[0]["scientific_request_identical"] is True
    assert mappings[0]["old_invocation_identity_reused"] is False
    assert mappings[0]["provider_call_has_not_started"] is True
    assert e.provider.calls == 0


@pytest.mark.parametrize(
    "mutation",
    [
        "messages",
        "tools",
        "config",
        "point_id",
        "parameter_digest",
        "attempt_index",
        "turn_index",
        "invalid_id",
        "outer_id",
        "fake_scope",
        "reuse_old_uuid",
        "old_invalid_id",
    ],
)
def test_v7_only_audit_uuid_differences_are_permitted(production_v7_intents, mutation):
    e = production_v7_intents
    old, new = copy.deepcopy(e.old), e.capture()
    payload = new["payload"]
    if mutation == "messages":
        payload["messages"][0]["content"] += " changed"
    elif mutation == "tools":
        payload["tools"] = []
    elif mutation == "config":
        payload["config"]["seed"] = 31
    elif mutation in {"point_id", "parameter_digest"}:
        payload["harness_invocation"][mutation] = "another-actual-point"
    elif mutation in {"attempt_index", "turn_index"}:
        payload["harness_invocation"][mutation] = 1
    elif mutation == "invalid_id":
        payload["harness_invocation"]["invocation_id"] = "invocation:" + "0" * 64
        payload["invocation_id"] = payload["harness_invocation"]["invocation_id"]
    elif mutation == "outer_id":
        payload["invocation_id"] = "invocation:" + "0" * 64
    elif mutation == "fake_scope":
        payload["harness_invocation"]["run_id"] = "not-an-ephemeral-scope"
    elif mutation == "reuse_old_uuid":
        payload["harness_invocation"] = copy.deepcopy(old["payload"]["harness_invocation"])
        payload["invocation_id"] = old["payload"]["invocation_id"]
    else:
        old["payload"]["harness_invocation"]["invocation_id"] = "bad"
        old["payload"]["invocation_id"] = "bad"
    if mutation in {"messages", "tools", "config"}:
        # A valid digest of a changed request still cannot authorize different sampling.
        payload["request_sha256"] = f.digest(
            {k: payload[k] for k in ("messages", "tools", "config")}
        )
    with pytest.raises(ValueError):
        f.validate_reexecution_intent(
            old, new, contracts=contracts, registered_provider=e.identity.model_dump(mode="json")
        )
    assert e.provider.calls == 0


def test_validated_invocation_mapping_is_published_before_provider(execution):
    e = execution
    observed = []

    def record(mapping):
        assert e.provider.actual_model_calls == 1  # Only the already inherited CPU fixture call.
        unknown_dir = e.new / "events" / e.binding["unknown_request"]["episode_key"]
        assert [f.read(p)["kind"] for p in sorted(unknown_dir.glob("*/event.json"))] == [
            "episode_started"
        ]
        observed.append(mapping)

    run_remaining(e, record_reexecution=record)
    assert len(observed) == 1
    assert observed[0]["scientific_request_identical"] is True
    assert e.provider.actual_model_calls == 3
