from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from enum import Enum

import pytest
from pydantic import BaseModel

from trusted_synthesis.canonical_json import strict_canonical_hash, to_canonical_json_data


class Mode(str, Enum):
    READY = "ready"


class Child(BaseModel):
    amount: Decimal
    mode: Mode


def test_strict_canonical_json_recurses_into_nested_pydantic_models() -> None:
    timestamp = datetime(2026, 8, 26, 12, 30, tzinfo=UTC)
    nested = {"child": Child(amount=Decimal("1.2300"), mode=Mode.READY), "at": timestamp}
    plain = {
        "child": {"amount": "1.23", "mode": "ready"},
        "at": "2026-08-26T12:30:00.000000+00:00",
    }

    assert to_canonical_json_data(nested) == plain
    assert strict_canonical_hash(nested) == strict_canonical_hash(plain)


@pytest.mark.parametrize(
    "value",
    [object(), {1: "non-string-key"}, float("nan"), Decimal("Infinity")],
)
def test_strict_canonical_json_fails_closed_for_unregistered_values(value: object) -> None:
    with pytest.raises((TypeError, ValueError)):
        strict_canonical_hash(value)
