"""Strict fixed empirical support, variable-N schedule, and the existing real trainer.

The parent remains 1000 tasks / 8000 originals. No API/GPU/model load occurs here.
This module does not infer consent, collect reviews, or accept an arbitrary subset.
"""

from __future__ import annotations

import copy
import hashlib
import json
import random
from collections import Counter
from fractions import Fraction
from pathlib import Path

from .contracts import Episode, digest
from .v8_training_driver import (
    REVIEW_POLICY_ID,
    TrainingDriver,
    VerifiedPool,
    _generation_contract,
    _require,
    _validate_encoding,
)
from .v8_training_driver import (
    conditional_sharing_proof as old_sharing_proof,
)


def _bound(body):
    return {**body, "id": digest(body)}


def _identity(record, schema):
    _require(
        record.get("schema") == schema
        and record.get("id") == digest({k: v for k, v in record.items() if k != "id"}),
        f"changed or unknown {schema}",
    )


def execution_plan(N):
    """Coordinates are derived once from actual support, never an assumed 820."""
    _require(type(N) is int and 0 < N <= 1000, "positive actual conditional task count required")
    s = (N + 4) // 5
    return _bound(
        dict(
            schema="v9_conditional_execution_plan.v1",
            N=N,
            steps_per_epoch=s,
            epochs=10,
            maximum_batch_size=5,
            tail_batch_size=N - 5 * (s - 1),
            shared_step=2 * s,
            outer_steps=[2 * s, 4 * s, 6 * s, 8 * s],
            final_step=10 * s,
            sharing_split_step=6 * s,
            mechanism_steps={"C_direction": 3 * s, "N_local": 5 * s},
            feedback_denominator=700,
            model_history_steps=150 * s,
            core_physical_steps=126 * s,
            verified_shared_core_steps=120 * s,
            reverse_mechanism_extra_steps=3 * s,
            loss_coefficient="pi(z|x)/(actual_B_j*n_xz*L_P)",
            mu=str(Fraction(1, N)),
            tail_padding=False,
            task_deletion=False,
            bitwise_equivalent_to_original_1000_schedule=False,
        )
    )


def build_task_schedule(task_ids, seed):
    tasks = list(task_ids)
    _require(
        len(set(tasks)) == len(tasks) and all(isinstance(t, str) and t for t in tasks),
        "unique nonempty task identifiers required",
    )
    _require(type(seed) is int and seed in (11, 29, 47), "paired seeds 11/29/47 only")
    plan = execution_plan(len(tasks))
    rng, batches = random.Random(seed), []
    for epoch in range(1, 11):
        permutation = list(tasks)
        rng.shuffle(permutation)
        for offset in range(0, len(tasks), 5):
            batch = permutation[offset : offset + 5]
            batches.append(
                dict(
                    step=len(batches) + 1,
                    epoch=epoch,
                    batch_index=offset // 5,
                    task_ids=batch,
                    actual_batch_size=len(batch),
                )
            )
    body = dict(
        schema="v9_conditional_task_schedule.v1",
        seed=seed,
        training_task_ids_sha256=digest(tasks),
        N=len(tasks),
        epochs=10,
        batch_size=5,
        updates=plan["final_step"],
        execution_plan_id=plan["id"],
        shuffle="local Python Random(seed); shuffle fresh original order each epoch",
        same_schedule_for_all_arms=True,
        real_tail_batches=True,
        batches=batches,
    )
    return {**body, "schedule_sha256": digest(body)}


def validate_execution_schedule(plan, schedule, task_ids, seed):
    _require(plan == execution_plan(len(task_ids)), "conditional coordinates changed")
    _require(schedule == build_task_schedule(task_ids, seed), "conditional task schedule changed")


def _protocol_roster(protocol):
    _identity(protocol, "v9_conditional_production_protocol.v1")
    _require(protocol["review_policy_id"] == REVIEW_POLICY_ID, "V8 review policy changed")
    _require(
        protocol.get("model") == "deepseek-flash", "registered API model must remain deepseek-flash"
    )
    tasks, slots = protocol["original_task_ids"], protocol["slots"]
    _require(len(tasks) == len(set(tasks)) == 1000, "parent must retain original 1000 tasks")
    _require(
        len(slots) == 8000
        and len({s["slot_id"] for s in slots}) == 8000
        and Counter(s["task_id"] for s in slots) == Counter({t: 8 for t in tasks}),
        "parent must retain original 8000 slots",
    )
    expected = {t: [s["slot_id"] for s in slots if s["task_id"] == t] for t in tasks}
    eligible = protocol["native_eligible_slot_ids"]
    _require(
        len(eligible) == len(set(eligible)) and set(eligible) <= {s["slot_id"] for s in slots},
        "native eligible roster changed",
    )
    native_tasks = [t for t in tasks if set(expected[t]) & set(eligible)]
    _require(
        protocol["native_supported_task_ids"] == native_tasks,
        "native supported task roster mismatch",
    )
    _require(
        protocol["slot_review_denominator"] == 2 * len(eligible)
        and protocol["alignment_denominator"] == 2 * len(native_tasks)
        and protocol["maximum_calls"] == 2 * (len(eligible) + len(native_tasks)),
        "complete production call matrix required",
    )
    return tasks, slots, expected, set(eligible)


def _completion(protocol, completion):
    version2 = completion.get("schema") == "v9_production_completion_seal.v2"
    _identity(
        completion,
        "v9_production_completion_seal.v2" if version2 else "v9_production_completion_seal.v1",
    )
    if version2:
        from .v9_network_terminal import TERMINAL_KIND, validate_authorization

        revision = completion["execution_revision"]
        _identity(revision, "v9_same_matrix_network_terminal_revision.v1")
        validate_authorization(revision["authorization_record"], protocol["id"])
        unknowns = sum(j.get("terminal_kind") == TERMINAL_KIND for j in completion["jobs"])
        _require(
            revision["protocol_id"] == protocol["id"]
            and revision["jobs_sha256"] == digest(protocol["jobs"])
            and completion["processed_jobs"] == protocol["maximum_calls"]
            and completion["network_unknown_jobs"] == unknowns
            and completion["completed_requests"] + unknowns == completion["processed_jobs"]
            and completion["all_registered_jobs_have_terminal_records"] is True
            and completion["all_registered_returns_present"] is (unknowns == 0),
            "explicit full-terminal closure required; actual returned count must stay truthful",
        )
    parent = protocol["parent"]
    _require(
        completion["protocol_id"] == protocol["id"]
        and completion["parent_launch_id"] == parent["generation_protocol"]["id"]
        and completion["parent_generation_seal_id"] == parent["generation_seal"]["id"]
        and completion["native_support_id"] == parent["native_support"]["id"]
        and completion["expected_requests"] == protocol["maximum_calls"]
        and (version2 or completion["completed_requests"] == protocol["maximum_calls"])
        and completion["slot_review_denominator"] == protocol["slot_review_denominator"]
        and completion["alignment_denominator"] == protocol["alignment_denominator"]
        and (version2 or completion["all_registered_returns_present"] is True)
        and completion["all_original_slots_retained"] is True,
        "all registered production returns must finish before support freeze",
    )
    _require(
        len(protocol["jobs"]) == len(completion["jobs"]) == protocol["maximum_calls"]
        and len({row["key"] for row in protocol["jobs"]}) == protocol["maximum_calls"]
        and {row["key"] for row in protocol["jobs"]} == {row["key"] for row in completion["jobs"]},
        "complete registered production job manifest required before support freeze",
    )


def build_support_manifest(protocol, completion, resolutions, encodings):
    """Pure freeze builder; strict file/receipt validation still occurs in the loader.

    Every jointly valid package must map and encode. A difficult package/task
    raises instead of being deleted from X*. Empty X* can be recorded, not trained.
    """
    tasks, slots, expected, eligible = _protocol_roster(protocol)
    _completion(protocol, completion)
    _require(set(resolutions) == set(tasks), "all original 1000 resolutions required")
    support, joint, layers = {}, set(), Counter(reason=0, tool=0, final=0)
    for task in tasks:
        resolution = resolutions[task]
        _require(
            resolution.get("schema") == "v8_common_material_resolution.v1"
            and resolution["review_policy_id"] == REVIEW_POLICY_ID
            and resolution["task_id"] == task
            and resolution["all_eight_candidates_retained"] is True
            and set(resolution["slots"]) == set(expected[task]),
            "original resolution/slot roster changed",
        )
        candidates = resolution["slots"]
        valid = [
            sid
            for sid in expected[task]
            if candidates[sid].get("q_native") is True and candidates[sid].get("v_trace") == "valid"
        ]
        _require(
            set(resolution["valid_slots_retained"]) == set(valid)
            and len(resolution["valid_slots_retained"]) == len(valid),
            "joint-valid original package dropped or duplicated",
        )
        for sid, row in candidates.items():
            _require(
                type(row.get("q_native")) is bool and row["q_native"] == (sid in eligible),
                "native eligibility changed",
            )
            if sid not in eligible:
                _require(
                    row.get("v_trace") == "not_assessed_native_ineligible",
                    "native incorrect is unassessed, not reviewed-invalid",
                )
            if sid not in valid:
                _require(
                    row.get("common_material_valid") is not True,
                    "ineligible package cannot enter common material",
                )
        if not valid:
            continue
        _require(
            resolution["task_mapping"] == "complete"
            and resolution["no_dropping_hard_to_map_valid_packages"] is True,
            "joint-valid task cannot be dropped for incomplete whole-task mapping",
        )
        counts, chi = Counter(), {}
        for sid in valid:
            row = candidates[sid]
            _require(
                row.get("mapper") == "mapped"
                and row.get("state_id")
                and type(row.get("chi")) is int
                and row["chi"] in (0, 1)
                and row.get("common_material_valid") is True
                and row.get("encoding_manifest", {}).get("mask_agreement") is True,
                "joint-valid package needs state, chi, and complete agreed mask",
            )
            state = row["state_id"]
            _require(state not in chi or chi[state] == row["chi"], "within-state chi changed")
            chi[state], counts[state] = row["chi"], counts[state] + 1
            _require(sid in encodings, "joint-valid original package is not encoded")
            encoding = encodings[sid]
            _require(
                encoding.get("schema") == "v8_student_encoding.v1"
                and encoding.get("encoding_policy") == "v8_single_authoritative_targets.v1"
                and encoding.get("encoding_admitted") is True
                and encoding.get("context_truncated") is False
                and encoding.get("context_limit") == 24576
                and not encoding.get("failures")
                and encoding.get("task_id") == task
                and type(encoding.get("L_P")) is int
                and encoding["L_P"] > 0,
                "all joint-valid packages require full admitted encoding; no length filtering",
            )
            total = 0
            for encoded_row in encoding["rows"]:
                for layer in layers:
                    count = len(encoded_row["layer_target_positions"][layer])
                    layers[layer] += count
                    total += count
            _require(
                total == encoding["L_P"] == encoding["total_supervised_tokens"],
                "supervised token count mismatch",
            )
        support[task] = dict(
            joint_valid_slot_ids=valid, states=dict(counts), chi=chi, n_x=len(valid)
        )
        joint.update(valid)
    _require(
        set(encodings) == joint, "encoding roster must include all and only joint-valid originals"
    )
    training_tasks, N = list(support), len(support)
    state_histogram = Counter(str(n) for row in support.values() for n in row["states"].values())
    flexible = sum(len(row["states"]) > 1 for row in support.values())
    mixed_chi = sum(len(set(row["chi"].values())) > 1 for row in support.values())
    dimension = sum(len(row["states"]) - 1 for row in support.values())

    def mass(number):
        return str(Fraction(number, N)) if N else "0"

    profile = _bound(
        dict(
            schema="v9_conditional_capability_profile.v1",
            N=N,
            D_pi=dimension,
            multi_state_tasks=flexible,
            M_flex=mass(flexible),
            chi_flexible_tasks=mixed_chi,
            chi_flexible_mass=mass(mixed_chi),
            one_state_tasks=N - flexible,
            singleton_package_tasks=sum(row["n_x"] == 1 for row in support.values()),
            supervised_tokens=dict(layers),
            supervised_token_layers={"reason": "R+U", "tool": "A", "final": "F"},
            separate_R_U_token_counts_available=False,
            package_count=len(joint),
            state_count=sum(len(row["states"]) for row in support.values()),
            state_package_histogram=dict(sorted(state_histogram.items())),
            nontrivial_pi=dimension > 0,
            nontrivial_manual=mixed_chi > 0,
            five_arm_algebraic_distinguishability_possible=dimension > 0 and mixed_chi > 0,
            power_established=False,
            student_results_used=False,
        )
    )
    parent = protocol["parent"]
    return _bound(
        dict(
            schema="v9_conditional_support_manifest.v1",
            production_protocol_id=protocol["id"],
            completion_seal_id=completion["id"],
            parent_launch_id=parent["generation_protocol"]["id"],
            parent_generation_seal_id=parent["generation_seal"]["id"],
            native_support_id=parent["native_support"]["id"],
            review_policy_id=REVIEW_POLICY_ID,
            original_task_ids=tasks,
            original_task_denominator=1000,
            original_slot_denominator=8000,
            all_originals_retained=True,
            all_production_candidates_processed=True,
            training_task_ids=training_tasks,
            N=N,
            mu={t: mass(1) for t in training_tasks},
            joint_valid_slot_ids=[s["slot_id"] for s in slots if s["slot_id"] in joint],
            task_support=support,
            excluded_tasks=[
                dict(task_id=t, reason="no_joint_valid_original_package")
                for t in tasks
                if t not in support
            ],
            capability_profile=profile,
            execution_plan=execution_plan(N) if N else None,
            student_results_used=False,
            no_valid_package_or_task_dropped=True,
        )
    )


def _check_production_returns(protocol, completion, read):
    """Bind the complete actual returns and validated labels, not model self-reports."""
    tasks, slots, _, eligible = _protocol_roster(protocol)
    _completion(protocol, completion)
    slot_tasks = {s["slot_id"]: s["task_id"] for s in slots}
    expected = {("slot", slot_tasks[sid], sid, r) for sid in eligible for r in (0, 1)}
    expected |= {
        ("alignment", task, None, r)
        for task in protocol["native_supported_task_ids"]
        for r in (0, 1)
    }

    def coordinate(row):
        return row["stage"], row["task_id"], row.get("slot_id"), row["reviewer"]

    registered, returned = protocol["jobs"], completion["jobs"]
    _require(
        len(registered) == len(returned) == len(expected)
        and {coordinate(j) for j in registered} == expected
        and {coordinate(j) for j in returned} == expected
        and len({j["key"] for j in registered}) == len(expected)
        and {j["key"] for j in registered} == {j["key"] for j in returned},
        "complete fixed production matrix required, not a successful prefix",
    )
    registered_by_key = {j["key"]: j for j in registered}
    labels = {}
    for job in returned:
        _require(
            coordinate(job) == coordinate(registered_by_key[job["key"]]),
            "production job identity changed",
        )
        artifact, assessment = read(job["response"]), read(job["assessment"])
        _require(
            artifact.get("semantic_review_request_sha256") == job["request_sha256"],
            "actual production response is unbound",
        )
        validation = assessment.get("validation")
        if artifact.get("terminal_kind") == "acknowledged_connection_unknown_no_model_response":
            from .v9_network_terminal import validate_terminal

            _require(
                completion["schema"] == "v9_production_completion_seal.v2",
                "old all-return completion cannot accept missing responses",
            )
            validate_terminal(
                artifact,
                protocol_id=protocol["id"],
                semantic_request_sha256=job["request_sha256"],
                revision=completion["execution_revision"],
            )
            _require(
                validation is None
                and assessment["interface_admitted"] is False
                and assessment["semantic_consistent"] is False,
                "unknown terminal cannot become a qualified original",
            )
        if validation is not None:
            request_key = (
                "review_request_sha256" if job["stage"] == "slot" else "alignment_request_sha256"
            )
            _require(
                validation.get(request_key) == job["request_sha256"]
                and validation.get("review_policy_id") == REVIEW_POLICY_ID
                and validation.get("reviewer") == job["reviewer"],
                "production assessment/request/policy mismatch",
            )
        if job["stage"] == "slot":
            if validation is not None:
                _require(
                    validation.get("task_id") == job["task_id"]
                    and validation.get("slot_id") == job["slot_id"],
                    "slot assessment changed original coordinates",
                )
            valid = (
                assessment.get("interface_admitted") is True
                and assessment.get("semantic_consistent") is True
                and validation is not None
                and validation.get("interface_admitted") is True
                and validation.get("semantic_consistent") is True
                and validation.get("v_trace") == "valid"
                and validation.get("derived") is not None
            )
            labels[job["slot_id"], job["reviewer"]] = valid
    return {sid for sid in eligible if labels[sid, 0] and labels[sid, 1]}


def load_training_pool(binding_path):
    """Verify original parent, all production returns, exact X*, and every whole package."""
    from .probe_collection import slot_directory
    from .settlement import episode_is_complete

    binding_path = Path(binding_path).resolve()
    binding = json.loads(binding_path.read_bytes())
    _require(
        binding.get("schema") == "v9_conditional_training_binding.v1"
        and binding.get("review_policy_id") == REVIEW_POLICY_ID,
        "unknown conditional binding",
    )
    cache = {}

    def location(entry):
        path = Path(entry["path"])
        return path.resolve() if path.is_absolute() else (binding_path.parent / path).resolve()

    def read(entry):
        path = location(entry)
        if path not in cache:
            raw = path.read_bytes()
            cache[path] = (hashlib.sha256(raw).hexdigest(), json.loads(raw))
        sha, value = cache[path]
        _require(sha == entry["sha256"], f"artifact byte SHA mismatch: {path}")
        if "id" in entry:
            _require(entry["id"] == value.get("id"), "artifact entry content identity mismatch")
        return value

    generation = read(binding["generation_protocol"])
    generation_root, source_manifest = _generation_contract(
        generation, location(binding["generation_protocol"]), read
    )
    seal, native, protocol, completion, support = (
        read(binding[key])
        for key in (
            "generation_seal",
            "native_support",
            "production_protocol",
            "production_completion_seal",
            "support_manifest",
        )
    )
    _identity(seal, "v8_whole_generation_seal.v1")
    _identity(native, "v8_native_full_population_support.v1")
    _require(
        location(binding["generation_seal"]) == generation_root / "generation_seal/record.json"
        and location(binding["native_support"]) == generation_root / "native_support/record.json"
        and seal["protocol_id"] == native["protocol_id"] == generation["id"]
        and native["generation_seal_id"] == seal["id"]
        and seal["denominator"] == native["slot_denominator"] == 8000
        and native["task_denominator"] == 1000
        and [r["slot"] for r in seal["slots"]] == generation["slots"]
        and [r["slot"] for r in native["rows"]] == generation["slots"]
        and all(type(r["Q_native"]) is bool for r in native["rows"]),
        "complete original generation/native scoring required",
    )
    tasks, slots, _, eligible = _protocol_roster(protocol)
    _require(
        tasks == generation["task_ids"]
        and slots == generation["slots"]
        and protocol["native_eligible_slot_ids"]
        == [r["slot"]["slot_id"] for r in native["rows"] if r["Q_native"] is True],
        "production must cover all and only existing native-correct candidates",
    )
    for key in ("generation_protocol", "generation_seal", "native_support"):
        _require(
            location(protocol["parent"][key]) == location(binding[key])
            and read(protocol["parent"][key]) == read(binding[key]),
            "conditional parent changed",
        )
    joint_from_reviews = _check_production_returns(protocol, completion, read)
    if completion["schema"] == "v9_production_completion_seal.v2":
        from .v9_network_terminal import PROTECTED

        revision = read(binding["production_execution_revision"])
        _require(
            revision == completion["execution_revision"]
            and revision["original_runtime_binding_sha256"] == digest(protocol["runtime_binding"])
            and all(
                revision["protected_sources"][name] == protocol["runtime_binding"][name]
                for name in PROTECTED
            )
            and read(revision["authorization"]) == revision["authorization_record"],
            "actual explicit terminal revision/authority/protected semantics differ",
        )
    _require(set(binding["resolutions"]) == set(tasks), "all 1000 resolutions required")
    resolutions = {task: read(entry) for task, entry in binding["resolutions"].items()}
    encodings = {sid: read(entry) for sid, entry in binding["encodings"].items()}
    _require(
        set(encodings) == joint_from_reviews,
        "all dual-validated native-correct packages must encode; no task/package filtering",
    )
    slot_tasks = {s["slot_id"]: s["task_id"] for s in slots}
    joint_by_task = {task: set() for task in tasks}
    for sid in joint_from_reviews:
        joint_by_task[slot_tasks[sid]].add(sid)
    for task, resolution in resolutions.items():
        _require(
            {
                sid
                for sid, row in resolution["slots"].items()
                if row.get("q_native") is True and row.get("v_trace") == "valid"
            }
            == joint_by_task[task],
            "resolution changed jointly valid production judgments",
        )
    _require(
        support == build_support_manifest(protocol, completion, resolutions, encodings),
        "frozen X* or capability profile differs from all completed actual material",
    )
    _require(support["N"] > 0, "empty conditional support cannot train")
    originals = {}
    for row in seal["slots"]:
        episode_path = slot_directory(generation_root, row["slot"]) / "episode/episode.json"
        _require(episode_path.resolve() == episode_path, "original episode path redirected")
        episode = Episode.model_validate(
            read(dict(path=str(episode_path), sha256=row["episode_file_sha256"]))
        )
        _require(
            row["status"] == "COMPLETE"
            and digest(episode) == row["episode_sha256"]
            and episode_is_complete(episode)
            and episode.task_id == row["slot"]["task_id"]
            and episode.config.model_dump(mode="json")
            == generation["configs_by_task"][episode.task_id]
            and episode.actual_model_calls == row["actual_model_calls"]
            and episode.stop_reason == row["stop_reason"]
            and episode.all_provider_calls_settled == row["all_provider_calls_settled"],
            "sealed original episode mismatch",
        )
        originals[row["slot"]["slot_id"]] = episode
    packages, arrays, chi = [], {}, {}
    for task in support["training_task_ids"]:
        chi[task] = support["task_support"][task]["chi"]
        for sid in support["task_support"][task]["joint_valid_slot_ids"]:
            row, encoding = resolutions[task]["slots"][sid], encodings[sid]
            _validate_encoding(
                encoding, row["encoding_manifest"], originals[sid], binding["tokenizer_binding"]
            )
            arrays[sid] = encoding["rows"]
            packages.append(
                dict(
                    package_id=sid,
                    task_id=task,
                    state_id=row["state_id"],
                    whole_package_target_tokens=encoding["L_P"],
                    fused=False,
                )
            )
    pool = VerifiedPool(
        support["training_task_ids"],
        packages,
        arrays,
        binding_id=digest(binding),
        chi=chi,
        production=True,
    )
    pool.tokenizer_binding = tuple(binding["tokenizer_binding"])
    pool.source_manifest_sha256 = digest(source_manifest)
    pool.generation_launch_id = generation["id"]
    pool.original_material_protocol_id = generation["original_protocol_id"]
    pool.verified_file_count = len(cache)
    pool.conditional_scope_verified = True
    pool.execution_plan = support["execution_plan"]
    pool.support_manifest, pool.capability_profile = support, support["capability_profile"]
    return pool


class ConditionalTrainingDriver(TrainingDriver):
    """The actual V8 optimizer/Adam/700-feedback chain, with verified V9 coordinates."""

    def __init__(self, model, optimizer, pool, **kwargs):
        seed = kwargs["seed"]
        schedule = build_task_schedule(pool.task_ids, seed)
        if pool.production_verified:
            _require(
                getattr(pool, "conditional_scope_verified", False),
                "strict conditional parent/support loader required",
            )
        else:
            _require(str(kwargs.get("device", "cpu")) == "cpu", "test-only pool cannot launch CUDA")
            kwargs["cpu_control_schedule"] = schedule
        _require(
            "execution_plan" not in kwargs and "task_schedule" not in kwargs,
            "derived conditional coordinates cannot be caller-overridden",
        )
        super().__init__(
            model,
            optimizer,
            pool,
            execution_plan=execution_plan(len(pool.task_ids)),
            task_schedule=schedule,
            **kwargs,
        )


def conditional_sharing_proof(left, right, *, N):
    """Dynamic first outer point, with the unchanged full-state/feedback proof."""
    return old_sharing_proof(left, right, shared_step=execution_plan(N)["shared_step"])


def tiny_cpu_pool(task_ids, packages, rows, *, chi):
    """Explicit synthetic controls including N<5; never production authorization."""
    execution_plan(len(task_ids))
    return VerifiedPool(
        task_ids,
        copy.deepcopy(packages),
        copy.deepcopy(rows),
        binding_id="v9_tiny_cpu:" + digest(packages),
        chi=chi,
        production=False,
    )
