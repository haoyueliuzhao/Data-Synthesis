import argparse
import copy
import json
import sys
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument('root', type=Path)
parser.add_argument('--formal', action='store_true')
args = parser.parse_args()
root = args.root.resolve()
sys.path.insert(0, str(root / 'implementation'))
import finqa_v45_controller as control
import finqa_v45_admission as admission
import finqa_v45_worker as worker
import finqa_v45_evaluation as evaluation
import finqa_v45_handoff as handoff
import finqa_v45_supervisor as supervisor

source = control.checked_source_bundle()
assert len(source['sha256']) == 74 and len(control.FILES) == 7
assert control.MAX_GPU_WORKERS == 5
assert control.DISPATCH_ORDER == admission.DISPATCH_ORDER == (5, 2, 0, 4, 3, 7, 1, 6)
for name, expected in source['sha256'].items():
    assert control.sha(root / 'implementation' / name) == expected
for name in control.FILES:
    assert control.sha(root / 'implementation' / name) == control.sha(control.REPO / 'trusted_data_synthesis/scripts' / name)
assert len(list((root / 'implementation').glob('*.py'))) == 81
worker._checked_entry(root, control)
evaluation._checked_entry(root, control)
handoff._runtime_sources(root)
assert Path(supervisor.original.__file__).resolve() == root / 'implementation/finqa_v43_supervisor.py'
with worker.bound_execution(control), worker.original.bound_execution(control), worker.original.original.bound_parent_control():
    dependencies = worker.original.original.dependencies(root)
assert not dependencies.rt.torch.cuda.is_initialized()
assert Path(evaluation.original._parent_module(root, control).__file__).resolve() == root / 'implementation/finqa_v37_evaluation.py'
plan = copy.deepcopy(control.verifier.checked_protocol(control.PARENT_ROOT))
plan.update(
    schema=control.PROTOCOL_SCHEMA,
    max_gpu_workers=5,
    max_workers_per_gpu=1,
    dispatch_priority=list(control.DISPATCH_ORDER),
    gpu_admission_policy=control.policy_record(),
    host_admission_policy=control.host_policy_record(),
    host_ram_admission_changed=True,
    host_ram_runtime_hard_gates_unchanged=True,
)
admission.validate_plan(plan)
gib = 1024**3
assert control.parent.HOST_RAM == dict(shard_rss_limit_bytes=160*gib, coordinator_rss_limit_bytes=192*gib, reserve_bytes=96*gib)
active = [dict(stage=s, rss_bytes=int(rss*gib), peak_rss_bytes=int(peak*gib)) for s,rss,peak in [
    ('replay_R3',3.68,16.42), ('replay_R3',4.10,16.41), ('train',2.93,16.25),
]]
needed = admission.host_memory_requirement('shard00', active)
assert 389*gib < needed < 390*gib
body = dict(
    schema='v45_frozen_cpu_dependencies_and_host_policy_acceptance.v1',
    at=control.now(), status='PASS', implementation_files=81, original_files_unchanged=74,
    max_gpu_workers=5, dispatch_priority=list(control.DISPATCH_ORDER),
    host_admission_policy=control.host_policy_record(),
    example_new_class_required_bytes=needed,
    unchanged_hard_host_gates=control.parent.HOST_RAM,
    actual_dependency_paths_checked=True, cuda_initialized=False,
    models_constructed=0, scientific_stages_started=0, api_calls=0,
    tensors_or_endpoint_answers_read=False,
    checker_sha256=control.sha(Path(__file__)),
)
if args.formal:
    implementation = control.checked_implementation(root)
    preparation = control.checked_preparation()
    body.update(implementation=control.entry(root / 'implementation/record.json'), preparation=control.entry(root / 'preparation/record.json'))
    record = control.publish(root / 'cpu_acceptance/record.json', body)
    print(json.dumps(dict(status=record['status'], id=record['id'], root=str(root), implementation_id=implementation['id'], preparation_id=preparation['id'])))
else:
    print(json.dumps(dict(status='PASS', root=str(root), files=81, required_gib=needed/gib, cuda_initialized=False)))
