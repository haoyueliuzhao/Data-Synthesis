"""Small dependency/authority controls, no production data, model, wallet or GPU."""

import copy

import pytest

from trusted_synthesis.finance_research import v10_training, v15_continuation, v15_material
from trusted_synthesis.finance_research import v15_prefix_material as prefix
from trusted_synthesis.finance_research import v15_workflow as workflow


def tiny_inputs():
    packages = [dict(package_id="a", task_id="t", whole_package_target_tokens=1, fused=False)]
    rows = [
        dict(row_sha256="zero", input_ids=[1], target_ids=[]),
        dict(row_sha256="positive", input_ids=[1, 2], target_ids=[2]),
    ]
    return packages, {"a": dict(rows=rows)}


def test_prefix_pool_has_no_partition_and_preserves_actual_row_order():
    packages, encodings = tiny_inputs()
    value = prefix.PrefixPool(
        task_ids=["t"],
        packages=packages,
        encodings=encodings,
        binding_ref=dict(id="test"),
        token_binding=["tok", "tmpl"],
        material_order_id=prefix.material_order_identity(["t"], packages, encodings),
        production=False,
    )
    assert not any(hasattr(value, key) for key in ("pi", "prior", "chi", "_manifest"))
    assert "state_id" not in value.packages[0]
    assert [r["row_sha256"] for r in value.row_arrays("a")] == ["positive"]
    assert len(value._encodings["a"]["rows"]) == 2
    assert value.full_training_admitted is value.conditional_scope_verified is False


def test_prefix_refuses_even_a_single_temporary_state():
    packages, encodings = tiny_inputs()
    packages[0]["state_id"] = "temporary"
    with pytest.raises(ValueError, match="no fabricated state"):
        prefix.PrefixPool(
            task_ids=["t"],
            packages=packages,
            encodings=encodings,
            binding_ref=dict(id="test"),
            token_binding=[],
            material_order_id="unused",
            production=False,
        )


def test_original_zero_target_row_order_is_bound_too():
    packages, encodings = tiny_inputs()
    order = prefix.material_order_identity(["t"], packages, encodings)
    encodings["a"]["rows"].reverse()
    with pytest.raises(ValueError, match="order changed"):
        prefix.PrefixPool(
            task_ids=["t"],
            packages=packages,
            encodings=encodings,
            binding_ref=dict(id="test"),
            token_binding=[],
            material_order_id=order,
            production=False,
        )


def test_prefix_binding_is_not_a_complete_training_dispatch(monkeypatch):
    monkeypatch.setattr(v10_training, "read_json", lambda p: dict(schema=prefix.BINDING_SCHEMA))
    with pytest.raises(ValueError, match="unknown real material binding"):
        v10_training.load_training_pool("synthetic")
    marker = object()
    monkeypatch.setattr(
        v10_training, "read_json", lambda p: dict(schema=v15_material.BINDING_SCHEMA)
    )
    monkeypatch.setattr(v15_material, "load_training_pool", lambda p: marker)
    assert v10_training.load_training_pool("synthetic") is marker


def test_new_derived_mapping_consumption_does_not_modify_raw_record(monkeypatch):
    record = dict(
        schema="v15_derived_mapping.v1",
        usable=True,
        inspection=dict(
            mapping_status="complete",
            mapping_admitted=True,
            states=[dict(semantic_summary=None)],
            state_by_slot={"p": "z", "q": "z"},
            chi_by_state={"z": 0},
        ),
    )
    original = copy.deepcopy(record)
    monkeypatch.setattr(v15_material, "read_ref", lambda ref: record)
    view = v15_material.authority_mapping(dict(task_id="t", record={}), {"t": ["p", "q"]})
    assert record == original and view["deterministic_singleton"] is False
    assert view["states"][0]["semantic_summary"] is None


def condition_fixture(tmp_path, monkeypatch):
    binding = dict(
        schema=v15_material.BINDING_SCHEMA,
        material_root=str(tmp_path),
        registration={"id": "mapping"},
        prefix_material_binding={"id": "prefix"},
    )
    intent = dict(
        schema="v15_pre_student_continuation_intent.v1",
        at="2026-09-30T00:00:00+00:00",
        decision="proceed_exploratory_if_complete_nontrivial_material",
        mapping_plan={"id": "mapping"},
        prefix_material_binding={"id": "prefix"},
        no_student_started_at_registration=True,
        scope_confirmed=True,
        student_results_used=False,
    )
    scale = dict(
        schema="v15_prospective_condition_realization.v1",
        prospective_intent={},
        decision_fixed_before_prefix=True,
        no_new_research_scale_decision=True,
        material_identity={"N": 744},
        student_results_used=False,
    )
    monkeypatch.setattr(v15_continuation, "read_ref", lambda ref: intent)
    monkeypatch.setattr(
        v15_continuation,
        "checked",
        lambda path: binding if str(path) == "binding" else dict(at="2026-09-30T00:01:00+00:00"),
    )
    return binding, intent, scale


def test_condition_realization_preserves_true_pre_prefix_intent(tmp_path, monkeypatch):
    _, intent, scale = condition_fixture(tmp_path, monkeypatch)
    assert v15_continuation.validate_condition_realization(scale, "binding", {"N": 744})
    intent["at"] = "2026-09-30T00:02:00+00:00"
    with pytest.raises(ValueError, match="before actual Student"):
        v15_continuation.validate_condition_realization(scale, "binding", {"N": 744})


def test_condition_realization_refuses_changed_mask_binding_or_student_selection(
    tmp_path, monkeypatch
):
    binding, _, scale = condition_fixture(tmp_path, monkeypatch)
    binding["prefix_material_binding"] = {"id": "different-mask"}
    with pytest.raises(ValueError, match="identical complete material"):
        v15_continuation.validate_condition_realization(scale, "binding", {"N": 744})
    binding["prefix_material_binding"] = {"id": "prefix"}
    scale["student_results_used"] = True
    with pytest.raises(ValueError, match="identical complete material"):
        v15_continuation.validate_condition_realization(scale, "binding", {"N": 744})


def test_mapping_failure_does_not_block_genuine_prefix_jobs(tmp_path, monkeypatch):
    ctl = workflow.Supervisor.__new__(workflow.Supervisor)
    ctl.output, ctl.root = tmp_path, tmp_path / "workflow"
    ctl.workflow = dict(allowed_gpu_indices=[0, 1, 2], minimum_free_mib=24576)
    ctl.max_gpu_workers, ctl.children, ctl.stop = 3, {}, False
    complete, launched, phases = set(), [], []
    monkeypatch.setattr(workflow, "marker_complete", lambda path: str(path) in complete)
    monkeypatch.setattr(
        workflow, "gpu_inventory", lambda: [dict(index=i, free=40000) for i in (0, 1, 2)]
    )
    monkeypatch.setattr(workflow.time, "sleep", lambda seconds: None)
    ctl.update = lambda phase, **kw: phases.append(phase)

    def launch(job, gpu=None):
        launched.append(job["key"])
        ctl.children[job["key"]] = dict(job=job, gpu=gpu)

    def reap():
        failures = []
        for key, child in list(ctl.children.items()):
            if child["gpu"] is None:
                failures.append(dict(key=key, completed=False))
            else:
                complete.add(str(child["job"]["result"]))
            del ctl.children[key]
        return failures

    ctl.launch, ctl.reap = launch, reap
    assert ctl.parallel_prefix_and_mapping() is False
    assert launched == ["fixed54-adjudication", "prefix-seed11", "prefix-seed29", "prefix-seed47"]
    assert phases[-1] == "PREFIX_OR_MAPPING_SAVED"
    assert len(complete) == 3


def test_finished_prefix_without_full_binding_cannot_branch(tmp_path, monkeypatch):
    ctl = workflow.Supervisor.__new__(workflow.Supervisor)
    ctl.output = tmp_path
    ctl.parallel_prefix_and_mapping = lambda: True
    phases = []
    ctl.update = lambda phase, **kw: phases.append((phase, kw))
    monkeypatch.setattr(workflow, "checked", lambda path: dict(phase="BLOCKED_MAPPING"))
    monkeypatch.setattr(v15_continuation, "register_and_migrate", lambda *a, **kw: 1 / 0)
    assert ctl.run() is None
    assert phases[-1][0] == "COMMON_PREFIX_COMPLETE_WAITING_FOR_MAPPING"
    assert phases[-1][1]["no_branch_or_feedback_started"]


def test_prefix_schedule_matches_existing_full_pool_order():
    from trusted_synthesis.finance_research.v9_conditional_training import build_task_schedule

    tasks = [f"task-{i:03d}" for i in range(744)]
    schedule = build_task_schedule(tasks, 11)
    assert len(schedule["batches"][:298]) == 298
    assert schedule["batches"][148]["actual_batch_size"] == 4
    assert schedule["batches"][297]["actual_batch_size"] == 4
    assert sum(len(b["task_ids"]) for b in schedule["batches"][:298]) == 1488
