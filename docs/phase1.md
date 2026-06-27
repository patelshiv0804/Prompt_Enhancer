# PromptIQ Backend Development – Phase 1

The Master Prompt has already been provided.

Follow all architecture decisions from the Master Prompt.

Do not re-analyze business logic.

Implement ONLY Phase 1.

Stop after Phase 1 is completed.

---

# Phase 1 Goal

Build the foundational backend infrastructure for PromptIQ.

This phase must establish a production-ready project structure that future phases will build upon.

No business features should be implemented yet.

---

# Scope Of Phase 1

Implement:

1. FastAPI Application Setup
2. Project Folder Structure
3. Environment Configuration
4. Settings Management
5. PostgreSQL Connection
6. pgvector Initialization Strategy
7. SQLModel Configuration
8. Alembic Configuration
9. Dependency Injection Setup
10. Logging Configuration
11. Global Exception Handling
12. Health Check Endpoint
13. Application Lifespan Events
14. Development Configuration
15. Production Configuration

---

# Tech Stack

Backend:

* FastAPI
* Python 3.12+

Database:

* PostgreSQL 16
* pgvector

ORM:

* SQLModel

Migrations:

* Alembic

Validation:

* Pydantic V2

Container Runtime:

* Podman

Database Admin:

* pgAdmin4

---

# Architecture Requirements

Use Clean Architecture.

Expected Layers:

app/
├── api/
├── core/
├── db/
├── models/
├── repositories/
├── services/
├── schemas/
├── utils/
├── tests/

Even if some folders are empty now, create them because future phases will use them.

---

# Configuration Requirements

Create:

* .env.example
* settings.py
* configuration loader
* environment validation

Use:

Pydantic Settings

All sensitive values must come from environment variables.

Example:

DATABASE_URL
SECRET_KEY
ENVIRONMENT
DEBUG

Do not hardcode secrets.

---

# Database Requirements

Create:

database.py

Implement:

* Async PostgreSQL connection
* SQLModel integration
* Async Session management
* Session Dependency

Use:

postgresql+psycopg

The design must support:

PostgreSQL 16

running inside Podman.

---

# pgvector Requirements

Prepare the project for pgvector.

Do NOT create models yet.

However:

Explain:

1. How pgvector will be installed.
2. How pgvector will be initialized.
3. Where vector support will be added later.
4. How Alembic migrations will support vector fields.

Include:

CREATE EXTENSION IF NOT EXISTS vector;

strategy.

---

# Alembic Requirements

Configure Alembic for:

* SQLModel
* PostgreSQL
* pgvector

Generate:

* alembic.ini configuration
* env.py configuration

Explain how future migrations will be generated.

Do not create actual table migrations yet.

---

# Dependency Injection

Create:

dependencies.py

Implement:

* database dependency
* common reusable dependencies

Design for future service injection.

---

# Logging Requirements

Implement structured logging.

Requirements:

* application logs
* error logs
* startup logs
* shutdown logs

Use Python logging module.

Create:

logging.py

Provide configuration.

---

# Exception Handling

Create global exception handlers for:

* validation errors
* HTTP exceptions
* unexpected exceptions

Use a consistent API response format.

Example:

{
"success": false,
"message": "Error message",
"details": {}
}

---

# Application Lifespan

Implement startup and shutdown events.

Startup should:

* validate configuration
* verify database connectivity
* log startup status

Shutdown should:

* gracefully close resources
* log shutdown status

---

# Health Endpoint

Create:

GET /health

Response:

{
"status": "healthy",
"database": "connected",
"environment": "development"
}

Database connectivity should be verified.

---

# Deliverables

Provide:

1. Recommended folder structure
2. Explanation of architecture decisions
3. Environment variable strategy
4. Database setup design
5. Alembic setup design
6. Logging design
7. Exception handling design
8. Complete code for Phase 1

---

# Important Restrictions

Do NOT create:

* models
* repositories
* services
* schemas
* API business routes
* migrations
* authentication
* JWT logic
* prompt logic
* template logic

Those belong to later phases.

Only create infrastructure.

---

# Output Format

Return:

1. Architecture Explanation
2. Folder Structure
3. Code Files
4. Setup Instructions
5. Validation Checklist

After completing Phase 1:

STOP.

Wait for approval before moving to Phase 2.
