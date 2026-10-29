"""Archive and prune only five reviewed registrations whose worktrees are absent."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import tarfile
from datetime import datetime, timezone

REPO = Path('/data1/zhuxinrui/projects/Data-Synthesis')
OUTPUT = REPO / 'trusted_data_synthesis/artifacts/storage_cleanup_20261029_stale_worktrees_01'
NAMES = ('trusted_synthesis_pro_flash', 'v26_60_worktree', 'Data-Synthesis-v26.110',
         'Data-Synthesis-v26.112', 'Data-Synthesis-v26.141')


def require(value, message):
    if not value:
        raise RuntimeError(message)


def git(*args):
    return subprocess.check_output(['git', '-C', str(REPO), *args],
        env={**os.environ, 'GIT_OPTIONAL_LOCKS': '0'}, stderr=subprocess.STDOUT).decode()


def identity(path):
    s = path.lstat()
    return [s.st_dev, s.st_ino, s.st_mode, s.st_size, s.st_mtime_ns,
            s.st_ctime_ns, s.st_nlink, s.st_blocks * 512, s.st_uid]


def dry_run():
    output = git('worktree', 'prune', '--dry-run', '--verbose', '--expire', 'now')
    expected = {f'Removing worktrees/{name}: gitdir file points to non-existent location' for name in NAMES}
    require(set(output.splitlines()) == expected, 'dry-run scope differs; keep registrations')
    return output


def publish(name, value):
    value = {**value, 'at': datetime.now(timezone.utc).isoformat()}
    value['id'] = hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()
    with (OUTPUT / name).open('x') as f:
        json.dump(value, f, ensure_ascii=False, indent=2)
        f.write('\n'); f.flush(); os.fsync(f.fileno())
    fd = os.open(OUTPUT, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)
    return value


def main():
    require(os.getuid() == os.geteuid() == 1004, 'registered account required')
    require(not OUTPUT.exists(), 'single fresh operation only')
    before = dry_run()
    refs, rows, directories, child_directories = {}, [], [], []
    for name in NAMES:
        root = REPO / '.git/worktrees' / name
        require(root.resolve() == root and root.is_dir() and not (root / 'locked').exists(),
                'registration redirected or locked')
        old_gitdir = Path((root / 'gitdir').read_text().strip())
        require(not os.path.lexists(old_gitdir) and not os.path.lexists(old_gitdir.parent),
                'working tree exists; keep registration')
        ref = (root / 'HEAD').read_text().strip()
        require(ref.startswith('ref: refs/heads/'), 'named branch required')
        ref = ref[5:]
        commit = git('rev-parse', '--verify', ref).strip()
        require(git('cat-file', '-t', commit).strip() == 'commit', 'commit missing')
        require(not subprocess.check_output(['git', '--git-dir', str(root),
            'diff', '--cached', '--name-only', commit],
            env={**os.environ, 'GIT_OPTIONAL_LOCKS': '0'}), 'staged changes must be kept')
        refs[ref] = commit
        directories.append({'path': str(root), 'identity': identity(root), 'absent_worktree': str(old_gitdir.parent)})
        for p in sorted(root.rglob('*')):
            s = p.lstat()
            require(s.st_uid == 1004 and (stat.S_ISDIR(s.st_mode) or
                    (stat.S_ISREG(s.st_mode) and s.st_nlink == 1)), 'unexpected registration entry')
            if p.is_file():
                rows.append({'path': str(p), 'name': str(p.relative_to(REPO)),
                             'identity': identity(p), 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()})
            else:
                child_directories.append({'path': str(p), 'identity': identity(p)})
    OUTPUT.mkdir(mode=0o700)
    (OUTPUT / 'executor.py').write_bytes(Path(__file__).read_bytes())
    plan = publish('plan.json', {'authorization': '清理历史无用数据', 'dry_run': before,
        'branches': refs, 'directories': directories, 'child_directories': child_directories, 'files': rows,
        'source_allocated_bytes': sum(x['identity'][7] for x in rows + directories + child_directories)})
    archive = OUTPUT / 'stale_worktree_metadata.tar.gz'
    with tarfile.open(archive, 'x:gz', dereference=False) as tar:
        for row in rows:
            p = Path(row['path'])
            require(identity(p) == row['identity'], 'source changed before backup')
            tar.add(p, arcname=row['name'], recursive=False)
    with archive.open('rb') as f:
        os.fsync(f.fileno())
    with tarfile.open(archive, 'r:gz') as tar:
        for member, row in zip(tar, rows, strict=True):
            require(member.isfile() and member.name == row['name'], 'archive member mismatch')
            require(hashlib.sha256(tar.extractfile(member).read()).hexdigest() == row['sha256'],
                    'backup content mismatch')
    publish('backup_verified.json', {'plan_id': plan['id'], 'archive': str(archive),
        'sha256': hashlib.sha256(archive.read_bytes()).hexdigest(), 'verified_members': len(rows)})
    require(dry_run() == before, 'prune candidate scope changed')
    require(all(identity(Path(row['path'])) == row['identity'] for row in rows + directories + child_directories),
            'registration changed; keep it')
    require(all(git('rev-parse', ref).strip() == commit for ref, commit in refs.items()),
            'branch changed; keep registration')
    require(shutil.rmtree.avoids_symlink_attacks, 'descriptor-safe removal required')
    publish('execution_intent.json', {'plan_id': plan['id'],
        'method': 'remove only the five archived absent-worktree registrations; no broad git prune'})
    removed = []
    for row in directories:
        root = Path(row['path'])
        require(identity(root) == row['identity'] and not (root / 'locked').exists()
                and not os.path.lexists(row['absent_worktree']), 'worktree changed; retain it')
        current_files = {str(p) for p in root.rglob('*') if p.is_file()}
        expected_files = {item['path'] for item in rows if Path(item['path']).is_relative_to(root)}
        require(current_files == expected_files, 'registration contents changed; retain it')
        require(all(identity(Path(item['path'])) == item['identity']
                    for item in rows + child_directories if Path(item['path']).is_relative_to(root)),
                'registration changed before removal')
        shutil.rmtree(root)
        removed.append(str(root))
    require(all(not Path(row['path']).exists() for row in directories), 'registration remains')
    require(all(git('rev-parse', ref).strip() == commit for ref, commit in refs.items()), 'branch changed')
    result = publish('result.json', {'status': 'COMPLETE', 'plan_id': plan['id'],
        'removed_registrations': len(NAMES), 'removed_source_allocated_bytes': plan['source_allocated_bytes'],
        'branches_preserved': refs, 'removed_paths': removed,
        'backup_and_audit_allocated_before_result': sum(p.stat().st_blocks * 512 for p in OUTPUT.iterdir()),
        'no_commit_objects_or_existing_worktrees_removed': True})
    print(json.dumps({k: result[k] for k in ('status', 'id', 'removed_source_allocated_bytes')}))


if __name__ == '__main__':
    main()
