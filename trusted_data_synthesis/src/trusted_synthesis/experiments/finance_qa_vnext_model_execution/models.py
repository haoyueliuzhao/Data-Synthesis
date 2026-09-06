"""Identities for this online experiment, separate from both public protocol and old pilots."""

from __future__ import annotations

import copy
import hashlib
import json
from typing import Any

from trusted_synthesis.canonical_json import canonical_json_bytes, strict_canonical_hash
from trusted_synthesis.domains.finance.qa_vnext.protocol import ProtocolError, require

STAGE = "finance_qa_vnext_representative_model_execution_and_export_pilot"
VERSION = "1.0.0"
PARENT_COMMIT = "fadcf13f91fbbff1ee9ddfcd8784627b3dd11373"
TASK_GROUPS = {
    "C": "registered_cross_metric_comparison",
    "B": "derived_growth_absolute_spread",
    "S": "source_explicit_part_whole_share",
}


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def record(kind: str, **fields: Any) -> dict[str, Any]:
    require("id" not in fields and "schema_version" not in fields, "online.identity_fields")
    body = {"schema_version": f"qa_vnext_model_execution_{kind}.v1", **copy.deepcopy(fields)}
    return {**body, "id": strict_canonical_hash(body, prefix=f"qa_vnext_model_execution_{kind}:")}


def identity(value: dict[str, Any], kind: str) -> None:
    expected = record(kind, **{k: v for k, v in value.items() if k not in {"id", "schema_version"}})
    require(
        canonical_json_bytes(value) == canonical_json_bytes(expected), "online.identity." + kind
    )


def read_json(data: bytes) -> Any:
    def unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        value: dict[str, Any] = {}
        for key, item in pairs:
            require(key not in value, "online.json_duplicate_key")
            value[key] = item
        return value

    def nonfinite(value: str) -> Any:
        raise ProtocolError("online.json_nonfinite")

    return json.loads(data, object_pairs_hook=unique, parse_constant=nonfinite)
