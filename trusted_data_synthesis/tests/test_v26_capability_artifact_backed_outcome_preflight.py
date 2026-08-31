from __future__ import annotations

import tempfile
from dataclasses import dataclass
from pathlib import Path

import pytest

from trusted_synthesis.core.task import authoritative_artifact_backed_outcome as outcome
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_capability_artifact_backed_outcome_preflight as preflight,
)


@dataclass(frozen=True)
class ScriptedFixture:
    frozen: preflight.FrozenInputs
    contract: outcome.ArtifactBackedOutcomeContract
    artifact_root: Path
    catalogs: preflight.Catalogs


@pytest.fixture(scope="module")
def scripted_fixture() -> ScriptedFixture:
    package_root = Path(__file__).resolve().parents[1]
    frozen = preflight._load_frozen_inputs(package_root)
    contract = outcome.contract_from_v2(
        registry=frozen.registry,
        predecessor_contract_id=frozen.predecessor_contract.contract_id,
        manifest=frozen.manifest,
        runner=frozen.runner,
        job_component_sequences=frozen.predecessor_contract.job_component_sequences,
    )
    temporary = tempfile.TemporaryDirectory(prefix="v26-186-test-artifacts-")
    artifact_root = Path(temporary.name)
    catalogs = preflight._scripted_catalogs(
        artifact_root=artifact_root,
        frozen=frozen,
        contract=contract,
    )
    yield ScriptedFixture(
        frozen=frozen,
        contract=contract,
        artifact_root=artifact_root,
        catalogs=catalogs,
    )
    temporary.cleanup()


def test_exact_scripted_artifact_dag(scripted_fixture: ScriptedFixture) -> None:
    evaluation = scripted_fixture.catalogs.evaluation
    assert evaluation.raw_descriptor_count == 192
    assert evaluation.result_descriptor_count == 192
    assert evaluation.artifact_file_count == 384
    assert evaluation.artifact_byte_match_count == 384
    assert evaluation.empirical is False
    assert len(tuple(scripted_fixture.artifact_root.iterdir())) == 384


def test_completed_invalid_factors_remain_independent(
    scripted_fixture: ScriptedFixture,
) -> None:
    audit = preflight._factorization(
        frozen=scripted_fixture.frozen,
        contract=scripted_fixture.contract,
    )
    assert {
        (item.reconstructed_base_valid, item.reconstructed_mechanism_qualified)
        for item in audit.controls
    } == {(True, False), (False, True)}
    assert {item.derived_locus_stages for item in audit.controls} == {
        ("mechanism",),
        ("base_answer",),
    }


def test_invented_failure_loci_reject_after_full_rehash(
    scripted_fixture: ScriptedFixture,
) -> None:
    audit = preflight._locus_audit(
        artifact_root=scripted_fixture.artifact_root,
        frozen=scripted_fixture.frozen,
        contract=scripted_fixture.contract,
        catalogs=scripted_fixture.catalogs,
    )
    assert audit.invented_locus_rejection_count == 2
    assert all(item.fully_rehashed and item.rejected for item in audit.controls)


def test_raw_and_result_byte_substitutions_reject(
    scripted_fixture: ScriptedFixture,
) -> None:
    audit = preflight._artifact_audit(
        artifact_root=scripted_fixture.artifact_root,
        frozen=scripted_fixture.frozen,
        contract=scripted_fixture.contract,
        catalogs=scripted_fixture.catalogs,
    )
    assert audit.changed_byte_rejection_count == 2
    assert {item.target for item in audit.controls} == {"Raw", "Result"}


def test_all_authoritative_parent_injections_reject(
    scripted_fixture: ScriptedFixture,
) -> None:
    audit = preflight._parent_audit(
        artifact_root=scripted_fixture.artifact_root,
        frozen=scripted_fixture.frozen,
        contract=scripted_fixture.contract,
        catalogs=scripted_fixture.catalogs,
    )
    assert audit.parent_types == ("Contract", "Job", "Manifest", "Registry", "Runner")
    assert audit.invalid_parent_rejection_count == 5
    assert all(item.rejected for item in audit.controls)


def test_diagnostic_policies_cannot_enter_exact_empirical_catalog(
    scripted_fixture: ScriptedFixture,
) -> None:
    audit = preflight._admission_audit(
        frozen=scripted_fixture.frozen,
        contract=scripted_fixture.contract,
    )
    assert audit.exact_attack_catalog_size == 192
    assert audit.empirical_evaluation_count == 0
    assert {item.target for item in audit.controls} == {
        "measurement_support_exit",
        "policy_horizon_exhausted",
    }
    assert all(item.fully_rehashed and item.rejected for item in audit.controls)
    assert all(
        item.rejection_reason == "non-reachable terminal policy cannot enter empirical evidence"
        for item in audit.controls
    )


def test_independent_git_tree_leaf_vector() -> None:
    content = b"payload\n"
    rows = (
        {
            "path": "file.txt",
            "kind": "file",
            "executable": False,
            "git_blob_id": preflight._git_blob_id(content),
        },
    )
    assert preflight._git_tree_id(rows) == "5c71942e43e4451d2770e34da7784705c90c63c1"
