"""Named deterministic reference scenarios for regression and review."""

from __future__ import annotations

from dataclasses import dataclass, replace

from mars_ai_os.mars_physics.models import MarsEnvironment, PhysicsState, SimulationIntent, Terrain


@dataclass(frozen=True, slots=True)
class PhysicsScenario:
    scenario_id: str
    state: PhysicsState
    intent: SimulationIntent
    environment: MarsEnvironment
    terrain: Terrain


def reference_scenarios() -> tuple[PhysicsScenario, ...]:
    base_state = PhysicsState(0, (0, 0, 0), 0, 0, 4000, 20, 25, 20, 35, True)
    base_intent = SimulationIntent(0.5, 0.05)
    env = MarsEnvironment()
    terrain = Terrain()
    return (
        PhysicsScenario("flat-compact", base_state, base_intent, env, terrain),
        PhysicsScenario(
            "loose-slip",
            base_state,
            base_intent,
            env,
            replace(
                terrain, traction_coefficient=0.08, cohesion_kpa=0.2, sinkage_factor_m_kpa=0.03
            ),
        ),
        PhysicsScenario("uphill", base_state, base_intent, env, replace(terrain, slope_deg=20)),
        PhysicsScenario("downhill", base_state, base_intent, env, replace(terrain, slope_deg=-20)),
        PhysicsScenario(
            "rocky", base_state, base_intent, env, replace(terrain, roughness=0.8, rock_density=0.7)
        ),
        PhysicsScenario("dusty", base_state, base_intent, replace(env, dust_opacity=0.85), terrain),
        PhysicsScenario(
            "low-temperature",
            replace(
                base_state,
                motor_temperature_c=-80,
                controller_temperature_c=-70,
                battery_temperature_c=-65,
            ),
            base_intent,
            replace(env, ambient_temperature_c=-100),
            terrain,
        ),
        PhysicsScenario(
            "high-motor-load-thermal",
            replace(base_state, motor_temperature_c=79),
            replace(base_intent, acceleration_mps2=1.5),
            env,
            replace(terrain, slope_deg=25),
        ),
        PhysicsScenario(
            "immobilization-risk",
            base_state,
            replace(base_intent, acceleration_mps2=2),
            env,
            replace(
                terrain, traction_coefficient=0.02, cohesion_kpa=0.05, sinkage_factor_m_kpa=0.08
            ),
        ),
        PhysicsScenario(
            "invalid-unsupported",
            replace(base_state, communication_available=False),
            SimulationIntent(0, 0, safe_motion_state=True),
            env,
            terrain,
        ),
    )
