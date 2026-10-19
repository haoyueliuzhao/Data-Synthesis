"""One fixed, lossless archive of explicitly selected inactive historical data.

The immutable older engine verifies every member before any source unlink.
Current science, 596-point history, model checkpoints and existing cold archives are
never eligible. Restoring a cold artifact is explicit, into an empty directory.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import stat

REPO = Path('/data1/zhuxinrui/projects/Data-Synthesis')
ART = REPO / 'trusted_data_synthesis/artifacts'
OUTPUT, BACKUP = ART / 'storage_cleanup_20261019_cold_archive_01', ART / 'cold_archive_20261019_01'
SCOPE = OUTPUT / 'scope.json'
ENGINE_PATH = ART / 'storage_cleanup_20261010_cold_archive_01/archive.py'
ENGINE_SHA256 = 'ee61e44d33c7c7f9fbe51d2d5a4239d953eb73a79f55d5e2ab552a551493318e'
ORIGINAL_HELPER = ART / 'storage_cleanup_20261010_test_tmp_01/cleanup.py'
ORIGINAL_HELPER_SHA256 = '00075258dca71ba946daeac8de641effebc01595a3e693b96e04f6566bf927d9'
PROTECTION_HELPER = ART / 'storage_cleanup_20261019_test_tmp_01/cleanup.py'
PROTECTION_HELPER_SHA256 = 'af819613455507dae7143ae248d4d6f00190c187eb40571bcc5958ac1652e03e'
FINQA = 'trusted_data_synthesis/artifacts/finance_research_20260928/finqa_v6_01'
V18 = FINQA + '/v18_researcher_continuation_01'
V25 = V18 + '/v25_training_replication_01'
PRODUCTION = V25 + '/production_resume_01'
SCIENCE = REPO / V18 / 'v54_feedback_temperature_01/automatic_recovery_01'
V61 = SCIENCE / 'concurrency_six_01'
WALLETS = frozenset((FINQA + '/v15_prefix_completion_01/wallet_before_v15_mapping.sqlite3',
                    FINQA + '/v12_rereview_02/wallet_before_v12_request_transfer.sqlite3'))
PROFILE = V25 + '/replay_performance_01/micro_R0/profile/trace.json'
COHORT = (PRODUCTION + '/recovery_04/contexts/seed389/c_only/step0894_outer/feedback_resume_view/'
          'dc03ecaa04ac96ea215e281ab5de848ddbf93ebb202fd32c541d637824c6c972/cohort_seal/record.json')
CONTEXT_PATTERN = re.compile(re.escape(PRODUCTION) +
    r'/(?:[^/]+/)*contexts/seed(?P<seed>137|251|389)/(?P<arm>c_only|full)/step(?P<step>0298|0894|1192)_outer')
AUTHORIZATION = '进一步清理压缩旧实验产物'
SCOPE_SCHEMA = 'old_experiments_lossless_cold_archive_scope.v1'
_SCOPE, _SCOPE_SHA256, _PROTECTION, _LAST_SELECTED = None, None, None, None
_TASK_RECORD_CACHE = {}


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_bytes())


def normalized_relative(value):
    require(isinstance(value, str) and value and not Path(value).is_absolute()
            and str(Path(value)) == value and '..' not in Path(value).parts,
            'one exact normalized repository-relative path required')
    require('v54_feedback_temperature_01' not in Path(value).parts
            and re.search(r'(?:^|/)step0*596(?:[^0-9]|$)', value) is None,
            'current V54 and every historical 596-point path are protected')
    return value


def context_coordinate(path):
    path = normalized_relative(path)
    match = CONTEXT_PATTERN.fullmatch(path)
    require(match is not None, 'only exact registered old non596 outer contexts are eligible')
    return int(match['seed']), match['arm'], int(match['step'])


def allowed_source(path, logical_bytes):
    path = normalized_relative(path)
    if path in WALLETS:
        return 'wallet_snapshot'
    if path == PROFILE:
        return 'historical_profile_trace'
    if path == COHORT:
        require(type(logical_bytes) is int and logical_bytes > 8 * 1024**2,
                'only explicitly selected cohort seals larger than 8MiB are eligible')
        return 'old_non596_cohort_seal'
    match = re.fullmatch(r'(.+)/task_cache/task[0-9]{4}/gradient\.pt', path)
    if match:
        context_coordinate(match[1])
        return 'old_non596_complete_task_gradient'
    raise RuntimeError('unknown historical path or tensor type is not authorized')


def validate_scope(value):
    require(value['schema'] == SCOPE_SCHEMA and value['authorization'] == AUTHORIZATION,
            'scope schema or explicit authorization changed')
    require(isinstance(value['sources'], list) and isinstance(value.get('gradient_contexts', []), list)
            and isinstance(value['groups'], dict) and value['groups'], 'explicit source/context/group lists required')
    seen, seen_contexts, totals = set(), set(), {}

    def count(group, number, allocated, logical):
        require(isinstance(group, str) and re.fullmatch(r'[a-z][a-z0-9_]{0,63}', group)
                and group in value['groups'], 'unregistered archive group')
        require(all(type(item) is int and item > 0 for item in (number, allocated, logical)),
                'positive exact source counts and byte amounts required')
        row = totals.setdefault(group, dict(count=0, allocated_bytes=0, logical_bytes=0))
        for key, amount in (('count', number), ('allocated_bytes', allocated), ('logical_bytes', logical)):
            row[key] += amount

    for item in value['sources']:
        path = normalized_relative(item['path'])
        require(path not in seen, 'duplicate explicit source')
        seen.add(path)
        kind = allowed_source(path, item['logical_bytes'])
        if kind == 'old_non596_complete_task_gradient':
            seed, _, _ = context_coordinate(path.rsplit('/task_cache/', 1)[0])
            require(item['group'] == f'old_class_seed{seed}', 'gradient group must preserve its registered seed')
        count(item['group'], 1, item['allocated_bytes'], item['logical_bytes'])
    for item in value.get('gradient_contexts', []):
        seed, _, _ = context_coordinate(item['path'])
        require(item['path'] not in seen_contexts and item['group'] == f'old_class_seed{seed}',
                'duplicate context or changed gradient seed group')
        require(not any(path.startswith(item['path'] + '/task_cache/') for path in seen),
                'context and explicit-source selectors overlap')
        seen_contexts.add(item['path'])
        count(item['group'], item['count'], item['allocated_bytes'], item['logical_bytes'])
    require(set(totals) == set(value['groups']), 'empty or undeclared archive group')
    for group, actual in totals.items():
        expected = value['groups'][group]
        require(actual['count'] == expected['count'] and actual['allocated_bytes'] == expected['allocated_bytes'],
                'group totals do not match the explicit sources and contexts')
        if expected.get('logical_bytes') is not None:
            require(actual['logical_bytes'] == expected['logical_bytes'], 'group logical bytes changed')
    return value


def checked_scope():
    global _SCOPE, _SCOPE_SHA256
    if _SCOPE is None:
        _SCOPE = validate_scope(read(SCOPE))
        _SCOPE_SHA256 = sha(SCOPE)
    else:
        require(sha(SCOPE) == _SCOPE_SHA256, 'immutable dependency scope changed during this invocation')
    return _SCOPE


def minimal_scopes(paths):
    retained = []
    for path in sorted(set(paths), key=lambda value: (len(value.parts), str(value))):
        if not any(path.is_relative_to(parent) for parent in retained):
            retained.append(path)
    return retained


def configure():
    scope = checked_scope()
    engine.OUTPUT, engine.BACKUP, engine.PUBLICATIONS = OUTPUT, BACKUP, []
    engine.GROUPS = tuple(scope['groups'])
    engine.EXPECTED = {key: (row['count'], row['allocated_bytes']) for key, row in scope['groups'].items()}
    roots = [(REPO / row['path']).parent for row in scope['sources']]
    roots.extend(REPO / row['path'] / 'task_cache' for row in scope.get('gradient_contexts', []))
    engine.SCOPES = minimal_scopes(roots)
    return scope


def check_database_sidecars(path):
    if str(path.relative_to(REPO)) in WALLETS:
        require(not any(path.parent.glob(path.name + '-*')),
                'a wallet sidecar appeared; retain the original database and re-audit')


def ordinary(path):
    info = _original_ordinary(path)
    check_database_sidecars(path)
    if path.name == 'gradient.pt':
        metadata = path.with_name('record.json')
        current = tuple(engine.identity(metadata))
        require(stat.S_ISREG(current[2]) and metadata == metadata.resolve(),
                'complete-task metadata is missing or redirected')
        if metadata in _TASK_RECORD_CACHE:
            expected_identity, expected_bytes = _TASK_RECORD_CACHE[metadata]
            require(current == expected_identity, 'complete-task metadata changed after its first validation')
        else:
            value = read(metadata)
            body = {key: item for key, item in value.items() if key != 'id'}
            require(value.get('schema') == 'v35_complete_task_gradient.v1' and value.get('complete_task') is True
                    and type(value.get('gradient_bytes')) is int
                    and value.get('id') == hashlib.sha256(engine.encode(body)).hexdigest()
                    and tuple(engine.identity(metadata)) == current,
                    'gradient is not bound to a complete immutable task record')
            expected_bytes = value['gradient_bytes']
            _TASK_RECORD_CACHE[metadata] = (current, expected_bytes)
        require(expected_bytes == info[3], 'gradient byte length differs from its complete-task record')
    return info


def selected():
    global _LAST_SELECTED
    scope = configure()
    tracked, rows = engine.tracked_paths(), []

    def add(relative, group, *, expected=None):
        path = REPO / relative
        require(str(path) not in tracked, 'Git-tracked content must stay in place')
        info = ordinary(path)
        kind = allowed_source(relative, info[3])
        if expected is not None:
            require((info[7], info[3]) == (expected['allocated_bytes'], expected['logical_bytes']),
                    'an explicit source changed from its audited byte amounts')
        rows.append(dict(path=relative, group=group, identity=info, source_kind=kind))

    for item in scope['sources']:
        add(item['path'], item['group'], expected=item)
    for item in scope.get('gradient_contexts', []):
        cache = REPO / item['path'] / 'task_cache'
        require(cache.is_dir() and cache == cache.resolve() and not cache.is_symlink(), 'context cache is redirected or absent')
        start = len(rows)
        for directory in sorted(cache.iterdir()):
            require(directory.is_dir() and not directory.is_symlink()
                    and re.fullmatch(r'task[0-9]{4}', directory.name)
                    and {path.name for path in directory.iterdir()} == {'record.json', 'gradient.pt'},
                    'context contains an unexpected, partial or redirected task entry')
            add(str((directory / 'gradient.pt').relative_to(REPO)), item['group'])
        added = rows[start:]
        require(len(added) == item['count']
                and sum(row['identity'][7] for row in added) == item['allocated_bytes']
                and sum(row['identity'][3] for row in added) == item['logical_bytes'],
                'exact context task count/allocation/logical bytes changed')
    require(len({row['path'] for row in rows}) == len(rows), 'expanded source selectors overlap')
    for group, expected in scope['groups'].items():
        chosen = [row for row in rows if row['group'] == group]
        require(len(chosen) == expected['count'] and sum(row['identity'][7] for row in chosen) == expected['allocated_bytes'],
                'actual group count or allocated bytes changed')
    _LAST_SELECTED = sorted(rows, key=lambda row: (row['group'], row['path']))
    return _LAST_SELECTED


def protection_helper():
    global _PROTECTION
    if _PROTECTION is None:
        require(sha(PROTECTION_HELPER) == PROTECTION_HELPER_SHA256, 'immutable protection helper changed')
        spec = importlib.util.spec_from_file_location('_cold_archive_19_protection', PROTECTION_HELPER)
        _PROTECTION = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(_PROTECTION)
    return _PROTECTION


def protected():
    checked_scope()
    result = protection_helper().protected()
    implementation = V61 / 'implementation/record.json'
    manifest = read(implementation)
    require(len(manifest['files']) == 14 and all(Path(name).name == name and name.endswith('.py') for name in manifest['files']),
            'all fourteen registered V61 source files must be protected')
    paths = [V61 / 'protocol/record.json', V61 / 'prepared/record.json', implementation,
             Path(__file__).resolve(), ENGINE_PATH, ORIGINAL_HELPER, PROTECTION_HELPER, SCOPE]
    paths.extend(implementation.parent / name for name in manifest['files'])
    for path in paths:
        result[str(path)] = engine.identity(path)
    return result


def runtime():
    result = dict(observed_at=engine.H['now'](), dynamic_observations_not_compared_for_equality=True,
                  no_experiment_action=True)
    try:
        result['original_current_control_snapshot'] = protection_helper().runtime()
    except (OSError, ValueError, KeyError) as error:
        result['original_snapshot_error'] = type(error).__name__
    for name, path in (('V61_queue', V61 / 'queue/status.json'), ('V61_cron', V61 / 'cron/status.json'),
                       ('V61_state', V61 / 'state.json')):
        try:
            if path.is_file():
                value = read(path)
                result[name] = {key: value[key] for key in ('status', 'phase', 'current_episode', 'at_epoch',
                    'updated_epoch', 'active_workers', 'pid', 'birth') if key in value}
        except (OSError, ValueError, KeyError) as error:
            result[name] = dict(observation_available=False, error_type=type(error).__name__)
    return result


def references_sources(arguments, cwd, targets, parents, context_roots):
    def within_context(value):
        return any(value == root or value.startswith(root + '/') for root in context_roots)
    if cwd in parents or within_context(cwd):
        return True
    for argument in arguments:
        value = argument.split('=', 1)[1] if argument.startswith('-') and '=' in argument else argument
        if value in targets or within_context(value):
            return True
    return False


def process_guard(_roots):
    rows = _LAST_SELECTED if _LAST_SELECTED is not None else selected()
    inodes = {(row['identity'][0], row['identity'][1]) for row in rows}
    targets = {str(REPO / row['path']) for row in rows}
    parents = {str(Path(path).parent) for path in targets}
    scope = checked_scope()
    context_roots = {str(REPO / item['path']) for item in scope.get('gradient_contexts', [])}
    context_roots.update(str(REPO / item['path'].rsplit('/task_cache/', 1)[0])
                         for item in scope['sources'] if item['path'].endswith('/gradient.pt'))
    report = dict(at=engine.H['now'](), inspected_same_account_processes=0, other_accounts_not_inspected=0,
        vanished_processes=0, skipped_self_and_ancestors=[], hits=[], protected_system_daemons_not_fully_inspected=[],
        no_environment_read=True, unrelated_argv_not_logged=True, no_process_signals=True,
        limitation='Readable same-account FD/mmap/explicit-path snapshot; future dynamic opens and other accounts are not comprehensively covered.')
    ancestors, cursor = {os.getpid()}, os.getppid()
    while cursor > 1 and cursor not in ancestors:
        ancestors.add(cursor)
        try:
            cursor = int((Path('/proc') / str(cursor) / 'stat').read_text().rsplit(')', 1)[1].split()[1])
        except (OSError, ValueError, IndexError):
            break
    for proc in sorted(Path('/proc').iterdir()):
        if not proc.name.isdigit():
            continue
        pid, comm, arguments = int(proc.name), None, []
        if pid in ancestors:
            report['skipped_self_and_ancestors'].append(pid)
            continue
        try:
            if proc.stat().st_uid != os.getuid():
                report['other_accounts_not_inspected'] += 1
                continue
            fields = (proc / 'stat').read_text().rsplit(')', 1)[1].split()
            birth = fields[19]
            comm = (proc / 'comm').read_text().strip()
            arguments = [value.decode(errors='replace') for value in (proc / 'cmdline').read_bytes().split(b'\0') if value]
            cwd = os.readlink(proc / 'cwd')
            if references_sources(arguments, cwd, targets, parents, context_roots):
                report['hits'].append(dict(pid=pid, birth=birth, channel='exact_target_or_registered_context_path'))
            for descriptor in (proc / 'fd').iterdir():
                try:
                    info = descriptor.stat()
                    if (info.st_dev, info.st_ino) in inodes:
                        report['hits'].append(dict(pid=pid, birth=birth, channel='target_inode_FD', fd=descriptor.name))
                except (FileNotFoundError, ProcessLookupError):
                    pass
            for line in (proc / 'maps').read_text().splitlines():
                fields = line.split(None, 5)
                if len(fields) >= 5:
                    major, minor = (int(value, 16) for value in fields[3].split(':'))
                    if (os.makedev(major, minor), int(fields[4])) in inodes:
                        report['hits'].append(dict(pid=pid, birth=birth, channel='target_inode_mmap'))
            after = (proc / 'stat').read_text().rsplit(')', 1)[1].split()[19]
            require(after == birth, 'process identity changed during source-use observation')
            report['inspected_same_account_processes'] += 1
        except (FileNotFoundError, ProcessLookupError):
            report['vanished_processes'] += 1
        except PermissionError as error:
            known = (comm == 'sshd' and arguments and arguments[0].startswith('sshd:')) or (
                comm == 'systemd' and arguments == ['/usr/lib/systemd/systemd', '--user']) or (
                comm == '(sd-pam)' and arguments == ['(sd-pam)'])
            require(known, 'unknown inaccessible same-account process prevents source removal')
            report['protected_system_daemons_not_fully_inspected'].append(dict(pid=pid, comm=comm, error_type=type(error).__name__))
    require(not report['hits'], 'an explicit source inode/path is in use; retain originals')
    return report


def positive_gain(source_allocated, archive_allocated, manifest_allocated):
    require(source_allocated > archive_allocated + manifest_allocated,
            'verified archive and member manifest have no positive allocated gain; retain all source files')
    return source_allocated - archive_allocated - manifest_allocated


def pack(group, rows):
    receipt = _original_pack(group, rows)
    archive_bytes = Path(receipt['archive']).stat().st_blocks * 512
    manifest_bytes = (OUTPUT / receipt['member_manifest']).stat().st_blocks * 512
    gain = positive_gain(receipt['source_allocated_bytes'], archive_bytes, manifest_bytes)
    return dict(receipt, archive_allocated_bytes=archive_bytes, member_manifest_allocated_bytes=manifest_bytes,
                positive_allocated_gain_before_shared_audit_overhead=gain)


def publish(name, body):
    if name == 'plan.json':
        body = dict(body, schema='old_experiments_lossless_cold_archive_plan.v1', authorization=AUTHORIZATION,
            frozen_engine_path=str(ENGINE_PATH), frozen_engine_sha256=ENGINE_SHA256,
            original_helper_sha256=ORIGINAL_HELPER_SHA256, protection_helper_sha256=PROTECTION_HELPER_SHA256,
            dependency_scope_path=str(SCOPE), dependency_scope_sha256=_SCOPE_SHA256,
            no_prior_plan_resumed=True, exact_current_and_step596_exclusion=True,
            whole_member_verification_before_any_unlink=True,
            each_new_archive_requires_positive_allocated_gain=True)
    elif name == 'result.json':
        body = dict(body, schema='old_experiments_lossless_cold_archive_result.v1')
    return _original_publish(name, body)


def load_engine():
    require(sha(ENGINE_PATH) == ENGINE_SHA256 and sha(ORIGINAL_HELPER) == ORIGINAL_HELPER_SHA256
            and sha(PROTECTION_HELPER) == PROTECTION_HELPER_SHA256, 'frozen archival or protection source changed')
    spec = importlib.util.spec_from_file_location('_cold_archive_19_original_engine', ENGINE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.__file__ = str(Path(__file__).resolve())
    return module


engine = load_engine()
_original_ordinary, _original_pack, _original_publish = engine.ordinary, engine.pack, engine.publish
engine.ordinary, engine.selected, engine.protected = ordinary, selected, protected
engine.pack, engine.publish = pack, publish
engine.H['process_guard'], engine.H['runtime'] = process_guard, runtime


def require_plan_bindings():
    scope = checked_scope()
    del scope
    plan = read(OUTPUT / 'plan.json')
    require(plan.get('id') == hashlib.sha256(engine.encode({key: value for key, value in plan.items() if key != 'id'})).hexdigest()
            and plan['frozen_engine_sha256'] == ENGINE_SHA256
            and plan['original_helper_sha256'] == ORIGINAL_HELPER_SHA256
            and plan['protection_helper_sha256'] == PROTECTION_HELPER_SHA256
            and plan['dependency_scope_sha256'] == _SCOPE_SHA256
            and plan['script_sha256'] == sha(__file__), 'plan engine, wrapper or dependency scope binding changed')
    return plan


def main():
    require(os.getuid() == os.geteuid() == 1004, 'archive and restore use only the registered nonroot account')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('prepare', 'apply', 'restore'))
    parser.add_argument('--group')
    parser.add_argument('--destination', type=Path)
    args = parser.parse_args()
    configure()
    if args.action == 'prepare':
        require(args.group is None and args.destination is None, 'prepare has no restore arguments')
        result = engine.prepare()
    else:
        require_plan_bindings()
        if args.action == 'restore':
            require(args.group and args.destination, 'restore requires a registered group and isolated empty destination')
            result = engine.restore(args.group, args.destination)
        else:
            require(args.group is None and args.destination is None, 'apply has no restore arguments')
            result = engine.apply()
    print(json.dumps({key: result[key] for key in ('id', 'status', 'source_allocated_bytes',
        'removed_files', 'estimated_net_reclaimed_bytes', 'destination') if key in result}, sort_keys=True))


if __name__ == '__main__':
    main()
