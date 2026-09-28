"""Tri-state read-only observations for original G2 records, never a new gate.

The exact registered outcome is retained even if an independently checked local
reference succeeded. This module does not sample, execute tools, or rescore QA.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from .contracts import digest
from .gpu_gate_v2 import _visible_results


def eligible_references(event):
    args = event["normalized_arguments"]
    if event["name"] == "calculate":
        root = ("variables",)
        value = args.get("variables", {})
    elif event["name"] == "final_answer":
        root = ("answer",)
        value = args.get("answer")
    else:
        root, value = (), args

    def walk(node, path):
        if isinstance(node, dict):
            for key, child in node.items():
                yield from walk(child, (*path, key))
        elif isinstance(node, list):
            for key, child in enumerate(node):
                yield from walk(child, (*path, key))
        elif isinstance(node, str) and node.startswith("prev:"):
            yield path, node

    return list(walk(value, root))


def lookup(value, parts):
    for part in parts:
        if isinstance(value, list):
            if not str(part).isdecimal() or int(part) >= len(value):
                raise ValueError("not a real list path")
            value = value[int(part)]
        elif isinstance(value, dict) and part in value:
            value = value[part]
        else:
            raise ValueError("not a real output path")
    return value


def diagnose_episode(episode, tokenizer, *, exact_registered_chain_match, numerical_replay_passed):
    """Inspect the original input IDs and normalized actual action fields."""
    report = dict(
        schema="finance_G2_observation_diagnostic.v3",
        episode_sha256=digest(episode),
        exact_registered_chain_match=bool(exact_registered_chain_match),
        observation_checked=False,
        prev_reference_used=None,
        visible_handle_verified=None,
        numerical_replay_passed=bool(numerical_replay_passed),
        definition=dict(
            prev_reference_used="at least one actually successful, value-checked dereference",
            visible_handle_verified="all checked preceding tool envelopes occur in original inputs",
            null="not checked or no corresponding observation; never shorthand for false",
        ),
        source_records_overwritten=False,
        new_model_calls=0,
    )
    prior, successful, observed, visibility = [], {}, [], []
    cursor = 0
    try:
        for turn_index, turn in enumerate(episode["turns"]):
            receipt = turn.get("receipt")
            if receipt is None:
                raise ValueError("actual local token receipt required")
            ids = receipt["prompt_input_ids"]
            decoded = tokenizer.decode(
                ids, skip_special_tokens=False, clean_up_tokenization_spaces=False
            )
            if tokenizer(decoded, add_special_tokens=False)["input_ids"] != ids:
                raise ValueError("original prompt token roundtrip differs")
            visible = _visible_results(decoded)
            for event in prior:
                envelope = json.loads(event["visible_output"])
                verified = envelope in visible
                visibility.append(
                    dict(turn_index=turn_index, handle=event["result_handle"], verified=verified)
                )
            calls = turn["tool_calls"]
            if len(calls) != 1:
                continue
            if cursor >= len(episode["tool_events"]):
                raise ValueError("parsed tool action has no execution event")
            event = episode["tool_events"][cursor]
            cursor += 1
            if event["call_id"] != calls[0]["call_id"]:
                raise ValueError("tool action order changed")
            for path, text in eligible_references(event):
                match = re.fullmatch(r"prev:(r[1-9][0-9]*)\.(output\..+)", text)
                resolved = False
                if not event["is_error"] and match and match[1] in successful:
                    source = successful[match[1]]
                    expected = lookup(source, match[2].split("."))
                    resolved = expected == lookup(event["executed_arguments"], path)
                observed.append(
                    dict(
                        turn_index=turn_index,
                        tool=event["name"],
                        reference=text,
                        successful_value_verified=resolved,
                        event_is_error=event["is_error"],
                    )
                )
            prior.append(event)
            if not event["is_error"]:
                successful[event["result_handle"]] = json.loads(event["visible_output"])
        if cursor != len(episode["tool_events"]):
            raise ValueError("unmatched execution events")
        report.update(
            observation_checked=True,
            prev_reference_used=any(row["successful_value_verified"] for row in observed),
            visible_handle_verified=all(row["verified"] for row in visibility)
            if visibility
            else None,
            visibility_observation_checked=bool(visibility),
            reference_observations=observed,
            visibility_observations=visibility,
            original_prompt_token_roundtrips_verified=len(episode["turns"]),
        )
    except (KeyError, ValueError, TypeError, IndexError) as error:
        report["observation_error"] = {"type": type(error).__name__, "message": str(error)}
    return report


def derive_existing_gate(run_root, tokenizer):
    run_root = Path(run_root)
    gate = json.loads((run_root / "gate_complete/record.json").read_bytes())
    rows = []
    for case in gate["cases"]:
        path = run_root / "gate/cases" / f"{case['index']:02d}" / "generation/record.json"
        episode = json.loads(path.read_bytes())["episode"]
        rows.append(
            {
                "index": case["index"],
                "point": case["point"],
                "kind": case["kind"],
                **diagnose_episode(
                    episode,
                    tokenizer,
                    exact_registered_chain_match=case["reference_chain"]["passed"],
                    numerical_replay_passed=case["feedback_replay_passed"],
                ),
            }
        )
    return dict(
        schema="finance_G2_existing_record_addendum.v1",
        source_gate_sha256=digest(gate),
        exact_registered_passes=sum(x["exact_registered_chain_match"] for x in rows),
        cases=rows,
        new_model_calls=0,
        original_results_overwritten=False,
    )
