"""Compliance source revision: synthetic identity and offline transport mocks only."""

import io
import json
import socket
import ssl
import time
import urllib.error
import urllib.request
from datetime import datetime

import prepare_calibration_sources_compliance_20260926 as m
import pytest

DIRECTORY = "https://www.sec.gov/files/company_tickers.json"
PROXY = {"kind": "proxy", "url": "http://127.0.0.1:7897"}
CONTACT = "researcher@example.test"
DENIED_AT = "2026-01-01T00:00:00+00:00"
DENIED_SECONDS = datetime.fromisoformat(DENIED_AT).timestamp()


@pytest.fixture(autouse=True)
def no_real_network(monkeypatch):
    def forbidden(*_args, **_kwargs):
        raise AssertionError("compliance unit test attempted real network I/O")

    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(urllib.request.OpenerDirector, "open", forbidden)
    monkeypatch.setattr(m.previous, "_tls_probe", forbidden)


@pytest.fixture
def registration(tmp_path, monkeypatch):
    monkeypatch.setattr(m.c, "RAW", tmp_path)
    monkeypatch.setattr(m.c, "emit", lambda _value: None)
    monkeypatch.setattr(m, "CONTACT", CONTACT)
    monkeypatch.setattr(time, "time", lambda: DENIED_SECONDS + 1000)
    monkeypatch.setattr(time, "sleep", lambda _seconds: None)
    base = m.p.record(
        "direction_calibration_source_acquisition_plan",
        sources={},
        code_commit="synthetic-base",
        candidate_count=64,
        excluded_CIKs=["cik:0000000001"],
        excluded_historical_tickers=["SYNOLD"],
        selection_rule={"hash_salt": "synthetic-fixed-salt:", "old_score_inputs": 0},
        official_directory_url=DIRECTORY,
        companyfacts_url_template="https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json",
        max_HTTP_requests=195,
        max_attempts_per_asset=3,
        minimum_request_interval_seconds=0.5,
        maximum_response_bytes=1024 * 1024,
        user_agent="Synthetic previous declaration",
        new_model_calls=0,
        new_feedback_sampling=0,
        new_Probe_materials=0,
        source_replacement=False,
        target_groups={"group_one": 60, "group_two": 60, "group_three": 60},
        at="synthetic-base-time",
    )
    m.c.write(m.original.folder() / "acquisition_plan.json", base)
    m.c.write(m.original.folder() / "network/state.json", {"requests": 3})
    m.c.write(m.original.folder() / "failures/directory/0001.json", {"error": "TLS EOF"})
    parent = m.p.record(
        "direction_calibration_source_acquisition_plan",
        parent_acquisition_plan_id=base["id"],
        parent_evidence=m.previous.parent_evidence(),
        sources={},
    )
    m.c.write(m.previous.folder() / "acquisition_plan.json", parent)
    m.c.write(m.previous.folder() / "network/state.json", {"requests": 1})
    m.c.write(
        m.previous.folder() / "access_blocked.json",
        {"status": 403, "url": DIRECTORY, "at": DENIED_AT},
    )
    m.c.write(
        m.previous.folder() / "route.json",
        m.p.record("calibration_source_transport_route", plan_id=parent["id"], route=PROXY),
    )
    monkeypatch.setattr(m.original, "read_plan", lambda _root: base)
    source = tmp_path / m.SCRIPT
    source.parent.mkdir(parents=True)
    source.write_bytes(b"synthetic committed compliance adapter")

    def git(args, cwd, text=False):
        assert cwd == tmp_path
        if args[:3] == ["git", "rev-parse", "HEAD"]:
            return "synthetic-compliance-commit\n" if text else b"synthetic-compliance-commit\n"
        assert args[:2] == ["git", "show"]
        return source.read_bytes()

    monkeypatch.setattr(m.subprocess, "check_output", git)
    return tmp_path, base, parent, source


@pytest.fixture
def registered(registration):
    root, _base, _parent, _source = registration
    return root, m.register(root)


class Response:
    def __init__(self, url, payload):
        self.url, self.payload = url, payload
        self.headers, self.status = {"Content-Type": "application/json"}, 200

    def geturl(self):
        return self.url

    def read(self, maximum=-1):
        return self.payload[:maximum] if maximum >= 0 else self.payload

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False


def transport(monkeypatch, callback):
    class Opener:
        def open(self, *args, **kwargs):
            return callback(*args, **kwargs)

    monkeypatch.setattr(urllib.request, "build_opener", lambda *_args, **_kwargs: Opener())


def test_registration_preserves_both_old_trees_and_scientific_contract(registration):
    root, base, parent, _source = registration
    before = m.previous_evidence()
    plan = m.register(root)
    assert plan["parent_acquisition_plan_id"] == parent["id"]
    assert plan["original_acquisition_plan_id"] == base["id"]
    assert plan["previous_evidence"] == before == m.previous_evidence()
    assert any(name.startswith("panel_sources/") for name in before)
    assert any(name.startswith("panel_sources_retry_revision_01/") for name in before)
    assert m.folder().name == "panel_sources_compliance_revision_02"
    assert plan["contact_email"] == CONTACT
    assert CONTACT in plan["user_agent"]
    assert plan["fixed_route"] == PROXY
    assert plan["directory_attempt_cap"] == 1
    assert plan["max_attempts_per_asset"] == 3
    assert plan["max_HTTP_requests"] == 193
    assert plan["previous_HTTP_attempts"] == 4
    assert plan["cumulative_HTTP_attempt_cap"] == 197
    assert plan["minimum_request_interval_seconds"] == 2
    assert plan["minimum_denial_cooldown_seconds"] == 600
    assert plan["additional_TLS_diagnostics"] == plan["direct_connections"] == 0
    assert plan["retry_after_another_403_or_429"] is False
    for key in ("selection_rule", "excluded_CIKs", "target_groups", "candidate_count"):
        assert plan[key] == base[key]
    assert plan["scientific_rules_changed"] is False
    assert m.read_plan(root) == plan
    assert m.register(root) == plan
    assert not (m.folder() / "network").exists()


@pytest.mark.parametrize("elapsed,allowed", [(599.99, False), (600, True), (601, True)])
def test_600_second_cooldown_boundary(registration, monkeypatch, elapsed, allowed):
    root, *_rest = registration
    monkeypatch.setattr(time, "time", lambda: DENIED_SECONDS + elapsed)
    if allowed:
        assert m.register(root)["minimum_denial_cooldown_seconds"] == 600
    else:
        with pytest.raises(ValueError, match="at_least600_seconds"):
            m.register(root)
        assert not (m.folder() / "acquisition_plan.json").exists()


@pytest.mark.parametrize(
    "contact", ["missing-at", "x@example.test\nheader", "x@example.test\rheader"]
)
def test_invalid_or_header_injected_contact_rejected(registration, monkeypatch, contact):
    root, *_rest = registration
    monkeypatch.setattr(m, "CONTACT", contact)
    with pytest.raises(ValueError, match="truthful_confirmed_contact"):
        m.register(root)


@pytest.mark.parametrize("tree", ["panel_sources", "panel_sources_retry_revision_01"])
def test_old_evidence_mutation_stops_before_network(registered, tree):
    root, _plan = registered
    m.c.write(root / tree / "unregistered_change.json", {"changed": True})
    with pytest.raises(ValueError, match="exact_prior_four|frozen_revision_and_previous"):
        m.read_plan(root)
    assert not (m.folder() / "network").exists()


def test_adapter_source_change_rejected(registration):
    root, _base, _parent, source = registration
    m.register(root)
    source.write_bytes(b"synthetic unregistered edit")
    with pytest.raises(ValueError, match="frozen_source"):
        m.read_plan(root)


def test_pinned_proxy_ignores_NO_PROXY_and_keeps_TLS_verification(registered, monkeypatch):
    _root, plan = registered
    monkeypatch.setattr(urllib.request, "proxy_bypass", lambda _host: True)
    opener = m._fixed_opener(plan, m.original.NoRedirect())
    proxy = next(h for h in opener.handlers if isinstance(h, m.previous.FixedProxy))
    tls = next(h for h in opener.handlers if isinstance(h, urllib.request.HTTPSHandler))
    request = urllib.request.Request(DIRECTORY)
    proxy.proxy_open(request, PROXY["url"], "https")
    assert request.host == "127.0.0.1:7897"
    assert request._tunnel_host == "www.sec.gov"
    assert request.full_url == DIRECTORY
    assert tls._context.check_hostname is True
    assert tls._context.verify_mode == ssl.CERT_REQUIRED
    with pytest.raises(ValueError, match="original_local_proxy_only"):
        m._fixed_opener({**plan, "fixed_route": {"kind": "direct"}})


def test_directory_contact_reserves_first_and_reuses_exact_cache(registered, monkeypatch):
    _root, plan = registered
    before = m.previous_evidence()
    payload = b'{"0":{"cik_str":123,"ticker":"SYN","title":"Synthetic"}}'
    seen = []

    def fetch(request, timeout):
        assert timeout == 60
        assert request.full_url == DIRECTORY
        assert request.headers["User-agent"] == plan["user_agent"]
        assert CONTACT in request.headers["User-agent"]
        assert m.p.read_json(m.folder() / "network/state.json")["requests"] == 1
        assert (m.folder() / "network/directory/0001.json").exists()
        seen.append(request.full_url)
        return Response(request.full_url, payload)

    transport(monkeypatch, fetch)
    api = m._collector(plan)
    path, receipt = api.get_asset(plan, "directory", DIRECTORY)
    assert path.read_bytes() == payload
    assert receipt["plan_id"] == plan["id"]
    assert api.get_asset(plan, "directory", DIRECTORY) == (path, receipt)
    assert seen == [DIRECTORY]
    assert m.previous_evidence() == before


@pytest.mark.parametrize("status", [403, 429])
def test_new_denial_permanently_stops_without_deleting_old_denial(registered, monkeypatch, status):
    root, plan = registered
    before = m.previous_evidence()
    calls = []
    payload = b"synthetic SEC denial"

    def fetch(request, timeout):
        calls.append(request.full_url)
        raise urllib.error.HTTPError(request.full_url, status, "denied", {}, io.BytesIO(payload))

    transport(monkeypatch, fetch)
    api = m._collector(plan)
    with pytest.raises(urllib.error.HTTPError):
        api.get_asset(plan, "directory", DIRECTORY)
    with pytest.raises(ValueError, match="permanent_stop"):
        m._collector(plan).get_asset(
            plan, "0000000123", "https://data.sec.gov/api/xbrl/companyfacts/CIK0000000123.json"
        )
    with pytest.raises(ValueError, match="permanent_stop"):
        m.read_plan(root)
    assert calls == [DIRECTORY]
    assert (m.folder() / "raw_attempts/directory/0001.bin").read_bytes() == payload
    assert m.previous_evidence() == before


def test_denial_marker_survives_body_read_failure(registered, monkeypatch):
    _root, plan = registered

    class BrokenBody(io.BytesIO):
        def read(self, *_args):
            raise TimeoutError("synthetic denied body timeout")

    def fetch(request, timeout):
        raise urllib.error.HTTPError(request.full_url, 403, "denied", {}, BrokenBody())

    transport(monkeypatch, fetch)
    with pytest.raises(TimeoutError):
        m._collector(plan).get_asset(plan, "directory", DIRECTORY)
    with pytest.raises(ValueError, match="permanent_stop"):
        m._unblocked()


@pytest.mark.parametrize("failure", ["TLS", "HTTP5xx"])
def test_directory_never_retries_even_retryable_error(registered, monkeypatch, failure):
    _root, plan = registered
    calls = []

    def fetch(request, timeout):
        calls.append(request.full_url)
        if failure == "TLS":
            raise urllib.error.URLError(ssl.SSLEOFError(8, "synthetic EOF"))
        raise urllib.error.HTTPError(
            request.full_url, 503, "synthetic unavailable", {}, io.BytesIO(b"503")
        )

    transport(monkeypatch, fetch)
    for _ in range(2):
        with pytest.raises(RuntimeError, match="asset_attempt_cap:directory"):
            m._collector(plan).get_asset(plan, "directory", DIRECTORY)
    assert calls == [DIRECTORY]
    assert m.p.read_json(m.folder() / "network/state.json")["requests"] == 1


def test_unresolved_directory_intent_is_not_replayed(registered):
    _root, plan = registered
    m.c.write(m.folder() / "network/state.json", {"requests": 1, "last_started": 0})
    m.c.write(m.folder() / "network/directory/0001.json", {"attempt": 1, "plan_id": plan["id"]})
    with pytest.raises(RuntimeError, match="asset_attempt_cap:directory"):
        m._collector(plan).get_asset(plan, "directory", DIRECTORY)


def test_companyfacts_three_attempt_cap_remains_persistent(registered, monkeypatch):
    _root, plan = registered
    calls = []
    url = "https://data.sec.gov/api/xbrl/companyfacts/CIK0000000123.json"

    def fetch(request, timeout):
        calls.append(request.full_url)
        raise urllib.error.URLError(TimeoutError("synthetic network timeout"))

    transport(monkeypatch, fetch)
    for _ in range(2):
        with pytest.raises(RuntimeError, match="asset_attempt_cap:0000000123"):
            m._collector(plan).get_asset(plan, "0000000123", url)
    assert calls == [url] * 3
    assert m.p.read_json(m.folder() / "network/state.json")["requests"] == 3


def test_global_193_cap_and_two_second_interval(registered, monkeypatch):
    _root, plan = registered
    path = m.folder() / "network/state.json"
    m.c.write(path, {"requests": 193, "last_started": 0})
    with pytest.raises(ValueError, match="HTTP_budget_exhausted"):
        m._collector(plan).get_asset(plan, "directory", DIRECTORY)
    m.c.write(path, {"requests": 0, "last_started": time.time()}, immutable=False)
    sleeps = []
    monkeypatch.setattr(time, "sleep", sleeps.append)
    transport(monkeypatch, lambda request, timeout: Response(request.full_url, b'{"0":{}}'))
    m._collector(plan).get_asset(plan, "directory", DIRECTORY)
    assert sleeps == [2]


def test_non_JSON_directory_retains_failure_and_never_retries(registered, monkeypatch):
    _root, plan = registered
    transport(
        monkeypatch, lambda request, timeout: Response(request.full_url, b"synthetic not JSON")
    )
    with pytest.raises(json.JSONDecodeError):
        m._collector(plan).get_asset(plan, "directory", DIRECTORY)
    with pytest.raises(ValueError, match="asset_terminal_failure"):
        m._collector(plan).get_asset(plan, "directory", DIRECTORY)
    assert (m.folder() / "raw_attempts/directory/0001.bin").read_bytes() == b"synthetic not JSON"


def test_cooldown_checked_again_before_each_transport(registered, monkeypatch):
    _root, plan = registered
    monkeypatch.setattr(time, "time", lambda: DENIED_SECONDS + 599)
    with pytest.raises(ValueError, match="at_least600_seconds"):
        m._collector(plan).get_asset(plan, "directory", DIRECTORY)
    assert not (m.folder() / "network").exists()
