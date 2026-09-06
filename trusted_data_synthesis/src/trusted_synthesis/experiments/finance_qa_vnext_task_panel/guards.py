"""Stage-specific zero-Student guards, plus zero-execution preparation/analysis."""

from __future__ import annotations

import socket
from contextlib import ExitStack, contextmanager
from typing import Any
from unittest.mock import patch

import torch

from trusted_synthesis.domains.finance.qa_vnext.program_adapter import ProgramTaskAdapter
from trusted_synthesis.domains.finance.qa_vnext.runtime import PublicQARuntime
from trusted_synthesis.domains.finance.qa_vnext.share_adapter import ShareTaskAdapter

from ..finance_qa_vnext_model_execution import runner as online_runner
from ..finance_qa_vnext_model_execution import transport
from ..finance_qa_vnext_model_execution.models import record, require


@contextmanager
def execution_guard(*, online: bool):
    counts = {}

    def forbidden(name):
        counts[name] = 0

        def stop(*args: Any, **kwargs: Any):
            counts[name] += 1
            raise RuntimeError("task_panel.forbidden." + name)

        return stop

    paths = [
        (torch.nn.Module, "__init__", "student_module_construction"),
        (torch, "load", "student_weight_load"),
        (torch.cuda, "_lazy_init", "cuda_initialization"),
    ]
    if not online:
        paths.extend(
            [
                (transport.HttpxSender, "send", "provider_send"),
                (transport.OnlineModelCallback, "generate", "model_callback"),
                (online_runner, "_credential", "credential_loader"),
                (PublicQARuntime, "__init__", "finance_runtime_construction"),
                (ProgramTaskAdapter, "execute", "program_operation_execute"),
                (ShareTaskAdapter, "execute", "share_operation_execute"),
                (socket.socket, "connect", "socket_connect"),
                (socket.socket, "connect_ex", "socket_connect_ex"),
                (socket, "create_connection", "socket_create_connection"),
            ]
        )
    require(not torch.cuda.is_initialized(), "task_panel.cuda_preinitialized")
    with ExitStack() as stack:
        for owner, attribute, name in paths:
            stack.enter_context(patch.object(owner, attribute, forbidden(name)))
        yield counts


def guard_report(counts: dict[str, int], *, phase: str) -> dict[str, Any]:
    require(
        not any(counts.values()) and not torch.cuda.is_initialized(), "task_panel.guard_failure"
    )
    return record(
        "task_panel_execution_guards",
        phase=phase,
        forbidden_path_call_counts=counts,
        all_zero=True,
        cuda_initialized=False,
        scope="instrumented entry points; not a formal isolation proof for arbitrary code",
    )
