"""Small prospective-contract and fake-bundle tests; never prepares real V63."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import finqa_v63_registration as registration
import pytest


def record(path, value):
    value = {**value, "id": registration.binding.digest(value)}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value))
    return value


def test_prospective_contract_is_balanced_and_does_not_grant_old_replay_or_extra_science(monkeypatch):
    monkeypatch.setattr(registration, "modules", lambda: pytest.fail("pure contract imports no runtime"))
    value = registration.scientific_contract()
    assert value["new_arms"] == ["C1", "C05"]
    assert value["feedback_temperatures"] == {"C1": 1.0, "C05": 0.5}
    assert value["feedback_draw_seeds"] == [101, 103]
    assert value["random_evaluation_seeds"] == [11, 29]
    assert value["new_feedback_sessions"] == 3 * 2 * 700 == 4200
    assert value["new_optimizer_updates"] == 3 * 2 * 298 == 1788
    assert value["new_total_logical_sessions"] == 4200 + 7458 == 11658
    assert value["new_class_forward_passes"] == value["new_step745_evaluation"] == 0
    assert not value["old_gJ_reused_or_rescaled"]
    assert not value["automatic_followup_authorized"]
    assert value["primary_net_correct_at_least"] == 27
    assert value["key_secondary_net_correct_at_least"] == 1
    assert value["old_batch_not_in_new_primary"] is True
    assert value["formal_and_two_draw_buffers_share_one_atomic_response_checkpoint"]
    assert value["formal_q_from_formal_C_once"] and value["mean_of_normalized_draw_q_forbidden"]
    assert value["diagnostic_extra_VJPs_total"] == value["diagnostic_extra_inner_product_passes_total"] == 12
    assert value["draw_mean_tolerances"]["atol"] == 1e-7
    assert value["draw_mean_tolerances"]["rtol"] == 2e-4
    assert value["draw_mean_tolerances"]["source"] == "V54_CPU_full_autograd_gradient_comparison"


def test_registration_installs_frozen_paths_and_canonical_auxiliary_before_scientific_imports(monkeypatch):
    calls = []
    monkeypatch.setattr(registration.binding, "install_scientific_paths", lambda: calls.append("paths"))

    def import_module(name):
        calls.append(name)
        if name == "finqa_v63_entry":
            return SimpleNamespace(install_registered_auxiliary=lambda: calls.append("auxiliary"))
        return SimpleNamespace(name=name)

    monkeypatch.setattr(registration.importlib, "import_module", import_module)
    loaded = registration.modules()
    assert calls[:3] == ["paths", "finqa_v63_entry", "auxiliary"]
    assert set(loaded) == {"training", "runtime", "controller", "evaluation", "diagnostics",
                           "temperature", "signals", "gpu_isolation"}
    assert len(calls) == 3 + len(loaded)


def test_checkpoint_metadata_accepts_plain_native_JSON_but_never_hashes_tensor(tmp_path, monkeypatch):
    directory = tmp_path / "step0596_step"
    directory.mkdir()
    metadata = json.dumps({"seed": 137, "step": 596, "phase": "step"}).encode()
    (directory / "record.json").write_bytes(metadata)
    (directory / "state.pt").write_bytes(b"must not read or deserialize this fixture")
    source_sha, reads = registration.binding.sha, []

    def only_metadata(path):
        assert Path(path).name == "record.json"
        reads.append(Path(path))
        return source_sha(path)

    monkeypatch.setattr(registration.binding, "sha", only_metadata)
    registration._checkpoint_metadata({
        "path": str(directory), "record_sha256": hashlib.sha256(metadata).hexdigest()})
    assert reads == [directory / "record.json"]


@pytest.fixture
def bundle(tmp_path, monkeypatch):
    root, old, repo = tmp_path / "new", tmp_path / "old", tmp_path / "repository"
    for owner in (registration, registration.binding):
        monkeypatch.setattr(owner, "ROOT", root)
        monkeypatch.setattr(owner, "OLD_ROOT", old)
        monkeypatch.setattr(owner, "REPO", repo)
    monkeypatch.setattr(registration, "_IMPLEMENTATION", None)
    old_sources = {f"finqa_original_{index:03d}.py": f"# unchanged original {index}\n".encode()
                   for index in range(96)}
    directory = old / "implementation"
    directory.mkdir(parents=True)
    for name, raw in old_sources.items():
        (directory / name).write_bytes(raw)
    external = old / "frozen_source/required.py"
    external.parent.mkdir()
    external.write_text("# external frozen dependency\n")
    old_manifest = record(directory / "record.json", dict(
        schema="old-frozen-96", sha256={name: hashlib.sha256(raw).hexdigest()
                                      for name, raw in old_sources.items()},
        external_frozen_source_sha256={str(external): registration.binding.sha(external)},
        frozen_source_root=str(external.parent)))
    monkeypatch.setattr(registration.binding, "OLD_IMPLEMENTATION_ID", old_manifest["id"])
    script_root = repo / "trusted_data_synthesis/scripts"
    script_root.mkdir(parents=True)
    new_sources = {name: f"# newly committed {name}\n".encode() for name in registration.FILES}
    for name, raw in new_sources.items():
        (script_root / name).write_bytes(raw)
    calls = []
    commit = "a" * 40

    def git(command, **kwargs):
        calls.append(command)
        assert command[:1] == ["git"] and kwargs["cwd"] == repo
        if command[1] == "rev-parse":
            assert kwargs["text"] is True
            return commit + "\n"
        assert command[1] == "show" and command[2].startswith(commit + ":")
        return new_sources[Path(command[2].split(":", 1)[1]).name]

    monkeypatch.setattr(registration.subprocess, "check_output", git)
    return SimpleNamespace(root=root, old=old, repo=repo, old_sources=old_sources,
        new_sources=new_sources, manifest=old_manifest, calls=calls, commit=commit)


def test_freeze_preserves_all96_and_adds_exactly16_without_external_source_rewrite(bundle):
    e = bundle
    assert len(registration.FILES) == len(set(registration.FILES)) == 16
    assert {"finqa_v63_draw_components.py", "finqa_v63_worker_audit.py",
            "finqa_v63_registration.py"} <= set(registration.FILES)
    result = registration.freeze(e.root, "committed-source")
    assert len(result["sha256"]) == 112
    assert result["source_commit"] == e.commit
    assert result["committed_files"] == list(registration.FILES)
    assert result["original_96_files_byte_identical"] and not result["historical_files_modified"]
    for name, raw in {**e.old_sources, **e.new_sources}.items():
        assert (e.root / "implementation" / name).read_bytes() == raw
    for name, raw in e.old_sources.items():
        assert (e.old / "implementation" / name).read_bytes() == raw
    assert registration.checked_implementation(e.root) == result
    assert len(e.calls) == 17  # one resolve, one read per newly committed source


@pytest.mark.parametrize("changed", ["original", "workspace"])
def test_freeze_rejects_changed_source_before_creating_new_root(bundle, changed):
    e = bundle
    if changed == "original":
        path = e.old / "implementation" / next(iter(e.old_sources))
    else:
        path = e.repo / "trusted_data_synthesis/scripts" / registration.FILES[0]
    path.write_text("# changed unregistered source\n")
    with pytest.raises(ValueError, match="source changed|uncommitted"):
        registration.freeze(e.root, "committed-source")
    assert not e.root.exists()


def test_existing_or_partial_root_cannot_be_overwritten_by_repeating_prepare(bundle):
    e = bundle
    e.root.mkdir()
    evidence = e.root / "existing-evidence"
    evidence.write_bytes(b"preserved")
    with pytest.raises(ValueError, match="fresh independent"):
        registration.freeze(e.root, "committed-source")
    assert evidence.read_bytes() == b"preserved" and not e.calls


def test_completed_history_also_requires_the_same_controller_actual_exit_zero(bundle, monkeypatch):
    e = bundle
    old_protocol = record(e.old / "protocol/record.json", {"schema": "old-protocol"})
    closeout = record(e.old / "signal_recovery_04/closeout/record.json", dict(
        status="COMPLETE", accepted_jobs=68, active_workers=0))
    monkeypatch.setattr(registration.binding, "OLD_PROTOCOL_ID", old_protocol["id"])
    monkeypatch.setattr(registration.binding, "OLD_CLOSEOUT_ID", closeout["id"])
    record(e.old / "signal_recovery_04/supervisor/closeout/record.json", dict(
        status="COMPLETE", controller_attempts=1, automatic_restart_stopped=True))
    directory = e.old / "signal_recovery_04/supervisor/attempts/attempt0001"
    record(directory / "launch/record.json", dict(pid=12345, birth="actual-birth"))
    actual = dict(pid=12345, birth="actual-birth", returncode=0, actual_waitpid_observed=True)
    record(directory / "actual_exit/record.json", actual)
    record(e.old / "evaluations/registration/record.json", dict(schema="old-evaluation"))
    refs, values = registration.original_evidence()
    assert set(refs) >= {"controller_launch", "controller_exit"}
    assert values["controller_exit"]["returncode"] == 0
    for change in (dict(returncode=1), dict(actual_waitpid_observed=False), dict(birth="different")):
        record(directory / "actual_exit/record.json", {**actual, **change})
        with pytest.raises(ValueError, match="actual controller waitpid"):
            registration.original_evidence()


def test_prepare_resolves_policies_before_freeze_and_uses_only_frozen_diagnostics_subprocess(
        bundle, monkeypatch):
    e, events = bundle, []
    source = record(e.old / "original_source/record.json", dict(schema="old-public-source"))
    source_ref = registration.binding.entry(e.old / "original_source/record.json")
    plan = record(e.old / "evaluations/registration/record.json", dict(schema="old-evaluation"))
    record(e.old / "evaluations/panels/panel/summary/record.json", dict(
        registration_id=plan["id"]))
    refs = {"evaluation_registration": registration.binding.entry(
        e.old / "evaluations/registration/record.json")}
    monkeypatch.setattr(registration, "original_evidence", lambda: (
        refs, {"protocol": {"evaluation_source_registration": source_ref},
               "evaluation_registration": plan}))
    monkeypatch.setattr(registration, "parent_metadata", lambda seed: {"seed": seed, "Tensor_loaded": False})
    audit_path = e.old / "user-audit.txt"
    audit_path.write_text("fixture prospective authorization")
    monkeypatch.setattr(registration.binding, "USER_AUDIT", audit_path)
    file_ref = registration.binding.file_ref

    def audit_ref(path):
        if Path(path) == audit_path:
            events.append("audit")
        return file_ref(path)

    monkeypatch.setattr(registration.binding, "file_ref", audit_ref)
    monkeypatch.setattr(registration, "_policy_fields", lambda loaded: (
        events.append("policies") or {"scientific_contract": registration.scientific_contract()}))
    monkeypatch.setattr(registration.shutil, "disk_usage", lambda path: SimpleNamespace(free=200 * 1024 ** 3))

    def freeze(root, commit):
        assert events == ["policies", "audit"]
        events.append("freeze")
        return record(root / "implementation/record.json", dict(
            schema=registration.IMPLEMENTATION_SCHEMA, source_commit=e.commit))

    monkeypatch.setattr(registration, "freeze", freeze)

    def prepare_parent(root, seed, protocol_id):
        events.append(f"parent{seed}")
        return record(root / f"parents/seed{seed}/record.json", dict(
            protocol_id=protocol_id, seed=seed))

    loaded = dict(
        runtime=SimpleNamespace(GPU_UUIDS={str(i): f"GPU-{i}" for i in range(8)},
                                CPU_AFFINITY={}, birth=lambda pid: None),
        evaluation=SimpleNamespace(PANEL_SPECS=(("panel",),)),
        controller=SimpleNamespace(base=SimpleNamespace(GPU_LEASE_ROOT=e.old / "leases")),
        training=SimpleNamespace(prepare_parent=prepare_parent))
    monkeypatch.setattr(registration, "modules", lambda: loaded)

    def diagnostics(command, *, cwd, check):
        assert command == [str(registration.binding.PYTHON),
                           str(e.root / "implementation/finqa_v63_diagnostics.py"),
                           "prepare", "--root", str(e.root)]
        assert cwd == e.repo and check is True
        assert events[-3:] == ["parent137", "parent251", "parent389"]
        events.append("frozen_diagnostics_prepare")
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(registration.subprocess, "run", diagnostics)
    result = registration.prepare("committed-source")
    assert result["scientific_supervisor_started"] is False and result["CUDA_initialized"] is False
    assert result["scientific_calls"] == 0 and result["frozen_entry_check_imports_still_required"]
    assert events[-1] == "frozen_diagnostics_prepare"
