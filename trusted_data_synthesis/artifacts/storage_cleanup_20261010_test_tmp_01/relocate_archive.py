"""Move verified fixture payloads into the prescribed local-only archive scope."""

import json
import os
import runpy
import stat
from pathlib import Path


def main():
    source = Path(__file__).resolve().parent
    helpers = runpy.run_path(str(source / "cleanup.py"))
    require, sha, publish = (helpers[key] for key in ("require", "sha", "publish"))
    result = json.loads((source / "result.json").read_text())
    verified = json.loads((source / "backup_verified.json").read_text())
    require(result["status"] == "COMPLETE", "cleanup must already be complete")
    require(result["plan_id"] == verified["plan_id"], "backup plan mismatch")
    destination = source.parent / "local_test_archive_20261010_01"
    require(source == helpers["OUTPUT"], "unexpected evidence directory")
    require(destination.parent == destination.parent.resolve(), "redirected destination")
    require(not os.path.lexists(destination), "never overwrite a previous local archive")
    rows = []
    for name, expected in (
        ("test_fixtures.tar.gz", verified["archive_sha256"]),
        ("member_manifest.json.gz", verified["member_manifest_sha256"]),
    ):
        old = source / name
        before = helpers["identity"](old)
        require(stat.S_ISREG(before[2]) and before[6] == 1, "not a single-link regular file")
        rows.append(
            dict(
                source=str(old),
                destination=str(destination / name),
                sha256=expected,
                identity_before=before,
            )
        )
    publish(
        "archive_relocation_intent.json",
        dict(
            at=helpers["now"](),
            cleanup_result_id=result["id"],
            files=rows,
            reason="Keep fixture payloads in the AGENTS.md local_test_archive scope",
            preserves_original_cleanup_records=True,
        ),
    )
    destination.mkdir()
    for row in rows:
        old, new = Path(row["source"]), Path(row["destination"])
        require(helpers["identity"](old) == row["identity_before"], "source changed")
        require(not os.path.lexists(new), "destination already exists")
        os.rename(old, new)
        row["identity_after"] = helpers["identity"](new)
        require(row["identity_after"][:2] == row["identity_before"][:2], "not a same-inode move")
        require(sha(new) == row["sha256"], "archive hash changed")
    for directory in (source, destination, destination.parent):
        fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    record = publish(
        "archive_location.json",
        dict(
            at=helpers["now"](),
            status="COMPLETE",
            cleanup_result_id=result["id"],
            files=rows,
            fixture_payloads_local_only=True,
            original_evidence_not_rewritten=True,
            archive=str(destination / "test_fixtures.tar.gz"),
            member_manifest=str(destination / "member_manifest.json.gz"),
            sha256_verified_after_same_filesystem_rename=True,
        ),
    )
    print(json.dumps(dict(status=record["status"], archive=record["archive"], id=record["id"])))


if __name__ == "__main__":
    main()
