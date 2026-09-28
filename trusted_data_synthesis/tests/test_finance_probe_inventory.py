"""CPU-only fixed-slot and H1-R encoding controls; qualification is mocked explicitly."""

import copy
import json
from collections import Counter
from fractions import Fraction

import pytest
from test_finance_research_encoding import CharacterTokenizer, api_episode

from trusted_synthesis.finance_research.contracts import digest, invocation_identity
from trusted_synthesis.finance_research.encoding import (
    encode_probe_for_student,
    events_for_turns,
    probe_generation_record,
    supervised_turns,
)
from trusted_synthesis.finance_research.probe_inventory import (
    InventoryIndex,
    freeze_inventory,
    inventory_progress,
    record_slot_result,
    register_inventory,
)
from trusted_synthesis.finance_research.providers import _api_messages, canonical_assistant_message
from trusted_synthesis.finance_research.training_policy import (
    training_interface_policy,
    training_interface_policy_v3,
)


def h1r_episode():
    """Project explicit mock HTTP records to the newly registered H1-R contract."""
    old = api_episode()
    config = old.config.model_copy(
        update={
            "harness_id": "bigfinance-derived-vtdo-v3",
            "submission_profile": "finqa_program_v2",
            "context_limit": 1048576,
            "max_new_tokens": 2048,
        }
    )
    turns, events = [], []
    messages = copy.deepcopy(old.turns[0].provider_metadata["public_request"]["messages"])
    scope = {"run_id": "mock-inventory", "episode_id": "mock-slot", "attempt": 1}
    for index, (turn, event) in enumerate(zip(old.turns, old.tool_events, strict=True)):
        call = turn.tool_calls[0].model_copy(update={"call_id": "repeated-technical-id"})
        metadata = copy.deepcopy(turn.provider_metadata)
        metadata["harness_invocation"] = invocation_identity(scope, turn_index=index)
        metadata["public_request"]["messages"] = _api_messages(messages)
        metadata["public_request"]["thinking"] = {"type": "disabled"}
        metadata["public_request"]["max_tokens"] = 2048
        metadata["request_sha256"] = digest(metadata["public_request"])
        metadata["api_response"]["choices"][0]["message"]["tool_calls"][0]["id"] = call.call_id
        turn = turn.model_copy(update={"tool_calls": (call,), "provider_metadata": metadata})
        envelope = {
            "result_handle": f"r{index + 1}",
            "status": "error" if event.is_error else "ok",
            "output": event.raw_output,
        }
        event = event.model_copy(
            update={
                "call_id": call.call_id,
                "result_handle": envelope["result_handle"],
                "visible_output": json.dumps(envelope),
                "invocation_id": invocation_identity(scope, turn_index=index, tool_index=0)[
                    "invocation_id"
                ],
                "reference_protocol": "visible-result-handle-v2",
            }
        )
        turns.append(turn)
        events.append(event)
        messages += [
            canonical_assistant_message(turn),
            {"role": "tool", "tool_call_id": call.call_id, "content": event.visible_output},
        ]
    return old.model_copy(
        update={
            "config": config,
            "turns": tuple(turns),
            "tool_events": tuple(events),
            "messages": tuple(messages),
        }
    )


@pytest.fixture(scope="module")
def registration():
    return register_inventory(
        task_ids=["finqa:mock"] + [f"original-{i:04d}" for i in range(1, 1000)],
        source_manifest_sha256="a" * 64,
        qualification_rule_id="qualification:mock",
        mapper_rule_id="mapper:mock",
        collection_policy_id="collection:mock",
        slot_config=h1r_episode().config,
    )


def fixture_result(reg, slot, *, missing=False):
    # This is an explicit structural fixture, not a real qualification/API record.
    index, task = slot["slot_index"], slot["task_id"]
    verdict, state = "CompletePass", "a"
    if slot["purpose"] == "sealed_diagnostic":
        state = "sealed-only-state"
    elif task == reg["task_ids"][0]:
        verdict, state = (
            ("unknown", None)
            if index == 4
            else ("invalid", None)
            if index == 5
            else ("CompletePass", "b" if index == 3 else "a")
        )
    if missing and task == reg["task_ids"][7] and slot["purpose"] == "train":
        verdict, state = "unknown", None
    sha = digest(["mock-episode", slot["slot_id"]])
    decision = dict(
        episode_sha256=sha,
        task_id=task,
        verdict=verdict,
        state_id=state,
        evidence_sha256=digest(["mock-evidence", slot["slot_id"]]),
        reason="explicit structural fixture, never semantic proof",
    )
    body = dict(
        schema="finance_research.probe_slot_result.v1",
        inventory_id=reg["inventory_id"],
        **slot,
        episode_sha256=sha,
        qualification_rule_id=reg["qualification_rule_id"],
        mapper_rule_id=reg["mapper_rule_id"],
        decision=decision,
        all_provider_calls_settled=True,
        episode_complete=True,
        actual_model_calls=1,
        stop_reason="final_answer",
        original_episode_retained=True,
        semantic_decision_produced_by_inventory=False,
    )
    return {**body, "slot_result_id": "finqa_probe_slot_result:" + digest(body)}


def test_fixed_roster_and_progress_never_turns_budget_stop_into_selected_population(registration):
    assert len(registration["slots"]) == 8000
    assert Counter(row["purpose"] for row in registration["slots"]) == {
        "train": 6000,
        "sealed_diagnostic": 2000,
    }
    progress = inventory_progress(registration, [registration["slots"][0]["slot_id"]])
    assert progress["denominator"] == 8000 and progress["completed"] == 1
    assert (
        len(progress["missing_slot_ids"]) == 7999 and not progress["ready_for_joint_qualification"]
    )
    assert not progress["qualification_performed"]
    with pytest.raises(ValueError, match="8,000"):
        freeze_inventory(registration, [fixture_result(registration, registration["slots"][0])])


def test_post_collection_prior_keeps_every_qualified_train_package_and_excludes_sealed(
    registration,
):
    frozen = freeze_inventory(
        InventoryIndex(registration),
        [fixture_result(registration, slot) for slot in registration["slots"]],
    )
    first = registration["task_ids"][0]
    assert frozen["admitted"] and not frozen["training_authorized"]
    assert frozen["pi0"][first] == frozen["r"][first] == {"a": "3/4", "b": "1/4"}
    assert frozen["train_state_counts"][first] == {"a": 3, "b": 1}
    assert frozen["sealed_state_counts"][first] == {"sealed-only-state": 2}
    assert "sealed-only-state" not in frozen["state_support"][first]
    assert len(frozen["retained_train_slot_ids"]) == 5998
    assert len(frozen["material_registration"]["decisions"]) == 6000
    assert len(frozen["sealed_diagnostic_slot_ids"]) == 2000
    assert len(frozen["single_state_static_task_ids"]) == 999
    assert frozen["multi_state_task_ids"] == [first]
    assert sum(Fraction(value) for value in frozen["mu"].values()) == 1
    # pi0/(5*n_xz*L) agrees for all qualified packages despite state multiplicity.
    assert Fraction(frozen["pi0"][first]["a"]) / (5 * 3 * 2) == Fraction(1, 5 * 4 * 2)
    assert Fraction(frozen["pi0"][first]["b"]) / (5 * 1 * 2) == Fraction(1, 5 * 4 * 2)


def test_zero_train_task_is_retained_and_sealed_success_cannot_rescue_or_renormalize(registration):
    frozen = freeze_inventory(
        registration,
        [fixture_result(registration, slot, missing=True) for slot in registration["slots"]],
    )
    missing = registration["task_ids"][7]
    assert not frozen["admitted"] and frozen["material_registration"] is None
    assert frozen["missing_train_task_ids"] == [missing]
    assert frozen["state_support"][missing] == [] and frozen["pi0"][missing] == {}
    assert len(frozen["mu"]) == 1000 and frozen["mu"][missing] == "1/1000"
    assert frozen["sealed_state_counts"][missing] == {"sealed-only-state": 2}
    assert frozen["candidate_tasks_deleted"] == 0


def test_slot_result_binds_actual_episode_decision_and_rules(registration):
    episode = h1r_episode()
    evidence = {"mock": True, "source": "not a real semantic proof"}
    result = {
        "decision": {
            "episode_sha256": digest(episode),
            "task_id": episode.task_id,
            "verdict": "unknown",
            "state_id": None,
            "evidence_sha256": digest(evidence),
            "reason": "limited evidence unresolved",
        },
        "evidence": evidence,
        "qualification_rule_id": registration["qualification_rule_id"],
        "mapper_rule_id": registration["mapper_rule_id"],
    }
    index = InventoryIndex(registration)
    row = record_slot_result(index, registration["slots"][0]["slot_id"], episode, result)
    assert row["decision"]["verdict"] == "unknown" and row["episode_sha256"] == digest(episode)
    changed = copy.deepcopy(result)
    changed["evidence"]["tampered"] = True
    with pytest.raises(ValueError, match="evidence hash"):
        record_slot_result(index, registration["slots"][0]["slot_id"], episode, changed)
    with pytest.raises(ValueError, match="unknown/infrastructure"):
        record_slot_result(
            index,
            registration["slots"][0]["slot_id"],
            episode.model_copy(update={"all_provider_calls_settled": False}),
            result,
        )


def test_H1R_API_encoder_matches_invocations_not_repeated_technical_ids():
    episode = h1r_episode()
    assert len({event.call_id for event in episode.tool_events}) == 1
    assert events_for_turns(episode) == episode.tool_events
    assert supervised_turns(episode) == (False, True, True)
    encoded = encode_probe_for_student(probe_generation_record(episode), CharacterTokenizer())
    assert [row.supervised for row in encoded.rows] == [False, True, True]
    history = json.loads(encoded.rows[1].rendered_prompt.split("\n<assistant>\n")[0])
    assert json.loads(history[-1]["content"]) == json.loads(episode.tool_events[0].visible_output)
    assert json.loads(history[-1]["content"])["status"] == "error"
    assert encoded.context_limit == 24576 and episode.config.context_limit == 1048576
    with pytest.raises(ValueError, match="untruncated"):
        encode_probe_for_student(
            probe_generation_record(episode), CharacterTokenizer(), context_limit=100
        )


@pytest.mark.parametrize(
    "mode", ["missing", "enabled", "extra", "reasoning_text", "reasoning_tokens"]
)
def test_H1R_Probe_thinking_contract_is_exact_and_no_hidden_reasoning_is_material(mode):
    episode = h1r_episode()
    turn = episode.turns[0]
    metadata = copy.deepcopy(turn.provider_metadata)
    if mode == "missing":
        del metadata["public_request"]["thinking"]
    elif mode == "enabled":
        metadata["public_request"]["thinking"] = {"type": "enabled"}
    elif mode == "extra":
        metadata["public_request"]["repair"] = True
    elif mode == "reasoning_text":
        metadata["api_response"]["choices"][0]["message"]["reasoning_content"] = (
            "unexpected thinking"
        )
    else:
        metadata["api_response"]["usage"]["completion_tokens_details"] = {"reasoning_tokens": 1}
    metadata["request_sha256"] = digest(metadata["public_request"])
    episode = episode.model_copy(
        update={
            "turns": (turn.model_copy(update={"provider_metadata": metadata}),) + episode.turns[1:]
        }
    )
    with pytest.raises(ValueError, match="thinking|request/response"):
        probe_generation_record(episode)


def test_v3_policy_separates_approved_inventory_from_unstarted_training_proposal():
    old = training_interface_policy()
    policy = training_interface_policy_v3()
    assert old["schema_version"].endswith(".v2") and old["probe"]["rollouts_per_task"] is None
    assert policy["previous_policy_id"] == old["policy_id"]
    assert policy["probe"]["sessions"] == 8000 and policy["probe"]["hard_cap_CNY"] == "800"
    future = policy["training_comparison_proposal_not_run_registration"]
    assert not policy["training_authorized"]
    assert (
        future["paired_seeds"] == [11, 29, 47] and future["physical_SFT_steps_three_seeds"] == 9000
    )
    assert (
        future["feedback_sessions_per_seed"] == 700 and future["local_generate_call_cap"] == 264992
    )
    assert future["N"] == 0 and future["combined_KL_coefficient"] == 5


def conditional_scope_fixture(original_registration):
    original = original_registration["task_ids"]
    selected = [original[0], original[7]]
    body = dict(
        schema="finqa_conditional_probe_scope.v1",
        dataset="finqa",
        original_denominator=1000,
        original_task_ids=original,
        task_ids=selected,
        scoped_task_count=len(selected),
        coverage_rows=[
            dict(
                task_id=task,
                included=task in selected,
                status="author_anchored_supported" if task in selected else "unknown",
                reason="static author anchor available"
                if task in selected
                else "outside fixed static support",
                evidence_sha256=digest(["mock static source evidence", task]),
            )
            for task in original
        ],
        qualification_rule_id=original_registration["qualification_rule_id"],
        mapper_rule_id=original_registration["mapper_rule_id"],
        snapshot_id="fixture-snapshot",
        source_manifest_sha256=original_registration["source_manifest_sha256"],
        private_sha256="b" * 64,
        selection_uses_probe_outcomes=False,
        static_support_is_material_qualification=False,
        slot_counts={"total": 8, "train": 6, "sealed": 2},
        author_source_assumption=(
            "explicit fixture author-source assumption; not a real qualification"
        ),
    )
    return {**body, "scope_id": "finqa_conditional_scope:" + digest(body)}


def conditional_registration(original_registration, scope=None, *, task_ids=None):
    scope = conditional_scope_fixture(original_registration) if scope is None else scope
    return register_inventory(
        task_ids=scope["task_ids"] if task_ids is None else task_ids,
        source_manifest_sha256=original_registration["source_manifest_sha256"],
        qualification_rule_id=original_registration["qualification_rule_id"],
        mapper_rule_id=original_registration["mapper_rule_id"],
        collection_policy_id=original_registration["collection_policy_id"],
        slot_config=original_registration["slot_config"],
        conditional_scope=scope,
    )


def test_conditional_inventory_changes_real_slots_and_preserves_all_original_exclusions(
    registration,
):
    conditional = conditional_registration(registration)
    assert conditional["candidate_task_count"] == 2
    assert conditional["registered_slot_denominator"] == len(conditional["slots"]) == 16
    assert conditional["original_candidate_count"] == 1000
    assert conditional["original_task_ids"] == registration["task_ids"]
    coverage = conditional["conditional_scope"]["coverage_rows"]
    assert len(coverage) == 1000 and sum(row["included"] for row in coverage) == 2
    assert coverage[1]["reason"] == "outside fixed static support"
    assert {slot["task_id"] for slot in conditional["slots"]} == set(conditional["task_ids"])
    progress = inventory_progress(InventoryIndex(conditional), [conditional["slots"][0]["slot_id"]])
    assert progress["denominator"] == 16 and progress["completed"] == 1
    assert progress["original_candidate_count"] == 1000
    assert not progress["original_1000_admitted"]
    # The old full-original registration remains a separate unchanged population.
    assert registration["candidate_task_count"] == 1000
    assert "conditional_scope" not in registration and "scope_id" not in registration


def test_conditional_freeze_uses_mu_over_registered_N_and_never_claims_original_1000_admission(
    registration,
):
    conditional = conditional_registration(registration)
    frozen = freeze_inventory(
        InventoryIndex(conditional),
        [fixture_result(conditional, slot) for slot in conditional["slots"]],
    )
    assert frozen["admitted"] and not frozen["original_1000_admitted"]
    assert frozen["candidate_task_count"] == 2 and frozen["original_candidate_count"] == 1000
    assert frozen["mu"] == {task: "1/2" for task in conditional["task_ids"]}
    assert frozen["material_registration"]["mu"] == frozen["mu"]
    assert len(frozen["material_registration"]["decisions"]) == 12
    assert frozen["train_slot_denominator"] == 12 and frozen["sealed_slot_denominator"] == 4
    assert len(frozen["excluded_original_task_ids"]) == 998
    assert frozen["conditional_scope"] == conditional["conditional_scope"]
    assert frozen["scope_id"] == conditional["scope_id"]
    assert not frozen["training_authorized"] and frozen["sealed_packages_in_training"] == 0


def test_missing_qualified_task_inside_conditional_scope_blocks_without_another_subset(
    registration,
):
    conditional = conditional_registration(registration)
    missing = conditional["task_ids"][-1]
    results = [fixture_result(conditional, slot) for slot in conditional["slots"]]
    for row in results:
        if row["task_id"] == missing and row["purpose"] == "train":
            row["decision"].update(verdict="unknown", state_id=None)
            row["slot_result_id"] = "finqa_probe_slot_result:" + digest(
                {key: value for key, value in row.items() if key != "slot_result_id"}
            )
    frozen = freeze_inventory(conditional, results)
    assert not frozen["admitted"] and frozen["material_registration"] is None
    assert frozen["missing_train_task_ids"] == [missing]
    assert frozen["mu"] == {task: "1/2" for task in conditional["task_ids"]}
    assert frozen["state_support"][missing] == []
    assert frozen["sealed_state_counts"][missing] == {"sealed-only-state": 2}
    assert (
        not frozen["original_1000_admitted"]
        and frozen["no_further_task_deletion_or_mass_renormalization"]
    )


def test_conditional_roster_requires_valid_external_scope_and_exact_original_order(registration):
    selected = conditional_scope_fixture(registration)["task_ids"]
    with pytest.raises(ValueError, match="1,000"):
        register_inventory(
            task_ids=selected,
            source_manifest_sha256=registration["source_manifest_sha256"],
            qualification_rule_id=registration["qualification_rule_id"],
            mapper_rule_id=registration["mapper_rule_id"],
            collection_policy_id="fixture",
            slot_config=registration["slot_config"],
        )
    with pytest.raises(ValueError, match="roster/order"):
        conditional_registration(registration, task_ids=list(reversed(selected)))
    scope = conditional_scope_fixture(registration)
    scope["source_manifest_sha256"] = "c" * 64
    scope["scope_id"] = "finqa_conditional_scope:" + digest(
        {key: value for key, value in scope.items() if key != "scope_id"}
    )
    with pytest.raises(ValueError, match="source manifest"):
        conditional_registration(registration, scope)
