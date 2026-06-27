# PromptIQ Backend Development – Phase 6

Architecture review for Mistral AI has been approved.

Implement ONLY Phase 6.

Follow all architecture decisions from:

* Master Prompt
* Phase 1
* Phase 2
* Phase 3
* Phase 4
* Phase 5
* Mistral AI Architecture Review

---

# Phase 6 Goal

Implement the complete Service Layer.

No API routes.

No authentication.

No Prompt Similarity Search.

Only Service Layer.

---

# Business Workflow

User Prompt
↓
Template Retrieval Engine
↓
Best Template
↓
Prompt Analysis
↓
Prompt Optimization
↓
Prompt Version Creation
↓
current_version_id Update
↓
Prompt Embedding Generation
↓
Save Prompt

---

# Services To Create

services/
├── prompt_analysis_service.py
├── prompt_optimization_service.py
├── prompt_version_service.py
├── prompt_restore_service.py
├── prompt_embedding_service.py
├── template_selection_service.py
└── llm/

---

## TemplateSelectionService

Use:

TemplateSearchService

from Phase 5.

Responsibilities:

* mode filtering
* template retrieval
* ranking
* template selection

Input:

user_prompt
mode

Output:

selected_template

---

## PromptAnalysisService

Use:

BaseLLMProvider

Responsibilities:

* prompt quality analysis
* strengths
* weaknesses
* scoring
* grading

Do not persist data.

---

## PromptOptimizationService

Workflow:

User Prompt
↓
TemplateSelectionService
↓
Selected Template
↓
BaseLLMProvider
↓
Optimized Prompt

Responsibilities:

* optimization orchestration
* provider communication
* output validation

Do not directly access repositories.

---

## PromptVersionService

Rules:

New Prompt:

Create Prompt
↓
Create Version 1
↓
Set current_version_id

Existing Prompt:

Create Version N+1
↓
Update current_version_id

Never overwrite versions.

Always preserve history.

---

## PromptRestoreService

Responsibilities:

Restore previous version.

Example:

Current:

V5

Restore:

V2

System:

Update current_version_id
↓
Update prompt embedding

Never lose history.

---

## PromptEmbeddingService

IMPORTANT

Prompt embeddings are different from template embeddings.

Generate embeddings for:

prompts.embedding

only.

Purpose:

* duplicate detection
* prompt similarity
* recommendations
* history search

Source:

active prompt version content

Do NOT use prompt embeddings for template retrieval.

---

## Transaction Strategy

Operations must be atomic.

Example:

Optimize Prompt

Create Version
↓
Update Prompt
↓
Update Embedding

Rollback on failure.

Use AsyncSession transactions.

---

## Error Handling

Create domain exceptions:

* PromptNotFound
* TemplateNotFound
* VersionNotFound
* EmbeddingGenerationError
* LLMProviderError
* RestoreVersionError

No FastAPI exceptions.

---

## Logging

Log:

* prompt analysis
* prompt optimization
* selected template
* version creation
* version restoration
* embedding generation
* mistral latency

Use structured logging.

---

## Configuration

Environment Variables:

MISTRAL_API_KEY

MISTRAL_MODEL

MISTRAL_TIMEOUT

EMBEDDING_MODEL_NAME

TOP_K_RESULTS

SIMILARITY_THRESHOLD

Validate at startup.

---

## Deliverables

Provide:

1. Service Architecture
2. Workflow Diagrams
3. BaseLLMProvider
4. MistralProvider
5. LLMFactory
6. TemplateSelectionService
7. PromptAnalysisService
8. PromptOptimizationService
9. PromptVersionService
10. PromptRestoreService
11. PromptEmbeddingService
12. Transaction Strategy
13. Error Handling Strategy
14. Complete Service Layer Code

After completing Phase 6:

STOP.

Wait for approval before moving to Phase 7.
