from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import date
from decimal import Decimal
from typing import Any

from trusted_synthesis.core.evidence.schema import (
    DefinitionRef,
    EntityRef,
    EvidenceItem,
    EvidenceStatus,
    PropertyRef,
    ProvenanceRef,
    SourceAuthority,
    SourceRef,
    TimeRef,
)
from trusted_synthesis.domains.finance.schema import FinanceArchiveConfig


class FinanceArchiveError(RuntimeError):
    pass


class FinanceArchiveAdapter:
    adapter_id = "finance_archive.v1"
    domain = "finance"

    _catalog_files = {
        "entities": "canonical_entities.parquet",
        "metrics": "metrics.parquet",
        "sources": "source_registry.parquet",
        "definitions": "source_metric_definitions.parquet",
    }

    def __init__(self, config: FinanceArchiveConfig):
        self.config = config
        self._report: dict[str, Any] | None = None
        self._catalogs: dict[str, dict[str, dict[str, Any]]] | None = None

    def inspect(self) -> dict[str, Any]:
        paths = {
            "archive_root": self.config.archive_root,
            "kg_nodes": self.config.kg_nodes_path,
            "kg_edges": self.config.kg_edges_path,
            "kg_report": self.config.kg_report_path,
            **{
                f"catalog_{name}": self.config.catalog_root / filename
                for name, filename in self._catalog_files.items()
            },
        }
        existence = {name: path.exists() for name, path in paths.items()}
        errors = [f"missing:{name}" for name, exists in existence.items() if not exists]
        report = self._load_report() if self.config.kg_report_path.exists() else {}
        quality = report.get("quality") or {}
        graph_schema_version = str(quality.get("graph_schema_version") or "")
        if report.get("kg_build_id") != self.config.required_kg_build_id:
            errors.append("kg_build_id_mismatch")
        if quality.get("kg_quality_gate_status") != "passed":
            errors.append("kg_quality_gate_not_passed")
        if graph_schema_version != self.config.required_graph_schema_version:
            errors.append("graph_schema_version_mismatch")
        return {
            "adapter_id": self.adapter_id,
            "domain": self.domain,
            "archive_root": str(self.config.archive_root),
            "read_only": True,
            "paths": {name: str(path) for name, path in paths.items()},
            "path_exists": existence,
            "kg_build_id": report.get("kg_build_id"),
            "graph_schema_version": graph_schema_version or None,
            "quality_gate_status": quality.get("kg_quality_gate_status"),
            "fact_node_count": quality.get("fact_node_count"),
            "derived_fact_node_count": quality.get("derived_fact_node_count"),
            "node_count": quality.get("node_count"),
            "edge_count": quality.get("edge_count"),
            "compatible": not errors,
            "errors": errors,
        }

    def iter_evidence(self, *, limit: int | None = None) -> Iterator[EvidenceItem]:
        inspection = self.inspect()
        if not inspection["compatible"]:
            raise FinanceArchiveError(f"Finance archive is incompatible: {inspection['errors']}")
        if limit is not None and limit < 1:
            raise ValueError("limit must be positive")
        report = self._load_report()
        catalogs = self._load_catalogs()
        emitted = 0
        with self.config.kg_nodes_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                row = json.loads(line)
                if row.get("node_type") != "Fact" or not row.get("is_active", 1):
                    continue
                item = self._map_fact_node(row, report, catalogs)
                if item is None:
                    continue
                yield item
                emitted += 1
                if limit is not None and emitted >= limit:
                    return

    def _map_fact_node(
        self,
        row: dict[str, Any],
        report: dict[str, Any],
        catalogs: dict[str, dict[str, dict[str, Any]]],
    ) -> EvidenceItem | None:
        properties = row.get("properties") or {}
        if row.get("kg_build_id") != self.config.required_kg_build_id:
            raise FinanceArchiveError(
                f"Fact node belongs to unexpected KG build: {row.get('kg_build_id')}"
            )
        status = str(properties.get("verification_status") or "")
        if status not in self.config.accepted_verification_statuses:
            return None
        if properties.get("graph_ready_reason") != "ready":
            return None
        if self.config.exclude_forecasts and bool(properties.get("is_forecast")):
            return None
        entity_id = str(properties["entity_id"])
        metric_id = str(properties["metric_id"])
        source_id = str(properties["source_id"])
        definition_id = str(properties.get("source_definition_id") or "")
        entity = catalogs["entities"].get(entity_id, {})
        metric = catalogs["metrics"].get(metric_id, {})
        source = catalogs["sources"].get(source_id, {})
        definition = catalogs["definitions"].get(definition_id, {})
        kg_build_id = str(row["kg_build_id"])
        period_end = _date(properties.get("period_end"))
        period_start = _date(properties.get("period_start"))
        return EvidenceItem(
            evidence_id=(
                f"evidence:finance:{properties['stable_fact_id']}@{self.config.required_kg_build_id}"
            ),
            domain=self.domain,
            entity=EntityRef(
                entity_id=entity_id,
                name=str(entity.get("canonical_name") or entity_id),
                entity_type=str(entity.get("entity_type") or "unknown"),
                market=_optional(entity.get("market")),
                country=_optional(entity.get("country")),
            ),
            property=PropertyRef(
                property_id=metric_id,
                name=str(metric.get("canonical_name") or metric_id),
                category=_optional(metric.get("metric_category")),
                period_type=_optional(
                    properties.get("metric_period_type") or metric.get("period_type")
                ),
            ),
            value=Decimal(str(properties["normalized_value"])),
            unit=_optional(properties.get("normalized_unit")),
            currency=_optional(properties.get("normalized_currency")),
            time=TimeRef(
                label=_time_label(properties, period_end),
                start=period_start,
                end=period_end,
                basis=_optional(properties.get("time_basis")),
                frequency=_optional(properties.get("frequency")),
            ),
            source=SourceRef(
                source_id=source_id,
                name=str(source.get("source_name") or source_id),
                authority=_authority(source.get("authority_level")),
                provider=_optional(source.get("provider")),
                uri=_optional(source.get("base_url")),
                license_note=_optional(source.get("license_note")),
            ),
            definition=DefinitionRef(
                definition_id=definition_id or None,
                text=_optional(definition.get("definition_text")),
                comparability_level=_optional(properties.get("comparability_level")),
                vintage_policy=_optional(properties.get("vintage_policy")),
            ),
            provenance=ProvenanceRef(
                adapter_id=self.adapter_id,
                archive_id=f"finance_kg:{kg_build_id}",
                source_record_id=str(properties["fact_id"]),
                raw_object_id=_optional(properties.get("raw_object_id")),
                build_ids={
                    "kg": kg_build_id,
                    "standardized_fact": str(properties.get("build_id") or "unknown"),
                    "kg_input_fact": str(
                        (report.get("quality") or {}).get("input_fact_build_id") or "unknown"
                    ),
                },
                extraction_method="archived_graph_ready_fact",
            ),
            status=EvidenceStatus.ACCEPTED,
            confidence=float(properties.get("confidence_score") or 0),
            attributes={
                "verification_status": status,
                "source_definition_id": definition_id or None,
                "semantic_equivalence_group_id": properties.get("semantic_equivalence_group_id"),
                "raw_equivalence_group_id": properties.get("raw_equivalence_group_id"),
                "financial_scope_type": properties.get("financial_scope_type"),
                "fiscal_year": properties.get("fiscal_year"),
                "fiscal_quarter": properties.get("fiscal_quarter"),
                "calendar_year": properties.get("calendar_year"),
                "value_scale": properties.get("value_scale"),
            },
        )

    def _load_report(self) -> dict[str, Any]:
        if self._report is None:
            self._report = json.loads(self.config.kg_report_path.read_text(encoding="utf-8"))
        return self._report

    def _load_catalogs(self) -> dict[str, dict[str, dict[str, Any]]]:
        if self._catalogs is not None:
            return self._catalogs
        try:
            import pyarrow.parquet as pq
        except ImportError as exc:
            raise FinanceArchiveError(
                "Finance archive catalogs require the optional pyarrow dependency"
            ) from exc
        keys = {
            "entities": "entity_id",
            "metrics": "metric_id",
            "sources": "source_id",
            "definitions": "definition_id",
        }
        self._catalogs = {}
        for name, filename in self._catalog_files.items():
            rows = pq.read_table(self.config.catalog_root / filename).to_pylist()
            self._catalogs[name] = {
                str(row[keys[name]]): row for row in rows if row.get(keys[name]) is not None
            }
        return self._catalogs


def _authority(value: Any) -> SourceAuthority:
    normalized = str(value or "").casefold()
    if normalized.startswith("s1") or "official" in normalized:
        return SourceAuthority.OFFICIAL
    if normalized.startswith("s2") or "database" in normalized:
        return SourceAuthority.CURATED_DATABASE
    return SourceAuthority.SECONDARY_WEB


def _date(value: Any) -> date | None:
    if value in (None, ""):
        return None
    return date.fromisoformat(str(value)[:10])


def _optional(value: Any) -> str | None:
    return None if value in (None, "") else str(value)


def _time_label(properties: dict[str, Any], period_end: date | None) -> str:
    fiscal_year = properties.get("fiscal_year")
    fiscal_quarter = properties.get("fiscal_quarter")
    if fiscal_year and fiscal_quarter:
        return f"FY{fiscal_year} {fiscal_quarter}"
    if fiscal_year:
        return f"FY{fiscal_year}"
    return period_end.isoformat() if period_end else "unspecified period"
