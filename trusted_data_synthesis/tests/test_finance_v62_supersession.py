"""Only temporary files and an in-memory crontab; no real signals or tasks."""
import fcntl
import os
from pathlib import Path
import time
from types import SimpleNamespace
import pytest
import finqa_v62_supersession as s


@pytest.fixture
def env(tmp_path, monkeypatch):
    science = tmp_path / 'science'
    root, old, guard, source = [science / name for name in ('prep', 'old61', 'old60', 'source04')]
    for path in (root, old, guard, source):
        path.mkdir(parents=True)
    for key, value in (('PREPARATION_ROOT', root), ('SCIENCE_ROOT', science),
            ('SUPERSEDED_MASTER_ROOT', old), ('PARENT_WATCHDOG_ROOT', guard), ('SOURCE_CONTROL_ROOT', source)):
        monkeypatch.setattr(s, key, value)
    monkeypatch.setattr(os, 'getuid', lambda: 1004)
    monkeypatch.setattr(os, 'geteuid', lambda: 1004)
    monkeypatch.setattr(os, 'kill', lambda *a: pytest.fail('no process signal is permitted'))
    monkeypatch.setattr(s, 'owner_uid', lambda _: (1004,)*4)
    monkeypatch.setattr(s, 'identity', lambda pid, birth: dict(pid=pid, birth=birth, proc_state='S',
        alive=not (pid == s.OBSERVER_PID and (old / 'terminal/record.json').exists())))
    paths = [science / 'owner.lock', *[science / 'locks' / f'gpu{i}.lock' for i in range(8)]]
    for path in [*paths, old / 'cron/crontab_change.lock']:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch()
    source_protocol = s.publish(source / 'protocol/record.json', dict(scientific_protocol_id=s.SCIENTIFIC_PROTOCOL_ID))
    monkeypatch.setattr(s, 'SOURCE_CONTROL_PROTOCOL_ID', source_protocol['id'])
    guard_protocol = s.publish(guard / 'protocol/record.json', dict(source='v60'))
    monkeypatch.setattr(s, 'PARENT_WATCHDOG_PROTOCOL_ID', guard_protocol['id'])
    core = [f'core{i}' for i in range(23)]
    old_protocol = s.publish(old / 'protocol/record.json', dict(
        original_lock_bindings={str(path): {k: v for k, v in s.inode(path).items() if k != 'path'} for path in paths},
        handoff_binding=dict(id='fixed-handoff', core_job_ids=core,
            controls={'controller':dict(pid=101, birth='one'), 'supervisor':dict(pid=102, birth='two')})))
    monkeypatch.setattr(s, 'SUPERSEDED_MASTER_PROTOCOL_ID', old_protocol['id'])
    s.publish(old / 'implementation/record.json', dict(files={'old.py':'hash'}))
    s.publish(old / 'cron/status.json', dict(status='PASSIVE_HANDOFF_RUNNING',
        handoff_status='WAITING_FOR_ACCEPTED_TRAINING_CORE', invocation=dict(pid=s.OBSERVER_PID,birth=s.OBSERVER_BIRTH)))
    journal = dict(protocol_id=s.SCIENTIFIC_PROTOCOL_ID, control_protocol_id=s.SOURCE_CONTROL_PROTOCOL_ID,
        controller_attempt=1, updated_epoch=time.time(), accepted={key:{} for key in core[:-1]},
        job_states={key:dict(status='COMPLETE' if key in core[:-1] else 'RUNNING') for key in core},
        active_jobs=[dict(pid=999,birth='worker',gpu_index=2)])
    s.publish(source / 'journal/state.json', journal)
    return SimpleNamespace(root=root,old=old,guard=guard,source=source,science=science,core=core,journal=journal)


class FakeCron:
    def __init__(self, *, fail_write=False):
        self.raw = b'MAILTO=private_fixture\n1 1 * * * other-task\n'+s.exact_line(60,s.PARENT_WATCHDOG_ROOT)+b'\n'+s.exact_line(61,s.SUPERSEDED_MASTER_ROOT)+b'\n'
        self.writes = 0
        self.fail_write = fail_write

    def __call__(self, command, **kwargs):
        assert 0 < kwargs['timeout'] <= 10
        if command == ['crontab','-l']:
            return SimpleNamespace(returncode=0,stdout=self.raw,stderr=b'')
        assert command == ['crontab','-']
        self.writes += 1
        if self.fail_write:
            raise OSError('uncertain mock write')
        self.raw = kwargs['input']
        return SimpleNamespace(returncode=0,stdout=b'',stderr=b'')


def test_pure_snapshot_and_prepare_do_not_touch_old_or_science(env):
    binding, observed = s.fresh_binding()
    assert observed['accepted_core'] == 22 and observed['unaccepted_core'] == [env.core[-1]]
    plan = s.prepare(env.root)
    assert plan['binding'] == binding and (env.root / 'implementation/finqa_v62_supersession.py').is_file()
    assert not (env.old / 'terminal/record.json').exists() and not (env.source / 'STOP').exists()


def test_single_passive_retirement_preserves_science_and_old60_cron(env):
    s.prepare(env.root)
    runner = FakeCron()
    old60 = s.exact_line(60,env.guard)
    result = s.retire(env.root,runner=runner)
    assert result['status'] == 'V61_PASSIVE_GUARD_RETIRED'
    assert runner.writes == 1 and old60 in runner.raw and b'private_fixture' in runner.raw
    assert s.exact_line(61,env.old) not in runner.raw
    assert not (env.source / 'STOP').exists() and not (env.source / 'control/stop_requested/record.json').exists()
    assert result['observer_returncode'] is None and result['process_signals_sent'] is False
    assert s.checked_completed(env.root)['id'] == result['id']
    assert 'private_fixture' not in str(result)


def test_lease_excludes_old_all8_barrier_but_does_not_take_active_gpu(env):
    binding,_ = s.fresh_binding()
    active = env.science / 'locks/gpu2.lock'
    with active.open('r+') as worker:
        fcntl.flock(worker,fcntl.LOCK_EX|fcntl.LOCK_NB)
        with s.one_original_lease(binding) as lease:
            assert lease and lease['path'] != str(active)
            with Path(lease['path']).open('r+') as contender:
                with pytest.raises(BlockingIOError):
                    fcntl.flock(contender,fcntl.LOCK_EX|fcntl.LOCK_NB)
        with Path(lease['path']).open('r+') as released:
            fcntl.flock(released,fcntl.LOCK_EX|fcntl.LOCK_NB)


def test_all_busy_leases_do_not_fence_guard(env):
    s.prepare(env.root)
    streams=[]
    try:
        for path in sorted((env.science/'locks').iterdir()):
            stream=path.open('r+')
            fcntl.flock(stream,fcntl.LOCK_EX|fcntl.LOCK_NB)
            streams.append(stream)
        assert s.retire(env.root,runner=FakeCron())['status'] == 'WAITING_FOR_ONE_ORIGINAL_PROJECT_LEASE'
        assert not (env.old/'terminal/record.json').exists()
        assert not (env.root/'intent/record.json').exists()
    finally:
        for stream in streams:
            stream.close()


@pytest.mark.parametrize('relative',['handoff/transaction/record.json','handoff/completed/record.json','state.json','STOP'])
def test_existing_old_handoff_or_user_stop_blocks_before_mutation(env,relative):
    path=env.old/relative
    path.parent.mkdir(parents=True,exist_ok=True)
    path.touch()
    with pytest.raises(RuntimeError):
        s.fresh_binding()
    assert not (env.old/'terminal/record.json').exists()


def test_completed_training_never_forced_into_retirement(env):
    path=env.source/'journal/state.json'
    path.unlink()
    s.publish(path,dict(env.journal,accepted={key:{} for key in env.core}))
    with pytest.raises(RuntimeError,match='CORE_ALREADY_COMPLETE'):
        s.fresh_binding()


def test_ambiguous_crontab_write_permanently_blocks_retry(env):
    s.prepare(env.root)
    runner=FakeCron(fail_write=True)
    with pytest.raises(OSError):
        s.retire(env.root,runner=runner)
    assert (env.root/'blocked/record.json').is_file()
    with pytest.raises(RuntimeError,match='ONCE_ONLY'):
        s.retire(env.root,runner=runner)
    assert runner.writes == 1 and not (env.source/'STOP').exists()


def test_completed_receipt_survives_later_legal_old04_and_old60_stop(env,monkeypatch):
    s.prepare(env.root)
    result=s.retire(env.root,runner=FakeCron())
    s.publish(env.guard/'terminal/record.json',dict(status='SUPERSEDED_BY_V62_PASSIVE_HANDOFF'))
    s.publish(env.source/'control/stop_requested/record.json',dict(status='authorized_later_maintenance'))
    monkeypatch.setattr(s,'identity',lambda pid,birth:dict(pid=pid,birth=birth,alive=False))
    assert s.checked_completed(env.root)['id'] == result['id']


def test_replaced_original_lock_rejected(env):
    binding,_=s.fresh_binding()
    path=env.science/'locks/gpu0.lock'
    path.rename(path.with_suffix('.old'))
    path.touch()
    with pytest.raises(RuntimeError,match='LEASE_IDENTITY_CHANGED'):
        with s.one_original_lease(binding):
            pass


def test_deadline_has_no_automatic_extension():
    with pytest.raises(RuntimeError,match='SIXTY_SECOND'):
        s.remaining(time.monotonic()-0.01)
