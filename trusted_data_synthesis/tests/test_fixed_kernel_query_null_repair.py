"""One minimal set of CPU controls for the independent nullable-query revision."""

import hashlib
import importlib
import importlib.util
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parents[1] / "scripts/fixed_kernel_query_null_repair_20260915.py"
SPEC = importlib.util.spec_from_file_location("query_null_repair_control", SCRIPT)
repair = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(repair)


def pair(monkeypatch, concept):
    monkeypatch.syspath_prepend(str(Path(__file__).parents[1] / "src"))
    runtime = importlib.import_module(
        "trusted_synthesis.experiments.finance_qa_vnext_eval_readiness.runtime"
    )
    payload = {"s": {"facts": {"us-gaap": {"Revenue": concept}}}}
    return (
        runtime,
        runtime.SnapshotSources.synthetic(payload),
        repair.repaired_snapshot_sources_class(runtime).synthetic(payload),
    )


def concept(**fields):
    return {
        "label": "Revenue",
        "description": "Reported revenue",
        "units": {"USD": [{"val": 3, "start": "2020-01-01", "end": "2020-12-31"}]},
        **fields,
    }


def test_explicit_null_repair_returns_hit_or_legitimate_empty(monkeypatch):
    for field in ("label", "description"):
        _, old, new = pair(monkeypatch, concept(**{field: None}))
        args = {"source_id": "s", "label_contains": "Revenue", "unit": "USD"}
        with pytest.raises(TypeError, match="NoneType"):
            old.query(args)
        result = new.query(args)
        assert result["total"] == 1 and result["records"][0]["record"]["val"] == 3
        result_key = "label" if field == "label" else "definition"
        assert result["records"][0][result_key] is None  # No metadata replacement in returns.
        assert new.query({**args, "label_contains": "nonexistent"})["total"] == 0
        assert new.payloads["s"]["facts"]["us-gaap"]["Revenue"][field] is None


def test_nonnull_queries_and_all_other_methods_unchanged(monkeypatch):
    runtime, old, new = pair(monkeypatch, concept())
    raw_before = Path(runtime.__file__).read_bytes()
    method_before = runtime.SnapshotSources.query
    for args in (
        {"source_id": "s", "label_contains": "revenue", "unit": "USD", "limit": 1},
        {"source_id": "s", "concept": "us-gaap:Revenue", "start": "2020-01-01"},
        {"source_id": "s", "unit": "million USD"},
        {"source_id": "s", "offset": 1},
    ):
        assert new.query(args) == old.query(args)
    for name in ("_payload", "_row", "read_source", "read_json", "list_concepts"):
        assert getattr(type(new), name) is getattr(runtime.SnapshotSources, name)
    assert runtime.SnapshotSources.query is method_before
    assert (
        hashlib.sha256(Path(runtime.__file__).read_bytes()).digest()
        == hashlib.sha256(raw_before).digest()
    )


def test_nonnull_invalid_types_and_invalid_arguments_still_fail(monkeypatch):
    _, old, new = pair(monkeypatch, concept(label=False))
    args = {"source_id": "s", "label_contains": "Revenue"}
    for instance in (old, new):
        with pytest.raises(TypeError):
            instance.query(args)
        with pytest.raises(ValueError, match="source.query_arguments"):
            instance.query({"source_id": "s", "unknown": 1})
        with pytest.raises(ValueError, match="source.page_limits"):
            instance.query({"source_id": "s", "limit": 21})
