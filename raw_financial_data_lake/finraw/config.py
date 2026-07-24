from __future__ import annotations

import json
from pathlib import Path
from typing import Any


DEFAULT_CONFIG_PATH = Path(__file__).resolve().parents[1] / "config" / "default_config.json"


def load_config(path: str | None = None) -> dict[str, Any]:
    with DEFAULT_CONFIG_PATH.open("r", encoding="utf-8") as f:
        config = json.load(f)

    config_path = Path(path) if path else DEFAULT_CONFIG_PATH
    if path:
        config = _deep_merge(config, _load_profile(config_path.resolve(), set()))

    base_dir = DEFAULT_CONFIG_PATH.resolve().parents[1]
    secrets_path = DEFAULT_CONFIG_PATH.parent / "local_secrets.json"
    if secrets_path.exists():
        with secrets_path.open("r", encoding="utf-8") as f:
            config = _deep_merge(config, json.load(f))

    config = _strip_replace_markers(config)
    for key in ("storage_root", "metadata_db"):
        value = Path(config[key])
        if not value.is_absolute():
            config[key] = str((base_dir / value).resolve())
    return config


def _load_profile(path: Path, loading: set[Path]) -> dict[str, Any]:
    if path in loading:
        chain = " -> ".join(str(item) for item in [*loading, path])
        raise ValueError(f"Cyclic config extends chain: {chain}")
    with path.open("r", encoding="utf-8") as f:
        payload = json.load(f)
    extends = payload.pop("extends", None)
    if not extends:
        return payload
    parent_path = Path(str(extends))
    if not parent_path.is_absolute():
        parent_path = (path.parent / parent_path).resolve()
    loading.add(path)
    try:
        parent = _load_profile(parent_path, loading)
    finally:
        loading.remove(path)
    return _deep_merge(parent, payload)


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    if override.get("__replace__") is True:
        return dict(override)
    merged = dict(base)
    for key, value in override.items():
        if key == "__replace__":
            continue
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _strip_replace_markers(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: _strip_replace_markers(item)
            for key, item in value.items()
            if key != "__replace__"
        }
    if isinstance(value, list):
        return [_strip_replace_markers(item) for item in value]
    return value
