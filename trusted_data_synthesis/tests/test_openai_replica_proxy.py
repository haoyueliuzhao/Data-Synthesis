from __future__ import annotations

import importlib.util
import itertools
from pathlib import Path
from types import ModuleType


def _load_proxy_module() -> ModuleType:
    path = Path(__file__).parents[1] / "scripts" / "openai_round_robin_proxy.py"
    spec = importlib.util.spec_from_file_location("openai_round_robin_proxy", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_post_routing_prefers_least_loaded_backend_without_retry() -> None:
    proxy = _load_proxy_module()
    proxy.BACKENDS = ("backend-a", "backend-b", "backend-c")
    proxy.BACKEND_INFLIGHT = {
        "backend-a": 2,
        "backend-b": 0,
        "backend-c": 1,
    }
    proxy.COUNTER = itertools.count()

    assert proxy._select_backends("POST") == ("backend-b",)
    assert proxy.BACKEND_INFLIGHT["backend-b"] == 1
    proxy._release_backend("POST", "backend-b")
    assert proxy.BACKEND_INFLIGHT["backend-b"] == 0


def test_get_routing_retains_deterministic_all_backend_fallback() -> None:
    proxy = _load_proxy_module()
    proxy.BACKENDS = ("backend-a", "backend-b", "backend-c")
    proxy.BACKEND_INFLIGHT = dict.fromkeys(proxy.BACKENDS, 0)
    proxy.COUNTER = itertools.count(1)

    assert proxy._select_backends("GET") == (
        "backend-b",
        "backend-c",
        "backend-a",
    )
    assert proxy.BACKEND_INFLIGHT == {
        "backend-a": 0,
        "backend-b": 0,
        "backend-c": 0,
    }
