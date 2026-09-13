"""CPU-only lifecycle controls: injected providers never issue model requests."""

import copy
import threading
from collections import Counter
from pathlib import Path

import pytest
from test_qa_vnext_fixed_kernel_distribution import catalog

from trusted_synthesis.experiments.finance_qa_vnext_fixed_kernel_value import population
from trusted_synthesis.experiments.finance_qa_vnext_fixed_kernel_value import protocol as p
from trusted_synthesis.experiments.finance_qa_vnext_fixed_kernel_value import study as s


class FakeLedger:
    """Synthetic bookkeeping only; deliberately no SQLite or network handle."""

    def __init__(self, path, registrations):
        self.path = path
        self.rows = {row["session_id"]: {**row, "state": "registered"} for row in registrations}
        self.leases = []
        self.stops = []
        self.lock = threading.Lock()

    def finish(self, session_id, terminal):
        assert self.rows[session_id]["state"] != "finished"
        self.rows[session_id].update(state="finished", terminal=terminal)

    def requests(self):
        return copy.deepcopy(self.leases)

    def sessions(self):
        return copy.deepcopy(list(self.rows.values()))

    def halt(self, reason):
        self.stops.append(reason)

    def send(self, registered, state="settled"):
        with self.lock:
            row = dict(
                request_id="synthetic_lease_" + registered["session_id"],
                session_id=registered["session_id"],
                state=state,
                reserved_tokens=115712,
                charged_tokens=3 if state == "settled" else 115712,
            )
            self.leases.append(row)
        return row

    def cancel_unsent(self, request_id, reason):
        row = next(item for item in self.leases if item["request_id"] == request_id)
        assert row["state"] == "reserved"
        row.update(state="not_sent", charged_tokens=0, outcome=reason)

    def settle(self, request_id, *, outcome):
        row = next(item for item in self.leases if item["request_id"] == request_id)
        assert row["state"] == "sent"
        row.update(state="usage_unknown", outcome=outcome)

    def snapshot(self):
        return p.record(
            "kernel_wallet_snapshot",
            persisted_stops={"kernel_fatal": "synthetic"} if self.stops else {},
            kernel_conservative_debit=sum(row["charged_tokens"] for row in self.leases),
            common_conservative_debit=100 + sum(row["charged_tokens"] for row in self.leases),
        )


def tiny_inputs(tmp_path, monkeypatch):
    monkeypatch.setattr(p, "SESSION_CAP", 3)
    regs = [
        p.record(
            "session_registration",
            session_id="synthetic_session_" + str(i),
            ordinal=i,
            task_id="synthetic_task_" + str(i),
            identity={"task_id": "synthetic_task_" + str(i)},
        )
        for i in range(3)
    ]
    fixtures = {row["task_id"]: {"identity": row["identity"], "messages": []} for row in regs}
    registry = p.record("material_registry", sessions=regs, freeze_id="synthetic_freeze")
    ledger = FakeLedger(tmp_path / "NO_REAL_DATABASE", regs)
    return regs, fixtures, registry, ledger


def fake_provider(ledger, registered, *_):
    def call(*_):
        ledger.send(registered)
        return "synthetic_public_response"

    return call


def fake_generator(messages, identity, *, provider, registered):
    provider(messages, {"synthetic": True})
    return p.record(
        "material_session",
        registered_session_id=registered["session_id"],
        global_fatal=False,
        terminal="first_final",
        identity=identity,
    )


def fake_assessor(session_path, registered, *_):
    session = p.read_json(session_path)
    return p.record(
        "material_qualification",
        session_id=session["id"],
        registered_session_id=registered["session_id"],
        synthetic_control_only=True,
    )


def test_injected_full_collection_retains_fixed_denominator_and_original_refs(
    tmp_path, monkeypatch
):
    regs, fixtures, registry, ledger = tiny_inputs(tmp_path, monkeypatch)
    result = s.collect_registered(
        ledger,
        registry,
        fixtures,
        tmp_path / "output",
        tmp_path / "runtime",
        "synthetic_code",
        "unused_synthetic_credential",
        generation_workers=2,
        assessment_workers=2,
        processes=False,
        provider_factory=fake_provider,
        generator=fake_generator,
        assessor=fake_assessor,
    )
    assert result["synthetic_injection"] is True
    assert result["all_generation_and_assessment_workers_closed"]
    assert not result["global_stop"] and not result["errors"]
    assert [row["session_id"] for row in result["results"]] == [row["session_id"] for row in regs]
    assert all(row["status"] == "finished" for row in result["results"])
    assert len(ledger.leases) == 3 and all(row["state"] == "finished" for row in ledger.sessions())
    for row in result["results"]:
        for key in ("session", "qualification"):
            ref = row[key]
            assert not Path(ref["path"]).is_absolute()
            assert s._read_reference(ref, tmp_path / "output")["id"] == ref["id"]


def test_global_stop_does_not_schedule_replacement_or_remove_unrequested_rows(
    tmp_path, monkeypatch
):
    regs, fixtures, registry, ledger = tiny_inputs(tmp_path, monkeypatch)

    def stop_generator(messages, identity, *, provider, registered):
        value = fake_generator(messages, identity, provider=provider, registered=registered)
        return p.record(
            "material_session",
            registered_session_id=registered["session_id"],
            global_fatal=True,
            terminal="fatal_provider_or_budget_stop",
            identity=identity,
            original_control_id=value["id"],
        )

    result = s.collect_registered(
        ledger,
        registry,
        fixtures,
        tmp_path / "output",
        tmp_path / "runtime",
        "code",
        "test",
        generation_workers=1,
        assessment_workers=1,
        processes=False,
        provider_factory=fake_provider,
        generator=stop_generator,
        assessor=fake_assessor,
    )
    assert len(ledger.leases) == 1
    assert Counter(row["status"] for row in result["results"]) == {
        "budget_aborted": 1,
        "not_run": 2,
    }
    assert len(result["results"]) == len(regs) == 3
    assert result["global_stop"]
    assert all(row["state"] == "finished" for row in ledger.sessions())


def test_assessment_exception_is_typed_and_stops_admission_without_losing_raw_session(
    tmp_path, monkeypatch
):
    _, fixtures, registry, ledger = tiny_inputs(tmp_path, monkeypatch)

    def bad_assessor(*_):
        raise ValueError("synthetic_offline_assessment_error")

    result = s.collect_registered(
        ledger,
        registry,
        fixtures,
        tmp_path / "output",
        tmp_path / "runtime",
        "code",
        "test",
        generation_workers=1,
        assessment_workers=1,
        processes=False,
        provider_factory=fake_provider,
        generator=fake_generator,
        assessor=bad_assessor,
    )
    assert result["global_stop"] and result["errors"]
    failed = [row for row in result["results"] if row["status"] == "failed"]
    assert failed and all(row["session"] and row["qualification"] is None for row in failed)
    assert all(value["error_type"] == "ValueError" for value in result["errors"])


@pytest.mark.parametrize("orphan", ["reserved", "sent"])
def test_closed_worker_orphans_are_cancelled_only_if_unsent(tmp_path, monkeypatch, orphan):
    _, fixtures, registry, ledger = tiny_inputs(tmp_path, monkeypatch)

    def bad_provider(current, registered, *_):
        def call(*_):
            current.send(registered, orphan)
            raise RuntimeError("synthetic_orphan")

        return call

    result = s.collect_registered(
        ledger,
        registry,
        fixtures,
        tmp_path / "output",
        tmp_path / "runtime",
        "code",
        "test",
        generation_workers=1,
        assessment_workers=1,
        processes=False,
        provider_factory=bad_provider,
        generator=fake_generator,
        assessor=fake_assessor,
    )
    assert result["global_stop"] and result["errors"]
    assert len(ledger.leases) == 1
    assert ledger.leases[0]["state"] == ("not_sent" if orphan == "reserved" else "usage_unknown")
    assert ledger.leases[0]["charged_tokens"] == (0 if orphan == "reserved" else 115712)


def report_inputs(monkeypatch):
    monkeypatch.setattr(p, "SESSION_CAP", 3)
    results = [
        {
            "session_id": "session_" + str(i),
            "status": "finished",
            "session": {"id": "s" + str(i)},
            "qualification": {"id": "q" + str(i)},
        }
        for i in range(3)
    ]
    freeze = {"id": "freeze", "code_snapshot_id": "code"}
    registry = {"id": "registry", "sessions": [{}] * 3}
    collected = dict(
        results=results,
        errors=[],
        global_stop=False,
        synthetic_injection=False,
        all_generation_and_assessment_workers_closed=True,
        counts={},
        elapsed_seconds=0,
    )
    wallet = dict(
        id="wallet", persisted_stops={}, kernel_conservative_debit=9, common_conservative_debit=109
    )
    journal = [{"session_id": row["session_id"], "state": "settled"} for row in results]
    return freeze, registry, collected, wallet, journal


def test_raw_completion_and_global_contract_are_distinct(monkeypatch):
    args = report_inputs(monkeypatch)
    passed = s._generation_report(*args, contracts_passed=True, references={})
    failed = s._generation_report(*args, contracts_passed=False, references={})
    assert passed["status"] == "COMPLETE_FIXED_COLLECTION"
    assert failed["status"] == "STOP_INCOMPLETE_OR_CONTRACT"
    assert passed["raw_registry_complete"] is failed["raw_registry_complete"] is True
    assert failed["generation_contract_passed"] is False
    assert failed["finished_sessions"] == 3 and failed["unrequested_sessions"] == 0


def test_inflight_or_unjoined_worker_cannot_claim_generation_closed(monkeypatch):
    args = report_inputs(monkeypatch)
    args[-1][0]["state"] = "sent"
    with pytest.raises(ValueError, match="closed_generation_denominator"):
        s._generation_report(*args, contracts_passed=True, references={})


def test_unmeasured_global_gate_never_claims_zero_support_or_failed_tokenization():
    kernel = dict(
        id="placeholder_kernel",
        population_id="population",
        registry_id="registry",
        tasks=[{"task_id": "a", "family": "annual_flow"}],
        train_packages=[],
        physical_originals_sha256="placeholder",
    )
    index = dict(id="index", materialization_permitted=False, collection_complete=False)
    generation = dict(id="generation", raw_registry_complete=True, generation_contract_passed=False)
    gate = s._materialization_gate(index, kernel, generation)
    assert gate["training_gate"] == "FAIL"
    assert gate["raw_registry_complete"] is True
    assert gate["token_support_measurement"] == "NOT_MEASURED_GLOBAL_GATE"
    assert gate["global_mass_movement"] is gate["common_intervention_task_count"] is None
    assert gate["per_pool_task_actual_support"] is gate["empty_pool_task_support"] is None


@pytest.mark.parametrize("attribute", ["failures", "errors", "skipped"])
def test_nonpassing_junit_is_rejected(tmp_path, attribute):
    path = tmp_path / "control.xml"
    path.write_text('<testsuites><testsuite tests="1" ' + attribute + '="1"/></testsuites>')
    with pytest.raises(ValueError, match="all_CPU_controls"):
        s._junit(path)


def test_new_code_snapshot_detects_postfreeze_edits(tmp_path, monkeypatch):
    monkeypatch.setattr(p, "PACKAGE", "new_package")
    package = tmp_path / "new_package"
    package.mkdir()
    path = package / "only.py"
    path.write_text("x = 1\n")
    bound = s.code_snapshot(tmp_path)
    original = p.record("original_code_dependencies", members=[])
    s.verify_code(tmp_path, bound, original)
    path.write_text("x = 2\n")
    with pytest.raises(ValueError, match="frozen_new_code"):
        s.verify_code(tmp_path, bound, original)


def test_uncommitted_preparation_is_rejected_before_any_input_or_wallet_access(
    tmp_path, monkeypatch
):
    freeze = dict(
        id="freeze",
        artifacts={"policy.json": {}},
        code_snapshot_id="code",
        original_code_dependencies_id="original",
    )
    monkeypatch.setattr(s, "_load_prepared", lambda _: (freeze, {}, {}))
    p.write_once(tmp_path / "code_snapshot.json", {"id": "code"})
    p.write_once(tmp_path / "original_code_dependencies.json", {"id": "original"})
    p.write_once(tmp_path / "policy.json", {"unchanged": True})
    monkeypatch.setattr(s, "verify_code", lambda *_: None)
    monkeypatch.setattr(s, "git", lambda *_: b"wrong committed bytes")

    def forbidden(*_):
        raise AssertionError("must reject before source or wallet access")

    monkeypatch.setattr(s.preflight, "load_inputs", forbidden)
    monkeypatch.setattr(s, "_wallet_before", forbidden)
    with pytest.raises(ValueError, match="committed_before_HTTP"):
        s._verify_launch(tmp_path, tmp_path, tmp_path, require_unregistered_wallet=True)


@pytest.mark.parametrize("bad", ["generation_open", "budget_open", "different_report"])
def test_materialization_requires_matching_generation_and_budget_closure(
    tmp_path, monkeypatch, bad
):
    output = tmp_path / "output"
    output.mkdir()
    monkeypatch.setattr(p, "SESSION_CAP", 3)
    freeze = dict(id="freeze", code_snapshot_id="code")
    registry = dict(id="registry")
    monkeypatch.setattr(
        s, "guarded_roots", lambda *_: (tmp_path, tmp_path, output, tmp_path / "runtime")
    )
    monkeypatch.setattr(s, "_load_prepared", lambda _: (freeze, {}, registry))
    generation = p.record(
        "material_generation_report",
        generation_closed=bad != "generation_open",
        no_inflight_requests=True,
        registered_sessions=3,
        freeze_id="freeze",
        registry_id="registry",
        code_snapshot_id="code",
    )
    final = p.record(
        "kernel_budget_finalization",
        freeze_id="freeze",
        purpose_closed=bad != "budget_open",
        report_id="wrong" if bad == "different_report" else generation["id"],
    )
    p.write_once(output / "generation_report.json", generation)
    p.write_once(output / "budget_finalization.json", final)

    def forbidden(*_):
        raise AssertionError("no real wallet or tokenizer should be opened")

    monkeypatch.setattr(s.budget, "KernelLedger", forbidden)
    with pytest.raises(ValueError, match="generation_and_budget_closed"):
        s.materialize(tmp_path, tmp_path)


def test_prepare_is_offline_and_keeps_formal_tokenizer_filename_unused(tmp_path, monkeypatch):
    output, work = tmp_path / "output", tmp_path / "runtime"
    output.mkdir()
    work.mkdir()
    monkeypatch.setattr(s, "guarded_roots", lambda *_: (tmp_path, tmp_path, output, work))
    monkeypatch.setattr(s, "PROTECTED", ())
    selected = population.make_population(catalog())
    records = {
        key: p.record(key)
        for key in ("source_dependencies", "source_evidence", "boundary_manifest")
    }
    inputs = {"population": selected, "fixtures": {}, **records}
    monkeypatch.setattr(s.preflight, "load_inputs", lambda _: inputs)
    monkeypatch.setattr(
        s.preflight,
        "scripted_controls",
        lambda *_, **__: p.record(
            "scripted_preflight_controls", status="PASS", passed_control_count=560
        ),
    )
    monkeypatch.setattr(s, "code_snapshot", lambda _: p.record("study_code_snapshot"))
    monkeypatch.setattr(s, "base_dependencies", lambda _: p.record("original_code_dependencies"))
    monkeypatch.setattr(s, "verify_code", lambda *_: None)
    old = p.record("legacy_wallet_snapshot")
    monkeypatch.setattr(s, "_wallet_before", lambda _: (old, 123))
    monkeypatch.setattr(s, "_shadow_evidence", lambda *_: p.record("shadow_evidence_import"))
    monkeypatch.setattr(
        s,
        "_gpu_evidence",
        lambda *_: p.record(
            "GPU_engineering_evidence",
            reports=[{"report": {"checkpoint_binding_id": "checkpoint"}}],
        ),
    )
    monkeypatch.setattr(s, "_assets", lambda _: ({"id": "checkpoint"}, {"id": "tokenizer"}))

    def forbidden(*_):
        raise AssertionError("prepare must never read a credential or create a provider")

    monkeypatch.setattr(s, "_credential", forbidden)
    monkeypatch.setattr(s.transport, "Provider", forbidden)
    monkeypatch.setattr(s.budget, "KernelLedger", forbidden)
    audit = tmp_path / "audit.txt"
    audit.write_text("Synthetic complete audit text, not a real financial result.")
    monkeypatch.setattr(p, "AUDIT_PATH", str(audit))
    junit = tmp_path / "cpu.xml"
    junit.write_text(
        '<testsuites><testsuite tests="2" failures="0" errors="0" skipped="0"/></testsuites>'
    )
    p.write_once(
        work / "official_model_preflight.json",
        p.record(
            "official_model_preflight",
            HTTP_status=200,
            administrative_GET_requests=1,
            model_generation_requests=0,
            model_ids=[p.MODEL],
            credential_saved=False,
        ),
    )
    freeze = s.prepare(
        tmp_path,
        tmp_path,
        junit_path=junit,
        shadow_path="unused",
        gpu_reports=["unused"],
        control_workers=1,
    )
    registry = p.read_json(output / "registry.json")
    assert registry["freeze_id"] == freeze["id"] and len(registry["sessions"]) == 10240
    assert (output / "tokenizer_binding_preflight.json").is_file()
    assert not (output / "tokenizer_binding.json").exists()
    assert (output / "cpu_tests.xml").read_bytes() == junit.read_bytes()
    assert p.read_json(output / "audit_directive.json")["complete_text"] == audit.read_text()
    assert (
        freeze["generation_requests_before_freeze"]
        == freeze["live_wallet_mutations_by_prepare"]
        == 0
    )
