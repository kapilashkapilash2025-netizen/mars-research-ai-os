# Mars Research AI OS

An **Areograph Labs** open research platform. Our working mission is to make planetary intelligence
verifiable. See [docs/BRAND_IDENTITY.md](docs/BRAND_IDENTITY.md).

The Python-backed deterministic Mission Control architecture, API, scoring, safety boundaries, and
deployment model are documented in
[docs/VERIFIABLE_MISSION_TWIN.md](docs/VERIFIABLE_MISSION_TWIN.md).

The provenance-first, deterministic AI/ML dataset preparation workflow is documented in
[docs/ML_DATA_PIPELINE.md](docs/ML_DATA_PIPELINE.md).

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

## Status

Early research and architecture phase. The first milestone is defining a small, testable MVP around Mars knowledge search and cited answers.

The project is governed as a long-term scientific research platform. See [docs/PROJECT_CHARTER.md](docs/PROJECT_CHARTER.md).

The classical [Quantum-Inspired Planetary Intelligence Engine](docs/QUANTUM_INSPIRED_ENGINE.md) provides reproducible QUBO and simulated-annealing foundations for advisory mission decisions without requiring quantum hardware.

The [Predictive Digital Twin Engine](docs/PREDICTIVE_DIGITAL_TWIN.md) is the canonical information-only rover state for future subsystems. It provides immutable snapshots, deterministic diffs, replay, event publication, and bounded assumption-explicit prediction.

The [Mars Physics and Environment Engine](docs/MARS_PHYSICS_ENGINE.md) provides deterministic,
backend-neutral candidate predictions for simulation review. Its lightweight models are not calibrated
for hardware and expose no actuation interface.

The [Knowledge Provenance Model](docs/KNOWLEDGE_PROVENANCE.md) defines immutable, deterministic records
for research sources, ingested documents, and precisely located evidence.

## Quick Start

The base runtime requires Python 3.11 or newer.

```bash
python -m pip install -e ".[dev]"
mars-ai-os health
mars-ai-os physics-demo
mars-ai-os navigation-demo
python -m pytest
```

The interactive Mars Knowledge Console lives in `apps/dashboard`. It provides local evidence search,
numbered source trails, and session-only ingestion for pasted research material.

The same application includes a deterministic Mission Control Simulator MVP with selectable science
targets, route candidates, rover telemetry, safety controls, and a replayable event timeline. It is an
information-only demonstration and is not calibrated or authorized for hardware control.

Development is pull-request based. See [CONTRIBUTING.md](CONTRIBUTING.md) before making changes.

## Contributing

Ideas and contributions are welcome. Please open an issue before starting a large change so the design can be discussed first.
