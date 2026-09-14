"""Four small CPU cache controls; never authentic Student or collection work."""

from pathlib import Path

import numpy as np
import pytest

from trusted_synthesis.experiments.finance_qa_vnext_fixed_kernel_value import protocol as p
from trusted_synthesis.experiments.finance_qa_vnext_fixed_kernel_value import (
    trajectory_materials as t,
)


def original_package(pool="A", attack=None):
    first_ids = [10, 11, 12, 13] if attack != "nonprefix" else [10, 99, 12, 13]
    rows = []
    for index, (ids, positions) in enumerate(
        (
            (first_ids, [2]),
            ([10, 11, 12, 13, 14, 15], [2, 5] if attack == "overlap" else [4, 5]),
        )
    ):
        rows.append(
            {
                "candidate": {"response_index": index},
                "representation": {
                    "input_ids": ids,
                    "target_mask": [int(i in positions) for i in range(len(ids))],
                    "labels": [value if i in positions else -100 for i, value in enumerate(ids)],
                    "sequence_length": len(ids),
                    "target_token_count": len(positions),
                },
            }
        )
    original = p.record(
        "encoded_original_package",
        registered_session_id="synthetic_" + pool,
        task_id="synthetic_task",
        pool=pool,
        role="train",
        rows=rows,
        whole_package_target_tokens=3,
    )
    metadata = {
        "package_id": original["id"],
        "session_id": original["registered_session_id"],
        "registration_id": "synthetic_registration_" + pool,
        "outcome_id": "synthetic_outcome_" + pool,
        "task_id": original["task_id"],
        "pool": pool,
        "role": "train",
        "family": "annual_flow",
        "state_id": "synthetic_state",
        "method": "endpoint",
        "whole_package_target_tokens": 3,
        "original_package_sha256": p.sha(p.encode(original)),
    }
    return original, metadata


def test_prefix_fusion_retains_every_target_without_new_tokens():
    original, metadata = original_package()
    result = t._trajectory_rows(original, metadata)
    assert result["metadata"]["fused"]
    assert result["metadata"]["rows"] == 1
    assert result["metadata"]["source_rows"] == 2
    assert result["metadata"]["sequence_tokens"] == 6
    assert result["metadata"]["source_sequence_tokens"] == 10
    row = result["arrays"][0]
    np.testing.assert_array_equal(row["input_ids"], [10, 11, 12, 13, 14, 15])
    np.testing.assert_array_equal(row["target_positions"], [2, 4, 5])
    assert row["input_ids"].dtype == row["target_positions"].dtype == np.int32


@pytest.mark.parametrize("attack", ["nonprefix", "overlap"])
def test_incompatible_package_keeps_all_original_rows_and_target_multiplicity(attack):
    original, metadata = original_package(attack=attack)
    result = t._trajectory_rows(original, metadata)
    assert not result["metadata"]["fused"]
    assert result["metadata"]["rows"] == result["metadata"]["source_rows"] == 2
    assert (
        result["metadata"]["sequence_tokens"] == result["metadata"]["source_sequence_tokens"] == 10
    )
    assert sum(len(row["target_positions"]) for row in result["arrays"]) == 3
    assert len(result["metadata"]["fallback_reasons"]) == 1
    for old, cached in zip(original["rows"], result["arrays"], strict=True):
        np.testing.assert_array_equal(old["representation"]["input_ids"], cached["input_ids"])
        expected = np.flatnonzero(old["representation"]["target_mask"])
        np.testing.assert_array_equal(expected, cached["target_positions"])


def test_prepare_cache_and_readonly_mmap_loading_without_original_rechecks(tmp_path, monkeypatch):
    source, output = tmp_path / "source", tmp_path / "cache"
    references, package_rows, budgets, inventory = {}, {}, {}, []
    for pool in p.POOLS:
        original, metadata = original_package(pool, attack="nonprefix" if pool == "B" else None)
        path = source / (pool + ".json")
        p.write_once(path, original)
        references[original["id"]] = {
            "path": path.name,
            "sha256": p.sha(path),
            "id": original["id"],
        }
        package_rows[original["id"]] = {
            "rows": 2,
            "sequence_tokens": 10,
            "target_tokens": 3,
            "rows_sha256": "synthetic",
        }
        per = {"packages": 1, "rows": 2, "sequence_tokens": 10, "target_tokens": 3}
        budgets[pool] = {
            **{key + "_per_epoch": value for key, value in per.items()},
            **{key + "_all_epochs": 10 * value for key, value in per.items()},
        }
        inventory.append(metadata)
    parent = p.record(
        "execution_freeze",
        kernel_id="fixed_kernel:synthetic_original",
        material_input_receipt={"path": "unused_injected_receipt.json"},
        input_files={},
    )
    parent_path = source / "execution_freeze.json"
    p.write_once(parent_path, parent)

    class SyntheticAuthority(dict):
        pass

    authority = SyntheticAuthority(kernel={"train_packages": inventory})
    authority.package_references = references
    authority.receipt = {"id": "synthetic_material_receipt"}
    authority.verification = p.record(
        "material_input_verification",
        pool_budgets=budgets,
        package_rows=package_rows,
    )
    authority_calls = []

    def supplied_authority(*args, **kwargs):
        authority_calls.append((args, kwargs))
        return authority

    monkeypatch.setattr(t.original_materials, "load_authority", supplied_authority)
    checked = p.checked

    def no_second_package_hash(value, kind):
        assert kind != "encoded_original_package"
        return checked(value, kind)

    monkeypatch.setattr(p, "checked", no_second_package_hash)
    manifest = t.prepare_cache(source, output, parent_path, workers=1)
    assert len(authority_calls) == 1
    assert manifest["source_train_packages"] == manifest["raw_package_SHA_checks"] == 2
    assert manifest["fused_packages"] == manifest["fallback_packages"] == 1
    assert manifest["pool_budgets"]["A"]["sequence_tokens_per_epoch"] == 6
    assert manifest["pool_budgets"]["B"]["sequence_tokens_per_epoch"] == 10
    assert manifest["source_material_budgets"] == budgets
    assert manifest["tokenization_calls"] == manifest["full_kernel_rebuilds"] == 0
    descriptor = t._descriptor(output / "manifest.json", output)
    pool = t.load_pool(output, descriptor, "A")
    row = next(pool.row_arrays(pool.packages[0]))
    np.testing.assert_array_equal(row["target_ids"], [12, 14, 15])
    assert not row["input_ids"].flags.writeable
    assert not row["target_positions"].flags.writeable
    assert not row["target_ids"].flags.writeable
    with pytest.raises(ValueError):
        row["input_ids"][0] = 99
    assert pool.actual_budget == manifest["pool_budgets"]["A"]
    assert pool.source_material_budget == budgets["A"]
    assert pool.kernel_id == parent["kernel_id"]
    assert t.require_pool(pool) is pool
    sha = p.sha

    def no_repeated_numeric_sha(value):
        assert not isinstance(value, Path) or value.suffix != ".npy"
        return sha(value)

    monkeypatch.setattr(p, "sha", no_repeated_numeric_sha)
    assert t.load_pool(output, manifest, "A") is pool
