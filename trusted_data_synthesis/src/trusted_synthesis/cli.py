from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from trusted_synthesis.core.evaluation.evaluator import QualityEvaluator
from trusted_synthesis.core.evidence.schema import EvidenceBundle
from trusted_synthesis.core.graph.builder import EvidenceGraphBuilder
from trusted_synthesis.core.task.generator import EvidenceTaskSynthesizer
from trusted_synthesis.core.trajectory.generator import DeterministicTrajectoryGenerator
from trusted_synthesis.domains.finance.adapter import FinanceArchiveAdapter
from trusted_synthesis.domains.finance.schema import FinanceArchiveConfig
from trusted_synthesis.hashing import canonical_hash


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    adapter = FinanceArchiveAdapter(FinanceArchiveConfig.from_json(args.config))
    if args.command == "inspect-finance":
        _emit(adapter.inspect(), args.output)
        return 0
    if args.command == "sample-finance":
        records = [
            item.model_dump(mode="json", exclude_none=True)
            for item in adapter.iter_evidence(limit=args.limit)
        ]
        _emit({"count": len(records), "evidence": records}, args.output)
        return 0
    if args.command == "demo-finance":
        _emit(_demo(adapter, args.limit), args.output)
        return 0
    parser.error(f"Unknown command: {args.command}")
    return 2


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="trusted-synthesis")
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ("inspect-finance", "sample-finance", "demo-finance"):
        subparser = subparsers.add_parser(command)
        subparser.add_argument("--config", required=True)
        subparser.add_argument("--output", type=Path)
        if command != "inspect-finance":
            subparser.add_argument("--limit", type=int, default=3)
    return parser


def _demo(adapter: FinanceArchiveAdapter, limit: int) -> dict[str, Any]:
    task_synthesizer = EvidenceTaskSynthesizer()
    trajectory_generator = DeterministicTrajectoryGenerator()
    graph_builder = EvidenceGraphBuilder()
    evaluator = QualityEvaluator()
    samples = []
    for evidence in adapter.iter_evidence(limit=limit):
        bundle_identity = {"purpose": "finance_demo", "evidence_id": evidence.evidence_id}
        bundle = EvidenceBundle(
            bundle_id=canonical_hash(bundle_identity, prefix="bundle:"),
            evidence=(evidence,),
            purpose="finance archive retrieval demo",
            graph_build_id=evidence.provenance.build_ids.get("kg"),
        )
        graph = graph_builder.build(bundle)
        task = task_synthesizer.fact_retrieval(bundle, evidence.evidence_id)
        trajectory = trajectory_generator.generate(task, bundle)
        assessment = evaluator.evaluate(task, bundle, trajectory)
        samples.append(
            {
                "bundle": bundle.model_dump(mode="json", exclude_none=True),
                "graph": graph.model_dump(mode="json", exclude_none=True),
                "task": task.model_dump(mode="json", exclude_none=True),
                "trajectory": trajectory.model_dump(mode="json", exclude_none=True),
                "quality": assessment.model_dump(mode="json", exclude_none=True),
            }
        )
    return {
        "pipeline": [
            "finance_adapter",
            "evidence_bundle",
            "evidence_graph",
            "task_synthesis",
            "trajectory_generation",
            "quality_evaluation",
        ],
        "sample_count": len(samples),
        "samples": samples,
    }


def _emit(payload: Any, output: Path | None) -> None:
    text = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, default=str) + "\n"
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(text, encoding="utf-8")
    else:
        print(text, end="")


if __name__ == "__main__":
    raise SystemExit(main())
