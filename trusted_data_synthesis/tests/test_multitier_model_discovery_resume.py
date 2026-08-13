import json
from pathlib import Path

import pytest

from trusted_synthesis.experiments.vtdo_experiment.phase1_multitier_confirmation import (
    _resolve_stage_model_discovery,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_pro_flash_agent_pilot import (
    ExplorerArm,
)


class _Client:
    def __init__(self) -> None:
        self.calls = 0

    def discover_models(self) -> tuple[str, ...]:
        self.calls += 1
        return ("deepseek-v4-flash", "deepseek-v4-pro")


def test_resume_reuses_frozen_model_discovery_without_provider_call(tmp_path: Path) -> None:
    path = tmp_path / "model_discovery.json"
    path.write_text(
        json.dumps(
            {
                "run_identity": "run:test",
                "model_arm": "flash",
                "requested_model": "deepseek-v4-flash",
                "discovered_models": ["deepseek-v4-flash", "deepseek-v4-pro"],
            }
        ),
        encoding="utf-8",
    )
    client = _Client()

    assert _resolve_stage_model_discovery(
        client,  # type: ignore[arg-type]
        path,
        run_identity="run:test",
        model_arm=ExplorerArm.FLASH,
    ) == ("deepseek-v4-flash", "deepseek-v4-pro")
    assert client.calls == 0


def test_resume_rejects_discovery_from_another_run(tmp_path: Path) -> None:
    path = tmp_path / "model_discovery.json"
    path.write_text(
        json.dumps(
            {
                "run_identity": "run:other",
                "model_arm": "flash",
                "requested_model": "deepseek-v4-flash",
                "discovered_models": ["deepseek-v4-flash"],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="another stage run"):
        _resolve_stage_model_discovery(
            _Client(),  # type: ignore[arg-type]
            path,
            run_identity="run:test",
            model_arm=ExplorerArm.FLASH,
        )
