#!/usr/bin/env python3
"""Summarize the six actual adjudications without reading any Student signals."""

import argparse
from collections import Counter
from datetime import datetime
from pathlib import Path

from trusted_synthesis.finance_research.calibration import now
from trusted_synthesis.finance_research.v6_collection import bound, persist, require
from trusted_synthesis.finance_research.v13_material_registration import checked, entry, read_ref
from trusted_synthesis.finance_research.v16_registration import OUTPUT


def summarize(
    output,
    destination,
    *,
    expected_calls=6,
    expected_packages=24,
    inherited_tasks=738,
    schema="v16_actual_six_task_report.v1",
):
    output = Path(output).resolve()
    plan = checked(output / "registration/record.json")
    definition = read_ref(plan["definition"])
    result = checked(output / "controller_result/record.json")
    require(result["registration_id"] == plan["id"], "same six-task execution required")
    require(result["completion_seal"] is not None, "report real returned six-task matrix only")
    seal = read_ref(result["completion_seal"])
    tokens = Counter()
    fee, tasks = 0, []
    for ref in seal["terminals"]:
        terminal = read_ref(ref)
        record = read_ref(terminal["record"])
        artifact, inspection = record["artifact"], record["inspection"]
        tokens.update(
            {
                k: artifact["usage"][k]
                for k in (
                    "prompt_tokens",
                    "completion_tokens",
                    "prompt_cache_hit_tokens",
                    "prompt_cache_miss_tokens",
                    "total_tokens",
                )
            }
        )
        fee += artifact["peak_tariff_upper_bound_microcny"]
        tasks.append(
            dict(
                task_id=terminal["task_id"],
                original_packages=len(record["slot_ids"]),
                authority=terminal["record"],
                original_failure=definition["previous_failed_authorities"][terminal["task_id"]],
                mapping_admitted=inspection["mapping_admitted"],
                errors=inspection["errors"],
                states=[
                    dict(
                        state_id=s["state_id"],
                        members=s["slot_ids"],
                        chi=s["chi"],
                        basis=s["basis"],
                    )
                    for s in inspection["states"]
                ],
                resolution=inspection["resolution"],
                unresolved=inspection["unresolved"],
                finish_reason=artifact["finish_reason"],
                completion_tokens=artifact["usage"]["completion_tokens"],
                output_cap=record["request"]["max_output_tokens"],
                cost_microcny=artifact["peak_tariff_upper_bound_microcny"],
            )
        )
    before, after = result["before_budget"], result["after_budget"]
    require(
        len(tasks) == expected_calls
        and sum(t["original_packages"] for t in tasks) == expected_packages
        and after["settled_tariff_microcny"] - before["settled_tariff_microcny"] == fee
        and after["held_microcny"] == before["held_microcny"]
        and after["unknown_requests"] == before["unknown_requests"],
        "six actual settlements conserve budget and historical UNKNOWN holds",
    )
    material_path = output / "material/result/record.json"
    support_path = output / "material/support/record.json"
    profile = None
    if material_path.exists():
        support = checked(support_path)
        profile = {
            k: v for k, v in support["capability_profile"].items() if k != "package_reason_coverage"
        }
    report = bound(
        dict(
            schema=schema,
            at=now(),
            registration=entry(output / "registration/record.json"),
            controller_result=entry(output / "controller_result/record.json"),
            completion_seal=result["completion_seal"],
            fixed_tasks=expected_calls,
            fixed_packages=expected_packages,
            inherited_tasks_unchanged=inherited_tasks,
            original_738_authorities_unchanged=True,
            returned=expected_calls,
            usable=sum(t["mapping_admitted"] for t in tasks),
            controller_elapsed_seconds=(
                datetime.fromisoformat(seal["at"]) - datetime.fromisoformat(seal["started_at"])
            ).total_seconds(),
            tokens=dict(tokens),
            settled_upper_bound_microcny=fee,
            before_budget=before,
            after_budget=after,
            original_UNKNOWN_count=after["unknown_requests"],
            original_UNKNOWN_hold_microcny=after["held_microcny"],
            new_UNKNOWN_count=0,
            new_UNKNOWN_hold_microcny=0,
            automatic_retries=0,
            tasks=tasks,
            complete_capability_profile=profile,
            material_result=entry(material_path) if material_path.exists() else None,
            same_model="deepseek-flash",
            source_is_model_judgment_not_independent_financial_truth=True,
            Student_signals_read=False,
            API_calls_by_this_report=0,
            GPU_used=False,
        )
    )
    persist(destination, report)
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--destination", type=Path, required=True)
    args = parser.parse_args()
    result = summarize(args.output, args.destination)
    print(
        {
            k: result[k]
            for k in ("id", "returned", "usable", "settled_upper_bound_microcny", "tokens")
        }
    )
