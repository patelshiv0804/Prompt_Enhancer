from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_
from typing import List, Optional, Union
import uuid
from datetime import datetime
import json
from app.db.models import StyleProfile
from app.schemas.style_profiles import CreateStyleProfileRequest, UpdateStyleProfileRequest


def _visibility_condition(user_id: Optional[uuid.UUID]):
    """Owner-or-null visibility filter (N1).

    When ``user_id`` is provided, a style is visible only if the caller owns it
    or it is a shared/legacy profile with no owner (``user_id IS NULL``). When
    ``user_id`` is None the filter is a no-op, preserving the previous behaviour
    for any non-authenticated caller.
    """
    if user_id is None:
        return None
    return or_(StyleProfile.user_id == user_id, StyleProfile.user_id.is_(None))


class StyleProfileRepository:
    @staticmethod
    async def create_style(db: AsyncSession, obj_in: CreateStyleProfileRequest, user_id: Optional[uuid.UUID] = None) -> StyleProfile:
        db_obj = StyleProfile(
            user_id=user_id,
            name=obj_in.name,
            type=obj_in.type,
            attributes=obj_in.attributes,
            injection_template=obj_in.injection_template,
            thumbnail_url=obj_in.thumbnail_url,
            is_active=False
        )
        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj

    @staticmethod
    async def get_style_by_id(db: AsyncSession, id: uuid.UUID, user_id: Optional[uuid.UUID] = None) -> Optional[StyleProfile]:
        statement = select(StyleProfile).where(
            StyleProfile.id == id,
            StyleProfile.deleted_at.is_(None)
        )
        cond = _visibility_condition(user_id)
        if cond is not None:
            statement = statement.where(cond)
        result = await db.execute(statement)
        return result.scalar_one_or_none()

    @staticmethod
    async def get_all_styles(db: AsyncSession, skip: int = 0, limit: int = 100, user_id: Optional[uuid.UUID] = None) -> List[StyleProfile]:
        statement = select(StyleProfile).where(
            StyleProfile.deleted_at.is_(None)
        )
        cond = _visibility_condition(user_id)
        if cond is not None:
            statement = statement.where(cond)
        statement = statement.order_by(StyleProfile.created_at.asc(), StyleProfile.id.asc()).offset(skip).limit(limit)
        result = await db.execute(statement)
        return list(result.scalars().all())

    @staticmethod
    async def update_style(db: AsyncSession, db_obj: StyleProfile, obj_in: UpdateStyleProfileRequest) -> StyleProfile:
        update_data = obj_in.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(db_obj, field, value)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj

    @staticmethod
    async def soft_delete_style(db: AsyncSession, db_obj: StyleProfile) -> StyleProfile:
        db_obj.deleted_at = datetime.utcnow()
        db_obj.is_active = False
        await db.commit()
        await db.refresh(db_obj)
        return db_obj

    @staticmethod
    async def activate_style(db: AsyncSession, db_obj: StyleProfile) -> StyleProfile:
        db_obj.is_active = True
        await db.commit()
        await db.refresh(db_obj)
        return db_obj

    @staticmethod
    async def deactivate_style(db: AsyncSession, db_obj: StyleProfile) -> StyleProfile:
        db_obj.is_active = False
        await db.commit()
        await db.refresh(db_obj)
        return db_obj

    @staticmethod
    async def get_active_styles(db: AsyncSession, user_id: Optional[uuid.UUID] = None) -> List[StyleProfile]:
        statement = select(StyleProfile).where(
            StyleProfile.is_active == True,
            StyleProfile.deleted_at.is_(None)
        )
        cond = _visibility_condition(user_id)
        if cond is not None:
            statement = statement.where(cond)
        result = await db.execute(statement)
        return list(result.scalars().all())

    @staticmethod
    async def duplicate_style(db: AsyncSession, db_obj: StyleProfile, user_id: Optional[uuid.UUID] = None) -> StyleProfile:
        new_obj = StyleProfile(
            user_id=user_id if user_id is not None else db_obj.user_id,
            name=f"{db_obj.name} Copy",
            type=db_obj.type,
            attributes=db_obj.attributes,
            injection_template=db_obj.injection_template,
            thumbnail_url=db_obj.thumbnail_url,
            is_active=False,
            use_count=0
        )
        db.add(new_obj)
        await db.commit()
        await db.refresh(new_obj)
        return new_obj

    @staticmethod
    async def search_styles(db: AsyncSession, query: str, type: Optional[str] = None, user_id: Optional[uuid.UUID] = None) -> List[StyleProfile]:
        statement = select(StyleProfile).where(
            StyleProfile.deleted_at.is_(None)
        )
        cond = _visibility_condition(user_id)
        if cond is not None:
            statement = statement.where(cond)
        if query:
            statement = statement.where(StyleProfile.name.ilike(f"%{query}%"))
        if type:
            statement = statement.where(StyleProfile.type == type)
        result = await db.execute(statement)
        return list(result.scalars().all())

    @staticmethod
    async def get_styles_by_type(db: AsyncSession, type: str, user_id: Optional[uuid.UUID] = None) -> List[StyleProfile]:
        statement = select(StyleProfile).where(
            StyleProfile.type == type,
            StyleProfile.deleted_at.is_(None)
        )
        cond = _visibility_condition(user_id)
        if cond is not None:
            statement = statement.where(cond)
        result = await db.execute(statement)
        return list(result.scalars().all())

    @staticmethod
    async def get_popular_styles(db: AsyncSession, limit: int = 10, user_id: Optional[uuid.UUID] = None) -> List[StyleProfile]:
        statement = select(StyleProfile).where(
            StyleProfile.deleted_at.is_(None)
        )
        cond = _visibility_condition(user_id)
        if cond is not None:
            statement = statement.where(cond)
        statement = statement.order_by(StyleProfile.use_count.desc()).limit(limit)
        result = await db.execute(statement)
        return list(result.scalars().all())

    @staticmethod
    async def get_recent_styles(db: AsyncSession, limit: int = 10, user_id: Optional[uuid.UUID] = None) -> List[StyleProfile]:
        statement = select(StyleProfile).where(
            StyleProfile.deleted_at.is_(None)
        )
        cond = _visibility_condition(user_id)
        if cond is not None:
            statement = statement.where(cond)
        statement = statement.order_by(StyleProfile.created_at.desc()).limit(limit)
        result = await db.execute(statement)
        return list(result.scalars().all())

    @staticmethod
    async def get_recommended_styles(db: AsyncSession, limit: int = 10, user_id: Optional[uuid.UUID] = None) -> List[StyleProfile]:
        statement = select(StyleProfile).where(
            StyleProfile.deleted_at.is_(None)
        )
        cond = _visibility_condition(user_id)
        if cond is not None:
            statement = statement.where(cond)
        statement = statement.order_by(StyleProfile.is_active.desc(), StyleProfile.use_count.desc()).limit(limit)
        result = await db.execute(statement)
        return list(result.scalars().all())

    @staticmethod
    async def increment_use_count(db: AsyncSession, db_obj: StyleProfile) -> StyleProfile:
        db_obj.use_count += 1
        await db.commit()
        await db.refresh(db_obj)
        return db_obj

    @staticmethod
    async def get_usage_history(db: AsyncSession, user_id: Optional[uuid.UUID] = None) -> List[dict]:
        statement = select(StyleProfile).where(StyleProfile.deleted_at.is_(None))
        cond = _visibility_condition(user_id)
        if cond is not None:
            statement = statement.where(cond)
        result = await db.execute(statement)
        styles = result.scalars().all()
        history = []
        for s in styles:
            if s.use_count > 0:
                history.append({
                    "style_id": str(s.id),
                    "style_name": s.name,
                    "use_count": s.use_count,
                    "last_used_at": s.updated_at.isoformat() if s.updated_at else None
                })
        return history

    @staticmethod
    async def get_usage_analytics(db: AsyncSession, user_id: Optional[uuid.UUID] = None) -> dict:
        statement = select(StyleProfile).where(StyleProfile.deleted_at.is_(None))
        cond = _visibility_condition(user_id)
        if cond is not None:
            statement = statement.where(cond)
        result = await db.execute(statement)
        styles = result.scalars().all()
        total_uses = sum(s.use_count for s in styles)
        by_type = {}
        for s in styles:
            by_type[s.type] = by_type.get(s.type, 0) + s.use_count
        return {
            "total_style_profiles": len(styles),
            "total_uses": total_uses,
            "usage_by_type": by_type
        }

    @staticmethod
    async def import_style(db: AsyncSession, json_data: Union[dict, str], user_id: Optional[uuid.UUID] = None) -> StyleProfile:
        if isinstance(json_data, str):
            try:
                data = json.loads(json_data)
            except Exception:
                raise ValueError("Invalid JSON string format")
        else:
            data = json_data

        db_obj = StyleProfile(
            user_id=user_id,
            name=data.get("name", "Imported Style"),
            type=data.get("type", "art_style"),
            attributes=data.get("attributes", {}),
            injection_template=data.get("injection_template"),
            thumbnail_url=data.get("thumbnail_url"),
            is_active=False
        )
        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj

    @staticmethod
    async def export_style(db: AsyncSession, db_obj: StyleProfile) -> dict:
        return {
            "name": db_obj.name,
            "type": db_obj.type,
            "attributes": db_obj.attributes,
            "injection_template": db_obj.injection_template,
            "thumbnail_url": db_obj.thumbnail_url
        }

    @staticmethod
    async def get_style_by_id_raw(db: AsyncSession, id: uuid.UUID, user_id: Optional[uuid.UUID] = None) -> Optional[StyleProfile]:
        statement = select(StyleProfile).where(
            StyleProfile.id == id
        )
        cond = _visibility_condition(user_id)
        if cond is not None:
            statement = statement.where(cond)
        result = await db.execute(statement)
        return result.scalar_one_or_none()

    @staticmethod
    async def restore_style(db: AsyncSession, db_obj: StyleProfile) -> StyleProfile:
        db_obj.deleted_at = None
        await db.commit()
        await db.refresh(db_obj)
        return db_obj

    @staticmethod
    async def get_deleted_styles(db: AsyncSession, user_id: Optional[uuid.UUID] = None) -> List[StyleProfile]:
        statement = select(StyleProfile).where(
            StyleProfile.deleted_at.is_not(None)
        )
        cond = _visibility_condition(user_id)
        if cond is not None:
            statement = statement.where(cond)
        result = await db.execute(statement)
        return list(result.scalars().all())

    @staticmethod
    async def permanent_delete_style(db: AsyncSession, db_obj: StyleProfile) -> None:
        await db.delete(db_obj)
        await db.commit()
