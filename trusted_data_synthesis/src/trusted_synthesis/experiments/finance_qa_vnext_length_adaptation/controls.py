"""Finite representation-only corruptions, never new model samples or trajectories."""

from __future__ import annotations

import copy
import json
from typing import Any

from trusted_synthesis.domains.finance.qa_vnext.protocol import ProtocolError

from ..finance_qa_vnext_model_execution.models import require
from .core import (
    ARRAYS,
    assets,
    compare_historical,
    record,
    session_packages,
    validate_condition,
    validate_record,
)
from .source import validate_candidates


def reseal(value: dict[str, Any], kind: str, **changes: Any) -> dict[str, Any]:
    return record(
        kind,
        **{**{k: v for k, v in value.items() if k not in {"id", "schema_version"}}, **changes},
    )


def run_controls(
    source: dict[str, Any],
    condition: dict[str, Any],
    tokens: dict[str, Any],
    tokenizer: Any,
) -> dict[str, Any]:
    results = []

    def rejects(name, function):
        try:
            function()
        except (ProtocolError, assets.TrainingPreflightError) as error:
            results.append(
                {"name": name, "expected": "reject", "observed": "reject", "code": str(error)}
            )
        else:
            raise ProtocolError("length.control_did_not_reject." + name)

    for index, label in ((15, "B01"), (32, "B02")):
        removed = tokens["records"][index]
        subset = reseal(
            tokens,
            "token_dataset",
            records=[item for item in tokens["records"] if item is not removed],
            candidate_count=33,
            fit_count=33,
        )
        packages = session_packages(source, subset)
        affected = next(item for item in packages["rows"] if item["label"] == label)
        require(
            affected["complete"] is False
            and affected["missing_or_nonconsumable_turns"] == [16]
            and affected["expected_units"] == 17
            and affected["consumable_units"] == 16
            and affected["units"][-1]["display_turn"] == 17
            and affected["units"][-1]["consumable"] is True,
            "length.control_incomplete_session",
        )
        results.append(
            {
                "name": label + "_remove_t16_keep_final",
                "expected": "incomplete_package",
                "observed": "incomplete_package",
                "missing_turns": [16],
                "remaining_fit_units": 16,
                "original_denominator": 17,
            }
        )

    for mutation in (
        "target_json_reserialized",
        "future_public_state",
        "cross_session_row",
        "delete_t16",
    ):
        rows = copy.deepcopy(source["dataset"]["rows"])
        if mutation == "target_json_reserialized":
            rows[15]["target_text"] = json.dumps(json.loads(rows[15]["target_text"]), indent=1)
        elif mutation == "future_public_state":
            rows[15]["messages"] = copy.deepcopy(rows[16]["messages"])
        elif mutation == "cross_session_row":
            rows[15]["messages"] = copy.deepcopy(rows[32]["messages"])
        else:
            rows.pop(15)
        rejects(mutation, lambda rows=rows: validate_candidates(source, rows))

    # The two formerly not-fit rows have no old arrays: corrupt their newly
    # encoded arrays and require actual decoding/mask checks to reject them.
    for mutation in (
        "truncate_prompt",
        "omit_target_tail",
        "omit_suffix",
        "do_not_count_suffix",
        "label_prompt",
        "label_suffix",
        "mask_target_tail",
        "wrong_causal_shift",
        "cross_session_token_parent",
    ):
        changed = copy.deepcopy(tokens["records"][15])
        if mutation in {"truncate_prompt", "omit_target_tail", "omit_suffix"}:
            position = {
                "truncate_prompt": 1,
                "omit_target_tail": changed["target_token_end"] - 1,
                "omit_suffix": changed["sequence_length"] - 1,
            }[mutation]
            for name in ARRAYS:
                changed[name].pop(position)
            changed["sequence_length"] -= 1
            if mutation == "truncate_prompt":
                for name in (
                    "prompt_token_count",
                    "target_token_start",
                    "target_token_end",
                    "causal_target_token_start",
                    "causal_target_token_end",
                ):
                    changed[name] -= 1
            elif mutation == "omit_target_tail":
                for name in ("target_token_end", "target_token_count", "causal_target_token_end"):
                    changed[name] -= 1
            else:
                changed["suffix_token_count"] -= 1
        elif mutation == "do_not_count_suffix":
            changed["sequence_length"] -= 2
        elif mutation in {"label_prompt", "label_suffix"}:
            position = 1 if mutation == "label_prompt" else changed["target_token_end"]
            changed["target_mask"][position] = 1
            changed["labels"][position] = changed["input_ids"][position]
        elif mutation == "mask_target_tail":
            position = changed["target_token_end"] - 1
            changed["target_mask"][position] = 0
            changed["labels"][position] = -100
        elif mutation == "wrong_causal_shift":
            changed["causal_shift"] = 0
        else:
            changed["session_id"] = source["sessions"][1]["id"]
        changed = reseal(changed, "token_record")
        rejects(
            mutation,
            lambda changed=changed: validate_record(
                source["dataset"]["rows"][15],
                changed,
                condition,
                source["binding"],
                tokenizer,
            ),
        )

    for resealed in (False, True):
        changed_source = dict(source)
        binding = {**source["binding"], "maximum_sequence_length": 32_768}
        if resealed:
            binding = assets.record(
                "tokenizer_binding",
                **{k: v for k, v in binding.items() if k not in {"id", "schema_version"}},
            )
        changed_source["binding"] = binding
        rejects(
            "rewrite_old_binding_resealed_" + str(resealed),
            lambda source=changed_source: validate_condition(condition, source),
        )

    for field, value in (("maximum_sequence_length", 131_072), ("rope_scaling", {"factor": 4})):
        changed_condition = reseal(condition, "condition", **{field: value})
        rejects(
            "change_new_policy_" + field,
            lambda value=changed_condition: validate_condition(value, source),
        )

    old = copy.deepcopy(source["old_tokens"]["records"][15])
    old["maximum_sequence_length"] = 32_768
    rejects(
        "rewrite_old_not_fit_record_same_id", lambda: compare_historical(old, tokens["records"][15])
    )
    results.append(
        {
            "name": "all_32_old_fit_arrays_and_boundaries_identical",
            "expected": "preserved",
            "observed": "preserved",
            "checked_records": sum(
                compare_historical(old, new)["old_consumable_arrays_existed"]
                for old, new in zip(
                    source["old_tokens"]["records"],
                    tokens["records"],
                    strict=True,
                )
            ),
        }
    )
    return record(
        "controls",
        representation_condition_id=condition["id"],
        rows=results,
        control_count=len(results),
        all_expected_outcomes=True,
        scope="local representation corruptions; not Provider samples or task executions",
    )
