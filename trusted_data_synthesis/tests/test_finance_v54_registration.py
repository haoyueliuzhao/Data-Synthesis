from __future__ import annotations

import pytest

import finqa_v54_evaluation as evaluation
import finqa_v54_registration as registration


def registered_fixture(tmp_path, monkeypatch, *, budget=1788, omit_c1=None,
                       branch_q="q", old_parent_changed=False):
    """Mock records only: no prepare, source freeze, real state load or GPU entry."""
    monkeypatch.setattr(registration, "ROOT", tmp_path)
    implementation = tmp_path / "implementation/record.json"
    evaluation.publish(implementation, dict(schema="mock_implementation"))
    sources = {str(seed): dict(parent=dict(path=f"old/seed{seed}/step596", state_sha256="a"),
                              old_outer=dict(path=f"old/seed{seed}/outer596", state_sha256="b"))
               for seed in registration.SEEDS}
    body = dict(schema=registration.SCHEMA, output_root=str(tmp_path),
        scientific_contract=registration.scientific_contract(), resource_policy=registration.runtime.resource_policy(),
        allowed_gpu_indices=list(range(8)), gpu_uuids=registration.runtime.GPU_UUIDS,
        max_gpu_workers=4, max_workers_per_gpu=1, cpu_affinity=registration.runtime.CPU_AFFINITY,
        gpu_lease_root=str(registration.TRAINING_ROOT / "locks"), gpu_priority=list(range(8)),
        parents={str(seed): str(tmp_path / f"parents/seed{seed}/record.json") for seed in registration.SEEDS},
        evaluation=evaluation.evaluation_contract(), implementation=registration.entry(implementation),
        source_parent_checkpoints=sources)
    protocol = evaluation.publish(tmp_path / "protocol/record.json", body)
    parents, branches = {}, {}
    for seed in registration.SEEDS:
        proof = dict(eligible=True, q_digest="q", snapshots={"745": dict(path="745"), "894": dict(path="894")})
        parent = dict(schema="v54_actual_parent.v1", seed=seed, protocol_id=protocol["id"],
            parent_checkpoint=sources[str(seed)]["parent"], old_outer_checkpoint=sources[str(seed)]["old_outer"],
            parent_state_digest="real-parent", c1_reuse=proof)
        if old_parent_changed and seed == 137:
            parent["parent_checkpoint"] = dict(path="unregistered", state_sha256="a")
        parent_path = tmp_path / f"parents/seed{seed}/record.json"
        actual_parent = evaluation.publish(parent_path, parent)
        parents[str(seed)] = registration.entry(parent_path)
        if seed != omit_c1:
            branch_path = tmp_path / f"branches/seed{seed}/C1/completed/record.json"
            evaluation.publish(branch_path, dict(schema="v54_fixed_q_branch_complete.v1", status="COMPLETE",
                protocol_id=protocol["id"], seed=seed, arm="C1", optimizer_updates=298, new_optimizer_updates=0,
                parent_state_digest="real-parent", distribution_digest=branch_q, snapshots=proof["snapshots"],
                training_binding=dict(parent_id=actual_parent["id"], c1_proof_digest=registration.runtime.digest(proof)),
                next_outer894_executed=False))
            branches[f"seed{seed}/C1"] = registration.entry(branch_path)
    prepared = evaluation.publish(tmp_path / "prepared/record.json", dict(schema="v54_three_parent_ready.v1",
        protocol=registration.entry(tmp_path / "protocol/record.json"), parents=parents, c1_branches=branches,
        actual_new_optimizer_budget=budget, reused_C1_logical_updates=894, logical_optimizer_updates=2682,
        new_feedback_sessions=2100, new_evaluation_sessions=12267, total_new_sessions=14367))
    return protocol, prepared


def test_protocol_then_parent_entries_avoid_circular_ids_and_match_controller(tmp_path, monkeypatch):
    protocol, prepared = registered_fixture(tmp_path, monkeypatch)
    assert all(isinstance(path, str) for path in protocol["parents"].values())
    assert registration.checked_prepared(tmp_path) == prepared
    assert prepared["actual_new_optimizer_budget"] == 1788
    assert len(prepared["c1_branches"]) == 3
    assert all(registration.runtime.read_ref(ref)["protocol_id"] == protocol["id"]
               for ref in prepared["parents"].values())


@pytest.mark.parametrize("budget", [-1, 1789, 2682])
def test_prepared_budget_must_equal_actual_reuse_membership(tmp_path, monkeypatch, budget):
    registered_fixture(tmp_path, monkeypatch, budget=budget)
    with pytest.raises(ValueError, match="exact physical optimizer budget"):
        registration.checked_prepared(tmp_path)


def test_admitted_c1_cannot_omit_its_bound_branch(tmp_path, monkeypatch):
    registered_fixture(tmp_path, monkeypatch, omit_c1=251)
    with pytest.raises(ValueError, match="C1 reuse membership"):
        registration.checked_prepared(tmp_path)


def test_c1_branch_cannot_substitute_another_distribution(tmp_path, monkeypatch):
    registered_fixture(tmp_path, monkeypatch, branch_q="changed")
    with pytest.raises(ValueError, match="actual complete parent proof"):
        registration.checked_prepared(tmp_path)


def test_parent_must_match_predeclared_source_not_only_protocol_id(tmp_path, monkeypatch):
    registered_fixture(tmp_path, monkeypatch, old_parent_changed=True)
    with pytest.raises(ValueError, match="registered source point"):
        registration.checked_prepared(tmp_path)


@pytest.mark.parametrize("changed_original", [False, True])
def test_89_file_binding_preserves_exact_original_81(tmp_path, monkeypatch, changed_original):
    monkeypatch.setattr(registration, "ROOT", tmp_path)
    original = {f"finqa_old_{i}.py": "oldsha" for i in range(81)}
    original_path = tmp_path / "old/record.json"
    old = evaluation.publish(original_path, dict(sha256=original))
    monkeypatch.setattr(registration, "SOURCE_BUNDLE_ID", old["id"])
    files = {**original, **{name: "newsha" for name in registration.FILES}}
    if changed_original:
        files["finqa_old_0.py"] = "different"
    evaluation.publish(tmp_path / "implementation/record.json", dict(
        schema="v54_frozen_temperature_execution_implementation.v1",
        committed_files=list(registration.FILES), sha256=files,
        original_implementation=registration.entry(original_path), external_frozen_source_sha256={}))
    monkeypatch.setattr(registration, "sha", lambda path: files[path.name])
    if changed_original:
        with pytest.raises(ValueError, match="81 scientific files"):
            registration.checked_implementation(tmp_path)
    else:
        assert len(registration.checked_implementation(tmp_path)["sha256"]) == 89
