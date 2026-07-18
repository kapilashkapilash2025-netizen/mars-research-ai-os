from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from mars_ai_os.kernel import Kernel, KernelState


@dataclass
class FakeService:
    name: str
    events: list[str] = field(default_factory=list)
    healthy: bool = True

    def start(self) -> None:
        self.events.append(f"start:{self.name}")

    def stop(self) -> None:
        self.events.append(f"stop:{self.name}")

    def health(self) -> dict[str, object]:
        return {"healthy": self.healthy}


def test_kernel_runs_services_and_reports_health() -> None:
    events: list[str] = []
    first = FakeService("catalog", events)
    second = FakeService("evidence", events)
    kernel = Kernel()
    kernel.register(first)
    kernel.register(second)

    kernel.start()

    assert kernel.state is KernelState.RUNNING
    assert kernel.health()["healthy"] is True
    kernel.stop()
    assert events == ["start:catalog", "start:evidence", "stop:evidence", "stop:catalog"]


def test_kernel_rejects_duplicate_service_names() -> None:
    kernel = Kernel()
    kernel.register(FakeService("catalog"))

    with pytest.raises(ValueError, match="already registered"):
        kernel.register(FakeService("catalog"))

