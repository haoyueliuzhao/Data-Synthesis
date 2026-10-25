"""Focused LR-after-restore, exact-dose and durable-intervention controls."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from types import FunctionType, MethodType, SimpleNamespace

import pytest

import finqa_v72_binding as binding
import finqa_v72_training as training
import finqa_v72_runtime as runtime


class Monitor:
    def __init__(self, stop=None):
        self.stop = stop

    def check_stop(self, _label, **fields):
        if fields.get("step") == self.stop:
            raise RuntimeError("requested durable pause")

    def clear_unused(self, _label):
        pass


class Driver:
    def __init__(self, root, state):
        self.root = root / "training"
        self.state = copy.deepcopy(state)
        self.optimizer = SimpleNamespace(param_groups=self.state["optimizer"]["param_groups"])
        self.outer_steps = (298, 596, 894, 1192)
        self.steps, self.commits, self.actual_lrs = [], [], []

    @property
    def arm(self):
        return self.state["arm"]

    @property
    def pi(self):
        return self.state["pi"]

    @property
    def outer_done(self):
        return self.state["outer_done"]

    @property
    def step_index(self):
        return self.state["step"]

    def _payload(self):
        return copy.deepcopy(self.state)

    def restore(self, directory):
        self.state = json.loads((Path(directory) / "state.pt").read_bytes())
        self.optimizer = SimpleNamespace(param_groups=self.state["optimizer"]["param_groups"])

    def commit(self, phase, evidence):
        assert phase in ("step", "lr_intervention"), "no new outer is allowed"
        directory = self.root / f"step{self.step_index:04d}_{phase}"
        directory.mkdir(parents=True, exist_ok=False)
        raw = json.dumps(self.state, sort_keys=True).encode()
        (directory / "state.pt").write_bytes(raw)
        (directory / "record.json").write_text(json.dumps(dict(
            step=self.step_index, phase=phase, arm=self.arm, seed=137,
            pool_id=self.state["pool_id"], schedule_sha256=self.state["schedule"]["schedule_sha256"],
            checkpoint_contains_actual_model_Adam_RNG_pi=True,
            state_sha256=hashlib.sha256(raw).hexdigest(), actual_state_digest=binding.digest(self.state),
            evidence=evidence)))
        self.commits.append((self.step_index, phase))
        return directory

    def step(self):
        assert self.outer_steps == () and self.arm == "C-only"
        assert self.step_index < self.final_step
        batch = self.state["schedule"]["batches"][self.step_index]
        self.actual_lrs.append(self.optimizer.param_groups[0]["lr"])
        self.state["step"] += 1
        self.state["parameters"] += 1
        for value in self.state["optimizer"]["state"].values():
            value["step"] += 1
            value["exp_avg"] += 1
            value["exp_avg_sq"] += 1
        self.state["rng"] += 1
        self.steps.append(self.step_index)
        report = dict(id="update-" + str(self.step_index), optimizer_step_calls=1, clip_calls=1,
            actual_parameter_update=True, CPU_control_only=False,
            execution_design="original_unfused_response_rows_v18",
            supervision_policy="v14_state_independent_original_span_union.v1",
            additional_batch_division=False, additional_loss_scaling=False,
            task_batch=dict(task_ids=batch["task_ids"], step=self.step_index,
                            schedule_id=self.state["schedule"]["schedule_sha256"]))
        self.commit("step", report)
        return report


@pytest.fixture
def environment(tmp_path, monkeypatch):
    for module in (binding, training, runtime):
        monkeypatch.setattr(module, "ROOT", tmp_path)
    # State-machine tests use integer moments/cursors; the real native Adam and
    # tensor serializer contract is exercised by the separate native test.
    monkeypatch.setattr(training, "validate_point_state", lambda state, step, rt, **kw: state)
    schedule = dict(schedule_sha256="actual-ten-epoch", batches=[
        {"task_ids": [f"task{n}" for n in range(4 if (i + 1) % 149 == 0 else 5)]}
        for i in range(1490)])
    state = {key: 1 for key in training.records.COMPONENTS}
    state.update(seed=137, arm="C-only", step=1192, outer_done=[298],
        pi={"task": {"a": .7, "b": .3}}, prior={"task": {"a": .5, "b": .5}},
        optimizer=dict(state={"0":dict(step=1192, exp_avg=19, exp_avg_sq=23)},
            param_groups=[dict(lr=1e-4, betas=[.9,.999], eps=1e-8, weight_decay=0, params=[0])]),
        parameters=12, rng=23, schedule=schedule, pool_id="actual-pool",
        execution_plan=dict(outer_steps=[298,596,894,1192], final_step=1490),
        adapter_binding="actual-adapter", frozen_base_digest="actual-base")
    point = dict(schema="v72_fixed_pi_low_lr_window.v1", id="point1192", step=1192, final_step=1490,
        seed=137, arm=training.ARM, condition=training.CONDITION, checkpoint_arm="C-only",
        protocol_id="protocol-v72", parent_state_digest=binding.digest(state),
        parent_checkpoint={"path":"exact-original1192"}, initial_checkpoint={"path":"exact-original1192"},
        outer_done=[298], parent_pi=copy.deepcopy(state["pi"]), fixed_pi=copy.deepcopy(state["pi"]),
        fixed_pi_digest=binding.digest(state["pi"]), pool_id="actual-pool",
        new_outer_updates=0, automatic_outer_disabled=True,
        initial_learning_rate=1e-4, learning_rate=1e-5, parameter_group_count=1,
        fixed_component_digests={key:binding.digest(state[key]) for key in training.FIXED_COMPONENTS},
        component_digests={"rng":binding.digest(state["rng"])},
        optimizer_groups_except_lr_digest=binding.digest(training._without_lr(state["optimizer"]["param_groups"])),
        planned_post_intervention_state_digest=binding.digest(training.state_with_learning_rate(state,1e-5)),
        original_schedule_sha256="actual-ten-epoch", window_task_batches=schedule["batches"][1192:1490])
    rt = SimpleNamespace(v8=SimpleNamespace(_tree_digest=binding.digest))
    return SimpleNamespace(root=tmp_path,state=state,point=point,rt=rt)


def run(e,driver,monitor=None):
    return training.execute_training(e.root,e.point,e.state,driver,rt=e.rt,monitor=monitor or Monitor())


def test_exact298_dose_and_only_one_lr_intervention(environment):
    e=environment; driver=Driver(e.root,e.state); before=copy.deepcopy(e.state)
    result=run(e,driver)
    assert driver.steps==list(range(1193,1491)) and driver.actual_lrs==[1e-5]*298
    assert driver.commits[0]==(1192,"lr_intervention") and len(driver.commits)==299
    assert sum(phase=="step" for _,phase in driver.commits)==298
    assert driver.pi==before["pi"]!=before["prior"] and driver.outer_done==[298]
    post=json.loads((training.intervention_directory(e.root)/"state.pt").read_bytes())
    assert binding.digest(post)!=binding.digest(before)
    assert training.state_with_learning_rate(post,1e-4)==before
    assert result["optimizer_updates"]==298 and result["outer_updates"]==0
    assert result["learning_rate"]==1e-5 and result["initial_learning_rate"]==1e-4
    assert result["task_exposures"]==1488 and len(result["update_receipts"])==298
    assert [len(b["task_ids"]) for b in e.point["window_task_batches"]].count(4)==2
    assert not list(driver.root.glob("*_outer"))


@pytest.mark.parametrize("component",["rng","parameters","optimizer"])
def test_original_complete_parent_must_precede_intervention(environment,component):
    e=environment;driver=Driver(e.root,e.state)
    if component=="optimizer":driver.state["optimizer"]["state"]["0"]["exp_avg"]+=1
    else:driver.state[component]+=1
    with pytest.raises(ValueError,match="actual parent"):
        run(e,driver)
    assert not driver.steps and not driver.commits


def test_setting_lr_before_exact_restore_is_rejected(environment):
    e=environment;driver=Driver(e.root,e.state)
    driver.optimizer.param_groups[0]["lr"]=1e-5
    with pytest.raises(ValueError,match="actual parent"):
        run(e,driver)
    assert not driver.commits


def test_resume_preserves_original_intervention_and_actual_rng(environment):
    e=environment;first=Driver(e.root,e.state)
    with pytest.raises(RuntimeError,match="durable pause"):
        run(e,first,Monitor(stop=1203))
    native=training.intervention_directory(e.root)
    original_bytes=(native/"state.pt").read_bytes()
    second=Driver(e.root,e.state);result=run(e,second)
    assert first.steps==list(range(1193,1203)) and second.steps==list(range(1203,1491))
    assert not any(phase=="lr_intervention" for _,phase in second.commits)
    assert (native/"state.pt").read_bytes()==original_bytes
    assert second.state["rng"]==e.state["rng"]+298
    assert result["updates_in_final_worker"]==288


def test_intervention_checkpoint_before_proof_can_reconcile_without_reapplying(environment,monkeypatch):
    e=environment;first=Driver(e.root,e.state)
    original_publish=training.publish
    def crash_proof(path,body):
        if Path(path).parent.name=="lr_intervention":raise OSError("after atomic state before proof")
        return original_publish(path,body)
    monkeypatch.setattr(training,"publish",crash_proof)
    with pytest.raises(OSError):run(e,first)
    assert first.commits==[(1192,"lr_intervention")] and not first.steps
    monkeypatch.setattr(training,"publish",original_publish)
    second=Driver(e.root,e.state);result=run(e,second)
    assert len(second.steps)==298 and all(phase=="step" for _,phase in second.commits)
    assert result["optimizer_updates"]==298


@pytest.mark.parametrize("mutation",["lr","betas","pi","history"])
def test_resume_rejects_lr_or_fixed_components_drift(environment,mutation):
    e=environment
    with pytest.raises(RuntimeError):run(e,Driver(e.root,e.state),Monitor(stop=1195))
    p=e.root/"training/step1194_step/state.pt";state=json.loads(p.read_bytes())
    if mutation=="lr":state["optimizer"]["param_groups"][0]["lr"]=1e-4
    elif mutation=="betas":state["optimizer"]["param_groups"][0]["betas"]=[.8,.99]
    elif mutation=="pi":state["pi"]={"task":{"a":.5,"b":.5}}
    else:state["outer_done"]=[298,1192]
    p.write_text(json.dumps(state))
    if mutation=="lr":
        # Restore retains the wrong rate, which the before-step runtime gate
        # rejects even with the synthetic common tensor validator bypassed.
        with pytest.raises(ValueError,match="LR"):
            run(e,Driver(e.root,e.state))
    else:
        with pytest.raises(ValueError,match="hyperparameters|pi0|history|component"):
            run(e,Driver(e.root,e.state))


def test_completed_window_can_only_restore_not_train_again(environment):
    e=environment;result=run(e,Driver(e.root,e.state))
    with pytest.raises(ValueError,match="cannot execute again"):run(e,Driver(e.root,e.state))
    restored=Driver(e.root,e.state)
    training.restore_completed_window(e.point,result,restored,e.rt)
    assert restored.step_index==1490 and restored.optimizer.param_groups[0]["lr"]==1e-5
    assert not restored.steps and not restored.commits


@pytest.mark.parametrize("name",["step1192_outer","step1192_step","step1491_step"])
def test_outer_and_extra_update_paths_forbid_resume(environment,name):
    e=environment;(e.root/"training"/name).mkdir(parents=True)
    with pytest.raises(ValueError,match="forbids|dose"):
        training.latest_window_checkpoint(e.root/"training",1192)


def test_resume_progress_counts_optimizer_not_lr_change(environment):
    e=environment;e.point=binding.publish(e.root/"points/step1192/context/record.json",e.point)
    with pytest.raises(RuntimeError):run(e,Driver(e.root,e.state),Monitor(stop=1193))
    audit=training.audit_training_resume(e.root,runtime.job_spec(1192))
    assert audit["progress_units"]==0 and audit["details"]["actual_lr_intervention_checkpoint_present"]
    assert audit["details"]["new_outer_commits"]==0


@pytest.mark.parametrize("step,stage",[(894,"train"),(1490,"train"),(1192,"distribution"),(1192,"replay")])
def test_runtime_registers_only_requested_training_window(environment,step,stage):
    with pytest.raises(ValueError,match="only one low-LR"):
        runtime.stage_root(environment.root,step,stage)


@pytest.mark.parametrize("changed",["rng","parameters","moment","cursor","betas"])
def test_lr_only_validator_rejects_every_other_state_change(environment,changed):
    e=environment;after=copy.deepcopy(training.state_with_learning_rate(e.state,1e-5))
    if changed in ("rng","parameters"):after[changed]+=1
    elif changed=="moment":after["optimizer"]["state"]["0"]["exp_avg"]+=1
    elif changed=="cursor":after["optimizer"]["state"]["0"]["step"]+=1
    else:after["optimizer"]["param_groups"][0]["betas"]=[.8,.99]
    with pytest.raises(ValueError,match="only actual LR"):
        training.validate_only_lr_intervention(e.state,after,e.point,e.rt)


def test_native_optimizer_restore_overwrites_constructor_lr_and_intervention_preserves_moments(tmp_path):
    import torch
    from trusted_synthesis.finance_research import v8_training_driver as v8
    assert Path(v8.__file__).resolve().is_relative_to(Path(binding.install_scientific_paths()["frozen_source_root"]))
    real=v8.TrainingDriver;model=torch.nn.Linear(2,1)
    optimizer=torch.optim.AdamW(model.parameters(),lr=1e-4,weight_decay=0)
    for parameter in model.parameters():
        optimizer.state[parameter]=dict(step=torch.tensor(1192.),exp_avg=torch.full_like(parameter,.2),exp_avg_sq=torch.full_like(parameter,.4))
    driver=object.__new__(real)
    driver.root,driver.model,driver.optimizer=tmp_path/"native",model,optimizer
    driver.pool=SimpleNamespace(cache_id="tiny-low-lr-pool")
    driver.seed,driver.arm=137,"C-only";driver.parameters=dict(model.named_parameters())
    driver.schedule=dict(schedule_sha256="same-ten-epoch",batches=[])
    driver.execution_plan=dict(outer_steps=[298,596,894,1192],final_step=1490)
    driver.adapter_binding,driver.base_digest=None,"same-base"
    driver.pi={"task":{"a":.7,"b":.3}};driver.prior={"task":{"a":.5,"b":.5}}
    driver.step_index,driver.outer_done=1192,[298]
    fixed_rng=dict(cpu=torch.tensor([1,7],dtype=torch.uint8),cuda=None,fixture_only=True)
    restored_rng=[]
    def bind(function,**overrides):
        clone=FunctionType(function.__code__,dict(function.__globals__,**overrides),function.__name__,function.__defaults__,function.__closure__)
        clone.__kwdefaults__=function.__kwdefaults__
        return MethodType(clone,driver)
    driver._payload=bind(real._payload,_rng=lambda:copy.deepcopy(fixed_rng))
    driver.restore=bind(real.restore,_restore_rng=lambda value:restored_rng.append(value))
    before=driver._payload();parent=driver.commit("step",{"cpu_fixture_only":True})
    optimizer.param_groups[0]["lr"]=1e-5
    driver.restore(parent)
    assert optimizer.param_groups[0]["lr"]==1e-4
    assert v8._tree_digest(driver._payload())==v8._tree_digest(before)
    optimizer.param_groups[0]["lr"]=1e-5
    post=driver._payload()
    assert v8._tree_digest(post)!=v8._tree_digest(before)
    assert v8._tree_digest(training.state_with_learning_rate(post,1e-4))==v8._tree_digest(before)
    intervention=driver.commit("lr_intervention",{"cpu_fixture_only":True})
    optimizer.param_groups[0]["lr"]=1e-4
    driver.restore(intervention)
    assert optimizer.param_groups[0]["lr"]==1e-5
    assert v8._tree_digest(driver._payload())==v8._tree_digest(post)
    assert v8._tree_digest(restored_rng[-1])==v8._tree_digest(fixed_rng)


@pytest.mark.parametrize("lr,cursor,valid",[(1e-5,1490,True),(1e-4,1490,False),(1e-5,1489,False)])
def test_actual_tensor_endpoint_requires_new_lr_and_exact_adam_cursor(lr,cursor,valid):
    import torch
    from trusted_synthesis.finance_research import v8_training_driver as v8
    pi={f"task{i}":{"a":1.0} for i in range(744)}
    state=dict(seed=137,arm="C-only",step=1490,outer_done=[298],model_training=True,
        pi=pi,prior=copy.deepcopy(pi),pool_id="tiny-actual-fixed",
        rng={"cuda":[torch.tensor([1],dtype=torch.uint8)]},
        optimizer=dict(state={0:dict(step=torch.tensor(float(cursor)),
            exp_avg=torch.tensor([.2]),exp_avg_sq=torch.tensor([.4]))},
            param_groups=[dict(lr=lr,betas=(.9,.999),eps=1e-8,weight_decay=0,params=[0])]),
        execution_plan=dict(outer_steps=[298,596,894,1192],final_step=1490),
        schedule=dict(schedule_sha256="same"),adapter_binding="adapter",frozen_base_digest="base")
    point=dict(fixed_pi=pi,fixed_pi_digest=v8._tree_digest(pi),
        fixed_component_digests={key:v8._tree_digest(state[key]) for key in training.FIXED_COMPONENTS},
        optimizer_groups_except_lr_digest=v8._tree_digest(training._without_lr(state["optimizer"]["param_groups"])))
    rt=SimpleNamespace(v8=v8)
    if valid:
        assert training.validate_low_lr_state(state,1490,point,rt) is state
    else:
        with pytest.raises(ValueError,match="learning rate|Adam cursor"):
            training.validate_low_lr_state(state,1490,point,rt)
