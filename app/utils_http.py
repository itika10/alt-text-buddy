# app/utils_http.py
from fastapi import UploadFile, HTTPException

MAX_BYTES = 10 * 1024 * 1024  # 10 MB
ALLOWED_TYPES = {"image/png", "image/jpeg", "image/webp"}

async def read_image_or_raise(upload: UploadFile) -> bytes:
    ctype = (upload.content_type or "").lower()
    if ctype not in ALLOWED_TYPES:
        raise HTTPException(status_code=415, detail=f"Unsupported content type: {ctype}")
    data = await upload.read()
    if len(data) > MAX_BYTES:
        raise HTTPException(status_code=413, detail="Image too large")
    return data
