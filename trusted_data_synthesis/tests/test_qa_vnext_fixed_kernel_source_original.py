"""Pinned original-source integration and conflict attacks; never Provider/GPU.

These tests skip when the separately archived read-only research parents are
absent.  The algorithmic execution controls live in the companion test module.
"""

import copy
import json
from contextlib import ExitStack
from pathlib import Path

import pytest

from trusted_synthesis.experiments.finance_qa_vnext_fixed_kernel_value import protocol as p
from trusted_synthesis.experiments.finance_qa_vnext_fixed_kernel_value.semantic_mapping import (
    assess_new_semantics,
)
from trusted_synthesis.experiments.finance_qa_vnext_fixed_kernel_value.source_boundary import (
    load_source_evidence,
    prepare_fixture,
)
from trusted_synthesis.experiments.finance_qa_vnext_movement_support.run import load_fixtures
from trusted_synthesis.experiments.finance_qa_vnext_probe_coverage.runtime import replay

DATA = Path("/data1/zhuxinrui/projects/Data-Synthesis")
PROBE = Path(
    "/tmp/data-synthesis-probe-coverage-uPr3h7/trusted_data_synthesis/artifacts/qa_vnext_probe_coverage/probe_20260913"
)
DEVELOPMENT_TASK = "task_01bd8584a1cf4dc01f01a5113decf5df6e0a149f48219ef550ff5129cde4b21c"


@pytest.fixture(scope="module")
def original_inputs():
    if not (
        DATA
        / "trusted_data_synthesis/artifacts/qa_vnext_readiness_revision"
        / "revision_20260912/manifest.json"
    ).is_file():
        pytest.skip("separately archived original-source fixtures unavailable")
    with ExitStack() as stack:
        fixtures, dependencies = load_fixtures(stack, DATA)
        evidence = load_source_evidence(DATA, dependencies["parents"], fixtures)
        by_task = {row["identity"]["task_id"]: row for row in fixtures}
        yield by_task, evidence


@pytest.fixture(scope="module")
def repeated_fixture(original_inputs):
    fixtures, evidence = original_inputs
    original = fixtures[DEVELOPMENT_TASK]
    prepared = prepare_fixture(original, source_evidence=evidence)
    assert prepared["source_boundary"]["added_occurrences"]
    return original, evidence, prepared


def test_original_DOM_and_CFO_parent_replay_is_bounded_and_source_only(original_inputs):
    fixtures, evidence = original_inputs
    assert len(fixtures) == 255
    assert len(evidence["table_proofs"]) == 23
    assert len(evidence["raw_files"]) == 37
    assert evidence["API_calls"] == evidence["GPU_operations"] == 0
    assert not evidence["Student_outputs_read"] and not evidence["gold_values_read"]


def test_repeated_cell_has_distinct_identity_and_complete_source_proof(repeated_fixture):
    original, evidence, prepared = repeated_fixture
    proof = prepared["source_boundary"]["added_occurrences"][0]
    assert proof["occurrence_fact_id"] != proof["canonical_fact_id"]
    assert proof["original_fact_id"] is None
    assert proof["actual_period_anchor_occurrences"] and proof["original_cell_reference"]
    assert proof["source_unit"] == "million USD" and proof["scale_factor"] == "1"
    assert not proof["numeric_equality_used_as_sole_alias_basis"] and not proof["gold_value_used"]
    assert prepared["messages"] == original["messages"]
    assert prepared["native_bindings"] == original["native_bindings"]
    assert set(original["native_bindings"]) <= set(prepared["enriched_native_bindings"])
    missing_evidence = prepare_fixture(original)
    assert missing_evidence["source_boundary"]["added_occurrences"] == []


@pytest.mark.parametrize(
    "conflict", ["entity", "actual_start", "definition", "unit_scale", "sign", "report_version"]
)
def test_equal_answer_cannot_override_native_semantic_conflicts(repeated_fixture, conflict):
    original, evidence, prepared = repeated_fixture
    changed = copy.deepcopy(original)
    proof = prepared["source_boundary"]["added_occurrences"][0]
    native = changed["native_bindings"][proof["canonical_fact_id"]]
    if conflict == "entity":
        native["entity_id"] = "DIFFERENT_ISSUER"
    elif conflict == "actual_start":
        native["record"]["start"] = "1900-01-01"
    elif conflict == "definition":
        native["source_definition_id"] += "_different_definition"
    elif conflict == "unit_scale":
        native["record"]["unit"] = "USD"
    elif conflict == "sign":
        native["record"]["val"] = str(-int(native["record"]["val"]))
    else:
        native["record"]["accn"] = "different_filing_version"
    # The unchanged gold amount is deliberately irrelevant to locator admission.
    assert (
        changed["bundle"]["private"]["answer_exact"]
        == original["bundle"]["private"]["answer_exact"]
    )
    result = prepare_fixture(changed, source_evidence=evidence)
    assert not any(
        row["original_locator"] == proof["original_locator"]
        for row in result["source_boundary"]["added_occurrences"]
    )
    assert any(
        row["status"] == "UNRESOLVED_COLUMN" for row in result["source_boundary"]["coverage"]
    )
    assert result["messages"] == original["messages"]


@pytest.mark.parametrize("marker", ["restated", "recast", "revised", "reclassification"])
def test_explicit_revision_requires_new_proof_even_with_equal_full_column(repeated_fixture, marker):
    original, evidence, prepared = repeated_fixture
    proof = prepared["source_boundary"]["added_occurrences"][0]
    changed = copy.deepcopy(evidence)
    changed["table_proofs"][proof["original_locator"]["source_id"]]["explicit_revision_markers"] = [
        marker
    ]
    changed = p.record(
        "source_evidence",
        **{key: value for key, value in changed.items() if key not in {"id", "schema_version"}},
    )
    result = prepare_fixture(original, source_evidence=changed)
    assert not any(
        row["original_locator"] == proof["original_locator"]
        for row in result["source_boundary"]["added_occurrences"]
    )


def test_actual_period_anchor_tamper_is_rejected_by_original_JSON_proof(repeated_fixture):
    original, evidence, prepared = repeated_fixture
    changed = copy.deepcopy(original)
    proof = prepared["source_boundary"]["added_occurrences"][0]
    for identifier in proof["actual_period_anchor_fact_ids"]:
        native = changed["native_bindings"][identifier]
        for occurrence in native["all_equal_source_occurrences"]:
            if occurrence["record"].get("accn") == proof["source_accession"]:
                occurrence["record"]["start"] = "1900-01-01"
    result = prepare_fixture(changed, source_evidence=evidence)
    assert not any(
        row["original_locator"] == proof["original_locator"]
        for row in result["source_boundary"]["added_occurrences"]
    )
    assert any(
        "CFO_original_record_proof_join" in row.get("reason", "")
        for row in result["source_boundary"]["coverage"]
    )


@pytest.mark.parametrize("ordinal", [0, 29, 71, 97, 104])
def test_localized_probe_development_regression_preserves_old_qualification(
    original_inputs, ordinal
):
    if not (PROBE / "registry.json").is_file():
        pytest.skip("original Probe 0.1 development archive unavailable")
    fixtures, evidence = original_inputs
    registered = next(
        row
        for row in json.loads((PROBE / "registry.json").read_bytes())
        if row["ordinal"] == ordinal
    )
    directory = PROBE / "sessions" / registered["session_id"]
    session = json.loads((directory / "session.json").read_bytes())
    original = json.loads((directory / "qualification.json").read_bytes())[
        "original_semantic_assessment"
    ]
    replay(session)
    fixture = prepare_fixture(fixtures[registered["task_id"]], source_evidence=evidence)
    result = assess_new_semantics(session, fixture, original)
    assert result["original_semantic_assessment"] == original
    assert original["full_mapping_status"] == "PENDING_REVIEW"
    assert result["financial_valid"] and result["actual_method"] == "movement"
    assert result["full_mapping_status"] == "MAPPED"
    assert not result["training_eligible"]
    assert result["original_results_not_rewritten"]
