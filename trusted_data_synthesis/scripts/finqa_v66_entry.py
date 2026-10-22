"""Cold V66 entry; unchanged legal-stop observation precedes science imports."""
from __future__ import annotations

import argparse
import importlib
import json
import os
from pathlib import Path
import sys

import finqa_v66_binding as b


def early_observer(root, args):
    allowed = {'finqa_v66_binding.py', 'finqa_v66_entry.py', 'finqa_v64_binding.py',
               'finqa_v63_binding.py', 'finqa_v63_signals.py', 'finqa_v59_signals.py',
               'finqa_v58_signals.py', 'finqa_v58_observer.py'}
    for name, module in sys.modules.items():
        origin = getattr(module, '__file__', None)
        b.require(not (name == 'torch' or name.startswith('torch.')
            or name == 'trusted_synthesis' or name.startswith('trusted_synthesis.')
            or origin and Path(origin).name.startswith('finqa_') and Path(origin).name not in allowed),
            'V66 signal receipt must be installed before scientific imports: ' + name)
    b.require(os.getuid() == os.geteuid() == b.OWNER_UID, 'legal stop filter requires original UID1004')
    protocol = b.checked(root / 'protocol/record.json')
    signals = b.source_module('finqa_v63_signals')
    b.require(protocol['signal_policy'] == signals.signals_policy()
              and protocol['signal_source_bindings'] == signals.external_source_bindings(),
              'unchanged signal policy/source binding required')
    if args.mode == 'worker':
        directory = args.attempt_root / 'signals'
    elif args.mode == 'run':
        directory = root / 'controllers' / f'attempt{args.controller_attempt:04d}' / 'signals'
    else:
        directory = root / ('supervisor/signals' if args.mode == 'supervise' else 'frozen_worker_import_verification/signals')
    return signals._reference().install(directory, role=args.mode, context=dict(
        mode=args.mode, control_root=str(root), control_protocol_id=protocol['id'],
        scientific_root=str(b.SCIENTIFIC_ROOT), scientific_protocol_id=b.BASE_PROTOCOL_ID,
        job_id=os.environ.get('V54_JOB_ID'), attempt_id=os.environ.get('V63_ATTEMPT_ID'),
        inherited_signal_policy_unchanged=True, CPU_import_check=args.mode == 'check-imports'))


def check_imports():
    registration = importlib.import_module('finqa_v66_registration')
    protocol = registration.checked_protocol()
    manifest = registration.checked_implementation()
    entry = b.source_module('finqa_v63_entry')
    for name in (*entry.WORKER_IMPORTS, *entry.RECOVERY_IMPORTS, *entry.NEW_IMPORTS):
        importlib.import_module(name)
    for filename in registration.FILES:
        importlib.import_module(filename[:-3])
    _, runtime = b.source_module('finqa_v63_training').runtime()
    b.require(not runtime.torch.cuda.is_initialized(), 'CPU check must not initialize CUDA')
    old_control = b.checked(b.OLD_CONTROL / 'implementation/record.json')
    remaining, operational = {}, []
    for name, module in sys.modules.items():
        origin = getattr(module, '__file__', None)
        if not origin:
            continue
        path = Path(origin).resolve()
        if path.name.startswith('finqa_v66_') or path.parent == b.OLD_CONTROL / 'implementation':
            directory, implementation = ((b.ROOT / 'implementation', manifest)
                if path.name.startswith('finqa_v66_') else (b.OLD_CONTROL / 'implementation', old_control))
            b.require(path.parent == directory and path.name in implementation['sha256']
                      and b.sha(path) == implementation['sha256'][path.name],
                      'non-frozen operational implementation: ' + str(path))
            operational.append(dict(module=name, path=str(path), sha256=b.sha(path)))
        else:
            remaining[name] = module
    old_binding = b.source_module('finqa_v63_binding')
    verified = entry.verify_imported_modules(b.SCIENTIFIC_ROOT, b.checked(b.SOURCE / 'record.json'),
        b.checked(old_binding.OLD_ROOT / 'implementation/record.json'), protocol['signal_source_bindings'],
        modules=remaining)
    body = dict(schema='v66_actual_frozen_worker_CPU_import_check.v1', status='PASS',
        control_protocol_id=protocol['id'], implementation_id=manifest['id'],
        CUDA_initialized=False, scientific_calls=0, optimizer_updates=0,
        operational_sources=operational, **verified)
    return dict(body, id=b.digest(body))


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('--mode', choices=('run', 'supervise', 'worker', 'check-imports'), required=True)
    parser.add_argument('--root', type=Path, default=b.ROOT)
    parser.add_argument('--controller-attempt', type=int, default=1)
    parser.add_argument('--seed', type=int)
    parser.add_argument('--stage')
    parser.add_argument('--gpu-index', type=int)
    parser.add_argument('--attempt-root', type=Path)
    args = parser.parse_args(argv)
    root = args.root.resolve()
    b.require(root == b.ROOT and Path(__file__).resolve().parent == root / 'implementation',
              'production entry must be the independent frozen V66 implementation')
    if args.mode == 'worker':
        b.require(args.seed == 389 and args.stage in b.STAGES and args.gpu_index in range(8)
                  and args.attempt_root is not None, 'unregistered V66 worker coordinate')
        args.attempt_root = args.attempt_root.resolve()
        b.require(args.attempt_root.parent == b.SCIENTIFIC_ROOT / f'stages/seed389/{args.stage}/attempts'
                  and os.environ.get('V54_JOB_ID') == 'seed389.' + args.stage
                  and os.environ.get('V66_CONTROL_ROOT') == str(root), 'V66 worker launch identity changed')
    observer = early_observer(root, args)
    try:
        registration = importlib.import_module('finqa_v66_registration')
        registration.initialize()
        protocol = registration.checked_protocol()
        registration.checked_implementation()
        if args.mode == 'check-imports':
            result = check_imports()
        elif args.mode == 'worker':
            b.require(os.environ.get('V66_CONTROL_PROTOCOL_ID') == protocol['id'], 'worker protocol changed')
            result = importlib.import_module('finqa_v66_worker').run(b.SCIENTIFIC_ROOT,
                args.seed, args.stage, args.gpu_index, attempt_root=args.attempt_root)
        else:
            controller = importlib.import_module('finqa_v66_controller')
            result = (controller.supervise(root) if args.mode == 'supervise' else
                      controller.Controller(root, controller_attempt=args.controller_attempt).run())
        print(json.dumps(result if args.mode == 'check-imports' else
                         {k: result.get(k) for k in ('schema', 'id', 'status')}, sort_keys=True))
        return 75 if result.get('status') == 'CONTROLLER_TRANSIENT_FAILURE' else (0 if result.get('status') in ('PASS', 'COMPLETE') else 2)
    finally:
        observer.close()


if __name__ == '__main__':
    raise SystemExit(main())
