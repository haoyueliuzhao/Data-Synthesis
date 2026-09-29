"""Only CPU synthetic serialization; no model, tokenizer, wallet or files."""

import copy
import json

import pytest

from trusted_synthesis.finance_research import v12_review_capacity as capacity


def fixture(texts=None, *, count=5):
    texts = texts or ["plain", 'quote " and slash \\ and tab\t', "汉字🙂", "\x00" * 4, "x" * 10]
    if count != 5:
        texts = ["x"] * count
    segments, units = [], []
    for index, text in enumerate(texts):
        kind = "public_content" if index % 2 else "source_text"
        segment_id = f"segment:{index}"
        segments.append(dict(segment_id=segment_id, kind=kind, text=text))
        units.append(
            dict(
                unit_id=f"u{index:05d}",
                segment_id=segment_id,
                kind=kind,
                start=0,
                end=len(text),
                text=text,
            )
        )
    actions = [dict(action_id="actual_original_action_identifier:not_shortened")]
    return dict(
        view_id="view:synthetic", segments=segments, turns=[dict(actions=copy.deepcopy(actions))]
    ), dict(units=units, actions=actions, events=[])


def encode(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def test_role_scenarios_exact_UTF8_escaping_overhead_and_unmodified_inputs():
    view, catalog = fixture()
    before = copy.deepcopy((view, catalog))
    values = {role: capacity.capacity_for(view, catalog, role) for role in ("A", "B")}
    for role, result in values.items():
        baseline = {
            "process": {
                name: dict(
                    status="critical_error",
                    summary="x" * 1024,
                    evidence_ids=[u["unit_id"] for u in catalog["units"]],
                    partial_evidence=[],
                )
                for name in capacity.DIMENSIONS
            }
        }
        public = [u for u in catalog["units"] if u["kind"] == "public_content"]
        if role == "A":
            baseline["supervision"] = dict(
                status="complete",
                positive_units=[u["unit_id"] for u in public],
                partial_positive_content=[],
                positive_actions=[catalog["actions"][0]["action_id"]],
            )
        assert len(encode(baseline)) == result["whole_unit_scenario_utf8_bytes"]
        longest = sorted(catalog["units"], key=lambda u: len(encode(u["text"])), reverse=True)[:4]
        for name, unit in zip(capacity.DIMENSIONS, longest, strict=False):
            baseline["process"][name]["partial_evidence"] = [
                {"id": unit["unit_id"], "quote": unit["text"]}
            ]
        if role == "A":
            baseline["supervision"]["partial_positive_content"] = [
                {"id": u["unit_id"], "quote": u["text"]} for u in public
            ]
        assert len(encode(baseline)) == result["scenario_utf8_bytes"]
        assert result["estimated_output_tokens"] == (5 * (len(encode(baseline)) + 1024) + 3) // 4
        assert result["max_output_tokens"] == next(
            cap for cap in capacity.CAPS if cap >= result["estimated_output_tokens"]
        )
        assert result["hard_output_size_guarantee"] is False
        assert result["new_summary_or_reference_validator_limits"] is False
        assert result["final_complete_input_wire_plus_output_cap_check_required"] is True
    assert values["A"]["scenario_utf8_bytes"] > values["B"]["scenario_utf8_bytes"]
    assert (view, catalog) == before


def test_capacity_is_data_dependent_and_never_clamps_an_over_limit_original():
    small = capacity.capacity_for(*fixture(), "A")
    larger = capacity.capacity_for(*fixture(count=700), "A")
    assert larger["max_output_tokens"] > small["max_output_tokens"]
    view, catalog = fixture(["x" * 70000])
    before = copy.deepcopy((view, catalog))
    with pytest.raises(ValueError, match="planned_output_exceeds_65536"):
        capacity.capacity_for(view, catalog, "A")
    assert (view, catalog) == before


def test_original_catalog_omissions_and_unknown_role_fail_closed():
    view, catalog = fixture()
    with pytest.raises(ValueError, match="registered_A_or_B_role"):
        capacity.capacity_for(view, catalog, "mapping")
    catalog["units"].pop()
    with pytest.raises(ValueError, match="truncated_or_dropped"):
        capacity.capacity_for(view, catalog, "A")
