# Mars Research AI OS

An open-source AI operating system for organizing Mars research, scientific data, simulations, mission knowledge, and autonomous research workflows.

## Mission

Build a reliable research platform that helps scientists, engineers, students, and mission teams explore Mars data and turn evidence into useful decisions.

## Initial Goals

- Ingest and organize public Mars mission datasets
- Search research papers and mission knowledge with citations
- Run AI-assisted analysis and simulation workflows
- Support modular research agents and tools
- Keep scientific claims traceable to their sources

## Proposed Architecture

- `apps/` — user-facing applications and dashboards
- `core/` — orchestration, models, memory, and shared services
- `agents/` — specialized research agents
- `data/` — dataset connectors and schemas
- `docs/` — architecture, research notes, and project plans
- `tests/` — automated verification

The base platform also includes a hardware-neutral, safety-oriented eight-wheel BLDC navigation module. See [docs/NAVIGATION.md](docs/NAVIGATION.md).

## Status

Early research and architecture phase. The first milestone is defining a small, testable MVP around Mars knowledge search and cited answers.

## Quick Start

The base runtime requires Python 3.11 or newer.

```bash
python -m pip install -e ".[dev]"
mars-ai-os health
python -m pytest
```

Run the optional eight-wheel Mars physics prototype:

```bash
python -m pip install -e ".[simulation]"
mars-ai-os simulate --duration 6 --gui
```

Keep the simulator open and design with live driving/camera controls:

```bash
mars-ai-os simulate --interactive
```

Interactive mode also renders the rover-to-orbiter-to-Earth DTN network with configurable delay, packet loss, contact status, queue depth, and delivered bundles. See [docs/COMMUNICATIONS.md](docs/COMMUNICATIONS.md).

See [docs/SIMULATION.md](docs/SIMULATION.md) for headless runs and model scope.

Development is pull-request based. See [CONTRIBUTING.md](CONTRIBUTING.md) before making changes.

## Contributing

Ideas and contributions are welcome. Please open an issue before starting a large change so the design can be discussed first.
