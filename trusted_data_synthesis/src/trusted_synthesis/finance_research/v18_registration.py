"""Freeze a no-API researcher successor without reinstating the held V17 material."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .calibration import now
from .v6_collection import bound, persist, require, sha
from .v13_material_registration import checked, entry, read_ref
from .v18_material import ABMD, historical_context
from .v18_researcher_authority import KIND, load_authority

STUDY = Path(
    "/data1/zhuxinrui/projects/Data-Synthesis/trusted_data_synthesis/artifacts/finance_research_20260928/finqa_v6_01"
)
SOURCE = STUDY / "v17_three_task_continuation_01"
OUTPUT = STUDY / "v18_researcher_continuation_01"
FROZEN = Path(
    "/data1/zhuxinrui/projects/Data-Synthesis/.codex-worktrees/finqa-v17-three-continuation-20260930"
)
AUDIT = Path(
    "/home/zhuxinrui/.codex/attachments/28b7ebbf-7c7d-4b59-81e6-d70595ee367b/已粘贴的文本.txt"
)
BATCH_ID = "finqa-v18-20260930-researcher-continuation-01"
SOURCES = (
    "v18_registration.py",
    "v18_researcher_authority.py",
    "v18_material.py",
    "v18_continuation.py",
    "v18_workflow.py",
    "v17_material.py",
    "v16_material.py",
    "v16_continuation.py",
    "v16_workflow.py",
    "v16_arm_training.py",
    "v15_material.py",
    "v15_prefix_material.py",
    "v14_material.py",
    "v14_encoding_cache.py",
    "v14_student_encoding.py",
    "v10_training.py",
    "v9_conditional_training.py",
    "v9_training_launcher.py",
    "v9_mechanism_execution.py",
    "v9_final_evaluation.py",
    "v8_training_driver.py",
    "v6_collection.py",
    "contracts.py",
    "storage.py",
)


def source_bindings():
    return {name: sha(Path(__file__).parent / name) for name in SOURCES}


def prepare(output=OUTPUT, *, source=SOURCE, frozen=FROZEN):
    """Read existing source references only; no encoding, Student, wallet or API."""
    output, source, frozen = (Path(p).resolve() for p in (output, source, frozen))
    require(
        not (output / "definition/record.json").exists(),
        "preserve the immutable researcher definition",
    )
    previous = checked(source / "registration/record.json")
    parent = read_ref(previous["definition"])
    revoked = checked(source / "material/binding/record.json")
    hold = checked(source / "admission_hold/record.json")
    authority = entry(output / "researcher_authority/record.json")
    inspected = load_authority(authority, parent["fixed_task_slots"])
    require(output != source, "researcher successor must have its own material root")
    inherited = {task: ref for task, ref in revoked["mapping_authorities"].items() if task != ABMD}
    definition = bound(
        dict(
            schema="v18_researcher_continuation_definition.v1",
            at=now(),
            batch_id=BATCH_ID,
            **{
                key: parent[key]
                for key in (
                    "source_root",
                    "source_registration",
                    "source_frozen_root",
                    "source_completion_seal",
                    "source_support",
                    "prospective_intent",
                    "prefix_material_binding",
                    "fixed_task_slots",
                    "candidate_slot_ids",
                )
            },
            source_v17_registration=entry(source / "registration/record.json"),
            source_v17_definition=previous["definition"],
            source_v17_completion_seal=entry(source / "completion_seal/record.json"),
            source_v17_revoked_binding=entry(source / "material/binding/record.json"),
            source_v17_admission_hold=entry(source / "admission_hold/record.json"),
            source_v17_frozen_root=str(frozen),
            inherited_mapping_authorities=inherited,
            previous_failed_authorities={ABMD: hold["paid_source"]},
            previous_failure_kind="semantic_admission_hold_despite_structural_pass",
            fixed_unresolved_task_ids=[ABMD],
            exact_original_packages=4,
            researcher_authority=authority,
            judgment_source_kind=KIND,
            actual_judgment_source="Codex source-grounded research adjudication; not human and not a paid API return",
            researcher_mapping_status=inspected["mapping_status"],
            api_model_policy="deepseek-flash",
            authorized_API_calls=0,
            API_calls=0,
            API_count_scope="external_paid_API_requests; Codex research judgment has participated",
            student_results_used=False,
            original_743_authorities_unchanged=True,
            supervision_and_encoding_unchanged=True,
            old_V17_hold_and_binding_preserved=True,
            no_automatic_retry=True,
            no_new_generation_or_supervision=True,
            user_request="参照审计修订并开展后续实验",
            audit=dict(path=str(AUDIT), sha256=sha(AUDIT)),
        )
    )
    # This verifies parent741 + exactly the two retained V17 sources. The held
    # ABMD inspection is explicitly excluded, without opening encoding arrays.
    historical_context(definition)
    persist(output / "definition", definition)
    return definition


def checked_researcher_authority(definition):
    record = read_ref(definition["researcher_authority"])
    inspected = load_authority(definition["researcher_authority"], definition["fixed_task_slots"])
    require(record["inspection"] == inspected, "researcher authority inspection changed")
    return record


def register(output=OUTPUT):
    output = Path(output).resolve()
    if (output / "registration/record.json").exists():
        plan = checked_plan(output)
    else:
        definition = checked(output / "definition/record.json")
        require(
            definition["schema"] == "v18_researcher_continuation_definition.v1"
            and definition["api_model_policy"] == "deepseek-flash"
            and definition["authorized_API_calls"] == definition["API_calls"] == 0,
            "explicit researcher successor with zero external API authority required",
        )
        checked_researcher_authority(definition)
        plan = bound(
            dict(
                schema="v18_researcher_continuation_plan.v1",
                at=now(),
                batch_id=BATCH_ID,
                definition=entry(output / "definition/record.json"),
                protocol_identity=definition["id"],
                source_bindings=source_bindings(),
                researcher_authority=definition["researcher_authority"],
                judgment_source_kind=KIND,
                actual_judgment_source=definition["actual_judgment_source"],
                api_model_policy="deepseek-flash",
                authorized_API_calls=0,
                API_calls=0,
                API_count_scope=definition["API_count_scope"],
                Codex_research_judgment_participated=True,
                source_root=definition["source_root"],
                source_registration=definition["source_registration"],
                original_743_authorities_unchanged=True,
                old_V17_hold_and_binding_preserved=True,
                student_results_used=False,
                no_automatic_retry=True,
            )
        )
        persist(output / "registration", plan)
    seal = bound(
        dict(
            schema="v18_researcher_adjudication_seal.v1",
            at=plan["at"],
            registration_id=plan["id"],
            protocol_id=plan["protocol_identity"],
            authority=plan["researcher_authority"],
            expected_model_calls=0,
            actual_model_calls=0,
            call_count_scope="external_paid_API_requests_only",
            Codex_research_judgment_participated=True,
            judgment_source_kind=KIND,
            human_judgment=False,
            not_a_paid_model_return=True,
            paid_API_receipt=None,
            old_V17_hold_and_binding_preserved=True,
        )
    )
    persist(output / "completion_seal", seal)
    return plan


def checked_plan(output=OUTPUT):
    output = Path(output).resolve()
    plan = checked(output / "registration/record.json")
    definition = read_ref(plan["definition"])
    require(
        plan["schema"] == "v18_researcher_continuation_plan.v1"
        and plan["batch_id"] == BATCH_ID
        and plan["source_bindings"] == source_bindings()
        and plan["protocol_identity"] == definition["id"]
        and definition["schema"] == "v18_researcher_continuation_definition.v1"
        and plan["researcher_authority"] == definition["researcher_authority"]
        and plan["source_root"] == definition["source_root"]
        and plan["source_registration"] == definition["source_registration"]
        and plan["judgment_source_kind"] == definition["judgment_source_kind"] == KIND
        and plan["actual_judgment_source"] == definition["actual_judgment_source"]
        and plan["Codex_research_judgment_participated"] is True
        and plan["api_model_policy"] == definition["api_model_policy"] == "deepseek-flash"
        and plan["authorized_API_calls"]
        == plan["API_calls"]
        == definition["authorized_API_calls"]
        == definition["API_calls"]
        == 0
        and plan["student_results_used"] is definition["student_results_used"] is False
        and definition["fixed_unresolved_task_ids"] == [ABMD]
        and len(definition["inherited_mapping_authorities"]) == 743
        and len(definition["fixed_task_slots"]) == 744
        and sum(map(len, definition["fixed_task_slots"].values())) == 2468
        and not any(key in plan for key in ("jobs", "model", "budget_database", "provider")),
        "frozen non-human researcher source, exact population and no paid API stage required",
    )
    return plan


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "define", "register"))
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    result = register(args.output) if args.action == "register" else prepare(args.output)
    print(json.dumps(dict(id=result["id"], output=str(args.output), authorized_API_calls=0)))


if __name__ == "__main__":
    main()
