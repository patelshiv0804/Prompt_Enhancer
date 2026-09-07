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
#   Never run it against a database holding production data, and never in CI —
#   the CI guard below is a hard refusal, not a convention. The dump is written
#   inside the Postgres container's /tmp and removed after the restore; nothing
#   lands on the host.
#
# TWO RUNNERS: locally, Postgres and the application live in containers and every
#   command has to `docker exec` into one of them. In CI, Postgres is a service
#   container reachable on localhost and the application is installed on the
#   runner itself, so there is nothing to exec into. Both are supported through
#   the pg_/app_ wrappers; override the auto-detection with
#   BOOTSTRAP_RUNNER=docker|native.
#
set -euo pipefail

MODE="${1:-clone}"

PG_CONTAINER="${PG_CONTAINER:-promptiq-postgres}"
WEB_CONTAINER="${WEB_CONTAINER:-promptiq-web}"
PG_USER="${POSTGRES_USER:-postgres}"
PG_PASSWORD="${POSTGRES_PASSWORD:-admin}"
DEV_DB="${POSTGRES_DB:-prompt_enhancer}"
TEST_DB="${TEST_DB:-${DEV_DB}_test}"
DUMP_PATH="/tmp/${DEV_DB}.bootstrap.dump"

if [[ "$TEST_DB" == "$DEV_DB" ]]; then
  echo "REFUSING: test database name is identical to the dev database ($DEV_DB)." >&2
  exit 1
fi

# ── Pick a runner ─────────────────────────────────────────────────────────
RUNNER="${BOOTSTRAP_RUNNER:-}"
if [[ -z "$RUNNER" ]]; then
  if [[ -n "${CI:-}" ]] || ! docker inspect "$PG_CONTAINER" >/dev/null 2>&1; then
    RUNNER=native
  else
    RUNNER=docker
  fi
fi

# Cloning copies real accounts and their password hashes. CI logs and artifacts
# are far more widely readable than a local container, so refuse outright rather
# than trusting the caller to pass the right mode.
if [[ "$MODE" == "clone" && -n "${CI:-}" ]]; then
  echo "REFUSING: clone mode copies real user data and must never run in CI." >&2
  echo "          Use: $0 migrate" >&2
  exit 1
fi

if [[ "$RUNNER" == "docker" ]]; then
  # Inside the container Postgres is reached over the local socket as a trusted
  # superuser, and the app's DATABASE_URL has to name the compose service host.
  DB_HOST_FOR_APP="db"
  DB_PORT_FOR_APP="5432"
  # MSYS2/Git-Bash on Windows rewrites anything that looks like a POSIX absolute
  # path before handing it to a native binary, so `--file=/tmp/x` reaches
  # docker.exe as `--file=C:/Users/.../Temp/x` and pg_dump fails inside the
  # container. These two variables switch that rewriting off; they are simply
  # unused on Linux and macOS.
  _docker() { MSYS_NO_PATHCONV=1 MSYS2_ARG_CONV_EXCL='*' docker "$@"; }
  pg_()  { _docker exec -i "$PG_CONTAINER" "$@"; }
  app_() { _docker exec -i -e DATABASE_URL="$APP_DATABASE_URL" "$WEB_CONTAINER" "$@"; }
else
  # Native: psql and the application both run here, so the connection details
  # come from the standard libpq variables.
  export PGHOST="${PGHOST:-localhost}"
  export PGPORT="${PGPORT:-5432}"
  export PGPASSWORD="${PGPASSWORD:-$PG_PASSWORD}"
  DB_HOST_FOR_APP="$PGHOST"
  DB_PORT_FOR_APP="$PGPORT"
  pg_()  { "$@"; }
  app_() { DATABASE_URL="$APP_DATABASE_URL" "$@"; }
fi

APP_DATABASE_URL="postgresql+asyncpg://${PG_USER}:${PG_PASSWORD}@${DB_HOST_FOR_APP}:${DB_PORT_FOR_APP}/${TEST_DB}"

psql_postgres() { pg_ psql -v ON_ERROR_STOP=1 -U "$PG_USER" -d postgres "$@"; }
psql_test()     { pg_ psql -v ON_ERROR_STOP=1 -U "$PG_USER" -d "$TEST_DB" "$@"; }

echo "==> mode=$MODE  runner=$RUNNER  dev=$DEV_DB  test=$TEST_DB"

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
    pg_ pg_dump \
      -U "$PG_USER" -d "$DEV_DB" \
      --format=custom --no-owner --no-privileges \
      --file="$DUMP_PATH"

    # The custom-format dump carries CREATE EXTENSION vector, every index
    # (including the HNSW vector indexes), the alembic_version row and all data.
    echo "==> restoring into $TEST_DB"
    pg_ pg_restore \
      -U "$PG_USER" -d "$TEST_DB" \
      --no-owner --no-privileges \
      "$DUMP_PATH"

    pg_ rm -f "$DUMP_PATH"
    ;;

  migrate)
    echo "==> creating pgvector extension"
    psql_test -c "CREATE EXTENSION IF NOT EXISTS vector;"

    echo "==> alembic upgrade head"
    app_ python -m alembic upgrade head

    echo "==> seeding"
    app_ python scripts/seed.py
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
app_ python scripts/ensure_test_user.py

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
if [[ "$RUNNER" == "docker" ]]; then
  echo "    docker exec promptiq-web python -m pytest tests -q"
else
  echo "    TEST_DATABASE_URL='$APP_DATABASE_URL' python -m pytest tests -q"
fi
