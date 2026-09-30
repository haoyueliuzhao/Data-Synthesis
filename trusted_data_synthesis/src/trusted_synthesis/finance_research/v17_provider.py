"""Explicit three-task protocol on the existing exact-byte, no-retry transport."""

from . import v16_provider as transport
from . import v17_adjudication_protocol as protocol
from . import v17_budget as budget

annotation_client = transport.annotation_client


def restore_settled(row, request):
    return transport.restore_settled(row, request, protocol=protocol, version="v17")


def paid_record(request, artifact, row):
    return transport.paid_record(request, artifact, row, protocol=protocol, version="v17")


async def request_once(**kwargs):
    protocol.require(kwargs["request"].get("model") == "deepseek-flash", "fixed flash only")
    return await transport.request_once(**kwargs, protocol=protocol, budget=budget, version="v17")
