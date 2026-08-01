from __future__ import annotations

import json
from pathlib import Path

from pydantic import ValidationError

from trusted_synthesis.core.vtdo.round import VTDORoundArtifact


def load_vtdo_round_artifacts(
    sources: tuple[Path, ...],
) -> tuple[tuple[VTDORoundArtifact, ...], tuple[str, ...]]:
    """Load frozen rounds from files or directories under one fail-closed contract."""

    rounds: list[VTDORoundArtifact] = []
    blockers: list[str] = []
    for source in sources:
        paths = tuple(sorted(source.glob("*.json*"))) if source.is_dir() else (source,)
        if not paths or any(not path.is_file() for path in paths):
            blockers.append(f"missing_round_artifact_source:{source}")
            continue
        for path in paths:
            try:
                payloads = _read_json_records(path)
            except (OSError, json.JSONDecodeError) as error:
                blockers.append(f"unreadable_round_artifact:{path.name}:{type(error).__name__}")
                continue
            for index, payload in enumerate(payloads):
                try:
                    rounds.append(VTDORoundArtifact.model_validate(payload))
                except ValidationError:
                    blockers.append(f"invalid_round_artifact:{path.name}:{index}")
    if not rounds and not blockers:
        blockers.append("vtdo_round_artifacts_empty")
    return tuple(rounds), tuple(sorted(set(blockers)))


def _read_json_records(path: Path) -> tuple[object, ...]:
    if path.suffix == ".jsonl":
        return tuple(
            json.loads(line)
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        )
    value = json.loads(path.read_text(encoding="utf-8"))
    return tuple(value) if isinstance(value, list) else (value,)
