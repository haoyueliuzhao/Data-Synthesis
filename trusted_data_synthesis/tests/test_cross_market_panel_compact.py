"""Synthetic fixed-panel compaction controls; no model, API or real registration."""

import copy
import json
from pathlib import Path

import cross_market_panel_compact_20260927 as m
import fixed_kernel_cross_market_evaluation_20260926 as evaluation
import pytest
from test_cross_market_panel_revision_05 import module, synthetic_panel  # noqa: F401


def selected_inputs():
    tasks, documents, issuer, reviews = synthetic_panel()
    loaded = ({"candidates": tasks}, documents, issuer, None, reviews)
    plan = dict(
        financial_protocol_id="financial:synthetic",
        public_metric_universe=list(m.core.financial.METRICS),
    )
    return plan, loaded, m.selected_original(plan, loaded)[0]


def test_same_full_panel_executes_420_controls_and_roundtrips_all_runtime_sources(
    module, monkeypatch, tmp_path
):
    plan, loaded, original = selected_inputs()
    candidates, documents, issuer, _, reviews = loaded
    namespace = m.compiler_namespace()
    tokenized = []

    def count_tokens(messages):
        public = json.loads(messages[0]["content"])
        tokenized.append(public["period_contract"]["task_id"])
        return 18432  # Exact unchanged admission boundary, not a real tokenizer estimate.

    report, prepared = namespace["compile_panel"](
        candidates["candidates"],
        documents,
        issuer,
        reviews,
        plan["financial_protocol_id"],
        plan["public_metric_universe"],
        count_tokens,
    )
    expected_ids = [row["spec"]["task_id"] for row in original]
    assert report["passed"] is True
    assert report["selected_task_ids"] == tokenized == expected_ids
    assert report["selected_group_counts"] == m.core.QUOTAS
    assert report["scripted_control_executions"] == 420
    assert report["input_tokenizations"] == len(prepared) == 180
    assert all(c["expected"] is c["observed"] for row in report["checks"] for c in row["controls"])
    unchanged_tool_fields = {
        "source_id",
        "native_pointer",
        "source_raw_sha256",
        "source_url",
        "concept",
        "source_unit",
        "record",
        "actual_period",
        "exact_value",
        "unit",
        "conversion",
    }
    for old, item in zip(original, prepared, strict=True):
        projected = json.loads(item["public_messages"][0]["content"])
        expected, audit = m.compact.compact(old["public"])
        assert projected == expected == item["bundle"]["public"]
        assert m.compact.restore(projected, audit) == old["public"]
        assert item["candidate_task_id"] == old["task"]["task_id"]
        assert item["spec"] == old["spec"]
        assert set(item["native_bindings"]) == {fact["fact_id"] for fact in old["visible"]}
        before = m.core.runtime.SourceViewSources(old["public"])
        after = m.core.runtime.SourceViewSources(projected)
        for index, (source, alias) in enumerate(
            zip(old["public"]["sources"], projected["sources"], strict=True), 1
        ):
            assert alias["source_id"] == f"S{index:04d}"
            assert audit["sources"][index - 1]["original_source_id"] == source["source_id"]
            unit = "million " + source["unit"]
            old_read = before.read_source(dict(source_id=source["source_id"], unit=unit))
            new_read = after.read_source(dict(source_id=alias["source_id"], unit=unit))
            assert {k: old_read[k] for k in unchanged_tool_fields} == {
                k: new_read[k] for k in unchanged_tool_fields
            }
    monkeypatch.setattr(m.base, "RAW", tmp_path)
    published = namespace["publish_panel"](
        tmp_path,
        dict(
            id="synthetic-compact-protocol",
            runtime_binding=m.core.runtime.binding(),
            issuer_admission={"id": issuer["id"]},
        ),
        report,
        prepared,
    )
    manifest = evaluation.prior.public_manifest({"panel": published})
    private = evaluation.prior._private_assets(
        {"panel": published}, manifest, {"id": "synthetic-seal-only"}
    )
    assert [row["task_id"] for row in manifest["tasks"]] == expected_ids
    assert len(private["bundles"]) == 180
    assert all(private["bundles"][row["spec"]["task_id"]] == row["bundle"] for row in prepared)


def test_one_overlong_selected_view_rejects_full_panel_without_replacement(module):
    plan, loaded, original = selected_inputs()
    candidates, documents, issuer, _, reviews = loaded
    namespace = m.compiler_namespace()
    namespace["scripted_controls"] = lambda *args: [dict(expected=True, observed=True)]
    lengths = iter([18433] + [100] * 179)
    report, prepared = namespace["compile_panel"](
        candidates["candidates"],
        documents,
        issuer,
        reviews,
        plan["financial_protocol_id"],
        plan["public_metric_universe"],
        lambda messages: next(lengths),
    )
    assert report["passed"] is False and prepared == []
    assert report["status"] == "BLOCKED_SELECTED_INPUT_OR_SCRIPTED_CONTROL"
    assert report["no_replacement_after_selected_input_failure"] is True
    assert report["selected_task_ids"] == [row["spec"]["task_id"] for row in original]
    assert sum(not row["passed"] for row in report["checks"]) == 1
    assert report["input_tokenizations"] == 180


@pytest.fixture
def registration(module, monkeypatch, tmp_path):
    scope, loaded, selected = selected_inputs()
    monkeypatch.setattr(m.base, "RAW", tmp_path)
    monkeypatch.setattr(m.previous, "RAW", tmp_path / "panel_text_table_02")
    monkeypatch.setattr(m, "RAW", tmp_path / "panel_compact_03")
    parent = m.base.record(
        m.previous.PROTOCOL,
        **scope,
        sources={},
        runtime_binding=m.core.runtime.binding(),
        source_text_table_review_bundle_id="synthetic-review-bundle",
        source_text_table_reviews={"path": "synthetic-review-path"},
        source_text_table_review_scope=module.REVIEW_SCOPE,
        full_original_PDF_visual_exhaustion_claimed=False,
    )
    failed = m.base.record(
        m.previous.COMPLETION,
        protocol_id=parent["id"],
        passed=False,
        status="BLOCKED_SELECTED_INPUT_OR_SCRIPTED_CONTROL",
        selected_task_ids=[row["spec"]["task_id"] for row in selected],
        scripted_control_executions=420,
        checks=[
            dict(
                initial_prompt_tokens=18433 if index == 0 else 100,
                controls=[dict(expected=True, observed=True)] * (3 if index < 60 else 2),
            )
            for index in range(180)
        ],
    )
    m.base.write(m.previous.RAW / "protocol.json", parent)
    m.base.write(m.previous.RAW / "summary.json", failed)
    monkeypatch.setattr(m.previous, "protocol", lambda root: parent)
    monkeypatch.setattr(m, "inputs", lambda plan: loaded)
    root = Path(m.__file__).resolve().parents[2]
    git_reads = []

    def synthetic_committed_sources(command, **kwargs):
        git_reads.append(command)
        if command == ["git", "rev-parse", "HEAD"]:
            return "synthetic-commit\n"
        assert command[:2] == ["git", "show"]
        return (root / command[2].split(":", 1)[1]).read_bytes()

    monkeypatch.setattr(m.subprocess, "check_output", synthetic_committed_sources)
    return root, parent, failed, selected, git_reads


def test_synthetic_registration_preserves_failure_review_scope_and_fixed_budget(registration):
    root, parent, _, selected, git_reads = registration
    frozen_parent = (m.previous.RAW / "protocol.json").read_bytes()
    frozen_failure = (m.previous.RAW / "summary.json").read_bytes()
    plan = m.register(root)
    assert m.protocol(root) == plan == m.register(root)
    assert len(git_reads) == 3
    assert plan["selected_original_binding"] == m.selection_binding(selected)
    for key in (
        "runtime_binding",
        "source_text_table_review_bundle_id",
        "source_text_table_reviews",
        "source_text_table_review_scope",
        "full_original_PDF_visual_exhaustion_claimed",
    ):
        assert plan[key] == parent[key]
    assert plan["maximum_initial_prompt_tokens"] == 18432
    assert plan["maximum_compiler_passes"] == 1
    assert plan["maximum_scripted_control_executions"] == 420
    assert plan["maximum_initial_prompt_tokenizations"] == 180
    for key in (
        "actual_model_generation_calls",
        "actual_model_scoring_cases",
        "network_requests",
        "GPU_processes",
        "new_training_updates",
        "new_source_semantic_API_calls",
    ):
        assert plan[key] == 0
    assert (m.previous.RAW / "protocol.json").read_bytes() == frozen_parent
    assert (m.previous.RAW / "summary.json").read_bytes() == frozen_failure
    assert not (m.base.RAW / "evaluation_01").exists()
    body = {key: value for key, value in plan.items() if key not in {"id", "schema_version"}}
    changed = m.base.record(m.PROTOCOL, **(body | {"maximum_initial_prompt_tokens": 18433}))
    m.base.write(m.RAW / "protocol.json", changed, immutable=False)
    with pytest.raises(ValueError, match="same_parent_failure_runtime_and_limit"):
        m.protocol(root)


@pytest.mark.parametrize("blocked", ["control_failure", "existing_evaluation"])
def test_registration_rejects_non_length_failure_or_started_evaluation(registration, blocked):
    root, _, failed, _, git_reads = registration
    if blocked == "control_failure":
        body = copy.deepcopy({k: v for k, v in failed.items() if k not in {"id", "schema_version"}})
        body["checks"][0]["controls"][0]["observed"] = False
        m.base.write(
            m.previous.RAW / "summary.json",
            m.base.record(m.previous.COMPLETION, **body),
            immutable=False,
        )
        reason = "preserved_length_only_failed_parent"
    else:
        m.base.write(m.base.RAW / "evaluation_01/protocol.json", {"synthetic": True})
        reason = "no_evaluation_started_before_representation_revision"
    with pytest.raises(ValueError, match=reason):
        m.register(root)
    assert git_reads == []
    assert not (m.RAW / "protocol.json").exists()


# ruff: noqa: F811 -- imported pytest fixture intentionally injected by name
