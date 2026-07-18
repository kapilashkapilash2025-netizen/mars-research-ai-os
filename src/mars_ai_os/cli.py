"""Command-line entry point for the base runtime."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence

from mars_ai_os.kernel import Kernel


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="mars-ai-os")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("health", help="Print a base-kernel health report")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "health":
        kernel = Kernel()
        kernel.start()
        print(json.dumps(kernel.health(), indent=2, sort_keys=True))
        kernel.stop()
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

