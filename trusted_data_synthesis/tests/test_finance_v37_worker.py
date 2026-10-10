"""CPU/mock production-stage contracts; never a GPU or new feedback experiment."""

import ast
import copy
import hashlib
import importlib
import json
import os
import subprocess
import sys
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

import pytest
import torch

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
worker = importlib.import_module("finqa_v37_worker")


def digest(value):
    if isinstance(value, torch.Tensor):
        value = value.detach().cpu().contiguous()
        value = dict(
            shape=list(value.shape),
            dtype=str(value.dtype),
            data=value.reshape(-1).view(torch.uint8).numpy().tobytes().hex(),
        )
    if isinstance(value, dict):
        value = {str(k): digest(v) for k, v in value.items()}
    elif isinstance(value, (tuple, list)):
        value = [digest(v) for v in value]
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


class Immutable:
    @staticmethod
    def write_immutable_artifact_directory(path, files):
        path.mkdir(parents=True, exist_ok=False)
        for name, raw in files.items():
            (path / name).write_bytes(raw)


class Monitor:
    def __init__(self, fail_at=None):
        self.labels, self.fail_at = [], fail_at

    def clear_unused(self, label):
        self.labels.append(label)
        if label == self.fail_at:
            raise ValueError("mock resource failure")

    def snapshot(self, label, **_context):
        self.labels.append(label)

    def check_stop(self, label, **_context):
        self.labels.append(label)


PARAMETERS = dict(
    epsilon=0.05,
    contribution_exponent=0.8,
    novelty_exponent=0.2,
    novelty_temperature=1.0,
    lambda_current=4.0,
    lambda_prior=1.0,
    rms_floor=1e-8,
)


@pytest.fixture
def phase(tmp_path):
    parameters = {"weight": torch.nn.Parameter(torch.tensor([[1.0, 2.0]]))}
    before = dict(
        seed=137,
        arm="C-only",
        step=1192,
        pi={"task": {"s": 1.0}},
        prior={"task": {"s": 1.0}},
        rng={"test": "actual-rng"},
    )
    context = dict(
        id="current-context",
        seed=137,
        arm="C-only",
        step=1192,
        due_outer=True,
        pre_state_digest=digest(before),
        parameter_spec=[dict(name="weight", shape=[1, 2], dtype="torch.float32")],
        mu={"task": "1"},
        branch=dict(contribution_only=True, b_N=0.0, parameters=copy.deepcopy(PARAMETERS)),
        checkpoint={"state": {"path": "current-state.pt", "sha256": "current-state-sha"}},
        feedback=dict(
            mode="sealed_existing",
            expected_point_id="point",
            base_root=str(tmp_path / "feedback"),
            root=str(tmp_path / "feedback" / "sealed"),
            manifest={"path": "manifest"},
        ),
    )
    driver = SimpleNamespace(
        parameters=parameters, optimizer=object(), model=object(), tokenizer=object()
    )
    point = dict(
        G={"weight": torch.tensor([[0.5, 0.25]])},
        theta_bar={"weight": torch.tensor([[0.9, 1.9]])},
        update={"weight": torch.tensor([[0.1, 0.1]])},
        diagnostics={"original": True},
        point_id="point",
        adam_binding_snapshot={"clip": {"max_norm": 1.0, "epsilon": 1e-6}},
        feedback_seal={"seal_sha256": "actual-seal", "denominator": 700},
        rewards=[1] + [0] * 699,
    )
    prepared = dict(
        binding=SimpleNamespace(snapshot=point["adam_binding_snapshot"]),
        **{key: point[key] for key in ("G", "theta_bar", "update", "diagnostics")},
    )
    calls = []

    def prepare(named, optimizer, gradients, pi, mu):
        assert named is parameters and optimizer is driver.optimizer
        assert pi is before["pi"] and mu is context["mu"]
        calls.append("prepare")
        return prepared

    rt = SimpleNamespace(
        torch=torch,
        v8=SimpleNamespace(
            _tree_digest=digest,
            parameter_digest=digest,
            digest=lambda value: hashlib.sha256(str(value).encode()).hexdigest(),
            PARAMETERS=copy.deepcopy(PARAMETERS),
            prepare_virtual_point=prepare,
            _rng=lambda: copy.deepcopy(before["rng"]),
        ),
    )
    bundle = SimpleNamespace(
        rt=rt,
        immutable=Immutable,
        guard=SimpleNamespace(recompute_point_id=lambda *_a, **_k: "point"),
    )
    return SimpleNamespace(
        directory=tmp_path / "stage",
        context=context,
        before=before,
        driver=driver,
        point=point,
        prepared=prepared,
        bundle=bundle,
        monitor=Monitor(),
        stop=SimpleNamespace(requested=False),
        calls=calls,
    )


def test_actual_tensor_payload_is_context_bound_and_not_only_a_completion_boolean(phase):
    ref = worker.save_payload(
        phase.directory,
        phase.bundle.rt,
        Immutable,
        context=phase.context,
        phase="replay_R3",
        value={"gJ": {"weight": torch.tensor([[3.0, -4.0]])}},
    )
    assert Path(ref["path"]).is_file()
    state = worker.read_payload(
        phase.directory / "payload", phase.bundle.rt, context=phase.context, phase="replay_R3"
    )
    assert torch.equal(state["gJ"]["weight"], torch.tensor([[3.0, -4.0]]))
    with pytest.raises(ValueError, match="another actual point"):
        worker.read_payload(
            phase.directory / "payload",
            phase.bundle.rt,
            context=phase.context | {"id": "step298-reference"},
            phase="replay_R3",
        )
    raw = (phase.directory / "payload/state.pt").read_bytes()
    (phase.directory / "payload/state.pt").write_bytes(raw + b"changed")
    with pytest.raises(ValueError, match="tensor bytes changed"):
        worker.read_payload(phase.directory / "payload", phase.bundle.rt, context=phase.context)


class Cohort:
    def __init__(self, phase):
        self.denominator = 700
        self.identity = SimpleNamespace(
            point_id="point", parameter_digest=digest(phase.point["theta_bar"])
        )
        self.seal_sha256 = "actual-seal"
        self.episodes = [
            SimpleNamespace(actual_model_calls=1, turns=[object()]) for _ in range(700)
        ]

    def model_dump(self, **_kwargs):
        return {"seal_sha256": self.seal_sha256, "denominator": 700}


def feedback_files(root):
    for name in (
        "intent/record.json",
        "cohort_seal/record.json",
        "native_rewards/record.json",
        "draw0/run.json",
        "draw0/generation_seal/seal.json",
        "draw1/run.json",
        "draw1/generation_seal/seal.json",
    ):
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{}")


def test_existing_point_mismatch_stops_before_feedback_read_or_collector(phase, monkeypatch):
    monkeypatch.setattr(
        worker.control,
        "read_ref",
        lambda _ref: {"pre_state_digest": phase.context["pre_state_digest"]},
    )

    def reject(*_args):
        phase.calls.append("point_rejected")
        raise ValueError("actual point mismatch")

    phase.bundle.guard.check_recomputed_point = reject
    phase.bundle.guard.read_sealed_feedback = lambda *_a, **_k: pytest.fail(
        "must not read feedback before point match"
    )
    with pytest.raises(ValueError, match="actual point mismatch"):
        worker.execute_virtual(
            phase.directory,
            phase.context,
            phase.before,
            phase.driver,
            {},
            phase.bundle,
            phase.monitor,
            phase.stop,
        )
    assert phase.calls == ["prepare", "point_rejected"]
    assert (phase.directory / "computed_point/payload/state.pt").exists()
    assert not Path(phase.context["feedback"]["base_root"]).exists()


def test_existing_feedback_is_read_only_after_real_point_match(phase, monkeypatch):
    root = Path(phase.context["feedback"]["root"])
    feedback_files(root)
    manifest = dict(pre_state_digest=phase.context["pre_state_digest"], feedback_root=str(root))
    monkeypatch.setattr(worker.control, "read_ref", lambda _ref: manifest)
    phase.bundle.guard.check_recomputed_point = lambda *_a: phase.calls.append("point_match")

    def read(*_a, **_k):
        assert phase.calls[-1] == "point_match"
        phase.calls.append("read_original")
        return Cohort(phase), phase.point["rewards"]

    phase.bundle.guard.read_sealed_feedback = read
    result = worker.execute_virtual(
        phase.directory,
        phase.context,
        phase.before,
        phase.driver,
        {},
        phase.bundle,
        phase.monitor,
        phase.stop,
    )
    assert phase.calls == ["prepare", "point_match", "read_original"]
    assert (
        result["new_feedback_episodes"]
        == result["new_sampling_calls"]
        == result["scoring_calls"]
        == 0
    )
    assert result["response_count"] == 1 and result["denominator"] == 700
    actual = worker.read_payload(
        phase.directory / "payload", phase.bundle.rt, context=phase.context
    )
    assert torch.equal(actual["G"]["weight"], phase.point["G"]["weight"])


def test_future_first_sampling_uses_new_point_without_reference_answer(phase):
    phase.context["feedback"].update(
        mode="first_sampling", expected_point_id=None, root=None, manifest=None
    )
    root = Path(phase.context["feedback"]["base_root"]) / phase.bundle.rt.v8.digest("point")

    class Collector:
        def collect(self, model, tokenizer, theta, *, point_id, event_sink):
            assert point_id == "point" and theta is phase.prepared["theta_bar"]
            assert (phase.directory / "computed_point/payload/state.pt").exists()
            phase.calls.append("first_collector")
            feedback_files(root)
            return Cohort(phase), phase.point["rewards"]

    phase.bundle.rt.v8.LocalFeedbackCollector = Collector
    result = worker.execute_virtual(
        phase.directory,
        phase.context,
        phase.before,
        phase.driver,
        {},
        phase.bundle,
        phase.monitor,
        phase.stop,
        collector=Collector(),
    )
    assert phase.calls == ["prepare", "first_collector"]
    assert result["new_feedback_episodes"] == 700 and result["scoring_calls"] == 700
    assert result["original_sealed_point_matched"] is None


def test_existing_or_partial_future_feedback_never_gets_resampled(phase):
    phase.context["feedback"].update(mode="first_sampling", expected_point_id=None)
    root = Path(phase.context["feedback"]["base_root"]) / phase.bundle.rt.v8.digest("point")
    root.mkdir(parents=True)

    class Collector:
        def collect(self, *_a, **_k):
            pytest.fail("partial feedback must not be resampled")

    phase.bundle.rt.v8.LocalFeedbackCollector = Collector
    with pytest.raises(ValueError, match="cannot be sampled or rescored"):
        worker.execute_virtual(
            phase.directory,
            phase.context,
            phase.before,
            phase.driver,
            {},
            phase.bundle,
            phase.monitor,
            phase.stop,
            collector=Collector(),
        )


@pytest.mark.parametrize("arm", ["C-only", "Full"])
def test_distribution_binds_original_arm_prior_and_novelty_and_saves_actual_outputs(
    phase, monkeypatch, arm
):
    phase.context["arm"] = phase.before["arm"] = arm
    phase.context["branch"].update(
        contribution_only=arm == "C-only", b_N=0 if arm == "C-only" else 0.2
    )
    actual_gj = {"weight": torch.tensor([[3.0, -4.0]])}
    replay = dict(
        current_point_only=True,
        V33_reference_gradient_used=False,
        point_id="point",
        gJ=actual_gj,
        feedback_report=dict(denominator=700, complete_replay=True),
    )
    monkeypatch.setattr(worker, "rebind_prepared", lambda *_a: phase.prepared)

    def update(prepared, gradients, gJ, pi, prior, mu, **kwargs):
        assert kwargs["contribution_only"] is (arm == "C-only")
        assert kwargs["novelty_exponent"] == 0.2 and kwargs["lambda_prior"] == 1.0
        assert prior is phase.before["prior"] and pi is phase.before["pi"]
        assert torch.equal(gJ["weight"], actual_gj["weight"])
        phase.calls.append("update")
        return dict(
            a={"weight": torch.tensor([[5.0, -6.0]])},
            C={"task": {"s": 0.0}},
            distribution=dict(
                pi_next={"task": {"s": 1.0}},
                task_diagnostics={"task": {"N": {"s": 0.25}}},
                effective_novelty_exponent=0 if arm == "C-only" else 0.2,
                contribution_only=arm == "C-only",
            ),
            feedback_report=kwargs["feedback_report"],
        )

    phase.bundle.rt.v8.update_distribution = update
    result = worker.execute_distribution(
        phase.directory,
        phase.context,
        phase.before,
        phase.point,
        replay,
        phase.driver,
        {},
        phase.bundle,
        phase.monitor,
        phase.stop,
    )
    assert phase.calls == ["update"] and result["outer_commits"] == 0
    saved = worker.read_payload(
        phase.directory / "payload", phase.bundle.rt, context=phase.context, phase="distribution"
    )
    assert saved["N"] == {"task": {"s": 0.25}}
    assert saved["outer_inputs"]["schema"] == "v9_real_outer_inputs.v1"
    assert torch.equal(saved["outer_inputs"]["gJ"]["weight"], actual_gj["weight"])
    assert (
        saved["evidence"]["distribution"]["effective_novelty_exponent"]
        == phase.context["branch"]["b_N"]
    )


def test_full_cannot_be_silently_routed_through_c_only(phase):
    phase.context["arm"] = "Full"
    with pytest.raises(ValueError, match="C-only/Full branch"):
        worker.validate_branch(phase.context, phase.bundle.rt)


def test_replay_uses_actual_current_point_R3_accumulator_and_fixed700_not_v33(phase):
    @contextmanager
    def installed(_model, theta):
        yield theta

    phase.bundle.rt.v8.installed_point = installed
    actual = {"weight": torch.tensor([[7.0, -8.0]])}
    options = []

    class Session:
        def __init__(self, _model, _theta, **kwargs):
            options.append(kwargs)

    def feedback(cohort, rewards, model, theta, **kwargs):
        assert kwargs["profile_id"] == phase.context["id"]
        assert kwargs["checkpoint_every"] == 16 and kwargs["pause_after_response"] is None
        assert kwargs["rng_restore_source"]["checkpoint"] == phase.context["checkpoint"]["state"]
        kwargs["backend_factory"](model, theta)
        worker.control.publish(kwargs["root"] / "response000001/record.json", dict(cursor=1))
        return actual, dict(
            complete_replay=True,
            denominator=700,
            point_id="point",
            gJ_digest=digest(actual),
            response_checkpoint_binding={"response_count": 1},
            restored_completed_responses=0,
            accounting={"responses_replayed": 1},
        )

    phase.bundle.replay = SimpleNamespace(
        BACKEND_VERSION="registered-R3",
        source_binding=lambda: {"same": "code"},
        optimized=SimpleNamespace(bind_dependencies=lambda fn, **kw: fn),
        v32=SimpleNamespace(feedback_gradient=feedback),
        R3Session=Session,
    )
    result = worker.execute_replay(
        phase.directory,
        phase.context,
        phase.before,
        phase.point,
        Cohort(phase),
        phase.point["rewards"],
        phase.driver,
        phase.bundle,
        phase.monitor,
        phase.stop,
    )
    saved = worker.read_payload(
        phase.directory / "payload", phase.bundle.rt, context=phase.context, phase="replay_R3"
    )
    assert torch.equal(saved["gJ"]["weight"], actual["weight"])
    assert saved["V33_reference_gradient_used"] is False
    assert (
        result["response_count"] == result["replayed_responses"] == 1
        and result["denominator"] == 700
    )
    assert options[0]["activation_resident_budget_bytes"] == 16 * worker.GIB
    assert options[0]["full_kv_budget_bytes"] == 8 * worker.GIB
    assert options[0]["allocated_memory_limit_bytes"] == 76 * worker.GIB


def test_failed_or_unexited_upstream_payload_cannot_admit_distribution(tmp_path):
    context = {"id": "context", "due_outer": True}
    plan = {"id": "protocol"}
    for previous in ("virtual_point", "replay_R3"):
        worker.control.publish(tmp_path / previous / "payload/record.json", dict(actual=True))
        worker.control.publish(
            tmp_path / previous / "result/record.json",
            dict(
                protocol_id="protocol",
                context_id="context",
                stage=previous,
                status="COMPLETE",
                model_released=True,
                resources={"all_gates_passed": previous != "replay_R3"},
                payload=worker.control.entry(tmp_path / previous / "payload/record.json"),
            ),
        )
        worker.control.publish(
            tmp_path / previous / "exit/record.json",
            dict(protocol_id="protocol", context_id="context", stage=previous, returncode=0),
        )
    with pytest.raises(ValueError, match="upstream production stage"):
        worker.require_upstream(tmp_path, context, plan, "distribution")


def test_original_arm_locks_allow_math_readers_but_exclude_training_writer(tmp_path):
    context = dict(
        seed=137,
        arm="C-only",
        training_root=str(tmp_path),
        arm_root=str(tmp_path / "seed137/arms/c_only"),
    )
    with worker.training_point_locks(context, "shard00"):
        with worker.training_point_locks(context, "shard01"):
            with pytest.raises(BlockingIOError):
                with worker.training_point_locks(context, "train"):
                    pytest.fail("writer cannot overlap actual-point readers")
    with worker.training_point_locks(context, "train"):
        with pytest.raises(BlockingIOError):
            with worker.training_point_locks(context, "virtual_point"):
                pytest.fail("reader cannot overlap an actual training writer")


def test_real_frozen_Adam_cold_binding_and_Full_novelty_on_CPU():
    repo = Path(__file__).parents[2]
    frozen = (
        repo
        / ".codex-worktrees/finqa-v18-researcher-continuation-20260930/trusted_data_synthesis/src"
    )
    code = r"""
import copy,sys,torch
from types import SimpleNamespace
sys.path.insert(0,sys.argv[1]); sys.path.insert(0,sys.argv[2])
from trusted_synthesis.finance_research import v8_training_driver as v8
import finqa_v37_worker as worker
assert not torch.cuda.is_initialized()
torch.manual_seed(17)
model=torch.nn.Linear(2,1,bias=False)
optimizer=torch.optim.AdamW(model.parameters(),lr=1e-4,betas=(.9,.999),eps=1e-8,weight_decay=0,foreach=False,fused=False)
model.weight.grad=torch.tensor([[.1,.2]])
optimizer.step()
model.weight.grad=torch.ones_like(model.weight)*3
named=dict(model.named_parameters())
pi={'a':{'x':.75,'y':.25},'control':{'z':1.0}}
prior={'a':{'x':.5,'y':.5},'control':{'z':1.0}}
mu={'a':'1/2','control':'1/2'}
gradients={'a':{'x':{'weight':torch.tensor([[1.,0.]])},'y':{'weight':torch.tensor([[0.,1.]])}},'control':{'z':{'weight':torch.tensor([[.2,.4]])}}}
prepared=v8.prepare_virtual_point(named,optimizer,gradients,pi,mu)
point={key:worker.cpu_tensors(prepared[key]) for key in ('G','theta_bar','update')}
point.update(diagnostics=copy.deepcopy(prepared['diagnostics']),adam_binding_snapshot=copy.deepcopy(prepared['binding'].snapshot))
cold=torch.nn.Linear(2,1,bias=False); cold.load_state_dict(model.state_dict())
cold_optimizer=torch.optim.AdamW(cold.parameters(),lr=1e-4,betas=(.9,.999),eps=1e-8,weight_decay=0,foreach=False,fused=False)
cold_optimizer.load_state_dict(copy.deepcopy(optimizer.state_dict()))
driver=SimpleNamespace(parameters=dict(cold.named_parameters()),optimizer=cold_optimizer)
rebound=worker.rebind_prepared(point,driver,SimpleNamespace(rt=SimpleNamespace(v8=v8)))
assert rebound['binding'].snapshot==prepared['binding'].snapshot
assert v8.parameter_digest(rebound['G'])==v8.parameter_digest(prepared['G'])
assert v8.parameter_digest(rebound['theta_bar'])==v8.parameter_digest(prepared['theta_bar'])
gJ={'weight':torch.tensor([[.25,-.5]])}
report={'denominator':700,'all_receipts_validated':True,'gJ_digest':v8.parameter_digest(gJ),'parameter_digest':v8.parameter_digest(rebound['theta_bar']),'accounting':{'zero_reward_trajectories_skipped':0}}
full=v8.update_distribution(rebound,gradients,gJ,pi,prior,mu,feedback_report=report,control_tasks=['control'],contribution_only=False,**v8.PARAMETERS)
conly=v8.update_distribution(rebound,gradients,gJ,pi,prior,mu,feedback_report=report,control_tasks=['control'],contribution_only=True,**v8.PARAMETERS)
assert full['distribution']['effective_novelty_exponent']==.2
assert conly['distribution']['effective_novelty_exponent']==0
assert full['distribution']['task_diagnostics']['a']['N']['y']>0
assert full['distribution']['pi_next']!=conly['distribution']['pi_next']
assert not torch.cuda.is_initialized()
print('CPU_COLD_BINDING_AND_FULL_NOVELTY_PASS')
"""
    result = subprocess.run(
        [sys.executable, "-c", code, str(frozen), str(repo / "trusted_data_synthesis/scripts")],
        text=True,
        capture_output=True,
        env=os.environ | {"CUDA_VISIBLE_DEVICES": "", "PYTHONDONTWRITEBYTECODE": "1"},
        timeout=120,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "CPU_COLD_BINDING_AND_FULL_NOVELTY_PASS" in result.stdout


def test_worker_has_one_lifetime_peak_reset_and_no_monolithic_outer_or_reference_gj_loader():
    tree = ast.parse(Path(worker.__file__).read_text())
    attrs = [
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    ]
    assert attrs.count("reset_peak_memory_stats") == 1
    assert (
        "outer_update" not in attrs
        and "run_until" not in attrs
        and "load_saved_gradient" not in attrs
    )
    distribution = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "execute_distribution"
    )
    calls = [
        node.func.attr
        for node in ast.walk(distribution)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    ]
    assert calls.count("update_distribution") == 1 and "prepare_virtual_point" not in calls
