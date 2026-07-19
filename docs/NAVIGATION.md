# Eight-Wheel BLDC Navigation

The first navigation module models an eight-wheel skid-steer rover with four brushless DC motors on each side. It converts linear and angular velocity targets into left/right wheel RPM while preserving the requested turn ratio when RPM limits are reached.

## Wheel layout

- Left: front, mid-front, mid-rear, rear
- Right: front, mid-front, mid-rear, rear

Every motor controller must implement the `BLDCMotor` interface. Vendor-specific CAN, UART, or fieldbus drivers belong in separate modules and must translate controller telemetry into the common `MotorTelemetry` model.

## Safety behavior

- An exact eight-wheel mapping is required before startup.
- Faulted or overheated motors prevent startup.
- A fault detected during operation stops all eight wheels.
- A missing velocity command beyond the configured timeout stops all eight wheels.
- Emergency stop is latched; this base module does not automatically restart motion.
- Speed and turn inputs are limited, then wheel RPM is proportionally scaled.

## Hardware boundary

`SimulatedBLDCMotor` is for software development only. Do not connect this code directly to flight or rover hardware. A hardware adapter requires controller-specific limits, redundant physical emergency stops, independent watchdogs, current limiting, braking policy, communications-loss behavior, wheel direction calibration, and staged bench testing before any mobile test.

