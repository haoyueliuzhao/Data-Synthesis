from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable

from trusted_synthesis.core.evaluation.contracts.schema import (
    ContractQualityAssessment,
    QualityContract,
)
from trusted_synthesis.core.evaluation.critic.schema import (
    AcceptabilityLabel,
    AlignmentReport,
    AnnotationSource,
    FailureLocationLabel,
    QualityAnnotation,
    QualityCriticDataset,
    QualityCriticExample,
)
from trusted_synthesis.core.evaluation.quality_vector import QualityVector
from trusted_synthesis.core.evidence.corpus import EvidenceCorpus
from trusted_synthesis.core.task.schema import TaskPackage
from trusted_synthesis.core.trajectory.schema import Trajectory
from trusted_synthesis.hashing import canonical_hash


def build_contract_annotation(
    contract: QualityContract,
    assessment: ContractQualityAssessment,
) -> QualityAnnotation:
    clauses = {item.clause_id: item for item in contract.clauses}
    root_clauses = tuple(
        clauses[item]
        for item in assessment.root_failure_clause_ids
        if item in clauses
    )
    acceptability = {
        "accepted": AcceptabilityLabel.ACCEPT,
        "quarantined": AcceptabilityLabel.QUARANTINE,
        "rejected": AcceptabilityLabel.REJECT,
    }[assessment.decision.value]
    identity = {
        "assessment_id": assessment.assessment_id,
        "contract_hash": contract.contract_hash,
        "acceptability": acceptability.value,
    }
    return QualityAnnotation(
        annotation_id=canonical_hash(identity, prefix="contract_quality_annotation:"),
        source=AnnotationSource.CONTRACT,
        acceptability=acceptability,
        failure_families=tuple(sorted({item.failure_family for item in root_clauses})),
        root_locations=tuple(
            FailureLocationLabel(
                location_type=item.target.target_type,
                location_ref=item.target.target_ref,
            )
            for item in root_clauses
        ),
        confidence=1,
        source_assessment_id=assessment.assessment_id,
    )


def build_quality_critic_example(
    *,
    task: TaskPackage,
    corpus: EvidenceCorpus,
    contract: QualityContract,
    trajectory: Trajectory,
    assessment: ContractQualityAssessment,
    quality_vector: QualityVector,
    candidate_source: str,
    advisory_annotations: tuple[QualityAnnotation, ...] = (),
    metadata: dict[str, object] | None = None,
) -> QualityCriticExample:
    if trajectory.task_id != task.task_id or assessment.trajectory_id != trajectory.trajectory_id:
        raise ValueError("critic example task, trajectory, and assessment do not align")
    contract_annotation = build_contract_annotation(contract, assessment)
    critic_input = {
        "task": task.public.model_dump(mode="json", exclude_none=True),
        "evidence_corpus": [
            item.model_dump(mode="json", exclude_none=True) for item in corpus.evidence
        ],
        "trajectory": trajectory.model_dump(mode="json", exclude_none=True),
        "quality_contract_summary": {
            "contract_hash": contract.contract_hash,
            "clauses": [
                {
                    "clause_kind": item.clause_kind,
                    "severity": item.severity.value,
                    "target_type": item.target.target_type,
                    "diagnostic_dimensions": item.diagnostic_dimensions,
                    "failure_family": item.failure_family,
                }
                for item in contract.clauses
            ],
        },
    }
    identity = {
        "task_id": task.task_id,
        "trajectory_id": trajectory.trajectory_id,
        "contract_hash": contract.contract_hash,
        "candidate_source": candidate_source,
    }
    return QualityCriticExample(
        example_id=canonical_hash(identity, prefix="quality_critic_example:"),
        task_id=task.task_id,
        trajectory_id=trajectory.trajectory_id,
        domain=task.public.domain,
        retrieval_track=task.public.retrieval_track.value,
        planning_track=task.public.planning_track.value,
        candidate_source=candidate_source,
        critic_input=critic_input,
        contract_annotation=contract_annotation,
        quality_vector=quality_vector,
        advisory_annotations=advisory_annotations,
        metadata=dict(metadata or {}),
    )


def make_quality_critic_dataset(
    examples: Iterable[QualityCriticExample],
) -> QualityCriticDataset:
    ordered = tuple(sorted(examples, key=lambda item: item.example_id))
    identity = {
        "example_ids": tuple(item.example_id for item in ordered),
        "schema_version": "quality_critic_dataset.v1",
    }
    return QualityCriticDataset(
        dataset_id=canonical_hash(identity, prefix="quality_critic_dataset:"),
        examples=ordered,
        contract_positive_count=sum(
            item.contract_annotation.acceptability == AcceptabilityLabel.ACCEPT
            for item in ordered
        ),
        contract_negative_count=sum(
            item.contract_annotation.acceptability != AcceptabilityLabel.ACCEPT
            for item in ordered
        ),
        real_agent_count=sum(item.candidate_source == "real_agent" for item in ordered),
        counterfactual_count=sum(
            item.candidate_source == "typed_counterfactual" for item in ordered
        ),
        human_annotation_count=sum(
            annotation.source == AnnotationSource.HUMAN
            for item in ordered
            for annotation in item.advisory_annotations
        ),
        model_advisory_count=sum(
            annotation.source == AnnotationSource.MODEL_ADVISORY
            for item in ordered
            for annotation in item.advisory_annotations
        ),
    )


def evaluate_annotation_alignment(
    examples: Iterable[QualityCriticExample],
) -> AlignmentReport:
    ordered = tuple(examples)
    by_source: dict[AnnotationSource, list[tuple[QualityAnnotation, QualityAnnotation]]] = (
        defaultdict(list)
    )
    for example in ordered:
        for annotation in example.advisory_annotations:
            by_source[annotation.source].append(
                (example.contract_annotation, annotation)
            )
    human = tuple(by_source[AnnotationSource.HUMAN])
    model = tuple(by_source[AnnotationSource.MODEL_ADVISORY])
    identity = {
        "example_ids": tuple(sorted(item.example_id for item in ordered)),
        "human_annotation_ids": tuple(
            sorted(right.annotation_id for _, right in human)
        ),
        "model_annotation_ids": tuple(
            sorted(right.annotation_id for _, right in model)
        ),
    }
    human_agreement = _acceptability_agreement(human)
    model_agreement = _acceptability_agreement(model)
    human_failure_f1 = _failure_f1(human)
    model_failure_f1 = _failure_f1(model)
    human_location = _root_localization(human)
    model_location = _root_localization(model)
    notes = []
    if not human:
        notes.append(
            "No human labels were supplied; model advisory agreement is not human agreement."
        )
    return AlignmentReport(
        report_id=canonical_hash(identity, prefix="quality_alignment_report:"),
        example_count=len(ordered),
        human_annotation_count=len(human),
        model_advisory_count=len(model),
        human_contract_acceptability_agreement=human_agreement,
        model_contract_acceptability_agreement=model_agreement,
        human_failure_classification_f1=human_failure_f1,
        model_failure_classification_f1=model_failure_f1,
        human_root_localization_rate=human_location,
        model_root_localization_rate=model_location,
        human_target_met=(
            None
            if human_agreement is None or human_failure_f1 is None or human_location is None
            else human_agreement > 0.9
            and human_failure_f1 > 0.85
            and human_location > 0.8
        ),
        model_advisory_target_met=(
            None
            if model_agreement is None or model_failure_f1 is None or model_location is None
            else model_agreement > 0.9
            and model_failure_f1 > 0.85
            and model_location > 0.8
        ),
        notes=tuple(notes),
    )


def _acceptability_agreement(
    pairs: tuple[tuple[QualityAnnotation, QualityAnnotation], ...],
) -> float | None:
    if not pairs:
        return None
    return sum(left.acceptability == right.acceptability for left, right in pairs) / len(pairs)


def _failure_f1(
    pairs: tuple[tuple[QualityAnnotation, QualityAnnotation], ...],
) -> float | None:
    if not pairs:
        return None
    expected = {
        (index, family)
        for index, (left, _) in enumerate(pairs)
        for family in left.failure_families
    }
    observed = {
        (index, family)
        for index, (_, right) in enumerate(pairs)
        for family in right.failure_families
    }
    return _set_f1(expected, observed)


def _root_localization(
    pairs: tuple[tuple[QualityAnnotation, QualityAnnotation], ...],
) -> float | None:
    if not pairs:
        return None
    scored = []
    for left, right in pairs:
        expected = {
            (item.location_type, item.location_ref) for item in left.root_locations
        }
        observed = {
            (item.location_type, item.location_ref) for item in right.root_locations
        }
        scored.append(_set_f1(expected, observed))
    return sum(scored) / len(scored)


def _set_f1(expected: set, observed: set) -> float:
    if not expected and not observed:
        return 1.0
    if not expected or not observed:
        return 0.0
    true_positive = len(expected & observed)
    precision = true_positive / len(observed)
    recall = true_positive / len(expected)
    return 0.0 if precision + recall == 0 else 2 * precision * recall / (precision + recall)
