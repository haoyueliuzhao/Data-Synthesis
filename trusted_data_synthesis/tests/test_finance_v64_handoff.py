"""Narrow maintenance identity/signal barriers; never sends a real signal."""
from __future__ import annotations

import copy
import signal

import pytest

import finqa_v64_binding as binding
import finqa_v64_handoff as handoff


def receipt(sender=10):
    return dict(pid=20, signal=signal.SIGTERM, si_pid=sender, si_uid=binding.OWNER_UID,
                si_code=0, at_epoch=100.0, schema='v59_received_signal_kernel_receipt.v1',
                provenance='kernel_sigwaitinfo', receipt_queue_drops_before=0)


def check(rows):
    return handoff.check_receipts(rows, target=20, allowed_senders={10, 30},
                                  after_epoch=99, required_sender=10)


def test_maintenance_and_one_parent_propagation_allowed():
    check([receipt(), receipt(30)])


@pytest.mark.parametrize('change', [dict(pid=21), dict(signal=signal.SIGINT),
    dict(si_pid=40), dict(si_uid=1008), dict(si_code=-1), dict(at_epoch=98)])
def test_unrelated_or_ambiguous_legal_stop_rejected(change):
    value = receipt()
    value.update(change)
    with pytest.raises(ValueError, match='unrelated or ambiguous'):
        check([value])


def test_missing_or_duplicate_actual_receipt_rejected():
    with pytest.raises(ValueError, match='missing'):
        check([receipt(30)])
    with pytest.raises(ValueError, match='repeated'):
        check([receipt(), receipt()])


def test_non_pidfd_path_signals_exact_registered_controller_once(monkeypatch):
    monkeypatch.delattr(handoff.os, 'pidfd_open', raising=False)
    monkeypatch.setattr(handoff, 'alive', lambda value: True)
    observed = []
    monkeypatch.setattr(handoff.os, 'kill', lambda pid, number: observed.append((pid, number)))
    handoff.signal_once(dict(pid=20, birth='a'), dict(pid=30, birth='b'))
    assert observed == [(20, signal.SIGTERM)]


def test_identity_change_prevents_any_signal(monkeypatch):
    monkeypatch.delattr(handoff.os, 'pidfd_open', raising=False)
    monkeypatch.setattr(handoff, 'alive', lambda value: False)
    monkeypatch.setattr(handoff.os, 'kill', lambda *args: pytest.fail('must not signal'))
    with pytest.raises(ValueError, match='identity changed'):
        handoff.signal_once(dict(pid=20, birth='a'), dict(pid=30, birth='b'))


def journal():
    feedback = {f'seed{seed}.feedback_{arm}': {} for seed in (137, 251, 389) for arm in ('C1', 'C05')}
    return dict(protocol_id=binding.BASE_PROTOCOL_ID, updated_epoch=100,
        evaluation_registered=False, accepted=feedback,
        job_states={'seed137.replay_C1': dict(status='RUNNING')},
        active_jobs=[dict(job_id='seed137.replay_C1', pid=20, birth='a', gpu_index=0)])


def test_only_fresh_complete_feedback_live_replay_is_admitted(monkeypatch):
    monkeypatch.setattr(handoff.time, 'time', lambda: 101)
    monkeypatch.setattr(handoff, 'alive', lambda value: True)
    source = journal()
    assert handoff.checked_before(source, dict(max_gpu_workers=6)) == source
    invalid = []
    row = copy.deepcopy(source); row['updated_epoch'] = 60; invalid.append(row)
    row = copy.deepcopy(source); row['accepted'].pop('seed137.feedback_C1'); invalid.append(row)
    row = copy.deepcopy(source); row['job_states']['seed137.replay_C1']['status'] = 'DISPATCHING'; invalid.append(row)
    row = copy.deepcopy(source); row['evaluation_registered'] = True; invalid.append(row)
    for row in invalid:
        with pytest.raises(ValueError):
            handoff.checked_before(row, dict(max_gpu_workers=6))


def test_replay_pause_with_concurrent_resource_failure_cannot_resume(monkeypatch):
    report = dict(all_gates_passed=True, observed_violation=None,
        single_process_lifetime_includes_loading=True, peak_resets_after_loading=0,
        peak_resets_before_loading=1, actual_boundary_observations=2,
        peak_allocated_bytes=32 * 1024 ** 3, minimum_boundary_free_bytes=4 * 1024 ** 3,
        peak_rss_bytes=30 * 1024 ** 3, minimum_host_available_bytes=300 * 1024 ** 3)
    active = dict(pid=20, birth='a')
    closed = dict(protocol_id=binding.BASE_PROTOCOL_ID, job_id='seed137.replay_C1',
        **active, resources=report, status='FAILED_OR_STOPPED', error={'type': 'ReplayPaused'})
    failure = dict(CUDA_initialized=True, resources=report, resource_closeout={}, exception_type='ReplayPaused')
    monkeypatch.setattr(binding, 'read_ref', lambda reference: closed)
    handoff.checked_maintenance_resources(failure, active, 'seed137.replay_C1')
    report['observed_violation'] = {'reason': 'host shortage'}
    with pytest.raises(ValueError, match='concurrent resource failure'):
        handoff.checked_maintenance_resources(failure, active, 'seed137.replay_C1')


def test_failed_new_start_is_terminal_before_barrier_release(monkeypatch, tmp_path):
    from types import SimpleNamespace
    monkeypatch.setattr(binding, 'ROOT', tmp_path)
    monkeypatch.setattr(handoff, 'alive', lambda target: False)
    process = SimpleNamespace(pid=123, poll=lambda: 2)
    assert handoff.stop_failed_start({'id': 'control'}, process, 'birth') is True
    marker = binding.checked(tmp_path / 'control/stop_requested/record.json')
    assert marker['automatic_restart_allowed'] is False
    proof = binding.checked(tmp_path / 'handoff/failed_start_stop/record.json')
    assert proof['all_new_control_identities_exited'] is True
