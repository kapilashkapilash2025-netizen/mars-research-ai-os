"""PyBullet visualization for the Mars-to-Earth DTN simulation."""

from __future__ import annotations

from typing import Any

from mars_ai_os.communications import BundlePriority, CommunicationConfig, MarsEarthNetwork


class CommunicationOverlay:
    def __init__(self, bullet: Any, client_id: int) -> None:
        self.bullet = bullet
        self.client_id = client_id
        self.network = MarsEarthNetwork()
        self._last_health_bundle_s = -60.0
        self._last_science_bundle_s = -300.0
        self._status_text_id = -1
        self._relay_line_id = -1
        self._earth_line_id = -1
        self._delay_control = bullet.addUserDebugParameter(
            "Earth one-way delay (minutes)", 3.0, 22.4, 12.0, physicsClientId=client_id
        )
        self._loss_control = bullet.addUserDebugParameter(
            "Communication packet loss (%)", 0.0, 30.0, 0.0, physicsClientId=client_id
        )
        self._time_scale_control = bullet.addUserDebugParameter(
            "Communication time acceleration", 1.0, 600.0, 120.0, physicsClientId=client_id
        )
        self._draw_static_nodes()
        self.network.submit("startup/health", 4_096, BundlePriority.HEALTH)

    def step(self, physics_elapsed_s: float) -> None:
        light_minutes = self.bullet.readUserDebugParameter(
            self._delay_control, physicsClientId=self.client_id
        )
        loss_percent = self.bullet.readUserDebugParameter(
            self._loss_control, physicsClientId=self.client_id
        )
        time_scale = self.bullet.readUserDebugParameter(
            self._time_scale_control, physicsClientId=self.client_id
        )
        if (
            light_minutes * 60 != self.network.config.one_way_light_time_s
            or loss_percent / 100 != self.network.config.packet_loss_probability
        ):
            self.network.config = CommunicationConfig(
                one_way_light_time_s=light_minutes * 60,
                packet_loss_probability=loss_percent / 100,
            )
        self.network.step(physics_elapsed_s * time_scale)
        self._generate_periodic_bundles()
        self._update_visuals(light_minutes, time_scale)

    def _generate_periodic_bundles(self) -> None:
        now = self.network.now_s
        if now - self._last_health_bundle_s >= 60:
            self.network.submit("rover/health", 8_192, BundlePriority.HEALTH, lifetime_s=3_600)
            self._last_health_bundle_s = now
        if now - self._last_science_bundle_s >= 300:
            self.network.submit("science/telemetry", 2_000_000, BundlePriority.SCIENCE)
            self._last_science_bundle_s = now

    def _draw_static_nodes(self) -> None:
        for label, position in (
            ("ROVER DTN", (-1.8, -2.5, 1.3)),
            ("MARS RELAY", (0.3, -2.5, 2.2)),
            ("DSN / EARTH", (2.5, -2.5, 1.3)),
        ):
            self.bullet.addUserDebugText(
                label,
                position,
                textColorRGB=(0.9, 0.65, 0.2),
                textSize=1.1,
                physicsClientId=self.client_id,
            )

    def _update_visuals(self, light_minutes: float, time_scale: float) -> None:
        relay_color = (0.2, 0.9, 0.3) if self.network.relay_contact_active else (0.8, 0.2, 0.2)
        earth_color = (0.2, 0.9, 0.3) if self.network.dsn_contact_active else (0.8, 0.2, 0.2)
        self._relay_line_id = self.bullet.addUserDebugLine(
            (-1.5, -2.5, 1.4),
            (0.0, -2.5, 2.1),
            relay_color,
            lineWidth=3,
            replaceItemUniqueId=self._relay_line_id,
            physicsClientId=self.client_id,
        )
        self._earth_line_id = self.bullet.addUserDebugLine(
            (0.6, -2.5, 2.1),
            (2.2, -2.5, 1.4),
            earth_color,
            lineWidth=3,
            replaceItemUniqueId=self._earth_line_id,
            physicsClientId=self.client_id,
        )
        counts = self.network.summary()["bundles"]
        queued = counts["rover_queue"] + counts["relay_queue"]
        status = (
            f"COMM x{time_scale:.0f} | delay {light_minutes:.1f} min | "
            f"queued {queued} | propagating {counts['propagating']} | "
            f"Earth delivered {counts['delivered']}"
        )
        self._status_text_id = self.bullet.addUserDebugText(
            status,
            (-1.8, -2.5, 0.7),
            textColorRGB=(0.9, 0.9, 0.9),
            textSize=1.0,
            replaceItemUniqueId=self._status_text_id,
            physicsClientId=self.client_id,
        )

