"""Immutable, bounded, lossless stage publication; never a Git or training entry.

Raw originals remain untouched. Every selected file is content-bound, secret
scanned, format-checked and round-tripped through deterministic <=32 MiB gzip
tar shards. Large member/duplicate indices are paged rather than giant JSON
arrays. Materials never traverse the registered Student execution directory.
"""

import gzip
import hashlib
import io
import json
import os
import stat
import struct
import tarfile
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
from pathlib import Path, PurePosixPath

from ..finance_qa_vnext_basis_student.publication import _credential
from . import protocol as p

MAX_SHARD_BYTES = 32 * 1024 * 1024
MAX_LOGICAL_FILE_BYTES = 1024 * 1024 * 1024
FRAGMENT_BYTES = 16 * 1024 * 1024
FRAGMENT_NAMESPACE = "__publication_chunks__"
INDEX_PAGE_BYTES = 4 * 1024 * 1024
STUDENT_PARTS = {
    "execution",
    "student_execution",
    "student_results",
    "students",
    "training",
    "scores",
    "evaluation",
    "results",
}
MATERIAL_REQUIRED = {
    "generation_report.json",
    "budget_finalization.json",
    "freeze.json",
    "registry.json",
    "population.json",
    "materialization_index.json",
    "material_gate.json",
    "session_results.json",
}


def _require(condition, code):
    p.require(condition, "publication." + code)


def _relative(name):
    _require(
        isinstance(name, str)
        and name
        and "\\" not in name
        and not any(ord(char) < 32 or ord(char) == 127 for char in name),
        "safe_relative_name",
    )
    path = PurePosixPath(name)
    _require(
        not path.is_absolute()
        and path.as_posix() == name
        and not {"", ".", ".."} & set(path.parts),
        "normalized_relative_name",
    )
    lower = [part.casefold() for part in path.parts]
    _require(
        not any(
            part in {".git", "wallet", "credentials", "__pycache__"} or part.startswith("runtime")
            for part in lower[:-1]
        ),
        "no_wallet_or_runtime_directory",
    )
    basename = lower[-1]
    _require(
        not (
            basename == ".env"
            or basename.startswith(".env.")
            or basename.endswith(
                (
                    ".env",
                    ".db",
                    ".db-wal",
                    ".db-shm",
                    ".sqlite",
                    ".sqlite3",
                    ".sqlite-wal",
                    ".sqlite-shm",
                    ".pem",
                    ".key",
                )
            )
            or basename in {"id_rsa", "id_ed25519"}
        ),
        "no_wallet_environment_or_credentials",
    )
    return path


def _regular_root(path):
    path = Path(path).absolute()
    _require(
        path.is_dir() and not any(part.is_symlink() for part in (path, *path.parents)),
        "regular_root_no_symlink",
    )
    return path


def _read_member(root, name, *, offset=0, count=None):
    """Open every path component NOFOLLOW and reject nonregular/oversize files."""
    parts = _relative(name).parts
    with ExitStack() as stack:
        directory = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        stack.callback(os.close, directory)
        for component in parts[:-1]:
            directory = os.open(
                component, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=directory
            )
            stack.callback(os.close, directory)
        descriptor = os.open(
            parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory
        )
        stack.callback(os.close, descriptor)
        before = os.fstat(descriptor)
        _require(stat.S_ISREG(before.st_mode), "only_regular_member")
        _require(
            before.st_size <= MAX_LOGICAL_FILE_BYTES,
            "logical_member_over_1GiB_capacity_no_truncation",
        )
        expected = before.st_size - offset if count is None else count
        _require(
            type(offset) is int
            and type(expected) is int
            and 0 <= offset <= before.st_size
            and 0 <= expected <= before.st_size - offset,
            "exact_logical_byte_range",
        )
        os.lseek(descriptor, offset, os.SEEK_SET)
        blocks, length = [], 0
        while length < expected:
            block = os.read(descriptor, min(1024 * 1024, expected - length))
            _require(block, "complete_logical_byte_range")
            length += len(block)
            blocks.append(block)
        after = os.fstat(descriptor)

        def fingerprint(value):
            return (value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns, value.st_ctime_ns)

        _require(
            fingerprint(before) == fingerprint(after) and length == expected,
            "source_changed_during_read",
        )
        return b"".join(blocks)


def _json(raw):
    def pairs(values):
        result = {}
        for key, value in values:
            _require(key not in result, "duplicate_JSON_key")
            result[key] = value
        return result

    try:
        value = json.loads(raw, object_pairs_hook=pairs)
        _require(p.encode(value) == raw, "canonical_original_JSON")
        return value
    except (ValueError, TypeError, UnicodeError):
        # Never include untrusted JSON text (which might contain a credential).
        raise ValueError("fixed_kernel.publication.invalid_or_noncanonical_JSON") from None


def _scan(raw, name, secret):
    _require(
        secret not in raw and secret not in name.encode(), "credential_detected_no_value_disclosed"
    )
    _require(not raw.startswith(b"SQLite format 3\0"), "SQLite_content_forbidden")


def _load_json(root, name, secret):
    raw = _read_member(root, name)
    _scan(raw, name, secret)
    return _json(raw)


def _is_student(root, name):
    parts = PurePosixPath(name).parts
    if any(part.casefold() in STUDENT_PARTS for part in parts[:-1]):
        return True
    for depth in range(1, len(parts)):
        if (root.joinpath(*parts[:depth]) / "preparation/execution_freeze.json").exists():
            return True
    return False


def _inventory(root, stage, allowlist, approved):
    names, excluded = set(), []
    starts = sorted(set(allowlist)) if allowlist is not None else [""]
    _require(allowlist is None or len(starts) == len(allowlist), "unique_explicit_allowlist")

    def visit(name):
        if name:
            _relative(name)
            _require(
                PurePosixPath(name).parts[0] != FRAGMENT_NAMESPACE,
                "reserved_physical_chunk_namespace",
            )
        path = root / name
        _require(not path.is_symlink(), "no_member_or_directory_symlink")
        if (
            name
            and stage == "materials"
            and (
                any(part.casefold() in STUDENT_PARTS for part in PurePosixPath(name).parts)
                or (path.is_dir() and (path / "preparation/execution_freeze.json").exists())
                or _is_student(root, name)
            )
        ):
            _require(allowlist is None, "Student_results_forbidden_in_material_allowlist")
            excluded.append(
                {
                    "path": name,
                    "reason": "Student_execution_outside_materials_stage",
                    "contents_read": False,
                }
            )
            return
        if path.is_dir():
            for child in sorted(path.iterdir(), key=lambda value: value.name):
                visit(str(child.relative_to(root)))
            return
        _require(path.is_file(), "only_existing_regular_source_entries")
        suffix = path.suffix.lower()
        if suffix == ".log":
            excluded.append(
                {
                    "path": name,
                    "reason": "console_log_not_scientific_allowlist_retained_locally",
                    "contents_read": False,
                }
            )
            return
        _require(
            suffix in {".json", ".jsonl", ".xml", ".safetensors"}, "unregistered_source_format"
        )
        if suffix == ".safetensors":
            _require(
                stage == "results"
                and name in approved
                and path.name == "final_adapter.safetensors",
                "only_explicit_approved_final_LoRA_no_base_weights",
            )
        names.add(name)

    for name in starts:
        visit(name)
    return sorted(names), sorted(excluded, key=lambda row: row["path"])


def _materials_gate(root, secret):
    generation = p.checked(
        _load_json(root, "generation_report.json", secret), "material_generation_report"
    )
    budget = p.checked(
        _load_json(root, "budget_finalization.json", secret), "kernel_budget_finalization"
    )
    registry = p.checked(_load_json(root, "registry.json", secret), "material_registry")
    frozen = _load_json(root, "freeze.json", secret)
    index = p.checked(
        _load_json(root, "materialization_index.json", secret), "materialization_index"
    )
    selected = p.checked(_load_json(root, "population.json", secret), "population")
    results = _load_json(root, "session_results.json", secret)
    _require(
        generation["generation_closed"] is True
        and generation["no_inflight_requests"] is True
        and generation["registered_sessions"] == 10240
        and generation["status"] in {"COMPLETE_FIXED_COLLECTION", "STOP_INCOMPLETE_OR_CONTRACT"},
        "closed_generation_full_denominator_required",
    )
    _require(
        budget["purpose_closed"] is True
        and budget["report_id"] == generation["id"]
        and budget["freeze_id"] == registry["freeze_id"] == frozen["id"],
        "closed_budget_same_report_and_freeze",
    )
    _require(
        len(registry["sessions"]) == registry["session_count"] == 10240
        and len({row["session_id"] for row in registry["sessions"]}) == 10240,
        "complete_registered_10240_identity",
    )
    _require(
        index["registry_id"] == registry["id"]
        and index["freeze_id"] == frozen["id"]
        and index["complete_registered_denominator"] == 10240,
        "complete_materialization_denominator",
    )
    registered_ids = {row["session_id"] for row in registry["sessions"]}
    _require(
        len(selected["tasks"]) == 200
        and len({row["task_id"] for row in selected["tasks"]}) == 200
        and registry["population_id"] == selected["id"],
        "same_200_scientific_population",
    )
    _require(
        isinstance(results, list)
        and len(results) == 10240
        and {row["session_id"] for row in results} == registered_ids,
        "every_registered_terminal_result_retained",
    )
    _require(
        len(index["entries"]) == 10240
        and {row["registered_session_id"] for row in index["entries"]} == registered_ids,
        "every_registered_material_outcome_retained",
    )
    references = [
        row[key] for row in results for key in ("session", "qualification") if row.get(key)
    ]
    references += [
        row[key] for row in index["entries"] for key in ("outcome", "package") if row.get(key)
    ]
    for reference in references:
        _relative(reference["path"])
        _require(
            isinstance(reference.get("sha256"), str) and isinstance(reference.get("id"), str),
            "explicit_original_artifact_reference",
        )
    _require(
        all(
            type(generation[key]) is int and 0 <= generation[key] <= 10240
            for key in ("finished_sessions", "unrequested_sessions")
        ),
        "explicit_observed_collection_counts",
    )
    if generation["status"] == "COMPLETE_FIXED_COLLECTION":
        _require(
            generation["finished_sessions"] == 10240
            and generation["unrequested_sessions"] == 0
            and all(row["status"] == "finished" for row in results),
            "complete_collection_is_not_stopped_prefix",
        )
    else:
        _require(index["collection_complete"] is False, "stopped_prefix_not_complete_material")
    return (
        {
            "stage": "materials",
            "report_path": "generation_report.json",
            "report_id": generation["id"],
            "report_status": generation["status"],
            "budget_finalization_id": budget["id"],
            "freeze_id": frozen["id"],
            "registry_id": registry["id"],
            "registered_denominator": 10240,
            "gate_FAIL_does_not_prevent_closed_evidence_publication": True,
        },
        set(MATERIAL_REQUIRED) | {row["path"] for row in references},
        {},
        references,
    )


def _results_gate(code_root, root, secret, report_path, approved_paths):
    _require(isinstance(report_path, str), "explicit_execution_report_path_required")
    report_path = _relative(report_path).as_posix()
    directory = PurePosixPath(report_path).parent
    _require(
        directory.as_posix() != "." and PurePosixPath(report_path).name == "report.json",
        "dedicated_execution_report_directory",
    )
    report = p.checked(_load_json(root, report_path, secret), "execution_report")
    _require(
        report["actual_complete"] is True
        and report["status"] in {"COMPLETE_NO_POSITIVE_DIRECTION", "COMPLETE_FIXED_CONFIRMATION"},
        "actual_complete_execution_terminal_required",
    )
    freeze_path = str(directory / "preparation/execution_freeze.json")
    frozen = p.checked(_load_json(root, freeze_path, secret), "execution_freeze")
    _require(
        (code_root / frozen["output_directory"]).absolute() == (root / directory).absolute()
        and report["study_freeze_id"] == frozen["study_freeze_id"]
        and report["kernel_id"] == frozen["kernel_id"],
        "execution_directory_and_frozen_inputs_join",
    )
    decision_path = str(directory / "decision.json")
    decision = p.checked(_load_json(root, decision_path, secret), "actual_direction_decision")
    _require(
        report["decision_id"] == decision["id"] and decision["actual_complete"] is True,
        "execution_actual_decision_join",
    )
    jobs = [("A", arm, seed) for arm in p.ARMS for seed in p.SEEDS]
    if report["status"] == "COMPLETE_NO_POSITIVE_DIRECTION":
        _require(
            decision["selected_arm"] == "alpha0"
            and report["actual_training_runs"] == 9
            and report["actual_evaluation_sessions"] == 1620,
            "completed_no_move_is_not_missing_confirmation",
        )
    else:
        _require(
            decision["selected_arm"] in {"plus", "minus"}
            and report["actual_training_runs"] == 15
            and report["actual_evaluation_sessions"] == 10260
            and report["confirmation_sessions"] == 8640,
            "complete_selected_direction_confirmation",
        )
        jobs += [
            ("B", arm, seed) for arm in ("alpha0", decision["selected_arm"]) for seed in p.SEEDS
        ]
    required = {report_path, freeze_path, decision_path}
    approved = {}
    for pool, arm, seed in jobs:
        training = directory / "training" / f"{pool}_{arm}_{seed}"
        training_path = str(training / "report.json")
        row = p.checked(_load_json(root, training_path, secret), "training_report")
        adapter = row["final_adapter"]
        _require(
            row["actual_complete"] is True
            and row["status"] == "COMPLETE_FINAL_CHECKPOINT"
            and row["optimizer_updates"] == 400
            and row["epochs_completed"] == 10
            and row["final_adapter_restored_identity_verified"] is True
            and (row["pool"], row["arm"], row["seed"]) == (pool, arm, seed)
            and row["study_freeze_id"] == report["study_freeze_id"]
            and row["kernel_id"] == report["kernel_id"]
            and adapter["parameter_digest"] == row["checkpoint_id"]
            and adapter["path"] == "final_adapter.safetensors",
            "approved_actual_final_LoRA_report",
        )
        name = str(training / adapter["path"])
        approved[name] = {
            "bytes": adapter["bytes"],
            "sha256": adapter["sha256"],
            "training_report_id": row["id"],
            "checkpoint_id": row["checkpoint_id"],
        }
        required.update((training_path, name))
    _require(
        approved_paths is not None and set(approved_paths) == set(approved),
        "caller_approved_exact_final_adapter_paths_required",
    )
    source_manifest_path = str(directory / "manifest.json")
    source_manifest = p.checked(
        _load_json(root, source_manifest_path, secret), "evaluation_manifest"
    )
    _require(
        source_manifest["report_id"] == report["id"]
        and source_manifest["phase"] == "fixed_kernel_value_execution",
        "producer_execution_manifest_closed",
    )
    required.add(source_manifest_path)
    return (
        {
            "stage": "results",
            "report_path": report_path,
            "report_id": report["id"],
            "report_status": report["status"],
            "execution_freeze_id": frozen["id"],
            "study_freeze_id": frozen["study_freeze_id"],
            "source_execution_manifest_id": source_manifest["id"] if source_manifest else None,
            "source_execution_manifest_may_include_locally_retained_console_logs": True,
            "new_publication_manifest_not_a_relabelled_source_closure": True,
        },
        required,
        approved,
        [],
    )


def _safetensors(raw):
    _require(len(raw) >= 8, "final_adapter_binary_header")
    length = struct.unpack("<Q", raw[:8])[0]
    _require(0 < length <= min(1024 * 1024, len(raw) - 8), "bounded_final_adapter_header")
    try:
        header = json.loads(raw[8 : 8 + length])
    except (ValueError, UnicodeError):
        raise ValueError("fixed_kernel.publication.invalid_final_adapter_header") from None
    tensors = {key: value for key, value in header.items() if key != "__metadata__"}
    _require(
        tensors
        and all(
            name.endswith((".lora_A", ".lora_B")) and (".q_proj." in name or ".v_proj." in name)
            for name in tensors
        ),
        "LoRA_only_no_base_parameters",
    )
    intervals = []
    for metadata in tensors.values():
        shape = metadata["shape"]
        _require(
            metadata["dtype"] == "F32"
            and isinstance(shape, list)
            and all(type(size) is int and size > 0 for size in shape),
            "registered_FP32_adapter_tensors",
        )
        count = 1
        for size in shape:
            count *= size
        left, right = metadata["data_offsets"]
        _require(
            type(left) is int and type(right) is int and left >= 0 and right - left == count * 4,
            "adapter_tensor_storage",
        )
        intervals.append((left, right))
    intervals.sort()
    _require(
        intervals[0][0] == 0
        and all(
            left == previous[1]
            for previous, (left, _) in zip(intervals, intervals[1:], strict=False)
        )
        and intervals[-1][1] == len(raw) - 8 - length,
        "complete_nonoverlapping_adapter_payload",
    )
    return len(tensors)


def _scan_member(root, name, secret, approved):
    raw = _read_member(root, name)
    _scan(raw, name, secret)
    suffix = PurePosixPath(name).suffix.lower()
    result = {"path": name, "bytes": len(raw), "sha256": p.sha(raw), "format": suffix.lstrip(".")}
    if suffix == ".json":
        value = _json(raw)
        if isinstance(value, dict) and isinstance(value.get("id"), str):
            result["record_id"] = value["id"]
    elif suffix == ".jsonl":
        count = 0
        for line in raw.splitlines(keepends=True):
            content = (
                line[:-2] if line.endswith(b"\r\n") else line[:-1] if line.endswith(b"\n") else line
            )
            _json(content)
            count += 1
        result["canonical_JSONL_records"] = count
        result["original_newline_bytes_preserved"] = True
    elif suffix == ".xml":
        _require(
            b"<!DOCTYPE" not in raw.upper() and b"<!ENTITY" not in raw.upper(),
            "XML_external_entities_forbidden",
        )
        try:
            ET.fromstring(raw)
        except ET.ParseError:
            raise ValueError("fixed_kernel.publication.invalid_test_XML") from None
    else:
        _require(
            name in approved
            and result["bytes"] == approved[name]["bytes"]
            and result["sha256"] == approved[name]["sha256"],
            "exact_approved_final_adapter_bytes",
        )
        result.update(approved[name])
        result["LoRA_tensor_count"] = _safetensors(raw)
    return result


def _tar_member(row):
    member = tarfile.TarInfo(row["path"])
    member.size, member.mode, member.mtime = row["bytes"], 0o644, 0
    member.uid = member.gid = 0
    member.uname = member.gname = ""
    try:
        member.tobuf(format=tarfile.USTAR_FORMAT)
    except (ValueError, UnicodeError):
        raise ValueError(
            "fixed_kernel.publication.member_path_outside_explicit_USTAR_domain"
        ) from None
    return member


def _tar_bytes(payload_blocks):
    return ((payload_blocks + 1024 + 10239) // 10240) * 10240


def _fits(payload_blocks):
    count = _tar_bytes(payload_blocks)
    # zlib's conservative compress-bound overhead plus the gzip header/trailer.
    bound = count + (count >> 12) + (count >> 14) + (count >> 25) + 31
    return count <= MAX_SHARD_BYTES and bound <= MAX_SHARD_BYTES


def _partition(members):
    groups, current, size = [], [], 0
    for row in members:
        _tar_member(row)
        increment = 512 + ((row["bytes"] + 511) // 512) * 512
        _require(
            _fits(increment), "single_member_plus_container_overhead_exceeds_32MiB_no_truncation"
        )
        if current and not _fits(size + increment):
            groups.append(current)
            current, size = [], 0
        current.append(row)
        size += increment
    if current:
        groups.append(current)
    return groups


def _physical_members(root, originals, secret):
    physical = []
    for row in originals:
        increment = 512 + ((row["bytes"] + 511) // 512) * 512
        split = not _fits(increment)
        try:
            _tar_member(row)
        except ValueError:
            split = True
        identifier = p.sha(p.encode([row["path"], row["sha256"]]))
        ranges = (list(range(0, row["bytes"], FRAGMENT_BYTES)) or [0]) if split else [0]
        _require(not split or _fits(512 + FRAGMENT_BYTES), "registered_fragment_fits_shard")
        for number, offset in enumerate(ranges):
            count = min(FRAGMENT_BYTES, row["bytes"] - offset) if split else row["bytes"]
            name = f"{FRAGMENT_NAMESPACE}/{identifier}/{number:05d}.part" if split else row["path"]
            digest = (
                p.sha(_read_member(root, row["path"], offset=offset, count=count))
                if split
                else row["sha256"]
            )
            physical.append(
                {
                    "path": name,
                    "bytes": count,
                    "sha256": digest,
                    "logical_path": row["path"],
                    "logical_sha256": row["sha256"],
                    "logical_offset": offset,
                    "fragment_index": number,
                    "fragment_count": len(ranges),
                }
            )
        # Whole-file recheck also catches secrets crossing a fragment boundary.
        if split:
            raw = _read_member(root, row["path"])
            _scan(raw, row["path"], secret)
            _require(
                p.sha(raw) == row["sha256"], "logical_source_unchanged_before_any_archive_write"
            )
        row["physical_member_count"] = len(ranges)
    return sorted(physical, key=lambda row: row["path"])


def _physical_bytes(root, row):
    return _read_member(
        root,
        row.get("logical_path", row["path"]),
        offset=row.get("logical_offset", 0),
        count=row["bytes"],
    )


def _logical_roundtrips(root, destination, originals, physical):
    by_archive = {}
    for row in physical:
        by_archive.setdefault(row["publication_archive"], {})[row["path"]] = row
    digests = {row["path"]: hashlib.sha256() for row in originals}
    covered = dict.fromkeys(digests, 0)
    # One sequential decompression per shard, not one reopen per small file.
    for archive_name, expected in sorted(by_archive.items()):
        observed = []
        with tarfile.open(destination / archive_name, "r|gz") as archive:
            for member in archive:
                row = expected[member.name]
                name = row["logical_path"]
                _require(
                    row["logical_offset"] == covered[name], "ordered_gapless_logical_reconstruction"
                )
                raw = archive.extractfile(member).read()
                _require(
                    len(raw) == row["bytes"] and p.sha(raw) == row["sha256"],
                    "exact_logical_fragment_reconstruction",
                )
                digests[name].update(raw)
                covered[name] += len(raw)
                observed.append(member.name)
        _require(observed == list(expected), "complete_logical_physical_member_index")
    for original in originals:
        _require(
            covered[original["path"]] == original["bytes"]
            and digests[original["path"]].hexdigest() == original["sha256"]
            and p.sha(_read_member(root, original["path"])) == original["sha256"],
            "original_full_logical_SHA_roundtrip",
        )
        original["logical_reconstruction_SHA_verified"] = True


def _pack(root, rows, destination, secret):
    _require(
        not destination.exists() and not destination.is_symlink(), "exclusive_shard_no_overwrite"
    )
    with destination.open("xb") as stream:
        with gzip.GzipFile(
            filename="", mode="wb", fileobj=stream, mtime=0, compresslevel=6
        ) as compressed:
            with tarfile.open(fileobj=compressed, mode="w", format=tarfile.USTAR_FORMAT) as archive:
                for row in rows:
                    raw = _physical_bytes(root, row)
                    _scan(raw, row["path"], secret)
                    _require(
                        len(raw) == row["bytes"] and p.sha(raw) == row["sha256"],
                        "source_unchanged_before_packing",
                    )
                    archive.addfile(_tar_member(row), io.BytesIO(raw))
        stream.flush()
        os.fsync(stream.fileno())
    _require(destination.stat().st_size <= MAX_SHARD_BYTES, "compressed_shard_over_32MiB")
    raw_tar = gzip.decompress(destination.read_bytes())
    _require(len(raw_tar) <= MAX_SHARD_BYTES, "raw_tar_shard_over_32MiB")
    with tarfile.open(fileobj=io.BytesIO(raw_tar), mode="r:") as archive:
        _require(
            [member.name for member in archive.getmembers()] == [row["path"] for row in rows],
            "exact_shard_namespace",
        )
        for row, member in zip(rows, archive.getmembers(), strict=True):
            _require(
                member.isfile() and member.mtime == member.uid == member.gid == 0,
                "regular_deterministic_shard_member",
            )
            restored = archive.extractfile(member).read()
            original = _physical_bytes(root, row)
            _require(
                restored == original and p.sha(restored) == row["sha256"], "byte_for_byte_roundtrip"
            )
    return {
        "path": destination.name,
        "bytes": destination.stat().st_size,
        "sha256": p.sha(destination),
        "raw_tar_bytes": len(raw_tar),
        "raw_tar_sha256": p.sha(raw_tar),
        "member_count": len(rows),
        "original_payload_bytes": sum(row["bytes"] for row in rows),
        "every_member_roundtrip_verified": True,
    }


def _index_pages(destination, kind, rows):
    pages, current, size = [], [], 0

    def emit():
        value = p.record(kind, page=len(pages), rows=current)
        raw = p.encode(value)
        _require(len(raw) <= INDEX_PAGE_BYTES <= MAX_SHARD_BYTES, "bounded_publication_index_page")
        path = destination / f"{kind}-{len(pages):05d}.json"
        p.write_once(path, value)
        pages.append(
            {
                "path": path.name,
                "bytes": len(raw),
                "sha256": p.sha(raw),
                "id": value["id"],
                "row_count": len(current),
            }
        )

    for row in rows:
        width = len(p.encode(row)) + 1
        _require(width + 1024 <= INDEX_PAGE_BYTES, "index_row_over_page_limit")
        if current and size + width + 1024 > INDEX_PAGE_BYTES:
            emit()
            current, size = [], 0
        current.append(row)
        size += width
    if current:
        emit()
    return pages


def seal_stage(
    code_root,
    data_root,
    stage="materials",
    *,
    allowlist=None,
    report_path=None,
    approved_adapter_paths=None,
    workers=p.CPU_WORKERS,
    secret_loader=_credential,
):
    """Seal one immutable snapshot outside the raw tree; no Git operations.

    ``allowlist`` contains exact relative files/directories, never globs. With no
    materials allowlist the whole material-stage tree is selected, excluding
    console logs and registered Student directories without reading them.
    Results require explicit report_path, allowlist and approved final adapters.
    An existing destination (even unfinished) is never overwritten or deleted.
    """
    _require(stage in {"materials", "results"}, "known_publication_stage")
    code_root, data_root = _regular_root(code_root), _regular_root(data_root)
    _require(code_root != data_root, "independent_code_and_readonly_data_root")
    root = _regular_root(code_root / p.OUTPUT)
    destination = code_root / (p.OUTPUT + "_publication") / stage
    _require(
        not destination.exists()
        and not any(part.is_symlink() for part in (destination, *destination.parents)),
        "exclusive_regular_stage_destination",
    )
    _require(
        not destination.is_relative_to(root) and destination.is_relative_to(code_root),
        "publication_outside_raw_tree",
    )
    _require(type(workers) is int and workers > 0, "positive_scan_workers")
    secret = secret_loader(data_root)
    _require(isinstance(secret, bytes) and len(secret) >= 8, "actual_credential_scan_required")
    if stage == "materials":
        _require(
            report_path in {None, "generation_report.json"}
            and approved_adapter_paths in (None, []),
            "materials_only_no_Student_result_binding",
        )
        closure, required, approved, references = _materials_gate(root, secret)
    else:
        _require(allowlist is not None, "explicit_results_allowlist_required")
        closure, required, approved, references = _results_gate(
            code_root, root, secret, report_path, approved_adapter_paths
        )
    names, excluded = _inventory(root, stage, allowlist, approved)
    expected_names, _ = _inventory(
        root,
        stage,
        None if stage == "materials" else [str(PurePosixPath(report_path).parent)],
        approved,
    )
    _require(names == expected_names, "explicit_allowlist_cannot_drop_stage_scientific_evidence")
    _require(
        all(secret not in row["path"].encode() for row in excluded),
        "credential_in_excluded_name_not_disclosed",
    )
    _require(required <= set(names) and names, "all_required_closed_stage_members_included")
    with ThreadPoolExecutor(max_workers=workers) as pool:
        members = list(pool.map(lambda name: _scan_member(root, name, secret, approved), names))
    by_path = {row["path"]: row for row in members}
    _require(
        all(
            by_path[reference["path"]]["sha256"] == reference["sha256"]
            and by_path[reference["path"]].get("record_id") == reference["id"]
            for reference in references
        ),
        "all_original_session_qualification_package_references_match",
    )
    physical = _physical_members(root, members, secret)
    groups = _partition(physical)
    destination.mkdir(parents=True, exist_ok=False)
    archives = []
    for number, rows in enumerate(groups):
        path = destination / f"raw-{number:05d}.tar.gz"
        archives.append(_pack(root, rows, path, secret))
        for row in rows:
            row["publication_archive"] = path.name
    _logical_roundtrips(root, destination, members, physical)
    _require(
        _inventory(root, stage, allowlist, approved)[0] == names,
        "selected_source_namespace_unchanged",
    )
    duplicates, first = [], {}
    for row in members:
        if row["sha256"] in first:
            duplicates.append(
                {
                    "sha256": row["sha256"],
                    "first_path": first[row["sha256"]],
                    "duplicate_path": row["path"],
                    "both_original_paths_retained": True,
                }
            )
        else:
            first[row["sha256"]] = row["path"]
    member_pages = _index_pages(destination, "original_member_index", members)
    physical_pages = _index_pages(destination, "physical_member_index", physical)
    duplicate_pages = _index_pages(destination, "duplicate_content_index", duplicates)
    digest = hashlib.sha256()
    for row in members:
        digest.update(p.encode(row) + b"\n")
    manifest = p.record(
        "publication_manifest",
        stage=stage,
        closure=closure,
        source_root=p.OUTPUT,
        scope_allowlist=sorted(allowlist) if allowlist is not None else None,
        source_snapshot_sha256=digest.hexdigest(),
        snapshot_digest_rule="canonical member descriptor plus LF in lexical path order",
        original_file_count=len(members),
        original_bytes=sum(row["bytes"] for row in members),
        member_index_pages=member_pages,
        physical_member_index_pages=physical_pages,
        physical_member_count=len(physical),
        logical_files_fragmented=sum(row["physical_member_count"] > 1 for row in members),
        logical_fragment_bytes=FRAGMENT_BYTES,
        maximum_logical_file_bytes=MAX_LOGICAL_FILE_BYTES,
        duplicate_content_index_pages=duplicate_pages,
        duplicate_original_path_count=len(duplicates),
        duplicate_bytes_not_dropped_or_hardlinked=True,
        archives=archives,
        maximum_shard_bytes=MAX_SHARD_BYTES,
        raw_tar_and_compressed_shards_both_bounded=True,
        container_overhead_reserved_for_every_physical_member=True,
        large_logical_files_losslessly_fragmented_without_modifying_originals=True,
        ordered_logical_offsets_full_SHA_and_no_gaps_verified=True,
        deterministic_USTAR_order_owner_mode_and_zero_mtime=True,
        gzip_filename_empty_mtime_zero=True,
        all_original_member_SHA_and_roundtrips_verified=True,
        excluded_local_entries=excluded,
        original_source_files_modified=False,
        previous_stage_publications_modified=False,
        giant_kernel_or_outcome_arrays_written_directly_to_Git=False,
        actual_credential_scanned=True,
        credential_hits=0,
        wallet_runtime_credentials_or_base_weights_published=False,
        publication_is_scoped_evidence_not_a_scientific_PASS=True,
        source_in_memory_material_kernel_not_reconstructed=True,
        API_calls=0,
        GPU_operations=0,
        git_operations=0,
    )
    _require(len(p.encode(manifest)) <= INDEX_PAGE_BYTES, "bounded_top_level_publication_manifest")
    p.write_once(destination / "publication_manifest.json", manifest)
    return manifest
