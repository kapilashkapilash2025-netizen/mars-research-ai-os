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
    simulate = subparsers.add_parser("simulate", help="Run the eight-wheel PyBullet prototype")
    simulate.add_argument("--duration", type=float, default=6.0, help="Simulation seconds")
    simulate.add_argument("--gui", action="store_true", help="Open the PyBullet GUI")
    simulate.add_argument(
        "--interactive",
        action="store_true",
        help="Run an unlimited real-time GUI with live design sliders",
    )
    simulate.add_argument(
        "--real-time", action="store_true", help="Pace a timed GUI run at wall-clock speed"
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "health":
        kernel = Kernel()
        kernel.start()
        print(json.dumps(kernel.health(), indent=2, sort_keys=True))
        kernel.stop()
        return 0
    if args.command == "simulate":
        from mars_ai_os.simulation import SimulationConfig, run_demo, run_interactive

        if args.interactive:
            run_interactive()
            return 0
        result = run_demo(
            SimulationConfig(
                duration_s=args.duration,
                gui=args.gui,
                real_time=args.real_time or args.gui,
            )
        )
        print(json.dumps(result.to_dict(), indent=2, sort_keys=True))
        return 0 if result.navigation_healthy else 1
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

