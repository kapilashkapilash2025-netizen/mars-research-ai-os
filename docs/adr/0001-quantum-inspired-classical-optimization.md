# ADR 0001: Classical QUBO and Simulated Annealing Foundation

- Status: Accepted
- Date: 2026-07-19

## Context

Planetary mission decisions combine competing scientific value, energy, risk, terrain, timing, and communication considerations. The platform needs a portable optimization representation that can be evaluated deterministically in simulation and extended without coupling the OS to a particular solver vendor.

## Decision

Adopt QUBO as the initial binary optimization interchange model and a pure-Python, seeded simulated-annealing implementation as the first reference solver.

## Consequences

- The engine runs on ordinary classical computers and in CI.
- Every run can be replayed from its problem fingerprint, configuration, and seed.
- Domain constraints must be encoded and independently verified.
- Results are heuristic recommendations, not proofs of optimality or safety authorization.
- Exact and alternative classical solvers can be added behind the same problem contract for benchmarking.

