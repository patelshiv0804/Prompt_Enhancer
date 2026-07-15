# PromptIQ Production Readiness & Architecture Handbook

This handbook serves as the official guide for deploying, managing, and scaling the **PromptIQ AI Enhancement Engine** in a production environment.

---

## 1. System Architecture Overview

PromptIQ is designed around modular, domain-driven services, structured repository layers, and a robust asynchronous web API layer built on FastAPI and SQLModel (SQLAlchemy).

### Architectural Workflow

```mermaid
graph TD
    Client[Client App / API Client] -->|HTTP Request| API[FastAPI Layer]
    API -->|Authorization/Current User| Deps[Dependency Injection / deps.py]
    API -->|Invokes orchestrator| EService[PromptEnhancementService]
    EService -->|Selects template| TService[TemplateSelectionService]
    EService -->|Renders placeholders| Renderer[TemplateRenderer]
    EService -->|Formats request| PBuilder[PromptBuilder]
    EService -->|Generates prompt| Mistral[Mistral AI API Provider]
    
    API -->|Analysis| AService[PromptAnalysisService]
    API -->|Comparison| CService[PromptComparisonService]
    API -->|Persistence & Versioning| PService[PromptPersistenceService]
    
    PService -->|Saves Prompt & Version| PRepo[PromptRepository / VersionRepository]
    PService -->|Async Embedding Updates| EmbService[PromptEmbeddingService]
    
    EmbService -->|Computes Vectors| ST[SentenceTransformers Embeddings]
    PRepo -->|Stores Vectors| PG[PostgreSQL DB + pgvector]
```

---

## 2. Database Models & Mapping

The database schema leverage standard SQLModel mappings with PostgreSQL native JSONB and `pgvector` vector fields.

### Entity Relationship Diagram

```mermaid
erDiagram
    PROFILES {
        uuid id PK
        string email UK
        datetime created_at
    }
    AI_MODELS {
        uuid id PK
        string provider
        string model_name
        boolean is_active
    }
    TEMPLATES {
        uuid id PK
        string title
        string body
        string mode
        string role
        vector embedding
        uuid ai_model_id FK
        boolean is_approved
    }
    PROMPTS {
        uuid id PK
        string title
        string original_prompt
        uuid user_id FK
        uuid template_id FK
        uuid ai_model_id FK
        uuid current_version_id FK
        float total_score
        string grade
        vector embedding
        datetime deleted_at
    }
    PROMPT_VERSIONS {
        uuid id PK
        uuid prompt_id FK
        integer version_number
        string version_type
        string content
        string change_summary
        datetime created_at
    }

    PROFILES ||--o{ PROMPTS : creates
    AI_MODELS ||--o{ TEMPLATES : supports
    AI_MODELS ||--o{ PROMPTS : runs_on
    TEMPLATES ||--o{ PROMPTS : applied_to
    PROMPTS ||--o{ PROMPT_VERSIONS : has_history
```

### Models Summary

1. **`Profile`**: User user profile management, holding authorization emails and metadata.
2. **`AIModel`**: Supported model registry (e.g. `openai`, `mistral`, `anthropic`).
3. **`Template`**: AI prompts engineering baseline patterns used to enrich original user inputs. Holds reference vectors (384-dimensions) for template semantic retrieval.
4. **`Prompt`**: Top-level entity representing a user's prompt project. Integrates a `deleted_at` field supporting soft delete policies.
5. **`PromptVersion`**: Sequence logs recording all iterations of prompt refinements, supporting full version rollback operations.

---

## 3. Production Deployment Manual

### A. Local Run / Development
To launch the service locally in production mode:
```bash
# Set production environment variables
export ENVIRONMENT=production
export MISTRAL_API_KEY="your-actual-api-key"
export DATABASE_URL="postgresql+asyncpg://kartik:kartik123@localhost:5432/promptiq"

# Run Uvicorn server
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

### B. Deploying with Docker & Docker Compose
Containerized deployment ensures reproducible setups with automatic database health checks and vector extension boots.

1. **Build and start services**:
   ```bash
   docker-compose up --build -d
   ```
2. **Apply Database Migrations (Alembic)**:
   ```bash
   docker-compose exec web alembic upgrade head
   ```

---

## 4. Production Security & Stability Guidelines

1. **Non-Root Runtime Isolation**:
   The runtime container runs as a dedicated user `appuser` (UID: 10001) instead of root, ensuring container escape defenses.
2. **Secrets Management**:
   Never check in raw secrets or `.env` files. In staging/production, load parameters through secure variables platforms (e.g., AWS Secrets Manager, GitHub Secrets, HashiCorp Vault).
3. **Soft-Delete Implementation**:
   Prompts are never deleted permanently from database tables when using standard delete endpoints. The `deleted_at` field marks record states while database queries filter out deactivated inputs by default.
4. **LLM Timeouts and Fallbacks**:
   Mistral AI connections use defined timeouts (default: 30s) and fallback retry configurations to prevent request starvation or API lockups during peak hours.
