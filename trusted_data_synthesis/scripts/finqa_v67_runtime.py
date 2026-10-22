"""Registered roots and two GPU lanes; all per-worker resource gates unchanged."""
from __future__ import annotations

from pathlib import Path
import sys
from types import ModuleType

import finqa_v67_binding as binding

original = binding.early_module('finqa_v65_runtime')
source = Path(original.__file__).read_text()
binding.require(source.count('import finqa_v65_binding as binding') == 3,
                'frozen generation resource adapter import structure changed')
source = source.replace('finqa_v65_', 'finqa_v67_').replace('_v65_', '_v67_')
needle = "('import finqa_v63_binding as binding', 'import finqa_v67_binding as binding', 1),"
binding.require(source.count(needle) == 1, 'frozen base resource adapter changed')
source = source.replace(needle, needle + "\n" + "\n".join((
    "    ('max_gpu_workers=binding.MAX_WORKERS,', 'max_gpu_workers=binding.MAX_WORKERS, max_workers_per_gpu=binding.MAX_WORKERS_PER_GPU,', 1),",
    "    ('protocol[\"max_workers_per_gpu\"] == 1', 'protocol[\"max_workers_per_gpu\"] == binding.MAX_WORKERS_PER_GPU', 1),",
)))
_runtime = ModuleType('_v67_private_generation_resource_runtime')
_runtime.__file__ = str(Path(original.__file__).resolve())
_runtime.__package__ = ''
sys.modules[_runtime.__name__] = _runtime
exec(compile(source, _runtime.__file__ + '::V67_registered_root_adapter', 'exec'), _runtime.__dict__)

_GenerationGuard = _runtime.ResourceGuard


class ResourceGuard(_GenerationGuard):
    def __init__(self, root, job, gpu_index, **kwargs):
        binding.require(Path(root).resolve() == binding.ROOT
                        and job.get('kind', 'generate') == job.get('stage') == 'generate',
                        'V67 resources are generation-only in their registered root')
        protocol = binding.checked(Path(root) / 'protocol/record.json')
        slots = binding.gpu_slot_policy()
        binding.require(protocol['gpu_slot_policy'] == slots
                        and protocol['max_workers_per_gpu'] == binding.MAX_WORKERS_PER_GPU
                        and protocol['own_max_workers_per_gpu'] == binding.MAX_NEW_WORKERS_PER_GPU
                        and protocol['gpu_lease_root'] == slots['second_slot_lease_root']
                        and protocol['legacy_gpu_lease_root'] == slots['legacy_gpu_lease_root'],
                        'V67 requires its sole secondary lane and the untouched exclusive legacy lane')
        super().__init__(root, job, gpu_index, **kwargs)


# The original contextmanager resolves ResourceGuard in this private namespace.
# Its V54 __enter__ retains the exact path/inode/WRITE-FLOCK descriptor checks;
# only the new protocol's gpu_lease_root selects the secondary global lane.
_runtime.ResourceGuard = ResourceGuard
execution_context = _runtime.execution_context
controller_runtime = _runtime.controller_runtime
resource_policy = _runtime.resource_policy
resource_recovery_policy = _runtime.resource_recovery_policy
memory_protection_policy = _runtime.memory_protection_policy


def __getattr__(name):
    return getattr(_runtime, name)
