"""Tiny opaque archive controls: no actual Git, training, API, scan or seal."""

import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest

from trusted_synthesis.experiments.finance_qa_vnext_fixed_kernel_value import protocol as protocol

SCRIPT = (
    Path(__file__).resolve().parents[1] / "scripts/finalize_fixed_kernel_fast_execution_20260914.py"
)
SPEC = importlib.util.spec_from_file_location("fast_publication_test", SCRIPT)
helper = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(helper)


def manifest(root, p, relative, *, stage, source_root, report_id):
    output = root / relative
    output.mkdir(parents=True)
    (output / "raw-00000.tar.gz").write_bytes(b"opaque synthetic archive, never decompressed")
    p.write_once(
        output / "original_member_index-00000.json",
        p.record("original_member_index", page=0, rows=[]),
    )
    value = p.record(
        "publication_manifest",
        stage=stage,
        source_root=source_root,
        closure={"report_id": report_id},
        archives=[helper.descriptor(output, "raw-00000.tar.gz")],
        member_index_pages=[helper.descriptor(output, "original_member_index-00000.json")],
        physical_member_index_pages=[],
        duplicate_content_index_pages=[],
        actual_credential_scanned=True,
        credential_hits=0,
        wallet_runtime_credentials_or_base_weights_published=False,
        all_original_member_SHA_and_roundtrips_verified=True,
        original_file_count=1,
        original_bytes=123,
    )
    p.write_once(output / "publication_manifest.json", value)
    return value


@pytest.fixture
def closed(tmp_path):
    root, parent, data = (tmp_path / name for name in ("fast", "parent", "data"))
    root.mkdir()
    parent.mkdir()
    data.mkdir()
    p = SimpleNamespace(
        OUTPUT="raw/fast",
        MATERIALS="raw/materials",
        RUNTIME="runtime",
        BRANCH="synthetic_fast",
        PARENT_ROOT=parent,
        DATA_ROOT=data,
        EXPECTED_KERNEL="original_exact_kernel",
        ARMS=("alpha0", "plus", "minus"),
        SEEDS=(11, 29, 47),
        **{
            name: getattr(protocol, name)
            for name in ("record", "checked", "read_json", "write_once", "encode", "now")
        },
    )
    for name in (helper.SCRIPT, helper.DEPENDENCY):
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"# Synthetic committed operator source, not executed.\n")
    original = p.record("study_freeze", retained=True)
    authorization = p.record(
        "kernel_completion_authorization",
        amended_combined_token_cap=350000000,
        amendment_after_parent_budget_stop=True,
        unamended_preregistration_claimed=False,
    )
    completion = p.record("kernel_completion_freeze", authorization_id=authorization["id"])
    generation = p.record(
        "material_generation_report",
        registered_sessions=10240,
        finished_sessions=10240,
        generation_closed=True,
        no_inflight_requests=True,
        new_HTTP_request_count=1401,
        completion_conservative_debit=6323646,
    )
    gate = p.record(
        "material_gate",
        kernel_id=p.EXPECTED_KERNEL,
        training_gate="PASS",
        material_gate="PASS",
        dose_gate="PASS",
        generation_report_id=generation["id"],
    )
    p.EXPECTED_GATE = gate["id"]
    receipt_path = p.OUTPUT + "/preparation/material_input_receipt.json"
    p.write_once(root / receipt_path, p.record("verified_material_receipt", synthetic=True))
    config = p.record("training_configuration", unchanged=True)
    frozen = p.record(
        "execution_freeze",
        kernel_id=p.EXPECTED_KERNEL,
        study_freeze_id=original["id"],
        output_directory=p.OUTPUT,
        training_configuration=config,
        material_input_receipt=helper.descriptor(root, receipt_path),
    )
    authority = p.record(
        "fast_execution_authority",
        execution_freeze_id=frozen["id"],
        original_material_gate_id=gate["id"],
        original_kernel_id=p.EXPECTED_KERNEL,
        original_generation_report_id=generation["id"],
        completion_freeze_id=completion["id"],
        original_registry_freeze_id=original["id"],
        execution_only_performance_revision=True,
        numerical_or_scientific_conditions_changed=False,
        actual_full_original_kernel_ID_equal=True,
        original_parent_reports_relabelled=False,
        training_configuration_id=config["id"],
    )
    decision = p.record(
        "actual_direction_decision", actual_complete=True, selected_arm="alpha0", paired_mean_gain=0
    )
    report = p.record(
        "execution_report",
        actual_complete=True,
        status="COMPLETE_NO_POSITIVE_DIRECTION",
        decision_id=decision["id"],
        study_freeze_id=original["id"],
        kernel_id=p.EXPECTED_KERNEL,
        training_configuration_id=config["id"],
        actual_training_runs=9,
        actual_evaluation_sessions=1620,
        confirmation_sessions=0,
        independent_positive_effect_confirmed=False,
    )
    producer = p.record(
        "evaluation_manifest", report_id=report["id"], phase="fixed_kernel_value_execution"
    )
    for name, value in (
        (p.OUTPUT + "/report.json", report),
        (p.OUTPUT + "/manifest.json", producer),
        (p.OUTPUT + "/decision.json", decision),
        (p.OUTPUT + "/preparation/execution_freeze.json", frozen),
        (p.OUTPUT + "/preparation/fast_execution_authority.json", authority),
        (p.MATERIALS + "/generation_report.json", generation),
        (p.MATERIALS + "/material_gate.json", gate),
        (p.MATERIALS + "/freeze.json", original),
        (p.MATERIALS + "/authorization.json", authorization),
        (p.MATERIALS + "/completion_freeze.json", completion),
    ):
        p.write_once(root / name, value)
    p.write_once(parent / p.MATERIALS / "material_gate.json", gate)
    old_manifest = manifest(
        parent,
        p,
        p.MATERIALS + "_publication/materials",
        stage="materials",
        source_root=p.MATERIALS,
        report_id=generation["id"],
    )
    (root / ".env").write_text("synthetic must-not-be-read sentinel")
    (parent / p.MATERIALS / "giant_original_session.json").write_text("never read by copy helper")
    return root, p, report, old_manifest


class StubGit:
    def __init__(self, *, dirty=False, push_failure=False):
        self.calls, self.staged, self.head = [], [], "committed_operator"
        self.dirty, self.push_failure = dirty, push_failure

    def __call__(self, root, *args, input=None):
        self.calls.append((args, input))
        output = b""
        if args[0] == "branch":
            output = b"synthetic_fast\n"
        elif args[:2] == ("rev-parse", "HEAD"):
            output = self.head.encode()
        elif args[0] == "show":
            output = (root / args[1].split(":", 1)[1]).read_bytes()
        elif args[:3] == ("diff", "--cached", "--name-only"):
            output = b"unrelated\0" if self.dirty else b"\0".join(self.staged)
        elif args[0] == "add":
            self.staged = input.rstrip(b"\0").split(b"\0")
        elif args[0] == "commit":
            self.head = "publication_commit"
        elif args[0] == "push" and self.push_failure:
            raise RuntimeError("synthetic push rejection")
        return SimpleNamespace(stdout=output)


def sealer(root, p, report, observed):
    def seal(code_root, data_root, stage, **kwargs):
        observed.append((stage, kwargs))
        assert code_root == root and data_root == p.DATA_ROOT and stage == "results"
        assert kwargs["allowlist"] == ["fast"] and kwargs["report_path"] == "fast/report.json"
        assert kwargs["source_output"] == "raw" and len(kwargs["approved_adapter_paths"]) == 9
        assert all(
            name.startswith("fast/training/A_") and name.endswith("/final_adapter.safetensors")
            for name in kwargs["approved_adapter_paths"]
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


@pytest.mark.parametrize("push_failure", [False, True])
def test_one_actual_result_seal_old_material_copy_and_independent_lineage(closed, push_failure):
    root, p, report, old_manifest = closed
    runner, observed = StubGit(push_failure=push_failure), []
    if push_failure:
        with pytest.raises(RuntimeError, match="push rejection"):
            helper.finalize(root, p, sealer=sealer(root, p, report, observed), runner=runner)
    else:
        assert (
            helper.finalize(root, p, sealer=sealer(root, p, report, observed), runner=runner)[
                "status"
            ]
            == "COMMITTED_AND_PUSHED"
        )
    assert len(observed) == 1 and observed[0][0] == "results"
    copied = p.read_json(root / (p.MATERIALS + "_publication/materials/publication_manifest.json"))
    assert copied == old_manifest
    assert not (p.PARENT_ROOT / (p.MATERIALS + "_workflow/terminal.json")).exists()
    assert not (root / (p.MATERIALS + "_workflow/terminal.json")).exists()
    assert [args for args, _ in runner.calls if args[0] == "add"] == [
        ("add", "--sparse", "--force", "--pathspec-from-file=-", "--pathspec-file-nul")
    ]
    assert [args for args, _ in runner.calls if args[0] == "push"] == [
        ("push", helper.REMOTE, helper.REFSPEC)
    ]
    assert not any(b".env" in name or b"giant_original" in name for name in runner.staged)
    text = (root / helper.SUMMARY).read_text()
    assert "不是原始未修订预注册方案" in text and "不是旧 completion 主进程直接执行" in text
    assert "independent_positive_effect_confirmed`：false" in text
    receipt = p.read_json(root / p.RUNTIME / "fast_publication_git_receipt.json")
    assert receipt["status"] == (
        "COMMITTED_PUSH_FAILED" if push_failure else "COMMITTED_AND_PUSHED"
    )


def test_missing_real_closure_never_invokes_sealer_or_git_writes(closed):
    root, p, report, _ = closed
    (root / p.OUTPUT / "manifest.json").rename(root / p.OUTPUT / "producer_manifest_retained.json")
    runner, observed = StubGit(), []
    with pytest.raises(ValueError, match="not_ready"):
        helper.finalize(root, p, sealer=sealer(root, p, report, observed), runner=runner)
    assert observed == [] and not any(
        args[0] in {"add", "commit", "push"} for args, _ in runner.calls
    )


def test_unrelated_staging_refused_before_lock_or_seal(closed):
    root, p, report, _ = closed
    runner, observed = StubGit(dirty=True), []
    with pytest.raises(ValueError, match="preexisting_staged"):
        helper.finalize(root, p, sealer=sealer(root, p, report, observed), runner=runner)
    assert observed == [] and not (root / p.RUNTIME / "fast_publication_operator.lock").exists()


def test_changed_old_archive_rejected_without_rescan_or_reseal(closed):
    root, p, _, old_manifest = closed
    path = p.PARENT_ROOT / (p.MATERIALS + "_publication/materials/raw-00000.tar.gz")
    path.write_bytes(b"corrupt sealed archive")
    with pytest.raises(ValueError, match="exact_SHA"):
        helper.copy_materials(root, p, old_manifest)
    assert not (root / (p.MATERIALS + "_publication/materials/publication_manifest.json")).exists()
