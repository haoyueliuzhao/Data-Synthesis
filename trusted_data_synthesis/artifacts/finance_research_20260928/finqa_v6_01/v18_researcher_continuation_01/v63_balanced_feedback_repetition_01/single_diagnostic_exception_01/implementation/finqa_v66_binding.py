"""One explicitly authorized diagnostic exception, separate from V63/V64."""
from __future__ import annotations

import importlib
import json
import os
from pathlib import Path
import sys
import tempfile
from types import ModuleType

REPO = Path('/data1/zhuxinrui/projects/Data-Synthesis')
SCIENTIFIC_ROOT = REPO / 'trusted_data_synthesis/artifacts/finance_research_20260928/finqa_v6_01/v18_researcher_continuation_01/v63_balanced_feedback_repetition_01'
OLD_CONTROL = SCIENTIFIC_ROOT / 'gpu_memory_protection_01'
ROOT = SCIENTIFIC_ROOT / 'single_diagnostic_exception_01'
SOURCE = SCIENTIFIC_ROOT / 'implementation'
PYTHON = REPO / 'trusted_data_synthesis/.venv/bin/python'
BASE_PROTOCOL_ID = 'a4e56b5954cad3f578cfa5e8ba7bac64a87810cc857d04ef8c5b736f28b4d8db'
BASE_IMPLEMENTATION_ID = '4442335a0a1e881bbba25bd97a507f73ce3fcbf7fcc9c14b4b264f8a391b6dc8'
OWNER_UID = 1004
STAGES = ('replay_C05', 'distribution_C05', 'train_C05')
JOBS = tuple('seed389.' + stage for stage in STAGES)
CHECKPOINT = SCIENTIFIC_ROOT / 'stages/seed389/replay_C05/checkpoints/response000830'
FAILURE = SCIENTIFIC_ROOT / 'stages/seed389/replay_C05/attempts/attempt0001/failure/record.json'


def _old_binding():
    directory = OLD_CONTROL / 'implementation'
    if str(directory) not in sys.path:
        sys.path.insert(0, str(directory))
    module = importlib.import_module('finqa_v64_binding')
    if Path(module.__file__).resolve() != directory / 'finqa_v64_binding.py':
        raise ValueError('V66 must bind the immutable V64 source, not workspace code')
    manifest = module.checked(directory / 'record.json')
    module.require(module.sha(module.__file__) == manifest['sha256']['finqa_v64_binding.py'],
                   'immutable V64 binding changed')
    return module


_original = _old_binding()
require, digest, sha, checked, file_ref, entry, read_ref = (
    _original.require, _original.digest, _original.sha, _original.checked,
    _original.file_ref, _original.entry, _original.read_ref)
source_module, base_protocol = _original.source_module, _original.base_protocol


def protection_source(name):
    directory = OLD_CONTROL / 'implementation'
    manifest = checked(directory / 'record.json')
    filename = name + '.py'
    require(filename in manifest['sha256'], 'unregistered V64 source')
    path = directory / filename
    require(sha(path) == manifest['sha256'][filename], 'frozen V64 source changed')
    return path


def private_module(name, path, replacements=()):
    source = Path(path).read_text()
    for before, after, count in replacements:
        require(source.count(before) == count, 'private adapter structure changed: ' + before)
        source = source.replace(before, after)
    module = ModuleType(name)
    module.__file__, module.__package__ = str(Path(path).resolve()), ''
    sys.modules[name] = module
    exec(compile(source, module.__file__ + '::V66_registered_adapter', 'exec'), module.__dict__)
    return module


def publish(path, body):
    p = Path(path).resolve()
    require(p.is_relative_to(ROOT) and not p.is_symlink(), 'V66 record escaped independent root')
    body = {k: v for k, v in body.items() if k != 'id'}
    value = dict(**body, id=digest(body))
    if p.exists():
        require(checked(p) == value, 'immutable V66 record differs')
        return value
    p.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix='.v66-record-', dir=p.parent)
    try:
        with os.fdopen(fd, 'w') as stream:
            json.dump(value, stream, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
            stream.write('\n')
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temporary, p)
        directory = os.open(p.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        Path(temporary).unlink(missing_ok=True)
    return value


def scope(job):
    require(job.get('job_id', job.get('id')) in JOBS
            and job.get('seed') == 389 and job.get('arm') == 'C05'
            and job.get('stage') in STAGES, 'V66 is limited to three seed389-C05 stages')
