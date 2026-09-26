"""Bounded successor source retry: synthetic metadata and mocked transport only."""

import io
import json
import socket
import ssl
import time
import urllib.error
import urllib.request

import pytest
import retry_direction_calibration_sources_20260926 as m

DIRECT = {"kind": "direct"}
PROXY = {"kind": "proxy", "url": "http://127.0.0.1:7897"}
DIRECTORY = "https://www.sec.gov/files/company_tickers.json"
READ_PLAN = m.read_plan


@pytest.fixture(autouse=True)
def no_real_network(monkeypatch):
    def forbidden(*_args, **_kwargs):
        raise AssertionError("unit test attempted real network I/O")

    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(urllib.request.OpenerDirector, "open", forbidden)


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(m.c, "RAW", tmp_path)
    monkeypatch.setattr(m.c, "emit", lambda _value: None)
    frozen = m.p.record(
        "direction_calibration_source_retry_revision",
        candidate_count=64,
        excluded_CIKs=[],
        excluded_historical_tickers=["AAPL", "ABMD", "AMT", "BKR", "ECL", "KHC", "MRK", "UNP"],
        selection_rule={
            "hash_salt": "direction_calibration_new_sources_20260926.v1:",
            "old_score_inputs": 0,
        },
        max_HTTP_requests=195,
        max_attempts_per_asset=3,
        minimum_request_interval_seconds=0,
        maximum_response_bytes=1024 * 1024,
        user_agent="Data-Synthesis academic research https://github.com/haoyueliuzhao/Data-Synthesis",
        official_directory_url=DIRECTORY,
        companyfacts_url_template="https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json",
        max_TLS_diagnostics=2,
        diagnostic_routes=[PROXY, DIRECT],
        diagnostic_host="www.sec.gov",
        diagnostic_timeout_seconds=20,
        maximum_TLS_diagnostic_connections=2,
    )
    monkeypatch.setattr(m, "read_plan", lambda _root: frozen)
    return tmp_path, frozen


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

    monkeypatch.setattr(m, "_fixed_opener", lambda *_args, **_kwargs: Opener())


def test_retry_directory_is_a_sibling_and_parent_manifest_covers_every_file(isolated):
    root, _plan = isolated
    old = root / "panel_sources"
    m.c.write(old / "network/state.json", {"requests": 3})
    m.c.write(old / "failures/directory/0003.json", {"error": "synthetic TLS EOF"})
    before = m.parent_evidence()
    assert m.folder() != old and not m.folder().is_relative_to(old)
    assert set(before) == {"network/state.json", "failures/directory/0003.json"}
    m.c.write(m.folder() / "synthetic_new_record.json", {"new": True})
    assert m.parent_evidence() == before


def test_collector_reserves_before_transport_and_writes_only_new_tree(isolated, monkeypatch):
    root, plan = isolated
    old = root / "panel_sources"
    m.c.write(old / "network/state.json", {"requests": 3})
    before = m.parent_evidence()
    payload = b'{"0":{"cik_str":123,"ticker":"SYN","title":"Synthetic"}}'
    seen = []

    def fetch(request, timeout):
        assert timeout == 60
        state = m.p.read_json(m.folder() / "network/state.json")
        assert state["requests"] == 1
        assert (m.folder() / "network/directory/0001.json").is_file()
        assert request.full_url == DIRECTORY
        assert request.headers["User-agent"] == plan["user_agent"]
        seen.append(request.full_url)
        return Response(request.full_url, payload)

    transport(monkeypatch, fetch)
    api = m._collector(plan, DIRECT)
    destination, receipt = api.get_asset(plan, "directory", DIRECTORY)
    assert destination == m.folder() / "snapshots/directory.json"
    assert destination.read_bytes() == payload
    assert receipt["plan_id"] == plan["id"]
    assert receipt["raw_response"]["path"].startswith(str(m.folder()))
    assert api.get_asset(plan, "directory", DIRECTORY) == (destination, receipt)
    assert seen == [DIRECTORY]
    assert m.parent_evidence() == before


@pytest.mark.parametrize("status", [403, 429])
def test_access_denial_blocks_every_next_request_and_keeps_raw_body(isolated, monkeypatch, status):
    _root, plan = isolated
    calls = []
    payload = b"synthetic denied body"

    def fetch(request, timeout):
        calls.append(request.full_url)
        raise urllib.error.HTTPError(request.full_url, status, "denied", {}, io.BytesIO(payload))

    transport(monkeypatch, fetch)
    api = m._collector(plan, DIRECT)
    with pytest.raises(urllib.error.HTTPError):
        api.get_asset(plan, "directory", DIRECTORY)
    assert (m.folder() / "access_blocked.json").is_file()
    assert (m.folder() / "raw_attempts/directory/0001.bin").read_bytes() == payload
    with pytest.raises((ValueError, RuntimeError)):
        api.get_asset(
            plan, "0000000123", "https://data.sec.gov/api/xbrl/companyfacts/CIK0000000123.json"
        )
    assert calls == [DIRECTORY]


def test_parent_access_denial_is_inherited_even_after_adapter_creation(isolated, monkeypatch):
    root, plan = isolated
    api = m._collector(plan, DIRECT)
    m.c.write(root / "panel_sources/access_blocked.json", {"status": 403})

    def forbidden(*_args, **_kwargs):
        raise AssertionError("parent access block ignored")

    transport(monkeypatch, forbidden)
    with pytest.raises((ValueError, RuntimeError)):
        api.get_asset(plan, "directory", DIRECTORY)
    assert not (m.folder() / "network/state.json").exists()


@pytest.mark.parametrize("status", [403, 429])
def test_denial_marker_survives_failure_to_read_error_body(isolated, monkeypatch, status):
    _root, plan = isolated

    class BrokenBody(io.BytesIO):
        def read(self, *_args):
            raise TimeoutError("synthetic denied-body timeout")

    def fetch(request, timeout):
        raise urllib.error.HTTPError(request.full_url, status, "denied", {}, BrokenBody())

    transport(monkeypatch, fetch)
    api = m._collector(plan, DIRECT)
    with pytest.raises((urllib.error.HTTPError, TimeoutError)):
        api.get_asset(plan, "directory", DIRECTORY)
    assert (m.folder() / "access_blocked.json").is_file()


def test_retry_ledger_stays_finite_across_new_adapter_instances(isolated, monkeypatch):
    _root, plan = isolated
    calls = []
    # The original collector's timeout backoff is not part of test wall time.
    monkeypatch.setattr(time, "sleep", lambda _seconds: None)

    def fetch(request, timeout):
        calls.append(request.full_url)
        raise urllib.error.URLError(ssl.SSLEOFError(8, "synthetic TLS EOF"))

    transport(monkeypatch, fetch)
    for _ in range(2):
        api = m._collector(plan, DIRECT)
        with pytest.raises(RuntimeError, match="asset_attempt_cap"):
            api.get_asset(plan, "directory", DIRECTORY)
    assert len(calls) == 3
    assert m.p.read_json(m.folder() / "network/state.json")["requests"] == 3
    assert len(list((m.folder() / "network/directory").glob("*.json"))) == 3


def test_global_request_cap_rejects_without_network(isolated, monkeypatch):
    _root, plan = isolated
    m.c.write(m.folder() / "network/state.json", {"requests": 195, "last_started": 0})

    def forbidden(*_args, **_kwargs):
        raise AssertionError("request budget ignored")

    transport(monkeypatch, forbidden)
    with pytest.raises(ValueError, match="HTTP_budget_exhausted"):
        m._collector(plan, DIRECT).get_asset(plan, "directory", DIRECTORY)


def test_semantic_invalid_response_is_retained_and_not_retried(isolated, monkeypatch):
    _root, plan = isolated
    calls = []
    payload = b"not JSON"

    def fetch(request, timeout):
        calls.append(request.full_url)
        return Response(request.full_url, payload)

    transport(monkeypatch, fetch)
    api = m._collector(plan, DIRECT)
    with pytest.raises(json.JSONDecodeError):
        api.get_asset(plan, "directory", DIRECTORY)
    with pytest.raises((ValueError, RuntimeError)):
        api.get_asset(plan, "directory", DIRECTORY)
    assert calls == [DIRECTORY]
    assert (m.folder() / "raw_attempts/directory/0001.bin").read_bytes() == payload


def test_tls_success_pins_proxy_without_SEC_HTTP_and_resume_skips_diagnostics(
    isolated, monkeypatch
):
    root, plan = isolated
    seen = []

    def probe(route, host, timeout=20):
        intent = m.folder() / "diagnostic_intents/01.json"
        assert m.p.read_json(intent)["plan_id"] == plan["id"]
        assert host == "www.sec.gov" and timeout == 20
        seen.append(route)
        return {"tls_version": "synthetic TLS", "cipher": ["synthetic", "TLS", 256]}

    monkeypatch.setattr(m, "_tls_probe", probe)
    assert m.diagnose(root) == PROXY
    pinned = (m.folder() / "route.json").read_bytes()
    assert m.diagnose(root) == PROXY
    assert seen == [PROXY]
    assert (m.folder() / "route.json").read_bytes() == pinned
    assert not (m.folder() / "network/state.json").exists()


def test_pure_proxy_TLS_EOF_allows_exactly_one_direct_diagnostic(isolated, monkeypatch):
    root, _plan = isolated
    seen = []

    def probe(route, host, timeout=20):
        seen.append(route)
        assert (m.folder() / "diagnostic_intents" / f"{len(seen):02d}.json").exists()
        if route == PROXY:
            raise ssl.SSLEOFError(8, "synthetic TLS EOF")
        return {"tls_version": "synthetic TLS", "cipher": ["synthetic", "TLS", 256]}

    monkeypatch.setattr(m, "_tls_probe", probe)
    assert m.diagnose(root) == DIRECT
    assert m.diagnose(root) == DIRECT
    assert seen == [PROXY, DIRECT]
    assert not (m.folder() / "network/state.json").exists()


@pytest.mark.parametrize(
    "error,access_denied",
    [
        (OSError("Tunnel connection failed: 403 Forbidden"), True),
        (OSError("Tunnel connection failed: 429 Too Many Requests"), True),
        (OSError("Tunnel connection failed: 407 Proxy Authentication Required"), True),
        (OSError("Tunnel connection failed: 503 Service Unavailable"), True),
        (ssl.SSLCertVerificationError(1, "synthetic certificate verification failure"), False),
        (RuntimeError("synthetic coding error"), False),
    ],
)
def test_non_network_diagnostic_failure_never_falls_back(
    isolated, monkeypatch, error, access_denied
):
    root, _plan = isolated
    seen = []

    def probe(route, host, timeout=20):
        seen.append(route)
        raise error

    monkeypatch.setattr(m, "_tls_probe", probe)
    for _ in range(2):
        with pytest.raises((ValueError, RuntimeError)):
            m.diagnose(root)
    assert seen == [PROXY]
    assert (m.folder() / "diagnostic_terminal.json").exists()
    assert (m.folder() / "access_blocked.json").exists() == access_denied
    assert not (m.folder() / "route.json").exists()


def test_two_network_diagnostic_failures_exhaust_persistent_budget(isolated, monkeypatch):
    root, _plan = isolated
    seen = []

    def probe(route, host, timeout=20):
        seen.append(route)
        raise TimeoutError("synthetic TLS timeout")

    monkeypatch.setattr(m, "_tls_probe", probe)
    for _ in range(2):
        with pytest.raises(RuntimeError, match="TLS_diagnostic_budget_exhausted"):
            m.diagnose(root)
    assert seen == [PROXY, DIRECT]
    assert len(list((m.folder() / "diagnostic_intents").glob("*.json"))) == 2


def test_unresolved_diagnostic_intent_stops_without_replay_or_fallback(isolated, monkeypatch):
    root, plan = isolated
    m.c.write(m.folder() / "diagnostic_intents/01.json", {"plan_id": plan["id"], "route": PROXY})

    def forbidden(*_args, **_kwargs):
        raise AssertionError("uncertain diagnostic was replayed")

    monkeypatch.setattr(m, "_tls_probe", forbidden)
    with pytest.raises(ValueError, match="unresolved_diagnostic_intent"):
        m.diagnose(root)
    assert not (m.folder() / "diagnostic_intents/02.json").exists()


def test_tampered_route_cannot_trigger_rediagnosis(isolated, monkeypatch):
    root, plan = isolated
    m.c.write(
        m.folder() / "route.json",
        m.p.record("calibration_source_transport_route", plan_id="wrong:plan", route=DIRECT),
    )

    def forbidden(*_args, **_kwargs):
        raise AssertionError("tampered route caused fresh diagnostics")

    monkeypatch.setattr(m, "_tls_probe", forbidden)
    with pytest.raises(ValueError, match="same_persisted_route"):
        m.diagnose(root)
    assert plan["id"] != "wrong:plan"


def test_FixedProxy_does_not_obey_ambient_NO_PROXY_or_modify_target_identity(monkeypatch):
    monkeypatch.setattr(urllib.request, "proxy_bypass", lambda _host: True)
    request = urllib.request.Request(DIRECTORY)
    handler = m.FixedProxy({"https": PROXY["url"]})
    assert handler.proxy_open(request, PROXY["url"], "https") is None
    assert request.host == "127.0.0.1:7897"
    assert request._tunnel_host == "www.sec.gov"
    assert request.full_url == DIRECTORY


def test_fixed_opener_uses_empty_proxy_map_for_direct_and_preserves_certificate_verification(
    isolated,
):
    _root, plan = isolated
    opener = m._fixed_opener(plan, DIRECT, urllib.request.HTTPRedirectHandler())
    proxies = [
        handler for handler in opener.handlers if isinstance(handler, urllib.request.ProxyHandler)
    ]
    # ProxyHandler({}) may have no protocol-specific methods and therefore not be installed.
    assert not proxies or all(handler.proxies == {} for handler in proxies)
    tls = next(
        handler for handler in opener.handlers if isinstance(handler, urllib.request.HTTPSHandler)
    )
    assert tls._context.check_hostname is True
    assert tls._context.verify_mode == ssl.CERT_REQUIRED


def test_unknown_route_is_rejected_before_opener_creation(isolated):
    _root, plan = isolated
    with pytest.raises(ValueError, match="registered_route_only"):
        m._fixed_opener(plan, {"kind": "proxy", "url": "http://different.example:8080"})


@pytest.fixture
def registration(isolated, monkeypatch):
    root, synthetic = isolated
    monkeypatch.setattr(m, "read_plan", READ_PLAN)
    fields = {key: value for key, value in synthetic.items() if key not in ("id", "schema_version")}
    parent = m.p.record(
        "direction_calibration_source_acquisition_plan",
        **fields,
        sources={},
        code_commit="synthetic-parent-commit",
        at="synthetic-parent-time",
    )
    monkeypatch.setattr(m.original, "read_plan", lambda _root: parent)
    monkeypatch.setattr(urllib.request, "getproxies", lambda: {"https": PROXY["url"]})
    monkeypatch.setattr(urllib.request, "proxy_bypass", lambda _host: False)
    m.c.write(root / "panel_sources/acquisition_plan.json", parent)
    m.c.write(root / "panel_sources/network/state.json", {"requests": 3, "last_started": 0})
    for number in (1, 2, 3):
        m.c.write(
            root / "panel_sources/network/directory" / f"{number:04d}.json",
            {"plan_id": parent["id"], "attempt": number},
        )
        m.c.write(
            root / "panel_sources/failures/directory" / f"{number:04d}.json",
            {"attempt": number, "url": DIRECTORY, "error": "URLError(SSLEOFError('synthetic'))"},
        )
    source = root / m.SCRIPT
    source.parent.mkdir(parents=True)
    source.write_bytes(b"synthetic committed adapter")

    def git(args, cwd, text=False):
        assert cwd == root
        if args[:3] == ["git", "rev-parse", "HEAD"]:
            return "synthetic-retry-commit\n" if text else b"synthetic-retry-commit\n"
        assert args[:2] == ["git", "show"]
        return source.read_bytes()

    monkeypatch.setattr(m.subprocess, "check_output", git)
    return root, parent, source


def test_actual_revision_registration_preserves_contract_and_parent_bytes(registration):
    root, parent, _source = registration
    before = m.parent_evidence()
    revision = m.register(root)
    assert revision["parent_acquisition_plan_id"] == parent["id"]
    assert revision["parent_evidence"] == before == m.parent_evidence()
    assert revision["max_HTTP_requests"] == 195
    assert revision["max_attempts_per_asset"] == 3
    assert revision["cumulative_HTTP_attempt_cap"] == 198
    assert revision["maximum_TLS_diagnostic_connections"] == 2
    assert revision["diagnostic_HTTP_to_SEC"] == 0
    assert revision["selection_rule"] == parent["selection_rule"]
    assert revision["user_agent"] == parent["user_agent"]
    assert revision["official_directory_url"] == parent["official_directory_url"]
    assert revision["scientific_rules_changed"] is False
    assert m.read_plan(root) == revision
    before_revision = (m.folder() / "acquisition_plan.json").read_bytes()
    assert m.register(root) == revision
    assert (m.folder() / "acquisition_plan.json").read_bytes() == before_revision
    assert not (m.folder() / "diagnostic_intents").exists()
    assert not (m.folder() / "network").exists()


def test_parent_evidence_mutation_rejects_before_network(registration):
    root, _parent, _source = registration
    m.register(root)
    m.c.write(root / "panel_sources/network/state.json", {"requests": 4}, immutable=False)
    with pytest.raises(ValueError, match="frozen_parent_evidence_and_finite_revision"):
        m.read_plan(root)
    assert not (m.folder() / "diagnostic_intents").exists()


def test_source_mutation_rejects_before_network(registration):
    root, _parent, source = registration
    m.register(root)
    source.write_bytes(b"synthetic unregistered code change")
    with pytest.raises(ValueError, match="frozen_code"):
        m.read_plan(root)
    assert not (m.folder() / "diagnostic_intents").exists()


def test_registration_rejects_prior_HTTP_denial_instead_of_TLS_failure(registration):
    root, _parent, _source = registration
    m.c.write(
        root / "panel_sources/failures/directory/0001.json",
        {"attempt": 1, "url": DIRECTORY, "error": "synthetic HTTP forbidden", "status": 403},
        immutable=False,
    )
    with pytest.raises(ValueError, match="original_TLS_EOF_not_HTTP_denial"):
        m.register(root)
    assert not (m.folder() / "acquisition_plan.json").exists()
