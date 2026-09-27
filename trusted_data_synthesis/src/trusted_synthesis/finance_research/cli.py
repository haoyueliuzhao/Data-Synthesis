"""Explicit import -> role plan -> generation seal -> separate native scoring."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
from pathlib import Path

from trusted_synthesis.core.immutable_artifacts import write_immutable_artifact_directory

from .contracts import RunConfig, digest
from .planning import build_role_plan
from .storage import (
    encode,
    execute_run,
    import_snapshot,
    load_public_snapshot,
    prepare_run,
    read_json,
    score_run,
)


def _key(env_file):
    key = os.environ.get("DEEPSEEK_API_KEY")
    if key:
        return key
    if env_file is not None:
        for line in Path(env_file).read_text().splitlines():
            name, separator, value = line.strip().partition("=")
            if separator and name.strip() == "DEEPSEEK_API_KEY":
                return value.strip().strip("\"'")
    raise ValueError("DEEPSEEK_API_KEY missing; set environment or pass --env-file")


def _local_provider(args, config):
    """Reuse the existing checkpoint/LoRA loader, never alter its frozen implementation."""
    if args.checkpoint_binding is None:
        raise ValueError("local provider requires --checkpoint-binding from bind-local")
    if os.environ.get("CUBLAS_WORKSPACE_CONFIG") != ":4096:8":
        raise ValueError("set CUBLAS_WORKSPACE_CONFIG=:4096:8 before starting local generation")
    from transformers import AutoTokenizer

    from trusted_synthesis.experiments.finance_qa_vnext_pq_student import model as existing

    from .providers import LocalTorchProvider, local_model_identity

    binding = read_json(args.checkpoint_binding)
    adapter_record = read_json(args.adapter_record) if args.adapter_record else None
    if bool(args.adapter) != bool(args.adapter_record):
        raise ValueError(
            "adapter file and its existing byte-binding record must be supplied together"
        )
    # With no checkpoint adapter this is the original base function plus zero-B LoRA;
    # preserve the explicit parameter coordinates rather than inventing virtual bytes.
    model, _ = existing.load_student(
        binding,
        config.seed,
        trainable=True,
        adapter_path=args.adapter,
        adapter_record=adapter_record,
    )
    model.eval()
    tokenizer = AutoTokenizer.from_pretrained(
        binding["directory"], local_files_only=True, trust_remote_code=False
    )
    point_id = args.point_id or "point:" + digest(
        dict(base=binding["id"], adapter=adapter_record, initial_seed=config.seed)
    )
    identity = local_model_identity(model, tokenizer, model_id=binding["id"], point_id=point_id)
    return LocalTorchProvider(model, tokenizer, identity)


def preflight(output):
    """A synthetic wiring control, not a real model or benchmark result."""
    from .datasets import adapt_finqa
    from .providers import ScriptedProvider

    output = Path(output).resolve()
    if output.exists():
        raise FileExistsError(output)
    raw = dict(
        id="SYNTHETIC/2020/page_1.pdf-1",
        filename="SYNTHETIC/2020/page_1.pdf",
        pre_text=["This is a synthetic interface control, not a benchmark question."],
        table=[["period", "value"], ["current", "8"], ["previous", "2"]],
        post_text=[],
        qa=dict(
            question="What is the increase?",
            program="subtract(8, 2)",
            exe_ans=6,
            gold_inds={"table_1": "PRIVATE_CONTROL_REFERENCE"},
        ),
    )
    bundles = adapt_finqa([raw], split="train", revision="synthetic-preflight-v1")
    manifest = import_snapshot(bundles, output / "snapshot", source={"synthetic": True})
    _, tasks, lineages = load_public_snapshot(output / "snapshot")
    plan = build_role_plan(tasks, lineages, sft_tasks=0, feedback_tasks=0, calibration_tasks=1)
    write_immutable_artifact_directory(output / "roles", {"plan.json": encode(plan)})
    turns = [
        dict(id="read", name="read_source", arguments={"source_id": "table:0"}),
        dict(
            id="calc",
            name="calculate",
            arguments={
                "expression": "current - previous",
                "variables": {
                    "current": "prev:read.content.1.1",
                    "previous": "prev:read.content.2.1",
                },
            },
        ),
        dict(
            id="final",
            name="final_answer",
            arguments={"answer": "prev:calc.result", "program": "subtract(8, 2)"},
        ),
    ]
    provider = ScriptedProvider([json.dumps(turn) for turn in turns])
    config = RunConfig(role="calibration")
    prepare_run(
        output / "snapshot",
        plan,
        output / "generation",
        role="calibration",
        config=config,
        identity=provider.identity,
    )
    seal = asyncio.run(execute_run(output / "generation", provider))
    report = score_run(output / "generation", output / "scoring")
    passed = (
        report["fixture_only"]
        and report["results"][0]["native"]["status"] == "scored"
        and report["results"][0]["native"]["native"]["execution_accuracy"] == 1.0
        and report["results"][0]["trajectory"]["actual_model_calls"] == 0
    )
    summary = dict(
        passed=passed,
        fixture_only=True,
        real_model_calls=0,
        API_calls=0,
        native_dataset_or_training_value_claimed=False,
        snapshot_id=manifest["id"],
        role_plan_id=plan["id"],
        generation_seal_id=seal["id"],
        scoring_report_id=report["id"],
        output=str(output),
    )
    write_immutable_artifact_directory(output / "summary", {"summary.json": encode(summary)})
    return summary


def _parser():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("catalog", help="Show dataset roles and upstream readiness")
    imp = commands.add_parser(
        "import", help="Offline raw dataset snapshot -> public/private adapter"
    )
    for name in ("dataset", "split", "revision"):
        imp.add_argument("--" + name, required=True)
    imp.add_argument("--input", required=True, type=Path)
    imp.add_argument("--output", required=True, type=Path)
    plan = commands.add_parser("plan", help="Freeze source-group roles before collection")
    plan.add_argument("--snapshot", required=True, type=Path)
    plan.add_argument("--output", required=True, type=Path)
    plan.add_argument("--sft-tasks", type=int, default=1000)
    plan.add_argument("--feedback-tasks", type=int, default=350)
    plan.add_argument("--calibration-tasks", type=int, default=120)
    plan.add_argument("--seed", type=int, default=20260928)
    plan.add_argument("--separate-tatqa-training", action="store_true")
    check = commands.add_parser("preflight", help="Synthetic zero-model durable end-to-end control")
    check.add_argument("--output", type=Path, required=True)
    bind = commands.add_parser(
        "bind-local", help="Bind existing local base bytes on CPU; no GPU load"
    )
    bind.add_argument("--output", type=Path, required=True)
    run = commands.add_parser("run", help="Explicitly execute registered real API/local generation")
    run.add_argument("--provider", required=True, choices=("deepseek", "local"))
    run.add_argument("--snapshot", type=Path)
    run.add_argument("--role-plan", type=Path)
    run.add_argument("--role", choices=("calibration", "sft", "feedback", "development", "test"))
    run.add_argument("--config", type=Path)
    run.add_argument("--limit", type=int)
    run.add_argument("--output", type=Path, required=True)
    run.add_argument("--resume", action="store_true")
    run.add_argument("--env-file", type=Path)
    run.add_argument("--checkpoint-binding", type=Path)
    run.add_argument("--adapter", type=Path)
    run.add_argument("--adapter-record", type=Path)
    run.add_argument("--point-id")
    score = commands.add_parser("score", help="Open references only after complete generation seal")
    score.add_argument("--run", required=True, type=Path)
    score.add_argument("--output", required=True, type=Path)
    return parser


def main(argv=None):
    parser = _parser()
    args = parser.parse_args(argv)
    if args.command == "catalog":
        from .catalog import DATASETS

        result = DATASETS
    elif args.command == "import":
        from .datasets import load_snapshot

        bundles = load_snapshot(args.dataset, args.input, args.split, args.revision)
        result = import_snapshot(
            bundles,
            args.output,
            source=dict(
                input=str(args.input.resolve()),
                sha256=hashlib.sha256(args.input.read_bytes()).hexdigest(),
                dataset=args.dataset,
                split=args.split,
                revision=args.revision,
            ),
        )
    elif args.command == "plan":
        _, tasks, lineages = load_public_snapshot(args.snapshot)
        result = build_role_plan(
            tasks,
            lineages,
            seed=args.seed,
            sft_tasks=args.sft_tasks,
            feedback_tasks=args.feedback_tasks,
            calibration_tasks=args.calibration_tasks,
            separate_tatqa_training=args.separate_tatqa_training,
        )
        write_immutable_artifact_directory(args.output, {"plan.json": encode(result)})
        result = {key: result[key] for key in ("id", "actual_counts", "requested_training_counts")}
    elif args.command == "preflight":
        result = preflight(args.output)
    elif args.command == "bind-local":
        from trusted_synthesis.experiments.finance_qa_vnext_pq_student.model import bind_checkpoint

        result = bind_checkpoint()
        write_immutable_artifact_directory(args.output, {"checkpoint.json": encode(result)})
    elif args.command == "run":
        from .providers import DeepSeekFlashProvider

        if args.resume:
            if any((args.snapshot, args.role_plan, args.role, args.config, args.limit is not None)):
                parser.error("resume uses its frozen registration; omit snapshot/role/config/limit")
            registered = read_json(args.output / "run.json")
            config = RunConfig.model_validate(registered["config"])
        else:
            if not all((args.snapshot, args.role_plan, args.role)):
                parser.error("new run requires snapshot, role-plan, role and explicit output")
            config = (
                RunConfig.model_validate(read_json(args.config))
                if args.config
                else RunConfig(role=args.role)
            )
        provider = (
            DeepSeekFlashProvider(api_key=_key(args.env_file))
            if args.provider == "deepseek"
            else _local_provider(args, config)
        )
        if not args.resume:
            prepare_run(
                args.snapshot,
                read_json(args.role_plan),
                args.output,
                role=args.role,
                config=config,
                identity=provider.identity,
                limit=args.limit,
            )
        result = asyncio.run(execute_run(args.output, provider))
    elif args.command == "score":
        result = score_run(args.run, args.output)
        result = {key: result[key] for key in ("id", "denominator", "datasets", "fixture_only")}
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 1 if isinstance(result, dict) and result.get("passed") is False else 0
