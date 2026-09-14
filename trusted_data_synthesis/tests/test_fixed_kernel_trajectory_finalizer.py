"""Focused successor publication controls; no real archive, Git, GPU or API."""

import importlib.util
from pathlib import Path

import pytest
from test_fixed_kernel_fast_publication import StubGit, closed as parent_closed, manifest

SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "scripts/finalize_fixed_kernel_trajectory_execution_20260914.py"
)
SPEC = importlib.util.spec_from_file_location("trajectory_finalizer_test", SCRIPT)
helper = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(helper)


def test_producer_manifest_can_exceed_small_index_page_limit(closed):
    root, p = closed[:2]
    record = p.record(
        "evaluation_manifest", report_id="synthetic:report", padding="x" * (helper.SMALL_LIMIT + 1)
    )
    relative = p.OUTPUT + "/large_producer_inventory.json"
    p.write_once(root / relative, record)
    assert helper.read_producer_manifest(root, relative, p) == record


@pytest.fixture
def closed(parent_closed):
    root, p, old_report, old_manifest = parent_closed
    original_output = p.OUTPUT
    p.MATERIALS_ROOT = p.PARENT_ROOT
    p.PARENT_ROOT = root.parent / "paused_fast"
    p.PARENT_ROOT.mkdir()
    p.OUTPUT = "raw/trajectory"
    p.EXPECTED_MATERIAL_MANIFEST = old_manifest["id"]
    for name in (
        "generation_report.json",
        "freeze.json",
        "authorization.json",
        "completion_freeze.json",
    ):
        p.write_once(p.MATERIALS_ROOT / p.MATERIALS / name, p.read_json(root / p.MATERIALS / name))
    for name in helper.SOURCES:
        path = root / name
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"# Synthetic committed successor helper, not executed.\n")
    old_authority = p.read_json(
        root / original_output / "preparation/fast_execution_authority.json"
    )
    generation = p.read_json(p.MATERIALS_ROOT / p.MATERIALS / "generation_report.json")
    gate = p.read_json(p.MATERIALS_ROOT / p.MATERIALS / "material_gate.json")

    def budget(rows, sequence):
        per = {"packages": 2, "target_tokens": 4, "rows": rows, "sequence_tokens": sequence}
        return {
            key + suffix: count * factor
            for key, count in per.items()
            for suffix, factor in (("_per_epoch", 1), ("_all_epochs", 10))
        }

    actual = {pool: budget(1, 4) for pool in ("A", "B")}
    source = {pool: budget(2, 6) for pool in ("A", "B")}
    verification = p.record(
        "material_input_verification", kernel_id=p.EXPECTED_KERNEL, pool_budgets=source
    )
    old_config = p.record(
        "training_configuration", execution="old_response_rows", lora_dropout=0.05
    )
    config = p.record(
        "training_configuration", execution="trajectory_prefix_union_v1", lora_dropout=0.05
    )
    parent = p.record(
        "execution_freeze",
        kernel_id=p.EXPECTED_KERNEL,
        training_configuration=old_config,
        material_verification=verification,
        material_input_receipt={"path": "old/receipt.json"},
    )
    parent_path = "old/preparation/execution_freeze.json"
    p.write_once(p.PARENT_ROOT / parent_path, parent)
    cache = p.record(
        "trajectory_material_cache",
        kernel_id=p.EXPECTED_KERNEL,
        material_verification_id=verification["id"],
        parent_execution_freeze_id=parent["id"],
        pool_budgets=actual,
        source_material_budgets=source,
        dropout_random_trajectory_changed=True,
        stochastic_or_bitwise_training_equivalence_claimed=False,
    )
    cache_root = p.OUTPUT + "/preparation/trajectory_cache"
    p.write_once(root / cache_root / "manifest.json", cache)
    cached = {
        "cache_root": cache_root,
        "manifest": helper.descriptor(root, cache_root + "/manifest.json"),
        "manifest_id": cache["id"],
    }
    frozen = p.record(
        "execution_freeze",
        kernel_id=p.EXPECTED_KERNEL,
        study_freeze_id=old_report["study_freeze_id"],
        output_directory=p.OUTPUT,
        input_root=str(p.PARENT_ROOT),
        original_material_gate_id=gate["id"],
        training_configuration=config,
        parent_training_configuration_id=old_config["id"],
        parent_execution_freeze=helper.descriptor(p.PARENT_ROOT, parent_path),
        parent_execution_freeze_id=parent["id"],
        material_verification=verification,
        material_input_receipt=parent["material_input_receipt"],
        trajectory_cache=cached,
        trajectory_pool_budgets=actual,
        source_material_budgets=source,
        dropout_correlation_changed=True,
        bitwise_equivalence_claimed=False,
        parent_partial_Students_resumed=False,
    )
    authority = p.record(
        "trajectory_execution_authority",
        execution_freeze_id=frozen["id"],
        parent_execution_freeze_id=parent["id"],
        original_material_gate_id=gate["id"],
        original_kernel_id=p.EXPECTED_KERNEL,
        original_generation_report_id=generation["id"],
        completion_freeze_id=old_authority["completion_freeze_id"],
        original_registry_freeze_id=old_report["study_freeze_id"],
        parent_source_root=str(p.PARENT_ROOT),
        original_material_source_root=str(p.MATERIALS_ROOT),
        training_configuration_id=config["id"],
        parent_training_configuration_id=old_config["id"],
        source_material_verification_id=verification["id"],
        trajectory_cache_id=cache["id"],
        trajectory_cache=cached,
        source_material_validation_reused=True,
        original_kernel_ID_recomputed=False,
        dropout_correlation_changed=True,
        bitwise_equivalence_claimed=False,
        fresh_Students_from_original_base_and_seed=True,
        parent_partial_Students_or_optimizers_resumed=False,
        parent_incomplete_run_claimed_complete=False,
        original_parent_reports_relabelled=False,
    )
    decision = p.read_json(root / original_output / "decision.json")
    fields = {
        key: value for key, value in old_report.items() if key not in {"id", "schema_version"}
    }
    fields["training_configuration_id"] = config["id"]
    report = p.record("execution_report", **fields)
    closed = p.record(
        "evaluation_manifest", report_id=report["id"], phase="fixed_kernel_value_execution"
    )
    for name, value in (
        ("report.json", report),
        ("manifest.json", closed),
        ("decision.json", decision),
        ("preparation/execution_freeze.json", frozen),
        ("preparation/trajectory_execution_authority.json", authority),
    ):
        p.write_once(root / p.OUTPUT / name, value)
    for arm in p.ARMS:
        for seed in p.SEEDS:
            trained = p.record(
                "training_report",
                actual_complete=True,
                status="COMPLETE_FINAL_CHECKPOINT",
                pool="A",
                arm=arm,
                seed=seed,
                kernel_id=p.EXPECTED_KERNEL,
                training_configuration_id=config["id"],
                trajectory_cache_id=cache["id"],
                material_verification_id=verification["id"],
                actual_budget=actual["A"],
                source_material_budget=source["A"],
                optimizer_updates=400,
                epochs_completed=10,
                final_adapter_restored_identity_verified=True,
            )
            p.write_once(root / p.OUTPUT / "training" / f"A_{arm}_{seed}" / "report.json", trained)
    return root, p, report, old_manifest


def sealer(root, p, report, observed):
    def seal(code_root, data_root, stage, **kwargs):
        observed.append((stage, kwargs))
        assert code_root == root and data_root == p.DATA_ROOT and stage == "results"
        assert kwargs["source_output"] == "raw"
        assert kwargs["allowlist"] == ["trajectory"]
        assert kwargs["report_path"] == "trajectory/report.json"
        assert len(kwargs["approved_adapter_paths"]) == 9
        assert all(
            name.startswith("trajectory/training/A_") for name in kwargs["approved_adapter_paths"]
        )
        return manifest(
            root,
            p,
            "raw_publication/results",
            stage="results",
            source_root="raw",
            report_id=report["id"],
        )

    return seal


def test_successor_only_result_seal_existing_material_copy_exact_push_and_honest_dropout_lineage(
    closed,
):
    root, p, report, old_manifest = closed
    runner, observed = StubGit(), []
    result = helper.finalize(root, p, sealer=sealer(root, p, report, observed), runner=runner)
    assert result["status"] == "COMMITTED_AND_PUSHED"
    assert len(observed) == 1
    assert (
        p.read_json(root / (p.MATERIALS + "_publication/materials/publication_manifest.json"))
        == old_manifest
    )
    terminal = p.read_json(root / (p.OUTPUT + "_publication_workflow/terminal.json"))
    assert terminal["dropout_correlation_changed"] is True
    assert terminal["bitwise_equivalence_claimed"] is False
    assert terminal["parent_partial_states_resumed"] is False
    assert terminal["original_kernel_ID_recomputed"] is False
    assert terminal["original_material_reseals"] == 0
    assert terminal["old_workflow_terminal_fabricated"] is False
    assert len(terminal["actual_training_report_ids"]) == 9
    assert not (p.PARENT_ROOT / "old/report.json").exists()
    assert not (p.MATERIALS_ROOT / (p.MATERIALS + "_workflow/terminal.json")).exists()
    assert [args for args, _ in runner.calls if args[0] == "add"] == [
        ("add", "--sparse", "--force", "--pathspec-from-file=-", "--pathspec-file-nul")
    ]
    assert [args for args, _ in runner.calls if args[0] == "push"] == [
        ("push", helper.REMOTE, helper.REFSPEC)
    ]
    assert not any(
        b".env" in name or b"runtime" in name or b"giant_original" in name for name in runner.staged
    )
    summary = (root / helper.SUMMARY).read_text()
    assert "不是逐位等价重放" in summary and "重新初始化 LoRA/AdamW" in summary
    assert "independent_positive_effect_confirmed`：false" in summary


def test_missing_new_result_closure_never_uses_old_result_or_runs_sealer_or_git_writes(closed):
    root, p, report, _ = closed
    (root / p.OUTPUT / "manifest.json").rename(root / p.OUTPUT / "retained_unclosed_manifest.json")
    runner, observed = StubGit(), []
    with pytest.raises(ValueError, match="not_ready"):
        helper.finalize(root, p, sealer=sealer(root, p, report, observed), runner=runner)
    assert not observed
    assert not any(args[0] in {"add", "commit", "push"} for args, _ in runner.calls)


def test_bitwise_equivalence_claim_in_successor_authority_is_rejected_before_publication(closed):
    root, p, report, _ = closed
    path = root / p.OUTPUT / "preparation/trajectory_execution_authority.json"
    value = p.read_json(path)
    fields = {key: item for key, item in value.items() if key not in {"id", "schema_version"}}
    fields["bitwise_equivalence_claimed"] = True
    path.write_bytes(p.encode(p.record("trajectory_execution_authority", **fields)))
    runner, observed = StubGit(), []
    with pytest.raises(ValueError, match="not_bitwise_replay"):
        helper.finalize(root, p, sealer=sealer(root, p, report, observed), runner=runner)
    assert not observed
    assert not any(args[0] in {"add", "commit", "push"} for args, _ in runner.calls)
