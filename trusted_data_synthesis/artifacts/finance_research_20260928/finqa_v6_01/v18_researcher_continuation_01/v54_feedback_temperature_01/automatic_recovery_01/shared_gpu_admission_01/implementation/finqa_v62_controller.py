"""Cold six-worker control amendment over unchanged V56 scientific state.

The original constructor still checks the real four-worker scientific protocol.
Only private scheduling call sites consume the independently registered six-
worker amendment. No shared base module, scientific record or source is changed.
"""
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
import types

from finqa_v62_binding import (MASTER_ROOT, PYTHON, REPO, SCIENCE_ROOT,
    SOURCE_CONTROL_ROOT, SOURCE_CONTROL_PROTOCOL_ID, checked_record, digest,
    episode_root, load_v59_module, require, resource_override)

LEGACY_ROOT = SCIENCE_ROOT / 'signal_recovery_02'
LEGACY_IMPLEMENTATION_ID = '280d0bb04947cf02d2c0c2c610205ab8df22ed078a50828ab7ba1227fdf0f313'
LEGACY_CONTROLLER_SHA256 = '6236043316b750bd7b49e31906fea91bf87abca50fff060c3c97afc84d51a214'
ORIGINAL_WORKERS, EFFECTIVE_WORKERS = 4, 6


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


def resource_override_contract():
    return resource_override()


def gpu_isolation():
    source = Path(__file__).resolve().with_name('finqa_v62_gpu_isolation.py')
    name = '_v62_controller_bound_gpu_isolation'
    if name not in sys.modules:
        spec = importlib.util.spec_from_file_location(name, source)
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
    result = sys.modules[name]
    require(Path(result.__file__).resolve() == source, 'V62 GPU helper origin changed')
    return result


def adapter_contract(control_root=None):
    value = dict(schema='v62_private_six_worker_control_adapter.v1',
        watchdog_root=str(MASTER_ROOT), episode_pattern='episodes/episode[0-9]{4,}',
        scientific_root=str(SCIENCE_ROOT), initial_control_root=str(SOURCE_CONTROL_ROOT),
        initial_control_protocol_id=SOURCE_CONTROL_PROTOCOL_ID,
        legacy_implementation_id=LEGACY_IMPLEMENTATION_ID,
        legacy_controller_sha256=LEGACY_CONTROLLER_SHA256,
        controller_entry=str(MASTER_ROOT / 'implementation/finqa_v62_controller.py'),
        worker_entry=str(MASTER_ROOT / 'implementation/finqa_v62_worker.py'),
        registration_module='finqa_v62_registration',
        actual_argv_mutated_before_Popen_and_launch_record=True,
        original_scientific_constructor_validates_cap_four_before_override=True,
        original_scientific_protocol_object_contents_and_ID_unchanged=True,
        shared_base_module_or_MAX_WORKERS_mutated=False,
        private_overrides=['V57_run_base.can_dispatch', 'V54_acquire_global_can_dispatch',
                           'control_journal_and_status_effective_limit_reporting'],
        acquire_function_code_and_all_RAM_GPU_admission_functions_unchanged=True,
        original_logical_class_shards=4, original_evaluation_job_count=45,
        V59_signal_policy_exactly_reused=True,
        GPU_owner_exclusion_removed_only_by_new_V62_policy=True,
        initial_V59_controller_not_restarted_or_hot_patched=True,
        resource_override=resource_override_contract())
    if control_root is not None:
        value['control_root'] = str(episode_root(control_root))
    return value


def can_dispatch(active):
    """Initialization, resource waiting and draining all remain in active."""
    require(len(active) <= EFFECTIVE_WORKERS, 'registered six-worker cap exceeded')
    gpus = [child.gpu for child in active.values()]
    require(len(gpus) == len(set(gpus)), 'more than one experiment worker on a physical GPU')
    require(all(type(gpu) is int and 0 <= gpu <= 7 for gpu in gpus), 'unregistered physical GPU')
    return len(active) < EFFECTIVE_WORKERS


def route_function(function, **replacements):
    """Same frozen function code, with a private control-only global lookup."""
    namespace = dict(function.__globals__)
    namespace.update(replacements)
    result = types.FunctionType(function.__code__, namespace, function.__name__,
                                function.__defaults__, function.__closure__)
    result.__kwdefaults__ = function.__kwdefaults__
    result.__annotations__ = dict(function.__annotations__)
    result.__module__ = function.__module__
    return result


class DispatchBase:
    def __init__(self, delegate, root, evaluation):
        self.delegate, self.root, self.evaluation = delegate, Path(root), evaluation

    def can_dispatch(self, active):
        return can_dispatch(active)

    def _status(self, path, value):
        path = Path(path)
        if path in (self.root / 'journal/state.json', self.root / 'queue/status.json'):
            require(value.get('schema') in ('v57_actual_job_attempt_journal.v1', 'v57_per_job_queue.v1')
                    and isinstance(value.get('control_protocol_id'), str),
                    'only the registered episode journal/status may receive the resource amendment')
            had_id = 'id' in value
            value = {key: item for key, item in value.items() if key != 'id'}
            value.update(max_gpu_workers=EFFECTIVE_WORKERS, effective_max_gpu_workers=EFFECTIVE_WORKERS,
                original_scientific_max_gpu_workers=ORIGINAL_WORKERS, max_workers_per_gpu=1,
                resource_override_protocol_id=value['control_protocol_id'],
                resource_override_sha256=digest(resource_override_contract()))
            if had_id:
                value = self.evaluation.bound(value)
        return self.delegate._status(path, value)

    def __getattr__(self, name):
        return getattr(self.delegate, name)


def controller_class(original_controller, original_base):
    # The original acquire body invokes its module-global can_dispatch. Only
    # this function's private globals change; its host/GPU admission stays.
    acquire = route_function(original_base.Controller.acquire, can_dispatch=can_dispatch)

    class SixWorkerController(original_controller):
        def __init__(self, *args, **kwargs):
            self._v62_override_applied = False
            super().__init__(*args, **kwargs)
            require(original_base.MAX_WORKERS == ORIGINAL_WORKERS
                    and self.protocol['max_gpu_workers'] == ORIGINAL_WORKERS,
                    'original scientific constructor/protocol must still validate its actual cap four')
            control = self.control_protocol
            require(control['original_scientific_max_gpu_workers'] == ORIGINAL_WORKERS
                    and control['max_gpu_workers'] == EFFECTIVE_WORKERS
                    and control['per_gpu_workers'] == 1
                    and control['scientific_protocol_id'] == self.protocol['id']
                    and control['resource_override'] == resource_override_contract(),
                    'a separately bound six-worker control amendment is required')
            self._v62_override_applied = True

        def acquire(self, job):
            require(self._v62_override_applied, 'resource override cannot run before original construction completes')
            return acquire(self, job)

    SixWorkerController.__name__ = 'V62SixWorkerController'
    SixWorkerController._v62_acquire_function = acquire
    return SixWorkerController


class ImportRouter:
    def import_module(self, name, package=None):
        return importlib.import_module('finqa_v62_registration' if name == 'finqa_v57_registration' else name, package)

    def __getattr__(self, name):
        return getattr(importlib, name)


class ProcessRouter:
    def __init__(self, delegate, root):
        self.delegate = delegate
        self.redirect = {
            str(root / 'implementation/finqa_v57_controller.py'): str(MASTER_ROOT / 'implementation/finqa_v62_controller.py'),
            str(root / 'implementation/finqa_v57_worker.py'): str(MASTER_ROOT / 'implementation/finqa_v62_worker.py')}

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
    name = '_v62_private_control_' + digest(str(root))[:16]
    if name not in sys.modules:
        spec = importlib.util.spec_from_file_location(name, source)
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
        require(module.ROOT == LEGACY_ROOT and module.SCIENTIFIC_ROOT == SCIENCE_ROOT,
                'frozen controller root identity differs')
        original_base, original_controller = module.base, module.Controller
        require(original_base.MAX_WORKERS == ORIGINAL_WORKERS, 'shared scientific base was already altered')
        module.ROOT = root
        module.importlib = ImportRouter()
        module.subprocess = ProcessRouter(subprocess, root)
        module.base = DispatchBase(original_base, root, module.evaluation)
        module.Controller = controller_class(original_controller, original_base)
        module._v62_root, module._v62_original_base = root, original_base
    result = sys.modules[name]
    require(result._v62_root == root and result.ROOT == root
            and result._v62_original_base.MAX_WORKERS == ORIGINAL_WORKERS,
            'private episode or original shared base changed')
    return result


def Controller(root, *, controller_attempt=1, runtime=None, registration=None, scientific_registration=None):
    root = episode_root(root)
    frozen = private_controller(root)
    registration = registration or importlib.import_module('finqa_v62_registration')
    runtime = runtime or importlib.import_module('finqa_v54_runtime')
    runtime = gpu_isolation().install_controller_runtime(runtime)
    return frozen.Controller(root, controller_attempt=controller_attempt, runtime=runtime,
        registration=registration, scientific_registration=scientific_registration)


def main():
    args = arguments()
    if args.action == 'check-imports':
        importlib.import_module('finqa_v62_registration').checked_master_protocol(MASTER_ROOT)
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
