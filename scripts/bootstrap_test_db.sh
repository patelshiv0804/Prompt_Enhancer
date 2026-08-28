#!/usr/bin/env bash
#
# bootstrap_test_db.sh — build the dedicated test database.
#
#   ./scripts/bootstrap_test_db.sh clone     (default) copy the dev DB into it
#   ./scripts/bootstrap_test_db.sh migrate   build it from alembic + seed.py
#
# clone   — for local development. Dumps the live dev database and restores it
#           into <DEV_DB>_test, so tests run against real templates and their
#           real 384-dim embeddings. The dev database is only ever read.
#
# migrate — for CI, where no dev database exists. Creates the schema from
#           migrations and fills it with scripts/seed.py.
#
# WHY pg_dump AND NOT `CREATE DATABASE ... TEMPLATE`:
#   Postgres refuses a TEMPLATE copy while any other session is connected to the
#   source, and the web container holds a connection pool open against the dev
#   database. pg_dump has no such restriction.
#
# SAFETY: clone mode copies real user rows, including bcrypt password hashes.
#   Never run it against a database holding production data, and never in CI.
#   The dump is written inside the Postgres container's /tmp and removed after
#   the restore; nothing lands on the host.
#
set -euo pipefail

MODE="${1:-clone}"

PG_CONTAINER="${PG_CONTAINER:-promptiq-postgres}"
WEB_CONTAINER="${WEB_CONTAINER:-promptiq-web}"
PG_USER="${POSTGRES_USER:-postgres}"
DEV_DB="${POSTGRES_DB:-prompt_enhancer}"
TEST_DB="${TEST_DB:-${DEV_DB}_test}"
DUMP_PATH="/tmp/${DEV_DB}.bootstrap.dump"

if [[ "$TEST_DB" == "$DEV_DB" ]]; then
  echo "REFUSING: test database name is identical to the dev database ($DEV_DB)." >&2
  exit 1
fi

psql_postgres() { docker exec -i "$PG_CONTAINER" psql -v ON_ERROR_STOP=1 -U "$PG_USER" -d postgres "$@"; }
psql_test()     { docker exec -i "$PG_CONTAINER" psql -v ON_ERROR_STOP=1 -U "$PG_USER" -d "$TEST_DB" "$@"; }

echo "==> mode=$MODE  dev=$DEV_DB  test=$TEST_DB  container=$PG_CONTAINER"

# ── Recreate the test database ────────────────────────────────────────────
# Drop needs every other session gone, including sessions this script's own
# previous run left behind.
echo "==> dropping and recreating $TEST_DB"
psql_postgres -c "SELECT pg_terminate_backend(pid)
                  FROM pg_stat_activity
                  WHERE datname = '${TEST_DB}' AND pid <> pg_backend_pid();" >/dev/null
psql_postgres -c "DROP DATABASE IF EXISTS ${TEST_DB};"
psql_postgres -c "CREATE DATABASE ${TEST_DB} OWNER ${PG_USER};"

case "$MODE" in
  clone)
    echo "==> dumping $DEV_DB (read-only; dev stays online)"
    docker exec "$PG_CONTAINER" pg_dump \
      -U "$PG_USER" -d "$DEV_DB" \
      --format=custom --no-owner --no-privileges \
      --file="$DUMP_PATH"

    # The custom-format dump carries CREATE EXTENSION vector, every index
    # (including the HNSW vector indexes), the alembic_version row and all data.
    echo "==> restoring into $TEST_DB"
    docker exec "$PG_CONTAINER" pg_restore \
      -U "$PG_USER" -d "$TEST_DB" \
      --no-owner --no-privileges \
      "$DUMP_PATH"

    docker exec "$PG_CONTAINER" rm -f "$DUMP_PATH"
    ;;

  migrate)
    echo "==> creating pgvector extension"
    psql_test -c "CREATE EXTENSION IF NOT EXISTS vector;"

    echo "==> alembic upgrade head"
    docker exec -e DATABASE_URL="postgresql+asyncpg://${PG_USER}:${POSTGRES_PASSWORD:-admin}@db:5432/${TEST_DB}" \
      "$WEB_CONTAINER" python -m alembic upgrade head

    echo "==> seeding"
    docker exec -e DATABASE_URL="postgresql+asyncpg://${PG_USER}:${POSTGRES_PASSWORD:-admin}@db:5432/${TEST_DB}" \
      "$WEB_CONTAINER" python scripts/seed.py
    ;;

  *)
    echo "Unknown mode '$MODE'. Use 'clone' or 'migrate'." >&2
    exit 1
    ;;
esac

# ── A login-able account ──────────────────────────────────────────────────
# Cloned users carry bcrypt hashes whose plaintext is unknown, so none of them
# can authenticate. This adds one account with known credentials.
echo "==> ensuring the known test user"
docker exec -e DATABASE_URL="postgresql+asyncpg://${PG_USER}:${POSTGRES_PASSWORD:-admin}@db:5432/${TEST_DB}" \
  "$WEB_CONTAINER" python scripts/ensure_test_user.py

# ── Report ────────────────────────────────────────────────────────────────
echo "==> row counts in $TEST_DB"
psql_test -c "
SELECT 'templates' AS table, count(*) FROM templates
UNION ALL SELECT 'ai_models',       count(*) FROM ai_models
UNION ALL SELECT 'users',           count(*) FROM users
UNION ALL SELECT 'profiles',        count(*) FROM profiles
UNION ALL SELECT 'prompts',         count(*) FROM prompts
UNION ALL SELECT 'prompt_versions', count(*) FROM prompt_versions
UNION ALL SELECT 'style_profiles',  count(*) FROM style_profiles
ORDER BY 2 DESC;"

echo "==> done. Run tests with:"
echo "    docker exec promptiq-web python -m pytest tests -q"
