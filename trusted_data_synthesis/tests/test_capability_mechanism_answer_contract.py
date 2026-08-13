from types import SimpleNamespace

from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_mechanism_development import (
    _answer_contract_passes,
)


def _variant(*, include_contract: bool = True) -> SimpleNamespace:
    projection = {"evidence:left": "Left", "evidence:right": "Right"}
    metadata = (
        {
            "answer_projection_contract_version": "v1",
            "agent_contract_guidance": {
                "answer_reference_contract": {
                    "allowed_reference_labels": ("Left", "Right"),
                },
                "answer_field_constraints": {
                    "higher_ref": {"allowed_values": ("Left", "Right", None)},
                },
                "operation_execution_contract": {"contract_version": "v1"},
            },
        }
        if include_contract
        else {}
    )
    artifact = SimpleNamespace(
        answer_projection=projection,
        projected_expected_output={"higher_ref": "Right", "difference": "2"},
        task=SimpleNamespace(
            public=SimpleNamespace(
                metadata=metadata,
                instruction="The final output rule is: higher_ref plus absolute difference.",
            ),
            oracle=SimpleNamespace(selection_contract={"answer_projection": projection}),
        ),
    )
    return SimpleNamespace(artifact=artifact)


def test_mechanism_answer_contract_accepts_projected_public_labels() -> None:
    assert _answer_contract_passes(_variant())


def test_mechanism_answer_contract_rejects_missing_public_contract() -> None:
    assert not _answer_contract_passes(_variant(include_contract=False))
