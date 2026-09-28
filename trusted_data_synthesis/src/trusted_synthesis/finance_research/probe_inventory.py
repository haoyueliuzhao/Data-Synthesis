"""Fixed Probe slots and post-collection support freeze, not a semantic certifier.

This module never calls a model, reads private answers, ranks packages, or runs
training. Qualification/Mapper decisions come from separately frozen rules.
All 1,000 original candidates remain visible. A smaller active roster requires a
separately authorized, pre-generation conditional scope with exclusion evidence;
zero-support tasks can never be dropped from that registered active population.
"""

from __future__ import annotations

import copy
from collections import Counter, defaultdict
from fractions import Fraction

from .contracts import Episode, RunConfig, digest
from .materials import MaterialRegistration, QualificationDecision
from .settlement import episode_is_complete

TASKS, SLOTS_PER_TASK, TRAIN_SLOTS = 1000, 8, 6


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _validated_scope(
    scope, *, tasks, source_manifest_sha256, qualification_rule_id, mapper_rule_id
):
    from .probe_scope import validate_conditional_scope

    scope = validate_conditional_scope(
        scope, qualification_rule_id=qualification_rule_id, mapper_rule_id=mapper_rule_id
    )
    _require(list(tasks) == scope["task_ids"], "conditional task roster/order differs from scope")
    _require(
        scope["source_manifest_sha256"] == source_manifest_sha256,
        "conditional scope source manifest differs from inventory",
    )
    _require(
        len(scope["original_task_ids"]) == TASKS and 0 < len(tasks) <= TASKS,
        "conditional scope must preserve the original 1,000 and a nonempty active roster",
    )
    return copy.deepcopy(scope)


def _checked_registration(registration):
    if isinstance(registration, InventoryIndex):
        return registration._registration
    value = copy.deepcopy(registration)
    _require(
        value.get("inventory_id")
        == "finqa_probe_inventory:"
        + digest({key: item for key, item in value.items() if key != "inventory_id"}),
        "inventory registration content identity mismatch",
    )
    conditional = value.get("conditional_scope")
    count = TASKS
    if conditional is not None:
        conditional = _validated_scope(
            conditional,
            tasks=value["task_ids"],
            source_manifest_sha256=value["source_manifest_sha256"],
            qualification_rule_id=value["qualification_rule_id"],
            mapper_rule_id=value["mapper_rule_id"],
        )
        count = len(conditional["task_ids"])
        _require(
            value.get("scope_id") == conditional["scope_id"]
            and value.get("original_candidate_count") == TASKS
            and value.get("original_task_ids") == conditional["original_task_ids"],
            "conditional inventory lost its original population binding",
        )
    _require(
        value["candidate_task_count"] == len(value["task_ids"]) == count,
        "fixed registered task inventory denominator changed",
    )
    _require(
        len(set(value["task_ids"])) == count
        and len(value["slots"]) == value["registered_slot_denominator"] == count * SLOTS_PER_TASK,
        "duplicate tasks or changed registered slot denominator",
    )
    expected = [
        (task, index, "train" if index < TRAIN_SLOTS else "sealed_diagnostic")
        for task in value["task_ids"]
        for index in range(SLOTS_PER_TASK)
    ]
    _require(
        [(row["task_id"], row["slot_index"], row["purpose"]) for row in value["slots"]] == expected,
        "fixed slot order or purpose changed",
    )
    _require(
        len({row["slot_id"] for row in value["slots"]}) == len(expected),
        "duplicate registered slot identity",
    )
    return value


class InventoryIndex:
    """Validate the fixed roster once, then bind results without O(N²) hashing."""

    def __init__(self, registration):
        self._registration = copy.deepcopy(_checked_registration(registration))
        self._slots = {row["slot_id"]: row for row in self._registration["slots"]}


def register_inventory(
    *,
    task_ids,
    source_manifest_sha256,
    qualification_rule_id,
    mapper_rule_id,
    collection_policy_id,
    slot_config,
    conditional_scope=None,
):
    """Register rules and slots first; no behavior-state support is assumed here.

    task_ids are original PublicTask.task_id values, without a dataset prefix.
    All slot configs are identical; slot identity does not pretend the API exposes
    a seed-equivalent local sampler. The real returned API response is retained.
    """
    tasks = tuple(task_ids)
    _require(
        len(tasks) == len(set(tasks)) and all(isinstance(t, str) and t for t in tasks),
        "register distinct original SFT task IDs",
    )
    conditional = None
    if conditional_scope is None:
        _require(len(tasks) == TASKS, "register exactly 1,000 distinct original SFT task IDs")
    else:
        conditional = _validated_scope(
            conditional_scope,
            tasks=tasks,
            source_manifest_sha256=source_manifest_sha256,
            qualification_rule_id=qualification_rule_id,
            mapper_rule_id=mapper_rule_id,
        )
    count = len(tasks)
    _require(
        isinstance(source_manifest_sha256, str) and len(source_manifest_sha256) == 64,
        "bind the admitted original-split source manifest",
    )
    _require(
        all(
            isinstance(value, str) and value
            for value in (qualification_rule_id, mapper_rule_id, collection_policy_id)
        ),
        "qualification, Mapper and collection policy must be frozen first",
    )
    config = (
        slot_config.model_dump(mode="json")
        if isinstance(slot_config, RunConfig)
        else copy.deepcopy(slot_config)
    )
    config = RunConfig.model_validate(config).model_dump(mode="json")
    _require(
        config["role"] == "sft"
        and config["tier"] == "EVAL_NATIVE"
        and config["api_model"] == "deepseek-flash"
        and (config["harness_id"], config["submission_profile"])
        in {
            ("bigfinance-derived-vtdo-v3", "finqa_program_v2"),
            ("bigfinance-derived-vtdo-v4", "finqa_program_v3_structured"),
        }
        and config["local_tool_protocol"] == "qwen2.5-native-tool-call-v1"
        and config["max_steps"] == 32
        and config["max_new_tokens"] == 2048
        and config["context_limit"] == 1048576
        and (config["temperature"], config["top_p"], config["top_k"]) == (1.0, 1.0, 0),
        "inventory requires a registered H1-R/profile pair, SFT role and deepseek-flash",
    )
    body = dict(
        schema="finance_research.fixed_probe_inventory.v1",
        dataset="finqa",
        task_ids=list(tasks),
        candidate_task_count=count,
        source_manifest_sha256=source_manifest_sha256,
        qualification_rule_id=qualification_rule_id,
        mapper_rule_id=mapper_rule_id,
        collection_policy_id=collection_policy_id,
        slot_config=config,
        slots_per_task=SLOTS_PER_TASK,
        train_slots_per_task=TRAIN_SLOTS,
        sealed_slots_per_task=SLOTS_PER_TASK - TRAIN_SLOTS,
        registered_slot_denominator=count * SLOTS_PER_TASK,
        all_slots_before_qualification_and_support_freeze=True,
        task_deletion_or_mass_renormalization=False,
        automatic_topups=False,
        prior_state_support_assumed=False,
        selection_by_NLL_length_style_rarity_or_student=False,
        sealed_slots_may_enter_training=False,
    )
    if conditional is not None:
        body.update(
            schema="finance_research.conditional_probe_inventory.v1",
            scope_id=conditional["scope_id"],
            conditional_scope=conditional,
            original_candidate_count=TASKS,
            original_task_ids=conditional["original_task_ids"],
            original_1000_admitted=False,
            population_selection_explicitly_registered=True,
            selection_uses_probe_outcomes=False,
        )
    scope = digest(body)
    body["slots"] = []
    for task in tasks:
        for index in range(SLOTS_PER_TASK):
            slot = dict(
                task_id=task,
                slot_index=index,
                purpose="train" if index < TRAIN_SLOTS else "sealed_diagnostic",
            )
            body["slots"].append(
                {
                    **slot,
                    "slot_id": "finqa_probe_slot:" + digest({"inventory_scope": scope, **slot}),
                }
            )
    return {**body, "inventory_id": "finqa_probe_inventory:" + digest(body)}


def inventory_progress(registration, completed_slot_ids):
    """Fixed-denominator collection progress without inspecting any quality label."""
    registration = _checked_registration(registration)
    completed = tuple(completed_slot_ids)
    known = {row["slot_id"] for row in registration["slots"]}
    done = set(completed)
    _require(
        len(done) == len(completed) and done <= known, "duplicate or unregistered completed slot"
    )
    missing = [row["slot_id"] for row in registration["slots"] if row["slot_id"] not in done]
    progress = dict(
        inventory_id=registration["inventory_id"],
        denominator=len(known),
        completed=len(completed),
        missing_slot_ids=missing,
        ready_for_joint_qualification=not missing,
        qualification_performed=False,
        training_authorized=False,
    )
    if registration.get("conditional_scope") is not None:
        progress.update(
            scope_id=registration["scope_id"],
            original_candidate_count=TASKS,
            conditional_candidate_count=registration["candidate_task_count"],
            original_1000_admitted=False,
        )
    return progress


def record_slot_result(registration, slot_id, episode: Episode, qualification):
    """Bind an external qualification result; do not invent financial semantics.

    The controller must first seal all registered collection slots before calling the
    qualifier. freeze_inventory independently rejects any incomplete result set.
    Raw episodes and full qualification evidence remain in their original stores;
    this lightweight record carries their exact hashes, without copying histories.
    """
    index = (
        registration if isinstance(registration, InventoryIndex) else InventoryIndex(registration)
    )
    registration, slots = index._registration, index._slots
    _require(slot_id in slots, "unregistered Probe slot")
    slot = slots[slot_id]
    episode = Episode.model_validate_json(episode.model_dump_json())
    _require(
        episode.task_id == slot["task_id"] and episode.dataset == registration["dataset"],
        "slot task differs from original episode",
    )
    _require(
        episode.config.model_dump(mode="json") == registration["slot_config"],
        "slot generation config differs from preregistration",
    )
    _require(
        episode.provider.backend == "deepseek_api"
        and episode.provider.model_id == "deepseek-flash",
        "Probe inventory requires actual deepseek-flash API generation",
    )
    _require(
        episode_is_complete(episode), "unknown/infrastructure episode cannot complete a Probe slot"
    )
    _require(
        qualification["qualification_rule_id"] == registration["qualification_rule_id"]
        and qualification["mapper_rule_id"] == registration["mapper_rule_id"],
        "qualification/Mapper rule drift",
    )
    decision = QualificationDecision.model_validate(qualification["decision"])
    _require(
        decision.episode_sha256 == digest(episode) and decision.task_id == slot["task_id"],
        "qualification belongs to a different actual Probe episode",
    )
    _require(
        decision.evidence_sha256 == digest(qualification["evidence"]),
        "qualification evidence hash mismatch",
    )
    body = dict(
        schema="finance_research.probe_slot_result.v1",
        inventory_id=registration["inventory_id"],
        **slot,
        episode_sha256=digest(episode),
        qualification_rule_id=registration["qualification_rule_id"],
        mapper_rule_id=registration["mapper_rule_id"],
        decision=decision.model_dump(mode="json"),
        all_provider_calls_settled=True,
        episode_complete=True,
        actual_model_calls=episode.actual_model_calls,
        actual_API_prompt_tokens=(
            sum(turn.usage["prompt_tokens"] for turn in episode.turns)
            if all(type(turn.usage.get("prompt_tokens")) is int for turn in episode.turns)
            else None
        ),
        actual_API_completion_tokens=(
            sum(turn.usage["completion_tokens"] for turn in episode.turns)
            if all(type(turn.usage.get("completion_tokens")) is int for turn in episode.turns)
            else None
        ),
        stop_reason=episode.stop_reason,
        original_episode_retained=True,
        semantic_decision_produced_by_inventory=False,
    )
    return {**body, "slot_result_id": "finqa_probe_slot_result:" + digest(body)}


def freeze_inventory(registration, slot_results):
    """Freeze actual support only after all slots; no selective support repair.

    admitted means full candidate-task *qualified original Probe support*. Offline
    Student encoding and training authorization remain independent later gates.
    """
    registration = _checked_registration(registration)
    results = tuple(copy.deepcopy(row) for row in slot_results)
    by_slot = {row["slot_id"]: row for row in results}
    slots = registration["slots"]
    _require(
        len(by_slot) == len(results) == len(slots)
        and set(by_slot) == {row["slot_id"] for row in slots},
        f"all {len(slots):,} distinct preregistered slots must complete "
        "before qualification freeze",
    )
    seen_episodes = set()
    train_counts, sealed_counts = defaultdict(Counter), defaultdict(Counter)
    verdicts = {"train": Counter(), "sealed_diagnostic": Counter()}
    train_decisions, retained_train_slots, sealed_slot_ids, ordered_results = [], [], [], []
    for slot in slots:
        row = by_slot[slot["slot_id"]]
        _require(
            row.get("slot_result_id")
            == "finqa_probe_slot_result:"
            + digest({key: value for key, value in row.items() if key != "slot_result_id"}),
            "slot result content identity mismatch",
        )
        _require(
            row["inventory_id"] == registration["inventory_id"]
            and all(row[key] == value for key, value in slot.items()),
            "slot identity/purpose changed after generation",
        )
        _require(
            row["episode_complete"] is True and row["all_provider_calls_settled"] is True,
            "incomplete/unknown slot cannot enter material freeze",
        )
        _require(
            row["qualification_rule_id"] == registration["qualification_rule_id"]
            and row["mapper_rule_id"] == registration["mapper_rule_id"],
            "post-collection qualification/Mapper drift",
        )
        decision = QualificationDecision.model_validate(row["decision"])
        _require(
            decision.task_id == slot["task_id"]
            and decision.episode_sha256 == row["episode_sha256"],
            "slot/qualification evidence binding mismatch",
        )
        _require(
            row["episode_sha256"] not in seen_episodes, "one original episode cannot fill two slots"
        )
        seen_episodes.add(row["episode_sha256"])
        verdicts[slot["purpose"]].update([decision.verdict])
        ordered_results.append(row)
        if slot["purpose"] == "train":
            train_decisions.append(decision)
            if decision.verdict == "CompletePass":
                train_counts[slot["task_id"]].update([decision.state_id])
                retained_train_slots.append(slot["slot_id"])
        else:
            sealed_slot_ids.append(slot["slot_id"])
            if decision.verdict == "CompletePass":
                sealed_counts[slot["task_id"]].update([decision.state_id])
    tasks = registration["task_ids"]
    count = len(tasks)
    missing = [task for task in tasks if not train_counts[task]]
    support = {task: sorted(train_counts[task]) for task in tasks}
    prior = {
        task: {
            state: str(Fraction(count, sum(train_counts[task].values())))
            for state, count in sorted(train_counts[task].items())
        }
        for task in tasks
    }
    # Only an independently registered conditional scope may change the population.
    # Zero qualified tasks inside it still block the entire fixed active roster.
    mu = {task: str(Fraction(1, count)) for task in tasks}
    material = None
    if not missing:
        material = MaterialRegistration(
            source_manifest_sha256=registration["source_manifest_sha256"],
            validator_binding_id=registration["qualification_rule_id"],
            qualification_registration_id="finqa_post_collection_qualification:"
            + digest(
                {
                    "inventory_id": registration["inventory_id"],
                    "qualification_rule_id": registration["qualification_rule_id"],
                    "mapper_rule_id": registration["mapper_rule_id"],
                    "slot_result_ids": [row["slot_result_id"] for row in ordered_results],
                }
            ),
            state_support={task: tuple(states) for task, states in support.items()},
            mu=mu,
            pi0=prior,
            decisions=tuple(train_decisions),
        ).model_dump(mode="json")
    static = [task for task in tasks if len(support[task]) == 1]
    varying = [task for task in tasks if len(support[task]) > 1]
    body = dict(
        schema="finance_research.frozen_probe_support.v1",
        inventory_id=registration["inventory_id"],
        candidate_task_count=count,
        slot_denominator=len(slots),
        train_slot_denominator=count * TRAIN_SLOTS,
        sealed_slot_denominator=count * (SLOTS_PER_TASK - TRAIN_SLOTS),
        admitted=not missing,
        admission_scope="qualified original Probe support for all 1,000 candidates",
        training_authorized=False,
        student_encoding_admission_separate=True,
        missing_train_task_ids=missing,
        missing_train_task_count=len(missing),
        retained_train_slot_ids=retained_train_slots,
        sealed_diagnostic_slot_ids=sealed_slot_ids,
        all_qualified_train_packages_retained=True,
        sealed_packages_in_training=0,
        verdict_counts={purpose: dict(counts) for purpose, counts in verdicts.items()},
        train_state_counts={task: dict(sorted(train_counts[task].items())) for task in tasks},
        sealed_state_counts={task: dict(sorted(sealed_counts[task].items())) for task in tasks},
        state_support=support,
        mu=mu,
        pi0=prior,
        r=copy.deepcopy(prior),
        prior_interpretation=(
            "empirical qualified train-package frequency; not Probe generation probability"
        ),
        single_state_static_task_ids=static,
        multi_state_task_ids=varying,
        nontrivial_pi_support_present=bool(varying),
        observed_D_pi=sum(max(0, len(support[task]) - 1) for task in tasks),
        D_pi=(sum(len(support[task]) - 1 for task in tasks) if not missing else None),
        M_flex=str(Fraction(len(varying), count)),
        D_pi_null_means_full_population_support_missing=True,
        nontrivial_support_does_not_establish_statistical_power=True,
        pi_optimization_support_ready=not missing and bool(varying),
        material_registration=material,
        slot_results=ordered_results,
        semantic_qualification_performed_by_inventory=False,
        task_deletion_performed=False,
        candidate_tasks_deleted=0,
        extra_collection_or_per_state_topups=False,
    )
    conditional = registration.get("conditional_scope")
    if conditional is not None:
        body.update(
            schema="finance_research.frozen_conditional_probe_support.v1",
            scope_id=conditional["scope_id"],
            conditional_scope=copy.deepcopy(conditional),
            original_candidate_count=TASKS,
            original_task_ids=conditional["original_task_ids"],
            original_1000_admitted=False,
            admission_scope=(
                f"qualified original Probe support for all {count} tasks in the "
                "explicit static-supported conditional population, not original 1,000"
            ),
            excluded_original_task_ids=[
                row["task_id"] for row in conditional["coverage_rows"] if not row["included"]
            ],
            exclusions_precede_Probe_generation=True,
            no_further_task_deletion_or_mass_renormalization=True,
        )
    token_counts = {purpose: {} for purpose in ("train", "sealed_diagnostic")}
    for row in ordered_results:
        if row["decision"]["verdict"] != "CompletePass":
            continue
        state = (
            token_counts[row["purpose"]]
            .setdefault(row["task_id"], {})
            .setdefault(
                row["decision"]["state_id"],
                dict(packages=0, API_prompt_tokens=0, API_completion_tokens=0),
            )
        )
        state["packages"] += 1
        for key in ("API_prompt_tokens", "API_completion_tokens"):
            value = row.get("actual_" + key)
            state[key] = (
                state[key] + value if state[key] is not None and value is not None else None
            )
    body["qualified_state_sample_and_API_token_counts"] = token_counts
    body["API_tokens_are_not_Student_supervised_tokens"] = True
    body["Student_supervised_token_counts"] = None
    return {**body, "frozen_inventory_id": "finqa_frozen_probe_support:" + digest(body)}
