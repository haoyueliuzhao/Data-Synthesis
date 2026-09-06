"""Fail closed on forbidden execution paths during preparation and adaptation."""

from __future__ import annotations

import builtins
import io
import os
import socket
from contextlib import ExitStack, contextmanager
from pathlib import Path
from typing import Any
from unittest.mock import patch

import torch

from trusted_synthesis.domains.finance.qa_vnext import measurement
from trusted_synthesis.domains.finance.qa_vnext.program_adapter import ProgramTaskAdapter
from trusted_synthesis.domains.finance.qa_vnext.runtime import PublicQARuntime
from trusted_synthesis.domains.finance.qa_vnext.share_adapter import ShareTaskAdapter

from ..finance_qa_vnext_model_execution import qualification, runner, transport
from .core import assets, record


@contextmanager
def zero_execution_guard():
    """Counters are observed forbidden-path invocations, not declared budgets."""
    counts: dict[str, int] = {}

    def forbidden(name: str):
        counts[name] = 0

        def fail(*args: Any, **kwargs: Any):
            counts[name] += 1
            raise RuntimeError("length.forbidden_execution." + name)

        return fail

    paths = [
        (transport.HttpxSender, "send", "provider_send"),
        (transport.OnlineModelCallback, "generate", "model_callback"),
        (runner, "_credential", "credential_loader"),
        (PublicQARuntime, "__init__", "finance_runtime_construction"),
        (ProgramTaskAdapter, "execute", "program_operation_execute"),
        (ShareTaskAdapter, "execute", "share_operation_execute"),
        (qualification, "qualify_session", "qualification_recomputation"),
        (measurement, "audit_session", "domain_audit_recomputation"),
        (socket.socket, "connect", "socket_connect"),
        (socket.socket, "connect_ex", "socket_connect_ex"),
        (socket, "create_connection", "socket_create_connection"),
        (torch.nn.Module, "__init__", "student_module_construction"),
        (torch, "load", "torch_weight_load"),
        (torch.cuda, "_lazy_init", "cuda_initialization"),
    ]
    env_failure = forbidden("credential_file_read")
    asset_failure = forbidden("unbound_model_file_read")

    def guarded_open(real):
        def checked(file, *args, **kwargs):
            if isinstance(file, (str, bytes, os.PathLike)):
                path = Path(os.fsdecode(file)).absolute()
                if path.name == ".env" or path.name.startswith(".env."):
                    env_failure()
                if path.is_relative_to(assets.MODEL_DIRECTORY) and path.name not in {
                    item[0] for item in assets.TOKENIZER_MEMBERS
                }:
                    asset_failure()
            return real(file, *args, **kwargs)

        return checked

    with ExitStack() as stack:
        for owner, name, label in paths:
            stack.enter_context(patch.object(owner, name, forbidden(label)))
        stack.enter_context(patch.object(builtins, "open", guarded_open(builtins.open)))
        stack.enter_context(patch.object(io, "open", guarded_open(io.open)))
        yield counts


def guard_report(counts: dict[str, int]) -> dict[str, Any]:
    return record(
        "execution_guards",
        forbidden_path_call_counts=dict(sorted(counts.items())),
        all_zero=all(value == 0 for value in counts.values()),
        cuda_initialized=torch.cuda.is_initialized(),
        scope="instrumented entry points, original-file access and explicit CPU tensor checks",
    )
