"""Registered execution-only guard revision; original B sources and protocol stay immutable."""

# ruff: noqa: E501 -- explicit audit and recovery contracts
import argparse
import copy
import os
import subprocess
import sys
from pathlib import Path

import fixed_kernel_B_common_20260922 as b
import fixed_kernel_B_control_guard_20260924 as guard
import fixed_kernel_B_training_worker_20260922 as training
import run_fixed_kernel_B_confirmation_20260922 as runner

p = b.p
SCRIPT = "trusted_data_synthesis/scripts/resume_fixed_kernel_B_control_guard_20260924.py"
GUARD = "trusted_data_synthesis/scripts/fixed_kernel_B_control_guard_20260924.py"
NAME = "control_guard_20260924"
TARGET = "B_delayed_c_11"
ERROR = "ValueError('fixed_kernel.B_training.control_prior_unchanged')"
PLAN_ID = "B_confirm_protocol:0dba5b5625fbf37d7e4f93fc0b7636cba1df66a1fec611e6af67d6a5710bbe1a"
BASE_IMPLEMENTATION = runner.implementation
BASE_PUBLISH = runner.publish_completed


def directory():
    return b.RAW / "revisions" / NAME


def _reference(relative):
    path = b.RAW / relative
    return dict(path=relative, sha256=p.sha(path), bytes=path.stat().st_size)


def require_quiescent():
    paths = [b.RAW / "control/watchdog_identity.json", b.RAW / "control/controller_identity.json"]
    paths.extend(sorted((b.RAW / "worker_identities").glob("*/*.json")))
    for path in paths:
        if path.exists():
            value = p.read_json(path)
            identity = value.get("identity", value)
            p.require(
                not runner.identity.same_process(identity),
                "B_revision.no_live_original_process:" + str(path),
            )


def require_revision(root):
    root = Path(root).resolve()
    revision = p.checked(
        p.read_json(directory() / "registration.json"), "B_control_guard_execution_revision"
    )
    plan = b.read_protocol(root)
    p.require(
        plan["id"] == revision["protocol_id"] == PLAN_ID, "B_revision.original_scientific_plan"
    )
    p.require(
        p.sha(b.RAW / "protocol.json") == revision["protocol_sha256"],
        "B_revision.original_protocol_bytes",
    )
    p.require(
        (b.RAW / "implementation.json").exists(), "B_revision.original_implementation_required"
    )
    implementation = BASE_IMPLEMENTATION(root, plan)
    p.require(
        implementation["id"] == revision["original_implementation_id"]
        and p.sha(b.RAW / "implementation.json") == revision["original_implementation_sha256"],
        "B_revision.original_implementation_bytes",
    )
    p.require(
        set(revision["new_sources"]) == {SCRIPT, GUARD},
        "B_revision.only_registered_execution_sources",
    )
    for name, digest in revision["new_sources"].items():
        p.require(p.sha(root / name) == digest, "B_revision.frozen_new_source:" + name)
    p.require(
        revision["physical_budget"] == plan["physical_budget"]
        and revision["effective_budget"] == plan["effective_budget"],
        "B_revision.no_budget_expansion",
    )
    failed = revision["failed_attempt"]
    p.require(
        p.sha(b.RAW / failed["path"]) == failed["sha256"], "B_revision.original_failure_preserved"
    )
    return revision, plan


def register(root):
    root = Path(root).resolve()
    if (directory() / "registration.json").exists():
        return require_revision(root)[0]
    with (
        b.locked(b.RAW / "watchdog.lock", blocking=False),
        b.locked(b.RAW / "controller.lock", blocking=False),
    ):
        require_quiescent()
        plan = b.read_protocol(root)
        p.require(plan["id"] == PLAN_ID, "B_revision.exact_authorized_experiment")
        p.require(
            (b.RAW / "implementation.json").exists(), "B_revision.original_implementation_required"
        )
        implementation = BASE_IMPLEMENTATION(root, plan)
        state = p.read_json(b.RAW / "control/state.json")
        failed_path = f"results/{TARGET}/0001.json"
        failed = p.read_json(b.RAW / failed_path)
        p.require(
            failed["key"] == TARGET
            and failed["attempt"] == 1
            and failed["returncode"] == 1
            and failed["error"] == ERROR,
            "B_revision.only_authorized_failure",
        )
        p.require(
            not state["active"]
            and {key for key, row in state["jobs"].items() if row["stopped"]} == {TARGET}
            and state["jobs"][TARGET]["stopped"] == failed
            and state["jobs"][TARGET]["attempt"] == 1,
            "B_revision.single_known_stopped_job",
        )
        for path in (b.RAW / "results").glob("*/*.json"):
            value = p.read_json(path)
            p.require(
                value["returncode"] == 0 or value == failed,
                "B_revision.no_unreviewed_other_failure",
            )
        reports = []
        for seed in plan["seeds"]:
            for condition, step in (("prefix", 200), ("static", 400)):
                relative = f"jobs/B_{condition}_{seed}/report.json"
                report = p.checked(p.read_json(b.RAW / relative), "B_training_job_report")
                p.require(
                    report["complete"]
                    and report["plan_id"] == plan["id"]
                    and report["completed_updates"] == step
                    and Path(report["checkpoint_path"]).is_file(),
                    "B_revision.preserve_completed_training",
                )
                reports.append(
                    dict(
                        **_reference(relative),
                        report_id=report["id"],
                        checkpoint_sha256=report["checkpoint_sha256"],
                    )
                )
            p.require(
                not list((b.RAW / "jobs" / f"B_delayed_c_{seed}" / "updates").glob("*.pt")),
                "B_revision.no_prior_Delayed_tail_updates",
            )
        p.require(
            not (b.RAW / "generation/confirm").exists(),
            "B_revision.before_any_confirmation_generation",
        )
        job = training._job(plan, TARGET)
        prefix = p.checked(
            p.read_json(b.RAW / "jobs" / TARGET / "branch_binding.json"),
            "B_shared_prefix_branch_binding",
        )
        try:
            training._distribution(b, plan, job, prefix)
        except ValueError as error:
            p.require(
                str(error) == "fixed_kernel.B_training.control_prior_unchanged",
                "B_revision.reproduce_only_known_guard",
            )
        else:
            raise ValueError("B_revision.original_failure_not_reproduced")
        returned = guard.revised_distribution(b, plan, job, prefix)
        updated = p.read_json(b.RAW / "outer" / TARGET / "distribution_update.json")
        p.require(returned == updated["pi_next"], "B_revision.saved_pi_returned_without_change")
        head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
        sources = {}
        for name in (SCRIPT, GUARD):
            payload = (root / name).read_bytes()
            p.require(
                payload == subprocess.check_output(["git", "show", head + ":" + name], cwd=root),
                "B_revision.committed_new_source_before_registration",
            )
            sources[name] = p.sha(payload)
        revision = p.record(
            "B_control_guard_execution_revision",
            authorization="2026-09-24 user 同意: 登记校验修订并从现有保存点恢复后续实验",
            scope="control distribution scalar representation equality only; no numerical algorithm, values, scoring, tasks or budget change",
            protocol_id=plan["id"],
            protocol_sha256=p.sha(b.RAW / "protocol.json"),
            original_implementation_id=implementation["id"],
            original_implementation_sha256=p.sha(b.RAW / "implementation.json"),
            original_code_commit=plan["code_commit"],
            code_commit=head,
            new_sources=sources,
            original_scientific_sources_unchanged=True,
            original_failure_reproduced=True,
            guard_rule="frozen anchored distribution._scalar on each control value, followed by exact ==; no tolerance; never write back or recompute pi",
            real_control_tasks_checked=len(plan["materials"]["binding"]["control_tasks"]),
            saved_pi_sha256=p.sha(p.encode(returned)),
            saved_pi_unchanged=True,
            failed_attempt=_reference(failed_path),
            completed_training=reports,
            state_before=_reference("control/state.json"),
            needs_attention_before=_reference("needs_attention.json"),
            budget_before=_reference("budget/state.json"),
            budget_counts_before=p.read_json(b.RAW / "budget/state.json")["counts"],
            effective_budget=plan["effective_budget"],
            physical_budget=plan["physical_budget"],
            only_stop_to_clear=TARGET,
            previous_attempt_preserved=1,
            no_existing_training_feedback_scoring_or_replay_repeated=True,
            confirmation_results_read=False,
            completion_revision_link=str(directory() / "completion_link.json"),
            at=p.now(),
        )
        b.write(directory() / "registration.json", revision)
        b.emit(
            dict(
                event="B_control_guard_revision_registered",
                revision_id=revision["id"],
                code_commit=head,
            )
        )
        return revision


def resume_control(root):
    revision, _ = require_revision(root)
    receipt_path = directory() / "resume_applied.json"
    if receipt_path.exists():
        receipt = p.checked(p.read_json(receipt_path), "B_control_guard_resume_applied")
        p.require(receipt["revision_id"] == revision["id"], "B_revision.applied_same_revision")
        return receipt
    with (
        b.locked(b.RAW / "watchdog.lock", blocking=False),
        b.locked(b.RAW / "controller.lock", blocking=False),
        b.locked(b.RAW / "budget.lock"),
    ):
        require_quiescent()
        before_path = directory() / "archive/control_state_before.json"
        if not before_path.exists():
            payload = (b.RAW / "control/state.json").read_bytes()
            p.require(
                p.sha(payload) == revision["state_before"]["sha256"],
                "B_revision.unchanged_failed_control_state",
            )
            b.durable.atomic_bytes(before_path, payload, immutable=True)
        p.require(
            p.sha(before_path) == revision["state_before"]["sha256"],
            "B_revision.original_control_archive",
        )
        before = p.read_json(before_path)
        after = copy.deepcopy(before)
        p.require(
            not before["active"]
            and before["jobs"][TARGET]["attempt"] == 1
            and before["jobs"][TARGET]["stopped"]["error"] == ERROR,
            "B_revision.only_known_stop_released",
        )
        after["jobs"][TARGET]["stopped"] = None
        after["jobs"][TARGET]["not_before"] = 0
        after["jobs"][TARGET]["resumed_by_revision"] = revision["id"]
        p.require(
            p.sha(b.RAW / "control/state.json")
            in (revision["state_before"]["sha256"], p.sha(p.encode(after))),
            "B_revision.no_unrelated_control_overwrite",
        )
        p.require(
            p.sha(b.RAW / "budget/state.json") == revision["budget_before"]["sha256"],
            "B_revision.budget_and_attempt_ledger_unchanged",
        )
        attention = b.RAW / "needs_attention.json"
        archived_attention = directory() / "archive/needs_attention_resolved.json"
        if attention.exists():
            p.require(
                p.sha(attention) == revision["needs_attention_before"]["sha256"],
                "B_revision.only_registered_attention_marker",
            )
        else:
            p.require(
                archived_attention.exists()
                and p.sha(archived_attention) == revision["needs_attention_before"]["sha256"],
                "B_revision.resolved_marker_preserved",
            )
        intent_path = directory() / "resume_intent.json"
        fields = dict(
            revision_id=revision["id"],
            job_key=TARGET,
            state_before_sha256=revision["state_before"]["sha256"],
            state_after_sha256=p.sha(p.encode(after)),
            budget_sha256=revision["budget_before"]["sha256"],
            attempt_count_before=1,
            attempt_count_after=1,
        )
        if intent_path.exists():
            intent = p.checked(p.read_json(intent_path), "B_control_guard_resume_intent")
            p.require(
                all(intent[key] == value for key, value in fields.items()),
                "B_revision.same_interrupted_resume_intent",
            )
        else:
            intent = p.record("B_control_guard_resume_intent", **fields, at=p.now())
            b.write(intent_path, intent)
        for relative in ("heartbeat.json", "watchdog_status.json"):
            path = b.RAW / relative
            if path.exists():
                b.durable.atomic_bytes(
                    directory() / "archive" / relative, path.read_bytes(), immutable=True
                )
        b.write(b.RAW / "control/state.json", after, immutable=False)
        if attention.exists():
            p.require(not archived_attention.exists(), "B_revision.no_attention_archive_overwrite")
            archived_attention.parent.mkdir(parents=True, exist_ok=True)
            attention.rename(archived_attention)
            for folder in (archived_attention.parent, b.RAW):
                fd = os.open(folder, os.O_RDONLY | os.O_DIRECTORY)
                try:
                    os.fsync(fd)
                finally:
                    os.close(fd)
        receipt = p.record(
            "B_control_guard_resume_applied",
            revision_id=revision["id"],
            intent_id=intent["id"],
            state_after_sha256=fields["state_after_sha256"],
            old_failure_retained=True,
            old_attention_archive=str(archived_attention),
            budget_unchanged=True,
            previous_attempt_preserved=1,
            at=p.now(),
        )
        b.write(receipt_path, receipt)
        b.emit(
            dict(
                event="B_control_guard_stop_resolved",
                revision_id=revision["id"],
                next_training_attempt=2,
            )
        )
        return receipt


def install(root, mode, job=None, attempt=None):
    revision, _ = require_revision(root)
    applied = p.checked(
        p.read_json(directory() / "resume_applied.json"), "B_control_guard_resume_applied"
    )
    p.require(
        applied["revision_id"] == revision["id"], "B_revision.resume_authority_before_execution"
    )
    training._distribution = guard.revised_distribution
    runner.SCRIPT = SCRIPT  # Every child re-enters this registered wrapper before the frozen DAG.

    def checked_implementation(root, plan):
        require_revision(root)
        return BASE_IMPLEMENTATION(root, plan)

    runner.implementation = checked_implementation

    def revised_publication(root, report):
        current, _ = require_revision(root)
        link = p.record(
            "B_control_guard_completed_report_link",
            revision_id=current["id"],
            protocol_id=report["protocol_id"],
            scientific_report_id=report["id"],
            execution_code_commit=current["code_commit"],
            original_report_and_scientific_conclusions_not_modified=True,
        )
        b.write(directory() / "completion_link.json", link)
        return BASE_PUBLISH(root, report)

    runner.publish_completed = revised_publication
    identity = runner.identity.identity(os.getpid())
    receipt = p.record(
        "B_control_guard_execution_process",
        revision_id=revision["id"],
        code_commit=revision["code_commit"],
        mode=mode,
        job_key=job,
        attempt=attempt,
        identity=identity,
        guard_installed=True,
        at=p.now(),
    )
    b.write(
        directory() / "processes" / f"{identity['pid']}_{identity['start_ticks']}.json", receipt
    )
    if mode == "worker":
        b.write(directory() / "workers" / job / f"{attempt:04d}.json", receipt)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--mode",
        required=True,
        choices=("register", "resume", "start", "watch", "coordinate", "worker"),
    )
    parser.add_argument("--job")
    parser.add_argument("--attempt", type=int)
    parser.add_argument("--required-MiB", type=int, default=32768)
    args = parser.parse_args()
    root = args.root.resolve()
    if args.mode == "register":
        register(root)
        return 0
    if args.mode == "resume":
        resume_control(root)
        return 0
    install(root, args.mode, args.job, args.attempt)
    return runner.main()


if __name__ == "__main__":
    sys.exit(main())
