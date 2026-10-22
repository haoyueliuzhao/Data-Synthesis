"""Private root adaptation of the unchanged lifetime/shared-GPU gates."""
from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
import sys
from types import ModuleType

import finqa_v65_binding as binding


def _compile(name, original, replacements):
    source = Path(original.__file__).read_text()
    for before, after, count in replacements:
        binding.require(source.count(before) == count, 'registered resource adapter structure changed')
        source = source.replace(before, after)
    module = ModuleType(name)
    module.__file__ = str(Path(original.__file__).resolve())
    module.__package__ = ''
    sys.modules[name] = module
    exec(compile(source, module.__file__ + '::V65_private_resource_adapter', 'exec'), module.__dict__)
    return module


_original_runtime = binding.source_module('finqa_v63_runtime')
_source = Path(_original_runtime.__file__).read_text()
_reference = _compile('_v65_reference_resource_runtime', _original_runtime, [
    ('import finqa_v63_binding as binding', 'import finqa_v65_binding as binding', 1),
    ('_v63_frozen_resource_base', '_v65_frozen_resource_base', _source.count('_v63_frozen_resource_base')),
    ('_v63_frozen_resource_deferral', '_v65_frozen_resource_deferral', _source.count('_v63_frozen_resource_deferral')),
])
_old_protection = binding.predecessor_module('finqa_v64_runtime')
_protection_source = Path(_old_protection.__file__).read_text()
_protection = _compile('_v65_private_protection_runtime', _old_protection, [
    ('import finqa_v64_binding as binding', 'import finqa_v65_binding as binding', 1),
    ('reference = binding.source_module("finqa_v63_runtime")',
     'reference = sys.modules["_v65_reference_resource_runtime"]', 1),
    ('import finqa_v64_registration as registration', 'import finqa_v65_registration as registration', 1),
    ('Path(root).resolve() == SCIENTIFIC_ROOT.resolve()', 'Path(root).resolve() == ROOT.resolve()', 1),
    ('_v64_original_resource_base', '_v65_original_resource_base', _protection_source.count('_v64_original_resource_base')),
    ('_v64_private_resource_deferral', '_v65_private_resource_deferral', _protection_source.count('_v64_private_resource_deferral')),
])


class ResourceGuard(_protection.ResourceGuard):
    def __init__(self, root, job, gpu_index, **kwargs):
        binding.require(Path(root).resolve() == binding.ROOT and job.get('kind', 'generate') == 'generate'
                        and job.get('stage') == 'generate', 'V65 resources are generation-only')
        super().__init__(root, job, gpu_index, **kwargs)


memory_protection_policy = _protection.memory_protection_policy
resource_protection_policy = memory_protection_policy
resource_policy = _reference.resource_policy
resource_recovery_policy = _reference.resource_recovery_policy
ExplicitStop = _reference.ExplicitStop
ResourceGateError = _reference.ResourceGateError
LifetimeResourceFailure = _reference.LifetimeResourceFailure


@contextmanager
def execution_context(root, job, gpu_index):
    with ResourceGuard(root, job, gpu_index) as guard:
        yield guard


def controller_runtime():
    return _reference.controller_runtime()


def __getattr__(name):
    return getattr(_reference, name)
