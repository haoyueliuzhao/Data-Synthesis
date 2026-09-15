"""Three bounded synthetic controls; no historical package, model or tokenizer."""

import copy
import importlib.util
from pathlib import Path

import numpy as np
import pytest

SCRIPT = Path(__file__).parents[1] / "scripts/fixed_kernel_delivery_training_audit_20260915.py"
SPEC = importlib.util.spec_from_file_location("delivery_training_audit", SCRIPT)
audit = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(audit)
p = audit.p


def fixture():
    messages = [
        {"role": "system", "content": "public protocol"},
        {"role": "user", "content": "public source"},
    ]
    rows = []
    for index, kind, ids, start, end in [
        (0, "calculate", [1, 2, 3, 4, 5], 2, 4),
        (1, "Final", [1, 2, 3, 4, 5, 6, 7, 8], 5, 7),
    ]:
        text = '{"tool":"calculate"}' if index == 0 else '{"final":{}}'
        candidate = {
            "id": f"candidate:{index}",
            "response_index": index,
            "response_kind": kind,
            "target_text": text,
            "target_raw_sha256": p.sha(text),
            "messages": messages,
            "public_runtime_state_id": "history:" + p.sha(p.encode(messages)),
            "role": "train",
            "pool": "A",
        }
        mask = [int(start <= pos < end) for pos in range(len(ids))]
        representation = {
            "input_ids": ids,
            "target_mask": mask,
            "labels": [token if active else -100 for token, active in zip(ids, mask, strict=True)],
            "sequence_length": len(ids),
            "target_token_count": end - start,
            "target_token_start": start,
            "target_token_end": end,
            "causal_shift": 1,
            "causal_target_token_start": start - 1,
            "causal_target_token_end": end - 1,
            "target_raw_sha256": p.sha(text),
        }
        rows.append({"candidate": candidate, "representation": representation})
    metadata = {
        "role": "train",
        "pool": "A",
        "package_id": "package:1",
        "task_id": "task:1",
        "session_id": "session:1",
        "fused": True,
        "whole_package_target_tokens": 4,
        "segments": [
            {
                "input_offset": 0,
                "input_length": 8,
                "target_offset": 0,
                "target_count": 4,
                "source_response_indices": [0, 1],
            }
        ],
    }
    original = {
        "role": "train",
        "pool": "A",
        "id": "package:1",
        "task_id": "task:1",
        "registered_session_id": "session:1",
        "rows": rows,
        "whole_package_target_tokens": 4,
    }
    return (
        original,
        metadata,
        np.arange(1, 9, dtype=np.int32),
        np.array([2, 3, 5, 6], dtype=np.int32),
    )


def test_metadata_selection_ignores_loss_output_order_and_private_fields():
    tasks = [
        {
            "task_id": f"{family}:{i}",
            "family": family,
            "public_messages_sha256": str(i),
            "surface_version_id": "surface:1",
        }
        for family in audit.FAMILIES
        for i in range(3)
    ]
    chosen = audit.choose_tasks({"tasks": tasks})
    changed = [
        {**row, "loss": 900 - i, "private_answer": "do not read", "output": "Final"}
        for i, row in enumerate(reversed(tasks))
    ]
    assert audit.choose_tasks({"tasks": changed}) == chosen
    assert len(chosen) == 3


def test_actual_slice_union_and_causal_shift_reject_missing_Final_target():
    original, metadata, inputs, positions = fixture()
    rows = audit.audit_rows(original, metadata, inputs, positions)
    assert [row["response_kind"] for row in rows] == ["calculate", "Final"]
    assert rows[1]["causal_logit_start"] == 4
    wrong = positions.copy()
    wrong[-1] = 7
    with pytest.raises(ValueError):
        audit.audit_rows(original, metadata, inputs, wrong)
    bad = copy.deepcopy(original)
    bad["rows"][1]["representation"]["causal_target_token_start"] = 5
    with pytest.raises(ValueError):
        audit.audit_rows(bad, metadata, inputs, positions)


def test_prefix_only_native_public_history_never_target_or_autonomous_credit():
    original, metadata, _, _ = fixture()
    candidate = original["rows"][1]["candidate"]
    prefix = audit.public_prefix(
        candidate, {"task_id": "task:1", "family": "annual_flow"}, metadata
    )
    assert prefix["input_messages"] == candidate["messages"]
    assert prefix["reference_response"] == candidate["target_text"]
    assert prefix["reference_response_is_offline_only_never_sent_to_Student"]
    assert "target_text" not in prefix and "target_raw_sha256" not in prefix
    assert not prefix["conditional_continuation_is_autonomous_success"]
    assert not prefix["supplied_Probe_history_is_Student_capability"]
    candidate["target_text"] = '{"final":{"result_id":"tool:1"}}'
    candidate["messages"] = candidate["messages"] + [
        {"role": "assistant", "content": original["rows"][0]["candidate"]["target_text"]},
        {
            "role": "user",
            "content": '{"tool_observation":{"call_id":"tool:1","tool":"calculate","status":"ok"}}',
        },
    ]
    boundaries = audit.choose_boundaries(original)
    assert boundaries[0][1] is original["rows"][0]["candidate"]
    assert boundaries[0][2] is True
