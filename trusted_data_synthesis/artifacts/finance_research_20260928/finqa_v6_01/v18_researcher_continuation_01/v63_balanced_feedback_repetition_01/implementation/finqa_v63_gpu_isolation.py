"""V63 known-owner shared-GPU gates; no foreign-process control."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import time
import xml.etree.ElementTree as ET

def gpu_isolation_policy():
    return dict(schema='v63_known_UID_shared_GPU_admission.v1',
        excluded_username=None, excluded_host_uid=None,
        known_UID_sharing_allowed=True, prior_account_specific_exclusion_cancelled=True,
        uid_fields=['real', 'effective', 'saved', 'filesystem'],
        source='nvidia-smi XML compute and graphics processes plus proc status/stat',
        account_name_lookup_required=False, process_birth_checked_before_and_after=True,
        unknown_ownership_or_unattributed_MPS_blocks_admission=True,
        controller_dispatch_and_locked_recheck=True,
        worker_pre_CUDA_and_pre_model_recheck=True,
        worker_each_resource_sample_checked=True, observation_cache_seconds=0,
        original_explicit_stop_and_lifetime_hard_gates_take_precedence=True,
        conflict_yields_only_own_worker_via_original_resource_deferral=True,
        own_unsealed_compute_may_be_recomputed_after_durable_audit=True,
        other_process_signals_or_migration=False, other_project_files_read=False,
        environment_or_command_line_read=False,
        no_global_GPU_reservation_or_zero_transient_overlap_guarantee=True,
        query_timeout_seconds=3, GPU_UUIDs_memory_math_and_worker_limits_unchanged=True)

def _process_identity(pid, *, proc_root=Path('/proc')):
    directory = Path(proc_root) / str(pid)
    try:
        before = (directory / 'stat').read_text().rsplit(')', 1)[1].split()
        uid_line = next(line for line in (directory / 'status').read_text().splitlines()
                        if line.startswith('Uid:'))
        uids = tuple(map(int, uid_line.split()[1:]))
        after = (directory / 'stat').read_text().rsplit(')', 1)[1].split()
        if (len(uids) != 4 or any(uid < 0 or uid >= 2**32 for uid in uids)
            or not before[19].isdigit() or before[19] != after[19]
            or after[0] in ('Z', 'X', 'x')):
            return dict(pid=pid, ownership_known=False, reason='changed_or_exiting_identity')
        return dict(pid=pid, birth=before[19], ownership_known=True, uids=uids)
    except (OSError, ValueError, IndexError, StopIteration) as error:
        return dict(pid=pid, ownership_known=False, reason=type(error).__name__)

def _query_xml(uuids):
    command = ['nvidia-smi', '-q', '-x', '-i', ','.join(uuids)]
    result = subprocess.run(command, check=True, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, text=True, timeout=3)
    return result.stdout

def probe_gpus(uuids, *, query=None, process_identity=None):
    uuids = tuple(dict.fromkeys(str(value) for value in uuids))
    if not uuids or any(not value.startswith('GPU-') or ',' in value for value in uuids):
        raise ValueError('registered GPU UUIDs are required for owner isolation')
    output = {uuid: dict(gpu_uuid=uuid, allowed=False,
        observed_epoch=time.time(), reason='not_observed', known_processes=[],
        unresolved_processes=[], process_count=None) for uuid in uuids}
    query = query or _query_xml
    process_identity = process_identity or _process_identity
    try:
        document = ET.fromstring(query(uuids))
        if document.tag != 'nvidia_smi_log':
            raise ValueError('unexpected GPU process query document')
        seen = set()
        for gpu in document.findall('gpu'):
            uuid = gpu.findtext('uuid', '').strip()
            if uuid not in output:
                continue
            if uuid in seen:
                raise ValueError('duplicate GPU ownership observation')
            seen.add(uuid)
            row = output[uuid]
            processes = gpu.find('processes')
            if processes is None or (processes.text or '').strip() not in ('', 'None'):
                row['reason'] = 'GPU_process_list_unavailable'
                continue
            entries = processes.findall('process_info')
            row['process_count'] = len(entries)
            for item in entries:
                pid = int(item.findtext('pid', '0'))
                if pid <= 0:
                    row['unresolved_processes'].append(dict(pid=pid, reason='invalid_process_id'))
                    continue
                # A shared MPS server is not a reliable attribution of clients.
                # Inspect only the public process name, never argv or environ.
                name = Path(item.findtext('process_name', '')).name.lower()
                process_type = item.findtext('type', '')
                if 'mps' in name or 'M' in process_type:
                    row['unresolved_processes'].append(dict(pid=pid, reason='unattributed_MPS_clients'))
                    continue
                owner = process_identity(pid)
                uids = owner.get('uids')
                known = (owner.get('ownership_known') is True and owner.get('pid') == pid
                    and isinstance(owner.get('birth'), str) and owner['birth'].isdigit()
                    and isinstance(uids, (list, tuple)) and len(uids) == 4
                    and all(type(uid) is int and 0 <= uid < 2**32 for uid in uids))
                if not known:
                    row['unresolved_processes'].append(dict(pid=pid, reason=owner.get('reason', 'unknown_UID')))
                else:
                    row['known_processes'].append(dict(pid=pid, birth=owner['birth'], uids=list(uids)))
            row['allowed'] = not row['unresolved_processes']
            row['reason'] = 'all_observed_process_owners_known' if row['allowed'] else 'ownership_unresolved'
    except (OSError, ValueError, KeyError, ET.ParseError, subprocess.SubprocessError) as error:
        for row in output.values():
            row.update(allowed=False, reason='owner_observation_unavailable', error_type=type(error).__name__)
    return output

class ControllerRuntime:
    def __init__(self, delegate):
        self.delegate = delegate

    def inventory(self):
        rows = self.delegate.inventory()
        if not rows:
            return []
        observations = probe_gpus([row['uuid'] for row in rows])
        return [dict(row, gpu_isolation=observations[row['uuid']]) for row in rows
                if observations[row['uuid']]['allowed']]

    def __getattr__(self, name):
        return getattr(self.delegate, name)

def install_controller_runtime(runtime):
    # Deliberately lazy: never import lifecycle measurements before the original
    # scientific closure has completed its dependency binding.
    return runtime if isinstance(runtime, ControllerRuntime) else ControllerRuntime(runtime)

def guarded_class(runtime):
    base = runtime.ResourceGuard

    class IsolatedResourceGuard(base):
        def _isolation(self, label, value=None):
            # Known user stops and original scientific lifetime failures retain
            # their meaning; unknown ownership cannot relabel either as a retry.
            if self.violation is not None:
                raise runtime.LifetimeResourceFailure('existing original resource failure', self.violation)
            if self.stop.requested and self.job.get('stage') not in ('replay_C1', 'replay_C05'):
                raise runtime.ExplicitStop('explicit stop before GPU owner-isolation check')
            uuid = runtime.GPU_UUIDS[str(self.gpu)]
            observed = probe_gpus([uuid])[uuid]
            self.isolation_checks = getattr(self, 'isolation_checks', 0) + 1
            self.isolation_latest = observed
            if not observed['allowed']:
                observation = dict(value or {}, at=runtime.now(), label=label,
                    resource_category='GPU_ownership_unresolved',
                    gpu_index=self.gpu, gpu_uuid=uuid, gpu_isolation=observed,
                    passed=False, no_foreign_process_signaled=True)
                self._defer(observation)
            return observed

        def _wait_until_capacity(self, *, cuda_initialized):
            if self.stop.requested:
                raise runtime.ExplicitStop('explicit stop before CUDA/model admission')
            label = 'post_CUDA_before_model' if cuda_initialized else 'before_CUDA'
            self._isolation(label)
            result = super()._wait_until_capacity(cuda_initialized=cuda_initialized)
            self._isolation(label + '_after_capacity_wait')
            return result

        def _sample(self, label, boundary, context):
            if self.stop.requested and self.job.get('stage') not in ('replay_C1', 'replay_C05'):
                raise runtime.ExplicitStop('explicit stop before original resource sample')
            value = super()._sample(label, boundary, context)
            # Original metrics are evaluated first. In particular, an allocated
            # peak violation cannot be hidden behind a new capacity deferral.
            self._hard_gates(value)
            value['gpu_isolation'] = self._isolation(label, value)
            return value

        def report(self):
            value = super().report()
            value.update(gpu_isolation_policy=gpu_isolation_policy(),
                         gpu_isolation_checks=getattr(self, 'isolation_checks', 0),
                         last_gpu_isolation_observation=getattr(self, 'isolation_latest', None))
            return value

    return IsolatedResourceGuard
