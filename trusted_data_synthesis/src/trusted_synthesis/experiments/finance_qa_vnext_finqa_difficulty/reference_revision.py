"""Post-batch v2.1: publish the exact Update reference contract, no new sampling.

The v2 Runtime and its frozen 24-session runner remain untouched. This separate
version is offline-verified preparation for a future explicitly registered batch.
It does not replay, repair, relabel, or replace any original model submission.
"""

from trusted_synthesis.domains.finance.qa_vnext.protocol import record

from .runtime import Runtime

VERSION = "finqa_source_numeric_h2.v2.1"
REFERENCE_RULE = (
    "Update.observation is an ID, not an assessment or explanation. "
    "Copy state.pending_observation.id exactly. Express your judgment only in "
    "disposition: accept or reject. Do not write prose in observation. "
    "The Host never fills this field or accepts an observation on your behalf."
)


class ReferenceExplicitRuntime(Runtime):
    """Only public version/reference instructions/schema change; admission unchanged."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        fields = {
            key: value
            for key, value in self.protocol.items()
            if key not in {"id", "schema_version", "version"}
        }
        self.protocol = record("protocol", version=VERSION, **fields)

    def request(self):
        request = super().request()
        observation = request["response_schemas"]["update"]["properties"]["observation"]
        observation["description"] = REFERENCE_RULE
        if self.pending is not None:
            observation["const"] = self.pending["id"]
        request["rules"]["update_reference"] = REFERENCE_RULE
        return record(
            "public_request",
            **{key: value for key, value in request.items() if key not in {"id", "schema_version"}},
        )
