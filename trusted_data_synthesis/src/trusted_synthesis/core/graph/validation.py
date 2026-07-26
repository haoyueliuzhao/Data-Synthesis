from __future__ import annotations

from collections.abc import Mapping

from pydantic import BaseModel, ConfigDict

from trusted_synthesis.core.evidence.payloads import DerivedResult
from trusted_synthesis.core.evidence.schema import EvidenceBundle, EvidenceItem
from trusted_synthesis.core.graph.schema import NodeKind, ProofGraph


class ProofGraphCheck(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    check_id: str
    passed: bool
    details: tuple[str, ...] = ()


class ProofGraphValidationReport(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    graph_id: str
    checks: tuple[ProofGraphCheck, ...]

    @property
    def passed(self) -> bool:
        return all(check.passed for check in self.checks)


class ProofGraphValidator:
    """Validate proof content, derivation closure, and exact source localization."""

    def validate(
        self,
        graph: ProofGraph,
        bundle: EvidenceBundle,
        evidence_ids: tuple[str, ...] | None = None,
    ) -> ProofGraphValidationReport:
        by_id = {item.evidence_id: item for item in bundle.evidence}
        requested = evidence_ids or tuple(by_id)
        nodes = {node.node_id: node for node in graph.nodes}
        relations = {(edge.source_id, edge.relation, edge.target_id) for edge in graph.edges}
        missing_bundle = tuple(sorted(set(requested) - set(by_id)))
        missing_nodes = tuple(
            sorted(
                evidence_id
                for evidence_id in requested
                if evidence_id not in nodes or nodes[evidence_id].kind != NodeKind.EVIDENCE
            )
        )
        payload_failures = []
        relation_failures = []
        derivation_failures = []
        for evidence_id in requested:
            evidence = by_id.get(evidence_id)
            node = nodes.get(evidence_id)
            if evidence is None or node is None:
                continue
            expected_properties = {
                "assertion_id": evidence.assertion_id,
                "evidence_version_id": evidence.evidence_version_id,
                "evidence_kind": evidence.evidence_kind.value,
                "payload": evidence.payload.model_dump(mode="json", exclude_none=True),
                "epistemic_status": evidence.epistemic_status.value,
            }
            if node.kind != NodeKind.EVIDENCE or node.properties != expected_properties:
                payload_failures.append(evidence_id)
            relation_failures.extend(self._relation_failures(evidence, nodes, relations))
            expected_parents = set(evidence.provenance.parent_evidence_ids)
            observed_parents = {
                target
                for source, relation, target in relations
                if source == evidence_id and relation == "DERIVED_FROM"
            }
            payload_parents = (
                set(evidence.payload.input_evidence_ids)
                if isinstance(evidence.payload, DerivedResult)
                else expected_parents
            )
            if observed_parents != expected_parents or payload_parents != expected_parents:
                derivation_failures.append(evidence_id)
        checks = (
            _check("proof_bundle_coverage", not missing_bundle, missing_bundle),
            _check("proof_evidence_nodes", not missing_nodes, missing_nodes),
            _check(
                "proof_evidence_payload_version",
                not payload_failures,
                tuple(sorted(payload_failures)),
            ),
            _check(
                "proof_required_relations",
                not relation_failures,
                tuple(sorted(relation_failures)),
            ),
            _check(
                "proof_derivation_consistency",
                not derivation_failures,
                tuple(sorted(derivation_failures)),
            ),
        )
        return ProofGraphValidationReport(graph_id=graph.graph_id, checks=checks)

    @staticmethod
    def _relation_failures(
        evidence: EvidenceItem,
        nodes: Mapping[str, object],
        relations: set[tuple[str, str, str]],
    ) -> list[str]:
        subject_id = f"subject:{evidence.domain}:{evidence.subject.subject_id}"
        predicate_id = f"predicate:{evidence.domain}:{evidence.predicate}"
        source_id = f"source:{evidence.domain}:{evidence.source.source_id}"
        locator_id = f"locator:{evidence.domain}:{evidence.source_locator.locator_hash}"
        required = {
            (subject_id, "HAS_EVIDENCE", evidence.evidence_id),
            (evidence.evidence_id, "ASSERTS", predicate_id),
            (evidence.evidence_id, "FROM_SOURCE", source_id),
            (evidence.evidence_id, "LOCATED_AT", locator_id),
        }
        temporal = evidence.temporal_context.model_dump(mode="json", exclude_none=True)
        if temporal:
            from trusted_synthesis.hashing import canonical_hash

            required.add(
                (
                    evidence.evidence_id,
                    "IN_TIME",
                    f"time:{evidence.domain}:{canonical_hash(temporal)}",
                )
            )
        if evidence.scope:
            from trusted_synthesis.hashing import canonical_hash

            scope_data = evidence.scope.model_dump(mode="json", exclude_none=True)
            required.add(
                (
                    evidence.evidence_id,
                    "APPLIES_TO",
                    f"scope:{evidence.domain}:{canonical_hash(scope_data)}",
                )
            )
        if evidence.definition.definition_id:
            required.add(
                (
                    evidence.evidence_id,
                    "HAS_DEFINITION",
                    f"definition:{evidence.domain}:{evidence.definition.definition_id}",
                )
            )
        failures = [
            f"{evidence.evidence_id}:{relation}:{target}"
            for source, relation, target in required
            if (source, relation, target) not in relations
            or source not in nodes
            or target not in nodes
        ]
        locator = nodes.get(locator_id)
        if (
            locator is None
            or getattr(locator, "kind", None) != NodeKind.LOCATOR
            or getattr(locator, "properties", None)
            != evidence.source_locator.model_dump(mode="json", exclude_none=True)
        ):
            failures.append(f"{evidence.evidence_id}:locator_payload_mismatch")
        return failures


def _check(check_id: str, passed: bool, details: tuple[str, ...] = ()) -> ProofGraphCheck:
    return ProofGraphCheck(check_id=check_id, passed=passed, details=details)
