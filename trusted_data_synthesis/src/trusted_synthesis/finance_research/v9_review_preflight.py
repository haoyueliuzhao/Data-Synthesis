"""Read-only-wallet, zero-API sizing of every V8 native-correct original package.

The conditional population does not change any V8 review rule or output capacity.
Artifacts contain all original eight slots, not an affordable success prefix.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from multiprocessing import get_context
from pathlib import Path

from .calibration import now
from .contracts import Episode, PrivateReference, digest
from .probe_budget import ProbePriceSheet, read_budget_snapshot
from .probe_collection import slot_directory
from .providers import _json
from .storage import _read_snapshot_rows, load_public_snapshot, read_json
from .v6_collection import STUDY, bound, mechanical_check, persist, require, sha
from .v6_decomposed_review import bind_capacity, job_directory, job_key
from .v6_task import public_trajectory_view
from .v8_collection import checked_record
from .v8_review_policy import policy_definition
from .v8_single_target_review import capacity_features, slot_review_request

GENERATION = STUDY / "new_full_probe_v8_launch_01"
OUTPUT = STUDY / "conditional_five_arm_v9_01"
TECHNICAL = STUDY / "audit_revision_20260929/review_validation_108_01"


def task_input_path(output, task_id):
    return Path(output) / "preflight/tasks" / digest(task_id) / "record.json"


def load_task_input(output, task_id):
    value = checked_record(task_input_path(output, task_id))
    require(
        value["schema"] == "v9_conditioned_task_review_inputs.v1"
        and value["task_id"] == task_id
        and value["prepared"]["id"]
        == digest({k: v for k, v in value["prepared"].items() if k != "id"}),
        "conditional task input changed",
    )
    return value


def request_body(request):
    """Same complete wire fields as v6_review_provider, without opening a wallet."""
    require(request["model"] == "deepseek-flash", "fixed API model changed")
    require(
        request["review_policy_id"] == policy_definition()["id"]
        and request["strict_tool_sha256"] == digest(request["strict_tool"]),
        "frozen review contract changed",
    )
    return dict(
        model=request["model"],
        messages=request["messages"],
        temperature=0,
        top_p=1,
        max_tokens=request["max_output_tokens"],
        thinking={"type": "disabled"},
        stream=False,
        tools=[request["strict_tool"]],
        tool_choice={"type": "function", "function": {"name": "submit_review"}},
    )


class ParentInventory:
    """Bind the sealed parent once; stream each task's eight original episodes."""

    def __init__(self, parent=GENERATION):
        self.parent = Path(parent)
        self.plan = checked_record(self.parent / "registration/protocol.json")
        self.seal = checked_record(self.parent / "generation_seal/record.json")
        self.native = checked_record(self.parent / "native_support/record.json")
        require(
            self.seal["protocol_id"] == self.native["protocol_id"] == self.plan["id"]
            and self.native["generation_seal_id"] == self.seal["id"]
            and self.plan["task_denominator"] == 1000
            and self.plan["slot_denominator"] == self.seal["denominator"] == 8000
            and self.native["native_unknown_slots"] == 0,
            "whole original 1000/8000 sealed native population required",
        )
        self.slots = {t: [] for t in self.plan["task_ids"]}
        for slot in self.plan["slots"]:
            self.slots[slot["task_id"]].append(slot)
        require(
            len(self.slots) == 1000
            and all(
                [s["slot_index"] for s in slots] == list(range(8)) for slots in self.slots.values()
            ),
            "all original eight-slot coordinates required",
        )
        self.outcomes = {r["slot"]["slot_id"]: r for r in self.seal["slots"]}
        self.scores = {r["slot"]["slot_id"]: r for r in self.native["rows"]}
        ids = {s["slot_id"] for s in self.plan["slots"]}
        require(
            len(ids) == len(self.outcomes) == len(self.scores) == 8000
            and ids == set(self.outcomes) == set(self.scores)
            and all(self.scores[s["slot_id"]]["slot"] == s for s in self.plan["slots"])
            and sum(r["Q_native"] is True for r in self.scores.values()) == 5691
            and all(type(r["Q_native"]) is bool for r in self.scores.values()),
            "native records differ; no rescoring or splicing",
        )
        manifest, tasks, _ = load_public_snapshot(self.plan["snapshot"])
        require(manifest["id"] == self.plan["snapshot_id"], "source snapshot changed")
        refs = _read_snapshot_rows(
            self.plan["snapshot"], "private.references.jsonl", PrivateReference, manifest
        )
        wanted = set(self.slots)
        self.tasks = {t.task_id: t for t in tasks if t.task_id in wanted}
        self.references = {r.task_id: r for r in refs if r.task_id in wanted}
        require(set(self.tasks) == set(self.references) == wanted, "public/private task binding")
        policy = checked_record(self.plan["review_policy"]["path"])
        require(
            sha(self.plan["review_policy"]["path"]) == self.plan["review_policy"]["sha256"]
            and policy["definition"] == policy_definition(),
            "V8 policy must remain unchanged",
        )
        self.budget = read_budget_snapshot(self.plan["budget_database"])
        require(
            self.budget["config_sha256"] == self.plan["budget_config_sha256"],
            "original joint wallet changed",
        )
        self.sheet = ProbePriceSheet(**self.plan["budget_config"]["price_sheet"])

    def prepared(self, task_id):
        views, mechanical, scores, episodes, tokens = [], {}, {}, {}, {}
        for slot in self.slots[task_id]:
            sid = slot["slot_id"]
            saved = self.outcomes[sid]
            path = slot_directory(self.parent, slot) / "episode/episode.json"
            raw = path.read_bytes()
            require(
                hashlib.sha256(raw).hexdigest() == saved["episode_file_sha256"], "episode changed"
            )
            episode = Episode.model_validate_json(raw)
            require(
                saved["status"] == "COMPLETE"
                and saved["slot"] == slot
                and digest(episode) == saved["episode_sha256"]
                and episode.task_id == task_id
                and episode.config.model_dump(mode="json") == self.plan["configs_by_task"][task_id],
                "original complete generation binding changed",
            )
            check = mechanical_check(
                self.tasks[task_id], episode, slot, {"id": self.plan["budget_config"]["run_id"]}
            )
            require(
                all(
                    check[k] is True
                    for k in (
                        "sealed",
                        "calls_settled",
                        "history_complete",
                        "actions_observations_bound",
                        "private_reference_isolated",
                    )
                ),
                "original public history does not replay",
            )
            check["native_correct"] = self.scores[sid]["Q_native"]
            mechanical[sid], scores[sid] = check, self.scores[sid]["native"]
            views.append(dict(slot_id=sid, trajectory=public_trajectory_view(episode, slot_id=sid)))
            episodes[sid] = dict(
                path=str(path),
                sha256=saved["episode_file_sha256"],
                episode_sha256=saved["episode_sha256"],
            )
            tokens[sid] = sum(t.usage["completion_tokens"] for t in episode.turns)
        bundle = dict(
            schema="v6_task_review_bundle.v1", task_id=task_id, seal_id=self.seal["id"], slots=views
        )
        return dict(
            prepared=bound(dict(bundle=bundle, mechanical=mechanical, native_scores=scores)),
            private_reference=self.references[task_id].model_dump(mode="json"),
            episodes=episodes,
            generation_tokens=tokens,
        )


def prepare_task(inventory, task_id):
    data = inventory.prepared(task_id)
    prepared = data["prepared"]
    requests, jobs, features, eligible = {}, [], {}, []
    for slot in inventory.slots[task_id]:
        sid = slot["slot_id"]
        # Q=False requests are constructed only to measure unchanged all-eight
        # alignment workload; they are neither saved as dispatch jobs nor sent.
        first = slot_review_request(prepared, sid, data["private_reference"], 0)
        measured = capacity_features(first)
        features[sid] = dict(
            generation_tokens=data["generation_tokens"][sid],
            target_fragments=measured["target_fragment_count"],
            actions=measured["action_count"],
        )
        if prepared["mechanical"][sid]["native_correct"] is not True:
            continue
        eligible.append(sid)
        for reviewer in (0, 1):
            request = (
                first
                if reviewer == 0
                else slot_review_request(prepared, sid, data["private_reference"], reviewer)
            )
            capacity = bind_capacity(
                request,
                generation_tokens=features[sid]["generation_tokens"],
                fragments=features[sid]["target_fragments"],
                actions=features[sid]["actions"],
            )
            key = job_key("slot", task_id, reviewer, sid)
            wire = _json(request_body(request)).encode("utf-8")
            requests[key] = request
            jobs.append(
                dict(
                    key=key,
                    stage="slot",
                    task_id=task_id,
                    slot_id=sid,
                    slot_index=slot["slot_index"],
                    reviewer=reviewer,
                    request_sha256=digest(request),
                    capacity=capacity,
                    exact_http_body_bytes=len(wire),
                )
            )
    alignment = (
        bind_capacity(
            None,
            generation_tokens=sum(v["generation_tokens"] for v in features.values()),
            fragments=sum(v["target_fragments"] for v in features.values()),
            actions=sum(v["actions"] for v in features.values()),
            alignment=True,
        )
        if eligible
        else None
    )
    return bound(
        dict(
            schema="v9_conditioned_task_review_inputs.v1",
            task_id=task_id,
            parent_launch_id=inventory.plan["id"],
            parent_seal_id=inventory.seal["id"],
            parent_native_support_id=inventory.native["id"],
            review_policy_id=policy_definition()["id"],
            **data,
            requests=requests,
            jobs=jobs,
            slot_features=features,
            q_true_slot_ids=eligible,
            alignment_capacity=alignment,
            original_slot_count=8,
            q_false_review_dispatched=False,
        )
    )


def cost_summary(jobs, sheet, remaining_microcny):
    """Separate exact frozen caps from conditional tokenization size scenarios."""
    count = len(jobs)
    output = sum(j["capacity"]["max_output_tokens"] for j in jobs)
    visible_bytes = sum(j.get("exact_http_body_bytes", 0) for j in jobs)
    official_input = count * sheet.context_input_token_ceiling
    output_cost = sheet.cost_microcny(hit=0, miss=0, output=output)
    official_cost = sum(
        sheet.cost_microcny(
            hit=0, miss=sheet.context_input_token_ceiling, output=j["capacity"]["max_output_tokens"]
        )
        for j in jobs
    )
    return dict(
        calls=count,
        output_capacity_histogram=dict(
            sorted(Counter(str(j["capacity"]["max_output_tokens"]) for j in jobs).items())
        ),
        frozen_output_tokens_total=output,
        exact_http_body_bytes_total=visible_bytes,
        exact_http_body_bytes_known_calls=sum("exact_http_body_bytes" in j for j in jobs),
        output_full_capacity_cost_microcny=output_cost,
        output_full_capacity_cost_fits_remaining=output_cost <= remaining_microcny,
        official_input_token_ceiling_total=official_input,
        guaranteed_tariff_upper_bound_microcny=official_cost,
        guaranteed_upper_bound_fits_remaining=official_cost <= remaining_microcny,
        actual_api_input_tokens_known=False,
        official_context_ceiling_is_not_expected_input_usage=True,
        output_capacity_is_not_predicted_usage=True,
    )


def historical_forecast(new_jobs, sheet, technical=TECHNICAL):
    """Load-based descriptive extrapolation, explicitly not a completion guarantee."""
    plan = checked_record(Path(technical) / "registration/protocol.json")
    stats = {
        stage: dict(
            calls=0,
            prompt_tokens=0,
            completion_tokens=0,
            estimated_requirement=0,
            settled_microcny=0,
            exact_http_body_bytes=0,
        )
        for stage in ("slot", "alignment")
    }
    for job in plan["jobs"]:
        record = read_json(job_directory(technical, job) / "response/record.json")
        artifact = record.get("artifact", record)
        usage = artifact["usage"]
        item = stats[job["stage"]]
        item["calls"] += 1
        item["prompt_tokens"] += usage["prompt_tokens"]
        item["completion_tokens"] += usage["completion_tokens"]
        item["estimated_requirement"] += job["capacity"]["estimated_requirement"]
        item["exact_http_body_bytes"] += len(_json(artifact["public_request"]).encode("utf-8"))
        item["settled_microcny"] += sheet.cost_microcny(
            hit=usage["prompt_cache_hit_tokens"],
            miss=usage["prompt_cache_miss_tokens"],
            output=usage["completion_tokens"],
        )
    forecast = {}
    for stage, history in stats.items():
        selected = [j for j in new_jobs if j["stage"] == stage]
        ratio = (
            sum(j["capacity"]["estimated_requirement"] for j in selected)
            / history["estimated_requirement"]
        )
        prompt_ratio = (
            sum(j["exact_http_body_bytes"] for j in selected) / history["exact_http_body_bytes"]
            if stage == "slot"
            else ratio
        )
        predicted_prompt = math.ceil(history["prompt_tokens"] * prompt_ratio)
        predicted_output = math.ceil(history["completion_tokens"] * ratio)
        forecast[stage] = dict(
            historical=history,
            new_calls=len(selected),
            actual_load_estimator_ratio=ratio,
            flat_per_call_cost_microcny=math.ceil(
                history["settled_microcny"] * len(selected) / history["calls"]
            ),
            load_scaled_cost_microcny=math.ceil(history["settled_microcny"] * ratio),
            load_scaled_prompt_tokens=math.ceil(history["prompt_tokens"] * ratio),
            load_scaled_completion_tokens=math.ceil(history["completion_tokens"] * ratio),
            actual_wire_size_ratio=prompt_ratio if stage == "slot" else None,
            size_load_scenario_prompt_tokens=predicted_prompt,
            size_load_scenario_completion_tokens=predicted_output,
            size_load_scenario_all_input_miss_cost_microcny=sheet.cost_microcny(
                hit=0, miss=predicted_prompt, output=predicted_output
            ),
        )
    return dict(
        historical_protocol_id=plan["id"],
        stages=forecast,
        flat_per_call_total_microcny=sum(
            v["flat_per_call_cost_microcny"] for v in forecast.values()
        ),
        load_scaled_total_microcny=sum(v["load_scaled_cost_microcny"] for v in forecast.values()),
        size_load_scenario_all_input_miss_total_microcny=sum(
            v["size_load_scenario_all_input_miss_cost_microcny"] for v in forecast.values()
        ),
        completion_guarantee=False,
        confidence_interval_claimed=False,
        assumptions=[
            "Old six-task technical sample is not representative or random "
            "relative to the new native-correct population.",
            "Frozen load estimator ratios are descriptive sensitivity scenarios, "
            "not calibrated token forecasts.",
            "Actual cache-hit mix and response lengths may differ; "
            "failed semantic responses were not excluded.",
            "No caps, prompts, request ordering, wallet or qualification rules "
            "are changed to fit this estimate.",
            "Size/load scenario scales slot prompt tokens by actual complete wire bytes; "
            "outputs and future alignment inputs use unchanged load-estimator ratios. "
            "All predicted input tokens are priced as cache misses, but token counts "
            "remain empirical predictions, not guaranteed upper bounds.",
        ],
    )


_WORK_CONTEXT = None


def _initialize_worker(inventory, output):
    global _WORK_CONTEXT
    _WORK_CONTEXT = (inventory, output)


def _one_task(task_id):
    inventory, output = _WORK_CONTEXT
    path = task_input_path(output, task_id)
    if path.exists():
        payload = load_task_input(output, task_id)
        require(
            payload["parent_launch_id"] == inventory.plan["id"]
            and payload["parent_seal_id"] == inventory.seal["id"]
            and payload["parent_native_support_id"] == inventory.native["id"],
            "partial preflight parent changed",
        )
    else:
        payload = prepare_task(inventory, task_id)
        persist(path.parent, payload)
    result = list(payload["jobs"])
    if payload["q_true_slot_ids"]:
        for reviewer in (0, 1):
            result.append(
                dict(
                    key=job_key("alignment", task_id, reviewer),
                    stage="alignment",
                    task_id=task_id,
                    reviewer=reviewer,
                    slot_id=None,
                    capacity=payload["alignment_capacity"],
                )
            )
    return (
        task_id,
        dict(
            path=str(path),
            id=payload["id"],
            sha256=sha(path),
            native_correct=len(payload["q_true_slot_ids"]),
        ),
        result,
    )


def run_preflight(output=OUTPUT, parent=GENERATION, workers=16):
    output = Path(output)
    require(
        not (output / "preflight/report/record.json").exists(),
        "preflight is immutable; load existing result",
    )
    inventory = ParentInventory(parent)
    records, jobs = {}, []

    with ProcessPoolExecutor(
        max_workers=workers,
        mp_context=get_context("fork"),
        initializer=_initialize_worker,
        initargs=(inventory, output),
    ) as pool:
        for index, (task_id, binding, prepared_jobs) in enumerate(
            pool.map(_one_task, inventory.plan["task_ids"]), 1
        ):
            records[task_id] = binding
            jobs.extend(prepared_jobs)
            if index % 50 == 0:
                print(
                    json.dumps(
                        dict(preflight_tasks=index, total_tasks=1000, no_api_dispatched=True)
                    ),
                    flush=True,
                )
    require(
        Counter(j["stage"] for j in jobs) == dict(slot=11382, alignment=1640),
        "complete call scope changed",
    )
    after = read_budget_snapshot(inventory.plan["budget_database"])
    require(after == inventory.budget, "wallet changed during zero-API preflight")
    remaining = after["snapshot"]["remaining_exposure_microcny"]
    report = bound(
        dict(
            schema="v9_complete_review_cost_preflight.v1",
            at=now(),
            model="deepseek-flash",
            parent_launch_id=inventory.plan["id"],
            parent_seal_id=inventory.seal["id"],
            parent_native_support_id=inventory.native["id"],
            parent_directory=str(parent),
            review_policy_id=policy_definition()["id"],
            candidate_tasks=1000,
            original_slots=8000,
            native_correct_slots=5691,
            native_ineligible_slots=2309,
            native_supported_tasks=820,
            training_task_count=None,
            task_inputs=records,
            jobs=jobs,
            budget_snapshot=after,
            remaining_exposure_microcny=remaining,
            stages={
                stage: cost_summary(
                    [j for j in jobs if j["stage"] == stage], inventory.sheet, remaining
                )
                for stage in ("slot", "alignment")
            },
            complete=cost_summary(jobs, inventory.sheet, remaining),
            forecast=historical_forecast(jobs, inventory.sheet),
            price_sheet=inventory.plan["budget_config"]["price_sheet"],
            capacity_policy_unchanged=True,
            all_original_slots_retained=True,
            all_native_true_requests_constructed=True,
            no_api_dispatched=True,
            api_calls=0,
            gpu_work=False,
            wallet_unchanged=True,
            production_dispatch_authorized=False,
            limitations=[
                "Alignment messages depend on own-side actual future reviews "
                "and cannot yet have exact request bytes.",
                "All 1640 alignment caps use unchanged V8 formula and all eight original "
                "trajectories, including native-false context.",
                "Exact HTTP bytes include tool schema and full original request, "
                "but are not exact model input tokens.",
                "Official input context ceiling is a conservative guaranteed token bound, "
                "not a forecast of actual usage.",
                "Full output capacities alone exceed the remaining wallet; "
                "lowering them or reviewing a cheap prefix is not authorized.",
            ],
        )
    )
    persist(output / "preflight/report", report)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--parent", type=Path, default=GENERATION)
    parser.add_argument("--workers", type=int, default=16)
    args = parser.parse_args(argv)
    value = run_preflight(args.output, args.parent, args.workers)
    print(
        json.dumps(
            {k: value[k] for k in ("id", "complete", "forecast", "no_api_dispatched")},
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
