# PromptIQ Backend - Phase 1 Setup

This repository contains the Phase 1 backend scaffolding for PromptIQ.

## Phase 1 Deliverables

1. Project Folder Structure
2. Python Environment Setup
3. Dependency Installation
4. Podman Setup
5. PostgreSQL Setup
6. pgAdmin Setup
7. pgvector Setup
8. Environment Variables
9. Database Configuration
10. Alembic Configuration
11. Logging Configuration
12. Exception Handling
13. Health Endpoint
14. FastAPI Initialization
15. Complete Startup Guide

---

## Python Environment Setup

### Python Version

- Python 3.12+

### Create a Virtual Environment

#### Windows

```powershell
cd C:\Users\karti\Documents\projects\promptIq
python -m venv .venv
.\.venv\Scripts\Activate
```

#### Linux / macOS

```bash
cd ~/Documents/projects/promptIq
python3 -m venv .venv
source .venv/bin/activate
```

### Install Dependencies

```bash
pip install -r requirements.txt
```

---

## Dependency Management

All Phase 1 dependencies are declared in `requirements.txt`.

Dependencies and why they are required:

- `fastapi`: FastAPI framework for async web APIs.
- `uvicorn[standard]`: ASGI server to run FastAPI.
- `sqlmodel`: ORM layer built on SQLAlchemy and Pydantic.
- `sqlalchemy`: Core SQL toolkit used by SQLModel and Alembic.
- `psycopg[binary]`: PostgreSQL driver for SQLAlchemy and Alembic.
- `asyncpg`: Async PostgreSQL driver for async DB access.
- `alembic`: Database migration management.
- `pydantic`: Validation and settings modeling.
- `pydantic-settings`: Environment-driven settings management.
- `pgvector`: PostgreSQL vector type support for semantic search.
- `python-dotenv`: `.env` file loading during local development.

---

## Load Testing

The repository includes a k6 smoke/load profile that runs through Docker Compose.
By default it exercises liveness and authenticated profile traffic only, so it
does not spend LLM tokens during routine checks. Set `LOAD_INCLUDE_LLM=true` in
`.env.loadtest` only when you intentionally want to include `/api/v1/analyze`.

```bash
docker compose --env-file .env.loadtest -f docker-compose.yml -f docker-compose.load.yml up --abort-on-container-exit k6
```

Tune the run with `LOAD_VUS`, `LOAD_DURATION`, `LOAD_EMAIL`, and
`LOAD_PASSWORD` in `.env.loadtest`.

---

## Project Initialization Commands

1. Create project directories (if not already present):

```bash
mkdir -p app/api/v1 app/core app/db app/schemas alembic/versions
```

2. Create environment file:

```bash
copy .env.example .env
```

3. Activate the virtual environment:

```bash
# Windows
.\.venv\Scripts\Activate

# Linux / macOS
source .venv/bin/activate
```

4. Install dependencies:

```bash
pip install -r requirements.txt
```

5. Start the FastAPI server:

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

---

## Podman Setup

This project uses Podman instead of Docker.

### Create Persistent Volumes

```bash
podman volume create promptiq_pgdata
podman volume create promptiq_pgadmin_data
```

### PostgreSQL Container

```bash
podman run -d \
  --name postgres-db \
  -p 5432:5432 \
  -v promptiq_pgdata:/var/lib/postgresql/data \
  -e POSTGRES_DB=promptiq \
  -e POSTGRES_USER=promptiq_user \
  -e POSTGRES_PASSWORD=promptiq_pass \
  docker.io/library/postgres:16
```

### pgAdmin Container

```bash
podman run -d \
  --name pgadmin \
  -p 5050:80 \
  -v promptiq_pgadmin_data:/var/lib/pgadmin \
  -e PGADMIN_DEFAULT_EMAIL=admin@example.com \
  -e PGADMIN_DEFAULT_PASSWORD=adminpassword \
  docker.io/dpage/pgadmin4
```

### How pgAdmin Connects to PostgreSQL

In pgAdmin, register a new server using:

- Host name/address: `localhost`
- Port: `5432`
- Maintenance database: `postgres`
- Username: `promptiq_user`
- Password: `promptiq_pass`

Because the containers expose ports on the host, pgAdmin can connect over `localhost:5432`.

---

## Podman Verification

Verify running containers:

```bash
podman ps
```

Verify port mapping:

```bash
podman port postgres-db
podman port pgadmin
```

Verify PostgreSQL is accessible:

```bash
podman exec -it postgres-db psql -U promptiq_user -d promptiq -c "SELECT 1;"
```

Verify pgAdmin is accessible:

Open browser: http://localhost:5050

---

## PostgreSQL Setup

If the environment variables already created the database and user, the following commands are optional.

Enter the PostgreSQL container:

```bash
podman exec -it postgres-db bash
psql -U postgres
```

Create database and user:

```sql
CREATE USER promptiq_user WITH PASSWORD 'promptiq_pass';
CREATE DATABASE promptiq OWNER promptiq_user;
GRANT ALL PRIVILEGES ON DATABASE promptiq TO promptiq_user;
```

Verify connectivity:

```sql
\\c promptiq
SELECT current_database();
SELECT current_user;
```

---

## pgvector Installation

Install the extension in the PromptIQ database:

```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

Verify pgvector exists:

```sql
SELECT extname FROM pg_extension WHERE extname = 'vector';
```

Test vector support:

```sql
SELECT '[1,2,3]'::vector(3) AS vec;
```

---

## Database Connection Verification

A Python startup verification example is included in `app/db/session.py`.

Example:

```python
from sqlalchemy import text
from app.db.session import engine

async def verify_connection() -> bool:
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))
        result = await conn.execute(text("SELECT extname FROM pg_extension WHERE extname = 'vector'"))
        return result.scalar_one_or_none() == 'vector'
```

---

## Development Workflow

1. Start Podman containers:
   - `podman run -d --name postgres-db -p 5432:5432 -v promptiq_pgdata:/var/lib/postgresql/data -e POSTGRES_DB=promptiq -e POSTGRES_USER=promptiq_user -e POSTGRES_PASSWORD=promptiq_pass docker.io/library/postgres:16`
   - `podman run -d --name pgadmin -p 5050:80 -v promptiq_pgadmin_data:/var/lib/pgadmin -e PGADMIN_DEFAULT_EMAIL=admin@example.com -e PGADMIN_DEFAULT_PASSWORD=adminpassword docker.io/dpage/pgadmin4`
2. Activate virtual environment.
3. Install Python dependencies.
4. Copy `.env.example` to `.env` and update variables.
5. Run Alembic migrations:
   - `alembic revision --autogenerate -m "initial schema"`
   - `alembic upgrade head`
6. Start FastAPI:
   - `uvicorn app.main:app --reload --host 0.0.0.0 --port 8000`
7. Open Swagger UI:
   - `http://localhost:8000/docs`

---

## Environment Variables

Add these variables to `.env`:

```text
DATABASE_URL=postgresql+asyncpg://promptiq_user:promptiq_pass@localhost:5432/promptiq
```

---

## Alembic Configuration

Alembic is configured to use the application settings from `app.core.config` and to generate migrations from SQLModel metadata.

---

## Logging Configuration

Logging is configured in `app/core/logging.py` using structured log formatting with the standard Python logging system.

---

## Exception Handling

A global exception handler is registered in `app/main.py` to return JSON error responses for unhandled exceptions.

---

## Health Endpoint

The application exposes a health endpoint at:

- `GET /api/v1/health`

It verifies application startup and reports the database status and pgvector extension availability.

---

## FastAPI Initialization

The FastAPI app is initialized in `app/main.py` with router registration and startup events.
