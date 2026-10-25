"""One bounded, recoverable archive of reviewed project tests and caches.

The original byte-bound engine verifies every archive member before removing
any source. No historical apply plan or scientific directory is eligible.
Shared protection helpers are observational and independent of this test plan.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
from types import FunctionType, ModuleType

REPO = Path('/data1/zhuxinrui/projects/Data-Synthesis')
ART = REPO / 'trusted_data_synthesis/artifacts'
TEMP = ART / 'test_tmp'
OUTPUT = ART / 'storage_cleanup_20261025_test_cache_01'
ARCHIVE = ART / 'local_test_archive_20261025_01'
SOURCE = ART / 'storage_cleanup_20261010_test_tmp_01/cleanup.py'
SOURCE_SHA256 = '00075258dca71ba946daeac8de641effebc01595a3e693b96e04f6566bf927d9'
SCIENCE = ART / 'finance_research_20260928/finqa_v6_01/v18_researcher_continuation_01/v72_low_lr_continuation_01'
PROTECTION_DEFAULT = Path('/tmp/cleanup_20261025_protection.json')
OWNER_UID = 1004
SCOPE_SCHEMA = 'project_test_cache_cleanup_scope.v1'
AUTHORIZATION = '清理历史无用数据'
CACHE_RELATIVE = (
    'trusted_data_synthesis/.mypy_cache',
    'trusted_data_synthesis/.pytest_cache',
    'trusted_data_synthesis/scripts/__pycache__',
    'trusted_data_synthesis/tests/__pycache__',
)
TEST_CHILD_NAMES = frozenset((
    'v61-control-hNyhby', 'v61-registration-1RpOEG',
    'v62-control-PLktqG', 'v62-registration-WWK6pR',
    'v63-diagnostics-barrier-20261020', 'v63-diagnostics-draw-fields-20261020',
    'v63-diagnostics-iTV8zN', 'v63-registration-delta.Ktx98d',
    'v63-registration.g07Ex9', 'v63-runtime-training.JfLNL2',
    'v65-final-tmTGIY', 'v65-generation.7Fmv8o', 'v65-integrated-jwfYBL',
    'v67-integrated-gllc5v', 'v67-registration-GYwktx',
    'v68-integration-BPxBGZ', 'v69-integration-G1mzLM',
    'v70-registration-58imVi', 'v70-report-summary-ztg6jc',
))
_ANCHORS = None


def require(value, message):
    if not value:
        raise RuntimeError(message)


def plain(path):
    return json.loads(Path(path).read_bytes())


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def file_ref(path):
    return dict(path=str(Path(path).resolve()), sha256=sha(path))


def identity_snapshot(paths):
    """Stat only the caller's fixed path set, never scientific Tensor bytes."""
    return {str(Path(path)): ENGINE.identity(path) for path in sorted(map(Path, paths))}


def _record_paths(value):
    if isinstance(value, dict):
        for key, item in value.items():
            if key == 'path' and isinstance(item, str) and Path(item).is_absolute():
                path = Path(item)
                if path.is_file():
                    yield path
                elif path.is_dir():
                    for name in ('record.json', 'state.pt'):
                        if (path / name).is_file():
                            yield path / name
            else:
                yield from _record_paths(item)
    elif isinstance(value, list):
        for item in value:
            yield from _record_paths(item)


def science_anchor_paths():
    """Capture current immutable V72 inputs; caller must preserve this set."""
    protocol = plain(SCIENCE / 'protocol/record.json')
    implementation = plain(SCIENCE / 'implementation/record.json')
    paths = {REPO / 'AGENTS.md', SOURCE}
    for relative in ('protocol/record.json', 'prepared/record.json',
                     'implementation/record.json', 'points/step1192/context/record.json',
                     'static_supervision_audit/record.json', 'existing_analysis/record.json',
                     'existing_analysis/producer.py', 'owner.lock', 'supervisor/owner.lock'):
        path = SCIENCE / relative
        if path.is_file():
            paths.add(path)
    paths.update((SCIENCE / 'implementation').glob('*.py'))
    paths.update(Path(path) for path in implementation['source_bindings'])
    paths.update(_record_paths(implementation['historical_manifests']))
    for key in ('initial_parent', 'baseline_evaluation', 'parent_evaluation',
                'high_lr_evaluation', 'evaluation_source_registration',
                'old_evaluation_registration', 'source_scientific_protocol'):
        paths.update(_record_paths(protocol[key]))
    for name in ('step1192_lr_intervention', 'step1490_step'):
        for leaf in ('record.json', 'state.pt'):
            path = SCIENCE / 'training' / name / leaf
            if path.is_file():
                paths.add(path)
    lease_root = Path(protocol['gpu_lease_root'])
    paths.update(lease_root.glob('*.lock'))
    # Small immutable manifests and actual endpoint tensors are stat-only.
    return sorted(paths)


def runtime_snapshot():
    """Observe natural progress/completion; never stop or signal a process."""
    snapshots, identities = {}, {}
    for label, relative in (
        ('queue', 'queue/status.json'), ('supervisor_queue', 'supervisor/queue/status.json'),
        ('scientific_closeout', 'closeout/record.json'),
        ('supervisor_closeout', 'supervisor/closeout/record.json'),
    ):
        path = SCIENCE / relative
        if not path.is_file():
            continue
        row = plain(path)
        snapshots[label] = {key: row[key] for key in ('status', 'updated_epoch',
            'finished_epoch', 'active_workers', 'accepted_jobs', 'controller_attempt') if key in row}
        for child in row.get('active_workers', []) if isinstance(row.get('active_workers'), list) else []:
            if type(child.get('pid')) is int and child.get('birth'):
                identities[(child['pid'], child['birth'])] = child.get('job_id', 'worker')
        if type(row.get('pid')) is int and row.get('birth'):
            identities[(row['pid'], row['birth'])] = label
    path = SCIENCE / 'supervisor/launch/record.json'
    if path.is_file():
        row = plain(path)
        identities[(row['pid'], row['birth'])] = 'supervisor'
    processes = []
    for (pid, expected), role in sorted(identities.items()):
        observed = ENGINE.birth(pid)
        processes.append(dict(pid=pid, expected_birth=expected, observed_birth=observed,
            same_live_identity=observed == expected, role=role))
    return dict(observed_at=ENGINE.now(), scientific_root=str(SCIENCE), snapshots=snapshots,
        processes=processes, natural_completion_allowed=True,
        dynamic_queue_equality_not_required=True, no_process_signals=True,
        no_GPU_or_API_calls=True)


def admitted_root(path):
    path = Path(path)
    require(path.is_absolute() and path == path.resolve() and path.is_dir(),
            'candidate must be one existing canonical non-symlink directory')
    cache_paths = {REPO / relative for relative in CACHE_RELATIVE}
    require(path in cache_paths or (path.parent == TEMP and path.name in TEST_CHILD_NAMES),
            'candidate is not one of the reviewed nineteen test roots or four caches')
    require(path not in (REPO, TEMP, ART, OUTPUT, ARCHIVE, SCIENCE), 'broad deletion forbidden')
    cursor = path
    while cursor != REPO:
        require(cursor.is_relative_to(REPO) and not cursor.is_symlink(), 'candidate ancestor escaped or redirected')
        cursor = cursor.parent


def _owned_identity(path):
    value = Path(path).lstat()
    require(value.st_uid == OWNER_UID, 'foreign-owned object must be retained')
    return [value.st_dev, value.st_ino, value.st_mode, value.st_size,
            value.st_mtime_ns, value.st_ctime_ns, value.st_nlink, value.st_blocks * 512]


def protected():
    global _ANCHORS
    if _ANCHORS is None:
        plan = OUTPUT / 'plan.json'
        require(plan.is_file(), 'fixed protection anchors must be registered before apply')
        _ANCHORS = tuple(plain(plan)['protected_files'])
    return identity_snapshot(_ANCHORS)


def load_engine():
    raw = SOURCE.read_bytes()
    require(hashlib.sha256(raw).hexdigest() == SOURCE_SHA256, 'original archive engine bytes changed')
    module = ModuleType('_fixed_20261025_project_test_archive_engine')
    module.__file__, module.__package__ = str(SOURCE), ''
    exec(compile(raw, str(SOURCE), 'exec'), module.__dict__)
    module.REPO, module.TEMP, module.OUTPUT = REPO, TEMP, OUTPUT
    module.admitted_root, module.protected, module.runtime = admitted_root, protected, runtime_snapshot
    # Same inventory implementation, but its one lstat also enforces ownership.
    namespace = dict(vars(module), identity=_owned_identity)
    module.inventory = FunctionType(module.inventory.__code__, namespace, 'inventory')
    module.__file__ = str(Path(__file__).resolve())
    return module


ENGINE = load_engine()
process_guard = ENGINE.process_guard


def validate_scope(value, protection):
    require(value['schema'] == SCOPE_SCHEMA and value['authorization'] == AUTHORIZATION,
            'new exact cleanup authorization/schema required')
    roots = value['roots']
    require(isinstance(roots, list) and roots and all(isinstance(path, str) for path in roots)
            and len(set(roots)) == len(roots), 'explicit unique root list required')
    paths = sorted(map(Path, roots))
    boundaries = [Path(row['path']) for row in protection['conservative_protected_roots']]
    for path in paths:
        admitted_root(path)
        require(not any(path.is_relative_to(bound) or bound.is_relative_to(path) for bound in boundaries),
                'candidate overlaps a protected scientific/model/worktree/lock root')
    require(not any(a != b and a.is_relative_to(b) for a in paths for b in paths),
            'nested cleanup roots would double count or expand removal')
    return paths


def prepare(scope_path, protection_path=PROTECTION_DEFAULT):
    global _ANCHORS
    require(os.getuid() == os.geteuid() == OWNER_UID, 'registered account required, not root')
    require(not (OUTPUT / 'plan.json').exists() and not (OUTPUT / 'execution_intent.json').exists()
            and not ARCHIVE.exists(), 'one fresh cleanup plan and backup only')
    scope, protection = plain(scope_path), plain(protection_path)
    roots = validate_scope(scope, protection)
    for reference in scope.get('source_reviews', []):
        require(sha(reference['path']) == reference['sha256'], 'reviewed candidate source changed')
    ENGINE.tracked_guard(roots)
    processes = process_guard(roots)
    rows = []
    for root in roots:
        entries = ENGINE.inventory(root)
        rows.append(dict(path=str(root), allocated_bytes=sum(row['identity'][7] for row in entries),
            entry_count=len(entries), metadata_sha256=hashlib.sha256(ENGINE.encode(entries)).hexdigest()))
    allocated = sum(row['allocated_bytes'] for row in rows)
    require(allocated == scope['source_allocated_bytes_from_read_only_inventory'],
            'reviewed allocation changed; preserve targets and update the proposed scope first')
    _ANCHORS = tuple(sorted(set(science_anchor_paths()) | {Path(__file__).resolve(),
        Path(scope_path).resolve(), Path(protection_path).resolve()}))
    protected_files = protected()
    require(OUTPUT.is_absolute() and OUTPUT.resolve() == OUTPUT and ARCHIVE.resolve() == ARCHIVE,
            'audit output or archive ancestor may not be redirected')
    OUTPUT.mkdir(mode=0o700, parents=True, exist_ok=True)
    require(not OUTPUT.is_symlink(), 'audit output may not be redirected')
    return ENGINE.publish('plan.json', dict(schema='unused_tests_recoverable_archive_plan.v1',
        at=ENGINE.now(), authorization=AUTHORIZATION, script_sha256=sha(__file__),
        source_engine=file_ref(SOURCE), scope_input=file_ref(scope_path), protection_input=file_ref(protection_path),
        roots=rows, source_allocated_bytes=allocated, process_guard=processes,
        protected_files=protected_files, runtime=runtime_snapshot(),
        protected_scope_review=protection, scope=scope, archive_destination=str(ARCHIVE),
        preserve_test_tmp_parent=True, backup_must_verify_before_any_source_removal=True,
        no_automatic_scope_expansion=True, no_automatic_retry=True,
        dynamic_queue_contents_are_snapshots_not_immutable_guards=True))


def relocate_archives():
    result, verified = plain(OUTPUT / 'result.json'), plain(OUTPUT / 'backup_verified.json')
    require(result['status'] == 'COMPLETE' and result['plan_id'] == verified['plan_id'],
            'only fully successful verified cleanup can relocate its new archives')
    require(not ARCHIVE.exists() and ARCHIVE.parent.resolve() == OUTPUT.parent.resolve(),
            'a fresh same-parent archive destination is required')
    rows = []
    for name, key in [('test_fixtures.tar.gz', 'archive_sha256'), ('member_manifest.json.gz', 'member_manifest_sha256')]:
        source = OUTPUT / name
        info = ENGINE.identity(source)
        require(stat.S_ISREG(info[2]) and info[6] == 1 and info[0] == ARCHIVE.parent.stat().st_dev,
                'only this new ordinary same-device archive may relocate')
        rows.append(dict(source=str(source), destination=str(ARCHIVE / name), sha256=verified[key], identity_before=info))
    ENGINE.publish('archive_relocation_intent.json', dict(at=ENGINE.now(), plan_id=result['plan_id'],
        source_result_id=result['id'], files=rows, previous_records_unchanged=True))
    ARCHIVE.mkdir(mode=0o700)
    fd = os.open(ARCHIVE.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)
    for row in rows:
        source, destination = Path(row['source']), Path(row['destination'])
        require(ENGINE.identity(source) == row['identity_before'] and not os.path.lexists(destination),
                'archive identity or destination changed')
        os.rename(source, destination)
        after = ENGINE.identity(destination)
        require(all(after[i] == row['identity_before'][i] for i in (0, 1, 2, 3, 4, 6, 7)),
                'same-device archive relocation changed content metadata')
        row['identity_after'] = after
    fd = os.open(ARCHIVE, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)
    ENGINE.sync_output_directory()
    return ENGINE.publish('archive_location.json', dict(at=ENGINE.now(), status='ARCHIVE_RELOCATED',
        plan_id=result['plan_id'], source_result_id=result['id'], files=rows,
        hashes_inherited_from_complete_member_verification=True, prior_result_not_rewritten=True))


def apply():
    require(os.getuid() == os.geteuid() == OWNER_UID, 'registered account required, not root')
    plan = plain(OUTPUT / 'plan.json')
    require(plan['source_engine'] == file_ref(SOURCE) and plan['source_engine']['sha256'] == SOURCE_SHA256,
            'bound original engine changed')
    require(plan['archive_destination'] == str(ARCHIVE) and not ARCHIVE.exists(), 'archive target changed or consumed')
    for reference in (plan['scope_input'], plan['protection_input']):
        require(sha(reference['path']) == reference['sha256'], 'bound new scope or protection review changed')
    require(validate_scope(plan['scope'], plan['protected_scope_review']) == [Path(row['path']) for row in plan['roots']],
            'planned exact root list changed')
    result = ENGINE.apply()
    relocate_archives()
    return result


def status():
    path = OUTPUT / 'result.json'
    if path.exists():
        value = plain(path)
        location = OUTPUT / 'archive_location.json'
        value = dict(value, final_archive_location=plain(location) if location.exists() else None)
        retained = sum(path.lstat().st_blocks * 512 for root in (OUTPUT, ARCHIVE) if root.is_dir()
                       for path in root.iterdir() if path.is_file() and not path.is_symlink())
        value['retained_cleanup_artifacts_allocated_bytes_now'] = retained
        value['net_reclaimed_bytes_including_final_audit'] = value['removed_source_allocated_bytes'] - retained
        value['additional_code_docs_git_and_directory_metadata_not_in_net'] = True
        return value
    return dict(status='EXECUTION_STARTED_NO_AUTO_RETRY' if (OUTPUT / 'execution_intent.json').exists()
        else 'PREPARED' if (OUTPUT / 'plan.json').exists() else 'NOT_PREPARED', output=str(OUTPUT))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('prepare', 'apply', 'status'))
    parser.add_argument('--scope', type=Path)
    parser.add_argument('--protection', type=Path, default=PROTECTION_DEFAULT)
    args = parser.parse_args(argv)
    if args.action == 'prepare':
        require(args.scope is not None, 'prepare requires a reviewed exact scope file')
        result = prepare(args.scope, args.protection)
    else:
        result = apply() if args.action == 'apply' else status()
    print(json.dumps({key: result[key] for key in ('id', 'status', 'source_allocated_bytes',
        'removed_source_allocated_bytes', 'estimated_net_reclaimed_bytes',
        'net_reclaimed_bytes_including_final_audit') if key in result}, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
