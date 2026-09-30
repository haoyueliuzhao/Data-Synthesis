"""Fixed three-task lineage and shared handoff controls, without API/GPU/real tensors."""

import copy
from pathlib import Path

import pytest

from trusted_synthesis.finance_research import v10_training
from trusted_synthesis.finance_research import v16_continuation as continuation
from trusted_synthesis.finance_research import v16_material as shared
from trusted_synthesis.finance_research import v17_material as material


def predecessor_fixture(monkeypatch, tmp_path):
    tasks = [f"t{i}" for i in range(744)]
    slots = {t: [f"{t}-p{j}" for j in range(5 if t == "t743" else 4)] for t in tasks}
    mappings = {t: dict(mapping_status="complete", mapping_admitted=True) for t in tasks[:738]}
    mappings.update({t: dict(mapping_status="failed", mapping_admitted=False) for t in tasks[738:]})
    authorities = {t: {"id": "original-" + t} for t in tasks}
    history = dict(mappings=mappings, authorities=authorities, failed=set(tasks[738:]))
    fields = dict(
        source_root="v15",
        source_registration={"id": "v15-plan"},
        source_completion_seal={"id": "v15-seal"},
        source_support={"id": "v15-support"},
        source_frozen_root="c0",
        prospective_intent={"id": "intent"},
        prefix_material_binding={"id": "prefix"},
        fixed_task_slots=slots,
    )
    parent = dict(fields, id="v16-definition", at="2026-09-30T00:01:00+00:00")
    terminal_refs, jobs, records = [], [], {}
    next_authorities = copy.deepcopy(authorities)
    for i, task in enumerate(tasks[738:]):
        request_ref, record_ref, terminal_ref = (
            {"id": f"request{i}"},
            {"id": f"record{i}"},
            {"id": f"terminal{i}"},
        )
        request = {"task_id": task}
        records[request_ref["id"]] = request
        records[record_ref["id"]] = dict(
            schema="v16_paid_material_annotation.v1",
            actual_model_call_receipt_verified=True,
            request=request,
            inspection=dict(
                mapping_status="complete" if i < 3 else "failed", mapping_admitted=i < 3
            ),
        )
        records[terminal_ref["id"]] = dict(
            task_id=task,
            registration_id="v16-plan",
            terminal_kind="paid_model_return",
            record=record_ref,
        )
        terminal_refs.append(terminal_ref)
        jobs.append(dict(task_id=task, request=request_ref))
        next_authorities[task] = record_ref
    records["v16-definition"] = parent
    records["v16-plan"] = dict(
        schema="v16_six_task_adjudication_plan.v1",
        id="v16-plan",
        model="deepseek-flash",
        definition={"id": "v16-definition"},
        protocol_identity="v16-definition",
        jobs=jobs,
        source_bindings={"old.py": "old-sha"},
    )
    records["v16-seal"] = dict(
        registration_id="v16-plan",
        protocol_id="v16-definition",
        all_registered_jobs_have_authentic_terminals=True,
        actual_returns=6,
        expected_calls=6,
        network_unknowns=0,
        terminals=terminal_refs,
    )
    records["v16-support"] = dict(task_support={t: {} for t in tasks[:741]})
    definition = dict(
        fields,
        at="2026-09-30T00:02:00+00:00",
        predecessor_root=str(tmp_path),
        predecessor_registration={"id": "v16-plan"},
        predecessor_definition={"id": "v16-definition"},
        predecessor_completion_seal={"id": "v16-seal"},
        predecessor_support={"id": "v16-support"},
        predecessor_frozen_root="599bb28",
        fixed_unresolved_task_ids=tasks[741:],
        inherited_mapping_authorities={t: next_authorities[t] for t in tasks[:741]},
        previous_failed_authorities={t: next_authorities[t] for t in tasks[741:]},
    )
    entries = {
        str(tmp_path / "registration/record.json"): {"id": "v16-plan"},
        str(tmp_path / "completion_seal/record.json"): {"id": "v16-seal"},
        str(tmp_path / "material/support/record.json"): {"id": "v16-support"},
    }
    monkeypatch.setattr(material, "read_ref", lambda ref: records[ref["id"]])
    monkeypatch.setattr(material, "entry", lambda path: entries[str(path)])
    monkeypatch.setattr(material, "sha", lambda path: "old-sha")
    monkeypatch.setattr(shared, "historical_context", lambda value: copy.deepcopy(history))
    return definition, records


def test_three_successors_preserve_actual_741_and_all_six_old_returns(monkeypatch, tmp_path):
    definition, records = predecessor_fixture(monkeypatch, tmp_path)
    before = copy.deepcopy((definition, records))
    result = material.historical_context(definition)
    assert len(result["authorities"]) == 744
    assert len(result["failed"]) == 3
    assert sum(len(definition["fixed_task_slots"][t]) for t in result["failed"]) == 13
    assert (definition, records) == before


@pytest.mark.parametrize("change", ["old741", "failed-source", "source-code", "backdate", "subset"])
def test_predecessor_refuses_relabeling_or_changed_scope(monkeypatch, tmp_path, change):
    definition, records = predecessor_fixture(monkeypatch, tmp_path)
    if change == "old741":
        definition["inherited_mapping_authorities"]["t740"] = {"id": "replacement"}
    elif change == "failed-source":
        definition["previous_failed_authorities"]["t743"] = {"id": "replacement"}
    elif change == "source-code":
        monkeypatch.setattr(material, "sha", lambda path: "new-current-code-not-old-frozen")
    elif change == "backdate":
        definition["at"] = records["v16-definition"]["at"]
    else:
        definition["fixed_unresolved_task_ids"] = ["t741", "t742"]
    with pytest.raises(ValueError):
        material.historical_context(definition)


def test_v17_complete_loader_dispatch(monkeypatch):
    marker = object()
    monkeypatch.setattr(
        v10_training, "read_json", lambda path: dict(schema=material.BINDING_SCHEMA)
    )
    monkeypatch.setattr(material, "load_training_pool", lambda path: marker)
    assert v10_training.load_training_pool("synthetic") is marker


def test_v17_uses_exact_three_receipts_and_v17_provider(monkeypatch):
    calls = []
    monkeypatch.setattr(shared, "successor_results", lambda *args, **kwargs: calls.append(kwargs))
    material.successor_results("output", {}, {})
    assert calls[0]["expected_calls"] == 3
    assert calls[0]["paid_schema"] == "v17_paid_material_annotation.v1"
    assert calls[0]["receipt_verifier"] is material.verify_successor_receipt


def test_mechanism_registration_precedes_every_zero_update_migration(monkeypatch, tmp_path):
    from trusted_synthesis.finance_research import v9_mechanism_execution as mechanisms
    from trusted_synthesis.finance_research import v9_training_launcher as launcher
    from trusted_synthesis.finance_research import v15_prefix_training as prefix

    order = []
    definition = dict(
        prospective_intent={"id": "intent"},
        source_registration={"id": "original"},
        source_root=str(tmp_path / "original"),
    )
    binding = dict(definition={"id": "definition"}, registration={"id": "new"})
    monkeypatch.setattr(
        continuation,
        "checked",
        lambda path: (
            dict(
                continuation_intent_id="intent",
                source_bindings={"v9_mechanism_execution.py": "mechanism-sha"},
            )
            if "original/workflow" in str(path)
            else binding
        ),
    )
    monkeypatch.setattr(continuation, "sha", lambda path: "mechanism-sha")
    monkeypatch.setattr(continuation, "read_ref", lambda ref: definition)
    monkeypatch.setattr(continuation, "entry", lambda path: {"path": str(path)})
    monkeypatch.setattr(continuation, "persist", lambda *args: None)
    monkeypatch.setattr(
        continuation,
        "completed_prefixes",
        lambda definition: {
            seed: dict(result={"id": f"result{seed}"}, checkpoint=f"seed{seed}")
            for seed in (11, 29, 47)
        },
    )
    monkeypatch.setattr(launcher, "material_identity", lambda pool: {"N": 744})
    monkeypatch.setattr(launcher, "file_binding", lambda path: {"path": str(path)})
    monkeypatch.setattr(
        launcher, "register", lambda *args, **kw: order.append("launcher") or {"id": "launcher"}
    )
    monkeypatch.setattr(mechanisms, "register", lambda *args: order.append("mechanisms"))
    monkeypatch.setattr(
        prefix,
        "migrate_prefix_checkpoint",
        lambda point, *args: order.append(point) or {"migrated_checkpoint": {}},
    )
    result = continuation.register_and_migrate(
        tmp_path,
        allowed_gpu_indices=[0],
        lineage_validator=lambda *args: {"id": "intent"},
        prefix_loader=lambda *args: object(),
        pool_loader=lambda *args: object(),
    )
    assert order == ["launcher", "mechanisms", "seed11", "seed29", "seed47"]
    assert result["optimizer_steps_during_migration"] == 0
    assert result["first_formal_outer_required_before_C_or_Full_step299"] is True


def test_v17_reuses_exact_fifteen_arm_tail_and_mainline():
    from trusted_synthesis.finance_research import v16_workflow, v17_workflow

    assert (
        v17_workflow.Supervisor.run_remaining_mainline
        is v16_workflow.Supervisor.run_remaining_mainline
    )
    ctl = v17_workflow.Supervisor.__new__(v17_workflow.Supervisor)
    jobs = ctl.arm_jobs(Path("synthetic-missing-launcher"))
    assert len(jobs) == 15 and ctl.scope_label == "THREE_TASK"
    assert {job["args"][-1] for job in jobs} == set(continuation.ARMS)
