"""Offline full-roster preparation and exact V12 production registration."""

from __future__ import annotations

import argparse
import hashlib
import json
import multiprocessing
import os
from collections import Counter
from pathlib import Path

from .calibration import now, publish
from .contracts import Episode, digest
from .probe_budget import ProbeBudget, read_budget_snapshot
from .storage import read_json
from .v6_collection import bound, persist, require, sha
from .v12_review_protocol import (
    BATCH_ID,
    MODEL,
    canonical,
    policy_definition,
    prepare_request,
    request_body,
)

STUDY = Path(
    "/data1/zhuxinrui/projects/Data-Synthesis/trusted_data_synthesis/artifacts/finance_research_20260928/finqa_v6_01"
)
SOURCE = STUDY / "v10_new8000_01"
OUTPUT = STUDY / "v12_rereview_02"
CONCURRENCY = dict(
    max=64,
    ramp=[
        dict(settled_at_least=0, workers=16),
        dict(settled_at_least=16, workers=32),
        dict(settled_at_least=64, workers=64),
    ],
)
REQUEST_SOURCES = (
    "v12_review_protocol.py",
    "v12_review_capacity.py",
    "v11_process_review.py",
    "v6_task.py",
    "contracts.py",
)
EXECUTION_SOURCES = REQUEST_SOURCES + (
    "v12_review_registration.py",
    "v12_review_controller.py",
    "v12_review_provider.py",
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
        "registered V12 evidence identity differs",
    )
    return value


def entry(path):
    path = Path(path).resolve()
    return dict(path=str(path), id=checked(path)["id"], sha256=sha(path))


def source_bindings(names=EXECUTION_SOURCES):
    return {name: sha(Path(__file__).parent / name) for name in names}


def _prepare_slot(item):
    state = _PREPARE
    slot, outcome, native = item
    try:
        path = Path(outcome["episode_path"]).resolve()
        expected = (
            Path(state["source"])
            / "slots"
            / slot["slot_id"].split(":", 1)[1]
            / "episode/episode.json"
        )
        raw = path.read_bytes()
        require(
            path == expected and hashlib.sha256(raw).hexdigest() == outcome["episode_file_sha256"],
            "original episode bytes/path changed",
        )
        episode = Episode.model_validate_json(raw)
        integrity = checked(outcome["integrity_path"])
        require(
            outcome["status"] == "COMPLETE"
            and integrity["episode_sha256"] == digest(episode) == outcome["episode_sha256"]
            and integrity["id"] == outcome["integrity_id"]
            and all(v is True for v in integrity["checks"].values())
            and native["Q_native"] is True,
            "complete mechanically bound native-correct original required",
        )
        jobs = []
        for role in ("A", "B"):
            req = prepare_request(
                episode,
                slot_id=slot["slot_id"],
                role=role,
                native_result=native["native"],
                integrity=integrity["checks"],
                protocol_id=state["definition"]["id"],
            )
            body = request_body(req)
            directory = Path(state["output"]) / "requests" / req["episode_id"].split(":", 1)[1]
            persist(directory, req)
            jobs.append(
                dict(
                    kind="review",
                    episode_id=req["episode_id"],
                    slot_id=slot["slot_id"],
                    task_id=slot["task_id"],
                    role=role,
                    max_output_tokens=req["max_output_tokens"],
                    request_id=req["id"],
                    request_sha256=digest(body),
                    request_body_sha256=hashlib.sha256(canonical(body)).hexdigest(),
                    request_file_sha256=sha(directory / "record.json"),
                    wire_bytes=len(canonical(body)),
                    capacity=req["capacity"],
                )
            )
        return dict(slot_id=slot["slot_id"], jobs=jobs, error=None)
    except Exception as exc:
        return dict(
            slot_id=slot["slot_id"], jobs=[], error=dict(type=type(exc).__name__, message=str(exc))
        )


def prepare_matrix(output=OUTPUT, source=SOURCE, *, workers=8):
    """No wallet open or model call; all 11438 requests must be ready before registration."""
    global _PREPARE
    output, source = Path(output).resolve(), Path(source).resolve()
    require(
        not (output / "preparation/record.json").exists(),
        "keep previous preparation; never overwrite a frozen roster",
    )
    old = checked(source / "registration/protocol.json")
    generation = checked(source / "generation_seal/record.json")
    native = checked(source / "native_support/record.json")
    require(
        old["id"] == generation["protocol_id"] == native["protocol_id"]
        and native["generation_seal_id"] == generation["id"]
        and len(old["slots"]) == len(generation["slots"]) == len(native["rows"]) == 8000
        and [r["slot"] for r in generation["slots"]]
        == [r["slot"] for r in native["rows"]]
        == old["slots"],
        "original complete 8000 roster/native source required",
    )
    eligible = [row for row in native["rows"] if row["Q_native"] is True]
    require(len(eligible) == 5719, "exact whole existing 5719 candidate population required")
    inputs = {
        rel: entry(source / rel)
        for rel in (
            "registration/protocol.json",
            "generation_seal/record.json",
            "native_support/record.json",
            "transport_proxy_01/authorization/record.json",
        )
    }
    definition = bound(
        dict(
            schema="v12_rereview_definition.v1",
            batch_id=BATCH_ID,
            model=MODEL,
            original_task_denominator=1000,
            original_slot_denominator=8000,
            source_root=str(source),
            source_batch_id=old["batch_id"],
            source_protocol_id=old["id"],
            source_inputs=inputs,
            policy=policy_definition(),
            eligible_slots=[r["slot"] for r in eligible],
            expected_pairs=5719,
            expected_reviews=11438,
            source_request_bindings=source_bindings(REQUEST_SOURCES),
            one_new_A_and_B_for_every_original=True,
            old_valid_results_reused=False,
            request_authorization="重新审阅",
            output_limit_auto_retry=False,
            material_projection_failures_do_not_remove_joint_candidates=True,
            no_mapping_and_no_training=True,
        )
    )
    persist(output / "definition", definition)
    outcomes = {r["slot"]["slot_id"]: r for r in generation["slots"]}
    items = [(r["slot"], outcomes[r["slot"]["slot_id"]], r) for r in eligible]
    _PREPARE = dict(source=str(source), output=str(output), definition=definition)
    results, jobs, caps, errors = [], [], Counter(), []
    require(type(workers) is int and 1 <= workers <= 8, "one to eight preparation CPU workers")
    pool = multiprocessing.get_context("fork").Pool(workers) if workers > 1 else None
    try:
        iterator = (
            pool.imap(_prepare_slot, items, chunksize=1) if pool else map(_prepare_slot, items)
        )
        for i, result in enumerate(iterator, 1):
            results.append(result["slot_id"])
            if result["error"]:
                errors.append(result)
            else:
                jobs.extend(result["jobs"])
                caps.update(f"{j['role']}:{j['max_output_tokens']}" for j in result["jobs"])
            if i % 128 == 0:
                print(
                    json.dumps(
                        dict(
                            stage="V12_PREPARE",
                            processed_pairs=i,
                            denominator=5719,
                            errors=len(errors),
                        )
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
        "request implementation changed during preparation",
    )
    complete = not errors and len(jobs) == 11438
    record = bound(
        dict(
            schema="v12_full_matrix_preparation.v1",
            at=now(),
            definition_id=definition["id"],
            protocol_identity=definition["id"],
            ordered_slots=results,
            expected_pairs=5719,
            expected_reviews=11438,
            complete=complete,
            jobs=jobs,
            error_count=len(errors),
            errors=errors,
            output_cap_counts=dict(caps),
            total_wire_bytes=sum(j["wire_bytes"] for j in jobs),
            max_wire_bytes=max((j["wire_bytes"] for j in jobs), default=0),
            no_input_truncation=True,
            no_model_call=True,
            old_review_labels_not_consulted=True,
        )
    )
    publish(output / "preparation", record)
    return record


def register_plan(output=OUTPUT):
    """Freeze complete requests and runtime/source scope; budget application is separate."""
    output = Path(output).resolve()
    definition = checked(output / "definition/record.json")
    preparation = checked(output / "preparation/record.json")
    require(
        preparation["complete"]
        and preparation["definition_id"] == definition["id"]
        and len(preparation["jobs"]) == 11438,
        "no prefix can register production",
    )
    require(
        source_bindings(REQUEST_SOURCES) == definition["source_request_bindings"],
        "prepared request source changed",
    )
    old = checked(Path(definition["source_root"]) / "registration/protocol.json")
    authorization = checked(
        Path(definition["source_root"]) / "transport_proxy_01/authorization/record.json"
    )
    record = bound(
        dict(
            schema="v12_complete_rereview_plan.v1",
            at=now(),
            batch_id=BATCH_ID,
            protocol_identity=definition["id"],
            definition=entry(output / "definition/record.json"),
            preparation=entry(output / "preparation/record.json"),
            source_root=definition["source_root"],
            source_batch_id=old["batch_id"],
            source_protocol_id=old["id"],
            model=MODEL,
            policy_id=policy_definition()["id"],
            source_bindings=source_bindings(),
            budget_database=old["budget_database"],
            budget_config=old["budget_config"],
            budget_config_sha256=old["budget_config_sha256"],
            jobs=preparation["jobs"],
            expected_pairs=5719,
            expected_reviews=11438,
            source_native_support_id=definition["source_inputs"]["native_support/record.json"][
                "id"
            ],
            concurrency=CONCURRENCY,
            concurrency_authorization=dict(
                user_request="查询官方文档，提高并发",
                official_account_limit=2500,
                reference="https://api-docs.deepseek.com/zh-cn/quick_start/rate_limit/",
                account_level_not_per_key=True,
                global_provider_usage_not_observed=True,
                runtime_max=64,
                ramp_on_transport_settlements_not_semantics=True,
            ),
            network_policy=dict(
                automatic_retry=False,
                same_wave_connection_unknown_threshold=3,
                pending_zero_before_acknowledgement=True,
                original_holds_permanent=True,
                acknowledge_exact_no_response_network_failures_only=True,
                unknown_is_terminal_not_positive=True,
                service_unknown_not_automatically_acknowledged=True,
                guard_stops_without_automatic_restart=True,
            ),
            transport=dict(
                mode="explicit_proxy",
                source_env="HTTPS_PROXY",
                proxy_url_sha256=authorization["proxy_url_sha256"],
                parent_authorization=definition["source_inputs"][
                    "transport_proxy_01/authorization/record.json"
                ],
                trust_env=False,
                verify_TLS=True,
                retries=0,
                read_timeout_seconds=1200,
            ),
            request_transfer=dict(
                generation_before=199000,
                generation_after=191000,
                review_mapping_before=17000,
                review_mapping_after=25000,
                total_request_cap=258000,
                unallocated_requests_unchanged=True,
            ),
            money_caps_unchanged=dict(
                total_microcny=2000000000, review_mapping_microcny=1300000000
            ),
            accepted_risk="批准调拨，按现费用上限尝试",
            no_completion_guarantee=True,
            source_generation_or_native_rerun=False,
            old_verdict_reuse=False,
            no_mapping=True,
            no_training=True,
        )
    )
    publish(output / "registration", record)
    return record


def checked_plan(output=OUTPUT):
    output = Path(output).resolve()
    plan = checked(output / "registration/record.json")
    require(
        plan["schema"] == "v12_complete_rereview_plan.v1"
        and plan["batch_id"] == BATCH_ID
        and plan["model"] == MODEL
        and plan["source_bindings"] == source_bindings(),
        "exact registered V12 code/model required",
    )
    require(
        plan["policy_id"] == policy_definition()["id"]
        and plan["concurrency"] == CONCURRENCY
        and plan["expected_reviews"] == len(plan["jobs"]) == 11438
        and len({j["episode_id"] for j in plan["jobs"]}) == 11438,
        "runtime/policy/complete matrix changed",
    )
    for key in ("definition", "preparation"):
        ref = plan[key]
        require(
            sha(ref["path"]) == ref["sha256"] and checked(ref["path"])["id"] == ref["id"],
            "immutable request registration changed",
        )
    return plan


def ledger_for(plan):
    current = read_budget_snapshot(plan["budget_database"])
    require(
        current["config_sha256"] == plan["budget_config_sha256"],
        "shared wallet config changed; never create/reset it",
    )
    cfg = plan["budget_config"]
    return ProbeBudget(
        plan["budget_database"],
        **{
            k: cfg[k]
            for k in (
                "run_id",
                "price_sheet",
                "max_output_tokens",
                "purpose",
                "hard_cap_microcny",
                "warning_microcny",
                "request_cap",
                "amendment_id",
                "allowed_output_limits",
            )
        },
    )


def resolve_proxy(plan):
    config = plan["transport"]
    value = os.environ.get(config["source_env"])
    require(
        config["mode"] == "explicit_proxy"
        and isinstance(value, str)
        and hashlib.sha256(value.encode()).hexdigest() == config["proxy_url_sha256"],
        "explicit approved proxy missing/changed; no direct fallback",
    )
    return value


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
