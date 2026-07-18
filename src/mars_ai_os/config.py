"""Environment-backed runtime configuration."""

from __future__ import annotations

from dataclasses import dataclass
from os import environ


@dataclass(frozen=True, slots=True)
class Settings:
    """Small, explicit configuration surface for the base runtime."""

    environment: str = "development"
    log_level: str = "INFO"
    evidence_required: bool = True

    @classmethod
    def from_environment(cls) -> Settings:
        """Load supported settings without leaking unrelated environment values."""

        return cls(
            environment=environ.get("MARS_AI_ENV", "development"),
            log_level=environ.get("MARS_AI_LOG_LEVEL", "INFO").upper(),
            evidence_required=_as_bool(environ.get("MARS_AI_EVIDENCE_REQUIRED", "true")),
        )


def _as_bool(value: str) -> bool:
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"Invalid boolean configuration value: {value!r}")
