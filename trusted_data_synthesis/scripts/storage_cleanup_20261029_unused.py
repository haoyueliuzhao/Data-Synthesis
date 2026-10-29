"""One reviewed cleanup: verified test archive and regenerable probe samples.

No scientific directory is removable. The byte-bound 2026-10-10 archive engine
verifies every member before removing any test root. Its backup stays here.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
from types import ModuleType

REPO = Path('/data1/zhuxinrui/projects/Data-Synthesis')
ART = REPO / 'trusted_data_synthesis/artifacts'
OUTPUT = ART / 'storage_cleanup_20261029_unused_01'
REVIEW = Path('/tmp/storage_cleanup_20261029_candidates.json')
SOURCE = ART / 'storage_cleanup_20261010_test_tmp_01/cleanup.py'
SOURCE_SHA256 = '00075258dca71ba946daeac8de641effebc01595a3e693b96e04f6566bf927d9'
OWNER_UID = 1004
SCIENCE = ART / ('finance_research_20260928/finqa_v6_01/v18_researcher_continuation_01/'
                 'v76_fixed_demonstration_closed_loop_01/execution_revision_03')
ROOTS = frozenset({
    REPO / 'trusted_data_synthesis/.pytest_cache',
    REPO / 'trusted_data_synthesis/scripts/__pycache__',
    REPO / 'trusted_data_synthesis/tests/__pycache__',
    Path('/tmp/pytest-of-zhuxinrui/pytest-2041'),
    Path('/tmp/pytest-of-zhuxinrui/pytest-2042'),
    Path('/tmp/pytest-of-zhuxinrui/pytest-2043'),
})
PROBE = Path('/tmp/v76_storage_delta_probe_20261029')
SAMPLES = frozenset(PROBE / name for name in (
    '0.ordinary.zst', '1.ordinary.zst', '2.ordinary.zst', '1.xor.zst', '2.xor.zst'))
PROBE_SOURCE = Path('/tmp/v76_storage_readonly_probe.py')
OLD_TRAIN = ART / ('finance_research_20260928/finqa_v6_01/v18_researcher_continuation_01/'
                   'v54_feedback_temperature_01/automatic_recovery_01/branches/seed137/Hold/training')
ORIGINAL_STATES = frozenset(OLD_TRAIN / f'step{step:04d}_step/state.pt' for step in (597, 598, 599))


def require(value, message):
    if not value:
        raise RuntimeError(message)


def plain(path):
    return json.loads(Path(path).read_bytes())


def metadata(path):
    path = Path(path)
    s = path.lstat()
    value = dict(path=str(path), device=s.st_dev, inode=s.st_ino, mode=s.st_mode,
                 uid=s.st_uid, gid=s.st_gid, nlink=s.st_nlink, size=s.st_size,
                 allocated_bytes=s.st_blocks * 512, mtime_ns=s.st_mtime_ns,
                 ctime_ns=s.st_ctime_ns)
    if stat.S_ISLNK(s.st_mode):
        value['link_target'] = os.readlink(path)
    return value


def allowed_root(path):
    path = Path(path)
    require(path in ROOTS, 'only the exact reviewed test/cache roots are eligible')
    require(path.is_absolute() and path == path.resolve() and path.is_dir()
            and not path.is_symlink(), 'test root must be canonical and not redirected')


def inventory(root, engine):
    root = Path(root)
    allowed_root(root)
    device, rows = root.lstat().st_dev, []

    def visit(path):
        value = path.lstat()
        require(value.st_uid == OWNER_UID and value.st_dev == device,
                'foreign owner or mount boundary must be retained')
        kind = ('directory' if stat.S_ISDIR(value.st_mode) else
                'file' if stat.S_ISREG(value.st_mode) else
                'symlink' if stat.S_ISLNK(value.st_mode) else None)
        require(kind is not None and (kind != 'file' or value.st_nlink == 1),
                'special or hardlinked test entry must be retained')
        row = dict(path=str(path.relative_to('/')), kind=kind, identity=engine.identity(path))
        if kind == 'symlink':
            row['target'] = os.readlink(path)
            require((path.parent / row['target']).resolve(strict=False).is_relative_to(root),
                    'test symlink escaped its exact root')
        rows.append(row)
        if kind == 'directory':
            for child in sorted(path.iterdir()):
                visit(child)

    visit(root)
    return rows


def tracked_guard(roots):
    for root in roots:
        allowed_root(root)
    inside = [str(path.relative_to(REPO)) for path in roots if path.is_relative_to(REPO)]
    if inside:
        tracked = subprocess.check_output(['git', '-C', str(REPO), 'ls-files', '-z', '--', *inside],
                                          env={**os.environ, 'GIT_OPTIONAL_LOCKS': '0'})
        require(not tracked, 'Git-tracked content must be retained')


def science_anchors():
    protocol = plain(SCIENCE / 'protocol/record.json')
    implementation = plain(SCIENCE / 'implementation/record.json')
    paths = {SOURCE, REPO / 'AGENTS.md', PROBE / 'record.json', PROBE_SOURCE}
    paths.update(ORIGINAL_STATES)
    paths.update(path.parent / 'record.json' for path in ORIGINAL_STATES)
    for relative in ('protocol/record.json', 'implementation/record.json', 'prepared/record.json',
                     'owner.lock', 'supervisor/owner.lock', 'activation/owner.lock'):
        path = SCIENCE / relative
        if path.is_file():
            paths.add(path)
    paths.update((SCIENCE / 'implementation').glob('*.py'))
    paths.update(map(Path, implementation['source_bindings']))
    paths.update(Path(protocol['gpu_lease_root']).glob('*.lock'))
    return sorted(paths)


def runtime_snapshot(engine):
    snapshots, identities = {}, {}
    for label, relative in [('queue', 'queue/status.json'),
                            ('supervisor_queue', 'supervisor/queue/status.json'),
                            ('closeout', 'closeout/record.json'),
                            ('supervisor_launch', 'supervisor/launch/record.json')]:
        path = SCIENCE / relative
        if not path.is_file():
            continue
        value = plain(path)
        snapshots[label] = {key: value[key] for key in ('status', 'updated_epoch', 'accepted_jobs',
                            'active_workers', 'pid', 'birth') if key in value}
        children = value.get('active_workers', [])
        for item in [value, *(children if isinstance(children, list) else [])]:
            if type(item.get('pid')) is int and item.get('birth'):
                identities[item['pid']] = item['birth']
    return dict(observed_at=engine.now(), snapshots=snapshots,
                processes=[dict(pid=pid, expected_birth=birth, observed_birth=engine.birth(pid))
                           for pid, birth in sorted(identities.items())],
                dynamic_queue_equality_not_required=True, no_process_signals=True)


def engine_for(anchors):
    raw = SOURCE.read_bytes()
    require(hashlib.sha256(raw).hexdigest() == SOURCE_SHA256, 'original archive engine changed')
    engine = ModuleType('_fixed_unused_20261029_archive_engine')
    engine.__file__ = str(Path(__file__).resolve())
    exec(compile(raw, str(SOURCE), 'exec'), engine.__dict__)
    engine.REPO, engine.OUTPUT = Path('/'), OUTPUT
    engine.admitted_root = allowed_root
    engine.inventory = lambda root: inventory(root, engine)
    engine.tracked_guard = tracked_guard
    engine.protected = lambda: {str(p): engine.identity(p) for p in sorted(map(Path, anchors))}
    engine.runtime = lambda: runtime_snapshot(engine)
    return engine


def validate_review(review, engine):
    require(review['schema'] == 'bounded_readonly_cleanup_candidate_audit.v1', 'unknown review schema')
    roots = review['directory_candidates']
    samples = review['file_candidates']
    require(len(roots) == len(ROOTS) and {Path(row['root']) for row in roots} == ROOTS,
            'review changed the exact test/cache root list')
    require(len(samples) == len(SAMPLES)
            and {Path(row['metadata']['path']) for row in samples} == SAMPLES,
            'review changed the exact regenerable sample list')
    inventories = {}
    for row in roots:
        current = inventory(Path(row['root']), engine)
        observed = {str(Path('/') / item['path']): metadata(Path('/') / item['path']) for item in current}
        prior = {item['path']: item for item in row['members']}
        require(len(prior) == len(row['members']) and observed == prior,
                'reviewed test identity or contents changed; retain the source')
        require(row['metadata'] == prior[row['root']]
                and row['allocated_bytes'] == sum(item['identity'][7] for item in current),
                'reviewed allocation/root metadata changed')
        inventories[Path(row['root'])] = current
    validate_samples(review)
    return inventories


def validate_samples(review):
    samples = review['file_candidates']
    require(len(samples) == len(SAMPLES)
            and {Path(row['metadata']['path']) for row in samples} == SAMPLES,
            'only the exact regenerable sample list is eligible')
    for row in samples:
        old = row['metadata']
        path = Path(old['path'])
        require(path == path.resolve() and metadata(path) == old,
                'reviewed sample identity changed; retain it')
        require(stat.S_ISREG(old['mode']) and old['uid'] == OWNER_UID and old['nlink'] == 1,
                'sample must be one ordinary owned file')
    sources = review['storage_probe_originals']
    require(len(sources) == len(ORIGINAL_STATES)
            and {Path(row['state']['path']) for row in sources} == ORIGINAL_STATES,
            'only the three original probe checkpoints are valid regeneration sources')
    probe = plain(PROBE / 'record.json')
    original_sha = {row['path']: row['sha256'] for row in probe['sample']}
    require(set(map(Path, original_sha)) == ORIGINAL_STATES, 'probe source list changed')
    for row in sources:
        state, record = Path(row['state']['path']), Path(row['record']['path'])
        require(record == state.parent / 'record.json'
                and metadata(state) == row['state'] and metadata(record) == row['record'],
                'original checkpoint or record identity changed')
        require(plain(record)['state_sha256'] == row['registered_state_sha256']
                == row['sample_record_sha256'] == original_sha[str(state)],
                'registered original SHA differs; retain the probe samples')
    require(PROBE_SOURCE.is_file(), 'preserve the probe producer before removing samples')


def prepare():
    require(os.getuid() == os.geteuid() == OWNER_UID, 'registered account required')
    require(not OUTPUT.exists() and OUTPUT.resolve() == OUTPUT, 'one fresh canonical cleanup directory only')
    review = plain(REVIEW)
    engine = engine_for([])
    inventories = validate_review(review, engine)
    roots = sorted(ROOTS)
    tracked_guard(roots)
    processes = engine.process_guard([*roots, *sorted(SAMPLES)])
    entries = [(root, inventories[root]) for root in roots]
    rows = [dict(path=str(root), allocated_bytes=sum(x['identity'][7] for x in values),
                 entry_count=len(values), metadata_sha256=hashlib.sha256(engine.encode(values)).hexdigest())
            for root, values in entries]
    total = sum(row['allocated_bytes'] for row in rows)
    require(shutil.disk_usage(ART).free > 2 * total + 4 * 1024**3,
            'archive destination lacks the original conservative free-space reserve')
    OUTPUT.mkdir(mode=0o700, parents=True, exist_ok=False)
    for name, raw in [('cleanup.py', Path(__file__).read_bytes()), ('review.json', REVIEW.read_bytes())]:
        with (OUTPUT / name).open('xb') as stream:
            stream.write(raw); stream.flush(); os.fsync(stream.fileno())
    anchors = sorted(set(science_anchors()) | {OUTPUT / 'cleanup.py', OUTPUT / 'review.json'})
    engine = engine_for(anchors)
    return engine.publish('plan.json', dict(schema='unused_tests_recoverable_archive_plan.v1',
        at=engine.now(), authorization='清理历史无用数据', script_sha256=engine.sha(__file__),
        original_archive_engine_sha256=SOURCE_SHA256, review_sha256=engine.sha(OUTPUT / 'review.json'),
        roots=rows, source_allocated_bytes=total, process_guard=processes,
        protected_files=engine.protected(), runtime=engine.runtime(),
        exact_regenerable_samples=[row['metadata'] for row in review['file_candidates']],
        backup_must_verify_before_any_source_removal=True,
        restore_relative_to='/', restore_requires_empty_isolated_destination_and_manifest_review=True,
        probe_samples_are_regenerable_not_byte_identical_backups=True))


def apply():
    require(os.getuid() == os.geteuid() == OWNER_UID, 'registered account required')
    plan = plain(OUTPUT / 'plan.json')
    engine = engine_for(plan['protected_files'])
    require(not (OUTPUT / 'wrapper_execution_intent.json').exists(), 'no automatic cleanup retry')
    require(plan['id'] == hashlib.sha256(engine.encode({k: v for k, v in plan.items() if k != 'id'})).hexdigest(),
            'plan changed')
    require(engine.sha(__file__) == plan['script_sha256']
            and engine.sha(OUTPUT / 'review.json') == plan['review_sha256'], 'frozen source or review changed')
    review = plain(OUTPUT / 'review.json')
    require(len(plan['roots']) == len(ROOTS)
            and {Path(row['path']) for row in plan['roots']} == ROOTS, 'planned root list changed')
    validate_samples(review)
    require(engine.protected() == plan['protected_files'], 'protected sources changed before cleanup')
    require(shutil.disk_usage(OUTPUT).free > 2 * plan['source_allocated_bytes'] + 4 * 1024**3,
            'archive destination lacks required space')
    occupancy = engine.process_guard([*sorted(ROOTS), *sorted(SAMPLES)])
    engine.publish('wrapper_execution_intent.json', dict(at=engine.now(), plan_id=plan['id'],
                   process_guard=occupancy, no_automatic_retry=True))
    removed_samples, archive_result, failure = [], None, None
    try:
        archive_result = engine.apply()
        require(archive_result['status'] == 'COMPLETE', 'test archive cleanup did not complete')
        validate_samples(review)
        engine.process_guard(sorted(SAMPLES))
        require(engine.protected() == plan['protected_files'], 'protected sources changed before sample removal')
        for row in review['file_candidates']:
            old = row['metadata']
            require(metadata(old['path']) == old, 'sample changed immediately before unlink')
            Path(old['path']).unlink()
            removed_samples.append(old)
        fd = os.open(PROBE, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
        require(engine.protected() == plan['protected_files'], 'protected sources changed during cleanup')
    except BaseException as exc:
        failure = dict(type=type(exc).__name__, message=str(exc))
        raise
    finally:
        actual_archive = archive_result
        if actual_archive is None and (OUTPUT / 'result.json').is_file():
            actual_archive = plain(OUTPUT / 'result.json')
        removed = (actual_archive or {}).get('removed_roots', [])
        devices = {}
        reviewed = {row['root']: row for row in review['directory_candidates']}
        for row in removed:
            key = str(reviewed[row['path']]['metadata']['device'])
            devices[key] = devices.get(key, 0) + row['allocated_bytes']
        for row in removed_samples:
            key = str(row['device'])
            devices[key] = devices.get(key, 0) + row['allocated_bytes']
        output_device = str(OUTPUT.stat().st_dev)
        backup_bytes = sum(p.lstat().st_blocks * 512 for p in OUTPUT.iterdir() if p.is_file())
        net = dict(devices)
        net[output_device] = net.get(output_device, 0) - backup_bytes
        engine.publish('complete.json', dict(at=engine.now(),
            status='COMPLETE' if failure is None else 'PARTIAL_STOPPED_NO_RETRY', failure=failure,
            archive_result_id=(actual_archive or {}).get('id'), roots_removed=len(removed),
            samples_removed=removed_samples, source_removed_allocated_bytes_by_device=devices,
            backup_and_audit_device=output_device, backup_and_audit_allocated_bytes=backup_bytes,
            estimated_net_reclaimed_bytes_by_device=net,
            net_excludes_this_final_small_record_and_directory_metadata=True,
            archive_retained_at=str(OUTPUT / 'test_fixtures.tar.gz'),
            no_process_signals=True, no_GPU_or_API_calls=True, runtime_after=engine.runtime(),
            protected_files_unchanged=engine.protected() == plan['protected_files']))
    return plain(OUTPUT / 'complete.json')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['prepare', 'apply'])
    args = parser.parse_args()
    result = prepare() if args.action == 'prepare' else apply()
    print(json.dumps({key: result[key] for key in ('id', 'status', 'roots_removed',
          'source_allocated_bytes', 'estimated_net_reclaimed_bytes_by_device') if key in result},
          ensure_ascii=False))
