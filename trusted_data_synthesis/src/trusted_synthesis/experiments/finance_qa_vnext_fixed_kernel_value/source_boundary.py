"""One bounded source-coverage pass; no answer matching or public-source pruning.

Repeated report cells retain their own occurrence identity.  An occurrence may
share a canonical fact only after the full issuer definition/reconciliation,
same-accession actual-period anchor and revision-compatible column are proven.
Unknown cells remain visible and unknown.  This module never reads responses.
"""

import copy
import json
import re
from collections import Counter
from pathlib import Path

from ..finance_qa_vnext_catalog_bridge.assessment import source_fact_bindings
from ..finance_qa_vnext_linear_postprocess.manifest import LinearParent
from ..finance_qa_vnext_task_build import issuer_tables as issuer
from ..finance_qa_vnext_task_build.archive import validate_record
from ..finance_qa_vnext_task_build.native_facts import resolve_raw
from . import protocol as p

CFO = "net_cash_provided_by_used_in_operating_activities"
RULE = "same_issuer_definition_actual_period_full_column_repeated_disclosure.v1"


def _body(row):
    return {key: value for key, value in row.items() if key not in {"id", "schema_version"}}


def _pointer(payload, pointer):
    value = payload
    for part in pointer.split("/")[1:]:
        part = part.replace("~1", "/").replace("~0", "~")
        value = value[int(part)] if isinstance(value, list) else value[part]
    return value


def _tables(fixtures):
    tables = {}
    for fixture in fixtures:
        public_ids = {r["source_id"] for r in fixture["bundle"]["public"]["sources"]}
        for native in fixture["native_bindings"].values():
            if (
                native.get("source_kind") != "issuer_report_table"
                or native["table_id"] not in public_ids
            ):
                continue
            table = native["table_record"]
            if table["table_id"] not in tables:
                validate_record(table, "issuer_source_table")
            p.require(tables.get(table["table_id"], table) == table, "source.unique_table_parent")
            tables[table["table_id"]] = table
    return tables


def load_source_evidence(data_root, dependency_parents, fixtures):
    """Verify only public issuer tables and their CFO anchors, not old trajectories.

    Parent descriptors come from ``load_fixtures``' byte-pinned dependencies.
    The returned content-addressed object is passed to ``prepare_fixture`` and
    should be frozen with the new experiment; no provider/model/GPU is touched.
    """
    from lxml import html

    data_root = Path(data_root)
    tables = _tables(fixtures)
    raws, members = {}, []
    for descriptor in dependency_parents:
        parent = LinearParent(data_root, descriptor["directory"], descriptor["manifest_id"])
        try:
            p.require(parent.descriptor() == descriptor, "source.parent_descriptor")
            names = sorted(
                name
                for name in parent.members
                if name.startswith("parents/raw_objects/") and name.endswith(".json")
            )
            for name in names:
                for raw in parent.read(name):
                    old = raws.get(raw["content_sha256"])
                    p.require(
                        old is None or old["storage_uri"] == raw["storage_uri"],
                        "source.raw_parent_conflict",
                    )
                    raws[raw["content_sha256"]] = raw
                members.append(
                    {"parent_manifest_id": descriptor["manifest_id"], **parent.members[name]}
                )
        finally:
            parent.close()
    native_rows = {}
    for fixture in fixtures:
        for identifier, native in fixture["native_bindings"].items():
            if (
                native.get("metric_id") == CFO
                and native.get("source_kind") != "issuer_report_table"
            ):
                p.require(
                    native_rows.get(identifier, native) == native, "source.native_parent_conflict"
                )
                native_rows[identifier] = native
    needed = {table["raw_sha256"] for table in tables.values()} | {
        row["raw_sha256"] for row in native_rows.values()
    }
    verified, trees, payloads = [], {}, {}
    for digest in sorted(needed):
        p.require(digest in raws, "source.raw_object_parent_missing")
        raw = raws[digest]
        path = resolve_raw(data_root, raw)
        data = path.read_bytes()
        p.require(p.sha(data) == digest, "source.raw_bytes_reread")
        if any(table["raw_sha256"] == digest for table in tables.values()):
            trees[digest] = html.fromstring(data)
        else:
            payloads[digest] = json.loads(data)
        verified.append(
            {
                "raw_sha256": digest,
                "raw_object_id": raw["raw_object_id"],
                "path": str(path.relative_to(data_root)),
                "bytes": len(data),
            }
        )
    proofs = {}
    for identifier, table in sorted(tables.items()):
        tree = trees[table["raw_sha256"]]
        nodes = tree.xpath(table["table_xpath"])
        p.require(len(nodes) == 1, "source.unique_original_DOM_table")
        document_text = issuer.text(tree)
        observed = issuer.table_structure(nodes[0], document_text)
        # Earlier pinned parents predate supplementary raw-text/DOM annotation
        # fields. Compare every archived field while retaining fresh annotations.
        projection = copy.deepcopy(observed)
        for key in ("rows", "headers"):
            fresh = (
                [cell for row in projection[key] for cell in row]
                if key == "rows"
                else projection[key]
            )
            archived = (
                [cell for row in table["structure"][key] for cell in row]
                if key == "rows"
                else table["structure"][key]
            )
            p.require(len(fresh) == len(archived), "source.original_cell_count")
            for cell, old_cell in zip(fresh, archived, strict=True):
                for supplementary in ("raw_text", "cell_xpath", "has_superscript"):
                    if supplementary not in old_cell:
                        cell.pop(supplementary, None)
        p.require(
            projection == table["structure"],
            "source.original_complete_table_structure:" + identifier,
        )
        revision_window = document_text[
            observed["definition_text_start"] : observed["table_text_end"] + 600
        ]
        revision_markers = [
            match.group(0)
            for match in re.finditer(
                r"\b(?:restat\w*|recast\w*|revis(?:ed|ion)\w*|reclassif\w*)\b",
                revision_window,
                re.I,
            )
        ]
        superscripts = [
            [cell["row"], cell["cell"]]
            for row in observed["rows"]
            for cell in row
            if cell.get("has_superscript") and re.search(r"\d", cell["text"])
        ]
        proofs[identifier] = p.record(
            "original_table_proof",
            table_id=identifier,
            table_record_id=table["id"],
            raw_sha256=table["raw_sha256"],
            table_xpath=table["table_xpath"],
            entity_id=table["entity_id"],
            source_cluster=table["source_cluster"],
            accession=table["accession"],
            complete_original_structure_sha256=p.sha(p.encode(observed)),
            archived_structure_sha256=p.sha(p.encode(projection)),
            original_DOM_replayed=True,
            superscript_numeric_cells=superscripts,
            revision_disclosure_scan_scope=(
                "bound_definition_through_table_and_600_following_normalized_characters; "
                "not a whole_report_absence_claim"
            ),
            revision_window=revision_window,
            explicit_revision_markers=revision_markers,
        )
    occurrences = {}
    for identifier, native in sorted(native_rows.items()):
        payload = payloads[native["raw_sha256"]]
        p.require(
            "cik:" + str(payload["cik"]).zfill(10) == native["source_cluster"],
            "source.CFO_original_entity",
        )
        checked = []
        for occurrence in native["all_equal_source_occurrences"]:
            actual = _pointer(payload, occurrence["pointer"])
            p.require(actual == occurrence["record"], "source.CFO_original_occurrence")
            checked.append(
                {"pointer": occurrence["pointer"], "record_sha256": p.sha(p.encode(actual))}
            )
        occurrences[identifier] = {"raw_sha256": native["raw_sha256"], "occurrences": checked}
    return p.record(
        "source_evidence",
        rule=RULE,
        task_count=len(fixtures),
        table_proofs=proofs,
        CFO_occurrence_proofs=occurrences,
        raw_files=verified,
        dependency_members=members,
        API_calls=0,
        GPU_operations=0,
        Student_outputs_read=False,
        gold_values_read=False,
    )


def _column(table, header):
    structure = table["structure"]
    return [
        issuer.row_amount(
            structure["rows"][index],
            header,
            year_headers=structure["headers"],
            header_row=structure["rows"][header["row"]],
        )
        for index in structure["selected_rows"]
    ]


def _anchor(table, header, column, bindings, evidence):
    candidates = []
    for identifier, native in bindings.items():
        if native.get("metric_id") != CFO or native.get("source_kind") == "issuer_report_table":
            continue
        if (native["entity_id"], native["source_cluster"], native["record"]["end"]) != (
            table["entity_id"],
            table["source_cluster"],
            header["period_end"],
        ):
            continue
        if identifier not in evidence["CFO_occurrence_proofs"]:
            continue
        p.require(
            native.get("native_unit") == "USD" and "/units/USD/" in native["pointer"],
            "source.CFO_native_unit",
        )
        occurrence_proof = evidence["CFO_occurrence_proofs"][identifier]
        p.require(
            occurrence_proof["raw_sha256"] == native["raw_sha256"], "source.CFO_raw_proof_join"
        )
        verified_records = {
            row["pointer"]: row["record_sha256"] for row in occurrence_proof["occurrences"]
        }
        for occurrence in native["all_equal_source_occurrences"]:
            record = occurrence["record"]
            if (
                record.get("accn") == table["accession"]
                and record.get("end") == header["period_end"]
                and record.get("start")
                and record.get("form") == "10-K"
                and record.get("fp") == "FY"
            ):
                p.require(
                    verified_records.get(occurrence["pointer"]) == p.sha(p.encode(record)),
                    "source.CFO_original_record_proof_join",
                )
                candidates.append((identifier, occurrence))
    # Period is located by metadata first. Amount agreement is a subsequent
    # source-unit consistency check, never a gold or answer locator search.
    periods = {
        (r["record"]["start"], r["record"]["end"], r["record"].get("filed")) for _, r in candidates
    }
    p.require(len(periods) == 1, "source.same_accession_actual_period_unresolved")
    start, end, filed = next(iter(periods))
    p.require(
        filed
        and all(
            issuer.Decimal(str(r["record"]["val"])) == column[0][0] * 1000000 for _, r in candidates
        ),
        "source.CFO_unit_or_revision_conflict",
    )
    return start, end, filed, candidates


def _canonical_column(table, start, end, bindings):
    native = [
        (identifier, row)
        for identifier, row in bindings.items()
        if row.get("source_kind") == "issuer_report_table"
        and row["entity_id"] == table["entity_id"]
        and row["definition_shape"] == table["definition_shape"]
        and row["record"]["start"] == start
        and row["record"]["end"] == end
    ]
    by_label = {}
    for identifier, row in native:
        by_label.setdefault(row["record"]["row_label"], []).append((identifier, row))
    labels = [table["structure"]["labels"][index] for index in table["structure"]["selected_rows"]]
    p.require(
        all(label in by_label for label in labels), "source.canonical_complete_column_missing"
    )
    result = []
    for label in labels:
        rows = by_label[label]
        for _, row in rows:
            definition_input = {
                "source_cluster": table["source_cluster"],
                "source_definition_identity": table["source_definition_identity"],
            }
            role = {"label": label, "is_reported_total": label == labels[-1]}
            p.require(
                row["metric_id"] == issuer.metric_id(definition_input, role)
                and row["source_definition_id"] == issuer.definition_id(definition_input, role)
                and row["native_definition"]["description"]
                == table["definition_shape"]["definition_quote"],
                "source.canonical_metric_definition_identity",
            )
            p.require(
                row["record"]["unit"] == "million USD"
                and row["table_record"]["definition_shape"] == table["definition_shape"]
                and row["table_record"]["entity_id"] == table["entity_id"],
                "source.canonical_unit_entity_definition",
            )
            p.require(
                row["raw_sha256"] == row["table_record"]["raw_sha256"]
                and row["table_id"] == row["table_record"]["table_id"]
                and row["record"]["accn"] == row["table_record"]["accession"],
                "source.canonical_report_version_parent",
            )
        meanings = {
            (
                row["metric_id"],
                row["source_definition_id"],
                p.encode(row["native_definition"]),
                row["record"]["val"],
            )
            for _, row in rows
        }
        p.require(len(meanings) == 1, "source.canonical_definition_or_revision_conflict")
        result.append(sorted(rows)[0])
    return result


def prepare_fixture(fixture, *, source_evidence=None):
    """Return unchanged public fixture plus private occurrence mapping/proofs.

    No aliases are added without verified original DOM/CFO evidence.  The
    original native mapping remains available for regression, and added rows
    are only supplied to the explicitly new semantic assessor.
    """
    if source_evidence is not None:
        p.checked(source_evidence, "source_evidence")
    bundle, bindings = fixture["bundle"], fixture["native_bindings"]
    enriched = dict(bindings)
    existing = source_fact_bindings(bundle, bindings)
    coverage, added = [], []
    public = {row["source_id"]: row for row in bundle["public"]["sources"]}
    tables = _tables([fixture])
    for source_id, source in sorted(public.items()):
        if "record" in source:
            key = p.encode(
                {"source_id": source_id, "native_pointer": source["native_pointer"]}
            ).decode()
            candidates = existing.get(key, [])
            coverage.append(
                {
                    "source_id": source_id,
                    "status": "ORIGINAL_JSON_BOUND"
                    if len(candidates) == 1
                    else "UNRESOLVED_PUBLIC_JSON",
                    "original_fact_ids": candidates,
                    "public_source_retained": True,
                }
            )
        elif source_id not in tables:
            coverage.append(
                {
                    "source_id": source_id,
                    "status": "UNRESOLVED_PUBLIC_TABLE",
                    "reason": "source.original_table_parent_missing",
                    "public_source_retained": True,
                }
            )
    for table_id, table in sorted(tables.items()):
        source = public[table_id]
        p.require(
            source["raw_sha256"] == table["raw_sha256"]
            and source["original_url"] == table["original_url"]
            and source["native_table_xpath"] == table["table_xpath"]
            and source["original_rows"]
            == [[cell["text"] for cell in row] for row in table["structure"]["rows"]]
            and source["definition"] == table["structure"]["definition_quote"]
            and source["unit"] == "million USD",
            "source.public_whole_table_parent_join",
        )
        for header in table["structure"]["headers"]:
            common = {
                "source_id": table_id,
                "period_end": header["period_end"],
                "original_header": header,
                "table_record_id": table["id"],
            }
            try:
                column = _column(table, header)
                p.require(
                    source_evidence is not None and table_id in source_evidence["table_proofs"],
                    "source.original_source_evidence_required",
                )
                proof = source_evidence["table_proofs"][table_id]
                p.require(
                    proof["table_record_id"] == table["id"]
                    and proof["original_DOM_replayed"]
                    and proof["raw_sha256"] == table["raw_sha256"],
                    "source.table_proof_join",
                )
                p.require(
                    not proof["explicit_revision_markers"],
                    "source.explicit_revision_requires_new_semantic_proof",
                )
                p.require(
                    not proof["superscript_numeric_cells"], "source.numeric_annotation_unresolved"
                )
                start, end, filed, anchors = _anchor(
                    table, header, column, bindings, source_evidence
                )
                canonical = _canonical_column(table, start, end, bindings)
                for _, native in canonical:
                    canonical_proof = source_evidence["table_proofs"].get(native["table_id"])
                    p.require(
                        canonical_proof
                        and canonical_proof["table_record_id"] == native["table_record"]["id"]
                        and canonical_proof["original_DOM_replayed"]
                        and not canonical_proof["superscript_numeric_cells"]
                        and not canonical_proof["explicit_revision_markers"],
                        "source.canonical_revision_evidence_unresolved",
                    )
                    canonical_header = next(
                        item
                        for item in native["table_record"]["structure"]["headers"]
                        if item["period_end"] == end
                    )
                    canonical_values = _column(native["table_record"], canonical_header)
                    p.require(
                        [amount for amount, _ in canonical_values]
                        == [amount for amount, _ in column],
                        "source.original_report_column_revision_conflict",
                    )
                    canonical_start, canonical_end, _, _ = _anchor(
                        native["table_record"],
                        canonical_header,
                        canonical_values,
                        bindings,
                        source_evidence,
                    )
                    p.require(
                        [canonical_start, canonical_end] == [start, end],
                        "source.canonical_actual_period_conflict",
                    )
                p.require(
                    sum(amount for amount, _ in column[:-1]) == column[-1][0],
                    "source.original_signed_column_closure",
                )
                p.require(
                    all(
                        amount == issuer.Decimal(native["record"]["val"])
                        for (amount, _), (_, native) in zip(column, canonical, strict=True)
                    ),
                    "source.full_column_revision_conflict",
                )
                for (amount, reference), (canonical_id, native) in zip(
                    column, canonical, strict=True
                ):
                    locator = {
                        "source_id": table_id,
                        "cells": [
                            [cell["row"], cell["cell"]]
                            for cell in reference["cells"]
                            if cell["text"].strip() not in {"", "$"}
                        ],
                    }
                    key = p.encode(locator).decode()
                    known = existing.get(key, [])
                    p.require(len(known) <= 1, "source.existing_locator_ambiguous")
                    occurrence_id = (
                        known[0]
                        if known
                        else "fact_occurrence_"
                        + p.sha(p.encode([table["id"], locator, start, end, native["metric_id"]]))
                    )
                    evidence_row = p.record(
                        "source_occurrence",
                        rule=RULE,
                        original_fact_id=known[0] if known else None,
                        occurrence_fact_id=occurrence_id,
                        canonical_fact_id=canonical_id,
                        original_locator=locator,
                        original_cell_reference=reference,
                        original_table_proof_id=proof["id"],
                        original_raw_sha256=table["raw_sha256"],
                        original_raw_object_id=table["raw_object_id"],
                        original_document_id=table["original_document_id"],
                        canonical_raw_sha256=native["raw_sha256"],
                        canonical_locator={
                            "source_id": native["table_id"],
                            "cells": native["record"]["cell_reference"]["cells"],
                        },
                        entity_id=table["entity_id"],
                        metric_id=native["metric_id"],
                        source_definition_id=native["source_definition_id"],
                        definition_shape=table["definition_shape"],
                        actual_period=[start, end],
                        source_unit="million USD",
                        normalized_unit="million USD",
                        scale_factor="1",
                        source_accession=table["accession"],
                        canonical_accession=native["record"]["accn"],
                        actual_period_anchor_fact_ids=sorted(
                            {identifier for identifier, _ in anchors}
                        ),
                        actual_period_anchor_occurrences=[row for _, row in anchors],
                        revision_semantics=(
                            "same_definition_actual_period_and_complete_signed_reconciliation_"
                            "column_identical; report_occurrences_remain_distinct"
                        ),
                        numeric_equality_used_as_sole_alias_basis=False,
                        gold_value_used=False,
                    )
                    if not known:
                        new_native = copy.deepcopy(native)
                        new_native.update(
                            raw_sha256=table["raw_sha256"],
                            raw_object_id=table["raw_object_id"],
                            table_id=table_id,
                            table_record=table,
                            document_id="doc_task_issuer_" + table["raw_sha256"][:24],
                            pointer=table["table_xpath"]
                            + f"/tr[{reference['cells'][0]['row'] + 1}]@{end}",
                        )
                        new_native["record"].update(
                            val=str(amount),
                            start=start,
                            end=end,
                            accn=table["accession"],
                            filed=filed,
                            cell_reference=reference,
                        )
                        new_native["source_occurrence_proof_id"] = evidence_row["id"]
                        new_native["canonical_fact_id"] = canonical_id
                        enriched[occurrence_id] = new_native
                        added.append(evidence_row)
                        existing[key] = [occurrence_id]
                    coverage.append(
                        {
                            **common,
                            "locator": locator,
                            "status": "ORIGINAL_BOUND" if known else "PROVEN_REPEATED_OCCURRENCE",
                            "proof": evidence_row,
                        }
                    )
            except (ValueError, KeyError, TypeError, IndexError) as error:
                coverage.append(
                    {
                        **common,
                        "status": "UNRESOLVED_COLUMN",
                        "reason": str(error),
                        "public_source_retained": True,
                    }
                )
    table_scope = [
        {
            "source_id": identifier,
            "all_original_rows_publicly_accessible": True,
            "certified_reconciliation_row_indices": table["structure"]["selected_rows"],
            "other_rows_not_certified_as_financial_facts": [
                index
                for index in range(len(table["structure"]["rows"]))
                if index not in table["structure"]["selected_rows"]
            ],
        }
        for identifier, table in sorted(tables.items())
    ]
    boundary = p.record(
        "fixture_source_boundary",
        task_id=bundle["task_id"],
        bundle_id=bundle["id"],
        original_native_bindings_sha256=p.sha(p.encode(bindings)),
        enriched_native_bindings_sha256=p.sha(p.encode(enriched)),
        source_evidence_id=source_evidence["id"] if source_evidence else None,
        original_bound_locator_count=len(source_fact_bindings(bundle, bindings)),
        new_bound_locator_count=len(source_fact_bindings(bundle, enriched)),
        added_occurrences=added,
        coverage=coverage,
        counts=dict(Counter(row["status"] for row in coverage)),
        table_public_access_scope=table_scope,
        public_messages_unchanged=True,
        all_original_facts_retained=True,
        unknown_sources_removed=False,
        original_results_not_rewritten=True,
    )
    return {**fixture, "enriched_native_bindings": enriched, "source_boundary": boundary}


def coverage_report(prepared):
    """Metadata-only complete denominator; never choose tasks from this report."""
    return p.record(
        "source_coverage_report",
        task_count=len(prepared),
        task_ids=[row["identity"]["task_id"] for row in prepared],
        fixtures=[row["source_boundary"] for row in prepared],
        added_occurrences=sum(len(row["source_boundary"]["added_occurrences"]) for row in prepared),
        public_source_pruning=False,
        selection_uses_coverage=False,
        API_calls=0,
        GPU_operations=0,
        Student_outputs_read=False,
    )
