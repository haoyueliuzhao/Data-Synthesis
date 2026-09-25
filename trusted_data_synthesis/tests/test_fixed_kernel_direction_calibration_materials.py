"""CPU-only controls for the fixed equal-TV reflection and exact state reuse."""

import copy
import importlib
import json
import random
import sys
from pathlib import Path

import numpy as np
import pytest
import torch

from trusted_synthesis.experiments.finance_qa_vnext_anchored_vtdo import distribution
from trusted_synthesis.experiments.finance_qa_vnext_anchored_vtdo import protocol as ap

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
m = importlib.import_module("fixed_kernel_direction_calibration_materials_20260926")
p = m.p


def rerecord(record, **changes):
    kind = record["id"].split(":")[0]
    maker = ap.record if record["schema_version"].startswith("anchored_vtdo.") else p.record
    return maker(
        kind,
        **{**{k: v for k, v in record.items() if k not in {"id", "schema_version"}}, **changes},
    )


def toy_distribution(seed=11):
    rng = random.Random(seed)
    prior = {"trained": {"a": "1/5", "b": "4/5"}, "control": {"c": "2/5", "d": "3/5"}}
    magnitude = rng.uniform(-1, 1)
    C = {"trained": {"a": magnitude, "b": -magnitude / 4}, "control": {"c": 0, "d": 0}}
    binding = p.record(
        "anchored_sources_material_binding",
        prior=prior,
        mu={"trained": "1/2", "control": "1/2"},
        control_tasks=["control"],
    )
    core = distribution.anchored_update(
        prior, prior, C, binding["mu"], control_tasks=["control"], contribution_only=True
    )
    updated = p.record(
        "anchored_sources_distribution_step", numeric_core_update=core, pi_next=core["pi_next"]
    )
    return binding, updated


def test_reflection_keeps_saved_plus_exact_controls_and_original_marginal():
    for seed in range(40):
        binding, updated = toy_distribution(seed)
        before = copy.deepcopy((binding, updated))
        result = m.reflect(binding, updated)
        arms = result["distributions"]
        assert result["probability_clipping_or_repair"] is False
        assert result["KL_symmetry_claimed"] is False
        assert arms["positive"] == updated["pi_next"]
        assert (
            arms["static"]["control"] == arms["positive"]["control"] == arms["negative"]["control"]
        )
        assert arms["static"]["control"]["c"] == 0.4
        assert result["task_marginal"] == binding["mu"]
        assert (binding, updated) == before
        for task, states in arms["static"].items():
            assert result["per_task"][task]["TV_plus"] == pytest.approx(
                result["per_task"][task]["TV_minus"], abs=1e-12
            )
            for state, r in states.items():
                assert arms["negative"][task][state] == 2 * r - arms["positive"][task][state]
                assert arms["negative"][task][state] > 0
        assert m.REVERSE_RATIO_LOWER > 0.398
        json.dumps(result, allow_nan=False)


@pytest.mark.parametrize(
    "field,value",
    [
        ("epsilon", 0.1),
        ("contribution_exponent", 0.9),
        ("lambda_current", 3),
        ("lambda_prior", 2),
        ("effective_novelty_exponent", 0.2),
        ("contribution_only", False),
        ("probability_clipping_or_repair", True),
    ],
)
def test_formula_bound_not_silently_generalized(field, value):
    binding, updated = toy_distribution()
    core = rerecord(updated["numeric_core_update"], **{field: value})
    updated = rerecord(updated, numeric_core_update=core)
    with pytest.raises(ValueError, match="calibration.formula"):
        m.reflect(binding, updated)


def test_current_must_equal_original_prior_not_just_have_same_support():
    binding, updated = toy_distribution()
    core = copy.deepcopy(updated["numeric_core_update"])
    core["task_diagnostics"]["trained"]["pi_current"] = {"a": 0.3, "b": 0.7}
    updated = rerecord(updated, numeric_core_update=rerecord(core))
    with pytest.raises(ValueError, match="current_equals_original_prior"):
        m.reflect(binding, updated)


@pytest.mark.parametrize("values", [{"a": 0.5, "b": 0.5}, {"a": 0.1, "b": 0.8}, {"a": 0, "b": 1}])
def test_invalid_reflection_rejected_without_clip_or_normalize(values):
    binding, updated = toy_distribution()
    core = copy.deepcopy(updated["numeric_core_update"])
    core["pi_next"]["trained"] = values
    core["task_diagnostics"]["trained"]["pi_next"] = values
    updated = rerecord(updated, numeric_core_update=rerecord(core), pi_next=core["pi_next"])
    with pytest.raises(ValueError, match="positive_simplex_no_repair"):
        m.reflect(binding, updated)


def test_controls_use_strict_original_scalar_equality_not_numeric_tolerance():
    binding, updated = toy_distribution()
    core = copy.deepcopy(updated["numeric_core_update"])
    changed = {"c": 0.4 + 1e-14, "d": 0.6 - 1e-14}
    core["pi_next"]["control"] = changed
    core["task_diagnostics"]["control"]["pi_next"] = changed
    updated = rerecord(updated, numeric_core_update=rerecord(core), pi_next=core["pi_next"])
    with pytest.raises(ValueError, match="exact_controls"):
        m.reflect(binding, updated)


def saved_rng(step):
    generator = torch.Generator(device="cpu").manual_seed(11)
    return dict(
        cpu=generator.get_state(),
        cuda=[generator.get_state()],
        python=random.Random(11).getstate(),
        numpy=np.random.RandomState(11).get_state(),
        schedule_cursor=step,
    )


def tiny_checkpoint(tmp_path):
    model = torch.nn.Linear(1, 1, bias=False)
    optimizer = torch.optim.AdamW(model.parameters())
    for _ in range(2):
        optimizer.zero_grad()
        model.weight.square().sum().backward()
        optimizer.step()
    names = dict(model.named_parameters())
    bound = m.b.old.adam.bind_adamw(names, optimizer, clip_max_norm=1)
    state = {}
    for row in bound.parameters:
        for name, value in (
            ("theta", row.theta),
            ("first_moment", row.first),
            ("second_moment", row.second),
        ):
            state[name + "/" + row.name] = value.detach().cpu().clone()
    update = p.record("optimizer_update", test=True)
    saved = dict(
        kind="B_shared_training_state",
        plan_id="plan",
        job_key="job",
        completed_updates=2,
        snapshot=bound.snapshot,
        state=state,
        rng=saved_rng(2),
        update_report=update,
    )
    path = tmp_path / "jobs/job/updates/0002.pt"
    m.b.s.atomic_torch(path, saved)
    p.write_once(path.with_suffix(".json"), update)
    return path, saved


def test_checkpoint_uses_actual_Adam_tensors_and_complete_RNG_without_GPU(tmp_path):
    path, saved = tiny_checkpoint(tmp_path)
    before = torch.get_rng_state().clone()
    ref, snapshot = m._checkpoint(tmp_path, {"id": "plan"}, "job", 2)
    assert snapshot == saved["snapshot"]
    assert ref["sha256"] == p.sha(path)
    assert ref["RNG_binding"]["schedule_cursor"] == 2
    assert torch.equal(before, torch.get_rng_state())
    assert ref["parameters_Adam_and_RNG_verified"]


@pytest.mark.parametrize("corruption", ["tensor", "cursor", "cuda", "update"])
def test_checkpoint_corruption_has_no_reuse_credit(tmp_path, monkeypatch, corruption):
    _, saved = tiny_checkpoint(tmp_path)
    if corruption == "tensor":
        saved["state"]["first_moment/weight"].add_(1)
    elif corruption == "cursor":
        saved["rng"]["schedule_cursor"] = 3
    elif corruption == "cuda":
        saved["rng"]["cuda"] = []
    else:
        saved["update_report"] = p.record("optimizer_update", test=False)
    monkeypatch.setattr(m.b.torch, "load", lambda *a, **k: saved)
    with pytest.raises(ValueError):
        m._checkpoint(tmp_path, {"id": "plan"}, "job", 2)


def toy_history():
    tasks = [f"t{i}" for i in range(200)]
    packages = [dict(package_id=task, task_id=task, coefficient_float=1 / 5) for task in tasks]
    batches = [dict(step=i, task_ids=tasks[i % 40 * 5 : (i % 40 + 1) * 5]) for i in range(400)]
    plan = dict(
        materials=dict(
            schedules={"11": dict(batches=batches)},
            training_groups=dict.fromkeys(tasks, "control"),
            trajectory_cache=dict(manifest_id="cache"),
        )
    )
    reports = {}
    ids = [None] * 400
    for step in range(201, 241):
        chosen = batches[step - 1]["task_ids"]
        record = p.record(
            "optimizer_update",
            pool="B",
            arm="static",
            cache_id="cache",
            tasks=[dict(task_id=task, group="control") for task in chosen],
            packages=[row for row in packages if row["task_id"] in chosen],
            optimizer_step_calls=1,
            clip_calls=1,
            zero_grad_calls=1,
            additional_loss_scaling=False,
            loss_rule="pi(state|task)/(5*n_state*whole_package_target_tokens)",
            execution_design="trajectory_prefix_union_v1",
        )
        reports[step] = record
        ids[step - 1] = record["id"]
    return plan, packages, reports, {"update_report_ids": ids}


def test_reused_40_updates_cover_all_original_packages_once(monkeypatch):
    plan, packages, reports, report = toy_history()
    monkeypatch.setattr(p, "read_json", lambda path: reports[int(path.stem)])
    result = m._history(Path("/synthetic"), plan, 11, "static", packages, report)
    assert result["updates"] == len(result["update_report_ids"]) == 40


@pytest.mark.parametrize("corruption", ["coefficient", "package", "schedule", "extra_scaling"])
def test_history_refuses_distribution_material_or_schedule_changes(monkeypatch, corruption):
    plan, packages, reports, report = toy_history()
    row = copy.deepcopy(reports[201])
    if corruption == "coefficient":
        row["packages"][0]["coefficient_float"] += 1e-15
    elif corruption == "package":
        row["packages"][0]["package_id"] = "not-original"
    elif corruption == "schedule":
        row["tasks"] = list(reversed(row["tasks"]))
    else:
        row["additional_loss_scaling"] = True
    reports[201] = rerecord(row)
    report["update_report_ids"][200] = reports[201]["id"]
    monkeypatch.setattr(p, "read_json", lambda path: reports[int(path.stem)])
    with pytest.raises(ValueError):
        m._history(Path("/synthetic"), plan, 11, "static", packages, report)


def test_failure_before_admission_does_not_load_checkpoints_or_authorize_retraining(
    tmp_path, monkeypatch
):
    def refuse(*args):
        raise ValueError("incomplete original B")

    monkeypatch.setattr(m, "_completed_plan", refuse)
    monkeypatch.setattr(m.b, "load_training", lambda *a, **k: pytest.fail("must not load"))
    with pytest.raises(ValueError, match="incomplete original B"):
        m.admit(tmp_path, tmp_path)
