# PromptIQ Context

## Tech Stack

- FastAPI
- SQLModel
- PostgreSQL 16
- pgvector
- Alembic
- Podman
- Mistral AI

## Completed Phases

Phase 1:
Infrastructure

Phase 2:
Database Models

Phase 3:
Schemas

Phase 4:
Repositories

Phase 5:
Template Retrieval Engine

Phase 6:
Service Layer (Mistral)

Phase 7:
API Layer (In Progress)

---

## Architecture Decisions

### Tables

- profiles
- ai_models
- templates
- prompts
- prompt_versions

### Removed

optimized_prompt

### Added

template_id in prompts

### Prompt Versioning

prompt_versions.content
is source of truth.

current_version_id
points to active version.

### Embeddings

templates.embedding
→ template retrieval

prompts.embedding
→ prompt similarity

### LLM

Current:
Mistral AI

Future:
OpenAI
Gemini
Anthropic

via BaseLLMProvider

### Authentication

Not implemented.

Handled by another teammate.