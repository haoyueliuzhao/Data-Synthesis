from __future__ import annotations

from pathlib import Path

import pytest

from trusted_synthesis import __version__
from trusted_synthesis.architecture.generalization import (
    assert_generalization_contract,
    audit_generalization_contract,
)
from trusted_synthesis.core.adapters import AdapterCapability
from trusted_synthesis.core.operations.registry import default_registry
from trusted_synthesis.core.release import SplitPolicy, build_release_manifest
from trusted_synthesis.experiments.cross_domain_contract_suite import (
    run_cross_domain_contract_suite,
)


class _ContractAdapter:
    adapter_id = "contract_fixture.v1"
    domain = "contract_fixture"

    @staticmethod
    def capability_manifest() -> tuple[AdapterCapability, ...]:
        return (AdapterCapability.EVIDENCE_STREAM,)


def test_core_has_no_domain_dependency_or_domain_interpretation() -> None:
    report = assert_generalization_contract(Path("src"))

    assert report.passed
    assert report.core_domain_import_count == 0
    assert report.core_domain_branch_count == 0
    assert report.core_domain_field_access_count == 0


def test_generalization_guard_fails_closed_on_all_boundary_classes(tmp_path: Path) -> None:
    core = tmp_path / "src" / "trusted_synthesis" / "core"
    core.mkdir(parents=True)
    (tmp_path / "src" / "trusted_synthesis" / "domains" / "finance").mkdir(parents=True)
    (core / "bad.py").write_text(
        "\n".join(
            (
                "from trusted_synthesis.domains.finance import FinanceSemanticPolicy",
                "def choose(item, domain):",
                "    if domain == 'finance':",
                "        return item.currency",
                "    return None",
            )
        ),
        encoding="utf-8",
    )

    report = audit_generalization_contract(tmp_path / "src")

    assert not report.passed
    assert report.core_domain_import_count == 1
    assert report.core_domain_branch_count == 1
    assert report.core_domain_field_access_count == 1


def test_generalization_guard_catches_indirect_bypasses_across_common_packages(
    tmp_path: Path,
) -> None:
    package = tmp_path / "src" / "trusted_synthesis"
    for name in ("core", "runtime", "architecture", "domains/finance", "domains/medical"):
        (package / name).mkdir(parents=True)
    (package / "core" / "relative.py").write_text(
        "from ..domains.finance import FinancePolicy\n", encoding="utf-8"
    )
    (package / "runtime" / "dynamic.py").write_text(
        "\n".join(
            (
                "import importlib",
                "TARGET = 'trusted_synthesis.domains.medical'",
                "ALIAS = TARGET",
                "plugin = importlib.import_module(ALIAS)",
            )
        ),
        encoding="utf-8",
    )
    (package / "architecture" / "dispatch.py").write_text(
        "\n".join(
            (
                "TARGET = 'finance'",
                "DOMAIN_ALIAS = TARGET",
                "FIELD = 'currency'",
                "FIELD_ALIAS = FIELD",
                "handlers = {DOMAIN_ALIAS: object()}",
                "def choose(domain, context):",
                "    if domain == DOMAIN_ALIAS:",
                "        return context[FIELD_ALIAS]",
                "    return None",
            )
        ),
        encoding="utf-8",
    )

    report = audit_generalization_contract(tmp_path / "src")

    assert not report.passed
    assert report.scanned_packages == ("core", "runtime", "architecture")
    assert report.discovered_domains == ("finance", "medical")
    assert report.core_domain_import_count == 2
    assert report.dynamic_domain_import_count == 1
    assert report.core_domain_branch_count == 2
    assert report.domain_dispatch_count == 1
    assert report.core_domain_field_access_count == 1


def test_release_manifest_freezes_passing_generalization_audit() -> None:
    contracts = run_cross_domain_contract_suite()
    manifest = build_release_manifest(
        release_id="release:generalization_contract_test",
        tasks=(),
        adapters=(_ContractAdapter(),),
        registry=default_registry(),
        split_policy=SplitPolicy(policy_id="generalization_contract_test"),
        source_build_ids={"fixture": "fixture_build_v1"},
        domain_plugin_sets=contracts.plugin_sets,
        cross_domain_contract_suite=contracts.result,
    )

    assert manifest.framework_version == __version__ == "0.9.0"
    assert manifest.metadata["generalization_contract_version"] == "generalization_contract.v1.2"
    assert manifest.metadata["core_domain_import_count"] == 0
    assert manifest.metadata["core_domain_branch_count"] == 0
    assert manifest.metadata["core_domain_field_access_count"] == 0
    assert manifest.mutation_taxonomy_manifest_hash
    assert manifest.quality_contract_runtime_version == "quality_contract_runtime.v1"
    assert manifest.quality_contract_compiler_versions == ("quality_contract_compiler.v5",)
    assert manifest.proof_compiler_versions == ("proof_carrying_compiler.v4",)
    assert set(manifest.quality_contract_hashes) == set(contracts.result.quality_contract_hashes)
    assert set(manifest.proof_certificate_hashes) == set(contracts.result.proof_certificate_hashes)
    assert manifest.clause_verifier_manifest_hashes
    assert manifest.counterfactual_operator_manifest_hashes
    assert manifest.cross_domain_contract_suite.counterfactual_case_count > 0
    assert manifest.cross_domain_contract_suite.counterfactual_clean_false_positive_count == 0
    assert manifest.cross_domain_contract_suite.counterfactual_detection_f1 > 0.95
    assert manifest.cross_domain_contract_suite.counterfactual_clause_coverage_rate == 1.0
    assert manifest.cross_domain_contract_suite.counterfactual_operator_coverage_rate == 1.0
    assert {item.domain for item in manifest.domain_plugin_sets} == {"legal", "science"}
    assert manifest.source_grounding_verifiers == {}


def test_release_manifest_freezes_executed_cross_domain_contract_suite() -> None:
    contracts = run_cross_domain_contract_suite()
    manifest = build_release_manifest(
        release_id="release:cross_domain_contract_test",
        tasks=(),
        adapters=(_ContractAdapter(),),
        registry=default_registry(),
        split_policy=SplitPolicy(policy_id="cross_domain_contract_test"),
        source_build_ids={"fixture": "fixture_build_v1"},
        domain_plugin_sets=contracts.plugin_sets,
        cross_domain_contract_suite=contracts.result,
    )

    assert manifest.cross_domain_contract_suite == contracts.result
    assert manifest.cross_domain_contract_suite_hash == contracts.result.result_hash
    assert manifest.cross_domain_contract_suite.contract_decision_parity_rate == 1
    assert manifest.cross_domain_contract_suite.quality_contract_count == 2
    assert manifest.cross_domain_contract_suite.proof_certificate_count == 2
    assert {item.domain for item in manifest.domain_plugin_sets} == {"legal", "science"}

    with pytest.raises(ValueError, match="did not pass"):
        build_release_manifest(
            release_id="release:failed_cross_domain_contract_test",
            tasks=(),
            adapters=(_ContractAdapter(),),
            registry=default_registry(),
            split_policy=SplitPolicy(policy_id="failed_cross_domain_contract_test"),
            source_build_ids={"fixture": "fixture_build_v1"},
            domain_plugin_sets=contracts.plugin_sets,
            cross_domain_contract_suite=contracts.result.model_copy(
                update={"status": "failed", "failure_details": ("mutation escaped",)}
            ),
        )

    with pytest.raises(ValueError, match="did not pass"):
        build_release_manifest(
            release_id="release:partial_cross_domain_contract_test",
            tasks=(),
            adapters=(_ContractAdapter(),),
            registry=default_registry(),
            split_policy=SplitPolicy(policy_id="partial_cross_domain_contract_test"),
            source_build_ids={"fixture": "fixture_build_v1"},
            domain_plugin_sets=contracts.plugin_sets,
            cross_domain_contract_suite=contracts.result.model_copy(
                update={"clean_candidate_pass_rate": 0.99}
            ),
        )

    with pytest.raises(ValueError, match="missing plugin sets"):
        build_release_manifest(
            release_id="release:missing_suite_plugins_test",
            tasks=(),
            adapters=(_ContractAdapter(),),
            registry=default_registry(),
            split_policy=SplitPolicy(policy_id="missing_suite_plugins_test"),
            source_build_ids={"fixture": "fixture_build_v1"},
            cross_domain_contract_suite=contracts.result,
        )
