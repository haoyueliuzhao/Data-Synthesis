"""User-authorized one additional judgment for each of three remaining original tasks."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from . import v16_registration as previous_registration
from .calibration import now
from .contracts import digest
from .v6_collection import bound, persist, require, sha
from .v13_material_registration import checked, entry, read_ref

STUDY = previous_registration.STUDY
SOURCE = STUDY / "v16_six_task_continuation_01"
OUTPUT = STUDY / "v17_three_task_continuation_01"
FROZEN = Path(
    "/data1/zhuxinrui/projects/Data-Synthesis/.codex-worktrees/finqa-v16-six-continuation-20260930"
)
BATCH_ID = "finqa-v17-20260930-three-task-continuation-01"
FIXED_TASKS = ("ABMD/2008/page_87.pdf-1", "KHC/2018/page_27.pdf-1", "PNC/2016/page_73.pdf-1")
SOURCES = tuple(
    dict.fromkeys(
        previous_registration.SOURCES
        + (
            "v17_registration.py",
            "v17_adjudication_protocol.py",
            "v17_provider.py",
            "v17_controller.py",
            "v17_budget.py",
            "v16_material.py",
        )
    )
)


def source_bindings():
    return {name: sha(Path(__file__).parent / name) for name in SOURCES}


def original_authorities(source=SOURCE):
    """All old741 references unchanged, including three usable V16 judgments."""
    source = Path(source).resolve()
    plan = checked(source / "registration/record.json")
    definition = read_ref(plan["definition"])
    _, parent, authorities, prior_failed = previous_registration.original_authorities(
        definition["source_root"]
    )
    seal = checked(source / "completion_seal/record.json")
    support = checked(source / "material/support/record.json")
    require(
        seal["registration_id"] == plan["id"]
        and seal["expected_calls"] == seal["actual_returns"] == len(plan["jobs"]) == 6
        and seal["network_unknowns"] == 0
        and seal["usable_returns"] == 3,
        "actual closed six-task wave is the predecessor, not a rewritten attempt",
    )
    failed = {}
    for job, terminal_ref in zip(plan["jobs"], seal["terminals"], strict=True):
        terminal = read_ref(terminal_ref)
        record = read_ref(terminal["record"])
        task = job["task_id"]
        require(
            task in prior_failed
            and task == terminal["task_id"]
            and task not in authorities
            and task not in failed
            and terminal["registration_id"] == plan["id"]
            and terminal["terminal_kind"] == "paid_model_return"
            and record["schema"] == "v16_paid_material_annotation.v1"
            and record["actual_model_call_receipt_verified"] is True
            and record["request"] == read_ref(job["request"]),
            "original V16 receipt changed",
        )
        target = authorities if record["inspection"]["mapping_admitted"] else failed
        target[task] = terminal["record"]
    groups = definition["fixed_task_slots"]
    require(
        groups == parent["fixed_task_slots"]
        and len(groups) == 744
        and sum(map(len, groups.values())) == 2468
        and len(authorities) == 741
        and set(authorities) == set(support["task_support"])
        and set(failed) == set(FIXED_TASKS)
        and sum(len(groups[t]) for t in failed) == 13
        and set(authorities).isdisjoint(failed)
        and set(authorities) | set(failed) == set(groups),
        "only the actual remaining three tasks/13 packages may be adjudicated again",
    )
    return plan, definition, authorities, failed


def prepare(output=OUTPUT, *, source=SOURCE, frozen=FROZEN):
    from . import v17_adjudication_protocol as protocol

    output, source, frozen = (Path(p).resolve() for p in (output, source, frozen))
    require(
        not (output / "definition/record.json").exists(),
        "do not replace a registered additional wave",
    )
    previous, parent, authorities, failed = original_authorities(source)
    code = frozen / "trusted_data_synthesis/src/trusted_synthesis/finance_research"
    require(
        all(sha(code / n) == h for n, h in previous["source_bindings"].items()),
        "previous six-call execution verified at its real frozen source",
    )
    definition = bound(
        dict(
            schema="v17_three_task_definition.v1",
            at=now(),
            batch_id=BATCH_ID,
            **{
                k: parent[k]
                for k in (
                    "source_root",
                    "source_frozen_root",
                    "source_registration",
                    "source_completion_seal",
                    "source_support",
                    "prospective_intent",
                    "prefix_material_binding",
                    "fixed_task_slots",
                    "candidate_slot_ids",
                )
            },
            predecessor_root=str(source),
            predecessor_frozen_root=str(frozen),
            predecessor_registration=entry(source / "registration/record.json"),
            predecessor_definition=previous["definition"],
            predecessor_completion_seal=entry(source / "completion_seal/record.json"),
            predecessor_support=entry(source / "material/support/record.json"),
            inherited_mapping_authorities=authorities,
            previous_failed_authorities=failed,
            fixed_unresolved_task_ids=list(FIXED_TASKS),
            model="deepseek-flash",
            policy=protocol.policy_definition(),
            expected_requests=3,
            exact_original_packages=13,
            user_request="追加授权，同时授权推送",
            explicit_additional_call_authority=True,
            maximum_additional_calls=3,
            calls_per_remaining_task=1,
            raw_experiment_artifact_push_authorized=True,
            authorization_context=(
                "assistant asked for one additional deepseek-flash call for each of ABMD/KHC/PNC "
                "and permission to upload original API artifacts; user approved both"
            ),
            student_results_used=False,
            original_741_unchanged=True,
            supervision_and_encoding_unchanged=True,
            no_automatic_retry=True,
            judgment_sources_separately_named=True,
            prior_failures_preserved=True,
        )
    )
    persist(output / "definition", definition)
    jobs = []
    for task in FIXED_TASKS:
        latest = read_ref(failed[task])
        req = protocol.prepare_mapping(
            latest["request"]["views"],
            latest_record=latest,
            protocol_id=definition["id"],
            source_bindings=dict(
                v17_definition_id=definition["id"],
                original_v16_failed_authority=failed[task],
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
            "all and only the unchanged original task packages",
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
                authority_reason="explicitly_authorized_three_task_adjudication",
            )
        )
    result = bound(
        dict(
            schema="v17_three_task_preparation.v1",
            at=now(),
            definition_id=definition["id"],
            jobs=jobs,
            complete=len(jobs) == 3,
            actual_model_calls=0,
            student_results_used=False,
        )
    )
    persist(output / "preparation", result)
    return result


def register(output=OUTPUT):
    output = Path(output).resolve()
    definition = checked(output / "definition/record.json")
    prepared = checked(output / "preparation/record.json")
    previous = read_ref(definition["predecessor_registration"])
    require(
        prepared["complete"] and prepared["definition_id"] == definition["id"],
        "all three requests frozen before any new paid judgment",
    )
    value = bound(
        dict(
            schema="v17_three_task_adjudication_plan.v1",
            at=now(),
            batch_id=BATCH_ID,
            protocol_identity=definition["id"],
            definition=entry(output / "definition/record.json"),
            preparation=entry(output / "preparation/record.json"),
            source_root=definition["source_root"],
            source_registration=definition["source_registration"],
            predecessor_root=definition["predecessor_root"],
            predecessor_registration=definition["predecessor_registration"],
            source_protocol_id=previous["id"],
            source_bindings=source_bindings(),
            model="deepseek-flash",
            expected_requests=3,
            purpose_counts={"mapping": 3},
            jobs=prepared["jobs"],
            fixed_task_slots=definition["fixed_task_slots"],
            fixed_unresolved_task_ids=list(FIXED_TASKS),
            concurrency=dict(max=3),
            **{
                k: previous[k]
                for k in ("budget_database", "budget_config", "budget_config_sha256", "transport")
            },
            student_results_used=False,
            no_automatic_retry=True,
            money_and_request_caps_unchanged=True,
            explicit_additional_call_authority=True,
        )
    )
    persist(output / "registration", value)
    return value


def checked_plan(output=OUTPUT):
    plan = checked(Path(output) / "registration/record.json")
    definition, prepared = read_ref(plan["definition"]), read_ref(plan["preparation"])
    require(
        plan["schema"] == "v17_three_task_adjudication_plan.v1"
        and plan["batch_id"] == BATCH_ID
        and plan["source_bindings"] == source_bindings()
        and plan["model"] == "deepseek-flash"
        and plan["protocol_identity"] == definition["id"] == prepared["definition_id"]
        and prepared["complete"]
        and plan["jobs"] == prepared["jobs"]
        and len(plan["jobs"]) == plan["expected_requests"] == 3
        and [j["task_id"] for j in plan["jobs"]] == list(FIXED_TASKS)
        and plan["predecessor_registration"] == definition["predecessor_registration"]
        and plan["source_registration"] == definition["source_registration"]
        and definition["explicit_additional_call_authority"] is True,
        "frozen three-call input/model/source and explicit additional authorization required",
    )
    return plan


ledger_for = previous_registration.ledger_for
resolve_proxy = previous_registration.resolve_proxy


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "register"))
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    result = prepare(args.output) if args.action == "prepare" else register(args.output)
    print(json.dumps(dict(id=result["id"], output=str(args.output))))


if __name__ == "__main__":
    main()
