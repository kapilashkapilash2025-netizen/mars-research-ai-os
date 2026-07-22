"""Stable deterministic CLI demonstration."""

from mars_ai_os.mars_physics.engine import PhysicsEngine
from mars_ai_os.mars_physics.models import VehicleParameters
from mars_ai_os.mars_physics.scenarios import reference_scenarios


def run_physics_demo() -> dict[str, object]:
    scenario = reference_scenarios()[2]
    result = PhysicsEngine().step(
        scenario.state,
        scenario.intent,
        scenario.environment,
        scenario.terrain,
        VehicleParameters(),
        timestep_s=10,
        seed=13,
    )
    return {
        "scenario": scenario.scenario_id,
        "fingerprint": result.fingerprint,
        "position_m": list(result.predicted_state.position_m),
        "battery_energy_wh": result.predicted_state.battery_energy_wh,
        "slip_ratio": result.slip_ratio,
        "sinkage_m": result.sinkage_m,
        "warnings": list(result.warnings),
        "confidence": result.confidence,
        "safety": "candidate prediction only; no hardware commands",
    }
