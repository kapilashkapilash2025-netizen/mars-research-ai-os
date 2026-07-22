"""Small repository boundary with in-memory and atomic JSON implementations."""

from __future__ import annotations

import json
from pathlib import Path
from threading import RLock
from typing import Protocol

from mars_ai_os.mission.contracts import MissionPlan, MissionRun, jsonable


class MissionRepository(Protocol):
    def save_plan(self, plan: MissionPlan) -> None: ...
    def load_plan(self, plan_id: str) -> MissionPlan: ...
    def save_run(self, run: MissionRun) -> None: ...
    def load_run(self, run_id: str) -> MissionRun: ...


class MemoryMissionRepository:
    def __init__(self) -> None:
        self.plans: dict[str, MissionPlan] = {}
        self.runs: dict[str, MissionRun] = {}

    def save_plan(self, plan: MissionPlan) -> None:
        self.plans[plan.plan_id] = plan

    def load_plan(self, plan_id: str) -> MissionPlan:
        return self.plans[plan_id]

    def save_run(self, run: MissionRun) -> None:
        self.runs[run.run_id] = run

    def load_run(self, run_id: str) -> MissionRun:
        return self.runs[run_id]


class JsonMissionRepository(MemoryMissionRepository):
    """Process-local objects plus versioned, atomic JSON audit persistence."""

    def __init__(self, directory: str | Path) -> None:
        super().__init__()
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self._lock = RLock()

    def save_plan(self, plan: MissionPlan) -> None:
        super().save_plan(plan)
        self._write(f"plan-{plan.plan_id}.json", jsonable(plan))

    def save_run(self, run: MissionRun) -> None:
        super().save_run(run)
        self._write(f"run-{run.run_id}.json", jsonable(run))

    def _write(self, name: str, value: object) -> None:
        target = self.directory / name
        temporary = target.with_suffix(".tmp")
        with self._lock:
            temporary.write_text(json.dumps(value, indent=2, sort_keys=True), encoding="utf-8")
            temporary.replace(target)
