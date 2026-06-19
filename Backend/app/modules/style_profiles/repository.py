from sqlalchemy.orm import Session
from typing import List, Optional, Union
import uuid
from datetime import datetime
import json
from app.modules.style_profiles.models import StyleProfile
from app.modules.style_profiles.schemas import CreateStyleProfileRequest, UpdateStyleProfileRequest

class StyleProfileRepository:
    @staticmethod
    def create_style(db: Session, obj_in: CreateStyleProfileRequest, user_id: Optional[uuid.UUID] = None) -> StyleProfile:
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
        db.commit()
        db.refresh(db_obj)
        return db_obj

    @staticmethod
    def get_style_by_id(db: Session, id: uuid.UUID) -> Optional[StyleProfile]:
        return db.query(StyleProfile).filter(
            StyleProfile.id == id,
            StyleProfile.deleted_at.is_(None)
        ).first()

    @staticmethod
    def get_all_styles(db: Session, skip: int = 0, limit: int = 100) -> List[StyleProfile]:
        return db.query(StyleProfile).filter(
            StyleProfile.deleted_at.is_(None)
        ).offset(skip).limit(limit).all()

    @staticmethod
    def update_style(db: Session, db_obj: StyleProfile, obj_in: UpdateStyleProfileRequest) -> StyleProfile:
        update_data = obj_in.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(db_obj, field, value)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    @staticmethod
    def soft_delete_style(db: Session, db_obj: StyleProfile) -> StyleProfile:
        db_obj.deleted_at = datetime.utcnow()
        db_obj.is_active = False
        db.commit()
        db.refresh(db_obj)
        return db_obj

    @staticmethod
    def activate_style(db: Session, db_obj: StyleProfile) -> StyleProfile:
        db_obj.is_active = True
        db.commit()
        db.refresh(db_obj)
        return db_obj

    @staticmethod
    def deactivate_style(db: Session, db_obj: StyleProfile) -> StyleProfile:
        db_obj.is_active = False
        db.commit()
        db.refresh(db_obj)
        return db_obj

    @staticmethod
    def get_active_styles(db: Session) -> List[StyleProfile]:
        return db.query(StyleProfile).filter(
            StyleProfile.is_active == True,
            StyleProfile.deleted_at.is_(None)
        ).all()

    @staticmethod
    def duplicate_style(db: Session, db_obj: StyleProfile) -> StyleProfile:
        new_obj = StyleProfile(
            user_id=db_obj.user_id,
            name=f"{db_obj.name} Copy",
            type=db_obj.type,
            attributes=db_obj.attributes,
            injection_template=db_obj.injection_template,
            thumbnail_url=db_obj.thumbnail_url,
            is_active=False,
            use_count=0
        )
        db.add(new_obj)
        db.commit()
        db.refresh(new_obj)
        return new_obj

    @staticmethod
    def search_styles(db: Session, query: str, type: Optional[str] = None) -> List[StyleProfile]:
        q = db.query(StyleProfile).filter(
            StyleProfile.deleted_at.is_(None)
        )
        if query:
            q = q.filter(StyleProfile.name.ilike(f"%{query}%"))
        if type:
            q = q.filter(StyleProfile.type == type)
        return q.all()

    @staticmethod
    def get_styles_by_type(db: Session, type: str) -> List[StyleProfile]:
        return db.query(StyleProfile).filter(
            StyleProfile.type == type,
            StyleProfile.deleted_at.is_(None)
        ).all()

    @staticmethod
    def get_popular_styles(db: Session, limit: int = 10) -> List[StyleProfile]:
        return db.query(StyleProfile).filter(
            StyleProfile.deleted_at.is_(None)
        ).order_by(StyleProfile.use_count.desc()).limit(limit).all()

    @staticmethod
    def get_recent_styles(db: Session, limit: int = 10) -> List[StyleProfile]:
        return db.query(StyleProfile).filter(
            StyleProfile.deleted_at.is_(None)
        ).order_by(StyleProfile.created_at.desc()).limit(limit).all()

    @staticmethod
    def get_recommended_styles(db: Session, limit: int = 10) -> List[StyleProfile]:
        return db.query(StyleProfile).filter(
            StyleProfile.deleted_at.is_(None)
        ).order_by(StyleProfile.is_active.desc(), StyleProfile.use_count.desc()).limit(limit).all()

    @staticmethod
    def increment_use_count(db: Session, db_obj: StyleProfile) -> StyleProfile:
        db_obj.use_count += 1
        db.commit()
        db.refresh(db_obj)
        return db_obj

    @staticmethod
    def get_usage_history(db: Session) -> List[dict]:
        styles = db.query(StyleProfile).filter(StyleProfile.deleted_at.is_(None)).all()
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
    def get_usage_analytics(db: Session) -> dict:
        styles = db.query(StyleProfile).filter(StyleProfile.deleted_at.is_(None)).all()
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
    def import_style(db: Session, json_data: Union[dict, str]) -> StyleProfile:
        if isinstance(json_data, str):
            try:
                data = json.loads(json_data)
            except Exception:
                raise ValueError("Invalid JSON string format")
        else:
            data = json_data
            
        db_obj = StyleProfile(
            name=data.get("name", "Imported Style"),
            type=data.get("type", "art_style"),
            attributes=data.get("attributes", {}),
            injection_template=data.get("injection_template"),
            thumbnail_url=data.get("thumbnail_url"),
            is_active=False
        )
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    @staticmethod
    def export_style(db: Session, db_obj: StyleProfile) -> dict:
        return {
            "name": db_obj.name,
            "type": db_obj.type,
            "attributes": db_obj.attributes,
            "injection_template": db_obj.injection_template,
            "thumbnail_url": db_obj.thumbnail_url
        }

    @staticmethod
    def get_style_by_id_raw(db: Session, id: uuid.UUID) -> Optional[StyleProfile]:
        return db.query(StyleProfile).filter(
            StyleProfile.id == id
        ).first()

    @staticmethod
    def restore_style(db: Session, db_obj: StyleProfile) -> StyleProfile:
        db_obj.deleted_at = None
        db.commit()
        db.refresh(db_obj)
        return db_obj

    @staticmethod
    def get_deleted_styles(db: Session) -> List[StyleProfile]:
        return db.query(StyleProfile).filter(
            StyleProfile.deleted_at.is_not(None)
        ).all()

    @staticmethod
    def permanent_delete_style(db: Session, db_obj: StyleProfile) -> None:
        db.delete(db_obj)
        db.commit()

