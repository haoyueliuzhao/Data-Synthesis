"""Additive accepted-result bindings from public records only; no task oracle."""

import copy

from trusted_synthesis.domains.finance.qa_vnext.protocol import record, require
from trusted_synthesis.experiments.finance_qa_vnext_finqa_reason_policy.runtime import (
    ReasonPolicyRuntime,
)

VERSION = "finqa_readable_accepted_bindings.v1"
VIEW_KEY = "accepted_result_bindings"
VIEW_SCOPE = (
    "Mechanical restatement of accepted numeric derivations, in acceptance order. "
    "Original IDs are unchanged. No financial role or derived unit is assigned."
)


def source_record(context, source_id):
    fact = next(f for f in context["numeric_catalog"] if f["id"] == source_id)
    fragment = context["related_source_fragments"][fact["segment"]]
    return {
        "numeric_catalog_record": copy.deepcopy(fact),
        "original_fragment": copy.deepcopy(fragment),
    }


def input_record(ref, operation, accepted, context, constants):
    if operation == "read":
        fact = next(f for f in context["numeric_catalog"] if f["id"] == ref)
        return {
            "id": ref,
            "kind": "source",
            "value": fact["token"],
            "exact_value": fact["value"],
            "source_ids": [ref],
        }
    if ref in constants:
        return {
            "id": ref,
            "kind": "constant",
            "value": ref.split(":", 1)[1],
            "exact_value": ref.split(":", 1)[1],
            "source_ids": [],
        }
    claim = accepted[ref]
    return {
        "id": ref,
        "kind": "accepted_claim",
        "value": claim["value"],
        "exact_value": claim["exact_value"],
        "source_ids": copy.deepcopy(claim["lineage"]),
    }


def binding_view(request, public_events):
    """Never reads task, target, gold, financial probes, or model reasons."""
    context, accepted, observations, rows = request["context"], {}, {}, []
    constants = set(request["protocol"]["constants"])
    for event in public_events:
        if not event["admitted"]:
            continue
        if event["observation"] is not None:
            obs = event["observation"]
            action = obs["model_action"]
            inputs = [
                input_record(ref, action["operation"], accepted, context, constants)
                for ref in action["inputs"]
            ]
            displayed_inputs = [
                i["id"] if action["operation"] == "read" else i["value"] for i in inputs
            ]
            observations[obs["id"]] = {
                "operation": action["operation"],
                "operation_submission": event["submission_count"],
                "ordered_inputs": inputs,
                "numeric_derivation_display": action["operation"]
                + "("
                + ", ".join(displayed_inputs)
                + ") -> "
                + obs["value"],
            }
        if event["claim"] is not None:
            claim, update = event["claim"], event["model_submission"]
            require(
                update["kind"] == "update" and update["disposition"] == "accept",
                "view.explicit_accept_record",
            )
            require(
                claim["observation_id"] == update["observation"], "view.accepted_observation_id"
            )
            require(claim["id"] not in accepted, "view.unique_claim_identity")
            rows.append(
                {
                    "claim_id": claim["id"],
                    "value": claim["value"],
                    "exact_value": claim["exact_value"],
                    "actual_expression": copy.deepcopy(claim["expression"]),
                    "source_ids": copy.deepcopy(claim["lineage"]),
                    "sources": [
                        source_record(context, source_id) for source_id in claim["lineage"]
                    ],
                    "execution": copy.deepcopy(observations[claim["observation_id"]]),
                    "acceptance": {
                        "disposition": "accept",
                        "observation_id": update["observation"],
                        "update_submission": event["submission_count"],
                        "update_request_id": event["request_id"],
                    },
                }
            )
            accepted[claim["id"]] = claim
    require(
        list(accepted) == [c["id"] for c in request["state"]["claims"]],
        "view.all_accepted_in_original_order",
    )
    return {"version": VERSION, "scope": VIEW_SCOPE, "results": rows}


def verify_binding_view(request, public_events, view_condition):
    """Check the emitted binding against original records, not inferred financial roles."""
    require(view_condition in {"V0", "V1"}, "view.condition")
    if view_condition == "V0":
        require(VIEW_KEY not in request, "view.V0_unchanged")
        return
    view = request[VIEW_KEY]
    require(set(view) == {"version", "scope", "results"}, "view.fixed_fields")
    require(view["version"] == VERSION and view["scope"] == VIEW_SCOPE, "view.fixed_scope")
    claims = request["state"]["claims"]
    require(
        [r["claim_id"] for r in view["results"]] == [c["id"] for c in claims],
        "view.no_filter_rank_or_value_merge",
    )
    observations = {
        e["observation"]["id"]: e
        for e in public_events
        if e["admitted"] and e["observation"] is not None
    }
    updates = {
        e["claim"]["id"]: e for e in public_events if e["admitted"] and e["claim"] is not None
    }
    for row, claim in zip(view["results"], claims, strict=True):
        require(
            set(row)
            == {
                "claim_id",
                "value",
                "exact_value",
                "actual_expression",
                "source_ids",
                "sources",
                "execution",
                "acceptance",
            },
            "view.row_fields_no_role_assignment",
        )
        require(
            row["value"] == claim["value"] and row["exact_value"] == claim["exact_value"],
            "view.numeric_values_unchanged",
        )
        require(
            row["actual_expression"] == claim["expression"]
            and row["source_ids"] == claim["lineage"],
            "view.actual_expression_and_lineage",
        )
        created, accepted_at = observations[claim["observation_id"]], updates[claim["id"]]
        action = created["observation"]["model_action"]
        execution = row["execution"]
        require(
            execution["operation"] == action["operation"]
            and execution["operation_submission"] == created["submission_count"],
            "view.actual_operation",
        )
        require(
            [i["id"] for i in execution["ordered_inputs"]] == action["inputs"],
            "view.ordered_full_input_ids",
        )
        earlier_claims = {
            e["claim"]["id"]: e["claim"]
            for e in public_events
            if e["admitted"]
            and e["claim"] is not None
            and e["submission_count"] < created["submission_count"]
        }
        expected_inputs = [
            input_record(
                ref,
                action["operation"],
                earlier_claims,
                request["context"],
                set(request["protocol"]["constants"]),
            )
            for ref in action["inputs"]
        ]
        require(
            execution["ordered_inputs"] == expected_inputs,
            "view.inputs_at_execution_not_current_intent",
        )
        require(
            row["sources"] == [source_record(request["context"], ref) for ref in claim["lineage"]],
            "view.original_source_fragments",
        )
        require(
            row["acceptance"]
            == {
                "disposition": "accept",
                "observation_id": claim["observation_id"],
                "update_submission": accepted_at["submission_count"],
                "update_request_id": accepted_at["request_id"],
            },
            "view.original_acceptance",
        )
    require(view == binding_view(request, public_events), "view.exact_mechanical_reconstruction")


class ReadableBindingRuntime(ReasonPolicyRuntime):
    def __init__(self, *args, view_condition, **kwargs):
        require(view_condition in {"V0", "V1"}, "view.condition")
        self.view_condition = view_condition
        super().__init__(*args, expression_condition="P", **kwargs)

    def request(self):
        request = super().request()
        if self.view_condition == "V1":
            request[VIEW_KEY] = binding_view(request, self.events)
            return record(
                "public_request",
                **{k: v for k, v in request.items() if k not in {"id", "schema_version"}},
            )
        return request
