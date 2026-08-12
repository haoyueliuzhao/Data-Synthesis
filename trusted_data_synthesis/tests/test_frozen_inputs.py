from __future__ import annotations

import hashlib

import pytest

from trusted_synthesis.experiments.vtdo_experiment.phase1_frozen_inputs import (
    resolve_frozen_input,
)


def _digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def test_frozen_input_prefers_an_unchanged_original(tmp_path) -> None:
    payload = b"immutable population"
    original = tmp_path / "population.json"
    original.write_bytes(payload)

    assert resolve_frozen_input(original, _digest(payload)) == original.resolve()


def test_frozen_input_uses_a_content_addressed_mirror_when_original_is_absent(
    tmp_path,
) -> None:
    payload = b"mirrored population"
    digest = _digest(payload)
    mirror = tmp_path / "mirror"
    mirror.mkdir()
    (mirror / digest).write_bytes(payload)

    resolved = resolve_frozen_input(
        tmp_path / "missing.json",
        digest,
        mirror_roots=(mirror,),
    )

    assert resolved == (mirror / digest).resolve()


def test_changed_original_cannot_fall_back_to_a_valid_mirror(tmp_path) -> None:
    payload = b"expected population"
    digest = _digest(payload)
    original = tmp_path / "population.json"
    original.write_bytes(b"changed population")
    mirror = tmp_path / "mirror"
    mirror.mkdir()
    (mirror / digest).write_bytes(payload)

    with pytest.raises(ValueError, match="frozen input changed"):
        resolve_frozen_input(original, digest, mirror_roots=(mirror,))
