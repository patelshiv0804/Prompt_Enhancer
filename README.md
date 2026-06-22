# Prompt Enhancer Backend

A robust, scalable FastAPI backend for the Prompt Enhancer application, featuring modular architecture, asynchronous PostgreSQL database interactions, JWT-based authentication, and automated testing.

## Technologies Used

- **Framework**: FastAPI
- **Language**: Python 3.11+
- **Database**: PostgreSQL (with `asyncpg`)
- **ORM**: SQLAlchemy 2.0 (Async)
- **Migrations**: Alembic
- **Authentication**: JWT (JSON Web Tokens) with `bcrypt`
- **Testing**: Pytest with `pytest-asyncio`
- **Formatting**: Black, Ruff

## Project Structure

The project follows a domain-driven, modular architecture:

```
Prompt_Enhancer/
├── alembic/              # Database migration scripts
├── app/                  # Main application code
│   ├── api/              # API router registration
│   ├── core/             # Core configurations (DB, security, exceptions, logging)
│   ├── middleware/       # Custom ASGI middleware (rate limit, logging, auth)
│   └── modules/          # Domain modules (features)
│       ├── auth/         # Authentication (Register, Login)
│       └── users/        # Users domain (Module A: Profile, Module B: Settings)
├── scripts/              # Helper scripts (seed, migrate)
└── tests/                # Test suite
    ├── integration/      # Integration tests (API endpoints)
    └── unit/             # Unit tests (Schema validation)
```

## Setup Instructions

### 1. Requirements

- Python 3.11+
- PostgreSQL server running locally or via Docker

### 2. Environment Setup

Create a virtual environment and install dependencies:

```bash
python -m venv venv
source venv/bin/activate  # On Windows: .\venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Configuration

Copy the example environment file and configure it:

```bash
cp .env.example .env
```

Ensure your PostgreSQL credentials in the `.env` file are correct:
```env
DATABASE_URL=postgresql+asyncpg://postgres:admin@localhost:5432/prompt_enhancer
TEST_DATABASE_URL=postgresql+asyncpg://postgres:admin@localhost:5432/prompt_enhancer_test
```

### 4. Database Initialization

Create the necessary databases and run Alembic migrations to set up the schema:

```bash
# Create databases (Windows/Powershell)
python scripts/create_dbs.py

# Run migrations
python -m alembic upgrade head
```

Optionally, you can seed the database with a test user (`shiv@gmail.com` / `Test1234!`):

```bash
python -m scripts.seed
```

### 5. Running the Application

Start the development server with live reload:

```bash
uvicorn app.main:app --reload
```

The API will be available at: http://127.0.0.1:8000
Interactive API Documentation (Swagger UI): http://127.0.0.1:8000/docs

## Running Tests

The application includes a comprehensive test suite covering both unit tests (schemas) and integration tests (APIs).

To run all tests:

```bash
pytest tests/ -v
```

To run a specific module:

```bash
pytest tests/integration/test_auth_api.py -v
```

## API Modules Implemented

### Authentication
- `POST /api/v1/auth/register`: Register a new user
- `POST /api/v1/auth/login`: Login and receive JWT

### Module A: Profile Management
- `GET /api/v1/profile/me`: Get current user profile
- `PATCH /api/v1/profile/me`: Update profile (supports multipart form data for avatars)
- `DELETE /api/v1/profile/me`: Soft-delete account
- `POST /api/v1/profile/restore`: Request account restoration (OTP sent)
- `POST /api/v1/profile/restore/verify`: Verify OTP and restore account
- `GET /api/v1/profile/plan`: Get user subscription limits
- `PATCH /api/v1/profile/onboarding`: Update onboarding status
- `GET /api/v1/profile/stats`: Get user dashboard statistics
- `GET /api/v1/profile/activity`: Get recent user activity logs

### Module B: User Settings
- `GET /api/v1/settings`: Get user preferences
- `PATCH /api/v1/settings`: Bulk update preferences
- `POST /api/v1/settings/reset`: Reset to defaults
- `PATCH /api/v1/settings/theme`: Update theme (`light`, `dark`, `system`)
- `PATCH /api/v1/settings/default-model`: Update default AI model
- `PATCH /api/v1/settings/default-mode`: Update system mode (e.g. `youtube-shorts`)
- `PATCH /api/v1/settings/intent-detection`: Toggle intent detection
- `PATCH /api/v1/settings/diff-view`: Toggle diff view by default
