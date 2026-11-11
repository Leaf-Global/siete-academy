"""Dev auth bypass defaults off and is refused outside development.

The request-path cases call `get_current_user` directly. The shared `client`
fixture replaces that dependency, so these tests use the `db` fixture only.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.core.config import Settings
from app.modules.auth.dependencies import get_current_user
from app.modules.users.models import User

ROOT = Path(__file__).resolve().parents[2]


def _seed_user(db, *, email: str) -> User:
    user = User(
        firebase_uid=f"uid-{email}",
        email=email,
        display_name="Dev Bypass",
        role="admin",
        locale="es",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _assert_header_rejected(monkeypatch, settings: Settings, db, email: str) -> None:
    """X-Dev-User must not authenticate. A seeded user makes a live bypass fail the test."""
    monkeypatch.setattr(
        "app.modules.auth.dependencies.get_settings",
        lambda: settings,
    )
    with pytest.raises(HTTPException) as exc:
        get_current_user(authorization=None, x_dev_user=email, db=db)
    assert exc.value.status_code == 401
    assert exc.value.detail == "Missing bearer token"


def test_dev_auth_bypass_defaults_off(db, monkeypatch):
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.delenv("DEV_AUTH_BYPASS", raising=False)

    assert Settings.model_fields["dev_auth_bypass"].default is False

    settings = Settings(_env_file=None)
    assert settings.app_env == "development"
    assert settings.dev_auth_bypass is False
    assert settings.dev_auth_bypass_active is False

    example_assignments = [
        line.strip()
        for line in (ROOT / ".env.example").read_text().splitlines()
        if line.strip().startswith("DEV_AUTH_BYPASS=")
    ]
    assert example_assignments == ["DEV_AUTH_BYPASS=false"]

    dockerfile = (ROOT / "backend" / "Dockerfile").read_text()
    assert "DEV_AUTH_BYPASS=false" in dockerfile
    assert "DEV_AUTH_BYPASS=true" not in dockerfile

    compose = (ROOT / "docker-compose.yml").read_text()
    assert compose.count("${DEV_AUTH_BYPASS:-false}") == 2

    user = _seed_user(db, email="default-off@test.dev")
    _assert_header_rejected(monkeypatch, settings, db, user.email)


@pytest.mark.parametrize("app_env", ["production", "staging"])
def test_dev_auth_bypass_refused_outside_development(db, monkeypatch, app_env):
    monkeypatch.setenv("APP_ENV", app_env)
    monkeypatch.setenv("DEV_AUTH_BYPASS", "true")
    with pytest.raises(ValidationError, match="DEV_AUTH_BYPASS"):
        Settings(_env_file=None)

    monkeypatch.setenv("DEV_AUTH_BYPASS", "false")
    safe = Settings(_env_file=None)
    assert safe.app_env == app_env
    assert safe.dev_auth_bypass is False
    assert safe.dev_auth_bypass_active is False

    # model_construct skips the startup validator. The request path still
    # has to ignore the header, including when the email belongs to a real user.
    forced = Settings.model_construct(app_env=app_env, dev_auth_bypass=True)
    assert forced.dev_auth_bypass is True
    assert forced.dev_auth_bypass_active is False
    user = _seed_user(db, email=f"{app_env}-bypass@test.dev")
    _assert_header_rejected(monkeypatch, forced, db, user.email)


def test_dev_auth_bypass_works_when_explicitly_enabled_in_development(db, monkeypatch):
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("DEV_AUTH_BYPASS", "true")
    settings = Settings(_env_file=None)
    assert settings.dev_auth_bypass is True
    assert settings.app_env == "development"
    assert settings.dev_auth_bypass_active is True

    user = _seed_user(db, email="dev-bypass@test.dev")
    monkeypatch.setattr(
        "app.modules.auth.dependencies.get_settings",
        lambda: settings,
    )
    current = get_current_user(authorization=None, x_dev_user=user.email, db=db)
    assert current.user.id == user.id
    assert current.user.email == user.email
    assert current.role == "admin"
    assert current.claims["_dev"] is True
