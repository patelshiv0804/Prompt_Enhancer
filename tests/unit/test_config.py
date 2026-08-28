"""Unit tests for app/core/config.py.

The interesting behaviour here is ``_enforce_production_security``, which is the
only thing standing between a careless deploy and an authentication bypass. Each
test builds a *fresh* ``Settings`` instance rather than touching the module
singleton, so nothing leaks into the rest of the suite.

Every field the validator reads is passed explicitly. ``Settings`` also loads
``.env`` (``model_config``), and constructor kwargs win over it — being explicit
keeps these tests identical in CI, where no ``.env`` exists.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.core.config import _WEAK_SECRET_KEYS, Settings, get_settings, settings

pytestmark = pytest.mark.unit

STRONG_KEY = "b8f2c1d47e9a4f6b8c3e5d7a9b1c3e5f7a9b1c3e5d7f9a1b"  # 48 chars
assert len(STRONG_KEY) >= 32, "the fixture key must itself satisfy the rule"

BASE = {
    "database_url": "postgresql+asyncpg://user:pass@localhost:5432/unit_test",
    "enable_dev_auth_bypass": False,
    "secret_key": STRONG_KEY,
}


def build(**overrides: object) -> Settings:
    return Settings(**{**BASE, **overrides})  # type: ignore[arg-type]


# ─────────────────────────────────────────────────────────────────────────────
# The production guard
# ─────────────────────────────────────────────────────────────────────────────


def test_production_accepts_a_strong_configuration() -> None:
    config = build(environment="production")

    assert config.environment == "production"
    assert config.enable_dev_auth_bypass is False


def test_production_rejects_the_dev_auth_bypass() -> None:
    with pytest.raises(ValidationError, match="enable_dev_auth_bypass must be False"):
        build(environment="production", enable_dev_auth_bypass=True)


@pytest.mark.parametrize("weak", sorted(_WEAK_SECRET_KEYS))
def test_production_rejects_every_known_weak_secret(weak: str) -> None:
    """Parametrised over the real set, so a newly-added entry is covered here too."""
    with pytest.raises(ValidationError, match="secret_key must be a strong"):
        build(environment="production", secret_key=weak)


def test_the_default_secret_key_is_one_of_the_rejected_values() -> None:
    """The out-of-the-box default must not be deployable.

    ``secret_key`` has a placeholder default so local development works with no
    ``.env`` at all; that is only safe if production refuses it.
    """
    assert Settings.model_fields["secret_key"].default in _WEAK_SECRET_KEYS


@pytest.mark.parametrize("length", [0, 1, 31])
def test_production_rejects_short_secrets(length: int) -> None:
    with pytest.raises(ValidationError, match=">=32 chars"):
        build(environment="production", secret_key="x" * length)


def test_a_32_char_secret_is_the_boundary() -> None:
    """The check is ``len < 32``, so exactly 32 is accepted."""
    config = build(environment="production", secret_key="y" * 32)

    assert len(config.secret_key) == 32


@pytest.mark.parametrize("environment", ["development", "staging", "test", ""])
def test_non_production_environments_are_not_guarded(environment: str) -> None:
    """Deliberate asymmetry, and a trap worth naming.

    The guard keys off the exact string ``"production"``. A deployment labelled
    ``prod``, ``Production`` or ``live`` gets no protection at all, so the value
    is effectively load-bearing configuration.
    """
    config = build(
        environment=environment,
        enable_dev_auth_bypass=True,
        secret_key="changeme",
    )

    assert config.enable_dev_auth_bypass is True


def test_environment_matching_is_case_sensitive() -> None:
    """Same trap as above, stated as its own case because it is the likely typo."""
    config = build(environment="Production", enable_dev_auth_bypass=True)

    assert config.enable_dev_auth_bypass is True


# ─────────────────────────────────────────────────────────────────────────────
# Derived properties
# ─────────────────────────────────────────────────────────────────────────────


def test_cookie_secure_only_in_production() -> None:
    assert build(environment="production").COOKIE_SECURE is True
    assert build(environment="development").COOKIE_SECURE is False


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("http://a.test", ["http://a.test"]),
        ("http://a.test,http://b.test", ["http://a.test", "http://b.test"]),
        ("  http://a.test , http://b.test  ", ["http://a.test", "http://b.test"]),
        ("http://a.test,,http://b.test", ["http://a.test", "http://b.test"]),
        ("", []),
        (",", []),
    ],
    ids=["single", "pair", "padded", "empty-item", "empty", "only-separator"],
)
def test_cors_origins_parsing(raw: str, expected: list[str]) -> None:
    assert build(cors_origins=raw).CORS_ORIGINS == expected


def test_cors_origin_regex_is_none_when_unset() -> None:
    """CORSMiddleware treats ``None`` and ``""`` differently — ``""`` would match
    nothing while still enabling the regex path."""
    assert build(cors_origin_regex="").CORS_ORIGIN_REGEX is None
    assert build(cors_origin_regex="chrome-extension://.*").CORS_ORIGIN_REGEX == (
        "chrome-extension://.*"
    )


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("id-one", ["id-one"]),
        ("id-one, id-two", ["id-one", "id-two"]),
        ("", []),
    ],
)
def test_google_client_ids_parsing(raw: str, expected: list[str]) -> None:
    config = build(google_client_id=raw)

    assert config.GOOGLE_CLIENT_IDS == expected
    assert config.GOOGLE_CLIENT_ID == raw


def test_uppercase_aliases_mirror_their_fields() -> None:
    """``app/core/security.py`` reads the uppercase names; jose needs them."""
    config = build(secret_key=STRONG_KEY, algorithm="HS512", access_token_expire_minutes=15)

    assert config.SECRET_KEY == STRONG_KEY
    assert config.ALGORITHM == "HS512"
    assert config.ACCESS_TOKEN_EXPIRE_MINUTES == 15


# ─────────────────────────────────────────────────────────────────────────────
# The singleton
# ─────────────────────────────────────────────────────────────────────────────


def test_get_settings_returns_the_module_singleton() -> None:
    """Not a factory — identity is what makes the conftest's rewrite of
    ``settings.database_url`` visible to every module that already imported it."""
    assert get_settings() is settings
    assert get_settings() is get_settings()


def test_unknown_environment_variables_are_ignored() -> None:
    """``extra="ignore"``: this is why ``.env``'s ``TEST_DATABASE_URL`` never
    reaches ``Settings`` and the conftest has to resolve it itself."""
    config = Settings(**BASE, some_unknown_setting="x")  # type: ignore[arg-type]

    assert not hasattr(config, "some_unknown_setting")
