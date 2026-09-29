"""Prospective serialized-output planning, not a tokenizer or hard size proof.

No provider, wallet, model, file or network is opened. The hypothetical scenario
is never sent as a review or treated as a semantic judgment. Summary and quote
allowances do not add validator maxLength/maxItems or mandatory references.
The caller must check the final complete input wire plus chosen output cap.
"""

import copy
import hashlib
import json

CAPS = (8192, 16384, 32768, 65536)
DIMENSIONS = (
    "evidence_and_operations",
    "observation_interpretation",
    "unwithdrawn_critical_contradictions",
    "actual_revisions",
)
SUMMARY_BYTES_PER_CHECK = 1024
TOOL_ENVELOPE_BYTES = 1024


def _json_bytes(value):
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def _require(value, message):
    if not value:
        raise ValueError("v12_capacity." + message)


def capacity_for(view, catalog, role):
    """Plan using every unit ID in each check and every A target unit/action.

    Four largest JSON-escaped unit strings each populate one check's partial
    evidence scenario. A also budgets a partial quote for every public-content
    unit. These deliberately redundant alternatives reserve bytes, not targets.
    """
    _require(role in {"A", "B"}, "registered_A_or_B_role")
    _require(isinstance(view, dict) and isinstance(catalog, dict), "original_view_and_catalog")
    units, actions = catalog["units"], catalog["actions"]
    segments = {segment["segment_id"]: segment for segment in view["segments"]}
    _require(len(segments) == len(view["segments"]), "unique_original_segments")
    _require(
        isinstance(units, list)
        and len({unit["unit_id"] for unit in units}) == len(units)
        and all(isinstance(unit["unit_id"], str) and unit["unit_id"] for unit in units),
        "unique_original_unit_IDs",
    )
    cursors = dict.fromkeys(segments, 0)
    for unit in units:
        segment_id = unit["segment_id"]
        _require(segment_id in segments, "unit_belongs_to_original_segment")
        segment = segments[segment_id]
        _require(
            isinstance(unit["text"], str)
            and type(unit["start"]) is type(unit["end"]) is int
            and unit["kind"] == segment["kind"]
            and unit["start"] == cursors[segment_id]
            and unit["end"] == unit["start"] + len(unit["text"])
            and segment["text"][unit["start"] : unit["end"]] == unit["text"],
            "unit_text_and_character_coverage_unchanged",
        )
        cursors[segment_id] = unit["end"]
    _require(
        all(cursors[key] == len(segment["text"]) for key, segment in segments.items()),
        "no_original_segment_truncated_or_dropped",
    )
    action_ids = [action["action_id"] for action in actions]
    _require(
        len(set(action_ids)) == len(action_ids)
        and all(isinstance(item, str) and item for item in action_ids)
        and action_ids
        == [action["action_id"] for turn in view["turns"] for action in turn["actions"]],
        "all_real_action_IDs_unchanged",
    )
    ids = [unit["unit_id"] for unit in units]
    public = [unit for unit in units if unit["kind"] == "public_content"]
    baseline = dict(
        process={
            name: dict(
                status="critical_error",
                summary="x" * SUMMARY_BYTES_PER_CHECK,
                evidence_ids=list(ids),
                partial_evidence=[],
            )
            for name in DIMENSIONS
        }
    )
    if role == "A":
        baseline["supervision"] = dict(
            status="complete",
            positive_units=[unit["unit_id"] for unit in public],
            partial_positive_content=[],
            positive_actions=list(action_ids),
        )
    baseline_bytes = len(_json_bytes(baseline))
    scenario = copy.deepcopy(baseline)
    # Python's stable ordering makes equal-size ties retain original unit order.
    longest = sorted(units, key=lambda unit: len(_json_bytes(unit["text"])), reverse=True)[:4]
    for name, unit in zip(DIMENSIONS, longest, strict=False):
        scenario["process"][name]["partial_evidence"] = [
            dict(id=unit["unit_id"], quote=unit["text"])
        ]
    evidence_scenario_bytes = len(_json_bytes(scenario))
    if role == "A":
        scenario["supervision"]["partial_positive_content"] = [
            dict(id=unit["unit_id"], quote=unit["text"]) for unit in public
        ]
    scenario_wire = _json_bytes(scenario)
    planned = len(scenario_wire) + TOOL_ENVELOPE_BYTES
    estimated_tokens = (5 * planned + 3) // 4
    maximum = next((cap for cap in CAPS if cap >= estimated_tokens), None)
    if maximum is None:
        raise ValueError(
            "v12_capacity.planned_output_exceeds_65536: "
            f"role={role}, estimated_tokens={estimated_tokens}, "
            f"scenario_utf8_bytes={len(scenario_wire)}; "
            "no clamp, clipping, omitted package or paid dispatch"
        )
    result = dict(
        schema="v12_serialized_review_capacity.v1",
        role=role,
        source_view_id=view.get("view_id"),
        source_view_sha256=hashlib.sha256(_json_bytes(view)).hexdigest(),
        source_catalog_sha256=hashlib.sha256(_json_bytes(catalog)).hexdigest(),
        units=len(units),
        public_content_units=len(public),
        actual_actions=len(actions),
        process_checks=len(DIMENSIONS),
        summary_utf8_bytes_per_check=SUMMARY_BYTES_PER_CHECK,
        summary_utf8_bytes_total=len(DIMENSIONS) * SUMMARY_BYTES_PER_CHECK,
        whole_unit_scenario_utf8_bytes=baseline_bytes,
        partial_evidence_units=[
            dict(unit_id=unit["unit_id"], json_string_utf8_bytes=len(_json_bytes(unit["text"])))
            for unit in longest
        ],
        partial_evidence_quote_json_utf8_bytes=sum(
            len(_json_bytes(unit["text"])) for unit in longest
        ),
        partial_evidence_added_utf8_bytes=evidence_scenario_bytes - baseline_bytes,
        partial_positive_content_quote_json_utf8_bytes=sum(
            len(_json_bytes(unit["text"])) for unit in public
        )
        if role == "A"
        else 0,
        partial_positive_content_added_utf8_bytes=len(scenario_wire) - evidence_scenario_bytes,
        scenario_utf8_bytes=len(scenario_wire),
        scenario_sha256=hashlib.sha256(scenario_wire).hexdigest(),
        tool_envelope_utf8_bytes=TOOL_ENVELOPE_BYTES,
        total_planning_utf8_bytes_before_multiplier=planned,
        safety_multiplier="5/4",
        estimated_output_tokens=estimated_tokens,
        allowed_max_output_tokens=list(CAPS),
        max_output_tokens=maximum,
        response_token_forecast_exact=False,
        hard_output_size_guarantee=False,
        planning_reference_lists_are_not_mandatory_model_output=True,
        new_summary_or_reference_validator_limits=False,
        original_view_or_catalog_rewritten=False,
        input_or_output_clipping=False,
        private_model_answers_or_old_review_results_used=False,
        final_complete_input_wire_plus_output_cap_check_required=True,
        registered_context_ceiling=1048576,
    )
    return {**result, "id": hashlib.sha256(_json_bytes(result)).hexdigest()}
