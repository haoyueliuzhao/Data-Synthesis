from __future__ import annotations

import re
from pathlib import Path

_IMMUTABLE_REVISION = re.compile(r"[0-9a-fA-F]{40,64}")


def validate_model_loading_contract(base_model: str, revision: str | None) -> None:
    """Fail closed for mutable remote model references."""

    local_path = Path(base_model).expanduser()
    if local_path.exists():
        if not local_path.is_dir():
            raise ValueError("local base_model must be a directory")
        return
    if not revision or not _IMMUTABLE_REVISION.fullmatch(revision):
        raise ValueError(
            "remote model loading requires an immutable 40-64 character commit revision"
        )


def validate_adapter_artifact(adapter_dir: Path) -> None:
    """Require a local Safetensors adapter before evaluation."""

    path = adapter_dir.expanduser().resolve()
    if not path.is_dir():
        raise ValueError(f"adapter directory does not exist: {path}")
    if not (path / "adapter_model.safetensors").is_file():
        raise ValueError("adapter evaluation requires adapter_model.safetensors")
