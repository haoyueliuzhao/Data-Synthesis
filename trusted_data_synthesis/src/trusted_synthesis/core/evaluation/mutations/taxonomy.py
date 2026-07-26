from __future__ import annotations

from trusted_synthesis.core.evaluation.mutations.schema import (
    MutationFamily,
    MutationTaxonomyEntry,
)
from trusted_synthesis.hashing import canonical_hash

GENERIC_MUTATION_TAXONOMY = {
    item.mutation_id: item
    for item in (
        MutationTaxonomyEntry(
            mutation_id="missing_evidence",
            family=MutationFamily.EVIDENCE,
            universal_error=True,
            description="Required evidence is absent from selection.",
        ),
        MutationTaxonomyEntry(
            mutation_id="scope_mismatch",
            family=MutationFamily.SCOPE,
            universal_error=True,
            description="Evidence is bound to the wrong subject or population scope.",
        ),
        MutationTaxonomyEntry(
            mutation_id="time_shift",
            family=MutationFamily.TEMPORAL,
            universal_error=True,
            description="Evidence comes from an incorrect validity or observation period.",
        ),
        MutationTaxonomyEntry(
            mutation_id="definition_mismatch",
            family=MutationFamily.DEFINITION,
            universal_error=True,
            description="A predicate or measurement definition is incompatible.",
        ),
        MutationTaxonomyEntry(
            mutation_id="wrong_derivation",
            family=MutationFamily.DERIVATION,
            universal_error=True,
            description="An operation or final result is computed incorrectly.",
        ),
        MutationTaxonomyEntry(
            mutation_id="citation_mismatch",
            family=MutationFamily.CITATION,
            universal_error=True,
            description="A citation does not bind to the selected evidence and source span.",
        ),
        MutationTaxonomyEntry(
            mutation_id="unsupported_claim",
            family=MutationFamily.CLAIM,
            universal_error=True,
            description="A claim extends beyond its supporting evidence.",
        ),
        MutationTaxonomyEntry(
            mutation_id="public_oracle_leakage",
            family=MutationFamily.TRAJECTORY,
            universal_error=True,
            description="A candidate uses hidden oracle-only information.",
        ),
        MutationTaxonomyEntry(
            mutation_id="tool_or_step_contract",
            family=MutationFamily.TRAJECTORY,
            universal_error=True,
            description="A tool, step, or program-node contract is violated.",
        ),
        MutationTaxonomyEntry(
            mutation_id="multi_error",
            family=MutationFamily.COMPOSITE,
            universal_error=True,
            description="Multiple independent contract violations occur together.",
        ),
    )
}


def taxonomy_entry(mutation_id: str) -> MutationTaxonomyEntry:
    try:
        return GENERIC_MUTATION_TAXONOMY[mutation_id]
    except KeyError as exc:
        raise ValueError(f"unknown generic mutation taxonomy entry: {mutation_id}") from exc


def mutation_taxonomy_manifest_hash() -> str:
    manifest = tuple(
        item.model_dump(mode="json")
        for item in sorted(GENERIC_MUTATION_TAXONOMY.values(), key=lambda value: value.mutation_id)
    )
    return canonical_hash(manifest, prefix="mutation_taxonomy_manifest:")
