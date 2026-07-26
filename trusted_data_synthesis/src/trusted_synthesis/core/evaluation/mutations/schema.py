from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict


class MutationFamily(str, Enum):
    EVIDENCE = "evidence"
    TEMPORAL = "temporal"
    SCOPE = "scope"
    DEFINITION = "definition"
    PROVENANCE = "provenance"
    TRAJECTORY = "trajectory"
    CITATION = "citation"
    DERIVATION = "derivation"
    CLAIM = "claim"
    COMPOSITE = "composite"


class MutationTaxonomyEntry(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    mutation_id: str
    family: MutationFamily
    universal_error: bool
    description: str
