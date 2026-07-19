from __future__ import annotations

import pytest

pybullet = pytest.importorskip("pybullet")

from mars_ai_os.simulation.pybullet_world import (  # noqa: E402
    MARS_GRAVITY_MPS2,
    PyBulletMarsWorld,
    SimulationConfig,
    run_demo,
)


def test_world_loads_eight_wheel_rover() -> None:
    config = SimulationConfig(duration_s=0.1, time_step_s=1 / 120)

    with PyBulletMarsWorld(config) as world:
        drive = world.build_drive()
        drive.start()

        assert len(drive.motors) == 8
        assert MARS_GRAVITY_MPS2 == pytest.approx(3.721)


def test_headless_demo_moves_and_stays_healthy() -> None:
    result = run_demo(
        SimulationConfig(
            duration_s=1.5,
            time_step_s=1 / 120,
            linear_speed_mps=0.45,
            angular_speed_radps=0.0,
        )
    )

    assert result.steps == 180
    assert result.distance_m > 0.05
    assert result.navigation_healthy is True
