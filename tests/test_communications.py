from __future__ import annotations

from mars_ai_os.communications import (
    BundlePriority,
    BundleState,
    CommunicationConfig,
    MarsEarthNetwork,
)


def always_connected(**overrides: object) -> CommunicationConfig:
    values: dict[str, object] = {
        "one_way_light_time_s": 10.0,
        "rover_relay_rate_bps": 8_000.0,
        "relay_earth_rate_bps": 8_000.0,
        "relay_contact_period_s": 1.0,
        "relay_contact_duration_s": 1.0,
        "dsn_contact_period_s": 1.0,
        "dsn_contact_duration_s": 1.0,
    }
    values.update(overrides)
    return CommunicationConfig(**values)  # type: ignore[arg-type]


def test_bundle_reaches_earth_after_store_forward_and_light_time() -> None:
    network = MarsEarthNetwork(always_connected())
    bundle = network.submit("science/test", 1_000, BundlePriority.SCIENCE)

    for _ in range(14):
        network.step(1.0)

    assert bundle.state is BundleState.DELIVERED
    assert bundle.delivered_at_s is not None


def test_blackout_keeps_bundle_in_rover_storage() -> None:
    config = CommunicationConfig(
        one_way_light_time_s=10,
        rover_relay_rate_bps=8_000,
        relay_earth_rate_bps=8_000,
        relay_contact_period_s=10,
        relay_contact_duration_s=1,
        dsn_contact_period_s=1,
        dsn_contact_duration_s=1,
    )
    network = MarsEarthNetwork(config)
    network.step(2.0)
    bundle = network.submit("rover/health", 1_000, BundlePriority.HEALTH)
    network.step(5.0)

    assert bundle.state is BundleState.ROVER_QUEUE


def test_emergency_bundle_is_transmitted_before_science() -> None:
    network = MarsEarthNetwork(always_connected())
    science = network.submit("science/image", 1_000, BundlePriority.SCIENCE)
    emergency = network.submit("fault/motor", 1_000, BundlePriority.EMERGENCY)

    network.step(0.1)

    assert emergency.state is BundleState.ROVER_TO_RELAY
    assert science.state is BundleState.ROVER_QUEUE


def test_repeated_link_loss_eventually_fails_bundle() -> None:
    network = MarsEarthNetwork(always_connected(packet_loss_probability=1.0, max_retries=1))
    bundle = network.submit("science/test", 100, BundlePriority.SCIENCE)

    for _ in range(5):
        network.step(1.0)

    assert bundle.state is BundleState.FAILED
    assert bundle.attempts == 2

