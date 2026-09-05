"""Freeze one existing local tokenizer and mask only original assistant content.

This module never loads a language model or invokes training. Tokenizer loading
may import torch through transformers; that is not a GPU job or a weight load.
"""

from __future__ import annotations

import json
from importlib import metadata
from pathlib import Path
from typing import Any

from .models import MAX_SEQUENCE_LENGTH, TrainingPreflightError, record, require, sha

MODEL_REVISION = "a09a35458c702b33eeacc393d103063234e8bc28"
MODEL_DIRECTORY = Path("/data1/zhuxinrui/models/Qwen2.5-7B-Instruct-" + MODEL_REVISION)
SOURCE_CONFIGURATION = "trusted_data_synthesis/config/vtdo_qwen2_5_7b_500k.json"
SOURCE_CONFIGURATION_SHA256 = "e9a51988c6b4034c21a7d5b84b94e4ce65c772f9b608f81c08054e97bee4d852"
SOURCE_CONFIGURATION_BYTES = 855
TOKENIZER_MEMBERS = (
    ("config.json", 663, "7463bb0ea78315365e6c6b74de4e73bbcc8359dfb0c5a737584e077d42c0b03c"),
    (
        "tokenizer_config.json",
        7_305,
        "5b5d4f65d0acd3b2d56a35b56d374a36cbc1c8fa5cf3b3febbbfabf22f359583",
    ),
    (
        "tokenizer.json",
        7_031_645,
        "c0382117ea329cdf097041132f6d735924b697924d6f6fc3945713e96ce87539",
    ),
    (
        "merges.txt",
        1_671_839,
        "599bab54075088774b1733fde865d5bd747cbcc7a547c5bc12610e874e26f5e3",
    ),
    (
        "vocab.json",
        2_776_833,
        "ca10d7e9fb3ed18575dd1e277a2579c16d108e32f27439684afa0e10b1440910",
    ),
)
UNBOUND_SIDECARS = (
    "chat_template.jinja",
    "chat_templates",
    "special_tokens_map.json",
    "added_tokens.json",
)
TEMPLATE_SHA256 = "cd8e9439f0570856fd70470bf8889ebd8b5d1107207f67a5efb46e342330527f"
TEMPLATE_BYTES = 2_507
CHAT_SUFFIX = "<|im_end|>\n"
SUFFIX_TOKEN_IDS = [151645, 198]
SOFTWARE_PACKAGES = ("transformers", "tokenizers", "jinja2", "huggingface-hub")
LOAD_POLICY = {
    "local_files_only": True,
    "token": False,
    "trust_remote_code": False,
    "use_fast": True,
}
MASK_POLICY = "original_assistant_content_only; prompt/header/EOS/suffix/padding=-100"


def _read(path: Path, code: str) -> bytes:
    try:
        return path.read_bytes()
    except OSError as error:
        raise TrainingPreflightError(code) from error


def _json_object(data: bytes, code: str) -> dict[str, Any]:
    try:
        value = json.loads(data)
    except (ValueError, UnicodeError) as error:
        raise TrainingPreflightError(code) from error
    require(isinstance(value, dict), code)
    return dict(value)


def _software_versions() -> dict[str, str]:
    try:
        return {name: metadata.version(name) for name in SOFTWARE_PACKAGES}
    except metadata.PackageNotFoundError as error:
        raise TrainingPreflightError("tokenizer.software_unavailable") from error


def _read_members(directory: Path) -> tuple[list[dict[str, Any]], dict[str, bytes]]:
    require(directory.is_dir(), "tokenizer.local_directory")
    for name in UNBOUND_SIDECARS:
        candidate = directory / name
        require(
            not candidate.exists() and not candidate.is_symlink(),
            "tokenizer.unbound_sidecar",
        )
    members = []
    contents = {}
    for name, byte_count, digest in TOKENIZER_MEMBERS:
        data = _read(directory / name, "tokenizer.file_missing")
        require(
            len(data) == byte_count and sha(data) == digest,
            "tokenizer.file_content",
        )
        members.append({"relative_path": name, "byte_count": len(data), "sha256": sha(data)})
        contents[name] = data
    return members, contents


def _configuration_reference(repo_root: Path) -> dict[str, Any]:
    path = repo_root / SOURCE_CONFIGURATION
    raw = _read(path, "tokenizer.student_configuration_missing")
    require(
        len(raw) == SOURCE_CONFIGURATION_BYTES and sha(raw) == SOURCE_CONFIGURATION_SHA256,
        "tokenizer.student_configuration_content",
    )
    payload = _json_object(raw, "tokenizer.student_configuration_invalid")
    expected = {
        "base_model": str(MODEL_DIRECTORY),
        "model_revision": MODEL_REVISION,
        "max_seq_length": MAX_SEQUENCE_LENGTH,
        "max_new_tokens": 1_536,
    }
    selected = {name: payload.get(name) for name in expected}
    require(selected == expected, "tokenizer.student_configuration_fields")
    return {
        "relative_path": SOURCE_CONFIGURATION,
        "absolute_path": str(path.resolve()),
        "sha256": sha(raw),
        "byte_count": len(raw),
        "selected_fields": selected,
        "historical_training_configuration_is_new_training_authorization": False,
    }


def _load_local(directory: Path) -> Any:
    from transformers import AutoTokenizer

    return AutoTokenizer.from_pretrained(str(directory), **LOAD_POLICY)


def _binding_and_tokenizer(repo_root: Path, directory: Path) -> tuple[dict[str, Any], Any]:
    directory = directory.resolve()
    configuration = _configuration_reference(repo_root.resolve())
    members, contents = _read_members(directory)
    config = _json_object(contents["config.json"], "tokenizer.model_config_invalid")
    token_config = _json_object(contents["tokenizer_config.json"], "tokenizer.config_invalid")
    template = token_config.get("chat_template")
    require(isinstance(template, str), "tokenizer.template_missing")
    assert isinstance(template, str)
    require(
        len(template.encode("utf-8")) == TEMPLATE_BYTES
        and sha(template.encode("utf-8")) == TEMPLATE_SHA256,
        "tokenizer.template_content",
    )
    require(
        config.get("max_position_embeddings") == 32_768
        and config.get("rope_scaling") is None
        and MAX_SEQUENCE_LENGTH <= config["max_position_embeddings"],
        "tokenizer.model_context_limit",
    )
    require(token_config.get("model_max_length") == 131_072, "tokenizer.declared_context")
    versions = _software_versions()
    tokenizer = _load_local(directory)
    require(tokenizer.is_fast is True, "tokenizer.fast_required")
    require(tokenizer.chat_template == template, "tokenizer.template_runtime")
    require(
        type(tokenizer).__name__ == "Qwen2Tokenizer"
        and tokenizer.eos_token_id == 151645
        and tokenizer.pad_token_id == 151643
        and tokenizer.bos_token_id is None
        and tokenizer.model_max_length == 131_072,
        "tokenizer.runtime_identity",
    )
    require(
        tokenizer(CHAT_SUFFIX, add_special_tokens=False)["input_ids"] == SUFFIX_TOKEN_IDS,
        "tokenizer.suffix_identity",
    )
    # Detect file or template replacement during loading; no original is rewritten.
    after_members, _ = _read_members(directory)
    require(after_members == members, "tokenizer.changed_during_loading")
    binding = record(
        "tokenizer_binding",
        directory=str(directory),
        model_name="Qwen/Qwen2.5-7B-Instruct",
        model_revision=MODEL_REVISION,
        revision_authority="existing local Student configuration and content-bound files",
        remote_revision_independently_verified=False,
        source_configuration=configuration,
        members=members,
        member_count=len(members),
        member_bytes=sum(item["byte_count"] for item in members),
        chat_template=template,
        chat_template_sha256=TEMPLATE_SHA256,
        chat_template_byte_count=TEMPLATE_BYTES,
        tokenizer_class=type(tokenizer).__name__,
        backend_class=type(tokenizer.backend_tokenizer).__name__,
        is_fast=tokenizer.is_fast,
        software_versions=versions,
        maximum_sequence_length=MAX_SEQUENCE_LENGTH,
        model_max_position_embeddings=config["max_position_embeddings"],
        model_rope_scaling=config.get("rope_scaling"),
        model_max_length_declared=tokenizer.model_max_length,
        tokenizer_declared_limit_is_model_context_authority=False,
        model_config_transformers_version=config.get("transformers_version"),
        bos_token_id=tokenizer.bos_token_id,
        eos_token_id=tokenizer.eos_token_id,
        pad_token_id=tokenizer.pad_token_id,
        chat_suffix=CHAT_SUFFIX,
        suffix_token_ids=SUFFIX_TOKEN_IDS,
        load_policy=LOAD_POLICY,
        mask_policy=MASK_POLICY,
        automatic_assistant_mask_used=False,
        weights_are_members=False,
        language_model_loaded=False,
        student_training_authorized=False,
        gpu_execution_required=False,
    )
    return binding, tokenizer


def register_tokenizer(repo_root: Path, directory: Path | None = None) -> dict[str, Any]:
    """Bind the existing five metadata files; never download or load weights."""
    binding, _ = _binding_and_tokenizer(repo_root, directory or MODEL_DIRECTORY)
    return binding


def load_tokenizer(binding: dict[str, Any]) -> Any:
    """Recheck the local files, exact template, configuration and software."""
    require(isinstance(binding, dict), "tokenizer.binding_shape")
    require(
        record(
            "tokenizer_binding",
            **{key: value for key, value in binding.items() if key not in {"id", "schema_version"}},
        )
        == binding,
        "tokenizer.binding_identity",
    )
    require(
        isinstance(binding.get("source_configuration"), dict)
        and isinstance(binding["source_configuration"].get("absolute_path"), str)
        and isinstance(binding.get("directory"), str),
        "tokenizer.binding_shape",
    )
    configuration_path = Path(binding["source_configuration"]["absolute_path"])
    require(
        configuration_path.is_absolute() and len(configuration_path.parents) >= 3,
        "tokenizer.configuration_path",
    )
    repo_root = configuration_path.parents[2]
    require(
        configuration_path == repo_root / SOURCE_CONFIGURATION,
        "tokenizer.configuration_path",
    )
    directory = Path(binding["directory"])
    require(directory.is_absolute(), "tokenizer.local_directory")
    current, tokenizer = _binding_and_tokenizer(repo_root, directory)
    require(current == binding, "tokenizer.binding_drift")
    return tokenizer


def _validate_row(row: dict[str, Any]) -> None:
    require(isinstance(row, dict), "tokenization.row_shape")
    require(
        all(isinstance(row.get(key), str) and row[key] for key in ("id", "session_id", "state_id")),
        "tokenization.row_identity",
    )
    messages = row.get("messages")
    require(
        isinstance(messages, list)
        and len(messages) == 2
        and all(
            isinstance(message, dict)
            and set(message) == {"role", "content"}
            and isinstance(message["content"], str)
            for message in messages
        )
        and [message["role"] for message in messages] == ["system", "user"],
        "tokenization.original_message_shape",
    )
    require(
        isinstance(row.get("target_text"), str) and bool(row["target_text"]),
        "tokenization.target_text",
    )


def _tokenize_row(row: dict[str, Any], binding: dict[str, Any], tokenizer: Any) -> dict[str, Any]:
    _validate_row(row)
    messages = row["messages"]
    target = row["target_text"]
    prefix = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    full = tokenizer.apply_chat_template(
        [*messages, {"role": "assistant", "content": target}],
        tokenize=False,
        add_generation_prompt=False,
    )
    require(full == prefix + target + CHAT_SUFFIX, "tokenization.rendered_content_changed")
    start = len(prefix)
    end = start + len(target)
    prefix_ids = tokenizer(prefix, add_special_tokens=False, truncation=False, padding=False)[
        "input_ids"
    ]
    encoded = tokenizer(
        full,
        add_special_tokens=False,
        truncation=False,
        padding=False,
        return_attention_mask=True,
        return_offsets_mapping=True,
    )
    input_ids = encoded["input_ids"]
    offsets = encoded["offset_mapping"]
    require(
        len(input_ids) <= MAX_SEQUENCE_LENGTH,
        "tokenization.sequence_limit",
    )
    require(input_ids[: len(prefix_ids)] == prefix_ids, "tokenization.prefix_token_mismatch")
    require(
        len(offsets) == len(input_ids)
        and all(0 <= left <= right <= len(full) for left, right in offsets),
        "tokenization.offset_shape",
    )
    require(
        not any(left < start < right or left < end < right for left, right in offsets),
        "tokenization.boundary_crossing",
    )
    selected = [
        index for index, (left, right) in enumerate(offsets) if start <= left < right <= end
    ]
    require(bool(selected) and selected[0] > 0, "tokenization.no_causal_target")
    require(
        selected == list(range(len(prefix_ids), len(prefix_ids) + len(selected))),
        "tokenization.target_token_interval",
    )
    target_start = selected[0]
    target_end = selected[-1] + 1
    target_offsets = offsets[target_start:target_end]
    require(
        target_offsets[0][0] == start
        and target_offsets[-1][1] == end
        and all(
            target_offsets[index - 1][1] == target_offsets[index][0]
            for index in range(1, len(target_offsets))
        ),
        "tokenization.target_offset_partition",
    )
    target_ids = input_ids[target_start:target_end]
    require(
        not set(target_ids).intersection(tokenizer.all_special_ids),
        "tokenization.special_token_inside_target",
    )
    decoded = tokenizer.decode(
        target_ids, skip_special_tokens=False, clean_up_tokenization_spaces=False
    )
    require(decoded.encode("utf-8") == target.encode("utf-8"), "tokenization.target_decode")
    require(input_ids[target_end:] == SUFFIX_TOKEN_IDS, "tokenization.suffix_tokens")
    attention_mask = encoded["attention_mask"]
    require(attention_mask == [1] * len(input_ids), "tokenization.unexpected_padding")
    mask = [int(target_start <= index < target_end) for index in range(len(input_ids))]
    labels = [token if mask[index] else -100 for index, token in enumerate(input_ids)]
    return record(
        "tokenized_row",
        row_id=row["id"],
        session_id=row["session_id"],
        state_id=row["state_id"],
        tokenizer_binding_id=binding["id"],
        input_ids=input_ids,
        attention_mask=attention_mask,
        labels=labels,
        target_mask=mask,
        sequence_length=len(input_ids),
        prompt_token_count=len(prefix_ids),
        target_token_count=len(selected),
        suffix_token_count=len(input_ids) - target_end,
        target_token_start=target_start,
        target_token_end=target_end,
        rendered_sha256=sha(full.encode("utf-8")),
        rendered_byte_count=len(full.encode("utf-8")),
        target_raw_sha256=sha(target.encode("utf-8")),
        target_character_start=start,
        target_character_end=end,
        truncated=False,
        boundary_checks={
            "full_render_is_exact_prefix_content_suffix": True,
            "original_content_utf8_bytes_preserved": True,
            "full_token_prefix_equals_prompt_tokens": True,
            "no_token_crosses_content_boundaries": True,
            "content_offsets_partition_exact_character_interval": True,
            "content_tokens_decode_to_original_utf8_bytes": True,
            "content_token_interval_is_contiguous": True,
            "prompt_and_role_header_have_zero_target_mask": True,
            "eos_and_suffix_have_zero_target_mask": True,
            "padding_is_absent_before_collation": True,
            "all_target_positions_have_causal_predecessor": True,
            "no_truncation": True,
        },
    )


def tokenize_rows(rows: list[dict[str, Any]], binding: dict[str, Any]) -> list[dict[str, Any]]:
    """Return unpadded, content-only causal-LM rows without rewriting inputs."""
    require(isinstance(rows, list) and bool(rows), "tokenization.empty_rows")
    for row in rows:
        _validate_row(row)
    require(len({row["id"] for row in rows}) == len(rows), "tokenization.duplicate_rows")
    tokenizer = load_tokenizer(binding)
    tokenized = [_tokenize_row(row, binding, tokenizer) for row in rows]
    require(tokenizer.chat_template == binding["chat_template"], "tokenizer.template_runtime")
    current_members, _ = _read_members(Path(binding["directory"]))
    require(current_members == binding["members"], "tokenizer.changed_during_tokenization")
    return tokenized
