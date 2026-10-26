"""CPU-only inherited constructor contract; never enters a resource guard."""
from pathlib import Path
import sys

import pytest

SCRIPTS = str(Path(__file__).resolve().parents[1] / "scripts")
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)
import finqa_v74_binding as binding
import finqa_v74_resources as resources


def protocol():
    return dict(id="CPU_contract_fixture", output_root=str(resources.ROOT),
        resource_policy=resources.resource_policy(),
        resource_recovery_policy=resources.resource_recovery_policy(),
        gpu_isolation_policy=resources.isolation.gpu_isolation_policy(),
        allowed_gpu_indices=list(range(8)), gpu_uuids=dict(resources.GPU_UUIDS),
        gpu_lease_root=str(resources.V18 / "v25_training_replication_01/training_replication/locks"),
        max_gpu_workers=1, max_workers_per_gpu=1)


def test_complete_guard_contract_is_distinct_from_resource_admission():
    result = resources.validate_registered_contract(protocol())
    assert result["status"] == "PASS"
    assert not result["resource_admission_passed"] and not result["guard_entered"]
    assert result["controller_retry_and_worker_capacity_deferral_are_distinct"]
    assert result["V64_constructor_is_not_inherited"]


@pytest.mark.parametrize("field", ["id", "resource_policy", "resource_recovery_policy",
    "gpu_isolation_policy", "allowed_gpu_indices", "gpu_uuids", "gpu_lease_root",
    "max_gpu_workers", "max_workers_per_gpu"])
def test_all_constructor_and_enter_protocol_fields_required(field):
    value = protocol()
    value.pop(field)
    with pytest.raises(ValueError, match="missing resource guard protocol fields"):
        resources.validate_registered_contract(value)


def test_controller_retry_policy_does_not_substitute_for_worker_deferral_policy():
    value = protocol()
    value["recovery_policy"] = dict(retry_backoff_seconds=300)
    value.pop("resource_recovery_policy")
    with pytest.raises(ValueError, match="resource_recovery_policy"):
        resources.validate_registered_contract(value)


@pytest.mark.parametrize("field", ["resource_policy", "resource_recovery_policy", "gpu_isolation_policy",
    "allowed_gpu_indices", "gpu_uuids", "gpu_lease_root", "max_gpu_workers", "max_workers_per_gpu", "output_root"])
def test_changed_frozen_guard_contract_is_rejected(field):
    value = protocol()
    if field.endswith("policy"):
        value[field] = dict(value[field], unexpected_override=True)
    elif field == "allowed_gpu_indices": value[field] = [0]
    elif field == "gpu_uuids": value[field]["0"] = "another_GPU"
    elif field.endswith("root"): value[field] = "/tmp/unregistered_resource_root"
    else: value[field] += 1
    with pytest.raises(ValueError):
        resources.validate_registered_contract(value)


def test_actual_inherited_constructor_runs_on_CPU_without_enter_or_cuda(tmp_path, monkeypatch):
    import torch
    assert not torch.cuda.is_initialized()
    monkeypatch.setattr(resources, "ROOT", tmp_path)
    monkeypatch.setattr(binding, "ROOT", tmp_path)
    value = protocol()
    binding.publish(tmp_path / "protocol/record.json", {k: v for k, v in value.items() if k != "id"})
    events = []
    def forbidden(*args, **kwargs):
        events.append("forbidden")
        raise AssertionError("constructor must not enter, admit, sample or initialize CUDA")
    monkeypatch.setattr(resources._base.ResourceGuard, "__enter__", forbidden)
    monkeypatch.setattr(resources._base, "inventory", forbidden)
    monkeypatch.setattr(resources._durable, "inventory", forbidden)
    monkeypatch.setattr(resources._isolation, "probe_gpus", forbidden)
    monkeypatch.setattr(torch.cuda, "set_device", forbidden)
    class NoTorchAccess:
        def __getattr__(self, name): return forbidden(name)
    job = dict(job_id="P.continuation", model="P", kind="generate", stage="generate", memory_phase="generate")
    guard = resources.ResourceGuard(tmp_path, job, 4, torch_module=NoTorchAccess())
    try:
        assert guard.kind == "generate" and guard.gpu == 4
        assert guard._thread is None and guard._handlers == {} and guard._reset is None
        assert guard.lease_identity is None and guard.observations == [] and guard.preflight_observations == []
        assert not guard.report()["all_gates_passed"]
        assert guard.report()["actual_boundary_observations"] == 0
        assert guard.directory == tmp_path / "resources/P.continuation" / f"pid{resources._base.os.getpid()}"
        assert events == [] and not torch.cuda.is_initialized()
    finally:
        # Constructor owns one empty CPU log; do not invoke __exit__/closeout.
        guard._events.close()


def test_missing_worker_policy_fails_before_any_resource_log_creation(tmp_path, monkeypatch):
    monkeypatch.setattr(resources, "ROOT", tmp_path)
    monkeypatch.setattr(binding, "ROOT", tmp_path)
    value = protocol()
    value.pop("resource_recovery_policy")
    binding.publish(tmp_path / "protocol/record.json", {k: v for k, v in value.items() if k != "id"})
    with pytest.raises(ValueError, match="resource_recovery_policy"):
        resources.ResourceGuard(tmp_path, dict(job_id="P.continuation", kind="generate", stage="generate", memory_phase="generate"), 4)
    assert not (tmp_path / "resources").exists()
