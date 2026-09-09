from typing import List, Optional, Any, Dict
from fastapi import APIRouter, Depends, HTTPException, Query
from app.schemas.models import InstrumentOut, InstrumentCreate, UserRole, TestSessionOut
from app.api.deps import get_store, get_current_user, require_role
from app.repository.memory_store import MemoryStore

router = APIRouter(prefix="/instruments", tags=["instruments"])

@router.get("", response_model=List[InstrumentOut])
@router.get("/", response_model=List[InstrumentOut])
def get_instruments(
    search: Optional[str] = None,
    store: MemoryStore = Depends(get_store),
    current_user=Depends(get_current_user)
):
    if search:
        return store.search_instruments(search)
    return store.get_instruments()

@router.get("/{id}")
def get_instrument(id: str, store: MemoryStore = Depends(get_store), current_user=Depends(get_current_user)) -> Dict[str, Any]:
    instrument = store.get_instrument_by_id(id)
    if not instrument:
        raise HTTPException(status_code=404, detail="Instrument not found")
    
    sessions = store.get_sessions_by_instrument(id)
    return {
        "instrument": instrument,
        "sessions": sessions
    }

@router.post("", response_model=InstrumentOut)
@router.post("/", response_model=InstrumentOut)
def create_instrument(
    data: InstrumentCreate,
    store: MemoryStore = Depends(get_store),
    current_user=Depends(require_role(UserRole.INSPECTOR, UserRole.ADMIN))
):
    instrument = store.create_instrument(data)
    store.add_activity(f"Created instrument {instrument.manufacturer} {instrument.model}", user=current_user.full_name)
    return instrument
