"""One authorized retirement of the unactivated V61 CPU guard, without signals.

The user cancelled the yyy-account exclusion. Before the replacement policy can
be registered, the still-passive old guard must cease trying to activate it.
No scientific STOP, process signal, GPU allocation or worker action is used.
"""
from __future__ import annotations
import argparse
import contextlib
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shlex
import stat
import subprocess
import tempfile
import time
from finqa_v62_binding import (SCIENCE_ROOT, SOURCE_CONTROL_ROOT,
    SOURCE_CONTROL_PROTOCOL_ID, SCIENTIFIC_PROTOCOL_ID, SUPERSEDED_MASTER_ROOT,
    SUPERSEDED_MASTER_PROTOCOL_ID, PREPARATION_ROOT, PARENT_WATCHDOG_ROOT,
    PARENT_WATCHDOG_PROTOCOL_ID, PYTHON)

COMPLETED_RECORD_PATH = PREPARATION_ROOT / 'completed/record.json'
OWNER_UID, OBSERVER_PID, OBSERVER_BIRTH = 1004, 698967, '480763593'
MAX_LEASE_SECONDS = 60
AUTHORIZATION = '取消避开yyy账户的限制；仅退休尚未接管的V61纯CPU守护'


def require(value, code):
    if not value:
        raise RuntimeError(code)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
        separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def checked(path):
    value = json.loads(Path(path).read_bytes())
    require(value['id'] == digest({k: v for k, v in value.items() if k != 'id'}), 'RECORD_CHANGED')
    return value


def ref(path):
    path = Path(path).resolve()
    return dict(path=str(path), sha256=hashlib.sha256(path.read_bytes()).hexdigest(), id=checked(path)['id'])


def read_ref(value):
    path = Path(value['path'])
    result = checked(path)
    require(hashlib.sha256(path.read_bytes()).hexdigest() == value['sha256']
        and result['id'] == value['id'], 'IMMUTABLE_REFERENCE_CHANGED')
    return result


def publish(path, body):
    path = Path(path)
    require(not path.exists() and not path.is_symlink(), 'RETIREMENT_EVIDENCE_EXISTS_NO_OVERWRITE')
    body = {k: v for k, v in body.items() if k != 'id'}
    value = {**body, 'id': digest(body)}
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix='.retire-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w') as stream:
            json.dump(value, stream, sort_keys=True, ensure_ascii=False, allow_nan=False)
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temporary, path)
        descriptor = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
    finally:
        Path(temporary).unlink(missing_ok=True)
    return value


def own_root(root=PREPARATION_ROOT):
    root = Path(root)
    require(root == root.resolve() == PREPARATION_ROOT and not root.is_symlink()
        and os.getuid() == os.geteuid() == OWNER_UID, 'UNREGISTERED_RETIREMENT_ROOT_OR_UID')
    return root


def identity(pid, birth):
    try:
        fields = Path(f'/proc/{pid}/stat').read_text().rsplit(')', 1)[1].split()
    except (FileNotFoundError, ProcessLookupError):
        return dict(pid=pid, birth=birth, alive=False)
    return dict(pid=pid, birth=birth, alive=fields[19] == birth,
        observed_birth=fields[19], proc_state=fields[0])


def owner_uid(pid):
    row = next(line for line in Path(f'/proc/{pid}/status').read_text().splitlines() if line.startswith('Uid:'))
    return tuple(map(int, row.split()[1:]))


def inode(path):
    path = Path(path)
    require(path == path.resolve(), 'ORIGINAL_LOCK_REDIRECTED')
    value = path.lstat()
    require(stat.S_ISREG(value.st_mode), 'ORIGINAL_LOCK_NOT_REGULAR')
    return dict(path=str(path), device=value.st_dev, inode=value.st_ino)


def exact_line(version, root):
    command = [str(PYTHON), '-u', str(root / f'implementation/finqa_v{version}_cron.py'),
               'tick', '--root', str(root)]
    return ('* * * * * '+' '.join(shlex.quote(v) for v in command)
        + f' # FINQA_V{version}_ACCOUNT_WATCHDOG_01_UID1004').encode()


def read_cron(runner=None, *, timeout=10):
    value = (runner or subprocess.run)(['crontab', '-l'], stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, check=False, timeout=timeout)
    require(value.returncode == 0, 'CRONTAB_READ_FAILED')
    return value.stdout


def without_v61(raw):
    target, kept, count = exact_line(61, SUPERSEDED_MASTER_ROOT), [], 0
    for line in raw.splitlines(keepends=True):
        content = line.rstrip(b'\r\n')
        if content == target:
            count += 1
        else:
            require(b'# FINQA_V61_ACCOUNT_WATCHDOG_01_UID1004' not in content, 'V61_CRON_MARKER_CONFLICT')
            kept.append(line)
    require(count == 1, 'EXACTLY_ONE_OLD_V61_CRON_LINE_REQUIRED')
    require(sum(line.rstrip(b'\r\n') == exact_line(60, PARENT_WATCHDOG_ROOT)
        for line in raw.splitlines(keepends=True)) == 1, 'V60_SCIENTIFIC_GUARD_NOT_IN_PLACE')
    return b''.join(kept)


def policy():
    return dict(schema='v62_retire_unactivated_v61_guard.v1', owner_uid=OWNER_UID,
        source_episode=str(SOURCE_CONTROL_ROOT), source_protocol_id=SOURCE_CONTROL_PROTOCOL_ID,
        retired_guard_root=str(SUPERSEDED_MASTER_ROOT), retired_guard_protocol_id=SUPERSEDED_MASTER_PROTOCOL_ID,
        bound_guard_pid=OBSERVER_PID, bound_guard_birth=OBSERVER_BIRTH,
        old_core_must_still_be_incomplete_before_fence=True,
        original_idle_project_leases_retained=1, maximum_lease_seconds=MAX_LEASE_SECONDS,
        no_GPU_capacity_query_or_allocation=True, no_worker_draining=True,
        process_signals_sent=False, source_or_guard_STOP_written=False,
        old_guard_terminal='SUPERSEDED_BEFORE_HANDOFF', old_guard_exits_naturally=True,
        old_protocol_and_implementation_unchanged=True, old_V60_and_other_cron_lines_preserved=True,
        unknown_write_result_blocks_without_repeating_actions=True)


def no_handoff_or_stop(*, terminal_allowed=False):
    old = SUPERSEDED_MASTER_ROOT
    for root in (old, SOURCE_CONTROL_ROOT, PARENT_WATCHDOG_ROOT):
        require(not (root / 'STOP').exists() and not (root / 'control/stop_requested/record.json').exists(),
            'EXPLICIT_USER_STOP_PREVENTS_RETIREMENT')
    for relative in ('handoff/transaction/record.json', 'handoff/completed/record.json', 'state.json'):
        require(not (old / relative).exists(), 'V61_ALREADY_ENTERED_HANDOFF_OR_SUCCESSOR')
    for relative in ('episodes', 'requests'):
        directory = old / relative
        require(not directory.exists() or not any(directory.iterdir()), 'V61_SUCCESSOR_TRANSACTION_EXISTS')
    require(terminal_allowed or not (old / 'terminal/record.json').exists(), 'V61_ALREADY_TERMINAL')
    require(not (PARENT_WATCHDOG_ROOT / 'terminal/record.json').exists(), 'V60_ALREADY_TERMINAL')


def fresh_binding(binding=None):
    no_handoff_or_stop()
    old = checked(SUPERSEDED_MASTER_ROOT / 'protocol/record.json')
    parent = checked(PARENT_WATCHDOG_ROOT / 'protocol/record.json')
    source = checked(SOURCE_CONTROL_ROOT / 'protocol/record.json')
    require(old['id'] == SUPERSEDED_MASTER_PROTOCOL_ID and parent['id'] == PARENT_WATCHDOG_PROTOCOL_ID
        and source['id'] == SOURCE_CONTROL_PROTOCOL_ID
        and source['scientific_protocol_id'] == SCIENTIFIC_PROTOCOL_ID, 'REGISTERED_PROTOCOL_CHANGED')
    state_path = PARENT_WATCHDOG_ROOT / 'state.json'
    if state_path.exists():
        state = checked(state_path)
        require(state['current_episode'] == dict(root=str(SOURCE_CONTROL_ROOT), protocol_id=SOURCE_CONTROL_PROTOCOL_ID)
            and state.get('pending_request') is None and state['phase'] == 'WATCHING', 'V60_EPISODE_ADVANCED')
    status = json.loads((SUPERSEDED_MASTER_ROOT / 'cron/status.json').read_bytes())
    invocation = status['invocation']
    require(status['status'] == 'PASSIVE_HANDOFF_RUNNING'
        and status['handoff_status'] == 'WAITING_FOR_ACCEPTED_TRAINING_CORE'
        and (invocation['pid'], invocation['birth']) == (OBSERVER_PID, OBSERVER_BIRTH), 'BOUND_V61_OBSERVER_CHANGED')
    observed = identity(OBSERVER_PID, OBSERVER_BIRTH)
    require(observed['alive'] and observed.get('proc_state') not in ('Z', 'X', 'x')
        and owner_uid(OBSERVER_PID) == (OWNER_UID,) * 4, 'BOUND_V61_OBSERVER_NOT_LIVE_OWNER')
    journal = checked(SOURCE_CONTROL_ROOT / 'journal/state.json')
    require(journal['protocol_id'] == SCIENTIFIC_PROTOCOL_ID
        and journal['control_protocol_id'] == SOURCE_CONTROL_PROTOCOL_ID
        and journal['controller_attempt'] == 1 and 0 <= time.time()-journal['updated_epoch'] <= 20,
        'SOURCE04_JOURNAL_NOT_FRESH_OR_CHANGED')
    core = old['handoff_binding']['core_job_ids']
    require(len(core) == 23 and set(core)-set(journal['accepted']), 'SOURCE_CORE_ALREADY_COMPLETE_DO_NOT_FORCE')
    require(not any(row['status'] in ('HARD_BLOCKED', 'DEPENDENCY_BLOCKED', 'UNKNOWN')
        for row in journal['job_states'].values()), 'SOURCE_SCIENTIFIC_FAILURE')
    for row in old['handoff_binding']['controls'].values():
        current = identity(row['pid'], row['birth'])
        require(current['alive'] and current.get('proc_state') not in ('Z', 'X', 'x'), 'SOURCE_CONTROL_IDENTITY_CHANGED')
    result = dict(schema='v62_fixed_passive_retirement_binding.v1',
        old_guard_protocol=ref(SUPERSEDED_MASTER_ROOT / 'protocol/record.json'),
        old_guard_implementation=ref(SUPERSEDED_MASTER_ROOT / 'implementation/record.json'),
        old_V60_protocol=ref(PARENT_WATCHDOG_ROOT / 'protocol/record.json'),
        source_protocol=ref(SOURCE_CONTROL_ROOT / 'protocol/record.json'),
        observer=dict(pid=OBSERVER_PID, birth=OBSERVER_BIRTH, uid=OWNER_UID),
        original_lock_bindings=old['original_lock_bindings'],
        old_cron_change_lock=inode(SUPERSEDED_MASTER_ROOT / 'cron/crontab_change.lock'),
        old_handoff_binding_id=old['handoff_binding']['id'], core_job_ids=core)
    if binding is not None:
        require(result == binding, 'PASSIVE_RETIREMENT_BINDING_CHANGED')
    return result, dict(journal_id=journal['id'], accepted_core=len(set(core)&set(journal['accepted'])),
        unaccepted_core=sorted(set(core)-set(journal['accepted'])), active_jobs=journal['active_jobs'], observed_epoch=time.time())


def prepare(root=PREPARATION_ROOT):
    root = own_root(root)
    require(not (root / 'plan/record.json').exists() and not (root / 'intent/record.json').exists(), 'NEW_RETIREMENT_PLAN_REQUIRED')
    binding, observation = fresh_binding()
    raw = Path(__file__).read_bytes()
    directory = root / 'implementation'
    directory.mkdir(parents=True, exist_ok=False)
    with (directory / 'finqa_v62_supersession.py').open('xb') as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    return publish(root / 'plan/record.json', dict(schema='v62_registered_passive_guard_retirement.v1',
        authorization=AUTHORIZATION, policy=policy(), binding=binding,
        script_sha256=hashlib.sha256(raw).hexdigest(), observation=observation,
        created_epoch=time.time(), process_signals_sent=False, scientific_data_modified=False))


@contextlib.contextmanager
def one_original_lease(binding):
    candidates = [(Path(path), row) for path, row in sorted(binding['original_lock_bindings'].items())
        if Path(path) != SCIENCE_ROOT / 'owner.lock']
    require(len(candidates) == 8, 'ORIGINAL_EIGHT_GPU_LEASE_BINDINGS_REQUIRED')
    held, observed = None, None
    try:
        for path, expected in candidates:
            stream = path.open('r+')
            try:
                require(inode(path) == dict(path=str(path), **expected)
                    and (os.fstat(stream.fileno()).st_dev, os.fstat(stream.fileno()).st_ino)
                        == (expected['device'], expected['inode']), 'ORIGINAL_LEASE_IDENTITY_CHANGED')
                fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                stream.close()
                continue
            except BaseException:
                stream.close()
                raise
            held, observed = stream, dict(path=str(path), **expected)
            break
        yield observed
    finally:
        if held is not None:
            held.close()


def remaining(deadline):
    value = deadline-time.monotonic()
    require(value > 0, 'SIXTY_SECOND_RETIREMENT_WINDOW_EXHAUSTED')
    return min(value, 10)


def retire(root=PREPARATION_ROOT, *, runner=None):
    root = own_root(root)
    plan = checked(root / 'plan/record.json')
    require(plan['policy'] == policy() and plan['authorization'] == AUTHORIZATION
        and hashlib.sha256(Path(__file__).read_bytes()).hexdigest() == plan['script_sha256'], 'RETIREMENT_PLAN_OR_IMPLEMENTATION_CHANGED')
    require(not (root / 'intent/record.json').exists() and not (root / 'completed/record.json').exists(),
        'RETIREMENT_IS_ONCE_ONLY_NO_AUTOMATIC_RETRY')
    fresh_binding(plan['binding'])
    with one_original_lease(plan['binding']) as lease:
        if lease is None:
            return dict(status='WAITING_FOR_ONE_ORIGINAL_PROJECT_LEASE', process_signals_sent=False)
        started, deadline = time.monotonic(), time.monotonic()+MAX_LEASE_SECONDS
        try:
            _, observation = fresh_binding(plan['binding'])
            before = read_cron(runner, timeout=remaining(deadline))
            after = without_v61(before)
            change = plan['binding']['old_cron_change_lock']
            with Path(change['path']).open('r+') as lock:
                require(inode(change['path']) == change, 'CRON_CHANGE_LOCK_REPLACED')
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                require(read_cron(runner, timeout=remaining(deadline)) == before, 'CRONTAB_CHANGED_BEFORE_RETIREMENT')
                _, observation = fresh_binding(plan['binding'])
                remaining(deadline)
                intent = publish(root / 'intent/record.json', dict(schema='v62_passive_guard_retirement_intent.v1',
                    plan_id=plan['id'], created_epoch=time.time(), original_lease=lease,
                    maximum_lease_seconds=MAX_LEASE_SECONDS, fresh_observation=observation,
                    old_observer=plan['binding']['observer'], before_crontab_sha256=hashlib.sha256(before).hexdigest(),
                    target_crontab_sha256=hashlib.sha256(after).hexdigest(), process_signals_sent=False, scientific_STOP_written=False))
                remaining(deadline)
                terminal = publish(SUPERSEDED_MASTER_ROOT / 'terminal/record.json', dict(
                    schema='v62_superseded_unactivated_v61_guard.v1', protocol_id=SUPERSEDED_MASTER_PROTOCOL_ID,
                    status='SUPERSEDED_BEFORE_HANDOFF', reason='AUTHORIZED_V62_SHARED_GPU_ADMISSION',
                    intent_id=intent['id'], preparation_root=str(root), at_epoch=time.time(),
                    automatic_recovery_allowed=False, scientific_STOP_written=False, process_signals_sent=False))
                require(read_cron(runner, timeout=remaining(deadline)) == before, 'CRONTAB_CHANGED_AFTER_SAFE_FENCE')
                publish(root / 'cron_removal/intent/record.json', dict(schema='v62_exact_v61_cron_removal_intent.v1',
                    retirement_intent_id=intent['id'], target_sha256=hashlib.sha256(after).hexdigest(),
                    old_V60_line_preserved=True, unrelated_content_not_logged=True, at_epoch=time.time()))
                result = (runner or subprocess.run)(['crontab', '-'], input=after,
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False, timeout=remaining(deadline))
                require(result.returncode == 0, 'CRONTAB_WRITE_OUTCOME_UNKNOWN_NO_RETRY')
                observed = read_cron(runner, timeout=remaining(deadline))
                require(observed == after, 'CRONTAB_POST_WRITE_MISMATCH_NO_ROLLBACK')
                publish(root / 'cron_removal/result/record.json', dict(schema='v62_exact_v61_cron_removed.v1',
                    retirement_intent_id=intent['id'], observed_sha256=hashlib.sha256(observed).hexdigest(),
                    old_V61_line_removed=True, old_V60_and_unrelated_lines_preserved=True,
                    at_epoch=time.time(), other_crontab_content_recorded=False))
            while identity(OBSERVER_PID, OBSERVER_BIRTH)['alive']:
                no_handoff_or_stop(terminal_allowed=True)
                time.sleep(min(0.25, remaining(deadline)))
            no_handoff_or_stop(terminal_allowed=True)
            require(checked(SUPERSEDED_MASTER_ROOT / 'terminal/record.json') == terminal, 'RETIREMENT_TERMINAL_CHANGED')
            remaining(deadline)
            return publish(root / 'completed/record.json', dict(schema='v62_passive_guard_retirement_completed.v1',
                status='V61_PASSIVE_GUARD_RETIRED', plan=ref(root / 'plan/record.json'), intent=ref(root / 'intent/record.json'),
                old_guard_terminal=ref(SUPERSEDED_MASTER_ROOT / 'terminal/record.json'),
                crontab_removal=ref(root / 'cron_removal/result/record.json'), observer=plan['binding']['observer'],
                observer_identity_gone=True, observer_actual_waitpid_observed=False, observer_returncode=None,
                held_original_lease=lease, lease_elapsed_seconds=time.monotonic()-started,
                lease_released_on_function_return=True, maximum_lease_seconds=MAX_LEASE_SECONDS,
                old_guard_handoff_or_successor_started=False, source_scientific_STOP_written=False,
                process_signals_sent=False, source_04_training_not_paused=True, historical_protocols_unchanged=True,
                finished_epoch=time.time()))
        except BaseException as error:
            if (root / 'intent/record.json').exists() and not (root / 'blocked/record.json').exists():
                publish(root / 'blocked/record.json', dict(schema='v62_retirement_stopped_no_retry.v1',
                    status='BLOCKED_NO_RETRY', error_type=type(error).__name__, external_write_result_may_be_unknown=True,
                    automatic_retry=False, process_signals_sent=False, at_epoch=time.time()))
            raise


def checked_completed(root=PREPARATION_ROOT):
    """Enduring read-only proof; never re-run old61's dynamic protocol checks."""
    root = own_root(root)
    require(not (root / 'blocked/record.json').exists(), 'RETIREMENT_HAS_UNRESOLVED_FAILURE')
    value = checked(root / 'completed/record.json')
    plan, intent = read_ref(value['plan']), read_ref(value['intent'])
    terminal, removal = read_ref(value['old_guard_terminal']), read_ref(value['crontab_removal'])
    require(value['schema'] == 'v62_passive_guard_retirement_completed.v1'
        and value['status'] == 'V61_PASSIVE_GUARD_RETIRED' and plan['policy'] == policy()
        and intent['plan_id'] == plan['id'] and terminal['intent_id'] == intent['id']
        and removal['retirement_intent_id'] == intent['id']
        and terminal['status'] == 'SUPERSEDED_BEFORE_HANDOFF' and terminal['protocol_id'] == SUPERSEDED_MASTER_PROTOCOL_ID
        and value['observer'] == dict(pid=OBSERVER_PID, birth=OBSERVER_BIRTH, uid=OWNER_UID)
        and value['process_signals_sent'] is False and value['source_scientific_STOP_written'] is False
        and value['lease_elapsed_seconds'] < MAX_LEASE_SECONDS
        and value['observer_actual_waitpid_observed'] is False and value['observer_returncode'] is None,
        'PASSIVE_RETIREMENT_RECEIPT_CHANGED')
    require(not identity(OBSERVER_PID, OBSERVER_BIRTH)['alive'], 'RETIRED_V61_OBSERVER_STILL_PRESENT')
    for relative in ('handoff/transaction/record.json', 'handoff/completed/record.json', 'state.json'):
        require(not (SUPERSEDED_MASTER_ROOT / relative).exists(), 'RETIRED_GUARD_STARTED_HANDOFF')
    for key in ('old_guard_protocol', 'old_guard_implementation', 'old_V60_protocol', 'source_protocol'):
        read_ref(plan['binding'][key])
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('inspect', 'prepare', 'retire', 'check-completed'))
    args = parser.parse_args()
    if args.action == 'inspect':
        binding, observation = fresh_binding()
        result = dict(status='PASSIVE_RETIREMENT_ADMISSIBLE', binding=binding, observation=observation)
    else:
        result = {'prepare': prepare, 'retire': retire, 'check-completed': checked_completed}[args.action]()
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == '__main__':
    main()
