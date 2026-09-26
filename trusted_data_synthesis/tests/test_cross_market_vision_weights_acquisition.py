"""Offline bounded downloader tests: fake HTTPS streams and synthetic tiny files."""

import hashlib
import io
import threading
import urllib.error
from copy import deepcopy
from types import SimpleNamespace

import acquire_cross_market_vision_weights_20260927 as m
import pytest


def artifact(payload=b"pinned original bytes", kind="sha256", filename="config.json"):
    digest = (
        hashlib.sha256(payload).hexdigest()
        if kind == "sha256"
        else hashlib.sha1(f"blob {len(payload)}\0".encode() + payload).hexdigest()
    )
    return dict(
        filename=filename,
        bytes=len(payload),
        hash_kind=kind,
        expected_hash=digest,
        role="metadata",
        url=f"https://huggingface.co/official/repo/resolve/fixed/{filename}",
    )


class Response(io.BytesIO):
    status = 200

    def __init__(self, payload, headers=None):
        super().__init__(payload)
        self.headers = {} if headers is None else headers
        self.read_limits = []

    def read(self, maximum):
        self.read_limits.append(maximum)
        return super().read(maximum)


@pytest.fixture
def tiny(tmp_path, monkeypatch):
    monkeypatch.setattr(m.base, "RAW", tmp_path)
    monkeypatch.setattr(m, "RAW", tmp_path / "new-acquisition")
    row = artifact()
    return dict(
        row=row, plan=dict(id="synthetic-plan", model_files=[row]), payload=b"pinned original bytes"
    )


def test_manifest_is_exact_eighteen_four_weights_no_python_and_bounded():
    fields = m.fixed_fields()
    rows = fields["model_files"]
    assert rows == m.provision.manifest()
    assert len(rows) == 18 and sum(r["role"] == "weights" for r in rows) == 4
    assert sum(r["bytes"] for r in rows if r["role"] == "weights") == 17_056_744_056
    assert sum(r["bytes"] for r in rows if r["role"] == "metadata") < 32 * 2**20
    assert not any(r["filename"].endswith(".py") for r in rows)
    assert fields["maximum_initial_GETs"] == 18
    assert fields["maximum_redirects_per_file"] == 4
    assert fields["maximum_physical_HTTP_requests"] == 90
    assert fields["maximum_concurrent_files"] == 2


@pytest.mark.parametrize(
    "url",
    [
        "http://huggingface.co/a",
        "https://huggingface.co.evil.invalid/a",
        "https://example.invalid/a",
        "https://huggingface.co:444/a",
        "https://user:secret@huggingface.co/a",
        "https://huggingface.co/a#fragment",
        "https://huggingface.co/a\r\nX-Test:bad",
    ],
)
def test_unapproved_destinations_rejected_without_network(url):
    with pytest.raises(ValueError, match="official_HTTPS"):
        m.safe_url(url)


def test_signed_redirect_queries_are_hashed_not_logged():
    view = m.safe_url("https://cas-bridge.xethub.hf.co/object?signature=private-looking-value")
    assert view["signed_query_not_logged"] is True
    assert "private-looking-value" not in str(view)
    assert view["host"] == "cas-bridge.xethub.hf.co"


@pytest.mark.parametrize("kind", ["sha256", "git_blob_sha1"])
def test_attempt_reserved_before_GET_exact_digest_and_local_reuse(tiny, kind):
    row = artifact(tiny["payload"], kind)
    plan = dict(tiny["plan"], model_files=[row])
    calls = []

    def sender(url, timeout):
        paths = m.file_paths(row)
        assert paths["attempt"].is_file() and (paths["requests"] / "0.json").is_file()
        assert url == row["url"] and 0 < timeout <= 120
        calls.append(url)
        return Response(tiny["payload"], {"Content-Length": str(row["bytes"])})

    result = m.download_file(plan, row, sender=sender)
    assert result["status"] == "DOWNLOADED_HASH_VERIFIED_NOT_LOADED"
    assert result["physical_HTTP_requests"] == 1 and not result["model_loaded"]
    paths = m.file_paths(row)
    assert paths["final"].read_bytes() == tiny["payload"] and not paths["partial"].exists()
    assert result == m.download_file(plan, row, sender=lambda *_: pytest.fail("no second GET"))
    assert len(calls) == 1


def test_four_redirects_are_counted_separately_and_bounded(tiny):
    calls = []

    def sender(url, timeout):
        calls.append(url)
        if len(calls) <= 4:
            raise urllib.error.HTTPError(
                url,
                302,
                "redirect",
                {"Location": f"https://cas-bridge.xethub.hf.co/object{len(calls)}?sig=secret"},
                None,
            )
        return Response(tiny["payload"])

    result = m.download_file(tiny["plan"], tiny["row"], sender=sender)
    assert result["status"] in m.VERIFIED and result["physical_HTTP_requests"] == 5
    assert len(calls) == 5 and len(result["redirects"]) == 4
    assert "sig=secret" not in "".join(p.read_text() for p in m.RAW.rglob("*.json") if p.is_file())


def test_fifth_redirect_denied_without_sixth_GET(tiny):
    calls = []

    def sender(url, timeout):
        calls.append(url)
        raise urllib.error.HTTPError(
            url, 302, "redirect", {"Location": "https://cdn-lfs.hf.co/another"}, None
        )

    result = m.download_file(tiny["plan"], tiny["row"], sender=sender)
    assert result["status"] == "TRANSFER_FAILED_NOT_REFUNDED"
    assert result["physical_HTTP_requests"] == len(calls) == 5
    assert "redirect_cap_exhausted" in result["error_reason"]


def test_official_redirect_to_unapproved_host_not_followed(tiny):
    calls = []

    def sender(url, timeout):
        calls.append(url)
        raise urllib.error.HTTPError(
            url, 302, "redirect", {"Location": "https://mirror.invalid/model"}, None
        )

    result = m.download_file(tiny["plan"], tiny["row"], sender=sender)
    assert result["physical_HTTP_requests"] == len(calls) == 1
    assert result["status"] == "TRANSFER_FAILED_NOT_REFUNDED"


@pytest.mark.parametrize("status", [403, 429])
def test_access_denial_stops_other_files_without_retry_or_route_change(tiny, status):
    stop = threading.Event()
    calls = []

    def sender(url, timeout):
        calls.append(url)
        raise urllib.error.HTTPError(url + "?signed=secret", status, "secret", {}, None)

    result = m.download_file(tiny["plan"], tiny["row"], sender=sender, stop=stop)
    assert result["http_status"] == status and stop.is_set()
    assert result["status"] == "TRANSFER_FAILED_NOT_REFUNDED"
    assert result == m.download_file(tiny["plan"], tiny["row"], sender=sender)
    other = artifact(filename="other.json")
    plan = dict(tiny["plan"], model_files=[tiny["row"], other])
    assert (
        m.download_file(plan, other, sender=sender, stop=stop)["status"]
        == "NOT_STARTED_INTERRUPTED"
    )
    assert len(calls) == 1 and "signed=secret" not in str(result)


@pytest.mark.parametrize("case", ["oversize", "short", "wrong_hash", "length", "encoding"])
def test_stream_or_metadata_failure_retains_partial_and_never_retries(tiny, case):
    body, headers = tiny["payload"], {}
    if case == "oversize":
        body += b"too long"
    elif case == "short":
        body = body[:-1]
    elif case == "wrong_hash":
        body = b"x" * len(body)
    elif case == "length":
        headers["Content-Length"] = "999"
    else:
        headers["Content-Encoding"] = "gzip"
    stream = Response(body, headers)
    result = m.download_file(tiny["plan"], tiny["row"], sender=lambda *_: stream)
    paths = m.file_paths(tiny["row"])
    assert result["status"] == "TRANSFER_FAILED_NOT_REFUNDED"
    assert paths["partial"].exists() and not paths["final"].exists()
    assert paths["partial"].stat().st_size <= tiny["row"]["bytes"] + 1
    assert (
        m.download_file(tiny["plan"], tiny["row"], sender=lambda *_: pytest.fail("no retry"))
        == result
    )


@pytest.mark.parametrize("failure", [TimeoutError("secret URL"), KeyboardInterrupt()])
def test_timeout_or_interrupt_has_receipt_and_retained_attempt(tiny, failure):
    def sender(*_):
        raise failure

    result = m.download_file(tiny["plan"], tiny["row"], sender=sender)
    assert result["status"] in {"TRANSFER_FAILED_NOT_REFUNDED", "TRANSFER_INTERRUPTED_NOT_REFUNDED"}
    assert result["physical_HTTP_requests"] == 1
    assert m.file_paths(tiny["row"])["receipt"].is_file()
    assert "secret URL" not in str(result)


def test_unsettled_attempt_is_not_replayed(tiny):
    row, plan = tiny["row"], tiny["plan"]
    paths = m.file_paths(row)
    m.save(
        paths["attempt"],
        m.base.record(
            m.ATTEMPT,
            protocol_id=plan["id"],
            filename=row["filename"],
            manifest_entry_sha256=m.base.sha(m.base.encode(row)),
        ),
    )
    result = m.download_file(
        plan, row, sender=lambda *_: pytest.fail("unsettled GET cannot replay")
    )
    assert result["status"] == "UNSETTLED_OR_PARTIAL_NOT_REPLAYED"
    assert result["physical_HTTP_requests"] == 0


def test_untracked_partial_is_not_resumed_or_overwritten(tiny):
    paths = m.file_paths(tiny["row"])
    paths["partial"].parent.mkdir(parents=True)
    paths["partial"].write_bytes(b"original interruption")
    result = m.download_file(
        tiny["plan"], tiny["row"], sender=lambda *_: pytest.fail("no Range GET")
    )
    assert result["status"] == "UNSETTLED_OR_PARTIAL_NOT_REPLAYED"
    assert paths["partial"].read_bytes() == b"original interruption"


def test_existing_complete_pinned_bytes_recovered_without_network(tiny):
    paths = m.file_paths(tiny["row"])
    paths["final"].parent.mkdir(parents=True)
    paths["final"].write_bytes(tiny["payload"])
    result = m.download_file(
        tiny["plan"], tiny["row"], sender=lambda *_: pytest.fail("already complete")
    )
    assert result["status"] == "LOCAL_HASH_VERIFIED_NOT_LOADED"
    assert (
        result["physical_HTTP_requests"] == 0 and result["local_acquisition_history_not_inferred"]
    )


def test_changed_completed_file_cannot_be_credited_or_redownloaded(tiny):
    m.download_file(tiny["plan"], tiny["row"], sender=lambda *_: Response(tiny["payload"]))
    m.file_paths(tiny["row"])["final"].write_bytes(b"x" * len(tiny["payload"]))
    with pytest.raises(ValueError, match="local_exact_manifest_digest"):
        m.download_file(tiny["plan"], tiny["row"], sender=lambda *_: pytest.fail("no repair GET"))


def test_global_attempt_and_HTTP_caps_do_not_create_extra_requests(tiny, monkeypatch):
    monkeypatch.setattr(m, "MAX_INITIAL_GETS", 0)
    with pytest.raises(ValueError, match="initial_GET_budget_exhausted"):
        m.download_file(tiny["plan"], tiny["row"], sender=lambda *_: pytest.fail("no initial GET"))
    monkeypatch.setattr(m, "MAX_INITIAL_GETS", 18)
    monkeypatch.setattr(m, "MAX_HTTP_REQUESTS", 0)
    result = m.download_file(
        tiny["plan"], tiny["row"], sender=lambda *_: pytest.fail("no extra hop")
    )
    assert result["status"] == "TRANSFER_FAILED_NOT_REFUNDED"
    assert result["physical_HTTP_requests"] == 0


def test_50GB_disk_guard(tiny, monkeypatch):
    monkeypatch.setattr(m.shutil, "disk_usage", lambda _: SimpleNamespace(free=49_999_999_999))
    with pytest.raises(ValueError, match="50GB_free"):
        m.disk_guard()
    monkeypatch.setattr(m.shutil, "disk_usage", lambda _: SimpleNamespace(free=50_000_000_000))
    assert m.disk_guard() == 50_000_000_000


def test_undeclared_file_or_python_artifact_cannot_start(tiny):
    row = deepcopy(tiny["row"])
    row["filename"] = "unregistered.json"
    with pytest.raises(ValueError, match="frozen_manifest"):
        m.download_file(tiny["plan"], row)
    row["filename"] = "download.py"
    with pytest.raises(ValueError, match="non_executable"):
        m.file_paths(row)


def test_parent_or_symlink_escape_rejected(tiny):
    with pytest.raises(ValueError, match="confined_artifact"):
        m.save(m.RAW.parent / "old-stage.json", {})
    paths = m.file_paths(tiny["row"])
    paths["final"].parent.mkdir(parents=True)
    paths["final"].symlink_to(m.RAW.parent / "other-stage.json")
    with pytest.raises(ValueError):
        m.file_paths(tiny["row"])


def test_official_transport_uses_GET_direct_TLS_no_auth(monkeypatch):
    observed = []

    class Opener:
        def open(self, request, timeout):
            observed.append((request, timeout))
            return "synthetic response"

    def build(*handlers):
        assert handlers[0].proxies == {}
        assert isinstance(handlers[1], m.urllib.request.HTTPSHandler)
        assert isinstance(handlers[2], m.NoRedirect)
        return Opener()

    monkeypatch.setattr(m.urllib.request, "build_opener", build)
    assert m.open_once("https://huggingface.co/fixed", 120) == "synthetic response"
    request, timeout = observed[0]
    assert request.get_method() == "GET" and timeout == 120
    assert request.get_header("Authorization") is None
    assert request.get_header("Range") is None
    assert request.get_header("Accept-encoding") == "identity"


def test_register_rejects_unregistered_attempt_before_parent_work(tiny, monkeypatch):
    m.save(m.RAW / "HTTP_requests" / "config.json" / "0.json", {"synthetic": True})
    monkeypatch.setattr(m.provision, "protocol", lambda _: pytest.fail("must reject before parent"))
    with pytest.raises(ValueError, match="unregistered_network_activity"):
        m.register(m.RAW.parent)
