# Mars-to-Earth Communication Digital Twin

The communications simulation models the operational path from an autonomous surface rover through a Mars relay orbiter and the Deep Space Network to Earth mission control.

## Architecture

```text
Rover DTN node -> UHF relay contact -> Mars orbiter storage
              -> scheduled deep-space downlink + light time
              -> DSN / Earth delivery
```

The rover never depends on Earth for immediate driving decisions. Commands are treated as delayed mission intents; local autonomy validates and executes them. Telemetry and science data are packaged as delay-tolerant bundles and stored until the next link becomes available.

## Simulated behavior

- configurable 3–22.4 minute one-way light time
- rover-to-orbiter and orbiter-to-Earth bandwidth
- independent relay and DSN contact windows
- emergency, health, navigation, science, and log priorities
- store-and-forward queues
- deterministic packet loss, retry, expiry, and failure
- accelerated communication time while rover physics stays real-time

## Run

Headless communication scenario:

```bash
mars-ai-os communicate --duration 3600 --step 1
```

Live rover and communication visualization:

```bash
mars-ai-os simulate --interactive
```

The PyBullet panel includes controls for one-way delay, packet loss, and communication time acceleration. Green links indicate an active contact; red links indicate a blackout. The overlay reports queued, propagating, and Earth-delivered bundles.

This is a protocol and operations model, not an RF link-budget certification. Antenna gain, frequency, transmitter power, coding, atmospheric loss, pointing, real orbiter ephemerides, and DSN scheduling require mission-specific inputs before calibration.

