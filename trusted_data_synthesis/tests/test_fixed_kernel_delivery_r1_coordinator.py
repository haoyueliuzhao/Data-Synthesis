"""Only new matrix and resource-admission controls; no model or old audit replay."""

import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).parents[1] / "scripts/run_fixed_kernel_delivery_r1_20260915.py"
SPEC = importlib.util.spec_from_file_location("delivery_r1_coordinator_control", SCRIPT)
coordinator = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(coordinator)


def test_fixed_matrix_base_identity_and_prospective_order():
    rows = coordinator.matrix_models()
    assert len(rows) == len({row["key"] for row in rows}) == 10
    assert rows[0]["key"] == rows[0]["model_kind"] == "unfinetuned_base"
    assert sum(row["model_kind"] == "finetuned" for row in rows) == 9
    assert sum(row["condition_order"] == ["original", "gamma_doc"] for row in rows) == 5
    assert sum(row["condition_order"] == ["gamma_doc", "original"] for row in rows) == 5
    assert all(set(row["condition_order"]) == {"original", "gamma_doc"} for row in rows)
    assert len(rows) * 2 * 3 * 32 + len(rows) * 6 == coordinator.MAX_MODEL_CALLS == 1980


def test_free_memory_admission_allows_busy_but_not_insufficient_or_owned_GPU():
    raw = "0, a, 27000, 100\n1, b, 24575, 0\n2, c, 24576, 90\n3, d, 80000, 0"
    selected = coordinator.eligible_gpus(raw, ("a", "b", "c"), used=("c",))
    assert [row["uuid"] for row in selected] == ["a"]
    assert selected[0]["utilization_percent"] == 100
    assert [row["uuid"] for row in coordinator.eligible_gpus(raw, ("c",))] == ["c"]
