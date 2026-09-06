"""Small dynamic CPU batches and serialization checks, without model or loss calls."""

from __future__ import annotations

from typing import Any

import numpy as np
import torch

from ..finance_qa_vnext_model_execution.models import require, sha
from ..qa_reasoning_share_training_preflight.loss import decode_arrays, encode_arrays
from .core import ARRAYS, identity, record, validate_record


def collate(
    rows: list[dict[str, Any]],
    tokens: list[dict[str, Any]],
    condition: dict[str, Any],
    binding: dict[str, Any],
    tokenizer: Any,
) -> tuple[dict[str, Any], bytes]:
    require(0 < len(rows) == len(tokens) <= 2, "length.cpu_small_batch")
    require(len({row["session_id"] for row in rows}) == 1, "length.cpu_no_session_splice")
    require(not torch.cuda.is_initialized(), "length.cpu_cuda_preinitialized")
    for row, token in zip(rows, tokens, strict=True):
        validate_record(row, token, condition, binding, tokenizer)
    maximum = max(item["sequence_length"] for item in tokens)
    shape = (len(tokens), maximum)
    arrays = {
        "input_ids": np.full(shape, binding["pad_token_id"], dtype=np.int64),
        "labels": np.full(shape, -100, dtype=np.int64),
        "attention_mask": np.zeros(shape, dtype=np.int64),
        "target_mask": np.zeros(shape, dtype=np.int64),
    }
    for index, item in enumerate(tokens):
        size = item["sequence_length"]
        for name in ARRAYS:
            arrays[name][index, :size] = item[name]
    binary = encode_arrays(arrays)
    restored = decode_arrays(binary)
    require(
        set(restored) == set(ARRAYS)
        and all(np.array_equal(restored[name], arrays[name]) for name in ARRAYS),
        "length.cpu_serialization_roundtrip",
    )
    tensors = {name: torch.from_numpy(restored[name]) for name in ARRAYS}
    require(all(value.device.type == "cpu" for value in tensors.values()), "length.cpu_device")
    require(all(value.dtype == torch.int64 for value in tensors.values()), "length.cpu_dtype")
    mask = tensors["target_mask"].bool()
    attention = tensors["attention_mask"].bool()
    require(
        torch.equal(tensors["labels"][mask], tensors["input_ids"][mask])
        and bool(torch.all(tensors["labels"][~mask] == -100))
        and not bool(torch.any(mask & ~attention))
        and not bool(torch.any(mask[:, 0])),
        "length.cpu_target_and_padding_mask",
    )
    shifted_targets = mask[:, 1:]
    require(
        int(shifted_targets.sum()) == sum(item["target_token_count"] for item in tokens)
        and bool(torch.all(attention[:, :-1][shifted_targets]))
        and torch.equal(
            tensors["labels"][:, 1:][shifted_targets],
            tensors["input_ids"][:, 1:][shifted_targets],
        ),
        "length.cpu_actual_causal_shift",
    )
    for index, item in enumerate(tokens):
        size = item["sequence_length"]
        require(
            bool(torch.all(tensors["attention_mask"][index, :size] == 1))
            and bool(torch.all(tensors["attention_mask"][index, size:] == 0))
            and bool(torch.all(tensors["input_ids"][index, size:] == binding["pad_token_id"])),
            "length.cpu_dynamic_right_padding",
        )
    require(not torch.cuda.is_initialized(), "length.cpu_cuda_initialized")
    return record(
        "cpu_batch",
        representation_condition_id=condition["id"],
        candidate_ids=[row["id"] for row in rows],
        token_record_ids=[item["id"] for item in tokens],
        session_id=rows[0]["session_id"],
        shape=list(shape),
        padding_side="right",
        unpadded_lengths=[item["sequence_length"] for item in tokens],
        pad_token_id=binding["pad_token_id"],
        dtype="int64",
        device="cpu",
        real_token_count=int(attention.sum()),
        target_token_count=int(mask.sum()),
        padding_token_count=int((~attention).sum()),
        causal_target_count=int(shifted_targets.sum()),
        original_arrays_roundtrip_exact=True,
        original_content_revalidated=True,
        dynamic_padding_checked=True,
        labels_and_causal_predecessors_checked=True,
        npz_sha256=sha(binary),
        npz_byte_count=len(binary),
        student_forward_calls=0,
        student_parameter_updates=0,
        GPU_jobs=0,
        quotient_weights_assigned=False,
    ), binary


def build_batches(
    source: dict[str, Any],
    dataset: dict[str, Any],
    condition: dict[str, Any],
    tokenizer: Any,
) -> tuple[dict[str, Any], dict[str, bytes]]:
    identity(dataset, "token_dataset")
    tokens = {item["row_id"]: item for item in dataset["records"]}
    batches, files = [], {}
    for label, session in zip(("B01", "B02"), source["sessions"], strict=True):
        rows = [row for row in source["dataset"]["rows"] if row["session_id"] == session["id"]]
        rows = [row for row in rows if tokens[row["id"]]["consumable_token_representation"]]
        for offset in range(0, len(rows), 2):
            selected = rows[offset : offset + 2]
            summary, binary = collate(
                selected,
                [tokens[row["id"]] for row in selected],
                condition,
                source["binding"],
                tokenizer,
            )
            name = f"cpu_batches/{label}_{offset // 2:02d}.npz"
            files[name] = binary
            batches.append({"path": name, "batch": summary})
    used = [row_id for item in batches for row_id in item["batch"]["candidate_ids"]]
    require(len(used) == len(set(used)) == dataset["fit_count"], "length.cpu_exhaustive_fit_rows")
    return record(
        "cpu_loading",
        representation_condition_id=condition["id"],
        batches=batches,
        batch_count=len(batches),
        loaded_records=len(used),
        maximum_batch_size=2,
        maximum_observed_batch_sequence_length=max(
            (item["batch"]["shape"][1] for item in batches),
            default=None,
        ),
        all_tensors_cpu=True,
        student_weight_loads=0,
        student_forward_calls=0,
        student_parameter_updates=0,
        GPU_jobs=0,
        training_stack_or_gpu_memory_feasibility_validated=False,
    ), files
