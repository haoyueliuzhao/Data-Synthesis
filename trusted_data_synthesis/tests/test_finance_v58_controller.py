import hashlib
import importlib
import subprocess
import sys
from types import SimpleNamespace

import pytest

_original_public_controller = sys.modules.get("finqa_v57_controller")
_original_popen = subprocess.Popen
_original_import = importlib.import_module

import finqa_v58_controller as controller


def test_private_adapter_preserves_frozen_bytes_and_global_modules():
    frozen = controller.frozen
    assert hashlib.sha256(open(frozen.__file__, "rb").read()).hexdigest() == controller.FROZEN_CONTROLLER_SHA256
    assert frozen.ROOT == controller.ROOT == controller.SCIENTIFIC_ROOT / "signal_recovery_03"
    assert sys.modules.get("finqa_v57_controller") is _original_public_controller
    assert subprocess.Popen is _original_popen and importlib.import_module is _original_import
    assert frozen.subprocess.delegate is subprocess and frozen.importlib.delegate is importlib
    assert controller._load_private_controller() is frozen


def test_registration_router_redirects_only_the_exact_control_registration():
    calls = []
    router = controller._ImportRouter(SimpleNamespace(import_module=lambda name, package:
        calls.append((name, package)) or name))
    assert router.import_module("finqa_v57_registration") == "finqa_v58_registration"
    assert router.import_module("finqa_v56_registration") == "finqa_v56_registration"
    assert router.import_module("finqa_v57_registration.extra") == "finqa_v57_registration.extra"
    assert router.import_module(".local", "a_package") == ".local"
    assert calls[-1] == (".local", "a_package")


def test_process_router_updates_recorded_argv_in_place_and_preserves_other_commands(tmp_path):
    calls = []
    delegate = SimpleNamespace(Popen=lambda command, **kwargs: calls.append((command, kwargs)) or "child")
    router = controller._ProcessRouter(delegate, tmp_path)
    environment = dict(PYTHONPATH="unchanged", V57_CONTROL_ROOT=str(tmp_path))
    command = [str(controller.PYTHON), "-u", str(tmp_path / "implementation/finqa_v57_controller.py"),
               "run", "--root", str(tmp_path), "--controller-attempt", "2"]
    identity = id(command)
    assert router.Popen(command, env=environment) == "child"
    assert id(command) == identity and calls[0][0] is command and calls[0][1]["env"] is environment
    assert command[2] == str(tmp_path / "implementation/finqa_v58_controller.py")
    assert command[3:] == ["run", "--root", str(tmp_path), "--controller-attempt", "2"]
    unrelated = [str(controller.PYTHON), "-u", "/unrelated/finqa_v57_controller.py"]
    router.Popen(unrelated)
    assert unrelated[2] == "/unrelated/finqa_v57_controller.py"
    with pytest.raises(ValueError, match="mutable original argv"):
        router.Popen((str(controller.PYTHON), "-u", str(tmp_path / "implementation/finqa_v57_worker.py")))


def test_real_inherited_launch_record_names_actual_v58_worker_and_original_helpers(tmp_path, monkeypatch):
    control = controller.Controller.__new__(controller.Controller)
    control.root, control.control_root = tmp_path / "science", tmp_path / "control"
    control.protocol = dict(id="science", cpu_affinity={"4": "4-7"})
    control.control_protocol = dict(id="control03")
    control.controller_attempt = 1
    key = "seed137.shard01"
    job = dict(job_id=key, seed=137, stage="shard01", kind="class", dependencies=[])
    control.jobs = {key: job}
    control.job_states = {key: dict(controller.frozen.inherited._initial_state(), attempts=4)}
    control.active, control.accepted, control.attempt_history = {}, {}, []
    control.resource_wait_seconds, control.evaluation_registered = 123.0, False
    control.runtime = SimpleNamespace(worker_environment=lambda _row: dict(KEEP_ENV="same"),
                                      birth=lambda _pid: "new-birth")
    control._audit = lambda _job: dict(resume_allowed=True, unknown_calls=0, progress_units=7,
                                     durable_progress_digest="actual-old-task-boundary")
    calls = []
    def popen(command, **kwargs):
        calls.append((list(command), kwargs))
        return SimpleNamespace(pid=99999999, poll=lambda: None)
    monkeypatch.setattr(controller.frozen, "subprocess", controller._ProcessRouter(
        SimpleNamespace(Popen=popen, STDOUT=subprocess.STDOUT), control.control_root))
    lease = SimpleNamespace(fileno=lambda: 123, close=lambda: None)
    control.launch(job, (dict(index=4, uuid="GPU-registered"), lease, dict(original_gates=True)))
    command, kwargs = calls[0]
    child = control.active[key]
    record = controller.evaluation.checked(child.attempt_dir / "launch/record.json")
    assert record["command"] == command
    assert str(control.control_root / "implementation/finqa_v58_worker.py") in record["command"]
    assert str(control.control_root / "implementation/finqa_v57_worker.py") not in record["command"]
    assert record["command"][record["command"].index("--root") + 1] == str(control.root)
    assert kwargs["env"]["KEEP_ENV"] == "same" and kwargs["pass_fds"] == (123,)
    assert kwargs["env"]["V56_ATTEMPT_ID"] == "attempt0005"
    assert str(controller.REPO / "trusted_data_synthesis/scripts") in kwargs["env"]["PYTHONPATH"].split(":")
    assert record["protocol_id"] == "science" and record["control_protocol_id"] == "control03"


def test_subclass_passes_new_registration_without_changing_scientific_registration(monkeypatch):
    actual, new_registration, scientific_registration = {}, object(), object()
    def original_init(self, root, **kwargs):
        actual.update(root=root, **kwargs)
    monkeypatch.setattr(controller.frozen.Controller, "__init__", original_init)
    monkeypatch.setattr(controller, "importlib", SimpleNamespace(import_module=lambda name:
        new_registration if name == "finqa_v58_registration" else pytest.fail("unexpected registration import")))
    controller.Controller(scientific_registration=scientific_registration)
    assert actual["root"] == controller.ROOT
    assert actual["registration"] is new_registration
    assert actual["scientific_registration"] is scientific_registration


def test_stop_resource_retry_and_durable_acceptance_methods_are_exactly_inherited():
    for name in ("_restore_journal", "launch", "run", "_stop", "reap", "ready", "_accept_result", "finish"):
        assert getattr(controller.Controller, name) is getattr(controller.frozen.Controller, name)
    contract = controller.adapter_contract()
    assert contract["registration_redirect"] == {"finqa_v57_registration": "finqa_v58_registration"}
    assert contract["actual_argv_mutated_before_Popen_and_launch_record"] is True
    assert contract["frozen_bytes_mathematics_resources_and_explicit_stop_rules_unchanged"] is True
