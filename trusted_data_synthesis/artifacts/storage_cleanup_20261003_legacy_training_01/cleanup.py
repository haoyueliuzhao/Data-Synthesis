"""One-shot, explicitly approved legacy-artifact cleanup; not a general GC tool."""

import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
from datetime import datetime
from zoneinfo import ZoneInfo


REPO = Path('/data1/zhuxinrui/projects/Data-Synthesis')
ART = REPO / 'trusted_data_synthesis/artifacts'
AUDIT = ART / 'storage_cleanup_20261003_legacy_training_01'
FIXED = ART / 'qa_vnext_fixed_kernel_value'
FEAS = ART / 'feasibility/architecture_mvp_20260730'
FEAS_RUNS = (
    'training_D2', 'training_C2_current', 'training_C2_80k',
    'prompt_v5/train_D2', 'prompt_v6/train_D2',
    'prompt_v6_complete_contract/train_D2',
)
OLD_V21 = (
    'finance_v21_target_observability_local_updates_v1_20260807',
    'finance_v21_direct_target_observability_study_v1_20260807',
)
EXPECTED = {
    'cancelled_august_v21': 169,
    'superseded_v13_requests': 1316,
    'proxy_gradients': 332,
    'delayed_c_outer_gradients': 1714,
    'direction_response_gradients': 1711,
    'feasibility_checkpoint_payloads': 60,
}


def now():
    return datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds')


def digest_file(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(4 * 1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + '\n').encode()


def publish(name, value):
    # Generated audit output is never allowed to overwrite an earlier receipt.
    with (AUDIT / name).open('xb') as f:
        f.write(encoded(value))
        f.flush()
        os.fsync(f.fileno())


def file_stat(path):
    assert path.is_absolute() and path.is_relative_to(ART), str(path)
    assert path.resolve() == path, f'linked path: {path}'
    s = path.lstat()
    assert stat.S_ISREG(s.st_mode) and s.st_nlink == 1, str(path)
    return dict(path=str(path.relative_to(REPO)), device=s.st_dev, inode=s.st_ino,
                size=s.st_size, allocated_bytes=s.st_blocks * 512,
                mtime_ns=s.st_mtime_ns, ctime_ns=s.st_ctime_ns)


def discover():
    groups = {name: [] for name in EXPECTED}
    scopes = []
    for name in OLD_V21:
        p = ART / 'vtdo_experiment' / name
        scopes.append(p)
        groups['cancelled_august_v21'].extend(p.rglob('*.safetensors'))
    p = ART / 'finance_research_20260928/finqa_v6_01/v13_material_01/requests'
    scopes.append(p.parent)
    requests = [f for f in p.rglob('*') if f.is_file()]
    assert all(f.suffix == '.json' for f in requests)
    groups['superseded_v13_requests'].extend(requests)
    for seed in (11, 29, 47):
        for epoch in (0, 5):
            p = FIXED / f'proxy_audit_cache_20260919/jobs/A_full_{seed}_epoch{epoch}'
            scopes.append(p)
            groups['proxy_gradients'].append(p / 'class_gradients.npy')
            groups['proxy_gradients'].extend((p / 'positive_gradients').glob('*.safetensors'))
        p = FIXED / f'delayed_C_B_confirmation_cache_20260922/outer/B_delayed_c_{seed}'
        scopes.append(p)
        groups['delayed_c_outer_gradients'].append(p / 'population.pt')
        groups['delayed_c_outer_gradients'].extend((p / 'replay').glob('*.pt'))
        p = FIXED / f'direction_calibration_cache_20260926/reliability/B_direction_reliability_{seed}'
        scopes.append(p)
        groups['direction_response_gradients'].extend((p / 'responses').glob('*.pt'))
    for run in FEAS_RUNS:
        p = FEAS / run / 'trainer_state'
        scopes.append(p)
        # Keep the original JSON/README records, including trainer_state.json.
        for name in ('adapter_model.safetensors', 'optimizer.pt', 'rng_state.pth',
                     'scheduler.pt', 'training_args.bin'):
            groups['feasibility_checkpoint_payloads'].extend(p.glob(f'checkpoint-*/{name}'))
    rows = []
    for name, paths in groups.items():
        assert len(paths) == EXPECTED[name], (name, len(paths), EXPECTED[name])
        rows.extend(dict(group=name, **file_stat(p)) for p in sorted(paths))
    assert len({r['path'] for r in rows}) == len(rows)
    selected = {r['path'] for r in rows}
    tracked = subprocess.check_output(
        ['git', 'ls-files', '-z', '--', *[str(p.relative_to(REPO)) for p in scopes]],
        cwd=REPO,
    ).decode().split('\0')
    assert not selected.intersection(tracked), 'tracked deletion target'
    retained = []
    for scope in scopes:
        assert scope.resolve() == scope and scope.is_dir(), str(scope)
        for p in scope.rglob('*'):
            assert not p.is_symlink(), str(p)
            if p.is_file() and str(p.relative_to(REPO)) not in selected:
                retained.append(file_stat(p))
    return rows, sorted(retained, key=lambda r: r['path'])


def protected_points():
    records = []
    points = FIXED / 'cross_market_calibration_cache_20260926/evaluation_01/points'
    point_files = sorted(points.glob('*/point.json'))
    assert len(point_files) == 9
    for p in point_files:
        obj = json.loads(p.read_text())
        for key in ('adapter', 'origin_checkpoint'):
            value = obj[key]
            path = Path(value['path'])
            if not path.is_absolute():
                path = p.parent / path
            path = path.resolve()
            sha = digest_file(path)
            assert sha == value['sha256'], (str(p), key)
            records.append(dict(kind=key, sha256=sha, **file_stat(path)))
        records.append(dict(kind='point_metadata', sha256=digest_file(p), **file_stat(p)))
    for run in FEAS_RUNS:
        p = FEAS / run / 'adapter'
        assert (p / 'adapter_model.safetensors').is_file(), str(p)
        records.extend(dict(kind='feasibility_final', **file_stat(f))
                       for f in sorted(p.rglob('*')) if f.is_file())
    return records


def no_open_targets(rows):
    selected = {str(REPO / r['path']) for r in rows}
    hits = []
    for proc in Path('/proc').iterdir():
        if not proc.name.isdigit():
            continue
        try:
            if proc.stat().st_uid != os.getuid():
                continue
            for link in (proc / 'fd').iterdir():
                try:
                    target = os.readlink(link)
                except OSError:
                    continue
                if target in selected:
                    hits.append((proc.name, target))
        except (OSError, PermissionError):
            continue
    assert not hits, hits


def runtime():
    p = ART / 'finance_research_20260928/finqa_v6_01/v18_researcher_continuation_01/six_gpu_queue_01/queue/status.json'
    s = json.loads(p.read_text())
    workers = []
    for w in s['active_children']:
        raw = Path(f'/proc/{w["pid"]}/stat').read_text().rsplit(')', 1)[1].split()
        assert raw[19] == str(w['birth']) and raw[0] != 'Z'
        workers.append({k: w[k] for k in ('job_key', 'pid', 'birth', 'gpu')})
    assert not s['failures']
    return dict(at=now(), heartbeat_at=s['at'], phase=s['phase'],
                workers=workers, queued=s['queued'], failures=s['failures'],
                disk_free_bytes=shutil.disk_usage(ART).free)


def summary(rows):
    return {name: dict(files=sum(r['group'] == name for r in rows),
                       allocated_bytes=sum(r['allocated_bytes'] for r in rows if r['group'] == name))
            for name in EXPECTED}


def main():
    if sys.argv[1:] == ['plan']:
        rows, retained = discover()
        protected = protected_points()
        assert not {r['path'] for r in rows}.intersection(r['path'] for r in protected)
        no_open_targets(rows)
        plan = dict(schema='legacy_training_cleanup_plan.v1', at=now(),
                    scope='user-approved 2026-10-03 whitelist only',
                    script_sha256=digest_file(Path(__file__)),
                    files=rows, retained_files=retained, protected=protected,
                    groups=summary(rows), before=runtime())
        publish('plan.json', plan)
        print(json.dumps(dict(plan_sha256=digest_file(AUDIT / 'plan.json'),
                              groups=plan['groups'], files=len(rows),
                              retained_files=len(retained), protected_files=len(protected),
                              before=plan['before']), ensure_ascii=False), flush=True)
        return
    assert len(sys.argv) == 3 and sys.argv[1] == 'execute'
    assert not (AUDIT / 'result.json').exists()
    plan_path = AUDIT / 'plan.json'
    assert digest_file(plan_path) == sys.argv[2], 'plan hash changed'
    plan = json.loads(plan_path.read_text())
    assert digest_file(Path(__file__)) == plan['script_sha256'], 'script changed'
    rows, retained = discover()
    assert rows == plan['files'] and retained == plan['retained_files'], 'inventory changed'
    assert protected_points() == plan['protected'], 'protected points changed'
    no_open_targets(rows)
    before = runtime()
    publish('execution_intent.json', dict(at=now(), plan_sha256=sys.argv[2], before=before))
    deleted = []
    try:
        for row in rows:
            path = REPO / row['path']
            assert file_stat(path) == {k: v for k, v in row.items() if k != 'group'}
            path.unlink()  # Only individual, resolved, previously registered regular files.
            deleted.append(row['path'])
        assert all(not (REPO / row['path']).exists() for row in rows)
        for row in retained:
            assert file_stat(REPO / row['path']) == row, row['path']
        assert protected_points() == plan['protected'], 'protected point mutation'
        after = runtime()
        result = dict(schema='legacy_training_cleanup_result.v1', status='complete',
                      at=now(), plan_sha256=sys.argv[2], deleted_file_count=len(deleted),
                      deleted_allocated_bytes=sum(r['allocated_bytes'] for r in rows),
                      groups=summary(rows), retained_files_unchanged=len(retained),
                      protected_files_unchanged=len(plan['protected']), before=before,
                      after=after, net_free_increase_bytes=after['disk_free_bytes']-before['disk_free_bytes'],
                      backup_created=False, git_recovery_available=False)
    except BaseException as exc:
        result = dict(status='partial_failure', at=now(), plan_sha256=sys.argv[2],
                      deleted_file_count=len(deleted), deleted_paths=deleted,
                      error=f'{type(exc).__name__}: {exc}')
        publish('result.json', result)
        raise
    publish('result.json', result)
    print(json.dumps(result, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
