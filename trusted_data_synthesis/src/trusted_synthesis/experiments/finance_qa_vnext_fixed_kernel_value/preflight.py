"""Metadata-first fixed inputs and bounded, explicitly synthetic CPU controls."""

import json
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from contextlib import ExitStack
from multiprocessing import get_context
from pathlib import Path

from ..finance_qa_vnext_catalog_bridge.controls import script_for_witness
from ..finance_qa_vnext_linear_postprocess.manifest import LinearParent
from ..finance_qa_vnext_movement_support.run import load_fixtures
from ..finance_qa_vnext_task_build.archive import validate_record
from . import population, runtime, transport
from . import protocol as p
from .semantic_mapping import assess_new_semantics
from .source_boundary import load_source_evidence, prepare_fixture

_CONTROL_FIXTURES = None


def load_inputs(data_root):
    """Choose 200 from metadata before checking source coverage; return JSON only.

    All original fixture parents are read with pinned descriptors. Public inputs
    are neither pruned nor rewritten. The larger 255-directory source evidence
    merely covers repeated report parents; it cannot change the selected tasks.
    No handles, providers, Student results, credentials or GPU objects survive.
    """
    data_root = Path(data_root)
    with ExitStack() as stack:
        revision = LinearParent(data_root, p.REVISION, p.REVISION_MANIFEST)
        stack.callback(revision.close)
        catalog = revision.read("catalog.json")
        validate_record(catalog, "composed_task_catalog")
        selected = population.make_population(catalog)
        originals, dependencies = load_fixtures(stack, data_root)
        p.require(
            dependencies["catalog_id"] == catalog["id"]
            and len(originals) == len({row["identity"]["task_id"] for row in originals}) == 255,
            "preflight.original_catalog_fixture_join",
        )
        source_evidence = load_source_evidence(data_root, dependencies["parents"], originals)
        by_task = {row["identity"]["task_id"]: row for row in originals}
        prepared, boundaries = {}, []
        for registered in selected["tasks"]:
            original = by_task[registered["task_id"]]
            p.require(
                original["bundle"]["id"] == registered["bundle_id"]
                and original["identity"]["public_messages_sha256"]
                == registered["public_messages_sha256"]
                and original["identity"]["parent_manifest_id"] == registered["parent_manifest_id"],
                "preflight.selected_original_scientific_identity",
            )
            fixture = prepare_fixture(original, source_evidence=source_evidence)
            p.require(
                all(
                    fixture[key] == original[key]
                    for key in ("bundle", "messages", "identity", "native_bindings")
                ),
                "preflight.original_public_and_private_parents_unchanged",
            )
            prepared[registered["task_id"]] = fixture
            boundary = fixture["source_boundary"]
            boundaries.append(
                {
                    "task_id": registered["task_id"],
                    "family": registered["family"],
                    "source_cluster": registered["source_cluster"],
                    "bundle_id": registered["bundle_id"],
                    "parent_manifest_id": registered["parent_manifest_id"],
                    "surface_version_id": registered["surface_version_id"],
                    "public_messages_sha256": registered["public_messages_sha256"],
                    "original_native_bindings_sha256": boundary["original_native_bindings_sha256"],
                    "enriched_native_bindings_sha256": boundary["enriched_native_bindings_sha256"],
                    "source_boundary_id": boundary["id"],
                    "coverage_counts": boundary["counts"],
                    "unresolved_public_coverage": [
                        row
                        for row in boundary["coverage"]
                        if row["status"].startswith("UNRESOLVED")
                    ],
                    "original_sources_removed": False,
                }
            )
    manifest = p.record(
        "input_boundary_manifest",
        population_id=selected["id"],
        source_catalog_id=catalog["id"],
        source_dependencies_id=dependencies["id"],
        source_evidence_id=source_evidence["id"],
        original_catalog_task_count=255,
        selected_task_count=len(prepared),
        tasks=boundaries,
        metadata_selection_preceded_source_coverage=True,
        coverage_based_replacement=False,
        public_messages_rewritten=False,
        original_parent_data_modified=False,
        API_calls=0,
        GPU_operations=0,
        Student_outputs_read=False,
    )
    return {
        "population": selected,
        "fixtures": prepared,
        "source_dependencies": dependencies,
        "source_evidence": source_evidence,
        "boundary_manifest": manifest,
    }


def _control_plan(inputs):
    tasks = population.validate_population(inputs["population"])
    p.require(
        set(inputs["fixtures"]) == {row["task_id"] for row in tasks},
        "preflight.exact_selected_fixture_task_set",
    )
    jobs = []
    for task in tasks:
        guidance = ("neutral",) if task["family"] == "control" else ("endpoint", "movement")
        actuals = ("control",) if task["family"] == "control" else ("endpoint", "movement")
        for requested in guidance:
            for actual in actuals:
                jobs.append(
                    {
                        "ordinal": len(jobs),
                        "task_id": task["task_id"],
                        "guidance": requested,
                        "expected_actual_method": actual,
                    }
                )
    p.require(len(jobs) == 560, "preflight.fixed_560_engineering_controls")
    return jobs


def _run_control(fixture, job):
    profile = p.CONTROL_PROFILE if job["guidance"] == "neutral" else p.TARGET_PROFILE
    registration = p.record(
        "engineering_control_registration",
        session_id="ENGINEERING_SYNTHETIC_"
        + p.sha(p.encode([fixture["source_boundary"]["id"], job])),
        identity=fixture["identity"],
        profile=profile,
        basis=job["guidance"],
        system_prompt_sha256=p.sha(p.system_prompt(profile, job["guidance"])),
        role="engineering_only",
        not_a_formal_material_registration=True,
    )
    try:
        script = script_for_witness(
            fixture["bundle"], fixture["native_bindings"], job["expected_actual_method"]
        )
        queue = iter(script)
        session = runtime.generate(
            fixture["messages"],
            fixture["identity"],
            registered=registration,
            provider=lambda *_: p.encode(next(queue)).decode(),
        )
        runtime.replay(session)
        qualification = assess_new_semantics(session, fixture)
        request_sizes = [
            len(transport.render(turn["input_messages"])[1]) for turn in session["turns"]
        ]
        tool_count = sum(event["tool_call"] is not None for event in session["events"])
        passed = bool(
            qualification["financial_valid"]
            and qualification["actual_method"] == job["expected_actual_method"]
            and qualification["full_mapping_status"] == "MAPPED"
            and session["first_final_index"] is not None
            and len(session["turns"]) <= p.MAX_RESPONSES
            and tool_count <= p.MAX_TOOLS
        )
        fields = {
            "passed": passed,
            "session_id": session["id"],
            "qualification_id": qualification["id"],
            "original_semantic_assessment_id": qualification["original_semantic_assessment"]["id"],
            "financial_valid": qualification["financial_valid"],
            "actual_method": qualification["actual_method"],
            "full_mapping_status": qualification["full_mapping_status"],
            "reason": qualification["reason"],
            "mapping_pending_reasons": qualification.get("full_mapping_pending_reasons", []),
            "responses": len(session["turns"]),
            "tool_calls": tool_count,
            "maximum_request_body_bytes": max(request_sizes, default=0),
            "public_messages_unchanged": session["public_messages"] == fixture["messages"],
            "registered_system_unchanged": session["initial_messages"][0]["content"]
            == p.system_prompt(profile, job["guidance"]),
            "complete_original_runtime_replayed": True,
        }
    except (ValueError, TypeError, KeyError, IndexError, StopIteration, RuntimeError) as error:
        fields = {
            "passed": False,
            "reason": str(error),
            "error_type": type(error).__name__,
            "responses": None,
            "tool_calls": None,
            "maximum_request_body_bytes": None,
        }
    return p.record(
        "engineering_scripted_control",
        **job,
        registration_id=registration["id"],
        registered_session_id=registration["session_id"],
        family=fixture["identity"]["family"],
        bundle_id=fixture["bundle"]["id"],
        source_boundary_id=fixture["source_boundary"]["id"],
        **fields,
        origin="ENGINEERING_SYNTHETIC",
        script_accesses_private_witness_and_reference_answer=True,
        runtime_private_oracle_access_flag_is_not_a_claim_about_script_construction=True,
        genuine_Teacher_origin=False,
        authentic_origin_verified=False,
        formal_10240_registration_member=False,
        training_eligible=False,
        training_samples=0,
        API_calls=0,
        GPU_operations=0,
        Student_outputs_read=False,
    )


def _initialize_controls(fixtures):
    global _CONTROL_FIXTURES
    _CONTROL_FIXTURES = fixtures


def _control_job(job):
    return _run_control(_CONTROL_FIXTURES[job["task_id"]], job)


def scripted_controls(inputs, workers=p.CPU_WORKERS):
    """560 engineering-only controls, including both opposite-guidance cases.

    Spawned workers receive pure JSON fixtures, not live parent descriptors.
    The returned rows are ordered by the predeclared control plan; no successful
    subset can replace a failed control, and no runtime/prompt is repaired here.
    """
    p.require(type(workers) is int and workers > 0, "preflight.explicit_CPU_workers")
    jobs = _control_plan(inputs)
    if workers == 1:
        rows = [_run_control(inputs["fixtures"][job["task_id"]], job) for job in jobs]
    else:
        with ProcessPoolExecutor(
            max_workers=workers,
            mp_context=get_context("spawn"),
            initializer=_initialize_controls,
            initargs=(inputs["fixtures"],),
        ) as pool:
            rows = list(pool.map(_control_job, jobs))
    p.require(
        [row["ordinal"] for row in rows] == list(range(560)),
        "preflight.complete_control_plan_order",
    )
    failed = [row for row in rows if not row["passed"]]
    return p.record(
        "scripted_preflight_controls",
        population_id=inputs["population"]["id"],
        boundary_manifest_id=inputs["boundary_manifest"]["id"],
        status="PASS" if not failed else "FAIL_ENGINEERING_CONTROLS",
        expected_control_count=560,
        completed_control_count=len(rows),
        passed_control_count=len(rows) - len(failed),
        failed_control_ids=[row["id"] for row in failed],
        by_family=dict(Counter(row["family"] for row in rows)),
        rows=rows,
        maximum_responses=max((row["responses"] or 0 for row in rows), default=0),
        maximum_tool_calls=max((row["tool_calls"] or 0 for row in rows), default=0),
        maximum_request_body_bytes=max(
            (row["maximum_request_body_bytes"] or 0 for row in rows), default=0
        ),
        CPU_workers=workers,
        origin="ENGINEERING_SYNTHETIC",
        private_reference_witness_used_for_script_construction=True,
        genuine_Teacher_origin=False,
        formal_material_sessions_created=0,
        training_samples=0,
        API_calls=0,
        GPU_operations=0,
        Student_outputs_read=False,
    )


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", required=True)
    parser.add_argument("--workers", type=int, default=p.CPU_WORKERS)
    args = parser.parse_args()
    inputs = load_inputs(args.data_root)
    checks = scripted_controls(inputs, workers=args.workers)
    print(
        json.dumps({key: value for key, value in checks.items() if key != "rows"}, sort_keys=True)
    )
    for row in checks["rows"]:
        if not row["passed"]:
            print(json.dumps(row, sort_keys=True))
