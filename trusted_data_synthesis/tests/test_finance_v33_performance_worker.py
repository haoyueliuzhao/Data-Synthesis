"""CPU-only checks of the pinned measurement adapter; no experiment execution."""

import ast
import importlib
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
worker = importlib.import_module("finqa_v33_performance_worker")


def source():
    return Path(worker.ADAPTER_RECEIPT["source"]["path"]).read_text()


def function(tree, name):
    return next(
        node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == name
    )


def test_exact_five_non_numeric_adaptations():
    original = ast.parse(source())
    adapted, counts = worker.adapt_source(source())
    assert counts == worker.EXPECTED_ADAPTATIONS
    changed = {"run", "execute_micro", "execute_cohort"}
    for node in original.body:
        if isinstance(node, ast.FunctionDef) and node.name not in changed:
            assert ast.dump(node) == ast.dump(function(adapted, node.name))
    assert worker.run.__globals__["control"] is worker.control
    assert worker.run.__globals__["__file__"] == worker.__file__
    assert worker.run.__globals__["dependencies"] is worker.dependencies
    assert worker.run.__globals__["execute_micro"] is worker.execute_micro


@pytest.mark.parametrize(
    "old,new",
    [
        ('profile_responses=int(variant == "R0")', "profile_responses=1"),
        ('variant in ("R1", "R2")', 'variant in ("R1", "R2", "R4")'),
        ('"micro_R1", "micro_R2"', '"micro_R1", "micro_R4"'),
        (
            "import finqa_v32_performance_controller as control",
            "import wrong_controller as control",
        ),
        ("profile = run_profile(", "profile = wrong_profile("),
    ],
)
def test_fails_closed_on_source_contract_drift(old, new):
    assert old in source()
    with pytest.raises(ValueError, match="changed"):
        worker.adapt_source(source().replace(old, new))


def test_profile_removed_and_only_r3_admitted():
    tree, _ = worker.adapt_source(source())
    micro = function(tree, "execute_micro")
    diagnostic = next(
        node
        for node in ast.walk(micro)
        if isinstance(node, ast.If)
        and any(
            isinstance(child, ast.Call)
            and isinstance(child.func, ast.Name)
            and child.func.id == "run_profile"
            for statement in node.body
            for child in ast.walk(statement)
        )
    )
    assert ast.literal_eval(diagnostic.test) is False
    counter = next(
        node
        for node in ast.walk(micro)
        if isinstance(node, ast.keyword) and node.arg == "profile_responses"
    )
    assert ast.literal_eval(counter.value) == 0
    run = function(tree, "run")
    assert next(
        ast.literal_eval(node) for node in ast.walk(run) if isinstance(node, ast.Set)
    ) == set(worker.control.STAGES)
    cohort = function(tree, "execute_cohort")
    allowed = next(
        node
        for node in ast.walk(cohort)
        if isinstance(node, ast.Compare)
        and isinstance(node.left, ast.Name)
        and node.left.id == "variant"
    )
    assert ast.literal_eval(allowed.comparators[0]) == ("R3",)


def test_result_labels_and_no_profile_enforced(monkeypatch):
    monkeypatch.setattr(
        worker, "_micro", lambda: dict(variant="R3", profile_responses=0, diagnostic_profile=None)
    )
    assert worker.execute_micro()["active_variant"] == "R3"
    monkeypatch.setattr(
        worker, "_micro", lambda: dict(variant="R0", profile_responses=1, diagnostic_profile=None)
    )
    with pytest.raises(ValueError, match="diagnostic profile"):
        worker.execute_micro()
    monkeypatch.setattr(worker, "_cohort", lambda: dict(selected_variant="R3"))
    assert worker.execute_cohort()["active_variant"] == "R3"


def test_dependency_facade_preserves_ordered_accumulation_bytecode():
    # Other test modules may already have imported the working-tree runtime;
    # production always enters from a fresh interpreter, so exercise that path.
    program = """
import sys
sys.path.insert(0, sys.argv[1])
import finqa_v33_performance_worker as worker
_, rt, _, variants, _, _ = worker.dependencies()
import finqa_v33_activation_residency as backend
assert not rt.torch.cuda.is_initialized()
assert variants.feedback_gradient.__code__ is backend.v32.feedback_gradient.__code__
assert variants.feedback_gradient.__globals__['BACKEND_VERSION'] == backend.BACKEND_VERSION
assert backend.v32.feedback_gradient.__globals__['BACKEND_VERSION'] == backend.v32.BACKEND_VERSION
assert variants.__file__ == backend.__file__
try:
    variants.ReplaySession(None, None, variant='R2')
except ValueError as exc:
    assert 'only registered R3' in str(exc)
else:
    raise AssertionError('unregistered variant accepted')
"""
    subprocess.run(
        [sys.executable, "-c", program, str(Path(worker.__file__).parent)],
        check=True,
        capture_output=True,
        text=True,
        timeout=60,
    )
