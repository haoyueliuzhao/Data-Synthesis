"""Read-only frozen lineage and independent group-ready scoring namespace."""
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
ROOT = SCIENTIFIC_ROOT / 'partial_scoring_01'
COMPLETION_ROOT = SCIENTIFIC_ROOT / 'evaluation_completion_01'
SOURCE_GENERATION_ROOT = SCIENTIFIC_ROOT / 'early_generation_01'
COMPLETION_IMPLEMENTATION_ID = '653d3a7936ce8564756c8f61c1d0370bbd3b1b604a0aaf36af30b711c3962141'
COMPLETION_PROTOCOL_ID = '92d90941f2757278f94dd3bcdd73af39d1271fb2aa37bf896260aa4efa382a83'
BASE_PROTOCOL_ID = 'a4e56b5954cad3f578cfa5e8ba7bac64a87810cc857d04ef8c5b736f28b4d8db'
EARLY_PROTOCOL_ID = '85a9477e307377c0b57d4045f0d9a2498d22ba5554f7749b3aa1b165a997c870'
PYTHON = REPO / 'trusted_data_synthesis/.venv/bin/python'
OWNER_UID = 1004
ELIGIBLE_COORDINATES = tuple((seed, arm) for seed in (137, 251, 389) for arm in ('C1', 'C05'))
MAX_CPU_WORKERS = 2
CPU_RSS_LIMIT_GIB = 32
HOST_RESERVE_GIB = 96
OTHER_SCOPES_STARTUP_GIB = 6 * 48 + 64


def eligibility_path(coordinate):
    allowed = {f'seed{seed}/{arm}' for seed, arm in ELIGIBLE_COORDINATES}
    require(coordinate in allowed, 'only the original six model groups may be scored')
    return ROOT / 'eligibility' / coordinate / 'record.json'


def _completion_binding():
    directory = COMPLETION_ROOT / 'implementation'
    if str(directory) not in sys.path:
        sys.path.insert(0, str(directory))
    module = importlib.import_module('finqa_v67_binding')
    if Path(module.__file__).resolve() != directory / 'finqa_v67_binding.py':
        raise ValueError('partial scoring requires the actual frozen V67 binding')
    manifest = module.checked(directory / 'record.json')
    module.require(manifest['id'] == COMPLETION_IMPLEMENTATION_ID
        and module.sha(module.__file__) == manifest['sha256']['finqa_v67_binding.py'],
        'frozen completion binding changed')
    return module


_original = _completion_binding()
require, digest, sha, checked, file_ref, entry, read_ref = (
    _original.require, _original.digest, _original.sha, _original.checked,
    _original.file_ref, _original.entry, _original.read_ref)
source_module = _original.source_module
source_generation_module = early_module = _original.early_module
base_protocol = _original.base_protocol
install_scientific_paths = _original.install_scientific_paths


def completion_module(name):
    directory = COMPLETION_ROOT / 'implementation'
    manifest = checked(directory / 'record.json')
    filename = name + '.py'
    require(manifest['id'] == COMPLETION_IMPLEMENTATION_ID and filename in manifest['sha256']
            and sha(directory / filename) == manifest['sha256'][filename],
            'unregistered frozen completion dependency')
    if str(directory) not in sys.path:
        sys.path.insert(0, str(directory))
    module = importlib.import_module(name)
    require(Path(module.__file__).resolve() == directory / filename,
            'workspace completion module contaminated scoring')
    return module


def publish(path, body):
    target = Path(path).resolve()
    require(target.is_relative_to(ROOT) and not Path(path).is_symlink(),
            'partial scoring cannot write original generations, controls or scientific results')
    body = {key: value for key, value in body.items() if key != 'id'}
    value = dict(body, id=digest(body))
    if target.exists():
        require(checked(target) == value, 'existing immutable scoring evidence differs')
        return value
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix='.v68-record-', dir=target.parent)
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
