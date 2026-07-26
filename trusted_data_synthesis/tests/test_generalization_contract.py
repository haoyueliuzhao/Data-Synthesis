from __future__ import annotations

from pathlib import Path

from trusted_synthesis import __version__
from trusted_synthesis.architecture.generalization import (
    assert_generalization_contract,
    audit_generalization_contract,
)
from trusted_synthesis.core.adapters import AdapterCapability
from trusted_synthesis.core.operations.registry import default_registry
from trusted_synthesis.core.release import SplitPolicy, build_release_manifest


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


def test_release_manifest_freezes_passing_generalization_audit() -> None:
    manifest = build_release_manifest(
        release_id="release:generalization_contract_test",
        tasks=(),
        adapters=(_ContractAdapter(),),
        registry=default_registry(),
        split_policy=SplitPolicy(policy_id="generalization_contract_test"),
        source_build_ids={"fixture": "fixture_build_v1"},
    )

    assert manifest.framework_version == __version__ == "0.4.0"
    assert manifest.metadata["generalization_contract_version"] == "generalization_contract.v1.1"
    assert manifest.metadata["core_domain_import_count"] == 0
    assert manifest.metadata["core_domain_branch_count"] == 0
    assert manifest.metadata["core_domain_field_access_count"] == 0
