"""Once-only archive of the reviewed 187 test directories and three caches.

The byte-bound prior engine still performs all-member backup verification,
process/Git guards, metadata rechecks and descriptor-safe removal. No formal
experiment, scientific checkpoint, worktree, GPU lease or old archive is eligible.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path

REPO = Path('/data1/zhuxinrui/projects/Data-Synthesis')
OUTPUT = REPO / 'trusted_data_synthesis/artifacts/storage_cleanup_20261019_test_tmp_01'
TEMP = REPO / 'trusted_data_synthesis/artifacts/test_tmp'
ARCHIVE = REPO / 'trusted_data_synthesis/artifacts/local_test_archive_20261019_01'
SOURCE = REPO / 'trusted_data_synthesis/artifacts/storage_cleanup_20261010_test_tmp_01/cleanup.py'
SOURCE_SHA256 = '00075258dca71ba946daeac8de641effebc01595a3e693b96e04f6566bf927d9'
SCIENCE = REPO / ('trusted_data_synthesis/artifacts/finance_research_20260928/finqa_v6_01/'
    'v18_researcher_continuation_01/v54_feedback_temperature_01/automatic_recovery_01')
CONTROL, MASTER = SCIENCE / 'signal_recovery_04', SCIENCE / 'automatic_control_watchdog_01'
CACHES = {REPO / '.ruff_cache': 8192,
    REPO / 'trusted_data_synthesis/.pytest_cache': 253952,
    REPO / 'trusted_data_synthesis/.ruff_cache': 40960}
EXPECTED_TEST_DIRECTORIES = 187
EXPECTED_ALLOCATED_BYTES = 2384310272


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def plain(path):
    return json.loads(Path(path).read_bytes())


def admitted_root(path):
    path = Path(path)
    require(path.is_absolute() and path == path.resolve() and path.is_dir(),
            'one existing canonical non-symlink candidate directory required')
    require(path.parent == TEMP or path in CACHES,
            'only direct test_tmp children and the exact three caches are authorized')
    require(path not in (REPO, TEMP, OUTPUT, ARCHIVE, SCIENCE), 'broad or scientific deletion forbidden')
    cursor = path
    while cursor != REPO:
        require(cursor.is_relative_to(REPO) and not cursor.is_symlink(), 'candidate ancestor escaped or redirected')
        cursor = cursor.parent


def protected():
    """Stat only immutable anchors; never compare changing queues or tensors' bytes."""
    paths = {REPO / 'AGENTS.md', SOURCE, Path(__file__).resolve(), SCIENCE / 'owner.lock'}
    for root in (SCIENCE.parent, SCIENCE.parent / 'recovery_01', SCIENCE, CONTROL, MASTER):
        for relative in ('protocol/record.json', 'prepared/record.json', 'implementation/record.json'):
            path = root / relative
            if path.is_file():
                paths.add(path)
        paths.update((root / 'implementation').glob('*.py'))
    for seed in (137, 251, 389):
        path = SCIENCE / f'parents/seed{seed}/record.json'
        paths.add(path)
        parent = plain(path)
        paths.add(Path(parent['task_plan']['path']))
        paths.add(Path(parent['old_outer_inputs']['path']))
        references = [parent['parent_checkpoint'], parent['old_outer_checkpoint'],
                      *parent['c1_reuse']['snapshots'].values()]
        for reference in references:
            paths.update(Path(reference['path']) / name for name in ('record.json', 'state.pt'))
        if parent['old_class_context']:
            paths.add(Path(parent['old_class_context']['path']))
    master = plain(MASTER / 'protocol/record.json')
    paths.update(Path(path) for path in master['original_lock_bindings'])
    return {str(path): ENGINE.identity(path) for path in sorted(paths)}


def runtime():
    """Observation only: concurrent scientific queues are allowed to advance."""
    snapshots, identities = {}, []
    for name, path in (
        ('control_queue', CONTROL / 'queue/status.json'),
        ('watchdog_queue', MASTER / 'queue/status.json'),
        ('cron_status', MASTER / 'cron/status.json')):
        if path.is_file():
            value = plain(path)
            snapshots[name] = {key: value[key] for key in ('status', 'phase', 'at', 'at_epoch',
                'updated_epoch', 'active_workers', 'active_jobs', 'current_episode', 'controller_attempt') if key in value}
            for key in ('active_workers', 'active_jobs'):
                if isinstance(value.get(key), list):
                    identities.extend(item for item in value[key] if isinstance(item, dict)
                                      and type(item.get('pid')) is int and item.get('birth'))
    supervisor = CONTROL / 'supervisor/launch/record.json'
    if supervisor.is_file():
        identities.append(plain(supervisor))
    return dict(observed_at=ENGINE.now(), snapshots=snapshots,
        processes=[dict(pid=item['pid'], expected_birth=item['birth'], observed_birth=ENGINE.birth(item['pid']))
                   for item in identities], dynamic_queue_equality_not_required=True,
        no_process_signal_or_experiment_action=True)


def load_engine():
    require(hashlib.sha256(SOURCE.read_bytes()).hexdigest() == SOURCE_SHA256,
            'the original archival engine bytes changed')
    spec = importlib.util.spec_from_file_location('_fixed_20261019_cleanup_engine', SOURCE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.OUTPUT = OUTPUT
    module.admitted_root = admitted_root
    module.protected = protected
    module.runtime = runtime
    # Its existing apply() binds sha(__file__) to this reviewed wrapper; the
    # original source hash is separately fixed above and in the new plan.
    module.__file__ = str(Path(__file__).resolve())
    return module


ENGINE = load_engine()


def prepare():
    require(os.getuid() == os.geteuid() == 1004, 'use the registered account, never root')
    require(not (OUTPUT / 'plan.json').exists() and not ARCHIVE.exists(), 'one fresh cleanup/archive plan only')
    children = sorted(TEMP.iterdir())
    require(len(children) == EXPECTED_TEST_DIRECTORIES and all(path.is_dir() and not path.is_symlink()
        for path in children), 'the reviewed 187 direct test directories changed; re-audit first')
    roots = [*children, *CACHES]
    ENGINE.tracked_guard(roots)
    process = ENGINE.process_guard(roots)
    rows = []
    for path in roots:
        entries = ENGINE.inventory(path)
        size = sum(row['identity'][7] for row in entries)
        if path in CACHES:
            require(size == CACHES[path], 'the reviewed cache allocation changed: ' + str(path))
        rows.append(dict(path=str(path), allocated_bytes=size, entry_count=len(entries),
            metadata_sha256=hashlib.sha256(ENGINE.encode(entries)).hexdigest()))
    require(sum(row['allocated_bytes'] for row in rows) == EXPECTED_ALLOCATED_BYTES,
            'the reviewed total allocation changed; no silent scope shrink or expansion')
    return ENGINE.publish('plan.json', dict(schema='unused_tests_recoverable_archive_plan.v1',
        at=ENGINE.now(), script_sha256=ENGINE.sha(__file__), source_engine=str(SOURCE),
        source_engine_sha256=SOURCE_SHA256, roots=rows, process_guard=process,
        source_allocated_bytes=EXPECTED_ALLOCATED_BYTES, protected_files=protected(), runtime=runtime(),
        fixed_test_directory_count=EXPECTED_TEST_DIRECTORIES, exact_cache_roots={str(k): v for k, v in CACHES.items()},
        archive_destination=str(ARCHIVE), final_archive_names=['test_fixtures.tar.gz', 'member_manifest.json.gz'],
        protected_scopes=['entire V54 temperature experiment and every recovery/control namespace',
            'all formal experiments, historical parent states, task gradients and evaluation data',
            'all GPU leases and owner locks including their original inodes',
            'all frozen source, worktrees, model assets, .venv, .git and existing cold/local archives'],
        preserve_test_tmp_parent=True, backup_must_verify_before_any_source_removal=True,
        dynamic_queue_contents_are_snapshots_not_immutable_guards=True))


def relocate_archives():
    result, verified = plain(OUTPUT / 'result.json'), plain(OUTPUT / 'backup_verified.json')
    require(result['status'] == 'COMPLETE' and result['plan_id'] == verified['plan_id'],
            'only a fully successful verified cleanup may relocate its two new archives')
    require(not ARCHIVE.exists() and ARCHIVE.parent.resolve() == OUTPUT.parent.resolve(),
            'one new same-parent archive directory required; never overwrite an archive')
    rows = []
    for name, digest_key in (('test_fixtures.tar.gz', 'archive_sha256'),
                             ('member_manifest.json.gz', 'member_manifest_sha256')):
        source = OUTPUT / name
        require(source.is_file() and not source.is_symlink() and source.stat().st_nlink == 1,
                'only the two new ordinary archive files may move')
        require(source.stat().st_dev == ARCHIVE.parent.stat().st_dev, 'archive relocation must stay on one filesystem')
        rows.append(dict(source=str(source), destination=str(ARCHIVE / name),
                         sha256=verified[digest_key], identity_before=ENGINE.identity(source)))
    ENGINE.publish('archive_relocation_intent.json', dict(at=ENGINE.now(), plan_id=result['plan_id'],
        source_result_id=result['id'], files=rows, no_old_record_rewrite=True, same_filesystem=True))
    ARCHIVE.mkdir()
    parent_descriptor = os.open(ARCHIVE.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(parent_descriptor)
    finally:
        os.close(parent_descriptor)
    for row in rows:
        source, target = Path(row['source']), Path(row['destination'])
        require(ENGINE.identity(source) == row['identity_before'] and not os.path.lexists(target),
                'archive identity or target changed before exact relocation')
        os.rename(source, target)
        after = ENGINE.identity(target)
        require(all(after[index] == row['identity_before'][index] for index in (0, 1, 2, 3, 4, 6, 7)),
                'same-filesystem relocation changed archive identity or content metadata')
        row['identity_after'] = after
    descriptor = os.open(ARCHIVE, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    ENGINE.sync_output_directory()
    return ENGINE.publish('archive_location.json', dict(at=ENGINE.now(), status='ARCHIVE_RELOCATED',
        plan_id=result['plan_id'], source_result_id=result['id'], files=rows,
        previous_result_and_backup_verified_records_unchanged=True,
        hashes_reused_from_original_complete_member_verification=True))


def apply():
    require(os.getuid() == os.geteuid() == 1004, 'use the registered account, never root')
    plan = plain(OUTPUT / 'plan.json')
    require(plan['source_engine_sha256'] == SOURCE_SHA256 and plan['source_engine'] == str(SOURCE)
            and plan['archive_destination'] == str(ARCHIVE) and not ARCHIVE.exists(),
            'bound engine or new archive destination changed')
    require(plan['source_allocated_bytes'] == EXPECTED_ALLOCATED_BYTES and len(plan['roots']) == 190,
            'fixed 187+3 source scope changed')
    result = ENGINE.apply()
    relocate_archives()
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('prepare', 'apply'))
    arguments = parser.parse_args()
    result = prepare() if arguments.action == 'prepare' else apply()
    print(json.dumps({key: result[key] for key in ('id', 'status', 'source_allocated_bytes',
        'removed_source_allocated_bytes', 'estimated_net_reclaimed_bytes') if key in result}, sort_keys=True))
