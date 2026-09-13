"""Synthetic metadata-only controls for the independently frozen recovery batch."""

import copy

import pytest
from test_qa_vnext_fixed_kernel_distribution import catalog

from trusted_synthesis.experiments.finance_qa_vnext_fixed_kernel_value import population
from trusted_synthesis.experiments.finance_qa_vnext_fixed_kernel_value import protocol as p
from trusted_synthesis.experiments.finance_qa_vnext_fixed_kernel_value import study as s


def rerecord(kind, value, **changes):
    fields = {key: item for key, item in value.items() if key not in {"id", "schema_version"}}
    return p.record(kind, **(fields | changes))


@pytest.fixture
def closed_parent(tmp_path, monkeypatch):
    monkeypatch.setattr(s, "CLOSED_FAILED_ROOT", tmp_path)
    monkeypatch.setattr(s, "CLOSED_FAILED_OUTPUT", "closed_metadata")
    monkeypatch.setattr(s, "git", lambda *_: b"synthetic_published_failure_commit\n")
    selected = population.make_population(catalog())
    policy = rerecord("fixed_kernel_policy", p.policy(), request_cap=p.REQUEST_CAP + 342)
    freeze = p.record(
        "study_freeze",
        population_id=selected["id"],
        policy_id=policy["id"],
        material_token_cap=p.TOKEN_CAP + 1269703,
    )
    generation = p.record(
        "material_generation_report",
        generation_closed=True,
        no_inflight_requests=True,
        status="STOP_INCOMPLETE_OR_CONTRACT",
        registered_sessions=10240,
        freeze_id=freeze["id"],
        kernel_conservative_debit=1269703,
        actual_HTTP_request_count=342,
    )
    final = p.record(
        "kernel_budget_finalization",
        purpose_closed=True,
        report_id=generation["id"],
        freeze_id=freeze["id"],
    )
    gate = p.record(
        "material_gate",
        generation_report_id=generation["id"],
        training_gate="FAIL",
        materialization_permitted=False,
        population_id=selected["id"],
    )
    summary = p.record(
        "closed_collection_summary",
        registered_sessions=10240,
        generation_report_id=generation["id"],
        budget_finalization_id=final["id"],
        material_gate_id=gate["id"],
        training_gate="FAIL",
        Student_training_runs=0,
        Student_evaluation_sessions=0,
    )
    records = {
        "population.json": selected,
        "policy.json": policy,
        "freeze.json": freeze,
        "generation_report.json": generation,
        "budget_finalization.json": final,
        "material_gate.json": gate,
        "closed_collection_summary.json": summary,
    }
    for name, value in records.items():
        p.write_once(tmp_path / "closed_metadata" / name, value)
    return selected, records, tmp_path / "closed_metadata"


def test_recovery_parent_retains_old_failure_denominator_and_exact_remaining_allowance(
    closed_parent,
):
    selected, records, root = closed_parent
    before = {path.name: path.read_bytes() for path in root.iterdir()}
    binding = s.recovery_parent_binding(selected)
    assert binding["old_generation_report_id"] == records["generation_report.json"]["id"]
    assert binding["original_failed_registered_denominator"] == 10240
    assert binding["old_training_gate_preserved"] == "FAIL"
    assert binding["remaining_token_cap"] == p.TOKEN_CAP
    assert binding["remaining_actual_HTTP_request_cap"] == p.REQUEST_CAP
    assert binding["old_sessions_or_packages_read_or_imported"] == 0
    assert binding["closed_previous_purpose_reopened"] is False
    assert len(binding["public_system_prompt_sha256"]) == 3
    assert before == {path.name: path.read_bytes() for path in root.iterdir()}


@pytest.mark.parametrize("field", ["TOKEN_CAP", "REQUEST_CAP"])
def test_recovery_cannot_regrant_old_spending(closed_parent, monkeypatch, field):
    selected, _, _ = closed_parent
    monkeypatch.setattr(p, field, getattr(p, field) + 1)
    with pytest.raises(ValueError, match="remaining_original_token_and_HTTP"):
        s.recovery_parent_binding(selected)


def test_recovery_cannot_change_population(closed_parent):
    selected, _, _ = closed_parent
    changed = copy.deepcopy(selected)
    changed["tasks"].reverse()
    with pytest.raises(ValueError, match="exact_same_200"):
        s.recovery_parent_binding(changed)


@pytest.mark.parametrize("field", ["REPLICATES", "ORDER_SEED", "MAX_RESPONSES", "SEQUENCE_CAP"])
def test_recovery_does_not_change_scientific_protocol(closed_parent, monkeypatch, field):
    selected, _, _ = closed_parent
    monkeypatch.setattr(p, field, getattr(p, field) + 1)
    with pytest.raises(ValueError, match="preserves_P2_roles_and_scientific_rules"):
        s.recovery_parent_binding(selected)


def test_recovery_cannot_modify_public_prompt(closed_parent, monkeypatch):
    selected, _, _ = closed_parent
    original = p.system_prompt
    monkeypatch.setattr(p, "system_prompt", lambda *args: original(*args) + "\nchanged")
    with pytest.raises(ValueError, match="original_public_prompt_bytes"):
        s.recovery_parent_binding(selected)


@pytest.mark.parametrize(
    "filename,kind,changes",
    [
        ("generation_report.json", "material_generation_report", {"generation_closed": False}),
        ("budget_finalization.json", "kernel_budget_finalization", {"purpose_closed": False}),
        (
            "closed_collection_summary.json",
            "closed_collection_summary",
            {"Student_training_runs": 1},
        ),
        (
            "closed_collection_summary.json",
            "closed_collection_summary",
            {"registered_sessions": 135},
        ),
    ],
)
def test_recovery_rejects_reopened_trained_or_reduced_old_batch(
    closed_parent, filename, kind, changes
):
    selected, records, root = closed_parent
    path = root / filename
    path.write_bytes(p.encode(rerecord(kind, records[filename], **changes)))
    with pytest.raises(ValueError, match="old_failed_batch_closed_without_training_or_relabel"):
        s.recovery_parent_binding(selected)


def test_recovery_binding_detects_later_parent_metadata_change(closed_parent):
    selected, records, root = closed_parent
    before = s.recovery_parent_binding(selected)
    path = root / "closed_collection_summary.json"
    path.write_bytes(
        p.encode(
            rerecord("closed_collection_summary", records[path.name], extra_annotation="changed")
        )
    )
    assert s.recovery_parent_binding(selected) != before


def test_new_package_not_original_dependency_but_closed_parent_is_protected():
    assert s._current_study_member(p.PACKAGE + "/budget.py")
    assert s._current_study_member(
        "trusted_data_synthesis/tests/test_qa_vnext_fixed_kernel_study_recovery.py"
    )
    assert not s._current_study_member(
        "trusted_data_synthesis/src/trusted_synthesis/experiments/finance_qa_vnext_probe_coverage/runtime.py"
    )
    assert not s._current_study_member(
        "trusted_data_synthesis/tests/test_qa_vnext_fixed_kernel_study_recovery.py.bak"
    )
    assert len(s.PROTECTED) == 6
    assert str(s.CLOSED_FAILED_ROOT) in s.PROTECTED


def test_single_request_shadow_cannot_satisfy_recovery_pressure_proof(tmp_path):
    before = p.record("legacy_wallet_snapshot")
    report = p.record(
        "wallet_shadow_control",
        status="PASS_SYNTHETIC_SHADOW_ONLY",
        source_legacy_snapshot_before=before,
        source_legacy_snapshot_after=before,
        source_wallet_modified=False,
        source_new_purpose_registered=False,
        live_API_calls=0,
        live_new_tokens=0,
    )
    path = tmp_path / "tiny_shadow.json"
    p.write_once(path, report)
    with pytest.raises(ValueError, match="128_worker_three_round_single_writer"):
        s._shadow_evidence(path, before)
