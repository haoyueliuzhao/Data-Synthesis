"""One bounded, read-only pass over saved sessions; never score, repair or generate.

The two populations are separate. Evidence layers overlap and are not mutually
exclusive causes. Repeated-query state is content-addressed public observations,
not a tool-call counter. Call IDs are excluded only from the observation identity;
actual result-reference dependencies are retained for calculation provenance.
"""

# ruff: noqa: E501 -- exact observational definitions and evidence paths

import argparse
import hashlib
import json
import re
import subprocess
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path

BASE = Path("trusted_data_synthesis/artifacts/qa_vnext_fixed_kernel_value")
ORIGINAL = BASE / "parallel_tail_execution_20260914"
HIGHER = BASE / "budget_reevaluation_20260915"
DEFAULT_OUTPUT = BASE / "delivery_diagnostic_20260915/stage_A"
MODELS = tuple(f"A_{arm}_{seed}" for arm in ("alpha0", "plus", "minus") for seed in (11, 29, 47))
MAX_SESSION_BYTES = 64 * 1024 * 1024
MAX_RESPONSE_BYTES = 65536
LONG_STRING_CHARACTERS = 2048


def canonical(value):
    return json.dumps(
        value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False
    )


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def require(condition, code):
    if not condition:
        raise ValueError("delivery_ledger." + code)


def strict_json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, "duplicate_json_key")
            result[key] = value
        return result

    def nonfinite(_):
        raise ValueError("nonfinite_json")

    return json.loads(raw, object_pairs_hook=pairs, parse_constant=nonfinite)


def record(kind, **fields):
    body = {"schema_version": "delivery_diagnostic.v1." + kind, **fields}
    return {**body, "id": kind + ":" + digest(body)}


def read_bound(root, path, maximum):
    require(path.resolve().is_relative_to(root), "input_containment")
    require(not path.is_symlink(), "input_not_symlink")
    before = path.stat()
    require(0 < before.st_size <= maximum, "bounded_input_size")
    raw = path.read_bytes()
    after = path.stat()
    require(
        (before.st_size, before.st_mtime_ns) == (after.st_size, after.st_mtime_ns), "stable_input"
    )
    return strict_json(raw.decode()), {
        "path": str(path.relative_to(root)),
        "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
    }


def write_new(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as handle:
        handle.write(canonical(value) + "\n")


def walk(value):
    yield value
    if isinstance(value, dict):
        for item in value.values():
            yield from walk(item)
    elif isinstance(value, list):
        for item in value:
            yield from walk(item)


def protocol_labels(raw):
    """Diagnostic labels do NOT provide an alternative Final parser to runtime."""
    labels = Counter()
    parsed = None
    try:
        parsed = strict_json(raw)
        labels["strict_json_valid"] += 1
        if isinstance(parsed, dict):
            labels["strict_json_object"] += 1
            labels["canonical_top_level_final"] += int("final" in parsed)
            labels["case_variant_top_level_final"] += int(
                any(k != "final" and k.casefold() == "final" for k in parsed)
            )
        else:
            labels["strict_json_not_object"] += 1
        labels["nested_final_key"] += int(
            any(isinstance(item, dict) and "final" in item for item in list(walk(parsed))[1:])
        )
        longest = max((len(item) for item in walk(parsed) if isinstance(item, str)), default=0)
        labels["long_json_string_heuristic"] += int(longest >= LONG_STRING_CHARACTERS)
    except (ValueError, TypeError, RecursionError):
        labels["strict_json_invalid"] += 1
    labels["raw_final_word_heuristic"] += int(
        re.search(r"\bfinal\b", raw, re.IGNORECASE) is not None
    )
    labels["response_byte_limit_exceeded"] += int(len(raw.encode()) > MAX_RESPONSE_BYTES)
    fenced = re.fullmatch(r"\s*```(?:json)?\s*([\s\S]*?)\s*```\s*", raw, re.IGNORECASE)
    if fenced:
        try:
            inside = strict_json(fenced.group(1))
            labels["code_fenced_final_diagnostic_only"] += int(
                isinstance(inside, dict) and "final" in inside
            )
        except (ValueError, TypeError, RecursionError):
            pass
    return +labels, parsed


def numeric(value):
    if isinstance(value, bool) or value is None or not isinstance(value, (str, int, float)):
        return False
    try:
        return Decimal(str(value)).is_finite()
    except InvalidOperation:
        return False


def public_pointers(value, inherited_source=None):
    """Never join identical pointer strings across different source snapshots."""
    found = set()
    if isinstance(value, dict):
        source = value.get("source_id", inherited_source)
        for key in ("native_pointer", "pointer"):
            pointer = value.get(key)
            if isinstance(source, str) and isinstance(pointer, str):
                found.add((source, pointer))
        for item in value.values():
            found.update(public_pointers(item, source))
    elif isinstance(value, list):
        for item in value:
            found.update(public_pointers(item, inherited_source))
    return found


def analyze_session(session, source_reference, model, population):
    turns, events = session["turns"], session["events"]
    require(len(turns) <= session["max_responses"] <= 64, "response_bound")
    event_by_index = {row["response_index"]: row for row in events}
    require(len(event_by_index) == len(events), "unique_event_steps")
    counts, protocol, errors, finish_reasons = Counter(), Counter(), Counter(), Counter()
    first, response_shas, parsed_shas = {}, [], []
    previous_json_sha, consecutive_json_repeats = None, 0
    evidence = {
        digest(
            {
                "initial_messages": session["initial_messages"],
                "sources": session["source_descriptors"],
            }
        )
    }
    pointers = public_pointers(session["source_descriptors"])
    initial_pointers = set(pointers)
    source_ids = {row["source_id"] for row in session["source_descriptors"]}
    queries, calculations, query_examples, pointer_examples = {}, [], [], []
    nullable_error_examples = []
    supported_numeric_results = set()
    read_result_ids = set()
    mismatch_steps = []

    def saw(label, step):
        counts[label] += 1
        first.setdefault(label, step)

    for expected_index, turn in enumerate(turns):
        index = turn["response_index"]
        require(index == expected_index and index in event_by_index, "sequential_turn_event_join")
        step = index + 1
        raw = turn["raw_response"]
        raw_sha = hashlib.sha256(raw.encode()).hexdigest()
        require(raw_sha == turn["raw_response_sha256"], "response_sha_identity")
        response_shas.append(raw_sha)
        labels, parsed = protocol_labels(raw)
        protocol.update(labels)
        for label in labels:
            first.setdefault(label, step)
        parsed_sha = digest(parsed) if labels["strict_json_valid"] else None
        if parsed_sha is not None:
            parsed_shas.append(parsed_sha)
            consecutive_json_repeats += int(parsed_sha == previous_json_sha)
        previous_json_sha = parsed_sha
        receipt = turn.get("provider_receipt") or {}
        finish_reasons[str(receipt.get("finish_reason", "not_recorded"))] += 1
        event = event_by_index[index]
        if (
            labels["canonical_top_level_final"]
            and not labels["response_byte_limit_exceeded"]
            and not event.get("final")
        ):
            mismatch_steps.append(step)
        if event.get("protocol_error"):
            saw("runtime_protocol_error", step)
            errors["protocol:" + str(event["protocol_error"])] += 1
            evidence.add(digest({"protocol_error": event["protocol_error"]}))
        tool = event.get("tool_call")
        if not tool:
            continue
        name, args = tool["tool"], tool["arguments"]
        saw("tool:" + str(name), step)
        if not isinstance(args, dict):
            args = {}
        result = tool.get("result") or {}
        if not isinstance(result, dict):
            result = {}
        ok = tool.get("status") == "ok"
        if not ok:
            saw("tool_error", step)
            errors[str(name) + ":" + str(tool.get("error", "unspecified"))] += 1
            if name == "query_source" and 'can only concatenate str (not "NoneType") to str' in str(
                tool.get("error", "")
            ):
                saw("query_source_string_concatenation_NoneType_error", step)
                if len(nullable_error_examples) < 1:
                    allowed = {
                        "source_id",
                        "concept",
                        "label_contains",
                        "unit",
                        "start",
                        "end",
                        "offset",
                        "limit",
                    }
                    offset, limit = args.get("offset", 0), args.get("limit", 20)
                    nullable_error_examples.append(
                        {
                            "step": step,
                            "arguments": args,
                            "arguments_match_public_query_shape": set(args) <= allowed
                            and args.get("source_id") in source_ids
                            and type(offset) is int
                            and offset >= 0
                            and type(limit) is int
                            and 1 <= limit <= 20,
                            "source_descriptor": next(
                                (
                                    row
                                    for row in session["source_descriptors"]
                                    if row["source_id"] == args.get("source_id")
                                ),
                                None,
                            ),
                            "observed_error": tool["error"],
                            "mechanism_candidate": "nullable label/description in query substring concatenation; actual snapshot metadata requires separate targeted confirmation",
                        }
                    )
        state_before = digest(sorted(evidence))
        query_key = None
        if name == "query_source":
            if counts["calculate_success_numeric"]:
                saw("query_after_successful_numeric_calculation", step)
            query_key = digest({"source_id": args.get("source_id"), "arguments": args})
            prior = queries.get(query_key)
            if prior is not None:
                saw("query_same_canonical_arguments", step)
                if prior["state_after"] == state_before:
                    saw("query_repeat_without_new_public_evidence", step)
                    if prior["observation_sha256"] == digest(
                        {"status": tool["status"], "result": result, "error": tool.get("error")}
                    ):
                        saw("query_repeat_same_result_without_new_public_evidence", step)
                    if len(query_examples) < 2:
                        query_examples.append(
                            {
                                "previous_step": prior["step"],
                                "step": step,
                                "arguments": args,
                                "arguments_sha256": query_key,
                                "preceding_public_state_sha256": state_before,
                                "previous_post_observation_state_sha256": prior["state_after"],
                            }
                        )
            if ok and bool(result.get("records")):
                saw("query_nonempty_records", step)
                saw("nonempty_discovery_return", step)
            elif ok and result.get("total") == 0 and result.get("records") == []:
                saw("query_success_empty_total_zero", step)
            elif ok:
                saw("query_success_empty_page_or_other", step)
            if ok and any(
                isinstance(row, dict)
                and isinstance(row.get("record"), dict)
                and numeric(row["record"].get("val"))
                for row in result.get("records", [])
            ):
                saw("source_record_value_exposed_in_query", step)
        if name == "list_concepts" and ok and result.get("concepts"):
            saw("list_concepts_nonempty", step)
            saw("nonempty_discovery_return", step)
        if name in {"read_source", "read_json"}:
            source = args.get("source_id")
            pointer = (
                args.get("native_pointer") if name == "read_source" else args.get("pointer", "")
            )
            key = (
                (source, pointer) if isinstance(source, str) and isinstance(pointer, str) else None
            )
            if key is not None and key in pointers - initial_pointers:
                status = "pointer_from_prior_public_return"
            elif key is not None and key in initial_pointers:
                status = "pointer_in_initial_public_descriptor"
            elif name == "read_json" and source in source_ids and pointer == "":
                status = "public_snapshot_root"
            else:
                status = "pointer_not_observed_in_prior_return"
            saw(name + ":" + status, step)
            if len(pointer_examples) < 2:
                pointer_examples.append(
                    {
                        "step": step,
                        "tool": name,
                        "source_id": source,
                        "pointer": pointer,
                        "evidence_class": status,
                        "status": tool["status"],
                    }
                )
            if (
                ok
                and name == "read_source"
                and numeric(result.get("exact_value"))
                and result.get("source_id") == source
                and result.get("native_pointer") == pointer
                and isinstance(result.get("record"), dict)
                and numeric(result["record"].get("val"))
            ):
                saw("successful_source_numeric_read", step)
                read_result_ids.add(tool["call_id"])
                supported_numeric_results.add(tool["call_id"])
            if ok and name == "read_json":
                items = result.get("items", [])
                if items:
                    saw("read_json_nonempty", step)
                    saw("nonempty_discovery_return", step)
                if any(isinstance(item, dict) and numeric(item.get("value")) for item in items):
                    saw("read_json_numeric_scalar_observed", step)
                if any(
                    isinstance(item, dict)
                    and str(item.get("pointer", "")).endswith("/val")
                    and numeric(item.get("value"))
                    for item in items
                ):
                    saw("read_json_record_val_observed", step)
        if name == "calculate":
            variables = args.get("variables", {})
            refs = (
                [
                    v["result_id"]
                    for v in variables.values()
                    if isinstance(v, dict) and isinstance(v.get("result_id"), str)
                ]
                if isinstance(variables, dict)
                else []
            )
            if refs:
                saw("calculate_requested_result_references", step)
            if refs and any(ref in read_result_ids for ref in refs):
                saw("calculate_references_prior_source_read", step)
            actual_refs = result.get("used_result_ids", [])
            source_traceable = bool(actual_refs) and all(
                ref in supported_numeric_results for ref in actual_refs
            )
            if ok and numeric(result.get("exact_value")):
                saw("calculate_success_numeric", step)
                if source_traceable:
                    saw("calculate_success_all_dependencies_source_traceable", step)
                    supported_numeric_results.add(tool["call_id"])
            if len(calculations) < 2:
                calculations.append(
                    {
                        "step": step,
                        "status": tool["status"],
                        "expression": args.get("expression"),
                        "requested_result_ids": refs,
                        "actual_used_result_ids": actual_refs,
                        "exact_value": result.get("exact_value"),
                        "unit": result.get("unit"),
                        "all_dependencies_source_traceable": source_traceable,
                        "requested_physical_quantity_correctness": "NOT_ASSESSED",
                    }
                )
        elif name in {"select_max", "compare", "lookup_selected"} and ok:
            refs = result.get("used_result_ids", [])
            if (
                refs
                and all(ref in supported_numeric_results for ref in refs)
                and numeric(result.get("exact_value"))
            ):
                supported_numeric_results.add(tool["call_id"])
        # A content set changes only for new observable information. The argument
        # binding matters: two snapshots may expose identical-looking pointers.
        evidence.add(
            digest(
                {
                    "tool": name,
                    "arguments": tool["arguments"],
                    "status": tool["status"],
                    "result": tool.get("result"),
                    "error": tool.get("error"),
                }
            )
        )
        if ok:
            pointers.update(public_pointers(result, args.get("source_id")))
        if query_key:
            queries[query_key] = {
                "step": step,
                "state_after": digest(sorted(evidence)),
                "observation_sha256": digest(
                    {"status": tool["status"], "result": result, "error": tool.get("error")}
                ),
            }

    recognized = session["first_final_index"] is not None
    no_discovery = not counts["nonempty_discovery_return"]
    no_read = not (
        counts["successful_source_numeric_read"] or counts["read_json_record_val_observed"]
    )
    no_calculation = not counts["calculate_success_numeric"]
    flags = {
        "runtime_recognized_final": recognized,
        "canonical_final_runtime_mismatch_candidate": bool(mismatch_steps),
        "any_suspicious_final_form": any(
            protocol[label]
            for label in (
                "case_variant_top_level_final",
                "nested_final_key",
                "code_fenced_final_diagnostic_only",
                "raw_final_word_heuristic",
            )
        ),
        "all_responses_strict_json_objects": protocol["strict_json_object"] == len(turns)
        and bool(turns),
        "any_repeated_canonical_json": len(set(parsed_shas)) < len(parsed_shas),
        "any_long_json_string_heuristic": bool(protocol["long_json_string_heuristic"]),
        "list_concepts_called": bool(counts["tool:list_concepts"]),
        "nonempty_query_observed": bool(counts["query_nonempty_records"]),
        "repeat_query_without_new_public_evidence": bool(
            counts["query_repeat_without_new_public_evidence"]
        ),
        "numeric_source_read_observed": not no_read,
        "successful_calculation_observed": not no_calculation,
        "joint_no_discovery_no_numeric_read_no_successful_calculation_no_final": no_discovery
        and no_read
        and no_calculation
        and not recognized,
        "successful_calculation_but_no_final": not no_calculation and not recognized,
        "any_tool_error": bool(counts["tool_error"]),
        "query_source_string_concatenation_NoneType_error_observed": bool(
            counts["query_source_string_concatenation_NoneType_error"]
        ),
        "successful_calculation_then_more_queries_but_no_final": bool(
            counts["query_after_successful_numeric_calculation"]
        )
        and not recognized,
    }
    ledger = record(
        "session_failure_ledger",
        population=population,
        model=model,
        task_id=session["identity"]["task_id"],
        family=session["identity"]["family"],
        source=source_reference,
        runtime_session_id=session["id"],
        responses=len(turns),
        max_responses=session["max_responses"],
        terminal=session["terminal"],
        first_final_index=session["first_final_index"],
        first_observed_step_one_based=first,
        flags=flags,
        protocol_response_counts=dict(protocol),
        observed_counts=dict(counts),
        error_counts=dict(errors),
        finish_reason_counts=dict(finish_reasons),
        unique_raw_response_sha256=len(set(response_shas)),
        canonical_json_consecutive_equal_pairs=consecutive_json_repeats,
        repeated_query_examples=query_examples,
        pointer_examples=pointer_examples,
        calculation_examples=calculations,
        final_runtime_mismatch_steps=mismatch_steps,
        nullable_query_error_examples=nullable_error_examples,
        requested_physical_quantity_correctness="NOT_ASSESSED_NO_GOLD_OR_NEW_SCORING",
        intermediate_correctness_then_continued_query="NOT_ASSESSED",
        observations_not_mutually_exclusive_root_causes=True,
    )
    return ledger, response_shas


def aggregate(ledgers, expected):
    require(len(ledgers) == expected, "exact_population_size")
    fields = ("protocol_response_counts", "observed_counts", "error_counts", "finish_reason_counts")
    totals = {key: Counter() for key in fields}
    flags, terminals, first_nonempty = Counter(), Counter(), Counter()
    for row in ledgers:
        for key in fields:
            totals[key].update(row[key])
        flags.update({key: int(value) for key, value in row["flags"].items()})
        terminals[row["terminal"]] += 1
        step = row["first_observed_step_one_based"].get("query_nonempty_records")
        first_nonempty["not_observed" if step is None else str(step)] += 1
    return {
        "sessions": expected,
        "unique_tasks": len({row["task_id"] for row in ledgers}),
        "responses": sum(row["responses"] for row in ledgers),
        "session_flag_counts_over_separate_population": dict(flags),
        "terminal_counts": dict(terminals),
        "first_nonempty_query_step_histogram": dict(first_nonempty),
        **{key: dict(value) for key, value in totals.items()},
        "labels_overlap_do_not_subtract_as_exclusive_causes": True,
    }


def case_selection(rows):
    selected = []
    for predicate in (
        lambda r: bool(r["final_runtime_mismatch_steps"]),
        lambda r: r["flags"]["query_source_string_concatenation_NoneType_error_observed"],
        lambda r: r["flags"]["successful_calculation_but_no_final"],
        lambda r: r["flags"]["repeat_query_without_new_public_evidence"],
        lambda r: r["flags"]["any_suspicious_final_form"],
        lambda r: r["population"] == "higher_budget_27",
    ):
        candidate = next(
            (r for r in rows if predicate(r) and r["id"] not in {s["ledger_id"] for s in selected}),
            None,
        )
        if candidate:
            selected.append(
                {
                    "ledger_id": candidate["id"],
                    "population": candidate["population"],
                    "model": candidate["model"],
                    "task_id": candidate["task_id"],
                    "runtime_session_source": candidate["source"],
                    "ledger_path": f"sessions/{candidate['population']}/{candidate['model']}/{candidate['task_id']}.json",
                    "flags": candidate["flags"],
                    "first_steps": candidate["first_observed_step_one_based"],
                }
            )
        if len(selected) == 4:
            break
    return selected


def run(root, output):
    root, output = root.resolve(), output.resolve()
    require(
        output.is_relative_to(root / BASE / "delivery_diagnostic_20260915"),
        "new_diagnostic_output_only",
    )
    require(not output.exists(), "single_invocation_no_output_overwrite")
    # Metadata enumeration does not open any runtime or callback content.
    paths = {}
    for population, generation, expected_each in (
        ("original_1620", root / ORIGINAL / "generation/dev", 180),
        ("higher_budget_27", root / HIGHER / "pilot/generation", 3),
    ):
        paths[population] = []
        for model in MODELS:
            sessions = sorted((generation / model / "sessions").glob("*/runtime_session.json"))
            require(len(sessions) == expected_each, "fixed_model_session_count")
            paths[population].extend((model, path) for path in sessions)
    pilot_keys = {(model, path.parent.name) for model, path in paths["higher_budget_27"]}
    require(
        len(pilot_keys) == 27 and len({task for _, task in pilot_keys}) == 3, "fixed_pilot_pairs"
    )
    output.mkdir(parents=True)
    code_sha = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    started = record(
        "scan_started",
        started_at=datetime.now(timezone.utc).isoformat(),
        code_commit=commit,
        script_sha256=code_sha,
        exact_session_reads=1647,
        callback_files_to_read=0,
        no_model_or_api_calls=True,
        no_rescoring=True,
        input_populations_separate=True,
    )
    write_new(output / "started.json", started)
    rows, selected_shas, pairs = [], {}, []
    population_summaries = {}
    for population in ("original_1620", "higher_budget_27"):
        population_rows = []
        for model, path in paths[population]:
            session, reference = read_bound(root, path, MAX_SESSION_BYTES)
            require(session["identity"]["task_id"] == path.parent.name, "session_path_task_join")
            ledger, response_shas = analyze_session(session, reference, model, population)
            write_new(
                output / "sessions" / population / model / (ledger["task_id"] + ".json"), ledger
            )
            population_rows.append(ledger)
            key = (model, ledger["task_id"])
            if population == "original_1620" and key in pilot_keys:
                selected_shas[key] = (response_shas, reference)
            elif population == "higher_budget_27":
                old_shas, old_source = selected_shas[key]
                compared = min(32, len(old_shas), len(response_shas))
                mismatches = [i + 1 for i in range(compared) if old_shas[i] != response_shas[i]]
                pairs.append(
                    {
                        "model": model,
                        "task_id": key[1],
                        "original_source": old_source,
                        "higher_budget_source": reference,
                        "requested_prefix_responses": 32,
                        "compared_responses": compared,
                        "original_prefix_sha256": old_shas[:32],
                        "higher_budget_prefix_sha256": response_shas[:32],
                        "mismatch_steps_one_based": mismatches,
                        "all_first_32_raw_response_bytes_identical": compared == 32
                        and not mismatches,
                    }
                )
        population_summaries[population] = aggregate(
            population_rows, 1620 if population == "original_1620" else 27
        )
        rows.extend(population_rows)
    require(len(pairs) == 27, "paired_sha_count")
    # Reuse existing summary numbers verbatim, without callback / token rescans.
    resources = []
    for relative in (ORIGINAL / "report.json", HIGHER / "comparison.json"):
        existing, reference = read_bound(root, root / relative, 8 * 1024 * 1024)
        resources.append(
            {
                "source": reference,
                "record_id": existing.get("id"),
                "existing_resource_usage": existing.get("resource_usage"),
                "original_pilot_resource_usage": existing.get("old_budget", {}).get(
                    "resource_usage"
                ),
                "higher_budget_resource_usage": existing.get("higher_budget", {}).get(
                    "resource_usage"
                ),
                "unavailable_fields_left_null_not_recomputed": True,
            }
        )
    report = record(
        "failure_location_report",
        started_id=started["id"],
        status="COMPLETE_BOUNDED_OBSERVATIONAL_SCAN",
        finished_at=datetime.now(timezone.utc).isoformat(),
        populations=population_summaries,
        paired_prefix={
            "pairs": len(pairs),
            "fully_identical_first_32": sum(
                row["all_first_32_raw_response_bytes_identical"] for row in pairs
            ),
            "comparisons": pairs,
        },
        cases=case_selection(rows),
        existing_resources=resources,
        methodology={
            "step_index": "one-based; original runtime first_final_index remains zero-based",
            "query_repeat": "same canonical arguments and same source; public evidence content-set immediately before this query equals after preceding identical query; changing call IDs excluded, not changing facts",
            "public_state": "initial messages plus source descriptors and distinct complete observed tool/protocol outcomes; source arguments preserved; never merely number of calls",
            "pointer_evidence": "exact (source_id, pointer) from earlier successful public tool return; initial descriptors and public root are separate categories; unobserved does not prove fabricated",
            "numeric_evidence": "read_source actual record.val/exact_value or read_json /val; query-exposed val separately recorded; not assessed as the required financial amount",
            "calculation_evidence": "saved runtime success plus numeric value; all actual used_result_ids must reach prior numeric source reads for source-traceable label; no question correctness judgment",
            "final": "runtime recognized Final is authoritative; strict top-level lowercase final and suspicious text/case/fences are separate observational labels; no JSON repair or final supplementation",
            "loop": "repeated identical canonical JSON and same-query/public-state recurrence are observations, not a diagnosis of hidden reasoning",
            "long_string": f"heuristic >= {LONG_STRING_CHARACTERS} characters in a parsed JSON string; does not establish token truncation",
            "root_cause": "overlapping evidence layers and joint paths; not mutually exclusive or proven causal explanations",
        },
        new_financial_scores_created=False,
        callback_files_read=0,
        implementation_defect_scope={
            "canonical_Final_runtime_mismatch_candidate_sessions": {
                key: value["session_flag_counts_over_separate_population"].get(
                    "canonical_final_runtime_mismatch_candidate", 0
                )
                for key, value in population_summaries.items()
            },
            "query_NoneType_error_observed_sessions": {
                key: value["session_flag_counts_over_separate_population"].get(
                    "query_source_string_concatenation_NoneType_error_observed", 0
                )
                for key, value in population_summaries.items()
            },
            "sufficient_to_explain_all_no_Final": "NOT_ESTABLISHED_BY_OBSERVATIONAL_SCAN",
            "causal_limit": "An observed query defect affects its recorded subset; neither that subset nor all no-Final sessions can be attributed solely to this defect without an intervention. Direct parser mismatch candidates require targeted source/event review before repair.",
        },
        original_results_modified=False,
        observations_not_new_training_value_evidence=True,
    )
    write_new(output / "report.json", report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    root = args.root.resolve()
    output = args.output if args.output.is_absolute() else root / args.output
    report = run(root, output)
    print(canonical({"report_id": report["id"], "status": report["status"], "output": str(output)}))


if __name__ == "__main__":
    main()
