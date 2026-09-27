"""Compile the fixed evidence05 panel after a separately settled text/table review.

This is a new preparation contract, not a revision of the frozen panel_01 run.
The original selection, public projection, issuer joins and runtime controls are
reused without mutating their globals. Only evidence05 input routing and the
explicitly limited composition-review contract differ. No model/API/PDF access.
"""

import argparse
import importlib
import subprocess
from collections import Counter
from pathlib import Path

import cross_market_panel_20260926 as core
import cross_market_repaired_geometry_execution_20260926 as isolation
import run_cross_market_unit_encoding_revision_05_20260927 as financial05

base, p = core.base, core.p
SCRIPT = "trusted_data_synthesis/scripts/cross_market_panel_revision_05_20260927.py"
REVIEW_MODULE = "cross_market_text_table_review_revision_20260927"
REVIEW_SCRIPT = "trusted_data_synthesis/scripts/" + REVIEW_MODULE + ".py"
FRONTIER_MODULE = "cross_market_text_frontier_20260927"
FRONTIER_SCRIPT = "trusted_data_synthesis/scripts/" + FRONTIER_MODULE + ".py"
RAW = base.RAW / "panel_text_table_02"
FINANCIAL = financial05.RAW
ISSUER = base.RAW / "issuer_admission_01/admission.json"
PROTOCOL = "cross_market_panel_text_table_compilation_protocol"
COMPLETION = "cross_market_panel_text_table_compilation_completed"


def require(condition, reason):
    base.require(condition, "panel05." + reason)


def review_module():
    # The review implementation is a separate, prospectively committed contract.
    return importlib.import_module(REVIEW_MODULE)


def frontier_module():
    return importlib.import_module(FRONTIER_MODULE)


def review_bundle(path, financial_protocol_id):
    module = review_module()
    bundle = base.checked(base.read(path), module.BUNDLE_KIND)
    module.validate_bundle(bundle, financial_protocol_id)
    reviews = {row["task_id"]: row for row in bundle["reviews"]}
    require(len(reviews) == len(bundle["reviews"]), "unique_settled_task_reviews")
    return bundle, reviews


def compiler_namespace():
    module = review_module()
    namespace = isolation.isolated_namespace(core)
    namespace["require_composition_review"] = module.require_composition_review
    original_certificate = namespace["private_certificate"]

    def private_certificate(task, review_id):
        value = original_certificate(task, review_id)
        if task["group"] != "composition_required":
            return value
        body = {k: v for k, v in value.items() if k not in {"id", "schema_version"}}
        body.pop("source_exhaustion_review_id")
        body.update(
            source_text_table_review_id=review_id,
            source_review_scope=module.REVIEW_SCOPE,
            full_original_PDF_visual_exhaustion_claimed=False,
        )
        return core.relation_record("panel_composition_certificate", **body)

    namespace["private_certificate"] = private_certificate
    original_bundle = namespace["private_bundle"]

    def private_bundle(task, spec, public, review_id):
        value = original_bundle(task, spec, public, review_id)
        body = {k: v for k, v in value.items() if k not in {"id", "schema_version"}}
        body["validation"] = dict(body["validation"])
        body["validation"].pop("composition_source_exhaustion_review_id")
        body["validation"].update(
            composition_text_table_review_id=review_id,
            composition_review_scope=module.REVIEW_SCOPE,
            full_original_PDF_visual_exhaustion_claimed=False,
        )
        return core.relation_record("EvaluationTaskBundle", **body)

    namespace["private_bundle"] = private_bundle
    return namespace


def validate_selection_closure(candidates, documents, issuer, bundle, financial_protocol_id):
    """Prove unreviewed tail cannot alter the original deterministic front sixty."""
    review_module().validate_bundle(bundle, financial_protocol_id)
    frontier = frontier_module()
    items, _ = frontier.eligible_items(
        candidates, documents, core.statistics.admission_mapping(issuer), core.financial.METRICS
    )
    composition = [row for row in items if row["task"]["group"] == "composition_required"]
    eligible = {row["task"]["task_id"] for row in composition}
    closure = bundle["selection_closure"]
    listed_eligible = closure["eligible_candidate_task_ids"]
    rejected = closure["semantically_rejected_candidate_task_ids"]
    reviewed = closure["reviewed_candidate_task_ids"]
    require(
        closure["complete"] is True
        and len(listed_eligible) == len(set(listed_eligible))
        and set(listed_eligible) == eligible
        and len(rejected) == len(set(rejected))
        and set(rejected) <= eligible
        and len(reviewed) == len(set(reviewed))
        and set(rejected) <= set(reviewed) <= eligible,
        "closed_frontier_exact_eligible_and_settled_rejections",
    )
    selected = frontier.next_selected(composition, set(rejected))
    expected = [row["task"]["task_id"] for row in selected]
    reviews = {row["task_id"]: row for row in bundle["reviews"]}
    require(
        len(expected) == len(set(expected)) == 60
        and set(reviews) <= eligible
        and closure["selected_candidate_task_ids"] == expected
        and set(expected) <= set(reviewed)
        and all(task_id in reviews and reviews[task_id]["passed"] is True for task_id in expected)
        and not set(rejected)
        & {task_id for task_id, row in reviews.items() if row["passed"] is True},
        "optimistic_front_sixty_all_really_passed_no_unreviewed_exclusion",
    )
    for item in selected:
        review_module().require_composition_review(
            item["task"], documents, reviews, financial_protocol_id
        )
    return expected


def validate_financial_inputs(plan, summary, candidates):
    base.checked(plan, financial05.prior.PROTOCOL)
    base.checked(summary, financial05.prior.COMPLETION)
    base.checked(candidates, "cross_market_financial_task_candidates")
    require(
        plan["evidence_revision_number"] == 5
        and plan["document_count"] == len(plan["documents"]) == 440
        and plan["fixed_original_candidates"] == 9513
        and plan["fixed_supplementary_anchors"] == 20
        and plan["fixed_total_candidate_anchors"] == 9533
        and plan["maximum_anchor_scan_documents"] == plan["maximum_new_review_plans"] == 0
        and plan["public_metric_universe"] == list(core.financial.METRICS)
        and plan["quotas"] == core.QUOTAS,
        "exact_financial05_inputs_not_an_automatic_successor",
    )
    counts = Counter(row["group"] for row in candidates["candidates"])
    require(
        summary["protocol_id"] == candidates["protocol_id"] == plan["id"]
        and summary["status"] == "FINANCIAL_ENUMERATION_COMPLETE_NOT_EVALUATION_READY"
        and summary["documents"] == 440
        and summary["input_candidates"] == 9533
        and summary["original_input_candidates"] == 9513
        and summary["supplementary_input_candidates"] == 20
        and dict(counts) == summary["candidate_counts"]
        and all(counts[group] >= 60 for group in core.GROUPS),
        "completed_financial05_fixed_candidate_pool",
    )
    return dict(counts)


def register(root, review_path, output=RAW):
    root, output, review_path = (
        Path(root).resolve(),
        Path(output).resolve(),
        Path(review_path).resolve(),
    )
    require(output == RAW.resolve(), "fixed_new_panel_directory")
    require(review_path.is_relative_to(base.RAW.resolve()), "registered_local_review_input")
    if (output / "protocol.json").exists():
        value = protocol(root, output)
        require(
            value["source_text_table_reviews"] == core.reference(review_path),
            "same_registered_review_bundle",
        )
        return value
    financial_plan = base.read(FINANCIAL / "protocol.json")
    summary = base.read(FINANCIAL / "summary.json")
    candidates = base.read(FINANCIAL / "candidate_tasks.json")
    counts = validate_financial_inputs(financial_plan, summary, candidates)
    module = review_module()
    bundle, _ = review_bundle(review_path, financial_plan["id"])
    candidate_reference = core.reference(FINANCIAL / "candidate_tasks.json")
    require(
        {k: candidate_reference[k] for k in ("path", "bytes", "sha256")}
        == summary["candidate_tasks"],
        "financial05_candidate_receipt",
    )
    document_refs, documents = [], {}
    for item in financial_plan["documents"]:
        path = (
            FINANCIAL / "documents" / (base.sha(item["document"]["raw_object_id"])[:24] + ".json")
        )
        value = base.checked(base.read(path), "cross_market_financial_document")
        require(
            value["protocol_id"] == financial_plan["id"] and value["document"] == item["document"],
            "financial05_original_document_join",
        )
        document_refs.append(core.reference(path))
        documents[value["document"]["raw_object_id"]] = value
    issuer = base.checked(base.read(ISSUER), "cross_market_issuer_admission")
    core.statistics.admission_mapping(issuer)
    selected_composition = validate_selection_closure(
        candidates["candidates"], documents, issuer, bundle, financial_plan["id"]
    )
    reuse_path = base.PARENT / "reuse_admission.json"
    reuse = p.checked(base.read(reuse_path), "direction_calibration_material_admission")
    require(reuse["passed"] is True, "original_tokenizer_admitted")
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    names = sorted(
        set(financial_plan["sources"])
        | {
            SCRIPT,
            core.SCRIPT,
            financial05.SCRIPT,
            REVIEW_SCRIPT,
            FRONTIER_SCRIPT,
            isolation.SCRIPT,
            "trusted_data_synthesis/scripts/fixed_kernel_cross_market_runtime_20260926.py",
            "trusted_data_synthesis/scripts/cross_market_statistics_20260926.py",
        }
    )
    sources = {}
    for name in names:
        payload = (root / name).read_bytes()
        require(
            payload == subprocess.check_output(["git", "show", head + ":" + name], cwd=root),
            "committed_code_before_panel_registration",
        )
        sources[name] = base.sha(payload)
        if name in financial_plan["sources"]:
            require(
                sources[name] == financial_plan["sources"][name], "preserved_financial05_source"
            )
    value = base.record(
        PROTOCOL,
        at=base.now(),
        code_commit=head,
        sources=sources,
        financial_protocol_id=financial_plan["id"],
        financial_protocol=core.reference(FINANCIAL / "protocol.json"),
        financial_summary=core.reference(FINANCIAL / "summary.json"),
        candidates=candidate_reference,
        candidate_group_counts=counts,
        documents=document_refs,
        issuer_admission=core.reference(ISSUER),
        source_text_table_reviews=core.reference(review_path),
        source_text_table_review_bundle_id=bundle["id"],
        source_text_table_review_scope=module.REVIEW_SCOPE,
        composition_frontier_closed_selected_candidates=selected_composition,
        source_exhaustion_review_claim_replaced_not_forged=True,
        full_original_PDF_visual_exhaustion_claimed=False,
        tokenizer_binding=reuse["materials"]["assets"]["tokenizer_binding"],
        tokenizer_parent_admission=core.reference(reuse_path),
        runtime_binding=core.runtime.binding(),
        public_metric_universe=list(core.financial.METRICS),
        quotas=core.QUOTAS,
        selection_salt=core.SALT,
        selection=(
            "Unchanged issuer-target dedup; fixed latest publication/raw-object metadata; "
            "issuer hash roundrobin then endperiod/taskid; "
            "no replacement after selected input/control failure"
        ),
        source_scope=(
            "all qualified registered metrics in declared original report vintages/public periods; "
            "composition review limited to registered saved text/table domain"
        ),
        maximum_compiler_passes=1,
        maximum_scripted_control_executions=420,
        maximum_initial_prompt_tokenizations=180,
        actual_model_generation_calls=0,
        actual_model_scoring_cases=0,
        original_PDF_opens=0,
        image_reads=0,
        GPU_processes=0,
        network_requests=0,
        new_training_updates=0,
        evaluation_launch_authorized=False,
        prior_panel_01_preserved=True,
    )
    base.write(output / "protocol.json", value)
    return value


def protocol(root, output=RAW):
    output = Path(output).resolve()
    require(output == RAW.resolve(), "fixed_new_panel_directory")
    plan = base.checked(base.read(output / "protocol.json"), PROTOCOL)
    for name, digest in plan["sources"].items():
        require(base.sha(Path(root) / name) == digest, "frozen_source:" + name)
    require(
        plan["runtime_binding"] == core.runtime.binding()
        and plan["quotas"] == core.QUOTAS
        and plan["selection_salt"] == core.SALT
        and plan["public_metric_universe"] == list(core.financial.METRICS)
        and plan["source_text_table_review_scope"] == review_module().REVIEW_SCOPE
        and plan["maximum_compiler_passes"] == 1
        and plan["maximum_scripted_control_executions"] == 420
        and plan["maximum_initial_prompt_tokenizations"] == 180
        and plan["full_original_PDF_visual_exhaustion_claimed"] is False
        and plan["evaluation_launch_authorized"] is False,
        "fixed_runtime_quota_selection_and_review_scope",
    )
    return plan


def run(root, output=RAW):
    output = Path(output).resolve()
    plan = protocol(root, output)
    with base.locked(output / "run.lock"):
        if (output / "summary.json").exists():
            value = base.checked(base.read(output / "summary.json"), COMPLETION)
            require(value["protocol_id"] == plan["id"], "same_completed_compilation")
            return value
        require(
            not (output / "compilation_attempt.json").exists(), "unsettled_attempt_no_budget_reset"
        )
        candidates = core.read_reference(plan["candidates"])
        rows = [core.read_reference(reference) for reference in plan["documents"]]
        documents = {row["document"]["raw_object_id"]: row for row in rows}
        require(
            len(rows) == len(documents) == 440
            and all(row["protocol_id"] == plan["financial_protocol_id"] for row in rows),
            "exact_440_financial05_document_join",
        )
        issuer = core.read_reference(plan["issuer_admission"])
        review_reference = plan["source_text_table_reviews"]
        sealed_bundle = core.read_reference(review_reference)
        bundle, reviews = review_bundle(review_reference["path"], plan["financial_protocol_id"])
        require(
            bundle == sealed_bundle and bundle["id"] == plan["source_text_table_review_bundle_id"],
            "same_settled_review_bundle",
        )
        selected_composition = validate_selection_closure(
            candidates["candidates"], documents, issuer, bundle, plan["financial_protocol_id"]
        )
        require(
            selected_composition == plan["composition_frontier_closed_selected_candidates"],
            "same_frozen_composition_frontier",
        )
        base.write(
            output / "compilation_attempt.json",
            dict(protocol_id=plan["id"], attempt=1, at=base.now()),
        )
        from trusted_synthesis.experiments.qa_reasoning_share_training_preflight.tokenization import (  # noqa: E501
            load_tokenizer,
        )

        tokenizer = None

        def count_tokens(messages):
            nonlocal tokenizer
            if tokenizer is None:
                tokenizer = load_tokenizer(plan["tokenizer_binding"])
            rendered = tokenizer.apply_chat_template(
                [
                    dict(
                        role="system", content=core.runtime.SYSTEM + "\nRequested guidance: neutral"
                    ),
                    *messages,
                ],
                tokenize=False,
                add_generation_prompt=True,
            )
            return len(tokenizer(rendered, add_special_tokens=False, truncation=False)["input_ids"])

        namespace = compiler_namespace()
        report, prepared = namespace["compile_panel"](
            candidates["candidates"],
            documents,
            issuer,
            reviews,
            plan["financial_protocol_id"],
            plan["public_metric_universe"],
            count_tokens,
        )
        require(
            report.get("scripted_control_executions", 0) <= 420
            and report.get("input_tokenizations", 0) <= 180,
            "finite_compilation_work",
        )
        if report["passed"]:
            actual_composition = [
                item["candidate_task_id"]
                for item in prepared
                if item["spec"]["group"] == "composition_required"
            ]
            require(
                actual_composition == selected_composition,
                "compiled_composition_matches_closed_optimistic_frontier",
            )
        report.update(
            source_text_table_review_scope=plan["source_text_table_review_scope"],
            full_original_PDF_visual_exhaustion_claimed=False,
            old_panel_01_result_unchanged=True,
        )
        references = (
            namespace["publish_panel"](output, plan, report, prepared) if report["passed"] else None
        )
        value = base.record(
            COMPLETION,
            protocol_id=plan["id"],
            **report,
            evaluation_panel_references=references,
            evaluation_started=False,
            at=base.now(),
        )
        base.write(output / "summary.json", value)
        return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("register", "run", "status"))
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--reviews", type=Path)
    args = parser.parse_args()
    if args.action == "register":
        require(args.reviews is not None, "settled_text_table_reviews_required")
        value = register(args.root, args.reviews)
    elif args.action == "run":
        value = run(args.root)
    else:
        value = (
            base.read(RAW / "summary.json")
            if (RAW / "summary.json").exists()
            else protocol(args.root)
        )
    base.emit(
        dict(
            event="panel_text_table02_" + args.action,
            id=value["id"],
            status=value.get("status"),
            passed=value.get("passed", False),
        )
    )


if __name__ == "__main__":
    main()
