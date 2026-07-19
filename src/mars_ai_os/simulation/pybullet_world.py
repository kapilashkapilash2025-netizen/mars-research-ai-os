"""PyBullet prototype world for the eight-wheel rover."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from importlib import import_module
from math import pi
from pathlib import Path
from time import sleep
from typing import Any

from mars_ai_os.navigation.drive import DriveLimits, EightWheelDrive
from mars_ai_os.navigation.motor import MotorTelemetry, WheelPosition

MARS_GRAVITY_MPS2 = 3.721
WHEEL_JOINTS = {position: f"{position.value}_joint" for position in WheelPosition}


@dataclass(frozen=True, slots=True)
class SimulationConfig:
    duration_s: float = 6.0
    time_step_s: float = 1 / 240
    linear_speed_mps: float = 0.55
    angular_speed_radps: float = 0.10
    gui: bool = False
    real_time: bool = False
    motor_torque_nm: float = 45.0

    def __post_init__(self) -> None:
        if self.duration_s <= 0:
            raise ValueError("duration_s must be greater than zero")
        if self.time_step_s <= 0:
            raise ValueError("time_step_s must be greater than zero")
        if self.motor_torque_nm <= 0:
            raise ValueError("motor_torque_nm must be greater than zero")


@dataclass(frozen=True, slots=True)
class SimulationResult:
    duration_s: float
    steps: int
    start_position_m: tuple[float, float, float]
    final_position_m: tuple[float, float, float]
    distance_m: float
    final_yaw_rad: float
    navigation_healthy: bool

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(slots=True)
class SimulationClock:
    now: float = 0.0

    def __call__(self) -> float:
        return self.now


class PyBulletBLDCMotor:
    """Translate the common BLDC contract into PyBullet velocity control."""

    def __init__(
        self,
        bullet: Any,
        client_id: int,
        body_id: int,
        joint_index: int,
        position: WheelPosition,
        max_torque_nm: float,
    ) -> None:
        self._bullet = bullet
        self._client_id = client_id
        self._body_id = body_id
        self._joint_index = joint_index
        self._position = position
        self._max_torque_nm = max_torque_nm
        self._enabled = False

    @property
    def position(self) -> WheelPosition:
        return self._position

    def enable(self) -> None:
        self._enabled = True

    def command_rpm(self, rpm: float) -> None:
        if not self._enabled:
            raise RuntimeError(f"Motor is disabled: {self.position}")
        self._bullet.setJointMotorControl2(
            self._body_id,
            self._joint_index,
            self._bullet.VELOCITY_CONTROL,
            targetVelocity=rpm * 2 * pi / 60,
            force=self._max_torque_nm,
            physicsClientId=self._client_id,
        )

    def stop(self) -> None:
        self._bullet.setJointMotorControl2(
            self._body_id,
            self._joint_index,
            self._bullet.VELOCITY_CONTROL,
            targetVelocity=0.0,
            force=self._max_torque_nm,
            physicsClientId=self._client_id,
        )

    def disable(self) -> None:
        self.stop()
        self._enabled = False

    def telemetry(self) -> MotorTelemetry:
        state = self._bullet.getJointState(
            self._body_id, self._joint_index, physicsClientId=self._client_id
        )
        return MotorTelemetry(
            rpm=float(state[1]) * 60 / (2 * pi),
            temperature_c=20.0,
            bus_voltage_v=48.0,
        )


class PyBulletMarsWorld:
    def __init__(self, config: SimulationConfig) -> None:
        self.config = config
        self.bullet = _load_pybullet()
        mode = self.bullet.GUI if config.gui else self.bullet.DIRECT
        self.client_id = self.bullet.connect(mode)
        if self.client_id < 0:
            raise RuntimeError("Unable to connect to PyBullet")
        self.body_id: int | None = None
        self.clock = SimulationClock()

    def __enter__(self) -> PyBulletMarsWorld:
        self.setup()
        return self

    def __exit__(self, *_: object) -> None:
        self.bullet.disconnect(physicsClientId=self.client_id)

    def setup(self) -> None:
        self.bullet.resetSimulation(physicsClientId=self.client_id)
        self.bullet.setGravity(0, 0, -MARS_GRAVITY_MPS2, physicsClientId=self.client_id)
        self.bullet.setTimeStep(self.config.time_step_s, physicsClientId=self.client_id)
        self._create_terrain()
        urdf = _repository_root() / "assets" / "robots" / "mars_rover_8wd.urdf"
        self.body_id = self.bullet.loadURDF(
            str(urdf),
            basePosition=(0, 0, 0.48),
            useFixedBase=False,
            physicsClientId=self.client_id,
        )
        for joint_index in range(self.bullet.getNumJoints(self.body_id, self.client_id)):
            self.bullet.changeDynamics(
                self.body_id,
                joint_index,
                lateralFriction=1.2,
                rollingFriction=0.02,
                spinningFriction=0.02,
                physicsClientId=self.client_id,
            )

    def build_drive(self) -> EightWheelDrive:
        if self.body_id is None:
            raise RuntimeError("World is not set up")
        joint_indices = self._joint_indices()
        motors = {
            position: PyBulletBLDCMotor(
                self.bullet,
                self.client_id,
                self.body_id,
                joint_indices[joint_name],
                position,
                self.config.motor_torque_nm,
            )
            for position, joint_name in WHEEL_JOINTS.items()
        }
        return EightWheelDrive(
            motors,
            DriveLimits(wheel_radius_m=0.25, track_width_m=1.24, command_timeout_s=0.25),
            self.clock,
        )

    def pose(self) -> tuple[tuple[float, float, float], float]:
        if self.body_id is None:
            raise RuntimeError("World is not set up")
        position, orientation = self.bullet.getBasePositionAndOrientation(
            self.body_id, physicsClientId=self.client_id
        )
        yaw = self.bullet.getEulerFromQuaternion(orientation)[2]
        return tuple(float(value) for value in position), float(yaw)

    def step(self) -> None:
        self.bullet.stepSimulation(physicsClientId=self.client_id)
        self.clock.now += self.config.time_step_s
        if self.config.real_time:
            sleep(self.config.time_step_s)

    def follow_camera(self, distance: float, yaw: float, pitch: float) -> None:
        position, _ = self.pose()
        self.bullet.resetDebugVisualizerCamera(
            cameraDistance=distance,
            cameraYaw=yaw,
            cameraPitch=pitch,
            cameraTargetPosition=position,
            physicsClientId=self.client_id,
        )

    def _joint_indices(self) -> dict[str, int]:
        if self.body_id is None:
            raise RuntimeError("World is not set up")
        result = {}
        count = self.bullet.getNumJoints(self.body_id, physicsClientId=self.client_id)
        for index in range(count):
            info = self.bullet.getJointInfo(self.body_id, index, physicsClientId=self.client_id)
            result[info[1].decode("utf-8")] = index
        missing = set(WHEEL_JOINTS.values()) - set(result)
        if missing:
            raise RuntimeError(f"URDF is missing wheel joints: {sorted(missing)}")
        return result

    def _create_terrain(self) -> None:
        plane_shape = self.bullet.createCollisionShape(
            self.bullet.GEOM_PLANE, physicsClientId=self.client_id
        )
        plane = self.bullet.createMultiBody(
            baseMass=0,
            baseCollisionShapeIndex=plane_shape,
            physicsClientId=self.client_id,
        )
        self.bullet.changeDynamics(
            plane, -1, lateralFriction=1.0, rollingFriction=0.01, physicsClientId=self.client_id
        )
        # Deterministic rocks border the test corridor without blocking the initial run.
        for x, y, scale in ((1.5, 1.1, 1.0), (2.5, -1.2, 1.4), (3.7, 1.0, 0.8)):
            rock_shape = self.bullet.createCollisionShape(
                self.bullet.GEOM_SPHERE,
                radius=0.18 * scale,
                physicsClientId=self.client_id,
            )
            rock = self.bullet.createMultiBody(
                baseMass=0,
                baseCollisionShapeIndex=rock_shape,
                basePosition=(x, y, 0.14 * scale),
                physicsClientId=self.client_id,
            )
            self.bullet.changeDynamics(
                rock, -1, lateralFriction=1.1, physicsClientId=self.client_id
            )


def run_demo(config: SimulationConfig | None = None) -> SimulationResult:
    config = config or SimulationConfig()
    with PyBulletMarsWorld(config) as world:
        drive = world.build_drive()
        drive.start()
        start_position, _ = world.pose()
        steps = round(config.duration_s / config.time_step_s)
        refresh_steps = max(1, round(0.1 / config.time_step_s))
        for step in range(steps):
            if step % refresh_steps == 0:
                drive.command_velocity(config.linear_speed_mps, config.angular_speed_radps)
            world.step()
            drive.tick()
        final_position, yaw = world.pose()
        health = drive.health()
        drive.stop()

    dx = final_position[0] - start_position[0]
    dy = final_position[1] - start_position[1]
    return SimulationResult(
        duration_s=config.duration_s,
        steps=steps,
        start_position_m=start_position,
        final_position_m=final_position,
        distance_m=(dx * dx + dy * dy) ** 0.5,
        final_yaw_rad=yaw,
        navigation_healthy=health["healthy"] is True,
    )


def run_interactive() -> None:
    """Run an unlimited, real-time GUI session with live design controls."""

    config = SimulationConfig(gui=True, real_time=True)
    with PyBulletMarsWorld(config) as world:
        from mars_ai_os.simulation.communication_overlay import CommunicationOverlay

        drive = world.build_drive()
        drive.start()
        bullet = world.bullet
        client = world.client_id
        speed = bullet.addUserDebugParameter(
            "Forward / reverse (m/s)", -1.0, 1.0, 0.0, physicsClientId=client
        )
        turn = bullet.addUserDebugParameter(
            "Turn left / right (rad/s)", -0.8, 0.8, 0.0, physicsClientId=client
        )
        pause = bullet.addUserDebugParameter(
            "Pause motors (0=drive, 1=pause)", 0.0, 1.0, 1.0, physicsClientId=client
        )
        emergency = bullet.addUserDebugParameter(
            "EMERGENCY STOP", 0.0, 1.0, 0.0, physicsClientId=client
        )
        camera_distance = bullet.addUserDebugParameter(
            "Camera distance", 3.0, 15.0, 6.0, physicsClientId=client
        )
        camera_yaw = bullet.addUserDebugParameter(
            "Camera yaw", -180.0, 180.0, 45.0, physicsClientId=client
        )
        camera_pitch = bullet.addUserDebugParameter(
            "Camera pitch", -80.0, -10.0, -30.0, physicsClientId=client
        )
        bullet.addUserDebugText(
            "Mars AI OS | adjust sliders to drive and inspect the rover",
            (0.0, 0.0, 1.2),
            textColorRGB=(0.9, 0.4, 0.1),
            textSize=1.3,
            parentObjectUniqueId=world.body_id,
            physicsClientId=client,
        )
        communications = CommunicationOverlay(bullet, client)

        refresh_steps = max(1, round(0.1 / config.time_step_s))
        step = 0
        try:
            while bullet.isConnected(physicsClientId=client):
                if bullet.readUserDebugParameter(emergency, physicsClientId=client) >= 0.5:
                    drive.emergency_stop("operator emergency stop")
                    break
                is_paused = bullet.readUserDebugParameter(pause, physicsClientId=client) >= 0.5
                if step % refresh_steps == 0:
                    linear = 0.0 if is_paused else bullet.readUserDebugParameter(
                        speed, physicsClientId=client
                    )
                    angular = 0.0 if is_paused else bullet.readUserDebugParameter(
                        turn, physicsClientId=client
                    )
                    drive.command_velocity(linear, angular)
                world.step()
                drive.tick()
                communications.step(config.time_step_s)
                world.follow_camera(
                    bullet.readUserDebugParameter(camera_distance, physicsClientId=client),
                    bullet.readUserDebugParameter(camera_yaw, physicsClientId=client),
                    bullet.readUserDebugParameter(camera_pitch, physicsClientId=client),
                )
                step += 1
        except KeyboardInterrupt:
            drive.emergency_stop("operator interrupted simulation")
        finally:
            drive.stop()


def _load_pybullet() -> Any:
    try:
        return import_module("pybullet")
    except ModuleNotFoundError as error:
        raise RuntimeError(
            'PyBullet is required; install it with: python -m pip install -e ".[simulation]"'
        ) from error


def _repository_root() -> Path:
    return Path(__file__).resolve().parents[3]
