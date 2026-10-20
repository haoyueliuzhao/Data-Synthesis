"""Frozen, bounded post-hoc diagnostics for the balanced feedback repetition.

Only sealed local artifacts are read. No model, generation, scoring, tool
execution, backward pass or scientific mutation is available in this module.
Formal commands require the independently frozen V63 implementation and rules.
Pure functions remain importable for small CPU/mock tests.
"""
from __future__ import annotations

import argparse
import ast
import copy
import fcntl
import gc
import hashlib
import importlib
import inspect
import json
import math
import textwrap
import time
from collections import Counter, defaultdict
from contextlib import contextmanager
from fractions import Fraction
from pathlib import Path

import finqa_v63_binding as binding

ROOT, OLD_ROOT = binding.ROOT, binding.OLD_ROOT
SEEDS, NEW_ARMS = binding.SEEDS, binding.ARMS
OLD_ARMS = ("Hold", "C1", "C05")
PRIMARY_PANEL = "step894_dev883_greedy"
PARSER_BRANCHES = (
    "A_no_opening_envelope",
    "B_malformed_tag_in_prose_prefix",
    "C_non_envelope_between_or_after_envelopes",
    "D_invalid_call_object_schema",
    "E_missing_closing_envelope",
    "F_strict_JSON_or_argument_extraction_exception",
    "G_accepted_tool_envelopes",
)
LAYER_LABELS = {
    "reason": "public_reasoning_and_public_updates",
    "tool": "approved_ordinary_tool_envelope_and_its_Student_EOS",
    "final": "approved_submit_program_envelope_and_its_Student_EOS",
}
DRAW_COMPONENT_FIELDS = (
    "draw_components", "draw_gJ", "gJ_by_draw", "C_by_draw", "draw_C_diagnostics",
    "draw_gradient_digests", "draw_components_schema", "draw_response_counts",
    "formal_and_draws_atomically_committed",
)
DRAW_METADATA_SCOPES = ("evidence", "feedback_report", "report", "binding", "backend_identity")
require, digest = binding.require, binding.digest


def policy():
    return dict(
        schema="v63_bounded_posthoc_diagnostics_policy.v1",
        source_old_root=str(OLD_ROOT), output_root=str(ROOT / "diagnostics"),
        old_results_already_seen=True, analysis_is_posthoc_not_blinded=True,
        original_B_remaining_72_examples_read=False,
        old_invalid_population=dict(panel=PRIMARY_PANEL, seeds=list(SEEDS),
            arms=list(OLD_ARMS), denominator_per_condition=883,
            expected_invalid_by_arm=dict(C05=271, C1=247, Hold=295), expected_total=813),
        parser=dict(categories=list(PARSER_BRANCHES),
            implementation="same frozen parse_qwen_native_response; label its seven tuple return branches only",
            episode_exclusive_category="terminal returned turn's original-parser first-return branch",
            first_rejected_turn="separate earliest A..F returned turn, not the episode exclusive category",
            saved_original_tool_calls_compared=True, repair_or_rescore=False,
            saved_parser_disagreement_blocks_diagnostic_acceptance=True,
            accepted_prefix_or_longer_generation_counterfactual=False),
        qualitative=dict(batch=0, baseline="C1", candidate="C05",
            strata=["I->R", "R->I"], maximum_per_parent_per_direction=6,
            maximum_per_parent=12, maximum_total=36, redistribute_unused_stratum_quota=False,
            order="ascending canonical selection SHA256, then original task key",
            digest_fields=["policy_id", "seed", "task_key", "transition",
                           "baseline_episode_sha256", "candidate_episode_sha256"],
            immutable_selection_before_reading_original_pair_bytes=True,
            read_both_original_trajectories_and_existing_tool_events=True,
            automatic_reading_packet_is_not_completed_manual_analysis=True,
            new_batch_additional_qualitative_pairs=0),
        new_invalid_population=dict(batch=1, seeds=list(SEEDS), arms=list(NEW_ARMS),
            denominator_per_condition=883, maximum_rows=5298,
            same_automatic_parser_categories=True, no_new_qualitative_reading_quota=True),
        directions=dict(C_already_includes_mu=True,
            executed_direction="sum_task_state C[x,z] * (q[x,z] - parent_pi[x,z])",
            multiply_direction_by_mu_again=False,
            q_distance="mu-weighted TV and both directional KLs on identical positive support",
            report_saved_RMS_and_floor=True,
            RMS_definition="original mu-weighted RMS(C/mu) over noncontrol support",
            old_new_same_temperature=True,
            old_C_on_new_direction_and_new_C_on_old_direction=True,
            within_batch_two_temperature_comparison=True,
            success_episode_task_and_source_support=True,
            endpoint="complete dev883 native I/W/R utility",
            explanatory_only=True, two_batches_not_a_population_variance_estimate=True,
            missing_new_results="PENDING, never invented or selected from the better old/new batch",
            missing_old_draw_components="NA only after bounded formal metadata field inspection; no old R3 replay",
            old_draw_field_names=list(DRAW_COMPONENT_FIELDS),
            old_draw_metadata_scopes=list(DRAW_METADATA_SCOPES),
            old_draw_inspection="existing old outer/distribution metadata plus C05 replay result and final complete checkpoint record",
            old_draw_intermediate_checkpoint_scan=False, old_draw_replay_Tensor_opened=False,
            existing_old_draw_fields="retain exact source/field references; do not fabricate numerical comparisons"),
        coefficients=dict(
            categories=LAYER_LABELS,
            source="original reviewed span authority and original frozen Student layer_target_positions",
            retokenize_or_reclassify_original_text=False,
            original_three_layers_partition_all_and_only_supervised_targets=True,
            reason_and_update_separately_identified=False,
            EOS="retain original encoding's action layer; no EOS inferred from decoded text",
            distribution="Hold: actual parent pi; every C branch: its own actual fixed q",
            token_coefficient="p_branch[x,z] / (B_actual * n_xz * whole_package_L_P)",
            window=[597, 894], updates=298,
            original_seed_schedule_and_real_tail_batches=True,
            multiply_coefficient_by_mu=False,
            zero_target_context_not_removed=True, loss_or_gradient_contribution_claimed=False,
            classification_frozen_before_diagnostic_calculation=True),
        payload_access=dict(old_C05="one SHA-bound CPU mmap extraction of C/q/evidence per seed",
            gradient_tensor_values_accessed=False, model_constructed=False,
            Tensor_container_opening_disclosed=True, extraction_cost_recorded=True,
            extracted_small_inputs_reused=True),
        source_mutation=False, external_API_calls=0, new_model_calls=0,
        native_rescoring_calls=0, new_backward_passes=0, GPU_work=0,
    )


def _root(root):
    root = Path(root).resolve()
    require(root == ROOT.resolve(), "diagnostics belong only to the registered V63 root")
    return root


def _frozen_entry(root):
    manifest = binding.checked(root / "implementation/record.json")
    source = root / "implementation/finqa_v63_diagnostics.py"
    require(Path(__file__).resolve() == source
            and manifest["sha256"][source.name] == binding.sha(source),
            "formal diagnostics require the byte-frozen V63 entry, not workspace execution")
    return manifest


def prepare(root=ROOT):
    root = _root(root)
    _frozen_entry(root)
    protocol = binding.checked(root / "protocol/record.json")
    require(protocol["diagnostics_policy"] == policy(), "diagnostic policy was not frozen prospectively")
    path = root / "diagnostics/rules/record.json"
    if path.exists():
        return checked_policy(root)
    return binding.publish(path, dict(schema="v63_frozen_posthoc_diagnostic_rules.v1",
        protocol_id=protocol["id"], policy=policy(), implementation=binding.entry(root / "implementation/record.json"),
        source=binding.file_ref(Path(__file__)), registered_before_diagnostic_scans=True,
        old_outcomes_already_known=True, preparation_only=True))


def checked_policy(root=ROOT):
    root = _root(root)
    manifest = _frozen_entry(root)
    protocol = binding.checked(root / "protocol/record.json")
    value = binding.checked(root / "diagnostics/rules/record.json")
    require(value["protocol_id"] == protocol["id"]
            and value["policy"] == protocol["diagnostics_policy"] == policy()
            and binding.read_ref(value["implementation"])["id"] == manifest["id"]
            and value["source"] == binding.file_ref(Path(__file__)),
            "registered post-hoc diagnostic scope or source changed")
    return value


@contextmanager
def _locked(root):
    checked_policy(root)
    with (root / "diagnostics/owner.lock").open("a") as stream:
        fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield


def _read_json(path, expected_sha=None):
    path = Path(path).resolve()
    raw = path.read_bytes()
    actual = hashlib.sha256(raw).hexdigest()
    require(expected_sha is None or actual == expected_sha, "sealed source bytes changed: " + str(path))
    return json.loads(raw), dict(path=str(path), sha256=actual, bytes=len(raw))


def _coordinate(seed, arm):
    require(seed in SEEDS and arm in OLD_ARMS, "unregistered diagnostic condition")
    return f"seed{seed}/{arm}"


def native_state(row):
    """Interpret already saved native judgments; never execute or score an answer."""
    native = row["native"]
    value = native["native"]["execution_accuracy"]
    require(value is None or type(value) in (int, float) and value in (0, 1),
            "native execution is binary or explicitly UNKNOWN")
    if value is None:
        require(native["status"] == "unknown", "missing execution must remain UNKNOWN")
        return "UNKNOWN"
    if native["status"] == "invalid_prediction":
        require(value == 0 and native["program_executable"] is False, "invalid/native contradiction")
        return "I"
    require(native["status"] == "scored" and native["program_executable"] is True,
            "known native state must be executable or invalid")
    return "R" if value == 1 else "W"


def classified_parser(parser):
    """Attach labels only to original returns; every predicate and output stays."""
    tree = ast.parse(textwrap.dedent(inspect.getsource(parser)))
    returns = sorted((node for node in ast.walk(tree)
        if isinstance(node, ast.Return) and isinstance(node.value, ast.Tuple)), key=lambda node: node.lineno)
    require(len(returns) == len(PARSER_BRANCHES), "original seven parser return branches changed")
    for node, category in zip(returns, PARSER_BRANCHES, strict=True):
        node.value = ast.Tuple(elts=[ast.Constant(category), node.value], ctx=ast.Load())
    ast.fix_missing_locations(tree)
    namespace = dict(parser.__globals__)
    exec(compile(tree, str(__file__) + "::label_original_returns", "exec"), namespace)
    return namespace[parser.__name__]


def _calls(values):
    result = []
    for value in values:
        require(isinstance(value, dict) or hasattr(value, "model_dump"), "unknown original parsed-call type")
        result.append(value.model_dump(mode="json") if hasattr(value, "model_dump") else dict(value))
    return result


def inspect_episode(episode, score_row, classifier):
    task = score_row.get("original_task_key", score_row["task_key"])
    require(f"{episode['dataset']}/{episode['task_id']}" == task,
            "native result and original episode task differ")
    require(episode["stop_reason"] == score_row["stop_reason"]
            and episode["actual_model_calls"] == score_row["actual_model_calls"],
            "saved native termination and original episode differ")
    turns, previous = [], set()
    for index, turn in enumerate(episode["turns"], start=1):
        receipt = turn.get("receipt")
        if receipt is None:
            turns.append(dict(turn=index, category="NA_missing_original_receipt", saved_parser_result_matches=None))
            continue
        raw = turn["raw_text"]
        require(hashlib.sha256(raw.encode()).hexdigest() == receipt["raw_response_sha256"],
                "original raw response does not match its actual receipt")
        category, (_prefix, parsed) = classifier(raw, call_prefix=receipt["call_id"])
        calls = _calls(parsed)
        earlier = [event for event in episode["tool_events"] if event["call_id"] in previous]
        turns.append(dict(turn=index, category=category, parsed_call_count=len(calls),
            saved_parser_result_matches=calls == turn["tool_calls"],
            raw_response_sha256=receipt["raw_response_sha256"],
            generated_tokens=len(receipt["raw_generated_token_ids"]),
            actual_EOS=receipt["actual_eos"], finish_reason=receipt["finish_reason"],
            earlier_tool_events=len(earlier), earlier_tool_errors=sum(bool(e["is_error"]) for e in earlier),
            earlier_tool_names=dict(Counter(e["name"] for e in earlier))))
        previous.update(call["call_id"] for call in turn["tool_calls"])
    terminal = turns[-1] if turns else dict(turn=None, category="NA_no_returned_turn")
    first = next((row for row in turns if row["category"] in PARSER_BRANCHES[:-1]), None)
    return dict(task_key=task, source_group=score_row["source_group"], native_state=native_state(score_row),
        stop_reason=score_row["stop_reason"], native_reason=score_row["native"].get("reason"),
        terminal_parser_category=terminal["category"], first_rejected_turn=first,
        turns=turns, original_receipts_complete=bool(turns) and all(row["category"] in PARSER_BRANCHES for row in turns),
        saved_parser_disagreement=any(row["saved_parser_result_matches"] is False for row in turns),
        model_calls=episode["actual_model_calls"], tools_reexecuted=0, native_rescored=False)


def select_pairs(reports, episode_indexes, *, policy_id):
    """Old b0 only: <=6 digest-ordered pairs per parent and transition."""
    selected, population = [], {}
    for seed in SEEDS:
        left, right = (reports[_coordinate(seed, arm)] for arm in ("C1", "C05"))
        require(left["denominator"] == right["denominator"] == 883
                and len(left["results"]) == len(right["results"]) == 883,
                "paired selection requires each complete original dev883 report")
        strata = {"I->R": [], "R->I": []}
        for baseline, candidate in zip(left["results"], right["results"], strict=True):
            task = baseline.get("original_task_key", baseline["task_key"])
            require(task == candidate.get("original_task_key", candidate["task_key"]),
                    "native pair task order changed")
            transition = native_state(baseline) + "->" + native_state(candidate)
            if transition not in strata:
                continue
            before = episode_indexes[_coordinate(seed, "C1")][task]
            after = episode_indexes[_coordinate(seed, "C05")][task]
            identity = dict(policy_id=policy_id, seed=seed, task_key=task, transition=transition,
                baseline_episode_sha256=before["sha256"], candidate_episode_sha256=after["sha256"])
            strata[transition].append(dict(**identity, selection_digest=digest(identity),
                baseline=before, candidate=after))
        population[str(seed)] = {key: len(values) for key, values in strata.items()}
        for transition in ("I->R", "R->I"):
            rows = sorted(strata[transition], key=lambda row: (row["selection_digest"], row["task_key"]))
            selected.extend(rows[:6])
    require(len(selected) <= 36 and all(sum(row["seed"] == seed for row in selected) <= 12 for seed in SEEDS),
            "qualitative selection exceeded its fixed old-only budget")
    return dict(selected=selected, count=len(selected), transition_population=population,
        feedback_batch=0, unused_stratum_quota_redistributed=False, new_batch_qualitative_pairs=0,
        selection_precedes_original_pair_reading=True, manual_reading_completed=False)


def _probability(value):
    result = float(Fraction(str(value)))
    require(math.isfinite(result) and result > 0, "strictly positive finite original state probability required")
    return result


def checked_distribution(value, support):
    require(set(value) == set(support), "diagnostic task support changed")
    result = {}
    for task in support:
        require(set(value[task]) == set(support[task]) and value[task], "diagnostic state support changed")
        result[task] = {state: _probability(probability) for state, probability in value[task].items()}
        require(abs(math.fsum(result[task].values()) - 1) < 1e-9, "state probabilities are not normalized")
    return result


def direction_score(C, q, parent_pi):
    """C already contains task mu. Deliberately no mu argument exists."""
    q = checked_distribution(q, parent_pi)
    parent = checked_distribution(parent_pi, parent_pi)
    require(set(C) == set(parent), "C task support differs")
    terms = []
    for task in parent:
        require(set(C[task]) == set(parent[task]), "C state support differs")
        for state in parent[task]:
            c = float(C[task][state])
            require(math.isfinite(c), "C contains a non-finite value")
            terms.append(c * (q[task][state] - parent[task][state]))
    return math.fsum(terms)


def q_distance(left, right, mu):
    left = checked_distribution(left, right)
    right = checked_distribution(right, right)
    require(set(mu) == set(left), "mu task support differs")
    weights = {task: _probability(mu[task]) for task in mu}
    require(abs(math.fsum(weights.values()) - 1) < 1e-9, "task mu is not normalized")
    return dict(
        weighted_TV=math.fsum(weights[t] * abs(left[t][z] - right[t][z]) / 2 for t in left for z in left[t]),
        weighted_KL_left_right=math.fsum(weights[t] * left[t][z] * math.log(left[t][z] / right[t][z])
                                       for t in left for z in left[t]),
        weighted_KL_right_left=math.fsum(weights[t] * right[t][z] * math.log(right[t][z] / left[t][z])
                                       for t in left for z in left[t]),
        mu_used_for_distribution_distance_only=True,
    )


def encoding_summary(package, rows):
    """Count the original disjoint approved layers, including their original EOS."""
    counts = Counter({layer: 0 for layer in LAYER_LABELS})
    row_digests = []
    for row in rows:
        layers, positions = row["layer_target_positions"], row["target_positions"]
        require(set(layers) == set(LAYER_LABELS)
                and all(type(p) is int and p > 0 for p in positions)
                and positions == sorted(set(positions)), "invalid original supervised target positions")
        combined = [p for layer in LAYER_LABELS for p in layers[layer]]
        require(sorted(combined) == positions and len(combined) == len(set(combined))
                and len(row["target_ids"]) == len(positions),
                "original reason/tool/final layers do not exactly partition targets")
        for layer in LAYER_LABELS:
            counts[layer] += len(layers[layer])
        row_digests.append(row["row_sha256"])
    length = package["whole_package_target_tokens"]
    require(type(length) is int and length > 0 and sum(counts.values()) == length,
            "whole-package L_P differs from original supervised spans")
    return dict(package_id=package["package_id"], task_id=package["task_id"], state_id=package["state_id"],
        L_P=length, layer_tokens=dict(counts), row_count=len(rows),
        original_encoded_row_ids_digest=digest(row_digests))


def coefficient_mass(packages, distribution, batches, *, expected_updates=298):
    """Sum coefficients, not NLL or gradients, with actual finite task exposure."""
    require(len(batches) == expected_updates and expected_updates > 0, "fixed update-window length changed")
    roster, counts, seen = defaultdict(set), Counter(), set()
    for package in packages:
        require(package["package_id"] not in seen, "a whole package cannot be counted twice")
        seen.add(package["package_id"])
        task, state = package["task_id"], package["state_id"]
        roster[task].add(state)
        counts[task, state] += 1
        require(set(package["layer_tokens"]) == set(LAYER_LABELS)
                and all(type(n) is int and n >= 0 for n in package["layer_tokens"].values())
                and type(package["L_P"]) is int and package["L_P"] > 0
                and sum(package["layer_tokens"].values()) == package["L_P"],
                "compact package categories must retain the original whole-package token denominator")
    probabilities = checked_distribution(distribution, roster)
    exposure = {task: Fraction(0) for task in roster}
    tails, visits = Counter(), Counter()
    for batch in batches:
        tasks = batch["task_ids"]
        require(tasks and len(tasks) == len(set(tasks)) and set(tasks) <= set(roster)
                and len(tasks) <= 5, "actual complete-task batch changed")
        for task in tasks:
            exposure[task] += Fraction(1, len(tasks))
            tails[task] += len(tasks) < 5
            visits[task] += 1
    require(sum(exposure.values()) == expected_updates, "actual finite batch exposure does not conserve updates")
    terms = {layer: [] for layer in LAYER_LABELS}
    task_terms = {task: {layer: [] for layer in LAYER_LABELS} for task in roster}
    for package in packages:
        task, state, length = package["task_id"], package["state_id"], package["L_P"]
        token_weight = float(exposure[task]) * probabilities[task][state] / (counts[task, state] * length)
        for layer in LAYER_LABELS:
            mass = token_weight * package["layer_tokens"][layer]
            terms[layer].append(mass)
            task_terms[task][layer].append(mass)
    mass = {layer: math.fsum(values) for layer, values in terms.items()}
    total = math.fsum(mass.values())
    require(abs(total - expected_updates) < 1e-6, "supervised coefficient mass does not conserve update count")
    return dict(updates=expected_updates, package_count=len(packages), task_count=len(roster),
        state_count=len(counts), coefficient_mass=mass,
        coefficient_mass_fraction={key: value / total for key, value in mass.items()},
        total_coefficient_mass=total, expected_total_mass=expected_updates,
        per_task={task: dict(exposure=str(exposure[task]), visits=visits[task], tail_visits=tails[task],
            mass={layer: math.fsum(values) for layer, values in task_terms[task].items()}) for task in roster},
        exact_actual_batch_denominators=True, branch_distribution_used=True,
        separate_reason_and_update_not_claimed=True, actual_loss_or_gradient_contribution=False)


def feedback_coverage(rewards, scores, source_groups):
    require(len(rewards) == len(scores) == 700 and all(type(v) in (int, float) and v in (0, 1) for v in rewards),
            "complete original binary-reward 700 cohort required")
    successful = [row["task_id"] for value, row in zip(rewards, scores, strict=True) if value == 1]
    require(set(row["task_id"] for row in scores) <= set(source_groups), "feedback source lineage missing")
    return dict(denominator=700, successful_episodes=len(successful),
        successful_unique_tasks=len(set(successful)),
        successful_source_groups=len({source_groups[task] for task in successful}),
        source_group_successful_episode_counts=dict(Counter(source_groups[task] for task in successful)),
        successful_episodes_by_draw=[sum(rewards[start:start+350]) for start in (0, 350)],
        successful_unique_tasks_by_draw=[len({row["task_id"] for value, row in
            zip(rewards[start:start+350], scores[start:start+350], strict=True) if value == 1})
            for start in (0, 350)],
        zero_reward_episodes_retained_in_denominator=True)


def _model_inputs(source_root, batch, arms):
    plan = binding.checked(source_root / "evaluations/registration/record.json")
    reports, indexes, sources = {}, {}, {}
    for seed in SEEDS:
        for arm in arms:
            coordinate = _coordinate(seed, arm)
            jobs = [job for job in plan["jobs"].values() if
                (job["seed"], job["arm"], job["panel"], job["draw_seed"])
                == (seed, arm, PRIMARY_PANEL, 20260928)]
            require(len(jobs) == 1 and jobs[0]["denominator"] == 883, "one complete native dev job per condition")
            job = jobs[0]
            score_path = source_root / f"evaluations/panels/{PRIMARY_PANEL}/models/seed{seed}/{arm}/record.json"
            score = binding.checked(score_path)
            require(score["registration_id"] == plan["id"] and score["panel"] == PRIMARY_PANEL
                    and (score["seed"], score["arm"]) == (seed, arm)
                    and score["denominator"] == len(score["results"]) == 883,
                    "diagnostics require the exact complete sealed dev883 model report")
            if batch:
                require(score["feedback_batch"] == job["feedback_batch"] == 1, "new-batch model identity changed")
            directory = source_root / "evaluations/jobs" / job["job_id"]
            whole = binding.checked(directory / "whole_queue_seal/record.json")
            require(whole["registration_id"] == plan["id"] and whole["job_id"] == job["job_id"]
                    and whole["denominator"] == 883 and whole["all_provider_calls_settled"] is True,
                    "original complete generation seal is required")
            seal, seal_ref = _read_json(whole["generation_seal"]["path"], whole["generation_seal"]["sha256"])
            generation = Path(seal_ref["path"]).parent.parent
            require(generation == (directory / "shards" / PRIMARY_PANEL / "generation").resolve(),
                    "generation seal escaped this exact model job")
            run, run_ref = _read_json(generation / "run.json")
            tasks = [row.get("original_task_key", row["task_key"]) for row in score["results"]]
            require(run["id"] == whole["run_id"] and seal["id"] == whole["generation_seal_id"]
                    and run["tasks"] == tasks == plan["cohorts"]["development"]["tasks"]
                    and len(tasks) == len(set(tasks)) == len(seal["episodes"]) == 883
                    and run["episode_keys"] == [entry["key"] for entry in seal["episodes"]]
                    and run["config"] == job["config"] and run["provider"] == job["model_identity"],
                    "sealed score/run/config/model/task ordering changed")
            indexes[coordinate] = {}
            for task, entry in zip(tasks, seal["episodes"], strict=True):
                path = (generation / entry["path"]).resolve()
                require(path.is_relative_to(generation), "episode reference escaped its generation tree")
                indexes[coordinate][task] = dict(path=str(path), sha256=entry["sha256"], episode_key=entry["key"])
            reports[coordinate] = score
            sources[coordinate] = dict(score=binding.entry(score_path),
                whole_generation_seal=binding.entry(directory / "whole_queue_seal/record.json"),
                generation_seal=seal_ref, run=run_ref)
    return reports, indexes, sources, plan


def _actual_parser():
    locations = binding.install_scientific_paths()
    module = importlib.import_module("trusted_synthesis.finance_research.qwen_protocol")
    require(Path(module.__file__).resolve().is_relative_to(Path(locations["frozen_source_root"])),
            "diagnostics must use the original byte-frozen native parser")
    return classified_parser(module.parse_qwen_native_response), binding.file_ref(module.__file__)


def _pair_packet(root, rules, selection, reports, indexes, classifier, cached):
    path = root / "diagnostics/invalid/batch0/reading_packet/record.json"
    if path.exists():
        saved = binding.checked(path)
        require(saved["selection_id"] == selection["id"] and saved["rules_id"] == rules["id"],
                "bounded reading packet belongs to another frozen selection")
        return saved
    score_indexes = {key: {row.get("original_task_key", row["task_key"]): row for row in value["results"]}
                     for key, value in reports.items()}
    pairs = []
    for chosen in selection["selected"]:
        sides = {}
        for label, arm in (("baseline", "C1"), ("candidate", "C05")):
            coordinate = _coordinate(chosen["seed"], arm)
            reference = indexes[coordinate][chosen["task_key"]]
            key = reference["path"]
            try:
                if key in cached:
                    episode, source = cached[key]
                else:
                    episode, source = _read_json(key, reference["sha256"])
            except FileNotFoundError:
                sides[label] = dict(arm=arm, available=False, expected_original_episode=reference,
                    reason="NA_original_episode_unavailable")
                continue
            factual = inspect_episode(episode, score_indexes[coordinate][chosen["task_key"]], classifier)
            sides[label] = dict(arm=arm, available=True, original_episode=source, facts=factual,
                raw_turns=[turn["raw_text"] for turn in episode["turns"]],
                existing_tool_events=episode["tool_events"], saved_final_answer=episode["final_answer"])
        available = all(side["available"] for side in sides.values())
        if available:
            require(sides["baseline"]["facts"]["native_state"] + "->" + sides["candidate"]["facts"]["native_state"]
                    == chosen["transition"], "selected native transition changed")
        pairs.append(dict(seed=chosen["seed"], task_key=chosen["task_key"], transition=chosen["transition"],
            selection_digest=chosen["selection_digest"], **sides,
            observations=dict(
                original_both_sides_read=available,
                baseline_terminal_parser=sides["baseline"].get("facts", {}).get("terminal_parser_category"),
                candidate_terminal_parser=sides["candidate"].get("facts", {}).get("terminal_parser_category"),
                baseline_existing_tool_errors=(sum(bool(e["is_error"]) for e in sides["baseline"]["existing_tool_events"])
                                               if sides["baseline"]["available"] else None),
                candidate_existing_tool_errors=(sum(bool(e["is_error"]) for e in sides["candidate"]["existing_tool_events"])
                                                if sides["candidate"]["available"] else None),
                source_derived_facts_only=True, causal_mechanism_claimed=False,
                repair_rescore_or_counterfactual=False)))
    return binding.publish(path, dict(schema="v63_old_only_bounded_pair_reading_packet.v1",
        rules_id=rules["id"], selection_id=selection["id"], pair_count=len(pairs), pairs=pairs,
        manual_reading_completed=False, automatic_original_bytes_read_not_manual_analysis=True,
        new_batch_pairs_read=0, old_B_remaining_examples_read=0))


def _invalid_diagnostics(root, rules, source_root, batch, reports, indexes, sources):
    directory = root / "diagnostics/invalid" / f"batch{batch}"
    if (directory / "summary/record.json").exists():
        saved = binding.checked(directory / "summary/record.json")
        require(saved["rules_id"] == rules["id"] and saved["feedback_batch"] == batch,
                "invalid diagnostic summary belongs to another rule or batch")
        return saved
    classifier, parser_ref = _actual_parser()
    selection = None
    selected_paths, selected_cache = set(), {}
    if batch == 0:
        selection = binding.publish(directory / "selection/record.json",
            dict(schema="v63_old_I_R_pair_selection.v1", rules_id=rules["id"],
                 score_sources=sources, **select_pairs(reports, indexes, policy_id=digest(policy()))))
        selected_paths = {row[side]["path"] for row in selection["selected"] for side in ("baseline", "candidate")}
    models, total_categories, by_arm = {}, Counter(), Counter()
    for coordinate, score in reports.items():
        invalid = [row for row in score["results"] if native_state(row) == "I"]
        path = directory / "models" / coordinate / "record.json"
        if path.exists():
            model = binding.checked(path)
            require(model["rules_id"] == rules["id"] and model["source"] == sources[coordinate]
                    and model["parser_source"] == parser_ref, "saved invalid classification source changed")
        else:
            rows = []
            for row in invalid:
                task = row.get("original_task_key", row["task_key"])
                reference = indexes[coordinate][task]
                try:
                    episode, episode_ref = _read_json(reference["path"], reference["sha256"])
                except FileNotFoundError:
                    rows.append(dict(task_key=task, available=False,
                        terminal_parser_category="NA_original_episode_unavailable", expected=reference))
                    continue
                inspected = inspect_episode(episode, row, classifier)
                rows.append(dict(available=True, original_episode=episode_ref, **inspected))
                if reference["path"] in selected_paths:
                    selected_cache[reference["path"]] = episode, episode_ref
            model = binding.publish(path, dict(schema="v63_saved_native_invalid_first_parser_diagnostic.v1",
                rules_id=rules["id"], coordinate=coordinate, feedback_batch=batch,
                source=sources[coordinate], parser_source=parser_ref, denominator=883,
                invalid_count=len(invalid), rows=rows,
                original_archive_unavailable=sum(not row["available"] for row in rows),
                incomplete_original_receipts=sum(row.get("original_receipts_complete") is False for row in rows),
                parser_disagreement_count=sum(row.get("saved_parser_disagreement", False) for row in rows),
                terminal_parser_category_counts=dict(Counter(row["terminal_parser_category"] for row in rows)),
                first_rejected_turn_category_counts=dict(Counter(row["first_rejected_turn"]["category"]
                    for row in rows if row.get("first_rejected_turn") is not None)),
                first_rejected_turn_counts=dict(Counter(str(row["first_rejected_turn"]["turn"])
                    for row in rows if row.get("first_rejected_turn") is not None)),
                native_scores_rewritten=False, parser_repaired=False, new_model_calls=0))
        models[coordinate] = binding.entry(path)
        total_categories.update(model["terminal_parser_category_counts"])
        by_arm[score["arm"]] += len(invalid)
    if batch == 0:
        require(dict(by_arm) == policy()["old_invalid_population"]["expected_invalid_by_arm"]
                and sum(by_arm.values()) == 813, "the fixed old dev invalid population changed")
        packet = _pair_packet(root, rules, selection, reports, indexes, classifier, selected_cache)
    else:
        packet = None
    summaries = [binding.read_ref(ref) for ref in models.values()]
    missing = sum(value["original_archive_unavailable"] for value in summaries)
    incomplete = sum(value["incomplete_original_receipts"] for value in summaries)
    disagreements = sum(value["parser_disagreement_count"] for value in summaries)
    unknowns = sum(native_state(row) == "UNKNOWN" for report in reports.values() for row in report["results"])
    missing_pairs = sum(not row["observations"]["original_both_sides_read"] for row in packet["pairs"]) if packet else 0
    return binding.publish(directory / "summary/record.json",
        dict(schema="v63_bounded_invalid_diagnostic_summary.v1", rules_id=rules["id"], feedback_batch=batch,
            source_root=str(source_root), model_reports=models, invalid_by_arm=dict(by_arm),
            invalid_total=sum(by_arm.values()), terminal_parser_category_counts=dict(total_categories),
            original_archive_unavailable=missing, incomplete_original_receipts=incomplete,
            native_UNKNOWN_rows=unknowns, selected_pairs_original_bytes_incomplete=missing_pairs,
            parser_disagreement_count=disagreements,
            parser_disagreement_detected=bool(disagreements),
            first_rejected_turn_category_counts=dict(sum(
                (Counter(row["first_rejected_turn_category_counts"]) for row in summaries), Counter())),
            status=invalid_acceptance_status(missing=missing, incomplete=incomplete,
                unknowns=unknowns, missing_pairs=missing_pairs, disagreements=disagreements),
            selection_id=selection["id"] if selection else None, pair_packet_id=packet["id"] if packet else None,
            qualitative_pair_limit=36 if batch == 0 else 0, manual_reading_completed=False,
            original_B_remaining_72_examples_read=False, native_scores_changed=False))


def invalid_acceptance_status(*, missing, incomplete, unknowns, missing_pairs, disagreements):
    if disagreements:
        return "BLOCKED_PARSER_DISAGREEMENT"
    return "INCOMPLETE" if missing or incomplete or unknowns or missing_pairs else "COMPLETE"


def _utility(report):
    counts = Counter(native_state(row) for row in report["results"])
    require(report["denominator"] == len(report["results"]) == 883, "complete dev883 denominator required")
    return dict(denominator=883, states={key: counts[key] for key in ("I", "W", "R", "UNKNOWN")},
        correct=counts["R"], unknown=counts["UNKNOWN"],
        complete_mean=counts["R"] / 883 if not counts["UNKNOWN"] else None)


def _plain_metadata(value):
    """Refuse tensors rather than calling .item(), .tolist() or a tensor digest."""
    if value is None or type(value) in (str, bool, int):
        return value
    if type(value) is float:
        require(math.isfinite(value), "non-finite scientific diagnostic metadata")
        return value
    if isinstance(value, dict):
        require(all(isinstance(key, str) for key in value), "metadata dictionary needs string keys")
        return {key: _plain_metadata(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain_metadata(item) for item in value]
    raise ValueError("diagnostic metadata extraction cannot access Tensor values: " + type(value).__name__)


def _draw_field_references(value, source, prefix=""):
    """Observe only registered field names; never dereference a gradient value."""
    require(isinstance(value, dict), "old draw metadata container must be a dictionary")
    references = [dict(source=source, field=prefix + field, numerical_value_read=False)
                  for field in DRAW_COMPONENT_FIELDS if field in value]
    for field in DRAW_METADATA_SCOPES:
        if isinstance(value.get(field), dict):
            references.extend(_draw_field_references(value[field], source, prefix + field + "."))
    return references


def _old_draw_components(source_root, parent, arm, report, inspected, found):
    """Inspect at most two additional JSON records per old C05 condition."""
    inspected, found = list(inspected), list(found)
    if arm == "C05":
        replay_root = source_root / f"stages/seed{parent['seed']}/replay_C05"
        result_path = replay_root / "result/record.json"
        result = binding.checked(result_path)
        require(result["status"] == "COMPLETE" and result["parent_id"] == parent["id"]
                and result["stage"] == "replay_C05" and result["complete_replay"] is True
                and result["denominator"] == 700, "old draw inspection requires the actual completed C05 replay")
        result_source = binding.entry(result_path)
        inspected.append(result_source)
        found.extend(_draw_field_references(result, result_source))
        checkpoint_binding = report["response_checkpoint_binding"]
        count = checkpoint_binding["response_count"]
        require(type(count) is int and count >= 0 and result["responses"] == count,
                "old draw inspection must use the actual final response cursor")
        path = replay_root / "checkpoints" / f"response{count:06d}" / "record.json"
        checkpoint = binding.checked(path)
        require(checkpoint["cursor"] == count and checkpoint["full_replay_complete"] is True
                and checkpoint["binding"] == checkpoint_binding,
                "old final response checkpoint differs from the actual completed replay")
        source = binding.entry(path)
        inspected.append(source)
        found.extend(_draw_field_references(checkpoint, source))
    require(arm in NEW_ARMS and inspected, "old draw availability needs its actual formal metadata sources")
    return dict(
        status="PRESENT_REFERENCED_NOT_NUMERICALLY_RECOMPUTED" if found else "NA_NO_DRAW_FIELDS_IN_FORMAL_METADATA",
        inspection_complete=True, inspected_sources=inspected, existing_component_fields=found,
        registered_field_names=list(DRAW_COMPONENT_FIELDS), registered_metadata_scopes=list(DRAW_METADATA_SCOPES),
        absence_scope="inspected bound formal result/checkpoint/container metadata only",
        unavailable_source_is_not_absence=True, intermediate_checkpoints_scanned=False,
        gradient_tensor_values_read=False, old_replay_Tensor_opened=False,
        old_R3_replayed=False, old_draw_numerical_agreement_recomputed=False)


def _payload_metadata(source_root, parent, arm, batch):
    stage = f"distribution_{arm}"
    directory = source_root / f"stages/seed{parent['seed']}/{stage}"
    result = binding.checked(directory / "result/record.json")
    record = binding.read_ref(result["payload"])
    require(result["status"] == "COMPLETE"
            and record["parent_id"] == parent["id"]
            and record["parent_state_digest"] == parent["parent_state_digest"]
            and record["stage"] == stage and record["actual_tensors_saved"] is True,
            "distribution payload must be the completed same-parent scientific stage")
    path = directory / "payload/state.pt"
    require(Path(result["payload"]["path"]).resolve() == directory / "payload/record.json",
            "distribution payload reference escaped its exact stage")
    started = time.monotonic()
    require(path.stat().st_size == record["state_bytes"]
            and binding.sha(path) == record["state_sha256"], "scientific payload byte binding changed")
    torch = importlib.import_module("torch")
    require(not torch.cuda.is_initialized(), "read-only diagnostics cannot initialize CUDA")
    value = torch.load(path, map_location="cpu", weights_only=False, mmap=True)
    try:
        condition = _plain_metadata(value["condition"])
        require(value["point_id"] == condition["identity"]["point_id"] == parent["point_id"]
                and condition["temperature"] == binding.TEMPERATURES[arm],
                "saved C/q belongs to a different point or feedback temperature")
        if batch:
            require((condition["arm"], condition["feedback_batch"], condition["draw_seeds"])
                    == (arm, batch, list(binding.DRAW_SEEDS)), "saved C/q is not the registered new feedback repeat")
        else:
            require(arm == "C05" and condition["temperature"] == 0.5, "only old C05 needs this payload extraction")
        metadata = _plain_metadata(dict(C=value["C"], q=value["q"], condition=condition,
            distribution=value["evidence"]["distribution"], feedback_report=value["evidence"]["feedback_report"]))
        metadata["existing_draw_component_fields"] = _draw_field_references(
            value, dict(path=str(path), sha256=record["state_sha256"]))
    finally:
        del value
        gc.collect()
    require(not torch.cuda.is_initialized(), "CPU mmap metadata extraction initialized CUDA")
    return metadata, dict(
        source_result=binding.entry(directory / "result/record.json"),
        source_payload_record=result["payload"], source_state_sha256=record["state_sha256"],
        source_state_digest_reference_only=record["state_digest"], source_container=str(path),
        source_container_bytes=record["state_bytes"], elapsed_seconds=time.monotonic()-started,
        CPU_mmap_container_opened=True, full_file_SHA_bytes_read=record["state_bytes"],
        gradient_tensor_values_accessed=False, full_tensor_state_digest_recomputed=False,
        model_constructed=False, new_backward_passes=0)


def _material_input(root, rules, parents):
    path = root / "diagnostics/inputs/material_and_schedules/record.json"
    if path.exists():
        saved = binding.checked(path)
        require(saved["rules_id"] == rules["id"] and saved["pool_id"] == parents[137]["pool_id"],
                "saved original supervision material input changed")
        return saved
    started = time.monotonic()
    binding.install_scientific_paths()
    training = binding.old_module("finqa_v25_training_replication")
    rt = training.load_runtime()
    source_plan = binding.read_ref(parents[137]["training_protocol"])
    require(all(parent["training_protocol"] == parents[137]["training_protocol"]
                and parent["pool_id"] == parents[137]["pool_id"] for parent in parents.values()),
            "all branches must retain one original complete material")
    # This is the original reviewed-span/encoding loader. No model/assets loader,
    # tokenizer, new encoding, parameter checkpoint or class gradient is opened.
    pool = rt.material.load_training_pool(source_plan["material_binding"]["path"])
    require(pool.production_verified and pool.cache_id == parents[137]["pool_id"]
            and list(pool.task_ids) == source_plan["training_task_ids"],
            "original supervised material identity changed")
    packages = [encoding_summary(package, pool._rows[package["package_id"]]) for package in pool.packages]
    require(len(pool.task_ids) == 744 and len(packages) == 2468
            and len({(p["task_id"], p["state_id"]) for p in packages}) == 1360,
            "original material task/state/package support changed")
    schedules = {}
    for seed in SEEDS:
        schedule = training.build_task_schedule(pool.task_ids, seed)
        require(rt.v8._tree_digest(schedule) == parents[seed]["component_digests"]["schedule"],
                "frozen seed schedule does not match the actual saved parent schedule")
        window = schedule["batches"][596:894]
        require(len(window) == 298, "fixed 597..894 actual schedule window changed")
        schedules[str(seed)] = dict(schedule_sha256=schedule["schedule_sha256"],
            actual_parent_schedule_digest=parents[seed]["component_digests"]["schedule"], batches=window)
    saved = binding.publish(path, dict(schema="v63_original_supervised_coefficient_inputs.v1",
        rules_id=rules["id"], pool_id=pool.cache_id,
        source_training_protocol=parents[137]["training_protocol"],
        material_binding=source_plan["material_binding"],
        frozen_material_source=binding.file_ref(rt.material.__file__),
        original_span_and_encoding_loader_reused=True, encoding_recomputed=False,
        package_count=len(packages), packages=packages, schedules=schedules,
        layer_labels=LAYER_LABELS, elapsed_seconds=time.monotonic()-started,
        gradient_or_model_Tensor_values_read=False, model_calls=0, CUDA_initialized=rt.torch.cuda.is_initialized()))
    require(not saved["CUDA_initialized"], "original material diagnostics must remain CPU-only")
    del pool, packages
    gc.collect()
    return saved


def _source_groups(root, rules, old_parents, old_plan):
    path = root / "diagnostics/inputs/feedback_source_groups/record.json"
    if path.exists():
        value = binding.checked(path)
        require(value["rules_id"] == rules["id"], "feedback source-group input belongs to another rule")
        return value["groups"]
    wanted = set()
    for parent in old_parents.values():
        reference = parent["original_T1_feedback_bindings"]["draw0_run"]
        run, _ = _read_json(reference["path"], reference["sha256"])
        require(len(run["tasks"]) == 350 and all("/" in task for task in run["tasks"]),
                "old complete feedback task roster changed")
        wanted.update(task.split("/", 1)[1] for task in run["tasks"])
    require(len(wanted) == 350, "all feedback conditions must retain the same 350 tasks")
    binding.install_scientific_paths()
    storage = importlib.import_module("trusted_synthesis.finance_research.storage")
    manifest, tasks, lineages = storage.load_public_snapshot(old_plan["snapshot"])
    require(manifest["id"] == old_plan["snapshot_id"], "original public source snapshot changed")
    groups = {task.task_id: lineage.source_group for task, lineage in zip(tasks, lineages, strict=True)
              if task.task_id in wanted}
    require(set(groups) == wanted and all(groups.values()), "complete original feedback source groups required")
    binding.publish(path, dict(schema="v63_original_feedback_source_groups.v1", rules_id=rules["id"],
        snapshot=old_plan["snapshot"], snapshot_id=manifest["id"], groups=groups,
        private_references_read=False, new_QA_or_material=False))
    return groups


def _condition_input(root, rules, source_root, parent, arm, batch, report, groups):
    seed = parent["seed"]
    path = root / f"diagnostics/inputs/conditions/batch{batch}/seed{seed}/{arm}/record.json"
    if path.exists():
        saved = binding.checked(path)
        require(saved["rules_id"] == rules["id"] and saved["parent_state_digest"] == parent["parent_state_digest"]
                and saved["feedback_batch"] == batch and saved["arm"] == arm,
                "sealed C/q metadata input belongs to a different condition")
        return saved
    branch_path = source_root / f"branches/seed{seed}/{arm}/completed/record.json"
    branch = binding.checked(branch_path)
    require(branch["status"] == "COMPLETE" and branch["parent_state_digest"] == parent["parent_state_digest"]
            and branch["start_step"] == 596 and branch["end_step"] == 894
            and branch["next_outer894_executed"] is False, "only completed same-parent fixed-q branches may be explained")
    if batch:
        require(branch["feedback_batch"] == 1 and arm in NEW_ARMS, "new branch must be an actual b1 result")
    extraction, coverage, condition, old_draw = None, None, None, None
    if arm == "Hold":
        require(batch == 0, "Hold is reused, never a new feedback condition")
        C, q, distribution, report_feedback = None, parent["parent_pi"], None, None
        scientific_source = binding.entry(branch_path)
    elif arm == "C1" and batch == 0:
        reference = parent["old_outer_checkpoint"]
        original, scientific_source = _read_json(Path(reference["path"]) / "record.json", reference["record_sha256"])
        evidence = original["evidence"]
        C, q = evidence["C"], parent["original_T1_q"]
        distribution, report_feedback = evidence["distribution"], evidence["feedback_report"]
        require(distribution["pi_next"] == q and report_feedback["point_id"] == parent["point_id"],
                "old C1 C/q is not from the registered common point")
        reward_ref = parent["original_T1_feedback_bindings"]["rewards"]
        rewards, reward_source = _read_json(reward_ref["path"], reward_ref["sha256"])
        old_draw = _old_draw_components(source_root, parent, arm, report_feedback,
            [scientific_source], _draw_field_references(original, scientific_source))
    else:
        metadata, extraction = _payload_metadata(source_root, parent, arm, batch)
        C, q, condition = metadata["C"], metadata["q"], metadata["condition"]
        distribution, report_feedback = metadata["distribution"], metadata["feedback_report"]
        require(distribution["pi_next"] == q, "actual executed q differs from its saved distribution evidence")
        scientific_source = extraction["source_payload_record"]
        feedback_root = source_root / f"stages/seed{seed}/feedback_{arm}/feedback" / condition["id"]
        original_condition, condition_source = _read_json(feedback_root / "intent/record.json")
        require(original_condition == condition, "feedback condition and saved C/q binding differ")
        rewards, reward_source = _read_json(feedback_root / "native_rewards/record.json")
        require(rewards["condition_id"] == condition["id"], "native rewards belong to another condition")
        if not batch:
            old_draw = _old_draw_components(source_root, parent, arm, report_feedback,
                [scientific_source], metadata["existing_draw_component_fields"])
    if arm != "Hold":
        require(report_feedback["denominator"] == 700
                and rewards["cohort_seal_sha256"] == report_feedback["cohort_seal_sha256"]
                and digest(rewards["rewards"]) == report_feedback["reward_sha256"],
                "success coverage must use the actual 700 rewards that produced C")
        coverage = dict(feedback_coverage(rewards["rewards"], rewards["scores"], groups), source=reward_source)
        require(coverage["successful_episodes"] == 700-report_feedback["accounting"]["zero_reward_trajectories_skipped"],
                "coverage and actual replay reward accounting differ")
    checked_distribution(q, parent["parent_pi"])
    rt = binding.old_module("finqa_v25_training_replication").load_runtime()
    require(rt.v8._tree_digest(q) == branch["distribution_digest"],
            "coefficient and direction diagnostics must use the branch's actual executed distribution")
    return binding.publish(path, dict(schema="v63_same_parent_C_q_utility_metadata.v1",
        rules_id=rules["id"], seed=seed, arm=arm, feedback_batch=batch,
        temperature=None if arm == "Hold" else binding.TEMPERATURES[arm],
        parent_id=parent["id"], parent_state_digest=parent["parent_state_digest"],
        point_id=parent["point_id"], parent_pi=_plain_metadata(parent["parent_pi"]),
        mu=_plain_metadata(parent["mu"]), C=_plain_metadata(C), q=_plain_metadata(q),
        saved_distribution=_plain_metadata(distribution), feedback_condition=_plain_metadata(condition),
        success_coverage=coverage, scientific_source=scientific_source,
        branch_completed=binding.entry(branch_path), utility=_utility(report),
        CPU_metadata_extraction=extraction, C_already_includes_mu=True,
        old_draw_component_status=(old_draw["status"] if old_draw else
            "NOT_APPLICABLE_HOLD" if arm == "Hold" else "see_original_new_replay_component_acceptance"),
        old_draw_component_inspection=old_draw,
        analysis_only=True, model_calls=0, backward_passes=0))


def _coefficient_results(root, rules, material, inputs, batch):
    references = {}
    for value in inputs:
        seed, arm = value["seed"], value["arm"]
        path = root / f"diagnostics/coefficients/batch{batch}/seed{seed}/{arm}/record.json"
        if path.exists():
            result = binding.checked(path)
            require(result["input_id"] == value["id"] and result["material_input_id"] == material["id"],
                    "coefficient result source changed")
        else:
            result = binding.publish(path, dict(schema="v63_actual_branch_supervised_coefficient_mass.v1",
                rules_id=rules["id"], input_id=value["id"], material_input_id=material["id"],
                seed=seed, arm=arm, feedback_batch=batch, distribution=value["branch_completed"],
                layer_labels=LAYER_LABELS,
                **coefficient_mass(material["packages"], value["q"], material["schedules"][str(seed)]["batches"])))
        references[f"seed{seed}/{arm}/b{batch}"] = binding.entry(path)
    return references


def direction_table(inputs):
    rows = []
    for value in inputs:
        if value["arm"] == "Hold":
            continue
        distribution = value["saved_distribution"]
        temperature = distribution.get("temperature")
        rows.append(dict(seed=value["seed"], arm=value["arm"], feedback_batch=value["feedback_batch"],
            input_id=value["id"], executed_direction_score=direction_score(value["C"], value["q"], value["parent_pi"]),
            direction_multiplied_by_mu_again=False, q_vs_parent=q_distance(value["q"], value["parent_pi"], value["mu"]),
            saved_RMS_C_over_mu=None if temperature is None else temperature.get("global_weighted_RMS"),
            saved_RMS_floor=None if temperature is None else temperature.get("RMS_floor"),
            saved_RMS_after_floor=None if temperature is None else temperature.get("global_scale_after_floor"),
            RMS_unavailable_reason=None if temperature is not None else distribution.get("status", "not_saved"),
            success_coverage=value["success_coverage"], dev_utility=value["utility"]))
    return rows


def cross_batch_table(inputs):
    lookup = {(row["seed"], row["arm"], row["feedback_batch"]): row for row in inputs if row["arm"] != "Hold"}
    rows = []
    for seed in SEEDS:
        for arm in NEW_ARMS:
            old_value, new_value = lookup[seed, arm, 0], lookup[seed, arm, 1]
            require(old_value["parent_state_digest"] == new_value["parent_state_digest"]
                    and old_value["parent_pi"] == new_value["parent_pi"] and old_value["mu"] == new_value["mu"],
                    "old/new diagnostics need one identical real parent, pi and task marginal")
            old_u, new_u = old_value["utility"], new_value["utility"]
            complete = old_u["unknown"] == new_u["unknown"] == 0
            rows.append(dict(seed=seed, arm=arm,
                old_input_id=old_value["id"], new_input_id=new_value["id"],
                same_temperature_q_distance=q_distance(old_value["q"], new_value["q"], old_value["mu"]),
                old_C_old_direction=direction_score(old_value["C"], old_value["q"], old_value["parent_pi"]),
                old_C_new_direction=direction_score(old_value["C"], new_value["q"], old_value["parent_pi"]),
                new_C_old_direction=direction_score(new_value["C"], old_value["q"], old_value["parent_pi"]),
                new_C_new_direction=direction_score(new_value["C"], new_value["q"], old_value["parent_pi"]),
                utility_new_minus_old_correct=new_u["correct"]-old_u["correct"] if complete else None,
                utility_new_minus_old=(new_u["correct"]-old_u["correct"])/883 if complete else None,
                denominator=883, UNKNOWN_not_zero=True, C_direction_extra_mu=False))
    within = []
    for seed in SEEDS:
        for batch in (0, 1):
            one, low = lookup[seed, "C1", batch], lookup[seed, "C05", batch]
            require(one["parent_state_digest"] == low["parent_state_digest"]
                    and one["parent_pi"] == low["parent_pi"] and one["mu"] == low["mu"],
                    "temperature diagnostic pairs require the same actual parent")
            complete = one["utility"]["unknown"] == low["utility"]["unknown"] == 0
            within.append(dict(seed=seed, feedback_batch=batch,
                q_distance_C1_C05=q_distance(one["q"], low["q"], one["mu"]),
                C1_C_on_C05_direction=direction_score(one["C"], low["q"], one["parent_pi"]),
                C05_C_on_C1_direction=direction_score(low["C"], one["q"], one["parent_pi"]),
                utility_C05_minus_C1_correct=low["utility"]["correct"]-one["utility"]["correct"] if complete else None,
                denominator=883))
    return dict(same_temperature_across_batches=rows, same_batch_across_temperatures=within,
        explanatory_only=True, batches_pooled_into_new_primary=False,
        two_batches_not_a_variance_estimate=True, direction_agreement_is_not_causal_or_stability_proof=True)


def old(root=ROOT):
    root = _root(root)
    with _locked(root):
        rules = checked_policy(root)
        output = root / "diagnostics/old/record.json"
        if output.exists():
            result = binding.checked(output)
            require(result["rules_id"] == rules["id"], "old diagnostic closeout policy changed")
            return result
        reports, indexes, sources, plan = _model_inputs(OLD_ROOT, 0, OLD_ARMS)
        invalid = _invalid_diagnostics(root, rules, OLD_ROOT, 0, reports, indexes, sources)
        parents = {seed: binding.checked(OLD_ROOT / f"parents/seed{seed}/record.json") for seed in SEEDS}
        material = _material_input(root, rules, parents)
        groups = _source_groups(root, rules, parents, plan)
        inputs = [_condition_input(root, rules, OLD_ROOT, parents[seed], arm, 0,
                    reports[_coordinate(seed, arm)], groups) for seed in SEEDS for arm in OLD_ARMS]
        coefficients = _coefficient_results(root, rules, material, inputs, 0)
        directions = binding.publish(root / "diagnostics/directions/batch0/record.json",
            dict(schema="v63_old_actual_C_q_utility_table.v1", rules_id=rules["id"], rows=direction_table(inputs),
                new_batch_status="PENDING_NOT_GENERATED_BY_DIAGNOSTICS",
                cross_batch_analysis="deferred until all new branches and all evaluation exits/scores complete",
                C_direction_extra_mu=False, actual_loss_or_gradient_contribution_claimed=False))
        return binding.publish(output, dict(schema="v63_old_bounded_posthoc_diagnostics_complete.v1",
            rules_id=rules["id"], status=invalid["status"], invalid_summary_id=invalid["id"],
            directions_id=directions["id"], coefficient_results=coefficients,
            condition_input_ids={f"seed{row['seed']}/{row['arm']}/b0": row["id"] for row in inputs},
            material_input_id=material["id"], qualitative_packet_exists=True,
            manual_qualitative_reading_completed=False, new_batch_only_planned=True,
            new_model_or_API_calls=0, scoring_calls=0, new_backward_passes=0))


def _postrun_admission(root):
    protocol = binding.checked(root / "protocol/record.json")
    plan = binding.checked(root / "evaluations/registration/record.json")
    barrier = binding.checked(root / "evaluation_barrier/record.json")
    require(barrier["protocol_id"] == plan["protocol_id"] == protocol["id"]
            and len(plan["jobs"]) == 24
            and barrier["all_24_generation_jobs_complete"] is True
            and barrier["all_dispatched_evaluation_workers_exited"] is True
            and barrier["active_children"] == []
            and set(barrier["job_results"]) == set(plan["jobs"]),
            "postrun diagnostics require the sealed actual successful all-24-generation exit barrier")
    for key, job in plan["jobs"].items():
        result_path = root / "evaluations/jobs" / key / "result/record.json"
        require(job["job_id"] == key and barrier["job_results"][key] == binding.file_ref(result_path),
                "postrun generation result path or SHA differs from the controller's all-24-generation barrier")
    for panel in (PRIMARY_PANEL, "step894_calibration120_greedy", "step894_calibration120_random_T1"):
        summary = binding.checked(root / f"evaluations/panels/{panel}/summary/record.json")
        require(summary["registration_id"] == plan["id"] and summary["panel"] == panel,
                "all predeclared new panels must be scored before postrun diagnosis")
    return barrier


def postrun(root=ROOT):
    root = _root(root)
    with _locked(root):
        rules = checked_policy(root)
        _postrun_admission(root)
        prior = binding.checked(root / "diagnostics/old/record.json")
        require(prior["rules_id"] == rules["id"], "original old diagnostic rules are required")
        require(prior["status"] == "COMPLETE",
                "old diagnostic parser/source/UNKNOWN failures block postrun acceptance")
        output = root / "diagnostics/postrun/record.json"
        if output.exists():
            result = binding.checked(output)
            require(result["rules_id"] == rules["id"], "postrun diagnostic rule changed")
            return result
        reports, indexes, sources, _plan = _model_inputs(root, 1, NEW_ARMS)
        invalid = _invalid_diagnostics(root, rules, root, 1, reports, indexes, sources)
        parents = {seed: binding.checked(root / f"parents/seed{seed}/record.json") for seed in SEEDS}
        material = binding.checked(root / "diagnostics/inputs/material_and_schedules/record.json")
        groups = binding.checked(root / "diagnostics/inputs/feedback_source_groups/record.json")["groups"]
        new_inputs = [_condition_input(root, rules, root, parents[seed], arm, 1,
                        reports[_coordinate(seed, arm)], groups) for seed in SEEDS for arm in NEW_ARMS]
        old_inputs = [binding.checked(root / f"diagnostics/inputs/conditions/batch0/seed{seed}/{arm}/record.json")
                      for seed in SEEDS for arm in OLD_ARMS]
        coefficients = _coefficient_results(root, rules, material, new_inputs, 1)
        directions = binding.publish(root / "diagnostics/directions/postrun/record.json",
            dict(schema="v63_balanced_old_new_C_q_utility_diagnostics.v1", rules_id=rules["id"],
                rows=direction_table(old_inputs + new_inputs), **cross_batch_table(old_inputs + new_inputs),
                C_already_contains_mu=True, actual_loss_or_gradient_contribution_claimed=False))
        return binding.publish(output, dict(schema="v63_balanced_feedback_postrun_diagnostics_complete.v1",
            rules_id=rules["id"], status=invalid["status"], invalid_summary_id=invalid["id"],
            directions_id=directions["id"], new_coefficient_results=coefficients,
            old_inputs_reused_without_payload_remapping=True, new_qualitative_pairs=0,
            old_promotion_unchanged=True, new_primary_decision_not_modified=True,
            new_model_or_API_calls=0, scoring_calls=0, new_backward_passes=0))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "old", "postrun"))
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()
    result = {"prepare": prepare, "old": old, "postrun": postrun}[args.action](args.root)
    print(json.dumps(dict(id=result["id"], schema=result["schema"], status=result.get("status")), sort_keys=True))


if __name__ == "__main__":
    main()
