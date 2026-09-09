from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from app.schemas.models import (
    TestSessionOut, TestSessionCreate, TestSessionUpdate, SessionStatus, UserRole,
    ComplianceResult, RejectRequest
)
from app.api.deps import get_db, get_current_user, require_role
from app.repository.db_repository import DBRepository
from app.services.metrology import evaluate_session

router = APIRouter(prefix="/sessions", tags=["sessions"])

@router.get("", response_model=List[TestSessionOut])
@router.get("/", response_model=List[TestSessionOut])
def get_sessions(
    status: Optional[SessionStatus] = None,
    instrument_id: Optional[str] = None,
    tester: Optional[str] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    repo: DBRepository = Depends(get_db),
    current_user=Depends(get_current_user)
):
    sessions = repo.get_sessions()
    
    if status:
        sessions = [s for s in sessions if s.status == status]
    if instrument_id:
        sessions = [s for s in sessions if s.instrument_id == instrument_id]
    if tester:
        sessions = [s for s in sessions if s.tester == tester]
    if from_date:
        sessions = [s for s in sessions if s.test_date >= from_date]
    if to_date:
        sessions = [s for s in sessions if s.test_date <= to_date]
        
    return sessions

@router.get("/{id}", response_model=TestSessionOut)
def get_session(id: str, repo: DBRepository = Depends(get_db), current_user=Depends(get_current_user)):
    session = repo.get_session_by_id(id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session

@router.post("", response_model=TestSessionOut)
@router.post("/", response_model=TestSessionOut)
def create_session(
    data: TestSessionCreate,
    repo: DBRepository = Depends(get_db),
    current_user=Depends(require_role(UserRole.INSPECTOR, UserRole.ADMIN))
):
    session = repo.create_session(data)
    repo.add_activity(f"Created test session {session.id}", user=current_user.full_name)
    return session

@router.put("/{id}", response_model=TestSessionOut)
def update_session(
    id: str,
    data: TestSessionUpdate,
    repo: DBRepository = Depends(get_db),
    current_user=Depends(require_role(UserRole.INSPECTOR, UserRole.ADMIN))
):
    session = repo.update_session(id, data)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    repo.add_activity(f"Updated observations for session {session.id}", user=current_user.full_name)
    return session

@router.post("/{id}/evaluate", response_model=ComplianceResult)
def evaluate_test_session(
    id: str,
    repo: DBRepository = Depends(get_db),
    current_user=Depends(get_current_user)
):
    session = repo.get_session_by_id(id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    instrument = repo.get_instrument_by_id(session.instrument_id)
    if not instrument:
        raise HTTPException(status_code=404, detail="Instrument not found")

    result = evaluate_session(session, instrument)
    repo.add_activity(f"Evaluated session {session.id}", user=current_user.full_name)
    return result

@router.patch("/{id}/submit", response_model=TestSessionOut)
def submit_session(
    id: str,
    repo: DBRepository = Depends(get_db),
    current_user=Depends(require_role(UserRole.INSPECTOR, UserRole.ADMIN))
):
    session = repo.get_session_by_id(id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.status != SessionStatus.DRAFT:
        raise HTTPException(status_code=400, detail="Only DRAFT sessions can be submitted")
    
    session = repo.set_session_status(id, SessionStatus.PENDING_REVIEW)
    repo.add_activity(f"Submitted session {session.id} for review", user=current_user.full_name)
    return session

@router.patch("/{id}/approve", response_model=TestSessionOut)
def approve_session(
    id: str,
    repo: DBRepository = Depends(get_db),
    current_user=Depends(require_role(UserRole.REVIEWER, UserRole.ADMIN))
):
    session = repo.get_session_by_id(id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.status != SessionStatus.PENDING_REVIEW:
        raise HTTPException(status_code=400, detail="Only PENDING_REVIEW sessions can be approved")
    
    session = repo.set_session_status(id, SessionStatus.APPROVED)
    repo.add_activity(f"Approved session {session.id}", user=current_user.full_name)
    return session

@router.patch("/{id}/reject", response_model=TestSessionOut)
def reject_session(
    id: str,
    data: RejectRequest,
    repo: DBRepository = Depends(get_db),
    current_user=Depends(require_role(UserRole.REVIEWER, UserRole.ADMIN))
):
    session = repo.get_session_by_id(id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.status != SessionStatus.PENDING_REVIEW:
        raise HTTPException(status_code=400, detail="Only PENDING_REVIEW sessions can be rejected")
    
    session = repo.set_session_status(id, SessionStatus.REJECTED, reason=data.rejection_reason)
    repo.add_activity(f"Rejected session {session.id}", user=current_user.full_name)
    return session
