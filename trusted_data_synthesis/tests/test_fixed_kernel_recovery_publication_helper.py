"""Small stub checks; never call real Git, producers, wallets, APIs or GPUs."""

import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest

from trusted_synthesis.experiments.finance_qa_vnext_fixed_kernel_value import protocol as frozen_p

SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "scripts/finalize_fixed_kernel_writer_recovery_publication_20260913.py"
)
SPEC = importlib.util.spec_from_file_location("recovery_publication_helper_test", SCRIPT)
helper = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(helper)


@pytest.fixture
def closed(tmp_path):
    p = SimpleNamespace(
        OUTPUT="raw",
        RUNTIME="runtime",
        BRANCH="synthetic_recovery",
        **{
            name: getattr(frozen_p, name)
            for name in ("record", "checked", "read_json", "write_once", "encode")
        },
    )
    operator_path = tmp_path / helper.OPERATOR_SCRIPT
    operator_path.parent.mkdir(parents=True)
    operator_path.write_bytes(b"# Synthetic operator source, never executed.\n")
    source_sha = helper.descriptor(tmp_path, helper.OPERATOR_SCRIPT)["sha256"]
    started = p.record(
        "operator_workflow_started",
        process_launcher_injected=False,
        operator_source_sha256=source_sha,
        code_root=str(tmp_path),
        raw_directory=str(tmp_path / "raw"),
    )
    generation = p.record(
        "material_generation_report",
        generation_closed=True,
        no_inflight_requests=True,
        registered_sessions=10240,
        status="STOP_INCOMPLETE_OR_CONTRACT",
    )
    final = p.record("kernel_budget_finalization", purpose_closed=True, report_id=generation["id"])
    gate = p.record("material_gate", generation_report_id=generation["id"], training_gate="FAIL")
    terminal = p.record(
        "operator_workflow_terminal",
        status="STOP_EXISTING_MATERIAL_GATE_FAIL",
        started_id=started["id"],
        source_script_sha256=source_sha,
        process_launcher_injected=False,
        material_gate_id=gate["id"],
        child_exit_codes={"materials_seal": 0},
        actual_execution_complete=False,
    )
    for name, value in (
        ("raw_workflow/started.json", started),
        ("raw_workflow/terminal.json", terminal),
        ("raw/generation_report.json", generation),
        ("raw/budget_finalization.json", final),
        ("raw/material_gate.json", gate),
        (
            "raw/recovery_parent_binding.json",
            p.record("recovery_parent_binding", protected_parent_commit="old_closed_commit"),
        ),
    ):
        p.write_once(tmp_path / name, value)
    sealed = tmp_path / "raw_publication/materials"
    sealed.mkdir(parents=True)
    archive = sealed / "raw-00000.tar.gz"
    archive.write_bytes(b"synthetic opaque container; not unpacked or semantically revalidated")
    archive_row = helper.descriptor(sealed, archive.name)
    page = sealed / "original_member_index-00000.json"
    p.write_once(page, p.record("original_member_index", page=0, rows=[]))
    manifest = p.record(
        "publication_manifest",
        stage="materials",
        source_root="raw",
        closure={"report_id": generation["id"]},
        archives=[archive_row],
        member_index_pages=[helper.descriptor(sealed, page.name)],
        physical_member_index_pages=[],
        duplicate_content_index_pages=[],
        actual_credential_scanned=True,
        credential_hits=0,
        wallet_runtime_credentials_or_base_weights_published=False,
        all_original_member_SHA_and_roundtrips_verified=True,
        original_file_count=3,
        original_bytes=1234,
    )
    p.write_once(sealed / "publication_manifest.json", manifest)
    p.write_once(
        tmp_path / "raw_workflow/stages/materials_seal/result.json",
        p.record("operator_stage_result", stage="materials_seal", result_id=manifest["id"]),
    )
    (tmp_path / ".env").write_text("synthetic must-not-be-read sentinel")
    (tmp_path / "raw/giant_kernel.json").write_text("not an allowed top-level report")
    (tmp_path / "raw_workflow/stages/materials_seal/console.log").write_text("not selected")
    return tmp_path, p


def test_exact_manifest_allowlist_and_fail_not_scientific_pass(closed):
    root, p = closed
    result = helper.collect(root, p)
    names = {row["path"] for row in result["members"]}
    assert "raw_publication/materials/raw-00000.tar.gz" in names
    assert "raw_publication/materials/original_member_index-00000.json" in names
    assert not any(
        ".env" in name or "giant_kernel" in name or name.endswith(".log") for name in names
    )
    markdown = helper.summary(result).decode()
    assert "材料门 FAIL" in markdown and "未提供／未测量" in markdown
    assert "没有宣称该阶段已封存" in markdown


@pytest.mark.parametrize("change", ["archive_bytes", "active_child", "injected", "source_change"])
def test_reject_corrupt_archive_active_child_or_synthetic_terminal(closed, change):
    root, p = closed
    if change == "archive_bytes":
        (root / "raw_publication/materials/raw-00000.tar.gz").write_bytes(b"changed")
    elif change == "source_change":
        (root / helper.OPERATOR_SCRIPT).write_bytes(b"modified after operator started")
    else:
        path = root / "raw_workflow/terminal.json"
        old = p.read_json(path)
        fields = {key: value for key, value in old.items() if key not in {"id", "schema_version"}}
        fields.update(
            {"active_child_pids": {"materials_seal": 123}}
            if change == "active_child"
            else {"process_launcher_injected": True}
        )
        path.write_bytes(p.encode(p.record("operator_workflow_terminal", **fields)))
    with pytest.raises(ValueError):
        helper.collect(root, p)


class StubGit:
    def __init__(self, *, dirty=False, push_failure=False):
        self.calls, self.staged, self.head = [], [], "parent_commit"
        self.dirty, self.push_failure = dirty, push_failure

    def __call__(self, root, *args, input=None):
        self.calls.append((args, input))
        output = b""
        if args[0] == "branch":
            output = b"synthetic_recovery\n"
        elif args[:2] == ("rev-parse", "HEAD"):
            output = self.head.encode()
        elif args[:3] == ("diff", "--cached", "--name-only"):
            output = b"unrelated_user_file\0" if self.dirty else b"\0".join(self.staged)
        elif args[0] == "add":
            self.staged = input.rstrip(b"\0").split(b"\0")
        elif args[0] == "commit":
            self.head = "new_commit"
        elif args[0] == "push" and self.push_failure:
            raise RuntimeError("synthetic non-fast-forward rejection")
        return SimpleNamespace(stdout=output)


def test_unrelated_staged_change_refused_before_artifact_writes(closed):
    root, p = closed
    runner = StubGit(dirty=True)
    with pytest.raises(ValueError, match="preexisting_staged"):
        helper.finalize(root, p, runner=runner)
    assert not (root / helper.SUMMARY).exists()
    assert not any(args[0] in {"add", "commit", "push"} for args, _ in runner.calls)


@pytest.mark.parametrize("push_failure", [False, True])
def test_exact_commit_and_one_nonforced_push_preserve_failure_receipt(closed, push_failure):
    root, p = closed
    runner = StubGit(push_failure=push_failure)
    if push_failure:
        with pytest.raises(RuntimeError, match="non-fast-forward"):
            helper.finalize(root, p, runner=runner)
    else:
        assert helper.finalize(root, p, runner=runner)["status"] == "COMMITTED_AND_PUSHED"
    pushes = [args for args, _ in runner.calls if args[0] == "push"]
    assert pushes == [("push", helper.REMOTE, "HEAD:refs/heads/main")]
    adds = [args for args, _ in runner.calls if args[0] == "add"]
    assert adds == [("add", "--force", "--pathspec-from-file=-", "--pathspec-file-nul")]
    assert not any(args[0] in {"checkout", "reset", "rebase", "merge"} for args, _ in runner.calls)
    assert not any(b".env" in name or b"giant_kernel" in name for name in runner.staged)
    receipt = p.read_json(root / "runtime/final_publication_receipt.json")
    assert receipt["commit"] == "new_commit" and receipt["parent_commit"] == "parent_commit"
    assert receipt["status"] == (
        "COMMITTED_PUSH_FAILED" if push_failure else "COMMITTED_AND_PUSHED"
    )
