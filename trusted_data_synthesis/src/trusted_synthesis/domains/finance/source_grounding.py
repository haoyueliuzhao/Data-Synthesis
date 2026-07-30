from __future__ import annotations

import hashlib
import json
from collections import OrderedDict
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict

from trusted_synthesis.core.evidence.payloads import ScalarObservation
from trusted_synthesis.core.evidence.schema import EvidenceItem
from trusted_synthesis.hashing import canonical_hash


class SourceGroundingReport(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    evidence_id: str
    checks: dict[str, bool]
    failures: tuple[str, ...]

    @property
    def passed(self) -> bool:
        return not self.failures


class FinanceSourceGroundingVerifier:
    """Dereference archived objects and verify that their raw values support evidence."""

    verifier_id = "finance_source_grounding.v1"
    verifier_version = "1.2.0"

    def __init__(
        self,
        *,
        archive_root: Path,
        legacy_archive_roots: tuple[Path, ...] = (),
        raw_objects: dict[str, dict[str, Any]],
        cache_size: int = 16,
    ) -> None:
        self._archive_root = archive_root.resolve()
        self._legacy_archive_roots = tuple(path.resolve() for path in legacy_archive_roots)
        self._raw_objects = raw_objects
        self._cache_size = cache_size
        self._byte_cache: OrderedDict[str, bytes] = OrderedDict()
        self._payload_cache: OrderedDict[str, Any] = OrderedDict()
        self._digest_cache: dict[str, str] = {}
        self._report_cache: dict[str, SourceGroundingReport] = {}

    def verify(self, evidence: EvidenceItem) -> SourceGroundingReport:
        report_cache_key = canonical_hash(
            evidence,
            prefix="finance_source_grounding_evidence:",
        )
        cached = self._report_cache.get(report_cache_key)
        if cached is not None:
            return cached
        checks = {
            "raw_object_registered": False,
            "raw_object_source_match": False,
            "storage_uri_match": False,
            "storage_path_confined": False,
            "raw_object_exists": False,
            "content_hash_match": False,
            "source_entailment": False,
        }
        locator = evidence.source_locator
        raw_object_id = locator.raw_object_id or ""
        metadata = self._raw_objects.get(raw_object_id)
        if metadata is None:
            return self._report(evidence, checks, report_cache_key)
        checks["raw_object_registered"] = True
        checks["raw_object_source_match"] = metadata.get("source_id") == evidence.source.source_id
        storage_uri = str(metadata.get("storage_uri") or "")
        checks["storage_uri_match"] = bool(storage_uri) and locator.storage_uri == storage_uri
        path = self._resolve_storage_path(storage_uri) if storage_uri else None
        checks["storage_path_confined"] = bool(
            path is not None and path.is_relative_to(self._archive_root)
        )
        checks["raw_object_exists"] = bool(path is not None and path.is_file())
        if not checks["raw_object_exists"] or not checks["storage_path_confined"]:
            return self._report(evidence, checks, report_cache_key)
        assert path is not None
        raw_bytes = self._read_bytes(raw_object_id, path)
        digest = self._digest_cache.get(raw_object_id)
        if digest is None:
            digest = hashlib.sha256(raw_bytes).hexdigest()
            self._digest_cache[raw_object_id] = digest
        expected_hash = str(metadata.get("content_sha256") or "")
        checks["content_hash_match"] = bool(expected_hash) and digest == expected_hash
        if evidence.provenance.content_hash:
            checks["content_hash_match"] = checks["content_hash_match"] and (
                evidence.provenance.content_hash == expected_hash
            )
        try:
            payload = self._read_payload(raw_object_id, raw_bytes)
        except (UnicodeDecodeError, json.JSONDecodeError):
            return self._report(evidence, checks, report_cache_key)
        checks["source_entailment"] = _source_entails(evidence, payload)
        return self._report(evidence, checks, report_cache_key)

    def _resolve_storage_path(self, storage_uri: str) -> Path:
        source_path = Path(storage_uri).expanduser()
        candidate = (
            source_path.resolve()
            if source_path.is_absolute()
            else (self._archive_root / source_path).resolve()
        )
        if candidate.is_relative_to(self._archive_root):
            return candidate
        for legacy_root in self._legacy_archive_roots:
            if not candidate.is_relative_to(legacy_root):
                continue
            remapped = (self._archive_root / candidate.relative_to(legacy_root)).resolve()
            if remapped.is_relative_to(self._archive_root):
                return remapped
        return candidate

    def _read_bytes(self, raw_object_id: str, path: Path) -> bytes:
        cached = self._byte_cache.pop(raw_object_id, None)
        if cached is not None:
            self._byte_cache[raw_object_id] = cached
            return cached
        content = path.read_bytes()
        self._byte_cache[raw_object_id] = content
        while len(self._byte_cache) > self._cache_size:
            self._byte_cache.popitem(last=False)
        return content

    def _read_payload(self, raw_object_id: str, raw_bytes: bytes) -> Any:
        cached = self._payload_cache.pop(raw_object_id, None)
        if cached is not None:
            self._payload_cache[raw_object_id] = cached
            return cached
        payload = json.loads(raw_bytes)
        self._payload_cache[raw_object_id] = payload
        while len(self._payload_cache) > self._cache_size:
            self._payload_cache.popitem(last=False)
        return payload

    def _report(
        self,
        evidence: EvidenceItem,
        checks: dict[str, bool],
        report_cache_key: str,
    ) -> SourceGroundingReport:
        report = SourceGroundingReport(
            evidence_id=evidence.evidence_id,
            checks=checks,
            failures=tuple(check_id for check_id, passed in checks.items() if not passed),
        )
        self._report_cache[report_cache_key] = report
        return report


def _source_entails(evidence: EvidenceItem, payload: Any) -> bool:
    if not isinstance(evidence.payload, ScalarObservation):
        return False
    handlers = {
        "sec_companyfacts": _sec_entails,
        "fred_observations": _fred_entails,
        "worldbank_indicators": _world_bank_entails,
    }
    handler = handlers.get(evidence.source.source_id)
    return False if handler is None else handler(evidence, payload)


def _sec_entails(evidence: EvidenceItem, payload: Any) -> bool:
    if not isinstance(payload, dict):
        return False
    raw_concept = str(evidence.definition.attributes.get("raw_concept_name") or "")
    if ":" not in raw_concept:
        return False
    namespace, concept = raw_concept.split(":", 1)
    concept_payload = (payload.get("facts") or {}).get(namespace, {}).get(concept, {})
    units = concept_payload.get("units") or {}
    period_end = _period_end(evidence)
    period_start = evidence.temporal_context.valid_from
    fiscal_year = evidence.domain_context.get("fiscal_year")
    fiscal_quarter = str(evidence.domain_context.get("fiscal_quarter") or "")
    source_fiscal_quarter = fiscal_quarter.removesuffix("_YTD")
    for rows in units.values():
        if not isinstance(rows, list):
            continue
        for row in rows:
            if not isinstance(row, dict) or row.get("val") is None:
                continue
            if period_end and str(row.get("end") or "") != period_end.isoformat():
                continue
            if period_start and row.get("start") and str(row["start"]) != period_start.isoformat():
                continue
            if fiscal_year is not None and row.get("fy") is not None:
                if int(row["fy"]) != int(fiscal_year):
                    continue
            if source_fiscal_quarter and row.get("fp") and str(row["fp"]) != source_fiscal_quarter:
                continue
            if _normalized_raw_value(row["val"], evidence) == _evidence_value(evidence):
                return True
    return False


def _fred_entails(evidence: EvidenceItem, payload: Any) -> bool:
    if not isinstance(payload, dict):
        return False
    period_end = _period_end(evidence)
    if period_end is None:
        return False
    for row in payload.get("observations") or ():
        if not isinstance(row, dict) or row.get("value") in (None, "."):
            continue
        if row.get("date") != period_end.isoformat():
            continue
        return _normalized_raw_value(row["value"], evidence) == _evidence_value(evidence)
    return False


def _world_bank_entails(evidence: EvidenceItem, payload: Any) -> bool:
    if not isinstance(payload, list) or len(payload) < 2 or not isinstance(payload[1], list):
        return False
    year = evidence.domain_context.get("calendar_year") or evidence.domain_context.get(
        "fiscal_year"
    )
    if year is None:
        period_end = _period_end(evidence)
        year = period_end.year if period_end else None
    for row in payload[1]:
        if not isinstance(row, dict) or row.get("value") is None:
            continue
        if str(row.get("date")) != str(year):
            continue
        return _normalized_raw_value(row["value"], evidence) == _evidence_value(evidence)
    return False


def _normalized_raw_value(value: Any, evidence: EvidenceItem) -> Decimal:
    observed = Decimal(str(value))
    scale = str(evidence.domain_context.get("value_scale") or "reported").casefold()
    divisor = {
        "thousand": Decimal("1000"),
        "million": Decimal("1000000"),
        "billion": Decimal("1000000000"),
    }.get(scale, Decimal("1"))
    return observed / divisor


def _evidence_value(evidence: EvidenceItem) -> Decimal:
    if not isinstance(evidence.payload, ScalarObservation):
        raise ValueError("source grounding requires scalar evidence")
    try:
        return Decimal(str(evidence.payload.value))
    except (InvalidOperation, TypeError) as exc:
        raise ValueError("evidence value is not numeric") from exc


def _period_end(evidence: EvidenceItem):
    context = evidence.temporal_context
    return context.valid_to or context.observed_at or context.valid_from
