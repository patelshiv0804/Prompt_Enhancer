"""
seed.py — PromptIQ Database Seeder
====================================
Populates the database with realistic sample data for development/testing.

Tables seeded (in dependency order):
  1. users            → base auth records
  2. profiles         → linked to users (1-to-1)
  3. user_settings    → linked to profiles
  4. ai_models        → LLM provider catalogue
  5. templates        → prompt templates linked to ai_models
  6. style_profiles   → writing style presets
  7. prompts          → user prompts linked to profile + ai_model + template
  8. prompt_versions  → version history for each prompt

Usage:
  # Local (venv activated)
  python scripts/seed.py

  # Inside Docker container
  docker exec -it promptiq-web python scripts/seed.py
"""

import asyncio
import sys
import os
from uuid import uuid4
from datetime import datetime, timezone

# ── Make sure `app` package is importable when run from project root ──
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import async_session, engine
from app.db.models import (
    User,
    Profile,
    UserSettings,
    AIModel,
    Template,
    StyleProfile,
    Prompt,
    PromptVersion,
)

# ── Password hashing ──────────────────────────────────────────────────
import bcrypt as _bcrypt

def hash_password(plain: str) -> str:
    return _bcrypt.hashpw(plain.encode("utf-8"), _bcrypt.gensalt()).decode("utf-8")


# ═══════════════════════════════════════════════════════════════════════
# SEED DATA
# ═══════════════════════════════════════════════════════════════════════

USERS = [
    {
        "email": "admin@promptiq.dev",
        "password": "Admin@1234",
        "full_name": "Admin User",
        "display_name": "Admin",
        "plan": "pro",
        "is_verified": True,
    },
    {
        "email": "alice@example.com",
        "password": "Alice@1234",
        "full_name": "Alice Johnson",
        "display_name": "Alice",
        "plan": "free",
        "is_verified": True,
    },
    {
        "email": "bob@example.com",
        "password": "Bob@1234",
        "full_name": "Bob Smith",
        "display_name": "Bob",
        "plan": "free",
        "is_verified": False,
    },
]

AI_MODELS = [
    {
        "provider": "mistral",
        "model_name": "mistral-small-latest",
        "description": "Mistral Small — fast, efficient, great for everyday prompt tasks.",
        "is_active": True,
        "supports_analysis": True,
        "supports_optimization": True,
    },
    {
        "provider": "mistral",
        "model_name": "mistral-large-latest",
        "description": "Mistral Large — high-quality reasoning for complex prompts.",
        "is_active": True,
        "supports_analysis": True,
        "supports_optimization": True,
    },
    {
        "provider": "openai",
        "model_name": "gpt-4o",
        "description": "OpenAI GPT-4o — multimodal flagship model.",
        "is_active": False,
        "supports_analysis": True,
        "supports_optimization": True,
    },
    {
        "provider": "openai",
        "model_name": "gpt-3.5-turbo",
        "description": "OpenAI GPT-3.5 Turbo — cost-effective for high-volume tasks.",
        "is_active": False,
        "supports_analysis": True,
        "supports_optimization": True,
    },
    {
        "provider": "anthropic",
        "model_name": "claude-3-sonnet",
        "description": "Anthropic Claude 3 Sonnet — balanced performance and safety.",
        "is_active": False,
        "supports_analysis": True,
        "supports_optimization": True,
    },
]

TEMPLATES_DATA = [
    {
        "title": "Code Review Assistant",
        "description": "Helps review code for bugs, style, and best practices.",
        "body": (
            "You are an expert software engineer. Review the following code:\n\n"
            "```\n{code}\n```\n\n"
            "Provide feedback on:\n"
            "1. Potential bugs or errors\n"
            "2. Code style and readability\n"
            "3. Performance improvements\n"
            "4. Security considerations\n"
            "Be concise and actionable."
        ),
        "mode": "technical",
        "category": "development",
        "role": "developer",
        "tags": ["code-review", "debugging", "best-practices"],
        "is_featured": True,
        "is_approved": True,
    },
    {
        "title": "Blog Post Writer",
        "description": "Generates engaging blog posts on any topic.",
        "body": (
            "You are a skilled content writer. Write a well-structured blog post about: {topic}\n\n"
            "Requirements:\n"
            "- Engaging headline\n"
            "- Introduction that hooks the reader\n"
            "- 3-5 main sections with subheadings\n"
            "- Practical examples or data points\n"
            "- Strong conclusion with a call to action\n"
            "- Tone: {tone} (default: informative)\n"
            "Target word count: {word_count} (default: 800)"
        ),
        "mode": "creative",
        "category": "content",
        "role": "writer",
        "tags": ["blog", "content-writing", "SEO"],
        "is_featured": True,
        "is_approved": True,
    },
    {
        "title": "API Documentation Generator",
        "description": "Generates clear API documentation from endpoint descriptions.",
        "body": (
            "You are a technical documentation expert. Generate comprehensive API documentation for:\n\n"
            "Endpoint: {endpoint}\n"
            "Method: {method}\n"
            "Description: {description}\n\n"
            "Include:\n"
            "- Overview\n"
            "- Request parameters (path, query, body)\n"
            "- Response schema with examples\n"
            "- Error codes\n"
            "- Code examples in Python and JavaScript\n"
            "Format as clean Markdown."
        ),
        "mode": "technical",
        "category": "documentation",
        "role": "developer",
        "tags": ["api", "documentation", "technical-writing"],
        "is_featured": False,
        "is_approved": True,
    },
    {
        "title": "Marketing Email Copywriter",
        "description": "Writes persuasive marketing emails that convert.",
        "body": (
            "You are a conversion-focused email copywriter. Write a marketing email for:\n\n"
            "Product/Service: {product}\n"
            "Target Audience: {audience}\n"
            "Goal: {goal} (e.g., drive sign-ups, promote sale)\n\n"
            "Structure:\n"
            "- Subject line (and 2 A/B alternatives)\n"
            "- Preview text\n"
            "- Email body with a clear value proposition\n"
            "- CTA button text\n"
            "- P.S. line\n"
            "Tone: Friendly yet professional. Max 200 words."
        ),
        "mode": "marketing",
        "category": "email",
        "role": "marketer",
        "tags": ["email", "copywriting", "marketing", "conversion"],
        "is_featured": True,
        "is_approved": True,
    },
    {
        "title": "Data Analysis Prompt",
        "description": "Structures prompts for analyzing datasets and deriving insights.",
        "body": (
            "You are a senior data analyst. Analyze the following data:\n\n"
            "{data}\n\n"
            "Provide:\n"
            "1. Key trends and patterns\n"
            "2. Anomalies or outliers\n"
            "3. Actionable insights (top 3)\n"
            "4. Recommended next steps\n"
            "5. Suggested visualizations\n"
            "Be precise, data-driven, and avoid speculation."
        ),
        "mode": "analytical",
        "category": "data",
        "role": "analyst",
        "tags": ["data-analysis", "insights", "analytics"],
        "is_featured": False,
        "is_approved": True,
    },
]

STYLE_PROFILES = [
    {
        "name": "Professional & Concise",
        "type": "brand_voice",
        "attributes": {
            "tone": "formal",
            "length": "short",
            "vocabulary": "business",
            "personality": ["authoritative", "clear", "direct"],
        },
        "injection_template": "Use a professional, concise tone. Avoid jargon. Be direct and action-oriented.",
        "is_active": True,
    },
    {
        "name": "Creative Storyteller",
        "type": "character",
        "attributes": {
            "tone": "imaginative",
            "length": "medium",
            "vocabulary": "rich",
            "personality": ["creative", "engaging", "descriptive"],
        },
        "injection_template": "Write with vivid imagery and narrative flair. Draw the reader in with storytelling techniques.",
        "is_active": True,
    },
    {
        "name": "Academic Researcher",
        "type": "brand_voice",
        "attributes": {
            "tone": "analytical",
            "length": "long",
            "vocabulary": "technical",
            "personality": ["precise", "evidence-based", "structured"],
        },
        "injection_template": "Use academic language with citations where relevant. Structure with clear hypotheses and evidence.",
        "is_active": False,
    },
    {
        "name": "Cinematic Epic",
        "type": "cinematic",
        "attributes": {
            "style": "epic",
            "lighting": "dramatic",
            "color_palette": "dark-gold",
            "camera": "wide-angle",
        },
        "injection_template": "Render in a cinematic epic style with dramatic lighting, wide establishing shots, and sweeping vistas.",
        "is_active": True,
    },
]

SAMPLE_PROMPTS = [
    {
        "title": "Explain async/await in Python",
        "original_prompt": "Explain how async and await work in Python with a real-world example.",
        "total_score": 72.5,
        "grade": "B",
    },
    {
        "title": "Write a landing page headline",
        "original_prompt": "Write a compelling headline for a SaaS product that helps developers write better prompts.",
        "total_score": 85.0,
        "grade": "A",
    },
    {
        "title": "Summarise quarterly sales data",
        "original_prompt": "Summarise the key trends from Q3 2024 sales data and suggest improvements for Q4.",
        "total_score": 68.0,
        "grade": "C",
    },
]


# ═══════════════════════════════════════════════════════════════════════
# SEEDER LOGIC
# ═══════════════════════════════════════════════════════════════════════

async def seed(session: AsyncSession) -> None:
    now = datetime.now(timezone.utc)

    print("\n🌱 Starting PromptIQ database seed...\n")

    # ── 1. AI Models ─────────────────────────────────────────────────
    print("  ➜ Seeding AI models...")
    ai_model_objects = []
    for m in AI_MODELS:
        obj = AIModel(id=uuid4(), created_at=now, updated_at=now, **m)
        session.add(obj)
        ai_model_objects.append(obj)
    await session.flush()
    mistral_model = ai_model_objects[0]  # mistral-small-latest
    print(f"    ✔ {len(ai_model_objects)} AI models added.")

    # ── 2. Templates ──────────────────────────────────────────────────
    print("  ➜ Seeding templates...")
    template_objects = []
    for t in TEMPLATES_DATA:
        obj = Template(
            id=uuid4(),
            created_at=now,
            updated_at=now,
            ai_model_id=mistral_model.id,
            **t,
        )
        session.add(obj)
        template_objects.append(obj)
    await session.flush()
    print(f"    ✔ {len(template_objects)} templates added.")

    # ── 3. Style Profiles ─────────────────────────────────────────────
    print("  ➜ Seeding style profiles...")
    for sp in STYLE_PROFILES:
        obj = StyleProfile(id=uuid4(), created_at=now, updated_at=now, **sp)
        session.add(obj)
    await session.flush()
    print(f"    ✔ {len(STYLE_PROFILES)} style profiles added.")

    # ── 4. Users + Profiles + Settings ───────────────────────────────
    print("  ➜ Seeding users, profiles, and settings...")
    profile_objects = []
    for u in USERS:
        user_id = uuid4()

        # User (auth record)
        user = User(
            id=user_id,
            email=u["email"],
            hashed_password=hash_password(u["password"]),
            is_active=True,
            is_verified=u["is_verified"],
            created_at=now,
            updated_at=now,
        )
        session.add(user)

        # Profile (linked to user)
        profile = Profile(
            id=user_id,  # same UUID as user (1-to-1)
            email=u["email"],
            full_name=u["full_name"],
            display_name=u["display_name"],
            plan=u["plan"],
            is_active=True,
            onboarding_completed=True,
            created_at=now,
            updated_at=now,
        )
        session.add(profile)
        profile_objects.append(profile)

        # UserSettings
        settings_obj = UserSettings(
            id=uuid4(),
            user_id=user_id,
            theme="dark",
            default_mode="general",
            default_model="mistral-small-latest",
            show_diff_by_default=True,
            auto_detect_intent=True,
            created_at=now,
            updated_at=now,
        )
        session.add(settings_obj)

    await session.flush()
    print(f"    ✔ {len(USERS)} users, profiles, and settings added.")

    # ── 5. Prompts + Versions (for first user: admin) ─────────────────
    print("  ➜ Seeding sample prompts and versions...")
    admin_profile = profile_objects[0]
    prompts_to_update = []
    for idx, p in enumerate(SAMPLE_PROMPTS):
        prompt_id = uuid4()
        version_id = uuid4()

        # Prompt
        prompt = Prompt(
            id=prompt_id,
            created_at=now,
            updated_at=now,
            user_id=admin_profile.id,
            ai_model_id=mistral_model.id,
            template_id=template_objects[idx % len(template_objects)].id,
            title=p["title"],
            original_prompt=p["original_prompt"],
            current_version_id=None,
            total_score=p["total_score"],
            grade=p["grade"],
        )
        session.add(prompt)
        prompts_to_update.append((prompt, version_id))

    # Flush prompts first
    await session.flush()

    for prompt, version_id in prompts_to_update:
        # Version 1 (original)
        version = PromptVersion(
            id=version_id,
            created_at=now,
            updated_at=now,
            prompt_id=prompt.id,
            version_number=1,
            version_type="original",
            content=prompt.original_prompt,
            change_summary="Initial version",
        )
        session.add(version)

    # Flush versions next
    await session.flush()

    # Link back current_version_id to prompts
    for prompt, version_id in prompts_to_update:
        prompt.current_version_id = version_id

    # Final flush for prompts updates
    await session.flush()
    print(f"    ✔ {len(SAMPLE_PROMPTS)} prompts + versions added.")

    # ── Commit all ────────────────────────────────────────────────────
    await session.commit()

    print("\n✅ Seed completed successfully!\n")
    print("━" * 50)
    print("  Test accounts:")
    for u in USERS:
        print(f"  📧 {u['email']}  🔑 {u['password']}")
    print("━" * 50)
    print("  Access Swagger UI → http://localhost:8000/docs\n")


async def main() -> None:
    async with async_session() as session:
        try:
            await seed(session)
        except Exception as e:
            await session.rollback()
            print(f"\n❌ Seed failed: {e}")
            raise


if __name__ == "__main__":
    asyncio.run(main())
