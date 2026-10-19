"""Fresh V59 observation entry over the byte-bound V58 CPU observer.

Only the control namespace and authorized signal receipt policy change. The
observer never acquires GPU resources or sends signals to another process.
"""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import importlib.util
import json
import os
import sys
from pathlib import Path

REPO = Path('/data1/zhuxinrui/projects/Data-Synthesis')
SCIENCE_ROOT = REPO / 'trusted_data_synthesis/artifacts/finance_research_20260928/finqa_v6_01/v18_researcher_continuation_01/v54_feedback_temperature_01/automatic_recovery_01'
ROOT = SCIENCE_ROOT / 'signal_recovery_04'
SOURCE_ROOT = SCIENCE_ROOT / 'signal_recovery_03'
SOURCE_IMPLEMENTATION_ID = '63525be8d361117a8dd0ee2f10265d9fa97e675da969e622580fadece8060e6f'
SOURCE_SHA256 = '1431a463064cf5c0aa0e86a455ae0cf3d9f662ff7142cd953807604406fbc55b'


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
        separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def checked(path):
    value = json.loads(Path(path).read_bytes())
    require(value['id'] == digest({k: v for k, v in value.items() if k != 'id'}),
            'observation record identity changed: ' + str(path))
    return value


def load_original():
    implementation = SOURCE_ROOT / 'implementation'
    manifest = checked(implementation / 'record.json')
    source = implementation / 'finqa_v58_observer.py'
    require(manifest['id'] == SOURCE_IMPLEMENTATION_ID
        and manifest['files'][source.name] == SOURCE_SHA256
        and hashlib.sha256(source.read_bytes()).hexdigest() == SOURCE_SHA256,
        'the original bounded CPU observer source changed')
    name = '_v59_frozen_v58_process_observer'
    if name not in sys.modules:
        spec = importlib.util.spec_from_file_location(name, source)
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
    module = sys.modules[name]
    require(Path(module.__file__).resolve() == source, 'observer module origin differs')
    return module


def observer_policy():
    from finqa_v59_signals import signals_policy
    return dict(schema='v59_bound_original_observer_with_narrow_TERM_policy.v1',
        original_observer_sha256=SOURCE_SHA256,
        original_observer_implementation_id=SOURCE_IMPLEMENTATION_ID,
        original_bounded_observer=load_original().observer_policy(),
        control_root=str(ROOT), scientific_root=str(SCIENCE_ROOT),
        signals_policy=signals_policy(), signal_install_before_observer_threads=True,
        process_UID_changed=False, system_or_other_project_settings_changed=False,
        SIGKILL_protection_claimed=False)


def checked_control(root, science_root):
    require(Path(root).resolve() == ROOT and Path(science_root).resolve() == SCIENCE_ROOT,
            'observer requires the registered V59 control/scientific roots')
    protocol = checked(ROOT / 'protocol/record.json')
    require(protocol['control_root'] == str(ROOT)
        and protocol['scientific_root'] == str(SCIENCE_ROOT)
        and protocol['observer_policy'] == observer_policy(),
        'new observation authorization or inherited policy differs')
    reference = protocol['implementation']
    manifest_path = ROOT / 'implementation/record.json'
    require(Path(reference['path']).resolve() == manifest_path
        and hashlib.sha256(manifest_path.read_bytes()).hexdigest() == reference['sha256'],
        'new observation implementation reference changed')
    manifest = checked(manifest_path)
    require(manifest['id'] == reference['id'], 'new implementation identity differs')
    for name, expected in manifest['files'].items():
        require(Path(name).name == name and name.startswith('finqa_v59_'),
                'unexpected observation bundle member')
        require(hashlib.sha256((ROOT / 'implementation' / name).read_bytes()).hexdigest() == expected,
                'new observation source changed: ' + name)
    return protocol


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--science-root', type=Path, required=True)
    args = parser.parse_args()
    from finqa_v59_signals import install
    # Runs before the inherited observer starts its writer thread. Its ordinary
    # main-thread TERM/INT handler remains effective for allowed stop signals.
    install(args.root / 'signals' / f'observer-{os.getpid()}', role='observer',
            context=dict(control_root=str(args.root), scientific_root=str(args.science_root)))
    checked_control(args.root, args.science_root)
    original = load_original()
    directory = args.root / 'observer'
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / 'owner.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        require(not (directory / 'launch/record.json').exists(),
                'observer is single-use and is not automatically relaunched')
        print(json.dumps(original.Observer(args.root, args.science_root).run(), sort_keys=True))


if __name__ == '__main__':
    main()
