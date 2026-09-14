"""Tiny opaque-file stubs: no real Git, API, GPU, secret scan or raw replay."""

import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest

from trusted_synthesis.experiments.finance_qa_vnext_fixed_kernel_value import protocol as frozen_p

SCRIPT = (
    Path(__file__).resolve().parents[1] / "scripts/finalize_fixed_kernel_completion_20260914.py"
)
SPEC = importlib.util.spec_from_file_location("completion_publication_helper_test", SCRIPT)
helper = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(helper)


def make_closed(root, *, actual=False):
    p = SimpleNamespace(
        OUTPUT="raw",
        RUNTIME="runtime",
        BRANCH="synthetic_completion",
        **{
            name: getattr(frozen_p, name)
            for name in ("record", "checked", "read_json", "write_once", "encode")
        },
    )
    source = root / helper.COMPLETION_SOURCE
    source.parent.mkdir(parents=True)
    source.write_bytes(b"# Synthetic fixed completion source; never executed.\n")
    source_sha = helper.descriptor(root, helper.COMPLETION_SOURCE)["sha256"]
    original = p.record("study_freeze", old_closed=True)
    code = p.record("study_code_snapshot", synthetic=True)
    authorization = p.record(
        "kernel_completion_authorization",
        original_combined_token_cap=250000000,
        amended_combined_token_cap=350000000,
        new_purpose_token_cap=109024251,
        new_HTTP_request_cap=8300,
        common_token_cap=1000000000,
        already_finished_retained=9968,
        unfinished_slots=272,
        authenticated_prefix_responses=404,
        amendment_after_parent_budget_stop=True,
        unamended_preregistration_claimed=False,
    )
    parent = p.record(
        "completion_parent_binding",
        original_freeze_id=original["id"],
        commit="closed_parent_commit",
        generation_report_id="old_closed_report",
    )
    frozen = p.record(
        "kernel_completion_freeze",
        original_freeze_id=original["id"],
        authorization_id=authorization["id"],
        parent_binding_id=parent["id"],
        parent_commit=parent["commit"],
        output_directory=p.OUTPUT,
        code_snapshot_id=code["id"],
    )
    generation = p.record(
        "material_generation_report",
        generation_closed=True,
        no_inflight_requests=True,
        freeze_id=original["id"],
        completion_freeze_id=frozen["id"],
        budget_amendment_id=authorization["id"],
        parent_generation_report_id=parent["generation_report_id"],
        status="COMPLETE_FIXED_COLLECTION",
        registered_sessions=10240,
        finished_sessions=10240,
        inherited_finished_sessions=9968,
        newly_generated_session_records=272,
    )
    final = p.record(
        "kernel_budget_finalization",
        purpose_closed=True,
        report_id=generation["id"],
        freeze_id=original["id"],
        completion_freeze_id=frozen["id"],
        purpose="kernel_completion_registration",
    )
    gate = p.record(
        "material_gate",
        generation_report_id=generation["id"],
        training_gate="PASS" if actual else "FAIL",
    )
    started = p.record(
        "completion_workflow_started",
        completion_freeze_id=frozen["id"],
        material_gate_id=gate["id"],
        code_snapshot_id=code["id"],
        completion_source_sha256=source_sha,
        process_launcher_injected=False,
    )
    execution = None
    if actual:
        decision = p.record("actual_direction_decision", selected_arm=None, paired_mean_gain=-0.1)
        execution = p.record(
            "execution_report",
            actual_complete=True,
            decision_id=decision["id"],
            actual_training_runs=9,
            independent_positive_effect_confirmed=False,
        )
        p.write_once(root / "raw/student_execution/decision.json", decision)
        p.write_once(root / "raw/student_execution/report.json", execution)
    codes = {"materials_seal": 0, **({"results_seal": 0} if actual else {})}
    terminal = p.record(
        "completion_workflow_terminal",
        status="COMPLETE_ACTUAL_EXECUTION_AND_SEALS"
        if actual
        else "STOP_EXISTING_MATERIAL_GATE_FAIL",
        started_id=started["id"],
        completion_freeze_id=frozen["id"],
        material_gate_id=gate["id"],
        code_snapshot_id=code["id"],
        completion_source_sha256=source_sha,
        process_launcher_injected=False,
        actual_execution_complete=actual,
        actual_execution_report_id=execution["id"] if execution else None,
        child_exit_codes=codes,
        active_child_pids={},
        ended_at="synthetic_finished_time",
    )
    for name, value in (
        ("raw_workflow/started.json", started),
        ("raw_workflow/terminal.json", terminal),
        ("raw/freeze.json", original),
        ("raw/completion_freeze.json", frozen),
        ("raw/completion_code_snapshot.json", code),
        ("raw/authorization.json", authorization),
        ("raw/parent_binding.json", parent),
        ("raw/generation_report.json", generation),
        ("raw/budget_finalization.json", final),
        ("raw/material_gate.json", gate),
    ):
        p.write_once(root / name, value)
    for stage in ("materials", "results") if actual else ("materials",):
        sealed = root / ("raw_publication/" + stage)
        sealed.mkdir(parents=True)
        archive = sealed / "raw-00000.tar.gz"
        archive.write_bytes(b"opaque synthetic archive; never opened as tar or decompressed")
        page = sealed / "original_member_index-00000.json"
        p.write_once(page, p.record("original_member_index", rows=[], page=0))
        manifest = p.record(
            "publication_manifest",
            stage=stage,
            source_root="raw",
            closure={"report_id": (generation if stage == "materials" else execution)["id"]},
            archives=[helper.descriptor(sealed, archive.name)],
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
            root / f"raw_workflow/stages/{stage}_seal/exit.json",
            p.record("completion_stage_exit", stage=stage + "_seal", return_code=0),
        )
    (root / ".env").write_text("synthetic must-not-be-read sentinel")
    (root / "raw/giant_kernel.json").write_text("not a fixed report")
    (root / "raw_workflow/stages/materials_seal/console.log").write_text("not selected")
    return root, p


@pytest.fixture
def closed(tmp_path):
    return make_closed(tmp_path)


def test_exact_allowlist_reports_budget_amendment_and_no_scientific_pass(closed):
    root, p = closed
    evidence = helper.collect(root, p)
    names = {row["path"] for row in evidence["members"]}
    assert "raw_publication/materials/raw-00000.tar.gz" in names
    assert "raw/completion_freeze.json" in names and "raw/freeze.json" in names
    assert not any(
        ".env" in name or "giant_kernel" in name or name.endswith(".log") for name in names
    )
    text = helper.summary(evidence).decode()
    assert "材料门 FAIL" in text and "未提供／未测量" in text
    assert "不是原始未修订预注册" in text and "250,000,000" in text and "350,000,000" in text
    assert "没有宣称该阶段已封存" in text


@pytest.mark.parametrize("change", ["archive", "active_child", "source", "amendment"])
def test_reject_corrupt_or_unclosed_or_relabelled_inputs(closed, change):
    root, p = closed
    if change == "archive":
        (root / "raw_publication/materials/raw-00000.tar.gz").write_bytes(b"changed")
    elif change == "source":
        (root / helper.COMPLETION_SOURCE).write_bytes(b"changed source")
    else:
        path = root / "raw_workflow/terminal.json"
        old = p.read_json(path)
        fields = {k: v for k, v in old.items() if k not in {"id", "schema_version"}}
        fields.update(
            {"active_child_pids": {"materials_seal": 123}}
            if change == "active_child"
            else {"completion_freeze_id": p.read_json(root / "raw/freeze.json")["id"]}
        )
        path.write_bytes(p.encode(p.record("completion_workflow_terminal", **fields)))
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
            output = b"synthetic_completion\n"
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


def test_unrelated_staged_change_refused_before_summary_or_commit(closed):
    root, p = closed
    runner = StubGit(dirty=True)
    with pytest.raises(ValueError, match="preexisting_staged"):
        helper.finalize(root, p, runner=runner)
    assert not (root / helper.SUMMARY).exists()
    assert not any(args[0] in {"add", "commit", "push"} for args, _ in runner.calls)


@pytest.mark.parametrize("push_failure", [False, True])
def test_exact_sparse_allowlist_one_nonforced_push_and_one_archive_SHA_pass(
    closed, monkeypatch, push_failure
):
    root, p = closed
    runner, hashed = StubGit(push_failure=push_failure), []
    original = helper.descriptor

    def observed(root, name, limit=helper.SMALL_LIMIT):
        hashed.append(name)
        return original(root, name, limit)

    monkeypatch.setattr(helper, "descriptor", observed)
    if push_failure:
        with pytest.raises(RuntimeError, match="non-fast-forward"):
            helper.finalize(root, p, runner=runner)
    else:
        assert helper.finalize(root, p, runner=runner)["status"] == "COMMITTED_AND_PUSHED"
    assert [args for args, _ in runner.calls if args[0] == "push"] == [
        ("push", helper.REMOTE, "HEAD:refs/heads/main")
    ]
    assert [args for args, _ in runner.calls if args[0] == "add"] == [
        ("add", "--sparse", "--force", "--pathspec-from-file=-", "--pathspec-file-nul")
    ]
    assert not any(args[0] in {"checkout", "reset", "rebase", "merge"} for args, _ in runner.calls)
    assert hashed.count("raw_publication/materials/raw-00000.tar.gz") == 1
    assert not any(b".env" in name or b"giant_kernel" in name for name in runner.staged)
    receipt = p.read_json(root / "runtime/final_publication_receipt.json")
    assert receipt["commit"] == "new_commit" and receipt["parent_commit"] == "parent_commit"
    assert receipt["status"] == (
        "COMMITTED_PUSH_FAILED" if push_failure else "COMMITTED_AND_PUSHED"
    )


def test_actual_training_completion_does_not_invent_positive_effect(tmp_path):
    root, p = make_closed(tmp_path, actual=True)
    evidence = helper.collect(root, p)
    assert set(evidence["seals"]) == {"materials", "results"}
    text = helper.summary(evidence).decode()
    assert "`actual_training_runs`：9" in text
    assert "`independent_positive_effect_confirmed`：false" in text
    assert "科学结果为正" in text and "工程冒烟与正式训练分开计数" in text
