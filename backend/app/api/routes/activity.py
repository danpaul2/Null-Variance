from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from app.schemas.models import ActivityLogEntry
from app.api.deps import get_store, get_current_user
from app.repository.memory_store import MemoryStore

router = APIRouter(prefix="/activity", tags=["activity"])

@router.get("", response_model=List[ActivityLogEntry])
@router.get("/", response_model=List[ActivityLogEntry])
def get_activity_log(
    limit: int = Query(20, ge=1, le=100),
    store: MemoryStore = Depends(get_store),
    current_user=Depends(get_current_user)
):
    return store.get_activity_log(limit)

@router.post("", response_model=ActivityLogEntry)
@router.post("/", response_model=ActivityLogEntry)
def create_activity(
    text: str = Query(...),
    user: Optional[str] = Query(None),
    store: MemoryStore = Depends(get_store),
    current_user=Depends(get_current_user)
):
    actual_user = user or current_user.full_name
    store.add_activity(text=text, user=actual_user)
    return store.activity_log[0]
