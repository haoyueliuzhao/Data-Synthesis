"""Five small injected operator checks; no real subprocess/GPU/API/credential reads."""

import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest

from trusted_synthesis.experiments.finance_qa_vnext_fixed_kernel_value import protocol as frozen_p

SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "scripts/run_fixed_kernel_writer_recovery_followthrough_20260913.py"
)
SPEC = importlib.util.spec_from_file_location("fixed_kernel_external_operator_test", SCRIPT)
operator = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(operator)


@pytest.fixture
def p():
    return SimpleNamespace(
        OUTPUT="raw",
        RUNTIME="runtime",
        **{
            name: getattr(frozen_p, name)
            for name in (
                "require",
                "record",
                "checked",
                "read_json",
                "write_once",
                "encode",
                "now",
                "sha",
            )
        },
    )


def closed(p, status="PASS"):
    generation = p.record(
        "material_generation_report",
        generation_closed=True,
        no_inflight_requests=True,
        registry_id="registry",
        freeze_id="freeze",
    )
    finalization = p.record(
        "kernel_budget_finalization",
        purpose_closed=True,
        freeze_id="freeze",
        report_id=generation["id"],
    )
    gate = p.record(
        "material_gate",
        generation_report_id=generation["id"],
        registry_id="registry",
        training_gate=status,
    )
    return dict(gate=gate, generation=generation, finalization=finalization)


def fake_launcher(observed, *, publication_spawn_failure=False, exits=None):
    class Fake:
        def __init__(self, *args):
            self.jobs = {}

        def start(self, stage):
            observed.append(("start", stage))
            if stage == "materials_seal" and publication_spawn_failure:
                raise OSError("synthetic publication spawn failure")
            assert stage not in self.jobs
            self.jobs[stage] = True

        def poll(self, stage):
            observed.append(("poll", stage))
            return (exits or {}).get(stage, 0)

        def active_pids(self):
            return {}

    return Fake


def run(
    tmp_path,
    p,
    observed,
    *,
    status="PASS",
    actual=True,
    publication_spawn_failure=False,
    gate_reader=None,
):
    return operator.supervise(
        tmp_path,
        tmp_path / "read_only_data",
        p=p,
        poll_seconds=0.01,
        launcher_factory=fake_launcher(
            observed, publication_spawn_failure=publication_spawn_failure
        ),
        sleeper=lambda seconds: observed.append(("sleep", seconds)),
        gate_reader=gate_reader or (lambda *args: closed(p, status)),
        report_reader=lambda *args: p.record(
            "execution_report", actual_complete=actual, status="COMPLETE_NO_POSITIVE_DIRECTION"
        ),
    )


def test_wait_then_parallel_seal_prepare_and_one_shot(tmp_path, p, monkeypatch):
    observed = []
    readiness = iter((None, closed(p)))
    result = run(tmp_path, p, observed, gate_reader=lambda *args: next(readiness))
    assert result["status"] == "COMPLETE_ACTUAL_EXECUTION_AND_SEALS"
    assert ("sleep", 0.01) in observed
    assert observed.index(("start", "prepare")) < observed.index(("poll", "materials_seal"))
    assert [stage for event, stage in observed if event == "start"] == [
        "materials_seal",
        "prepare",
        "execute",
        "results_seal",
    ]
    assert not (tmp_path / "raw").exists()
    assert (tmp_path / "raw_workflow/terminal.json").exists()
    before = list(observed)
    with pytest.raises(ValueError, match="one_shot"):
        run(tmp_path, p, observed)
    assert observed == before
    assert result["process_launcher_injected"] is True
    operator.verify_operator_source(tmp_path / "raw_workflow", p)
    monkeypatch.setattr(operator, "script_sha", lambda: "changed_operator_source")
    with pytest.raises(ValueError, match="source_changed_after_start"):
        operator.verify_operator_source(tmp_path / "raw_workflow", p)


def test_fail_gate_seals_closed_evidence_without_student(tmp_path, p):
    observed = []
    result = run(tmp_path, p, observed, status="FAIL")
    assert result["status"] == "STOP_EXISTING_MATERIAL_GATE_FAIL"
    assert not result["actual_execution_complete"]
    assert [stage for event, stage in observed if event == "start"] == ["materials_seal"]


def test_nonactual_execution_is_never_results_sealed(tmp_path, p):
    observed = []
    with pytest.raises(ValueError, match="actual_result_required"):
        run(tmp_path, p, observed, actual=False)
    assert ("start", "results_seal") not in observed
    terminal = p.read_json(tmp_path / "raw_workflow/terminal.json")
    assert terminal["status"] == "STOP_OPERATOR_OR_CHILD_FAILURE"
    assert terminal["automatic_retry"] is False


def test_publication_spawn_failure_does_not_become_scientific_gate(tmp_path, p):
    observed = []
    result = run(tmp_path, p, observed, publication_spawn_failure=True)
    assert result["status"] == "COMPLETE_ACTUAL_EXECUTION_PUBLICATION_FAILED"
    assert result["actual_execution_complete"]
    assert result["child_exit_codes"]["materials_seal"] == -1
    assert ("start", "execute") in observed and ("start", "results_seal") in observed


def test_read_only_existing_closure_joins(tmp_path, p):
    raw = tmp_path / "raw"
    assert operator.read_closed_gate(raw, p) is None
    supplied = closed(p)
    for filename, key in (
        ("material_gate.json", "gate"),
        ("generation_report.json", "generation"),
        ("budget_finalization.json", "finalization"),
    ):
        p.write_once(raw / filename, supplied[key])
    before = {path.name: path.read_bytes() for path in raw.iterdir()}
    assert operator.read_closed_gate(raw, p) == supplied
    assert {path.name: path.read_bytes() for path in raw.iterdir()} == before
