"""Local tokenizer-only checks over saved admitted requests, never Student training."""

from __future__ import annotations

import copy
import json
import shutil
import socket
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import pytest

from trusted_synthesis.experiments.qa_reasoning_share_training_preflight import models
from trusted_synthesis.experiments.qa_reasoning_share_training_preflight import (
    tokenization as tokens,
)

ROOT = Path(__file__).resolve().parents[2]
EXPECTED_TARGETS = {"M02": 2_812, "M03": 4_691, "M04": 2_793, "M05": 2_817, "M06": 2_826}


@pytest.fixture(scope="module")
def originals() -> dict[Path, str]:
    paths = [tokens.MODEL_DIRECTORY / name for name, _, _ in tokens.TOKENIZER_MEMBERS]
    paths.append(ROOT / tokens.SOURCE_CONFIGURATION)
    for parent in (models.PILOT_PARENT, models.QUOTIENT_PARENT):
        paths.extend(path for path in (ROOT / parent).rglob("*") if path.is_file())
    snapshots = {path: models.sha(path.read_bytes()) for path in paths}
    yield snapshots
    assert {path: models.sha(path.read_bytes()) for path in paths} == snapshots


@pytest.fixture(scope="module")
def binding(originals: dict[Path, str]) -> dict[str, Any]:
    def forbidden(*args: Any, **kwargs: Any) -> Any:
        pytest.fail("tokenizer-only checks must not access a network or load model weights")

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(socket, "create_connection", forbidden)
        patch.setattr(socket, "getaddrinfo", forbidden)
        from transformers import AutoTokenizer

        original_loader = AutoTokenizer.from_pretrained
        calls = []

        def local_only(path: str, **kwargs: Any) -> Any:
            calls.append((path, kwargs))
            assert kwargs == {
                "local_files_only": True,
                "token": False,
                "trust_remote_code": False,
                "use_fast": True,
            }
            return original_loader(path, **kwargs)

        patch.setattr(AutoTokenizer, "from_pretrained", local_only)
        result = tokens.register_tokenizer(ROOT)
    assert len(calls) == 1
    return result


@pytest.fixture(scope="module")
def rows(originals: dict[Path, str]) -> list[dict[str, Any]]:
    """Read actual Receipt eligibility; do not manufacture a 27-row fixture."""
    parent = ROOT / models.PILOT_PARENT
    quotient = ROOT / models.QUOTIENT_PARENT
    result = []
    for audit_path in sorted((parent / "online_reports").glob("M*.json")):
        audit = json.loads(audit_path.read_bytes())
        if not audit["qualified"]:
            continue
        label = audit_path.stem
        assignment = json.loads((quotient / "assignments" / f"{label}.json").read_bytes())
        turns = parent / "online" / label / "turns"
        for receipt_path in sorted(turns.glob("*_receipt.json")):
            receipt = json.loads(receipt_path.read_bytes())
            if not receipt["admitted"]:
                continue
            prefix = receipt_path.name.split("_", 1)[0]
            provider_request = json.loads((turns / f"{prefix}_provider_request.json").read_bytes())
            provider_response = json.loads(
                (turns / f"{prefix}_provider_response.json").read_bytes()
            )
            submission = json.loads((turns / f"{prefix}_submission.json").read_bytes())
            body = json.loads(provider_request["body_json"])
            raw = submission["raw_public_json"]
            assert models.sha(raw.encode()) == provider_response["public_content_sha256"]
            assert len(raw.encode()) == provider_response["public_content_bytes"]
            assert submission["id"] == receipt["submission_id"]
            result.append(
                models.record(
                    "tokenizer_test_source_row",
                    session_id=assignment["session_id"],
                    state_id=assignment["state_id"],
                    messages=body["messages"],
                    target_text=raw,
                    label=label,
                    turn_index=int(prefix),
                    source_submission_id=submission["id"],
                )
            )
    return result


@pytest.fixture(scope="module")
def encoded(rows: list[dict[str, Any]], binding: dict[str, Any]) -> list[dict[str, Any]]:
    original_rows = copy.deepcopy(rows)
    result = tokens.tokenize_rows(rows, binding)
    assert rows == original_rows
    return result


def _copied_directory(tmp_path: Path) -> Path:
    directory = tmp_path / "tokenizer"
    directory.mkdir()
    for name, _, _ in tokens.TOKENIZER_MEMBERS:
        shutil.copyfile(tokens.MODEL_DIRECTORY / name, directory / name)
    return directory


def _reidentify(binding: dict[str, Any]) -> dict[str, Any]:
    return models.record(
        "tokenizer_binding",
        **{key: value for key, value in binding.items() if key not in {"id", "schema_version"}},
    )


def test_exact_existing_tokenizer_binding_does_not_inherit_training_authority(
    binding: dict[str, Any],
) -> None:
    assert binding["model_revision"] == tokens.MODEL_REVISION
    assert binding["directory"] == str(tokens.MODEL_DIRECTORY.resolve())
    assert binding["member_count"] == 5 and binding["member_bytes"] == 11_488_285
    assert binding["members"] == [
        {"relative_path": name, "byte_count": size, "sha256": digest}
        for name, size, digest in tokens.TOKENIZER_MEMBERS
    ]
    assert binding["chat_template_byte_count"] == 2_507
    assert models.sha(binding["chat_template"].encode()) == tokens.TEMPLATE_SHA256
    assert binding["maximum_sequence_length"] == 24_576
    assert binding["model_max_position_embeddings"] == 32_768
    assert binding["model_max_length_declared"] == 131_072
    assert binding["tokenizer_declared_limit_is_model_context_authority"] is False
    assert set(binding["source_configuration"]["selected_fields"]) == {
        "base_model",
        "model_revision",
        "max_seq_length",
        "max_new_tokens",
    }
    assert binding["source_configuration"]["sha256"] == tokens.SOURCE_CONFIGURATION_SHA256
    assert binding["source_configuration"]["byte_count"] == 855
    assert binding["software_versions"] == tokens._software_versions()
    assert binding["is_fast"] is True
    assert binding["automatic_assistant_mask_used"] is False
    assert binding["language_model_loaded"] is False
    assert binding["weights_are_members"] is False
    assert binding["student_training_authorized"] is False
    assert binding["gpu_execution_required"] is False


def test_real_admitted_pool_has_27_rows_exact_lengths_and_trajectory_token_totals(
    rows: list[dict[str, Any]], encoded: list[dict[str, Any]]
) -> None:
    assert len(rows) == len(encoded) == 27
    assert Counter(json.loads(row["target_text"])["kind"] for row in rows) == {
        "action": 11,
        "update": 11,
        "final": 5,
    }
    assert Counter(row["label"] for row in rows) == {
        "M02": 5,
        "M03": 7,
        "M04": 5,
        "M05": 5,
        "M06": 5,
    }
    totals: dict[str, int] = defaultdict(int)
    for row, tensor_row in zip(rows, encoded, strict=True):
        assert tensor_row["row_id"] == row["id"]
        assert tensor_row["session_id"] == row["session_id"]
        assert tensor_row["state_id"] == row["state_id"]
        totals[row["label"]] += tensor_row["target_token_count"]
    assert dict(totals) == EXPECTED_TARGETS
    assert sum(totals.values()) == 15_939
    assert sum(row["prompt_token_count"] for row in encoded) == 352_876
    assert sum(row["suffix_token_count"] for row in encoded) == 54
    assert sum(row["sequence_length"] for row in encoded) == 368_869
    assert min(row["sequence_length"] for row in encoded) == 12_716
    assert max(row["sequence_length"] for row in encoded) == 15_110


def test_masks_supervise_only_exact_content_and_exclude_header_prompt_suffix_and_padding(
    rows: list[dict[str, Any]], encoded: list[dict[str, Any]], binding: dict[str, Any]
) -> None:
    tokenizer = tokens.load_tokenizer(binding)
    for source, row in zip(rows, encoded, strict=True):
        start, end = row["target_token_start"], row["target_token_end"]
        assert 0 < start < end < row["sequence_length"] <= 24_576
        assert start == row["prompt_token_count"]
        assert end - start == row["target_token_count"]
        assert row["target_mask"] == [0] * start + [1] * (end - start) + [0, 0]
        assert row["labels"] == [-100] * start + row["input_ids"][start:end] + [-100, -100]
        assert row["input_ids"][end:] == [151645, 198]
        assert row["attention_mask"] == [1] * row["sequence_length"]
        assert row["truncated"] is False
        assert all(row["boundary_checks"].values())
        assert row["target_raw_sha256"] == models.sha(source["target_text"].encode())
        assert (
            tokenizer.decode(
                row["input_ids"][start:end],
                skip_special_tokens=False,
                clean_up_tokenization_spaces=False,
            ).encode()
            == source["target_text"].encode()
        )
        assert sum(row["target_mask"][1:]) == row["target_token_count"]


def test_same_rows_and_binding_rebuild_identical_unpadded_tokens(
    rows: list[dict[str, Any]], encoded: list[dict[str, Any]], binding: dict[str, Any]
) -> None:
    assert tokens.tokenize_rows(rows, binding) == encoded


@pytest.mark.parametrize("name", [item[0] for item in tokens.TOKENIZER_MEMBERS])
def test_each_changed_local_tokenizer_member_is_rejected_without_touching_original(
    name: str, tmp_path: Path
) -> None:
    directory = _copied_directory(tmp_path)
    raw = (directory / name).read_bytes()
    (directory / name).write_bytes(b"!" + raw[1:])
    with pytest.raises(models.TrainingPreflightError, match="tokenizer.file_content"):
        tokens.register_tokenizer(ROOT, directory)


def test_loaded_tokenizer_template_drift_is_rejected(
    binding: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    tokenizer = tokens.load_tokenizer(binding)
    tokenizer.chat_template += " "
    monkeypatch.setattr(tokens, "_load_local", lambda _: tokenizer)
    with pytest.raises(models.TrainingPreflightError, match="tokenizer.template_runtime"):
        tokens.load_tokenizer(binding)


def test_software_version_drift_is_rejected(
    binding: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    changed = dict(binding["software_versions"], tokenizers="0.0.changed")
    monkeypatch.setattr(tokens, "_software_versions", lambda: changed)
    with pytest.raises(models.TrainingPreflightError, match="tokenizer.binding_drift"):
        tokens.load_tokenizer(binding)


@pytest.mark.parametrize("field", ["id", "maximum_sequence_length", "chat_template"])
def test_binding_identity_or_rehashed_contract_drift_is_rejected(
    field: str, binding: dict[str, Any]
) -> None:
    changed = copy.deepcopy(binding)
    changed[field] = "changed" if field != "maximum_sequence_length" else 131_072
    if field != "id":
        changed = _reidentify(changed)
    code = "tokenizer.binding_identity" if field == "id" else "tokenizer.binding_drift"
    with pytest.raises(models.TrainingPreflightError, match=code):
        tokens.load_tokenizer(changed)


@pytest.mark.parametrize("name", tokens.UNBOUND_SIDECARS)
def test_unbound_tokenizer_sidecar_cannot_override_frozen_metadata(
    name: str, tmp_path: Path
) -> None:
    directory = _copied_directory(tmp_path)
    (directory / name).write_text("unbound override")
    with pytest.raises(models.TrainingPreflightError, match="tokenizer.unbound_sidecar"):
        tokens.register_tokenizer(ROOT, directory)


def test_original_student_configuration_drift_is_rejected(tmp_path: Path) -> None:
    config = tmp_path / tokens.SOURCE_CONFIGURATION
    config.parent.mkdir(parents=True)
    original = (ROOT / tokens.SOURCE_CONFIGURATION).read_bytes()
    config.write_bytes(original.replace(b"24576", b"131072"))
    with pytest.raises(
        models.TrainingPreflightError, match="tokenizer.student_configuration_content"
    ):
        tokens.register_tokenizer(tmp_path)


def test_overlength_input_is_rejected_instead_of_silently_truncated(
    rows: list[dict[str, Any]], binding: dict[str, Any]
) -> None:
    row = copy.deepcopy(rows[0])
    row["target_text"] = " x" * tokens.MAX_SEQUENCE_LENGTH
    with pytest.raises(models.TrainingPreflightError, match="tokenization.sequence_limit"):
        tokens.tokenize_rows([row], binding)


class _TokenizerMutation:
    def __init__(self, tokenizer: Any, mutation: str, character_start: int, token_start: int):
        self.tokenizer = tokenizer
        self.mutation = mutation
        self.character_start = character_start
        self.token_start = token_start

    def __getattr__(self, key: str) -> Any:
        return getattr(self.tokenizer, key)

    def apply_chat_template(self, *args: Any, **kwargs: Any) -> str:
        text = self.tokenizer.apply_chat_template(*args, **kwargs)
        if self.mutation == "render" and not kwargs.get("add_generation_prompt"):
            text += " "
        return str(text)

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        encoded = self.tokenizer(*args, **kwargs)
        if self.mutation == "prefix" and not kwargs.get("return_offsets_mapping"):
            encoded["input_ids"][-1] += 1
        if kwargs.get("return_offsets_mapping"):
            if self.mutation == "crossing":
                _, end = encoded["offset_mapping"][self.token_start]
                encoded["offset_mapping"][self.token_start] = (self.character_start - 1, end)
            if self.mutation == "padding":
                encoded["attention_mask"][-1] = 0
        return encoded

    def decode(self, *args: Any, **kwargs: Any) -> str:
        text = self.tokenizer.decode(*args, **kwargs)
        return str(text) + (" " if self.mutation == "decode" else "")


@pytest.mark.parametrize(
    ("mutation", "code"),
    [
        ("render", "tokenization.rendered_content_changed"),
        ("prefix", "tokenization.prefix_token_mismatch"),
        ("crossing", "tokenization.boundary_crossing"),
        ("decode", "tokenization.target_decode"),
        ("padding", "tokenization.unexpected_padding"),
    ],
)
def test_boundary_mask_and_render_mutations_fail_closed(
    mutation: str,
    code: str,
    rows: list[dict[str, Any]],
    encoded: list[dict[str, Any]],
    binding: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    proxy = _TokenizerMutation(
        tokens.load_tokenizer(binding),
        mutation,
        encoded[0]["target_character_start"],
        encoded[0]["target_token_start"],
    )
    monkeypatch.setattr(tokens, "load_tokenizer", lambda _: proxy)
    with pytest.raises(models.TrainingPreflightError, match=code):
        tokens.tokenize_rows([rows[0]], binding)


@pytest.mark.parametrize("mutation", ["empty", "duplicate", "roles", "empty_target"])
def test_invalid_positive_rows_are_rejected_before_tokenizer_loading(
    mutation: str,
    rows: list[dict[str, Any]],
    binding: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    selected = copy.deepcopy(rows[:1])
    if mutation == "empty":
        selected = []
    elif mutation == "duplicate":
        selected.append(copy.deepcopy(selected[0]))
    elif mutation == "roles":
        selected[0]["messages"].append({"role": "assistant", "content": "future answer"})
    else:
        selected[0]["target_text"] = ""
    monkeypatch.setattr(
        tokens, "load_tokenizer", lambda _: pytest.fail("invalid rows reached tokenizer loading")
    )
    with pytest.raises(models.TrainingPreflightError):
        tokens.tokenize_rows(selected, binding)


def test_original_parent_and_tokenizer_bytes_remain_unchanged(originals: dict[Path, str]) -> None:
    assert {path: models.sha(path.read_bytes()) for path in originals} == originals
