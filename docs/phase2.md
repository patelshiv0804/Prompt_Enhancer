# PromptIQ Backend Development – Phase 2

The Master Prompt and Phase 1 have already been completed and approved.

Follow all architecture decisions from the Master Prompt.

Implement ONLY Phase 2.

Do not implement repositories, services, routes, business logic, or semantic search yet.

Stop after Phase 2.

---

# Phase 2 Goal

Design and implement the database layer.

Create all database models and relationships required for the MVP.

Generate SQLModel models and Alembic migrations.

This phase establishes the data structure that future phases will use.

---

# Tables To Implement

Only create:

1. profiles
2. ai_models
3. templates
4. prompts
5. prompt_versions

Do NOT create any other tables.

---

# ORM Requirements

Use:

* SQLModel
* PostgreSQL 16
* pgvector
* Async SQLAlchemy support

All models must:

* use UUID primary keys
* support timestamps
* support future scalability
* follow SQLModel best practices

---

# Common Model Requirements

Every table should include:

created_at
updated_at

Use timezone-aware timestamps.

Implement reusable base classes where appropriate.

Example:

TimestampMixin

UUIDMixin

Avoid code duplication.

---

# Table Design Rules

## profiles

Create model for:

profiles

Include:

* id
* email
* full_name
* avatar_url
* is_active
* created_at
* updated_at

Requirements:

* email unique
* indexed fields where appropriate

Generate constraints and indexes.

---

## ai_models

Create model for:

ai_models

Purpose:

Stores available LLM providers and models.

Include fields from schema document.

Examples:

* provider
* model_name
* description
* is_active
* supports_analysis
* supports_optimization

Add appropriate indexes.

---

## templates

Create model for:

templates

Purpose:

Internal prompt-enhancement strategies.

Important:

Templates are NOT user-generated.

Include:

* id
* title
* description
* body
* mode
* category
* ai_model_id
* tags
* embedding
* is_featured
* is_approved
* use_count
* created_at
* updated_at

Requirements:

Relationship:

templates
↓
ai_models

Many templates can use one AI model.

---

# Template Embeddings

Create:

embedding

using:

pgvector

Type:

vector(384)

Purpose:

Template retrieval

Category matching

Semantic template search

Optimization strategy selection

Embedding should be generated from:

title + description + body

Do not implement generation logic yet.

Only model design.

---

## prompts

Create model for:

prompts

Important Architecture Rules:

DO NOT CREATE:

optimized_prompt

This column has been removed.

---

Include:

* id
* user_id
* template_id
* ai_model_id
* title
* original_prompt
* current_version_id
* embedding
* total_score
* grade
* created_at
* updated_at

---

Relationships

profiles
↓
prompts

templates
↓
prompts

ai_models
↓
prompts

---

# Prompt Embeddings

Create:

embedding

using:

vector(384)

Purpose:

* duplicate detection
* prompt similarity search
* prompt recommendations
* prompt history search

Prompt embeddings always represent:

latest active version only.

Do NOT store embeddings in prompt_versions.

---

## prompt_versions

Create model for:

prompt_versions

Purpose:

Version history

Source of truth for prompt content.

---

Include:

* id
* prompt_id
* version_number
* version_type
* content
* change_summary
* created_at

---

Relationship:

prompts (1)
↓
prompt_versions (many)

---

# Versioning Constraints

Implement constraints where appropriate.

Examples:

Prompt:

P1

Versions:

V1
V2
V3

Version numbers should be unique per prompt.

Example:

prompt_id + version_number

should be unique.

Generate database constraints.

---

# current_version_id Relationship

Design the relationship carefully.

prompts.current_version_id

references:

prompt_versions.id

Avoid circular relationship issues.

Explain the implementation approach.

Document any SQLModel limitations and recommended solution.

---

# Indexing Strategy

Design indexes for:

profiles

ai_models

templates

prompts

prompt_versions

Explain:

* why index exists
* expected query patterns
* future scalability

---

# PostgreSQL Considerations

Use PostgreSQL best practices.

Generate:

* unique constraints
* foreign keys
* indexes

Ensure compatibility with:

* PostgreSQL 16
* pgvector

---

# Alembic Requirements

Generate:

1. Initial migration
2. pgvector support migration
3. foreign key creation
4. indexes

Explain migration order.

---

# Deliverables

Provide:

1. ER Diagram Explanation
2. Relationship Explanation
3. SQLModel Models
4. Mixins
5. Constraints
6. Indexes
7. Alembic Migrations
8. Migration Strategy
9. PostgreSQL Considerations

---

# Important Restrictions

Do NOT create:

* repositories
* services
* routes
* schemas
* search services
* embedding generation services
* authentication

Those belong to later phases.

Only implement the database layer.

---

# Output Format

Return:

1. Architecture Review
2. ER Design
3. Relationship Analysis
4. SQLModel Code
5. Alembic Code
6. Migration Notes
7. Validation Checklist

After completing Phase 2:

STOP.

Wait for approval before moving to Phase 3.
