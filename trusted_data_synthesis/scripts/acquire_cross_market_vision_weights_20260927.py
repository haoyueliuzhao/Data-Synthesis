"""Bounded acquisition of eighteen pinned official model artifacts; no model load.

Register only after code freeze; run is a separate explicit operation. Every
initial GET and redirect is reserved before sending. Failed or unknown attempts
are never replayed, partial files are not resumed, and denial stops new sends.
"""

import argparse
import hashlib
import os
import shutil
import signal
import ssl
import subprocess
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import provision_cross_market_vision_pilot_20260927 as provision

base = provision.base
RAW = base.RAW / "original_evidence_revision_02" / "vision_model_acquisition_01"
SCRIPT = "trusted_data_synthesis/scripts/acquire_cross_market_vision_weights_20260927.py"
PROTOCOL = "cross_market_vision_weight_acquisition_protocol"
ATTEMPT = "cross_market_vision_artifact_attempt"
REQUEST = "cross_market_vision_artifact_HTTP_reservation"
RECEIPT = "cross_market_vision_artifact_receipt"
SUMMARY = "cross_market_vision_weight_acquisition_summary"
MAX_INITIAL_GETS = 18
MAX_REDIRECTS = 4
MAX_HTTP_REQUESTS = MAX_INITIAL_GETS * (MAX_REDIRECTS + 1)
MAX_CONCURRENT_FILES = 2
MINIMUM_FREE_BYTES = 50_000_000_000
SOCKET_TIMEOUT_SECONDS = 120
ARTIFACT_DEADLINE_SECONDS = 3600
CHUNK_BYTES = 2**20
ALLOWED_HOSTS = (
    "huggingface.co",
    "cdn-lfs.huggingface.co",
    "cdn-lfs.hf.co",
    "cdn-lfs-us-1.hf.co",
    "cdn-lfs-eu-1.hf.co",
    "cas-bridge.xethub.hf.co",
    "us.aws.cdn.hf.co",
)
VERIFIED = {"DOWNLOADED_HASH_VERIFIED_NOT_LOADED", "LOCAL_HASH_VERIFIED_NOT_LOADED"}
REDIRECT_CODES = {301, 302, 303, 307, 308}


def require(condition, reason):
    base.require(condition, "vision_acquisition." + reason)


def confined(path):
    path = Path(path)
    require(not RAW.is_symlink(), "acquisition_root_symlink_forbidden")
    require(RAW.resolve().is_relative_to(base.RAW.resolve()), "registered_output_root")
    require(
        path.resolve().is_relative_to(RAW.resolve()) and ".." not in path.parts,
        "confined_artifact_path",
    )
    require(not path.is_symlink(), "artifact_symlink_forbidden")
    return path


def save(path, value, *, immutable=True):
    base.write(confined(path), value, immutable=immutable)


def reference(path):
    path = Path(path)
    return dict(path=str(path), sha256=base.sha(path), bytes=path.stat().st_size)


def fixed_fields():
    return dict(
        repository=provision.REPO,
        revision=provision.REVISION,
        model_files=provision.manifest(),
        model_directory=str(RAW / "models" / provision.REVISION),
        maximum_initial_GETs=MAX_INITIAL_GETS,
        maximum_initial_GETs_per_file=1,
        maximum_redirects_per_file=MAX_REDIRECTS,
        maximum_physical_HTTP_requests=MAX_HTTP_REQUESTS,
        maximum_concurrent_files=MAX_CONCURRENT_FILES,
        maximum_weight_bytes=provision.MAX_WEIGHT_BYTES,
        maximum_metadata_bytes=provision.MAX_METADATA_BYTES,
        maximum_extra_stream_bytes_per_file=1,
        minimum_free_bytes=MINIMUM_FREE_BYTES,
        socket_timeout_seconds=SOCKET_TIMEOUT_SECONDS,
        artifact_deadline_seconds=ARTIFACT_DEADLINE_SECONDS,
        allowed_HTTPS_hosts=list(ALLOWED_HOSTS),
        direct_connection=True,
        default_TLS_verification=True,
        authentication=False,
        model_discovery=False,
        automatic_retries=0,
        partial_resume=False,
        alternate_sources=False,
        access_denial_stops_remaining_requests=True,
        Python_artifacts_downloaded=0,
        dependency_installs=0,
        model_loads=0,
        GPU_processes=0,
        inference_API_calls=0,
        PDF_opens=0,
        page_renders=0,
        semantic_certificates=0,
        Student_environment_writes=0,
    )


def disk_guard():
    free = shutil.disk_usage(base.RAW).free
    require(free >= MINIMUM_FREE_BYTES, "at_least_50GB_free_required")
    return free


def register(root):
    root = Path(root)
    if (RAW / "protocol.json").exists():
        return protocol(root)
    require(
        not any((RAW / "attempts").glob("*.json"))
        and not any((RAW / "HTTP_requests").glob("*/*.json"))
        and not any((RAW / "receipts").glob("*.json")),
        "no_unregistered_network_activity",
    )
    parent = provision.protocol(root)
    parent_ref = reference(provision.RAW / "protocol.json")
    fields = fixed_fields()
    require(
        parent["model_files"] == fields["model_files"] and parent["revision"] == provision.REVISION,
        "exact_frozen_provision_manifest",
    )
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    sources = dict(parent["sources"])
    for name in (SCRIPT, provision.SCRIPT):
        content = (root / name).read_bytes()
        require(
            content == subprocess.check_output(["git", "show", head + ":" + name], cwd=root),
            "committed_acquisition_code",
        )
        sources[name] = base.sha(content)
    plan = base.record(
        PROTOCOL,
        at=base.now(),
        code_commit=head,
        sources=sources,
        provision_protocol_id=parent["id"],
        provision_protocol_reference=parent_ref,
        available_bytes_at_registration=disk_guard(),
        authority="Separate bounded official artifact acquisition under the user's continue-"
        "experiment resource authority; actual run only after controller freezes and invokes it. "
        "No transfer credit is borrowed from the offline provision stage.",
        network_requests_at_registration=0,
        **fields,
    )
    save(RAW / "protocol.json", plan)
    return plan


def protocol(root):
    plan = base.checked(base.read(RAW / "protocol.json"), PROTOCOL)
    require(all(plan.get(k) == v for k, v in fixed_fields().items()), "immutable_finite_scope")
    for name, digest in plan["sources"].items():
        require(base.sha(Path(root) / name) == digest, "frozen_code")
    parent_ref = plan["provision_protocol_reference"]
    require(reference(Path(parent_ref["path"])) == parent_ref, "provision_bytes")
    parent = base.checked(base.read(parent_ref["path"]), provision.PROTOCOL)
    require(
        parent["id"] == plan["provision_protocol_id"]
        and parent["model_files"] == plan["model_files"],
        "provision_identity",
    )
    return plan


def safe_url(url):
    require(isinstance(url, str) and len(url) <= 32768, "bounded_URL")
    parts = urllib.parse.urlsplit(url)
    require(
        parts.scheme == "https"
        and parts.hostname in ALLOWED_HOSTS
        and parts.port in (None, 443)
        and parts.username is None
        and parts.password is None
        and not parts.fragment
        and "\r" not in url
        and "\n" not in url,
        "official_HTTPS_destination_only",
    )
    return dict(
        scheme="https",
        host=parts.hostname,
        path=parts.path,
        full_URL_sha256=base.sha(url),
        signed_query_not_logged=bool(parts.query),
    )


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def open_once(url, timeout):
    safe_url(url)
    opener = urllib.request.build_opener(
        urllib.request.ProxyHandler({}),
        urllib.request.HTTPSHandler(context=ssl.create_default_context()),
        NoRedirect(),
    )
    request = urllib.request.Request(
        url,
        method="GET",
        headers={
            "Accept-Encoding": "identity",
            "User-Agent": "Data-Synthesis-fixed-artifact-acquisition/1",
        },
    )
    return opener.open(request, timeout=timeout)


def file_paths(row):
    name = row["filename"]
    require(
        Path(name).name == name and name not in {".", ".."} and not name.endswith(".py"),
        "pinned_non_executable_filename",
    )
    directory = confined(RAW / "models" / provision.REVISION)
    return dict(
        final=confined(directory / name),
        partial=confined(directory / (name + ".partial")),
        attempt=confined(RAW / "attempts" / (name + ".json")),
        receipt=confined(RAW / "receipts" / (name + ".json")),
        requests=confined(RAW / "HTTP_requests" / name),
    )


def digesters(row):
    sha256 = hashlib.sha256()
    if row["hash_kind"] == "sha256":
        declared = sha256
    else:
        require(row["hash_kind"] == "git_blob_sha1", "pinned_digest_kind")
        declared = hashlib.sha1(f"blob {row['bytes']}\0".encode())
    return sha256, declared


def update_hashes(sha256, declared, chunk):
    sha256.update(chunk)
    if declared is not sha256:
        declared.update(chunk)


def verified_local(path, row):
    path = confined(path)
    require(path.is_file() and path.stat().st_size == row["bytes"], "local_exact_file_bytes")
    sha256, declared = digesters(row)
    with path.open("rb") as stream:
        while chunk := stream.read(CHUNK_BYTES):
            update_hashes(sha256, declared, chunk)
    require(declared.hexdigest() == row["expected_hash"], "local_exact_manifest_digest")
    return dict(
        path=str(path),
        bytes=row["bytes"],
        sha256=sha256.hexdigest(),
        expected_hash_verified=declared.hexdigest(),
        hash_kind=row["hash_kind"],
    )


def check_binding(value, plan, row, kind):
    base.checked(value, kind)
    require(
        value["protocol_id"] == plan["id"]
        and value["filename"] == row["filename"]
        and value["manifest_entry_sha256"] == base.sha(base.encode(row)),
        "attempt_file_binding",
    )
    return value


def receipt(plan, row, paths, status, **details):
    value = base.record(
        RECEIPT,
        protocol_id=plan["id"],
        filename=row["filename"],
        at=base.now(),
        manifest_entry_sha256=base.sha(base.encode(row)),
        status=status,
        physical_HTTP_requests=len(list(paths["requests"].glob("*.json"))),
        partial_path=str(paths["partial"]),
        partial_bytes=paths["partial"].stat().st_size if paths["partial"].exists() else 0,
        automatic_retries=0,
        model_loaded=False,
        **details,
    )
    save(paths["receipt"], value)
    return value


def reserve_HTTP(plan, row, paths, hop, url):
    destination = safe_url(url)
    with base.locked(RAW / "HTTP_budget.lock", blocking=True):
        require(
            hop <= MAX_REDIRECTS
            and len(list((RAW / "HTTP_requests").glob("*/*.json"))) < MAX_HTTP_REQUESTS,
            "physical_HTTP_budget_exhausted",
        )
        path = paths["requests"] / f"{hop}.json"
        require(not path.exists(), "HTTP_hop_cannot_replay")
        save(
            path,
            base.record(
                REQUEST,
                protocol_id=plan["id"],
                filename=row["filename"],
                hop=hop,
                method="GET",
                destination=destination,
                at=base.now(),
                initial_request=hop == 0,
                retry=False,
            ),
        )


def time_left(deadline, stop):
    require(not stop.is_set(), "transfer_interrupted")
    remaining = deadline - time.monotonic()
    require(remaining > 0, "artifact_deadline_exceeded")
    return min(SOCKET_TIMEOUT_SECONDS, remaining)


def open_bounded(plan, row, paths, deadline, stop, sender):
    url, redirects = row["url"], []
    for hop in range(MAX_REDIRECTS + 1):
        timeout = time_left(deadline, stop)
        reserve_HTTP(plan, row, paths, hop, url)
        try:
            response = sender(url, timeout)
        except urllib.error.HTTPError as error:
            if error.code not in REDIRECT_CODES:
                error.close()
                raise
            target = error.headers.get("Location")
            error.close()
            require(hop < MAX_REDIRECTS, "redirect_cap_exhausted")
            require(isinstance(target, str) and bool(target), "redirect_location_required")
            target = urllib.parse.urljoin(url, target)
            destination = safe_url(target)
            redirects.append(dict(status=error.code, destination=destination))
            url = target
            continue
        return response, redirects
    raise ValueError("vision_acquisition.redirect_cap_exhausted")


def download_file(plan, row, *, sender=open_once, stop=None):
    stop = stop if stop is not None else threading.Event()
    require(row in plan["model_files"], "file_in_frozen_manifest")
    paths = file_paths(row)
    with base.locked(RAW / "file_locks" / (row["filename"] + ".lock")):
        if paths["receipt"].exists():
            previous = check_binding(base.read(paths["receipt"]), plan, row, RECEIPT)
            if previous["status"] in VERIFIED:
                require(
                    verified_local(paths["final"], row) == previous["artifact"],
                    "completed_artifact_unchanged",
                )
            return previous
        if paths["attempt"].exists():
            check_binding(base.read(paths["attempt"]), plan, row, ATTEMPT)
        if paths["final"].exists():
            artifact = verified_local(paths["final"], row)
            return receipt(
                plan,
                row,
                paths,
                "LOCAL_HASH_VERIFIED_NOT_LOADED",
                artifact=artifact,
                recovery_of_existing_attempt=paths["attempt"].exists(),
                local_acquisition_history_not_inferred=True,
            )
        if paths["attempt"].exists() or paths["partial"].exists():
            return receipt(
                plan,
                row,
                paths,
                "UNSETTLED_OR_PARTIAL_NOT_REPLAYED",
                artifact=None,
                error_type="InterruptedOrUnknown",
                http_status=None,
            )
        if stop.is_set():
            return dict(
                filename=row["filename"],
                status="NOT_STARTED_INTERRUPTED",
                artifact=None,
                physical_HTTP_requests=0,
            )
        with base.locked(RAW / "attempt_budget.lock", blocking=True):
            require(
                len(list((RAW / "attempts").glob("*.json"))) < MAX_INITIAL_GETS,
                "initial_GET_budget_exhausted",
            )
            save(
                paths["attempt"],
                base.record(
                    ATTEMPT,
                    protocol_id=plan["id"],
                    filename=row["filename"],
                    manifest_entry_sha256=base.sha(base.encode(row)),
                    at=base.now(),
                    maximum_initial_GETs=1,
                    maximum_redirects=MAX_REDIRECTS,
                    partial_resume=False,
                    status="RESERVED_BEFORE_NETWORK_NO_REFUND",
                ),
            )
        started = time.monotonic()
        byte_count, redirects = 0, []
        try:
            paths["partial"].parent.mkdir(parents=True, exist_ok=True)
            sha256, declared = digesters(row)
            with paths["partial"].open("xb") as stream:
                response, redirects = open_bounded(
                    plan,
                    row,
                    paths,
                    started + ARTIFACT_DEADLINE_SECONDS,
                    stop,
                    sender,
                )
                with response:
                    require(response.status == 200, "full_HTTP_200_required")
                    require(
                        response.headers.get("Content-Encoding", "identity") == "identity",
                        "unencoded_original_artifact_required",
                    )
                    length = response.headers.get("Content-Length")
                    require(
                        length is None or int(length) == row["bytes"], "declared_content_length"
                    )
                    while byte_count <= row["bytes"]:
                        time_left(started + ARTIFACT_DEADLINE_SECONDS, stop)
                        maximum = min(CHUNK_BYTES, row["bytes"] + 1 - byte_count)
                        chunk = response.read(maximum)
                        require(len(chunk) <= maximum, "reader_byte_cap")
                        if not chunk:
                            break
                        stream.write(chunk)
                        byte_count += len(chunk)
                        update_hashes(sha256, declared, chunk)
                        require(byte_count <= row["bytes"], "stream_larger_than_manifest")
                stream.flush()
                os.fsync(stream.fileno())
            require(byte_count == row["bytes"], "stream_smaller_than_manifest")
            require(declared.hexdigest() == row["expected_hash"], "download_manifest_digest")
            require(not paths["final"].exists(), "never_overwrite_final_artifact")
            os.rename(paths["partial"], paths["final"])
            descriptor = os.open(paths["final"].parent, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
            artifact = dict(
                path=str(paths["final"]),
                bytes=byte_count,
                sha256=sha256.hexdigest(),
                expected_hash_verified=declared.hexdigest(),
                hash_kind=row["hash_kind"],
            )
            return receipt(
                plan,
                row,
                paths,
                "DOWNLOADED_HASH_VERIFIED_NOT_LOADED",
                artifact=artifact,
                redirects=redirects,
                http_status=200,
                duration_seconds=time.monotonic() - started,
            )
        except BaseException as error:
            code = error.code if isinstance(error, urllib.error.HTTPError) else None
            if code in (403, 429):
                stop.set()
            status = (
                "TRANSFER_INTERRUPTED_NOT_REFUNDED"
                if isinstance(error, (KeyboardInterrupt, SystemExit))
                or stop.is_set()
                and code is None
                else ("TRANSFER_FAILED_NOT_REFUNDED")
            )
            return receipt(
                plan,
                row,
                paths,
                status,
                artifact=None,
                http_status=code,
                error_type=type(error).__name__,
                error_reason=str(error)
                if isinstance(error, ValueError)
                and str(error).startswith("cross_market.vision_acquisition.")
                else "Transport detail and signed URLs deliberately not persisted",
                redirects=redirects,
                duration_seconds=time.monotonic() - started,
            )


def run(root):
    plan = protocol(root)
    with base.locked(RAW / "controller.lock"):
        disk_guard()
        stop = threading.Event()
        previous = [base.read(path) for path in (RAW / "receipts").glob("*.json")]
        if any(row.get("http_status") in (403, 429) for row in previous):
            stop.set()  # A later run cannot route around an access denial via other files.
        handlers = {}
        if threading.current_thread() is threading.main_thread():
            for number in (signal.SIGINT, signal.SIGTERM):
                handlers[number] = signal.signal(number, lambda *_: stop.set())
        try:
            with ThreadPoolExecutor(max_workers=MAX_CONCURRENT_FILES) as executor:
                futures = [
                    executor.submit(download_file, plan, row, stop=stop)
                    for row in plan["model_files"]
                ]
                results = [future.result() for future in futures]
        finally:
            for number, handler in handlers.items():
                signal.signal(number, handler)
        statuses = dict(Counter(row["status"] for row in results))
        ready = all(row["status"] in VERIFIED for row in results)
        summary = base.record(
            SUMMARY,
            at=base.now(),
            protocol_id=plan["id"],
            status="PINNED_MODEL_FILES_VERIFIED_NOT_LOADED"
            if ready
            else "MODEL_ACQUISITION_NOT_READY_FAILED_OR_INTERRUPTED",
            files=len(results),
            verified_files=sum(row["status"] in VERIFIED for row in results),
            statuses=statuses,
            results=results,
            reserved_file_attempts=len(list((RAW / "attempts").glob("*.json"))),
            reserved_physical_HTTP_requests=len(list((RAW / "HTTP_requests").glob("*/*.json"))),
            physical_request_count_is_conservative_reservation_count=True,
            maximum_initial_GETs=MAX_INITIAL_GETS,
            maximum_HTTP_requests=MAX_HTTP_REQUESTS,
            model_loads=0,
            GPU_processes=0,
            dependency_installs=0,
            PDF_opens=0,
            semantic_certificates=0,
        )
        # Every summary version remains immutable in runs; latest pointer is atomic.
        save(RAW / "runs" / (summary["id"].split(":")[-1] + ".json"), summary)
        save(RAW / "summary.json", summary, immutable=False)
        base.emit({k: v for k, v in summary.items() if k != "results"})
        return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("register", "status", "run"))
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    args = parser.parse_args()
    value = {"register": register, "status": protocol, "run": run}[args.action](args.root)
    if args.action != "run":
        base.emit(value)


if __name__ == "__main__":
    main()
