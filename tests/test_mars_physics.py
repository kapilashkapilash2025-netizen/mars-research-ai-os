from __future__ import annotations

from dataclasses import replace
from math import isfinite

import pytest

from mars_ai_os.digital_twin import DigitalTwinEngine, create_provenance, reference_rover_state
from mars_ai_os.digital_twin.events import EventBus, PhysicsPredictionCompleted
from mars_ai_os.mars_physics import (
    MarsEnvironment,
    PhysicsEngine,
    PhysicsState,
    PhysicsTwinAdapter,
    SimulationIntent,
    Terrain,
    VehicleParameters,
    reference_scenarios,
)
from mars_ai_os.mars_physics.demo import run_physics_demo


def test_identical_inputs_are_bit_reproducible() -> None:
    scenario = reference_scenarios()[0]
    engine = PhysicsEngine()
    args = (
        scenario.state,
        scenario.intent,
        scenario.environment,
        scenario.terrain,
        VehicleParameters(),
    )
    first = engine.step(*args, timestep_s=10, seed=13)
    second = engine.step(*args, timestep_s=10, seed=13)
    assert first == second
    assert first.fingerprint == second.fingerprint


@pytest.mark.parametrize("scenario", reference_scenarios(), ids=lambda item: item.scenario_id)
def test_reference_scenario_physical_invariants(scenario: object) -> None:
    result = PhysicsEngine().step(
        scenario.state,
        scenario.intent,
        scenario.environment,
        scenario.terrain,
        VehicleParameters(),
        timestep_s=10,
        seed=13,
    )
    assert result.predicted_state.timestamp_s > scenario.state.timestamp_s
    assert 0 <= result.slip_ratio <= 1
    assert 0 <= result.sinkage_m <= 0.25
    assert 0 <= result.predicted_state.battery_energy_wh <= 5000
    assert result.energy.drivetrain_energy_wh >= 0
    assert result.energy.auxiliary_energy_wh >= 0
    assert result.energy.solar_input_wh >= 0
    assert result.energy.curtailed_energy_wh >= 0
    assert result.energy.unmet_energy_wh >= 0
    requested_change = (
        result.energy.solar_input_wh
        - result.energy.drivetrain_energy_wh
        - result.energy.auxiliary_energy_wh
    )
    assert requested_change == pytest.approx(
        result.energy.net_battery_change_wh
        + result.energy.curtailed_energy_wh
        - result.energy.unmet_energy_wh
    )
    assert 0 <= result.observations.camera_quality <= 1
    assert 0 <= result.observations.lidar_quality <= 1
    assert 0 <= result.solar_quality <= 1
    assert 0 <= result.communication_quality <= 1
    assert 0 <= result.confidence <= 1
    assert all(
        isfinite(value)
        for value in (
            result.thermal.motor_c,
            result.thermal.controller_c,
            result.thermal.battery_c,
            result.thermal.compute_c,
        )
    )


def test_uphill_costs_more_drivetrain_energy_than_downhill() -> None:
    scenarios = {item.scenario_id: item for item in reference_scenarios()}
    engine = PhysicsEngine()
    vehicle = VehicleParameters()
    uphill = scenarios["uphill"]
    downhill = scenarios["downhill"]
    up = engine.step(
        uphill.state,
        uphill.intent,
        uphill.environment,
        uphill.terrain,
        vehicle,
        timestep_s=10,
        seed=1,
    )
    down = engine.step(
        downhill.state,
        downhill.intent,
        downhill.environment,
        downhill.terrain,
        vehicle,
        timestep_s=10,
        seed=1,
    )
    assert up.energy.drivetrain_energy_wh > down.energy.drivetrain_energy_wh
    assert any("braking" in warning for warning in down.warnings)


def test_dust_degrades_sensor_solar_and_communication_quality() -> None:
    scenario = reference_scenarios()[0]
    engine = PhysicsEngine()
    clear = engine.step(
        scenario.state,
        scenario.intent,
        MarsEnvironment(dust_opacity=0),
        scenario.terrain,
        VehicleParameters(),
        timestep_s=10,
        seed=2,
    )
    dusty = engine.step(
        scenario.state,
        scenario.intent,
        MarsEnvironment(dust_opacity=0.9),
        scenario.terrain,
        VehicleParameters(),
        timestep_s=10,
        seed=2,
    )
    assert dusty.observations.camera_quality < clear.observations.camera_quality
    assert dusty.observations.lidar_quality < clear.observations.lidar_quality
    assert dusty.energy.solar_input_wh < clear.energy.solar_input_wh
    assert dusty.communication_quality < clear.communication_quality


def test_noise_seed_changes_observation_not_truth() -> None:
    scenario = reference_scenarios()[0]
    engine = PhysicsEngine()
    args = (
        scenario.state,
        scenario.intent,
        scenario.environment,
        scenario.terrain,
        VehicleParameters(),
    )
    first = engine.step(*args, timestep_s=10, seed=3)
    second = engine.step(*args, timestep_s=10, seed=4)
    assert first.predicted_state == second.predicted_state
    assert first.observations != second.observations


@pytest.mark.parametrize(
    ("factory", "message"),
    [
        (lambda: MarsEnvironment(gravity_mps2=float("nan")), "finite"),
        (lambda: Terrain(slope_deg=60), "slope_deg"),
        (
            lambda: PhysicsState(0, (0, 0, 0), 0, 0, -1, 20, 20, 20, 20, True),
            "battery",
        ),
    ],
)
def test_invalid_models_are_rejected(factory: object, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        factory()


def test_communication_loss_rejects_unapproved_continuing_motion() -> None:
    scenario = reference_scenarios()[0]
    disconnected = replace(scenario.state, communication_available=False)
    with pytest.raises(ValueError, match="safe motion"):
        PhysicsEngine().step(
            disconnected,
            SimulationIntent(0.5),
            scenario.environment,
            scenario.terrain,
            VehicleParameters(),
            timestep_s=10,
            seed=1,
        )


def test_twin_adapter_produces_candidate_and_event_without_mutation() -> None:
    provenance = create_provenance(
        configuration={"reference": True},
        seed=13,
        assumptions=(),
        author="test",
        recorded_at_s=0,
    )
    twin = DigitalTwinEngine(
        initial_state=reference_rover_state(),
        mission_id="test-mission",
        seed=13,
        environment_id="mars-reference",
        timestamp_s=0,
        provenance=provenance,
    )
    original_id = twin.live_snapshot.snapshot_id
    original_history = len(twin.history.snapshots)
    bus = EventBus()
    events: list[PhysicsPredictionCompleted] = []
    bus.subscribe(PhysicsPredictionCompleted, events.append)
    result, candidate = PhysicsTwinAdapter(event_bus=bus).predict(
        twin.live_snapshot,
        SimulationIntent(0.4, 0.02),
        MarsEnvironment(),
        Terrain(),
        VehicleParameters(),
        timestep_s=10,
        seed=13,
    )
    assert twin.live_snapshot.snapshot_id == original_id
    assert len(twin.history.snapshots) == original_history
    assert candidate.snapshot_id != original_id
    assert candidate.metadata[0].value == original_id
    assert result.predicted_snapshot_id == candidate.snapshot_id
    assert events[0].configuration_hash == result.configuration_hash


def test_physics_demo_is_stable_and_information_only() -> None:
    first = run_physics_demo()
    assert first == run_physics_demo()
    assert len(str(first["fingerprint"])) == 64
    assert "no hardware" in str(first["safety"])
