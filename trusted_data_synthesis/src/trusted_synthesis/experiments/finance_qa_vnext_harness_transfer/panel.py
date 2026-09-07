"""Bind exactly four previously source-grounded instances; no new H2 prompt plan."""

from __future__ import annotations

import copy
from pathlib import Path

from trusted_synthesis.core.operations.registry import operation_semantic_contract_hash
from trusted_synthesis.core.operations.schema import OperationInput
from trusted_synthesis.domains.finance.qa_vnext.bound_share_adapter import BoundShareTaskAdapter
from trusted_synthesis.domains.finance.qa_vnext.catalog import _frozen_source_pool
from trusted_synthesis.domains.finance.qa_vnext.program_adapter import ProgramTaskAdapter
from trusted_synthesis.domains.finance.qa_vnext.protocol import record, require
from trusted_synthesis.domains.finance.qa_vnext.runner import build_catalog
from trusted_synthesis.experiments.finance_qa_vnext_cross_binding.source import (
    CONTEXT_FIELDS,
    load_sources,
)

TASKS = {
    "U16": ("S", "unp_2016"),
    "J15": ("S", "jpm_2015"),
    "H24": ("B", "branch_hii_2014_q2_2014_q4"),
    "H13": ("B", "branch_hii_2014_q1_2014_q3"),
}


class CompositionalBoundShare(BoundShareTaskAdapter):
    """Source bridge only: use original semantic checks, not offered-node membership.

    H1 still admits only exact offered actions in StudyRuntime. H2's unchanged
    OpenAdapter constructs proposals and validates current input references first.
    Neither path alters the source arithmetic, Claim metadata or Final QA formula.
    """

    def __init__(self, source):
        super().__init__(source)
        original = self.context
        fields = {
            k: v for k, v in original.items() if k not in {"id", "schema_version", "adapter_id"}
        }
        self.context = record(
            "context",
            **fields,
            adapter_id="harness_transfer_source_bridge.v1",
            source_adapter_context_id=original["id"],
            binding_bridge="Original bound-source semantics; "
            "reference membership belongs to H1 admission",
        )

    def prepare(self, offer, claims):
        operation = offer["operation"]
        require(
            operation in {"relation_sum", "share_ratio", "scale_percent"}, "bound_bridge.operation"
        )
        require(
            offer["parameters"] == ({"method": "sum"} if operation == "relation_sum" else {}),
            "bound_bridge.parameters",
        )
        require(
            offer["operation_contract_id"]
            == operation_semantic_contract_hash(self.registry.require(operation)),
            "bound_bridge.operation_contract",
        )
        accepted = {item["id"]: item for item in claims}
        resolved = []
        for ref in offer["inputs"]:
            if ref["kind"] == "evidence":
                item = self.evidence[ref["ref_id"]]
                content = (
                    {"relation": copy.deepcopy(item), "lineage": [item["id"]]}
                    if item["kind"] == "part_whole"
                    else {
                        **{
                            key: item[key]
                            for key in ("value", "metric", "definition", *CONTEXT_FIELDS)
                        },
                        "lineage": [item["id"]],
                        "producer_operation": None,
                    }
                )
            else:
                require(
                    ref["kind"] == "claim" and ref["ref_id"] in accepted,
                    "bound_bridge.accepted_input",
                )
                item = accepted[ref["ref_id"]]
                self._check_claim(item)
                content = {
                    **item["proposition"]["output"],
                    "producer_operation": item["proposition"]["operation"],
                }
            resolved.append({**ref, **content})
        self._admit(operation, resolved)
        lineage = sorted({key for item in resolved for key in item["lineage"]})
        require(lineage == offer["basis"]["evidence_refs"], "bound_bridge.actual_lineage")
        return {
            "operation": operation,
            "inputs": tuple(OperationInput(ref_id=item["ref_id"], value=item) for item in resolved),
            "parameters": offer["parameters"],
            "lineage": lineage,
            "slot": offer["obligation_id"],
            "operation_contract_id": offer["operation_contract_id"],
        }

    def final_claims(self, claims):
        for claim in claims:
            self._check_claim(claim)
        return [c["id"] for c in claims if c["proposition"]["operation"] == "scale_percent"]


class Panel:
    def __init__(self, root: Path):
        self.root = root
        self.catalog = build_catalog(root)
        self.shares = {
            s.source_key: s for s in load_sources(root) if s.source_key in {"unp_2016", "jpm_2015"}
        }
        pool = _frozen_source_pool(root)
        self.cases, self.references = {}, {}
        for key in ("H24", "H13"):
            matches = [
                (row, bundle)
                for row, bundle in pool.branch_candidates
                if row["case_id"] == TASKS[key][1]
            ]
            require(len(matches) == 1, "transfer.exact_existing_hii_case")
            row, bundle = matches[0]
            roles = {}
            for predicate, prefix in (("revenue", "revenue"), ("operating_income", "income")):
                selected = sorted(
                    (e for e in bundle.evidence if e.predicate == predicate),
                    key=lambda e: e.temporal_context.valid_from,
                )
                require(len(selected) == 2, "transfer.exact_temporal_pair")
                roles[prefix + "_earlier"] = (selected[0].evidence_id,)
                roles[prefix + "_later"] = (selected[1].evidence_id,)
            self.cases[key] = self.catalog.compile(
                "derived_growth_absolute_spread",
                bundle,
                roles,
                case_id=row["case_id"],
                source_binding=self.catalog.bind_frozen_source(
                    root, bundle, case_id=row["case_id"]
                ),
            )
            self.references[key] = copy.deepcopy(row)  # Preparation only; never a Request field.
        require(
            self.references["H24"]["numeric_relationship"] == "mixed_sign"
            and self.references["H13"]["near_equal_growth"] is True,
            "transfer.fixed_numeric_conditions",
        )

    def adapter(self, key):
        require(key in TASKS, "transfer.task_key")
        if TASKS[key][0] == "S":
            return CompositionalBoundShare(self.shares[TASKS[key][1]])
        return ProgramTaskAdapter(self.cases[key], self.catalog.registry)

    def bindings(self):
        result = []
        for key, (family, source) in TASKS.items():
            adapter = self.adapter(key)
            result.append(
                record(
                    "transfer_source_binding",
                    task_key=key,
                    family=family,
                    existing_source_key=source,
                    task_id=adapter.context["task_id"],
                    context_id=adapter.context["id"],
                    source_binding=adapter.context["source_binding"],
                    numeric=adapter.context["numeric"],
                    historical_reference=self.references.get(key),
                    historical_binding_is_not_new_model_coverage=True,
                    usage="known_source_cross_instance_development_not_blindtest",
                )
            )
        require(len({r["task_id"] for r in result}) == 4, "transfer.four_distinct_tasks")
        return result
