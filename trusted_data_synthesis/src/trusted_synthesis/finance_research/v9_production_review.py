"""One conditional-domain production cohort on the sealed V8 stock.

No new generation, semantic rule revision, old technical-success splicing, or
prefix training. Paid dispatch needs both explicit scope and funding decisions.
The original full-1000 stop and V8 review policy remain unchanged.
"""

from __future__ import annotations

import argparse
import asyncio
import fcntl
import math
import subprocess
from pathlib import Path

import httpx

from .calibration import ROOT, now, publish, status
from .contracts import Episode, digest
from .probe_budget import read_budget_snapshot
from .semantic_review import document_index
from .storage import read_json, runtime_binding
from .v6_collection import ENV_FILE, STUDY, bound, require, sha
from .v6_decomposed_review import bind_capacity, job_directory, job_key
from .v6_review_provider import request_review
from .v6_review_revision import _key, original_protocol
from .v8_collection import ledger_for
from .v8_review_policy import REVIEW_WIRE, policy_definition
from .v8_single_target_review import (
    alignment_request,
    encode_reviewed_probe_for_student,
    inspect_alignment,
    inspect_slot_review,
    resolve_pair,
    slot_review_record,
)

OUTPUT = STUDY / "conditional_five_arm_v9_01"
PARENT = STUDY / "new_full_probe_v8_launch_01"
AUDIT = Path(
    "/home/zhuxinrui/.codex/attachments/3779ccde-f592-4535-b67e-8e7f27d27388/已粘贴的文本.txt"
)
EXPECTED_AUDIT_SHA = "6345f5f4c31f4ba09a87e07077f775850dcfc1fdbfe02f66942b5a560b3f32cc"
MAXIMUM_CALLS, SLOT_CALLS, ALIGNMENT_CALLS = 13022, 11382, 1640


def checked(path):
    value = read_json(path)
    require(value["id"] == digest({k: v for k, v in value.items() if k != "id"}), "record changed")
    return value


def entry(path):
    path = Path(path).resolve()
    value = checked(path)
    return dict(path=str(path), sha256=sha(path), id=value["id"])


def read_entry(item):
    require(sha(item["path"]) == item["sha256"], "bound artifact bytes changed")
    value = checked(item["path"])
    require(value["id"] == item["id"], "bound artifact content identity changed")
    return value


def scope_authorization(output=OUTPUT):
    """Record the user's actual explicit reply; not an approval of more money."""
    require(sha(AUDIT) == EXPECTED_AUDIT_SHA, "audit attachment changed")
    value = bound(
        dict(
            schema="v9_conditional_scope_authorization.v1",
            at=now(),
            user_reply="确认采用条件性五臂修订",
            audit=dict(path=str(AUDIT), sha256=sha(AUDIT)),
            original_population_remains_failed=True,
            original_tasks=1000,
            original_slots=8000,
            conditional_population=(
                "all tasks with at least one original package P: "
                "Q(P)=true AND V0(P)=V1(P)=effective valid"
            ),
            one_package_reviewed_twice_not_two_packages_required=True,
            clarifies_initial_authorization_id="fffbc76efc84cae60d3abc5ced5a67f0439349ae1e66b2734290d6dd73f0d948",
            N=None,
            mu="1/N after one complete qualification pass",
            no_generation=True,
            no_old_stock_splicing=True,
            no_new_technical_cohort=True,
            semantics_policy_id=policy_definition()["id"],
            monetary_cap_changed=False,
            full_qualification_before_training=True,
            all_joint_originals_required=True,
            training_or_GPU_start_authorized_by_this_record_alone=False,
        )
    )
    publish(Path(output) / "scope_authorization_v2", value)
    return value


def fixed_scope(plan):
    tasks, slots, jobs = plan["original_task_ids"], plan["slots"], plan["jobs"]
    eligible = set(plan["native_eligible_slot_ids"])
    supported = plan["native_supported_task_ids"]
    require(len(tasks) == len(set(tasks)) == 1000 and len(slots) == 8000, "original cover changed")
    require(
        len({s["slot_id"] for s in slots}) == 8000 and len(eligible) == 5691,
        "native roster changed",
    )
    require(len(supported) == len(set(supported)) == 820, "native support is not training N")
    require(
        len(jobs) == len({j["key"] for j in jobs}) == MAXIMUM_CALLS,
        "exact complete matrix required",
    )
    actual_slot = {
        (j["task_id"], j["slot_id"], j["reviewer"]) for j in jobs if j["stage"] == "slot"
    }
    expected_slot = {
        (s["task_id"], s["slot_id"], r) for s in slots if s["slot_id"] in eligible for r in (0, 1)
    }
    actual_align = {(j["task_id"], j["reviewer"]) for j in jobs if j["stage"] == "alignment"}
    require(
        actual_slot == expected_slot and len(actual_slot) == SLOT_CALLS,
        "all native true need both new reviews",
    )
    require(
        actual_align == {(t, r) for t in supported for r in (0, 1)}
        and len(actual_align) == ALIGNMENT_CALLS,
        "all supported own-side alignments required",
    )
    require(
        plan["maximum_calls"] == MAXIMUM_CALLS
        and plan["review_policy_id"] == policy_definition()["id"],
        "policy/call limit changed",
    )


def register(output=OUTPUT, *, funding_path):
    from .v9_review_preflight import load_task_input, task_input_path

    output = Path(output)
    require(not (output / "registration").exists(), "immutable production registration exists")
    scope = entry(output / "scope_authorization_v2/record.json")
    require(
        read_entry(scope)["user_reply"] == "确认采用条件性五臂修订",
        "explicit conditional scope required",
    )
    funding = entry(funding_path)
    decision = read_entry(funding)
    require(
        decision["schema"] == "v9_production_funding_decision.v1"
        and decision["explicit_user_authorization"]
        and decision["strategy"] in {"bounded_full_cohort_attempt", "full_envelope_funded"}
        and decision["no_prefix_training"] is True,
        "explicit funding/risk arrangement required before paid registration",
    )
    preflight = entry(output / "preflight/report/record.json")
    require(
        decision["preflight_id"] == preflight["id"], "funding must refer to actual full preflight"
    )
    measured = read_entry(preflight)
    parent = {
        name: entry(PARENT / relative)
        for name, relative in (
            ("generation_protocol", "registration/protocol.json"),
            ("generation_seal", "generation_seal/record.json"),
            ("native_support", "native_support/record.json"),
        )
    }
    generation, native = (
        read_entry(parent["generation_protocol"]),
        read_entry(parent["native_support"]),
    )
    require(native["native_unknown_slots"] == 0, "unknown native outcomes cannot be zero")
    eligible = [r["slot"]["slot_id"] for r in native["rows"] if r["Q_native"] is True]
    supported = [
        t for t in generation["task_ids"] if native["support_by_task"][t]["native_correct"] > 0
    ]
    jobs, inputs = [], {}
    for task in generation["task_ids"]:
        payload = load_task_input(output, task)
        inputs[task] = entry(task_input_path(output, task))
        expected_input = measured["task_inputs"][task]
        require(
            all(inputs[task][k] == expected_input[k] for k in ("path", "id", "sha256")),
            "preflight task input differs from dispatched scope",
        )
        jobs.extend(payload["jobs"])
        if task in supported:
            for reviewer in (0, 1):
                jobs.append(
                    dict(
                        key=job_key("alignment", task, reviewer),
                        stage="alignment",
                        task_id=task,
                        slot_id=None,
                        reviewer=reviewer,
                        capacity=payload["alignment_capacity"],
                    )
                )
    order = {task: i for i, task in enumerate(generation["task_ids"])}
    jobs.sort(
        key=lambda j: (
            0 if j["stage"] == "slot" else 1,
            j.get("slot_index", 0),
            order[j["task_id"]],
            j["reviewer"],
        )
    )
    wallet = read_budget_snapshot(generation["budget_database"])
    b = wallet["snapshot"]
    require(
        not b["pending_requests"] and not b["halt"] and not b["unacknowledged_unknown_requests"],
        "shared wallet not settled/usable",
    )
    require(
        b.get("effective_hard_cap_microcny", b["hard_cap_microcny"])
        == decision["hard_cap_microcny"]
        and wallet["config_sha256"] == decision["budget_config_sha256"],
        "funding and actual wallet differ",
    )
    if decision["strategy"] == "full_envelope_funded":
        require(
            measured["complete"]["guaranteed_tariff_upper_bound_microcny"]
            <= b["remaining_exposure_microcny"],
            "cannot claim guaranteed affordability from an expected cost",
        )
    else:
        require(
            decision.get("risk_of_incomplete_cohort_accepted") is True,
            "explicit incomplete-cohort financial risk arrangement required",
        )
    require(
        b["request_partition"]["consumed"]["production_review"] == 0,
        "production partition already used",
    )
    require(
        b["request_partition"]["limits"]["production_review"] >= MAXIMUM_CALLS,
        "request budget insufficient",
    )
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    for path in Path(__file__).parent.rglob("*.py"):
        require(
            path.read_bytes()
            == subprocess.check_output(
                ["git", "show", commit + ":" + str(path.relative_to(ROOT))], cwd=ROOT
            ),
            "freeze source before registration",
        )
    body = dict(
        schema="v9_conditional_production_protocol.v1",
        at=now(),
        source_commit=commit,
        runtime_binding=runtime_binding(),
        authorization=scope,
        funding=funding,
        preflight=preflight,
        parent=parent,
        parent_launch_id=generation["id"],
        review_policy_id=policy_definition()["id"],
        review_policy=generation["review_policy"],
        original_task_ids=generation["task_ids"],
        slots=generation["slots"],
        native_eligible_slot_ids=eligible,
        native_supported_task_ids=supported,
        slot_review_denominator=SLOT_CALLS,
        alignment_denominator=ALIGNMENT_CALLS,
        maximum_calls=MAXIMUM_CALLS,
        jobs=jobs,
        task_inputs=inputs,
        model="deepseek-flash",
        concurrency=32,
        retry_count=0,
        namespace="v8prod:",
        budget_database=generation["budget_database"],
        budget_config=wallet["config"],
        budget_config_sha256=wallet["config_sha256"],
        partition_id=generation["partition_id"],
        original_full1000_policy_and_failure_unchanged=True,
        conditional_N_unknown_before_qualification=True,
        student_assets=original_protocol()["assets"],
        no_generation=True,
        no_prefix_training=True,
        no_success_splicing=True,
        all_joint_packages_required=True,
        fixed_V8_semantics=True,
        automatic_training=False,
        automatic_new_trial=False,
        GPU_reservation=False,
    )
    fixed_scope(body)
    plan = bound(body)
    publish(output / "registration", plan, "protocol.json")
    return plan


def checked_plan(output):
    plan = checked(Path(output) / "registration/protocol.json")
    fixed_scope(plan)
    require(plan["runtime_binding"] == runtime_binding(), "frozen production source changed")
    for name in ("authorization", "funding", "preflight"):
        read_entry(plan[name])
    require(
        read_entry(plan["review_policy"])["definition"] == policy_definition(),
        "V8 semantics changed",
    )
    return plan


def native_ineligible_placeholder(prepared, sid, reviewer):
    """Inert internal resolver adapter, explicitly NOT an actual model judgment.

    Legacy alignment consumes a three-valued field; unknown here means no claim,
    not a paid review failure. Persisted final inventory uses the explicit
    not_assessed_native_ineligible status. A Q=true slot can never take this path.
    """
    require(
        prepared["mechanical"][sid]["native_correct"] is False, "cannot skip native-eligible review"
    )
    return dict(
        schema="v9_native_ineligible_placeholder.v1",
        wire_protocol=REVIEW_WIRE,
        review_policy_id=policy_definition()["id"],
        task_id=prepared["bundle"]["task_id"],
        task_bundle_sha256=digest(prepared["bundle"]),
        slot_id=sid,
        reviewer=reviewer,
        v_trace="unknown",
        reported_v_trace=None,
        interface_admitted=None,
        semantic_consistent=None,
        parsed=None,
        derived=None,
        raw_review_sha256=None,
        not_a_model_judgment=True,
        model_calls=0,
        native_correct=False,
        public_inventory_status="not_assessed_native_ineligible",
        document_index=document_index(prepared["bundle"]),
    )


class ProductionContext:
    def __init__(self, output, plan):
        self.output, self.plan = Path(output), plan
        self.jobs = {j["key"]: j for j in plan["jobs"]}
        self.cache = {}

    def task(self, task_id):
        # Bound per-task artifacts; keep a small cache, never all 11382 requests.
        if task_id not in self.cache:
            if len(self.cache) >= 40:
                self.cache.pop(next(iter(self.cache)))
            self.cache[task_id] = read_entry(self.plan["task_inputs"][task_id])
        return self.cache[task_id]

    def request(self, job):
        if job["stage"] == "slot":
            request = self.task(job["task_id"])["requests"][job["key"]]
            require(digest(request) == job["request_sha256"], "registered slot request changed")
            return request
        saved = checked(job_directory(self.output, job) / "request/record.json")
        require(
            saved["protocol_id"] == self.plan["id"] and saved["job_key"] == job["key"],
            "alignment request changed",
        )
        return saved["request"]

    def side(self, task_id, reviewer):
        payload = self.task(task_id)
        prepared = payload["prepared"]
        values = {}
        for slot in prepared["bundle"]["slots"]:
            sid = slot["slot_id"]
            if prepared["mechanical"][sid]["native_correct"] is False:
                values[sid] = native_ineligible_placeholder(prepared, sid, reviewer)
            else:
                job = self.jobs[job_key("slot", task_id, reviewer, sid)]
                artifact = read_json(job_directory(self.output, job) / "response/record.json")
                values[sid] = slot_review_record(self.request(job), artifact)
        return values

    def prepare_alignment(self, task_id):
        payload = self.task(task_id)
        for reviewer in (0, 1):
            job = self.jobs[job_key("alignment", task_id, reviewer)]
            side = self.side(task_id, reviewer)
            request = alignment_request(payload["prepared"], side, reviewer)
            cap = job["capacity"]
            actual = bind_capacity(
                request,
                generation_tokens=cap["generation_tokens"],
                fragments=cap["target_fragments"],
                actions=cap["actions"],
                alignment=True,
            )
            require(actual == cap, "no after-results output-cap change")
            publish(
                job_directory(self.output, job) / "request",
                bound(
                    dict(
                        protocol_id=self.plan["id"],
                        job_key=job["key"],
                        slot_review_bindings={sid: digest(r) for sid, r in side.items()},
                        request=request,
                    )
                ),
            )


def _assessment(artifact, request, job):
    if artifact["finish_reason"] == "tool_calls" and not artifact.get("review_format_error"):
        return (inspect_slot_review if job["stage"] == "slot" else inspect_alignment)(
            artifact["review_text"], request
        )
    return dict(
        interface_admitted=False,
        semantic_consistent=False,
        validation=None,
        error=artifact.get("review_format_error") or "non-normal strict finish",
        reviewer=job["reviewer"],
        task_bundle_sha256=request["task_bundle_sha256"],
        slot_review_bindings=request.get("slot_review_bindings"),
        pairs=None,
        raw_review_sha256=None,
    )


def complete_seal(output, plan):
    """Whole-cohort barrier includes actual malformed/invalid returns, not missing calls."""
    rows = []
    for job in plan["jobs"]:
        directory = job_directory(output, job)
        response, assessment = (
            directory / "response/record.json",
            directory / "assessment/record.json",
        )
        require(response.is_file() and assessment.is_file(), "all13022 returned originals required")
        artifact = read_json(response)
        rows.append(
            {k: job.get(k) for k in ("key", "stage", "task_id", "slot_id", "reviewer")}
            | dict(
                request_sha256=artifact["semantic_review_request_sha256"],
                response=dict(path=str(response), sha256=sha(response)),
                assessment=dict(path=str(assessment), sha256=sha(assessment)),
            )
        )
    seal = bound(
        dict(
            schema="v9_production_completion_seal.v1",
            protocol_id=plan["id"],
            parent_launch_id=plan["parent_launch_id"],
            parent_generation_seal_id=plan["parent"]["generation_seal"]["id"],
            native_support_id=plan["parent"]["native_support"]["id"],
            expected_requests=MAXIMUM_CALLS,
            completed_requests=len(rows),
            slot_review_denominator=SLOT_CALLS,
            alignment_denominator=ALIGNMENT_CALLS,
            all_registered_returns_present=True,
            all_original_slots_retained=True,
            jobs=rows,
            semantic_failures_retained=True,
            no_prefix_population=True,
        )
    )
    publish(Path(output) / "production_completion_seal", seal)
    return seal


def freeze_material(output, plan, seal):
    from .v7_base_evaluation import load_tokenizer
    from .v9_conditional_training import build_support_manifest

    output = Path(output)
    context, tokenizer = ProductionContext(output, plan), None
    resolutions, encodings, paths, failures = {}, {}, {}, []
    for task_id in plan["original_task_ids"]:
        payload = context.task(task_id)
        sides = [context.side(task_id, r) for r in (0, 1)]
        alignments = [None, None]
        if task_id in plan["native_supported_task_ids"]:
            for r in (0, 1):
                job = context.jobs[job_key("alignment", task_id, r)]
                record = read_json(job_directory(output, job) / "assessment/record.json")
                alignments[r] = record.get("validation") or record
        resolution = resolve_pair(payload["prepared"], *sides, *alignments)
        for row in resolution["slots"].values():
            if row["q_native"] is False:
                row.update(
                    v_trace="not_assessed_native_ineligible",
                    per_reviewer_v_trace=["not_assessed_native_ineligible"] * 2,
                    process_review_model_calls=0,
                )
        resolution = bound(
            resolution | dict(production_protocol_id=plan["id"], no_old_technical_packages=True)
        )
        publish(output / "resolutions" / digest(task_id), resolution)
        resolutions[task_id] = resolution
        paths[task_id] = entry(output / "resolutions" / digest(task_id) / "record.json")
        # Do not drop a joint-valid package merely because the whole task is unmapped.
        for sid in resolution["valid_slots_retained"]:
            mask = resolution["slots"][sid]["encoding_manifest"]
            if resolution["task_mapping"] != "complete" or mask is None:
                failures.append(
                    dict(
                        task_id=task_id,
                        slot_id=sid,
                        reason="joint_valid_mapping_or_mask_incomplete",
                    )
                )
                continue
            if tokenizer is None:
                tokenizer = load_tokenizer(plan["student_assets"])
            ep = payload["episodes"][sid]
            require(sha(ep["path"]) == ep["sha256"], "original episode changed before encoding")
            episode = Episode.model_validate_json(Path(ep["path"]).read_bytes())
            encoding = encode_reviewed_probe_for_student(episode, mask, tokenizer)
            publish(output / "encodings" / digest(sid), encoding)
            encodings[sid] = encoding
            if not encoding["encoding_admitted"]:
                failures.append(
                    dict(task_id=task_id, slot_id=sid, reason="full_history_encoding_failed")
                )
    eligible_count = sum(len(r["valid_slots_retained"]) for r in resolutions.values())
    support = None
    if not failures:
        try:
            support = build_support_manifest(plan, seal, resolutions, encodings)
            publish(output / "support_manifest", support)
        except ValueError as failure:
            failures.append(dict(reason="support_freeze_refused", detail=str(failure)))
    binding = None
    if support is not None and support["N"] > 0:
        codec = {(e["tokenizer_digest"], e["chat_template_digest"]) for e in encodings.values()}
        require(len(codec) == 1, "same actual tokenizer/template required")
        binding = bound(
            dict(
                schema="v9_conditional_training_binding.v1",
                review_policy_id=plan["review_policy_id"],
                **plan["parent"],
                production_protocol=entry(output / "registration/protocol.json"),
                production_completion_seal=entry(output / "production_completion_seal/record.json"),
                support_manifest=entry(output / "support_manifest/record.json"),
                resolutions=paths,
                encodings={
                    sid: dict(
                        path=str(output / "encodings" / digest(sid) / "record.json"),
                        sha256=sha(output / "encodings" / digest(sid) / "record.json"),
                    )
                    for sid in encodings
                },
                tokenizer_binding=list(next(iter(codec))),
            )
        )
        publish(output / "training_binding", binding)
    report = bound(
        dict(
            schema="v9_conditional_material_result.v1",
            at=now(),
            protocol_id=plan["id"],
            completion_seal_id=seal["id"],
            candidate_tasks=1000,
            candidate_slots=8000,
            native_eligible_slots=5691,
            joint_valid_package_count=eligible_count,
            joint_supported_task_count=sum(
                bool(r["valid_slots_retained"]) for r in resolutions.values()
            ),
            support_manifest_id=support["id"] if support else None,
            N_frozen=support["N"] if support else None,
            binding_id=binding["id"] if binding else None,
            failures=failures,
            all_joint_originals_retained=True,
            no_mapping_or_length_selection=True,
            material_frozen=support is not None,
            training_started=False,
            capability_and_pre_student_scale_decision_still_required=True,
        )
    )
    publish(output / "material_result", report)
    return report


async def run(output=OUTPUT, env_file=ENV_FILE):
    output = Path(output)
    plan = checked_plan(output)
    require(
        not (output / "started").exists(),
        "started cohort requires explicit recovery audit, never implicit resend",
    )
    ledger, context = ledger_for(plan), ProductionContext(output, plan)
    before = ledger.snapshot()
    require(
        not before["halt"] and not before["unacknowledged_unknown_requests"],
        "original shared wallet safety stop",
    )
    require(
        before["request_partition"]["consumed"]["production_review"] == 0,
        "new cohort cannot splice previous production attempts",
    )
    completed, dispatched, errors, totals = (
        {},
        set(),
        [],
        dict(cost_microcny=0, prompt_tokens=0, completion_tokens=0),
    )
    stop = asyncio.Event()
    key = _key(env_file)
    publish(output / "started", bound(dict(at=now(), protocol_id=plan["id"], budget=before)))

    def progress(phase):
        status(
            output,
            dict(
                at=now(),
                protocol_id=plan["id"],
                phase=phase,
                returned=len(completed),
                dispatched=len(dispatched),
                dispatched_counter_means_provider_invocations_not_http_confirmation=True,
                denominator=MAXIMUM_CALLS,
                errors=errors,
                budget=ledger.snapshot(),
                no_prefix_training=True,
                training_started=False,
                automatic_next_cohort=False,
            ),
        )

    progress("PRODUCTION_REVIEW_RUNNING")
    async with httpx.AsyncClient(
        follow_redirects=False,
        timeout=1200,
        limits=httpx.Limits(
            max_connections=plan["concurrency"], max_keepalive_connections=plan["concurrency"]
        ),
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
                        require(request["model"] == "deepseek-flash", "no model fallback")
                        require(
                            job["key"] not in dispatched and len(dispatched) < MAXIMUM_CALLS,
                            "duplicate/unregistered job",
                        )
                        episode_id = "v8prod:" + digest(
                            dict(protocol_id=plan["id"], job_key=job["key"])
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
                        assessment = _assessment(artifact, request, job)
                        publish(directory / "assessment", assessment)
                        completed[job["key"]] = dict(
                            stage=stage,
                            interface=assessment["interface_admitted"],
                            semantic=assessment["semantic_consistent"],
                        )
                        totals["cost_microcny"] += artifact["peak_tariff_upper_bound_microcny"]
                        totals["prompt_tokens"] += artifact["usage"]["prompt_tokens"]
                        totals["completion_tokens"] += artifact["usage"]["completion_tokens"]
                    except Exception as failure:
                        issue = dict(
                            job_key=job["key"],
                            error_type=type(failure).__name__,
                            error=str(failure),
                            retry=False,
                            completed_model_return=(directory / "response").exists(),
                        )
                        publish(directory / "blocked", issue)
                        errors.append(issue)
                        stop.set()
                    progress("PRODUCTION_" + stage.upper() + "_RUNNING")

            await asyncio.gather(*(worker() for _ in range(plan["concurrency"])))

        await stage_run("slot")
        if len(completed) == SLOT_CALLS and not errors:
            try:
                for task in plan["native_supported_task_ids"]:
                    context.prepare_alignment(task)
            except Exception as failure:
                errors.append(
                    dict(
                        stage="alignment_preparation",
                        error_type=type(failure).__name__,
                        error=str(failure),
                        retry=False,
                    )
                )
                stop.set()
            if not stop.is_set():
                await stage_run("alignment")
    seal = material = None
    if len(completed) == MAXIMUM_CALLS and not errors:
        try:
            seal = complete_seal(output, plan)
            progress("ALL_REVIEWS_RETURNED_FREEZING_MATERIAL")
            material = freeze_material(output, plan, seal)
        except Exception as failure:
            errors.append(
                dict(
                    stage="material_freeze",
                    error_type=type(failure).__name__,
                    error=str(failure),
                    retry=False,
                )
            )
    result = bound(
        dict(
            schema="v9_conditional_production_result.v1",
            at=now(),
            protocol_id=plan["id"],
            returned=len(completed),
            dispatched=len(dispatched),
            dispatched_counter_means_provider_invocations_not_http_confirmation=True,
            denominator=MAXIMUM_CALLS,
            stages={
                stage: dict(
                    returned=sum(v["stage"] == stage for v in completed.values()),
                    interface_passed=sum(
                        v["stage"] == stage and v["interface"] for v in completed.values()
                    ),
                    semantic_consistent=sum(
                        v["stage"] == stage and v["semantic"] for v in completed.values()
                    ),
                )
                for stage in ("slot", "alignment")
            },
            returned_cost_and_usage=totals,
            errors=errors,
            completion_seal_id=seal["id"] if seal else None,
            material_result_id=material["id"] if material else None,
            budget=ledger.snapshot(),
            all_original_failures_retained=True,
            no_prefix_training=True,
            training_started=False,
            automatic_next_cohort=False,
        )
    )
    publish(output / "result", result)
    progress("PRODUCTION_COMPLETE" if seal and not errors else "PRODUCTION_STOPPED_INCOMPLETE")
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("authorize-scope", "register", "run", "status"))
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--funding", type=Path)
    parser.add_argument("--env-file", type=Path, default=ENV_FILE)
    args = parser.parse_args(argv)
    if args.action == "authorize-scope":
        print(scope_authorization(args.output)["id"])
    elif args.action == "register":
        require(args.funding is not None, "funding decision file required")
        print(register(args.output, funding_path=args.funding)["id"])
    elif args.action == "status":
        print(read_json(args.output / "status.json"))
    else:
        with (args.output / "controller.lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            print(asyncio.run(run(args.output, args.env_file)))


if __name__ == "__main__":
    main()
