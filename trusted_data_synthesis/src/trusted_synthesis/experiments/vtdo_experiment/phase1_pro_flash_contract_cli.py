from __future__ import annotations

import argparse
import json
from pathlib import Path

from trusted_synthesis.experiments.vtdo_experiment.phase1_pro_flash_agent_pilot import (
    prepare_pro_flash_pilot_contract,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Freeze the Finance DeepSeek V4-Pro/V4-Flash paired Pilot"
    )
    parser.add_argument("--source-artifacts", required=True, type=Path)
    parser.add_argument("--pro-config", required=True, type=Path)
    parser.add_argument("--flash-config", required=True, type=Path)
    parser.add_argument("--exclude-artifact", action="append", default=[], type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--seed", type=int, default=20260811)
    parser.add_argument("--task-sampling-salt", default="finance_v23_pro_flash_tasks_v1")
    parser.add_argument("--exact-target-sampling-salt", default="finance_v23_exact_target_v1")
    return parser


def main() -> None:
    args = _parser().parse_args()
    contract = prepare_pro_flash_pilot_contract(
        source_artifacts_path=args.source_artifacts,
        pro_config_path=args.pro_config,
        flash_config_path=args.flash_config,
        excluded_artifact_paths=tuple(args.exclude_artifact),
        output_path=args.output,
        run_id=args.run_id,
        random_seed=args.seed,
        task_sampling_salt=args.task_sampling_salt,
        exact_target_sampling_salt=args.exact_target_sampling_salt,
    )
    print(
        json.dumps(
            {
                "contract_id": contract.contract_id,
                "calibration_task_count": len(contract.calibration_tasks),
                "discovery_task_count": len(contract.discovery_tasks),
                "exact_target_task_count": len(contract.exact_target_task_ids),
                "models": {
                    item.arm.value: item.requested_model for item in contract.model_contracts
                },
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
