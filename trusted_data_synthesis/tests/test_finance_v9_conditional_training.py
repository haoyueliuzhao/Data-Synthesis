"""Synthetic parent contracts and actual small CPU updates; never production evidence."""

import copy
import json
from collections import Counter
from fractions import Fraction
from types import SimpleNamespace

import pytest
import torch

from trusted_synthesis.finance_research.materials import TaskBatch, task_batch_examples
from trusted_synthesis.finance_research.providers import parameter_digest
from trusted_synthesis.finance_research.v8_training_driver import REVIEW_POLICY_ID, installed_point
from trusted_synthesis.finance_research.v9_conditional_training import (
    ConditionalTrainingDriver,
    _bound,
    _check_production_returns,
    build_support_manifest,
    build_task_schedule,
    execution_plan,
    load_training_pool,
    tiny_cpu_pool,
    validate_execution_schedule,
)


class TinyModel(torch.nn.Module):
    def __init__(self):
        super().__init__()
        self.weight = torch.nn.Parameter(torch.arange(20, dtype=torch.float32).reshape(4, 5) / 10)

    def forward(self, input_ids, attention_mask, use_cache, logits_to_keep):
        return SimpleNamespace(logits=self.weight[input_ids][:, logits_to_keep])


def material(N):
    tasks = [f"q{i}" for i in range(N)]
    packages, rows, chi = [], {}, {}
    for task in tasks:
        chi[task] = {"z0": 0, "z1": 1}
        for index, state in enumerate(("z0", "z0", "z1")):
            sid = f"{task}/s{index}"
            packages.append(
                dict(
                    package_id=sid,
                    task_id=task,
                    state_id=state,
                    whole_package_target_tokens=2,
                    fused=False,
                )
            )
            rows[sid] = [dict(input_ids=[0, 1, 2], target_positions=[1, 2], target_ids=[1, 2])]
    return tiny_cpu_pool(tasks, packages, rows, chi=chi)


def driver(path, N=7, arm="shared", model=None):
    model = model or TinyModel()
    return ConditionalTrainingDriver(
        model,
        torch.optim.AdamW(model.parameters(), lr=1e-4, weight_decay=0),
        material(N),
        root=path,
        seed=11,
        arm=arm,
    )


@pytest.mark.parametrize("N", [1, 4, 5, 7, 819, 820, 1000])
def test_schedule_exact_ten_epochs_and_real_tail(N):
    tasks = [f"t{i}" for i in range(N)]
    schedule = build_task_schedule(tasks, 11)
    plan = execution_plan(N)
    assert plan["steps_per_epoch"] == (N + 4) // 5
    assert len(schedule["batches"]) == plan["final_step"] == 10 * ((N + 4) // 5)
    assert Counter(t for b in schedule["batches"] for t in b["task_ids"]) == Counter(
        {t: 10 for t in tasks}
    )
    for epoch in range(1, 11):
        batches = [b for b in schedule["batches"] if b["epoch"] == epoch]
        assert len(batches[-1]["task_ids"]) == plan["tail_batch_size"]
        assert Counter(t for b in batches for t in b["task_ids"]) == Counter(tasks)
    assert plan["feedback_denominator"] == 700
    validate_execution_schedule(plan, schedule, tasks, 11)
    changed = copy.deepcopy(schedule)
    changed["batches"][-1]["task_ids"] = [tasks[0]] * 5
    with pytest.raises(ValueError, match="schedule changed"):
        validate_execution_schedule(plan, changed, tasks, 11)


def test_tail_actual_weight_real_update_and_exact_resume(tmp_path):
    run = driver(tmp_path / "first")
    assert set(run.pool._manifest.registration.mu.values()) == {"1/7"}
    run.step()
    checkpoint = run.root / "step0001_step"
    tail = run.schedule["batches"][1]
    assert len(tail["task_ids"]) == 2
    batch = TaskBatch(
        task_ids=tuple(tail["task_ids"]),
        sampling_probability={t: "1/7" for t in run.pool.task_ids},
        sampling_design="uniform_epoch_permutation",
        schedule_id="control",
        step=2,
    )
    examples = task_batch_examples(run.pool, run.pi, batch)
    assert {Fraction(p["target_token_coefficient"]) for p in examples} == {Fraction(1, 12)}
    report = run.step()
    assert report["batch_size"] == 2 and report["packages_completed"] == 6
    assert report["optimizer_step_calls"] == report["clip_calls"] == 1
    assert report["additional_batch_division"] is False
    expected = parameter_digest(run.parameters)
    resumed = driver(tmp_path / "resume")
    resumed.restore(checkpoint)
    assert resumed.step()["weighted_loss"] == report["weighted_loss"]
    assert parameter_digest(resumed.parameters) == expected


def test_actual_dynamic_shared_prefix_and_manual_branches(tmp_path):
    shared = driver(tmp_path / "shared")
    assert shared.shared_step == 4 and shared.outer_steps == (4, 8, 12, 16)
    shared.run_until(shared.shared_step)
    assert shared.optimizer.state[shared.model.weight]["step"].item() == 4
    with pytest.raises(ValueError, match="arm complete"):
        shared.step()
    checkpoint = shared.root / "step0004_step"
    plus, minus = (
        driver(tmp_path / "plus", arm="Manual+"),
        driver(tmp_path / "minus", arm="Manual-"),
    )
    plus.restore(checkpoint, branch=True)
    minus.restore(checkpoint, branch=True)
    assert plus.pi["q0"] == pytest.approx({"z0": 0.5, "z1": 0.5})
    assert minus.pi["q0"] == pytest.approx({"z0": 0.8, "z1": 0.2})
    blocked = driver(tmp_path / "full", arm="Full")
    blocked.restore(checkpoint, branch=True)
    with pytest.raises(ValueError, match="sealed outer"):
        blocked.step()
    plus.run_until(plus.final_step)
    assert plus.step_index == 20 and plus.optimizer.state[plus.model.weight]["step"].item() == 20


def test_real_conditional_outer_keeps_actual_mu_and_zero_feedback_rule(tmp_path):
    from test_finance_research_feedback import episode, seal
    from test_finance_research_providers import Model, Tokenizer

    from trusted_synthesis.finance_research.providers import (
        LocalTorchProvider,
        local_model_identity,
    )

    class Combined(TinyModel, Model):
        def __init__(self):
            TinyModel.__init__(self)
            self.generation_config = SimpleNamespace(eos_token_id=2)
            self.calls = 0

    shared = driver(tmp_path / "shared", model=Combined())
    shared.run_until(4)
    run = driver(tmp_path / "full", arm="Full", model=Combined())
    run.restore(shared.root / "step0004_step", branch=True)
    original, real_adam_step = (
        copy.deepcopy(run.pi),
        run.optimizer.state[run.model.weight]["step"].item(),
    )

    def collect(prepared, point_id):
        with installed_point(run.model, prepared["theta_bar"]) as theta:
            tokenizer = Tokenizer()
            identity = local_model_identity(
                run.model,
                tokenizer,
                model_id="CPU_conditional_control",
                point_id=point_id,
                parameter_tensors=theta,
            )
            local = LocalTorchProvider(run.model, tokenizer, identity, parameter_tensors=theta)
            episodes = [episode(local, seed=i) for i in (1, 2)]
            return seal(episodes, identity), [0, 0]

    result = run.outer_update(cpu_control_feedback=collect)
    assert result["distribution"]["status"] == "UNINFORMATIVE_FEEDBACK"
    assert run.pi == original and run.outer_done == [4]
    assert run.optimizer.state[run.model.weight]["step"].item() == real_adam_step
    run.step()
    assert run.step_index == 5


def population():
    tasks = [f"q{i}" for i in range(1000)]
    slots = [dict(task_id=t, slot_id=f"{t}/s{i}", slot_index=i) for t in tasks for i in range(8)]
    eligible = ["q0/s0", "q0/s1", "q1/s0"]
    parent = {
        key: dict(path=key, sha256="f" * 64, id=key)
        for key in ("generation_protocol", "generation_seal", "native_support")
    }
    jobs = [dict(key=f"slot:{sid}:{r}") for sid in eligible for r in (0, 1)]
    jobs += [dict(key=f"alignment:{task}:{r}") for task in tasks[:2] for r in (0, 1)]
    protocol = _bound(
        dict(
            schema="v9_conditional_production_protocol.v1",
            model="deepseek-flash",
            review_policy_id=REVIEW_POLICY_ID,
            parent=parent,
            original_task_ids=tasks,
            slots=slots,
            native_eligible_slot_ids=eligible,
            native_supported_task_ids=tasks[:2],
            slot_review_denominator=6,
            alignment_denominator=4,
            maximum_calls=10,
            jobs=jobs,
        )
    )
    completion = _bound(
        dict(
            schema="v9_production_completion_seal.v1",
            protocol_id=protocol["id"],
            parent_launch_id="generation_protocol",
            parent_generation_seal_id="generation_seal",
            native_support_id="native_support",
            expected_requests=10,
            completed_requests=10,
            slot_review_denominator=6,
            alignment_denominator=4,
            all_registered_returns_present=True,
            all_original_slots_retained=True,
            jobs=jobs,
        )
    )
    resolutions, encodings = {}, {}
    for task in tasks:
        rows = {}
        for i in range(8):
            sid = f"{task}/s{i}"
            valid = sid in eligible
            rows[sid] = dict(
                q_native=valid,
                v_trace="valid" if valid else "not_assessed_native_ineligible",
                common_material_valid=valid,
                mapper="mapped" if valid else "ineligible",
                state_id=f"z{i}" if valid else None,
                chi=i if valid else None,
                encoding_manifest={"mask_agreement": True} if valid else None,
            )
            if valid:
                encodings[sid] = dict(
                    schema="v8_student_encoding.v1",
                    task_id=task,
                    encoding_policy="v8_single_authoritative_targets.v1",
                    encoding_admitted=True,
                    context_truncated=False,
                    context_limit=24576,
                    L_P=3,
                    total_supervised_tokens=3,
                    failures=[],
                    rows=[dict(layer_target_positions={"reason": [1], "tool": [2], "final": [3]})],
                )
        resolutions[task] = dict(
            schema="v8_common_material_resolution.v1",
            task_id=task,
            review_policy_id=REVIEW_POLICY_ID,
            slots=rows,
            all_eight_candidates_retained=True,
            valid_slots_retained=[sid for sid in rows if sid in eligible],
            task_mapping="complete",
            no_dropping_hard_to_map_valid_packages=True,
        )
    return protocol, completion, resolutions, encodings


def test_support_freeze_retains_singletons_and_original_denominator():
    protocol, completion, resolutions, encodings = population()
    support = build_support_manifest(protocol, completion, resolutions, encodings)
    assert support["N"] == 2 and support["training_task_ids"] == ["q0", "q1"]
    assert support["mu"] == {"q0": "1/2", "q1": "1/2"}
    assert len(support["excluded_tasks"]) == 998 and support["original_slot_denominator"] == 8000
    profile = support["capability_profile"]
    assert profile["D_pi"] == 1 and profile["M_flex"] == "1/2"
    assert profile["chi_flexible_tasks"] == 1 and profile["one_state_tasks"] == 1
    assert profile["singleton_package_tasks"] == 1
    assert profile["supervised_tokens"] == {"reason": 3, "tool": 3, "final": 3}
    assert profile["five_arm_algebraic_distinguishability_possible"] is True
    assert profile["power_established"] is False


@pytest.mark.parametrize(
    "failure",
    [
        "missing_resolution",
        "missing_package",
        "hard_mapping",
        "overlength",
        "prefix",
        "qfalse",
        "chi",
    ],
)
def test_no_scope_freeze_by_dropping_hard_package_or_tail(failure):
    protocol, completion, resolutions, encodings = population()
    if failure == "missing_resolution":
        del resolutions["q999"]
    elif failure == "missing_package":
        del encodings["q0/s1"]
    elif failure == "hard_mapping":
        resolutions["q0"]["task_mapping"] = "unknown"
    elif failure == "overlength":
        encodings["q0/s1"]["encoding_admitted"] = False
    elif failure == "prefix":
        completion["completed_requests"] = 9
        completion = _bound({k: v for k, v in completion.items() if k != "id"})
    elif failure == "qfalse":
        resolutions["q2"]["slots"]["q2/s0"]["v_trace"] = "invalid"
    else:
        resolutions["q0"]["slots"]["q0/s1"]["chi"] = 3
    with pytest.raises(ValueError):
        build_support_manifest(protocol, completion, resolutions, encodings)


def test_single_state_inventory_is_retained_not_five_arm_identification():
    protocol, completion, resolutions, encodings = population()
    resolutions["q0"]["slots"]["q0/s1"].update(state_id="z0", chi=0)
    support = build_support_manifest(protocol, completion, resolutions, encodings)
    assert support["N"] == 2 and len(support["joint_valid_slot_ids"]) == 3
    assert support["capability_profile"]["D_pi"] == 0
    assert support["capability_profile"]["five_arm_algebraic_distinguishability_possible"] is False


def test_complete_production_matrix_recomputes_valid_not_model_label():
    protocol, completion, _, _ = population()
    jobs, returned, artifacts = [], [], {}
    coords = [
        ("slot", sid.split("/")[0], sid, r)
        for sid in protocol["native_eligible_slot_ids"]
        for r in (0, 1)
    ]
    coords += [
        ("alignment", task, None, r)
        for task in protocol["native_supported_task_ids"]
        for r in (0, 1)
    ]
    for index, (stage, task, sid, reviewer) in enumerate(coords):
        key = str(index)
        job = dict(key=key, stage=stage, task_id=task, slot_id=sid, reviewer=reviewer)
        jobs.append(job)
        returned.append(
            job
            | dict(request_sha256=key, response={"path": key + "r"}, assessment={"path": key + "a"})
        )
        validation = dict(
            review_request_sha256=key,
            alignment_request_sha256=key,
            review_policy_id=REVIEW_POLICY_ID,
            reviewer=reviewer,
            task_id=task,
            slot_id=sid,
            interface_admitted=True,
            semantic_consistent=True,
            v_trace="valid",
            derived={},
        )
        artifacts[key + "r"] = {"semantic_review_request_sha256": key}
        artifacts[key + "a"] = dict(
            interface_admitted=True, semantic_consistent=True, validation=validation
        )
    protocol = _bound({**{k: v for k, v in protocol.items() if k != "id"}, "jobs": jobs})
    completion = _bound(
        {
            **{k: v for k, v in completion.items() if k != "id"},
            "protocol_id": protocol["id"],
            "jobs": returned,
        }
    )

    def read(entry):
        return artifacts[entry["path"]]

    assert _check_production_returns(protocol, completion, read) == set(
        protocol["native_eligible_slot_ids"]
    )
    # A self-reported valid whose finite validation is inconsistent is not joint-valid.
    artifacts["1a"]["semantic_consistent"] = False
    assert "q0/s0" not in _check_production_returns(protocol, completion, read)
    completion["jobs"] = completion["jobs"][:-1]
    completion = _bound({k: v for k, v in completion.items() if k != "id"})
    with pytest.raises(ValueError, match="complete registered production job manifest"):
        _check_production_returns(protocol, completion, read)


def test_loader_fails_before_any_model_for_missing_or_unbound_material(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_training_pool(tmp_path / "absent.json")
    artifact = tmp_path / "parent.json"
    artifact.write_text("{}")
    binding = tmp_path / "binding.json"
    binding.write_text(
        json.dumps(
            dict(
                schema="v9_conditional_training_binding.v1",
                review_policy_id=REVIEW_POLICY_ID,
                generation_protocol={"path": str(artifact), "sha256": "0" * 64},
            )
        )
    )
    with pytest.raises(ValueError, match="byte SHA"):
        load_training_pool(binding)
    with pytest.raises(ValueError, match="test-only"):
        model = TinyModel()
        ConditionalTrainingDriver(
            model,
            torch.optim.AdamW(model.parameters()),
            material(1),
            root=tmp_path / "gpu",
            seed=11,
            device="cuda",
        )
