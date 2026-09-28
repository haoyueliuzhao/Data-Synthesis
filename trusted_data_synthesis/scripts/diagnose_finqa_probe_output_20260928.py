"""One registered offline diagnostic of the sealed 1320-slot legacy Probe inventory.

Run with PYTHONPATH pointing to the frozen registration worktree's src. This
script never calls a model, qualify_episode, a material builder, or training.
Only public turn.raw_text is inspected for prose; private reasoning fields are
not inspected, sampled, copied or used as diagnostic evidence.
"""

from __future__ import annotations

import argparse
import csv
import fcntl
import hashlib
import io
import json
import subprocess
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from trusted_synthesis.core.immutable_artifacts import write_immutable_artifact_directory
from trusted_synthesis.finance_research import contracts, native_metrics, profiles
from trusted_synthesis.finance_research.contracts import PrivateReference, TaskBundle, digest
from trusted_synthesis.finance_research.planning import task_key, verify_role_plan
from trusted_synthesis.finance_research.storage import load_public_snapshot

CACHE = Path(
    "/data1/zhuxinrui/projects/Data-Synthesis/trusted_data_synthesis/artifacts/finance_research_20260928"
)
LEGACY = CACHE / "finqa_conditional_probe_inventory_01"
OUTPUT = CACHE / "structured_probe_followup_01/legacy_output_diagnostic_01"
PROFILE = "finqa_program_v2"
SAMPLE_LIMIT = 12
SAMPLE_TURNS = 2
SAMPLE_CHARACTERS = 200
SOURCE_RECORDS = ("protocol.json", "generation_seal/record.json", "inventory_complete/record.json")


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False).encode()


def read(path):
    return json.loads(Path(path).read_bytes())


def identified(prefix, body):
    return {**body, "id": prefix + digest(body)}


def checked(value, key="id", prefix=""):
    if value[key] != prefix + digest({k: v for k, v in value.items() if k != key}):
        raise ValueError(f"content identity mismatch: {key}")
    return value


def publish(directory, payloads):
    write_immutable_artifact_directory(directory, payloads)


def git_head(directory):
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=directory, text=True).strip()


def source_binding():
    modules = (contracts, native_metrics, profiles)
    paths = [Path(module.__file__).resolve() for module in modules]
    paths += [
        native_metrics.VENDOR / "PROVENANCE.json",
        native_metrics.VENDOR / "finqa_evaluate.py",
    ]
    native_metrics.metric_provenance()
    source_root = paths[0].parents[4]
    script = Path(__file__).resolve()
    return {
        "frozen_scorer_checkout": str(source_root),
        "frozen_scorer_commit": git_head(source_root),
        "sources": {str(path): sha(path.read_bytes()) for path in paths},
        "script": str(script),
        "script_sha256": sha(script.read_bytes()),
        "script_checkout_commit_at_registration": git_head(script.parents[2]),
        "script_source_bound_independently_of_uncommitted_status": True,
        "profile": profiles.profile_definition(PROFILE),
        "profile_sha256": digest(profiles.profile_definition(PROFILE)),
    }


def legacy_metadata(root):
    root = Path(root).resolve()
    plan = checked(read(root / "protocol.json"))
    seal = checked(read(root / "generation_seal/record.json"))
    frozen = checked(
        read(root / "inventory_complete/record.json"),
        "frozen_inventory_id",
        "finqa_frozen_probe_support:",
    )
    inventory = plan["inventory"]
    checked(inventory, "inventory_id", "finqa_probe_inventory:")
    if not (
        plan["active_slot_denominator"] == 1320
        and len(plan["task_ids"]) == 165
        and seal["denominator"] == 1320
        and seal["complete"] is True
        and seal["all_API_requests_settled"] is True
        and seal["protocol_id"] == plan["id"]
        and frozen["slot_denominator"] == 1320
        and frozen["inventory_id"] == inventory["inventory_id"]
    ):
        raise ValueError("the complete unchanged legacy 165x8 inventory is required")
    ordered = sorted(
        inventory["slots"],
        key=lambda slot: (
            plan["task_ids"].index(slot["task_id"]),
            slot["slot_index"],
        ),
    )
    expected = [
        (task, index, "train" if index < 6 else "sealed_diagnostic")
        for task in plan["task_ids"]
        for index in range(8)
    ]
    if [(s["task_id"], s["slot_index"], s["purpose"]) for s in ordered] != expected:
        raise ValueError("original task/slot train/sealed roster differs")
    generated = {row["slot"]["slot_id"]: row for row in seal["slots"]}
    qualified = {row["slot_id"]: row for row in frozen["slot_results"]}
    if len(generated) != len(qualified) or set(generated) != {s["slot_id"] for s in ordered}:
        raise ValueError("sealed generation/old qualification membership differs")
    bindings = []
    for slot in ordered:
        generation, old = generated[slot["slot_id"]], qualified[slot["slot_id"]]
        if (
            generation["slot"] != slot
            or generation["status"] != "COMPLETE"
            or (
                old["episode_sha256"] != generation["episode_sha256"]
                or old["decision"]["episode_sha256"] != generation["episode_sha256"]
                or old["task_id"] != slot["task_id"]
                or old["purpose"] != slot["purpose"]
            )
        ):
            raise ValueError("old slot/episode/decision bindings differ")
        episode_path = Path(generation["episode_path"]).resolve()
        if not episode_path.is_relative_to(root / "slots"):
            raise ValueError("original episode path is outside the legacy inventory")
        # No native record exists in the frozen inventory schema for this study.
        # If a future caller has such records, registration must explicitly bind
        # their provenance instead of silently overwriting/recomputing them.
        if "native" in old or "native_score" in old:
            raise ValueError("existing native scores need an explicit reuse binding")
        bindings.append(
            {
                **slot,
                "episode_path": str(episode_path),
                "episode_file_sha256": generation["episode_file_sha256"],
                "episode_sha256": generation["episode_sha256"],
                "old_decision": old["decision"],
                "old_slot_result_id": old["slot_result_id"],
            }
        )
    if any(
        (root / location).exists() for location in ("scoring", "native_scores", "native_metrics")
    ):
        raise ValueError(
            "existing native-score location must be reviewed for reuse before registering"
        )
    return plan, seal, frozen, bindings


def register(root=LEGACY, output=OUTPUT):
    root, output = Path(root).resolve(), Path(output).resolve()
    if (output / "protocol.json").exists():
        return verify_registration(output)
    if output.exists():
        raise ValueError("new diagnostic registration directory must not already exist")
    plan, seal, frozen, slots = legacy_metadata(root)
    manifest = read(Path(plan["snapshot"]) / "manifest.json")
    body = {
        "schema": "finqa_legacy_output_diagnostic_protocol.v1",
        "registered_at": datetime.now(timezone.utc).isoformat(),
        "legacy_root": str(root),
        "legacy_protocol_id": plan["id"],
        "legacy_inventory_id": plan["inventory"]["inventory_id"],
        "legacy_generation_seal_id": seal["id"],
        "legacy_frozen_inventory_id": frozen["frozen_inventory_id"],
        "legacy_execution_source_commit": plan["source_commit"],
        "source_records": {name: sha((root / name).read_bytes()) for name in SOURCE_RECORDS},
        "snapshot": plan["snapshot"],
        "snapshot_id": plan["snapshot_id"],
        "private_reference_member_sha256": manifest["files"]["private.references.jsonl"]["sha256"],
        "task_ids": plan["task_ids"],
        "slots": slots,
        "denominator": 1320,
        "purpose_denominators": {"train": 990, "sealed_diagnostic": 330},
        "summary_purpose_labels": {"train": "train", "sealed": "sealed_diagnostic"},
        "order": "original task_ids order, then slot_index 0..7; not launch or success order",
        "native_score_policy": (
            "one offline score_native call per original slot, frozen finqa_program_v2"
        ),
        "preexisting_native_scores": 0,
        "preexisting_native_check": [
            "frozen slot result schema",
            "scoring",
            "native_scores",
            "native_metrics",
        ],
        "resume": "reuse content-bound diagnostic slot records; never rescore a persisted slot",
        "exception_policy": "unknown/null retained in registered denominator; never financial zero",
        "program_structure": "frozen native_metrics._program_tokens container/operator/arity test",
        "program_execution": (
            "scored=>true; invalid structure/missing/official non-executable=>false; "
            "unresolved=>unknown"
        ),
        "cross_table_axes": [
            "public_body_status",
            "program_structure",
            "program_executable",
            "execution_accuracy",
            "old_qualification_reason",
        ],
        "public_body": (
            "any original turn.raw_text.strip() nonempty; never inspect private reasoning"
        ),
        "sample_policy": {
            "first_nonempty_slots": SAMPLE_LIMIT,
            "public_turns_per_slot": SAMPLE_TURNS,
            "characters_per_turn": SAMPLE_CHARACTERS,
            "selection_order": "registered task/slot order",
            "fields": ["turn.raw_text"],
            "representative_population_claimed": False,
        },
        "bindings": source_binding(),
        "model_calls": 0,
        "API_calls": 0,
        "GPU_calls": 0,
        "qualification_reexecution": False,
        "old_labels_changed": False,
        "old_public_content_removed": False,
        "sealed_slots_enter_training": False,
        "material_admission": False,
        "training_authorized": False,
    }
    protocol = identified("finqa_legacy_output_diagnostic:", body)
    publish(output, {"protocol.json": encoded(protocol)})
    return protocol


def verify_registration(output):
    protocol = checked(
        read(Path(output) / "protocol.json"), prefix="finqa_legacy_output_diagnostic:"
    )
    binding = protocol["bindings"]
    if (
        str(Path(__file__).resolve()) != binding["script"]
        or sha(Path(__file__).read_bytes()) != binding["script_sha256"]
    ):
        raise ValueError("registered diagnostic script changed; do not silently rerun")
    for path, expected in binding["sources"].items():
        if sha(Path(path).read_bytes()) != expected:
            raise ValueError("registered frozen scorer/profile source bytes changed")
    if str(Path(native_metrics.__file__).resolve()) not in binding["sources"] or (
        digest(profiles.profile_definition(PROFILE)) != binding["profile_sha256"]
    ):
        raise ValueError("use the registered frozen PYTHONPATH, not the new harness checkout")
    root = Path(protocol["legacy_root"])
    if any(
        sha((root / path).read_bytes()) != expected
        for path, expected in protocol["source_records"].items()
    ):
        raise ValueError("legacy inventory/seal/labels changed after diagnostic registration")
    return protocol


def reference_bundles(protocol):
    plan = read(Path(protocol["legacy_root"]) / "protocol.json")
    manifest, tasks, lineages = load_public_snapshot(protocol["snapshot"])
    if manifest["id"] != protocol["snapshot_id"]:
        raise ValueError("registered original QA snapshot changed")
    verify_role_plan(plan["role_plan"], tasks, lineages)
    wanted = set(protocol["task_ids"])
    positions = [index for index, task in enumerate(tasks) if task.task_id in wanted]
    if len(positions) != 165 or any(
        plan["role_plan"]["assignments"][task_key(tasks[i])] != "sft" for i in positions
    ):
        raise ValueError("diagnostic references must be the same 165 SFT tasks only")
    raw = (Path(protocol["snapshot"]) / "private.references.jsonl").read_bytes()
    if sha(raw) != protocol["private_reference_member_sha256"]:
        raise ValueError("original private-reference member changed")
    lines = [line for line in raw.splitlines() if line.strip()]
    if len(lines) != len(tasks):
        raise ValueError("original reference/public row counts differ")
    return {
        tasks[index].task_id: TaskBundle(
            public=tasks[index],
            lineage=lineages[index],
            reference=PrivateReference.model_validate_json(lines[index]),
        )
        for index in positions
    }


def public_projection(raw_episode):
    """Read only public content and final submission; no provider/private reasoning traversal."""
    return {
        "task_id": raw_episode["task_id"],
        "dataset": raw_episode["dataset"],
        "config": raw_episode["config"],
        "public_contents": [turn["raw_text"] for turn in raw_episode["turns"]],
        "final_answer": raw_episode["final_answer"],
        "final_program": raw_episode["final_program"],
        "final_scale": raw_episode["final_scale"],
        "stop_reason": raw_episode["stop_reason"],
        "all_provider_calls_settled": raw_episode["all_provider_calls_settled"],
    }


def bounded_sample(contents):
    return [
        {
            "turn_index": index,
            "content_prefix": content[:SAMPLE_CHARACTERS],
            "content_characters": len(content),
            "content_sha256": sha(content.encode()),
            "display_prefix_only_original_not_changed": True,
        }
        for index, content in enumerate(contents)
        if content.strip()
    ][:SAMPLE_TURNS]


def score_projection(bundle, projected):
    program = projected["final_program"]
    scorer = native_metrics._load_finqa_scorer()
    tokens = native_metrics._program_tokens(program, scorer)
    structure = "missing" if program is None else ("valid" if tokens is not None else "invalid")
    result = native_metrics.score_native(
        bundle,
        projected["final_answer"],
        scale=projected["final_scale"],
        program=program,
        submission_profile=PROFILE,
        stop_reason=projected["stop_reason"],
        all_provider_calls_settled=projected["all_provider_calls_settled"],
    )
    if tokens is None:
        executable = False
    elif result["status"] == "scored":
        executable = True
    elif result.get("reason") == "predicted FinQA program is not executable":
        executable = False
    else:
        executable = None
    return dict(
        program_structure=structure,
        program_executable=executable,
        native_score=result,
        native_status=result["status"],
        execution_accuracy=result["native"]["execution_accuracy"],
        program_accuracy=result["native"]["program_accuracy"],
        native_score_recorded_once=True,
    )


def _label(value):
    return "unknown" if value is None else str(value).lower()


def summarize(rows):
    result = {}
    for purpose in ("all", "train", "sealed"):
        original_purpose = "sealed_diagnostic" if purpose == "sealed" else purpose
        chosen = [row for row in rows if purpose == "all" or row["purpose"] == original_purpose]
        cross = Counter(
            (
                row["public_body_status"],
                row["program_structure"],
                _label(row["program_executable"]),
                _label(row["execution_accuracy"]),
                row["old_qualification_reason"],
            )
            for row in chosen
        )
        by_body = []
        for body in ("empty", "nonempty", "unknown"):
            part = [row for row in chosen if row["public_body_status"] == body]
            by_body.append(
                dict(
                    public_body_status=body,
                    slots=len(part),
                    structurally_valid=sum(row["program_structure"] == "valid" for row in part),
                    executable=sum(row["program_executable"] is True for row in part),
                    execution_correct=sum(row["execution_accuracy"] == 1 for row in part),
                    execution_unknown=sum(row["execution_accuracy"] is None for row in part),
                    program_correct=sum(row["program_accuracy"] == 1 for row in part),
                )
            )
        scored = [
            row["execution_accuracy"] for row in chosen if row["execution_accuracy"] is not None
        ]
        result[purpose] = dict(
            denominator=len(chosen),
            body_breakdown=by_body,
            native_execution_correct=sum(value == 1 for value in scored),
            native_execution_unknown=len(chosen) - len(scored),
            complete_denominator_execution_mean=(sum(scored) / len(chosen))
            if chosen and len(scored) == len(chosen)
            else None,
            old_verdict_counts=dict(Counter(row["old_qualification_verdict"] for row in chosen)),
            old_reason_counts=dict(Counter(row["old_qualification_reason"] for row in chosen)),
            program_structure_counts=dict(Counter(row["program_structure"] for row in chosen)),
            native_status_counts=dict(Counter(row["native_status"] for row in chosen)),
            cross_table=[
                dict(
                    public_body_status=key[0],
                    program_structure=key[1],
                    program_executable=key[2],
                    execution_accuracy=key[3],
                    old_qualification_reason=key[4],
                    slots=count,
                )
                for key, count in sorted(cross.items())
            ],
        )
    return result


def markdown(summary):
    def table_row(values):
        return "| " + " | ".join(str(value) for value in values) + " |"

    lines = [
        "# 旧 FinQA Probe 库存：公开正文／程序／原生指标非准入诊断",
        "",
        "本诊断保持原 1320 槽、旧资格与 train/sealed 用途不变；没有重采、重判资格或训练。",
        "官方 execution 来自实际预测程序的固定 FinQA v2 评分，不以 Final 数字正确代替。",
        "此处 unknown 是诊断或评分不能确定；不改写为模型零分。",
        "",
        "| 用途 | 固定分母 | 原生execution正确 | 原生未知 | 全分母execution均值 |",
        "|---|---:|---:|---:|---:|",
    ]
    for purpose, group in summary["groups"].items():
        mean = group["complete_denominator_execution_mean"]
        lines.append(
            table_row(
                [
                    purpose,
                    group["denominator"],
                    group["native_execution_correct"],
                    group["native_execution_unknown"],
                    mean if mean is not None else "unknown",
                ]
            )
        )
    lines += [
        "",
        "## 公开正文交叉诊断",
        "",
        "| 用途 | 正文 | 槽数 | 程序结构合法 | 程序可执行 | "
        "execution正确 | execution未知 | program正确 |",
        "|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for purpose, group in summary["groups"].items():
        for row in group["body_breakdown"]:
            lines.append(
                table_row(
                    [
                        purpose,
                        row["public_body_status"],
                        row["slots"],
                        row["structurally_valid"],
                        row["executable"],
                        row["execution_correct"],
                        row["execution_unknown"],
                        row["program_correct"],
                    ]
                )
            )
    lines += [
        "",
        "完整五维交叉表见 summary.json；逐槽结果见 slots.tsv 与 slots.jsonl。",
        "原生正确不证明公开说明正确，也不升级任何旧 unknown/invalid 为 CompletePass。",
        "正文非空是存在性检测，不是其金融断言的语义裁定。程序结构合法也不等于可执行或答案正确。",
        "",
        "## 事前固定的有界公开正文样本",
        "",
        "按原 task/slot 顺序取前12个非空正文槽，"
        "每槽只展示最早2条非空 public content 的前200个字符。",
        "只作解释，不能代表全部非空正文；没有读取或展示 private reasoning，没有删除原正文。",
    ]
    for sample in summary["samples"]:
        lines += [
            "",
            f"### {sample['task_id']} / slot {sample['slot_index']} / {sample['purpose']}",
            "",
        ]
        for item in sample["public_contents"]:
            lines += [
                f"turn {item['turn_index']}（原文 {item['content_characters']} 字符）：",
                "",
                "```json",
                json.dumps(item["content_prefix"], ensure_ascii=False),
                "```",
                "",
            ]
    lines += [
        "## 解释边界",
        "",
        "每题有8个相关生成槽，这不是1320道独立金融题。train与sealed分别报告；sealed不转入训练。",
        "旧资格首因仍是原有限认证器的首阻断，不等于已经逐条审阅所有公开声明。",
        "未扫描旧R/G/H结果、未执行qualification或Mapper、未删除内容、未改原始记录。",
        "模型/API/GPU调用均为0。任何新生成协议及训练准入均需独立登记。",
        "",
    ]
    return "\n".join(lines).encode()


def run(output=OUTPUT):
    output = Path(output).resolve()
    protocol = verify_registration(output)
    with (output / "diagnostic.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if (output / "complete/record.json").exists():
            return checked(
                read(output / "complete/record.json"),
                prefix="finqa_legacy_output_diagnostic_complete:",
            )
        bundles, rows, samples = reference_bundles(protocol), [], []
        for ordinal, slot in enumerate(protocol["slots"]):
            cache = output / "slot_records" / f"{ordinal:04d}"
            if (cache / "record.json").exists():
                row = checked(read(cache / "record.json"), prefix="finqa_legacy_output_slot:")
                if row["protocol_id"] != protocol["id"] or row["slot_id"] != slot["slot_id"]:
                    raise ValueError("diagnostic cache is bound to another slot/protocol")
            else:
                row = dict(
                    protocol_id=protocol["id"],
                    ordinal=ordinal,
                    task_id=slot["task_id"],
                    slot_index=slot["slot_index"],
                    purpose=slot["purpose"],
                    slot_id=slot["slot_id"],
                    episode_file_sha256=slot["episode_file_sha256"],
                    episode_sha256=slot["episode_sha256"],
                    old_qualification_verdict=slot["old_decision"]["verdict"],
                    old_qualification_reason=slot["old_decision"]["reason"],
                    old_qualification_evidence_sha256=slot["old_decision"]["evidence_sha256"],
                    public_body_status="unknown",
                    nonempty_public_turns=None,
                    program_structure="unknown",
                    program_executable=None,
                    native_status="unknown",
                    execution_accuracy=None,
                    program_accuracy=None,
                    diagnostic_error=None,
                    native_score_recorded_once=False,
                    public_sample=None,
                    private_reasoning_inspected=False,
                )
                try:
                    raw = Path(slot["episode_path"]).read_bytes()
                    if sha(raw) != slot["episode_file_sha256"]:
                        raise ValueError("sealed original episode bytes changed")
                    projected = public_projection(json.loads(raw))
                    if (
                        projected["task_id"] != slot["task_id"]
                        or projected["dataset"] != "finqa"
                        or projected["config"]["role"] != "sft"
                        or projected["config"]["submission_profile"] != PROFILE
                    ):
                        raise ValueError("episode task/role/profile differs from registered slot")
                    contents = projected["public_contents"]
                    nonempty = sum(bool(text.strip()) for text in contents)
                    row.update(
                        public_body_status="nonempty" if nonempty else "empty",
                        nonempty_public_turns=nonempty,
                        public_turn_count=len(contents),
                    )
                    if nonempty and len(samples) < SAMPLE_LIMIT:
                        row["public_sample"] = dict(
                            task_id=slot["task_id"],
                            slot_index=slot["slot_index"],
                            purpose=slot["purpose"],
                            slot_id=slot["slot_id"],
                            public_contents=bounded_sample(contents),
                        )
                    row.update(score_projection(bundles[slot["task_id"]], projected))
                except Exception as error:
                    row["diagnostic_error"] = f"{type(error).__name__}: {error}"[:1000]
                    row.update(
                        native_status="diagnostic_unknown",
                        execution_accuracy=None,
                        program_accuracy=None,
                    )
                row = identified("finqa_legacy_output_slot:", row)
                publish(cache, {"record.json": encoded(row)})
            rows.append(row)
            if row.get("public_sample") is not None:
                samples.append(row["public_sample"])
            if (ordinal + 1) % 100 == 0:
                print(json.dumps({"diagnosed_slots": ordinal + 1, "denominator": 1320}), flush=True)
        if len(rows) != 1320 or len(samples) > SAMPLE_LIMIT:
            raise ValueError("fixed diagnostic denominator/sample bound violated")
        summary = identified(
            "finqa_legacy_output_summary:",
            dict(
                schema="finqa_legacy_output_diagnostic_summary.v1",
                complete=True,
                protocol_id=protocol["id"],
                legacy_inventory_id=protocol["legacy_inventory_id"],
                legacy_frozen_inventory_id=protocol["legacy_frozen_inventory_id"],
                denominator=1320,
                groups=summarize(rows),
                samples=samples,
                recorded_offline_native_scores=sum(
                    row["native_score_recorded_once"] for row in rows
                ),
                diagnostic_exceptions=sum(row["diagnostic_error"] is not None for row in rows),
                slot_result_ids=[row["id"] for row in rows],
                original_labels_changed=False,
                qualifications_reexecuted=0,
                public_content_deleted=False,
                private_reasoning_inspected=False,
                sealed_slots_enter_training=False,
                material_admission=False,
                training_authorized=False,
                model_calls=0,
                API_calls=0,
                GPU_calls=0,
            ),
        )
        fields = [
            "ordinal",
            "task_id",
            "slot_index",
            "purpose",
            "slot_id",
            "public_body_status",
            "nonempty_public_turns",
            "program_structure",
            "program_executable",
            "execution_accuracy",
            "program_accuracy",
            "native_status",
            "old_qualification_verdict",
            "old_qualification_reason",
            "diagnostic_error",
            "episode_sha256",
        ]
        table = io.StringIO()
        writer = csv.DictWriter(
            table, fieldnames=fields, delimiter="\t", lineterminator="\n", extrasaction="ignore"
        )
        writer.writeheader()
        writer.writerows(rows)
        payloads = {
            "summary.json": encoded(summary),
            "report.md": markdown(summary),
            "slots.tsv": table.getvalue().encode(),
            "slots.jsonl": b"".join(
                json.dumps(row, ensure_ascii=False, sort_keys=True, allow_nan=False).encode()
                + b"\n"
                for row in rows
            ),
        }
        if (output / "results").exists():
            if any(
                (output / "results" / name).read_bytes() != raw for name, raw in payloads.items()
            ):
                raise ValueError("immutable diagnostic result changed; original results retained")
        else:
            publish(output / "results", payloads)
        complete = identified(
            "finqa_legacy_output_diagnostic_complete:",
            dict(
                complete=True,
                protocol_id=protocol["id"],
                summary_id=summary["id"],
                summary_sha256=sha(payloads["summary.json"]),
                denominator=1320,
                results_manifest={
                    name: dict(sha256=sha(raw), bytes=len(raw)) for name, raw in payloads.items()
                },
                diagnostic_exceptions=summary["diagnostic_exceptions"],
                old_labels_changed=False,
                qualifications_reexecuted=0,
                model_calls=0,
                API_calls=0,
                GPU_calls=0,
            ),
        )
        publish(output / "complete", {"record.json": encoded(complete)})
        return complete


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("register", "run"))
    parser.add_argument("--legacy-root", type=Path, default=LEGACY)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    value = (
        register(args.legacy_root, args.output) if args.action == "register" else run(args.output)
    )
    print(
        json.dumps({key: value[key] for key in ("id", "complete", "denominator") if key in value}),
        flush=True,
    )


if __name__ == "__main__":
    main()
