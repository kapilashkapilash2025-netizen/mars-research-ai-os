# ADR 0002: Canonical Predictive Digital Twin State

- Status: Accepted
- Date: 2026-07-19

## Context

Independent subsystem state creates divergence, weakens auditability, and makes simulation-to-hardware behavior difficult to reproduce. Future mission, navigation, HAL, communication, power, physics, science, and AI components require one traceable information model.

## Decision

Adopt the Predictive Digital Twin Engine as the canonical state gateway. Use immutable snapshots, an append-only historical twin, one live snapshot, bounded predictive snapshots, deterministic diffs, typed events, and content-addressed provenance.

The engine is information-only and never commands hardware.

## Consequences

- every subsystem must read state from a twin snapshot and submit state changes through the engine
- prediction results are isolated from canonical history until explicitly reviewed and adopted through a normal live update
- deterministic mission time, seed, configuration, assumptions, software version, and author become mandatory provenance
- initial prediction fidelity is deliberately limited and unknown inputs remain explicit
- persistence, concurrency, schema migration, and calibrated uncertainty remain future architectural work

