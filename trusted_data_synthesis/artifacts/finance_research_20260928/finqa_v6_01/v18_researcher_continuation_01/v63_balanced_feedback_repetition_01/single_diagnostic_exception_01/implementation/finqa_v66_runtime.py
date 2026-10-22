"""Frozen V64 resource behavior, with independent V66 operational evidence."""
from __future__ import annotations
import finqa_v66_binding as b

_runtime = b.private_module('_v66_private_resource_runtime', b.protection_source('finqa_v64_runtime'), (
    ('import finqa_v64_binding as binding', 'import finqa_v66_binding as binding', 1),
    ('import finqa_v64_registration as registration', 'import finqa_v66_registration as registration', 1),
))
ResourceGuard = _runtime.ResourceGuard
ScientificMonitor = _runtime.ScientificMonitor
execution_context = _runtime.execution_context
memory_protection_policy = _runtime.memory_protection_policy
controller_runtime = _runtime.controller_runtime


def __getattr__(name):
    return getattr(_runtime, name)
