"""One authorized complete-response maintenance handoff; no scientific retry."""
from __future__ import annotations

import fcntl
import importlib
import json
import os
from pathlib import Path
import signal
import subprocess
import time

import finqa_v64_binding as b


def identity(pid):
    try:
        fields = Path('/proc/%s/stat' % pid).read_text().rsplit(')', 1)[1].split()
    except (FileNotFoundError, ProcessLookupError):
        return None
    return fields[19] if fields[0] not in ('Z', 'X', 'x') else None


def alive(record):
    return identity(record['pid']) == record['birth']


def signal_once(target, supervisor):
    descriptor = None
    try:
        if hasattr(os, 'pidfd_open') and hasattr(signal, 'pidfd_send_signal'):
            descriptor = os.pidfd_open(target['pid'])
        b.require(alive(target) and alive(supervisor), 'control identity changed before signal')
        if descriptor is None:
            os.kill(target['pid'], signal.SIGTERM)
        else:
            signal.pidfd_send_signal(descriptor, signal.SIGTERM)
    finally:
        if descriptor is not None:
            os.close(descriptor)


def stop_receipts(path):
    """Read this experiment's kernel receipts, never another process's files."""
    path = Path(path).resolve()
    b.require(path.is_relative_to(b.SCIENTIFIC_ROOT), 'foreign signal evidence')
    if not path.exists():
        return []
    rows = [json.loads(line) for line in path.read_text().splitlines() if line]
    return [row for row in rows if row.get('decision', {}).get('dispatch_original_stop')]


def check_receipts(rows, *, target, allowed_senders, after_epoch, required_sender=None):
    for row in rows:
        b.require(row.get('schema') == 'v59_received_signal_kernel_receipt.v1'
                  and row.get('provenance') == 'kernel_sigwaitinfo'
                  and row.get('receipt_queue_drops_before') == 0
                  and row.get('pid') == target and row.get('signal') == signal.SIGTERM
                  and row.get('si_uid') == b.OWNER_UID and row.get('si_code') == 0
                  and row.get('si_pid') in allowed_senders and row['at_epoch'] >= after_epoch,
                  'unrelated or ambiguous legal stop is not maintenance authorization')
    b.require(len(rows) == len({row['si_pid'] for row in rows}),
              'repeated unexplained stop receipt blocks automatic handoff')
    if required_sender is not None:
        b.require(any(row['si_pid'] == required_sender for row in rows),
                  'actual kernel maintenance signal receipt is missing')


def checked_before(value, protocol):
    b.require(value['protocol_id'] == b.BASE_PROTOCOL_ID
              and 0 <= time.time() - value['updated_epoch'] < 30,
              'old journal must be fresh and scientifically bound')
    b.require(value['evaluation_registered'] is False,
              'this handoff is limited to the registered pre-training R3 boundary')
    feedback = {f'seed{seed}.feedback_{arm}' for seed in (137, 251, 389) for arm in ('C1', 'C05')}
    b.require(feedback <= set(value['accepted']), 'all 4200 complete feedbacks must already be accepted')
    b.require(not any(row['status'] in ('HARD_BLOCKED', 'DEPENDENCY_BLOCKED', 'DISPATCHING', 'SETTLING_EXIT')
                      for row in value['job_states'].values()), 'unsettled or blocked old state cannot be handed off')
    for active in value['active_jobs']:
        key = active['job_id']
        b.require('.replay_' in key and value['job_states'][key]['status'] in ('RUNNING', 'DRAINING')
                  and alive(active), 'only exact live registered replay workers may be paused')
    b.require(len(value['active_jobs']) <= protocol['max_gpu_workers'], 'old worker count changed')
    return value


def acquire_gpu_leases(protocol, occupied, leases):
    """Lock every currently free project slot; never touch a foreign process."""
    for gpu in range(8):
        if gpu in leases:
            continue
        path = Path(protocol['gpu_lease_root']) / ('gpu-' + b.digest(protocol['gpu_uuids'][str(gpu)]) + '.lock')
        b.require(path.is_file() and not path.is_symlink(), 'registered project lease is missing or aliased')
        stream = path.open('r+')
        try:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            stream.close()
            b.require(gpu in occupied, 'an unexplained project lease prevents maintenance')
            continue
        b.require(os.fstat(stream.fileno()).st_ino == path.stat().st_ino, 'project lease inode changed')
        leases[gpu] = stream


def _attempt_row(before, active):
    rows = [row for row in before['attempt_history'] if
            (row['job_id'], row['attempt']) == (active['job_id'], active['attempt'])]
    b.require(len(rows) == 1, 'exact old attempt history entry required')
    return rows[0]


def checked_maintenance_resources(failure, active, job_id):
    closed = b.read_ref(failure['resource_closeout'])
    report = failure['resources']
    gib = 1024 ** 3
    b.require(failure['CUDA_initialized'] is True
              and closed['protocol_id'] == b.BASE_PROTOCOL_ID and closed['job_id'] == job_id
              and (closed['pid'], closed['birth']) == (active['pid'], active['birth'])
              and closed['resources'] == report and closed['status'] == 'FAILED_OR_STOPPED'
              and closed['error']['type'] == failure['exception_type'],
              'maintenance must bind the actual stopped CUDA process resource closeout')
    b.require(report['all_gates_passed'] is True and report['observed_violation'] is None
              and report['single_process_lifetime_includes_loading'] is True
              and report['peak_resets_after_loading'] == 0 and report['peak_resets_before_loading'] == 1
              and report['actual_boundary_observations'] > 0
              and report['peak_allocated_bytes'] <= 76 * gib
              and report['minimum_boundary_free_bytes'] >= 2 * gib
              and report['peak_rss_bytes'] <= 192 * gib
              and report['minimum_host_available_bytes'] >= 96 * gib,
              'a concurrent resource failure cannot be reclassified as maintenance')
    return closed


def stop_failed_start(protocol, process, process_birth):
    """Make a failed new launch terminal before releasing the GPU barrier."""
    marker = b.ROOT / 'control/stop_requested/record.json'
    if not marker.exists():
        b.publish(marker, dict(schema='v64_terminal_explicit_stop.v1',
            protocol_id=b.BASE_PROTOCOL_ID, control_protocol_id=protocol['id'],
            reason='authorized handoff new-controller startup failed', at_epoch=time.time(),
            automatic_restart_allowed=False))
    target = dict(pid=process.pid, birth=process_birth)
    if process_birth is not None and alive(target):
        os.kill(process.pid, signal.SIGTERM)
    deadline = time.monotonic() + 660
    while process.poll() is None and time.monotonic() < deadline:
        time.sleep(2)
    controller_path = b.ROOT / 'controllers/attempt0001/launch/record.json'
    controller = b.checked(controller_path) if controller_path.exists() else None
    confirmed = process.poll() is not None and (controller is None or not alive(controller))
    b.publish(b.ROOT / 'handoff/failed_start_stop/record.json', dict(
        schema='v64_failed_start_stop_before_GPU_barrier_release.v1',
        terminal_marker=b.entry(marker), supervisor_pid=process.pid, supervisor_birth=process_birth,
        supervisor_actual_returncode=process.poll(), controller=controller,
        all_new_control_identities_exited=confirmed,
        no_new_worker_could_acquire_project_GPU_lease=True,
        no_automatic_relaunch=True, finished_epoch=time.time()))
    return confirmed


def prepare_inheritance(protocol, before, intent, old_controller, old_supervisor):
    import finqa_v64_controller as control
    import finqa_v64_registration as registration
    import finqa_v64_worker as worker
    runtime = importlib.import_module('finqa_v64_runtime').controller_runtime()
    final = b.checked(b.SCIENTIFIC_ROOT / 'journal/state.json')
    b.require(final['active_jobs'] == [] and final['attempt_history'] == before['attempt_history'],
              'new dispatch or unsettled worker appeared during maintenance')
    controller_dir = Path(protocol['baseline']['original_controller']['path']).parent.parent
    receipts = stop_receipts(controller_dir / 'signals/received.jsonl')
    check_receipts(receipts, target=old_controller['pid'],
        allowed_senders={intent['pid'], old_supervisor['pid']}, after_epoch=intent['at_epoch'],
        required_sender=intent['pid'])
    b.require(stop_receipts(b.SCIENTIFIC_ROOT / 'supervisor/signals/received.jsonl') == [],
              'an independent legal supervisor stop cannot be overridden')
    b.require(not (b.SCIENTIFIC_ROOT / 'STOP').exists(),
              'an independent explicit STOP cannot be overridden by maintenance')
    closeout = b.checked(b.SCIENTIFIC_ROOT / 'closeout/record.json')
    supervisor_closeout = b.checked(b.SCIENTIFIC_ROOT / 'supervisor/closeout/record.json')
    b.require(closeout['status'] == supervisor_closeout['status'] == 'STOPPED_EXPLICIT_REQUEST_NO_AUTO_RESUME',
              'old stop did not close normally at the maintenance boundary')
    controller_exit_path = b.SCIENTIFIC_ROOT / 'supervisor/attempts' / (
        'attempt%04d' % protocol['baseline']['old_controller_attempt']) / 'actual_exit/record.json'
    actual = b.checked(controller_exit_path)
    b.require(actual['actual_waitpid_observed'] is True and actual['returncode'] == 2
              and (actual['pid'], actual['birth']) == (old_controller['pid'], old_controller['birth']),
              'the old controller actual exit must be observed by its original parent')
    resumes = {}
    for active in before['active_jobs']:
        row = _attempt_row(before, active)
        control.audit_attempt_exit(row, b.base_protocol(), runtime)
        directory = control.checked_attempt_directory(row)
        launch = b.checked(directory / 'launch/record.json')
        b.require((launch['pid'], launch['birth']) == (active['pid'], active['birth']), 'old worker identity differs')
        exits = b.checked(directory / 'actual_exit/record.json')
        signals = stop_receipts(directory / 'signals/received.jsonl')
        check_receipts(signals, target=active['pid'], allowed_senders={old_controller['pid']},
                       after_epoch=intent['at_epoch'])
        key = active['job_id']
        if key in final['accepted']:
            b.require(exits['returncode'] == 0, 'naturally accepted worker must actually exit zero')
            continue
        check_receipts(signals, target=active['pid'], allowed_senders={old_controller['pid']},
                       after_epoch=intent['at_epoch'], required_sender=old_controller['pid'])
        failure = b.checked(directory / 'failure/record.json')
        b.require(exits['returncode'] == 1 and failure['exception_type'] in ('ReplayPaused', 'ExplicitStop')
                  and failure['pid'] == active['pid'] and failure['protocol_id'] == b.BASE_PROTOCOL_ID
                  and failure['attempt_root'] == str(directory),
                  'only the actual complete-response maintenance exception may continue')
        checked_maintenance_resources(failure, active, key)
        audit = control.inherited.checked_audit(worker.audit_job_resume(b.SCIENTIFIC_ROOT, launch['job']))
        b.require(audit['resume_allowed'] and audit['unknown_calls'] == 0
                  and audit['progress_units'] >= before['job_states'][key]['progress_units'],
                  'missing, unknown, or regressed complete-response checkpoint')
        destination = b.ROOT / 'handoff/jobs' / key
        b.publish(destination / 'resume_audit/record.json', audit)
        b.publish(destination / 'acceptance/record.json', dict(schema='v64_complete_response_maintenance_acceptance.v1',
            status='PASS', authorization_id=protocol['maintenance_authorization']['id'],
            job_id=key, attempt=active['attempt'], pid=active['pid'], birth=active['birth'],
            worker_signaled=True, checkpoint_boundary='complete_response',
            error_type=failure['exception_type'], progress_units=audit['progress_units'],
            actual_returncode=exits['returncode'], original_failure=b.entry(directory / 'failure/record.json'),
            kernel_stop_receipts=signals, actual_checkpoint_byte_revalidation_required_in_cold_worker=True))
        resumes[key] = dict(attempt=active['attempt'], pid=active['pid'], birth=active['birth'],
            authorization_id=protocol['maintenance_authorization']['id'],
            launch=b.entry(directory / 'launch/record.json'), actual_exit=b.entry(directory / 'actual_exit/record.json'),
            resume_audit=b.entry(destination / 'resume_audit/record.json'),
            maintenance_acceptance=b.entry(destination / 'acceptance/record.json'))
    final_path = b.ROOT / 'handoff/inherited_journal/record.json'
    b.publish(final_path, final)
    body = dict(schema=registration.PREPARED_SCHEMA, control_protocol_id=protocol['id'],
        scientific_protocol_id=b.BASE_PROTOCOL_ID, authorization_id=protocol['maintenance_authorization']['id'],
        all_old_scientific_workers_actual_exits_observed=True,
        old_controller_and_supervisor_identities_gone=True, new_scientific_calls=0,
        pre_stop_journal=b.entry(b.ROOT / 'handoff/pre_stop_journal/record.json'),
        inherited_journal=b.entry(final_path), maintenance_resume_jobs=resumes,
        old_controller_actual_exit=b.entry(controller_exit_path),
        old_closeout=b.entry(b.SCIENTIFIC_ROOT / 'closeout/record.json'),
        old_supervisor_closeout=b.entry(b.SCIENTIFIC_ROOT / 'supervisor/closeout/record.json'),
        controller_kernel_stop_receipts=receipts, original_STOP_and_failures_unchanged=True,
        prepared_epoch=time.time())
    # Exercise the exact new inheritance validator before publishing permission
    # to launch. No model, CUDA or scientific worker is constructed here.
    original_prepared = b.source_module('finqa_v63_registration').checked_prepared(b.SCIENTIFIC_ROOT)
    jobs = control.base.core_jobs({seed: b.read_ref(ref) for seed, ref in original_prepared['parents'].items()})
    control.maintenance_states(final, before, body, protocol, jobs)
    return b.publish(b.ROOT / 'prepared/record.json', body)


def execute():
    b.require(Path(__file__).resolve().parent == b.ROOT / 'implementation', 'run only the frozen handoff once')
    b.require(os.getuid() == os.geteuid() == b.OWNER_UID, 'only registered project owner may hand off')
    import finqa_v64_registration as registration
    registration.modules()
    protocol = registration.checked_protocol()
    registration.checked_implementation()
    preflight = b.checked(b.ROOT / 'frozen_worker_import_verification/record.json')
    b.require(preflight['status'] == 'PASS' and preflight['control_protocol_id'] == protocol['id']
              and preflight['CUDA_initialized'] is False, 'frozen real CPU dependency preflight required')
    directory = b.ROOT / 'handoff'
    directory.mkdir(exist_ok=True)
    leases = {}
    process, process_birth = None, None
    with (directory / 'owner.lock').open('a') as owner:
        fcntl.flock(owner, fcntl.LOCK_EX | fcntl.LOCK_NB)
        b.require(not (directory / 'intent/record.json').exists()
                  and not (directory / 'failure/record.json').exists(), 'maintenance handoff is single-use')
        try:
            old_controller = b.read_ref(protocol['baseline']['original_controller'])
            old_supervisor = b.read_ref(protocol['baseline']['original_supervisor'])
            b.require(alive(old_controller) and alive(old_supervisor), 'registered old control identities changed')
            b.require(not (b.SCIENTIFIC_ROOT / 'STOP').exists()
                      and not (b.SCIENTIFIC_ROOT / 'control/stop_requested/record.json').exists()
                      and not (b.SCIENTIFIC_ROOT / 'closeout/record.json').exists(), 'old stop must not be overridden')
            first = checked_before(b.checked(b.SCIENTIFIC_ROOT / 'journal/state.json'), protocol)
            acquire_gpu_leases(protocol, {row['gpu_index'] for row in first['active_jobs']}, leases)
            before = checked_before(b.checked(b.SCIENTIFIC_ROOT / 'journal/state.json'), protocol)
            b.require(before['active_jobs'] == first['active_jobs']
                      and before['attempt_history'] == first['attempt_history'], 'dispatch raced with maintenance barrier')
            b.publish(directory / 'pre_stop_journal/record.json', before)
            intent = b.publish(directory / 'intent/record.json', dict(schema='v64_single_maintenance_signal_intent.v1',
                pid=os.getpid(), birth=identity(os.getpid()), uid=os.getuid(), at_epoch=time.time(),
                authorization_id=protocol['maintenance_authorization']['id'],
                target_pid=old_controller['pid'], target_birth=old_controller['birth'], signal=signal.SIGTERM,
                barrier_gpu_indices=sorted(leases), original_active_workers=before['active_jobs']))
            signal_once(old_controller, old_supervisor)
            b.publish(directory / 'signal_sent/record.json', dict(intent=b.entry(directory / 'intent/record.json'),
                at_epoch=time.time(), sent_once=True, target='registered old controller only'))
            deadline = time.monotonic() + 660
            while alive(old_controller) or alive(old_supervisor):
                b.require(time.monotonic() < deadline, 'old control identities did not exit within original drain grace')
                time.sleep(2)
            acquire_gpu_leases(protocol, set(), leases)
            b.require(len(leases) == 8, 'all project GPU leases must be available after actual exit')
            # Original owner lock is checked without retaining it into the new
            # controller, which must itself acquire that same exclusion lock.
            with (b.SCIENTIFIC_ROOT / 'owner.lock').open('r+') as science_owner:
                fcntl.flock(science_owner, fcntl.LOCK_EX | fcntl.LOCK_NB)
                prepared = prepare_inheritance(protocol, before, intent, old_controller, old_supervisor)
            import finqa_v64_controller as control
            command = [str(b.PYTHON), '-u', str(b.ROOT / 'implementation/finqa_v64_entry.py'),
                       '--mode', 'supervise', '--root', str(b.ROOT)]
            environment = dict(os.environ, PYTHONPATH=control.execution_pythonpath(),
                               V64_CONTROL_ROOT=str(b.ROOT), V64_CONTROL_PROTOCOL_ID=protocol['id'])
            with (directory / 'new_supervisor.log').open('xb') as log:
                process = subprocess.Popen(command, cwd=b.REPO, env=environment, stdout=log,
                    stderr=subprocess.STDOUT, start_new_session=True)
            process_birth = identity(process.pid)
            b.require(process_birth is not None, 'new supervisor exited before identity registration')
            b.publish(directory / 'new_supervisor_launch/record.json', dict(command=command,
                pid=process.pid, birth=process_birth, prepared_id=prepared['id'], at_epoch=time.time()))
            deadline = time.monotonic() + 120
            path = b.ROOT / 'controllers/attempt0001/launch/record.json'
            while not path.exists():
                b.require(process.poll() is None, 'new supervisor exited before controller admission')
                b.require(time.monotonic() < deadline, 'new controller startup remains unconfirmed; no duplicate launch')
                time.sleep(2)
            launch = b.checked(path)
            b.require(alive(launch) and launch['control_protocol_id'] == protocol['id'], 'new controller identity invalid')
            return b.publish(directory / 'complete/record.json', dict(schema='v64_single_handoff_complete.v1',
                status='COMPLETE', prepared=b.entry(b.ROOT / 'prepared/record.json'),
                new_supervisor=b.entry(b.ROOT / 'supervisor/launch/record.json'),
                new_controller=b.entry(path), old_identities_exited=True,
                new_scientific_calls_before_barrier_release=0, protection_actual_warm_not_yet_asserted=True,
                finished_epoch=time.time()))
        except BaseException as error:
            new_stopped = stop_failed_start(protocol, process, process_birth) if process is not None else True
            b.publish(directory / 'failure/record.json', dict(schema='v64_handoff_stopped_no_automatic_retry.v1',
                status='STOPPED_NO_AUTOMATIC_RETRY' if new_stopped else 'STOP_REQUESTED_EXIT_UNCONFIRMED',
                error_type=type(error).__name__, error=str(error),
                failed_epoch=time.time(), old_records_unchanged=True))
            raise
        finally:
            for stream in leases.values():
                stream.close()


if __name__ == '__main__':
    value = execute()
    print(json.dumps(dict(id=value['id'], status=value['status']), sort_keys=True))
