"""Minimal lifecycle kernel for research services and agents."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Protocol

from mars_ai_os.config import Settings


class Service(Protocol):
    """Contract implemented by kernel-managed tools, agents, and services."""

    @property
    def name(self) -> str: ...

    def start(self) -> None: ...

    def stop(self) -> None: ...

    def health(self) -> dict[str, object]: ...


class KernelState(StrEnum):
    CREATED = "created"
    RUNNING = "running"
    STOPPED = "stopped"


@dataclass(slots=True)
class Kernel:
    """Own service registration, lifecycle ordering, and health reporting."""

    settings: Settings = field(default_factory=Settings.from_environment)
    _services: dict[str, Service] = field(default_factory=dict, init=False)
    _state: KernelState = field(default=KernelState.CREATED, init=False)

    @property
    def state(self) -> KernelState:
        return self._state

    @property
    def service_names(self) -> tuple[str, ...]:
        return tuple(self._services)

    def register(self, service: Service) -> None:
        if self._state is not KernelState.CREATED:
            raise RuntimeError("Services can only be registered before the kernel starts")
        if not service.name.strip():
            raise ValueError("Service name cannot be empty")
        if service.name in self._services:
            raise ValueError(f"Service already registered: {service.name}")
        self._services[service.name] = service

    def start(self) -> None:
        if self._state is not KernelState.CREATED:
            raise RuntimeError(f"Cannot start kernel from state {self._state}")

        started: list[Service] = []
        try:
            for service in self._services.values():
                service.start()
                started.append(service)
        except Exception:
            for service in reversed(started):
                service.stop()
            raise

        self._state = KernelState.RUNNING

    def stop(self) -> None:
        if self._state is not KernelState.RUNNING:
            raise RuntimeError(f"Cannot stop kernel from state {self._state}")
        for service in reversed(tuple(self._services.values())):
            service.stop()
        self._state = KernelState.STOPPED

    def health(self) -> dict[str, object]:
        services = {name: service.health() for name, service in self._services.items()}
        healthy = self._state is KernelState.RUNNING and all(
            status.get("healthy") is True for status in services.values()
        )
        return {
            "healthy": healthy,
            "state": self._state.value,
            "environment": self.settings.environment,
            "evidence_required": self.settings.evidence_required,
            "services": services,
        }

