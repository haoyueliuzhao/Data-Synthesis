"""One-time numeric trajectory cache over the already certified originals.

Every train package is read and byte-authenticated once. Exact prefix-compatible
rows share their final sequence and the union of their original target masks.
Nonprefix or overlapping targets retain ALL original rows as explicit fallback.
No tokenizer, financial assessment, material selection, or kernel rebuild occurs.
"""

import json
import os
from concurrent.futures import ProcessPoolExecutor
from multiprocessing import get_context
from pathlib import Path

import numpy as np

from . import fast_materials as original_materials
from . import protocol as p

_MINT = object()
_LOADED = {}


def _descriptor(path, root):
    return {
        "path": str(path.relative_to(root)),
        "bytes": path.stat().st_size,
        "sha256": p.sha(path),
    }


def _read_bound(root, reference):
    path = original_materials._path(root, reference["path"])
    raw = path.read_bytes()
    p.require(
        ("bytes" not in reference or len(raw) == reference["bytes"])
        and p.sha(raw) == reference["sha256"],
        "trajectory.actual_bound_bytes",
    )
    return raw


def _trajectory_rows(original, metadata):
    """Verify only fusion compatibility, preserving multiplicity on fallback."""
    rows = original["rows"]
    p.require(bool(rows), "trajectory.nonempty_original_package")
    converted, response_indices = [], []
    source_sequence_tokens, target_count = 0, 0
    for index, row in enumerate(rows):
        representation = row["representation"]
        ids = np.asarray(representation["input_ids"], dtype=np.int32)
        positions = np.flatnonzero(representation["target_mask"]).astype(np.int32)
        labels = np.asarray(representation["labels"], dtype=np.int32)
        p.require(
            ids.ndim == positions.ndim == labels.ndim == 1
            and len(ids) == len(labels) == representation["sequence_length"]
            and 1 < len(ids) <= p.SEQUENCE_CAP
            and len(positions) == representation["target_token_count"] > 0
            and positions[0] > 0
            and positions[-1] < len(ids)
            and np.array_equal(labels[positions], ids[positions]),
            "trajectory.original_target_labels_and_bounds",
        )
        response_index = row.get("candidate", {}).get("response_index", index)
        response_indices.append(response_index)
        converted.append(
            {
                "input_ids": ids,
                "target_positions": positions,
                "source_response_indices": [response_index],
            }
        )
        source_sequence_tokens += len(ids)
        target_count += len(positions)
    p.require(
        target_count
        == original["whole_package_target_tokens"]
        == metadata["whole_package_target_tokens"],
        "trajectory.unchanged_whole_package_target_count",
    )
    final_ids = converted[-1]["input_ids"]
    reasons = []
    if not all(
        len(row["input_ids"]) <= len(final_ids)
        and np.array_equal(row["input_ids"], final_ids[: len(row["input_ids"])])
        for row in converted
    ):
        reasons.append("original_row_not_exact_prefix_of_final_sequence")
    targets = np.concatenate([row["target_positions"] for row in converted])
    if len(np.unique(targets)) != target_count:
        reasons.append("original_target_positions_overlap_do_not_deduplicate")
    if not reasons:
        converted = [
            {
                "input_ids": final_ids,
                "target_positions": np.sort(targets),
                "source_response_indices": response_indices,
            }
        ]
    return {
        "metadata": {
            **metadata,
            "fused": not reasons,
            "fallback_reasons": reasons,
            "source_rows": len(rows),
            "source_sequence_tokens": source_sequence_tokens,
            "rows": len(converted),
            "sequence_tokens": sum(len(row["input_ids"]) for row in converted),
        },
        "arrays": converted,
    }


def _prepare_original(arguments):
    source_root, metadata, reference, certified_rows = arguments
    raw = _read_bound(source_root, reference)  # One actual raw-package SHA only.
    original = json.loads(raw)
    p.require(
        reference["sha256"] == metadata["original_package_sha256"]
        and original["id"] == reference["id"] == metadata["package_id"]
        and original["registered_session_id"] == metadata["session_id"]
        and original["task_id"] == metadata["task_id"]
        and original["pool"] == metadata["pool"]
        and original["role"] == metadata["role"] == "train",
        "trajectory.exact_certified_original_package_binding",
    )
    # The exact bytes already passed the original material verifier. Do not
    # p.checked(original), re-hash canonical JSON, or re-assess semantics here.
    result = _trajectory_rows(original, metadata)
    row = result["metadata"]
    p.require(
        row["source_rows"] == certified_rows["rows"]
        and row["source_sequence_tokens"] == certified_rows["sequence_tokens"]
        and row["whole_package_target_tokens"] == certified_rows["target_tokens"],
        "trajectory.original_certified_counts_unchanged",
    )
    return result


def _save_numeric(path, array):
    with path.open("xb") as stream:
        np.save(stream, array, allow_pickle=False)
        stream.flush()
        os.fsync(stream.fileno())


def _pool_budget(packages):
    per_epoch = {
        "packages": len(packages),
        "rows": sum(row["rows"] for row in packages),
        "target_tokens": sum(row["whole_package_target_tokens"] for row in packages),
        "sequence_tokens": sum(row["sequence_tokens"] for row in packages),
    }
    return {
        **{key + "_per_epoch": value for key, value in per_epoch.items()},
        **{key + "_all_epochs": 10 * value for key, value in per_epoch.items()},
    }


def _write_pool(output, pool, originals, source_budget):
    directory = output / pool
    directory.mkdir()
    inputs, targets, packages = [], [], []
    input_offset = target_offset = 0
    for original in originals:
        metadata = original["metadata"]
        segments = []
        for row in original["arrays"]:
            ids, positions = row["input_ids"], row["target_positions"]
            segments.append(
                {
                    "input_offset": input_offset,
                    "input_length": len(ids),
                    "target_offset": target_offset,
                    "target_count": len(positions),
                    "source_response_indices": row["source_response_indices"],
                }
            )
            inputs.append(ids)
            targets.append(positions)
            input_offset += len(ids)
            target_offset += len(positions)
        packages.append({**metadata, "segments": segments})
    actual = _pool_budget(packages)
    p.require(
        actual["packages_per_epoch"] == source_budget["packages_per_epoch"]
        and actual["target_tokens_per_epoch"] == source_budget["target_tokens_per_epoch"]
        and sum(row["source_rows"] for row in packages) == source_budget["rows_per_epoch"]
        and sum(row["source_sequence_tokens"] for row in packages)
        == source_budget["sequence_tokens_per_epoch"]
        and all(
            source_budget[key + "_all_epochs"] == 10 * source_budget[key + "_per_epoch"]
            for key in ("packages", "rows", "target_tokens", "sequence_tokens")
        ),
        "trajectory.all_original_packages_targets_and_ten_epochs_retained",
    )
    input_path, target_path = directory / "input_ids.npy", directory / "target_positions.npy"
    _save_numeric(input_path, np.concatenate(inputs).astype(np.int32, copy=False))
    _save_numeric(target_path, np.concatenate(targets).astype(np.int32, copy=False))
    package_index = p.record(
        "trajectory_pool_index",
        pool=pool,
        packages=packages,
        input_elements=input_offset,
        target_elements=target_offset,
        actual_budget=actual,
        source_material_budget=source_budget,
        original_package_order_retained=True,
        target_multiplicity_retained=True,
    )
    index_path = directory / "packages.json"
    p.write_once(index_path, package_index)
    return {
        "input_ids": _descriptor(input_path, output),
        "target_positions": _descriptor(target_path, output),
        "package_index": _descriptor(index_path, output),
        "package_index_id": package_index["id"],
        "input_elements": input_offset,
        "target_elements": target_offset,
        "fused_packages": sum(row["fused"] for row in packages),
        "fallback_packages": sum(not row["fused"] for row in packages),
        "actual_budget": actual,
    }


def prepare_cache(source_root, output_directory, parent_freeze_path, workers=24):
    """Build the train-only cache once from the original closed authority."""
    source_root = Path(source_root).resolve()
    output = Path(output_directory).resolve()
    parent_path = Path(parent_freeze_path)
    parent_path = parent_path if parent_path.is_absolute() else source_root / parent_path
    p.require(
        parent_path.resolve().is_relative_to(source_root), "trajectory.parent_freeze_in_source"
    )
    p.require(
        type(workers) is int and 1 <= workers <= p.CPU_WORKERS, "trajectory.bounded_CPU_workers"
    )
    p.require(not output.exists(), "trajectory.new_exclusive_cache_directory")
    parent_raw = parent_path.read_bytes()
    parent = p.checked(json.loads(parent_raw), "execution_freeze")
    authority = original_materials.load_authority(
        source_root,
        parent["material_input_receipt"],
        parent["input_files"],
        expected_kernel_id=parent["kernel_id"],
    )
    source_budgets = authority.verification["pool_budgets"]
    inventory = authority["kernel"]["train_packages"]
    p.require(
        len(inventory) == sum(source_budgets[pool]["packages_per_epoch"] for pool in p.POOLS)
        and all(row["role"] == "train" and row["pool"] in p.POOLS for row in inventory),
        "trajectory.entire_certified_train_inventory_only",
    )
    output.mkdir(parents=True)
    p.write_once(
        output / "started.json",
        p.record(
            "trajectory_cache_started",
            parent_execution_freeze_id=parent["id"],
            kernel_id=parent["kernel_id"],
            train_packages=len(inventory),
            workers=workers,
            tokenization_calls=0,
            API_calls=0,
            GPU_operations=0,
            started_at=p.now(),
        ),
    )
    arguments = (
        (
            source_root,
            row,
            authority.package_references[row["package_id"]],
            authority.verification["package_rows"][row["package_id"]],
        )
        for row in inventory
    )
    by_pool = {pool: [] for pool in p.POOLS}

    def accept(results):
        for result in results:
            by_pool[result["metadata"]["pool"]].append(result)

    if workers == 1:
        accept(map(_prepare_original, arguments))
    else:
        with ProcessPoolExecutor(max_workers=workers, mp_context=get_context("spawn")) as executor:
            accept(executor.map(_prepare_original, arguments, chunksize=1))
    pools = {
        pool: _write_pool(output, pool, by_pool[pool], source_budgets[pool]) for pool in p.POOLS
    }
    manifest = p.record(
        "trajectory_material_cache",
        kernel_id=parent["kernel_id"],
        material_verification_id=authority.verification["id"],
        parent_execution_freeze_id=parent["id"],
        parent_material_receipt_id=authority.receipt["id"],
        parent_execution_freeze_path=str(parent_path.resolve()),
        parent_execution_freeze_sha256=p.sha(parent_raw),
        source_root=str(source_root),
        source_material_receipt=parent["material_input_receipt"],
        pools=pools,
        pool_budgets={pool: pools[pool]["actual_budget"] for pool in p.POOLS},
        source_material_budgets=source_budgets,
        source_train_packages=len(inventory),
        fused_packages=sum(value["fused_packages"] for value in pools.values()),
        fallback_packages=sum(value["fallback_packages"] for value in pools.values()),
        actual_numeric_dtype="int32",
        numpy_allow_pickle=False,
        readonly_mmap_loading=True,
        maximum_sequence_length=p.SEQUENCE_CAP,
        every_original_train_package_retained=True,
        original_targets_and_multiplicity_retained=True,
        original_package_order_retained=True,
        original_row_order_retained_on_fallback=True,
        raw_package_SHA_checks=len(inventory),
        additional_canonical_package_hashes=0,
        full_kernel_rebuilds=0,
        financial_assessments=0,
        tokenization_calls=0,
        API_calls=0,
        GPU_operations=0,
        model_loads=0,
        cache_is_new_execution_representation_not_original_material_bytes=True,
        dropout_random_trajectory_changed=True,
        stochastic_or_bitwise_training_equivalence_claimed=False,
        deterministic_prefix_target_objective_preserved=True,
        workers=workers,
        finished_at=p.now(),
    )
    p.write_once(output / "manifest.json", manifest)
    return manifest


class TrajectoryPool:
    """Privately bound readonly numeric cache, never an original-material claim."""

    def __init__(self, *, mint, root, manifest, pool, index, inputs, positions):
        p.require(mint is _MINT, "trajectory.private_pool_constructor")
        object.__setattr__(self, "_mint", mint)
        object.__setattr__(self, "cache_root", root)
        object.__setattr__(self, "manifest", original_materials.freeze_json(manifest))
        object.__setattr__(self, "manifest_id", manifest["id"])
        object.__setattr__(self, "cache_id", manifest["id"])
        object.__setattr__(self, "pool", pool)
        object.__setattr__(self, "packages", original_materials.freeze_json(index["packages"]))
        object.__setattr__(
            self,
            "_by_id",
            original_materials.freeze_json({row["package_id"]: row for row in self.packages}),
        )
        object.__setattr__(self, "_inputs", inputs)
        object.__setattr__(self, "_positions", positions)
        object.__setattr__(self, "actual_budget", self.manifest["pool_budgets"][pool])
        object.__setattr__(
            self, "source_material_budget", self.manifest["source_material_budgets"][pool]
        )
        object.__setattr__(self, "kernel_id", manifest["kernel_id"])
        object.__setattr__(self, "material_verification_id", manifest["material_verification_id"])

    def __setattr__(self, *_):
        raise TypeError("trajectory pool metadata is immutable")

    def row_arrays(self, package):
        package_id = package if isinstance(package, str) else package["package_id"]
        row = self._by_id[package_id]
        for segment in row["segments"]:
            start, length = segment["input_offset"], segment["input_length"]
            target_start, count = segment["target_offset"], segment["target_count"]
            ids = self._inputs[start : start + length]
            positions = self._positions[target_start : target_start + count]
            targets = ids[positions]
            targets.flags.writeable = False
            yield {
                "input_ids": ids,
                "target_positions": positions,
                "target_ids": targets,
                "sequence_length": length,
                "target_token_count": count,
                "source_response_indices": segment["source_response_indices"],
            }


def require_pool(pool):
    p.require(
        type(pool) is TrajectoryPool
        and pool._mint is _MINT
        and pool.manifest_id == pool.manifest["id"] == pool.cache_id
        and pool.kernel_id == pool.manifest["kernel_id"]
        and not pool._inputs.flags.writeable
        and not pool._positions.flags.writeable,
        "trajectory.privately_verified_readonly_pool",
    )
    return pool


def load_pool(cache_root, manifest_or_descriptor, pool):
    """Verify metadata and both numeric-file SHAs once per worker, then mmap."""
    root = Path(cache_root).resolve()
    p.require(pool in p.POOLS, "trajectory.registered_pool")
    if "schema_version" in manifest_or_descriptor:
        manifest = manifest_or_descriptor
    else:
        manifest = json.loads(_read_bound(root, manifest_or_descriptor))
    p.checked(manifest, "trajectory_material_cache")
    key = str(root), manifest["id"], pool
    if key in _LOADED:
        return require_pool(_LOADED[key])
    selected = manifest["pools"][pool]
    index = p.checked(
        json.loads(_read_bound(root, selected["package_index"])), "trajectory_pool_index"
    )
    p.require(
        index["id"] == selected["package_index_id"]
        and index["pool"] == pool
        and index["actual_budget"] == manifest["pool_budgets"][pool]
        and index["source_material_budget"] == manifest["source_material_budgets"][pool],
        "trajectory.actual_pool_index_binding",
    )
    arrays = []
    for name, elements in (
        ("input_ids", "input_elements"),
        ("target_positions", "target_elements"),
    ):
        reference = selected[name]
        path = original_materials._path(root, reference["path"])
        p.require(
            path.stat().st_size == reference["bytes"] and p.sha(path) == reference["sha256"],
            "trajectory.actual_numeric_file_bytes",
        )
        array = np.load(path, mmap_mode="r", allow_pickle=False)
        p.require(
            array.dtype == np.dtype(np.int32)
            and array.ndim == 1
            and len(array) == index[elements] == selected[elements]
            and not array.flags.writeable,
            "trajectory.readonly_int32_array_shape",
        )
        arrays.append(array)
    value = TrajectoryPool(
        mint=_MINT,
        root=root,
        manifest=manifest,
        pool=pool,
        index=index,
        inputs=arrays[0],
        positions=arrays[1],
    )
    _LOADED[key] = value
    return value
