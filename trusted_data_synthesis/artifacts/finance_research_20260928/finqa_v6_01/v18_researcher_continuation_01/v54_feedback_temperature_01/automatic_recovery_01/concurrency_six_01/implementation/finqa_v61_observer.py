"""One byte-bound CPU observer for an independently registered watchdog episode."""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path

from finqa_v61_binding import (MASTER_ROOT, SCIENCE_ROOT, SOURCE_CONTROL_PROTOCOL_ID,
    checked_record, episode_root, load_v59_module, require, resource_override)


def observer_policy():
    observer = load_v59_module('finqa_v59_observer').load_original()
    return dict(schema='v61_single_bound_episode_observer.v1',
        watchdog_root=str(MASTER_ROOT), original_control_protocol_id=SOURCE_CONTROL_PROTOCOL_ID,
        original_bounded_observer=observer.observer_policy(),
        signals_policy=load_v59_module('finqa_v59_signals').signals_policy(),
        resource_override=resource_override(), scientific_worker_limit=6,
        only_one_independent_observer=True, original_scientific_root_unchanged=True,
        old_pure_CPU_observer_may_be_retired_only_after_scientific_processes_exit=True,
        retirement_requires_registered_PID_birth_and_records_owner_signal=True,
        other_processes_signaled=False, SIGKILL_protection_claimed=False)


def checked_control(root, science_root):
    root = episode_root(root)
    require(Path(science_root).resolve() == SCIENCE_ROOT, 'observer scientific root changed')
    value = checked_record(root / 'protocol/record.json')
    require(value['control_root'] == str(root) and value['scientific_root'] == str(SCIENCE_ROOT)
            and value['observer_policy'] == observer_policy(),
            'episode observer authorization differs')
    reference = value['implementation']
    manifest_path = MASTER_ROOT / 'implementation/record.json'
    require(Path(reference['path']).resolve() == manifest_path
            and hashlib.sha256(manifest_path.read_bytes()).hexdigest() == reference['sha256'],
            'observer master implementation reference changed')
    implementation = checked_record(manifest_path)
    require(implementation['id'] == reference['id'], 'observer master implementation identity differs')
    for name in ('finqa_v61_observer.py', 'finqa_v61_binding.py'):
        require(hashlib.sha256((MASTER_ROOT / 'implementation' / name).read_bytes()).hexdigest()
                == implementation['files'][name], 'episode observer source changed: ' + name)
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--science-root', type=Path, required=True)
    args = parser.parse_args()
    root = episode_root(args.root)
    load_v59_module('finqa_v59_signals').install(root / 'signals' / f'observer-{os.getpid()}',
        role='observer', context=dict(control_root=str(root), automatic_watchdog_root=str(MASTER_ROOT)))
    checked_control(root, args.science_root)
    original = load_v59_module('finqa_v59_observer').load_original()
    directory = root / 'observer'
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / 'owner.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        require(not (directory / 'launch/record.json').exists(), 'episode observer is single-use')
        print(json.dumps(original.Observer(root, SCIENCE_ROOT).run(), sort_keys=True))


if __name__ == '__main__':
    main()
