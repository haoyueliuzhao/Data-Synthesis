"""Freeze fixed-54 mapping policy, residual requests and authorities before any prefix."""

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

from .calibration import now, publish
from .contracts import digest
from .v6_collection import bound, persist, require, sha
from .v13_material_registration import checked, entry, read_ref

STUDY = Path(
    "/data1/zhuxinrui/projects/Data-Synthesis/trusted_data_synthesis/artifacts/finance_research_20260928/finqa_v6_01"
)
SOURCE = STUDY / "v14_representation_01"
OUTPUT = STUDY / "v15_prefix_completion_01"
BATCH_ID = "finqa-v15-20260930-prefix-completion-01"
AUDIT = Path(
    "/home/zhuxinrui/.codex/attachments/1dac779a-3922-450d-b7cc-933c1485ba55/已粘贴的文本.txt"
)
CONCURRENCY = {"max": 16, "ramp": [{"settled_at_least": 0, "workers": 16}]}
REQUEST_SOURCES = (
    "v15_mapping_protocol.py",
    "v14_material_protocol.py",
    "v13_material_protocol.py",
    "v12_review_protocol.py",
    "v12_review_capacity.py",
    "v11_process_review.py",
    "v10_review_protocol.py",
    "v10_process_review.py",
    "v6_task.py",
    "qwen_protocol.py",
    "contracts.py",
)
EXECUTION_SOURCES = REQUEST_SOURCES + (
    "v15_mapping_registration.py",
    "v15_mapping_provider.py",
    "v15_mapping_controller.py",
    "v15_budget.py",
    "v14_budget.py",
    "v13_budget.py",
    "v12_budget.py",
    "v10_budget.py",
    "probe_budget.py",
    "v10_funding.py",
)


def source_bindings(names=EXECUTION_SOURCES):
    return {name: sha(Path(__file__).parent / name) for name in names}


def canonical(value):
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode()


def define_mapping(output, mapping_review, source=SOURCE):
    from .v15_mapping_protocol import policy_definition

    output, source = Path(output).resolve(), Path(source).resolve()
    review_ref = entry(Path(mapping_review).resolve())
    review = read_ref(review_ref)
    previous = checked(source / "registration/record.json")
    parent = read_ref(previous["definition"])
    seal = checked(source / "completion_seal/record.json")
    support = checked(source / "material/support/record.json")
    groups = parent["fixed_task_slots"]
    fixed = [task for task in groups if task not in support["task_support"]]
    inherited = review["inherited_mapping_authority_refs"]
    derived = review["derived_mapping_authority_refs"]
    residual = review["residual_mapping_task_ids"]
    inherit_ids = {r["task_id"] for r in inherited}
    derived_ids = {r["task_id"] for r in derived}
    require(
        review["schema"] == "v15_mapping_review.v1"
        and review["old_690_partition_evidence_chi_unchanged"] is True
        and review["policy"] == policy_definition()
        and all(
            sha(Path(__file__).parent / name) == value
            for name, value in review["source_protocol_hashes"].items()
        )
        and seal["registration_id"] == previous["id"]
        and seal["actual_returns"] == seal["expected_calls"] == 309
        and seal["network_unknowns"] == 0
        and support["N"] == 744
        and support["package_count"] == 2468
        and len(fixed) == 54
        and set(fixed) == set(review["fixed_task_ids"])
        and len(inherited) == len(inherit_ids) == 690
        and inherit_ids == set(support["task_support"])
        and len(derived) == len(derived_ids)
        and derived_ids <= set(fixed)
        and len(residual) == len(set(residual))
        and set(residual).isdisjoint(derived_ids)
        and set(residual) | derived_ids == set(fixed),
        "fixed 54 review, old 690 authority and residual partition must all bind before training",
    )
    result = bound(
        dict(
            schema="v15_fixed_mapping_definition.v1",
            at=now(),
            batch_id=BATCH_ID,
            source_root=str(source),
            source_v14_definition=previous["definition"],
            source_v14_plan=entry(source / "registration/record.json"),
            source_v14_seal=entry(source / "completion_seal/record.json"),
            source_material_support=entry(source / "material/support/record.json"),
            source_material_result=entry(source / "material/result/record.json"),
            mapping_review=review_ref,
            parent_fixed_population_id=parent["id"],
            fixed_task_slots=groups,
            candidate_slot_ids=parent["candidate_slot_ids"],
            pairs=parent["pairs"],
            fixed_unresolved_task_ids=fixed,
            residual_task_ids=residual,
            inherited_mapping_authority_refs=inherited,
            derived_mapping_authority_refs=derived,
            expected_requests=len(residual),
            purpose_counts={"mapping": len(residual)},
            policy=policy_definition(),
            source_request_bindings=source_bindings(REQUEST_SOURCES),
            no_Student_observations_consumed=True,
            only_original_public_trajectories_in_model_input=True,
            no_new_projection_or_mask=True,
            no_student_loss_checkpoint_gradient_or_dev_in_requests=True,
            mapping_policy_and_authority_must_precede_prefix=True,
            old_valid_authorities_preserved=True,
            field_authority_fixed_before_new_returns=True,
            new_failures_never_fall_back_to_old_invalid=True,
            user_request="参照审计修订并开展后续实验",
            audit={"path": str(AUDIT), "sha256": sha(AUDIT)},
        )
    )
    persist(output / "definition", result)
    return result


def prepare_mapping(output=OUTPUT, *, mapping_review, source=SOURCE):
    from . import v15_mapping_protocol as protocol

    output = Path(output).resolve()
    require(
        not (output / "preparation/record.json").exists(),
        "preserve existing prepared requests; use new revision",
    )
    definition = define_mapping(output, mapping_review, source)
    pairs = {p["slot_id"]: p for p in definition["pairs"]}
    residual = set(definition["residual_task_ids"])
    jobs, errors = [], []
    for task, slots in definition["fixed_task_slots"].items():
        if task not in residual:
            continue
        try:
            views = [
                read_ref(pairs[sid]["A_request"])["candidate_request"]["trajectory"]
                for sid in slots
            ]
            bindings = dict(
                v15_definition_id=definition["id"],
                task_slot_ids=slots,
                mapping_review=definition["mapping_review"],
                original_records=[
                    {
                        k: pairs[sid][k]
                        for k in ("slot_id", "pair", "A_record", "B_record", "A_request")
                    }
                    for sid in slots
                ],
            )
            req = protocol.prepare_mapping(
                views, protocol_id=definition["id"], source_bindings=bindings
            )
            body = protocol.request_body(req)
            wire = canonical(body)
            require(
                req["purpose"] == req["role"] == "mapping" and req["slot_ids"] == slots,
                "mapping-only original complete task required",
            )
            directory = output / "requests" / req["episode_id"].split(":", 1)[1]
            persist(directory, req)
            jobs.append(
                dict(
                    kind="mapping",
                    purpose="mapping",
                    role="mapping",
                    task_id=task,
                    slot_id=None,
                    slot_ids=slots,
                    episode_id=req["episode_id"],
                    authority_reason="mapping_completion",
                    request_id=req["id"],
                    request=entry(directory / "record.json"),
                    request_file_sha256=sha(directory / "record.json"),
                    request_sha256=digest(body),
                    request_body_sha256=hashlib.sha256(wire).hexdigest(),
                    max_output_tokens=req["max_output_tokens"],
                    wire_bytes=len(wire),
                    capacity=req["capacity"],
                )
            )
        except Exception as exc:
            errors.append(dict(task_id=task, type=type(exc).__name__, message=str(exc)))
    drift = source_bindings(REQUEST_SOURCES) != definition["source_request_bindings"]
    result = bound(
        dict(
            schema="v15_mapping_preparation.v1",
            at=now(),
            definition_id=definition["id"],
            protocol_identity=definition["id"],
            jobs=jobs,
            error_count=len(errors),
            errors=errors,
            source_drift=drift,
            complete=not errors and not drift and len(jobs) == len(residual),
            no_Student_observations_consumed=True,
            all_requests_prepared_before_prefix_required=True,
            dispatch_order="original_fixed_task_order_residual_only",
            output_cap_counts=dict(Counter(str(j["max_output_tokens"]) for j in jobs)),
            total_wire_bytes=sum(j["wire_bytes"] for j in jobs),
            max_wire_bytes=max((j["wire_bytes"] for j in jobs), default=0),
            no_model_call=True,
            no_wallet_registration=True,
            no_input_truncation=True,
        )
    )
    publish(output / "preparation", result)
    return result


prepare_residual = prepare_mapping


def register_plan(output=OUTPUT):
    from .v15_mapping_protocol import policy_definition

    output = Path(output).resolve()
    definition = checked(output / "definition/record.json")
    prepared = checked(output / "preparation/record.json")
    previous = read_ref(definition["source_v14_plan"])
    require(
        prepared["complete"]
        and prepared["definition_id"] == definition["id"]
        and source_bindings(REQUEST_SOURCES) == definition["source_request_bindings"],
        "all exact requests and unchanged mapping policy/source required before prefix binding",
    )
    plan = bound(
        dict(
            schema="v15_fixed_mapping_plan.v1",
            at=now(),
            batch_id=BATCH_ID,
            protocol_identity=definition["id"],
            definition=entry(output / "definition/record.json"),
            preparation=entry(output / "preparation/record.json"),
            mapping_review=definition["mapping_review"],
            source_root=definition["source_root"],
            source_batch_id=previous["batch_id"],
            source_protocol_id=previous["id"],
            source_review_seal_id=definition["source_v14_seal"]["id"],
            model="deepseek-flash",
            policy_id=policy_definition()["id"],
            source_bindings=source_bindings(),
            jobs=prepared["jobs"],
            expected_requests=definition["expected_requests"],
            purpose_counts=definition["purpose_counts"],
            fixed_task_slots=definition["fixed_task_slots"],
            candidate_slot_ids=definition["candidate_slot_ids"],
            fixed_unresolved_task_ids=definition["fixed_unresolved_task_ids"],
            residual_task_ids=definition["residual_task_ids"],
            inherited_mapping_authority_refs=definition["inherited_mapping_authority_refs"],
            budget_database=previous["budget_database"],
            budget_config=previous["budget_config"],
            budget_config_sha256=previous["budget_config_sha256"],
            transport=previous["transport"],
            network_policy=previous["network_policy"],
            concurrency=CONCURRENCY,
            dispatch_order=prepared["dispatch_order"],
            prefix_binding_must_reference_this_registration_and_mapping_review=True,
            no_Student_observations_consumed=True,
            no_mask_or_task_or_original_order_change=True,
            automatic_retries=False,
            money_and_request_caps_unchanged=True,
            no_completion_guarantee=True,
        )
    )
    publish(output / "registration", plan)
    return plan


def checked_plan(output=OUTPUT):
    from .v15_mapping_protocol import policy_definition

    output = Path(output).resolve()
    plan = checked(output / "registration/record.json")
    require(
        plan["schema"] == "v15_fixed_mapping_plan.v1"
        and plan["batch_id"] == BATCH_ID
        and plan["model"] == "deepseek-flash"
        and plan["concurrency"] == CONCURRENCY
        and plan["source_bindings"] == source_bindings()
        and plan["policy_id"] == policy_definition()["id"],
        "registered frozen V15 mapping source/model/runtime differs",
    )
    definition = read_ref(plan["definition"])
    prepared = read_ref(plan["preparation"])
    read_ref(plan["mapping_review"])
    require(
        prepared["complete"]
        and prepared["jobs"] == plan["jobs"]
        and plan["expected_requests"] == definition["expected_requests"] == len(plan["jobs"]) <= 54
        and len(plan["fixed_unresolved_task_ids"]) == 54,
        "all mapping inputs must be frozen before Student prefix can consume its binding",
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
    parser.add_argument("action", choices=["prepare", "register"])
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--source", type=Path, default=SOURCE)
    parser.add_argument("--mapping-review", type=Path)
    args = parser.parse_args()
    if args.action == "prepare":
        require(
            args.mapping_review is not None, "fixed54 zero-model review must precede preparation"
        )
        result = prepare_mapping(
            args.output, mapping_review=args.mapping_review, source=args.source
        )
    else:
        result = register_plan(args.output)
    print(
        json.dumps(
            dict(id=result["id"], complete=result.get("complete", True), output=str(args.output)),
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
