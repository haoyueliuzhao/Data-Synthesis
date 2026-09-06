"""Separate identities and immutable finite design for Update calibration."""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

from trusted_synthesis.canonical_json import strict_canonical_hash
from trusted_synthesis.domains.finance.qa_vnext.protocol import require
from trusted_synthesis.experiments.finance_qa_vnext_model_execution.models import read_json, sha
from trusted_synthesis.experiments.finance_qa_vnext_model_execution.transport import (
    SYSTEM_PROMPT,
    TransportConfig,
)

STAGE = "finance_qa_vnext_update_public_contract_repair_and_paired_calibration"
BASELINE = "13e19866b894c4018d795a564076a86b8e1edb17"
OLD_RELATIVE = (
    "trusted_data_synthesis/artifacts/qa_vnext_model_execution/representative_v1_final_20260906"
)
OLD_EXECUTION_SHA = "6697418c533ae7f4d8b08b9889a287932607b1425c318d865ca60da7eec172b6"
CALIBRATION_PROMPT = SYSTEM_PROMPT + (
    " This is a read-only single-step calibration. The current pending Observation has "
    "already been verified. This task ONLY tests encoding its complete acceptance. "
    "Return exactly one Update with disposition=accept for the current pending "
    "Observation. Do not return Action, Final, or reject. There is no second attempt "
    "and no execution or State commit. Use only the supplied public Request."
)


def configuration() -> TransportConfig:
    return TransportConfig(
        attempts_per_session=1,
        maximum_pilot_attempts=24,
        system_prompt=CALIBRATION_PROMPT,
    )


def record(kind: str, **fields: Any) -> dict[str, Any]:
    require("id" not in fields and "schema_version" not in fields, "calibration.identity_fields")
    body = {"schema_version": f"qa_vnext_update_calibration_{kind}.v1", **copy.deepcopy(fields)}
    return {
        **body,
        "id": strict_canonical_hash(body, prefix=f"qa_vnext_update_calibration_{kind}:"),
    }


def inventory(directory: Path) -> list[dict[str, Any]]:
    require(directory.is_dir() and not directory.is_symlink(), "calibration.inventory_root")
    members = []
    for path in sorted(directory.rglob("*")):
        require(not path.is_symlink(), "calibration.inventory_symlink")
        if path.is_file():
            data = path.read_bytes()
            members.append(
                {
                    "path": path.relative_to(directory).as_posix(),
                    "bytes": len(data),
                    "sha256": sha(data),
                }
            )
    return members


def read(path: Path) -> Any:
    return read_json(path.read_bytes())
