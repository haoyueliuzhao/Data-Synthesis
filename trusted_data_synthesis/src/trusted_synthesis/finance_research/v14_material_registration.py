"""Zero-call residual preparation after the uniform existing-representation audit."""

import argparse
import hashlib
import json
from collections import Counter
from itertools import zip_longest
from pathlib import Path

from .calibration import now, publish
from .contracts import digest
from .v6_collection import bound, persist, require, sha
from .v13_material_registration import checked, entry, read_ref

STUDY = Path(
    "/data1/zhuxinrui/projects/Data-Synthesis/trusted_data_synthesis/artifacts/finance_research_20260928/finqa_v6_01"
)
SOURCE = STUDY / "v13_material_02"
OUTPUT = STUDY / "v14_representation_01"
BATCH_ID = "finqa-v14-20260930-representation-01"
AUDIT = Path(
    "/home/zhuxinrui/.codex/attachments/1094385e-368e-4a06-80f5-49876fbbfa72/已粘贴的文本.txt"
)
CONCURRENCY = {"max": 16, "ramp": [{"settled_at_least": 0, "workers": 16}]}
REQUEST_SOURCES = (
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
    "v14_material_registration.py",
    "v14_material_provider.py",
    "v14_material_controller.py",
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


def define_residual(output, representation_review, source=SOURCE):
    from .v14_material_protocol import policy_definition

    output, source = Path(output).resolve(), Path(source).resolve()
    review_ref = entry(Path(representation_review).resolve())
    review = read_ref(review_ref)
    previous = checked(source / "registration/record.json")
    parent = read_ref(previous["definition"])
    seal = checked(source / "completion_seal/record.json")
    require(
        review["schema"] == "v14_representation_review.v1"
        and review["mapping_review_count"] == 633
        and review["original_successes_preserved"] == 325
        and review["original_success_partition_evidence_chi_unchanged"] is True
        and review["policy"] == policy_definition()
        and all(
            sha(Path(__file__).parent / name) == expected
            for name, expected in review["source_protocol_hashes"].items()
        )
        and review["source_v13_plan"]["id"] == previous["id"]
        and review["source_v13_completion_seal"]["id"] == seal["id"]
        and seal["registration_id"] == previous["id"]
        and seal["expected_calls"] == 1316
        and seal["actual_returns"] == 1304
        and seal["network_unknowns"] == 12,
        "complete original V13 and uniform representation-review evidence required",
    )
    groups = parent["fixed_task_slots"]
    candidates = parent["candidate_slot_ids"]
    multi = {task for task, slots in groups.items() if len(slots) > 1}
    mapping_ok = {r["task_id"] for r in review["mapping_authority_refs"]}
    projection_ok = {r["slot_id"] for r in review["inherited_projection_authority_refs"]}
    projection_derived = {r["slot_id"] for r in review["derived_projection_authority_refs"]}
    missing_p = review["residual_projection_slot_ids"]
    missing_m = review["residual_mapping_task_ids"]
    network = review["network_unknown_task_ids"]
    require(
        len(candidates) == 2468
        and len(groups) == 744
        and len(multi) == 645
        and len(mapping_ok) == len(review["mapping_authority_refs"])
        and mapping_ok.isdisjoint(missing_m)
        and mapping_ok | set(missing_m) == multi
        and len(projection_ok) == len(review["inherited_projection_authority_refs"]) == 2465
        and len(projection_derived) == len(review["derived_projection_authority_refs"]) <= 2
        and projection_ok.isdisjoint(projection_derived)
        and (projection_ok | projection_derived).isdisjoint(missing_p)
        and projection_ok | projection_derived | set(missing_p) == set(candidates)
        and len(missing_p) == len(set(missing_p)) <= 3
        and len(missing_m) == len(set(missing_m)) <= 320
        and len(network) == len(set(network)) == 12
        and set(network) <= set(missing_m)
        and 0 <= review["m"] == 320 - len(missing_m) <= 256
        and 0 <= review["b"] == 3 - len(missing_p) <= 2
        and len(missing_p) + len(missing_m) <= 323,
        "exact residual authority must preserve all fixed common packages/tasks",
    )
    result = bound(
        dict(
            schema="v14_fixed_residual_definition.v1",
            batch_id=BATCH_ID,
            source_root=str(source),
            source_v13_definition=previous["definition"],
            source_v13_plan=entry(source / "registration/record.json"),
            source_v13_seal=entry(source / "completion_seal/record.json"),
            source_material_support=entry(source / "material/support/record.json"),
            representation_review=review_ref,
            parent_fixed_population_id=parent["id"],
            candidate_slot_ids=candidates,
            fixed_task_slots=groups,
            pairs=parent["pairs"],
            residual_projection_slot_ids=missing_p,
            residual_mapping_task_ids=missing_m,
            network_unknown_task_ids=network,
            network_unknown_sources=review["network_unknown_sources"],
            expected_requests=len(missing_p) + len(missing_m),
            purpose_counts={"projection": len(missing_p), "mapping": len(missing_m)},
            policy=policy_definition(),
            source_request_bindings=source_bindings(REQUEST_SOURCES),
            field_authority_fixed_before_new_returns=True,
            old_valid_authorities_preserved=True,
            new_failures_never_fall_back_to_old_invalid=True,
            no_new_generation=True,
            no_AB_rereview=True,
            fixed_complete_population_required=True,
            training_authorized_by_preparation=False,
            user_request="参照审计修订并开展后续实验",
            audit={"path": str(AUDIT), "sha256": sha(AUDIT)},
        )
    )
    persist(output / "definition", result)
    return result


def prepare_residual(output=OUTPUT, *, representation_review, source=SOURCE):
    from . import v14_material_protocol as protocol

    output = Path(output).resolve()
    require(
        not (output / "preparation/record.json").exists(),
        "preserve earlier preparation; use a new output revision",
    )
    definition = define_residual(output, representation_review, source)
    pairs = {p["slot_id"]: p for p in definition["pairs"]}
    missing_p = set(definition["residual_projection_slot_ids"])
    missing_m = set(definition["residual_mapping_task_ids"])
    network = set(definition["network_unknown_task_ids"])
    network_sources = {r["task_id"]: r for r in definition["network_unknown_sources"]}
    queues = {"projection": [], "mapping": []}
    errors = []
    for task, slots in definition["fixed_task_slots"].items():
        projections = [sid for sid in slots if sid in missing_p]
        if not projections and task not in missing_m:
            continue
        try:
            views = [
                read_ref(pairs[sid]["A_request"])["candidate_request"]["trajectory"]
                for sid in slots
            ]
            bindings = dict(
                v14_definition_id=definition["id"],
                task_slot_ids=slots,
                representation_review=definition["representation_review"],
                original_records=[
                    {
                        k: pairs[sid][k]
                        for k in ("slot_id", "pair", "A_record", "B_record", "A_request")
                    }
                    for sid in slots
                ],
            )
            requests = [
                protocol.prepare_projection(
                    view, protocol_id=definition["id"], source_bindings=bindings
                )
                for view in views
                if view["slot_id"] in missing_p
            ]
            if task in missing_m:
                requests.append(
                    protocol.prepare_mapping(
                        views, protocol_id=definition["id"], source_bindings=bindings
                    )
                )
            for req in requests:
                body = protocol.request_body(req)
                wire = canonical(body)
                directory = output / "requests" / req["episode_id"].split(":", 1)[1]
                persist(directory, req)
                kind = req["purpose"]
                reason = (
                    "projection_completion"
                    if kind == "projection"
                    else ("network_recovery_new_once" if task in network else "mapping_completion")
                )
                queues[kind].append(
                    dict(
                        kind=kind,
                        purpose=kind,
                        role=kind,
                        episode_id=req["episode_id"],
                        task_id=task,
                        slot_id=req.get("slot_id"),
                        slot_ids=req["slot_ids"],
                        authority_reason=reason,
                        original_network_source=network_sources[task]
                        if reason == "network_recovery_new_once"
                        else None,
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
    jobs = [
        job
        for pair in zip_longest(queues["projection"], queues["mapping"])
        for job in pair
        if job is not None
    ]
    drift = source_bindings(REQUEST_SOURCES) != definition["source_request_bindings"]
    result = bound(
        dict(
            schema="v14_residual_preparation.v1",
            at=now(),
            definition_id=definition["id"],
            protocol_identity=definition["id"],
            jobs=jobs,
            error_count=len(errors),
            errors=errors,
            source_drift=drift,
            complete=not errors and not drift and len(jobs) == definition["expected_requests"],
            kind_counts=dict(Counter(j["kind"] for j in jobs)),
            dispatch_order="alternate_projection_mapping_preserving_each_purpose_order",
            output_cap_counts=dict(Counter(f"{j['kind']}:{j['max_output_tokens']}" for j in jobs)),
            total_wire_bytes=sum(j["wire_bytes"] for j in jobs),
            max_wire_bytes=max((j["wire_bytes"] for j in jobs), default=0),
            no_model_call=True,
            no_wallet_registration=True,
            no_input_truncation=True,
        )
    )
    publish(output / "preparation", result)
    return result


def register_plan(output=OUTPUT):
    from .v14_material_protocol import policy_definition

    output = Path(output).resolve()
    definition = checked(output / "definition/record.json")
    prepared = checked(output / "preparation/record.json")
    previous = read_ref(definition["source_v13_plan"])
    require(
        prepared["complete"]
        and prepared["definition_id"] == definition["id"]
        and source_bindings(REQUEST_SOURCES) == definition["source_request_bindings"],
        "exact complete residual requests and unchanged request source required",
    )
    plan = bound(
        dict(
            schema="v14_fixed_residual_material_plan.v1",
            at=now(),
            batch_id=BATCH_ID,
            protocol_identity=definition["id"],
            definition=entry(output / "definition/record.json"),
            preparation=entry(output / "preparation/record.json"),
            representation_review=definition["representation_review"],
            source_root=definition["source_root"],
            source_batch_id=previous["batch_id"],
            source_protocol_id=previous["id"],
            source_review_seal_id=definition["source_v13_seal"]["id"],
            model="deepseek-flash",
            policy_id=policy_definition()["id"],
            source_bindings=source_bindings(),
            jobs=prepared["jobs"],
            expected_requests=definition["expected_requests"],
            purpose_counts=definition["purpose_counts"],
            fixed_task_slots=definition["fixed_task_slots"],
            candidate_slot_ids=definition["candidate_slot_ids"],
            network_unknown_task_ids=definition["network_unknown_task_ids"],
            budget_database=previous["budget_database"],
            budget_config=previous["budget_config"],
            budget_config_sha256=previous["budget_config_sha256"],
            transport=previous["transport"],
            network_policy=previous["network_policy"],
            concurrency=CONCURRENCY,
            dispatch_order=prepared["dispatch_order"],
            automatic_retries=False,
            field_authority_not_best_of=True,
            money_and_request_caps_unchanged=True,
            no_partial_training=True,
            original_unknown_holds_permanent=True,
            no_completion_guarantee=True,
        )
    )
    publish(output / "registration", plan)
    return plan


def checked_plan(output=OUTPUT):
    from .v14_material_protocol import policy_definition

    output = Path(output).resolve()
    plan = checked(output / "registration/record.json")
    require(
        plan["schema"] == "v14_fixed_residual_material_plan.v1"
        and plan["batch_id"] == BATCH_ID
        and plan["model"] == "deepseek-flash"
        and plan["concurrency"] == CONCURRENCY
        and plan["source_bindings"] == source_bindings()
        and plan["policy_id"] == policy_definition()["id"],
        "registered new V14 source/model/runtime differs; old source gates are not disabled",
    )
    definition = read_ref(plan["definition"])
    preparation = read_ref(plan["preparation"])
    read_ref(plan["representation_review"])
    require(
        preparation["complete"]
        and plan["jobs"] == preparation["jobs"]
        and plan["expected_requests"]
        == definition["expected_requests"]
        == len(plan["jobs"])
        <= 323,
        "complete frozen residual matrix required",
    )
    return plan


def ledger_for(plan):
    from .v12_review_registration import ledger_for as old_ledger

    return old_ledger(plan)


def resolve_proxy(plan):
    from .v13_material_registration import resolve_proxy as original_proxy

    return original_proxy(plan)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["prepare", "register"])
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--source", type=Path, default=SOURCE)
    parser.add_argument("--representation-review", type=Path)
    args = parser.parse_args()
    if args.action == "prepare":
        require(
            args.representation_review is not None, "uniform offline review must be supplied first"
        )
        result = prepare_residual(
            args.output, representation_review=args.representation_review, source=args.source
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
