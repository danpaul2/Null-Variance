import os
from typing import List
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from app.schemas.models import AttachmentOut
from app.api.deps import get_db, get_current_user
from app.repository.db_repository import DBRepository

router = APIRouter(prefix="", tags=["attachments"])

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

@router.post("/sessions/{id}/attachments", response_model=AttachmentOut)
async def upload_attachment(
    id: str,
    file: UploadFile = File(...),
    repo: DBRepository = Depends(get_db),
    current_user=Depends(get_current_user)
):
    session = repo.get_session_by_id(id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
        
    file_path = os.path.join(UPLOAD_DIR, file.filename)
    
    contents = await file.read()
    with open(file_path, "wb") as f:
        f.write(contents)
    
    file_size = f"{len(contents) / 1024:.2f} KB"
    
    attachment = repo.add_attachment(id, file.filename, file_size, file.content_type)
    repo.add_activity(f"Uploaded attachment {file.filename} to session {id}", user=current_user.full_name)
    return attachment

@router.get("/sessions/{id}/attachments", response_model=List[AttachmentOut])
def list_attachments(
    id: str,
    repo: DBRepository = Depends(get_db),
    current_user=Depends(get_current_user)
):
    session = repo.get_session_by_id(id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    return repo.get_attachments_by_session(id)

@router.delete("/sessions/{id}/attachments/{attachment_id}")
def delete_attachment(
    id: str,
    attachment_id: str,
    repo: DBRepository = Depends(get_db),
    current_user=Depends(get_current_user)
):
    session = repo.get_session_by_id(id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    deleted = repo.delete_attachment(attachment_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Attachment not found")
    
    repo.add_activity(f"Deleted attachment {attachment_id} from session {id}", user=current_user.full_name)
    return {"message": "Attachment deleted successfully"}
