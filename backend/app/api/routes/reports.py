import io
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from app.api.deps import get_db, get_current_user
from app.repository.db_repository import DBRepository
from app.services.metrology import evaluate_session
from app.services.reports import generate_pdf, generate_docx

router = APIRouter(prefix="/reports", tags=["reports"])

@router.get("/{session_id}/pdf")
def get_report_pdf(
    session_id: str,
    repo: DBRepository = Depends(get_db),
    current_user=Depends(get_current_user)
):
    session = repo.get_session_by_id(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    instrument = repo.get_instrument_by_id(session.instrument_id)
    if not instrument:
        raise HTTPException(status_code=404, detail="Instrument not found")

    result = evaluate_session(session, instrument)
    pdf_bytes = generate_pdf(session, instrument, result)

    repo.add_activity(f"Generated PDF report for session {session.id}", user=current_user.full_name)

    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=Report_{session.id}.pdf"}
    )

@router.get("/{session_id}/docx")
def get_report_docx(
    session_id: str,
    repo: DBRepository = Depends(get_db),
    current_user=Depends(get_current_user)
):
    session = repo.get_session_by_id(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    instrument = repo.get_instrument_by_id(session.instrument_id)
    if not instrument:
        raise HTTPException(status_code=404, detail="Instrument not found")

    result = evaluate_session(session, instrument)
    docx_bytes = generate_docx(session, instrument, result)

    repo.add_activity(f"Generated DOCX report for session {session.id}", user=current_user.full_name)

    return StreamingResponse(
        io.BytesIO(docx_bytes),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f"attachment; filename=Report_{session.id}.docx"}
    )
