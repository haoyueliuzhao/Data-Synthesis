"""Small synthetic checks; no real cleanup plan or scientific files touched."""
import hashlib
import json
import os
from pathlib import Path
import sys
import subprocess
import tarfile

import pytest

SCRIPTS = str(Path(__file__).resolve().parents[1] / 'scripts')
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)
import storage_cleanup_20261025_test_cache as cleanup


@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    repo = tmp_path / 'repo'
    art = repo / 'trusted_data_synthesis/artifacts'
    test_tmp = art / 'test_tmp'
    root = test_tmp / 'case'
    root.mkdir(parents=True)
    subprocess.run(['git', 'init', '-q', str(repo)], check=True)
    sentinel = repo / 'protected.txt'
    sentinel.write_text('must remain')
    for name, value in dict(REPO=repo, ART=art, TEMP=test_tmp,
            OUTPUT=art/'new-audit', ARCHIVE=art/'local_test_archive_new',
            SCIENCE=art/'science', OWNER_UID=os.getuid(), TEST_CHILD_NAMES=frozenset({'case'}),
            _ANCHORS=None).items():
        monkeypatch.setattr(cleanup, name, value)
    engine = cleanup.load_engine()
    monkeypatch.setattr(cleanup, 'ENGINE', engine)
    guard_calls = []
    def process_guard(roots):
        guard_calls.append([str(path) for path in roots])
        return dict(hits=[], inspected_same_account_processes=0, synthetic=True)
    monkeypatch.setattr(cleanup, 'process_guard', process_guard)
    monkeypatch.setattr(engine, 'process_guard', process_guard)
    monkeypatch.setattr(cleanup, 'science_anchor_paths', lambda: [sentinel])
    protection = repo / 'protection.json'
    protection.write_text(json.dumps(dict(conservative_protected_roots=[dict(path=str(cleanup.SCIENCE))])))
    return repo, root, sentinel, protection, guard_calls


def scope_for(root, protection):
    scope = protection.with_name('scope.json')
    entries = cleanup.ENGINE.inventory(root)
    value = dict(schema=cleanup.SCOPE_SCHEMA, authorization=cleanup.AUTHORIZATION,
        roots=[str(root)], source_allocated_bytes_from_read_only_inventory=sum(row['identity'][7] for row in entries))
    scope.write_text(json.dumps(value))
    return scope


def test_scope_refuses_broad_unreviewed_and_protected_roots(sandbox):
    repo, root, _, protection, _ = sandbox
    value = dict(schema=cleanup.SCOPE_SCHEMA, authorization=cleanup.AUTHORIZATION, roots=[str(root)])
    assert cleanup.validate_scope(value, cleanup.plain(protection)) == [root]
    for path in [repo, cleanup.TEMP, cleanup.SCIENCE, repo/'trusted_data_synthesis/.venv', cleanup.TEMP/'new-unreviewed']:
        path.mkdir(parents=True, exist_ok=True)
        with pytest.raises(RuntimeError):
            cleanup.validate_scope(dict(value, roots=[str(path)]), cleanup.plain(protection))
    with pytest.raises(RuntimeError, match='protected'):
        cleanup.validate_scope(value, dict(conservative_protected_roots=[dict(path=str(root))]))


def test_inventory_rejects_escape_link_and_hardlink(sandbox):
    repo, root, sentinel, _, _ = sandbox
    escape = root/'escape'
    escape.symlink_to(sentinel)
    with pytest.raises(RuntimeError, match='escapes'):
        cleanup.ENGINE.inventory(root)
    escape.unlink()
    (root/'data').write_text('test')
    os.link(root/'data', root/'alias')
    with pytest.raises(RuntimeError, match='hardlinked'):
        cleanup.ENGINE.inventory(root)


def test_verified_archive_relocates_without_rewriting_old_result_and_cannot_reapply(sandbox):
    _, root, sentinel, protection, guards = sandbox
    payload = root/'data.txt'
    payload.write_bytes(b'complete fixture bytes\n')
    (root/'inside').symlink_to(payload)
    scope = scope_for(root, protection)
    plan = cleanup.prepare(scope, protection)
    result = cleanup.apply()
    assert result['status'] == 'COMPLETE' and not root.exists()
    assert sentinel.read_text() == 'must remain'
    location = cleanup.plain(cleanup.OUTPUT/'archive_location.json')
    assert location['source_result_id'] == result['id']
    assert result['archive'] != location['files'][0]['destination']
    assert cleanup.plain(cleanup.OUTPUT/'result.json') == result
    archive = cleanup.ARCHIVE/'test_fixtures.tar.gz'
    with tarfile.open(archive, 'r:gz') as stream:
        member = stream.getmember(str(payload.relative_to(cleanup.REPO)))
        assert stream.extractfile(member).read() == b'complete fixture bytes\n'
    assert hashlib.sha256(archive.read_bytes()).hexdigest() == result['archive_sha256']
    assert cleanup.status()['removed_source_allocated_bytes'] == plan['source_allocated_bytes']
    assert len(guards) >= 3
    with pytest.raises(RuntimeError):
        cleanup.apply()


def test_change_after_plan_keeps_source_and_never_starts_removal(sandbox):
    _, root, _, protection, _ = sandbox
    payload = root/'data'
    payload.write_text('old')
    cleanup.prepare(scope_for(root, protection), protection)
    payload.write_text('changed content')
    with pytest.raises(RuntimeError, match='changed after planning'):
        cleanup.apply()
    assert payload.read_text() == 'changed content'
    assert not (cleanup.OUTPUT/'execution_intent.json').exists()


def test_runtime_allows_natural_completion_and_preserves_fixed_anchor_set(sandbox, monkeypatch):
    _, root, sentinel, protection, _ = sandbox
    cleanup.prepare(scope_for(root, protection), protection)
    before = cleanup.protected()
    queue = cleanup.SCIENCE/'queue/status.json'
    queue.parent.mkdir(parents=True)
    queue.write_text(json.dumps(dict(status='RUNNING', active_workers=[dict(pid=123,birth='x',job_id='job')])))
    monkeypatch.setattr(cleanup.ENGINE, 'birth', lambda _: 'x')
    assert cleanup.runtime_snapshot()['processes'][0]['same_live_identity']
    queue.write_text(json.dumps(dict(status='COMPLETE',active_workers=[])))
    closeout = cleanup.SCIENCE/'closeout/record.json'
    closeout.parent.mkdir(); closeout.write_text(json.dumps(dict(status='COMPLETE')))
    assert cleanup.runtime_snapshot()['snapshots']['scientific_closeout']['status'] == 'COMPLETE'
    assert cleanup.protected() == before and str(sentinel) in before


def test_changed_original_engine_is_never_executed(tmp_path, monkeypatch):
    path = tmp_path/'wrong.py'
    path.write_text('raise AssertionError("must never execute")')
    monkeypatch.setattr(cleanup, 'SOURCE', path)
    with pytest.raises(RuntimeError, match='engine bytes changed'):
        cleanup.load_engine()
