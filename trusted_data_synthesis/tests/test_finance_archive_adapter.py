from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from datetime import date
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from trusted_synthesis.core.evidence import EpistemicStatus, ScalarObservation
from trusted_synthesis.core.evidence.schema import SourceAuthority
from trusted_synthesis.core.refinement import (
    RefinedSynthesisMaterializer,
    aggregate_cell_feedback,
    build_observed_policy,
    build_synthesis_cell,
    update_synthesis_policy,
)
from trusted_synthesis.core.refinement.materialization import make_synthesis_cell_request
from trusted_synthesis.core.task.schema import PlanningTrack, RetrievalTrack
from trusted_synthesis.domains.finance.adapter import FinanceArchiveAdapter, _time_label
from trusted_synthesis.domains.finance.schema import FinanceArchiveConfig
from trusted_synthesis.experiments.agent_validation.runner import _compile_runtime
from trusted_synthesis.experiments.agent_validation.tracks import materialize_track_variant
from trusted_synthesis.experiments.finance_archive import (
    FinanceArchiveBindingProvider,
)


def test_finance_time_label_distinguishes_quarterly_instant_and_duration() -> None:
    instant = {"fiscal_year": 2025, "fiscal_quarter": "Q1", "metric_period_type": "point_in_time"}
    duration = {"fiscal_year": 2025, "fiscal_quarter": "Q1", "metric_period_type": "duration"}

    assert _time_label(instant, date(2025, 3, 31)) == "FY2025 Q1 (as of 2025-03-31)"
    assert _time_label(duration, date(2025, 3, 31)) == "FY2025 Q1 (period ended 2025-03-31)"


def test_finance_adapter_reads_only_quality_passed_graph_facts(tmp_path: Path) -> None:
    config = _archive_fixture(tmp_path)
    adapter = FinanceArchiveAdapter(config)
    before = sorted(path.relative_to(tmp_path) for path in tmp_path.rglob("*"))

    inspection = adapter.inspect()
    evidence = list(adapter.iter_evidence(limit=1))
    grounding = adapter.source_grounding_verifier().verify(evidence[0])
    mismatched = evidence[0].model_copy(
        update={
            "payload": evidence[0].payload.model_copy(update={"value": 999}),
        }
    )
    mismatched_grounding = adapter.source_grounding_verifier().verify(mismatched)
    after = sorted(path.relative_to(tmp_path) for path in tmp_path.rglob("*"))

    assert inspection["compatible"] is True
    assert inspection["read_only"] is True
    assert inspection["fact_node_count"] == 1
    assert len(evidence) == 1
    assert evidence[0].subject.name == "Example Company"
    assert evidence[0].predicate == "revenue"
    assert evidence[0].temporal_context.label == "year ended 2023-12-31"
    assert isinstance(evidence[0].payload, ScalarObservation)
    assert evidence[0].source.authority == SourceAuthority.OFFICIAL
    assert evidence[0].epistemic_status == EpistemicStatus.OBSERVED
    assert evidence[0].provenance.build_ids["kg"] == "kg_test"
    assert grounding.passed
    assert not mismatched_grounding.passed
    assert mismatched_grounding is not grounding
    assert "source_entailment" in mismatched_grounding.failures
    assert before == after


def test_finance_adapter_remaps_registered_legacy_archive_root(tmp_path: Path) -> None:
    config = _archive_fixture(tmp_path)
    raw_objects_path = config.catalog_root / "raw_objects.parquet"
    rows = pq.read_table(raw_objects_path).to_pylist()
    legacy_root = Path("/workspace/Data Synthesis/raw_financial_data_lake")
    rows[0]["storage_uri"] = str(legacy_root / "raw" / "companyfacts.json")
    _parquet(raw_objects_path, rows)
    config = config.model_copy(update={"legacy_archive_roots": (legacy_root,)})

    adapter = FinanceArchiveAdapter(config)
    evidence = next(adapter.iter_evidence(limit=1))
    grounding = adapter.source_grounding_verifier().verify(evidence)

    assert evidence.source_locator.storage_uri == rows[0]["storage_uri"]
    assert grounding.passed
    assert all(grounding.checks.values())


def test_finance_archive_provider_materializes_a_proof_carrying_sample(
    tmp_path: Path,
) -> None:
    adapter = FinanceArchiveAdapter(_archive_fixture(tmp_path))
    provider = FinanceArchiveBindingProvider(
        adapter,
        candidate_pool_id="finance_archive_test_pool",
        sampling_partition_id="A",
        pool_split_seed=7,
        evidence_scan_limit=100,
        evidence_sample_size=100,
        stratum_reservoir_size=20,
        candidates_per_pattern=10,
    )
    binding = provider._bindings_by_pattern["finance.fact_retrieval"][0]
    if provider._partition(binding) == "B":
        provider = provider.for_partition("B")
    source = provider._contract_case(binding)
    cell = build_synthesis_cell(
        source.task.public,
        source.corpus,
        source.task.oracle.gold_evidence_ids,
    )
    task_cells = {source.task.task_id: cell}
    policy = build_observed_policy(task_cells)
    update = update_synthesis_policy(
        policy,
        aggregate_cell_feedback(policy, (), (), task_cells),
        (),
        eta=0,
        beta=1,
        gamma=0,
        total_budget=1,
        calibration_manifest_hash="calibration:finance_archive_provider_test",
        require_calibrated_feedback=False,
    )

    artifacts, report = RefinedSynthesisMaterializer(provider).materialize(
        update,
        seed=17,
    )

    assert report.status == "passed"
    assert report.seed_effective
    assert report.candidate_pool_id == "finance_archive_test_pool"
    assert report.grounding_required_sample_count == 1
    assert report.grounding_checked_count == 1
    assert report.grounding_pass_count == 1
    assert report.grounding_failure_counts == {}
    assert len(artifacts) == 1
    assert artifacts[0].compiled.task.public.domain == "finance"
    assert " for as of " not in artifacts[0].compiled.task.public.instruction
    assert artifacts[0].compiled.task.public.metadata["source_grounding_requirement"] == "required"
    assert artifacts[0].candidate.domain_plugin_set.evidence_adapter_id == "finance_archive.v2"
    assert (
        provider._source_grounding_verifier.verifier_id
        in artifacts[0].candidate.domain_plugin_set.verification_plugin_ids
    )
    assert (
        artifacts[0].candidate.domain_plugin_set.versions["source_grounding"]
        == provider._source_grounding_verifier.verifier_version
    )


def test_finance_archive_capacity_audit_is_distribution_and_grounding_aware(
    tmp_path: Path,
) -> None:
    adapter = FinanceArchiveAdapter(_archive_fixture(tmp_path))
    provider = FinanceArchiveBindingProvider(
        adapter,
        candidate_pool_id="finance_archive_capacity_pool",
        sampling_partition_id="A",
        pool_split_seed=13,
        evidence_scan_limit=100,
        evidence_sample_size=100,
        stratum_reservoir_size=20,
        candidates_per_pattern=10,
    )
    binding = provider._bindings_by_pattern["finance.fact_retrieval"][0]
    if provider._partition(binding) == "B":
        provider = provider.for_partition("B")

    report = provider.capacity_report(
        target_sample_count=1,
        pattern_target_shares={"finance.fact_retrieval": 1.0},
        distractor_evaluation_limit_per_pattern=2,
    )

    assert report.status == "ready"
    assert report.target_counts_by_pattern["finance.fact_retrieval"] == 1
    assert report.binding_count_by_pattern["finance.fact_retrieval"] == 1
    assert (
        report.partition_binding_counts[provider.sampling_partition_id]["finance.fact_retrieval"]
        == 1
    )
    assert report.source_grounding_checked_count == 1
    assert report.source_grounding_valid_count == 1
    assert report.source_grounding_failure_counts == {}
    assert report.evaluated_distractor_binding_count == 1
    assert report.difficulty_distribution == {"easy": 1}
    assert report.synthesis_cell_count == 1
    assert report.quota_shortfalls == {}


def test_finance_archive_contract_cases_are_deterministic_and_pinned(
    tmp_path: Path,
) -> None:
    adapter = FinanceArchiveAdapter(_archive_fixture(tmp_path))
    provider = FinanceArchiveBindingProvider(
        adapter,
        candidate_pool_id="finance_archive_contract_case_pool",
        sampling_partition_id="A",
        pool_split_seed=23,
        evidence_scan_limit=100,
        evidence_sample_size=100,
        stratum_reservoir_size=20,
        candidates_per_pattern=10,
    )
    binding = provider._bindings_by_pattern["finance.fact_retrieval"][0]
    if provider._partition(binding) == "B":
        provider = provider.for_partition("B")

    first = provider.contract_cases(1, seed=31)
    repeated = provider.contract_cases(1, seed=31)

    assert provider.kg_build_id == "kg_test"
    assert tuple(item.task.task_id for item in first) == tuple(
        item.task.task_id for item in repeated
    )
    assert first[0].domain == "finance"
    assert first[0].corpus.corpus_hash == repeated[0].corpus.corpus_hash
    tracked_task = materialize_track_variant(
        first[0].task,
        first[0].corpus,
        retrieval_track=RetrievalTrack.RESOLVED,
        planning_track=PlanningTrack.PLAN_GIVEN,
    )
    compiled, _ = _compile_runtime(first[0], tracked_task)
    assert compiled.sample.task_id == tracked_task.task_id
    assert first[0].source_grounding_verifier is not None


def test_finance_archive_contract_cases_skip_invalid_mined_binding(
    tmp_path: Path,
    monkeypatch,
) -> None:
    adapter = FinanceArchiveAdapter(_archive_fixture(tmp_path))
    provider = FinanceArchiveBindingProvider(
        adapter,
        candidate_pool_id="finance_archive_skip_invalid_pool",
        sampling_partition_id="A",
        pool_split_seed=29,
        evidence_scan_limit=100,
        evidence_sample_size=100,
        stratum_reservoir_size=20,
        candidates_per_pattern=10,
    )
    binding = provider._bindings_by_pattern["finance.fact_retrieval"][0]
    alternate = replace(binding, stratum=(*binding.stratum, "retry"))
    provider._bindings_by_pattern["finance.fact_retrieval"] = (binding, alternate)
    monkeypatch.setattr(provider, "_partition", lambda _: provider.sampling_partition_id)
    original_contract_case = provider._contract_case
    calls = 0

    def fail_first(candidate):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise ValueError("synthetic semantic rejection")
        return original_contract_case(candidate)

    monkeypatch.setattr(provider, "_contract_case", fail_first)

    cases = provider.contract_cases(1, seed=37)

    assert len(cases) == 1
    assert calls == 2


def test_finance_archive_refined_iterator_skips_invalid_mined_binding(
    tmp_path: Path,
    monkeypatch,
) -> None:
    adapter = FinanceArchiveAdapter(_archive_fixture(tmp_path))
    provider = FinanceArchiveBindingProvider(
        adapter,
        candidate_pool_id="finance_archive_refined_skip_invalid_pool",
        sampling_partition_id="A",
        pool_split_seed=41,
        evidence_scan_limit=100,
        evidence_sample_size=100,
        stratum_reservoir_size=20,
        candidates_per_pattern=10,
    )
    pattern_id = "finance.fact_retrieval"
    binding = provider._bindings_by_pattern[pattern_id][0]
    alternate = replace(binding, stratum=(*binding.stratum, "retry"))
    provider._bindings_by_pattern[pattern_id] = (binding, alternate)
    monkeypatch.setattr(provider, "_partition", lambda _: provider.sampling_partition_id)
    source_case = provider._contract_case(binding)
    cell = build_synthesis_cell(
        source_case.task.public,
        source_case.corpus,
        source_case.task.oracle.gold_evidence_ids,
    )
    request = make_synthesis_cell_request(
        policy_update_id="policy:test",
        cell=cell,
        policy_allocated_count=1,
        requested_count=1,
        seed=43,
    )
    original_contract_case = provider._contract_case
    calls = 0

    def fail_first(candidate):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise ValueError("synthetic semantic rejection")
        return original_contract_case(candidate)

    monkeypatch.setattr(provider, "_contract_case", fail_first)

    candidates = tuple(provider.iter_candidates(request))

    assert len(candidates) == 1
    assert calls == 2


def _archive_fixture(root: Path) -> FinanceArchiveConfig:
    catalog_root = root / "catalog"
    catalog_root.mkdir()
    _parquet(
        catalog_root / "canonical_entities.parquet",
        [
            {
                "entity_id": "EXAMPLE_US",
                "canonical_name": "Example Company",
                "entity_type": "company",
                "market": "US",
                "country": "US",
            }
        ],
    )
    _parquet(
        catalog_root / "metrics.parquet",
        [
            {
                "metric_id": "revenue",
                "canonical_name": "Revenue",
                "metric_category": "financial_statement",
                "statement_type": "income_statement",
                "period_type": "period_flow",
                "default_unit": "monetary",
                "default_currency": "USD",
            }
        ],
    )
    _parquet(
        catalog_root / "source_registry.parquet",
        [
            {
                "source_id": "sec_companyfacts",
                "source_name": "SEC Company Facts",
                "authority_level": "S1_official",
                "provider": "SEC",
                "base_url": "https://data.sec.gov/",
                "license_note": None,
            }
        ],
    )
    _parquet(
        catalog_root / "source_metric_definitions.parquet",
        [
            {
                "definition_id": "sdef_revenue",
                "definition_text": "GAAP revenue",
                "raw_concept_name": "us-gaap:Revenue",
            }
        ],
    )
    raw_path = root / "raw" / "companyfacts.json"
    raw_path.parent.mkdir()
    raw_path.write_text(
        json.dumps(
            {
                "facts": {
                    "us-gaap": {
                        "Revenue": {
                            "units": {
                                "USD": [
                                    {
                                        "start": "2023-01-01",
                                        "end": "2023-12-31",
                                        "fy": 2023,
                                        "fp": "FY",
                                        "val": 123450000,
                                    }
                                ]
                            }
                        }
                    }
                }
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    _parquet(
        catalog_root / "raw_objects.parquet",
        [
            {
                "raw_object_id": "raw_example",
                "source_id": "sec_companyfacts",
                "original_url": "https://data.sec.gov/api/xbrl/companyfacts/example.json",
                "storage_uri": str(raw_path),
                "content_sha256": hashlib.sha256(raw_path.read_bytes()).hexdigest(),
            }
        ],
    )
    report_path = root / "kg_build_report.json"
    report_path.write_text(
        json.dumps(
            {
                "kg_build_id": "kg_test",
                "quality": {
                    "kg_quality_gate_status": "passed",
                    "graph_schema_version": "3.0",
                    "input_fact_build_id": "fact_build_test",
                    "fact_node_count": 1,
                    "derived_fact_node_count": 0,
                    "node_count": 5,
                    "edge_count": 4,
                },
            }
        ),
        encoding="utf-8",
    )
    nodes_path = root / "kg_nodes.jsonl"
    nodes_path.write_text(
        json.dumps(
            {
                "is_active": 1,
                "kg_build_id": "kg_test",
                "node_type": "Fact",
                "properties": {
                    "stable_fact_id": "fact_revenue_2023",
                    "fact_id": "fact_revenue_2023__build",
                    "build_id": "standardized_build_test",
                    "entity_id": "EXAMPLE_US",
                    "metric_id": "revenue",
                    "normalized_value": "123.45",
                    "normalized_unit": "million USD",
                    "normalized_currency": "USD",
                    "period_start": "2023-01-01",
                    "period_end": "2023-12-31",
                    "fiscal_year": 2023,
                    "fiscal_quarter": "FY",
                    "time_basis": "fiscal_period",
                    "frequency": "annual",
                    "metric_period_type": "period_flow",
                    "financial_scope_type": "consolidated_company",
                    "entity_scope_id": "EXAMPLE_US",
                    "source_id": "sec_companyfacts",
                    "source_definition_id": "sdef_revenue",
                    "raw_object_id": "raw_example",
                    "verification_status": "single_source",
                    "graph_ready_reason": "ready",
                    "is_forecast": 0,
                    "confidence_score": 0.99,
                    "comparability_level": "xbrl_concept_level",
                    "value_scale": "million",
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )
    edges_path = root / "kg_edges.jsonl"
    edges_path.write_text("", encoding="utf-8")
    return FinanceArchiveConfig(
        adapter_version="finance_archive.v2",
        archive_root=root,
        kg_nodes_path=nodes_path,
        kg_edges_path=edges_path,
        kg_report_path=report_path,
        catalog_root=catalog_root,
        exclude_forecasts=True,
        accepted_verification_statuses=("single_source", "cross_verified"),
        required_kg_build_id="kg_test",
        required_graph_schema_version="3.0",
    )


def _parquet(path: Path, rows: list[dict[str, object]]) -> None:
    pq.write_table(pa.Table.from_pylist(rows), path)
