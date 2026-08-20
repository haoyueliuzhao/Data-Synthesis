from __future__ import annotations

import json
from pathlib import Path

from trusted_synthesis.runtime.agent.prospective_thinking import (
    PROSPECTIVE_THINKING_MODE_POLICY,
    bind_prospective_thinking,
)
from trusted_synthesis.runtime.agent.schema import AgentModelConfig


def test_prospective_flash_profile_is_thinking_bound() -> None:
    package_root = Path(__file__).resolve().parents[1]
    payload = json.loads(
        (package_root / "config" / "deepseek_v4_flash_agent_thinking_v1.json").read_text(
            encoding="utf-8"
        )
    )

    config = AgentModelConfig.model_validate(payload["model"])
    binding = bind_prospective_thinking(config)

    assert config.model == "deepseek-v4-flash"
    assert config.fallback_models == ()
    assert config.require_requested_model is True
    assert binding.model_config_id == config.public_manifest_hash
    assert binding.policy_id == PROSPECTIVE_THINKING_MODE_POLICY.policy_id
