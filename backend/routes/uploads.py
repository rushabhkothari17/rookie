"""File upload route — stores files in MongoDB for use in intake questions.

Files are stored temporarily and automatically deleted after 24 hours.
"""
from __future__ import annotations

import base64
import uuid
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import Response

from routes.auth import get_current_user
from db.session import db as async_db
from services.audit_service import create_audit_log

router = APIRouter(prefix="/api/uploads", tags=["uploads"])

MAX_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB
EXPIRY_HOURS = 24  # Files expire after 24 hours


def _db():
    import os
    from pymongo import MongoClient
    client = MongoClient(os.environ["MONGO_URL"])
    return client[os.environ["DB_NAME"]]


@router.post("")
async def upload_file(file: UploadFile = File(...), user: dict = Depends(get_current_user)):
    content = await file.read()
    if len(content) > MAX_SIZE_BYTES:
        raise HTTPException(413, detail="File too large (max 10 MB)")

    upload_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(hours=EXPIRY_HOURS)
    
    db = _db()
    db.file_uploads.insert_one({
        "id": upload_id,
        "filename": file.filename,
        "content_type": file.content_type or "application/octet-stream",
        "size": len(content),
        "data_b64": base64.b64encode(content).decode(),
        "user_id": user.get("id", ""),
        "tenant_id": user.get("tenant_id", ""),
        "created_at": now.isoformat(),
        "expires_at": expires_at.isoformat(),
    })
    
    # Create TTL index if it doesn't exist (MongoDB will auto-delete expired docs)
    db.file_uploads.create_index("expires_at", expireAfterSeconds=0)

    return {
        "id": upload_id,
        "filename": file.filename,
        "size": len(content),
        "content_type": file.content_type,
        "url": f"/api/uploads/{upload_id}",
        "expires_in": f"{EXPIRY_HOURS} hours",
    }


@router.get("/{upload_id}")
async def get_upload(upload_id: str, user: dict = Depends(get_current_user)):
    db = _db()
    doc = db.file_uploads.find_one({"id": upload_id}, {"_id": 0})
    if not doc:
        raise HTTPException(404, detail="File not found")
    content = base64.b64decode(doc["data_b64"])
    return Response(
        content=content,
        media_type=doc.get("content_type", "application/octet-stream"),
        headers={"Content-Disposition": f'attachment; filename="{doc["filename"]}"'},
    )
