"""Effective six-worker routing with V62 actual worker and unchanged math."""
import copy
from pathlib import Path
from types import SimpleNamespace

import pytest

import finqa_v62_controller as control


def active(count):
    return {str(index): SimpleNamespace(gpu=index, lifecycle='INITIALIZING') for index in range(count)}


def test_effective_six_counts_initializing_waiting_draining_and_one_per_GPU():
    assert control.can_dispatch(active(5))
    assert not control.can_dispatch(active(6))
    with pytest.raises(ValueError, match='six-worker'):
        control.can_dispatch(active(7))
    duplicate = active(2)
    duplicate['1'].gpu = 0
    with pytest.raises(ValueError, match='physical GPU'):
        control.can_dispatch(duplicate)


def test_actual_Popen_and_record_argv_use_new_V62_worker():
    root, seen = control.MASTER_ROOT / 'episodes/episode000001', []
    router = control.ProcessRouter(SimpleNamespace(Popen=lambda command: seen.append(list(command))), root)
    for kind in ('controller', 'worker'):
        command = ['/usr/bin/taskset', '--cpu-list', '0-37', str(control.PYTHON), '-u',
                   str(root / f'implementation/finqa_v57_{kind}.py')]
        router.Popen(command)
        assert command[-1] == str(control.MASTER_ROOT / f'implementation/finqa_v62_{kind}.py')
        assert seen[-1] == command
    assert Path(control.gpu_isolation().__file__).name == 'finqa_v62_gpu_isolation.py'
    assert control.gpu_isolation().gpu_isolation_policy()['excluded_host_uid'] is None


def test_private_six_override_retains_original_four_constructor_and_all_resource_gates():
    science = dict(id='same-science', max_gpu_workers=4)
    untouched = copy.deepcopy(science)
    amendment = dict(scientific_protocol_id='same-science', original_scientific_max_gpu_workers=4,
        max_gpu_workers=6, per_gpu_workers=1, resource_override=control.resource_override_contract())
    namespace = dict(can_dispatch=lambda workers: len(workers) < 4)
    exec('def acquire(self, job):\n    return can_dispatch(self.active) and self.original_resource_gate(job)\n', namespace)
    acquire = namespace['acquire']
    base = SimpleNamespace(MAX_WORKERS=4, Controller=SimpleNamespace(acquire=acquire))
    class Original:
        def __init__(self):
            assert self._v62_override_applied is False and base.MAX_WORKERS == science['max_gpu_workers'] == 4
            self.protocol, self.control_protocol, self.active = science, amendment, active(5)
            self.original_resource_gate = lambda job: job['pass']
    derived = control.controller_class(Original, base)
    instance = derived()
    assert instance.acquire({'pass': True})
    assert not instance.acquire({'pass': False})
    assert derived._v62_acquire_function.__code__ is acquire.__code__
    assert science == untouched and base.MAX_WORKERS == 4

