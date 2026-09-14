"""Small synthetic identity/parity controls; no real corpus or GPU is loaded."""

import copy
import pickle

import pytest
from test_qa_vnext_fixed_kernel_distribution import outcome, rerecord

from trusted_synthesis.experiments.finance_qa_vnext_fixed_kernel_value import distribution as d
from trusted_synthesis.experiments.finance_qa_vnext_fixed_kernel_value import fast_materials as f
from trusted_synthesis.experiments.finance_qa_vnext_fixed_kernel_value import materials as m
from trusted_synthesis.experiments.finance_qa_vnext_fixed_kernel_value import population as pop
from trusted_synthesis.experiments.finance_qa_vnext_fixed_kernel_value import protocol as p


def control(tmp_path, monkeypatch, *, failed=False):
    tasks = [
        {"task_id": "task_" + str(i), "family": family}
        for i, family in enumerate((*p.FAMILIES[:3], "control", "control"))
    ]
    selected = p.record("population", tasks=tasks)
    registered, outcomes = [], []
    for pool in p.POOLS:
        for task in tasks:
            methods = ("control",) if task["family"] == "control" else ("endpoint", "movement")
            for ordinal, (method, replicate) in enumerate(
                [*((method, 0) for method in methods), (methods[0], 12)]
            ):
                reg = p.record(
                    "session_registration",
                    session_id=f"{pool}_{task['task_id']}_{ordinal}",
                    task_id=task["task_id"],
                    family=task["family"],
                    pool=pool,
                    role="sealed" if replicate == 12 else "train",
                    replicate=replicate,
                    freeze_id="synthetic_freeze",
                    basis=method,
                )
                value = outcome(reg, eligible=True, method=method, state="synthetic_fine")
                original = rerecord(value["original_package"], role=reg["role"])
                value = rerecord(value, role=reg["role"], original_package=original)
                registered.append(reg)
                outcomes.append(value)
    # Exercise every original eligibility flag without removing its slot.
    for flag in ("financial_valid", "full_class_valid", "consumable", "authentic_origin_verified"):
        base = registered[0]
        reg = rerecord(base, session_id="ineligible_" + flag)
        value = outcome(reg, eligible=True, method="endpoint", state="synthetic_fine")
        original = rerecord(value["original_package"], role="train")
        value = rerecord(value, role="train", original_package=original, **{flag: False})
        registered.append(reg)
        outcomes.append(value)
    if failed:
        reg = rerecord(registered[0], session_id="failed_original")
        registered.append(reg)
        outcomes.append(
            rerecord(outcome(reg), status="failed", role="train", original_package=None)
        )
    registry = p.record(
        "material_registry",
        sessions=registered,
        session_count=len(registered),
        freeze_id="synthetic_freeze",
    )
    monkeypatch.setattr(d, "validate_population", lambda value: value["tasks"])
    monkeypatch.setattr(d, "validate_registry", lambda value, _: value["sessions"])
    monkeypatch.setattr(d, "TASK_COUNT", len(tasks))
    monkeypatch.setattr(p, "SESSION_CAP", len(registered))
    entries = [
        m.store_materialized({"outcome": value, "package": value.get("original_package")}, tmp_path)
        for value in outcomes
    ]
    index = p.record(
        "materialization_index",
        status="COMPLETE_FIXED_MATERIALIZATION",
        collection_complete=True,
        complete_registered_denominator=len(registered),
        registry_id=registry["id"],
        freeze_id=registry["freeze_id"],
        entries=entries,
    )
    files = {}
    for key, value in (
        ("population", selected),
        ("registry", registry),
        ("materialization_index", index),
    ):
        path = tmp_path / (key + ".json")
        p.write_once(path, value)
        files[key] = {"path": path.name, "bytes": path.stat().st_size, "sha256": p.sha(path)}
    return selected, registry, outcomes, files


@pytest.mark.parametrize(
    "payload", [{}, {"values": [1, 2, {"中文": False}]}, {"nested": {"x": None}}]
)
def test_identity_check_matches_record_without_copying(payload, monkeypatch):
    value = p.record("synthetic_identity", **payload)
    monkeypatch.setattr(p.copy, "deepcopy", lambda *_: pytest.fail("verifier must not copy"))
    assert p.checked(value, "synthetic_identity") is value
    pop._checked(value, "synthetic_identity")


@pytest.mark.parametrize("field,value", [("schema_version", "wrong"), ("id", "wrong"), ("x", 9)])
def test_identity_tampering_still_rejected(field, value):
    original = p.record("synthetic_identity", x=1)
    changed = {**original, field: value}
    with pytest.raises(ValueError, match="content_identity"):
        p.checked(changed, "synthetic_identity")
    with pytest.raises(ValueError, match="content_identity"):
        pop._checked(changed, "synthetic_identity")


def test_public_record_still_isolates_mutable_inputs_and_frozen_tree_rejects_mutation():
    source = {"rows": [{"ids": [1, 2, 3]}]}
    original = p.record("synthetic_identity", source=source)
    source["rows"][0]["ids"][0] = 99
    assert original["source"]["rows"][0]["ids"][0] == 1
    frozen = f.freeze_json(original)
    assert copy.deepcopy(frozen) is frozen
    assert p.encode(frozen) == p.encode(original)
    with pytest.raises(TypeError, match="immutable"):
        frozen["source"]["rows"][0]["ids"][0] = 0
    with pytest.raises(TypeError, match="immutable"):
        frozen["source"]["rows"].append({})
    restored = pickle.loads(pickle.dumps(frozen))
    assert restored == frozen
    with pytest.raises(TypeError, match="immutable"):
        restored["source"]["rows"][0]["ids"].clear()


@pytest.mark.parametrize("failed", [False, True])
def test_complete_builder_value_id_and_all_flags_match_original(tmp_path, monkeypatch, failed):
    selected, registry, outcomes, files = control(tmp_path, monkeypatch, failed=failed)
    expected = d.build_kernel(selected, registry, outcomes)
    loaded = f.load_material_inputs(tmp_path, files, expected_kernel_id=expected["id"], workers=1)
    assert loaded["kernel"] == expected
    assert loaded["kernel"]["id"] == expected["id"]
    assert loaded["outcomes"] == outcomes
    assert loaded["kernel"]["valid_sealed_packages"]
    with pytest.raises(TypeError, match="immutable"):
        loaded.verification = {"status": "fabricated PASS"}
    with pytest.raises(TypeError, match="immutable"):
        loaded._stamps.clear()
    assert loaded["kernel"]["exclusions"] == {"invalid_or_incomplete_train": 4 + int(failed)}
    monkeypatch.setattr(d, "build_kernel", lambda *_: pytest.fail("no repeated build"))
    assert (
        f.load_material_inputs(tmp_path, files, expected_kernel_id=expected["id"], workers=1)
        is loaded
    )
    f.assert_verified_inputs(
        loaded, loaded["kernel"], loaded["population"], loaded["registry"], loaded["outcomes"]
    )


def test_receipt_authority_pool_only_originals_and_source_tamper(tmp_path, monkeypatch):
    selected, registry, outcomes, files = control(tmp_path, monkeypatch)
    expected = d.build_kernel(selected, registry, outcomes)
    loaded = f.load_material_inputs(tmp_path, files, expected_kernel_id=expected["id"], workers=1)
    verification = p.record(
        "material_input_verification",
        kernel_id=expected["id"],
        population_id=selected["id"],
        registry_id=registry["id"],
    )
    receipt = f.make_receipt(loaded, verification)
    path = tmp_path / "verified_receipt.json"
    p.write_once(path, receipt)
    descriptor = {"path": path.name, "bytes": path.stat().st_size, "sha256": p.sha(path)}
    monkeypatch.setattr(d, "build_kernel", lambda *_: pytest.fail("authority must not rebuild"))
    authority = f.load_authority(tmp_path, descriptor, files, expected_kernel_id=expected["id"])
    assert authority.kind == "authority"
    assert authority.verification == verification
    assert all("original_package" not in row for row in authority["kernel"]["train_packages"])
    reads = []
    read = f._read

    def observed(root, reference, stamps, **kwargs):
        if reference["path"].endswith("package.json"):
            reads.append(reference["id"])
        return read(root, reference, stamps, **kwargs)

    monkeypatch.setattr(f, "_read", observed)
    view = f.load_training_pool(
        tmp_path, descriptor, files, pool="A", expected_kernel_id=expected["id"]
    )
    assert set(reads) == {
        row["package_id"] for row in expected["train_packages"] if row["pool"] == "A"
    }
    assert view.kind == "pool" and view.pool == "A"
    assert f.checked_kernel(view["kernel"]) is view["kernel"]
    with pytest.raises(ValueError, match="content_identity"):
        p.checked(view["kernel"], "fixed_kernel")
    with pytest.raises(ValueError, match="private_immutable"):
        f.require_verified(dict(loaded))
    reference = view.package_references[reads[0]]
    original_path = tmp_path / reference["path"]
    original_path.write_bytes(original_path.read_bytes() + b" ")
    with pytest.raises(ValueError, match="verified_source_file_changed"):
        f.require_verified(view)


def test_serial_parallel_hydration_exact_kernel_and_frozen_tree_parity(tmp_path, monkeypatch):
    values = []
    for workers in (1, 2):
        root = tmp_path / str(workers)
        _, _, _, files = control(root, monkeypatch, failed=True)
        values.append(f.load_material_inputs(root, files, workers=workers))
    serial, parallel = values
    assert serial["kernel"] == parallel["kernel"]
    assert serial["kernel"]["id"] == parallel["kernel"]["id"]
    assert serial["outcomes"] == parallel["outcomes"]
    assert serial.package_references == parallel.package_references
    assert parallel.receipt["CPU_hydration_workers"] == 2
    assert serial.receipt["verified_file_count"] == parallel.receipt["verified_file_count"]
    assert serial.receipt["verified_file_bytes"] == parallel.receipt["verified_file_bytes"]
    original = parallel["kernel"]["train_packages"][0]["original_package"]
    with pytest.raises(TypeError, match="immutable"):
        original["rows"][0]["representation"]["input_ids"][0] = 99
