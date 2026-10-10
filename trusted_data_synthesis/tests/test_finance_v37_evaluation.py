"""CPU/mock checks of resource observation around the unchanged local provider."""

import asyncio
import gc
import importlib
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
subject = importlib.import_module("finqa_v37_evaluation")


@pytest.fixture
def fixture():
    calls, events = [], []

    class Provider:
        async def chat(self, *args, **kwargs):
            calls.append((args, kwargs))
            return {"actual_tokens": [31, 7, 8], "content": "unaltered"}

    def loader(*args, **kwargs):
        calls.append(("load", args, kwargs))
        return Provider()

    final = SimpleNamespace(
        load_final_provider=loader,
        torch=SimpleNamespace(
            cuda=SimpleNamespace(
                is_initialized=lambda: False,
                reset_peak_memory_stats=lambda: events.append("one_reset_before_load"),
            )
        ),
    )
    monitor = SimpleNamespace(
        snapshot=lambda name, **kwargs: events.append(name),
        clear_unused=lambda name: events.append(name),
        check_stop=lambda name, **kwargs: events.append(name),
    )
    return SimpleNamespace(final=final, monitor=monitor, calls=calls, events=events)


def test_observation_preserves_loader_and_response_exact_values(fixture):
    f = fixture
    state, original = subject.install_observation_hook(f.final, lambda: f.monitor, lambda: False)
    provider = f.final.load_final_provider("plan", "job", {"actual_state": 3})
    response = asyncio.run(provider.chat(["public_history"], {"tools": 4}, config="same"))
    assert response == {"actual_tokens": [31, 7, 8], "content": "unaltered"}
    assert f.calls == [
        ("load", ("plan", "job", {"actual_state": 3}), {}),
        ((["public_history"], {"tools": 4}), {"config": "same"}),
    ]
    assert f.events == [
        "one_reset_before_load",
        "before_model_load",
        "after_model_load",
        "before_endpoint_response",
        "after_endpoint_response",
    ]
    assert state["response_calls"] == 1 and state["provider_ref"]() is provider
    assert original is not f.final.load_final_provider


def test_no_second_load_or_implicit_retry(fixture):
    f = fixture
    subject.install_observation_hook(f.final, lambda: f.monitor, lambda: False)
    f.final.load_final_provider("same")
    with pytest.raises(ValueError, match="one actual endpoint model"):
        f.final.load_final_provider("same")
    assert len(f.calls) == 1


def test_stop_blocks_next_provider_call(fixture):
    f = fixture
    state, _ = subject.install_observation_hook(f.final, lambda: f.monitor, lambda: True)
    provider = f.final.load_final_provider("plan")
    with pytest.raises(ValueError, match="safe stop"):
        asyncio.run(provider.chat("no new generation"))
    assert len(f.calls) == 1 and state["response_calls"] == 0


def test_observation_cycle_does_not_keep_loaded_provider_alive(fixture):
    f = fixture
    state, _ = subject.install_observation_hook(f.final, lambda: f.monitor, lambda: False)
    provider = f.final.load_final_provider("plan")
    assert state["provider_ref"]() is provider
    del provider
    gc.collect()
    assert state["provider_ref"]() is None
