"""Six once-only, outcome-blind adjudications inheriting the original V15 intent."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from .calibration import now
from .contracts import digest
from .v6_collection import bound, persist, require, sha
from .v13_material_registration import checked, entry, read_ref

STUDY = Path(
    "/data1/zhuxinrui/projects/Data-Synthesis/trusted_data_synthesis/artifacts/finance_research_20260928/finqa_v6_01"
)
SOURCE = STUDY / "v15_prefix_completion_01"
OUTPUT = STUDY / "v16_six_task_continuation_01"
FROZEN = Path("/data1/zhuxinrui/projects/Data-Synthesis/.codex-worktrees/finqa-v15-prefix-20260930")
AUDIT = Path(
    "/home/zhuxinrui/.codex/attachments/fcf9edc7-83c2-407f-9baf-7193624a99c1/已粘贴的文本.txt"
)
BATCH_ID = "finqa-v16-20260930-six-task-continuation-01"
SOURCES = (
    "v16_registration.py",
    "v16_adjudication_protocol.py",
    "v16_provider.py",
    "v16_controller.py",
    "v16_budget.py",
    "v10_budget.py",
    "probe_budget.py",
    "v10_funding.py",
    "contracts.py",
    "qwen_protocol.py",
    "v15_mapping_protocol.py",
    "v14_material_protocol.py",
    "v13_material_protocol.py",
    "v12_review_protocol.py",
    "v12_review_capacity.py",
    "v11_process_review.py",
    "v10_review_protocol.py",
    "v10_process_review.py",
    "v6_task.py",
    "providers.py",
    "v6_collection.py",
    "v13_material_registration.py",
    "calibration.py",
)


def source_bindings():
    return {name: sha(Path(__file__).parent / name) for name in SOURCES}


def original_authorities(source):
    """Read the original recorded decisions; never rerun the old reviewer or wallet."""
    source = Path(source).resolve()
    plan = checked(source / "registration/record.json")
    definition = read_ref(plan["definition"])
    review = read_ref(definition["mapping_review"])
    support = checked(source / "material/support/record.json")
    seal = checked(source / "completion_seal/record.json")
    require(
        seal["registration_id"] == plan["id"]
        and seal["actual_returns"] == 36
        and seal["expected_calls"] == 36
        and seal["network_unknowns"] == 0,
        "inherit the actual complete V15 return matrix",
    )
    authorities = {}
    for field in ("inherited_mapping_authority_refs", "derived_mapping_authority_refs"):
        for value in review[field]:
            require(value["task_id"] not in authorities, "duplicate old authority")
            authorities[value["task_id"]] = value["record"]
    failed = {}
    for terminal_ref in seal["terminals"]:
        terminal = read_ref(terminal_ref)
        record = read_ref(terminal["record"])
        task = terminal["task_id"]
        require(
            task not in authorities
            and task not in failed
            and terminal["terminal_kind"] == "paid_model_return"
            and record["actual_model_call_receipt_verified"] is True,
            "original unique paid mapping source required",
        )
        inspected = record.get("inspection") or {}
        destination = authorities if inspected.get("mapping_admitted") is True else failed
        destination[task] = terminal["record"]
    groups = definition["fixed_task_slots"]
    require(
        len(groups) == 744
        and sum(map(len, groups.values())) == 2468
        and len(authorities) == 738
        and len(failed) == 6
        and set(authorities) == set(support["task_support"])
        and set(authorities).isdisjoint(failed)
        and set(authorities) | set(failed) == set(groups)
        and sum(len(groups[t]) for t in failed) == 24,
        "exact 738 preserved authorities plus fixed six tasks and 24 original packages",
    )
    return plan, definition, authorities, failed


def prepare(output=OUTPUT, *, source=SOURCE, frozen=FROZEN):
    from . import v16_adjudication_protocol as protocol

    output, source, frozen = map(lambda p: Path(p).resolve(), (output, source, frozen))
    require(
        not (output / "definition/record.json").exists(),
        "retain the immutable six-task preparation",
    )
    previous, parent, authorities, failed = original_authorities(source)
    old_code = frozen / "trusted_data_synthesis/src/trusted_synthesis/finance_research"
    require(
        all(
            sha(old_code / name) == expected
            for name, expected in previous["source_bindings"].items()
        ),
        "original registered code must be checked at its frozen source, not relabeled",
    )
    intent = checked(source / "continuation_intent/record.json")
    prefix = entry(source / "prefix_material/binding/record.json")
    require(
        intent["mapping_plan"] == entry(source / "registration/record.json")
        and intent["prefix_material_binding"] == prefix
        and intent["student_results_used"] is False,
        "retain actual pre-prefix intent unchanged",
    )
    fixed = [task for task in parent["fixed_task_slots"] if task in failed]
    definition = bound(
        dict(
            schema="v16_six_task_definition.v1",
            at=now(),
            batch_id=BATCH_ID,
            source_root=str(source),
            source_frozen_root=str(frozen),
            source_registration=entry(source / "registration/record.json"),
            source_completion_seal=entry(source / "completion_seal/record.json"),
            source_support=entry(source / "material/support/record.json"),
            prospective_intent=entry(source / "continuation_intent/record.json"),
            prefix_material_binding=prefix,
            fixed_task_slots=parent["fixed_task_slots"],
            candidate_slot_ids=parent["candidate_slot_ids"],
            fixed_unresolved_task_ids=fixed,
            inherited_mapping_authorities=authorities,
            previous_failed_authorities=failed,
            policy=protocol.policy_definition(),
            model="deepseek-flash",
            expected_requests=6,
            exact_original_packages=24,
            student_results_used=False,
            judgment_sources_separately_named=True,
            original_738_unchanged=True,
            supervision_and_encoding_unchanged=True,
            no_automatic_retry=True,
            user_request="参照审计修订并开展后续实验",
            audit=dict(path=str(AUDIT), sha256=sha(AUDIT)),
        )
    )
    persist(output / "definition", definition)
    jobs = []
    for task in fixed:
        latest = read_ref(failed[task])
        req = protocol.prepare_mapping(
            latest["request"]["views"],
            latest_record=latest,
            protocol_id=definition["id"],
            source_bindings=dict(
                v16_definition_id=definition["id"],
                original_v15_authority=failed[task],
                task_slot_ids=parent["fixed_task_slots"][task],
            ),
        )
        body = protocol.request_body(req)
        wire = json.dumps(
            body, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
        directory = output / "requests" / req["episode_id"].split(":", 1)[1]
        persist(directory, req)
        require(
            req["task_id"] == task and req["slot_ids"] == parent["fixed_task_slots"][task],
            "all and only original packages for each adjudicated task",
        )
        jobs.append(
            dict(
                kind="mapping",
                purpose="mapping",
                role="mapping",
                task_id=task,
                slot_id=None,
                slot_ids=req["slot_ids"],
                episode_id=req["episode_id"],
                request_id=req["id"],
                request=entry(directory / "record.json"),
                request_sha256=digest(body),
                request_body_sha256=hashlib.sha256(wire).hexdigest(),
                max_output_tokens=req["max_output_tokens"],
                wire_bytes=len(wire),
                authority_reason="fixed_six_task_adjudication",
            )
        )
    result = bound(
        dict(
            schema="v16_six_task_preparation.v1",
            at=now(),
            definition_id=definition["id"],
            jobs=jobs,
            complete=len(jobs) == 6,
            actual_model_calls=0,
            student_results_used=False,
        )
    )
    persist(output / "preparation", result)
    return result


def register(output=OUTPUT):
    output = Path(output).resolve()
    definition = checked(output / "definition/record.json")
    preparation = checked(output / "preparation/record.json")
    previous = read_ref(definition["source_registration"])
    require(
        preparation["complete"] and preparation["definition_id"] == definition["id"],
        "all six exact requests must precede new paid judgments",
    )
    result = bound(
        dict(
            schema="v16_six_task_adjudication_plan.v1",
            at=now(),
            batch_id=BATCH_ID,
            protocol_identity=definition["id"],
            definition=entry(output / "definition/record.json"),
            preparation=entry(output / "preparation/record.json"),
            source_root=definition["source_root"],
            source_registration=definition["source_registration"],
            source_protocol_id=previous["id"],
            source_bindings=source_bindings(),
            model="deepseek-flash",
            jobs=preparation["jobs"],
            expected_requests=6,
            purpose_counts={"mapping": 6},
            fixed_task_slots=definition["fixed_task_slots"],
            fixed_unresolved_task_ids=definition["fixed_unresolved_task_ids"],
            budget_database=previous["budget_database"],
            budget_config=previous["budget_config"],
            budget_config_sha256=previous["budget_config_sha256"],
            transport=previous["transport"],
            concurrency=dict(max=6),
            student_results_used=False,
            no_automatic_retry=True,
            money_and_request_caps_unchanged=True,
        )
    )
    persist(output / "registration", result)
    return result


def checked_plan(output=OUTPUT):
    output = Path(output).resolve()
    plan = checked(output / "registration/record.json")
    definition, prepared = read_ref(plan["definition"]), read_ref(plan["preparation"])
    require(
        plan["schema"] == "v16_six_task_adjudication_plan.v1"
        and plan["batch_id"] == BATCH_ID
        and plan["model"] == "deepseek-flash"
        and plan["source_bindings"] == source_bindings()
        and plan["protocol_identity"] == definition["id"] == prepared["definition_id"]
        and prepared["complete"]
        and plan["jobs"] == prepared["jobs"]
        and len(plan["jobs"]) == plan["expected_requests"] == 6
        and len({j["task_id"] for j in plan["jobs"]}) == 6
        and {j["task_id"] for j in plan["jobs"]} == set(definition["fixed_unresolved_task_ids"])
        and plan["source_registration"] == definition["source_registration"],
        "frozen six-task scope, API model, inputs and execution source required",
    )
    return plan


def ledger_for(plan):
    from .v12_review_registration import ledger_for as original

    return original(plan)


def resolve_proxy(plan):
    from .v13_material_registration import resolve_proxy as original

    return original(plan)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "register"))
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    result = prepare(args.output) if args.action == "prepare" else register(args.output)
    print(json.dumps(dict(id=result["id"], output=str(args.output))))


if __name__ == "__main__":
    main()
