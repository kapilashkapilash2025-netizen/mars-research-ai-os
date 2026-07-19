# Deterministic Mars Physics and Environment Engine

## Status and safety boundary

This package is an information-only scientific simulation foundation. It predicts candidate state;
it has no motor, CAN, ROS, networking, or hardware command interface. Results are engineering
approximations for software review, not validated flight, mobility, or terramechanics evidence.

The canonical Predictive Digital Twin remains the sole rover state authority. `PhysicsTwinAdapter`
reads a `TwinSnapshot`, returns a new candidate snapshot, and publishes
`PhysicsPredictionCompleted`. It never calls `DigitalTwinEngine.update_state`. A future reviewed
safety/control workflow must explicitly accept a candidate.

## Package boundaries

- `models.py`: immutable validated SI-unit environment, terrain, vehicle, input, and result records.
- `engine.py`: deterministic slope, resistance, slip, sinkage, energy, thermal, dust, and sensor
  approximations behind `PhysicsEngine.step`.
- `adapters.py`: canonical twin mapping, candidate creation, provenance, and event publication.
- `scenarios.py`: ten stable fixtures spanning nominal, hazardous, and unsupported conditions.
- `demo.py`: concise deterministic CLI output.

The orchestration boundary is backend-neutral. A future PyBullet, Gazebo, laboratory, or
high-fidelity model can implement the same input/result contract after independent validation.

## Public units and equations

Fields carry unit suffixes: `_m`, `_mps`, `_mps2`, `_n`, `_w`, `_wh`, `_c`, `_s`, `_kg`, `_kpa`,
and `_deg`. Ratios and quality values are dimensionless and bounded to `[0, 1]`.

The reference calculation uses:

- normal force `N = m g cos(theta)`;
- slope force `F_s = m g sin(theta)`;
- rolling force `F_r = C_rr N`, adjusted by bounded roughness and rock factors;
- traction limit `F_t = mu N`;
- positive drivetrain energy `max(0, F_demand) distance / efficiency`;
- solar input `irradiance area efficiency dust_factor time`;
- first-order lumped thermal relaxation toward `ambient + heat * thermal_resistance`.

Slope energy therefore increases uphill. Downhill results flag braking/regeneration review instead
of claiming captured energy. Slip combines wheel/ground kinematics and traction excess, then clamps
to `[0, 1]`. Sinkage is a capped load/cohesion heuristic; it is explicitly not Bekker/Wong or a
calibrated regolith model.

## Truth, observations, and determinism

`PhysicsState` is simulation truth. `SensorObservation` is derived separately using a local seeded
pseudorandom generator for IMU, encoder, lidar, temperature, and battery-voltage noise. Camera and
lidar quality metadata degrade with dust. Identical state, intent, environment, terrain, vehicle,
configuration, timestep, and seed produce identical records and SHA-256 fingerprints. Changing only
the seed changes observations, not truth.

## Safety invariants

- Time advances by a positive configured timestep; no time reversal is accepted.
- Slip, dust, confidence, solar, sensing, and communication quality are bounded.
- Battery energy is clamped to capacity. Accounting reports actual change plus non-negative
  curtailed or unmet energy, preserving the simplified input/output balance at battery bounds.
- Thermal results remain finite; sinkage is capped.
- Unsafe continuing motion during known communication loss is rejected unless a future safety layer
  supplies an explicit safe motion state.
- Warnings request human/safety-layer review, derating, braking assessment, or safe state. They do not
  execute those actions.

## Optimization boundary

The result exposes an advisory cost vector: energy, traversal risk, thermal risk, slip risk, and
duration. The classical quantum-inspired optimizer may consume these values later, but it cannot
bypass physics constraints, safety review, or candidate acceptance.

## Assumptions, calibration gaps, and extension points

Nominal gravity defaults to configurable `3.721 m/s^2`. Wheel load is evenly distributed. Dust
attenuation, rock/roughness penalties, motor losses, solar geometry, thermal transfer, sensor noise,
and regolith response are simplified. Missing twin battery energy is rejected instead of fabricated;
other reference adapter defaults are visible in code and provenance assumptions.

Calibration requires traceable Mars environmental datasets, rover geometry and mass properties,
wheel/regolith tests, motor maps, thermal-vacuum results, solar orientation and dust deposition data,
and sensor characterization. Model coefficients should become versioned configuration datasets.
Backend adapters, richer uncertainty distributions, multi-step horizons, calibrated braking, and
validated terramechanics are future work.

## Reproduction

```bash
mars-ai-os physics-demo
python -m pytest tests/test_mars_physics.py
```

The ten scenario IDs are `flat-compact`, `loose-slip`, `uphill`, `downhill`, `rocky`, `dusty`,
`low-temperature`, `high-motor-load-thermal`, `immobilization-risk`, and `invalid-unsupported`.
