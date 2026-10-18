from copy import deepcopy

import pytest

import finqa_v56_registration as registration


def test_recovery_scope_keeps_science_and_consumed_allowances():
    contract = registration.recovery_contract()
    assert len(registration.FILES) == 15
    assert 81 + len(registration.FILES) == 96
    assert contract["inherited_complete_feedback_episodes"] == 70
    assert contract["inherited_partial_returned_turns"] == 3
    assert contract["prior_two_request_reexecution_allowances_remaining"] == 0
    assert contract["new_UNKNOWN_call_automatic_retry_allowed"] is False
    assert contract["remaining_optimizer_updates"] == 1788
    assert contract["remaining_feedback_episodes"] == 2030
    assert contract["remaining_new_class_tasks"] == 1479
    assert contract["evaluation_sessions"] == 12267


def test_parent_inheritance_only_rebinds_protocol_and_read_only_lineage():
    parent = dict(id="old-parent", protocol_id="old-protocol", seed=137,
        component_digests=dict(theta="parameters", optimizer="moments", rng="RNG"),
        task_plan=dict(path="frozen-plan", sha256="plan-hash"),
        parent_pi=dict(task=dict(state="1/2")), recovery_lineage=dict(earlier="retained by source ref"))
    original = deepcopy(parent)
    value = registration.inherited_parent_body(parent, "new-protocol", dict(path="old-parent"), dict(path="old-prepared"))
    assert parent == original
    assert value["protocol_id"] == "new-protocol"
    assert value["component_digests"] == parent["component_digests"]
    assert value["parent_pi"] == parent["parent_pi"]
    assert value["task_plan"] == parent["task_plan"]
    assert value["recovery_lineage"]["source_parent_id"] == "old-parent"
    value["parent_pi"]["task"]["state"] = "1"
    assert parent == original


def prepared_fixture(tmp_path, monkeypatch, changes=None):
    root, old = tmp_path / "new", tmp_path / "old"
    pub, ref = registration.publish, registration.entry
    plan = old / "plan/record.json"
    pub(plan, dict(schema="CPU_fixture_task_plan"))
    old_parents = {}
    for seed in registration.science.SEEDS:
        directory = old / f"parents/seed{seed}/record.json"
        pub(directory, dict(schema="v54_actual_parent.v1", seed=seed,
            protocol_id="old-protocol", parent_state_digest=f"parent-{seed}",
            parent_pi=dict(task=dict(state="1")), task_plan=ref(plan),
            c1_reuse=dict(eligible=True, q_digest=f"q-{seed}",
                          snapshots={"745": dict(step=745), "894": dict(step=894)})))
        old_parents[str(seed)] = ref(directory)
    old_prepared = pub(old / "prepared/record.json", dict(parents=old_parents))
    monkeypatch.setattr(registration, "OLD_PREPARED_ID", old_prepared["id"])
    protocol = pub(root / "protocol/record.json", dict(
        inherited_experiment=dict(prepared=ref(old / "prepared/record.json")),
        parents={str(seed): str(root / f"parents/seed{seed}/record.json")
                 for seed in registration.science.SEEDS}))
    monkeypatch.setattr(registration, "checked_protocol", lambda given: protocol)
    parents, branches = {}, {}
    for seed in registration.science.SEEDS:
        source = old_parents[str(seed)]
        body = registration.inherited_parent_body(registration.read_ref(source), protocol["id"],
                                                 source, ref(old / "prepared/record.json"))
        parent = pub(root / f"parents/seed{seed}/record.json", body)
        parents[str(seed)] = ref(root / f"parents/seed{seed}/record.json")
        pub(root / f"branches/seed{seed}/C1/completed/record.json", dict(
            protocol_id=protocol["id"], status="COMPLETE", seed=seed, arm="C1",
            optimizer_updates=298, new_optimizer_updates=0,
            parent_state_digest=parent["parent_state_digest"],
            snapshots=parent["c1_reuse"]["snapshots"], distribution_digest=parent["c1_reuse"]["q_digest"],
            training_binding=dict(parent_id=parent["id"], c1_proof_digest=registration.runtime.digest(parent["c1_reuse"])),
            next_outer894_executed=False))
        branches[f"seed{seed}/C1"] = ref(root / f"branches/seed{seed}/C1/completed/record.json")
    body = dict(schema=registration.PREPARED_SCHEMA, protocol=ref(root / "protocol/record.json"),
        original_prepared=ref(old / "prepared/record.json"), parents=parents, c1_branches=branches,
        actual_new_optimizer_budget=1788, logical_optimizer_updates=2682, reused_C1_logical_updates=894,
        new_feedback_sessions=2100, remaining_feedback_episodes=2030, new_evaluation_sessions=12267,
        total_new_sessions=14367, inherited_complete_feedback_episodes=70, inherited_partial_returned_turns=3,
        inherited_complete_class_tasks=9, inherited_class_rows=45, remaining_new_class_tasks=1479,
        old_single_request_allowance_remaining=0)
    body.update(changes or {})
    pub(root / "prepared/record.json", body)
    return root


def test_actual_prepared_budget_and_read_only_C1_refs(tmp_path, monkeypatch):
    root = prepared_fixture(tmp_path, monkeypatch)
    assert registration.checked_prepared(root)["remaining_feedback_episodes"] == 2030


@pytest.mark.parametrize("changes", [dict(actual_new_optimizer_budget=2682),
    dict(remaining_feedback_episodes=2100), dict(old_single_request_allowance_remaining=2),
    dict(inherited_partial_returned_turns=0), dict(remaining_new_class_tasks=1488)])
def test_cannot_reset_consumed_work_or_allowances(tmp_path, monkeypatch, changes):
    root = prepared_fixture(tmp_path, monkeypatch, changes)
    with pytest.raises(ValueError, match="scientific dose differs"):
        registration.checked_prepared(root)
