# Quantum-Inspired Planetary Intelligence Engine

## Decision

The first engine uses a Quadratic Unconstrained Binary Optimization (QUBO) representation and a seeded classical simulated-annealing solver. This gives the platform a portable binary optimization contract while requiring no quantum hardware or vendor service.

The formulation follows established QUBO/Ising mappings and simulated annealing research:

- Kirkpatrick, Gelatt, and Vecchi, “Optimization by Simulated Annealing,” *Science* 220 (1983), DOI: https://doi.org/10.1126/science.220.4598.671
- Lucas, “Ising formulations of many NP problems,” *Frontiers in Physics* 2:5 (2014), DOI: https://doi.org/10.3389/fphy.2014.00005
- Glover, Kochenberger, and Du, “A Tutorial on Formulating and Using QUBO Models” (2018), https://arxiv.org/abs/1811.11538

## Scope

The foundation provides:

- named binary decision variables
- linear and quadratic objective terms
- explicit cardinality constraints
- deterministic seeded simulated annealing
- problem fingerprints and replayable run records
- advisory results with feasibility and trace metadata

Future domain adapters will translate mission planning, terrain selection, power allocation, communication contact scheduling, and predictive choices into versioned optimization problems.

## Safety boundary

The optimizer never directly commands a motor, power switch, radio, or mission actuator. Its result must pass:

1. exact domain constraint validation
2. deterministic vehicle safety rules
3. simulation scenario evaluation
4. uncertainty and provenance review
5. human authorization when mission policy requires it

An infeasible result is rejected. A feasible result is still only a recommendation. Simulated annealing is heuristic and does not prove global optimality.

## Reproducibility

Every result records the algorithm identifier, problem SHA-256 fingerprint, solver configuration, random seed, evaluation count, accepted moves, best assignment, energy, and progress history. Re-running the same problem and configuration on the same engine version must produce the same record.

## Alternatives considered

- Exhaustive search: exact but scales exponentially; useful only as a small-problem test oracle.
- Mixed-integer programming: important future baseline, but adds a solver dependency and licensing/runtime choices.
- Quantum hardware: intentionally excluded from the foundation because it would reduce portability and does not remove safety-validation requirements.
- Unseeded metaheuristics: rejected because they weaken reproducibility and auditability.

