"""Opt into complete Final publication without changing Task, Context or verification."""

from .bound_share_adapter import BoundShareTaskAdapter


class FinalPublishedShareTaskAdapter(BoundShareTaskAdapter):
    public_final_contract_enabled = True
