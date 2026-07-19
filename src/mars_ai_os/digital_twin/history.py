"""Append-only historical state and explicit replay cursors."""

from __future__ import annotations

from dataclasses import dataclass

from mars_ai_os.digital_twin.models import TwinSnapshot


class HistoricalTwin:
    def __init__(
        self,
        initial: TwinSnapshot,
        *,
        parent_snapshot_id: str | None = None,
        branch_name: str = "canonical",
    ) -> None:
        self._snapshots = [initial]
        self.parent_snapshot_id = parent_snapshot_id
        self.branch_name = branch_name

    @property
    def snapshots(self) -> tuple[TwinSnapshot, ...]:
        return tuple(self._snapshots)

    def append(self, snapshot: TwinSnapshot) -> None:
        if snapshot.timestamp_s < self._snapshots[-1].timestamp_s:
            raise ValueError("Historical snapshots must be time ordered")
        if any(item.snapshot_id == snapshot.snapshot_id for item in self._snapshots):
            raise ValueError("Historical snapshots are immutable and cannot be duplicated")
        self._snapshots.append(snapshot)

    def load(self, snapshot_id: str) -> TwinSnapshot:
        for snapshot in self._snapshots:
            if snapshot.snapshot_id == snapshot_id:
                return snapshot
        raise KeyError(snapshot_id)

    def replay(self) -> tuple[TwinSnapshot, ...]:
        return self.snapshots

    def cursor(self, snapshot_id: str | None = None) -> ReplayCursor:
        index = len(self._snapshots) - 1
        if snapshot_id is not None:
            index = next(
                (
                    i
                    for i, snapshot in enumerate(self._snapshots)
                    if snapshot.snapshot_id == snapshot_id
                ),
                -1,
            )
            if index < 0:
                raise KeyError(snapshot_id)
        return ReplayCursor(self.snapshots, index)

    def branch(self, snapshot_id: str, branch_name: str) -> HistoricalTwin:
        if not branch_name.strip():
            raise ValueError("Replay branch name cannot be empty")
        base = self.load(snapshot_id)
        return HistoricalTwin(base, parent_snapshot_id=base.snapshot_id, branch_name=branch_name)


@dataclass(slots=True)
class ReplayCursor:
    snapshots: tuple[TwinSnapshot, ...]
    index: int

    @property
    def current(self) -> TwinSnapshot:
        return self.snapshots[self.index]

    def step_forward(self) -> TwinSnapshot:
        if self.index >= len(self.snapshots) - 1:
            raise IndexError("Replay is already at the newest snapshot")
        self.index += 1
        return self.current

    def step_backward(self) -> TwinSnapshot:
        if self.index <= 0:
            raise IndexError("Replay is already at the oldest snapshot")
        self.index -= 1
        return self.current
