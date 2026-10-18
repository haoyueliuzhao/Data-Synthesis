import subprocess
import os
from types import SimpleNamespace

import pytest

import finqa_v60_binding as binding
import finqa_v60_controller as controller
import finqa_v60_observer as observer


def test_episode_cannot_restart_initial_control_or_escape_watchdog():
    with pytest.raises(ValueError):
        binding.episode_root(binding.SOURCE_CONTROL_ROOT)
    with pytest.raises(ValueError):
        binding.episode_root(binding.MASTER_ROOT / 'episode0001')
    root = binding.MASTER_ROOT / 'episodes/episode0001'
    assert binding.episode_root(root) == root
    assert controller.adapter_contract(root)['control_root'] == str(root)


def test_redirect_records_real_new_controller_and_unchanged_V59_worker():
    root = binding.MASTER_ROOT / 'episodes/episode0001'
    seen = []
    router = controller.ProcessRouter(SimpleNamespace(Popen=lambda command, **kwargs: seen.append(list(command))), root)
    command = [str(binding.PYTHON), '-u', str(root / 'implementation/finqa_v57_worker.py'), '--root', str(binding.SCIENCE_ROOT)]
    router.Popen(command)
    assert seen[0] == command
    assert command[2] == str(binding.SOURCE_CONTROL_ROOT / 'implementation/finqa_v59_worker.py')
    command = [str(binding.PYTHON), '-u', str(root / 'implementation/finqa_v57_controller.py'), 'run']
    router.Popen(command)
    assert command[2] == str(binding.MASTER_ROOT / 'implementation/finqa_v60_controller.py')


def test_constructor_delegates_episode_and_GPU_owner_proxy_without_measurement(monkeypatch):
    root = binding.MASTER_ROOT / 'episodes/episode0001'
    values = {}
    original_runtime, proxy, registration = object(), object(), object()
    def build(actual_root, **kwargs):
        values.update(root=actual_root, **kwargs)
        return values
    monkeypatch.setattr(controller, 'private_controller', lambda _: SimpleNamespace(Controller=build))
    monkeypatch.setattr(controller, 'load_v59_module', lambda _: SimpleNamespace(
        install_controller_runtime=lambda runtime: proxy if runtime is original_runtime else pytest.fail('runtime changed')))
    controller.Controller(root, runtime=original_runtime, registration=registration, controller_attempt=2)
    assert values['runtime'] is proxy and values['registration'] is registration
    assert values['root'] == root and values['controller_attempt'] == 2


def test_private_controller_source_and_global_subprocess_remain_unchanged():
    # Pytest fixtures can import the workspace scientific package before a
    # lazy control loader runs. The production guard correctly rejects that
    # mixture; test the real entry in its own clean CPU import process.
    program = '''
import subprocess
import finqa_v60_controller as controller
from finqa_v60_binding import MASTER_ROOT, SCIENCE_ROOT
native = subprocess.Popen
root = MASTER_ROOT / 'episodes/episode0001'
frozen = controller.private_controller(root)
assert frozen.ROOT == root and frozen.SCIENTIFIC_ROOT == SCIENCE_ROOT
assert subprocess.Popen is native
assert controller.private_controller(root) is frozen
'''
    result = subprocess.run([str(binding.PYTHON), '-c', program], cwd=binding.REPO,
        env=dict(os.environ, PYTHONPATH=str(binding.REPO / 'trusted_data_synthesis/scripts')),
        capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_observer_retains_single_read_only_monitor_and_original_stop_policy():
    policy = observer.observer_policy()
    assert policy['only_one_independent_observer'] and not policy['other_processes_signaled']
    assert policy['signals_policy']['owner_SIGTERM_dispatches_original_stop']
    assert policy['signals_policy']['every_SIGINT_dispatches_original_stop']
    assert not policy['SIGKILL_protection_claimed']
