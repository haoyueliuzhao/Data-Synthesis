"""Targeted CPU-only checks for the new V45 natural-handoff namespace."""

import importlib
import shutil
import sys
from pathlib import Path

import pytest
import test_finance_v44_handoff as v44_tests

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
h = importlib.import_module("finqa_v45_handoff")


@pytest.fixture
def handoff(tmp_path, monkeypatch):
    monkeypatch.setattr(v44_tests, "h", h)
    return v44_tests.handoff.__wrapped__(tmp_path, monkeypatch)


def test_new_handoff_observes_natural_exit_and_releases_once(handoff):
    v44_tests.test_natural_handoff_waits_for_post_barrier_queue_and_releases_once(handoff)


def test_stop_after_preflight_does_not_signal_scientific_parent(handoff):
    v44_tests.test_stop_after_preflight_never_signals_parent(handoff)


def test_new_prepared_module_loads_actual_neighbor_primitive(tmp_path):
    canonical = importlib.import_module("finqa_v41_handoff")
    implementation = tmp_path / "implementation"
    implementation.mkdir()
    for source in (Path(h.__file__), Path(h.base.__file__)):
        shutil.copy2(source, implementation / source.name)
    spec = importlib.util.spec_from_file_location(
        "v45_cpu_prepared_handoff", implementation / "finqa_v45_handoff.py"
    )
    candidate = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = candidate
    spec.loader.exec_module(candidate)
    assert candidate.base is not canonical
    assert Path(candidate.base.__file__) == implementation / "finqa_v41_handoff.py"
    candidate._runtime_sources(tmp_path)
