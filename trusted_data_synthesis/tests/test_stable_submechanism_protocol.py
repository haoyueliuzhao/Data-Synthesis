from __future__ import annotations

from copy import deepcopy

import pytest

from trusted_synthesis.experiments.vtdo_experiment.phase1_stable_submechanism_protocol import (  # noqa: E501
    _verify_historical_lineage,
)


def _historical_inputs() -> tuple[dict[str, object], ...]:
    development_contract: dict[str, object] = {"contract_id": "development"}
    development_report: dict[str, object] = {
        "contract_id": "development",
        "primary_information_geometry_ready": True,
    }
    confirmation_contract: dict[str, object] = {
        "contract_id": "confirmation",
        "source_development_contract_id": "development",
    }
    confirmation_report: dict[str, object] = {
        "contract_id": "confirmation",
        "primary_information_geometry_confirmed": False,
        "pro_sparse_anchor_authorized": False,
        "failure_codes": ["residual_condition_number"],
        "primary_spectrum": {
            "parent_information_share": {
                "finance.candidate_verification_and_repair": 0.0,
            }
        },
    }
    return (
        development_contract,
        development_report,
        confirmation_contract,
        confirmation_report,
    )


def test_historical_lineage_requires_frozen_development_success() -> None:
    values = list(deepcopy(_historical_inputs()))
    values[1]["primary_information_geometry_ready"] = False

    with pytest.raises(ValueError, match="did not pass its frozen geometry"):
        _verify_historical_lineage(*values)


def test_historical_lineage_requires_diagnosed_zero_information_parent() -> None:
    values = list(deepcopy(_historical_inputs()))
    spectrum = values[3]["primary_spectrum"]
    assert isinstance(spectrum, dict)
    parent_share = spectrum["parent_information_share"]
    assert isinstance(parent_share, dict)
    parent_share["finance.candidate_verification_and_repair"] = 0.05

    with pytest.raises(ValueError, match="zero-information parent"):
        _verify_historical_lineage(*values)


def test_historical_lineage_accepts_the_frozen_v25_29_diagnosis() -> None:
    _verify_historical_lineage(*_historical_inputs())
