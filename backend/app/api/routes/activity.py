from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from app.schemas.models import ActivityLogEntry
from app.api.deps import get_db, get_current_user
from app.repository.db_repository import DBRepository

router = APIRouter(prefix="/activity", tags=["activity"])

@router.get("", response_model=List[ActivityLogEntry])
@router.get("/", response_model=List[ActivityLogEntry])
def get_activity_log(
    limit: int = Query(20, ge=1, le=100),
    repo: DBRepository = Depends(get_db),
    current_user=Depends(get_current_user)
):
    return repo.get_activity_log(limit)

@router.post("", response_model=ActivityLogEntry)
@router.post("/", response_model=ActivityLogEntry)
def create_activity(
    text: str = Query(...),
    user: Optional[str] = Query(None),
    repo: DBRepository = Depends(get_db),
    current_user=Depends(get_current_user)
):
    actual_user = user or current_user.full_name
    repo.add_activity(text=text, user=actual_user)
    return repo.get_activity_log(1)[0]
