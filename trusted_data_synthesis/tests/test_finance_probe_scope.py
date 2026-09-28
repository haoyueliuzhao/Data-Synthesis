"""Small synthetic scope controls; no real outcomes, API, GPU or rule changes."""

import copy
import hashlib
import json

import pytest
from test_finance_research_qualification import source_fixture

from trusted_synthesis.finance_research import probe_scope as scope_module
from trusted_synthesis.finance_research.contracts import digest
from trusted_synthesis.finance_research.planning import build_role_plan
from trusted_synthesis.finance_research.probe_scope import (
    AUTHOR_SOURCE_ASSUMPTION,
    SCHEMA,
    SLOT_COUNTS,
    build_conditional_scope,
    validate_conditional_scope,
)
from trusted_synthesis.finance_research.qualification import qualification_rules
from trusted_synthesis.finance_research.state_mapping import mapper_rules


def seal(body):
    value = {key: item for key, item in body.items() if key != "scope_id"}
    return {**value, "scope_id": "finqa_conditional_scope:" + digest(value)}


def synthetic_scope():
    original = [f"fixture:{index}" for index in range(1000)]
    chosen = {original[7], original[301]}
    return seal(
        dict(
            schema=SCHEMA,
            dataset="finqa",
            original_denominator=1000,
            original_task_ids=original,
            task_ids=[task for task in original if task in chosen],
            scoped_task_count=2,
            coverage_rows=[
                dict(
                    task_id=task,
                    included=task in chosen,
                    status="author_anchored_supported" if task in chosen else "unknown",
                    reason="synthetic scope-only control",
                    evidence_sha256=digest(task),
                )
                for task in original
            ],
            qualification_rule_id=qualification_rules()["id"],
            mapper_rule_id=mapper_rules()["id"],
            snapshot_id="synthetic-snapshot",
            source_manifest_sha256="a" * 64,
            private_sha256="b" * 64,
            slot_counts=copy.deepcopy(SLOT_COUNTS),
            selection_uses_probe_outcomes=False,
            static_support_is_material_qualification=False,
            author_source_assumption=AUTHOR_SOURCE_ASSUMPTION,
        )
    )


def checked(scope):
    return validate_conditional_scope(scope, qualification_rules()["id"], mapper_rules()["id"])


def test_validation_is_pure_preserves_exclusions_and_does_not_alias_scope(tmp_path, monkeypatch):
    scope = synthetic_scope()
    monkeypatch.setattr(
        scope_module, "load_public_snapshot", lambda *_: pytest.fail("no source read")
    )
    result = checked(scope)
    assert len(result["coverage_rows"]) == result["original_denominator"] == 1000
    assert result["task_ids"] == ["fixture:7", "fixture:301"]
    result["task_ids"].reverse()
    assert scope["task_ids"] == ["fixture:7", "fixture:301"]


@pytest.mark.parametrize(
    "mutation",
    [
        "reordered_selected",
        "missing_original",
        "missing_coverage",
        "duplicate_original",
        "included_unknown",
        "uses_outcomes",
        "admitted",
        "wrong_slots",
        "wrong_rule",
        "bad_evidence_hash",
        "wrong_count",
    ],
)
def test_rehashed_inconsistent_scope_still_rejected(mutation):
    scope = synthetic_scope()
    if mutation == "reordered_selected":
        scope["task_ids"].reverse()
    elif mutation == "missing_original":
        scope["original_task_ids"].pop()
    elif mutation == "missing_coverage":
        scope["coverage_rows"].pop()
    elif mutation == "duplicate_original":
        scope["original_task_ids"][-1] = scope["original_task_ids"][0]
    elif mutation == "included_unknown":
        scope["coverage_rows"][0]["included"] = True
    elif mutation == "uses_outcomes":
        scope["selection_uses_probe_outcomes"] = True
    elif mutation == "admitted":
        scope["static_support_is_material_qualification"] = True
    elif mutation == "wrong_slots":
        scope["slot_counts"] = {"total": 8, "train": 7, "sealed": 1}
    elif mutation == "wrong_rule":
        scope["qualification_rule_id"] = "foreign"
    elif mutation == "bad_evidence_hash":
        scope["coverage_rows"][0]["evidence_sha256"] = "not-a-hash"
    else:
        scope["scoped_task_count"] = 3
    with pytest.raises(ValueError):
        checked(seal(scope))


def test_original_scope_hash_detects_byte_content_change():
    scope = synthetic_scope()
    scope["coverage_rows"][0]["reason"] = "changed after freeze"
    with pytest.raises(ValueError, match="identity"):
        checked(scope)


def source_snapshot(tmp_path):
    bundle = source_fixture()
    tasks, lineages, refs = [], [], []
    for index in range(1002):
        task_id, question = f"SYNTHETIC/2021/fixture-{index}", f"Unique fixture question {index}?"
        tasks.append(bundle.public.model_copy(update={"task_id": task_id, "question": question}))
        lineages.append(
            bundle.lineage.model_copy(
                update={
                    "original_id": task_id,
                    "original_split": "train"
                    if index < 1000
                    else ("dev" if index == 1000 else "test"),
                    "question_fingerprint": digest(question),
                }
            )
        )
        refs.append(bundle.reference.model_copy(update={"task_id": task_id}))
    members = {
        "public.jsonl": b"\n".join(task.model_dump_json().encode() for task in tasks) + b"\n",
        "lineage.jsonl": b"\n".join(row.model_dump_json().encode() for row in lineages) + b"\n",
        # Opaque hash-only held-out rows deliberately cannot become PrivateReference.
        # This fixture proves the builder never interprets non-SFT author references.
        "private.references.jsonl": b"\n".join(
            row.model_dump_json().encode() for row in refs[:1000]
        )
        + b'\n"opaque dev reference: do not parse"\n"opaque test reference: do not parse"\n',
    }
    manifest = dict(
        schema="synthetic-fixture",
        task_order=[f"finqa/{t.task_id}" for t in tasks],
        files={
            name: dict(sha256=hashlib.sha256(raw).hexdigest(), bytes=len(raw))
            for name, raw in members.items()
        },
    )
    manifest["id"] = digest(manifest)
    for name, raw in members.items():
        (tmp_path / name).write_bytes(raw)
    (tmp_path / "manifest.json").write_text(json.dumps(manifest, indent=2))
    roles = build_role_plan(tasks, lineages, sft_tasks=1000, feedback_tasks=0, calibration_tasks=0)
    previous = dict(snapshot=str(tmp_path), snapshot_id=manifest["id"], role_plan=roles)
    previous["id"] = digest(previous)
    return previous


def test_builder_binds_original_source_bytes_and_only_parses_original_SFT_rows(
    tmp_path, monkeypatch
):
    previous = source_snapshot(tmp_path)
    seen = []

    def support(bundle):
        seen.append(bundle.public.task_id)
        accepted = bundle.public.task_id.rsplit("-", 1)[1] in {"7", "301"}
        return dict(
            task_id=bundle.public.task_id,
            status="author_anchored_supported" if accepted else "unknown",
            reason="synthetic support fixture",
            qualification_rule_id=qualification_rules()["id"],
            material_admission=False,
            no_probe_outcome_examined=True,
            private_reference_check_pending=False,
        )

    monkeypatch.setattr(scope_module, "task_support_check", support)
    result = build_conditional_scope(previous)
    assert len(seen) == 1000 and seen == result["original_task_ids"]
    assert result["task_ids"] == [seen[7], seen[301]]
    assert (
        result["source_manifest_sha256"]
        == hashlib.sha256((tmp_path / "manifest.json").read_bytes()).hexdigest()
    )
    assert result["source_manifest_sha256"] != result["manifest_content_digest"]
    assert result["private_reference_roles_inspected"] == ["sft"]
    assert result["private_reference_objects_inspected"] == 1000
    assert "evidence" not in result["coverage_rows"][0]
    (tmp_path / "private.references.jsonl").write_bytes(b"corrupted member")
    with pytest.raises(ValueError, match="private-reference member bytes"):
        build_conditional_scope(previous)
