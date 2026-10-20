"""Private resource adapters for both batch-one arms and six-worker admission.

The original lifetime and deferral implementations are compiled into private
namespaces. Only stage names, the new root/policy and replay stop-boundary
selection change; historical imported modules and files are not patched.
"""
from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
import sys
from types import ModuleType

import finqa_v63_binding as binding
binding.install_scientific_paths()
import finqa_v54_runtime as reference_base
import finqa_v56_runtime as reference_recovery
import finqa_v63_gpu_isolation as isolation

REPO, V18, ROOT = binding.REPO, binding.V18, binding.ROOT
GIB = reference_base.GIB
GPU_UUIDS, CPU_AFFINITY = reference_base.GPU_UUIDS, reference_base.CPU_AFFINITY
MINIMUM_FREE_GIB, HOST_STARTUP_GIB = reference_base.MINIMUM_FREE_GIB, reference_base.HOST_STARTUP_GIB
CUBLAS_WORKSPACE_CONFIG = reference_base.CUBLAS_WORKSPACE_CONFIG
worker_environment = reference_base.worker_environment
inventory, host_memory, process_memory, birth = (
    reference_base.inventory, reference_base.host_memory, reference_base.process_memory,
    reference_base.birth)
now = reference_base.now
require, checked, publish, entry, file_ref, read_ref, digest = (
    binding.require, binding.checked, binding.publish, binding.entry,
    binding.file_ref, binding.read_ref, binding.digest)


def kind(job):
    stage = job.get("stage")
    stages = {f"{phase}_{arm}": phase for arm in binding.ARMS
              for phase in ("feedback", "replay", "distribution", "train")}
    stages["generate"] = "generate"
    require(stage is None or stage in stages, "unregistered V63 scientific stage")
    values = [stages[stage]] if stage is not None else []
    values.extend(job[field] for field in ("kind", "memory_phase") if job.get(field) is not None)
    require(values and all(value in MINIMUM_FREE_GIB and value == values[0] for value in values),
            "V63 stage and resource phase differ")
    return values[0]


def resource_policy():
    policy = reference_base.resource_policy()
    policy.update(schema="v63_native_six_worker_resource_policy.v1",
        max_gpu_workers=binding.MAX_WORKERS,
        same_lifetime_memory_and_per_worker_limits=True,
        diagnostic_draw_buffers_and_VJPs_count_in_actual_resources=True)
    return policy


def resource_recovery_policy():
    policy = reference_recovery.resource_recovery_policy()
    policy.update(schema="v63_actual_durable_resource_recovery.v1",
        replay_checkpoint_formal_and_draw_accumulators_atomic=True,
        new_UNKNOWN_call_or_diagnostic_numeric_failure_retry=False)
    return policy


def _private(name, reference, replacements):
    path = Path(reference.__file__).resolve()
    old = binding.checked(binding.OLD_ROOT / "implementation/record.json")
    require(binding.sha(path) == old["sha256"][path.name],
            "the original resource implementation bytes changed")
    source = path.read_text()
    for before, after, count in replacements:
        require(source.count(before) == count, "resource adapter source structure changed")
        source = source.replace(before, after)
    module = ModuleType(name)
    module.__file__ = str(path)
    module.__package__ = ""
    sys.modules[name] = module
    exec(compile(source, str(path) + "::V63_private_resource_adapter", "exec"), module.__dict__)
    return module


_base = _private("_v63_frozen_resource_base", reference_base, [
    ('self.job.get("stage") != "replay_C05"',
     'self.job.get("stage") not in ("replay_C1", "replay_C05")', 1)])
_base.ROOT = ROOT
_base.kind = kind
_base.resource_policy = resource_policy
_base.publish = publish
_base.checked = checked
_durable = _private("_v63_frozen_resource_deferral", reference_recovery, [
    ("import finqa_v54_runtime as original", "import _v63_frozen_resource_base as original", 1),
    ('self.job.get("stage") != "replay_C05"',
     'self.job.get("stage") not in ("replay_C1", "replay_C05")', 1)])
_durable.ROOT = ROOT
_durable.resource_policy = resource_policy
_durable.resource_recovery_policy = resource_recovery_policy
_durable.publish = publish
_durable.checked = checked
ExplicitStop, ResourceGateError = _base.ExplicitStop, _base.ResourceGateError
ResourceDeferred = _durable.ResourceDeferred
LifetimeResourceFailure = _durable.LifetimeResourceFailure
R3CapacityError = _durable.R3CapacityError
_SharedGuard = isolation.guarded_class(_durable)


class ResourceGuard(_SharedGuard):
    def __init__(self, root, job, gpu_index, *, torch_module=None):
        require(Path(root).resolve() == ROOT, "foreign scientific resource root")
        protocol = checked(ROOT / "protocol/record.json")
        require(protocol["gpu_isolation_policy"] == isolation.gpu_isolation_policy()
                and protocol["max_gpu_workers"] == binding.MAX_WORKERS
                and protocol["max_workers_per_gpu"] == 1,
                "registered shared-GPU or worker-slot policy changed")
        super().__init__(root, job, gpu_index, torch_module=torch_module)


@contextmanager
def execution_context(root, job, gpu_index):
    with ResourceGuard(root, job, gpu_index) as guard:
        yield guard


def controller_runtime():
    return isolation.install_controller_runtime(sys.modules[__name__])
