"""No-API researcher successor controls; held V17 material is never unheld."""

import copy
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from trusted_synthesis.finance_research import v10_training
from trusted_synthesis.finance_research import v18_material as material


def history_fixture(monkeypatch, tmp_path):
    old_root = tmp_path / "v17"
    retained = sorted(material.RETAINED_V17_TASKS)
    fixed = [f"task{i}" for i in range(741)] + [material.ABMD] + retained
    groups = {t: [f"{t}-p{i}" for i in range(4)] for t in fixed}
    original = {t: {"id": "old-" + t} for t in fixed}
    history = dict(
        authorities=copy.deepcopy(original),
        failed={material.ABMD, *retained},
        mappings={t: dict(mapping_status="complete", mapping_admitted=True) for t in fixed},
    )
    fields = dict(
        source_root="v15",
        source_registration={"id": "v15-plan"},
        source_frozen_root="c0",
        source_completion_seal={"id": "v15-seal"},
        source_support={"id": "v15-support"},
        prospective_intent={"id": "intent"},
        prefix_material_binding={"id": "prefix"},
        fixed_task_slots=groups,
    )
    records, jobs, terminals = {}, [], []
    authorities = copy.deepcopy(original)
    for i, task in enumerate([material.ABMD] + retained):
        request_ref, record_ref, terminal_ref = (
            {"id": f"request{i}"},
            {"id": f"paid{i}"},
            {"id": f"terminal{i}"},
        )
        records[request_ref["id"]] = dict(task_id=task)
        records[record_ref["id"]] = dict(
            schema="v17_paid_material_annotation.v1",
            actual_model_call_receipt_verified=True,
            request=records[request_ref["id"]],
            inspection=dict(
                mapping_status="complete",
                mapping_admitted=True,
                source_marker="held-invalid" if i == 0 else task,
            ),
        )
        records[terminal_ref["id"]] = dict(
            task_id=task,
            registration_id="v17-plan",
            terminal_kind="paid_model_return",
            record=record_ref,
        )
        jobs.append(dict(task_id=task, request=request_ref))
        terminals.append(terminal_ref)
        authorities[task] = record_ref
    records["v17-definition"] = dict(fields, id="v17-definition", at="2026-09-30T00:00:00+00:00")
    records["v17-plan"] = dict(
        id="v17-plan",
        schema="v17_three_task_adjudication_plan.v1",
        definition={"id": "v17-definition"},
        protocol_identity="v17-definition",
        source_bindings={"old.py": "frozen-sha"},
        jobs=jobs,
    )
    records["v17-seal"] = dict(
        registration_id="v17-plan",
        protocol_id="v17-definition",
        actual_returns=3,
        expected_calls=3,
        network_unknowns=0,
        all_registered_jobs_have_authentic_terminals=True,
        terminals=terminals,
    )
    records["revoked"] = dict(
        id="revoked",
        schema=material.predecessor.BINDING_SCHEMA,
        material_root=str(old_root),
        definition={"id": "v17-definition"},
        registration={"id": "v17-plan"},
        completion_seal={"id": "v17-seal"},
        prefix_material_binding=fields["prefix_material_binding"],
        mapping_authorities=authorities,
    )
    records["hold"] = dict(
        id="hold",
        schema="v17_explicit_semantic_admission_hold.v1",
        at="2026-09-30T00:01:00+00:00",
        revoked_binding={"id": "revoked"},
        registration={"id": "v17-plan"},
        task_id=material.ABMD,
        paid_source=authorities[material.ABMD],
        original_prefix_must_continue=True,
        no_replacement_partition_or_chi_supplied=True,
    )
    definition = dict(
        fields,
        at="2026-09-30T00:02:00+00:00",
        source_v17_registration={"id": "v17-plan"},
        source_v17_definition={"id": "v17-definition"},
        source_v17_completion_seal={"id": "v17-seal"},
        source_v17_revoked_binding={"id": "revoked"},
        source_v17_admission_hold={"id": "hold"},
        source_v17_frozen_root="d1ea",
        fixed_unresolved_task_ids=[material.ABMD],
        inherited_mapping_authorities={
            t: ref for t, ref in authorities.items() if t != material.ABMD
        },
        previous_failed_authorities={material.ABMD: authorities[material.ABMD]},
        researcher_authority={"id": "researcher"},
    )
    monkeypatch.setattr(material, "read_ref", lambda ref: records[ref["id"]])
    monkeypatch.setattr(
        material,
        "entry",
        lambda path: {"id": "hold" if "admission_hold" in str(path) else "revoked"},
    )
    monkeypatch.setattr(material, "sha", lambda path: "frozen-sha")
    monkeypatch.setattr(
        material.predecessor, "historical_context", lambda parent: copy.deepcopy(history)
    )
    return definition, records


def test_743_inherited_but_held_ABMD_inspection_is_never_used(monkeypatch, tmp_path):
    definition, records = history_fixture(monkeypatch, tmp_path)
    before = copy.deepcopy((definition, records))
    result = material.historical_context(definition)
    assert len(definition["inherited_mapping_authorities"]) == 743
    assert result["mappings"][material.ABMD] is None
    assert result["authorities"][material.ABMD] == records["hold"]["paid_source"]
    assert result["failed"] == {material.ABMD}
    assert (definition, records) == before


@pytest.mark.parametrize(
    "change", ["hold-removed", "hold-source", "inherited-authority", "backdated"]
)
def test_hold_and_exact_inherited_authorities_cannot_be_removed_or_changed(
    monkeypatch, tmp_path, change
):
    definition, records = history_fixture(monkeypatch, tmp_path)
    if change == "hold-removed":
        del records["hold"]
    elif change == "hold-source":
        records["hold"]["paid_source"] = {"id": "other"}
    elif change == "inherited-authority":
        definition["inherited_mapping_authorities"]["task0"] = {"id": "replacement"}
    else:
        definition["at"] = records["hold"]["at"]
    with pytest.raises((ValueError, KeyError)):
        material.historical_context(definition)


def test_new_binding_cannot_be_written_into_old_held_root(monkeypatch, tmp_path):
    definition, _ = history_fixture(monkeypatch, tmp_path)
    with pytest.raises(ValueError, match="held V17 material root"):
        material.binding_body(tmp_path / "v17", dict(definition=definition))


def test_researcher_result_uses_named_no_API_authority_and_keeps_unresolved(monkeypatch):
    inspection = dict(mapping_status="unresolved", mapping_admitted=False)
    calls = []
    authority_module = SimpleNamespace(
        load_authority=lambda ref, groups: calls.append((ref, groups)) or inspection
    )
    monkeypatch.setitem(
        sys.modules, "trusted_synthesis.finance_research.v18_researcher_authority", authority_module
    )
    monkeypatch.setattr(
        material.shared,
        "successor_results",
        lambda *args, **kw: pytest.fail("no paid provider path"),
    )
    definition = dict(
        researcher_authority={"id": "named-Codex"},
        fixed_task_slots={material.ABMD: ["p0", "p1", "p2", "p3"]},
    )
    seal = dict(
        schema="v18_researcher_adjudication_seal.v1",
        registration_id="plan",
        protocol_id="protocol",
        authority=definition["researcher_authority"],
        expected_model_calls=0,
        actual_model_calls=0,
    )
    monkeypatch.setattr(material, "checked", lambda path: seal)
    _, results = material.researcher_results(
        "synthetic", dict(id="plan", protocol_identity="protocol"), definition
    )
    assert calls == [(definition["researcher_authority"], definition["fixed_task_slots"])]
    assert results[material.ABMD]["inspection"]["mapping_admitted"] is False
    assert "chi_by_state" not in results[material.ABMD]["inspection"]


def test_v18_schema_dispatch_does_not_reuse_revoked_V17_loader(monkeypatch):
    marker = object()
    monkeypatch.setattr(
        v10_training, "read_json", lambda path: dict(schema=material.BINDING_SCHEMA)
    )
    monkeypatch.setattr(material, "load_training_pool", lambda path: marker)
    monkeypatch.setattr(
        material.predecessor,
        "load_training_pool",
        lambda path: pytest.fail("held binding never loaded"),
    )
    assert v10_training.load_training_pool("new-v18") is marker


def test_v18_reuses_original_fifteen_arm_mainline():
    from trusted_synthesis.finance_research import v16_workflow, v18_workflow

    assert (
        v18_workflow.Supervisor.run_remaining_mainline
        is v16_workflow.Supervisor.run_remaining_mainline
    )
    ctl = v18_workflow.Supervisor.__new__(v18_workflow.Supervisor)
    assert len(ctl.arm_jobs(Path("new-v18-no-checkpoints"))) == 15


def registration_fixture(monkeypatch, tmp_path):
    from trusted_synthesis.finance_research import v18_registration as registration
    from trusted_synthesis.finance_research.v6_collection import bound, persist

    task_ids = [material.ABMD] + [f"task{i}" for i in range(743)]
    groups = {
        task: [f"{task}-p{j}" for j in range(4 if i < 236 else 3)]
        for i, task in enumerate(task_ids)
    }
    definition = bound(
        dict(
            schema="v18_researcher_continuation_definition.v1",
            researcher_authority={"id": "named-source"},
            source_root="original-v15",
            source_registration={"id": "original-plan"},
            fixed_unresolved_task_ids=[material.ABMD],
            fixed_task_slots=groups,
            inherited_mapping_authorities={task: {"id": task} for task in task_ids[1:]},
            judgment_source_kind=registration.KIND,
            actual_judgment_source="Codex, not human; no API return",
            api_model_policy="deepseek-flash",
            authorized_API_calls=0,
            API_calls=0,
            API_count_scope="external paid API only; research judgment participated",
            student_results_used=False,
        )
    )
    persist(tmp_path / "definition", definition)
    monkeypatch.setattr(registration, "source_bindings", lambda: {"test-source": "fixed-sha"})
    monkeypatch.setattr(
        registration, "checked_researcher_authority", lambda definition: dict(inspection={})
    )
    return registration, definition


def test_no_API_registration_explicitly_records_Codex_judgment(monkeypatch, tmp_path):
    from trusted_synthesis.finance_research.v13_material_registration import checked

    registration, _ = registration_fixture(monkeypatch, tmp_path)
    plan = registration.register(tmp_path)
    assert registration.checked_plan(tmp_path) == plan
    assert registration.register(tmp_path) == plan
    assert not any(key in plan for key in ("jobs", "model", "budget_database", "provider"))
    assert plan["api_model_policy"] == "deepseek-flash" and plan["authorized_API_calls"] == 0
    seal = checked(tmp_path / "completion_seal/record.json")
    assert seal["expected_model_calls"] == seal["actual_model_calls"] == 0
    assert seal["Codex_research_judgment_participated"] is True
    assert seal["human_judgment"] is False and seal["not_a_paid_model_return"] is True


@pytest.mark.parametrize(
    "field,value",
    [
        ("authorized_API_calls", 1),
        ("api_model_policy", "another-model"),
        ("model", "deepseek-flash"),
    ],
)
def test_researcher_plan_cannot_grant_API_or_claim_a_paid_model(
    monkeypatch, tmp_path, field, value
):
    registration, definition = registration_fixture(monkeypatch, tmp_path)
    plan = registration.register(tmp_path)
    changed = dict(plan, **{field: value})
    monkeypatch.setattr(registration, "checked", lambda path: changed)
    monkeypatch.setattr(registration, "read_ref", lambda reference: definition)
    with pytest.raises(ValueError, match="no paid API stage"):
        registration.checked_plan(tmp_path)
