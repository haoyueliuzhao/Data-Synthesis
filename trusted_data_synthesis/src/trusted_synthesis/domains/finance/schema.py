from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field


class FinanceArchiveConfig(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    adapter_version: str
    archive_root: Path
    legacy_archive_roots: tuple[Path, ...] = ()
    kg_nodes_path: Path
    kg_edges_path: Path
    kg_report_path: Path
    catalog_root: Path
    exclude_forecasts: bool = True
    accepted_verification_statuses: tuple[str, ...] = Field(min_length=1)
    required_kg_build_id: str
    required_graph_schema_version: str

    @classmethod
    def from_json(cls, path: str | Path) -> FinanceArchiveConfig:
        config_path = Path(path).resolve()
        payload = json.loads(config_path.read_text(encoding="utf-8"))
        archive_root = (config_path.parent / payload["archive_root"]).resolve()
        payload["archive_root"] = archive_root
        legacy_roots = []
        for value in payload.get("legacy_archive_roots", ()):
            legacy_root = Path(value).expanduser()
            if not legacy_root.is_absolute():
                legacy_root = config_path.parent / legacy_root
            legacy_roots.append(legacy_root.resolve())
        payload["legacy_archive_roots"] = legacy_roots
        for field in ("kg_nodes_path", "kg_edges_path", "kg_report_path", "catalog_root"):
            payload[field] = (archive_root / payload[field]).resolve()
        return cls.model_validate(payload)
