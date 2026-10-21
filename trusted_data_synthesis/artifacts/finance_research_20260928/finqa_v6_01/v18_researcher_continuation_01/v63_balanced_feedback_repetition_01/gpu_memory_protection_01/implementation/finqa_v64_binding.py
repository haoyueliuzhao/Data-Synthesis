"""Pure identities for a separate operational protection layer over V63."""
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
ROOT = SCIENTIFIC_ROOT / 'gpu_memory_protection_01'
SOURCE = SCIENTIFIC_ROOT / 'implementation'
PYTHON = REPO / 'trusted_data_synthesis/.venv/bin/python'
BASE_PROTOCOL_ID = 'a4e56b5954cad3f578cfa5e8ba7bac64a87810cc857d04ef8c5b736f28b4d8db'
BASE_IMPLEMENTATION_ID = '4442335a0a1e881bbba25bd97a507f73ce3fcbf7fcc9c14b4b264f8a391b6dc8'
OWNER_UID = 1004


def require(condition, message):
    if not condition:
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
    v = json.loads(Path(path).read_bytes())
    require(v.get('id') == digest({k: x for k, x in v.items() if k != 'id'}),
            'immutable record identity changed: ' + str(path))
    return v


def file_ref(path):
    p = Path(path).resolve()
    return dict(path=str(p), sha256=sha(p))


def entry(path):
    p = Path(path).resolve()
    return dict(**file_ref(p), id=checked(p)['id'])


def read_ref(reference):
    require(sha(reference['path']) == reference['sha256'], 'bound source bytes changed')
    v = checked(reference['path'])
    require('id' not in reference or reference['id'] == v['id'], 'bound source identity changed')
    return v


def publish(path, body):
    p = Path(path).resolve()
    require(p.is_relative_to(ROOT.resolve()) and not p.is_symlink(),
            'new operational records must stay inside the separate V64 control root')
    body = {k: v for k, v in body.items() if k != 'id'}
    value = dict(**body, id=digest(body))
    if p.exists():
        require(checked(p) == value, 'existing immutable operational record differs')
        return value
    p.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix='.v64-record-', dir=p.parent)
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


def source_module(name):
    """Load one exact original file; this helper does not eagerly load science."""
    manifest = checked(SOURCE / 'record.json')
    require(manifest['id'] == BASE_IMPLEMENTATION_ID, 'original V63 execution bundle changed')
    filename = name + '.py'
    require(filename in manifest['sha256'], 'module is outside the registered V63 bundle: ' + name)
    path = SOURCE / filename
    require(sha(path) == manifest['sha256'][filename], 'original execution source bytes changed')
    if str(SOURCE) not in sys.path:
        sys.path.insert(0, str(SOURCE))
    existing = sys.modules.get(name)
    if existing is not None:
        require(Path(existing.__file__).resolve() == path, 'non-frozen module already imported: ' + name)
        return existing
    module = importlib.import_module(name)
    require(Path(module.__file__).resolve() == path, 'module did not resolve to the original frozen file')
    return module


def base_protocol():
    p = checked(SCIENTIFIC_ROOT / 'protocol/record.json')
    require(p['id'] == BASE_PROTOCOL_ID, 'scientific V63 protocol changed')
    return p
