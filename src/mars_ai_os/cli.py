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
    subparsers.add_parser(
        "optimize-demo", help="Run a deterministic quantum-inspired mission selection demo"
    )
    subparsers.add_parser(
        "twin-demo", help="Demonstrate snapshots, diffs, prediction, events, and replay"
    )
    knowledge_parser = subparsers.add_parser(
        "knowledge-demo", help="Ask a cited question against a bundled sample Mars corpus"
    )
    knowledge_parser.add_argument(
        "--question",
        default="What is Mars atmosphere made of?",
        help="Question to ask the knowledge engine",
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
    if args.command == "optimize-demo":
        from mars_ai_os.intelligence import AnnealingConfig, SimulatedAnnealingOptimizer
        from mars_ai_os.intelligence.planetary import (
            MissionCandidate,
            build_mission_selection_problem,
        )

        problem = build_mission_selection_problem(
            (
                MissionCandidate("inspect_ridge", 9.0, 90.0, 1.5, 50.0),
                MissionCandidate("sample_crater", 12.0, 180.0, 3.0, 80.0),
                MissionCandidate("relay_wait", 3.0, 20.0, 0.2, 5.0),
                MissionCandidate("thermal_survey", 7.0, 60.0, 1.0, 30.0),
            ),
            maximum_selected=2,
        )
        result = SimulatedAnnealingOptimizer().solve(problem, AnnealingConfig(seed=13))
        output = result.to_dict()
        history = output.pop("best_energy_history")
        output["history_points"] = len(history)
        print(json.dumps(output, indent=2, sort_keys=True))
        return 0
    if args.command == "twin-demo":
        from mars_ai_os.digital_twin.demo import run_twin_demo

        print(json.dumps(run_twin_demo(), indent=2, sort_keys=True))
        return 0
    if args.command == "knowledge-demo":
        from mars_ai_os.knowledge.demo import run_knowledge_demo

        print(json.dumps(run_knowledge_demo(args.question), indent=2, sort_keys=True))
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

