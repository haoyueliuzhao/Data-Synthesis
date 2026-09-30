"""Small successor-source controls, no real wallet/model/GPU or production mutation."""

import copy
from pathlib import Path

import pytest

from trusted_synthesis.finance_research import v10_training
from trusted_synthesis.finance_research import v16_continuation as continuation
from trusted_synthesis.finance_research import v16_material as material
from trusted_synthesis.finance_research import v16_workflow as workflow


def lineage_fixture(monkeypatch, tmp_path):
    inherited = {f"task{i}": {"id": f"old{i}"} for i in range(738)}
    failed = {f"task{i}": {"id": f"failed{i}"} for i in range(738, 744)}
    definition = dict(
        schema="v16_six_task_definition.v1",
        source_root=str(tmp_path),
        at="2026-09-30T00:02:00+00:00",
        prospective_intent={"id": "intent"},
        source_registration={"id": "old-registration"},
        prefix_material_binding={"id": "prefix"},
        inherited_mapping_authorities=inherited,
        previous_failed_authorities=failed,
        fixed_unresolved_task_ids=list(failed),
        student_results_used=False,
    )
    binding = dict(
        schema=material.BINDING_SCHEMA,
        original_registration=definition["source_registration"],
        prefix_material_binding=definition["prefix_material_binding"],
        prospective_intent=definition["prospective_intent"],
        inherited_mapping_authorities=copy.deepcopy(inherited),
        previous_failed_authorities=copy.deepcopy(failed),
        successor_task_ids=list(failed),
        fixed_arms=continuation.ARMS,
        fixed_seeds=list(continuation.SEEDS),
        feedback_denominator=700,
    )
    intent = dict(
        schema="v15_pre_student_continuation_intent.v1",
        id="intent",
        at="2026-09-30T00:00:00+00:00",
        mapping_plan=definition["source_registration"],
        prefix_material_binding=definition["prefix_material_binding"],
        decision="proceed_exploratory_if_complete_nontrivial_material",
        no_student_started_at_registration=True,
        scope_confirmed=True,
        student_results_used=False,
        arms=continuation.ARMS,
        seeds=list(continuation.SEEDS),
        require_actual_prefix_step=298,
        feedback_denominator=700,
        dev_tasks=883,
    )
    monkeypatch.setattr(continuation, "read_ref", lambda ref: intent)
    monkeypatch.setattr(continuation, "checked", lambda path: dict(at="2026-09-30T00:01:00+00:00"))
    return binding, definition, intent


def test_narrow_successor_preserves_real_original_intent(monkeypatch, tmp_path):
    binding, definition, intent = lineage_fixture(monkeypatch, tmp_path)
    originals = copy.deepcopy((binding, definition, intent))
    assert continuation.validate_lineage(binding, definition) is intent
    assert (binding, definition, intent) == originals


@pytest.mark.parametrize(
    "mutation",
    [
        "backdated-successor",
        "late-intent",
        "changed-old-authority",
        "changed-old-registration",
        "changed-prefix",
        "Student-selection",
    ],
)
def test_lineage_refuses_rewriting_history_or_selection(monkeypatch, tmp_path, mutation):
    binding, definition, intent = lineage_fixture(monkeypatch, tmp_path)
    if mutation == "backdated-successor":
        definition["at"] = intent["at"]
    elif mutation == "late-intent":
        intent["at"] = definition["at"]
    elif mutation == "changed-old-authority":
        binding["inherited_mapping_authorities"]["task0"] = {"id": "replacement"}
    elif mutation == "changed-old-registration":
        binding["original_registration"] = {"id": "new-registration"}
    elif mutation == "changed-prefix":
        binding["prefix_material_binding"] = {"id": "different-mask"}
    else:
        definition["student_results_used"] = True
    with pytest.raises(ValueError):
        continuation.validate_lineage(binding, definition)


def test_complete_loader_dispatch_is_explicit(monkeypatch):
    marker = object()
    monkeypatch.setattr(v10_training, "read_json", lambda p: dict(schema=material.BINDING_SCHEMA))
    monkeypatch.setattr(material, "load_training_pool", lambda p: marker)
    assert v10_training.load_training_pool("synthetic") is marker


def test_metadata_gate_requires_all_three_actual298(monkeypatch, tmp_path):
    from trusted_synthesis.finance_research import v15_prefix_training as prefix

    steps = {11: 298, 29: 297, 47: 298}

    def ref(path):
        seed = next(s for s in steps if f"seed{s}" in str(path))
        return {"step": steps[seed], "path": str(path)}

    def finished(path):
        seed = next(s for s in steps if f"seed{s}" in str(path))
        point = Path(path).parent.parent / "shared/step0298_step"
        return dict(
            schema="v15_prior_prefix_seed_result.v1",
            seed=seed,
            complete_prefix=True,
            checkpoint=ref(point),
            actual=dict(committed_step=steps[seed], consumption=dict(updates=steps[seed])),
        )

    monkeypatch.setattr(continuation, "checked", finished)
    monkeypatch.setattr(prefix, "latest_checkpoint", lambda root: root / "step0298_step")
    monkeypatch.setattr(prefix, "checkpoint_ref", ref)
    with pytest.raises(ValueError, match="all three actual"):
        continuation.completed_prefixes(dict(source_root=str(tmp_path)))
    steps[29] = 298
    assert set(continuation.completed_prefixes(dict(source_root=str(tmp_path)))) == {11, 29, 47}


def test_incomplete_six_stops_successor_without_touching_prefix(monkeypatch, tmp_path):
    ctl = workflow.Supervisor.__new__(workflow.Supervisor)
    ctl.output, ctl.workflow, ctl.stop = (
        tmp_path,
        dict(original_prefix_root=str(tmp_path / "old")),
        False,
    )
    phases = []
    ctl.update = lambda phase, **kw: phases.append((phase, kw))
    monkeypatch.setattr(workflow, "marker_complete", lambda path: True)
    monkeypatch.setattr(workflow, "checked", lambda path: {"training_admitted": False})
    monkeypatch.setattr(workflow, "entry", lambda path: {"path": str(path)})
    monkeypatch.setattr(workflow.time, "sleep", lambda n: pytest.fail("must stop without retry"))
    assert ctl.wait_for_inputs() is False
    assert phases[-1][1]["original_prefix_control_untouched"] is True
    assert phases[-1][1]["no_retry"] is True


def test_fifteen_tail_jobs_keep_five_arms_and_prioritize_formal_outer(tmp_path):
    ctl = workflow.Supervisor.__new__(workflow.Supervisor)
    jobs = ctl.arm_jobs(tmp_path)
    assert len(jobs) == len({j["key"] for j in jobs}) == 15
    assert all(j["module"] == "v16_arm_training" for j in jobs)
    assert {j["args"][-1] for j in jobs} == set(continuation.ARMS)
    assert [j["args"][-1] for j in jobs[:6]] == ["C-only"] * 3 + ["Full"] * 3
    assert all(j["args"][0] == "run-arm" for j in jobs)
    assert not any("prefix" in j["key"] for j in jobs)


def test_api_failure_without_seal_stops_no_retry_and_no_prefix_control(monkeypatch, tmp_path):
    ctl = workflow.Supervisor.__new__(workflow.Supervisor)
    ctl.output, ctl.workflow, ctl.stop = (
        tmp_path,
        dict(original_prefix_root=str(tmp_path / "old")),
        False,
    )
    ctl.plan = {"id": "six-plan"}
    phases = []
    ctl.update = lambda phase, **kw: phases.append((phase, kw))
    monkeypatch.setattr(workflow, "marker_complete", lambda path: "controller_result" in str(path))
    monkeypatch.setattr(
        workflow,
        "checked",
        lambda path: {"registration_id": "six-plan", "phase": "SAVED_FAILURE_NO_RETRY"},
    )
    monkeypatch.setattr(workflow, "entry", lambda path: {"path": str(path)})
    monkeypatch.setattr(
        workflow.time, "sleep", lambda n: pytest.fail("must not wait forever or retry")
    )
    assert ctl.wait_for_inputs() is False
    assert phases[-1][0] == "SIX_TASK_API_FAILURE_SAVED_PREFIX_UNTOUCHED"
    assert phases[-1][1]["original_prefix_control_untouched"] is True
    assert phases[-1][1]["no_branch_or_feedback_started"] is True


def test_no_material_no_gpu_queue_or_tensor_load(monkeypatch, tmp_path):
    ctl = workflow.Supervisor.__new__(workflow.Supervisor)
    ctl.output = tmp_path
    ctl.wait_for_inputs = lambda: False
    monkeypatch.setattr(
        continuation, "register_and_migrate", lambda *a, **kw: pytest.fail("must not migrate")
    )
    assert ctl.run() is None
