"""CPU-only runtime metadata tests; scientific checkpoint state is not extended."""

import importlib
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
import torch

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
worker = importlib.import_module("finqa_v19_profiled_worker")


def test_checkpoint_profile_is_atomic_metadata_not_computational_state(tmp_path):
    profile_ref = dict(path="synthetic-profile", id="profile", sha256="a" * 64)
    payload = dict(
        parameters={"p": torch.tensor([1.0, 2.0])},
        step=298,
        arm="Full",
        optimizer={"state": {}},
        rng={"cpu": torch.get_rng_state()},
        pi={"q": {"z": 1}},
    )
    original = SimpleNamespace(
        root=tmp_path / "original",
        step_index=298,
        arm="Full",
        seed=29,
        pool=SimpleNamespace(cache_id="pool"),
        schedule={"schedule_sha256": "schedule"},
        _payload=lambda: payload,
    )
    changed = worker.ProfiledDriver.__new__(worker.ProfiledDriver)
    changed.__dict__.update(original.__dict__)
    changed.root = tmp_path / "profiled"
    changed.profile_reference = profile_ref
    a = worker.original_driver.TrainingDriver.commit(original, "step", {})
    b = changed.commit("step", {})
    ra = json.loads((a / "record.json").read_bytes())
    rb = json.loads((b / "record.json").read_bytes())
    assert ra["actual_state_digest"] == rb["actual_state_digest"]
    assert rb["execution_profile"] == profile_ref
    actual = torch.load(b / "state.pt", weights_only=False)
    assert "execution_profile" not in actual
    assert torch.equal(actual["parameters"]["p"], payload["parameters"]["p"])


def test_restore_rejects_another_execution_profile_before_loading_tensors(tmp_path):
    (tmp_path / "record.json").write_text(json.dumps({"execution_profile": {"id": "other"}}))
    driver = worker.ProfiledDriver.__new__(worker.ProfiledDriver)
    driver.profile_reference = {"id": "approved"}
    with pytest.raises(ValueError, match="exact optimized execution profile"):
        driver.restore(tmp_path)


@pytest.mark.parametrize("seed,arm,gpu", [(11, "Full", 1), (29, "C-only", 2), (29, "Full", 0)])
def test_running_arms_and_other_gpus_cannot_enter_optimized_worker(
    monkeypatch, tmp_path, seed, arm, gpu
):
    monkeypatch.setattr(
        worker,
        "checked_profile",
        lambda root: {
            "optimized_job_keys": ["arm-29-full", "arm-47-full"],
            "allowed_gpu_indices": [1, 2, 3, 6],
        },
    )
    monkeypatch.setattr(worker, "admitted_validation", lambda *args: {"id": "synthetic-validation"})
    monkeypatch.setattr(
        worker.original_arm, "run_arm", lambda *a, **kw: pytest.fail("must not start a model")
    )
    with pytest.raises(ValueError, match="protected running arms"):
        worker.run(tmp_path, seed, arm, gpu, profile_root=tmp_path)
