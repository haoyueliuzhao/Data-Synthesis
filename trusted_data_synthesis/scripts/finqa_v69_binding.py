"""Frozen lineage and exact one-job GPU0-to-GPU6 handoff authorization."""
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
ROOT = SCIENTIFIC_ROOT / 'gpu0_to_gpu6_migration_01'
COMPLETION_ROOT = SOURCE_ROOT = SCIENTIFIC_ROOT / 'evaluation_completion_01'
SOURCE_GENERATION_ROOT = SCIENTIFIC_ROOT / 'early_generation_01'
SCORING_ROOT = SCIENTIFIC_ROOT / 'partial_scoring_01'
COMPLETION_IMPLEMENTATION_ID = '653d3a7936ce8564756c8f61c1d0370bbd3b1b604a0aaf36af30b711c3962141'
COMPLETION_PROTOCOL_ID = '92d90941f2757278f94dd3bcdd73af39d1271fb2aa37bf896260aa4efa382a83'
BASE_PROTOCOL_ID = 'a4e56b5954cad3f578cfa5e8ba7bac64a87810cc857d04ef8c5b736f28b4d8db'
EARLY_PROTOCOL_ID = '85a9477e307377c0b57d4045f0d9a2498d22ba5554f7749b3aa1b165a997c870'
PYTHON = REPO / 'trusted_data_synthesis/.venv/bin/python'
OWNER_UID = 1004
TARGET_JOB_ID = 'step894_dev883_greedy_seed389_C05_b1_draw20260928'
DESTINATION_JOB_ID = 'step894_calibration120_random_T1_seed389_C05_b1_draw29'
TARGET_PID, TARGET_BIRTH = 203941, '507110006'
CONTROLLER_PID, CONTROLLER_BIRTH = 203516, '507109451'
DESTINATION_PID, DESTINATION_BIRTH = 1254401, '507299393'
SOURCE_GPU, DEST_GPU = 0, 6
SOURCE_ATTEMPT, DEST_ATTEMPT = 1, 2
MAX_NEW_GPU_WORKERS = 1
STARTUP_AVAILABLE_GIB = 512
STOP_SETTLE_SECONDS = 600


def _source_binding():
    directory = COMPLETION_ROOT / 'implementation'
    if str(directory) not in sys.path:
        sys.path.insert(0, str(directory))
    module = importlib.import_module('finqa_v67_binding')
    if Path(module.__file__).resolve() != directory / 'finqa_v67_binding.py':
        raise ValueError('migration must use the actual frozen generation binding')
    manifest = module.checked(directory / 'record.json')
    module.require(manifest['id'] == COMPLETION_IMPLEMENTATION_ID
        and module.sha(module.__file__) == manifest['sha256']['finqa_v67_binding.py'],
        'frozen generation binding changed')
    return module


_original = _source_binding()
require, digest, sha, checked, file_ref, entry, read_ref = (
    _original.require, _original.digest, _original.sha, _original.checked,
    _original.file_ref, _original.entry, _original.read_ref)
source_module, early_module = _original.source_module, _original.early_module
base_protocol, install_scientific_paths = _original.base_protocol, _original.install_scientific_paths


def completion_module(name):
    directory = COMPLETION_ROOT / 'implementation'
    manifest = checked(directory / 'record.json')
    filename = name + '.py'
    require(manifest['id'] == COMPLETION_IMPLEMENTATION_ID and filename in manifest['sha256']
            and sha(directory / filename) == manifest['sha256'][filename],
            'unregistered frozen generation dependency')
    if str(directory) not in sys.path:
        sys.path.insert(0, str(directory))
    module = importlib.import_module(name)
    require(Path(module.__file__).resolve() == directory / filename,
            'workspace generation source contaminated migration')
    return module


def target_directory():
    return COMPLETION_ROOT / 'evaluations/jobs' / TARGET_JOB_ID


def source_attempt_directory():
    return target_directory() / 'attempts/attempt0001'


def destination_attempt_directory():
    return target_directory() / 'attempts/attempt0002'


def publish(path, body):
    target = Path(path).resolve()
    require(target.is_relative_to(ROOT) and not Path(path).is_symlink(),
            'migration audit publication must stay in its independent root')
    body = {key: value for key, value in body.items() if key != 'id'}
    value = dict(body, id=digest(body))
    if target.exists():
        require(checked(target) == value, 'existing immutable migration evidence differs')
        return value
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix='.v69-record-', dir=target.parent)
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


def append_target_record(path, body):
    """The explicit migration permits fresh attempt2/accepted, never rewrites."""
    path = Path(path).resolve()
    allowed = {destination_attempt_directory() / part / 'record.json'
               for part in ('dispatch_intent', 'launch', 'actual_exit', 'migration_binding')}
    allowed.add(target_directory() / 'accepted/record.json')
    require(path in allowed and not path.exists(),
            'only the authorized new attempt2 lifecycle and final acceptance may be appended')
    return _original.publish(path, body)


def __getattr__(name):
    return getattr(_original, name)
