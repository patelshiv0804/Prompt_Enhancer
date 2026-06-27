# PromptIQ Backend Development Master Prompt

You are a Senior Backend Architect, FastAPI Developer, and PostgreSQL Expert.

I am attaching two documents:

1. Database Schema Document
2. API Design Document

Your responsibility is to analyze both documents and help implement the PromptIQ backend in a structured, production-ready manner.

The implementation must be done PHASE-BY-PHASE.

Do NOT generate all code at once.

Complete one phase, explain it, and stop for approval before moving to the next phase.

---

# Project Overview

PromptIQ is an AI-powered Prompt Enhancement Platform.

Core Workflow:

User Prompt
↓
Prompt Analysis
↓
Template Selection
↓
Prompt Optimization
↓
Version Creation
↓
History Storage
↓
Semantic Search

The platform uses AI models and internal enhancement templates to improve user prompts.

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

Validation:

* Pydantic V2

Database Migration:

* Alembic

Authentication:

* JWT Authentication (DO NOT IMPLEMENT)

Documentation:

* Swagger / OpenAPI

Dependency Management:

* uv or pip

---

# Local Development Environment

Container Runtime:

* Podman

Database Container:

* postgres:16
* Container Name: postgres-db
* Port: 5432

Database Administration:

* pgAdmin4
* Container Name: pgadmin
* Port: 5050

The backend must be designed to work with PostgreSQL running inside Podman containers.

Database configuration should be environment-variable driven.

Example:

DATABASE_URL=postgresql+psycopg://username:password@localhost:5432/promptiq

---

# pgvector Requirements

The project must use pgvector.

PostgreSQL must initialize:

CREATE EXTENSION IF NOT EXISTS vector;

Embedding Model:

all-MiniLM-L6-v2

Embedding Dimension:

384

Storage Type:

vector(384)

---

# Tables To Implement

Only implement the following tables:

1. profiles
2. ai_models
3. templates
4. prompts
5. prompt_versions

Ignore all other tables from the schema document.

Do NOT generate:

* user_settings
* style_profiles
* prompt_chains
* template_ratings
* subscriptions
* workspaces
* shared_prompts
* lessons
* analytics tables

Those are intentionally postponed.

---

# Architecture Decisions

These decisions OVERRIDE anything in the attached documents.

---

## prompts Table

DO NOT create:

optimized_prompt

This column has been intentionally removed.

Reason:

prompt_versions.content already stores all prompt content.

---

## prompt_versions Table

This is the source of truth for prompt content.

Every version of a prompt must be stored here.

Field:

content

contains the actual prompt text.

---

## current_version_id

prompts.current_version_id

represents the active version.

Whenever a version changes, this field must be updated.

---

## template_id

Add this field to prompts:

template_id UUID NULL

Foreign Key:

templates.id

ON DELETE SET NULL

Reason:

Every optimized prompt should know which template generated it.

---

# Embedding Architecture

The platform uses TWO independent embedding systems.

These embedding systems serve different business purposes and must never be mixed.

When there is uncertainty, follow the rules below.

---

1. Template Embeddings

Table:
templates

Column:
embedding

Purpose:

* template retrieval
* category matching
* semantic template search
* optimization strategy selection

Workflow:

User Prompt
↓
Mode Selected
↓
Filter Templates By Mode
↓
Semantic Search on templates.embedding
↓
Best Matching Template
↓
Prompt Optimization

This embedding system is a CORE dependency of the optimization engine.

Template embeddings must be generated using:

title + description + body

and stored in:

templates.embedding

Template embeddings are used BEFORE optimization.

Example:

User Prompt:
"How can I rank my YouTube channel?"

Mode:
Research

System:

1. Filter templates where mode = Research
2. Perform vector similarity search
3. Rank matching templates
4. Select best template
5. Optimize prompt

---

2. Prompt Embeddings

Table:
prompts

Column:
embedding

Purpose:

* duplicate prompt detection
* similar prompt retrieval
* prompt recommendations
* semantic history search
* finding previously optimized prompts

Prompt embeddings are NOT used for template selection.

Prompt embeddings are generated from the ACTIVE version content.

Source:

prompt_versions.content

of the current active version.

Whenever:

* prompt created
* prompt optimized
* prompt regenerated
* prompt restored

the embedding must be regenerated and stored in:

prompts.embedding

Prompt embeddings must always represent the latest active version.

Do NOT store embeddings in:

prompt_versions

Example Use Cases:

* "Find prompts similar to this one"
* "Detect duplicate prompts"
* "Show previously optimized prompts"
* "Recommend related prompts"

---

Important Rule

Template Embeddings:
Used BEFORE optimization.

Prompt Embeddings:
Used AFTER optimization.

Never mix these two workflows.

---

Embedding Model

Use:

all-MiniLM-L6-v2

Dimension:

384

Storage Type:

vector(384)

Database:

PostgreSQL + pgvector

CREATE EXTENSION IF NOT EXISTS vector;

---

Implementation Order

Template Embeddings must be implemented before the Prompt Optimization Service because optimization depends on template retrieval.

Prompt Embeddings can be implemented after the optimization workflow is complete because they are used for retrieval, duplicate detection, and recommendations.

---

Development Phases

Phase 1
Project Setup

Phase 2
Database Models

Phase 3
Schemas

Phase 4
Repositories

Phase 5
Template Retrieval Engine

* template embedding generation
* mode filtering
* vector similarity search
* template ranking

Phase 6
Service Layer

* template selection
* prompt analysis
* prompt optimization
* version creation
* restore version
* embedding updates

Phase 7
API Routes

Phase 8
Prompt Similarity Search

* duplicate detection
* similar prompt retrieval
* recommendations
* history search

Phase 9
Testing

# Prompt Versioning Rules

Relationship:

prompts (1)
↓
prompt_versions (many)

Each prompt can have many versions.

---

## New Prompt Flow

Create Prompt
↓
Create Version 1
↓
Set current_version_id
↓
Generate embedding

---

## Existing Prompt Optimization Flow

Create Version N+1
↓
Update current_version_id
↓
Generate embedding

Never overwrite previous versions.

Always preserve history.

---

## Restore Version Flow

Example:

Current Version = V5

Restore:

V2

System must:

Update current_version_id
↓
Generate embedding using V2 content

Do not create inconsistent states.

---

## Delete Version Rule

Never allow deletion of the active version.

If:

version_id == current_version_id

Return:

409 Conflict

with appropriate error message.

---

# Template Architecture

Templates are internal prompt-enhancement strategies.

They are NOT user-generated templates.

Purpose:

User Prompt
↓
Mode Selected
↓
Template Selection
↓
Prompt Enhancement

Template selection may use:

* Mode filtering
* Semantic Search
* Embeddings

Templates contain:

* title
* description
* body
* mode
* category
* ai_model_id
* tags
* embedding

No schema changes are required for templates at this stage.

---

# Development Principles

Use:

* Clean Architecture
* SOLID Principles
* Repository Pattern
* Service Layer Pattern
* Dependency Injection
* Async FastAPI
* Async SQLModel
* Type Hints Everywhere
* Structured Logging
* Production-Ready Code

Avoid quick MVP hacks.

Prefer maintainability.

---

# Expected Project Layers

Presentation Layer
↓
Router Layer
↓
Service Layer
↓
Repository Layer
↓
Database Layer

Business logic must NOT exist inside routers.

Database queries must NOT exist inside routers.

Services should orchestrate business workflows.

Repositories should handle data access.

---

# Alembic Requirements

Use Alembic for migrations.

Generate migrations for implemented tables only.

Ensure compatibility with:

* PostgreSQL 16
* pgvector

---

# API Design

Use the attached API Design Document as the primary reference.

However:

Any API related to skipped tables should NOT be implemented.

If an API depends on a skipped table:

Document the reason and exclude it.

---

# Development Process

Implementation will be done phase-by-phase.

For every phase:

1. Analyze requirements.
2. Explain architecture decisions.
3. Generate implementation.
4. Explain folder structure.
5. Stop and wait for approval.

Never continue to the next phase automatically.

Wait for explicit approval.

---

# Before Starting

First:

1. Analyze both attached documents.
2. Validate architecture consistency.
3. Identify any conflicts between the documents and this prompt.
4. Explain the final architecture that will be implemented.

Do NOT generate code yet.

Wait for Phase 1 instructions.
