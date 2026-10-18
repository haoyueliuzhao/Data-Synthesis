import importlib
import subprocess
from types import SimpleNamespace

import finqa_v59_controller as controller


def test_control04_constructor_selects_only_new_registration_and_keeps_original_science(monkeypatch):
    captured, registration, science, runtime = {}, object(), object(), object()
    def original_init(self, root, **kwargs):
        captured.update(root=root, **kwargs)
    monkeypatch.setattr(controller.frozen.Controller, "__init__", original_init)
    monkeypatch.setattr(controller, "importlib", SimpleNamespace(import_module=lambda name:
        registration if name == "finqa_v59_registration" else
        SimpleNamespace(install_controller_runtime=lambda original: original)))
    controller.Controller(controller_attempt=2, scientific_registration=science, runtime=runtime)
    assert captured["root"] == controller.SCIENTIFIC_ROOT / "signal_recovery_04"
    assert captured["registration"] is registration
    assert captured["scientific_registration"] is science and captured["controller_attempt"] == 2
    calls = []
    router = controller._ImportRouter(SimpleNamespace(import_module=lambda name, package:
        calls.append((name, package)) or name))
    assert router.import_module("finqa_v57_registration") == "finqa_v59_registration"
    assert router.import_module("finqa_v56_registration") == "finqa_v56_registration"


def test_isolation_runtime_is_installed_lazily_before_inherited_constructor(monkeypatch):
    calls = []
    def measurement():
        raise AssertionError("constructing the runtime must not observe inventory or birth")
    original = SimpleNamespace(inventory=measurement, birth=measurement)
    proxy = SimpleNamespace(inventory=measurement, birth=measurement)
    def install(value):
        assert value is original
        calls.append("install")
        return proxy
    def construct(self, root, **kwargs):
        calls.append("constructor")
        assert kwargs["runtime"] is proxy
    monkeypatch.setattr(controller, "importlib", SimpleNamespace(import_module=lambda _name:
        SimpleNamespace(install_controller_runtime=install)))
    monkeypatch.setattr(controller.frozen.Controller, "__init__", construct)
    controller.Controller(registration=object(), runtime=original, scientific_registration=object())
    assert calls == ["install", "constructor"]


def test_inherited_launch_records_actual_v59_worker_and_continuous_scientific_attempt(tmp_path, monkeypatch):
    control = controller.Controller.__new__(controller.Controller)
    control.root, control.control_root = tmp_path / "science", tmp_path / "control04"
    control.protocol = dict(id="science", cpu_affinity={"4": "4-7"})
    control.control_protocol, control.controller_attempt = dict(id="control04"), 1
    key = "seed137.shard01"
    job = dict(job_id=key, seed=137, stage="shard01", kind="class", dependencies=[])
    control.jobs = {key: job}
    control.job_states = {key: dict(controller.frozen.inherited._initial_state(), attempts=5)}
    control.active, control.accepted, control.attempt_history = {}, {}, []
    control.resource_wait_seconds, control.evaluation_registered = 123.0, False
    control.runtime = SimpleNamespace(worker_environment=lambda _row: dict(KEEP_ENV="same"),
                                      birth=lambda _pid: "new-birth")
    control._audit = lambda _job: dict(resume_allowed=True, unknown_calls=0, progress_units=160,
                                     durable_progress_digest="actual-complete-task-cursor")
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
    assert str(control.control_root / "implementation/finqa_v59_worker.py") in command
    assert command[command.index("--root") + 1] == str(control.root)
    assert kwargs["env"]["V56_ATTEMPT_ID"] == "attempt0006"
    assert kwargs["env"]["V57_CONTROL_ROOT"] == str(control.control_root)
    assert kwargs["env"]["KEEP_ENV"] == "same" and kwargs["pass_fds"] == (123,)
    assert str(controller.REPO / "trusted_data_synthesis/scripts") in kwargs["env"]["PYTHONPATH"].split(":")
    assert record["protocol_id"] == "science" and record["control_protocol_id"] == "control04"


def test_controller_entry_and_adapter_bindings_do_not_change_global_process_or_stop_rules(tmp_path):
    original_import, original_popen = importlib.import_module, subprocess.Popen
    calls = []
    router = controller._ProcessRouter(SimpleNamespace(Popen=lambda command, **kwargs:
        calls.append(command)), tmp_path)
    command = [str(controller.PYTHON), "-u", str(tmp_path / "implementation/finqa_v57_controller.py"),
               "run", "--root", str(tmp_path)]
    router.Popen(command)
    assert calls[0] is command and command[2] == str(tmp_path / "implementation/finqa_v59_controller.py")
    assert importlib.import_module is original_import and subprocess.Popen is original_popen
    for method in ("_restore_journal", "_stop", "reap", "_accept_result"):
        assert getattr(controller.Controller, method) is getattr(controller.frozen.Controller, method)
    binding = controller.adapter_contract()
    assert binding["reused_implementation_id"] == "63525be8d361117a8dd0ee2f10265d9fa97e675da969e622580fadece8060e6f"
    assert binding["source_implementation_id"] == controller.FROZEN_IMPLEMENTATION_ID
    assert binding["signal_policy_wrapper_separately_registered"] is True
    assert controller._load_private_controller() is controller.frozen
