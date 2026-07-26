from __future__ import annotations

from enum import Enum


class EpistemicStatus(str, Enum):
    OBSERVED = "observed"
    ASSERTED = "asserted"
    DERIVED = "derived"
    DISPUTED = "disputed"
    SUPERSEDED = "superseded"
    REJECTED = "rejected"
