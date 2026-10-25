"""Recoverably archive one reviewed /tmp test list, then remove proven copies."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
from types import ModuleType

import storage_cleanup_20261025_test_cache as shared

REPO = shared.REPO
TMP = Path('/tmp')
OUTPUT = shared.ART / 'storage_cleanup_20261025_tmp_tests_01'
BACKUP = shared.ART / 'local_test_archive_20261025_tmp_01'
REVIEW = Path('/tmp/cleanup_20261025_tmp_review_02.json')
TMP_NAMES = frozenset((
    'finqa-v57-controller-path-tests-GKLyv7', 'finqa-v57-controller-tests-1tZRGj',
    'finqa-v57-controller-tests-UYbia1', 'finqa-v57-controller-tests-pgIJp3',
    'finqa-v58-controller-tests-WnmMsF', 'finqa-v58-controller-tests-dCcBJy',
    'finqa-v59-controller-tests-BnQnJF', 'finqa-v59-isolation-binding-test-iyXrgy',
    'finqa-v60-lock-probe-tests-GdXbsE', 'finqa-v60-reconcile-window-test-9n1zTc',
    'finqa-v60-watchdog-audit-tests-XPKLvM', 'finqa-v60-watchdog-identity-tests-3y7xFP',
    'finqa-v60-watchdog-tests-514mSX', 'finqa-v60-watchdog-tests-7CblHY',
    'pytest-of-zhuxinrui/pytest-1998',
    'pytest-of-zhuxinrui/pytest-1999',
))
DUPLICATES = frozenset((
    '/tmp/v71_existing_mechanism_analysis_20261024.json',
    '/tmp/v72_existing_analysis_20261025.json',
    '/tmp/v72_static_audit_20261025.json',
    '/tmp/v72_static_audit_before_vendor_binding.py',
))
require = shared.require


def allowed_root(path):
    path = Path(path)
    require(path.is_absolute() and path in {TMP / name for name in TMP_NAMES},
            'only the exact reviewed test directories may be archived')
    require(path == path.resolve() and path.is_dir() and not path.is_symlink(),
            'test root must be canonical and not redirected')


def inventory(root, engine):
    allowed_root(root)
    entries = []
    device = TMP.stat().st_dev
    def visit(path):
        info = path.lstat()
        require(info.st_uid == shared.OWNER_UID and info.st_dev == device,
                'foreign owner or mount boundary must be retained')
        kind = ('directory' if stat.S_ISDIR(info.st_mode) else
                'file' if stat.S_ISREG(info.st_mode) else
                'symlink' if stat.S_ISLNK(info.st_mode) else None)
        require(kind is not None and (kind != 'file' or info.st_nlink == 1),
                'special or hardlinked test entry must be retained')
        item = dict(path=str(path.relative_to(TMP)), kind=kind, identity=engine.identity(path))
        if kind == 'symlink':
            item['target'] = os.readlink(path)
            require((path.parent / item['target']).resolve(strict=False).is_relative_to(root),
                    'test link escaped its own reviewed root')
        entries.append(item)
        if kind == 'directory':
            for child in sorted(path.iterdir()):
                visit(child)
    visit(Path(root))
    return entries


def engine_for(anchors):
    raw = shared.SOURCE.read_bytes()
    require(hashlib.sha256(raw).hexdigest() == shared.SOURCE_SHA256, 'original archive engine changed')
    engine = ModuleType('_tmp_tests_1025_original_engine')
    engine.__file__ = str(shared.SOURCE)
    exec(compile(raw, str(shared.SOURCE), 'exec'), engine.__dict__)
    engine.REPO, engine.TEMP, engine.OUTPUT = TMP, TMP, OUTPUT
    engine.admitted_root = allowed_root
    engine.inventory = lambda root: inventory(root, engine)
    def tracked_guard(roots):
        for root in roots:
            allowed_root(root)
        # All selected files are outside this repository; other Git roots are
        # synthetic fixtures already reviewed, never source working trees.
    engine.tracked_guard = tracked_guard
    engine.protected = lambda: shared.identity_snapshot(anchors)
    engine.runtime = shared.runtime_snapshot
    return engine


def reviewed_candidates():
    review = shared.plain(REVIEW)
    roots = [Path(row['root']['path']) for row in review['candidate_roots']
             if Path(row['root']['path']).is_relative_to(TMP)]
    require(set(roots) == {TMP / name for name in TMP_NAMES} and len(roots) == len(TMP_NAMES),
            'the reviewed temporary test list changed')
    duplicates = review['temporary_duplicates']
    require({row['path'] for row in duplicates} == DUPLICATES and len(duplicates) == 4,
            'only four byte-identical temporary outputs are eligible')
    return review, sorted(roots), duplicates


def duplicate_identity(path):
    value = Path(path).lstat()
    require(stat.S_ISREG(value.st_mode) and value.st_uid == shared.OWNER_UID and value.st_nlink == 1,
            'temporary output must be one ordinary owned file')
    return value


def verify_reviewed_inventory(root, rows, reviewed):
    """Reject replacement/new data using the same required inventory pass."""
    value = Path(root).lstat()
    old = reviewed['root']
    actual = (value.st_dev, value.st_ino, value.st_mode, value.st_size,
              value.st_mtime_ns, value.st_ctime_ns, value.st_nlink, value.st_uid)
    keys = ('dev', 'ino', 'mode', 'size', 'mtime_ns', 'ctime_ns', 'nlink', 'uid')
    require(actual == tuple(old[key] for key in keys), 'reviewed test root identity changed')
    require(sum(row['identity'][7] for row in rows) == reviewed['allocated_bytes']
            and sum(row['kind'] == 'file' for row in rows) == reviewed['files']
            and sum(row['kind'] == 'directory' for row in rows) == reviewed['directories']
            and sum(row['kind'] == 'symlink' for row in rows) == reviewed['symlinks']
            and max(row['identity'][4] for row in rows) == reviewed['newest_mtime_ns']
            and min(row['identity'][4] for row in rows) == reviewed['oldest_mtime_ns'],
            'reviewed test contents or allocation changed; keep them')


def remove_reviewed_alias(review):
    """Only the original dangling alias is dispensable, never a replacement."""
    alias = TMP / 'pytest-of-zhuxinrui/pytest-current'
    target = TMP / 'pytest-of-zhuxinrui/pytest-1999'
    rows = [row for row in review.get('associated_test_aliases', []) if row.get('path') == str(alias)]
    if (len(rows) != 1 or alias.parent.resolve() != alias.parent
            or os.path.lexists(target) or not alias.is_symlink()):
        return False
    row, value = rows[0], alias.lstat()
    fields = ('dev', 'ino', 'mode', 'size', 'mtime_ns', 'ctime_ns', 'uid')
    actual = (value.st_dev, value.st_ino, value.st_mode, value.st_size,
              value.st_mtime_ns, value.st_ctime_ns, value.st_uid)
    if actual != tuple(row.get(key) for key in fields):
        return False
    if os.readlink(alias) != str(target) or row.get('symlink_target') != str(target):
        return False
    alias.unlink()
    return True


def apply():
    require(not OUTPUT.exists() and not BACKUP.exists(), 'this one-shot cleanup has already been prepared')
    require(OUTPUT.resolve() == OUTPUT and BACKUP.resolve() == BACKUP,
            'audit/archive ancestor may not be redirected')
    review, roots, duplicates = reviewed_candidates()
    anchors = shared.science_anchor_paths()
    anchors += [Path(row['permanent_copy']) for row in duplicates]
    engine = engine_for(sorted(set(anchors)))
    paths = [*roots, *[Path(row['path']) for row in duplicates]]
    occupancy = engine.process_guard(paths)
    metadata = []
    reviewed_roots = {Path(row['root']['path']): row for row in review['candidate_roots']}
    for root in roots:
        rows = engine.inventory(root)
        verify_reviewed_inventory(root, rows, reviewed_roots[root])
        metadata.append(dict(path=str(root), allocated_bytes=sum(x['identity'][7] for x in rows),
            entry_count=len(rows), metadata_sha256=hashlib.sha256(engine.encode(rows)).hexdigest()))
    total = sum(row['allocated_bytes'] for row in metadata)
    require(shutil.disk_usage(shared.ART).free > 2 * total + 4 * 1024**3,
            'destination also needs the original conservative archive free-space gate')
    for row in duplicates:
        info = duplicate_identity(row['path'])
        require((info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)
                == (row['dev'], row['ino'], row['logical_bytes'], row['mtime_ns'], row['ctime_ns']),
                'reviewed temporary duplicate changed')
        require(engine.sha(row['path']) == row['source_sha256'] == row['permanent_sha256']
                == engine.sha(row['permanent_copy']), 'permanent identical content is not intact')
    OUTPUT.mkdir(mode=0o700, parents=True, exist_ok=False)
    if review.get('preflight_revision'):
        old_source = review['preflight_revision']['preflight_source']
        raw = Path(old_source['path']).read_bytes()
        require(hashlib.sha256(raw).hexdigest() == old_source['sha256'],
                'pre-removal admission source evidence changed')
        with (OUTPUT / 'source_preflight_01.py').open('xb') as stream:
            stream.write(raw); stream.flush(); os.fsync(stream.fileno())
    engine.publish('review_binding.json', dict(authorization='清理历史无用数据',
        review=shared.file_ref(REVIEW), wrapper=shared.file_ref(__file__),
        reviewed_document=review,
        shared_wrapper=shared.file_ref(shared.__file__), engine=shared.file_ref(shared.SOURCE),
        exact_roots=[str(p) for p in roots], duplicates=duplicates,
        archives_must_be_retained=True, source_filesystem_device=TMP.stat().st_dev,
        backup_filesystem_device=shared.ART.stat().st_dev))
    engine.publish('plan.json', dict(schema='unused_tests_recoverable_archive_plan.v1', at=engine.now(),
        script_sha256=engine.sha(shared.SOURCE), roots=metadata, process_guard=occupancy,
        source_allocated_bytes=total, protected_files=engine.protected(), runtime=engine.runtime(),
        preserve_test_tmp_parent=True, backup_must_verify_before_any_source_removal=True))
    result = engine.apply()
    require(result['status'] == 'COMPLETE', 'stop on incomplete temporary test cleanup')
    BACKUP.mkdir(mode=0o700, exist_ok=False)
    for directory in (BACKUP.parent, BACKUP):
        fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
        try: os.fsync(fd)
        finally: os.close(fd)
    relocated = []
    for name in ('test_fixtures.tar.gz', 'member_manifest.json.gz'):
        source, destination = OUTPUT / name, BACKUP / name
        before = engine.identity(source)
        os.rename(source, destination)
        engine.sync_output_directory()
        fd = os.open(BACKUP, os.O_RDONLY | os.O_DIRECTORY)
        try: os.fsync(fd)
        finally: os.close(fd)
        after = engine.identity(destination)
        require(all(before[i] == after[i] for i in (0,1,2,3,4,6,7)),
                'same-filesystem backup relocation changed content identity')
        relocated.append(dict(path=str(destination), sha256=engine.sha(destination), identity=before))
    fd = os.open(BACKUP, os.O_RDONLY | os.O_DIRECTORY)
    try: os.fsync(fd)
    finally: os.close(fd)
    engine.publish('archive_location.json', dict(original_result_id=result['id'], files=relocated,
        restore_relative_to='/tmp', restore_into_empty_directory_without_overwriting=True))
    final_occupancy = engine.process_guard([Path(row['path']) for row in duplicates])
    removed = []
    for row in duplicates:
        source = Path(row['path']); value = duplicate_identity(source)
        require((value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns, value.st_ctime_ns)
                == (row['dev'], row['ino'], row['logical_bytes'], row['mtime_ns'], row['ctime_ns']),
                'temporary duplicate changed before unlink')
        require(engine.sha(source) == row['source_sha256'] == engine.sha(row['permanent_copy']),
                'duplicate content changed before unlink')
        source.unlink()
        removed.append(row)
    alias_removed = remove_reviewed_alias(review)
    require(engine.protected() == shared.plain(OUTPUT / 'plan.json')['protected_files'],
            'protected scientific inputs changed')
    return engine.publish('complete.json', dict(status='COMPLETE', at=engine.now(),
        test_archive_result_id=result['id'], roots_removed=len(roots),
        tmp_test_allocated_bytes_removed=total,
        tmp_duplicate_allocated_bytes_removed=sum(row['allocated_bytes'] for row in removed),
        duplicates_removed=removed, dangling_original_test_alias_removed=alias_removed,
        final_duplicate_process_guard=final_occupancy,
        protected_files_unchanged=True, no_signals=True, no_GPU_or_API_calls=True,
        source_and_backup_on_different_filesystems=TMP.stat().st_dev != BACKUP.stat().st_dev,
        backup_and_audit_allocated_bytes=sum(p.stat().st_blocks*512 for directory in (OUTPUT,BACKUP)
                                           for p in directory.iterdir() if p.is_file())))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['apply'])
    parser.parse_args()
    value = apply()
    print(json.dumps({key: value[key] for key in ('id','status','roots_removed',
        'tmp_test_allocated_bytes_removed','tmp_duplicate_allocated_bytes_removed')}, ensure_ascii=False))
