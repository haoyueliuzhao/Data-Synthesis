"""Explicitly authorized three-task wave using the existing no-retry execution core."""

import argparse
import json
from pathlib import Path
from types import SimpleNamespace

from . import v16_controller as core
from . import v17_adjudication_protocol as protocol
from . import v17_budget as budget
from . import v17_provider as provider
from . import v17_registration as registration


def runtime():
    return SimpleNamespace(
        version="v17",
        scope="three",
        count=3,
        protocol=protocol,
        budget=budget,
        provider=provider,
        checked_plan=registration.checked_plan,
        ledger_for=registration.ledger_for,
        resolve_proxy=registration.resolve_proxy,
    )


async def execute(output, plan, ledger, *, api_key, client):
    return await core.execute(
        output, plan, ledger, api_key=api_key, client=client, runtime=runtime()
    )


def deploy(output=registration.OUTPUT):
    return core.deploy(output, runtime=runtime())


def run(output=registration.OUTPUT):
    return core.run(output, runtime=runtime())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("deploy", "run"))
    parser.add_argument("--output", type=Path, default=registration.OUTPUT)
    args = parser.parse_args()
    result = deploy(args.output) if args.action == "deploy" else run(args.output)
    print(
        json.dumps({k: result.get(k) for k in ("id", "phase", "actual_returns", "usable_returns")})
    )


if __name__ == "__main__":
    main()
