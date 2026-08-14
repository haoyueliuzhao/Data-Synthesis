from trusted_synthesis.experiments.vtdo_experiment.phase1_multitier_runtime_resolution import (  # noqa: E501
    RuntimeResolutionStage,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_stable_submechanism_support import (  # noqa: E501
    _runtime_resolution_stage,
)


def test_stable_support_stage_adapter_is_explicit_and_total() -> None:
    assert _runtime_resolution_stage("development") == RuntimeResolutionStage.RESIDUAL_DEVELOPMENT
    assert _runtime_resolution_stage("confirmation") == RuntimeResolutionStage.HELDOUT_CONFIRMATION
