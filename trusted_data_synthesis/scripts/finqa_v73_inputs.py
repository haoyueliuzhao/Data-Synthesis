"""Fixed V73 conditional samples and byte-bound historical inference inputs.

This module never loads a language model, executes a tool, or scores an answer.
Selection must be published before ``materialize_contexts`` opens raw episodes.
"""
from __future__ import annotations

import copy
import hashlib
import importlib
import json
from collections import Counter, defaultdict
from functools import lru_cache
from pathlib import Path

import finqa_v73_binding as binding

require, digest = binding.require, binding.digest
SELECTION_SALT = "finqa-v73-same-context-20261025-v1"
MODEL_ORDER = ("P", "H", "L")


def _bound(body):
    body = {k: v for k, v in body.items() if k != "id"}
    return dict(body, id=digest(body))


def native_state(row):
    value = row["native"]
    if value["status"] == "unknown":
        return "UNKNOWN"
    if value["status"] == "invalid_prediction":
        require(value["program_executable"] is False, "contradictory invalid native state")
        return "I"
    require(value["status"] == "scored" and value["program_executable"] is True,
            "unrecognized sealed native state")
    score = value["native"]["execution_accuracy"]
    require(score in (0, 1), "native EA must be known binary")
    return "R" if score == 1 else "W"


def load_sources():
    """Read small sealed selection metadata, without opening an episode."""
    final_path = binding.V72_ROOT / "evaluations/final_summary/record.json"
    final = binding.checked(final_path)
    require(final["status"] == "COMPLETE", "V72 must have completed")
    refs = dict(P=final["model_reports"]["step1192.dev_greedy"],
                H=final["HighLR"]["model_reports"]["step1490.dev_greedy"],
                L=final["model_reports"]["step1490.dev_greedy"])
    scores = {name: binding.read_ref(ref) for name, ref in refs.items()}
    invalid_ref = final["failure_mechanisms"]
    invalid = binding.read_ref(invalid_ref)
    registrations, roots, registration_refs = {}, {}, {}
    for name in MODEL_ORDER:
        job_root = Path(refs[name]["path"]).parent.parent
        path = job_root / "registration/record.json"
        registrations[name] = binding.checked(path)
        registration_refs[name] = binding.entry(path)
        roots[name] = str(job_root / "shards" / registrations[name]["job"]["panel"] / "generation")
    return dict(scores=scores, invalid=invalid, registrations=registrations,
                generation_roots=roots, source_refs=dict(final_summary=binding.entry(final_path),
                    scores=refs, failure_mechanisms=invalid_ref, registrations=registration_refs))


def load_tokenizer(registrations):
    """Load only the shared frozen CPU tokenizer, never a language model."""
    assets = registrations["P"]["assets"]
    require(all(registrations[name]["assets"] == assets for name in MODEL_ORDER),
            "P/H/L tokenizer or base assets differ")
    binding.install_scientific_paths()
    base = importlib.import_module("trusted_synthesis.finance_research.v7_base_evaluation")
    providers = importlib.import_module("trusted_synthesis.finance_research.providers")
    tokenizer = base.load_tokenizer(assets)
    tokens, template = providers.tokenizer_binding(tokenizer)
    require(all((registrations[name]["model_identity"]["tokenizer_digest"],
                 registrations[name]["model_identity"]["chat_template_digest"]) == (tokens, template)
                for name in MODEL_ORDER), "shared CPU tokenizer identity differs from old generation")
    return tokenizer


def _rows(score):
    rows = {row["task_key"]: row for row in score["results"]}
    require(len(rows) == len(score["results"]) == score["denominator"],
            "native panel has missing or duplicate task keys")
    require(score["status"] == "COMPLETE", "selection needs sealed complete scores")
    return rows


def round_robin_sample(candidates, *, salt, group, count):
    """Hash-order clusters and full task IDs; take one per live cluster per pass."""
    clusters = defaultdict(list)
    for row in candidates:
        clusters[row["source_group"]["group"]].append(row)
    for cluster, rows in clusters.items():
        rows.sort(key=lambda r: (digest([salt, group, "task", r["task_key"]]), r["task_key"]))
    cluster_order = sorted(clusters, key=lambda c: (digest([salt, group, "cluster", c]), c))
    selected = []
    depth = 0
    while len(selected) < count:
        before = len(selected)
        for cluster in cluster_order:
            if depth < len(clusters[cluster]):
                selected.append(clusters[cluster][depth])
                if len(selected) == count:
                    break
        require(len(selected) > before, "insufficient conditional candidate population")
        depth += 1
    return selected, cluster_order


def select_samples(parent_scores, high_scores, low_scores, invalid, *,
                   salt=SELECTION_SALT, per_group=48, expected_counts=None):
    """Select from old outcomes only. No request/episode is read here."""
    if expected_counts is None and per_group == 48:
        expected_counts = dict(F=125, K=380)
    scores = {name: _rows(score) for name, score in
              zip(MODEL_ORDER, (parent_scores, high_scores, low_scores), strict=True)}
    keys = set(scores["P"])
    require(all(set(rows) == keys for rows in scores.values()), "P/H/L task panels differ")
    labels = {row["task_key"]: row for row in invalid["low_lr_rows"]}
    require(len(labels) == len(invalid["low_lr_rows"]), "duplicate low-LR failure labels")
    populations = dict(F=[], K=[])
    for key in sorted(keys):
        states = {name: native_state(rows[key]) for name, rows in scores.items()}
        require("UNKNOWN" not in states.values(), "old native UNKNOWN cannot enter a known panel")
        cluster = scores["P"][key]["source_group"]
        require(cluster["level"] != "unknown" and cluster["group"], "source cluster is unknown")
        require(all(rows[key]["source_group"] == cluster for rows in scores.values()),
                "historical source group changed between models")
        if states["P"] != "R":
            continue
        group = None
        if states["L"] == "R":
            group = "K"  # Deliberately independent of H's correctness.
        elif states["L"] == "I":
            require(key in labels, "selected native invalid lacks its frozen classification")
            label = labels[key]
            require(label["from_parent1192"] == "R", "failure classification parent state mismatch")
            if (label["terminal_category"], label["stop_reason"]) == ("missing_terminal_submission", "no_tool_call"):
                group = "F"
        if group:
            populations[group].append(dict(task_key=key, group=group,
                original_task_key=scores["P"][key]["original_task_key"],
                source_group=copy.deepcopy(cluster), old_states=states))
    if expected_counts is not None:
        require({g: len(rows) for g, rows in populations.items()} == expected_counts,
                "F125/K380 conditional populations changed")
    selected, orders = [], {}
    for group in ("F", "K"):
        rows, orders[group] = round_robin_sample(populations[group], salt=salt,
                                               group=group, count=per_group)
        selected.extend(rows)
    require(len({r["task_key"] for r in selected}) == 2 * per_group, "conditional groups overlap")
    return _bound(dict(schema="v73_fixed_conditional_selection.v1", salt=salt,
        rule="hash(salt,group,cluster) order; hash(salt,group,full task_key) within cluster; round robin",
        expected_counts=expected_counts, per_group=per_group, unique_tasks=len(selected),
        candidate_counts={g: len(v) for g, v in populations.items()}, candidates=populations,
        cluster_order=orders, selected=selected,
        source_distributions={g: dict(candidate=dict(Counter(r["source_group"]["group"] for r in populations[g])),
            selected=dict(Counter(r["source_group"]["group"] for r in selected if r["group"] == g))) for g in ("F", "K")},
        H_outcome_is_not_a_selection_condition=True, new_scores_or_models_used=False,
        population_prevalence_estimate=False, replacement_after_missing_context=False))


class Reader:
    def __init__(self):
        self.sources = {}

    def read(self, path, *, expected_sha=None, record=False):
        path = Path(path).resolve()
        raw = path.read_bytes()
        actual_sha = hashlib.sha256(raw).hexdigest()
        require(expected_sha is None or actual_sha == expected_sha, "historical bytes changed: " + str(path))
        value = json.loads(raw)
        if record:
            require(value.get("id") == digest({k: v for k, v in value.items() if k != "id"}),
                    "historical record ID changed: " + str(path))
        self.sources[str(path)] = dict(path=str(path), sha256=actual_sha,
                                      **({"id": value["id"]} if record else {}))
        return value


def _generation_index(root, registration, reader):
    root = Path(root).resolve()
    run = reader.read(root / "run.json", record=True)
    seal = reader.read(root / "generation_seal/seal.json", record=True)
    require(seal["complete"] and seal["all_provider_calls_settled"]
            and seal["run_id"] == run["id"] and run["provider"] == registration["model_identity"]
            and run["config"] == registration["job"]["config"]
            and len(run["tasks"]) == len(run["episode_keys"]) == seal["registered_denominator"]
            and [r["key"] for r in seal["episodes"]] == run["episode_keys"],
            "historical generation index, model identity or seal changed")
    require(len(set(run["tasks"])) == len(run["tasks"]), "duplicate original task index")
    return {task: dict(row, root=str(root)) for task, row in zip(run["tasks"], seal["episodes"], strict=True)}


def parent_submit_index(episode):
    """Locate the actual accepted submit event, not a prose mention or last turn."""
    successful = {event["call_id"]: event for event in episode["tool_events"]
                  if event["name"] == "submit_program" and event["is_error"] is False
                  and isinstance(event["raw_output"], dict) and event["raw_output"].get("submitted") is True}
    indices = []
    for index, turn in enumerate(episode["turns"]):
        calls = turn["tool_calls"]
        if len(calls) == 1 and calls[0]["name"] == "submit_program" and calls[0]["call_id"] in successful:
            require(calls[0]["arguments"].get("program") == episode["final_program"]
                    == successful[calls[0]["call_id"]]["raw_output"].get("program"),
                    "accepted parent submission and final program differ")
            indices.append(index)
    require(len(indices) == 1, "parent needs exactly one actual successful submit turn")
    return indices[0]


@lru_cache(maxsize=1)
def _tool_spec_factory():
    binding.install_scientific_paths()
    module = importlib.import_module("trusted_synthesis.finance_research.v6_task")
    return module.public_reasoning_tool_specs


def _original_tool_specs():
    return _tool_spec_factory()()


def restore_request_tool_order(request):
    """Restore only the original native-template schema insertion order.

    Historical JSON records sort keys, while Qwen's tools|tojson renderer uses
    insertion order. The frozen original factory supplies that lost order, but
    no value may differ from the actual saved tools. Render SHA and receipt IDs
    are still checked afterwards. Call again after JSON reload, including just
    before the actual provider call; persisting a dict does not retain order.
    """
    original_tools = _original_tool_specs()
    require(request["tools"] == original_tools and digest(request["tools"]) == digest(original_tools),
            "saved tool values differ from the original frozen factory; cannot restore order")
    restored = copy.deepcopy(request)
    restored["tools"] = original_tools
    require(digest(restored) == digest(request), "tool order restoration changed request values")
    return restored


def verify_turn(turn, registration, tokenizer):
    """Render exactly the saved public request and compare every actual token."""
    receipt = turn["receipt"]
    request = copy.deepcopy(turn["provider_metadata"]["request"])
    require(receipt is not None and receipt["identity"] == registration["model_identity"],
            "turn receipt is missing or belongs to another model")
    require(request["config"] == registration["job"]["config"]
            and request["tool_protocol"] == "qwen2.5-native-tool-call-v1"
            and request["template_tools_kwarg_used"] is True,
            "original request config or native tool template differs")
    require(digest(request) == receipt["request_sha256"], "original request hash changed")
    request = restore_request_tool_order(request)
    rendered = tokenizer.apply_chat_template(request["messages"], tools=request["tools"],
        tokenize=False, add_generation_prompt=True)
    require(hashlib.sha256(rendered.encode()).hexdigest() == request["rendered_prompt_sha256"],
            "saved request no longer renders to the original prompt bytes")
    prompt = list(tokenizer(rendered, add_special_tokens=False, truncation=False, padding=False)["input_ids"])
    require(prompt and prompt == receipt["prompt_input_ids"], "reconstructed prompt token IDs differ")
    require(len(prompt) + request["config"]["max_new_tokens"] <= request["config"]["context_limit"],
            "registered original context exceeds the generation reservation")
    output = receipt["raw_generated_token_ids"]
    require(output and len(output) <= request["config"]["max_new_tokens"], "missing original response token sequence")
    eos_ids = receipt["sampling"]["eos_token_ids"]
    require((output[-1] in eos_ids) == receipt["actual_eos"], "original actual EOS contradicts saved IDs")
    decoded = tokenizer.decode(output[:-1] if receipt["actual_eos"] else output,
        skip_special_tokens=False, clean_up_tokenization_spaces=False)
    require(decoded == turn["raw_text"]
            and hashlib.sha256(decoded.encode()).hexdigest() == receipt["raw_response_sha256"],
            "original generated token decoding or response SHA differs")
    require(turn["finish_reason"] == receipt["finish_reason"], "saved finish reason contradicts receipt")
    return request, prompt, receipt


def context_identity(prompt, request, model_identity):
    """Exact rendered-input equivalence; old current-response tokens are excluded."""
    return digest(dict(prompt_input_ids=prompt, tools=request["tools"], config=request["config"],
        tokenizer_digest=model_identity["tokenizer_digest"], chat_template_digest=model_identity["chat_template_digest"]))


def materialize_contexts(selection, registrations, tokenizer, *, generation_roots):
    """Open selected old episodes only; missing/unverifiable slots remain UNKNOWN.

    Callers must durably publish ``selection`` before this function. Generation
    contexts and teacher-forced targets are separate channels. Unknown slots never
    remove a selected task or cause replacement sampling.
    """
    require(selection["id"] == digest({k: v for k, v in selection.items() if k != "id"}),
            "selection changed after it was fixed")
    reader = Reader()
    indices, index_failures = {}, {}
    for model in MODEL_ORDER:
        try:
            indices[model] = _generation_index(generation_roots[model], registrations[model], reader)
        except (OSError, ValueError, KeyError, TypeError) as error:
            index_failures[model] = dict(exception=type(error).__name__, reason=str(error))
    contexts, targets, rows, unknown, unknown_targets = {}, {}, [], [], []
    for chosen in selection["selected"]:
        task_key, group = chosen["task_key"], chosen["group"]
        logical = dict(task_key=task_key, group=group, source_group=chosen["source_group"],
                       contexts={name: None for name in MODEL_ORDER}, source_responses={})
        for model in MODEL_ORDER:
            try:
                require(model not in index_failures, "source index unavailable: " + str(index_failures.get(model)))
                reference = indices[model][chosen["original_task_key"]]
                root = Path(reference["root"])
                path = (root / reference["path"]).resolve()
                require(path.is_relative_to(root / "episodes"), "historical episode escaped its root")
                episode = reader.read(path, expected_sha=reference["sha256"])
                require(f"{episode['dataset']}/{episode['task_id']}" == chosen["original_task_key"]
                        and episode["all_provider_calls_settled"] is True and episode["turns"],
                        "selected historical task is incomplete or different")
                turn_index = parent_submit_index(episode) if model == "P" else len(episode["turns"]) - 1
                turn = episode["turns"][turn_index]
                request, prompt, receipt = verify_turn(turn, registrations[model], tokenizer)
                context_id = context_identity(prompt, request, registrations[model]["model_identity"])
                source = dict(task_key=task_key, group=group, source_model=model, turn_index=turn_index,
                    episode=reader.sources[str(path)], request_sha256=receipt["request_sha256"],
                    receipt_sha256=digest(receipt), raw_response_sha256=receipt["raw_response_sha256"])
                if context_id not in contexts:
                    contexts[context_id] = dict(context_id=context_id, request=request, prompt_input_ids=prompt,
                        logical_sources=[], source_receipts=[], canonical_source=source,
                        tokenizer_digest=registrations[model]["model_identity"]["tokenizer_digest"],
                        chat_template_digest=registrations[model]["model_identity"]["chat_template_digest"])
                contexts[context_id]["logical_sources"].append(source)
                contexts[context_id]["source_receipts"].append(dict(episode=source["episode"],
                    turn_index=turn_index, receipt_sha256=source["receipt_sha256"],
                    request_sha256=receipt["request_sha256"]))
                logical["contexts"][model] = context_id
                logical["source_responses"][model] = dict(raw_response_sha256=receipt["raw_response_sha256"],
                    response_ids_sha256=digest(receipt["raw_generated_token_ids"]),
                    actual_eos=receipt["actual_eos"], finish_reason=receipt["finish_reason"],
                    response_token_count=len(receipt["raw_generated_token_ids"]))
                if model == "P":
                    target = dict(task_key=task_key, group=group, parent_context_id=context_id,
                        request=request, prompt_input_ids=prompt, tools=request["tools"],
                        raw_generated_token_ids=receipt["raw_generated_token_ids"], raw_text=turn["raw_text"],
                        actual_eos=receipt["actual_eos"], eos_token_ids=receipt["sampling"]["eos_token_ids"],
                        receipt=receipt, source_episode=reader.sources[str(path)], turn_index=turn_index)
                    targets[task_key] = dict(target, target_id=digest(target))
            except (OSError, ValueError, KeyError, TypeError, IndexError) as error:
                failure = dict(task_key=task_key, group=group, source_model=model, status="UNKNOWN",
                    exception=type(error).__name__, reason=str(error), replacement=False)
                unknown.append(failure)
                if model == "P":
                    unknown_targets.append(dict(failure, target_channel="fixed_parent_response"))
        rows.append(logical)
    require(len(rows) == selection["unique_tasks"], "missing-context handling changed task denominator")
    known_slots = sum(value is not None for row in rows for value in row["contexts"].values())
    return _bound(dict(schema="v73_exact_historical_inputs.v1", selection_id=selection["id"],
        contexts=contexts, targets=targets, logical_rows=rows, unknown_contexts=unknown,
        unknown_targets=unknown_targets, source_refs=list(reader.sources.values()),
        dedup=dict(key="prompt_input_ids + tools + config + tokenizer_digest + chat_template_digest",
            canonical_representative="first selected task in F then K order, source P then H then L",
            logical_context_slots=3 * selection["unique_tasks"], known_context_slots=known_slots,
            unique_contexts=len(contexts), merged_known_slots=known_slots - len(contexts),
            logical_generation_slots=9 * selection["unique_tasks"],
            planned_unique_generation_calls=3 * len(contexts), planned_probability_sequences=3 * len(targets)),
        private_references_read=False, new_model_calls=0, new_tool_executions=0, new_native_scores=0,
        parent_current_response_only_in_probability_channel=True, missing_slots_never_dropped=True))
