"""New publication provenance, with the unchanged parameterized quotient rule."""

from trusted_synthesis.canonical_json import canonical_json_bytes
from trusted_synthesis.domains.finance.qa_vnext.final_public_contract import (
    public_final_contract,
    public_final_schema,
)

from ..finance_qa_vnext_cross_binding.projection import project_entry as frozen_project
from ..finance_qa_vnext_model_execution.models import record, require, sha
from .rules import quotient_rule


def project_entry(entry, condition, rule, contract):
    """Check what was actually shown; do not repair an answer or broaden interpretation."""
    publication = public_final_contract()
    require(
        rule == quotient_rule()
        and condition["final_public_contract_id"] == publication["id"]
        and contract["final_public_contract_id"] == publication["id"],
        "final_projection.frozen_publication_and_rule",
    )
    session = entry["session"]
    requests = []
    for event in session["events"] if session else []:
        request = event["request"]
        schema = request["response_schemas"]["final"]
        require(
            request.get("public_final_contract") == publication and schema == public_final_schema(),
            "final_projection.actual_final_publication_missing_or_changed",
        )
        requests.append(
            {
                "sequence": event["sequence"],
                "request_id": request["id"],
                "public_final_contract_id": publication["id"],
                "displayed_final_schema_sha256": sha(canonical_json_bytes(schema)),
            }
        )
    before = canonical_json_bytes(entry)
    projected = frozen_project(entry, condition, rule, contract)
    require(canonical_json_bytes(entry) == before, "final_projection.source_mutated")
    check = record(
        "final_publication_projection_binding",
        generation_condition_id=condition["id"],
        measurement_application_id=condition["measurement_application_id"],
        public_final_contract_id=publication["id"],
        qualification_id=entry["qualification"]["id"],
        saved_event_request_count=len(requests),
        requests=requests,
        source_projection_id=projected["id"],
        quotient_rule_id=rule["id"],
        quotient_semantics_changed=False,
        post_outcome_rule_extension=False,
        historical_failed_sessions_promoted=False,
    )
    return record(
        "panel_quotient_projection",
        **{key: value for key, value in projected.items() if key not in {"id", "schema_version"}},
        final_publication_binding=check,
    )
