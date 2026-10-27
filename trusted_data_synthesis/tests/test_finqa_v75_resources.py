"""Only the new V75 stage/cap constructor contract, without CUDA entry."""
from pathlib import Path
import sys
import pytest

SCRIPTS=str(Path(__file__).resolve().parents[1]/"scripts")
if SCRIPTS not in sys.path:sys.path.append(SCRIPTS)
import finqa_v75_binding as b
b.install_scientific_paths();b.install_registered_auxiliary()
import finqa_v75_resources as resources


def protocol():
    return dict(output_root=str(resources.ROOT),resource_policy=resources.resource_policy(),
        resource_recovery_policy=resources.resource_recovery_policy(),
        gpu_isolation_policy=resources.isolation.gpu_isolation_policy(),allowed_gpu_indices=list(range(8)),
        gpu_uuids=resources.GPU_UUIDS,
        gpu_lease_root=str(b.V18/"v25_training_replication_01/training_replication/locks"),
        max_gpu_workers=6,max_workers_per_gpu=1)


@pytest.mark.parametrize("stage,kind",[("collect","generate"),("train","train"),("generate","generate")])
def test_each_new_stage_actual_guard_constructor_cpu_only(tmp_path,monkeypatch,stage,kind):
    import torch
    monkeypatch.setattr(resources,"ROOT",tmp_path);monkeypatch.setattr(b,"ROOT",tmp_path)
    b.publish(tmp_path/"protocol/record.json",protocol())
    class NoTorch:
        def __getattr__(self,name):raise AssertionError("constructor must not touch CUDA: "+name)
    guard=resources.ResourceGuard(tmp_path,dict(job_id="fixture",stage=stage,kind=kind,memory_phase=kind),6,torch_module=NoTorch())
    try:
        assert guard.kind==kind and guard.gpu==6
        assert guard._thread is None and guard.lease_identity is None
        assert not torch.cuda.is_initialized() and guard.report()["actual_boundary_observations"]==0
    finally:guard._events.close()


def test_stage_memory_kind_cannot_misdeclare_collect_as_training():
    with pytest.raises(ValueError,match="phase differs"):
        resources.kind(dict(stage="collect",kind="train",memory_phase="train"))
