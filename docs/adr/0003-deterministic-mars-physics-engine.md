# ADR 0003: Deterministic backend-neutral Mars physics engine

- Status: proposed
- Date: 2026-07-19
- Issue: https://github.com/kapilashkapilash2025-netizen/mars-research-ai-os/issues/8

## Context

OS development needs reproducible physical/environment predictions before real hardware exists, but
the project must not create another canonical rover state or imply unearned model fidelity.

## Decision

Create a pure-Python, dependency-free `mars_physics` package whose immutable SI-unit input and result
contract is independent of a simulator backend. It reads canonical twin snapshots through an adapter,
returns candidate snapshots, records provenance and fingerprints, and never mutates live/history state.
Reference equations are bounded engineering approximations and all stochastic observations are seeded.

## Consequences

Tests and OS subsystem reviews gain fast reproducible scenarios without PyBullet/Gazebo installation.
The simplified models are unsuitable for hardware qualification and require explicit calibration.
Future high-fidelity backends can replace computations behind the stable boundary. Explicit candidate
acceptance and safety authority remain outside physics. Optimization receives advisory costs only.
