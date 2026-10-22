"""Pure, read-only scientific lineage and an independent Full continuation root.

Importing bindings never loads a model, starts a process, initializes CUDA or
writes an artifact. Historical frozen bundles stay at their original paths.
"""
from __future__ import annotations

import hashlib
import importlib
import json
import os
from pathlib import Path
import sys
import tempfile

REPO = Path('/data1/zhuxinrui/projects/Data-Synthesis')
V18 = REPO / 'trusted_data_synthesis/artifacts/finance_research_20260928/finqa_v6_01/v18_researcher_continuation_01'
ROOT = V18 / 'v70_full_closed_loop_01'
V63_ROOT = SOURCE_ROOT = PARENT_ROOT = SCIENTIFIC_ROOT = V18 / 'v63_balanced_feedback_repetition_01'
OLD_ROOT = V18 / 'v54_feedback_temperature_01/automatic_recovery_01'
V64_ROOT = PREDECESSOR_ROOT = V63_ROOT / 'gpu_memory_protection_01'
BASE_PROTOCOL_ID = 'a4e56b5954cad3f578cfa5e8ba7bac64a87810cc857d04ef8c5b736f28b4d8db'
BASE_IMPLEMENTATION_ID = '4442335a0a1e881bbba25bd97a507f73ce3fcbf7fcc9c14b4b264f8a391b6dc8'
V64_IMPLEMENTATION_ID = '68f98365beaeebe0e256bc551939c9cb1ae5963833fa50d151b282e2c9c4ef71'
PYTHON = REPO / 'trusted_data_synthesis/.venv/bin/python'
USER_PLAN = Path('/home/zhuxinrui/.codex/attachments/495116ae-9bbe-4781-956b-38cfe8d1c14e/已粘贴的文本.txt')
SEED = 137
SEEDS = (137,)
POINTS = (894, 1192, 1490)
APPLIED_POINTS = (894, 1192)
DRAW_SEEDS = (101, 103)
OWNER_UID = 1004
MAX_WORKERS = 6
MAX_WORKERS_PER_GPU = 1
GPU_PRIORITY = (6, 7, 2, 4, 5, 3, 1, 0)
_MANIFESTS = {}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
        separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def sha(path):
    value = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 ** 2), b''):
            value.update(chunk)
    return value.hexdigest()


def checked(path):
    value = json.loads(Path(path).read_bytes())
    require(value.get('id') == digest({key: row for key, row in value.items() if key != 'id'}),
            'immutable record identity changed: ' + str(path))
    return value


def file_ref(path):
    path = Path(path).resolve()
    return dict(path=str(path), sha256=sha(path))


def entry(path):
    return dict(**file_ref(path), id=checked(path)['id'])


def read_ref(reference):
    require(sha(reference['path']) == reference['sha256'], 'bound saved bytes changed: ' + str(reference['path']))
    value = checked(reference['path'])
    require('id' not in reference or value['id'] == reference['id'], 'bound saved record ID changed')
    return value


def publish(path, body):
    """Atomic immutable publication, strictly within the new scientific root."""
    requested = Path(path)
    path = requested.resolve()
    require(path.is_relative_to(ROOT.resolve()) and not requested.is_symlink(),
            'V70 must not overwrite historical artifacts or publish through symlinks')
    body = {key: value for key, value in body.items() if key != 'id'}
    value = dict(body, id=digest(body))
    if path.exists():
        require(checked(path) == value, 'existing immutable V70 artifact differs')
        return value
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix='.v70-record-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w') as stream:
            json.dump(value, stream, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
            stream.write('\n'); stream.flush(); os.fsync(stream.fileno())
        os.link(temporary, path)
        descriptor = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
    finally:
        Path(temporary).unlink(missing_ok=True)
    return value


def _source(name, root, expected):
    directory = root / 'implementation'
    if root not in _MANIFESTS:
        manifest = checked(directory / 'record.json')
        require(manifest['id'] == expected, 'historical scientific implementation changed')
        _MANIFESTS[root] = manifest
    manifest = _MANIFESTS[root]
    filename = name + '.py'
    require(filename in manifest['sha256'] and sha(directory / filename) == manifest['sha256'][filename],
            'unregistered or changed historical scientific module: ' + name)
    if str(directory) not in sys.path:
        sys.path.insert(0, str(directory))
    module = importlib.import_module(name)
    require(Path(module.__file__).resolve() == directory / filename,
            'non-frozen scientific import: ' + name)
    return module


def source_module(name):
    return _source(name, V63_ROOT, BASE_IMPLEMENTATION_ID)


def source_v64(name):
    return _source(name, V64_ROOT, V64_IMPLEMENTATION_ID)


predecessor_module = source_v64


def install_scientific_paths():
    return source_module('finqa_v63_binding').install_scientific_paths()


def old_module(name):
    install_scientific_paths()
    return source_module('finqa_v63_binding').old_module(name)


def base_protocol():
    value = checked(V63_ROOT / 'protocol/record.json')
    require(value['id'] == BASE_PROTOCOL_ID, 'original V63 protocol changed')
    return value


def install_registered_auxiliary():
    install_scientific_paths()
    return source_module('finqa_v63_entry').install_registered_auxiliary()
