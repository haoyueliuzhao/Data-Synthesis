"""Read-only preparation of the fixed V74 mixed-origin continuation panel.

This module copies only information available before the selected source call,
plus the exact V73 cross-model response. It never calls a model, executes a tool,
opens a private reference, or produces a new correctness score.
"""
from __future__ import annotations

from collections import Counter
import copy
import hashlib
import importlib
import json
from pathlib import Path

import finqa_v74_binding as b

require, digest = b.require, b.digest
SOURCE_PROTOCOL_ID = "6ca6c4b8775b30a96cbe6346e5b5a188713a58299d2a14cf736e5fbbc9da0bac"
DIRECTIONS = (("L_from_P", "P", "L"), ("P_from_L", "L", "P"))
EXPECTED_ACTION_COUNTS = {
    ("L_from_P", "F"): (45, 0, 3), ("L_from_P", "K"): (48, 0, 0),
    ("P_from_L", "F"): (12, 26, 10), ("P_from_L", "K"): (42, 5, 1),
}
ACTION_ORDER = ("compliant_submit_candidate", "compliant_nonterminal_candidate", "plain_no_tool_call")


def bound(body):
    body = {key: value for key, value in body.items() if key != "id"}
    return dict(body, id=digest(body))


class Reader:
    """Read each necessary file once and retain its original bytes binding."""
    def __init__(self):
        self.sources, self.values = {}, {}

    def read(self, path, *, sha256=None, record=False):
        path = str(Path(path).resolve())
        if path not in self.values:
            raw = Path(path).read_bytes()
            self.sources[path] = dict(path=path, sha256=hashlib.sha256(raw).hexdigest())
            self.values[path] = json.loads(raw)
        value, reference = self.values[path], self.sources[path]
        require(sha256 is None or reference["sha256"] == sha256, "source bytes changed: " + path)
        if record:
            require(value.get("id") == digest({k: v for k, v in value.items() if k != "id"}),
                    "source record identity changed: " + path)
            reference["id"] = value["id"]
        return value

    def ref(self, path):
        return copy.deepcopy(self.sources[str(Path(path).resolve())])

    def read_ref(self, reference, *, record=True):
        value = self.read(reference["path"], sha256=reference["sha256"], record=record)
        require("id" not in reference or value.get("id") == reference["id"], "source reference identity changed")
        return value


def residual_budget(prior_calls, category, max_steps=32):
    require(type(prior_calls) is int and 0 <= prior_calls < max_steps, "source call index is outside original budget")
    require(max_steps == 32 and category in ACTION_ORDER, "unregistered interaction contract")
    return max(0, max_steps - prior_calls - 1) if category == ACTION_ORDER[1] else 0


def prefix_before(episode, turn_index, source_identity):
    """Keep source turns, events and settlements unchanged; discard its future."""
    require(type(turn_index) is int and 0 <= turn_index < len(episode["turns"]), "invalid source turn index")
    require(episode["all_provider_calls_settled"] is True and episode["provider"] == source_identity,
            "source episode is unsettled or has another identity")
    turns = episode["turns"][:turn_index]
    calls = [call for turn in turns for call in turn["tool_calls"]]
    call_ids = [call["call_id"] for call in calls]
    require(len(set(call_ids)) == len(call_ids), "duplicate historical tool call identity")
    events = episode["tool_events"][:len(call_ids)]
    require([event["call_id"] for event in events] == call_ids,
            "historical event order does not match the exact source prefix")
    require(not any(event["name"] == "submit_program" and not event["is_error"] for event in events),
            "source prefix was already terminal")
    invocation_ids = [turn["provider_metadata"]["invocation_id"] for turn in turns]
    require(len(set(invocation_ids)) == len(invocation_ids), "duplicate source model invocation")
    by_invocation = {}
    for settlement in episode["call_settlements"]:
        invocation = settlement.get("evidence", {}).get("invocation_id")
        if invocation in invocation_ids:
            require(invocation not in by_invocation, "duplicate source settlement")
            by_invocation[invocation] = settlement
    settlements = [by_invocation[invocation] for invocation in invocation_ids]
    for index, (turn, settlement) in enumerate(zip(turns, settlements, strict=True)):
        require(turn["receipt"]["identity"] == source_identity,
                "source prefix contains a rewritten or foreign receipt")
        require(settlement["state"] == "returned" and settlement["actual_model_calls"] == 1
                and settlement["evidence"]["harness_invocation"]["turn_index"] == index,
                "prefix model call cannot be accounted as one complete original call")
    return dict(prefix_turns=copy.deepcopy(turns), prefix_events=copy.deepcopy(events),
                prefix_settlements=copy.deepcopy(settlements))


def history_structure(turn_index, events, prompt_ids):
    programs = [dict(name=e["name"], program=e["executed_arguments"].get("program"),
                     is_error=e["is_error"], raw_output=copy.deepcopy(e["raw_output"]),
                     visible_output=e["visible_output"])
                for e in events if e["name"] == "run_program"]
    counts = Counter(e["name"] for e in events)
    return dict(source_call_index_zero_based=turn_index, source_call_ordinal=turn_index + 1,
        already_completed_model_calls=turn_index, already_executed_tool_events=len(events),
        is_first_request=turn_index == 0, tool_counts=dict(counts),
        run_program_success_count=sum(not e["is_error"] for e in programs),
        run_program_error_count=sum(e["is_error"] for e in programs),
        had_successful_run_program=any(not e["is_error"] for e in programs),
        had_failed_run_program=any(e["is_error"] for e in programs),
        had_read_source=counts["read_source"] > 0, had_list_sources=counts["list_sources"] > 0,
        executed_programs_and_outputs=programs, prompt_token_count=len(prompt_ids),
        prompt_token_ids_sha256=digest(prompt_ids))


def context_comparison(task, parent, low):
    p, l = parent["history_structure"], low["history_structure"]
    p_programs, l_programs = p["executed_programs_and_outputs"], l["executed_programs_and_outputs"]
    return dict(task_key=task["task_key"], group=task["group"], source_group=task["source_group"],
        hP=p, hL=l,
        executed_program_sequence_identical=[e["program"] for e in p_programs] == [e["program"] for e in l_programs],
        run_program_visible_output_sequence_identical=[e["visible_output"] for e in p_programs] == [e["visible_output"] for e in l_programs],
        programs_and_outputs_identical=p_programs == l_programs,
        all_visible_tool_outputs_identical=[e["visible_output"] for e in parent["prefix_events"]]
            == [e["visible_output"] for e in low["prefix_events"]],
        actual_prompt_tokens_identical=parent["prompt_input_ids"] == low["prompt_input_ids"],
        original_request_values_identical=parent["original_request"] == low["original_request"],
        empty_program_sequences_are_reported_as_empty_not_evidence_of_shared_computation=True)


def _source_history(task, source_model, context, registration, reader):
    matches = [row for row in context["logical_sources"]
        if row["task_key"] == task["task_key"] and row["source_model"] == source_model]
    require(len(matches) == 1, "deduplicated context lacks its unique original source label")
    source = matches[0]
    episode = reader.read_ref(source["episode"], record=False)
    require(f"{episode['dataset']}/{episode['task_id']}" == task["original_task_key"], "source task identity changed")
    index = source["turn_index"]
    original_turn = episode["turns"][index]
    receipt, request = original_turn["receipt"], original_turn["provider_metadata"]["request"]
    require(receipt["identity"] == registration["model_identity"]
        and receipt["request_sha256"] == source["request_sha256"] == digest(request)
        and digest(receipt) == source["receipt_sha256"]
        and context["request"] == request and context["prompt_input_ids"] == receipt["prompt_input_ids"],
        "source request/receipt differs from V73 exact-token input")
    require(request["config"] == episode["config"] == registration["job"]["config"], "source decoding contract changed")
    config = request["config"]
    require((config["max_steps"], config["max_new_tokens"], config["context_limit"], config["temperature"])
            == (32, 2048, 24576, 0.0), "original generation limits changed")
    public_task = json.loads(request["messages"][1]["content"])
    require(digest(public_task) == episode["public_task_sha256"], "historical public task message hash changed")
    require(public_task["task_id"] == episode["task_id"] and public_task["dataset"] == episode["dataset"],
            "historical public task message identity changed")
    prefix = prefix_before(episode, index, registration["model_identity"])
    return dict(source_model=source_model, source_episode=copy.deepcopy(source["episode"]),
        source_turn_index=index, source_provider=copy.deepcopy(episode["provider"]),
        public_task_sha256=episode["public_task_sha256"], public_task=public_task,
        context_id=context["context_id"], original_request=copy.deepcopy(request),
        prompt_input_ids=copy.deepcopy(context["prompt_input_ids"]), config=copy.deepcopy(config),
        source_receipt_sha256=source["receipt_sha256"], source_request_sha256=source["request_sha256"],
        history_structure=history_structure(index, prefix["prefix_events"], context["prompt_input_ids"]), **prefix)


def _first_response(protocol, root, actor, history, reader):
    context_id = history["context_id"]
    jobs = [j for j in protocol["jobs"].values() if j["model"] == actor and context_id in j["context_ids"]]
    require(len(jobs) == 1, "cross response is not uniquely assigned to a V73 job")
    directory = root / "jobs" / jobs[0]["job_id"] / "outputs/generation" / context_id
    result = reader.read(directory / "result.json", record=True)
    returned = reader.read_ref(result["returned"])
    require(Path(result["returned"]["path"]).resolve() == directory / "returned.json", "cross response return escaped V73 operation")
    require(result["protocol_id"] == returned["protocol_id"] == protocol["id"]
        and result["model"] == returned["model"] == returned["value"]["model_label"] == actor
        and result["key"] == returned["key"] == context_id
        and result["kind"] == returned["kind"] == "generation", "cross response coordinate changed")
    turn = returned["value"]["turn"]
    receipt = turn["receipt"]
    require(receipt["identity"] == protocol["model_bindings"][actor]["model_identity"]
        and receipt["prompt_input_ids"] == history["prompt_input_ids"]
        and receipt["request_sha256"] == digest(history["original_request"])
        and turn["provider_metadata"]["request"] == history["original_request"],
        "first response is not the exact registered cross-model call")
    require(hashlib.sha256(turn["raw_text"].encode()).hexdigest() == receipt["raw_response_sha256"]
        == result["raw_response_sha256"] == result["classification"]["raw_response_sha256"]
        and receipt["raw_generated_token_ids"] == result["raw_generated_token_ids"],
        "first response bytes or tokens changed")
    category = result["classification"]["category"]
    require(category in ACTION_ORDER, "V73 cross first response outside fixed three categories")
    return dict(first_turn=copy.deepcopy(turn), classification=copy.deepcopy(result["classification"]),
        first_action_category=category, first_response_returned=reader.ref(directory / "returned.json"),
        first_response_result=reader.ref(directory / "result.json"),
        first_response_raw_sha256=receipt["raw_response_sha256"],
        first_response_token_ids_sha256=digest(receipt["raw_generated_token_ids"]))


def panel_budget(conditions, *, expected=True):
    counts = Counter((r["direction"], r["group"], r["first_action_category"]) for r in conditions)
    if expected:
        require(len(conditions) == 192 and len({r["condition_id"] for r in conditions}) == 192,
                "fixed condition denominator changed")
        actual = {(direction, group): tuple(counts[direction, group, action] for action in ACTION_ORDER)
                  for direction, group in EXPECTED_ACTION_COUNTS}
        require(actual == EXPECTED_ACTION_COUNTS, "V73 first-response category counts changed")
    continuing = [row for row in conditions if row["first_action_category"] == ACTION_ORDER[1]]
    maximum = sum(row["remaining_model_calls"] for row in continuing)
    require(maximum <= 961 and all(row["actor_model"] == "P" for row in continuing),
            "new inference escaped P-only 31-branch conservative budget")
    return dict(unique_tasks=len({r["task_key"] for r in conditions}), conditional_trajectories=len(conditions),
        reused_first_responses=len(conditions), new_first_response_generations=0,
        direct_submit_candidates=sum(r["first_action_category"] == ACTION_ORDER[0] for r in conditions),
        no_tool_call_terminations=sum(r["first_action_category"] == ACTION_ORDER[2] for r in conditions),
        continued_nonterminal_branches=len(continuing), exact_new_model_call_upper_bound=maximum,
        conservative_new_model_call_upper_bound=961,
        per_branch_remaining_call_budget={r["condition_id"]: r["remaining_model_calls"] for r in continuing},
        original_max_steps=32, reused_first_response_counts_as_one_original_budget_call=True,
        new_native_logical_scores=len(conditions), new_NLL=0, new_backward=0, new_optimizer=0,
        new_outer=0, new_class=0, new_VJP=0, external_API_calls=0,
        historical_tool_reconstruction_separately_accounted=True,
        registered_upper_bound_is_not_actual_usage=True)


def prepare_inputs(source_root=None):
    """Return a freeze-ready record; the caller publishes it inside V74 only."""
    root = Path(source_root or b.V73_ROOT).resolve()
    reader = Reader()
    protocol = reader.read(root / "protocol/record.json", record=True)
    require(protocol["id"] == SOURCE_PROTOCOL_ID, "V74 requires the accepted V73 execution revision 02")
    closeout = reader.read(root / "closeout/record.json", record=True)
    require(closeout["status"] == "COMPLETE" and closeout["protocol_id"] == protocol["id"], "V73 did not finish")
    inputs = reader.read_ref(protocol["inputs"])
    selection = reader.read_ref(protocol["selection"])
    require(inputs["selection"]["id"] == selection["id"] and len(selection["selected"]) == 96
        and not inputs["unknown_contexts"] and not inputs["unknown_targets"], "fixed source inputs are incomplete")
    logical = {row["task_key"]: row for row in inputs["logical_rows"]}
    require(set(logical) == {row["task_key"] for row in selection["selected"]}, "fixed selection and logical rows differ")
    registrations = {m: inputs["generation_registrations"][m] for m in ("P", "L")}
    require(all(r["snapshot_id"] == registrations["P"]["snapshot_id"]
        and r["snapshot"] == registrations["P"]["snapshot"] for r in registrations.values()),
        "source models use different public snapshots")
    # Only public rows and the manifest are read. Private references remain for
    # the all-conditions-complete CPU scoring phase.
    snapshot = Path(registrations["P"]["snapshot"])
    manifest = reader.read(snapshot / "manifest.json", record=True)
    require(manifest["id"] == registrations["P"]["snapshot_id"], "public snapshot identity changed")
    raw = (snapshot / "public.jsonl").read_bytes()
    public_sha = hashlib.sha256(raw).hexdigest()
    require(manifest["files"]["public.jsonl"] == dict(sha256=public_sha, bytes=len(raw)), "public snapshot changed")
    reader.sources[str((snapshot / "public.jsonl").resolve())] = dict(path=str((snapshot / "public.jsonl").resolve()), sha256=public_sha)
    chosen = {r["original_task_key"] for r in selection["selected"]}
    public_tasks = {}
    for line in raw.splitlines():
        if line.strip():
            task = json.loads(line)
            key = f"{task['dataset']}/{task['task_id']}"
            if key in chosen:
                require(key not in public_tasks, "duplicate selected public task")
                public_tasks[key] = task
    require(set(public_tasks) == chosen, "selected public tasks missing from original snapshot")
    # Frozen original view conversion requires no model, tokenizer or scorer.
    b.install_scientific_paths()
    contracts = importlib.import_module("trusted_synthesis.finance_research.contracts")
    profiles = importlib.import_module("trusted_synthesis.finance_research.profiles")
    conditions, structures = [], []
    for task in selection["selected"]:
        contexts = logical[task["task_key"]]["contexts"]
        histories = {m: _source_history(task, m, inputs["contexts"][contexts[m]], registrations[m], reader)
                     for m in ("P", "L")}
        original_public = contracts.PublicTask.model_validate(public_tasks[task["original_task_key"]])
        for history in histories.values():
            actual_view = profiles.public_run_view(original_public, history["config"]["submission_profile"]).model_dump(mode="json")
            require(actual_view == history["public_task"], "source request task differs from the original public profile view")
        structures.append(context_comparison(task, histories["P"], histories["L"]))
        for direction, source, actor in DIRECTIONS:
            history = histories[source]
            first = _first_response(protocol, root, actor, history, reader)
            row = dict(condition_id=digest(dict(task_key=task["task_key"], direction=direction)),
                task_key=task["task_key"], original_task_key=task["original_task_key"],
                group=task["group"], source_group=copy.deepcopy(task["source_group"]),
                direction=direction, actor_model=actor,
                actor_identity=copy.deepcopy(protocol["model_bindings"][actor]["model_identity"]),
                **copy.deepcopy(history), **first)
            row["remaining_model_calls"] = residual_budget(row["source_turn_index"], row["first_action_category"])
            row["original_budget_remaining_after_reused_response"] = 32 - row["source_turn_index"] - 1
            conditions.append(row)
    clusters = {group: set(r["source_group"]["group"] for r in selection["selected"] if r["group"] == group)
                for group in ("F", "K")}
    structure_summary = dict(schema="v74_readonly_source_context_structure.v1", rows=structures,
        F_selected_clusters=len(clusters["F"]), K_selected_clusters=len(clusters["K"]),
        shared_F_K_clusters=sorted(clusters["F"] & clusters["K"]),
        shared_F_K_cluster_count=len(clusters["F"] & clusters["K"]),
        union_source_cluster_count=len(clusters["F"] | clusters["K"]),
        actual_prompt_token_identical_count=sum(r["actual_prompt_tokens_identical"] for r in structures),
        programs_and_outputs_identical_count=sum(r["programs_and_outputs_identical"] for r in structures),
        semantic_approximation_used=False, new_model_calls=0, new_tool_executions=0)
    return bound(dict(schema="v74_fixed_cross_history_inputs.v1", source_protocol=reader.ref(root / "protocol/record.json"),
        source_closeout=reader.ref(root / "closeout/record.json"), source_inputs=copy.deepcopy(protocol["inputs"]),
        source_selection=copy.deepcopy(protocol["selection"]), tasks=copy.deepcopy(selection["selected"]),
        conditions=conditions, budget=panel_budget(conditions), context_structure=structure_summary,
        public_tasks=public_tasks, generation_registrations=copy.deepcopy(registrations),
        old_scores={m: copy.deepcopy(inputs["original_source_refs"]["scores"][m]) for m in ("P", "L")},
        model_bindings={m: copy.deepcopy(protocol["model_bindings"][m]) for m in ("P", "L")},
        source_refs=list(reader.sources.values()), original_source_identities_preserved=True,
        source_future_turns_or_final_answers_in_prompts=False, private_references_read=False,
        new_model_calls=0, new_tool_executions=0, new_native_scores=0,
        missing_source_policy="block; never replace, reselect, truncate or invent a history"))
