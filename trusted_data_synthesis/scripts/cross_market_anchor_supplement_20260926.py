"""Prospective exact-literal row anchors from already registered geometry only.

Pure in-memory scan: no files, PDF, network, financial qualification or task
enumeration. The caller must register/freeze rules before the uniform 440-doc
scan and enforce the total cap before passing any new anchor to qualification.
An anchor is a source locator, not an amount/period/scope observation.
"""

import re
import unicodedata
from decimal import Decimal, InvalidOperation

import prepare_cross_market_sources_20260926 as base
from cross_market_layout_qualification_20260926 import lines_for_page

SCRIPT = "trusted_data_synthesis/scripts/cross_market_anchor_supplement_20260926.py"
MAX_ROWS_PER_DOCUMENT = 64
MAX_TOTAL_ROWS = 1024
LITERAL_LABELS = {
    "revenues": "revenue",
    "cost of revenue": "cost_of_revenue",
    "cost of revenues": "cost_of_revenue",
}
RULE_VERSION = "exact_whole_row_literals.v1"
NATIVE_NUMBER = re.compile(r"[+-]?(?:\d+|\d{1,3}(?:,\d{3})+)(?:\.\d+)?")
NOTE_TOKEN = re.compile(
    r"(?:\d+[a-z]?\((?:[a-z]|\d+|[ivx]{1,4})\)|\d+(?:,\d+){1,2}|\d+[,;]|\d+[a-z]|"
    r"\((?:[a-z]|\d+|[ivx]{1,4})\)|\[(?:[a-z]|\d+|[ivx]{1,4})\]|"
    r"[a-z]|[一二三四五六七八九十]+、\d+|[,;*†‡—–-])"
)
PENDING = "NEW_LITERAL_GEOMETRY_ROW_ANCHOR_UNQUALIFIED"


class AnchorCapExceeded(ValueError):
    """No partial/truncated anchor result can be treated as a successful scan."""

    def __init__(self, scope, observed, limit):
        self.scope, self.observed, self.limit = scope, observed, limit
        super().__init__(f"anchor_supplement.{scope}_cap_exceeded:{observed}>{limit}")


def require(value, reason):
    base.require(value, "anchor_supplement." + reason)


def literal(text):
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", str(text))).strip().casefold()


def candidate_label_key(text):
    # Old parser source labels can omit whitespace. This key is ONLY for
    # conservative suppression of already-existing anchors, not for new matches.
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", str(text))).casefold()


def native_number(text):
    """Validate a complete original numeric word, without period assignment."""
    normalized = unicodedata.normalize("NFKC", str(text)).strip().replace("−", "-")
    if normalized.startswith("(") and normalized.endswith(")"):
        normalized = "-" + normalized[1:-1]
    if not NATIVE_NUMBER.fullmatch(normalized):
        return False
    try:
        return Decimal(normalized.replace(",", "")).is_finite()
    except InvalidOperation:
        return False


def word_reference(word):
    return dict(
        original_word_index=word["original_word_index"],
        text=word["text"],
        x0=word["x0"],
        y0=word["y0"],
        x1=word["x1"],
        y1=word["y1"],
    )


def literal_prefix(line):
    """No arbitrary prefix, translation, hierarchy or semantic suffix removal."""
    for stop in range(1, len(line["words"]) + 1):
        label_words = line["words"][:stop]
        printed_label = " ".join(word["text"] for word in label_words)
        normalized = literal(printed_label)
        if normalized in LITERAL_LABELS:
            return dict(
                metric_id=LITERAL_LABELS[normalized],
                literal_label=normalized,
                printed_label=printed_label,
                label_words=label_words,
                remaining_words=line["words"][stop:],
            )
    return None


def placeholder_candidate(doc, geometry, page, line, match, numeric_words, annotation_words):
    locator = dict(
        rule_version=RULE_VERSION,
        raw_object_id=doc["raw_object_id"],
        raw_sha256=doc["sha256"],
        geometry_id=geometry["id"],
        page_number=page,
        metric_id=match["metric_id"],
        original_label=match["printed_label"],
        row_word_indices=[w["original_word_index"] for w in line["words"]],
        label_word_indices=[w["original_word_index"] for w in match["label_words"]],
    )
    identifier = "source_geometry_anchor:" + base.sha(base.encode(locator))
    # financial_facts archives these fields as old bindings, but its source
    # observations must be rederived from geometry. None does NOT mean zero.
    placeholders = {
        "period_start": None,
        "period_end": None,
        "period_hint": None,
        "fiscal_year": None,
        "fiscal_quarter": None,
        "value": None,
        "_raw_value_text": None,
        "currency": None,
        "unit": None,
        "value_scale": None,
        "table_id": None,
        "column_index": None,
        "_period_source_page": None,
        "_statement_source_page": None,
        "_unit_source_page": None,
        "_period_label": None,
        "_unit_evidence_text": None,
        "statement_type": None,
        "financial_scope_type": None,
    }
    provenance = dict(
        kind="exact_literal_cached_geometry_row_locator_not_financial_observation",
        **locator,
        original_url=doc["original_url"],
        geometry_line_index=line["line_index"],
        original_row_text=line["text"],
        original_label_words=[word_reference(w) for w in match["label_words"]],
        unassigned_native_numeric_words=[word_reference(w) for w in numeric_words],
        unassigned_annotation_words=[word_reference(w) for w in annotation_words],
        numeric_word_count_is_not_observation_count=True,
        additional_notes_and_numeric_columns_require_later_qualification=True,
        not_an_original_9513_parser_candidate=True,
        financial_values_periods_scope_currency_not_assigned=True,
    )
    candidate = dict(
        **placeholders,
        candidate_id=identifier,
        raw_object_id=doc["raw_object_id"],
        entity_id="unresolved_security:" + doc["security_id"],
        page_number=page,
        row_index=line["line_index"],
        row_index_kind="new_geometry_line_index_not_parser_table_row",
        source_field_name=match["printed_label"],
        matched_metric_id=match["metric_id"],
        metric_hint=match["metric_id"],
        _source_id=doc["source_id"],
        _source_publish_date=doc.get("publish_date"),
        evidence_text=line["text"],
        evidence_sha256=base.sha(line["text"]),
        evidence_status="source_locator_only_not_mechanically_verified",
        candidate_state=PENDING,
        review_status="UNREVIEWED",
        confidence_score=None,
        cross_check_status="not_run",
        promotion_status="not_promoted",
        promoted_fact_id=None,
        qa_eligible=0,
        kg_eligible=0,
        _validation_errors=["pending_independent_financial_qualification"],
        placeholder_contract=dict(
            status="UNQUALIFIED_PLACEHOLDERS",
            fields=sorted(placeholders),
            no_zero_fill=True,
            no_manifest_year_as_period=True,
            no_assumed_currency_scale_or_consolidated_scope=True,
            no_original_parser_credit=True,
        ),
        extraction_metadata=dict(
            parser_version=None,
            statement_title=None,
            period_inference="not_established_new_geometry_anchor",
            table_row_span=[line["line_index"]],
            value_extraction_method="literal_geometry_row_locator_only_no_value_extraction",
            source_id=doc["source_id"],
            source_publish_date=doc.get("publish_date"),
            verification_methods=[],
            validation_errors=["financial_admission_pending"],
        ),
        source_geometry_anchor_provenance=provenance,
    )
    review = dict(
        candidate_id=identifier,
        mechanical_checks_passed=False,
        failures=["new_geometry_anchor_has_no_original_parser_or_mechanical_admission_credit"],
        status="PENDING_INDEPENDENT_FINANCIAL_QUALIFICATION",
        qa_eligible=False,
        original_candidate_review=False,
        source_geometry_anchor=True,
    )
    return candidate, review


def scan_document(original_extraction, geometry, doc):
    """Scan every registered selected geometry page, independent of prior outcomes.

    Returns keys new_anchors, mechanical_reviews, skipped_existing,
    rejected_rows and counts. Caps fail the whole document, never take first N.
    """
    base.checked(original_extraction, "PDF_extraction_result")
    base.checked(geometry, "cross_market_original_PDF_geometry")
    require(
        original_extraction["document"] == geometry["document"] == doc,
        "frozen_original_document_identity",
    )
    require(geometry["status"] == "GEOMETRY_COLLECTED_NOT_ADMITTED", "complete_cached_geometry")
    pages = geometry["pages"]
    numbers = [p["page_number"] for p in pages]
    registered_pages = geometry["page_selection"]["selected_pages"]
    require(
        len(set(numbers)) == len(numbers) and set(numbers) == set(registered_pages),
        "exact_original_selected_pages_only",
    )
    original_candidates = original_extraction["parsed"]["candidates"]
    existing = {}
    for c in original_candidates:
        require(c["raw_object_id"] == doc["raw_object_id"], "original_candidate_parent")
        key = (
            c["page_number"],
            c["matched_metric_id"],
            candidate_label_key(c["source_field_name"]),
        )
        existing.setdefault(key, []).append(c["candidate_id"])
    anchors, reviews, skipped, rejected = [], [], [], []
    total_lines = outside_literals = literal_rows = 0
    physical_rows = set()
    for page in sorted(pages, key=lambda p: p["page_number"]):
        for line in lines_for_page(page):
            total_lines += 1
            match = literal_prefix(line)
            if match is None:
                outside_literals += 1
                continue
            literal_rows += 1
            numeric_words = [w for w in match["remaining_words"] if native_number(w["text"])]
            annotation_words = [w for w in match["remaining_words"] if not native_number(w["text"])]
            descriptor = dict(
                page_number=page["page_number"],
                geometry_line_index=line["line_index"],
                metric_id=match["metric_id"],
                original_label=match["printed_label"],
                original_row_text=line["text"],
                original_word_indices=[w["original_word_index"] for w in line["words"]],
            )
            unsupported = [
                w for w in annotation_words if not NOTE_TOKEN.fullmatch(literal(w["text"]))
            ]
            if unsupported:
                rejected.append(
                    dict(
                        **descriptor,
                        reason="unsupported_extra_semantic_label_or_annotation_word",
                        unresolved_words=[word_reference(w) for w in unsupported],
                    )
                )
                continue
            if len(numeric_words) < 2:
                rejected.append(
                    dict(
                        **descriptor,
                        reason="fewer_than_two_native_numeric_words",
                        native_numeric_word_count=len(numeric_words),
                    )
                )
                continue
            key = (
                page["page_number"],
                match["metric_id"],
                candidate_label_key(match["printed_label"]),
            )
            if key in existing:
                skipped.append(
                    dict(
                        **descriptor,
                        reason="existing_original_page_metric_label_anchor_preserved",
                        original_candidate_ids=sorted(existing[key]),
                        prior_admission_status_not_used=True,
                    )
                )
                continue
            physical = (page["page_number"], tuple(descriptor["original_word_indices"]))
            require(physical not in physical_rows, "duplicate_new_physical_row")
            physical_rows.add(physical)
            candidate, review = placeholder_candidate(
                doc, geometry, page["page_number"], line, match, numeric_words, annotation_words
            )
            anchors.append(candidate)
            reviews.append(review)
            if len(anchors) > MAX_ROWS_PER_DOCUMENT:
                raise AnchorCapExceeded("document", len(anchors), MAX_ROWS_PER_DOCUMENT)
    require(
        len(anchors) == len(reviews) == len({a["candidate_id"] for a in anchors}),
        "unique_new_anchors",
    )
    return dict(
        status="LITERAL_ROW_SCAN_COMPLETE_NOT_FINANCIALLY_QUALIFIED",
        rule_version=RULE_VERSION,
        raw_object_id=doc["raw_object_id"],
        raw_sha256=doc["sha256"],
        geometry_id=geometry["id"],
        original_extraction_id=original_extraction["id"],
        new_anchors=anchors,
        mechanical_reviews=reviews,
        skipped_existing=skipped,
        rejected_rows=rejected,
        counts=dict(
            original_candidates=len(original_candidates),
            selected_geometry_pages=len(pages),
            inspected_geometry_lines=total_lines,
            outside_registered_literals=outside_literals,
            literal_prefix_rows=literal_rows,
            skipped_existing_rows=len(skipped),
            rejected_literal_rows=len(rejected),
            new_row_anchors=len(anchors),
        ),
        original_candidates_unchanged=True,
        financial_qualification_performed=False,
        observations_rederived=0,
        tasks_created=0,
        amount_or_closure_based_selection=False,
    )


def enforce_global_anchor_cap(total_new_rows):
    require(type(total_new_rows) is int and total_new_rows >= 0, "nonnegative_total_row_count")
    if total_new_rows > MAX_TOTAL_ROWS:
        raise AnchorCapExceeded("global", total_new_rows, MAX_TOTAL_ROWS)
    return total_new_rows
