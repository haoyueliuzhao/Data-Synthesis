from __future__ import annotations

import inspect
from dataclasses import dataclass
from typing import Any, Protocol

from trusted_synthesis.core.evaluation.contracts.observation import CandidateObservationIndex
from trusted_synthesis.core.evaluation.contracts.schema import QualityClause
from trusted_synthesis.core.evidence.corpus import EvidenceCorpus
from trusted_synthesis.core.graph.schema import ProofGraph
from trusted_synthesis.core.task.difficulty import (
    TASK_DIFFICULTY_POLICY_VERSION,
    difficulty_level,
    difficulty_score,
    task_structure_features,
)
from trusted_synthesis.core.task.schema import TaskPackage
from trusted_synthesis.core.trajectory.candidate_verifier import CandidateVerificationReport
from trusted_synthesis.core.trajectory.schema import Trajectory
from trusted_synthesis.hashing import canonical_hash


@dataclass(frozen=True)
class ClauseVerificationContext:
    task: TaskPackage
    corpus: EvidenceCorpus
    proof_graph: ProofGraph
    trajectory: Trajectory
    report: CandidateVerificationReport
    observations: CandidateObservationIndex


@dataclass(frozen=True)
class ClauseVerificationOutcome:
    passed: bool
    observed: Any = None
    expected: Any = None
    failure_code: str | None = None
    details: tuple[str, ...] = ()


class ClauseVerifierProtocol(Protocol):
    verifier_id: str
    verifier_version: str

    def verify(
        self,
        clause: QualityClause,
        context: ClauseVerificationContext,
    ) -> ClauseVerificationOutcome: ...


class ClauseVerifierRegistry:
    def __init__(self, verifiers: tuple[ClauseVerifierProtocol, ...] = ()) -> None:
        self._verifiers: dict[str, ClauseVerifierProtocol] = {}
        for verifier in verifiers:
            self.register(verifier)

    def register(self, verifier: ClauseVerifierProtocol) -> None:
        if verifier.verifier_id in self._verifiers:
            raise ValueError(f"clause verifier already registered: {verifier.verifier_id}")
        self._verifiers[verifier.verifier_id] = verifier

    def get(self, verifier_id: str) -> ClauseVerifierProtocol | None:
        return self._verifiers.get(verifier_id)

    def require(self, verifier_id: str) -> ClauseVerifierProtocol:
        verifier = self.get(verifier_id)
        if verifier is None:
            raise ValueError(f"unknown clause verifier: {verifier_id}")
        return verifier

    def manifest(self) -> tuple[dict[str, str], ...]:
        return tuple(
            {
                "verifier_id": verifier.verifier_id,
                "verifier_version": verifier.verifier_version,
                "implementation_hash": canonical_hash(
                    inspect.getsource(type(verifier)), prefix="clause_verifier_impl:"
                ),
            }
            for verifier in sorted(self._verifiers.values(), key=lambda item: item.verifier_id)
        )

    @property
    def manifest_hash(self) -> str:
        return canonical_hash(self.manifest(), prefix="clause_verifier_manifest:")


class _CandidateCheckVerifier:
    verifier_id = "candidate_check.v1"
    verifier_version = "1.0.0"

    def verify(
        self, clause: QualityClause, context: ClauseVerificationContext
    ) -> ClauseVerificationOutcome:
        check_id = str(clause.parameters.get("check_id") or "")
        if not check_id or check_id not in context.observations.checks:
            return ClauseVerificationOutcome(
                passed=False,
                failure_code="candidate_check_missing",
                details=(check_id or "check_id_not_configured",),
            )
        passed = context.observations.checks[check_id]
        details = context.observations.check_details.get(check_id, ())
        detail_token = clause.parameters.get("detail_token")
        if not passed and detail_token:
            relevant = tuple(item for item in details if str(detail_token) in item)
            if relevant:
                details = relevant
            elif details:
                return ClauseVerificationOutcome(
                    passed=True,
                    observed={"check_id": check_id, "target_not_implicated": True},
                    expected=True,
                )
        return ClauseVerificationOutcome(
            passed=passed,
            observed={"check_id": check_id, "passed": passed},
            expected=True,
            failure_code=None if passed else "candidate_check_failed",
            details=details,
        )


class _EvidencePresentVerifier:
    verifier_id = "evidence_present.v1"
    verifier_version = "1.0.0"

    def verify(
        self, clause: QualityClause, context: ClauseVerificationContext
    ) -> ClauseVerificationOutcome:
        evidence_id = clause.target.target_ref
        passed = evidence_id in context.corpus.by_id()
        return ClauseVerificationOutcome(
            passed=passed,
            observed=passed,
            expected=True,
            failure_code=None if passed else "evidence_missing",
            details=() if passed else (evidence_id,),
        )


class _EvidenceSelectedVerifier:
    verifier_id = "evidence_selected.v1"
    verifier_version = "1.0.0"

    def verify(
        self, clause: QualityClause, context: ClauseVerificationContext
    ) -> ClauseVerificationOutcome:
        evidence_id = clause.target.target_ref
        passed = evidence_id in set(context.observations.selected_evidence_ids)
        return ClauseVerificationOutcome(
            passed=passed,
            observed=passed,
            expected=True,
            failure_code=None if passed else "gold_evidence_not_selected",
            details=() if passed else (evidence_id,),
        )


class _ProofEvidenceVerifier:
    verifier_id = "proof_evidence_node.v1"
    verifier_version = "1.0.0"

    def verify(
        self, clause: QualityClause, context: ClauseVerificationContext
    ) -> ClauseVerificationOutcome:
        evidence_id = clause.target.target_ref
        passed = context.proof_graph.contains_evidence(evidence_id)
        return ClauseVerificationOutcome(
            passed=passed,
            observed=passed,
            expected=True,
            failure_code=None if passed else "proof_evidence_node_missing",
            details=() if passed else (evidence_id,),
        )


class _TrackVerifier:
    verifier_id = "task_track.v1"
    verifier_version = "1.0.0"

    def verify(
        self, clause: QualityClause, context: ClauseVerificationContext
    ) -> ClauseVerificationOutcome:
        field = str(clause.parameters.get("field") or "")
        expected = clause.parameters.get("expected")
        observed = getattr(context.task.public, field, None)
        observed_value = getattr(observed, "value", observed)
        passed = observed_value == expected
        return ClauseVerificationOutcome(
            passed=passed,
            observed=observed_value,
            expected=expected,
            failure_code=None if passed else "task_track_mismatch",
        )


class _TaskPatternBindingVerifier:
    verifier_id = "task_pattern_binding.v1"
    verifier_version = "1.0.0"

    def verify(
        self, clause: QualityClause, context: ClauseVerificationContext
    ) -> ClauseVerificationOutcome:
        observed_pattern = context.task.public.metadata.get("task_pattern")
        observed_binding = context.task.oracle.selection_contract.get("pattern_binding")
        expected_pattern = clause.parameters.get("pattern")
        expected_binding = clause.parameters.get("binding")
        if (
            not isinstance(observed_pattern, dict)
            or not isinstance(observed_binding, dict)
            or not isinstance(expected_pattern, dict)
            or not isinstance(expected_binding, dict)
        ):
            return ClauseVerificationOutcome(
                passed=False,
                failure_code="task_pattern_binding_missing",
            )
        role_bindings = observed_binding.get("role_bindings")
        if not isinstance(role_bindings, dict):
            return ClauseVerificationOutcome(
                passed=False,
                failure_code="task_pattern_roles_missing",
            )
        flattened = [
            str(evidence_id)
            for evidence_ids in role_bindings.values()
            if isinstance(evidence_ids, (list, tuple))
            for evidence_id in evidence_ids
        ]
        gold_ids = tuple(context.task.oracle.gold_evidence_ids)
        checks = {
            "pattern_identity": observed_pattern == expected_pattern,
            "binding_identity": observed_binding == expected_binding,
            "role_coverage": len(flattened) == len(gold_ids) and set(flattened) == set(gold_ids),
            "role_uniqueness": len(flattened) == len(set(flattened)),
            "source_graph": observed_binding.get("source_graph_id") == context.proof_graph.graph_id,
            "contract_hash": clause.expected_ref
            == canonical_hash(
                {
                    "pattern": observed_pattern,
                    "binding": observed_binding,
                },
                prefix="task_pattern_binding_contract:",
            ),
        }
        passed = all(checks.values())
        return ClauseVerificationOutcome(
            passed=passed,
            observed=checks,
            expected={key: True for key in checks},
            failure_code=None if passed else "task_pattern_binding_mismatch",
            details=tuple(key for key, value in checks.items() if not value),
        )


class _TaskDifficultyVerifier:
    verifier_id = "task_difficulty.v2"
    verifier_version = "2.0.0"

    def verify(
        self, clause: QualityClause, context: ClauseVerificationContext
    ) -> ClauseVerificationOutcome:
        observed = context.task.public.metadata.get("difficulty_profile")
        expected = clause.parameters.get("expected_profile")
        pattern = context.task.public.metadata.get("task_pattern")
        if not isinstance(observed, dict) or not isinstance(expected, dict):
            return ClauseVerificationOutcome(
                passed=False,
                failure_code="difficulty_profile_missing",
            )
        if not isinstance(pattern, dict):
            return ClauseVerificationOutcome(
                passed=False,
                failure_code="difficulty_pattern_identity_missing",
            )
        structural = task_structure_features(
            context.task.oracle.task_program,
            context.proof_graph,
            context.task.oracle.gold_evidence_ids,
        )
        semantic_constraint_count = float(pattern.get("semantic_constraint_count", -1))
        semantic_alignment_cost = float(observed.get("semantic_alignment_cost", -1))
        pattern_prior_cost = float(pattern.get("difficulty_base_cost", -1))
        score = difficulty_score(
            **structural,
            semantic_constraint_count=semantic_constraint_count,
            semantic_alignment_cost=semantic_alignment_cost,
        )
        level = difficulty_level(score).value
        checks = {
            "profile_frozen": observed == expected,
            "profile_hash": clause.expected_ref
            == canonical_hash(observed, prefix="task_difficulty_profile:"),
            "structural_features": all(
                observed.get(key) == value for key, value in structural.items()
            ),
            "semantic_constraint_count": observed.get("semantic_constraint_count")
            == semantic_constraint_count,
            "pattern_prior_cost": observed.get("pattern_prior_cost") == pattern_prior_cost,
            "pattern_prior_level": observed.get("pattern_prior_level")
            == pattern.get("difficulty_base"),
            "structural_score": observed.get("structural_score") == score,
            "total_score": observed.get("total_score") == score,
            "difficulty_level": observed.get("level") == level,
            "policy_version": observed.get("policy_version") == TASK_DIFFICULTY_POLICY_VERSION,
        }
        passed = all(checks.values())
        return ClauseVerificationOutcome(
            passed=passed,
            observed=checks,
            expected={key: True for key in checks},
            failure_code=None if passed else "difficulty_profile_mismatch",
            details=tuple(key for key, value in checks.items() if not value),
        )


class _ProgramNodeVerifier:
    verifier_id = "program_node_trace.v1"
    verifier_version = "1.0.0"

    def verify(
        self, clause: QualityClause, context: ClauseVerificationContext
    ) -> ClauseVerificationOutcome:
        node_id = clause.target.target_ref
        known_nodes = {node.node_id for node in context.task.oracle.task_program.nodes}
        if node_id not in known_nodes:
            return ClauseVerificationOutcome(
                passed=False,
                failure_code="program_node_missing_from_oracle",
                details=(node_id,),
            )
        aggregate_passed = context.observations.checks.get("program_node_alignment", False)
        details = context.observations.check_details.get("program_node_alignment", ())
        relevant = tuple(item for item in details if f"node:{node_id}" in item)
        if aggregate_passed:
            return ClauseVerificationOutcome(
                passed=True,
                observed={"node_id": node_id, "aligned": True},
                expected=True,
            )
        if relevant:
            return ClauseVerificationOutcome(
                passed=False,
                observed={"node_id": node_id, "aligned": False},
                expected=True,
                failure_code="program_node_trace_failed",
                details=relevant,
            )
        return ClauseVerificationOutcome(
            passed=True,
            observed={"node_id": node_id, "not_implicated": True},
            expected=True,
        )


class _AnswerFieldVerifier:
    verifier_id = "answer_field.v1"
    verifier_version = "1.0.0"

    def verify(
        self, clause: QualityClause, context: ClauseVerificationContext
    ) -> ClauseVerificationOutcome:
        path = clause.target.json_path or "result"
        value: Any = context.trajectory.final_answer
        for part in path.split("."):
            if not isinstance(value, dict) or part not in value:
                return ClauseVerificationOutcome(
                    passed=False,
                    failure_code="answer_field_missing",
                    details=(path,),
                )
            value = value[part]
        return ClauseVerificationOutcome(passed=True, observed=value, expected="present")


class _CitationEvidenceVerifier:
    verifier_id = "citation_evidence.v1"
    verifier_version = "1.0.0"

    def verify(
        self, clause: QualityClause, context: ClauseVerificationContext
    ) -> ClauseVerificationOutcome:
        evidence_id = clause.target.target_ref
        passed = evidence_id in set(context.observations.citation_evidence_ids)
        return ClauseVerificationOutcome(
            passed=passed,
            observed=passed,
            expected=True,
            failure_code=None if passed else "citation_for_evidence_missing",
            details=() if passed else (evidence_id,),
        )


def default_clause_verifier_registry() -> ClauseVerifierRegistry:
    return ClauseVerifierRegistry(
        (
            _CandidateCheckVerifier(),
            _EvidencePresentVerifier(),
            _EvidenceSelectedVerifier(),
            _ProofEvidenceVerifier(),
            _TrackVerifier(),
            _TaskPatternBindingVerifier(),
            _TaskDifficultyVerifier(),
            _ProgramNodeVerifier(),
            _AnswerFieldVerifier(),
            _CitationEvidenceVerifier(),
        )
    )
