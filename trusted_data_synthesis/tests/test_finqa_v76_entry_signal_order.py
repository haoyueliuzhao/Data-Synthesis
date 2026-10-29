"""Fresh-process controls for parser -> actual signal install -> dispatch.

The child imports the actual entry and original frozen signal implementation.
Only scientific dispatch is replaced. No model or GPU worker is started, and
all signal observers/logs are local to the short-lived CPU test process.
"""
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys

import pytest

REPO = Path(__file__).resolve().parents[2]
SCRIPTS = REPO / 'trusted_data_synthesis/scripts'
HISTORICAL_ENTRY = REPO / ('trusted_data_synthesis/artifacts/finance_research_20260928/'
    'finqa_v6_01/v18_researcher_continuation_01/v76_fixed_demonstration_closed_loop_01/'
    'execution_revision_01/implementation/finqa_v76_entry.py')

CHILD = r'''
import importlib.util
import json
import os
from pathlib import Path
import sys

scripts, fixture_root, coordinate, historical = sys.argv[1:]
sys.path.insert(0, scripts)
if historical:
    spec = importlib.util.spec_from_file_location('finqa_v76_entry', historical)
    entry = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = entry
    spec.loader.exec_module(entry)
else:
    import finqa_v76_entry as entry

b, signals = entry.binding, entry.signals
root = Path(fixture_root).resolve()
root.mkdir(parents=True)
(root / 'implementation').mkdir()
b.ROOT = root
entry.__file__ = str(root / 'implementation/finqa_v76_entry.py')
# Use the actual frozen signal policy and source bindings, not a signal mock.
protocol = b.publish(root / 'protocol/record.json', dict(
    signal_policy=signals.signals_policy(),
    signal_source_bindings=signals.external_source_bindings()))
signals.require_early_install()
assert 'torch' not in sys.modules
assert 'finqa_v76_queue_base' not in sys.modules
assert 'finqa_v37_task_cache' not in sys.modules

if coordinate == 'A.class':
    job = 'step1192.shard00'
    attempt = root / 'points/step1192/shard00/attempts/attempt0001'
    argv = ['--mode','worker','--root',str(root),'--seed','137',
            '--stage',job,'--gpu-index','6','--attempt-root',str(attempt)]
elif coordinate == 'D.train':
    job = 'D.step1490.train'
    attempt = root / 'fixed/points/step1490/train/attempts/attempt0001'
    argv = ['--mode','worker','--root',str(root),'--seed','137',
            '--stage',job,'--gpu-index','7','--attempt-root',str(attempt)]
elif coordinate == 'A.generate':
    job = 'A.step1490.dev_greedy.shard0'
    attempt = root / 'evaluations/jobs' / job / 'attempts/attempt0001'
    argv = ['--mode','generate','--root',str(root),'--job',job,
            '--gpu','6','--attempt-root',str(attempt)]
else:
    raise AssertionError('unknown test coordinate')
for prefix in ('V76','V63','V56'):
    os.environ[prefix + '_ATTEMPT_DIR'] = str(attempt)
    os.environ[prefix + '_ATTEMPT_ID'] = 'attempt0001'
os.environ['V54_JOB_ID'] = job
os.environ['CUDA_VISIBLE_DEVICES'] = ''
dispatched = []

def cpu_only_dispatch(actual_root, args):
    observer = signals._original._OBSERVER
    assert observer is not None and not observer.closed.is_set()
    assert observer.receiver.is_alive() and observer.writer.is_alive()
    assert actual_root == root and args.attempt_root == attempt
    assert args.mode == ('generate' if coordinate == 'A.generate' else 'worker')
    assert (args.job if args.mode == 'generate' else args.stage) == job
    assert observer.role == args.mode
    assert observer.context['job_id'] == job
    assert observer.context['attempt_id'] == 'attempt0001'
    assert observer.context['v63_root'] == str(root)
    if 'torch' in sys.modules:
        assert not sys.modules['torch'].cuda.is_initialized()
    # Waiting for this CPU observer's startup log avoids accepting installation
    # merely because a mutable flag was set. It sends no signal to any process.
    observer.records.join()
    records = [json.loads(line) for line in (attempt / 'signals/received.jsonl').read_text().splitlines()]
    assert any(r['schema'] == 'v58_signal_observer_started.v1'
               and r['pid'] == os.getpid() and r['role'] == args.mode for r in records)
    dispatched.append(job)
    print('V76_TEST_DISPATCH_AFTER_REAL_SIGNAL_INSTALL=' + job)
    return {'schema':'v76_CPU_entry_order_fixture.v1','id':'test-only','status':'COMPLETE'}

entry._dispatch = cpu_only_dispatch
code = entry.main(argv)
assert code == 0 and dispatched == [job]
assert signals._original._OBSERVER.closed.is_set()
print('V76_TEST_ENTRY_COMPLETE=' + coordinate)
'''


def _child(tmp_path, coordinate, *, historical=False):
    env = dict(os.environ)
    env.pop('PYTHONPATH', None)
    # Fresh interpreter, not the pytest process with already imported torch or
    # scientific fixtures. The entry itself chooses its registered source path.
    return subprocess.run([sys.executable, '-c', CHILD, str(SCRIPTS),
        str(tmp_path/'isolated-root'),coordinate,str(HISTORICAL_ENTRY) if historical else ''],
        cwd=REPO,env=env,capture_output=True,text=True,timeout=60,check=False)


@pytest.mark.parametrize('coordinate',['A.class','D.train','A.generate'])
def test_actual_entry_installs_real_observer_before_scientific_dispatch(tmp_path, coordinate):
    result = _child(tmp_path,coordinate)
    assert result.returncode == 0, result.stdout + '\n' + result.stderr
    assert 'V76_TEST_DISPATCH_AFTER_REAL_SIGNAL_INSTALL=' in result.stdout
    assert 'V76_TEST_ENTRY_COMPLETE=' + coordinate in result.stdout


def test_frozen_revision01_worker_reproduces_pre_signal_scientific_import_failure(tmp_path):
    assert HISTORICAL_ENTRY.is_file(), 'the actual failed immutable revision01 entry must remain available'
    result = _child(tmp_path,'A.class',historical=True)
    assert result.returncode != 0
    assert 'signal observer must precede scientific imports' in result.stderr
    assert 'V76_TEST_DISPATCH_AFTER_REAL_SIGNAL_INSTALL=' not in result.stdout
    assert not (tmp_path/'isolated-root/points/step1192/shard00/attempts/attempt0001/signals').exists()
