"""Focused synthetic guards for the four-wallet lossless archival wrapper."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import stat
from types import SimpleNamespace

import pytest

SOURCE = Path(__file__).resolve().parents[1] / 'scripts/storage_cleanup_20261025_wallet_snapshots.py'
spec = importlib.util.spec_from_file_location('wallet_snapshot_archive_test', SOURCE)
archive = importlib.util.module_from_spec(spec)
spec.loader.exec_module(archive)


def review():
    rows = []
    for index, relative in enumerate(sorted(archive.WALLETS)):
        path = str(archive.REPO / relative)
        rows.append(dict(path=path, eligibility='ELIGIBLE_FOR_VERIFIED_LOSSLESS_COLD_ARCHIVE_ONLY',
            blockers=[], visible_process_hits=[], sidecars_present=[], symlink=False,
            nlink=1, tracked=False, uid=1004, recorded_as_pre_registration_backup=True,
            logical_bytes=100, allocated_bytes=4096, dev=1, ino=index + 1,
            mode=stat.S_IFREG | 0o600, actual_mtime_ns=5, ctime_ns=6,
            recorded_backup=dict(path=path, bytes=100, sha256=str(index) * 64),
            creation_record=path + '.registration.json', creation_record_id='record'))
    return dict(schema='wallet_snapshot_cold_archive_eligibility_20261025.v1', status='ELIGIBLE',
        read_only=True, current_dependencies_unchanged=True,
        exact_paths=sorted(archive.WALLETS), candidates=rows)


def test_exact_four_snapshots_exclude_live_ledgers_and_path_variants():
    rows = archive.validate_review(review())
    assert len(rows) == 4 and {row['path'] for row in rows} == archive.WALLETS
    forbidden = [archive.PREFIX + 'experiment0_01/budget.sqlite3',
        archive.PREFIX + 'v17_three_task_continuation_01/wallet_before_v17.sqlite3-wal',
        '../' + sorted(archive.WALLETS)[0], '/' + sorted(archive.WALLETS)[0]]
    for path in forbidden:
        with pytest.raises(RuntimeError):
            archive.checked_relative(path)


@pytest.mark.parametrize('field,value', [('blockers', ['live']), ('sidecars_present', ['wal']),
    ('tracked', True), ('nlink', 2), ('uid', 0)])
def test_changed_or_ineligible_review_blocks_before_archival(field, value):
    data = review(); data['candidates'][0][field] = value
    with pytest.raises(RuntimeError):
        archive.validate_review(data)


def test_wallet_sidecar_is_checked_from_actual_siblings(tmp_path):
    path = tmp_path / 'wallet_before_v17.sqlite3'; path.write_bytes(b'dummy')
    archive.check_sidecars(path)
    sidecar = path.with_name(path.name + '-wal'); sidecar.touch()
    with pytest.raises(RuntimeError, match='sidecar'):
        archive.check_sidecars(path)


def test_selected_identity_or_git_tracking_change_is_rejected(monkeypatch):
    rows = archive.validate_review(review())
    monkeypatch.setattr(archive, 'configure', lambda: dict(sources=rows))
    monkeypatch.setattr(archive.engine, 'tracked_paths', lambda: set())
    by_path = {str(archive.REPO / row['path']): row['identity'] for row in rows}
    monkeypatch.setattr(archive, 'ordinary', lambda path: by_path[str(path)])
    assert archive.selected() == rows
    by_path[str(archive.REPO / rows[0]['path'])] = [99] * 8
    with pytest.raises(RuntimeError, match='identity changed'):
        archive.selected()
    monkeypatch.setattr(archive.engine, 'tracked_paths', lambda: {str(archive.REPO / rows[0]['path'])})
    with pytest.raises(RuntimeError, match='Git-tracked'):
        archive.selected()


def test_pack_requires_original_recorded_backup_digest_before_admitting_removal(tmp_path, monkeypatch):
    rows = archive.validate_review(review())
    receipt = dict(member_manifest='members.json.gz', member_manifest_sha256='manifest',
        archive=str(tmp_path / 'pack.tar.zst'), source_allocated_bytes=16384)
    monkeypatch.setattr(archive, '_original_pack', lambda group, rows: receipt)
    members = [dict(path=row['path'], sha256=row['recorded_content_sha256']) for row in rows]
    members[0]['sha256'] = 'f' * 64
    monkeypatch.setattr(archive.engine, 'load_manifest', lambda *args: members)
    with pytest.raises(RuntimeError, match='original registration'):
        archive.pack(archive.GROUP, rows)


def test_positive_gain_keeps_sources_if_archive_and_manifest_are_not_smaller():
    assert archive.positive_gain(16384, 4096, 4096) == 8192
    with pytest.raises(RuntimeError, match='positive allocated gain'):
        archive.positive_gain(8192, 4096, 4096)


def test_preserved_fixed_paths_do_not_rescan_parent_trees(tmp_path, monkeypatch):
    path = tmp_path / 'registration.json'; path.write_text('{}')
    monkeypatch.setattr(archive, '_PRESERVED', (path,))
    def forbidden(*args, **kwargs):
        raise AssertionError('no recursive source-tree census')
    monkeypatch.setattr(Path, 'rglob', forbidden)
    first = archive.preserved([])
    assert first['count'] == 1
    path.write_text('{"changed":true}')
    assert archive.preserved([]) != first


def test_restore_rejects_nonempty_or_unregistered_destination_before_content_read(tmp_path, monkeypatch):
    monkeypatch.setattr(archive, 'require_plan_bindings', lambda: {})
    monkeypatch.setattr(archive.os, 'getuid', lambda: 1004)
    monkeypatch.setattr(archive.os, 'geteuid', lambda: 1004)
    monkeypatch.setattr(archive.engine, 'GROUPS', (archive.GROUP,))
    (tmp_path / 'existing').write_text('keep')
    with pytest.raises(RuntimeError, match='empty canonical'):
        archive.restore(archive.GROUP, tmp_path)
    with pytest.raises(RuntimeError):
        archive.restore('some_other_archive', tmp_path)
    assert (tmp_path / 'existing').read_text() == 'keep'


def test_apply_attempt_is_consumed_even_on_failure_no_retry(tmp_path, monkeypatch):
    monkeypatch.setattr(archive, 'OUTPUT', tmp_path)
    monkeypatch.setattr(archive, 'require_plan_bindings', lambda: {'id': 'plan'})
    monkeypatch.setattr(archive.os, 'getuid', lambda: 1004)
    monkeypatch.setattr(archive.os, 'geteuid', lambda: 1004)
    def publish(name, body):
        path = tmp_path / name
        with path.open('x') as stream:
            json.dump(body, stream)
        return body
    monkeypatch.setattr(archive, 'publish', publish)
    calls = []
    def fail():
        calls.append(True); raise RuntimeError('synthetic pre-removal refusal')
    monkeypatch.setattr(archive.engine, 'apply', fail)
    with pytest.raises(RuntimeError, match='pre-removal'):
        archive.apply()
    with pytest.raises(RuntimeError, match='one apply attempt'):
        archive.apply()
    assert calls == [True] and (tmp_path / 'operation_failure.json').exists()
