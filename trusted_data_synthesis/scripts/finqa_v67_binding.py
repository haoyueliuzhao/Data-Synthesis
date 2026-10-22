"""Pure bindings for JSON finalization repair and the final four jobs."""
from __future__ import annotations

import importlib
import json
import os
from pathlib import Path
import sys
import tempfile

REPO = Path('/data1/zhuxinrui/projects/Data-Synthesis')
V18 = REPO / 'trusted_data_synthesis/artifacts/finance_research_20260928/finqa_v6_01/v18_researcher_continuation_01'
SCIENTIFIC_ROOT = V18 / 'v63_balanced_feedback_repetition_01'
ROOT = SCIENTIFIC_ROOT / 'evaluation_completion_01'
SOURCE_GENERATION_ROOT = SCIENTIFIC_ROOT / 'early_generation_01'
OLD_GENERATION_ROOT = PEER_ROOT = SOURCE_GENERATION_ROOT
RECOVERY_ROOT = SCIENTIFIC_ROOT / 'single_diagnostic_exception_01'
EARLY_IMPLEMENTATION_ID = 'e7721781d4af4bbd3f943b25101c391d6bd587262068e3330c7a3b6febb4881b'
EARLY_PROTOCOL_ID = '85a9477e307377c0b57d4045f0d9a2498d22ba5554f7749b3aa1b165a997c870'
BASE_PROTOCOL_ID = 'a4e56b5954cad3f578cfa5e8ba7bac64a87810cc857d04ef8c5b736f28b4d8db'
BASE_IMPLEMENTATION_ID = '4442335a0a1e881bbba25bd97a507f73ce3fcbf7fcc9c14b4b264f8a391b6dc8'
PYTHON = REPO / 'trusted_data_synthesis/.venv/bin/python'
OWNER_UID = 1004
MAX_WORKERS = 3
MAX_WORKERS_PER_GPU = 2
MAX_NEW_WORKERS_PER_GPU = 1
CPU_SEAL_WORKERS = 1
GPU_PRIORITY = (0, 6, 7, 2, 4, 5, 3, 1)
ELIGIBLE_COORDINATES = ((389, 'C05'),)
RESIDUAL_PEER_JOBS = (
    'step894_dev883_greedy_seed251_C05_b1_draw20260928',
    'step894_dev883_greedy_seed251_C1_b1_draw20260928',
    'step894_dev883_greedy_seed389_C1_b1_draw20260928',
)


def _original_binding():
    directory = SOURCE_GENERATION_ROOT / 'implementation'
    if str(directory) not in sys.path:
        sys.path.insert(0, str(directory))
    module = importlib.import_module('finqa_v65_binding')
    if Path(module.__file__).resolve() != directory / 'finqa_v65_binding.py':
        raise ValueError('V67 must use the actual frozen V65 binding')
    manifest = module.checked(directory / 'record.json')
    module.require(manifest['id'] == EARLY_IMPLEMENTATION_ID
        and module.sha(module.__file__) == manifest['sha256']['finqa_v65_binding.py'],
        'original early-generation binding changed')
    return module


_original = _original_binding()
require, digest, sha, checked, file_ref, entry, read_ref = (
    _original.require, _original.digest, _original.sha, _original.checked,
    _original.file_ref, _original.entry, _original.read_ref)
source_module, predecessor_module = _original.source_module, _original.predecessor_module
base_protocol = _original.base_protocol
install_scientific_paths = _original.install_scientific_paths


def early_module(name):
    directory = SOURCE_GENERATION_ROOT / 'implementation'
    manifest = checked(directory / 'record.json')
    require(manifest['id'] == EARLY_IMPLEMENTATION_ID, 'original V65 implementation changed')
    filename = name + '.py'
    require(filename in manifest['sha256'] and sha(directory / filename) == manifest['sha256'][filename],
            'unregistered original early-generation source')
    if str(directory) not in sys.path:
        sys.path.insert(0, str(directory))
    module = importlib.import_module(name)
    require(Path(module.__file__).resolve() == directory / filename, 'non-frozen V65 source contaminated continuation')
    return module


source_generation_module = early_module


def publish(path, body):
    target = Path(path).resolve()
    require(target.is_relative_to(ROOT) and not Path(path).is_symlink(),
            'V67 cannot overwrite original generations, failures or control state')
    body = {k: v for k, v in body.items() if k != 'id'}
    value = dict(**body, id=digest(body))
    if target.exists():
        require(checked(target) == value, 'existing immutable V67 record differs')
        return value
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix='.v67-record-', dir=target.parent)
    try:
        with os.fdopen(fd, 'w') as stream:
            json.dump(value, stream, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
            stream.write('\n'); stream.flush(); os.fsync(stream.fileno())
        os.link(temporary, target)
        descriptor = os.open(target.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
    finally:
        Path(temporary).unlink(missing_ok=True)
    return value


def __getattr__(name):
    return getattr(_original, name)


def gpu_slot_policy():
    """Two global exclusive lanes: one frozen legacy lane, one V67 lane.

    Legacy workers continue to validate and hold their original exclusive
    descriptor. V67 never borrows that descriptor or modifies its inode: a
    separate globally stable directory supplies the one secondary lane.
    """
    legacy = Path(base_protocol()['gpu_lease_root']).resolve()
    secondary = legacy / 'v67-secondary-slot'
    return dict(schema='v67_two_global_exclusive_GPU_lanes.v1',
        max_total_project_workers_per_gpu=MAX_WORKERS_PER_GPU,
        max_legacy_workers_per_gpu=1, own_max_workers_per_gpu=MAX_NEW_WORKERS_PER_GPU,
        legacy_gpu_lease_root=str(legacy), second_slot_lease_root=str(secondary),
        lock_filename='gpu-<canonical_UUID_sha256>.lock',
        both_lanes_require_exclusive_flock=True,
        inherited_descriptor_path_inode_and_flock_checked=True,
        legacy_descriptor_or_frozen_workers_modified=False,
        primary_exit_never_creates_a_second_secondary_slot=True,
        future_controllers_must_reuse_secondary_slot_root=True,
        initializing_waiting_and_draining_count_in_lane=True,
        original_generate_admission_and_lifetime_gates_unchanged=True,
        foreign_processes_never_signaled_or_migrated=True)
