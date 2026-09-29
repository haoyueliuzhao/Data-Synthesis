"""Offline httpx routing checks: no socket, credentials, wallet, API or GPU."""

import ast
import asyncio
import os
import ssl
from collections import Counter
from pathlib import Path
from types import SimpleNamespace

import httpcore
import httpx
import pytest

SOURCE = Path(__file__).resolve().parents[1] / "src/trusted_synthesis/finance_research"
CLIENT_COUNTS = {
    "probe_provider.py": 1,
    "v6_review_provider.py": 1,
    "providers.py": 1,
    "probe_collection.py": 1,
    "v6_collection.py": 2,
    "v6_review_revision.py": 1,
    "v6_decomposed_review.py": 1,
    "v7_review_mask_trial.py": 1,
    "v8_collection.py": 1,
    "v8_review_validation.py": 1,
    "v9_production_review.py": 1,
}


def constructors():
    found = []
    for path in sorted(SOURCE.glob("*.py")):
        for node in ast.walk(ast.parse(path.read_text())):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "httpx"
                and node.func.attr in {"AsyncClient", "AsyncHTTPTransport"}
            ):
                found.append((path.name, node))
    return found


def construct(node):
    return eval(
        compile(ast.Expression(node), "<only-httpx-constructor>", "eval"),
        {
            "httpx": httpx,
            "self": SimpleNamespace(timeout=120),
            "timeout": 120,
            "concurrency": 32,
            "plan": {"concurrency": 32},
        },
    )


@pytest.fixture
def reverse_proxy_environment(monkeypatch):
    names = ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy")
    for name in names:
        monkeypatch.setenv(name, "http://127.0.0.1:7897")
    for name in ("NO_PROXY", "no_proxy"):
        monkeypatch.delenv(name, raising=False)
    return {name: os.environ[name] for name in names}


def test_every_existing_deepseek_owned_constructor_ignores_environment():
    nodes = constructors()
    assert Counter(name for name, n in nodes if n.func.attr == "AsyncClient") == CLIENT_COUNTS
    assert Counter(name for name, n in nodes if n.func.attr == "AsyncHTTPTransport") == {
        "probe_provider.py": 1,
        "v6_review_provider.py": 1,
    }
    assert len(nodes) == 14
    for _, node in nodes:
        keywords = {k.arg: k.value for k in node.keywords}
        assert isinstance(keywords.get("trust_env"), ast.Constant)
        assert keywords["trust_env"].value is False
        assert not {"proxy", "mounts"} & set(keywords)
        assert (
            not isinstance(keywords.get("verify"), ast.Constant) or keywords["verify"].value is True
        )


@pytest.mark.parametrize(
    "filename,node",
    constructors(),
    ids=lambda value: (
        value if isinstance(value, str) else value.func.attr + ":" + str(value.lineno)
    ),
)
def test_real_httpx_deepseek_pool_is_direct_tls_verified_zero_retry(
    reverse_proxy_environment, filename, node
):
    async def inspect():
        actual = construct(node)
        try:
            if isinstance(actual, httpx.AsyncClient):
                assert actual.trust_env is False
                assert not actual.follow_redirects
                for endpoint in (
                    "https://api.deepseek.com/chat/completions",
                    "https://api.deepseek.com/beta/chat/completions",
                ):
                    transport = actual._transport_for_url(httpx.URL(endpoint))
                    assert type(transport._pool) is httpcore.AsyncConnectionPool
                    assert transport._pool._retries == 0
                    assert transport._pool._ssl_context.verify_mode == ssl.CERT_REQUIRED
                    assert transport._pool._ssl_context.check_hostname is True
                assert not actual._mounts
            else:
                assert type(actual._pool) is httpcore.AsyncConnectionPool
                assert actual._pool._retries == 0
                assert actual._pool._ssl_context.verify_mode == ssl.CERT_REQUIRED
                assert actual._pool._ssl_context.check_hostname is True
        finally:
            await actual.aclose()

    asyncio.run(inspect())
    assert {
        name: os.environ[name] for name in reverse_proxy_environment
    } == reverse_proxy_environment


def test_other_services_keep_environment_proxy_and_live_entry_has_no_client_injection(
    reverse_proxy_environment,
):
    async def inspect():
        async with httpx.AsyncClient() as unchanged:
            route = unchanged._transport_for_url(httpx.URL("https://example.org/"))
            assert type(route._pool) is httpcore.AsyncHTTPProxy

    asyncio.run(inspect())
    tree = ast.parse((SOURCE / "v9_production_review.py").read_text())
    run = next(n for n in tree.body if isinstance(n, ast.AsyncFunctionDef) and n.name == "run")
    assert "client" not in {a.arg for a in [*run.args.args, *run.args.kwonlyargs]}


def test_frozen_source_child_no_proxy_routes_only_deepseek_direct(
    reverse_proxy_environment, monkeypatch
):
    # Runtime-only switch for the immutable original long-batch source. Preserve
    # the other proxy settings and merge existing localhost bypasses.
    bypass = "localhost,127.0.0.1,api.deepseek.com"
    monkeypatch.setenv("NO_PROXY", bypass)
    monkeypatch.setenv("no_proxy", bypass)

    async def inspect():
        async with httpx.AsyncClient() as unchanged_constructor:
            for endpoint in (
                "https://api.deepseek.com/models",
                "https://api.deepseek.com/chat/completions",
                "https://api.deepseek.com/beta/chat/completions",
            ):
                direct = unchanged_constructor._transport_for_url(httpx.URL(endpoint))
                assert type(direct._pool) is httpcore.AsyncConnectionPool
                assert direct._pool._retries == 0
                assert direct._pool._ssl_context.verify_mode == ssl.CERT_REQUIRED
                assert direct._pool._ssl_context.check_hostname is True
            other = unchanged_constructor._transport_for_url(httpx.URL("https://example.com/"))
            assert type(other._pool) is httpcore.AsyncHTTPProxy
            assert other._pool._proxy_url.host == b"127.0.0.1"
            assert other._pool._proxy_url.port == 7897

    asyncio.run(inspect())
    assert {
        name: os.environ[name] for name in reverse_proxy_environment
    } == reverse_proxy_environment
