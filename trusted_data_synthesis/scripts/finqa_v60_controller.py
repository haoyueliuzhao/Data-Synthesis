"""Per-episode control wrapper; never restart the initial V59 one-shot entry."""
from __future__ import annotations

import argparse
import hashlib
import importlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

from finqa_v60_binding import (MASTER_ROOT, PYTHON, REPO, SCIENCE_ROOT,
    SOURCE_CONTROL_ROOT, SOURCE_CONTROL_PROTOCOL_ID, checked_record, digest,
    episode_root, load_v59_module, require)

LEGACY_ROOT = SCIENCE_ROOT / 'signal_recovery_02'
LEGACY_IMPLEMENTATION_ID = '280d0bb04947cf02d2c0c2c610205ab8df22ed078a50828ab7ba1227fdf0f313'
LEGACY_CONTROLLER_SHA256 = '6236043316b750bd7b49e31906fea91bf87abca50fff060c3c97afc84d51a214'


def arguments(*, early=False):
    parser = argparse.ArgumentParser(description=__doc__, add_help=not early)
    parser.add_argument('action', choices=('run', 'supervise', 'check-imports'))
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--controller-attempt', type=int, default=1)
    return parser.parse_known_args()[0] if early else parser.parse_args()


if __name__ == '__main__':
    early = arguments(early=True)
    load_v59_module('finqa_v59_signals').install(
        early.root / 'signals' / f'{early.action}-{os.getpid()}',
        role='supervisor' if early.action == 'supervise' else 'controller',
        context=dict(control_root=str(early.root), controller_attempt=early.controller_attempt,
                     automatic_watchdog_root=str(MASTER_ROOT)))


def adapter_contract(control_root=None):
    value = dict(schema='v60_independent_episode_frozen_control_adapter.v1',
        watchdog_root=str(MASTER_ROOT), episode_pattern='episodes/episode[0-9]{4,}',
        scientific_root=str(SCIENCE_ROOT), initial_control_root=str(SOURCE_CONTROL_ROOT),
        initial_control_protocol_id=SOURCE_CONTROL_PROTOCOL_ID,
        legacy_implementation_id=LEGACY_IMPLEMENTATION_ID,
        legacy_controller_sha256=LEGACY_CONTROLLER_SHA256,
        controller_entry=str(MASTER_ROOT / 'implementation/finqa_v60_controller.py'),
        worker_entry=str(SOURCE_CONTROL_ROOT / 'implementation/finqa_v59_worker.py'),
        registration_module='finqa_v60_registration',
        actual_argv_mutated_before_Popen_and_launch_record=True,
        V59_signal_and_GPU_owner_policy_exactly_reused=True,
        original_science_helper_paths_and_resource_gates_preserved=True,
        initial_V59_controller_not_restarted_or_hot_patched=True)
    if control_root is not None:
        value['control_root'] = str(episode_root(control_root))
    return value


class ImportRouter:
    def import_module(self, name, package=None):
        return importlib.import_module('finqa_v60_registration' if name == 'finqa_v57_registration' else name, package)

    def __getattr__(self, name):
        return getattr(importlib, name)


class ProcessRouter:
    def __init__(self, delegate, root):
        self.delegate = delegate
        self.redirect = {
            str(root / 'implementation/finqa_v57_controller.py'): str(MASTER_ROOT / 'implementation/finqa_v60_controller.py'),
            str(root / 'implementation/finqa_v57_worker.py'): str(SOURCE_CONTROL_ROOT / 'implementation/finqa_v59_worker.py')}

    def Popen(self, command, *args, **kwargs):
        if isinstance(command, (list, tuple)):
            matches = [index for index, value in enumerate(command) if isinstance(value, str) and value in self.redirect]
            if matches:
                require(isinstance(command, list) and len(matches) == 1,
                        'one mutable exact registered control argv required')
                index = matches[0]
                require(index >= 2 and command[index - 2:index] == [str(PYTHON), '-u'],
                        'registered Python executable argument is required')
                command[index] = self.redirect[command[index]]
        return self.delegate.Popen(command, *args, **kwargs)

    def __getattr__(self, name):
        return getattr(self.delegate, name)


def private_controller(root, *, CPU_check=False):
    root = Path(root).resolve()
    require((CPU_check and root == MASTER_ROOT) or episode_root(root) == root,
            'controller requires its authorized independent episode')
    source = LEGACY_ROOT / 'implementation/finqa_v57_controller.py'
    manifest = checked_record(source.parent / 'record.json')
    require(manifest['id'] == LEGACY_IMPLEMENTATION_ID
            and manifest['files'][source.name] == LEGACY_CONTROLLER_SHA256
            and hashlib.sha256(source.read_bytes()).hexdigest() == LEGACY_CONTROLLER_SHA256,
            'original frozen controller bytes changed')
    name = '_v60_private_control_' + digest(str(root))[:16]
    if name not in sys.modules:
        spec = importlib.util.spec_from_file_location(name, source)
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
        require(module.ROOT == LEGACY_ROOT and module.SCIENTIFIC_ROOT == SCIENCE_ROOT,
                'frozen controller root identity differs')
        module.ROOT = root
        module.importlib = ImportRouter()
        module.subprocess = ProcessRouter(subprocess, root)
        module._v60_root = root
    result = sys.modules[name]
    require(result._v60_root == root and result.ROOT == root,
            'private controller episode was changed')
    return result


def Controller(root, *, controller_attempt=1, runtime=None, registration=None, scientific_registration=None):
    root = episode_root(root)
    frozen = private_controller(root)
    registration = registration or importlib.import_module('finqa_v60_registration')
    runtime = runtime or importlib.import_module('finqa_v54_runtime')
    runtime = load_v59_module('finqa_v59_gpu_isolation').install_controller_runtime(runtime)
    return frozen.Controller(root, controller_attempt=controller_attempt, runtime=runtime,
        registration=registration, scientific_registration=scientific_registration)


def main():
    args = arguments()
    if args.action == 'check-imports':
        importlib.import_module('finqa_v60_registration').checked_master_protocol(MASTER_ROOT)
        frozen = private_controller(MASTER_ROOT, CPU_check=True)
        result = frozen.check_imports()
    else:
        root = episode_root(args.root)
        frozen = private_controller(root)
        result = (frozen.supervise(root) if args.action == 'supervise' else
                  Controller(root, controller_attempt=args.controller_attempt).run())
    print(json.dumps(dict(status=result['status'], id=result['id']), sort_keys=True))
    if result['status'] == 'CONTROLLER_TRANSIENT_FAILURE':
        return frozen.TEMPORARY_CONTROLLER_EXIT
    return 0 if result['status'] in ('COMPLETE', 'CPU_IMPORTS_VERIFIED') else 2


if __name__ == '__main__':
    raise SystemExit(main())
