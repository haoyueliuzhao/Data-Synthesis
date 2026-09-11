"""Acquire official TRAIN/DEV source bytes once; never repurpose frozen benchmark tests.

This is public-source acquisition, not Teacher synthesis, model evaluation,
financial certification, or training. No credential is read or sent.
"""

import argparse
import hashlib
import subprocess
import tempfile
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

from .core import (
    AUDIT,
    AUDIT_SHA,
    OUTPUT,
    Store,
    encode,
    history_guard,
    read_json,
    record,
    require,
    sha,
)

REVISION = "0f16e2867befa6840783e58be38c9efb9229d742"
REPOSITORY = "https://github.com/czyssrs/FinQA"
FILES = (
    ("finqa/train.json", "dataset/train.json"),
    ("finqa/dev.json", "dataset/dev.json"),
    ("finqa/README.md", "README.md"),
    ("finqa/LICENSE", "LICENSE"),
)
BYTE_CAP = 128 * 1024 * 1024


def fetch_file(specification, *, opener=urllib.request.urlopen):
    relative, upstream = specification
    url = f"https://raw.githubusercontent.com/czyssrs/FinQA/{REVISION}/{upstream}"
    require(specification in FILES, "intake.fixed_public_train_dev_files")
    before = time.monotonic()
    started = datetime.now(timezone.utc).isoformat()
    request = urllib.request.Request(
        url, headers={"User-Agent": "Data-Synthesis-source-inventory/1.0"}
    )
    with opener(request, timeout=120) as response:
        require(
            response.status == 200 and response.geturl() == url, "intake.exact_public_HTTP_source"
        )
        raw = response.read(BYTE_CAP + 1)
        require(0 < len(raw) <= BYTE_CAP, "intake.bounded_nonempty_source")
    if relative.endswith(".json"):
        import json

        rows = json.loads(raw)
        require(isinstance(rows, list) and rows, "intake.original_record_array")
        require(
            all(isinstance(row, dict) and "qa" in row and "table" in row for row in rows),
            "intake.original_FinQA_records",
        )
    return (
        relative,
        raw,
        record(
            "basis_scale_source_download",
            path=relative,
            source_url=url,
            repository=REPOSITORY,
            pinned_revision=REVISION,
            bytes=len(raw),
            sha256=sha(raw),
            git_blob_sha1=hashlib.sha1(
                b"blob " + str(len(raw)).encode() + b"\x00" + raw
            ).hexdigest(),
            started_utc=started,
            elapsed_seconds=time.monotonic() - before,
            http_status=200,
            retries=0,
            original_bytes_unchanged=True,
            teacher_or_judge_request=False,
            credentials_sent=False,
            use="new source inventory; not yet task/relationship certified",
        ),
    )


def git_files():
    """Read the same four immutable blobs via public Git transport after raw HTTPS failed.

    The caller retains the failed raw-HTTPS acquisition separately. No checkout
    or repository code execution occurs; this is not a Teacher retry.
    """
    temporary = Path(tempfile.mkdtemp(prefix="basis-scale-finqa-source-"))
    repository = temporary / "repository.git"
    started = datetime.now(timezone.utc).isoformat()
    before = time.monotonic()
    completed = subprocess.run(
        [
            "git",
            "clone",
            "--bare",
            "--depth",
            "1",
            "--single-branch",
            REPOSITORY + ".git",
            str(repository),
        ],
        capture_output=True,
        check=False,
        timeout=180,
    )
    require(completed.returncode == 0, "intake.public_git_clone_failed")

    def git(*arguments):
        return subprocess.check_output(["git", "--git-dir", str(repository), *arguments])

    require(
        git("rev-parse", "HEAD").decode().strip() == REVISION, "intake.exact_pinned_git_revision"
    )
    for relative, upstream in FILES:
        size = int(git("cat-file", "-s", REVISION + ":" + upstream))
        require(0 < size <= BYTE_CAP, "intake.bounded_original_git_blob")
        raw = git("show", REVISION + ":" + upstream)
        require(len(raw) == size, "intake.git_blob_size")
        blob = git("rev-parse", REVISION + ":" + upstream).decode().strip()
        require(
            blob == hashlib.sha1(b"blob " + str(size).encode() + b"\x00" + raw).hexdigest(),
            "intake.git_blob_identity",
        )
        yield (
            relative,
            raw,
            record(
                "basis_scale_source_git_blob",
                path=relative,
                source_url=f"{REPOSITORY}/blob/{REVISION}/{upstream}",
                repository=REPOSITORY,
                pinned_revision=REVISION,
                bytes=size,
                sha256=sha(raw),
                git_blob_sha1=blob,
                acquisition_started_utc=started,
                acquisition_elapsed_seconds=time.monotonic() - before,
                transport="public Git; immutable original blob, no checkout or code execution",
                original_bytes_unchanged=True,
                Teacher_or_semantic_model_request=False,
                DeepSeek_credential_loaded=False,
            ),
        )


def acquire(root, *, transport="git"):
    root = Path(root)
    history_guard(root)
    audit = Path(AUDIT).read_bytes()
    require(sha(audit) == AUDIT_SHA, "intake.original_user_audit")
    store = Store(root / OUTPUT / "source_intake")
    store.json(
        "acquisition_plan.json",
        record(
            "basis_scale_source_acquisition_plan",
            repository=REPOSITORY,
            pinned_revision=REVISION,
            sources=[{"path": path, "upstream_path": remote} for path, remote in FILES],
            fixed_source_files=4,
            per_response_byte_limit=BYTE_CAP,
            transport=transport,
            raw_https_attempt="preserved separately; failed before any source bytes were recorded",
            max_git_clone_attempts=1,
            prior_evaluation_only_files_are_exclusion_references_not_training_inputs=True,
            duplicate_download_does_not_change_an_existing_source_usage_identity=True,
            financial_relationships_or_company_isolation_certified=False,
            Teacher_sessions=0,
            semantic_model_requests=0,
            tokenizer_loads=0,
            Student_runs=0,
        ),
    )
    store.write("audit.original.txt", audit)
    downloaded = []
    if transport == "https":
        with ThreadPoolExecutor(max_workers=4) as pool:
            received = list(pool.map(fetch_file, FILES))
    else:
        require(transport == "git", "intake.registered_source_transport")
        received = git_files()
    for relative, raw, response in received:
        store.write(relative, raw)
        downloaded.append(response)
    counts = {
        split: len(read_json(store.root / f"finqa/{split}.json")) for split in ("train", "dev")
    }
    license_text = (store.root / "finqa/LICENSE").read_text()
    require("MIT License" in license_text, "intake.license_inspected")
    report = record(
        "basis_scale_source_intake_report",
        status="SOURCE_BYTES_ACQUIRED_NOT_TASK_CERTIFIED",
        counts=counts,
        downloads=downloaded,
        source_transport=transport,
        prior_raw_https_connections_scheduled=4,
        prior_raw_https_outcome=(
            "SSL unexpected EOF surfaced; other thread outcomes were not recorded"
        ),
        current_public_git_clone_attempts=1 if transport == "git" else 0,
        new_Teacher_sessions=0,
        semantic_model_requests=0,
        tokenizer_loads=0,
        Student_runs=0,
        original_evaluation_only_snapshots_not_overwritten=True,
        raw_question_count_is_not_unique_task_or_dual_relation_coverage=True,
        new_training_population_established=False,
        training_allowed=False,
    )
    store.json("report.json", report)
    store.json("history.json", history_guard(root))
    store.seal(report_id=report["id"])
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    print(encode(acquire(args.root)).decode())


if __name__ == "__main__":
    main()
