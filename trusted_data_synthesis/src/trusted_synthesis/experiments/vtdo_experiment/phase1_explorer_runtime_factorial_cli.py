from __future__ import annotations

import argparse
from pathlib import Path

from trusted_synthesis.experiments.vtdo_experiment.phase1_explorer_runtime_factorial import (
    prepare_explorer_runtime_factorial_contract,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Freeze the Finance Explorer x Runtime factorial Pilot contract"
    )
    parser.add_argument("--base-contract", type=Path, required=True)
    parser.add_argument("--finance-archive-config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()
    contract = prepare_explorer_runtime_factorial_contract(
        base_contract_path=args.base_contract,
        finance_archive_config_path=args.finance_archive_config,
        output_path=args.output,
        run_id=args.run_id,
    )
    print(contract.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
