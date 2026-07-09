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
        with config_path.open("r", encoding="utf-8") as f:
            config = _deep_merge(config, json.load(f))

    base_dir = DEFAULT_CONFIG_PATH.resolve().parents[1]
    secrets_path = DEFAULT_CONFIG_PATH.parent / "local_secrets.json"
    if secrets_path.exists():
        with secrets_path.open("r", encoding="utf-8") as f:
            config = _deep_merge(config, json.load(f))

    for key in ("storage_root", "metadata_db"):
        value = Path(config[key])
        if not value.is_absolute():
            config[key] = str((base_dir / value).resolve())
    return config


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged
