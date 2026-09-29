"""Read the one-batch explicit proxy authorization; never mutate environment/routes."""

import hashlib
import json
import os
from pathlib import Path

from .contracts import digest

BATCH_ID = "finqa-v10-20260929-new8000-01"
PROXY_URL_SHA256 = "813477bf51a0efb3b5926c3759f01d02cdf25cd70e6cfc7fa186d9d5e1e1d118"
AUTHORIZATION_PATH = Path("transport_proxy_01/authorization/record.json")
USER_REPLY = "授权现有代理验证并恢复"


def checked_proxy(output, plan):
    """None preserves the former direct route; any present bad binding fails closed.

    HTTPS_PROXY is read only after validating the explicit current-batch record.
    No fallback proxy variable, network probe, credentials or environment writes.
    """
    path = Path(output) / AUTHORIZATION_PATH
    if not path.exists():
        return None
    record = json.loads(path.read_bytes())
    if not (
        isinstance(record, dict)
        and record.get("id") == digest({k: v for k, v in record.items() if k != "id"})
        and record.get("schema") == "v10_explicit_proxy_authorization.v1"
        and plan.get("batch_id") == record.get("batch_id") == BATCH_ID
        and record.get("protocol_id") == plan.get("id")
        and isinstance(plan.get("id"), str)
        and bool(plan["id"])
        and record.get("proxy_url_sha256") == PROXY_URL_SHA256
        and isinstance(record.get("authorization"), dict)
        and record["authorization"].get("user_reply") == USER_REPLY
    ):
        raise ValueError("explicit proxy authority or original batch/protocol binding differs")
    proxy = os.environ.get("HTTPS_PROXY")
    if not isinstance(proxy, str) or hashlib.sha256(proxy.encode()).hexdigest() != PROXY_URL_SHA256:
        raise ValueError("HTTPS_PROXY differs from the explicitly authorized proxy hash")
    return proxy
