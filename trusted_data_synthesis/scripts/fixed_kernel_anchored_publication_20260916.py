"""Publish bounded aggregate milestones; raw trajectories and tensor files stay local."""

# ruff: noqa: E501 -- explicit publication scope and lineage
import json
import subprocess
from pathlib import Path

from trusted_synthesis.experiments.finance_qa_vnext_fixed_kernel_value import protocol as p


def publish(root, output, key, summary):
    root = Path(root).resolve()
    directory = root / output / "public"
    attempt = directory / (key + "_publication.json")
    if attempt.exists():
        return
    forbidden = {
        "prompt",
        "targets",
        "raw_response",
        "input_ids",
        "generated_token_ids",
        "weights",
        "theta",
        "gradient",
        "C",
        "pi_next",
    }

    def validate(value):
        if isinstance(value, dict):
            p.require(
                not forbidden.intersection(value), "publication.no_raw_tensor_or_session_payload"
            )
            for item in value.values():
                validate(item)
        elif isinstance(value, list):
            p.require(len(value) <= 16, "publication.bounded_aggregate_lists")
            for item in value:
                validate(item)

    validate(summary)
    fields = {
        name: value for name, value in summary.items() if name not in {"id", "schema_version"}
    }
    if "id" in summary:
        fields["source_report_id"] = summary["id"]
    raw = p.encode(fields)
    p.require(len(raw) < 65536, "publication.small_summary_only")
    path = directory / (key + ".json")
    doc = root / "trusted_data_synthesis/docs/anchored_A" / (key + "_20260916.md")
    try:
        p.write_once(path, p.record("anchored_A_public_milestone", **fields))
        doc.parent.mkdir(parents=True, exist_ok=True)
        with doc.open("x") as stream:
            stream.write(
                "# 已登记anchored A阶段记录\n\n自动生成的汇总；原始会话、模型和梯度张量留在本地。\n\n"
                "随机反馈效用不等于最终greedy效用。dev已参与元优化，不是独立确认。Full是唯一主候选，B/确认仍关闭。\n\n```json\n"
                + json.dumps(fields, ensure_ascii=False, indent=2)
                + "\n```\n"
            )
        paths = [str(path.relative_to(root)), str(doc.relative_to(root))]
        subprocess.run(["git", "add", "--sparse", "-f", "--", *paths], cwd=root, check=True)
        subprocess.run(
            [
                "git",
                "commit",
                "--only",
                "-m",
                "Record registered anchored A milestone " + key,
                "--",
                *paths,
            ],
            cwd=root,
            check=True,
        )
        commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
        authorization = root / output / "runtime/publication_authorization.json"
        approved = authorization.exists() and p.read_json(authorization).get("authorized") is True
        if approved:
            subprocess.run(
                [
                    "git",
                    "-c",
                    "http.proxy=",
                    "push",
                    "https://github.com/haoyueliuzhao/Data-Synthesis.git",
                    "HEAD:main",
                ],
                cwd=root,
                check=True,
            )
        result = dict(
            status="PUBLISHED"
            if approved
            else "COMMITTED_LOCALLY_AWAITING_SPECIFIC_PUBLICATION_APPROVAL",
            commit=commit,
        )
    except Exception as failure:
        result = dict(
            status="PUBLICATION_FAILED_SCIENTIFIC_RUN_UNAFFECTED", error_type=type(failure).__name__
        )
    p.write_once(attempt, p.record("anchored_A_publication_attempt", **result, at=p.now()))


def completed_json(path):
    if not path.exists() or not path.stat().st_size:
        return None
    try:
        return p.read_json(path)
    except json.JSONDecodeError:
        return None  # A new writer may still be flushing; never re-execute scientific work.


def milestones(root, output, plan):
    root = Path(root).resolve()
    for run in plan["runs"]:
        directory = root / output / "runs" / run["key"]
        for label, step in (("epoch0", 0), ("epoch5", 200)):
            key = run["key"] + "_" + label
            if (root / output / "public" / (key + "_publication.json")).exists():
                continue
            report = completed_json(directory / "rounds" / label / "report.json")
            updated = completed_json(directory / "updates" / f"{step + 1:04d}/report.json")
            if report is not None and updated is not None:
                p.require(
                    updated["optimizer_step_calls"] == 1, "publication.real_following_inner_update"
                )
                contribution = p.read_json(directory / "rounds" / label / "C.json")
                publish(
                    root,
                    output,
                    key,
                    dict(
                        run=run,
                        actual_Student_updates_completed_at_milestone=step + 1,
                        full_population_G_computed=report["full_G"],
                        formal_feedback_sessions=360,
                        stochastic_qualified=report["qualified"],
                        denominator=360,
                        gJ_report_id=report["gJ_id"],
                        centered_Contribution_id=report["C_id"],
                        C_absolute_maximum=max(
                            abs(value)
                            for row in contribution["C"].values()
                            for value in row.values()
                        ),
                        centering_residual_maximum=max(
                            abs(value) for value in contribution["centering_residuals"].values()
                        ),
                        distribution_update_id=report["update_id"],
                        update_status=report["update_status"],
                        novelty_active=report["novelty_active"],
                        source_report_id=report["id"],
                        B_and_confirmation=0,
                        at=p.now(),
                    ),
                )
        report = completed_json(directory / "report.json")
        if report is not None:
            publish(
                root,
                output,
                run["key"] + "_final",
                {
                    key: report[key]
                    for key in (
                        "run",
                        "status",
                        "actual_optimizer_updates",
                        "actual_feedback_sessions",
                        "final_greedy_sessions",
                        "final_qualified",
                        "denominator",
                        "final_point_id",
                        "actual_generate_calls",
                        "development_participated_in_meta_learning",
                    )
                },
            )
