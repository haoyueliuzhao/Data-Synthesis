from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from itertools import combinations
from typing import Any, NoReturn

from trusted_synthesis.canonical_json import canonical_json_bytes, strict_canonical_hash
from trusted_synthesis.core.evidence.epistemic import EpistemicStatus
from trusted_synthesis.core.evidence.locator import SourceLocator
from trusted_synthesis.core.evidence.payloads import EvidenceKind, ScalarObservation
from trusted_synthesis.core.evidence.schema import (
    EvidenceBundle,
    EvidenceItem,
    ProvenanceRef,
    SemanticDefinitionRef,
    SourceAuthority,
    SourceRef,
    SubjectRef,
)
from trusted_synthesis.core.evidence.scope import EvidenceScope
from trusted_synthesis.core.evidence.temporal import TemporalContext

from . import models


class ArchiveAdmissionError(ValueError):
    """A frozen-Archive selector or derived Evidence Binding was not authoritative."""

    def __init__(self, stage: str, reason: str) -> None:
        super().__init__(reason)
        self.stage = stage


def _fail(stage: str, reason: str) -> NoReturn:
    raise ArchiveAdmissionError(stage, reason)


@dataclass(frozen=True)
class PeriodSpec:
    label: str
    sort_key: int
    column_index: int
    valid_from: date
    valid_to: date
    frequency: str


@dataclass(frozen=True)
class RecordSpec:
    record_id: str
    filename: str
    subject_id: str
    subject_name: str
    revenue_row: int
    revenue_label: str
    income_row: int
    income_label: str
    gross_profit_row: int | None
    gross_profit_label: str | None
    periods: tuple[PeriodSpec, ...]


RECORD_SPECS = (
    RecordSpec(
        record_id="CDW/2017/page_38.pdf-1",
        filename="CDW/2017/page_38.pdf",
        subject_id="finqa:CDW",
        subject_name="CDW Corporation",
        revenue_row=2,
        revenue_label="Net sales",
        income_row=4,
        income_label="Income from operations",
        gross_profit_row=3,
        gross_profit_label="Gross profit",
        periods=(
            PeriodSpec("FY2015", 2015, 3, date(2015, 1, 1), date(2015, 12, 31), "annual"),
            PeriodSpec("FY2016", 2016, 2, date(2016, 1, 1), date(2016, 12, 31), "annual"),
            PeriodSpec("FY2017", 2017, 1, date(2017, 1, 1), date(2017, 12, 31), "annual"),
        ),
    ),
    RecordSpec(
        record_id="HII/2015/page_121.pdf-1",
        filename="HII/2015/page_121.pdf",
        subject_id="finqa:HII",
        subject_name="Huntington Ingalls Industries",
        revenue_row=2,
        revenue_label="Sales and service revenues",
        income_row=3,
        income_label="Operating income (loss)",
        gross_profit_row=None,
        gross_profit_label=None,
        periods=(
            PeriodSpec("2014 Q1", 201401, 1, date(2014, 1, 1), date(2014, 3, 31), "quarterly"),
            PeriodSpec("2014 Q2", 201402, 2, date(2014, 4, 1), date(2014, 6, 30), "quarterly"),
            PeriodSpec("2014 Q3", 201403, 3, date(2014, 7, 1), date(2014, 9, 30), "quarterly"),
            PeriodSpec("2014 Q4", 201404, 4, date(2014, 10, 1), date(2014, 12, 31), "quarterly"),
        ),
    ),
)


def archive_sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def validate_archive_bytes(payload: bytes) -> None:
    if len(payload) != models.ARCHIVE_BYTE_COUNT or archive_sha256(payload) != (
        models.ARCHIVE_SHA256
    ):
        _fail("archive.bytes", "frozen FinQA source Archive bytes differ")


def select_records(records: Any) -> tuple[tuple[RecordSpec, dict[str, Any]], ...]:
    if not isinstance(records, list) or len(records) != models.ARCHIVE_RECORD_COUNT:
        _fail("archive.record_domain", "frozen Archive record domain differs")
    by_id: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        if isinstance(record, dict) and isinstance(record.get("id"), str):
            by_id.setdefault(record["id"], []).append(record)
    selected = []
    for spec in RECORD_SPECS:
        rows = by_id.get(spec.record_id, [])
        if len(rows) != 1:
            _fail("archive.source_selector", f"source record is not unique:{spec.record_id}")
        record = rows[0]
        if record.get("filename") != spec.filename:
            _fail("archive.source_selector", f"source filename differs:{spec.record_id}")
        _validate_table(spec, record)
        selected.append((spec, record))
    if tuple(spec.record_id for spec, _ in selected) != models.SOURCE_RECORD_IDS:
        _fail("archive.source_selector", "selected source-record set differs")
    return tuple(selected)


def _validate_table(spec: RecordSpec, record: dict[str, Any]) -> None:
    table = record.get("table_ori")
    if not isinstance(table, list):
        _fail("archive.table_schema", f"source table is absent:{spec.record_id}")
    expected: tuple[tuple[int, str], ...] = (
        (spec.revenue_row, spec.revenue_label),
        (spec.income_row, spec.income_label),
    )
    if spec.gross_profit_row is not None and spec.gross_profit_label is not None:
        expected += ((spec.gross_profit_row, spec.gross_profit_label),)
    for row_index, label in expected:
        if row_index >= len(table) or not isinstance(table[row_index], list):
            _fail("archive.table_schema", f"source row is absent:{spec.record_id}:{label}")
        if table[row_index][0] != label:
            _fail("archive.source_cell", f"source row label differs:{spec.record_id}:{label}")
    for period in spec.periods:
        for row_index, _ in expected:
            row = table[row_index]
            if period.column_index >= len(row):
                _fail("archive.source_cell", "source numeric cell is absent")
            _decimal(row[period.column_index])


def archive_record_rows(
    selected: tuple[tuple[RecordSpec, dict[str, Any]], ...],
) -> tuple[dict[str, Any], ...]:
    return tuple(
        {
            "record_id": spec.record_id,
            "filename": spec.filename,
            "subject_id": spec.subject_id,
            "subject_name": spec.subject_name,
            "record_sha256": hashlib.sha256(canonical_json_bytes(record)).hexdigest(),
            "table_sha256": hashlib.sha256(canonical_json_bytes(record["table_ori"])).hexdigest(),
            "revenue_row": spec.revenue_row,
            "income_row": spec.income_row,
            "gross_profit_row": spec.gross_profit_row,
            "period_labels": tuple(period.label for period in spec.periods),
            "period_count": len(spec.periods),
            "source_is_real_financial_document_snapshot": True,
            "distribution_weight": None,
            "schema_version": "qa_archive_selected_record.v1",
        }
        for spec, record in selected
    )


def branch_bindings(
    selected: tuple[tuple[RecordSpec, dict[str, Any]], ...],
    archive_id: str,
) -> tuple[tuple[str, EvidenceBundle, dict[str, tuple[str, ...]], dict[str, Any]], ...]:
    rows: list[tuple[str, EvidenceBundle, dict[str, tuple[str, ...]], dict[str, Any]]] = []
    for spec, record in selected:
        for earlier, later in combinations(spec.periods, 2):
            evidence = (
                _cell_evidence(spec, record, earlier, spec.revenue_row, "revenue", archive_id),
                _cell_evidence(spec, record, later, spec.revenue_row, "revenue", archive_id),
                _cell_evidence(
                    spec, record, earlier, spec.income_row, "operating_income", archive_id
                ),
                _cell_evidence(
                    spec, record, later, spec.income_row, "operating_income", archive_id
                ),
            )
            case_id = (
                f"branch_{spec.subject_id.rsplit(':', maxsplit=1)[-1].casefold()}_"
                f"{_slug(earlier.label)}_{_slug(later.label)}"
            )
            bundle = _bundle(case_id, evidence)
            role_bindings: dict[str, tuple[str, ...]] = {
                "revenue_earlier": (evidence[0].evidence_id,),
                "revenue_later": (evidence[1].evidence_id,),
                "income_earlier": (evidence[2].evidence_id,),
                "income_later": (evidence[3].evidence_id,),
            }
            rv0, rv1, iv0, iv1 = (_scalar(item) for item in evidence)
            rg = (rv1 - rv0) / rv0 * Decimal("100")
            ig = (iv1 - iv0) / iv0 * Decimal("100")
            relation = (
                "both_positive"
                if rg >= 0 and ig >= 0
                else "both_negative"
                if rg < 0 and ig < 0
                else "mixed_sign"
            )
            metadata = {
                "subject_id": spec.subject_id,
                "source_record_id": spec.record_id,
                "earlier_period": earlier.label,
                "later_period": later.label,
                "period_span": later.sort_key - earlier.sort_key,
                "revenue_growth": str(rg),
                "income_growth": str(ig),
                "absolute_growth_spread": str(abs(rg - ig)),
                "numeric_relationship": relation,
                "adjacent_periods": later.sort_key - earlier.sort_key == 1,
                "near_equal_growth": abs(rg - ig) < Decimal("1"),
            }
            rows.append((case_id, bundle, role_bindings, metadata))
    return tuple(rows)


def serial_candidate_rows(
    selected: tuple[tuple[RecordSpec, dict[str, Any]], ...],
    archive_id: str,
) -> tuple[dict[str, Any], ...]:
    rows = []
    for spec, record in selected:
        if spec.gross_profit_row is None:
            continue
        table = record["table_ori"]
        if any(
            isinstance(row, list) and row and "target" in str(row[0]).casefold() for row in table
        ):
            _fail("archive.target_domain", "unexpected target row entered frozen source table")
        for period in spec.periods:
            numerator = _cell_evidence(
                spec, record, period, spec.gross_profit_row, "gross_profit", archive_id
            )
            denominator = _cell_evidence(
                spec, record, period, spec.revenue_row, "revenue", archive_id
            )
            rows.append(
                {
                    "case_id": f"serial_{_slug(period.label)}",
                    "task_type": "registered_margin_target_gap",
                    "subject_id": spec.subject_id,
                    "source_record_id": spec.record_id,
                    "period": period.label,
                    "available_role_evidence_ids": {
                        "numerator": (numerator.evidence_id,),
                        "denominator": (denominator.evidence_id,),
                        "target": (),
                    },
                    "required_roles": ("numerator", "denominator", "target"),
                    "archive_role_complete": False,
                    "constructible": False,
                    "typed_blocker": "authoritative_gross_margin_target_evidence_absent",
                    "arbitrary_target_constant_admitted": False,
                    "derived_observed_margin_relabelled_as_target": False,
                    "schema_version": "qa_archive_parameter_case_row.v1",
                }
            )
    return tuple(rows)


def reject_target_candidate(
    *,
    evidence: EvidenceItem,
    selected_records: tuple[dict[str, Any], ...],
) -> None:
    if evidence.predicate != "gross_margin_target":
        _fail("archive.target_authority", "candidate does not claim target evidence")
    locator = evidence.source_locator
    matching = [
        row for row in selected_records if row["record_id"] == evidence.provenance.source_record_id
    ]
    if not matching:
        _fail("archive.target_authority", "target does not bind an admitted source record")
    if locator.row is None or "target" not in locator.row.casefold():
        _fail("archive.target_authority", "target predicate has no target-labelled source row")
    _fail("archive.target_authority", "frozen Archive contains no admitted target-labelled row")


def _cell_evidence(
    spec: RecordSpec,
    record: dict[str, Any],
    period: PeriodSpec,
    row_index: int,
    predicate: str,
    archive_id: str,
) -> EvidenceItem:
    table = record["table_ori"]
    label = str(table[row_index][0])
    raw_value = str(table[row_index][period.column_index])
    value = _decimal(raw_value)
    page_match = re.search(r"page_(\d+)\.pdf", spec.filename)
    if page_match is None:
        _fail("archive.source_selector", "source page is not parseable")
    cell_authority = {
        "archive_id": archive_id,
        "source_record_id": spec.record_id,
        "filename": spec.filename,
        "table": "table_ori",
        "row_index": row_index,
        "row_label": label,
        "column_index": period.column_index,
        "period": period.label,
        "raw_value": raw_value,
        "normalized_predicate": predicate,
        "normalized_value": str(value),
    }
    digest = hashlib.sha256(canonical_json_bytes(cell_authority)).hexdigest()
    evidence_id = f"evidence:finqa_archive_cell:{digest}"
    return EvidenceItem(
        evidence_id=evidence_id,
        assertion_id=f"assertion:finqa_archive_cell:{digest}",
        evidence_version_id=f"version:finqa_archive_cell:{digest}@v1",
        domain="finance",
        evidence_kind=EvidenceKind.SCALAR,
        subject=SubjectRef(
            subject_id=spec.subject_id,
            name=spec.subject_name,
            subject_type="public_company",
            attributes={"ticker": spec.subject_id.rsplit(":", maxsplit=1)[-1]},
        ),
        predicate=predicate,
        payload=ScalarObservation(
            value=value,
            unit="million USD",
            currency="USD",
        ),
        temporal_context=TemporalContext(
            label=period.label,
            valid_from=period.valid_from,
            valid_to=period.valid_to,
            basis="fiscal_period",
            frequency=period.frequency,
        ),
        scope=EvidenceScope(
            scope_type="consolidated_entity",
            scope_id=spec.subject_id,
            label=f"{spec.subject_name} consolidated",
        ),
        source=SourceRef(
            source_id=archive_id,
            name="FinQA frozen test financial-document source Archive",
            authority=SourceAuthority.CURATED_DATABASE,
            provider="FinQA",
            license_note="Existing repository-frozen research benchmark snapshot",
            attributes={"distribution_inference_authorized": False},
        ),
        source_locator=SourceLocator(
            storage_uri=models.ARCHIVE_PATH,
            raw_object_id=f"{archive_id}:{spec.record_id}",
            source_document_id=spec.filename,
            document_version=models.ARCHIVE_SHA256,
            page=int(page_match.group(1)),
            table="table_ori",
            row=label,
            json_pointer=f"/{spec.record_id}/table_ori/{row_index}/{period.column_index}",
            table_cell=f"R{row_index}C{period.column_index}",
            quoted_text_hash=hashlib.sha256(raw_value.encode("utf-8")).hexdigest(),
        ),
        definition=SemanticDefinitionRef(
            definition_id=f"finance_archive_{predicate}.v1",
            text=f"Archive-normalized {predicate.replace('_', ' ')} financial statement cell.",
            attributes={
                "comparability_level": "exact_archive_table_cell",
                "statement_type": "income_statement",
                "period_type": "duration",
                "default_unit": "million USD",
                "source_row_label": label,
            },
        ),
        provenance=ProvenanceRef(
            adapter_id="qa_frozen_finqa_table_adapter.v1",
            archive_id=archive_id,
            source_record_id=spec.record_id,
            build_ids={"archive_sha256": models.ARCHIVE_SHA256},
            content_hash=digest,
            extraction_method="exact_table_cell_selector",
        ),
        epistemic_status=EpistemicStatus.OBSERVED,
        extraction_confidence=1.0,
        domain_context={
            "statement_type": "income_statement",
            "period_type": "duration",
            "economic_period_sort_key": period.sort_key,
            "is_forecast": False,
            "archive_grounded": True,
            "benchmark_distribution_weight": None,
        },
    )


def _bundle(case_id: str, evidence: tuple[EvidenceItem, ...]) -> EvidenceBundle:
    identity = {
        "case_id": case_id,
        "evidence_ids": tuple(item.evidence_id for item in evidence),
        "evidence_version_ids": tuple(item.evidence_version_id for item in evidence),
        "schema_version": "qa_archive_evidence_bundle.v1",
    }
    return EvidenceBundle(
        bundle_id=strict_canonical_hash(identity, prefix="qa_archive_evidence_bundle:"),
        evidence=evidence,
        purpose="archive-grounded depth-three parameter-space constructibility preflight",
        graph_build_id=f"qa_archive_graph:{case_id}",
        metadata={
            "provider_generated": False,
            "archive_grounded": True,
            "benchmark_distribution_weight": None,
            "stage": models.STAGE,
        },
    )


def _decimal(value: Any) -> Decimal:
    cleaned = re.sub(r"[^0-9.()\-]", "", str(value)).strip()
    if cleaned.startswith("(") and cleaned.endswith(")"):
        cleaned = f"-{cleaned[1:-1]}"
    try:
        return Decimal(cleaned)
    except (InvalidOperation, ValueError) as exc:
        _fail("archive.source_cell", f"source cell is not numeric:{value!r}")
        raise AssertionError from exc


def _scalar(evidence: EvidenceItem) -> Decimal:
    if not isinstance(evidence.payload, ScalarObservation):
        _fail("archive.evidence", "archive Evidence is not scalar")
    return Decimal(str(evidence.payload.value))


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.casefold()).strip("_")
