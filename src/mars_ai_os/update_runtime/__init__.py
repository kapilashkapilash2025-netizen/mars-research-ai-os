"""Deterministic image/update contract; no firmware flashing or cryptographic claim."""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import StrEnum

from mars_ai_os.digital_twin.provenance import canonical_json


def _digest(value: object) -> str:
    import hashlib

    return hashlib.sha256(canonical_json(value).encode()).hexdigest()


class Slot(StrEnum):
    A = "A"
    B = "B"


class UpdateState(StrEnum):
    IDLE = "idle"
    VALIDATED = "validated"
    STAGED = "staged"
    BOOT_PENDING = "boot_pending"
    CONFIRMED = "confirmed"
    ROLLED_BACK = "rolled_back"
    REJECTED = "rejected"


@dataclass(frozen=True, slots=True)
class ImageManifest:
    image_id: str
    version: str
    base_os: str
    architecture: str
    packages: tuple[str, ...]
    configuration_hash: str
    build_seed: int
    digest: str = ""


@dataclass(frozen=True, slots=True)
class UpdatePackage:
    package_id: str
    manifest: ImageManifest
    expected_digest: str
    signature_scheme: str = "deterministic-placeholder/1"
    fingerprint: str = ""


@dataclass(frozen=True, slots=True)
class UpdateRecord:
    state: UpdateState
    active_slot: Slot
    pending_slot: Slot | None
    package_id: str | None
    reason: str
    fingerprint: str = ""


class SecureUpdateManager:
    def __init__(self):
        self.record = UpdateRecord(UpdateState.IDLE, Slot.A, None, None, "initial")

    def validate(self, package: UpdatePackage):
        valid = (
            package.manifest.digest == package.expected_digest
            and package.signature_scheme == "deterministic-placeholder/1"
        )
        self.record = self._record(
            UpdateState.VALIDATED if valid else UpdateState.REJECTED,
            None,
            package.package_id,
            "manifest verified" if valid else "digest/signature contract mismatch",
        )
        return valid

    def stage(self, package: UpdatePackage):
        if self.record.state != UpdateState.VALIDATED:
            raise ValueError("validated package required")
        target = Slot.B if self.record.active_slot == Slot.A else Slot.A
        self.record = self._record(
            UpdateState.STAGED, target, package.package_id, "inactive slot staged"
        )

    def request_boot(self):
        if self.record.state != UpdateState.STAGED:
            raise ValueError("staged update required")
        self.record = self._record(
            UpdateState.BOOT_PENDING,
            self.record.pending_slot,
            self.record.package_id,
            "awaiting health confirmation",
        )

    def confirm_boot(self, healthy: bool):
        if self.record.state != UpdateState.BOOT_PENDING:
            raise ValueError("boot confirmation required")
        if healthy:
            self.record = self._record(
                UpdateState.CONFIRMED,
                None,
                self.record.package_id,
                "new slot healthy",
                active=self.record.pending_slot,
            )
        else:
            self.record = self._record(
                UpdateState.ROLLED_BACK,
                None,
                self.record.package_id,
                "health check failed; retained prior slot",
            )

    def _record(self, state, pending, package, reason, active=None):
        r = UpdateRecord(state, active or self.record.active_slot, pending, package, reason)
        return replace(r, fingerprint=_digest(r))


def build_manifest(version: str = "0.1.0") -> ImageManifest:
    m = ImageManifest(
        "mars-ai-os",
        version,
        "debian-minimal-contract/1",
        "x86_64",
        ("python3", "systemd", "mars-ai-os"),
        "configuration-placeholder",
        13,
    )
    return replace(m, digest=_digest(m))
