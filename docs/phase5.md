# PromptIQ Backend Development – Phase 5

Phase 1, Phase 2, Phase 3, and Phase 4 have been completed and approved.

Follow all architecture decisions from the Master Prompt.

Implement ONLY Phase 5.

Do not implement Prompt Optimization yet.

Do not implement Prompt Similarity Search.

Stop after Phase 5.

---

# Phase 5 Goal

Build the Template Retrieval Engine.

This engine is responsible for selecting the most appropriate enhancement template before prompt optimization begins.

This is a core dependency of the optimization pipeline.

---

# Business Workflow

User Prompt
↓
Mode Selection
↓
Template Filtering
↓
Semantic Search
↓
Template Ranking
↓
Best Template
↓
Return Template

Prompt optimization is NOT part of this phase.

This phase only retrieves the most suitable template.

---

# Embedding Architecture

This phase works ONLY with:

templates.embedding

Purpose:

* template retrieval
* category matching
* semantic template search
* optimization strategy selection

Do NOT use:

prompts.embedding

That belongs to Phase 8.

---

# Search Scope

Search only:

templates

Only approved templates:

is_approved = true

Only active AI models if applicable.

---

# Embedding Model

Use:

all-MiniLM-L6-v2

Dimensions:

384

Framework:

Sentence Transformers

Expected Service:

EmbeddingService

Purpose:

Generate embeddings for:

* user prompt
* template content

---

# Template Embedding Generation

Template embeddings should be generated from:

title
+
description
+
body

Example:

combined_text =
title + description + body

Generate embedding.

Store in:

templates.embedding

Do not regenerate embeddings during search.

Embeddings should already exist in database.

---

# User Prompt Embedding

When user submits:

"How can I rank my YouTube channel?"

Generate temporary embedding.

Do NOT save this embedding.

Purpose:

Similarity comparison.

---

# Template Filtering

Before semantic search:

Filter by:

mode

Example:

Research

Only search:

Research templates

Do not search all templates.

This reduces search space.

---

# Semantic Search Requirements

Implement:

Cosine Similarity

using:

pgvector

Search against:

templates.embedding

Requirements:

* top_k support
* configurable threshold
* ranking support

---

# Ranking Strategy

Implement ranking service.

Rank templates by:

1. Similarity Score
2. Approval Status
3. Usage Count
4. Featured Status

Explain ranking logic.

Document reasoning.

---

# Search Result Structure

Example:

[
{
"template_id": "...",
"title": "...",
"similarity_score": 0.92
}
]

Include score.

Support future debugging.

---

# Services To Create

Create:

EmbeddingService

Responsibilities:

* load embedding model
* generate embeddings
* normalize embeddings
* cache model instance

---

Create:

TemplateSearchService

Responsibilities:

* filter templates
* perform similarity search
* rank results
* return best templates

---

Create:

TemplateRankingService

Responsibilities:

* ranking logic
* score adjustments
* future extensibility

---

# Repository Integration

Use:

TemplateRepository

from Phase 4.

Do not bypass repositories.

Service Layer
↓
Repository Layer
↓
Database

must be respected.

---

# Performance Requirements

Design for:

1000+
templates

Requirements:

* pgvector indexes
* top-k retrieval
* minimal memory usage

Explain indexing strategy.

---

# Error Handling

Handle:

* no matching templates
* invalid mode
* embedding generation failure
* database errors

Use custom exceptions.

Do not use HTTP exceptions here.

---

# Configuration

Create configuration options:

TOP_K_RESULTS

SIMILARITY_THRESHOLD

EMBEDDING_MODEL_NAME

Allow environment-based configuration.

---

# Logging

Log:

* search requests
* search duration
* selected template
* similarity score

Use structured logging.

---

# Unit Testing Requirements

Design tests for:

EmbeddingService

TemplateSearchService

RankingService

Mock embedding generation.

Mock repository layer.

Explain testing strategy.

Do not implement full test suite yet.

That belongs to Phase 9.

---

# Deliverables

Provide:

1. Search Architecture
2. Embedding Architecture
3. Service Design
4. Ranking Design
5. pgvector Query Design
6. Performance Strategy
7. Error Handling Strategy
8. Complete Service Code
9. Configuration Code
10. Integration Notes

---

# Important Restrictions

Do NOT implement:

* prompt optimization
* prompt analysis
* prompt versioning
* prompt similarity search
* API routes
* authentication

Only implement template retrieval.

---

# Output Format

Return:

1. Architecture Explanation
2. Retrieval Flow Diagram
3. Service Layer Design
4. Embedding Service Code
5. Template Search Service Code
6. Ranking Service Code
7. Repository Integration Notes
8. Configuration Notes
9. Future Phase Integration Notes

After completing Phase 5:

STOP.

Wait for approval before moving to Phase 6.
