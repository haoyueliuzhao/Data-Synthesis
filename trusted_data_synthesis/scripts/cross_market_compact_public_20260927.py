"""Lossless public-only encoding of the fixed cross-market source panel.

The original runtime reads neither definition nor evidence subfields, so complete
definitions and table headers can be shared inside each public document without
changing its executable source identity. Audit-only fields travel in a separate
manifest. No private facts, filesystem, model, source selection or numeric
normalization enter this transformation.
"""

from __future__ import annotations

import copy
import hashlib
import json

SCHEMA = "cross_market_compact_public.v1:20260927"
POLICY = SCHEMA
SCRIPT = "trusted_data_synthesis/scripts/cross_market_compact_public_20260927.py"
PUBLIC_FIELDS = {
    "question",
    "sources",
    "source_documents",
    "period_contract",
    "quantity_contract",
    "source_policy",
    "tool_contract",
}
DOCUMENT_AUDIT_FIELDS = {
    "financial_qualification_record_id",
    "complete_original_pdf",
    "complete_original_page_text",
}
EVIDENCE_AUDIT_FIELDS = {
    "table",
    "parser_word_index",
    "financial_fact_id",
    "full_original_evidence_sha256",
}
POLICY_ADDITIONS = {"compact_public_encoding": SCHEMA}
TOOL_ADDITIONS = {
    "definition_ref_resolution": (
        "For each source, definition.ref names its complete original definition in "
        "source_documents[matching raw_object_id].definitions."
    ),
    "table_ref_resolution": (
        "For each source, evidence.table_ref names its original unit_header and page in "
        "source_documents[matching raw_object_id].statement_tables."
    ),
    "source_id_encoding": (
        "S0001 etc. identify every supplied source in unchanged order; "
        "use that source_id in read_source."
    ),
}


def _require(condition, reason):
    if not condition:
        raise ValueError("compact_public." + reason)


def _encode(value):
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode()


def _sha(value):
    return hashlib.sha256(_encode(value)).hexdigest()


def _remove(value, keys):
    return {key: value.pop(key) for key in sorted(keys) if key in value}


def _add(value, additions):
    _require(not set(value) & set(additions), "reserved_projection_field")
    value.update(copy.deepcopy(additions))


def _intern(dictionary, lookup, key, value, prefix):
    encoded = _encode(key)
    if encoded not in lookup:
        identifier = prefix + f"{len(dictionary) + 1:03d}"
        lookup[encoded] = identifier
        dictionary[identifier] = copy.deepcopy(value)
    return lookup[encoded]


def compact(public):
    """Return (model public JSON, audit manifest), preserving every source row.

    Source IDs are a deterministic positional bijection, never fact-role based.
    Definitions are interned by complete JSON value. Statement tables retain
    distinct original table identities even when their visible headers coincide.
    Unknown fields are retained, not guessed to be audit-only.
    """
    _require(isinstance(public, dict) and set(public) == PUBLIC_FIELDS, "seven_public_fields")
    projected = copy.deepcopy(public)
    documents, definition_lookups, table_lookups, document_audits = {}, {}, {}, []
    for document in projected["source_documents"]:
        raw_id = document["raw_object_id"]
        _require(raw_id not in documents, "unique_documents")
        _require(
            not {"definitions", "statement_tables"} & set(document),
            "unencoded_document_required",
        )
        document_audits.append(
            {"raw_object_id": raw_id, "removed_fields": _remove(document, DOCUMENT_AUDIT_FIELDS)}
        )
        document["definitions"], document["statement_tables"] = {}, {}
        documents[raw_id] = document
        definition_lookups[raw_id], table_lookups[raw_id] = {}, {}

    source_audits, original_ids = [], set()
    for index, source in enumerate(projected["sources"], 1):
        original_id = source["source_id"]
        _require(isinstance(original_id, str) and original_id not in original_ids, "unique_sources")
        original_ids.add(original_id)
        raw_id = source["raw_object_id"]
        _require(raw_id in documents, "source_document_join")
        document = documents[raw_id]
        definition = source["definition"]
        _require(isinstance(definition, dict) and set(definition) != {"ref"}, "full_definition")
        definition_id = _intern(
            document["definitions"], definition_lookups[raw_id], definition, definition, "D"
        )
        evidence = source["evidence"]
        _require("table_ref" not in evidence, "unencoded_evidence_required")
        table = {"page": evidence["page"], "unit_header": evidence["unit_header"]}
        table_id = _intern(
            document["statement_tables"],
            table_lookups[raw_id],
            {"table": evidence["table"], **table},
            table,
            "T",
        )
        source["source_id"] = f"S{index:04d}"
        source["definition"] = {"ref": definition_id}
        removed = _remove(evidence, EVIDENCE_AUDIT_FIELDS)
        evidence.pop("unit_header")
        evidence["table_ref"] = table_id
        source_audits.append(
            {
                "source_id": source["source_id"],
                "original_source_id": original_id,
                "removed_fields": {"evidence": removed},
            }
        )

    _add(projected["source_policy"], POLICY_ADDITIONS)
    _add(projected["tool_contract"], TOOL_ADDITIONS)
    audit = {
        "schema": SCHEMA,
        "original_public_sha256": _sha(public),
        "projected_public_sha256": _sha(projected),
        "documents": document_audits,
        "sources": source_audits,
    }
    return projected, audit


def restore(projected, audit):
    """Rebuild the exact original JSON from projected values and removed fields.

    Audit entries contain no copy of the original financial row, definition,
    amount, period or unit header. These are read from the projection, decoded,
    then checked against the original public digest.
    """
    _require(isinstance(projected, dict) and set(projected) == PUBLIC_FIELDS, "seven_public_fields")
    _require(audit.get("schema") == SCHEMA, "audit_schema")
    _require(_sha(projected) == audit["projected_public_sha256"], "projected_digest")
    original = copy.deepcopy(projected)
    documents = {row["raw_object_id"]: row for row in original["source_documents"]}
    _require(len(documents) == len(original["source_documents"]), "unique_documents")
    _require(len(original["sources"]) == len(audit["sources"]), "source_count")
    for index, (source, removed) in enumerate(
        zip(original["sources"], audit["sources"], strict=True), 1
    ):
        _require(source["source_id"] == removed["source_id"] == f"S{index:04d}", "source_order")
        document = documents[source["raw_object_id"]]
        _require(set(source["definition"]) == {"ref"}, "definition_reference")
        source["definition"] = copy.deepcopy(document["definitions"][source["definition"]["ref"]])
        evidence = source["evidence"]
        table = document["statement_tables"][evidence.pop("table_ref")]
        _require(evidence["page"] == table["page"], "table_page")
        _require(set(removed["removed_fields"]) == {"evidence"}, "source_audit_fields")
        evidence_audit = removed["removed_fields"]["evidence"]
        _require(set(evidence_audit) <= EVIDENCE_AUDIT_FIELDS, "evidence_audit_fields")
        _require(not set(evidence) & (set(evidence_audit) | {"unit_header"}), "evidence_collision")
        evidence["unit_header"] = copy.deepcopy(table["unit_header"])
        evidence.update(copy.deepcopy(evidence_audit))
        source["source_id"] = removed["original_source_id"]

    _require(len(original["source_documents"]) == len(audit["documents"]), "document_count")
    for document, removed in zip(original["source_documents"], audit["documents"], strict=True):
        _require(document["raw_object_id"] == removed["raw_object_id"], "document_order")
        document.pop("definitions")
        document.pop("statement_tables")
        fields = removed["removed_fields"]
        _require(set(fields) <= DOCUMENT_AUDIT_FIELDS, "document_audit_fields")
        _require(not set(document) & set(fields), "document_collision")
        document.update(copy.deepcopy(fields))
    for field, additions in (
        ("source_policy", POLICY_ADDITIONS),
        ("tool_contract", TOOL_ADDITIONS),
    ):
        for key, value in additions.items():
            _require(original[field].pop(key) == value, "projection_contract")
    _require(_sha(original) == audit["original_public_sha256"], "restored_original_digest")
    return original
