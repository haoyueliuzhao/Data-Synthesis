"""V76 cold-worker resource gates; one inherited primary lease per physical GPU.

Only operational stage names/root are adapted. Lifetime peaks, original R3
capacity checks, known-owner isolation and explicit-stop behavior stay frozen.
"""
from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
import sys
from types import FunctionType, ModuleType, SimpleNamespace

import finqa_v76_binding as binding

reference = binding.source_module("finqa_v63_runtime")
reference_base = reference.reference_base
reference_recovery = reference.reference_recovery
isolation = binding.source_module("finqa_v63_gpu_isolation")
protection = binding.source_v64("finqa_v64_runtime")
ROOT, REPO, V18 = binding.ROOT, binding.REPO, binding.V18
GIB = 1024 ** 3
GPU_UUIDS, CPU_AFFINITY = reference.GPU_UUIDS, reference.CPU_AFFINITY
MINIMUM_FREE_GIB = dict(reference_base.MINIMUM_FREE_GIB)
HOST_STARTUP_GIB = dict(reference_base.HOST_STARTUP_GIB)
worker_environment = reference.worker_environment
inventory, host_memory, process_memory, birth = (
    reference.inventory, reference.host_memory, reference.process_memory, reference.birth)
now = reference.now
require = binding.require


def kind(job):
    stage = job.get("stage")
    phases = {**{f"shard{i:02d}": "class_" for i in range(4)},
              "virtual_point": "feedback", "replay": "replay",
              "distribution": "distribution", "train": "train", "generate": "generate"}
    require(stage in phases, "unregistered V76 scientific resource stage")
    values = [phases[stage]]
    values.extend("class_" if job[field] == "class" else job[field]
                  for field in ("kind", "memory_phase") if field in job)
    require(all(value == values[0] for value in values), "V76 stage/resource phase differs")
    return values[0]


def resource_policy():
    return dict(reference_base.resource_policy(),
        schema="v76_full_closed_loop_resource_policy.v1", max_gpu_workers=6,
        max_workers_per_gpu=1, primary_exclusive_GPU_lease_only=True,
        CPU_initialization_wait_and_draining_count_as_workers=True,
        diagnostic_draw_buffers_and_VJPs_count_in_actual_resources=True,
        new_parameter_points_never_reuse_parent_class_gradients=True,
        fixed_teacher_gradients_count_in_class_virtual_distribution_resources=True,
        memory_protection_policy=memory_protection_policy())


def memory_protection_policy():
    return dict(protection.memory_protection_policy(), scientific_root=str(ROOT),
                schema="v76_inherited_worker_local_native_cache_protection.v1")


def resource_recovery_policy():
    return dict(reference.resource_recovery_policy(),
        schema="v76_actual_durable_resource_recovery.v1",
        old_UNKNOWN_and_single_numeric_exception_allowances_inherited=False)


def validate_registered_contract(protocol):
    """Pure structural checks for the complete inherited guard protocol.

    This is not GPU admission. It does not enter a guard, inspect live capacity,
    acquire a lease, start a sampler or initialize CUDA. In particular the V56
    per-worker capacity-deferral policy is separate from the V76 controller's
    job-retry policy and must be registered under its original required key.
    """
    required = {
        "id", "resource_policy", "resource_recovery_policy", "gpu_isolation_policy",
        "allowed_gpu_indices", "gpu_uuids", "gpu_lease_root", "max_gpu_workers",
        "max_workers_per_gpu",
    }
    require(isinstance(protocol, dict), "resource guard requires a protocol object")
    require(required <= protocol.keys(), "missing resource guard protocol fields: "
            + str(sorted(required - protocol.keys())))
    require(isinstance(protocol["id"], str) and protocol["id"], "resource protocol identity is absent")
    require(protocol["gpu_isolation_policy"] == isolation.gpu_isolation_policy(),
            "registered original GPU ownership policy changed")
    require(type(protocol["max_gpu_workers"]) is int and protocol["max_gpu_workers"] == 6
            and type(protocol["max_workers_per_gpu"]) is int and protocol["max_workers_per_gpu"] == 1,
            "registered six-total/one-per-GPU worker contract changed")
    require(protocol["resource_recovery_policy"] == resource_recovery_policy(),
            "registered inherited per-worker capacity-deferral policy missing or changed")
    require(protocol["resource_policy"] == resource_policy(),
            "registered complete lifetime resource policy changed")
    require(protocol["allowed_gpu_indices"] == list(range(8))
            and protocol["gpu_uuids"] == GPU_UUIDS,
            "registered eight physical GPU identities changed")
    lease_root = Path(protocol["gpu_lease_root"])
    expected_lease_root = V18 / "v25_training_replication_01/training_replication/locks"
    require(lease_root.is_absolute() and lease_root.resolve() == expected_lease_root.resolve(),
            "resource __enter__ requires the original project GPU lease root")
    if "output_root" in protocol:
        require(Path(protocol["output_root"]).resolve() == ROOT.resolve(),
                "resource protocol belongs to another execution root")
    return dict(schema="v76_inherited_resource_constructor_contract.v1", status="PASS",
        checked_constructor_fields=sorted(required - {"id", "gpu_lease_root"}),
        checked_enter_protocol_fields=["id", "gpu_lease_root"],
        constructor_chain=["V76.ResourceGuard", "IsolatedResourceGuard(no own constructor)",
            "V56.ResourceGuard", "V54.ResourceGuard"],
        V64_constructor_is_not_inherited=True,
        controller_retry_and_worker_capacity_deferral_are_distinct=True,
        environment_and_lease_FD_validation_deferred_to_actual_enter=True,
        live_resources_observed=False, resource_admission_passed=False,
        guard_entered=False, CUDA_initialized=False, model_loaded=False)


def _private(name, source, substitutions):
    raw = Path(source.__file__).read_text()
    for before, after, count in substitutions:
        require(raw.count(before) == count, "frozen resource adapter structure changed")
        raw = raw.replace(before, after)
    module = ModuleType(name)
    module.__file__, module.__package__ = str(Path(source.__file__).resolve()), ""
    sys.modules[name] = module
    exec(compile(raw, module.__file__ + "::V76_resource_adapter", "exec"), module.__dict__)
    return module


_base = _private("_v76_frozen_resource_base", reference_base, [
    ('self.job.get("stage") != "replay_C05"', 'self.job.get("stage") != "replay"', 1)])
_base.ROOT, _base.kind, _base.resource_policy = ROOT, kind, resource_policy
_base.publish, _base.checked = binding.publish, binding.checked
_durable = _private("_v76_frozen_resource_deferral", reference_recovery, [
    ("import finqa_v54_runtime as original", "import _v76_frozen_resource_base as original", 1),
    ('self.job.get("stage") != "replay_C05"', 'self.job.get("stage") != "replay"', 1),
    ("                    gc.collect()\n                    self.torch.cuda.empty_cache()",
     "                    self._capacity_cleanup(value, free_pass=free_pass)", 1)])
_durable.ROOT, _durable.resource_policy = ROOT, resource_policy
_durable.resource_recovery_policy = resource_recovery_policy
_durable.publish, _durable.checked = binding.publish, binding.checked
# The owner-isolation adapter must honor the same durable replay stop boundary.
_isolation = _private("_v76_frozen_owner_isolation", isolation, [
    ("('replay_C1', 'replay_C05')", "('replay',)", 2)])
_SharedGuard = _isolation.guarded_class(_durable)
ExplicitStop, ResourceGateError = _base.ExplicitStop, _base.ResourceGateError
ResourceDeferred = _durable.ResourceDeferred
LifetimeResourceFailure, R3CapacityError = _durable.LifetimeResourceFailure, _durable.R3CapacityError


def _protection_methods():
    namespace = dict(vars(protection), ROOT=ROOT, SCIENTIFIC_ROOT=ROOT,
        binding=binding, ExplicitStop=ExplicitStop, memory_protection_policy=memory_protection_policy,
        reference=SimpleNamespace(now=now))
    output = {}
    for name in ("_protection_event", "_capacity_cleanup", "_warm_replay_cache"):
        original = getattr(protection.ResourceGuard, name)
        value = FunctionType(original.__code__, namespace, original.__name__,
                             original.__defaults__, original.__closure__)
        value.__kwdefaults__ = original.__kwdefaults__
        output[name] = value
    return output


_protect = _protection_methods()


class ResourceGuard(_SharedGuard):
    _protection_event = _protect["_protection_event"]
    _capacity_cleanup = _protect["_capacity_cleanup"]
    _warm_replay_cache = _protect["_warm_replay_cache"]

    def __init__(self, root, job, gpu_index, *, torch_module=None):
        require(Path(root).resolve() == ROOT.resolve(), "foreign V76 resource root")
        protocol = binding.checked(ROOT / "protocol/record.json")
        validate_registered_contract(protocol)
        require(protocol["gpu_isolation_policy"] == isolation.gpu_isolation_policy()
                and protocol["max_gpu_workers"] == 6 and protocol["max_workers_per_gpu"] == 1,
                "registered V76 worker-slot/owner-isolation policy changed")
        require(protocol["resource_policy"]["memory_protection_policy"] == memory_protection_policy(),
                "registered worker-local native cache protection changed")
        self.control_protocol = protocol
        self._warm_attempted, self._warm_allocation_bytes = False, 0
        self._warm_status = "NOT_ATTEMPTED" if job.get("kind") == "replay" else "NOT_APPLICABLE"
        self._warm_receipt, self._cache_release_count, self._cache_retained_wait_count = None, 0, 0
        self._protection_events = []
        super().__init__(root, job, gpu_index, torch_module=torch_module)

    def prepare_replay_response(self, session, model, prompt_length, response_length):
        self._warm_replay_cache()
        return super().prepare_replay_response(session, model, prompt_length, response_length)

    def report(self):
        value = super().report()
        original_pre_model_warm = value["warm_allocation_bytes"]
        value.update(control_protocol_id=self.control_protocol["id"],
            inherited_pre_model_warm_allocation_bytes=original_pre_model_warm,
            warm_allocation_bytes=self._warm_allocation_bytes,
            resource_protection=dict(policy=memory_protection_policy(),
                warm_attempted=self._warm_attempted, status=self._warm_status,
                actual_warm_allocation_bytes=self._warm_allocation_bytes,
                receipt=self._warm_receipt, cache_release_count=self._cache_release_count,
                cache_retained_wait_count=self._cache_retained_wait_count,
                protection_degraded=self._cache_release_count > 0,
                events=list(self._protection_events), future_capacity_or_exclusivity_guaranteed=False))
        return value


@contextmanager
def execution_context(root, job, gpu_index):
    with ResourceGuard(root, job, gpu_index) as guard:
        yield guard


def controller_runtime():
    return isolation.install_controller_runtime(sys.modules[__name__])
