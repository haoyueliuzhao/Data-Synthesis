"""Frozen P1192 lineage and one independent training-state demonstration path.

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
PREPARATION_ROOT = V18 / 'v76_fixed_demonstration_closed_loop_01'
ROOT = PREPARATION_ROOT / 'execution_revision_01'
V75_ROOT = V18 / 'v75_training_state_demonstration_01/execution_revision_01'
V75_IMPLEMENTATION_ID = 'cca5d185b6b1a7c0368bcb5e63e576ef88210c4e020a8287032c2f539b941d73'
V74_ROOT = V18 / 'v74_cross_history_continuation_01'
V74_IMPLEMENTATION_ID = '46dd9616dcb6377e57a54a7c69adc683f011c4ef73a6e997c73e6c649f56ab99'
V73_PREPARATION = V18 / 'v73_same_context_probe_01'
V73_ROOT = V73_PREPARATION / 'execution_revision_02'
V73_IMPLEMENTATION_ID = '9d3b2c748fbc0fc0610f04dc4e4da59ffa1676d2e52d12417dea32db106b9cad'
V72_ROOT = V18 / 'v72_low_lr_continuation_01'
V72_IMPLEMENTATION_ID = '44b1549162941868a73dea58de96f3d24a58e57a69e3039b5527ed966d91fd87'
V71_ROOT = V18 / 'v71_fixed_distribution_control_01/execution_revision_01'
V71_IMPLEMENTATION_ID = 'ae5ea266872c9f269ad39c2adeb8f2566fa922adfa0f5f82bb3bd20f47a00244'
V71_PROTOCOL_ID = '1b69496f9fe3a1617eab1d6a34739c60305c63d00229924c0edbdb507b9d6d80'
V70_ROOT = V18 / 'v70_full_closed_loop_01'
V70_IMPLEMENTATION_ID = '7ba22615a08cc7763bb30ff4a6da9c5930e3747be2eabfa4a1253213baa82589'
V70_PROTOCOL_ID = 'a5ca2c859c88db4b5b4db84a1c3afc2aa4feccd193b098a2b5d5174322cf9c78'
V63_ROOT = SOURCE_ROOT = PARENT_ROOT = SCIENTIFIC_ROOT = V18 / 'v63_balanced_feedback_repetition_01'
OLD_ROOT = V18 / 'v54_feedback_temperature_01/automatic_recovery_01'
V64_ROOT = PREDECESSOR_ROOT = V63_ROOT / 'gpu_memory_protection_01'
BASE_PROTOCOL_ID = 'a4e56b5954cad3f578cfa5e8ba7bac64a87810cc857d04ef8c5b736f28b4d8db'
BASE_IMPLEMENTATION_ID = '4442335a0a1e881bbba25bd97a507f73ce3fcbf7fcc9c14b4b264f8a391b6dc8'
V64_IMPLEMENTATION_ID = '68f98365beaeebe0e256bc551939c9cb1ae5963833fa50d151b282e2c9c4ef71'
PYTHON = REPO / 'trusted_data_synthesis/.venv/bin/python'
USER_PLAN = Path('/home/zhuxinrui/.codex/attachments/2d927b13-b9ad-4758-b76b-fa276d6d61ab/已粘贴的文本.txt')
SEED = 137
SEEDS = (137,)
POINTS = (1192, 1490, 1788)
APPLIED_POINTS = (1192, 1490)
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
            'V76 must not overwrite historical artifacts or publish through symlinks')
    body = {key: value for key, value in body.items() if key != 'id'}
    value = dict(body, id=digest(body))
    if path.exists():
        require(checked(path) == value, 'existing immutable V76 artifact differs')
        return value
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix='.v76-record-', dir=path.parent)
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


def source_v70(name):
    full = name if name.startswith('finqa_v70_') else 'finqa_v70_' + name
    return _source(full, V70_ROOT, V70_IMPLEMENTATION_ID)


def source_v71(name):
    return _source(name, V71_ROOT, V71_IMPLEMENTATION_ID)


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


def source_v72(name):
    full = name if name.startswith("finqa_v72_") else "finqa_v72_" + name
    return _source(full, V72_ROOT, V72_IMPLEMENTATION_ID)


def write_status(path, body):
    """Atomic mutable progress only inside this independent experiment."""
    path = Path(path)
    require(path.resolve().is_relative_to(ROOT.resolve()) and not path.is_symlink(),
            "progress escaped the V76 root")
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".v76-status-", dir=path.parent)
    try:
        with os.fdopen(fd, "w") as stream:
            json.dump(body, stream, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
            stream.write("\n"); stream.flush(); os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def source_v73(name):
    full = name if name.startswith("finqa_v73_") else "finqa_v73_" + name
    return _source(full, V73_ROOT, V73_IMPLEMENTATION_ID)


def source_v74(name):
    full = name if name.startswith("finqa_v74_") else "finqa_v74_" + name
    return _source(full, V74_ROOT, V74_IMPLEMENTATION_ID)


def source_v75(name):
    full = name if name.startswith("finqa_v75_") else "finqa_v75_" + name
    return _source(full, V75_ROOT, V75_IMPLEMENTATION_ID)
