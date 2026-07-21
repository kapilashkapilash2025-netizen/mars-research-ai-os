"""Deterministic simulation-first boot runtime; no kernel or hardware driver."""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import StrEnum

from mars_ai_os.digital_twin.provenance import canonical_json


def _fp(value: object) -> str:
    import hashlib

    return hashlib.sha256(canonical_json(value).encode()).hexdigest()


class BootState(StrEnum):
    OFF = "off"
    BOOTING = "booting"
    SELF_TEST = "self_test"
    SAFE_MODE = "safe_mode"
    READY = "ready"
    FAULTED = "faulted"
    SHUTDOWN = "shutdown"


@dataclass(frozen=True, slots=True)
class ServiceManifest:
    name: str
    requires: tuple[str, ...]
    critical: bool = True


@dataclass(frozen=True, slots=True)
class BootRecord:
    sequence: int
    timestamp_s: float
    state: BootState
    detail: str
    fingerprint: str = ""


class BootRuntime:
    def __init__(self, services: tuple[ServiceManifest, ...]):
        self.services = services
        self.state = BootState.OFF
        self.audit: list[BootRecord] = []

    def boot(self, available: tuple[str, ...], now_s: float) -> BootState:
        self._set(BootState.BOOTING, now_s, "runtime starting")
        self._set(BootState.SELF_TEST, now_s, "checking critical services")
        missing = tuple(s.name for s in self.services if s.critical and s.name not in available)
        self._set(
            BootState.SAFE_MODE if missing else BootState.READY,
            now_s,
            "missing: " + ",".join(missing) if missing else "all critical services ready",
        )
        return self.state

    def shutdown(self, now_s: float):
        self._set(BootState.SHUTDOWN, now_s, "explicit shutdown")

    def _set(self, state, now, detail):
        self.state = state
        r = BootRecord(len(self.audit) + 1, now, state, detail)
        self.audit.append(replace(r, fingerprint=_fp(r)))


def reference_manifest() -> tuple[ServiceManifest, ...]:
    return (
        ServiceManifest("audit-service", ()),
        ServiceManifest("digital-twin-service", ("audit-service",)),
        ServiceManifest("safety-service", ("digital-twin-service",)),
        ServiceManifest("hal-service", ("safety-service",)),
        ServiceManifest("mission-service", ("safety-service",), False),
    )
