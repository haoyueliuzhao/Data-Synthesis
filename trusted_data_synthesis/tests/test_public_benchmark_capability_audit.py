from __future__ import annotations

from pathlib import Path

import pytest

from trusted_synthesis.experiments.vtdo_experiment.phase1_public_benchmark_capability_audit import (
    CAPABILITY_AXES,
    FinancialBenchmarkManifest,
    PublicBenchmarkReferenceManifest,
    _audit_financial_snapshot,
    _finqa_operator_sequence,
    _mechanism_catalog,
    _mechanism_population_contract,
)

ROOT = Path(__file__).resolve().parents[1]
FINANCIAL_MANIFEST = ROOT / "benchmarks/manifests/vtdo_external_benchmarks.json"
DESIGN_MANIFEST = ROOT / "benchmarks/manifests/v25_21_public_agent_design_references.json"


def test_finqa_operator_sequence_preserves_dependent_program_order() -> None:
    assert _finqa_operator_sequence("subtract(153.7, 139.9), divide(#0, 139.9)") == (
        "subtract",
        "divide",
    )


def test_frozen_financial_benchmark_statistics_have_exact_denominators() -> None:
    manifest = FinancialBenchmarkManifest.model_validate_json(
        FINANCIAL_MANIFEST.read_text(encoding="utf-8")
    )
    audits = {
        spec.benchmark_id: _audit_financial_snapshot(spec, FINANCIAL_MANIFEST.parent)
        for spec in manifest.snapshots
    }

    finqa = audits["finqa"]
    assert finqa.observed_example_count == 1147
    assert finqa.distributions["program_depth"] == {
        "1": 654,
        "2": 409,
        "3": 55,
        "4": 10,
        "5": 19,
    }
    assert finqa.structural_signals["multi_step_program"].count == 493
    assert finqa.structural_signals["comparison_operator"].count == 20

    tat_qa = audits["tat_qa"]
    assert tat_qa.observed_example_count == 1663
    assert tat_qa.distributions["answer_type"] == {
        "arithmetic": 699,
        "count": 40,
        "multi-span": 210,
        "span": 714,
    }
    assert tat_qa.structural_signals["cross_modal_evidence"].count == 546


def test_financial_snapshot_hash_mismatch_fails_closed() -> None:
    manifest = FinancialBenchmarkManifest.model_validate_json(
        FINANCIAL_MANIFEST.read_text(encoding="utf-8")
    )
    altered = manifest.snapshots[0].model_copy(update={"sha256": "0" * 64})

    with pytest.raises(ValueError, match="snapshot hash"):
        _audit_financial_snapshot(altered, FINANCIAL_MANIFEST.parent)


def test_public_agent_reference_manifest_is_aggregate_only() -> None:
    manifest = PublicBenchmarkReferenceManifest.model_validate_json(
        DESIGN_MANIFEST.read_text(encoding="utf-8")
    )

    assert manifest.usage == "design_reference_only"
    assert manifest.content_policy.task_content_loaded is False
    assert manifest.content_policy.synthesis_access == "forbidden"
    assert manifest.content_policy.training_access == "forbidden"
    assert {item.benchmark_id for item in manifest.references} == {
        "gaia",
        "bfcl_v4",
        "webarena",
        "swe_bench",
        "agentbench",
    }
    serialized = manifest.model_dump(mode="json")
    assert not _contains_content_key(serialized)


def test_v25_21_mechanism_catalog_covers_each_capability_axis_once() -> None:
    mechanisms = _mechanism_catalog()
    contract = _mechanism_population_contract()

    assert len(mechanisms) == 7
    assert {item.primary_axis for item in mechanisms} == set(CAPABILITY_AXES)
    assert all("bridge" in item.tiers for item in mechanisms)
    assert contract.minimum_development_group_count == 84
    assert contract.development_groups_per_mechanism_by_tier["bridge"] == 4
    assert contract.pro_api_calls_authorized is False
    assert contract.exact_target_evaluated is False
    assert contract.next_permitted_stage.endswith("population_construction_only")


def _contains_content_key(value: object) -> bool:
    if isinstance(value, dict):
        if {"question", "answer", "prompt"} & set(value):
            return True
        return any(_contains_content_key(item) for item in value.values())
    if isinstance(value, list):
        return any(_contains_content_key(item) for item in value)
    return False
