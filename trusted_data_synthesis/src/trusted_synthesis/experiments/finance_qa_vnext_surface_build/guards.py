"""Only the purpose-scoped strict rewrite sender may open network connections."""

import socket
from contextlib import ExitStack, contextmanager
from contextvars import ContextVar
from unittest.mock import patch

from finraw.llm_client import OpenAICompatibleJsonClient

from ..finance_qa_vnext_task_panel.guards import execution_guard

REWRITE_NETWORK = ContextVar("registered_question_rewrite_network", default=False)


@contextmanager
def rewrite_guard():
    originals = [
        (socket.socket, "connect"),
        (socket.socket, "connect_ex"),
        (socket, "create_connection"),
    ]
    originals = [(owner, name, getattr(owner, name)) for owner, name in originals]
    allowed = {name: 0 for _, name, _ in originals}
    with execution_guard(online=False) as forbidden, ExitStack() as stack:
        forbidden["generic_LLM_client"] = 0

        def deny_generic(*args, **kwargs):
            forbidden["generic_LLM_client"] += 1
            raise RuntimeError("surface.generic_model_client_forbidden")

        stack.enter_context(patch.object(OpenAICompatibleJsonClient, "complete_json", deny_generic))
        for owner, name, original in originals:

            def scoped(*args, _name=name, _original=original, **kwargs):
                if not REWRITE_NETWORK.get():
                    key = "socket_" + _name
                    forbidden[key] += 1
                    raise RuntimeError("surface.unregistered_network")
                allowed[_name] += 1
                return _original(*args, **kwargs)

            stack.enter_context(patch.object(owner, name, scoped))
        yield {
            "forbidden": forbidden,
            "allowed_rewrite_socket_calls": allowed,
            "scope": (
                "instrumented entry points with thread-local sender permission; "
                "not formal isolation"
            ),
        }
