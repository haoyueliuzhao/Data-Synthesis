"""No repeat/resume/train mode: freeze, collect once, assess, finalize or read packets."""

import argparse
import json
import subprocess
from pathlib import Path

from .plan import OUTPUT, read_json, require


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("prepare", "collect", "assess", "finalize", "show"))
    parser.add_argument("--reviews", type=Path)
    parser.add_argument("--first", type=int, default=1)
    parser.add_argument("--last", type=int, default=2)
    args = parser.parse_args()
    root = Path(subprocess.check_output(["git", "rev-parse", "--show-toplevel"], text=True).strip())
    if args.mode == "prepare":
        from .collect import prepare

        result = prepare(root)
    elif args.mode == "collect":
        from .collect import collect

        result = collect(root)
    elif args.mode == "assess":
        from .assess import assess

        result = assess(root)
    elif args.mode == "finalize":
        from .assess import finalize

        require(args.reviews is not None, "cli.reviews_required")
        result = finalize(root, args.reviews)
    else:
        paths = sorted((root / OUTPUT / "assessment/packets").glob("*.json"))
        require(1 <= args.first <= args.last <= len(paths), "cli.actual_packet_interval")
        for ordinal in range(args.first, args.last + 1):
            packet = read_json(paths[ordinal - 1])
            print(
                json.dumps(
                    {
                        "ordinal": ordinal,
                        **{
                            k: v
                            for k, v in packet.items()
                            if k not in {"public_document", "public_quantity_context"}
                        },
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                flush=True,
            )
        return
    print(result["id"], flush=True)


if __name__ == "__main__":
    main()
