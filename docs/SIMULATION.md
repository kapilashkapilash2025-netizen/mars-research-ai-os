# PyBullet Prototype Simulation

The first physics prototype uses PyBullet in headless or GUI mode. It loads an eight-wheel URDF, applies Mars gravity (`3.721 m/s²`), creates a deterministic terrain corridor, maps every wheel joint to the common BLDC interface, and runs the same `EightWheelDrive` controller used by the navigation module.

## Install

```bash
python -m pip install -e ".[dev,simulation]"
```

## Run

Headless, suitable for automation:

```bash
mars-ai-os simulate --duration 6
```

Interactive GUI:

```bash
mars-ai-os simulate --duration 20 --gui
```

## Live design mode

For an unlimited real-time session that stays open until you close it or press `Ctrl+C`:

```bash
mars-ai-os simulate --interactive
```

The PyBullet side panel provides live sliders for forward/reverse speed, left/right turning, motor pause, emergency stop, camera distance, camera yaw, and camera pitch. Start with the motors paused, set the desired speed and turn, then move the pause slider to `0`.

Timed GUI runs are now paced at wall-clock speed, so `--duration 20 --gui` remains visible for approximately 20 real seconds. Headless runs remain unpaced for fast automated testing.

The command prints the start/final pose, travelled distance, final yaw, step count, and navigation health as JSON.

## Prototype scope

This model is designed to validate software integration and basic rigid-body behavior. It is not yet a digital twin. The next fidelity steps are calibrated motor torque curves, suspension joints, regolith contact parameters, wheel slip measurement, IMU/encoder noise, terrain elevation datasets, power and thermal models, and Monte Carlo scenario evaluation.

