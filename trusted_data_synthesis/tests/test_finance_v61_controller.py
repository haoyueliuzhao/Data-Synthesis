"""CPU-only six-worker routing tests; no science preflight or process launch."""
import ast
import copy
from pathlib import Path
from types import SimpleNamespace

import pytest

import finqa_v61_controller as control


def active(count):
    return {str(index): SimpleNamespace(gpu=index, lifecycle='INITIALIZING') for index in range(count)}


def test_private_cap_admits_four_and_five_stops_six_rejects_seven_and_duplicate_gpu():
    assert control.can_dispatch(active(4)) is True
    assert control.can_dispatch(active(5)) is True
    assert control.can_dispatch(active(6)) is False
    with pytest.raises(ValueError, match='six-worker'):
        control.can_dispatch(active(7))
    duplicate = active(2)
    duplicate['1'].gpu = 0
    with pytest.raises(ValueError, match='physical GPU'):
        control.can_dispatch(duplicate)


def test_actual_controller_and_old_worker_argv_are_mutated_before_popen():
    root = control.MASTER_ROOT / 'episodes/episode000001'
    seen = []
    router = control.ProcessRouter(SimpleNamespace(Popen=lambda command, **kwargs: seen.append(list(command))), root)
    for source, target in (
        ('finqa_v57_controller.py', control.MASTER_ROOT / 'implementation/finqa_v61_controller.py'),
        ('finqa_v57_worker.py', control.SOURCE_CONTROL_ROOT / 'implementation/finqa_v59_worker.py')):
        command = ['/usr/bin/taskset', '--cpu-list', '0-37', str(control.PYTHON), '-u',
                   str(root / 'implementation' / source), '--root', str(control.SCIENCE_ROOT)]
        router.Popen(command)
        assert command[5] == str(target) and seen[-1] == command
    with pytest.raises(ValueError, match='mutable'):
        router.Popen((str(control.PYTHON), '-u', str(root / 'implementation/finqa_v57_controller.py')))


def test_constructor_checks_original_four_then_routes_acquire_to_six_without_mutating_protocol():
    scientific = dict(id='original-science', max_gpu_workers=4, value='unchanged')
    untouched = copy.deepcopy(scientific)
    registered = dict(id='new-control', scientific_protocol_id='original-science',
        original_scientific_max_gpu_workers=4, max_gpu_workers=6, per_gpu_workers=1,
        resource_override=control.resource_override_contract())
    old_calls = []
    namespace = dict(can_dispatch=lambda workers: old_calls.append(len(workers)) or len(workers) < 4)
    exec('def acquire(self, job):\n    return can_dispatch(self.active) and self.original_host_and_GPU_gate(job)\n', namespace)
    frozen_acquire = namespace['acquire']
    base = SimpleNamespace(MAX_WORKERS=4, Controller=SimpleNamespace(acquire=frozen_acquire))

    class Original:
        def __init__(self, science, amended):
            assert self._v61_override_applied is False
            assert base.MAX_WORKERS == science['max_gpu_workers'] == 4
            self.protocol, self.control_protocol = science, amended
            self.active = active(4)
            self.original_host_and_GPU_gate = lambda job: job['host_and_gpu_pass']

    derived = control.controller_class(Original, base)
    instance = derived(scientific, registered)
    assert instance._v61_override_applied is True
    assert instance.acquire(dict(host_and_gpu_pass=True)) is True
    assert instance.acquire(dict(host_and_gpu_pass=False)) is False
    assert old_calls == [] and scientific == untouched and base.MAX_WORKERS == 4
    assert derived._v61_acquire_function.__code__ is frozen_acquire.__code__
    assert namespace['can_dispatch'](active(4)) is False
    invalid = dict(registered, max_gpu_workers=4)
    with pytest.raises(ValueError, match='six-worker control amendment'):
        derived(scientific, invalid)


def test_journal_and_status_report_effective_six_with_original_four_provenance(tmp_path):
    emitted = []
    delegate = SimpleNamespace(MAX_WORKERS=4, _status=lambda path, value: emitted.append((path, value)))
    evaluation = SimpleNamespace(bound=lambda body: {**body, 'id': control.digest(body)})
    proxy = control.DispatchBase(delegate, tmp_path, evaluation)
    source = dict(schema='v57_actual_job_attempt_journal.v1', protocol_id='same-science',
                  control_protocol_id='new-control', active_jobs=list(active(6)))
    original = evaluation.bound(source)
    proxy._status(tmp_path / 'journal/state.json', original)
    journal = emitted[-1][1]
    assert original == evaluation.bound(source)
    assert journal['max_gpu_workers'] == journal['effective_max_gpu_workers'] == 6
    assert journal['original_scientific_max_gpu_workers'] == 4
    assert journal['protocol_id'] == 'same-science'
    assert journal['id'] == control.digest({key: value for key, value in journal.items() if key != 'id'})
    proxy._status(tmp_path / 'queue/status.json', dict(schema='v57_per_job_queue.v1',
        protocol_id='same-science', control_protocol_id='new-control', max_gpu_workers=4))
    assert emitted[-1][1]['max_gpu_workers'] == 6
    assert delegate.MAX_WORKERS == proxy.MAX_WORKERS == 4


def test_frozen_RAM_formula_unchanged_for_six_generate_and_rss_hard_limit():
    # Evaluate only two small original pure functions, not scientific imports.
    path = control.SCIENCE_ROOT / 'implementation/finqa_v54_controller.py'
    tree = ast.parse(path.read_text())
    selected = [node for node in tree.body if isinstance(node, ast.FunctionDef)
                and node.name in ('_kind_key', 'host_requirement')]
    assert len(selected) == 2
    gib = 1024 ** 3
    namespace = dict(GIB=gib, HOST_RESERVE_BYTES=96 * gib,
        HOST_STARTUP_GIB=control.resource_override_contract()['host_startup_gib_by_kind'], require=control.require)
    exec(compile(ast.Module(body=selected, type_ignores=[]), str(path), 'exec'), namespace)
    worker = dict(kind='generate', memory=dict(rss_bytes=0, peak_rss_bytes=0))
    assert namespace['host_requirement']('generate', [worker] * 5) == 384 * gib
    occupied = dict(kind='generate', memory=dict(rss_bytes=20 * gib, peak_rss_bytes=20 * gib))
    assert namespace['host_requirement']('generate', [occupied] * 5) == 284 * gib
    bad = dict(kind='generate', memory=dict(rss_bytes=193 * gib, peak_rss_bytes=193 * gib))
    with pytest.raises(ValueError, match='RSS hard gate'):
        namespace['host_requirement']('generate', [bad])
