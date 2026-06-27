# PromptIQ Backend Development – Phase 4

Phase 1, Phase 2, and Phase 3 have been completed and approved.

Follow all architecture decisions from the Master Prompt.

Use:

* FastAPI
* SQLModel
* PostgreSQL
* pgvector
* Async SQLAlchemy

Implement ONLY Phase 4.

Stop after Phase 4.

---

# Phase 4 Goal

Build the Repository Layer.

The repository layer is responsible for:

* database access
* CRUD operations
* pagination
* filtering
* querying

Repositories must NOT contain:

* business logic
* optimization logic
* prompt analysis logic
* template retrieval logic
* API logic

Repositories should only interact with the database.

---

# Repository Architecture

Expected structure:

repositories/
├── base.py
├── profile.py
├── ai_model.py
├── template.py
├── prompt.py
├── prompt_version.py

Create reusable patterns.

Avoid duplicated code.

---

# Base Repository

Create:

BaseRepository

Purpose:

Reusable CRUD functionality.

Support:

* get_by_id
* get_all
* create
* update
* delete
* exists

Requirements:

* async support
* generic typing
* reusable inheritance

Future repositories should extend BaseRepository.

---

# Profile Repository

Create:

ProfileRepository

Operations:

* create profile
* get profile by id
* get profile by email
* update profile
* deactivate profile
* list profiles

Requirements:

email lookup optimization

Use indexes from Phase 2.

---

# AI Model Repository

Create:

AIModelRepository

Operations:

* create model
* update model
* activate model
* deactivate model
* get model by provider
* list active models

Requirements:

provider-based lookup support.

---

# Template Repository

Create:

TemplateRepository

Operations:

* create template
* update template
* delete template
* get template by id
* list templates
* filter by mode
* filter by category
* filter by ai_model

Requirements:

Support future semantic search integration.

Do NOT implement vector search yet.

Only create repository methods that future semantic search services can reuse.

---

# Prompt Repository

Create:

PromptRepository

Operations:

* create prompt
* update prompt
* delete prompt
* get prompt by id
* list prompts
* get prompts by user
* get prompts by template
* get prompts by model

Requirements:

Support future duplicate detection and prompt search.

Do NOT implement semantic search yet.

---

# Prompt Version Repository

Create:

PromptVersionRepository

Operations:

* create version
* get version by id
* get versions by prompt
* get latest version
* count versions
* delete version

Requirements:

Version ordering support.

Return versions ordered by:

version_number DESC

where appropriate.

---

# Query Optimization

Implement:

Pagination support

Filtering support

Sorting support

Reusable query builders

Avoid N+1 query issues.

Use eager loading where appropriate.

Explain loading strategy.

---

# Relationship Loading

Support future nested responses.

Examples:

Prompt
↓
Template

Prompt
↓
AI Model

Prompt
↓
Versions

Design repository methods that can optionally preload relationships.

Example:

include_template=True

include_versions=True

---

# Error Handling

Repositories should:

* return None when record not found
* raise database exceptions only when appropriate
* avoid HTTP exceptions

Repositories must not know about FastAPI.

---

# Transaction Strategy

Design repository methods to work with:

AsyncSession

Transactions should be controlled by the service layer.

Repositories should not commit business transactions automatically.

Explain the chosen approach.

---

# Future Semantic Search Compatibility

Prepare repositories for:

Template Search

Prompt Search

Future services will use:

templates.embedding

and

prompts.embedding

Do NOT implement vector search now.

But ensure repository design allows:

* similarity search methods later
* reusable query composition

---

# Type Safety

Use:

* Generic Types
* Type Hints
* SQLModel Types
* AsyncSession Types

Avoid Any where possible.

---

# Deliverables

Provide:

1. Repository Architecture
2. Base Repository Design
3. Generic Repository Pattern
4. Repository Implementations
5. Query Optimization Strategy
6. Relationship Loading Strategy
7. Transaction Strategy
8. Complete Repository Code

---

# Important Restrictions

Do NOT implement:

* services
* API routes
* prompt optimization
* prompt analysis
* semantic search
* vector similarity queries
* embedding generation
* authentication

Only implement repositories.

---

# Output Format

Return:

1. Architecture Explanation
2. Repository Folder Structure
3. Base Repository Code
4. Individual Repository Code
5. Query Strategy Notes
6. Transaction Notes
7. Future Search Integration Notes

After completing Phase 4:

STOP.

Wait for approval before moving to Phase 5.
