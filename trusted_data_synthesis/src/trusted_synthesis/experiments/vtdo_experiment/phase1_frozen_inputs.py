from __future__ import annotations

import hashlib
from collections.abc import Iterable
from pathlib import Path


def resolve_frozen_input(
    original_path: Path,
    expected_sha256: str,
    *,
    mirror_roots: Iterable[Path] = (),
) -> Path:
    """Resolve an immutable input without allowing a changed original to fall back."""

    original_path = original_path.resolve()
    if original_path.exists():
        if not original_path.is_file() or file_sha256(original_path) != expected_sha256:
            raise ValueError(f"frozen input changed: {original_path}")
        return original_path

    for root in mirror_roots:
        candidate = root.resolve() / expected_sha256
        if not candidate.is_file():
            continue
        if file_sha256(candidate) != expected_sha256:
            raise ValueError(f"content-addressed frozen-input mirror changed: {candidate}")
        return candidate
    raise ValueError(f"frozen input is unavailable: {original_path}")


def project_frozen_input_mirror_root(config_path: Path) -> Path:
    project_root = config_path.resolve().parent.parent
    return project_root / "artifacts" / "frozen_inputs" / "sha256"


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
