"""
export_seed_data.py — connects to the local Docker dev DB via asyncpg
and prints a ready-to-commit scripts/seed.py to stdout.

Run inside the web container:
    docker exec promptiq-web python /tmp/export_seed_data.py > scripts/seed.py
"""

import asyncio
import json
import sys
from datetime import datetime

import asyncpg

DSN = "postgresql://postgres:admin@db:5432/prompt_enhancer"


async def fetch_all():
    conn = await asyncpg.connect(DSN)

    ai_models = await conn.fetch("""
        SELECT id::text, provider, model_name, description,
               is_active, supports_analysis, supports_optimization
        FROM ai_models
        ORDER BY provider, model_name
    """)

    templates = await conn.fetch("""
        SELECT
            t.id::text,
            t.title,
            t.description,
            t.body,
            t.mode,
            t.category,
            t.ai_model_id::text,
            t.tags,
            t.embedding::text   AS embedding_str,
            t.is_featured,
            t.is_approved,
            t.use_count,
            t.role
        FROM templates t
        ORDER BY t.category, t.title
    """)

    style_profiles = await conn.fetch("""
        SELECT id::text, name, type, attributes::text,
               injection_template, thumbnail_url,
               is_active, use_count
        FROM style_profiles
        WHERE user_id IS NULL
        ORDER BY name
    """)

    await conn.close()
    return (
        [dict(r) for r in ai_models],
        [dict(r) for r in templates],
        [dict(r) for r in style_profiles],
    )


def py_str(v):
    if v is None:
        return "None"
    return repr(str(v))


def py_bool(v):
    return "True" if v else "False"


def py_int(v):
    return str(int(v)) if v is not None else "0"


def py_list(v):
    if v is None:
        return "[]"
    if isinstance(v, str):
        try:
            v = json.loads(v)
        except Exception:
            return "[]"
    return repr(list(v))


def embedding_list(emb_str):
    """Convert '[0.1,0.2,...]' postgres vector text to a Python list literal."""
    if emb_str is None:
        return "None"
    inner = emb_str.strip()[1:-1]
    floats = [float(x) for x in inner.split(",")]
    return repr(floats)


async def main():
    ai_models, templates, style_profiles = await fetch_all()
    generated_at = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

    lines = [
        '"""',
        'seed.py — populate the test database with reference data.',
        '',
        'Called by scripts/bootstrap_test_db.sh in migrate mode (CI and local',
        'fresh-bootstrap). Inserts ai_models, templates, and style_profiles.',
        'User accounts are handled separately by scripts/ensure_test_user.py.',
        '',
        'Idempotent: rows are upserted via ON CONFLICT DO NOTHING so the script',
        'is safe to re-run against a partially-seeded database.',
        '',
        f'Auto-generated {generated_at} from the local dev database.',
        'Do NOT edit by hand — regenerate with scripts/export_seed_data.py.',
        '"""',
        '',
        'import asyncio',
        'import json',
        'import os',
        'import sys',
        '',
        'sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))',
        '',
        'from sqlalchemy import text',
        'from app.db.session import async_session, engine',
        '',
        '',
        '# ---------------------------------------------------------------------------',
        '# Reference data (exported from local dev DB)',
        '# ---------------------------------------------------------------------------',
        '',
    ]

    # AI_MODELS
    lines.append('AI_MODELS = [')
    for m in ai_models:
        lines.append('    {')
        lines.append(f'        "id": {py_str(m["id"])},')
        lines.append(f'        "provider": {py_str(m["provider"])},')
        lines.append(f'        "model_name": {py_str(m["model_name"])},')
        lines.append(f'        "description": {py_str(m["description"])},')
        lines.append(f'        "is_active": {py_bool(m["is_active"])},')
        lines.append(f'        "supports_analysis": {py_bool(m["supports_analysis"])},')
        lines.append(f'        "supports_optimization": {py_bool(m["supports_optimization"])},')
        lines.append('    },')
    lines.append(']')
    lines.append('')

    # TEMPLATES
    lines.append('TEMPLATES = [')
    for t in templates:
        lines.append('    {')
        lines.append(f'        "id": {py_str(t["id"])},')
        lines.append(f'        "title": {py_str(t["title"])},')
        lines.append(f'        "description": {py_str(t["description"])},')
        lines.append(f'        "body": {py_str(t["body"])},')
        lines.append(f'        "mode": {py_str(t["mode"])},')
        lines.append(f'        "category": {py_str(t["category"])},')
        lines.append(f'        "ai_model_id": {py_str(t["ai_model_id"])},')
        lines.append(f'        "tags": {py_list(t["tags"])},')
        lines.append(f'        "embedding": {embedding_list(t["embedding_str"])},')
        lines.append(f'        "is_featured": {py_bool(t["is_featured"])},')
        lines.append(f'        "is_approved": {py_bool(t["is_approved"])},')
        lines.append(f'        "use_count": {py_int(t["use_count"])},')
        lines.append(f'        "role": {py_str(t["role"])},')
        lines.append('    },')
    lines.append(']')
    lines.append('')

    # STYLE_PROFILES
    lines.append('STYLE_PROFILES = [')
    for s in style_profiles:
        lines.append('    {')
        lines.append(f'        "id": {py_str(s["id"])},')
        lines.append(f'        "name": {py_str(s["name"])},')
        lines.append(f'        "type": {py_str(s["type"])},')
        lines.append(f'        "attributes": {py_str(s["attributes"])},')
        lines.append(f'        "injection_template": {py_str(s["injection_template"])},')
        lines.append(f'        "thumbnail_url": {py_str(s["thumbnail_url"])},')
        lines.append(f'        "is_active": {py_bool(s["is_active"])},')
        lines.append(f'        "use_count": {py_int(s["use_count"])},')
        lines.append('    },')
    lines.append(']')
    lines.append('')

    # Seed functions
    lines += [
        '',
        '# ---------------------------------------------------------------------------',
        '# Seed functions',
        '# ---------------------------------------------------------------------------',
        '',
        'async def seed_ai_models(conn) -> int:',
        '    result = await conn.execute(',
        '        text("""',
        '            INSERT INTO ai_models',
        '                (id, provider, model_name, description,',
        '                 is_active, supports_analysis, supports_optimization)',
        '            VALUES',
        '                (:id, :provider, :model_name, :description,',
        '                 :is_active, :supports_analysis, :supports_optimization)',
        '            ON CONFLICT (provider, model_name) DO NOTHING',
        '        """),',
        '        AI_MODELS,',
        '    )',
        '    return result.rowcount',
        '',
        '',
        'async def seed_templates(conn) -> int:',
        '    inserted = 0',
        '    for row in TEMPLATES:',
        '        emb = row["embedding"]',
        '        if emb is not None:',
        '            emb_clause = "ARRAY[:embedding]::vector"',
        '        else:',
        '            emb_clause = "NULL"',
        '        result = await conn.execute(',
        '            text(f"""',
        '                INSERT INTO templates',
        '                    (id, title, description, body, mode, category,',
        '                     ai_model_id, tags, embedding,',
        '                     is_featured, is_approved, use_count, role)',
        '                VALUES',
        '                    (:id, :title, :description, :body, :mode, :category,',
        '                     :ai_model_id, :tags::jsonb, {emb_clause},',
        '                     :is_featured, :is_approved, :use_count, :role)',
        '                ON CONFLICT (id) DO NOTHING',
        '            """),',
        '            {**row, "tags": json.dumps(row["tags"])},',
        '        )',
        '        inserted += result.rowcount',
        '    return inserted',
        '',
        '',
        'async def seed_style_profiles(conn) -> int:',
        '    result = await conn.execute(',
        '        text("""',
        '            INSERT INTO style_profiles',
        '                (id, name, type, attributes, injection_template,',
        '                 thumbnail_url, is_active, use_count)',
        '            VALUES',
        '                (:id, :name, :type, :attributes::json, :injection_template,',
        '                 :thumbnail_url, :is_active, :use_count)',
        '            ON CONFLICT (id) DO NOTHING',
        '        """),',
        '        STYLE_PROFILES,',
        '    )',
        '    return result.rowcount',
        '',
        '',
        'async def main() -> None:',
        '    url = os.environ.get("DATABASE_URL", "")',
        '    db_name = url.rsplit("/", 1)[-1].split("?")[0]',
        '    if not db_name.endswith("_test"):',
        '        raise SystemExit(',
        '            f"REFUSING: database \'{db_name}\' does not end in \'_test\'.\\n"',
        '            "Set DATABASE_URL to the test database before running this script."',
        '        )',
        '',
        '    async with async_session() as session:',
        '        async with session.begin():',
        '            conn = await session.connection()',
        '            n_models = await seed_ai_models(conn)',
        '            n_templates = await seed_templates(conn)',
        '            n_styles = await seed_style_profiles(conn)',
        '',
        '    await engine.dispose()',
        '    print(f"  ai_models:      {n_models} inserted")',
        '    print(f"  templates:      {n_templates} inserted")',
        '    print(f"  style_profiles: {n_styles} inserted")',
        '',
        '',
        'if __name__ == "__main__":',
        '    asyncio.run(main())',
    ]

    print("\n".join(lines))


asyncio.run(main())
