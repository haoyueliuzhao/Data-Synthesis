"""Lossless evidence export; Git publication remains an explicit scoped operation."""

import argparse
import gzip
import io
import json
import tarfile
from pathlib import Path

from ..finance_qa_vnext_basis_student.publication import _credential
from . import protocol as p
from . import study

DIRECT = {
    "policy.json",
    "freeze.json",
    "registry.json",
    "selected_tasks.json",
    "official_API_preflight.json",
    "code_snapshot.json",
    "cpu_tests.xml",
    "scripted_preflight.json",
    "real_schema_shadow_control.json",
    "tokenizer_asset_check.json",
    "budget_registration.json",
    "execution_started.json",
    "report.json",
    "coverage_metrics.json",
    "token_diagnostics.json",
    "session_results.json",
    "terminal_registry.json",
    "wallet_after_generation.json",
    "budget_finalization.json",
}


def pack_once(output, paths, archive):
    output, archive = Path(output), Path(archive)
    p.require(not archive.exists() and not archive.is_symlink(), "exclusive_evidence_archive")
    names = [str(Path(x).relative_to(output)) for x in paths]
    p.require(
        len(names) == len(set(names)) and names == sorted(names), "unique_sorted_archive_members"
    )
    with archive.open("xb") as stream:
        with gzip.GzipFile(filename="", mode="wb", fileobj=stream, mtime=0) as compressed:
            with tarfile.open(fileobj=compressed, mode="w") as tar:
                for path, name in zip(paths, names, strict=True):
                    p.require(
                        not Path(name).is_absolute()
                        and ".." not in Path(name).parts
                        and Path(path).is_file()
                        and not Path(path).is_symlink(),
                        "safe_archive_member",
                    )
                    raw = Path(path).read_bytes()
                    member = tarfile.TarInfo(name=name)
                    member.size = len(raw)
                    member.mode = 0o644
                    member.mtime = 0
                    member.uid = member.gid = 0
                    member.uname = member.gname = ""
                    tar.addfile(member, io.BytesIO(raw))
    with tarfile.open(archive, "r:gz") as tar:
        p.require([x.name for x in tar.getmembers()] == names, "archive_exact_namespace")
        for name in names:
            member = tar.getmember(name)
            p.require(
                member.isfile() and tar.extractfile(member).read() == (output / name).read_bytes(),
                "lossless_original_evidence_round_trip",
            )
    return archive


def seal(code_root, data_root):
    code_root, data_root, output, _ = study.guarded_roots(code_root, data_root)
    report = p.checked(json.loads((output / "report.json").read_bytes()), "probe_coverage_report")
    freeze = p.checked(json.loads((output / "freeze.json").read_bytes()), "coverage_freeze")
    p.require(
        report["freeze_id"] == freeze["id"] and report["training_admitted"] is False,
        "same_probe_only_report",
    )
    code = p.checked(
        json.loads((output / "code_snapshot.json").read_bytes()), "probe_code_snapshot"
    )
    base = p.checked(
        json.loads((output / "original_code_dependencies.json").read_bytes()),
        "original_code_dependencies",
    )
    study.verify_code(code_root, code, base)
    p.require(
        study._junit(output / "cpu_tests.xml") == freeze["CPU_test_result"], "same_frozen_CPU_tests"
    )
    secret = _credential(data_root)
    paths = sorted(x for x in output.rglob("*") if x.is_file())
    p.require(paths and not any(x.is_symlink() for x in paths), "regular_evidence_files")
    p.require(
        not (output / "artifact_manifest.json").exists()
        and not (output / "raw_evidence.tar.gz").exists(),
        "single_final_publication",
    )
    members, packed = [], []
    for path in paths:
        name = str(path.relative_to(output))
        raw = path.read_bytes()
        p.require(secret not in raw, "credential_not_in_scientific_output")
        p.require(path.suffix in {".json", ".xml"}, "only_registered_JSON_or_test_XML")
        if path.suffix == ".json":
            value = json.loads(raw)
            p.require(p.encode(value) == raw, "canonical_original_JSON")
        direct = name in DIRECT
        members.append(
            {
                "path": name,
                "bytes": len(raw),
                "sha256": p.sha(raw),
                "publication": "direct" if direct else "raw_evidence.tar.gz",
            }
        )
        if not direct:
            packed.append(path)
    archive = pack_once(output, packed, output / "raw_evidence.tar.gz")
    final = p.record(
        "probe_artifact_manifest",
        report_id=report["id"],
        freeze_id=freeze["id"],
        raw_members=members,
        archive={"path": archive.name, "bytes": archive.stat().st_size, "sha256": p.sha(archive)},
        direct_files=sorted(m["path"] for m in members if m["publication"] == "direct"),
        every_original_byte_preserved=True,
        uncompressed_local_originals_retained=True,
        original_experiment_archives_repacked_or_modified=False,
        credential_hits=0,
        SQLite_wallet_and_runtime_files_not_published=True,
    )
    p.write_once(output / "artifact_manifest.json", final)
    return final


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--code-root", type=Path, required=True)
    parser.add_argument("--data-root", type=Path, required=True)
    args = parser.parse_args()
    value = seal(args.code_root, args.data_root)
    print(
        json.dumps(
            {
                "id": value["id"],
                "raw_files": len(value["raw_members"]),
                "archive_bytes": value["archive"]["bytes"],
            }
        )
    )


if __name__ == "__main__":
    main()
