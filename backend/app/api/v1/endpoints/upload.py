from fastapi import APIRouter, Depends, HTTPException, File, UploadFile, Form
from pydantic import BaseModel
from typing import Optional
import uuid
import shutil
import os
from pathlib import Path
from app.core.config import settings
from app.services.storage import storage_service
from app.core.celery_app import apply_async_with_context
from app.tasks.transcode import transcode_to_hls

router = APIRouter()

class PresignedUrlRequest(BaseModel):
    filename: str
    content_type: str
    file_type: str = "video" # video or image

class PresignedUrlResponse(BaseModel):
    upload_url: str
    fields: dict
    public_url: str
    file_key: str

@router.post("/presigned", response_model=PresignedUrlResponse)
def get_presigned_url(req: PresignedUrlRequest):
    """
    Generate a presigned URL for direct upload to S3/R2.
    If S3 is not configured (no credentials), fallback to local server upload URL logic.
    """
    # Check if S3 credentials exist
    use_s3 = settings.R2_ACCESS_KEY_ID and settings.R2_SECRET_ACCESS_KEY
    
    # Generate a unique object name
    ext = req.filename.split('.')[-1]
    if req.file_type == "video":
        object_name = f"uploads/videos/{uuid.uuid4()}.{ext}"
    else:
        object_name = f"uploads/images/{uuid.uuid4()}.{ext}"
    
    if use_s3:
        # S3 Logic
        data = storage_service.generate_presigned_upload_url(object_name, req.content_type)
        if not data:
            raise HTTPException(status_code=500, detail="Failed to generate upload URL")
        return data
    else:
        # Local Fallback Logic
        # We return a URL that points to our own backend's local upload endpoint
        # The frontend will POST to this URL just like it would to S3
        
        # In Docker/Local, we need to know our own host. 
        # For simplicity, we assume relative path or configured base URL.
        # Let's say we have an endpoint /api/v1/upload/local
        
        upload_url = "/api/v1/upload/local"
        
        # Public URL (where the file will be served from after upload)
        # Assuming we mount /static/uploads
        public_url = f"/static/{object_name}"
        
        return {
            "upload_url": upload_url,
            "fields": {"key": object_name}, # Pass key so local uploader knows where to put it
            "public_url": public_url,
            "file_key": object_name
        }

@router.post("/local")
async def local_upload(file: UploadFile = File(...), key: Optional[str] = Form(None)):
    """
    Handle local file upload (fallback for S3).
    """
    # If key is not provided in Form, try to get it from filename or generate new
    if not key:
        # Fallback generation if key missing
        ext = file.filename.split('.')[-1]
        key = f"uploads/images/{uuid.uuid4()}.{ext}" # Default to image for safety if unknown
    
    # Security check: ensure key starts with uploads/
    if not key.startswith("uploads/"):
        raise HTTPException(status_code=400, detail="Invalid key")
    
    # Define local path
    # In Docker, WORKDIR is /app. So "static" is /app/static.
    # Locally, it's relative to where we run uvicorn.
    # We must ensure we are writing to the absolute path where static files are served.
    
    # Better to use absolute path relative to project root
    base_dir = Path(__file__).resolve().parent.parent.parent.parent.parent
    upload_dir = base_dir / "static"
    file_path = upload_dir / key
    
    # Ensure directory exists
    file_path.parent.mkdir(parents=True, exist_ok=True)
    
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        print(f"Upload Error: {e}")
        raise HTTPException(status_code=500, detail=f"File save failed: {e}")
        
    return {"status": "ok", "key": key, "url": f"/static/{key}"}


@router.post("/avatar")
async def upload_avatar(file: UploadFile = File(...)):
    ext = file.filename.split('.')[-1]
    key = f"uploads/avatars/{uuid.uuid4()}.{ext}"
    return await local_upload(file=file, key=key)


@router.post("/background")
async def upload_background(file: UploadFile = File(...)):
    ext = file.filename.split('.')[-1]
    key = f"uploads/backgrounds/{uuid.uuid4()}.{ext}"
    return await local_upload(file=file, key=key)


class TranscodeRequest(BaseModel):
    post_id: int
    input_key: str


@router.post("/transcode-hls")
def request_transcode(req: TranscodeRequest):
    apply_async_with_context(transcode_to_hls, args=[int(req.post_id), str(req.input_key)])
    return {"ok": True}


class DeleteRequest(BaseModel):
    key: str


@router.post("/delete")
def delete_object(req: DeleteRequest):
    key = (req.key or "").strip().lstrip("/")
    if not key.startswith("uploads/"):
        raise HTTPException(status_code=400, detail="Invalid key")

    use_s3 = settings.R2_ACCESS_KEY_ID and settings.R2_SECRET_ACCESS_KEY
    if use_s3:
        ok = storage_service.delete_object(key)
        if not ok:
            raise HTTPException(status_code=500, detail="Delete failed")
        return {"ok": True}

    base_dir = Path(__file__).resolve().parent.parent.parent.parent.parent
    file_path = (base_dir / "static" / key)
    try:
        if file_path.exists():
            file_path.unlink()
        return {"ok": True}
    except Exception:
        raise HTTPException(status_code=500, detail="Delete failed")
