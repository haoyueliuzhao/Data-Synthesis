"""One newly authorized cached locator revision; no PDF, API or model access.

Preserve the prior 40/231-pending/68 result and its spent budget. Apply a frozen
locator-only extension uniformly to the same 440 documents / 9,513 anchors.
Financial definitions, source geometry, task kernels and quotas stay fixed.
"""

import argparse
import copy
import subprocess
from pathlib import Path

import cross_market_layout_qualification_20260926 as core
import cross_market_repaired_geometry_execution_20260926 as adapter

base = core.base
RAW = base.RAW / "original_evidence_revision_02" / "financial_locator_revision_03"
PREVIOUS = adapter.FINANCIAL
GEOMETRY = adapter.GEOMETRY
SCRIPT = "trusted_data_synthesis/scripts/run_cross_market_locator_revision_20260926.py"
LOCATOR_SCRIPT = "trusted_data_synthesis/scripts/cross_market_locator_revision_20260926.py"
KIND = "cross_market_layout_qualification_protocol"
COMPLETION = "cross_market_financial_qualification_completed"
EXPECTED_PRIOR_COUNTS = {"dual_sufficient": 40, "composition_required": 231, "other_financial": 68}


def ref(path):
    path = Path(path)
    base.require(
        path.resolve().is_relative_to(base.RAW.resolve()), "locator_revision_reference_root"
    )
    return dict(path=str(path), bytes=path.stat().st_size, sha256=base.sha(path))


def read_ref(reference):
    path = Path(reference["path"])
    base.require(ref(path) == reference, "locator_revision_immutable_parent")
    return base.read(path)


def save(path, value):
    base.require(Path(path).resolve().is_relative_to(RAW.resolve()), "locator_revision_output_root")
    base.write(path, value)


def validate_fixed_scope(parent, done, geometry, geometry_done):
    base.require(
        done["protocol_id"] == parent["id"]
        and done["documents"] == 440
        and done["input_candidates"] == 9513
        and done["candidate_counts"] == EXPECTED_PRIOR_COUNTS
        and done["status"] == "FINANCIAL_ENUMERATION_COMPLETE_NOT_EVALUATION_READY",
        "locator_revision_preserved_prior_result",
    )
    base.require(
        parent["document_count"] == len(parent["documents"]) == 440
        and parent["fixed_cached_candidates"] == 9513
        and parent["quotas"] == dict.fromkeys(core.old.GROUPS, 60),
        "locator_revision_fixed_population_and_quotas",
    )
    base.require(
        geometry_done["protocol_id"] == geometry["id"]
        and geometry_done["documents"] == 440
        and geometry_done["selected_pages"] == 7530
        and geometry_done["coverage_pages"] == 104439
        and geometry_done["original_blank_pages_rendered"] == 420
        and geometry_done["status"] == "GEOMETRY_COMPLETE_NOT_ADMITTED"
        and geometry["derived_geometry_view"] is True,
        "locator_revision_complete_same_geometry",
    )


def parent_inputs():
    references = {
        "prior_protocol": ref(PREVIOUS / "protocol.json"),
        "prior_completion": ref(PREVIOUS / "summary.json"),
        "prior_candidates": ref(PREVIOUS / "candidate_tasks.json"),
        "geometry_protocol": ref(GEOMETRY / "protocol.json"),
        "geometry_completion": ref(GEOMETRY / "summary.json"),
        "prior_review_protocol": ref(adapter.REVIEW / "protocol.json"),
        "prior_review_manifest": ref(adapter.REVIEW / "packet_manifest.json"),
    }
    parent = base.checked(read_ref(references["prior_protocol"]), KIND)
    done = base.checked(read_ref(references["prior_completion"]), COMPLETION)
    geometry = base.checked(
        read_ref(references["geometry_protocol"]), "cross_market_original_geometry_protocol"
    )
    geometry_done = base.checked(
        read_ref(references["geometry_completion"]), "cross_market_original_geometry_completed"
    )
    validate_fixed_scope(parent, done, geometry, geometry_done)
    base.require(
        parent["geometry_protocol"] == references["geometry_protocol"]
        and parent["geometry_completion"] == references["geometry_completion"]
        and done["candidate_tasks"] == references["prior_candidates"],
        "locator_revision_exact_parent_inputs",
    )
    review_plan = base.checked(
        read_ref(references["prior_review_protocol"]), "cross_market_source_review_protocol"
    )
    review_done = base.checked(
        read_ref(references["prior_review_manifest"]), "cross_market_source_review_packet_manifest"
    )
    base.require(
        review_plan["financial_protocol_id"] == parent["id"]
        and review_done["protocol_id"] == review_plan["id"]
        and review_done["any_source_review_certificate_created"] is False,
        "locator_revision_prior_materials_not_semantic_proof",
    )
    return parent, done, references


def register(root):
    if (RAW / "protocol.json").exists():
        return protocol(root)
    parent, done, references = parent_inputs()
    base.require(
        not list(RAW.glob("document_attempts/*.json"))
        and not (RAW / "enumeration_attempt.json").exists(),
        "locator_revision_no_unregistered_attempts",
    )
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    sources = dict(parent["sources"])
    for name in (SCRIPT, LOCATOR_SCRIPT, adapter.SCRIPT):
        payload = (root / name).read_bytes()
        base.require(
            payload == subprocess.check_output(["git", "show", head + ":" + name], cwd=root),
            "locator_revision_committed_code",
        )
        sources[name] = base.sha(payload)
    for name, digest in sources.items():
        base.require(base.sha(root / name) == digest, "locator_revision_unchanged_parent_code")
    # Reuse the same source/geometry references and scientific contract, not
    # the previous protocol identity or its already-consumed execution credit.
    body = {
        k: copy.deepcopy(v)
        for k, v in parent.items()
        if k not in {"id", "schema_version", "execution_adapter"}
    }
    body.update(
        at=base.now(),
        code_commit=head,
        sources=sources,
        parent_protocol_id=parent["id"],
        parent_completion=references["prior_completion"],
        parent_completion_id=done["id"],
        previous_execution_preserved=True,
        locator_revision=True,
        locator_revision_number=3,
        parent_references=references,
        authorization="User approved one separately registered cache-only header/label/date "
        "locator revision, without PDF rereads or quota changes.",
        additional_cached_document_attempts=440,
        maximum_cached_document_passes=440,
        maximum_attempts_per_cached_document=1,
        maximum_enumerations=1,
        maximum_rederived_observations=19026,
        prior_budget_consumed_not_reused=True,
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
        inspected_before_registration="Prior 40/231-pending/68 counts and four SHA-selected "
        "cached locator examples were inspected. Source-value blind design is not claimed; "
        "no Student outcomes and no production requalification before this registration.",
        locator_policy=dict(
            scope="Exact loss-fill display annotation for unchanged income labels; explicit "
            "annual/date evidence immediately above same-page title; "
            "split year+年度 header tokens; "
            "explicit YYYY年12月31日止年度 calendar annual expression.",
            maximum_above_title_lines=3,
            maximum_above_title_distance_points=60,
            original_geometry_unchanged=True,
            original_candidate_unchanged=True,
            discard_unknown_parentheticals=False,
            infer_year_from_metadata=False,
            change_value_sign=False,
            change_currency=False,
            bypass_source_review=False,
            maximum_prior_header_pages=4,
            line_vertical_center_tolerance_points=3,
            column_alignment_tolerance_points=38,
            financial_definitions_and_task_kernel_unchanged=True,
        ),
    )
    value = base.record(KIND, **body)
    save(RAW / "protocol.json", value)
    base.emit(dict(event="cache_locator_revision_registered", id=value["id"], documents=440))
    return value


def protocol(root):
    value = base.checked(base.read(RAW / "protocol.json"), KIND)
    base.require(
        value.get("locator_revision") is True
        and value["locator_revision_number"] == 3
        and value["additional_cached_document_attempts"] == 440
        and value["maximum_attempts_per_cached_document"] == 1
        and value["maximum_enumerations"] == 1
        and value["maximum_rederived_observations"] == 19026
        and value["maximum_additional_PDF_opens"] == 0
        and value["maximum_API_calls"] == 0
        and value["evaluation_authorized"] is False,
        "locator_revision_finite_scope",
    )
    for name, digest in value["sources"].items():
        base.require(base.sha(root / name) == digest, "locator_revision_frozen_code")
    parents = {k: read_ref(r) for k, r in value["parent_references"].items()}
    validate_fixed_scope(
        parents["prior_protocol"],
        parents["prior_completion"],
        parents["geometry_protocol"],
        parents["geometry_completion"],
    )
    base.require(
        value["documents"] == parents["prior_protocol"]["documents"]
        and value["quotas"] == parents["prior_protocol"]["quotas"],
        "locator_revision_no_document_or_quota_replacement",
    )
    return value


def execution_namespace():
    import cross_market_locator_revision_20260926 as locators

    ns = adapter.isolated_namespace(core, RAW=RAW, GEOMETRY=GEOMETRY)
    locators.install(ns)
    ns["protocol"] = protocol
    ns["save"] = save
    for name in (
        "financial_facts",
        "_fact",
        "document_qualify",
        "run",
        "year_columns",
        "unit_certificate",
    ):
        base.require(
            ns[name].__code__ is getattr(core, name).__code__,
            "locator_revision_preserved_core:" + name,
        )
    return ns


def run(root):
    return execution_namespace()["run"](root)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("register", "run", "status"))
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    if args.action == "register":
        value = register(args.root.resolve())
    elif args.action == "run":
        value = run(args.root.resolve())
    else:
        value = (
            base.read(RAW / "summary.json")
            if (RAW / "summary.json").exists()
            else protocol(args.root.resolve())
        )
    base.emit(
        dict(
            event="cache_locator_revision_" + args.action,
            id=value["id"],
            status=value.get("status"),
        )
    )


if __name__ == "__main__":
    main()
