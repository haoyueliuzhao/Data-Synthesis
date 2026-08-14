from __future__ import annotations

import json
from pathlib import Path

import pytest

from trusted_synthesis.core.evidence.schema import EvidenceItem
from trusted_synthesis.experiments.vtdo_experiment.phase1_agent_evidence_union import (
    FINANCE_AGENT_EVIDENCE_UNION_ITEM_VERSION,
    FinanceAgentEvidenceUnionItem,
    finance_agent_evidence_union_item_id,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_sensitive_frontier import (  # noqa: E501
    _load_evidence_pool,
)


def _union_item(
    evidence: EvidenceItem,
    *,
    union_id: str = "finance_agent_evidence_union:test",
    source_artifact_ids: tuple[str, ...] = ("artifact:test",),
) -> FinanceAgentEvidenceUnionItem:
    values = {
        "union_id": union_id,
        "evidence": evidence,
        "source_artifact_ids": source_artifact_ids,
        "schema_version": FINANCE_AGENT_EVIDENCE_UNION_ITEM_VERSION,
    }
    provisional = FinanceAgentEvidenceUnionItem.model_construct(union_item_id="pending", **values)
    return FinanceAgentEvidenceUnionItem(
        union_item_id=finance_agent_evidence_union_item_id(provisional), **values
    )


def test_evidence_union_loader_preserves_unique_lineage(
    tmp_path: Path,
    finance_evidence: EvidenceItem,
) -> None:
    items: list[FinanceAgentEvidenceUnionItem] = []
    for index in range(3):
        evidence = finance_evidence.model_copy(
            update={
                "evidence_id": f"evidence:test:{index}",
                "assertion_id": f"assertion:test:{index}",
                "evidence_version_id": f"version:test:{index}",
                "source": finance_evidence.source.model_copy(
                    update={"source_id": f"source:test:{index}"}
                ),
            }
        )
        items.append(_union_item(evidence, source_artifact_ids=(f"artifact:test:{index}",)))
    path = tmp_path / "evidence_union.jsonl"
    path.write_text(
        "".join(json.dumps(item.model_dump(mode="json"), sort_keys=True) + "\n" for item in items),
        encoding="utf-8",
    )

    pool = _load_evidence_pool(path)

    assert set(pool.public) == {f"evidence:test:{index}" for index in range(3)}
    assert pool.source_artifact_count == 3
    assert pool.source_artifact_ids == {f"artifact:test:{index}" for index in range(3)}


def test_evidence_union_loader_rejects_duplicate_evidence_identity(
    tmp_path: Path,
    finance_evidence: EvidenceItem,
) -> None:
    item = _union_item(finance_evidence)
    path = tmp_path / "duplicated_evidence_union.jsonl"
    line = json.dumps(item.model_dump(mode="json"), sort_keys=True) + "\n"
    path.write_text(line + line, encoding="utf-8")

    with pytest.raises(ValueError, match="repeats an Evidence ID"):
        _load_evidence_pool(path)


def test_evidence_union_item_requires_sorted_unique_source_lineage(
    finance_evidence: EvidenceItem,
) -> None:
    with pytest.raises(ValueError, match="not unique and sorted"):
        _union_item(
            finance_evidence,
            source_artifact_ids=("artifact:z", "artifact:a", "artifact:a"),
        )
