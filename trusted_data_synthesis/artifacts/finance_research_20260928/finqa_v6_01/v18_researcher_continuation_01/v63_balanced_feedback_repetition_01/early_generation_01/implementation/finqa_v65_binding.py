"""Pure identities for five accepted endpoints' unscored early generation."""
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
SCIENTIFIC_ROOT = V18 / 'v63_balanced_feedback_repetition_01'
ROOT = SCIENTIFIC_ROOT / 'early_generation_01'
PREDECESSOR_ROOT = SCIENTIFIC_ROOT / 'gpu_memory_protection_01'
PEER_ROOT = SCIENTIFIC_ROOT / 'single_diagnostic_exception_01'
COMMON_ROOT = SCIENTIFIC_ROOT / 'parallel_continuation_authorization_01'
OLD_ROOT = V18 / 'v54_feedback_temperature_01/automatic_recovery_01'
BASE_PROTOCOL_ID = 'a4e56b5954cad3f578cfa5e8ba7bac64a87810cc857d04ef8c5b736f28b4d8db'
BASE_IMPLEMENTATION_ID = '4442335a0a1e881bbba25bd97a507f73ce3fcbf7fcc9c14b4b264f8a391b6dc8'
PREDECESSOR_PROTOCOL_ID = '2ae502f0d54bef462d92483c32a5408282250accd873d4104900d9b6ac8d89f9'
PREDECESSOR_IMPLEMENTATION_ID = '68f98365beaeebe0e256bc551939c9cb1ae5963833fa50d151b282e2c9c4ef71'
PYTHON = REPO / 'trusted_data_synthesis/.venv/bin/python'
OWNER_UID = 1004
SEEDS, ARMS, BATCH = (137, 251, 389), ('C1', 'C05'), 1
DRAW_SEEDS = (101, 103)
MAX_WORKERS = 5
ELIGIBLE_COORDINATES = ((137, 'C1'), (137, 'C05'), (251, 'C1'), (251, 'C05'), (389, 'C1'))
_MANIFESTS = {}


def require(ok, message):
    if not ok:
        raise ValueError(message)


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
        separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 ** 2), b''):
            h.update(chunk)
    return h.hexdigest()


def checked(path):
    value = json.loads(Path(path).read_bytes())
    require(value.get('id') == digest({k: v for k, v in value.items() if k != 'id'}),
            'immutable record identity changed: ' + str(path))
    return value


def file_ref(path):
    p = Path(path).resolve()
    return dict(path=str(p), sha256=sha(p))


def entry(path):
    return dict(**file_ref(path), id=checked(path)['id'])


def read_ref(reference):
    require(sha(reference['path']) == reference['sha256'], 'bound reference bytes changed')
    value = checked(reference['path'])
    require('id' not in reference or value['id'] == reference['id'], 'bound record identity changed')
    return value


def publish(path, body):
    target = Path(path).resolve()
    require(target.is_relative_to(ROOT) or target.is_relative_to(COMMON_ROOT),
            'V65 cannot overwrite old science/control records')
    body = {k: v for k, v in body.items() if k != 'id'}
    value = dict(**body, id=digest(body))
    if target.exists():
        require(checked(target) == value, 'existing immutable V65 record differs')
        return value
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix='.v65-record-', dir=target.parent)
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


def _source(name, root, expected):
    directory = root / 'implementation'
    if root not in _MANIFESTS:
        manifest = checked(directory / 'record.json')
        require(manifest['id'] == expected, 'frozen parent implementation changed')
        _MANIFESTS[root] = manifest
    manifest = _MANIFESTS[root]
    filename = name + '.py'
    require(filename in manifest['sha256'] and sha(directory / filename) == manifest['sha256'][filename],
            'module escaped its frozen parent source registration')
    if str(directory) not in sys.path:
        sys.path.insert(0, str(directory))
    module = importlib.import_module(name)
    require(Path(module.__file__).resolve() == directory / filename, 'workspace source contaminated production')
    return module


def source_module(name):
    return _source(name, SCIENTIFIC_ROOT, BASE_IMPLEMENTATION_ID)


def predecessor_module(name):
    return _source(name, PREDECESSOR_ROOT, PREDECESSOR_IMPLEMENTATION_ID)


source_v64 = predecessor_module


def install_scientific_paths():
    return source_module('finqa_v63_binding').install_scientific_paths()


def base_protocol():
    value = checked(SCIENTIFIC_ROOT / 'protocol/record.json')
    require(value['id'] == BASE_PROTOCOL_ID, 'old scientific protocol changed')
    return value


def __getattr__(name):
    return getattr(source_module('finqa_v63_binding'), name)
