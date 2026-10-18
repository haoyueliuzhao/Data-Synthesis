from types import SimpleNamespace

import pytest

import finqa_v59_observer as observer


def test_original_observer_is_byte_bound_and_unchanged():
    original = observer.load_original()
    assert original is observer.load_original()
    assert original.observer_policy()['event_log_total_max_bytes'] == 64 * 1024**2
    assert original.observer_policy()['scientific_processes_signaled'] is False
    assert observer.ROOT.name == 'signal_recovery_04'


def test_policy_keeps_original_limits_and_does_not_claim_root_protection(monkeypatch):
    import sys
    monkeypatch.setitem(sys.modules, 'finqa_v59_signals',
        SimpleNamespace(signals_policy=lambda: {'owner_uid': 1004, 'only_SI_USER': True}))
    policy = observer.observer_policy()
    assert policy['signal_install_before_observer_threads'] is True
    assert policy['signals_policy']['owner_uid'] == 1004
    assert policy['original_bounded_observer']['environment_argv_credentials_history_read'] is False
    assert not policy['process_UID_changed'] and not policy['SIGKILL_protection_claimed']


def test_old_observer_control_root_is_not_restarted():
    with pytest.raises(ValueError, match='registered V59'):
        observer.checked_control(observer.SOURCE_ROOT, observer.SCIENCE_ROOT)
