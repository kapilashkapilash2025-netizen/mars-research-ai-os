from mars_ai_os.control.controller import SafetyMotionController
from mars_ai_os.control.models import MotionAuthorization, MotionIntent, OperatingMode, SourceType
from mars_ai_os.digital_twin import DigitalTwinEngine, create_provenance, reference_rover_state
from mars_ai_os.hal import HalConfiguration, InMemorySimulationBackend, ManualClock


def run_control_demo() -> dict[str, object]:
    clock = ManualClock()
    hal = InMemorySimulationBackend(HalConfiguration(), clock)
    hal.initialize()
    prov = create_provenance(
        configuration={"demo": True},
        seed=13,
        assumptions=(),
        author="control-demo",
        recorded_at_s=0,
    )
    twin = DigitalTwinEngine(
        initial_state=reference_rover_state(),
        mission_id="demo",
        seed=13,
        environment_id="mars",
        timestamp_s=0,
        provenance=prov,
    )
    auth = MotionAuthorization(
        "demo-auth", "demo", "test", (OperatingMode.TEST,), 1, 1, 2, 0, 10, "demo"
    )
    controller = SafetyMotionController(hal)
    controller.enter_mode(OperatingMode.TEST, auth, 0)
    intent = MotionIntent(
        "straight",
        "demo",
        "demo",
        SourceType.TEST_HARNESS,
        0.5,
        0,
        0,
        2,
        1,
        auth,
        OperatingMode.TEST,
        duration_s=1,
    )
    result = controller.process(intent, twin.live_snapshot)
    stop = controller.safe_stop(twin.live_snapshot)
    return {
        "accepted": result.accepted,
        "motor_commands": len(result.wheel_rpm),
        "left_rpm": result.wheel_rpm[0][1],
        "right_rpm": result.wheel_rpm[-1][1],
        "safe_stop": stop.accepted,
        "trace": result.trace.fingerprint,
        "safety": "deterministic simulation authority only; no hardware commands",
    }
