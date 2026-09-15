"""One new layout control; prior source compilation controls are not rerun."""

import importlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
compact = importlib.import_module("fixed_kernel_source_view_compact_20260915")


def test_lossless_layout_and_same_live_replay_numeric_read():
    p = compact.p
    sources = [
        {
            "source_id": "s" + str(i),
            "source_kind": "original_companyfacts_observation",
            "raw_object_id": "raw",
            "raw_sha256": "sha",
            "original_url": "https://example.invalid/",
            "native_pointer": "/" + str(i),
            "label": "Metric",
            "definition": "Original definition",
            "concept": "us-gaap:Metric",
            "unit": "USD",
            "record": {"val": i + 5, "end": "2020-12-31"},
        }
        for i in range(2)
    ]
    public = {
        "question": "synthetic",
        "sources": sources,
        "quantity_contract": {},
        "period_contract": {"task_id": "synthetic"},
        "source_policy": "synthetic",
        "tool_contract": {},
    }
    packed = compact.compact_public(public)
    assert compact.expand_public(packed) == public
    assert len(packed["sources"]) == len(sources)
    runtime = compact.build_runtime()
    messages = [{"role": "user", "content": p.encode(packed).decode()}]
    identity = {
        "task_id": "synthetic",
        "family": "dual_sufficient",
        "surface_version_id": "new-v2",
        "parent_manifest_id": "new-v2-manifest",
        "public_messages_sha256": p.sha(p.encode(messages)),
    }
    source = runtime.Sources(packed)
    session = runtime.generate(
        messages,
        identity,
        source,
        scripted=[
            {"tool": "read_source", "arguments": {"source_id": "s0", "unit": "million USD"}},
            {"final": {"value": "0.000005", "unit": "million USD", "result_id": "tool:1"}},
        ],
    )
    assert session["events"][0]["tool_call"]["result"]["exact_value"] == "1/200000"
    assert runtime.replay_session(session, source) == session
    assert compact.SYSTEM == compact.prior.SYSTEM
