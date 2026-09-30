"""Fixed V12 candidate population, typed missing measurements, no cohort repair."""

from __future__ import annotations

import argparse
import hashlib
import json
import multiprocessing
import os
from collections import Counter
from itertools import zip_longest
from pathlib import Path

from .calibration import now, publish
from .contracts import digest
from .storage import read_json
from .v6_collection import bound, persist, require, sha
from .v12_review_registration import CONCURRENCY

STUDY = Path(
    "/data1/zhuxinrui/projects/Data-Synthesis/trusted_data_synthesis/artifacts/"
    "finance_research_20260928/finqa_v6_01"
)
SOURCE = STUDY / "v12_rereview_02"
OUTPUT = STUDY / "v13_material_02"
AUDIT = Path(
    "/home/zhuxinrui/.codex/attachments/5aee0df4-6c07-493a-b0df-96f321761034/已粘贴的文本.txt"
)
BATCH_ID = "finqa-v13-20260930-material-01"
REQUEST_SOURCES = (
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
    "v13_material_registration.py",
    "v13_material_provider.py",
    "v13_material_controller.py",
    "v13_budget.py",
    "v12_budget.py",
    "v10_budget.py",
    "probe_budget.py",
    "v10_funding.py",
)
_PREPARE = None


def checked(path):
    value = read_json(path)
    require(
        value.get("id") == digest({k: v for k, v in value.items() if k != "id"}),
        "registered V13 source identity changed",
    )
    return value


def entry(path):
    path = Path(path).resolve()
    return dict(path=str(path), id=checked(path)["id"], sha256=sha(path))


def read_ref(ref):
    require(sha(ref["path"]) == ref["sha256"], "original referenced bytes changed")
    value = checked(ref["path"])
    require(value["id"] == ref["id"], "original referenced ID changed")
    return value


def source_bindings(names=EXECUTION_SOURCES):
    return {name: sha(Path(__file__).parent / name) for name in names}


def define_population(output=OUTPUT, source=SOURCE):
    from .v13_material_protocol import policy_definition

    output, source = Path(output).resolve(), Path(source).resolve()
    previous = checked(source / "registration/record.json")
    seal = checked(source / "review_seal/record.json")
    require(
        seal["registration_id"] == previous["id"]
        and seal["protocol_id"] == previous["protocol_identity"]
        and seal["all_model_responses_returned"] is True
        and seal["actual_returns"] == seal["expected_reviews"] == 11438
        and seal["expected_pairs"] == 5719
        and seal["production_admitted"] is False,
        "complete actual V12 inventory required, never a prefix",
    )
    candidates = seal["joint_process_candidate_slot_ids"]
    missing = seal["projection_blocked_candidate_slot_ids"]
    require(
        len(candidates) == len(set(candidates)) == 2468
        and len(missing) == len(set(missing)) == 671
        and set(missing) < set(candidates),
        "retain the fixed 2468 candidates including all 671 missing projections",
    )
    original_root = Path(previous["source_root"]).resolve()
    generation = checked(original_root / "generation_seal/record.json")
    native = checked(original_root / "native_support/record.json")
    original = checked(original_root / "registration/protocol.json")
    require(
        original["id"] == generation["protocol_id"] == native["protocol_id"]
        and native["generation_seal_id"] == generation["id"]
        and previous["source_protocol_id"] == original["id"],
        "same original generation/native cohort required",
    )
    inputs = {
        "source_v12_plan": entry(source / "registration/record.json"),
        "source_v12_seal": entry(source / "review_seal/record.json"),
        "source_v10_plan": entry(original_root / "registration/protocol.json"),
        "source_generation": entry(original_root / "generation_seal/record.json"),
        "source_native": entry(original_root / "native_support/record.json"),
    }
    g_by_slot = {r["slot"]["slot_id"]: r for r in generation["slots"]}
    n_by_slot = {r["slot"]["slot_id"]: r for r in native["rows"]}
    jobs = {(j["slot_id"], j["role"]): j for j in previous["jobs"]}
    pair_refs = {Path(ref["path"]).parent.name: ref for ref in seal["paired_cores"]}
    candidate_set = set(candidates)
    require(
        [
            j["slot_id"]
            for j in previous["jobs"]
            if j["role"] == "A" and j["slot_id"] in candidate_set
        ]
        == candidates,
        "original registered candidate order changed",
    )
    pairs, fixed_tasks = [], {}
    for slot in candidates:
        ref = pair_refs[slot.split(":", 1)[1]]
        pair = read_ref(ref)
        task = jobs[(slot, "A")]["task_id"]
        require(
            pair["slot_id"] == slot
            and pair["task_id"] == task
            and pair["joint_process_candidate"] is True
            and pair["both_actual_responses_returned"] is True
            and pair["Q_native_as_registered"] is True
            and pair["A_projection_usable"] is (slot not in missing)
            and pair["registration_id"] == previous["id"],
            "candidate process/projection scope changed",
        )
        a, b = (read_ref(pair[f"{role}_terminal"]) for role in ("A", "B"))
        require(
            all(t["actual_model_response_returned"] is True for t in (a, b)),
            "field authorities must retain actual original model receipts",
        )
        a_job = jobs[(slot, "A")]
        a_request = source / "requests" / a_job["episode_id"].split(":", 1)[1] / "record.json"
        outcome, score = g_by_slot[slot], n_by_slot[slot]
        require(
            outcome["status"] == "COMPLETE" and score["Q_native"] is True,
            "same native-correct original episode required",
        )
        pairs.append(
            dict(
                slot_id=slot,
                task_id=task,
                pair=ref,
                A_record=a["record"],
                B_record=b["record"],
                A_request=dict(
                    path=str(a_request), id=a_job["request_id"], sha256=a_job["request_file_sha256"]
                ),
                original_episode=dict(
                    path=outcome["episode_path"],
                    sha256=outcome["episode_file_sha256"],
                    episode_sha256=outcome["episode_sha256"],
                ),
                original_integrity=entry(outcome["integrity_path"]),
                native_result=score["native"],
                projection_authority="V13_completion_only" if slot in missing else "V12_A_original",
            )
        )
        fixed_tasks.setdefault(task, []).append(slot)
    tasks = [
        dict(
            task_id=task,
            slot_ids=slots,
            partition_mode="model_once" if len(slots) > 1 else "deterministic_singleton",
        )
        for task, slots in fixed_tasks.items()
    ]
    require(
        len(tasks) == 744 and sum(len(t["slot_ids"]) == 1 for t in tasks) == 99,
        "fixed 744 tasks, 645 multiple-package and 99 true singletons required",
    )
    result = bound(
        dict(
            schema="v13_fixed_candidate_population.v1",
            batch_id=BATCH_ID,
            source_root=str(source),
            source_v10_root=str(original_root),
            inputs=inputs,
            source_review_seal_id=seal["id"],
            source_v12_protocol_id=previous["protocol_identity"],
            audit=dict(path=str(AUDIT), sha256=sha(AUDIT)),
            user_request="参照审计修订并开展后续实验",
            policy=policy_definition(),
            source_request_bindings=source_bindings(REQUEST_SOURCES),
            original_task_denominator=1000,
            original_slot_denominator=8000,
            native_correct_pairs=5719,
            native_correct_tasks=820,
            candidate_slot_ids=candidates,
            projection_completion_slot_ids=missing,
            fixed_task_slots=fixed_tasks,
            pairs=pairs,
            tasks=tasks,
            expected_candidates=2468,
            expected_tasks=744,
            expected_projections=671,
            preserved_original_projections=1797,
            expected_mappings=645,
            deterministic_singletons=99,
            expected_paid_requests=1316,
            fixed_field_authority_before_new_returns=True,
            old_qualification_rejudged=False,
            complete_population_required_before_training=True,
            no_failed_projection_dropped=True,
            singleton_chi=None,
            singleton_chi_status="not_required_for_weighting",
            singleton_rule_applies_only_to_actual_one_package_tasks=True,
            no_raw_JSON_repair=True,
            no_new_generation=True,
            no_AB_rereview=True,
            no_retry=True,
            no_automatic_budget_increase=True,
            structural_D_pi_upper_bound=1724,
            observed_D_pi=None,
            training_plan_is_conditional_not_executed=True,
            five_arms=["Static", "Manual+", "Manual-", "C-only", "Full"],
            seeds=[11, 29, 47],
        )
    )
    persist(output / "definition", result)
    return result


def _prepare_task(task):
    from . import v13_material_protocol as protocol

    state = _PREPARE
    try:
        pairs = [state["pairs"][slot] for slot in task["slot_ids"]]
        views = [read_ref(p["A_request"])["candidate_request"]["trajectory"] for p in pairs]
        source = dict(
            v13_population_id=state["definition"]["id"],
            task_slot_ids=task["slot_ids"],
            source_review_seal=state["definition"]["inputs"]["source_v12_seal"],
            original_records=[
                {k: p[k] for k in ("slot_id", "pair", "A_record", "B_record", "A_request")}
                for p in pairs
            ],
        )
        requests = [
            protocol.prepare_projection(
                v, protocol_id=state["definition"]["id"], source_bindings=source
            )
            for p, v in zip(pairs, views, strict=True)
            if p["projection_authority"] == "V13_completion_only"
        ]
        singletons = []
        if task["partition_mode"] == "model_once":
            requests.append(
                protocol.prepare_mapping(
                    views, protocol_id=state["definition"]["id"], source_bindings=source
                )
            )
        else:
            single = protocol.singleton(
                views[0], protocol_id=state["definition"]["id"], source_bindings=source
            )
            path = Path(state["output"]) / "deterministic_singletons" / digest(task["task_id"])
            persist(path, single)
            singletons.append(dict(task_id=task["task_id"], record=entry(path / "record.json")))
        jobs = []
        for req in requests:
            body = protocol.request_body(req)
            raw = json.dumps(
                body, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
            ).encode()
            require(
                len(raw) + req["max_output_tokens"] < 1048576,
                "full task/input-output boundary exceeded; no clipping",
            )
            path = Path(state["output"]) / "requests" / req["episode_id"].split(":", 1)[1]
            persist(path, req)
            kind = req["purpose"]
            jobs.append(
                dict(
                    kind=kind,
                    purpose=kind,
                    role=kind,
                    episode_id=req["episode_id"],
                    task_id=task["task_id"],
                    slot_id=req.get("slot_id"),
                    slot_ids=req["slot_ids"],
                    max_output_tokens=req["max_output_tokens"],
                    request_id=req["id"],
                    request=entry(path / "record.json"),
                    request_sha256=digest(body),
                    request_body_sha256=hashlib.sha256(raw).hexdigest(),
                    request_file_sha256=sha(path / "record.json"),
                    wire_bytes=len(raw),
                    capacity=req["capacity"],
                )
            )
        return dict(task_id=task["task_id"], jobs=jobs, singletons=singletons, error=None)
    except Exception as exc:
        return dict(
            task_id=task["task_id"],
            jobs=[],
            singletons=[],
            error=dict(type=type(exc).__name__, message=str(exc)),
        )


def prepare_matrix(output=OUTPUT, source=SOURCE, *, workers=8):
    global _PREPARE
    output = Path(output).resolve()
    require(
        not (output / "preparation/record.json").exists(),
        "keep frozen preparation; never overwrite",
    )
    definition = define_population(output, source)
    _PREPARE = dict(
        output=str(output),
        definition=definition,
        pairs={p["slot_id"]: p for p in definition["pairs"]},
    )
    require(type(workers) is int and 1 <= workers <= 8, "one to eight preparation CPU workers")
    pool = multiprocessing.get_context("fork").Pool(workers) if workers > 1 else None
    jobs, singletons, errors, caps = [], [], [], Counter()
    try:
        iterator = (
            pool.imap(_prepare_task, definition["tasks"], chunksize=1)
            if pool
            else map(_prepare_task, definition["tasks"])
        )
        for index, result in enumerate(iterator, 1):
            if result["error"]:
                errors.append(result)
            else:
                jobs.extend(result["jobs"])
                singletons.extend(result["singletons"])
                caps.update(f"{j['kind']}:{j['max_output_tokens']}" for j in result["jobs"])
            if index % 64 == 0:
                print(
                    json.dumps(
                        dict(stage="V13_PREPARE", tasks=index, denominator=744, errors=len(errors))
                    ),
                    flush=True,
                )
    finally:
        if pool:
            pool.close()
            pool.join()
        _PREPARE = None
    require(
        source_bindings(REQUEST_SOURCES) == definition["source_request_bindings"],
        "request source changed during preparation",
    )
    kinds = Counter(j["kind"] for j in jobs)
    # Both independent measurements can occupy the same wave, without an outcome gate.
    purpose_queues = [[j for j in jobs if j["kind"] == kind] for kind in ("projection", "mapping")]
    jobs = [j for pair in zip_longest(*purpose_queues) for j in pair if j is not None]
    complete = (
        not errors and kinds == Counter(projection=671, mapping=645) and len(singletons) == 99
    )
    result = bound(
        dict(
            schema="v13_full_measurement_preparation.v1",
            at=now(),
            protocol_identity=definition["id"],
            definition_id=definition["id"],
            complete=complete,
            jobs=jobs,
            singletons=singletons,
            error_count=len(errors),
            errors=errors,
            kind_counts=kinds,
            dispatch_order="alternate_projection_mapping_preserving_each_purpose_order",
            output_cap_counts=caps,
            total_wire_bytes=sum(j["wire_bytes"] for j in jobs),
            max_wire_bytes=max((j["wire_bytes"] for j in jobs), default=0),
            no_input_truncation=True,
            no_model_call=True,
        )
    )
    publish(output / "preparation", result)
    return result


def register_plan(output=OUTPUT):
    from .v13_material_protocol import policy_definition

    output = Path(output).resolve()
    definition = checked(output / "definition/record.json")
    preparation = checked(output / "preparation/record.json")
    require(
        preparation["complete"] and preparation["definition_id"] == definition["id"],
        "only all 1316 calls plus 99 deterministic partitions may register",
    )
    require(
        source_bindings(REQUEST_SOURCES) == definition["source_request_bindings"],
        "prepared source changed",
    )
    previous = read_ref(definition["inputs"]["source_v12_plan"])
    plan = bound(
        dict(
            schema="v13_fixed_candidate_material_plan.v1",
            at=now(),
            batch_id=BATCH_ID,
            protocol_identity=definition["id"],
            definition=entry(output / "definition/record.json"),
            preparation=entry(output / "preparation/record.json"),
            source_root=definition["source_root"],
            source_v10_root=definition["source_v10_root"],
            source_batch_id=previous["batch_id"],
            source_protocol_id=previous["id"],
            source_review_seal_id=definition["source_review_seal_id"],
            model="deepseek-flash",
            policy_id=policy_definition()["id"],
            source_bindings=source_bindings(),
            budget_database=previous["budget_database"],
            budget_config=previous["budget_config"],
            budget_config_sha256=previous["budget_config_sha256"],
            jobs=preparation["jobs"],
            dispatch_order=preparation["dispatch_order"],
            singletons=preparation["singletons"],
            expected_requests=1316,
            expected_projections=671,
            expected_mappings=645,
            expected_singletons=99,
            expected_candidates=2468,
            expected_tasks=744,
            fixed_task_slots=definition["fixed_task_slots"],
            candidate_slot_ids=definition["candidate_slot_ids"],
            projection_completion_slot_ids=definition["projection_completion_slot_ids"],
            singleton_task_ids=[
                t["task_id"]
                for t in definition["tasks"]
                if t["partition_mode"] == "deterministic_singleton"
            ],
            concurrency=CONCURRENCY,
            transport=previous["transport"],
            network_policy=previous["network_policy"],
            user_request="参照审计修订并开展后续实验",
            audit=definition["audit"],
            effective_hard_cap_microcny=2000000000,
            effective_review_mapping_microcny=1300000000,
            global_request_cap=258000,
            review_mapping_request_cap=25000,
            field_authority_not_best_of=True,
            new_AB_review=False,
            new_generation=False,
            deterministic_singletons_are_not_model_returns=True,
            complete_material_required_before_training=True,
            no_completion_guarantee=True,
            automatic_retries=False,
            additional_budget_authorized=False,
        )
    )
    publish(output / "registration", plan)
    return plan


def checked_plan(output=OUTPUT):
    from .v13_material_protocol import policy_definition

    output = Path(output).resolve()
    plan = checked(output / "registration/record.json")
    require(
        plan["schema"] == "v13_fixed_candidate_material_plan.v1"
        and plan["batch_id"] == BATCH_ID
        and plan["model"] == "deepseek-flash"
        and plan["source_bindings"] == source_bindings()
        and plan["policy_id"] == policy_definition()["id"]
        and plan["concurrency"] == CONCURRENCY,
        "exact registered V13 code/model/runtime required",
    )
    for key in ("definition", "preparation"):
        read_ref(plan[key])
    require(
        len(plan["jobs"]) == len({j["episode_id"] for j in plan["jobs"]}) == 1316
        and Counter(j["kind"] for j in plan["jobs"]) == Counter(projection=671, mapping=645)
        and len(plan["singletons"]) == 99,
        "fixed complete measurement matrix changed",
    )
    return plan


def resolve_proxy(plan):
    config = plan["transport"]
    value = os.environ.get(config["source_env"])
    require(
        config["mode"] == "explicit_proxy"
        and isinstance(value, str)
        and hashlib.sha256(value.encode()).hexdigest() == config["proxy_url_sha256"],
        "same approved proxy required; no direct fallback",
    )
    return value


def ledger_for(plan):
    """Open the unchanged original wallet; the new permit is a separate operation."""
    from .v12_review_registration import ledger_for as original_ledger

    return original_ledger(plan)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["prepare", "register"])
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--source", type=Path, default=SOURCE)
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()
    result = (
        prepare_matrix(args.output, args.source, workers=args.workers)
        if args.action == "prepare"
        else register_plan(args.output)
    )
    print(
        json.dumps(
            dict(id=result["id"], complete=result.get("complete", True), output=str(args.output)),
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
