"""Synthetic source-build guards; never access network, packages, models or GPUs."""

import hashlib
import io
import os
import tarfile
import urllib.error

import build_cross_market_vision_environment_20260927 as m
import pytest


@pytest.fixture
def raw(tmp_path, monkeypatch):
    monkeypatch.setattr(m.base, "RAW", tmp_path)
    monkeypatch.setattr(m, "RAW", tmp_path / "build")
    m.RAW.mkdir()
    return m.RAW


def archive(path, extras=()):
    prefix = "vision-" + m.COMMIT
    members = [
        (prefix + "/setup.py", b"pass\n", tarfile.REGTYPE),
        (prefix + "/version.txt", b"0.22.1\n", tarfile.REGTYPE),
        *extras,
    ]
    with tarfile.open(path, "w:gz") as output:
        for name, data, kind in members:
            item = tarfile.TarInfo(name)
            item.type = kind
            item.size = len(data) if kind == tarfile.REGTYPE else 0
            item.linkname = "elsewhere" if kind in (tarfile.SYMTYPE, tarfile.LNKTYPE) else ""
            output.addfile(item, io.BytesIO(data) if item.size else None)
    return path


def test_exact_artifacts_and_no_denied_wheel_or_model_request():
    assert len(m.ARTIFACTS) == 3 and {x["key"] for x in m.ARTIFACTS} == {
        "source",
        "pillow",
        "setuptools",
    }
    assert m.COMMIT in m.ARTIFACTS[0]["url"]
    assert m.ARTIFACTS[0]["maximum_bytes"] == 256 * 2**20
    assert all("download-r2" not in x["url"] and "huggingface" not in x["url"] for x in m.ARTIFACTS)
    assert sum(x["bytes"] for x in m.ARTIFACTS[1:]) == 8142316
    assert all(len(x["sha256"]) == 64 for x in m.ARTIFACTS[1:])


def test_safe_regular_extract(raw):
    path = archive(raw / "source.tar.gz")
    root, counts = m.safe_extract(path, raw / "out")
    assert root.name == "vision-" + m.COMMIT
    assert counts["entries"] == 2 and counts["extracted_file_bytes"] == 12
    with pytest.raises(ValueError, match="new_extract_directory"):
        m.safe_extract(path, raw / "out")


@pytest.mark.parametrize(
    "suffix,kind",
    [
        ("../escape", tarfile.REGTYPE),
        ("link", tarfile.SYMTYPE),
        ("hardlink", tarfile.LNKTYPE),
        ("fifo", tarfile.FIFOTYPE),
        ("device", tarfile.CHRTYPE),
        ("back\\slash", tarfile.REGTYPE),
    ],
)
def test_unsafe_members_rejected(raw, suffix, kind):
    path = archive(raw / "bad.tar.gz", [("vision-" + m.COMMIT + "/" + suffix, b"x", kind)])
    with pytest.raises(
        ValueError, match="vision_build_(safe_archive_path|no_archive_links_devices)"
    ):
        m.safe_extract(path, raw / "out")
    assert not (raw / "escape").exists()


@pytest.mark.parametrize("limit,value", [("MAX_ENTRIES", 1), ("MAX_EXTRACTED_BYTES", 2)])
def test_expansion_and_entry_caps(raw, monkeypatch, limit, value):
    path = archive(raw / "source.tar.gz")
    monkeypatch.setattr(m, limit, value)
    with pytest.raises(ValueError, match="vision_build_archive_.*cap"):
        m.safe_extract(path, raw / "out")


def fake_item(body=b"official fixture"):
    return dict(
        key="fixture",
        filename="fixture.whl",
        url="https://files.pythonhosted.org/a.whl",
        hosts=["files.pythonhosted.org"],
        bytes=len(body),
        maximum_bytes=len(body),
        sha256=hashlib.sha256(body).hexdigest(),
    )


def test_download_receipt_records_actual_bytes_before_other_work(raw, monkeypatch):
    body = b"official fixture"
    response = io.BytesIO(body)
    response.status = 200
    calls = []

    class Opener:
        def open(self, request, timeout):
            calls.append(request.full_url)
            return response

    monkeypatch.setattr(m.urllib.request, "build_opener", lambda *args: Opener())
    receipt = m.acquire({"id": "synthetic"}, fake_item(body))
    assert receipt["actual_file"]["sha256"] == hashlib.sha256(body).hexdigest()
    assert receipt["actual_file"]["bytes"] == len(body) and receipt["expected_digest_verified"]
    assert (raw / "receipts/fixture.json").exists() and len(calls) == 1
    assert len(list((raw / "requests").glob("*.json"))) == 1


@pytest.mark.parametrize("status", [403, 429])
def test_denial_never_redirected_or_retried(raw, monkeypatch, status):
    calls = []

    class Opener:
        def open(self, request, timeout):
            calls.append(request.full_url)
            raise urllib.error.HTTPError(
                request.full_url,
                status,
                "denied",
                {"Location": "https://files.pythonhosted.org/other"},
                None,
            )

    monkeypatch.setattr(m.urllib.request, "build_opener", lambda *args: Opener())
    with pytest.raises(urllib.error.HTTPError):
        m.acquire({"id": "synthetic"}, fake_item())
    assert calls == [fake_item()["url"]]
    assert not (raw / "receipts/fixture.json").exists()


def test_redirect_scope_and_budget(raw, monkeypatch):
    calls = []

    class Opener:
        def open(self, request, timeout):
            calls.append(request.full_url)
            raise urllib.error.HTTPError(
                request.full_url,
                302,
                "redirect",
                {"Location": "https://files.pythonhosted.org/next"},
                None,
            )

    monkeypatch.setattr(m.urllib.request, "build_opener", lambda *args: Opener())
    with pytest.raises(urllib.error.HTTPError):
        m.acquire({"id": "synthetic"}, fake_item())
    assert len(calls) == 3
    with pytest.raises(ValueError, match="official_URL"):
        m.allowed_url("http://files.pythonhosted.org/plain", fake_item())
    with pytest.raises(ValueError, match="official_URL"):
        m.allowed_url("https://files.pythonhosted.org.attacker.invalid/a", fake_item())


def test_reserved_build_not_refunded(raw, monkeypatch):
    m.base.write(raw / "attempt.json", {"reserved": True})
    monkeypatch.setattr(m, "protocol", lambda root: {"id": "synthetic"})
    monkeypatch.setattr(m, "acquire", lambda *args: pytest.fail("no second network attempt"))
    with pytest.raises(ValueError, match="reserved_no_retry"):
        m.run(raw)


def test_source_receipt_precedes_extract_and_failure_is_final(raw, monkeypatch):
    plan = dict(id="synthetic", runtime={})
    monkeypatch.setattr(m, "protocol", lambda root: plan)
    monkeypatch.setattr(m, "metadata", lambda python: {})
    monkeypatch.setattr(m, "MIN_FREE_BYTES", 0)

    def acquire(plan, item):
        receipt = dict(actual_file={"path": str(raw / item["filename"]), "sha256": "a" * 64})
        m.save(raw / "receipts" / (item["key"] + ".json"), receipt)
        return receipt

    def extract(*args):
        assert (raw / "receipts/source.json").is_file()
        raise ValueError("cross_market.vision_build_synthetic_stop")

    monkeypatch.setattr(m, "acquire", acquire)
    monkeypatch.setattr(m, "safe_extract", extract)
    result = m.run(raw)
    assert result["status"] == "SOURCE_BUILD_FAILED_NO_AUTOMATIC_RETRY"
    assert result["model_loads"] == 0 and result["parent_runtime_unchanged"]
    monkeypatch.setattr(m, "acquire", lambda *args: pytest.fail("no repeat after failure"))
    assert m.run(raw) == result


def test_child_cpu_flags_and_local_install_contract(raw, monkeypatch):
    monkeypatch.setenv("CUDA_VISIBLE_DEVICES", "parent-visible")
    monkeypatch.setenv("PIP_INDEX_URL", "unused-test-setting")
    env = m.child_environment(raw / "source/vision")
    assert os.environ["CUDA_VISIBLE_DEVICES"] == "parent-visible"
    assert env["CUDA_VISIBLE_DEVICES"] == "" and env["FORCE_CUDA"] == "0"
    assert env["BUILD_VERSION"] == "0.22.1+localcpu" and env["MAX_JOBS"] == "8"
    assert "PIP_INDEX_URL" not in env and env["PIP_NO_INDEX"] == "1"
    assert env["GIT_CEILING_DIRECTORIES"] == str(raw / "source")
    calls = []
    monkeypatch.setattr(m, "command", lambda args, **kwargs: calls.append((args, kwargs)))
    m.pip_install(raw / "venv/bin/python", [raw / "fixture.whl"], env, label="test")
    args = calls[0][0]
    assert all(
        flag in args
        for flag in ["-I", "-B", "--no-index", "--no-deps", "--ignore-installed", "--no-compile"]
    )
    assert "Image.open" not in m.SMOKE and "from_pretrained" not in m.SMOKE
    assert "device='cpu'" in m.SMOKE
