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

The command prints the start/final pose, travelled distance, final yaw, step count, and navigation health as JSON.

## Prototype scope

This model is designed to validate software integration and basic rigid-body behavior. It is not yet a digital twin. The next fidelity steps are calibrated motor torque curves, suspension joints, regolith contact parameters, wheel slip measurement, IMU/encoder noise, terrain elevation datasets, power and thermal models, and Monte Carlo scenario evaluation.

