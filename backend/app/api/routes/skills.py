import json

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.app.api.deps import get_current_user
from backend.app.core.database import get_db
from backend.app.repositories.skill_repo import SkillRepository


router = APIRouter()


@router.get("")
async def list_enabled_skills(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    items = SkillRepository.list(db, is_enabled=True)
    return {
        "total": len(items),
        "items": [
            {
                "id": item.id,
                "name": item.name,
                "display_name": item.display_name,
                "triggers": json.loads(item.triggers) if item.triggers else [],
                "description": item.description,
                "category": item.category,
                "is_enabled": item.is_enabled,
            }
            for item in items
        ],
    }
