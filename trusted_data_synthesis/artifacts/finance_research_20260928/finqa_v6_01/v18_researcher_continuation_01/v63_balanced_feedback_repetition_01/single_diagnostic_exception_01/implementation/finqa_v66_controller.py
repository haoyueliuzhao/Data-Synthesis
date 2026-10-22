"""Single-worker three-stage scope; original process/retry lifecycle retained."""
from __future__ import annotations

import copy
import importlib
from pathlib import Path
import time

import finqa_v66_binding as b

path = b.protection_source('finqa_v64_controller')
source = path.read_text()
_controller = b.private_module('_v66_private_controller', path, (
    ('finqa_v64_', 'finqa_v66_', source.count('finqa_v64_')),
    ('V64_CONTROL_', 'V66_CONTROL_', source.count('V64_CONTROL_')),
    ('fcntl.flock(science_owner, fcntl.LOCK_EX | fcntl.LOCK_NB)',
     'fcntl.flock(science_owner, fcntl.LOCK_SH | fcntl.LOCK_NB)', 1),
    ('base.can_dispatch(self.active)', 'self.can_dispatch()', 3),
    ('max_gpu_workers=base.MAX_WORKERS', 'max_gpu_workers=1', 1),
    ('all_project_leases_observed_released=True',
     'own_workers_exited_and_no_unsettled_dispatches=True, peer_GPU_leases_not_required_released=True', 1),
))
base, inherited, evaluation = _controller.base, _controller.inherited, _controller.evaluation


def restore_states(journal):
    b.require(journal['protocol_id'] == b.BASE_PROTOCOL_ID and journal['active_jobs'] == []
              and len(journal['accepted']) == 21 and len(journal['job_states']) == 24
              and journal['evaluation_registered'] is False, 'old settled21/24 scope changed')
    states = copy.deepcopy(journal['job_states'])
    b.require(states[b.JOBS[0]]['status'] == 'HARD_BLOCKED'
              and states[b.JOBS[1]]['status'] == states[b.JOBS[2]]['status'] == 'DEPENDENCY_BLOCKED',
              'only the known replay and its two downstream dependency blocks may open')
    for key, state in states.items():
        if key in b.JOBS:
            state.update(status='PENDING', original_status=state['status'],
                         reason='explicitly authorized single diagnostic disposition', next_eligible_epoch=0)
        else:
            b.require(state['status'] == 'COMPLETE' and key in journal['accepted'],
                      'another hard failure cannot be unlocked by this exception')
    return states


class Controller(_controller.Controller):
    def __init__(self, root=b.ROOT, *, controller_attempt=1, runtime=None):
        self.control_root = Path(root).resolve()
        b.require(self.control_root == b.ROOT, 'foreign single-exception root')
        self.control_registration = importlib.import_module('finqa_v66_registration')
        self.control_protocol = self.control_registration.checked_protocol()
        self.control_registration.checked_implementation()
        self.control_prepared = self.control_registration.checked_prepared()
        runtime = runtime or importlib.import_module('finqa_v66_runtime').controller_runtime()
        base.Controller.__init__(self, b.SCIENTIFIC_ROOT, runtime=runtime,
                                  registration=b.source_module('finqa_v63_registration'))
        b.require(type(controller_attempt) is int and controller_attempt >= 1
                  and not (b.ROOT / 'closeout/record.json').exists(), 'terminal V66 cannot reopen')
        self.controller_attempt = controller_attempt
        self.controller_directory = b.ROOT / 'controllers' / f'attempt{controller_attempt:04d}'
        self.explicit_stop = False
        self._restore_journal()

    def _restore_journal(self):
        b.require(not _controller.stop_requested(b.ROOT), 'explicit V66 stop is terminal')
        path = b.ROOT / 'journal/state.json'
        fresh = not path.exists()
        journal = (b.read_ref(self.control_prepared['inherited_journal']) if fresh else b.checked(path))
        inherited._require_empty_settled_journal(journal)
        if fresh:
            b.require(self.controller_attempt == 1, 'missing first V66 journal')
            self.job_states = restore_states(journal)
        else:
            _controller._control_binding(journal, self.protocol, self.control_protocol)
            self.job_states = copy.deepcopy(journal['job_states'])
        self.attempt_history = copy.deepcopy(journal['attempt_history'])
        self.resource_wait_seconds = journal['resource_wait_seconds']
        for row in self.attempt_history:
            _controller.audit_attempt_exit(row, self.protocol, self.runtime)
        for key, reference in journal['accepted'].items():
            self.accepted[key] = b.read_ref(reference)
        b.require(set(self.job_states) == set(self.jobs), 'scientific roster changed')
        for key, state in self.job_states.items():
            b.require((state['status'] == 'COMPLETE') == (key in self.accepted), 'accepted scope mismatch')
            b.require(state['attempts'] == max((r['attempt'] for r in self.attempt_history if r['job_id'] == key), default=0),
                      'attempt ordinal may not reset')
        self._block_dependencies()

    def ready(self):
        jobs = super().ready()
        for job in jobs:
            b.scope(job)
        return jobs

    def can_dispatch(self):
        b.require(len(self.active) <= 1, 'V66 includes initialization/draining in its one-worker cap')
        return not self.active

    def acquire(self, job):
        b.scope(job)
        return super().acquire(job) if self.can_dispatch() else None

    def _host_gate(self, job):
        needed = base.host_requirement(job['kind'], self._memory())
        if needed is None:
            return None
        needed += 240 * base.GIB
        try:
            observed = self.runtime.host_memory()
        except (OSError, ValueError):
            return None
        available = observed.get('available_bytes')
        if type(available) is not int or available < needed:
            return None
        return dict(available_bytes=available, required_bytes=needed,
            reserve_bytes=base.HOST_RESERVE_BYTES, peer_V65_startup_reserved_bytes=240 * base.GIB,
            live_worker_count=len(self.active))

    def _validate_coordinate(self, child, result):
        b.scope(child.job)
        if child.job['kind'] != 'replay':
            return super()._validate_coordinate(child, result)
        from finqa_v66_diagnostics import accepted_exception
        job = child.job
        b.require(result['status'] == 'COMPLETE' and result['feedback_batch'] == 1
            and result['schema'] == 'v63_scientific_stage_result.v1'
            and result['protocol_id'] == self.protocol['id']
            and result['parent_id'] == self.parents[str(job['seed'])]['id']
            and (result['seed'], result['stage'], result['arm'], result['temperature'])
                == (job['seed'], job['stage'], job['arm'], job['temperature'])
            and result['model_released'] is True and result['denominator'] == 700
            and result['complete_replay'] is True and result['real_parent_unchanged'] is True,
            'all original replay coordinate, parent, denominator and completion gates remain required')
        b.require(accepted_exception(result)
                  and result['restored_completed_responses'] == result['responses'] == 830,
                  'replay exception must preserve FAIL and restore830, never replay new responses')
        evaluation.checked_file(result['payload'])

    def seal_training(self):
        b.require(len(self.accepted) == 24 and not self.active, 'all original24 core exits required')
        training = b.source_module('finqa_v63_training')
        branches = {}
        for seed in base.stats.SEEDS:
            for arm in base.stats.ARMS:
                training.checked_branch_result(self.root, seed, arm)
                branches[base.stats.coordinate(seed, arm)] = evaluation.file_binding(
                    self.root / f'branches/seed{seed}/{arm}/completed/record.json')
        evaluation.publish(self.root / 'training_barrier/record.json', dict(
            schema='v63_actual_six_new_training_exit_barrier.v1', protocol_id=self.protocol['id'],
            all_six_new_branches_complete=True, all_six_894_snapshots_sealed=True,
            all_dispatched_training_workers_exited=True, active_children=[], branch_records=branches,
            worker_exits=[self.accepted[key]['actual_exit'] for key in self.core],
            accepted_core_jobs={key: evaluation.file_binding(self.job_directory(job) / 'accepted/record.json')
                                for key, job in self.core.items()},
            diagnostic_exception_preserved=True, V66_control_protocol_id=self.control_protocol['id']))
        # This flag serves only the original lifecycle's finish transition. No
        # evaluation plan or generation jobs are registered by this controller.
        self.evaluation_registered = True
        self.journal()

    def finish(self):
        b.require(not self.active and len(self.accepted) == 24 and len(self.jobs) == 24,
                  'three scoped stages must exit successfully; no extra jobs')
        value = b.publish(b.ROOT / 'closeout/record.json', dict(
            schema='v66_single_point_exception_training_scope_closeout.v1', status='COMPLETE',
            completion_scope='three authorized stages only, not whole experiment',
            control_protocol_id=self.control_protocol['id'], protocol_id=self.protocol['id'],
            active_workers=0, accepted_scoped_jobs={key: evaluation.file_binding(
                self.job_directory(self.jobs[key]) / 'accepted/record.json') for key in b.JOBS},
            diagnostic_status='FAIL_ACCEPTED_BY_EXPLICIT_SINGLE_POINT_EXCEPTION',
            diagnostic_evidence=self.control_protocol['diagnostic_evidence'],
            new_response_replays=0, new_feedback=0, new_optimizer_updates=298,
            generation_jobs_started=0, private_scores_viewed=False,
            old_failed_records_unchanged=True, finished_epoch=time.time()))
        self.status('COMPLETE')
        return value


def controller_restart_audit(root, protocol, control_protocol, runtime):
    b.require(not _controller.stop_requested(root), 'explicit stop forbids restart')
    journal = b.checked(Path(root) / 'journal/state.json')
    _controller._control_binding(journal, protocol, control_protocol)
    inherited._require_empty_settled_journal(journal)
    for row in journal['attempt_history']:
        _controller.audit_attempt_exit(row, protocol, runtime)
    # Peer V65 workers may legitimately hold original GPU leases. This root's
    # exact exits and empty journal are required; each future launch acquires EX.
    return journal


_controller.Controller = Controller
_controller.controller_restart_audit = controller_restart_audit
supervise = _controller.supervise
