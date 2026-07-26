from __future__ import annotations

from copy import deepcopy

from trusted_synthesis.core.evidence.schema import EvidenceItem
from trusted_synthesis.core.trajectory.schema import ActionType, Trajectory
from trusted_synthesis.hashing import canonical_hash

CONTRACT_MUTATION_TYPES = (
    "missing_evidence",
    "time_shift",
    "scope_mismatch",
    "definition_mismatch",
    "wrong_derivation",
    "citation_mismatch",
    "unsupported_claim",
)


def generate_contract_mutations(
    candidate: Trajectory,
    corpus: tuple[EvidenceItem, ...],
) -> tuple[tuple[str, Trajectory], ...]:
    distractors = {item.evidence_id: item for item in corpus if "wrong_" in item.evidence_id}
    mutations = []
    for mutation_type in CONTRACT_MUTATION_TYPES:
        if mutation_type == "missing_evidence":
            mutated = _replace_selection(candidate, None)
        elif mutation_type == "time_shift":
            mutated = _replace_selection(candidate, _find(distractors, "wrong_time"))
        elif mutation_type == "scope_mismatch":
            mutated = _replace_selection(candidate, _find(distractors, "wrong_scope"))
        elif mutation_type == "definition_mismatch":
            mutated = _replace_selection(candidate, _find(distractors, "wrong_definition"))
        elif mutation_type == "wrong_derivation":
            mutated = _wrong_derivation(candidate)
        elif mutation_type == "citation_mismatch":
            mutated = _citation_mismatch(candidate)
        else:
            mutated = _unsupported_claim(candidate)
        mutations.append((mutation_type, _finalize(candidate, mutated, mutation_type)))
    return tuple(mutations)


def _replace_selection(candidate: Trajectory, replacement: EvidenceItem | None) -> Trajectory:
    selected_steps = [step for step in candidate.steps if step.action == ActionType.SELECT_EVIDENCE]
    selected_ids = list(selected_steps[0].evidence_ids)
    selected_ids[0:1] = [replacement.evidence_id] if replacement is not None else []
    steps = []
    for step in candidate.steps:
        if step.action == ActionType.SEARCH and replacement is not None:
            evidence_ids = tuple(dict.fromkeys((*step.evidence_ids, replacement.evidence_id)))
            steps.append(
                step.model_copy(
                    update={
                        "evidence_ids": evidence_ids,
                        "observation": {"matched_count": len(evidence_ids)},
                    }
                )
            )
        elif step.action == ActionType.SELECT_EVIDENCE and step.program_node_id is None:
            steps.append(
                step.model_copy(
                    update={
                        "evidence_ids": tuple(selected_ids),
                        "observation": {"selected_count": len(selected_ids)},
                    }
                )
            )
        else:
            steps.append(step)
    return candidate.model_copy(update={"steps": tuple(steps)})


def _wrong_derivation(candidate: Trajectory) -> Trajectory:
    steps = list(candidate.steps)
    for index, step in enumerate(steps):
        if step.action != ActionType.CALCULATE:
            continue
        result = deepcopy(step.observation.get("result") or {})
        key = next(iter(result))
        value = result[key]
        result[key] = not value if isinstance(value, bool) else f"mutated:{value}"
        steps[index] = step.model_copy(update={"observation": {"result": result}})
        break
    return candidate.model_copy(update={"steps": tuple(steps)})


def _citation_mismatch(candidate: Trajectory) -> Trajectory:
    answer = deepcopy(candidate.final_answer)
    answer["citations"][0]["source_id"] = "unrelated_source"
    return candidate.model_copy(update={"final_answer": answer})


def _unsupported_claim(candidate: Trajectory) -> Trajectory:
    answer = deepcopy(candidate.final_answer)
    answer["claims"] = [
        {
            "claim_id": "unsupported_extension",
            "claim_type": "causal_claim",
            "evidence_ids": list(candidate.steps[-1].evidence_ids),
        }
    ]
    return candidate.model_copy(update={"final_answer": answer})


def _find(distractors: dict[str, EvidenceItem], token: str) -> EvidenceItem:
    return next(item for key, item in sorted(distractors.items()) if token in key)


def _finalize(source: Trajectory, mutated: Trajectory, mutation_type: str) -> Trajectory:
    trajectory_id = canonical_hash(
        {
            "source": source.trajectory_id,
            "mutation_type": mutation_type,
            "steps": [item.model_dump(mode="json") for item in mutated.steps],
            "answer": mutated.final_answer,
        },
        prefix="cross_domain_mutation:",
    )
    return mutated.model_copy(update={"trajectory_id": trajectory_id})
