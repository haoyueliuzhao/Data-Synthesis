"""One zero-network cached CPU build, excluding two declared gallery symlinks.

The original failed attempt and partial source directory remain untouched.
No symlink is created or followed; all other extraction/build guards survive.
"""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import tarfile
import time
import types
from pathlib import Path, PurePosixPath

import build_cross_market_vision_environment_20260927 as old

base = old.base
SCRIPT = "trusted_data_synthesis/scripts/run_cross_market_vision_cached_build_20260927.py"
RAW = base.RAW / "original_evidence_revision_02" / "vision_source_cached_build_02"
KIND = "cross_market_vision_cached_build_protocol"
COMPLETE = "cross_market_vision_cached_build_completed"
PARENT_ID = (
    "cross_market_vision_source_build_protocol:"
    "fd6974d4db5c53dea6c9b498867fea6ff10e5d7f7c463e8097feeea5fc176486"
)
FAILURE_ID = (
    "cross_market_vision_source_build_completed:"
    "d3dbd96af1ad789c47ed635384a3d041783cc9fbb904d725c557247b4517159e"
)
ARCHIVE_SHA256 = "e5b2d896a8226f76cee8c7614d1a6ed834ba50607c3b0a2f2c03bde327447aad"
PREFIX = "vision-" + old.COMMIT
SKIPPED_LINKS = {
    PREFIX + "/gallery/assets/coco/images/000000000001.jpg": "../../astronaut.jpg",
    PREFIX + "/gallery/assets/coco/images/000000000002.jpg": "../../dog2.jpg",
}


def save(path, value):
    base.require(Path(path).resolve().is_relative_to(RAW.resolve()), "vision_cached_output_root")
    base.write(path, value)


def helpers():
    """Reuse exact frozen helper code with independent stage globals, not monkeypatches."""
    namespace = dict(old.__dict__)
    namespace.update(RAW=RAW, BUILD_FLAGS=dict(old.BUILD_FLAGS))
    for name in ("acquire", "run", "register", "protocol", "allowed_url", "NoRedirect"):
        namespace.pop(name, None)
    for name in (
        "save",
        "ref",
        "checked_ref",
        "metadata",
        "child_environment",
        "command",
        "create_environment",
        "pip_install",
        "failure",
    ):
        value = getattr(old, name)
        copied = types.FunctionType(
            value.__code__, namespace, name, value.__defaults__, value.__closure__
        )
        copied.__kwdefaults__ = value.__kwdefaults__
        namespace[name] = copied
    return namespace


def parent_inputs(root):
    prior = old.protocol(root)
    complete = base.checked(base.read(old.RAW / "summary.json"), old.COMPLETE)
    base.require(
        prior["id"] == PARENT_ID
        and complete["id"] == FAILURE_ID
        and complete["protocol_id"] == prior["id"]
        and complete["status"] == "SOURCE_BUILD_FAILED_NO_AUTOMATIC_RETRY"
        and complete["error"].get("guard") == "cross_market.vision_build_no_archive_links_devices"
        and complete["HTTP_requests"] == 4
        and complete["parent_runtime_unchanged"]
        and not (old.RAW / "venv").exists(),
        "vision_cached_exact_failed_parent",
    )
    rows = []
    base.require(len(complete["artifact_receipts"]) == 3, "vision_cached_three_original_receipts")
    for item, recorded in zip(old.ARTIFACTS, complete["artifact_receipts"], strict=True):
        receipt_path = old.RAW / "receipts" / (item["key"] + ".json")
        receipt = base.checked(base.read(receipt_path), "cross_market_vision_source_artifact")
        reference = receipt["actual_file"]
        base.require(
            receipt == recorded
            and receipt["artifact"] == item
            and receipt["protocol_id"] == prior["id"]
            and receipt["HTTP_status"] == 200
            and receipt["status"] == "RECEIVED_NOT_EXECUTED"
            and Path(reference["path"]) == old.RAW / "downloads" / item["filename"],
            "vision_cached_exact_original_artifact",
        )
        old.checked_ref(reference)
        if item["key"] == "source":
            base.require(
                reference["bytes"] == 13267110 and reference["sha256"] == ARCHIVE_SHA256,
                "vision_cached_exact_archive",
            )
        else:
            base.require(
                reference["bytes"] == item["bytes"] and reference["sha256"] == item["sha256"],
                "vision_cached_official_wheel_hash",
            )
        rows.append(
            dict(artifact=item, original_receipt=old.ref(receipt_path), original_file=reference)
        )
    return prior, rows


def register(root):
    if (RAW / "protocol.json").exists():
        return protocol(root)
    prior, rows = parent_inputs(root)
    root = Path(root)
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    payload = (root / SCRIPT).read_bytes()
    base.require(
        payload == subprocess.check_output(["git", "show", head + ":" + SCRIPT], cwd=root),
        "vision_cached_committed_code",
    )
    sources = {**prior["sources"], SCRIPT: base.sha(payload)}
    plan = base.record(
        KIND,
        at=base.now(),
        code_commit=head,
        sources=sources,
        parent_protocol=old.ref(old.RAW / "protocol.json"),
        parent_failure=old.ref(old.RAW / "summary.json"),
        parent_protocol_id=prior["id"],
        parent_failure_id=FAILURE_ID,
        cached_artifacts=rows,
        skipped_gallery_symlinks=SKIPPED_LINKS,
        runtime=prior["runtime"],
        source_python=prior["source_python"],
        inherited_site=prior["inherited_site"],
        build_flags=dict(old.BUILD_FLAGS),
        expected_local_version=old.VERSION,
        maximum_cached_reuses=3,
        maximum_environment_build_attempts=1,
        maximum_build_seconds=old.BUILD_TIMEOUT,
        maximum_archive_entries=old.MAX_ENTRIES,
        maximum_extracted_bytes=old.MAX_EXTRACTED_BYTES,
        maximum_produced_wheel_bytes=old.MAX_WHEEL_BYTES,
        minimum_initial_free_bytes=old.MIN_FREE_BYTES,
        maximum_requested_CPU_jobs=8,
        automatic_retries=0,
        network_requests=0,
        HTTP_requests=0,
        links_created=0,
        links_followed=0,
        expected_skipped_demo_links=2,
        parent_partial_source_touched=False,
        Student_environment_writes=0,
        model_weight_downloads=0,
        model_loads=0,
        GPU_processes=0,
        actual_image_reads=0,
        semantic_certificates=0,
        policy="Copy three fixed verified cache artifacts to new root; skip exactly the two "
        "declared gallery symlink headers without creating/following them. All regular source "
        "bytes and frozen CPU build helpers remain unchanged. Preserve original failure.",
    )
    save(RAW / "protocol.json", plan)
    return plan


def protocol(root):
    plan = base.checked(base.read(RAW / "protocol.json"), KIND)
    for name, digest in plan["sources"].items():
        base.require(base.sha(Path(root) / name) == digest, "vision_cached_frozen_code")
    old.checked_ref(plan["parent_protocol"])
    old.checked_ref(plan["parent_failure"])
    base.require(
        plan["parent_protocol_id"] == PARENT_ID
        and plan["parent_failure_id"] == FAILURE_ID
        and plan["skipped_gallery_symlinks"] == SKIPPED_LINKS
        and plan["build_flags"] == old.BUILD_FLAGS
        and plan["network_requests"] == 0
        and plan["maximum_environment_build_attempts"] == 1
        and len(plan["cached_artifacts"]) == 3,
        "vision_cached_frozen_scope",
    )
    return plan


def reuse(plan, item):
    source = item["original_file"]
    path = Path(source["path"])
    base.require(
        path.is_file() and not path.is_symlink() and path.stat().st_size == source["bytes"],
        "vision_cached_original_regular_file",
    )
    old.checked_ref(item["original_receipt"])
    destination = RAW / "downloads" / item["artifact"]["filename"]
    destination.parent.mkdir(exist_ok=True)
    digest, size = hashlib.sha256(), 0
    with path.open("rb") as reader, destination.open("xb") as writer:
        while chunk := reader.read(2**20):
            size += len(chunk)
            base.require(size <= source["bytes"], "vision_cached_copy_size_cap")
            writer.write(chunk)
            digest.update(chunk)
        base.require(
            size == source["bytes"] and digest.hexdigest() == source["sha256"],
            "vision_cached_copy_hash",
        )
        writer.flush()
        os.fsync(writer.fileno())
    receipt = base.record(
        "cross_market_vision_cached_artifact_reuse",
        at=base.now(),
        protocol_id=plan["id"],
        original_file=source,
        original_receipt=item["original_receipt"],
        copied_file=dict(path=str(destination), bytes=size, sha256=digest.hexdigest()),
        cache_reads=1,
        network_requests=0,
        HTTP_requests=0,
    )
    save(RAW / "receipts" / (item["artifact"]["key"] + ".json"), receipt)
    return receipt


def safe_extract(archive, destination):
    base.require(not destination.exists(), "vision_build_new_extract_directory")
    destination.mkdir()
    seen, skipped, count, size = set(), [], 0, 0
    with tarfile.open(archive, mode="r|gz") as source:
        for member in source:
            count += 1
            name = PurePosixPath(member.name)
            base.require(count <= old.MAX_ENTRIES, "vision_build_archive_entry_cap")
            base.require(
                not name.is_absolute()
                and name.parts
                and name.parts[0] == PREFIX
                and ".." not in name.parts
                and "\\" not in member.name
                and len(member.name) <= 1024
                and member.name not in seen,
                "vision_build_safe_archive_path",
            )
            seen.add(member.name)
            if member.name in SKIPPED_LINKS:
                base.require(
                    member.issym()
                    and member.linkname == SKIPPED_LINKS[member.name]
                    and member.size == 0,
                    "vision_cached_exact_demo_symlink",
                )
                skipped.append(
                    dict(
                        name=member.name,
                        link_target=member.linkname,
                        type="symlink",
                        created=False,
                        followed=False,
                    )
                )
                continue
            base.require(member.isdir() or member.isfile(), "vision_build_no_archive_links_devices")
            target = destination.joinpath(*name.parts)
            base.require(
                target.resolve().is_relative_to(destination.resolve()),
                "vision_build_confined_extract",
            )
            if member.isdir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            size += member.size
            base.require(
                0 <= member.size and size <= old.MAX_EXTRACTED_BYTES,
                "vision_build_archive_expansion_cap",
            )
            target.parent.mkdir(parents=True, exist_ok=True)
            source_file = source.extractfile(member)
            base.require(source_file is not None, "vision_build_regular_archive_member")
            with source_file, target.open("xb") as writer:
                remaining = member.size
                while remaining:
                    chunk = source_file.read(min(2**20, remaining))
                    base.require(bool(chunk), "vision_build_complete_archive_member")
                    writer.write(chunk)
                    remaining -= len(chunk)
    base.require(
        {row["name"] for row in skipped} == set(SKIPPED_LINKS),
        "vision_cached_both_declared_links_recorded",
    )
    source_root = destination / PREFIX
    base.require(
        (source_root / "setup.py").is_file() and (source_root / "version.txt").is_file(),
        "vision_build_expected_source_root",
    )
    return source_root, dict(
        entries=count,
        extracted_file_bytes=size,
        original_commit=old.COMMIT,
        skipped_gallery_symlinks=skipped,
        links_created=0,
        links_followed=0,
    )


def run(root):
    plan, ns = protocol(root), helpers()
    with base.locked(RAW / "run.lock"):
        if (RAW / "summary.json").exists():
            result = base.checked(base.read(RAW / "summary.json"), COMPLETE)
            base.require(result["protocol_id"] == plan["id"], "vision_cached_completion_identity")
            if result["status"] == "CPU_VISION_ENVIRONMENT_READY_NOT_VLM_VALIDATED":
                old.checked_ref(result["produced_wheel"])
            return result
        base.require(not (RAW / "attempt.json").exists(), "vision_cached_reserved_no_retry")
        base.require(
            shutil.disk_usage(RAW).free >= old.MIN_FREE_BYTES, "vision_cached_disk_headroom"
        )
        base.require(
            ns["metadata"](old.parent.SOURCE_PYTHON) == plan["runtime"],
            "vision_cached_parent_before_unchanged",
        )
        save(
            RAW / "attempt.json",
            base.record(
                "cross_market_vision_cached_build_attempt",
                at=base.now(),
                protocol_id=plan["id"],
                attempt=1,
                reserved_cached_reuses=3,
                reserved_environment_build_attempts=1,
                network_requests=0,
                HTTP_requests=0,
            ),
        )
        started, fields = time.monotonic(), {}
        try:
            receipts = [reuse(plan, item) for item in plan["cached_artifacts"]]
            fields["cached_artifact_receipts"] = receipts
            source_root, inventory = safe_extract(
                Path(receipts[0]["copied_file"]["path"]), RAW / "source"
            )
            save(
                RAW / "source_inventory.json",
                base.record(
                    "cross_market_vision_cached_source_inventory",
                    at=base.now(),
                    protocol_id=plan["id"],
                    **inventory,
                ),
            )
            fields["source_inventory"] = inventory
            env = ns["child_environment"](source_root)
            python = ns["create_environment"](plan, source_root, env)
            fields["build_log"] = ns["command"](
                [str(python), "-I", "-B", "setup.py", "bdist_wheel"],
                cwd=source_root,
                env=env,
                label="build_CPU_torchvision",
                timeout=old.BUILD_TIMEOUT,
            )
            wheels = list((source_root / "dist").glob("*.whl"))
            base.require(
                len(wheels) == 1
                and wheels[0].name.startswith("torchvision-0.22.1+localcpu-")
                and not wheels[0].is_symlink()
                and 0 < wheels[0].stat().st_size <= old.MAX_WHEEL_BYTES,
                "vision_cached_one_bounded_wheel",
            )
            fields["produced_wheel"] = old.ref(wheels[0])
            save(
                RAW / "built_wheel.json",
                base.record(
                    "cross_market_vision_cached_locally_built_wheel",
                    at=base.now(),
                    protocol_id=plan["id"],
                    source_receipt=old.ref(RAW / "receipts/source.json"),
                    wheel=fields["produced_wheel"],
                    build_flags=dict(old.BUILD_FLAGS),
                ),
            )
            ns["pip_install"](python, wheels, env, label="install_local_CPU_torchvision")
            fields["smoke_log"] = ns["command"](
                [str(python), "-I", "-B", "-c", old.SMOKE],
                cwd=RAW,
                env=env,
                label="synthetic_CPU_smoke",
                timeout=120,
            )
            lines = Path(fields["smoke_log"]["path"]).read_text().splitlines()
            values = [
                json.loads(line.split("=", 1)[1])
                for line in lines
                if line.startswith("VISION_BUILD_SMOKE=")
            ]
            base.require(len(values) == 1, "vision_cached_one_smoke_receipt")
            fields.update(
                smoke=values[0],
                prepared_runtime=ns["metadata"](python),
                environment_python=str(python),
                status="CPU_VISION_ENVIRONMENT_READY_NOT_VLM_VALIDATED",
            )
        except Exception as error:
            detail = ns["failure"](error)
            if isinstance(error, ValueError) and str(error).startswith(
                "cross_market.vision_cached_"
            ):
                detail["guard"] = str(error)
            fields.update(status="CACHED_SOURCE_BUILD_FAILED_NO_AUTOMATIC_RETRY", error=detail)
        unchanged = ns["metadata"](old.parent.SOURCE_PYTHON) == plan["runtime"]
        old.checked_ref(plan["parent_failure"])
        old.checked_ref(plan["parent_protocol"])
        if not unchanged:
            fields.update(status="PARENT_RUNTIME_CHANGE_REQUIRES_INVESTIGATION")
        result = base.record(
            COMPLETE,
            at=base.now(),
            protocol_id=plan["id"],
            seconds=round(time.monotonic() - started, 3),
            parent_runtime_unchanged=unchanged,
            parent_failed_result_unchanged=True,
            reserved_environment_build_attempts=1,
            reserved_cached_reuses=3,
            completed_cached_reuses=len(list((RAW / "receipts").glob("*.json"))),
            network_requests=0,
            HTTP_requests=0,
            model_weight_downloads=0,
            model_loads=0,
            GPU_processes=0,
            actual_image_reads=0,
            semantic_certificates=0,
            **fields,
        )
        save(RAW / "summary.json", result)
        return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("register", "run", "status"))
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    args = parser.parse_args()
    if args.command == "register":
        result = register(args.root)
    elif args.command == "run":
        result = run(args.root)
    else:
        result = protocol(args.root)
    base.emit(result)


if __name__ == "__main__":
    main()
