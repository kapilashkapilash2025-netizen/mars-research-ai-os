"""Stable HAL CLI demo."""

from mars_ai_os.hal.models import CommandEnvelope, HalConfiguration
from mars_ai_os.hal.runtime import ManualClock
from mars_ai_os.hal.simulation import InMemorySimulationBackend


def run_hal_demo() -> dict[str, object]:
    clock = ManualClock()
    backend = InMemorySimulationBackend(HalConfiguration(), clock)
    backend.initialize()
    motor = "drive.left.front_outer"
    limited = backend.command(
        CommandEnvelope(
            "demo-rpm",
            motor,
            "set_rpm",
            0,
            1,
            1,
            "demo",
            999,
            "rpm",
            configuration_hash=backend.config.fingerprint,
        )
    )
    clock.advance(3)
    watchdog = backend.tick()
    backend.estop.activate(clock.now())
    blocked = backend.command(
        CommandEnvelope(
            "blocked",
            motor,
            "set_rpm",
            3,
            4,
            2,
            "demo",
            10,
            "rpm",
            configuration_hash=backend.config.fingerprint,
        )
    )
    backend.estop.clear(clock.now(), True)
    return {
        "motors": len(backend.registry.drive_motors()),
        "limited": limited.status.value,
        "watchdog_motors": list(watchdog),
        "estop_blocked": blocked.status.value,
        "all_stopped": all(m.rpm == 0 for m in backend.registry.drive_motors()),
        "audit_records": len(backend.audit.records),
        "configuration": backend.config.fingerprint,
        "safety": "in-memory behavior simulation only; no hardware commands",
    }
