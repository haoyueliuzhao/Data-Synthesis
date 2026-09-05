from __future__ import annotations

import hashlib
import json
from pathlib import Path
from unittest.mock import patch

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from trusted_synthesis.core.operations.registry import default_registry
from trusted_synthesis.domains.finance import realization as realization_module
from trusted_synthesis.domains.finance import tasks as task_module
from trusted_synthesis.domains.finance.adapter import FinanceArchiveAdapter
from trusted_synthesis.domains.finance.operations import finance_vnext_operation_registry
from trusted_synthesis.domains.finance.schema import FinanceArchiveConfig
from trusted_synthesis.experiments.finance_pilot import candidate as candidate_module
from trusted_synthesis.experiments.finance_pilot import runner
from trusted_synthesis.experiments.finance_pilot.runner import run_finance_pilot
from trusted_synthesis.experiments.finance_pilot.sampler import discover_bindings
from trusted_synthesis.experiments.finance_pilot.schema import FinancePilotConfig
from trusted_synthesis.experiments.finance_pilot.task_factory import build_task_cases
from trusted_synthesis.hashing import canonical_hash
from trusted_synthesis.runtime import InMemoryEvidenceToolRuntime


def _json_file(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, sort_keys=True) + "\n", encoding="utf-8")


def _parquet(path: Path, rows: list[dict[str, object]]) -> None:
    pq.write_table(pa.Table.from_pylist(rows), path)


@pytest.fixture
def pilot_archive(tmp_path: Path) -> FinanceArchiveAdapter:
    """Synthetic SEC-shaped archive; real adapter, sampling and source-byte grounding."""
    archive = tmp_path / "archive"
    catalog = archive / "catalog"
    catalog.mkdir(parents=True)
    raw_dir = archive / "raw"
    raw_dir.mkdir()
    metrics = (("revenue", "Revenue"), ("gross_profit", "GrossProfit"))
    entities = [
        {
            "entity_id": f"PILOT_{index}_US",
            "canonical_name": f"Pilot Company {index}",
            "entity_type": "company",
            "market": "US",
            "country": "US",
        }
        for index in range(3)
    ]
    _parquet(catalog / "canonical_entities.parquet", entities)
    _parquet(
        catalog / "metrics.parquet",
        [
            {
                "metric_id": predicate,
                "canonical_name": concept,
                "metric_category": "financial_statement",
                "statement_type": "income_statement",
                "period_type": "period_flow",
                "default_unit": "monetary",
                "default_currency": "USD",
            }
            for predicate, concept in metrics
        ],
    )
    _parquet(
        catalog / "source_registry.parquet",
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
        catalog / "source_metric_definitions.parquet",
        [
            {
                "definition_id": f"sdef_{predicate}",
                "definition_text": f"GAAP {concept}",
                "raw_concept_name": f"us-gaap:{concept}",
            }
            for predicate, concept in metrics
        ],
    )
    raw_objects = []
    nodes = []
    for entity_index, entity in enumerate(entities):
        entity_id = entity["entity_id"]
        raw_object_id = f"raw_{entity_id}"
        raw_path = raw_dir / f"{entity_id}.json"
        facts = {}
        for metric_index, (predicate, concept) in enumerate(metrics):
            observations = []
            for year in (2021, 2022, 2023):
                value = (100 + entity_index * 20 + (year - 2021) * 10) // (metric_index + 1)
                observations.append(
                    {
                        "start": f"{year}-01-01",
                        "end": f"{year}-12-31",
                        "fy": year,
                        "fp": "FY",
                        "val": value * 1_000_000,
                    }
                )
                fact_id = f"fact_{entity_id}_{predicate}_{year}"
                nodes.append(
                    {
                        "is_active": 1,
                        "kg_build_id": "kg_pilot_registry_test",
                        "node_type": "Fact",
                        "properties": {
                            "stable_fact_id": fact_id,
                            "fact_id": f"{fact_id}__build",
                            "build_id": "standardized_pilot_registry_test",
                            "entity_id": entity_id,
                            "metric_id": predicate,
                            "normalized_value": str(value),
                            "normalized_unit": "million USD",
                            "normalized_currency": "USD",
                            "period_start": f"{year}-01-01",
                            "period_end": f"{year}-12-31",
                            "fiscal_year": year,
                            "fiscal_quarter": "FY",
                            "time_basis": "fiscal_period",
                            "frequency": "annual",
                            "metric_period_type": "period_flow",
                            "financial_scope_type": "consolidated_company",
                            "entity_scope_id": entity_id,
                            "source_id": "sec_companyfacts",
                            "source_definition_id": f"sdef_{predicate}",
                            "raw_object_id": raw_object_id,
                            "verification_status": "single_source",
                            "graph_ready_reason": "ready",
                            "is_forecast": 0,
                            "confidence_score": 0.99,
                            "comparability_level": "xbrl_concept_level",
                            "value_scale": "million",
                        },
                    }
                )
            facts[concept] = {"units": {"USD": observations}}
        _json_file(raw_path, {"facts": {"us-gaap": facts}})
        raw_objects.append(
            {
                "raw_object_id": raw_object_id,
                "source_id": "sec_companyfacts",
                "original_url": f"https://data.sec.gov/fixture/{entity_id}.json",
                "storage_uri": str(raw_path),
                "content_sha256": hashlib.sha256(raw_path.read_bytes()).hexdigest(),
            }
        )
    _parquet(catalog / "raw_objects.parquet", raw_objects)
    report_path = archive / "kg_build_report.json"
    _json_file(
        report_path,
        {
            "kg_build_id": "kg_pilot_registry_test",
            "quality": {
                "kg_quality_gate_status": "passed",
                "graph_schema_version": "3.0",
                "input_fact_build_id": "fact_build_pilot_registry_test",
                "fact_node_count": len(nodes),
                "derived_fact_node_count": 0,
                "node_count": len(nodes),
                "edge_count": 0,
            },
        },
    )
    nodes_path = archive / "kg_nodes.jsonl"
    nodes_path.write_text(
        "".join(json.dumps(node, sort_keys=True) + "\n" for node in nodes), encoding="utf-8"
    )
    edges_path = archive / "kg_edges.jsonl"
    edges_path.write_text("", encoding="utf-8")
    return FinanceArchiveAdapter(
        FinanceArchiveConfig(
            adapter_version="finance_archive.v2",
            archive_root=archive,
            kg_nodes_path=nodes_path,
            kg_edges_path=edges_path,
            kg_report_path=report_path,
            catalog_root=catalog,
            exclude_forecasts=True,
            accepted_verification_statuses=("single_source", "cross_verified"),
            required_kg_build_id="kg_pilot_registry_test",
            required_graph_schema_version="3.0",
        )
    )


def _jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


@pytest.mark.parametrize("task_quotas", [{"registered_cross_metric_comparison": 1}, None])
def test_real_finance_pilot_entrypoint_uses_vnext_registry(
    pilot_archive: FinanceArchiveAdapter,
    tmp_path: Path,
    task_quotas: dict[str, int] | None,
) -> None:
    config = FinancePilotConfig(mutation_types=())
    if task_quotas is not None:
        config = config.model_copy(update={"task_quotas": task_quotas})
    output = tmp_path / "pilot"
    report = run_finance_pilot(pilot_archive, config, output)
    expected_count = sum(config.task_quotas.values())
    assert report["task_synthesis"]["task_type_counts"] == config.task_quotas
    assert report["reference_validation"]["accepted"] == expected_count
    assert report["candidate_validation"]["clean_accepted"] == expected_count
    assert report["proof_carrying_quality_contract"]["contract_clean_accepted"] == expected_count
    assert report["proof_carrying_quality_contract"]["proof_certificate_count"] == expected_count
    assert report["thresholds"]["qa_parent_authority_portfolio_complete"]
    assert all(report["reproducibility"].values())
    assert report["production_ready"] is False
    manifest = json.loads((output / "release_manifest.json").read_text(encoding="utf-8"))
    expected_registry_hash = canonical_hash(
        finance_vnext_operation_registry().manifest(), prefix="operation_manifest:"
    )
    assert manifest["operation_manifest_hash"] == expected_registry_hash
    finance_plugins = [
        item for item in manifest["domain_plugin_sets"] if item["domain"] == "finance"
    ]
    assert len(finance_plugins) == 1
    assert finance_plugins[0]["operation_registry_manifest_hash"] == expected_registry_hash
    samples = _jsonl(output / "proof_carrying_samples.jsonl")
    for sample in samples:
        assert sample["certificate"]["operation_manifest_hash"] == expected_registry_hash
    if task_quotas is not None:
        tasks = _jsonl(output / "task_packages.jsonl")
        assert [node["operator_id"] for node in tasks[0]["oracle"]["task_program"]["nodes"]] == [
            "registered_compare"
        ]
    else:
        assert set(config.task_quotas) == {
            "fact_retrieval",
            "comparison",
            "temporal_growth",
            "temporal_average",
        }


def test_one_registry_instance_reaches_all_finance_pilot_consumers(
    pilot_archive: FinanceArchiveAdapter,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    selected = finance_vnext_operation_registry()
    calls: list[str] = []

    def selected_registry():
        calls.append("registry_factory")
        return selected

    def unexpected_registry():
        pytest.fail("Finance pilot consumer silently rebuilt its operation registry")

    monkeypatch.setattr(runner, "finance_vnext_operation_registry", selected_registry)
    for module in (task_module, realization_module, candidate_module):
        monkeypatch.setattr(module, "finance_vnext_operation_registry", unexpected_registry)

    consumers = {
        "FinanceTaskPlugin": "_registry",
        "ReferenceWorkflowCompiler": "_executor.registry",
        "FinanceNumericCandidateGenerator": "_registry",
        "ReferenceWorkflowVerifier": "_oracle.registry",
        "QualityContractCompiler": "_operation_registry",
        "ProofCarryingSampleCompiler": "_operation_registry",
        "CandidateWorkflowVerifier": "_registry",
    }

    def wrap_constructor(name: str, attribute_path: str) -> None:
        constructor = getattr(runner, name)

        def traced(*args, **kwargs):
            instance = constructor(*args, **kwargs)
            bound = instance
            for attribute in attribute_path.split("."):
                bound = getattr(bound, attribute)
            assert bound is selected, name
            if name == "FinanceTaskPlugin":
                assert instance._compiler._operation_registry is selected
            if name == "ProofCarryingSampleCompiler":
                assert instance._reference_compiler._executor.registry is selected
                assert instance._reference_evaluator._workflow_verifier._oracle.registry is selected
            calls.append(name)
            return instance

        monkeypatch.setattr(runner, name, traced)

    for name, attribute_path in consumers.items():
        wrap_constructor(name, attribute_path)

    with (
        patch.object(runner, "finance_plugin_set", wraps=runner.finance_plugin_set) as plugin_spy,
        patch.object(
            runner, "build_release_manifest", wraps=runner.build_release_manifest
        ) as release_spy,
        patch.object(
            task_module,
            "compile_finance_realization_portfolio",
            wraps=task_module.compile_finance_realization_portfolio,
        ) as realization_spy,
    ):
        report = run_finance_pilot(
            pilot_archive,
            FinancePilotConfig(
                task_quotas={"registered_cross_metric_comparison": 1}, mutation_types=()
            ),
            tmp_path / "shared_registry_pilot",
        )
    assert report["candidate_validation"]["clean_accepted"] == 1
    assert all(report["reproducibility"].values())
    assert calls.count("registry_factory") == 1
    assert set(calls) == {"registry_factory", *consumers}
    assert len(plugin_spy.call_args_list) == 2
    assert all(call.args[1] is selected for call in plugin_spy.call_args_list)
    assert len(release_spy.call_args_list) == 2
    assert all(call.kwargs["registry"] is selected for call in release_spy.call_args_list)
    assert len(realization_spy.call_args_list) == 1
    assert all(call.kwargs["registry"] is selected for call in realization_spy.call_args_list)


def test_missing_registered_operation_fails_closed_at_real_entrypoint(
    pilot_archive: FinanceArchiveAdapter,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(runner, "finance_vnext_operation_registry", default_registry)
    output = tmp_path / "missing_registered_operation"
    with pytest.raises(ValueError, match="unknown operation: registered_compare"):
        run_finance_pilot(
            pilot_archive,
            FinancePilotConfig(
                task_quotas={"registered_cross_metric_comparison": 1}, mutation_types=()
            ),
            output,
        )
    assert not output.exists()


def test_explicit_registry_preserves_default_task_and_candidate_identities(
    pilot_archive: FinanceArchiveAdapter,
) -> None:
    selected = finance_vnext_operation_registry()
    config = FinancePilotConfig(
        task_quotas={family: 1 for family in task_module.FinanceTaskPlugin.task_family_ids},
        mutation_types=(),
    )
    evidence = tuple(pilot_archive.iter_evidence())
    bindings = discover_bindings(evidence, config)
    case_sets = tuple(
        build_task_cases(
            bindings,
            evidence,
            distractors_per_task=1,
            hard_distractors_per_task=1,
            use_real_distractors=True,
            task_synthesizer=plugin,
        )
        for plugin in (
            task_module.FinanceTaskPlugin(),
            task_module.FinanceTaskPlugin(registry=selected),
        )
    )
    assert len(case_sets[0]) == 8
    assert case_sets[0] == case_sets[1]
    generators = (
        candidate_module.FinanceNumericCandidateGenerator(),
        candidate_module.FinanceNumericCandidateGenerator(selected),
    )
    for case in case_sets[0]:
        default, injected = (
            generator.generate(case.task.public, InMemoryEvidenceToolRuntime(case.corpus))
            for generator in generators
        )
        assert default == injected
        assert default.trajectory_id == injected.trajectory_id
