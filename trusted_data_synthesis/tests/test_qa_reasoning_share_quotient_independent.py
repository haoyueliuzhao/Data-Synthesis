"""Bounded independent checks of the one frozen six-session measurement.

The new pure mapper constructs one in-memory test fixture.  Every producer is
then disabled before the independent checker runs.  Online calls, candidate
execution and original qualification replay are forbidden throughout.
"""

from __future__ import annotations

import ast
import copy
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from trusted_synthesis.experiments.qa_reasoning_share_model_pilot import adapter, engine
from trusted_synthesis.experiments.qa_reasoning_share_model_pilot import independent as pilot_audit
from trusted_synthesis.experiments.qa_reasoning_share_quotient_measurement import (
    comparison,
    independent,
    measurement,
    models,
    projection,
)
from trusted_synthesis.experiments.qa_reasoning_share_quotient_measurement.inputs import (
    assert_unchanged,
    load_inputs,
)

ROOT = Path(__file__).resolve().parents[2]


def _forbidden(*args: Any, **kwargs: Any) -> None:
    raise AssertionError("this check may read frozen evidence, never call a semantic producer")


@pytest.fixture(scope="module")
def measured() -> Iterator[dict[str, Any]]:
    with pytest.MonkeyPatch.context() as guard:
        guard.setattr(engine.ModelProtocolEngine, "__init__", _forbidden)
        guard.setattr(engine.ModelProtocolEngine, "exchange", _forbidden)
        guard.setattr(adapter.DeepSeekAdapter, "perform", _forbidden)
        guard.setattr(adapter.CurlTransport, "send", _forbidden)
        guard.setattr(adapter.MockTransport, "send", _forbidden)
        for executor in (
            engine.RelationSumExecutor,
            engine.ShareRatioExecutor,
            engine.ScalePercentExecutor,
        ):
            guard.setattr(executor, "execute", _forbidden)
        guard.setattr(pilot_audit, "audit_records", _forbidden)
        guard.setattr(pilot_audit, "audit_session", _forbidden)
        inputs = load_inputs(ROOT)
        rules = models.measurement_contract()
        projections = [
            projection.project_session(inputs, session, rules) for session in inputs["sessions"]
        ]
        pairs = comparison.compare_all(projections, rules)
        partition = measurement.build_partition(inputs, rules, projections, pairs)
        result = {
            "inputs": inputs,
            "rules": rules,
            "projections": projections,
            "pairs": pairs,
            "partition": partition,
            "measurement": measurement.measure_empirical(inputs, rules, partition),
        }
        yield result
        assert_unchanged(ROOT, inputs)


@pytest.fixture(autouse=True)
def disable_measurement_producers(
    monkeypatch: pytest.MonkeyPatch,
    measured: dict[str, Any],
) -> None:
    for module in (projection, comparison, measurement):
        for name, value in tuple(vars(module).items()):
            if callable(value) and getattr(value, "__module__", None) == module.__name__:
                monkeypatch.setattr(module, name, _forbidden)


def _renew(obj: dict[str, Any], **changes: Any) -> dict[str, Any]:
    kind = obj["schema_version"].removeprefix("share_quotient_").removesuffix(".v1")
    return models.record(
        kind,
        **(
            {key: value for key, value in obj.items() if key not in {"id", "schema_version"}}
            | changes
        ),
    )


def _fraction(numerator: int, denominator: int) -> dict[str, Any]:
    return {
        "numerator": numerator,
        "denominator": denominator,
        "exact": f"{numerator}/{denominator}",
        "value": numerator / denominator if denominator else None,
    }


def _audit(bundle: dict[str, Any]) -> dict[str, Any]:
    return independent.audit_measurement(**bundle)


def _rejected(bundle: dict[str, Any], stage: str, reason: str | None = None) -> None:
    report = _audit(bundle)
    assert report["passed"] is False, report
    assert report["errors"][0]["stage"] == stage, report
    if reason is not None:
        assert report["errors"][0]["reason"] == reason, report


def _replace_projection(bundle: dict[str, Any], index: int, replacement: dict[str, Any]) -> None:
    old = bundle["projections"][index]
    new = _renew(replacement)
    bundle["projections"][index] = new
    for i, pair in enumerate(bundle["pairs"]):
        changes = {
            key: new["id"]
            for key in ("left_projection_id", "right_projection_id")
            if pair[key] == old["id"]
        }
        if changes:
            bundle["pairs"][i] = _renew(pair, **changes)
    assignments = [
        _renew(row, projection_id=new["id"]) if row["projection_id"] == old["id"] else row
        for row in bundle["partition"]["assignments"]
    ]
    bundle["partition"] = _renew(bundle["partition"], assignments=assignments)


def test_original_measurement_and_complete_alpha_renaming(measured: dict[str, Any]) -> None:
    report = _audit(measured)
    assert report["passed"] is True, report
    assert report["provider_calls"] == report["new_candidate_runtime_executions"] == 0
    assert report["original_qualification_reexecuted"] is False
    assert len(report["checks"]) == 5
    assert [p["statistics"]["reduced_corrections"] for p in measured["projections"]] == [
        0,
        2,
        5,
        1,
        4,
        0,
    ]
    assert measured["projections"][0]["status"] == "not_qualified"
    assert measured["measurement"]["q"]["exact"] == "5/6"

    syntax = ast.parse(Path(independent.__file__).read_text(encoding="utf-8"))
    imports = [node.module or "" for node in ast.walk(syntax) if isinstance(node, ast.ImportFrom)]
    assert not any(
        word in module
        for module in imports
        for word in (
            "projection",
            "comparison",
            "measurement.",
            "controls",
            "adapter",
            "engine",
            "runtime",
        )
    )

    renamed = copy.deepcopy(measured)
    old = renamed["projections"][1]
    key_map = {node["key"]: f"alpha:{index}" for index, node in enumerate(old["graph"]["nodes"])}
    for node in old["graph"]["nodes"]:
        node["key"] = key_map[node["key"]]
    for edge in old["graph"]["edges"]:
        edge["source"], edge["target"] = key_map[edge["source"]], key_map[edge["target"]]
    for row in old["node_provenance"]:
        row["key"] = key_map[row["key"]]
    identifier = old["session_id"]
    for index, pair in enumerate(renamed["pairs"]):
        rows = copy.deepcopy(pair["bijection"])
        for row in rows:
            if pair["left_session_id"] == identifier:
                row["left"] = key_map[row["left"]]
            if pair["right_session_id"] == identifier:
                row["right"] = key_map[row["right"]]
        renamed["pairs"][index] = _renew(pair, bijection=rows)
    _replace_projection(renamed, 1, old)
    assert _audit(renamed)["passed"] is True


def test_all_actual_update_nodes_must_be_retained(measured: dict[str, Any]) -> None:
    changed = copy.deepcopy(measured)
    result = changed["projections"][1]
    key = next(node["key"] for node in result["graph"]["nodes"] if node["kind"] == "update")
    result["graph"]["nodes"] = [node for node in result["graph"]["nodes"] if node["key"] != key]
    result["graph"]["edges"] = [
        edge for edge in result["graph"]["edges"] if key not in (edge["source"], edge["target"])
    ]
    result["node_provenance"] = [row for row in result["node_provenance"] if row["key"] != key]
    _replace_projection(changed, 1, result)
    _rejected(changed, "event_projection_and_corrections", "independent.complete_node_coverage")


def test_actual_denominator_use_edge_cannot_be_changed(measured: dict[str, Any]) -> None:
    changed = copy.deepcopy(measured)
    result = changed["projections"][1]
    edge = next(
        edge for edge in result["graph"]["edges"] if edge["role"] == "operand:denominator:1"
    )
    edge["source"] = changed["inputs"]["context"]["evidence"]["freight"]["id"]
    _replace_projection(changed, 1, result)
    _rejected(
        changed, "event_projection_and_corrections", "independent.complete_role_edge_coverage"
    )


def test_accepted_percent_claim_value_is_retained(measured: dict[str, Any]) -> None:
    changed = copy.deepcopy(measured)
    result = changed["projections"][2]
    claim = next(
        node
        for node in result["graph"]["nodes"]
        if node["kind"] == "claim" and node["semantics"]["producer_operation"] == "scale_percent"
    )
    claim["semantics"]["proposition"]["value"] = "93.508458"
    _replace_projection(changed, 2, result)
    _rejected(changed, "event_projection_and_corrections", "independent.node_semantics")


@pytest.mark.parametrize("field", ["pending_observation", "accepted_claim"])
def test_rejection_cannot_hide_a_changed_knowledge_state(
    measured: dict[str, Any],
    field: str,
) -> None:
    changed = copy.deepcopy(measured)
    state = changed["inputs"]["sessions"][2]["records"]["events"][5]["post_state"]
    if field == "pending_observation":
        state["pending_observation"]["output"]["value"] = "93.508458"
    else:
        state["accepted_claims"][0]["proposition"]["value"] = "0"
    _rejected(changed, "event_projection_and_corrections", "independent.correction_factual_witness")


@pytest.mark.parametrize("kind", ["action", "final"])
def test_rejection_cannot_hide_a_different_semantic_target(
    measured: dict[str, Any],
    kind: str,
) -> None:
    changed = copy.deepcopy(measured)
    if kind == "action":
        proposal = changed["inputs"]["sessions"][3]["records"]["events"][2]["submission"]["parsed"]
        proposal["inputs"][0]["ref_id"] = changed["inputs"]["context"]["evidence"]["freight"]["id"]
    else:
        event = changed["inputs"]["sessions"][2]["records"]["events"][10]
        event["submission"]["parsed"]["answer_claim_id"] = event["request"]["state"][
            "accepted_claims"
        ][1]["id"]
    _rejected(changed, "event_projection_and_corrections", "independent.correction_factual_witness")


def test_pair_certificates_require_bijection_or_actual_label_difference(
    measured: dict[str, Any],
) -> None:
    changed = copy.deepcopy(measured)
    index = next(i for i, pair in enumerate(changed["pairs"]) if pair["relation"] == "equivalent")
    pair = changed["pairs"][index]
    pair["bijection"] = pair["bijection"][:-1]
    changed["pairs"][index] = _renew(pair)
    _rejected(changed, "ten_pair_semantic_witnesses", "independent.bijection_total_injective")

    changed = copy.deepcopy(measured)
    index = next(
        i
        for i, pair in enumerate(changed["pairs"])
        if pair["relation"] == "different_retained_semantics"
    )
    changed["pairs"][index] = _renew(
        changed["pairs"][index],
        difference_witness={"kind": "graph_hash", "left": "a", "right": "b"},
    )
    _rejected(changed, "ten_pair_semantic_witnesses", "independent.explicit_difference_required")


def test_failed_session_and_denominators_are_not_repaired(measured: dict[str, Any]) -> None:
    changed = copy.deepcopy(measured)
    first = changed["partition"]["assignments"][0]
    forged = _renew(first, session_id=changed["projections"][0]["session_id"])
    changed["partition"] = _renew(
        changed["partition"], assignments=[*changed["partition"]["assignments"], forged]
    )
    _rejected(changed, "relation_partition_and_assignments", "independent.assignment_domain")

    changed = copy.deepcopy(measured)
    changed["measurement"] = _renew(changed["measurement"], q=_fraction(5, 5))
    _rejected(changed, "empirical_denominators", "independent.exact_empirical_ratio")


def test_unknown_projection_keeps_all_five_unmapped_without_renormalization(
    measured: dict[str, Any],
) -> None:
    changed = copy.deepcopy(measured)
    result = changed["projections"][2]
    result["status"] = "undetermined"
    result["uninterpreted"] = [{"turn_index": None, "code": "isolated_unknown_measurement_control"}]
    identifier = result["session_id"]
    _replace_projection(changed, 2, result)
    for index, pair in enumerate(changed["pairs"]):
        if identifier in (pair["left_session_id"], pair["right_session_id"]):
            changed["pairs"][index] = _renew(
                pair,
                relation="undetermined",
                reason="one projection is uninterpreted",
                bijection=[],
                difference_witness=None,
                canonical_search={"left_permutations": None, "right_permutations": None},
            )
    qualified_ids = [
        p["session_id"] for p in changed["projections"] if p["status"] != "not_qualified"
    ]
    changed["partition"] = _renew(
        changed["partition"],
        complete=False,
        classes=[],
        assignments=[],
        class_count=None,
        unmapped_session_ids=qualified_ids,
        relation_checks={
            "complete_pairs": True,
            "reflexive": False,
            "symmetric": True,
            "transitive": None,
        },
    )
    changed["measurement"] = _renew(
        changed["measurement"],
        complete=False,
        mapped_count=0,
        unmapped_count=5,
        state_frequencies=[],
        conditional_distribution=None,
        joint_total=_fraction(0, 6),
        conditional_total=_fraction(0, 5),
        unmapped_conditional=_fraction(5, 5),
    )
    report = _audit(changed)
    assert report["passed"] is True, report
    assert changed["measurement"]["q"]["exact"] == "5/6"
    assert changed["measurement"]["conditional_distribution"] is None
    changed["measurement"] = _renew(changed["measurement"], qualified_denominator=4)
    _rejected(changed, "empirical_denominators", "independent.empirical_domain")


def test_ten_pairs_are_a_fixed_domain_not_a_success_selected_subset(
    measured: dict[str, Any],
) -> None:
    changed = copy.deepcopy(measured)
    changed["pairs"] = changed["pairs"][:-1]
    _rejected(changed, "ten_pair_semantic_witnesses", "independent.complete_ten_pairs")
