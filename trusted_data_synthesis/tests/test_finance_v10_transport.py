"""Explicit proxy binding and installed HTTPX pool inspection; never send HTTP."""

import asyncio
import copy
import hashlib
import json
import os
import ssl

import httpcore
import pytest

from trusted_synthesis.finance_research import v10_review_provider as provider
from trusted_synthesis.finance_research import v10_transport as transport
from trusted_synthesis.finance_research.contracts import digest

PROXY = "http://127.0.0.1:7897"
PLAN = dict(id="synthetic-original-protocol", batch_id=transport.BATCH_ID)


def record():
    body = dict(
        schema="v10_explicit_proxy_authorization.v1",
        protocol_id=PLAN["id"],
        batch_id=PLAN["batch_id"],
        proxy_url_sha256=transport.PROXY_URL_SHA256,
        authorization=dict(user_reply=transport.USER_REPLY),
    )
    return {**body, "id": digest(body)}


def save(directory, value):
    path = directory / transport.AUTHORIZATION_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def test_exact_proxy_authority_reads_environment_without_mutating_other_routes(
    tmp_path, monkeypatch
):
    assert hashlib.sha256(PROXY.encode()).hexdigest() == transport.PROXY_URL_SHA256
    monkeypatch.setenv("HTTPS_PROXY", PROXY)
    monkeypatch.setenv("HTTP_PROXY", "http://127.0.0.1:7890")
    monkeypatch.setenv("ALL_PROXY", "socks5://127.0.0.1:9999")
    monkeypatch.setenv("NO_PROXY", "localhost,example.com")
    before = dict(os.environ)
    save(tmp_path, record())
    assert transport.checked_proxy(tmp_path, PLAN) == PROXY
    assert dict(os.environ) == before


def test_absent_authority_keeps_direct_but_present_invalid_file_never_falls_back(tmp_path):
    assert transport.checked_proxy(tmp_path, PLAN) is None
    save(tmp_path, {"not": "a bound authority"})
    with pytest.raises(ValueError, match="authority"):
        transport.checked_proxy(tmp_path, PLAN)


@pytest.mark.parametrize(
    "field", ["protocol_id", "batch_id", "proxy_url_sha256", "user_reply", "record_hash"]
)
def test_wrong_authority_or_scope_rejected_before_constructing_transport(
    tmp_path, monkeypatch, field
):
    monkeypatch.setenv("HTTPS_PROXY", PROXY)
    value = copy.deepcopy(record())
    if field == "user_reply":
        value["authorization"][field] = "not the explicit approval"
    elif field == "record_hash":
        value["id"] = "0" * 64
    else:
        value[field] = "different binding"
    if field != "record_hash":
        value["id"] = digest({k: v for k, v in value.items() if k != "id"})
    save(tmp_path, value)
    with pytest.raises(ValueError, match="binding differs"):
        transport.checked_proxy(tmp_path, PLAN)


def test_authorized_file_requires_exact_uppercase_HTTPS_PROXY_no_alternate_fallback(
    tmp_path, monkeypatch
):
    save(tmp_path, record())
    monkeypatch.delenv("HTTPS_PROXY", raising=False)
    monkeypatch.setenv("https_proxy", PROXY)
    monkeypatch.setenv("HTTP_PROXY", PROXY)
    with pytest.raises(ValueError, match="HTTPS_PROXY differs"):
        transport.checked_proxy(tmp_path, PLAN)
    monkeypatch.setenv("HTTPS_PROXY", PROXY + "/")
    with pytest.raises(ValueError, match="HTTPS_PROXY differs"):
        transport.checked_proxy(tmp_path, PLAN)


def test_proxy_and_direct_factories_have_TLS_noenv_zero_retries_and_no_connections(monkeypatch):
    monkeypatch.setenv("HTTPS_PROXY", "http://127.0.0.1:9999")
    monkeypatch.setenv("ALL_PROXY", "http://127.0.0.1:9998")
    monkeypatch.setenv("SSL_CERT_FILE", "/nonexistent-untrusted-environment-ca.pem")

    async def inspect():
        async with provider.annotation_client(timeout=17, proxy=PROXY) as proxied:
            pool = proxied._transport._pool
            assert isinstance(pool, httpcore.AsyncHTTPProxy)
            assert pool._proxy_url.host == b"127.0.0.1" and pool._proxy_url.port == 7897
            assert proxied._trust_env is False and proxied._mounts == {}
            assert pool._retries == 0 and pool._ssl_context.check_hostname
            assert pool._ssl_context.verify_mode == ssl.CERT_REQUIRED
            assert pool.connections == [] and proxied in provider._DIRECT_CLIENTS
        async with provider.direct_client(timeout=19) as direct:
            pool = direct._transport._pool
            assert isinstance(pool, httpcore.AsyncConnectionPool)
            assert not isinstance(pool, httpcore.AsyncHTTPProxy)
            assert direct._trust_env is False and direct._mounts == {}
            assert pool._retries == 0 and pool._ssl_context.check_hostname
            assert pool._ssl_context.verify_mode == ssl.CERT_REQUIRED
            assert pool.connections == [] and direct in provider._DIRECT_CLIENTS

    asyncio.run(inspect())
