"""Three synthetic checks of the fixed /tmp wrapper, not a live cleanup."""
import hashlib
import json
import os
from pathlib import Path
import stat
import sys
import tarfile

import pytest

SCRIPTS = str(Path(__file__).resolve().parents[1] / 'scripts')
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)
import storage_cleanup_20261025_tmp_tests as cleanup


def configure(tmp_path, monkeypatch):
    scratch = tmp_path/'scratch'
    data = tmp_path/'data'
    case = scratch/'case'
    case.mkdir(parents=True); data.mkdir()
    sentinel = data/'protected.txt'
    sentinel.write_text('immutable source anchor')
    for name, value in dict(TMP=scratch, OUTPUT=data/'audit', BACKUP=data/'backup',
                            TMP_NAMES=frozenset({'case'}), REVIEW=data/'review.json').items():
        monkeypatch.setattr(cleanup, name, value)
    monkeypatch.setattr(cleanup.shared, 'ART', data)
    monkeypatch.setattr(cleanup.shared, 'science_anchor_paths', lambda: [sentinel])
    monkeypatch.setattr(cleanup.shared, 'runtime_snapshot', lambda: dict(status='COMPLETE', no_signals=True))
    original_engine_for = cleanup.engine_for
    def factory(anchors):
        value = original_engine_for(anchors)
        value.process_guard = lambda _: dict(hits=[], synthetic=True)
        return value
    monkeypatch.setattr(cleanup, 'engine_for', factory)
    return scratch, data, case, sentinel


def test_no_broad_root_unreviewed_root_or_escape_symlink(tmp_path, monkeypatch):
    scratch, data, case, sentinel = configure(tmp_path, monkeypatch)
    engine = cleanup.engine_for([sentinel])
    cleanup.allowed_root(case)
    for path in (scratch, data, scratch/'other'):
        path.mkdir(exist_ok=True)
        with pytest.raises(RuntimeError, match='exact reviewed'):
            cleanup.allowed_root(path)
    (case/'escape').symlink_to(sentinel)
    with pytest.raises(RuntimeError, match='escaped'):
        cleanup.inventory(case, engine)


def test_real_tiny_backup_is_verified_before_deletion_and_permanent_copies_survive(tmp_path, monkeypatch):
    scratch, data, case, sentinel = configure(tmp_path, monkeypatch)
    (case/'payload.txt').write_bytes(b'fixture content remains recoverable\n')
    (case/'inside').symlink_to(case/'payload.txt')
    duplicates = []
    for index in range(4):
        source, permanent = scratch/f'duplicate{index}.json', data/f'permanent{index}.json'
        raw = ('unique proof '+str(index)).encode()
        source.write_bytes(raw); permanent.write_bytes(raw)
        info = source.lstat(); digest = hashlib.sha256(raw).hexdigest()
        duplicates.append(dict(path=str(source), permanent_copy=str(permanent),
            dev=info.st_dev, ino=info.st_ino, logical_bytes=info.st_size,
            mtime_ns=info.st_mtime_ns, ctime_ns=info.st_ctime_ns,
            allocated_bytes=info.st_blocks*512, source_sha256=digest, permanent_sha256=digest))
    monkeypatch.setattr(cleanup, 'DUPLICATES', frozenset(row['path'] for row in duplicates))
    entries = cleanup.inventory(case, cleanup.engine_for([sentinel]))
    info = case.lstat()
    reviewed = dict(root=dict(path=str(case),dev=info.st_dev,ino=info.st_ino,mode=info.st_mode,
        size=info.st_size,mtime_ns=info.st_mtime_ns,ctime_ns=info.st_ctime_ns,
        nlink=info.st_nlink,uid=info.st_uid),
        allocated_bytes=sum(row['identity'][7] for row in entries),
        files=sum(row['kind']=='file' for row in entries),
        directories=sum(row['kind']=='directory' for row in entries),
        symlinks=sum(row['kind']=='symlink' for row in entries),
        newest_mtime_ns=max(row['identity'][4] for row in entries),
        oldest_mtime_ns=min(row['identity'][4] for row in entries))
    # The guard must reject a reviewed count drift before producing a plan.
    with pytest.raises(RuntimeError, match='contents or allocation changed'):
        cleanup.verify_reviewed_inventory(case,entries,dict(reviewed,files=reviewed['files']+1))
    cleanup.REVIEW.write_text(json.dumps(dict(candidate_roots=[reviewed],
        temporary_duplicates=duplicates, associated_test_aliases=[])))
    original_remove = cleanup.shutil.rmtree
    checked = []
    def verified_remove(path, *args, **kwargs):
        proof = json.loads((cleanup.OUTPUT/'backup_verified.json').read_text())
        assert proof['all_regular_files_content_verified'] and proof['verified_members'] == 3
        checked.append(str(path))
        return original_remove(path, *args, **kwargs)
    verified_remove.avoids_symlink_attacks = original_remove.avoids_symlink_attacks
    monkeypatch.setattr(cleanup.shutil, 'rmtree', verified_remove)
    result = cleanup.apply()
    assert result['status'] == 'COMPLETE' and checked == [str(case)] and not case.exists()
    assert sentinel.read_text() == 'immutable source anchor'
    for row in duplicates:
        assert not Path(row['path']).exists()
        assert hashlib.sha256(Path(row['permanent_copy']).read_bytes()).hexdigest() == row['permanent_sha256']
    with tarfile.open(cleanup.BACKUP/'test_fixtures.tar.gz', 'r:gz') as archive:
        assert archive.extractfile('case/payload.txt').read() == b'fixture content remains recoverable\n'
    assert stat.S_IMODE(cleanup.BACKUP.stat().st_mode) == 0o700
    with pytest.raises(RuntimeError, match='already been prepared'):
        cleanup.apply()


def test_replaced_alias_or_recreated_target_is_retained(tmp_path, monkeypatch):
    scratch = tmp_path/'scratch'
    parent = scratch/'pytest-of-zhuxinrui'; parent.mkdir(parents=True)
    monkeypatch.setattr(cleanup, 'TMP', scratch)
    target, alias = parent/'pytest-1999', parent/'pytest-current'
    alias.symlink_to(target)
    def record():
        value = alias.lstat()
        return dict(path=str(alias),dev=value.st_dev,ino=value.st_ino,mode=value.st_mode,
            size=value.st_size,mtime_ns=value.st_mtime_ns,ctime_ns=value.st_ctime_ns,
            uid=value.st_uid,symlink_target=str(target))
    review = dict(associated_test_aliases=[record()])
    alias.rename(parent/'original-alias-retained-for-test')
    alias.symlink_to(target)
    assert not cleanup.remove_reviewed_alias(review) and alias.is_symlink()
    review = dict(associated_test_aliases=[record()])
    target.mkdir()
    assert not cleanup.remove_reviewed_alias(review) and alias.is_symlink()
    target.rmdir()
    assert cleanup.remove_reviewed_alias(review) and not os.path.lexists(alias)
