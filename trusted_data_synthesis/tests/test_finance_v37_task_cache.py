"""Narrow CPU controls for actual-state production contexts, not a GPU replay."""

import copy
import hashlib
import importlib
import io
import json
import pickle
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
import torch

from trusted_synthesis.finance_research import v8_training_driver as v8

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
contexts = importlib.import_module("finqa_v37_task_cache")
original = importlib.import_module("finqa_v35_task_cache")


@pytest.fixture
def fixture(tmp_path):
    torch.set_num_threads(1)
    task_ids = ["task0", "task1", "task2", "task3"]
    packages = [
        dict(task_id=task, state_id="z0", package_id=f"p{index}", whole_package_target_tokens=1)
        for index, task in enumerate(task_ids)
    ]
    pool = v8.VerifiedPool(
        task_ids,
        packages,
        {
            p["package_id"]: [dict(input_ids=[1, 2], target_positions=[1], target_ids=[2])]
            for p in packages
        },
        binding_id="V37_CPU_FIXTURE_ONLY",
        chi={},
        production=False,
    )
    execution = dict(
        shared_step=298, sharing_split_step=894, final_step=1490, outer_steps=[298, 596, 894, 1192]
    )
    root = tmp_path / "v25_training_replication_01/training_replication"
    (root / "registration").mkdir(parents=True)
    (root / "registration/record.json").write_text(json.dumps(dict(id="CPU_training_protocol")))

    def schedule(tasks, seed):
        return dict(
            schedule_sha256=contexts.digest(dict(task_ids=list(tasks), seed=seed)),
            seed=seed,
            batches=[dict(task_ids=list(tasks))],
        )

    rt = SimpleNamespace(
        torch=torch,
        v8=v8,
        conditional=SimpleNamespace(execution_plan=lambda _count: copy.deepcopy(execution)),
    )
    training = SimpleNamespace(
        __file__=__file__,
        DEFAULT_ROOT=root,
        build_task_schedule=schedule,
        checked_launch=lambda _root: (
            dict(id="CPU_training_protocol", budgets=dict(physical_updates=11622)),
            pool,
            None,
            None,
        ),
    )
    outputs = tmp_path / "production_resume_01"
    counter = [0]

    def checkpoint(seed=389, arm="Full", step=298, outer_done=(), phase="branch", pi=None):
        state = dict(
            schema="v8_committed_training_state.v1",
            seed=seed,
            arm=arm,
            step=step,
            pool_id=pool.cache_id,
            outer_done=list(outer_done),
            schedule=schedule(pool.task_ids, seed),
            execution_plan=copy.deepcopy(execution),
            pi=copy.deepcopy(pi or pool._manifest.registration.pi0),
            prior=copy.deepcopy(pool._manifest.registration.pi0),
            parameters={"weight": torch.tensor([[1.0, -2.0]], dtype=torch.float32)},
            buffers={"buffer": torch.tensor([3.0])},
            optimizer=dict(
                state={
                    0: dict(
                        step=torch.tensor(float(step)),
                        exp_avg=torch.ones(1, 2),
                        exp_avg_sq=torch.ones(1, 2) * 2,
                    )
                },
                param_groups=[
                    dict(params=[0], lr=1e-4, betas=(0.9, 0.999), eps=1e-8, weight_decay=0)
                ],
            ),
            rng=v8._rng(),
            model_training=True,
            frozen_base_digest="CPU_frozen_base",
            adapter_binding={"CPU": True},
        )
        directory = root / f"seed{seed}/arms/{contexts.ARMS[arm]}/training/step{step:04d}_{phase}"
        directory.mkdir(parents=True, exist_ok=True)
        stream = io.BytesIO()
        torch.save(state, stream)
        raw = stream.getvalue()
        (directory / "state.pt").write_bytes(raw)
        record = dict(
            seed=seed,
            arm=arm,
            step=step,
            pool_id=pool.cache_id,
            phase=phase,
            schedule_sha256=state["schedule"]["schedule_sha256"],
            state_sha256=hashlib.sha256(raw).hexdigest(),
            actual_state_digest=v8._tree_digest(state),
            checkpoint_contains_actual_model_Adam_RNG_pi=True,
        )
        (directory / "record.json").write_text(json.dumps(record))
        return directory, state

    def output():
        counter[0] += 1
        return outputs / f"context{counter[0]}"

    def prepare(path, output_root=None, **extra):
        return contexts.prepare_outer(
            output_root or output(),
            path,
            training=training,
            rt=rt,
            original_cache_module=original,
            sources={},
            execution_binding=dict(protocol_id="CPU_authorized"),
            **extra,
        )

    def load(context):
        return contexts.load_context(
            context["run_root"], training=training, rt=rt, original_cache_module=original
        )

    def seal_pending(path, state):
        coordinate = (state["seed"], state["arm"], state["step"])
        point = contexts.PENDING_SEALED[coordinate]
        _state, ref = contexts.read_checkpoint(path, rt)
        feedback = path.parent.parent / "feedback" / contexts.digest(point)
        for relative in [
            "intent/record.json",
            "cohort_seal/record.json",
            "native_rewards/record.json",
        ]:
            p = feedback / relative
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(json.dumps(dict(CPU_fixture=True, point_id=point)))
        manifest = dict(
            schema="v32_read_only_same_point_manifest.v1",
            point_id=point,
            feedback_root=str(feedback),
            checkpoint=str(path),
            seed=state["seed"],
            arm=state["arm"],
            step=state["step"],
            phase="step",
            checkpoint_record=ref["record"],
            checkpoint_state=ref["state"],
            actual_state_digest=ref["actual_state_digest"],
            pre_state_digest=ref["actual_state_digest"],
            denominator=700,
            pending_point_recomputation_required=True,
            new_sampling_allowed=False,
            native_rescoring_allowed=False,
            feedback_files=dict(
                cohort=contexts.file_ref(feedback / "cohort_seal/record.json"),
                rewards=contexts.file_ref(feedback / "native_rewards/record.json"),
            ),
            intent_file=contexts.file_ref(feedback / "intent/record.json"),
            cohort_seal_sha256="CPU_cohort",
            rewards_sha256="CPU_rewards",
        )
        target = (
            root.parent
            / "replay_performance_01/manifests"
            / f"seed{state['seed']}_{contexts.ARMS[state['arm']]}_outer{state['step']}/record.json"
        )
        contexts.publish(target, manifest)
        return target

    return SimpleNamespace(
        root=root,
        outputs=outputs,
        pool=pool,
        rt=rt,
        training=training,
        checkpoint=checkpoint,
        prepare=prepare,
        load=load,
        seal_pending=seal_pending,
        output=output,
    )


@pytest.mark.parametrize("arm,contribution_only,b_n", [("C-only", True, 0.0), ("Full", False, 0.2)])
def test_complete_actual_prestate_arm_schedule_pi_context_and_future_point(
    fixture, arm, contribution_only, b_n
):
    f = fixture
    path, state = f.checkpoint(arm=arm)
    context = f.prepare(path)
    restored, prestate, pool, cache = f.load(context)
    assert restored == context and v8._tree_digest(prestate) == v8._tree_digest(state)
    assert context["checkpoint"]["path"] == str(path)
    assert context["training_root"] == str(f.root)
    assert context["branch"] == dict(
        contribution_only=contribution_only, b_N=b_n, parameters=v8.PARAMETERS
    )
    assert (
        context["feedback"]["mode"] == "first_sampling"
        and context["feedback"]["expected_point_id"] is None
    )
    assert context["task_binding"]["schema"] == "v37_actual_outer_task_gradient_binding.v1"
    assert context["component_digest"]["optimizer"] == v8._tree_digest(state["optimizer"])
    assert context["component_digest"]["rng"] == v8._tree_digest(state["rng"])
    assert context["component_digest"]["schedule"] == v8._tree_digest(state["schedule"])
    assert context["pi"] == state["pi"] and context["prior"] == state["prior"]
    assert (
        len(cache.plan["assignments"]) == 4
        and cache.plan["global_registration"]["mu"] == pool._manifest.registration.mu
    )
    assert contexts.peek_context(context["run_root"]) == context
    assert not torch.cuda.is_initialized()


def test_three_original_sealed_coordinates_bind_own_checkpoint_not_reference298(fixture):
    f = fixture
    for (seed, arm, step), point in contexts.PENDING_SEALED.items():
        done = [value for value in (298, 596, 894, 1192) if value < step]
        path, state = f.checkpoint(seed, arm, step, done, "step")
        manifest_path = f.seal_pending(path, state)
        context = f.prepare(path)
        assert context["feedback"]["mode"] == "sealed_existing"
        assert context["feedback"]["expected_point_id"] == point
        assert context["feedback"]["manifest"] == contexts.entry(manifest_path)
        assert context["task_binding"]["expected_existing_sampling_point_id"] == point
        assert context["task_binding"]["pre_state_digest"] == v8._tree_digest(state)
        f.load(context)


def test_changed_parameter_point_arm_or_full_state_cannot_reuse_committed_task(fixture):
    f = fixture
    path, _state = f.checkpoint()
    context = f.prepare(path)
    _, _, _, cache = f.load(context)
    task = f.pool.task_ids[0]
    values = {"z0": {"weight": torch.tensor([[0.25, -0.5]])}}
    cache.commit(task, values)
    assert cache.has(task) and cache.read(task) is cache.read(task)
    assert cache.verification_summary()["strict_payload_file_reads"] == 1
    for key, changed in [
        ("arm", "C-only"),
        ("step", 596),
        ("pre_state_digest", "other"),
        ("component_digest", {}),
    ]:
        binding = {**context["task_binding"], key: changed}
        wrong = contexts.ProductionTaskCache(
            cache.root,
            binding,
            cache.plan,
            cache.parameter_spec,
            f.rt,
            original_cache_module=original,
        )
        with pytest.raises(ValueError, match="binding/point/source"):
            wrong.read(task)
    legacy = {**context["task_binding"], "schema": "v35_exact_task_gradient_math_binding.v1"}
    with pytest.raises(ValueError, match="reference-point"):
        contexts.ProductionTaskCache(
            cache.root,
            legacy,
            cache.plan,
            cache.parameter_spec,
            f.rt,
            original_cache_module=original,
        )
    with pytest.raises(ValueError, match="every original task"):
        cache.assemble()


def test_original_order_full_population_and_live_verified_values_not_cross_process(fixture):
    f = fixture
    path, _ = f.checkpoint()
    context = f.prepare(path)
    _, _, _, cache = f.load(context)
    for index, task in reversed(list(enumerate(f.pool.task_ids))):
        cache.commit(task, {"z0": {"weight": torch.tensor([[float(index), 1.0]])}})
    assembled = cache.assemble()
    assert list(assembled) == list(f.pool.task_ids)
    assert contexts.inspect_cache(context["run_root"], complete=True)["complete_task_count"] == 4
    assert cache.verification_summary()["strict_payload_file_reads"] == 4
    cache.assemble()
    assert cache.verification_summary()["strict_payload_file_reads"] == 4
    with pytest.raises(TypeError, match="another process"):
        pickle.dumps(cache.verified_state)
    cache.read(f.pool.task_ids[0])["z0"]["weight"].add_(1)
    with pytest.raises(ValueError, match="CPU tensors changed"):
        cache.has(f.pool.task_ids[0])


def test_nonouter_training_context_no_task_plan_and_due_outer_cannot_be_bypassed(fixture):
    f = fixture
    path, _ = f.checkpoint(seed=251, arm="Full", step=419, outer_done=[298], phase="step")
    root = f.output()
    context = contexts.prepare_training_context(
        root,
        path,
        training=f.training,
        rt=f.rt,
        sources={},
        execution_binding=dict(protocol_id="CPU", training_stop_step=596),
    )
    assert context["kind"] == "training" and context["training_stop_step"] == 596
    assert context["task_plan"] is None and not (root / "task_plan").exists()
    assert f.load(context)[3] is None
    due_path, _ = f.checkpoint(seed=389, arm="C-only")
    with pytest.raises(ValueError, match="cannot be bypassed"):
        contexts.prepare_training_context(
            f.output(),
            due_path,
            training=f.training,
            rt=f.rt,
            sources={},
            execution_binding=dict(protocol_id="CPU"),
        )


def test_latest_checkpoint_required_and_completed_outer_never_repeated(fixture):
    f = fixture
    old, _ = f.checkpoint(seed=137, arm="C-only", step=298)
    completed, _ = f.checkpoint(seed=137, arm="C-only", step=298, outer_done=[298], phase="outer")
    with pytest.raises(ValueError, match="latest actual"):
        f.prepare(old)
    with pytest.raises(ValueError, match="due uncommitted"):
        f.prepare(completed)


def test_native_latest_phase_order_preserves_branch_over_same_step(fixture):
    f = fixture
    step, _ = f.checkpoint(phase="step")
    branch, _ = f.checkpoint(phase="branch")
    assert contexts._latest_path(step.parent) == branch


def test_actual_CPU_matrix_accounting_three_pending_and_no_endpoint_access(fixture):
    f = fixture
    matrix = [
        (137, "Static", 1490, []),
        (137, "C-only", 1192, [298, 596, 894]),
        (137, "Full", 1192, [298, 596, 894]),
        (251, "Static", 1490, []),
        (251, "C-only", 894, [298, 596]),
        (251, "Full", 419, [298]),
        (389, "Static", 327, []),
        (389, "C-only", 298, []),
        (389, "Full", 298, []),
    ]
    for seed, arm, step, done in matrix:
        path, state = f.checkpoint(seed, arm, step, done, "step")
        if (seed, arm, step) in contexts.PENDING_SEALED:
            f.seal_pending(path, state)
    result = contexts.production_snapshot(training=f.training, rt=f.rt)
    assert result["completed_physical_updates"] == 5812
    assert result["remaining_physical_updates"] == 5810
    assert result["completed_outers"] == 9 and result["remaining_outers"] == 15
    assert result["pending_sealed_feedback_episodes"] == 2100
    assert (
        result["future_first_sampling_outers"] == 12
        and result["future_first_sampling_feedback_episodes"] == 8400
    )
    assert result["endpoint_scores_or_answers_read"] is False
