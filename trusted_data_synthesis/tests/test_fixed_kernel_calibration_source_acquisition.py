"""Synthetic metadata and mocked HTTP only; no source acquisition or model call."""

import copy
import io
import json
import urllib.error

import prepare_direction_calibration_panel_20260926 as m
import pytest


def new_ciks(count=80, split="dev"):
    return [
        str(i).zfill(10)
        for i in range(1, 10000)
        if m.panel.source_split("cik:" + str(i).zfill(10)) == split
    ][:count]


def directory():
    return {
        str(i): {"cik_str": int(cik), "ticker": "SYN" + str(i), "title": "Synthetic " + str(i)}
        for i, cik in enumerate(new_ciks())
    }


def plan():
    return m.p.record(
        "direction_calibration_source_acquisition_plan",
        candidate_count=64,
        excluded_CIKs=[],
        excluded_historical_tickers=sorted(m.panel.HISTORICAL_TICKERS),
        selection_rule={"hash_salt": m.SALT, "old_score_inputs": 0},
        max_HTTP_requests=195,
        max_attempts_per_asset=3,
        minimum_request_interval_seconds=0.5,
        maximum_response_bytes=1024 * 1024,
        user_agent=m.USER_AGENT,
        official_directory_url=m.TICKERS,
        companyfacts_url_template="https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json",
    )


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(m.c, "RAW", tmp_path)
    monkeypatch.setattr(m.c, "emit", lambda _value: None)
    monkeypatch.setattr(m.time, "sleep", lambda _value: None)
    monkeypatch.setattr(m.time, "time", lambda: 1000.0)
    value = plan()
    monkeypatch.setattr(m, "read_plan", lambda _root: value)
    return tmp_path, value


class Response:
    def __init__(self, url, payload, status=200):
        self.url, self.payload, self.status = url, payload, status
        self.headers = {"Content-Type": "application/json", "Date": "synthetic-date"}

    def geturl(self):
        return self.url

    def read(self, maximum=-1):
        return self.payload[:maximum] if maximum >= 0 else self.payload

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False


def install_transport(monkeypatch, callback):
    """Intercept both the former transport and explicit no-redirect opener."""
    monkeypatch.setattr(m.urllib.request, "urlopen", callback)

    class Opener:
        def open(self, *args, **kwargs):
            return callback(*args, **kwargs)

    handlers = []

    def create(*values):
        handlers.extend(values)
        return Opener()

    monkeypatch.setattr(m.urllib.request, "build_opener", create)
    return handlers


def preserved_payloads(root, payload):
    return [path for path in root.rglob("*") if path.is_file() and path.read_bytes() == payload]


def test_metadata_hash_order_is_fixed_and_ignores_financial_or_old_score_fields():
    metadata, frozen = directory(), plan()
    rows, count = m.choose(metadata, frozen)
    assert len(rows) == 64 and count == 80
    expected = sorted(new_ciks(), key=lambda cik: (m.p.sha(m.SALT + "cik:" + cik), cik))[:64]
    assert [row["cik"] for row in rows] == expected
    changed = dict(reversed(list(copy.deepcopy(metadata).items())))
    for index, row in enumerate(changed.values()):
        row["old_Q"] = index % 2
        row["facts"] = {"irrelevant_value": -999999 * index}
    assert m.choose(changed, frozen) == (rows, count)


def test_excludes_old_CIK_historical_tickers_and_nondev_before_fixed64_selection():
    metadata, frozen = directory(), plan()
    frozen["excluded_CIKs"] = ["cik:" + new_ciks()[0]]
    metadata["1"]["ticker"] = "MRK"
    for i, cik in enumerate(new_ciks(2, "train")):
        metadata["train" + str(i)] = {
            "cik_str": int(cik),
            "ticker": "TRAIN" + str(i),
            "title": "Train",
        }
    for i, cik in enumerate(new_ciks(2, "confirm")):
        metadata["confirm" + str(i)] = {
            "cik_str": int(cik),
            "ticker": "CONFIRM" + str(i),
            "title": "Confirm",
        }
    rows, eligible = m.choose(metadata, frozen)
    assert eligible == 78 and len(rows) == 64
    assert not {row["cik"] for row in rows} & set(new_ciks()[:2])
    assert all(m.panel.source_split("cik:" + row["cik"]) == "dev" for row in rows)


def test_CIK_dedup_uses_lexicographic_ticker_not_directory_order():
    metadata = directory()
    first = copy.deepcopy(metadata["0"])
    metadata["extra"] = {**first, "ticker": "AAA"}
    left = m.choose(metadata, plan())
    right = m.choose(dict(reversed(list(metadata.items()))), plan())
    assert left == right
    assert left[1] == 80
    selected = {row["cik"]: row for row in left[0]}
    if new_ciks()[0] in selected:
        assert selected[new_ciks()[0]]["ticker"] == "AAA"


def test_historical_ticker_excludes_whole_CIK_including_aliases():
    metadata = directory()
    historical = copy.deepcopy(metadata["0"])
    metadata["historical_alias"] = {**historical, "ticker": "ABMD"}
    rows, eligible = m.choose(metadata, plan())
    assert eligible == 79
    assert historical["cik_str"] not in {int(row["cik"]) for row in rows}


def test_short_metadata_pool_stops_without_any_fallback():
    metadata = {str(i): row for i, row in enumerate(list(directory().values())[:63])}
    with pytest.raises(ValueError, match="insufficient_new_metadata_CIKs"):
        m.choose(metadata, plan())


def test_actual_registration_freezes64_195_three_and_no_model_scope(isolated, monkeypatch):
    root, _frozen = isolated
    source = root / m.SCRIPT
    source.parent.mkdir(parents=True)
    source.write_bytes(b"synthetic committed implementation")
    old = root / m.panel.HISTORICAL_METADATA
    m.c.write(old, {"rows": [{"source_cluster": "cik:" + str(9000000000 + i)} for i in range(100)]})
    monkeypatch.setattr(m.c, "read_protocol", lambda _root: {"id": "synthetic:parent"})
    monkeypatch.setattr(m.panel, "_source_root", lambda _root: root)
    monkeypatch.setattr(m.panel, "CODE_PATHS", ())

    def git(args, cwd, text=False):
        assert cwd == root
        if args[:2] == ["git", "rev-parse"]:
            return "synthetic-commit\n" if text else b"synthetic-commit\n"
        assert args[:2] == ["git", "show"]
        return source.read_bytes()

    monkeypatch.setattr(m.subprocess, "check_output", git)
    frozen = m.register(root)
    assert frozen["candidate_count"] == 64
    assert frozen["max_HTTP_requests"] == 195
    assert frozen["max_attempts_per_asset"] == 3
    assert frozen["minimum_request_interval_seconds"] == 0.5
    assert (
        frozen["new_model_calls"]
        == frozen["new_feedback_sampling"]
        == frozen["new_Probe_materials"]
        == 0
    )
    assert frozen["original_years"] == [2010, 2025]
    assert frozen["target_groups"] == dict.fromkeys(m.panel.GROUPS, 60)
    assert frozen["roster_before_companyfacts"] is True
    assert frozen["all_sources_sealed_before_task_enumeration"] is True
    assert len(frozen["excluded_CIKs"]) == 100
    assert len(frozen["excluded_historical_tickers"]) == 8


def test_reservation_precedes_HTTP_and_exact_snapshot_reuses_without_new_request(
    isolated, monkeypatch
):
    root, frozen = isolated
    cik = new_ciks(1)[0]
    url = frozen["companyfacts_url_template"].format(cik=cik)
    payload = json.dumps({"cik": int(cik), "facts": {}}).encode()
    calls = []

    def fetch(request, timeout):
        assert timeout == 60
        state = m.p.read_json(m.folder() / "network/state.json")
        assert state["requests"] == len(calls) + 1
        assert (m.folder() / "network" / cik / "0001.json").exists()
        assert request.headers["User-agent"] == m.USER_AGENT
        calls.append(request.full_url)
        return Response(url, payload)

    handlers = install_transport(monkeypatch, fetch)
    path, receipt = m.get_asset(frozen, cik, url)
    assert calls == [url] and receipt["bytes"] == len(payload)
    assert path.read_bytes() == payload
    assert m.get_asset(frozen, cik, url) == (path, receipt)
    assert calls == [url]
    assert m.p.read_json(m.folder() / "network/state.json")["requests"] == 1
    # One successful request cannot silently follow a redirect for another unmetered HTTP call.
    assert handlers and any(
        isinstance(item, m.urllib.request.HTTPRedirectHandler) for item in handlers
    )
    redirect = next(
        item for item in handlers if isinstance(item, m.urllib.request.HTTPRedirectHandler)
    )
    assert (
        redirect.redirect_request(None, None, 302, "redirect", {}, "https://other.example/") is None
    )
    assert preserved_payloads(root, payload)


@pytest.mark.parametrize("status", [403, 429])
def test_access_denial_stops_globally_and_retains_response_bytes(isolated, monkeypatch, status):
    root, frozen = isolated
    payload = b"synthetic denied response, retained exactly"
    calls = []

    def fetch(request, timeout):
        calls.append(request.full_url)
        raise urllib.error.HTTPError(request.full_url, status, "denied", {}, io.BytesIO(payload))

    install_transport(monkeypatch, fetch)
    with pytest.raises(urllib.error.HTTPError):
        m.get_asset(frozen, "directory", frozen["official_directory_url"])
    assert len(calls) == 1
    assert (m.folder() / "access_blocked.json").is_file()
    assert preserved_payloads(root, payload)
    with pytest.raises(ValueError, match="access_blocked"):
        m.get_asset(frozen, new_ciks(1)[0], "https://data.sec.gov/next")
    assert len(calls) == 1


@pytest.mark.parametrize("status", [403, 429])
def test_access_denial_marker_survives_body_read_failure(isolated, monkeypatch, status):
    _root, frozen = isolated
    calls = []

    class BrokenBody(io.BytesIO):
        def read(self, *_args):
            raise TimeoutError("synthetic timeout while reading denied response body")

    def fetch(request, timeout):
        calls.append(request.full_url)
        raise urllib.error.HTTPError(request.full_url, status, "denied", {}, BrokenBody(b""))

    install_transport(monkeypatch, fetch)
    with pytest.raises((urllib.error.HTTPError, TimeoutError)):
        m.get_asset(frozen, "directory", frozen["official_directory_url"])
    assert (m.folder() / "access_blocked.json").is_file()
    with pytest.raises(ValueError, match="access_blocked"):
        m.get_asset(frozen, new_ciks(1)[0], "https://data.sec.gov/next")
    assert len(calls) == 1


def test_five_xx_attempts_are_charged_and_finite_across_resume(isolated, monkeypatch):
    root, frozen = isolated
    calls = []
    payload = b"synthetic transient server response"

    def fetch(request, timeout):
        calls.append(request.full_url)
        raise urllib.error.HTTPError(request.full_url, 503, "temporary", {}, io.BytesIO(payload))

    install_transport(monkeypatch, fetch)
    for _ in range(2):
        with pytest.raises(RuntimeError, match="asset_attempt_cap"):
            m.get_asset(frozen, "directory", frozen["official_directory_url"])
    assert len(calls) == 3
    assert m.p.read_json(m.folder() / "network/state.json")["requests"] == 3
    assert len(list((m.folder() / "network/directory").glob("*.json"))) == 3
    assert len(preserved_payloads(root, payload)) >= 3


def test_global195_cap_stops_before_unbudgeted_request(isolated, monkeypatch):
    _root, frozen = isolated
    m.c.write(m.folder() / "network/state.json", {"requests": 195, "last_started": 0})

    def forbidden(*_args, **_kwargs):
        raise AssertionError("unbudgeted HTTP")

    install_transport(monkeypatch, forbidden)
    with pytest.raises(ValueError, match="HTTP_budget_exhausted"):
        m.get_asset(frozen, "directory", frozen["official_directory_url"])
    assert m.p.read_json(m.folder() / "network/state.json")["requests"] == 195


def test_redirect_response_stops_after_one_charged_attempt(isolated, monkeypatch):
    root, frozen = isolated
    payload = b"synthetic redirect response"
    calls = []

    def fetch(request, timeout):
        calls.append(request.full_url)
        raise urllib.error.HTTPError(
            request.full_url,
            302,
            "redirect",
            {"Location": "https://other.example/"},
            io.BytesIO(payload),
        )

    install_transport(monkeypatch, fetch)
    with pytest.raises(urllib.error.HTTPError):
        m.get_asset(frozen, "directory", frozen["official_directory_url"])
    assert len(calls) == 1
    assert m.p.read_json(m.folder() / "network/state.json")["requests"] == 1
    assert preserved_payloads(root, payload)


def test_wrong_plan_snapshot_receipt_rejected_without_HTTP(isolated, monkeypatch):
    _root, frozen = isolated
    payload = b"{}"
    key = "directory"
    path = m.folder() / "snapshots/directory.json"
    m.c.b.durable.atomic_bytes(path, payload, immutable=True)
    m.c.write(
        m.folder() / "receipts/directory.json",
        m.p.record(
            "calibration_source_HTTP_receipt",
            plan_id="wrong:plan",
            url=m.TICKERS,
            sha256=m.p.sha(payload),
            bytes=len(payload),
        ),
    )

    def forbidden(*_args, **_kwargs):
        raise AssertionError("invalid cached receipt must not trigger HTTP")

    install_transport(monkeypatch, forbidden)
    with pytest.raises(ValueError, match="reuse_exact_snapshot"):
        m.get_asset(frozen, key, m.TICKERS)


def test_nonjson_success_body_is_retained_and_not_retried(isolated, monkeypatch):
    root, frozen = isolated
    payload = b"synthetic response that is not JSON"
    calls = []

    def fetch(request, timeout):
        calls.append(request.full_url)
        return Response(request.full_url, payload)

    install_transport(monkeypatch, fetch)
    with pytest.raises(json.JSONDecodeError):
        m.get_asset(frozen, "directory", frozen["official_directory_url"])
    assert len(calls) == 1
    assert preserved_payloads(root, payload)
    assert not (m.folder() / "receipts/directory.json").exists()
    with pytest.raises((ValueError, RuntimeError)):
        m.get_asset(frozen, "directory", frozen["official_directory_url"])
    assert len(calls) == 1


def test_acquire_seals_roster_before_any_companyfacts_and_never_replaces_failure(
    isolated, monkeypatch
):
    root, frozen = isolated
    metadata = directory()
    rows, _count = m.choose(metadata, frozen)
    failed = rows[2]["cik"]
    seen = []
    directory_path = root / "synthetic_directory.json"
    directory_path.write_text(json.dumps(metadata))

    def get(plan, key, url):
        seen.append(key)
        if key == "directory":
            return directory_path, {"sha256": m.p.sha(directory_path)}
        roster = m.p.checked(
            m.p.read_json(m.folder() / "roster.json"), "calibration_new_CIK_roster"
        )
        assert roster["sources"] == rows
        assert roster["no_companyfacts_values_read_before_roster"] is True
        if key == failed:
            raise RuntimeError("synthetic frozen-source failure")
        return root / (key + ".json"), {"sha256": "1" * 64, "bytes": 1, "id": "fake:" + key}

    monkeypatch.setattr(m, "get_asset", get)
    with pytest.raises(RuntimeError, match="frozen-source failure"):
        m.acquire(root)
    assert seen == ["directory", *[row["cik"] for row in rows[:3]]]
    assert not (m.folder() / "source_registration.json").exists()


def test_run_reuses_existing_completion_without_rebuilding_or_model_calls(isolated, monkeypatch):
    root, _frozen = isolated
    source_registration = {"id": "synthetic_registration:complete"}
    admission = {"id": "synthetic_admission:complete", "passed": True}
    monkeypatch.setattr(m, "acquire", lambda _root: source_registration)
    m.c.write(root / "calibration_panel/admission.json", admission)

    def forbidden(*_args, **_kwargs):
        raise AssertionError("unexpected panel/model execution")

    monkeypatch.setattr(m.panel, "build", forbidden)
    assert m.run(root) == 0
    completion_path = m.folder() / "completion.json"
    before = completion_path.read_bytes()
    assert m.run(root) == 0
    assert completion_path.read_bytes() == before
    assert m.p.read_json(completion_path)["new_model_calls"] == 0
