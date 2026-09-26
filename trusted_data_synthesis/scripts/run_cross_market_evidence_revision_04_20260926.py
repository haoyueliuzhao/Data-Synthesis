"""Bounded audited engineering and direct-label anchor supplement, cache only.

Register before one uniform scan and one uniform financial pass. Original 9,513
anchors and all failures stay immutable; new anchors have separate provenance.
No PDF, render, parser, network, API, Student, scoring or training calls.
"""

import argparse
import copy
import subprocess
from collections import Counter
from decimal import InvalidOperation
from pathlib import Path

import cross_market_layout_qualification_20260926 as core
import cross_market_locator_revision_20260926 as v3
import cross_market_repaired_geometry_execution_20260926 as adapter
import run_cross_market_locator_revision_20260926 as previous

base = core.base
ROOT = base.RAW / "original_evidence_revision_02"
RAW = ROOT / "financial_evidence_revision_04"
PREVIOUS = previous.RAW
GEOMETRY = adapter.GEOMETRY
SCRIPT = "trusted_data_synthesis/scripts/run_cross_market_evidence_revision_04_20260926.py"
MODULES = (
    "trusted_data_synthesis/scripts/cross_market_row_binding_revision_20260926.py",
    "trusted_data_synthesis/scripts/cross_market_header_binding_revision_20260926.py",
    "trusted_data_synthesis/scripts/cross_market_anchor_supplement_20260926.py",
)
PROTOCOL = "cross_market_layout_qualification_protocol"
SCAN = "cross_market_direct_label_anchor_scan"
SCAN_DONE = "cross_market_direct_label_anchor_scan_completed"
FINANCIAL = "cross_market_financial_document"
COMPLETION = "cross_market_financial_qualification_completed"
MAX_NEW_ANCHORS = 1024
MAX_NEW_PER_DOCUMENT = 64
MAX_OBSERVATIONS = 2 * (9513 + MAX_NEW_ANCHORS)
AUDITS = (
    "dual_evidence_readonly_audit_manifest_20260926.json",
    "cost_anchor_audit_20260926.json",
    "gross_profit_anchor_audit_20260926.json",
    "dual_relation_gap_audit_20260926.json",
)


def ref(path):
    path = Path(path)
    return dict(path=str(path), bytes=path.stat().st_size, sha256=base.sha(path))


def read_ref(reference):
    path = Path(reference["path"])
    base.require(path.suffix == ".json" and ref(path) == reference, "evidence04_bound_JSON_cache")
    return base.read(path)


def save(path, value):
    base.require(Path(path).resolve().is_relative_to(RAW.resolve()), "evidence04_output_root")
    base.write(path, value)


def key_for(item):
    return base.sha(item["document"]["raw_object_id"])[:24]


def validate_parent(parent, done, geometry_done):
    base.require(
        parent["document_count"] == len(parent["documents"]) == done["documents"] == 440
        and done["protocol_id"] == parent["id"]
        and done["input_candidates"] == 9513
        and done["candidate_counts"]
        == dict(dual_sufficient=40, composition_required=417, other_financial=158)
        and parent["quotas"] == dict.fromkeys(core.old.GROUPS, 60),
        "evidence04_same_prior_scope",
    )
    base.require(
        geometry_done["status"] == "GEOMETRY_COMPLETE_NOT_ADMITTED"
        and geometry_done["documents"] == 440
        and geometry_done["coverage_pages"] == 104439
        and geometry_done["selected_pages"] == 7530
        and geometry_done["original_blank_pages_rendered"] == 420,
        "evidence04_complete_fixed_geometry",
    )


def register(root):
    if (RAW / "protocol.json").exists():
        return protocol(root)
    references = {
        "prior_protocol": ref(PREVIOUS / "protocol.json"),
        "prior_completion": ref(PREVIOUS / "summary.json"),
        "prior_candidates": ref(PREVIOUS / "candidate_tasks.json"),
        "geometry_protocol": ref(GEOMETRY / "protocol.json"),
        "geometry_completion": ref(GEOMETRY / "summary.json"),
    }
    public = (
        root
        / "trusted_data_synthesis/artifacts/qa_vnext_fixed_kernel_value"
        / "cross_market_calibration_20260926/public"
    )
    references.update({name: ref(public / name) for name in AUDITS})
    parent = base.checked(read_ref(references["prior_protocol"]), PROTOCOL)
    done = base.checked(read_ref(references["prior_completion"]), COMPLETION)
    geometry_done = base.checked(
        read_ref(references["geometry_completion"]), "cross_market_original_geometry_completed"
    )
    validate_parent(parent, done, geometry_done)
    base.require(
        parent["geometry_protocol"] == references["geometry_protocol"]
        and parent["geometry_completion"] == references["geometry_completion"],
        "evidence04_same_geometry_refs",
    )
    base.require(
        not list(RAW.glob("*attempts/*.json")) and not (RAW / "enumeration_attempt.json").exists(),
        "evidence04_no_unregistered_attempts",
    )
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    sources = dict(parent["sources"])
    for name in (SCRIPT, *MODULES):
        payload = (root / name).read_bytes()
        base.require(
            payload == subprocess.check_output(["git", "show", head + ":" + name], cwd=root),
            "evidence04_committed_code",
        )
        sources[name] = base.sha(payload)
    for name, digest in sources.items():
        base.require(base.sha(root / name) == digest, "evidence04_preserved_prior_code")
    body = {
        k: copy.deepcopy(v)
        for k, v in parent.items()
        if k
        not in {
            "schema_version",
            "id",
            "execution_adapter",
            "locator_policy",
            "locator_revision_number",
            "locator_revision",
            "parent_references",
            "maximum_rederived_observations",
        }
    }
    body.update(
        at=base.now(),
        code_commit=head,
        sources=sources,
        evidence_revision_number=4,
        parent_protocol_id=parent["id"],
        parent_completion=references["prior_completion"],
        parent_completion_id=done["id"],
        parent_references=references,
        authorization="User requested continuing repairs and experiments after the complete "
        "read-only audit; register cache-only engineering and separately marked direct-label "
        "anchor additions. No quota, source roster, model or task-kernel change.",
        fixed_original_candidates=9513,
        maximum_anchor_scan_documents=440,
        maximum_new_anchors=MAX_NEW_ANCHORS,
        maximum_new_anchors_per_document=MAX_NEW_PER_DOCUMENT,
        maximum_total_candidate_anchors=9513 + MAX_NEW_ANCHORS,
        additional_cached_document_attempts=440,
        maximum_cached_document_passes=440,
        maximum_attempts_per_cached_document=1,
        maximum_enumerations=1,
        maximum_rederived_observations=MAX_OBSERVATIONS,
        prior_budget_consumed_not_reused=True,
        literal_supplement_labels=["Revenues", "Cost of revenue", "Cost of revenues"],
        source_candidate_pool_is_explicitly_extended=True,
        original_9513_records_unchanged=True,
        supplement_scan_is_not_financial_admission=True,
        inferred_or_unlabeled_revenue_supplement=False,
        cost_of_goods_sold_mapping_authorized=False,
        maximum_additional_PDF_opens=0,
        maximum_additional_renders=0,
        maximum_API_calls=0,
        maximum_new_review_plans=0,
        original_PDF_opens=0,
        parser_calls=0,
        network_requests=0,
        GPU_processes=0,
        model_calls=0,
        scoring_calls=0,
        new_training_updates=0,
        evaluation_authorized=False,
        data_adaptive_engineering_revision=True,
        Student_outcomes_consulted=False,
        inspected_before_registration="Audit of all 208 failed cost/GP anchors and 18 recorded "
        "relation gaps, plus prior candidate counts. Not source-value-blind; no Student Q.",
        repair_policy=dict(
            display_labels="Exact registered English/Chinese bilingual pairs and exact减:营业成本; "
            "not arbitrary CJK/parenthetical deletion or financial-definition merging.",
            header="Bounded explicit title/date/unit grammar with source word evidence; "
            "ordinal days and short date columns require original printed annual evidence.",
            notes="Bounded compound note references in an independently located Notes column; "
            "do not truncate rightmost numbers or rewrite original geometry.",
            unresolved="Restatement, unadjudicated scope/version changes, multi-semantic columns, "
            "quarterly/summary sources and unlabeled subtotals remain gated.",
            financial_math_and_task_kernel_unchanged=True,
        ),
    )
    value = base.record(PROTOCOL, **body)
    save(RAW / "protocol.json", value)
    base.emit(dict(event="evidence04_registered", id=value["id"]))
    return value


def protocol(root):
    plan = base.checked(base.read(RAW / "protocol.json"), PROTOCOL)
    base.require(
        plan["evidence_revision_number"] == 4
        and plan["document_count"] == 440
        and len(plan["documents"]) == 440
        and plan["maximum_new_anchors"] == 1024
        and plan["maximum_new_anchors_per_document"] == 64
        and plan["maximum_cached_document_passes"] == 440
        and plan["maximum_enumerations"] == 1
        and plan["maximum_rederived_observations"] == 21074
        and plan["maximum_additional_PDF_opens"] == plan["maximum_API_calls"] == 0
        and not plan["evaluation_authorized"],
        "evidence04_fixed_budget",
    )
    for name, digest in plan["sources"].items():
        base.require(base.sha(root / name) == digest, "evidence04_frozen_code")
    parents = {name: read_ref(value) for name, value in plan["parent_references"].items()}
    validate_parent(
        parents["prior_protocol"], parents["prior_completion"], parents["geometry_completion"]
    )
    base.require(
        plan["documents"] == parents["prior_protocol"]["documents"], "evidence04_same_440_inputs"
    )
    return plan


def reserve(plan, directory, key):
    attempt = RAW / directory / (key + ".json")
    base.require(not attempt.exists(), "evidence04_unsettled_attempt_no_automatic_retry")
    base.require(
        len(list((RAW / directory).glob("*.json"))) < 440, "evidence04_document_attempt_cap"
    )
    save(attempt, dict(protocol_id=plan["id"], at=base.now(), document_key=key, attempt=1))


def scan(root):
    import cross_market_anchor_supplement_20260926 as supplement

    plan = protocol(root)
    with base.locked(RAW / "scan.lock"):
        if (RAW / "scan_summary.json").exists():
            value = base.checked(base.read(RAW / "scan_summary.json"), SCAN_DONE)
            base.require(value["protocol_id"] == plan["id"], "evidence04_scan_parent")
            return value
        records, total = [], 0
        for index, item in enumerate(plan["documents"], 1):
            key = key_for(item)
            destination = RAW / "anchors" / (key + ".json")
            if destination.exists():
                result = base.checked(base.read(destination), SCAN)
                base.require(
                    result["protocol_id"] == plan["id"] and result["document"] == item["document"],
                    "evidence04_existing_scan_identity",
                )
            else:
                reserve(plan, "scan_attempts", key)
                extraction = base.checked(read_ref(item["extraction"]), "PDF_extraction_result")
                geometry = base.checked(
                    read_ref(item["geometry"]), "cross_market_original_PDF_geometry"
                )
                base.require(
                    extraction["document"] == geometry["document"] == item["document"],
                    "evidence04_scan_document_identity",
                )
                result = base.record(
                    SCAN,
                    protocol_id=plan["id"],
                    document=item["document"],
                    input_references={k: item[k] for k in ("extraction", "geometry")},
                    **supplement.scan_document(extraction, geometry, item["document"]),
                )
                save(destination, result)
            count = len(result["new_anchors"])
            base.require(count <= MAX_NEW_PER_DOCUMENT, "evidence04_document_anchor_cap")
            total += count
            base.require(total <= MAX_NEW_ANCHORS, "evidence04_global_anchor_cap_no_truncation")
            records.append(ref(destination))
            if index % 80 == 0:
                base.emit(dict(event="evidence04_anchor_scan", documents=index, new_anchors=total))
        result = base.record(
            SCAN_DONE,
            at=base.now(),
            protocol_id=plan["id"],
            status="DIRECT_LABEL_ANCHORS_SCANNED_NOT_ADMITTED",
            documents=440,
            original_anchors=9513,
            added_anchors=total,
            total_anchors=9513 + total,
            results=records,
            original_PDF_opens=0,
            parser_calls=0,
            original_candidates_unchanged=True,
            qa_eligible=False,
        )
        save(RAW / "scan_summary.json", result)
        base.emit({k: v for k, v in result.items() if k != "results"})
        return result


def namespace():
    import cross_market_header_binding_revision_20260926 as header
    import cross_market_row_binding_revision_20260926 as row

    ns = adapter.isolated_namespace(core)
    v3.install(ns)
    header.install_header_namespace(ns)
    row.install_row_namespace(ns)
    base.require(
        ns["financial_facts"].__code__ is core.financial_facts.__code__
        and ns["_fact"].__code__ is core._fact.__code__,
        "evidence04_financial_core_unchanged",
    )
    return ns


def verify_supplementary_binding(candidate, facts):
    """A new exact locator cannot take credit for another same-label source row."""
    source = candidate["source_geometry_anchor_provenance"]
    expected_row = source["geometry_line_index"]
    row_words = set(source["row_word_indices"])
    for fact in facts:
        certificate = fact["evidence"]["independent_row_column_certificate"]
        label_words = certificate["row_binding_revision_evidence"]["original_label_words"]
        base.require(
            certificate["page"] == source["page_number"]
            and certificate["row_start"] == certificate["row"] == expected_row
            and set(certificate["candidate_word_indices"]) <= row_words
            and [w["original_word_index"] for w in label_words] == source["label_word_indices"],
            "evidence04_supplementary_anchor_cannot_rebind_another_row",
        )


def qualify_document(plan, item, anchor_reference, ns):
    key = key_for(item)
    destination = RAW / "documents" / (key + ".json")
    if destination.exists():
        result = base.checked(base.read(destination), FINANCIAL)
        base.require(
            result["protocol_id"] == plan["id"]
            and result["document"] == item["document"]
            and result["input_references"]["supplementary_anchors"] == anchor_reference,
            "evidence04_existing_financial_identity",
        )
        return result
    reserve(plan, "document_attempts", key)
    extraction = base.checked(read_ref(item["extraction"]), "PDF_extraction_result")
    geometry = base.checked(read_ref(item["geometry"]), "cross_market_original_PDF_geometry")
    audit = base.checked(read_ref(item["audit"]), "cross_market_PDF_evidence_audit")
    text = base.checked(read_ref(item["text_bundle"]), "cross_market_original_PDF_page_text")
    anchors = base.checked(read_ref(anchor_reference), SCAN)
    doc = item["document"]
    base.require(
        extraction["document"]
        == geometry["document"]
        == audit["document"]
        == anchors["document"]
        == doc
        and anchors["protocol_id"] == plan["id"]
        and text["raw_sha256"] == doc["sha256"],
        "evidence04_financial_input_identity",
    )
    reviews = {r["candidate_id"]: r for r in audit["candidate_reviews"]}
    reviews.update({r["candidate_id"]: r for r in anchors["mechanical_reviews"]})
    original = extraction["parsed"]["candidates"]
    added = anchors["new_anchors"]
    new_ids = {r["candidate_id"] for r in added}
    base.require(
        len(new_ids) == len(added) and not new_ids & {r["candidate_id"] for r in original},
        "evidence04_distinct_new_anchors",
    )
    qualified, rejected, adjudications = {}, [], []
    prepared = ns["prepared_geometry"](geometry)
    for candidate in [*original, *added]:
        extra = candidate["candidate_id"] in new_ids
        origin = (
            "supplementary_direct_label_geometry_anchor" if extra else "original_9513_parser_anchor"
        )
        try:
            facts = ns["financial_facts"](
                candidate, doc, reviews[candidate["candidate_id"]], geometry, prepared
            )
            if extra:
                verify_supplementary_binding(candidate, facts)
            for fact in facts:
                fact["anchor_origin"] = origin
                fact["source_anchor_lineage"] = [
                    dict(candidate_id=candidate["candidate_id"], anchor_origin=origin)
                ]
                if extra:
                    fact["supplementary_anchor_provenance"] = copy.deepcopy(candidate)
                    fact["source_anchor_lineage"][0]["supplementary_anchor_reference"] = (
                        anchor_reference
                    )
                    fact["new_anchor_scan_did_not_imply_admission"] = True
                if fact["fact_id"] not in qualified:
                    qualified[fact["fact_id"]] = fact
                else:
                    qualified[fact["fact_id"]]["original_candidate_bindings"].extend(
                        fact["original_candidate_bindings"]
                    )
                    qualified[fact["fact_id"]]["source_anchor_lineage"].extend(
                        fact["source_anchor_lineage"]
                    )
            adjudications.append(
                dict(
                    candidate_id=candidate["candidate_id"],
                    anchor_origin=origin,
                    status="ORIGINAL_ANCHOR_ROW_INDEPENDENTLY_REDERIVED"
                    if not extra
                    else "SUPPLEMENTARY_ANCHOR_ROW_INDEPENDENTLY_REDERIVED",
                    fact_ids=[f["fact_id"] for f in facts],
                    input_anchor_unchanged=True,
                )
            )
        except (ValueError, KeyError, TypeError, InvalidOperation) as error:
            rejected.append(
                dict(
                    candidate_id=candidate["candidate_id"],
                    metric_id=candidate["matched_metric_id"],
                    anchor_origin=origin,
                    reason=str(error),
                )
            )
            adjudications.append(
                dict(
                    candidate_id=candidate["candidate_id"],
                    anchor_origin=origin,
                    status="UNRESOLVED_OR_OUTSIDE_SCOPE",
                    reason=str(error),
                    input_anchor_unchanged=True,
                )
            )
    facts = list(qualified.values())
    base.require(len(facts) <= 2 * len(adjudications), "evidence04_document_observation_bound")
    usable, conflicts = core.old.unique_facts(facts)
    result = base.record(
        FINANCIAL,
        protocol_id=plan["id"],
        document=doc,
        input_references={k: item[k] for k in ("extraction", "audit", "text_bundle", "geometry")}
        | dict(supplementary_anchors=anchor_reference),
        status="FINANCIAL_PASS_COMPLETE_ISSUER_AND_TASK_GATES_PENDING",
        original_anchor_count=len(original),
        supplementary_anchor_count=len(added),
        qualified_facts=facts,
        candidate_adjudications=adjudications,
        usable_fact_ids=[f["fact_id"] for f in usable.values()],
        rejected_candidates=rejected,
        observation_conflicts=conflicts,
        aggregate_review=core.old.aggregate_locators({p["page"]: p["text"] for p in text["pages"]}),
        qa_eligible=False,
    )
    save(destination, result)
    return result


def qualify(root):
    plan = protocol(root)
    scanned = base.checked(base.read(RAW / "scan_summary.json"), SCAN_DONE)
    base.require(
        scanned["protocol_id"] == plan["id"]
        and scanned["documents"] == 440
        and scanned["added_anchors"] <= MAX_NEW_ANCHORS,
        "evidence04_completed_scan_required",
    )
    with base.locked(RAW / "qualification.lock"):
        if (RAW / "summary.json").exists():
            value = base.checked(base.read(RAW / "summary.json"), COMPLETION)
            base.require(value["protocol_id"] == plan["id"], "evidence04_existing_summary_identity")
            return value
        anchor_refs = {Path(r["path"]).stem: r for r in scanned["results"]}
        ns, documents = namespace(), []
        for index, item in enumerate(plan["documents"], 1):
            documents.append(qualify_document(plan, item, anchor_refs[key_for(item)], ns))
            if index % 40 == 0:
                base.emit(
                    dict(event="evidence04_financial_documents_saved", count=index, total=440)
                )
        task_path = RAW / "candidate_tasks.json"
        if task_path.exists():
            tasks = base.checked(base.read(task_path), "cross_market_financial_task_candidates")
            base.require(tasks["protocol_id"] == plan["id"], "evidence04_existing_task_identity")
        else:
            attempt = RAW / "enumeration_attempt.json"
            base.require(not attempt.exists(), "evidence04_enumeration_unsettled_no_retry")
            save(attempt, dict(protocol_id=plan["id"], at=base.now(), attempt=1))
            candidates, rejects = core.old.compile_candidates(documents)
            tasks = base.record(
                "cross_market_financial_task_candidates",
                protocol_id=plan["id"],
                candidates=candidates,
                rejected_relations=rejects,
                qa_eligible=False,
                issuer_admitted=False,
                source_exhaustion_admitted=False,
            )
            save(task_path, tasks)
        facts = [f for d in documents for f in d["qualified_facts"]]
        adj = [a for d in documents for a in d["candidate_adjudications"]]
        rejects = [r for d in documents for r in d["rejected_candidates"]]
        base.require(
            sum(d["original_anchor_count"] for d in documents) == 9513
            and sum(d["supplementary_anchor_count"] for d in documents) == scanned["added_anchors"]
            and len(adj) == scanned["total_anchors"]
            and len(facts) <= MAX_OBSERVATIONS,
            "evidence04_exact_total_bounds",
        )
        counts = Counter(t["group"] for t in tasks["candidates"])
        value = base.record(
            COMPLETION,
            at=base.now(),
            protocol_id=plan["id"],
            status="FINANCIAL_ENUMERATION_COMPLETE_NOT_EVALUATION_READY",
            documents=440,
            input_candidates=len(adj),
            original_input_candidates=9513,
            supplementary_input_candidates=scanned["added_anchors"],
            financially_qualified_issuer_pending_facts=len(facts),
            independently_rederived_source_observations=len(facts),
            candidate_status_counts=dict(Counter(t["status"] for t in tasks["candidates"])),
            anchor_status_counts=dict(Counter(a["status"] for a in adj)),
            supplementary_qualified_facts=sum(
                any(
                    a["anchor_origin"] == "supplementary_direct_label_geometry_anchor"
                    for a in f["source_anchor_lineage"]
                )
                for f in facts
            ),
            public_metric_coverage={
                m: sum(f["metric_id"] == m for f in facts) for m in core.old.METRICS
            },
            rejected_candidates=len(rejects),
            rejection_reasons=dict(Counter(r["reason"] for r in rejects)),
            candidate_counts={g: counts[g] for g in core.old.GROUPS},
            relation_rejections=len(tasks["rejected_relations"]),
            quotas=plan["quotas"],
            candidate_tasks=ref(task_path),
            anchor_scan=ref(RAW / "scan_summary.json"),
            panel_ready=False,
            issuer_admitted_tasks=0,
            admitted_composition_source_exhaustion_tasks=0,
            original_candidates_unchanged=True,
            prior_results_preserved=True,
            original_PDF_opens=0,
            parser_calls=0,
            network_requests=0,
            API_calls=0,
            GPU_processes=0,
            model_sessions=0,
            new_training_updates=0,
        )
        save(RAW / "summary.json", value)
        base.emit({k: v for k, v in value.items() if k != "candidate_tasks"})
        return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("register", "scan", "qualify"))
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    {"register": register, "scan": scan, "qualify": qualify}[args.action](args.root.resolve())


if __name__ == "__main__":
    main()
