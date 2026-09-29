"""Bounded offline attribution of existing review artifacts; never rejudge a trace.

Only registered response/assessment files are read. No wallet, API, GPU,
generation inventory, process control, validator rerun, or label repair occurs.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

from trusted_synthesis.core.immutable_artifacts import write_immutable_artifact_directory

from .contracts import digest
from .v8_review_policy import nonassertive_fragment_kind

STUDY = Path(
    "/data1/zhuxinrui/projects/Data-Synthesis/trusted_data_synthesis/artifacts/"
    "finance_research_20260928/finqa_v6_01"
)
TECHNICAL = STUDY / "audit_revision_20260929/review_validation_108_01"
PRODUCTION = STUDY / "conditional_five_arm_v9_01"
OUTPUT = STUDY / "process_review_v10_01/review_failure_audit_01"
NETWORK_TERMINAL = "acknowledged_connection_unknown_no_model_response"
FAILURE_CASES = {
    "structure_or_return_format_failure",
    "annotation_internal_inconsistency",
    "network_unknown_no_model_response",
    "consistent_reviewer_invalid_claim",
    "consistent_reviewer_unknown",
    "unrecognized_assessment_shape",
}


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _now():
    return datetime.now(timezone.utc).isoformat()


def _read(path):
    path = Path(path)
    raw = path.read_bytes()
    return json.loads(raw), dict(
        path=str(path.resolve()), sha256=hashlib.sha256(raw).hexdigest(), bytes=len(raw)
    )


def _error(assessment):
    validation = assessment.get("validation") or {}
    value = assessment.get("error") or validation.get("semantic_validation_error")
    return (
        value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, sort_keys=True)
    )


def annotation_family(error):
    """Descriptive buckets only: not alternate acceptance criteria or financial labels."""
    value = str(error).lower()
    if "nonassertive" in value:
        return "nonassertive_surface_rule_rejection"
    if "approved span needs reviewed proposition" in value:
        return "approved_fragment_missing_proposition_link"
    if "node" in value or "graph" in value or "edge" in value:
        return "graph_or_node_annotation_binding"
    if re.search(r"\baction\b", value) and (
        "binding" in value or "proposition" in value or "evidence" in value
    ):
        return "action_annotation_binding"
    if any(term in value for term in ("mask", "target", "substring", "overlap")):
        return "target_coverage_or_mask_annotation"
    if "retract" in value:
        return "retraction_annotation_consistency"
    if "unresolved key claim" in value or "critical coverage" in value:
        return "reported_valid_vs_claim_annotation_inconsistency"
    if any(term in value for term in ("evidence", "span", "quote", "anchor", "source")):
        return "evidence_pointer_or_source_annotation"
    if any(term in value for term in ("term", "proposition", "claim")):
        return "term_or_proposition_annotation_binding"
    return "other_annotation_internal_inconsistency"


def classify_existing(stage, response, assessment):
    """Preserve current labels. ``invalid`` remains a reviewer claim, not ground truth."""
    if response is None:
        return dict(
            category="no_response_in_snapshot",
            actual_model_response=False,
            process_error_established=False,
            reported_v_trace=None,
            effective_v_trace=None,
        )
    if response.get("terminal_kind") == NETWORK_TERMINAL:
        return dict(
            category="network_unknown_no_model_response",
            actual_model_response=False,
            process_error_established=False,
            reported_v_trace=None,
            effective_v_trace="unknown",
        )
    if assessment is None:
        return dict(
            category="model_return_without_assessment_in_snapshot",
            actual_model_response=True,
            process_error_established=False,
            reported_v_trace=None,
            effective_v_trace=None,
        )
    validation = assessment.get("validation") or {}
    label = validation.get("v_trace")
    reported = validation.get("reported_v_trace")
    error = _error(assessment)
    if assessment.get("interface_admitted") is False:
        category = "structure_or_return_format_failure"
    elif assessment.get("interface_admitted") is not True:
        category = "unrecognized_assessment_shape"
    elif assessment.get("semantic_consistent") is False:
        category = "annotation_internal_inconsistency"
    elif assessment.get("semantic_consistent") is not True or not validation:
        category = "unrecognized_assessment_shape"
    elif stage == "alignment":
        category = "consistent_alignment_annotation"
    elif label == "valid":
        category = "consistent_reviewer_valid_label"
    elif label == "invalid":
        category = "consistent_reviewer_invalid_claim"
    elif label == "unknown":
        category = "consistent_reviewer_unknown"
    else:
        category = "unrecognized_assessment_shape"
    parsed_slot = (validation.get("parsed") or {}).get("slot") or {}
    propositions = parsed_slot.get("propositions") or []
    flags = [
        p
        for p in propositions
        if p.get("critical") is True
        and p.get("status") != "retracted"
        and p.get("judgment") != "supported"
    ]
    return dict(
        category=category,
        actual_model_response=True,
        reported_v_trace=reported,
        effective_v_trace=label,
        annotation_error=error
        if category
        in (
            "structure_or_return_format_failure",
            "annotation_internal_inconsistency",
            "unrecognized_assessment_shape",
        )
        else None,
        annotation_family=annotation_family(error)
        if category == "annotation_internal_inconsistency"
        else None,
        reviewer_reason_codes=parsed_slot.get("reason_codes") or [],
        annotated_unretracted_critical_nonsupported_propositions=len(flags),
        process_error_established=False,
        native_financial_error_frequency_measured=False,
    )


def _raw_excerpt(response, *, limit=800):
    text = response.get("review_text")
    if not isinstance(text, str):
        return None
    # Fixed field-first excerpt, never a favourable-content choice.
    location = text.find('"reason_codes"')
    if location < 0:
        location = text.find('"v_trace"')
    if location < 0:
        location = 0
    return dict(
        field="review_text",
        start=location,
        end=min(len(text), location + limit),
        exact_text=text[location : location + limit],
        selection="first reason_codes field, else first v_trace, else start; <=800 characters",
    )


def _case(job, order, response, assessment, classification, response_ref, assessment_ref):
    value = dict(
        protocol_job_index=order,
        job_key=job["key"],
        stage=job["stage"],
        task_id=job["task_id"],
        slot_id=job.get("slot_id"),
        reviewer=job["reviewer"],
        classification=classification,
        response=response_ref,
        assessment=assessment_ref,
        finish_reason=response.get("finish_reason"),
        review_format_error=response.get("review_format_error"),
        actual_return_excerpt=_raw_excerpt(response),
        case_selection="first jobs in unchanged protocol.jobs order within each category",
        is_independent_financial_reassessment=False,
    )
    validation = (assessment or {}).get("validation") or {}
    slot = (validation.get("parsed") or {}).get("slot") or {}
    rejected = []
    for span in slot.get("mask", []):
        if (
            span.get("label") == "nonassertive_context"
            and nonassertive_fragment_kind(span.get("quote")) is None
        ):
            rejected.append(
                {key: span.get(key) for key in ("doc_id", "start", "end", "quote", "label")}
            )
        if len(rejected) == 2:
            break
    value["first_model_labelled_fragments_outside_original_surface_rule"] = rejected
    value["fragments_are_reviewer_quotes_not_reaudited_against_Episode"] = True
    return value


def inspect_batch(root, *, case_limit=2):
    root = Path(root).resolve()
    started = _now()
    plan, protocol_ref = _read(root / "registration/protocol.json")
    _require(
        plan.get("id") == digest({k: v for k, v in plan.items() if k != "id"}),
        "registered protocol content changed",
    )
    _require(
        plan.get("schema")
        in {"v8_one_full_review_validation.v1", "v9_conditional_production_protocol.v1"},
        "only the existing V8 technical/V9 production protocol is in scope",
    )
    jobs = plan["jobs"]
    _require(
        len(jobs) == len({j["key"] for j in jobs}) and case_limit in (1, 2),
        "fixed unique registered jobs and bounded examples required",
    )
    # Freeze membership once. New publishes while scanning are explicitly outside
    # this snapshot; this is not a transaction over the live production directory.
    member_started = _now()
    responses = {p.resolve() for p in (root / "jobs").glob("*/response/record.json")}
    assessments = {p.resolve() for p in (root / "jobs").glob("*/assessment/record.json")}
    member_finished = _now()
    status, status_ref = (None, None)
    if (root / "status.json").exists():
        status, status_ref = _read(root / "status.json")
    stage_counts, categories, families, errors = (
        defaultdict(Counter),
        Counter(),
        Counter(),
        Counter(),
    )
    reported_labels, effective_labels, finish_reasons = Counter(), Counter(), Counter()
    interface_counts, consistent_counts = Counter(), Counter()
    reason_codes, invalid_claim_details = Counter(), Counter()
    examples, rows, files = defaultdict(list), [], []
    for index, job in enumerate(jobs):
        _require(job["stage"] in ("slot", "alignment"), "unknown registered stage")
        directory = root / "jobs" / job["key"].replace(":", "_")
        response_path, assessment_path = (
            directory / "response/record.json",
            directory / "assessment/record.json",
        )
        response, response_ref = (
            _read(response_path) if response_path in responses else (None, None)
        )
        assessment, assessment_ref = (
            _read(assessment_path) if assessment_path in assessments else (None, None)
        )
        classification = classify_existing(job["stage"], response, assessment)
        category = classification["category"]
        categories[category] += 1
        stage_counts[job["stage"]][category] += 1
        if classification["actual_model_response"] and assessment:
            interface_counts[job["stage"]] += assessment.get("interface_admitted") is True
            consistent_counts[job["stage"]] += assessment.get("semantic_consistent") is True
        if classification.get("annotation_family"):
            families[classification["annotation_family"]] += 1
        if classification.get("annotation_error"):
            errors[classification["annotation_error"]] += 1
        if job["stage"] == "slot" and classification["actual_model_response"]:
            reported_labels[str(classification.get("reported_v_trace"))] += 1
            effective_labels[str(classification.get("effective_v_trace"))] += 1
        if response is not None:
            finish_reasons[str(response.get("finish_reason"))] += 1
        if category == "consistent_reviewer_invalid_claim":
            reason_codes.update(classification["reviewer_reason_codes"])
            invalid_claim_details[
                "with_annotated_critical_nonsupported_proposition"
                if classification["annotated_unretracted_critical_nonsupported_propositions"]
                else "without_annotated_critical_nonsupported_proposition"
            ] += 1
        if category in FAILURE_CASES and len(examples[category]) < case_limit:
            examples[category].append(
                _case(
                    job,
                    index,
                    response or {},
                    assessment,
                    classification,
                    response_ref,
                    assessment_ref,
                )
            )
        rows.append(
            dict(
                protocol_job_index=index,
                job_key=job["key"],
                stage=job["stage"],
                task_id=job["task_id"],
                slot_id=job.get("slot_id"),
                reviewer=job["reviewer"],
                classification=classification,
                response=response_ref,
                assessment=assessment_ref,
            )
        )
        files.extend(ref for ref in (response_ref, assessment_ref) if ref is not None)
    _require(sum(categories.values()) == len(jobs), "original job denominator changed")
    schema = plan["schema"]
    actual_returned = sum(row["classification"]["actual_model_response"] for row in rows)
    report = dict(
        schema="v10_existing_review_failure_attribution.v1",
        source_protocol=protocol_ref,
        source_protocol_id=plan["id"],
        source_protocol_schema=schema,
        started_at=started,
        finished_at=_now(),
        membership_scan_started_at=member_started,
        membership_scan_finished_at=member_finished,
        member_file_count=len(files),
        global_atomic_snapshot_claimed=False,
        snapshot_policy=(
            "registered jobs only; response/assessment membership enumerated once; "
            "later files excluded"
        ),
        status_reference=status_ref,
        status_at_read={
            k: status.get(k)
            for k in (
                "at",
                "phase",
                "processed",
                "returned",
                "network_unknown_terminals",
                "dispatched",
            )
        }
        if status
        else None,
        original_job_denominator=len(jobs),
        original_stage_denominators=dict(Counter(j["stage"] for j in jobs)),
        observed_actual_model_responses=actual_returned,
        observed_network_unknown_terminals=categories["network_unknown_no_model_response"],
        categories=dict(categories),
        stage_categories={k: dict(v) for k, v in stage_counts.items()},
        annotation_failure_families=dict(families),
        stage_interface_admitted=dict(interface_counts),
        stage_semantically_consistent=dict(consistent_counts),
        exact_annotation_errors=dict(errors),
        slot_reported_v_trace=dict(reported_labels),
        slot_stored_effective_v_trace=dict(effective_labels),
        finish_reason_counts=dict(finish_reasons),
        consistent_invalid_reviewer_reason_codes=dict(reason_codes),
        consistent_invalid_annotation_content=dict(invalid_claim_details),
        examples=dict(examples),
        snapshot_file_bindings_sha256=digest(files),
        source_job_results_changed=False,
        old_unknown_reclassified=False,
        validator_rerun=False,
        model_calls=0,
        wallet_access=False,
        process_control=False,
        GPU_used=False,
        actual_trace_financial_error_rate=None,
        original_trace_semantic_quality_measured=False,
        selection_bias_magnitude_measured=False,
        interpretation=(
            "Structure failures and annotation inconsistencies concern the review interface. "
            "Consistent invalid labels/reason codes are reviewer allegations, "
            "not independently confirmed financial errors. Current partial production observations "
            "cannot estimate all8000 trace quality."
        ),
    )
    return report | dict(id=digest(report)), rows


def regex_examples():
    samples = (
        "I will inspect the public table.",
        "Let me inspect the public table.",
        "I will inspect the public table first.",
    )
    return [
        dict(
            text=text,
            classification=nonassertive_fragment_kind(text),
            synthetic_example=True,
            original_model_output=False,
            rule_was_modified=False,
        )
        for text in samples
    ]


def _markdown(report):
    lines = [
        "# 既有审阅失败离线归因（零模型）",
        "",
        "本报告不重判原轨迹、不更改任何旧标签，也未访问钱包或控制进程。",
        "",
    ]
    for name, batch in report["batches"].items():
        lines += [
            f"## {name}",
            "",
            f"固定登记分母：{batch['original_job_denominator']}；"
            f"本次文件快照中真实模型返回：{batch['observed_actual_model_responses']}；"
            f"无模型返回的网络 UNKNOWN：{batch['observed_network_unknown_terminals']}。",
            "",
            "这不是活跃目录的原子全局快照，晚于文件成员枚举的新结果不计入。",
            "",
            "### 分类",
            "",
        ]
        lines += [f"- `{key}`：{value}" for key, value in sorted(batch["categories"].items())]
        lines += ["", "### Annotation 内部不一致的描述性归因", ""]
        lines += [
            f"- `{key}`：{value}"
            for key, value in sorted(batch["annotation_failure_families"].items())
        ]
        lines += [
            "",
            "一致 invalid 仅代表原审阅器作出否定标签。"
            "理由代码是否成立、原金融过程是否真正出错，本次均未独立核验。",
            "",
            "invalid 的原注释字段分布：`"
            + json.dumps(batch["consistent_invalid_annotation_content"], ensure_ascii=False)
            + "`。没有列出否定关键命题，不证明轨迹有效；列出了也不自动证明原财务错误。",
            "",
            "### 固定顺序案例",
            "",
        ]
        for category, cases in batch["examples"].items():
            for case in cases:
                lines += [
                    f"- `{category}`，原 job 序号 {case['protocol_job_index']}，"
                    f"`{case['job_key']}`，"
                    f"任务 `{case['task_id']}`，审阅侧 {case['reviewer']}。"
                ]
                if case["classification"].get("annotation_error"):
                    lines += [
                        "  原检查错误：`"
                        + case["classification"]["annotation_error"].replace("`", "'")
                        + "`。"
                    ]
                if case["classification"].get("reviewer_reason_codes"):
                    lines += [
                        "  原模型理由代码：`"
                        + json.dumps(
                            case["classification"]["reviewer_reason_codes"], ensure_ascii=False
                        )
                        + "`。"
                    ]
                if case["response"]:
                    lines += [
                        f"  原返回：[record.json]({case['response']['path']})；"
                        f"SHA256 `{case['response']['sha256']}`。"
                    ]
                for fragment in case[
                    "first_model_labelled_fragments_outside_original_surface_rule"
                ]:
                    lines += [
                        "  审阅输出引用并标记为 nonassertive、但超出原表面规则的片段：`"
                        + str(fragment["quote"]).replace("`", "'")
                        + "`（本次没有重新核对原 Episode，也未判定其应被豁免）。"
                    ]
        lines += [""]
    lines += [
        "## 三个源码正则合成例证",
        "",
        "以下不是原批模型输出；只复现未改动的有限表面规则，不计入真实失败频数。",
        "",
    ]
    lines += [
        f"- `{row['text']}` → `{row['classification']}`"
        for row in report["synthetic_regex_examples"]
    ]
    lines += [
        "",
        "## 本次仍不可测",
        "",
        "原8000条真实关键过程错误率、内部思维忠实性、审阅标签准确率、由schema造成的选择偏差大小、简化规则后的有效材料增量，均不能由本次统计确定。过程问题与annotation失败不得合并为金融错误率；技术批与生产批不拼成同一成绩总体。",
        "",
        "本次只将已有记录按审计用途重新归类，不产生新的valid、不拓宽白名单、不提供训练准入。完整逐job绑定及短原返回引文见同目录JSON/JSONL。",
        "",
    ]
    return "\n".join(lines)


def run(output=OUTPUT, technical=TECHNICAL, production=PRODUCTION):
    output = Path(output)
    _require(not output.exists(), "dedicated immutable audit directory must be new")
    batches, files = {}, {}
    for name, path in (("technical108", technical), ("production_snapshot", production)):
        batches[name], rows = inspect_batch(path)
        files[name + ".jobs.jsonl"] = "".join(
            json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows
        ).encode()
    body = dict(
        schema="v10_review_failure_audit_bundle.v1",
        created_at=_now(),
        batches=batches,
        synthetic_regex_examples=regex_examples(),
        source_policies_unchanged=True,
        frozen_regex_source_sha256=hashlib.sha256(
            Path(__file__).with_name("v8_review_policy.py").read_bytes()
        ).hexdigest(),
        no_new_API_or_GPU=True,
        no_old_labels_changed=True,
        no_material_qualification_granted=True,
    )
    report = body | dict(id=digest(body))
    files["record.json"] = (
        json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    ).encode()
    files["report.md"] = _markdown(report).encode()
    write_immutable_artifact_directory(output, files)
    return report


def regroup_descriptive_families(source, output):
    """Correct lexical buckets from saved rows only; never reread API files."""
    source, output = Path(source), Path(output)
    _require(not output.exists(), "dedicated immutable correction directory must be new")
    report, original_ref = _read(source / "record.json")
    _require(
        report["id"] == digest({k: v for k, v in report.items() if k != "id"}),
        "original offline audit changed",
    )
    report = {k: v for k, v in report.items() if k != "id"}
    snapshot_refs = {}
    for name, batch in report["batches"].items():
        path = source / (name + ".jobs.jsonl")
        raw = path.read_bytes()
        rows = [json.loads(line) for line in raw.splitlines()]
        _require(len(rows) == batch["original_job_denominator"], "saved job denominator changed")
        families = Counter(
            annotation_family(row["classification"]["annotation_error"])
            for row in rows
            if row["classification"]["category"] == "annotation_internal_inconsistency"
        )
        batch["annotation_failure_families"] = dict(families)
        for cases in batch["examples"].values():
            for case in cases:
                classification = case["classification"]
                if classification.get("annotation_family"):
                    classification["annotation_family"] = annotation_family(
                        classification["annotation_error"]
                    )
        batch.pop("id", None)
        batch["id"] = digest(batch)
        snapshot_refs[name] = dict(
            path=str(path.resolve()),
            sha256=hashlib.sha256(raw).hexdigest(),
            bytes=len(raw),
            original_labels_and_categories_unchanged=True,
        )
    report.update(
        created_at=_now(),
        original_offline_audit=original_ref,
        original_job_row_sources=snapshot_refs,
        descriptive_regrouping_only=True,
        original_API_artifacts_reread=False,
        correction_reason=(
            "Require whole word action: retraction must not match its action substring. "
            "No category, original label, example choice or judgment changed."
        ),
    )
    report["id"] = digest(report)
    markdown = _markdown(report) + (
        "\n## 描述性归因修订说明\n\n"
        "初版将 retraction 中的 action 子串误归入动作标注类；本版仅将 action 匹配改为完整词，"
        "从初版已封存逐job摘要重算描述性family，不重读原API文件。原判定、主分类计数、"
        "例子选择和有效性均未改变。初版及完整逐job摘要永久保留，来源绑定见本版JSON。\n"
    )
    write_immutable_artifact_directory(
        output,
        {
            "record.json": (
                json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
            ).encode(),
            "report.md": markdown.encode(),
        },
    )
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--technical", type=Path, default=TECHNICAL)
    parser.add_argument("--production", type=Path, default=PRODUCTION)
    parser.add_argument("--regroup-from", type=Path)
    args = parser.parse_args(argv)
    report = (
        regroup_descriptive_families(args.regroup_from, args.output)
        if args.regroup_from
        else run(args.output, args.technical, args.production)
    )
    print(
        json.dumps(
            dict(
                id=report["id"],
                output=str(args.output),
                batches={
                    name: dict(
                        denominator=b["original_job_denominator"], categories=b["categories"]
                    )
                    for name, b in report["batches"].items()
                },
            ),
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
