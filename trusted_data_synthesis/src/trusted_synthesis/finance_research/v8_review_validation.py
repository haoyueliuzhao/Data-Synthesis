"""One fixed 96+12 fresh V8 validation; no perfection-rate pilot or production loop.

Uses only the six original preselected old tasks. New generation may be in flight
in the same partitioned ledger. No new-generation outcomes or Base results are read.
"""

from __future__ import annotations

import argparse
import asyncio
import copy
import fcntl
import json
import math
import subprocess
from pathlib import Path

import httpx

from .calibration import ROOT, now, publish, status
from .contracts import Episode, digest
from .probe_budget import read_budget_snapshot
from .storage import read_json, runtime_binding
from .v6_collection import ENV_FILE, STUDY, bound, checked_prepared, require, sha
from .v6_decomposed_review import Context, bind_capacity, job_directory, job_key, task_inputs
from .v6_review_provider import request_review
from .v6_review_revision import ORIGINAL, _key
from .v8_collection import ledger_for
from .v8_review_policy import policy_definition
from .v8_single_target_review import (
    alignment_request,
    capacity_features,
    encode_reviewed_probe_for_student,
    inspect_alignment,
    inspect_slot_review,
    resolve_pair,
    slot_review_record,
    slot_review_request,
)

OUTPUT = STUDY / "audit_revision_20260929/review_validation_108_01"
GENERATION = STUDY / "new_full_probe_v8_launch_01/registration/protocol.json"
PUBLIC_BANK = STUDY / "review_revision_04"
MAXIMUM_CALLS = 108


def checked(path):
    value = read_json(path)
    require(
        value["id"] == digest({k: v for k, v in value.items() if k != "id"}), "bound record changed"
    )
    return value


def negative_controls():
    """Small synthetic finite-contract controls; not model observations or truth proof."""
    views = []
    for i in range(8):
        sid = f"s{i}"
        strings = [
            ("source", "source_text", "Revenue is 120."),
            (
                "content",
                "public_content",
                "Revenue is 120.\nQ: None; submitting the predicted program.",
            ),
            ("args", "action_arguments", '{"program":"add(120, 0)"}'),
            ("obs", "tool_observation", '{"submitted":true}'),
        ]
        view = dict(
            task_id="synthetic/contract",
            episode_sha256=f"fixture-{i}",
            view_id=f"view-{i}",
            slot_id=sid,
            segments=[
                dict(segment_id=k, kind=kind, text=t, start=0, end=len(t), turn_index=0)
                for k, kind, t in strings
            ],
            turns=[
                dict(
                    turn_index=0,
                    actions=[
                        dict(action_id="a", name="submit_program", arguments_segment_id="args")
                    ],
                )
            ],
            events=[dict(action_id="a", observation_segment_id="obs", is_error=False)],
        )
        views.append(dict(slot_id=sid, trajectory=view))
    bundle = dict(
        schema="v6_task_review_bundle.v1",
        task_id="synthetic/contract",
        seal_id="synthetic",
        slots=views,
    )
    request = slot_review_request(bundle, "s0", {}, 0)
    cat = request["document_catalog"]
    source = next(e for e, d in cat.items() if d["kind"] == "source_text")
    claim = next(
        e
        for e, d in cat.items()
        if d["kind"] == "public_content" and d["text"].startswith("Revenue")
    )
    action = next(e for e, d in cat.items() if d["kind"] == "action_arguments")
    targets = {
        e: dict(label="approved", proposition_ids=["p"], evidence=[source, e])
        if e in (claim, action)
        else dict(label="nonassertive_context", proposition_ids=[], evidence=[])
        for e, d in cat.items()
        if d["kind"] in {"public_content", "action_arguments"}
    }
    raw = dict(
        terms=[
            dict(
                term_id="t",
                subject="synthetic company",
                attribute="revenue",
                period="reported",
                value="120",
                unit="reporting unit",
                public_source_anchor_ids=[source],
            )
        ],
        nodes=[
            dict(
                node_id="n",
                predicate="answer",
                operation="none",
                term_ids=["t"],
                public_source_anchor_ids=[source],
                proposition_ids=["p"],
                accepted=True,
                evidence=[claim],
            )
        ],
        edges=[],
        v_trace="valid",
        reason_codes=[],
        coverage_complete=True,
        propositions=[
            dict(
                proposition_id="p",
                status="assertion",
                critical=True,
                judgment="supported",
                accepted=True,
                model_claim_ids=[claim],
                support_evidence_ids=[source],
                retraction_model_ids=[],
            )
        ],
        updates=[],
        targets=targets,
    )
    positive = inspect_slot_review(json.dumps(raw), request)
    cases = []
    for name in (
        "missing_target",
        "critical_unknown",
        "financial_nonassertive",
        "wrong_source",
        "duplicate_json",
    ):
        value = copy.deepcopy(raw)
        if name == "missing_target":
            value["targets"].pop(action)
        elif name == "critical_unknown":
            value["propositions"][0]["judgment"] = "unknown"
        elif name == "financial_nonassertive":
            value["targets"][claim] = dict(
                label="nonassertive_context", proposition_ids=[], evidence=[]
            )
        elif name == "wrong_source":
            value["terms"][0]["public_source_anchor_ids"] = [action]
        text = '{"targets":{},"targets":{}}' if name == "duplicate_json" else json.dumps(value)
        result = inspect_slot_review(text, request)
        refused = not result["interface_admitted"] or not result["semantic_consistent"]
        cases.append(dict(name=name, false_pass=not refused, error=result.get("error")))
    value = copy.deepcopy(raw)
    value["targets"][claim]["label"] = "unknown"
    result = inspect_slot_review(json.dumps(value), request)
    retained = result["validation"] and not result["validation"]["derived"]["mask_complete"]
    cases.append(dict(name="action_does_not_approve_other_content", false_pass=not bool(retained)))
    return bound(
        dict(
            schema="v8_finite_negative_controls.v1",
            synthetic_only=True,
            model_calls=0,
            positive_control=positive["semantic_consistent"],
            cases=cases,
            passed=positive["semantic_consistent"] and not any(c["false_pass"] for c in cases),
            financial_semantic_omniscience_claimed=False,
        )
    )


def fixed_scope(plan):
    jobs, tasks = plan["jobs"], plan["task_ids"]
    slots = [j for j in jobs if j["stage"] == "slot"]
    aligns = [j for j in jobs if j["stage"] == "alignment"]
    require(
        len(tasks) == len(set(tasks)) == 6
        and len(jobs) == len({j["key"] for j in jobs}) == 108
        and len(slots) == 96
        and len(aligns) == 12
        and plan["maximum_calls"] == 108,
        "fixed six-task full108 scope changed",
    )
    require(
        {(j["task_id"], j["slot_index"], j["reviewer"]) for j in slots}
        == {(t, s, r) for t in tasks for s in range(8) for r in (0, 1)}
        and {(j["task_id"], j["reviewer"]) for j in aligns}
        == {(t, r) for t in tasks for r in (0, 1)},
        "original fixed coordinates lost or selected",
    )


def register(output=OUTPUT, generation_launch=GENERATION):
    output = Path(output)
    require(not output.exists(), "one V8 technical batch only; never overwrite/restart a cohort")
    generation = checked(generation_launch)
    policy_path = Path(generation["review_policy"]["path"])
    policy = checked(policy_path)
    require(
        sha(policy_path) == generation["review_policy"]["sha256"]
        and policy["id"] == generation["review_policy"]["id"]
        and policy["definition"] == policy_definition(),
        "generation and review must share the pre-generation policy",
    )
    budget = read_budget_snapshot(generation["budget_database"])
    partition = budget["snapshot"].get("request_partition", {})
    require(
        budget["config_sha256"] == generation["budget_config_sha256"]
        and partition.get("partition_id") == generation["partition_id"]
        and partition["limits"]["technical_review"] == 108
        and partition["limits"]["production_review"] == 18000
        and partition["consumed"]["technical_review"] == 0,
        "original shared wallet/registered review partition differs or was already used",
    )
    require(
        not budget["snapshot"]["halt"]
        and not budget["snapshot"]["unacknowledged_unknown_requests"],
        "unknown shared costs must not be bypassed",
    )
    # Ordinary registered generation in-flight requests are allowed, not a quiescence gate.
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    for path in Path(__file__).parent.rglob("*.py"):
        require(
            path.read_bytes()
            == subprocess.check_output(
                ["git", "show", commit + ":" + str(path.relative_to(ROOT))], cwd=ROOT
            ),
            "freeze review source before dispatch registration",
        )
    bank_plan = checked(PUBLIC_BANK / "registration/protocol.json")
    bank = Context(PUBLIC_BANK, bank_plan)
    jobs, inputs, capacities = [], {}, {}
    for task_id in bank_plan["task_ids"]:
        prepared = checked_prepared(ORIGINAL, task_id)
        reference = json.loads(prepared["requests"][0]["messages"][1]["content"])[
            "review_only_private_reference"
        ]
        requests, features = {}, []
        for old in bank.slot_jobs[task_id]:
            request = slot_review_request(prepared, old["slot_id"], reference, old["reviewer"])
            f = capacity_features(request)
            cap = bind_capacity(
                request,
                generation_tokens=old["capacity"]["generation_tokens"],
                fragments=f["target_fragment_count"],
                actions=f["action_count"],
            )
            requests[old["key"]] = request
            jobs.append({**old, "capacity": cap, "request_sha256": digest(request)})
            if old["reviewer"] == 0:
                features.append(cap)
        inputs[task_id] = bound(
            dict(task_id=task_id, original_prepared_id=prepared["id"], requests=requests)
        )
        capacities[task_id] = bind_capacity(
            None,
            generation_tokens=sum(c["generation_tokens"] for c in features),
            fragments=sum(c["target_fragments"] for c in features),
            actions=sum(c["actions"] for c in features),
            alignment=True,
        )
    order = {t: i for i, t in enumerate(bank_plan["task_ids"])}
    jobs.sort(key=lambda j: (j["slot_index"], order[j["task_id"]], j["reviewer"]))
    for task_id in bank_plan["task_ids"]:
        for reviewer in (0, 1):
            jobs.append(
                dict(
                    key=job_key("alignment", task_id, reviewer),
                    stage="alignment",
                    task_id=task_id,
                    reviewer=reviewer,
                    slot_id=None,
                    capacity=capacities[task_id],
                )
            )
    controls = negative_controls()
    require(controls["passed"], "CPU finite negative controls failed; no real dispatch")
    body = dict(
        schema="v8_one_full_review_validation.v1",
        at=now(),
        source_commit=commit,
        runtime_binding=runtime_binding(),
        generation_launch_id=generation["id"],
        review_policy=dict(path=str(policy_path), id=policy["id"], sha256=sha(policy_path)),
        review_policy_id=policy["definition"]["id"],
        task_ids=bank_plan["task_ids"],
        jobs=jobs,
        maximum_calls=108,
        slot_denominator=96,
        alignment_denominator=12,
        technical_namespace="v8review:",
        model="deepseek-flash",
        retry_count=0,
        no_twelve_call_pilot=True,
        no_format_percentage_gate=True,
        no_success_splicing=True,
        negative_controls_id=controls["id"],
        old_R6_result_unchanged=True,
        old_preselected_public_bank=str(PUBLIC_BANK),
        original_generation_directory=str(ORIGINAL),
        budget_database=generation["budget_database"],
        budget_config=generation["budget_config"],
        budget_config_sha256=generation["budget_config_sha256"],
        partition_id=generation["partition_id"],
        pending_generation_allowed=True,
        automatic_production_review=False,
        automatic_next_technical_trial=False,
        automatic_training=False,
        GPU_reservation=False,
    )
    fixed_scope(body)
    publish(output / "negative_controls", controls)
    saved = {}
    for task_id, payload in inputs.items():
        path = task_inputs(output, task_id)
        publish(path, payload)
        saved[task_id] = dict(id=payload["id"], sha256=sha(path / "record.json"))
    plan = bound(body | dict(slot_inputs=saved))
    publish(output / "registration", plan, "protocol.json")
    return plan


def checked_plan(output):
    plan = checked(Path(output) / "registration/protocol.json")
    fixed_scope(plan)
    require(plan["runtime_binding"] == runtime_binding(), "frozen review implementation changed")
    policy = checked(plan["review_policy"]["path"])
    require(
        policy["definition"] == policy_definition()
        and policy["id"] == plan["review_policy"]["id"]
        and sha(plan["review_policy"]["path"]) == plan["review_policy"]["sha256"],
        "pre-generation policy changed",
    )
    return plan


class ReviewContext(Context):
    def slot_reviews(self, task_id, reviewer):
        result = {}
        for job in self.slot_jobs[task_id]:
            if job["reviewer"] == reviewer:
                artifact = read_json(job_directory(self.output, job) / "response/record.json")
                result[job["slot_id"]] = slot_review_record(self.request(job), artifact)
        require(
            len(result) == 8, "all original eight own-side reviews required, including unknowns"
        )
        return result

    def prepare_alignment(self, task_id):
        prepared = checked_prepared(ORIGINAL, task_id)
        for reviewer in (0, 1):
            job = self.jobs[job_key("alignment", task_id, reviewer)]
            request = alignment_request(prepared, self.slot_reviews(task_id, reviewer), reviewer)
            cap = job["capacity"]
            actual = bind_capacity(
                request,
                generation_tokens=cap["generation_tokens"],
                fragments=cap["target_fragments"],
                actions=cap["actions"],
                alignment=True,
            )
            require(actual == cap, "alignment capacity changed after results")
            publish(
                job_directory(self.output, job) / "request",
                bound(
                    dict(
                        protocol_id=self.plan["id"],
                        job_key=job["key"],
                        slot_review_hashes=self.slot_review_hashes(task_id, reviewer),
                        request=request,
                    )
                ),
            )


def _end_to_end(output, plan, context):
    """Every jointly qualified package in a mapped task is encoded; never select an easy subset."""
    from transformers import AutoTokenizer

    tokenizer = None
    generation = read_json(ORIGINAL / "generation_seal/record.json")
    paths = {row["slot"]["slot_id"]: row for row in generation["slots"]}
    original_plan = read_json(ORIGINAL / "protocol.json")
    tasks, paths_count = {}, 0
    for task_id in plan["task_ids"]:
        prepared = checked_prepared(ORIGINAL, task_id)
        sides = [context.slot_reviews(task_id, r) for r in (0, 1)]
        alignments = []
        for r in (0, 1):
            job = context.jobs[job_key("alignment", task_id, r)]
            assessment = read_json(job_directory(output, job) / "assessment/record.json")
            alignments.append(assessment.get("validation") or assessment)
        resolution = resolve_pair(prepared, *sides, *alignments)
        publish(Path(output) / "resolutions" / digest(task_id), resolution)
        encodings, failures = {}, []
        if resolution["common_kernel_material_ready"]:
            if tokenizer is None:
                binding = original_plan["assets"]["tokenizer_binding"]
                directory = (
                    binding.get("directory") or original_plan["assets"]["base_binding"]["directory"]
                )
                tokenizer = AutoTokenizer.from_pretrained(directory, local_files_only=True)
            for sid in resolution["valid_slots_retained"]:
                original = paths[sid]
                require(
                    sha(original["episode_path"]) == original["episode_file_sha256"],
                    "original episode changed",
                )
                episode = Episode.model_validate_json(Path(original["episode_path"]).read_bytes())
                encoding = encode_reviewed_probe_for_student(
                    episode, resolution["slots"][sid]["encoding_manifest"], tokenizer
                )
                publish(Path(output) / "encodings" / digest(sid), encoding)
                encodings[sid] = dict(
                    encoding_id=encoding["encoding_id"], admitted=encoding["encoding_admitted"]
                )
                if not encoding["encoding_admitted"]:
                    failures.append(sid)
        whole_task = (
            bool(encodings)
            and not failures
            and set(encodings) == set(resolution["valid_slots_retained"])
        )
        if whole_task:
            paths_count += len(encodings)
        tasks[task_id] = dict(
            resolution_schema=resolution["schema"],
            task_mapping=resolution["task_mapping"],
            jointly_qualified_count=len(resolution["valid_slots_retained"]),
            all_joint_packages_encoded=whole_task,
            encodings=encodings,
            encoding_failures=failures,
            no_hard_package_dropped=True,
        )
    return dict(
        real_end_to_end_accepted_packages=paths_count,
        tasks=tasks,
        sampled_synthetic_controls_count_as_real_paths=False,
        model_calls_added=0,
        original1000_training_admitted=False,
    )


async def run(output, env_file):
    output = Path(output)
    plan = checked_plan(output)
    require(
        not (output / "started").exists(),
        "started fixed validation requires audit, never implicit resend",
    )
    ledger = ledger_for(plan)
    before = ledger.snapshot()
    require(
        not before["halt"] and not before["unacknowledged_unknown_requests"],
        "shared wallet safety stop",
    )
    require(
        before["request_partition"]["consumed"]["technical_review"] == 0,
        "technical namespace already consumed",
    )
    controls = checked(output / "negative_controls/record.json")
    require(
        controls["id"] == plan["negative_controls_id"] and controls["passed"],
        "negative-control evidence changed",
    )
    context, key = ReviewContext(output, plan), _key(env_file)
    publish(output / "started", bound(dict(at=now(), protocol_id=plan["id"], budget=before)))
    completed, dispatched, errors = {}, set(), []
    stop = asyncio.Event()

    def progress(phase):
        status(
            output,
            dict(
                at=now(),
                protocol_id=plan["id"],
                phase=phase,
                returned=len(completed),
                dispatched=len(dispatched),
                denominator=108,
                budget=ledger.snapshot(),
                errors=errors,
                no_percentage_gate=True,
                training_started=False,
                production_review_started=False,
            ),
        )

    async with httpx.AsyncClient(
        trust_env=False,
        follow_redirects=False,
        timeout=1200,
        limits=httpx.Limits(max_connections=4, max_keepalive_connections=4),
    ) as client:

        async def stage_run(stage):
            queue = asyncio.Queue()
            for job in plan["jobs"]:
                if job["stage"] == stage:
                    queue.put_nowait(job)

            async def worker():
                while not stop.is_set():
                    try:
                        job = queue.get_nowait()
                    except asyncio.QueueEmpty:
                        return
                    directory = job_directory(output, job)
                    try:
                        request = context.request(job)
                        require(
                            job["key"] not in dispatched and len(dispatched) < 108,
                            "duplicate/unregistered validation call",
                        )
                        episode_id = "v8review:" + digest(
                            dict(protocol_id=plan["id"], job=job["key"])
                        )
                        publish(
                            directory / "started",
                            dict(at=now(), episode_id=episode_id, job_key=job["key"]),
                        )
                        dispatched.add(job["key"])
                        artifact = await request_review(
                            ledger=ledger,
                            api_key=key,
                            episode_id=episode_id,
                            request=request,
                            client=client,
                            timeout=max(180, math.ceil(90 + request["max_output_tokens"] / 128)),
                        )
                        publish(directory / "response", artifact)
                        if artifact["finish_reason"] != "tool_calls" or artifact.get(
                            "review_format_error"
                        ):
                            assessment = dict(
                                interface_admitted=False,
                                semantic_consistent=False,
                                validation=None,
                                error=artifact.get("review_format_error")
                                or "non-normal strict finish",
                                reviewer=job["reviewer"],
                                task_bundle_sha256=request["task_bundle_sha256"],
                                slot_review_bindings=request.get("slot_review_bindings"),
                                pairs=None,
                                raw_review_sha256=None,
                            )
                        else:
                            inspector = (
                                inspect_slot_review if stage == "slot" else inspect_alignment
                            )
                            assessment = inspector(artifact["review_text"], request)
                        publish(directory / "assessment", assessment)
                        completed[job["key"]] = dict(
                            stage=stage, artifact=artifact, assessment=assessment
                        )
                        # Known malformed or semantic-unknown returns do NOT stop the fixed cohort.
                    except Exception as failure:
                        error = dict(
                            job_key=job["key"],
                            error_type=type(failure).__name__,
                            retry=False,
                            settlement=getattr(failure, "settlement", None),
                            actual_model_calls=getattr(failure, "actual_model_calls", None),
                            provider_evidence=copy.deepcopy(getattr(failure, "evidence", None)),
                        )
                        publish(directory / "blocked", error)
                        errors.append(error)
                        stop.set()
                    progress("V8_" + stage.upper() + "_RUNNING")

            await asyncio.gather(*(worker() for _ in range(4)))

        await stage_run("slot")
        if len(completed) == 96 and not errors:
            try:
                for task_id in plan["task_ids"]:
                    context.prepare_alignment(task_id)
            except Exception as failure:
                errors.append(
                    dict(
                        stage="alignment_preparation",
                        error_type=type(failure).__name__,
                        retry=False,
                    )
                )
                stop.set()
            if not stop.is_set():
                await stage_run("alignment")
    paths = dict(
        real_end_to_end_accepted_packages=0, tasks={}, original1000_training_admitted=False
    )
    if len(completed) == 108 and not errors:
        try:
            paths = _end_to_end(output, plan, context)
        except Exception as failure:
            errors.append(
                dict(stage="consensus_encoding", error_type=type(failure).__name__, retry=False)
            )
    final = ledger.snapshot()
    ready = (
        len(completed) == 108
        and not errors
        and controls["passed"]
        and paths["real_end_to_end_accepted_packages"] > 0
        and not final["halt"]
        and not final["unacknowledged_unknown_requests"]
    )
    stages = {
        stage: dict(
            returned=sum(v["stage"] == stage for v in completed.values()),
            interface_passed=sum(
                v["stage"] == stage and v["assessment"]["interface_admitted"]
                for v in completed.values()
            ),
            semantic_consistent=sum(
                v["stage"] == stage and v["assessment"]["semantic_consistent"]
                for v in completed.values()
            ),
        )
        for stage in ("slot", "alignment")
    }
    result = bound(
        dict(
            schema="v8_one_full_review_validation_result.v1",
            at=now(),
            protocol_id=plan["id"],
            denominator=108,
            dispatched=len(dispatched),
            dispatched_counter_means_provider_invocations_not_http_confirmation=True,
            returned=len(completed),
            stages=stages,
            negative_controls_id=controls["id"],
            end_to_end=paths,
            review_engineering_ready=ready,
            readiness_not_a_format_percentage=True,
            errors=errors,
            budget=final,
            actual_response_hashes={k: digest(v["artifact"]) for k, v in completed.items()},
            returned_review_cost_upper_bound_microcny=sum(
                v["artifact"]["peak_tariff_upper_bound_microcny"] for v in completed.values()
            ),
            returned_review_usage={
                field: sum(v["artifact"]["usage"].get(field, 0) for v in completed.values())
                for field in ("prompt_tokens", "completion_tokens", "total_tokens")
            },
            error_costs_not_imputed_from_shared_wallet=True,
            new_calls_in_other_partitions_not_attributed_to_review=True,
            original1000_training_admitted=False,
            automatic_next_trial=False,
            automatic_production_review=False,
            training_started=False,
            all_failures_retained=True,
        )
    )
    publish(output / "result", result)
    progress("V8_VALIDATION_COMPLETE" if len(completed) == 108 else "V8_VALIDATION_STOPPED_SAFETY")
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("register", "run", "status"))
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--generation-launch", type=Path, default=GENERATION)
    parser.add_argument("--env-file", type=Path, default=ENV_FILE)
    args = parser.parse_args(argv)
    if args.action == "register":
        print(
            dict(protocol_id=register(args.output, args.generation_launch)["id"], maximum_calls=108)
        )
    elif args.action == "status":
        print(read_json(args.output / "status.json"))
    else:
        args.output.mkdir(parents=True, exist_ok=True)
        with (args.output / "controller.lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            print(asyncio.run(run(args.output, args.env_file)))


if __name__ == "__main__":
    main()
