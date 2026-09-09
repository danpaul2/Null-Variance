import os
from typing import List
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from app.schemas.models import AttachmentOut
from app.api.deps import get_store, get_current_user
from app.repository.memory_store import MemoryStore

router = APIRouter(prefix="", tags=["attachments"])

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

@router.post("/sessions/{id}/attachments", response_model=AttachmentOut)
async def upload_attachment(
    id: str,
    file: UploadFile = File(...),
    store: MemoryStore = Depends(get_store),
    current_user=Depends(get_current_user)
):
    session = store.get_session_by_id(id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
        
    file_path = os.path.join(UPLOAD_DIR, file.filename)
    
    contents = await file.read()
    with open(file_path, "wb") as f:
        f.write(contents)
    
    file_size = f"{len(contents) / 1024:.2f} KB"
    
    attachment = store.add_attachment(id, file.filename, file_size, file.content_type)
    store.add_activity(f"Uploaded attachment {file.filename} to session {id}", user=current_user.full_name)
    return attachment

@router.get("/sessions/{id}/attachments", response_model=List[AttachmentOut])
def list_attachments(
    id: str,
    store: MemoryStore = Depends(get_store),
    current_user=Depends(get_current_user)
):
    session = store.get_session_by_id(id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    return store.get_attachments_by_session(id)

@router.delete("/sessions/{id}/attachments/{attachment_id}")
def delete_attachment(
    id: str,
    attachment_id: str,
    store: MemoryStore = Depends(get_store),
    current_user=Depends(get_current_user)
):
    session = store.get_session_by_id(id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    attachments = store.get_attachments_by_session(id)
    att_to_delete = next((a for a in attachments if a.id == attachment_id), None)
    
    if not att_to_delete:
        raise HTTPException(status_code=404, detail="Attachment not found")
    
    attachments.remove(att_to_delete)
    if att_to_delete in session.attachments:
        session.attachments.remove(att_to_delete)
    
    # Optionally delete file from disk, but not explicitly requested.
    store.add_activity(f"Deleted attachment {att_to_delete.file_name} from session {id}", user=current_user.full_name)
    return {"message": "Attachment deleted successfully"}
