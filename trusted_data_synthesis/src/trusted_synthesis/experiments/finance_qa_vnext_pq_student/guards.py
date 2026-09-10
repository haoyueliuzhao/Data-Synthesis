"""Offline Student execution guards; GPU is allowed, network and credentials are not."""

import builtins
import io
import os
import socket
from contextlib import ExitStack, contextmanager
from pathlib import Path
from unittest.mock import patch

from .plan import record, require


@contextmanager
def offline_guard(forbidden_paths=()):
    counts = {}
    forbidden = {Path(path).resolve() for path in forbidden_paths}
    original_open = builtins.open
    original_io_open = io.open
    original_os_open = os.open

    def blocked(name):
        counts[name] = 0

        def fail(*args, **kwargs):
            counts[name] += 1
            raise RuntimeError("pq_offline.forbidden." + name)

        return fail

    def check_file(file):
        if isinstance(file, (str, bytes, Path)):
            path = Path(file.decode() if isinstance(file, bytes) else file).resolve()
            if path in forbidden or path.name == ".env":
                counts["private_or_credential_file_read"] += 1
                raise PermissionError("pq_offline.private_file")

    def checked_open(file, *args, **kwargs):
        check_file(file)
        return original_open(file, *args, **kwargs)

    def checked_io_open(file, *args, **kwargs):
        check_file(file)
        return original_io_open(file, *args, **kwargs)

    def checked_os_open(file, *args, **kwargs):
        check_file(file)
        return original_os_open(file, *args, **kwargs)

    counts["private_or_credential_file_read"] = 0
    with ExitStack() as stack:
        stack.enter_context(patch.object(socket.socket, "connect", blocked("socket_connect")))
        stack.enter_context(patch.object(socket.socket, "connect_ex", blocked("socket_connect_ex")))
        stack.enter_context(
            patch.object(socket, "create_connection", blocked("socket_create_connection"))
        )
        stack.enter_context(patch.object(builtins, "open", checked_open))
        stack.enter_context(patch.object(io, "open", checked_io_open))
        stack.enter_context(patch.object(os, "open", checked_os_open))
        yield counts


def report(counts, phase):
    require(not any(counts.values()), "pq_offline.no_forbidden_calls")
    return record(
        "offline_student_guards",
        phase=phase,
        calls=counts,
        all_zero=True,
        provider_calls=0,
        GPU_explicitly_allowed=True,
        scope=(
            "instrumented Python entry points, local-only model loading; "
            "not arbitrary-code isolation proof"
        ),
    )
