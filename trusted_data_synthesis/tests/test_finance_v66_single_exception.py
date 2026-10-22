"""CPU-only exact-scope and resource/lifecycle regression tests."""
from __future__ import annotations

import copy
import io
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import finqa_v66_registration as registration
registration.initialize()
import finqa_v66_binding as binding
import finqa_v66_controller as controller
import finqa_v66_diagnostics as diagnostics
import finqa_v66_temperature as temperature
import finqa_v66_worker as worker


@pytest.fixture(scope='module')
def exact():
    evidence = diagnostics.cpu_evidence()
    evidence['id'] = binding.digest(evidence)
    state = diagnostics.torch.load(io.BytesIO((binding.CHECKPOINT / 'state.pt').read_bytes()),
                                   map_location='cpu', weights_only=False)
    return evidence, state


def accumulator(exact):
    evidence, state = exact
    value = object.__new__(diagnostics.DrawAccumulator)
    value.cursor, value.denominator = 830, 700
    value.work = [None] * 830
    value.condition_id = evidence['condition_id']
    value.tolerances = diagnostics.original.MEAN_TOLERANCES
    value.draws = state['draw_components']['draws']
    value.mean_check_seconds_this_process = 0
    value.observe = lambda *_args, **_kwargs: None
    return value


def test_actual_checkpoint_and_fail_evidence(exact):
    evidence, _ = exact
    assert evidence['state_bytes'] == 30461727
    assert evidence['checkpoint_state']['sha256'] == 'f540252df99ab10edcc631926640e074a3918ced213404af7ed6022954b103eb'
    assert evidence['status'] == 'FAIL'
    assert evidence['report']['failed_element_count'] == 1
    assert evidence['report']['element_count'] == 2523136
    assert evidence['cause_established'] is False


def test_exact_exception_keeps_failure_and_formal_tensor(exact, monkeypatch):
    evidence, state = exact
    monkeypatch.setattr(diagnostics, 'checked_evidence', lambda: evidence)
    before = diagnostics.original.original.parameter_digest(state['total'])
    report = accumulator(exact).compare(state['total'])
    assert report['passed'] is False and report['status'] == 'FAIL'
    assert report['accepted_by_exception'] is True
    assert diagnostics.original.original.parameter_digest(state['total']) == before
    assert report['formal_gradient_replaced_by_component_mean'] is False


@pytest.mark.parametrize('field,value', [('cursor', 829), ('condition_id', 'different'), ('denominator', 698)])
def test_exception_rejects_another_scope(exact, monkeypatch, field, value):
    evidence, state = exact
    monkeypatch.setattr(diagnostics, 'checked_evidence', lambda: evidence)
    acc = accumulator(exact)
    setattr(acc, field, value)
    with pytest.raises(diagnostics.original.DrawDiagnosticError, match='exception does not apply'):
        acc.compare(state['total'])


def test_changed_formal_cannot_use_exception(exact, monkeypatch):
    evidence, state = exact
    monkeypatch.setattr(diagnostics, 'checked_evidence', lambda: evidence)
    total = {name: tensor.clone() for name, tensor in state['total'].items()}
    total[next(iter(total))].flatten()[0] += 0.1
    with pytest.raises(diagnostics.original.DrawDiagnosticError):
        accumulator(exact).compare(total)


def test_aggregate_L2_reporting_is_not_a_new_bitwise_gate(exact, monkeypatch):
    evidence, state = exact
    rounded = copy.deepcopy(evidence)
    rounded['report']['L2_error'] += 1e-18
    monkeypatch.setattr(diagnostics, 'checked_evidence', lambda: rounded)
    assert accumulator(exact).compare(state['total'])['accepted_by_exception'] is True


def test_original_backend_identity_is_unchanged():
    assert temperature.backend_identity is temperature.original.backend_identity
    assert temperature._compute.__code__ is temperature.original.feedback_gradient.__code__


def test_missing_checkpoint_cannot_replay(exact, monkeypatch):
    evidence, _ = exact
    monkeypatch.setattr(diagnostics, 'checked_evidence', lambda: evidence)
    monkeypatch.setattr(binding, 'sha', lambda _path: 'changed')
    monkeypatch.setattr(temperature, '_compute', lambda *_args, **_kwargs: pytest.fail('entered formal loop'))
    with pytest.raises(ValueError, match='complete830'):
        temperature.feedback_gradient(condition={'id': evidence['condition_id']})


def test_original_raw_C_diagnostic_failure_not_waived(monkeypatch):
    from trusted_synthesis.experiments.finance_qa_vnext_anchored_vtdo import optimizer_pullback as adam
    monkeypatch.setattr(adam, 'pullback', lambda *_args: {'a': {'x': diagnostics.torch.ones(1)}})
    monkeypatch.setattr(adam, 'centered_contributions', lambda *_args: {'C': {'task': {'slot': 1.0}}})
    rt = SimpleNamespace(v8=SimpleNamespace(parameter_digest=lambda _values: 'digest'))
    monitor = SimpleNamespace(check_stop=lambda *_args, **_kwargs: None,
                              clear_unused=lambda *_args: None)
    replay = {'draw_gJ': {seed: {'x': diagnostics.torch.ones(1)} for seed in (101, 103)}}
    with pytest.raises(diagnostics.original.DrawDiagnosticError, match='raw C mean differs'):
        worker._worker.draw_contributions({'G': {'x': diagnostics.torch.ones(1)}, 'binding': None},
            [], replay, {'task': {'slot': 0.0}}, {'pi': {}}, {'mu': 0}, rt, monitor)


def test_saved_payload_retry_retains_restored830(exact, tmp_path, monkeypatch):
    evidence, _ = exact
    directory = tmp_path / 'replay'
    (directory / 'payload').mkdir(parents=True)
    (directory / 'payload/record.json').write_text('{}')
    value = dict(condition={'id': evidence['condition_id']}, gJ={}, draw_gJ={101: {}, 103: {}},
        report=dict(complete_replay=True, denominator=700, gJ_digest='digest',
                    response_checkpoint_binding={'response_count': 830}, restored_completed_responses=830))
    monkeypatch.setattr(worker._worker, 'read_payload', lambda *_args: value)
    monkeypatch.setattr(worker._worker, '_condition', lambda *_args: value['condition'])
    monkeypatch.setattr(diagnostics, 'accepted_exception', lambda _value: True)
    monkeypatch.setattr(diagnostics, 'checked_evidence', lambda: evidence)
    monkeypatch.setattr(worker._worker.binding, 'entry', lambda _path: {'id': 'payload'})
    rt = SimpleNamespace(v8=SimpleNamespace(parameter_digest=lambda _value: 'digest'))
    result = worker._worker.execute_replay(None, directory, None, None, None, None, rt, None, arm='C05')
    assert result['restored_completed_responses'] == result['responses'] == 830
    assert result['replayed_responses'] == 0
    assert result['draw_diagnostics_passed'] is False


def test_only_three_states_unlock_and_old_journal_is_unchanged():
    original = binding.checked(binding.OLD_CONTROL / 'journal/state.json')
    before = copy.deepcopy(original)
    restored = controller.restore_states(original)
    assert original == before
    assert {key for key, row in restored.items() if row['status'] == 'PENDING'} == set(binding.JOBS)
    assert len([row for row in restored.values() if row['status'] == 'COMPLETE']) == 21


def test_another_hard_block_is_not_eligible():
    journal = binding.checked(binding.OLD_CONTROL / 'journal/state.json')
    journal['job_states']['seed137.train_C1']['status'] = 'HARD_BLOCKED'
    with pytest.raises(ValueError, match='another hard failure'):
        controller.restore_states(journal)


@pytest.mark.parametrize('seed,stage', [(137, 'replay_C05'), (389, 'replay_C1'), (389, 'feedback_C05')])
def test_worker_scope_rejects_unapproved_jobs(seed, stage):
    with pytest.raises(ValueError, match='three seed389'):
        binding.scope(worker._worker.job_spec(seed, stage))


def test_one_worker_includes_draining():
    value = object.__new__(controller.Controller)
    value.active = {'job': SimpleNamespace(lifecycle='DRAINING')}
    assert value.can_dispatch() is False
    value.active['second'] = object()
    with pytest.raises(ValueError, match='one-worker'):
        value.can_dispatch()


def test_host_admission_reserves_full_peer_240GiB(monkeypatch):
    value = object.__new__(controller.Controller)
    value.active = {}
    value._memory = lambda: []
    value.runtime = SimpleNamespace(host_memory=lambda: {'available_bytes': 383 * 1024 ** 3})
    monkeypatch.setattr(controller.base, 'host_requirement', lambda *_args: 144 * 1024 ** 3)
    assert value._host_gate({'kind': 'train'}) is None
    value.runtime.host_memory = lambda: {'available_bytes': 384 * 1024 ** 3}
    gate = value._host_gate({'kind': 'train'})
    assert gate['required_bytes'] == 384 * 1024 ** 3
    assert gate['peer_V65_startup_reserved_bytes'] == 240 * 1024 ** 3


def test_control_path_has_shared_owner_and_no_evaluation_dispatch():
    assert controller.Controller.run.__code__.co_filename.endswith('::V66_registered_adapter')
    assert controller.Controller.finish.__code__.co_names.count('score') == 0
    assert 'prepare_jobs' not in controller.Controller.seal_training.__code__.co_names
    assert 'LOCK_SH' in controller.Controller.run.__code__.co_names
