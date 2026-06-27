# PromptIQ Backend Development – Phase 3

Phase 1 and Phase 2 have been completed and approved.

Follow all architecture decisions from the Master Prompt.

Use the models created in Phase 2.

Implement ONLY Phase 3.

Do not implement repositories, services, routes, semantic search, or business logic.

Stop after Phase 3.

---

# Phase 3 Goal

Create all request and response schemas required by the API layer.

Use:

* Pydantic V2
* FastAPI Best Practices
* Strong Validation
* Reusable Schema Design

This phase should prepare the backend for future service and API implementation.

---

# Tables Covered

Create schemas only for:

1. profiles
2. ai_models
3. templates
4. prompts
5. prompt_versions

---

# Schema Organization

Create schema modules:

schemas/
├── profile.py
├── ai_model.py
├── template.py
├── prompt.py
├── prompt_version.py
├── common.py

Use clean separation.

---

# Common Schemas

Create reusable schemas for:

Pagination

Success Response

Error Response

Timestamp Response

Base API Response

Examples:

PageResponse
PaginatedResponse
APIResponse
ErrorResponse

These should be reusable across all future endpoints.

---

# Profile Schemas

Create:

ProfileCreate

ProfileUpdate

ProfileRead

ProfileSummary

Requirements:

* email validation
* optional update fields
* response-safe design

Do not expose internal fields.

---

# AI Model Schemas

Create:

AIModelCreate

AIModelUpdate

AIModelRead

AIModelSummary

Requirements:

Support all fields from Phase 2 model.

Use enums where appropriate.

---

# Template Schemas

Create:

TemplateCreate

TemplateUpdate

TemplateRead

TemplateSummary

TemplateSearchResponse

Requirements:

Include:

* title
* description
* body
* mode
* category
* ai_model_id
* tags

Important:

Do NOT expose embedding field in public responses.

Embedding should never be returned to frontend clients.

---

# Prompt Schemas

Create:

PromptCreate

PromptUpdate

PromptRead

PromptSummary

PromptDetailResponse

Requirements:

Use current architecture.

Do NOT include:

optimized_prompt

because it does not exist.

Include:

* title
* original_prompt
* template_id
* ai_model_id
* current_version_id

PromptDetailResponse should support:

Current Active Version

Version Count

Template Information

Model Information

---

# Prompt Version Schemas

Create:

PromptVersionCreate

PromptVersionRead

PromptVersionSummary

PromptVersionRestoreRequest

Requirements:

Expose:

* version_number
* version_type
* content
* change_summary

Support future restore operations.

---

# Validation Rules

Implement validation for:

UUID fields

String lengths

Required fields

Email fields

Version numbers

Prompt content

Template content

Use:

Field()

Annotated

Pydantic validators

Where appropriate.

---

# Enum Design

Create reusable enums for:

VersionType

PromptGrade

TemplateMode

ModelProvider

If these concepts exist in Phase 2 models.

Place enums in a reusable location.

---

# API Response Design

All responses should follow a consistent structure.

Example:

{
"success": true,
"message": "Prompt retrieved successfully",
"data": {}
}

Error Example:

{
"success": false,
"message": "Prompt not found",
"errors": {}
}

Create reusable response wrappers.

---

# Serialization Rules

Support:

UUID serialization

Datetime serialization

Nested objects

Relationship responses

Avoid exposing internal database implementation details.

---

# Future Compatibility

Design schemas so they work with:

Repositories (Phase 4)

Services (Phase 6)

API Routes (Phase 7)

Avoid tightly coupling schemas to database models.

---

# Deliverables

Provide:

1. Schema Architecture
2. Folder Structure
3. Common Schemas
4. Enum Definitions
5. Profile Schemas
6. AI Model Schemas
7. Template Schemas
8. Prompt Schemas
9. Prompt Version Schemas
10. Validation Strategy

---

# Important Restrictions

Do NOT implement:

* repositories
* services
* routes
* authentication
* semantic search
* embedding generation
* business logic

Only implement schemas.

---

# Output Format

Return:

1. Architecture Explanation
2. Folder Structure
3. Complete Schema Code
4. Validation Notes
5. Future Integration Notes

After completing Phase 3:

STOP.

Wait for approval before moving to Phase 4.
