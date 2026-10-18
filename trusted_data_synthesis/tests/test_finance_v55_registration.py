from types import SimpleNamespace

import pytest

import finqa_v54_controller as controller
import finqa_v54_evaluation as evaluation
import finqa_v55_registration as registration


def original_parent(seed=137):
    return dict(id=f"old-parent-{seed}", schema="v54_actual_parent.v1", protocol_id="old-protocol",
        seed=seed, parent_checkpoint=dict(path="real-parent", state_sha256="parameter+Adam+RNG"),
        old_outer_checkpoint=dict(path="old-outer"), parent_state_digest="real-state",
        component_digests=dict(pi="actual-pi", rng="actual-rng"), parent_pi=dict(x=[0.2, 0.8]),
        task_plan=dict(path="old-task-plan", sha256="bound-plan"),
        old_class_context=None if seed != 389 else dict(path="original-389-cache"),
        new_class_task_count=744 if seed != 389 else 0,
        c1_reuse=dict(eligible=True, q_digest="old-q", snapshots={"745": "old745", "894": "old894"}))


def test_parent_recovery_changes_only_protocol_and_explicit_lineage():
    old = original_parent()
    body = registration.inherited_parent_body(old, "new-protocol", dict(path="old-parent-record"), dict(path="old-prepared"))
    assert body["protocol_id"] == "new-protocol"
    assert body["task_plan"] == old["task_plan"]
    assert body["c1_reuse"] == old["c1_reuse"]
    assert registration.validate_inherited_parent(body, old, "new-protocol", dict(path="old-parent-record"),
                                                  dict(path="old-prepared")) == body
    body["parent_pi"]["x"][0] = 1
    assert old["parent_pi"]["x"][0] == 0.2
    with pytest.raises(ValueError, match="only protocol_id"):
        registration.validate_inherited_parent(body, old, "new-protocol", dict(path="old-parent-record"), dict(path="old-prepared"))


@pytest.mark.parametrize("field", ["parent_checkpoint", "component_digests", "c1_reuse", "task_plan"])
def test_parent_lineage_cannot_hide_changed_scientific_field(field):
    old = original_parent()
    body = registration.inherited_parent_body(old, "new", {}, {})
    body[field] = dict(unregistered="replacement")
    with pytest.raises(ValueError, match="only protocol_id"):
        registration.validate_inherited_parent(body, old, "new", {}, {})


def test_only_explicit_recovery_root_selects_new_registration():
    assert controller.registration_module_name(controller.DEFAULT_ROOT) == "finqa_v54_registration"
    assert controller.registration_module_name(controller.DEFAULT_ROOT / "recovery_01") == "finqa_v55_registration"
    with pytest.raises(ValueError, match="unregistered"):
        controller.registration_module_name(controller.DEFAULT_ROOT / "recovery_02")
    assert len(registration.FILES) == 10
    assert 81 + len(registration.FILES) == 91


def test_controller_inherits_old_wait_without_worker_double_counting(tmp_path):
    parents = {}
    for seed in (137, 251, 389):
        body = original_parent(seed)
        body.pop("id")
        body["protocol_id"] = "new-protocol"
        path = tmp_path / f"parents/seed{seed}/record.json"
        evaluation.publish(path, body)
        parents[str(seed)] = evaluation.file_binding(path)
    protocol = dict(id="new-protocol", gpu_uuids={str(i): f"uuid{i}" for i in range(8)},
        gpu_lease_root=str(controller.GPU_LEASE_ROOT), max_gpu_workers=4, gpu_priority=list(range(8)),
        inherited_resource_wait_seconds=89.84583379887044)
    fake = SimpleNamespace(checked_protocol=lambda root: protocol, checked_implementation=lambda root: {},
                           checked_prepared=lambda root: dict(parents=parents))
    value = controller.Controller(tmp_path, runtime=SimpleNamespace(), registration=fake)
    assert value.resource_wait_seconds == 89.84583379887044
    assert len(value.core) == 23
    assert len([j for j in value.core.values() if j["kind"] == "train"]) == 6


def recovery_fixture(tmp_path, monkeypatch, *, wait=89.84583379887044):
    old_root, root = tmp_path / "original", tmp_path / "original/recovery_01"
    monkeypatch.setattr(registration, "OLD_ROOT", old_root)
    monkeypatch.setattr(registration, "ROOT", root)
    old_body = dict(scientific_contract=registration.base.scientific_contract(),
        evaluation=evaluation.evaluation_contract(), source_parent_checkpoints={"mock": "old-points"},
        evaluation_source_registration={"mock": "original-evaluator"}, training_source_registration={"mock": "original-training"},
        resource_policy=dict(old_without_CUBLAS=True))
    old = evaluation.publish(old_root / "protocol/record.json", old_body)
    closeout = evaluation.publish(old_root / "closeout/record.json", dict(resource_wait_seconds=89.84583379887044))
    monkeypatch.setattr(registration, "OLD_PROTOCOL_ID", old["id"])
    monkeypatch.setattr(registration, "OLD_CLOSEOUT_ID", closeout["id"])
    parent_refs = {str(seed): dict(path=f"old-parent-{seed}", sha256=f"hash-{seed}") for seed in (137, 251, 389)}
    evaluation.publish(old_root / "prepared/record.json", dict(parents=parent_refs))
    inheritance = dict(protocol=registration.entry(old_root / "protocol/record.json"),
        controller_closeout=registration.entry(old_root / "closeout/record.json"),
        prepared=registration.entry(old_root / "prepared/record.json"))
    evaluation.publish(root / "implementation/record.json", dict(schema=registration.IMPLEMENTATION_SCHEMA))
    authorization = dict(old_root=str(old_root), recovery_root=str(root),
        old_protocol=evaluation.file_binding(old_root / "protocol/record.json"),
        old_closeout=evaluation.file_binding(old_root / "closeout/record.json"),
        seeds={str(seed): dict(old_parent=parent_refs[str(seed)]) for seed in (137, 251, 389)})
    monkeypatch.setattr(registration, "_guard_module", lambda: SimpleNamespace(checked_authorization=lambda value: value))
    protocol = evaluation.publish(root / "protocol/record.json", dict(schema=registration.SCHEMA,
        output_root=str(root), **{k: v for k, v in old_body.items() if k != "resource_policy"},
        recovery_contract=registration.recovery_contract(), resource_policy=registration.runtime.resource_policy(),
        gpu_uuids=registration.runtime.GPU_UUIDS, allowed_gpu_indices=list(range(8)), max_gpu_workers=4,
        max_workers_per_gpu=1, cpu_affinity=registration.runtime.CPU_AFFINITY,
        gpu_lease_root=str(registration.base.TRAINING_ROOT / "locks"), gpu_priority=list(range(8)),
        parents={str(seed): str(root / f"parents/seed{seed}/record.json") for seed in (137, 251, 389)},
        inherited_experiment=inheritance, inherited_resource_wait_seconds=wait,
        implementation=registration.entry(root / "implementation/record.json"), feedback_recovery=authorization))
    return root, protocol


def test_new_protocol_keeps_old_policy_as_history_and_uses_current_CUBLAS_policy(tmp_path, monkeypatch):
    root, protocol = recovery_fixture(tmp_path, monkeypatch)
    assert registration.checked_protocol(root) == protocol
    assert protocol["resource_policy"] == registration.runtime.resource_policy()


def test_recovery_protocol_cannot_reset_historical_resource_wait(tmp_path, monkeypatch):
    root, _ = recovery_fixture(tmp_path, monkeypatch, wait=0)
    with pytest.raises(ValueError, match="must not reset"):
        registration.checked_protocol(root)


def test_success_closeout_requires_two_actual_returned_receipts(tmp_path):
    control = controller.Controller.__new__(controller.Controller)
    control.root, control.protocol = tmp_path, dict(id="protocol", feedback_recovery=dict(id="authority"))
    for seed in (137, 389):
        directory = tmp_path / f"feedback_recovery/seed{seed}"
        claim = evaluation.publish(directory / "claim/record.json", dict(protocol_id="protocol",
            authorization_id="authority", seed=seed, authorized_reexecution_ordinal=1))
        if seed == 137:
            evaluation.publish(directory / "resolution/record.json", dict(protocol_id="protocol",
                authorization_id="authority", seed=seed, claim_id=claim["id"], new_actual_model_calls=1,
                old_unknown_record_preserved=True, old_unknown_reclassified=False))
    partial = control.feedback_recovery_accounting()
    assert len(partial["actual_claims"]) == 2 and partial["actual_returned_reexecution_calls"] == 1
    assert partial["old_unknowns_reclassified"] is False
    with pytest.raises(ValueError, match="actual returned receipts"):
        control.feedback_recovery_accounting(require_complete=True)


@pytest.mark.parametrize("changed_c1_parent", [False, True])
def test_inherited_prepared_accepts_real_C1_publication_and_rejects_old_parent_id(tmp_path, monkeypatch, changed_c1_parent):
    import finqa_v54_training as training

    old_refs = {}
    for seed in (137, 251, 389):
        plan = tmp_path / f"old/task_plan{seed}/record.json"
        evaluation.publish(plan, dict(task_count=744))
        old = original_parent(seed)
        old.pop("id")
        old["task_plan"] = registration.entry(plan)
        path = tmp_path / f"old/parents/seed{seed}/record.json"
        evaluation.publish(path, old)
        old_refs[str(seed)] = registration.entry(path)
    old_prepared_path = tmp_path / "old/prepared/record.json"
    old_prepared = evaluation.publish(old_prepared_path, dict(parents=old_refs))
    monkeypatch.setattr(registration, "OLD_PREPARED_ID", old_prepared["id"])
    old_prepared_ref = registration.entry(old_prepared_path)
    root = tmp_path / "old/recovery_01"
    protocol = evaluation.publish(root / "protocol/record.json", dict(
        inherited_experiment=dict(prepared=old_prepared_ref),
        parents={str(seed): str(root / f"parents/seed{seed}/record.json") for seed in (137, 251, 389)}))
    monkeypatch.setattr(registration, "checked_protocol", lambda path: protocol)
    parents, branches = {}, {}
    for seed in (137, 251, 389):
        source = registration.read_ref(old_refs[str(seed)])
        body = registration.inherited_parent_body(source, protocol["id"], old_refs[str(seed)], old_prepared_ref)
        path = root / f"parents/seed{seed}/record.json"
        evaluation.publish(path, body)
        parents[str(seed)] = registration.entry(path)
        result = training.publish_c1_reuse(root, seed, protocol["id"])
        branch_path = root / f"branches/seed{seed}/C1/completed/record.json"
        if changed_c1_parent and seed == 137:
            # Publish a separately bound mock record with the forbidden old
            # parent identity, without overwriting the original fixture record.
            result.pop("id")
            result["training_binding"]["parent_id"] = source["id"]
            branch_path = root / "invalid_branch/record.json"
            evaluation.publish(branch_path, result)
        branches[f"seed{seed}/C1"] = registration.entry(branch_path)
    evaluation.publish(root / "prepared/record.json", dict(schema=registration.PREPARED_SCHEMA,
        protocol=registration.entry(root / "protocol/record.json"), original_prepared=old_prepared_ref,
        parents=parents, c1_branches=branches, actual_new_optimizer_budget=1788,
        new_feedback_sessions=2100, new_evaluation_sessions=12267, total_new_sessions=14367))
    if changed_c1_parent:
        with pytest.raises(ValueError, match="original complete training proof"):
            registration.checked_prepared(root)
    else:
        assert registration.checked_prepared(root)["actual_new_optimizer_budget"] == 1788
