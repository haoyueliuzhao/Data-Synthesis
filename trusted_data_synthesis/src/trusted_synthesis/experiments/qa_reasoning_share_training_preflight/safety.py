"""Runtime guard for this offline, tokenizer-only and CPU-loss preflight."""

from __future__ import annotations

import os
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import torch

from .models import TrainingPreflightError, record, require


@contextmanager
def offline_cpu_guard() -> Iterator[dict[str, Any]]:
    active = True
    attempts = {"network": 0, "credentials": 0, "model_weights": 0, "cuda_initialization": 0}

    def audit(event: str, args: tuple[Any, ...]) -> None:
        if not active:
            return
        category = None
        if event in {"socket.connect", "socket.getaddrinfo", "socket.sendto"}:
            category = "network"
        if event == "open" and args and isinstance(args[0], (str, bytes, os.PathLike)):
            path = Path(os.fsdecode(args[0]))
            if (
                path.name == ".env"
                or path.name.startswith(".env.")
                or (path.name in {"token", "stored_tokens"} and "huggingface" in str(path))
            ):
                category = "credentials"
            elif path.suffix.lower() in {".safetensors", ".bin", ".pt", ".pth", ".ckpt"}:
                category = "model_weights"
        if category is not None:
            attempts[category] += 1
            raise TrainingPreflightError("scope.forbidden_" + category)

    def blocked_cuda(*args: Any, **kwargs: Any) -> None:
        attempts["cuda_initialization"] += 1
        raise TrainingPreflightError("scope.forbidden_cuda_initialization")

    require(not torch.cuda.is_initialized(), "scope.cuda_already_initialized")
    prior_lazy_init = torch.cuda._lazy_init
    previous_threads = torch.get_num_threads()
    torch.set_num_threads(8)
    torch.cuda._lazy_init = blocked_cuda
    sys.addaudithook(audit)
    result: dict[str, Any] = {}
    try:
        yield result
        require(not any(attempts.values()), "scope.forbidden_attempt")
        require(not torch.cuda.is_initialized(), "scope.cuda_became_initialized")
        result.update(
            record(
                "runtime_scope",
                forbidden_attempt_counts=attempts,
                network_guard_events=["socket.connect", "socket.getaddrinfo", "socket.sendto"],
                credential_and_weight_file_open_guard=True,
                cuda_lazy_initialization_blocked=True,
                CUDA_initialized=False,
                tensor_device="cpu",
                cpu_intraop_threads=8,
                torch_version=torch.__version__,
                Student_model_constructed=False,
                Student_forward_passes=0,
                Student_parameter_updates=0,
                Provider_calls=0,
                new_candidate_runtime_executions=0,
                old_qualification_projection_comparison_reexecuted=False,
                scope_evidence=(
                    "guarded I/O and CUDA entry points plus bounded implementation; "
                    "not a complete sandbox proof"
                ),
            )
        )
    finally:
        active = False
        torch.cuda._lazy_init = prior_lazy_init
        torch.set_num_threads(previous_threads)
