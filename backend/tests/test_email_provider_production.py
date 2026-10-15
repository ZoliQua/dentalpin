"""Console email provider must be loud in production (#614).

`EMAIL_PROVIDER` defaults to `console`, which writes the whole message —
recipient, name, treatment, amount — to the application log and reports
`SUCCESS`, so the outbox marks it sent while the patient receives
nothing. Reaching that state in production is an omission, not a choice,
so it has to say so — and since the fail-closed boot guard, it cannot
even start there (see the boot-refusal tests at the bottom of this file).
"""

from __future__ import annotations

import logging

import pytest

from app.core.email.service import EmailService


def _resolve(monkeypatch, caplog, *, environment: str, provider: str = "console"):
    from app.config import settings as app_settings

    monkeypatch.setattr(app_settings, "ENVIRONMENT", environment)
    monkeypatch.setattr(app_settings, "EMAIL_PROVIDER", provider)
    monkeypatch.setattr(app_settings, "EMAIL_ENABLED", True)
    monkeypatch.setattr(app_settings, "TESTING", False)
    service = EmailService()
    with caplog.at_level(logging.INFO, logger="app.core.email.service"):
        service._initialize()
    return caplog.text


def test_console_in_production_logs_an_error(monkeypatch, caplog) -> None:
    text = _resolve(monkeypatch, caplog, environment="production")
    assert "EMAIL_PROVIDER=console in production" in text
    assert any(r.levelno >= logging.ERROR for r in caplog.records)


def test_console_in_development_stays_quiet(monkeypatch, caplog) -> None:
    text = _resolve(monkeypatch, caplog, environment="development")
    assert "in production" not in text
    assert not [r for r in caplog.records if r.levelno >= logging.ERROR]


def test_smtp_in_production_does_not_warn(monkeypatch, caplog) -> None:
    text = _resolve(monkeypatch, caplog, environment="production", provider="smtp")
    assert "EMAIL_PROVIDER=console in production" not in text


def test_env_example_documents_the_setting() -> None:
    """An operator cannot set what the example never mentions."""
    from pathlib import Path

    example = Path(__file__).resolve().parents[2] / ".env.example"
    body = example.read_text(encoding="utf-8")
    for key in ("EMAIL_PROVIDER", "EMAIL_ENABLED", "EMAIL_SMTP_HOST"):
        assert key in body, key


def _compose_env(path) -> set[str]:
    """Keys the backend service passes through, from a compose file."""
    import re

    body = path.read_text(encoding="utf-8")
    after = body.split("\n  backend:", 1)[1]
    # The next service starts at exactly two spaces + a name; anything more
    # indented still belongs to backend.
    nxt = re.search(r"^  \S", after, re.M)
    backend = after[: nxt.start()] if nxt else after
    return set(re.findall(r"^\s{6}([A-Z][A-Z0-9_]*):", backend, re.M))


@pytest.mark.parametrize("compose", ["docker-compose.prod.yml", "docker-compose.coolify.yml"])
def test_production_compose_forwards_every_email_setting(compose: str) -> None:
    """The remedy we print must be applicable where we print it.

    Neither prod compose file declares `env_file`, so a setting that is not
    listed under `environment:` never reaches the container. Telling an
    operator to set `EMAIL_PROVIDER=smtp` while the SMTP host, user and
    password stay at their defaults hands them a broken remedy (#614).
    """
    from pathlib import Path

    from app.config import Settings

    declared = {n for n in Settings.model_fields if n.startswith("EMAIL_")}
    forwarded = _compose_env(Path(__file__).resolve().parents[2] / compose)
    missing = sorted(declared - forwarded)
    assert not missing, f"{compose} does not forward: {missing}"


@pytest.mark.parametrize("compose", ["docker-compose.prod.yml", "docker-compose.coolify.yml"])
def test_boolean_email_settings_have_a_real_default(compose: str) -> None:
    """``${X:-}`` resolves to an empty string, which fails bool parsing at boot."""
    import re
    from pathlib import Path

    from app.config import Settings

    body = (Path(__file__).resolve().parents[2] / compose).read_text(encoding="utf-8")
    bools = {
        n
        for n, f in Settings.model_fields.items()
        if n.startswith("EMAIL_") and f.annotation is bool
    }
    for name in sorted(bools):
        m = re.search(rf"^\s+{name}: \$\{{{name}:-(.*?)\}}", body, re.M)
        assert m, f"{compose}: {name} not forwarded with a default"
        assert m.group(1) != "", f"{compose}: {name} defaults to empty, which fails bool parsing"


def _make_settings(**overrides):
    from app.config import MIN_SECRET_KEY_LENGTH, Settings

    kwargs = {
        "DATABASE_URL": "postgresql://user:pass@localhost/db",
        "SECRET_KEY": "a" * MIN_SECRET_KEY_LENGTH,
        "BUDGET_PUBLIC_SECRET_KEY": "a" * MIN_SECRET_KEY_LENGTH,
        "AGENDA_PUBLIC_SECRET_KEY": "a" * MIN_SECRET_KEY_LENGTH,
        "ENVIRONMENT": "development",
    }
    kwargs.update(overrides)
    return Settings(**kwargs)


def test_console_provider_in_production_refuses_to_boot():
    """Fail-closed: console logs PII while reporting delivery (#614)."""
    with pytest.raises(ValueError, match="EMAIL_PROVIDER='console' is not allowed"):
        _make_settings(ENVIRONMENT="production", EMAIL_PROVIDER="console")


def test_unknown_provider_in_production_refuses_to_boot():
    """Unknown falls back to console in the service — same hole, same refusal."""
    with pytest.raises(ValueError, match="EMAIL_PROVIDER='carrier-pigeon' is not allowed"):
        _make_settings(ENVIRONMENT="production", EMAIL_PROVIDER="carrier-pigeon")


def test_disabled_email_in_production_boots():
    """EMAIL_ENABLED=false is the legitimate no-mail opt-out."""
    settings = _make_settings(ENVIRONMENT="production", EMAIL_ENABLED=False)
    assert settings.EMAIL_ENABLED is False


def test_demo_mode_in_production_keeps_console():
    """The public demo carries only seeded fake data (maintainer-controlled)."""
    settings = _make_settings(ENVIRONMENT="production", DEMO_MODE=True)
    assert settings.EMAIL_PROVIDER == "console"


def test_smtp_provider_in_production_boots_clean():
    import warnings

    with warnings.catch_warnings():
        warnings.simplefilter("error")
        settings = _make_settings(ENVIRONMENT="production", EMAIL_PROVIDER="smtp")
    assert settings.EMAIL_PROVIDER == "smtp"


def test_console_provider_outside_production_boots_silently():
    """Console is the documented dev default — no warning noise on every boot."""
    import warnings

    with warnings.catch_warnings():
        warnings.simplefilter("error")
        settings = _make_settings(ENVIRONMENT="development")
    assert settings.EMAIL_PROVIDER == "console"
