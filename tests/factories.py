"""Row builders for the backend test suite.

WHY FACTORIES AT ALL
--------------------
The test database is a *clone of the dev database*, so it already contains 170
templates, 6 AI models and 5 accounts. Reaching for whatever
``select(AIModel).limit(1)`` happens to return couples the test to data nobody
controls: it changes whenever someone uses the dev app, and a failure then tells
you nothing about the code. Every test that asserts on a row should therefore
create that row itself.

The read-only exception is deliberate and narrow: tests may *read* cloned rows to
exercise pgvector similarity over a realistic corpus, but only ever assert
invariants ("at least one approved template came back", "results are ordered by
distance"), never counts or fixed IDs.

TWO LAYERS
----------
``make_*`` returns an unsaved instance — no session, no I/O — for unit tests and
for cases that want to tweak fields before insert.
``create_*`` persists and flushes, resolving foreign keys as needed, and is what
integration tests normally use.

Nothing here commits. The session handed in is bound to a transaction the
conftest rolls back, so ``flush`` is enough to make rows visible to the
application code under test while still guaranteeing they disappear afterwards.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID, uuid4

from sqlalchemy import select

# Plain SQLAlchemy AsyncSession, not sqlmodel's: every repository in app/ annotates
# and uses that one (no call site uses session.exec()), so the factories stay on
# the same type the code under test receives.
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.db.models import (
    AIModel,
    Profile,
    Prompt,
    PromptVersion,
    StyleProfile,
    Template,
    User,
    UserSettings,
)
from tests.constants import TEST_USER_PASSWORD
from tests.stubs.embedding import hashed_embedding

# ── Uniqueness ────────────────────────────────────────────────────────────
# A random suffix rather than a counter: pytest-xdist runs several worker
# processes against the same database, and a per-process counter would hand the
# same "user-1@..." to every worker and trip the unique index on profiles.email.


def unique_suffix() -> str:
    return uuid4().hex[:10]


def unique_email(prefix: str = "factory") -> str:
    """An address in a domain no cloned row uses, so it can never collide.

    The domain has to satisfy two constraints at once. It must not appear in the
    cloned dev data (real user emails), and it must survive ``pydantic.EmailStr``,
    because ``/auth/register``, ``/auth/forgot-password`` and
    ``/auth/verify-reset-otp`` validate their input with it.

    That rules out the obvious choices: ``email_validator`` rejects the whole of
    ``SPECIAL_USE_DOMAIN_NAMES`` — ``arpa``, ``invalid``, ``local``, ``localhost``,
    ``onion``, ``test`` — with "the part after the @-sign is a special-use or
    reserved name", so ``@factory.test`` and ``@harness.local`` come back as 422
    from every one of those endpoints. ``promptiq-tests.dev`` is a real TLD (and
    pydantic runs the validator with ``check_deliverability=False``, so no DNS
    lookup happens), which is why factory accounts can be driven through the
    public API rather than only inserted directly.

    ``test@promptiq.test`` — the bootstrap account — is the exception that proves
    the rule: it can still *log in*, because ``/auth/login`` takes an
    ``OAuth2PasswordRequestForm`` whose ``username`` is a plain ``str``.
    """
    return f"{prefix}-{unique_suffix()}@promptiq-tests.dev"


# bcrypt at the app's cost factor takes ~0.25 s per call. Nearly every account
# the factories build uses the same password, so hash it once per process.
_PASSWORD_HASH_CACHE: dict[str, str] = {}


def cached_hash(password: str) -> str:
    hashed = _PASSWORD_HASH_CACHE.get(password)
    if hashed is None:
        hashed = hash_password(password)
        _PASSWORD_HASH_CACHE[password] = hashed
    return hashed


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ── Unsaved builders ──────────────────────────────────────────────────────


def make_ai_model(**overrides: Any) -> AIModel:
    suffix = unique_suffix()
    fields: dict[str, Any] = {
        "provider": f"factory-{suffix}",
        "model_name": f"factory-model-{suffix}",
        "description": "Created by tests.factories.",
        "is_active": True,
        "supports_analysis": True,
        "supports_optimization": True,
    }
    fields.update(overrides)
    return AIModel(**fields)


def make_template(*, ai_model_id: UUID, **overrides: Any) -> Template:
    suffix = unique_suffix()
    body = overrides.pop(
        "body",
        "You are a {{role}} working in {{mode}} mode.\nTask: {{prompt}}",
    )
    fields: dict[str, Any] = {
        "title": f"Factory Template {suffix}",
        "description": "Created by tests.factories.",
        "body": body,
        "mode": "general",
        "category": "general",
        "role": "creator",
        "ai_model_id": ai_model_id,
        "tags": ["factory"],
        # A real 384-dim unit vector, so pgvector's cosine operator and the HNSW
        # index treat this row exactly like a seeded one. Derived from the body,
        # so a test can craft a query with deliberate lexical overlap.
        "embedding": hashed_embedding(body),
        "is_featured": False,
        "is_approved": True,
        "use_count": 0,
    }
    fields.update(overrides)
    return Template(**fields)


def make_user(*, password: str = TEST_USER_PASSWORD, **overrides: Any) -> User:
    fields: dict[str, Any] = {
        "email": overrides.pop("email", unique_email("user")),
        "hashed_password": overrides.pop("hashed_password", cached_hash(password)),
        "auth_provider": "local",
        "is_active": True,
        "is_verified": True,
    }
    fields.update(overrides)
    return User(**fields)


def make_profile(*, id: UUID, email: str, **overrides: Any) -> Profile:
    """``profiles.id`` is both the primary key and a FK to ``users.id``.

    The two tables share one identifier, so the ``User`` must exist (or be
    flushed in the same unit of work) before the profile is inserted.
    """
    fields: dict[str, Any] = {
        "id": id,
        "email": email,
        "full_name": "Factory User",
        "display_name": "factory",
        "is_active": True,
        "plan": "free",
        "role": "creator",
        "onboarding_completed": True,
    }
    fields.update(overrides)
    return Profile(**fields)


def make_user_settings(*, profile_id: UUID, **overrides: Any) -> UserSettings:
    # Named user_id on the model, but the FK targets profiles.id.
    fields: dict[str, Any] = {"user_id": profile_id}
    fields.update(overrides)
    return UserSettings(**fields)


def make_prompt(*, user_id: UUID, **overrides: Any) -> Prompt:
    original = overrides.pop("original_prompt", "write a blog post about testing")
    fields: dict[str, Any] = {
        "user_id": user_id,
        "title": f"Factory Prompt {unique_suffix()}",
        "original_prompt": original,
        "embedding": hashed_embedding(original),
    }
    fields.update(overrides)
    return Prompt(**fields)


def make_prompt_version(*, prompt_id: UUID, **overrides: Any) -> PromptVersion:
    fields: dict[str, Any] = {
        "prompt_id": prompt_id,
        "version_number": 1,
        "version_type": "enhanced",
        "content": "You are an expert assistant.\nObjective: factory version body.",
        "change_summary": "Created by tests.factories.",
    }
    fields.update(overrides)
    return PromptVersion(**fields)


def make_style_profile(*, user_id: UUID, **overrides: Any) -> StyleProfile:
    fields: dict[str, Any] = {
        "user_id": user_id,
        "name": f"Factory Style {unique_suffix()}",
        # The table has a CHECK constraint limiting type to five values; anything
        # else fails at insert with a constraint violation.
        "type": "brand_voice",
        "attributes": {"tone": "direct", "source": "tests.factories"},
        "injection_template": "Write in a {{tone}} voice.",
        "is_active": True,
        "use_count": 0,
    }
    fields.update(overrides)
    return StyleProfile(**fields)


# ── Persisting helpers ────────────────────────────────────────────────────


@dataclass
class Account:
    """The three rows that together make one usable login.

    ``user`` authenticates, ``profile`` owns content (prompts FK to
    ``profiles.id``), ``settings`` backs the preferences endpoints. They share
    one UUID, which is also the ``sub`` claim in the access token.

    ``id`` and ``email`` are captured as plain values rather than read through
    ``user``, because the ORM instance is **expired** after any request whose
    handler rolled back — and rolling back is exactly what the error paths do. A
    ``@property`` returning ``self.user.email`` would then need a database round
    trip to answer, from synchronous attribute-access context, and raise
    ``MissingGreenlet`` instead of the value the test wanted. Tests that need the
    *current* database state still have ``user``/``profile``/``settings`` and can
    ``await db_session.refresh(...)``; tests that just want "the address I
    registered" get it unconditionally.
    """

    user: User
    profile: Profile
    settings: UserSettings
    password: str
    id: UUID
    email: str


async def create_ai_model(session: AsyncSession, **overrides: Any) -> AIModel:
    model = make_ai_model(**overrides)
    session.add(model)
    await session.flush()
    return model


async def create_template(
    session: AsyncSession,
    *,
    ai_model: Optional[AIModel] = None,
    **overrides: Any,
) -> Template:
    """``templates.ai_model_id`` is NOT NULL, so create a model if none is given."""
    if ai_model is None and "ai_model_id" not in overrides:
        ai_model = await create_ai_model(session)
    ai_model_id = overrides.pop("ai_model_id", None) or ai_model.id  # type: ignore[union-attr]
    template = make_template(ai_model_id=ai_model_id, **overrides)
    session.add(template)
    await session.flush()
    return template


async def create_account(
    session: AsyncSession,
    *,
    password: str = TEST_USER_PASSWORD,
    profile_overrides: Optional[dict[str, Any]] = None,
    **user_overrides: Any,
) -> Account:
    user = make_user(password=password, **user_overrides)
    session.add(user)
    # Flush before building the profile: profiles.id is a FK to users.id, so the
    # user row has to be on the wire first even though the UUID is client-side.
    await session.flush()

    profile = make_profile(id=user.id, email=user.email, **(profile_overrides or {}))
    session.add(profile)
    await session.flush()

    settings_row = make_user_settings(profile_id=profile.id)
    session.add(settings_row)
    await session.flush()

    return Account(
        user=user,
        profile=profile,
        settings=settings_row,
        password=password,
        id=user.id,
        email=user.email,
    )


async def create_prompt(
    session: AsyncSession,
    *,
    account: Optional[Account] = None,
    user_id: Optional[UUID] = None,
    **overrides: Any,
) -> Prompt:
    # account.id, not account.profile.id: the two are the same UUID, but the
    # former is a plain value that survives an expired ORM instance.
    owner_id = user_id or (account.id if account else None)
    if owner_id is None:
        raise ValueError("create_prompt needs either account= or user_id=.")
    prompt = make_prompt(user_id=owner_id, **overrides)
    session.add(prompt)
    await session.flush()
    return prompt


async def create_prompt_version(
    session: AsyncSession,
    *,
    prompt: Prompt,
    set_current: bool = True,
    **overrides: Any,
) -> PromptVersion:
    """Append a version, numbering it after the highest existing one.

    ``(prompt_id, version_number)`` is unique, so a fixed ``version_number=1``
    would break the moment a test adds a second version.
    """
    if "version_number" not in overrides:
        highest = await session.scalar(
            select(PromptVersion.version_number)
            .where(PromptVersion.prompt_id == prompt.id)
            .order_by(PromptVersion.version_number.desc())
            .limit(1)
        )
        overrides["version_number"] = (highest or 0) + 1

    version = make_prompt_version(prompt_id=prompt.id, **overrides)
    session.add(version)
    await session.flush()

    if set_current:
        prompt.current_version_id = version.id
        session.add(prompt)
        await session.flush()
    return version


async def create_style_profile(
    session: AsyncSession,
    *,
    account: Optional[Account] = None,
    user_id: Optional[UUID] = None,
    **overrides: Any,
) -> StyleProfile:
    # style_profiles.user_id carries no foreign key, so an arbitrary UUID is
    # accepted here — pass a real account when the test asserts on ownership.
    owner_id = user_id or (account.id if account else uuid4())
    style = make_style_profile(user_id=owner_id, **overrides)
    session.add(style)
    await session.flush()
    return style
