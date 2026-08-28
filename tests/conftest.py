"""Backend test harness.

Authored from scratch. The suite it replaces pointed ``settings.database_url`` at
the live development database and cleaned up with
``DELETE FROM templates WHERE title LIKE '%Test%'``; that is the specific failure
mode every design decision below is guarding against.

FOUR THINGS THIS FILE GUARANTEES
--------------------------------
1. **Nothing ever touches the dev database.** ``settings.database_url`` is
   rewritten to the ``_test`` database at *import time*, before any application
   module has a chance to build an engine from it. Three guards refuse to run at
   all if that URL resolves to the dev database name or to a name that does not
   end in ``_test``.

2. **Every test is rolled back.** Each test runs inside an outer transaction
   that is never committed. ``get_async_session`` — which calls
   ``session.commit()`` on the way out ([app/db/session.py:37]) — is overridden
   with a session bound in ``join_transaction_mode="create_savepoint"``, so that
   commit releases a savepoint instead of ending the outer transaction. Rows the
   API writes are therefore visible to the test that wrote them and gone by the
   next one. No cleanup queries, no ordering dependencies.

3. **No network, no model weights.** ``get_llm_provider`` and
   ``get_embedding_service`` are replaced through ``dependency_overrides``, which
   reaches the whole graph because every service in ``app/api/v1/deps.py`` is
   ``Depends``-injected. Nine places construct ``EmbeddingService()`` or
   ``MistralProvider()`` directly and so bypass DI entirely (module-level
   singletons in ``app/api/v1/prompt_versions.py``, the ``or EmbeddingService()``
   constructor defaults in five services, and the background task at
   [app/api/v1/enhancement.py:172]); those are covered by a second, narrower
   safety net that points the real classes' methods at the *same* stub objects.
   The net is a backstop, not the mechanism: it forwards to the stubs rather than
   reimplementing behaviour, so there is one definition of what the fake LLM does.

4. **Rate limits cannot cause phantom failures.** The global
   ``RateLimitMiddleware`` (300/60s) is registered inside ``create_app()`` only
   when ``settings.rate_limit_enabled``, so that flag is cleared here before the
   app is built. The two route-level limiters — ``sensitive_rate_limiter``
   (5/60s, guards login) and ``llm_rate_limiter`` (20/60s, guards enhance) — are
   overridden to no-ops. Under ASGI transport every request reports the same
   client IP, so without this the 6th login test and the 21st enhance test would
   fail for reasons that have nothing to do with the code under test. Tests that
   assert limiter behaviour request the ``rate_limits_enforced`` fixture.

WHAT THE CLONED DATA IS AND IS NOT FOR
--------------------------------------
The test database is a clone of dev (``scripts/bootstrap_test_db.sh clone``), so
it holds ~170 templates with real MiniLM embeddings. Read them to exercise
pgvector over a realistic corpus, but assert only invariants — never a row count
or a fixed id, because that data drifts every time someone uses the dev app.
Anything a test asserts on precisely, it should create itself via
``tests.factories``.
"""

from __future__ import annotations

# ─────────────────────────────────────────────────────────────────────────────
# PHASE 1 — reconfigure settings before the application reads them.
#
# app/db/session.py builds its engine at import time from settings.database_url,
# and app/main.py calls create_app() at import time. Both therefore have to
# observe the values set here, which means this block must come before any
# `from app...` import other than the config module itself. Import order in this
# file is load-bearing; the isort/ruff directives keep a formatter from
# "tidying" it into a broken state.
# ─────────────────────────────────────────────────────────────────────────────
import os  # noqa: E402
from typing import AsyncIterator, Iterator, Optional  # noqa: E402

from sqlalchemy.engine import make_url  # noqa: E402

from app.core.config import settings  # noqa: E402


def _resolve_test_database_url() -> str:
    """Derive the test database URL and refuse anything that isn't obviously one.

    ``TEST_DATABASE_URL`` is honoured only when exported into the real
    environment. The value in ``.env`` is deliberately *not* used: pydantic drops
    it (it is not a Settings field), and it points at ``localhost``, which is
    wrong inside the container where the Postgres host is ``db``. Deriving from
    the live ``database_url`` instead means the test DB always sits beside the dev
    one, whatever the host.
    """
    dev_url = make_url(settings.database_url)
    dev_name = dev_url.database

    override = os.environ.get("TEST_DATABASE_URL")
    url = make_url(override) if override else dev_url.set(database=f"{dev_name}_test")

    name = url.database or ""
    if name == dev_name:
        raise RuntimeError(
            f"REFUSING TO RUN: the test database resolved to {name!r}, which is the "
            "development database. Tests would write to real data."
        )
    if not name.endswith("_test"):
        raise RuntimeError(
            f"REFUSING TO RUN: test database {name!r} does not end in '_test'. This "
            "guard is what stops a mistyped TEST_DATABASE_URL from destroying data."
        )
    return url.render_as_string(hide_password=False)


TEST_DATABASE_URL = _resolve_test_database_url()

# The single most important line in this file: from here on, anything that reads
# settings.database_url — the app's own engine, Alembic, the background task's
# deferred `from app.db.session import async_session` — gets the test database.
settings.database_url = TEST_DATABASE_URL

# Read by create_app(); must be false *before* the app object is constructed,
# because the middleware is added conditionally and cannot be removed afterwards.
settings.rate_limit_enabled = False

# Redis is a shared, out-of-transaction cache: the classification and embedding
# namespaces are keyed on prompt text, so a cached dev entry would silently
# answer a test's question (and a test's entry would pollute dev). Disabling it
# is a supported mode — every redis_client operation degrades to a miss, and
# auth_service keeps an in-memory OTP store for exactly this case.
settings.redis_enabled = False

# With the bypass on, an unauthenticated request resolves to a hardcoded dev
# profile instead of failing, which would quietly void every 401 assertion.
settings.enable_dev_auth_bypass = False

# ─────────────────────────────────────────────────────────────────────────────
# PHASE 2 — now it is safe to import the application.
# ─────────────────────────────────────────────────────────────────────────────
import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402
from fastapi import FastAPI  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy import select, text  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine  # noqa: E402
from sqlalchemy.pool import NullPool  # noqa: E402

from app.api.v1.deps import (  # noqa: E402
    get_embedding_service,
    get_llm_provider,
    get_session,
)
from app.core.security import create_access_token  # noqa: E402
from app.db.models import Template, User  # noqa: E402
from app.db.session import get_async_session  # noqa: E402
from app.main import create_app  # noqa: E402
from app.middleware.rate_limit import llm_rate_limiter, sensitive_rate_limiter  # noqa: E402
from app.services.embedding_service import EmbeddingService  # noqa: E402
from app.services.llm.mistral_provider import MistralProvider  # noqa: E402
from tests import factories  # noqa: E402
from tests.constants import ACCESS_COOKIE_NAME, TEST_USER_EMAIL  # noqa: E402
from tests.stubs.embedding import StubEmbeddingService  # noqa: E402
from tests.stubs.llm import StubLLMProvider  # noqa: E402

# httpx needs a host for the URL it never actually dials. The cookie jar matches
# on this exact name, so authed_client's cookie is scoped to it.
TEST_HOST = "testserver"
BASE_URL = f"http://{TEST_HOST}"


# ─────────────────────────────────────────────────────────────────────────────
# Database
# ─────────────────────────────────────────────────────────────────────────────


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def test_engine() -> AsyncIterator:
    """One engine for the whole session, with pooling switched off.

    NullPool because these connections are checked out and closed once per test:
    a pool would hold them open across the session and, at higher ``-n`` values
    under xdist, several workers' idle pools together can exhaust Postgres'
    ``max_connections``. Session-scoped because asyncpg connections are bound to
    the event loop that created them, and the loop here is session-scoped too.
    """
    engine = create_async_engine(
        TEST_DATABASE_URL,
        future=True,
        echo=False,
        poolclass=NullPool,
    )
    try:
        yield engine
    finally:
        await engine.dispose()


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def verify_test_database(test_engine) -> None:
    """Fail loudly, once, if the harness is aimed at the wrong database.

    The URL guards above check a *string*; this checks what the server actually
    connected to, which is the only claim that matters. It also states plainly
    whether the clone has been run, because "0 templates" otherwise shows up much
    later as a pile of confusing assertion failures.

    Pulled in by ``db_session`` rather than autouse on purpose: the unit tier must
    be able to run with no database reachable at all (that is what makes it usable
    as a fast pre-DB CI job), and an autouse session fixture would connect even
    for tests that never touch Postgres.
    """
    async with test_engine.connect() as conn:
        db_name = await conn.scalar(text("SELECT current_database()"))
        if not str(db_name).endswith("_test"):
            raise RuntimeError(
                f"Connected to database {db_name!r}, which is not a test database."
            )

        has_vector = await conn.scalar(
            text("SELECT 1 FROM pg_extension WHERE extname = :ext"),
            {"ext": settings.pgvector_extension},
        )
        if not has_vector:
            raise RuntimeError(
                f"The '{settings.pgvector_extension}' extension is missing from "
                f"{db_name}. Run scripts/bootstrap_test_db.sh."
            )

        template_count = await conn.scalar(text("SELECT count(*) FROM templates"))
        if not template_count:
            raise RuntimeError(
                f"{db_name} has no templates. Run scripts/bootstrap_test_db.sh clone "
                "to copy the development data across."
            )


@pytest_asyncio.fixture(loop_scope="session")
async def db_session(test_engine, verify_test_database) -> AsyncIterator[AsyncSession]:
    """A session whose every write is discarded when the test ends.

    The mechanism: open a connection, begin a transaction on it, and bind the
    session to that *connection* rather than the engine. ``create_savepoint``
    makes the session's own ``commit()`` calls — its own, the repositories', and
    the one inside ``get_async_session`` — release a SAVEPOINT instead of
    committing, so the outer transaction stays open and the final rollback undoes
    everything, including anything the API wrote.
    """
    conn = await test_engine.connect()
    trans = await conn.begin()
    session = AsyncSession(
        bind=conn,
        expire_on_commit=False,
        join_transaction_mode="create_savepoint",
    )
    try:
        yield session
    finally:
        await session.close()
        if trans.is_active:
            await trans.rollback()
        await conn.close()


# ─────────────────────────────────────────────────────────────────────────────
# Stubs for the two external dependencies
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture
def stub_llm() -> StubLLMProvider:
    """The fake LLM. Fresh per test, so recorded calls belong to one test only."""
    return StubLLMProvider()


@pytest.fixture
def stub_embedding() -> StubEmbeddingService:
    return StubEmbeddingService()


def _async_forward(target, name: str):
    """Bound-method shim: drops ``self`` and forwards to the stub instance."""

    def forward(_self, *args, **kwargs):
        return getattr(target, name)(*args, **kwargs)

    return forward


def _patch_llm_class(monkeypatch: pytest.MonkeyPatch, stub: StubLLMProvider) -> None:
    # __init__ is neutralised so constructing a provider never needs a real API
    # key — which is what lets the unit tier run in CI with no secrets at all.
    def _init(self, *_args, **_kwargs) -> None:
        self.model = "stub-model"
        self.api_key = "stub-key"

    monkeypatch.setattr(MistralProvider, "__init__", _init)
    for name in (
        "analyze_prompt",
        "optimize_prompt",
        "optimize_prompt_stream",
        "generate",
        "health_check",
    ):
        monkeypatch.setattr(MistralProvider, name, _async_forward(stub, name))


def _patch_embedding_class(
    monkeypatch: pytest.MonkeyPatch, stub: StubEmbeddingService
) -> None:
    def _no_real_model(_self):
        raise AssertionError(
            "EmbeddingService.model was accessed, which loads the real "
            "sentence-transformers weights. If that is intended, request the "
            "real_embedding_service fixture and mark the test slow."
        )

    monkeypatch.setattr(EmbeddingService, "model", property(_no_real_model))
    for name in (
        "generate",
        "generate_for_prompt",
        "generate_async",
        "generate_for_prompt_async",
        "generate_for_prompt_cached",
        "normalize",
    ):
        monkeypatch.setattr(EmbeddingService, name, _async_forward(stub, name))


@pytest.fixture(autouse=True)
def guard_bypass_paths(
    request: pytest.FixtureRequest,
    monkeypatch: pytest.MonkeyPatch,
    stub_llm: StubLLMProvider,
    stub_embedding: StubEmbeddingService,
) -> None:
    """Cover the call sites that construct providers directly, bypassing DI.

    ``dependency_overrides`` only reaches things FastAPI resolves. It does not
    reach the module-level singletons in ``app/api/v1/prompt_versions.py``, the
    ``embedding_service or EmbeddingService()`` fallbacks in five services, or
    the background task at [app/api/v1/enhancement.py:172] — each of which would
    otherwise open a real HTTP connection or load 90 MB of model weights. Patching
    the classes' *methods* (not their construction) catches all of them at once,
    whichever module namespace holds the imported name.
    """
    _patch_llm_class(monkeypatch, stub_llm)
    # A test that opts into real embeddings needs the genuine class methods, so
    # skip that half of the net for it. The LLM half always stays on: there is no
    # scenario in this suite where calling Mistral for real is correct.
    if "real_embedding_service" not in request.fixturenames:
        _patch_embedding_class(monkeypatch, stub_embedding)


@pytest.fixture
def real_embedding_service(request: pytest.FixtureRequest, app: FastAPI):
    """The genuine MiniLM encoder, for tests that assert on *semantic* quality.

    Needed because stub vectors are lexical hashes with no relationship to the
    real embeddings stored on the cloned templates — similarity between the two
    is noise. Loading the model costs seconds and ~90 MB, so the marker is
    mandatory rather than advisory: ``-m "not slow"`` must be able to skip it.
    """
    if request.node.get_closest_marker("slow") is None:
        pytest.fail(
            "real_embedding_service loads the sentence-transformers model. Mark "
            "the test with @pytest.mark.slow so the fast tier can exclude it."
        )
    service = EmbeddingService()
    app.dependency_overrides[get_embedding_service] = lambda: service
    return service


# ─────────────────────────────────────────────────────────────────────────────
# Application
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture(scope="session")
def app_instance() -> FastAPI:
    """Built once. ``create_app()`` calls ``setup_logging()`` and registers
    middleware, neither of which should be repeated hundreds of times; the only
    per-test state is ``dependency_overrides``, and that is a plain dict on the
    instance, cleared and repopulated by the ``app`` fixture below.
    """
    return create_app()


@pytest.fixture
def app(
    app_instance: FastAPI,
    db_session: AsyncSession,
    stub_llm: StubLLMProvider,
    stub_embedding: StubEmbeddingService,
) -> AsyncIterator[FastAPI]:
    async def _override_session() -> AsyncIterator[AsyncSession]:
        # Mirrors app/db/session.py deliberately, commit included: with
        # create_savepoint that commit is a savepoint release, so keeping it means
        # the code under test runs against the same transaction semantics it sees
        # in production instead of a subtly different no-commit variant.
        try:
            yield db_session
            await db_session.commit()
        except Exception:
            await db_session.rollback()
            raise

    overrides = {
        get_async_session: _override_session,
        # ``get_session`` is a one-line wrapper that just returns whatever
        # ``get_async_session`` yielded, so overriding it has to supply the *same*
        # generator rather than the bare session. A plain ``lambda: db_session``
        # would give the ~20 routes that depend on it directly (all of
        # ``templates``, ``ai_models``, the password-reset endpoints) a dependency
        # with no teardown — no commit on success and, worse, no rollback on
        # failure. A route that swallows an ``IntegrityError`` and converts it to
        # a 400 would then hand the *test* a session stuck in
        # ``PendingRollbackError``, so the follow-up "and the row was not created"
        # assertion would blow up instead of running. Using the generator here
        # gives those routes production semantics.
        get_session: _override_session,
        get_llm_provider: lambda: stub_llm,
        get_embedding_service: lambda: stub_embedding,
        # Both limiters key on (path, client IP), and ASGI transport reports one
        # IP for the entire suite. See the module docstring.
        sensitive_rate_limiter: lambda: None,
        llm_rate_limiter: lambda: None,
    }
    app_instance.dependency_overrides.clear()
    app_instance.dependency_overrides.update(overrides)
    try:
        yield app_instance
    finally:
        app_instance.dependency_overrides.clear()


@pytest.fixture
def rate_limits_enforced(app: FastAPI) -> Iterator[FastAPI]:
    """Restore the real route limiters, for the tests that assert 429.

    Both limiters are module-level singletons holding a ``defaultdict(list)`` of
    ``(path, client IP) -> timestamps``, and every request in the suite arrives
    from the same ASGI client address. Without clearing that dict a test which
    deliberately burns the 5/60s login budget would leave the bucket full for a
    full minute of wall-clock — so the next test to ask for real limiters would
    get a 429 on its first request. Clearing on the way in *and* out keeps these
    tests order-independent and leaves no residue for anything that follows.

    ``llm_rate_limiter`` is Redis-backed, but the suite runs with
    ``redis_enabled=False``, so ``incr_fixed_window`` returns ``None`` and it
    enforces through its in-process ``_local`` fallback — that is the dict to
    clear.
    """
    app.dependency_overrides.pop(sensitive_rate_limiter, None)
    app.dependency_overrides.pop(llm_rate_limiter, None)
    sensitive_rate_limiter._hits.clear()
    llm_rate_limiter._local._hits.clear()
    try:
        yield app
    finally:
        sensitive_rate_limiter._hits.clear()
        llm_rate_limiter._local._hits.clear()


def _transport(app: FastAPI) -> ASGITransport:
    """The ASGI transport both clients use, with app exceptions **not** re-raised.

    ``raise_app_exceptions=False`` is not a way of hiding failures — it is what
    makes the test client behave like uvicorn does in production, and without it
    most of the auth error paths are untestable.

    ``app/main.py`` registers exactly one handler: ``add_exception_handler(
    Exception, http_error_handler)``. Starlette installs a handler for bare
    ``Exception`` on ``ServerErrorMiddleware``, which is the outermost layer, and
    that layer *sends the response and then re-raises* so the ASGI server can log
    the failure. So the four application exceptions that reach it —
    ``AlreadyExistsException`` (400), ``InvalidOTPException`` (400),
    ``NotFoundException`` (404) and ``UnauthorizedException`` (401) — produce a
    correct JSON response **and** propagate.

    httpx's ``ASGITransport`` defaults to ``raise_app_exceptions=True``, so that
    re-raise surfaces inside ``await client.post(...)`` instead of returning the
    response the app already sent. Verified: registering a duplicate email raises
    ``AlreadyExistsException`` out of the call, while the same request with this
    flag off returns ``400 {"detail": "User with this email"}`` — byte-identical
    to what a browser gets. Every "wrong password → 401", "duplicate email → 400"
    and "unknown user → 404" assertion depends on this.

    ``HTTPException`` and ``RequestValidationError`` are unaffected either way:
    FastAPI's own defaults handle those inside ``ExceptionMiddleware``, which does
    not re-raise.

    Debuggability is preserved because ``http_error_handler`` calls
    ``logger.exception`` before returning, so the traceback still appears under
    pytest's "Captured log call" whenever a test fails.
    """
    return ASGITransport(app=app, raise_app_exceptions=False)


@pytest_asyncio.fixture(loop_scope="session")
async def client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    """Unauthenticated client.

    ASGI transport, so requests never leave the process. Note that it does not
    run lifespan events — the startup hook's ``verify_database_startup()`` and
    embedding-model warmup are therefore skipped, which is what we want.
    Starlette ``BackgroundTasks`` *do* still run.
    """
    async with AsyncClient(
        transport=_transport(app), base_url=BASE_URL
    ) as http_client:
        yield http_client


# ─────────────────────────────────────────────────────────────────────────────
# Authentication
# ─────────────────────────────────────────────────────────────────────────────


def token_for(user_id) -> str:
    """Mint an access token directly.

    Logging in would be more end-to-end, but ``/auth/login`` is capped at 5
    requests per minute per IP and the whole suite shares one IP, so the 6th test
    to log in would fail. The dedicated auth tests exercise the real endpoint;
    everything else uses this. ``sub`` must be the user UUID as a string — that is
    what both ``get_current_user`` and ``get_current_user_id`` decode.
    """
    return create_access_token({"sub": str(user_id)})


@pytest_asyncio.fixture(loop_scope="session")
async def account(db_session: AsyncSession) -> factories.Account:
    """A brand-new user + profile + settings, rolled back with the test.

    Fresh rather than the cloned ``test@promptiq.test`` account so that tests
    which mutate a user cannot interfere with each other, and so assertions about
    "this user's prompts" start from a genuinely empty list.
    """
    return await factories.create_account(db_session)


@pytest.fixture
def access_token(account: factories.Account) -> str:
    return token_for(account.id)


@pytest.fixture
def auth_headers(access_token: str) -> dict[str, str]:
    """Bearer-header auth, as an API client or Swagger would send it."""
    return {"Authorization": f"Bearer {access_token}"}


@pytest_asyncio.fixture(loop_scope="session")
async def authed_client(
    app: FastAPI, access_token: str
) -> AsyncIterator[AsyncClient]:
    """Cookie-authenticated client — the path the browser frontend actually uses.

    The cookie is sent as an explicit default header rather than through httpx's
    jar. ``http.cookiejar`` refuses to attach cookies to a dotless host like
    ``testserver`` (it does not look like a real domain), so ``cookies.set(...)``
    silently sends nothing and every request comes back 401. The server sees an
    identical ``Cookie:`` header either way, so ``request.cookies`` — which is
    what ``get_current_user`` and ``get_current_user_id`` read — is exercised
    exactly as in production.

    Tests that need real ``Set-Cookie`` lifecycle behaviour (login writing the
    cookie, logout clearing it) should use the plain ``client`` fixture and let
    httpx's jar handle what the server sends back.
    """
    async with AsyncClient(
        transport=_transport(app),
        base_url=BASE_URL,
        headers={"Cookie": f"{ACCESS_COOKIE_NAME}={access_token}"},
    ) as http_client:
        yield http_client


@pytest_asyncio.fixture(loop_scope="session")
async def bootstrap_user(db_session: AsyncSession) -> User:
    """The committed ``test@promptiq.test`` row, whose password we know.

    Cloned accounts carry bcrypt hashes of unknown plaintext, so none of them can
    log in; ``scripts/ensure_test_user.py`` upserts this one for the tests that
    need a real ``/auth/login`` round-trip. It lives outside the test transaction,
    so treat it as read-only — mutating it leaks across tests.
    """
    user = await db_session.scalar(select(User).where(User.email == TEST_USER_EMAIL))
    if user is None:
        pytest.fail(
            f"{TEST_USER_EMAIL} is missing from the test database. Run "
            "scripts/bootstrap_test_db.sh (it calls scripts/ensure_test_user.py)."
        )
    return user


# ─────────────────────────────────────────────────────────────────────────────
# Convenience
# ─────────────────────────────────────────────────────────────────────────────


@pytest_asyncio.fixture(loop_scope="session")
async def cloned_template(db_session: AsyncSession) -> Optional[Template]:
    """An arbitrary approved template from the cloned corpus, with a real vector.

    For exercising retrieval against realistic data. Which row comes back is not
    guaranteed and must not be asserted on — take its ``role``/``mode`` and use
    those, rather than its id.
    """
    return await db_session.scalar(
        select(Template)
        .where(Template.is_approved.is_(True), Template.embedding.isnot(None))
        .limit(1)
    )
