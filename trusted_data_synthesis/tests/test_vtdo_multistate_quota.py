from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from trusted_synthesis.experiments.counterfactual_finance_fixture import (
    build_finance_counterfactual_case,
)
from trusted_synthesis.experiments.vtdo_experiment import multistate as multistate_module
from trusted_synthesis.experiments.vtdo_experiment.multistate import (
    FINANCE_MULTI_STATE_VERSION,
    FinanceMultiStateConfig,
    build_finance_multi_state_dataset,
)


def test_task_count_is_an_accepted_quota_with_complete_funnel(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    cases = tuple(build_finance_counterfactual_case(index) for index in (1, 2, 3))

    class FakeProvider:
        kg_build_id = "kg:test"

        def __init__(self, *_args, **_kwargs) -> None:
            pass

        def contract_cases(
            self,
            count: int,
            *,
            seed: int,
            require_corpus_disjoint: bool,
        ):
            assert count == 3
            assert seed == 20260731
            assert require_corpus_disjoint
            return cases

    monkeypatch.setattr(
        multistate_module,
        "FinanceArchiveConfig",
        SimpleNamespace(from_json=lambda _path: object()),
    )
    monkeypatch.setattr(multistate_module, "FinanceArchiveAdapter", lambda _config: object())
    monkeypatch.setattr(multistate_module, "FinanceArchiveBindingProvider", FakeProvider)

    report, artifacts = build_finance_multi_state_dataset(
        FinanceMultiStateConfig(
            finance_archive_config_path=tmp_path / "unused.json",
            task_count=2,
            candidate_task_oversampling_factor=1.5,
        ),
        tmp_path / "output",
    )

    assert report.schema_version == FINANCE_MULTI_STATE_VERSION
    assert report.status == "passed"
    assert report.requested_task_count == 2
    assert report.accepted_task_count <= report.attempted_task_count <= 3
    assert report.accepted_task_count == 2
    assert report.rejected_task_count == (
        report.attempted_task_count - report.accepted_task_count
    )
    assert report.strategy_attempt_count >= 3 * report.attempted_task_count
    assert (
        report.strategy_verifier_pass_count + report.strategy_verifier_failure_count
        == report.strategy_attempt_count
    )
    assert 0 <= report.duplicate_state_count < report.strategy_attempt_count
    assert report.adversarial_mutation_rejection_count == 2
    assert report.independent_verifier_pass_rate == pytest.approx(
        report.strategy_verifier_pass_count / report.strategy_attempt_count
    )
    assert 0 < report.independent_verifier_pass_rate <= 1
    assert sum(report.failure_counts.values()) == report.rejected_task_count
    assert len(artifacts) == 2
    assert len({item.omega.task.task_id for item in artifacts}) == 2
    assert all(
        item.state_space_compilation.joint_compilation_artifact_id
        == item.joint_compilation.artifact_id
        for item in artifacts
    )
    assert all(
        item.state_space_compilation.omega_component_manifest
        == item.joint_compilation.component_manifest
        for item in artifacts
    )
    assert all(
        len(item.state_space_compilation.variations) >= item.strategy_attempt_count
        for item in artifacts
    )
