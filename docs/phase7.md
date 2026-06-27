# PromptIQ Backend Development – Phase 7

Phase 1 through Phase 6 have been completed and approved.

Follow all architecture decisions from:

* Master Prompt
* Phase 1
* Phase 2
* Phase 3
* Phase 4
* Phase 5
* Phase 6

Implement ONLY Phase 7.

Do NOT implement Prompt Similarity Search.

Do NOT implement Testing.

Stop after Phase 7.

---

# Phase 7 Goal

Implement the API Layer.

Create production-ready FastAPI routers that expose the functionality implemented in previous phases.

Routers must remain thin.

Business logic belongs in services.

Database logic belongs in repositories.

---

# API Architecture

Expected Flow

Client
↓
Router
↓
Service
↓
Repository
↓
Database

Routers should:

* validate requests
* call services
* return responses

Routers should NOT:

* execute SQL
* call repositories directly
* contain optimization logic
* contain embedding logic

---

# Router Structure

Create:

api/
├── deps.py
├── profiles.py
├── ai_models.py
├── templates.py
├── prompts.py
├── prompt_versions.py
└── health.py

Create:

api/router.py

for router registration.

---

# Health Router

Create:

GET /health

Purpose:

Application health check.

Response:

{
"status": "healthy",
"database": "connected",
"environment": "development"
}

Use service layer if needed.

---

# Profiles Router

Implement:

GET /profiles/{id}

PATCH /profiles/{id}

GET /profiles/me

Requirements:

Use schemas from Phase 3.

Use services from Phase 6.

Return standardized responses.

---

# AI Models Router

Implement:

GET /ai-models

GET /ai-models/{id}

GET /ai-models/active

Purpose:

View available AI models.

No provider-specific logic in routes.

---

# Templates Router

Implement:

GET /templates

GET /templates/{id}

GET /templates/mode/{mode}

GET /templates/category/{category}

Purpose:

Browse templates.

Use:

TemplateRepository → Service Layer

Do not expose embeddings.

---

# Prompts Router

Most important router.

Implement:

POST /prompts

GET /prompts

GET /prompts/{id}

DELETE /prompts/{id}

Purpose:

Prompt management.

---

# Create Prompt Endpoint

POST /prompts

Workflow:

User Prompt
↓
Template Selection
↓
Prompt Analysis
↓
Prompt Optimization
↓
Version Creation
↓
Embedding Creation
↓
Return Response

Use:

PromptOptimizationService

Do not implement logic in router.

---

# Get Prompt Endpoint

GET /prompts/{id}

Return:

Prompt Details

Current Active Version

Template Information

AI Model Information

Version Count

Use nested response schemas.

---

# List Prompts Endpoint

GET /prompts

Support:

Pagination

Sorting

Filtering

Examples:

?page=1
?page_size=20
?template_id=
?model_id=

Use reusable pagination schemas.

---

# Prompt Versions Router

Implement:

GET /prompts/{prompt_id}/versions

GET /versions/{version_id}

POST /versions/{version_id}/restore

DELETE /versions/{version_id}

---

# Restore Version Endpoint

Workflow:

Version ID
↓
PromptRestoreService
↓
current_version_id updated
↓
embedding updated
↓
response returned

---

# Delete Version Endpoint

Important Rule

If:

version_id == current_version_id

Return:

409 Conflict

Use domain exception from service layer.

Do not implement logic inside router.

---

# API Response Standardization

Create reusable response format.

Success Example

{
"success": true,
"message": "Prompt created successfully",
"data": {}
}

Error Example

{
"success": false,
"message": "Prompt not found",
"errors": {}
}

All routers must use the same format.

---

# Dependency Injection

Use FastAPI Depends.

Inject:

* services
* database session
* configuration

through dependencies.

Do not manually instantiate services in routes.

---

# Exception Handling Integration

Integrate custom exceptions from Phase 6.

Examples:

PromptNotFound

TemplateNotFound

VersionNotFound

LLMProviderError

EmbeddingGenerationError

Map them to appropriate HTTP status codes.

Example:

404

409

422

500

---

# OpenAPI Documentation

Add:

* tags
* summaries
* descriptions
* response models
* error responses

Swagger documentation should be production-ready.

---

# Pagination

Implement reusable pagination.

Support:

page

page_size

sorting

future filtering

Use schemas from Phase 3.

---

# Logging

Log:

* request received
* request completed
* response status
* execution time
* route errors

Use structured logging.

---

# Security Placeholder

JWT is not implemented.

Create placeholder dependencies.

Example:

get_current_user()

Raise:

Not Implemented

or return mock user.

Document clearly.

Do not implement authentication.

---

# Deliverables

Provide:

1. API Architecture
2. Router Structure
3. Dependency Injection Design
4. Response Standardization Design
5. Exception Mapping Strategy
6. Complete Router Code
7. OpenAPI Integration
8. Pagination Strategy
9. Logging Strategy

---

# Important Restrictions

Do NOT implement:

* Prompt Similarity Search
* Search APIs
* Duplicate Detection APIs
* Recommendation APIs
* Testing

Those belong to future phases.

Only implement API Layer.

---

# Output Format

Return:

1. API Architecture Explanation
2. Router Folder Structure
3. Dependency Design
4. Router Implementations
5. Exception Mapping Design
6. OpenAPI Design
7. Integration Notes

After completing Phase 7:

STOP.

Wait for approval before moving to Phase 8.
