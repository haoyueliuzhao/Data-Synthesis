"""Recompile the same frozen 180 tasks with reversible financial public compaction.

No source re-review, API, training, task replacement, truncation or relaxed input
limit. The prior failed compilation remains immutable. Runtime/scorer unchanged.
"""

import argparse
import copy
import subprocess
from pathlib import Path

import cross_market_compact_public_20260927 as compact
import cross_market_panel_revision_05_20260927 as previous

base, core = previous.base, previous.core
RAW = base.RAW / "panel_compact_03"
SCRIPT = "trusted_data_synthesis/scripts/cross_market_panel_compact_20260927.py"
PROTOCOL = "cross_market_panel_compact_protocol"
COMPLETION = "cross_market_panel_compact_completed"


def require(value, reason):
    base.require(value, "panel_compact." + reason)


def inputs(plan):
    candidates = core.read_reference(plan["candidates"])
    documents = {
        row["document"]["raw_object_id"]: row
        for reference in plan["documents"]
        for row in [core.read_reference(reference)]
    }
    issuer = core.read_reference(plan["issuer_admission"])
    bundle, reviews = previous.review_bundle(
        plan["source_text_table_reviews"]["path"], plan["financial_protocol_id"]
    )
    return candidates, documents, issuer, bundle, reviews


def selected_original(plan, loaded):
    candidates, documents, issuer, _, reviews = loaded
    selected, counts, rejected = previous.compiler_namespace()["choose_tasks"](
        candidates["candidates"],
        documents,
        core.statistics.admission_mapping(issuer),
        reviews,
        plan["financial_protocol_id"],
        plan["public_metric_universe"],
    )
    return selected, counts, rejected


def selection_binding(selected):
    return [
        dict(
            task_id=row["spec"]["task_id"],
            candidate_task_id=row["task"]["task_id"],
            group=row["task"]["group"],
            public_sha256=base.sha(base.encode(row["public"])),
            visible_fact_ids=[fact["fact_id"] for fact in row["visible"]],
        )
        for row in selected
    ]


def register(root):
    if (RAW / "protocol.json").exists():
        return protocol(root)
    parent = previous.protocol(root)
    failed = base.checked(base.read(previous.RAW / "summary.json"), previous.COMPLETION)
    require(
        failed["protocol_id"] == parent["id"]
        and failed["passed"] is False
        and failed["status"] == "BLOCKED_SELECTED_INPUT_OR_SCRIPTED_CONTROL"
        and len(failed["checks"]) == 180
        and failed["scripted_control_executions"] == 420
        and all(
            control["expected"] is control["observed"]
            for row in failed["checks"]
            for control in row["controls"]
        ),
        "preserved_length_only_failed_parent",
    )
    require(
        not (base.RAW / "evaluation_01/protocol.json").exists(),
        "no_evaluation_started_before_representation_revision",
    )
    selected, _, _ = selected_original(parent, inputs(parent))
    require(
        [row["spec"]["task_id"] for row in selected] == failed["selected_task_ids"],
        "same_selected_180_order_before_compaction",
    )
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    sources = dict(parent["sources"])
    for name in (SCRIPT, compact.SCRIPT):
        payload = (root / name).read_bytes()
        require(
            payload == subprocess.check_output(["git", "show", head + ":" + name], cwd=root),
            "committed_revision_before_registration",
        )
        sources[name] = base.sha(payload)
    body = {k: copy.deepcopy(v) for k, v in parent.items() if k not in {"id", "schema_version"}}
    body.update(
        at=base.now(),
        code_commit=head,
        sources=sources,
        parent_panel_protocol=core.reference(previous.RAW / "protocol.json"),
        parent_failed_summary=core.reference(previous.RAW / "summary.json"),
        selected_original_binding=selection_binding(selected),
        compact_policy=compact.POLICY,
        maximum_initial_prompt_tokens=18432,
        model_context_limit=24576,
        maximum_compiler_passes=1,
        maximum_scripted_control_executions=420,
        maximum_initial_prompt_tokenizations=180,
        audit_storage="Every selected original public view, reversible projection audit and "
        "projected digest retained under audit/, never sent as extra model context.",
        representation_revision="Same source rows/order and financial data, definitions, headers, "
        "periods, currency, document versions and canonical native identities. Opaque public "
        "read indices are deterministic short aliases. Shared document dictionaries replace "
        "repeated definitions/header text; pure audit metadata moves out of the prompt.",
        interpretation="This is a declared new common public representation before any Student "
        "generation, not byte-identical prompts or a guarantee of identical model behavior.",
        no_task_replacement=True,
        no_financial_source_filter_change=True,
        no_token_truncation=True,
        original_failed_compilation_unchanged=True,
        runtime_and_scorer_unchanged=True,
        actual_model_generation_calls=0,
        actual_model_scoring_cases=0,
        network_requests=0,
        GPU_processes=0,
        new_training_updates=0,
        new_source_semantic_API_calls=0,
    )
    plan = base.record(PROTOCOL, **body)
    base.write(RAW / "protocol.json", plan)
    return plan


def protocol(root):
    plan = base.checked(base.read(RAW / "protocol.json"), PROTOCOL)
    for name, digest in plan["sources"].items():
        require(base.sha(root / name) == digest, "frozen_code:" + name)
    require(
        core.reference(previous.RAW / "protocol.json") == plan["parent_panel_protocol"]
        and core.reference(previous.RAW / "summary.json") == plan["parent_failed_summary"]
        and plan["runtime_binding"] == core.runtime.binding()
        and plan["compact_policy"] == compact.POLICY
        and plan["maximum_initial_prompt_tokens"] == 18432,
        "same_parent_failure_runtime_and_limit",
    )
    return plan


def compiler_namespace():
    namespace = previous.compiler_namespace()
    original_sources = namespace["public_sources"]

    def public_sources(spec, document_facts, metric_universe):
        public, visible = original_sources(spec, document_facts, metric_universe)
        projected, audit = compact.compact(public)
        require(compact.restore(projected, audit) == public, "exact_public_restoration")
        core.runtime.SourceViewSources(projected)
        return projected, visible

    namespace["public_sources"] = public_sources
    return namespace


def run(root):
    plan = protocol(root)
    with base.locked(RAW / "run.lock"):
        if (RAW / "summary.json").exists():
            value = base.checked(base.read(RAW / "summary.json"), COMPLETION)
            require(value["protocol_id"] == plan["id"], "same_completed_revision")
            return value
        require(not (RAW / "compilation_attempt.json").exists(), "unsettled_no_budget_reset")
        loaded = inputs(plan)
        candidates, documents, issuer, review_bundle, reviews = loaded
        original, _, _ = selected_original(plan, loaded)
        require(
            selection_binding(original) == plan["selected_original_binding"],
            "unchanged_full_180_financial_selection",
        )
        previous.validate_selection_closure(
            candidates["candidates"],
            documents,
            issuer,
            review_bundle,
            plan["financial_protocol_id"],
        )
        from trusted_synthesis.experiments.qa_reasoning_share_training_preflight.tokenization import (  # noqa: E501
            load_tokenizer,
        )

        tokenizer = load_tokenizer(plan["tokenizer_binding"])

        def count_tokens(messages):
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

        base.write(
            RAW / "compilation_attempt.json", dict(protocol_id=plan["id"], attempt=1, at=base.now())
        )
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
        expected = [row["task_id"] for row in plan["selected_original_binding"]]
        require(
            report.get("selected_task_ids") == expected
            and report.get("scripted_control_executions") == 420
            and report.get("input_tokenizations") == 180,
            "same_selected_tasks_and_fixed_checks",
        )
        archives = []
        for row in original:
            tid = row["spec"]["task_id"]
            projected, audit = compact.compact(row["public"])
            require(
                compact.restore(projected, audit) == row["public"], "archived_exact_restoration"
            )
            stem = tid.split(":", 1)[1]
            original_path, audit_path = (
                RAW / "audit/original_public" / (stem + ".json"),
                RAW / "audit/projections" / (stem + ".json"),
            )
            base.write(original_path, row["public"])
            base.write(audit_path, audit)
            archives.append(
                dict(
                    task_id=tid,
                    original_public=core._asset_reference(original_path),
                    projection_audit=core._asset_reference(audit_path),
                    compact_public_sha256=base.sha(base.encode(projected)),
                    source_rows=len(projected["sources"]),
                    exact_restoration=True,
                )
            )
        if report["passed"]:
            for item, original_item in zip(prepared, original, strict=True):
                require(
                    item["candidate_task_id"] == original_item["task"]["task_id"]
                    and set(item["native_bindings"])
                    == {v["fact_id"] for v in original_item["visible"]},
                    "no_candidate_or_native_binding_change",
                )
                require(
                    item["bundle"]["public"] == compact.compact(original_item["public"])[0],
                    "published_same_compact_view",
                )
        base.write(
            RAW / "projection_audit_manifest.json",
            base.record(
                "cross_market_public_compaction_audit",
                protocol_id=plan["id"],
                tasks=archives,
                original_rows_and_financial_information_preserved=True,
            ),
        )
        before = core.read_reference(plan["parent_failed_summary"])
        report.update(
            source_text_table_review_scope=plan["source_text_table_review_scope"],
            full_original_PDF_visual_exhaustion_claimed=False,
            compact_policy=compact.POLICY,
            same_selected_tasks_as_failed_parent=True,
            original_public_roundtrip_checked=180,
            original_max_prompt_tokens=max(r["initial_prompt_tokens"] for r in before["checks"]),
            compact_max_prompt_tokens=max(r["initial_prompt_tokens"] for r in report["checks"]),
            projection_audit=core.reference(RAW / "projection_audit_manifest.json"),
        )
        references = (
            namespace["publish_panel"](RAW, plan, report, prepared) if report["passed"] else None
        )
        value = base.record(
            COMPLETION,
            protocol_id=plan["id"],
            **report,
            evaluation_panel_references=references,
            evaluation_started=False,
            at=base.now(),
        )
        base.write(RAW / "summary.json", value)
        return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("register", "run", "status"))
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    value = (
        base.read(RAW / "summary.json")
        if args.action == "status"
        else globals()[args.action](args.root.resolve())
    )
    base.emit(
        dict(
            event="panel_compact_" + args.action,
            id=value["id"],
            passed=value.get("passed"),
            status=value.get("status"),
            compact_max_prompt_tokens=value.get("compact_max_prompt_tokens"),
        )
    )


if __name__ == "__main__":
    main()
