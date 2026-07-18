from __future__ import annotations

import pytest

from mars_ai_os.config import Settings


def test_settings_load_namespaced_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MARS_AI_ENV", "test")
    monkeypatch.setenv("MARS_AI_LOG_LEVEL", "debug")
    monkeypatch.setenv("MARS_AI_EVIDENCE_REQUIRED", "yes")

    settings = Settings.from_environment()

    assert settings.environment == "test"
    assert settings.log_level == "DEBUG"
    assert settings.evidence_required is True


def test_settings_reject_invalid_boolean(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MARS_AI_EVIDENCE_REQUIRED", "maybe")

    with pytest.raises(ValueError, match="Invalid boolean"):
        Settings.from_environment()

