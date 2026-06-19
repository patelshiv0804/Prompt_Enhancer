# PromptIQ Backend

A backend service for prompt management and optimization, built with FastAPI, SQLAlchemy, and PostgreSQL.

## Prerequisites

- Python 3.10+
- Docker & Docker Compose (optional, for database)

## Quick Start

1. Create and activate a virtual environment:
   ```bash
   python -m venv .venv
   .venv\Scripts\activate
   ```

2. Install dependencies:
   ```bash
   pip install fastapi uvicorn sqlalchemy psycopg[binary] alembic python-dotenv pydantic-settings python-jose passlib[bcrypt] python-multipart email-validator loguru pgvector
   ```

3. Start the local database (if using docker-compose):
   ```bash
   docker-compose up -d
   ```

4. Run the API development server:
   ```bash
   uvicorn app.main:app --reload
   ```

5. Access the API documentation:
   - Swagger UI: http://localhost:8000/docs
   - ReDoc: http://localhost:8000/redoc
