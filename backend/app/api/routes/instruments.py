from typing import List, Optional, Any, Dict
from fastapi import APIRouter, Depends, HTTPException
from app.schemas.models import InstrumentOut, InstrumentCreate, UserRole
from app.api.deps import get_db, get_current_user, require_role
from app.repository.db_repository import DBRepository

router = APIRouter(prefix="/instruments", tags=["instruments"])


@router.get("", response_model=List[InstrumentOut])
@router.get("/", response_model=List[InstrumentOut])
def get_instruments(
    search: Optional[str] = None,
    repo: DBRepository = Depends(get_db),
    current_user=Depends(get_current_user)
):
    if search:
        return repo.search_instruments(search)
    return repo.get_instruments()


@router.get("/{id}")
def get_instrument(
    id: str,
    repo: DBRepository = Depends(get_db),
    current_user=Depends(get_current_user)
) -> Dict[str, Any]:
    instrument = repo.get_instrument_by_id(id)
    if not instrument:
        raise HTTPException(status_code=404, detail="Instrument not found")
    sessions = repo.get_sessions_by_instrument(id)
    return {"instrument": instrument, "sessions": sessions}


@router.post("", response_model=InstrumentOut)
@router.post("/", response_model=InstrumentOut)
def create_instrument(
    data: InstrumentCreate,
    repo: DBRepository = Depends(get_db),
    current_user=Depends(require_role(UserRole.INSPECTOR, UserRole.ADMIN))
):
    instrument = repo.create_instrument(data)
    repo.add_activity(f"Created instrument {instrument.manufacturer} {instrument.model}", user=current_user.full_name)
    return instrument
