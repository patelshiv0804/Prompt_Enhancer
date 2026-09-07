"""Integration tier — real Postgres, real routing, stubbed LLM and embeddings.

Every test here goes through the ASGI app, so a failure implicates the route
handler, its schema, its service chain and its SQL together. The two things that
are *not* real are the Mistral client and the sentence-transformers model, both
replaced by deterministic stubs in ``tests/conftest.py``; everything downstream of
them — pgvector similarity, transactions, cascade deletes — runs for real against
the cloned database.

FIVE HOUSE RULES FOR THIS TIER
------------------------------
**1. Own the rows you assert on.** The database is a clone of the dev database, so
it already holds 170 templates, 6 AI models and 5 accounts, and those change
whenever someone uses the dev app. Assert on rows the test created, or on
invariants ("at least one approved template came back", "results are ordered by
distance") — never on counts or fixed ids from cloned data.

**2. ``commit()`` before a request you expect to fail.** The session is bound with
``join_transaction_mode="create_savepoint"``, so the app's own
``session.rollback()`` on the error path unwinds the current SAVEPOINT — which
includes anything the test flushed but has not yet released. A setup row created
with ``factories.create_*`` and left unflushed-to-savepoint therefore disappears
before the assertion can run. ``await db_session.commit()`` releases the savepoint
first, moving the setup rows into the outer transaction where only the per-test
rollback can touch them.

**3. Error paths need ``raise_app_exceptions=False``.** Already handled by the
``client``/``authed_client`` fixtures; see ``_transport`` in ``tests/conftest.py``
for why every non-``HTTPException`` error would otherwise be raised into the test
instead of returned as a response.

**4. After a request that failed, ORM instances are expired.** The session
dependency rolls back on the error path exactly as production does, and a rollback
expires every loaded object — so reading ``some_template.title`` afterwards is a
lazy database read issued from synchronous attribute-access context, which raises
``MissingGreenlet`` rather than returning the value. Either capture the scalars
you need into locals *before* the request (``factories.Account`` already exposes
``id`` and ``email`` this way, for precisely this reason), or
``await db_session.refresh(obj)`` before reading it again.

**5. ``expire_all()`` between a request that eager-loads a collection and a later
DELETE of its parent.** Production gives every request a fresh session; the
harness deliberately shares one, which makes one ORM behaviour visible that
production never hits. ``GET /prompts/{id}`` loads ``Prompt.versions`` via
``selectinload``, leaving the collection in the identity map. ``Prompt.versions``
is declared ``passive_deletes=True`` but *without* ``cascade="all, delete"`` —
and ``passive_deletes`` only stops SQLAlchemy from *loading* children in order to
disown them. An **already-loaded** collection is still disowned, so deleting the
prompt emits ``UPDATE prompt_versions SET prompt_id = NULL`` and trips the NOT
NULL constraint instead of letting the database's ``ON DELETE CASCADE`` run. The
result is a generic 400 from a DELETE that works perfectly in isolation. Call
``db_session.expire_all()`` between the two requests to model the fresh session
production would have used.
"""
