"""One lossless archive of four reviewed pre-registration wallet snapshots.

The byte-bound original engine verifies every member before any source unlink.
Main/inventory ledgers, sidecars, scientific data and prior archives are excluded.
Restore is explicit into an existing empty directory; no SQLite operation occurs.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import re
import stat
from types import ModuleType

REPO = Path('/data1/zhuxinrui/projects/Data-Synthesis')
ART = REPO / 'trusted_data_synthesis/artifacts'
OUTPUT = ART / 'storage_cleanup_20261025_wallet_snapshots_01'
BACKUP = ART / 'cold_archive_20261025_wallet_snapshots_01'
ENGINE_PATH = ART / 'storage_cleanup_20261010_cold_archive_01/archive.py'
ENGINE_SHA256 = 'ee61e44d33c7c7f9fbe51d2d5a4239d953eb73a79f55d5e2ab552a551493318e'
ORIGINAL_HELPER = ART / 'storage_cleanup_20261010_test_tmp_01/cleanup.py'
ORIGINAL_HELPER_SHA256 = '00075258dca71ba946daeac8de641effebc01595a3e693b96e04f6566bf927d9'
PROTECTION_HELPER = REPO / 'trusted_data_synthesis/scripts/storage_cleanup_20261025_test_cache.py'
PROTECTION_HELPER_SHA256 = '557bdf0d3a88e7ee2862c5b43fc41ba5136f8d8064f72c5c261782307d1cf611'
ELIGIBILITY_DEFAULT = Path('/tmp/cleanup_20261025_wallet_review.json')
ELIGIBILITY_SHA256 = '2e84dd05a07162a44a82fd6e17a3664e87e91cb08641095f4dded40f1cc978de'
AUTHORIZATION, OWNER_UID = '清理历史无用数据', 1004
GROUP = 'wallet_before_snapshots'
PREFIX = 'trusted_data_synthesis/artifacts/finance_research_20260928/finqa_v6_01/'
WALLETS = frozenset(PREFIX + name for name in (
    'v13_material_02/wallet_before_v13_material_purposes.sqlite3',
    'v14_representation_01/wallet_before_v14_residual.sqlite3',
    'v16_six_task_continuation_01/wallet_before_v16.sqlite3',
    'v17_three_task_continuation_01/wallet_before_v17.sqlite3'))
_SCOPE, _SCOPE_SHA, _PROTECTION, _PROTECTION_SHA = None, None, None, None
_ANCHORS, _PRESERVED = None, None


def require(value, message):
    if not value:
        raise RuntimeError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def plain(path):
    return json.loads(Path(path).read_bytes())


def file_ref(path):
    return dict(path=str(Path(path).resolve()), sha256=sha(path))


def checked_relative(value):
    require(isinstance(value, str) and value in WALLETS and not Path(value).is_absolute()
            and str(Path(value)) == value and '..' not in Path(value).parts,
            'only the exact four wallet_before snapshots are authorized')
    return value


def validate_review(value):
    require(value['schema'] == 'wallet_snapshot_cold_archive_eligibility_20261025.v1'
            and value['status'] == 'ELIGIBLE' and value['read_only'] is True
            and value['current_dependencies_unchanged'] is True
            and len(value['exact_paths']) == 4 and set(value['exact_paths']) == WALLETS,
            'a complete fixed four-snapshot eligibility review is required')
    selected = []
    for row in value['candidates']:
        path = Path(row['path'])
        if not path.is_relative_to(REPO) or str(path.relative_to(REPO)) not in WALLETS:
            continue
        require(row['eligibility'] == 'ELIGIBLE_FOR_VERIFIED_LOSSLESS_COLD_ARCHIVE_ONLY'
                and row['blockers'] == [] and row['visible_process_hits'] == []
                and row['sidecars_present'] == [] and row['symlink'] is False
                and row['nlink'] == 1 and row['tracked'] is False and row['uid'] == OWNER_UID
                and row['recorded_as_pre_registration_backup'] is True
                and row['recorded_backup']['path'] == str(path)
                and row['recorded_backup']['bytes'] == row['logical_bytes']
                and re.fullmatch(r'[0-9a-f]{64}', row['recorded_backup']['sha256']) is not None,
                'wallet review does not establish an idle historical backup')
        identity = [row[key] for key in ('dev', 'ino', 'mode', 'logical_bytes',
                                         'actual_mtime_ns', 'ctime_ns', 'nlink', 'allocated_bytes')]
        selected.append(dict(path=str(path.relative_to(REPO)), group=GROUP, identity=identity,
            source_kind='historical_pre_registration_wallet_snapshot',
            recorded_content_sha256=row['recorded_backup']['sha256'],
            creation_record=row['creation_record'], creation_record_id=row['creation_record_id']))
    require(len(selected) == 4 and {row['path'] for row in selected} == WALLETS,
            'review must identify each exact source once')
    return sorted(selected, key=lambda row: row['path'])


def check_sidecars(path):
    require(not any(path.parent.glob(path.name + '-*'))
            and not path.with_name(path.name + '.journal').exists(),
            'wallet WAL/SHM/journal/other sidecar appeared; preserve originals')


def ordinary(path):
    path = Path(path)
    checked_relative(str(path.relative_to(REPO)))
    info = _original_ordinary(path)
    require(path.lstat().st_uid == OWNER_UID, 'foreign-owned source is forbidden')
    check_sidecars(path)
    return info


def checked_scope():
    global _SCOPE, _SCOPE_SHA
    path = OUTPUT / 'scope.json'
    if _SCOPE is None:
        value = plain(path)
        require(value['schema'] == 'four_wallet_snapshots_cold_archive_scope.v1'
                and value['authorization'] == AUTHORIZATION
                and len(value['sources']) == 4
                and {row['path'] for row in value['sources']} == WALLETS,
                'fixed wallet scope or authorization changed')
        for row in value['sources']:
            checked_relative(row['path'])
            require(row['group'] == GROUP and len(row['identity']) == 8
                    and stat.S_ISREG(row['identity'][2]) and row['identity'][6] == 1,
                    'invalid fixed wallet identity')
        _SCOPE, _SCOPE_SHA = value, sha(path)
    else:
        require(sha(path) == _SCOPE_SHA, 'immutable wallet scope changed')
    return _SCOPE


def configure():
    scope = checked_scope()
    engine.OUTPUT, engine.BACKUP, engine.PUBLICATIONS = OUTPUT, BACKUP, []
    engine.GROUPS = (GROUP,)
    engine.EXPECTED = {GROUP: (4, sum(row['identity'][7] for row in scope['sources']))}
    # File-level scopes keep Git/process admission exact; no recursive parent census.
    engine.SCOPES = [REPO / row['path'] for row in scope['sources']]
    return scope


def selected():
    scope = configure()
    tracked = engine.tracked_paths()
    for row in scope['sources']:
        path = REPO / row['path']
        require(str(path) not in tracked, 'Git-tracked source must remain in place')
        require(ordinary(path) == row['identity'], 'wallet identity changed since eligibility review')
    return scope['sources']


def protection_helper():
    global _PROTECTION, _PROTECTION_SHA
    path = OUTPUT / 'protection_helper.py'
    require(path.is_file(), 'frozen new protection helper is required')
    raw = path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    require(digest == PROTECTION_HELPER_SHA256, 'reviewed new protection helper bytes changed')
    if _PROTECTION is None:
        module = ModuleType('_wallet_20261025_protection')
        module.__file__, module.__package__ = str(path), ''
        exec(compile(raw, str(path), 'exec'), module.__dict__)
        _PROTECTION, _PROTECTION_SHA = module, digest
    else:
        require(digest == _PROTECTION_SHA, 'frozen protection helper changed')
    return _PROTECTION


def protected():
    global _ANCHORS
    if _ANCHORS is None:
        _ANCHORS = tuple(plain(OUTPUT / 'plan.json')['protected_files'])
    return protection_helper().identity_snapshot(_ANCHORS)


def preserved(_rows):
    global _PRESERVED
    if _PRESERVED is None:
        _PRESERVED = tuple(plain(OUTPUT / 'plan.json')['preserved_file_paths'])
    entries = [[str(path), engine.identity(path)] for path in map(Path, _PRESERVED)]
    return dict(count=len(entries), metadata_sha256=hashlib.sha256(engine.encode(entries)).hexdigest())


def runtime():
    return protection_helper().runtime_snapshot()


def process_guard(_roots):
    return protection_helper().process_guard([REPO / row['path'] for row in checked_scope()['sources']])


def positive_gain(source_allocated, archive_allocated, manifest_allocated):
    require(source_allocated > archive_allocated + manifest_allocated,
            'verified archive has no positive allocated gain; retain all sources')
    return source_allocated - archive_allocated - manifest_allocated


def pack(group, rows):
    require(group == GROUP and len(rows) == 4, 'only one fixed four-member pack is allowed')
    receipt = _original_pack(group, rows)
    members = engine.load_manifest(receipt['member_manifest'], receipt['member_manifest_sha256'])
    expected = {row['path']: row for row in rows}
    require(len(members) == 4 and {row['path'] for row in members} == WALLETS,
            'archive member set changed')
    for row in members:
        require(row['sha256'] == expected[row['path']]['recorded_content_sha256'],
                'actual wallet bytes differ from the original registration backup digest')
    archive_allocated = Path(receipt['archive']).stat().st_blocks * 512
    manifest_allocated = (OUTPUT / receipt['member_manifest']).stat().st_blocks * 512
    gain = positive_gain(receipt['source_allocated_bytes'], archive_allocated, manifest_allocated)
    return dict(receipt, original_recorded_backup_hashes_match=True,
        archive_allocated_bytes=archive_allocated, member_manifest_allocated_bytes=manifest_allocated,
        positive_allocated_gain_before_shared_audit_overhead=gain)


def publish(name, body):
    if name == 'plan.json':
        body = dict(body, schema='four_wallet_snapshots_lossless_archive_plan.v1',
            authorization=AUTHORIZATION, frozen_engine_sha256=ENGINE_SHA256,
            original_helper_sha256=ORIGINAL_HELPER_SHA256,
            frozen_protection_helper=file_ref(OUTPUT / 'protection_helper.py'),
            eligibility_review=file_ref(OUTPUT / 'eligibility_review.json'),
            fixed_scope_sha256=_SCOPE_SHA, preserved_file_paths=list(map(str, _PRESERVED)),
            non_target_protection_scope='fixed immediate non-directory siblings plus explicit scientific anchors',
            no_recursive_parent_census=True, no_automatic_retry=True,
            no_database_connections_or_SQLite_changes=True,
            original_registration_digest_checked_during_pack_before_source_removal=True,
            historical_redeployment_requires_original_path_restoration=True,
            max_actual_parallel_packers=1)
    elif name == 'result.json':
        body = dict(body, schema='four_wallet_snapshots_lossless_archive_result.v1',
            authorization=AUTHORIZATION,
            retained_files_scope='fixed immediate non-directory siblings plus separate explicit scientific anchors',
            historical_redeployment_requires_original_path_restoration=True)
    return _original_publish(name, body)


def load_engine():
    raw = ENGINE_PATH.read_bytes()
    require(hashlib.sha256(raw).hexdigest() == ENGINE_SHA256
            and sha(ORIGINAL_HELPER) == ORIGINAL_HELPER_SHA256,
            'frozen original archive engine/helper changed')
    module = ModuleType('_wallet_20261025_original_cold_engine')
    module.__file__, module.__package__ = str(ENGINE_PATH), ''
    exec(compile(raw, str(ENGINE_PATH), 'exec'), module.__dict__)
    module.__file__ = str(Path(__file__).resolve())
    return module


engine = load_engine()
_original_ordinary, _original_pack, _original_publish = engine.ordinary, engine.pack, engine.publish
engine.ordinary, engine.selected, engine.protected, engine.preserved = ordinary, selected, protected, preserved
engine.pack, engine.publish = pack, publish
engine.H['process_guard'], engine.H['runtime'] = process_guard, runtime


@contextmanager
def private_files():
    previous = os.umask(0o077)
    try:
        yield
    finally:
        os.umask(previous)


def _write_new(path, raw):
    with Path(path).open('xb') as stream:
        stream.write(raw); stream.flush(); os.fsync(stream.fileno())


def prepare(eligibility_path=ELIGIBILITY_DEFAULT):
    global _ANCHORS, _PRESERVED
    require(os.getuid() == os.geteuid() == OWNER_UID, 'registered nonroot account required')
    require(not os.path.lexists(OUTPUT) and not os.path.lexists(BACKUP), 'one fresh plan and backup only')
    eligibility_raw = Path(eligibility_path).read_bytes()
    require(hashlib.sha256(eligibility_raw).hexdigest() == ELIGIBILITY_SHA256,
            'reviewed eligibility bytes changed')
    rows = validate_review(json.loads(eligibility_raw))
    helper_raw = PROTECTION_HELPER.read_bytes()
    require(hashlib.sha256(helper_raw).hexdigest() == PROTECTION_HELPER_SHA256,
            'reviewed current science protection helper changed')
    with private_files():
        OUTPUT.mkdir(mode=0o700)
        _write_new(OUTPUT / 'archive.py', Path(__file__).read_bytes())
        _write_new(OUTPUT / 'protection_helper.py', helper_raw)
        _write_new(OUTPUT / 'eligibility_review.json', eligibility_raw)
        scope = dict(schema='four_wallet_snapshots_cold_archive_scope.v1', authorization=AUTHORIZATION,
            sources=rows, one_group=GROUP, source_allocated_bytes=sum(row['identity'][7] for row in rows),
            main_and_inventory_ledgers_excluded=True, database_sidecars_forbidden=True)
        _write_new(OUTPUT / 'scope.json', engine.encode(scope) + b'\n')
        engine.sync_directory(OUTPUT)
        configure()
        helper = protection_helper()
        targets = {REPO / row['path'] for row in rows}
        science = set(helper.science_anchor_paths())
        require(not targets & science, 'candidate overlaps an active scientific protection anchor')
        _ANCHORS = tuple(sorted(science | {Path(__file__).resolve(), OUTPUT / 'archive.py',
            OUTPUT / 'protection_helper.py', OUTPUT / 'eligibility_review.json', OUTPUT / 'scope.json',
            ENGINE_PATH, ORIGINAL_HELPER}))
        siblings = set()
        for directory in sorted({path.parent for path in targets}):
            for path in directory.iterdir():
                if path not in targets and not stat.S_ISDIR(path.lstat().st_mode):
                    siblings.add(path)
        _PRESERVED = tuple(sorted(siblings))
        return engine.prepare()


def require_plan_bindings():
    configure()
    plan = plain(OUTPUT / 'plan.json')
    require(plan['id'] == hashlib.sha256(engine.encode({k: v for k, v in plan.items() if k != 'id'})).hexdigest()
            and plan['schema'] == 'four_wallet_snapshots_lossless_archive_plan.v1'
            and plan['authorization'] == AUTHORIZATION
            and plan['frozen_engine_sha256'] == ENGINE_SHA256
            and plan['original_helper_sha256'] == ORIGINAL_HELPER_SHA256
            and plan['fixed_scope_sha256'] == _SCOPE_SHA
            and plan['script_sha256'] == sha(__file__), 'bound wallet plan or implementation changed')
    for key in ('frozen_protection_helper', 'eligibility_review'):
        reference = plan[key]
        require(sha(reference['path']) == reference['sha256'], 'bound supporting source changed')
    require(plan['frozen_protection_helper']['path'] == str(OUTPUT / 'protection_helper.py')
            and plan['eligibility_review']['path'] == str(OUTPUT / 'eligibility_review.json'),
            'supporting sources escaped independent archive root')
    return plan


def apply():
    require(os.getuid() == os.geteuid() == OWNER_UID, 'registered nonroot account required')
    plan = require_plan_bindings()
    require(not (OUTPUT / 'apply_attempt.json').exists(), 'one apply attempt only; no automatic retry')
    with private_files():
        publish('apply_attempt.json', dict(plan_id=plan['id'], at=engine.H['now'](), no_automatic_retry=True))
        try:
            return engine.apply()
        except BaseException as error:
            if not (OUTPUT / 'operation_failure.json').exists():
                publish('operation_failure.json', dict(plan_id=plan['id'], at=engine.H['now'](),
                    status='STOPPED_NO_AUTOMATIC_RETRY', error_type=type(error).__name__, error=str(error),
                    source_paths_still_present=[path for path in sorted(WALLETS) if os.path.lexists(REPO / path)],
                    original_result_not_overwritten=True))
            raise


def restore(group, destination):
    require(os.getuid() == os.geteuid() == OWNER_UID, 'registered nonroot account required')
    require_plan_bindings()
    with private_files():
        return engine.restore(group, Path(destination))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('prepare', 'apply', 'restore'))
    parser.add_argument('--eligibility', type=Path, default=ELIGIBILITY_DEFAULT)
    parser.add_argument('--group', choices=(GROUP,))
    parser.add_argument('--destination', type=Path)
    args = parser.parse_args(argv)
    if args.action == 'restore':
        require(args.group and args.destination, 'restore requires a group and empty isolated destination')
        result = restore(args.group, args.destination)
    else:
        require(args.group is None and args.destination is None, 'only restore accepts destination/group')
        result = prepare(args.eligibility) if args.action == 'prepare' else apply()
    print(json.dumps({key: result[key] for key in ('id', 'status', 'source_allocated_bytes',
        'removed_files', 'estimated_net_reclaimed_bytes', 'destination') if key in result}, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
