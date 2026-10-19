"""One explicitly authorized, irreversible old-B intermediate-state cleanup.

Only the new plan's exact ordinary state.pt files may be unlinked. The original
descriptor-safe unlink engine is byte-bound and unchanged. All JSON, directory,
epoch, outer, shared, C1-window, selected recovery-point and live V54 data stay.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import stat
import subprocess

REPO = Path('/data1/zhuxinrui/projects/Data-Synthesis')
V18 = REPO / 'trusted_data_synthesis/artifacts/finance_research_20260928/finqa_v6_01/v18_researcher_continuation_01'
ROOT = V18 / 'v25_training_replication_01/training_replication'
OUT = REPO / 'trusted_data_synthesis/artifacts/storage_cleanup_20261019_replication_intermediates_01'
SCRIPT, SCOPE = OUT / 'cleanup.py', OUT / 'scope.json'
SOURCE = REPO / 'trusted_data_synthesis/artifacts/storage_cleanup_20261005_non_epoch_01/cleanup.py'
SOURCE_SHA256 = '232f419898c04c6fe813a9f0b43984f64a064b36537276b084eebcb122e982df'
PROTECTION_SOURCE = REPO / 'trusted_data_synthesis/artifacts/storage_cleanup_20261019_test_tmp_01/cleanup.py'
PROTECTION_SOURCE_SHA256 = 'af819613455507dae7143ae248d4d6f00190c187eb40571bcc5958ac1652e03e'
SCIENCE = V18 / 'v54_feedback_temperature_01/automatic_recovery_01'
CONTROL, MASTER = SCIENCE / 'signal_recovery_04', SCIENCE / 'automatic_control_watchdog_01'
CONTROL_ID = 'ffad4c05b8031cf94be53746b40ea1f0636c66e13e8a042d02b51cdb70736d5d'
SCIENTIFIC_ID = '53e084012b25dc34cc9a073cb53a1a3bf5d1dc7c4547937cd39e87e4d4be75af'
SEEDS, ARMS = (137, 251, 389), ('static', 'c_only', 'full')
AUTHORIZATION = '允许删除旧中间状态'
BASE_COUNT = 9768
MANDATORY_EXCLUSIONS = {(137, 'c_only', 1193), (389, 'full', 299),
    (251, 'full', 1213), (251, 'full', 1237), (251, 'full', 1334), (251, 'full', 1335)}
_SCOPE, _PROTECTION = None, None


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_bytes())


def bound_record(path):
    value = read(path)
    body = {key: item for key, item in value.items() if key != 'id'}
    expected = hashlib.sha256(json.dumps(body, sort_keys=True, ensure_ascii=False,
        separators=(',', ':'), allow_nan=False).encode()).hexdigest()
    require(value.get('id') == expected, 'bound lifecycle record changed: ' + str(path))
    return value


def base_coordinates():
    return {(seed, arm, step) for seed in SEEDS for arm in ARMS for step in range(299, 1491)
            if step % 149 and not (arm == 'c_only' and 597 <= step <= 894)}


def checked_scope():
    global _SCOPE
    if _SCOPE is None:
        value = read(SCOPE)
        require(value['schema'] == 'v25_authorized_non_epoch_retention_scope.v1'
                and value['authorization'] == AUTHORIZATION and value['candidate_base_count'] == BASE_COUNT,
                'exact user authorization or original candidate scope changed')
        excluded = {(row['seed'], row['arm'], row['step']) for row in value['excluded_coordinates']}
        require(len(excluded) == len(value['excluded_coordinates'])
                and MANDATORY_EXCLUSIONS <= excluded <= base_coordinates(),
                'explicit recovery-point exclusions are duplicate, missing or outside the candidate scope')
        require(value['expected_candidate_count'] == BASE_COUNT - len(excluded)
                and type(value['expected_candidate_allocated_bytes']) is int
                and value['expected_candidate_allocated_bytes'] > 0,
                'final fixed count/allocation must match the audited exclusions')
        for path in value.get('protected_audit_refs', []):
            candidate = Path(path)
            require(candidate.is_absolute() and candidate == candidate.resolve() and candidate.is_relative_to(REPO)
                    and candidate.suffix == '.json' and candidate.stat().st_size <= 16 * 1024**2,
                    'only explicit small repository JSON audit references may be protected and hashed')
        _SCOPE = value
    return _SCOPE


def fixed_targets():
    scope = checked_scope()
    excluded = {(row['seed'], row['arm'], row['step']) for row in scope['excluded_coordinates']}
    return sorted(ROOT / f'seed{seed}/arms/{arm}/training/step{step:04d}_step/state.pt'
                  for seed, arm, step in base_coordinates() - excluded)


def target_inventory():
    scope, paths = checked_scope(), fixed_targets()
    require(len(paths) == scope['expected_candidate_count'], 'exact candidate count changed')
    tracked = set(subprocess.check_output(['git', 'ls-files', '-z', '--', ENGINE.relative(ROOT)], cwd=REPO,
        env={**os.environ, 'GIT_OPTIONAL_LOCKS': '0'}).decode().split('\0'))
    rows, checked, device = [], set(), ROOT.stat().st_dev
    for path in paths:
        require(ENGINE.relative(path) not in tracked, 'Git-tracked tensor must not be deleted')
        row = ENGINE.identity(path, checked)
        require(row['nlink'] == 1 and row['dev'] == device,
                'hardlinked or foreign-device candidate must be retained')
        rows.append(row)
    require(sum(row['allocated_bytes'] for row in rows) == scope['expected_candidate_allocated_bytes'],
            'actual fixed allocation differs from the audited authorization')
    if scope.get('expected_candidate_logical_bytes') is not None:
        require(sum(row['size'] for row in rows) == scope['expected_candidate_logical_bytes'],
                'actual fixed logical bytes differ from the audit')
    return rows


def protection_helper():
    global _PROTECTION
    if _PROTECTION is None:
        require(digest(PROTECTION_SOURCE) == PROTECTION_SOURCE_SHA256, 'immutable protection helper changed')
        spec = importlib.util.spec_from_file_location('_b_cleanup_immutable_anchor_helper', PROTECTION_SOURCE)
        _PROTECTION = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(_PROTECTION)
    return _PROTECTION


def protection_inventory():
    selected, groups = set(fixed_targets()), {}

    def add(path, kind):
        path = Path(path)
        require(path not in selected, 'protected file intersects the explicit deletion list')
        groups.setdefault(path, set()).add(kind)

    for seed in SEEDS:
        for arm in ARMS:
            base = ROOT / f'seed{seed}/arms/{arm}/training'
            for checkpoint in sorted(base.glob('step*_*')):
                add(checkpoint / 'record.json', 'all_old_B_checkpoint_records')
                state = checkpoint / 'state.pt'
                if state not in selected:
                    add(state, 'all_nonselected_old_B_checkpoint_states')
                if (checkpoint / 'outer_inputs.pt').is_file():
                    add(checkpoint / 'outer_inputs.pt', 'all_outer_inputs')
            for epoch in range(447, 1491, 149):
                add(base / f'step{epoch:04d}_step/state.pt', 'all_epoch_endpoints')
            if arm == 'c_only':
                for step in range(597, 895):
                    add(base / f'step{step:04d}_step/state.pt', 'complete_protected_C1_window')
            for path in base.glob('replay_checkpoints/**/state.pt'):
                add(path, 'old_B_response_checkpoint_state')
            result = base.parent / 'result/record.json'
            if result.is_file():
                add(result, 'old_B_arm_result')
        for path in (ROOT / f'seed{seed}/shared').rglob('*'):
            if path.is_file():
                add(path, 'all_shared_files')
        result = ROOT / f'seed{seed}/result/record.json'
        if result.is_file():
            add(result, 'old_B_seed_result')
    for row in checked_scope()['excluded_coordinates']:
        add(ROOT / f"seed{row['seed']}/arms/{row['arm']}/training/step{row['step']:04d}_step/state.pt",
            'explicit_registered_recovery_point')
    for path in protection_helper().protected():
        add(path, 'current_scientific_control_and_original_lock_anchor')
    for path in (SCRIPT, SOURCE, PROTECTION_SOURCE, SCOPE):
        add(path, 'cleanup_implementation_or_scope')
    audit_paths = {Path(path) for path in checked_scope().get('protected_audit_refs', [])}
    for path in audit_paths:
        add(path, 'small_dependency_audit')
    rows, counts, checked = [], {}, set()
    for path, kinds in sorted(groups.items()):
        row = ENGINE.identity(path, checked)
        row['kinds'] = sorted(kinds)
        if path in audit_paths or path in (SCRIPT, SOURCE, PROTECTION_SOURCE, SCOPE):
            row['sha256'] = digest(path)
        rows.append(row)
        for kind in kinds:
            counts[kind] = counts.get(kind, 0) + 1
    require(counts['all_epoch_endpoints'] == 72 and counts['complete_protected_C1_window'] == 894,
            'registered epoch or complete C1 protection coverage changed')
    return rows, counts


def allowed_current_processes():
    protocol = bound_record(CONTROL / 'protocol/record.json')
    require(protocol['id'] == CONTROL_ID and protocol['scientific_protocol_id'] == SCIENTIFIC_ID,
            'the currently authorized control04 identity changed')
    queue = bound_record(CONTROL / 'journal/state.json')
    require(queue['control_protocol_id'] == CONTROL_ID and queue['protocol_id'] == SCIENTIFIC_ID,
            'current scientific journal binding changed')
    allowed = {(row['pid'], row['birth']): 'current_scientific_worker' for row in queue['active_jobs']}
    paths = [(CONTROL / 'supervisor/launch/record.json', 'current_supervisor')]
    paths.extend((path, 'current_controller') for path in sorted(CONTROL.glob('controllers/attempt*/launch/record.json')))
    for path, role in paths:
        value = bound_record(path)
        require(value['control_protocol_id'] == CONTROL_ID, 'foreign current controller identity')
        allowed[(value['pid'], value['birth'])] = role
    observer = read(CONTROL / 'observer/launch/record.json')
    require(observer['root'] == str(CONTROL) and observer['science_root'] == str(SCIENCE),
            'foreign read-only observer identity')
    allowed[(observer['pid'], observer['birth'])] = 'current_readonly_observer'
    master = bound_record(MASTER / 'protocol/record.json')
    cron_command = master['cron_policy']['command']
    require(cron_command == [str(REPO / 'trusted_data_synthesis/.venv/bin/python'), '-u',
        str(MASTER / 'implementation/finqa_v60_cron.py'), 'tick', '--root', str(MASTER)],
        'registered exact V60 cron command changed')
    return allowed, cron_command


def process_audit(rows):
    targets = {(row['dev'], row['inode']) for row in rows}
    target_paths = {str(REPO / row['path']) for row in rows}
    allowed, cron_command = allowed_current_processes()
    report = dict(at=ENGINE.now(), own_uid=os.getuid(), own_uid_processes_checked=0,
        other_uid_processes_not_inspected=0, vanished_processes=0, allowed_current_identities=[],
        protected_system_daemons_not_fully_inspected=[], target_users=[], unknown_relevant_python=[],
        no_process_signaled=True, private_unrelated_argv_not_logged=True,
        limitation='Same-account readable FD/mmap/path snapshot only; future dynamic opens, other accounts and protected daemon FD tables are not comprehensively covered.')
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
        try:
            if proc.stat().st_uid != os.getuid():
                report['other_uid_processes_not_inspected'] += 1
                continue
            before = (proc / 'stat').read_text().rsplit(')', 1)[1].split()
            birth, state = before[19], before[0]
            comm = (proc / 'comm').read_text().strip()
            arguments = [part.decode(errors='replace') for part in (proc / 'cmdline').read_bytes().split(b'\0') if part]
            cwd = os.readlink(proc / 'cwd')
            role = allowed.get((pid, birth))
            if arguments == cron_command:
                role = 'exact_registered_V60_cron_tick'
            if role and state != 'Z':
                report['allowed_current_identities'].append(dict(pid=pid, birth=birth, role=role))
            direct_path = [token for token in arguments if token in target_paths or token == str(ROOT)
                           or token.startswith(str(ROOT) + '/')]
            if direct_path or cwd == str(ROOT) or cwd.startswith(str(ROOT) + '/'):
                if pid not in ancestors:
                    report['target_users'].append(dict(pid=pid, birth=birth, channel='explicit_old_B_argv_or_cwd'))
            executable = Path(arguments[0]).name if arguments else ''
            relevant = any(str(ROOT) in token or str(SCIENCE) in token or 'finqa_v' in token for token in arguments)
            if pid not in ancestors and role is None and state not in ('Z', 'T', 't') and relevant and (
                    'python' in executable or 'torchrun' in executable):
                report['unknown_relevant_python'].append(dict(pid=pid, birth=birth, executable=executable))
            for descriptor in (proc / 'fd').iterdir():
                try:
                    info = descriptor.stat()
                    if (info.st_dev, info.st_ino) in targets:
                        report['target_users'].append(dict(pid=pid, birth=birth, channel='open_target_fd', fd=descriptor.name))
                except (FileNotFoundError, ProcessLookupError):
                    pass
            for line in (proc / 'maps').read_text().splitlines():
                fields = line.split(None, 5)
                if len(fields) < 5:
                    continue
                major, minor = (int(value, 16) for value in fields[3].split(':'))
                if (os.makedev(major, minor), int(fields[4])) in targets:
                    report['target_users'].append(dict(pid=pid, birth=birth, channel='mapped_target_inode'))
            after = (proc / 'stat').read_text().rsplit(')', 1)[1].split()
            require(after[19] == birth, 'process identity changed during target-use observation')
            report['own_uid_processes_checked'] += 1
        except (FileNotFoundError, ProcessLookupError):
            report['vanished_processes'] += 1
        except PermissionError as error:
            known_system = (comm == 'sshd' and arguments and arguments[0].startswith('sshd:')) or (
                comm == 'systemd' and arguments == ['/usr/lib/systemd/systemd', '--user']) or (
                comm == '(sd-pam)' and arguments == ['(sd-pam)'])
            require(known_system, 'unknown inaccessible same-account process prevents cleanup')
            report['protected_system_daemons_not_fully_inspected'].append(dict(pid=pid, comm=comm, error_type=type(error).__name__))
    require(not report['target_users'], 'a target inode/path is currently in use; retain it')
    require(not report['unknown_relevant_python'], 'unregistered active scientific Python process; retain candidates')
    return report


def load_engine():
    require(digest(SOURCE) == SOURCE_SHA256, 'original descriptor-safe unlink engine changed')
    spec = importlib.util.spec_from_file_location('_b_replication_old_unlink_engine', SOURCE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.ROOT, module.OUT, module.SCRIPT = ROOT, OUT, SCRIPT
    module.SEEDS, module.ARMS, module.AUTHORIZATION = SEEDS, ARMS, AUTHORIZATION
    module.fixed_targets, module.target_inventory = fixed_targets, target_inventory
    module.protection_inventory, module.process_audit = protection_inventory, process_audit
    original_write = module.write_new

    def write_new(path, value):
        value = dict(value)
        if value.get('schema') == 'finqa_v18_non_epoch_cleanup_result.v1':
            value['schema'] = 'finqa_v25_b_replication_intermediate_cleanup_result.v1'
            try:
                value['runtime_after'] = protection_helper().runtime()
            except (OSError, ValueError, KeyError) as error:
                # A disappearing/changing observation must not prevent the
                # irreversible deletion result from being durably published.
                value['runtime_after'] = dict(observation_available=False, error_type=type(error).__name__,
                                              no_experiment_action=True)
        value.update(source_engine_sha256=SOURCE_SHA256, protection_source_sha256=PROTECTION_SOURCE_SHA256,
                     dependency_scope_sha256=digest(SCOPE))
        return original_write(path, value)

    module.write_new = write_new
    return module


ENGINE = load_engine()


def plan():
    require(not (OUT / 'plan.json').exists() and not (OUT / 'execution_intent.json').exists(), 'one new immutable plan only')
    scope = checked_scope()
    targets = target_inventory()
    protection, counts = protection_inventory()
    body = dict(schema='finqa_v25_b_replication_intermediate_cleanup_plan.v1', at=ENGINE.now(),
        authorization_exact=AUTHORIZATION, scope_root=ENGINE.relative(ROOT), seeds=list(SEEDS), arms=list(ARMS),
        steps='299..1490, nonmultiples of149, excluding c_only597..894 and explicit recovery coordinates',
        target_basename='state.pt', script_sha256=digest(SCRIPT), dependency_scope=str(SCOPE),
        source_engine=str(SOURCE), protection_source=str(PROTECTION_SOURCE), exclusions=scope['excluded_coordinates'],
        destructive=True, tensor_hashing_performed=False,
        recoverability='Irrecoverable: no content backup; Git and retained JSON cannot reconstruct deleted model/Adam/RNG states.',
        only_unlink_fixed_targets=True, directories_and_all_other_files_retained=True, no_retry_or_resume=True,
        candidates=targets, candidate_count=len(targets), candidate_logical_bytes=sum(row['size'] for row in targets),
        candidate_allocated_bytes=sum(row['allocated_bytes'] for row in targets), protected=protection,
        protected_count=len(protection), protection_counts=counts, process_audit=process_audit(targets),
        filesystem_before=ENGINE.storage(), dynamic_current_branch_trees_not_compared=True,
        git_head=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=REPO).decode().strip())
    ENGINE.write_new(OUT / 'plan.json', body)
    print(json.dumps(dict(plan_sha256=digest(OUT / 'plan.json'), candidate_count=len(targets),
        candidate_allocated_bytes=body['candidate_allocated_bytes'], protected_count=len(protection), execution_performed=False)))


def execute(expected_sha):
    scope = checked_scope()
    body = read(OUT / 'plan.json')
    require(body['source_engine_sha256'] == SOURCE_SHA256
            and body['protection_source_sha256'] == PROTECTION_SOURCE_SHA256
            and body['dependency_scope_sha256'] == digest(SCOPE)
            and body['schema'] == 'finqa_v25_b_replication_intermediate_cleanup_plan.v1',
            'new plan implementation or dependency audit binding changed')
    ENGINE.EXPECTED_COUNT = scope['expected_candidate_count']
    return ENGINE.execute(expected_sha)


if __name__ == '__main__':
    require(os.getuid() == os.geteuid() == 1004 and Path(__file__).resolve() == SCRIPT,
            'registered account and exact new cleanup entry required')
    ENGINE.no_symlink_ancestors(SCRIPT)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('plan', 'execute'))
    parser.add_argument('--plan-sha256')
    arguments = parser.parse_args()
    if arguments.action == 'plan':
        require(arguments.plan_sha256 is None, 'plan does not accept an execution hash')
        plan()
    else:
        execute(arguments.plan_sha256)
